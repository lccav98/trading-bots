import requests

address = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

query = {"query": "{positions(user: \"" + address + "\") {assetId amount avgCost}}"}

resp = requests.post(
    "https://clob.polymarket.com/graphql",
    json=query,
    headers=headers,
    timeout=10
)
print("GraphQL status:", resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    print("Data:", data)