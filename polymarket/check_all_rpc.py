import requests

address = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"
usdc_polygon = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"

rpc_endpoints = [
    "https://polygon-rpc.com",
    "https://rpc.ankr.com/polygon",
    "https://polygon-mainnet.public.blastapi.io",
]

for rpc in rpc_endpoints:
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{
            "to": usdc_polygon,
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
            print(f"[OK] {rpc}: ${balance:.2f} USDC")
        else:
            print(f"[ZERO] {rpc}: $0.00")
    except Exception as e:
        print(f"[ERR] {rpc}: {e}")

print(f"\nAddress: {address}")
