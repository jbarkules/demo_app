"""Command-line entry point: scan gold futures, print liquidity zones,
size a position, and compute realistic profit goals.

Usage:
    python -m goldscan --account 25000 --risk 1.0 --period 6mo
"""

from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import liquidity, profit_goals, scraper, strategy

DISCLAIMER = (
    "Educational tool. Not financial advice. Futures trading involves "
    "substantial risk of loss. Past performance does not guarantee future "
    "results. Most retail futures traders lose money."
)


def _zones_table(zones: list[liquidity.Zone], last_price: float, limit: int = 15) -> Table:
    table = Table(title=f"Liquidity Zones (price ${last_price:,.2f})")
    table.add_column("Kind", style="cyan")
    table.add_column("Side")
    table.add_column("Range", justify="right")
    table.add_column("Distance", justify="right")
    table.add_column("Note", style="dim")
    nearest = sorted(zones, key=lambda z: abs(z.mid - last_price))[:limit]
    for z in nearest:
        rng = (
            f"${z.price_low:,.2f}"
            if z.price_low == z.price_high
            else f"${z.price_low:,.2f} – ${z.price_high:,.2f}"
        )
        delta = z.mid - last_price
        sign = "+" if delta >= 0 else ""
        side = z.side or "—"
        side_color = (
            "green" if z.side == "bullish" else "red" if z.side == "bearish" else "dim"
        )
        table.add_row(z.kind, f"[{side_color}]{side}[/{side_color}]", rng, f"{sign}{delta:,.2f}", z.note)
    return table


def _profile_panel(profile: profit_goals.ProfitProfile) -> Panel:
    lines = [
        f"Account: ${profile.account:,.0f}    Risk/trade: {profile.risk_per_trade_pct:.2f}%",
        f"Win rate: {profile.win_rate * 100:.0f}%    Reward:Risk: {profile.win_loss_ratio:.2f}    "
        f"Trades/mo: {profile.trades_per_month}",
        f"Per-trade expectancy: {profile.expectancy_R:+.3f} R",
        "",
        f"[bold]Monthly target:[/bold] {profile.monthly_return_pct:+.2f}%  "
        f"(${profile.monthly_dollars:+,.0f})",
        f"[bold]Annual target:[/bold]  {profile.annual_return_pct:+.2f}%  "
        f"(${profile.annual_dollars:+,.0f})",
        f"Realistic annual range: {profile.realistic_annual_range[0]:+.1f}% to "
        f"{profile.realistic_annual_range[1]:+.1f}%",
        f"Estimated max drawdown: -{profile.estimated_max_drawdown_pct:.1f}%",
    ]
    if profile.capped_to_baseline:
        lines.append("[yellow]Note: target was capped against CTA baseline.[/yellow]")
    for n in profile.notes:
        lines.append(f"[dim]• {n}[/dim]")
    return Panel("\n".join(lines), title="Realistic Profit Goals", border_style="green")


def _risk_panel(plan: strategy.RiskPlan, last_price: float) -> Panel:
    lines = [
        f"Contract: [bold]{plan.contract}[/bold]    Size: {plan.contracts} contract(s)",
        f"Stop distance: ${plan.stop_distance:,.2f}/oz    Risk/contract: ${plan.risk_per_contract:,.2f}",
        f"Total risk: ${plan.total_risk:,.2f}",
        f"Notional exposure: ${plan.notional:,.0f}    Leverage: {plan.leverage:.2f}x",
    ]
    if plan.contracts == 0:
        lines.append("[red]Account too small for even 1 contract at this risk %.[/red]")
    return Panel("\n".join(lines), title=f"Position Plan (price ${last_price:,.2f})", border_style="cyan")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", type=float, default=25_000, help="Account size in USD")
    parser.add_argument("--risk", type=float, default=1.0, help="Risk per trade %% (default 1.0)")
    parser.add_argument(
        "--source",
        choices=["yahoo", "oanda"],
        default="yahoo",
        help="Market-data source (yahoo=GC=F 15-min delayed, oanda=XAU_USD real-time)",
    )
    parser.add_argument("--period", default="6mo", help="Lookback period (1mo, 3mo, 6mo, 1y, 2y, 5y)")
    parser.add_argument("--interval", default="1d", help="Bar interval (1d, 4h, 1h, 15m, 5m, 1m)")
    parser.add_argument("--ticker", default=None, help="Override the source's default instrument")
    parser.add_argument("--win-rate", type=float, default=0.45)
    parser.add_argument("--rr", type=float, default=1.8, help="Reward:risk ratio")
    parser.add_argument("--trades-per-month", type=int, default=12)
    parser.add_argument("--full-contract", action="store_true", help="Use GC (100 oz) instead of MGC (10 oz)")
    parser.add_argument("--stop-atr", type=float, default=1.5, help="ATR multiple for stop distance")
    parser.add_argument("--no-cot", action="store_true", help="Skip CFTC COT fetch")
    args = parser.parse_args(argv)

    console = Console()

    source_kwargs = {}
    if args.ticker:
        source_kwargs["instrument"] = args.ticker

    try:
        df, src = scraper.fetch_ohlc(
            source=args.source,
            period=args.period,
            interval=args.interval,
            **source_kwargs,
        )
    except Exception as e:
        console.print(f"[red]Failed to fetch price data from {args.source}:[/red] {e}")
        if args.source == "oanda":
            console.print(
                "[dim]Set OANDA_API_TOKEN (and optionally OANDA_ACCOUNT_ID for "
                "real-time bid/ask). Free demo tokens at oanda.com.[/dim]"
            )
        return 1

    snap = scraper.latest_snapshot(df, src)
    live_tag = "[green]LIVE[/green]" if snap.is_realtime else "[yellow]delayed[/yellow]"
    console.print(
        Panel(
            f"[bold]{snap.ticker}[/bold] via {src.name}  {live_tag}    "
            f"${snap.last:,.2f}    ({snap.change_pct:+.2f}% vs prev close)\n"
            f"Day range: ${snap.day_low:,.2f} – ${snap.day_high:,.2f}    "
            f"As of: {snap.asof:%Y-%m-%d %H:%M %Z}",
            title="Gold Snapshot",
            border_style="yellow",
        )
    )

    zones = liquidity.scan_all(df)
    console.print(_zones_table(zones, snap.last))

    signal = strategy.confirmation_signal(df, zones)
    if signal:
        console.print(Panel(signal, title="Confirmation Signal", border_style="magenta"))

    atr_now = float(strategy.atr(df).iloc[-1])
    realized_vol = strategy.annualized_volatility(df)
    stop_distance = atr_now * args.stop_atr
    contract_oz = strategy.GC_CONTRACT_OZ if args.full_contract else strategy.MGC_CONTRACT_OZ
    plan = strategy.position_size(
        account=args.account,
        risk_pct=args.risk,
        stop_distance=stop_distance,
        contract_oz=contract_oz,
        last_price=snap.last,
    )
    console.print(
        Panel(
            f"ATR(14): ${atr_now:.2f}    Stop distance ({args.stop_atr}x ATR): ${stop_distance:.2f}\n"
            f"Realized volatility (20d, annualized): {realized_vol * 100:.1f}%",
            title="Volatility",
            border_style="blue",
        )
    )
    console.print(_risk_panel(plan, snap.last))

    profile = profit_goals.compute_profit_profile(
        account=args.account,
        risk_per_trade_pct=args.risk,
        win_rate=args.win_rate,
        win_loss_ratio=args.rr,
        trades_per_month=args.trades_per_month,
    )
    console.print(_profile_panel(profile))

    if not args.no_cot:
        cot = scraper.fetch_cot_managed_money()
        if cot:
            console.print(Panel("CFTC COT data fetched (managed-money excerpt available).", border_style="dim"))

    console.print(f"\n[dim italic]{DISCLAIMER}[/dim italic]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
