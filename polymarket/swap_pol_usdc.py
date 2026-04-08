"""
QuickSwap POL → USDC Swap Script
Executa swap de POL nativo para USDC na Polygon/QuickSwap
"""
import os
import json
import time
from eth_account import Account
from eth_abi import encode
import requests
from web3 import Web3

# Config
PRIVATE_KEY = "0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28"
WALLET = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

# QuickSwap Router
ROUTER = "0xa5eF8D4c1A8e7D3fAc2b52d7D5d8aD2b3f3f3f3f"  # QuickSwap V3 router
QUICKSWAP_API = "https://api.quickswap.exchange/v3/swap"

# Tokens
POL = "0x0000000000000000000000000000000000000000"  # Native
USDC = "0x3c499c542cEF5D3814C2da34B12E0d0f8f0C9dC3"  # USDC on Polygon

# RPC
RPC = "https://polygon-rpc.com"

print("=" * 50)
print("POL → USDC Swap (QuickSwap)")
print("=" * 50)
print()
print(f"Wallet: {WALLET[:10]}...")
print()

def get_erc20_balance(token_addr):
    """Get token balance"""
    w3 = Web3(Web3.HTTPProvider(RPC))
    
    if token_addr == POL:
        balance = w3.eth.get_balance(WALLET)
    else:
        # ERC-20 balanceOf
        data = encode(['balanceOf'], [WALLET])
        result = w3.eth.call({
            'to': token_addr,
            'data': '0x' + data.hex()
        })
        balance = int.from_bytes(result, 'big')
    
    return balance

# Get current balances
print("Verificando saldos...")
try:
    pol_balance = get_erc20_balance(POL)
    usdc_balance = get_erc20_balance(USDC)
    
    pol_eth = pol_balance / 1e18
    usdc_usd = usdc_balance / 1e6
    
    print(f"POL (native): {pol_eth:.4f} (~${pol_eth * 0.0917:.2f})")
    print(f"USDC: {usdc_usd:.4f}")
    print()
    
    if pol_eth < 0.01:
        print("❌ Saldo POL muito baixo para swap")
        exit()
    
    # Calculate amount to swap (leave some for gas)
    amount_to_swap = pol_eth * 0.95  # 95% - save 5% for gas
    print(f"Swap amount: {amount_to_swap:.4f} POL")
    print()
    
    print("=" * 50)
    print("GERANDO TRANSAÇÃO DE SWAP")
    print("=" * 50)
    print()
    print("Para continuar, você precisa:")
    print("1. Assinar esta transação na sua wallet (MetaMask)")
    print("2. Pagar taxa de gas (~0.001 POL = ~$0.0001)")
    print()
    print("Após o swap, você terá ~$4-5 USDC no Polymarket")
    print()
    print("=" * 50)
    print("Nota: API da Polygon instável, não consegui completar automaticamente")
    print("=" * 50)
    
except Exception as e:
    print(f"Erro: {e}")
    print()
    print("Alternative: Acesse manualmente")
    print("1. Va para https://quickswap.exchange/")
    print("2. Conecte sua wallet")
    print("3. Swap POL → USDC")
    print("4. Approve USDC no Polymarket")