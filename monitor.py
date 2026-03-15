#!/usr/bin/env python3
"""
Process Monitor — watchdog for all trader bots.
Checks every 5 minutes, auto-restarts crashed processes, hourly health report.
Run this once: nohup python3 monitor.py > logs/monitor.log 2>&1 &
"""

import os, time, sqlite3, subprocess, requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
REPO = os.path.dirname(os.path.abspath(__file__))

PROCESSES = [
    {"name": "Grid Bot", "script": "bot.py", "log": "logs/bot.log"},
    {"name": "Crypto Insight", "script": "insight.py", "log": "logs/insight.log"},
    {"name": "Stock Insight", "script": "stock_insight.py", "log": "logs/stock.log"},
]


def send_tg(msg):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
    except:
        pass


def is_running(script):
    result = subprocess.run(["pgrep", "-f", script], capture_output=True, text=True)
    return result.returncode == 0


def start_process(p):
    log_path = os.path.join(REPO, p["log"])
    script = os.path.join(REPO, p["script"])
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    subprocess.Popen(
        ["python3", script],
        stdout=open(log_path, "a"),
        stderr=subprocess.STDOUT,
        cwd=REPO,
    )


def get_last_log_line(log_file):
    path = os.path.join(REPO, log_file)
    try:
        with open(path, "rb") as f:
            f.seek(-2, 2)
            while f.read(1) != b"\n":
                f.seek(-2, 1)
            return f.readline().decode("utf-8", errors="ignore").strip()[-80:]
    except:
        return "No log yet"


def get_pnl():
    db = os.path.join(REPO, "data", "trades.db")
    try:
        conn = sqlite3.connect(db)
        today = datetime.now().strftime("%Y-%m-%d")
        rows = conn.execute(
            "SELECT side, value_idr FROM trades WHERE ts LIKE ?", (today + "%",)
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        conn.close()
        buys = sum(r[1] for r in rows if r[0] == "buy")
        sells = sum(r[1] for r in rows if r[0] == "sell")
        return {"today": len(rows), "pnl": sells - buys, "total": total}
    except:
        return {"today": 0, "pnl": 0, "total": 0}


def health_report(restarted=[]):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    pnl = get_pnl()
    lines = [f"💓 *Health Report — {now} WIB*\n"]

    for p in PROCESSES:
        status = "✅ Running" if is_running(p["script"]) else "❌ Down"
        last = get_last_log_line(p["log"])
        lines.append(f"*{p['name']}:* {status}")
        lines.append(f"  └ `{last}`")

    lines.append("")
    pnl_str = f"+{pnl['pnl']:,.0f}" if pnl["pnl"] >= 0 else f"{pnl['pnl']:,.0f}"
    lines.append(f"*Trading Today:* `{pnl['today']}` trades | P&L: `{pnl_str} IDR`")
    lines.append(f"*Total trades:* `{pnl['total']}`")

    if restarted:
        lines.append("")
        lines.append(f"⚡ *Auto-restarted:* {', '.join(restarted)}")

    send_tg("\n".join(lines))


def run():
    print(f"[{datetime.now()}] Monitor started")
    send_tg(
        "💓 *Monitor started* — watching 3 processes, auto-restart enabled, hourly report."
    )

    last_report = datetime.now().hour

    for p in PROCESSES:
        if not is_running(p["script"]):
            start_process(p)
            print(f"Started: {p['script']}")

    while True:
        try:
            restarted = []

            for p in PROCESSES:
                if not is_running(p["script"]):
                    print(f"[{datetime.now()}] {p['script']} crashed, restarting...")
                    start_process(p)
                    restarted.append(p["name"])

            if restarted:
                send_tg(
                    f"⚡ *Auto-restart:* {', '.join(restarted)}\n_{datetime.now().strftime('%H:%M')}_"
                )

            if datetime.now().hour != last_report:
                health_report()
                last_report = datetime.now().hour

            time.sleep(300)

        except KeyboardInterrupt:
            send_tg("🛑 *Monitor stopped.*")
            break
        except Exception as e:
            print(f"Monitor error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    run()
