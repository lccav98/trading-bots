"""
Lightweight ES Signal Bot - Runs fast, sends OIF orders to NT8
No browser, no slow auth - just market data + signals + OIF
"""

import yfinance as yf
import logging
import time
import sys
import os
from datetime import datetime

sys.path.insert(0, r'C:\Users\OpAC BV\Documents\Tradovate-Claude Code\apex-claude-trader')
from nt8_ati_bridge import send_oif_order

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger('signal_bot')

SYMBOL = "ES"
TIMEFRAME = 5  # minutes
CONTRACTS = 1

# EMA fast/slow for trend
EMA_FAST = 9
EMA_SLOW = 21

# RSI
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70


def get_candles():
    """Get candles from yfinance - fast"""
    ticker = yf.Ticker("ES=F")
    df = ticker.history(period="2d", interval="5m")
    if df.empty:
        return []
    df = df.reset_index()
    candles = []
    for _, row in df.iterrows():
        ts = row['Datetime'].timestamp() if 'Datetime' in row else row['Date'].timestamp()
        candles.append({
            'time': ts,
            'open': row['Open'],
            'high': row['High'],
            'low': row['Low'],
            'close': row['Close']
        })
    return candles[-50:]  # last 50 candles


def calculate_ema(prices, period):
    """Calculate EMA"""
    if len(prices) < period:
        return None
    ema = sum(prices[:period]) / period
    multiplier = 2 / (period + 1)
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema


def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    if len(prices) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    if len(gains) < period:
        return 50
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def analyze(candles):
    """Generate signal"""
    if len(candles) < 25:
        return None, "Sem dados suficientes"
    
    closes = [c['close'] for c in candles]
    current_price = closes[-1]
    
    # EMAs
    ema9 = calculate_ema(closes, EMA_FAST)
    ema21 = calculate_ema(closes, EMA_SLOW)
    
    # RSI
    rsi = calculate_rsi(closes, RSI_PERIOD)
    
    # Trend
    trend = "ALTA" if ema9 > ema21 else "BAIXA"
    
    # Signals
    signal = None
    reason = ""
    
    # Buy: EMA9 crosses above EMA21 + RSI oversold
    if ema9 > ema21 and rsi < RSI_OVERSOLD:
        signal = "BUY"
        reason = f"EMA cross up + RSI oversold ({rsi:.0f})"
    # Sell: EMA9 crosses below EMA21 + RSI overbought
    elif ema9 < ema21 and rsi > RSI_OVERBOUGHT:
        signal = "SELL"
        reason = f"EMA cross down + RSI overbought ({rsi:.0f})"
    
    return {
        'signal': signal,
        'price': current_price,
        'ema9': ema9,
        'ema21': ema21,
        'rsi': rsi,
        'trend': trend,
        'reason': reason
    }, "OK"


def send_order(signal_data):
    """Send order to NT8 via OIF"""
    if not signal_data or not signal_data.get('signal'):
        return
    
    signal = signal_data['signal']
    action = "BUY" if signal == "BUY" else "SELL"
    
    # Try different symbol formats
    for sym in ["ESM6", "ES", "ESU6"]:
        try:
            result = send_oif_order(action, sym, CONTRACTS, "MARKET", "", "", "", "ApexOIFExecutor")
            logger.info(f"✅ ORDEM ENVIADA: {action} {CONTRACTS} {sym}")
            return True
        except Exception as e:
            logger.warning(f"  {sym} failed: {e}")
            continue
    
    logger.error("❌ Nenhuma ordem enviada")
    return False


def run_once():
    """Run one analysis cycle"""
    logger.info("=" * 50)
    logger.info(f"ES Signal Bot - {datetime.now().strftime('%H:%M')}")
    logger.info("=" * 50)
    
    candles = get_candles()
    if not candles:
        logger.error("❌ Sem dados do mercado")
        return
    
    signal_data, status = analyze(candles)
    
    if signal_data and signal_data.get('signal'):
        logger.info(f"📊 {signal_data['trend']} | Preço: {signal_data['price']}")
        logger.info(f"📊 EMA9: {signal_data['ema9']:.1f} | EMA21: {signal_data['ema21']:.1f}")
        logger.info(f"📊 RSI: {signal_data['rsi']:.1f}")
        logger.info(f"🔥 SINAL: {signal_data['signal']} - {signal_data['reason']}")
        
        # Send order to NT8
        send_order(signal_data)
    else:
        logger.info(f"⏸️ Sem sinal - {status}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_once()
    else:
        # Run continuously every 5 minutes
        logger.info("Iniciando bot contínuo... (Ctrl+C para parar)")
        while True:
            run_once()
            time.sleep(300)  # 5 minutes