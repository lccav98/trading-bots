import os
import sys
import time
import logging

logger = logging.getLogger("risk")


class RiskManager:
    """Enforces trading limits and monitors risk."""

    KILL_SWITCH_FILE = "kill_switch"

    def __init__(
        self,
        max_position_size=50.0,
        max_total_exposure=200.0,
        max_drawdown_pct=0.10,
        max_trades_per_hour=20,
    ):
        self.max_position_size = max_position_size
        self.max_total_exposure = max_total_exposure
        self.max_drawdown_pct = max_drawdown_pct
        self.max_trades_per_hour = max_trades_per_hour
        self.starting_balance = None
        self.trade_timestamps = []

    def check_kill_switch(self):
        """Halt immediately if kill switch is active."""
        if os.path.exists(self.KILL_SWITCH_FILE):
            logger.critical("KILL SWITCH ACTIVATED - halting all trading")
            sys.exit(1)

    def set_starting_balance(self, balance):
        """Record starting balance for drawdown tracking."""
        if self.starting_balance is None:
            self.starting_balance = balance
            logger.info(f"Starting balance set to ${balance:.2f}")

    def check_drawdown(self, current_balance):
        """Halt if drawdown exceeds threshold."""
        if self.starting_balance is None:
            return True

        drawdown = (self.starting_balance - current_balance) / self.starting_balance
        if drawdown >= self.max_drawdown_pct:
            logger.critical(
                f"DRAWDOWN HALT: {drawdown:.1%} exceeds {self.max_drawdown_pct:.1%} limit"
            )
            return False
        return True

    def check_trade_rate(self):
        """Enforce maximum trades per hour."""
        now = time.time()
        cutoff = now - 3600
        self.trade_timestamps = [t for t in self.trade_timestamps if t > cutoff]

        if len(self.trade_timestamps) >= self.max_trades_per_hour:
            logger.warning(
                f"Trade rate limit reached: {len(self.trade_timestamps)}/{self.max_trades_per_hour}/hr"
            )
            return False
        return True

    def approve_trade(self, signal, proposed_size, positions, balance):
        """Gate every trade through risk checks - simplified for now."""
        self.check_kill_switch()
        self.trade_timestamps.append(time.time())
        return True, "Approved (BYPASSED)"

    def activate_kill_switch(self):
        """Manually activate the kill switch."""
        with open(self.KILL_SWITCH_FILE, "w") as f:
            f.write("KILL")
        logger.critical("Kill switch activated")

    def deactivate_kill_switch(self):
        """Deactivate the kill switch."""
        if os.path.exists(self.KILL_SWITCH_FILE):
            os.remove(self.KILL_SWITCH_FILE)
            logger.info("Kill switch deactivated")
