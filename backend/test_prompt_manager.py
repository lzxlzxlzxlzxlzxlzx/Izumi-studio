"""Unit tests for PromptManager."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.prompt_manager import (
    get_order, sort_prompts, filter_by_trigger, _default_prompts,
)
from app.models.preset import IPreset, IPresetPrompt, EGenerationType, EInjectionPosition, ERole
from app.models.runtime import IPromptCollection, IPromptItem


def test_default_order():
    """Verify 14 default prompts are sorted correctly."""
    coll = get_order()
    identifiers = [p.identifier for p in coll.prompts]
    # enhanceDefinitions is disabled by default, so 13 enabled
    assert len(coll.prompts) == 13, f"Expected 13 enabled prompts, got {len(coll.prompts)}"
    assert "enhanceDefinitions" not in identifiers
    # Verify ordering: main should be first
    assert identifiers[0] == "main", f"First should be main, got {identifiers[0]}"


def test_disabled_skipped():
    """enhanceDefinitions (enabled=False) should be excluded."""
    coll = get_order()
    ids = [p.identifier for p in coll.prompts]
    assert "enhanceDefinitions" not in ids


def test_trigger_filter():
    """Prompts with trigger restrictions should be excluded when type doesn't match."""
    # Create a preset with a trigger-restricted prompt
    preset = IPreset(
        name="test",
        prompts=[
            IPresetPrompt(
                identifier="custom_continue_only",
                name="Custom Continue",
                role=ERole.SYSTEM,
                content="Only on continue",
                injection_position=EInjectionPosition.RELATIVE,
                injection_depth=4,
                injection_order=5,
                enabled=True,
                injection_trigger=[EGenerationType.CONTINUE],
            ),
        ],
    )
    # NORMAL type should exclude the continue-only prompt
    coll = get_order(preset=preset, generation_type=EGenerationType.NORMAL)
    ids = [p.identifier for p in coll.prompts]
    assert "custom_continue_only" not in ids, f"Should exclude continue-only, got {ids}"

    # CONTINUE type should include it
    coll2 = get_order(preset=preset, generation_type=EGenerationType.CONTINUE)
    ids2 = [p.identifier for p in coll2.prompts]
    assert "custom_continue_only" in ids2, f"Should include continue-only, got {ids2}"


def test_character_override():
    """Character overrides should replace main and jailbreak content."""
    coll = get_order(
        character_overrides={
            "system_prompt": "CUSTOM SYSTEM PROMPT",
            "jailbreak": "CUSTOM JAILBREAK",
        },
    )
    main = next(p for p in coll.prompts if p.identifier == "main")
    jb = next(p for p in coll.prompts if p.identifier == "jailbreak")
    assert main.content == "CUSTOM SYSTEM PROMPT"
    assert jb.content == "CUSTOM JAILBREAK"


def test_sort_by_position_depth_order():
    """Custom injection parameters should affect sort order."""
    # Two prompts with the same position but different depth/order
    p1 = IPresetPrompt(
        identifier="early", name="Early",
        injection_position=EInjectionPosition.RELATIVE,
        injection_depth=2, injection_order=5, enabled=True,
    )
    p2 = IPresetPrompt(
        identifier="late", name="Late",
        injection_position=EInjectionPosition.RELATIVE,
        injection_depth=4, injection_order=1, enabled=True,
    )
    sorted_prompts = sort_prompts([p2, p1])
    assert sorted_prompts[0].identifier == "early"
    assert sorted_prompts[1].identifier == "late"


def test_preset_overrides_existing():
    """Preset should override default prompt content."""
    preset = IPreset(
        name="custom",
        prompts=[
            IPresetPrompt(
                identifier="nsfw",
                name="NSFW Override",
                role=ERole.SYSTEM,
                content="Custom NSFW content",
                injection_position=EInjectionPosition.RELATIVE,
                injection_depth=4,
                injection_order=10,
                enabled=True,
            ),
        ],
    )
    coll = get_order(preset=preset)
    nsfw = next(p for p in coll.prompts if p.identifier == "nsfw")
    assert nsfw.content == "Custom NSFW content"
    assert nsfw.name == "NSFW Override"


def test_preset_adds_new_prompt():
    """Preset can add prompts not in defaults."""
    preset = IPreset(
        name="custom",
        prompts=[
            IPresetPrompt(
                identifier="my_custom_prompt",
                name="My Custom",
                role=ERole.SYSTEM,
                content="Hello world",
                injection_position=EInjectionPosition.RELATIVE,
                injection_depth=3,
                injection_order=15,
                enabled=True,
            ),
        ],
    )
    coll = get_order(preset=preset)
    ids = [p.identifier for p in coll.prompts]
    assert "my_custom_prompt" in ids


def test_absolute_before_relative():
    """ABSOLUTE position should sort after RELATIVE."""
    p_rel = IPresetPrompt(
        identifier="rel", injection_position=EInjectionPosition.RELATIVE,
        injection_depth=0, injection_order=999, enabled=True,
    )
    p_abs = IPresetPrompt(
        identifier="abs", injection_position=EInjectionPosition.ABSOLUTE,
        injection_depth=0, injection_order=1, enabled=True,
    )
    sorted_prompts = sort_prompts([p_abs, p_rel])
    assert sorted_prompts[0].identifier == "rel"
    assert sorted_prompts[1].identifier == "abs"


def test_no_trigger_always_included():
    """Prompts with empty injection_trigger should always be included."""
    preset = IPreset(
        name="test",
        prompts=[
            IPresetPrompt(
                identifier="always_on",
                name="Always",
                enabled=True,
                injection_position=EInjectionPosition.RELATIVE,
                injection_depth=4,
                injection_order=5,
                injection_trigger=[],  # empty = match all
            ),
        ],
    )
    for gt in EGenerationType:
        coll = get_order(preset=preset, generation_type=gt)
        ids = [p.identifier for p in coll.prompts]
        assert "always_on" in ids, f"Should be included for {gt}"


def test_all_prompts_are_ipromptitem():
    """Output collection items must be IPromptItem instances."""
    coll = get_order()
    for p in coll.prompts:
        assert isinstance(p, IPromptItem), f"Expected IPromptItem, got {type(p)}"
        assert isinstance(p.identifier, str)
        assert p.identifier  # non-empty


if __name__ == "__main__":
    tests = [
        ("Default order (13 enabled)", test_default_order),
        ("Disabled skipped", test_disabled_skipped),
        ("Trigger filter", test_trigger_filter),
        ("Character override", test_character_override),
        ("Sort by position/depth/order", test_sort_by_position_depth_order),
        ("Preset overrides existing", test_preset_overrides_existing),
        ("Preset adds new prompt", test_preset_adds_new_prompt),
        ("ABSOLUTE after RELATIVE", test_absolute_before_relative),
        ("No trigger always included", test_no_trigger_always_included),
        ("All output are IPromptItem", test_all_prompts_are_ipromptitem),
    ]

    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {name}: {e}")

    print(f"\n{passed}/{len(tests)} tests passed")
