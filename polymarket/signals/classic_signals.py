from collections import defaultdict
from dataclasses import dataclass
import logging

logger = logging.getLogger("signals")

@dataclass
class Signal:
    condition_id: str
    token_id: str
    side: str
    strength: float
    reason: str
    market_question: str = ""

class ThresholdSignalGenerator:
    """Generates signals when price deviates from moving average."""

    def __init__(self, lookback=20, buy_threshold=-0.05, sell_threshold=0.05):
        self.lookback = lookback
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.price_history = defaultdict(list)

    def update_price(self, condition_id, price):
        """Record a new price observation."""
        history = self.price_history[condition_id]
        history.append(price)
        if len(history) > self.lookback * 2:
            self.price_history[condition_id] = history[-self.lookback:]

    def generate_signals(self, watchlist):
        """Evaluate each market and return signals."""
        signals = []

        for market in watchlist:
            cid = market["condition_id"]
            current_price = market["price"]
            self.update_price(cid, current_price)

            history = self.price_history[cid]
            if len(history) < self.lookback:
                continue

            avg_price = sum(history[-self.lookback:]) / self.lookback
            deviation = (current_price - avg_price) / avg_price

            if deviation <= self.buy_threshold:
                signals.append(Signal(
                    condition_id=cid,
                    token_id=market["token_ids"][0],
                    side="BUY",
                    strength=min(abs(deviation) / 0.10, 1.0),
                    reason=f"Price {current_price:.3f} is {deviation:.1%} below {self.lookback}-period avg {avg_price:.3f}",
                    market_question=market["question"],
                ))
            elif deviation >= self.sell_threshold:
                signals.append(Signal(
                    condition_id=cid,
                    token_id=market["token_ids"][0],
                    side="SELL",
                    strength=min(abs(deviation) / 0.10, 1.0),
                    reason=f"Price {current_price:.3f} is {deviation:.1%} above {self.lookback}-period avg {avg_price:.3f}",
                    market_question=market["question"],
                ))

        logger.info(f"Generated {len(signals)} signals from {len(watchlist)} markets")
        return signals

class MomentumSignalGenerator:
    """Generates signals based on sustained price momentum."""

    def __init__(self, consecutive_periods=3, min_move=0.02):
        self.consecutive_periods = consecutive_periods
        self.min_move = min_move
        self.price_history = defaultdict(list)

    def update_price(self, condition_id, price):
        history = self.price_history[condition_id]
        history.append(price)
        if len(history) > self.consecutive_periods + 5:
            self.price_history[condition_id] = history[-(self.consecutive_periods + 5):]

    def generate_signals(self, watchlist):
        """Generate momentum signals."""
        signals = []

        for market in watchlist:
            cid = market["condition_id"]
            current_price = market["price"]
            self.update_price(cid, current_price)

            history = self.price_history[cid]
            if len(history) < self.consecutive_periods + 1:
                continue

            recent = history[-(self.consecutive_periods + 1):]
            moves = [recent[i+1] - recent[i] for i in range(len(recent)-1)]

            all_up = all(m > self.min_move for m in moves)
            all_down = all(m < -self.min_move for m in moves)

            if all_up:
                total_move = sum(moves)
                signals.append(Signal(
                    condition_id=cid,
                    token_id=market["token_ids"][0],
                    side="BUY",
                    strength=min(total_move / 0.15, 1.0),
                    reason=f"Momentum UP: {self.consecutive_periods} consecutive moves, total {total_move:.1%}",
                    market_question=market["question"],
                ))
            elif all_down:
                total_move = abs(sum(moves))
                signals.append(Signal(
                    condition_id=cid,
                    token_id=market["token_ids"][0],
                    side="SELL",
                    strength=min(total_move / 0.15, 1.0),
                    reason=f"Momentum DOWN: {self.consecutive_periods} consecutive moves, total {total_move:.1%}",
                    market_question=market["question"],
                ))

        logger.info(f"Generated {len(signals)} momentum signals from {len(watchlist)} markets")
        return signals
