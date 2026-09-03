import pytest
from data.market.delivery_tracker import (
    register_delivery_data,
    get_delivery_snapshot,
    DeliveryZone,
)
from data.fundamentals.quality_filter import (
    evaluate_fundamental_quality,
    FundamentalGrade,
)
from data.corporate.insider_flow import (
    check_promoter_pledge_and_governance,
    GovernanceRiskLevel,
)
from data.derivatives.gex_engine import calculate_gamma_exposure
from data.derivatives.participant_oi import parse_participant_oi_data
from data.macro.macro_check import fetch_macro_sentiment
from core.market_state import calculate_market_state
from core.mqi import get_atr_score


def test_dimension_5_delivery_volume_tracker():
    """Verify Dimension 5: Deliverable Volume & Institutional Accumulation."""
    # Case 1: High delivery accumulation (>= 60%)
    snap_accum = register_delivery_data("TCS", traded_qty=1000000, deliverable_qty=680000)
    assert snap_accum.delivery_zone == DeliveryZone.INSTITUTIONAL_ACCUMULATION
    assert snap_accum.is_institutional_accumulation is True
    assert snap_accum.delivery_percentage == 68.0

    # Case 2: Speculative churn (< 25%)
    snap_churn = register_delivery_data("IDEA", traded_qty=5000000, deliverable_qty=800000)
    assert snap_churn.delivery_zone == DeliveryZone.SPECULATIVE_CHURN
    assert snap_churn.is_speculative_churn is True
    assert snap_churn.delivery_percentage == 16.0


def test_dimension_6_fundamental_quality_filter():
    """Verify Dimension 6: Point-in-Time Fundamental Screening & Insolvency Veto."""
    # Case 1: Prime Grade A company
    snap_prime = evaluate_fundamental_quality(
        "RELIANCE",
        roce_pct=19.2,
        debt_to_equity=0.40,
        operating_margin_pct=17.5,
        free_cash_flow_positive=True,
    )
    assert snap_prime.fundamental_grade == FundamentalGrade.GRADE_A_PRIME
    assert snap_prime.is_trade_allowed is True

    # Case 2: High Debt Zombie Distress Veto (D/E > 2.5)
    snap_distress = evaluate_fundamental_quality(
        "ZOMBIE_CORP",
        debt_to_equity=3.2,
        altman_z_proxy=0.8,
    )
    assert snap_distress.fundamental_grade == FundamentalGrade.DISTRESS_REJECT
    assert snap_distress.is_trade_allowed is False


def test_dimension_7_insider_and_promoter_pledge_sentry():
    """Verify Dimension 7: Promoter Share Pledge Governance Risk Gate."""
    # Case 1: Clean governance (< 5% pledge)
    snap_safe = check_promoter_pledge_and_governance("INFY", promoter_pledged_pct=0.0)
    assert snap_safe.governance_risk == GovernanceRiskLevel.SAFE_PRIME
    assert snap_safe.is_governance_approved is True

    # Case 2: Dangerous High Pledge Veto (> 20% pledge)
    snap_veto = check_promoter_pledge_and_governance("RISKY_CO", promoter_pledged_pct=34.5)
    assert snap_veto.governance_risk == GovernanceRiskLevel.HIGH_PLEDGE_VETO
    assert snap_veto.is_governance_approved is False
