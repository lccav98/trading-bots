from eth_account import Account

key = "0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28"
acct = Account.from_key(key)
print(f"EOA Address from private key: {acct.address}")
