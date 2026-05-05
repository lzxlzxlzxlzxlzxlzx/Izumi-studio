"""
PresetManager — Manage preset storage, retrieval, and default preset.
"""

from __future__ import annotations
from typing import Optional
import json
from pathlib import Path

from app.config import settings
from app.db.database import get_conn
from app.models.preset import IPreset


def get_preset(name: str) -> Optional[IPreset]:
    """Load a preset from disk by name."""
    conn = get_conn()
    row = conn.execute(
        "SELECT file_path FROM presets_index WHERE name = ?", (name,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    try:
        raw = json.loads(Path(row["file_path"]).read_text(encoding="utf-8"))
        return IPreset(**raw)
    except Exception:
        return None


def get_default_preset() -> Optional[IPreset]:
    """
    Return the default preset if one is configured.
    Currently returns the first imported preset as default.
    """
    conn = get_conn()
    row = conn.execute(
        "SELECT name FROM presets_index ORDER BY updated_at DESC LIMIT 1"
    ).fetchone()
    conn.close()

    if not row:
        return None

    return get_preset(row["name"])


def set_default_preset(name: str) -> bool:
    """Mark a preset as the default by touching its updated_at."""
    preset = get_preset(name)
    if not preset:
        return False

    conn = get_conn()
    conn.execute(
        "UPDATE presets_index SET updated_at = datetime('now') WHERE name = ?",
        (name,),
    )
    conn.commit()
    conn.close()
    return True


def save_preset(preset: IPreset) -> bool:
    """Write a preset back to its JSON file and update the index."""
    conn = get_conn()
    row = conn.execute(
        "SELECT file_path FROM presets_index WHERE name = ?", (preset.name,)
    ).fetchone()
    if not row:
        conn.close()
        return False

    out_path = Path(row["file_path"])
    out_path.write_text(
        json.dumps(preset.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    conn.execute(
        "UPDATE presets_index SET updated_at = datetime('now') WHERE name = ?",
        (preset.name,),
    )
    conn.commit()
    conn.close()
    return True


def list_presets() -> list[dict]:
    """List all imported presets."""
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
