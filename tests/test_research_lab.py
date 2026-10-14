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
from apps.web.data_views import build_evidence_compare, build_research_index, build_tca
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
    # qanat-style trial journal: a re-run of the SAME question is not a new attempt
    (tmp_path / "walk_forward_20260102_000000.json").write_text(
        '{"kind": "walk_forward", "payload": {"verdict": "OVERFIT"}}',
        encoding="utf-8")
    out = build_research_index()
    t = out["trial_summary"]
    assert t["available"] is True and t["attempts"] == 3
    assert t["distinct_questions"] == 2  # (walk_forward×2 = one question) + (sweep)
    assert t["verdicts"] == {"ROBUST": 1, "OVERFIT": 1}


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
    assert "/api/journal/evidence/compare" in paths
    assert "/api/market/dbnomics" in paths
    assert "/api/analytics/tca" in paths


# ── RUN-COMPARE (Vibe-Trading Compare.tsx, clean-room slice) ────────────────

def _write_artifact(tmp_path, name, payload):
    import json
    (tmp_path / name).write_text(json.dumps({
        "kind": "walk_forward",
        "generated_at_utc": "2026-10-11T00:00:00+00:00",
        "git_revision_short": "abc123",
        "payload": payload,
    }), encoding="utf-8")


def test_evidence_compare_side_by_side_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_mod, "DEFAULT_EVIDENCE_DIR", tmp_path)
    _write_artifact(tmp_path, "walk_forward_20261010_000000.json", {
        "strategy_id": "S03", "verdict": "OVERFIT",
        "overall_verdict": {"wfe_pct": 12.5, "pooled_oos_trades": 40, "robust": False},
    })
    _write_artifact(tmp_path, "walk_forward_20261011_000000.json", {
        "strategy_id": "S03", "verdict": "ROBUST",
        "overall_verdict": {"wfe_pct": 61.0, "pooled_oos_trades": 155, "robust": True},
    })
    out = build_evidence_compare([
        "walk_forward_20261010_000000.json",
        "walk_forward_20261011_000000.json",
    ])
    assert out["available"] is True
    assert len(out["columns"]) == 2
    assert [c["verdict"] for c in out["columns"]] == ["OVERFIT", "ROBUST"]
    assert out["columns"][1]["metrics"]["overall_verdict.wfe_pct"] == 61.0
    assert out["columns"][0]["metrics"]["strategy_id"] == "S03"


def test_evidence_compare_rejects_path_traversal_and_caps_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_mod, "DEFAULT_EVIDENCE_DIR", tmp_path)
    _write_artifact(tmp_path, "walk_forward_20261011_000000.json", {"verdict": "ROBUST"})
    out = build_evidence_compare([
        "../secret.env", "..\\secret.env", "/etc/passwd",
        "walk_forward_20261011_000000.json", "missing.json",
    ])
    assert len(out["columns"]) == 4  # capped, traversal rejected per column
    assert out["columns"][0]["error"].startswith("rejected")
    assert out["columns"][1]["error"].startswith("rejected")
    assert out["columns"][2]["error"].startswith("rejected")
    assert out["columns"][3]["verdict"] == "ROBUST"  # missing.json cut by the cap


def test_evidence_compare_includes_semantic_diff(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(evidence_mod, "DEFAULT_EVIDENCE_DIR", tmp_path)
    (tmp_path / "walk_forward_20261010_000000.json").write_text(json.dumps({
        "kind": "walk_forward", "payload": {"verdict": "OVERFIT", "wfe_pct": 12.5}}), encoding="utf-8")
    (tmp_path / "walk_forward_20261011_000000.json").write_text(json.dumps({
        "kind": "walk_forward", "payload": {"verdict": "ROBUST", "wfe_pct": 61.0}}), encoding="utf-8")
    out = build_evidence_compare([
        "walk_forward_20261010_000000.json",
        "walk_forward_20261011_000000.json",
    ])
    assert out["available"] is True
    assert out["diff"]["verdict_flip"] == {"old": "OVERFIT", "new": "ROBUST"}
    assert out["diff"]["counts"]["changed"] == 2


def test_evidence_compare_empty_selection_is_honest(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_mod, "DEFAULT_EVIDENCE_DIR", tmp_path)
    out = build_evidence_compare([])
    assert out["available"] is False
    assert "no artifact files selected" in out["reason"]


def test_dbnomics_builder_fail_closed_on_blank_codes():
    from apps.web.data_views import build_dbnomics_series
    out = build_dbnomics_series()
    assert out == {"available": False, "reason": "provider/dataset/series codes required"}


def test_insider_endpoint_fail_closed_and_registered(monkeypatch, tmp_path):
    from apps.web.data_views import build_insider_deals
    from apps.web.routes import router as api_router
    import mjonai.research.data.insider_deals as ind
    monkeypatch.setattr(ind, "DEFAULT_INSIDER_DIR", str(tmp_path / "ins"))
    assert build_insider_deals("")["available"] is False
    out = build_insider_deals("NEVERSYMBOLXX")
    assert out["available"] is True and out["deals"] == [] and out["count"] == 0
    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/api/market/insider-deals" in paths


def test_delivery_endpoint_fail_closed_and_registered(monkeypatch):
    from apps.web.data_views import build_delivery_snapshot
    from apps.web.routes import router as api_router
    import mjonai.data.market.delivery_tracker as dt
    monkeypatch.setattr(dt, "_DELIVERY_CACHE", {})
    assert build_delivery_snapshot("")["available"] is False
    out = build_delivery_snapshot("NEVERSYMBOLXX")
    assert out == {"available": False, "symbol": "NEVERSYMBOLXX",
                   "reason": "no delivery data for this symbol yet (daily 18:30 refresh)"}
    paths = {getattr(r, "path", None) for r in api_router.routes}
    assert "/api/market/delivery" in paths
