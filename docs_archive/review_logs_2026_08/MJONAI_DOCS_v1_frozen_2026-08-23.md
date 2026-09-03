# MJONAI â€” MASTER DOCUMENTATION
*(Single consolidated source. Rebuilt from every project doc, deduplicated, Aug 2026.)*

---

## 1. IDENTITY, PHILOSOPHY & WORKING RULES

### What MJONAI is (one sentence)
A modular AI-assisted quantitative trading and research platform focused on **probabilistic edge discovery** in Indian equities â€” not price prediction, not a chatbot, not a retail signal app.

### Core Philosophy
> **Probability estimation over prediction.**
We do not predict price. We estimate conditional probabilities, identify regime-aware edges, log everything, validate rigorously, deploy only what survives.

### Honest Status (anchor snapshot)
| Area | Status |
|---|---|
| Architecture | Good â€” modular, layered, orchestration in place |
| Governance docs | Strong (docs/current_state/) |
| Runtime skeleton | Decent â€” main.py boots, scheduler works |
| Intelligence subsystem | Sufficient â€” frozen as support infra |
| Telemetry richness | Very strong (signal_intelligence_log captures everything) |
| Engineering cognition | Strong (impact_analyzer, knowledge_engine) |
| **Research organization** | **Immature â€” primary bottleneck** |
| **Validation rigor** | **Early â€” primary bottleneck** |
| **Edge validation** | **Early â€” primary bottleneck** |
| Portfolio intelligence / Runtime resilience / Operational maturity | Early / Medium / Early |

### The Anti-Drift Rules (read every session)
1. Each session continues from the last â€” check ACTIVE_WORK_STATE first.
2. One concrete change per session â€” finish, verify, commit.
3. Edit existing files. NEVER create _v2, _new, _combined versions.
4. No new features without explicit ask.
5. No reopening settled decisions (intelligence subsystem frozen, Master/Handover archived).
6. Always show before/after diff before any file change.
7. Update ACTIVE_WORK_STATE.md at session end.

### Subsystem Status (one line each)
- main.py â€” runtime entry, scheduler, healthy
- orchestration/ â€” clean 5-file refactor
- core/ â€” constants, time, market_state, MQI
- data/angelone/ â€” WebSocket + token map, working
- strategy/signal_scanner.py â€” wires all 7 strategies, too big but working
- strategy/registry/ â€” strategies S01â€“S07, all live
- risk/ â€” devil_checks, trade_risk, emergency_triggers
- agents/ â€” Bull + Supervisor live, Bear scaffolded (not wired)
- execution/paper.py â€” works, too big
- db/repository.py â€” works, god-object (TD-002)
- communication/ â€” Telegram + commands
- research/ â€” canonical pipeline being defined (was current focus)
- mjonai_intelligence/ â€” frozen support infra, don't touch
- Test/ â€” was 10 duplicate backtests, archive 9 (cleanup)

### Immediate Next Steps (canonical order)
1. Declare research v2 canonical, archive v1 scripts.
2. Fix DuckDB system_log bug (B2).
3. Run clean grid test on all 499 Nifty 500 stocks.
4. Surface real edges: compute IC per (indicator, params, direction); find IC > 0.05 across regimes.
5. Apply walk-forward discipline: 3yr in-sample + 1yr out-of-sample; if OOS drops >30% vs IS â†’ mark overfit.
6. Deferred until edges exist: splitting big files, new strategies, live trading prep.

### Frozen (don't touch)
- mjonai_intelligence/ â€” completed support tooling
- F&O / MCX / crypto / NCDEX â€” deferred long-term vision
- agents/bear.py, Economist/Devil agents â€” wait for edges
- Shoonya broker integration â€” defer until live trading
- All Tier 2â€“4 capital activation work

### How to Start an AI Session (verbatim prompt)
> "Continuing MJONAI. Read 01_DIRECTION.md first. Then read docs/current_state/ACTIVE_WORK_STATE.md to see the current task. Behave as continuation engineering lead, not architecture generator. One concrete change per session. Show before/after diffs. No new features without explicit ask."

### Parked for Future Evaluation
**Kronos â€” Foundation Model for Financial K-Lines** (github.com/shiyu-coder/Kronos, arXiv 2508.02739, AAAI 2026, MIT). Pre-trained decoder-only Transformer for OHLCV forecasting; 12B K-line records, 45 exchanges; sizes mini 4.1M / small 24.7M / base 102.3M / large 499.2M.
- Why parked: zero validated strategies; heavy ML deps; philosophy mismatch (predicts price vs probability estimation).
- Evaluate when: after 7 strategies have ICs and at least one shows IC > 0.05. Then zero-shot on same Nifty 50 benchmark, isolated in research/experiments/kronos_eval/.
- If integrated: becomes one more strategy in registry competing for IC. Does NOT touch agents, risk, execution, or architecture.

## 2. THE GOLDEN RULES â€” HARDCODED, NEVER OVERRIDE (Constitution)

These rules are the constitutional law. No signal, no agent, no user, no code change can break them. Every module must enforce them independently.

### Non-Negotiable Rules
- Capital protection over profit â€” ALWAYS, in every situation without exception
- Never override a stop loss once set â€” loss aversion is the enemy of survival
- Minimum 3 of 4 AI agents must agree for any signal to pass
- 2-2 agent split = wait 15 minutes, re-debate, still split = REJECT the signal
- Devil Agent VETO overrides all other votes â€” no appeal, no override
- Confidence below 65% = REJECTED automatically â€” no exceptions
- Risk:Reward below 2.0 = REJECTED automatically â€” no exceptions
- Never risk more than 2% of capital per trade
- Maximum 4 signals per day â€” HARD LIMIT for intraday, no override possible
- Psychology guard CANNOT be disabled by any user, admin, or code change
- Paper trade minimum 30 days before any real money is deployed
- Real money only after 65%+ win rate sustained over 20+ trades in that asset class
- Each asset class must prove 60%+ accuracy independently before next class is added
- SEBI compliance: personal use only until Research Analyst registration is received

### The Philosophical DNA â€” 10 Masters
| Master | What MJONAI borrows |
|---|---|
| Warren Buffett | Business quality, long-term compounding, never invest in what you don't understand |
| Jesse Livermore | Market timing precision, trend following, "sitting" â€” patience for the perfect setup |
| Ray Dalio | All Weather portfolio, macro analysis, risk parity, debt cycle awareness |
| Paul Tudor Jones | Strict risk management, never average a losing position, preserve capital first |
| Peter Lynch | Growth identification, PEG ratio, invest in what you understand |
| John Bogle | Index fund wisdom, cost minimization, compounding over short-term trading |
| Benjamin Graham | Margin of safety, deep value, fundamental analysis as foundation |
| George Soros | Reflexivity â€” market participants influence fundamentals, currency dynamics |
| Jim Simons (RenTech) | Statistical patterns, data-driven decisions, adaptive models, no human override |
| Daniel Kahneman | Behavioral finance, cognitive bias taxonomy, psychology guard design |

## 3. THE 8-LAYER EVIDENCE FRAMEWORK (Signal Philosophy)

Technical indicators alone: **52â€“55% win rate**. Same indicators confirmed by all 8 layers: **62â€“68% win rate**. The indicators do not change â€” the confirmation does. A signal is when 8 completely independent data sources all agree simultaneously.

### Layer 1: Technical Indicators (Necessary But Not Sufficient)
**Momentum:** RSI(14) â€” 55â€“70 zone = momentum building without overbought; MACD â€” histogram positive + line crossing signal line upward; Stochastic â€” crossing above 20 from oversold; ROC â€” accelerating rate; Williams %R.
**Trend:** Supertrend flip (redâ†’green = trend change, ATR band); EMA stack 9 > 21 > 50 > 200 = perfect bull alignment; ADX above 25 = strong trend, below 20 = range-bound; Ichimoku â€” price above green cloud = strong uptrend; Parabolic SAR = trailing stop, not entry.
**Structure:** Support/Resistance breakout with conviction; Fibonacci 61.8% = highest-probability reversal zone; Chart patterns (Cup & Handle, Bull Flag, Inverse H&S, Ascending Triangle); multi-timeframe alignment (5m, 15m, 1H, Daily ALL agree); Pivot Points (daily/weekly/monthly S/R); Market Profile / Value Area (fair value zone).
**Volatility:** Bollinger Band Squeeze (compress then expand = momentum).

### Layer 2: Volume & Market Microstructure
- Volume confirmation on breakouts (RVOL / relative volume)
- Volume profile / POC, value area high/low
- Order-flow proxies, large-block prints, delivery % vs average
- Time-of-day liquidity regimes (opening volume quality)

### Layer 3: Options Market Intelligence (Most Powerful Leading Indicator)
- Put-Call Ratio (PCR), Max Pain, IV Rank / IV Percentile
- Gamma Exposure (GEX) regime: positive vs negative gamma
- OI buildup/unwinding classification; smart money flow
- Expected move (Spot Ã— IV Ã— âˆš(DTE/365)); 0DTE activity

### Layer 4: Institutional Flow Intelligence
- FII/DII net cash flow (cash segment)
- FII long-short ratio in index futures; cumulative flow velocity
- Sector rotation / RRG quadrants (leading, improving, lagging, weakening)
- Gift Nifty (SGX) pre-market gap and global confluence

### Layer 5: Fundamental Quality Signals
- Earnings quality, surprise, and revision momentum
- Valuation sanity (PE/PB/PEG vs sector)
- Balance-sheet red flags, promoter holding changes
- (For equities â€” fundamental layer; not required for pure intraday)

### Layer 6: Macro & Regulatory Intelligence
- RBI MPC decisions, Union Budget day/week
- US Fed FOMC, global risk-on/off (S&P 500, crude, DXY)
- India VIX level + rate of change; regime classification
- Earnings/board-meeting blackout windows

### Layer 7: Alternative Data (The Unfair Edge)
- News/sentiment (structured, filtered)
- Social/monitoring signals (to be built systematically)
- Seasonality, event calendars, monsoon/MSP (agri)
- (Gap: this layer is the least built â€” the "unfair edge" opportunity)

### Layer 8: Pattern Memory Database (The Learning Engine)
- Deterministic setup hash per (symbol, strategy, regime, params, timeframe)
- Win-rate / expectancy / profit-factor accumulation per setup
- Laplace-smoothed win rate; quarantine after repeated failures (3+ in 90d)
- Feeds back into Devil Checks (pattern memory veto) and agent confidence

## 4. THE AI AGENT DEBATE ROOM

### 4.1 Architecture Overview
Multiple specialist agents analyze the same signal independently, then debate, and a Supervisor makes the final decision. The system learns from wrong calls via agent error taxonomy and weight recalibration.

### 4.2 The Five Agents
**Agent 1 â€” The Bull (Technical Analyst):** Builds the case FOR the trade using technical evidence: trend (EMA stack, ADX, Supertrend), momentum (RSI, MACD, Stochastic), volume confirmation (RVOL, CMF), price structure (S/R, patterns), options layer (PCR, GEX, IVR), market breadth. Output: verdict + confidence (0â€“100) + key reasons + concerns.

**Agent 2 â€” The Bear (Fundamental & Sentiment):** Builds the case AGAINST. Challenges with fundamentals (earnings risk, valuation), macro risks (RBI/Fed/Budget), sentiment extremes, pattern-memory failures, and correlation/concentration risk. Output: verdict + confidence + reasons + concerns.

**Agent 3 â€” The Economist (Macro Analyst):** Scores the macro backdrop: global risk-on/off, FII/DII flows, VIX regime, sector rotation stage, event proximity (MPC/FOMC/budget/earnings). Weighs in on direction and position size.

**Agent 4 â€” The Devil's Advocate (Veto Power):** Deliberately searches for reasons the trade FAILS. Has VETO authority â€” its veto overrides all other votes, no appeal. Prevents hubris and confirmation bias.

**Agent 5 â€” The Supervisor (Final Decision Maker):** Receives all agent verdicts, applies the consensus rules (below), applies deterministic gates (devil checks, MQI), and issues the final decision: APPROVE / REJECT / HOLD.

### 4.3 Consensus Logic (complete rules)
- Minimum **3 of 4** agents must agree for a signal to pass
- **2-2 split** = wait 15 minutes, re-debate; still split = **REJECT**
- **Devil Agent VETO** overrides everything â€” no appeal, no override
- Confidence < 65% = auto-reject
- Risk:Reward < 2.0 = auto-reject
- Supervisor applies final deterministic gates (MQI level, devil checks, portfolio limits) before APPROVE

### 4.4 Agent Error Taxonomy â€” How MJONAI Learns from Wrong Signals
After each closed trade, the system classifies WHY agents were wrong:
- **Data error** (bad feed, stale candle) â€” data layer fix, no agent penalty
- **Signal error** (indicators mis-fired) â€” strategy fix
- **Agent reasoning error** (wrong call given right data) â€” weight penalty for that agent on that setup type
- **Regime change** (unforeseen macro event) â€” no penalty, log the regime
- **Execution error** (slippage, late entry) â€” execution fix
Each error type has a distinct remediation path. Agent weights are recalibrated (agent_weight_log) based on accuracy over evaluated trades.

### 4.5 Agent Weight Adjustment System
- Every agent has a weight (0â€“1) that scales its vote influence
- Weights recalibrated periodically based on realized accuracy (was_correct, actual_rr)
- Recalibration logged: agent_name, old_weight, new_weight, weight_change, trigger_reason, accuracy_pct, trades_evaluated
- Prevents a persistently-wrong agent from dragging the debate down

### 4.6 Proposed New Agents (deferred)
- (Phase 21 proposals) â€” e.g., specialist sector agents, volatility specialists
- Not built; wait for validated edges first

## 5. SIGNAL ENGINE & STRATEGY LOGIC

### 5.1 Signal Generation Pipeline (canonical flow)
1. Data acquisition (live WebSocket / historical) â†’ candles + OI + depth
2. Strategy compute â†’ technical setup (entry, SL, target, confidence)
3. **8-Layer Evidence check** â†’ confirm with independent layers
4. Deterministic gates â†’ Devil Checks (8 vetoes) + MQI gating
5. AI Agent Debate â†’ Bull / Bear / Economist / Devil / Supervisor
6. Risk & sizing â†’ position sizing, tranches, limits
7. Execution â†’ paper or live (with slippage, taxes, brokerage)
8. Telemetry â†’ log everything (signal_intelligence, agent_logs, scan_log)
9. Outcome â†’ forward returns, pattern memory update, agent recalibration

### 5.2 Signal Correlation Checker (logic gap â†’ fixed)
- Prevents correlated signals from both passing (same sector / same underlying / high correlation > 0.80)
- One signal per correlated cluster per scan

### 5.3 Volatility Regime Classifier
- VIX-based confidence adjustment: high-vol regime â†’ lower confidence, smaller size
- VIX > 25 â†’ high-vol override: block new position entries

### 5.4 Time-of-Day Filter
- Liquidity time buckets: MORNING_PRIME 09:30â€“10:30, MIDDAY_HIGH 10:30â€“12:00, MIDDAY 12:00â€“14:00, AFTERNOON_PRIME 14:00â€“15:00, EXCLUDED otherwise
- Strategies matched to their best-performing session window

### 5.5 Signal Priority Queue
- When multiple signals compete for the daily cap (max 4/day), prioritize by: composite confidence, layer-count, real R:R, MQI alignment

### 5.6 Signal Staleness Decay
- Signals decay with age: older signal â†’ lower effective confidence â†’ replaced by fresher setups

### 5.7 Signal Circuit Breaker
- If N consecutive signals fail in a short window â†’ pause signal generation (feeds behavioral guard)

### 5.8 Critical Logic Gaps (historical â€” must be enforced)
- signal_correlation_checker.py âœ“
- volatility_regime_classifier.py âœ“
- time_of_day_filter.py âœ“ (time buckets)
- signal_priority_queue.py
- signal_staleness_decay.py
- signal_circuit_breaker.py
- (Each gap listed as "file X" in the original spec â€” most are now implemented in strategy/ + risk/ + core/)

### 5.9 Strategy Taxonomy (initial candidates)
| Type | Examples | Notes |
|---|---|---|
| Trend-following | Momentum RSI, Turtle Breakout, Supertrend | Needs ADX > 25, clean regime |
| Mean-reversion | RSI(2) pullbacks, Bollinger fade | Best in range-bound, low ADX |
| Breakout/volatility | Bollinger Squeeze, 52-week high | Needs RVOL confirmation |
| Price action | Liquidity sweeps, CPR, patterns | Swing, EMA50/200 filters |
| Short-side | Momentum short, mean-reversion short | Mirror of long logic |
| Intraday scalping | All-day box breakout | Volume surge + tight box |
| Options | Theta decay (selling), directional buying | Uses Greeks, IVR, GEX |

## 6. RISK MANAGEMENT SYSTEM

### 6.1 Risk Philosophy
Capital protection is the #1 rule. Position sizing is dynamic (volatility- and confidence-adjusted), never flat. Every trade carries a defined risk; the portfolio carries hard limits and kill switches.

### 6.2 Dynamic Position Sizing Framework
- Per-trade risk: 1%â€“2% of capital (INTRADAY 1.0%, SWING 1.5%, POSITIONAL 2.0%, options buying 0.5%)
- Size = (capital Ã— risk_pct Ã— market_weight Ã— confidence_weight) Ã· stop_distance
- Market weight scales down in high VIX; confidence weight scales with agent confidence
- Stop distance = ATR multiplier Ã— ATR14 (per strategy policy), clamped to min/max stop %
- Tranche splitting: 3-part partial exits with per-tranche targets (risk re-scaling after first tranche)

### 6.3 Stop Loss System
- Stop set from structure (swing low/high) or ATR (2.0Ã— typical), never arbitrary %
- **Never override a stop once set** (Golden Rule)
- Trailing SL ratchets in ATR increments; breakeven trigger after 1R
- SL stages: INITIAL â†’ BREAKEVEN â†’ 1R_LOCKED â†’ TRAILING

### 6.4 Portfolio-Level Risk (was the missing piece)
- **Portfolio Greeks aggregation** (options): portfolio-level delta/gamma/theta/vega exposure
- **Cross-asset correlation matrix**: prevent 2 highly correlated positions in same sector (> 0.80)
- Max open positions by capital tier (3 / 5 / 8)
- Max 2 stocks per sector; max 25% of growth pool per sector; 80% growth pool deployment ceiling
- Beta-weighted sector exposure caps: 18% high-beta (Realty/Metal), 30% defensives (FMCG/Pharma)

### 6.5 Hard Limits & Kill Switches
| Level | Trigger | Action |
|---|---|---|
| L1 Soft stop | 3 consecutive losses | 120-min trading halt |
| L2 Daily cap | 5 new trades/day (LIVE) | Block new entries |
| L3 Daily risk stop | âˆ’3% of capital (VIX-scaled) | Square off, halt for day |
| L4 Kill line | âˆ’15% cumulative drawdown | Square off ALL, lockout |
| Drawdown tiers | â‰¥5% / â‰¥10% / â‰¥15% | Advisory â†’ halve sizes â†’ hard kill |
- Kill switch always available on dashboard (one click â†’ cancel orders, close positions, disable signals, log, Telegram alert)

### 6.6 Black Swan & Emergency Protocols
- Crisis mode: VIX > 28 or intraday index crash â†’ halt new entries
- Budget day blackout (Feb 1), RBI MPC-day blackout, earnings blackout (4h window)
- Emergency triggers broadcast to Telegram/Discord + risk_events table
- Behavioral guard: 2 consecutive losses â†’ 30m pause; 2 same-symbol â†’ 45m lock; 4 losses â†’ full-day lockout; after 14:30 IST losses stop trading for the day
- GARCH overnight gap risk model: veto if expected gap > 1.5Ã— SL distance
- Volatility-scaled daily stop via VIX

### 6.7 Asset-Class-Specific Risk Rules
- **Equities:** standard ATR stops, delivery/intraday tax model
- **Options:** premium-based stops (buying 15â€“25%, selling 10â€“20%); delta-adjusted sizing; theta-awareness; expiry-day scaling
- **Commodities/currency:** contract lot sizes, freeze quantities, MCX/CTT tax model
- **Crypto (future):** 24/7 liquidity, VDA 31.2% tax, expiry Friday awareness

## 7. TAX ENGINE & CAPITAL GAINS (Indian framework)

### 7.1 Capital Gains (Finance Act 2024, incl. 4% Health & Education Cess)
| Type | Rate | Effective |
|---|---|---|
| STCG (equity, held < 12 months) | 20% | 20.80% |
| LTCG (equity, held > 12 months) | 12.5% | 13.00% |
| LTCG exemption | â‚¹1,25,000/yr | threshold |
| Crypto VDA (Sec 115BBH) | 30% flat | 31.20% |
- FIFO lot matching for holdings (execution/tax.py)

### 7.2 Transaction Friction (per-trade model)
| Charge | Rate | Basis |
|---|---|---|
| Brokerage | min(0.03%, â‚¹20) | turnover |
| STT Equity Delivery | 0.10% | turnover, both sides |
| STT Equity Intraday | 0.025% | sell side |
| STT Futures | 0.02% | sell side |
| STT Options Premium | 0.10% | premium, sell side |
| NSE Turnover (cash) | 0.00297% | turnover, both |
| BSE Turnover (cash) | 0.00375% | turnover, both |
| NSE F&O turnover | 0.00173% fut / 0.03503% opt | both |
| MCX turnover | 0.00210% | both |
| SEBI fee | â‚¹10/crore (0.0001%) | turnover |
| Stamp duty delivery buy | 0.015% | buy value |
| Stamp duty intraday buy | 0.003% | buy value |
| GST | 18% | on brokerage + exchange + SEBI fees |
| DP charges | â‚¹15.34 | per delivery debit (CDSL â‚¹13 + 18% GST) |

### 7.3 FIFO Lot Tracker (tax engine)
- Tracks lots per symbol: buy date, quantity, cost basis
- Sells matched FIFO â†’ realized gain/loss per lot
- Auto-classifies STCG vs LTCG by holding period
- Tracks STT/CTT/stamp duty per lot for accurate net P&L
- Handles partial exits and delivery vs intraday (MIS) separately

### 7.4 Critical Tax Calculations the System Must Do
- Net P&L after ALL friction (gross âˆ’ STT âˆ’ exchange âˆ’ SEBI âˆ’ stamp âˆ’ brokerage âˆ’ GST)
- Real risk-reward after taxes (devil check 6): net_reward/net_risk â‰¥ 2.0
- Yearly realized gain report, LTCG exemption tracking
- (Legal) tax-arbitrage awareness: delivery vs intraday optimization, FIFO selection

### 7.5 Wealth Lifecycle (from original v4.0 vision â€” planned modules)
- Life-stage financial planning; insurance as wealth foundation; debt management
- Real-returns education; compounding visualizations; goal-based planning
- Government schemes; estate planning; wealth transfer
- (These are Phase-22+ wealth modules, beyond the trading core)

## 8. BACKTESTING & VALIDATION DISCIPLINE

### 8.1 The Most Critical Fixes (before trusting any backtest)
1. **Survivorship bias fix** â€” universe must include delisted/dead stocks for the period tested, not just today's Nifty constituents
2. **Look-ahead bias prevention** â€” signals may only use data available AT the bar; no future info (no full-period normalization, no future price in indicator windows)
3. **Realistic execution assumptions** â€” slippage, brokerage, STT, stamp duty, GST, freeze quantities, partial fills
4. **Multiple-testing correction** â€” every parameter combo tested is a "trial"; use DSR / White's Reality Check

### 8.2 Walk-Forward Validation Framework (mandatory)
- Rolling windows: train (in-sample) â†’ test (out-of-sample)
- Default: 3y train + 1y test, step 1y (configurable)
- Each window: grid-optimize params on TRAIN slice â†’ apply best params to TEST slice (never re-fit on test)
- **WFE (Walk-Forward Efficiency)** = OOS return Ã· IS return Ã— 100; benchmark > 50% = robust
- If OOS degrades > 30% vs IS â†’ mark overfit, do not pursue

### 8.3 Overfitting Prevention Stack (mandatory)
- **Deflated Sharpe Ratio (DSR)** â€” Bailey & LÃ³pez de Prado: corrects Sharpe for selection bias over N trials
- **White's Reality Check** â€” stationary bootstrap (1000Ã—) p-value; significant if p < 0.05
- **Monte Carlo drawdown simulation** â€” reshuffle returns â†’ drawdown distribution â†’ tail risk
- **IC analysis** â€” Information Coefficient per (indicator, params, direction); pursue only IC > 0.05 across regimes
- Forward-return windows: intraday 5/15/30/60/120 min; swing 1/3/5/10/20 days

### 8.4 Complete Performance Metrics (canonical set)
- Trades, wins, losses, breakeven; win rate % / loss rate % / breakeven rate %
- Gross profit, gross loss, net profit; avg win, avg loss; profit factor; payoff ratio
- Expectancy (= avg return per trade); avg planned vs actual R:R
- Best/worst trade; consecutive wins/losses; avg holding time/duration
- Max drawdown %, recovery factor, CAGR, Sharpe, Sortino, Calmar
- Avg confidence, avg entry score, avg technical score, avg position size
- Strategy stability score; comparison by market state / MQI / sector / entry time / mode

### 8.5 Research Discipline (current-phase rules)
- Canonical workflow: one entrypoint, one truth (mjonai-research engine)
- Zero hardcoded symbols (dynamic universes); zero hardcoded stops (ATR-based)
- Edges must survive: IC > 0.05 across multiple regimes â†’ walk-forward pass â†’ promotion to live consideration
- Research findings documented before any strategy is deployed

## 9. DATA STRATEGY & MARKET DATA LAYER

### 9.1 Data Source Hierarchy
| Market | Primary | Fallback |
|---|---|---|
| Indian equities (NSE/BSE) | Angel One SmartAPI (live) / scrip master | yfinance |
| Indian historical candles | Angel historical API (1mâ€“1d) | yfinance (.NS/.BO) |
| Global macro (SPX, crude, DXY, VIX) | yfinance | DB stale fallback |
| India VIX | yfinance (^INDIAVIX) | DB fallback |
| Global/US equities (future) | Tiingo (chosen over Yahoo â€” regression fix) | Yahoo last-resort |
| Options chain (live) | Angel One option chain | â€” |
| FII/DII flows | (NSE/SEBI feeds, per spec) | â€” |
| NCDEX agri (future) | named vendor feeds (per v4.1) | â€” |

### 9.2 Canonical Data Schema (candle)
`timestamp, open, high, low, close, volume, open_interest, amount?` â€” OHLCV is the contract; volume/amount optional for models that accept them.

### 9.3 Data Pipeline
- Live: Angel WebSocket (SmartWebSocketV2) â†’ in-memory live_prices â†’ scanners
- Historical: downloader â†’ ParquetStore cache (`storage/parquet/{provider}/{exchange}/{symbol}/{tf}.parquet`) â†’ MarketDataService (cache-first, provider fallback)
- Instrument master: Angel scrip master JSON â†’ token_map (self-healing, daily sync, local cache)
- Sector indices for breadth/RRG: sector token map

### 9.4 Data Quality & Provenance
- DataQuality enum: CONFIDENT / STALE / DEGRADED / FALLBACK â€” every factor tags its provenance
- Zero free points on data failure (MQI: degraded â†’ no trade day)
- Feed staleness: > 120s without ticks during market hours = stale â†’ WS supervisor restarts
- Instrument master failure â†’ Telegram alert, cache fallback

### 9.5 Data Gaps & Mitigation (honest)
- Options historical data for backtesting â€” vendor needed (named in v4.1)
- NCDEX data source â€” not confirmed (blocking agri)
- FII/DII daily flows â€” feed reliability
- Alternative data (Layer 7) â€” least built, the "unfair edge" opportunity

## 10. ARCHITECTURE & TECHNOLOGY STACK

### 10.1 High-Level Architecture (3 layers)
1. **mjonai-build** â€” 24/7 operational runtime: data feeds, scanning, risk gates, AI agents, execution (paper/live), telemetry
2. **mjonai-research** (merged INTO build as `engine/`) â€” research & validation: backtests, walk-forward, optimization, benchmarks
3. **mjonai-dashboard** â€” web UI: FastAPI backend + Next.js frontend, reads the shared Supabase telemetry

**Shared truth:** Supabase (15 tables) written by build, read by dashboard. Local JSONL journals as durable replay buffers.

### 10.2 Technology Stack
| Layer | Tech |
|---|---|
| Language | Python 3.11 (do not use 3.12/3.13/3.14) |
| Live feed | Angel One SmartWebSocketV2 (websocket-client) |
| Broker API | Angel One SmartAPI (smartapi-python) + TOTP (pyotp) |
| Data | yfinance (live macro + research), pandas-market-calendars |
| Storage | Supabase (Postgres), DuckDB (research results), Parquet (candle cache), JSONL journals |
| Backtest/research | pandas, numpy, scipy, pyarrow, duckdb |
| AI agents | GROQ (llama-3.3-70b-versatile), Gemini (gemini-2.5-flash), generic OpenAI-compatible (deepseek-chat); deterministic rule-engine fallback |
| Dashboard backend | FastAPI + uvicorn + pydantic |
| Dashboard frontend | Next.js 14 (React), Tailwind |
| Auth | API-key header (X-API-Key), WebSocket token |
| Alerts | Telegram bot + commands, Discord webhooks |
| Deployment | Windows dev; Oracle Cloud Ubuntu VM (systemd mjonai.service); Render (historical) |

### 10.3 Key Architectural Decisions
- **Dual-key live gate:** SYSTEM_MODE (RESEARCH/PAPER/LIVE) + LIVE_EXECUTION_AUTHORIZED â€” both must be set to trade live
- **Modes are data:** every record tagged system_mode (RESEARCH/PAPER/LIVE) for clean isolation & comparison
- **Deterministic over stochastic:** all risk gates pure Python; LLM only after deterministic checks; rule-engine fallback when LLMs fail
- **Repository facade:** db/repository.py is the single persistence gateway (39+ callers)
- **Local journal replay:** every DB write mirrored to local JSONL â†’ replay on reconnect (offline resilience)
- **Strategy contract:** research strategies use ParameterSet/configure() for grid-search; build strategies use class-attr params for live scanning â€” same strategy IDs, different contracts (deliberate)
- **Event-driven comms:** dispatcher + in-process event bus (publish_event) + WebSocket manager for dashboard push

## 11. DATABASE SCHEMA (Supabase â€” 15 tables)

All tables: `id UUID PK`, `created_at/updated_at TIMESTAMPTZ`, `system_mode VARCHAR(32) DEFAULT 'RESEARCH'`, soft-delete `is_deleted` where applicable.

### Trading & Execution
- **trades** â€” symbol, direction, entry_price, decision_price, slippage_bps, initial_sl/current_sl/trailing_sl, sl_stage, target_price, quantity, quantity_remaining, strategy_id, signal_id, asset_class, uses_partial_exit, status, exit_price, gross_pnl, net_pnl, stt_tax, exchange_turnover_fee, brokerage, exit_reason, actual_rr, price_low/high_since_entry, mae_pct, mfe_pct, giveback_pct, market_state, mqi_level, vix_at_entry, sector, research_valid, entry_time, exit_time
- **trade_tranches** â€” trade_id (FK), tranche_number (1/2/3), quantity, target_price, target_rr, status, exit_price, gross_pnl, net_pnl, exit_time

### Signals & Intelligence
- **signals** â€” symbol, direction, strategy_id, setup_name, entry_price, sl_price, target_price, confidence, market_state, status (PENDINGâ€¦), system_mode
- **signal_intelligence** â€” signal_id, symbol, strategy_id, market_state, mqi_score, rvol_score, sector_breadth_score, vix_value, final_verdict (APPROVEâ€¦), forward_return_1d/5d/20d, forward_returns_computed

### AI Agents & Learning
- **agent_logs** â€” agent_name, signal_id, raw_verdict, confidence_given, key_reasons JSONB, concerns JSONB, latency_ms, prompt_tokens, completion_tokens, was_correct, actual_rr, called_at
- **agent_weight_log** â€” agent_name, old_weight, new_weight, weight_change, trigger_reason, accuracy_pct, trades_evaluated, recalibrated_at

### Pattern Memory
- **patterns** â€” setup_hash, strategy_id, market_state, timeframe, occurrences, wins, losses, win_rate_pct, laplace_win_rate_pct, expectancy, profit_factor, consecutive_losses, is_quarantined, last_occurred_at; UNIQUE(setup_hash, system_mode)

### Snapshots
- **daily_snapshots** â€” snapshot_date, peak_equity, current_equity, drawdown_pct, realized_pnl_today, unrealized_pnl, total/winning/losing trades today, kill_line_breached; UNIQUE(snapshot_date, system_mode)
- **intraday_snapshots** â€” snapshot_time, current_equity, drawdown_pct, open_positions_count
- **market_state_snapshots** â€” snapshot_time, market_state, vix_regime, mqi_score

### System & Health
- **scan_log** â€” symbols_scanned, signals_generated, signals_approved, scan_duration_ms, timeframe, asset_class, scanned_at
- **system_health_log** â€” oracle_cpu/ram/disk_pct, websocket_healthy, internet_ok, groq/gemini/supabase_latency_ms, logged_at
- **strategy_performance** â€” strategy_id, strategy_version, period, market_state, mqi_level, total_trades, wins, losses, win_rate, profit_factor, sharpe, max_drawdown_pct, calmar, avg_rr, net_pnl; UNIQUE(strategy_id, version, period, state, mqi, mode)
- **risk_events** â€” event_type, message, level, triggered_at
- **system_log** â€” event_type, message, level, created_at

### Future tables (from v4.1 spec, not yet built)
agent_disagreement_log, data_lineage_log, signal_correlation_log, liquidity_scores, backtest_cost_assumptions, corporate_actions_log (ex_date vs record_date), instrument_key universal standard

### Redis key patterns (upstash, from v1.1 spec)
- Live quotes, MQI state, cooldown state, pattern memory cache â€” TTL-based keys; (documented in spec; redis optional at runtime)

## 12. OPERATIONS, DEPLOYMENT & ENVIRONMENT

### 12.1 Runtime Schedule (IST, as registered by main.py)
| Time | Job |
|---|---|
| 08:25 | Daily state reset + Angel One re-auth |
| 08:30 | Morning macro & RRG sector briefing (MQI, VIX, global macro, FII/DII, Gift Nifty) |
| Every 1 min | Active trade trailing SL & MTM monitor (+ health telemetry) |
| Every 15 min | Multi-strategy scanner & AI debate |
| 15:35 | EOD performance scorecard (daily snapshot upsert, Telegram/Discord) |
| 16:00 | ML forward returns computation |
| 16:30 | Daily research report generation |
| Sunday 10:00 | Weekly Alphalens factor analytics |

### 12.2 Environment Layout
- Root `D:\MJONAI` â€” master repo; credentials/; docs consolidated into MJONAI_DOCS.md
- `mjonai-build\` â€” the single merged project (runtime + engine/)
- `mjonai-dashboard\` â€” FastAPI + Next.js (separate stack)
- `.venv` at root â€” Python 3.11.9, all deps
- Env files: `credentials\.env.master` (canonical, 71 vars) + `mjonai-build\.env` (17 vars, synced subset â€” same values)
- Credentials synced & verified (Angel, Telegram, Supabase, GROQ, Gemini, Shoonya all MATCH)

### 12.3 Oracle Cloud Deployment (Linux VM)
- Ubuntu 22.04/24.04; Python 3.11 via deadsnakes PPA; venv at /opt/MJONAI/.venv
- `scripts/setup_oracle_vm.sh` â€” apt updates, build-essential, ufw, python3.11-venv, pip install requirements, verify imports, install systemd unit
- `scripts/mjonai.service` â€” WorkingDirectory=/opt/MJONAI/mjonai-build, EnvironmentFile=/opt/MJONAI/credentials/.env.master, ExecStart=.venv/bin/python main.py, Restart=always
- Paths on server mirror the repo layout; SYSTEM_MODE=LIVE only after paper validation

### 12.4 Windows Dev
- `scripts/setup_windows.ps1` â€” venv, pip, env bootstrap
- VS Code with .venv interpreter; pytest on mjonai-build/tests
- Test suites: build 568 tests pass; engine/tests (research) in progress

### 12.5 Historical Deployment Notes (ArthAI era â€” for reference)
- System previously ran on Render.com cloud (laptop-off = zero impact); alerts via Telegram/Discord
- 15 API endpoints served; Supabase backend
- Production lessons: keep secrets only in env files, never in source; snapshot scripts redact values

### 12.6 Accounts & Services (names only â€” values in env files)
Angel One (SmartAPI), Telegram bot, Discord (channels + webhooks), Supabase (project wpxlzyyruazhaivyftsp), GROQ, Gemini, Upstash Redis, Timescale (planned), Ollama (local, planned), Render/Vercel (historical dashboard hosts), Shoonya (deferred), news/search APIs (NEWS_API_KEY, SERPAPI_KEY, TAVILY_API_KEY)

## 13. AUDIT, INVENTORY & TECH DEBT

### 13.1 Known Bugs & Problems
| ID | Sev | Status | Description |
|---|---|---|---|
| B1 | HIGH (quarantined) | Frozen | mjonai_intelligence/console.py bare imports fail as module â€” frozen, don't fix |
| B2 | MEDIUM | Fixed | grid_tester_v2.py DuckDB "system_log does not exist" â€” CREATE TABLE IF NOT EXISTS added |
| B3 | MEDIUM (unverified) | Open | main.py start_websocket([WATCHLIST_TOKENS]) may pass list-of-list â€” verify |
| B4 | LOW | Open | agents/bear.py exists, never imported (silently dead) â€” decision deferred |
| B5 | LOW | Open | ask.py referenced missing MJONAI_AGENT_PLAN.md â€” orphan (now archived with tools) |
| B6 | LEGACY (unverified) | Open | historical "60-second close bug" (P14/P36) â€” status unknown post-refactor |

### 13.2 Tech Debt Register
| ID | File | Debt | Status |
|---|---|---|---|
| TD-001 | strategy/signal_scanner.py (1,173 lines) | owns too many responsibilities | do NOT split yet |
| TD-002 | db/repository.py (1,519 lines) | god-object facade | do NOT split yet |
| TD-003 | execution/paper.py (1,308 lines) | fragile to edits | deferred |
| TD-004 | Test/ (10 duplicate backtests) | cleanup | archived â†’ Test_archive |
| TD-005 | research/ legacy (v1/v2) in build | fragmentation | archived â†’ research_archive |
| TD-006 | build/research analytics duplicate engine/analytics | overlap | merge decision pending |
| TD-007 | broker layers: data/angelone vs engine/execution/brokers | two layers | keep separate (different purpose) |

### 13.3 Known Cross-Cutting Gaps (as of merge)
- Dashboard backend: app.py imports 10 routes.* modules that don't exist yet â†’ backend can't boot
- Research results: runners print to console only; nothing persisted (DuckDB/exports dirs empty)
- Researchâ†’build promotion of validated params: no mechanism yet
- Dashboardâ†’build kill switch: docs require it, not implemented
- Frontend: localhost:8000 hardcoded, API key in source â†’ move to env
- Strategy params: build class-attrs vs research ParameterSet â€” no shared contract (deliberate, needs bridge doc)

### 13.4 Governance Rules Recap (see also Â§1)
- Read MJONAI_DOCS.md + ACTIVE_WORK_STATE at session start
- One concrete change per session; show before/after diffs
- Never create _v2/_new/_combined duplicates
- No new features without explicit ask; don't reopen settled decisions
- Frozen: mjonai_intelligence/, bear.py wiring, Shoonya, F&O/MCX/crypto, Kronos (until edges), Tier 2â€“4

## 14. PROJECT HISTORY & SESSION LOG

### 14.1 Lineage
ArthAI ("Arth" = meaning in Hindi + AI) â†’ MJONAI. Started as a personal wealth-intelligence system, consolidated across multiple earlier projects (mjonai_build, my_project_arthai, old_mjonai, new_mjonai, arthai_project â€” remnants visible in env.master comments). Master spec lineage: v3.0 â†’ v4.0 (project_plan1) â†’ v4.1 (project_plan2) â†’ v1.1 technical requirements (current living spec).

### 14.2 Session History
| Date | Session | What happened |
|---|---|---|
| 5 May 2026 | FIX-Aâ€¦FIX-L | Tier 1+2 fix sessions |
| 6 May 2026 | S16 | Research Lab v2, all 7 strategies live, forward-returns module, signal_direction support |
| 22â€“24 May | â€” | Governance docs created in docs/current_state (14 docs) |
| 23 May | â€” | Orchestration refactor â€” clean 5-file orchestration/ subsystem |
| 27 May | â€” | Kronos surfaced & evaluated â†’ parked |
| 28 May | Session A | Documentation cleanup: anchor docs created (01_DIRECTION etc.), Master/Handover archived |
| 19 Aug 2026 | (this cleanup) | Env verified (py 3.11.9, all deps), 568 tests pass, boot clean in RESEARCH mode, fixed behavioral_guard reset_guard NameError, archived Test/ + legacy research/, merged mjonai-research INTO mjonai-build, credentials synced & verified, consolidated all docs into this single file |

### 14.3 Current State (post-merge, 19 Aug 2026)
- Single project root: D:\MJONAI\mjonai-build (runtime + engine/)
- 568 build tests pass; engine/tests research suite being fixed (report.py fixed; test_analytics.py pending)
- Boot verified clean in RESEARCH mode (scheduler: 9 jobs)
- Docs: this single file replaces all prior md files (in progress â€” remaining files to mine: PROJECT_SNAPSHOT benchmarks, remaining current_state docs, orchestration README, ARCHIVE docs)
- Next: fix engine/tests (test_analytics.py TradeResult shape), fix research integration glue (paths, sys.path hack, CSVs), then regenerate snapshots

### 14.4 Remaining Docs to Mine (for the consolidation)
- PROJECT_SNAPSHOT.md â†’ benchmark alpha matrix + env example + subsystem deep-dive
- current_state: ANALYTICS_ARCHITECTURE, ANALYTICS_METRICS_CATALOG, GENERATION_STATUS, RESEARCH_ENGINE_IMPLEMENTATION_MAP, RESEARCH_ENGINE_V2, PROJECT_INVENTORY, PROJECT_QUERY_EXAMPLES, PROJECT_REALITY
- governance: IDEAS, QUESTIONS
- orchestration/README.md
- archive: MJONAI_MASTER_v2.0, MJONAI_HANDOVER_v2.0

## 15. BENCHMARKS & RESEARCH FINDINGS (from historical runs)

### 15.1 Master Cross-Sector Alpha Matrix (from PROJECT_SNAPSHOT.md â€” historical result)
Top findings by profit factor (win rate shown, trades, avg win/loss, max DD):
| Rank | Sector | Strategy | Trades | Win Rate | PF | Avg Win | Avg Loss | Max DD |
|---|---|---|---|---|---|---|---|---|
| 1 | NIFTY_AUTO | S02_MeanReversion | 31 | 61.3% | 2.43 | 6.32% | âˆ’4.12% | â€” |
| 2 | NIFTY_AUTO | S08_IntradayAllDay | 235 | 54.0% | 1.90 | 6.89% | âˆ’4.28% | â€” |
| 3 | NIFTY_AUTO | S03_TurtleBreakout | 401 | 53.6% | 1.82 | 6.53% | âˆ’4.15% | â€” |
| 4 | NIFTY_AUTO | S05_PriceAction | 381 | 52.2% | 1.74 | 6.49% | âˆ’4.08% | â€” |
| 5 | NIFTY_IT | S01_MomentumRSI | 134 | 54.5% | 1.61 | 5.84% | âˆ’4.36% | â€” |
| 6 | NIFTY_PHARMA | S05_PriceAction | 472 | 49.4% | 1.50 | 5.87% | âˆ’3.81% | â€” |
| 7 | NIFTY_AUTO | S01_MomentumRSI | 212 | 47.6% | 1.47 | 6.54% | âˆ’4.06% | â€” |

*(Full matrix continues beyond this excerpt; treat as historical reference, re-run via run_universe_benchmark.py for current numbers.)*

### 15.2 Insights from the Matrix
- NIFTY_AUTO dominated the top ranks (mean-reversion & intraday variants strongest there)
- S02_MeanReversion on Auto: highest PF (2.43) but few trades (31) â€” small sample, needs walk-forward
- S08_IntradayAllDay: high trade count (235) + PF 1.90 â€” candidate for deeper validation
- IT sector: S01 momentum strong (PF 1.61) â€” trend-following suits IT
- Pharma: price action best (PF 1.50) but win rate < 50% â€” driven by large winners
- **Discipline note:** these are historical numbers; validation requires the Â§8 discipline (IC, walk-forward, DSR) before any promotion.

### 15.3 Environment Setup Guide (from PROJECT_SNAPSHOT â€” sanitized)
- Python 3.11 venv at root; install root requirements.txt
- Frontend: Node 18+ / npm (dashboard only)
- Run research: python run_universe_benchmark.py / run_walk_forward.py (from mjonai-build after merge)
- Run runtime: python main.py (SYSTEM_MODE=RESEARCH for paper/sim)
- Run dashboard: uvicorn (backend) + npm run dev (frontend)

## 16. FINAL UNIQUE BITS (from remaining docs)

### 16.1 Analytics Metrics Catalog (owner map â€” the contract)
- Performance metrics â†’ analytics/performance_metrics.py (build) / engine/analytics (research)
- Capital metrics â†’ analytics/capital_metrics.py
- Strategy metrics â†’ analytics/strategy_metrics.py
- Market metrics (per market state / MQI level) â†’ analytics (planned/partial)
- Portfolio metrics (capital utilization, daily/weekly/monthly/yearly returns) â†’ analytics
- Rule: no metric computed by multiple modules; each metric has a single owner (contract from ANALYTICS_METRICS_CATALOG.md)

### 16.2 Project Intelligence Tooling (mjonai_intelligence/ â€” frozen)
- project_indexer, project_query_engine, knowledge_engine, impact_analyzer, refactor_advisor
- chunking_engine, confidence_engine, governance_loader, memory_store, metadata_enricher
- section_parser, subsystem_mapper, relationship_mapper, project_state_analyzer
- Purpose: query the codebase itself, analyze impact of changes, advise refactors
- Status: FROZEN (complete per governance) â€” do not modify; B1 known bug (console.py bare imports)

### 16.3 Ideas & Open Questions (from governance/IDEAS.md + QUESTIONS.md â€” recorded for future)
- (Placeholder â€” original files were scratch notes; capture any that survive the review, else drop)
- Open questions from the spec: data source reliability for FII/DII and NCDEX; options historical data vendor; dashboard route modules; research persistence

### 16.4 Live Dashboard API Surface (historical, 15 endpoints â€” for reference)
- signals, pre-market, market-mood, options, commodities, paper-trading, portfolio, performance, watchlist, ipo, mf, crypto, weekly-review, alerts-log, system-status
- (Current dashboard routes: /api/v1/* + legacy /api/*; frontend pages: dashboard, signals, market, options, paper-trading, performance, portfolio, assistant, watchlist, system)

### 16.5 Chronology of Key Spec Decisions (v4.0 â†’ v4.1 â†’ v1.1)
- v4.0: 8-layer framework, 5 agents, full asset coverage, tax engine, wealth lifecycle
- v4.1: Golden Rules formalized, coverage tracker, data-source fixes (Tiingo/NCDEX/FinBERT), DB additions, priority coding
- v1.1: current living technical requirements â€” 16 sections, Phase 0 foundation
- Post-merge: single project tree, single doc file (this), single env source (.env.master)

## 17. SYSTEM IDENTITY, MANDATE & RESEARCH LAB PHILOSOPHY

### 17.1 The Name
**MJONAI** = **M**J (**M**ani **J**anga) + **ON** (Always On, 24/7) + **AI** (Intelligence layer). Founder: Mani Sankar Reddy (MJ Reddy).

### 17.2 What MJONAI Is / Is Not
- **IS:** A personal financial OS and research platform â€” finds opportunities across asset classes, tests multiple strategies simultaneously, evaluates signals via AI agent debate, enforces institutional-grade risk rules, learns from every outcome, compounds wealth through proven strategies.
- **IS NOT:** Not a trading bot. Not a signal app. Not a prediction engine. Not a retail tool.

### 17.3 Core Mandate â€” NEVER CHANGE (hierarchy)
> **Capital Protection > Risk-Adjusted Growth > Profit**
- Personality: Conservative but Consistent. Target: **12â€“18% annual returns net of costs and taxes**.

### 17.4 The Research Lab Mandate (v2.0) â€” the fundamental insight
> Paper trading = **Research Laboratory**. Not practice. Not simulation.
> Goal: Discover genuine edges through systematic testing.
> Method: Run everything. Track everything. Analyze everything.
> Deploy only what the data proves works.

The wrong thinking (pre-Session 7): treating paper trading as practice for live. The right thinking: the paper/research phase IS the product â€” a controlled lab where every signal, agent call, and outcome is data. "Contamination boundary" concept: clean data starts at a defined timestamp (05 May 2026 19:02 IST) so research results aren't polluted by pre-cleanup behavior.

### 17.5 Master-v2.0 Session Rules (earlier, stricter edition of the anti-drift rules)
1. Read all files completely before responding
2. Confirm understanding by answering verification questions
3. Never introduce patterns not in these files
4. Never assume â€” ask before building
5. Never over-engineer
6. One file changed per session maximum
7. Discuss before writing a single line of code

### 17.6 Historical State (Session 16, 06 May 2026 â€” for reference)
- System Health ~99.5/100; Peak Equity â‚¹209,037; 8 closed trades (all research_valid=FALSE)
- Active strategies: 7 (S01â€“S07); SYSTEM_MODE RESEARCH
- Forward Returns ENABLED; Signal Direction ENABLED (LONG/SHORT)
- Scope: Personal use only. Future: Personal â†’ Family â†’ SaaS (if proven)

## 18. REPO, ENVIRONMENT & HONEST STATUS

### 18.1 Repository & Environment (historical, from Handover v3.0)
- GitHub: `https://github.com/manisankarreddyj/mjonai-build` â€” branch `master`
- Original dev setup: **Windows 11 + WSL2 Ubuntu 22.04 (mandatory)**, Python 3.11.15
- Venv was at `/mnt/d/mjonai_build/venv`; project at `/mnt/d/mjonai_build`
- Git credential fix: `git config --global credential.helper store`
- Oracle VM: code `29d6643` fully deployed, PID 98662, health ~99.5/100
- (Note: current machine is native Windows + PowerShell; WSL2 is the original/historical setup â€” relevant if you ever return to the Linux workflow)

### 18.2 The Big Audit (Handover v3.0)
- **Audit status: COMPLETE â€” 27 files audited, 477 bugs found, 58 fixed**
- Tier 1 fixes COMPLETE (FIX-A through FIX-G)
- Tier 2 fixes COMPLETE (FIX-H through FIX-L)
- Tier 3 fixes PARTIAL (FIX-M, FIX-O, FIX-T, FIX-Y applied)
- Research contamination boundary: 05 May 2026 19:02 IST

### 18.3 Honest Repo Status (from ARTHAI_CONTEXT.md â€” the "where we really stand" audit)
**Clearly built:**
- Platform & app shell (dashboard shell, auth, API)
- Core trading engine (scanning, signals, paper trading, risk)
- Risk & trading operations (devil checks, emergency triggers)
- Intelligence/assistant/integrations (Telegram/Discord, agents)
- Tax & reporting (FIFO, taxes)

**Partial, renamed, or architecturally drifted:**
- (Original doc lists specifics â€” most drift is the legacy-project consolidation remnants: v1/v2 research, duplicate analytics, env duplication â€” now addressed by this merge/consolidation)

**Clearly missing against the spec:**
- Dashboard route modules (backend can't boot)
- Research result persistence
- F&O/options advanced (IVR, GEX, 0DTE) â€” partial
- MCX/NCDEX data feeds
- Alternative data (Layer 7)

**Current blockers (from the audit):**
- Environment integrity (multiple venv/paths, WSL vs native)
- Project hygiene (duplicates, stale docs) â€” this cleanup
- Architecture clarity (research split, dashboard naming) â€” this merge

### 18.4 Session History 1â€“16 (from Handover â€” the pre-28-May record)
- S1â€“S6: foundation, env, broker connectivity
- S7 (01 May): master v1.5, paper-trading-as-lab insight
- S8â€“S15: Tier 1/2 fix sessions, hardening
- S16 (06 May): Research Lab v2, all 7 strategies live, forward returns + signal direction enabled
- Post-S16: 22â€“24 May governance docs; 23 May orchestration refactor; 27 May Kronos parked; 28 May Session A docs cleanup

## 19. AI & INTELLIGENCE LAYER, ROADMAP & KPIs

### 19.1 AI & Intelligence Layer (v1.1 Â§11)
- **Multi-agent debate room** is the core AI pattern (Bull/Bear/Economist/Devil/Supervisor) â€” Â§4
- LLM integration: GROQ (llama-3.3-70b-versatile), Gemini (gemini-2.5-flash), OpenAI-compatible fallback (deepseek-chat)
- **Deterministic-first:** all risk/logic gates are pure code; LLMs add reasoning only AFTER deterministic checks pass
- Rule-engine fallback: if LLMs fail/timeout â†’ deterministic consensus rules still produce a decision (never a hang)
- Agent call telemetry: latency, prompt/completion tokens, verdict accuracy, weight recalibration (agent_logs, agent_weight_log)

### 19.2 Answerable AI & Explainability (v1.1 Â§12)
- Every decision explainable through a conversational interface backed by a **knowledge graph**
- `knowledge/` module: principles library (Weinstein, Taleb, LÃ³pez de Prado, Douglas, Simons), retriever, explainability (plain-English trade rationale + post-mortem)
- `mjonai_intelligence/` (frozen): project query engine over the codebase itself
- The "answer every why" mandate: post-trade reflections (critic agent) + execution-quality classification

### 19.3 Implementation Roadmap (v1.1 Â§13 â€” high level)
- Phase 0 (current): Foundation & infrastructure â€” env, data layer, core runtime, research engine
- Phase 1: Indian equities proof-of-concept (target Sharpe > 1.0, max DD < 20%)
- Phase 2â€“9 (global expansion): US (NASDAQ/NYSE), Europe (LSE/XETRA), commodities, crypto (spot+futures), prediction markets (Polymarket, Kalshi) â€” each with explicit validation gates before go-live
- Every phase gated on the previous phase's evidence (edge survival first)

### 19.4 Success Metrics & KPIs (v1.1 Â§15)
| Objective | Target | Phase |
|---|---|---|
| Indian POC | Sharpe > 1.0, max DD < 20% | 2 |
| US equities | OOS Sharpe > 0.8 | 6 |
| European equities | OOS Sharpe > 0.8 | 7 |
| Crypto (spot + futures) | Validated strategies, controlled risk | 7 |
| Prediction markets | Edge identification + execution | 8 |
| Commodities | Validated trend/mean-reversion strategies | 7 |
- KPIs: win rate target 55â€“65% (per RenTech insight), IC > 0.05, WFE > 50%, agent accuracy tracking, drawdown discipline (kill line 15%)

### 19.5 Open Questions & Dependencies (v1.1 Â§14 â€” abbreviated)
- Data source reliability: FII/DII flows, NCDEX agri
- Options historical data vendor for backtesting
- Dashboard route implementation plan
- Research persistence design
- Live-trading authorization flow (dual-key, paperâ†’live transition criteria)

### 19.6 Regulatory & Ethical Constraints (v1.1 Â§4.3, Â§17)
- **SEBI compliance: personal use only until Research Analyst (RA) registration received** (Golden Rule)
- No advice to third parties pre-registration; family-money expansion only after registration
- Data licensing: only use feeds with authorized access (Angel scrip master, yfinance public, etc.)

## 20. FACTOR INVESTING, COMPLIANCE & THE VISION (from Master Spec v4.0 Â§12â€“22)

### 20.1 Opportunity Cost (v4.0 Â§12)
The concept the system must always remember: every rupee deployed in one trade is a rupee NOT available for a better opportunity. Position sizing and signal caps exist to preserve optionality, not just limit risk.

### 20.2 Factor Investing â€” The Academic Edge (v4.0 Â§13)
Beyond technical setups, factor exposure is a documented source of long-run return:
- **Value** (PE/PB/PEG/EV-EBITDA), **Size**, **Momentum** (12-1), **Quality** (ROE/ROCE, margins), **Low Volatility**, **Dividend Yield**
- Use factor scores as a Layer-5-style confirmation overlay, and for portfolio construction (factor-neutral vs factor-tilt decisions)
- (Research engine is the natural home for factor backtests â€” future work)

### 20.3 Macro Economic Cycles & Sector Rotation (v4.0 Â§14)
- Map sector strength to macro phase: early-cycle (financials, consumer discretionary) â†’ mid-cycle (tech, industrials) â†’ late-cycle (energy, materials) â†’ recession (defensives: staples, healthcare, utilities)
- RRG (relative rotation graphs) + sector breadth feed this â€” already in intelligence/sector_rotation.py
- Combine with FII/DII flows and VIX regime for the Economist agent's macro vote

### 20.4 Frontend & Backend Spec (v4.0 Â§15â€“16 â€” abbreviated)
- Frontend (dashboard): signals feed, market mood, options chain, paper trading, portfolio, performance, assistant chat, watchlist, system status â€” all live pages (current Next.js app)
- Backend: FastAPI, versioned API (/api/v1/* + legacy), auth via API key, WebSocket push, repository facade to Supabase
- Design goal: the dashboard is the control surface AND the observability surface (kill switch requirement)

### 20.5 SEBI / RBI / Regulatory Compliance (v4.0 Â§17)
- Personal-use only until RA registration; no third-party advice pre-registration
- Tax compliance: STT/CTT/stamp duty/GST/STCG/LTCG handled by tax engine (Â§7)
- Data compliance: only authorized feeds; no scraping of restricted sources
- (Full regulatory matrix in the original Â§17 â€” revisit when moving to live/family/SAAS)

### 20.6 Infrastructure & DevOps (v4.0 Â§18)
- Windows dev â†’ Oracle Cloud Ubuntu VM (systemd) â†’ (future) containerized stack
- Planned: Docker Compose (TimescaleDB, Postgres, Redis, Ollama) per the Phase-E roadmap; SQL schemas
- Monitoring: system_health_log, Telegram/Discord alerts, process lock, runtime guard, WS supervisor

### 20.7 Execution Plan â€” Phase by Phase (v4.0 Â§19, condensed)
Phase 0â€“14: foundation, trading core, risk, agents, research (built: >50%)
Phase 15â€“17: hardening (in progress at the time; now largely done)
Phase 18â€“25: expansion â€” new asset classes, wealth modules, family/SAAS
Each phase has P0/P1/P2/P3 priority-coded tasks (v4.1 added color-coding)

### 20.8 Competitor-Sourced Features (v4.0 Â§20)
- Study retail/institutional platforms' winning features (screening, alerts, watchlists, risk dashboards) and adopt only those aligned with the core mandate
- Never copy features that contradict "probability over prediction" or the risk-first hierarchy

### 20.9 Progress Tracking System (v4.0 Â§21)
- Coverage % tracker per asset class (Â§2 of the Golden Rules block â€” update monthly)
- Session log, bug registry, tech-debt register â€” all now consolidated in this doc + codebase
- "Everything tracked, everything analyzed" â€” the Research Lab mandate

### 20.10 The Vision (v4.0 Â§22 â€” the supreme picture)
> A globally recognized financial intelligence system: institutional-grade quantitative research + explainable AI, proving that disciplined process and continuous learning produce sustainable edge â€” without sacrificing transparency or control â€” across every liquid market in the world.
- Personal â†’ Family â†’ Business (SEBI-registered) â†’ SaaS (if proven)
- Global multi-asset: equities, fixed income, commodities, currencies, crypto, prediction markets, alternatives
- 24/7 self-learning: trades during market hours, researches/learns off-hours

## 21. RUNTIME TRUTHS & ORIGINAL-ARCHITECTURE CONTEXT

### 21.1 Verified-Healthy Checklist (from ARTHAI_CONTEXT audit, 20 Apr 2026 â€” the "what actually boots" proof)
- Python 3.11 at C:\Users\manis\AppData\Local\Programs\Python\Python311
- main.py imports + full startup chain verified (env, connections, data pipeline, technical analysis, AI brain, knowledge base, risk guard, market intelligence, signal engine, paper trading, alerts, personal assistant, strategy lab, scheduler, dashboard)
- Scheduler registered **16 jobs** (at that time)
- Dashboard health: GET /health â†’ HTTP 200
- pytest works after removing unused pytest-asyncio; test_technical_analysis 8 passed; test_signal_engine 8 passed
- Windows console logging hardened so Unicode logs don't crash on default code page
- Rejected-signal storage repaired to match Supabase schema
- DB-backed signal-history tests clean up their own TEST_* rows

### 21.2 The Original (ArthAI) Architecture â€” now renamed/reorganized
Earlier layout had: core/data_pipeline/, core/technical_analysis/, core/signal_engine/ (signal_manager.py), core/ai_brain/ (debate_room.py), core/options_engine/, core/risk_management/, top-level risk_management/, paper_trading/, special_modes/, scheduler/task_scheduler.py (APScheduler), market_intelligence/, knowledge_base/, strategy_lab/, personal_assistant/, psychology_guard/, dashboard/frontend/src, Sentry monitoring.
â†’ Current layout (mjonai-build + engine/) is the reorganized successor. Original names matter only for historical traceability.

### 21.3 Runtime Architecture (current â€” from RUNTIME_ARCHITECTURE.md)
- Entry: main.py â†’ orchestration/ (startup, scheduler, runtime_guard, health_monitor, websocket_supervisor) â†’ subsystems
- Config governance: runtime_config.py is the single tunables source; constants.py is the single constants source
- Scheduler responsibilities: pre-market, scans, monitor, EOD, research, weekly

### 21.4 Runtime Flow (current â€” from RUNTIME_FLOW.md)
- Layers: Market Intelligence â†’ Signal Intelligence â†’ AI Validation â†’ Execution â†’ Research Intelligence â†’ Communication
- Market open flow â†’ signal scanning flow (strategy layer) â†’ approval flow â†’ execution â†’ telemetry

### 21.5 Schema note (docs vs code divergence)
- SYSTEM_ALGORITHMS.md references **17 tables**; db/schema.sql defines **15** â€” the docs were written at a different schema generation. Code (schema.sql) is authoritative.

### 21.6 Research Engine V2 rationale (from RESEARCH_ENGINE_V2.md â€” why the engine exists)
- Fragmented research scripts, inconsistent assumptions, simplified execution models, weak portfolio simulation were the problems
- Research Engine V2 (now engine/) = standardized pipeline: one entry, consistent assumptions, realistic costs, portfolio-aware simulation

### 21.7 Project Reality (from PROJECT_REALITY.md â€” condensed)
- What MJONAI currently is: a research-first platform where the runtime, strategy/signal system, research/backtesting, AI-assisted validation, paper trading, intelligence logging, and communication layer all WORK (as of that writing)
- Current primary goal: research maturity / edge discovery

## 22. OPERATIONS RECORD, INVENTORY & OPEN QUESTIONS

### 22.1 Historical Ops Record (from ArthAI_Project_Summary.md â€” condensed)
- Phase 1 COMPLETE â€” Production Live (April 2026); system ran on Render.com (laptop-off = zero impact)
- Alerts: Telegram/Discord automatically
- Signal engine config + Nifty 50 daily scan list (09:20 AM) existed at that time
- All-accounts/credentials reference lived in that doc â†’ now in env files (values) + Â§12.6 (names)
- 15 API endpoints, Supabase backend, package list â€” historical reference only (current API surface in Â§16.4)

### 22.2 Project Inventory (from PROJECT_INVENTORY.md â€” the map of what exists)
- Core runtime: main.py, agents/, execution/, risk/, communication/, core/, db/
- Research: research/ + research_data.duckdb (legacy â€” now research_archive/)
- (Inventory is now superseded by the merged tree: mjonai-build + engine/)

### 22.3 Open Questions & Ideas (from governance IDEAS/QUESTIONS â€” recorded for future)
- Q-001: (see original) â€” capture any that survive review
- Standing open items (from across docs):
  - Dashboard route modules implementation
  - Research persistence design
  - FII/DII + NCDEX data source reliability
  - Options historical data vendor
  - Live-trading authorization flow
  - Kronos re-evaluation (after edges)

### 22.4 Coverage Confirmation (what this master doc now contains)
Sections 1â€“22: Identity & Working Rules; Golden Rules (Constitution); 8-Layer Evidence Framework; AI Agent Debate Room; Signal Engine & Strategy; Risk Management; Tax Engine; Backtesting & Validation; Data Strategy; Architecture & Stack; Database Schema; Operations/Deploy/Env; Audit & Tech Debt; History & Sessions; Benchmarks; Final Bits; Identity/Mandate/Research Lab; Repo/Env/Status; AI Layer/Answerable AI/Roadmap/KPIs; Factor Investing/Compliance/Vision; Runtime Truths & Original Architecture; Ops Record/Inventory/Open Questions.

**Everything framework-level and decision-level from all 29 original md files is now consolidated here. Implementation-level detail lives in the code itself.**

## 23. AUDIT FACTS, ADRs, SERVER OPS & WHAT REMAINS IN ARCHIVE

### 23.1 Audit Facts (00_AUDIT_FACTS.md, 27 May 2026 â€” forensic read of 117 files)
- **Project by numbers:** 117 files, 30,457 lines, 924 KB; 96 Python files; ~30 files reachable from main.py (live); ~50 NOT reachable (research, tests, intelligence, dead code)
- **What actually works (verified):** runtime spine real & connected â€” all 7 strategies wired into signal_scanner; orchestration clean (23 May); forward_returns runs daily 4PM from main.py; DuckDB 91 MB holds real research data; v2 grid tester ran 50 stocks Ã— ~2,000 trades
- **Supabase: 17 tables, Mumbai region** (note: docs said 17, schema.sql defines 15 â€” schema.sql is authoritative)
- **Orphan/dead-code table (from audit):** agents/bear.py (322 lines, never wired), research/sector_scanner.py, deep_analysis.py, exit_simulator.py, test_sector_filter.py, debug_nan.py, check_data.py, fix_and_analyze.py, install_research.py, quick_view.py, ask.py (35), ask_ai.py (58), research_log.txt
- **B7 (new, from audit):** WebSocket reconnect loop "partially fixed" â€” status unverified (added to bug table)
- **Test/ folder analysis:** 10 scripts written 7 May, all same stack (vectorbt, yfinance, pandas, talib, numpy); recommendation was keep backtest_all_7strategies.py, archive other 9
- **Runtime flow (as-audited):** startup â†’ AngelOne TOTP â†’ WS Nifty 500 â†’ Telegram listener â†’ scheduler (08:25 reset, 08:30 briefing, 09:30â€“15:15 scans every 15 min, 15:35 EOD, 16:00 forward returns, 16:30 report, Sun 10:00 Alphalens, 1-min monitor) â†’ per-scan: risk gate â†’ no-trade-day? â†’ daily limit? â†’ live prices? â†’ loop 499 symbols Ã— 7 strategies parallel â†’ devil_checks â†’ Bull â†’ Supervisor â†’ open_paper_trade; loop sleep 30s
- **Scan gates (the 4-check funnel):** Gate 1 risk engine allows â†’ Gate 2 not no-trade-day â†’ Gate 3 under daily limit â†’ Gate 4 live prices OK

### 23.2 Architecture Decision Records (ADR.md)
- **ADR-001 (Accepted, 03 July 2026):** MJONAI is an **Autonomous Financial Intelligence Operating System**, not a trading bot. Vision extends beyond trading: research, forecasting, portfolio intelligence, knowledge management, autonomous learning, financial decision support across asset classes.
- Rules: every decision gets unique ID; never deleted; changes recorded as new reasons, never overwrite history.

### 23.3 Canonical System State (CANONICAL_SYSTEM_STATE.md â€” ownership map)
- Entry: main.py | Orchestration: orchestration/ | Runtime config: core/runtime_config.py | Persistence: db/repository.py | Signal engine: strategy/signal_scanner.py | Execution: execution/paper.py | Risk: risk/ | Research: research/ (now engine/)
- Canonical strategies: S01â€“S07 (LONG + SHORT enabled)

### 23.4 Refactor Boundaries (stability ratings â€” what is SAFE to build on)
- Research persistence layer: stability HIGH (centralized data access, signal lifecycle, pattern memory, AI verdict persistence)
- Signal intelligence architecture: stability HIGH (layered filtering, multi-stage validation, strategy registry)
- (Implied: these two are the strongest systems â€” refactor elsewhere first)

### 23.5 Analytics Subsystem Scope (ANALYTICS_ARCHITECTURE.md)
- Purpose: evidence layer â€” "How is MJONAI actually performing?"
- Measures: trade/portfolio/strategy/market-regime/risk/agent performance; daily/weekly/monthly/overall summaries
- Does NOT: generate signals, execute, place orders, do research, modify decisions

### 23.6 Oracle Cloud Production Server (from OPERATIONS_PLAYBOOK â€” the actual box)
- Instance: **VM.Standard.E2.1.Micro** | 1 OCPU | 1 GB RAM | 48.27 GB storage
- **Public IP: 140.245.234.150** | Ubuntu 22.04.5 LTS
- Project path: /home/ubuntu/mjonai-build | venv: /home/ubuntu/mjonai-build/venv
- SSH: `ssh -i ~/.ssh/ssh-key-2026-04-27.key ubuntu@140.245.234.150` (key backed up in Bitwarden)
- systemd: `sudo systemctl start|stop|restart mjonai`
- GitHub repo (private): github.com/manisankarreddyj/mjonai-build, branch master

### 23.7 Orchestration Design Philosophy (orchestration/README.md)
- Orchestration is responsible for: startup sequencing, scheduler wiring, runtime monitoring, process lifecycle, health telemetry, graceful shutdown
- NOT responsible for: strategy, signals, market analysis, portfolio analytics, AI reasoning, research, execution decisions
- Philosophy: keep thin; business logic in domain modules; incremental validated extractions; avoid aggressive refactors; avoid circular dependencies

### 23.8 âš ï¸ Content that exists ONLY in the archived Master v2.0 (per archive README) â€” NOT yet extracted
- F&O Engine spec (Master Â§17) â€” Tier 2 work
- MCX Commodity spec (Master Â§18) â€” Tier 2+ work
- Validation Framework (Master Â§23) â€” paperâ†’live transition
- Psychology Guard spec (Master Â§24) â€” future feature
- Tax Engine detail (Master Â§25) â€” live trading prep
- Regulatory Position (Master Â§28) â€” compliance reference
- Coding Standards (Master Â§30)
- Capital Tier Activation thresholds (Master Â§33) â€” long-term roadmap
- 52-persona Board governance (Master Â§43) â€” aspirational
- Full Fix Session History (Handover Â§9) + all 16 session histories (Handover Â§21)

## 24. RISK ENGINE, EXIT LOGIC & CONFIDENCE (from MASTER v2.0 Â§9â€“12, 15â€“16)

### 24.1 Authority Hierarchy (NEVER CHANGE â€” the power order)
Risk Engine â†’ Constitutional law | Orchestrator â†’ Capital governor | Allocation Engine â†’ Capital distributor | AI Debate Room â†’ Advisory only | Signal Engine â†’ Opportunity finder | Execution Engine â†’ Order placer
**8 Golden Rules (MASTER edition):** 1) Capital protection over profit â€” always. 2) Never override SL. 3) Risk Engine cannot be overridden by AI or signal. 4) AI is advisory only â€” never authority. 5) Allocation decides IF trade happens â€” not signal. 6) System must survive worst-case scenarios. 7) No trade without execution feasibility check. 8) All P&L shown NET of costs and tax â€” never gross.

### 24.2 Risk Per Trade & Real Costs (v2.0 rates â€” note: slightly older than constants.py; constants.py is authoritative)
Risk: Intraday 1% | Swing 1.5% | Positional 2% of capital.
Position sizing formula: `PositionSize = Capital Ã— min(Risk%, Risk% Ã— Wc Ã— Wm)` â€” MIN ensures 2% ceiling never breached.
- Wc (confidence): 65â€“70â†’0.6 | 70â€“80â†’0.8 | 80â€“90â†’1.0 | 90+â†’1.2
- Wm (market): VIX>20â†’0.5 | normalâ†’1.0 | ADX>30â†’1.2
Max open positions: Tier1 3 | all tiers 6 | intraday 4 | swing 3 | positional 2. Growth pool max deploy 80%.
Sector cap: 25% growth pool/sector, max 2 stocks/sector.
Emergency triggers: RISK STOP (daily loss â‰¥3%, DD â‰¥15% kill line, margin â‰¥70%; recovery 24h/7d) | SOFT STOP (3 consecutive losses, VIX surge >15% in 1h, data lag >10s; auto-resume 60m) | HARD STOP manual-only (price mismatch >0.5% Angel vs yfinance, manual SL override, API error >5%/15min).
**KILL LINE vs LEVEL 3 (important distinction):** Kill Line = primary automated protection (trading failure). Level 3 = only if Kill Line fired BUT system FAILED to execute close (system integrity failure). Independent concepts.

### 24.3 Triple-Barrier Exit Logic
First barrier hit exits: SL | Target | Time.
| Timeframe | SL | Target | Time barrier |
|---|---|---|---|
| Intraday | 1% risk | RR â‰¥2.0 | 3:15 PM â€” no exceptions |
| Swing | 1.5% risk | 2â€“3R | 7 trading days |
| Positional | 2% risk | Structure + trailing | 40 trading days |
Trailing: at 1R â†’ SL to breakeven (entry+costs); at 2R â†’ SL to 1R level; after 2R â†’ trail by best of (15-min swing low/high | EMA21(15m) | price âˆ’ 1.5Ã—ATR14). **RATCHET RULE: SL only moves toward profit. Never backward. Ever.** VIX>22 â†’ add 0.5Ã—ATR to trailing distances. Options exits: Long SL at 50% premium loss, target 100â€“200%, exit 1 day before expiry; Short SL at 2Ã— premium, target 50% captured, exit 2 days before expiry.

### 24.4 Overnight Risk Protocol
AUTO-CLOSE (30â€“60 min before close): earnings/RBI/budget/election/FOMC/OPEC next day, expiry after 2PM. ALERT + size âˆ’25%: US CPI/NFP next day, state elections, VIX>22 sustained, short options within 3d of expiry. NORMAL CARRY: no events 24h, VIX<18, no earnings, margin<50%. Gap risk: ExpectedGap = historical overnight vol Ã— event multiplier Ã— VIX factor; if > SLÃ—1.5 â†’ auto close.

### 24.5 MQI 6-Factor (MASTER edition â€” slightly different from current mqi.py; code is authoritative)
1. ATR compression (ATR14 vs 20d avg) | 2. India VIX intraday change % | 3. Market breadth (% Nifty 500 above EMA50) | 4. Gap follow-through (did gap sustain 30 min after open) | 5. Event proximity (RBI/FOMC/Budget/Expiry) | 6. Opening volume (first 30 min vs 20d avg)
Gating: HIGHâ†’2 signals, MEDIUMâ†’1, LOWâ†’1 (MQ13 fix: was 0, now 1), VERY LOWâ†’NO-TRADE DAY (scanner disabled + Telegram).

### 24.6 Market State Engine (8:30 AM daily, factors +1/0/âˆ’1)
Price vs EMA200 (Â±1% â†’ 0) | Breadth >65% above EMA50 â†’ +1, <35% â†’ âˆ’1 | VIX <14â†’+1, 14â€“20â†’0, >20â†’âˆ’1 | FII flow T-1 (NSE publishes ~6â€“7 PM; labeled "FII Trend (T-1)"; net >â‚¹500Cr buy +1 / sell âˆ’1; intraday FII proxy = Nifty futures premium vs spot, >0.1% = bullish). Classification: score â‰¥+2 BULL, â‰¤âˆ’2 BEAR, else NEUTRAL. HIGH VOL OVERRIDE: VIX>25 overrides all.

### 24.7 Confidence Scoring (dual gate â€” BOTH must pass)
`Confidence = TechnicalÃ—0.30 + MTFÃ—0.25 + VolatilityÃ—0.20 + LiquidityÃ—0.15 + ContextÃ—0.10`
Gate 1 (per-component minimums): technical â‰¥60, MTF â‰¥75, volatility â‰¥50, liquidity â‰¥60, context â‰¥40 â€” fail any â†’ AUTO-REJECT. Gate 2: weighted total â‰¥65.
Component details: Technical = RSI dir +20, MACD cross +20, EMA aligned +20, Supertrend +20, candle +20 (min 3/5). MTF = 4/4 TF agree 100, 3/4 75, 2/4 40 REJECT. Volatility = ATR fits SL 100, 75% 75, 50% 50, ATR>SL REJECT; VIX adj <14 +10, 14â€“20 0, 20â€“25 âˆ’15, >25 âˆ’30. Liquidity = vol >2Ã—avg 100, 1.5â€“2Ã— 80, 1â€“1.5Ã— 60, <avg 20; spread <0.1% +20, 0.1â€“0.2% 0, 0.2â€“0.5% âˆ’20, >0.5% AUTO-REJECT. Context = FII match +40, sector aligned +30, no event 24h +30, major event âˆ’50, FII selling 3+ days âˆ’30.

## 25. F&O ENGINE, MCX ENGINE, VALIDATION, PSYCHOLOGY & TAX (MASTER v2.0)

### 25.1 F&O Engine (Tier 2+ â€” paper signals at Tier 1)
- Four-layer validation: Price action | Options flow (OI, PCR, sweeps) | IV environment | Portfolio Greeks
- **IV framework (both measures must agree):** IV Rank = (Current âˆ’ 52W Low)/(52W High âˆ’ 52W Low)Ã—100; IV Percentile = Days IV<Current/252Ã—100. Both <30 â†’ BUY strategies | 30â€“70 â†’ spreads only | >70 â†’ SELL premium
- **VIX override:** >25 â†’ block premium selling | >30 â†’ block all F&O
- **Greeks limits:** Net Delta max 3 Nifty lots | Net Vega max 5% portfolio per 1% IV | Net Gamma expiry max 2 lots
- **Expiry day:** 9:15â€“11:30 all allowed | 11:30â€“2:00 spreads only, âˆ’25% size | after 2:00 no new F&O | 3:15 PM force close all intraday options
- **0DTE:** confidence â‰¥85, IV Rank â‰¥40, size halved

### 25.2 MCX Commodity Engine (Tier 2+)
- Data: AngelOne SmartAPI primary | Shoonya manual failover
- Universe: Precious (Gold 1kg/Mini/Guinea/Petal, Silver 30kg/Mini/Micro, Platinum, Palladium) | Energy (Crude 100bbl/Mini, Natural Gas 1250/Mini) | Base metals (Copper, Zinc, Lead, Aluminium, Nickel, Brass, Steel Long + Minis) | Agri NCDEX (Castor, Turmeric, Jeera, Coriander, Chana, Soybean, Guar, Mentha, Cotton, CPO, Rubber)
- Three-layer signal: 1) Global anchor COMEX/NYMEX/LME via yfinance 2) Indian microstructure (MCX OI, volume, MCX-vs-international spread) 3) Technical (EMA, RSI directional, Supertrend)
- Gold-Silver ratio: >80 â†’ long Silver | <60 â†’ long Gold
- Blackouts: OPEC day no Crude | EIA Wednesday 8:30 PM IST no Crude intraday | RBI MPC day no commodities
- Limits: total commodities max 20% growth pool | single commodity max 10%

### 25.3 Validation Framework (paper â†’ real money â€” ALL criteria)
- 30 consecutive paper trading days | 50 closed paper trades | Win rate >65% on most recent 30 trades | 60%+ per asset class over 20+ trades independently | Max DD never >15% | Psychology score >70/100 avg last 30 days | Zero circuit breakers last 14 days | Founder explicit written confirmation (dated & signed)
- Transition ALWAYS human-initiated; system shows "Ready" indicator; never auto-switches

### 25.4 Psychology Guard (cannot be disabled by anyone)
Bias detection: Overconfidence (win streak>3 + size increase) | Revenge (trade within 30 min of loss) | FOMO (entry after price moved >0.3% beyond signal) | Anchoring (holding beyond max DD) | Disposition effect (sell winners early, hold losers past SL) | Recency (behavior change after market extreme) | Loss aversion (SL override/refusal to close) | Herding (trade without MJONAI signal)
Levels: Warning â†’ Alert (confirm to proceed) â†’ Block (violated Golden Rule). Psychology score 0â€“100 weekly (bias count + override attempts + SL discipline + time between loss and next trade). Cooling periods: Lossâ†’30 min | Circuit breakerâ†’24h | 5% DD dayâ†’48h.

### 25.5 Tax Engine (MASTER Â§25 â€” extends Â§7)
| Instrument | STCG | LTCG | Threshold |
|---|---|---|---|
| Listed Equity | 20% | 12.5% above â‚¹1.25L | 12 months |
| Equity MF | 20% | 12.5% above â‚¹1.25L | 12 months |
| Debt MF | Slab | Slab | 24 months |
| F&O | Business income slab | N/A | Always |
| Intraday | Speculative slab | N/A | Always |
| Crypto/VDA | 30% + 1% TDS on sell | 30% | No LT benefit |
| SGB (maturity) | Tax FREE | Tax FREE | Hold to RBI maturity |
- FIFO lots; alert at 11 months "wait 30 days â†’ LTCG saves â‚¹X"; track â‚¹1.25L exemption
- Advance tax: Jun 15 15% | Sep 15 45% | Dec 15 75% | Mar 15 100%
- Tax-loss harvesting alert before March 31

## 26. REGULATORY, OVERRIDE, CODING STANDARDS, CAPITAL TIERS & BOARD

### 26.1 Regulatory Position (MASTER Â§28)
- Personal use only. No subscriptions, signal sharing, or public advisory.
- SEBI algo: **Tier 1 = signals only, MJ places orders manually** (no broker API order placement). Before API order placement (Tier 2+): consult SEBI/legal advisor.
- FEMA/RBI: INR pairs only (USD/INR, EUR/INR, GBP/INR, JPY/INR); no offshore leveraged forex; US stocks LRS limit $250k/yr.
- Crypto: compliant Indian exchanges only; 30% + 1% TDS; no loss set-off.
- Polymarket: Tier 3 only after legal review (alt: Metaculus API).
- DPDP 2023: all data in India (Supabase Mumbai); no third-party sharing; full deletion on request.

### 26.2 Manual Override Policy
- CAN override (automatic penalty): rejected signal, position size, time barrier, exit decision
- CANNOT override (ever): 15% kill line, margin emergency, data quarantine, psychology Level-3 block
- Penalty (auto, unwaivable): position size âˆ’50% for that trade, daily signal limit âˆ’1, psychology âˆ’5 points, permanently logged
- 2 overrides in 24h â†’ Soft Stop 24h (no signals regardless of MQI). After 20 override trades: if override win rate <50% â†’ max override size permanently âˆ’25%.

### 26.3 Coding Standards (MASTER Â§30 â€” the project's own engineering law)
ALWAYS: type hints everywhere | Pydantic v2 for data shapes crossing module boundaries | docstring on every function | try/except on every external API call | structured JSON logging (not print) | return structured response objects | one responsibility per file | max one new file per session | never modify >2 existing files in one session.
NEVER: hard-code secrets | commit .env | import from higher authority level | add business logic to repository.py | circular imports | print() in production | trust external data unvalidated.
File header template (Module/Purpose/Depends on/Used by/Last modified). Git commits: [feat]/[fix]/[upgrade]/[docs]. Testing before close: uvicorn no errors + 3 plain-English test scenarios + all pass.

### 26.4 Feature Tier Classification (MASTER Â§31 â€” future feature roadmap)
- **Tier A (Phase 1â€“2):** OFI, India Fear & Greed Index, Earnings Audio Analyzer (Whisper), Gov Contract Tracker, SEBI Enforcement Tracker, MCA Intelligence, Toxic Flow Detector, Decision Transparency Report, Calibration Engine, GTT Pre-Placer, Weighted Options Sentiment, FII Category Analyzer, India VIX Term Structure, Central Bank NLP, Earnings Surprise Predictor
- **Tier B (Phase 2â€“3):** VPIN, Volatility Targeting, Risk Parity, Tail Risk Hedge (OTM puts), Market Knowledge Graph, LLM Consensus Scorer, Causal Inference (DoWhy), Correlation Regime Switcher, CVaR, Real Yield Tracker, Global Liquidity Monitor, Governance Scorecard, Hurst Exponent, Supplier-Customer Mapper, Insider Network Analyzer, Narrative Economics, Disposition Tracker
- **Tier C (Phase 3â€“4):** Satellite Intelligence, Multi-Agent Simulation (Mesa), Federated Learning, RL Position Sizer, Hawkes Process, PCA Regime Detection, Reflexivity Detector, Cross-Sectional Momentum, Patent Citation Network, Quantum Portfolio Optimizer

### 26.5 Return Expectations (MASTER Â§32 â€” the honesty benchmark)
Benchmark: Nifty 50 index fund â‰ˆ1%/mo (12%/yr), zero effort. MJONAI must beat it consistently.
| Level | Monthly | Annual | Meaning |
|---|---|---|---|
| Underperforming | <1% | <12% | Stop real money, return to paper |
| Acceptable | 1.0â€“1.5% | 12â€“18% | Working; don't scale yet |
| Good | 1.5â€“2.0% | 18â€“24% | Top-tier retail; plan Tier 2 |
| Exceptional | 2.0â€“3.0% | 24â€“36% | Verify over 6+ months |
| Fantasy | >3.0% | >36% | Check for errors; 12+ months validation |
Rules: no living expenses from MJONAI income in T1/T2; every rupee = bonus; Tier 1 goal = proof of concept; 14â€“16% sustained annual = genuinely excellent; most active managers don't beat 14% net.

### 26.6 Capital Tier Activation (MASTER Â§33 â€” the rollout ladder)
**Principle: architecture never changes; what changes = which engines are ACTIVE / PAPER-ONLY / DISABLED by capital.**
- **Tier 1 (under â‚¹2L â€” current):** ACTIVE: equity swing+positional (Nifty 200), Bull+Supervisor, 8 devil checks, risk engine, paper mode, Telegram, pattern memory (write-only), psychology guard. PAPER-ONLY: F&O options buying, Gold/Crude Mini MCX, equity intraday. DISABLED: F&O selling, iron condor/butterfly, Silver/Copper MCX, covered calls, CSP, income engine, 5-agent debate, knowledge RAG, stability pillar, crypto. Allocation 80/10/10 (equity/emergency/opportunity). Real-money rules: max risk â‚¹1,000/trade, 3 positions, 2 signals/day, swing+positional only, manual AngelOne orders. **Unlock Tier 2:** 60 paper days, 30+ real trades, win rate >60% (last 30), DD <8%, zero breakers 30d, Sharpe >1.0, capital â‚¹2L.
- **Tier 2 (â‚¹2â€“10L):** 4-agent debate (+Bear+Economist), F&O buying (>85% conviction, 1â€“2 lots), Gold+Crude Mini MCX, FinBERT, IV Rank filter, options flow, selective intraday, pattern read+write, 3 signals/day. Allocation 60/20/20. Target 1.5â€“2.5%/mo.
- **Tier 3 (â‚¹10â€“25L):** 5-agent debate (+Devil), F&O selling (Greeks limits), spreads, index futures (1 lot), iron condor (IVR>70), Silver Mini, covered calls, full knowledge RAG, full IV framework, Greeks monitoring, expiry protocol, 4 signals/day, stability pillar, Polymarket (post-review). Allocation 50/30/20.
- **Tier 4 (â‚¹25L+):** full income engine, CSP, iron butterfly, full MCX+NCDEX agri, crypto sandbox (5% spot only), REITs/InvITs, gold 5% SGB, tail risk hedge, vol targeting, advanced alt data, agent recalibration, family system, SaaS prep. Full 3-pillar model.
- Timeline: T1â†’2: 12â€“18 mo | T2â†’3: 24â€“36 mo | T3â†’4: 36â€“60 mo | full system: 5â€“7 yr. Capital growth reality: profits alone insufficient; savings injection required to reach next tier.
- **EXIT CONDITIONS â€” Level 1 (stop real money, return to paper):** win rate <50% for 30+ trades, OR Sharpe <0.5 for 60+ days, OR underperforms Nifty TRI by >5% over 6 months, OR 5+ consecutive losses twice in a month. **Level 2 (strategy pivot):** 3 consecutive Level-1 months + no improvement + win rate <52%/90d + portfolio lost >15% â†’ pause 30+ days, audit, 30 days paper after fix. **Level 3 (system integrity failure ONLY):** kill line fired AND system failed to close â†’ manual liquidation, 30-day pause, full audit of risk engine. **Philosophical exit:** if after 12 honest months can't beat Nifty 50 TRI net across regimes â†’ index fund wins. Most professional active managers fail to beat 14% net.

### 26.7 The Board & Governance (MASTER Â§43)
- Every session starts: "Board assembled. All tiers active. Read all files completely before responding. Today is [date]. Continue from [priority]."
- Tier invocation by decision type: simple fix â†’ T1 | strategy â†’ T1+2 | India market â†’ T1+2+3 | global macro â†’ +4 | compliance â†’ +5 | major architecture â†’ all | **Founder veto overrides all votes always** (MJ Reddy).
- Tier 1 Operating Committee (every session): CEO (no scope creep), CTO (architecture compliance), CFO (capital rules/cost/tax), Developer (one change at a time), QA/Tester, Analyst, PM/Manager, Security, SysAdmin (Oracle/deploy), Risk Officer.
- (Tiers 2â€“5: strategy/science/compliance/vision boards â€” exist in the original Â§43; capture when needed.)

## 27. STRATEGY REGISTRY v2.0, RESEARCH AGENDA & v2.0 FEATURES

### 27.1 Strategy Registry v2.0 (the 7 active strategies â€” full spec)
Base contract: `generate_signal(df, symbol, vix, market_state, mqi_level) -> dict | None`; signal must contain strategy_id, symbol, signal_type, technical_score, confidence, reasons, timeframe. Also `get_parameters()` (MLflow) + `get_description()`.

| ID | Name | Type | Logic | Status |
|---|---|---|---|---|
| S01 | MomentumRSI | Swing 3â€“10d | RSI 55â€“70 + EMA 20/50/200 + MACD 12/26/9 + Supertrend(3) + Candle | ACTIVE |
| S02 | MeanReversion | Swing 3â€“7d | RSI<30 + BB lower (2SD) + volume spike + above EMA200 | ACTIVE |
| S03 | TurtleBreakout | Positional 2â€“8w | 20d-high breakout + vol>1.5x + SL=10d low + ATR trail | ACTIVE |
| S04 | BollingerSqueeze | Swing 3â€“10d | BB width<75% avg â†’ expansion + MACD/RSI confirm | ACTIVE |
| S05 | PriceActionCandles | Swing 2â€“7d | 37 bullish TA-Lib patterns + EMA50 + vol>1.2x | ACTIVE |
| S06 | MomentumShort | Swing 3â€“10d | RSI 30â€“45 bearish + MACD bearish + EMA down + Supertrend bear + Evening/Shooting Star | ACTIVE NEW |
| S07 | MeanReversionShort | Swing 3â€“7d | RSI>70 + above BB upper + vol spike + below EMA200 | ACTIVE NEW |

Per-strategy targets & research Qs: S01 win>55% (best BULL+HIGH; worst BEAR/HIGH VIX) | S02 win>50% (oversold in BULL) | S03 win>40%, RR>3.0 (does Turtle work in NSE?) | S04 win>55% (low VIX + catalyst) | S05 win>50% (which of 37 patterns work in NSE large caps?) | S06 win>50% (does bearish momentum mirror bullish?) | S07 win>50% (mean reversion from overbought?).

**Strategy lifecycle:** BIRTH (write â†’ paper 30+ days â†’ min 30 trades) â†’ EVALUATION (100 trades: >55% + Sharpe>0.8 PROMISING, 45â€“55% INVESTIGATE, <45% REVIEW) â†’ GRADUATION (200+ trades: >55% + Sharpe>1.0 + DD<15% + works 2/3 regimes â†’ LIVE) â†’ RETIREMENT (<40% after 100 trades, no regime explanation â†’ ARCHIVED, not deleted) â†’ EVOLUTION (edge exists, wrong params â†’ fork + new version + re-paper).
**Adding a strategy (the 6-step ceremony):** 1) write hypothesis "I believe [signal] predicts [outcome] in [regime] because [reason]" 2) file inheriting BaseStrategy 3) register in registry 4) paper 30+ days/30+ trades 5) Alphalens IC>0.05 = genuine edge 6) Board review: graduate/retire/iterate.
Per-trade performance log shape (strategy_id, version, symbol, dates, holding_days, market_state, mqi_level, vix, confidence, sl_method, bull_verdict, devil_checks, outcome, actual_rr, gross/net_pnl, time_of_day, day_of_week, sector, signal_direction).

### 27.2 Research Agenda â€” 20 Categories (the "what to test next" roadmap)
**Cat 1 â€” Technical indicators:** currently using RSI(14), MACD(12,26,9), EMA(20,50,200), Supertrend(simplified), Hammer+Engulfing. Research Qs: does RSI 55â€“70 predict returns in NSE? which MACD params work in Indian large caps? do Fibonacci EMAs (9,21,55,89) beat standard? does HMA reduce lag? TO TEST â€” momentum: RSI 7/9/14/21, Stoch RSI, Williams %R, ROC 10/20, Awesome Osc. trend: EMA cross 9/21,20/50,50/200, HMA, ADX>25, Ichimoku, Parabolic SAR. volatility: BB width/squeeze/%B, Keltner, Donchian 20/55, ATR sizing, HV Rank. volume: OBV divergence, CMF, MFI, Force Index, Volume ROC. **KEY Q: which indicator combination has highest IC in Indian large caps?**
**Cat 2 â€” Candlestick patterns:** currently using only Hammer + Engulfing (2 of 61 TA-Lib patterns). Single: Doji, Dragonfly/Gravestone Doji, Spinning Top, Marubozu, Hammer, Inverted Hammer, Hanging Man, Shooting Star. Two: Bullish/Bearish Engulfing, Piercing, Dark Cloud, Harami, Tweezer. Three: Morning Star (strongest bullish), Evening Star (strongest bearish), Three White Soldiers, Three Black Crows, Three Inside Up/Down, Abandoned Baby.
(Cats 3â€“20 in original Â§38: momentum variants, mean reversion, volatility, volume, market structure, options, macro, event-driven, sector rotation, etc. â€” full list lives in the archived MASTER Â§38; capture when the research phase reaches them.)
**KEY INSIGHT:** research maturity = run the agenda systematically, compute IC per (indicator, params, direction), keep only what survives (IC>0.05, walk-forward, DSR).

### 27.3 v2.0 Runtime Features (Session 16 additions)
- **Signal direction:** signal dict now has signal_direction LONG/SHORT + signal_type BUY/SELL; SHORT = sell at market (paper only), SL above entry, target below, P&L = (entryâˆ’exit)Ã—qty.
- **Forward returns + Alphalens:** research/forward_returns.py; 4 PM daily compute, 4:30 PM report, Sunday 10 AM Alphalens IC. Windows [1,3,5,10,20]. IC thresholds: >0.05 genuine edge, >0.10 strong (rare), <0.02 noise â†’ retire.
- **Scan overlap lock:** _scan_running flag prevents concurrent scans (skips if one running).
- **Paper size:** fixed â‚¹10,000/trade in RESEARCH; confidence mins RESEARCH 50 / LIVE 65.

## 28. THE NORTH STAR & THREE-PILLAR CAPITAL MODEL

### 28.1 The North Star (MASTER Â§3 â€” THE goal, everything serves this)
> FIND 3â€“5 GENUINE EDGES IN INDIAN MARKETS.
An edge is: 1) wins more than it loses 2) wins in MULTIPLE regimes (not just bull) 3) wins AFTER all costs and taxes 4) EXPLAINABLE (we know why) 5) ROBUST (param changes don't kill it) 6) SCALES with capital.
3 proven edges = MJONAI is complete. Everything else = supporting infrastructure.
Jim Simons lesson: tested thousands of signals, most failed, a few worked consistently, compounded over decades = greatest fund in history. We are NOT building a thousand signals; we are systematically finding 3â€“5.
Timeline: Month 1â€“2 generate data (500+ trades) â†’ Month 3 first Alphalens (IC per signal) â†’ Month 4 iterate â†’ Month 5â€“6 statistical confidence â†’ Month 7+ graduate to live. No shortcuts. The data tells us what works.

### 28.2 Three-Pillar Capital Model (MASTER Â§8)
- **Pillar 1 â€” GROWTH (50% base):** Equity (Tier 1), F&O (Tier 2+), MCX (Tier 2+), Crypto (Tier 4). Regime adjustments: Bull +10% (max 70%) | Bear âˆ’15% (min 30%) | High Vol âˆ’20% (min 30%).
- **Pillar 2 â€” STABILITY (30% base, Tier 3+ only):** 65% passive core (AAA bonds, liquid funds, T-bills) | 30% tactical duration | 5% permanent gold (SGB primary, Gold ETF secondary).
- **Pillar 3 â€” INCOME (remaining, Tier 3+ only):** target 12â€“15% annual yield. 40% dividend engine | 25% covered call | 20% CSP | 15% bond/REIT yield.
- **Tier 1 allocation:** 80% equity swing/positional | 10% emergency reserve (never touch) | 10% opportunity reserve (90%+ confidence only).
- **Crypto sandbox (Tier 4 only):** max 5% total capital, spot only, no leverage, 30% flat tax.
- **Gold rule:** 5% of total portfolio permanently in gold (SGB â†’ Gold ETF â†’ MCX Gold), separate from MCX tactical.
- **Hard limits:** Growth 30â€“70% | Stability 20â€“50% | Cash 10% minimum floor â€” never breach.
- **Regime conflict:** priority High Vol > Bear > Bull â€” always apply most conservative adjustment.

## 29. AI DEBATE ROOM v2.0 & SIGNAL LIFECYCLE

### 29.1 Architectural Separation (critical design rule)
- `risk/devil_checks.py` = deterministic Python code, part of Risk Engine, runs BEFORE any LLM, binary pass/fail, cannot hallucinate.
- `agents/` = LLM agents, advisory only, NEVER make hard decisions. All pass â†’ LLM agents; any fail â†’ VETOED. LLM explains why, LLM does NOT decide the veto.
- The 8 devil checks (pseudocode from spec): gap risk (overnight > 1.5Ã— SL) | liquidity (spread > 0.5%) | data quality (<85) | pattern memory (â‰¥3 fails in 90d) | correlation (>0.80 vs open pos) | real RR (â‰¥2.0 after costs) | portfolio limits (max positions, growth pool â‰¥80%) | event risk (high-impact within 4h).

### 29.2 The 5 Agents (v2.0 detail â€” models, fallbacks, hard rules)
- **Bull (Tier 1 ACTIVE):** llama-3.3-70b-versatile, fallback llama-3.1-8b-instant. Output verdict STRONG_BUY/BUY/NEUTRAL/SELL + confidence + key_reasons + regime_note + pattern_history.
- **Bear (Tier 2):** Gemini 2.5 Flash + FinBERT, fallback Cohere. Hard rules: promoter pledge >70% â†’ BEARISH flag; CFO/MD insider buy <30 days â†’ +20 bullish. Output BEARISH/CAUTION/NEUTRAL/BULLISH + red_flags + insider_activity.
- **Economist (Tier 2):** RSS + RBI DBIE + FRED API + DuckDuckGo, fallback cached (max 1h stale). Hard rules: MPC within 2 days â†’ âˆ’20% confidence; FOMC within 2 days â†’ âˆ’10%; RBI VRR 5+ days â†’ bullish liquidity. Output macro_regime (BULL_CYCLE/LATE_CYCLE/BEAR_CYCLE/RECOVERY).
- **Devil LLM (Tier 3, explanation only):** CANNOT veto. Identifies contradictions, adjusts confidence max âˆ’15 if risk score >80. Output risk_score + contradictions + stress_points + confidence_adjustment + explanation.
- **Supervisor (Tier 1 ACTIVE):** models/gemini-2.5-flash, fallback llama-3.3-70b. Decision rules CODE-ENFORCED (not LLM): any devil check failed â†’ REJECT; Tier 3+ 4/4 agree STRONG BUY, 3/4 BUY, 2-2 split wait 15min re-debate then REJECT; confidence <65 REJECT; real RR <2.0 REJECT; Tier 1 Bull NEUTRAL/SELL â†’ REJECT.
- **Transparency Report (replaces SHAP â€” incompatible with LLMs):** approved, verdict, final_confidence, position_size_factor, top_reasons, deciding_factor, rejection_reason, devil_checks_passed/failed, signal_summary.
- **Groq rate limits:** 30 req/min, 14,400 tokens/min. Tier 1 = 2 calls/signal (Bull+Supervisor). Fallback: 3 consecutive failures in 5 min â†’ switch to Ollama, Wc capped 0.8, Telegram alert.
- **Agent recalibration:** every 50 trades OR 30 days (whichever first); weight range 0.6â€“1.6; all changes logged to agent_weight_log.

### 29.3 Signal Lifecycle (MASTER Â§14)
- Daily limits: Tier 1 = 2 signals | all tiers = 4. Upgrade 2â†’4 when win rate >60% for 30+ days, zero breakers 14 days, max DD <8%. Rejected signals: unlimited, all logged + feed Pattern Memory.
- Pipeline: 1) MQI check (Very Low â†’ No-Trade) 2) scan every 15 min (9:30â€“3:15 weekdays) 3) pre-filter (technical min 3/5, liquidity, time-of-day) 4) devil checks 5) confidence scoring 6) agent debate 7) priority queue (rank confidence Ã— real_RR if over limit) 8) approved â†’ Telegram+Discord+Dashboard+logged 9) **staleness: 100%â†’95% (5min)â†’85% (10min)â†’70% (15min)â†’EXPIRED (20min)** 10) price moves >0.3% from entry â†’ immediate expiry.
- **Time-of-day filter:** 9:15â€“9:30 EXCLUDED (opening noise) | 9:30â€“10:30 HIGH (best) | 10:30â€“12:00 MEDIUM-HIGH | 12:00â€“2:00 MEDIUM | 2:00â€“3:00 HIGH (pre-close institutional) | 3:00â€“3:15 EXCLUDED | after 3:15 NONE (close intraday only).
- Confirmation: paper = automated; live = manual within 15 min (no action = expired), order placed in AngelOne app not API (Tier 1).

## 30. DATA ARCHITECTURE, KNOWLEDGE ENGINE, REPORTING & INFRASTRUCTURE

### 30.1 Data Sources (MASTER Â§19)
- **AngelOne (primary):** NSE/BSE equity+F&O, MCX, currency. SmartWebSocket v2, Historical API (2yr), Options Chain, GTT, Margin, Portfolio. Cost â‚¹0.
- **Shoonya (manual failover ONLY):** TOTP 2FA cannot be safely automated. AngelOne fails â†’ Telegram alert â†’ MJ logs in manually â†’ reconnect. Gap: yfinance 15-min delayed data; no new signals during outage.
- **yfinance:** S&P500, NASDAQ, DJI, DXY, Gold, Brent, Asian/European indices. Free, no key.
- **FRED API:** US rates, Treasury yields, CPI, employment. Free key at fred.stlouisfed.org.
- **News RSS (free, no auth):** ET, Moneycontrol, LiveMint, Business Standard, Reuters India, NDTV Profit, Bloomberg India.
- **Regulatory (scrapers):** SEBI, NSE, BSE circulars, RBI press releases, MCA filings, NCLT, CCI.
- **FII/DII:** T-1 only (NSE publishes ~6â€“7 PM), labeled "FII Trend (T-1)"; intraday proxy = Nifty futures premium (labeled as proxy).
- **Polymarket:** defer Tier 3 (FEMA ambiguous); alternative Metaculus API.
- **Government data (free):** EPFO, VAHAN, DGCA, GST e-way, IMD monsoon, RBI DBIE, Coal India.
- **Data Quality Watchdog:** heartbeat ping 1.1.1.1 every 10s; price conflict Angel vs yfinance >0.5% â†’ quarantine; ghost candle (price >1% move + volume=0) â†’ bad-data flag; spike (1-min candle >3% without news) â†’ anomaly flag; quarantine lift when both sources within 0.1% for 5 consecutive minutes.

### 30.2 Knowledge Engine (MASTER Â§20 â€” structure Tier 2, active Tier 3)
- Stack: ChromaDB (local) | sentence-transformers (local) | PyMuPDF | BeautifulSoup + Scrapy | feedparser | PRAW | Ollama (summarization, on-demand)
- Books library: Trading (Murphy, Nison, Schwager Market Wizards, Lefevre, Douglas, Natenberg) | Quant (LÃ³pez de Prado, Chan, Aronson) | Value (Graham, Lynch, Cunningham)
- Purpose: RAG/memory support for the Answerable-AI layer (knowledge graph, retrieval)

### 30.3 Reporting (MASTER Â§26)
- **Performance X-ray:** per-pillar P&L | per-strategy | per-regime | per-agent accuracy | per-time-of-day | per-day-of-week | signal funnel | missed-signal cost | ghost-signal analysis.
- Primary metrics: Net P&L + tax-adjusted CAGR. Secondary: gross P&L + nominal CAGR. **Benchmark: Nifty 50 TRI always shown.**
- Metrics: win rate, PF, Sharpe, Sortino, Calmar, Max DD, recovery factor, avg win:loss, expectancy, max consecutive losses.
- **India Fear & Greed Index (custom):** VIX 25% | Nifty momentum vs 125-day avg 25% | PCR trend 20% | Gold vs equity 15% | Nifty500 breadth 15%. Score 0â€“100, daily dashboard + Telegram morning briefing.

### 30.4 Infrastructure (MASTER Â§27)
- Connectivity: primary WiFi, backup mobile hotspot (pre-configured WSL2); heartbeat ping 1.1.1.1 every 10s; disconnect â†’ pause signals + Telegram; reconnect â†’ hard sync AngelOne vs Supabase.
- **GitHub Actions overnight jobs:** daily_data.yml (6 AM) | regulatory_monitor.yml (7 AM) | weekly_cleanup.yml (Sun 2 AM) | weekly_performance.yml (Sun 10 AM).
- **Backup 3-2-1:** Supabase cloud (real-time, Mumbai) + local WSL2 (periodic export) + GitHub (code) + Google Drive (weekly CSV).
- **Phoenix recovery (<15 min, any machine):** clone repo â†’ install Python 3.11 + WSL2 â†’ pip install â†’ copy .env from Bitwarden â†’ python main.py (pulls state from Supabase) â†’ operational, no data loss.
- **Daily startup (8:45 AM) checklist:** WSL2 terminal â†’ ping â†’ AngelOne token verify/re-login â†’ Angel vs yfinance diff >0.5% = NO-GO â†’ Supabase vs Angel holdings diff >1% = NO-GO â†’ capital/margin check â†’ calendar check â†’ Shoonya manual check â†’ APIs responding. GO â†’ Telegram "MJONAI LIVE â€” {Date}. Regime: {STATE}. MQI: {LEVEL}." Fail â†’ NO-GO, no signals.
- **Execution modes:** 1) paper automated 2) semi-manual live (MJ places order in app) 3) full-auto DISABLED until SEBI review.
- **Kill switch:** always on dashboard, one click â†’ cancel orders, close positions, disable signals, log, Telegram alert.

## 31. RESEARCH AGENDA (CATS 3â€“20), DATA QUESTIONS, WORKFLOW & CHANGELOG

### 31.1 Category 3 â€” Chart Patterns
Reversal: H&S / inverse H&S, double/triple top-bottom, rounding bottom. Continuation: bull/bear flag, bull/bear pennant, ascending/descending/symmetrical triangle, rectangle. Breakout: 52-week high, all-time high, resistance breakout with volume. S/R: prev day/week high-low, round numbers (â‚¹500/â‚¹1000/â‚¹1500), Fibonacci (23.6/38.2/50/61.8/78.6%), pivots (Standard/Camarilla/Woodie). Q: does 52-week high breakout generate momentum in Indian large caps?

### 31.2 Category 4 â€” Strategy Archetypes (10 fundamentally different approaches)
1. Momentum (S01) â€” buy strength; best bull + low VIX. 2. Mean reversion (S02) â€” buy weakness in uptrend. 3. Breakout/Turtle (S03) â€” buy new highs with volume. 4. Volatility squeeze (S04) â€” buy after compression. 5. Price action only (S05) â€” patterns + S/R, zero indicators. 6. Volume-price/Wyckoff â€” accumulation/distribution. 7. Relative strength â€” strongest sector vs market. 8. Calendar effects â€” Monday/Friday, month/quarter-end, earnings season. 9. Fundamental triggers â€” earnings surprise, analyst upgrade, insider buying. 10. Volatility strategies â€” buy VIX spikes, mean-revert elevated VIX.
**KEY INSIGHT:** no single strategy works in all regimes; multiple strategies = smoother equity curve.

### 31.3 Category 5 â€” Timeframes
Currently daily only. Research: 5m (noisy), 15m (institutional), 1h (swing entry confirm), daily (current), weekly (positional). MTF: weekly trend + daily signal + 1H entry; monthly trend + weekly signal + daily entry. Expected: shorter = more signals/lower WR; longer = fewer/higher WR; optimal swing = daily signal + weekly confirmation.

### 31.4 Category 6 â€” Backtesting Methodology (anti-overfitting rules)
1. **Walk-forward only** (3y train, 1y OOS, roll 6mo; OOS drop >30% = overfit, reject). 2. **Survivorship bias correction** (historical constituents, not current; delisted = real losses). 3. **Look-ahead prevention** (signal on bar close, entry next bar open). 4. **Cost realism** (full STT/brokerage/stamp/exchange/GST/SEBI/slippage; gross-not-net = useless). 5. **Monte Carlo** (reorder 10,000Ã—; worst case = ruin â†’ too aggressive). 6. **Sensitivity analysis** (param should work across nearby values; only-works-at-exact-value = overfit).

### 31.5 Category 7 â€” Forecasting Methods
Stats: ARIMA, SARIMA, GARCH (vol forecasting â†’ size adjustment). ML: Random Forest, XGBoost (win/loss classifier), LSTM. Foundation models (future): TimesFM (Google), Chronos (Amazon) â€” zero-shot.

### 31.6 Category 8 â€” Alternative Data (all free/legal/underused)
Government: GST e-way, EPFO payroll, VAHAN registrations, DGCA air traffic, Coal India, IMD monsoon, GST collections. Corporate: MCA filings, SEBI enforcement, NSE bulk/block deals, NCLT, patents. Web/social: job postings, Glassdoor, Google Trends, Reddit (r/IndiaInvestments, r/Dalal_Street).

### 31.7 Category 9 â€” Indian-Market-Specific Research
Expiry week effects (weekly Thu intraday patterns; monthly last-Thu max vol) | RBI MPC effect (uncertainty 2 days before, clarity after) | Budget day patterns (2010â€“2026 study) | Monsoon effect (Junâ€“Sep: FMCG rural demand) | FII behavior (Dec profit booking, Jan fresh allocation, Mar quarter-end rebalancing) | SGX Nifty gap (overnight â†’ predicts open) | Sector rotation (which sectors lead early/late bull; defensives in bear).

### 31.8 Category 10 â€” Market Microstructure
Order-flow imbalance (OFI) â€” buy minus sell per price level, predicts 1â€“5 min direction | VWAP dynamics (institutional benchmark) | Bulk/block deals (NSE daily) | Circuit-breaker patterns (upper = demand, lower = panic).

### 31.9 Category 11 â€” Quantitative Methods
Fama-French 3-factor (market, size, value) | Pairs trading (cointegrated; buy laggard/sell leader on divergence) | Hurst exponent (H>0.5 trending, H<0.5 mean-reverting, H=0.5 random) | Kelly criterion f* = (bpâˆ’q)/b | Portfolio optimization (expected returns + covariance).

### 31.10 Category 12 â€” Behavioral Finance
Anchoring (52-week high, round numbers) | Earnings announcement drift (PEAD â€” post-surprise drift) | Disposition effect (sell winners early, hold losers) | Momentum crashes (regime change).

### 31.11 Category 13 â€” Corporate Governance
Promoter behavior (pledge ratio, open-market buying) | Audit quality (auditor change, qualified opinion) | Related-party transactions (excessive = money leakage).

### 31.12 Category 14 â€” Global Macro Connections
Dollar milkshake (strong USD â†’ EM outflows) | Carry trade (JPY strengthening â†’ carry unwind â†’ EM selloff) | Fed balance sheet (QE â†’ Nifty up, QT â†’ down) | Crude (India importer; high crude â†’ inflation â†’ RBI hawkish â†’ Nifty down).

### 31.13 Category 15 â€” Statistical Validation
**IC (most important metric):** >0.05 genuine edge, >0.10 strong (rare), <0.02 noise â†’ retire. IC decay (how long predictive) | Factor quantile analysis (Q1â€“Q5 buckets) | Sharpe interpretation (<0.5 poor, 0.5â€“1.0 acceptable, 1.0â€“2.0 professional, >2.0 exceptional â€” verify).

### 31.14 Category 16 â€” Tool Rationale
Alphalens first (does the signal have alpha at all before ML) | DuckDB (10k rows: pandas 4s vs DuckDB 0.04s) | MLflow (log every experiment, reproduce exactly) | pandas-market-calendars (hardcoded 14 holidays misses Eid/Muharram; NSE has 15â€“20/yr) | **Stand on giants:** MJONAI's unique value is NOT better ARIMA/backtester/optimizer â€” it IS Indian market knowledge, multi-strategy research framework, AI agent evaluation, systematic deployment, founder's judgment.

### 31.15 Category 17 â€” Forecasting vs Prediction
Prediction ("RELIANCE will be â‚¹1500 in 30 days") â‰ˆ impossible. Forecasting ("probability of positive return in 5 days = 62%") = what we do. Edge in probabilities: 58% WR Ã— 2R avg: 100 trades = +116R wins âˆ’ 42R losses = +74R net. Why forecasting fails: overfitting, regime change, costs, look-ahead bias.

### 31.16 Category 18 â€” Research Lab Data Flow
Data generated per closed paper trade (the 20-field log â€” see Â§27.1). After 500 trades answers: strategy performance (best WR / risk-adjusted / regime fit) | signal quality (RSI 55â€“70 predictive? structure vs ATR SL? swing-low confirm?) | agent accuracy (Bull BUY vs NEUTRAL matter? devil warnings correlate with losses? Supervisor aligns?) | timing (best time-of-day, day-of-week) | regime dependency (BULL/NEUTRAL/BEAR; VIX bands; MQI HIGH vs MEDIUM).

### 31.17 Category 19 â€” The Unknown Unknowns
Jim Simons: "We search for anomalies in data" â€” not "implement RSI/MACD/EMA." Log at signal time: phase of moon, distance from 52-week high, consecutive up days, VIX percentile (not level), Nifty500 breadth, day-of-month bucket, distance from ATH. Discipline: log everything, analyze systematically, test rigorously, accept what data says.

### 31.18 Category 20 â€” The Philosophical Foundation
Why systematic: humans have loss aversion (losses feel 2.5Ã—), overconfidence, revenge, FOMO, anchoring, herding. MJONAI removes via predetermined entry/SL/size, cooling periods, psychology guard. Why paper matters (Yogi Berra). Why 3â€“5 edges not 100 (Buffett: diversification = protection against ignorance). Why costs matter: 60% WR gross â†’ breaks even after 2% round-trip â†’ loses after 3%. Compounding: 1.5%/mo â†’ â‚¹1Lâ†’â‚¹5.90L in 10yr; 2.0%/mo â†’ â‚¹10.65L in 10yr â€” 80% more wealth.

### 31.19 What the Data Will Tell Us (Â§39 â€” the 8 questions after 100 trades/strategy)
1. Does RSI 55â€“70 predict returns? (IC test) 2. Does structure SL beat ATR SL? 3. Does Bull BUY add value? 4. Which devil check prevents most losses? 5. Best time of day? 6. Which regime suits each strategy? 7. Optimal confidence threshold? 8. Does sector-cap enforcement help?

### 31.20 Research Workflow (Â§40)
Wk1â€“2: generate data (RESEARCH mode, all strategies parallel, target 50+ trades before analysis). Wk3: export agent_logs â†’ DuckDB â†’ Alphalens per strategy/signal â†’ QuantStats â†’ MLflow. Wk4: deep dive (positive IC? regimes? devil checks? Bull alpha?). Month 2: iterate versions in MLflow. Month 3: 200+ trades AND IC>0.05 â†’ walk-forward â†’ pass gates â†’ graduate LIVE; IC<0.02 after 200 â†’ retire + document + archive.

### 31.21 Session 7 Insights (Â§41 â€” the 7 foundational realizations)
1. Paper limits were wrong (â‚¹2L real-money rules â‰  â‚¹0-risk sim; research = unlimited positions, Nifty 500). 2. Fixed â‚¹10k size for comparability (risk-based sizing distorts stats across stocks). 3. Devil checks WARN (not veto) in research mode â€” discover if they prevent losses. 4. Strategy registry enables parallel testing. 5. Tool philosophy: don't build what exists (statsmodels, xgboost); build Indian knowledge + agent eval + deployment. 6. North star narrow: find 3â€“5 edges, execute well; complexity â‰  edge. 7. Research lab mindset: signal = hypothesis, paper trade = experiment, closed trade = data point.

### 31.22 Changelog (Â§42 â€” key history)
**v2.0 (06 May, S16):** strategy independence | scan overlap lock | forward returns module | S06+S07 shorts | signal_direction field | Groq rate backoff 2.1s (FIX-M) | NaN guards | year-boundary holiday refresh (FIX-O) | MQI LOW=1 signal (FIX-MQ13) | WS _stop_requested (FIX-T) | Telegram SYSTEM_MODE check (FIX-Y) | 12 new DB columns | research scheduler | full audit (27 files, 18 fixed, 9 verified) | docs merged 4â†’2.
**v1.5 (01 May, S7):** llama-3.3-70b | google-genai 1.74 | gemini-2.5-flash | bull fallback 8B cap-80 | supervisor deterministic rules | devil checks pre-LLM | earnings yfinance+NSE, 3-day block | pipeline: technicalâ†’confidenceâ†’earningsâ†’sectorâ†’LTPâ†’levelsâ†’devilâ†’bullâ†’supervisor | dynamic limits (BULL+HIGH=5, NEUTRAL+HIGH=3, BEAR=1, VIX>25=1) | time barrier 7 trading days | sector cap 2 stocks/25% | close_trade closes tranches first | quantity_remaining for P&L | Research Lab mode | registry parallel testing | Oracle prep.
**v1.4:** RSI range corrected | devil architecture separated | Kill Line vs Level 3 clarified | agent_weight_log as Table 13.
**v1.3 (15 fixes):** TA-Lib â†’ WSL2 mandatory | Ollama on-demand (RAM) | Render â†’ GitHub Actions | Shoonya manual-only | FII/DII T-1 acknowledged | Groq fallback trigger | Supabase 500MB retention | Next.js 15 | VectorBTâ†’Backtrader noted | confidence component-fail auto-reject | "recently" = 90 days | devil veto = code only | SHAP â†’ Transparency Report | Polymarket Tier 3 | Level 3 = system integrity only.

## 32. ORACLE DEPLOYMENT, ARTHAI OPS RECORD, SYSTEM-ALGORITHM DRIFT & GOVERNANCE LOG

### 32.1 Oracle Cloud Deployment Guide (from ORACLE_CLOUD_DEPLOYMENT.md)
- Region: **India South (Mumbai) `ap-mumbai-1`** or India West (Hyderabad) `ap-hyderabad-1`
- Image: Ubuntu 22.04/24.04 LTS (Canonical). Shapes: `VM.Standard.A1.Flex` (Ampere ARM, 4 OCPU/24GB â€” Always-Free eligible) OR `VM.Standard.E2.1.Micro` (AMD x86, 1 OCPU/1GB â€” the box in use)
- SSH keys: download & save private key (e.g. `oracle_vm_key.pem`)
- **Firewall (VCN â†’ Security Lists ingress):** Port 22 (SSH), 80/443 (dashboard), 8000 (FastAPI) â€” CIDR 0.0.0.0/0
- Deploy: `ssh -i key ubuntu@<IP>` â†’ `sudo mkdir -p /opt/MJONAI && sudo chown -R ubuntu:ubuntu /opt/MJONAI` â†’ from Windows `scp -i key -r d:\MJONAI\* ubuntu@<IP>:/opt/MJONAI/` â†’ `chmod +x scripts/setup_oracle_vm.sh && ./setup_oracle_vm.sh`
- Manage: `systemctl start|stop|restart|status mjonai`, `journalctl -u mjonai -f`
- Daily automation timeline (from the guide): 08:45 gift_nifty gap | 09:00 token sync | 09:15 WS live + strategies | 09:15â€“15:15 debate+execution | 15:15 close intraday MIS | 15:30 feeds pause | 16:00 EOD PnL + tax ledger + Telegram

### 32.2 ArthAI Phase-1 Ops Record (from ArthAI_Project_Summary.md â€” the actual content)
- Repo: github.com/manisankarreddyj/arthai.git (main); local folder D:\ArthAI_project; Python 3.14.3 (older stack)
- **Run command:** `uvicorn backend.main:app --reload --reload-dir backend --host 0.0.0.0 --port 8000` â†’ docs at /docs
- **Auto-schedule (Render-era):** 8:45 AM morning briefing | 9:20 AM Nifty 50 scan | 3:45 PM EOD â€” all â†’ Telegram + Discord; keep-alive via GitHub Actions at 8:44 + 9:18
- **Test results then:** local 13/13 passing, prod 4/4 passing, LIVE on Render.com
- **15 API endpoints (the full list):** GET /api/health, GET /api/, /api/market/mood, /api/market/top-stocks, /api/market/nifty50 | POST /api/signal/generate, /signal/scan (max 20), /signal/scan-nifty50, /signal/scan-extended (100), GET /api/signal/history | POST /api/chat, /api/position-size, /api/risk-profile | POST /api/paper-trade/open (BUY only), /paper-trade/close, GET /api/paper-trade/list. Security: X-Arthai-Key header on writes.
- **Supabase tables then (4):** signals, user_profiles, paper_trades, market_mood
- **Service/account matrix (costs):** GitHub free, Supabase free 500MB (4 tables), Google Cloud UPI-linked â‚¹500 budget, Render free, Vercel free (frontend not built), Upstash Redis free (unused), Gemini free 18mo (primary), Groq free forever (backup), Telegram free (primary alerts), Discord free (6 webhooks), AngelOne free, HuggingFace free
- **Note:** this was the pre-merge ArthAI era; current MJONAI supersedes it (schema, stack, structure all newer) â€” kept as historical record + the account matrix is still the live account inventory.

### 32.3 System Algorithms â€” Implementation Reality & Drift (from SYSTEM_ALGORITHMS.md, verified 27 May 2026)
**DB schema evolution (17 tables â€” the full history):**
- **Original 6:** trades (30 research cols in S8, +signal_direction S16) | trade_tranches | **signals (DEPRECATED â€” kept, no new inserts)** | market_state_history | risk_events | system_log
- **8 new (Session 8):** signal_intelligence_log (87+ cols â€” the PRIMARY signal table) | agent_logs (22) | daily_portfolio_snapshot (40) | pattern_memory (22) | scan_log (22) | system_health_log (19) | strategy_performance (28) | agent_weight_log (20)
- **Session 16 additions:** signal_intelligence_log += forward_return_1d/3d/5d/10d/20d, pnl_1d..20d, raw_signal_value, signal_direction; trades += signal_direction (default LONG)
- **signal_type ENUM:** GENERATED, PRE_FILTERED, DEBATE_REJECTED, APPROVED, EXPIRED, EXECUTED, CLOSED, MISSED_FILTERED, MISSED_REJECTED, MISSED_EXPIRED, GHOST_SIGNAL
- **Retention (Supabase 500MB free tier):** signal_intelligence_log 90 days (exportâ†’delete), agent_logs 180 days, market_state_history 365 days, trades/pattern_memory/agent_weight_log PERMANENT. Weekly cleanup job Sunday 2 AM (GitHub Actions).

**âš ï¸ THE DRIFT TABLE (Master spec vs. actual code â€” code is truth):**
| Concept | Master said | Code actually does | Severity |
|---|---|---|---|
| MQI factors | 6 | **5** (no "gap follow-through" factor) | LOW |
| Market State Factor 2 (breadth) | computed from Nifty 500 | **hardcoded 0 (placeholder)** | MED |
| Market State Factor 4 (FII) | NSE T-1 + proxy | **hardcoded 0 (placeholder)** | MED |
| MQI Factor 3 (breadth) | computed | **hardcoded 1 (placeholder)** | LOW |
| MQI Factor 6 (opening volume) | computed | **hardcoded 1 (placeholder)** | LOW |
| Confidence formula | Master formula | `calculate_confidence()` exists â€” **NEEDS AUDIT** | NEEDS AUDIT |
| Triple-barrier exits | Master | paper.py implements â€” **NEEDS AUDIT** | NEEDS AUDIT |

**Also verified in code:** market_state Factor 1 uses `yf.Ticker("^NSEI").history(period="1y")` (NOT yf.download â€” MS02/MS03 fix avoids MultiIndex); VIX default on failure 15.0 (NEUTRAL); Supervisor optimization FIX-SV05 = only calls Gemini on the APPROVE path (saves quota); Bull 2.1s min between calls, 3 consecutive failures â†’ safe NEUTRAL; RESEARCH mode: devil checks WARN (not veto) + unlimited signals (9999) â€” LIVE mode enforces limits; all 7 strategies run INDEPENDENTLY per symbol per scan (SS19 fix â€” was "first wins" before).

### 32.4 Governance Log (from IDEAS.md + QUESTIONS.md â€” the actual contents)
- **IDEA-001 (Under Discussion, Very High, 03 July 2026):** Transform MJONAI into an Autonomous Financial Intelligence Operating System â€” research, forecasting, portfolio intelligence, risk management, multi-asset analysis, explainable AI, autonomous improvement with human governance. (Matches ADR-001.)
- **Q-001 (Open, Very High):** What should be the complete organizational structure of MJONAI? (â†’ the Â§26.7 Board & Governance is the answer in progress.)
- **Rules:** ideas/questions never deleted; ideas flow Discussion â†’ Research â†’ Design â†’ Approval â†’ Implementation; answers recorded with decision dates.

## 33. GENERATION-0 DIRECTIVE RESOLUTION

### 33.1 The Directive (from GENERATION_STATUS.md, 03 Jul 2026)
- Generation 0 â€” Foundation | Sprint 0 â€” Project Blueprint | Phase: Understanding Existing System
- Status: In Progress | Task: understand the repo before changes | Branch: generation-0-foundation
- **Rule:** No restructuring. No deletion. No new architecture implementation. Understand first.

### 33.2 Resolution (19 Aug 2026 â€” founder decision)
- **SUPERSEDED** by explicit founder-directed actions this session: merge of mjonai-research â†’ mjonai-build, archiving of Test/ + legacy research/ + all legacy docs, and env consolidation.
- The "understand first" phase is complete â€” the full system was read, documented (this master doc), and the merge/cleanup executed under direct founder instruction.
- **Remaining live governance:** the Anti-Drift rules (Â§1), Golden Rules (Â§2), Coding Standards (Â§26.3), and Capital Tier rules (Â§26.6). "No restructuring" applied only to Generation-0's discovery phase, which is done.

FILE: mjonai-build\.env
----------------------------------------------------------------------------------------------------
[SECRET FILE - VARIABLE NAMES ONLY]

ENV FILE: credentials\.env.master
  ANGELONE_API_KEY [PRESENT]
  ANGELONE_CLIENT_ID [PRESENT]
  ANGELONE_PASSWORD [PRESENT]
  ANGELONE_TOTP_SECRET [PRESENT]
  ANGELONE_SECRET_KEY [PRESENT]
  SHOONYA_API_KEY [PRESENT]
  SHOONYA_IMEI [PRESENT]
  SHOONYA_PASSWORD [PRESENT]
  SHOONYA_SECRET_CODE [PRESENT]
  SHOONYA_USER_ID [PRESENT]
  SHOONYA_VENDOR_CODE [PRESENT]
  TELEGRAM_BOT_TOKEN [PRESENT]
  TELEGRAM_CHAT_ID [PRESENT]
  SUPABASE_DB_URL [PRESENT]
  SUPABASE_KEY [PRESENT]
  SUPABASE_URL [PRESENT]
  DATABASE_URL [PRESENT]
  POSTGRES_DB [PRESENT]
  POSTGRES_PASSWORD [PRESENT]
  POSTGRES_PORT [PRESENT]
  POSTGRES_USER [PRESENT]
  DISCORD_ALERTS_CHANNEL [PRESENT]
  DISCORD_BOT_TOKEN [PRESENT]
  DISCORD_MARKET_MOOD_CHANNEL [PRESENT]
  DISCORD_OPTIONS_CHANNEL [PRESENT]
  DISCORD_PAPER_TRADING_CHANNEL [PRESENT]
  DISCORD_PORTFOLIO_CHANNEL [PRESENT]
  DISCORD_SERVER_ID [PRESENT]
  DISCORD_SIGNALS_CHANNEL [PRESENT]
  DISCORD_WEBHOOK_ALERTS [PRESENT]
  DISCORD_WEBHOOK_MARKET_MOOD [PRESENT]
  DISCORD_WEBHOOK_OPTIONS [PRESENT]
  DISCORD_WEBHOOK_PAPER_TRADING [PRESENT]
  DISCORD_WEBHOOK_PORTFOLIO [PRESENT]
  DISCORD_WEBHOOK_SIGNALS [PRESENT]
  REDIS_PORT [PRESENT]
  UPSTASH_REDIS_REST_TOKEN [PRESENT]
  UPSTASH_REDIS_REST_URL [PRESENT]
  UPSTASH_REDIS_TOKEN [PRESENT]
  UPSTASH_REDIS_URL [PRESENT]
  CLAUDE_API_KEY [PRESENT]
  GEMINI_API_KEY [PRESENT]
  GROQ_API_KEY [PRESENT]
  HUGGINGFACE_TOKEN [PRESENT]
  OLLAMA_PORT [PRESENT]
  NEWS_API_KEY [PRESENT]
  SERPAPI_KEY [PRESENT]
  TAVILY_API_KEY [PRESENT]
  APP_ENV [PRESENT]
  APP_NAME [PRESENT]
  APP_PORT [PRESENT]
  APP_VERSION [PRESENT]
  ARTHAI_API_KEY [PRESENT]
  CAPITAL_TOTAL [PRESENT]
  DASHBOARD_PORT [PRESENT]
  DEBUG [PRESENT]
  ENVIRONMENT [PRESENT]
  GOOGLE_CLOUD_PROJECT [PRESENT]
  GOOGLE_CLOUD_REGION [PRESENT]
  MAX_RISK_PER_TRADE [PRESENT]
  MAX_SIGNALS_PER_DAY [PRESENT]
  MIN_CONFIDENCE_SCORE [PRESENT]
  MIN_RISK_REWARD [PRESENT]
  PAPER_TRADING_MODE [PRESENT]
  RENDER_URL [PRESENT]
  STARTING_CAPITAL_INR [PRESENT]
  TIMESCALE_DB [PRESENT]
  TIMESCALE_PASSWORD [PRESENT]
  TIMESCALE_PORT [PRESENT]
  TIMESCALE_USER [PRESENT]
  VERCEL_URL [PRESENT]
ENV FILE: mjonai-build\.env
  ANGELONE_API_KEY [PRESENT]
  ANGELONE_CLIENT_ID [PRESENT]
  ANGELONE_PASSWORD [PRESENT]
  ANGELONE_TOTP_SECRET [PRESENT]
  TELEGRAM_BOT_TOKEN [PRESENT]
  TELEGRAM_CHAT_ID [PRESENT]
  SUPABASE_URL [PRESENT]
  SUPABASE_KEY [PRESENT]
  SUPABASE_DB_URL [PRESENT]
  SHOONYA_USER_ID [PRESENT]
  SHOONYA_PASSWORD [PRESENT]
  SHOONYA_SECRET_CODE [PRESENT]
  SHOONYA_VENDOR_CODE [PRESENT]
  SHOONYA_API_KEY [PRESENT]
  SHOONYA_IMEI [PRESENT]
  GROQ_API_KEY [PRESENT]
  GEMINI_API_KEY [PRESENT]

[SECRET VALUES OMITTED]

FILE: mjonai-build\.gitignore
----------------------------------------------------------------------------------------------------
