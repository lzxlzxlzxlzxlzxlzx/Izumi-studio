import json
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse
from app.db.database import get_conn, generate_id
from app.models.message import IChatMessage, ISwipe
from app.models.runtime import IGenerateRequest, IGenerateChunk
from app.services.llm_router import chat_stream, chat_sync, CHARACTER_TOOLS, estimate_message_tokens
from app.services.context_assembler import assemble
from app.services.card_manager import get_card
from app.services.preset_manager import get_default_preset
from app.services.character_registry import process_skill_call
from app.services.worldbook_engine import scan as scan_worldbook
from app.services.memory_system import get_output, extract_and_store, get_memories as get_ltm_memories, format_memories_for_prompt
from app.models.memory import IMemoryOutput
from app.models.worldbook import IWorldBook

logger = logging.getLogger(__name__)

router = APIRouter()


POST_PROCESS_CHARACTERS_PROMPT = """你是故事角色管理器。请根据本轮对话内容（包括用户的明确指令、故事剧情和长期记忆），识别需要创建或修改的角色。

当前已登记的角色：
{current_characters}

当前长期记忆：
{memories}

本轮用户输入：
{user_input}

本轮故事内容：
{story_content}

请使用可用工具来管理角色。规则（按优先级从高到低）：
1. 【用户明确指令优先】如果用户明确要求创建某角色、修改某角色的属性（包括新增属性或修改现有值）、或删除某角色，请立即执行相应操作
2. 新角色在故事中出场且尚未登记 → 调用 create_character 创建（attributes 包含基本描述即可）
3. 已有角色的属性在故事中发生变化 → 调用 update_character 更新（只传变化的属性）
4. 角色死亡或离场 → 调用 update_character 设置 is_alive=False 或 is_active=False
5. 如果角色没有变化，不要调用任何工具"""


def _load_story_characters(session_id: str) -> list[dict]:
    """Load registered story characters from DB as plain dicts."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT name, attributes_json, is_active, is_alive FROM story_characters WHERE session_id = ? ORDER BY first_seen_round ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({
            "name": r["name"],
            "attributes": json.loads(r["attributes_json"] or "{}"),
            "is_active": bool(r["is_active"]),
            "is_alive": bool(r["is_alive"]),
        })
    return result


def _ensure_card_npcs_initialized(session_id: str, card) -> None:
    """Persist card NPCs into story_characters table on first use."""
    if not (card and card.character and card.character.npcs):
        return
    conn = get_conn()
    existing = conn.execute(
        "SELECT COUNT(*) as cnt FROM story_characters WHERE session_id = ?", (session_id,)
    ).fetchone()
    if existing and existing["cnt"] > 0:
        conn.close()
        return  # already initialized
    import uuid
    for npc in card.character.npcs:
        char_id = str(uuid.uuid4())
        attrs = dict(npc.attributes) if npc.attributes else {}
        attrs["name"] = npc.name
        conn.execute(
            """INSERT INTO story_characters
               (id, session_id, name, attributes_json, is_active, is_alive,
                first_seen_round, last_seen_round, source, images_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'card_definition', '[]', datetime('now'), datetime('now'))""",
            (
                char_id, session_id, npc.name,
                json.dumps(attrs, ensure_ascii=False),
                int(getattr(npc, 'start_active', True)),
                1,
            ),
        )
    conn.commit()
    conn.close()


@router.get("/messages/{session_id}", response_model=list[IChatMessage])
def list_messages(session_id: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY idx ASC",
        (session_id,),
    ).fetchall()
    messages = [_row_to_message(r) for r in rows]
    conn.close()
    return messages


@router.post("", response_model=IChatMessage, status_code=201)
def create_user_message(req: IGenerateRequest):
    """Save user message. Does NOT trigger generation — use /stream for that."""
    conn = get_conn()

    sess = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (req.session_id,)).fetchone()
    if not sess:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    last = conn.execute(
        "SELECT idx, round_index FROM chat_messages WHERE session_id = ? ORDER BY idx DESC LIMIT 1",
        (req.session_id,),
    ).fetchone()
    next_idx = (last["idx"] + 1) if last else 0
    next_round = (last["round_index"] + 1) if last and last["round_index"] is not None else 0

    mid = generate_id()
    conn.execute(
        """INSERT INTO chat_messages (id, session_id, role, name, content, idx, round_index, created_at)
           VALUES (?, ?, 'user', 'user', ?, ?, ?, datetime('now'))""",
        (mid, req.session_id, req.input, next_idx, next_round),
    )
    conn.execute(
        "UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?",
        (req.session_id,),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM chat_messages WHERE id = ?", (mid,)).fetchone()
    conn.close()
    return _row_to_message(row)


@router.post("/stream/{session_id}")
async def stream_generate(session_id: str, input: str = Query(...)):
    """
    SSE streaming generation endpoint.

    Flow:
    1. Save user message
    2. Load session + card + history + worldbook + memories
    3. Assemble context (main LLM receives system prompts + character info + memories)
    4. Stream LLM response (storytelling only — no tool calling)
    5. Save assistant message
    6. Extract long-term memories from this exchange
    7. Post-process: character management via dedicated LLM call
    8. Yield done event to frontend

    Parameters:
        input: The user's message text (query parameter for simplicity)
    """
    conn = get_conn()

    # 1. Load session
    sess_row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    if not sess_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    card_id = sess_row["card_id"]
    conn.close()

    # 2. Load card
    card = get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Character card not found")

    # 3. Save user message
    user_msg = _save_user_message(session_id, input)

    # 4. Load full message history
    all_messages = _load_messages(session_id)

    # 5. Load preset (card-specific or default)
    preset = None
    if card.preset_name:
        from app.services.preset_manager import get_preset
        preset = get_preset(card.preset_name)
    if not preset:
        preset = get_default_preset()

    # 6. Load worldbooks from card and scan for activated entries
    worldbook_result = None
    if card.worldbook_ids:
        try:
            wbs = _load_worldbooks_by_ids(card.worldbook_ids)
            if wbs:
                chat_text = "\n".join(
                    f"{m.name or 'user'}: {m.content}" for m in all_messages[:-1]
                    if isinstance(m.content, str)
                )
                # Include current user input so keywords in the latest query trigger relevant entries
                if input:
                    chat_text += f"\nuser: {input}"
                extras = {
                    "char_desc": card.character.description or "",
                    "char_personality": card.character.personality or "",
                    "char_scenario": card.character.scenario or "",
                }
                worldbook_result = scan_worldbook(wbs, chat_text, extra_buffers=extras)
                if worldbook_result:
                    logger.info(
                        f"[session={session_id[:8]}] worldbook_scan | "
                        f"before={len(worldbook_result.before_char)} after={len(worldbook_result.after_char)} "
                        f"depth={len(worldbook_result.at_depth)}"
                    )
        except Exception:
            logger.exception(f"[session={session_id[:8]}] worldbook scan failed")
            worldbook_result = None

    # 7. Load long-term memories for context enrichment
    memory_output = get_output(session_id)

    # 8. Assemble context (with registered story characters, worldbook, memory)
    _ensure_card_npcs_initialized(session_id, card)
    story_chars = _load_story_characters(session_id)
    initial_messages = assemble(
        card=card,
        chat_history=all_messages[:-1],  # exclude the just-saved user message
        current_input=input,
        preset=preset,
        worldbook=worldbook_result,
        story_characters=story_chars,
        memory=memory_output,
    )

    # 7. Model params from card's preset_config
    pcfg = card.preset_config
    model = pcfg.model or "deepseek-chat"
    temperature = getattr(pcfg, 'temperature', 0.7) or 0.7

    # Log context summary
    sys_msg = initial_messages[0]["content"] if initial_messages else ""
    token_est = estimate_message_tokens(initial_messages)
    logger.info(
        f"[session={session_id[:8]}] request | model={model} msgs={len(initial_messages)} "
        f"tokens~{token_est} wc={pcfg.word_count_min}-{pcfg.word_count_max} "
        f"temp={temperature} input_len={len(input)}"
    )
    logger.debug(f"[session={session_id[:8]}] system_prompt:\n{sys_msg}")

    async def event_generator():
        messages = list(initial_messages)

        try:
            collected_content: list[str] = []

            async for chunk in chat_stream(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=getattr(pcfg, 'max_tokens', 2048) or 2048,
                top_p=getattr(pcfg, 'top_p', 0.95) or 0.95,
                frequency_penalty=getattr(pcfg, 'frequency_penalty', 0.3) or 0.3,
                presence_penalty=getattr(pcfg, 'presence_penalty', 0.2) or 0.2,
            ):
                if chunk.type == "token":
                    collected_content.append(chunk.token or "")
                    yield {"data": json.dumps({"type": "token", "token": chunk.token}, ensure_ascii=False)}

                elif chunk.type == "done":
                    full_text = "".join(collected_content)
                    logger.info(
                        f"[session={session_id[:8]}] response | len={len(full_text)} text={full_text[:200]}"
                    )
                    _save_assistant_message(
                        session_id=session_id,
                        content=full_text,
                        char_name=card.character.name,
                        tool_calls=[],
                    )

                    # ---- Long-term memory extraction ----
                    try:
                        async def _extract_memory_llm(messages: list[dict]) -> str:
                            resp = await chat_sync(
                                messages=messages,
                                model="deepseek-chat",
                                temperature=0.3,
                                max_tokens=512,
                            )
                            choices = resp.get("choices", [])
                            if choices:
                                return choices[0].get("message", {}).get("content", "") or ""
                            return ""

                        new_memories = await extract_and_store(
                            session_id=session_id,
                            user_input=input,
                            assistant_output=full_text,
                            llm_func=_extract_memory_llm,
                        )
                        logger.info(
                            f"[session={session_id[:8]}] memory | extracted {len(new_memories)} new facts"
                        )
                    except Exception:
                        logger.exception(f"[session={session_id[:8]}] memory extraction failed")

                    # ---- Post-processing: character management ----
                    post_tool_calls: list[dict] = []
                    try:
                        current_chars = _load_story_characters(session_id)
                        char_list_str_lines = []
                        for c in current_chars:
                            status = f"{'出场' if c['is_active'] else '离场'}, {'存活' if c['is_alive'] else '死亡'}"
                            attrs = c.get("attributes") or {}
                            attr_items = [f"{k}={v}" for k, v in attrs.items()
                                          if k not in ("name", "is_active", "is_alive")]
                            if attr_items:
                                attr_str = ", ".join(str(a) for a in attr_items[:12])
                                char_list_str_lines.append(f"- {c['name']} [{status}] 属性：{attr_str}")
                            else:
                                char_list_str_lines.append(f"- {c['name']} [{status}]")
                        char_list_str = "\n".join(char_list_str_lines) or "(暂无登记角色)"

                        mem_list = get_ltm_memories(session_id)
                        mem_text = format_memories_for_prompt(mem_list) or "(无长期记忆)"

                        pp_messages = [
                            {"role": "system", "content": POST_PROCESS_CHARACTERS_PROMPT.format(
                                current_characters=char_list_str,
                                memories=mem_text,
                                user_input=input,
                                story_content=full_text,
                            )},
                        ]
                        pp_resp = await chat_sync(
                            messages=pp_messages,
                            model="deepseek-chat",
                            temperature=0.1,
                            max_tokens=500,
                            tools=CHARACTER_TOOLS,
                        )
                        pp_choices = pp_resp.get("choices", [])
                        if pp_choices:
                            pp_msg = pp_choices[0].get("message", {})
                            pp_tool_calls = pp_msg.get("tool_calls", [])
                            if pp_tool_calls:
                                logger.info(
                                    f"[session={session_id[:8]}] post-process | {len(pp_tool_calls)} tool calls"
                                )
                                for tc in pp_tool_calls:
                                    fn = tc.get("function", {})
                                    logger.info(
                                        f"[session={session_id[:8]}] post-process | "
                                        f"{fn.get('name', '?')} {fn.get('arguments', '{}')}"
                                    )
                                    result = process_skill_call(
                                        session_id=session_id,
                                        message_id=user_msg.id,
                                        message_index=user_msg.index,
                                        tool_call=tc,
                                        card=card,
                                    )
                                    if result.success:
                                        post_tool_calls.append(tc)
                                        yield {"data": json.dumps({
                                            "type": "tool_call",
                                            "tool_call": tc,
                                        }, ensure_ascii=False)}
                                    else:
                                        logger.warning(
                                            f"[session={session_id[:8]}] post-process | tool failed: {result.error}"
                                        )
                            else:
                                logger.info(
                                    f"[session={session_id[:8]}] post-process | no changes"
                                )
                        else:
                            logger.info(
                                f"[session={session_id[:8]}] post-process | no response"
                            )
                    except Exception as pp_e:
                        logger.warning(
                            f"[session={session_id[:8]}] post-process error: {pp_e}"
                        )

                    # Build character_changes summary from post-processing tool calls
                    character_changes = []
                    for tc in post_tool_calls:
                        fn = tc.get("function", {})
                        fname = fn.get("name", "")
                        try:
                            fargs = json.loads(fn.get("arguments", "{}"))
                        except (json.JSONDecodeError, TypeError):
                            fargs = {}
                        if fname == "create_character":
                            character_changes.append({"action": "created", "name": fargs.get("name", "?")})
                        elif fname == "update_character":
                            character_changes.append({"action": "updated", "name": fargs.get("name", "?")})
                        elif fname == "delete_character":
                            character_changes.append({"action": "deleted", "name": fargs.get("name", "?")})

                    logger.info(f"[session={session_id[:8]}] stream | completed")

                    yield {"data": json.dumps({
                        "type": "done",
                        "full_response": full_text,
                        "tool_calls": post_tool_calls,
                        "character_changes": character_changes,
                    }, ensure_ascii=False)}
                    return

                elif chunk.type == "error":
                    logger.error(f"[session={session_id[:8]}] stream error: {chunk.error}")
                    yield {"data": json.dumps({"type": "error", "error": chunk.error}, ensure_ascii=False)}
                    return

        except Exception as e:
            logger.exception(f"[session={session_id[:8]}] stream exception")
            yield {"data": json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(event_generator())


@router.post("/rollback/{session_id}")
def rollback(session_id: str, target_index: int):
    conn = get_conn()
    conn.execute("DELETE FROM chat_messages WHERE session_id = ? AND idx > ?", (session_id, target_index))
    conn.execute("DELETE FROM character_change_logs WHERE session_id = ? AND message_index > ?", (session_id, target_index))
    conn.execute("UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "target_index": target_index}


@router.get("/{session_id}/memories")
def list_memories(session_id: str):
    """Return all long-term memories for a session."""
    return get_ltm_memories(session_id)


# ============================================================
# Helpers
# ============================================================

def _load_worldbooks_by_ids(ids: list[str]) -> list[IWorldBook]:
    """Load worldbook objects from the DB index by their IDs."""
    if not ids:
        return []
    conn = get_conn()
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT file_path FROM worldbooks_index WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    conn.close()

    result: list[IWorldBook] = []
    for row in rows:
        try:
            raw = json.loads(open(row["file_path"], "r", encoding="utf-8").read())
            result.append(IWorldBook(**raw))
        except Exception:
            logger.warning(f"Failed to load worldbook: {row['file_path']}")
    return result


def _save_user_message(session_id: str, content: str) -> IChatMessage:
    conn = get_conn()
    last = conn.execute(
        "SELECT idx, round_index FROM chat_messages WHERE session_id = ? ORDER BY idx DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    next_idx = (last["idx"] + 1) if last else 0
    next_round = (last["round_index"] + 1) if last and last["round_index"] is not None else 0

    mid = generate_id()
    conn.execute(
        """INSERT INTO chat_messages (id, session_id, role, name, content, idx, round_index, created_at)
           VALUES (?, ?, 'user', 'user', ?, ?, ?, datetime('now'))""",
        (mid, session_id, content, next_idx, next_round),
    )
    conn.execute("UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?", (session_id,))
    conn.commit()

    row = conn.execute("SELECT * FROM chat_messages WHERE id = ?", (mid,)).fetchone()
    conn.close()
    return _row_to_message(row)


def _save_tool_result(
    session_id: str,
    tool_call_id: str,
    content: str,
) -> IChatMessage:
    """Persist a tool result message so it appears in history on subsequent turns."""
    conn = get_conn()
    last = conn.execute(
        "SELECT idx, round_index FROM chat_messages WHERE session_id = ? ORDER BY idx DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    next_idx = (last["idx"] + 1) if last else 0
    round_idx = last["round_index"] if last else 0

    mid = generate_id()
    conn.execute(
        """INSERT INTO chat_messages (id, session_id, role, name, content, idx, round_index, created_at, tool_call_id)
           VALUES (?, ?, 'tool', '', ?, ?, ?, datetime('now'), ?)""",
        (mid, session_id, content, next_idx, round_idx, tool_call_id),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM chat_messages WHERE id = ?", (mid,)).fetchone()
    conn.close()
    return _row_to_message(row)


def _save_assistant_message(
    session_id: str,
    content: str,
    char_name: str,
    tool_calls: list | None = None,
) -> IChatMessage:
    conn = get_conn()
    last = conn.execute(
        "SELECT idx, round_index FROM chat_messages WHERE session_id = ? ORDER BY idx DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    next_idx = (last["idx"] + 1) if last else 0
    round_idx = last["round_index"] if last else 0

    mid = generate_id()
    conn.execute(
        """INSERT INTO chat_messages (id, session_id, role, name, content, idx, round_index, created_at, tool_calls_json)
           VALUES (?, ?, 'assistant', ?, ?, ?, ?, datetime('now'), ?)""",
        (mid, session_id, char_name, content, next_idx, round_idx, json.dumps(tool_calls or [], ensure_ascii=False)),
    )
    conn.execute("UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?", (session_id,))
    conn.commit()

    row = conn.execute("SELECT * FROM chat_messages WHERE id = ?", (mid,)).fetchone()
    conn.close()
    return _row_to_message(row)


def _load_messages(session_id: str) -> list[IChatMessage]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY idx ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [_row_to_message(r) for r in rows]


def _row_to_message(row) -> IChatMessage:
    return IChatMessage(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        name=row["name"] or "",
        content=_parse_content(row),
        media=json.loads(row["media_json"] or "[]"),
        index=row["idx"],
        round_index=row["round_index"],
        created_at=row["created_at"],
        swipes=[ISwipe(**s) for s in json.loads(row["swipes_json"] or "[]")],
        swipe_index=row["swipe_index"] or 0,
        has_checkpoint=bool(row["has_checkpoint"]),
        locked=bool(row["locked"]),
        tool_calls=json.loads(row["tool_calls_json"] or "[]"),
        tool_call_id=row["tool_call_id"],
    )


def _parse_content(row) -> str | list:
    parts = json.loads(row["content_parts_json"] or "null")
    if parts:
        return parts
    return row["content"] or ""
