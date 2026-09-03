"""One-shot generator for Supabase migration artifacts. Disposable tooling."""
import os, json, re, datetime
from collections import defaultdict
from core.runtime_config import load_mjonai_env
load_mjonai_env()

from supabase import create_client
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

TABLES = ["trades", "trade_tranches", "signals", "signal_intelligence_log", "pattern_memory",
          "daily_portfolio_snapshot", "intraday_portfolio_snapshot", "market_state_history",
          "agent_logs", "agent_weight_log", "scan_log", "system_health_log",
          "strategy_performance", "risk_events", "system_log"]

live = {}
for t in TABLES:
    try:
        d = sb.table(t).select("*").limit(1).execute().data
        live[t] = sorted(d[0].keys()) if d else []
    except Exception:
        live[t] = None  # missing table

# ---- writer key unions from runtime journals ----
W = defaultdict(set)
EV2T = {"INSERT_TRADE": "trades", "MARKET_STATE_HISTORY": "market_state_history",
        "DAILY_PORTFOLIO_SNAPSHOT": "daily_portfolio_snapshot", "INSERT_SYSTEM_LOG": "system_log",
        "INSERT_AGENT_LOG": "agent_logs", "MQI_SCORE_UPDATE": "market_state_history",
        "INSERT_SCAN_LOG": "scan_log", "INSERT_HEALTH_LOG": "system_health_log",
        "RISK_EVENT": "risk_events", "INSERT_RISK_EVENT": "risk_events",
        "INSERT_WEIGHT_LOG": "agent_weight_log", "STRATEGY_PERFORMANCE": "strategy_performance"}
for jf in ["storage/trades_journal.jsonl", "storage/snapshots_journal.jsonl",
           "storage/system_journal.jsonl", "storage/agent_logs_journal.jsonl"]:
    for line in open(jf, encoding="utf-8"):
        try:
            e = json.loads(line)
            t = EV2T.get(e.get("event_type"))
            if t:
                W[t] |= set(e.get("payload", {}).keys())
        except Exception:
            pass

def dataclass_fields(path, cls):
    src = open(path, encoding="utf-8").read()
    m = re.search(r"class " + cls + r"\b.*?:\n(.*?)(?=\n@|\nclass |\ndef )", src, re.S)
    return set(re.findall(r"^\s{4}([a-z_0-9]+)\s*:", m.group(1), re.M)) if m else set()

CODE = {
    "signal_intelligence_log": dataclass_fields("db/signals.py", "SignalIntelligenceRecord"),
    "intraday_portfolio_snapshot": dataclass_fields("db/snapshots.py", "IntradaySnapshotRecord"),
    "agent_weight_log": dataclass_fields("db/system.py", "AgentWeightRecord"),
    "strategy_performance": dataclass_fields("db/system.py", "StrategyPerformanceRecord"),
    "pattern_memory": {"setup_hash", "occurrences", "wins", "losses", "breakevens", "win_rate",
                       "laplace_win_rate", "avg_rr_achieved", "expectancy_rr", "profit_factor",
                       "last_10_outcomes", "last_outcome", "last_seen", "first_seen", "system_mode",
                       "updated_at", "candle_pattern", "sl_method", "market_state", "sector",
                       "strategy_id", "symbol", "vix_range"},
    "risk_events": {"event_type", "message", "level", "system_mode", "triggered_at"},
}
for t, s in CODE.items():
    W[t] |= s

BOOLS = {"is_deleted", "was_executed", "earnings_safe", "sector_cap_ok", "devil_all_passed",
         "fallback_used", "kill_line_triggered", "high_vol_override", "no_trade_day",
         "websocket_healthy", "internet_ok", "research_valid", "position_limit_reached",
         "forward_returns_computed"}
DATES = {"snapshot_date", "date", "day_date", "period_start", "period_end",
         "time_barrier_date", "expiry_date"}
JSONS = {"key_reasons", "concerns", "last_10_outcomes", "macro_flags", "reasons", "tranches",
         "metadata_json"}
TIMES = {"called_at", "generated_at", "scanned_at", "logged_at", "snapshot_time",
         "first_seen", "last_seen", "last_occurred_at"}
COUNT_COLS = {"closed_trades_today", "win_trades_today", "loss_trades_today",
              "trades_closed_today", "trades_opened_today", "winning_trades_today",
              "losing_trades_today", "total_trades", "open_positions", "wins_today",
              "losses_today", "signals_generated", "signals_approved", "signals_expired",
              "signals_rejected", "signals_pre_filtered", "signals_devil_failed",
              "signals_bull_rejected", "symbols_scanned", "active_trades",
              "live_prices_count", "stale_symbols", "occurrences", "breakevens",
              "quantity", "quantity_remaining", "holding_days", "trades_evaluated",
              "open_positions_count", "prompt_tokens", "response_tokens",
              "completion_tokens", "consecutive_losses", "consecutive_wins",
              "wins", "losses"}
MONEY_EXTRA = {"capital_free", "high_water_mark", "weight_change", "risk_per_share",
               "cash_available"}

def typ(c):
    cl = c.lower()
    if cl == "id":
        return "UUID"
    if cl.endswith("_id") and cl != "strategy_id":
        return "UUID"
    if cl == "strategy_id":
        return "TEXT"
    if cl.startswith("is_") or cl.startswith("was_") or cl in BOOLS:
        return "BOOLEAN"
    if cl in TIMES or cl.endswith("_at") or cl.endswith("_time"):
        return "TIMESTAMPTZ"
    if cl in DATES:
        return "DATE"
    if cl in JSONS:
        return "JSONB"
    tail = cl.split("_")[-1]
    numeric_tails = {"pct", "price", "pnl", "cost", "rr", "score", "value", "amount", "cr",
                     "ms", "equity", "cash", "rate", "factor", "ratio", "weight"}
    numeric_whole = {"confidence", "slippage_bps", "risk_per_share", "total_cost", "peak_equity",
                     "current_equity", "margin_utilized", "nifty_close", "nifty_level",
                     "entry_price", "exit_price", "stop_loss", "target", "target_1", "target_2",
                     "target_3", "atr_at_signal", "rsi_value", "planned_capital", "sharpe_rolling_30",
                     "cumulative_return_pct", "daily_return_pct", "deployment_pct", "vix_rank",
                     "actual_rr", "planned_rr", "avg_rr_achieved", "expectancy_rr", "win_rate"}
    ints = {"mqi_score", "total_score", "breadth_score", "vix_score", "fii_score"}
    if cl in COUNT_COLS:
        return "INTEGER"
    if cl in MONEY_EXTRA:
        return "NUMERIC"
    if cl in ("nifty_price", "ema20", "ema200"):
        return "NUMERIC"
    if cl in numeric_whole or tail in numeric_tails:
        return "NUMERIC"
    if tail.isdigit() is False and cl.startswith(("signals_", "trades_", "wins_", "losses_", "closed_", "loss_", "win_", "open_")):
        return "INTEGER"
    return "TEXT"

diffs = {}
for t in TABLES:
    need = W.get(t, set())
    have = set(live.get(t) or [])
    miss = sorted(need - have - {"id"})
    legacy = sorted(have - need - {"id", "created_at", "updated_at", "is_deleted"}) if live.get(t) else []
    if miss or live.get(t) is None:
        diffs[t] = {"missing": miss, "status": "CREATE" if live.get(t) is None else "ALTER",
                    "legacy_unused": legacy}

stamp = datetime.datetime.utcnow().strftime("%Y-%m-%d")
sql = ["-- MJONAI SUPABASE MIGRATION DRAFT (auto-generated %s)" % stamp,
       "-- Base: ACTUAL WRITER payloads (runtime journals + code dataclass contracts).",
       "-- db/schema.sql was NOT used as column source (stale third generation:",
       "-- initial_sl/target_price/stt_tax names match neither live DB nor writers).",
       "-- Additive-only: CREATE + ADD COLUMN IF NOT EXISTS. No drops, no renames, no data changes.",
       "", 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";', ""]
report = ["# Supabase Schema Diff Report", "", "**Generated:** %s (UTC)" % stamp, "",
          "Three-way reconciliation: LIVE remote schema (measured read-only via PostgREST)",
          "vs WRITER contracts (journal payload unions + code dataclass fields).",
          "`db/schema.sql` excluded as DDL source - it matches neither.", ""]
for t, d in diffs.items():
    report += ["## %s - %s" % (t, d["status"]), ""]
    if d["status"] == "CREATE":
        cols = sorted((W[t] | {"created_at"}) - {"id", "updated_at"})
        body = ["    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),"]
        for c in cols:
            dflt = " NOT NULL DEFAULT NOW()" if c == "created_at" else ""
            body.append("    %s %s%s," % (c, typ(c), dflt))
        body.append("    updated_at TIMESTAMPTZ")
        sql.append("CREATE TABLE IF NOT EXISTS %s (" % t)
        sql.extend(body)
        sql.append(");")
        sql.append("CREATE INDEX IF NOT EXISTS idx_%s_checkpoint ON %s(checkpoint_time DESC);" % (t, t))
        report.append("- NEW TABLE (writers currently fail silently against it).")
        report.append("- Columns created: %s" % cols)
    else:
        sql.append("-- %s: writer-required columns missing in live" % t)
        for c in d["missing"]:
            dflt = ""
            if typ(c) == "TIMESTAMPTZ":
                dflt = " DEFAULT NOW()"
            elif c == "system_mode":
                dflt = " DEFAULT 'RESEARCH'"
            sql.append("ALTER TABLE %s ADD COLUMN IF NOT EXISTS %s %s%s;" % (t, c, typ(c), dflt))
        report.append("- Missing writer columns (%d): %s" % (len(d["missing"]), d["missing"]))
    if d.get("legacy_unused"):
        report.append("- Live-only legacy columns left untouched (%d): %s" % (len(d["legacy_unused"]), d["legacy_unused"]))
    report.append("")
sql.append("")
sql.append("-- END OF MIGRATION DRAFT - review before applying.")
outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
open(os.path.join(outdir, "MIGRATION_DRAFT.sql"), "w", encoding="utf-8").write("\n".join(sql))
open(os.path.join(outdir, "SCHEMA_DIFF_REPORT.md"), "w", encoding="utf-8").write("\n".join(report))
print("tables needing change:", list(diffs))
for t, d in diffs.items():
    print("\n%s [%s] missing(%d): %s" % (t, d["status"], len(d["missing"]),
          d["missing"][:14]))
print("\nwrote planning/supabase/MIGRATION_DRAFT.sql + SCHEMA_DIFF_REPORT.md")
