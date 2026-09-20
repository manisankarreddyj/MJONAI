"""
Module: strategy/registry/__init__.py
Purpose: SOTA Strategy Registry Package Exports (S01 through S18).
         Universal multi-asset, multi-timeframe quantitative strategy suite.
"""

# Universal TA-Lib Compatibility Bridge (auto-injects pure NumPy/Pandas if C TA-Lib missing)
import mjonai.strategy.registry.indicators
from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult
from mjonai.strategy.registry.momentum_rsi import MomentumRSI                  # S01: Momentum RSI Trend Long
from mjonai.strategy.registry.mean_reversion import MeanReversion              # S02: Mean Reversion Long
from mjonai.strategy.registry.turtle_breakout import TurtleBreakout            # S03: Turtle Breakout Positional
from mjonai.strategy.registry.bollinger_squeeze import BollingerSqueeze        # S04: Bollinger Squeeze Volatility
from mjonai.strategy.registry.price_action import PriceActionCandles           # S05: CPR & Candlestick Price Action
from mjonai.strategy.registry.momentum_short import MomentumShort              # S06: Momentum Breakdown Short
from mjonai.strategy.registry.mean_reversion_short import MeanReversionShort   # S07: Overbought Mean Reversion Short
from mjonai.strategy.registry.intraday_all_day import IntradayAllDayStrategy   # S08: All-Day Intraday & Scalping
from mjonai.strategy.registry.options_theta_decay import OptionsThetaDecay     # S09: Options Delta-Neutral Theta Decay
from mjonai.strategy.registry.pairs_trading import PairsTrading                # S10: Statistical Arbitrage Pairs
from mjonai.strategy.registry.volume_profile import VolumeProfileStrategy      # S11: Volume Profile & Value Area Auction
from mjonai.strategy.registry.macro_commodity_crypto import MacroCommodityCrypto # S12: Macro Commodity & Crypto Trend
from mjonai.strategy.registry.s13_gamma_flip import GammaFlipStrategy          # S13: Dealer Gamma Flip
from mjonai.strategy.registry.s14_pead import PostEarningsDriftStrategy        # S14: Post-Earnings Drift
from mjonai.strategy.registry.s15_fii_short_squeeze import FIIShortSqueezeStrategy # S15: FII Short Squeeze Sentry
from mjonai.strategy.registry.s16_cross_sectional_momentum import CrossSectionalMomentumStrategy # S16: Cross-Sectional Decile RS
from mjonai.strategy.registry.s17_order_flow_microprice import OrderFlowMicroPriceStrategy # S17: Order Flow Micro-Price
from mjonai.strategy.registry.s18_gap_fill import GapFillAndFVGStrategy        # S18: Gap Fill & FVG

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