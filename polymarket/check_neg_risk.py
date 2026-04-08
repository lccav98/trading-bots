from py_clob_client.client import ClobClient
import requests, json

key = "0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28"
client = ClobClient(
    host="https://clob.polymarket.com",
    key=key,
    chain_id=137,
    signature_type=1,
    funder="0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3",
)

resp = requests.get("https://gamma-api.polymarket.com/markets", params={
    "closed": "false", "limit": 20, "order": "volume24hr", "ascending": "false"
})
markets = resp.json()

for m in markets[:10]:
    token_ids = m.get("clobTokenIds", "[]")
    if isinstance(token_ids, str):
        token_ids = json.loads(token_ids)
    if len(token_ids) >= 1:
        question = m.get("question", "")[:70]
        print(f"Market: {question}")
        print(f"  Token: {token_ids[0][:40]}...")
        try:
            book = client.get_order_book(token_ids[0])
            print(f"  neg_risk: {book.neg_risk}, tick: {book.tick_size}")
        except Exception as e:
            print(f"  Error: {e}")
        print()