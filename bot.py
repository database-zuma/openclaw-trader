#!/usr/bin/env python3
"""
OpenClaw Trader — Indodax Grid Bot
Runs on Android Termux (Ubuntu proot) or any Linux.
Paper trading mode: set PAPER_TRADE=true in .env
"""

import os, time, json, hmac, hashlib, sqlite3, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("INDODAX_API_KEY", "")
API_SECRET = os.getenv("INDODAX_SECRET_KEY", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
PAIR = os.getenv("TRADING_PAIR", "btcidr")
PAPER = os.getenv("PAPER_TRADE", "true").lower() == "true"

GRID_LEVELS = int(os.getenv("GRID_LEVELS", "5"))
GRID_SPACING = float(os.getenv("GRID_SPACING_PCT", "1.0")) / 100
CAPITAL_IDR = float(os.getenv("CAPITAL_IDR", "500000"))
POLL_INTERVAL = int(os.getenv("POLL_SECONDS", "30"))

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "trades.db")
LOG_PATH = os.path.join(
    os.path.dirname(__file__), "logs", f"{datetime.now().strftime('%Y-%m-%d')}.log"
)

INDODAX_PUBLIC = "https://indodax.com/api"
INDODAX_PRIVATE = "https://indodax.com/tapi"


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def send_tg(msg):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        log(f"Telegram error: {e}")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            pair TEXT,
            side TEXT,
            price REAL,
            amount REAL,
            value_idr REAL,
            order_id TEXT,
            paper INTEGER,
            status TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grid_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            pair TEXT,
            center_price REAL,
            grid_levels TEXT,
            capital_idr REAL,
            paper INTEGER
        )
    """)
    conn.commit()
    conn.close()


def get_ticker(pair):
    try:
        r = requests.get(f"{INDODAX_PUBLIC}/{pair}/ticker", timeout=10)
        r.raise_for_status()
        return r.json()["ticker"]
    except Exception as e:
        log(f"Ticker error: {e}")
        return None


def private_request(method, params=None):
    if PAPER:
        return {"success": 1, "paper_mode": True}
    params = params or {}
    params["method"] = method
    params["timestamp"] = int(time.time() * 1000)
    params["recvWindow"] = 5000

    body = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    sig = hmac.new(API_SECRET.encode(), body.encode(), hashlib.sha512).hexdigest()

    try:
        r = requests.post(
            INDODAX_PRIVATE,
            data=params,
            headers={"Key": API_KEY, "Sign": sig},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"Private API error: {e}")
        return None


def get_balance():
    result = private_request("getInfo")
    if result and result.get("success"):
        return result.get("return", {}).get("balance", {})
    return {}


def place_order(pair, side, price, amount_idr):
    coin = pair.replace("idr", "")
    coin_amount = round(amount_idr / price, 8)

    log(
        f"{'[PAPER] ' if PAPER else ''}ORDER {side.upper()} {pair} @ {price:,.0f} IDR | {coin_amount:.6f} {coin.upper()} | {amount_idr:,.0f} IDR"
    )

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO trades (ts, pair, side, price, amount, value_idr, order_id, paper, status) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            datetime.now().isoformat(),
            pair,
            side,
            price,
            coin_amount,
            amount_idr,
            "paper" if PAPER else "",
            1 if PAPER else 0,
            "filled" if PAPER else "open",
        ),
    )
    conn.commit()
    conn.close()

    if not PAPER:
        result = private_request(
            "trade",
            {
                "pair": pair,
                "type": side,
                "price": int(price),
                f"idr" if side == "buy" else coin: amount_idr
                if side == "buy"
                else coin_amount,
            },
        )
        return result

    return {"success": 1, "paper": True}


def build_grid(center_price, levels, spacing, capital):
    grid = []
    per_level = capital / levels
    for i in range(levels):
        offset = (i - levels // 2) * spacing
        buy_price = round(center_price * (1 + offset - spacing / 2))
        sell_price = round(center_price * (1 + offset + spacing / 2))
        grid.append(
            {"buy": buy_price, "sell": sell_price, "capital": per_level, "active": True}
        )
    return grid


def daily_report(grid, current_price):
    conn = sqlite3.connect(DB_PATH)
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT side, value_idr FROM trades WHERE ts LIKE ? AND pair=?",
        (f"{today}%", PAIR),
    ).fetchall()
    conn.close()

    buys = sum(r[1] for r in rows if r[0] == "buy")
    sells = sum(r[1] for r in rows if r[0] == "sell")
    pnl = sells - buys

    msg = (
        f"📊 *Daily Report — {today}*\n"
        f"Pair: `{PAIR.upper()}`\n"
        f"Price: `{current_price:,.0f} IDR`\n"
        f"Trades: `{len(rows)}`\n"
        f"Buy vol: `{buys:,.0f} IDR`\n"
        f"Sell vol: `{sells:,.0f} IDR`\n"
        f"Est P&L: `{'+' if pnl >= 0 else ''}{pnl:,.0f} IDR`\n"
        f"Mode: `{'PAPER' if PAPER else 'LIVE'}`"
    )
    send_tg(msg)
    log(f"Daily report sent. P&L: {pnl:,.0f} IDR")


def run():
    init_db()
    mode = "📝 PAPER TRADING" if PAPER else "🔴 LIVE TRADING"
    log(f"Starting OpenClaw Trader | {mode} | Pair: {PAIR.upper()}")

    ticker = get_ticker(PAIR)
    if not ticker:
        log("Failed to get initial ticker. Exiting.")
        return

    center = float(ticker["last"])
    grid = build_grid(center, GRID_LEVELS, GRID_SPACING, CAPITAL_IDR)

    send_tg(
        f"🤖 *OpenClaw Trader Started*\n"
        f"Mode: `{mode}`\n"
        f"Pair: `{PAIR.upper()}`\n"
        f"Center: `{center:,.0f} IDR`\n"
        f"Grids: `{GRID_LEVELS}` levels @ `{GRID_SPACING * 100:.1f}%` spacing\n"
        f"Capital: `{CAPITAL_IDR:,.0f} IDR`"
    )

    last_report = datetime.now().date()
    filled_buys = {}

    while True:
        try:
            ticker = get_ticker(PAIR)
            if not ticker:
                time.sleep(POLL_INTERVAL)
                continue

            price = float(ticker["last"])

            for i, level in enumerate(grid):
                if not level["active"]:
                    continue

                if price <= level["buy"] and i not in filled_buys:
                    result = place_order(PAIR, "buy", level["buy"], level["capital"])
                    if result and result.get("success"):
                        filled_buys[i] = level["buy"]
                        send_tg(
                            f"✅ BUY filled | `{PAIR.upper()}` @ `{level['buy']:,.0f}` IDR | `{level['capital']:,.0f}` IDR"
                        )

                elif price >= level["sell"] and i in filled_buys:
                    result = place_order(PAIR, "sell", level["sell"], level["capital"])
                    if result and result.get("success"):
                        profit = (
                            (level["sell"] - filled_buys[i])
                            / filled_buys[i]
                            * level["capital"]
                        )
                        del filled_buys[i]
                        send_tg(
                            f"💰 SELL filled | `{PAIR.upper()}` @ `{level['sell']:,.0f}` IDR | profit ~`{profit:,.0f}` IDR"
                        )

            if datetime.now().date() != last_report:
                daily_report(grid, price)
                last_report = datetime.now().date()

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            log("Stopped by user.")
            send_tg("🛑 *OpenClaw Trader stopped.*")
            break
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
