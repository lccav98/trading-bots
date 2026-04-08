"""
One Inch Swap - POL → USDC
Usa API pública para obter melhor taxa e executar swap
"""
import requests
import time
from eth_account import Account
from web3 import Web3

PRIVATE_KEY = "0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28"
WALLET = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

# 1Inch API
ONE_INCH_API = "https://api.1inch.io/v5.0/137/swap"

# Tokens
POL = "0x0000000000000000000000000000000000000000"
USDC = "0x3c499c542cEF5D3814C2da34B12E0d0f8f0C9dC3"

RPC = "https://rpc.ankr.com/polygon"

w3 = Web3(Web3.HTTPProvider(RPC))
account = Account.from_key(PRIVATE_KEY)

print("=== 1Inch POL -> USDC Swap ===")
print()

# 1. Get current balance
print("1. Verificando saldo...")
try:
    pol_bal = w3.eth.get_balance(WALLET)
    pol_eth = pol_bal / 1e18
    print(f"   POL: {pol_eth:.4f}")
except:
    pol_eth = 5.59 / 0.0917  # fallback
    print(f"   POL: ~{pol_eth:.2f} (estimado)")

if pol_eth < 0.5:
    print("   ❌ Saldo muito baixo")
    exit()

# 2. Get quote from 1inch
print()
print("2. Buscando melhor taxa...")
amount = int((pol_eth * 0.90) * 1e18)  # 90% to leave for gas

params = {
    "fromTokenAddress": POL,
    "toTokenAddress": USDC,
    "amount": str(amount),
    "fromAddress": WALLET,
    "slippage": 1,  # 1% slippage
}

try:
    r = requests.get(ONE_INCH_API, params=params, timeout=10)
    data = r.json()
    
    if "tx" in data:
        tx = data["tx"]
        to_token_amount = int(tx.get("value", "0")) / 1e6 if tx.get("value") else 0
        print(f"   Receberia: ~{to_token_amount:.2f} USDC")
        print()
        
        print("3. Preparando transação...")
        print()
        
        # Build transaction
        tx_dict = {
            "from": tx["from"],
            "to": tx["to"],
            "data": tx["data"],
            "value": int(tx["value"], 16) if tx["value"].startswith("0x") else int(tx["value"]),
            "gas": int(tx.get("gas", 200000)),
            "gasPrice": int(tx.get("gasPrice", w3.eth.gas_price)),
            "nonce": w3.eth.get_transaction_count(WALLET),
            "chainId": 137,
        }
        
        print(f"   Gas estimado: {tx_dict['gas']}")
        print(f"   Gas price: {tx_dict['gasPrice'] / 1e9:.2f} Gwei")
        print()
        
        # Sign
        signed = account.sign_transaction(tx_dict)
        
        # Send
        print("4. Enviando transação...")
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"   Transaction Hash: {tx_hash.hex()}")
        print()
        print("✅ Transação enviada! Confirme na blockchain...")
        
    else:
        print(f"   Erro: {data}")
        
except Exception as e:
    print(f"   Erro na API: {e}")
    print()
    print("Alternative: Faça manualmente em:")
    print("   https://quickswap.exchange")
    print("   ou")
    print("   https://app.1inch.io/")