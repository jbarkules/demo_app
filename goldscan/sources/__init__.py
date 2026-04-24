"""Pluggable market-data sources.

Usage:
    from goldscan.sources import get_source
    src = get_source("oanda")           # or "yahoo"
    df = src.fetch_ohlc("6mo", "1d")
    tick = src.latest_price()
"""

from __future__ import annotations

from .base import DataSource, LivePrice
from .oanda import OandaSource
from .yahoo import YahooSource

_REGISTRY = {
    "yahoo": YahooSource,
    "yfinance": YahooSource,
    "oanda": OandaSource,
}


def get_source(name: str, **kwargs) -> DataSource:
    name = name.lower()
    if name not in _REGISTRY:
        raise ValueError(f"Unknown source {name!r}. Available: {sorted(_REGISTRY)}")
    return _REGISTRY[name](**kwargs)


__all__ = ["DataSource", "LivePrice", "YahooSource", "OandaSource", "get_source"]
