#!/bin/bash
REPO="$HOME/openclaw-trader"
LOG="$REPO/logs/update.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

TOKEN=$(python3 -c "
import json
d=json.load(open('$HOME/.openclaw/openclaw.json'))
for path in [['channels','telegram','token'],['channel','token'],['telegram','token']]:
    try:
        v=d
        for k in path: v=v[k]
        print(v); break
    except: pass
" 2>/dev/null)

CHAT_ID=$(curl -s "https://api.telegram.org/bot${TOKEN}/getUpdates" | python3 -c "
import json,sys
d=json.load(sys.stdin)
msgs=d.get('result',[])
if msgs: print(msgs[-1]['message']['chat']['id'])
" 2>/dev/null)

send_tg() {
    curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
        -d "chat_id=${CHAT_ID}" -d "text=$1" -d "parse_mode=Markdown" > /dev/null
}

mkdir -p "$REPO/logs"
echo "[$TIMESTAMP] Checking for updates..." >> "$LOG"

cd "$REPO"
BEFORE=$(git rev-parse HEAD 2>/dev/null)
git pull -q >> "$LOG" 2>&1
PULL_STATUS=$?
AFTER=$(git rev-parse HEAD 2>/dev/null)

if [ $PULL_STATUS -ne 0 ]; then
    send_tg "⚠️ *Trader update FAILED* ($TIMESTAMP)%0Agit pull error"
    exit 1
fi

[ "$BEFORE" = "$AFTER" ] && exit 0

CHANGED=$(git log --oneline "$BEFORE".."$AFTER" 2>/dev/null | head -3)
echo "[$TIMESTAMP] Changes detected, restarting bots..." >> "$LOG"

pkill -f "python3 bot.py" 2>/dev/null
pkill -f "python3 insight.py" 2>/dev/null
pkill -f "python3 stock_insight.py" 2>/dev/null
sleep 3

nohup python3 "$REPO/bot.py"           >> "$REPO/logs/bot.log"   2>&1 &
nohup python3 "$REPO/insight.py"       >> "$REPO/logs/insight.log" 2>&1 &
nohup python3 "$REPO/stock_insight.py" >> "$REPO/logs/stock.log"  2>&1 &

echo "[$TIMESTAMP] Bots restarted" >> "$LOG"
send_tg "✅ *Trader updated & restarted* ($TIMESTAMP)%0A%0AChanges:%0A\`\`\`${CHANGED}\`\`\`%0A%0AProcesses: bot.py + insight.py + stock_insight.py"
