"""Honest-fetch contract for the interactive app (all data pages).

Every data page fetches from an authenticated API. Class of bug this pins (the
qanat U-03/U-06 lesson): a hung server reads "connected" because no fetch has a
timeout, and a failed request leaves a panel silently empty — the page looks like
"nothing to show" when the truth is "the API did not answer". The contract is the
backend's: fail-closed with an explicit reason, never a silent blank or a false
"connected".

These pins make it impossible to silently (a) drop the request timeout, (b) drop
the fail-closed fallback, or (c) reintroduce the bare un-timed `fetch(path + ...)`.

Main-suite only (pure source inspection, no network, no browser).
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = REPO_ROOT / "apps" / "web" / "templates"

# Pages that share the fail-closed `api()` helper.
API_PAGES = ["index.html", "options.html", "research.html",
             "strategies.html", "trades.html", "console.html"]


def _read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", API_PAGES)
def test_api_helper_is_fail_closed_with_a_timeout(name):
    html = _read(name)
    assert "AbortController" in html, f"{name}: request timeout removed — a hung server would read 'connected'"
    assert "setTimeout(() => ctrl.abort(), 12000)" in html, f"{name}: 12s fetch timeout missing"
    assert '"server unreachable"' in html and '"request timed out"' in html, (
        f"{name}: no honest fallback reason on network failure/timeout"
    )
    assert 'available: false' in html, f"{name}: non-ok response must resolve to an explicit unavailable object"


@pytest.mark.parametrize("name", API_PAGES)
def test_no_bare_untimed_fetch_regression(name):
    html = _read(name)
    assert "=> fetch(path +" not in html, (
        f"{name}: reintroduced the bare un-timed fetcher — requests must go through the fail-closed api()"
    )


def test_market_poll_has_timeout_and_honest_stale_disclosure():
    html = _read("market.html")
    assert "AbortController" in html, "market.html: poll timeout removed"
    assert "API unreachable" in html and "API timed out" in html, (
        "market.html: poll must disclose unreachable/timed-out, not silently keep stale values"
    )
    assert "if (!res.ok) return;" not in html, "market.html: a non-ok poll must disclose, not silently return"


@pytest.mark.parametrize("name,phrase", [
    ("console.html", "not an empty queue"),
    ("strategies.html", "not a zero"),
    ("trades.html", "not empty"),
    ("index.html", "showing last values, retrying"),
])
def test_render_guards_disclose_a_failed_fetch(name, phrase):
    html = _read(name)
    assert phrase in html, f"{name}: render guard missing — a failed fetch could render as empty/success"


def test_options_greeks_history_section_is_fail_closed():
    html = _read("options.html")
    assert "ghist-chart" in html and "ghist-note" in html
    assert "No Greeks history." in html
    # unsolvable days render as gaps, never solver defaults
    assert "gaps are unsolvable days" in html


def test_options_greeks_history_route_registered():
    from apps.web.routes import router as api_router
    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/api/options/greeks-history" in paths


def test_options_straddle_section_is_fail_closed():
    html = _read("options.html")
    assert "strad-chart" in html and "strad-note" in html
    assert "No straddle series." in html
    assert "daily bars, not intraday rolling" in html


def test_options_straddle_route_registered():
    from apps.web.routes import router as api_router
    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/api/options/straddle-series" in paths


def test_options_portfolio_section_is_fail_closed():
    html = _read("options.html")
    assert "pf-list" in html and "pf-save" in html and "pf-note" in html
    assert "replay, never execution" in html


def test_options_portfolio_routes_registered():
    from apps.web.routes import router as api_router
    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/api/options/portfolio" in paths
    assert "/api/options/portfolio/{name}" in paths


def test_index_no_longer_claims_connection_on_error():
    html = _read("index.html")
    assert "API connection active" not in html, (
        "index.html: the false 'API connection active' message on failure must stay removed"
    )
