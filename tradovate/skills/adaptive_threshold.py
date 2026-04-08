"""
skills/adaptive_threshold.py

Dynamically adjusts the minimum score threshold for trade execution
based on recent market conditions (volatility regime) and bot
performance (recent win rate, consecutive losses).

Default threshold comes from config MIN_SCORE_TO_TRADE (typically 4).
Adjustments keep the final threshold clamped within [3, 5].

Usage:
    from skills.adaptive_threshold import AdaptiveThreshold

    at = AdaptiveThreshold()
    trade_history = [...]   # list of dicts with "result" ("WIN"/"LOSS")
    candles       = [...]   # list of dicts with "high", "low", "close"

    threshold = at.get_current_threshold(trade_history, candles)
    regime    = at.get_regime(candles)          # "normal" | "high_vol" | "low_vol"
"""

import logging
from config.settings import MIN_SCORE_TO_TRADE

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _atr_from_candles(candles: list, period: int) -> float:
    """Compute ATR over a slice of candles by reusing the strategy module."""
    if len(candles) < period + 1:
        return 0.0

    from skills.strategy import atr as atr_func

    highs   = [c["high"]   for c in candles]
    lows    = [c["low"]    for c in candles]
    closes  = [c["close"]  for c in candles]
    return atr_func(highs, lows, closes, period)


# ------------------------------------------------------------------
# class
# ------------------------------------------------------------------

class AdaptiveThreshold:
    """Calculates a context-aware minimum score threshold for trades."""

    # --- constants ---
    THRESHOLD_MIN = 3
    THRESHOLD_MAX = 5

    SHORT_ATR_PERIOD = 20   # recent volatility window
    LONG_ATR_PERIOD  = 50   # baseline volatility window

    HIGH_VOL_FACTOR  = 1.5  # short ATR > long * 1.5  -> high_vol
    LOW_VOL_FACTOR   = 0.5  # short ATR < long * 0.5   -> low_vol

    LOOKBACK_TRADES  = 10
    WIN_RATE_GOOD    = 0.60  # >60% -> relax threshold
    WIN_RATE_BAD     = 0.40  # <40% -> tighten threshold
    CONSEC_LOSS_GAP  = 2     # consecutive losses -> tighten heavily

    def __init__(self, base_threshold: int | None = None):
        self.base_threshold = base_threshold or MIN_SCORE_TO_TRADE

    # --------------------------------------------------------------
    # public API
    # --------------------------------------------------------------

    def get_regime(self, candles: list) -> str:
        """
        Detect current market volatility regime.

        Returns one of: "normal", "high_vol", "low_vol".
        """
        short_atr = _atr_from_candles(candles, self.SHORT_ATR_PERIOD)
        long_atr  = _atr_from_candles(candles, self.LONG_ATR_PERIOD)

        if long_atr == 0:
            logger.debug("ATR(long)=0 — insufficient data, defaulting to normal regime")
            return "normal"

        ratio = short_atr / long_atr

        if ratio > self.HIGH_VOL_FACTOR:
            regime = "high_vol"
        elif ratio < self.LOW_VOL_FACTOR:
            regime = "low_vol"
        else:
            regime = "normal"

        self._last_regime = regime  # cache for main.py to avoid duplicate call

        logger.info(
            "Volatility regime: %s  (short_atr=%.4f, long_atr=%.4f, ratio=%.2f)",
            regime, short_atr, long_atr, ratio,
        )
        return regime

    def get_current_threshold(
        self,
        trade_history: list[dict],
        candles: list,
    ) -> int:
        """
        Return the adjusted minimum score threshold considering both
        market regime and recent bot performance.

        Parameters
        ----------
        trade_history : list[dict]
            Each dict must contain at least ``result`` with value
            ``"WIN"`` or ``"LOSS"`` (order: oldest first).
        candles : list[dict]
            Standard candle dicts with ``high``, ``low``, ``close``.

        Returns
        -------
        int
            Threshold clamped to [3, 5].
        """
        threshold = self.base_threshold
        reasons: list[str] = []

        # --- 1. Market regime adjustment ---
        regime = self.get_regime(candles)

        if regime == "high_vol":
            threshold += 1
            reasons.append(
                f"high volatility detected (ATR short/long ratio elevated), +1"
            )
        elif regime == "low_vol":
            threshold += 1
            reasons.append(
                f"low volatility / chop detected (ATR short/long ratio low), +1"
            )
        # normal -> no adjustment

        # --- 2. Performance-based adjustment ---
        adj, perf_reason = self._performance_adjustment(trade_history)
        threshold += adj
        if perf_reason:
            reasons.append(perf_reason)

        # --- 3. Clamp ---
        threshold = max(self.THRESHOLD_MIN, min(self.THRESHOLD_MAX, threshold))

        log_msg = (
            f"Adaptive threshold: {threshold}  (base={self.base_threshold}, "
            f"regime={regime}, adjustments: {', '.join(reasons) if reasons else 'none'})"
        )
        logger.info(log_msg)

        return threshold

    # --------------------------------------------------------------
    # performance helpers
    # --------------------------------------------------------------

    def _performance_adjustment(self, trade_history: list[dict]):
        """
        Returns (adjustment_int, reason_str).

        adjustment is typically -1, 0, +1, or +2 based on recent
        win-rate and consecutive losses.
        """
        if not trade_history:
            return 0, ""

        # Recent N trades
        recent = trade_history[-self.LOOKBACK_TRADES:]
        results = [t.get("result", "").upper() for t in recent]

        # --- Win rate ---
        completed = [r for r in results if r in ("WIN", "LOSS")]
        if not completed:
            return 0, ""

        wins = completed.count("WIN")
        losses = completed.count("LOSS")
        total = len(completed)
        win_rate = wins / total

        # --- Consecutive losses (most recent streak) ---
        consec_losses = 0
        for r in reversed(completed):
            if r == "LOSS":
                consec_losses += 1
            else:
                break

        adjustment = 0
        reason_parts: list[str] = []

        # Win-rate adjustments
        if win_rate > self.WIN_RATE_GOOD:
            adjustment -= 1
            reason_parts.append(
                f"win_rate={win_rate:.0%} (>{self.WIN_RATE_GOOD:.0%}), -1"
            )
        elif win_rate < self.WIN_RATE_BAD:
            adjustment += 1
            reason_parts.append(
                f"win_rate={win_rate:.0%} (<{self.WIN_RATE_BAD:.0%}), +1"
            )

        # Consecutive losses override
        if consec_losses >= self.CONSEC_LOSS_GAP:
            adjustment += 2
            reason_parts.append(
                f"{consec_losses} consecutive losses (>= {self.CONSEC_LOSS_GAP}), +2"
            )

        reason = " | ".join(reason_parts) if reason_parts else ""
        return adjustment, reason
