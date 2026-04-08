from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

key = "0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28"

client = ClobClient(
    host="https://clob.polymarket.com",
    key=key,
    chain_id=137,
    signature_type=1,
    funder="0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3",
)
client.set_api_creds(client.create_or_derive_api_creds())

# Get all positions
try:
    positions = client.get_positions()
    print("Positions:")
    print(positions)
except Exception as e:
    print("Error getting positions:", e)

# Try get_open_orders
try:
    orders = client.get_orders()
    print("\\nOpen orders:")
    print(orders)
except Exception as e:
    print("Error getting orders:", e)