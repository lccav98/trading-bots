import requests

# Check if the address has ANY activity on Polygon
address = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

# Check via PolygonScan API (no key needed for basic queries)
resp = requests.get(
    f"https://api.polygonscan.com/api",
    params={
        "module": "account",
        "action": "balance",
        "address": address,
        "tag": "latest",
    },
    timeout=10
)
data = resp.json()
print(f"PolygonScan API Response: {data}")

if data.get("status") == "1":
    balance = int(data["result"]) / 1e18
    print(f"MATIC Balance: {balance:.4f}")
else:
    print(f"Error: {data.get('message', 'Unknown')}")
