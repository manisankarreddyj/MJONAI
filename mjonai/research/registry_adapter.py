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

    @property
    def parameters(
        self,
    ) -> list[ParameterDefinition]:
        """
        Expose the strategy's current numeric parameters as a single-
        point grid by default. Widen any entry to search real space,
        e.g. ParameterDefinition("RSI_MIN", values=[45.0, 55.0, 65.0]).
        """

        grid: list[ParameterDefinition] = []

        try:
            current = self._s.get_parameters() or {}
        except Exception:
            current = {}

        for key, value in current.items():

            if isinstance(value, bool):
                continue

            if isinstance(value, (int, float)):

                grid.append(
                    ParameterDefinition(
                        name=key,
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
