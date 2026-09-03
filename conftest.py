"""ADR-0008: make the repo root importable for pytest (mjonai.*, apps.*, tools.*).

The suite runs from the repo root: `python -m pytest tests/`. This conftest makes
that work regardless of how pytest was invoked (cwd-independent).
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
