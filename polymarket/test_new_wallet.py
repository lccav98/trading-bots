from py_clob_client.client import ClobClient
import requests, json

# New wallet
new_key = "b32b7cb2f17dd14f5decac299426610ece408f517fa2f4e46a7e906bc13ffbf4"
new_addr = "0x115e44374d0154caF4d7f0d86F9F89cC2a148Fca"

client = ClobClient(
    host="https://clob.polymarket.com",
    key=new_key,
    chain_id=137,
    signature_type=1,
    funder=new_addr,
)

# Create API key
creds = client.create_or_derive_api_creds()
print(f"API Key created: {creds.api_key}")
client.set_api_creds(creds)

# Get first market
resp = requests.get("https://gamma-api.polymarket.com/markets", params={
    "closed": "false", "limit": 3, "order": "volume24hr", "ascending": "false"
})
markets = resp.json()

for m in markets:
    token_ids_str = m.get("clobTokenIds", "[]")
    token_ids = json.loads(token_ids_str) if isinstance(token_ids_str, str) else token_ids_str
    
    if not token_ids:
        continue
    
    question = m.get("question", "")[:60]
    print(f"\nTrying: {question}")
    
    try:
        from py_clob_client.clob_types import OrderArgs, PartialCreateOrderOptions
        
        book = client.get_order_book(token_ids[0])
        print(f"  Book OK - neg_risk: {book.neg_risk}")
        
        if book.asks:
            best_ask = float(book.asks[0].price)
            order = OrderArgs(token_id=token_ids[0], price=best_ask, size=0.01, side="BUY")
            result = client.create_and_post_order(order, PartialCreateOrderOptions(tick_size=book.tick_size, neg_risk=book.neg_risk))
            print(f"  SUCCESS! Result: {result}")
            break
    except Exception as e:
        print(f"  Error: {str(e)[:100]}")