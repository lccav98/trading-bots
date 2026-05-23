import os
import sys
import time
import json
import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv

from core.indicators import Indicators, analyze_momentum
from core.position import PositionManager
from core.cooldown import CooldownManager
from core.session import SessionManager
from core.sizing import position_size_kelly

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hf_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

COMMISSION = 0.001


class HighFrequencyBot:

    def __init__(self, config):
        self.symbol      = config.get('symbol', 'TRXUSDT')
        self.paper_mode  = config.get('paper_mode', True)
        self.position_fraction = config.get('position_fraction', 0.10)

        self.profit_tier1     = config.get('profit_tier1', 0.005)
        self.profit_tier2     = config.get('profit_tier2', 0.030)
        self.stop_loss_pct    = config.get('stop_loss', 0.015)
        self.trailing_pct     = config.get('trailing_stop_pct', 0.005)
        self.max_trades_per_cycle = config.get('max_trades_per_cycle', 3)
        self.cycle_duration       = config.get('cycle_duration', 300)
        self.min_24h_volume       = config.get('min_24h_volume', 1_000_000)
        self.params = config.get('params', {
            'c1_thresh': 0.001, 'c5_thresh': 0.002,
            'atr_mult': 2.0, 'use_ema': False,
            'rsi_max': 70, 'stoch_max': 80,
            'adx_thresh': 0,
        })

        self.balance            = float(config.get('paper_balance', 10.0))
        self.trade_count        = 0
        self.daily_pnl          = 0.0
        self.trade_history      = []
        self.cycle_start        = time.time()

        self.pos_mgr = PositionManager(commission=COMMISSION, quote_asset='USDT')
        self.cd_mgr  = CooldownManager(
            base_cooldown_loss=7200,
            max_consecutive_losses=config.get('max_consecutive_losses', 3),
            pause_cycles=2,
            adaptive=True,
        )
        self.session_mgr = SessionManager(
            hours_avoid=config.get('avoid_hours_utc', [2, 3, 4]),
        )

        self.quote_asset = 'USDT'
        self.base_asset  = ''

        api_key    = config.get('api_key', '')
        api_secret = config.get('api_secret', '')
        self.client = None
        if api_key and api_secret:
            self.client = Client(api_key, api_secret)
            self._detect_assets()
            if not self.paper_mode:
                self._sync_balance()

    def _detect_assets(self):
        try:
            info = self.client.get_symbol_info(self.symbol)
            self.base_asset  = info['baseAsset']
            self.quote_asset = info['quoteAsset']
            logger.info(f"Par: {self.base_asset}/{self.quote_asset}")
        except Exception as e:
            logger.warning(f"Não foi possível detectar ativos do par: {e}")

    def _sync_balance(self):
        try:
            account = self.client.get_account()
            for bal in account['balances']:
                if bal['asset'] == self.quote_asset:
                    self.balance = float(bal['free'])
                    logger.info(f"Saldo sincronizado: {self.balance:.6f} {self.quote_asset}")
                    return
        except Exception as e:
            logger.error(f"Falha ao sincronizar saldo: {e}")

    def get_price(self):
        if not self.client:
            return None
        try:
            t = self.client.get_symbol_ticker(symbol=self.symbol)
            return float(t['price'])
        except Exception:
            return None

    def get_klines(self, limit=120):
        if not self.client:
            return None
        try:
            klines = self.client.get_klines(
                symbol=self.symbol,
                interval=Client.KLINE_INTERVAL_5MINUTE,
                limit=limit
            )
            df = pd.DataFrame(klines, columns=[
                'ts', 'open', 'high', 'low', 'close', 'volume',
                'close_ts', 'quote_vol', 'trades',
                'tb_base', 'tb_quote', 'ignore'
            ])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            return df
        except Exception as e:
            logger.error(f"Erro ao buscar klines: {e}")
            return None

    def get_24h_volume(self):
        if not self.client:
            return float('inf')
        try:
            ticker = self.client.get_ticker(symbol=self.symbol)
            return float(ticker['quoteVolume'])
        except Exception:
            return float('inf')

    def _open_position(self, price, order_size):
        qty  = order_size / price
        cost = order_size * (1 + COMMISSION)

        if self.paper_mode:
            self.balance -= cost
        else:
            try:
                order = self.client.order_market_buy(
                    symbol=self.symbol,
                    quantity=round(qty, 2)
                )
                if order.get('fills'):
                    price = float(order['fills'][0]['price'])
                self.balance -= cost
            except Exception as e:
                logger.error(f"Buy falhou: {e}")
                return False

        self.pos_mgr.open(
            price=price, qty=qty, cost=cost,
            stop_loss_pct=self.stop_loss_pct,
            tier1_pct=self.profit_tier1,
            tier2_pct=self.profit_tier2,
            trail_pct=self.trailing_pct,
            direction='long', symbol=self.symbol, timeframe='5m',
        )
        q = self.quote_asset
        logger.info(
            f"{'PAPER ' if self.paper_mode else ''}BUY  "
            f"{qty:.6f} {self.base_asset} @ {price:.6f} {q}  "
            f"custo={cost:.6f} {q}"
        )
        self.trade_history.append({
            'type': 'BUY', 'price': price,
            'qty': qty, 'time': datetime.now().isoformat()
        })
        return True

    def _close_position(self, price, reason, partial_pct=1.0):
        pos = self.pos_mgr.position
        if not pos:
            return

        qty          = pos['qty'] * partial_pct
        cost_partial = pos['cost'] * partial_pct
        revenue      = qty * price * (1 - COMMISSION)
        pnl          = revenue - cost_partial

        if self.paper_mode:
            self.balance += revenue
        else:
            try:
                self.client.order_market_sell(symbol=self.symbol, quantity=round(qty, 2))
            except Exception as e:
                logger.error(f"Sell falhou: {e}")
                return

        self.daily_pnl += pnl
        q = self.quote_asset
        logger.info(
            f"{'PAPER ' if self.paper_mode else ''}SELL "
            f"{qty:.6f} {self.base_asset} @ {price:.6f} {q}  "
            f"pnl={pnl:+.6f} {q}  [{reason}]  saldo={self.balance:.6f} {q}"
        )
        self.trade_history.append({
            'type': 'SELL', 'price': price, 'qty': qty,
            'pnl': pnl, 'reason': reason,
            'time': datetime.now().isoformat()
        })

        if partial_pct < 1.0:
            self.pos_mgr.close_partial(partial_pct)
        else:
            pnl_pct = (price - pos['price']) / pos['price']
            if pnl < 0:
                self.cd_mgr.record_loss(self.symbol, pnl_pct, timeframe='5m')
            else:
                self.cd_mgr.record_win(self.symbol, timeframe='5m')
            self.pos_mgr.close_full()
            self.trade_count += 1

    def run(self):
        mode = 'PAPER' if self.paper_mode else 'REAL'
        logger.info(f"{'='*55}")
        logger.info(f"HF Bot — {self.symbol} ({self.base_asset}/{self.quote_asset}) | Modo: {mode}")
        logger.info(f"Saldo inicial: {self.balance:.6f} {self.quote_asset}")
        logger.info(f"Tier1={self.profit_tier1*100:.2f}% | Tier2={self.profit_tier2*100:.2f}% | SL={self.stop_loss_pct*100:.2f}%")
        logger.info(f"{'='*55}")

        try:
            while True:
                if time.time() - self.cycle_start > self.cycle_duration:
                    logger.info(
                        f"--- Ciclo encerrado | "
                        f"PnL=${self.daily_pnl:+.4f} | "
                        f"Trades={self.trade_count} ---"
                    )
                    self.save_state()
                    self.cycle_start  = time.time()
                    self.trade_count  = 0
                    self.daily_pnl    = 0.0

                self.cd_mgr.decay()

                enter_ok, enter_reason = self.session_mgr.should_enter()
                if not enter_ok:
                    logger.info(f"Sessão bloqueada: {enter_reason} — aguardando...")
                    time.sleep(60)
                    continue

                if self.cd_mgr.is_blocked(self.symbol):
                    logger.info("Proteção de perdas ativa — aguardando...")
                    time.sleep(10)
                    continue

                price = self.get_price()
                if not price:
                    time.sleep(5)
                    continue

                if self.pos_mgr.is_open():
                    exit_signal = self.pos_mgr.check_exit(price)
                    if exit_signal:
                        reason, fraction = exit_signal
                        self._close_position(price, reason, partial_pct=fraction)
                        if exit_signal[0] == 'tp_tier1' and self.pos_mgr.is_open():
                            self.pos_mgr.set_tier1_hit(self.pos_mgr.position['price'])
                            logger.info(f"Stop movido para break-even")
                    elif self.pos_mgr.is_open():
                        pos = self.pos_mgr.position
                        pnl_pct = (price - pos['price']) / pos['price'] * 100
                        logger.info(
                            f"P={price:.6f} | entry={pos['price']:.6f} | "
                            f"pnl={pnl_pct:+.2f}% | stop={pos['stop_price']:.6f} | "
                            f"tier1={'✓' if pos['tier1_hit'] else '…'}"
                        )

                elif self.trade_count < self.max_trades_per_cycle:
                    if not self.client:
                        time.sleep(3)
                        continue

                    vol = self.get_24h_volume()
                    if vol < self.min_24h_volume:
                        logger.info(f"Volume 24h insuficiente: ${vol:,.0f} — aguardando")
                        time.sleep(15)
                        continue

                    df = self.get_klines(limit=120)
                    if df is None or len(df) < 50:
                        time.sleep(5)
                        continue

                    signal, score, data = analyze_momentum(df, self.params)

                    logger.info(
                        f"P={price:.6f} | sig={signal} | score={score:.4f} | "
                        f"ADX={data['adx']:.1f} | RSI={data['rsi']:.0f} | "
                        f"vol_ratio={data['vol_ratio']:.1f}x"
                    )

                    if signal == 'buy' and self.balance >= 1.0:
                        order_size = position_size_kelly(self.balance, self.position_fraction, max(1, int(score * 1000)))
                        logger.info(f"Score={score:.4f} → tamanho=${order_size:.2f}")
                        self._open_position(price, order_size)

                time.sleep(3)

        except KeyboardInterrupt:
            logger.info("Bot encerrado pelo usuário")
        finally:
            self.save_state()

    def save_state(self):
        state = {
            'balance':            self.balance,
            'trade_count':        self.trade_count,
            'daily_pnl':          self.daily_pnl,
            'position':           self.pos_mgr.to_dict(),
            'history':            self.trade_history[-50:],
            'saved_at':           datetime.now().isoformat(),
        }
        state.update(self.cd_mgr.to_dict())
        with open('hf_bot_state.json', 'w') as f:
            json.dump(state, f, indent=2)


def main():
    symbol = os.getenv('BINANCE_SYMBOL', 'TRXUSDT').upper()

    quote_volume_defaults = {
        'USDT': 1_000_000, 'USDC': 1_000_000, 'BTC': 10, 'ETH': 100, 'BNB': 500,
    }
    quote = next((q for q in quote_volume_defaults if symbol.endswith(q)), 'USDT')
    min_vol = quote_volume_defaults.get(quote, 1_000_000)

    paper_balance_defaults = {'USDT': 10.0, 'USDC': 10.0, 'BTC': 0.0003, 'ETH': 0.005, 'BNB': 0.05}
    paper_balance = paper_balance_defaults.get(quote, 10.0)

    config = {
        'paper_mode':   os.getenv('PAPER_MODE', 'true').lower() != 'false',
        'symbol':       symbol,
        'api_key':      os.getenv('BINANCE_API_KEY', ''),
        'api_secret':   os.getenv('BINANCE_API_SECRET', ''),
        'position_fraction': 0.15,
        'paper_balance':     paper_balance,
        'profit_tier1':      0.005,
        'profit_tier2':      0.030,
        'stop_loss':         0.015,
        'trailing_stop_pct': 0.005,
        'max_trades_per_cycle':   3,
        'cycle_duration':         300,
        'min_24h_volume':         min_vol,
        'avoid_hours_utc':        [2, 3, 4],
        'max_consecutive_losses': 3,
        'params': {
            'c1_thresh': 0.001, 'c5_thresh': 0.002,
            'atr_mult': 2.0, 'use_ema': False,
            'rsi_max': 70, 'stoch_max': 80,
            'adx_thresh': 0,
        },
    }

    bot = HighFrequencyBot(config)
    bot.run()


if __name__ == '__main__':
    main()