import requests

# Try to get market info by condition ID or search more specifically
# The search above returned old markets (2023) - need to find recent ones

# Try with different search params
resp = requests.get(
    "https://clob.polymarket.com/markets",
    params={
        "active": "true",
        "closed": "false", 
        "limit": "50",
    },
    timeout=10
)

print("Active markets count:", resp.json().get("count", 0) if resp.status_code == 200 else "error")

# Let's try searching for Bitcoin specifically in a different way
# Check if there's a specific endpoint for condition ID lookup

# Try the info endpoint for specific token hashes from CSV
hashes = [
    "0xe4330513cd025d295bd80a4ac1f234c24648243d199e7f1b445164c8282f2679",
    "0xa5d264fd4e896a06a6ff95717b9412b8f800b72441bfea4060f2fe1a7f028c2d",
]

for h in hashes:
    print(f"\nTrying hash: {h[:20]}...")
    # Try to get trade info
    try:
        resp = requests.get(f"https://clob.polymarket.com/trades?hash={h}", timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"  Data: {resp.json()}")
    except Exception as e:
        print(f"  Error: {e}")