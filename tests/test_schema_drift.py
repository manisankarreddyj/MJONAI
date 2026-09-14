"""
Static schema-drift guard: verifies mjonai/db/schema.sql matches writer payloads.

Three verification layers (all source-derived, no network):
  1. DDL columns == MANIFEST  — prevents schema.sql drift
  2. Whitelist source literals == MANIFEST  — prevents whitelist drift
  3. Dataclass fields + runtime adds == MANIFEST  — prevents writer-field drift
"""

import ast
import re
from pathlib import Path
from typing import Dict, Set, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = REPO_ROOT / "mjonai" / "db" / "schema.sql"
SIGNALS_PY = REPO_ROOT / "mjonai" / "db" / "signals.py"
SNAPSHOTS_PY = REPO_ROOT / "mjonai" / "db" / "snapshots.py"


# ─── MANIFEST: writer-accurate column set per table (audit 2026-09-14) ───────
# This is the single source of truth. Tests verify DDL and writers agree with it.
MANIFEST: Dict[str, Set[str]] = {
    "trades": {
        "id", "symbol", "direction", "entry_price", "initial_sl", "current_sl",
        "trailing_sl", "sl_stage", "target_price", "quantity", "quantity_remaining",
        "strategy_id", "signal_id", "asset_class", "decision_price", "slippage_bps",
        "uses_partial_exit", "status", "system_mode", "exit_price", "gross_pnl",
        "net_pnl", "stt_tax", "stt", "exchange_turnover_fee", "brokerage",
        "exit_reason", "actual_rr", "price_low_since_entry", "price_high_since_entry",
        "mae_pct", "mfe_pct", "giveback_pct", "entry_time", "exit_time",
        "created_at", "updated_at", "research_valid", "is_deleted",
    },
    "trade_tranches": {
        "id", "trade_id", "tranche_number", "quantity", "target_price", "target_rr",
        "status", "exit_price", "gross_pnl", "net_pnl", "exit_time", "updated_at",
        "is_deleted",
    },
    "signals": {
        "id", "symbol", "signal_type", "entry_price", "stop_loss", "target",
        "confidence", "timeframe", "market_state", "mqi_level", "status", "created_at",
    },
    # signal_intelligence_log: populated dynamically from _KNOWN_SIGNAL_COLUMNS
    "agent_logs": {
        "id", "agent_name", "signal_id", "raw_verdict", "confidence_given",
        "key_reasons", "concerns", "full_response", "latency_ms", "prompt_tokens",
        "completion_tokens", "agent_model", "fallback_used", "system_mode",
        "called_at", "updated_at", "actual_outcome", "actual_rr", "was_correct",
    },
    "pattern_memory": {
        "id", "setup_hash", "symbol", "strategy_id", "sl_method", "market_state",
        "vix_range", "candle_pattern", "occurrences", "wins", "losses", "breakevens",
        "win_rate", "laplace_win_rate", "avg_rr_achieved", "expectancy_rr",
        "profit_factor", "last_10_outcomes", "last_outcome", "is_quarantined",
        "is_deleted", "system_mode", "first_seen", "last_seen", "updated_at",
    },
    "daily_portfolio_snapshot": {
        "id", "snapshot_date", "capital_total", "cash_balance", "margin_used",
        "daily_pnl", "daily_pnl_pct", "unrealized_pnl", "peak_equity",
        "drawdown_pct", "open_positions", "closed_trades", "win_count",
        "loss_count", "system_mode", "metrics_json", "updated_at",
    },
    "intraday_portfolio_snapshot": {
        "id", "checkpoint_time", "current_equity", "cash_available",
        "margin_utilized", "unrealized_pnl", "realized_pnl", "open_positions_count",
        "drawdown_pct", "kill_line_triggered", "system_mode",
    },
    # market_state_history: populated dynamically from _MARKET_STATE_COLUMNS
    "scan_log": {
        "id", "symbols_scanned", "signals_generated", "signals_approved",
        "scan_duration_ms", "timeframe", "asset_class", "system_mode",
        "passed_liquidity", "passed_earnings", "passed_breadth",
        "passed_pattern_memory", "scanned_at",
    },
    "system_health_log": {
        "id", "oracle_cpu_pct", "oracle_ram_pct", "oracle_disk_pct",
        "websocket_healthy", "internet_ok", "groq_latency_ms", "gemini_latency_ms",
        "supabase_latency_ms", "angelone_latency_ms", "system_mode", "logged_at",
    },
    "strategy_performance": {
        "id", "strategy_id", "strategy_version", "period_start", "period_end",
        "market_state", "mqi_level", "system_mode", "total_trades", "wins",
        "losses", "win_rate", "profit_factor", "sharpe_ratio", "max_drawdown_pct",
        "calmar_ratio", "avg_rr", "net_pnl", "last_computed_at", "updated_at",
    },
    "agent_weight_log": {
        "id", "agent_name", "old_weight", "new_weight", "weight_change",
        "trigger_reason", "accuracy_pct", "trades_evaluated", "system_mode",
        "recalibrated_at",
    },
    "risk_events": {
        "id", "event_type", "message", "level", "system_mode", "triggered_at",
    },
    "system_log": {
        "id", "event_type", "message", "level", "system_mode", "created_at",
    },
}

# Whitelist-based tables: source file + variable name for the column set constant
WHITELIST_TABLES: Dict[str, Tuple[Path, str]] = {
    "signal_intelligence_log": (SIGNALS_PY, "_KNOWN_SIGNAL_COLUMNS"),
    "market_state_history": (SNAPSHOTS_PY, "_MARKET_STATE_COLUMNS"),
}

# Dataclass-based tables: (source file, class name, extra DB cols, dataclass fields to exclude)
# extra DB cols: columns added by the insert builder but not in the dataclass
# excluded cols: dataclass fields not present in the DB (renamed/filtered)
DATACLASS_TABLES: Dict[str, Tuple[Path, str, Set[str], Set[str]]] = {
    "trades": (
        REPO_ROOT / "mjonai" / "db" / "trades.py",
        "TradeRecord",
        {"id", "stt"},  # id: Supabase-generated; stt: close_trade UPDATE only
        set(),
    ),
    "trade_tranches": (
        REPO_ROOT / "mjonai" / "db" / "trades.py",
        "TrancheRecord",
        {"id"},
        set(),
    ),
    "agent_logs": (
        REPO_ROOT / "mjonai" / "db" / "agents.py",
        "AgentLogRecord",
        {"id"},
        set(),
    ),
    "pattern_memory": (
        REPO_ROOT / "mjonai" / "db" / "patterns.py",
        "PatternMemoryRecord",
        {"id"},
        set(),
    ),
    "daily_portfolio_snapshot": (
        REPO_ROOT / "mjonai" / "db" / "snapshots.py",
        "PortfolioSnapshot",
        {"id"},
        set(),
    ),
    "intraday_portfolio_snapshot": (
        REPO_ROOT / "mjonai" / "db" / "snapshots.py",
        "IntradaySnapshotRecord",
        {"id"},
        set(),
    ),
    "scan_log": (
        REPO_ROOT / "mjonai" / "db" / "system.py",
        "ScanLogRecord",
        {"id"},
        set(),
    ),
    "system_health_log": (
        REPO_ROOT / "mjonai" / "db" / "system.py",
        "SystemHealthRecord",
        {"id"},
        set(),
    ),
    "strategy_performance": (
        REPO_ROOT / "mjonai" / "db" / "system.py",
        "StrategyPerformanceRecord",
        {"id"},
        set(),
    ),
    "agent_weight_log": (
        REPO_ROOT / "mjonai" / "db" / "system.py",
        "AgentWeightRecord",
        {"id"},
        set(),
    ),
}


# ─── DDL PARSER ─────────────────────────────────────────────────────────────

def _parse_ddl(path: Path) -> Dict[str, Set[str]]:
    """Extract table → column_names from CREATE TABLE statements in a SQL file."""
    text = path.read_text(encoding="utf-8")
    tables: Dict[str, Set[str]] = {}
    current_table: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        m = re.match(
            r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)\s*\(",
            stripped, re.IGNORECASE,
        )
        if m:
            current_table = m.group(1)
            tables[current_table] = set()
            continue
        if current_table and stripped == ");":
            current_table = None
            continue
        if current_table:
            if stripped.startswith("--") or stripped.startswith("CONSTRAINT"):
                continue
            col_match = re.match(
                r"(\w+)\s+(TEXT|NUMERIC|INTEGER|BOOLEAN|UUID|JSONB|TIMESTAMPTZ|DATE|VARCHAR)",
                stripped, re.IGNORECASE,
            )
            if col_match:
                tables[current_table].add(col_match.group(1))
    return tables


# ─── AST SOURCE EXTRACTORS ──────────────────────────────────────────────────

def _extract_set_literal(source_path: Path, var_name: str) -> Set[str]:
    """Extract a set literal assigned to a module-level variable via AST."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == var_name:
                    if isinstance(node.value, ast.Set):
                        return {elt.value for elt in node.value.elts}
    raise AssertionError(f"{var_name} not found in {source_path}")


def _extract_dataclass_fields(source_path: Path, class_name: str) -> Set[str]:
    """Extract field names from a @dataclass class via AST."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        has_dataclass = any(
            (isinstance(d, ast.Name) and d.id == "dataclass")
            or (isinstance(d, ast.Attribute) and d.attr == "dataclass")
            or (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "dataclass")
            or (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "dataclass")
            for d in node.decorator_list
        )
        if not has_dataclass:
            continue
        fields: Set[str] = set()
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fields.add(item.target.id)
        return fields
    raise AssertionError(f"dataclass {class_name} not found in {source_path}")


# ─── POPULATE MANIFEST FROM SOURCE (whitelist tables) ───────────────────────

def _populate_whitelist_columns() -> None:
    """Fill MANIFEST entries from in-source whitelist constants."""
    for table, (path, var_name) in WHITELIST_TABLES.items():
        MANIFEST[table] = _extract_set_literal(path, var_name)


_populate_whitelist_columns()


# ─── TESTS ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("table", sorted(MANIFEST.keys()))
def test_ddl_matches_manifest(table):
    """Every table in schema.sql must exactly match the MANIFEST column set."""
    ddl = _parse_ddl(SCHEMA_SQL)
    assert table in ddl, f"table '{table}' missing from schema.sql"
    expected = MANIFEST[table]
    actual = ddl[table]
    missing = expected - actual
    extra = actual - expected
    assert not missing, f"schema.sql missing columns for '{table}': {missing}"
    assert not extra, f"schema.sql has extra columns for '{table}': {extra}"


@pytest.mark.parametrize("table", sorted(MANIFEST.keys()))
def test_all_manifest_tables_in_ddl(table):
    """Every MANIFEST table must have a CREATE TABLE in schema.sql."""
    ddl = _parse_ddl(SCHEMA_SQL)
    assert table in ddl, f"MANIFEST table '{table}' missing from schema.sql"


@pytest.mark.parametrize("table", sorted(WHITELIST_TABLES.keys()))
def test_whitelist_source_matches_manifest(table):
    """In-source whitelist constant must exactly match the MANIFEST for that table."""
    path, var_name = WHITELIST_TABLES[table]
    source_cols = _extract_set_literal(path, var_name)
    expected = MANIFEST[table]
    assert source_cols == expected, (
        f"whitelist '{var_name}' in {path.name} diverges from MANIFEST for '{table}': "
        f"missing={expected - source_cols}, extra={source_cols - expected}"
    )


@pytest.mark.parametrize("table", sorted(DATACLASS_TABLES.keys()))
def test_dataclass_fields_match_manifest(table):
    """Dataclass fields + runtime adds must exactly equal MANIFEST for that table."""
    source_path, class_name, extra_cols, excluded_cols = DATACLASS_TABLES[table]
    dc_fields = _extract_dataclass_fields(source_path, class_name)
    derived = (dc_fields | extra_cols) - excluded_cols
    expected = MANIFEST[table]
    missing = expected - derived
    extra = derived - expected
    assert not missing, (
        f"dataclass '{class_name}' + runtime adds missing columns for '{table}': {missing}"
    )
    assert not extra, (
        f"dataclass '{class_name}' + runtime adds has extra columns for '{table}': {extra}"
    )


def test_no_orphaned_tables_in_ddl():
    """schema.sql must not contain tables outside MANIFEST."""
    ddl = _parse_ddl(SCHEMA_SQL)
    orphans = set(ddl.keys()) - set(MANIFEST.keys())
    assert not orphans, f"schema.sql has tables not in MANIFEST: {orphans}"


def test_whitelist_tables_in_dataclass_set():
    """WHITELIST_TABLES and DATACLASS_TABLES must be disjoint (no table double-covered)."""
    overlap = set(WHITELIST_TABLES.keys()) & set(DATACLASS_TABLES.keys())
    assert not overlap, f"tables covered by both WHITELIST and DATACLASS: {overlap}"
