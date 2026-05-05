from __future__ import annotations
from typing import Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime


class IContentPart(BaseModel):
    type: str  # "text" | "image"
    text: Optional[str] = None
    image_url: Optional[str] = None


class IMediaAttachment(BaseModel):
    type: str  # "image" | "audio" | "video"
    url: str
    alt_text: Optional[str] = None


class IToolCallFunction(BaseModel):
    name: str
    arguments: str


class IToolCall(BaseModel):
    id: str
    type: str = "function"
    function: IToolCallFunction


class ISwipe(BaseModel):
    index: int
    content: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class IChatMessage(BaseModel):
    id: str
    session_id: str
    role: str  # "user" | "assistant" | "system"
    name: str = ""
    content: Union[str, list[IContentPart]] = ""

    media: list[IMediaAttachment] = Field(default_factory=list)

    index: int
    round_index: int
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    swipes: list[ISwipe] = Field(default_factory=list)
    swipe_index: int = 0

    has_checkpoint: bool = False
    locked: bool = False

    tool_calls: list[IToolCall] = Field(default_factory=list)
    tool_call_id: Optional[str] = None
