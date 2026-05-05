"""
SillyTavern data import endpoints.

POST /api/import/worldbook  — upload a ST world book JSON file
POST /api/import/preset     — upload a ST preset JSON file
POST /api/import/card       — upload a ST V3 character card (.json or .png)
"""

import json
import base64
import struct
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from app.config import settings
from app.db.database import generate_id, get_conn
from app.services.st_importer import import_worldbook, import_preset, import_character_card

router = APIRouter(prefix="/api/import", tags=["import"])


def _extract_chara_from_png(data: bytes) -> dict:
    """
    Extract the ST V3 character card JSON from a PNG's tEXt chunk.

    SillyTavern embeds the card JSON (base64-encoded) in a tEXt chunk
    with keyword 'chara'. Also handles iTXt and zTXt chunks.
    """
    pos = 8  # skip PNG signature
    while pos < len(data):
        if pos + 8 > len(data):
            break
        length = struct.unpack('>I', data[pos:pos + 4])[0]
        chunk_type = data[pos + 4:pos + 8].decode('ascii', errors='ignore')
        chunk_data = data[pos + 8:pos + 8 + length]

        if chunk_type in ('tEXt', 'iTXt', 'zTXt'):
            null_idx = chunk_data.find(0)
            if null_idx > 0:
                keyword = chunk_data[:null_idx].decode('latin-1', errors='ignore')
                if keyword.lower() == 'chara':
                    value = chunk_data[null_idx + 1:].decode('utf-8', errors='ignore')
                    # Try parsing directly, fall back to base64 decode
                    try:
                        return json.loads(value)
                    except (json.JSONDecodeError, ValueError):
                        try:
                            decoded = base64.b64decode(value).decode('utf-8')
                            return json.loads(decoded)
                        except Exception:
                            raise HTTPException(400, "无法解析 PNG 中的角色卡数据")

        pos += 12 + length

    raise HTTPException(400, "PNG 文件中未找到角色卡数据 (chara chunk)")


@router.post("/worldbook")
async def import_wb(
    file: UploadFile = File(...),
    name: str = Form(""),
    description: str = Form(""),
):
    """Upload a SillyTavern world book JSON file and convert to our format."""
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(400, "Only .json files are accepted")

    raw = json.loads(await file.read())
    wb = import_worldbook(raw, name=name or (file.filename or "imported"), description=description)

    # Persist to JSON file
    out_path = settings.worldbooks_dir / f"{wb.id}.json"
    out_path.write_text(json.dumps(wb.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

    # Index
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO worldbooks_index (id, name, file_path, created_at, updated_at) VALUES (?, ?, ?, datetime('now'), datetime('now'))",
        (wb.id, wb.name, str(out_path)),
    )
    conn.commit()
    conn.close()

    return {"ok": True, "worldbook": wb.model_dump()}


@router.post("/preset")
async def import_pr(
    file: UploadFile = File(...),
    name: str = Form(""),
):
    """Upload a SillyTavern preset JSON file and convert to our format."""
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(400, "Only .json files are accepted")

    raw = json.loads(await file.read())
    preset = import_preset(raw, name=name or (file.filename or "imported-preset"))

    out_path = settings.presets_dir / f"{preset.name}.json"
    out_path.write_text(json.dumps(preset.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO presets_index (name, file_path, created_at, updated_at) VALUES (?, ?, datetime('now'), datetime('now'))",
        (preset.name, str(out_path)),
    )
    conn.commit()
    conn.close()

    return {"ok": True, "preset": preset.model_dump()}


@router.post("/card")
async def import_card(file: UploadFile = File(...)):
    """Upload a SillyTavern V3 character card (.json or .png) and convert to our format."""
    filename = (file.filename or "").lower()
    raw_bytes = await file.read()

    if filename.endswith(".json"):
        raw = json.loads(raw_bytes)
    elif filename.endswith(".png"):
        raw = _extract_chara_from_png(raw_bytes)
    else:
        raise HTTPException(400, "仅支持 .json 或 .png 格式的角色卡文件")

    # Extract embedded character_book before converting (ST V3 cards often embed
    # world books directly — ReZero card has 210 entries in character_book)
    data = raw.get("data", raw)
    embedded_wb = data.get("character_book")
    worldbook_id: str | None = None

    if embedded_wb and isinstance(embedded_wb, dict) and embedded_wb.get("entries"):
        try:
            wb_name = embedded_wb.get("name") or f"{data.get('name', 'unknown')} 世界书"
            wb = import_worldbook(embedded_wb, name=wb_name)
            wb_path = settings.worldbooks_dir / f"{wb.id}.json"
            wb_path.write_text(json.dumps(wb.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

            conn = get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO worldbooks_index (id, name, file_path, created_at, updated_at) VALUES (?, ?, ?, datetime('now'), datetime('now'))",
                (wb.id, wb.name, str(wb_path)),
            )
            conn.commit()
            conn.close()

            worldbook_id = wb.id
        except Exception:
            pass  # world book import failure shouldn't block card import

    card = import_character_card(raw, worldbook_id=worldbook_id)

    # Save JSON
    out_path = settings.cards_dir / f"{card.id}.json"
    out_path.write_text(json.dumps(card.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

    # Insert into DB
    from app.services.card_manager import _insert_card
    _insert_card(card)

    result = {"ok": True, "card": card.model_dump()}
    if worldbook_id:
        result["worldbook_id"] = worldbook_id
    return result
