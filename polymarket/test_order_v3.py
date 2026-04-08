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
    "closed": "false", "limit": 10, "order": "volume24hr", "ascending": "false"
})
markets = resp.json()

for m in markets[:5]:
    question = m.get("question", "")[:60]
    token_ids_str = m.get("clobTokenIds", "[]")
    token_ids = json.loads(token_ids_str) if isinstance(token_ids_str, str) else token_ids_str
    
    if not token_ids:
        continue
    
    print(f"Trying: {question}")
    print(f"  TokenID: {token_ids[0][:50]}...")
    
    try:
        book = client.get_order_book(token_ids[0])
        print(f"  Book OK - neg_risk: {book.neg_risk}, tick: {book.tick_size}")
        
        if book.asks:
            best_ask = float(book.asks[0].price)
            print(f"  Best ask: {best_ask}")
            
            # Try placing order
            order = OrderArgs(token_id=token_ids[0], price=best_ask, size=0.01, side="BUY")
            result = client.create_and_post_order(order, PartialCreateOrderOptions(tick_size=book.tick_size, neg_risk=book.neg_risk))
            print(f"  SUCCESS! Result: {result}")
            break
    except Exception as e:
        print(f"  Error: {str(e)[:120]}")
    print()