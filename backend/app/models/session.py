from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class EChatMode(str, Enum):
    CREATION = "creation"
    PLAY = "play"
    CHAT = "chat"


class IChatSession(BaseModel):
    id: str
    card_id: str
    mode: EChatMode = EChatMode.PLAY
    name: str = ""
    greeting_index: int = 0

    model: str = ""
    worldbook_ids: list[str] = Field(default_factory=list)
    preset_name: str = ""

    background_image: Optional[str] = None

    parent_session_id: Optional[str] = None
    branch_number: Optional[int] = None

    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
