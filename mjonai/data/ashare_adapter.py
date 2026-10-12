"""
Module: data/ashare_adapter.py
Purpose: A-share数据零依赖适配器 — 腾讯/东方财富爬虫，集成到MJONAI数据层.

Clean-room reimplementation from ai-berkshire/tools/ashare_data.py (MIT).
提供 A-share 零外部依赖数据层，curl绕过代理、GBK/UTF-8自动解码、实时行情/财务/估值/搜索CLI。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any, Dict, Optional

# MJONAI data layer integration
from mjonai.data.angelone.token_map import TOKEN_MAP


_TIMEOUT = 15


class AShareDataAdapter:
    """A-share零依赖数据适配器 — 复用腾讯/东方财富免费接口."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def _curl(self, url: str) -> str:
        """用 curl --noproxy 直连，绕过系统代理。"""
        result = subprocess.run(
            ["/usr/bin/curl", "-s", "--noproxy", "*",
             "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
             url],
            capture_output=True, timeout=self.timeout,
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise ConnectionError(f"请求失败: {url}")
        # 腾讯行情 API 返回 GBK 编码，其他返回 UTF-8
        try:
            return result.stdout.decode("utf-8")
        except UnicodeDecodeError:
            return result.stdout.decode("gbk")

    def _curl_json(self, url: str, params: Optional[Dict] = None) -> dict:
        """curl 获取 JSON。"""
        if params:
            from urllib.parse import urlencode
            url = f"{url}?{urlencode(params)}"
        return json.loads(self._curl(url))

    def _qq_code(self, code: str) -> str:
        """将股票代码转为腾讯行情格式。"""
        code = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
        if code.startswith(("6", "9", "5")):
            return f"sh{code}"
        elif code.startswith(("0", "3", "2", "1")):
            return f"sz{code}"
        elif code.startswith(("4", "8")):
            return f"bj{code}"
        return f"sh{code}"

    def _parse_qq_quote(self, raw: str) -> dict:
        """解析腾讯行情数据。格式：v_shXXXXXX="字段1~字段2~..."; """
        start = raw.find('"')
        end = raw.rfind('"')
        if start < 0 or end <= start:
            return {}
        fields = raw[start + 1:end].split("~")
        if len(fields) < 50:
            return {}
        return {
            "name": fields[1],
            "code": fields[2],
            "price": fields[3],
            "prev_close": fields[4],
            "open": fields[5],
            "volume": fields[6],         # 手
            "buy_vol": fields[7],
            "sell_vol": fields[8],
            "high": fields[33] if len(fields) > 33 else fields[3],
            "low": fields[34] if len(fields) > 34 else fields[3],
            "change_pct": fields[32],
            "change_amt": fields[31],
            "turnover_amt": fields[37] if len(fields) > 37 else "-",
            "turnover_rate": fields[38] if len(fields) > 38 else "-",
            "pe": fields[39] if len(fields) > 39 else "-",
            "market_cap": fields[45] if len(fields) > 45 else "-",    # 总市值（亿）
            "float_cap": fields[44] if len(fields) > 44 else "-",     # 流通市值（亿）
            "pb": fields[46] if len(fields) > 46 else "-",
            "limit_up": fields[47] if len(fields) > 47 else "-",
            "limit_down": fields[48] if len(fields) > 48 else "-",
            "total_shares": fields[38] if len(fields) > 38 else "-",
        }

    def _em_secid(self, code: str) -> str:
        """将股票代码转为东方财富 secid 格式：沪市前缀 1.，深市/北交所前缀 0.。"""
        code = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
        if code.startswith(("6", "9", "5")):
            return f"1.{code}"
        return f"0.{code}"

    def _fetch_52w(self, code: str) -> tuple:
        """从东方财富取 52 周最高/最低（f174/f175）。"""
        secid = self._em_secid(code)
        query = f"api/qt/stock/get?secid={secid}&fields=f174,f175&invt=2&fltt=2"
        for host in ("push2delay.eastmoney.com", "push2.eastmoney.com"):
            try:
                data = self._curl_json(f"https://{host}/{query}").get("data") or {}
                high, low = data.get("f174"), data.get("f175")
                if high not in (None, "-") and low not in (None, "-"):
                    return high, low
            except Exception:
                continue
        return "-", "-"

    def _fmt_yi(self, value) -> str:
        if value is None or value == "-" or value == "":
            return "-"
        try:
            v = float(value)
        except (ValueError, TypeError):
            return str(value)
        if abs(v) >= 1e8:
            return f"{v / 1e8:.2f}亿"
        if abs(v) >= 1e4:
            return f"{v / 1e4:.2f}万"
        return f"{v:.2f}"

    def _fmt_pct(self, value) -> str:
        if value is None or value == "-" or value == "":
            return "-"
        try:
            return f"{float(value):.2f}%"
        except (ValueError, TypeError):
            return str(value)

    def get_quote(self, code: str) -> Optional[Dict[str, Any]]:
        """实时行情快照。"""
        qq_code = self._qq_code(code)
        raw = self._curl(f"https://qt.gtimg.cn/q={qq_code}")
        d = self._parse_qq_quote(raw)
        if not d:
            return None

        high_52w, low_52w = self._fetch_52w(code)
        d["high_52w"] = high_52w
        d["low_52w"] = low_52w
        return d

    def get_valuation(self, code: str) -> Optional[Dict[str, Any]]:
        """估值指标汇总。"""
        qq_code = self._qq_code(code)
        raw = self._curl(f"https://qt.gtimg.cn/q={qq_code}")
        d = self._parse_qq_quote(raw)
        if not d:
            return None

        price = d["price"]
        market_cap_yi = d["market_cap"]

        # 市值验算
        try:
            p = Decimal(price)
            cap = Decimal(market_cap_yi) * Decimal("1e8")
            shares = cap / p
            d["implied_shares"] = float(shares)
            calc_cap = p * shares
            reported_cap = Decimal(market_cap_yi) * Decimal("1e8")
            diff = abs(calc_cap - reported_cap) / reported_cap * 100
            d["cap_verification"] = f"偏差 {float(diff):.1f}%"
        except Exception:
            pass

        high_52w, low_52w = self._fetch_52w(code)
        d["high_52w"] = high_52w
        d["low_52w"] = low_52w
        return d

    def get_financials(self, code: str) -> Optional[Dict[str, Any]]:
        """近5年核心财务数据。"""
        qq_code = self._qq_code(code)
        raw = self._curl(f"https://qt.gtimg.cn/q={qq_code}")
        d = self._parse_qq_quote(raw)
        name = d.get("name", code) if d else code

        code_clean = code.strip().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
        market = "SH" if code_clean.startswith(("6", "9", "5")) else "SZ"

        fin_url = "https://datacenter.eastmoney.com/securities/api/data/get"
        params = {
            "type": "RPT_F10_FINANCE_MAINFINADATA",
            "sty": "ALL",
            "filter": f'(SECUCODE="{code_clean}.{market}")(REPORT_TYPE="年报")',
            "p": "1",
            "ps": "5",
            "sr": "-1",
            "st": "REPORT_DATE",
            "source": "HSF10",
            "client": "PC",
        }
        reports = []
        try:
            data = self._curl_json(fin_url, params)
            reports = data.get("result", {}).get("data", [])
        except (OSError, ValueError, json.JSONDecodeError):
            pass

        if not reports:
            params["filter"] = f'(SECUCODE="{code_clean}.{market}")'
            try:
                data = self._curl_json(fin_url, params)
                reports = data.get("result", {}).get("data", [])
            except (OSError, ValueError, json.JSONDecodeError):
                pass

        return {
            "symbol": code,
            "name": name,
            "reports": reports[:5],
        }

    def search(self, keyword: str) -> list:
        """搜索股票代码。"""
        url = "https://searchadapter.eastmoney.com/api/suggest/get"
        token = os.environ.get("EASTMONEY_SEARCH_TOKEN") or "D43BF722C8E33BDC906FB84D85E326E8"
        params = {
            "input": keyword,
            "type": "14",
            "token": token,
            "count": "10",
        }
        data = self._curl_json(url, params)
        results = data.get("QuotationCodeTable", {}).get("Data", [])

        output = []
        for r in results:
            code = r.get("Code", "")
            name = r.get("Name", "")
            market = r.get("MktNum", "")
            mkt_label = {"1": "沪", "2": "深", "3": "北"}.get(str(market), "")
            output.append({"code": code, "name": name, "market": mkt_label})
        return output


def main():
    parser = argparse.ArgumentParser(
        description="A-share数据适配器 — 腾讯行情 + 东方财富财务数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_quote = sub.add_parser("quote", help="实时行情")
    p_quote.add_argument("code", help="股票代码，如 600519")

    p_fin = sub.add_parser("financials", help="核心财务数据（近5年）")
    p_fin.add_argument("code", help="股票代码")

    p_val = sub.add_parser("valuation", help="估值指标")
    p_val.add_argument("code", help="股票代码")

    p_search = sub.add_parser("search", help="搜索股票代码")
    p_search.add_argument("keyword", help="公司名或关键词")

    args = parser.parse_args()

    adapter = AShareDataAdapter()

    if not args.command:
        parser.print_help()
        return

    if args.command == "quote":
        result = adapter.get_quote(args.code)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "financials":
        result = adapter.get_financials(args.code)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "valuation":
        result = adapter.get_valuation(args.code)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "search":
        result = adapter.search(args.keyword)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()