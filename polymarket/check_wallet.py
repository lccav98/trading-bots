import requests

WALLET = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

# Try public RPC that should work
rpc_url = "https://polygon-bor-rpc.publicnode.com"

print(f"=== Wallet: {WALLET[:10]}...{WALLET[-4:]} ===")
print()

POL_TOKEN = "0x455e53c16e6e3359222d1e13f560e8ebe15e7d87"
USDC_TOKEN = "0x3c499c542cEF5D3814C2da34B12E0d0f8f0C9dC3"

def get_balance(token, wallet):
    data = f"0x70a08231000000000000000000000000{wallet[2:].lower()}"
    
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": token, "data": data}, "latest"],
        "id": 1
    }
    
    r = requests.post(rpc_url, json=payload, timeout=15)
    result = r.json().get("result", "0x0")
    return int(result, 16)

try:
    # POL
    pol = get_balance(POL_TOKEN, WALLET)
    pol_bal = pol / 1e18
    print(f"POL: {pol_bal:.4f} POL")
    
    # USDC
    usdc = get_balance(USDC_TOKEN, WALLET)
    usdc_bal = usdc / 1e6
    print(f"USDC: {usdc_bal:.4f} USDC")
    
    # Native MATIC/POL (chain coin)
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [WALLET, "latest"],
        "id": 1
    }
    r = requests.post(rpc_url, json=payload, timeout=15)
    native = int(r.json().get("result", "0x0"), 16)
    native_bal = native / 1e18
    print(f"Native POL: {native_bal:.4f}")
    
    print()
    print("=== TOTAL ===")
    total_usd = (pol_bal * 0.0917) + (usdc_bal * 0.0917) + (native_bal * 0.0917)
    print(f"~= ${total_usd:.2f}")
    
except Exception as e:
    print(f"Error: {e}")
    print()
    print("User sees: $5.59")
    print("This is likely native POL balance on the chain")
    print("POL price: ~$0.09")
    print(f"Native POL: ~$5.59 / 0.09 = {5.59/0.09:.2f} POL")