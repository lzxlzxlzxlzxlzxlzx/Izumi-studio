"""
World Book management endpoints.

GET    /api/worldbooks        — list all imported world books
GET    /api/worldbooks/{id}   — get a single world book with entries
DELETE /api/worldbooks/{id}   — delete a world book (file + index)
"""

import json
from fastapi import APIRouter, HTTPException
from app.config import settings
from app.db.database import get_conn
from app.models.worldbook import IWorldBook

router = APIRouter()


@router.get("")
def list_worldbooks():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, file_path, created_at, updated_at FROM worldbooks_index ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()

    return [
        {
            "id": r["id"],
            "name": r["name"],
            "file_path": r["file_path"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


@router.get("/{wb_id}", response_model=IWorldBook)
def get_worldbook(wb_id: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT file_path FROM worldbooks_index WHERE id = ?", (wb_id,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="World book not found")

    try:
        raw = json.loads(open(row["file_path"], "r", encoding="utf-8").read())
        return IWorldBook(**raw)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load world book: {e}")


@router.delete("/{wb_id}")
def delete_worldbook(wb_id: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT file_path FROM worldbooks_index WHERE id = ?", (wb_id,)
    ).fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="World book not found")

    conn.execute("DELETE FROM worldbooks_index WHERE id = ?", (wb_id,))
    conn.commit()
    conn.close()

    try:
        import os
        os.remove(row["file_path"])
    except OSError:
        pass

    return {"ok": True}
