from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, PartialCreateOrderOptions

for sig_type in [0, 1, 2]:
    print(f"\n=== Testing signature_type={sig_type} ===")
    try:
        client = ClobClient(
            host="https://clob.polymarket.com",
            key="0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28",
            chain_id=137,
            signature_type=sig_type,
            funder="0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3",
        )
        client.set_api_creds(client.create_or_derive_api_creds())

        order_args = OrderArgs(
            token_id="78633590736077251574794513664747155551297291244492840448622550955320930591622",
            price=0.01,
            size=100,
            side="BUY",
        )

        options = PartialCreateOrderOptions(tick_size="0.001", neg_risk=True)
        signed_order = client.create_order(order_args, options)
        
        print(f"Order signer: {signed_order.dict()['signer']}")
        print(f"Order maker: {signed_order.dict()['maker']}")
        print(f"Signature type: {signed_order.dict()['signatureType']}")

        result = client.post_order(signed_order)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
