#!/usr/bin/env python3
"""
Lista trades recentes e tenta fechar posicoes
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType


def main():
    print("=== LISTAR TRADES RECENTES ===\n")

    client = ClobClient(
        host="https://clob.polymarket.com",
        key=os.environ.get("POLYMARKET_PRIVATE_KEY"),
        chain_id=137,
        signature_type=1,
        funder=os.environ.get("FUNDER_ADDRESS"),
    )

    # Get recent trades
    try:
        resp = requests.get("https://clob.polymarket.com/data/trades", timeout=15)
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            trades = resp.json()
            print(f"Trades: {len(trades)}")

            for t in trades[:10]:
                print(f"  {t}")
    except Exception as e:
        print(f"Erro: {e}")


if __name__ == "__main__":
    main()
