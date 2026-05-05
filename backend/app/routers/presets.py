"""
Preset management endpoints.

GET    /api/presets       — list all imported presets
GET    /api/presets/{name} — get a single preset with full content
DELETE /api/presets/{name} — delete a preset (file + index)
"""

import json
from fastapi import APIRouter, HTTPException
from app.config import settings
from app.db.database import get_conn
from app.models.preset import IPreset

router = APIRouter()


@router.get("")
def list_presets():
    conn = get_conn()
    rows = conn.execute(
        "SELECT name, file_path, created_at, updated_at FROM presets_index ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()

    return [
        {
            "name": r["name"],
            "file_path": r["file_path"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


@router.get("/{name}", response_model=IPreset)
def get_preset(name: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT file_path FROM presets_index WHERE name = ?", (name,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Preset not found")

    try:
        raw = json.loads(open(row["file_path"], "r", encoding="utf-8").read())
        return IPreset(**raw)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load preset: {e}")


@router.delete("/{name}")
def delete_preset(name: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT file_path FROM presets_index WHERE name = ?", (name,)
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Preset not found")

    conn.execute("DELETE FROM presets_index WHERE name = ?", (name,))
    conn.commit()
    conn.close()

    try:
        import os
        os.remove(row["file_path"])
    except OSError:
        pass

    return {"ok": True}


@router.put("/{name}", response_model=IPreset)
def update_preset(name: str, preset: IPreset):
    """Update an existing preset (prompts, params, etc.)."""
    if preset.name != name:
        raise HTTPException(status_code=400, detail="Name in path must match name in body")
    from app.services.preset_manager import save_preset
    if not save_preset(preset):
        raise HTTPException(status_code=404, detail="Preset not found")
    return preset
