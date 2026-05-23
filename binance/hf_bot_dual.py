"""
Multi-asset bot com módulos core compartilhados.
Score ranking + position sizing dinâmico + iloc[-2] + cooldown adaptativo + sessões dinâmicas.
"""
import os
import time
import math
import json
import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv

from core.indicators import analyze_momentum
from core.position import PositionManager
from core.cooldown import CooldownManager
from core.session import SessionManager
from core.sizing import position_size_kelly

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hf_bot_dual.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

COMMISSION = 0.001

UNIVERSE = [
    'TRXUSDT', 'XRPUSDT', 'DOGEUSDT', 'ADAUSDT', 'XLMUSDT',
    'DOTUSDT', 'NEARUSDT', 'FTMUSDT', 'VETUSDT',
]


class MultiAssetBot:

    def __init__(self):
        self.paper_mode = os.getenv('PAPER_MODE', 'true').lower() != 'false'

        api_key    = os.getenv('BINANCE_API_KEY', '')
        api_secret = os.getenv('BINANCE_API_SECRET', '')
        self.client = Client(api_key, api_secret) if api_key and api_secret else None

        self.symbols  = UNIVERSE[:]
        self.filters  = {}
        if self.client:
            self._load_all_filters()

        self.balance             = float(os.getenv('PAPER_BALANCE', '7.17'))
        self.trade_count         = 0
        self.daily_pnl           = 0.0
        self.cycle_start         = time.time()
        self.trade_history       = []
        self._kl_cache           = {}

        self.pos_mgr = PositionManager(commission=COMMISSION)
        self.cd_mgr  = CooldownManager(
            base_cooldown_win=30 * 60,
            base_cooldown_loss=7200,
            max_consecutive_losses=2,
            pause_cycles=2,
            adaptive=True,
        )
        self.session_mgr = SessionManager(
            active_sessions=[(0, 24)],  # 24/7 — volatilidade real define entrada
            min_vol_ratio=1.3,
        )

        self.max_trades_per_cycle = 3
        self.cycle_duration       = 300
        self.position_fraction    = 0.15

        self._load_state()

        if not self.paper_mode and self.client:
            self._sync_balance()

        logger.info(f"Saldo: {self.balance:.6f} USDT | Modo: {'REAL' if not self.paper_mode else 'PAPER'}")
        logger.info(f"Universo: {', '.join(self.symbols)}")

    def _load_state(self):
        path = 'hf_bot_dual_state.json'
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                s = json.load(f)
            saved_at = s.get('saved_at')
            if saved_at:
                age_h = (datetime.now() - datetime.fromisoformat(saved_at)).total_seconds() / 3600
                if age_h > 48:
                    logger.info(f"Estado antigo ({age_h:.1f}h) — ignorado")
                    return
            pos = s.get('position')
            if pos and pos.get('symbol'):
                self.pos_mgr.position = pos
                pos.setdefault('extreme_price', pos.get('price'))
                pos.setdefault('trail_pct', 0.015)
                pos.setdefault('entry_time', time.time())
                pos.setdefault('direction', 'long')
                pos.setdefault('timeframe', pos.get('timeframe', '5m'))
                logger.info(f"Reload: posicao {pos['symbol']} {pos['qty']} @ {pos['price']:.6f} [{pos['timeframe']}]")
            self.cd_mgr.from_dict(s)
            self.trade_history = s.get('history', [])
        except Exception as e:
            logger.error(f"Falha load_state: {e}")

    def _load_all_filters(self):
        try:
            info   = self.client.get_exchange_info()
            by_sym = {s['symbol']: s for s in info['symbols']}
            for sym in list(self.symbols):
                s = by_sym.get(sym)
                if not s:
                    logger.warning(f"{sym} nao encontrado — removido")
                    self.symbols.remove(sym)
                    continue
                step = 0.1
                min_notional = 5.0
                for f in s['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        step = float(f['stepSize'])
                    elif f['filterType'] in ('NOTIONAL', 'MIN_NOTIONAL'):
                        mn = f.get('minNotional') or f.get('notional') or '5'
                        min_notional = float(mn)
                self.filters[sym] = {
                    'step': step, 'min_notional': min_notional, 'base': s['baseAsset'],
                }
            for sym, f in self.filters.items():
                logger.info(f"  {sym}: step={f['step']} min_notional=${f['min_notional']} base={f['base']}")
        except Exception as e:
            logger.error(f"Falha carregando filtros: {e}")

    def _floor_step(self, symbol, qty):
        step = self.filters[symbol]['step']
        return math.floor(qty / step) * step

    def _get_base_free(self, symbol):
        base = self.filters[symbol]['base']
        try:
            for b in self.client.get_account()['balances']:
                if b['asset'] == base:
                    return float(b['free'])
        except Exception as e:
            logger.error(f"Falha get_base_free: {e}")
        return 0.0

    def _sync_balance(self):
        try:
            for bal in self.client.get_account()['balances']:
                if bal['asset'] == 'USDT':
                    self.balance = float(bal['free'])
                    logger.info(f"Saldo sincronizado: {self.balance:.6f} USDT")
                    return
        except Exception as e:
            logger.error(f"Falha ao sincronizar saldo: {e}")

    def get_price(self, symbol):
        if not self.client:
            return None
        try:
            return float(self.client.get_symbol_ticker(symbol=symbol)['price'])
        except:
            return None

    def get_prices_batch(self, symbols):
        if not self.client:
            return {}
        try:
            tickers = self.client.get_symbol_ticker()
            wanted  = set(symbols)
            return {t['symbol']: float(t['price']) for t in tickers if t['symbol'] in wanted}
        except Exception as e:
            logger.error(f"Falha batch price: {e}")
            return {}

    def get_klines(self, symbol, interval, limit=120, ttl=30):
        key = (symbol, interval)
        now = time.time()
        if key in self._kl_cache:
            ts, df = self._kl_cache[key]
            if now - ts < ttl:
                return df
        if not self.client:
            return None
        try:
            kl = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            df = pd.DataFrame(kl, columns=[
                'ts', 'open', 'high', 'low', 'close', 'volume',
                'close_ts', 'quote_vol', 'trades',
                'tb_base', 'tb_quote', 'ignore'
            ])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            self._kl_cache[key] = (now, df)
            return df
        except Exception as e:
            logger.debug(f"klines {symbol} {interval} fail: {e}")
            return None

    def _get_spread_bps(self, symbol, max_bps=5):
        if not self.client:
            return True
        try:
            book = self.client.get_order_book(symbol=symbol, limit=5)
            best_bid = float(book['bids'][0][0])
            best_ask = float(book['asks'][0][0])
            spread_bps = (best_ask - best_bid) / best_bid * 10000
            if spread_bps > max_bps:
                logger.info(f"Spread {symbol}: {spread_bps:.1f}bps > {max_bps}bps — skip")
                return False
            return True
        except Exception as e:
            logger.debug(f"spread check {symbol} fail: {e}")
            return True

    def _open_position(self, symbol, price, order_size, tf_label, tf_params):
        f = self.filters[symbol]
        min_order = f['min_notional'] * 1.02
        if order_size < min_order:
            order_size = min_order
        if order_size > self.balance * 0.95:
            logger.info(f"Order {order_size:.2f} excede saldo livre — skip")
            return False

        qty = self._floor_step(symbol, order_size / price)
        if qty * price < f['min_notional']:
            qty_up = qty + f['step']
            if qty_up * price * (1 + COMMISSION) <= self.balance * 0.95:
                qty = qty_up
            else:
                logger.info(f"{symbol} qty abaixo do min_notional — skip")
                return False

        cost = qty * price * (1 + COMMISSION)

        if self.paper_mode:
            self.balance -= cost
        else:
            try:
                order = self.client.order_market_buy(symbol=symbol, quantity=qty)
                if order.get('fills'):
                    price = float(order['fills'][0]['price'])
                    qty   = float(order['executedQty'])
                    cost  = float(order['cummulativeQuoteQty']) * (1 + COMMISSION)
                self.balance -= cost
            except Exception as e:
                logger.error(f"Buy {symbol} falhou: {e}")
                return False

        sl    = tf_params.get('stop_loss', 0.012)
        t1    = tf_params.get('tier1', 0.008)
        t2    = tf_params.get('tier2', 0.030)
        trail = tf_params.get('trail_pct', 0.015)

        self.pos_mgr.open(
            price=price, qty=qty, cost=cost,
            stop_loss_pct=sl, tier1_pct=t1, tier2_pct=t2,
            trail_pct=trail, direction='long', symbol=symbol, timeframe=tf_label,
        )
        logger.info(
            f"{'PAPER ' if self.paper_mode else ''}BUY  "
            f"{qty} {f['base']} @ {price:.6f} [{symbol} {tf_label}]  "
            f"custo={cost:.4f} USDT"
        )
        self.trade_history.append({
            'type': 'BUY', 'symbol': symbol, 'price': price, 'qty': qty,
            'timeframe': tf_label, 'time': datetime.now().isoformat()
        })
        return True

    def _close_position(self, price, reason, partial_pct=1.0):
        pos = self.pos_mgr.position
        if not pos:
            return

        symbol    = pos['symbol']
        f         = self.filters[symbol]
        qty_target = pos['qty'] * partial_pct
        cost_target = pos['cost'] * partial_pct

        if self.paper_mode:
            qty      = qty_target
            revenue  = qty * price * (1 - COMMISSION)
            self.balance += revenue
        else:
            base_free = self._get_base_free(symbol)
            qty = self._floor_step(symbol, min(qty_target, base_free))

            if qty * price < f['min_notional']:
                if partial_pct < 1.0:
                    qty = self._floor_step(symbol, base_free)
                    if qty * price < f['min_notional']:
                        logger.warning("Posicao muito pequena p/ parcial — mantendo")
                        return
                else:
                    logger.warning(f"Dust de {base_free} {f['base']} ficara na conta")
                    self.pos_mgr.close_full()
                    return

            try:
                order = self.client.order_market_sell(symbol=symbol, quantity=qty)
                if order.get('fills'):
                    price   = float(order['fills'][0]['price'])
                    qty     = float(order['executedQty'])
                    revenue = float(order['cummulativeQuoteQty']) * (1 - COMMISSION)
                else:
                    revenue = qty * price * (1 - COMMISSION)
                self.balance += revenue
                self._sync_balance()
            except Exception as e:
                logger.error(f"Sell {symbol} falhou: {e}")
                return

        pnl = revenue - cost_target
        self.daily_pnl += pnl
        logger.info(
            f"{'PAPER ' if self.paper_mode else ''}SELL "
            f"{qty} {f['base']} @ {price:.6f} [{symbol}]  "
            f"pnl={pnl:+.4f} USDT [{reason} {pos['timeframe']}]  saldo={self.balance:.4f}"
        )
        self.trade_history.append({
            'type': 'SELL', 'symbol': symbol, 'price': price, 'qty': qty,
            'pnl': pnl, 'reason': reason,
            'timeframe': pos['timeframe'], 'time': datetime.now().isoformat()
        })

        if partial_pct < 1.0:
            self.pos_mgr.close_partial(partial_pct, closed_qty=qty)
        else:
            pnl_pct = (price - pos['price']) / pos['price']
            tf      = pos.get('timeframe', '5m')
            if pnl < 0:
                self.cd_mgr.record_loss(symbol, pnl_pct, timeframe=tf)
            else:
                self.cd_mgr.record_win(symbol, timeframe=tf)
            self.pos_mgr.close_full()
            self.trade_count += 1

    def run(self):
        params_15m = {
            'c1_thresh': 0.0003, 'c5_thresh': 0.0005,
            'atr_mult': 3.0, 'use_ema': False,
            'tier1': 0.008, 'tier2': 0.030, 'stop_loss': 0.012,
            'trail_pct': 0.015,
            'rsi_max': 70, 'stoch_max': 80,
            'vol_min_ratio': 1.0,
        }
        params_5m = {
            'c1_thresh': 0.0005, 'c5_thresh': 0.001,
            'atr_mult': 3.0, 'use_ema': True,
            'tier1': 0.008, 'tier2': 0.030, 'stop_loss': 0.012,
            'trail_pct': 0.012,
            'rsi_max': 70, 'stoch_max': 80,
            'vol_min_ratio': 1.0,
        }
        tf_defs = [
            ('15m', Client.KLINE_INTERVAL_15MINUTE, params_15m, 2),
            ('5m',  Client.KLINE_INTERVAL_5MINUTE,  params_5m,  1),
        ]

        logger.info("=" * 60)
        logger.info(f"Multi-Asset Bot | {len(self.symbols)} pares | Modo: {'REAL' if not self.paper_mode else 'PAPER'}")
        logger.info("=" * 60)

        try:
            while True:
                if time.time() - self.cycle_start > self.cycle_duration:
                    logger.info(
                        f"--- Ciclo encerrado | PnL={self.daily_pnl:+.4f} USDT | "
                        f"Trades={self.trade_count} ---"
                    )
                    self.save_state()
                    self.cycle_start = time.time()
                    self.trade_count = 0
                    self.daily_pnl   = 0.0

                self.cd_mgr.decay()

                if self.pos_mgr.is_open():
                    sym = self.pos_mgr.position['symbol']
                    price = self.get_price(sym)
                    if price:
                        exit_sig = self.pos_mgr.check_exit(price)
                        if exit_sig:
                            reason, fraction = exit_sig
                            self._close_position(price, reason, partial_pct=fraction)
                            if exit_sig[0] == 'tp_tier1' and self.pos_mgr.is_open():
                                self.pos_mgr.set_tier1_hit(self.pos_mgr.position['price'])
                                logger.info("Stop movido p/ break-even")
                        elif self.pos_mgr.is_open():
                            pos = self.pos_mgr.position
                            pnl_pct = (price - pos['price']) / pos['price'] * 100
                            logger.info(
                                f"[{sym}] P={price:.6f} posicao aberta "
                                f"pnl={pnl_pct:+.2f}% [{pos['timeframe']}]"
                            )
                    time.sleep(5)
                    continue

                if self.cd_mgr.is_blocked('__global__'):
                    time.sleep(30)
                    continue

                if self.trade_count >= self.max_trades_per_cycle:
                    time.sleep(30)
                    continue

                prices     = self.get_prices_batch(self.symbols)
                candidates = []
                scan_log   = []

                recent_symbols = []
                for t in reversed(self.trade_history):
                    if t.get('type') == 'BUY' and t.get('symbol') not in recent_symbols:
                        recent_symbols.append(t['symbol'])
                        if len(recent_symbols) >= 3:
                            break

                for sym in self.symbols:
                    if sym not in prices:
                        continue
                    if self.cd_mgr.is_blocked(sym):
                        mins = self.cd_mgr.time_remaining(sym)
                        scan_log.append(f"{sym}:CD{mins:.0f}m")
                        continue

                    recency_mult = 1.0
                    if sym in recent_symbols:
                        recency_mult = 0.7 if recent_symbols.index(sym) == 0 else 0.85

                    best_for_sym = None
                    for tf_label, interval, params, prio in tf_defs:
                        df = self.get_klines(sym, interval, limit=120,
                                             ttl=60 if tf_label != '5m' else 30)
                        if df is None or len(df) < 25:
                            continue
                        sig, score, _ = analyze_momentum(df, params)
                        if sig == 'buy':
                            score_adj = score * recency_mult
                            cand = (prio, score_adj, sym, tf_label, params, prices[sym])
                            if best_for_sym is None or score_adj > best_for_sym[1]:
                                best_for_sym = cand

                    if best_for_sym:
                        candidates.append(best_for_sym)
                        scan_log.append(f"{sym}:{best_for_sym[3]}(s={best_for_sym[1]:.4f})")
                    else:
                        scan_log.append(f"{sym}:-")

                logger.info("scan | " + " ".join(scan_log))

                if candidates and self.balance >= min(f['min_notional'] for f in self.filters.values()):
                    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
                    _, score, sym, tf_label, params, price = candidates[0]
                    mn         = self.filters[sym]['min_notional']

                    # Position sizing dinâmico por score
                    score_int = max(1, int(score * 1000))
                    order_size = position_size_kelly(self.balance, self.position_fraction, min(score_int, 5))
                    order_size = max(order_size, mn * 1.02)

                    if self.balance >= mn:
                        if not self._get_spread_bps(sym, max_bps=5):
                            logger.info(f"Spread alto em {sym} — aguardando")
                        else:
                            logger.info(f">>> ENTRADA {sym} [{tf_label}] score={score:.4f} size=${order_size:.2f}")
                            self._open_position(sym, price, order_size, tf_label, params)

                time.sleep(5)

        except KeyboardInterrupt:
            logger.info("Bot encerrado")
        finally:
            self.save_state()

    def save_state(self):
        state = {
            'balance': self.balance,
            'trade_count': self.trade_count,
            'daily_pnl': self.daily_pnl,
            'position': self.pos_mgr.to_dict(),
            'history': self.trade_history[-50:],
            'saved_at': datetime.now().isoformat(),
        }
        state.update(self.cd_mgr.to_dict())
        with open('hf_bot_dual_state.json', 'w') as f:
            json.dump(state, f, indent=2)


if __name__ == '__main__':
    bot = MultiAssetBot()
    bot.run()