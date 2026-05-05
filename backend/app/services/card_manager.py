import json
from pathlib import Path
from app.config import settings
from app.db.database import get_conn, generate_id
from app.models.card import ICharacterCard, ICharacterDefinition, ICoverInfo, IAvatarInfo, IBackgroundInfo


def list_cards(search: str = "", tags: list[str] | None = None) -> list[ICharacterCard]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM character_cards ORDER BY created_at DESC").fetchall()
    cards = [_row_to_card(r) for r in rows]
    conn.close()

    if search:
        q = search.lower()
        cards = [
            c for c in cards
            if q in c.name.lower()
            or q in c.description.lower()
            or any(q in t.lower() for t in c.tags)
        ]

    if tags:
        cards = [c for c in cards if all(t in c.tags for t in tags)]

    return cards


def get_card(card_id: str) -> ICharacterCard | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM character_cards WHERE id = ?", (card_id,)).fetchone()
    conn.close()
    return _row_to_card(row) if row else None


def create_card(name: str, description: str = "", tags: list[str] | None = None) -> ICharacterCard:
    card_id = generate_id()
    card = ICharacterCard(
        id=card_id,
        name=name,
        description=description,
        tags=tags or [],
        character=ICharacterDefinition(name=name),
    )
    _insert_card(card)
    return card


def update_card(card_id: str, **fields) -> ICharacterCard | None:
    card = get_card(card_id)
    if not card:
        return None

    for key, val in fields.items():
        if hasattr(card, key) and key not in ("character", "preset_config"):
            setattr(card, key, val)

    if "character" in fields:
        card.character = ICharacterDefinition(
            **(fields["character"] if isinstance(fields["character"], dict) else fields["character"].model_dump())
        )

    if "preset_config" in fields:
        from app.models.card import IPresetConfig
        cfg = fields["preset_config"]
        card.preset_config = IPresetConfig(
            **(cfg if isinstance(cfg, dict) else cfg.model_dump())
        )

    if "background" in fields:
        bg = fields["background"]
        card.background = IBackgroundInfo(
            **(bg if isinstance(bg, dict) else bg.model_dump())
        )

    conn = get_conn()
    conn.execute(
        """UPDATE character_cards SET
            name = ?, description = ?, tags = ?,
            character_json = ?,
            system_prompt = ?, post_history_instructions = ?,
            preset_name = ?, preset_config_json = ?,
            background_json = ?,
            worldbook_ids = ?,
            status = ?, version = version + 1,
            updated_at = datetime('now')
           WHERE id = ?""",
        (
            card.name, card.description, json.dumps(card.tags),
            _json(card.character),
            card.system_prompt, card.post_history_instructions,
            card.preset_name, _json(card.preset_config),
            _json(card.background),
            json.dumps(card.worldbook_ids),
            card.status.value if hasattr(card.status, 'value') else str(card.status),
            card_id,
        ),
    )
    conn.commit()
    conn.close()
    return get_card(card_id)


def delete_card(card_id: str) -> bool:
    conn = get_conn()
    cur = conn.execute("DELETE FROM character_cards WHERE id = ?", (card_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


def _insert_card(card: ICharacterCard):
    conn = get_conn()
    # Check for existing card with same name — update instead of inserting duplicate
    existing = conn.execute(
        "SELECT id FROM character_cards WHERE name = ?", (card.name,)
    ).fetchone()
    if existing:
        card_id = existing["id"]
        conn.execute(
            """UPDATE character_cards SET
                description=?, tags=?, spec=?, spec_version=?, extensions=?,
                cover_json=?, avatar_json=?, background_json=?, character_json=?,
                system_prompt=?, post_history_instructions=?, depth_prompt_json=?,
                worldbook_ids=?, preset_name=?, preset_config_json=?, image_config_json=?,
                authors_note_json=?, quick_reply_set_ids=?, regex_script_ids=?,
                status=?, version=?, updated_at=datetime('now')
               WHERE id=?""",
            (
                card.description, json.dumps(card.tags),
                card.spec, card.spec_version, json.dumps(card.extensions),
                _json(card.cover), _json(card.avatar), _json(card.background), _json(card.character),
                card.system_prompt, card.post_history_instructions,
                _json(card.depth_prompt) if card.depth_prompt else None,
                json.dumps(card.worldbook_ids), card.preset_name,
                _json(card.preset_config), _json(card.image_config),
                _json(card.authors_note) if card.authors_note else None,
                json.dumps(card.quick_reply_set_ids), json.dumps(card.regex_script_ids),
                card.status.value, card.version,
                card_id,
            ),
        )
    else:
        conn.execute(
            """INSERT INTO character_cards (
                id, name, description, tags, spec, spec_version, extensions,
                cover_json, avatar_json, background_json, character_json,
                system_prompt, post_history_instructions, depth_prompt_json,
                worldbook_ids, preset_name, preset_config_json, image_config_json,
                authors_note_json, quick_reply_set_ids, regex_script_ids,
                status, version, created_at, published_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                card.id, card.name, card.description, json.dumps(card.tags),
                card.spec, card.spec_version, json.dumps(card.extensions),
                _json(card.cover), _json(card.avatar), _json(card.background), _json(card.character),
                card.system_prompt, card.post_history_instructions,
                _json(card.depth_prompt) if card.depth_prompt else None,
                json.dumps(card.worldbook_ids), card.preset_name,
                _json(card.preset_config), _json(card.image_config),
                _json(card.authors_note) if card.authors_note else None,
                json.dumps(card.quick_reply_set_ids), json.dumps(card.regex_script_ids),
                card.status.value, card.version, card.created_at, card.published_at,
            ),
        )
    conn.commit()
    conn.close()


def _row_to_card(row) -> ICharacterCard:
    return ICharacterCard(
        id=row["id"],
        name=row["name"],
        description=row["description"] or "",
        tags=json.loads(row["tags"] or "[]"),
        spec=row["spec"] or "chara_card_v3",
        spec_version=row["spec_version"] or "1.0",
        extensions=json.loads(row["extensions"] or "{}"),
        cover=ICoverInfo(**json.loads(row["cover_json"] or "{}") or {"image_path": ""}),
        avatar=IAvatarInfo(**json.loads(row["avatar_json"] or "{}") or {"image_path": ""}),
        background=IBackgroundInfo(**json.loads(row["background_json"] or "{}") or {"image_path": ""}),
        character=ICharacterDefinition(**json.loads(row["character_json"] or "{}") or {"name": row["name"]}),
        system_prompt=row["system_prompt"],
        post_history_instructions=row["post_history_instructions"],
        depth_prompt=_parse_optional(row["depth_prompt_json"]),
        worldbook_ids=json.loads(row["worldbook_ids"] or "[]"),
        preset_name=row["preset_name"],
        preset_config=json.loads(row["preset_config_json"] or "{}"),
        image_config=json.loads(row["image_config_json"] or "{}"),
        authors_note=_parse_optional(row["authors_note_json"]),
        quick_reply_set_ids=json.loads(row["quick_reply_set_ids"] or "[]"),
        regex_script_ids=json.loads(row["regex_script_ids"] or "[]"),
        status=row["status"] or "draft",
        version=row["version"] or 0,
        created_at=row["created_at"] or "",
        published_at=row["published_at"],
    )


def _json(obj) -> str:
    if isinstance(obj, dict):
        return json.dumps(obj, default=str)
    return json.dumps(obj.model_dump(), default=str)


def _parse_optional(val):
    if val is None:
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return None
