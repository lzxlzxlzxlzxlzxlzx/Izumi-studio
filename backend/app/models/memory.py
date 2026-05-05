from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ---------- ILongTermMemory ----------

class ILongTermMemory(BaseModel):
    """A single long-term memory fact extracted from conversation."""
    id: str = ""
    session_id: str = ""
    category: str = ""  # 人物关系 | 世界观设定 | 重要事件 | 角色属性 | 其他
    content: str = ""
    created_at: str = ""


# ---------- IMemoryOutput ----------

class IMemoryOutput(BaseModel):
    """Output passed to the context assembler for injection into system prompt."""
    memories: list[ILongTermMemory] = Field(default_factory=list)
