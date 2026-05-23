#!/usr/bin/env python3
import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.exceptions import PolyException


def main():
    print("=== FECHAR POSICOES POLYMARKET ===")

    client = ClobClient(
        host="https://clob.polymarket.com",
        key=os.environ.get("POLYMARKET_PRIVATE_KEY"),
        chain_id=137,
        signature_type=1,
        funder=os.environ.get("FUNDER_ADDRESS"),
    )

    print("Buscando posicoes abertas...")
    positions = []

    endpoints = [
        "https://clob.polymarket.com/positions",
        "https://clob.polymarket.com/api/v1/positions",
    ]

    for url in endpoints:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                positions = resp.json()
                if positions:
                    print(f"Sucesso: {url}")
                    break
        except Exception as e:
            print(f"Erro: {e}")

    if not positions:
        print("Nenhuma posicao!")
        return

    print(f"Encontradas: {len(positions)}\n")

    for pos in positions:
        token_id = pos.get("token_id", "")
        size = float(pos.get("size", 0))
        side = pos.get("side", "UNKNOWN")
        if size <= 0:
            continue

        print(f"Token: {token_id[:30]}")
        print(f"  Tipo: {side} | Tamanho: {size}")

        try:
            book = client.get_order_book(token_id=token_id)
            price = 0

            if side == "BUY":
                if book.asks:
                    price = float(book.asks[0].price) + 0.01
            else:
                if book.bids:
                    price = float(book.bids[0].price) - 0.01

            if price <= 0 or price >= 1:
                print(f"  Preco invalido")
                continue

            reverse_side = "SELL" if side == "BUY" else "BUY"
            print(f"  -> {reverse_side}: {size} @ {price}")

            order_args = OrderArgs(
                token_id=token_id, price=round(price, 2), size=size, side=reverse_side
            )

            signed = client.create_order(order_args)
            response = client.post_order(signed, OrderType.GTC)
            order_id = response.get("orderID") if isinstance(response, dict) else None

            if order_id:
                print(f"  OK! ID: {order_id}")
            else:
                print(f"  Erro: {response}")

        except Exception as e:
            print(f"  Erro: {e}")

        time.sleep(1)

    print("\nVerificando saldo...")
    try:
        resp = requests.get(
            "https://clob.polymarket.com/balance-allowance",
            params={"asset_type": "COLLATERAL"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"Saldo: ${float(data.get('balance', 0)) / 1e6:.2f}")
    except:
        pass


if __name__ == "__main__":
    main()
