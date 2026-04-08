import requests

print("=== Polymarket Account & Polygon Gas ===")
print()

# 1. Polymarket Balance
print("--- Polymarket Account ---")
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
    
    client = ClobClient(
        host="https://clob.polymarket.com",
        key="0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28",
        chain_id=137,
        signature_type=1,
        funder="0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3",
    )
    client.set_api_creds(client.create_or_derive_api_creds())
    
    result = client.get_balance_allowance(
        BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=1)
    )
    
    balance = int(result.get("balance", 0)) / 1e6
    print(f"Balance: ${balance:.2f} USDC")
    print(f"Status: Paper Trading (no real funds)")
except Exception as e:
    print(f"Error: {e}")

print()

# 2. POL Price
print("--- POL (Polygon) Price ---")
try:
    r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=polygon-ecosystem-token&vs_currencies=usd", timeout=10)
    pol_price = r.json()["polygon-ecosystem-token"]["usd"]
    print(f"POL: ${pol_price:.4f}")
except:
    print("POL: ~$0.09 (fallback)")

print()

# 3. Gas - try multiple RPCs
print("--- Polygon Gas ---")
gas_found = False

rpcs = [
    "https://rpc.ankr.com/polygon",
    "https://polygon-rpc.com",
    "https://poly-rpc.gateway.pokt.network"
]

for rpc in rpcs:
    try:
        r = requests.post(rpc, json={
            "jsonrpc": "2.0",
            "method": "eth_gasPrice",
            "params": []
        }, timeout=5)
        
        if r.status_code == 200:
            result = r.json().get("result")
            if result:
                gas_wei = int(result, 16)
                gas_gwei = gas_wei / 1e9
                
                print(f"RPC: {rpc.replace('https://', '')}")
                print(f"Gas: {gas_gwei:.2f} Gwei")
                print(f"Cost per swap (~65k gas): ${gas_gwei * 0.09 * 65000 / 1e9:.4f}")
                gas_found = True
                break
    except:
        pass

if not gas_found:
    print("RPCs unavailable - network may be congested")
    print("Typical POL gas: 30-100 Gwei")
    print("Typical swap cost: $0.02-$0.10")