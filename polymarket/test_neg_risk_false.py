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

# Try a neg_risk=False token (US forces enter Iran)
token_id = "29161841202062237498398496448777074703545543916456563250843923272709169522674"
book = client.get_order_book(token_id)
print(f"neg_risk: {book.neg_risk}, tick_size: {book.tick_size}")

if book.asks:
    print(f"Best ask: {book.asks[0].price}")
else:
    print("No asks")

# Try order
order = OrderArgs(token_id=token_id, price=0.50, size=0.01, side="BUY")
result = client.create_and_post_order(order, PartialCreateOrderOptions(tick_size=book.tick_size, neg_risk=book.neg_risk))
print(f"Order result: {result}")