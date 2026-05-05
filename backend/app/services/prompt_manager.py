"""
PromptManager — Prompt ordering, filtering, and character-override application.

Sorts prompts by (injection_position, injection_depth, injection_order),
filters by generation_type trigger and enabled status, and applies
character-level overrides (system_prompt → main, jailbreak → jailbreak).
"""

from __future__ import annotations
from typing import Optional

from app.models.preset import IPreset, IPresetPrompt, EGenerationType, EInjectionPosition, ERole
from app.models.runtime import IPromptItem, IPromptCollection


def _default_prompts() -> list[IPresetPrompt]:
    """Return the 14 default system prompts (ST-aligned)."""
    return [
        IPresetPrompt(
            identifier="main", name="Main Prompt", role=ERole.SYSTEM,
            system_prompt=True, marker=True,
            injection_position=EInjectionPosition.RELATIVE,
            injection_depth=4, injection_order=0,
            enabled=True,
        ),
        IPresetPrompt(
            identifier="nsfw", name="Auxiliary Prompt", role=ERole.SYSTEM,
            system_prompt=True, marker=False,
            injection_position=EInjectionPosition.RELATIVE,
            injection_depth=4, injection_order=10,
            enabled=True,
        ),
        IPresetPrompt(
            identifier="dialogueExamples", name="Chat Examples", role=ERole.SYSTEM,
            system_prompt=True, marker=True,
            injection_position=EInjectionPosition.RELATIVE,
            injection_depth=4, injection_order=20,
            enabled=True,
        ),
        IPresetPrompt(
            identifier="jailbreak", name="Post-History Instructions", role=ERole.SYSTEM,
            system_prompt=True, marker=False,
            injection_position=EInjectionPosition.RELATIVE,
            injection_depth=4, injection_order=30,
            enabled=True,
        ),
        IPresetPrompt(
            identifier="chatHistory", name="Chat History", role=ERole.SYSTEM,
            system_prompt=True, marker=True,
            injection_position=EInjectionPosition.RELATIVE,
            injection_depth=4, injection_order=40,
            enabled=True,
        ),
        IPresetPrompt(
            identifier="worldInfoBefore", name="World Info (before)", role=ERole.SYSTEM,
            system_prompt=True, marker=True,
            injection_position=EInjectionPosition.RELATIVE,
            injection_depth=4, injection_order=50,
            enabled=True,
        ),
        IPresetPrompt(
            identifier="worldInfoAfter", name="World Info (after)", role=ERole.SYSTEM,
            system_prompt=True, marker=True,
            injection_position=EInjectionPosition.RELATIVE,
            injection_depth=4, injection_order=60,
            enabled=True,
        ),
        IPresetPrompt(
            identifier="charDescription", name="Char Description", role=ERole.SYSTEM,
            system_prompt=True, marker=True,
            injection_position=EInjectionPosition.RELATIVE,
            injection_depth=4, injection_order=70,
            enabled=True,
        ),
        IPresetPrompt(
            identifier="charPersonality", name="Char Personality", role=ERole.SYSTEM,
            system_prompt=True, marker=True,
            injection_position=EInjectionPosition.RELATIVE,
            injection_depth=4, injection_order=80,
            enabled=True,
        ),
        IPresetPrompt(
            identifier="scenario", name="Scenario", role=ERole.SYSTEM,
            system_prompt=True, marker=True,
            injection_position=EInjectionPosition.RELATIVE,
            injection_depth=4, injection_order=90,
            enabled=True,
        ),
        IPresetPrompt(
            identifier="personaDescription", name="Persona Description", role=ERole.SYSTEM,
            system_prompt=True, marker=True,
            injection_position=EInjectionPosition.RELATIVE,
            injection_depth=4, injection_order=100,
            enabled=True,
        ),
        IPresetPrompt(
            identifier="enhanceDefinitions", name="Enhance Definitions", role=ERole.SYSTEM,
            system_prompt=True, marker=True,
            injection_position=EInjectionPosition.RELATIVE,
            injection_depth=4, injection_order=110,
            enabled=False,
        ),
        IPresetPrompt(
            identifier="summary", name="Summary", role=ERole.SYSTEM,
            system_prompt=True, marker=True,
            injection_position=EInjectionPosition.RELATIVE,
            injection_depth=4, injection_order=120,
            enabled=True,
        ),
        IPresetPrompt(
            identifier="authorsNote", name="Author's Note", role=ERole.SYSTEM,
            system_prompt=True, marker=True,
            injection_position=EInjectionPosition.RELATIVE,
            injection_depth=4, injection_order=130,
            enabled=True,
        ),
    ]


def sort_prompts(prompts: list[IPresetPrompt]) -> list[IPresetPrompt]:
    """
    Sort by (injection_position, injection_depth, injection_order).
    RELATIVE (0) sorts before ABSOLUTE (1).
    """
    return sorted(prompts, key=lambda p: (
        p.injection_position.value,
        p.injection_depth,
        p.injection_order,
    ))


def filter_by_trigger(
    prompts: list[IPresetPrompt],
    generation_type: EGenerationType,
) -> list[IPresetPrompt]:
    """
    Keep prompts where injection_trigger is empty (always-on),
    or matches the current generation_type.
    """
    filtered: list[IPresetPrompt] = []
    for p in prompts:
        triggers = p.injection_trigger
        if not triggers:
            filtered.append(p)
        elif generation_type in triggers:
            filtered.append(p)
    return filtered


def _apply_overrides(
    prompts: list[IPresetPrompt],
    overrides: dict,
) -> list[IPresetPrompt]:
    """Apply character-level overrides to matching prompts."""
    result: list[IPresetPrompt] = []
    for p in prompts:
        if p.identifier == "main" and "system_prompt" in overrides and overrides["system_prompt"]:
            p = p.model_copy(update={"content": overrides["system_prompt"]})
        elif p.identifier == "jailbreak" and "jailbreak" in overrides and overrides["jailbreak"]:
            p = p.model_copy(update={"content": overrides["jailbreak"]})
        result.append(p)
    return result


def _prompt_to_item(p: IPresetPrompt) -> IPromptItem:
    return IPromptItem(
        identifier=p.identifier,
        name=p.name,
        role=p.role,
        content=p.content,
        system_prompt=p.system_prompt,
        marker=p.marker,
        injection_position=p.injection_position,
        injection_depth=p.injection_depth,
        injection_order=p.injection_order,
    )


class PromptOrderInput:
    """Thin input container matching the design spec."""
    def __init__(
        self,
        preset: Optional[IPreset] = None,
        generation_type: EGenerationType = EGenerationType.NORMAL,
        character_overrides: Optional[dict] = None,
    ):
        self.preset = preset
        self.generation_type = generation_type
        self.character_overrides = character_overrides or {}


def get_order(
    preset: Optional[IPreset] = None,
    generation_type: EGenerationType = EGenerationType.NORMAL,
    character_overrides: Optional[dict] = None,
) -> IPromptCollection:
    """
    Return the ordered, filtered prompt collection for a generation request.

    1. Start with the 14 default prompts
    2. Merge in preset prompts (override by identifier, add new)
    3. Filter by generation_type trigger
    4. Drop disabled prompts
    5. Sort by (injection_position, injection_depth, injection_order)
    6. Apply character overrides (system_prompt → main, jailbreak → jailbreak)
    """
    defaults = _default_prompts()

    if preset and preset.prompts:
        preset_map: dict[str, IPresetPrompt] = {}
        for p in preset.prompts:
            preset_map[p.identifier] = p

        merged: list[IPresetPrompt] = []
        seen: set[str] = set()
        for d in defaults:
            if d.identifier in preset_map:
                merged.append(preset_map[d.identifier])
                seen.add(d.identifier)
            else:
                merged.append(d)
                seen.add(d.identifier)

        for ident, p in preset_map.items():
            if ident not in seen:
                merged.append(p)
    else:
        merged = list(defaults)

    # Filter by trigger
    merged = filter_by_trigger(merged, generation_type)

    # Drop disabled
    merged = [p for p in merged if p.enabled]

    # Sort
    merged = sort_prompts(merged)

    # Apply character overrides
    if character_overrides:
        merged = _apply_overrides(merged, character_overrides)

    items = [_prompt_to_item(p) for p in merged]
    return IPromptCollection(prompts=items)
