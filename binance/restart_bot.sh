#!/bin/bash
# Auto-restart script para hf_bot_futures.py

LOG="/Users/luizclaudioaraujo/Projetos/trading-bots/binance/restart.log"
PIDFILE="/tmp/hf_bot_futures.pid"

# Se já está rodando, não faz nada
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "$(date): Bot já rodando (PID=$PID)" >> "$LOG"
        exit 0
    fi
fi

cd /Users/luizclaudioaraujo/Projetos/trading-bots/binance
nohup python3 hf_bot_futures.py > hf_bot_futures_stdout.log 2>&1 &
NEWPID=$!
echo "$NEWPID" > "$PIDFILE"
echo "$(date): Bot reiniciado (PID=$NEWPID)" >> "$LOG"
