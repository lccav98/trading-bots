"""
core/simulator.py — Simula trades virtuais para testar a estrategia
Sem risco, sem ordens reais. Acompanha preco e aplica SL/TP virtuais.
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class TradeSimulator:
    """Simula trades virtuis: entrada via sinal, saida por SL/TP/reversal."""

    def __init__(self, initial_balance=50000.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.position = None  # {"action", "entry", "sl", "tp", "contracts", "entry_time"}
        self.trades_closed = 0
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0
        self.journal = []
        self._open_time = None

        # Carrega journal existente
        self._load_journal()

    def enter_trade(self, action, entry_price, sl, tp, contracts, reason=""):
        """Entrada virtual em trade."""
        if self.position:
            return None

        self.position = {
            "action": action,
            "entry": entry_price,
            "sl": sl,
            "tp": tp,
            "contracts": contracts,
            "reason": reason,
            "entry_time": datetime.now().strftime("%H:%M:%S"),
        }
        self._open_time = datetime.now()

        ts = datetime.now().strftime("%H:%M:%S")
        dir_str = "COMPRA" if action == "BUY" else "VENDA"
        logger.info(
            f"🎮 SIM [{ts}] ENTRY VIRTUAL: {dir_str} @ {entry_price} "
            f"| SL:{sl} TP:{tp} | Contracts:{contracts}"
        )
        return {"success": True, "data": self.position}

    def check_exit(self, current_price):
        """Checa se SL/TP foi atingido ou se posicao deve ser fechada."""
        if not self.position:
            return None

        p = self.position
        hit = None

        if p["action"] == "BUY":
            if current_price <= p["sl"]:
                hit = "STOP LOSS"
                pnl = (p["sl"] - p["entry"]) * p["contracts"]
            elif current_price >= p["tp"]:
                hit = "TAKE PROFIT"
                pnl = (p["tp"] - p["entry"]) * p["contracts"]
        elif p["action"] == "SELL":
            if current_price >= p["sl"]:
                hit = "STOP LOSS"
                pnl = (p["entry"] - p["sl"]) * p["contracts"]
            elif current_price <= p["tp"]:
                hit = "TAKE PROFIT"
                pnl = (p["entry"] - p["tp"]) * p["contracts"]

        if hit:
            self._close_trade(pnl, hit, current_price)
            return {"hit": hit, "pnl": pnl}

        return None

    def check_reversal_exit(self, opposite_action):
        """Fecha se sinal inverter (opposite = BUY ou SELL)."""
        if not self.position:
            return None

        p = self.position
        # Approximate price for reversal exit
        # Calculate PnL at current entry (approximate — price would be checked externally)
        if p["action"] != opposite_action:
            return None

        # Reversal: close at current market (use midpoint between SL/TP as rough estimate)
        close_price = (p["sl"] + p["tp"]) / 2

        if p["action"] == "BUY":
            pnl = (close_price - p["entry"]) * p["contracts"]
        else:
            pnl = (p["entry"] - close_price) * p["contracts"]

        hit = "REVERSAO SINAL"
        self._close_trade(pnl, hit, close_price)
        return {"hit": hit, "pnl": pnl}

    def _close_trade(self, pnl, reason, close_price):
        self.total_pnl += pnl
        self.balance += pnl
        self.trades_closed += 1

        is_win = pnl > 0
        if is_win:
            self.wins += 1
        else:
            self.losses += 1

        entry_time = self.position.get("entry_time", "?")
        exit_time = datetime.now().strftime("%H:%M:%S")
        action = self.position["action"]

        logger.info(
            f"🎮 SIM [{exit_time}] EXIT: {action} | "
            f"Entrada:{self.position['entry']} → Saida:{close_price:.2f} | "
            f"Motivo:{reason} | PnL: ${pnl:.2f}"
        )
        logger.info(
            f"📊 TOTAL: P&L=${self.total_pnl:.2f} | "
            f"Balance=${self.balance:.2f} | "
            f"Trades:{self.trades_closed} | W:{self.wins} L:{self.losses} | "
            f"WR:{(self.wins/self.trades_closed*100) if self.trades_closed else 0:.0f}%"
        )

        # Salva no journal
        trade = {
            "entry_time": entry_time,
            "exit_time": exit_time,
            "action": action,
            "entry": self.position["entry"],
            "exit": close_price,
            "sl": self.position["sl"],
            "tp": self.position["tp"],
            "contracts": self.position["contracts"],
            "pnl": round(pnl, 2),
            "reason": reason,
            "balance": round(self.balance, 2),
        }
        self.journal.append(trade)
        self._save_journal()

        # Risk check
        if self.losses >= 2 or self.total_pnl < -800:
            logger.warning(
                f"🛑 SIM TRAVAMENTO: max losses ou perda diaria atingida! "
                f"P&L: ${self.total_pnl:.2f}"
            )

        self.position = None

    def _load_journal(self):
        path = "data/simulation_journal.json"
        if os.path.exists(path):
            try:
                self.journal = json.load(open(path))
                # Recalculate state from journal
                for t in self.journal:
                    pnl = t.get("pnl", 0)
                    self.total_pnl += pnl
                    self.balance += pnl
                    if pnl > 0:
                        self.wins += 1
                    else:
                        self.losses += 1
                    self.trades_closed += 1
            except Exception:
                self.journal = []

    def _save_journal(self):
        path = "data/simulation_journal.json"
        os.makedirs("data", exist_ok=True)
        json.dump(self.journal, open(path, "w"), indent=2, ensure_ascii=False)

    def is_trading_blocked(self):
        """Checa se sim travou por max losses ou max daily loss."""
        if self.losses >= 2:
            return True
        if self.total_pnl <= -800:
            return True
        return False

    def status(self):
        """Retorna status atual como dict."""
        wr = (self.wins / self.trades_closed * 100) if self.trades_closed else 0
        return {
            "balance": round(self.balance, 2),
            "total_pnl": round(self.total_pnl, 2),
            "trades": self.trades_closed,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(wr, 1),
            "position": "OPEN" if self.position else "FLAT",
            "position_details": self.position,
        }
