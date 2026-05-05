from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ENameBehavior(str, Enum):
    NONE = "none"
    DEFAULT = "default"
    CONTENT = "content"
    COMPLETION = "completion"


class EInjectionPosition(int, Enum):
    RELATIVE = 0
    ABSOLUTE = 1


class EGenerationType(str, Enum):
    NORMAL = "normal"
    CONTINUE = "continue"
    IMPERSONATE = "impersonate"


class EContextPosition(str, Enum):
    IN_PROMPT = "in_prompt"
    IN_CHAT = "in_chat"


class EInstructNameBehavior(str, Enum):
    NONE = "none"
    FORCE = "force"
    ALWAYS = "always"


class ERole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


# ---------- IPresetPrompt ----------

class IPresetPrompt(BaseModel):
    identifier: str
    name: str = ""
    enabled: bool = True
    role: ERole = ERole.SYSTEM
    content: str = ""
    system_prompt: bool = False
    marker: bool = False
    injection_position: EInjectionPosition = EInjectionPosition.RELATIVE
    injection_depth: int = 4
    injection_order: int = 0
    forbid_overrides: bool = False
    injection_trigger: list[EGenerationType] = Field(default_factory=list)
    extension: Optional[str] = None


# ---------- IContextConfig ----------

class IContextConfig(BaseModel):
    story_string: str = ""
    chat_start: str = ""
    example_separator: str = "<START>"
    position: EContextPosition = EContextPosition.IN_PROMPT
    role: ERole = ERole.SYSTEM
    depth: int = 0
    use_stop_strings: bool = False
    names_as_stop_strings: bool = False


# ---------- IInstructConfig ----------

class IInstructConfig(BaseModel):
    enabled: bool = False
    preset: str = "default"

    input_sequence: str = ""
    input_suffix: str = ""
    output_sequence: str = ""
    output_suffix: str = ""
    system_sequence: str = ""
    system_suffix: str = ""
    last_system_sequence: str = ""
    first_output_sequence: str = ""
    last_output_sequence: str = ""
    first_input_sequence: str = ""
    last_input_sequence: str = ""
    stop_sequence: str = ""

    wrap: bool = True
    macro: bool = True
    system_same_as_user: bool = False
    skip_examples: bool = False
    names_behavior: EInstructNameBehavior = EInstructNameBehavior.NONE
    sequences_as_stop_strings: bool = False

    story_string_prefix: str = ""
    story_string_suffix: str = ""
    activation_regex: str = ""
    bind_to_context: bool = True
    user_alignment_message: str = ""


# ---------- IPreset ----------

class IPreset(BaseModel):
    name: str = "default"

    temperature: float = 0.8
    frequency_penalty: float = 0.3
    presence_penalty: float = 0.2
    top_p: float = 0.95
    top_k: int = 40
    max_context: int = 4096
    max_tokens: int = 2048

    names_behavior: ENameBehavior = ENameBehavior.DEFAULT

    wi_format: str = ""
    scenario_format: str = ""
    personality_format: str = ""

    prompts: list[IPresetPrompt] = Field(default_factory=list)
    context_config: Optional[IContextConfig] = None
    instruct_config: Optional[IInstructConfig] = None
