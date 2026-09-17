"""Learning-loop Session B regression tests (2026-09-14).

Covers the calibration + quarantine closure:
  B1  build_calibration_vectors aligns confidences to realized outcomes on
      like-for-like signal sets (BULL/BEAR/SUPERVISOR all present).
  B2  run_agent_weight_calibration persists survivor rows, reports thin ones.
  B3  run_pattern_quarantine quarantines Laplacian pathologies only.
  B4  run_daily_learning_loop coordinates both legs without DB round-trips
      when inputs are injected.
"""

from unittest.mock import patch

import pytest

from mjonai.analytics.learning_loop import (
    build_calibration_vectors,
    run_agent_weight_calibration,
    run_daily_learning_loop,
    run_pattern_quarantine,
)


# Tests that do not inject forward returns must pin the lazy DB fetch to {} so
# the calibration path stays network-free and the IC columns stay honest-absent.
def _no_forward_returns(signal_ids):
    return {}


def _agent_log(common_signals=30, drop_agents=()):
    rows = []
    for i in range(common_signals):
        win = (i % 3) != 0  # ~2/3 wins
        outcome = "WIN" if win else "LOSS"
        for agent in ("BULL", "BEAR", "SUPERVISOR"):
            if agent in drop_agents:
                continue
            conf = 0.8 if win else 0.3
            if agent == "BEAR":
                conf = 0.2 if win else 0.7
            rows.append({
                "signal_id": f"sig-{i}",
                "agent_name": agent,
                "confidence_given": conf,
                "actual_outcome": outcome,
                "system_mode": "PAPER",
            })
    return rows


# ── B1: calibration-vector alignment ─────────────────────────────────────────

def test_alignment_requires_all_three_agents_per_signal():
    rows = _agent_log(common_signals=20)
    forecasts, outcomes = build_calibration_vectors(rows)
    assert forecasts is not None
    assert set(forecasts.keys()) == {"BULL", "BEAR", "SUPERVISOR"}
    assert len(forecasts["BULL"]) == len(outcomes) == 20
    # outcome binary: 20 signals; multiples of 3 (0,3,6,9,12,15,18) are LOSS → 13 wins
    assert sum(outcomes) == 13


def test_alignment_drops_agents_with_absent_signals():
    # SUPERVISOR missing entirely → common set collapses to < 2 → (None, None)
    rows = _agent_log(common_signals=15, drop_agents=("SUPERVISOR",))
    forecasts, outcomes = build_calibration_vectors(rows)
    assert forecasts is None and outcomes is None


def test_alignment_ignores_missing_outcome_rows():
    rows = _agent_log(common_signals=10)
    rows.append({
        "signal_id": "sig-999",
        "agent_name": "BULL",
        "confidence_given": 0.9,
        "actual_outcome": None,   # not yet closed → excluded
    })
    # The appends add no complete signal; common set stays 10.
    forecasts, _ = build_calibration_vectors(rows)
    assert forecasts is not None
    assert len(forecasts["BULL"]) == 10


# ── B2: weight calibration persistence ────────────────────────────────────────

def test_weight_recalibration_raises_good_agents():
    rows = _agent_log(common_signals=30)
    written = []

    def _fake_insert(rec):
        written.append(rec)
        return rec

    with (
        patch("mjonai.db.repository.insert_weight_log", side_effect=_fake_insert),
        patch("mjonai.db.repository.get_forward_returns_by_signal_ids", side_effect=_no_forward_returns),
    ):
        result = run_agent_weight_calibration(rows, system_mode="PAPER")

    assert result["updated_weights"] is True
    by_name = {a["agent_name"]: a for a in result["agents"]}
    # BULL is always-correct → weight should rise vs BEAR (always-wrong)
    assert by_name["BULL"]["new_weight"] > by_name["BEAR"]["new_weight"]
    assert by_name["SUPERVISOR"]["new_weight"] > by_name["BEAR"]["new_weight"]
    # 30-trade sample ≥ 10 floor → all persisted
    assert all(a["persisted"] for a in result["agents"])
    assert len(written) == 3
    assert all(w["system_mode"] == "PAPER" for w in written)
    # No forward returns available → IC columns honestly absent (never 0.0)
    assert result["info_coefficient_trustworthy"] is False
    assert all("information_coefficient" not in w for w in written)


def test_weight_recalibration_reports_thin_samples():
    rows = _agent_log(common_signals=5)
    written = []

    def _fake_insert(rec):
        written.append(rec)
        return rec

    with (
        patch("mjonai.db.repository.insert_weight_log", side_effect=_fake_insert),
        patch("mjonai.db.repository.get_forward_returns_by_signal_ids", side_effect=_no_forward_returns),
    ):
        result = run_agent_weight_calibration(rows, system_mode="PAPER")

    # Sample of 5 < 10 floor → reported, not persisted.
    assert all(a["sample_size"] == 5 for a in result["agents"])
    assert all(a["persisted"] is False for a in result["agents"])
    assert written == []
    assert result["info_coefficient_trustworthy"] is False


def test_weight_recalibration_short_circuits_on_no_common_sample():
    rows = _agent_log(common_signals=3, drop_agents=("SUPERVISOR",))
    with patch("mjonai.db.repository.insert_weight_log") as mock_insert:
        result = run_agent_weight_calibration(rows, system_mode="PAPER")
    assert result["updated_weights"] is False
    assert "insufficient common sample" in result["reason"]
    mock_insert.assert_not_called()


# ── B5: rank-IC wiring (2026-09-17) ───────────────────────────────────────────

def _monotone_rows(n=30):
    """Distinct ascending confidences with all-WIN outcomes and monotonically
    rising forward returns -> perfect Spearman IC == 1.0."""
    rows = []
    forward_returns = {}
    for i in range(n):
        conf = round(0.5 + i * 0.01, 4)
        for agent in ("BULL", "BEAR", "SUPERVISOR"):
            rows.append({
                "signal_id": f"sig-{i}",
                "agent_name": agent,
                "confidence_given": conf,
                "actual_outcome": "WIN",
                "system_mode": "PAPER",
            })
        forward_returns[f"sig-{i}"] = {
            "signal_direction": "LONG",
            "forward_return_20d": 0.01 + i * 0.01,
        }
    return rows, forward_returns


def test_calibration_persists_real_ic_when_returns_injected():
    rows, fwd = _monotone_rows()
    written = []

    def _fake_insert(rec):
        written.append(rec)
        return rec

    with patch("mjonai.db.repository.insert_weight_log", side_effect=_fake_insert):
        result = run_agent_weight_calibration(
            rows, system_mode="PAPER", forward_returns_by_signal=fwd
        )

    assert result["info_coefficient_trustworthy"] is True
    assert result["ic_sample_n"] == 30
    assert len(written) == 3
    # The real rank-IC reaches the persisted weight log (monotone -> IC == 1.0).
    for rec in written:
        assert "information_coefficient" in rec
        assert "ic_t_stat" in rec
        assert rec["information_coefficient"] == pytest.approx(1.0, abs=1e-6)


def test_calibration_omits_ic_columns_when_returns_thin():
    rows, fwd = _monotone_rows(30)
    # Remove forward returns for all but 2 signals -> below MIN_IC_SAMPLES=5.
    for i in range(2, 30):
        fwd[f"sig-{i}"] = {"signal_direction": "LONG"}
    written = []

    def _fake_insert(rec):
        written.append(rec)
        return rec

    with patch("mjonai.db.repository.insert_weight_log", side_effect=_fake_insert):
        result = run_agent_weight_calibration(
            rows, system_mode="PAPER", forward_returns_by_signal=fwd
        )

    assert result["info_coefficient_trustworthy"] is False
    assert result["ic_sample_n"] == 2
    assert len(written) == 3
    # Honest NULL: no fabricated IC/0.0 reaches the DB.
    for rec in written:
        assert "information_coefficient" not in rec
    for entry in result["agents"]:
        assert entry["information_coefficient"] is None
        assert entry["ic_sample_n"] == 0


def test_calibration_fetch_failure_fails_closed_to_absent_ic():
    rows = _agent_log(common_signals=30)
    written = []

    def _fake_insert(rec):
        written.append(rec)
        return rec

    # Corrupt fetch must not abort calibration — it degrades to Brier-only.
    def _boom(signal_ids):
        raise RuntimeError("Supabase TLS severed")

    with (
        patch("mjonai.db.repository.insert_weight_log", side_effect=_fake_insert),
        patch("mjonai.db.repository.get_forward_returns_by_signal_ids", side_effect=_boom),
    ):
        result = run_agent_weight_calibration(rows, system_mode="PAPER")

    assert result["updated_weights"] is True
    assert result["info_coefficient_trustworthy"] is False
    assert len(written) == 3
    assert all("information_coefficient" not in rec for rec in written)


# ── B3: pattern quarantine ────────────────────────────────────────────────────

def test_quarantine_kicks_pathological_hash_only():
    rows = [
        {"setup_hash": "BADPATTERN", "strategy_id": "S01", "occurrences": 15, "laplace_win_rate": 30.0},
        {"setup_hash": "GOODPATTERN", "strategy_id": "S02", "occurrences": 25, "laplace_win_rate": 66.0},
        {"setup_hash": "THINPATTERN", "strategy_id": "S03", "occurrences": 4, "laplace_win_rate": 10.0},
    ]
    with patch("mjonai.db.repository.quarantine_pattern", return_value=True) as mock_q:
        result = run_pattern_quarantine(rows, system_mode="PAPER")

    assert result["quarantined"] == ["BADPATTERN"]
    assert result["failed"] == []
    verdicts = {e["setup_hash"]: e["is_quarantined"] for e in result["evaluated"]}
    assert verdicts["BADPATTERN"] is True
    assert verdicts["GOODPATTERN"] is False
    assert verdicts["THINPATTERN"] is False  # below 10-trade verdict floor
    mock_q.assert_called_once_with("BADPATTERN", system_mode="PAPER")


def test_quarantine_records_db_failure_in_failed_list():
    rows = [{"setup_hash": "BAD", "strategy_id": "S1", "occurrences": 12, "laplace_win_rate": 20.0}]
    with patch("mjonai.db.repository.quarantine_pattern", return_value=False) as mock_q:
        result = run_pattern_quarantine(rows, system_mode="RESEARCH")
    assert result["quarantined"] == []
    assert result["failed"] == ["BAD"]
    mock_q.assert_called_once_with("BAD", system_mode="RESEARCH")


# ── B4: daily-loop coordination ───────────────────────────────────────────────

def test_daily_loop_coordinates_both_legs_with_injected_inputs():
    logs = _agent_log(common_signals=20)
    patterns = [{"setup_hash": "BAD", "strategy_id": "S1", "occurrences": 12, "laplace_win_rate": 20.0}]

    with (
        patch("mjonai.db.repository.insert_weight_log", side_effect=lambda rec: rec),
        patch("mjonai.db.repository.quarantine_pattern", return_value=True),
        patch("mjonai.db.repository.get_forward_returns_by_signal_ids", side_effect=_no_forward_returns),
    ):
        result = run_daily_learning_loop(
            agent_logs=logs, pattern_rows=patterns, current_weights=None, system_mode="PAPER"
        )

    assert result["system_mode"] == "PAPER"
    assert result["agent_calibration"]["updated_weights"] is True
    assert len(result["agent_calibration"]["agents"]) == 3
    assert result["pattern_quarantine"]["quarantined"] == ["BAD"]


def test_daily_loop_no_inputs_returns_skips_gracefully():
    with patch("mjonai.db.repository.get_agent_logs_for_calibration", return_value=[]), \
         patch("mjonai.db.repository.get_patterns_for_quarantine_eval", return_value=[]):
        result = run_daily_learning_loop(system_mode="PAPER")
    assert result["agent_calibration"]["status"] == "skipped"
    assert result["pattern_quarantine"]["evaluated_count"] == 0