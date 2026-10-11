"""Research lab surfaces: evidence index + TCA views and their page (main suite).

Covers the Bloomberg-research-management / TCA clean-room pair: the view functions
must be fail-closed with honest reasons, the page must render, and both routes
must be registered. The math underneath is pinned in tests/research/test_tca.py
and the glob regression in tests/research/test_evidence_store.py.
"""

import sys
from pathlib import Path

_root_dir = Path(__file__).resolve().parents[1]  # repo root (ADR-0008)
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

import mjonai.research.evidence as evidence_mod
from apps.web.data_views import build_research_index, build_tca
from apps.web.pages import research_page
from apps.web.routes import router as api_router
from mjonai.research.evidence import record_evidence


def test_research_index_lists_artifacts_newest_first(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_mod, "DEFAULT_EVIDENCE_DIR", tmp_path)
    # controlled timestamps: the 2026 sweep must outrank the 2020 walk-forward even
    # though 'walk_forward' > 'discovery_sweep' alphabetically (chronological sort).
    (tmp_path / "walk_forward_20200101_000000.json").write_text(
        '{"kind": "walk_forward", "payload": {"verdict": "ROBUST"}}', encoding="utf-8")
    (tmp_path / "discovery_sweep_20261011_000000.json").write_text(
        '{"kind": "discovery_sweep", "payload": {"rows": 3}}', encoding="utf-8")
    out = build_research_index()
    assert out["available"] is True
    assert [a["kind"] for a in out["artifacts"]] == ["discovery_sweep", "walk_forward"]
    assert out["artifacts"][0]["headline"]["summary_rows"] == 3  # int rows handled


def test_research_index_empty_dir_is_honest(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_mod, "DEFAULT_EVIDENCE_DIR", tmp_path)
    out = build_research_index()
    assert out["available"] is False
    assert "no verdict artifacts" in out["reason"]


def test_research_index_corrupt_artifact_listed_not_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_mod, "DEFAULT_EVIDENCE_DIR", tmp_path)
    (tmp_path / "bad_20261011.json").write_text("{oops", encoding="utf-8")
    out = build_research_index()
    assert out["available"] is True  # the dir has artifacts
    assert out["artifacts"][0].get("error")  # unreadable is DISCLOSED


def test_tca_empty_ledger_fails_closed(monkeypatch):
    import mjonai.db.repository as repo

    monkeypatch.setattr(repo, "get_all_closed_trades", lambda limit=200: [])
    out = build_tca()
    assert out["available"] is False
    assert "no closed trades" in out["reason"]


def test_tca_reader_failure_is_honest(monkeypatch):
    import mjonai.db.repository as repo

    def boom(limit=200):
        raise RuntimeError("db down")

    monkeypatch.setattr(repo, "get_all_closed_trades", boom)
    out = build_tca()
    assert out["available"] is False
    assert "TCA unavailable" in out["reason"]  # reason surfaced, never a crash


def test_tca_aggregates_from_ledger(monkeypatch):
    import mjonai.db.repository as repo

    rows = [
        {"symbol": "RELIANCE", "gross_pnl": 1000.0, "net_pnl": 940.0, "slippage_bps": 2.0,
         "side": "LONG", "exit_reason": "TARGET", "strategy_id": "S03"},
    ]
    monkeypatch.setattr(repo, "get_all_closed_trades", lambda limit=200: rows)
    out = build_tca()
    assert out["available"] is True
    assert out["trades_total"] == 1
    assert out["net_pnl"] == 940.0
    assert out["rows"][0]["symbol"] == "RELIANCE"


def test_research_page_renders():
    resp = research_page()
    body = resp.body.decode("utf-8")
    assert resp.status_code == 200
    assert "Research lab" in body
    assert "Transaction cost analysis" in body
    assert "Verdict artifacts" in body
    # read-only disclosure — never implies execution capability
    assert "READ-ONLY" in body


def test_research_routes_registered():
    # APIRouter carries prefix="/api", so registered paths include it.
    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/api/journal/evidence" in paths
    assert "/api/analytics/tca" in paths
