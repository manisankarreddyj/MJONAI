"""
Module: analytics/learning_loop.py

Purpose: Nightly learning-loop closure (P1.1 Session B, 2026-09-14).

Runs after the 16:00 forward-returns pass and completes the two feedback
channels the pipeline could previously only write:

  1. Agent recalibration — Brier-skill + rank-IC per agent over a COMMON
     outcome-tagged signal set (watchdog: no single trading day's noise
     moves a weight; min-sample guards below).
  2. Pattern-memory quarantine — setup hashes with >= 10 closed outcomes
     and a Laplace win-rate < 40% are quarantined so future signals are
     blocked before they can repeat the pathology.

Alignment rule (statistical honesty): an agent is only scored over signals
where BULL, BEAR and SUPERVISOR ALL produced an outcome-tagged row. Pairwise
skill comparisons on mismatched samples are meaningless — this keeps the
comparison like-for-like.

Mode scoping: pattern_memory / agent_weight_log rows are partitioned by
system_mode (RESEARCH / PAPER / LIVE). The loop is scoped to one mode —
defaulting to the engine's current SYSTEM_MODE — so research statistics
never quarantine a live pattern or vice-versa.
"""

from logging import getLogger
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = getLogger(__name__)

BOARD_AGENTS = ("BULL", "BEAR", "SUPERVISOR")
MIN_CALIBRATION_TRADES = 10          # per-agent common-sample floor
MIN_QUARANTINE_TRADES = 10           # >= 10 closed outcomes for a verdict
QUARANTINE_WIN_RATE_THRESHOLD = 0.40 # Laplace WR below this -> quarantine


def _system_mode() -> str:
    try:
        from mjonai.core.constants import SYSTEM_MODE
        return str(SYSTEM_MODE or "PAPER").upper()
    except Exception:
        return "PAPER"


def build_calibration_vectors(
    agent_logs: Sequence[Dict[str, Any]],
    agents: Sequence[str] = BOARD_AGENTS,
) -> Tuple[Optional[Dict[str, List[float]]], Optional[List[int]]]:
    """
    Align agent confidence rows with realized binary outcomes per signal.

    Only signals with an outcome-tagged row for EVERY listed agent are kept
    (like-for-like samples). Returns ``(None, None)`` when the common set is
    below 2 signals — weight moves need some sample to be meaningful.
    """
    rows_by_signal: Dict[str, Dict[str, Any]] = {}
    for row in agent_logs:
        name = str(row.get("agent_name") or "").strip().upper()
        sig_id = row.get("signal_id")
        outcome = str(row.get("actual_outcome") or "").upper()
        if name not in agents or not sig_id or outcome not in ("WIN", "LOSS"):
            continue
        bucket = rows_by_signal.setdefault(sig_id, {})
        bucket[name] = row
        bucket.setdefault("outcome", 1 if outcome == "WIN" else 0)

    common = [
        sig for sig, bucket in rows_by_signal.items()
        if all(agent in bucket for agent in agents) and bucket.get("outcome") is not None
    ]
    if len(common) < 2:
        return None, None

    forecasts: Dict[str, List[float]] = {}
    for agent in agents:
        confs: List[float] = []
        for sig in common:
            raw = rows_by_signal[sig][agent].get("confidence_given")
            try:
                confs.append(float(raw) if raw is not None else 0.5)
            except (TypeError, ValueError):
                confs.append(0.5)
        forecasts[agent] = confs
    outcomes = [int(rows_by_signal[sig]["outcome"]) for sig in common]
    return forecasts, outcomes


def run_agent_weight_calibration(
    agent_logs: Sequence[Dict[str, Any]],
    current_weights: Optional[Dict[str, float]] = None,
    agents: Sequence[str] = BOARD_AGENTS,
    min_trades: int = MIN_CALIBRATION_TRADES,
    system_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Recalibrate agent weights from realized outcomes and persist the log rows
    that survive the min-trades guard. Weight rows for thin samples are
    REPORTED but not persisted (a 3-trade Brier must not move money).
    """
    from mjonai.analytics.feedback_learning import recalibrate_agent_weights
    from mjonai.db.repository import insert_weight_log

    forecasts, outcomes = build_calibration_vectors(agent_logs, agents=agents)
    if forecasts is None or outcomes is None:
        return {"updated_weights": False, "reason": "insufficient common sample", "agents": []}

    scores = recalibrate_agent_weights(forecasts, outcomes, current_weights=current_weights)
    mode = (system_mode or _system_mode()).upper()
    persisted: List[Dict[str, Any]] = []
    for agent, score in scores.items():
        entry = {
            "agent_name": agent,
            "sample_size": score.sample_size,
            "brier_score": score.brier_score,
            "brier_skill_score": score.brier_skill_score,
            "accuracy_pct": score.accuracy_pct,
            "information_coefficient": score.information_coefficient,
            "old_weight": score.current_weight,
            "new_weight": score.updated_weight,
            "persisted": False,
        }
        if score.sample_size >= min_trades:
            rec = {
                "agent_name": agent,
                "old_weight": score.current_weight,
                "new_weight": score.updated_weight,
                "trigger_reason": "LEARNING_LOOP_BRIER",
                "accuracy_pct": score.accuracy_pct,
                "trades_evaluated": score.sample_size,
                "system_mode": mode,
            }
            try:
                insert_weight_log(rec)
                entry["persisted"] = True
            except Exception as e:
                logger.warning(f"[learning_loop] insert_weight_log failed for {agent}: {e}")
        persisted.append(entry)
    return {"updated_weights": True, "agents": persisted}


def run_pattern_quarantine(
    pattern_rows: Sequence[Dict[str, Any]],
    min_trades: int = MIN_QUARANTINE_TRADES,
    win_rate_threshold: float = QUARANTINE_WIN_RATE_THRESHOLD,
    system_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluate setup-hash memory rows and quarantine those whose Laplace win
    rate is below threshold on >= min_trades closed outcomes.
    """
    from mjonai.db.repository import quarantine_pattern

    mode = (system_mode or _system_mode()).upper()
    evaluated: List[Dict[str, Any]] = []
    quarantined: List[str] = []
    failed: List[str] = []

    for row in pattern_rows:
        setup_hash = str(row.get("setup_hash") or "").strip().upper()
        if not setup_hash:
            continue
        occurrences = int(row.get("occurrences") or 0)
        laplace = float(row.get("laplace_win_rate") or 0.0)
        if occurrences < min_trades:
            evaluated.append({
                "setup_hash": setup_hash,
                "total_trades": occurrences,
                "is_quarantined": False,
                "reason": f"Below {min_trades}-trade verdict floor",
            })
            continue

        # Invert the Laplace smoothing the writer applied:
        #   laplace = (wins + 1) / (occurrences + 2) * 100
        wins_est = max(0.0, (laplace / 100.0) * (occurrences + 2) - 1.0)
        winning = min(int(round(wins_est)), occurrences)
        losing = occurrences - winning
        trades = [{"net_pnl": 1.0}] * winning + [{"net_pnl": -1.0}] * losing

        from mjonai.analytics.feedback_learning import evaluate_setup_hash_memory
        status = evaluate_setup_hash_memory(
            setup_hash, str(row.get("strategy_id") or "UNKNOWN"), trades
        )

        item = {
            "setup_hash": setup_hash,
            "total_trades": status.total_trades,
            "winning_trades": status.winning_trades,
            "laplace_win_rate_pct": status.laplace_win_rate_pct,
            "is_quarantined": status.is_quarantined,
            "reason": status.reason,
            "persisted": False,
        }
        evaluated.append(item)
        if status.is_quarantined:
            try:
                ok = quarantine_pattern(setup_hash, system_mode=mode)
                item["persisted"] = bool(ok)
                if ok:
                    quarantined.append(setup_hash)
                else:
                    failed.append(setup_hash)
            except Exception as e:
                logger.warning(f"[learning_loop] quarantine failed for {setup_hash}: {e}")
                failed.append(setup_hash)

    return {"evaluated": evaluated, "evaluated_count": len(evaluated),
            "quarantined": quarantined, "failed": failed}


def run_daily_learning_loop(
    agent_logs: Optional[Sequence[Dict[str, Any]]] = None,
    pattern_rows: Optional[Sequence[Dict[str, Any]]] = None,
    current_weights: Optional[Dict[str, float]] = None,
    system_mode: Optional[str] = None,
    lookback_days: int = 30,
) -> Dict[str, Any]:
    """
    Full nightly closure: agent weight recalibration + pattern quarantine.

    Either input may be supplied directly (testing) or fetched from the DB
    (production 16:00 path). Failure in one leg does NOT abort the other.
    """
    mode = (system_mode or _system_mode()).upper()

    from mjonai.db.repository import (
        get_agent_logs_for_calibration,
        get_patterns_for_quarantine_eval,
        get_latest_weights,
    )

    try:
        logs = agent_logs if agent_logs is not None else get_agent_logs_for_calibration(lookback_days=lookback_days)
    except Exception as e:
        logger.warning(f"[learning_loop] agent-log fetch failed: {e}")
        logs = []

    try:
        patterns = pattern_rows if pattern_rows is not None else get_patterns_for_quarantine_eval(mode)
    except Exception as e:
        logger.warning(f"[learning_loop] pattern fetch failed: {e}")
        patterns = []

    try:
        weights = current_weights if current_weights is not None else get_latest_weights(mode)
    except Exception as e:
        logger.warning(f"[learning_loop] weight fetch failed: {e}")
        weights = None

    result: Dict[str, Any] = {
        "system_mode": mode,
        "agent_calibration": {"status": "skipped", "reason": "no outcome-tagged agent logs", "agents": []},
        "pattern_quarantine": {"evaluated": [], "evaluated_count": 0, "quarantined": [], "failed": []},
    }

    if logs:
        try:
            result["agent_calibration"] = run_agent_weight_calibration(
                logs, current_weights=weights, system_mode=mode
            )
        except Exception as e:
            logger.error(f"[learning_loop] calibration failed: {e}")
            result["agent_calibration"] = {"status": f"error: {e}", "agents": []}

    if patterns:
        try:
            result["pattern_quarantine"] = run_pattern_quarantine(patterns, system_mode=mode)
        except Exception as e:
            logger.error(f"[learning_loop] pattern quarantine failed: {e}")

    return result