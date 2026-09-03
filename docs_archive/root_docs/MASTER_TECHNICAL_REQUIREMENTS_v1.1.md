# MJONAI — Master Technical Requirements Document
Version: 1.1
Date: 2026-08-13
Status: Living Document — Subject to iterative updates
Project Lead: Mani
Technical Advisor: Kilo

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Vision, Mission & Objectives](#2-vision-mission--objectives)
3. [Scope Definition](#3-scope-definition)
4. [Core Principles & Constraints](#4-core-principles--constraints)
5. [System Architecture](#5-system-architecture)
6. [Data Strategy & Infrastructure](#6-data-strategy--infrastructure)
7. [Market Data Layer](#7-market-data-layer)
8. [Strategy Framework](#8-strategy-framework)
9. [Backtesting & Validation Engine](#9-backtesting--validation-engine)
10. [Risk Management System](#10-risk-management-system)
11. [AI & Intelligence Layer](#11-ai--intelligence-layer)
12. [Answerable AI & Explainability](#12-answerable-ai--explainability)
13. [Implementation Roadmap](#13-implementation-roadmap)
14. [Open Questions & Dependencies](#14-open-questions--dependencies)
15. [Success Metrics & KPIs](#15-success-metrics--kpis)
16. [Appendices](#16-appendices)

---

## 1. Executive Summary

MJONAI is a 24/7 self-learning, answerable global financial intelligence system designed to achieve sustainable risk-adjusted returns through evidence-based quantitative research and execution. The system operates continuously: actively trading during market hours across multiple time zones and conducting research, learning, and analytics during off-hours.

Initial Focus: Indian equity markets (NSE/BSE cash segment) and equity options (NSE F&O segment) for personal use, serving as the proving ground for the platform.

Ultimate Vision: A global multi-asset trading intelligence system covering equities, fixed income, commodities, currencies, crypto, prediction markets, and alternative assets across all major world markets — US, Europe, Asia, and emerging markets.

Key Differentiators:

- **Answerable AI**: Every decision is explainable through a conversational interface backed by a knowledge graph
- **Evidence-Based Learning**: All strategy modifications are validated through rigorous walk-forward testing with statistical correction for multiple testing bias
- **Regime-Aware**: Dynamic strategy selection, position sizing, and risk management adapted to market conditions across all asset classes
- **100% Open Source**: Self-hosted, transparent, no vendor lock-in
- **Multi-Asset, Multi-Market**: Designed from the ground up to handle diverse asset classes and geographies

Current Phase: Phase 0 — Foundation & Infrastructure Setup

---

## 2. Vision, Mission & Objectives

### 2.1 Vision

To build a globally recognized financial intelligence system that combines institutional-grade quantitative research with explainable AI, demonstrating that disciplined process and continuous learning can produce sustainable edge — without sacrificing transparency or control — across every liquid market in the world.

### 2.2 Mission

Create a 24/7 autonomous system that:

- Generates tradeable ideas through multi-strategy research across all asset classes
- Validates ideas through rigorous, statistically-correct backtesting
- Executes with disciplined risk management tailored to each market's microstructure
- Learns from outcomes and continuously improves
- Answers every "why" through natural language interaction
- Adapts to the unique characteristics of each market, asset class, and regulatory environment

### 2.3 Strategic Objectives

| Objective | Target | Timeline |
|-----------|--------|----------|
| Complete Indian markets proof-of-concept | Positive Sharpe > 1.0, max drawdown < 20% | Phase 2 |
| Expand to US equities (NASDAQ/NYSE) | Out-of-sample Sharpe > 0.8 | Phase 6 |
| Expand to European equities (LSE, XETRA) | Out-of-sample Sharpe > 0.8 | Phase 7 |
| Integrate crypto markets (spot + futures) | Validated strategies, controlled risk | Phase 7 |
| Integrate prediction markets (Polymarket, Kalshi) | Edge identification, execution | Phase 8 |
| Integrate commodities (metals, energy, agricultural) | Validated trend/mean-reversion strategies | Phase 7 |
| Integrate fixed income and bonds | Duration-based strategies, credit events | Phase 8 |
| Multi-asset portfolio optimization | True global portfolio, 10+ uncorrelated strategies | Phase 9 |
| Achieve explainable AI for all decisions across all markets | 100% of trades explainable via knowledge graph | Phase 5+ |
| Path to live deployment | Paper trading success for 6+ months per market | Future Phase |

---

## 3. Scope Definition

### 3.1 In Scope — Phase 1 (Initial Build: Indian Markets)

**Asset Classes:**

- Indian equity cash segment (NSE/BSE)
- Indian equity options (NSE F&O)
- Nifty 50, Bank Nifty, FinNifty indices
- Top 50 most liquid NSE stocks by volume and market cap

**Timeframes:**

- Intraday (1-minute to 15-minute bars)
- Swing (1-day to 1-week bars)
- Positional (1-week to 1-month bars)

**Strategy Types:**

- Momentum / trend-following
- Mean reversion
- Volatility-based
- Event-driven (earnings, budget, RBI policy)
- Options-specific: theta decay, volatility trading, directional spreads

**Data Types:**

- OHLCV price data
- Options chains (IV, Greeks, OI, volume)
- Corporate actions (splits, bonuses, dividends)
- News and sentiment
- Market regime indicators

**Functionality:**

- Historical data ingestion and storage
- Backtesting with walk-forward validation
- Paper trading / forward testing
- Strategy research and versioning
- Risk management and position sizing
- Knowledge graph for explainability
- Conversational AI interface
- Dashboard for monitoring

### 3.2 In Scope — Phases 2-9 (Global Expansion)

**Phase 2: Indian Maturity**

- Full Indian equity + options coverage
- Strategy zoo of 5-7 strategies
- Live paper trading for 6+ months

**Phase 3: US Equities**

- NASDAQ and NYSE listed equities
- US index options (SPX, NDX, RUT)
- ETF strategies (SPY, QQQ, sector ETFs)
- US market-specific considerations: extended hours, different settlement cycles

**Phase 4: European Equities**

- LSE (UK), XETRA (Germany), Euronext (France/Netherlands)
- European index options (Euro Stoxx 50, FTSE 100, DAX)
- MiFID II compliance considerations

**Phase 5: Asian Markets (excluding India)**

- Tokyo Stock Exchange (Japan)
- Hong Kong Stock Exchange (HKEX)
- Singapore Exchange (SGX)
- Australian Securities Exchange (ASX)

**Phase 6: Crypto Markets**

- Spot trading (Binance, Coinbase, Kraken)
- Perpetual futures (Binance, Bybit, OKX)
- Options on crypto (Deribit)
- DeFi protocols (on-chain data, yield strategies)
- 24/7 market considerations

**Phase 7: Commodities & Macro**

- Metals: Gold, Silver, Copper, Aluminum (LME, COMEX, MCX)
- Energy: Crude Oil, Natural Gas, Brent (NYMEX, ICE)
- Agricultural: Wheat, Corn, Soybeans, Coffee, Sugar (CBOT, ICE)
- Soft commodities and livestock

**Phase 8: Fixed Income & Alternative Assets**

- Government bonds (US Treasuries, UK Gilts, German Bunds, Indian G-Secs)
- Corporate bonds (investment grade + high yield)
- Credit default swaps (CDS)
- Prediction markets: Polymarket, Kalshi, Manifold Markets
- Emerging market bonds

**Phase 9: Advanced Multi-Asset**

- Foreign exchange (FX): Majors, crosses, emerging market currencies
- Real Estate Investment Trusts (REITs)
- Private market proxies
- Cross-asset arbitrage and relative value strategies
- Multi-asset portfolio optimization with correlation-aware allocation

### 3.3 Out of Scope (Indefinite)

- High-frequency trading (< 1-minute latency-sensitive strategies)
- Illiquid micro-cap stocks in any market
- Physical commodities delivery (paper trading only)
- Leveraged ETFs in non-standard structures
- User management / multi-user access (personal use focus)
- Mobile applications (dashboard-first)

### 3.4 Future Expansion (Post Phase 9)

- Additional prediction market platforms
- Carbon credits and ESG assets
- Collectibles and alternative investments
- Tokenized real-world assets (RWAs)
- Decentralized finance (DeFi) yield strategies

---

## 4. Core Principles & Constraints

### 4.1 Non-Negotiable Principles

- **Evidence Before Execution**: No trade is taken without documented edge thesis, invalidation condition, and statistical validation
- **Regime Awareness**: All systems adapt to market conditions; no static parameters
- **Explainability**: Every decision must be traceable and queryable across all markets
- **Data Quality Obsession**: Clean, point-in-time correct data is the foundation
- **Continuous Learning**: System evolves through validated improvement cycles, not random modification
- **Risk-First Design**: Position sizing and drawdown control precede return optimization
- **Open Source**: Transparent, auditable, no black boxes
- **Market Microstructure Respect**: Each asset class and market has unique characteristics that must be modeled correctly

### 4.2 Technical Constraints

- Environment: Windows laptop, WSL Ubuntu, VS Code with Kilo extension
- Deployment: Local machine / potential future VPS/home server
- Budget: 100% free/open-source stack; avoid paid services where possible
- Data: Prioritize free sources; document any paid data needs
- Compute: Optimize for local hardware; GPU usage optional but beneficial for ML models
- Latency: Paper trading and research focus; live deployment will require co-location evaluation

### 4.3 Regulatory & Ethical Constraints

- SEBI regulations for Indian markets
- SEC/FINRA regulations for US markets
- MiFID II for European markets
- FCA for UK markets
- Local regulatory requirements for each jurisdiction
- No guarantee of returns; all outputs are research, not advice
- Full audit trail for all decisions
- Risk capital posture defined before any live deployment consideration
- Data privacy compliance (GDPR for European markets, etc.)

---

## 5. System Architecture

### 5.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MJONAI SYSTEM                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   Data       │    │  Research   │    │  Execution  │         │
│  │   Layer      │───▶│  Layer      │───▶│  Layer      │         │
│  │             │    │             │    │             │         │
│  │ • Ingest    │    │ • Strategy  │    │ • Backtest  │         │
│  │ • Normalize │    │ • Backtest  │    │ • Forward   │         │
│  │ • Store     │    │ • Validate  │    │ • Paper     │         │
│  │ • Quality   │    │ • Optimize  │    │ • Live      │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│         │                  │                  │                  │
│         ▼                  ▼                  ▼                  │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              Knowledge Graph & Memory                 │       │
│  │   • Trade outcomes    • Strategy versions             │       │
│  │   • Regime history    • Learning log                  │       │
│  └──────────────────────────────────────────────────────┘       │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────┐       │
│  │           Answerable AI / Conversational Layer        │       │
│  │   • RAG over knowledge graph                          │       │
│  │   • Local LLM (Ollama)                               │       │
│  │   • Natural language queries                          │       │
│  └──────────────────────────────────────────────────────┘       │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  Dashboard  │    │  Reports    │    │  Alerts     │         │
│  │  (Streamlit)│    │  (Daily/    │    │  (Real-time)│         │
│  │             │    │   Weekly)   │    │             │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Technology Stack

| Layer | Technology | Purpose | Justification |
|-------|------------|---------|---------------|
| Language | Python 3.11+ | Primary development | Rich quant ecosystem, ML/AI libraries |
| Time-Series DB | TimescaleDB | OHLCV, options chains, ticks | PostgreSQL extension, optimized for time-series |
| Metadata DB | PostgreSQL | Knowledge graph, strategies, outcomes | ACID compliance, JSON support, pgvector |
| Cache/Events | Redis | Real-time streams, caching, pub/sub | Low latency, in-memory |
| API Layer | FastAPI | REST/WebSocket APIs | Async, auto-documentation, Fast |
| Dashboard | Streamlit | Web UI | Rapid prototyping, Plotly integration |
| LLM | Ollama | Local LLM inference | No cloud dependency, privacy |
| Embeddings | sentence-transformers | Vector embeddings | Local, free, good quality |
| Backtesting | VectorBT | Primary engine | Vectorized, fast, walk-forward support |
| Backtesting Alt | Backtrader | Complex execution simulation | Event-driven, realistic broker simulation |
| ML Framework | scikit-learn, XGBoost, PyTorch | Strategy ML components | Comprehensive ML toolkit |
| Time Series ML | Darts, PyTorch Forecasting | LSTM/Transformer models | Purpose-built for time series |
| Orchestration | Docker Compose | Service orchestration | Self-hosted, reproducible |
| Workflow | Prefect / Airflow | Task scheduling | Python-native, good for data pipelines |
| Vector Search | pgvector / ChromaDB | RAG embeddings | PostgreSQL-native or standalone |
| Graph DB | Neo4j (optional) | Knowledge graph | Native graph queries; may use PostgreSQL initially |

### 5.3 Infrastructure Topology

```
┌──────────────────────────────────────────────────────────────────┐
│                    Docker Compose Network                         │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  TimescaleDB  │  │  PostgreSQL  │  │       Redis          │   │
│  │  (Port 5432) │  │  (Port 5433) │  │    (Port 6379)       │   │
│  │              │  │              │  │                      │   │
│  │  ohlcv_bars  │  │  strategies  │  │  market_data_stream  │   │
│  │  options     │  │  opportunities│  │  signal_queue        │   │
│  │  ticks       │  │  outcomes    │  │  cache               │   │
│  │              │  │  regimes     │  │                      │   │
│  │              │  │  news        │  │                      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    Ollama (Port 11434)                     │    │
│  │              Local LLM (Llama 3, DeepSeek-R1)             │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              MJONAI Application Services                   │    │
│  │  • MarketDataProvider   • BacktestEngine                   │    │
│  │  • StrategyRegistry     • RiskManager                      │    │
│  │  • OpportunityGenerator • OutcomeRecorder                  │    │
│  │  • KnowledgeGraph       • ConversationalAI                 │    │
│  │  • Dashboard (Streamlit)                                   │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```


---

## 6. Data Strategy & Infrastructure

### 6.1 Database Schemas

**TimescaleDB: ohlcv_bars (Hypertable)**

```sql
CREATE TABLE ohlcv_bars (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    market_session TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open DECIMAL(18,4) NOT NULL,
    high DECIMAL(18,4) NOT NULL,
    low DECIMAL(18,4) NOT NULL,
    close DECIMAL(18,4) NOT NULL,
    volume BIGINT NOT NULL,
    trades INTEGER,
    source TEXT NOT NULL,
    currency TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (time, symbol, exchange, timeframe)
);
SELECT create_hypertable('ohlcv_bars', 'time', chunk_time_interval => INTERVAL '1 month');
CREATE INDEX idx_ohlcv_symbol_time ON ohlcv_bars (symbol, time DESC);
CREATE INDEX idx_ohlcv_exchange_symbol ON ohlcv_bars (exchange, symbol, time DESC);
```

**TimescaleDB: options_chains (Hypertable)**

```sql
CREATE TABLE options_chains (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    expiry DATE NOT NULL,
    strike DECIMAL(18,4) NOT NULL,
    option_type TEXT NOT NULL,
    open DECIMAL(18,4),
    high DECIMAL(18,4),
    low DECIMAL(18,4),
    close DECIMAL(18,4),
    volume BIGINT,
    open_interest BIGINT,
    iv DECIMAL(10,4),
    delta DECIMAL(10,6),
    gamma DECIMAL(10,6),
    theta DECIMAL(10,6),
    vega DECIMAL(10,6),
    rho DECIMAL(10,6),
    source TEXT NOT NULL,
    currency TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (time, symbol, exchange, expiry, strike, option_type)
);
SELECT create_hypertable('options_chains', 'time', chunk_time_interval => INTERVAL '1 month');
CREATE INDEX idx_options_symbol_expiry ON options_chains (symbol, exchange, expiry, time DESC);
```

**TimescaleDB: futures_contracts (Hypertable)**

```sql
CREATE TABLE futures_contracts (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    contract_month DATE NOT NULL,
    open DECIMAL(18,4),
    high DECIMAL(18,4),
    low DECIMAL(18,4),
    close DECIMAL(18,4),
    volume BIGINT,
    open_interest BIGINT,
    source TEXT NOT NULL,
    currency TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (time, symbol, exchange, contract_month)
);
SELECT create_hypertable('futures_contracts', 'time', chunk_time_interval => INTERVAL '1 month');
CREATE INDEX idx_futures_symbol_month ON futures_contracts (symbol, exchange, contract_month, time DESC);
```

**TimescaleDB: crypto_prices (Hypertable)**

```sql
CREATE TABLE crypto_prices (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    pair TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open DECIMAL(18,8) NOT NULL,
    high DECIMAL(18,8) NOT NULL,
    low DECIMAL(18,8) NOT NULL,
    close DECIMAL(18,8) NOT NULL,
    volume DECIMAL(18,8) NOT NULL,
    quote_volume DECIMAL(18,8),
    trades INTEGER,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (time, symbol, exchange, pair, timeframe)
);
SELECT create_hypertable('crypto_prices', 'time', chunk_time_interval => INTERVAL '1 month');
CREATE INDEX idx_crypto_symbol_time ON crypto_prices (symbol, exchange, time DESC);
```

**TimescaleDB: prediction_markets (Hypertable)**

```sql
CREATE TABLE prediction_markets (
    time TIMESTAMPTZ NOT NULL,
    market_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    event_name TEXT NOT NULL,
    outcome TEXT NOT NULL,
    price DECIMAL(10,4) NOT NULL,
    volume DECIMAL(18,4),
    liquidity DECIMAL(18,4),
    end_date TIMESTAMPTZ,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (time, market_id, platform, outcome)
);
SELECT create_hypertable('prediction_markets', 'time', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX idx_predmarket_platform ON prediction_markets (platform, market_id, time DESC);
```

**TimescaleDB: corporate_actions**

```sql
CREATE TABLE corporate_actions (
    ex_date DATE NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    action_type TEXT NOT NULL,
    ratio DECIMAL(18,6),
    dividend_amount DECIMAL(18,4),
    currency TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (ex_date, symbol, exchange, action_type)
);
```

**TimescaleDB: economic_events (Macro Calendar)**

```sql
CREATE TABLE economic_events (
    event_time TIMESTAMPTZ NOT NULL,
    event_name TEXT NOT NULL,
    country TEXT NOT NULL,
    currency TEXT NOT NULL,
    importance TEXT NOT NULL,
    previous_value DECIMAL(18,4),
    forecast_value DECIMAL(18,4),
    actual_value DECIMAL(18,4),
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (event_time, event_name, country)
);
CREATE INDEX idx_econ_events_time ON economic_events (event_time DESC);
CREATE INDEX idx_econ_events_country ON economic_events (country, event_time DESC);
```

**PostgreSQL: strategies**

```sql
CREATE TABLE strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    category TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    market TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    parameters JSONB NOT NULL,
    entry_rules JSONB NOT NULL,
    exit_rules JSONB NOT NULL,
    risk_rules JSONB NOT NULL,
    regime_constraints JSONB,
    parent_id UUID REFERENCES strategies(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    retired_at TIMESTAMPTZ,
    UNIQUE(name, version)
);
```

**PostgreSQL: opportunities**

```sql
CREATE TABLE opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    direction TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    strategy_id UUID REFERENCES strategies(id),
    regime TEXT NOT NULL,
    market TEXT NOT NULL,
    edge_thesis TEXT NOT NULL,
    invalidation_condition TEXT NOT NULL,
    stop_loss DECIMAL(18,4),
    target DECIMAL(18,4),
    probability DECIMAL(5,4),
    risk_reward_ratio DECIMAL(10,4),
    suggested_position_size DECIMAL(18,4),
    confidence_score DECIMAL(5,4),
    metadata JSONB,
    status TEXT NOT NULL DEFAULT 'generated',
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    executed_at TIMESTAMPTZ,
    outcome_id UUID
);
```

**PostgreSQL: outcomes**

```sql
CREATE TABLE outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id UUID REFERENCES opportunities(id),
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    market TEXT NOT NULL,
    direction TEXT NOT NULL,
    strategy_id UUID REFERENCES strategies(id),
    strategy_version INTEGER NOT NULL,
    entry_price DECIMAL(18,4) NOT NULL,
    exit_price DECIMAL(18,4),
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    stop_loss DECIMAL(18,4),
    target DECIMAL(18,4),
    position_size DECIMAL(18,4) NOT NULL,
    risk_amount DECIMAL(18,4) NOT NULL,
    pnl DECIMAL(18,4),
    pnl_percent DECIMAL(10,4),
    currency TEXT NOT NULL,
    outcome TEXT NOT NULL,
    exit_reason TEXT,
    regime_at_entry TEXT NOT NULL,
    regime_at_exit TEXT,
    commission DECIMAL(18,4) DEFAULT 0,
    slippage DECIMAL(18,4) DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**PostgreSQL: regimes**

```sql
CREATE TABLE regimes (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT,
    exchange TEXT,
    market TEXT NOT NULL,
    regime_type TEXT NOT NULL,
    confidence DECIMAL(5,4),
    volatility_percentile DECIMAL(5,4),
    adx DECIMAL(10,4),
    vix DECIMAL(10,4),
    metadata JSONB,
    PRIMARY KEY (time, symbol, exchange, regime_type)
);
```

**PostgreSQL: news_sentiment**

```sql
CREATE TABLE news_sentiment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    published_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    url TEXT,
    symbols TEXT[],
    exchanges TEXT[],
    markets TEXT[],
    sectors TEXT[],
    countries TEXT[],
    sentiment_score DECIMAL(5,4),
    importance_score DECIMAL(5,4),
    news_type TEXT,
    entities JSONB,
    embedding VECTOR(384),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_news_symbols ON news_sentiment USING GIN (symbols);
CREATE INDEX idx_news_exchanges ON news_sentiment USING GIN (exchanges);
CREATE INDEX idx_news_markets ON news_sentiment USING GIN (markets);
CREATE INDEX idx_news_published ON news_sentiment (published_at DESC);
```

### 6.2 Redis Key Patterns

| Key Pattern | Purpose | TTL |
|-------------|---------|-----|
| market:{market}:{symbol}:{timeframe} | Latest OHLCV bar | 1 hour |
| signal:opportunity:{id} | Generated trade signal | 24 hours |
| signal:queue | Opportunities awaiting approval | 24 hours |
| indicator:{market}:{symbol}:{indicator}:{params} | Cached indicator values | 1 hour |
| auth:session:{user_id} | API session tokens | 8 hours |
| rate_limit:api:{endpoint} | API rate limiting | 60 seconds |
| learning:lock:{strategy_id} | Prevent concurrent strategy updates | 5 minutes |

---

## 7. Market Data Layer

### 7.1 Canonical Data Schema

**Bar Data:**

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class OHLCVBar:
    timestamp: datetime
    symbol: str
    exchange: str
    market_session: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    trades: Optional[int]
    currency: str
    adjusted_close: Optional[float]
```

**Options Chain:**

```python
from dataclasses import dataclass
from datetime import date

@dataclass
class OptionsChain:
    timestamp: datetime
    underlying: str
    exchange: str
    expiry: date
    strike: float
    option_type: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    open_interest: int
    iv: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
```

**Futures Contract:**

```python
from dataclasses import dataclass
from datetime import date

@dataclass
class FuturesContract:
    timestamp: datetime
    symbol: str
    exchange: str
    contract_month: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    open_interest: int
    currency: str
```

**Crypto Bar:**

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class CryptoBar:
    timestamp: datetime
    symbol: str
    exchange: str
    pair: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades: int
```

**Prediction Market:**

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class PredictionMarket:
    timestamp: datetime
    market_id: str
    platform: str
    event_name: str
    outcome: str
    price: float
    volume: float
    liquidity: float
    end_date: datetime
```

**Economic Event:**

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class EconomicEvent:
    event_time: datetime
    event_name: str
    country: str
    currency: str
    importance: str
    previous_value: Optional[float]
    forecast_value: Optional[float]
    actual_value: Optional[float]
    source: str
```

### 7.2 Data Source Hierarchy by Market

**Indian Markets (NSE/BSE):**

1. Angel One SmartAPI — Live + historical, options chains
2. Shoonya API — Alternative broker API
3. Yahoo Finance — Indices, top stocks (limited history)
4. NSE Official Downloads — Bhavcopy, corporate actions
5. Moneycontrol — Historical data
6. Kaggle Datasets — Pre-built Nifty 50 datasets

**US Markets (NASDAQ/NYSE):**

1. Yahoo Finance — Free, good for daily data
2. Alpha Vantage — Free tier available
3. Polygon.io — Real-time + historical (free tier limited)
4. FRED (Federal Reserve) — Economic data
5. CBOE — Options data (limited free)
6. SEC EDGAR — Corporate filings and actions

**European Markets (LSE, XETRA, Euronext):**

1. Yahoo Finance — Free daily data
2. Alpha Vantage — Free tier
3. Investing.com — European market data
4. ECB Data Portal — European economic data
5. LSEG Refinitiv (paid, comprehensive)

**Crypto Markets:**

1. Binance API — Spot + futures (free tier generous)
2. CoinGecko API — Free market data
3. CoinMetrics — On-chain data (free tier)
4. Glassnode — On-chain analytics (free tier limited)
5. Deribit API — Crypto options data

**Commodities (Metals, Energy, Agricultural):**

1. Yahoo Finance — Commodity futures (GC=F, CL=F, etc.)
2. Alpha Vantage — Commodity data
3. LME — London Metal Exchange data (limited free)
4. CME Group — Futures data (delayed free)
5. EIA (Energy Information Administration) — Energy data
6. USDA — Agricultural data

**Fixed Income & Bonds:**

1. FRED (Federal Reserve) — US Treasury yields
2. investing.com — Bond prices and yields
3. ECB Data Portal — European bond yields
4. Yahoo Finance — Bond ETFs (AGG, TLT, etc.)
5. NSE/BSE — Indian G-Secs (limited)

**Prediction Markets:**

1. Polymarket API — Conditional event markets
2. Kalshi API — US event markets
3. Manifold Markets — API available
4. Metaculus — Forecasting platform (scraping)

**FX (Foreign Exchange):**

1. Yahoo Finance — Major currency pairs
2. Alpha Vantage — FX data
3. ECB Statistical Data Warehouse — EUR exchange rates
4. Federal Reserve — USD exchange rates

### 7.3 Data Pipeline

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Sources     │───▶│  Ingest      │───▶│  Validate    │
│  • APIs      │    │  • Download  │    │  • Completeness│
│  • Files     │    │  • Parse     │    │  • Accuracy   │
│  • Feeds     │    │  • Schedule  │    │  • Gaps       │
│  • WebSocket │    │  • WebSocket │    │  • Cross-check│
└──────────────┘    └──────────────┘    └──────────────┘
                                        │
                                        ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Dashboard   │◀──│  Store       │◀──│  Normalize    │
│  • Reports   │    │  • TimescaleDB│   │  • Canonical  │
│  • Alerts    │    │  • PostgreSQL │   │  • Corporate  │
│  • API       │    │  • Redis      │   │  • Alignment  │
│             │    │  • File Store │   │  • Currency   │
│             │    │              │   │  • Adjustment │
└──────────────┘    └──────────────┘    └──────────────┘
```

### 7.4 Data Gaps & Mitigation

| Gap | Mitigation | Priority |
|-----|-----------|----------|
| Historical options IV/Greeks (non-India) | API verification; implied estimation fallback | HIGH |
| Tick-level options data globally | Use 1-min bars as proxy; document limitation | MEDIUM |
| Pre-2010 Indian equity data | Start from reliable NSE data period | LOW |
| Pre-2000 US equity data | CRSP or Yahoo Finance limited history | LOW |
| Crypto pre-2012 data | CoinMetrics free tier; document limitation | LOW |
| Prediction market historical data | API availability varies; manual collection | MEDIUM |
| Corporate actions for all markets | SEC EDGAR (US), exchange feeds (others) | HIGH |
| Economic event history | FRED, ECB, IMF databases | MEDIUM |

---

## 8. Strategy Framework

### 8.1 Strategy Philosophy

No Single Strategy Fits All. The system operates as a strategy zoo — a collection of uncorrelated strategies, each optimized for specific market regimes, asset classes, and market microstructures.

### 8.2 Strategy Taxonomy

```
Strategies
├── Equity Strategies
│   ├── Momentum
│   │   ├── Relative Strength (6-12 month lookback)
│   │   ├── Price Momentum with Volume
│   │   ├── Earnings Momentum
│   │   └── Sector Rotation
│   ├── Mean Reversion
│   │   ├── Bollinger Bands + RSI (range-bound only)
│   │   ├── Pairs Trading / Statistical Arbitrage
│   │   ├── Intraday ORB + VWAP
│   │   └── ETF Arbitrage
│   ├── Value
│   │   ├── P/E, P/B, EV/EBITDA screening
│   │   ├── Quality Factors (ROE, profit margins)
│   │   └── Dividend Yield Strategies
│   ├── Volatility-Based
│   │   ├── VIX Position Sizing
│   │   ├── ATR-Based Stops
│   │   └── Volatility Regime Detection
│   └── Event-Driven
│       ├── Earnings Announcements
│       ├── Policy Events (RBI, Fed, ECB)
│       ├── Corporate Actions
│       └── Index Rebalancing
│
├── Options Strategies
│   ├── Theta Decay
│   │   ├── Short Straddle (ATM, pre-expiry)
│   │   ├── Short Strangle (OTM, low IV)
│   │   ├── Iron Condor (defined risk)
│   │   └── Iron Butterfly
│   ├── Volatility Trading
│   │   ├── Long Straddle (pre-event)
│   │   ├── IV Spreads (calendar, diagonal)
│   │   └── VIX Futures Hedge
│   └── Directional
│       ├── Covered Call
│       ├── Bull/Bear Spreads
│       └── Leveraged Directional
│
├── Crypto Strategies
│   ├── Trend Following
│   │   ├── Moving Average Crossovers
│   │   ├── Breakout Trading
│   │   └── Crypto-specific momentum
│   ├── Arbitrage
│   │   ├── Cross-exchange arbitrage
│   │   ├── Funding rate arbitrage (perpetual futures)
│   │   └── Triangular arbitrage
│   └── On-Chain Strategies
│       ├── NVT Ratio strategies
│       ├── Exchange flow analysis
│       └── Whale tracking
│
├── Commodity Strategies
│   ├── Trend Following (markets have strong trends)
│   ├── Carry Trade (contango/backwardation)
│   ├── Spread Trading (calendar, inter-commodity)
│   └── Seasonal Patterns (agricultural)
│
├── Fixed Income Strategies
│   ├── Duration Management
│   ├── Credit Spread Trading
│   ├── Curve Trading (steepening/flattening)
│   └── Carry Strategies
│
├── FX Strategies
│   ├── Carry Trade
│   ├── Momentum
│   ├── Mean Reversion
│   └── Event-Driven (rate decisions, elections)
│
└── Prediction Market Strategies
    ├── Event Trading
    ├── Arbitrage (across platforms)
    └── Sentiment-based positioning
```

### 8.3 Market-Specific Considerations

**Indian Markets:**

- T+1 settlement cycle
- High retail participation → retail flow patterns
- Circuit limits (20% for most stocks)
- Options expiry every Thursday (weekly)
- High volatility events: budget, elections, monsoon

**US Markets:**

- T+2 settlement cycle
- Pre-market and post-market sessions
- Options expiry every third Friday (monthly) + weekly
- Microstructure: HFT dominance, order flow toxicity
- Fed policy dominance

**European Markets:**

- MiFID II transparency requirements
- Multiple trading venues (dark pools, lit exchanges)
- ECB monetary policy influence
- Currency overlay (EUR, GBP, CHF)

**Crypto Markets:**

- 24/7 trading → continuous risk management needed
- Extreme volatility (50%+ moves common)
- Exchange risk (hacks, insolvencies)
- Regulatory uncertainty
- On-chain data availability (transparent ledger)

**Commodities Markets:**

- Physical delivery considerations
- Seasonal patterns (agricultural)
- Storage costs (carry)
- Geopolitical sensitivity
- Currency correlation (USD-denominated)

**Fixed Income Markets:**

- Duration risk (interest rate sensitivity)
- Credit risk (default probability)
- Liquidity risk (especially corporate bonds)
- Inflation expectations
- Central bank policy

**Prediction Markets:**

- Event resolution risk
- Liquidity constraints
- Platform-specific rules
- Market manipulation potential
- Correlation with real-world events

### 8.4 Strategy Development Lifecycle

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Idea       │───▶│  Research    │───▶│  Implementation│
│  • Concept   │    │  • Backtest  │    │  • Code        │
│  • Thesis    │    │  • Validate  │    │  • Tests       │
│  • Regime    │    │  • Optimize  │    │  • Docs        │
└──────────────┘    └──────────────┘    └──────────────┘
                           │                    │
                           ▼                    ▼
                    ┌──────────────┐    ┌──────────────┐
                    │  Validation  │───▶│  Deployment   │
                    │  • Walk-fwd  │    │  • Paper      │
                    │  • DSR       │    │  • Monitor    │
                    │  • Regime    │    │  • Learn      │
                    └──────────────┘    └──────────────┘
```

### 8.5 Initial Strategy Candidates

**Phase 1 (Indian Markets):**

1. Nifty 50 6-Month Momentum — Monthly rebalance, top 10 by 6M/1M momentum
2. Intraday ORB + VWAP — 15-min opening range breakout with volume confirmation
3. Mean Reversion (Range-Bound Regime) — Bollinger Bands + RSI, ADX < 20 filter
4. Weekly Iron Condor — Nifty/Bank Nifty, Monday entry, Thursday exit
5. Pre-Event Straddle — Budget/RBI plays, long straddle 3 days before

**Phase 2+ (Global Markets):**

6. US Equity Momentum (6M/1M) — NASDAQ/NYSE large-cap
7. Crypto Trend Following — Multi-timeframe moving average system
8. Gold Trend Following — Commodity trend following with inflation hedge overlay
9. FX Carry Trade — High-yield currency pairs with carry
10. Prediction Market Event Trading — Event-based positioning


---

## 9. Backtesting & Validation Engine

### 9.1 Engine Architecture

**Primary: VectorBT (Vectorized Backtesting)**

- Speed: 100-1000x faster than event-driven for parameter sweeps
- Ideal for: Walk-forward optimization, regime classification, multi-strategy portfolios
- Limitation: Less realistic execution simulation

**Secondary: Backtrader (Event-Driven)**

- Use case: Complex execution simulation, margin modeling, multi-leg options
- When needed: Final validation of strategies before paper trading

**Tertiary: Custom Simulation**

- For crypto 24/7 markets
- For prediction markets (event-based resolution)
- For multi-asset portfolio simulation

### 9.2 Walk-Forward Validation Framework

**Parameters for Indian Markets:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Training Window | 12-24 months | Captures full market cycles |
| Testing Window | 1-3 months | Enough trades for statistical significance |
| Step Size | 1 month | Balance between data efficiency and frequency |
| Minimum Cycles | 10 | Statistical confidence |
| Min Trades per Window | 30 | Minimum for meaningful metrics |

**Process:**

1. Train: Optimize strategy parameters on training window (in-sample)
2. Test: Lock parameters, test on next window (out-of-sample)
3. Roll: Advance both windows by test window length
4. Repeat: Until full dataset covered
5. Aggregate: Combine all out-of-sample results for final metrics

**Parameters for US Markets:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Training Window | 24-36 months | Longer cycles, regime persistence |
| Testing Window | 3-6 months | More data per window |
| Step Size | 3 months | Reduce overfitting risk |
| Minimum Cycles | 8 | Sufficient for validation |
| Min Trades per Window | 50 | Higher frequency strategies |

**Parameters for Crypto Markets:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Training Window | 6-12 months | Rapid regime changes |
| Testing Window | 1-2 months | Fast-moving markets |
| Step Size | 2 weeks | More frequent revalidation |
| Minimum Cycles | 15 | High noise requires more samples |
| Min Trades per Window | 40 | 24/7 trading generates more trades |

**Parameters for Commodities/Fixed Income:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Training Window | 36-60 months | Capture full business/commodity cycles |
| Testing Window | 6-12 months | Slower-moving markets |
| Step Size | 6 months | Long-term trends dominate |
| Minimum Cycles | 5 | Fewer but larger trades |
| Min Trades per Window | 20 | Lower frequency strategies |

### 9.3 Overfitting Prevention Stack (Mandatory)

1. **Walk-Forward Validation** — Primary defense
2. **Parameter Simplification** — Max 3-4 optimized parameters per strategy
3. **Sensitivity Analysis** — Test parameter stability; if RSI(14) breaks but RSI(13) works, suspect overfitting
4. **Regime-Specific Testing** — Verify performance across bull, bear, sideways markets
5. **Monte Carlo Simulation** — Stress-test drawdowns with randomized trade order
6. **Deflated Sharpe Ratio (DSR)** — Correct for multiple testing bias
7. **White's Reality Check** — Bootstrap-based performance test
8. **Rademacher Anti-Serum (RAS)** — Advanced multiple testing correction

### 9.4 Realistic Execution Assumptions

**Costs — Indian Markets:**

- Brokerage: ₹20 per trade or 0.05% (whichever lower) — Zerodha/Upstox rates
- STT: 0.1% on sell side (equity), 0.05% on options sell
- Transaction charges: 0.00345% (NSE)
- GST: 18% on brokerage and transaction charges
- Stamp duty: 0.015% (buy side, varies by state)

**Costs — US Markets:**

- Brokerage: $0.00 (most brokers: Robinhood, Interactive Brokers lite)
- SEC Fee: 0.00251% (sell side)
- FINRA TAF: $0.000166 per share (sell side)
- Pattern Day Trader Rule: $25,000 minimum for 4+ day trades/week
- Margin Interest: Varies by broker (typically 8-12%)

**Costs — Crypto Markets:**

- Maker Fee: 0.02-0.10% (varies by exchange, volume tier)
- Taker Fee: 0.04-0.20%
- Withdrawal Fees: Network-dependent (variable)
- Slippage: Higher on low-liquidity pairs (0.5%+)
- Funding Rates: Perpetual futures (0.01-0.1% per 8h period)

**Costs — European Markets:**

- Brokerage: varies by broker and exchange (typically 0.1-0.5%)
- Stamp Duty: 0.5% (UK, buy side only)
- Tobin Tax: 0.1% (France, on high-frequency trades)
- MiFID II reporting fees

**Slippage Assumptions:**

| Asset Class / Market | Liquidity | Slippage |
|---------------------|-----------|----------|
| Indian equities (Nifty 50) | High | 0.05-0.1% |
| Indian equities (mid-cap) | Medium | 0.2-0.5% |
| US equities (S&P 500) | High | 0.01-0.03% |
| US equities (small-cap) | Medium | 0.1-0.3% |
| European equities (large-cap) | High | 0.05-0.15% |
| Options (ATM) | Medium | 0.1-0.2% |
| Options (OTM) | Low | 0.3-0.5% |
| Crypto (BTC/ETH, top exchanges) | High | 0.05-0.1% |
| Crypto (altcoins) | Low | 0.5-2.0% |
| Commodity futures (top contracts) | High | 0.05-0.1% |
| Bond futures | Medium | 0.1-0.3% |
| Prediction markets | Low | 1.0-3.0% |

**Market Impact:**

- Position size < 5% of daily volume: Negligible
- Position size > 10% of daily volume: Add 0.1-0.3% slippage

### 9.5 Performance Metrics

**Primary Metrics:**

- **Sharpe Ratio** — Risk-adjusted returns (target > 1.0)
- **Sortino Ratio** — Downside risk-adjusted (target > 1.5)
- **Maximum Drawdown** — Peak-to-trough (target < 20%)
- **Calmar Ratio** — Return / max drawdown (target > 1.0)
- **Profit Factor** — Gross profit / gross loss (target > 1.5)
- **Win Rate** — Percentage of winning trades (context-dependent)
- **Average Win / Average Loss** — Risk-reward ratio (target > 1.5)

**Secondary Metrics:**

- **Recovery Factor** — Net profit / max drawdown
- **Ulcer Index** — Depth and duration of drawdowns
- **VaR / CVaR** — Tail risk measures
- **Turnover** — Trading frequency
- **Capacity** — Maximum capital strategy can handle
- **Skewness** — Distribution asymmetry (prefer positive skew)
- **Kurtosis** — Tail risk (lower is better)

---

## 10. Risk Management System

### 10.1 Risk Philosophy

Risk management is not a constraint on returns — it is the foundation of sustainable returns. Position sizing and drawdown control determine long-term outcomes more than trade selection. Different asset classes require different risk frameworks:

- **Equities**: Drawdown control, sector concentration limits
- **Options**: Greeks management, expiration risk
- **Crypto**: Extreme volatility, 24/7 risk, exchange risk
- **Commodities**: Commodity-specific risk, seasonality
- **Fixed Income**: Duration risk, credit risk, interest rate sensitivity
- **Prediction Markets**: Liquidity risk, event resolution risk

### 10.2 Dynamic Position Sizing Framework

Multi-Layer Approach:

```
┌───────────────────────────────────────────────────────────┐
│  Layer 4: Strategy-Level Risk                            │
│  • Per-strategy allocation                               │
│  • Strategy correlation limit                            │
└───────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────────────────────────────────────┐
│  Layer 3: Regime Risk Adjustment                         │
│  • VIX-based multiplier                                 │
│  • Regime confidence scaling                             │
└───────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────────────────────────────────────┐
│  Layer 2: Kelly Criterion / Volatility Targeting         │
│  • Fractional Kelly (0.25-0.5x)                         │
│  • Volatility targeting                                  │
└───────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────────────────────────────────────┐
│  Layer 1: Fixed-Fraction Base                            │
│  • 1-2% per trade risk                                  │
│  • 10-15% aggregate open risk                           │
└───────────────────────────────────────────────────────────┘
```

### 10.3 Position Sizing Calculation

```python
def calculate_position_size(
    account_value: float,
    strategy_sharpe: float,
    regime_multiplier: float,
    volatility: float,
    target_volatility: float = 0.15,
    kelly_fraction: float = 0.5,
    max_risk_per_trade: float = 0.02
) -> float:
    # Layer 1: Fixed fraction base
    base_risk = account_value * max_risk_per_trade
    
    # Layer 2: Kelly / Volatility targeting
    kelly_size = calculate_kelly(strategy_sharpe, win_rate, avg_win, avg_loss)
    vol_target_size = base_risk * (target_volatility / volatility)
    
    # Layer 3: Regime adjustment
    regime_adjusted = min(kelly_size, vol_target_size) * regime_multiplier
    
    # Layer 4: Strategy allocation (handled at portfolio level)
    
    # Constraints
    final_size = min(regime_adjusted, base_risk)
    return max(final_size, 0)
```

### 10.4 Regime-Based Risk Adjustments

| VIX Level | Regime | Position Multiplier | Action |
|-----------|--------|---------------------|--------|
| > 30 | Extreme Volatility | 0.25x | Reduce to 25% base size, halt new entries |
| 25-30 | High Volatility | 0.5x | Reduce to 50% base size |
| 15-25 | Normal | 1.0x | Standard sizing |
| 12-15 | Low Volatility | 1.25x | Can increase up to 125% |
| < 12 | Very Low | 1.5x | Consider increasing, watch for complacency |

### 10.5 Hard Limits & Kill Switches

**Account-Level:**

- **Maximum Drawdown Halt**: 20% drawdown → STOP ALL TRADING, reassess
- **Daily Loss Limit**: 5% daily loss → No new trades that day
- **Weekly Loss Limit**: 10% weekly loss → Reduce sizes by 50%
- **Monthly Loss Limit**: 15% monthly loss → Halve all positions

**Strategy-Level:**

- **Consecutive Losses**: 5 consecutive losses → Pause strategy, review
- **Strategy Drawdown**: 15% strategy-level drawdown → Halve position size
- **Performance Degradation**: Sharpe < 0.5 over 3 months → Review or retire

**Trade-Level:**

- **Per-Trade Risk**: Never risk more than 2% of account on single trade
- **Aggregate Risk**: Total open risk < 10-15% of account
- **Correlation Limit**: No more than 20% in correlated positions
- **Expiration Risk**: Options — exit or roll 24 hours before expiry

### 10.6 Drawdown Control Mechanisms

```python
def check_drawdown_limits(current_equity: float, peak_equity: float) -> Dict:
    drawdown = (peak_equity - current_equity) / peak_equity
    
    if drawdown > 0.20:
        return {"action": "HALT_ALL", "message": "20% drawdown - stop trading"}
    elif drawdown > 0.15:
        return {"action": "REDUCE_50", "message": "15% drawdown - halve sizes"}
    elif drawdown > 0.10:
        return {"action": "REDUCE_25", "message": "10% drawdown - reduce 25%"}
    else:
        return {"action": "NORMAL", "message": "Within limits"}
```

### 10.7 Asset-Class-Specific Risk Rules

**Options Risk:**

- Max 10% of portfolio in options at any time
- No single option position > 2% of portfolio
- Greek limits: Delta < 0.5 per position, Gamma < 0.1, Vega exposure limited
- Theta decay monitored daily; max 1% portfolio loss per day from theta
- Expiry rule: Exit 24h before expiry unless explicitly managed

**Crypto Risk:**

- Max 15% of portfolio in crypto (high volatility)
- Exchange risk: Diversify across 2-3 exchanges
- Stablecoin depeg risk: Monitor USDC/USDT reserves
- Regulatory risk: Monitor SEC, MiCA developments
- 24/7 monitoring required; auto-hedging at 2% daily loss

**Commodity Risk:**

- Roll costs for futures: Factor into backtest
- Storage/contango costs: Model in backtest
- Geopolitical risk: Hard stops on geopolitical events
- Seasonal risk: Reduce exposure during high-volatility seasons

**Fixed Income Risk:**

- Duration limit: Max 7 years modified duration
- Credit quality: Max 20% in non-investment grade
- Liquidity risk: Avoid bonds with < $1M daily volume
- Interest rate risk: Hedge with duration targets

---

## 11. AI & Intelligence Layer

### 11.1 Intelligence Stack

```
┌─────────────────────────────────────────────────────────────┐
│                   Intelligence Layer                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  News        │  │  Sentiment   │  │  Forecasting │      │
│  │  Ingestion   │  │  Analysis    │  │  Models      │      │
│  │              │  │              │  │              │      │
│  │ • RSS feeds  │  │ • FinBERT    │  │ • LSTM       │      │
│  │ • APIs       │  │ • VADER      │  │ • Transformers│     │
│  │ • WebSocket  │  │ • Groq+LLaMA│  │ • GARCH      │      │
│  │ • Scrapers   │  │ • Emotion    │  │ • Ensemble   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Regime      │  │  Strategy    │  │  Learning    │      │
│  │  Detection   │  │  Optimization│  │  Engine      │      │
│  │              │  │              │  │              │      │
│  │ • HMM       │  │ • Genetic    │  │ • Outcome    │      │
│  │ • VIX       │  │   Algorithms │  │   Analysis   │      │
│  │ • ADX       │  │ • Bayesian   │  │ • Strategy   │      │
│  │ • ML        │  │   Opt        │  │   Evolution  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 11.2 News & Sentiment Pipeline

**Data Sources (Free):**

- Economic Times Markets RSS
- Moneycontrol News RSS
- NSE Announcements RSS
- BSE Announcements RSS
- Mint Markets RSS
- Business Standard Markets RSS
- Financial Express Markets RSS
- Reuters API (free tier)
- Bloomberg (free tier limited)
- Twitter/X financial handles
- Reddit (r/investing, r/StockMarket, r/CryptoCurrency, r/options)

**Pipeline Architecture:**

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Sources     │───▶│  Ingestion   │───▶│  NLP         │
│  • RSS       │    │  • Feedparser│    │  • FinBERT   │
│  • APIs      │    │  • Reddit    │    │  • NER       │
│  • Feeds     │    │  • Dedup     │    │  • Sentiment │
│  • Scrapers  │    │  • Scheduler │    │  • Summary   │
└──────────────┘    └──────────────┘    └──────────────┘
                                          │
                                          ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Dashboard   │◀──│  Storage     │◀──│  Aggregation │
│  • Signals   │    │  • PostgreSQL│    │  • Sector    │
│  • Reports   │    │  • Redis     │    │  • Index     │
│  • Alerts    │    │  • Vector    │    │  • Weights   │
└──────────────┘    └──────────────┘    └──────────────┘
```

**Sentiment Scoring:**

- Range: -1.0 (very negative) to +1.0 (very positive)
- Comparative scoring: calibrated against batch anchors, not absolute
- Sector propagation: index-weighted aggregation across constituents
- Signal detection: |score| > 0.50 = company spike; sector reversal = 6h vs 18h baseline

### 11.3 Forecasting Models

**Price Forecasting:**

- **LSTM** — Baseline for univariate price prediction
- **Transformer (PatchTST / iTransformer)** — Multi-variate, long-range dependencies
- **Temporal Fusion Transformer (TFT)** — Multi-horizon with uncertainty estimates
- **Hybrid LSTM-Transformer** — Best of both; recommended for Phase 2+

**Volatility Forecasting:**

- **GARCH(1,1)** — Standard for volatility clustering
- **GARCH-LSTM** — Neural enhancement of GARCH
- **Realized Volatility** — Using high-frequency data when available

**Usage Constraints:**

- Forecasts are inputs to strategies, not standalone signals
- Never trade directly on forecast; use as confidence/weighting factor
- Forecasts must be accompanied by prediction intervals (uncertainty)

### 11.4 Regime Detection

**Multi-Modal Regime Classification:**

| Method | Regimes Detected | Use Case |
|--------|-----------------|----------|
| VIX Level | Low/Normal/High/Extreme | Options, position sizing |
| ADX | Trending/Range-bound | Equity strategy selection |
| HMM | 3-5 hidden states | Strategy allocation |
| Volatility Percentile | Low/Normal/High | Risk adjustment |
| Market Breadth | Broad/Narrow | Confirmation filter |
| 宏观经济因子 | Recession/Expansion | Multi-asset allocation |

**Regime-Aware Strategy Allocation:**

```python
regime_strategy_map = {
    "trending_up": ["momentum", "breakout"],
    "trending_down": ["contrarian", "defensive"],
    "range_bound": ["mean_reversion", "theta_decay"],
    "volatile": ["volatility_trading", "reduced_sizing"],
    "extreme_volatility": ["cash", "hedging"]
}
```


---

## 12. Answerable AI & Explainability

### 12.1 The Answerable AI Requirement

**Core Principle:** The system must answer "why" for every decision, not just "what happened."

**Query Types the System Must Support:**

- "Why did the system take trade X on date Y?"
- "What was the edge thesis for strategy Z in Q3 2024?"
- "How did regime R affect strategy S performance?"
- "What evidence supports strategy version 2 vs version 1?"
- "Show me all trades where stop loss was hit within 1 hour"
- "What would have happened if we used strategy T instead?"
- "Which sectors are showing positive sentiment this week?"
- "How does correlation between strategy A and B affect portfolio risk?"

### 12.2 Knowledge Graph Schema

**Node Types:**

- **Company** — NSE/BSE/NASDAQ/LSE listed entities
- **Strategy** — Strategy definitions and versions
- **Trade** — Individual trade records
- **Outcome** — Trade results
- **Regime** — Market regime snapshots
- **Event** — Earnings, policy, corporate actions
- **News** — News articles and sentiment
- **Indicator** — Technical indicator values
- **Model** — ML models and forecasts
- **Market** — Market definitions (NSE, NASDAQ, Binance)
- **AssetClass** — Equity, options, crypto, commodity, etc.

**Relationship Types:**

- GENERATED_BY — Trade → Strategy
- TRIGGERED_BY — Trade → Event/News
- OCCURRED_IN — Trade → Regime
- RESULTED_IN — Trade → Outcome
- BELONGS_TO — Company → Sector
- USES — Strategy → Indicator
- PREDICTS — Model → Price/Volatility
- TRADED_ON — Trade → Market
- PART_OF — Company → AssetClass

### 12.3 RAG Pipeline

**Architecture:**

```
User Query (Natural Language)
         │
         ▼
┌───────────────────────────────────────────────────────────┐
│  Query Understanding                                       │
│  • Intent classification                                   │
│  • Entity extraction (companies, strategies, dates)        │
│  • Query decomposition for complex questions               │
└───────────────────────────────────────────────────────────┘
         │
         ▼
┌───────────────────────────────────────────────────────────┐
│  Hybrid Retrieval                                          │
│  • Vector search (embeddings)                              │
│  • Graph traversal (knowledge graph)                       │
│  • Structured query (SQL/Cypher)                           │
│  • Reranking for relevance                                 │
└───────────────────────────────────────────────────────────┘
         │
         ▼
┌───────────────────────────────────────────────────────────┐
│  Context Assembly                                          │
│  • Trade details                                           │
│  • Strategy version and rationale                          │
│  • Regime context at time of trade                         │
│  • News/events that day                                    │
│  • Performance comparison                                  │
└───────────────────────────────────────────────────────────┘
         │
         ▼
┌───────────────────────────────────────────────────────────┐
│  LLM Generation (Ollama)                                  │
│  • Local LLM generates answer                              │
│  • Citations to source data                                │
│  • Confidence indicators                                   │
└───────────────────────────────────────────────────────────┘
```

**LLM Selection:**

- **Primary**: Llama 3 (8B or 70B) via Ollama
- **Alternative**: DeepSeek-R1 (reasoning-focused)
- **Embeddings**: sentence-transformers/all-MiniLM-L6-v2 (384-dim)
- **Reranker**: Optional cross-encoder for top-k refinement

### 12.4 Conversational Interface

**Interface Options:**

- **Streamlit Chat UI** — Primary interface, integrated with dashboard
- **CLI** — For power users and automation
- **FastAPI Endpoints** — For programmatic access

**Example Interactions:**

```
User: "Why did we lose on the Reliance trade on March 15?"
AI:   "The Reliance trade on March 15 was a 6-month momentum signal 
       generated by strategy v2.1. The edge thesis was continuation 
       of Q4 earnings momentum. Invalidations: RSI hit 75 (overbought) 
       and VIX spiked to 28 (high volatility regime). Exit was triggered 
       by stop loss at -12% vs target of +25%. The strategy has a 62% 
       win rate in trending_up regimes but this trade occurred in a 
       transitioning regime (ADX dropped from 28 to 19)."

User: "Compare strategy v1 vs v2 performance in 2024"
AI:   "Strategy v2 improved Sharpe from 0.8 to 1.3 (62% improvement) 
       in 2024. Main changes: added ADX filter (reduced false signals 
       by 40%) and tightened stop loss (reduced avg loss by 18%). 
       Walk-forward validation: 9/10 windows positive. DSR: 1.85."

User: "What's the current regime for Bitcoin?"
AI:   "Bitcoin is currently in a 'trending_up' regime with 78% confidence. 
       ADX: 32 (strong trend). Volatility percentile: 65th (elevated). 
       Recommended strategies: momentum, breakout. Current allocation: 
       12% of crypto portfolio. Risk multiplier: 1.0x (normal)."

User: "How did the Fed rate decision affect our gold positions?"
AI:   "The Fed held rates steady on June 12. Gold (XAU/USD) reacted with 
       a +1.2% move. Our gold trend-following strategy was already long 
       with a 3.5% unrealized gain. The strategy's exit rule (trailing 
       stop at 5%) was not triggered. Fed events have historically caused 
       2-3% moves in gold within 24h; our strategy is designed to capture 
       these. Backtest: 78% win rate around Fed days over 5 years."
```

---

## 13. Implementation Roadmap

### 13.1 Phase 0: Foundation (Weeks 1-4)

**Goal:** Establish infrastructure and validate data pipeline

| Week | Task | Deliverable | Status |
|------|------|-------------|--------|
| 1 | Project structure + Docker Compose | Running TimescaleDB, PostgreSQL, Redis | Pending |
| 1 | Database schemas | All tables created and migrated | Pending |
| 2 | MarketDataProvider abstraction | Interface + Yahoo Finance implementation | Pending |
| 2 | Data download scripts | 10-year Nifty 50 + top 20 stocks | Pending |
| 3 | Data normalization pipeline | Canonical schema, gap detection | Pending |
| 3 | Corporate action adjustment | Split/dividend adjusted prices | Pending |
| 4 | Validation framework | Data quality reports, completeness checks | Pending |

### 13.2 Phase 1: Backtesting Engine (Weeks 5-8)

**Goal:** Build and validate the backtesting infrastructure

| Week | Task | Deliverable | Status |
|------|------|-------------|--------|
| 5 | VectorBT integration | Basic backtest runner with costs | Pending |
| 5 | Walk-forward framework | Rolling window implementation | Pending |
| 6 | Regime detection | HMM + rule-based classifier | Pending |
| 6 | Statistical tests | DSR, White's RC, RAS | Pending |
| 7 | First strategy implementation | Nifty 50 6-month momentum | Pending |
| 7 | Walk-forward validation | 2021-2024 test, results analysis | Pending |
| 8 | Performance reporting | Metrics dashboard, reports | Pending |

### 13.3 Phase 2: Strategy Research (Weeks 9-12)

**Goal:** Develop and validate 3-5 strategy candidates

| Week | Task | Deliverable | Status |
|------|------|-------------|--------|
| 9 | Equity strategy 2 | Intraday ORB + VWAP | Pending |
| 9 | Equity strategy 3 | Mean reversion (range-bound filter) | Pending |
| 10 | Options strategy 1 | Weekly iron condor (data permitting) | Pending |
| 10 | Options strategy 2 | Pre-event straddle | Pending |
| 11 | Strategy registry | All strategies parameterized and versioned | Pending |
| 11 | Cross-strategy correlation analysis | Uncorrelated strategy portfolio | Pending |
| 12 | Strategy comparison report | Performance, Sharpe, drawdown matrix | Pending |

### 13.4 Phase 3: Intelligence Layer (Weeks 13-16)

**Goal:** Integrate news, sentiment, and forecasting

| Week | Task | Deliverable | Status |
|------|------|-------------|--------|
| 13 | News ingestion pipeline | RSS feeds + dedup + scheduler | Pending |
| 13 | Sentiment analysis | FinBERT integration, scoring | Pending |
| 14 | Sector aggregation | Nifty-weighted sentiment | Pending |
| 14 | Signal detection | Sentiment spikes, sector reversals | Pending |
| 15 | Forecasting models | LSTM baseline for Nifty 50 | Pending |
| 15 | Regime detection integration | ML-based regime classifier | Pending |
| 16 | Intelligence dashboard | News, sentiment, forecasts UI | Pending |

### 13.5 Phase 4: Risk & Learning (Weeks 17-20)

**Goal:** Dynamic risk management and outcome-based learning

| Week | Task | Deliverable | Status |
|------|------|-------------|--------|
| 17 | Risk manager module | Position sizing, kill switches | Pending |
| 17 | Regime-aware risk | VIX/volatility adjustment | Pending |
| 18 | Outcome recorder | Trade logging, attribution | Pending |
| 18 | Performance attribution | Strategy, regime, event breakdown | Pending |
| 19 | Knowledge graph | Neo4j or PostgreSQL graph | Pending |
| 19 | RAG pipeline | Query understanding, retrieval | Pending |
| 20 | Answerable AI interface | Chat UI, natural language queries | Pending |

### 13.6 Phase 5: Integration & Forward Testing (Weeks 21-24)

**Goal:** End-to-end system, forward test on 2024-2025 data

| Week | Task | Deliverable | Status |
|------|------|-------------|--------|
| 21 | Forward test framework | Simulated live trading on 2024-2025 | Pending |
| 21 | Paper trading simulation | Execution simulation, slippage | Pending |
| 22 | Backtest vs forward test comparison | Performance parity analysis | Pending |
| 22 | Strategy adaptation | Regime-based switching logic | Pending |
| 23 | Dashboard completion | Full monitoring UI | Pending |
| 23 | Automated reports | Daily pre-market, weekly review | Pending |
| 24 | System integration test | End-to-end validation | Pending |

### 13.7 Phase 6: US Equities (Weeks 25-32)

**Goal:** Expand to US markets with proven strategies

| Week | Task | Deliverable |
|------|------|-------------|
| 25-26 | US data pipeline | Yahoo Finance, Alpha Vantage, Polygon.io integration |
| 26-27 | US equity strategies | Momentum, mean reversion adapted for US markets |
| 27-28 | US options strategies | SPX/NDX options strategies |
| 28-29 | Regime detection for US | Fed policy regime classifier |
| 29-30 | Walk-forward validation | 5-year US equity backtest |
| 31-32 | US dashboard & reports | US-specific monitoring |

### 13.8 Phase 7: Crypto + Commodities + European Equities (Weeks 33-40)

**Goal:** Expand to crypto, commodities, and European markets

| Week | Task | Deliverable |
|------|------|-------------|
| 33-34 | Crypto data pipeline | Binance, CoinGecko, on-chain data |
| 34-35 | Crypto strategies | Trend following, arbitrage, on-chain |
| 35-36 | Commodities data | Metals, energy, agricultural futures |
| 36-37 | Commodity strategies | Trend following, carry, spread trading |
| 37-38 | European equities | LSE, XETRA, Euronext data + strategies |
| 38-40 | Cross-asset correlation | Correlation matrix, portfolio optimization |

### 13.9 Phase 8: Fixed Income + Prediction Markets (Weeks 41-48)

**Goal:** Fixed income and prediction market integration

| Week | Task | Deliverable |
|------|------|-------------|
| 41-42 | Fixed income data | FRED, investing.com, bond ETFs |
| 42-43 | Fixed income strategies | Duration, credit spread, carry |
| 43-44 | Prediction market data | Polymarket, Kalshi, Manifold APIs |
| 44-45 | Prediction market strategies | Event trading, arbitrage |
| 45-46 | Macro regime integration | Fed/ECB/RBI policy regime model |
| 47-48 | Multi-asset portfolio | 10+ uncorrelated strategies, optimization |

### 13.10 Phase 9: Global Multi-Asset (Weeks 49-56)

**Goal:** True global multi-asset portfolio

| Week | Task | Deliverable |
|------|------|-------------|
| 49-50 | FX data + strategies | Major pairs, carry trade |
| 50-51 | Asian markets | TSE, HKEX, SGX, ASX integration |
| 51-52 | REITs + alternatives | Global REIT data, strategies |
| 53-54 | Multi-asset optimization | Risk parity, Black-Litterman |
| 55-56 | System hardening | Monitoring, alerting, disaster recovery |

---

## 14. Open Questions & Dependencies

### 14.1 Critical Dependencies

| Dependency | Status | Impact | Resolution Path |
|------------|--------|--------|-----------------|
| Angel One API documentation | Pending | HIGH | User to provide; determines options data availability |
| Historical options data source | Unknown | HIGH | API verification; fallback research |
| Hardware specs (RAM/GPU) | Unknown | MEDIUM | User to provide; affects LLM/model choices |
| Starting capital definition | Pending | MEDIUM | Define for position sizing calibration |
| US market data API selection | Pending | MEDIUM | Evaluate Polygon.io, Alpha Vantage, Yahoo Finance |
| Crypto exchange selection | Pending | MEDIUM | Binance, Coinbase, Kraken evaluation |
| Prediction market API availability | Unknown | LOW | Research Polymarket, Kalshi API limits |

### 14.2 Technical Decisions Required

| Decision | Options | Recommendation | Status |
|----------|---------|---------------|--------|
| Graph Database | Neo4j vs PostgreSQL | Start with PostgreSQL + pgvector; add Neo4j if graph queries become complex | Pending |
| Workflow Orchestrator | Prefect vs Airflow vs none | Start with simple scheduler (APScheduler); add Prefect when pipelines scale | Pending |
| LLM Model | Llama 3 vs DeepSeek-R1 vs others | Llama 3 8B for speed; DeepSeek-R1 for reasoning tasks | Pending |
| Options Backtesting | VectorBT vs Backtrader | Backtrader for multi-leg options execution simulation | Pending |
| Crypto Data Storage | TimescaleDB vs InfluxDB vs In-memory | TimescaleDB for consistency; in-memory cache for real-time | Pending |
| ML Experiment Tracking | MLflow vs Weights & Biases vs none | Start with MLflow (open-source); W&B if scaling | Pending |
| Message Queue | Redis Streams vs RabbitMQ vs Kafka | Redis Streams for simplicity; Kafka if event volume scales | Pending |

### 14.3 Research Questions

1. **Options Data**: Can Angel One SmartAPI provide historical options chains with IV/Greeks for backtesting? If not, what are affordable alternatives?
2. **Strategy Count**: How many strategies should the initial "zoo" contain? Recommendation: 3-5 equity + 2-3 options initially, expanding to 15-20 globally.
3. **Regime Detection**: Should regime detection be rule-based (faster, interpretable) or ML-based (more adaptive)?
4. **Learning Frequency**: How often should the system attempt strategy improvement? Daily? Weekly? Monthly?
5. **Crypto Custody**: If live deployment happens, how to handle crypto custody? (Hardware wallet, exchange custody, self-custody)
6. **Prediction Market Liquidity**: Are prediction markets liquid enough for meaningful position sizes?
7. **Cross-Asset Hedging**: Should the system implement cross-asset hedges (e.g., gold hedge for equity risk)?


---

## 15. Success Metrics & KPIs

### 15.1 Technical Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Data pipeline uptime | > 99% | Daily ingestion success rate |
| Backtest execution time | < 5 min for 10-year test | VectorBT benchmark |
| Walk-forward cycles completed | 10+ per strategy | Validation reports |
| Strategy code coverage | > 80% | Unit tests |
| API response time | < 200ms | FastAPI benchmarks |
| Dashboard load time | < 3 seconds | Browser timing |
| Knowledge graph query response | < 1 second | Neo4j/PostgreSQL benchmarks |
| LLM response time | < 5 seconds | Ollama inference time |
| Data freshness | < 5 minutes for live data | Timestamp delta |

### 15.2 Strategy Performance Metrics

| Metric | Minimum | Target | Stretch |
|--------|---------|--------|---------|
| Sharpe Ratio (in-sample) | 0.8 | 1.2 | 1.5 |
| Sharpe Ratio (out-of-sample) | 0.5 | 1.0 | 1.3 |
| Maximum Drawdown | < 25% | < 20% | < 15% |
| Win Rate | > 45% | > 50% | > 55% |
| Profit Factor | > 1.3 | > 1.5 | > 2.0 |
| Recovery Factor | > 0.5 | > 1.0 | > 1.5 |
| Information Ratio | > 0.3 | > 0.5 | > 0.8 |
| Alpha (vs benchmark) | > 2% annual | > 5% annual | > 8% annual |

### 15.3 System Health Metrics

| Metric | Target |
|--------|--------|
| Strategy validation cycle time | < 2 weeks from idea to deployment |
| Explainability coverage | 100% of trades |
| False signal rate | < 30% |
| Strategy retirement rate | < 20% per quarter (too high = unstable) |
| Learning improvement rate | Positive DSR trend over 6 months |
| Data source redundancy | At least 2 sources per asset class |

---

## 16. Appendices

### 16.1 Glossary

| Term | Definition |
|------|------------|
| Walk-Forward Validation | Rolling optimization and testing methodology that simulates real trading |
| Deflated Sharpe Ratio | Sharpe ratio adjusted for multiple testing bias |
| Regime | Distinct market condition (trending, range-bound, volatile) |
| Kelly Criterion | Mathematical formula for optimal position sizing |
| VectorBT | Vectorized Python backtesting library |
| TimescaleDB | PostgreSQL extension for time-series data |
| GraphRAG | Retrieval-Augmented Generation using knowledge graphs |
| OHLCV | Open, High, Low, Close, Volume |
| IV | Implied Volatility |
| Greeks | Delta, Gamma, Theta, Vega, Rho — options risk measures |
| STT | Securities Transaction Tax (India) |
| VIX | Volatility Index (India VIX for NSE) |
| ADX | Average Directional Index — trend strength indicator |
| HMM | Hidden Markov Model — regime detection |
| DSR | Deflated Sharpe Ratio |
| VaR | Value at Risk |
| CVaR | Conditional Value at Risk (Expected Shortfall) |
| MiFID II | Markets in Financial Instruments Directive (EU regulation) |
| SEC | Securities and Exchange Commission (US regulator) |
| SEBI | Securities and Exchange Board of India |
| API | Application Programming Interface |
| RAG | Retrieval-Augmented Generation |
| NLP | Natural Language Processing |
| NER | Named Entity Recognition |
| NVT | Network Value to Transactions (crypto metric) |
| LSTM | Long Short-Term Memory (neural network) |
| TFT | Temporal Fusion Transformer |
| GARCH | Generalized AutoRegressive Conditional Heteroskedasticity |

### 16.2 Reference Materials

**Books:**

- "Machine Learning for Trading" — Stefan Jansen (3rd ed)
- "The Man Who Solved the Market" — Gregory Zuckerman
- "Advances in Financial Machine Learning" — Marcos López de Prado
- "Technical Analysis of the Financial Markets" — John Murphy
- "Trading and Exchanges" — Larry Harris
- "A Man for All Markets" — Edward Thorp
- "The Laws of Trading" — Agustin Lebron

**Papers:**

- Bailey & López de Prado (2014) — "The Deflated Sharpe Ratio"
- Pardo (1992, 2008) — Walk-forward optimization
- Aronson (2006) — "Evidence-Based Technical Analysis"
- López de Prado (2018) — "The 10 Reasons Most ML Funds Fail"
- Harvey et al. (2016) — "…and the Cross-Section of Expected Returns"

**Tools & Libraries:**

- VectorBT: https://vectorbt.dev/
- Backtrader: https://www.backtrader.com/
- TimescaleDB: https://www.timescale.com/
- Ollama: https://ollama.ai/
- GraphRAG: https://github.com/microsoft/graphrag
- FinBERT: https://huggingface.co/ProsusAI/finbert
- Darts: https://unit8co.github.io/darts/
- PyTorch Forecasting: https://pytorch-forecasting.readthedocs.io/
- Streamlit: https://streamlit.io/
- FastAPI: https://fastapi.tiangolo.com/

### 16.3 Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-08-13 | Kilo | Initial comprehensive document |
| 1.1 | 2026-08-13 | Kilo | Expanded global scope, all asset classes, multi-market support |

---

**END OF MASTER TECHNICAL REQUIREMENTS DOCUMENT v1.1**
