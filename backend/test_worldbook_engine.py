"""Unit tests for WorldBookEngine."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.worldbook_engine import scan, update_state, reset_state, _match_entry
from app.models.worldbook import (
    IWorldBook, IWorldEntry, IWorldBookRuntimeState,
    ESelectiveLogic, EEntryPosition, EEntryCategory,
)


def _make_wb(name: str, entries: list[IWorldEntry], **kwargs) -> IWorldBook:
    return IWorldBook(
        id=name, name=name,
        entries=entries,
        **kwargs,
    )


def _make_entry(eid: str, keys: list[str], content: str = "", **kwargs) -> IWorldEntry:
    defaults = dict(
        id=eid, category=EEntryCategory.WORLDVIEW,
        keys=keys, content=content,
        enabled=True,
    )
    defaults.update(kwargs)
    return IWorldEntry(**defaults)


def test_single_keyword_match():
    """1 entry, 1 key matched -> activated."""
    entry = _make_entry("e1", ["迷雾森林"], content="迷雾森林的描述")
    wb = _make_wb("test", [entry])
    result = scan([wb], "这片迷雾森林非常神秘")
    assert len(result.before_char) == 1
    assert result.before_char[0].id == "e1"


def test_no_match():
    """No key matched -> empty result."""
    entry = _make_entry("e1", ["巨龙"])
    wb = _make_wb("test", [entry])
    result = scan([wb], "这片迷雾森林非常神秘")
    assert len(result.before_char) == 0


def test_selective_logic_AND_ANY():
    """Secondary keys: AND_ANY -> any secondary match triggers."""
    entry = _make_entry("e1", ["迷雾"], keys_secondary=["魔法", "古老"],
                        selective_logic=ESelectiveLogic.AND_ANY, content="命中")
    wb = _make_wb("test", [entry])
    # "魔法" is in text, so AND_ANY should match
    result = scan([wb], "迷雾森林中魔法涌动")
    assert len(result.before_char) == 1


def test_selective_logic_AND_ALL():
    """Secondary keys: AND_ALL -> all secondaries must match."""
    entry = _make_entry("e1", ["迷雾"], keys_secondary=["魔法", "古老"],
                        selective_logic=ESelectiveLogic.AND_ALL, content="命中")
    wb = _make_wb("test", [entry])
    # Only "魔法" matches, "古老" doesn't
    result = scan([wb], "迷雾森林中魔法涌动")
    assert len(result.before_char) == 0
    # Both match
    result2 = scan([wb], "迷雾森林中古老的魔法涌动")
    assert len(result2.before_char) == 1


def test_selective_logic_NOT_ANY():
    """NOT_ANY: activated only when NO secondary matches."""
    entry = _make_entry("e1", ["迷雾"], keys_secondary=["魔法"],
                        selective_logic=ESelectiveLogic.NOT_ANY, content="命中")
    wb = _make_wb("test", [entry])
    result = scan([wb], "迷雾森林中魔法涌动")
    assert len(result.before_char) == 0  # 魔法 matched, so NOT_ANY fails
    result2 = scan([wb], "迷雾森林中精灵出没")
    assert len(result2.before_char) == 1  # no secondary match, so NOT_ANY passes


def test_selective_logic_NOT_ALL():
    """NOT_ALL: activated when NOT all secondaries match."""
    entry = _make_entry("e1", ["迷雾"], keys_secondary=["魔法", "古老"],
                        selective_logic=ESelectiveLogic.NOT_ALL, content="命中")
    wb = _make_wb("test", [entry])
    result = scan([wb], "迷雾森林中魔法涌动")
    assert len(result.before_char) == 1  # only 魔法, not all -> NOT_ALL passes
    result2 = scan([wb], "迷雾森林中古老的魔法涌动")
    assert len(result2.before_char) == 0  # both match -> NOT_ALL fails


def test_sticky():
    """Entry with sticky stays active for N rounds."""
    entry = _make_entry("e1", ["迷雾"], content="迷雾描述", sticky=3)
    wb = _make_wb("test", [entry])
    state = IWorldBookRuntimeState()
    result = scan([wb], "迷雾森林", state=state)
    # Entry should be in sticky_map
    assert result.updated_state.sticky_map.get("e1") == 3

    # Next round - sticky still active even without keyword match
    state2 = update_state(result.updated_state)
    result2 = scan([wb], "普通对话", state=state2)
    assert any(e.id == "e1" for e in result2.before_char)


def test_cooldown():
    """Entry with cooldown is blocked after activation."""
    entry = _make_entry("e1", ["迷雾"], content="迷雾描述", cooldown=3)
    wb = _make_wb("test", [entry])
    state = IWorldBookRuntimeState()
    result = scan([wb], "迷雾森林", state=state)
    assert "e1" in result.updated_state.cooldown_map

    # Same round re-scan should block
    result2 = scan([wb], "迷雾森林再次", state=result.updated_state)
    assert len(result2.before_char) == 0


def test_delay():
    """Entry with delay not scanned before round threshold."""
    entry = _make_entry("e1", ["迷雾"], content="迷雾描述", delay=5)
    wb = _make_wb("test", [entry])
    state = IWorldBookRuntimeState(round_count=2)
    result = scan([wb], "迷雾森林", state=state)
    assert len(result.before_char) == 0

    state2 = IWorldBookRuntimeState(round_count=10)
    result2 = scan([wb], "迷雾森林", state=state2)
    assert len(result2.before_char) == 1


def test_group_scoring():
    """Same group: only highest group_weight is kept."""
    e1 = _make_entry("e1", ["迷雾"], content="低权重", group="迷雾组", group_weight=1)
    e2 = _make_entry("e2", ["迷雾"], content="高权重", group="迷雾组", group_weight=10)
    wb = _make_wb("test", [e1, e2])
    result = scan([wb], "迷雾森林")
    matched = [e for e in result.before_char if e.group == "迷雾组"]
    assert len(matched) == 1
    assert matched[0].id == "e2"


def test_token_budget():
    """Only entries that fit within token budget are included."""
    long_content = "x" * 5000  # ~2500 tokens
    e1 = _make_entry("e1", ["迷雾"], content="短内容", priority=10)
    e2 = _make_entry("e2", ["迷雾"], content=long_content, priority=5)
    wb = _make_wb("test", [e1, e2], token_budget=50)
    result = scan([wb], "迷雾森林")
    ids = [e.id for e in result.before_char]
    assert "e1" in ids  # short content fits
    assert "e2" not in ids  # long content exceeds budget


def test_position_classification():
    """Verify output is split by entry position."""
    e1 = _make_entry("e1", ["迷雾"], content="before", position=EEntryPosition.BEFORE_CHAR)
    e2 = _make_entry("e2", ["迷雾"], content="after", position=EEntryPosition.AFTER_CHAR)
    e3 = _make_entry("e3", ["迷雾"], content="examples", position=EEntryPosition.EXAMPLES)
    e4 = _make_entry("e4", ["迷雾"], content="at_depth", position=EEntryPosition.AT_DEPTH, depth=2)
    wb = _make_wb("test", [e1, e2, e3, e4])
    result = scan([wb], "迷雾森林")
    assert len(result.before_char) == 1
    assert len(result.after_char) == 1
    assert len(result.examples) == 1
    assert len(result.at_depth) == 1
    assert result.at_depth[0].depth == 2


def test_reset_state():
    """reset_state() returns a fresh state."""
    state = reset_state()
    assert state.round_count == 0
    assert state.sticky_map == {}
    assert state.cooldown_map == {}


def test_case_sensitivity():
    """Worldbook-level case sensitivity should affect matching."""
    entry = _make_entry("e1", ["MistForest"], content="hit")
    # Case sensitive: "mistforest" should NOT match "MistForest"
    wb = _make_wb("test", [entry], case_sensitive=True)
    result = scan([wb], "the mistforest is dark")
    assert len(result.before_char) == 0

    # Case insensitive: should match
    wb2 = _make_wb("test2", [entry], case_sensitive=False)
    result2 = scan([wb2], "the mistforest is dark")
    assert len(result2.before_char) == 1


def test_extra_buffers():
    """Keywords in extra_buffers should also trigger entries."""
    entry = _make_entry("e1", ["精灵王"])
    wb = _make_wb("test", [entry])
    # Keyword only in persona_desc, not in chat
    result = scan([wb], "普通对话", extra_buffers={"persona_desc": "我是精灵王的使者"})
    assert len(result.before_char) == 1


def test_scan_depth():
    """Only the last N characters of the buffer should be scanned."""
    entry = _make_entry("e1", ["开头"])
    wb = _make_wb("test", [entry], scan_depth=50)
    long_history = "开头" + "x" * 200  # "开头" at the beginning, outside scan_depth=50 window
    result = scan([wb], long_history)
    assert len(result.before_char) == 0

    # Put keyword at the end (within scan_depth)
    result2 = scan([wb], "x" * 10 + "开头")
    assert len(result2.before_char) == 1


def test_disabled_entry():
    """Disabled entries should never activate."""
    entry = _make_entry("e1", ["迷雾"], enabled=False)
    wb = _make_wb("test", [entry])
    result = scan([wb], "迷雾森林")
    assert len(result.before_char) == 0


if __name__ == "__main__":
    tests = [
        ("Single keyword match", test_single_keyword_match),
        ("No match", test_no_match),
        ("Selective logic AND_ANY", test_selective_logic_AND_ANY),
        ("Selective logic AND_ALL", test_selective_logic_AND_ALL),
        ("Selective logic NOT_ANY", test_selective_logic_NOT_ANY),
        ("Selective logic NOT_ALL", test_selective_logic_NOT_ALL),
        ("Sticky", test_sticky),
        ("Cooldown", test_cooldown),
        ("Delay", test_delay),
        ("Group scoring", test_group_scoring),
        ("Token budget", test_token_budget),
        ("Position classification", test_position_classification),
        ("Reset state", test_reset_state),
        ("Case sensitivity", test_case_sensitivity),
        ("Extra buffers", test_extra_buffers),
        ("Scan depth", test_scan_depth),
        ("Disabled entry", test_disabled_entry),
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
