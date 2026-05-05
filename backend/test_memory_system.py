"""Unit tests for MemorySystem."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import patch, MagicMock
from app.models.memory import IMemorySummary, IMemoryOutput, IMemoryConfig


class FakeMessage:
    def __init__(self, role, content, round_index, name=""):
        self.role = role
        self.content = content
        self.round_index = round_index
        self.name = name or role


def make_history(num_rounds: int, msgs_per_round: int = 2):
    """Build a fake chat history with `num_rounds` rounds."""
    msgs = []
    for r in range(num_rounds):
        msgs.append(FakeMessage("user", f"用户消息{r}", r))
        msgs.append(FakeMessage("assistant", f"角色回复{r}", r))
    return msgs


def test_get_short_term():
    """20 rounds, short_term_rounds=5 -> returns only last 5 rounds of messages."""
    history = make_history(20)
    config = IMemoryConfig(short_term_rounds=5)

    with patch("app.services.memory_system.get_summaries", return_value=[]):
        from app.services.memory_system import get
        output = get("session1", history, config)

    round_indices = {getattr(m, "round_index", 0) for m in output.short_term}
    # Rounds 15-19 should be in short_term (threshold is max_round - 5 = 19 - 5 = 14)
    assert 15 in round_indices
    assert 19 in round_indices
    assert 0 not in round_indices  # old rounds excluded


def test_get_no_summaries():
    """New session with no summaries -> empty summaries list."""
    history = make_history(5)
    with patch("app.services.memory_system.get_summaries", return_value=[]):
        from app.services.memory_system import get
        output = get("session1", history)
    assert output.summaries == []


def test_check_trigger_not_due():
    """8 rounds, interval=10, no prior -> no summary generated."""
    history = make_history(8)
    config = IMemoryConfig(summary_interval=10)
    existing = []

    with patch("app.services.memory_system.get_summaries", return_value=existing):
        from app.services.memory_system import check_and_trigger
        import asyncio
        result = asyncio.run(check_and_trigger("s1", history, config))
    assert result is None


def test_check_trigger_due():
    """11 rounds (0-10), interval=10, no prior -> summary generated."""
    history = make_history(11)
    config = IMemoryConfig(summary_interval=10)
    existing = []

    with patch("app.services.memory_system.get_summaries", return_value=existing), \
         patch("app.services.memory_system._save_summary"):
        from app.services.memory_system import check_and_trigger
        import asyncio
        result = asyncio.run(check_and_trigger("s1", history, config))

    assert result is not None
    assert result.segment_start == 0
    assert result.segment_end == 10


def test_check_trigger_overlap():
    """Prior ended at 10, now at 15, interval=5 -> generates for 11-15."""
    history = make_history(16)  # rounds 0-15
    config = IMemoryConfig(summary_interval=5)
    existing = [
        IMemorySummary(
            id="s1", session_id="s1",
            segment_start=0, segment_end=9,
            summary="前情提要...",
            created_at="2025-01-01T00:00:00",
        ),
    ]

    with patch("app.services.memory_system.get_summaries", return_value=existing), \
         patch("app.services.memory_system._save_summary"):
        from app.services.memory_system import check_and_trigger
        import asyncio
        result = asyncio.run(check_and_trigger("s1", history, config))

    assert result is not None
    assert result.segment_start == 10
    assert result.segment_end == 15


def test_summary_lock_toggle():
    """Toggle lock on a summary."""
    conn = MagicMock()
    # Simulate: first fetch returns locked=0, then after toggle returns locked=1
    fetch_results = [
        {"locked": 0},   # First call: check if exists
        None,            # After update, no more fetches needed
    ]
    conn.execute = MagicMock()
    conn.execute.return_value.fetchone = MagicMock(side_effect=fetch_results)

    with patch("app.services.memory_system.get_conn", return_value=conn):
        from app.services.memory_system import toggle_lock
        conn.execute.return_value.fetchone.side_effect = [{"locked": 0}]
        result = toggle_lock("s1", "sum1")
        # Should have tried to update
        assert conn.execute.call_count >= 2


def test_toggle_lock_not_found():
    """Toggle lock on non-existent summary returns False."""
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None

    with patch("app.services.memory_system.get_conn", return_value=conn):
        from app.services.memory_system import toggle_lock
        result = toggle_lock("s1", "nonexistent")
    assert result is False


def test_delete_locked_fails():
    """Cannot delete a locked summary."""
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {"locked": 1}

    with patch("app.services.memory_system.get_conn", return_value=conn):
        from app.services.memory_system import delete_summary
        result = delete_summary("s1", "locked_sum")
    assert result is False


def test_short_term_with_custom_config():
    """Custom short_term_rounds should change the filter threshold."""
    history = make_history(10)
    config = IMemoryConfig(short_term_rounds=2)

    with patch("app.services.memory_system.get_summaries", return_value=[]):
        from app.services.memory_system import get
        output = get("s1", history, config)

    round_indices = {getattr(m, "round_index", 0) for m in output.short_term}
    # max_round=9, threshold=7 -> only rounds 8,9
    assert len(round_indices) >= 1
    # Should NOT include round 0
    assert 0 not in round_indices


def test_empty_history():
    """Empty history should return empty short_term."""
    with patch("app.services.memory_system.get_summaries", return_value=[]):
        from app.services.memory_system import get
        output = get("s1", [])
    assert output.short_term == []


if __name__ == "__main__":
    tests = [
        ("Short-term last 5 rounds", test_get_short_term),
        ("No summaries for new session", test_get_no_summaries),
        ("Check trigger not due", test_check_trigger_not_due),
        ("Check trigger due", test_check_trigger_due),
        ("Check trigger overlap", test_check_trigger_overlap),
        ("Toggle lock", test_summary_lock_toggle),
        ("Toggle lock not found", test_toggle_lock_not_found),
        ("Delete locked fails", test_delete_locked_fails),
        ("Custom short_term_rounds", test_short_term_with_custom_config),
        ("Empty history", test_empty_history),
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
