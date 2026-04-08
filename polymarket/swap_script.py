"""
POL -> USDC Swap Script
"""
import requests
from eth_account import Account
from web3 import Web3

PRIVATE_KEY = "0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28"
WALLET = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

RPC = "https://polygon-bor-rpc.publicnode.com"
w3 = Web3(Web3.HTTPProvider(RPC))
account = Account.from_key(PRIVATE_KEY)

USDC = "0x3c499c542cEF5D3814C2da34B12E0d0f8f0C9dC3"

print("=" * 50)
print("POL -> USDC Swap")
print("=" * 50)
print()

# Get balance
pol = w3.eth.get_balance(WALLET)
pol_eth = pol / 1e18
print(f"POL: {pol_eth:.4f}")
print()

if pol_eth < 1:
    print("Saldo muito baixo!")
    exit()

# Try 1Inch
amount = int(pol_eth * 0.95 * 1e18)
params = {
    "fromTokenAddress": "0x0000000000000000000000000000000000000000",
    "toTokenAddress": USDC,
    "amount": str(amount),
    "fromAddress": WALLET,
    "slippage": 3,
}

print("Buscando taxa...")
try:
    r = requests.get("https://api.1inch.io/v5.0/137/swap", params=params, timeout=15)
    data = r.json()
    
    if "tx" in data:
        tx = data["tx"]
        
        tx_dict = {
            "from": WALLET,
            "to": tx["to"],
            "data": tx["data"],
            "value": int(tx["value"], 16) if tx["value"] else amount,
            "gas": 300000,
            "gasPrice": w3.eth.gas_price,
            "nonce": w3.eth.get_transaction_count(WALLET),
            "chainId": 137,
        }
        
        print("Assinando...")
        signed = account.sign_transaction(tx_dict)
        
        print("Enviando...")
        h = w3.eth.send_raw_transaction(signed.raw_transaction)
        
        print()
        print("=" * 50)
        print(f"ENVIADO! Hash: {h.hex()}")
        print(f"Explorer: https://polygonscan.com/tx/{h.hex()}")
        print("=" * 50)
    else:
        print(f"Erro: {data}")
        
except Exception as e:
    print(f"Erro: {e}")
    print()
    print("Facam manualmente:")
    print("1. Va para https://quickswap.exchange")
    print("2. Conecte wallet")
    print("3. Swap POL -> USDC")