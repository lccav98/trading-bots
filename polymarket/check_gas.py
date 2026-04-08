import requests

# Get POL price from CoinGecko
try:
    r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=polygon-ecosystem-token&vs_currencies=usd", timeout=10)
    pol_price = r.json()["polygon-ecosystem-token"]["usd"]
except:
    pol_price = 0.035

# Try main Polygon RPC
try:
    r = requests.post("https://polygon-rpc.com", json={
        "jsonrpc": "2.0",
        "method": "eth_gasPrice",
        " params": []
    }, timeout=10, headers={"Content-Type": "application/json"})
    
    if r.status_code == 200:
        result = r.json().get("result", "0x0")
        gas_wei = int(result, 16)
        gas_gwei = gas_wei / 1e9
        
        print("=== Polygon (POL) Network ===")
        print(f"POL Price: ${pol_price:.4f}")
        print()
        print(f"Gas Price: {gas_gwei:.2f} Gwei")
        print()
        print(f"Estimated Costs:")
        print(f"  Transfer (21k gas):  ${gas_gwei * pol_price * 21000 / 1e9:.4f}")
        print(f"  Swap (65k gas):      ${gas_gwei * pol_price * 65000 / 1e9:.4f}")
        print(f"  Swap (100k gas):     ${gas_gwei * pol_price * 100000 / 1e9:.4f}")
except Exception as e:
    print(f"Error: {e}")