"""OANDA v20 REST adapter — free real-time XAU/USD with a demo account.

Setup:
    1. Sign up at oanda.com for a free fxTrade Practice (demo) account.
    2. Generate a personal-access token in the v20 dashboard.
    3. Export OANDA_API_TOKEN=...     (required)
       Export OANDA_ENV=practice|live (optional, defaults to practice)
       Export OANDA_ACCOUNT_ID=...    (optional; only needed for live pricing)

Notes:
    * Instrument is XAU_USD (spot), not GC futures. Spot tracks GC tick-for-tick
      apart from a small futures basis (~$1-3) that drifts with rates and
      storage. For zone analysis the difference is irrelevant.
    * Daily/intraday candles via /v3/instruments/{instrument}/candles work
      WITHOUT an account ID.
    * Real-time bid/ask via /v3/accounts/{accountID}/pricing requires an
      account ID. Falls back to last candle close if not configured.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd
import requests

from .base import LivePrice

PRACTICE_HOST = "https://api-fxpractice.oanda.com"
LIVE_HOST = "https://api-fxtrade.oanda.com"

# yfinance period strings → approximate trading-bar count by interval.
# OANDA's API caps `count` at 5000.
_INTERVAL_TO_GRANULARITY = {
    "1m": "M1",
    "2m": "M2",
    "5m": "M5",
    "15m": "M15",
    "30m": "M30",
    "1h": "H1",
    "4h": "H4",
    "1d": "D",
    "1wk": "W",
    "1mo": "M",
}

_PERIOD_TO_DAYS = {
    "5d": 5,
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
    "2y": 730,
    "5y": 1825,
    "10y": 3650,
    "max": 3650,
}


def _bars_for(period: str, interval: str) -> int:
    days = _PERIOD_TO_DAYS.get(period, 180)
    if interval == "1d":
        return min(5000, max(30, int(days * 252 / 365)))
    if interval == "1h":
        return min(5000, days * 24)
    if interval == "4h":
        return min(5000, days * 6)
    if interval in {"15m", "30m"}:
        per_day = 96 if interval == "15m" else 48
        return min(5000, days * per_day)
    if interval in {"1m", "5m"}:
        per_day = 1440 if interval == "1m" else 288
        return min(5000, days * per_day)
    return 500


class OandaSource:
    name = "oanda"

    def __init__(
        self,
        instrument: str = "XAU_USD",
        token: str | None = None,
        env: str | None = None,
        account_id: str | None = None,
        timeout: float = 10.0,
    ):
        self.instrument = instrument
        self.token = token or os.environ.get("OANDA_API_TOKEN")
        self.env = (env or os.environ.get("OANDA_ENV", "practice")).lower()
        self.account_id = account_id or os.environ.get("OANDA_ACCOUNT_ID")
        self.timeout = timeout
        self.host = LIVE_HOST if self.env == "live" else PRACTICE_HOST

        if not self.token:
            raise RuntimeError(
                "OANDA_API_TOKEN not set. Generate one at "
                "https://www.oanda.com/demo-account/tpa/personal_token"
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept-Datetime-Format": "RFC3339",
        }

    def fetch_ohlc(self, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
        granularity = _INTERVAL_TO_GRANULARITY.get(interval)
        if granularity is None:
            raise ValueError(
                f"Unsupported interval {interval!r}. "
                f"Use one of: {sorted(_INTERVAL_TO_GRANULARITY)}"
            )
        url = f"{self.host}/v3/instruments/{self.instrument}/candles"
        params = {
            "granularity": granularity,
            "count": _bars_for(period, interval),
            "price": "M",  # mid candles
        }
        r = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout)
        r.raise_for_status()
        return parse_candles(r.json())

    def latest_price(self) -> LivePrice:
        if not self.account_id:
            df = self.fetch_ohlc(period="5d", interval="1h")
            close = float(df["Close"].iloc[-1])
            return LivePrice(
                instrument=self.instrument,
                bid=close,
                ask=close,
                asof=df.index[-1].to_pydatetime().astimezone(timezone.utc),
                is_realtime=False,
            )

        url = f"{self.host}/v3/accounts/{self.account_id}/pricing"
        r = requests.get(
            url,
            headers=self._headers(),
            params={"instruments": self.instrument},
            timeout=self.timeout,
        )
        r.raise_for_status()
        prices = r.json().get("prices", [])
        if not prices:
            raise RuntimeError("OANDA returned no pricing data")
        p = prices[0]
        return LivePrice(
            instrument=self.instrument,
            bid=float(p["bids"][0]["price"]),
            ask=float(p["asks"][0]["price"]),
            asof=datetime.fromisoformat(p["time"].replace("Z", "+00:00")),
            is_realtime=True,
        )


def parse_candles(payload: dict) -> pd.DataFrame:
    """Convert an OANDA /candles response into an OHLCV DataFrame.

    Pure-function so it can be unit tested without network access.
    """
    candles = payload.get("candles", [])
    rows = []
    for c in candles:
        if not c.get("complete", True):
            continue
        mid = c.get("mid") or c.get("bid") or c.get("ask")
        if mid is None:
            continue
        rows.append(
            {
                "ts": pd.to_datetime(c["time"]),
                "Open": float(mid["o"]),
                "High": float(mid["h"]),
                "Low": float(mid["l"]),
                "Close": float(mid["c"]),
                "Volume": int(c.get("volume", 0)),
            }
        )
    if not rows:
        raise RuntimeError("OANDA returned no complete candles")
    df = pd.DataFrame(rows).set_index("ts")
    df.index = pd.to_datetime(df.index)
    return df[["Open", "High", "Low", "Close", "Volume"]]
