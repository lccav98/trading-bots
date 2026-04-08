import logging
import time
from dataclasses import dataclass

from data.binance import fetch_klines, fetch_last_price
from indicators.vwap import compute_session_vwap, compute_vwap_series
from indicators.rsi import compute_rsi, sma, slope_last
from indicators.macd import compute_macd
from indicators.heiken_ashi import compute_heiken_ashi, count_consecutive
from engines.regime import detect_regime
from engines.probability import score_direction, apply_time_awareness
from engines.edge import compute_edge, decide

logger = logging.getLogger("signals.ta")

@dataclass
class TASignal:
    side: str
    strength: str
    phase: str
    edge: float
    model_up: float
    model_down: float
    market_up: float
    market_down: float
    regime: str
    reason: str
    market_question: str = ""
    token_id_up: str = ""
    token_id_down: str = ""

class BTC15mTASignalGenerator:
    """
    Ported from PolymarketBTC15mAssistant.
    Combines Binance klines + Polymarket market prices to generate
    technical analysis signals for BTC 15m Up/Down markets.
    """

    def __init__(
        self,
        candle_window_minutes=15,
        rsi_period=14,
        rsi_ma_period=5,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        vwap_slope_lookback=5,
    ):
        self.candle_window_minutes = candle_window_minutes
        self.rsi_period = rsi_period
        self.rsi_ma_period = rsi_ma_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.vwap_slope_lookback = vwap_slope_lookback
        self.price_history = []

    def _compute_time_left(self, market):
        """Estimate minutes remaining until market settlement."""
        end_date = market.get("end_date") or market.get("endDate")
        if end_date:
            try:
                if isinstance(end_date, str):
                    from datetime import datetime
                    end_ts = datetime.fromisoformat(end_date.replace("Z", "+00:00")).timestamp()
                else:
                    end_ts = float(end_date)
                remaining = (end_ts - time.time()) / 60
                return max(0, remaining)
            except Exception:
                pass
        return self.candle_window_minutes

    def generate_signals(self, watchlist):
        """
        Scan BTC 15m markets from watchlist and generate TA signals.
        watchlist should contain markets with BTC 15m Up/Down data.
        """
        signals = []

        klines_1m = fetch_klines(interval="1m", limit=240)
        if not klines_1m:
            logger.warning("No klines data from Binance")
            return signals

        last_price = fetch_last_price()
        if last_price is None:
            logger.warning("No last price from Binance")
            return signals

        closes = [c["close"] for c in klines_1m]

        vwap_series = compute_vwap_series(klines_1m)
        vwap_now = vwap_series[-1] if vwap_series else None
        vwap_slope = None
        if vwap_series and len(vwap_series) >= self.vwap_slope_lookback:
            vwap_now_val = vwap_series[-1]
            vwap_prev = vwap_series[-self.vwap_slope_lookback]
            vwap_slope = (vwap_now_val - vwap_prev) / self.vwap_slope_lookback

        rsi_now = compute_rsi(closes, self.rsi_period)
        rsi_series = []
        for i in range(len(closes)):
            sub = closes[:i + 1]
            r = compute_rsi(sub, self.rsi_period)
            if r is not None:
                rsi_series.append(r)
        rsi_ma = sma(rsi_series, self.rsi_ma_period) if rsi_series else None
        rsi_slope = slope_last(rsi_series, 3) if rsi_series else None

        macd = compute_macd(closes, self.macd_fast, self.macd_slow, self.macd_signal)

        ha = compute_heiken_ashi(klines_1m)
        consec = count_consecutive(ha)

        volume_recent = sum(c["volume"] for c in klines_1m[-20:]) if len(klines_1m) >= 20 else 0
        volume_avg = sum(c["volume"] for c in klines_1m[-120:]) / 6 if len(klines_1m) >= 120 else 0

        vwap_cross_count = self._count_vwap_crosses(closes, vwap_series, 20)

        failed_vwap_reclaim = False
        if vwap_now is not None and len(vwap_series) >= 3:
            failed_vwap_reclaim = closes[-1] < vwap_now and closes[-2] > vwap_series[-2]

        regime = detect_regime(
            price=last_price,
            vwap=vwap_now,
            vwap_slope=vwap_slope,
            vwap_cross_count=vwap_cross_count,
            volume_recent=volume_recent,
            volume_avg=volume_avg,
        )

        scored = score_direction(
            price=last_price,
            vwap=vwap_now,
            vwap_slope=vwap_slope,
            rsi=rsi_now,
            rsi_slope=rsi_slope,
            macd=macd,
            heiken_color=consec["color"],
            heiken_count=consec["count"],
            failed_vwap_reclaim=failed_vwap_reclaim,
        )

        macd_hist_str = f"{macd['hist']:.2f}" if macd else "N/A"
        logger.info(
            f"TA Snapshot: price=${last_price:.0f} | RSI={rsi_now:.1f} | "
            f"VWAP={vwap_now:.0f} | MACD hist={macd_hist_str} | "
            f"HA={consec['color']} x{consec['count']} | regime={regime['regime']}"
        )

        for market in watchlist:
            time_left = self._compute_time_left(market)
            time_aware = apply_time_awareness(scored["raw_up"], time_left, self.candle_window_minutes)

            market_up = market.get("price")
            market_down = 1 - market_up if market_up is not None else None

            edge = compute_edge(
                model_up=time_aware["adjusted_up"],
                model_down=time_aware["adjusted_down"],
                market_yes=market_up,
                market_no=market_down,
            )

            rec = decide(
                remaining_minutes=time_left,
                edge_up=edge["edge_up"],
                edge_down=edge["edge_down"],
                model_up=time_aware["adjusted_up"],
                model_down=time_aware["adjusted_down"],
            )

            if rec["action"] != "ENTER":
                continue

            edge_val = edge["edge_up"] if rec["side"] == "UP" else edge["edge_down"]

            # MODERADO filters (backtest optimized + 3/4 indicator agreement)
            if edge_val < 0.15:
                continue

            # Check indicator agreement (3/4 minimum for MODERADO)
            agreements = self._check_indicator_agreement(
                rsi_now, rsi_slope, macd, consec, vwap_now, last_price, vwap_slope, rec["side"]
            )
            if agreements < 3:
                continue

            side = "BUY" if rec["side"] == "UP" else "SELL"
            token_id = market["token_ids"][0] if market.get("token_ids") else ""

            reason = (
                f"TA {rec['side']} | edge={edge_val:.3f} | "
                f"prob={time_aware['adjusted_up']:.2f}/{time_aware['adjusted_down']:.2f} | "
                f"regime={regime['regime']} | {rec['phase']} {rec['strength']} | indicators={agreements}/4"
            )

            signals.append(TASignal(
                side=side,
                strength=rec["strength"],
                phase=rec["phase"],
                edge=edge["edge_up"] if rec["side"] == "UP" else edge["edge_down"],
                model_up=time_aware["adjusted_up"],
                model_down=time_aware["adjusted_down"],
                market_up=edge["market_up"],
                market_down=edge["market_down"],
                regime=regime["regime"],
                reason=reason,
                market_question=market.get("question", ""),
                token_id_up=market["token_ids"][0] if len(market.get("token_ids", [])) > 0 else "",
                token_id_down=market["token_ids"][1] if len(market.get("token_ids", [])) > 1 else "",
            ))

        logger.info(f"Generated {len(signals)} TA signals from {len(watchlist)} markets")
        return signals

    def _count_vwap_crosses(self, closes, vwap_series, lookback):
        if not closes or not vwap_series or len(closes) < lookback or len(vwap_series) < lookback:
            return 0
        crosses = 0
        for i in range(len(closes) - lookback + 1, len(closes)):
            prev = closes[i - 1] - vwap_series[i - 1]
            cur = closes[i] - vwap_series[i]
            if prev == 0:
                continue
            if (prev > 0 and cur < 0) or (prev < 0 and cur > 0):
                crosses += 1
        return crosses

    def _check_indicator_agreement(self, rsi_now, rsi_slope, macd, consec, vwap_now, price, vwap_slope, side):
        agreements = 0

        if rsi_now is not None and rsi_slope is not None:
            if side == "UP" and rsi_now > 50 and rsi_slope > 0:
                agreements += 1
            elif side == "DOWN" and rsi_now < 50 and rsi_slope < 0:
                agreements += 1

        if macd is not None:
            if side == "UP" and macd["hist"] > 0 and macd["histDelta"] > 0:
                agreements += 1
            elif side == "DOWN" and macd["hist"] < 0 and macd["histDelta"] < 0:
                agreements += 1

        if consec["color"] is not None:
            if side == "UP" and consec["color"] == "green" and consec["count"] >= 2:
                agreements += 1
            elif side == "DOWN" and consec["color"] == "red" and consec["count"] >= 2:
                agreements += 1

        if vwap_now is not None and vwap_slope is not None:
            if side == "UP" and price > vwap_now and vwap_slope > 0:
                agreements += 1
            elif side == "DOWN" and price < vwap_now and vwap_slope < 0:
                agreements += 1

        return agreements
