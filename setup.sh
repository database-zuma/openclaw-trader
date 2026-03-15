#!/bin/bash
echo "🤖 OpenClaw Trader Setup"
echo "========================"

pip install requests python-dotenv --break-system-packages -q

mkdir -p data logs

if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ .env created — edit it before running the bot"
else
    echo "⏭️  .env already exists"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env — set your Telegram bot token + chat ID"
echo "  2. Backtest dulu: python3 backtest.py --days 30"
echo "  3. Paper trade:   python3 bot.py"
echo "  4. Live trade:    set PAPER_TRADE=false di .env, lalu python3 bot.py"
