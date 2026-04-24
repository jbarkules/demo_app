"""Thin facade over the pluggable source layer + CFTC COT helper.

For the actual price-data implementations see goldscan.sources.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import requests

from .sources import DataSource, LivePrice, get_source

# Default tickers — kept here so the CLI and tests can reference them.
GOLD_FUTURES_TICKER = "GC=F"     # Yahoo
GOLD_SPOT_OANDA = "XAU_USD"      # OANDA

COT_REPORT_URL = "https://www.cftc.gov/dea/newcot/FinFutWk.txt"


@dataclass
class PriceSnapshot:
    ticker: str
    last: float
    prev_close: float
    day_high: float
    day_low: float
    asof: datetime
    is_realtime: bool = False

    @property
    def change_pct(self) -> float:
        return (self.last - self.prev_close) / self.prev_close * 100.0


def fetch_ohlc(
    source: str | DataSource = "yahoo",
    period: str = "6mo",
    interval: str = "1d",
    **source_kwargs,
) -> tuple[pd.DataFrame, DataSource]:
    """Fetch OHLC bars from the requested source. Returns (df, source)."""
    src = source if not isinstance(source, str) else get_source(source, **source_kwargs)
    df = src.fetch_ohlc(period=period, interval=interval)
    return df, src


def latest_snapshot(df: pd.DataFrame, src: DataSource) -> PriceSnapshot:
    """Combine the last bar with a real-time tick when the source provides one."""
    last_bar = df.iloc[-1]
    prev_bar = df.iloc[-2] if len(df) >= 2 else last_bar
    try:
        tick: LivePrice | None = src.latest_price()
    except Exception:
        tick = None

    if tick is not None and tick.is_realtime:
        return PriceSnapshot(
            ticker=tick.instrument,
            last=tick.mid,
            prev_close=float(prev_bar["Close"]),
            day_high=max(float(last_bar["High"]), tick.mid),
            day_low=min(float(last_bar["Low"]), tick.mid),
            asof=tick.asof,
            is_realtime=True,
        )

    return PriceSnapshot(
        ticker=getattr(src, "instrument", "?"),
        last=float(last_bar["Close"]),
        prev_close=float(prev_bar["Close"]),
        day_high=float(last_bar["High"]),
        day_low=float(last_bar["Low"]),
        asof=df.index[-1].to_pydatetime(),
        is_realtime=False,
    )


def fetch_cot_managed_money(timeout: float = 10.0) -> dict | None:
    """Fetch the latest weekly CFTC managed-money excerpt for gold.

    Returns a dict with a raw text excerpt or None on failure. The CFTC
    publishes COT every Friday at 15:30 ET.
    """
    try:
        r = requests.get(COT_REPORT_URL, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException:
        return None

    blocks = r.text.split("GOLD")
    if len(blocks) < 2:
        return None
    return {"raw_excerpt": blocks[1][:4000].strip()}
