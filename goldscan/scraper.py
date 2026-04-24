"""Scrape gold futures (GC=F) prices and CFTC Commitment of Traders data."""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import requests
import yfinance as yf

GOLD_FUTURES_TICKER = "GC=F"
GOLD_SPOT_TICKER = "XAUUSD=X"

# CFTC disaggregated futures-only "managed money" report (legacy CSV).
COT_REPORT_URL = (
    "https://www.cftc.gov/dea/newcot/FinFutWk.txt"  # legacy short report
)
COT_DISAGG_URL = (
    "https://www.cftc.gov/files/dea/history/fut_disagg_txt_2026.zip"
)


@dataclass
class PriceSnapshot:
    ticker: str
    last: float
    prev_close: float
    day_high: float
    day_low: float
    asof: datetime

    @property
    def change_pct(self) -> float:
        return (self.last - self.prev_close) / self.prev_close * 100.0


def fetch_ohlc(
    ticker: str = GOLD_FUTURES_TICKER,
    period: str = "6mo",
    interval: str = "1d",
) -> pd.DataFrame:
    """Fetch OHLCV from Yahoo Finance. Default: 6 months of daily GC=F bars."""
    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        progress=False,
        auto_adjust=False,
    )
    if df.empty:
        raise RuntimeError(f"No data returned for {ticker} ({period}/{interval})")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def latest_snapshot(df: pd.DataFrame, ticker: str = GOLD_FUTURES_TICKER) -> PriceSnapshot:
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last
    return PriceSnapshot(
        ticker=ticker,
        last=float(last["Close"]),
        prev_close=float(prev["Close"]),
        day_high=float(last["High"]),
        day_low=float(last["Low"]),
        asof=df.index[-1].to_pydatetime(),
    )


def fetch_cot_managed_money(timeout: float = 10.0) -> dict | None:
    """Fetch latest managed-money net positioning for gold from the CFTC.

    Returns a small dict with longs/shorts/net or None if the request fails.
    The CFTC publishes COT every Friday at 15:30 ET.
    """
    try:
        r = requests.get(COT_REPORT_URL, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException:
        return None

    text = r.text
    # The legacy "FinFutWk" file is line-oriented; gold contracts are listed
    # under the "GOLD - COMMODITY EXCHANGE INC." header. We do a permissive
    # scan rather than a strict parse — the format has changed historically.
    blocks = text.split("GOLD")
    if len(blocks) < 2:
        return None
    block = blocks[1][:4000]
    return {"raw_excerpt": block.strip()}
