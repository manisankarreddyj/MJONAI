"""
Module: apps/web/report.py
Purpose: the one-page self-contained HTML EOD report.

CONCEPT SOURCE (clean-room, no code copied): TradingAgents v0.6.0 saves each
decision report as ONE self-contained HTML page. Apache-2.0 would permit code reuse,
but the report is re-implemented in MJONAI's stack anyway: server-rendered from the
repository facade, inline CSS, NO external requests — the file opens identically
offline and can be attached to Telegram as-is.

Honesty contract: every figure comes from the same facade the dashboard reads;
absent data renders "—" (never fabricated), and the mode label is always visible
so a paper report can never be mistaken for a live one.
"""
from __future__ import annotations

from typing import Any, Dict, List

_CSS = """
body{margin:0;font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;background:#0d1117;color:#e6edf3}
main{max-width:960px;margin:0 auto;padding:20px}
h1{font-size:1.25rem;margin:0 0 2px}
h2{font-size:.8rem;color:#8b949e;text-transform:uppercase;letter-spacing:.08em;margin:20px 0 6px}
.sub{color:#8b949e;font-size:.78rem}
.mode{display:inline-block;font-weight:800;font-size:.7rem;padding:2px 10px;border-radius:999px;
 border:1px solid #30363d;letter-spacing:.08em;vertical-align:middle;margin-left:8px}
.mode.RESEARCH{color:#60a5fa;border-color:#1f4b8f;background:rgba(59,130,246,.10)}
.mode.PAPER{color:#d29922;border-color:#6b4e0c;background:rgba(210,153,34,.10)}
.mode.LIVE{color:#f85149;border-color:#8c2b26;background:rgba(248,81,73,.12)}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:5px 6px;border-bottom:1px solid #21262d}
th{color:#8b949e;font-weight:500;font-size:.72rem}
tr:last-child td{border-bottom:none}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin:10px 0}
.tile{border:1px solid #21262d;border-radius:10px;padding:8px 10px}
.tile .k{color:#8b949e;font-size:.68rem;text-transform:uppercase;letter-spacing:.08em}
.tile .v{font-size:1.1rem;margin-top:2px}
.pos{color:#3fb950}.neg{color:#f85149}.mut{color:#8b949e}
.alert{border:1px solid #6b4e0c;background:rgba(210,153,34,.08);border-radius:8px;
 padding:8px 10px;margin:6px 0;font-size:.85rem}
.crit{border-color:#8c2b26;background:rgba(248,81,73,.08)}
footer{margin-top:26px;color:#8b949e;font-size:.72rem;border-top:1px solid #21262d;padding-top:8px}
"""


def _esc(s: Any) -> str:
    return (str(s if s is not None else "—")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def _money(v: Any, signed_v: bool = False) -> str:
    if v is None:
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    s = f"{abs(f):,.0f}"
    return f"{'+' if f >= 0 else '−'}₹{s}" if signed_v else f"₹{s}"


def build_report_data() -> Dict[str, Any]:
    """Gather every section from the same facade the dashboard reads (fail-closed:
    an empty DB produces '—'/'no data' rows, never fabricated figures)."""
    from apps.web.data_views import (
        build_ai_debates, build_equity_series, build_market_cockpit,
        build_recent_trades, build_signal_track_record, build_system_status,
    )

    status = build_system_status()
    equity = build_equity_series(days=14)
    trades = build_recent_trades(limit=25)
    track = build_signal_track_record(days=90)
    debates = build_ai_debates(limit=5)
    try:
        cockpit = build_market_cockpit()
    except Exception:
        cockpit = {}
    return {
        "status": status, "equity": equity, "trades": trades,
        "track": track, "debates": debates, "cockpit": cockpit,
    }


def render_eod_report() -> str:
    """One self-contained HTML page: no scripts, no external requests, no CDN."""
    from datetime import datetime, timezone

    d = build_report_data()
    status = d["status"] or {}
    mode = str(status.get("system_mode") or "RESEARCH").upper()
    equity = d["equity"] or []
    trades = d["trades"] or []
    track = d["track"] or {}
    debates = d["debates"] or []
    cockpit = d["cockpit"] or {}

    eq_last = equity[-1]["equity"] if equity else None
    eq_first = equity[0]["equity"] if equity else None
    window_pnl = (eq_last - eq_first) if (eq_last is not None and eq_first is not None) else None
    nets = [t.get("net_pnl") for t in trades if isinstance(t.get("net_pnl"), (int, float))]
    closed_net = sum(nets) if nets else None
    overall = track.get("overall") or {}

    alerts: List[str] = []
    guards = (cockpit.get("risk_guards") or {})
    if guards.get("kill_line_active"):
        alerts.append("<b>KILL LINE ACTIVE</b> — trading locked; manual reset required.")
    if guards.get("risk_stop_active"):
        alerts.append("<b>Risk stop active</b> — new entries halted.")
    if guards.get("behavioral_cooldown_active"):
        alerts.append(f"<b>Behavioral cooldown</b> — {_esc(guards.get('consecutive_losses'))} consecutive losses; cooldown running.")
    if guards.get("trading_allowed") is False:
        alerts.append("<b>Trading not allowed</b> — " + _esc(", ".join(guards.get("active_reasons") or [])))

    alert_html = "".join(
        f'<div class="alert {"crit" if "KILL" in a else ""}">{a}</div>' for a in alerts
    ) or '<div class="mut">No active risk locks.</div>'

    trade_rows = "".join(
        f"<tr><td>{_esc((t.get('closed_at') or '')[:16])}</td><td>{_esc(t.get('symbol'))}</td>"
        f"<td>{_esc(t.get('side'))}</td><td>{_esc(t.get('strategy_id'))}</td>"
        f"<td class=\"{'pos' if (t.get('net_pnl') or 0) >= 0 else 'neg'}\">{_money(t.get('net_pnl'), True)}</td>"
        f"<td>{_esc(t.get('exit_reason'))}</td></tr>"
        for t in trades
    ) or '<tr><td colspan="6" class="mut">no closed trades today</td></tr>'

    def _pct(v: Any, digits: int = 1, signed: bool = False) -> str:
        if not isinstance(v, (int, float)):
            return "—"
        return f"{100 * float(v):+.{digits}f}%" if signed else f"{100 * float(v):.{digits}f}%"

    strat_rows = "".join(
        f"<tr><td>{_esc(s.get('strategy_id'))}</td><td>{s.get('n')}</td>"
        f"<td>{_pct(s.get('hit_rate_1d'))}</td>"
        f"<td>{_pct(s.get('mean_fwd_1d'), 2, signed=True)}</td>"
        f"<td>{_pct(s.get('hit_rate_5d'))}</td></tr>"
        for s in (track.get("strategies") or [])
    ) or '<tr><td colspan="5" class="mut">no settled signals with forward returns yet</td></tr>'

    debate_rows = "".join(
        f"<tr><td>{_esc((b.get('time') or '')[:16])}</td><td>{_esc(b.get('symbol'))}</td>"
        f"<td>{_esc(b.get('signal_direction'))}</td><td>{_esc(b.get('final_confidence'))}</td>"
        f"<td>{_esc((b.get('bull_agent') or {}).get('verdict'))}</td>"
        f"<td>{_esc((b.get('supervisor_cio') or {}).get('reason'))}</td></tr>"
        for b in debates
    ) or '<tr><td colspan="6" class="mut">no recorded debates in window</td></tr>'

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>MJONAI EOD report — {now}</title><style>{_CSS}</style></head>
<body><main>
<h1>MJONAI — end-of-day report<span class="mode {mode}">{mode}</span></h1>
<div class="sub">{now} · generated from the repository facade · figures are what the system recorded, never estimates</div>

<h2>Risk state</h2>{alert_html}

<h2>Snapshot</h2>
<div class="tiles">
 <div class="tile"><div class="k">Equity</div><div class="v">{_money(eq_last)}</div></div>
 <div class="tile"><div class="k">14d equity Δ</div><div class="v {'pos' if (window_pnl or 0) >= 0 else 'neg'}">{_money(window_pnl, True)}</div></div>
 <div class="tile"><div class="k">Closed net (today)</div><div class="v {'pos' if (closed_net or 0) >= 0 else 'neg'}">{_money(closed_net, True)}</div></div>
 <div class="tile"><div class="k">Drawdown</div><div class="v">{'—' if status.get('drawdown_pct') is None else f"{status['drawdown_pct']:.1f}%"}</div></div>
 <div class="tile"><div class="k">Settled signals</div><div class="v">{overall.get('n', 0)}</div></div>
 <div class="tile"><div class="k">1-day hit-rate</div><div class="v">{'—' if overall.get('hit_rate_1d') is None else f"{100 * overall['hit_rate_1d']:.1f}%"}</div></div>
</div>

<h2>Closed trades today</h2>
<table><thead><tr><th>Closed</th><th>Symbol</th><th>Side</th><th>Strategy</th><th>Net</th><th>Exit</th></tr></thead>
<tbody>{trade_rows}</tbody></table>

<h2>Strategy track record (90d, direction-adjusted)</h2>
<table><thead><tr><th>Strategy</th><th>Signals</th><th>1d hit-rate</th><th>Mean fwd 1d</th><th>5d hit-rate</th></tr></thead>
<tbody>{strat_rows}</tbody></table>

<h2>Recent boardroom transcripts</h2>
<table><thead><tr><th>Time</th><th>Symbol</th><th>Direction</th><th>Conf</th><th>Bull</th><th>Supervisor</th></tr></thead>
<tbody>{debate_rows}</tbody></table>

<footer>MJONAI {mode} · research-tier reporting · this page cannot place orders (ADR-0007) ·
absent values render as — rather than estimates.</footer>
</main></body></html>"""
