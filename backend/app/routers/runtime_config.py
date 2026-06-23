from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.runtime_config import get_public_status, save_config

router = APIRouter()


class LlmConfigUpdate(BaseModel):
    API_KEY: str = ""
    API_URL: str = ""
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_API_URL: str = ""


@router.get("")
def get_config():
    """Return LLM config status without exposing secret keys."""
    return get_public_status()


@router.put("")
def update_config(body: LlmConfigUpdate):
    """Save LLM API keys for this deployment (stored in data/local_config.json)."""
    return save_config(body.model_dump())
