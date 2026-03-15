#!/usr/bin/env python3
"""
Backtest grid strategy against Indodax historical OHLC data.
Usage: python3 backtest.py --pair btcidr --days 30 --capital 500000 --levels 5 --spacing 1.0
"""

import argparse, requests, json
from datetime import datetime, timedelta


def get_ohlc(pair, tf="1D", count=30):
    try:
        r = requests.get(
            f"https://indodax.com/api/chart/chart_data?pair={pair}&tf={tf}&count={count}",
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        return data.get("chart_data", [])
    except Exception as e:
        print(f"OHLC fetch error: {e}")
        return []


def get_ticker_history(pair, days=30):
    candles = get_ohlc(pair, "1H", days * 24)
    prices = []
    for c in candles:
        if isinstance(c, list) and len(c) >= 5:
            prices.append(
                {
                    "ts": c[0],
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                }
            )
        elif isinstance(c, dict):
            prices.append(
                {
                    "ts": c.get("time", 0),
                    "open": float(c.get("open", 0)),
                    "high": float(c.get("high", 0)),
                    "low": float(c.get("low", 0)),
                    "close": float(c.get("close", 0)),
                }
            )
    return prices


def run_backtest(pair, days, capital, levels, spacing_pct):
    spacing = spacing_pct / 100
    print(f"\n{'=' * 55}")
    print(f"  BACKTEST: {pair.upper()} | {days} days | {capital:,.0f} IDR capital")
    print(f"  Grid: {levels} levels @ {spacing_pct}% spacing")
    print(f"{'=' * 55}\n")

    prices = get_ticker_history(pair, days)
    if not prices:
        print("No historical data. Using simulated prices for demo...")
        import random

        base = 1_650_000
        prices = [
            {
                "close": base + random.randint(-50000, 50000),
                "high": 0,
                "low": 0,
                "ts": i,
            }
            for i in range(days * 24)
        ]

    if not prices:
        print("Could not get price data.")
        return

    center = prices[0]["close"]
    per_level = capital / levels

    grid = []
    for i in range(levels):
        offset = (i - levels // 2) * spacing
        grid.append(
            {
                "buy": round(center * (1 + offset - spacing / 2)),
                "sell": round(center * (1 + offset + spacing / 2)),
                "capital": per_level,
            }
        )

    print(f"Starting price: {center:,.0f} IDR")
    print(f"Grid levels:")
    for i, g in enumerate(grid):
        print(f"  Level {i + 1}: BUY @ {g['buy']:,.0f} | SELL @ {g['sell']:,.0f}")
    print()

    total_pnl = 0
    total_trades = 0
    filled_buys = {}

    for candle in prices:
        price = candle["close"]

        for i, level in enumerate(grid):
            if price <= level["buy"] and i not in filled_buys:
                filled_buys[i] = price

            elif price >= level["sell"] and i in filled_buys:
                buy_price = filled_buys[i]
                profit = (price - buy_price) / buy_price * level["capital"]
                total_pnl += profit
                total_trades += 1
                del filled_buys[i]

    final_price = prices[-1]["close"]
    pct = (total_pnl / capital) * 100
    fee_estimate = total_trades * capital / levels * 0.003

    print(f"{'=' * 55}")
    print(f"  RESULTS ({len(prices)} candles / ~{days} days)")
    print(f"{'=' * 55}")
    print(f"  Trades executed : {total_trades}")
    print(
        f"  Gross P&L       : {'+' if total_pnl >= 0 else ''}{total_pnl:,.0f} IDR ({pct:.2f}%)"
    )
    print(f"  Est. fees (0.3%): -{fee_estimate:,.0f} IDR")
    print(f"  Net P&L est.    : {total_pnl - fee_estimate:,.0f} IDR")
    print(f"  Start price     : {center:,.0f} IDR")
    print(f"  End price       : {final_price:,.0f} IDR")
    print(f"  Price change    : {((final_price - center) / center * 100):+.2f}%")
    print(f"{'=' * 55}\n")

    if total_trades == 0:
        print(
            "⚠️  No trades executed — price didn't move enough to trigger grid levels."
        )
        print("   Try: increase days, decrease spacing %, or adjust capital.\n")
    elif total_pnl > 0:
        print(f"✅ Strategy profitable in this period. Consider paper trading next.")
    else:
        print(f"⚠️  Strategy lost in this period. Adjust spacing or levels.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest Indodax grid bot")
    parser.add_argument(
        "--pair", default="btcidr", help="Trading pair (default: btcidr)"
    )
    parser.add_argument(
        "--days", default=30, type=int, help="Days of history (default: 30)"
    )
    parser.add_argument(
        "--capital", default=500000, type=float, help="Capital in IDR (default: 500000)"
    )
    parser.add_argument(
        "--levels", default=5, type=int, help="Grid levels (default: 5)"
    )
    parser.add_argument(
        "--spacing", default=1.0, type=float, help="Spacing %% (default: 1.0)"
    )
    args = parser.parse_args()

    run_backtest(args.pair, args.days, args.capital, args.levels, args.spacing)
