import requests
import json

# Try the poly.market website API
address = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

# Check orders endpoint
resp = requests.get(
    f"https://clob.polymarket.com/orders?address={address}",
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=10
)
print("Orders status:", resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    print("Orders:", json.dumps(data, indent=2)[:1000])

# Check trades endpoint  
resp2 = requests.get(
    f"https://clob.polymarket.com/trades?address={address}",
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=10
)
print("\\nTrades status:", resp2.status_code)
if resp2.status_code == 200:
    data2 = resp2.json()
    print("Trades count:", len(data2.get("trades", [])))
    for t in data2.get("trades", [])[:3]:
        print(f"  {t}")