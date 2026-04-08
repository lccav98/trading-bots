import os
from dotenv import load_dotenv
load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

print("Connecting to Polymarket CLOB (via py_clob_client)...")

client = ClobClient(
    host="https://clob.polymarket.com",
    key=os.environ.get("POLYMARKET_PRIVATE_KEY"),
    chain_id=137,
    signature_type=1,
    funder=os.environ.get("FUNDER_ADDRESS"),
)

# Create API credentials
client.set_api_creds(client.create_or_derive_api_creds())

# Get balance allowance
result = client.get_balance_allowance(
    BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=1)
)

balance_val = int(result.get("balance", 0)) / 1e6
allowance_val = int(result.get("allowance", 0)) / 1e6

print("=== Polymarket Account ===")
print(f"Balance: ${balance_val:.2f} USDC")
print(f"Allowance: ${allowance_val:.2f} USDC")
print(f"Full response: {result}")