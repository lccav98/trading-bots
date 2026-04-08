import requests

# Try different subgraph endpoint
resp = requests.post(
    "https://clob.polymarket.com/query",
    json={
        "query": """
        query GetPositions($user: String!) {
            positions(where: {user: $user}) {
                assetId
                amount
                avgPrice
                asset {
                    conditionId
                    question
                }
            }
        }
        """,
        "variables": {"user": "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3".lower()}
    },
    headers={"Content-Type": "application/json"},
    timeout=10
)

print("Query status:", resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    print(data)
else:
    print(resp.text[:300])

# Alternative: check recent trades from history file
print("\n--- From your CSV history ---")
import csv
with open(r"C:\Users\OpAC BV\Downloads\Polymarket-History-2026-04-08.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row["action"] == "Buy":
            print(f"  {row['marketName'][:40]}... | {row['tokenName']} @ ${float(row['usdcAmount'])/float(row['tokenAmount']):.2f}")