#!/bin/bash
LOG="/Users/luizclaudioaraujo/Projetos/trading-bots/binance/restart.log"
PIDFILE="/tmp/hf_bot_futures.pid"
cd /Users/luizclaudioaraujo/Projetos/trading-bots/binance
export $(cat .env | grep -v '^#' | xargs -0 2>/dev/null)
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE" 2>/dev/null)
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "$(date): Bot rodando (PID=$OLD_PID)" >> "$LOG"
        exit 0
    fi
fi
nohup python3 hf_bot_futures.py >> hf_bot_futures_stdout.log 2>&1 &
NEWPID=$!
echo "$NEWPID" > "$PIDFILE"
echo "$(date): Bot iniciado (PID=$NEWPID)" >> "$LOG"
