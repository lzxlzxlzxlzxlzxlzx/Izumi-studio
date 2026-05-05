from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from app.models.card import ERole
from app.models.preset import EGenerationType


# ---------- IPromptItem / IPromptCollection ----------

class EInjectionPosition(int, Enum):
    RELATIVE = 0
    ABSOLUTE = 1


class IPromptItem(BaseModel):
    identifier: str
    name: str = ""
    role: ERole = ERole.SYSTEM
    content: str = ""
    system_prompt: bool = False
    marker: bool = False
    injection_position: EInjectionPosition = EInjectionPosition.RELATIVE
    injection_depth: int = 4
    injection_order: int = 0


class IPromptCollection(BaseModel):
    prompts: list[IPromptItem] = Field(default_factory=list)


# ---------- IContextAssemblyInput ----------

class IContextAssemblyInput(BaseModel):
    character: Optional[object] = None  # ICharacterCard
    worldbook: Optional[object] = None  # IWorldBookActivationResult
    memory: Optional[object] = None  # IMemoryOutput
    persona: Optional[object] = None  # IUserPersona
    authors_note: Optional[object] = None  # IAuthorsNoteConfig
    chat_history: list[object] = Field(default_factory=list)  # list[IChatMessage]
    prompt_collection: Optional[IPromptCollection] = None
    instruct_config: Optional[object] = None  # IInstructConfig
    context_config: Optional[object] = None  # IContextConfig
    token_budget: int = 4096
    current_input: str = ""
    system_prompt_override: Optional[str] = None
    jailbreak_override: Optional[str] = None
    generation_type: EGenerationType = EGenerationType.NORMAL


# ---------- IAssemblyOutput ----------

class IRawChatMessage(BaseModel):
    role: str
    content: str | list[object] = ""
    name: Optional[str] = None
    tool_calls: Optional[list[object]] = None
    tool_call_id: Optional[str] = None


class ITokenCounts(BaseModel):
    by_identifier: dict[str, dict[str, int]] = Field(default_factory=dict)
    total: int = 0
    budget: int = 0


class IAssemblyOutput(BaseModel):
    messages: list[IRawChatMessage] = Field(default_factory=list)
    token_counts: ITokenCounts = Field(default_factory=ITokenCounts)
    trimmed_components: list[str] = Field(default_factory=list)


# ---------- IExtensionPrompt ----------

class EExtensionPromptPosition(str, Enum):
    BEFORE_PROMPT = "before_prompt"
    IN_PROMPT = "in_prompt"
    IN_CHAT = "in_chat"


class IExtensionPrompt(BaseModel):
    text: str
    role: ERole = ERole.SYSTEM
    position: EExtensionPromptPosition = EExtensionPromptPosition.IN_PROMPT
    depth: int = 4


# ---------- IGenerateRequest ----------

class IGenerateRequest(BaseModel):
    session_id: str
    input: str
    images: Optional[list[object]] = None  # list[IContentPart]
    type: EGenerationType = EGenerationType.NORMAL
    quiet_prompt: Optional[str] = None
    extension_prompts: Optional[list[IExtensionPrompt]] = None


# ---------- IGenerateChunk (SSE) ----------

class IGenerateChunk(BaseModel):
    type: str  # "token" | "done" | "error" | "tool_call"
    token: Optional[str] = None
    full_response: Optional[str] = None
    error: Optional[str] = None
    tool_call: Optional[object] = None


# ---------- IPromptInspectorData ----------

class IPromptInspectorData(BaseModel):
    raw_input: str = ""
    activated_presets: list[dict[str, str]] = Field(default_factory=list)
    activated_world_entries: list[dict[str, object]] = Field(default_factory=list)
    authors_note: Optional[dict[str, object]] = None
    injected_memory: dict[str, list[str]] = Field(default_factory=dict)
    injected_persona: Optional[str] = None
    full_messages: list[IRawChatMessage] = Field(default_factory=list)
    token_stats: ITokenCounts = Field(default_factory=ITokenCounts)
    raw_response: Optional[str] = None
    tool_calls: list[dict[str, str]] = Field(default_factory=list)
