"""
Module: analytics/portfolio_hrp.py
Purpose: SOTA Hierarchical Risk Parity (HRP) Portfolio Allocation Engine.
         Computes risk-optimal capital weights for multi-asset equity/derivative watchlists
         using correlation distance clustering and recursive bisection without matrix inversion.
         Inspired by Marcos Lopez de Prado's machine learning asset allocation methodology.
"""

from dataclasses import dataclass, field, asdict
import logging
from typing import Dict, List, Any, Optional, Sequence, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HRPAllocationResult:
    """Immutable contract representing Hierarchical Risk Parity capital allocation."""
    weights: Dict[str, float]  # Symbol -> Capital Weight (sums to 1.0)
    ordered_symbols: List[str]
    portfolio_variance: float
    diversification_ratio: float
    method_used: str  # "HRP_RECURSIVE_BISECTION" or "INVERSE_VOLATILITY_FALLBACK"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _get_correlation_distance(corr_matrix: np.ndarray) -> np.ndarray:
    """Compute angular distance matrix from Pearson correlation matrix."""
    return np.sqrt(np.clip(0.5 * (1.0 - corr_matrix), 0.0, 1.0))


def _get_cluster_order(linkage_matrix: np.ndarray, num_items: int) -> List[int]:
    """Extract quasi-diagonal leaf order from hierarchical linkage matrix."""
    order = [int(linkage_matrix[-1, 0]), int(linkage_matrix[-1, 1])]
    for i in range(num_items - 3, -1, -1):
        idx = int(linkage_matrix[i, 0])
        val = int(linkage_matrix[i, 1])
        if idx in order:
            loc = order.index(idx)
            order.insert(loc, val)
        elif val in order:
            loc = order.index(val)
            order.insert(loc, idx)
    # Flatten to original leaf indices
    flat_order = [x for x in order if x < num_items]
    # Ensure all items present
    missing = [i for i in range(num_items) if i not in flat_order]
    return flat_order + missing


def _get_cluster_variance(cov: np.ndarray, cluster_indices: List[int]) -> float:
    """Compute variance of an inverse-variance weighted sub-cluster."""
    sub_cov = cov[np.ix_(cluster_indices, cluster_indices)]
    inv_diag = 1.0 / np.diag(sub_cov)
    inv_diag /= np.sum(inv_diag)
    cluster_var = float(np.dot(np.dot(inv_diag, sub_cov), inv_diag))
    return max(1e-8, cluster_var)


def _compute_recursive_bisection(cov: np.ndarray, ordered_indices: List[int]) -> np.ndarray:
    """Recursively split clusters and allocate weights inversely proportional to cluster variance."""
    weights = pd.Series(1.0, index=ordered_indices)
    clusters = [ordered_indices]

    while len(clusters) > 0:
        new_clusters = []
        for cluster in clusters:
            if len(cluster) > 1:
                mid = len(cluster) // 2
                left = cluster[:mid]
                right = cluster[mid:]

                var_left = _get_cluster_variance(cov, left)
                var_right = _get_cluster_variance(cov, right)

                alpha = 1.0 - var_left / (var_left + var_right)
                weights[left] *= alpha
                weights[right] *= (1.0 - alpha)

                if len(left) > 1:
                    new_clusters.append(left)
                if len(right) > 1:
                    new_clusters.append(right)
        clusters = new_clusters

    return weights.values


def calculate_hrp_weights(
    returns_df: pd.DataFrame,
    min_obs: int = 15,
) -> HRPAllocationResult:
    """
    Compute Hierarchical Risk Parity weights from historical asset returns.
    
    Args:
        returns_df: DataFrame where each column is an asset's periodic returns series.
        min_obs: Minimum return observations required for full HRP clustering.
        
    Returns:
        HRPAllocationResult contract containing normalized portfolio weights.
    """
    if returns_df is None or returns_df.empty or returns_df.shape[1] == 0:
        return HRPAllocationResult(
            weights={},
            ordered_symbols=[],
            portfolio_variance=0.0,
            diversification_ratio=1.0,
            method_used="EMPTY_INPUT",
        )

    symbols = list(returns_df.columns)
    num_assets = len(symbols)

    if num_assets == 1:
        return HRPAllocationResult(
            weights={symbols[0]: 1.0},
            ordered_symbols=symbols,
            portfolio_variance=float(returns_df[symbols[0]].var()),
            diversification_ratio=1.0,
            method_used="SINGLE_ASSET",
        )

    cov = returns_df.cov().values
    corr = returns_df.corr().values

    # Handle short history or degenerate matrices via inverse-volatility weighting
    if len(returns_df) < min_obs or np.isnan(corr).any() or np.isnan(cov).any():
        vol = returns_df.std().fillna(0.02).values
        inv_vol = 1.0 / np.maximum(vol, 1e-4)
        inv_vol_weights = inv_vol / np.sum(inv_vol)
        weight_dict = {sym: round(float(w), 4) for sym, w in zip(symbols, inv_vol_weights)}

        return HRPAllocationResult(
            weights=weight_dict,
            ordered_symbols=symbols,
            portfolio_variance=float(np.dot(np.dot(inv_vol_weights, np.nan_to_num(cov, nan=0.01)), inv_vol_weights)),
            diversification_ratio=1.1,
            method_used="INVERSE_VOLATILITY_FALLBACK",
        )

    # Hierarchical Clustering using scipy or manual linkage
    try:
        from scipy.cluster.hierarchy import linkage
        from scipy.spatial.distance import squareform

        dist = _get_correlation_distance(corr)
        np.fill_diagonal(dist, 0.0)
        condensed_dist = squareform(dist)
        link = linkage(condensed_dist, method="single")
        ordered_indices = _get_cluster_order(link, num_assets)
    except Exception as e:
        logger.debug(f"[HRP] Scipy linkage fallback: {e}")
        ordered_indices = list(range(num_assets))

    # Recursive bisection weight allocation
    sorted_weights = _compute_recursive_bisection(cov, ordered_indices)

    # Map back to symbols
    weight_dict = {}
    for idx, w in zip(ordered_indices, sorted_weights):
        sym = symbols[idx]
        weight_dict[sym] = round(float(w), 4)

    # Calculate portfolio variance
    weights_vec = np.array([weight_dict[s] for s in symbols])
    weights_vec /= np.sum(weights_vec)  # enforce exact unity
    port_var = float(np.dot(np.dot(weights_vec, cov), weights_vec))

    # Diversification ratio = weighted avg vol / portfolio vol
    asset_vols = np.sqrt(np.diag(cov))
    weighted_avg_vol = float(np.sum(weights_vec * asset_vols))
    port_vol = max(1e-6, np.sqrt(port_var))
    div_ratio = round(weighted_avg_vol / port_vol, 2)

    return HRPAllocationResult(
        weights={s: round(float(w), 4) for s, w in zip(symbols, weights_vec)},
        ordered_symbols=[symbols[i] for i in ordered_indices],
        portfolio_variance=round(port_var, 6),
        diversification_ratio=div_ratio,
        method_used="HRP_RECURSIVE_BISECTION",
    )
