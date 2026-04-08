import requests

# Get all Bitcoin markets
resp = requests.get(
    "https://clob.polymarket.com/markets",
    params={"active": "true", "limit": "100"},
    timeout=10
)

if resp.status_code == 200:
    data = resp.json()
    markets = data.get("data", [])
    
    bitcoin_markets = [m for m in markets if "bitcoin" in m.get("question", "").lower() or "btc" in m.get("question", "").lower()]
    
    print(f"Found {len(bitcoin_markets)} Bitcoin markets:\n")
    for m in bitcoin_markets[:10]:
        print(f"Question: {m.get('question')}")
        print(f"Condition ID: {m.get('conditionId')}")
        print(f"Active: {m.get('active')}, Closed: {m.get('closed')}")
        print(f"Volume: {m.get('volume')}")
        print("-" * 50)
else:
    print(f"Error: {resp.status_code}")