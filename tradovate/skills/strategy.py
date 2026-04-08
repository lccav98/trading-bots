"""
skills/strategy.py — Motor Multi-Estratégia
6 estratégias votam (peso 1-3 cada). Só executa se ≥3 concordam.

Estratégias:
  1. Mean Reversion  (BB + Stochastic) — reversão à média
  2. Trend Following (EMA 9/21/50 + MACD) —顺势
  3. Smart Money    (Order Blocks + FVG + Sweep) — institutional
  4. VWAP Pullback  (preço rejeita VWAP) — institutional anchor
  5. Momentum Scalp (RSI + Volume + ATR) — breakout rápido
  6. Session Alpha  (abertura London/NY) — alta volatilidade
"""

import logging
import numpy as np
from collections import deque
from config.settings import (
    BB_PERIOD, BB_STD,
    STOCH_K, STOCH_D, STOCH_SLOW,
    STOCH_OVERSOLD, STOCH_OVERBOUGHT,
    SYMBOL, TRAILING_STOP_TRIGGER_TICKS, MAX_DAILY_PROFIT,
)

logger = logging.getLogger(__name__)


# ============================================================
# INDICADORES BASE
# ============================================================

def ema(data: list, period: int) -> list:
    """EMA — Exponential Moving Average."""
    if len(data) < period:
        return []
    arr = np.array(data, dtype=float)
    result = np.full_like(arr, np.nan)
    result[period - 1] = np.mean(arr[:period])
    alpha = 2.0 / (period + 1)
    for i in range(period, len(arr)):
        result[i] = alpha * arr[i] + (1 - alpha) * result[i - 1]
    return result.tolist()


def rsi(closes: list, period: int = 14) -> float:
    """RSI — Relative Strength Index (último valor)."""
    if len(closes) < period + 1:
        return 50.0
    arr = np.array(closes, dtype=float)
    deltas = np.diff(arr[-period - 1:])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def macd(closes: list, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD — retorna (macd_line, signal_line, histogram)."""
    if len(closes) < slow + signal:
        return 0, 0, 0
    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)
    macd_vals = []
    for i in range(len(closes)):
        f = fast_ema[i] if not np.isnan(fast_ema[i]) else None
        s = slow_ema[i] if not np.isnan(slow_ema[i]) else None
        if f is not None and s is not None:
            macd_vals.append(f - s)
    if len(macd_vals) < signal:
        return macd_vals[-1] if macd_vals else 0, 0, 0
    signal_line = ema(macd_vals, signal)
    ml = macd_vals[-1]
    sl = signal_line[-1] if signal_line else 0
    return round(ml, 4), round(sl, 4), round(ml - sl, 4)


def atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """ATR — Average True Range."""
    if len(closes) < period + 1:
        return 0
    trs = []
    for i in range(1, len(closes)):
        high = highs[i]
        low  = lows[i]
        prev_close = closes[i - 1]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return round(np.mean(trs[-period:]), 4) if len(trs) >= period else round(np.mean(trs), 4) if trs else 0


def vwap(highs: list, lows: list, closes: list, volumes: list) -> float:
    """VWAP — Volume Weighted Average Price (cumulativo, sessão simples)."""
    if not volumes or len(volumes) < 2:
        return closes[-1] if closes else 0
    tp_arr = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
    vol_arr = volumes
    cum_tp_vol = sum(t * v for t, v in zip(tp_arr, vol_arr))
    cum_vol = sum(vol_arr)
    return round(cum_tp_vol / cum_vol, 4) if cum_vol > 0 else closes[-1]


def bollinger_bands(closes: list, period: int = BB_PERIOD, std_dev: float = BB_STD):
    """BB — Bollinger Bands."""
    if len(closes) < period:
        return None, None, None
    arr = np.array(closes[-period:], dtype=float)
    middle = np.mean(arr)
    std = np.std(arr, ddof=0)
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def stochastic(highs: list, lows: list, closes: list,
              k_period: int = STOCH_K, d_period: int = STOCH_D,
              slow: int = STOCH_SLOW):
    """Stochastic Oscillator — retorna (K, D)."""
    if len(closes) < k_period + d_period:
        return None, None
    k_values = []
    for i in range(k_period - 1, len(closes)):
        window_h = highs[i - k_period + 1: i + 1]
        window_l = lows[i - k_period + 1: i + 1]
        highest = max(window_h)
        lowest  = min(window_l)
        denom = highest - lowest
        if denom == 0:
            k_values.append(50.0)
        else:
            k_values.append(100 * (closes[i] - lowest) / denom)
    if not k_values:
        return None, None
    k = k_values[-1]
    d = np.mean(k_values[-d_period:]) if len(k_values) >= d_period else k_values[-1]
    return round(k, 2), round(d, 2)


def find_fvg(highs: list, lows: list, closes: list, lookback: int = 20):
    """Fair Value Gap — desequilíbrio entre candle 1 e candle 3 de uma sequência.
    Bullish FVG: high do candle 1 < low do candle 3 (gap de alta não preenchido)
    Bearish FVG: low do candle 1 > high do candle 3 (gap de baixa não preenchido)
    Retorna direction: 'bullish'/'bearish'/None.
    """
    if len(closes) < lookback + 3:
        return None
    # Escanear últimas N janelas de 3 candles consecutivas
    for i in range(max(1, len(closes) - lookback - 2), len(closes) - 2):
        h1, l1 = highs[i - 1], lows[i - 1]
        h3, l3 = highs[i + 1], lows[i + 1]
        c2 = closes[i]
        o2 = closes[i - 1]  # open approx = prev close

        # Bullish FVG: não há sobreposição entre candle 1 high e candle 3 low
        if h1 < l3 and c2 > o2:
            return "bullish"
        # Bearish FVG: não há sobreposição entre candle 1 low e candle 3 high
        if l1 > h3 and c2 < o2:
            return "bearish"
    return None


def detect_liquidity_sweep(highs: list, lows: list, closes: list, lookback: int = 20):
    """Liquidity Sweep — preço rompeu High/Low e fechou para trás.
    Bullish se sweep low (wick abaixo, reclaim), Bearish se sweep high (wick acima, rejection).
    """
    if len(closes) < lookback + 1:
        return None
    # Swing high/low antes da última vela
    recent_highs = highs[-(lookback + 1):-1]
    recent_lows  = lows[-(lookback + 1):-1]
    if not recent_highs or not recent_lows:
        return None
    swing_high = max(recent_highs)
    swing_low  = min(recent_lows)

    last_high, last_low, last_close = highs[-1], lows[-1], closes[-1]
    prev_close = closes[-2] if len(closes) > 1 else last_close

    # Bullish sweep: price wick abaixo do swing_low mas fecha acima (reclaim)
    if last_low < swing_low and last_close > swing_low:
        return "bullish"
    # Bearish sweep: price wick acima do swing_high mas fecha abaixo (rejection)
    if last_high > swing_high and last_close < swing_high:
        return "bearish"
    return None


# ============================================================
# ESTRATÉGIAS
# ============================================================

class StrategyResult:
    def __init__(self):
        self.votes = {"BUY": 0, "SELL": 0}
        self.max_score = 0
        self.reasons = []
        # Per-strategy votes for dashboard
        self.strategy_votes = {
            "MeanRev": {"action": "HOLD", "score": 0},
            "Trend": {"action": "HOLD", "score": 0},
            "SmartMoney": {"action": "HOLD", "score": 0},
            "VWAP": {"action": "HOLD", "score": 0},
            "Momentum": {"action": "HOLD", "score": 0},
            "Session": {"action": "HOLD", "score": 0},
        }

    def vote(self, action: str, weight: int, reason: str, strategy: str = None):
        if action in self.votes and weight > 0:
            self.votes[action] += weight
            self.reasons.append(f"[{weight}pt] {reason}")
        if strategy and strategy in self.strategy_votes:
            sv = self.strategy_votes[strategy]
            # Keep the dominant direction
            if weight > sv["score"] or sv["score"] == 0:
                sv["action"] = action
                sv["score"] = weight

    def best(self):
        if self.votes["BUY"] > self.votes["SELL"]:
            return "BUY", self.votes["BUY"]
        elif self.votes["SELL"] > self.votes["BUY"]:
            return "SELL", self.votes["SELL"]
        return "HOLD", 0


class StrategyEngine:
    def __init__(self):
        self.prev_vwap = None

    def analyze(self, candles: list) -> dict:
        """Analisa candles com todas as estratégias e retorna decisão."""
        result = StrategyResult()

        if len(candles) < 30:
            return {"action": "HOLD", "score": 0,
                    "reason": "Candles insuficientes", "price": 0}

        closes = [c["close"]  for c in candles]
        highs  = [c["high"]   for c in candles]
        lows   = [c["low"]    for c in candles]
        volumes = [c.get("volume", 0) for c in candles]
        price  = closes[-1]

        # Executa cada estratégia (passando strategy name)
        self._mean_reversion(closes, highs, lows, price, result)
        self._trend_following(closes, highs, lows, result)
        self._smart_money(highs, lows, closes, result)
        self._vwap_pullback(highs, lows, closes, volumes, price, result)
        self._momentum_scalp(highs, lows, closes, volumes, price, result)
        self._session_alpha(highs, lows, closes, result)

        action, score = result.best()

        # Calcula indicadores para o dashboard
        atr_val = atr(highs, lows, closes)
        rsi_val = rsi(closes)
        macd_val, macd_sig, macd_hist = macd(closes)
        k, d = stochastic(highs, lows, closes)
        bb_u, bb_m, bb_l = bollinger_bands(closes)
        v = vwap(highs, lows, closes, volumes)
        ema9_l = ema(closes, 9)
        ema21_l = ema(closes, 21)
        ema50_l = ema(closes, 50)

        indicators = {
            "RSI": rsi_val,
            "MACD": macd_val,
            "MACDSignal": macd_sig,
            "MACDHist": macd_hist,
            "StochK": k if k is not None else 50,
            "StochD": d if d is not None else 50,
            "BBUpper": bb_u if bb_u is not None else 0,
            "BBLower": bb_l if bb_l is not None else 0,
            "VWAP": v,
        }
        if ema9_l and ema21_l and ema50_l:
            indicators["EMAs"] = {"e9": ema9_l[-1], "e21": ema21_l[-1], "e50": ema50_l[-1]}

        return {
            "action":  action,
            "score":   score,
            "reason":  " | ".join(result.reasons[:4]),  # Top 4 reasons
            "price":   price,
            "details": result.reasons,
            "strategies": result.strategy_votes,
            "indicators": indicators,
            "ATR": atr_val,
        }

    def _mean_reversion(self, closes, highs, lows, price, result):
        """#1 Reversão à média — BB + Stochastic (peso 1)."""
        upper, middle, lower = bollinger_bands(closes)
        k, d = stochastic(highs, lows, closes)
        if None in (upper, middle, lower, k, d):
            return

        # BUY: preço na banda inferior + Stoch saindo de sobrevenda com cruzamento
        if price <= lower and k < STOCH_OVERSOLD and k > d:
            dist = (price - lower) / price * 100
            result.vote("BUY", 1, f"BB oversold (dist={dist:.2f}%) + Stoch K={k} > D={d}", "MeanRev")

        # SELL: preço na banda superior + Stoch saindo de sobrecompra
        elif price >= upper and k > STOCH_OVERBOUGHT and k < d:
            dist = (upper - price) / price * 100
            result.vote("SELL", 1, f"BB overbought (dist={dist:.2f}%) + Stoch K={k} < D={d}", "MeanRev")

    def _trend_following(self, closes, highs, lows, result):
        """#2 Trend Following — EMA Ribbon + MACD (peso 2 — tendência é forte)."""
        ema9  = ema(closes, 9)
        ema21 = ema(closes, 21)
        ema50 = ema(closes, 50)

        if len(ema50) < 3:
            return

        e9  = ema9[-1]
        e21 = ema21[-1]
        e50 = ema50[-1]

        macd_val, signal, histo = macd(closes)

        # BUY: EMA9 > EMA21 > EMA50 + MACD histogram positive
        if e9 > e21 > e50 and histo > 0:
            result.vote("BUY", 2, f"Trend UP EMA ribbon + MACD hist={histo:.4f}", "Trend")

        # SELL: EMA9 < EMA21 < EMA50 + MACD histogram negative
        elif e9 < e21 < e50 and histo < 0:
            result.vote("SELL", 2, f"Trend DN EMA ribbon + MACD hist={histo:.4f}", "Trend")

        # Extra: cruzamento de EMAs (sinal de entrada)
        if len(ema9) >= 2 and len(ema21) >= 2:
            # Golden cross recente (EMA9 cruzou acima EMA21)
            if ema9[-2] <= ema21[-2] and ema9[-1] > ema21[-1]:
                result.vote("BUY", 3, f"Golden Cross EMA9/21 (peso 3 — entrada de tendência)", "Trend")
            # Death cross recente
            elif ema9[-2] >= ema21[-2] and ema9[-1] < ema21[-1]:
                result.vote("SELL", 3, f"Death Cross EMA9/21 (peso 3 — entrada de tendência)", "Trend")

    def _smart_money(self, highs, lows, closes, result):
        """#3 Smart Money — Order Blocks + FVG + Liquidity Sweep (peso 2)."""
        fvg = find_fvg(highs, lows, closes)
        sweep = detect_liquidity_sweep(highs, lows, closes)
        price = closes[-1]

        # FVG Bullish + Liquidity Sweep Bullish = forte BUY
        if fvg == "bullish" and sweep == "bullish":
            result.vote("BUY", 3, f"FVG bullish + Liquidity Sweep (smart money confluence)", "SmartMoney")
        elif fvg == "bullish":
            result.vote("BUY", 1, "FVG bullish detected", "SmartMoney")
        elif sweep == "bullish":
            result.vote("BUY", 2, f"Liquidity Sweep bullish — price rejeitou low", "SmartMoney")

        # FVG Bearish + Liquidity Sweep Bearish = forte SELL
        if fvg == "bearish" and sweep == "bearish":
            result.vote("SELL", 3, f"FVG bearish + Liquidity Sweep (smart money confluence)", "SmartMoney")
        elif fvg == "bearish":
            result.vote("SELL", 1, "FVG bearish detected", "SmartMoney")
        elif sweep == "bearish":
            result.vote("SELL", 2, f"Liquidity Sweep bearish — price rejeitou high", "SmartMoney")

    def _vwap_pullback(self, highs, lows, closes, volumes, price, result):
        """#4 VWAP Pullback — preço rejeita VWAP em tendência (peso 2)."""
        v = vwap(highs, lows, closes, volumes)
        if v == 0:
            return

        dist_vwap = (price - v) / v * 100

        # Preço abaixo do VWAP e subindo (pullback bullish)
        if price < v and dist_vwap < -0.1 and len(closes) >= 3:
            if closes[-1] > closes[-2] > closes[-3]:
                result.vote("BUY", 2, f"VWAP pullback bullish (dist={dist_vwap:.2f}%, 3 green)", "VWAP")

        # Preço acima do VWAP e caindo (pullback bearish)
        elif price > v and dist_vwap > 0.1 and len(closes) >= 3:
            if closes[-1] < closes[-2] < closes[-3]:
                result.vote("SELL", 2, f"VWAP pullback bearish (dist={dist_vwap:.2f}%, 3 red)", "VWAP")

        # Preço longe demais do VWAP = mean reversion
        if abs(dist_vwap) > 0.5:
            direction = "SELL" if dist_vwap > 0 else "BUY"
            result.vote(direction, 1, f"VWAP mean reversion (dist={dist_vwap:.2f}%)", "VWAP")

        self.prev_vwap = v

    def _momentum_scalp(self, highs, lows, closes, volumes, price, result):
        """#5 Momentum Scalp — RSI + Volume Anomaly + ATR (peso 2)."""
        rsi_val = rsi(closes)
        atr_val = atr(highs, lows, closes)
        price_change = abs(closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) > 1 else 0

        # Average volume
        avg_vol = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes) if volumes else 0
        curr_vol = volumes[-1] if volumes else 0
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1

        # RSI oversold + volume spike + ATR expansion = BUY scalp
        if rsi_val < 30 and vol_ratio > 1.5 and atr_val > 0:
            result.vote("BUY", 2, f"Momentum scalp (RSI={rsi_val}, vol={vol_ratio:.1f}x, ATR={atr_val})")
        # RSI overbought + volume spike = SELL scalp
        elif rsi_val > 70 and vol_ratio > 1.5 and atr_val > 0:
            result.vote("SELL", 2, f"Momentum scalp short (RSI={rsi_val}, vol={vol_ratio:.1f}x, ATR={atr_val})")

        # Volume anomaly sem RSI extremo = breakout iminente
        if vol_ratio > 3 and price_change > 0.3:
            direction = "BUY" if closes[-1] > closes[-2] else "SELL"
            result.vote(direction, 1, f"Volume breakout (vol={vol_ratio:.1f}x, move={price_change:.2f}%)")

    def _session_alpha(self, highs, lows, closes, result):
        """#6 Session Alpha — aberturas London (9h BRT) e NY (11h30 BRT). Peso 2."""
        from datetime import datetime
        now = datetime.now()
        hour = now.hour
        minute = now.minute

        # London Open: 09h-10h UTC-3
        # NY Open: 11h30-12h30 UTC-3 (15h30 UTC = 12h30 BRT)
        london_open = (9 <= hour < 10)
        ny_open = (11 <= hour < 12) or (hour == 12 and minute <= 30)

        if not (london_open or ny_open):
            return

        # Range de abertura vs range médio
        if london_open:
            recent_range = np.mean([h - l for h, l in zip(highs[-10:], lows[-10:])]) if len(highs) >= 10 else 0
            open_range = highs[-1] - lows[-1] if len(highs) > 0 else 0

            if open_range > recent_range * 1.5 and len(closes) >= 2:
                direction = "BUY" if closes[-1] > closes[-2] else "SELL"
                session = "London Open"
                result.vote(direction, 2, f"{session} momentum breakout (range={open_range:.2f} vs avg={recent_range:.2f})")

        elif ny_open:
            # NY tem mais volume — busca reversal no primeiro candle
            if len(closes) >= 3:
                # 3 velas na mesma direção = follow
                if closes[-1] > closes[-2] > closes[-3]:
                    result.vote("BUY", 2, "NY Open bullish momentum (3 green)")
                elif closes[-1] < closes[-2] < closes[-3]:
                    result.vote("SELL", 2, "NY Open bearish momentum (3 red)")


# ============================================================
# GERAÇÃO DE SINAL (back compatibilidade)
# ============================================================

_engine = StrategyEngine()

def generate_signal(candles: list) -> dict:
    """
    Analisa candles e retorna sinal de trading.

    Retorno:
        {
            "action":  "BUY" | "SELL" | "HOLD",
            "score":   int,  # força (soma de votos)
            "reason":  str,  # resumo das razões
            "price":   float,
            "details": list, # razões detalhadas
        }
    """
    return _engine.analyze(candles)
