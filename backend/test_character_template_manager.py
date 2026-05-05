"""Unit tests for CharacterTemplateManager."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.character_template_manager import (
    get_templates, instantiate, instantiate_auto_active,
)
from app.models.character import IStoryCharacter


class FakeNPC:
    def __init__(self, name, start_active=True, attributes=None, description=""):
        self.name = name
        self.start_active = start_active
        self.attributes = attributes or {}
        self.description = description


class FakeCharacter:
    def __init__(self, npcs=None):
        self.npcs = npcs or []


class FakeCard:
    def __init__(self, npcs=None):
        self.character = FakeCharacter(npcs)


def test_get_templates_separates():
    """Auto-active and dormant NPCs are separated correctly."""
    card = FakeCard([
        FakeNPC("active1", True),
        FakeNPC("active2", True),
        FakeNPC("dormant1", False),
        FakeNPC("dormant2", False),
    ])
    result = get_templates(card)
    assert len(result.auto_active) == 2
    assert len(result.dormant) == 2
    assert result.auto_active[0].name == "active1"
    assert result.dormant[0].name == "dormant1"


def test_get_templates_empty():
    """Card with no NPCs returns empty lists."""
    card = FakeCard([])
    result = get_templates(card)
    assert result.auto_active == []
    assert result.dormant == []


def test_get_templates_none_card():
    """None card returns empty lists."""
    result = get_templates(None)
    assert result.auto_active == []
    assert result.dormant == []


def test_get_templates_none_npcs():
    """Card with None npcs returns empty lists."""
    card = FakeCharacter()  # no npcs attribute
    # reconstruct as a card-like object with character having no npcs
    class CardNoNPCs:
        class Char:
            npcs = None
        character = Char()
    result = get_templates(CardNoNPCs())
    assert result.auto_active == []
    assert result.dormant == []


def test_instantiate():
    """NPC template → IStoryCharacter with merged attributes."""
    npc = FakeNPC("艾莉丝", True, {"race": "elf", "hp": 100})
    char = instantiate(npc, "sess_001")
    assert isinstance(char, IStoryCharacter)
    assert char.name == "艾莉丝"
    assert char.session_id == "sess_001"
    assert char.attributes["race"] == "elf"
    assert char.attributes["hp"] == 100
    assert char.attributes["name"] == "艾莉丝"
    assert char.is_active is True
    assert char.is_alive is True
    assert char.source == "card_definition"


def test_instantiate_no_attributes():
    """NPC with no attributes → name is still added to attributes."""
    npc = FakeNPC("无名", True)
    char = instantiate(npc, "sess_001")
    assert char.attributes == {"name": "无名"}


def test_instantiate_auto_active():
    """Only start_active=True NPCs are instantiated."""
    card = FakeCard([
        FakeNPC("a", True),
        FakeNPC("b", False),
        FakeNPC("c", True),
    ])
    chars = instantiate_auto_active(card, "s1")
    assert len(chars) == 2
    names = {c.name for c in chars}
    assert names == {"a", "c"}


def test_instantiate_auto_active_empty():
    """Empty card → empty list."""
    result = instantiate_auto_active(FakeCard([]), "s1")
    assert result == []


def test_instantiate_auto_active_none():
    """None card → empty list."""
    result = instantiate_auto_active(None, "s1")
    assert result == []


if __name__ == "__main__":
    tests = [
        ("Separate auto-active and dormant", test_get_templates_separates),
        ("Empty NPCs", test_get_templates_empty),
        ("None card", test_get_templates_none_card),
        ("None npcs", test_get_templates_none_npcs),
        ("Instantiate NPC", test_instantiate),
        ("Instantiate no attributes", test_instantiate_no_attributes),
        ("Instantiate auto active", test_instantiate_auto_active),
        ("Instantiate auto empty", test_instantiate_auto_active_empty),
        ("Instantiate auto none", test_instantiate_auto_active_none),
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
