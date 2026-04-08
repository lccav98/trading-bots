import requests
import csv

# Get your positions from CSV
positions = []
with open(r"C:\Users\OpAC BV\Downloads\Polymarket-History-2026-04-08.csv", "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row["action"] == "Buy":
            positions.append({
                "market": row["marketName"],
                "token": row["tokenName"],
                "shares": float(row["tokenAmount"]),
                "cost": float(row["usdcAmount"]),
                "price": float(row["usdcAmount"]) / float(row["tokenAmount"]),
                "hash": row["hash"]
            })

print("Your positions:")
for p in positions:
    print(f"  {p['market'][:40]}")
    print(f"    {p['token']}: {p['shares']} shares @ ${p['price']:.4f} (${p['cost']})")

# Now search for these markets
print("\n--- Searching markets ---")
for p in positions:
    search_term = p["market"][:30].replace("?", "").replace("$", "")
    print(f"Searching: {search_term}")
    
    resp = requests.get(
        "https://clob.polymarket.com/markets",
        params={"question_contains": search_term, "limit": 5},
        timeout=10
    )
    
    if resp.status_code == 200:
        data = resp.json()
        for m in data.get("data", []):
            print(f"  Found: {m.get('question')[:50]}")
            print(f"    ID: {m.get('conditionId')}")
            print(f"    Closed: {m.get('closed')}")
            print()