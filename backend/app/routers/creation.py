"""
Creation API — 角色卡创作路由

Endpoints:
- CRUD for creation sessions (mode='creation')
- SSE streaming creation chat with card field tools
- File upload & parsing
- Draft / publish workflow
"""

import json
import uuid
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Request
from sse_starlette.sse import EventSourceResponse
from app.config import settings
from app.db.database import get_conn, generate_id
from app.models.session import IChatSession, EChatMode
from app.models.card import ICharacterCard
from app.services.creation_service import creation_chat_stream, parse_uploaded_file, get_linked_worldbooks
from app.services.card_manager import get_card, update_card, create_card

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Session CRUD
# ============================================================


@router.get("/sessions")
def list_sessions():
    """List all creation sessions ordered by last update."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT cs.*, cc.name as card_name
           FROM chat_sessions cs
           LEFT JOIN character_cards cc ON cs.card_id = cc.id
           WHERE cs.mode = 'creation'
           ORDER BY cs.updated_at DESC"""
    ).fetchall()
    sessions = []
    for r in rows:
        s = _row_to_session(r)
        s.card_name = r["card_name"] or ""
        sessions.append(s)
    conn.close()
    return sessions


@router.post("/sessions", status_code=201)
def create_session():
    """Create a new creation session with a blank character card."""
    # Use a unique name to avoid upsert collision with leftover drafts
    card_name = f"未命名角色卡 {generate_id()[-6:]}"
    card = create_card(name=card_name, description="", tags=[])

    # Re-read to get the actual DB id (create_card may upsert by name)
    conn = get_conn()
    row = conn.execute("SELECT id FROM character_cards WHERE name = ?", (card_name,)).fetchone()
    actual_card_id = row["id"] if row else card.id
    conn.close()

    # Create creation session
    conn = get_conn()
    sid = generate_id()
    conn.execute(
        """INSERT INTO chat_sessions (id, card_id, mode, name, greeting_index, created_at, updated_at)
           VALUES (?, ?, 'creation', '创作对话', 0, datetime('now'), datetime('now'))""",
        (sid, actual_card_id),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (sid,)).fetchone()
    conn.close()

    return {
        "session": _row_to_session(row),
        "card": get_card(actual_card_id),
    }


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete a creation session and its associated card."""
    conn = get_conn()

    sess = conn.execute(
        "SELECT * FROM chat_sessions WHERE id = ? AND mode = 'creation'", (session_id,)
    ).fetchone()
    if not sess:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    card_id = sess["card_id"]

    # Delete messages and session
    conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))

    # Delete the card if no other sessions reference it
    if card_id and card_id != "_konata_system":
        ref_count = conn.execute(
            "SELECT COUNT(*) FROM chat_sessions WHERE card_id = ? AND id != ?",
            (card_id, session_id),
        ).fetchone()[0]
        if ref_count == 0:
            conn.execute("DELETE FROM character_cards WHERE id = ?", (card_id,))

    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Get a creation session with its current card."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    card = get_card(row["card_id"]) if row["card_id"] else None
    return {
        "session": _row_to_session(row),
        "card": card,
    }


# ============================================================
# Messages
# ============================================================


@router.get("/messages/{session_id}")
def list_messages(session_id: str):
    """List messages for a creation session."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY idx ASC",
        (session_id,),
    ).fetchall()
    messages = []
    for r in rows:
        messages.append({
            "id": r["id"],
            "session_id": r["session_id"],
            "role": r["role"],
            "name": r["name"] or "",
            "content": r["content"] or "",
            "index": r["idx"],
            "round_index": r["round_index"],
            "created_at": r["created_at"],
            "tool_calls": json.loads(r["tool_calls_json"] or "[]"),
            "tool_call_id": r["tool_call_id"],
        })
    conn.close()
    return messages


# ============================================================
# SSE Streaming
# ============================================================


@router.post("/stream/{session_id}")
async def stream_creation(session_id: str, input: str = Query(...)):
    """SSE streaming chat for card creation (with tool calling for card fields)."""
    conn = get_conn()

    sess = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    if not sess:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    card_id = sess["card_id"]
    conn.close()

    if not card_id:
        raise HTTPException(status_code=400, detail="Session has no associated card")

    async def event_generator():
        try:
            async for chunk in creation_chat_stream(
                session_id=session_id,
                card_id=card_id,
                input_text=input,
                model="deepseek-chat",
            ):
                if chunk.type == "token":
                    yield {"data": json.dumps({"type": "token", "token": chunk.token}, ensure_ascii=False)}
                elif chunk.type == "tool_call":
                    yield {"data": json.dumps({"type": "tool_call", "tool_call": chunk.tool_call}, ensure_ascii=False)}
                elif chunk.type == "done":
                    payload = {"type": "done", "full_response": chunk.full_response}
                    if chunk.tool_call:
                        try:
                            payload["card_changes"] = json.loads(chunk.tool_call)
                        except (json.JSONDecodeError, TypeError):
                            pass
                    yield {"data": json.dumps(payload, ensure_ascii=False)}
                    return
                elif chunk.type == "error":
                    yield {"data": json.dumps({"type": "error", "error": chunk.error}, ensure_ascii=False)}
                    return
        except Exception as e:
            logger.exception(f"[creation] stream failed session={session_id[:8]}")
            yield {"data": json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(event_generator())


# ============================================================
# Card Field Editing (from FieldEditor)
# ============================================================


@router.patch("/card/{card_id}")
async def patch_card_field(card_id: str, request: Request):
    """Directly update a card field from the field editor panel."""
    card = get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    body = await request.json()
    field = body.get("field")
    value = body.get("value")
    if not field:
        raise HTTPException(status_code=400, detail="field is required")

    # Map field paths to update_card arguments
    char_fields = {"personality", "background", "scenario", "speaking_style", "first_mes", "mes_example", "creator_notes"}

    if field in char_fields:
        char_data = card.character.model_dump()
        char_data[field] = value
        update_card(card_id, character=char_data)
    elif field == "alternate_greetings":
        char_data = card.character.model_dump()
        if isinstance(value, str):
            char_data["alternate_greetings"] = [g.strip() for g in value.split("\n") if g.strip()]
        else:
            char_data["alternate_greetings"] = value
        update_card(card_id, character=char_data)
    elif field == "npcs":
        # value is a list of NPC dicts
        char_data = card.character.model_dump()
        char_data["npcs"] = value if isinstance(value, list) else []
        update_card(card_id, character=char_data)
    elif field in ("writing_style", "model", "temperature", "top_p", "frequency_penalty", "presence_penalty", "max_tokens", "word_count_min", "word_count_max"):
        cfg = card.preset_config.model_dump()
        cfg[field] = value
        update_card(card_id, preset_config=cfg)
    elif field in ("style_tags", "character_appearance"):
        img = card.image_config.model_dump()
        img[field] = value
        update_card(card_id, image_config=img)
    elif field == "tags":
        update_card(card_id, tags=value if isinstance(value, list) else [value])
    elif field in ("name", "description", "system_prompt", "post_history_instructions"):
        update_card(card_id, **{field: value})
    else:
        raise HTTPException(status_code=400, detail=f"Unknown field: {field}")

    # Return updated card
    updated = get_card(card_id)
    return updated


# ============================================================
# File Upload & Parse
# ============================================================


ALLOWED_TEXT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload/{session_id}")
async def upload_file(session_id: str, file: UploadFile = File(...)):
    """Upload a text file (.txt, .md, .docx), parse its content, and inject as user message."""
    conn = get_conn()
    sess = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    if not sess:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
    conn.close()

    # Validate file type
    filename = file.filename or "unknown.txt"
    ext = Path(filename).suffix.lower()
    if ext not in (".txt", ".md", ".docx"):
        raise HTTPException(400, f"不支持的文件格式: {ext}，仅支持 .txt, .md, .docx")

    # Save to temp location
    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(400, "文件过大（最大 10 MB）")

    tmp_dir = Path(settings.uploads_dir) / "creation_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{uuid.uuid4().hex}{ext}"
    tmp_path.write_bytes(raw)

    # Parse the file
    try:
        content = parse_uploaded_file(str(tmp_path), filename)
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(400, str(e))

    # Inject as user message (with file reference marker)
    msg_content = f"[上传了文件: {filename}]\n\n{content}"

    conn = get_conn()
    last = conn.execute(
        "SELECT idx, round_index FROM chat_messages WHERE session_id = ? ORDER BY idx DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    next_idx = (last["idx"] + 1) if last else 0
    next_round = (last["round_index"] + 1) if last and last["round_index"] is not None else 0

    conn.execute(
        """INSERT INTO chat_messages (id, session_id, role, name, content, idx, round_index, created_at)
           VALUES (?, ?, 'user', 'user', ?, ?, ?, datetime('now'))""",
        (generate_id(), session_id, msg_content, next_idx, next_round),
    )
    conn.execute("UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

    # Clean up temp file
    tmp_path.unlink(missing_ok=True)

    return {
        "ok": True,
        "filename": filename,
        "content_preview": content[:300],
        "char_count": len(content),
    }


# ============================================================
# Publish
# ============================================================


@router.post("/publish/{session_id}")
def publish_card(session_id: str):
    """Publish the card associated with this creation session."""
    conn = get_conn()
    sess = conn.execute(
        "SELECT * FROM chat_sessions WHERE id = ? AND mode = 'creation'", (session_id,)
    ).fetchone()
    conn.close()

    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    card_id = sess["card_id"]
    card = get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Associated card not found")

    from datetime import datetime
    update_card(card_id, status="published", published_at=datetime.now().isoformat())
    return get_card(card_id)


# ============================================================
# Worldbooks
# ============================================================


@router.get("/card/{card_id}/worldbooks")
def get_card_worldbooks(card_id: str):
    """Get linked worldbooks for a card."""
    return get_linked_worldbooks(card_id)


# ============================================================
# Helpers
# ============================================================


def _row_to_session(row) -> IChatSession:
    return IChatSession(
        id=row["id"],
        card_id=row["card_id"],
        mode=EChatMode(row["mode"]),
        name=row["name"] or "",
        greeting_index=row["greeting_index"],
        model=row["model"] or "",
        worldbook_ids=json.loads(row["worldbook_ids"] or "[]"),
        preset_name=row["preset_name"] or "",
        background_image=row["background_image"],
        parent_session_id=row["parent_session_id"],
        branch_number=row["branch_number"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
