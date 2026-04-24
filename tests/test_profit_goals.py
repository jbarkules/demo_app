from goldscan import profit_goals, strategy


def test_expectancy_positive_for_good_system():
    e = profit_goals.expectancy_in_R(0.45, 1.8)
    assert e > 0
    assert abs(e - (0.45 * 1.8 - 0.55)) < 1e-9


def test_expectancy_negative_for_bad_system():
    assert profit_goals.expectancy_in_R(0.3, 1.0) < 0


def test_profile_caps_against_baseline():
    p = profit_goals.compute_profit_profile(
        account=10_000,
        risk_per_trade_pct=2.0,
        win_rate=0.6,
        win_loss_ratio=3.0,
        trades_per_month=30,
    )
    # Raw expectancy here would imply >100% / yr — must be capped.
    assert p.capped_to_baseline
    assert p.annual_return_pct <= 24.0 + 1e-6


def test_profile_basic_consistency():
    p = profit_goals.compute_profit_profile(account=25_000)
    assert p.expectancy_R > 0
    assert p.monthly_dollars > 0
    assert p.realistic_annual_range[0] < p.annual_return_pct <= p.realistic_annual_range[1] + 1e-6


def test_kelly_fraction():
    f = strategy.kelly_fraction(0.55, 1.5)
    assert 0 <= f <= 1
    assert strategy.kelly_fraction(0.3, 1.0) == 0.0


def test_position_size_zero_stop_raises():
    import pytest

    with pytest.raises(ValueError):
        strategy.position_size(account=10_000, risk_pct=1.0, stop_distance=0)


def test_position_size_micro_default():
    plan = strategy.position_size(
        account=25_000, risk_pct=1.0, stop_distance=20.0, last_price=2000.0
    )
    # 1% of 25k = $250 risk, $20 stop * 10oz = $200/contract ⇒ 1 contract
    assert plan.contracts == 1
    assert plan.contract == "MGC"
    assert plan.notional == 1 * 10 * 2000.0
