import requests
import time
from datetime import datetime

# Convert timestamps from CSV
# Line 2: 1775523821
# Line 3: 1775499993  
# Line 4-6: 1775497163

timestamps = [1775523821, 1775499993, 1775497163]

print("=== Event timestamps ===")
for ts in timestamps:
    dt = datetime.fromtimestamp(ts)
    print(f"  {ts} = {dt}")

print(f"\n=== Current time ===")
now = int(time.time())
print(f"  {now} = {datetime.fromtimestamp(now)}")

print(f"\n=== Days ago ===")
for ts in timestamps:
    diff = now - ts
    days = diff / 86400
    print(f"  {ts}: {days:.1f} days ago")

# The April 7 event was 1 day ago (from the timestamp)
# April events - we're in April 2026

# Try to find any April 2026 Bitcoin markets
print("\n=== Looking for April 2026 Bitcoin markets ===")
resp = requests.get(
    "https://clob.polymarket.com/markets",
    params={"limit": 100},
    timeout=10
)

if resp.status_code == 200:
    data = resp.json()
    markets = data.get("data", [])
    
    btc_april = []
    for m in markets:
        q = m.get("question", "")
        if "bitcoin" in q.lower() and "april" in q.lower():
            btc_april.append(m)
    
    print(f"Found {len(btc_april)} Bitcoin April markets")
    for m in btc_april[:5]:
        print(f"  {m.get('question')[:60]}")
        print(f"    Active: {m.get('active')}, Closed: {m.get('closed')}")