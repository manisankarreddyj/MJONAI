# -*- coding: utf-8 -*-
"""
Module: research/data/feature_registry.py
Purpose: Feature-specification register — every fitted/derived research
feature is declared once with its inputs, params, version, and leakage
contract, so a later session can audit WHAT was computed FROM what WITHOUT
re-reading every call site.

CONCEPT SOURCE (clean-room): ml4trading's feature-specification register —
reimplemented here as a tiny fail-fast registry (no framework, no new deps).

Rules:
  * Registering a duplicate name with a DIFFERENT spec raises (a silent
    overwrite would let two meanings share one name across sessions).
  * Re-registering the IDENTICAL spec is idempotent (import-safe).
  * Specs are data, not callables: the registry never executes feature code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class FeatureSpec:
    """Declarative contract for one research feature/primitive."""
    name: str
    inputs: Tuple[str, ...] = ()
    params: Tuple[Tuple[str, str], ...] = ()
    version: str = "1.0.0"
    family: str = ""
    leakage_notes: str = ""

    def describe(self) -> str:
        inputs = ", ".join(self.inputs) if self.inputs else "—"
        params = ", ".join(f"{k}={v}" for k, v in self.params) or "—"
        return (
            f"{self.name} v{self.version} [{self.family or 'unfiled'}] "
            f"inputs=({inputs}) params=({params}) :: {self.leakage_notes or 'no leakage note'}"
        )


class FeatureRegistry:
    """Fail-fast registry of FeatureSpecs."""

    def __init__(self) -> None:
        self._specs: Dict[str, FeatureSpec] = {}

    def register(self, spec: FeatureSpec) -> FeatureSpec:
        """Register a spec; identical re-registration is idempotent."""
        if not spec.name or not spec.name.strip():
            raise ValueError("FeatureSpec needs a non-empty name")
        existing = self._specs.get(spec.name)
        if existing is not None:
            if existing == spec:
                return existing
            raise ValueError(
                f"feature '{spec.name}' already registered with a different spec: "
                f"existing={existing.describe()} vs new={spec.describe()}"
            )
        self._specs[spec.name] = spec
        return spec

    def get(self, name: str) -> Optional[FeatureSpec]:
        return self._specs.get(name)

    def list(self, family: Optional[str] = None) -> List[FeatureSpec]:
        specs = sorted(self._specs.values(), key=lambda s: s.name)
        if family is None:
            return specs
        return [s for s in specs if s.family == family]

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._specs

    def __len__(self) -> int:
        return len(self._specs)


FEATURE_REGISTRY = FeatureRegistry()


def register_feature_spec(
    name: str,
    inputs: Tuple[str, ...] = (),
    params: Optional[Dict[str, Any]] = None,
    version: str = "1.0.0",
    family: str = "",
    leakage_notes: str = "",
    registry: Optional[FeatureRegistry] = None,
) -> FeatureSpec:
    """Declare one feature spec on the given (default global) registry."""
    frozen_params = tuple(sorted((str(k), str(v)) for k, v in (params or {}).items()))
    spec = FeatureSpec(
        name=name,
        inputs=tuple(inputs),
        params=frozen_params,
        version=version,
        family=family,
        leakage_notes=leakage_notes,
    )
    # NOTE: `registry or FEATURE_REGISTRY` is WRONG here — an empty registry
    # is falsy via __len__, so an explicit empty registry would silently lose
    # its specs to the global one. Identity check, never truthiness.
    target = FEATURE_REGISTRY if registry is None else registry
    return target.register(spec)


def register_discovery_primitives(registry: Optional[FeatureRegistry] = None) -> List[FeatureSpec]:
    """Declare the 11 discovery-harness primitives (A1–A11) as feature specs.

    These are the bare vectorized `fn(df, params) -> Series`     position
    functions in `mjonai/research/discovery/signals.py` — one layer below a
    strategy (no scoring, stop, regime gate, or evidence layer). Declaring
    them here pins their leakage contract in one auditable place: every
    primitive reads bars ≤ t only, and walk-forward validation applies a
    7-day embargo on top.
    """
    # Same falsiness trap as register_feature_spec: explicit identity check.
    reg = FEATURE_REGISTRY if registry is None else registry
    declared = [
        ("sig_ts_momentum", ("close",), {"window": "12"}, "A1_ts_momentum"),
        ("sig_donchian", ("high", "low", "close"), {"window": "20"}, "A2_donchian"),
        ("sig_sma_cross", ("close",), {"fast": "10", "slow": "30"}, "A3_sma_cross"),
        ("sig_ma_filter_bh", ("close",), {"window": "200"}, "A4_ma_filter_bh"),
        ("sig_vol_target", ("close",), {"window": "20", "target_vol": "0.15"}, "A5_vol_target"),
        ("sig_calendar", ("date",), {}, "A6_calendar"),
        ("sig_dayofweek", ("date",), {}, "A7_dayofweek"),
        ("sig_smc_structure", ("high", "low", "close"), {"swing_length": "20"}, "A8_smc_structure"),
        ("sig_narrow_range", ("high", "low", "close"), {"n": "7", "ma": "5"}, "A9_narrow_range"),
        ("sig_vcp_breakout", ("high", "low", "close"), {"window": "20"}, "A10_vcp_breakout"),
        ("sig_consolidation_breakout", ("high", "low", "close"), {"window": "20"}, "A11_consolidation"),
    ]
    out = []
    for fn_name, inputs, params, family in declared:
        out.append(register_feature_spec(
            fn_name,
            inputs=inputs,
            params=params,
            version="1.0.0",
            family=family,
            leakage_notes=(
                "reads bars <= t only (truncation-equality pinned); "
                "walk-forward applies a 7-day embargo; research-only, never imported by production"
            ),
            registry=reg,
        ))
    return out
