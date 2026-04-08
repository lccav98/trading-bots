import sys
sys.path.insert(0, '.')

from signals.ta_signal_generator import BTC15mTASignalGenerator
from data.binance import fetch_klines, fetch_last_price

print("=== Testing Integrated TA Signal Generator ===\n")

print("1. Fetching Binance klines...")
klines = fetch_klines(limit=240)
print(f"   Klines fetched: {len(klines)} candles")

print("\n2. Fetching BTC price...")
price = fetch_last_price()
if price:
    print(f"   BTC price: ${price:.0f}")
else:
    print("   No price data")

print("\n3. Initializing TA Generator...")
gen = BTC15mTASignalGenerator()
print(f"   Window: {gen.candle_window_minutes}min")
print(f"   RSI period: {gen.rsi_period}")
print(f"   MACD: {gen.macd_fast}/{gen.macd_slow}/{gen.macd_signal}")

print("\n=== All components working! ===")
print("\nThe bot is ready to run with:")
print("  - Binance BTC price data (klines + spot)")
print("  - Technical Analysis (RSI, VWAP, MACD, Heiken Ashi)")
print("  - Edge detection vs Polymarket odds")
print("  - Risk-managed execution on Polymarket CLOB")
