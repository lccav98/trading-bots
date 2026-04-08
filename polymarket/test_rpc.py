import requests

rpcs = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/pol",
    "https://api.polygon.technology/rpc"
]

for rpc in rpcs:
    try:
        r = requests.post(rpc, json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}, timeout=5)
        if r.status_code == 200:
            result = r.json().get("result", "N/A")
            print(f"WORKS: {rpc}")
            print(f"Block: {result}")
            break
    except Exception as e:
        print(f"FAIL: {rpc} - {str(e)[:40]}")