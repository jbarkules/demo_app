"""Liquidity-zone detection for gold futures.

Implements the smart-money / ICT toolkit referenced by institutional desks
and discretionary CTAs:

  * Swing highs/lows                       — structural pivots
  * Equal highs / equal lows               — resting-stop pools
  * Previous day / previous week H/L       — session liquidity
  * Fair Value Gaps (FVG)                  — 3-candle imbalances
  * Order Blocks (OB)                      — last opposite candle before impulse
  * Liquidity sweeps                       — stop-runs that reverse
  * Psychological round numbers            — $25 / $50 / $100 levels

These are descriptive zones, not buy/sell signals. The strategy module
combines them with risk filters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


Side = Literal["bullish", "bearish"]


@dataclass
class Zone:
    kind: str
    side: Side | None
    price_low: float
    price_high: float
    timestamp: pd.Timestamp
    note: str = ""

    @property
    def mid(self) -> float:
        return (self.price_low + self.price_high) / 2.0


def find_swings(df: pd.DataFrame, lookback: int = 5) -> tuple[pd.Series, pd.Series]:
    """Return boolean Series marking swing highs and swing lows.

    A bar is a swing high if its High is strictly greater than the High of the
    `lookback` bars on either side; mirrored for lows.
    """
    highs = df["High"]
    lows = df["Low"]
    is_high = pd.Series(False, index=df.index)
    is_low = pd.Series(False, index=df.index)
    for i in range(lookback, len(df) - lookback):
        window_h = highs.iloc[i - lookback : i + lookback + 1]
        window_l = lows.iloc[i - lookback : i + lookback + 1]
        if highs.iloc[i] == window_h.max() and (window_h == highs.iloc[i]).sum() == 1:
            is_high.iloc[i] = True
        if lows.iloc[i] == window_l.min() and (window_l == lows.iloc[i]).sum() == 1:
            is_low.iloc[i] = True
    return is_high, is_low


def find_equal_levels(
    df: pd.DataFrame,
    lookback: int = 5,
    tolerance_pct: float = 0.0015,
) -> list[Zone]:
    """Equal highs / equal lows — classic liquidity pools.

    Two swing points within `tolerance_pct` of each other are flagged as a
    liquidity pool. Tolerance defaults to 0.15% (~$3 at $2000 gold).
    """
    is_high, is_low = find_swings(df, lookback=lookback)
    zones: list[Zone] = []

    swing_highs = df.loc[is_high, "High"]
    swing_lows = df.loc[is_low, "Low"]

    def _cluster(points: pd.Series, side: Side) -> list[Zone]:
        out: list[Zone] = []
        pts = list(points.items())
        used = set()
        for i, (ts_i, p_i) in enumerate(pts):
            if i in used:
                continue
            cluster_ts = [ts_i]
            cluster_p = [p_i]
            for j in range(i + 1, len(pts)):
                ts_j, p_j = pts[j]
                if abs(p_j - p_i) / p_i <= tolerance_pct:
                    cluster_ts.append(ts_j)
                    cluster_p.append(p_j)
                    used.add(j)
            if len(cluster_p) >= 2:
                out.append(
                    Zone(
                        kind="equal_high" if side == "bearish" else "equal_low",
                        side=side,
                        price_low=min(cluster_p),
                        price_high=max(cluster_p),
                        timestamp=max(cluster_ts),
                        note=f"{len(cluster_p)} touches",
                    )
                )
        return out

    zones.extend(_cluster(swing_highs, "bearish"))  # equal highs sit above buy stops
    zones.extend(_cluster(swing_lows, "bullish"))   # equal lows sit below sell stops
    return zones


def find_fair_value_gaps(df: pd.DataFrame, min_gap_atr: float = 0.25) -> list[Zone]:
    """3-candle Fair Value Gap detection.

    Bullish FVG: candle[i+1].Low > candle[i-1].High (gap up imbalance).
    Bearish FVG: candle[i+1].High < candle[i-1].Low (gap down imbalance).

    Filters out trivial gaps smaller than `min_gap_atr` * ATR(14).
    """
    if len(df) < 20:
        return []
    atr = _atr(df, period=14).iloc[-1]
    threshold = atr * min_gap_atr

    zones: list[Zone] = []
    for i in range(1, len(df) - 1):
        prev_h = df["High"].iloc[i - 1]
        prev_l = df["Low"].iloc[i - 1]
        next_h = df["High"].iloc[i + 1]
        next_l = df["Low"].iloc[i + 1]
        ts = df.index[i]

        if next_l > prev_h and (next_l - prev_h) >= threshold:
            zones.append(
                Zone(
                    kind="fvg",
                    side="bullish",
                    price_low=float(prev_h),
                    price_high=float(next_l),
                    timestamp=ts,
                    note=f"{next_l - prev_h:.2f} pt gap",
                )
            )
        elif next_h < prev_l and (prev_l - next_h) >= threshold:
            zones.append(
                Zone(
                    kind="fvg",
                    side="bearish",
                    price_low=float(next_h),
                    price_high=float(prev_l),
                    timestamp=ts,
                    note=f"{prev_l - next_h:.2f} pt gap",
                )
            )
    return zones


def find_order_blocks(df: pd.DataFrame, impulse_atr: float = 1.5) -> list[Zone]:
    """Order Block: last opposite-direction candle before an impulsive move.

    Bullish OB: last bearish candle before a strong up-move >= impulse_atr * ATR.
    Bearish OB: last bullish candle before a strong down-move >= impulse_atr * ATR.
    """
    if len(df) < 20:
        return []
    atr = _atr(df, period=14)
    zones: list[Zone] = []

    for i in range(1, len(df) - 1):
        body = df["Close"].iloc[i] - df["Open"].iloc[i]
        next_body = df["Close"].iloc[i + 1] - df["Open"].iloc[i + 1]
        threshold = atr.iloc[i] * impulse_atr

        if body < 0 and next_body > threshold:
            zones.append(
                Zone(
                    kind="order_block",
                    side="bullish",
                    price_low=float(df["Low"].iloc[i]),
                    price_high=float(df["High"].iloc[i]),
                    timestamp=df.index[i],
                    note="bullish OB",
                )
            )
        elif body > 0 and next_body < -threshold:
            zones.append(
                Zone(
                    kind="order_block",
                    side="bearish",
                    price_low=float(df["Low"].iloc[i]),
                    price_high=float(df["High"].iloc[i]),
                    timestamp=df.index[i],
                    note="bearish OB",
                )
            )
    return zones


def find_liquidity_sweeps(df: pd.DataFrame, lookback: int = 5) -> list[Zone]:
    """Detect bars that wicked beyond a recent swing then closed back inside.

    Bullish sweep: low pierces a prior swing low, close returns above it.
    Bearish sweep: high pierces a prior swing high, close returns below it.
    """
    if len(df) < lookback * 2 + 2:
        return []
    is_high, is_low = find_swings(df, lookback=lookback)
    swing_highs = df.loc[is_high, "High"]
    swing_lows = df.loc[is_low, "Low"]

    zones: list[Zone] = []
    for i in range(lookback + 1, len(df)):
        bar = df.iloc[i]
        ts = df.index[i]
        prior_highs = swing_highs[swing_highs.index < ts]
        prior_lows = swing_lows[swing_lows.index < ts]
        if not prior_highs.empty:
            ref = prior_highs.iloc[-1]
            if bar["High"] > ref and bar["Close"] < ref:
                zones.append(
                    Zone(
                        kind="liquidity_sweep",
                        side="bearish",
                        price_low=float(ref),
                        price_high=float(bar["High"]),
                        timestamp=ts,
                        note=f"swept high {ref:.2f}",
                    )
                )
        if not prior_lows.empty:
            ref = prior_lows.iloc[-1]
            if bar["Low"] < ref and bar["Close"] > ref:
                zones.append(
                    Zone(
                        kind="liquidity_sweep",
                        side="bullish",
                        price_low=float(bar["Low"]),
                        price_high=float(ref),
                        timestamp=ts,
                        note=f"swept low {ref:.2f}",
                    )
                )
    return zones


def find_psychological_levels(df: pd.DataFrame, step: float = 50.0, span_atr: float = 5.0) -> list[Zone]:
    """Round-number levels near the current price.

    Default: every $50 within ~5 ATR of the latest close. Round dollars
    are well-known order magnets in gold (e.g. $2000, $2050, $2100).
    """
    last = float(df["Close"].iloc[-1])
    atr = float(_atr(df, period=14).iloc[-1])
    half_window = atr * span_atr
    lo = last - half_window
    hi = last + half_window
    levels = np.arange(np.floor(lo / step) * step, np.ceil(hi / step) * step + step, step)
    ts = df.index[-1]
    return [
        Zone(
            kind="psych_level",
            side=None,
            price_low=float(lvl),
            price_high=float(lvl),
            timestamp=ts,
            note=f"${lvl:.0f} round",
        )
        for lvl in levels
    ]


def previous_session_levels(df: pd.DataFrame) -> list[Zone]:
    """Previous day high / low and previous week high / low."""
    if len(df) < 2:
        return []
    pdh = df["High"].iloc[-2]
    pdl = df["Low"].iloc[-2]
    ts = df.index[-2]
    out = [
        Zone("prev_day_high", "bearish", float(pdh), float(pdh), ts, "PDH"),
        Zone("prev_day_low", "bullish", float(pdl), float(pdl), ts, "PDL"),
    ]
    if len(df) >= 7:
        wk = df.iloc[-7:-1]
        out.append(Zone("prev_week_high", "bearish", float(wk["High"].max()), float(wk["High"].max()), wk.index[-1], "PWH"))
        out.append(Zone("prev_week_low", "bullish", float(wk["Low"].min()), float(wk["Low"].min()), wk.index[-1], "PWL"))
    return out


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def scan_all(df: pd.DataFrame) -> list[Zone]:
    """Run every detector and return zones sorted by recency."""
    zones: list[Zone] = []
    zones.extend(find_equal_levels(df))
    zones.extend(find_fair_value_gaps(df))
    zones.extend(find_order_blocks(df))
    zones.extend(find_liquidity_sweeps(df))
    zones.extend(previous_session_levels(df))
    zones.extend(find_psychological_levels(df))
    zones.sort(key=lambda z: z.timestamp, reverse=True)
    return zones
