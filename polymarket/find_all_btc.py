import requests

# Get ALL markets (including closed)
print("=== Looking for Bitcoin April 2026 markets (all) ===")

for i in range(0, 500, 100):
    resp = requests.get(
        "https://clob.polymarket.com/markets",
        params={"limit": 100, "offset": i},
        timeout=10
    )
    
    if resp.status_code == 200:
        data = resp.json()
        markets = data.get("data", [])
        
        for m in markets:
            q = m.get("question", "")
            # Look for bitcoin + either 50k, 60k, 72k or any April date
            if "bitcoin" in q.lower() and ("50" in q or "60" in q or "72" in q or "2026" in q or "april" in q):
                print(f"\n{q[:80]}")
                print(f"  ID: {m.get('conditionId')}")
                print(f"  Closed: {m.get('closed')}, Accepting: {m.get('accepting_orders')}")
                print(f"  Volume: {m.get('volume')}")
        
        if len(markets) < 100:
            break

print("\n=== Done ===")
print("Note: The API seems to only show 2023 data. Your markets might be archived differently.")