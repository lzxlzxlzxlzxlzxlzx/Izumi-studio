"""Unit tests for CharacterRegistryEngine."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import patch, MagicMock
import json

from app.models.character import (
    IStoryCharacter, ICharacterChangeLog, ICharacterAttributeChange,
    ICharacterRegistry, ECharacterSkillOp,
)


class FakeNPC:
    def __init__(self, name, start_active=True, attributes=None):
        self.name = name
        self.start_active = start_active
        self.attributes = attributes or {}

class FakeCharacter:
    def __init__(self, name, npcs=None):
        self.name = name
        self.npcs = npcs or []

class FakeCard:
    def __init__(self, name, npcs=None):
        self.character = FakeCharacter(name, npcs)


def test_build_empty():
    """Card with no NPCs -> empty registry."""
    card = FakeCard("test", [])
    with patch("app.services.character_registry.get_change_logs", return_value=[]):
        from app.services.character_registry import build
        reg = build("s1", card, 0)
    assert reg.characters == []
    assert reg.as_of_message_index == 0


def test_build_with_npcs():
    """2 NPCs with start_active=True -> 2 characters in registry."""
    card = FakeCard("test", [
        FakeNPC("艾莉丝", True, {"race": "elf"}),
        FakeNPC("雷恩", True, {"race": "human"}),
    ])
    with patch("app.services.character_registry.get_change_logs", return_value=[]), \
         patch("app.services.character_registry._upsert_character"):
        from app.services.character_registry import build
        reg = build("s1", card, 0)
    assert len(reg.characters) == 2
    names = {c.name for c in reg.characters}
    assert "艾莉丝" in names
    assert "雷恩" in names


def test_dormant_npc_not_included():
    """NPC with start_active=False -> not in registry."""
    card = FakeCard("test", [
        FakeNPC("active", True),
        FakeNPC("dormant", False),
    ])
    with patch("app.services.character_registry.get_change_logs", return_value=[]), \
         patch("app.services.character_registry._upsert_character"):
        from app.services.character_registry import build
        reg = build("s1", card, 0)
    names = {c.name for c in reg.characters}
    assert "active" in names
    assert "dormant" not in names


def test_build_with_changes():
    """1 NPC + 1 model-created via change log -> 2 characters."""
    card = FakeCard("test", [FakeNPC("艾莉丝", True, {"race": "elf"})])
    create_log = ICharacterChangeLog(
        id="log1", session_id="s1", message_id="msg2", message_index=1,
        character_id="char2", character_name="波波",
        action="create",
        changes=[
            ICharacterAttributeChange(attribute="name", new_value="波波"),
            ICharacterAttributeChange(attribute="race", new_value="slime"),
        ],
    )
    with patch("app.services.character_registry.get_change_logs", return_value=[create_log]), \
         patch("app.services.character_registry._upsert_character"):
        from app.services.character_registry import build
        reg = build("s1", card, 5)
    assert len(reg.characters) == 2
    names = {c.name for c in reg.characters}
    assert "波波" in names


def test_create_character():
    """processSkillCall with create_character -> new character in registry."""
    card = FakeCard("test")
    tool_call = {
        "id": "tc1", "type": "function",
        "function": {
            "name": "create_character",
            "arguments": json.dumps({"name": "路人甲", "attributes": {"occupation": "商人"}}, ensure_ascii=False),
        },
    }

    with patch("app.services.character_registry.get_change_logs", return_value=[]), \
         patch("app.services.character_registry._save_log"), \
         patch("app.services.character_registry._upsert_character"):
        from app.services.character_registry import process_skill_call
        result = process_skill_call("s1", "msg1", 1, tool_call, card)

    assert result.success
    assert result.data["name"] == "路人甲"
    assert any(c.name == "路人甲" for c in result.registry.characters)


def test_create_duplicate_fails():
    """Cannot create a character with an existing name."""
    card = FakeCard("test")
    tool_call = {
        "id": "tc1", "type": "function",
        "function": {
            "name": "create_character",
            "arguments": json.dumps({"name": "路人甲"}, ensure_ascii=False),
        },
    }

    # First call: empty logs -> create succeeds
    with patch("app.services.character_registry.get_change_logs", return_value=[]), \
         patch("app.services.character_registry._save_log"), \
         patch("app.services.character_registry._upsert_character"):
        from app.services.character_registry import process_skill_call
        result1 = process_skill_call("s1", "msg1", 1, tool_call, card)
        assert result1.success

    # Second call: logs now include the first create, so rebuild will have "路人甲"
    existing_log = result1.change_log
    with patch("app.services.character_registry.get_change_logs", return_value=[existing_log]), \
         patch("app.services.character_registry._save_log"), \
         patch("app.services.character_registry._upsert_character"):
        result2 = process_skill_call("s1", "msg2", 2, tool_call, card)
        assert not result2.success
        assert "already exists" in (result2.error or "")


def test_update_attribute():
    """Update character attribute -> changelog records old/new diff."""
    card = FakeCard("test", [FakeNPC("艾莉丝", True, {"hp": 100, "mp": 50})])

    tool_call = {
        "id": "tc1", "type": "function",
        "function": {
            "name": "update_character",
            "arguments": json.dumps({"name": "艾莉丝", "attributes": {"hp": 80, "location": "酒馆"}}, ensure_ascii=False),
        },
    }

    with patch("app.services.character_registry.get_change_logs", return_value=[]), \
         patch("app.services.character_registry._save_log"), \
         patch("app.services.character_registry._upsert_character"):
        from app.services.character_registry import process_skill_call
        result = process_skill_call("s1", "msg1", 1, tool_call, card)

    assert result.success
    assert result.change_log is not None
    # Find hp change
    hp_change = next((c for c in result.change_log.changes if c.attribute == "hp"), None)
    assert hp_change is not None
    assert hp_change.old_value == 100
    assert hp_change.new_value == 80

    # Find location change
    loc_change = next((c for c in result.change_log.changes if c.attribute == "location"), None)
    assert loc_change is not None
    assert loc_change.old_value is None
    assert loc_change.new_value == "酒馆"


def test_delete_attribute():
    """Setting attribute to null -> attribute removed."""
    card = FakeCard("test", [FakeNPC("艾莉丝", True, {"hp": 100, "status": "中毒"})])

    tool_call = {
        "id": "tc1", "type": "function",
        "function": {
            "name": "update_character",
            "arguments": json.dumps({"name": "艾莉丝", "attributes": {"status": None}}, ensure_ascii=False),
        },
    }

    with patch("app.services.character_registry.get_change_logs", return_value=[]), \
         patch("app.services.character_registry._save_log"), \
         patch("app.services.character_registry._upsert_character"):
        from app.services.character_registry import process_skill_call
        result = process_skill_call("s1", "msg1", 1, tool_call, card)

    assert result.success
    char = next(c for c in result.registry.characters if c.name == "艾莉丝")
    assert "status" not in char.attributes


def test_delete_character():
    """Delete removes character from registry."""
    card = FakeCard("test", [FakeNPC("临时角色", True)])

    tool_call = {
        "id": "tc1", "type": "function",
        "function": {
            "name": "delete_character",
            "arguments": json.dumps({"name": "临时角色"}, ensure_ascii=False),
        },
    }

    with patch("app.services.character_registry.get_change_logs", return_value=[]), \
         patch("app.services.character_registry._save_log"), \
         patch("app.services.character_registry._upsert_character"), \
         patch("app.services.character_registry._delete_character_snapshot"):
        from app.services.character_registry import process_skill_call
        result = process_skill_call("s1", "msg1", 1, tool_call, card)

    assert result.success
    assert not any(c.name == "临时角色" for c in result.registry.characters)


def test_list_filter():
    """list_characters with filter should work."""
    card = FakeCard("test", [
        FakeNPC("active1", True),
        FakeNPC("inactive1", False),
    ])
    tool_call = {
        "id": "tc1", "type": "function",
        "function": {
            "name": "list_characters",
            "arguments": json.dumps({"filter": "active"}, ensure_ascii=False),
        },
    }

    with patch("app.services.character_registry.get_change_logs", return_value=[]), \
         patch("app.services.character_registry._upsert_character"):
        from app.services.character_registry import process_skill_call
        result = process_skill_call("s1", "msg1", 1, tool_call, card)

    assert result.success
    # Only "active1" should be in the result data (inactive1 is dormant, won't be in build)
    assert len(result.data) == 1


def test_get_nonexistent():
    """get_character for non-existent name returns error."""
    card = FakeCard("test")
    tool_call = {
        "id": "tc1", "type": "function",
        "function": {
            "name": "get_character",
            "arguments": json.dumps({"name": "不存在"}, ensure_ascii=False),
        },
    }

    with patch("app.services.character_registry.get_change_logs", return_value=[]):
        from app.services.character_registry import process_skill_call
        result = process_skill_call("s1", "msg1", 1, tool_call, card)

    assert not result.success
    assert "not found" in (result.error or "")


def test_tool_definitions():
    """5 tool definitions returned in OpenAI format."""
    from app.services.character_registry import get_tool_definitions
    defs = get_tool_definitions()
    assert len(defs) == 5
    names = {d["function"]["name"] for d in defs}
    assert names == {
        "list_characters", "get_character", "create_character",
        "update_character", "delete_character",
    }
    for d in defs:
        assert d["type"] == "function"
        assert "parameters" in d["function"]


def test_rollback_deletes_later_logs():
    """Rollback deletes logs after target index."""
    card = FakeCard("test")
    conn = MagicMock()

    with patch("app.services.character_registry.get_conn", return_value=conn), \
         patch("app.services.character_registry.get_change_logs", return_value=[]), \
         patch("app.services.character_registry.build", return_value=ICharacterRegistry(
             session_id="s1", characters=[], as_of_message_index=3
         )) as mock_build:
        from app.services.character_registry import rollback
        result = rollback("s1", 3, card)

    conn.execute.assert_called()
    mock_build.assert_called_once_with("s1", card, 3)


if __name__ == "__main__":
    tests = [
        ("Build empty registry", test_build_empty),
        ("Build with NPCs", test_build_with_npcs),
        ("Dormant NPC not included", test_dormant_npc_not_included),
        ("Build with change logs", test_build_with_changes),
        ("Create character", test_create_character),
        ("Create duplicate fails", test_create_duplicate_fails),
        ("Update attribute", test_update_attribute),
        ("Delete attribute (null value)", test_delete_attribute),
        ("Delete character", test_delete_character),
        ("List with filter", test_list_filter),
        ("Get non-existent character", test_get_nonexistent),
        ("Tool definitions (5 functions)", test_tool_definitions),
        ("Rollback", test_rollback_deletes_later_logs),
    ]

    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            import traceback
            print(f"  FAIL  {name}: {e}")
            traceback.print_exc()

    print(f"\n{passed}/{len(tests)} tests passed")
