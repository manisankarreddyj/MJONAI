"""
Module: research/terminal_value.py
Purpose: 终值倍数与十年 IRR 推演工具 (Terminal Value Toolkit for MJONAI).

Clean-room reimplementation from ai-berkshire/tools/terminal_value.py (MIT).
核心是永续增长模型：

    PE(终值) = (1 - g/ROIC) / (r - g)

    分子 1 - g/ROIC  = 派息率。g/ROIC 是留存率——想每年长 g，每留存一块钱赚 ROIC，
                       就必须留下利润的 g/ROIC 再投，剩下的才能分给股东。
    分母 r - g       = 永续年金分母。你要 r 的回报，东西自己长 g，净差额就是 r-g。

三条必须记住的纪律（全部来自那份报告踩过的坑）：

1. r 和 g 必须同币种。3% 的名义增长，在 2.5% 通胀的美国是 0.5% 实际增长（保守），
   在 1% 通胀的中国是 2% 实际增长（激进）。同一个数字换币种就换了含义。
   本工具用 --g-shift 显式表达币种换算，不允许隐式混用。
2. 分母 r-g 至少要有 5 个百分点，戈登模型才有意义。低于 5pct 时 g 动一点点估值就翻天，
   那不是估值，是放大偏见。本工具对每一格做体检并显式警告。
3. 离散风险（退市/VIE失效/地缘断供/监管重击）不能放进 r 或 beta。抬 r 三个百分点对第 10 年
   现金流的惩罚是第 1 年的 2.6 倍，而退市是大致均匀甚至前置的年度危害率——用折现率处理它
   会把风险的时间分布搞反。正确做法是单列一个尾部情景档。
"""

from __future__ import annotations

import argparse
import json
import sys

# 戈登模型的有效性下限：分母 r-g 至少 5 个百分点
MIN_SPREAD = 0.05

# 预设：7公司10年投资价值横评（基准日 2026-08-14，口径修订 2026-08-17）
PRESET = {
    "腾讯": dict(roic=0.20, g=(0.015, 0.030, 0.040), p=(0.35, 0.50, 0.15),
                 irr10=(0.3, 9.3, 15.4), k=0.020),
    "阿里巴巴": dict(roic=0.15, g=(0.015, 0.030, 0.040), p=(0.35, 0.45, 0.20),
                     irr10=(-1.3, 7.8, 16.3), k=0.000),
    "拼多多": dict(roic=0.40, g=(0.005, 0.020, 0.030), p=(0.30, 0.55, 0.15),
                   irr10=(-9.7, 8.2, 15.0), k=0.000),
    "贵州茅台": dict(roic=0.25, g=(0.010, 0.025, 0.035), p=(0.35, 0.45, 0.20),
                     irr10=(-5.3, 3.4, 7.2), k=0.045),
    "泡泡玛特": dict(roic=0.25, g=(0.015, 0.030, 0.040), p=(0.38, 0.44, 0.18),
                     irr10=(-8.2, 4.9, 10.9), k=0.018),
    "美团": dict(roic=0.18, g=(0.015, 0.030, 0.040), p=(0.40, 0.45, 0.15),
                 irr10=(-12.1, 1.8, 8.7), k=0.000),
    "MiniMax": dict(roic=0.20, g=(0.025, 0.040, 0.050), p=(0.55, 0.30, 0.15),
                    irr10=(-30.8, -4.7, 9.6), k=-0.030),
}

BASE_R = 0.10  # 预设 irr10 对应的折现率

# 无风险利率实测值（2026-08），用于风险调整后回报的分子
RF = {
    "CNY": 0.0170,  # 中国 10 年期国债，2026-08-07
    "USD": 0.0470,  # 美国 10 年期国债，2026-08-14
}

LABELS = ("悲观", "基准", "乐观")

# 币种口径护栏
CURRENCY_BANDS = {
    "CNY": dict(r=(0.06, 0.09), g_max=0.02, rf=0.0170,
                note="中国10年期国债 1.70%（观测）/ 2.5-3.0%（合成）+ ERP 5.18%"),
    "USD": dict(r=(0.09, 0.115), g_max=0.040, rf=0.0470,
                note="美国10年期国债 4.70% + 中国总ERP 5.18%（含1.01%国别溢价）"),
    "HKD": dict(r=(0.09, 0.115), g_max=0.040, rf=0.0470,
                note="港币与美元挂钩，口径同 USD"),
}

# 离散风险的合法归属
RISK_PLACEMENT_OK = {"情景", "尾部档", "概率"}
RISK_PLACEMENT_BAD = {"折现率", "r", "beta", "β"}
RISK_PLACEMENT_WARN = {"未建模"}


def exit_pe(roic, g, r):
    """永续增长模型的终值 PE。

    返回 (pe, 留存率, 分子, 分母)。分母 <= 0 时返回 pe=None（模型失效）。
    """
    spread = r - g
    retention = g / roic
    numerator = 1.0 - retention
    if spread <= 0:
        return None, retention, numerator, spread
    return numerator / spread, retention, numerator, spread


def irr_from_terminal(profit_2036, mcap_today, pe, years=10, payout=0.0):
    """从零算 IRR：终值市值 = 2036 利润 x 退出 PE。"""
    return (profit_2036 * pe / mcap_today) ** (1.0 / years) - 1.0 + payout


def rescale_irr(irr_base, pe_base, pe_new, k, years=10):
    """把基准 r 下的 IRR 换算到新的退出倍数。"""
    return (1.0 + irr_base - k) * (pe_new / pe_base) ** (1.0 / years) - 1.0 + k


def weighted_stats(values, probs):
    """概率加权的期望值与标准差。"""
    mean = sum(v * p for v, p in zip(values, probs))
    var = sum(p * (v - mean) ** 2 for v, p in zip(values, probs))
    return mean, var ** 0.5


def load_companies(path):
    if not path:
        return dict(PRESET)
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    out = {}
    for name, spec in raw.items():
        out[name] = dict(roic=spec["roic"], g=tuple(spec["g"]), p=tuple(spec["p"]),
                         irr10=tuple(spec["irr10"]), k=spec.get("k", 0.0))
    return out


def warn_spread(spread):
    """分母宽度体检标记。"""
    if spread <= 0:
        return "✗失效"
    if spread < MIN_SPREAD:
        return "⚠窄"
    return ""


def evaluate(spec, r, g_shift=0.0, years=10):
    """算一家公司在给定 r 下的三档退出 PE 与 IRR。"""
    roic = spec["roic"]
    rows = []
    for label, g0, irr_b in zip(LABELS, spec["g"], spec["irr10"]):
        g = g0 + g_shift
        pe_new, retention, numerator, spread = exit_pe(roic, g, r)
        pe_base, _, _, _ = exit_pe(roic, g0, BASE_R)
        if pe_new is None or pe_base is None:
            irr = None
        else:
            irr = rescale_irr(irr_b / 100.0, pe_base, pe_new, spec["k"], years) * 100.0
        rows.append(dict(label=label, g=g, pe=pe_new, irr=irr,
                         retention=retention, numerator=numerator, spread=spread))
    return rows


def summarize(rows, probs, rf):
    """期望 IRR、标准差、风险调整后回报。任一档失效则整体不可用。"""
    irrs = [row["irr"] for row in rows]
    if any(x is None for x in irrs):
        return None, None, None
    mean, sd = weighted_stats(irrs, probs)
    ratio = (mean - rf * 100.0) / sd if sd > 0 else None
    return mean, sd, ratio


def run_multi_factor_scan(
    panel: pd.DataFrame,
    factor_funcs: Dict[str, Any],
    top_k: int = 10,
    long_short: bool = False,
    rebalance: str = "M",
    buffer_mult: float = 2.0,
    members_by_date: Optional[Dict[pd.Timestamp, set]] = None,
) -> Dict[str, Any]:
    """Run multi-factor scan at universe level (called by scanner)."""
    from mjonai.research.discovery import cross_sectional as CS

    # Compute all factors
    factor_frames = {}
    for name, (func, params, weight) in factor_funcs.items():
        fv = func(panel, **params)
        z = fv.apply(lambda row: _zscore_cross_section(row), axis=1)
        factor_frames[name] = z * weight

    # Composite score = equal-weighted average of factor z-scores
    composite = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    total_weight = 0.0
    for name, (_, _, weight) in factor_funcs.items():
        composite = composite.add(factor_frames[name], fill_value=0.0)
        total_weight += weight
    if total_weight > 0:
        composite = composite / total_weight

    # Rebalance schedule
    dates = panel.index
    if rebalance == "M":
        keys = pd.Series(dates.year * 12 + dates.month, index=dates)
    elif rebalance == "W":
        keys = pd.Series(dates.year * 52 + dates.isocalendar().week, index=dates)
    else:
        keys = pd.Series(np.arange(len(dates)), index=dates)

    stock_ret = panel.pct_change().fillna(0.0)

    holdings: List[str] = []
    weights = pd.Series(0.0, index=panel.columns)
    portfolio_ret = []
    turnover_log = []
    hold_log = []

    for i, d in enumerate(dates):
        if i > 0:
            g = float((weights * stock_ret.loc[d]).sum())
        else:
            g = 0.0

        rebal = (i == 0) or (keys.iloc[i] != keys.iloc[i - 1])
        eligible = None
        if members_by_date is not None:
            eligible = members_by_date.get(d, set())
            eligible = {s for s in eligible if s in panel.columns and not np.isnan(panel.at[d, s])}
            if len(eligible) < (top_k or 2):
                eligible = None
        if eligible is None:
            eligible = {s for s in panel.columns if not np.isnan(panel.at[d, s])}

        turnover = 0.0
        if rebal:
            fv = composite.loc[d, list(eligible)].dropna()
            n_hold = len(fv) if top_k is None else top_k
            need = 2 * n_hold if long_short else n_hold
            if len(fv) >= need and n_hold > 0:
                ranked = fv.sort_values(ascending=False)
                cutoff = ranked.index[:int(buffer_mult * n_hold)]
                keep = [s for s in cutoff if s in holdings][:n_hold]
                rest = [s for s in ranked.index if s not in keep and s not in holdings]
                new_holdings = (keep + rest)[:n_hold]
                shorts = []
                if long_short and len(fv) >= 2 * n_hold:
                    shorts = [s for s in ranked.index[-n_hold:] if s not in new_holdings]
                new_w = pd.Series(0.0, index=panel.columns)
                if new_holdings:
                    new_w.loc[new_holdings] = 1.0 / len(new_holdings)
                if shorts:
                    new_w.loc[shorts] = -(1.0 / (2 * len(shorts)))
                turnover = float((new_w - weights).abs().sum())
                holdings = new_holdings
                weights = new_w

        portfolio_ret.append((d, g, int((weights != 0).sum()), turnover))
        hold_log.append((d, tuple(s for s in holdings)))

    daily = pd.DataFrame(portfolio_ret, columns=["date", "gross", "n_holdings", "turnover"]).set_index("date")
    daily["net"] = daily["gross"]  # Cost not modeled here

    return {
        "daily": daily,
        "holdings": pd.Series(dict(hold_log)),
        "total_turnover_yr": float(daily["turnover"].sum() / max(1, len(daily) / 252.0)),
    }


def _zscore_cross_section(series: pd.Series) -> pd.Series:
    """Cross-sectional z-score normalization (mean=0, std=1)."""
    mean = series.mean()
    std = series.std(ddof=0)
    if std < 1e-12:
        return pd.Series(0.0, index=series.index)
    return (series - mean) / std