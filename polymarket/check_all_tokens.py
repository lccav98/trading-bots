import requests

address = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

usdc_native = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
usdc_bridged = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
usdc_binance = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"

rpc = "https://polygon-rpc.com"

def check_token_balance(rpc, token_address, token_name):
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{
            "to": token_address,
            "data": f"0x70a08231000000000000000000000000{address[2:].lower()}"
        }, "latest"],
        "id": 1
    }
    try:
        resp = requests.post(rpc, json=payload, timeout=10)
        data = resp.json()
        result = data.get("result", "")
        if result and result != "0x" and result != "0x0":
            balance = int(result, 16) / 1e6
            print(f"[{token_name}] ${balance:.2f} USDC")
            return balance
        else:
            print(f"[{token_name}] $0.00")
            return 0
    except Exception as e:
        print(f"[{token_name}] Error: {e}")
        return None

print(f"Checking all USDC variants for: {address}\n")

check_token_balance(rpc, usdc_native, "Native USDC")
check_token_balance(rpc, usdc_bridged, "Bridged USDC.e")

# Also check MATIC balance
matic_payload = {
    "jsonrpc": "2.0",
    "method": "eth_getBalance",
    "params": [address, "latest"],
    "id": 1
}
try:
    resp = requests.post(rpc, json=matic_payload, timeout=10)
    data = resp.json()
    result = data.get("result", "0x0")
    if result != "0x0":
        matic = int(result, 16) / 1e18
        print(f"[MATIC/POL] {matic:.4f}")
    else:
        print("[MATIC/POL] 0.0000")
except Exception as e:
    print(f"[MATIC/POL] Error: {e}")
