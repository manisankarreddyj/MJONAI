import pytest
from mjonai.data.altdata.freight_shipping import (
    evaluate_shipping_and_aviation_altdata,
    SupplyChainStressLevel,
)
from mjonai.data.altdata.news_sentry import (
    analyze_news_headline,
    is_emergency_news_freeze_active,
    NewsImpactLevel,
)


def test_shipping_and_aviation_altdata_engine():
    """Verify Baltic Dry Index, Tanker Rates, and Jet Fuel Crack Spreads."""
    # Case 1: Calm global freight conditions
    snap_calm = evaluate_shipping_and_aviation_altdata(
        bdi_value=1850.0,
        bdi_change_pct=4.5,
        tanker_rate_index=1100.0,
        jet_fuel_crack_usd=18.0,
    )
    assert snap_calm.supply_chain_stress == SupplyChainStressLevel.CALM_EXPANSION
    assert snap_calm.is_macro_shipping_tailwind is True
    assert snap_calm.is_airline_fuel_pressure is False

    # Case 2: Critical freight bottleneck (Tanker rates spike > 1800)
    snap_stress = evaluate_shipping_and_aviation_altdata(
        bdi_value=2400.0,
        bdi_change_pct=35.0,
        tanker_rate_index=1950.0,
        jet_fuel_crack_usd=28.5,
    )
    assert snap_stress.supply_chain_stress == SupplyChainStressLevel.CRITICAL_BOTTLENECK
    assert snap_stress.is_airline_fuel_pressure is True


def test_realtime_news_and_black_swan_freeze_sentry():
    """Verify Real-Time Financial News NLP and Emergency Freeze."""
    # Case 1: Black Swan War / Attack breaking headline -> Emergency Freeze Trigger
    alert_war = analyze_news_headline(
        headline="BREAKING: War outbreak reported in Middle East, missile strike on regional refinery",
        source="REUTERS_WIRE",
    )
    assert alert_war.impact_level == NewsImpactLevel.BLACK_SWAN_CRITICAL
    assert alert_war.is_emergency_freeze_active is True
    assert alert_war.impact_score <= -80
    assert is_emergency_news_freeze_active() is True

    # Case 2: Bullish Corporate Earnings Catalyst
    alert_bull = analyze_news_headline(
        headline="Reliance reports record profit growth and major upgrade from global brokerages",
        symbol="RELIANCE",
    )
    assert alert_bull.impact_level == NewsImpactLevel.BULLISH_CATALYST
    assert alert_bull.impact_score >= 50
    assert alert_bull.affected_symbol == "RELIANCE"
