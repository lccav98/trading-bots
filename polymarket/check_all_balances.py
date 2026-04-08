import requests

address = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

usdc_polygon = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
usdc_base = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

rpc_polygon = "https://polygon-rpc.com"
rpc_base = "https://mainnet.base.org"
rpc_ethereum = "https://eth.llamarpc.com"

def check_balance(rpc, usdc_address, network_name):
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{
            "to": usdc_address,
            "data": f"0x70a08231000000000000000000000000{address[2:].lower()}"
        }, "latest"],
        "id": 1
    }
    try:
        resp = requests.post(rpc, json=payload, timeout=10)
        data = resp.json()
        if "result" in data and data["result"] != "0x" and data["result"] != "0x0":
            balance = int(data["result"], 16) / 1e6
            print(f"{network_name}: ${balance:.2f} USDC")
            return balance
        else:
            print(f"{network_name}: $0.00 USDC")
            return 0
    except Exception as e:
        print(f"{network_name}: Error - {e}")
        return None

print(f"Checking USDC balances for: {address}\n")
print("=" * 40)

check_balance(rpc_polygon, usdc_polygon, "Polygon")
check_balance(rpc_base, usdc_base, "Base")

print("=" * 40)
print("\nDone!")
