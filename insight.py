#!/usr/bin/env python3
"""
Market Intelligence Layer — runs alongside bot.py
Fetches market data, news, sentiment and sends Telegram briefings.
Does NOT modify bot behavior — pure intelligence/context layer.
"""

import os, time, requests, sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
PAIR = os.getenv("TRADING_PAIR", "btcidr")
INTERVAL = int(os.getenv("INSIGHT_INTERVAL_HOURS", "4")) * 3600
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "trades.db")


def send_tg(msg):
    if not TG_TOKEN or not TG_CHAT:
        print(msg)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        print(f"Telegram error: {e}")


def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        d = r.json()["data"][0]
        return {"value": int(d["value"]), "label": d["value_classification"]}
    except:
        return None


def get_btc_dominance():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        dom = r.json()["data"]["market_cap_percentage"]["btc"]
        return round(dom, 1)
    except:
        return None


def get_ticker(pair):
    try:
        r = requests.get(f"https://indodax.com/api/{pair}/ticker", timeout=10)
        return r.json()["ticker"]
    except:
        return None


def get_crypto_news():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/news?per_page=3", timeout=10)
        items = r.json() if isinstance(r.json(), list) else r.json().get("data", [])
        return [
            {"title": n.get("title", ""), "url": n.get("url", "")} for n in items[:3]
        ]
    except:
        return []


def get_bot_stats():
    try:
        conn = sqlite3.connect(DB_PATH)
        today = datetime.now().strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT side, value_idr, price FROM trades WHERE ts LIKE ?", (today + "%",)
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        conn.close()

        buys = [r for r in rows if r[0] == "buy"]
        sells = [r for r in rows if r[0] == "sell"]
        pnl = sum(r[1] for r in sells) - sum(r[1] for r in buys)

        return {
            "today_trades": len(rows),
            "today_buys": len(buys),
            "today_sells": len(sells),
            "today_pnl": pnl,
            "total_trades": total,
        }
    except:
        return {
            "today_trades": 0,
            "today_buys": 0,
            "today_sells": 0,
            "today_pnl": 0,
            "total_trades": 0,
        }


def interpret_fear_greed(value):
    if value <= 20:
        return "🔴 Extreme Fear — pasar panik, historis bagus buat buy"
    if value <= 40:
        return "🟠 Fear — sentiment negatif, peluang entry menarik"
    if value <= 60:
        return "🟡 Neutral — pasar sideways, grid trading optimal"
    if value <= 80:
        return "🟢 Greed — pasar bullish, tapi hati-hati reversal"
    return "🔥 Extreme Greed — potensi koreksi tinggi"


def interpret_dominance(dom):
    if dom is None:
        return "Data tidak tersedia"
    if dom > 60:
        return f"BTC dominance {dom}% — altcoin lemah, BTC lebih aman"
    if dom > 50:
        return f"BTC dominance {dom}% — market BTC-driven, stabil"
    if dom > 40:
        return f"BTC dominance {dom}% — altseason kemungkinan dimulai"
    return f"BTC dominance {dom}% — altcoin season, BTC mungkin sideways"


def interpret_volume(ticker):
    if not ticker:
        return "Volume data tidak tersedia"
    try:
        vol = float(ticker.get("vol_idr", 0))
        if vol > 50_000_000_000:
            return f"Volume 24h: {vol / 1e9:.1f}B IDR — sangat tinggi, volatility besar"
        if vol > 20_000_000_000:
            return f"Volume 24h: {vol / 1e9:.1f}B IDR — normal, grid bisa kerja optimal"
        return f"Volume 24h: {vol / 1e9:.1f}B IDR — rendah, spread mungkin lebih lebar"
    except:
        return "Volume data tidak tersedia"


def build_briefing():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ticker = get_ticker(PAIR)
    fg = get_fear_greed()
    dom = get_btc_dominance()
    stats = get_bot_stats()
    news = get_crypto_news()

    coin = PAIR.replace("idr", "").upper()
    price = float(ticker["last"]) if ticker else 0
    high = float(ticker["high"]) if ticker else 0
    low = float(ticker["low"]) if ticker else 0
    pct = ((price - low) / (high - low) * 100) if high != low else 50

    lines = [f"🧠 *Market Briefing — {now}*\n"]

    lines.append(f"*{coin}/IDR*")
    lines.append(f"Price: `{price:,.0f}` IDR")
    if ticker:
        lines.append(
            f"24h Range: `{low:,.0f}` — `{high:,.0f}` ({pct:.0f}% dari bottom)"
        )
    lines.append("")

    if fg:
        lines.append(f"*Sentiment*")
        lines.append(f"Fear & Greed: `{fg['value']}` ({fg['label']})")
        lines.append(interpret_fear_greed(fg["value"]))
        lines.append("")

    if dom:
        lines.append(f"*Market Structure*")
        lines.append(interpret_dominance(dom))
        lines.append("")

    if ticker:
        lines.append(f"*Volume*")
        lines.append(interpret_volume(ticker))
        lines.append("")

    lines.append(f"*Bot Activity Hari Ini*")
    lines.append(
        f"Trades: `{stats['today_trades']}` ({stats['today_buys']} buy, {stats['today_sells']} sell)"
    )
    pnl_str = (
        f"+{stats['today_pnl']:,.0f}"
        if stats["today_pnl"] >= 0
        else f"{stats['today_pnl']:,.0f}"
    )
    lines.append(f"Est P&L: `{pnl_str} IDR`")
    lines.append(f"Total trades: `{stats['total_trades']}`")
    lines.append("")

    if news:
        lines.append(f"*Headlines*")
        for n in news[:2]:
            if n["title"]:
                lines.append(f"• {n['title'][:80]}")
        lines.append("")

    lines.append(
        f"_Bot tidak mengubah strategi berdasarkan briefing ini — insight only._"
    )

    return "\n".join(lines)


def run():
    print(f"Insight module started — briefing every {INTERVAL // 3600}h")
    send_tg(f"🧠 *Insight module started* — briefing setiap `{INTERVAL // 3600}` jam")

    while True:
        try:
            msg = build_briefing()
            send_tg(msg)
            print(f"[{datetime.now().strftime('%H:%M')}] Briefing sent")
        except Exception as e:
            print(f"Briefing error: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    run()
