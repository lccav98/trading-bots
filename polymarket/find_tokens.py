from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
import requests
import json

key = "0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28"
address = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"

client = ClobClient(
    host="https://clob.polymarket.com",
    key=key,
    chain_id=137,
    signature_type=1,
    funder=address,
)
client.set_api_creds(client.create_or_derive_api_creds())

# Find markets
markets_to_find = [
    "Will Bitcoin dip to $50,000 in April?",
    "Will the price of Bitcoin be above $60,000 on April 7?"
]

for market_name in markets_to_find:
    print(f"\nSearching: {market_name}")
    
    # Search markets
    resp = requests.get(
        "https://clob.polymarket.com/markets",
        params={"question__contains": market_name[:30]},
        timeout=10
    )
    
    if resp.status_code == 200:
        data = resp.json()
        markets = data.get("data", [])
        for m in markets:
            if market_name.lower() in m.get("question", "").lower():
                print(f"  Found: {m.get('question')[:50]}...")
                print(f"  Condition ID: {m.get('conditionId')}")
                print(f"  Active: {m.get('active')}")
                
                # Get order book to find token IDs
                try:
                    cond_id = m.get("conditionId")
                    book_resp = requests.get(
                        f"https://clob.polymarket.com/markets/{cond_id}",
                        timeout=10
                    )
                    if book_resp.status_code == 200:
                        market_data = book_resp.json()
                        print(f"  Markets in condition: {json.dumps(market_data, indent=2)[:500]}")
                except Exception as e:
                    print(f"  Error getting order book: {e}")