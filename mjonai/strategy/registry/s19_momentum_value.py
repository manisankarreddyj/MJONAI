"""
Module: strategy/registry/s19_momentum_value.py
Purpose: S19 — Momentum + Value 双层选股策略 (S19_MomentumValue)

Clean-room reimplementation from ai-berkshire/tools/stock_screener.py (MIT).
双层选股框架：
  第一层（动量发现）：60日新高 + 放量确认 → 进入待选池
  第二层（价值验证）：6维基本面评分 ≥ 3/6 → 买入信号
  信号分级：3/6=试探仓3% | 4/6=标准仓5% | 5-6/6=确信仓8%
  独立通过条件：毛利率连续2季改善 + 毛利>45% | EPS超预期>30%
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence
import numpy as np
import pandas as pd

from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult


@dataclass(frozen=True)
class S19SignalResult(StrategySignalResult):
    """Extended signal result with factor diagnostics."""
    momentum_score: Optional[Dict[str, Any]] = None
    value_score: Optional[Dict[str, Any]] = None
    independent_pass: bool = False
    independent_reason: str = ""


class S19_MomentumValueStrategy(BaseStrategy):
    """
    S19_MomentumValue — Momentum + Value 双层选股策略.

    策略逻辑：
    1. 动量发现层：60日新高 + 放量确认 → 触发动量信号
    2. 价值验证层：6维基本面评分（营收加速、毛利率扩张、EPS超预期、
       营收高增长、毛利率健康、毛利连续改善）
    3. 独立通过条件：毛利连续改善+毛利>45% | EPS超预期>30%
    4. 信号分级：3/6=试探仓3% | 4/6=标准仓5% | 5-6/6=确信仓8% | 独立通过=试探仓3%
    """

    name: str = "S19_MomentumValue"
    display_name: str = "Momentum + Value 双层选股"
    version: str = "1.0"
    timeframe: str = "daily"
    asset_class: str = "EQUITY"
    signal_direction: str = "LONG"
    is_active: bool = True
    allowed_regimes: Sequence[str] = ("BULL", "NEUTRAL", "BEAR", "SIDEWAYS")
    allowed_asset_classes: Sequence[str] = ("EQUITY",)
    min_candles_required: int = 60
    scan_cadences: Optional[Sequence[str]] = ("daily",)

    def __init__(self, **params: Any):
        super().__init__(**params)
        # 基本面数据缓存
        self._fundamentals_cache: Dict[str, Dict[str, Any]] = {}

    def get_parameters(self) -> Dict[str, Any]:
        return {}

    def get_description(self) -> str:
        return "Momentum + Value 双层选股：动量发现(60日新高+放量) + 价值验证(6维基本面评分) + 独立通过条件"

    def _fetch_fundamentals(self, ticker: str) -> Optional[Dict[str, Any]]:
        """获取基本面数据 — 实际应从数据源获取，此处返回模拟结构."""
        if ticker in self._fundamentals_cache:
            return self._fundamentals_cache[ticker]
        # 实际应用中应连接数据源
        return None

    def _update_fundamentals(self, ticker: str, data: Dict[str, Any]):
        """更新基本面数据缓存."""
        self._fundamentals_cache[ticker] = data

    def _check_momentum(self, prices: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """第一层：动量发现 — 60日新高 + 放量确认."""
        if len(prices) < 61:
            return None

        latest = prices.iloc[-1]
        close = latest["close"]
        high = latest["high"]
        low = latest["low"]
        volume = latest["volume"]

        # 60日新高
        past_60_highs = prices.iloc[-61:-1]["high"]
        is_60d_high = close > past_60_highs.max()

        # 放量：近5日均量 > 20日均量 × 1.5
        vol_5 = prices.iloc[-5:]["volume"].mean()
        vol_20 = prices.iloc[-20:]["volume"].mean()
        vol_ratio = vol_5 / vol_20 if vol_20 > 0 else 0
        is_volume = vol_ratio > 1.5

        # 30日涨幅
        close_30d = prices.iloc[-31]["close"] if len(prices) > 30 else prices.iloc[0]["close"]
        pct_30d = (close - close_30d) / close_30d * 100

        # 近5日有突破日
        recent_breakout = False
        for i in range(-5, 0):
            if prices.iloc[i]["close"] > prices.iloc[i-60:i]["high"].max():
                recent_breakout = True
                break

        triggered = (is_60d_high or recent_breakout) and is_volume

        return {
            "triggered": triggered,
            "close": round(close, 2),
            "date": str(prices.index[-1].date()),
            "is_60d_high": is_60d_high,
            "vol_ratio": round(vol_ratio, 2),
            "pct_30d": round(pct_30d, 1),
        }

    def _check_value(self, ticker: str) -> Optional[Dict[str, Any]]:
        """第二层：价值验证 — 6维基本面评分."""
        funds = self._fetch_fundamentals(ticker)
        if not funds or not funds.get("quarters"):
            return None

        quarters = funds["quarters"]
        sorted_q = sorted(quarters.items(), key=lambda x: x[0])

        if len(sorted_q) < 2:
            return None

        latest = sorted_q[-1]
        prev = sorted_q[-2] if len(sorted_q) >= 2 else None
        prev2 = sorted_q[-3] if len(sorted_q) >= 3 else None

        d = latest[1]
        pd = prev[1] if prev else None
        pd2 = prev2[1] if prev2 else None

        checks = {}

        # 1. 营收加速（同比增速在改善）
        if pd:
            checks["营收加速"] = d["rev_yoy"] > pd["rev_yoy"]
        else:
            checks["营收加速"] = d["rev_yoy"] > 20

        # 2. 毛利率方向
        if pd:
            checks["毛利率扩张"] = d["gm"] > pd["gm"] or d["gm"] > 55
        else:
            checks["毛利率扩张"] = d["gm"] > 45

        # 3. EPS超预期 > 10%
        checks["盈利惊喜"] = d["eps_beat"] > 10

        # 4. 营收高增长 > 15%
        checks["营收高增长"] = d["rev_yoy"] > 15

        # 5. 毛利率健康 > 40%
        checks["毛利率健康"] = d["gm"] > 40

        # 6. ★改进：毛利率连续2季改善
        if pd and pd2:
            checks["毛利连续改善"] = d["gm"] > pd["gm"] > pd2["gm"]
        elif pd:
            checks["毛利连续改善"] = d["gm"] > pd["gm"]
        else:
            checks["毛利连续改善"] = False

        score = sum(1 for v in checks.values() if v)

        # ★独立通过条件
        independent_pass = False
        independent_reason = ""

        # 条件A：毛利率连续2季改善 + 毛利>45%
        if checks.get("毛利连续改善") and d["gm"] > 45:
            independent_pass = True
            independent_reason = "毛利率连续改善+>45%"

        # 条件B：EPS超预期>30%（周期股底部场景）
        if d["eps_beat"] > 30:
            independent_pass = True
            independent_reason = "EPS超预期>30%（周期股信号）"

        return {
            "score": score,
            "max": 6,
            "checks": checks,
            "fund": d,
            "fund_date": latest[0],
            "fund_label": d.get("label", ""),
            "independent_pass": independent_pass,
            "independent_reason": independent_reason,
        }

    def _grade_signal(self, momentum: Optional[Dict], value: Optional[Dict]) -> tuple:
        """综合评级."""
        if not momentum or not momentum["triggered"]:
            return "SKIP", "无动量信号", ""

        if not value:
            return "WATCH", "动量触发但无基本面数据", "补充基本面"

        score = value["score"]
        ind = value["independent_pass"]

        if score >= 5 or (score >= 4 and ind):
            return "BUY_8%", f"确信仓（{score}/6）", "建议8%仓位"
        elif score >= 4 or (score >= 3 and ind):
            return "BUY_5%", f"标准仓（{score}/6）", "建议5%仓位"
        elif score >= 3:
            return "BUY_3%", f"试探仓（{score}/6）", "建议3%仓位"
        elif ind:
            return "BUY_3%", f"独立条件通过：{value['independent_reason']}", "建议3%仓位"
        else:
            return "PASS", f"动量有但基本面不足（{score}/6）", "继续观察"

    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        vix: float,
        market_state: str,
        mqi_level: str,
        higher_tf_df: Optional[pd.DataFrame] = None,
        precomputed_indicators: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """生成交易信号 — 双层选股逻辑."""
        if not self.is_active:
            return None

        # 验证数据
        is_valid, reason = self.validate_ohlcv_dataframe(df)
        if not is_valid:
            return None

        symbol = str(symbol)
        momentum = self._check_momentum(df)
        value = self._check_value(symbol)
        grade, reason, advice = self._grade_signal(momentum, value)

        if grade == "SKIP":
            return None

        entry_price = float(df["close"].iloc[-1])
        signal_direction = "LONG"

        # 简化的止损/目标价计算
        atr_vals = df["close"].rolling(14).apply(
            lambda x: (x.max() - x.min()) if len(x) > 1 else 0
        ).iloc[-1]
        atr = float(atr_vals) if not np.isnan(atr_vals) else entry_price * 0.02

        stop_loss = entry_price * 0.98 if signal_direction == "LONG" else entry_price * 1.02
        target = entry_price * 1.04 if signal_direction == "LONG" else entry_price * 0.96

        # 信号分级映射仓位
        grade_to_weight = {
            "BUY_8%": 1.0,
            "BUY_5%": 0.6,
            "BUY_3%": 0.35,
            "WATCH": 0.0,
            "PASS": 0.0,
        }
        position_weight = grade_to_weight.get(grade, 0.0)

        return {
            "strategy_id": self.name,
            "strategy_version": self.version,
            "symbol": symbol,
            "signal_direction": signal_direction,
            "signal_type": "BUY",
            "technical_score": float(momentum.get("pct_30d", 50)) if momentum else 50.0,
            "confidence": min(80 + value["score"] * 3, 95) if value else 60,
            "reasons": [reason],
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target": target,
            "timeframe": self.timeframe,
            "asset_class": self.asset_class,
            "indicator_scores": {"momentum": 1 if momentum and momentum["triggered"] else 0,
                                "value": value["score"] / 6 if value else 0},
            "indicator_values": {
                "momentum_pct_30d": momentum.get("pct_30d", 0) if momentum else 0,
                "vol_ratio": momentum.get("vol_ratio", 0) if momentum else 0,
                "value_score": value["score"] if value else 0,
                "value_checks": str(value["checks"]) if value else "{}",
            },
            "extra_metadata": {
                "grade": grade,
                "advice": advice,
                "momentum": momentum,
                "value": value,
            },
        }


def _zscore_cross_section(series: pd.Series) -> pd.Series:
    """Cross-sectional z-score normalization (mean=0, std=1)."""
    mean = series.mean()
    std = series.std(ddof=0)
    if std < 1e-12:
        return pd.Series(0.0, index=series.index)
    return (series - mean) / std