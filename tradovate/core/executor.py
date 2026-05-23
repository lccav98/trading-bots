"""
core/executor.py — Stub executor (sem playwright)
Modo sinais apenas - sem execução automática.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


class OrderExecutor:
    def __init__(self, auth, risk_manager):
        self.auth = auth
        self.risk = risk_manager
        logger.info("OrderExecutor: modo sinais (stub)")

    async def place_bracket_order(self, action, price, atr, score):
        return {"success": False, "reason": "Modo sinais - execução desativada"}

    async def cancel_all_orders(self):
        logger.info("Cancel orders: não implementado (modo sinais)")
        return {"success": False}

    async def close(self):
        logger.info("Executor closed")
