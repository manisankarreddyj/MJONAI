# MJONAI Master Architecture & Repository Structure

**State**: 100% Consolidated, Fully Modularized, Production Ready.
**Vault Status**: Completely Drained and Removed. Zero dead code or legacy clutter.

---

## 1. Master Repository Overview (`d:\MJONAI`)

```
d:\MJONAI\
├── credentials\             ← Master API keys & configuration (.env.master)
├── docs\                    ← Architecture summaries & technical specifications
├── mjonai-build\            ← Live & Paper Execution Engine (24/7 autonomous runtime)
├── mjonai-dashboard\        ← FastAPI Backend + Next.js 14 Frontend UI
├── mjonai-research\         ← Quantitative Backtesting & Walk-Forward Optimization
└── README.md                ← Master repository index
```

---

## 2. Production Subsystems Breakdown

### A. `mjonai-build` (Core Execution Engine)
- **`main.py`**: 24/7 master orchestrator and IST market scheduler.
- **`db/`**: 7 single-responsibility database submodules (`trades.py`, `signals.py`, `agents.py`, `snapshots.py`, `patterns.py`, `system.py`, `client.py`) + `repository.py` facade.
- **`execution/`**: 4 modular order execution submodules (`orders.py`, `tracker.py`, `tax.py`, `eod.py`) with Indian FIFO STCG (20%) / LTCG (12.5%) lot tracking.
- **`risk/`**:
  - `devil_checks.py`: Deterministic 8-check pre-trade veto engine.
  - `gap_risk.py`: GARCH overnight gap volatility distribution model.
  - `behavioral_guard.py`: Revenge trade blocker (30-min cooldown after 2 consecutive stop-outs).
  - `special_modes.py`: Crisis mode (flash crash/VIX > 28), Budget day blackout (Feb 1), and Expiry day scaling.
  - `emergency_triggers.py`: Portfolio risk manager (Risk Stop, Soft Stop, Kill Line).
- **`agents/`**: 3-Agent Adversarial Debate Room:
  - `bull.py`: Bull Conviction agent.
  - `bear.py`: Bear Risk Skeptic agent.
  - `supervisor.py`: Supervisor Gatekeeper with deterministic consensus scoring.
- **`strategy/`**: 8 Quantitative Strategies:
  - `S01_MomentumRSI`, `S02_MeanReversion`, `S03_TurtleBreakout`, `S04_BollingerSqueeze`, `S05_PriceAction`, `S06_MomentumShort`, `S07_MeanReversionShort`, `S08_IntradayAllDay` (All-day consolidation & scalping).
- **`options/`**: Options Intelligence Suite:
  - `greeks.py`: Black-Scholes analytical Greeks ($\Delta, \Gamma, \Theta, \mathcal{V}$) and Newton-Raphson IV solver.
  - `chain_engine.py`: Put-Call Ratio (PCR), Max Pain Strike, 1-SD expected move, and optimal strike selection.
  - `oi_scanner.py`: Live Option Chain Call/Put unwinding & institutional flow detector.
  - `directional_options.py`: Directional Index & Stock Options trading engine.
- **`intelligence/`**:
  - `gift_nifty.py`: Pre-market Gift Nifty (SGX) gap analyzer.
  - `fii_dii.py`: Foreign & Domestic institutional net money flow analyzer.
  - `sector_rotation.py`: NSE Sectoral relative strength and rotation matrix.
- **`knowledge/`**:
  - `principles.py`: Curated quant wisdom (Weinstein, Taleb, Lopez de Prado, Douglas, Simons).
  - `retriever.py`: Fast semantic tag and keyword principle matcher.
  - `explainability.py`: Human-readable trade rationale and post-mortem generator.
- **`analytics/`**:
  - `statistical_validation.py`: Deflated Sharpe Ratio (DSR), White's Reality Check, and Monte Carlo 1,000x reshuffling.
- **`communication/`**: Telegram instant alerts and interactive bot commands.
- **`data/`**: Angel One WebSocket stream, Token map, and historical 1m–1d candle engine.

---

### B. `mjonai-dashboard` (Web Interface)
- **`backend/`**: FastAPI service (`app.py`, `auth.py`, `websocket_manager.py`).
- **`frontend_src/`**: Next.js 14 Web UI with live pages (`/signals`, `/options`, `/market`, `/performance`, `/portfolio`, `/paper-trading`, `/assistant`, `/watchlist`, `/system`).

---

### C. `mjonai-research` (Backtesting & Research Engine)
- Vectorized walk-forward testing engine, DuckDB trade logging, and parameter grid optimization.
