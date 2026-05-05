import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db.database import get_conn, generate_id
from app.models.card import ICharacterCard
import app.services.card_manager as card_manager

router = APIRouter()


class CardListResponse(BaseModel):
    cards: list[ICharacterCard]
    total: int


@router.get("", response_model=CardListResponse)
def list_cards(search: str = "", tags: str = ""):
    tag_list = [t for t in tags.split(",") if t] if tags else []
    cards = card_manager.list_cards(search=search, tags=tag_list)
    return CardListResponse(cards=cards, total=len(cards))


@router.get("/{card_id}", response_model=ICharacterCard)
def get_card(card_id: str):
    card = card_manager.get_card(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


class CreateCardRequest(BaseModel):
    name: str
    description: str = ""
    tags: list[str] = []


@router.post("", response_model=ICharacterCard, status_code=201)
def create_card(req: CreateCardRequest):
    card = card_manager.create_card(name=req.name, description=req.description, tags=req.tags)
    return card


class UpdateCardRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    character: dict | None = None
    preset_config: dict | None = None
    background: dict | None = None
    system_prompt: str | None = None
    post_history_instructions: str | None = None
    preset_name: str | None = None
    worldbook_ids: list[str] | None = None


@router.patch("/{card_id}", response_model=ICharacterCard)
def update_card(card_id: str, req: UpdateCardRequest):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    card = card_manager.update_card(card_id, **updates)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.delete("/{card_id}")
def delete_card(card_id: str):
    ok = card_manager.delete_card(card_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Card not found")
    return {"ok": True}
