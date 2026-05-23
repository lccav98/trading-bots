#!/bin/bash
case "$1" in
    status)
        launchctl list | grep com.tradingbot.futures
        ps aux | grep -v grep | grep -i "hf_bot_futures.py"
        ;;
    start)
        launchctl start com.tradingbot.futures
        ;;
    stop)
        launchctl stop com.tradingbot.futures
        pkill -f "hf_bot_futures.py" 2>/dev/null
        ;;
    restart)
        pkill -f "hf_bot_futures.py" 2>/dev/null
        sleep 2
        /Users/luizclaudioaraujo/Projetos/trading-bots/binance/run_bot.sh
        ;;
    *)
        echo "Uso: $0 {status|start|stop|restart}"
        ;;
esac
