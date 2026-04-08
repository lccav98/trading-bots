import requests
import logging

logger = logging.getLogger("execution")

class TSExecutionEngine:
    """Execution engine that communicates with the TypeScript executor sidecar."""

    def __init__(self, host="http://localhost:4321", default_size=1.0):
        self.host = host
        self.default_size = default_size
        self.open_orders = {}
        self.positions = {}

    def _check_health(self):
        """Check if the TS executor is running."""
        try:
            resp = requests.get(f"{self.host}/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def execute_signal(self, signal, size=None):
        """Convert a signal into a limit order via TS executor."""
        size = size or self.default_size

        if not self._check_health():
            logger.error("TS executor is not running")
            return None

        try:
            book = requests.get(
                f"{self.host}/orderbook",
                params={"token_id": signal.token_id},
                timeout=10
            ).json()
        except Exception as e:
            logger.error(f"Failed to get order book: {e}")
            return None

        if signal.side == "BUY":
            asks = book.get("asks", [])
            if not asks:
                logger.warning(f"No asks for {signal.token_id}, skipping")
                return None
            best_ask = float(asks[0]["price"])
            price = round(best_ask - 0.01, 3)
        else:
            bids = book.get("bids", [])
            if not bids:
                logger.warning(f"No bids for {signal.token_id}, skipping")
                return None
            best_bid = float(bids[0]["price"])
            price = round(best_bid + 0.01, 3)

        if price <= 0:
            logger.warning(f"Invalid price {price} for {signal.token_id}")
            return None

        num_shares = size / price
        tick_size = book.get("tick_size", "0.001")
        neg_risk = book.get("neg_risk", False)

        try:
            resp = requests.post(
                f"{self.host}/order",
                json={
                    "token_id": signal.token_id,
                    "price": price,
                    "size": num_shares,
                    "side": signal.side,
                    "tick_size": tick_size,
                    "neg_risk": neg_risk,
                },
                timeout=15
            )
            result = resp.json()

            if resp.status_code == 200 and result.get("success"):
                order_id = result.get("result", {}).get("orderID", "unknown")
                logger.info(
                    f"Placed {signal.side} order: {num_shares:.1f} shares "
                    f"@ {price} (order {order_id}) neg_risk={neg_risk}"
                )

                if order_id:
                    self.open_orders[order_id] = {
                        "signal": signal,
                        "price": price,
                        "size": num_shares,
                        "status": "open",
                    }

                return order_id
            else:
                logger.error(f"Order failed: {result}")
                return None

        except Exception as e:
            logger.error(f"Order request failed: {e}")
            return None

    def sync_positions(self):
        """Refresh positions from the API."""
        try:
            resp = requests.get(f"{self.host}/orders", timeout=10)
            if resp.status_code == 200:
                orders = resp.json()
                self.positions = {}
                for o in orders:
                    if o.get("status") == "MATCHED" or o.get("status") == "FILLED":
                        tid = o.get("asset_id", "")
                        if tid:
                            self.positions[tid] = {
                                "size": float(o.get("originalSize", 0)),
                                "avg_price": float(o.get("price", 0)),
                            }
        except Exception as e:
            logger.error(f"Position sync failed: {e}")

    def cancel_stale_orders(self, max_age_seconds=300):
        """Cancel orders that haven't filled within max_age."""
        try:
            resp = requests.get(f"{self.host}/orders", timeout=10)
            if resp.status_code == 200:
                orders = resp.json()
                for order in orders:
                    if order.get("status") == "OPEN":
                        oid = order.get("id") or order.get("orderID")
                        if oid:
                            requests.delete(f"{self.host}/order/{oid}", timeout=10)
                            logger.info(f"Cancelled stale order {oid}")
        except Exception as e:
            logger.error(f"Cancel failed: {e}")

    def get_balance(self):
        """Get current balance from TS executor."""
        try:
            resp = requests.get(f"{self.host}/balance", timeout=10)
            if resp.status_code == 200:
                return resp.json().get("balance", 0)
        except Exception:
            pass
        return 0
