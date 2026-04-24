"""Unit tests for liquidity-zone detectors. Uses synthetic OHLC fixtures
so tests don't depend on the network."""

from __future__ import annotations

import numpy as np
import pandas as pd

from goldscan import liquidity


def _bar(o, h, l, c, v=1000):
    return {"Open": o, "High": h, "Low": l, "Close": c, "Volume": v}


def _frame(rows: list[dict]) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=len(rows), freq="D")
    return pd.DataFrame(rows, index=idx)


def test_swings_detect_obvious_pivots():
    rows = [_bar(100, 101, 99, 100) for _ in range(11)]
    rows[5] = _bar(100, 110, 99, 100)  # clear high
    df = _frame(rows)
    is_high, _ = liquidity.find_swings(df, lookback=3)
    assert is_high.iloc[5]
    assert not is_high.iloc[0]


def test_equal_highs_detected():
    rows = [_bar(100, 101, 99, 100) for _ in range(21)]
    rows[5] = _bar(100, 110.0, 99, 100)
    rows[15] = _bar(100, 110.05, 99, 100)
    df = _frame(rows)
    zones = liquidity.find_equal_levels(df, lookback=3, tolerance_pct=0.001)
    eq_highs = [z for z in zones if z.kind == "equal_high"]
    assert eq_highs, "expected at least one equal-high cluster"


def test_bullish_fvg_detected():
    rows = [_bar(100, 101, 99, 100) for _ in range(20)]
    # candle 9 is a strong impulse with a gap above prior high
    rows[8] = _bar(100, 102, 99, 100)
    rows[9] = _bar(102, 115, 102, 114)  # impulse
    rows[10] = _bar(114, 116, 110, 115)  # next bar low > rows[8].high (gap = 110-102 = 8)
    df = _frame(rows)
    gaps = liquidity.find_fair_value_gaps(df, min_gap_atr=0.0)
    bullish = [g for g in gaps if g.side == "bullish"]
    assert bullish, "expected a bullish FVG"


def test_psych_levels_around_price():
    rng = np.random.default_rng(0)
    closes = 2000 + rng.normal(0, 5, 60).cumsum()
    rows = [_bar(c - 1, c + 2, c - 2, c) for c in closes]
    df = _frame(rows)
    levels = liquidity.find_psychological_levels(df, step=50.0, span_atr=5.0)
    last = df["Close"].iloc[-1]
    assert all(z.kind == "psych_level" for z in levels)
    assert any(abs(z.price_low - last) < 100 for z in levels)


def test_scan_all_returns_zones_sorted_by_recency():
    rng = np.random.default_rng(1)
    closes = 2000 + rng.normal(0, 8, 80).cumsum()
    rows = []
    for c in closes:
        rows.append(_bar(c - 2, c + 3, c - 3, c))
    df = _frame(rows)
    zones = liquidity.scan_all(df)
    timestamps = [z.timestamp for z in zones]
    assert timestamps == sorted(timestamps, reverse=True)
