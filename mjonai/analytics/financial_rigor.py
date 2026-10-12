"""
Module: analytics/financial_rigor.py
Purpose: Financial Rigor Toolkit for MJONAI.
Exact decimal verification for market cap, valuation, cross-source cross-validation,
Benford's Law, three-scenario valuation, and exact calculator.

Clean-room reimplementation from ai-berkshire/tools/financial_rigor.py (MIT).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from decimal import Decimal, Context, ROUND_HALF_EVEN, InvalidOperation

# ── Exact Decimal Engine (no floating-point drift) ───────────────────────────

_CTX = Context(prec=28, rounding=ROUND_HALF_EVEN)


def exact(value) -> Decimal:
    """Convert any numeric to exact Decimal, avoiding float traps."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(str(value))


def fmt_number(d: Decimal, unit: str = "") -> str:
    """Format large numbers in human-readable form (亿/万亿/B/T)."""
    v = float(d)
    abs_v = abs(v)
    if unit in ("亿", "亿元", "亿港元", "亿美元"):
        if abs_v >= 10000:
            return f"{v/10000:.2f}万亿{unit[1:] if len(unit) > 1 else ''}"
        return f"{v:.2f}{unit}"
    if abs_v >= 1e12:
        return f"{v/1e12:.2f}T"
    if abs_v >= 1e9:
        return f"{v/1e9:.2f}B"
    if abs_v >= 1e6:
        return f"{v/1e6:.2f}M"
    return f"{v:,.2f}"


def _force_utf8_stdio():
    """Force stdout/stderr to UTF-8 to avoid Windows GBK issues."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


# ── 1. Market Cap Verification (股价×总股本 vs 报告市值) ──────────────────────

def verify_market_cap(price, shares, reported_cap, currency=""):
    """Verify market cap = price × shares, compare with reported value."""
    p = exact(price)
    s = exact(shares)
    r = exact(reported_cap)

    calculated = _CTX.multiply(p, s)
    deviation = abs(float(calculated - r) / float(r)) * 100 if r != 0 else 0

    print("=" * 60)
    print("市值验算 (Market Cap Verification)")
    print("=" * 60)
    print(f"  股价 (Price):       {p} {currency}")
    print(f"  总股本 (Shares):    {fmt_number(s)}")
    print(f"  计算市值:           {fmt_number(calculated)} {currency}")
    print(f"  报告市值:           {fmt_number(r)} {currency}")
    print(f"  偏差:               {deviation:.2f}%")
    print()

    if deviation > 5:
        print(f"  ❌ 警告: 偏差 {deviation:.1f}% > 5%, 请检查:")
        print(f"     - 股本是否为最新（回购/增发）?")
        print(f"     - 单位是否一致（港币 vs 人民币 vs 美元）?")
        print(f"     - 股价是否为最新?")
        return False
    elif deviation > 1:
        print(f"  ⚠️  偏差 {deviation:.1f}% 在可接受范围, 可能因股价波动/股本变化")
    else:
        print(f"  ✅ 验证通过: 偏差 {deviation:.2f}%")
    print()
    return deviation <= 5


# ── 2. Valuation Verification (PE/PB/ROE/FCF Yield 精确十进制计算) ─────────────

def verify_valuation(price, eps, bvps, fcf_per_share, dividend, currency=""):
    """Verify valuation metrics with exact decimal arithmetic."""
    p = exact(price)
    eps_d = exact(eps) if eps else None
    bvps_d = exact(bvps) if bvps else None
    fcf_d = exact(fcf_per_share) if fcf_per_share else None
    div_d = exact(dividend) if dividend else None

    print("=" * 60)
    print("估值验算 (Valuation Verification)")
    print("=" * 60)
    print(f"  股价 (Price):   {p} {currency}")

    if eps_d:
        pe = _CTX.divide(p, eps_d) if eps_d != 0 else None
        print(f"  PE = {fmt_number(pe)}x" if pe else "  PE = N/A")

    if bvps_d:
        pb = _CTX.divide(p, bvps_d) if bvps_d != 0 else None
        print(f"  PB = {fmt_number(pb)}x" if pb else "  PB = N/A")

    if fcf_d and fcf_d != 0:
        fcf_yield = _CTX.divide(fcf_d, p) * Decimal("100")
        print(f"  FCF Yield = {fmt_number(fcf_yield)}%")

    if div_d and div_d != 0:
        div_yield = _CTX.divide(div_d, p) * Decimal("100")
        print(f"  Div Yield = {fmt_number(div_yield)}%")

    print()
    return True


# ── 3. Multi-Source Cross-Validation (多源交叉验证) ──────────────────────────

def cross_validate(field: str, values: dict, unit: str = "", tolerance_pct: float = 1.0):
    """Cross-validate the same field from multiple sources."""
    print("=" * 60)
    print(f"多源交叉验证: {field}")
    print("=" * 60)

    valid = {}
    for src, val in values.items():
        if val is None or val == "":
            print(f"  {src}: 缺失")
            continue
        try:
            v = exact(val)
            valid[src] = v
            print(f"  {src}: {fmt_number(v, unit)}")
        except (ValueError, InvalidOperation):
            print(f"  {src}: 无效值 {val}")

    if len(valid) < 2:
        print("  ⚠️  至少需要两个有效来源才能交叉验证")
        return False

    # Find median as reference
    vals = list(valid.values())
    median = sorted(vals)[len(vals) // 2]

    all_ok = True
    for src, v in valid.items():
        if median == 0:
            deviation = 0
        else:
            deviation = abs(float(v - median) / float(median)) * 100
        status = "✅" if deviation <= tolerance_pct else "❌"
        print(f"  {status} {src}: 偏差 {deviation:.2f}% {'(超标)' if deviation > tolerance_pct else ''}")
        if deviation > tolerance_pct:
            all_ok = False

    if all_ok:
        print(f"  ✅ 所有来源偏差均在 {tolerance_pct}% 以内")
    else:
        print(f"  ❌ 存在超标偏差，请排查数据源")
    print()
    return all_ok


# ── 4. Three-Scenario Valuation (三情景估值) ─────────────────────────────────

def three_scenario(price, eps, growth_rates, pe_range, currency=""):
    """Three-scenario target price: bear/base/bull."""
    p = exact(price)
    eps_d = exact(eps) if eps else None

    if not eps_d or eps_d <= 0:
        print("EPS must be positive")
        return

    pe_low, pe_mid, pe_high = pe_range

    print("=" * 60)
    print("三情景目标价 (Three-Scenario Target Price)")
    print("=" * 60)
    print(f"  当前股价: {p} {currency}")
    print(f"  EPS:       {eps_d}")
    print()

    for label, g, pe in [("悲观", pe_low), ("中性", pe_mid), ("乐观", pe_high)]:
        target = _CTX.multiply(eps_d, exact(pe))
        upside = _CTX.divide(target - p, p) * Decimal("100")
        print(f"  {label:>4}: PE={pe}x  目标价={fmt_number(target)}  涨幅={float(upside):+.1f}%")

    print()
    return True


# ── 5. Benford's Law Detection (Benford定律检测) ──────────────────────────────

def benford(values: list, field_name: str = "数据"):
    """Benford's Law first-digit distribution test."""
    if not values:
        print("No data provided")
        return

    first_digits = []
    for v in values:
        try:
            v_str = str(abs(float(v))).replace(".", "").lstrip("0")
            if v_str:
                first_digits.append(int(v_str[0]))
        except (ValueError, TypeError):
            continue

    if not first_digits:
        print("No valid first digits extracted")
        return

    from collections import Counter
    counts = Counter(first_digits)
    total = len(first_digits)

    print("=" * 60)
    print(f"Benford定律检测: {field_name} (样本数={total})")
    print("=" * 60)
    print(f"{'数字':>4} {'观测%':>8} {'理论%':>8} {'偏差':>8}")
    print("-" * 36)

    benford_expected = {d: math.log10(1 + 1/d) for d in range(1, 10)}
    max_dev = 0
    for d in range(1, 10):
        observed = counts.get(d, 0) / total * 100
        expected = benford_expected[d] * 100
        dev = observed - expected
        max_dev = max(max_dev, abs(dev))
        print(f"{d:>4} {observed:>7.2f}% {expected:>7.2f}% {dev:>+7.2f}%")

    print(f"\n最大偏差: {max_dev:.2f}%")
    if max_dev > 5:
        print("⚠️  显著偏离 Benford 分布，建议人工核查数据真实性")
    else:
        print("✅ 符合 Benford 分布，数据特征正常")
    print()


# ── 6. Exact Calculator (精确计算器) ────────────────────────────────────────

def calc(expr: str) -> Decimal:
    """Evaluate arithmetic expression with exact decimal arithmetic."""
    # Safe eval: only allow numbers, operators, parentheses, and Decimal
    allowed = set("0123456789.+-*/() ")
    if not all(c in allowed for c in expr):
        raise ValueError(f"Expression contains disallowed characters: {expr}")

    # Replace numbers with Decimal constructor
    import re
    def replace_number(match):
        return f"Decimal('{match.group(0)}')"
    expr = re.sub(r'\b\d+\.?\d*\b', replace_number, expr)
    expr = expr.replace("Decimal", "Decimal")

    # Use a safe evaluation context
    local_ctx = {"Decimal": Decimal, "abs": abs, "min": min, "max": max,
                 "round": round, "pow": pow, "sum": sum}
    try:
        result = eval(expr, {"__builtins__": {}}, local_ctx)
        if not isinstance(result, Decimal):
            result = exact(result)
        return result
    except Exception as e:
        raise ValueError(f"Calculation error: {e}")


def calc_cmd(expr: str):
    """CLI wrapper for exact calculator."""
    try:
        result = calc(expr)
        print(f"{expr} = {fmt_number(result)}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


# ── CLI Entry ──────────────────────────────────────────────────────────────

def main():
    _force_utf8_stdio()
    parser = argparse.ArgumentParser(
        description="Financial Rigor Toolkit — exact decimal verification for investment research",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_mc = sub.add_parser("verify-market-cap", help="Market cap verification")
    p_mc.add_argument("--price", type=str, required=True)
    p_mc.add_argument("--shares", type=str, required=True)
    p_mc.add_argument("--reported", type=str, required=True)
    p_mc.add_argument("--currency", default="")

    p_val = sub.add_parser("verify-valuation", help="Valuation metrics verification")
    p_val.add_argument("--price", type=str, required=True)
    p_val.add_argument("--eps", type=str)
    p_val.add_argument("--bvps", type=str)
    p_val.add_argument("--fcf", type=str)
    p_val.add_argument("--dividend", type=str)
    p_val.add_argument("--currency", default="")

    p_cv = sub.add_parser("cross-validate", help="Cross-validate field from multiple sources")
    p_cv.add_argument("--field", type=str, required=True)
    p_cv.add_argument("--values", type=str, required=True, help='JSON string: {"source1": val1, "source2": val2}')
    p_cv.add_argument("--unit", default="")
    p_cv.add_argument("--tolerance", type=float, default=1.0)

    p_ts = sub.add_parser("three-scenario", help="Three-scenario target price")
    p_ts.add_argument("--price", type=str, required=True)
    p_ts.add_argument("--eps", type=str, required=True)
    p_ts.add_argument("--pe-low", type=float, required=True)
    p_ts.add_argument("--pe-mid", type=float, required=True)
    p_ts.add_argument("--pe-high", type=float, required=True)
    p_ts.add_argument("--currency", default="")

    p_ben = sub.add_parser("benford", help="Benford's Law test")
    p_ben.add_argument("--values", type=str, required=True, help="JSON array of numbers")
    p_ben.add_argument("--field", type=str, default="data")

    p_calc = sub.add_parser("calc", help="Exact decimal calculator")
    p_calc.add_argument("expr", type=str, help="Arithmetic expression")

    args = parser.parse_args()

    if args.command == "verify-market-cap":
        ok = verify_market_cap(args.price, args.shares, args.reported, args.currency)
        sys.exit(0 if ok else 1)
    elif args.command == "verify-valuation":
        verify_valuation(args.price, args.eps, args.bvps, args.fcf, args.dividend, args.currency)
    elif args.command == "cross-validate":
        cross_validate(args.field, json.loads(args.values), args.unit, args.tolerance)
    elif args.command == "three-scenario":
        three_scenario(args.price, args.eps, (args.pe_low, args.pe_mid, args.pe_high), args.currency)
    elif args.command == "benford":
        benford(json.loads(args.values), args.field)
    elif args.command == "calc":
        calc_cmd(args.expr)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()