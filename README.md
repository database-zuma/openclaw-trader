# OpenClaw Trader

Indodax grid trading bot. Runs on Android Termux. Managed by OpenClaw agent via Telegram.

## Urutan Wajib

```
Backtest → Paper Trade (3+ hari) → Live Trade
```

**Jangan skip backtest dan paper trade.**

## Install

```bash
git clone https://github.com/database-zuma/openclaw-trader.git ~/openclaw-trader
cd ~/openclaw-trader
bash setup.sh
```

## Config (.env)

```bash
nano .env
```

| Key | Keterangan |
|-----|-----------|
| `TELEGRAM_BOT_TOKEN` | Token bot Telegram kamu |
| `TELEGRAM_CHAT_ID` | Chat ID kamu |
| `TRADING_PAIR` | Pair (btcidr, ethidr, usdtidr, dll) |
| `PAPER_TRADE` | `true` = dummy money, `false` = real |
| `CAPITAL_IDR` | Modal dalam IDR |
| `GRID_LEVELS` | Jumlah grid (5-10) |
| `GRID_SPACING_PCT` | Jarak antar grid dalam % (0.5-2.0) |
| `POLL_SECONDS` | Cek harga tiap N detik (30) |

Untuk live trading, tambahkan juga:
```
INDODAX_API_KEY=...
INDODAX_SECRET_KEY=...
```
Generate di: Indodax → Account → API Management

## Backtest

Test strategi pakai data historis (tanpa uang):

```bash
python3 backtest.py --pair btcidr --days 30 --capital 500000
python3 backtest.py --pair btcidr --days 7  --capital 1000000 --levels 10 --spacing 0.5
```

## Paper Trade

```bash
python3 bot.py
```

Bot jalan pakai harga real tapi tidak eksekusi order beneran. Laporan harian dikirim ke Telegram.

## Run di Background (Termux)

```bash
nohup python3 bot.py > logs/bot.log 2>&1 &
echo "Bot PID: $!"
```

Stop:
```bash
pkill -f bot.py
```

## Live Trade

Setelah paper trade profitable 3+ hari:
1. Daftar & verifikasi akun Indodax
2. Generate API key di Indodax → Account → API Management
3. Set di `.env`: `PAPER_TRADE=false`, isi `INDODAX_API_KEY` dan `INDODAX_SECRET_KEY`
4. Jalankan bot

## OpenClaw Agent

Kamu bisa manage bot via Telegram dengan bilang ke agent:
- *"backtest BTC 30 hari"*
- *"start paper trading"*
- *"cek status bot"*
- *"lihat trades hari ini"*
- *"stop bot"*

Instruksi lengkap di `AGENTS.md`.

## Disclaimer

Trading crypto mengandung risiko. Bot ini adalah alat — bukan jaminan profit.
Selalu mulai dari backtest dan paper trading sebelum pakai uang nyata.
