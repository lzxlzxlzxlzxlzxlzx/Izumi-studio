from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class EInsertionStrategy(str, Enum):
    CHARACTER_FIRST = "character_first"
    GLOBAL_FIRST = "global_first"
    EVENLY = "evenly"


class EEntryCategory(str, Enum):
    WORLDVIEW = "worldview"
    CHARACTER = "character"
    LOCATION = "location"
    EVENT = "event"
    RULE = "rule"
    RELATION = "relation"


class ESelectiveLogic(str, Enum):
    AND_ANY = "AND_ANY"
    AND_ALL = "AND_ALL"
    NOT_ANY = "NOT_ANY"
    NOT_ALL = "NOT_ALL"


class EEntrySource(str, Enum):
    ORIGINAL = "original"
    IP_CANON = "ip_canon"
    IP_EXTENDED = "ip_extended"


class EEntryPosition(str, Enum):
    BEFORE_CHAR = "before_char"
    AFTER_CHAR = "after_char"
    AT_DEPTH = "at_depth"
    EXAMPLES = "examples"
    AN_TOP = "an_top"
    AN_BOTTOM = "an_bottom"
    EM_TOP = "em_top"
    EM_BOTTOM = "em_bottom"
    OUTLET = "outlet"


class ERole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


# ---------- IWorldEntry ----------

class IWorldEntry(BaseModel):
    id: str
    category: EEntryCategory = EEntryCategory.WORLDVIEW
    title: str = ""
    comment: str = ""

    keys: list[str] = Field(default_factory=list)
    keys_secondary: list[str] = Field(default_factory=list)
    selective_logic: ESelectiveLogic = ESelectiveLogic.AND_ANY

    content: str = ""
    source: EEntrySource = EEntrySource.ORIGINAL

    enabled: bool = True
    constant: bool = False

    priority: int = 0
    insertion_order: int = 0

    position: EEntryPosition = EEntryPosition.BEFORE_CHAR
    depth: int = 4
    role: ERole = ERole.SYSTEM

    scan_depth: Optional[int] = None
    case_sensitive: Optional[bool] = None
    match_whole_words: Optional[bool] = None

    probability: int = 100

    sticky: int = 0
    cooldown: int = 0
    delay: int = 0

    group: str = ""
    group_weight: int = 0

    prevent_recursion: bool = False
    exclude_recursion: bool = False
    delay_until_recursion: bool = False

    match_persona_description: bool = False
    match_character_description: bool = False
    match_character_personality: bool = False
    match_character_scenario: bool = False

    vectorized: bool = False

    created_at: str = ""
    updated_at: str = ""


# ---------- IWorldBook ----------

class IWorldBook(BaseModel):
    id: str
    name: str
    description: str = ""
    ip_name: str = ""

    ui_components: Optional[object] = None

    scan_depth: int = 100
    token_budget: int = 500
    token_budget_ratio: float = 0.0
    recursive_scanning: bool = False
    max_recursion_steps: int = 5
    case_sensitive: bool = False
    match_whole_words: bool = False
    insertion_strategy: EInsertionStrategy = EInsertionStrategy.EVENLY
    min_activations: int = 0
    overflow_alert: bool = True

    entries: list[IWorldEntry] = Field(default_factory=list)

    created_at: str = ""
    updated_at: str = ""


# ---------- IWorldBookRuntimeState ----------

class IWorldBookRuntimeState(BaseModel):
    sticky_map: dict[str, int] = Field(default_factory=dict)
    cooldown_map: dict[str, int] = Field(default_factory=dict)
    round_count: int = 0


# ---------- IAtDepthEntry ----------

class IAtDepthEntry(BaseModel):
    entry: IWorldEntry
    depth: int


# ---------- IWorldBookActivationResult ----------

class IWorldBookActivationResult(BaseModel):
    before_char: list[IWorldEntry] = Field(default_factory=list)
    after_char: list[IWorldEntry] = Field(default_factory=list)
    at_depth: list[IAtDepthEntry] = Field(default_factory=list)
    examples: list[IWorldEntry] = Field(default_factory=list)
    an_top: list[IWorldEntry] = Field(default_factory=list)
    an_bottom: list[IWorldEntry] = Field(default_factory=list)
    em_top: list[IWorldEntry] = Field(default_factory=list)
    em_bottom: list[IWorldEntry] = Field(default_factory=list)
    outlet: list[IWorldEntry] = Field(default_factory=list)
    updated_state: IWorldBookRuntimeState = Field(default_factory=IWorldBookRuntimeState)
    trimmed_count: int = 0
