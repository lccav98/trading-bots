from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, OpenOrderParams
import logging
import time

logger = logging.getLogger("execution")

class ExecutionEngine:
    """Places and manages orders on Polymarket."""

    def __init__(self, client: ClobClient, default_size=5.0):
        self.client = client
        self.default_size = default_size
        self.open_orders = {}
        self.positions = {}

    def execute_signal(self, signal, size=None):
        """Convert a signal into a limit order."""
        size = size or self.default_size

        try:
            book = self.client.get_order_book(signal.token_id)
        except Exception as e:
            logger.error(f"Failed to get order book for {signal.token_id}: {e}")
            return None

        if signal.side == "BUY":
            if not book.asks:
                logger.warning(f"No asks for {signal.token_id}, skipping")
                return None
            best_ask = float(book.asks[0].price)
            price = round(best_ask - 0.01, 2)
        else:
            if not book.bids:
                logger.warning(f"No bids for {signal.token_id}, skipping")
                return None
            best_bid = float(book.bids[0].price)
            price = round(best_bid + 0.01, 2)

        if price <= 0:
            logger.warning(f"Invalid price {price} for {signal.token_id}")
            return None

        num_shares = size / price
        tick_size = book.tick_size
        neg_risk = book.neg_risk

        try:
            order_args = OrderArgs(
                token_id=signal.token_id,
                price=price,
                size=num_shares,
                side=signal.side,
                options={} if not neg_risk else {"neg_risk": True}
            )
            signed = self.client.create_order(order_args)
            response = self.client.post_order(signed, OrderType.GTC)

            order_id = response.get("orderID") if isinstance(response, dict) else getattr(response, "orderID", None)

            logger.info(
                f"Placed {signal.side} order: {num_shares:.1f} shares "
                f"@ {price} (order {order_id}) neg_risk={neg_risk} tick_size={tick_size}"
            )

            if order_id:
                self.open_orders[order_id] = {
                    "signal": signal,
                    "price": price,
                    "size": num_shares,
                    "status": "open",
                    "created_at": time.time(),
                }

            return order_id

        except Exception as e:
            logger.error(f"Order failed: {e}")
            return None

    def sync_positions(self):
        """Refresh positions from the API using trade history."""
        try:
            trades = self.client.get_trades()
            self.positions = {}
            for t in trades:
                token_id = t.get("asset_id") or t.get("token_id", "")
                side = t.get("side", "")
                size = float(t.get("size", 0))
                price = float(t.get("price", 0))

                if token_id not in self.positions:
                    self.positions[token_id] = {
                        "size": 0,
                        "avg_price": 0,
                        "total_cost": 0,
                    }

                pos = self.positions[token_id]
                if side == "BUY":
                    pos["total_cost"] += size * price
                    pos["size"] += size
                else:
                    pos["size"] -= size

                if pos["size"] != 0:
                    pos["avg_price"] = pos["total_cost"] / abs(pos["size"]) if pos["size"] != 0 else 0
                else:
                    pos["avg_price"] = 0
                    pos["total_cost"] = 0

            # Remove closed positions
            self.positions = {k: v for k, v in self.positions.items() if abs(v["size"]) > 0.001}
        except Exception as e:
            logger.error(f"Position sync failed: {e}")

    def cancel_stale_orders(self, max_age_seconds=300):
        """Cancel orders that haven't filled within max_age."""
        try:
            open_orders = self.client.get_orders(OpenOrderParams())
            now = time.time()
            for order in open_orders:
                order_id = order.get("id")
                if not order_id:
                    continue

                local_info = self.open_orders.get(order_id, {})
                created_at = local_info.get("created_at")

                if created_at and (now - created_at) < max_age_seconds:
                    continue

                self.client.cancel(order_id)
                logger.info(f"Cancelled stale order {order_id}")
                if order_id in self.open_orders:
                    self.open_orders[order_id]["status"] = "cancelled"
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
