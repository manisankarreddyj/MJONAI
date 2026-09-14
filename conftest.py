"""ADR-0008: make the repo root importable for pytest (mjonai.*, apps.*, tools.*).

The suite runs from the repo root: `python -m pytest tests/`. This conftest makes
that work regardless of how pytest was invoked (cwd-independent).

Also defines the `--run-research` gate: tests/research/ suites carry the
`research` marker (tests/research/conftest.py) and are SKIPPED on a bare run.
Collecting them imports research modules, which is network-free; only execution
needs the flag:
    python -m pytest --run-research tests/research -q
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-research",
        action="store_true",
        default=False,
        help="execute research-marked suites (tests/research/); skipped without it",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-research"):
        return
    skip_research = pytest.mark.skip(reason="research suite: run with --run-research")
    for item in items:
        if "research" in item.keywords:
            item.add_marker(skip_research)
