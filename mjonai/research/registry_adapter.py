"""
Registry Adapter - the bridge between the LIVE strategy suite and research.

The strategies in strategy/registry are the ones that actually trade.
This module lets the research backtester run THOSE directly, so every
research number describes a strategy that exists in production.

The adapter is a pure translator: it changes no logic on either side.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from mjonai.research.optimization.models import (
    ParameterDefinition,
    ParameterSet,
)
from mjonai.research.strategy import Strategy, StrategyResult


# Live-market context values that registry strategies expect but do not
# use in their signal math (they are echoed into metadata only). Neutral
# placeholders keep historical runs deterministic.
NEUTRAL_VIX: float = 13.5
NEUTRAL_MARKET_STATE: str = "NEUTRAL"
NEUTRAL_MQI_LEVEL: str = "NEUTRAL"

BACKTESTABLE_DIRECTIONS = ("LONG", "SHORT")


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
    ):

        self._s = registry_strategy

        self.symbol = symbol

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
}


def available_registry_strategies() -> list[str]:
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
