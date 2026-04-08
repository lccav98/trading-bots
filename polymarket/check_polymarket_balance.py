import requests

address = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"
address2 = "0x20aAD1bc51A8AC672969A2efef81b5423892857b"

for addr in [address, address2]:
    print(f"\nChecking Polymarket portfolio for: {addr}")
    print("=" * 50)
    
    try:
        resp = requests.get(
            f"https://gamma-api.polymarket.com/profile/{addr}",
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"Portfolio: {data}")
        else:
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

print("\n\nChecking balance allowance via CLOB API...")
print("=" * 50)

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

for addr in [address, address2]:
    print(f"\nChecking CLOB balance for: {addr}")
    try:
        client = ClobClient(
            host="https://clob.polymarket.com",
            key="0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28",
            chain_id=137,
            signature_type=0,
            funder=addr,
        )
        client.set_api_creds(client.create_or_derive_api_creds())
        
        result = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        balance = int(result["balance"]) / 1e6
        print(f"Balance: ${balance:.2f}")
        print(f"Allowances: {result.get('allowances', {})}")
    except Exception as e:
        print(f"Error: {e}")
