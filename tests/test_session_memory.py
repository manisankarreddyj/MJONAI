"""Tests for tools/scripts/session_memory.py (ADR-0009 session-memory utility).

Uses tmp_path session roots — never writes to the real cache/sessions/.
"""
from datetime import date, datetime, timezone

import pytest

from tools.scripts.session_memory import (
    append_message,
    list_dates,
    read_messages,
    redact,
    session_path,
    tail,
)


def test_redact_masks_known_secret_pairs():
    text = "broker creds ANGELONE_API_KEY=abc123 keep this line normal"
    out = redact(text)
    assert "ANGELONE_API_KEY=***REDACTED***" in out
    assert "abc123" not in out
    assert "keep this line normal" in out
    assert "ABCD1234" in redact("MY_CUSTOM_KEY=ABCD1234")  # unknown key untouched


def test_redact_supports_colon_form():
    out = redact("Bearer GROQ_API_KEY: secretvalue")
    assert "GROQ_API_KEY=***REDACTED***" in out
    assert "secretvalue" not in out


def test_redact_leaves_placeholder_values():
    # Template/example values are still masked (they never belong in memory either).
    out = redact("SUPABASE_KEY=your_supabase_key_here")
    assert "your_supabase_key_here" not in out


def test_append_creates_daily_jsonl(tmp_path):
    when = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    path = append_message(tmp_path, "user", "hello world", when)
    assert path == session_path(tmp_path, date(2026, 9, 14))
    assert path.exists()
    rows = read_messages(tmp_path, date(2026, 9, 14))
    assert len(rows) == 1
    assert rows[0]["role"] == "user"
    assert rows[0]["text"] == "hello world"


def test_append_redacts_at_write_time(tmp_path):
    when = datetime(2026, 9, 14, 13, 0, tzinfo=timezone.utc)
    append_message(tmp_path, "assistant", "token TELEGRAM_BOT_TOKEN=leak123", when)
    rows = read_messages(tmp_path, date(2026, 9, 14))
    assert "leak123" not in rows[0]["text"]
    assert "***REDACTED***" in rows[0]["text"]


def test_append_rejects_unknown_role(tmp_path):
    with pytest.raises(ValueError):
        append_message(tmp_path, "robot", "nope", datetime.now(timezone.utc))


def test_list_and_tail(tmp_path):
    d0 = date(2026, 9, 13)
    d1 = date(2026, 9, 14)
    append_message(tmp_path, "user", "first", datetime(2026, 9, 13, 9, 0, tzinfo=timezone.utc))
    when = datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc)
    append_message(tmp_path, "assistant", "a", when)
    append_message(tmp_path, "assistant", "b", when)
    append_message(tmp_path, "assistant", "c", when)
    assert list_dates(tmp_path) == ["2026-09-13", "2026-09-14"]
    assert tail(tmp_path, d0, 20) == [("user", "first")]
    assert tail(tmp_path, d1, 2) == [("assistant", "b"), ("assistant", "c")]
    assert read_messages(tmp_path, d0)[0]["text"] == "first"


def test_missing_day_reads_empty(tmp_path):
    assert read_messages(tmp_path, date(2030, 1, 1)) == []
    assert tail(tmp_path, None, 5) == []