"""
Indicadores SMC / ICT — adaptado para hf_bot_futures.py
Coluna de tempo: 'ts' (timestamp ms int)
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd
import numpy as np


class TrendBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class BOSLevel(str, Enum):
    BOS   = "bos"
    CHOCH = "choch"


@dataclass
class SwingPoint:
    index: int
    price: float
    is_high: bool


@dataclass
class FVG:
    top: float
    bottom: float
    bias: TrendBias
    index: int


@dataclass
class OrderBlock:
    high: float
    low: float
    bias: TrendBias
    index: int


@dataclass
class VWAPLevel:
    vwap: float
    plus_1sd: float
    minus_1sd: float


@dataclass
class SMCSignal:
    bullish: bool
    bearish: bool
    confidence: float        # 0-1
    components: dict
    price: float
    entry_zone: Optional[tuple] = None


# ── Swing High / Low ─────────────────────────────────────────────────────────

def find_swing_highs_lows(
    df: pd.DataFrame,
    swing_length: int = 10,
) -> tuple[list[SwingPoint], list[SwingPoint]]:
    """Swing highs/lows vectorizados (rápido)."""
    high = df["high"].values
    low  = df["low"].values
    n    = len(high)
    highs, lows = [], []

    for i in range(swing_length, n - swing_length):
        window_h = high[i - swing_length : i + swing_length + 1]
        window_l = low[i  - swing_length : i + swing_length + 1]
        if high[i] >= window_h.max():
            highs.append(SwingPoint(index=i, price=float(high[i]), is_high=True))
        if low[i] <= window_l.min():
            lows.append(SwingPoint(index=i, price=float(low[i]),  is_high=False))

    return highs, lows


# ── BOS / CHoCH ──────────────────────────────────────────────────────────────

def detect_bos_choch(
    df: pd.DataFrame,
    highs: list[SwingPoint],
    lows:  list[SwingPoint],
) -> tuple[Optional[BOSLevel], TrendBias]:
    if len(highs) < 2 or len(lows) < 2:
        return None, TrendBias.NEUTRAL

    last_high, prev_high = highs[-1], highs[-2]
    last_low,  prev_low  = lows[-1],  lows[-2]
    close = float(df["close"].iloc[-1])

    if close > last_high.price:
        bos = BOSLevel.BOS if last_high.index > prev_high.index else BOSLevel.CHOCH
        return bos, TrendBias.BULLISH

    if close < last_low.price:
        bos = BOSLevel.BOS if last_low.index > prev_low.index else BOSLevel.CHOCH
        return bos, TrendBias.BEARISH

    return None, TrendBias.NEUTRAL


# ── Order Blocks ──────────────────────────────────────────────────────────────

def detect_order_blocks(
    df: pd.DataFrame,
    bos_type: Optional[BOSLevel],
    trend_bias: TrendBias,
    last_swing_high: Optional[SwingPoint],
    last_swing_low:  Optional[SwingPoint],
    lookback: int = 30,
) -> list[OrderBlock]:
    blocks = []
    if bos_type is None:
        return blocks

    open_  = df["open"].values
    close_ = df["close"].values
    high_  = df["high"].values
    low_   = df["low"].values

    if trend_bias == TrendBias.BULLISH and last_swing_low:
        anchor = last_swing_low.index
        for i in range(anchor - 1, max(anchor - lookback, 0), -1):
            if close_[i] < open_[i]:   # candle bearish
                blocks.append(OrderBlock(
                    high=float(high_[i]), low=float(low_[i]),
                    bias=TrendBias.BULLISH, index=i))
                break

    if trend_bias == TrendBias.BEARISH and last_swing_high:
        anchor = last_swing_high.index
        for i in range(anchor - 1, max(anchor - lookback, 0), -1):
            if close_[i] > open_[i]:   # candle bullish
                blocks.append(OrderBlock(
                    high=float(high_[i]), low=float(low_[i]),
                    bias=TrendBias.BEARISH, index=i))
                break

    return blocks


# ── Fair Value Gaps ───────────────────────────────────────────────────────────

def detect_fvg(df: pd.DataFrame) -> list[FVG]:
    """FVG clássico: gap entre candle[i-1] e candle[i+1] sem overlap."""
    gaps  = []
    high_ = df["high"].values
    low_  = df["low"].values
    close_= df["close"].values
    n     = len(df)

    for i in range(1, n - 1):
        prev_high = high_[i - 1]
        prev_low  = low_[i - 1]
        next_high = high_[i + 1]
        next_low  = low_[i + 1]

        # Bullish FVG: candle[i+1] não toca o high[i-1] → gap acima
        if next_low > prev_high:
            gaps.append(FVG(top=next_low, bottom=prev_high,
                            bias=TrendBias.BULLISH, index=i))
        # Bearish FVG: candle[i+1] não toca o low[i-1] → gap abaixo
        elif next_high < prev_low:
            gaps.append(FVG(top=prev_low, bottom=next_high,
                            bias=TrendBias.BEARISH, index=i))

    return gaps


def is_fvg_mitigated(fvg: FVG, close: float) -> bool:
    if fvg.bias == TrendBias.BULLISH:
        return close < fvg.bottom
    return close > fvg.top


# ── VWAP ─────────────────────────────────────────────────────────────────────

def calc_vwap(df: pd.DataFrame) -> VWAPLevel:
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_tpv = (typical * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum()
    vwap    = cum_tpv / cum_vol
    std     = vwap.rolling(20).std()
    v = float(vwap.iloc[-1])
    s = float(std.iloc[-1]) if not np.isnan(std.iloc[-1]) else 0.0
    return VWAPLevel(vwap=v, plus_1sd=v + s, minus_1sd=v - s)


# ── Aggregator ────────────────────────────────────────────────────────────────

class SMCAnalyzer:
    def __init__(self, swing_length: int = 10):
        self.swing_length = swing_length

    def analyze(self, df: pd.DataFrame) -> dict:
        """Retorna dicionário com estado SMC completo."""
        min_candles = self.swing_length * 2 + 5
        if len(df) < min_candles:
            return {"ok": False}

        highs, lows = find_swing_highs_lows(df, self.swing_length)
        last_high   = highs[-1] if highs else None
        last_low    = lows[-1]  if lows  else None

        bos_type, trend_bias = detect_bos_choch(df, highs, lows)
        order_blocks = detect_order_blocks(df, bos_type, trend_bias, last_high, last_low)

        close = float(df["close"].iloc[-1])
        all_fvgs = detect_fvg(df)
        fvgs = [f for f in all_fvgs[-20:] if not is_fvg_mitigated(f, close)]

        vwap = calc_vwap(df)

        trailing_top    = last_high.price if last_high else float(df["high"].max())
        trailing_bottom = last_low.price  if last_low  else float(df["low"].min())

        return {
            "ok": True,
            "close": close,
            "bos_type": bos_type,
            "trend_bias": trend_bias,
            "order_blocks": order_blocks,
            "fvgs": fvgs,
            "vwap": vwap,
            "trailing_top": trailing_top,
            "trailing_bottom": trailing_bottom,
        }

    def build_signal(self, state: dict) -> SMCSignal:
        if not state.get("ok"):
            return SMCSignal(bullish=False, bearish=False,
                             confidence=0, components={}, price=0)

        close         = state["close"]
        bos_type      = state["bos_type"]
        trend_bias    = state["trend_bias"]
        order_blocks  = state["order_blocks"]
        fvgs          = state["fvgs"]
        vwap          = state["vwap"]
        trailing_top  = state["trailing_top"]
        trailing_bot  = state["trailing_bottom"]

        bull_score = bear_score = 0
        components: dict = {}

        # 1. BOS / CHoCH
        if bos_type == BOSLevel.BOS and trend_bias == TrendBias.BULLISH:
            bull_score += 2; components["bos_bull"] = True
        elif bos_type == BOSLevel.BOS and trend_bias == TrendBias.BEARISH:
            bear_score += 2; components["bos_bear"] = True
        elif bos_type == BOSLevel.CHOCH:
            if trend_bias == TrendBias.BULLISH:
                bull_score += 1; components["choch_bull"] = True
            else:
                bear_score += 1; components["choch_bear"] = True

        # 2. Order Block
        active_ob = order_blocks[-1] if order_blocks else None
        if active_ob:
            if active_ob.bias == TrendBias.BULLISH and active_ob.low <= close <= active_ob.high:
                bull_score += 2; components["ob_bull"] = (active_ob.low, active_ob.high)
            elif active_ob.bias == TrendBias.BEARISH and active_ob.low <= close <= active_ob.high:
                bear_score += 2; components["ob_bear"] = (active_ob.low, active_ob.high)

        # 3. FVG
        if fvgs:
            last_fvg = fvgs[-1]
            if last_fvg.bias == TrendBias.BULLISH:
                bull_score += 1; components["fvg_bull"] = (last_fvg.bottom, last_fvg.top)
            else:
                bear_score += 1; components["fvg_bear"] = (last_fvg.bottom, last_fvg.top)

        # 4. VWAP
        if close > vwap.vwap:
            bull_score += 1; components["vwap_bull"] = True
        else:
            bear_score += 1; components["vwap_bear"] = True

        # 5. Premium / Discount
        mid = (trailing_top + trailing_bot) / 2
        if close < mid:
            bull_score += 1; components["discount_zone"] = True
        else:
            bear_score += 1; components["premium_zone"] = True

        MAX_SCORE = 7
        bullish = bull_score >= 3
        bearish = bear_score >= 3
        confidence = min(max(bull_score, bear_score) / MAX_SCORE, 1.0)

        entry_zone = (active_ob.low, active_ob.high) if active_ob else None

        return SMCSignal(
            bullish=bullish, bearish=bearish,
            confidence=confidence, components=components,
            price=close, entry_zone=entry_zone,
        )
