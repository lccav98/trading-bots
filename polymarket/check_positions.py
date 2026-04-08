import requests

address = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

resp = requests.get(f"https://clob.polymarket.com/positions?address={address}", timeout=10)
print("Status:", resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    positions = data.get("positions", [])
    print("Positions count:", len(positions))
    for p in positions[:3]:
        asset = p.get("assetID", "N/A")
        qty = p.get("quantity", 0)
        avg = p.get("avgPrice", 0)
        print(f"  {asset[:30]}: {qty} @ {avg}")
else:
    print("Response:", resp.text[:200])