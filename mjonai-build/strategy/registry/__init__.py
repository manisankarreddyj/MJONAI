"""
Module: strategy/registry/__init__.py
Purpose: SOTA Strategy Registry Package Exports (S01 through S12).
         Universal multi-asset, multi-timeframe quantitative strategy suite.
"""

# Universal TA-Lib Compatibility Bridge (auto-injects pure NumPy/Pandas if C TA-Lib missing)
import strategy.registry.indicators

from strategy.registry.base import BaseStrategy, StrategySignalResult
from strategy.registry.momentum_rsi import MomentumRSI                  # S01: Momentum RSI Trend Long
from strategy.registry.mean_reversion import MeanReversion              # S02: Mean Reversion Long
from strategy.registry.turtle_breakout import TurtleBreakout            # S03: Turtle Breakout Positional
from strategy.registry.bollinger_squeeze import BollingerSqueeze        # S04: Bollinger Squeeze Volatility
from strategy.registry.price_action import PriceActionCandles           # S05: CPR & Candlestick Price Action
from strategy.registry.momentum_short import MomentumShort              # S06: Momentum Breakdown Short
from strategy.registry.mean_reversion_short import MeanReversionShort   # S07: Overbought Mean Reversion Short
from strategy.registry.intraday_all_day import IntradayAllDayStrategy   # S08: All-Day Intraday & Scalping
from strategy.registry.options_theta_decay import OptionsThetaDecay     # S09: Options Delta-Neutral Theta Decay
from strategy.registry.pairs_trading import PairsTrading                # S10: Statistical Arbitrage Pairs
from strategy.registry.volume_profile import VolumeProfileStrategy      # S11: Volume Profile & Value Area Auction
from strategy.registry.macro_commodity_crypto import MacroCommodityCrypto # S12: Macro Commodity & Crypto Trend
from strategy.registry.s13_gamma_flip import GammaFlipStrategy          # S13: Dealer Gamma Flip
from strategy.registry.s14_pead import PostEarningsDriftStrategy        # S14: Post-Earnings Drift
from strategy.registry.s15_fii_short_squeeze import FIIShortSqueezeStrategy # S15: FII Short Squeeze Sentry
from strategy.registry.s16_cross_sectional_momentum import CrossSectionalMomentumStrategy # S16: Cross-Sectional Decile RS
from strategy.registry.s17_order_flow_microprice import OrderFlowMicroPriceStrategy # S17: Order Flow Micro-Price
from strategy.registry.s18_gap_fill import GapFillAndFVGStrategy        # S18: Gap Fill & FVG

__all__ = [
    "BaseStrategy",
    "StrategySignalResult",
    "MomentumRSI",
    "MeanReversion",
    "TurtleBreakout",
    "BollingerSqueeze",
    "PriceActionCandles",
    "MomentumShort",
    "MeanReversionShort",
    "IntradayAllDayStrategy",
    "OptionsThetaDecay",
    "PairsTrading",
    "VolumeProfileStrategy",
    "MacroCommodityCrypto",
    "GammaFlipStrategy",
    "PostEarningsDriftStrategy",
    "FIIShortSqueezeStrategy",
    "CrossSectionalMomentumStrategy",
    "OrderFlowMicroPriceStrategy",
    "GapFillAndFVGStrategy",
]