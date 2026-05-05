"""
WorldBookEngine — Keyword-scanning engine for world book entries.

Scans chat history (and optional extra buffers) against world book entries,
manages timing effects (sticky/cooldown/delay), enforces token budgets,
and returns activated entries classified by injection position.
"""

from __future__ import annotations
import random
from typing import Optional

from app.models.worldbook import (
    IWorldBook, IWorldEntry, IWorldBookRuntimeState,
    IWorldBookActivationResult, IAtDepthEntry,
    ESelectiveLogic, EEntryPosition,
)
from app.services.llm_router import estimate_tokens


# ---------------------------------------------------------------
# Keyword matching
# ---------------------------------------------------------------

def _match_keyword(entry: IWorldEntry, text: str, case_sensitive: bool, whole_word: bool) -> bool:
    """Check if any primary key of `entry` appears in `text`."""
    if not entry.keys:
        return False

    if not case_sensitive:
        text = text.lower()

    for key in entry.keys:
        k = key if case_sensitive else key.lower()
        if not k:
            continue
        if whole_word:
            # Simple word-boundary match (surrounded by non-alphanumeric or edges)
            import re
            pattern = r'(?<![a-zA-Z0-9一-鿿])' + re.escape(k) + r'(?![a-zA-Z0-9一-鿿])'
            if re.search(pattern, text):
                return True
        else:
            if k in text:
                return True
    return False


def _match_entry(entry: IWorldEntry, text: str, case_sensitive: bool, whole_word: bool) -> bool:
    """Full keyword matching with primary + secondary keys and selective logic."""
    if not _match_keyword(entry, text, case_sensitive, whole_word):
        return False

    if not entry.keys_secondary:
        return True

    secondary_count = 0
    secondary_total = len(entry.keys_secondary)
    for key in entry.keys_secondary:
        k = key if case_sensitive else key.lower()
        if not k:
            secondary_total -= 1
            continue
        if whole_word:
            import re
            pattern = r'(?<![a-zA-Z0-9一-鿿])' + re.escape(k) + r'(?![a-zA-Z0-9一-鿿])'
            if re.search(pattern, text):
                secondary_count += 1
        else:
            if k in text:
                secondary_count += 1

    secondary_all = (secondary_count == secondary_total > 0)
    secondary_any = (secondary_count >= 1)

    logic = entry.selective_logic
    if logic == ESelectiveLogic.AND_ANY:
        return secondary_any
    elif logic == ESelectiveLogic.AND_ALL:
        return secondary_all
    elif logic == ESelectiveLogic.NOT_ANY:
        return not secondary_any
    elif logic == ESelectiveLogic.NOT_ALL:
        return not secondary_all

    return True


# ---------------------------------------------------------------
# Core scanning
# ---------------------------------------------------------------

def scan(
    worldbooks: list[IWorldBook],
    chat_history_text: str,
    state: Optional[IWorldBookRuntimeState] = None,
    extra_buffers: Optional[dict] = None,
) -> IWorldBookActivationResult:
    """
    Scan all worldbook entries against chat history + extra buffers.

    Returns activated entries classified by position.
    """
    if state is None:
        state = IWorldBookRuntimeState()

    extra_buffers = extra_buffers or {}

    # Build scan buffer
    buffers = [chat_history_text]
    for field in ("persona_desc", "char_desc", "char_personality", "char_scenario"):
        val = extra_buffers.get(field, "")
        if val:
            buffers.append(val)
    scan_text = "\n".join(buffers)

    all_entries: list[IWorldEntry] = []
    for wb in worldbooks:
        for entry in wb.entries:
            all_entries.append(entry)

    # Entry-level properties come from the entry itself; worldbook sets defaults
    # We assume the first worldbook's settings for scan-depth, budgets etc.
    primary_wb = worldbooks[0] if worldbooks else None
    case_sensitive = primary_wb.case_sensitive if primary_wb else False
    whole_word = primary_wb.match_whole_words if primary_wb else False
    token_budget = primary_wb.token_budget if primary_wb else 500

    # Determine scan depth: only scan the last N characters of the buffer
    scan_depth = primary_wb.scan_depth if primary_wb else 100
    if scan_depth and len(scan_text) > scan_depth:
        scan_text = scan_text[-scan_depth:]

    activated: list[IWorldEntry] = []

    for entry in all_entries:
        # Pre-checks
        if not entry.enabled:
            continue
        if entry.delay > state.round_count:
            continue
        if entry.id in state.cooldown_map:
            continue

        # Keyword matching
        entry_case = entry.case_sensitive if entry.case_sensitive is not None else case_sensitive
        entry_whole = entry.match_whole_words if entry.match_whole_words is not None else whole_word

        if not _match_entry(entry, scan_text, entry_case, entry_whole):
            continue

        # Probability check
        if entry.probability < 100:
            if random.randint(1, 100) > entry.probability:
                continue

        # Activated
        activated.append(entry)

        # Sticky: keep activated for N more rounds
        if entry.sticky > 0:
            state.sticky_map[entry.id] = entry.sticky

        # Cooldown: block from activating for N rounds
        if entry.cooldown > 0:
            state.sticky_map.pop(entry.id, None)
            state.cooldown_map[entry.id] = entry.cooldown

    # Add sticky entries from prior rounds (if still active)
    for entry_id, remaining in list(state.sticky_map.items()):
        # Find the entry in the worldbooks
        for wb in worldbooks:
            for e in wb.entries:
                if e.id == entry_id and e not in activated:
                    activated.append(e)
                    break

    # Cascade: constant entries (e.g., world overview) activate all entries
    # from the same worldbook. This ensures that when a worldbook's overview
    # entry is active, all sub-entries are available without requiring each
    # one to individually match keywords.
    activated_ids = {e.id for e in activated}
    entry_to_wb: dict[str, IWorldBook] = {}
    for wb in worldbooks:
        for e in wb.entries:
            entry_to_wb[e.id] = wb
    for entry in list(activated):
        if entry.constant:
            wb = entry_to_wb.get(entry.id)
            if wb:
                for wb_entry in wb.entries:
                    if wb_entry.id not in activated_ids and wb_entry.enabled:
                        activated.append(wb_entry)
                        activated_ids.add(wb_entry.id)

    # Group scoring: same group → keep highest group_weight
    groups: dict[str, list[IWorldEntry]] = {}
    ungrouped: list[IWorldEntry] = []
    for e in activated:
        if e.group:
            groups.setdefault(e.group, []).append(e)
        else:
            ungrouped.append(e)

    scored: list[IWorldEntry] = []
    for group_entries in groups.values():
        best = max(group_entries, key=lambda e: e.group_weight)
        scored.append(best)
    scored.extend(ungrouped)

    # Token budget trimming (highest priority first)
    scored.sort(key=lambda e: -e.priority)
    result: list[IWorldEntry] = []
    remaining_budget = token_budget
    for e in scored:
        cost = estimate_tokens(e.content)
        if cost <= remaining_budget:
            result.append(e)
            remaining_budget -= cost

    trimmed_count = len(scored) - len(result)

    # Recursive scanning (simplified: one extra pass)
    if primary_wb and primary_wb.recursive_scanning:
        max_steps = primary_wb.max_recursion_steps
        for _step in range(min(max_steps, 3)):
            new_content = "\n".join(
                e.content for e in result
                if not e.prevent_recursion
            )
            if not new_content.strip():
                break
            extra_text = scan_text + "\n" + new_content
            new_activated: list[IWorldEntry] = []
            for entry in all_entries:
                if entry in result:
                    continue
                if not entry.enabled:
                    continue
                if entry.exclude_recursion:
                    continue
                entry_case = entry.case_sensitive if entry.case_sensitive is not None else case_sensitive
                entry_whole = entry.match_whole_words if entry.match_whole_words is not None else whole_word
                if _match_entry(entry, extra_text, entry_case, entry_whole):
                    cost = estimate_tokens(entry.content)
                    if cost <= remaining_budget:
                        result.append(entry)
                        remaining_budget -= cost
                        new_activated.append(entry)
            if not new_activated:
                break

    # Classify by position
    def pick(position: EEntryPosition) -> list[IWorldEntry]:
        return [e for e in result if e.position == position]

    at_depth_entries: list[IAtDepthEntry] = [
        IAtDepthEntry(entry=e, depth=e.depth)
        for e in result if e.position == EEntryPosition.AT_DEPTH
    ]

    return IWorldBookActivationResult(
        before_char=pick(EEntryPosition.BEFORE_CHAR),
        after_char=pick(EEntryPosition.AFTER_CHAR),
        at_depth=at_depth_entries,
        examples=pick(EEntryPosition.EXAMPLES),
        an_top=pick(EEntryPosition.AN_TOP),
        an_bottom=pick(EEntryPosition.AN_BOTTOM),
        em_top=pick(EEntryPosition.EM_TOP),
        em_bottom=pick(EEntryPosition.EM_BOTTOM),
        outlet=pick(EEntryPosition.OUTLET),
        updated_state=state,
        trimmed_count=trimmed_count,
    )


# ---------------------------------------------------------------
# State management
# ---------------------------------------------------------------

def update_state(state: IWorldBookRuntimeState) -> IWorldBookRuntimeState:
    """Advance round count and decrement timing effects."""
    state.round_count += 1

    # Decrement sticky counts, remove expired
    expired_sticky = [k for k, v in state.sticky_map.items() if v <= 1]
    for k in expired_sticky:
        del state.sticky_map[k]
    for k in list(state.sticky_map.keys()):
        state.sticky_map[k] -= 1

    # Decrement cooldown counts, remove expired
    expired_cd = [k for k, v in state.cooldown_map.items() if v <= 1]
    for k in expired_cd:
        del state.cooldown_map[k]
    for k in list(state.cooldown_map.keys()):
        state.cooldown_map[k] -= 1

    return state


def reset_state() -> IWorldBookRuntimeState:
    """Create a fresh runtime state for a new session."""
    return IWorldBookRuntimeState(
        sticky_map={},
        cooldown_map={},
        round_count=0,
    )
