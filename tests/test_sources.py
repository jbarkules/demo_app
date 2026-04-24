"""Tests for the pluggable source layer. Network-free."""

from __future__ import annotations

import os

import pytest

from goldscan.sources import get_source
from goldscan.sources.oanda import OandaSource, _bars_for, parse_candles


def test_get_source_aliases():
    os.environ["OANDA_API_TOKEN"] = "dummy"
    try:
        assert get_source("yahoo").name == "yahoo"
        assert get_source("yfinance").name == "yahoo"
        assert get_source("oanda").name == "oanda"
    finally:
        del os.environ["OANDA_API_TOKEN"]


def test_get_source_unknown_raises():
    with pytest.raises(ValueError):
        get_source("bloomberg")


def test_oanda_requires_token(monkeypatch):
    monkeypatch.delenv("OANDA_API_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="OANDA_API_TOKEN"):
        OandaSource()


def test_bars_for_daily_six_months():
    n = _bars_for("6mo", "1d")
    assert 100 < n < 200  # ~126 trading days


def test_bars_for_hourly_one_month():
    n = _bars_for("1mo", "1h")
    assert n == 30 * 24


def test_bars_for_capped_at_5000():
    assert _bars_for("10y", "1m") == 5000


def test_parse_candles_basic():
    payload = {
        "candles": [
            {
                "complete": True,
                "time": "2026-04-21T00:00:00.000000000Z",
                "volume": 12345,
                "mid": {"o": "2300.10", "h": "2315.50", "l": "2295.00", "c": "2310.25"},
            },
            {
                "complete": True,
                "time": "2026-04-22T00:00:00.000000000Z",
                "volume": 9999,
                "mid": {"o": "2310.25", "h": "2330.00", "l": "2305.00", "c": "2325.75"},
            },
        ]
    }
    df = parse_candles(payload)
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 2
    assert df["Close"].iloc[-1] == 2325.75
    assert df["Volume"].iloc[0] == 12345


def test_parse_candles_skips_incomplete():
    payload = {
        "candles": [
            {
                "complete": True,
                "time": "2026-04-21T00:00:00Z",
                "volume": 1,
                "mid": {"o": "1", "h": "2", "l": "0.5", "c": "1.5"},
            },
            {
                "complete": False,
                "time": "2026-04-22T00:00:00Z",
                "volume": 1,
                "mid": {"o": "1.5", "h": "2", "l": "1", "c": "1.8"},
            },
        ]
    }
    df = parse_candles(payload)
    assert len(df) == 1


def test_parse_candles_empty_raises():
    with pytest.raises(RuntimeError):
        parse_candles({"candles": []})
