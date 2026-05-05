"""
CharacterRegistryEngine — Runtime character registry with event-sourced change logs.

- build(): Replay NPC templates + change logs → current registry
- processSkillCall(): Execute LLM tool calls (list/get/create/update/delete)
- rollback(): Discard changes after a target message index
"""

from __future__ import annotations
from typing import Optional
from datetime import datetime
import json
import uuid
import logging

from app.db.database import get_conn
from app.models.character import (
    IStoryCharacter, ICharacterChangeLog, ICharacterAttributeChange,
    ICharacterRegistry, ICharacterImage, ECharacterSkillOp,
)

logger = logging.getLogger(__name__)

MAX_CHARACTERS_PER_SESSION = 50


# ---------------------------------------------------------------
# Tool definitions (same as llm_router.CHARACTER_TOOLS)
# ---------------------------------------------------------------

def get_tool_definitions() -> list[dict]:
    """Return the 5 character-management tool definitions in OpenAI format."""
    return [
        {
            "type": "function",
            "function": {
                "name": "list_characters",
                "description": "列出当前会话中所有角色",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter": {
                            "type": "string",
                            "enum": ["all", "active", "inactive"],
                            "description": "过滤条件：all=全部, active=仅出场角色, inactive=仅离场角色",
                        }
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_character",
                "description": "查询指定角色的详细信息，包括所有属性和状态",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "角色名称（精确匹配）",
                        }
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_character",
                "description": "在故事中创建新角色",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "新角色名称"},
                        "attributes": {
                            "type": "object",
                            "description": "角色属性键值对，如 {'race':'人类','age':25,'occupation':'商人'}",
                        },
                        "is_active": {"type": "boolean", "description": "是否立即出场，默认 true"},
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_character",
                "description": "修改已有角色的属性。传 null 值的属性会被删除。不要传未变化的属性以减少变更量。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "要修改的角色名称"},
                        "attributes": {
                            "type": "object",
                            "description": "要修改的属性键值对。值为 null 表示删除该属性。",
                        },
                        "is_active": {"type": "boolean", "description": "是否出场"},
                        "is_alive": {"type": "boolean", "description": "是否存活"},
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "delete_character",
                "description": "删除/移除角色（角色死亡或离场时使用）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "要删除的角色名称"},
                    },
                    "required": ["name"],
                },
            },
        },
    ]


# ---------------------------------------------------------------
# Change log persistence
# ---------------------------------------------------------------

def get_change_logs(
    session_id: str,
    upto_message_index: Optional[int] = None,
) -> list[ICharacterChangeLog]:
    """Fetch change logs for a session, optionally filtered by message_index."""
    conn = get_conn()
    if upto_message_index is not None:
        rows = conn.execute(
            "SELECT * FROM character_change_logs WHERE session_id = ? AND message_index <= ? ORDER BY message_index ASC, timestamp ASC",
            (session_id, upto_message_index),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM character_change_logs WHERE session_id = ? ORDER BY message_index ASC, timestamp ASC",
            (session_id,),
        ).fetchall()
    conn.close()
    return [_row_to_log(r) for r in rows]


def _row_to_log(row) -> ICharacterChangeLog:
    return ICharacterChangeLog(
        id=row["id"],
        session_id=row["session_id"],
        message_id=row["message_id"],
        message_index=row["message_index"],
        character_id=row["character_id"],
        character_name=row["character_name"],
        action=row["action"],
        timestamp=row["timestamp"],
        changes=[ICharacterAttributeChange(**c) for c in json.loads(row["changes_json"] or "[]")],
    )


def _save_log(log: ICharacterChangeLog) -> None:
    conn = get_conn()
    changes_data = [c.model_dump() for c in log.changes]
    conn.execute(
        """INSERT INTO character_change_logs
           (id, session_id, message_id, message_index, character_id, character_name,
            action, timestamp, changes_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            log.id, log.session_id, log.message_id, log.message_index,
            log.character_id, log.character_name,
            log.action, log.timestamp,
            json.dumps(changes_data, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------
# Registry build (event-sourcing replay)
# ---------------------------------------------------------------

def build(
    session_id: str,
    card,  # ICharacterCard
    upto_message_index: int = 0,
) -> ICharacterRegistry:
    """
    Build the character registry by replaying NPC templates + change logs.

    1. Start with NPCs where start_active=True
    2. Replay all change logs with message_index <= upto_message_index
    """
    characters: dict[str, IStoryCharacter] = {}

    # Step 1: Initialize from card NPCs
    if card and card.character and card.character.npcs:
        for npc in card.character.npcs:
            if not npc.start_active:
                continue
            char_id = str(uuid.uuid4())
            attrs = dict(npc.attributes) if npc.attributes else {}
            attrs["name"] = npc.name
            character = IStoryCharacter(
                id=char_id,
                session_id=session_id,
                name=npc.name,
                attributes=attrs,
                is_active=True,
                is_alive=True,
                first_seen_round=0,
                last_seen_round=0,
                source="card_definition",
            )
            characters[char_id] = character

            # Persist snapshot
            _upsert_character(character)

    # Step 2: Replay change logs
    logs = get_change_logs(session_id, upto_message_index)
    for log in logs:
        if log.action == "create":
            char = IStoryCharacter(
                id=log.character_id,
                session_id=session_id,
                name=log.character_name,
                attributes={c.attribute: c.new_value for c in log.changes if c.new_value is not None},
                is_active=True,
                is_alive=True,
                first_seen_round=log.message_index,
                last_seen_round=log.message_index,
                source="model_creation",
            )
            characters[char.id] = char
            _upsert_character(char)

        elif log.action == "update":
            char = characters.get(log.character_id)
            if not char:
                continue
            for change in log.changes:
                if change.new_value is None:
                    char.attributes.pop(change.attribute, None)
                else:
                    char.attributes[change.attribute] = change.new_value
            char.last_seen_round = log.message_index
            char.updated_at = log.timestamp
            # Also apply is_active / is_alive from changes
            for change in log.changes:
                if change.attribute == "is_active" and change.new_value is not None:
                    char.is_active = bool(change.new_value)
                if change.attribute == "is_alive" and change.new_value is not None:
                    char.is_alive = bool(change.new_value)
            _upsert_character(char)

        elif log.action == "delete":
            characters.pop(log.character_id, None)
            _delete_character_snapshot(log.character_id)

    return ICharacterRegistry(
        session_id=session_id,
        characters=list(characters.values()),
        as_of_message_index=upto_message_index,
    )


# ---------------------------------------------------------------
# Skill execution
# ---------------------------------------------------------------

class SkillResult:
    def __init__(
        self,
        success: bool,
        registry: Optional[ICharacterRegistry] = None,
        change_log: Optional[ICharacterChangeLog] = None,
        error: Optional[str] = None,
        data: Optional[dict | list] = None,
    ):
        self.success = success
        self.registry = registry
        self.change_log = change_log
        self.error = error
        self.data = data


def process_skill_call(
    session_id: str,
    message_id: str,
    message_index: int,
    tool_call: dict,
    card,  # ICharacterCard
) -> SkillResult:
    """
    Execute a character-management tool call from the LLM.

    Args:
        session_id: Current session
        message_id: The message that triggered this tool call
        message_index: Index of the triggering message
        tool_call: {"id": str, "type": "function", "function": {"name": str, "arguments": str}}
        card: The character card (for NPC templates)

    Returns:
        SkillResult with success/failure and updated registry
    """
    fn = tool_call.get("function", {})
    op = fn.get("name", "")
    args_str = fn.get("arguments", "{}")

    try:
        args = json.loads(args_str) if isinstance(args_str, str) else (args_str or {})
    except json.JSONDecodeError:
        return SkillResult(success=False, error=f"Invalid JSON arguments: {args_str}")

    # Build registry at current state
    registry = build(session_id, card, message_index)

    if op == ECharacterSkillOp.LIST_CHARACTERS:
        return _handle_list(registry, args)
    elif op == ECharacterSkillOp.GET_CHARACTER:
        return _handle_get(registry, args)
    elif op == ECharacterSkillOp.CREATE_CHARACTER:
        return _handle_create(session_id, message_id, message_index, registry, args)
    elif op == ECharacterSkillOp.UPDATE_CHARACTER:
        return _handle_update(session_id, message_id, message_index, registry, args)
    elif op == ECharacterSkillOp.DELETE_CHARACTER:
        return _handle_delete(session_id, message_id, message_index, registry, args)
    else:
        return SkillResult(success=False, error=f"Unknown skill: {op}")


def _handle_list(registry: ICharacterRegistry, args: dict) -> SkillResult:
    filter_val = args.get("filter", "all")
    chars = registry.characters
    if filter_val == "active":
        chars = [c for c in chars if c.is_active]
    elif filter_val == "inactive":
        chars = [c for c in chars if not c.is_active]

    data = [
        {
            "name": c.name,
            "is_active": c.is_active,
            "is_alive": c.is_alive,
            "attributes": c.attributes,
            "source": c.source,
        }
        for c in chars
    ]
    return SkillResult(success=True, registry=registry, data=data)


def _handle_get(registry: ICharacterRegistry, args: dict) -> SkillResult:
    name = args.get("name", "")
    char = _find_by_name(registry, name)
    if not char:
        return SkillResult(success=False, error=f"Character '{name}' not found",
                           registry=registry, data=[])
    data = {
        "name": char.name,
        "is_active": char.is_active,
        "is_alive": char.is_alive,
        "attributes": char.attributes,
        "source": char.source,
        "first_seen_round": char.first_seen_round,
        "last_seen_round": char.last_seen_round,
    }
    return SkillResult(success=True, registry=registry, data=data)


def _handle_create(
    session_id: str, message_id: str, message_index: int,
    registry: ICharacterRegistry, args: dict,
) -> SkillResult:
    name = args.get("name", "")
    if not name:
        return SkillResult(success=False, error="Character name is required", registry=registry)

    if _find_by_name(registry, name):
        return SkillResult(success=False, error=f"Character '{name}' already exists", registry=registry)

    if len(registry.characters) >= MAX_CHARACTERS_PER_SESSION:
        return SkillResult(success=False, error=f"Max {MAX_CHARACTERS_PER_SESSION} characters per session", registry=registry)

    char_id = str(uuid.uuid4())
    attrs = args.get("attributes", {}) or {}
    if not isinstance(attrs, dict):
        attrs = {}
    attrs["name"] = name
    is_active = args.get("is_active", True)
    now_ts = datetime.now().isoformat()

    changes = [
        ICharacterAttributeChange(attribute=k, old_value=None, new_value=v)
        for k, v in attrs.items()
    ]
    if "is_active" not in attrs:
        changes.append(ICharacterAttributeChange(attribute="is_active", old_value=None, new_value=is_active))
    changes.append(ICharacterAttributeChange(attribute="is_alive", old_value=None, new_value=True))

    log = ICharacterChangeLog(
        id=str(uuid.uuid4()),
        session_id=session_id,
        message_id=message_id,
        message_index=message_index,
        character_id=char_id,
        character_name=name,
        action="create",
        timestamp=now_ts,
        changes=changes,
    )
    _save_log(log)

    char = IStoryCharacter(
        id=char_id, session_id=session_id, name=name,
        attributes=attrs,
        is_active=is_active, is_alive=True,
        first_seen_round=message_index, last_seen_round=message_index,
        source="model_creation",
        created_at=now_ts, updated_at=now_ts,
    )
    _upsert_character(char)
    registry.characters.append(char)

    return SkillResult(success=True, registry=registry, change_log=log, data={"name": name, "id": char_id})


def _handle_update(
    session_id: str, message_id: str, message_index: int,
    registry: ICharacterRegistry, args: dict,
) -> SkillResult:
    name = args.get("name", "")
    char = _find_by_name(registry, name)
    if not char:
        return SkillResult(success=False, error=f"Character '{name}' not found", registry=registry)

    new_attrs = args.get("attributes", {}) or {}
    if not isinstance(new_attrs, dict):
        new_attrs = {}
    changes: list[ICharacterAttributeChange] = []
    now_ts = datetime.now().isoformat()

    for attr, new_val in new_attrs.items():
        old_val = char.attributes.get(attr)
        if old_val != new_val:
            changes.append(ICharacterAttributeChange(
                attribute=attr, old_value=old_val, new_value=new_val,
            ))

    # Handle is_active
    if "is_active" in args and args["is_active"] != char.is_active:
        changes.append(ICharacterAttributeChange(
            attribute="is_active",
            old_value=char.is_active,
            new_value=args["is_active"],
        ))
        char.is_active = args["is_active"]

    # Handle is_alive
    if "is_alive" in args and args["is_alive"] != char.is_alive:
        changes.append(ICharacterAttributeChange(
            attribute="is_alive",
            old_value=char.is_alive,
            new_value=args["is_alive"],
        ))
        char.is_alive = args["is_alive"]

    if not changes:
        return SkillResult(success=True, registry=registry, data={"name": name, "changes": 0})

    for change in changes:
        if change.new_value is None:
            char.attributes.pop(change.attribute, None)
        else:
            char.attributes[change.attribute] = change.new_value

    char.updated_at = now_ts
    char.last_seen_round = message_index

    log = ICharacterChangeLog(
        id=str(uuid.uuid4()),
        session_id=session_id,
        message_id=message_id,
        message_index=message_index,
        character_id=char.id,
        character_name=name,
        action="update",
        timestamp=now_ts,
        changes=changes,
    )
    _save_log(log)
    _upsert_character(char)

    return SkillResult(success=True, registry=registry, change_log=log,
                       data={"name": name, "changes": len(changes)})


def _handle_delete(
    session_id: str, message_id: str, message_index: int,
    registry: ICharacterRegistry, args: dict,
) -> SkillResult:
    name = args.get("name", "")
    char = _find_by_name(registry, name)
    if not char:
        return SkillResult(success=False, error=f"Character '{name}' not found", registry=registry)

    now_ts = datetime.now().isoformat()
    log = ICharacterChangeLog(
        id=str(uuid.uuid4()),
        session_id=session_id,
        message_id=message_id,
        message_index=message_index,
        character_id=char.id,
        character_name=name,
        action="delete",
        timestamp=now_ts,
        changes=[],
    )
    _save_log(log)

    registry.characters = [c for c in registry.characters if c.id != char.id]
    _delete_character_snapshot(char.id)

    return SkillResult(success=True, registry=registry, change_log=log, data={"name": name})


def _find_by_name(registry: ICharacterRegistry, name: str) -> Optional[IStoryCharacter]:
    for c in registry.characters:
        if c.name == name:
            return c
    return None


# ---------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------

def rollback(
    session_id: str,
    target_message_index: int,
    card,  # ICharacterCard
) -> ICharacterRegistry:
    """
    Delete all change logs after target_message_index, then rebuild the registry.
    """
    conn = get_conn()
    conn.execute(
        "DELETE FROM character_change_logs WHERE session_id = ? AND message_index > ?",
        (session_id, target_message_index),
    )
    conn.commit()
    conn.close()

    return build(session_id, card, target_message_index)


# ---------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------

def _upsert_character(char: IStoryCharacter) -> None:
    conn = get_conn()
    existing = conn.execute("SELECT id FROM story_characters WHERE id = ?", (char.id,)).fetchone()
    if existing:
        conn.execute(
            """UPDATE story_characters SET name=?, attributes_json=?, is_active=?, is_alive=?,
               first_seen_round=?, last_seen_round=?, source=?, images_json=?, updated_at=?
               WHERE id=?""",
            (
                char.name,
                json.dumps(char.attributes, ensure_ascii=False),
                int(char.is_active), int(char.is_alive),
                char.first_seen_round, char.last_seen_round,
                char.source,
                json.dumps([img.model_dump() for img in char.images], ensure_ascii=False),
                char.updated_at,
                char.id,
            ),
        )
    else:
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
                char.source,
                json.dumps([img.model_dump() for img in char.images], ensure_ascii=False),
                char.created_at, char.updated_at,
            ),
        )
    conn.commit()
    conn.close()


def _delete_character_snapshot(char_id: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM story_characters WHERE id = ?", (char_id,))
    conn.commit()
    conn.close()
