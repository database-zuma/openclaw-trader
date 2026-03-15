# AGENTS.md — OpenClaw Trader

OpenClaw agent instructions for managing the trading bot.

## What You Can Do

| Command from user | What to do |
|---|---|
| "backtest BTC 30 hari" | `python3 backtest.py --pair btcidr --days 30` |
| "backtest dengan modal 1jt" | `python3 backtest.py --capital 1000000` |
| "start paper trading" | `nohup python3 bot.py > logs/bot.log 2>&1 &` |
| "stop bot" | `pkill -f bot.py` |
| "cek status bot" | `pgrep -f bot.py && echo running || echo stopped` |
| "lihat trades hari ini" | query SQLite (lihat section DB) |
| "lihat log" | `tail -50 logs/$(date +%Y-%m-%d).log` |
| "ganti pair ke ETH" | edit `.env` set `TRADING_PAIR=ethidr`, restart bot |
| "mode live" | edit `.env` set `PAPER_TRADE=false`, restart bot |

## Bot Files

```
~/openclaw-trader/
├── bot.py          ← main grid bot (paper + live)
├── backtest.py     ← backtest against historical data
├── .env            ← config (API keys, pair, capital)
├── data/trades.db  ← SQLite trade history
└── logs/           ← daily log files
```

## Check Trade History (SQLite)

```bash
cd ~/openclaw-trader
python3 -c "
import sqlite3
conn = sqlite3.connect('data/trades.db')
rows = conn.execute('SELECT ts, side, price, value_idr, status FROM trades ORDER BY id DESC LIMIT 20').fetchall()
for r in rows: print(r)
conn.close()
"
```

## P&L Summary

```bash
cd ~/openclaw-trader
python3 -c "
import sqlite3
from datetime import datetime
conn = sqlite3.connect('data/trades.db')
today = datetime.now().strftime('%Y-%m-%d')
rows = conn.execute('SELECT side, value_idr FROM trades WHERE ts LIKE ?', (today+'%',)).fetchall()
buys  = sum(r[1] for r in rows if r[0]=='buy')
sells = sum(r[1] for r in rows if r[0]=='sell')
print(f'Trades: {len(rows)} | Buys: {buys:,.0f} | Sells: {sells:,.0f} | P&L: {sells-buys:,.0f} IDR')
conn.close()
"
```

## Safety Rules

- ALWAYS backtest before live trading
- ALWAYS run paper trading minimum 3 days before switching to live
- NEVER set PAPER_TRADE=false without user explicitly asking
- NEVER change CAPITAL_IDR to more than user specified
- If bot crashes 3x in a row → stop and report to user, don't auto-restart
