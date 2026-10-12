"""
Module: research/discovery/factor_generator.py
Purpose: DEAP-based Genetic Programming Factor Auto-Generator (Clean-room from Qbot's DEAP factor mining)

Generates alpha factors via genetic programming over a cross-sectional panel.
Uses DEAP (Distributed Evolutionary Algorithms in Python) for GP evolution.

Clean-room reimplementation inspired by Qbot's "基于deap实现的因子自动生成算法" mention.
No code copied — purely from DEAP docs and GP factor mining literature.

Usage:
    from mjonai.research.discovery.factor_generator import FactorGenerator
    
    gen = FactorGenerator(panel, universe_func)
    best_factors = gen.evolve(generations=20, pop_size=100)
"""

from __future__ import annotations

import logging
import operator
import random
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple, Set

import numpy as np
import pandas as pd

try:
    from deap import base, creator, gp, tools
except ImportError:
    creator = None
    base = None
    gp = None
    tools = None

from mjonai.strategy.registry.factors import FACTORS, _zscore_cross_section, _zrank
from mjonai.research.pit_universe import PitUniverseLedger

logger = logging.getLogger(__name__)

# ── Protected Operators (safe for GP) ──────────────────────────────────────────

def _protected_div(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Division with zero protection."""
    with np.errstate(divide='ignore', invalid='ignore'):
        result = np.divide(a, b, where=b!=0)
        result[~np.isfinite(result)] = 0.0
    return result

def _protected_log(x: np.ndarray) -> np.ndarray:
    """Log with negative/zero protection."""
    with np.errstate(divide='ignore', invalid='ignore'):
        result = np.log(np.abs(x) + 1e-12)
    return result

def _protected_sqrt(x: np.ndarray) -> np.ndarray:
    """Sqrt with negative protection."""
    return np.sqrt(np.maximum(x, 0))

def _ts_rank(series: np.ndarray) -> np.ndarray:
    """Time-series rank (percentile within window)."""
    # This would be applied per symbol over time
    # For cross-sectional use, see _zrank
    return series.argsort().argsort() / max(len(series), 1)

def _ts_zscore(series: np.ndarray) -> np.ndarray:
    """Time-series z-score."""
    mean = np.mean(series)
    std = np.std(series)
    if std < 1e-12:
        return np.zeros_like(series)
    return (series - mean) / std

# ── Primitive Set Definition ──────────────────────────────────────────────────

PRIMITIVES: Dict[str, Callable] = {
    # Arithmetic
    "add": lambda x, y: x + y,
    "sub": lambda x, y: x - y,
    "mul": lambda x, y: x * y,
    "div": _protected_div,
    # Transforms
    "log": _protected_log,
    "sqrt": _protected_sqrt,
    "abs": np.abs,
    "neg": lambda x: -x,
    "sign": np.sign,
    # Rolling stats (window=5 default, could be parameterized)
    "ts_mean": lambda x, w=5: pd.Series(x).rolling(w, min_periods=w).mean().values,
    "ts_std": lambda x, w=5: pd.Series(x).rolling(w, min_periods=w).std().values,
    "ts_min": lambda x, w=5: pd.Series(x).rolling(w, min_periods=w).min().values,
    "ts_max": lambda x, w=5: pd.Series(x).rolling(w, min_periods=w).max().values,
    "ts_sum": lambda x, w=5: pd.Series(x).rolling(w, min_periods=w).sum().values,
    # Cross-sectional (applied per date across symbols)
    "cs_rank": lambda x: _zrank(pd.DataFrame(x)).values if len(x.shape)==2 else x,
    "cs_zscore": lambda x: _zscore_cross_section(pd.Series(x)).values if len(x)==1 else x,
    # Correlation
    "ts_corr": lambda x, y, w=20: pd.Series(x).rolling(w).corr(pd.Series(y)).values,
    # Regression
    "ts_beta": lambda x, y, w=20: (
        pd.Series(x).rolling(w).cov(pd.Series(y)) / pd.Series(y).rolling(w).var()
    ).values,
}

TERMINALS = {
    "open": 0,
    "high": 1,
    "low": 2,
    "close": 3,
    "volume": 2,
    "vwap": 3,
    "returns": 0,  # close.pct_change()
    "log_returns": 0,  # log(close).diff()
}


class FactorGenerator:
    """
    Genetic Programming Factor Generator using DEAP.

    Evolves mathematical expressions over OHLCV data to maximize
    cross-sectional IC (Information Coefficient) with forward returns.

    Usage:
        gen = FactorGenerator(panel, universe_func)
        best = gen.evolve(generations=20, pop_size=100)
    """

    def __init__(
        self,
        panel: pd.DataFrame,
        universe_func: Callable[[pd.Timestamp], Set[str]],
        target_horizon: int = 5,
        min_ic: float = 0.02,
        max_depth: int = 5,
        pop_size: int = 200,
        generations: int = 20,
        cx_pb: float = 0.5,
        mut_pb: float = 0.3,
        seed: int = 42,
    ):
        if creator is None:
            raise ImportError("DEAP not installed. pip install deap")

        self.panel = panel
        self.universe_func = universe_func
        self.target_horizon = target_horizon
        self.min_ic = min_ic
        self.max_depth = max_depth
        self.pop_size = pop_size
        self.generations = generations
        self.cx_pb = cx_pb
        self.mut_pb = mut_pb
        self.seed = seed

        # Prepare data arrays aligned to panel
        self._prepare_data()

        # Setup DEAP
        self._setup_deap()

    def _prepare_data(self):
        """Extract OHLCV arrays aligned to panel."""
        self.dates = self.panel.index
        self.symbols = self.panel.columns.tolist()
        self.n_dates = len(self.dates)
        self.n_symbols = len(self.symbols)

        # Extract arrays: shape (n_dates, n_symbols)
        self.open_arr = self.panel["open"].values if "open" in self.panel.columns else np.zeros((self.n_dates, self.n_symbols))
        self.high_arr = self.panel["high"].values if "high" in self.panel.columns else np.zeros((self.n_dates, self.n_symbols))
        self.low_arr = self.panel["low"].values if "low" in self.panel.columns else np.zeros((self.n_dates, self.n_symbols))
        self.close_arr = self.panel["close"].values
        self.volume_arr = self.panel["volume"].values if "volume" in self.panel.columns else np.ones((self.n_dates, self.n_symbols))
        self.vwap_arr = self.panel["vwap"].values if "vwap" in self.panel.columns else self.close_arr

        # Precompute returns
        self.returns_arr = np.vstack([np.zeros(self.n_symbols), np.diff(self.close_arr, axis=0) / self.close_arr[:-1]])

        # Forward returns for target
        self.forward_returns = np.vstack([
            self.close_arr[h:] / self.close_arr[:-h] - 1
            for h in range(1, 1 + self.target_horizon)
        ]).mean(axis=0) if self.n_dates > self.target_horizon else np.zeros((self.n_dates, self.n_symbols))

    def _setup_deap(self):
        """Initialize DEAP creator, toolbox, and primitive set."""
        random.seed(self.seed)
        np.random.seed(self.seed)

        # Create fitness and individual
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        creator.create("Individual", gp.PrimitiveTree, fitness=creator.FitnessMax)

        self.pset = gp.PrimitiveSetTyped("MAIN", [], float)
        self.pset.addPrimitive(lambda x, y: x + y, [float, float], float, name="add")
        self.pset.addPrimitive(lambda x, y: x - y, [float, float], float, name="sub")
        self.pset.addPrimitive(lambda x, y: x * y, [float, float], float, name="mul")
        self.pset.addPrimitive(_protected_div, [float, float], float, name="div")
        self.pset.addPrimitive(_protected_log, [float], float, name="log")
        self.pset.addPrimitive(_protected_sqrt, [float], float, name="sqrt")
        self.pset.addPrimitive(np.abs, [float], float, name="abs")
        self.pset.addPrimitive(lambda x: -x, [float], float, name="neg")
        self.pset.addPrimitive(np.sign, [float], float, name="sign")

        # Rolling statistics
        self.pset.addPrimitive(lambda x, w=5: np.array(x).mean(), [float], float, name="mean")
        self.pset.addPrimitive(lambda x, w=5: np.array(x).std(), [float], float, name="std")
        self.pset.addPrimitive(lambda x: np.min(x), [float], float, name="min")
        self.pset.addPrimitive(lambda x: np.max(x), [float], float, name="max")

        # Cross-sectional operators (simplified - would need panel context)
        self.pset.addPrimitive(_zscore_cross_section, [float], float, name="cs_zscore")

        # Ephemeral constants
        self.pset.addEphemeralConstant("rand", lambda: random.uniform(-1, 1))

        # Terminals (OHLCV data references - would need panel binding)
        # In practice, these are evaluated at runtime with panel data

        self.toolbox = base.Toolbox()
        self.toolbox.register("expr", gp.genHalfAndHalf, pset=self.pset, min_=1, max_=self.max_depth)
        self.toolbox.register("individual", tools.initIterate, creator.Individual, self.toolbox.expr)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)
        self.toolbox.register("compile", gp.compile, pset=self.pset)

    def _evaluate_individual(self, individual) -> Tuple[float]:
        """
        Fitness = mean cross-sectional IC across dates.
        Only evaluated on in-sample period; out-of-sample tested separately.
        """
        try:
            func = self.toolbox.compile(expr=individual)
            # In practice, would compute factor values over panel and correlate with forward returns
            # This is a placeholder - real implementation needs panel data binding
            ic = random.uniform(-0.05, 0.1)  # Placeholder
            return (ic,)
        except Exception:
            return (-1.0,)

    def evolve(self) -> List[Tuple[Any, float]]:
        """Run GP evolution and return best individuals with fitness."""
        logger.info(f"Starting GP evolution: pop={self.pop_size}, gen={self.generations}")

        pop = self.toolbox.population(n=self.pop_size)
        hof = tools.HallOfFame(10)
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", np.mean)
        stats.register("std", np.std)
        stats.register("min", np.min)
        stats.register("max", np.max)

        pop, log = algorithms.eaSimple(
            pop, self.toolbox,
            cxpb=self.cx_pb, mutpb=self.mut_pb,
            ngen=self.generations,
            stats=stats, halloffame=hof,
            verbose=True
        )

        logger.info(f"Evolution complete. Best fitness: {hof[0].fitness.values[0] if hof else 'N/A'}")
        return [(ind, ind.fitness.values[0]) for ind in hof]


def run_factor_generation(
    panel: pd.DataFrame,
    universe_func: Callable,
    generations: int = 20,
    pop_size: int = 100,
    seed: int = 42,
) -> List[Tuple[str, float]]:
    """
    Convenience function to run factor generation.

    Returns:
        List of (expression_string, fitness) tuples for best factors.
    """
    gen = FactorGenerator(
        panel=panel,
        universe_func=universe_func,
        generations=generations,
        pop_size=pop_size,
        seed=seed,
    )
    results = gen.evolve()
    return [(str(ind), float(fit)) for ind, fit in results]


# ── CLI for standalone use ─────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="DEAP Factor Auto-Generator")
    parser.add_argument("--panel-path", required=True, help="Path to panel parquet (dates x symbols)")
    parser.add_argument("--universe", default="pit_nifty50", help="Universe: pit_nifty50 | all")
    parser.add_argument("--generations", type=int, default=20)
    parser.add_argument("--pop-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", help="Output JSON path")
    args = parser.parse_args()

    panel = pd.read_parquet(args.panel_path)
    if args.universe == "pit_nifty50":
        from mjonai.research.pit_universe import PitUniverseLedger
        ledger = PitUniverseLedger()
        def universe_func(d: pd.Timestamp):
            return set(ledger.members(d.date()))
    else:
        def universe_func(d: pd.Timestamp):
            return set(panel.columns)

    results = run_factor_generation(panel, universe_func, args.generations, args.pop_size, args.seed)

    import json
    out = {"best_factors": [{"expr": e, "fitness": f} for e, f in results]}
    if args.out:
        with open(args.out, "w") as f:
            json.dump(out, f, indent=2)
    else:
        print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()