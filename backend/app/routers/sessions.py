import json
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from app.db.database import get_conn, generate_id
from app.models.session import IChatSession, EChatMode
from app.models.character import IStoryCharacter, ICharacterImage
from app.services.card_manager import get_card
from app.services.character_template_manager import instantiate_auto_active
from app.config import settings

router = APIRouter()


@router.get("/card/{card_id}", response_model=list[IChatSession])
def list_sessions(card_id: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chat_sessions WHERE card_id = ? ORDER BY updated_at DESC",
        (card_id,),
    ).fetchall()
    sessions = [_row_to_session(r) for r in rows]
    conn.close()
    return sessions


class CreateSessionRequest(BaseModel):
    card_id: str
    mode: str = "play"
    name: str = ""
    greeting_index: int = 0


@router.post("", response_model=IChatSession, status_code=201)
def create_session(req: CreateSessionRequest):
    conn = get_conn()
    sid = generate_id()
    conn.execute(
        """INSERT INTO chat_sessions (id, card_id, mode, name, greeting_index, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
        (sid, req.card_id, req.mode, req.name, req.greeting_index),
    )
    conn.commit()

    # Instantiate NPCs from the card as story characters
    card = get_card(req.card_id)
    if card:
        characters = instantiate_auto_active(card, sid)
        for char in characters:
            conn.execute(
                """INSERT INTO story_characters
                   (id, session_id, name, attributes_json, is_active, is_alive,
                    first_seen_round, last_seen_round, source, images_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    char.id, char.session_id, char.name,
                    json.dumps(char.attributes, ensure_ascii=False),
                    int(char.is_active), int(char.is_alive),
                    char.first_seen_round, char.last_seen_round,
                    char.source, json.dumps([], ensure_ascii=False),
                    char.created_at, char.updated_at,
                ),
            )
        conn.commit()

        # Save first_mes as the opening assistant message
        first_mes = card.character.first_mes
        if first_mes:
            conn.execute(
                """INSERT INTO chat_messages
                   (id, session_id, role, name, content, idx, round_index, created_at)
                   VALUES (?, ?, 'assistant', ?, ?, 0, 0, datetime('now'))""",
                (generate_id(), sid, card.character.name, first_mes),
            )
            conn.commit()

    row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (sid,)).fetchone()
    conn.close()
    return _row_to_session(row)


@router.get("/{session_id}", response_model=IChatSession)
def get_session(session_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _row_to_session(row)


@router.delete("/{session_id}")
def delete_session(session_id: str):
    conn = get_conn()
    # Delete child records first to respect foreign keys
    conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM story_characters WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM character_change_logs WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM memory_summaries WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM long_term_memories WHERE session_id = ?", (session_id,))
    # Finally delete the session itself
    conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/{session_id}/characters", response_model=list[IStoryCharacter])
def list_characters(session_id: str):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM story_characters WHERE session_id = ? ORDER BY first_seen_round ASC",
        (session_id,),
    ).fetchall()

    # Lazy-instantiate: if session has no characters, try to create from card
    if not rows:
        session_row = conn.execute(
            "SELECT card_id FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if session_row:
            card = get_card(session_row["card_id"])
            if card:
                characters = instantiate_auto_active(card, session_id)
                for char in characters:
                    conn.execute(
                        """INSERT INTO story_characters
                           (id, session_id, name, attributes_json, is_active, is_alive,
                            first_seen_round, last_seen_round, source, images_json, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            char.id, char.session_id, char.name,
                            json.dumps(char.attributes, ensure_ascii=False),
                            int(char.is_active), int(char.is_alive),
                            char.first_seen_round, char.last_seen_round,
                            char.source, json.dumps([], ensure_ascii=False),
                            char.created_at, char.updated_at,
                        ),
                    )
                conn.commit()
                rows = conn.execute(
                    "SELECT * FROM story_characters WHERE session_id = ? ORDER BY first_seen_round ASC",
                    (session_id,),
                ).fetchall()

    conn.close()
    return [_row_to_character(r) for r in rows]


ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/{session_id}/characters/{character_id}/image")
async def upload_character_image(
    session_id: str,
    character_id: str,
    file: UploadFile = File(...),
):
    """Upload an image and attach it to a character."""
    # Validate
    if file.content_type and file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, f"Unsupported image type: {file.content_type}")
    raw = await file.read()
    if len(raw) > MAX_IMAGE_SIZE:
        raise HTTPException(400, "Image too large (max 10 MB)")

    # Verify character exists
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM story_characters WHERE id = ? AND session_id = ?",
        (character_id, session_id),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Character not found")

    # Save file
    ext = Path(file.filename or "image.png").suffix or ".png"
    filename = f"char_{uuid.uuid4().hex}{ext}"
    out_path = Path(settings.uploads_dir) / filename
    out_path.write_bytes(raw)

    # Build image record
    img = ICharacterImage(
        id=generate_id(),
        url=f"/uploads/{filename}",
        filename=filename,
        label="",
    )
    existing_images = json.loads(row["images_json"] or "[]")
    existing_images.append(img.model_dump())

    # Update DB
    conn.execute(
        "UPDATE story_characters SET images_json = ?, updated_at = datetime('now') WHERE id = ?",
        (json.dumps(existing_images, ensure_ascii=False), character_id),
    )
    conn.commit()

    # Return updated character
    updated = conn.execute("SELECT * FROM story_characters WHERE id = ?", (character_id,)).fetchone()
    conn.close()
    return _row_to_character(updated)


def _row_to_character(row) -> IStoryCharacter:
    return IStoryCharacter(
        id=row["id"],
        session_id=row["session_id"],
        name=row["name"],
        attributes=json.loads(row["attributes_json"] or "{}"),
        is_active=bool(row["is_active"]),
        is_alive=bool(row["is_alive"]),
        first_seen_round=row["first_seen_round"],
        last_seen_round=row["last_seen_round"],
        source=row["source"] or "card_definition",
        images=json.loads(row["images_json"] or "[]"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_session(row) -> IChatSession:
    import json
    return IChatSession(
        id=row["id"],
        card_id=row["card_id"],
        mode=EChatMode(row["mode"]),
        name=row["name"] or "",
        greeting_index=row["greeting_index"],
        model=row["model"] or "",
        worldbook_ids=json.loads(row["worldbook_ids"] or "[]"),
        preset_name=row["preset_name"] or "",
        background_image=row["background_image"],
        parent_session_id=row["parent_session_id"],
        branch_number=row["branch_number"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
