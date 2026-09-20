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


@pytest.fixture(autouse=True, scope="session")
def _block_live_alert_network():
    """Hard guard: no test may ever send a REAL Telegram/Discord alert.

    ``mjonai.core.runtime_config.load_mjonai_env()`` loads the root ``.env``
    at import time, so the test process does hold real bot credentials. Alert
    helpers resolve their credential accessor at CALL time, so neutralising the
    accessor here forces every alert into dry-run from any caller — including
    background daemon threads (e.g. the websocket reconnect loop) that outlive a
    ``with patch(...)`` block. Tests that assert send behaviour patch
    ``send_message`` / ``send_discord_webhook`` directly.
    """
    import mjonai.communication.telegram as _tg
    import mjonai.communication.discord as _dc

    _orig_tg, _orig_dc = _tg._get_credentials, _dc._get_webhook_url
    _tg._get_credentials = lambda: (None, None)
    _dc._get_webhook_url = lambda: None
    yield
    _tg._get_credentials = _orig_tg
    _dc._get_webhook_url = _orig_dc



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
