"""
core/market_data.py — Feed de candles via yfinance
"""

import asyncio
import logging
from collections import deque

import yfinance as yf

from config.settings import SYMBOL, TIMEFRAME_MINUTES

logger = logging.getLogger(__name__)

SYMBOL_TO_YF = {
    "MNQ": "MNQ=F",
    "MES": "MES=F",
    "MBT": "MBT=F",
    "ES": "ES=F",
    "NQ": "NQ=F",
    "CL": "CL=F",
    "GC": "GC=F",
    "YM": "YM=F",
    "RTY": "RTY=F",
    "ZB": "ZB=F",
}


def _to_candle(idx, row) -> dict:
    return {
        "timestamp": int(idx.timestamp() * 1000),
        "open": round(float(row["Open"]), 2),
        "high": round(float(row["High"]), 2),
        "low": round(float(row["Low"]), 2),
        "close": round(float(row["Close"]), 2),
        "volume": int(row.get("Volume", 0)),
    }


class MarketDataFeed:
    def __init__(self, auth=None, max_candles: int = 500):
        self.symbol = SYMBOL
        yf_sym = SYMBOL_TO_YF.get(SYMBOL)
        if yf_sym is None:
            raise ValueError(f"Symbol {SYMBOL} not mapped to yfinance ticker")
        self.yf_symbol = yf_sym
        self.candles = deque(maxlen=max_candles)
        self.last_candle = None
        self._poll_interval = max(TIMEFRAME_MINUTES * 60, 30)
        self._period = "5d" if TIMEFRAME_MINUTES >= 5 else "1d"
        self._ticker = yf.Ticker(self.yf_symbol)

    async def connect(self):
        self._refresh(full=True)
        if not self.candles:
            logger.warning(f"⚠️ Falha ao carregar {self.symbol}")
            return

        logger.info(
            f"📊 {self.symbol} | {len(self.candles)} candles | "
            f"Poll a cada {self._poll_interval:.0f}s"
        )

        while True:
            await asyncio.sleep(self._poll_interval)
            await asyncio.to_thread(self._refresh)

    def _refresh(self, *, full: bool = False):
        try:
            df = self._ticker.history(
                period=self._period, interval=f"{TIMEFRAME_MINUTES}m"
            )
        except Exception as e:
            logger.debug(f"yfinance fetch error: {e}")
            return

        if df.empty:
            return

        if full:
            self.candles.clear()

        last_ts = self.last_candle["timestamp"] if self.last_candle else None
        for idx, row in df.iterrows():
            ts = int(idx.timestamp() * 1000)
            if ts == last_ts:
                # Candle exists — only update it in place (OHLCV can change)
                self.candles[-1] = _to_candle(idx, row)
                continue
            if last_ts is not None and ts < last_ts:
                # Older than what we have — skip entirely
                continue
            self.candles.append(_to_candle(idx, row))

        if self.candles:
            self.last_candle = self.candles[-1]

    def get_candles(self) -> list:
        return list(self.candles)

    def get_latest_candle(self) -> dict | None:
        return dict(self.last_candle) if self.last_candle else None
