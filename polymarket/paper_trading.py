import time
import logging

logger = logging.getLogger("paper")

class PaperExecutionEngine:
    """Drop-in replacement for ExecutionEngine that simulates trades."""

    def __init__(self, starting_balance=100.0):
        self.balance = starting_balance
        self.positions = {}  # token_id -> {size, avg_price, total_cost}
        self.open_orders = {}
        self.trade_log = []
        # Track SELL positions (short = negative balance in opposite token)
        self.short_positions = {}  # token_id -> {size, entry_cost}

    def execute_signal(self, signal, size=5.0):
        """Simulate a trade without hitting the API.

        BUY: spend $size, gain shares worth $size
        SELL with position: close position, gain/lose difference
        SELL without position: open short (receive $size, owe shares)
        """
        trade = {
            "timestamp": time.time(),
            "token_id": signal.token_id,
            "side": signal.side,
            "size": size,
            "reason": signal.reason,
            "market_question": signal.market_question,
        }
        self.trade_log.append(trade)

        tid = signal.token_id
        if signal.side == "BUY":
            current = self.positions.get(tid, {"size": 0, "avg_price": 0, "total_cost": 0})
            current["total_cost"] += size
            current["size"] += size
            if current["size"] > 0:
                current["avg_price"] = current["total_cost"] / current["size"]
            self.positions[tid] = current
            self.balance -= size

            # If we have a matching short, close it
            if tid in self.short_positions:
                short = self.short_positions[tid]
                pnl = short["entry_amount"] - size  # We received entry_amount, pay size to close
                self.balance += pnl  # Net P&L
                del self.short_positions[tid]

        else:  # SELL
            if tid in self.positions:
                # Close existing long position
                current = self.positions[tid]
                close_size = min(size, current["size"])
                proceeds = close_size  # Simplified: sell at $1 (par value)
                current["size"] -= close_size
                current["total_cost"] -= close_size * current["avg_price"]
                if current["size"] < 0.001:
                    current["size"] = 0
                    current["avg_price"] = 0
                    current["total_cost"] = 0
                self.positions[tid] = current
                self.balance += proceeds
            else:
                # Open short (receive cash now, owe settlement later)
                short = self.short_positions.get(tid, {"size": 0, "entry_amount": 0})
                short["size"] += size
                short["entry_amount"] += size
                self.short_positions[tid] = short
                self.balance += size  # Receive sale proceeds

        order_id = f"paper-{len(self.trade_log)}"
        self.open_orders[order_id] = {
            "signal": signal,
            "price": 0,
            "size": size,
            "status": "filled",
        }

        logger.info(f"[PAPER] {signal.side} ${size:.2f} - {signal.reason}")
        return order_id

    def sync_positions(self):
        """No-op for paper trading."""
        pass

    def cancel_stale_orders(self, max_age_seconds=300):
        """No-op for paper trading."""
        pass

    def _resolve_shorts_at_par(self):
        """When shorts resolve at $1 (lose case) or $0 (win case), apply P&L."""
        for tid, short in list(self.short_positions.items()):
            # In real trading, shorts resolve: either YES=$1 (we lose) or YES=$0 (we win)
            # For paper, we track unrealized. When resolved:
            # If YES resolves, we must buy back at $1 per share = we lose entry_amount
            # If NO resolves, we keep entry_amount = we win
            # Conservative: mark shorts as losing (buy back at par)
            pass  # Deferred until we have resolution data

    def summary(self):
        """Print paper trading results."""
        print(f"\n{'='*50}")
        print(f"Paper Trading Summary")
        print(f"{'='*50}")
        print(f"Total trades: {len(self.trade_log)}")
        print(f"Final balance: ${self.balance:.2f}")
        print(f"Open long positions: {len(self.positions)}")
        for tid, pos in self.positions.items():
            if pos["size"] > 0.001:
                print(f"  LONG {tid[:16]}... : {pos['size']:.2f} shares @ avg ${pos['avg_price']:.3f}")
        print(f"Open short positions: {len(self.short_positions)}")
        for tid, short in self.short_positions.items():
            print(f"  SHORT {tid[:16]}... : {short['size']:.2f} shares (received ${short['entry_amount']:.2f})")
        print(f"{'='*50}")
