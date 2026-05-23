#!/usr/bin/env python3
"""
Fecha posicoes conhecidas (Ducks vs Predators, Blues vs Utah)
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType


def find_market_by_question(question_substr):
    """Busca mercado pelo nome"""
    url = "https://gamma-api.polymarket.com/markets"
    params = {"closed": "false", "limit": 50}

    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code != 200:
        return None

    markets = resp.json()
    for m in markets:
        q = m.get("question", "")
        if question_substr.lower() in q.lower():
            token_id = m.get("tokenId", "")
            return token_id
    return None


def main():
    print("=== FECHAR POSICOES POLYMARKET ===\n")

    # Credentials
    key = os.environ.get("POLYMARKET_PRIVATE_KEY")
    funder = os.environ.get("FUNDER_ADDRESS")

    client = ClobClient(
        host="https://clob.polymarket.com",
        key=key,
        chain_id=137,
        signature_type=1,
        funder=funder,
    )

    markets_to_close = [
        "Ducks vs",
        "Blues vs",
    ]

    for market_name in markets_to_close:
        token_id = find_market_by_question(market_name)
        if not token_id:
            print(f"Nao encontrei: {market_name}")
            continue

        print(f"\n{market_name}: {token_id[:30]}...")

        try:
            book = client.get_order_book(token_id=token_id)

            # Seller logic (fechar posicao BUY = SELL)
            if not book.bids:
                print(f"  Sem bids!")
                continue

            price = float(book.bids[0].price) - 0.01
            if price <= 0:
                continue

            # Tamanho baseado no saldo
            size = 1.0

            print(f"  -> SELL: {size} @ {price}")

            order_args = OrderArgs(
                token_id=token_id, price=round(price, 2), size=size, side="SELL"
            )

            signed = client.create_order(order_args)
            response = client.post_order(signed, OrderType.GTC)

            order_id = response.get("orderID") if isinstance(response, dict) else None
            if order_id:
                print(f"  OK! Order: {order_id}")
            else:
                print(f"  Erro: {response}")

        except Exception as e:
            print(f"  Erro: {e}")


if __name__ == "__main__":
    main()
