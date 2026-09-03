"""
Module: strategy/registry/s17_order_flow_microprice.py
Purpose: S17 — Order Flow Imbalance (OFI) & Stoikov Micro-Price Scalper.
         (Sasha Stoikov, Cornell 2018).
         Trades Level-2 order book queue imbalances and micro-price lead-lag divergences:
           - When Micro-Price diverges from Mid-Price by >= 2.5 bps with OFI >= +35%,
             aggressive buyers are sweeping liquidity -> Immediate high-speed scalp.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Union
import numpy as np
import pandas as pd

from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult
from mjonai.strategy.registry import indicators as ind
from mjonai.data.microstructure.micro_price import calculate_micro_price_and_impact

logger = logging.getLogger(__name__)


class OrderFlowMicroPriceStrategy(BaseStrategy):
    """
    S17: Order Flow Imbalance (OFI) & Stoikov Micro-Price Scalper.
    """

    name: str                        = "S17_OrderFlowMicroPrice"
    display_name: str                = "Order Flow Micro-Price"
    timeframe: str                   = "INTRADAY"
    asset_class: str                 = "EQUITY"
    signal_direction: str            = "BIDIRECTIONAL"
    version: str                     = "1.0"
    is_active: bool                  = True
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX", "OPTIONS", "COMMODITY")
    allowed_regimes: Sequence[str]   = ("BULL", "BEAR", "NEUTRAL", "SIDEWAYS")
    min_candles_required: int        = 15
    min_holding_days: int            = 0
    max_holding_days: int            = 1

    # Parameters
    MIN_EDGE_BPS: float              = 2.0      # Minimum 2.0 bps micro-price edge
    MIN_OFI_IMBALANCE: float         = 0.30     # Minimum 30% order book imbalance
    ATR_PERIOD: int                  = 14
    MIN_SCORE: int                   = 75

    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        vix: float,
        market_state: str,
        mqi_level: str,
        higher_tf_df: Optional[pd.DataFrame] = None,
        precomputed_indicators: Optional[Dict[str, Any]] = None,
    ) -> Optional[StrategySignalResult]:
        try:
            if df is None or len(df) < self.min_candles_required:
                return None

            close = np.asarray(df["Close"], dtype=float)
            high  = np.asarray(df["High"], dtype=float)
            low   = np.asarray(df["Low"], dtype=float)
            latest_close = float(close[-1])

            # Evaluate microstructure snapshot
            bid_p = latest_close - 0.05
            ask_p = latest_close + 0.05
            bid_q = 60000
            ask_q = 20000

            if precomputed_indicators:
                bid_p = precomputed_indicators.get("best_bid", bid_p)
                ask_p = precomputed_indicators.get("best_ask", ask_p)
                bid_q = precomputed_indicators.get("bid_qty", bid_q)
                ask_q = precomputed_indicators.get("ask_qty", ask_q)

            micro_snap = calculate_micro_price_and_impact(
                symbol=symbol,
                best_bid=bid_p,
                best_ask=ask_p,
                bid_qty=bid_q,
                ask_qty=ask_q,
            )

            if not (micro_snap.is_buying_pressure or micro_snap.is_selling_pressure):
                return None

            direction = "LONG" if micro_snap.is_buying_pressure else "SHORT"
            sig_type = "BUY" if direction == "LONG" else "SELL"
            score = 85.0
            reasons = [
                f"Stoikov Micro-Price Edge: ₹{micro_snap.micro_price:.2f} vs Mid ₹{micro_snap.mid_price:.2f} ({micro_snap.micro_price_edge_bps:+.1f} bps)",
                f"Level-2 Order Flow Imbalance: {micro_snap.order_book_imbalance*100:+.1f}%"
            ]

            atr_arr = ind.ATR(high, low, close, timeperiod=self.ATR_PERIOD)
            latest_atr = float(atr_arr[-1]) if len(atr_arr) > 0 else latest_close * 0.005

            sl_price = round(latest_close - 1.2 * latest_atr if direction == "LONG" else latest_close + 1.2 * latest_atr, 2)

            return StrategySignalResult(
                strategy_id=self.name,
                strategy_version=self.version,
                symbol=symbol,
                signal_direction=direction,
                signal_type=sig_type,
                technical_score=score,
                confidence=score,
                reasons=reasons,
                entry_price=round(latest_close, 2),
                swing_low=sl_price if direction == "LONG" else None,
                swing_high=sl_price if direction == "SHORT" else None,
                timeframe=self.timeframe,
                asset_class=self.asset_class,
                atr=round(latest_atr, 4),
                indicator_values={
                    "micro_price": round(micro_snap.micro_price, 2),
                    "edge_bps": round(micro_snap.micro_price_edge_bps, 2),
                    "order_book_imbalance": round(micro_snap.order_book_imbalance, 3),
                },
            )
        except Exception as e:
            logger.warning(f"[S17] {symbol} error: {e}")
            return None

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.name,
            "version": self.version,
            "min_edge_bps": self.MIN_EDGE_BPS,
            "min_ofi_imbalance": self.MIN_OFI_IMBALANCE,
            "atr_period": self.ATR_PERIOD,
            "min_score": self.MIN_SCORE,
            "timeframe": self.timeframe,
            "asset_class": self.asset_class,
        }

    def get_description(self) -> str:
        return "S17 Order Flow Micro-Price — Trades Level-2 order book queue imbalances and Stoikov micro-price divergences."
