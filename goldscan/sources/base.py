"""DataSource protocol shared by all market-data adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import pandas as pd


@dataclass
class LivePrice:
    """Real-time tick. Sources that only provide delayed bars set
    `is_realtime=False` and synthesise this from the last close."""

    instrument: str
    bid: float
    ask: float
    asof: datetime
    is_realtime: bool

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid


class DataSource(Protocol):
    name: str
    instrument: str

    def fetch_ohlc(self, period: str, interval: str) -> pd.DataFrame:
        """Return OHLCV DataFrame with DatetimeIndex and columns
        Open/High/Low/Close/Volume. `period` accepts strings like
        '1mo', '3mo', '6mo', '1y', '2y'. `interval` accepts '1d',
        '1h', '15m', '5m', '1m'."""
        ...

    def latest_price(self) -> LivePrice:
        """Return the most recent bid/ask (real-time when possible)."""
        ...
