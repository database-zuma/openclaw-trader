#!/usr/bin/env python3
"""
IDX Stock Insight — screener for Indonesian stocks (LQ45 + top caps)
Insight only — no auto trading. User executes manually on Stockbit.
Schedule: 08:30, 12:00, 15:30, 16:30 WIB
"""

import os, time, requests
from datetime import datetime
from dotenv import load_dotenv

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    print("Run: pip install yfinance pandas --break-system-packages")
    exit(1)

load_dotenv()

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

LQ45 = [
    "AALI",
    "ADRO",
    "AKRA",
    "AMRT",
    "ANTM",
    "ARTO",
    "ASII",
    "BBCA",
    "BBNI",
    "BBRI",
    "BBTN",
    "BMRI",
    "BRIS",
    "BRPT",
    "BUKA",
    "CPIN",
    "CTRA",
    "EMTK",
    "ERAA",
    "EXCL",
    "GGRM",
    "GOTO",
    "HMSP",
    "HRUM",
    "ICBP",
    "INCO",
    "INDF",
    "INKP",
    "INTP",
    "ISAT",
    "ITMG",
    "JPFA",
    "KLBF",
    "MAPI",
    "MDKA",
    "MEDC",
    "MIKA",
    "MNCN",
    "PGAS",
    "PGEO",
    "PTBA",
    "SMGR",
    "TBIG",
    "TLKM",
    "TOWR",
    "TPIA",
    "UNTR",
    "UNVR",
    "WIKA",
    "WSKT",
]

TICKERS = [f"{s}.JK" for s in LQ45]


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
        print(f"TG error: {e}")


def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def analyze(ticker_code):
    try:
        t = yf.Ticker(ticker_code)
        hist = t.history(period="3mo", interval="1d")
        if hist.empty or len(hist) < 20:
            return None

        close = hist["Close"]
        volume = hist["Volume"]
        price = float(close.iloc[-1])
        prev = float(close.iloc[-2])
        pct = (price - prev) / prev * 100

        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma50 = float(close.rolling(50).mean().iloc[-1]) if len(hist) >= 50 else None
        rsi = float(calc_rsi(close).iloc[-1])

        vol_today = float(volume.iloc[-1])
        vol_avg = float(volume.rolling(20).mean().iloc[-1])
        vol_ratio = vol_today / vol_avg if vol_avg > 0 else 1

        signals = []
        score = 0

        if rsi < 30:
            signals.append("RSI oversold")
            score += 2
        elif rsi < 40:
            signals.append("RSI mendekati oversold")
            score += 1
        elif rsi > 70:
            signals.append("RSI overbought")
            score -= 2
        elif rsi > 60:
            signals.append("RSI mendekati overbought")
            score -= 1

        if price > ma20:
            signals.append("di atas MA20")
            score += 1
        else:
            signals.append("di bawah MA20")
            score -= 1

        if ma50 and price > ma50:
            signals.append("di atas MA50")
            score += 1
        elif ma50:
            signals.append("di bawah MA50")
            score -= 1

        if vol_ratio > 2:
            signals.append(f"volume spike {vol_ratio:.1f}x")
            score += 1 if pct > 0 else -1

        if score >= 3:
            label = "🟢 BUY SIGNAL"
        elif score >= 1:
            label = "🟡 WATCH"
        elif score <= -3:
            label = "🔴 AVOID / JUAL"
        elif score <= -1:
            label = "🟠 HATI-HATI"
        else:
            label = "⚪ NEUTRAL"

        return {
            "code": ticker_code.replace(".JK", ""),
            "price": price,
            "pct": pct,
            "rsi": rsi,
            "ma20": ma20,
            "vol_ratio": vol_ratio,
            "signals": signals,
            "label": label,
            "score": score,
        }
    except:
        return None


def morning_briefing():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    send_tg(
        f"📈 *IDX Morning Briefing — {now} WIB*\n\nScanning {len(LQ45)} saham LQ45...\n_Ini insight only — eksekusi manual di Stockbit._"
    )

    results = []
    for tk in TICKERS:
        r = analyze(tk)
        if r:
            results.append(r)
        time.sleep(0.5)

    if not results:
        send_tg("⚠️ Gagal fetch data saham. Cek koneksi.")
        return

    buys = [r for r in results if r["score"] >= 3]
    watches = [r for r in results if 1 <= r["score"] < 3]
    avoids = [r for r in results if r["score"] <= -3]

    msg = [f"📊 *Hasil Scan — {datetime.now().strftime('%Y-%m-%d')}*\n"]
    msg.append(f"Total saham: `{len(results)}`")
    msg.append(f"Buy signal: `{len(buys)}`")
    msg.append(f"Watch: `{len(watches)}`")
    msg.append(f"Avoid: `{len(avoids)}`\n")

    if buys:
        msg.append("*🟢 BUY SIGNALS:*")
        for r in sorted(buys, key=lambda x: -x["score"])[:5]:
            pct_str = f"+{r['pct']:.1f}%" if r["pct"] >= 0 else f"{r['pct']:.1f}%"
            msg.append(
                f"`{r['code']}` — {r['price']:,.0f} ({pct_str}) | RSI {r['rsi']:.0f} | {', '.join(r['signals'][:2])}"
            )
        msg.append("")

    if watches:
        msg.append("*🟡 WATCH LIST:*")
        for r in sorted(watches, key=lambda x: -x["score"])[:5]:
            msg.append(f"`{r['code']}` — {r['price']:,.0f} | RSI {r['rsi']:.0f}")
        msg.append("")

    if avoids:
        msg.append("*🔴 AVOID/JUAL:*")
        for r in sorted(avoids, key=lambda x: x["score"])[:3]:
            msg.append(f"`{r['code']}` — {r['price']:,.0f} | RSI {r['rsi']:.0f}")
        msg.append("")

    msg.append(
        "_RSI < 30 = oversold (potensi naik) | RSI > 70 = overbought (potensi turun)_"
    )
    msg.append(
        "_MA20/50 = tren jangka pendek/menengah | Volume spike = ada pergerakan besar_"
    )

    send_tg("\n".join(msg))


def midday_update():
    now = datetime.now().strftime("%H:%M")
    results = []
    for tk in TICKERS:
        r = analyze(tk)
        if r and abs(r["pct"]) > 2:
            results.append(r)
        time.sleep(0.3)

    if not results:
        send_tg(f"📊 *{now} WIB* — Tidak ada pergerakan signifikan (>2%) saat ini.")
        return

    msg = [f"📊 *Midday Update — {now} WIB*\n"]
    msg.append("*Pergerakan signifikan (>2%):*")
    for r in sorted(results, key=lambda x: -abs(x["pct"]))[:8]:
        icon = "🚀" if r["pct"] > 0 else "📉"
        pct_str = f"+{r['pct']:.1f}%" if r["pct"] >= 0 else f"{r['pct']:.1f}%"
        vol = f" vol {r['vol_ratio']:.1f}x" if r["vol_ratio"] > 1.5 else ""
        msg.append(f"{icon} `{r['code']}` {pct_str} @ {r['price']:,.0f}{vol}")

    send_tg("\n".join(msg))


def closing_summary():
    now = datetime.now().strftime("%Y-%m-%d")
    results = []
    for tk in TICKERS:
        r = analyze(tk)
        if r:
            results.append(r)
        time.sleep(0.5)

    if not results:
        return

    top_gainers = sorted(results, key=lambda x: -x["pct"])[:5]
    top_losers = sorted(results, key=lambda x: x["pct"])[:5]
    buys_tmrw = [r for r in results if r["score"] >= 3]

    msg = [f"🔔 *Closing Summary — {now}*\n"]
    msg.append("*Top Gainers:*")
    for r in top_gainers:
        msg.append(f"🚀 `{r['code']}` +{r['pct']:.1f}%")

    msg.append("\n*Top Losers:*")
    for r in top_losers:
        msg.append(f"📉 `{r['code']}` {r['pct']:.1f}%")

    if buys_tmrw:
        msg.append(f"\n*Kandidat Besok ({len(buys_tmrw)} saham):*")
        for r in sorted(buys_tmrw, key=lambda x: -x["score"])[:5]:
            msg.append(
                f"👀 `{r['code']}` RSI {r['rsi']:.0f} | {', '.join(r['signals'][:2])}"
            )

    msg.append("\n_Semua ini adalah sinyal teknikal, bukan financial advice._")
    msg.append("_Selalu riset sendiri sebelum beli di Stockbit._")

    send_tg("\n".join(msg))


def run():
    print("IDX Stock Insight started")
    send_tg(
        "📈 *IDX Stock Insight aktif*\n\nJadwal:\n• 08:30 — Morning scan\n• 12:00 — Midday update\n• 15:30 — Pre-close\n• 16:30 — Closing summary\n\n_Semua insight only — eksekusi manual di Stockbit._"
    )

    while True:
        now = datetime.now()
        h, m = now.hour, now.minute

        if h == 8 and m == 30:
            morning_briefing()
            time.sleep(60)
        elif h == 12 and m == 0:
            midday_update()
            time.sleep(60)
        elif h == 15 and m == 30:
            midday_update()
            time.sleep(60)
        elif h == 16 and m == 30:
            closing_summary()
            time.sleep(60)
        else:
            time.sleep(30)


if __name__ == "__main__":
    run()
