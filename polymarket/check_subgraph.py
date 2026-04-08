import requests
import json

address = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

# Try to get trade history from events API
# First get events from subgraph
query = """
{
  user(id: "%s") {
    positions {
      market {
        id
        question
      }
      outcome
      amount
    }
  }
}
""" % address.lower()

resp = requests.post(
    "https://api.polymarket.com/subgraph",
    json={"query": query},
    timeout=10
)

print("Subgraph status:", resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    print(json.dumps(data, indent=2)[:1000])
else:
    print(resp.text[:500])