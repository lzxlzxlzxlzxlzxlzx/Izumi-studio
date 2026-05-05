"""
CharacterTemplateManager — NPC template management and instantiation.

Extracts NPC templates from character cards, separates them into
auto-active (start_active=True) and dormant groups, and provides
instantiation helpers for creating runtime IStoryCharacter instances.
"""

from __future__ import annotations
from datetime import datetime
import uuid

from app.models.character import IStoryCharacter, ICharacterImage


class ICharacterTemplates:
    """Output container for get_templates()."""
    def __init__(
        self,
        auto_active: list[IStoryCharacter],
        dormant: list[object],  # list[INPC]
    ):
        self.auto_active = auto_active
        self.dormant = dormant


def get_templates(card) -> ICharacterTemplates:
    """
    Separate NPC templates into auto-active and dormant groups.

    Args:
        card: ICharacterCard instance

    Returns:
        ICharacterTemplates with auto_active and dormant lists
    """
    auto_active: list[IStoryCharacter] = []
    dormant: list[object] = []

    if not card or not card.character or not card.character.npcs:
        return ICharacterTemplates(auto_active=[], dormant=[])

    for npc in card.character.npcs:
        if npc.start_active:
            auto_active.append(npc)
        else:
            dormant.append(npc)

    return ICharacterTemplates(auto_active=auto_active, dormant=dormant)


def instantiate(npc, session_id: str) -> IStoryCharacter:
    """
    Convert a single NPC template into a runtime IStoryCharacter.

    Args:
        npc: INPC template from a character card
        session_id: Session to bind the character to

    Returns:
        IStoryCharacter with generated id and merged attributes
    """
    now = datetime.now().isoformat()
    attrs = dict(npc.attributes) if npc.attributes else {}
    attrs["name"] = npc.name

    return IStoryCharacter(
        id=str(uuid.uuid4()),
        session_id=session_id,
        name=npc.name,
        attributes=attrs,
        is_active=True,
        is_alive=True,
        first_seen_round=0,
        last_seen_round=0,
        source="card_definition",
        images=[],
        created_at=now,
        updated_at=now,
    )


def instantiate_auto_active(card, session_id: str) -> list[IStoryCharacter]:
    """
    Batch-instantiate all NPCs with start_active=True from the card.

    Args:
        card: ICharacterCard instance
        session_id: Session to bind characters to

    Returns:
        List of IStoryCharacter for all auto-active NPCs
    """
    if not card or not card.character or not card.character.npcs:
        return []

    result: list[IStoryCharacter] = []
    for npc in card.character.npcs:
        if npc.start_active:
            result.append(instantiate(npc, session_id))
    return result
