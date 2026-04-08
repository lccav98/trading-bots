"""
Direct Swap via public API
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
QUICKSWAP = "0xa5eF8D4c1A8e7D3fAc2b52d7D5d8aD2b3f3f3f3f"

print("=" * 50)
print("POL -> USDC Direct Swap")
print("=" * 50)
print()

# Get balance
pol = w3.eth.get_balance(WALLET)
pol_eth = pol / 1e18
print(f"POL: {pol_eth:.4f}")

if pol_eth < 1:
    print("Saldo muito baixo!")
    exit()

# Amount to swap (95%)
amount = int(pol_eth * 0.95 * 1e18)
print(f"Swap: {amount / 1e18:.4f} POL")
print()

# Try other aggregators
apis = [
    ("https://api.1inch.io/v5.0/137/swap", {"fromTokenAddress": "0x0000000000000000000000000000000000000000", "toTokenAddress": USDC, "amount": str(amount), "fromAddress": WALLET, "slippage": 5}),
]

for api_url, params in apis:
    try:
        print(f"Tentando: {api_url.split('/api')[0]}...")
        r = requests.get(api_url, params=params, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            if "tx" in data:
                tx = data["tx"]
                print("OK! Encontrou rota!")
                
                # Build tx
                tx_dict = {
                    "from": WALLET,
                    "to": tx["to"],
                    "data": tx["data"],
                    "value": int(tx["value"], 16) if tx.get("value") and tx["value"].startswith("0x") else int(tx.get("value", amount)),
                    "gas": 350000,
                    "gasPrice": w3.eth.gas_price,
                    "nonce": w3.eth.get_transaction_count(WALLET),
                    "chainId": 137,
                }
                
                # Sign and send
                print("Assinando...")
                signed = account.sign_transaction(tx_dict)
                print("Enviando...")
                h = w3.eth.send_raw_transaction(signed.raw_transaction)
                
                print()
                print(f"SUCESSO! Hash: {h.hex()}")
                print(f"https://polygonscan.com/tx/{h.hex()}")
                exit()
                
    except Exception as e:
        print(f"Erro: {str(e)[:60]}")

print()
print("APIs indisponiveis.")
print()
print("PASSOS MANUAL:")
print("1. Va em https://quickswap.exchange")
print("2. Conecte sua MetaMask")
print("3. Selecione POL -> USDC")
print("4. Amount: 19.5 POL (deixe 1 POL para gas)")
print("5. Approve e confirme")
print()
print("Com 20 POL voce tera aproximadamente:")
print(f"  ~${20 * 0.0917 * 0.995:.2f} USDC")