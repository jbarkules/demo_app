"""Risk and position sizing for gold futures.

Built around the same principles institutional desks and CTAs use:

  * ATR-based stops (volatility-adjusted, not fixed-dollar)
  * Fixed fractional risk (0.5%-2% of account per trade)
  * Kelly fraction, quartered, as an upper bound on sizing
  * Realized vol used to scale exposure (vol targeting)

Contract specs reference: COMEX GC futures = 100 troy oz, $1 tick = $10
per contract. Micro Gold (MGC) = 10 troy oz, $1 tick = $1 per contract.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

GC_CONTRACT_OZ = 100  # COMEX standard gold futures
MGC_CONTRACT_OZ = 10  # CME Micro gold


@dataclass
class RiskPlan:
    contract: str
    contracts: int
    stop_distance: float
    risk_per_contract: float
    total_risk: float
    notional: float
    leverage: float


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev = close.shift(1)
    tr = pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def annualized_volatility(df: pd.DataFrame, window: int = 20) -> float:
    """Annualized realized volatility from log returns of close."""
    rets = np.log(df["Close"] / df["Close"].shift(1)).dropna()
    if len(rets) < window:
        return float("nan")
    return float(rets.tail(window).std() * np.sqrt(252))


def kelly_fraction(win_rate: float, win_loss_ratio: float) -> float:
    """Kelly criterion: f* = W - (1-W)/R. Clamped to [0, 1]."""
    if win_loss_ratio <= 0:
        return 0.0
    f = win_rate - (1 - win_rate) / win_loss_ratio
    return float(max(0.0, min(1.0, f)))


def position_size(
    account: float,
    risk_pct: float,
    stop_distance: float,
    contract_oz: int = MGC_CONTRACT_OZ,
    last_price: float = 0.0,
) -> RiskPlan:
    """Fixed-fractional sizing.

    risk_pct is in percent (1.0 = 1%). stop_distance is in dollars per oz.
    Returns a plan in micro contracts by default — gold's notional makes
    full GC contracts unsuitable for accounts under ~$50k.
    """
    if stop_distance <= 0:
        raise ValueError("stop_distance must be > 0")
    risk_dollars = account * (risk_pct / 100.0)
    risk_per_contract = stop_distance * contract_oz
    contracts = int(risk_dollars // risk_per_contract)
    notional = contracts * contract_oz * last_price
    leverage = (notional / account) if account else 0.0
    return RiskPlan(
        contract="MGC" if contract_oz == MGC_CONTRACT_OZ else "GC",
        contracts=contracts,
        stop_distance=stop_distance,
        risk_per_contract=risk_per_contract,
        total_risk=contracts * risk_per_contract,
        notional=notional,
        leverage=leverage,
    )


def confirmation_signal(df: pd.DataFrame, zones: list) -> str | None:
    """ICT-style confirmation: recent liquidity sweep + aligned OB/FVG.

    This is descriptive, not predictive. It surfaces setups; the trader
    still has to validate context (trend, COT positioning, macro).
    """
    recent = [z for z in zones if z.timestamp >= df.index[-5]]
    sweep = next((z for z in recent if z.kind == "liquidity_sweep"), None)
    if not sweep:
        return None
    aligned = [z for z in recent if z.kind in {"fvg", "order_block"} and z.side == sweep.side]
    if not aligned:
        return None
    direction = "LONG" if sweep.side == "bullish" else "SHORT"
    return f"{direction} setup: sweep + {aligned[0].kind} confluence"
