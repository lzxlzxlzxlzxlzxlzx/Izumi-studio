"""
ContextAssembler — Assembles the final IRawChatMessage[] for LLM consumption.

This is the central pipeline stage that combines:
- Preset prompts injected at SillyTavern-style positions (by identifier)
- Character definition (name, description, personality, scenario)
- Conversation history (IChatMessage[])
- Activated world book entries (optional — injected at position)
- Memory summaries (optional — injected in system prompt area)
- Post-history instructions (jailbreak — injected as user message, not system)
- Instruct sequences (when instruct_config.enabled)
- Token budget management (trim oldest non-locked content first)

Architecture (SillyTavern-compatible):
1. Build system messages from preset prompts by identifier order
2. Insert world book entries at their positions
3. Insert few-shot examples (mes_example)
4. Append conversation history
5. Inject jailbreak as user message (not system)
6. Apply instruct sequences (if instruct mode is on)
7. Apply token budget (trim from oldest messages)
8. Return final messages array
"""

from __future__ import annotations
from typing import Optional
import re

from app.models.card import ICharacterCard, ICharacterDefinition
from app.models.session import IChatSession
from app.models.message import IChatMessage
from app.models.preset import IPreset, EInstructNameBehavior
from app.models.config_models import IUserPersona, IAuthorsNoteConfig
from app.models.memory import IMemoryOutput
from app.services.memory_system import format_memories_for_prompt
from app.models.worldbook import IWorldBookActivationResult, EEntryPosition
from app.services.preset_renderer import (
    render_preset_supplement,
    get_writing_style,
    get_writer_identity,
    get_ordered_prompts,
    get_prompt_by_identifier,
    render_prompt_content,
)

MAX_CONTEXT = 12000


# ---------------------------------------------------------------
# System message builder — SillyTavern-style prompt splitting
# ---------------------------------------------------------------

def _build_system_messages(
    card: ICharacterCard,
    preset: Optional[IPreset] = None,
    persona: Optional[IUserPersona] = None,
) -> list[dict]:
    """
    Build system-level messages using SillyTavern prompt ordering.

    Each enabled preset prompt with content becomes its own message
    at the position determined by its identifier.

    Order: worldInfoBefore → main → charDescription → charPersonality
    → scenario → worldInfoAfter → personaDescription → other system prompts

    When no preset is available, falls back to the old blended system prompt.
    """
    c = card.character
    char_name = c.name or "{{char}}"

    # Card system_prompt override: skip all preset assembly
    if card.system_prompt:
        msg = card.system_prompt
        if preset:
            ws = get_writing_style(preset)
            if ws:
                msg += f"\n\n## 写作指导\n{ws}"
        return [{"role": "system", "content": msg}]

    # No preset: fall back to old blended behavior
    if not preset or not preset.prompts:
        return _fallback_system_message(card, persona)

    # Get ordered prompts
    ordered = get_ordered_prompts(preset)
    prompts_by_id: dict[str, dict] = {pid: msg for pid, msg in ordered}

    messages: list[dict] = []

    # 1. worldInfoBefore
    wib = prompts_by_id.get("worldInfoBefore")
    if wib:
        content = render_prompt_content(wib, char_name)
        if content:
            messages.append({"role": wib.role.value if hasattr(wib.role, 'value') else wib.role, "content": content})

    # 2. main (writer identity)
    main_prompt = prompts_by_id.get("main")
    main_content = None
    if main_prompt:
        main_content = _render_main_identity(main_prompt, char_name)
    if not main_content:
        main_content = get_writer_identity(preset, char_name)
    if not main_content:
        main_content = _extract_writer_identity_fallback(preset, char_name)
    if main_content:
        messages.append({"role": "system", "content": main_content})
    else:
        messages.append({"role": "system", "content": f"你是一位故事作家，正在为读者创作一个关于「{char_name}」的故事。请以第三人称叙事的方式，写出精彩的故事情节。"})

    # 3. charDescription
    desc_content = c.description
    if desc_content:
        messages.append({"role": "system", "content": f"## 故事角色：{char_name}\n{desc_content}"})

    # 4. charPersonality
    pers_content = c.personality
    if pers_content:
        messages.append({"role": "system", "content": f"## 角色性格\n{pers_content}"})

    # 5. scenario + background + speaking_style + npcs
    scenario_parts = []
    if c.scenario:
        scenario_parts.append(f"## 故事场景\n{c.scenario.replace('{{user}}', '用户')}")
    if c.background:
        scenario_parts.append(f"## 故事背景\n{c.background}")
    if c.speaking_style:
        scenario_parts.append(f"## 角色说话风格\n{c.speaking_style}")
    if c.npcs:
        npc_lines = ["## 故事中的其他角色"]
        for npc in c.npcs:
            npc_lines.append(f"- {npc.name}: {npc.description}" if npc.description else f"- {npc.name}")
        scenario_parts.append("\n".join(npc_lines))
    if scenario_parts:
        messages.append({"role": "system", "content": "\n\n".join(scenario_parts)})

    # 6. worldInfoAfter
    wia = prompts_by_id.get("worldInfoAfter")
    if wia:
        content = render_prompt_content(wia, char_name)
        if content:
            messages.append({"role": wia.role.value if hasattr(wia.role, 'value') else wia.role, "content": content})

    # 7. personaDescription
    pd_prompt = prompts_by_id.get("personaDescription")
    if pd_prompt:
        content = render_prompt_content(pd_prompt, char_name)
        if content:
            messages.append({"role": "system", "content": content})
    elif persona and persona.description:
        messages.append({"role": "system", "content": f"## 故事中用户化身的设定\n{persona.description}"})

    # 8. Other system_prompt=True prompts (nsfw, enhanceDefinitions, ...)
    handled_ids = {"worldInfoBefore", "main", "charDescription", "charPersonality",
                   "scenario", "worldInfoAfter", "personaDescription",
                   "dialogueExamples", "chatHistory", "jailbreak"}
    for pid, p in ordered:
        if pid in handled_ids:
            continue
        if p.system_prompt:
            content = render_prompt_content(p, char_name)
            if content:
                messages.append({"role": "system", "content": content})

    # 9. Writing style + word count + CoT (appended to last system message)
    wc = card.preset_config
    tail_lines = []

    ws_text = card.preset_config.writing_style or get_writing_style(preset) or ""
    if ws_text:
        if wc.word_count_min and wc.word_count_max:
            ws_text = re.sub(r'正文字数[：:].+', '', ws_text).strip()
        tail_lines.append(f"## 写作风格\n{ws_text}")

    if wc.word_count_min and wc.word_count_max:
        tail_lines.append(
            f"【重要】每次回复必须不少于{wc.word_count_min}字、不超过{wc.word_count_max}字。"
            f"请务必达到最低字数要求，通过环境描写、动作细节或内心独白来丰富内容。"
        )

    if wc.chain_of_thought:
        tail_lines.append("请在回复前先进行简短的思考（用<thinking>标签包裹，不计入字数），然后给出最终回复。")

    # Preset narrative supplement
    if preset:
        supplement = render_preset_supplement(preset, card)
        if supplement:
            if ws_text and _text_overlap_ratio(supplement, ws_text) < 0.7:
                tail_lines.append(f"## 额外叙事指导\n{supplement}")
            elif not ws_text:
                tail_lines.append(f"## 叙事指导\n{supplement}")

    if tail_lines:
        messages.append({"role": "system", "content": "\n\n".join(tail_lines)})

    return messages


def _render_main_identity(prompt: IPresetPrompt, char_name: str) -> str:
    """Render the 'main' prompt as a clean writer identity."""
    if not prompt or not prompt.content:
        return ""

    raw = prompt.content
    id_lines: list[str] = []
    in_task = False
    skip_block = False

    for line in raw.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue

        if "<main_task>" in stripped.lower() or "[main task]" in stripped.lower():
            in_task = True
            continue
        if "</main_task>" in stripped.lower() or "[/main task]" in stripped.lower():
            in_task = False
            continue
        if "<identity_isolation>" in stripped.lower() or "需要注意元叙事" in stripped or "认知隔离" in stripped:
            skip_block = True
            continue
        if "</identity_isolation>" in stripped.lower():
            skip_block = False
            continue
        if skip_block:
            continue
        if re.match(r'^\{\{(setvar|getvar)::', stripped):
            continue
        if stripped in ('[RESET ROLE AND TASK,RECEIVE NEW TASK]', '[Main Task]', '[/Main Task]'):
            continue

        if in_task:
            id_lines.append(stripped)

    if not id_lines:
        return ""

    result = "\n".join(id_lines)
    result = re.sub(r'\{\{(setvar|getvar)::[^}]*\}\}', '', result)
    result = re.sub(r'\{\{//[^}]*\}\}', '', result)
    result = result.replace("{{user}}", "Master")
    result = result.replace("<user>", char_name)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


def _fallback_system_message(
    card: ICharacterCard,
    persona: Optional[IUserPersona] = None,
) -> list[dict]:
    """Fallback: old blended system prompt for presets without structured prompts."""
    c = card.character
    char_name = c.name or "{{char}}"

    lines: list[str] = []
    lines.append(f"你是一位故事作家，正在为读者创作一个关于「{char_name}」的故事。请以第三人称叙事的方式，写出精彩的故事情节。")

    story_parts: list[str] = []
    if c.description:
        story_parts.append(f"## 故事角色：{char_name}\n{c.description}")
    if c.personality:
        story_parts.append(f"## 角色性格\n{c.personality}")
    if c.scenario:
        story_parts.append(f"## 故事场景\n{c.scenario.replace('{{user}}', '用户')}")
    if c.background:
        story_parts.append(f"## 故事背景\n{c.background}")
    if c.speaking_style:
        story_parts.append(f"## 角色说话风格\n{c.speaking_style}")
    if c.npcs:
        npc_lines = ["## 故事中的其他角色"]
        for npc in c.npcs:
            npc_lines.append(f"- {npc.name}: {npc.description}" if npc.description else f"- {npc.name}")
        story_parts.append("\n".join(npc_lines))
    if story_parts:
        lines.append("\n\n".join(story_parts))

    if persona and persona.description:
        lines.append(f"## 故事中用户化身的设定\n{persona.description}")

    wc = card.preset_config
    if wc.word_count_min and wc.word_count_max:
        lines.append(
            f"【重要】每次回复必须不少于{wc.word_count_min}字、不超过{wc.word_count_max}字。"
        )
    if wc.chain_of_thought:
        lines.append("请在回复前先进行简短的思考（用<thinking>标签包裹，不计入字数），然后给出最终回复。")

    return [{"role": "system", "content": "\n\n".join(lines)}]


# ---------------------------------------------------------------
# Instruct sequence formatting (for text-completion mode)
# ---------------------------------------------------------------

def _apply_instruct_sequences(
    messages: list[dict],
    instruct_config,
    char_name: str,
) -> list[dict]:
    """
    Wrap messages with instruct sequences when instruct mode is enabled.

    SillyTavern-compatible: applies input_sequence/output_sequence/system_sequence
    to each message based on its role.
    """
    if not instruct_config or not instruct_config.enabled:
        return messages

    ic = instruct_config
    name_behavior = ic.names_behavior

    def _should_include_name(role: str, is_first: bool, is_last: bool) -> bool:
        if name_behavior == EInstructNameBehavior.ALWAYS:
            return True
        if name_behavior == EInstructNameBehavior.FORCE:
            return role != "system"
        return False

    def _wrap(role: str, content: str, idx: int, total: int) -> str:
        is_first = (idx == 0)
        is_last = (idx == total - 1)

        if role == "user":
            seq = ic.first_input_sequence if is_first and ic.first_input_sequence else ic.last_input_sequence if is_last and ic.last_input_sequence else ic.input_sequence
            suffix = ic.input_suffix
        elif role == "assistant":
            seq = ic.first_output_sequence if is_first and ic.first_output_sequence else ic.last_output_sequence if is_last and ic.last_output_sequence else ic.output_sequence
            suffix = ic.output_suffix
        else:
            if ic.system_same_as_user:
                seq = ic.input_sequence
                suffix = ic.input_suffix
            else:
                seq = ic.system_sequence
                suffix = ic.system_suffix
            # Apply last_system_sequence for last system message
            if is_last and ic.last_system_sequence:
                seq = ic.last_system_sequence

        include_name = _should_include_name(role, is_first, is_last)

        result = seq
        if include_name:
            name = char_name if role == "assistant" else "用户"
            result += f"{name}: "
        result += content
        result += suffix
        return result

    wrapped = []
    total = len(messages)
    for i, msg in enumerate(messages):
        wrapped.append({
            "role": msg["role"],
            "content": _wrap(msg["role"], msg["content"], i, total),
        })

    return wrapped


# ---------------------------------------------------------------
# Jailbreak handling
# ---------------------------------------------------------------

def _get_jailbreak_content(
    card: ICharacterCard,
    preset: Optional[IPreset] = None,
) -> Optional[str]:
    """
    Get jailbreak/post-history-instructions content.

    Priority:
    1. card.post_history_instructions (character card override)
    2. preset 'jailbreak' prompt content
    """
    if card.post_history_instructions:
        return card.post_history_instructions

    if preset:
        jb = get_prompt_by_identifier(preset, "jailbreak")
        if jb and jb.content:
            return render_prompt_content(jb, card.character.name)

    return None


# ---------------------------------------------------------------
# History formatting
# ---------------------------------------------------------------

def _format_history(
    messages: list[IChatMessage],
    character_name: str,
    post_instructions: Optional[str] = None,
    max_rounds: int = 0,
) -> list[dict]:
    """
    Convert IChatMessage[] to OpenAI-compatible messages array.
    Ensures alternating user/assistant roles.
    """
    result: list[dict] = []

    # If max_rounds > 0, keep only the last N rounds (pairs)
    if max_rounds > 0:
        rounds_seen: set[int] = set()
        filtered: list[IChatMessage] = []
        for msg in reversed(messages):
            if msg.round_index not in rounds_seen:
                rounds_seen.add(msg.round_index)
            if len(rounds_seen) > max_rounds:
                break
            filtered.insert(0, msg)
        messages = filtered

    for msg in messages:
        name = msg.name or (character_name if msg.role == "assistant" else "user")
        content = msg.content if isinstance(msg.content, str) else str(msg.content)

        entry: dict = {
            "role": msg.role,
            "content": content,
            "name": name,
        }
        # Preserve tool_calls on assistant messages so the LLM sees them in history
        if msg.role == "assistant" and msg.tool_calls:
            entry["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
        # Preserve tool_call_id on tool result messages
        if msg.role == "tool" and msg.tool_call_id:
            entry["tool_call_id"] = msg.tool_call_id
        result.append(entry)

    if post_instructions:
        result.append({
            "role": "system",
            "content": post_instructions,
        })

    return result


def _inject_worldbook(
    messages: list[dict],
    wb: IWorldBookActivationResult,
    preset: Optional[IPreset] = None,
) -> list[dict]:
    """
    Inject activated world book entries at their designated positions.

    before_char → before the first system message
    after_char  → after the last scenario-related message, before examples
    at_depth    → at specified depth from the end
    """
    if not wb:
        return messages

    def make_wb_block(entries) -> str:
        if not entries:
            return ""
        texts = []
        for e in entries:
            texts.append(f"[{e.title or '世界设定'}]\n{e.content}")
        return "\n\n".join(texts)

    # before_char: insert at the very beginning
    if wb.before_char:
        block = make_wb_block(wb.before_char)
        if block:
            messages.insert(0, {"role": "system", "content": block})

    # after_char: insert after scenario, before examples
    # Find the index right after the last system message that contains story/scene content,
    # or just after the last system message with scenario-related content
    if wb.after_char:
        block = make_wb_block(wb.after_char)
        if block:
            # Find the last system message (before examples/chat) and append
            insert_idx = 0
            for i in range(len(messages) - 1, -1, -1):
                if messages[i]["role"] == "system":
                    insert_idx = i + 1
                    break
            messages.insert(insert_idx, {"role": "system", "content": block})

    # at_depth — simplified: inject at depth from end
    for field_name in ["examples", "an_top", "an_bottom", "em_top", "em_bottom"]:
        entries = getattr(wb, field_name, [])
        if entries:
            block = make_wb_block(entries)
            if block:
                messages.insert(0, {"role": "system", "content": block})

    return messages


def assemble(
    card: ICharacterCard,
    chat_history: list[IChatMessage],
    current_input: str,
    preset: Optional[IPreset] = None,
    persona: Optional[IUserPersona] = None,
    authors_note: Optional[IAuthorsNoteConfig] = None,
    memory: Optional[IMemoryOutput] = None,
    worldbook: Optional[IWorldBookActivationResult] = None,
    story_characters: Optional[list[dict]] = None,
    token_budget: int = MAX_CONTEXT,
) -> list[dict]:
    """
    Main assembly function. Returns OpenAI-compatible messages array.

    SillyTavern-compatible flow:
    1. Build system messages from preset prompts (by identifier)
    2. Append story characters to last system msg
    3. Inject world book entries at their positions
    4. Inject long-term memory as dedicated system message
    5. Add few-shot examples (mes_example)
    6. Append chat history
    7. Add jailbreak/post-history as user message (not system)
    8. Apply instruct sequences (if instruct mode on)
    9. Add current input
    10. Trim to budget

    Returns:
        list of {"role": str, "content": str, "name"?: str} dicts
    """
    char_name = card.character.name or "{{char}}"

    # 1. Build system messages from preset prompts (SillyTavern order)
    messages = _build_system_messages(card, preset, persona)

    # 2. Story Characters (append to last system message)
    if story_characters:
        char_lines = ["## 当前已登记角色"]
        for sc in story_characters:
            name = sc.get("name", "?")
            attrs = sc.get("attributes", {}) or {}
            attr_str = "、".join(f"{k}={v}" for k, v in attrs.items() if k != "name")[:120]
            status = "存活" if sc.get("is_alive", True) else "死亡"
            active = "出场" if sc.get("is_active", True) else "离场"
            char_lines.append(f"- {name} [{status}/{active}] {attr_str}")
        char_block = "\n".join(char_lines)
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "system":
                messages[i]["content"] += "\n\n" + char_block
                break

    # 3. World book entries
    if worldbook:
        messages = _inject_worldbook(messages, worldbook, preset)

    # 4. Long-term memory (dedicated system message)
    if memory and memory.memories:
        mem_text = format_memories_for_prompt(memory.memories)
        if mem_text:
            messages.append({"role": "system", "content": mem_text})

    # 5. Few-shot examples (from mes_example)
    if card.character.mes_example:
        examples = _parse_mes_example(card.character.mes_example, char_name)
        messages.extend(examples)

    # 5. Chat history
    # When writer preset is active, suppress roleplay-style post-history instructions
    post_instr = card.post_history_instructions
    if post_instr and preset:
        writer_id = get_writer_identity(preset, char_name)
        if writer_id and _is_roleplay_instruction(post_instr):
            post_instr = None

    history_msgs = _format_history(
        chat_history,
        char_name,
        post_instructions=None,  # No post-instructions in history — jailbreak handled separately
    )
    messages.extend(history_msgs)

    # 6. Jailbreak / post-history instructions as USER message
    jb_content = _get_jailbreak_content(card, preset)
    if jb_content:
        # If card has post_history_instructions AND it's roleplay-style,
        # skip it (already handled above by suppressing post_instr in _format_history)
        # Otherwise, add as user message
        if not card.post_history_instructions or not (
            preset and get_writer_identity(preset, char_name) and _is_roleplay_instruction(card.post_history_instructions)
        ):
            messages.append({"role": "user", "content": jb_content})

    # 7. Instruct sequences (if instruct_config.enabled)
    if preset and preset.instruct_config:
        messages = _apply_instruct_sequences(messages, preset.instruct_config, char_name)

    # 8. Authors Note
    if authors_note and authors_note.content:
        depth = authors_note.depth
        insert_idx = max(0, len(messages) - depth)
        messages.insert(insert_idx, {
            "role": "system",
            "content": f"[Author's Note]\n{authors_note.content}",
        })

    # 9. Current input
    messages.append({"role": "user", "content": current_input})

    # 10. Token budget management — trim oldest messages if over budget
    messages = _trim_to_budget(messages, token_budget)

    return messages


def _is_roleplay_instruction(text: str) -> bool:
    """Check if post-history instructions tell the AI to roleplay as a character,
    which contradicts the writer+story architecture."""
    rp_patterns = [
        r'以.+的身份',
        r'扮演.+角色',
        r'始终保持角色',
        r'你必须?是.+',
        r'回复时.+扮演',
        r'你的身份是',
    ]
    return any(re.search(p, text) for p in rp_patterns)


def _text_overlap_ratio(a: str, b: str) -> float:
    """Estimate how much of text A overlaps with text B (by line)."""
    if not a or not b:
        return 0.0
    a_lines = set(a.strip().split("\n"))
    b_lines = set(b.strip().split("\n"))
    if not a_lines:
        return 0.0
    return len(a_lines & b_lines) / len(a_lines)


def _parse_mes_example(mes_example: str, char_name: str) -> list[dict]:
    """
    Parse <START>-separated example dialogues into message list.
    Handles multi-line responses: lines after a speaker prefix belong to the same turn.

    Expected format:
    <START>
    {{user}}: user message (may span multiple lines)
    {{char}}: character response (may span multiple lines with *actions* and 「dialogue」)
    <START>
    ...
    """
    result: list[dict] = []
    blocks = mes_example.split("<START>")

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.split("\n")
        current_role: str | None = None
        current_lines: list[str] = []

        for line in lines:
            raw = line.strip()
            if not raw:
                continue

            # Replace macros
            line_replaced = raw.replace("{{char}}", char_name).replace("{{user}}", "用户")

            # Check if this line starts a new turn
            is_assistant = line_replaced.startswith(f"{char_name}:") or line_replaced.startswith(f"{char_name}：")
            is_user = line_replaced.startswith("{{user}}:") or line_replaced.startswith("用户:") or line_replaced.startswith("用户：")

            if is_assistant or is_user:
                # Flush previous turn
                if current_role and current_lines:
                    content = "\n".join(current_lines).strip()
                    if content:
                        result.append({
                            "role": current_role,
                            "content": content,
                            **({"name": char_name} if current_role == "assistant" else {}),
                        })
                    current_lines = []

                current_role = "assistant" if is_assistant else "user"
                # Extract content after the first colon
                content = line_replaced.split(":", 1)[-1].split("：", 1)[-1].strip()
                if content:
                    current_lines.append(content)
            else:
                # Continuation line for the current turn
                if current_role:
                    current_lines.append(raw)

        # Flush final turn in this block
        if current_role and current_lines:
            content = "\n".join(current_lines).strip()
            if content:
                result.append({
                    "role": current_role,
                    "content": content,
                    **({"name": char_name} if current_role == "assistant" else {}),
                })

    return result


def _trim_to_budget(messages: list[dict], budget: int) -> list[dict]:
    """
    Trim oldest non-system messages until estimated tokens fit within budget.
    Always keeps the most recent user message and at least 1 system message.

    Ensures tool messages are never orphaned: if an assistant message with
    tool_calls is removed, any subsequent tool messages referencing those
    call IDs are also removed.
    """
    from app.services.llm_router import estimate_message_tokens

    total = estimate_message_tokens(messages)
    if total <= budget:
        return messages

    # Reserve budget for response (~20%)
    target = int(budget * 0.8)

    # Remove from oldest non-system messages first
    kept: list[dict] = []
    removed = 0
    removed_tool_call_ids: set[str] = set()
    for i, msg in enumerate(messages):
        if msg["role"] == "system" and i == 0:
            # Always keep first system message
            kept.append(msg)
            continue
        # If this is a tool message and its tool_call was already removed, skip it
        if msg["role"] == "tool" and msg.get("tool_call_id") in removed_tool_call_ids:
            removed += 1
            continue
        current_total = estimate_message_tokens(kept + [msg] + messages[i + 1 :])
        if current_total > target and msg["role"] != "system":
            # If removing an assistant message with tool_calls, track its IDs
            # so subsequent tool messages referencing them are also removed
            if msg["role"] == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    call_id = tc.get("id") or tc.get("id", "")
                    if call_id:
                        removed_tool_call_ids.add(call_id)
            removed += 1
            continue
        kept.append(msg)

    if removed > 0:
        # Insert a note
        note = f"[注：为控制上下文长度，已省略较早的 {removed} 条消息]"
        for i, m in enumerate(kept):
            if m["role"] != "system":
                m["content"] = note + "\n\n" + m["content"]
                break

    return kept
