"""
SillyTavern data format importer.

Converts ST V3 character cards, world books, and presets to our internal
Pydantic models (ICharacterCard, IWorldBook, IPreset).

Compatibility notes:
- ST character cards have no npcs field; we keep npcs empty — story
  characters are registered at runtime via character tools/skills.
- ST world books store entries as a dict (keyed by numeric uid strings);
  we convert to a flat list.
- ST presets embed context_config / instruct_config fields at the top level;
  we extract them into the respective sub-objects.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from app.db.database import generate_id
from app.models.card import (
    ICharacterCard, ICharacterDefinition, ICoverInfo, IAvatarInfo,
    IPresetConfig, IImageConfig, IDepthPrompt,
    ECoverSource, ECardStatus, EAspectRatio, EImageService, ERole,
    IAuthorsNoteConfig, EANPosition,
)
from app.models.preset import (
    IPreset, IPresetPrompt,
    ENameBehavior, EInjectionPosition, EGenerationType,
    IContextConfig, IInstructConfig, EContextPosition, EInstructNameBehavior,
)
from app.models.worldbook import (
    IWorldBook, IWorldEntry,
    EInsertionStrategy, EEntryCategory, EEntrySource, EEntryPosition,
    ESelectiveLogic,
)


# ============================================================
# Position enum mappings
# ============================================================

ST_POSITION_MAP: dict[int, EEntryPosition] = {
    0: EEntryPosition.BEFORE_CHAR,
    1: EEntryPosition.AFTER_CHAR,
    2: EEntryPosition.AN_TOP,
    3: EEntryPosition.AN_BOTTOM,
    4: EEntryPosition.AT_DEPTH,
    5: EEntryPosition.EXAMPLES,
    6: EEntryPosition.EM_TOP,
    7: EEntryPosition.EM_BOTTOM,
    8: EEntryPosition.OUTLET,
}

ST_SELECTIVE_LOGIC_MAP: dict[int, ESelectiveLogic] = {
    0: ESelectiveLogic.AND_ANY,
    1: ESelectiveLogic.AND_ALL,
    2: ESelectiveLogic.NOT_ANY,
    3: ESelectiveLogic.NOT_ALL,
}

ST_NAMES_BEHAVIOR_MAP: dict[int, ENameBehavior] = {
    0: ENameBehavior.NONE,
    1: ENameBehavior.DEFAULT,
    2: ENameBehavior.CONTENT,
    3: ENameBehavior.COMPLETION,
}

ST_INSTRUCT_NAMES_MAP: dict[int, EInstructNameBehavior] = {
    0: EInstructNameBehavior.NONE,
    1: EInstructNameBehavior.FORCE,
    2: EInstructNameBehavior.ALWAYS,
}


# ============================================================
# World Book importer
# ============================================================

def import_worldbook(st_json: dict[str, Any], name: str = "", description: str = "") -> IWorldBook:
    """
    Convert a SillyTavern world book JSON dict to our IWorldBook model.

    Args:
        st_json: The raw ST world book JSON. Must have an 'entries' key
                 containing a dict of {str_idx: entry_obj}.
        name: Display name for the world book (ST files lack top-level names).
        description: Optional description.

    Returns:
        IWorldBook instance ready for storage.
    """
    raw_entries: dict[str, dict[str, Any]] | list[dict[str, Any]] = st_json.get("entries", {})

    entries: list[IWorldEntry] = []
    if isinstance(raw_entries, list):
        for raw in raw_entries:
            entry = _convert_world_entry(raw)
            entries.append(entry)
    else:
        for idx_str, raw in raw_entries.items():
            entry = _convert_world_entry(raw)
            entries.append(entry)

    wb = IWorldBook(
        id=generate_id(),
        name=name or "Imported World Book",
        description=description,
        entries=entries,
        scan_depth=100,
        token_budget=500,
        recursive_scanning=False,
        case_sensitive=False,
        match_whole_words=False,
        insertion_strategy=EInsertionStrategy.EVENLY,
        created_at="",
        updated_at="",
    )
    return wb


def _convert_world_entry(raw: dict[str, Any]) -> IWorldEntry:
    st_pos: int = raw.get("position", 0)
    st_logic: int = raw.get("selectiveLogic", 0)
    role_raw = raw.get("role")

    return IWorldEntry(
        id=str(raw.get("uid", generate_id())),
        category=EEntryCategory.WORLDVIEW,
        title=raw.get("comment", "") or "",
        comment=raw.get("comment", "") or "",
        keys=raw.get("key", []) or [],
        keys_secondary=raw.get("keysecondary", []) or [],
        selective_logic=ST_SELECTIVE_LOGIC_MAP.get(st_logic, ESelectiveLogic.AND_ANY),
        content=raw.get("content", "") or "",
        source=EEntrySource.ORIGINAL,
        enabled=not raw.get("disable", False),
        constant=raw.get("constant", False),
        priority=raw.get("order", 100),
        insertion_order=raw.get("displayIndex", 0),
        position=ST_POSITION_MAP.get(st_pos, EEntryPosition.BEFORE_CHAR),
        depth=raw.get("depth", 4),
        role=ERole(role_raw) if role_raw else ERole.SYSTEM,
        scan_depth=raw.get("scanDepth"),
        case_sensitive=raw.get("caseSensitive"),
        match_whole_words=raw.get("matchWholeWords"),
        probability=raw.get("probability", 100),
        sticky=raw.get("sticky", 0),
        cooldown=raw.get("cooldown", 0),
        delay=raw.get("delay", 0),
        group=raw.get("group", "") or "",
        group_weight=raw.get("groupWeight", 100),
        prevent_recursion=raw.get("preventRecursion", False),
        exclude_recursion=raw.get("excludeRecursion", False),
        delay_until_recursion=raw.get("delayUntilRecursion", False),
        vectorized=raw.get("vectorized", False),
        created_at="",
        updated_at="",
    )


# ============================================================
# Preset importer
# ============================================================

def import_preset(st_json: dict[str, Any], name: str = "") -> IPreset:
    """
    Convert a SillyTavern preset JSON dict to our IPreset model.

    ST presets are full settings files. We extract the fields relevant to our
    IPreset model and drop ST-specific extras (top_a, min_p, repetition_penalty,
    send_if_empty, impersonation_prompt, etc.).

    Args:
        st_json: Raw ST settings/preset JSON.
        name: Override name (defaults to "imported-{timestamp}").

    Returns:
        IPreset instance.
    """
    prompts: list[IPresetPrompt] = []
    for raw_prompt in st_json.get("prompts", []):
        prompts.append(_convert_preset_prompt(raw_prompt))

    nb_raw = st_json.get("names_behavior", 1)
    names_behavior = ST_NAMES_BEHAVIOR_MAP.get(nb_raw, ENameBehavior.DEFAULT)

    context_config = _extract_context_config(st_json)
    instruct_config = _extract_instruct_config(st_json)

    return IPreset(
        name=name or "imported-preset",
        temperature=st_json.get("temperature", 0.8),
        frequency_penalty=st_json.get("frequency_penalty", 0.3),
        presence_penalty=st_json.get("presence_penalty", 0.2),
        top_p=st_json.get("top_p", 0.95),
        top_k=st_json.get("top_k", 40),
        max_context=st_json.get("openai_max_context", 4096),
        max_tokens=st_json.get("openai_max_tokens", 2048),
        names_behavior=names_behavior,
        wi_format=st_json.get("wi_format", "{0}"),
        scenario_format=st_json.get("scenario_format", "[Circumstances: {{scenario}}]"),
        personality_format=st_json.get("personality_format", "[{{char}}'s personality: {{personality}}]"),
        prompts=prompts,
        context_config=context_config,
        instruct_config=instruct_config,
    )


def _convert_preset_prompt(raw: dict[str, Any]) -> IPresetPrompt:
    role_raw = raw.get("role", "system")
    return IPresetPrompt(
        identifier=raw.get("identifier", generate_id()),
        name=raw.get("name", ""),
        enabled=raw.get("enabled", True),
        role=ERole(role_raw) if role_raw else ERole.SYSTEM,
        content=raw.get("content", ""),
        system_prompt=raw.get("system_prompt", False),
        marker=raw.get("marker", False),
        injection_position=EInjectionPosition(raw.get("injection_position", 0)),
        injection_depth=raw.get("injection_depth", 4),
        injection_order=raw.get("injection_order", 100),
        forbid_overrides=raw.get("forbid_overrides", False),
        injection_trigger=[EGenerationType(t) for t in raw.get("injection_trigger", [])],
        extension=raw.get("extension"),
    )


def _extract_context_config(st: dict[str, Any]) -> IContextConfig:
    """Extract ContextConfig from ST top-level fields."""
    return IContextConfig(
        story_string=st.get("context_template", ""),
        chat_start=st.get("chat_start", ""),
        example_separator=st.get("example_separator", "<START>"),
        position=EContextPosition.IN_PROMPT,
        role=ERole.SYSTEM,
        depth=0,
        use_stop_strings=st.get("use_stop_strings", False),
        names_as_stop_strings=st.get("names_as_stop_strings", False),
    )


def _extract_instruct_config(st: dict[str, Any]) -> IInstructConfig | None:
    """Extract InstructConfig from ST top-level fields. Returns None if instruct mode is off."""
    if not st.get("instruct_enabled"):
        return None

    nib = st.get("instruct_names_behavior", 0)
    return IInstructConfig(
        enabled=True,
        preset=st.get("instruct_preset", "default"),
        input_sequence=st.get("input_sequence", ""),
        input_suffix=st.get("input_suffix", ""),
        output_sequence=st.get("output_sequence", ""),
        output_suffix=st.get("output_suffix", ""),
        system_sequence=st.get("system_sequence", ""),
        system_suffix=st.get("system_suffix", ""),
        last_system_sequence=st.get("last_system_sequence", ""),
        first_output_sequence=st.get("first_output_sequence", ""),
        last_output_sequence=st.get("last_output_sequence", ""),
        first_input_sequence=st.get("first_input_sequence", ""),
        last_input_sequence=st.get("last_input_sequence", ""),
        stop_sequence=st.get("stop_sequence", ""),
        wrap=st.get("wrap", True),
        macro=st.get("macro", True),
        system_same_as_user=st.get("system_same_as_user", False),
        skip_examples=st.get("skip_examples", False),
        names_behavior=ST_INSTRUCT_NAMES_MAP.get(nib, EInstructNameBehavior.NONE),
        sequences_as_stop_strings=st.get("sequences_as_stop_strings", False),
        story_string_prefix=st.get("story_string_prefix", ""),
        story_string_suffix=st.get("story_string_suffix", ""),
        activation_regex=st.get("activation_regex", ""),
        bind_to_context=st.get("bind_to_context", True),
        user_alignment_message=st.get("user_alignment_message", ""),
    )


# ============================================================
# Character Card importer (ST V3)
# ============================================================

def import_character_card(
    st_json: dict[str, Any],
    worldbook_id: str | None = None,
) -> ICharacterCard:
    """
    Convert a SillyTavern V3 character card JSON to our ICharacterCard.

    ST cards have no explicit npcs field, so npcs defaults to empty.
    Story characters are created at runtime via character tools / skills
    rather than pre-populated from the imported card.

    Args:
        st_json: Raw ST V3 character card. Top-level or with 'data' wrapper.
        worldbook_id: If the card embeds a character_book, the ID of the
                      extracted world book to link.

    Returns:
        ICharacterCard instance.
    """
    data = st_json.get("data", st_json)
    char_name = data.get("name", "Unknown")

    extensions = data.get("extensions", {}) or {}
    depth_raw = extensions.get("depth_prompt")

    char_def = ICharacterDefinition(
        name=char_name,
        description=data.get("description", ""),
        personality=data.get("personality", ""),
        scenario=data.get("scenario", ""),
        speaking_style="",
        background="",
        first_mes=data.get("first_mes", ""),
        alternate_greetings=data.get("alternate_greetings", []),
        mes_example=data.get("mes_example", ""),
        creator_notes=data.get("creator_notes", ""),
        npcs=[],
    )

    card_id = generate_id()

    return ICharacterCard(
        id=card_id,
        name=char_name,
        description=data.get("description", "")[:200],
        tags=data.get("tags", []),
        spec=data.get("spec", "chara_card_v3"),
        spec_version=data.get("spec_version", "3.0"),
        extensions=extensions,
        cover=ICoverInfo(image_path="", source=ECoverSource.UPLOAD),
        avatar=IAvatarInfo(image_path="", source=ECoverSource.UPLOAD),
        character=char_def,
        system_prompt=data.get("system_prompt"),
        post_history_instructions=data.get("post_history_instructions"),
        depth_prompt=IDepthPrompt(**depth_raw) if depth_raw else None,
        worldbook_ids=[worldbook_id] if worldbook_id else [],
        preset_name=None,
        preset_config=IPresetConfig(),
        image_config=IImageConfig(),
        status=ECardStatus.PUBLISHED,
        version=1,
    )
