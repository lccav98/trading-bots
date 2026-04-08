import time
import sys
from signals.value_trading import ResolvedMarketScanner, ValueSignalGenerator

print("=== Paper Trading Mode Test ===")

scanner = ResolvedMarketScanner(min_volume=5000, min_liquidity=1000, max_fetch_pages=2)
value_gen = ValueSignalGenerator(min_volume=5000, max_hours_to_resolve=24, near_resolved_threshold=0.94)

print("Scanning markets...")
markets = scanner.scan()
print(f"Found {len(markets)} markets")

print("\nGenerating signals...")
signals = value_gen.generate_for_watchlist(markets)

print(f"\nFound {len(signals)} signals:")
for s in signals[:5]:
    print(f"  - {s.side} ${s.token_id[:20]}... | EV: {s.expected_value:.2%} | {s.reason[:50]}...")

print("\n=== Bot ready for paper trading ===")
print("To run continuous: python main.py")