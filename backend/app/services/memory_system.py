"""
MemorySystem — Per-turn long-term memory extraction.

After each conversation turn, calls the LLM to extract key facts from the
exchange (user input + assistant output). Accumulated facts are injected
into the system prompt on every subsequent turn as a dedicated block.
"""

from __future__ import annotations
from typing import Optional
from datetime import datetime
import json
import uuid
import logging

from app.db.database import get_conn
from app.models.memory import ILongTermMemory, IMemoryOutput

logger = logging.getLogger(__name__)

# Categories used in extraction
CATEGORIES = ["人物关系", "世界观设定", "重要事件", "其他"]

EXTRACT_PROMPT = """你是一个长期记忆提取器。根据以下对话内容，提取需要长期记住的关键信息。

规则：
- 只提取确定的事实，不要推测
- 如果某条信息已经存在于「已有记忆」中，除非本次对话提供了明确的更新，否则不要重复提取
- 每条记忆应当简洁、完整、独立可读

输出格式（JSON 数组）：
[
  {{"category": "人物关系", "content": "陈瑾是锦绣王朝的王爷，小蝶是他的丫鬟"}},
  {{"category": "世界观设定", "content": "故事发生在锦绣王朝，一个中国古代背景的世界"}},
  {{"category": "重要事件", "content": "小蝶因打碎花瓶被陈瑾用红木镇尺打了屁股"}}
]

可用的 category：人物关系, 世界观设定, 重要事件, 其他

已有记忆：
{existing_memories}

本轮对话：
用户：{user_input}
助手：{assistant_output}

请输出 JSON 数组（如果没有需要提取的新信息，输出空数组 []）："""


def _row_to_memory(row) -> ILongTermMemory:
    return ILongTermMemory(
        id=row["id"],
        session_id=row["session_id"],
        category=row["category"],
        content=row["content"],
        created_at=row["created_at"],
    )


def get_memories(session_id: str) -> list[ILongTermMemory]:
    """Fetch all long-term memories for a session."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM long_term_memories WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [_row_to_memory(r) for r in rows]


def get_output(session_id: str) -> IMemoryOutput:
    """Build IMemoryOutput from stored memories for context injection."""
    return IMemoryOutput(memories=get_memories(session_id))


def format_memories_for_prompt(memories: list[ILongTermMemory]) -> str:
    """Format all accumulated memories into a structured system prompt block."""
    if not memories:
        return ""

    by_cat: dict[str, list[str]] = {}
    for m in memories:
        by_cat.setdefault(m.category, []).append(m.content)

    lines = ["## 长期记忆"]
    for cat in CATEGORIES:
        items = by_cat.get(cat)
        if items:
            lines.append(f"\n[{cat}]")
            for item in items:
                lines.append(f"- {item}")
    return "\n".join(lines)


def _save_memory(m: ILongTermMemory) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO long_term_memories (id, session_id, category, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (m.id, m.session_id, m.category, m.content, m.created_at),
    )
    conn.commit()
    conn.close()


def _content_exists(content: str, existing: list[ILongTermMemory]) -> bool:
    """Check if similar content already exists (by normalized substring)."""
    norm = content.strip().rstrip("。，.，")
    for m in existing:
        existing_norm = m.content.strip().rstrip("。，.，")
        if norm == existing_norm:
            return True
        # Also check if one is contained in the other (for updates)
        if len(norm) > 10 and (norm in existing_norm or existing_norm in norm):
            return True
    return False


async def extract_and_store(
    session_id: str,
    user_input: str,
    assistant_output: str,
    llm_func,
) -> list[ILongTermMemory]:
    """
    Extract long-term memories from a single conversation turn and store them.

    Args:
        session_id: The session to update.
        user_input: The user's message.
        assistant_output: The assistant's response.
        llm_func: async (messages: list[dict]) -> str — returns the LLM response text.

    Returns:
        List of newly stored memories.
    """
    if not user_input and not assistant_output:
        return []

    existing = get_memories(session_id)
    existing_text = "\n".join(f"[{m.category}] {m.content}" for m in existing) or "(无)"

    prompt = EXTRACT_PROMPT.format(
        existing_memories=existing_text,
        user_input=user_input,
        assistant_output=assistant_output,
    )

    try:
        raw = await llm_func([{"role": "user", "content": prompt}])
    except Exception as e:
        logger.warning(f"[session={session_id[:8]}] memory extraction failed: {e}")
        return []

    # Parse JSON from response
    try:
        # Find JSON array in response
        text = raw.strip()
        if "[" in text:
            text = text[text.index("["):]
        if "]" in text:
            text = text[:text.rindex("]") + 1]
        items = json.loads(text)
        if not isinstance(items, list):
            return []
    except (json.JSONDecodeError, ValueError):
        logger.warning(f"[session={session_id[:8]}] failed to parse memory extraction output")
        return []

    now = datetime.now().isoformat()
    stored: list[ILongTermMemory] = []

    for item in items:
        cat = item.get("category", "其他")
        content = item.get("content", "").strip()
        if not content or cat not in CATEGORIES:
            continue
        if _content_exists(content, existing):
            continue

        mem = ILongTermMemory(
            id=str(uuid.uuid4()),
            session_id=session_id,
            category=cat,
            content=content,
            created_at=now,
        )
        _save_memory(mem)
        stored.append(mem)
        existing.append(mem)  # avoid duplicate in same batch

    if stored:
        logger.info(
            f"[session={session_id[:8]}] memory | extracted {len(stored)} new facts "
            f"(total {len(existing)})"
        )

    return stored
