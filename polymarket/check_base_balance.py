import requests

address = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"
usdc_base = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
rpc = "https://mainnet.base.org"

payload = {
    "jsonrpc": "2.0",
    "method": "eth_call",
    "params": [{
        "to": usdc_base,
        "data": f"0x70a08231000000000000000000000000{address[2:].lower()}"
    }, "latest"],
    "id": 1
}

resp = requests.post(rpc, json=payload, timeout=10)
data = resp.json()
if "result" in data and data["result"] != "0x":
    balance = int(data["result"], 16) / 1e6
    print(f"Base USDC Balance: ${balance:.2f}")
else:
    print("Base USDC Balance: $0.00 or error")
    print(f"Response: {data}")
