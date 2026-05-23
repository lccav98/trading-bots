import time
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CooldownManager:

    def __init__(self, base_cooldown_win=30 * 60, base_cooldown_loss=7200,
                 max_consecutive_losses=3, pause_cycles=2,
                 adaptive=True):
        self.cooldowns        = {}
        self.base_win         = base_cooldown_win
        self.base_loss        = base_cooldown_loss
        self.adaptive         = adaptive
        self.max_consecutive  = max_consecutive_losses
        self.pause_cycles     = pause_cycles
        self.consecutive_losses = 0
        self.skip_cycles      = 0
        self._loss_sizes      = []

    def is_blocked(self, symbol):
        now = time.time()
        self.cooldowns = {k: v for k, v in self.cooldowns.items() if v > now}
        if self.skip_cycles > 0:
            return True
        return symbol in self.cooldowns

    def time_remaining(self, symbol):
        now = time.time()
        if symbol in self.cooldowns and self.cooldowns[symbol] > now:
            return max(0, (self.cooldowns[symbol] - now) / 60)
        return 0

    def record_win(self, symbol, timeframe='5m'):
        tf_map = {'5m': 1.0, '15m': 2.0, '1h': 4.0}
        multiplier = tf_map.get(timeframe, 1.0)
        cd = int(self.base_win * multiplier)
        self.cooldowns[symbol] = time.time() + cd
        self.consecutive_losses = 0
        logger.info(f"Cooldown {symbol} (win): {cd / 60:.0f}min")

    def record_loss(self, symbol, loss_pct, timeframe='5m'):
        if self.adaptive:
            loss_bps = abs(loss_pct) * 10000
            if loss_bps < 50:
                cd = self.base_loss * 0.5
            elif loss_bps < 100:
                cd = self.base_loss
            else:
                cd = self.base_loss * 2.0
        else:
            cd = self.base_loss

        self.cooldowns[symbol] = time.time() + cd
        self.consecutive_losses += 1
        logger.info(f"Cooldown {symbol} (loss -{loss_pct*100:.2f}%): {cd / 3600:.1f}h")

        if self.consecutive_losses >= self.max_consecutive:
            self.skip_cycles = self.pause_cycles
            logger.warning(
                f"{self.consecutive_losses} perdas consecutivas — "
                f"pausando {self.skip_cycles} ciclos"
            )

    def decay(self):
        self.skip_cycles = max(0, self.skip_cycles - 1)

    def to_dict(self):
        return {'cooldowns': self.cooldowns, 'consecutive_losses': self.consecutive_losses}

    def from_dict(self, d):
        self.cooldowns          = d.get('cooldowns', {})
        self.consecutive_losses = d.get('consecutive_losses', 0)
        now = time.time()
        self.cooldowns = {k: v for k, v in self.cooldowns.items() if v > now}