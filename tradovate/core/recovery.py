"""
core/recovery.py -- Crash Recovery & State Persistence

Handles:
  - State persistence to data/recovery_state.json
  - Crash detection on startup (date-matching restore)
  - Stale position reconciliation against broker
  - Graceful shutdown (SIGINT/SIGTERM) with state save + optional flatten
"""

import json
import logging
import os
import signal
from datetime import datetime, date

from config.settings import SYMBOL

logger = logging.getLogger(__name__)

RECOVERY_STATE_FILE = os.path.join("data", "recovery_state.json")


class RecoveryState:
    """Persist and restore bot state across restarts/crashes."""

    def __init__(self, risk_manager, executor):
        """
        Args:
            risk_manager: RiskManager instance (core.risk)
            executor: OrderExecutor instance (core.executor)
        """
        self.risk = risk_manager
        self.executor = executor
        self.last_saved_at = None

    # ------------------------------------------------------------------
    # State snapshot
    # ------------------------------------------------------------------

    def _build_state(self) -> dict:
        """Snapshot of everything needed to restore a session."""
        return {
            "session_date": date.today().isoformat(),
            "saved_at": datetime.now().isoformat(),
            "daily_pnl": self.risk.daily_pnl,
            "peak_pnl": self.risk.peak_pnl,
            "daily_high_water": self.risk.daily_high_water,
            "wins": self.risk.wins,
            "losses": self.risk.losses,
            "consec_losses": self.risk.consec_losses,
            "trade_count": self.risk.trade_count,
            "blocked": self.risk.blocked,
            "block_reason": self.risk.block_reason,
            "open_position": self.risk.open_position,
            "entry_price": self.risk.entry_price,
            "trailing_active": self.risk.trailing_active,
            "trailing_stop": self.risk.trailing_stop,
            "breakeven": getattr(self.risk, "_breakeven", False),
            "account_balance": self.risk.account_balance,
        }

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save(self):
        """Persist current state to disk."""
        state = self._build_state()
        try:
            os.makedirs(os.path.dirname(RECOVERY_STATE_FILE), exist_ok=True)
            with open(RECOVERY_STATE_FILE, "w") as f:
                json.dump(state, f, indent=2, default=str)
            self.last_saved_at = state["saved_at"]
            logger.info(f"Recovery state saved at {state['saved_at']}")
        except Exception as e:
            logger.error(f"Failed to save recovery state: {e}")

    def load(self) -> dict | None:
        """Load persisted state from disk. Returns None if file missing."""
        if not os.path.exists(RECOVERY_STATE_FILE):
            logger.info("No recovery state file found -- fresh start")
            return None
        try:
            with open(RECOVERY_STATE_FILE, "r") as f:
                state = json.load(f)
            logger.info(f"Recovery state loaded from {state.get('saved_at', 'unknown')}")
            return state
        except Exception as e:
            logger.error(f"Failed to load recovery state: {e}")
            return None

    # ------------------------------------------------------------------
    # Restore into RiskManager
    # ------------------------------------------------------------------

    def _restore_state(self, state: dict):
        """Apply a loaded state dict onto the RiskManager."""
        self.risk.daily_pnl = state.get("daily_pnl", 0.0)
        self.risk.peak_pnl = state.get("peak_pnl", 0.0)
        self.risk.daily_high_water = state.get("daily_high_water", 0.0)
        self.risk.wins = state.get("wins", 0)
        self.risk.losses = state.get("losses", 0)
        self.risk.consec_losses = state.get("consec_losses", 0)
        self.risk.trade_count = state.get("trade_count", 0)
        self.risk.blocked = state.get("blocked", False)
        self.risk.block_reason = state.get("block_reason", "")
        self.risk.open_position = state.get("open_position")
        self.risk.entry_price = state.get("entry_price", 0.0)
        self.risk.trailing_active = state.get("trailing_active", False)
        self.risk.trailing_stop = state.get("trailing_stop", 0.0)
        self.risk._breakeven = state.get("breakeven", False)
        self.risk.account_balance = state.get("account_balance", self.risk.account_balance)

    # ------------------------------------------------------------------
    # Startup -- crash detection + reconciliation
    # ------------------------------------------------------------------

    def recover_on_startup(self) -> tuple:
        """
        Called once at bot start.

        Returns:
            (bool, str): (restored, reason)
            True if state was restored from a previous session,
            False otherwise (fresh start or stale/old file cleaned up).
        """
        state = self.load()
        if state is None:
            return False, "No recovery state file found"

        saved_date = state.get("session_date")
        today = date.today().isoformat()

        if saved_date != today:
            logger.info(
                f"Recovery state is from {saved_date} (today is {today}) "
                "-- discarding stale state, fresh start"
            )
            return False, f"Stale state from {saved_date} — fresh start"

        logger.info(
            f"Crash detected -- restoring state from {state['saved_at']} "
            f"(date matches today)"
        )
        self._restore_state(state)
        logger.info(
            f"State restored | P&L: ${self.risk.daily_pnl:.2f} | "
            f"Trades: {self.risk.trade_count} | "
            f"W/L: {self.risk.wins}/{self.risk.losses} | "
            f"Open: {self.risk.open_position or 'Flat'}"
        )

        # Reconcile position against broker
        self._reconcile_positions(state)

        return True, f"Restored session from {state['saved_at']}"

    def _reconcile_positions(self, saved_state: dict):
        """
        Compare saved bot position against actual broker positions.

        Cases:
          1. Bot thinks position is open but broker has none -> clear stale state.
          2. Bot has no position but broker has one -> sync (best effort).
        """
        saved_position = saved_state.get("open_position")
        has_saved_position = saved_position is not None

        try:
            broker_positions = self.executor.get_positions()
        except Exception as e:
            logger.error(f"Could not fetch broker positions for reconciliation: {e}")
            return

        # Parse broker positions for the configured symbol
        has_broker_position = False
        broker_direction = None
        broker_qty = 0
        positions = broker_positions if isinstance(broker_positions, list) else []
        for pos in positions:
            if pos.get("symbol") != SYMBOL:
                continue
            # Check net position value
            net_qty = pos.get("netPos", pos.get("netPosition", 0))
            if net_qty != 0:
                has_broker_position = True
                broker_direction = "BUY" if net_qty > 0 else "SELL"
                broker_qty = abs(net_qty)
                break

        # Case 1: bot thought it had a position, but broker does not
        if has_saved_position and not has_broker_position:
            logger.warning(
                f"STALE POSITION DETECTED -- bot recorded {saved_position} "
                f"but broker reports flat position. Clearing stale state."
            )
            self.risk.open_position = None
            self.risk.entry_price = 0.0
            self.risk.trailing_active = False
            self.risk.trailing_stop = 0.0
            self.risk._breakeven = False
            self.save()

        # Case 2: broker has a position but bot does not
        elif has_broker_position and not has_saved_position:
            logger.warning(
                f"UNRECORDED BROKER POSITION -- {broker_direction} "
                f"{broker_qty} contract(s) found on broker but not in bot state. "
                f"Syncing."
            )
            self.risk.open_position = broker_direction
            # We don't know exact entry price; leave it at 0 so trailing doesn't activate
            self.risk.entry_price = 0.0
            self.risk.trade_count += 0  # don't inflate count, we don't know
            self.save()

        elif has_saved_position and has_broker_position:
            # Both agree there's a position -- verify direction matches
            if saved_position != broker_direction:
                logger.warning(
                    f"POSITION DIRECTION MISMATCH -- bot: {saved_position}, "
                    f"broker: {broker_direction}. Trusting broker."
                )
                self.risk.open_position = broker_direction
                self.risk.entry_price = 0.0
                self.risk.trailing_active = False
                self.risk.trailing_stop = 0.0
                self.save()
            else:
                logger.info(
                    f"Position reconciled OK -- {broker_direction} "
                    f"confirmed on broker"
                )
        else:
            logger.info("Position reconciliation OK -- both flat")

        return False, "Stale/processed state — bot continues normally"

    # ------------------------------------------------------------------
    # Graceful shutdown
    # ------------------------------------------------------------------

    def register_shutdown(self, flatten_on_exit: bool = False):
        """
        Register SIGINT/SIGTERM handlers.

        On signal: save state, optionally flatten position, then exit cleanly.
        """
        self.flatten_on_exit = flatten_on_exit

        def handler(signum, frame):
            sig_name = signal.Signals(signum).name
            logger.info(f"Received {sig_name} -- initiating graceful shutdown")
            self._handle_shutdown()

        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
        logger.info("Graceful shutdown handlers registered (SIGINT, SIGTERM)")

    def _handle_shutdown(self):
        """Execute the shutdown sequence."""
        logger.info("Graceful shutdown sequence started")

        # 1. Save current state
        self.save()

        # 2. Optionally flatten open position
        if self.flatten_on_exit and self.risk.open_position is not None:
            logger.warning(
                f"Flattening open {self.risk.open_position} position before exit"
            )
            result = self.executor.flatten_position()
            if result.get("success"):
                logger.info("Position flattened successfully")
            else:
                logger.error(
                    f"Failed to flatten position: {result.get('reason', 'unknown')}"
                )

        # 3. Final state save after any position changes
        self.save()

        logger.info("Graceful shutdown complete -- exiting")
        os._exit(0)
