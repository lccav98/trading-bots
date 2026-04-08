from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

client = ClobClient(
    host="https://clob.polymarket.com",
    key="0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28",
    chain_id=137,
)
client.set_api_creds(client.create_or_derive_api_creds())

result = client.get_balance_allowance(
    BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
)
print(f"Response keys: {result.keys()}")
print(f"Response: {result}")

balance_key = "balance" if "balance" in result else "usdc"
if balance_key in result:
    balance = int(result[balance_key]) / 1e6
    print(f"Balance: ${balance:.2f} USDC")
