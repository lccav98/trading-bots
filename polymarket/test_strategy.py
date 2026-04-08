import requests
import time
from datetime import datetime, timezone

GAMMA_URL = "https://gamma-api.polymarket.com/markets"

BLOCKED_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "crypto", 
    "solana", "dogecoin", "ether", "blockchain",
    "dip to", "below $", "above $"
]

BLOCKED_NEWS_KEYWORDS = [
    "will the price",
    "will be above", "will be below",
    "january", "february", "march", "april",
    "may", "june", "july", "august",
    "september", "october", "november", "december"
]

MIN_HOURS = 0.5
MAX_HOURS = 12
MAX_PRICE = 0.90

print("=" * 60)
print("TESTING UPDATED STRATEGY")
print("=" * 60)

# Fetch markets
params = {"closed": "false", "limit": 50, "order": "volume24hr", "ascending": "false"}
resp = requests.get(GAMMA_URL, params=params, timeout=15)
markets = resp.json()

print(f"\nTotal markets fetched: {len(markets)}")

total_blocked = 0
crypto_blocked = 0
news_blocked = 0
time_blocked = 0
price_blocked = 0
passed = 0

for m in markets:
    question = m.get("question", "")
    q_lower = question.lower()
    
    # Check crypto
    blocked = False
    for kw in BLOCKED_KEYWORDS:
        if kw in q_lower:
            crypto_blocked += 1
            blocked = True
            break
    
    # Check news/far-future
    if not blocked:
        for kw in BLOCKED_NEWS_KEYWORDS:
            if kw in q_lower:
                news_blocked += 1
                blocked = True
                break
    
    if blocked:
        total_blocked += 1
        continue
    
    # Check time
    end_date = m.get("endDate") or m.get("end_date")
    if end_date:
        try:
            end_ts = datetime.fromisoformat(end_date.replace("Z", "+00:00")).timestamp()
            hours_left = (end_ts - datetime.now(timezone.utc).timestamp()) / 3600
            
            if hours_left < MIN_HOURS or hours_left > MAX_HOURS:
                time_blocked += 1
                continue
        except:
            time_blocked += 1
            continue
    else:
        time_blocked += 1
        continue
    
    # Check price
    price = m.get("price", 0.5) or 0.5
    price_no = m.get("priceNo", 0.5) or 0.5
    if price >= MAX_PRICE or price_no >= MAX_PRICE:
        price_blocked += 1
        continue
    
    passed += 1
    print(f"\nPASSED: {question[:60]}")
    print(f"   Price: ${price:.2f} / ${price_no:.2f}")
    print(f"   Hours: {hours_left:.1f}h")
    print(f"   Volume: ${m.get('volume24hr', 0):,.0f}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Total markets: {len(markets)}")
print(f"X Crypto blocked: {crypto_blocked}")
print(f"X News/far-future blocked: {news_blocked}")
print(f"X Time blocked (<{MIN_HOURS}h or >{MAX_HOURS}h): {time_blocked}")
print(f"X Price blocked (>${MAX_PRICE}): {price_blocked}")
print(f"OK Passed filters: {passed}")