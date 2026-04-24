"""Yahoo Finance adapter via yfinance.

Free, no auth, but 15-minute delayed for futures. Good for end-of-day
research and backtesting; not suitable for intraday execution.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from .base import LivePrice


class YahooSource:
    name = "yahoo"

    def __init__(self, instrument: str = "GC=F"):
        self.instrument = instrument

    def fetch_ohlc(self, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
        df = yf.download(
            self.instrument,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=False,
        )
        if df.empty:
            raise RuntimeError(
                f"No data returned for {self.instrument} ({period}/{interval})"
            )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index)
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()

    def latest_price(self) -> LivePrice:
        df = self.fetch_ohlc(period="5d", interval="1h")
        last = df.iloc[-1]
        close = float(last["Close"])
        return LivePrice(
            instrument=self.instrument,
            bid=close,
            ask=close,
            asof=df.index[-1].to_pydatetime().astimezone(timezone.utc),
            is_realtime=False,
        )
