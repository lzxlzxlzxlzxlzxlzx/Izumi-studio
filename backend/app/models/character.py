from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ---------- ICharacterImage ----------

class ICharacterImage(BaseModel):
    id: str
    url: str
    label: Optional[str] = None
    filename: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ---------- IStoryCharacter ----------

class IStoryCharacter(BaseModel):
    id: str
    session_id: str
    name: str
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)
    is_active: bool = True
    is_alive: bool = True
    first_seen_round: int = 0
    last_seen_round: int = 0
    source: str = "card_definition"  # "card_definition" | "model_creation"
    images: list[ICharacterImage] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ---------- ICharacterAttributeChange ----------

class ICharacterAttributeChange(BaseModel):
    attribute: str
    old_value: Optional[str | int | float | bool] = None
    new_value: Optional[str | int | float | bool] = None


# ---------- ICharacterChangeLog ----------

class ICharacterChangeLog(BaseModel):
    id: str
    session_id: str
    message_id: str
    message_index: int
    character_id: str
    character_name: str
    action: str  # "create" | "update" | "delete"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    changes: list[ICharacterAttributeChange] = Field(default_factory=list)


# ---------- ICharacterRegistry ----------

class ICharacterRegistry(BaseModel):
    session_id: str
    characters: list[IStoryCharacter] = Field(default_factory=list)
    as_of_message_index: int = 0


# ---------- Skill params ----------

class ECharacterSkillOp(str, Enum):
    LIST_CHARACTERS = "list_characters"
    GET_CHARACTER = "get_character"
    CREATE_CHARACTER = "create_character"
    UPDATE_CHARACTER = "update_character"
    DELETE_CHARACTER = "delete_character"
