import requests

address = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

usdc_polygon = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
rpc_polygon = "https://polygon-rpc.com"

payload = {
    "jsonrpc": "2.0",
    "method": "eth_call",
    "params": [{
        "to": usdc_polygon,
        "data": f"0x70a08231000000000000000000000000{address[2:].lower()}"
    }, "latest"],
    "id": 1
}

resp = requests.post(rpc_polygon, json=payload, timeout=10)
data = resp.json()
print(f"Raw result: {data.get('result', 'N/A')}")

if "result" in data and data["result"] != "0x" and data["result"] != "0x0":
    balance = int(data["result"], 16) / 1e6
    print(f"Polygon USDC Balance: ${balance:.2f}")
else:
    print("Polygon USDC Balance: $0.00")
    print("\nPossible reasons:")
    print("1. Deposit not confirmed yet (can take 10-30 min)")
    print("2. Wrong network selected on Binance (not Polygon)")
    print("3. Wrong address")
    print("4. Binance withdrawal still processing")
