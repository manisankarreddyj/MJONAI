"""Persistent session-memory utility (ADR-0009, layer-3 convenience capture).

Deterministic, stdlib-only, never prints secrets. Raw per-message logs are
appended to cache/sessions/<YYYY-MM-DD>.jsonl (gitignored runtime data). The
distilled authoritative truth lives in MJONAI_DOCS.md section 16.

Run from the repo root; the script resolves the root via its own location.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION_ROOT = REPO_ROOT / "cache" / "sessions"
_MASK = "***REDACTED***"

# Keys whose values must never be persisted. Mirrors the credential names found
# across the codebase (credentials/.env.master schema); keep in sync with any
# provider added later.
SECRET_KEY_NAMES = frozenset(
    """
    ANGELONE_API_KEY ANGELONE_CLIENT_ID ANGELONE_PASSWORD ANGELONE_TOTP_SECRET
    ANGELONE_SECRET_KEY SHOONYA_API_KEY SHOONYA_IMEI SHOONYA_PASSWORD
    SHOONYA_SECRET_CODE SHOONYA_USER_ID SHOONYA_VENDOR_CODE SHOONYA_TOTP_KEY
    SHOONYA_TOTP_SECRET TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID SUPABASE_POOLER_URL
    SUPABASE_DB_URL SUPABASE_KEY SUPABASE_URL DATABASE_URL POSTGRES_DB
    POSTGRES_PASSWORD POSTGRES_PORT POSTGRES_USER DISCORD_BOT_TOKEN
    DISCORD_WEBHOOK_URL DISCORD_WEBHOOK_ALERTS DISCORD_WEBHOOK_MARKET_MOOD
    DISCORD_WEBHOOK_OPTIONS DISCORD_WEBHOOK_PORTFOLIO DISCORD_WEBHOOK_SIGNALS
    DISCORD_SERVER_ID REDIS_PORT UPSTASH_REDIS_REST_TOKEN UPSTASH_REDIS_REST_URL
    UPSTASH_REDIS_TOKEN UPSTASH_REDIS_URL CLAUDE_API_KEY GEMINI_API_KEY
    GOOGLE_API_KEY GROQ_API_KEY HUGGINGFACE_TOKEN OPENROUTER_API_KEY
    NVIDIA_API_KEY NVCF_API_KEY ZHIPUAI_API_KEY GLM_API_KEY NEWS_API_KEY
    SERPAPI_KEY TAVILY_API_KEY OPENALGO_API_KEY MJONAI_APP_TOKEN ARTHAI_API_KEY
    """.split()
)

_DATE_STEM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_KEY_EQ_RE = re.compile(r"\b([A-Z][A-Z0-9_]{3,})\s*[=:]\s*(\S+)")


def redact(text: str) -> str:
    """Redact any known secret key=value pair. Leaves ordinary text untouched."""
    def _mask(match: "re.Match[str]") -> str:
        name = match.group(1)
        if name in SECRET_KEY_NAMES:
            return f"{name}={_MASK}"
        return match.group(0)

    return _KEY_EQ_RE.sub(_mask, text)


def session_path(root: Path, day: date) -> Path:
    return root / f"{day.isoformat()}.jsonl"


def append_message(root: Path, role: str, text: str, when: "datetime | None" = None) -> Path:
    """Append one redacted message as a JSONL line. Returns the file written."""
    if role not in ("user", "assistant", "system"):
        raise ValueError(f"role must be user|assistant|system, got {role!r}")
    when = when or datetime.now(timezone.utc)
    root.mkdir(parents=True, exist_ok=True)
    path = session_path(root, when.date())
    record = {
        "t": when.isoformat(timespec="seconds"),
        "role": role,
        "text": redact(text).strip(),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def read_messages(root: Path, day: "date | None" = None) -> list[dict]:
    """Read all messages for a day (default: today). Malformed lines are skipped."""
    day = day or date.today()
    path = session_path(root, day)
    if not path.exists():
        return []
    messages: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return messages


def list_dates(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(p.stem for p in root.glob("*.jsonl") if _DATE_STEM_RE.match(p.stem))


def tail(root: Path, day: "date | None", lines: int) -> list[tuple[str, str]]:
    """Return the last N (role, text) entries for a day, oldest first."""
    return [(m["role"], m["text"]) for m in read_messages(root, day)[-lines:]]


def _parse_args(argv: "list[str] | None" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    append = sub.add_parser("append", help="append a message to today's session log")
    append.add_argument("--role", choices=("user", "assistant", "system"), default="assistant")
    append.add_argument("--text", required=True, help="message text (use '-' to read from stdin)")
    append.add_argument("--date", default=None, help="ISO date override (tests only)")

    sub.add_parser("list", help="list session log dates")

    t = sub.add_parser("tail", help="show last N entries for a date")
    t.add_argument("--date", default=None, help="ISO date (default: today)")
    t.add_argument("--lines", type=int, default=20)

    return parser.parse_args(argv)


def main(argv: "list[str] | None" = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dir_value = None
    for index, arg in enumerate(argv):
        if arg == "--dir":
            dir_value = argv[index + 1]
            del argv[index : index + 2]
            break
    args = _parse_args(argv)
    root = Path(dir_value) if dir_value else SESSION_ROOT

    if args.command == "append":
        text = args.text
        if text == "-":
            text = sys.stdin.read()
        day = date.fromisoformat(args.date) if args.date else None
        by_date = day or date.today()
        when = (
            datetime(by_date.year, by_date.month, by_date.day, 12, 0, tzinfo=timezone.utc)
            if args.date
            else None
        )
        path = append_message(root, args.role, text, when)
        print(f"appended to {path}")
        return 0

    if args.command == "list":
        for d in list_dates(root):
            print(d)
        return 0

    if args.command == "tail":
        day = date.fromisoformat(args.date) if args.date else None
        for role, text in tail(root, day, args.lines):
            print(f"[{role}] {text}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())