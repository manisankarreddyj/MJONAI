"""
Module: configs/strategy_config.py
Purpose: YAML-based declarative strategy/fund configuration system.
         Inspired by ai-hedge-fund's StrategySpec/BlendPolicy/FundSpec.
         Allows defining strategies, blends, and mandates in YAML without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Type, Union
from typing import get_args

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mjonai.strategy.registry import BaseStrategy
from mjonai.strategy.registry import (
    MomentumRSI,
    MeanReversion,
    TurtleBreakout,
    BollingerSqueeze,
    PriceActionCandles,
    MomentumShort,
    MeanReversionShort,
    IntradayAllDayStrategy,
    OptionsThetaDecay,
    PairsTrading,
    VolumeProfileStrategy,
    MacroCommodityCrypto,
    GammaFlipStrategy,
    PostEarningsDriftStrategy,
    FIIShortSqueezeStrategy,
    CrossSectionalMomentumStrategy,
    OrderFlowMicroPriceStrategy,
    GapFillAndFVGStrategy,
)

# Strategy name to class mapping
STRATEGY_CLASS_MAP: Dict[str, Type[BaseStrategy]] = {
    "S01_MomentumRSI": MomentumRSI,
    "S02_MeanReversion": MeanReversion,
    "S03_TurtleBreakout": TurtleBreakout,
    "S04_BollingerSqueeze": BollingerSqueeze,
    "S05_PriceActionCandles": PriceActionCandles,
    "S06_MomentumShort": MomentumShort,
    "S07_MeanReversionShort": MeanReversionShort,
    "S08_IntradayAllDay": IntradayAllDayStrategy,
    "S09_OptionsThetaDecay": OptionsThetaDecay,
    "S10_PairsTrading": PairsTrading,
    "S11_VolumeProfile": VolumeProfileStrategy,
    "S12_MacroCommodityCrypto": MacroCommodityCrypto,
    "S13_GammaFlip": GammaFlipStrategy,
    "S14_PostEarningsDrift": PostEarningsDriftStrategy,
    "S15_FIIShortSqueeze": FIIShortSqueezeStrategy,
    "S16_CrossSectionalMomentum": CrossSectionalMomentumStrategy,
    "S17_OrderFlowMicroPrice": OrderFlowMicroPriceStrategy,
    "S18_GapFillAndFVG": GapFillAndFVGStrategy,
}

# ── Type Aliases ──────────────────────────────────────────────────────────────

PortfolioMode = Literal["long_only", "long_short", "dollar_neutral"]


# ── Pydantic Models for YAML Schema ──────────────────────────────────────────

class ModelSpec(BaseModel):
    """One signal model in a strategy — a strategy from the registry."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Key into STRATEGY_CLASS_MAP, e.g. 'S01_MomentumRSI'")
    weight: float = Field(default=1.0, gt=0, description="Blend weight")
    params: Dict[str, Any] = Field(default_factory=dict, description="Constructor kwargs for the strategy")

    @field_validator("name")
    @classmethod
    def _declared_approach(cls, name: str) -> str:
        # Verify the model exists in registry
        if name not in STRATEGY_CLASS_MAP:
            raise ValueError(f"Unknown strategy {name!r}; available: {sorted(STRATEGY_CLASS_MAP)}")
        return name


class BlendPolicy(BaseModel):
    """How a strategy's model views combine into one sleeve."""

    model_config = ConfigDict(extra="forbid")

    method: Literal["conviction_weighted", "equal_weight", "signal_count"] = "conviction_weighted"
    gross_target: float = Field(default=1.0, gt=0, description="Desired sum of |weights| when views exist")
    mode: PortfolioMode


class StrategySpec(BaseModel):
    """A strategy ("pod"): signal models plus the policy that blends them."""

    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: Optional[str] = Field(default=None, description="Human-facing name, e.g. 'Deep Value'")
    weight: float = Field(default=1.0, gt=0)
    models: List[ModelSpec] = Field(min_length=1)
    blend: BlendPolicy

    @property
    def title(self) -> str:
        return self.display_name or self.name.replace("-", " ").title()

    @property
    def model_weights(self) -> Dict[str, float]:
        return {m.name: m.weight for m in self.models}


class FundSpec(BaseModel):
    """A mandate with fund-level risk limits and no fixed ticker universe."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    name: str
    strategies: List[StrategySpec] = Field(min_length=1)
    risk: Dict[str, Any] = Field(default_factory=dict)
    capital: float = Field(default=100_000.0, gt=0)
    rebalance: Literal["daily", "weekly", "monthly"] = Field(
        default="weekly",
        description="Rebalance frequency used by the backtester"
    )
    benchmark: str = Field(
        default="NIFTY_50",
        description="What the fund measures itself against"
    )

    @field_validator("benchmark")
    @classmethod
    def _uppercase_benchmark(cls, ticker: str) -> str:
        return ticker.upper()

    @field_validator("strategies")
    @classmethod
    def _unique_strategy_names(cls, strategies: List[StrategySpec]) -> List[StrategySpec]:
        names = [s.name for s in strategies]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(f"Duplicate strategy names: {sorted(duplicates)}")
        return strategies


# ── Loader Functions ──────────────────────────────────────────────────────────

def load_spec(path: str | Path) -> FundSpec:
    """Load a YAML mandate, raising ValueError with path and error details."""
    data = _read_yaml(path)
    if "schema_version" not in data:
        raise ValueError(f"{path}: schema_version: This fund uses an older format. Recreate it or update its configuration.")
    try:
        return FundSpec.model_validate(data)
    except Exception as exc:
        raise ValueError(_validation_message(path, exc)) from exc


def load_strategy(path: str | Path) -> StrategySpec:
    """Load one strategy (a library file) from YAML."""
    try:
        return StrategySpec.model_validate(_read_yaml(path))
    except Exception as exc:
        raise ValueError(_validation_message(path, exc)) from exc


def _read_yaml(path: str | Path) -> Dict[str, Any]:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError(f"{path}: cannot read configuration: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: configuration must be a YAML mapping")
    return data


def _validation_message(path: str | Path, exc: Exception) -> str:
    if hasattr(exc, "errors"):
        errors = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        return f"{path}: {errors}"
    return f"{path}: {exc}"


# ── Strategy Factory from YAML Spec ──────────────────────────────────────────

@dataclass
class StrategyInstance:
    """Constructed strategy instance with metadata."""
    spec: StrategySpec
    strategy: BaseStrategy
    blend_policy: BlendPolicy


def build_strategies_from_spec(
    spec: FundSpec,
    blind: bool = False,
) -> List[StrategyInstance]:
    """
    Build strategy instances from a FundSpec.

    Models are constructed once so their caches survive successive cycles.
    Callers may override with test doubles if needed.

    Args:
        spec: Validated FundSpec
        blind: If True, LLM agents run in blind mode (withholds ticker/industry/date)

    Returns:
        List of (StrategySpec, BaseStrategy instance, BlendPolicy)
    """
    instances = []
    for strategy in spec.strategies:
        staff = []
        for m in strategy.models:
            if m.name not in STRATEGY_CLASS_MAP:
                raise ValueError(f"Unknown model {m.name!r} in strategy {strategy.name!r}; available: {sorted(STRATEGY_CLASS_MAP)}")
            cls = STRATEGY_CLASS_MAP[m.name]
            # Strategies use class attributes for params; instantiate then set
            instance = cls()
            # Apply any YAML-specified params as attribute overrides
            for key, value in m.params.items():
                attr_name = key.upper()
                if hasattr(instance, attr_name):
                    setattr(instance, attr_name, value)
                else:
                    # Store in extra_metadata for runtime access
                    if not hasattr(instance, "extra_metadata"):
                        instance.extra_metadata = {}
                    instance.extra_metadata[key] = value
            # Handle blind mode for LLM agents
            if blind and hasattr(instance, "blind"):
                instance.blind = True
            staff.append(instance)
        instances.append(StrategyInstance(
            spec=strategy,
            strategy=staff[0] if len(staff) == 1 else staff,  # Single strategy or ensemble
            blend_policy=strategy.blend,
        ))
    return instances


# ── Example YAML Templates ──────────────────────────────────────────────────

EXAMPLE_MANDATE = """
schema_version: 2
name: "Example Equity Mandate"
capital: 100000
rebalance: "weekly"
benchmark: "NIFTY_50"
risk:
  max_position_pct: 0.02
  max_daily_loss_pct: 0.03
  max_drawdown_pct: 0.15
strategies:
  - name: "momentum_breakout"
    display_name: "Momentum Breakout"
    weight: 1.0
    models:
      - name: "S01_MomentumRSI"
        weight: 1.0
        params:
          rsi_period: 14
          volume_threshold: 1.5
    blend:
      method: "conviction_weighted"
      gross_target: 1.0
      mode: "long_only"
  - name: "mean_reversion"
    display_name: "Mean Reversion"
    weight: 1.0
    models:
      - name: "S02_MeanReversion"
        weight: 1.0
        params:
          rsi_oversold: 30
          rsi_overbought: 70
    blend:
      method: "conviction_weighted"
      gross_target: 1.0
      mode: "long_only"
"""

EXAMPLE_STRATEGY = """
name: "custom_momentum"
display_name: "Custom Momentum"
weight: 1.0
models:
  - name: "S01_MomentumRSI"
    weight: 1.0
    params:
      rsi_period: 14
  - name: "S03_TurtleBreakout"
    weight: 0.5
    params: {}
blend:
  method: "conviction_weighted"
  gross_target: 1.0
  mode: "long_only"
"""

def write_example_mandate(path: str | Path) -> None:
    """Write an example mandate YAML to disk."""
    Path(path).write_text(EXAMPLE_MANDATE.strip(), encoding="utf-8")


def write_example_strategy(path: str | Path) -> None:
    """Write an example strategy YAML to disk."""
    Path(path).write_text(EXAMPLE_STRATEGY.strip(), encoding="utf-8")


__all__ = [
    "ModelSpec",
    "BlendPolicy",
    "StrategySpec",
    "FundSpec",
    "StrategyInstance",
    "load_spec",
    "load_strategy",
    "build_strategies_from_spec",
    "write_example_mandate",
    "write_example_strategy",
    "EXAMPLE_MANDATE",
    "EXAMPLE_STRATEGY",
    "PortfolioMode",
]