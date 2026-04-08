from py_clob_client.client import ClobClient

client = ClobClient(
    host="https://clob.polymarket.com",
    key="0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28",
    chain_id=137,
    signature_type=1,
    funder="0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3",
)
client.set_api_creds(client.create_or_derive_api_creds())

book = client.get_order_book("78633590736077251574794513664747155551297291244492840448622550955320930591622")
print(f"Type: {type(book)}")
print(f"Attrs: {[x for x in dir(book) if not x.startswith('_')]}")
print(f"Book: {book}")
