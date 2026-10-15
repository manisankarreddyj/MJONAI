"""Unit tests for per-FY capital-gains accounting (compute_financial_year_tax)."""

from datetime import date, datetime, timedelta

from mjonai.execution.tax import (
    compute_financial_year_tax,
    current_indian_financial_year,
    FinancialYearTaxSummary,
)

FY_START = date(2025, 4, 1)
FY_END = date(2026, 3, 31)


def _trade(gross, asset, exit_date, holding_days):
    exit_dt = datetime.combine(exit_date, datetime.min.time())
    entry_dt = exit_dt - timedelta(days=holding_days)
    return {
        "gross_pnl": gross,
        "asset_class": asset,
        "entry_time": entry_dt.isoformat(),
        "exit_time": exit_dt.isoformat(),
    }


def test_ltcg_exemption_zeroes_small_gains():
    s = compute_financial_year_tax([_trade(50000.0, "EQUITY", date(2025, 6, 1), 400)], FY_START, FY_END)
    assert s.ltcg_gain == 50000.0
    assert s.ltcg_exemption_used == 50000.0
    assert s.ltcg_taxable == 0.0
    assert s.total_tax == 0.0


def test_ltcg_above_exemption_taxes_only_excess():
    s = compute_financial_year_tax([_trade(200000.0, "EQUITY", date(2025, 6, 1), 400)], FY_START, FY_END)
    assert s.ltcg_exemption_used == 125000.0
    assert s.ltcg_taxable == 75000.0
    assert s.ltcg_tax == round(75000.0 * 0.13, 2)  # 9750.0


def test_stcg_loss_sets_off_stcg_gain():
    s = compute_financial_year_tax([
        _trade(100000.0, "EQUITY", date(2025, 6, 1), 100),
        _trade(-40000.0, "EQUITY", date(2025, 7, 1), 100),
    ], FY_START, FY_END)
    assert s.stcg_taxable == 60000.0
    assert s.stcg_tax == round(60000.0 * 0.208, 2)  # 12480.0


def test_stcg_loss_excess_offset_ltcg_then_exemption():
    s = compute_financial_year_tax([
        _trade(-50000.0, "EQUITY", date(2025, 6, 1), 100),   # STCG loss
        _trade(100000.0, "EQUITY", date(2025, 7, 1), 400),    # LTCG gain
    ], FY_START, FY_END)
    assert s.stcg_taxable == 0.0
    assert s.ltcg_exemption_used == 50000.0  # 50k unused STCG loss -> ltcg_net 50k -> exempt
    assert s.ltcg_taxable == 0.0
    assert s.total_tax == 0.0


def test_vda_isolated_flat_rate_no_exemption():
    s = compute_financial_year_tax([_trade(100000.0, "CRYPTO", date(2025, 6, 1), 30)], FY_START, FY_END)
    assert s.vda_taxable == 100000.0
    assert s.vda_tax == round(100000.0 * 0.312, 2)  # 31200.0
    assert s.ltcg_exemption_used == 0.0  # VDA gets no exemption


def test_vda_losses_never_offset_gains_115bbh():
    """P1-TAX-2 (Sec 115BBH): VDA losses cannot offset VDA gains — each
    profitable transfer is taxed independently. The old max(0, g - l)
    understated crypto tax by the loss amount."""
    s = compute_financial_year_tax([
        _trade(100000.0, "CRYPTO", date(2025, 6, 1), 30),
        _trade(-60000.0, "CRYPTO", date(2025, 7, 1), 30),
    ], FY_START, FY_END)
    assert s.vda_gain == 100000.0
    assert s.vda_loss == 60000.0  # still disclosed...
    assert s.vda_taxable == 100000.0  # ...but never deducted
    assert s.vda_tax == round(100000.0 * 0.312, 2)


def test_fy_window_filters_trades_outside_bounds():
    inside = _trade(200000.0, "EQUITY", date(2026, 3, 31), 400)
    outside = _trade(200000.0, "EQUITY", date(2026, 4, 1), 400)  # next FY
    s = compute_financial_year_tax([inside, outside], FY_START, FY_END)
    assert s.ltcg_gain == 200000.0  # only 'inside' counted


def test_current_indian_financial_year_window():
    start, end = current_indian_financial_year(date(2026, 2, 10))  # Jan/Feb -> prior Apr
    assert (start, end) == (date(2025, 4, 1), date(2026, 3, 31))
    start2, end2 = current_indian_financial_year(date(2026, 6, 1))  # Jun -> current Apr
    assert (start2, end2) == (date(2026, 4, 1), date(2027, 3, 31))


def test_summary_to_dict():
    s = compute_financial_year_tax([_trade(200000.0, "EQUITY", date(2025, 6, 1), 400)], FY_START, FY_END)
    assert isinstance(s, FinancialYearTaxSummary)
    assert s.to_dict()["total_tax"] == s.total_tax
