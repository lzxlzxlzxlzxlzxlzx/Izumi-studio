"""
Konata Chat API — 泉此方系统对话路由

Endpoints:
- CRUD for konata chat sessions (mode='chat')
- SSE streaming chat with tool calling
- Data summary for the frontend reference panel
"""

import json
import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from app.db.database import get_conn, generate_id
from app.models.session import IChatSession, EChatMode
from app.services.konata_service import chat_stream

logger = logging.getLogger(__name__)

router = APIRouter()

SYSTEM_CARD_ID = "_konata_system"


# ============================================================
# Session CRUD
# ============================================================


@router.get("/sessions", response_model=list[IChatSession])
def list_sessions():
    """List all konata chat sessions ordered by last update."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chat_sessions WHERE mode = 'chat' ORDER BY updated_at DESC"
    ).fetchall()
    sessions = [_row_to_session(r) for r in rows]
    conn.close()
    return sessions


@router.post("/sessions", response_model=IChatSession, status_code=201)
def create_session():
    """Create a new konata chat session."""
    conn = get_conn()
    sid = generate_id()
    conn.execute(
        """INSERT INTO chat_sessions (id, card_id, mode, name, greeting_index, created_at, updated_at)
           VALUES (?, ?, 'chat', '新对话', 0, datetime('now'), datetime('now'))""",
        (sid, SYSTEM_CARD_ID),
    )
    conn.commit()

    row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (sid,)).fetchone()
    conn.close()
    return _row_to_session(row)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete a konata chat session and its messages."""
    conn = get_conn()

    sess = conn.execute(
        "SELECT * FROM chat_sessions WHERE id = ? AND mode = 'chat'", (session_id,)
    ).fetchone()
    if not sess:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/sessions/{session_id}", response_model=IChatSession)
def get_session(session_id: str):
    """Get a konata chat session."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return _row_to_session(row)


# ============================================================
# Messages
# ============================================================


@router.get("/messages/{session_id}")
def list_messages(session_id: str):
    """List messages for a konata chat session."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY idx ASC",
        (session_id,),
    ).fetchall()
    messages = []
    for r in rows:
        messages.append({
            "id": r["id"],
            "session_id": r["session_id"],
            "role": r["role"],
            "name": r["name"] or "",
            "content": r["content"] or "",
            "index": r["idx"],
            "round_index": r["round_index"],
            "created_at": r["created_at"],
            "tool_calls": json.loads(r["tool_calls_json"] or "[]"),
            "tool_call_id": r["tool_call_id"],
        })
    conn.close()
    return messages


# ============================================================
# SSE Streaming
# ============================================================


@router.post("/stream/{session_id}")
async def stream_konata(session_id: str, input: str = Query(...)):
    """SSE streaming chat with Konata (with tool calling for database queries)."""
    conn = get_conn()

    # Verify session exists
    sess = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    if not sess:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
    conn.close()

    async def event_generator():
        try:
            async for chunk in chat_stream(
                session_id=session_id,
                input_text=input,
                model="deepseek-chat",
            ):
                if chunk.type == "token":
                    yield {"data": json.dumps({"type": "token", "token": chunk.token}, ensure_ascii=False)}
                elif chunk.type == "tool_call":
                    yield {"data": json.dumps({"type": "tool_call", "tool_call": chunk.tool_call}, ensure_ascii=False)}
                elif chunk.type == "done":
                    yield {"data": json.dumps({"type": "done", "full_response": chunk.full_response}, ensure_ascii=False)}
                    return
                elif chunk.type == "error":
                    yield {"data": json.dumps({"type": "error", "error": chunk.error}, ensure_ascii=False)}
                    return
        except Exception as e:
            logger.exception(f"[konata] stream failed session={session_id[:8]}")
            yield {"data": json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(event_generator())


# ============================================================
# Data Summary (for frontend ReferencePanel)
# ============================================================


@router.get("/cards-summary")
def get_cards_summary():
    """Return all character cards with their play sessions for the reference panel."""
    conn = get_conn()

    # Get all non-system cards
    card_rows = conn.execute(
        "SELECT id, name, description, tags FROM character_cards "
        "WHERE id != ? ORDER BY created_at DESC",
        (SYSTEM_CARD_ID,),
    ).fetchall()

    cards = []
    for cr in card_rows:
        # Get play sessions for this card
        sess_rows = conn.execute(
            "SELECT id, name, updated_at, created_at FROM chat_sessions "
            "WHERE card_id = ? AND mode = 'play' ORDER BY updated_at DESC",
            (cr["id"],),
        ).fetchall()

        sessions = []
        for sr in sess_rows:
            msg_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM chat_messages WHERE session_id = ?",
                (sr["id"],),
            ).fetchone()["cnt"]
            sessions.append({
                "id": sr["id"],
                "name": sr["name"] or "未命名会话",
                "updated_at": sr["updated_at"],
                "created_at": sr["created_at"],
                "message_count": msg_count,
            })

        cards.append({
            "id": cr["id"],
            "name": cr["name"],
            "description": cr["description"] or "",
            "tags": json.loads(cr["tags"] or "[]"),
            "sessions": sessions,
        })

    conn.close()
    return {"cards": cards}


# ============================================================
# Helpers
# ============================================================


def _row_to_session(row) -> IChatSession:
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
