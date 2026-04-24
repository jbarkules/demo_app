"""Realistic profit-goal calculator.

Anchored to what actually happens at hedge funds and CTAs that trade gold:

  * Top quartile managed-futures funds: ~12-18% annual return,
    10-20% peak-to-trough drawdown, Sharpe ~0.6-1.0.
  * Median retail futures trader loses money. The realistic goal is
    survival + slow compounding, not "10% per month".
  * Per-trade expectancy is modest: a 45% win rate at 1.8 R/R is
    professional-grade. Edge compounds through many trades, not big bets.

We compute a "realistic" target using expectancy math, then sanity-check
it against the CTA-baseline so we don't promise sci-fi returns.
"""

from __future__ import annotations

from dataclasses import dataclass

import math

# Empirical baselines from hedge-fund / CTA performance studies.
CTA_BASELINE_ANNUAL_RETURN = 0.12   # 12%
CTA_BASELINE_DRAWDOWN = 0.18        # 18% peak-to-trough
CTA_BASELINE_SHARPE = 0.7
TRADING_DAYS = 252


@dataclass
class ProfitProfile:
    account: float
    risk_per_trade_pct: float
    win_rate: float
    win_loss_ratio: float
    trades_per_month: int

    expectancy_R: float
    monthly_return_pct: float
    annual_return_pct: float
    monthly_dollars: float
    annual_dollars: float
    estimated_max_drawdown_pct: float
    realistic_annual_range: tuple[float, float]
    capped_to_baseline: bool
    notes: list[str]


def expectancy_in_R(win_rate: float, win_loss_ratio: float) -> float:
    """Expected value per trade in units of R (R = dollars risked)."""
    return win_rate * win_loss_ratio - (1 - win_rate)


def estimate_max_drawdown(win_rate: float, trades: int = 100) -> float:
    """Rough analytical estimate of max consecutive losers as a fraction.

    Uses the geometric expectation of the longest losing streak in N
    trials: ~ log(N) / -log(1 - win_rate). Multiplies by 1.5 for variance.
    """
    if win_rate <= 0 or win_rate >= 1:
        return 0.0
    streak = math.log(trades) / -math.log(1 - win_rate)
    return min(0.5, streak * 1.5 / trades * trades)  # bounded at 50%


def compute_profit_profile(
    account: float,
    risk_per_trade_pct: float = 1.0,
    win_rate: float = 0.45,
    win_loss_ratio: float = 1.8,
    trades_per_month: int = 12,
) -> ProfitProfile:
    """Compute realistic monthly/annual targets for a gold-futures program.

    Defaults reflect a credible discretionary swing-trader profile:
      - 1% risk per trade
      - 45% win rate
      - 1.8:1 reward:risk
      - 12 trades / month (~3 per week)
    Expected value: 0.45 * 1.8 - 0.55 = 0.26 R per trade.
    """
    notes: list[str] = []
    exp_R = expectancy_in_R(win_rate, win_loss_ratio)
    if exp_R <= 0:
        notes.append("Negative expectancy — system loses money over time.")

    monthly_R = exp_R * trades_per_month
    monthly_return_pct = monthly_R * risk_per_trade_pct
    annual_return_pct = (1 + monthly_return_pct / 100) ** 12 * 100 - 100

    capped = False
    cta_cap = CTA_BASELINE_ANNUAL_RETURN * 100 * 2  # allow 2x CTA baseline as ceiling
    if annual_return_pct > cta_cap:
        notes.append(
            f"Raw expectancy implies {annual_return_pct:.1f}% / yr — capped at "
            f"{cta_cap:.0f}% (2x CTA baseline) for realism."
        )
        annual_return_pct = cta_cap
        monthly_return_pct = (1 + annual_return_pct / 100) ** (1 / 12) * 100 - 100
        capped = True

    max_dd = max(
        estimate_max_drawdown(win_rate) * 100,
        CTA_BASELINE_DRAWDOWN * 100 * (risk_per_trade_pct / 1.0),
    )

    low = annual_return_pct * 0.4   # bad year
    high = annual_return_pct * 1.3  # good year, lucky variance

    if risk_per_trade_pct > 2.0:
        notes.append(
            "Risk per trade above 2% is aggressive — drawdowns scale linearly "
            "with risk; doubling risk doubles expected DD."
        )
    if trades_per_month > 40:
        notes.append(
            "Very high trade frequency increases costs (commissions, slippage, "
            "spread). Real-world net returns degrade meaningfully above ~30/mo."
        )

    return ProfitProfile(
        account=account,
        risk_per_trade_pct=risk_per_trade_pct,
        win_rate=win_rate,
        win_loss_ratio=win_loss_ratio,
        trades_per_month=trades_per_month,
        expectancy_R=exp_R,
        monthly_return_pct=monthly_return_pct,
        annual_return_pct=annual_return_pct,
        monthly_dollars=account * (monthly_return_pct / 100),
        annual_dollars=account * (annual_return_pct / 100),
        estimated_max_drawdown_pct=max_dd,
        realistic_annual_range=(low, high),
        capped_to_baseline=capped,
        notes=notes,
    )
