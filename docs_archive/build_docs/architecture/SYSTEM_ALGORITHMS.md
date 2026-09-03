# MJONAI System Algorithms (As Implemented)

> This document documents the major algorithms implemented within MJONAI, their purpose, workflow, assumptions, and architectural role.

**Extracted from:** MJONAI_MASTER_v2.0.md (Sections 6, 10, 11, 12, 13, 14, 15)
**Cross-checked against:** core/mqi.py, core/market_state.py, risk/devil_checks.py, strategy/signal_scanner.py, execution/paper.py
**Last verified:** 27 May 2026
**Status:** SPEC — describes what the code actually does

> **Purpose:** Single source of truth for the algorithms running in production. When code disagrees with this doc, the code wins and this doc gets corrected. Replaces stale algorithm sections in Master v2.0.

> **Drift notes:** Where the implementation differs from the original Master v2.0 spec, this doc documents the **actual implementation**, not the spec, and flags the difference with a WARNING marker.

---

## 1. DATABASE SCHEMA (17 TABLES)

### Standards
- UUID primary key
- created_at / updated_at TIMESTAMPTZ
- is_deleted BOOLEAN DEFAULT FALSE
- Soft delete only — never hard delete
- All accessed via db/repository.py (52 functions)

### Original 6 Tables

| Table | Purpose |
|---|---|
| trades | Open/closed trades with full cost model. +30 research columns (Session 8). +signal_direction (Session 16). |
| trade_tranches | Partial exit tranche records |
| signals | **DEPRECATED** — kept, no new inserts |
| market_state_history | Daily regime + MQI + high_vol_override |
| risk_events | Permanent audit trail of circuit breakers, kill line |
| system_log | Startup, errors, peak equity storage |

### 8 New Tables (Session 8)

| Table | Columns | Purpose |
|---|---|---|
| signal_intelligence_log | 87+ cols (+12 forward-return + signal_direction in Session 16) | **Primary signal table.** Every signal event. |
| agent_logs | 22 | LLM call audit trail |
| daily_portfolio_snapshot | 40 | Equity curve |
| pattern_memory | 22 | Setup fingerprints (permanent) |
| scan_log | 22 | Scan cycle records |
| system_health_log | 19 | API + Oracle metrics (every 1 min) |
| strategy_performance | 28 | Computed rollup |
| agent_weight_log | 20 | Recalibration history |

### Session 16 Schema Additions

```sql
ALTER TABLE signal_intelligence_log ADD COLUMN IF NOT EXISTS
  forward_return_1d NUMERIC,
  forward_return_3d NUMERIC,
  forward_return_5d NUMERIC,
  forward_return_10d NUMERIC,
  forward_return_20d NUMERIC,
  pnl_1d NUMERIC,
  pnl_3d NUMERIC,
  pnl_5d NUMERIC,
  pnl_10d NUMERIC,
  pnl_20d NUMERIC,
  raw_signal_value NUMERIC,
  signal_direction TEXT;  -- LONG / SHORT

ALTER TABLE trades ADD COLUMN IF NOT EXISTS
  signal_direction TEXT DEFAULT 'LONG';
Retention Policy (Supabase 500MB free tier)
Table	Retention	Action
signal_intelligence_log	90 days	Export CSV -> delete
agent_logs	180 days	Export -> delete
market_state_history	365 days	Export -> delete
trades, positions, pattern_memory, agent_weight_log	Permanent	—
Cleanup job	Weekly	Sunday 2 AM via GitHub Actions
signal_intelligence_log.signal_type ENUM
text

GENERATED, PRE_FILTERED, DEBATE_REJECTED, APPROVED, EXPIRED, EXECUTED, CLOSED,
MISSED_FILTERED, MISSED_REJECTED, MISSED_EXPIRED, GHOST_SIGNAL
2. MARKET STATE ENGINE (4-Factor)
Module: core/market_state.py
Runs: 8:30 AM IST daily via morning_routine() in main.py
Output: (market_state, total_score, vix, high_vol_override)

Each factor scores +1 / 0 / -1. Saved to market_state_history table.

Factor 1 — Price vs Nifty EMA200
Nifty close > EMA200 by more than 1% -> +1
Nifty close < EMA200 by more than 1% -> -1
Within +/-1% -> 0
Data source: yf.Ticker("^NSEI").history(period="1y") (NOT yf.download — MS02/MS03 fix avoids MultiIndex)
Factor 2 — Breadth (Nifty 500)
NOT IMPLEMENTED YET. Returns 0 (Phase 2 placeholder).
Original spec: >65% above EMA50 -> +1 | <35% -> -1 | 35-65% -> 0
Factor 3 — India VIX
VIX < 14 -> +1
VIX > 20 -> -1
14 <= VIX <= 20 -> 0
Data source: yf.Ticker("^INDIAVIX").history(period="5d")
Default on failure: 15.0 (NEUTRAL)
Factor 4 — FII Flow (T-1)
NOT IMPLEMENTED YET. Returns 0 (Phase 2 placeholder).
Original spec: Net FII >Rs.500Cr buy -> +1 | >Rs.500Cr sell -> -1
FII T-1 data only — NSE publishes ~6-7 PM. Label everywhere as "FII Trend (T-1)".
Intraday proxy (planned): Nifty Futures premium vs spot.
Classification
Total Score	Market State
>= +2	BULL
-1 to +1	NEUTRAL
<= -2	BEAR
HIGH VOL OVERRIDE
Condition: VIX > 25
Effect: Overrides ALL regime classifications. No new directional positions today.
Capital impact (per Master spec): Growth pool -20%, Cash +10%
Implemented as: high_vol_override = vix > 25 boolean, logged to market_state_history
3. MARKET QUALITY INDEX (MQI) — 5-Factor
Module: core/mqi.py
Runs: 8:30 AM IST daily AFTER market state, via morning_routine() in main.py
Output: (mqi_level, signals_allowed, no_trade, mqi_pct)
Saves to: market_state_history table (same row as market state)

Each factor scores 0 / 1 / 2. Maximum = 10.

Factor 1 — ATR Compression — IMPLEMENTED
Compares current ATR(14) to 20-day average ATR
Ratio <= 0.8 -> 2 (compressed, clean trending)
Ratio <= 1.2 -> 1 (normal)
Ratio > 1.2 -> 0 (expanding, choppy)
Factor 2 — VIX Intraday Change — IMPLEMENTED
abs(VIX % change) < 5% -> 2
abs(VIX % change) < 10% -> 1
abs(VIX % change) >= 10% -> 0
Factor 3 — Market Breadth — PLACEHOLDER
Returns hardcoded 1 (Phase 2 placeholder)
Original spec: % of Nifty 500 stocks above EMA50
Factor 4 — MISSING
Original Master spec listed "Gap follow-through" — not implemented
Code only has 5 factors, not 6 as Master claims. Master doc was wrong on count.
Factor 5 — Event Proximity — IMPLEMENTED
Detects: F&O expiry, RBI MPC, Budget Day.

Condition	Score	Reason
Today is RBI MPC day OR F&O Monthly Expiry	0	High event risk
Today is RBI MPC eve OR Weekly Expiry Thursday OR Budget Week (forward window 3 days)	1	Medium event risk
No major events	2	Clean
RBI MPC dates hardcoded for 2026, 2027, 2028 (update annually — MPC_DATES_BY_YEAR dict)
Budget Day hardcoded: Feb 1 each year
Budget Week (FIX-W): forward-only window — only 3 days BEFORE and ON budget day (not symmetric)
F&O monthly expiry: Last Thursday of month
F&O weekly expiry: Every Thursday that's NOT monthly
Factor 6 — Opening Volume Quality — PLACEHOLDER
Returns hardcoded 1 (Phase 2 placeholder)
Original spec: First 30-min volume vs 20-day average
MQI Level Mapping (FIX-MQ13)
MQI %	Level	Signals Allowed	No-Trade Day
>= 70%	HIGH	2	False
>= 50%	MEDIUM	1	False
>= 30%	LOW	1 (FIX-MQ13: was 0)	False
< 30%	VERY LOW	0	True
No-Trade Day -> scanner disabled. Telegram: "MJONAI — MQI LOW. NO TRADE TODAY."

RESEARCH mode override: In main.py, RESEARCH mode sets _signals_allowed_today = 9999 regardless of MQI. Only LIVE mode enforces the limits above.

4. CONFIDENCE SCORING
Module: strategy/signal_scanner.py (calculate_confidence() function)
Used by: every signal before being passed to devil checks + agents.

Formula
text

Confidence = (Technical x 0.30) + (MTF x 0.25) + (Volatility x 0.20) +
             (Liquidity x 0.15) + (Context x 0.10)
Dual Gate — BOTH MUST PASS
Gate 1 — Component minimums (any fail -> AUTO-REJECT immediately, no formula):

Component	Minimum	Weight
Technical	60	0.30
MTF (Multi-TimeFrame)	75	0.25
Volatility	50	0.20
Liquidity	60	0.15
Context	40	0.10
Gate 2 — Weighted total >= 65. Below 65 -> AUTO-REJECT.

Component Scoring Detail
Technical (min 60): RSI directional range +20 | MACD crossover +20 | EMA aligned +20 | Supertrend +20 | Candle pattern +20. Need 3/5 minimum.

MTF (min 75): 4/4 timeframes agree -> 100 | 3/4 -> 75 | 2/4 -> 40 REJECT | 1/4 -> 0 REJECT

Volatility (min 50): ATR fits SL -> 100 | 75% of SL -> 75 | 50% of SL -> 50 | ATR > SL -> 0 REJECT. VIX adjustment: <14 +10 | 14-20 0 | 20-25 -15 | >25 -30.

Liquidity (min 60): Volume >2x avg -> 100 | 1.5-2x -> 80 | 1-1.5x -> 60 | <avg -> 20. Spread <0.1% +20 | 0.1-0.2% 0 | 0.2-0.5% -20 | >0.5% AUTO-REJECT.

Context (min 40): FII flow matches +40 | Sector aligned +30 | No event 24h +30 | Major event -50 | FII selling 3+ days -30.

Live thresholds (in core/constants.py)
Python

LIVE_CONFIDENCE_MIN     = 65   # LIVE mode minimum
RESEARCH_CONFIDENCE_MIN = 50   # RESEARCH mode minimum (more lenient for data gen)
5. AI DEBATE ROOM — 8 DEVIL CHECKS
Module: risk/devil_checks.py
Architectural separation: Devil checks are deterministic Python, not LLM. They run BEFORE any LLM agent. Cannot hallucinate. Binary pass/fail.

All 8 functions exist in code (verified via grep):

#	Function	Logic
1	check_gap_risk(sl_distance, overnight_move)	Fail if overnight_move > sl_distance x 1.5
2	check_liquidity(bid_ask_spread_pct)	Fail if spread > 0.5%
3	check_data_quality(quality_score)	Fail if quality < 85
4	check_pattern_memory(setup_hash, lookback_days=90)	Fail if setup failed 3+ times in 90 days
5	check_correlation(instrument_key, active_positions)	Fail if correlation > 0.80 with any open position
6	check_real_rr(entry, sl, target, costs)	Fail if real RR (after costs) < 2.0
7	check_portfolio_limits(open_positions, growth_pool_pct)	Fail if MAX_POSITIONS reached OR growth pool >= 80%
8	check_event_risk(calendar_events)	Fail if HIGH-impact event within 4 hours
Aggregator: run_all_devil_checks(...) returns (passed: bool, results: list[dict]).

Pipeline
ALL 8 must pass -> proceeds to LLM agents (Bull -> Supervisor)
ANY fail -> VETOED. LLM may explain why but does NOT decide the veto.
RESEARCH vs LIVE behavior (per Master Session 7 insight)
LIVE mode: Devil checks VETO (block trade)
RESEARCH mode: Devil checks WARN + log outcome (let trade through, mark it). This lets us discover empirically whether each check prevents losses.
6. AI AGENT STACK
Agent 1 — Bull (Technical Analyst) — TIER 1 ACTIVE
Module: agents/bull.py
Model: Groq llama-3.3-70b-versatile
Fallback: llama-3.1-8b-instant (confidence capped at 0.8 in fallback)
Rate limit: 2.1s minimum between calls (FIX-M)
Consecutive failure handling: 3 failures -> safe NEUTRAL
Output schema:

JSON

{
  "verdict": "STRONG_BUY|BUY|NEUTRAL|SELL",
  "confidence": 78,
  "key_reasons": ["RSI 62 bullish", "MACD confirmed", "4/4 TF aligned"],
  "regime_note": "VIX 13.4 — no penalty",
  "pattern_history": "66% win rate 90 days"
}
Agent 2 — Supervisor (Final Decision) — TIER 1 ACTIVE
Module: agents/supervisor.py
Model: Gemini models/gemini-2.5-flash (SDK: google-genai==1.74.0)
Fallback: llama-3.3-70b-versatile
Optimization (FIX-SV05): Only calls Gemini on APPROVE path (saves quota)
Decision rules: Code-enforced, NOT LLM:
Any devil check failed -> REJECT
Bull NEUTRAL/SELL -> REJECT (Tier 1)
Confidence < 65 -> REJECT
Real RR < 2.0 -> REJECT
Bull BUY/STRONG_BUY + confidence >=65 + all checks pass -> APPROVE
Agent 3 — Bear — SCAFFOLDED, NOT WIRED
Module: agents/bear.py (exists, 322 lines, complete)
Status: No file imports it. Reserved for Phase 2.
Agents 4-5 — Economist, Devil LLM — NOT BUILT YET
7. SIGNAL LIFECYCLE PIPELINE
Module: strategy/signal_scanner.py (scan_signals() function)
Runs: Every 15 minutes during market hours (9:30 AM - 3:15 PM IST), via scan_and_execute() in main.py.

Daily Limits
LIVE Tier 1: 2 signals/day
LIVE All Tiers: 4 signals/day
RESEARCH mode: 9999 (unlimited — data generation)
Rejected signals: unlimited. All logged to signal_intelligence_log. All feed Pattern Memory.

9-Stage Pipeline
MQI check — VERY LOW -> stop, send No-Trade message
Scanner runs every 15 min on Nifty 500 watchlist
Pre-filter: technical min (3/5 indicators), liquidity min, time-of-day window
All 7 strategies execute per symbol (independent — see SS19 fix)
Devil checks (8 deterministic checks)
Confidence scoring (dual-gate)
Agent debate (Bull -> Supervisor; Tier 1 only — Bear skipped)
Priority queue: if over daily limit, rank by confidence x real_RR
Approved signals: Telegram alert + Discord (future) + Dashboard (future) + logged
Staleness Logic
Time after signal	Effective Confidence
0 min	100%
5 min	95%
10 min	85%
15 min	70%
20 min	EXPIRED
Plus: Price moves >0.3% from entry -> immediate expiry.

Time-of-Day Window
Window	Behavior
9:15-9:30 AM	EXCLUDED — opening noise
9:30-10:30 AM	HIGH — best window
10:30-12:00 PM	MEDIUM-HIGH — normal
12:00-2:00 PM	MEDIUM — reduced threshold
2:00-3:00 PM	HIGH — pre-close institutional
3:00-3:15 PM	EXCLUDED — too close to close
After 3:15 PM	NONE — close intraday only
Scan Overlap Lock (Session 16)
Global flag _scan_running in signal_scanner.py prevents concurrent scan execution. If a scan is already running when the 15-min trigger fires, the new scan is skipped (logged with elapsed time).

8. TRIPLE BARRIER EXIT LOGIC
Module: execution/paper.py
First barrier hit exits the trade: SL | Target | Time

Timeframe	SL	Target	Time Barrier
Intraday	1% risk	RR >= 2.0	3:15 PM — no exceptions
Swing	1.5% risk	2-3R	7 trading days
Positional	2% risk	Structure + trailing	40 trading days
Trailing Stop (Ratchet Rule)
At 1R profit -> SL moves to breakeven (entry + costs)
At 2R profit -> SL moves to 1R level
After 2R -> trail using best of:
15-min swing low/high
EMA21 (15m)
Price - (1.5 x ATR14)
RATCHET RULE: SL only moves toward profit. Never backward. Ever.

HIGH VIX Buffer
VIX > 22 -> add 0.5 x ATR to all trailing distances.

LONG vs SHORT P&L
LONG: (exit - entry) x qty
SHORT: (entry - exit) x qty
SL location: LONG below entry / SHORT above entry
Target location: LONG above entry / SHORT below entry
9. ACTIVE STRATEGIES (7)
Registry: core/constants.py::STRATEGY_REGISTRY
Instances: strategy/signal_scanner.py (_S01 through _S07)
Mode: All 7 run independently per symbol per scan (per SS19 fix — was "first wins" before)

ID	Name	File	Type	Direction	Status
S01	MomentumRSI	strategy/registry/momentum_rsi.py	Swing 3-10d	LONG	ACTIVE
S02	MeanReversion	strategy/registry/mean_reversion.py	Swing 3-7d	LONG	ACTIVE
S03	TurtleBreakout	strategy/registry/turtle_breakout.py	Positional 2-8w	LONG	ACTIVE
S04	BollingerSqueeze	strategy/registry/bollinger_squeeze.py	Swing 3-10d	LONG	ACTIVE
S05	PriceActionCandles	strategy/registry/price_action.py	Swing 2-7d	LONG	ACTIVE
S06	MomentumShort	strategy/registry/momentum_short.py	Swing 3-10d	SHORT	ACTIVE
S07	MeanReversionShort	strategy/registry/mean_reversion_short.py	Swing 3-7d	SHORT	ACTIVE
Logic Summary
S01: RSI 55-70 + EMA 20/50/200 aligned + MACD bullish + Supertrend bull + Hammer/Engulfing candle
S02: RSI <30 + BB lower (2SD) + volume spike + above EMA200 (no falling knife)
S03: 20-day high breakout + volume >1.5x + above EMA200 + ATR expanding. SL = 10-day low (Turtle). Positional 2% risk.
S04: BB width <75% avg (squeeze) -> expansion + MACD bullish + RSI >50
S05: 37 bullish TA-Lib candle patterns + above EMA50 (mandatory) + volume >1.2x
S06: RSI 30-45 (bearish momentum) + MACD bearish + EMA aligned down + Supertrend bear + Evening/Shooting Star
S07: RSI >70 (overbought) + above BB upper + volume spike + below EMA200
Strategy Lifecycle (per Master spec — not yet enforced in code)
BIRTH -> paper 30+ days -> min 30 trades
EVALUATION (100 trades): >55% win + Sharpe >0.8 -> PROMISING | 45-55% -> INVESTIGATE | <45% -> REVIEW
GRADUATION (200+ trades): >55% win + Sharpe >1.0 + DD <15% + works in 2/3 regimes -> LIVE
RETIREMENT: <40% win after 100 trades -> ARCHIVED (not deleted)
Common Output Schema (from BaseStrategy)
Python

{
  "strategy_id": "S01_MomentumRSI",
  "strategy_version": "1.0",
  "symbol": "RELIANCE",
  "signal_type": "BUY",
  "signal_direction": "LONG",
  "technical_score": 80,
  "confidence": 74.0,
  "reasons": ["...", "..."],
  "timeframe": "SWING"
}
10. SCHEDULER JOBS
Module: orchestration/scheduler_setup.py

Time IST	Job	Function
08:25	Daily state reset	reset_daily_state()
08:25	AngelOne reconnect	connect_angelone() (trading days only)
08:30	Morning routine	Market state + MQI + macro
09:30 -> 15:15 every 15 min	Signal scan	scan_and_execute() (internal time gate)
15:35	EOD summary	eod_routine()
16:00	Forward returns calc	_calculate_forward_returns()
16:30	Daily research report	_generate_daily_research_report()
Sunday 10:00	Weekly Alphalens report	_generate_weekly_alphalens_report()
Every 1 min	Trade monitor	monitor_trades() (market hours only)
11. KEY DRIFT FROM ORIGINAL MASTER SPEC
These are places where the code does something different from what Master v2.0 said. The code is the truth.

Concept	Master said	Code does	Severity
MQI factors	6 factors	5 factors (no "gap follow-through")	LOW
Market State Factor 2 (Breadth)	Computed from Nifty 500	Hardcoded 0 (placeholder)	MED
Market State Factor 4 (FII)	NSE T-1 + intraday proxy	Hardcoded 0 (placeholder)	MED
MQI Factor 3 (Breadth)	Computed	Hardcoded 1 (placeholder)	LOW
MQI Factor 6 (Volume Quality)	Computed	Hardcoded 1 (placeholder)	LOW
Confidence formula	Master defined	calculate_confidence() exists in scanner — verify exact formula matches	NEEDS AUDIT
Triple Barrier	Master defined	execution/paper.py implements — verify all 3 timeframes	NEEDS AUDIT
Note: The above table identifies areas where focused code review is needed to bring spec and reality into alignment. Items marked NEEDS AUDIT should be checked during a future maintenance session.
