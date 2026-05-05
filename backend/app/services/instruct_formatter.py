"""
InstructFormatter — Wrap messages in instruction template sequences.

When enabled, messages are wrapped with configured prefix/suffix pairs
(e.g., <|user|>\n...\n<|assistant|>\n...). When disabled, falls back to
simple "name: content" format.
"""

from __future__ import annotations
from typing import Optional

from app.models.preset import (
    IInstructConfig, EInstructNameBehavior, ERole,
)


def _substitute_name(content: str, name: str, config: IInstructConfig) -> str:
    """Apply name wrapping according to config.names_behavior."""
    if config.names_behavior == EInstructNameBehavior.NONE:
        return content
    if config.names_behavior == EInstructNameBehavior.CONTENT:
        return f"{name}: {content}"
    if config.names_behavior == EInstructNameBehavior.COMPLETION:
        # Completion mode: starts with name, content follows
        if content.startswith(name):
            return content
        return f"{name}: {content}"
    # DEFAULT — no wrapping in instruct mode
    return content


def _simple_format(content: str, name: str) -> str:
    """Fallback format when instruct is disabled: 'name: content'."""
    return f"{name}: {content}"


# ---------------------------------------------------------------
# Public API
# ---------------------------------------------------------------

def format_message(
    content: str,
    role: str,
    config: IInstructConfig,
    name_user: str = "user",
    name_char: str = "assistant",
    is_first_user: bool = False,
    is_last_user: bool = False,
    is_first_output: bool = False,
    is_last_output: bool = False,
) -> str:
    """
    Wrap a single message with instruct sequences.

    Args:
        content: The message text
        role: 'system' | 'user' | 'assistant'
        config: Instruction template configuration
        name_user: User's display name
        name_char: Character's display name
        is_first_user: This is the first user input
        is_last_user: This is the last user input
        is_first_output: This is the first assistant output
        is_last_output: This is the last assistant output

    Returns:
        Formatted message string
    """
    if not config.enabled:
        name = name_user if role == ERole.USER else name_char
        return _simple_format(content, name)

    name = name_user if role == ERole.USER else name_char

    if role == ERole.SYSTEM:
        prefix = getattr(config, "system_sequence", "") or ""
        suffix = getattr(config, "system_suffix", "") or ""
        return prefix + content + suffix

    elif role == ERole.USER:
        prefix = ""
        if is_first_user and getattr(config, "first_input_sequence", ""):
            prefix = config.first_input_sequence
        elif is_last_user and getattr(config, "last_input_sequence", ""):
            prefix = config.last_input_sequence
        else:
            prefix = getattr(config, "input_sequence", "") or ""

        if config.wrap:
            content = _substitute_name(content, name, config)
        return prefix + content + (getattr(config, "input_suffix", "") or "")

    elif role == ERole.ASSISTANT:
        prefix = ""
        if is_first_output and getattr(config, "first_output_sequence", ""):
            prefix = config.first_output_sequence
        elif is_last_output and getattr(config, "last_output_sequence", ""):
            prefix = config.last_output_sequence
        else:
            prefix = getattr(config, "output_sequence", "") or ""

        if config.wrap:
            content = _substitute_name(content, name, config)
        return prefix + content + (getattr(config, "output_suffix", "") or "")

    # Fallback
    return content


def format_story_string(rendered_story: str, config: IInstructConfig) -> str:
    """Wrap the rendered story string with prefix/suffix."""
    if not config.enabled:
        return rendered_story

    prefix = getattr(config, "story_string_prefix", "") or ""
    suffix = getattr(config, "story_string_suffix", "") or ""
    return prefix + rendered_story + suffix


def get_stop_sequences(config: IInstructConfig) -> list[str]:
    """Collect all configured sequences that should act as stop tokens."""
    stops: list[str] = []
    candidates = [
        config.input_sequence,
        config.output_sequence,
        config.system_sequence,
        config.input_suffix,
        config.output_suffix,
        config.stop_sequence,
    ]
    for s in candidates:
        s = (s or "").strip()
        if s and s not in stops:
            stops.append(s)

    if config.sequences_as_stop_strings:
        extra = [
            config.first_input_sequence,
            config.last_input_sequence,
            config.first_output_sequence,
            config.last_output_sequence,
        ]
        for s in extra:
            s = (s or "").strip()
            if s and s not in stops:
                stops.append(s)

    return stops
