"""Unit tests for InstructFormatter."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.instruct_formatter import (
    format_message, format_story_string, get_stop_sequences,
)
from app.models.preset import IInstructConfig, ERole


def _make_config(**kwargs) -> IInstructConfig:
    defaults = dict(
        enabled=True,
        input_sequence="<|user|>\n",
        input_suffix="\n",
        output_sequence="<|assistant|>\n",
        output_suffix="\n",
        system_sequence="<|system|>\n",
        system_suffix="\n",
        first_input_sequence="",
        last_input_sequence="",
        first_output_sequence="<|assistant|>\n",
        last_output_sequence="",
        stop_sequence="<|stop|>",
        wrap=True,
    )
    defaults.update(kwargs)
    return IInstructConfig(**defaults)


def test_format_user_message():
    """User message wrapped with input_sequence + suffix."""
    config = _make_config()
    result = format_message("Hello", ERole.USER, config)
    assert result == "<|user|>\nHello\n"


def test_format_user_message_no_wrap():
    """With wrap=False, user content is not name-wrapped."""
    config = _make_config(wrap=False)
    result = format_message("Hello", ERole.USER, config, name_user="bob")
    assert result == "<|user|>\nHello\n"


def test_format_first_user():
    """First user message uses first_input_sequence."""
    config = _make_config(first_input_sequence="<|first_user|>\n")
    result = format_message("Start", ERole.USER, config, is_first_user=True)
    assert result == "<|first_user|>\nStart\n"


def test_format_last_user():
    """Last user message uses last_input_sequence."""
    config = _make_config(last_input_sequence="<|last_user|>\n")
    result = format_message("Bye", ERole.USER, config, is_last_user=True)
    assert result == "<|last_user|>\nBye\n"


def test_format_assistant():
    """Assistant message wrapped with output_sequence + suffix."""
    config = _make_config()
    result = format_message("Hi there", ERole.ASSISTANT, config)
    assert result == "<|assistant|>\nHi there\n"


def test_format_first_output():
    """First output uses first_output_sequence."""
    config = _make_config(first_output_sequence="<|first_output|>\n")
    result = format_message("First", ERole.ASSISTANT, config, is_first_output=True)
    assert result == "<|first_output|>\nFirst\n"


def test_format_last_output():
    """Last output uses last_output_sequence."""
    config = _make_config(last_output_sequence="<|last_output|>\n")
    result = format_message("Last", ERole.ASSISTANT, config, is_last_output=True)
    assert result == "<|last_output|>\nLast\n"


def test_format_system():
    """System message wrapped with system_sequence + suffix."""
    config = _make_config(system_sequence="<|system|>\n")
    result = format_message("Instructions", ERole.SYSTEM, config)
    assert result == "<|system|>\nInstructions\n"


def test_format_disabled():
    """When disabled, returns 'name: content'."""
    config = _make_config(enabled=False)
    result = format_message("Hello", ERole.USER, config, name_user="bob")
    assert result == "bob: Hello"

    result2 = format_message("Hi", ERole.ASSISTANT, config, name_char="alice")
    assert result2 == "alice: Hi"


def test_stop_sequences():
    """All configured stop strings are collected."""
    config = _make_config(
        input_sequence="[INST]",
        output_sequence="[/INST]",
        stop_sequence="</s>",
    )
    stops = get_stop_sequences(config)
    assert "[INST]" in stops
    assert "[/INST]" in stops
    assert "</s>" in stops


def test_stop_sequences_with_extra():
    """When sequences_as_stop_strings=True, first/last sequences included."""
    config = _make_config(
        input_sequence="[INST]",
        first_input_sequence="[FIRST_INST]",
        last_output_sequence="[LAST]",
        sequences_as_stop_strings=True,
    )
    stops = get_stop_sequences(config)
    assert "[FIRST_INST]" in stops
    assert "[LAST]" in stops


def test_format_story_string():
    """Story string wrapped with prefix/suffix."""
    config = _make_config(
        story_string_prefix="<|story|>\n",
        story_string_suffix="\n<|/story|>",
    )
    result = format_story_string("Once upon a time...", config)
    assert result == "<|story|>\nOnce upon a time...\n<|/story|>"


def test_format_story_string_disabled():
    """When disabled, story string is returned as-is."""
    config = _make_config(enabled=False)
    result = format_story_string("Raw story", config)
    assert result == "Raw story"


def test_empty_sequences():
    """Empty sequences produce clean output without extra spaces."""
    config = _make_config(
        input_sequence="",
        input_suffix="",
        output_sequence="",
        output_suffix="",
        system_sequence="",
        system_suffix="",
        wrap=False,
    )
    result = format_message("Hello", ERole.USER, config)
    assert result == "Hello"


if __name__ == "__main__":
    tests = [
        ("Format user message", test_format_user_message),
        ("Format user no wrap", test_format_user_message_no_wrap),
        ("Format first user", test_format_first_user),
        ("Format last user", test_format_last_user),
        ("Format assistant", test_format_assistant),
        ("Format first output", test_format_first_output),
        ("Format last output", test_format_last_output),
        ("Format system", test_format_system),
        ("Format disabled (simple)", test_format_disabled),
        ("Stop sequences", test_stop_sequences),
        ("Stop sequences with extras", test_stop_sequences_with_extra),
        ("Format story string", test_format_story_string),
        ("Story string disabled", test_format_story_string_disabled),
        ("Empty sequences", test_empty_sequences),
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
