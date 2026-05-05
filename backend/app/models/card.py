from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ECardStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ECoverSource(str, Enum):
    UPLOAD = "upload"
    AI_GENERATED = "ai_generated"


class ERole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class EAspectRatio(str, Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    SQUARE = "square"


class EImageService(str, Enum):
    DALLE3 = "dalle3"
    SD_LOCAL = "sd_local"
    FLUX = "flux"
    QWEN_IMAGE = "qwen_image"


# ---------- INPC ----------

class INPC(BaseModel):
    name: str
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)
    start_active: bool = False
    description: str = ""


# ---------- IDepthPrompt ----------

class IDepthPrompt(BaseModel):
    prompt: str
    depth: int
    role: ERole


# ---------- ICoverInfo ----------

class ICoverInfo(BaseModel):
    image_path: str
    source: ECoverSource = ECoverSource.UPLOAD
    generation_prompt: str = ""


# ---------- IAvatarInfo ----------

class IAvatarInfo(BaseModel):
    image_path: str
    source: ECoverSource = ECoverSource.UPLOAD
    generation_prompt: str = ""


# ---------- IBackgroundInfo ----------

class IBackgroundInfo(BaseModel):
    image_path: str = ""
    source: ECoverSource = ECoverSource.UPLOAD


# ---------- IPresetConfig ----------

class IPresetConfig(BaseModel):
    writing_style: str = ""
    chain_of_thought: bool = False
    word_count_min: int = 700
    word_count_max: int = 1500
    model: str = ""
    temperature: float = 1.0
    top_p: float = 0.99
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    max_tokens: int = 30000


# ---------- IImageConfig ----------

class IImageConfig(BaseModel):
    style_tags: str = ""
    character_appearance: str = ""
    reference_images: list[str] = Field(default_factory=list)
    aspect_ratio: EAspectRatio = EAspectRatio.PORTRAIT
    generation_service: EImageService = EImageService.SD_LOCAL
    auto_generate: bool = False


# ---------- IAuthorsNoteConfig ----------

class EANPosition(str, Enum):
    BEFORE_SCENARIO = "before_scenario"
    AFTER_SCENARIO = "after_scenario"
    CHAT = "chat"


class IAuthorsNoteConfig(BaseModel):
    content: str = ""
    position: EANPosition = EANPosition.AFTER_SCENARIO
    depth: int = 4
    interval: int = 1
    role: ERole = ERole.SYSTEM


# ---------- ICharacterDefinition ----------

class ICharacterDefinition(BaseModel):
    name: str
    description: str = ""
    personality: str = ""
    scenario: str = ""
    speaking_style: str = ""
    background: str = ""
    first_mes: str = ""
    alternate_greetings: list[str] = Field(default_factory=list)
    mes_example: str = ""
    creator_notes: str = ""
    npcs: list[INPC] = Field(default_factory=list)


# ---------- ICharacterCard ----------

class ICharacterCard(BaseModel):
    id: str
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)

    spec: str = "chara_card_v3"
    spec_version: str = "1.0"
    extensions: dict[str, object] = Field(default_factory=dict)

    cover: ICoverInfo = Field(default_factory=lambda: ICoverInfo(image_path=""))
    avatar: IAvatarInfo = Field(default_factory=lambda: IAvatarInfo(image_path=""))
    background: IBackgroundInfo = Field(default_factory=IBackgroundInfo)

    character: ICharacterDefinition = Field(default_factory=ICharacterDefinition)

    system_prompt: Optional[str] = None
    post_history_instructions: Optional[str] = None
    depth_prompt: Optional[IDepthPrompt] = None

    worldbook_ids: list[str] = Field(default_factory=list)
    preset_name: Optional[str] = None

    preset_config: IPresetConfig = Field(default_factory=IPresetConfig)
    image_config: IImageConfig = Field(default_factory=IImageConfig)

    authors_note: Optional[IAuthorsNoteConfig] = None
    quick_reply_set_ids: list[str] = Field(default_factory=list)
    regex_script_ids: list[str] = Field(default_factory=list)

    status: ECardStatus = ECardStatus.DRAFT
    version: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    published_at: Optional[str] = None
