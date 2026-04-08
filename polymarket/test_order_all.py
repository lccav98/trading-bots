import requests, json
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, PartialCreateOrderOptions

key = "0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28"
client = ClobClient(
    host="https://clob.polymarket.com",
    key=key,
    chain_id=137,
    signature_type=1,
    funder="0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3",
)

creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)

# Get markets via gamma
resp = requests.get("https://gamma-api.polymarket.com/markets", params={
    "closed": "false", "limit": 20, "order": "volume24hr", "ascending": "false"
})
markets = resp.json()

# Try first few until we find one that works
for m in markets[:5]:
    condition_id = m.get("conditionId")
    question = m.get("question", "")[:60]
    
    # Get from CLOB
    resp2 = requests.get("https://clob.polymarket.com/markets", params={"conditionID": condition_id})
    data = resp2.json().get("data", [])
    
    if not data:
        continue
    
    token_id = data[0].get("token_id", "")
    print(f"Trying: {question}")
    print(f"  TokenID: {token_id}")
    
    try:
        book = client.get_order_book(token_id)
        print(f"  Book OK - neg_risk: {book.neg_risk}, tick: {book.tick_size}")
        
        if book.asks:
            best_ask = float(book.asks[0].price)
            print(f"  Best ask: {best_ask}")
            
            # Try placing order
            order = OrderArgs(token_id=token_id, price=best_ask, size=0.01, side="BUY")
            result = client.create_and_post_order(order, PartialCreateOrderOptions(tick_size=book.tick_size, neg_risk=book.neg_risk))
            print(f"  SUCCESS! Result: {result}")
            break
    except Exception as e:
        print(f"  Error: {e}")
    print()