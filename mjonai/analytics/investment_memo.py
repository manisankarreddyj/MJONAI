"""
Module: analytics/investment_memo.py
Purpose: 投资备忘录模板生成器 (Investment Memo Template Generator).

Clean-room reimplementation from ai-berkshire/tools/terminal_value.py 输出格式 (MIT).
生成标准化的投资决策备忘录，包含四大师视角评分、估值区间、风险清单等。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from decimal import Decimal


@dataclass
class InvestmentMemo:
    """标准化投资备忘录数据结构."""
    company: str
    ticker: str
    date: str
    analyst: str

    # 四大师评分
    segment_score: Dict[str, float]  # 段永平: 生意质量
    moat_score: Dict[str, float]     # 巴菲特: 护城河
    mgmt_score: Dict[str, float]     # 段永平+巴菲特: 管理层
    risk_score: Dict[str, float]     # 芒格: 逆向风险
    trend_score: Dict[str, float]    # 李录: 文明趋势
    valuation_score: Dict[str, float] # 巴菲特+段永平: 估值

    # 综合评分
    overall_score: float
    recommendation: str  # BUY / HOLD / PASS
    position_size_pct: float

    # 价格区间
    price_target_low: float
    price_target_mid: float
    price_target_high: float
    current_price: float

    # 关键风险
    key_risks: List[str]
    key_uppers: List[str]

    # 备注
    notes: str


class InvestmentMemoGenerator:
    """投资备忘录生成器."""

    MASTERS = {
        "segment": "段永平 (生意本质)",
        "moat": "巴菲特 (护城河+安全边际)",
        "mgmt": "段永平+巴菲特 (管理层)",
        "risk": "芒格 (逆向思考+风险清单)",
        "trend": "李录 (文明趋势/范式转移)",
        "valuation": "巴菲特+段永平 (估值+安全边际)"
    }

    def __init__(self):
        pass

    def generate(self, memo: InvestmentMemo) -> str:
        """生成标准化投资备忘录 Markdown."""
        lines = []
        lines.append(f"# 投资决策备忘录: {memo.company} ({memo.ticker})")
        lines.append(f"**日期**: {memo.date}  |  **分析师**: {memo.analyst}")
        lines.append(f"**当前价格**: {memo.current_price:.2f}  |  **目标区间**: {memo.price_target_low:.2f} - {memo.price_target_mid:.2f} - {memo.price_target_high:.2f}")
        lines.append("")

        # 四大师评分表
        lines.append("## 四大师评分总表")
        lines.append("")
        lines.append("| 维度 | 框架 | 评分 | 核心判断 |")
        lines.append("|------|------|------|----------|")
        for key, label in self.MASTERS.items():
            score_data = getattr(memo, f"{key}_score")
            score = score_data.get("score", 0)
            rationale = score_data.get("rationale", "")
            stars = "★" * int(round(score)) + "☆" * (5 - int(round(score)))
            lines.append(f"| {label} | {score_data.get('framework', '')} | {stars} ({score}/5) | {rationale} |")
        lines.append("")

        # 综合评分
        lines.append(f"## 综合评分: {memo.overall_score:.1f} / 5.0")
        lines.append(f"**推荐**: {memo.recommendation}  |  **建议仓位**: {memo.position_size_pct:.0%}")
        lines.append("")

        # 价格区间
        lines.append("## 价格目标区间")
        lines.append("")
        lines.append("| 场景 | 目标价 | 涨幅 | 概率 |")
        lines.append("|------|--------|------|------|")
        lines.append(f"| 悲观 | {memo.price_target_low:.2f} | {(memo.price_target_low/memo.current_price-1)*100:+.1f}% | 25% |")
        lines.append(f"| 中性 | {memo.price_target_mid:.2f} | {(memo.price_target_mid/memo.current_price-1)*100:+.1f}% | 50% |")
        lines.append(f"| 乐观 | {memo.price_target_high:.2f} | {(memo.price_target_high/memo.current_price-1)*100:+.1f}% | 25% |")
        lines.append("")

        # 关键风险
        if memo.key_risks:
            lines.append("## 关键风险")
            lines.append("")
            for risk in memo.key_risks:
                lines.append(f"- {risk}")
            lines.append("")

        # 关键上行因素
        if memo.key_uppers:
            lines.append("## 关键上行因素")
            lines.append("")
            for upper in memo.key_uppers:
                lines.append(f"- {upper}")
            lines.append("")

        # 备注
        if memo.notes:
            lines.append("## 备注")
            lines.append("")
            lines.append(memo.notes)
            lines.append("")

        # 页脚
        lines.append("---")
        lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  分析师: {memo.analyst}*")
        lines.append("*免责声明: 仅供研究参考，不构成投资建议。投资有风险，决策需谨慎。*")

        return "\n".join(lines)

    def to_json(self, memo: InvestmentMemo) -> str:
        """导出为 JSON."""
        return json.dumps(asdict(memo), ensure_ascii=False, indent=2)

    def from_json(self, json_str: str) -> InvestmentMemo:
        """从 JSON 导入."""
        data = json.loads(json_str)
        return InvestmentMemo(**data)


def create_memo_from_template(
    company: str,
    ticker: str,
    current_price: float,
    scores: Dict[str, Dict[str, float]],
    price_targets: Dict[str, float],
    risks: List[str],
    uppers: List[str],
    analyst: str = "AI",
    notes: str = ""
) -> InvestmentMemo:
    """从模板创建备忘录."""
    # 计算综合评分 (简单平均)
    overall = sum(s["score"] for s in scores.values()) / len(scores) if scores else 0

    if overall >= 4.0:
        recommendation = "BUY"
        position = 0.08
    elif overall >= 3.5:
        recommendation = "BUY"
        position = 0.05
    elif overall >= 3.0:
        recommendation = "HOLD"
        position = 0.03
    else:
        recommendation = "PASS"
        position = 0.0

    return InvestmentMemo(
        company=company,
        ticker=ticker,
        date=datetime.now().strftime("%Y-%m-%d"),
        analyst=analyst,
        segment_score=scores.get("segment", {"score": 0, "rationale": ""}),
        moat_score=scores.get("moat", {"score": 0, "rationale": ""}),
        mgmt_score=scores.get("mgmt", {"score": 0, "rationale": ""}),
        risk_score=scores.get("risk", {"score": 0, "rationale": ""}),
        trend_score=scores.get("trend", {"score": 0, "rationale": ""}),
        valuation_score=scores.get("valuation", {"score": 0, "rationale": ""}),
        overall_score=round(overall, 1),
        recommendation=recommendation,
        position_size_pct=position,
        price_target_low=price_targets.get("low", 0),
        price_target_mid=price_targets.get("mid", 0),
        price_target_high=price_targets.get("high", 0),
        current_price=current_price,
        key_risks=risks,
        key_uppers=uppers,
        notes=notes,
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Investment Memo Generator")
    parser.add_argument("--company", required=True)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--price", type=float, required=True)
    parser.add_argument("--scores", type=str, help="JSON string of scores")
    parser.add_argument("--targets", type=str, help="JSON string of price targets")
    parser.add_argument("--risks", type=str, help="JSON array of risks")
    parser.add_argument("--uppers", type=str, help="JSON array of uppers")
    parser.add_argument("--analyst", default="AI")
    parser.add_argument("--notes", default="")
    parser.add_argument("--output", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--out", help="Output file path")
    args = parser.parse_args()

    scores = json.loads(args.scores) if args.scores else {}
    targets = json.loads(args.targets) if args.targets else {}
    risks = json.loads(args.risks) if args.risks else []
    uppers = json.loads(args.uppers) if args.uppers else []

    memo = create_memo_from_template(
        company=args.company,
        ticker=args.ticker,
        current_price=args.price,
        scores=scores,
        price_targets=targets,
        risks=risks,
        uppers=uppers,
        analyst=args.analyst,
        notes=args.notes,
    )

    generator = InvestmentMemoGenerator()
    if args.output == "markdown":
        output = generator.generate(memo)
    else:
        output = generator.to_json(memo)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Written to {args.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()