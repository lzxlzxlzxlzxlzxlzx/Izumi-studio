from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ERole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class EModelProvider(str, Enum):
    ANTHROPIC = "anthropic"
    DASHSCOPE = "dashscope"
    DEEPSEEK = "deepseek"
    MOONSHOT = "moonshot"
    AZURE_OPENAI = "azure_openai"


class EImageService(str, Enum):
    DALLE3 = "dalle3"
    SD_LOCAL = "sd_local"
    FLUX = "flux"
    QWEN_IMAGE = "qwen_image"


class EANPosition(str, Enum):
    BEFORE_SCENARIO = "before_scenario"
    AFTER_SCENARIO = "after_scenario"
    CHAT = "chat"


class ERegexPlacement(str, Enum):
    USER_INPUT = "user_input"
    MODEL_OUTPUT = "model_output"
    SLASH_COMMAND = "slash_command"


# ---------- IUserPersona ----------

class IUserPersona(BaseModel):
    id: str
    name: str
    avatar_path: Optional[str] = None
    description: str = ""
    injection_depth: int = 4
    injection_role: ERole = ERole.SYSTEM
    is_default: bool = False
    locked_chat_id: Optional[str] = None
    locked_card_id: Optional[str] = None


# ---------- IAuthorsNoteConfig ----------

class IAuthorsNoteConfig(BaseModel):
    content: str = ""
    position: EANPosition = EANPosition.AFTER_SCENARIO
    depth: int = 4
    interval: int = 1
    role: ERole = ERole.SYSTEM


# ---------- IQuickReplyButton ----------

class IQuickReplyButton(BaseModel):
    id: str
    label: str
    message: str
    show_label: bool = True
    is_auto: bool = False
    is_hotkey: bool = False
    hotkey: Optional[str] = None


# ---------- IQuickReplySet ----------

class IQuickReplySet(BaseModel):
    id: str
    name: str
    buttons: list[IQuickReplyButton] = Field(default_factory=list)


# ---------- IRegexScript ----------

class IRegexScript(BaseModel):
    id: str
    script_name: str
    enabled: bool = True
    find_regex: str
    replace_string: str = ""
    trim_strings: list[str] = Field(default_factory=list)
    placement: list[ERegexPlacement] = Field(default_factory=list)
    run_on_edit: bool = False
    markdown_only: bool = False
    min_depth: Optional[int] = None
    max_depth: Optional[int] = None


# ---------- IModelConfig ----------

class IModelConfig(BaseModel):
    name: str
    provider: EModelProvider
    base_url: str
    api_key: str = ""
    temperature: float = 0.8
    max_tokens: int = 2048
    top_p: float = 0.95
    frequency_penalty: float = 0.3
    presence_penalty: float = 0.2
    supports_vision: bool = False
    supports_tool_calling: bool = False


# ---------- IImageServiceConfig ----------

class IImageServiceConfig(BaseModel):
    service: EImageService = EImageService.SD_LOCAL
    enabled: bool = False
    api_key: str = ""
    base_url: str = ""


# ---------- UI schemas ----------

class IStatusField(BaseModel):
    key: str
    label: str
    type: str = "number"  # "progress" | "number" | "text" | "badge" | "heart"
    max: Optional[int] = None
    color: Optional[str] = None
    icon: Optional[str] = None


class IStatusBarConfig(BaseModel):
    enabled: bool = False
    position: str = "bottom"  # "top" | "bottom"
    fields: list[IStatusField] = Field(default_factory=list)


class IFloatingPanel(BaseModel):
    title: str
    fields: list[str] = Field(default_factory=list)


class IFloatingBallConfig(BaseModel):
    enabled: bool = False
    default_position: dict[str, str] = Field(default_factory=dict)
    panels: list[IFloatingPanel] = Field(default_factory=list)


class ISidePanelConfig(BaseModel):
    enabled: bool = False
    fields: list[str] = Field(default_factory=list)


class IStateFieldDef(BaseModel):
    type: str = "number"  # "number" | "string"
    default: int | float | str = 0
    min: Optional[int | float] = None
    max: Optional[int | float] = None


class IUIComponentSchema(BaseModel):
    status_bar: Optional[IStatusBarConfig] = None
    floating_ball: Optional[IFloatingBallConfig] = None
    side_panel: Optional[ISidePanelConfig] = None
    state_schema: dict[str, IStateFieldDef] = Field(default_factory=dict)


# ---------- IUIState ----------

class IUIState(BaseModel):
    session_id: str
    values: dict[str, int | float | str] = Field(default_factory=dict)
    updated_at: str = ""
