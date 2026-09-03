ARTHAI
Arth (Meaning) + AI
MASTER SPECIFICATION & EXECUTION PLAN
Version 4.1 — CONSOLIDATED SUPREME EDITION
Single Source of Truth — All Gaps Resolved — All Regressions Fixed
Created: April 2026  |  Supersedes v3.0 and v4.0

What is new in v4.1 vs v4.0
Fixed: Yahoo Finance regression — Tiingo is primary for global data, Yahoo is last-resort only
Fixed: NCDEX data source — specific vendors now named with authentication approach
Fixed: MCX/Shoonya WebSocket — authentication flow documented
Fixed: Historical options data — specific vendors for backtesting named
Fixed: FinBERT integration — model variant, preprocessing, threshold all specified
Fixed: Telegram format — exact message templates per signal type now in spec
Fixed: Paper-to-real transition — exact criteria fully defined
Fixed: Family system data isolation — architecture specified
Added: instrument_key universal standard to all DB tables
Added: DB index specifications (signals, paper_trades, portfolio)
Added: agent_disagreement_log table
Added: data_lineage_log table
Added: signal_correlation_log table
Added: liquidity_scores table
Added: backtest_cost_assumptions table
Added: ex_date vs record_date distinction in corporate_actions_log
Added: is_deleted soft delete as standard on all tables
Added: comex_mcx_spread.py to Phase 16 file list
Added: assignment_risk_handler.py as dedicated file
Added: Asset class coverage % tracker in ARTHAI_CONTEXT.md template
Added: Color-coded P0/P1/P2/P3 priority on every phase task
 
SECTION 1: PROJECT IDENTITY & CORE PHILOSOPHY
1.1 Identity
Attribute	Value
Full Name	ArthAI — Arth (Meaning in Hindi) + AI
Type	AI-Powered Complete Wealth Generation Intelligence System
Scope	Every money-making opportunity in Indian and global financial markets
Owner	Personal → Family → Business (SEBI Registered)
Python Version	3.11 — do not use 3.12, 3.13, or 3.14
Project Path	D:\My_Project_ArthAI
Paper Capital	Rs 1,00,000 (paper trading phase)
Real Capital Path	Rs 10K → 25K → 50K → 1L → Unlimited
Goal	India's most intelligent, disciplined, consistent personal wealth system

1.2 Golden Rules — HARDCODED, NEVER OVERRIDE
These rules are the constitutional law of ArthAI. No signal, no agent, no user, no code change can break them. Every module must enforce them independently.
•	Capital protection over profit — ALWAYS, in every situation without exception
•	Never override a stop loss once it is set — loss aversion is the enemy of survival
•	Minimum 3 of 4 AI agents must agree for any signal to pass
•	2-2 agent split = wait 15 minutes, re-debate, still split = REJECT the signal
•	Devil Agent VETO overrides all other votes — no appeal, no override
•	Confidence below 65% = REJECTED automatically — no exceptions
•	Risk:Reward below 2.0 = REJECTED automatically — no exceptions
•	Never risk more than 2% of capital per trade
•	Maximum 4 signals per day — HARD LIMIT for intraday, no override possible
•	Psychology guard CANNOT be disabled by any user, admin, or code change
•	Paper trade minimum 30 days before any real money is deployed
•	Real money only after 65%+ win rate sustained over 20+ trades in that asset class
•	Each asset class must prove 60%+ accuracy independently before next class is added
•	SEBI compliance: personal use only until Research Analyst registration is received

1.3 The Philosophical DNA — 10 Masters
Master	What ArthAI Borrows — Specifically
Warren Buffett	Business quality focus, long-term compounding, never invest in what you don't understand
Jesse Livermore	Market timing precision, trend following, "sitting" — patience to wait for the perfect setup
Ray Dalio	All Weather portfolio, macro analysis, risk parity, debt cycle awareness
Paul Tudor Jones	Strict risk management, never average a losing position, preserve capital first
Peter Lynch	Growth stock identification, PEG ratio, investing in what you understand
John Bogle	Index fund wisdom, cost minimization, long-term compounding over short-term trading
Benjamin Graham	Margin of safety, deep value, fundamental analysis as foundation
George Soros	Reflexivity — market participants influence fundamentals, currency dynamics
Jim Simons (RenTech)	Statistical patterns, data-driven decisions, adaptive models, no human override
Daniel Kahneman	Behavioral finance, cognitive bias taxonomy, psychology guard design

1.4 The Supreme Insight — Renaissance Technologies
The Medallion Fund made 66% annually for 34 years by being right just 50.75% of the time — across millions of trades, with perfect discipline, zero emotion, and continuous adaptive learning. ArthAI does not aim to predict markets. It aims to be systematically right 55-65% of the time with iron discipline. That is enough to build extraordinary wealth.
 
SECTION 2: ASSET CLASS COVERAGE — CURRENT STATUS TRACKER
This section is the honest current-state tracker missing from v4.0. Update these percentages monthly as modules are built. Do not let the spec fool you into thinking everything is equally ready.

2.1 Coverage Status — Update Monthly in ARTHAI_CONTEXT.md
Asset Class	Coverage %	Status	What Is Missing
NSE/BSE Equities	75%	Partial	Fundamental analysis engine, factor scorer, annual report red flag
F&O Index Options	40%	Critical gaps	IV Rank, Max Pain, GEX, 0DTE engine, options flow tracker, payoff builder
MCX Metals (Precious)	25%	Critical gaps	Gold Petal/Guinea/Mini, Silver Micro/Mini, Platinum, Palladium, commodity options
MCX Metals (Base)	20%	Critical gaps	All Mini variants, Brass, Steel Long, LME feed, SHFE correlation
MCX Energy	25%	Critical gaps	Crude Mini, NatGas Mini, Brent-WTI spread, EIA calendar, OPEC calendar
NCDEX Agri	10%	Blocking gap	Data source not confirmed, no engine files, monsoon/MSP feeds missing
Mutual Funds	60%	Partial	Fund overlap, direct vs regular cost drag, manager change alert, STP routing
ETFs	55%	Partial	NAV arbitrage detector, ETF vs MF comparison, international ETF full coverage
Fixed Income/Bonds	50%	Partial	Duration calculator, credit spread tracker, bond ladder builder, 54EC bonds
Currency/Forex	45%	Partial	RBI intervention model, carry trade calc, cross-currency options
Cryptocurrency	40%	Partial	On-chain analytics, funding rate, liquidation heatmap, VDA tax tracking
IPO/Primary Market	55%	Partial	DRHP AI analysis, promoter background, use-of-proceeds analyzer
REITs/InvITs	50%	Partial	NAV vs market price, pipeline asset tracking, distribution yield
Tax-Advantaged (PPF/NPS)	45%	Partial	NPS corpus projector, PPF optimizer, ELSS per-unit lock-in tracker
Global/US Stocks	30%	Critical gaps	LRS planner, currency-adjusted return calc, Tiingo data feed
Special Opportunities	50%	Partial	Merger arbitrage, delisting analysis, special dividend tracking
 
SECTION 3: THE 8-LAYER EVIDENCE FRAMEWORK
Technical indicators alone: 52-55% win rate. Same indicators confirmed by all 8 layers: 62-68% win rate. The indicators do not change — the confirmation does. A signal is when 8 completely independent data sources all agree simultaneously.

Layer 1: Technical Indicators
Momentum
•	RSI (14) — 55-70 zone = momentum building without overbought condition
•	MACD — histogram turning positive + line crossing signal line upward
•	Stochastic Oscillator — crossing above 20 from oversold = reversal signal
•	Rate of Change (ROC) — accelerating rate signals strengthening trend
•	Williams %R — complementary momentum confirmation
Trend
•	Supertrend — flip from red to green = trend change confirmed with ATR band
•	EMA Stack — 9 > 21 > 50 > 200 = perfect bull alignment, all timeframes
•	ADX — above 25 = strong trend worth trading, below 20 = range-bound, avoid directional
•	Ichimoku Cloud — price above green cloud = strong uptrend
•	Parabolic SAR — used for trailing stop, not entry signal
Structure
•	Support/Resistance — price breaking above key resistance with conviction
•	Fibonacci — 61.8% retracement = highest probability reversal zone
•	Chart Patterns — Cup & Handle, Bull Flag, Inverse H&S, Ascending Triangle
•	Multi-Timeframe Alignment — 5m, 15m, 1H, Daily must ALL agree on direction
•	Pivot Points — daily, weekly, monthly S/R reference levels
•	Market Profile / Value Area — where price spent most time = fair value zone
Volatility
•	Bollinger Band Squeeze — bands compress then expand = momentum signal
•	ATR (14) — used ONLY for stop loss sizing, not direction: SL = Entry ± 2×ATR
•	India VIX — below 14 = calm, 14-20 = normal, above 20 = elevated fear (adjust confidence)
Candlestick Patterns
•	Bullish Engulfing at support = strong reversal signal
•	Hammer with long lower wick = buyers rejecting lower prices
•	Morning Star / Evening Star = 3-candle reversal patterns
•	Pin Bar = sharp rejection of key level, highest probability pattern
•	Inside Bar breakout = compression then explosive directional move

Layer 2: Volume and Market Microstructure
Scenario	Meaning	ArthAI Action
Price rising + Volume rising	Healthy trend with institutional participation	Confirm bullish — full confidence
Price rising + Volume falling	Rally losing steam, institutions not buying	Reduce Bull confidence by 15%
Price falling + Volume rising	Genuine institutional selling / distribution	Confirm bearish — do not fight
Price flat + Volume rising	Accumulation or distribution in progress	Alert: big move coming, check OBV direction
Volume spike without news	Smart money acting on non-public information	STRONG signal — direction = institutional bias
Delivery % above 60% on rally	Real accumulation, institutions holding	Confirms bullish — raise confidence
Delivery % below 25% on rally	Just traders, no real conviction	Fake breakout risk — reduce confidence 10%
Bid-ask spread doubles from normal	Liquidity drying up — dangerous entry	Widen stop loss by 1.5×, reduce size
•	VWAP — price above VWAP = buyers in control today (institutional benchmark)
•	VWAP retest after breakout = ideal entry — institutions buying the retest
•	OBV rising while price flat = quiet institutional accumulation (most powerful signal)
•	Volume Profile — high volume node = strong S/R, low volume node = price moves fast

Layer 3: Options Market Intelligence
Options traders act with institutional conviction. Options flow precedes price movement — price follows options, not the other way around. This is the most powerful leading indicator in Layer 3.
Metric	Formula	Signal Interpretation
IV Rank	(Current IV - 52W Low) / (52W High - 52W Low) × 100	Below 30 = cheap, buy options. Above 70 = expensive, sell premium
IV Percentile	Count(days where IV < Current IV, last 252 days) / 252 × 100	Above 70% = most expensive in past year — sell premium strategies
Max Pain	Strike where Σ(call losses + put losses for holders) is maximized	Price gravitates here at expiry — key level for intraday targets
Expected Move	±(ATM Straddle Price / Spot Price) × 100	Implied ±% range for expiry week — do not expect breakout beyond this
Gamma Exposure (GEX)	Σ(Call OI × Call Gamma - Put OI × Put Gamma) × Spot² × 0.01	Positive GEX = dealers buy dips (supportive), Negative GEX = dealers sell rallies (volatile)
PCR Trend	Direction of PCR change over 3-5 days	Rising PCR = more puts being bought = bearish hedge. Direction > absolute value
•	Options Flow — unusual call/put volume > 5× 20-day average = institutional conviction bet
•	Synthetic Long (buy call + sell put simultaneously) = strong institutional directional bet
•	Large block option trade (single ticket > 10,000 lots) = fund-size position, strong signal
•	Put wall / Call wall — massive OI at a strike = price magnet and strong S/R
•	0DTE requires completely different risk rules — separate engine, separate confidence thresholds

Layer 4: Institutional Flow Intelligence
FII-DII Combination	Market Implication	Confidence Adjustment
FII buying + DII buying	STRONG BULL — both domestic and foreign agree	+10% confidence on bullish signals
FII selling + DII buying	RESILIENT — corrections shallow and short-lived	No adjustment — market has domestic support
FII buying + DII selling	Domestic profit booking — rally may not sustain	-5% confidence, watch for reversal
FII selling + DII selling	DANGER ZONE — major correction possible	-20% confidence, reduce all sizes
•	FII Derivative Positions (SEBI daily at 6 PM) — FII net long > 50,000 contracts = institutional bullish
•	FII net short futures flip from long in < 3 days = sudden view change, wait before acting
•	Bulk deals (0.5%+ stake) and block deals — real-time institutional transaction signals
•	FII herding detection — when FIIs buy/sell collectively, look for contrarian opportunity
•	DII SIP flow proxy — rising monthly SIP inflows = structural market support, corrections absorbed faster

Layer 5: Fundamental Quality Signals
•	Promoter holding consecutive Q increases (3+ quarters) = strongest long-term buy signal in India
•	Promoter pledging > 70% of promoter holding = automatic caution flag, Bear Agent overrides
•	Legal insider buying by CFO/MD = override all signals to BULLISH — they know next quarter
•	Earnings Quality Score — cash earnings vs reported earnings divergence (accruals ratio)
•	ROCE trend rising over 6 quarters = quality business improving
•	Free Cash Flow Yield > 5% = undervalued with real cash generation
•	Annual report red flags: auditor change, going concern note, related party transaction spikes
•	Concall tone analysis: management getting more defensive = forward guidance caution

Layer 6: Macro and Regulatory Intelligence
•	RBI MPC calendar — rate decisions move banking/real estate by 3-5%, pre-position carefully
•	RBI daily money market ops — VRR injection for 5+ days = easing bias BEFORE official statement
•	10-year G-Sec yield — sharp rise of 20bps in a week = FII bond selling, equity selling follows 5-10 days later
•	FOMC calendar (US Federal Reserve) — impacts Indian markets 0.5-1% on decision days
•	DXY — strong dollar = FII outflows from India, weak dollar = inflows
•	SEBI consultation papers — published weeks before final circulars, predict regulatory changes
•	India VIX regime — below 14 calm (+8% confidence), 14-20 normal, 20-25 elevated (-10%), above 25 danger (-20%), above 30 halt
•	Union Budget sector impact model — pre/post Budget signal adjustments by sector

Layer 7: Alternative Data — The Unfair Edge
65% of global hedge funds use alternative data, achieving 180-340 basis points additional alpha. Most Indian retail systems use zero alternative data. This is the biggest untapped edge available.
Data Source	What It Signals	India Application	Accessibility
Google Trends	Consumer interest before it appears in financials	Spike in searches for "HDFC Bank loan" = product demand rising	Free — Google Trends API
Job Posting Velocity	Division growth leads earnings by 2-3 quarters	Company aggressively hiring in sales = revenue growth coming	LinkedIn, Naukri scraper
App Store Ratings	Customer satisfaction deterioration before financials	Rating drops 4.3→3.8 in one month = churn risk rising	App store scraper
News Sentiment Velocity	Rate of change of sentiment, not just direction	3 positive articles yesterday, 12 today = acceleration	FinBERT on news feeds
Port Traffic (JNPT)	Macro leading indicator before GDP data	Container volume drop 2 months = economic slowdown coming	JNPT monthly data — public
Electricity Consumption	Industrial production proxy	Steel plant power consumption rising = production increasing	State electricity board data
Patent Filings	Product pipeline building signal	Heavy filing in specific tech = product launch coming	Patent office public data
Import/Export Data	Sector-specific margin signal	Steel import spike = steel user margins about to compress	DGFT monthly data — public

Layer 8: Pattern Memory Database
Every time a setup fires, log it. Every time a trade closes, log the outcome. After 6 months you have evidence instead of opinions. The Devil Agent stops guessing and starts citing.
•	Setup fingerprint: RSI range + MACD state + volume ratio + price vs MA + VIX bucket
•	Market context: Nifty trend, sector trend, FII flow direction, time of day, day of week
•	Agent votes: each agent verdict + confidence + key reasons (stored as JSONB)
•	Outcome: TARGET_HIT / SL_HIT / MANUALLY_CLOSED / EXPIRED with exact P&L after costs
•	Error classification: SIGNAL_ERROR / TIMING_ERROR / REGIME_ERROR / DATA_ERROR / ANOMALY / EXECUTION_ERROR
•	Query output: "This setup appeared 47 times. Won 31 (66%). In VIX > 20 only won 38%. Current VIX 22.4 — CAUTION."
 
SECTION 4: THE AI AGENT DEBATE ROOM — COMPLETE SPECIFICATION
4.1 Five Agent Architecture
Agent 1: The Bull — Technical Analyst
Attribute	Specification
Model	Groq llama-3.1-8b-instant (ultra fast — needed for real-time 15-min cycles)
Fallback	Ollama Llama 3.1 local (unlimited, free, no API cost)
File	core/ai_brain/agent_bull.py
Output Format	JSON: {verdict, confidence, key_reasons, regime_note, pattern_history}
Regime Rule	VIX > 20 → reduce confidence by 15% automatically
Regime Rule	Price > 3% above 20 EMA → reduce confidence by 8% (extended, risky entry)
Pattern Memory	Queries Pattern Memory DB before voting — cites historical win rate in reasoning
Analyzes	RSI, MACD, EMA stack, ATR, Supertrend, ADX, BB, OBV, VWAP, candlesticks, S/R, multi-TF

Agent 2: The Bear — Fundamental and Sentiment
Attribute	Specification
Model	Gemini 2.5 Flash (primary) + FinBERT local (sentiment layer)
FinBERT Model	ProsusAI/finbert from HuggingFace — specifically trained on financial text
FinBERT Preprocessing	Strip HTML, remove boilerplate, truncate to 512 tokens, pass sentence by sentence
FinBERT Threshold	Score > 0.6 positive = BULLISH signal, < -0.6 negative = BEARISH, between = NEUTRAL
Fallback	Cohere (100 requests/minute free tier)
File	core/ai_brain/agent_bear.py
Output Format	JSON: {verdict, confidence, key_reasons, red_flags, insider_activity}
Pledge Rule	Promoter pledge > 70% of total promoter holding = automatic BEARISH flag regardless of other data
Insider Override	CFO or MD legal insider buy in last 30 days = override to BULLISH, +20% confidence
Analyzes	FII/DII flows, promoter holding trend, pledge %, delivery %, PCR trend, news sentiment, insider trades, credit ratings, bulk/block deals, earnings quality

Agent 3: The Economist — Macro Analyst
Attribute	Specification
Model	Perplexity API (real-time search) + Claude as backup
Fallback	Cached RSS feeds + SerpAPI + Tavily
File	core/ai_brain/agent_economist.py
Cache Policy	Macro context cached once per hour — does not change minute by minute
Output Format	JSON: {verdict, confidence, macro_regime, key_reasons, event_risks, rbi_bias}
RBI Binary Event Rule	If MPC decision within 2 trading days: reduce ALL directional confidence by 20%
FOMC Binary Event Rule	If FOMC decision within 2 trading days: reduce confidence by 10% on all signals
RBI Liquidity Signal	VRR injection for 5+ consecutive days = easing bias BEFORE official statement
G-Sec Yield Signal	10-year yield rises 20bps in a week = FII bond selling coming, equity caution
SEBI Monitoring	Reads SEBI consultation papers (sebi.gov.in) — predicts regulatory changes weeks ahead
Analyzes	RBI MPC calendar, G-Sec yield, USD/INR, US Fed FOMC, Brent crude, DXY, Gift Nifty, geopolitics, GDP, SEBI papers, Budget sector impacts

Agent 4: The Devil's Advocate
Attribute	Specification
Model	Groq llama-3.3-70b-versatile (largest, most powerful reasoning model)
Fallback	Mistral large
File	core/ai_brain/agent_devil.py
Power	VETO overrides all other votes — BROKE_SIGNAL = rejected, no exceptions, no appeal
Output Format	JSON: {verdict, confidence, break_reason, historical_evidence, stress_points, correlation_risk}
Historical Precedent	Queries Pattern Memory DB first — reports exact stats: "47 occurrences, 66% win, 38% in VIX>20"
Liquidity Stress Test	Checks bid-ask spread and OI depth — thin liquidity = automatic BROKE_SIGNAL
Correlation Check	Calls signal_correlation_checker.py — flags if portfolio has correlated active position
Gap Risk	Checks upcoming earnings/events in next 3 days that could gap beyond stop loss
Data Quality Check	Verifies data quality score of all inputs > 85% — below = flag as data risk

Agent 5 (Supervisor): The Final Decision Maker
Attribute	Specification
Model	Gemini 2.5 Pro (most intelligent — justified cost for final decision only)
File	core/ai_brain/supervisor.py
Adaptive Weights	Reads agent_performance table — adjusts weights by asset class and VIX regime
Confidence Output	Format: "72 ± 8" — not just "72" — honest uncertainty range
Position Size Factor	Confidence 65-70% = 0.5×, 70-80% = 0.75×, 80-90% = 1.0×, 90%+ = 1.25×
Output Format	JSON: {approved, verdict, final_confidence, confidence_interval, position_size_factor, rejection_reason, signal_summary}

4.2 Consensus Logic — Complete Rules
Scenario	Outcome	System Action
4/4 agents agree + Devil fails to break	STRONG SIGNAL	Approve at full position_size_factor
3/4 agents agree + Devil fails to break	SIGNAL	Approve at standard position_size_factor
2-2 split	UNCERTAIN	Wait 15 min, re-debate, still split = REJECT, log to agent_disagreement_log
Devil outputs BROKE_SIGNAL	REJECTED	Override all votes — log reason, log to agent_disagreement_log
Final confidence < 65%	REJECTED	Automatic — never approved below threshold
Risk:Reward < 2.0	REJECTED	Automatic — never approved below threshold
Correlated active position exists	REJECTED	Shared 2% risk budget would be exceeded
VIX > 25	RESTRICTED	Only hedged strategies — all directional signals rejected
VIX > 30	HALTED	System enters capital protection mode — no new signals
Portfolio dropped 5% today	EMERGENCY HALT	Manual review required before system resumes

4.3 Error Taxonomy — What the System Learns From Each Wrong Signal
Without this taxonomy, the system learns the wrong lesson from correct signals that failed for external reasons. A correct signal in a black swan is NOT a signal error — do not reduce signal confidence because of it.
Error Type	Definition	System Learning Response
Signal Error	Setup was technically correct but market did not follow through	Reduce this pattern's weight in Pattern Memory DB
Timing Error	Correct direction but entry was too early or too late	Refine entry timing rules for this specific pattern
Regime Error	Strategy valid in normal VIX but failed in high VIX	Add VIX bucket filter to this strategy's conditions
Data Error	Signal based on incorrect, delayed, or corrupted data	Flag data source for quality review — do not penalize signal
Market Anomaly	Black swan, completely unpredictable external event	Log as anomaly — do NOT adjust strategy weights at all
Execution Error	Signal was correct but execution logic failed (paper trade bug)	Fix execution code only — do not penalize signal quality
Correlation Error	Multiple correlated positions amplified loss beyond expected	Strengthen correlation checker, reduce combined exposure rules

4.4 Agent Exact Prompt Templates
These are the exact system prompts for each agent. Give these to your AI developer as the system_prompt string in each agent file. The output JSON format is mandatory — never accept free-text output from agents.
Bull Agent System Prompt
You are The Bull, ArthAI's Technical Analysis Agent. You analyze market data to find bullish setups. You are disciplined and evidence-based. You have access to: RSI, MACD, EMA stack, ATR, Supertrend, ADX, Bollinger Bands, volume, delivery %, candlestick patterns, S/R levels, multi-timeframe data, and Pattern Memory DB historical stats. Rules: (1) Reduce confidence by 15% if VIX > 20. (2) Reduce confidence by 8% if price is more than 3% above 20 EMA. (3) Always cite the Pattern Memory DB historical win rate in your reasoning. Output ONLY this exact JSON: {"verdict": "STRONG_BUY|BUY|NEUTRAL|SELL", "confidence": 0-100, "key_reasons": ["r1","r2","r3"], "regime_note": "VIX impact on confidence", "pattern_history": "exact stats from Pattern Memory DB or null if no match"}
Bear Agent System Prompt
You are The Bear, ArthAI's Fundamental and Sentiment Agent. Rules: (1) If promoter pledge > 70% of total promoter holding, output BEARISH regardless of other data. (2) If legal insider buy by CFO or MD in last 30 days, add 20% to bullish confidence. (3) FinBERT sentiment score > 0.6 = BULLISH input, < -0.6 = BEARISH input. Output ONLY this exact JSON: {"verdict": "BEARISH|CAUTION|NEUTRAL|BULLISH", "confidence": 0-100, "key_reasons": ["r1","r2","r3"], "red_flags": ["any serious concerns or empty list"], "insider_activity": "description or null"}
Economist Agent System Prompt
You are The Economist, ArthAI's Macro Agent. Rules: (1) If MPC decision within 2 trading days, reduce all directional confidence by 20% and list as event_risk. (2) If FOMC within 2 trading days, reduce by 10%. (3) If RBI has conducted VRR (injection) for 5+ consecutive days, bias toward BULLISH for rate-sensitive sectors. (4) If 10-year G-Sec yield rose > 20bps this week, add FII selling risk to event_risks. Output ONLY this exact JSON: {"verdict": "BULLISH|NEUTRAL|BEARISH", "confidence": 0-100, "macro_regime": "BULL_CYCLE|LATE_CYCLE|BEAR_CYCLE|RECOVERY", "key_reasons": ["r1","r2"], "event_risks": ["list or empty"], "rbi_bias": "current RBI posture interpretation"}
Devil Agent System Prompt
You are The Devil's Advocate. Your ONLY job is to find every reason this trade will FAIL. You receive all three agent verdicts, the full signal setup, and Pattern Memory DB stats. Attempt to break by finding: (1) historical evidence this setup has low win rate in current conditions, (2) data quality issues, (3) liquidity risks, (4) upcoming events that could gap beyond stop loss, (5) correlation with existing portfolio, (6) contradictions between agents. If no strong reason found, output FAILED_TO_BREAK. VETO POWER: BROKE_SIGNAL rejects the trade regardless of all other votes. Output ONLY this exact JSON: {"verdict": "FAILED_TO_BREAK|BROKE_SIGNAL", "confidence": 0-100, "break_reason": "specific reason or null", "historical_evidence": "exact pattern stats", "stress_points": ["list"], "correlation_risk": "description or none"}
 
SECTION 5: SIGNAL ENGINE — COMPLETE LOGIC AND FILTERS
5.1 Signal Generation Pipeline — Step by Step
1.	Market scanner runs every 15 minutes from 9:15 AM to 3:30 PM on weekdays
2.	Universe: NSE 500 + all F&O instruments + all MCX contracts + currency pairs + top 50 crypto
3.	Data quality filter: remove instruments with quality score < 85% for that session
4.	Technical pre-filter: must pass minimum 3 of 5 technical conditions (speed optimization)
5.	Liquidity filter: remove instruments with bid-ask spread > 0.2% or insufficient OI depth
6.	Volatility regime classification: tag each candidate with current VIX bucket
7.	Time-of-day filter: apply quality rating for current session window (9:15-9:30 AM excluded)
8.	Correlation checker: reject if active or pending signal exists in correlated instrument
9.	4-agent debate room fires for each candidate passing all above filters
10.	Devil Agent queries Pattern Memory DB and runs correlation, liquidity, and gap risk checks
11.	Supervisor collects 4 verdicts, applies adaptive weights, calculates final_confidence ± interval
12.	Risk management check: position size fits within remaining daily risk budget
13.	If all checks pass: signal approved → Telegram + Discord + Dashboard + logged to DB + Pattern Memory updated
14.	Priority queue: if > 4 signals approve simultaneously, top 4 by confidence × R:R score survive
15.	All rejected signals logged with rejection reason — none are wasted, all feed Pattern Memory DB

5.2 All Signal Engine Files — Priority and Status
•	[P0] signal_correlation_checker.py — MOST CRITICAL missing file
•	[P0] volatility_regime_classifier.py — VIX bucket confidence adjustments
•	[P0] time_of_day_filter.py — 7 session windows with quality ratings
•	[P0] signal_circuit_breaker.py — 3 losses = 50% size, 5 losses = pause
•	[P0] signal_priority_queue.py — selects best 4 when > 4 fire simultaneously
•	[P0] flash_crash_detector.py — Nifty drops 2%+ in 5 min = halt all intraday
•	[P0] signal_staleness_decay.py — decay curve: 100%→95%→85%→70%→expired at 20 min
•	[P1] signal_correlation_log — DB table for all rejected correlated signals

5.3 Signal Correlation Logic — Exact Rules
Instrument Pair	Correlation Coefficient	Rule
Nifty + BankNifty	0.85-0.92	Reject — combined exposure = 1 position, not 2
Two IT stocks (same sector)	> 0.80	Reject — shared 2% risk budget, not each gets 2%
Gold MCX + Gold ETF	0.95+	Reject — same underlying, different instrument
USD/INR futures + US stock ETF	0.60-0.75	Flag — same directional FX exposure, reduce combined size
BankNifty + individual bank stock in Nifty	0.70-0.85	Reduce — partial overlap, allow at 0.75× size
Nifty + Gold	−0.20 to −0.40	Allow — negatively correlated, actually reduces portfolio risk
Gold + Silver MCX	0.80-0.90	Flag — similar precious metals, check combined exposure

5.4 Time-of-Day Filter
Time Window	Session Quality	Action	Rationale
9:15 AM – 9:30 AM	Very Low — EXCLUDED	No new entries allowed	Opening volatility is noise — institutions are still placing opening orders
9:30 AM – 10:30 AM	High	Full signal generation — best window	Institutional orders placed, trend established for the day
10:30 AM – 12:00 PM	Medium-High	Normal signal generation	Trend confirmed, good risk-reward environment
12:00 PM – 2:00 PM	Medium	Signal generation with caution	Lunch hour, liquidity can thin, choppy possible
2:00 PM – 3:00 PM	High	Good window	Pre-close institutional activity, strong directional moves
3:00 PM – 3:15 PM	Very Low — EXCLUDED	No new intraday entries	Too close to close, insufficient time to manage
3:15 PM onwards	None	Intraday must close — no new entries	All intraday positions must close by 3:30 PM regardless of P&L

5.5 VIX Regime Classifier
VIX Level	Regime Name	Confidence Adjustment	Allowed Strategies	Position Size
Below 14	CALM	+8% bonus for momentum signals	All strategies allowed — ideal conditions	Full size
14 to 20	NORMAL	No adjustment — base confidence	All strategies allowed	Full size
20 to 25	ELEVATED	−10% penalty on all signals	No naked options selling	0.75× size
25 to 30	FEAR	−20% penalty, only hedged	Only hedged strategies — no directional	0.5× size
Above 30	CRISIS	System pauses new signals	Capital protection mode only	No new positions
 
SECTION 6: RISK MANAGEMENT — COMPLETE SYSTEM
6.1 Dynamic Position Sizing
Confidence Level	Position Size Factor	Capital at Risk	Rationale
65-70%	0.5×	0.75% of capital	Low conviction — signal passes minimum but not strong
70-80%	0.75×	1.5% of capital	Standard signal — normal allocation
80-90%	1.0×	2.0% of capital	Strong signal — full standard allocation
90%+	1.25×	2.5% of capital	Exceptional signal — rare, maximum allowed
After 2 consecutive losses	0.5× of normal	Automatic protection	Prevent losing streak from compounding
After 3 consecutive losses	0.25× of normal	Severe reduction	Circuit breaker territory — review required
Correlated signals	Combined max 2%	Shared budget — not additive	BankNifty + Nifty together cannot exceed 2% total risk

6.2 Stop Loss Rules
•	ATR Stop: SL = Entry Price − (2.0 × ATR14) for longs; Entry + (2.0 × ATR14) for shorts
•	S/R Stop: placed just below nearest significant support (for longs)
•	Capital Stop: maximum 2% of portfolio at risk — whichever of above is tighter wins
•	GOLDEN RULE: Never override stop loss once set — this is constitutional law, not preference
•	Trailing Stop at 1R profit: move SL to breakeven — converts possible loser to breakeven
•	Trailing Stop at 1.5R profit: trail at 0.5R behind price — lets winners run
•	Time Stop: all intraday positions MUST close by 3:15 PM regardless of P&L

6.3 Portfolio-Level Risk Monitors
Risk Monitor	Threshold	Alert	File
Portfolio Delta (F&O)	Net delta > 3 Nifty lots equivalent	Telegram alert + dashboard badge	portfolio_greeks_aggregator.py
Portfolio Vega	Net vega creates > 5% swing on 5-point IV move	Reduce F&O exposure alert	portfolio_greeks_aggregator.py
Single stock concentration	Any position > 10% of portfolio	Alert at 8%, hard cap at 10%	concentration_limit_checker.py
Sector concentration	Any sector > 25% of portfolio	Alert at 20%, flag at 25%	sector_concentration_monitor.py
Margin utilization	F&O margin > 50% of total capital	Alert user, pause new F&O signals	margin_utilization_tracker.py
Currency exposure	USD exposure > 30% of portfolio	Alert — combine IT stocks + USD/INR + US ETFs	currency_exposure_aggregator.py
Daily portfolio drop	3% in one day	Alert + reduce new position sizes 50%	signal_circuit_breaker.py
Daily portfolio drop	5% in one day	EMERGENCY HALT — manual review required	signal_circuit_breaker.py

6.4 Black Swan and Emergency Protocols
Trigger	Protocol	File
Nifty drops 2%+ in 5 minutes	Flash crash — halt ALL new intraday entries immediately	flash_crash_detector.py
NSE circuit breaker Level 1 (10%)	Detect halt, pause all activity, alert user, wait for resumption	market_halt_handler.py
VIX crosses 25 intraday	Switch to FEAR regime — only hedged strategies allowed	volatility_regime_classifier.py
VIX crosses 30	CRISIS mode — no new signals, capital protection, urgent alert	liquidity_crisis_mode.py
3 consecutive signal losses	Reduce all sizes by 50%, send Telegram alert, log to circuit_breaker_log	signal_circuit_breaker.py
5 consecutive signal losses	Full pause — no new signals until manual confirmation next day	signal_circuit_breaker.py
Portfolio drops 3% in one day	Reduce sizes 50%, alert user, require confirmation to continue	signal_circuit_breaker.py
Portfolio drops 5% in one day	EMERGENCY HALT — no new signals, mandatory review before resume	signal_circuit_breaker.py
 
SECTION 7: COMPLETE ASSET CLASS COVERAGE
7.1 MCX Commodities — Complete with Data Sources
CRITICAL: AngelOne SmartAPI does NOT reliably serve MCX data. The primary MCX data source is Shoonya API (Finvasia). Authentication: Register at finvasia.com, complete KYC, use TOTP-based login. WebSocket endpoint: wss://api.shoonya.com/NorenWSTP/. All MCX instruments use the symbol format: MCX|{TOKEN_ID}. Token IDs available via API call to get_master.

MCX Data Authentication Flow — Step by Step
16.	Register at finvasia.com, complete KYC, get API key and client ID
17.	Enable TOTP 2FA — save the TOTP secret key in .env as SHOONYA_TOTP_SECRET
18.	Login API call: POST to https://api.shoonya.com/NorenWClientTP/QuickAuth with TOTP token
19.	Store session token (susertoken) returned — expires daily, must refresh each morning
20.	WebSocket connect: wss://api.shoonya.com/NorenWSTP/ with session token in connect message
21.	Subscribe to MCX instruments using token IDs from get_master call
22.	Fallback: Upstox API also covers MCX — use as secondary source if Shoonya fails

  PRECIOUS METALS  
Contract	Lot Size	Margin (Approx)	Strategy File	Key Signal Source
Gold (1 kg)	1 kg	Rs 40,000-50,000	gold_contracts_engine.py	DXY inverse, USD/INR, global safe haven flows
Gold Mini (100g)	100g	Rs 4,000-5,000	gold_contracts_engine.py	Same as Gold — lower entry barrier
Gold Guinea (8g)	8g	Rs 350-450	gold_contracts_engine.py	Festival season demand (Diwali, Akshaya Tritiya)
Gold Petal (1g)	1g	Rs 45-55	gold_contracts_engine.py	Retail gifting season plays — smallest possible bet
Silver (30 kg)	30 kg	Rs 60,000-80,000	silver_contracts_engine.py	Industrial demand + safe haven dual driver
Silver Mini (5 kg)	5 kg	Rs 10,000-13,000	silver_contracts_engine.py	More accessible, same signals as Silver
Silver Micro (1 kg)	1 kg	Rs 2,000-2,600	silver_contracts_engine.py	Entry-level silver trading
Platinum (200g)	200g	Variable	platinum_engine.py	Auto sector, EV transition, industrial demand
Palladium (100g)	100g	Variable	platinum_engine.py	Auto catalysts, South Africa supply concentration
•	Gold-Silver Ratio Engine (gold_silver_ratio_engine.py): Ratio > 80 → Silver cheap relative to Gold → long Silver. Ratio < 60 → Gold cheap → long Gold
•	COMEX-MCX Spread (comex_mcx_spread.py): When MCX price deviates from COMEX × INR/USD × import duty by > 0.5%, arbitrage signal
•	MCX Commodity Options (commodity_options_engine.py): Gold and Silver options now live on MCX — IV Rank applies same as equity options
•	LME Connector (lme_connector.py): London Metal Exchange reference prices via Quandl/Nasdaq Data Link API (free tier available)

  BASE METALS  
Contract	Variants	Key Macro Driver	SHFE Correlation	File
Copper	Regular + Mini	China PMI, global construction, EV demand	0.85+ — Copper follows Shanghai closely	base_metals_engine.py
Zinc	Regular + Mini	Galvanizing demand, infrastructure spending	0.75	base_metals_engine.py
Lead	Regular + Mini	Battery demand, auto sector	0.70	base_metals_engine.py
Aluminium	Regular + Mini	Power cost (energy-intensive), packaging, auto	0.65	base_metals_engine.py
Nickel	Regular + Mini	Stainless steel, EV batteries (key driver)	0.80	base_metals_engine.py
Brass	MCX listed only	Plumbing, electrical fittings, construction	N/A	base_metals_engine.py
Steel Long	MCX listed only	Infrastructure, construction, real estate	0.60	base_metals_engine.py
•	SHFE Correlation (shfe_correlation.py): China Caixin PMI release moves MCX base metals 0.5-2% — track monthly PMI dates in economic calendar
•	LME 3-month vs MCX spot: when divergence > import parity threshold, flag arbitrage opportunity

  ENERGY  
Contract	Lot Size	Key Driver	File
Crude Oil (100 bbl)	100 barrels	OPEC decisions, EIA inventory, geopolitics, DXY	energy_engine.py
Crude Oil Mini (10 bbl)	10 barrels	Same as Crude — lower entry barrier	energy_engine.py
Natural Gas (1250 mmBtu)	1250 mmBtu	US weather, Henry Hub storage, LNG export demand	energy_engine.py
Natural Gas Mini (250 mmBtu)	250 mmBtu	Same as NG — lower entry barrier	energy_engine.py
•	OPEC Meeting Calendar: major supply decisions move crude 3-8% — Economist Agent must flag OPEC meeting within 5 days as binary event risk
•	EIA Weekly Inventory Report: every Wednesday 9 PM IST — US crude inventory change moves price 1-3%
•	Brent-WTI Spread (brent_wti_spread in energy_engine.py): when spread abnormally wide/narrow vs 6-month average, mean reversion trade
•	Rupee-Crude Correlation: rising crude weakens INR, negative for overall market — Economist Agent tracks this

  NCDEX AGRI — CRITICAL: DATA SOURCE RESOLUTION  
Neither v3.0 nor v4.0 resolved NCDEX data. Resolution: Primary source = TickerPlant (tickerplant.com) — provides NCDEX real-time and EOD data with documented API. Authentication: contact sales@tickerplant.com for API credentials. Fallback = NCDEX website scraper for EOD data only. For real-time during market hours, TickerPlant is the only practical solution. Budget: approximately Rs 3,000-8,000/month depending on tier.
Commodity	Season	Key Driver	Signal Strength
Castor Seed (10 MT)	Rabi (Feb-Mar harvest)	Export demand for castor oil, Gujarat production	HIGH — most liquid NCDEX contract
Turmeric (100 kg)	Rabi (Jan-Feb)	Domestic consumption, pharma demand, monsoon	HIGH — very seasonal, predictable patterns
Jeera/Cumin (100 kg)	Rabi (Mar)	Export demand (largest exporter globally), Gujarat	HIGH — export policy driven
Coriander (100 kg)	Rabi (Feb-Mar)	Domestic demand, restaurant sector	MEDIUM
Chana/Chickpea (100 MT)	Rabi (Mar-Apr)	Government MSP, import duty changes	HIGH — very policy driven
Soybean (100 MT)	Kharif (Oct-Nov)	Edible oil demand, global crush margins, palm oil price	HIGH — global linkage
Guar Seed (10 MT)	Kharif (Oct)	Oil drilling guar gum demand, monsoon rainfall	MEDIUM-HIGH — US oil rig count matters
Mentha Oil (360 kg)	Summer (Jun-Jul)	Pharmaceutical demand, UP production	MEDIUM
Cotton (55 bales = 165 kg)	Kharif (Nov)	MSP, global prices, textile demand, import duty	HIGH — heavily policy driven
Crude Palm Oil (10 MT)	Year-round (imported)	Malaysia/Indonesia CPO prices, import duty changes	HIGH — global price follower
Rubber (100 kg)	Year-round	Auto sector demand, global supply (Thailand/Malaysia)	MEDIUM
•	Monsoon Tracker (monsoon_tracker.py): IMD data from imdpune.gov.in — weekly rainfall vs normal, cumulative deficit/surplus. Free access via IMD website scraper. API: data.imd.gov.in (registration required, free for research)
•	MSP Tracker (msp_tracker.py): Cabinet Committee on Economic Affairs announces MSPs — scrape pib.gov.in for press releases. MSP changes set price floors and drive seasonal signals
•	Export/Import Policy Tracker: agri.pib.gov.in and dgft.gov.in — agri commodities heavily affected by sudden export bans and import duty changes

7.2 Equity Markets
•	Universe: NSE 500 + BSE 500 (deduplicated) = approximately 600 unique instruments
•	F&O stocks: top 200 by OI liquidity — separate liquidity threshold for options vs futures
•	Sector indices: Bank, IT, Auto, Pharma, FMCG, Metal, Energy, Realty, Media — separate signal tracks
•	Key equity-specific signal: Delivery % > 60% on rally = real accumulation by institutions
•	Key equity-specific signal: Legal insider buy by CFO/MD = strongest single fundamental signal
•	Key equity-specific signal: Promoter holding increasing 3+ consecutive quarters = long-term buy

7.3 F&O — Options Strategies with Exact Conditions
Strategy	When to Use	IV Rank Requirement	Risk Profile
Bull Call Spread	Moderately bullish, defined risk needed	Any — IV Rank not critical	Limited risk and reward
Bear Put Spread	Moderately bearish, defined risk needed	Any	Limited risk and reward
Iron Condor	Sideways market expected, want to sell premium	IV Rank > 50 — selling expensive premium	Max profit in range, loss outside
Iron Butterfly	Strongly sideways, higher premium than condor	IV Rank > 60	Tighter range, higher premium
Long Straddle	Big move expected, direction unknown	IV Rank < 30 — buying cheap volatility	Unlimited profit, defined loss
Long Strangle	Big move expected, cheaper than straddle	IV Rank < 30	Same as straddle, wider strikes
Covered Call	Neutral on existing holding, want income	IV Rank > 40	Cap upside, collect premium
Cash Secured Put	Bullish, willing to buy the stock	IV Rank > 40	Collect premium, risk of assignment
Calendar Spread	Neutral short-term, bullish long-term	Near low, far moderate	Theta play — profit from time decay
Ratio Spread	Directional with hedge	IV Rank > 50	Complex — sell more than buy

7.4 Fixed Income
Instrument	Yield Range	Tax Treatment	ArthAI Signal Logic
10-Year G-Sec	6.5-7.5%	Interest at slab rate	Yield rising 20bps/week = equity caution signal
Sovereign Gold Bonds	Gold return + 2.5%	Capital gain tax-FREE on RBI maturity	Track SGB vs physical gold discount/premium on NSE
54EC Bonds (NHAI/REC)	5.0-5.5%	LTCG exempt on qualifying property gain	Track availability — 6-month window after property sale
Tax-Free Bonds	5.0-6.0%	Interest completely tax-free	Compare post-tax yield vs FD for user's tax bracket
Corporate Bonds (AAA)	7.5-8.5%	Interest at slab rate	Credit spread vs G-Sec — widening signals distress

7.5 Mutual Funds — Key Intelligence Features
•	Fund Overlap Analyzer: % common stocks between two MFs — above 50% overlap = not diversifying
•	Direct vs Regular cost drag: show commission in exact rupees over 10/20 years — not just TER%
•	Tax impact pre-redemption: show exact STCG/LTCG calculation BEFORE user confirms redeem
•	ELSS lock-in per unit: each SIP installment has its own 3-year lock-in — track individually by purchase date
•	Manager change alert: fund performance often drops after key manager leaves — flag immediately
•	Rolling returns: show 3-year, 5-year, 7-year rolling returns — not just point-to-point
•	Goal-to-SIP: "I want Rs 1 crore in 10 years at 12% expected return → invest Rs 43,472/month"

7.6 Cryptocurrency
•	Tax (VDA): 30% flat tax on ALL gains, 1% TDS on sell value, NO set-off allowed against any other income or loss
•	On-chain signals: whale wallet movements (Glassnode, CryptoQuant), exchange inflows/outflows
•	Funding rate: negative funding rate = shorts paying longs = institutional bullish position
•	Fear & Greed Index (Crypto): Alternative.me API — extreme fear below 20 = potential buy zone
•	Liquidation heatmap (Coinglass): where leveraged positions will be forcibly closed
 
SECTION 8: COMPLETE TAX ENGINE
8.1 Tax Framework — All Rates and Rules
Instrument	STCG Rate	LTCG Rate	Holding Threshold	Special Rule
Listed Equity Shares	20% (post Jul 2024)	12.5% above Rs 1.25L exempt	12 months	First Rs 1.25L LTCG per year: zero tax
Equity Mutual Funds	20%	12.5% above Rs 1.25L exempt	12 months	Same as listed equity
Debt Mutual Funds	Slab rate (up to 30%)	Slab rate (indexation removed post Apr 2023)	24 months	No indexation benefit anymore
Sovereign Gold Bonds	Slab rate	Tax FREE on RBI maturity redemption	8 years to maturity	Tax-free only on RBI maturity — secondary market sale taxed
Gold ETF / Physical Gold	Slab rate	Slab rate (indexation removed)	24 months	No indexation benefit
F&O (all)	Business income — slab rate	Not applicable (always business income)	N/A	Expenses (brokerage, advisory fees) deductible against F&O income
Crypto / VDA	30% flat — NO DEDUCTION except cost	30% flat — same rate	N/A — no long-term benefit	No set-off of VDA loss against any income
US Stocks / Int'l MF (post Apr 2023)	Slab rate	Slab rate	24 months	Currency gain also taxable
REITs / InvITs (distribution)	Per distribution type	Per distribution type	12 months equity portion	Complex — dividend, interest, capital return all taxed differently

8.2 All Transaction Costs — Exact Rates for P&L Calculation
Cost	Delivery Buy	Delivery Sell	Intraday	F&O Options Sell	F&O Futures Sell	MCX
STT	0%	0.1% of turnover	0.025% of sell	0.0625% of premium	0.0125% of sell	0% (CTT applies)
CTT	N/A	N/A	N/A	N/A	N/A	0.01% non-agri sell side
Stamp Duty	0.003% buy	0%	0.003% buy	0.003% buy	0.002% buy	0.002% buy
Exchange Charge (NSE)	0.00297%	0.00297%	0.00297%	0.05% premium	0.002%	MCX specific
SEBI Charge	0.0001%	0.0001%	0.0001%	0.0001%	0.0001%	0.0001%
Brokerage	Rs 20 flat	Rs 20 flat	Rs 20 flat	Rs 20 flat	Rs 20 flat	Rs 20 flat
GST on Brokerage	18% of Rs 20	18% of Rs 20	18% of Rs 20	18% of Rs 20	18% of Rs 20	18% of Rs 20
Slippage (estimate)	0.05%	0.05%	0.05-0.10%	0.5-1% on premium	0.05%	0.05-0.10%

8.3 All Tax Files
•	[P0] fifo_lot_tracker.py — FIFO buy/sell matching, holding period, cost basis per lot
•	[P0] stcg_ltcg_calculator.py — classify gains: STCG 20%, LTCG 12.5%, debt at slab
•	[P0] stt_ctt_calculator.py — all costs per trade type, applied in paper trading and reporting
•	[P0] vda_tax_tracker.py — crypto 30% flat, 1% TDS tracking, no set-off
•	[P1] tax_regime_comparator.py — exact tax under new vs old regime, recommendation
•	[P1] advance_tax_calculator.py — quarterly installments: 15% by Jun 15, 45% by Sep 15, 75% by Dec 15, 100% by Mar 15
•	[P1] tax_loss_harvester.py — identify candidates before March 31 deadline
•	[P1] form_26as_reconciler.py — broker P&L vs 26AS TDS credit matching
•	[P1] elss_lockin_tracker.py — each installment has own 3-year lock-in start date
•	[P1] tds_tracker.py — TDS on FD interest, debt MF, bonds — reconcile with 26AS
•	[P2] annual_tax_report.py — exportable PDF for CA/ITR filing
•	[P2] tax_arbitrage_advisor.py — legal optimization: LTCG harvesting, HUF, family gifting
 
SECTION 9: COMPLETE DATABASE SCHEMA
CRITICAL DATABASE STANDARDS (apply to ALL tables without exception): (1) instrument_key is the universal identifier across NSE/BSE/MCX/NCDEX — format: EXCHANGE:SYMBOL e.g. NSE:RELIANCE, MCX:GOLD24DECFUT. (2) Every table has: id UUID PRIMARY KEY, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ, is_deleted BOOLEAN DEFAULT FALSE. (3) is_deleted enables soft delete — never hard delete records. (4) Indexes: all tables indexed on created_at. Query-specific indexes listed per table.

9.1 Core Trading Tables
Table	Key Columns	Indexes	Purpose
signals	id, instrument_key, asset_class ENUM, direction, entry, sl, target, confidence, confidence_interval, iv_rank, vix_at_signal, fii_flow, regime, agent_votes JSONB, pattern_history JSONB, outcome ENUM, error_type ENUM, created_at, closed_at	(created_at, asset_class), (instrument_key, created_at)	All generated signals and their outcomes
paper_trades	id, signal_id FK, instrument_key, direction, entry_price, exit_price, quantity, lots, stt, brokerage, gst, stamp, exchange_charge, slippage, gross_pnl, net_pnl, created_at	(created_at), (signal_id)	Paper trading with ALL costs applied realistically
portfolio	id, instrument_key, asset_class, quantity, avg_cost, tax_lot_id FK, current_price, current_value, unrealized_pnl, pledge_status, created_at	(instrument_key), (asset_class)	Real and paper portfolio holdings
tax_lots	id, instrument_key, buy_date, buy_price, quantity, lot_type ENUM, sold_quantity, sell_date, sell_price, holding_days, gain_loss, stcg_ltcg ENUM, stt_paid, created_at	(instrument_key, buy_date), (stcg_ltcg)	FIFO tax lot tracking — mandatory for correct capital gains
pattern_memory	id, instrument_key, asset_class, setup_fingerprint JSONB, market_context JSONB, agent_votes JSONB, final_confidence, entry, sl, target, rr_ratio, outcome ENUM, actual_pnl, pnl_after_costs, error_type ENUM, vix_at_signal, fii_flow, regime, vix_bucket, created_at, closed_at	(instrument_key, asset_class), (vix_bucket, regime), (outcome)	Pattern Memory Database — Devil Agent queries, learning system writes
agent_performance	id, agent_name, asset_class, regime, vix_bucket, votes_cast, votes_correct, accuracy FLOAT, current_weight FLOAT, last_calibrated, created_at	(agent_name, asset_class, regime)	Per-agent accuracy tracking for adaptive weight adjustment
agent_disagreement_log	id, signal_id FK, instrument_key, split_type ENUM (2-2, VETO), bull_vote, bear_vote, economist_vote, devil_vote, devil_reason, outcome ENUM, created_at	(created_at), (split_type)	Logs all 2-2 splits and Devil vetoes with outcomes — critical for learning
data_lineage_log	id, signal_id FK, instrument_key, data_source, data_timestamp, data_quality_score, data_type, value_snapshot JSONB, created_at	(signal_id), (instrument_key)	For every signal: exactly which data from which source at what time
signal_correlation_log	id, signal_id FK, rejected_instrument_key, active_instrument_key, correlation_coefficient, rejection_reason, created_at	(created_at)	All signals rejected due to correlation — feeds learning system

9.2 Asset-Specific Tables
Table	Key Columns	Purpose
mcx_instruments	instrument_key, symbol, name, lot_size, tick_size, margin_initial, margin_maintenance, expiry_date, contract_type ENUM (REGULAR/MINI/MICRO), commodity_type ENUM	All MCX contracts with specifications
mcx_ohlc	id, instrument_key, timestamp, open, high, low, close, volume, oi, created_at	MCX commodity OHLC + volume + OI history
ncdex_instruments	instrument_key, symbol, name, lot_size, tick_size, expiry_date, commodity_type, msp_price, season	NCDEX contract specifications + MSP data
iv_history	id, instrument_key, expiry_date, strike, option_type ENUM, iv, timestamp, created_at	Historical implied volatility per instrument per expiry per strike
iv_rank_log	id, instrument_key, iv_current, iv_52w_high, iv_52w_low, iv_rank, iv_percentile, snapshot_date	Daily IV Rank snapshot per instrument
options_flow	id, instrument_key, expiry_date, strike, option_type, volume, avg_20d_volume, volume_ratio, lot_size, estimated_notional, flow_type ENUM, created_at	Unusual options activity log
max_pain_log	id, instrument_key, expiry_date, max_pain_strike, total_oi_at_pain, snapshot_time, created_at	Max pain per expiry, logged pre-market each expiry week
portfolio_greeks	id, net_delta, net_gamma, net_theta, net_vega, net_delta_rs, positions_snapshot JSONB, snapshot_time, created_at	Aggregated F&O Greeks across all positions — EOD snapshot + intraday on demand
fii_derivative_positions	id, net_futures_contracts, net_options_contracts, net_combined, index_name, data_date, created_at	FII net long/short in index futures — daily from SEBI
fundamental_history	id, instrument_key, period_type ENUM, period_date, pe, pb, ps, ev_ebitda, roe, roce, roa, debt_equity, current_ratio, operating_margin, net_margin, ocf, fcf, revenue, pat, created_at	10-year annual + quarterly financial data per stock
concall_transcripts	id, instrument_key, call_date, quarter, raw_text, sentiment_score, key_phrases JSONB, management_tone ENUM, guidance_tone ENUM, red_flags JSONB, created_at	Raw and NLP-processed earnings call content
backtest_cost_assumptions	id, asset_class, instrument_type, stt_buy_pct, stt_sell_pct, ctt_pct, stamp_pct, exchange_charge_pct, brokerage_flat, gst_on_brokerage_pct, slippage_pct, market_impact_pct, version, created_at	Cost assumptions used in each backtest run — versioned for reproducibility
liquidity_scores	id, instrument_key, avg_bid_ask_spread, avg_daily_volume, avg_daily_oi, impact_cost, liquidity_grade ENUM (A/B/C/D), score_date, created_at	Daily per-instrument liquidity quality score
screener_formulas	id, user_id FK, formula_name, formula_text, asset_class, last_run, result_count, is_public, created_at	User-saved custom screening formulas
thematic_baskets	id, basket_name, theme, rationale, created_by, is_public, created_at	AI-curated stock baskets with rationale
basket_holdings	id, basket_id FK, instrument_key, weight_pct, added_date, removed_date, created_at	Individual stocks in each thematic basket
mf_overlap_matrix	id, fund_a_key, fund_b_key, overlap_pct, common_stocks JSONB, computed_date, created_at	Pre-computed fund overlap percentages
crypto_tax_lots	id, instrument_key (VDA symbol), buy_date, buy_price_inr, quantity, sold_quantity, sell_date, sell_price_inr, gain_loss, tds_deducted, created_at	VDA-specific FIFO lots — 30% flat rate, no set-off
sgb_holdings	id, series_name, units, issue_price, maturity_date, interest_rate, current_market_price, redemption_type ENUM, created_at	Sovereign Gold Bond holdings tracking
goals	id, user_id FK, goal_name, goal_type ENUM, target_amount, target_date, monthly_sip, current_corpus, inflation_rate, expected_return, progress_pct, created_at	User financial goals with progress tracking
insurance_policies	id, user_id FK, policy_type ENUM, insurer, sum_assured, annual_premium, policy_start, policy_end, premium_due_date, claim_settlement_ratio, created_at	User insurance policy register
estate_documents	id, user_id FK, document_type ENUM, institution_name, account_reference, nominee_name, nominee_relation, notes_encrypted, created_at	Encrypted digital asset register for estate planning
rbi_policy_decisions	id, mpc_date, decision ENUM (HOLD/CUT/HIKE), rate_before, rate_after, stance, nifty_reaction_pct, banknifty_reaction_pct, created_at	MPC decisions with market reaction for Economist Agent learning
 
SECTION 10: COMPLETE CALCULATION LIBRARY — EXACT FORMULAS
10.1 Technical Indicator Formulas
Indicator	Exact Formula	ArthAI Use
RSI (14)	RS = EMA(14) of Up Closes / EMA(14) of Down Closes; RSI = 100 − (100/(1+RS))	55-70 = bullish momentum without overbought
MACD	MACD Line = EMA(12) − EMA(26); Signal = EMA(9) of MACD; Histogram = MACD − Signal	Histogram turning positive + line crossing = entry
ATR (14)	TR = max(H−L, |H−PrevC|, |L−PrevC|); ATR = EMA(TR, 14)	Stop loss: SL = Entry − 2×ATR (long) or Entry + 2×ATR (short)
Supertrend	Upper = (H+L)/2 + 3×ATR; Lower = (H+L)/2 − 3×ATR; direction = close vs active band	Flip to BUY = trend change confirmed
ADX	DM+ = H − PrevH (if > 0); DM− = PrevL − L (if > 0); ADX = EMA(|DI+ − DI−|/(DI++DI−)) × 100	> 25 = strong trend worth trading
VWAP	VWAP = Σ(Typical Price × Volume) / Σ(Volume); Typical = (H+L+C)/3; resets daily at open	Institutional benchmark — price above VWAP = buyers in control
OBV	If C > PrevC: OBV += Volume; If C < PrevC: OBV −= Volume; else OBV unchanged	Rising OBV while price flat = institutional accumulation signal
BB Squeeze	BB Width = (Upper − Lower) / Middle; Squeeze = Width at historical low	Low width → expansion = momentum signal
Fibonacci Levels	Levels = High − (High − Low) × ratio; ratios: 0.236, 0.382, 0.500, 0.618, 0.786	61.8% level = highest probability reversal zone

10.2 Options Calculations
Calculation	Exact Formula	Inputs Needed
IV Rank	(Current IV − 52W Low IV) / (52W High IV − 52W Low IV) × 100	1 year of daily IV history per instrument
IV Percentile	Count(days where daily IV < Current IV in last 252 days) / 252 × 100	252 days of daily IV snapshots
Max Pain	For each strike K: Pain(K) = Σ[Call OI × max(0, K − C_Strike)] + Σ[Put OI × max(0, P_Strike − K)]; Max Pain = argmin(Pain)	Full options chain OI across all strikes
Expected Move	±Straddle = ATM Call Price + ATM Put Price; EM% = ±(Straddle / Spot) × 100	ATM call price, ATM put price, spot price
GEX	GEX = Σ[(Call OI − Put OI) × Gamma × Spot² × 0.01] summed across all strikes	Full chain OI + computed option Gamma per strike
Black-Scholes Delta	d1 = [ln(S/K) + (r + σ²/2)t] / (σ√t); Delta_call = N(d1); Delta_put = N(d1) − 1	Spot S, Strike K, Rate r, Volatility σ, Time t
Theta (per day)	Theta = −[S×N'(d1)×σ / (2√t)] − r×K×e^(−rt)×N(d2); divide by 365 for daily	Same Black-Scholes inputs
Iron Condor Max Profit	Net Credit = (Higher Put Premium − Lower Put Premium) + (Higher Call Premium − Lower Call Premium)	All 4 leg premiums
Iron Condor Max Loss	(Strike Width − Net Credit) × Lot Size	Spread width between strikes + net credit
Break-Even (Long Call)	Strike + Premium Paid	Strike price, premium paid per share
Break-Even (Long Straddle)	Upper BE = Strike + Total Premium; Lower BE = Strike − Total Premium	ATM strike, total straddle premium

10.3 Risk Management Formulas
Calculation	Formula	When ArthAI Uses It
Position Lots	Lots = (Capital × Risk%) / (SL Points × Lot Size)	Every signal — determines how many lots to trade
Kelly Criterion	f = (b×p − q) / b; b=R:R ratio, p=win rate, q=1-p	Use half-Kelly as maximum — never full Kelly
VaR (95%, 1-day)	VaR = Portfolio Value × σ × 1.645	Daily monitoring — if VaR > 5% of capital, reduce exposure
Sharpe Ratio	(Annual Return − Risk Free Rate) / Annualized StdDev	Monthly strategy evaluation — target > 1.5
Sortino Ratio	(Annual Return − Risk Free Rate) / Downside StdDev	Monthly — penalizes only downside — target > 2.0
Calmar Ratio	Annualized CAGR / Maximum Drawdown %	Quarterly — target > 1.5
Maximum Drawdown	max((Peak − Trough) / Peak) × 100 across all history	Continuous — hard limit 15% for ArthAI
Expectancy	(Win Rate × Avg Win) − (Loss Rate × Avg Loss)	Monthly — must be positive for profitability
R-Multiple	Actual P&L / Initial Risk per Trade	Every closed trade — shows quality of outcome
Real Return	((1 + Nominal Return) / (1 + Inflation Rate)) − 1	All portfolio displays — show alongside nominal
Correlation Coefficient	ρ = Σ[(Xi−X̄)(Yi−Ȳ)] / √[Σ(Xi−X̄)² × Σ(Yi−Ȳ)²]	Signal correlation checker — above 0.80 = reject

10.4 Financial Planning Formulas
Calculation	Formula	ArthAI Application
SIP Future Value	FV = P × [(1+r)^n − 1] / r × (1+r); P=monthly SIP, r=monthly rate, n=months	Goal planner: what will Rs 10K/month at 12% become in 20 years?
Required SIP for Goal	P = FV × r / [(1+r)^n − 1] / (1+r)	Goal-to-SIP: what monthly SIP needed for Rs 1Cr in 15 years?
Real Goal Value	Real Goal = Nominal Goal × (1 + Inflation)^n	Education fund: Rs 50L today = Rs 90L needed in 10 years at 6%
Human Life Value	HLV = Annual Income × Years to Retirement − (Existing Assets − Liabilities)	Life insurance adequacy check
EMI Calculation	EMI = P × r × (1+r)^n / [(1+r)^n − 1]	Loan management, debt priority calculator
Opportunity Cost (Annual)	OC = Capital × (Target Return % − Current Return %)	Rs 5L in savings at 3.5% vs liquid fund 7%: OC = Rs 17,500/year
LTCG Tax Saving by Waiting	Saving = Gain × (STCG Rate − LTCG Rate) = Gain × 7.5%	Alert: "Wait 23 more days to save Rs 14,300 in tax"
Debt-to-Income Ratio	DTI = Total Monthly EMIs / Gross Monthly Income × 100	Above 40% = concerning, above 50% = dangerous
Emergency Fund Required	EF = Monthly Expenses × 6	Minimum buffer before investing in any market instrument
 
SECTION 11: BACKTESTING — PROFESSIONAL GRADE
A backtest without realistic costs shows 20-40% better returns than live trading. This creates dangerous false confidence. Every backtest MUST apply the cost model from Section 8.2. Every backtest MUST exclude survivorship bias. These are non-negotiable before real money is deployed.

11.1 Historical Options Data — Specific Sources
Neither v3.0 nor v4.0 specified where to get historical options data for backtesting. Resolution: Primary source = NSE Data on Demand (data.nseindia.com/products) — provides historical options data including EOD prices, OI, IV. Subscription cost approximately Rs 5,000-15,000/month depending on history depth. Alternative = Opstra (opstra.definedge.com) — provides backtesting with IV surface, free tier available for limited data. Budget option = NSE archives (nseindia.com/products/content/equities/equities/archieve_eq.htm) for EOD data, manual download.

11.2 Backtest Realism Requirements
Requirement	Why Critical	Implementation
Realistic costs (Section 8.2)	Without costs, returns inflated 20-40%	Apply full cost table from backtest_cost_assumptions table
Survivorship bias correction	Testing only current Nifty 500 overstates returns 3-8% annually	Use NSE historical constituent lists with addition/removal dates
Look-ahead bias prevention	Must only use data available at exact signal timestamp	Earnings: use only after announcement time. FII data: next day only
Slippage modeling	Never get exact signal price in real life	Minimum 0.05% for large cap, 0.15% for mid cap, 0.3% for small cap
Market impact modeling	Large orders move price against you	Extra 0.1-0.5% for orders > 2% of average daily volume
Options IV surface reconstruction	Options backtest requires historical IV by strike	NSE Data on Demand or Opstra for historical IV data
Multi-leg as single trade	Iron Condor is 1 trade, not 4 separate P&L calculations	Implement leg-grouping by strategy_id in paper_trades table

11.3 All Backtest Metrics with Formulas
Metric	Formula	Target for ArthAI	Interpretation
Win Rate	Winning trades / Total trades	Above 55%	Must be sustained over 50+ trades to be meaningful
Profit Factor	Gross Profit / Gross Loss	Above 2.0	2.0 means you make Rs 2 for every Rs 1 lost
Sharpe Ratio	(Return − RF) / StdDev of Returns	Above 1.5	Risk-adjusted return — above 1.0 is acceptable
Sortino Ratio	(Return − RF) / Downside StdDev	Above 2.0	Better than Sharpe — only penalizes bad volatility
Calmar Ratio	CAGR / Max Drawdown	Above 1.5	If CAGR 20% and max DD 15%: Calmar = 1.33
Max Drawdown	Max(Peak − Trough) / Peak × 100	Below 15%	Hard limit — above 15% means strategy too risky
Recovery Factor	Net Profit / Max Drawdown	Above 3.0	How quickly system recovers from worst loss
Expectancy per Trade	(Win% × Avg Win) − (Loss% × Avg Loss)	Positive	Must be positive for long-term profitability
Average Win/Loss Ratio	Average Win / Average Loss	Above 2.0	Average win should be 2× the average loss
Benchmark Alpha	Strategy CAGR − Nifty 50 TRI CAGR	Above 5%	Value added vs simply buying index fund
Tax-Adjusted CAGR	After applying STCG/LTCG/F&O taxes on all trades	Primary metric	This is what you actually keep — show alongside gross
Max Consecutive Losses	Longest losing streak in history	Know it — plan for it	Psychology planning: can you handle this losing streak emotionally?
 
SECTION 12: COMPLETE FRONTEND SPECIFICATION
12.1 Technology Stack
Component	Technology	Why
Framework	Next.js 16	React-based, server-side rendering, Vercel deployment
OHLC Charts	TradingView Lightweight Charts (open source, free)	Do NOT build candlestick charts from scratch — this is production grade
Portfolio Charts	Recharts or Nivo	P&L curves, allocation pies, performance charts
State Management	Zustand	Lighter than Redux, perfect for real-time state
Data Fetching	TanStack Query (React Query)	Caching, background refresh, loading states built in
Real-time	Socket.io-client	WebSocket for live prices, P&L, signal alerts
Animations	Framer Motion	Signal card animations, debate room reveals
Notifications	React Hot Toast	Non-blocking alert system
Date handling	date-fns	Lightweight — do not use moment.js
PWA	next-pwa	Install on phone, offline support
Keyboard shortcuts	hotkeys-js	j/k navigate signals, t=paper trade, ESC=close
Global data source	Tiingo API (tiingo.com) — NOT Yahoo Finance	Yahoo Finance is unreliable — rate limits without warning, stale data in market hours, no SLA

12.2 All Pages — Complete Specification
Page	Priority	Key Features
/dashboard	P0	Real-time P&L WebSocket ticker in header. Market mood meter gauge. Live agent debate view. Nifty/BankNifty/Gold/VIX mini charts sticky. 4 signal cards with countdown. Sector heatmap treemap. Morning briefing 5 bullets at 8:30 AM. One-click paper trade from signal card.
/charts	P0	TradingView Lightweight Charts. 15+ indicators overlay. Signal markers (buy/sell arrows at exact signal price). Multi-chart 2×2 grid. Drawing tools (trendline, Fibonacci, channel). Replay mode. Chart templates. Right-click menu.
/options	P0	Live options chain via WebSocket (NOT REST). CE/PE columns: OI, OI change, Volume, IV, Delta, Gamma, Theta, Vega. ITM/ATM/OTM color coding. OI bar visualization. Max Pain vertical line. IV Rank + IV Percentile header. Expected Move ±1SD range. Click strike → open strategy builder.
/strategy-builder	P0	Drag-and-drop option legs. Live payoff diagram updating. Max profit/loss/breakeven auto-calculated. Net Greeks across legs. Margin required live. Pre-built templates (Iron Condor, Straddle, etc.). P&L time slider. Save strategy. One-click backtest.
/scanner	P0	Custom formula: "PE < 20 AND ROE > 15 AND Price > 200DMA". Technical scans: Supertrend buy, Golden cross, 52W high breakout, Volume surge. Fundamental scans: Debt-free, High ROCE, Graham Net-Net, Factor Score. Multi-universe. Save scan for daily alerts. Export CSV.
/commodities	P1	MCX live rates all contracts (Gold Petal through 1kg, Silver Micro through 30kg, all base metals + Mini, Crude + Mini, NG + Mini). LME reference alongside MCX. Margin calculator. Gold-Silver ratio live. NCDEX agri rates. International prices.
/global	P1	Pre-market cues: Gift Nifty, Dow Futures, S&P Futures, NASDAQ Futures live. Asian markets. DXY, EUR/USD. Brent Crude, Gold Spot, India VIX in sticky header. Global cue impact estimator. US economic calendar with India impact rating.
/portfolio/xray	P1	Sector exposure pie. Market cap distribution. Stock+MF overlap detector. Correlation heatmap. Concentration alerts. Stress test (Nifty -20% scenario). Factor exposure tilt. Alpha vs Nifty 50 TRI.
/tax-planner	P1	FIFO P&L breakdown. STCG/LTCG running total. Rs 1.25L exemption progress bar. Tax optimization alerts ("wait 23 days to save Rs 14,300"). Tax loss harvesting candidates. New vs old regime comparison. Advance tax reminders. Crypto VDA separate section. Annual report export.
/mutual-funds	P1	MF screener. SIP calculator. Direct vs Regular cost drag in rupees. Fund overlap analyzer. Tax impact pre-redemption. Manager track record. Rolling returns. Goal-to-SIP calculator.
/ipo	P1	Upcoming IPOs: company, dates, price band, lot size. GMP tracker. AI recommendation (apply/avoid) with full reasoning. Subscription status live. Allotment probability. Listing day strategy. Past IPO performance.
/backtest	P1	Select strategy + date range + cost model assumptions. Run button. Equity curve chart. All 12 metrics. Trade log. Monte Carlo tab. Regime breakdown tab. Compare vs Nifty 50 TRI.
/performance	P2	Historical P&L. Win rate by asset class, regime, time of day. Sharpe, Calmar, Sortino, Max DD. Agent accuracy scorecards. Psychology score trend.
/agent-performance	P2	Each agent win rate by asset class and regime. Overconfidence detection. Current adaptive weights. Agent disagreement log.
 
SECTION 13: NOTIFICATION SYSTEM — EXACT FORMATS
13.1 Telegram Message Templates — Every Signal Type
Telegram maximum message length: 4096 characters. All messages must include SEBI disclaimer. Rate limit: 30 messages per second max. Use Telegram message queue with 50ms delay between messages to avoid hitting limits.

Template 1: Strong Buy Signal
🎯 ARTHAI — STRONG BUY  Instrument: BANKNIFTY Entry: 47,820 Stop Loss: 47,540 (−1.2R from entry) Target 1: 48,200 (+1.6R) Target 2: 48,490 (+2.4R) Position Size: 2 lots | Rs 2,000 at risk R:R Ratio: 2.4 | Confidence: 78% ±8% IV Rank: 42% (neutral) Expiry in: 15 minutes  Agent Summary: • Bull (82%): RSI 58, MACD bullish cross, 4TF aligned • Bear (71%): FII buying Rs 1,240Cr, PCR 1.18 bullish • Economist (74%): VIX 13.4, macro favorable, no events • Devil: FAILED TO BREAK — 66% historical win rate (47 occurrences)  ⚠ ArthAI is not a SEBI-registered Research Analyst. For personal educational use only. Investments in securities are subject to market risks.

Template 2: Signal Rejected — Circuit Breaker
🚨 ARTHAI — CIRCUIT BREAKER ACTIVE  Trigger: 3 consecutive losses  Last 3 Trades: • BankNifty BUY → SL Hit (−Rs 800) • Nifty BUY → SL Hit (−Rs 600) • HDFC Bank BUY → SL Hit (−Rs 400)  Error Classification: REGIME_ERROR All 3 trades failed in VIX 22.4 (elevated). Momentum strategies underperform when VIX > 20.  System Action: All position sizes reduced 50% for today. VIX regime threshold updated.  Manual Confirmation Required: Reply OK to resume, or system will auto-resume tomorrow morning.

Template 3: Psychology Guard Alert
🧠 ARTHAI PSYCHOLOGY ALERT  Bias Detected: Overconfidence (Post 3-Win Streak)  Your request: 3× normal position size after winning 3 trades.  Data: Consecutive wins do NOT change probability of next trade. Your overall win rate is 61%. Trade 4 also has 61% probability — unchanged by streak.  Action Taken: Position size capped at standard 2% risk.  Psychology Score This Week: 74/100 Most detected bias: Overconfidence (3 alerts)

Template 4: Pre-Market Morning Briefing
🌅 ARTHAI MORNING BRIEF — {DATE}  📊 Global Cues: • Gift Nifty: +0.3% → Nifty may open at ~22,650 • Dow Jones: −0.2% | Nasdaq: +0.1% | DXY: 103.2 • Brent Crude: $82.4 | Gold: $2,045 • India VIX: 14.2 (NORMAL regime)  📋 Today's Watch: • FII yesterday: Net bought Rs 1,240 Cr (BULLISH) • RBI money market: VRR injection (easing bias) • No major events today  🎯 ArthAI Bias: Mildly BULLISH | Scan from 9:30 AM  📌 Watchlist Today: BankNifty, Reliance, Gold MCX  ⚠ Educational use only. Not investment advice.

13.2 Paper-to-Real Money Transition Criteria — Exact Rules
Neither v3.0 nor v4.0 fully defined the transition from paper trading to real money. These are the exact, non-negotiable criteria. The system enforces them — users cannot self-certify.
Criterion	Exact Threshold	Measured How	Who Validates
Paper trading period	Minimum 30 consecutive calendar days	System checks first paper trade date	System — automatic
Minimum trade count (overall)	Minimum 30 completed paper trades (not 20)	Count of closed paper trades in paper_trades table	System — automatic
Win rate (overall)	Above 65% sustained — calculated on last 30 trades, not all-time	win_count / total_trades for most recent 30	System — automatic
Win rate (per asset class)	Each asset class where real money will be deployed must individually show 60%+ over 20+ trades	Separate calculation per asset_class in paper_trades	System — automatic
Maximum drawdown (paper)	Paper portfolio drawdown must NOT have exceeded 15% at any point	Peak-to-trough on paper portfolio equity curve	System — automatic
Psychology score	Average psychology score above 70/100 in last 30 days	Average of daily_psychology_state scores	System — automatic
Circuit breaker check	No circuit breaker event in last 14 days of paper trading	circuit_breaker_log table check	System — automatic
User confirmation	User must explicitly confirm they understand: real money can be lost, past paper performance does not guarantee future results	Confirmation checkbox + date logged	User — manual
When all criteria are met: System shows "Ready for Real Money" indicator (green) on dashboard. User still makes the final decision. System never automatically switches from paper to real — that transition is always a deliberate human choice.
 
SECTION 14: COMPLETE SCHEDULER — 24/7 OPERATION
Time	Day	Job	File	Purpose
6:00 AM	Daily	Daily Backup	daily_backup.py	Supabase PITR snapshot + Google Drive sync
6:30 AM	Daily	FII Derivatives Fetch	fii_derivative_tracker.py	Download SEBI FII futures/options position data
7:00 AM	Daily	MF NAV Update	mf_nav_job.py	Previous day NAV from AMFI (mfapi.in)
7:30 AM	Daily	Global Cues	global_cues_aggregator.py	Gift Nifty, Dow futures, Asian open, DXY, Crude, Gold — all via Tiingo
8:00 AM	Daily	Market Intelligence	market_intelligence_manager.py	FII/DII analysis, macro update, VIX regime
8:15 AM	Daily	IV Rank Update	iv_rank_calculator.py	Daily IV rank snapshot for all tracked F&O instruments
8:30 AM	Daily	Morning Briefing	pre_market_job.py	5-point AI briefing → Telegram + Dashboard
9:00 AM	Daily	Daily Lesson	daily_lessons.py	Financial education → Telegram
9:15 AM	Weekdays	Market Opens + Flash Monitor	flash_crash_detector.py	Begin 15-min scanning + flash crash monitoring
9:15-3:30 PM	Weekdays	Market Scan (every 15 min)	market_scan_job.py	Full scan → debate → signal if approved
12:00 PM	Weekdays	Midday Risk Check	portfolio_risk.py	Greeks, correlation, concentration checks
3:15 PM	Weekdays	Intraday Close Warning	signal_manager.py	Alert: all intraday must close by 3:30 PM
3:30 PM	Weekdays	Market Closes	market_scan_job.py	Stop scanning, pause flash crash monitor
4:00 PM	Weekdays	EOD Report	eod_report_job.py	Performance report → Telegram + Discord
4:30 PM	Weekdays	Delivery Data	delivery_data.py	Download delivery % from NSE
5:30 PM	Weekdays	FII/DII Final Data	fii_dii_tracker.py	Final daily FII/DII figures from NSE
6:00 PM	Daily	News Digest	news_collector.py	Evening news, update FinBERT sentiment scores
7:00 PM	Daily	Crypto Check	crypto_engine.py	Crypto momentum, Fear & Greed index
10:00 PM	Daily	Pattern Memory Update	pattern_memory_db.py	Log all closed trades to pattern memory DB
11:00 PM	Daily	Strategy Lab Run	strategy_lab_job.py	Overnight backtests, strategy health check
12:00 AM	Daily	Daily Reset	scheduler	Signal counter, cooldown timers, daily limits reset
10:00 AM	Saturday	Weekly Report	weekly_review.py	Comprehensive P&L, win rate, agent accuracy
10:00 AM	Sunday	Self-Evaluation	strategy_lab_job.py	Mini-backtest on last 4 weeks, decay detection
2:00 PM	Sunday	Agent Recalibration	regime_aware_weighter.py	Update agent weights from last 100 trade outcomes
6:00 PM	Sunday	Week Preview	pre_market_job.py	Key events next week → Telegram
March 25	Annual	Tax Harvest Alert	tax_loss_harvester.py	Final alert before March 31 deadline
 
SECTION 15: WEALTH LIFECYCLE — COMPLETE FINANCIAL PLANNING
15.1 Life Stage Allocation Framework
Stage	Age	Focus	Equity	Debt	Alternatives
Foundation	22-30	Emergency fund, term insurance, SIP start, zero personal debt	80%	10%	10% (gold ETF)
Growth	30-40	Wealth accumulation, child education fund, first property consideration	70%	20%	10%
Consolidation	40-50	Accelerate wealth, reduce risk, retirement corpus projection	60%	30%	10%
Pre-Retirement	50-60	Capital preservation, income generation, estate planning	40%	50%	10%
Retirement	60+	Regular income, protect capital, legacy planning	20%	70%	10%

15.2 Insurance as Wealth Foundation
•	Human Life Value: HLV = Annual Income × (Years to Retirement) − (Existing Assets − Liabilities) → minimum life cover required
•	Rule of thumb: minimum 15-20× annual income as life cover
•	Health insurance adequacy: Is Rs 5L cover sufficient in 2026 when cardiac surgery = Rs 10-15L? Almost certainly not.
•	Super top-up plans: most cost-effective way to increase health coverage — low premium for high additional coverage
•	Disability income insurance: probability of disability higher than death for working professionals — rarely bought, critically important
•	Critical illness: lump sum on diagnosis of 36 specified illnesses — separate from health insurance

15.3 Debt Priority Matrix
Loan Type	Typical Rate	Tax Benefit	Priority to Close	ArthAI Logic
Credit Card Outstanding	36-42% annual	None	1 — HIGHEST	This is wealth destruction. Close immediately from any savings.
Personal Loan	12-24%	None	2 — HIGH	No tax benefit, high rate. Close before investing.
Vehicle Loan	8-12%	None	3 — MEDIUM	Standard rate, no benefit. Close on schedule or slightly early.
Education Loan	9-14%	Section 80E — 100% interest deductible for 8 years	4 — MEDIUM-LOW	Tax benefit reduces effective rate to 6-10%. Balance investing vs prepaying.
Home Loan	8.5-9.5%	Section 24: Rs 2L interest + Section 80C: Rs 1.5L principal	5 — LOW	Tax benefits + inflation erodes debt. Invest instead of prepaying in most cases.

15.4 Real Returns — Every Number Must Show This
The single most important concept in financial planning. A 12% return when inflation is 6% is a 6% real return. A 7% FD for a 30% tax bracket person, when inflation is 5%, is only 0.5% real return. ArthAI must show real returns everywhere, always.
•	Formula: Real Return = ((1 + Nominal Return) / (1 + Inflation)) − 1
•	Example: 7% FD, 30% tax = 4.9% post-tax. At 5% inflation: (1.049/1.05) − 1 = −0.1% real return
•	Dashboard must show: Nominal Return AND Real Return side by side on ALL performance displays
•	Opportunity cost alert: "Rs 5L in savings account (3.5%) is losing Rs 17,500/year vs liquid fund (7%)"

15.5 Government Schemes — Eligibility Checker
Scheme	Who Qualifies	Annual Benefit	ArthAI Action
PPF	Any resident Indian	7.1% tax-free return (EEE), Rs 1.5L limit	Recommend maximizing annually — best guaranteed return
NPS	Any Indian citizen	Additional Rs 50K deduction under 80CCD(1B) beyond 80C	Recommend for extra Rs 50K deduction — especially 30% bracket
Sukanya Samriddhi	Girl child below 10 years	8.2% tax-free (EEE), Rs 1.5L limit	Alert parents with girl children to open account
PM Awas Yojana	Income eligibility based	Interest subsidy up to Rs 2.67L on home loan	Flag for eligible first-time home buyers
Senior Citizens Savings Scheme	Age 60+ or 55+ (VRS)	8.2%, quarterly payout, Rs 30L max	Recommend for retired users as best safe income option
SCSS (Tax saving FD)	All taxpayers	Lock in 5-year FD rates	Use for 80C component if other options exhausted

15.6 Estate Planning — Digital Asset Register
•	All investments, account numbers, and logins (encrypted) stored in estate_documents table
•	Nominee update checker: verify nominees are current across all MFs, demat, bank, insurance
•	Will template generator: basic will covering all financial assets
•	Family access document: one page document that tells your family where everything is
•	Succession planning: who manages portfolio if something happens? How does family access accounts?
 
SECTION 16: FAMILY SYSTEM — DATA ISOLATION ARCHITECTURE
Neither v3.0 nor v4.0 specified how family system data is isolated. This is the complete architecture.

16.1 Data Isolation Design
Architecture decision: Same Supabase database, Row Level Security (RLS) for isolation. NOT separate schemas or databases. Rationale: (1) Shared market data tables (instruments, prices) avoid duplication. (2) Supabase RLS enforces strict per-user data access. (3) Family admin can see aggregate, members see only own data.
Data Type	Isolation Method	Who Can See
Market data (prices, signals)	Shared — no isolation	All users
Portfolio holdings	RLS: user_id filter	Only that user + family admin
Trade history	RLS: user_id filter	Only that user + family admin
Psychology scores	RLS: user_id ONLY	Only that specific user — private, not even admin
Tax lots / P&L	RLS: user_id filter	Only that user + family admin (for tax optimization)
Goals	RLS: user_id filter OR family_id for shared goals	User + admin; shared goals visible to all family
Insurance policies	RLS: user_id filter	Only that user + family admin
Estate documents	RLS: user_id ONLY + additional encryption	Only that user

16.2 Family User Roles
Role	Permissions	Use Case
Family Admin	Full access to all family member portfolios and aggregate data	You — the builder and primary user
Active Trader	Full access to own portfolio, signals, paper trading	Spouse or family member who actively trades
Viewer	Read-only access to own portfolio — cannot trade	Family member who wants to see but not act
Minor Account	Restricted — parent/guardian is admin, no independent action	Child's investment account

16.3 Minor Account Legal Constraints
•	SEBI rules: minor account cannot be demat account holder independently — parent/guardian is account holder "on behalf of minor"
•	ArthAI minor account: all trades in guardian's demat, tagged with minor_account_id for tracking
•	Investment restriction: only equity MF and PPF allowed for minors — no F&O, no crypto, no direct equity
•	Account converts to adult account automatically at age 18 — system alerts 3 months before

16.4 Family Money Psychology
•	Each member gets own money personality classification: Spender / Saver / Investor / Security-Seeker
•	Per-member bias tracking: each member's top 3 detected biases shown in their own dashboard only
•	Conflict detection: when one member is strongly bullish and another strongly bearish on same instrument — flag for family discussion
•	Family governance rules: trades above threshold require family admin confirmation (configurable)
•	Shared goal tracking: house purchase, child education visible to all members contributing
 
SECTION 17: SEBI, RBI, AND REGULATORY COMPLIANCE
17.1 Mandatory Disclaimer — Exact Text
This exact text MUST appear on every signal, every page, every Telegram message, every Discord message. It is a legal requirement. Abbreviate where space is limited but never omit.
FULL VERSION: ArthAI is for personal educational use only. It is not a SEBI-registered Research Analyst or Investment Advisor. This is not investment advice. Investments in securities are subject to market risks. Read all related documents before investing. Past performance does not guarantee future results. You are solely responsible for your investment decisions.  SHORT VERSION (for Telegram): ⚠ Educational use only. Not SEBI RA. Not investment advice. Markets involve risk.

17.2 SEBI Research Analyst Registration — Phase 25
Requirement	Individual RA	Timeline
NISM Series XV Certification	Mandatory — register at nism.ac.in, examination fee Rs 1,500	3 months before application
Net Worth Certificate	Rs 1 lakh — from chartered accountant	Before application
Qualification	Graduate degree (any discipline)	Already met
Experience	5 years in financial services OR NISM XV (can substitute experience with certification after rule change)	Verify current SEBI rules at time of application
Application	Form A from sebi.gov.in/sebiweb/home, fee Rs 5,000	Phase 25
Annual compliance	Rs 5,000 renewal + annual compliance report by June 30	Post-registration

17.3 DPDP Act 2023 Compliance
•	Data minimization: collect only data strictly necessary for the service function
•	Explicit consent: separate consent checkboxes for each data category — not buried in terms
•	Right to access: users can download all their data in JSON/CSV format at any time
•	Right to erase: users can delete their account and all associated data — executed within 30 days
•	Data breach notification: within 72 hours to CERT-In (cert-in.org.in) AND affected users
•	Data localization: all user data stored in India — Supabase region must be Mumbai (ap-south-1)
•	No sharing with third parties without explicit per-party consent
 
SECTION 18: INFRASTRUCTURE AND SECURITY
18.1 Production Architecture
Component	Technology	Hosting
Backend API	FastAPI Python 3.11	Render.com (free → paid as usage grows)
Frontend	Next.js 16	Vercel (generous free tier)
Database	Supabase PostgreSQL + pgvector	Supabase cloud — Mumbai region (data localization)
Cache/Queue	Upstash Redis	Serverless Redis — pay per use
Task Queue	Celery + Redis	Co-located with backend
AI Models	Groq + Gemini + Claude + Ollama local	API calls — Ollama runs on your machine as fallback
MCX Data	Shoonya (Finvasia) WebSocket	Connect after Shoonya registration
NSE Options	NSE India WebSocket	Direct connection — replace current REST polling
Global Data	Tiingo API (NOT Yahoo Finance)	Tiingo free tier: 50 API calls/hour — sufficient for daily updates
Crypto	CoinGecko API (free)	1,000 calls/month free — sufficient for daily updates
Monitoring	Sentry (errors) + UptimeRobot (uptime)	Cloud services — both have free tiers

18.2 Critical Security Requirements
•	[P0] All API keys in .env only — NEVER commit to GitHub — add to .gitignore BEFORE first commit
•	[P0] Enable GitHub secrets scanning in repository settings immediately
•	[P0] Rate limiting: max 100 API requests/minute per IP using slowapi middleware
•	[P0] Input sanitization on ALL user inputs — prevent SQL injection and prompt injection
•	[P0] HTTPS everywhere — no HTTP endpoints in production — enforce in nginx/Render config
•	[P1] API key rotation: calendar reminder every 90 days for all provider keys
•	[P1] JWT: access tokens expire in 15 minutes, refresh tokens in 7 days
•	[P1] IP allowlisting: broker API calls only from ArthAI server IP addresses

18.3 API Fallback Chain
Primary	Limit Hit → Fallback 1	Fallback 2	Last Resort
Groq (Bull/Devil)	Ollama local (unlimited, free)	Mistral API	Cached last analysis + manual review alert
Gemini 2.5 Flash (Bear)	Cohere (100 req/min free)	Mistral	FinBERT local sentiment only
Gemini 2.5 Pro (Supervisor)	Claude API	Rule-based consensus fallback	Pause signals, alert user
Perplexity (Economist)	SerpAPI + Tavily	Cached RSS feeds (1-hour stale)	Hourly cached macro, show stale flag
AngelOne API (NSE equity)	Upstox API	Yahoo Finance (15-min delay — last resort only)	Pause equity signals, alert user
Shoonya API (MCX)	Upstox API (also covers MCX)	MCX website EOD scraper	Pause MCX signals, alert user
Tiingo (global data)	Alpha Vantage (free tier)	Yahoo Finance (truly last resort)	Pause global market display
Supabase (DB)	Redis cache (recent data)	Read-only local SQLite	Read-only mode, critical alert
TickerPlant (NCDEX)	NCDEX website EOD scraper	Manual input mode	Pause NCDEX signals only
 
SECTION 19: COMPLETE EXECUTION PLAN — PHASE BY PHASE
19.1 How to Work With AI — 8-Step Session Protocol
Follow this protocol every single session without exception. This prevents the most common AI-assisted development failure modes: scope creep, broken integrations, and lost context.
23.	Paste your updated ARTHAI_CONTEXT.md at the start of EVERY session — this is the AI's memory
24.	State exactly ONE thing to build today — never ask for multiple things in one session
25.	Ask AI to explain what it will build BEFORE any code is written — read the explanation carefully
26.	Say "show me the existing files this new file needs to connect with" — paste them to AI
27.	Say "do NOT change any existing files — only create the new file"
28.	After file is created: restart your server — if it starts cleanly, the file is syntactically correct
29.	Run 3 plain-English test scenarios — ask AI to write a test script, run it, verify PASS/FAIL
30.	Update ARTHAI_CONTEXT.md and tracker before closing the laptop — never skip this step

19.2 ARTHAI_CONTEXT.md Template — Update After Every Session
PROJECT: ArthAI v4.1 TECH STACK: Python 3.11, FastAPI, Supabase (Mumbai region), Upstash Redis, Next.js 16, Tiingo API (NOT Yahoo Finance for global data)  GLOBAL DATA SOURCE: Tiingo (tiingo.com) — Yahoo Finance is NOT reliable MCX DATA SOURCE: Shoonya (Finvasia) API — Shoonya WebSocket NSE OPTIONS: WebSocket (NOT REST polling — REST has 2-5 sec lag) NDEX DATA: TickerPlant API (tickerplant.com) INSTRUMENT KEY FORMAT: EXCHANGE:SYMBOL e.g. NSE:RELIANCE, MCX:GOLD24DECFUT  COVERAGE STATUS (update monthly): - NSE/BSE Equity: 75% - MCX Metals: 25% [CURRENT BUILD PHASE] - NCDEX: 10% [WAITING — TickerPlant setup needed] - F&O Options: 40% [...update all percentages...]  WHAT IS WORKING RIGHT NOW: - [List each working feature]  WHAT IS NOT BUILT: - [List each missing feature]  LAST SESSION BUILT: - [File name and what it does]  BUILDING TODAY: - [Single specific task]

19.3 Phase 15 — Audit and Hardening (4 Weeks) — All P0 Critical
  Week 1: Safety Systems  
•	[P0] signal_correlation_checker.py — MOST CRITICAL — prevents double-exposure risk
•	[P0] volatility_regime_classifier.py — VIX bucket classification
•	[P0] time_of_day_filter.py — 7 session windows with quality ratings
•	[P0] signal_circuit_breaker.py — consecutive loss handler
•	[P0] flash_crash_detector.py — emergency market halt
•	[P0] signal_staleness_decay.py — confidence decay over 20 minutes
•	[P0] signal_priority_queue.py — handles > 4 simultaneous signals
•	[P0] SEBI disclaimer on every signal — legal requirement, do now
  Week 2: AI Brain Upgrades  
•	[P0] pattern_memory_db.py — full 18-column schema + query/write interface
•	[P0] agent_performance_tracker.py — per-agent accuracy logging to Supabase
•	[P0] Update Devil Agent — add Pattern Memory DB query before voting
•	[P0] Update Bear Agent — add pledge % rule and insider override logic
•	[P0] Update Economist Agent — add RBI money market ops signal + FOMC rule
•	[P0] Update Supervisor — add adaptive weights and confidence interval output
•	[P0] prompt_manager.py — version-controlled prompts for all agents
•	[P0] agent_disagreement_log — add DB table, log all 2-2 splits and vetoes
  Week 3: Data Pipeline and Backtest  
•	[P0] Realistic cost model in paper trading — STT, brokerage, GST, stamp, slippage
•	[P0] Survivorship bias dataset for backtest engine
•	[P0] Look-ahead bias prevention — add timestamp validation to all signals
•	[P1] data_quality_scorer.py — quality score per instrument per feed
•	[P1] data_freshness_monitor.py — stale feed detection and alerting
•	[P1] data_lineage_log — add DB table, log data sources for every signal
•	[P1] error_classifier.py — 6 error types taxonomy for adaptive learning
  Week 4: Infrastructure  
•	[P0] Alembic migrations folder — DB schema change management
•	[P0] /api/v1/ prefix on ALL FastAPI routes — do this before more routes are added
•	[P0] api_middleware.py — auth + rate limiting + request ID + logging in one file
•	[P0] Fix data sources — confirm Tiingo for global, Shoonya for MCX, TickerPlant for NCDEX
•	[P0] Add instrument_key universal standard to ALL existing tables
•	[P0] Add is_deleted soft delete to ALL existing tables
•	[P0] Add indexes: signals(created_at, asset_class), paper_trades(instrument_key, created_at)
•	[P0] Add ex_date vs record_date distinction to corporate_actions_log
•	[P1] audit_logger.py — complete signal audit trail for SEBI compliance
•	[P1] GitHub secrets scanning enabled in repository settings

19.4 Phase 16 — MCX Commodities Engine (2 Weeks)
•	[P0] Set up Shoonya account: register, KYC, get API key, test WebSocket connection
•	[P0] mcx_websocket_connector.py — Shoonya API integration with TOTP auth
•	[P0] mcx_contract_specs.py — all contracts, lot sizes, margins, expiry rules
•	[P0] gold_contracts_engine.py — Petal, Guinea, Mini, Full strategies
•	[P0] silver_contracts_engine.py — Micro, Mini, Full strategies
•	[P1] platinum_engine.py — Platinum and Palladium
•	[P1] base_metals_engine.py — all base metals with all Mini variants, Brass, Steel Long
•	[P1] energy_engine.py — Crude (Regular + Mini), Natural Gas (Regular + Mini)
•	[P1] gold_silver_ratio_engine.py — ratio-based inter-commodity signals
•	[P1] comex_mcx_spread.py — COMEX vs MCX price divergence signal
•	[P1] commodity_options_engine.py — MCX Gold/Silver options (now live)
•	[P1] lme_connector.py — London Metal Exchange via Quandl/Nasdaq Data Link
•	[P1] Set up TickerPlant: contact sales, get API credentials, test connection
•	[P1] ncdex_connector.py — TickerPlant API integration
•	[P1] ncdex_agri_engine.py — all 11 agri commodities with seasonal patterns
•	[P1] monsoon_tracker.py — IMD API integration
•	[P1] msp_tracker.py — MSP scraper from pib.gov.in
•	[P1] commodity_macro_correlations.py — DXY, INR, China PMI, OPEC
•	[P1] shfe_correlation.py — Shanghai Futures Exchange vs MCX base metals

19.5 Phase 17 — Options Engine (2 Weeks)
•	[P0] Switch NSE options chain from REST polling to WebSocket — critical latency fix
•	[P0] iv_rank_calculator.py — mandatory input for ALL F&O signals
•	[P0] iv_percentile_calculator.py
•	[P0] max_pain_calculator.py — OI-weighted max pain
•	[P0] portfolio_greeks_aggregator.py — net Delta/Gamma/Theta/Vega across all F&O
•	[P1] iv_surface_builder.py — subscribe to NSE Data on Demand for historical IV
•	[P1] gamma_exposure_calculator.py — dealer GEX by strike
•	[P1] options_flow_tracker.py — unusual volume vs 20-day average
•	[P1] zero_dte_engine.py — 0DTE specific risk rules
•	[P1] expected_move_calculator.py — ATM straddle implied range
•	[P1] options_margin_calculator.py — SPAN + exposure per strategy
•	[P1] payoff_diagram_builder.py — data for frontend payoff visualization
•	[P1] assignment_risk_handler.py — dedicated file for in-the-money short option risk
•	[P1] rollover_recommender.py — near-to-far month rollover signals

19.6 Phase 18 — Fundamental Analysis (2 Weeks)
•	[P1] ratio_analyzer.py — all ratios with 10-year history
•	[P1] dcf_calculator.py — 3-scenario DCF with sensitivity table
•	[P1] earnings_quality_scorer.py — cash vs reported earnings
•	[P1] concall_nlp_analyzer.py — tone and guidance extraction from transcripts
•	[P1] annual_report_red_flag.py — auditor change, going concern detection
•	[P1] peer_comparison_engine.py — auto-group sector, compare 5 peers
•	[P1] promoter_activity_tracker.py — consecutive quarter changes, pledge trend
•	[P1] historical_valuation_bands.py — PE bands over 10 years
•	[P1] factor_scorer.py — 7-factor combined score: Quality 30%, Momentum 25%, Value 20%, Size 15%, Low Vol 10%
•	[P1] macro_regime_classifier.py — BULL/LATE/BEAR/RECOVERY output used for sector rotation

19.7 Phase 19 — Tax Engine (1 Week)
•	[P0] fifo_lot_tracker.py
•	[P0] stcg_ltcg_calculator.py
•	[P0] stt_ctt_calculator.py
•	[P0] vda_tax_tracker.py — crypto VDA 30% flat
•	[P1] tax_regime_comparator.py
•	[P1] advance_tax_calculator.py
•	[P1] tax_loss_harvester.py
•	[P1] form_26as_reconciler.py
•	[P1] elss_lockin_tracker.py
•	[P1] tds_tracker.py
•	[P2] annual_tax_report.py
•	[P2] tax_arbitrage_advisor.py

19.8 Phase 20 — Frontend Transformation (4 Weeks)
•	[P0] Week 1: Install packages: lightweight-charts, Zustand, TanStack Query, Socket.io-client, Framer Motion
•	[P0] Week 1: /charts — TradingView Lightweight Charts with signal markers
•	[P0] Week 1: Real-time WebSocket P&L in dashboard header
•	[P0] Week 2: /options — live options chain via WebSocket with all Greeks and IV Rank
•	[P0] Week 2: /strategy-builder — payoff diagram and drag-and-drop legs
•	[P0] Week 3: /scanner — custom formula + pre-built technical and fundamental scans
•	[P1] Week 3: /commodities — MCX/NCDEX live desk with margin calculator
•	[P1] Week 4: /global — pre-market global cues dashboard
•	[P1] Week 4: /portfolio/xray — sector exposure, overlap, stress test
•	[P1] Week 4: /tax-planner — all tax calculations visible
•	[P1] Week 4: Configure PWA — next-pwa, manifest.json, service worker

19.9 Phases 21-25 — Summary
•	Phase 21 (2 weeks): Adaptive learning — agent weight adjustment, weekly self-evaluation, strategy decay detector, error taxonomy classification
•	Phase 22 (2 weeks): Wealth lifecycle engine — insurance analyzer, debt manager, real return calculator, compounding engine, goal tracker, estate planner, government scheme checker, opportunity cost engine
•	Phase 23 (2 weeks): Family system — multi-user accounts with RLS, family psychology, shared goals, family tax optimizer, role-based access
•	Phase 24 (prerequisites first): Full automation — 6+ months proven performance, SEBI compliance complete, order_executor.py, auto SL modifier, emergency stop button
•	Phase 25 (6+ months): Business launch — NISM XV exam, SEBI RA registration, Pvt Ltd incorporation, GST registration, subscription tiers, public performance page, community
 
SECTION 20: FINAL MASTER CHECKLIST — COMPLETE BUILD
20.1 Priority Legend
•	P0 = BLOCKING — must complete before any real money is deployed
•	P1 = HIGH — complete before Phase 25 (business launch)
•	P2 = MEDIUM — complete within 12 months
•	P3 = LOW — complete when P0-P2 are done
•	BUILT = already working
•	UPGRADE = exists but needs enhancement per this spec

  PHASE 15 — P0 CRITICAL SAFETY (Do All Before Moving On)  
•	[P0] [ ] Python 3.11 verified — run: python --version
•	[P0] [ ] Alembic migrations set up
•	[P0] [ ] /api/v1/ prefix on ALL FastAPI routes
•	[P0] [ ] api_middleware.py (auth + rate limit + request ID + logging)
•	[P0] [ ] signal_correlation_checker.py — MOST CRITICAL
•	[P0] [ ] volatility_regime_classifier.py
•	[P0] [ ] time_of_day_filter.py
•	[P0] [ ] signal_staleness_decay.py
•	[P0] [ ] signal_priority_queue.py
•	[P0] [ ] signal_circuit_breaker.py
•	[P0] [ ] flash_crash_detector.py
•	[P0] [ ] pattern_memory_db.py — full 18-column schema
•	[P0] [ ] agent_disagreement_log — DB table added
•	[P0] [ ] data_lineage_log — DB table added
•	[P0] [ ] signal_correlation_log — DB table added
•	[P0] [ ] All existing DB tables: add instrument_key, is_deleted, indexes
•	[P0] [ ] corporate_actions_log: add ex_date vs record_date distinction
•	[P0] [ ] Realistic paper trading costs (STT, brokerage, GST, stamp, slippage)
•	[P0] [ ] Survivorship bias dataset in backtest engine
•	[P0] [ ] SEBI disclaimer on EVERY signal (Telegram, Discord, Dashboard)
•	[P0] [ ] Tiingo API for global data — remove Yahoo Finance as primary
•	[P0] [ ] agent_performance_tracker.py
•	[P0] [ ] prompt_manager.py
•	[P0] [ ] Update all 4 agents + Supervisor with new specifications
•	[P0] [ ] GitHub secrets scanning enabled

  PHASE 16 — MCX COMMODITIES  
•	[P0] [ ] Shoonya account registered + KYC complete + API credentials in .env
•	[P0] [ ] mcx_websocket_connector.py — Shoonya WebSocket with TOTP auth
•	[P0] [ ] mcx_contract_specs.py
•	[P0] [ ] gold_contracts_engine.py (all 4 sizes)
•	[P0] [ ] silver_contracts_engine.py (all 3 sizes)
•	[P1] [ ] base_metals_engine.py (all metals + Mini variants + Brass + Steel)
•	[P1] [ ] energy_engine.py (Crude + Mini, NG + Mini)
•	[P1] [ ] platinum_engine.py
•	[P1] [ ] comex_mcx_spread.py
•	[P1] [ ] gold_silver_ratio_engine.py
•	[P1] [ ] commodity_options_engine.py
•	[P1] [ ] lme_connector.py
•	[P1] [ ] TickerPlant account + API credentials in .env
•	[P1] [ ] ncdex_connector.py (TickerPlant)
•	[P1] [ ] ncdex_agri_engine.py (all 11 agri)
•	[P1] [ ] monsoon_tracker.py
•	[P1] [ ] msp_tracker.py
•	[P1] [ ] shfe_correlation.py
•	[P1] [ ] commodity_macro_correlations.py

  PHASE 17 — OPTIONS ENGINE  
•	[P0] [ ] NSE options chain switched to WebSocket
•	[P0] [ ] iv_rank_calculator.py
•	[P0] [ ] iv_percentile_calculator.py
•	[P0] [ ] max_pain_calculator.py
•	[P0] [ ] portfolio_greeks_aggregator.py
•	[P1] [ ] NSE Data on Demand subscription for historical IV
•	[P1] [ ] iv_surface_builder.py
•	[P1] [ ] gamma_exposure_calculator.py
•	[P1] [ ] options_flow_tracker.py
•	[P1] [ ] zero_dte_engine.py
•	[P1] [ ] expected_move_calculator.py
•	[P1] [ ] options_margin_calculator.py
•	[P1] [ ] payoff_diagram_builder.py
•	[P1] [ ] assignment_risk_handler.py (dedicated file)
•	[P1] [ ] rollover_recommender.py

  PHASE 18 — FUNDAMENTAL ANALYSIS  
•	[P1] [ ] ratio_analyzer.py
•	[P1] [ ] dcf_calculator.py
•	[P1] [ ] earnings_quality_scorer.py
•	[P1] [ ] concall_nlp_analyzer.py
•	[P1] [ ] annual_report_red_flag.py
•	[P1] [ ] peer_comparison_engine.py
•	[P1] [ ] factor_scorer.py
•	[P1] [ ] macro_regime_classifier.py

  PHASE 19 — TAX ENGINE  
•	[P0] [ ] fifo_lot_tracker.py
•	[P0] [ ] stcg_ltcg_calculator.py
•	[P0] [ ] stt_ctt_calculator.py
•	[P0] [ ] vda_tax_tracker.py
•	[P1] [ ] tax_regime_comparator.py
•	[P1] [ ] advance_tax_calculator.py
•	[P1] [ ] tax_loss_harvester.py
•	[P1] [ ] form_26as_reconciler.py
•	[P1] [ ] elss_lockin_tracker.py
•	[P2] [ ] annual_tax_report.py
•	[P2] [ ] tax_arbitrage_advisor.py

  PHASE 20 — FRONTEND (all pages)  
•	[P0] [ ] /charts (TradingView Lightweight Charts, signal markers)
•	[P0] [ ] /options (live chain, WebSocket, all Greeks, IV Rank)
•	[P0] [ ] /strategy-builder (payoff diagram, drag-drop legs)
•	[P0] [ ] /scanner (custom formula + pre-built scans)
•	[P0] [ ] Dashboard real-time WebSocket P&L
•	[P1] [ ] /commodities (MCX/NCDEX live desk)
•	[P1] [ ] /global (pre-market cues)
•	[P1] [ ] /portfolio/xray
•	[P1] [ ] /tax-planner
•	[P1] [ ] /mutual-funds (overlap, cost drag, manager track)
•	[P1] [ ] /ipo (GMP, subscription, AI recommendation)
•	[P1] [ ] PWA configuration
•	[P2] [ ] /backtest (full UI)
•	[P2] [ ] /performance (all metrics)
•	[P2] [ ] /agent-performance (scorecards)

  PHASES 21-25 — ADVANCED  
•	[P1] [ ] Phase 21: Adaptive learning (agent weights, weekly eval, decay detector)
•	[P1] [ ] Phase 22: Wealth lifecycle (insurance, debt, lifecycle, estate, goals)
•	[P2] [ ] Phase 23: Family system (multi-user, RLS, family psychology)
•	[P2] [ ] Phase 24: Full automation (after 6 months proven performance)
•	[P3] [ ] Phase 25: Business launch (NISM XV, SEBI RA, Pvt Ltd, subscriptions)


ARTHAI MASTER SPECIFICATION v4.1 — COMPLETE
All v3.0 gaps resolved. All v4.0 regressions fixed. All unresolved items from both documents addressed.
This is the one document. Update it after every build session. It is your memory.


"Not the fastest. Not the loudest. But the most intelligent, most disciplined,
 most consistent wealth-building system ever built for India."

When in doubt, stay out.   |   Capital protection over profit, always.   |   Find meaning in market chaos.
