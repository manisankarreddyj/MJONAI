"""
Registry Adapter - the bridge between the LIVE strategy suite and research.

The strategies in strategy/registry are the ones that actually trade.
This module lets the research backtester run THOSE directly, so every
research number describes a strategy that exists in production.

The adapter is a pure translator: it changes no logic on either side.

Backtestability gating (2026-09-20): a registry strategy gets a research
bridge ONLY when its signal math is reproducible from the daily OHLCV
frame the research pipeline feeds it — no network calls at signal time
and no fabricated inputs. S15 (FII Short Squeeze) and S17 (Order Flow
Micro-Price) are deliberately NOT registered: S15 calls the live
participant-OI endpoint inside ``generate_signal`` (a per-bar network hit
whose offline default never trips the trap), and S17 invents a bid/ask
order book when no microstructure snapshot is supplied. Both stay gated
until their real data sources are wired through ``precomputed_indicators``.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import pandas as pd

from mjonai.research.optimization.models import (
    ParameterDefinition,
    ParameterSet,
)
from mjonai.research.strategy import Strategy, StrategyResult

logger = logging.getLogger(__name__)


# Live-market context values that registry strategies expect but do not
# use in their signal math (they are echoed into metadata only). Neutral
# placeholders keep historical runs deterministic.
NEUTRAL_VIX: float = 13.5
NEUTRAL_MARKET_STATE: str = "NEUTRAL"
NEUTRAL_MQI_LEVEL: str = "NEUTRAL"

BACKTESTABLE_DIRECTIONS = ("LONG", "SHORT")

# Default location of the F&O EOD chain warehouse (built by
# apps/research/run_fno_backfill.py). Read through `load_eod_chain_for_date`,
# which fails CLOSED when the warehouse (or the date/underlying) is absent —
# a missing chain must never fabricate a gamma level.
DEFAULT_FNO_CHAIN_DIR: str = os.path.join("storage", "parquet", "fno_chain")

# Registry strategies whose signal math consumes real option-chain inputs
# via `precomputed_indicators`. S13 (Gamma Flip) reads zero_gamma_level /
# total_gex_crores; other strategies must be added here only once their live
# chain source is wired the same way.
CHAIN_AWARE_STRATEGIES: frozenset[str] = frozenset({"S13_GammaFlip"})


# ── Walk-forward search spaces ───────────────────────────────────────────────
# Keys are UPPERCASE class-attribute names (the names `configure` sets).
# Strategies not listed keep the single-point default (current class value).
# Grids are deliberately small — S01 is sample-starved on daily bars and a
# full cross-product of all 13 params would be infeasible.  These 4 high-
# leverage thresholds give the walk-forward optimizer a real search while
# keeping the grid at 3⁴ = 81 cells per training window.
REGISTRY_PARAMETER_GRIDS: dict[str, dict[str, list]] = {
    "S01_MomentumRSI": {
        "RSI_MIN": [50.0, 55.0, 60.0],
        "ADX_MIN_STRENGTH": [15.0, 20.0, 25.0],
        "RVOL_MIN_THRESHOLD": [1.20, 1.35, 1.50],
        "DONCHIAN_PERIOD": [15, 20, 25],
    },
}


class RegistryStrategyAdapter(Strategy):
    """
    Wraps one live `strategy.registry.BaseStrategy` so the research
    pipeline (runner -> simulator -> analytics) can execute it.

    Signal semantics: a registry strategy evaluates the LAST bar of the
    frame it is given, exactly like the research runner expects - a
    signal fires on the completed bar and the backtester fills at the
    NEXT bar's open.
    """

    def __init__(
        self,
        registry_strategy: Any,
        *,
        symbol: str = "",
        fno_chain_dir: Optional[str] = None,
    ):

        self._s = registry_strategy

        self.symbol = symbol
        self._fno_chain_dir = fno_chain_dir or DEFAULT_FNO_CHAIN_DIR
        self._chain_loader = None  # lazy import; resolved on first use

    # ── Identity ─────────────────────────────────────────────────────────────

    @property
    def name(
        self,
    ) -> str:

        return str(
            getattr(self._s, "name", self._s.__class__.__name__)
        )

    @property
    def version(
        self,
    ) -> str:

        return str(
            getattr(self._s, "version", "?")
        )

    @property
    def timeframe(
        self,
    ) -> str:

        return str(
            getattr(self._s, "timeframe", "")
        )

    @property
    def description(
        self,
    ) -> str:

        try:
            return str(self._s.get_description())
        except Exception:
            return ""

    @property
    def asset_class(
        self,
    ) -> str:

        return str(
            getattr(self._s, "asset_class", "EQUITY")
        )

    @property
    def min_bars(
        self,
    ) -> int:

        return int(
            getattr(self._s, "min_candles_required", 200)
        )

    # ── Research optimization hooks ──────────────────────────────────────────

    @staticmethod
    def _resolve_attr_name(strategy, key: str) -> str | None:
        """Map a `get_parameters()` key (snake_case) to the settable class
        attribute name (UPPER_CASE).  Returns None when no class attribute
        matches — those keys are not settable and must not appear in the grid."""
        cls = type(strategy)
        if hasattr(cls, key):
            return key
        upper = key.upper()
        if hasattr(cls, upper):
            return upper
        return None

    @property
    def parameters(
        self,
    ) -> list[ParameterDefinition]:
        """
        Expose the strategy's current numeric parameters as a search grid.

        Names are resolved to UPPER_CASE class attributes so ``configure``
        can apply them (the registry convention).  Strategies listed in
        ``REGISTRY_PARAMETER_GRIDS`` get widened multi-point grids for
        walk-forward parameter search; others keep a single-point default.

        Historical note: the original property emitted snake_case keys from
        ``get_parameters()`` but ``configure`` matched against UPPERCASE
        class attributes via ``hasattr`` — a silent no-op.  This is fixed
        by resolving names here before building the grid.
        """

        grid: list[ParameterDefinition] = []

        try:
            current = self._s.get_parameters() or {}
        except Exception:
            current = {}

        search_space = REGISTRY_PARAMETER_GRIDS.get(self.name, {})

        for key, value in current.items():

            if isinstance(value, bool):
                continue

            if not isinstance(value, (int, float)):
                continue

            attr_name = self._resolve_attr_name(self._s, key)
            if attr_name is None:
                continue

            if attr_name in search_space:
                grid.append(
                    ParameterDefinition(
                        name=attr_name,
                        values=search_space[attr_name],
                    )
                )
            else:
                grid.append(
                    ParameterDefinition(
                        name=attr_name,
                        values=[value],
                    )
                )

        return grid

    def configure(
        self,
        parameter_set: ParameterSet,
    ) -> None:
        """
        Apply scalar parameters as INSTANCE-level shadows of the
        registry strategy's class attributes (the registry convention,
        e.g. RSI_MIN, EMA_SHORT).

        Instance shadows matter: registry strategies store parameters
        on the class, so writing the class directly would leak values
        across walk-forward windows and symbols. Shadowing on the
        instance keeps every configured copy isolated.
        Unknown keys are ignored silently - grids may carry extra keys.
        """

        for key, value in parameter_set.values.items():

            if hasattr(type(self._s), key):

                setattr(self._s, key, value)

    # ── Signal translation ───────────────────────────────────────────────────

    def _chain_precomputed(
        self,
        data: pd.DataFrame,
    ) -> dict[str, float] | None:
        """
        Resolve REAL option-chain inputs for chain-aware strategies (S13
        Gamma Flip) from the local F&O EOD warehouse, keyed on the decision
        bar's date. Fail-closed by design: no warehouse, no symbol, no chain
        row for that date, or any math error returns None — the registry
        strategy then takes its own honest fallback (S13's EMA-20 proxy).
        Nothing here can fabricate a gamma level from empty data.
        """
        if self.name not in CHAIN_AWARE_STRATEGIES:
            return None
        symbol = (self.symbol or "").strip().upper()
        if not symbol:
            return None
        if data is None or data.empty:
            return None

        if self._chain_loader is None:
            try:
                from mjonai.research.data.fno_eod import load_eod_chain_for_date
                self._chain_loader = load_eod_chain_for_date
            except Exception as exc:
                logger.warning("[registry_adapter] chain loader unavailable: %s", exc)
                self._chain_loader = False
        if not self._chain_loader:
            return None

        decision_date = data.index[-1]
        try:
            frame = self._chain_loader(
                self._fno_chain_dir,
                symbol,
                decision_date,
            )
            if frame is None or frame.empty:
                return None
            return self._chain_to_precomputed(
                frame,
                decision_date=decision_date,
                fallback_spot=float(data["Close"].iloc[-1]),
            )
        except Exception as exc:
            logger.warning(
                "[registry_adapter] %s chain lookup %s failed closed: %s",
                symbol,
                decision_date,
                exc,
            )
            return None

    @staticmethod
    def _chain_to_precomputed(
        frame: pd.DataFrame,
        *,
        decision_date,
        fallback_spot: float,
    ) -> dict[str, float] | None:
        """
        Convert the nearest-expiry option chain rows for one underlying+day
        into the S13 precomputed gamma inputs (zero_gamma_level /
        total_gex_crores) via the canonical GEX engine. Returns None when the
        day's chain cannot form a GEX input (no strikes, no OI, no spot) —
        again fail-closed, never a fabricated level.
        """
        import numpy as np

        from mjonai.data.derivatives.gex_engine import calculate_gamma_exposure

        if frame.empty or "strike" not in frame or "oi" not in frame:
            return None

        opt_type = frame["option_type"].astype(str).str.upper().str.strip()
        ce = pd.to_numeric(
            frame.loc[opt_type == "CE", "oi"], errors="coerce"
        ).groupby(frame.loc[opt_type == "CE", "strike"]).sum()
        pe = pd.to_numeric(
            frame.loc[opt_type == "PE", "oi"], errors="coerce"
        ).groupby(frame.loc[opt_type == "PE", "strike"]).sum()
        strikes = sorted(
            {float(k) for k in set(ce.index) | set(pe.index) if pd.notna(k) and k > 0}
        )
        if not strikes:
            return None

        strip_price = pd.Timestamp(decision_date).normalize()
        expiries = pd.to_datetime(frame["expiry"]).dt.normalize()
        valid = expiries > strip_price
        dte_days = (
            max(1.0, float((expiries[valid].min() - strip_price).days))
            if valid.any()
            else 1.0
        )

        spot_candidates = pd.to_numeric(frame["underlying_price"], errors="coerce")
        spot_candidates = spot_candidates[spot_candidates > 0]
        spot = (
            float(spot_candidates.median())
            if not spot_candidates.empty
            else float(fallback_spot or 0.0)
        )
        if spot <= 0.0:
            return None

        ce_oi = ce.reindex(strikes).fillna(0.0)
        pe_oi = pe.reindex(strikes).fillna(0.0)
        if not bool(ce_oi.max() > 0) and not bool(pe_oi.max() > 0):
            return None

        lot = pd.to_numeric(frame["lot_size"], errors="coerce").dropna()
        lot_size = int(lot.median()) if not lot.empty else 65
        if lot_size <= 0:
            lot_size = 65

        try:
            snapshot = calculate_gamma_exposure(
                underlying=str(frame["underlying"].iloc[0]),
                spot_price=spot,
                strikes=list(strikes),
                call_oi=list(ce_oi.values),
                put_oi=list(pe_oi.values),
                dte_days=dte_days,
                lot_size=lot_size,
            )
        except Exception as exc:
            logger.warning("[registry_adapter] GEX math failed closed: %s", exc)
            return None

        if snapshot is None:
            return None
        zgl = snapshot.zero_gamma_level
        if zgl is None:
            # engine resorts to spot when no root is found; treat absence
            # honestly — S13 must not build a flip claim on a non-root.
            return None
        return {
            "zero_gamma_level": float(zgl),
            "total_gex_crores": float(snapshot.total_gex_crores),
        }

    def generate_signal(
        self,
        data: pd.DataFrame,
    ) -> StrategyResult | None:

        raw = self._s.generate_signal(
            df=data,
            symbol=self.symbol or "",
            vix=NEUTRAL_VIX,
            market_state=NEUTRAL_MARKET_STATE,
            mqi_level=NEUTRAL_MQI_LEVEL,
            precomputed_indicators=self._chain_precomputed(data),
        )

        if raw is None:
            return None

        fields = self._as_fields(raw)

        direction = str(fields.get("signal_direction", ""))

        if direction not in BACKTESTABLE_DIRECTIONS:
            # NON_DIRECTIONAL (e.g. options income) has no spot
            # long/short translation - skipped honestly.
            return None

        return StrategyResult(
            symbol=self.symbol or "",
            strategy_id=self.name,
            signal=direction,
            score=float(
                fields.get("technical_score", 0.0) or 0.0
            ),
            index=len(data) - 1,
            metadata={
                key: fields[key]
                for key in (
                    "confidence",
                    "entry_price",
                    "swing_low",
                    "swing_high",
                    "atr",
                    "adx",
                )
                if fields.get(key) is not None
            },
        )

    @staticmethod
    def _as_fields(
        raw: Any,
    ) -> dict[str, Any]:

        if isinstance(raw, dict):

            return raw

        if hasattr(raw, "to_dict"):

            return raw.to_dict()

        return {
            key: getattr(raw, key)
            for key in (
                "signal_direction",
                "technical_score",
                "confidence",
                "entry_price",
                "swing_low",
                "swing_high",
                "atr",
                "adx",
            )
            if hasattr(raw, key)
        }


# ── Registry loading ─────────────────────────────────────────────────────────

REGISTRY_STRATEGY_IDS: dict[str, str] = {
    "S01_MomentumRSI": "MomentumRSI",
    "S02_MeanReversion": "MeanReversion",
    "S03_TurtleBreakout": "TurtleBreakout",
    "S04_BollingerSqueeze": "BollingerSqueeze",
    "S05_PriceAction": "PriceActionCandles",
    "S06_MomentumShort": "MomentumShort",
    "S07_MeanReversionShort": "MeanReversionShort",
    "S08_IntradayAllDay": "IntradayAllDayStrategy",
    "S09_OptionsThetaDecay": "OptionsThetaDecay",
    "S10_PairsTrading": "PairsTrading",
    "S11_VolumeProfile": "VolumeProfileStrategy",
    "S12_MacroCommodityCrypto": "MacroCommodityCrypto",
    "S13_GammaFlip": "GammaFlipStrategy",
    "S14_PostEarningsDrift": "PostEarningsDriftStrategy",
    "S16_CrossSectionalMomentum": "CrossSectionalMomentumStrategy",
    "S18_GapFillFVG": "GapFillAndFVGStrategy",
}

# Registry strategies that MUST NOT be run through research today, with the
# reason (mirrored in the research CLIs' help). Wiring them would violate
# the validation contract: a backtest number must describe the real strategy's
# signal math on daily OHLCV, with no per-bar network access and no fabricated
# inputs. Both become backtestable once their live data source is injected via
# `precomputed_indicators` (GEX/participant-OI engine; microstructure feed).
RESEARCH_DATA_GATED: dict[str, str] = {
    "S15_FIIShortSqueeze": (
        "calls fetch_live_nse_participant_oi() inside generate_signal (per-bar "
        "network hit); offline default fii_ratio=0.20 can never trip the "
        "<=0.15 trap, so research would report a dead strategy."
    ),
    "S17_OrderFlowMicroPrice": (
        "invents a bid/ask order book (hardcoded ±0.05 / 60k:20k lots) when no "
        "microstructure snapshot is supplied, so research signals would come "
        "from fabricated Level-2 data."
    ),
}


def available_registry_strategies() -> list[str]:
    """Backtestable registry strategies (excludes RESEARCH_DATA_GATED ids so a
    misleading backtest is impossible rather than merely discouraged)."""
    return sorted(REGISTRY_STRATEGY_IDS)


def load_registry_strategy(
    strategy_id: str,
    *,
    symbol: str = "",
) -> RegistryStrategyAdapter:
    """
    Load a LIVE registry strategy wrapped for research, by its S-Id.
    Raises ValueError for unknown ids.
    """

    class_name = REGISTRY_STRATEGY_IDS.get(strategy_id)

    if class_name is None:

        raise ValueError(
            f"Unknown registry strategy: {strategy_id}. "
            f"Available: {', '.join(available_registry_strategies())}"
        )

    import mjonai.strategy.registry as registry
    strategy_class = getattr(registry, class_name)

    return RegistryStrategyAdapter(
        strategy_class(),
        symbol=symbol,
    )
