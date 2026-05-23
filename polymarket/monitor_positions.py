#!/usr/bin/env python3
"""
Monitor de posições Polymarket - verifica P&L a cada minuto
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

load_dotenv()

from py_clob_client.client import ClobClient


def get_positions_legacy(client):
    """Busca posições via API antiga"""
    url = "https://clob.polymarket.com/positions"
    try:
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {client._auth_token}"}, timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return []


def check_account():
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=os.environ.get("POLYMARKET_PRIVATE_KEY"),
        chain_id=137,
        signature_type=1,
        funder=os.environ.get("FUNDER_ADDRESS"),
    )

    # Get trades recentes
    try:
        trades = client.get_trades(limit=20)
        print(f"\n=== ÚLTIMOS 5 TRADES ===")
        total_pnl = 0
        for t in trades[:5]:
            side = t.get("side", "UNKNOWN")
            size = float(t.get("size", 0))
            price = float(t.get("price", 0))
            fee = float(t.get("fee", 0)) / 1e6
            pnl = size * price * 100 if side == "SELL" else 0  # Simplificado
            total_pnl += pnl
            print(f"  {side} {size} @ {price:.2f} | Fee: ${fee:.2f}")

        print(f"\n  Trades hoje: {len(trades)}")
        return True
    except Exception as e:
        print(f"Erro: {e}")
        return False


if __name__ == "__main__":
    check_account()
