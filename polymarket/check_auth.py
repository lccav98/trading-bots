from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
import requests
import time

key = "0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28"
address = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

client = ClobClient(
    host="https://clob.polymarket.com",
    key=key,
    chain_id=137,
    signature_type=1,
    funder=address,
)
client.set_api_creds(client.create_or_derive_api_creds())

# Try to get positions via API
print("=== Checking via authenticated API ===")

# Try to get orders - this might show open positions
try:
    orders = client.get_orders()
    print("Open orders:", orders)
except Exception as e:
    print(f"get_orders error: {e}")

# Try to get balance with more details
try:
    result = client.get_balance_allowance(
        asset_type="COLLATERAL"
    )
    print("\nBalance allowance:", result)
except Exception as e:
    print(f"get_balance_allowance error: {e}")

# Try to get positions using different method - check all possible endpoints
print("\n=== Checking market data ===")

# Get markets with Bitcoin
resp = requests.get(
    "https://clob.polymarket.com/markets",
    params={"limit": 10, "cursor": ""},
    timeout=10
)
if resp.status_code == 200:
    data = resp.json()
    markets = data.get("data", [])
    print(f"Got {len(markets)} markets")
    for m in markets[:5]:
        if "bitcoin" in m.get("question", "").lower() or "btc" in m.get("question", "").lower():
            print(f"\nBTC Market: {m.get('question')[:60]}")
            print(f"  ID: {m.get('conditionId')}")
            print(f"  Closed: {m.get('closed')}")