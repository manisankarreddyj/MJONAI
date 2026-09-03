# MJONAI — MASTER CONTEXT FILE v2.0

**Architecture | Rules | Research Philosophy | Single Source of Truth**

**Founder: Mani Sankar Reddy (MJ Reddy) | Status: Research Lab Active**

**Last Updated: 06 May 2026 — Session 16 Complete**

---

```

════════════════════════════════════════════════════

MJONAI MASTER v2.0

════════════════════════════════════════════════════

Version:         v2.0

Previous:        v1.5 (01 May 2026 — Session 7)

Updated:         06 May 2026 — Session 16

Commit:          29d6643

Oracle PID:      98662

System Health:   ~99.5/100

Peak Equity:     ₹209,037

Open Trades:     0 (clean state)

Closed Trades:   8 total (all research_valid=FALSE)

SYSTEM_MODE:     RESEARCH

Active Strategies: 7 (S01-S07)

Forward Returns: ENABLED

Signal Direction: ENABLED (LONG/SHORT)

════════════════════════════════════════════════════

```

---

## HOW TO USE THIS FILE

**Two documents must be read before any session — in this order:**

1. `MJONAI_MASTER_v2.0.md` — What the system IS. Architecture. Rules. Philosophy. Research methodology.
2. `MJONAI_HANDOVER_v3.0.md` — What is BUILT. Files. Functions. Bugs. Current state. Session history.

**Rules for every AI session:**

1. Read all files completely before responding
2. Confirm understanding by answering verification questions
3. Never introduce patterns not in these files
4. Never assume — ask before building
5. Never over-engineer
6. One file changed per session maximum
7. Discuss before writing a single line of code

---

## SECTION 1 — SYSTEM IDENTITY

**SYSTEM NAME:** MJONAI (M-Jon-AI) — MJ = Mani Janga | ON = Always On (24/7) | AI = Intelligence layer

**FOUNDER:** Mani Sankar Reddy (MJ Reddy)

**PHASE:** Research Lab Active — Paper Trading Live on Oracle Cloud

**SCOPE:** Personal use only. Future: Personal → Family → SaaS (if proven)

**WHAT MJONAI IS:** A personal financial OS and research platform that finds opportunities across asset classes, tests multiple strategies simultaneously, evaluates signals via AI agent debate, enforces institutional-grade risk rules, learns from every outcome, and compounds wealth through proven strategies.

**WHAT MJONAI IS NOT:** Not a trading bot. Not a signal app. Not a prediction engine. Not a retail tool.

**PERSONALITY:** Conservative but Consistent. Target: 12-18% annual returns net of costs and taxes.

**CORE MANDATE — NEVER CHANGE:**

> Capital Protection > Risk-Adjusted Growth > Profit

**RESEARCH LAB MANDATE (v2.0):**

> Paper trading = Research Laboratory. Not practice. Not simulation.
> Goal: Discover genuine edges through systematic testing.
> Method: Run everything. Track everything. Analyze everything.
> Deploy only what the data proves works.

---

## SECTION 2 — THE FUNDAMENTAL INSIGHT

### Paper Trading Is A Research Laboratory

```

WRONG THINKING (what we were doing until Session 7):

  Paper trading = practice for real money

  Apply real money constraints to paper trades

  Conservative. Restrictive. Safe.

  Result: 7 trades in weeks = meaningless data

CORRECT THINKING (discovered Session 7):

  Paper trading = research laboratory

  Goal: extract maximum information from market

  Expansive. Scientific. Data-driven.

  Result: 500 trades in weeks = statistical truth

The analogy:

  A pharmaceutical company does not restrict

  drug trials to 7 patients.

  They test on thousands to find truth.

  

  We were running a 7-patient drug trial

  on a ₹200,000 trading system.

  

  That tells us almost nothing.

  

  500+ paper trades across multiple strategies

  in different market regimes

  with full audit trail

  THAT tells us something.

The core shift:

  Paper mode ≠ simulated real money

  Paper mode = hypothesis testing machine

Every paper trade = one data point in an experiment.

The experiment: "Does this signal have genuine edge?"

The answer requires: statistical significance (100+ trades minimum).

```

---

## SECTION 3 — THE NORTH STAR

```

All discussion, all tools, all strategies, all research

serves ONE goal:

FIND 3-5 GENUINE EDGES IN INDIAN MARKETS

An edge is:

  1. Wins more than it loses

  2. Wins in MULTIPLE market regimes (not just bull)

  3. Wins AFTER all costs and taxes

  4. Is EXPLAINABLE (we know WHY it works)

  5. Is ROBUST (parameter changes don't kill it)

  6. SCALES with capital

3 proven edges = MJONAI is complete.

Everything else = supporting infrastructure.

The Jim Simons lesson:

  Renaissance Technologies tested thousands of signals.

  Most failed.

  A handful worked consistently.

  Those few, compounded over decades,

  made it the greatest fund in history.

  

  We are not building a thousand signals.

  We are systematically finding 3-5.

  

  The paper lab generates the data.

  The data reveals the edges.

  We listen to the data.

Timeline reality:

  Month 1-2:  Generate data (research mode, 500+ trades)

  Month 3:    First Alphalens analysis (IC per signal)

  Month 4:    Iterate on findings

  Month 5-6:  Statistical confidence building

  Month 7+:   Graduate proven strategies to live trading

  

  There are no shortcuts.

  The data will tell us what works.

  Our job is to listen.

```

---

## SECTION 4 — TECHNOLOGY STACK (LOCKED)

**LANGUAGE:** Python 3.11 ONLY. Not 3.12, 3.13, or 3.10.

**⚠️ WSL2 MANDATORY:** All Python runs inside WSL2 Ubuntu on Windows 10/11. Never in Windows CMD/PowerShell. TA-Lib: `sudo apt install ta-lib && pip install TA-Lib`

**⚠️ RAM CONSTRAINT:** 16GB RAM. Ollama (~8GB) = fallback only. Load on API failure → inference → unload. Never concurrent with main system.

**⚠️ MODEL UPDATES (v2.0):**

```
GROQ:
  CURRENT:    llama-3.3-70b-versatile ✅
  FALLBACK:   llama-3.1-8b-instant ✅
  RATE LIMIT: 2.1s minimum between calls (FIX-M)

GEMINI:
  CURRENT SDK:      google-genai==1.74.0 ✅
  CURRENT MODEL:    models/gemini-2.5-flash ✅
  USAGE:            system_instruction via GenerateContentConfig (FIX-H)

USAGE:
  from google import genai
  client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
  response = client.models.generate_content(
      model="models/gemini-2.5-flash",
      contents="prompt",
      config=types.GenerateContentConfig(
          system_instruction=SYSTEM_PROMPT,
          max_output_tokens=MAX_TOKENS,
      )
  )
```

**CORE STACK:**

| Component | Tool | Cost | Status |
|-----------|------|------|--------|
| Backend | FastAPI | ₹0 | ✅ Active |
| Database | Supabase PostgreSQL + pgvector (Mumbai) | ₹0 | ✅ Active |
| Cache | Local Redis → Upstash Phase 2 | ₹0 | Planned |
| Vector DB | ChromaDB local | ₹0 | Planned |
| Embeddings | sentence-transformers local | ₹0 | Planned |
| Frontend | Next.js 15 | ₹0 | Planned |
| Charts | TradingView Lightweight Charts | ₹0 | Planned |
| Indicators | TA-Lib 0.6.8 via WSL2 | ₹0 | ✅ Active |
| Backtest | VectorBT / Backtrader | ₹0 | Planned |
| Task Queue | APScheduler 1.2.2 → Celery Phase 2 | ₹0 | ✅ Active |
| Overnight | GitHub Actions (2000 min/month free) | ₹0 | Planned |
| Version | Git + GitHub private | ₹0 | ✅ Active |
| Local AI | Ollama + Llama 3.1 8B | ₹0 | Fallback only |

**AI AGENT STACK:**

| Agent | Model | Package | Status |
|-------|-------|---------|--------|
| Bull | llama-3.3-70b-versatile | groq==1.2.0 | ✅ LIVE |
| Bull Fallback | llama-3.1-8b-instant | groq==1.2.0 | ✅ Ready |
| Supervisor | models/gemini-2.5-flash | google-genai==1.74.0 | ✅ LIVE |
| Bear | Gemini 2.5 Flash + FinBERT | — | Phase 2 |
| Economist | RSS + FRED API | — | Phase 2 |
| Devil LLM | llama-3.3-70b-versatile | groq==1.2.0 | Phase 3 |

**RESEARCH TOOL STACK:**

| # | Tool | Purpose | Install |
|---|------|---------|---------|
| 1 | pandas-market-calendars | NSE holiday calendar | pip install pandas-market-calendars |
| 2 | alphalens-reloaded | Signal alpha testing | pip install alphalens-reloaded |
| 3 | quantstats | Portfolio performance reports | pip install quantstats |
| 4 | duckdb | Fast SQL on millions of trades | pip install duckdb |
| 5 | mlflow | Experiment tracking | pip install mlflow |
| 6 | pandas-ta | 130+ additional indicators | pip install pandas-ta |
| 7 | statsmodels | ARIMA, cointegration, stat tests | pip install statsmodels |
| 8 | arch | GARCH volatility models | pip install arch |
| 9 | pyportfolioopt | Portfolio optimization | pip install PyPortfolioOpt |
| 10 | tsfresh | 800+ automated time series features | pip install tsfresh |

**HARDWARE:**

```
LOCAL:
  HP EliteBook | Intel vPro i5 | 16GB RAM | 256GB
  Windows 10/11 + WSL2 Ubuntu 22.04
  WiFi primary | Mobile hotspot backup

ORACLE CLOUD (production 24/7):
  VM.Standard.E2.1.Micro | 1 OCPU | 1GB RAM | 48.27GB
  Ubuntu 22.04.5 LTS | IP: 140.245.234.150
  Path: /home/ubuntu/mjonai-build
  Service: mjonai.service (systemd)
  SSH: ssh -i ~/.ssh/ssh-key-2026-04-27.key ubuntu@140.245.234.150
  Key backup: Bitwarden

ORACLE RULES:
  ❌ NEVER: do-release-upgrade or Ubuntu 24.04 upgrade
  ✅ Restart: weekends only | Kill Line reset: sudo systemctl restart mjonai
```

**COST MANDATE:** ₹0 recurring Phase 1. Upgrade only when performance demands AND returns justify it.

---

## SECTION 5 — FOLDER STRUCTURE (LOCKED)

```
mjonai/
├── core/
│   ├── constants.py          ✅ BUILT (v2.0 — 328 sectors, S06-S07)
│   ├── market_state.py       ✅ BUILT (FIX-L applied)
│   ├── mqi.py                ✅ BUILT (FIX-P, FIX-V, FIX-W, FIX-MQ13)
│   └── time_utils.py         ✅ BUILT (FIX-O year boundary)
├── data/
│   ├── angelone/
│   │   ├── websocket.py      ✅ BUILT (FIX-T stop_requested)
│   │   ├── token_map.py      ✅ BUILT (499 symbols)
│   │   └── nifty500_tokens.csv ✅ (499 tokens)
│   ├── shoonya/              credentials saved, not integrated
│   ├── earnings/             ✅ BUILT (FIX-K past earnings filter)
│   │   ├── __init__.py
│   │   └── earnings_check.py
│   └── market_state/
│       └── macro_check.py    ✅ BUILT
├── strategy/
│   ├── signal_scanner.py     ✅ BUILT (SS19, scan lock, S06-S07)
│   ├── fno/                  paper only, planned
│   ├── mcx/                  paper only, planned
│   ├── income/               Tier 3+
│   ├── stability/            Tier 3+
│   └── registry/
│       ├── base.py           ✅ BUILT
│       ├── momentum_rsi.py   ✅ S01 (NaN guards added)
│       ├── mean_reversion.py ✅ S02 (NaN guards added)
│       ├── turtle_breakout.py ✅ S03 (FIX-J turtle_sl)
│       ├── bollinger_squeeze.py ✅ S04 (NaN guards added)
│       ├── price_action.py   ✅ S05 (FIX-I 37 patterns)
│       ├── momentum_short.py ✅ S06 NEW (bearish momentum)
│       └── mean_reversion_short.py ✅ S07 NEW (overbought reversal)
├── analysis/
│   ├── technical/            planned standalone
│   ├── volatility/           planned
│   ├── flow/                 Phase 2
│   ├── fundamental/          Phase 2
│   ├── sentiment/            Phase 2 (FinBERT)
│   └── pattern_memory/       Phase 2
├── agents/                   ✅ BUILT
│   ├── __init__.py           ✅
│   ├── bull.py               ✅ Groq 70B (FIX-M rate limit)
│   ├── supervisor.py         ✅ Gemini 2.5 (FIX-H, FIX-SV05)
│   ├── bear.py               ✅ Gemini 2.5 (FIX-H applied)
│   ├── economist.py          Phase 2
│   └── devil.py              Phase 3
├── risk/
│   ├── trade_risk.py         ✅ BUILT (SHORT support, parameters)
│   ├── emergency_triggers.py ✅ BUILT (FIX-B naming fixed)
│   ├── devil_checks.py       ✅ BUILT (328 sectors)
│   ├── portfolio_risk.py     planned
│   └── correlation.py        planned
├── orchestrator/             planned (all 3 files)
├── execution/
│   ├── paper.py              ✅ BUILT (SHORT signal support)
│   ├── broker.py             Tier 4 only
│   ├── gtt.py                Tier 4 only
│   └── order_manager.py      planned
├── reporting/                planned (all 4 files)
├── communication/
│   ├── telegram.py           ✅ BUILT (FIX-Y SYSTEM_MODE)
│   ├── telegram_commands.py  ✅ BUILT (TC01, TC12, TC18, TC19)
│   ├── discord.py            planned
│   └── alerts.py             planned
├── knowledge/                Phase 2 (all subfolders)
├── db/
│   ├── models.py             planned (SQLAlchemy)
│   ├── migrations/           planned (Alembic)
│   └── repository.py         ✅ BUILT (52 functions, 3 new)
├── backtest/                 planned (all 4 files)
├── research/                 ✅ BUILT (Session 16)
│   ├── __init__.py           ✅
│   ├── forward_returns.py    ✅ NEW (Alphalens integration)
│   ├── factor_analysis/      planned
│   ├── strategy_comparison/  planned
│   ├── regime_analysis/      planned
│   └── reports/              planned
├── utils/                    planned
├── tests/                    planned
├── .github/workflows/        planned
├── main.py                   ✅ BUILT (research scheduler)
├── requirements.txt          ✅ BUILT
└── .env                      NEVER commit — in .gitignore
```

**DEPENDENCY FLOW (one direction only):**

`data → strategy → agents → risk → orchestrator → execution → reporting → communication`

No circular imports. No business logic in repository.py. No imports from higher authority level.

---

## SECTION 6 — DATABASE SCHEMA (17 TABLES)

**STANDARDS:** UUID PK, created_at/updated_at TIMESTAMPTZ, is_deleted BOOLEAN DEFAULT FALSE. Soft delete only — never hard delete.

**RETENTION (Supabase 500MB free tier):**

- signal_intelligence_log: 90-day → export CSV → delete
- agent_logs: 180-day → export → delete
- market_state_history: 365-day → export → delete
- trades, positions, pattern_memory, agent_weight_log: permanent
- Cleanup: GitHub Actions every Sunday 2 AM

| Table | Purpose |
|-------|---------|
| users | Founder profile and settings |
| portfolio_state | Capital allocation across pillars |
| positions | Open positions with live P&L |
| trades | Completed trades with full cost and tax breakdown |
| signals | Generated signals with metadata and outcome |
| pattern_memory | Setup fingerprints and outcomes (permanent) |
| agent_logs | Per-signal agent debate records (180-day) |
| agent_weight_log | Agent recalibration history |
| risk_events | Circuit breaker and emergency trigger log (permanent) |
| market_state_history | Daily MQI score and regime records (365-day) |
| income_tracking | Dividends, covered call income, yield income |
| signal_intelligence_log | ALL signal events including missed and ghost (90-day) |
| system_log | System health, errors, startup events |
| scan_log | Scan cycle records (Session 8) |
| system_health_log | API + Oracle metrics (Session 8) |
| strategy_performance | Computed rollup (Session 8) |
| daily_portfolio_snapshot | Equity curve (Session 8) |

**NEW COLUMNS ADDED (Session 16):**

```sql
-- Forward returns for Alphalens IC analysis
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

-- Trade direction tracking
ALTER TABLE trades ADD COLUMN IF NOT EXISTS
  signal_direction TEXT DEFAULT 'LONG';  -- LONG / SHORT
```

**signal_intelligence_log signal_type ENUM:**

GENERATED, PRE_FILTERED, DEBATE_REJECTED, APPROVED, EXPIRED, EXECUTED, CLOSED, MISSED_FILTERED, MISSED_REJECTED, MISSED_EXPIRED, GHOST_SIGNAL

---

## SECTION 7 — AUTHORITY HIERARCHY (NEVER CHANGE)

```
Risk Engine        → Constitutional law
Orchestrator       → Capital governor
Allocation Engine  → Capital distributor
AI Debate Room     → Advisory only
Signal Engine      → Opportunity finder
Execution Engine   → Order placer
```

**GOLDEN RULES — HARDCODED, NEVER OVERRIDE:**

1. Capital protection over profit — always
2. Never override stop loss once set
3. Risk Engine cannot be overridden by AI or signal
4. AI is advisory only — never authority
5. Allocation decides IF trade happens — not signal
6. System must survive worst-case scenarios
7. No trade without execution feasibility check
8. All P&L shown NET of costs and tax — never gross

---

## SECTION 8 — THREE PILLAR CAPITAL MODEL

**PILLAR 1 — GROWTH (50% base):** Equity (Tier 1), F&O (Tier 2+), MCX (Tier 2+), Crypto (Tier 4).

Regime adjustments: Bull +10% (max 70%) | Bear -15% (min 30%) | High Vol -20% (min 30%)

**PILLAR 2 — STABILITY (30% base) — Tier 3+ only:**

65% Passive Core (AAA bonds, liquid funds, T-bills) | 30% Tactical Duration | 5% Permanent Gold (SGB primary, Gold ETF secondary)

**PILLAR 3 — INCOME (remaining) — Tier 3+ only:**

Target 12-15% annual yield. 40% Dividend Engine | 25% Covered Call | 20% CSP | 15% Bond/REIT Yield

**TIER 1 ALLOCATION:**

80% Equity swing/positional | 10% Emergency reserve (never touch) | 10% Opportunity reserve

**CRYPTO SANDBOX (Tier 4 only):** Max 5% total capital | Spot only | No leverage | 30% flat tax tracking

**GOLD RULE:** 5% of total portfolio permanently in Gold (SGB → Gold ETF → MCX Gold). Separate from MCX tactical trading.

**HARD LIMITS:** Growth: 30-70% | Stability: 20-50% | Cash: 10% minimum floor — never breach.

**REGIME CONFLICT:** Priority: High Vol > Bear > Bull. Always apply most conservative adjustment.

---

## SECTION 9 — RISK ENGINE

**RISK PER TRADE:**

| Timeframe | Max Risk |
|-----------|----------|
| Intraday | 1% of capital |
| Swing | 1.5% of capital |
| Positional | 2% of capital |

**REAL TRANSACTION COSTS:**

| Cost Item | Rate |
|-----------|------|
| Brokerage | ₹20 flat per order (AngelOne) |
| STT Delivery sell | 0.1% of turnover |
| STT Intraday sell | 0.025% of turnover |
| STT F&O options sell | 0.0625% of premium |
| STT F&O futures sell | 0.0125% of turnover |
| CTT MCX non-agri sell | 0.01% |
| Stamp duty buy (equity) | 0.003% |
| Stamp duty buy (F&O/MCX) | 0.002% |
| Exchange charge NSE | 0.00297% |
| GST on brokerage | 18% of brokerage |
| SEBI charge | 0.0001% of turnover |
| Slippage large cap | 0.05% |
| Slippage mid cap | 0.10-0.15% |
| Slippage F&O options | 0.5-1% on premium |
| Slippage MCX | 0.05-0.10% |

**POSITION SIZING:** `PositionSize = Capital × min(Risk%, Risk% × Wc × Wm)`

MIN function ensures 2% hard ceiling is never breached.

**Wc (Confidence Weight):** 65-70: 0.6 | 70-80: 0.8 | 80-90: 1.0 | 90+: 1.2

**Wm (Market Factor):** VIX >20: 0.5 | Normal: 1.0 | ADX >30: 1.2

**MAX OPEN POSITIONS:** Tier 1: 3 | All Tiers: 6 | Intraday: 4 | Swing: 3 | Positional: 2

Growth pool max deployment: 80% — 20% always held as buffer.

**SECTOR CAP:** Max 25% Growth pool per sector | Max 2 stocks per sector simultaneously.

**EMERGENCY TRIGGERS:**

RISK STOP (fire immediately):
- Daily loss ≥ 3% of capital
- Portfolio drawdown ≥ 15% from peak (Kill Line)
- Margin utilization ≥ 70%

Recovery: 24h (daily loss) | 7 days (Kill Line)

SOFT STOP (pause new signals):
- 3 consecutive losses
- VIX surges >15% in one hour
- Data lag >10 seconds

Recovery: 60 minutes auto-resume

HARD STOP (manual reset required):
- Price mismatch >0.5% AngelOne vs yfinance
- Manual SL override attempt
- API error rate >5% in 15 minutes

Recovery: Manual by MJ Reddy only

**KILL LINE vs LEVEL 3:** Kill Line = primary automated protection (trading failure). Level 3 = only if Kill Line fired but system FAILED to execute close (system integrity failure). Independent concepts.

---

## SECTION 10 — MARKET QUALITY INDEX (MQI)

Calculated BEFORE signal generation. Very Low = scanner disabled.

**SIX FACTORS:**

1. ATR compression: Current ATR(14) vs 20-day average
2. India VIX relative intraday change %
3. Market breadth: % Nifty 500 stocks above EMA50
4. Gap follow-through: did gap sustain 30 min after open?
5. Event proximity: RBI, FOMC, Budget, Expiry today/tomorrow?
6. Opening volume: first 30-min vs 20-day average

| MQI Level | Signals Allowed (Tier 1) |
|-----------|--------------------------|
| High | 2 |
| Medium | 1 |
| Low | 1 (FIX-MQ13: was 0, now allows 1) |
| Very Low | NO-TRADE DAY — scanner disabled |

**NO-TRADE DAY:** Scanner disabled. Telegram: "MJONAI — MQI LOW. NO TRADE TODAY."

---

## SECTION 11 — MARKET STATE ENGINE

Runs 8:30 AM daily. Each factor scores +1/0/-1.

**Factor 1 — Price vs Nifty EMA200:** >EMA200 → +1 | <EMA200 → -1 | within ±1% → 0

**Factor 2 — Breadth (Nifty 500):** >65% above EMA50 → +1 | <35% → -1 | 35-65% → 0

**Factor 3 — India VIX:** <14 → +1 | 14-20 → 0 | >20 → -1

**Factor 4 — FII Flow (T-1):** ⚠️ Previous day only. NSE publishes ~6-7 PM. Labelled "FII Trend (T-1)" everywhere.

Net FII >₹500Cr buy → +1 | >₹500Cr sell → -1 | between → 0

**Intraday FII Proxy:** Nifty Futures premium vs spot. >0.1% premium = bullish bias. Approximate only.

**Classification:** Score ≥+2 → BULL | ≤-2 → BEAR | -1 to +1 → NEUTRAL

**HIGH VOL OVERRIDE:** VIX >25 overrides all. Growth -20%, Cash +10%. No new directional positions.

---

## SECTION 12 — CONFIDENCE SCORING

```
Confidence = (Technical × 0.30) + (MTF × 0.25) + (Volatility × 0.20) +
             (Liquidity × 0.15) + (Context × 0.10)
```

**DUAL GATE — BOTH MUST PASS:**

- Gate 1: Each component must meet minimum. Fail any → AUTO-REJECT immediately (no formula).
- Gate 2: Weighted total ≥ 65. Below 65 → AUTO-REJECT.

```python
def calculate_confidence(technical, mtf, volatility, liquidity, context):
    if technical < 60: return reject("Technical below 60")
    if mtf < 75:       return reject("MTF below 75 (need 3/4 timeframes)")
    if volatility < 50: return reject("Volatility below 50")
    if liquidity < 60: return reject("Liquidity below 60")
    if context < 40:   return reject("Context below 40")
    total = (technical*0.30 + mtf*0.25 + volatility*0.20 + liquidity*0.15 + context*0.10)
    if total < 65: return reject(f"Total {total:.1f} below 65")
    return approve(total)
```

**TECHNICAL (min 60):** RSI directional range: +20 | MACD crossover: +20 | EMA aligned: +20 | Supertrend: +20 | Candle pattern: +20. Min 3/5 required.

**MTF (min 75):** 4/4 TF agree: 100 | 3/4: 75 | 2/4: 40 REJECT | 1/4: 0 REJECT

**VOLATILITY (min 50):** ATR fits SL: 100 | 75% of SL: 75 | 50% of SL: 50 | ATR > SL: 0 REJECT

VIX adjustments: <14: +10 | 14-20: 0 | 20-25: -15 | >25: -30

**LIQUIDITY (min 60):** Vol >2× avg: 100 | 1.5-2×: 80 | 1-1.5×: 60 | <avg: 20

Spread <0.1%: +20 | 0.1-0.2%: 0 | 0.2-0.5%: -20 | >0.5%: AUTO-REJECT

**CONTEXT (min 40):** FII flow matches: +40 | Sector aligned: +30 | No event 24h: +30 | Major event: -50 | FII selling 3+ days: -30

---

## SECTION 13 — AI DEBATE ROOM

**ARCHITECTURAL SEPARATION (critical):**

- `risk/devil_checks.py` — deterministic Python code. Part of Risk Engine. Runs BEFORE any LLM. Binary pass/fail. Cannot hallucinate.
- `agents/` — LLM agents. Advisory only. Never make hard decisions.

**DEVIL CHECKS (8) — TIER 1 ACTIVE:**

```python
def check_gap_risk(sl_distance, overnight_move):
    if overnight_move > sl_distance * 1.5: return False, "Gap risk exceeds 1.5× SL"
    return True, "Gap risk acceptable"

def check_liquidity(bid_ask_spread_pct):
    if bid_ask_spread_pct > 0.5: return False, "Spread > 0.5%"
    return True, "Liquidity acceptable"

def check_data_quality(quality_score):
    if quality_score < 85: return False, f"Data quality {quality_score} < 85%"
    return True, "Data quality acceptable"

def check_pattern_memory(setup_hash, lookback_days=90):
    failures = query_pattern_failures(setup_hash, lookback_days)
    if failures >= 3: return False, f"Setup failed {failures}× in {lookback_days} days"
    return True, f"Pattern acceptable ({failures} recent failures)"

def check_correlation(instrument_key, active_positions):
    for pos in active_positions:
        if correlation(instrument_key, pos) > 0.80: return False, f"Correlated: {pos}"
    return True, "No correlation conflict"

def check_real_rr(entry, sl, target, costs):
    real_rr = (target - entry - costs) / (entry - sl + costs)
    if real_rr < 2.0: return False, f"Real RR {real_rr:.2f} < 2.0"
    return True, f"Real RR {real_rr:.2f} acceptable"

def check_portfolio_limits(open_positions, growth_pool_pct):
    if len(open_positions) >= MAX_POSITIONS: return False, "Max positions reached"
    if growth_pool_pct >= 80: return False, f"Growth pool at {growth_pool_pct:.0f}%"
    return True, "Portfolio limits acceptable"

def check_event_risk(calendar_events):
    for e in calendar_events:
        if e.hours_away < 4 and e.impact == "HIGH": return False, f"Event in {e.hours_away:.0f}h: {e.name}"
    return True, "No imminent event risk"
```

All pass → LLM agents. Any fail → VETOED. LLM explains why. LLM does NOT decide the veto.

**AGENT 1 — BULL (Technical Analyst) — TIER 1 ACTIVE**

Model: `llama-3.3-70b-versatile` | Fallback: `llama-3.1-8b-instant`

Output:
```json
{"verdict": "STRONG_BUY|BUY|NEUTRAL|SELL", "confidence": 78,
 "key_reasons": ["RSI 62 bullish", "MACD confirmed", "4/4 TF aligned"],
 "regime_note": "VIX 13.4 — no penalty", "pattern_history": "66% win rate 90 days"}
```

**AGENT 2 — BEAR (Fundamental + Sentiment) — TIER 2**

Model: Gemini 2.5 Flash + FinBERT | Fallback: Cohere

Hard rules: Promoter pledge >70% → BEARISH flag | CFO/MD insider buy <30 days → +20 bullish

Output:
```json
{"verdict": "BEARISH|CAUTION|NEUTRAL|BULLISH", "confidence": 71,
 "key_reasons": ["FII net buyer ₹1,240Cr", "PCR 1.18"], "red_flags": [], "insider_activity": "None"}
```

**AGENT 3 — ECONOMIST (Macro) — TIER 2**

Model: RSS + RBI DBIE + FRED API + DuckDuckGo | Fallback: Cached (max 1h stale)

Hard rules: MPC within 2 days → -20% confidence | FOMC within 2 days → -10% | RBI VRR 5+ days → bullish liquidity

Output:
```json
{"verdict": "BULLISH|NEUTRAL|BEARISH", "confidence": 74,
 "macro_regime": "BULL_CYCLE|LATE_CYCLE|BEAR_CYCLE|RECOVERY",
 "key_reasons": ["VIX 13.4", "RBI VRR 5 days"], "event_risks": [], "rbi_bias": "Easing"}
```

**AGENT 4 — DEVIL LLM (Explanation Only) — TIER 3**

Model: `llama-3.3-70b-versatile` | Fallback: Ollama (on-demand)

CANNOT veto. Identifies contradictions between agents. Adjusts confidence only (max -15 if risk score >80).

Output:
```json
{"risk_score": 45, "contradictions_found": [],
 "stress_points": ["Earnings in 8 days"], "confidence_adjustment": 0,
 "explanation": "All checks passed. Bull and Bear aligned."}
```

**AGENT 5 — SUPERVISOR (Final Decision) — TIER 1 ACTIVE**

Model: `models/gemini-2.5-flash` | Fallback: `llama-3.3-70b-versatile`

Decision rules (code-enforced, not LLM):
- Any devil check failed → REJECT
- Tier 3+: 4/4 agree → STRONG BUY | 3/4 → BUY | 2-2 split → wait 15min, re-debate, still split → REJECT
- Confidence <65 → REJECT | Real RR <2.0 → REJECT
- Tier 1: Bull NEUTRAL/SELL → REJECT | Bull BUY/STRONG_BUY + confidence ≥65 + all checks pass → APPROVE

**TRANSPARENCY REPORT (replaces SHAP — incompatible with LLMs):**

```json
{"approved": true, "verdict": "BUY", "final_confidence": 78, "position_size_factor": 0.8,
 "top_reasons": ["RSI 62 bullish", "4/4 TF aligned", "FII buyer ₹1,240Cr"],
 "deciding_factor": "MTF alignment", "rejection_reason": null,
 "devil_checks_passed": 8, "devil_checks_failed": 0,
 "signal_summary": "HDFC Bank bullish. Entry ₹1,780 | 1.5% risk | RR 2.4"}
```

**GROQ RATE LIMITS:** 30 req/min, 14,400 tokens/min. Tier 1: 2 calls/signal (Bull + Supervisor).

Fallback: 3 consecutive failures in 5 min → switch to Ollama. Wc capped 0.8. Telegram alert sent.

**AGENT RECALIBRATION:** Every 50 trades OR 30 days (whichever first). Weight range: 0.6-1.6. All changes logged to agent_weight_log.

---

## SECTION 14 — SIGNAL LIFECYCLE

**DAILY LIMITS:** Tier 1: 2 signals | All Tiers: 4 signals

Upgrade 2→4 when: win rate >60% for 30+ days, zero circuit breakers 14 days, max DD <8%.

Rejected signals: unlimited. All logged to signal_intelligence_log. All feed Pattern Memory.

**SIGNAL PIPELINE:**

1. MQI check — Very Low → stop, No-Trade message
2. Scanner every 15 min (9:30-3:15 PM weekdays)
3. Pre-filter: technical min (3/5), liquidity min, time-of-day
4. Devil checks (risk/devil_checks.py)
5. Confidence scoring
6. Agent debate (Bull + Supervisor Tier 1)
7. Priority queue: rank by confidence × real_RR if over limit
8. Approved: Telegram + Discord + Dashboard + logged
9. Staleness: 100% → 95% (5min) → 85% (10min) → 70% (15min) → EXPIRED (20min)
10. Price moves >0.3% from entry → immediate expiry

**TIME-OF-DAY FILTER:**

| Window | Status |
|--------|--------|
| 9:15-9:30 AM | EXCLUDED — opening noise |
| 9:30-10:30 AM | HIGH — best window |
| 10:30-12:00 PM | MEDIUM-HIGH — normal |
| 12:00-2:00 PM | MEDIUM — reduced threshold |
| 2:00-3:00 PM | HIGH — pre-close institutional |
| 3:00-3:15 PM | EXCLUDED — too close to close |
| After 3:15 PM | NONE — close intraday only |

**CONFIRMATION:** Paper: automated. Live: manual within 15 min → no action = expired. Order placed in AngelOne app (not API, Tier 1).

---

## SECTION 15 — EXIT LOGIC (TRIPLE BARRIER)

First barrier hit exits the trade: SL | Target | Time

| Timeframe | SL | Target | Time Barrier |
|-----------|-----|--------|-------------|
| Intraday | 1% risk | RR ≥ 2.0 | 3:15 PM — no exceptions |
| Swing | 1.5% risk | 2-3R | 7 trading days |
| Positional | 2% risk | Structure + trailing | 40 trading days |

**TRAILING STOP:**

- At 1R profit → SL to breakeven (entry + costs)
- At 2R profit → SL to 1R level
- After 2R → trail using best of: 15-min swing low/high | EMA21 (15m) | Price − (1.5 × ATR14)

**RATCHET RULE:** SL only moves toward profit. Never backward. Ever.

**HIGH VIX BUFFER:** VIX >22 → add 0.5× ATR to all trailing distances.

**OPTIONS EXIT:**

Long: SL at 50% premium loss | Target 100-200% gain | Exit 1 day before expiry

Short: SL at 2× premium received | Target 50% captured | Exit 2 days before expiry

---

## SECTION 16 — OVERNIGHT RISK PROTOCOL

**AUTO CLOSE (30-60 min before close):**

Earnings next day | RBI MPC next day | Budget next day | Election overnight | FOMC overnight | OPEC (MCX Crude) | Expiry day after 2 PM

**ALERT + SIZE -25%:**

US CPI/NFP next day | State elections next day | VIX >22 sustained | Short options within 3 days of expiry

**NORMAL CARRY:** No events 24h | VIX stable <18 | No earnings | Margin <50%

**GAP RISK:** Expected Gap = historical overnight vol × event multiplier × VIX factor. If >SL × 1.5 → auto close.

---

## SECTION 17 — F&O ENGINE (Tier 2+ — paper signals Tier 1)

**FOUR-LAYER VALIDATION:** Price action | Options flow (OI, PCR, sweeps) | IV environment | Portfolio Greeks

**IV FRAMEWORK (both measures must agree):**

IV Rank = (Current − 52W Low) / (52W High − 52W Low) × 100

IV Percentile = Days IV < Current / 252 × 100

Both <30: BUY strategies | 30-70: spreads only | >70: SELL premium

**VIX OVERRIDE:** >25 → block premium selling | >30 → block all F&O

**GREEKS LIMITS:** Net Delta: max 3 Nifty lots | Net Vega: max 5% portfolio/1% IV | Net Gamma expiry: max 2 lots

**EXPIRY DAY:** 9:15-11:30 all allowed | 11:30-2:00 spreads only -25% size | After 2:00 no new F&O | 3:15 PM force close all intraday options

**0DTE:** Confidence ≥85, IV Rank ≥40, size halved

---

## SECTION 18 — MCX COMMODITY ENGINE (Tier 2+)

**DATA:** AngelOne SmartAPI primary | Shoonya manual failover

**UNIVERSE:**

Precious: Gold (1kg/Mini/Guinea/Petal), Silver (30kg/Mini/Micro), Platinum, Palladium

Energy: Crude Oil (100bbl/Mini), Natural Gas (1250/Mini mmBtu)

Base Metals: Copper, Zinc, Lead, Aluminium, Nickel, Brass, Steel Long (all with Mini)

Agri NCDEX: Castor, Turmeric, Jeera, Coriander, Chana, Soybean, Guar, Mentha, Cotton, CPO, Rubber

**THREE-LAYER SIGNAL:**

1. Global Anchor: COMEX/NYMEX/LME via yfinance
2. Indian Microstructure: MCX OI, volume, MCX vs international spread
3. Technical: EMA, RSI directional, Supertrend

**GOLD-SILVER RATIO:** >80 → Long Silver | <60 → Long Gold

**BLACKOUTS:** OPEC day: no Crude | EIA Wednesday 8:30 PM IST: no Crude intraday | RBI MPC day: no commodities

**LIMITS:** Total commodity: max 20% Growth pool | Single commodity: max 10%

---

## SECTION 19 — DATA ARCHITECTURE

**ANGELONE (primary):** NSE/BSE Equity+F&O, MCX, Currency. SmartWebSocket v2, Historical API (2yr), Options Chain, GTT, Margin, Portfolio. Cost: ₹0.

**SHOONYA (manual failover only):** TOTP 2FA cannot be safely automated. AngelOne fails → Telegram alert → MJ logs in manually → MJONAI reconnects. Gap: yfinance 15-min delayed data. No new signals during outage.

**YFINANCE:** S&P500, NASDAQ, DJI, DXY, Gold, Brent, Asian/European indices. Free, no key.

**FRED API:** US rates, Treasury yields, CPI, employment. Free key at fred.stlouisfed.org.

**NEWS RSS (free, no auth):** ET, Moneycontrol, LiveMint, Business Standard, Reuters India, NDTV Profit, Bloomberg India

**REGULATORY (scrapers):** SEBI, NSE, BSE circulars, RBI press releases, MCA filings, NCLT, CCI

**FII/DII:** T-1 only. NSE publishes ~6-7 PM. Labelled "FII Trend (T-1)" everywhere. Intraday proxy: Nifty Futures premium (approximate, labelled as proxy).

**POLYMARKET:** Defer to Tier 3. FEMA ambiguous. Alternative: Metaculus API (no crypto, no FEMA concern).

**GOVERNMENT DATA (free):** EPFO (epfindia.gov.in), VAHAN (vahan.parivahan.gov.in), DGCA (dgca.gov.in), GST e-way (ewaybillgst.gov.in), IMD monsoon (imd.gov.in), RBI DBIE (dbie.rbi.org.in), Coal India reports

**DATA QUALITY WATCHDOG:**

- Heartbeat: ping 1.1.1.1 every 10s
- Price conflict: AngelOne vs yfinance >0.5% → quarantine instrument
- Ghost candle: price >1% move + volume=0 → bad data flag
- Spike: 1-min candle >3% without news → anomaly flag
- Quarantine lift: both sources within 0.1% for 5 consecutive minutes

---

## SECTION 20 — KNOWLEDGE ENGINE (Structure: Tier 2 | Active: Tier 3)

**STACK:** ChromaDB (local) | sentence-transformers (local) | PyMuPDF | BeautifulSoup + Scrapy | feedparser | PRAW | Ollama (summarization, on-demand)

**BOOKS (knowledge/books/):**

Trading: Murphy, Nison, Schwager (Market Wizards), Lefevre, Douglas, Natenberg

Quant: Lopez de Prado, Chan, Aronson

Value: Graham, Lynch, Cunningham

Macro: Dalio, Soros, Taleb, Kahneman

India: Zerodha Varsity (13 modules), SEBI materials, NSE Academy, RBI annual reports

**INGESTION (GitHub Actions):**

6:00 AM daily: RSS feeds | 7:00 AM: SEBI/RBI/NSE/BSE circulars | 7:30 AM: Reddit digest | Weekly Sunday: SSRN/arXiv papers | Continuous: SEBI/RBI circular webhook

**RAG AT SIGNAL TIME:**

1. Extract context (asset class, strategy, regime, indicators)
2. Query ChromaDB → top 5 chunks
3. Inject into agent prompts
4. Bull: technical research | Bear: fundamental | Economist: macro | Devil: failure cases

---

## SECTION 21 — COMMUNICATION LAYER

**TELEGRAM (primary — phone execution layer):** 5 types only. Strict. No noise.

```
Type 1 — Signal:
🎯 MJONAI SIGNAL — BUY [SWING] (📈 LONG)
Stock: HDFC Bank | Entry: ₹1,780
SL: ₹1,745 (-1.96%) | Target: ₹1,850 (+3.93%)
Real RR: 2.0 | Risk: ₹700 (0.7% capital)
Confidence: 78% | Regime: BULL
Bull: RSI 63, 4TF aligned | Supervisor: All checks passed
Expires: 15 minutes | ⚠ Personal use only.

Type 2 — Risk Alert:
⚠ MJONAI RISK ALERT
Trigger: 3 consecutive losses | Action: Signal limit -1 today

Type 3 — Psychology:
🧠 MJONAI PSYCHOLOGY
Bias: FOMO | Trade blocked. 30-min cooling active.

Type 4 — Daily (post 3:30 PM):
📊 MJONAI DAILY REPORT
Trades: 2 | Wins: 1 | Losses: 1 | Net P&L: +₹420
Signals: 6 generated | 2 approved | 4 rejected | MQI: HIGH

Type 5 — Emergency:
🛑 MJONAI EMERGENCY STOP
Trigger: Daily loss 3% | All positions closed. Resumes tomorrow.
```

Max per day: 4 signals + 3 risk + 1 daily report. Exceeded → alert fatigue flag.

**DISCORD (secondary — desktop intelligence):** #signals | #agent-debate | #pattern-memory | #portfolio-xray | #weekly-review | #system-health

**ALERT PRIORITY:** Emergency > Risk > Psychology > Signals > System health > Daily reports

**TIER 1 EXECUTION:** Paper: fully automated. Live: manual in AngelOne app. No broker API calls. Zero SEBI algo risk.

---

## SECTION 22 — BACKTESTING ENGINE

**PRIMARY:** VectorBT. If insufficient → Backtrader (fully free, Indian examples on GitHub).

**CUSTOM INDIAN COST LAYER (mandatory — invalid without this):**

All costs from Section 9 | NSE/BSE hours 9:15-3:30 IST | Circuit breakers ±5/10/15/20% | NSE holiday calendar | Survivorship bias correction (historical constituents) | Look-ahead bias prevention | Slippage by instrument type

**THREE MODES:**

1. Strategy: single instrument, fast
2. Portfolio: all instruments, pillar allocation, correlation-aware
3. Monte Carlo: 1000 random orderings, outcome distribution

**PHASE GATES:**

| Phase | Trades | Max DD | Sharpe | Other |
|-------|--------|--------|--------|-------|
| Backtest | ≥300 | ≤15% | ≥1.2 | Profit Factor ≥1.5 |
| Paper | ≥50 | ≤10% | ≥1.0 | ≥30 days, zero violations |
| Controlled Live | ≥100 | ≤8% | ≥1.0 | ≥60 days, ≤5% capital |

Fail any criterion → do not proceed.

**ANTI-OVERFITTING:** Walk-forward only. 3yr in-sample, 1yr out-of-sample. Out-of-sample drops >30% vs in-sample → OVERFIT → REJECT.

**RESULTS MUST SHOW:** Tax-adjusted CAGR (primary) | Net CAGR | Gross CAGR (reference)

Benchmark: Nifty 50 TRI. Alpha = Net CAGR − Nifty TRI CAGR.

---

## SECTION 23 — VALIDATION FRAMEWORK

**ALL criteria must be met to move paper → real money:**

- 30 consecutive trading days paper complete
- 50 closed paper trades
- Win rate >65% on most recent 30 trades
- Per asset class: 60%+ win rate over 20+ trades independently
- Max drawdown never exceeded 15%
- Psychology score >70/100 average last 30 days
- Zero circuit breakers last 14 days
- MJ Reddy explicit written confirmation (dated and signed)

**TRANSITION:** Always human-initiated. System shows "Ready" indicator. Never auto-switches.

---

## SECTION 24 — PSYCHOLOGY GUARD

**Cannot be disabled by anyone.**

| Bias | Detection |
|------|-----------|
| Overconfidence | Win streak >3 + size increase request |
| Revenge trading | Trade attempt within 30 min of loss |
| FOMO | Entry attempt after price moved >0.3% beyond signal |
| Anchoring | Holding losing position beyond Max DD |
| Disposition effect | Selling winners early, holding losers past SL |
| Recency bias | Behavior change after market extreme |
| Loss aversion | SL override or refusal to close loser |
| Herding | Trade attempt without MJONAI signal |

**Levels:** Warning → Alert (confirm to proceed) → Block (violated Golden Rule)

**Psychology Score (0-100 weekly):** Bias count + override attempts + SL discipline + time between loss and next trade.

**Cooling Periods:** Loss → 30 min | Circuit breaker → 24h | 5% DD day → 48h

---

## SECTION 25 — TAX ENGINE

**ALL P&L NET OF COSTS AND TAX. GROSS IS NEVER PRIMARY.**

| Instrument | STCG | LTCG | Threshold |
|-----------|------|------|-----------|
| Listed Equity | 20% | 12.5% above ₹1.25L | 12 months |
| Equity MF | 20% | 12.5% above ₹1.25L | 12 months |
| Debt MF | Slab | Slab | 24 months |
| F&O | Business income slab | N/A | Always |
| Intraday | Speculative slab | N/A | Always |
| Crypto/VDA | 30% + 1% TDS on sell | 30% | No LT benefit |
| SGB (maturity) | Tax FREE | Tax FREE | Hold to RBI maturity |

**FIFO:** Each buy = dated lot. Alert at 11 months: "Wait 30 days → LTCG saves ₹X."

Track ₹1.25L LTCG exemption. Alert when approaching.

**ADVANCE TAX:** Jun 15: 15% | Sep 15: 45% | Dec 15: 75% | Mar 15: 100%

**TAX LOSS HARVESTING:** Alert before March 31: "Book ₹X loss on [Stock] → offset gains → save ₹Y."

---

## SECTION 26 — REPORTING

**PERFORMANCE X-RAY:** Per pillar P&L | Per strategy | Per regime | Per agent accuracy | Per time-of-day | Per day-of-week | Signal funnel | Missed signal cost | Ghost signal analysis

**ALL METRICS:** Primary: Net P&L + tax-adjusted CAGR | Secondary: Gross P&L + nominal CAGR | Benchmark: Nifty 50 TRI always shown

**METRICS:** Win rate | Profit Factor | Sharpe | Sortino | Calmar | Max DD | Recovery Factor | Avg Win:Loss | Expectancy | Max consecutive losses

**INDIA FEAR & GREED (custom):**

VIX 25% | Nifty momentum vs 125-day avg 25% | PCR trend 20% | Gold vs Equity 15% | Nifty500 breadth 15%

Score 0-100. Daily dashboard + Telegram morning briefing.

---

## SECTION 27 — INFRASTRUCTURE

**CONNECTIVITY:**

Primary: WiFi | Backup: Mobile hotspot (pre-configured WSL2)

Heartbeat: ping 1.1.1.1 every 10s

Disconnect → pause signals → Telegram alert

Reconnect → hard sync AngelOne vs Supabase before resuming

**GITHUB ACTIONS (overnight jobs):**

daily_data.yml (6 AM) | regulatory_monitor.yml (7 AM) | weekly_cleanup.yml (Sunday 2 AM) | weekly_performance.yml (Sunday 10 AM)

**BACKUP (3-2-1):**

1. Supabase cloud (real-time, Mumbai)
2. Local WSL2 (periodic export)
3. GitHub (code) + Google Drive (weekly CSV export)

**PHOENIX RECOVERY (<15 min, any machine):**

1. Clone GitHub repo
2. Install Python 3.11 + WSL2
3. pip install -r requirements.txt
4. Copy .env from Bitwarden
5. python main.py → pulls state from Supabase
6. Operational — no data loss

**DAILY STARTUP (8:45 AM):**

1. WSL2 terminal
2. Ping 1.1.1.1
3. AngelOne: verify token, auto re-login if expired
4. AngelOne vs yfinance Nifty price diff >0.5% → NO-GO
5. Supabase vs AngelOne holdings diff >1% → NO-GO
6. Capital/margin check
7. Calendar: events today/tomorrow?
8. Shoonya: manual check
9. All APIs responding?

GO → Telegram: "MJONAI LIVE — {Date}. Regime: {STATE}. MQI: {LEVEL}."

Fail → NO-GO. No signals until resolved.

**EXECUTION MODES:**

1. Paper: automated, no broker calls
2. Semi-manual live: signal sent, MJ places order in AngelOne app
3. Full auto: DISABLED until SEBI review

**KILL SWITCH:** Always on dashboard. One click → cancel orders, close positions, disable signals, log, Telegram alert.

---

## SECTION 28 — REGULATORY POSITION

**STATUS:** Personal use only. No subscriptions. No signal sharing. No public advisory.

**SEBI ALGO:** Safe approach Tier 1: MJONAI generates signals only. MJ places all orders manually. No broker API order placement. Before API order placement (Tier 2+): consult SEBI or SEBI-registered legal advisor.

**FEMA/RBI:** INR currency pairs only (USD/INR, EUR/INR, GBP/INR, JPY/INR). No offshore leveraged forex. US stocks/ETFs: LRS limit $250k/year.

**CRYPTO:** Compliant Indian exchanges only. 30% flat tax + 1% TDS on sell. No loss set-off.

**POLYMARKET:** Tier 3 only after legal review. Alternative: Metaculus API.

**DPDP 2023:** All data in India (Supabase Mumbai). No third-party sharing. Full deletion on request.

---

## SECTION 29 — MANUAL OVERRIDE POLICY

**CAN OVERRIDE (automatic penalty):** Rejected signal | Position size | Time barrier | Exit decision

**CANNOT OVERRIDE (ever):** 15% Kill Line | Margin emergency | Data quarantine | Psychology Level 3 block

**PENALTY (automatic, cannot be waived):**

- Position size -50% for that trade
- Daily signal limit -1
- Psychology score -5 points
- Permanently logged

**CONSECUTIVE PROTECTION:** 2 overrides in 24h → Soft Stop 24h. No signals regardless of MQI.

**TRACKING:** After 20 override trades: if override win rate <50% → max override size permanently -25%. Cannot be reset.

---

## SECTION 30 — CODING STANDARDS

**ALWAYS DO:**

- Type hints on every function parameter and return value
- Pydantic v2 models for all data shapes crossing module boundaries
- Docstring on every function (purpose, params, returns, raises)
- try/except on every external API call with specific exception types
- Structured JSON logging — not print statements
- Return structured Pydantic response objects — never raw exceptions
- One clear responsibility per file
- Maximum one new file per build session
- Never modify more than 2 existing files in one session

**NEVER DO:**

- Hard-code any API key, URL, or secret in source code
- Commit .env — add to .gitignore before first commit
- Import from a module at higher authority level
- Add business logic to repository.py (queries only)
- Circular imports between any two modules
- Use print() in production — use the logger
- Trust external data without validation
- Add a second file before the first makes the server start cleanly

**FILE HEADER (every Python file):**

```python
"""
Module: filename.py
Purpose: One clear sentence.
Depends on: module1, module2
Used by: module3, module4
Last modified: YYYY-MM-DD
"""
```

**GIT COMMIT FORMAT:**

```
[feat]    New feature
[fix]     Bug fixed
[upgrade] Improvement to existing feature
[docs]    Documentation only
```

**TESTING (before closing any session):**

1. `uvicorn main:app --reload` — no errors
2. Write 3 plain-English test scenarios
3. AI writes test script for those 3
4. All 3 pass before committing

---

## SECTION 31 — FEATURE TIER CLASSIFICATION

**TIER A — Phase 1-2:**

OFI | India Fear & Greed Index | Earnings Audio Analyzer (Whisper) | Government Contract Tracker (GeM, NHAI) | SEBI Enforcement Tracker | MCA Intelligence | Toxic Flow Detector | Decision Transparency Report | Calibration Engine | GTT Pre-Placer | Weighted Options Sentiment | FII Category Analyzer | India VIX Term Structure | Central Bank NLP | Earnings Surprise Predictor

**TIER B — Phase 2-3:**

VPIN | Volatility Targeting | Risk Parity Allocator | Tail Risk Hedge (OTM puts) | Market Knowledge Graph | LLM Consensus Scorer | Causal Inference (DoWhy) | Correlation Regime Switcher | CVaR | Real Yield Tracker | Global Liquidity Monitor | Corporate Governance Scorecard | Hurst Exponent | Supplier-Customer Mapper | Insider Network Analyzer | Narrative Economics Tracker | Disposition Effect Tracker

**TIER C — Phase 3-4:**

Satellite Intelligence | Multi-Agent Simulation (Mesa) | Federated Learning | RL Position Sizer | Hawkes Process | PCA Regime Detection | Reflexivity Detector | Cross-Sectional Momentum | Patent Citation Network | Quantum Portfolio Optimizer

---

## SECTION 32 — RETURN EXPECTATIONS

**BENCHMARK:** Nifty 50 Index Fund ≈1%/month (12%/year). Zero effort. Zero code. MJONAI must beat this consistently to justify the investment.

| Level | Monthly | Annual | Meaning |
|-------|---------|--------|---------|
| Underperforming | <1% | <12% | Stop real money. Return to paper. |
| Acceptable | 1.0-1.5% | 12-18% | Working. Don't scale yet. |
| Good | 1.5-2.0% | 18-24% | Top-tier retail. Plan Tier 2. |
| Exceptional | 2.0-3.0% | 24-36% | Verify over 6+ months. |
| Fantasy | >3.0% | >36% | Check for errors. Need 12+ months validation. |

**RULES:**

- Do NOT plan living expenses around MJONAI income in Tier 1 or 2
- Every rupee of profit = bonus, not income
- Tier 1 goal = proof of concept, not income
- 14-16% annual sustained = genuinely excellent globally
- Most active fund managers don't beat 14% net of fees

---

## SECTION 33 — CAPITAL TIER ACTIVATION

**PRINCIPLE:** Architecture never changes. What changes = which engines are ACTIVE, PAPER-ONLY, or DISABLED based on capital.

---

### TIER 1 — Under ₹2 Lakhs ← YOU ARE HERE

**ACTIVE:** Equity swing (3-10 days) | Equity positional (2-8 weeks) | Nifty 200 only | Bull + Supervisor agents | All 8 devil checks | Risk engine | Paper mode | Telegram | Pattern memory (write-only) | Psychology guard

**PAPER ONLY:** F&O options buying | Gold Mini MCX | Crude Mini MCX | Equity intraday

**DISABLED:** F&O selling | F&O futures | Iron Condor/Butterfly | Silver/Copper MCX | Covered calls | CSP | Income engine | 5-agent debate | Knowledge RAG | Stability pillar | Crypto

**CAPITAL ALLOCATION:**

80% → Equity swing/positional | 10% → Emergency reserve (never touch) | 10% → Opportunity reserve (90%+ confidence only)

**REAL MONEY RULES:**

Max risk/trade: ₹1,000 | Max positions: 3 | Max signals/day: 2

Trade types: Swing + positional only | Universe: Nifty 200 | Orders: manual AngelOne app only

**UNLOCK TIER 2 (all must be met):**

- 60 consecutive paper trading days
- 30+ real money trades
- Win rate >60% across last 30 trades
- Max drawdown never exceeded 8%
- Zero circuit breakers in last 30 days
- Sharpe >1.0 on real trades
- Capital at ₹2L (savings + profits combined)

---

### TIER 2 — ₹2-10 Lakhs

**NEW:** 4-agent debate (Bear + Economist) | F&O options buying (>85% conviction, 1-2 lots) | Gold + Crude Mini MCX | FinBERT | IV Rank filter | Options flow | Selective intraday | Pattern memory read+write | 3 signals/day

**ALLOCATION:** Growth 60% | Stability 20% (liquid fund) | Cash 20%

**TARGET:** 1.5-2.5% net/month

---

### TIER 3 — ₹10-25 Lakhs

**NEW:** 5-agent debate (Devil LLM) | F&O selling (Greeks limits) | Bull+Bear spreads | Index futures (1 lot) | Iron Condor (IV Rank >70) | Silver Mini | Covered calls | Full Knowledge RAG | Full IV framework | Greeks monitoring | Full expiry protocol | 4 signals/day | Full Stability pillar | Polymarket (after legal review)

**ALLOCATION:** Growth 50% | Stability 30% | Cash 20%

**TARGET:** 1.5-2.5% net/month

---

### TIER 4 — ₹25 Lakhs+

**NEW:** Full Income engine | CSP | Iron Butterfly | Full MCX + NCDEX agri | Crypto sandbox (5%, spot only) | REITs + InvITs | Gold 5% SGB | Systematic tail risk hedge | Volatility targeting | Advanced alt data | Agent recalibration | Family system | SaaS prep

**ALLOCATION:** Full 3-pillar model (Section 8) + Crypto sandbox

**TARGET:** 1.5-2.5% on larger absolute capital

---

### CAPITAL GROWTH REALITY

Tier 1 "Good" performance (1.5-2%/month) = ₹18,000-24,000/year profit on ₹1L.

To reach ₹2L: needs ₹58,000-76,000 additional savings on top of profits.

Profits alone insufficient. Savings injection required.

| Transition | Timeline |
|-----------|----------|
| Tier 1 → 2 | 12-18 months |
| Tier 2 → 3 | 24-36 months |
| Tier 3 → 4 | 36-60 months |
| Full system | 5-7 years |

---

### EXIT CONDITIONS

**LEVEL 1 — Stop real money, return to paper:**

Win rate <50% for 30+ consecutive trades

OR Sharpe <0.5 for 60+ trading days

OR Underperforms Nifty TRI by >5% over any 6 months

OR 5+ consecutive losses twice in same calendar month

Action: Halt real money. Paper mode. Audit. Fix. Re-validate before redeploying.

**LEVEL 2 — Strategy pivot:**

3 consecutive Level 1 months AND no improvement after debugging AND win rate <52% over 90 days AND portfolio lost >15%

Action: Pause 30+ days. Audit root cause. 30 days paper after fix. Resume only after paper validates.

**LEVEL 3 — System integrity failure only:**

Kill Line fired AND system FAILED to execute the close (risk engine failure — not a trading loss).

Action: Manual liquidation. 30-day pause. Full audit of why risk engine failed.

**PHILOSOPHICAL EXIT:**

If after 12 honest months system cannot beat Nifty 50 TRI after all costs and taxes, consistently across regimes → index fund wins. No shame. Most professional active managers fail to beat 14% net.

---

## SECTION 34 — STRATEGY REGISTRY (v2.0)

```python
# strategy/registry/base.py
class BaseStrategy:
    name: str          # e.g. "S01_MomentumRSI"
    display_name: str  # e.g. "Momentum RSI"
    timeframe: str     # "intraday" / "swing" / "positional"
    asset_class: str   # "equity" / "fno" / "mcx"
    version: str       # "1.0" — increment on parameter change

    def generate_signal(self, df, symbol, vix, market_state, mqi_level) -> dict | None:
        """Returns signal dict or None. Signal must contain:
        strategy_id, symbol, signal_type, technical_score, confidence, reasons, timeframe"""
        raise NotImplementedError

    def get_parameters(self) -> dict:
        """All parameters for MLflow tracking."""
        raise NotImplementedError

    def get_description(self) -> str:
        """Human-readable description for alerts and reports."""
        raise NotImplementedError
```

**7 Active Strategies (v2.0):**

| ID | Name | Type | Logic | Status |
|----|------|------|-------|--------|
| S01 | MomentumRSI | Swing 3-10d | RSI 55-70 + EMA 20/50/200 + MACD 12/26/9 + Supertrend(3) + Candle | ✅ ACTIVE |
| S02 | MeanReversion | Swing 3-7d | RSI <30 + BB lower (2SD) + volume spike + above EMA200 | ✅ ACTIVE |
| S03 | TurtleBreakout | Positional 2-8w | 20-day high breakout + volume >1.5x + SL=10-day low + ATR trail | ✅ ACTIVE |
| S04 | BollingerSqueeze | Swing 3-10d | BB width <75% avg → expansion + MACD/RSI confirm direction | ✅ ACTIVE |
| S05 | PriceActionCandles | Swing 2-7d | 37 bullish TA-Lib patterns + EMA50 + volume >1.2x | ✅ ACTIVE |
| S06 | MomentumShort | Swing 3-10d | RSI 30-45 bearish + MACD bearish + EMA aligned down + Supertrend bear + Evening/Shooting Star | ✅ ACTIVE NEW |
| S07 | MeanReversionShort | Swing 3-7d | RSI >70 overbought + above BB upper + volume spike + below EMA200 | ✅ ACTIVE NEW |

**S01 targets:** Win rate >55% | Best: BULL+HIGH | Worst: BEAR/HIGH VIX

**S02 targets:** Win rate >50% | Best: oversold in BULL | Worst: strong BEAR

**S03 targets:** Win rate >40% | RR >3.0 | Research Q: does Turtle work in NSE equities?

**S04 targets:** Win rate >55% | Best: low VIX + catalyst

**S05 targets:** Win rate >50% | Research Q: which of 37 patterns work in NSE large caps?

**S06 targets:** Win rate >50% | Best: BEAR regime | Research Q: does bearish momentum mirror bullish?

**S07 targets:** Win rate >50% | Best: overbought in BEAR | Research Q: does mean reversion from overbought work?

**Parallel testing flow:**

```
Every 15-min scan (RESEARCH mode):
  For each stock in Nifty 500:
    For each strategy in registry:
      signal = strategy.generate_signal(df, ...)
      if signal:
        run_devil_checks(signal)   ← WARN
        run_bull_agent(signal)     ← track
        run_supervisor(signal)     ← track
        open_paper_trade(signal)   ← fixed ₹10k
        log_to_agent_logs(signal)  ← full audit
```

**Performance log per closed trade:**

```json
{"strategy_id": "S01_MomentumRSI", "version": "1.0", "symbol": "RELIANCE",
 "entry_date": "2026-05-04", "exit_date": "2026-05-08", "holding_days": 4,
 "market_state": "BULL", "mqi_level": "HIGH", "vix_at_entry": 14.2,
 "confidence": 74.0, "sl_method": "STRUCTURE", "bull_verdict": "BUY",
 "devil_checks": 8, "outcome": "WIN", "actual_rr": 2.4,
 "gross_pnl": 240.0, "net_pnl": 198.0,
 "time_of_day": "10:15", "day_of_week": "Monday", "sector": "OIL_GAS",
 "signal_direction": "LONG"}
```

**Strategy lifecycle:**

- BIRTH: write → paper 30+ days → min 30 trades before assessment
- EVALUATION (100 trades): >55% + Sharpe >0.8 → PROMISING | 45-55% → INVESTIGATE | <45% → REVIEW
- GRADUATION (200+ trades): >55% win rate + Sharpe >1.0 + DD <15% + works 2/3 regimes → LIVE
- RETIREMENT: <40% after 100 trades, no regime explanation → ARCHIVED (not deleted)
- EVOLUTION: edge exists but wrong params → fork + new version + re-paper

**Adding new strategies:**

1. Write hypothesis: "I believe [signal] predicts [outcome] in [regime] because [reason]"
2. Create file inheriting BaseStrategy
3. Register in STRATEGY_REGISTRY in signal_scanner.py
4. Paper trade 30+ days, 30+ trades
5. Alphalens: IC >0.05 = genuine edge
6. Board review: graduate / retire / iterate

```python
# core/constants.py additions
STRATEGY_REGISTRY = {
    "S01_MomentumRSI":       "strategy.registry.momentum_rsi",
    "S02_MeanReversion":     "strategy.registry.mean_reversion",
    "S03_TurtleBreakout":    "strategy.registry.turtle_breakout",
    "S04_BollingerSqueeze":  "strategy.registry.bollinger_squeeze",
    "S05_PriceAction":       "strategy.registry.price_action",
    "S06_MomentumShort":     "strategy.registry.momentum_short",
    "S07_MeanReversionShort": "strategy.registry.mean_reversion_short",
}

PAPER_POSITION_SIZE_RESEARCH = 10_000
RESEARCH_CONFIDENCE_MIN      = 50
LIVE_CONFIDENCE_MIN          = 65
```

---

## SECTION 35 — SIGNAL DIRECTION SUPPORT (v2.0)

**NEW IN SESSION 16:** All signals now include `signal_direction` field.

```python
# Signal dict now includes:
{
    "signal_direction": "LONG" | "SHORT",
    "signal_type": "BUY" if LONG else "SELL",
    ...
}
```

**LONG Signals:**
- Entry: Buy at market price
- SL: Below entry (structure or ATR)
- Target: Above entry (2-3R)
- P&L: (exit - entry) × qty

**SHORT Signals:**
- Entry: Sell at market price (paper only)
- SL: Above entry (structure or ATR)
- Target: Below entry (2-3R)
- P&L: (entry - exit) × qty

---

## SECTION 36 — FORWARD RETURNS & ALPHALENS (v2.0)

**NEW IN SESSION 16:** Forward return tracking for Alphalens IC analysis.

**Module:** `research/forward_returns.py`

**Daily Schedule:**
- 4:00 PM IST: Calculate forward returns for all signals
- 4:30 PM IST: Daily research report via Telegram
- Sunday 10:00 AM: Weekly Alphalens IC analysis

**Forward Return Windows:**
```python
FORWARD_WINDOWS = [1, 3, 5, 10, 20]  # Trading days
```

**Alphalens IC Thresholds:**
- IC > 0.05 = genuine edge
- IC > 0.10 = strong edge (rare, treasure it)
- IC < 0.02 = noise, retire the signal

---

## SECTION 37 — SCAN OVERLAP LOCK (v2.0)

**NEW IN SESSION 16:** Prevents concurrent scans from running simultaneously.

```python
# strategy/signal_scanner.py
_scan_running = False
_scan_lock_time = None

def scan_signals(...):
    global _scan_running, _scan_lock_time
    
    if _scan_running:
        elapsed = (now_ist() - _scan_lock_time).seconds if _scan_lock_time else 0
        print(f"⚠️ Scan already running (started {elapsed}s ago). Skipping.")
        return []
    
    _scan_running = True
    _scan_lock_time = now_ist()
    
    try:
        # ... all scan logic ...
        return approved_signals
    finally:
        _scan_running = False
        _scan_lock_time = None
```

---

## SECTION 38 — RESEARCH AGENDA (20 CATEGORIES)

### Category 1 — Technical Indicators

**CURRENTLY USING (5):** RSI(14), MACD(12,26,9), EMA(20,50,200), Supertrend(simplified), Hammer+Engulfing

**RESEARCH QUESTIONS:**
- Does RSI 55-70 actually predict positive returns in NSE?
- Which MACD parameters work best in Indian large caps?
- Do Fibonacci EMAs (9,21,55,89) outperform standard?
- Does Hull Moving Average reduce lag meaningfully?

**TO TEST (momentum):** RSI variants: 7, 9, 14, 21 periods | Stochastic RSI | Williams %R | Rate of Change (ROC): 10, 20 day | Awesome Oscillator

**TO TEST (trend):** EMA cross: 9/21, 20/50, 50/200 | HMA (Hull Moving Average) | ADX strength filter (>25 = trending) | Ichimoku: cloud, tenkan/kijun cross | Parabolic SAR

**TO TEST (volatility):** Bollinger Bands: width, squeeze, %B | Keltner Channels | Donchian Channels (20-day, 55-day) | ATR as position sizing input | Historical Volatility Rank

**TO TEST (volume):** OBV divergence with price | CMF (Chaikin Money Flow) | MFI (Money Flow Index) — volume RSI | Force Index | Volume Rate of Change

**KEY RESEARCH QUESTION:** Which combination of indicators has highest Information Coefficient (IC) in Indian large caps?

---

### Category 2 — Candlestick Patterns

**CURRENTLY USING:** Hammer + Engulfing (2 of 61)

TA-Lib has 61 patterns. We use 2. Research lab tests all 61.

**SINGLE CANDLE:** Doji, Dragonfly Doji, Gravestone Doji | Spinning Top, Marubozu | Hammer ✅, Inverted Hammer | Hanging Man, Shooting Star

**TWO CANDLE:** Bullish Engulfing ✅, Bearish Engulfing | Piercing Line, Dark Cloud Cover | Bullish Harami, Bearish Harami | Tweezer Bottom, Tweezer Top

**THREE CANDLE:** Morning Star (strongest bullish reversal) | Evening Star (strongest bearish reversal) | Three White Soldiers | Three Black Crows | Three Inside Up/Down | Abandoned Baby

**RESEARCH QUESTION:** Which of 61 patterns have positive IC in NSE large caps after costs?

---

### Category 3 — Chart Patterns

**REVERSAL:** Head and Shoulders / Inverse H&S | Double Top / Double Bottom | Triple Top / Triple Bottom | Rounding Bottom (Saucer)

**CONTINUATION:** Bull Flag / Bear Flag | Bull Pennant / Bear Pennant | Ascending Triangle | Descending Triangle | Symmetrical Triangle | Rectangle (consolidation)

**BREAKOUT:** 52-week high breakout | All-time high breakout | Resistance breakout with volume confirmation

**SUPPORT/RESISTANCE:** Previous day/week high/low | Round numbers (₹500, ₹1000, ₹1500) | Fibonacci retracements (23.6%, 38.2%, 50%, 61.8%, 78.6%) | Pivot points (Standard, Camarilla, Woodie)

**RESEARCH QUESTION:** Does 52-week high breakout generate positive momentum in Indian large caps?

---

### Category 4 — Strategy Archetypes

**TEN FUNDAMENTALLY DIFFERENT APPROACHES:**

1. **MOMENTUM (current S01):** Buy strength. Trend following. Best: Bull market, low VIX.
2. **MEAN REVERSION (S02):** Buy weakness in uptrend. Opposite of momentum. Best: Sideways market, oversold conditions.
3. **BREAKOUT (S03 — Turtle):** Buy new highs with volume. Based on Turtle Trading (Richard Dennis, 1983). Best: Trending market after consolidation.
4. **VOLATILITY SQUEEZE (S04):** Buy after low volatility compression. Bollinger Band squeeze. Best: Any regime where volatility is compressed.
5. **PRICE ACTION ONLY (S05):** Candlestick patterns + S/R. Zero indicators. Best: All regimes — patterns work everywhere.
6. **VOLUME-PRICE ANALYSIS (Wyckoff):** Accumulation/Distribution detection. Smart money footprint. Best: Early stages of new trend.
7. **RELATIVE STRENGTH:** Buy strongest sector/stock vs market. Sector rotation strategy. Best: Trending market with clear sector leaders.
8. **CALENDAR EFFECTS:** Monday effect, Friday effect. Month-end, quarter-end patterns. Earnings season patterns. Best: Specific time windows only.
9. **FUNDAMENTAL TRIGGERS:** Earnings surprise momentum. Analyst upgrade effect. Insider buying signal. Best: Post-announcement momentum.
10. **VOLATILITY STRATEGIES:** Buy when VIX spikes (fear = opportunity). Mean revert elevated VIX. Best: Market correction environments.

**KEY INSIGHT:** No single strategy works in all regimes. Multiple strategies = smoother equity curve. Data reveals which regime each strategy needs.

---

### Category 5 — Timeframes

**CURRENTLY USING:** Daily only (swing trades)

**RESEARCH TO RUN:** 5-minute (intraday scalping — very noisy) | 15-minute (institutional intraday) | 1-hour (swing entry confirmation) | Daily ✅ (current) | Weekly (positional — stronger signals, fewer trades)

**MULTI-TIMEFRAME RESEARCH:** Weekly trend + Daily signal + 1H entry | Monthly trend + Weekly signal + Daily entry

**KEY FINDING (expected):** Shorter timeframes = more signals, lower win rate | Longer timeframes = fewer signals, higher win rate | Optimal for swing trading: Daily signal + Weekly confirmation

---

### Category 6 — Backtesting Methodology

**ANTI-OVERFITTING RULES (critical):**

1. **WALK-FORWARD TESTING ONLY:** Train on 3 years (in-sample). Test on 1 year (out-of-sample, never seen). Roll forward 6 months. Repeat. If out-of-sample drops >30% vs in-sample: Strategy is overfit. Reject. Do not deploy.

2. **SURVIVORSHIP BIAS CORRECTION:** Test on historical Nifty 500 constituents NOT current constituents. Stocks that delisted = real losses. Including them in test = false accuracy.

3. **LOOK-AHEAD BIAS PREVENTION:** Signal on bar close. Entry on NEXT bar open (not same bar). Never use data not available at signal time.

4. **TRANSACTION COST REALISM:** Full Indian costs every trade: STT, brokerage, stamp, exchange, GST, SEBI, slippage. A strategy that works gross but not net = useless.

5. **MONTE CARLO VALIDATION:** Take actual trade sequence. Randomly reorder 10,000 times. Distribution shows: best case, worst case, most likely. If worst case = ruin → strategy is too aggressive.

6. **SENSITIVITY ANALYSIS:** Change RSI period from 14 to 7, 9, 21, 28. Strategy should work across most values. If only works at exactly RSI=14 → overfit. Robust strategy works at 12, 14, 16 all similarly.

---

### Category 7 — Forecasting Methods

**STATISTICAL TIME SERIES:** ARIMA: predict future prices from past patterns | SARIMA: ARIMA with seasonality (monthly patterns) | GARCH: volatility forecasting → predict if next week will be high/low volatility → adjust position size based on vol forecast

**MACHINE LEARNING:** Random Forest: classify if trade will win/lose | XGBoost: same as Random Forest, usually better | LSTM (Long Short-Term Memory): Learns sequential price patterns

**FOUNDATION MODELS (future):** TimesFM (Google): pre-trained on billions of time series | Chronos (Amazon): zero-shot time series forecasting

---

### Category 8 — Alternative Data Sources

**ALL FREE. ALL LEGAL. ALL UNDERUSED BY RETAIL.**

**GOVERNMENT DATA:** GST e-way bills | EPFO payroll additions | VAHAN vehicle registrations | DGCA air traffic | Coal India production reports | IMD monsoon data | GST collections

**CORPORATE FILING INTELLIGENCE:** MCA filings | SEBI enforcement actions | NSE bulk/block deals | NCLT proceedings | Patent filings

**WEB/SOCIAL DATA:** Job posting trends | Glassdoor rating trends | Google Trends | Reddit (r/IndiaInvestments, r/Dalal_Street)

---

### Category 9 — Indian Market Specific Research

**EXPIRY WEEK EFFECTS:** Weekly (Thursday): specific intraday patterns | Monthly (last Thursday): maximum volatility

**RBI MPC EFFECT:** Pattern: uncertainty 2 days before → clarity after

**BUDGET DAY PATTERNS:** Historical study: 2010-2026 budget outcomes

**MONSOON EFFECT (June-September):** FMCG: rural demand rises with good monsoon

**FII BEHAVIOR PATTERNS:** December: year-end profit booking | January: fresh allocations | March: quarter-end rebalancing

**SGX NIFTY GAP RESEARCH:** SGX Nifty trades overnight | Predicts Indian market open direction

**SECTOR ROTATION:** Which sectors lead in early bull market? | Which sectors lead in late bull market? | Which sectors are defensive in bear market?

---

### Category 10 — Market Microstructure

**ORDER FLOW IMBALANCE (OFI):** Buy orders minus sell orders at each price level | Predicts short-term direction (1-5 minute)

**VWAP DYNAMICS:** VWAP = Volume Weighted Average Price | Institutional benchmark

**BULK/BLOCK DEAL ANALYSIS:** NSE publishes daily bulk + block deals | Large institutional transactions

**CIRCUIT BREAKER PATTERNS:** Upper circuit = strong demand, limited supply | Lower circuit = forced selling, panic

---

### Category 11 — Quantitative Methods

**FACTOR MODELS:** Fama-French 3 factors: Market risk (beta) | Size (small vs large cap) | Value (book-to-market)

**PAIRS TRADING:** Find two cointegrated stocks (move together long-term) | When spread diverges: buy laggard, sell leader | When spread converges: close both

**HURST EXPONENT:** Measures trend persistence | H > 0.5 = trending (momentum strategies work) | H < 0.5 = mean reverting (reversion strategies work) | H = 0.5 = random walk (nothing works)

**KELLY CRITERION:** Optimal position sizing formula: f* = (bp - q) / b

**PORTFOLIO OPTIMIZATION:** Given 15 stocks with expected returns + covariance: What is the optimal allocation?

---

### Category 12 — Behavioral Finance Patterns

**ANCHORING EFFECTS:** 52-week high anchoring | Round number anchoring (₹100, ₹500, ₹1000, ₹2000)

**EARNINGS ANNOUNCEMENT DRIFT (PEAD):** After positive earnings surprise: Stock continues rising for weeks

**DISPOSITION EFFECT:** Investors sell winners too early | Hold losers too long

**MOMENTUM CRASHES:** Momentum strategies periodically crash hard | Usually when regime changes suddenly

---

### Category 13 — Corporate Governance Research

**PROMOTER BEHAVIOR SIGNALS:** Promoter pledge ratio | Promoter open market buying

**AUDIT QUALITY SIGNALS:** Auditor change | Qualified audit opinion

**RELATED PARTY TRANSACTIONS:** Excessive RPT = money leakage from company

---

### Category 14 — Global Macro Connections

**DOLLAR MILKSHAKE:** Strong USD → EM (including India) outflows | Weak USD → EM inflows

**CARRY TRADE DYNAMICS:** Japan near-zero rates fund global carry trades | When JPY strengthens → carry unwind → EM selloff

**FED BALANCE SHEET:** Fed QE (expanding) → liquidity abundant → Nifty rises | Fed QT (contracting) → liquidity tightens → Nifty falls

**CRUDE OIL IMPACT:** India = large crude importer | High crude → inflation → RBI hawkish → Nifty falls

---

### Category 15 — Statistical Validation Methods

**INFORMATION COEFFICIENT (IC):** The most important research metric. Measures predictive power of a signal. IC > 0.05 = genuine edge | IC > 0.10 = strong edge (rare, treasure it) | IC < 0.02 = noise, retire the signal

**IC DECAY:** How long does signal remain predictive?

**FACTOR QUANTILE ANALYSIS:** Split signals into 5 buckets by strength | Q1 = weakest signals, Q5 = strongest

**SHARPE RATIO INTERPRETATION:** Sharpe < 0.5: poor (index fund beats this) | Sharpe 0.5-1.0: acceptable | Sharpe 1.0-2.0: good (professional grade) | Sharpe > 2.0: exceptional (verify carefully)

---

### Category 16 — Tool Rationale

**WHY ALPHALENS FIRST:** Before building complex ML models, before optimizing parameters, before deploying real money — we need to know: does the signal have alpha at all?

**WHY DUCKDB:** When agent_logs has 10,000 rows: pandas query: 4 seconds | DuckDB query: 0.04 seconds

**WHY MLFLOW:** Every experiment logged with every parameter. Compare any two experiments instantly. Reproduce any result exactly.

**WHY PANDAS-MARKET-CALENDARS:** Our hardcoded holiday list has 14 dates. NSE has 15-20 holidays per year. We are missing Eid, Muharram, and others.

**WHY STAND ON GIANTS (tool philosophy):** MJONAI's unique value is NOT: Building a better ARIMA implementation | Building a better backtester | Building better portfolio optimization. MJONAI's unique value IS: Indian market knowledge | Multi-strategy research framework | AI agent evaluation layer | Systematic deployment pipeline | Founder's judgment

---

### Category 17 — Forecasting vs Prediction

**PREDICTION:** "RELIANCE will be ₹1,500 in 30 days." This is almost impossible reliably.

**FORECASTING:** "Given current conditions, probability of positive return in 5 days = 62%." This is what we are doing. Not point prediction. Probability estimation.

**THE EDGE IS IN PROBABILITIES:** If our signals have 58% win rate: 100 trades × 58 wins × 2R average = +116R | 100 trades × 42 losses × 1R average = -42R | Net: +74R

**WHY MOST FORECASTING FAILS:** Overfitting | Regime change | Transaction costs | Look-ahead bias

---

### Category 18 — Research Lab Data Flow

**WHAT WE GENERATE IN RESEARCH MODE:**

Per paper trade closed: strategy_id, version, symbol | entry_date, exit_date, holding_days | market_state, mqi_level, vix_at_entry | confidence, sl_method, bull_verdict | devil_checks_passed (8 checks) | outcome (WIN/LOSS) | actual_rr, gross_pnl, net_pnl | time_of_day, day_of_week, sector

**This data answers (after 500 trades):**

**STRATEGY PERFORMANCE:** Which strategy has highest win rate? | Which strategy has highest risk-adjusted return? | Which strategy works in which regime?

**SIGNAL QUALITY:** Is RSI in 55-70 predictive? (Alphalens IC test) | Does structure SL outperform ATR SL? | Does swing low confirmation improve win rate?

**AGENT ACCURACY:** When Bull says BUY vs NEUTRAL — does it matter? | When devil checks warn — do warned trades lose? | Does Supervisor APPROVE/REJECT align with outcomes?

**TIMING ANALYSIS:** Which time of day produces best win rate? | Which day of week is best? | Does Monday differ from Friday?

**REGIME DEPENDENCY:** Win rate in BULL vs NEUTRAL vs BEAR? | Win rate at VIX <14 vs 14-20 vs >20? | Does MQI HIGH vs MEDIUM predict outcome?

---

### Category 19 — The Unknown Unknowns

**Jim Simons said:** "We search for anomalies in data." He did NOT say: "We implement RSI and MACD and EMA."

**For MJONAI:** When we log EVERYTHING about each trade, we create the ability to find unexpected patterns.

**Log at signal time:** Phase of moon? (some quants test this) | Distance from last 52-week high? | Number of consecutive up days before signal? | VIX percentile rank (not absolute level)? | Nifty 500 breadth at signal time? | Day of month (1st-7th vs 8th-15th vs...)? | Distance from previous all-time high?

**The discipline is:** Log everything. Analyze systematically. Test rigorously. Accept what data says. Reject intuition that data contradicts.

---

### Category 20 — The Philosophical Foundation

**WHY SYSTEMATIC TRADING:** Human traders have: Loss aversion (losses feel 2.5× gains) | Overconfidence after wins | Revenge trading after losses | FOMO (Fear Of Missing Out) | Anchoring to purchase prices | Herding with crowd

**MJONAI removes these by:** Predetermined entry rules (no FOMO) | Predetermined SL (no loss aversion override) | Predetermined position size (no overconfidence) | Cooling period after losses (no revenge trading) | Psychology guard tracks bias attempts

**WHY PAPER TRADING MATTERS:** "In theory there is no difference between theory and practice. In practice there is." — Yogi Berra

**WHY 3-5 EDGES NOT 100:** "Diversification is protection against ignorance. It makes little sense if you know what you are doing." — Warren Buffett

**WHY COSTS MATTER MORE THAN PEOPLE THINK:** Strategy with 60% win rate: Gross: fantastic | After 1% round-trip cost: good | After 2% round-trip cost: breaks even | After 3% round-trip cost: loses money

**THE COMPOUNDING INSIGHT:** At 1.5% monthly net: Year 1: ₹1L → ₹1.19L | Year 3: ₹1L → ₹1.70L | Year 5: ₹1L → ₹2.43L | Year 10: ₹1L → ₹5.90L. At 2.0% monthly net: Year 10: ₹1L → ₹10.65L. The difference between 1.5% and 2.0% monthly = 80% more wealth in 10 years.

---

## SECTION 39 — WHAT THE DATA WILL TELL US

**After 100 paper trades per strategy:**

**QUESTION 1:** Does RSI 55-70 actually predict returns? Method: Alphalens IC test on RSI values vs forward returns | Answer: IC > 0.05 = yes | IC < 0.02 = no

**QUESTION 2:** Does structure SL outperform ATR SL? Method: Compare win rate + actual RR for both methods

**QUESTION 3:** Does Bull agent BUY verdict add value? Method: Compare trades where Bull = BUY vs NEUTRAL | If BUY win rate significantly > NEUTRAL win rate: agent adds value

**QUESTION 4:** Which devil check prevents most losses? Method: When check would have warned, did trade actually lose?

**QUESTION 5:** Which time of day is best? Method: Win rate by 30-minute window | Expected: 9:30-10:30 and 2:00-3:00 should be best

**QUESTION 6:** Which regime suits each strategy? Method: Win rate by market_state × strategy_id

**QUESTION 7:** What is optimal confidence threshold? Method: Win rate by confidence range (50-60, 60-70, 70-80, 80+)

**QUESTION 8:** Does sector cap enforcement help? Method: Track would-be trades blocked by sector cap | Compare their outcomes vs trades that passed

---

## SECTION 40 — RESEARCH WORKFLOW

**WEEK 1-2 (data generation):** System runs in RESEARCH mode. All strategies generate signals simultaneously. All trades logged to agent_logs with full context. Target: 50+ trades minimum before any analysis.

**WEEK 3 (first analysis):** Export agent_logs to CSV. Load into DuckDB for fast SQL analysis. Run Alphalens per strategy per signal. Generate QuantStats report per strategy. Log all experiments to MLflow.

**WEEK 4 (deep dive):** Which strategies have positive IC? Which regimes produce best win rates? Which devil checks correlate with loss prevention? Is Bull agent adding alpha or noise?

**MONTH 2 (iteration):** Compare strategy versions in MLflow. Which parameter change improved IC? Which regime does each strategy need?

**MONTH 3 (graduation criteria):** Strategy with 200+ trades AND IC > 0.05: → Apply full backtesting (walk-forward). → If backtest passes phase gates. → Graduate to LIVE mode. Strategy with IC < 0.02 after 200 trades: → Retire. Document lessons. → Archive (not delete).

**THE DISCIPLINE:** Follow the data. Not the theory. If data says RSI 55-70 has no IC: retire it. If data says Monday signals win more: exploit it. If data says devil check X prevents 0 losses: remove it.

---

## SECTION 41 — KEY INSIGHTS FROM SESSION 7

**INSIGHT 1 — Paper limits were wrong:** We were applying ₹2L real money rules to a ₹0-at-risk simulation. Chairman identified this. Board corrected it. Impact: Research mode = unlimited positions, Nifty 500.

**INSIGHT 2 — Fixed position size for comparability:** Risk-based sizing makes trades incomparable. 29 shares RELIANCE vs 5 shares TCS vs 100 shares SBIN = different capital deployed = distorted statistics. Fixed ₹10k = all trades comparable = meaningful analysis.

**INSIGHT 3 — Devil checks WARN not VETO in research:** In live mode: devil checks VETO to protect capital. In research mode: devil checks WARN + log outcome. This lets us discover: do these checks actually prevent losses?

**INSIGHT 4 — Strategy registry enables parallel testing:** One strategy tested sequentially = months per strategy. Multiple strategies tested simultaneously = months total. Registry with base class = consistent interface for all.

**INSIGHT 5 — Tool philosophy:** Don't build what exists. Build what only you can build. statsmodels for ARIMA. xgboost for ML. MJONAI builds: Indian knowledge + agent evaluation + deployment.

**INSIGHT 6 — North star is narrow, not broad:** The temptation: build everything, test everything. The discipline: find 3-5 edges, execute them well. Complexity ≠ edge. Simplicity that works consistently = edge.

**INSIGHT 7 — The research lab mindset:** Every signal = hypothesis. Every paper trade = experiment. Every closed trade = data point. Analysis = reading the data. Deployment = acting on statistical truth. This is Jim Simons' methodology. Applied to Indian equity markets. By a founder with Indian market context. That combination is the genuine edge.

---

## SECTION 42 — CHANGELOG

### v2.0 — 06 May 2026 (Session 16)

| # | Change | Detail |
|---|--------|--------|
| 1 | Strategy independence (SS19) | All 7 strategies run independently per symbol |
| 2 | Scan overlap lock | `_scan_running` flag prevents concurrent scans |
| 3 | Forward returns module | `research/forward_returns.py` for Alphalens IC |
| 4 | Short strategies | S06 MomentumShort + S07 MeanReversionShort |
| 5 | Signal direction | `signal_direction` field (LONG/SHORT) in all signals |
| 6 | Rate limit backoff | 2.1s minimum between Groq API calls (FIX-M) |
| 7 | NaN guards | All strategies handle missing data gracefully |
| 8 | Year boundary | Holiday cache refreshes on Jan 1 (FIX-O) |
| 9 | MQI fix | LOW allows 1 signal, VERY LOW allows 0 (FIX-MQ13) |
| 10 | WebSocket fix | `_stop_requested` flag prevents unintended reconnect (FIX-T) |
| 11 | Telegram fix | SYSTEM_MODE check in signal alerts (FIX-Y) |
| 12 | Database | 12 new columns for forward returns + signal_direction |
| 13 | Research scheduler | Daily 4PM forward returns, 4:30PM report, Sunday Alphalens |
| 14 | Full audit | 27 files reviewed, 18 fixed, 9 verified working |
| 15 | Documentation | Master v2.0 + Handover v3.0 (merged 4→2 files) |

### v1.5 — 01 May 2026 (Session 7)

| # | Change | Detail |
|---|--------|--------|
| 1 | Groq model | llama-3.1-70b-versatile decommissioned → llama-3.3-70b-versatile |
| 2 | Gemini SDK | google.generativeai deprecated → google-genai==1.74.0 |
| 3 | Gemini model | gemini-1.5-flash → models/gemini-2.5-flash |
| 4 | agents/bull.py | Groq 70B. Fallback: 8B-instant. Confidence capped 80 in fallback. |
| 5 | agents/supervisor.py | Gemini 2.5. Deterministic rules in Python. LLM = transparency only. |
| 6 | risk/devil_checks.py | 8 deterministic vetoes. Pure Python. Pre-LLM. Cannot hallucinate. |
| 7 | earnings_check.py | yfinance primary + NSE fallback. Blocks within 3 trading days. |
| 8 | Signal pipeline | technical→confidence→earnings→sector→LTP→levels→devil→bull→supervisor |
| 9 | Bug4 | Dynamic limits: BULL+HIGH=5, NEUTRAL+HIGH=3, BEAR=1, VIX>25=1 |
| 10 | Bug5 | Time barrier = 7 trading days (not calendar). Skips weekends + holidays. |
| 11 | Bug12 | Earnings check: yfinance + NSE fallback. isinstance list check added. |
| 12 | Bug16 | Sector cap: max 2 stocks, max 25% Growth pool. SECTOR_MAP in constants. |
| 13 | H_T3 | close_paper_trade() closes tranches before parent. |
| 14 | H_T4 | get_open_trades_with_pnl() uses quantity_remaining. |
| 15 | Research Lab | RESEARCH vs LIVE modes. Paper = laboratory. |
| 16 | Strategy Registry | Parallel testing. 5 strategies. Base class. |
| 17 | Tool stack | 20 categories documented. Priority install order. |
| 18 | Oracle prepped | groq + google-genai installed. Keys set. git pull done. |
| 19 | requirements.txt | Added: google-ai-generativelanguage, google-genai, groq |
| 20 | Section 38 | All 10 Session 7 decisions documented. |

### v1.4

```
Fix 1: RSI range corrected (directional not neutral)
Fix 2: Devil architecture separated (deterministic vs LLM)
Fix 3: Kill Line vs Level 3 clarified
Fix 4: Week 1 task updated (AngelOne SDK verification)
Fix 5: agent_weight_log added as Table 13
```

### v1.3 — 15 Fixes

```
Fix 1:  TA-Lib Windows → mandatory WSL2
Fix 2:  RAM exhaustion → Ollama on-demand only
Fix 3:  Render.com → GitHub Actions overnight
Fix 4:  Shoonya auto-failover → manual only
Fix 5:  FII/DII real-time → acknowledged T-1 only
Fix 6:  Groq rate limits → fallback trigger defined
Fix 7:  Supabase 500MB → retention policy added
Fix 8:  Next.js 16 → corrected to 15
Fix 9:  VectorBT → Backtrader alternative noted
Fix 10: Confidence formula → component fail = auto-reject
Fix 11: "Recently" → defined as 90 calendar days
Fix 12: Devil VETO via LLM → VETO is deterministic code only
Fix 13: SHAP → replaced with Decision Transparency Report
Fix 14: Polymarket → Tier 3, Metaculus alternative
Fix 15: Kill Line vs Level 3 → Level 3 = system integrity only
```

---

## SECTION 43 — BOARD & GOVERNANCE

### How To Invoke The Board

```
Every new session starts with:
"Board assembled. All tiers active.
 Read all files completely before responding.
 Today is [date]. Continue from [priority]."

Governance tier invoked based on decision type:
  Simple code fix      → Tier 1 only
  Strategy decision    → Tier 1 + 2
  India market         → Tier 1 + 2 + 3
  Global macro         → Tier 1 + 2 + 4
  Compliance           → Tier 1 + 2 + 5
  Major architecture   → All tiers
  Founder veto         → Overrides all votes always
```

### FOUNDER / CHAIRMAN

```
Mani Sankar Reddy (MJ Reddy)
Final word on all decisions.
Veto overrides all board votes always.
```

### TIER 1 — OPERATING COMMITTEE (Every Session)

| Role | Responsibility |
|------|---------------|
| CEO | Strategic direction. No scope creep. |
| CTO | Architecture compliance. Master file enforcement. |
| CFO | Capital rules. Cost model. Tax accuracy. |
| Developer | Code changes. One at a time. |
| QA/Tester | Verify before commit. |
| Analyst | Cross-reference documents. |
| PM/Manager | Priorities. Sequencing. |
| Security | Credentials. Vulnerabilities. |
| SysAdmin | Oracle. Deployment. |
| Risk Officer | Risk engine integrity. |

### TIER 2 — FINANCIAL PROFESSIONALS

Investment Banker | Portfolio Manager | Hedge Fund Manager | Data Scientist/AI Architect | Equity Research Analyst | Market/Technical Analyst | Proprietary Trader | CA/CPA/Tax Advisor | Corporate Finance Director | Financial Advisor/Wealth Manager | SEBI Advisor | RBI Governor (persona) | Quant Analyst | Options/Derivatives Specialist | Macro Economist

### TIER 3 — INDIAN LEGENDS

| Name | Lens |
|------|------|
| Rakesh Jhunjhunwala | "Big Bull" — conviction, long-term |
| Radhakishan Damani | DMart — value, margin of safety |
| Raamdeo Agrawal | MOFSL — QGLP framework |
| Sunil Singhania | Abakkus — growth at reasonable price |
| Ashish Kacholia | Mid-cap deep dives |
| Mukul Agrawal | Small/mid-cap conviction |
| Vijay Kedia | SMILE framework, wealth creation |
| Anil Kumar Goel | Contrarian value, patience |
| Dolly Khanna | Turnaround specialist |
| Ashish Dhawan | ChrysCapital — PE mindset |

### TIER 4 — GLOBAL LEGENDS

| Name | Lens |
|------|------|
| Warren Buffett | Value, moats, never lose money |
| George Soros | Reflexivity, macro bets |
| Ray Dalio | All Weather, debt cycles, principles |
| Peter Lynch | One Up, PEG ratio |
| Charlie Munger | Mental models, inversion |
| Benjamin Graham | Father of value, margin of safety |
| Paul Tudor Jones | Macro, risk first, never average loser |
| Stanley Druckenmiller | Concentration, asymmetric bets |
| Jesse Livermore | Tape reading, trend following |
| Ed Seykota | Systematic, trend, risk discipline |
| Jim Simons | Quantitative, pattern recognition |

### TIER 5 — TECH & REGULATORY

| Role | Focus |
|------|-------|
| Wall Street Quant | Execution algos, factor models |
| SEBI Director | Algo classification, compliance |
| RBI Governor | Monetary policy, liquidity |
| AI/ML Researcher | Model architecture, LLM reliability |
| Cybersecurity Expert | API security, credentials |
| Finance Educator | Communication clarity |

### Board Operating Rules

```
1. Board thinks independently — not blindly follows documents
2. Challenge anything that seems wrong
3. Discuss before writing a single line of code
4. Show exact SEARCH FOR → REPLACE WITH always
5. Verify every change before moving to next
6. Batch changes to same file in one session
7. One commit per logical concern
8. Deploy to Oracle only after 3:40 PM IST
9. Never change trade monitoring during market hours
10. Never assume — ask Founder if unsure
11. Check git status and git diff before every commit
12. Never hardcode constants — use core/constants.py
13. Never query Supabase outside db/repository.py
14. Never import from main.py into any other module
15. Founder veto overrides all votes always
```

---

```

════════════════════════════════════════════════════

MJONAI MASTER v2.0 — COMPLETE

════════════════════════════════════════════════════

Version:         v2.0
Previous:        v1.5 (01 May 2026)
Updated:         06 May 2026 — Session 16
Sections:        43
Active Strategies: 7 (S01-S07)
Forward Returns: Enabled (Alphalens integration)
Signal Direction: LONG + SHORT support
Scan Overlap:    Lock implemented
Documentation:   Merged from 4 files (Master + Intelligence + Session 16)

Board sign-off:
  CEO ✅  CTO ✅  CFO ✅  Risk ✅  QA ✅
  Quant ✅  Trader ✅  SysAdmin ✅  PM ✅
  Security ✅  Data Scientist ✅

VERDICT: Complete. Ready for research data collection.

════════════════════════════════════════════════════
```

---

**MJONAI MASTER v2.0 — COMPLETE.**
