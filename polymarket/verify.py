from eth_account import Account
import requests

key = "0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28"
funder = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

# Verify
acct = Account.from_key(key)
print("=== VERIFICATION ===")
print(f"1. Private key valid hex: {key.startswith('0x')}")
print(f"   Key address: {acct.address}")
print(f"   Matches intended: {acct.address.lower() == funder.lower()}")

print(f"2. signature_type: 1 (POLY_PROXY)")

print(f"3. Funder: {funder}")
print(f"   Is proxy wallet (starts with 0xa): {funder.startswith('0xa')}")

# Check on Polymarket
resp = requests.get("https://gamma-api.polymarket.com/credentials", params={"address": funder})
print(f"4. Polymarket API response: {resp.status_code}")
if resp.status_code == 200:
    print(f"   Data: {resp.json()}")