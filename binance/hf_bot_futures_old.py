"""
Multi-Asset Futures Bot — Dual Direction (Long/Short)
Binance USDT-M Perpetual Futures | 1x leverage default
Fees: 0.05% taker (vs 0.10% Spot) → round-trip ~0.25%

Refactored: core modules + iloc[-2] + Kelly sizing + SMC scoring integration
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
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from dotenv import load_dotenv
from smc_indicators import SMCAnalyzer, TrendBias

from core.indicators import analyze_momentum, check_mtf_trend, Indicators
from core.position import PositionManager
from core.cooldown import CooldownManager
from core.session import SessionManager
from core.sizing import position_size_kelly

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hf_bot_futures.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

COMMISSION = 0.0005
LEVERAGE   = 1

UNIVERSE = [
    'TRXUSDT', 'XRPUSDT', 'DOGEUSDT', 'ADAUSDT', 'XLMUSDT',
    'DOTUSDT', 'NEARUSDT', 'SONICUSDT', 'VETUSDT',
    'LINKUSDT', 'AVAXUSDT', 'LTCUSDT', 'ATOMUSDT', 'POLUSDT',
]


class FuturesBot:

    def __init__(self):
        self.paper_mode = os.getenv('PAPER_MODE', 'true').lower() != 'false'

        api_key    = os.getenv('BINANCE_API_KEY', '')
        api_secret = os.getenv('BINANCE_API_SECRET', '')
        self.client = Client(api_key, api_secret) if api_key and api_secret else None

        self.symbols  = UNIVERSE[:]
        self.filters  = {}
        if self.client:
            self._load_all_filters()
            if not self.paper_mode:
                self._set_leverage_all()

        self.balance             = float(os.getenv('PAPER_BALANCE', '100.0'))
        self.trade_count         = 0
        self.daily_pnl           = 0.0
        self.cycle_start         = time.time()
        self.trade_history       = []
        self._kl_cache = {}
        self._smc_cache = {}

        self.pos_mgr = PositionManager(commission=COMMISSION)
        self.cd_mgr  = CooldownManager(
            base_cooldown_win=15 * 60,
            base_cooldown_loss=3600,
            max_consecutive_losses=3,
            pause_cycles=1,
            adaptive=True,
        )
        self.session_mgr = SessionManager(
            active_sessions=[(7, 19), (13, 22)],
            min_vol_ratio=1.2,
        )

        self.smc = SMCAnalyzer(swing_length=10)
        self.position_fraction    = 0.15
        self.max_trades_per_cycle = 3
        self.cycle_duration       = 300

        self._load_state()

        if not self.paper_mode and self.client:
            self._sync_balance()

        logger.info(
            f"Saldo: {self.balance:.4f} USDT | "
            f"Modo: {'REAL' if not self.paper_mode else 'PAPER'} | "
            f"Leverage: {LEVERAGE}x | Fee/lado: {COMMISSION*100:.3f}%"
        )
        logger.info(f"Universo: {', '.join(self.symbols)}")

    def _load_state(self):
        path = 'hf_bot_futures_state.json'
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
                pos.setdefault('extreme_price', pos.get('price'))
                pos.setdefault('trail_pct', 0.015)
                pos.setdefault('entry_time', time.time())
                pos.setdefault('direction', 'long')
                pos.setdefault('timeframe', pos.get('timeframe', '15m'))
                self.pos_mgr.position = pos
                logger.info(
                    f"Reload: {pos['direction'].upper()} {pos['symbol']} "
                    f"{pos['qty']} @ {pos['price']:.6f} [{pos['timeframe']}]"
                )
            self.cd_mgr.from_dict(s)
            self.trade_history = s.get('history', [])
        except Exception as e:
            logger.error(f"Falha load_state: {e}")

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
        with open('hf_bot_futures_state.json', 'w') as f:
            json.dump(state, f, indent=2)

    def _load_all_filters(self):
        try:
            info   = self.client.futures_exchange_info()
            by_sym = {s['symbol']: s for s in info['symbols']}
            for sym in list(self.symbols):
                s = by_sym.get(sym)
                if not s:
                    logger.warning(f"{sym} não encontrado em Futures — removido")
                    self.symbols.remove(sym)
                    continue
                step         = 1.0
                min_notional = 5.0
                for f in s['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        step = float(f['stepSize'])
                    elif f['filterType'] in ('MIN_NOTIONAL', 'NOTIONAL'):
                        mn = f.get('notional') or f.get('minNotional') or '5'
                        min_notional = float(mn)
                self.filters[sym] = {'step': step, 'min_notional': min_notional}
            for sym, f in self.filters.items():
                logger.info(f"  {sym}: step={f['step']} min_notional=${f['min_notional']}")
        except Exception as e:
            logger.error(f"Falha filtros Futures: {e}")
            for sym in self.symbols:
                self.filters.setdefault(sym, {'step': 1.0, 'min_notional': 5.0})

    def _set_leverage_all(self):
        for sym in self.symbols:
            try:
                self.client.futures_change_leverage(symbol=sym, leverage=LEVERAGE)
            except Exception as e:
                logger.warning(f"  {sym} leverage fail: {e}")

    def _floor_step(self, symbol, qty):
        step = self.filters[symbol]['step']
        return math.floor(qty / step) * step

    def _sync_balance(self):
        try:
            for b in self.client.futures_account_balance():
                if b['asset'] == 'USDT':
                    self.balance = float(b['availableBalance'])
                    logger.info(f"Saldo Futures: {self.balance:.4f} USDT")
                    return
        except Exception as e:
            logger.error(f"Falha sync balance: {e}")

    def get_price(self, symbol):
        if not self.client:
            return None
        try:
            return float(self.client.futures_symbol_ticker(symbol=symbol)['price'])
        except:
            return None

    def get_prices_batch(self, symbols):
        if not self.client:
            return {}
        try:
            tickers = self.client.futures_symbol_ticker()
            wanted  = set(symbols)
            return {t['symbol']: float(t['price']) for t in tickers if t['symbol'] in wanted}
        except Exception as e:
            logger.error(f"Falha batch price: {e}")
            return {}

    def get_klines(self, symbol, interval, limit=120, ttl=15):
        key = (symbol, interval)
        now = time.time()
        if key in self._kl_cache:
            ts, df = self._kl_cache[key]
            if now - ts < ttl:
                return df
        if not self.client:
            return None
        try:
            kl = self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)
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

    def _smc_score(self, symbol, direction):
        now = time.time()
        cache_key = (symbol, direction)
        if cache_key in self._smc_cache:
            ts, result = self._smc_cache[cache_key]
            if now - ts < 120:
                return result

        try:
            kl = self.client.futures_klines(symbol=symbol,
                                             interval=Client.KLINE_INTERVAL_15MINUTE,
                                             limit=200)
            df = pd.DataFrame(kl, columns=[
                'ts','open','high','low','close','volume',
                'close_ts','quote_vol','trades','tb_base','tb_quote','ignore'
            ])
            for col in ['open','high','low','close','volume']:
                df[col] = df[col].astype(float)

            state  = self.smc.analyze(df)
            signal = self.smc.build_signal(state)

            if direction == 'long' and signal.bullish:
                result = (signal.confidence, list(signal.components.keys()), True)
            elif direction == 'short' and signal.bearish:
                result = (signal.confidence, list(signal.components.keys()), True)
            else:
                result = (signal.confidence, list(signal.components.keys()), False)

            self._smc_cache[cache_key] = (now, result)
            return result
        except Exception as e:
            logger.debug(f"SMC check {symbol} falhou: {e}")
            return 0.0, [], True

    def _check_spread(self, symbol, max_bps=5):
        if not self.client:
            return True
        try:
            book      = self.client.futures_order_book(symbol=symbol, limit=5)
            best_bid  = float(book['bids'][0][0])
            best_ask  = float(book['asks'][0][0])
            spread    = (best_ask - best_bid) / best_bid * 10000
            if spread > max_bps:
                logger.info(f"Spread {symbol}: {spread:.1f}bps — skip")
                return False
            return True
        except:
            return True

    def _open_position(self, symbol, price, order_size, tf_label, tf_params, direction='long'):
        f            = self.filters[symbol]
        min_order    = f['min_notional'] * 1.02
        if order_size < min_order:
            order_size = min_order
        if order_size > self.balance * 0.95:
            logger.info(f"Order {order_size:.2f} excede saldo — skip")
            return False

        qty = self._floor_step(symbol, order_size / price)
        if qty * price < f['min_notional']:
            qty_up = qty + f['step']
            if qty_up * price * (1 + COMMISSION) <= self.balance * 0.95:
                qty = qty_up
            else:
                logger.info(f"{symbol} qty abaixo do min_notional — skip")
                return False

        notional = qty * price
        cost     = notional * (1 + COMMISSION)

        if self.paper_mode:
            self.balance -= cost
        else:
            try:
                side  = SIDE_BUY if direction == 'long' else SIDE_SELL
                order = self.client.futures_create_order(
                    symbol=symbol, side=side,
                    type=ORDER_TYPE_MARKET, quantity=qty
                )
                if order.get('fills'):
                    price    = float(order['fills'][0]['price'])
                    qty      = float(order['executedQty'])
                    notional = qty * price
                cost = notional * COMMISSION
                self.balance -= cost
            except Exception as e:
                logger.error(f"Futures open {direction} {symbol} falhou: {e}")
                return False

        sl  = tf_params.get('stop_loss', 0.008)
        t1  = tf_params.get('tier1',    0.010)
        t2  = tf_params.get('tier2',    0.030)
        trl = tf_params.get('trail_pct', 0.012)

        self.pos_mgr.open(
            price=price, qty=qty, cost=cost,
            stop_loss_pct=sl, tier1_pct=t1, tier2_pct=t2,
            trail_pct=trl, direction=direction, symbol=symbol, timeframe=tf_label,
        )

        icon = '⬆️ LONG' if direction == 'long' else '⬇️ SHORT'
        logger.info(
            f"{'PAPER ' if self.paper_mode else ''}{icon}  "
            f"{qty} {symbol} @ {price:.6f} [{tf_label}]  "
            f"notional={notional:.2f} USDT  stop={self.pos_mgr.position['stop_price']:.6f}"
        )
        self.trade_history.append({
            'type': direction.upper(), 'symbol': symbol, 'price': price,
            'qty': qty, 'timeframe': tf_label, 'time': datetime.now().isoformat()
        })
        return True

    def _close_position(self, price, reason, partial_pct=1.0):
        pos = self.pos_mgr.position
        if not pos:
            return

        symbol    = pos['symbol']
        direction = pos.get('direction', 'long')
        qty_c     = self._floor_step(symbol, pos['qty'] * partial_pct)

        if self.paper_mode:
            notional_c = pos['price'] * qty_c
            if direction == 'long':
                pnl = (price - pos['price']) * qty_c - 2 * COMMISSION * notional_c
            else:
                pnl = (pos['price'] - price) * qty_c - 2 * COMMISSION * notional_c
            self.balance += notional_c + pnl
        else:
            try:
                close_side = SIDE_SELL if direction == 'long' else SIDE_BUY
                order = self.client.futures_create_order(
                    symbol=symbol, side=close_side,
                    type=ORDER_TYPE_MARKET, quantity=qty_c,
                    reduceOnly=True
                )
                if order.get('fills'):
                    price = float(order['fills'][0]['price'])
                    qty_c = float(order['executedQty'])
                notional_c = pos['price'] * qty_c
                if direction == 'long':
                    pnl = (price - pos['price']) * qty_c - 2 * COMMISSION * notional_c
                else:
                    pnl = (pos['price'] - price) * qty_c - 2 * COMMISSION * notional_c
                self.balance += notional_c + pnl
                self._sync_balance()
            except Exception as e:
                logger.error(f"Futures close {symbol} falhou: {e}")
                return

        self.daily_pnl += pnl
        icon = '⬆️' if direction == 'long' else '⬇️'
        logger.info(
            f"{'PAPER ' if self.paper_mode else ''}{icon} CLOSE "
            f"{qty_c} {symbol} @ {price:.6f}  "
            f"pnl={pnl:+.4f} USDT [{reason} {pos['timeframe']}]  "
            f"saldo={self.balance:.4f}"
        )
        self.trade_history.append({
            'type': 'CLOSE', 'symbol': symbol, 'direction': direction,
            'price': price, 'qty': qty_c, 'pnl': pnl, 'reason': reason,
            'timeframe': pos['timeframe'], 'time': datetime.now().isoformat()
        })

        if partial_pct < 1.0:
            self.pos_mgr.close_partial(partial_pct)
        else:
            pnl_pct = (price - pos['price']) / pos['price'] if direction == 'long' else (pos['price'] - price) / pos['price']
            tf      = pos.get('timeframe', '15m')
            if pnl < 0:
                self.cd_mgr.record_loss(symbol, pnl_pct, timeframe=tf)
            else:
                self.cd_mgr.record_win(symbol, timeframe=tf)
            self.pos_mgr.close_full()
            self.trade_count += 1

    def _get_atr_mult_for_symbol(self, symbol):
        df = self.get_klines(symbol, Client.KLINE_INTERVAL_15MINUTE, limit=40, ttl=30)
        if df is None or len(df) < 20:
            return 1.0
        tr = pd.concat([df['high'] - df['low'],
                        (df['high'] - df['close'].shift()).abs(),
                        (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(7).mean().iloc[-1]
        avg = tr.rolling(50).mean().iloc[-1]
        if np.isnan(atr) or np.isnan(avg) or avg <= 0:
            return 1.0
        return atr / avg

    def _fallback_range_trade(self, prices):
        """Scalping em range quando o mercado está plano — captura micro-oscilações."""
        eligible = [s for s in self.symbols if self.filters.get(s, {}).get('min_notional', 999) <= 5.0]
        if not eligible:
            return

        candidates = []
        for sym in eligible:
            if sym not in prices or self.cd_mgr.is_blocked(sym):
                continue
            df = self.get_klines(sym, Client.KLINE_INTERVAL_15MINUTE, limit=40, ttl=30)
            if df is None or len(df) < 20:
                continue

            high = df['high'].max()
            low  = df['low'].min()
            close = df['close'].iloc[-1]
            range_val = (high - low) / close

            if range_val < 0.001:
                continue

            pos_in_range = (close - low) / (high - low)
            # Só entra se o preço estiver próximo de um extremo (bottom 20% ou top 20%)
            if pos_in_range < 0.2 or pos_in_range > 0.8:
                candidates.append((range_val, pos_in_range, sym, prices[sym], high, low, close))

        if not candidates:
            return

        candidates.sort(reverse=True)
        _, pos_in_range, sym, price, range_high, range_low, _ = candidates[0]
        direction = 'long' if pos_in_range < 0.2 else 'short'

        mn = self.filters[sym]['min_notional']
        order_size = min(self.balance * 0.5, self.balance * 0.95)
        if order_size < mn:
            return

        # TP no centro do range (~50% do caminho), SL fora do range
        if direction == 'long':
            tp_target = (price + range_high) / 2
            sl_target = range_low * 0.995
        else:
            tp_target = (price + range_low) / 2
            sl_target = range_high * 1.005

        tp_pct = abs((tp_target - price) / price)
        sl_pct = abs((sl_target - price) / price)

        if tp_pct < 0.003 or sl_pct < 0.002:
            return

        params = {
            'c1_thresh': 0, 'c5_thresh': 0, 'atr_mult': 100, 'use_ema': False,
            'stop_loss': sl_pct,
            'tier1': tp_pct * 0.5,
            'tier2': tp_pct,
            'trail_pct': 0,
        }

        icon = '⬆️ LONG' if direction == 'long' else '⬇️ SHORT'
        logger.info(
            f">>> FALLBACK {icon} {sym} @ {price:.6f} "
            f"(range: {range_low:.6f}-{range_high:.6f}) "
            f"TP~{tp_pct:.2%} SL~{sl_pct:.2%}"
        )
        self._open_position(sym, price, order_size, '15m', params, direction)

    def run(self):
        # Params principais (15m) e fallback
        params_15m = {
            'c1_thresh': 0.0002, 'c5_thresh': 0.0005,
            'atr_mult': 4.0, 'use_ema': False,
            'tier1': 0.012, 'tier2': 0.025, 'stop_loss': 0.015,
            'trail_pct': 0.010,
            'rsi_max': 78, 'stoch_max': 88,
            'rsi_short_min': 25, 'stoch_short_min': 25,
            'adx_thresh': 12, 'vol_min_ratio': 0.7,
        }
        params_low_vol = {
            'c1_thresh': 0.0001, 'c5_thresh': 0.0002,
            'atr_mult': 5.0, 'use_ema': False,
            'tier1': 0.010, 'tier2': 0.020, 'stop_loss': 0.012,
            'trail_pct': 0.008,
            'rsi_max': 82, 'stoch_max': 92,
            'rsi_short_min': 20, 'stoch_short_min': 20,
            'adx_thresh': 8, 'vol_min_ratio': 0.5,
        }
        tf_defs = [
            ('15m', Client.KLINE_INTERVAL_15MINUTE, params_15m, 1),
        ]

        no_signal_cycles = 0
        _last_session_ok = True

        logger.info('=' * 60)
        logger.info(
            f"Futures Bot | {len(self.symbols)} pares | "
            f"{'REAL' if not self.paper_mode else 'PAPER'} | {LEVERAGE}x | "
            f"Long+Short | Kelly sizing | SMC scoring | "
            f"MTF 15m+5m | Session filter | BB squeeze"
        )
        logger.info('=' * 60)

        try:
            while True:
                now = time.time()
                if now - self.cycle_start > self.cycle_duration:
                    logger.info(
                        f"--- Ciclo | PnL={self.daily_pnl:+.4f} USDT | "
                        f"Trades={self.trade_count} ---"
                    )
                    self.save_state()
                    self.cycle_start = time.time()
                    self.trade_count = 0
                    self.daily_pnl   = 0.0

                self.cd_mgr.decay()

                # Session filter
                session_ok, session_msg = self.session_mgr.should_enter()
                if not session_ok and session_msg == 'fora de sessao':
                    if _last_session_ok:
                        logger.info(f"Sessao fechada ({session_msg}) — scan reduzido")
                        _last_session_ok = False
                if not session_ok:
                    time.sleep(60)
                    continue
                _last_session_ok = True

                if self.pos_mgr.is_open():
                    sym   = self.pos_mgr.position['symbol']
                    price = self.get_price(sym)
                    if price:
                        exit_sig = self.pos_mgr.check_exit(price)
                        if exit_sig:
                            reason, fraction = exit_sig
                            self._close_position(price, reason, partial_pct=fraction)
                            if exit_sig[0] == 'tp_tier1' and self.pos_mgr.is_open():
                                self.pos_mgr.set_tier1_hit(self.pos_mgr.position['price'])
                                logger.info("Stop movido para break-even")
                        elif self.pos_mgr.is_open():
                            d   = self.pos_mgr.position['direction']
                            e   = self.pos_mgr.position['price']
                            pnl = (price - e) / e if d == 'long' else (e - price) / e
                            logger.info(
                                f"[{sym}] P={price:.6f} "
                                f"{'⬆️' if d=='long' else '⬇️'} "
                                f"pnl={pnl*100:+.2f}% [{self.pos_mgr.position['timeframe']}]"
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
                    if t.get('symbol') not in recent_symbols:
                        recent_symbols.append(t.get('symbol'))
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

                    best = None
                    for tf_label, interval, params, prio in tf_defs:
                        # Busca multi-timeframe: 15m principal + 5m de confirmação
                        df_15m = self.get_klines(sym, interval, limit=120, ttl=60)
                        df_5m  = self.get_klines(sym, Client.KLINE_INTERVAL_5MINUTE, limit=120, ttl=60)
                        if df_15m is None or len(df_15m) < 25:
                            continue

                        sig_long, score_long, meta_l = analyze_momentum(df_15m, params, direction='long', df_htf=df_5m)
                        sig_short, score_short, meta_s = analyze_momentum(df_15m, params, direction='short', df_htf=df_5m)

                        # Bônus BB squeeze: recompensa trade quando expanção vem após squeeze
                        if meta_l.get('squeeze') or meta_l.get('bb_width', 0) < 0.02:
                            if sig_long != 'neutral':
                                score_long *= 1.1
                        if meta_s.get('squeeze') or meta_s.get('bb_width', 0) < 0.02:
                            if sig_short != 'neutral':
                                score_short *= 1.1

                        for sig, score in [('buy', score_long), ('sell', score_short)]:
                            if sig in ('buy', 'sell') and score > 0:
                                score_adj = score * recency_mult
                                cand = (prio, score_adj, sym, tf_label, params, prices[sym], sig)
                                if best is None or score_adj > best[1]:
                                    best = cand

                    if best:
                        candidates.append(best)
                        d = '⬆️' if best[6] == 'buy' else '⬇️'
                        scan_log.append(f"{sym}:{d}{best[3]}(s={best[1]:.4f})")
                    else:
                        scan_log.append(f"{sym}:-")

                # Fallback: 4+ ciclos sem sinal + BB squeeze estende para 6
                if not candidates:
                    no_signal_cycles += 1
                else:
                    no_signal_cycles = 0

                use_fallback = no_signal_cycles >= 4
                if not candidates and use_fallback:
                    logger.info(f"⚠️ Fallback após {no_signal_cycles} ciclos — BB squeeze/lowvol")
                    for sym in self.symbols:
                        if sym not in prices:
                            continue
                        if self.cd_mgr.is_blocked(sym):
                            continue

                        recency_mult = 1.0
                        if sym in recent_symbols:
                            recency_mult = 0.7 if recent_symbols.index(sym) == 0 else 0.85

                        df = self.get_klines(sym, Client.KLINE_INTERVAL_15MINUTE, limit=120, ttl=60)
                        if df is None or len(df) < 25:
                            continue

                        # Detecta squeeze para favorecer a expansão
                        squeeze, bb_width, bb_upper, bb_lower, bb_mid = Indicators.bb_squeeze(df['close'])
                        squeeze_active = bool(squeeze.iloc[-2]) if not pd.isna(squeeze.iloc[-2]) else False

                        sig_long, score_long, _ = analyze_momentum(df, params_low_vol, direction='long')
                        sig_short, score_short, _ = analyze_momentum(df, params_low_vol, direction='short')

                        for sig, score in [('buy', score_long), ('sell', score_short)]:
                            if sig in ('buy', 'sell') and score > 0:
                                if squeeze_active:
                                    score *= 1.25
                                score_adj = score * recency_mult
                                cand = (1, score_adj, sym, '15m', params_low_vol, prices[sym], sig)
                                candidates.append(cand)
                                scan_log.append(f"{sym}:FB{s}={score:.4f}")
                                break
                    no_signal_cycles = 0

                logger.info("scan | " + " ".join(scan_log))

                if candidates and self.balance >= 5.0:
                    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
                    _, score, sym, tf_label, params, price, sig = candidates[0]
                    direction  = 'long' if sig == 'buy' else 'short'
                    mn         = self.filters[sym]['min_notional']

                    # Calcula atr_mult para pos sizing/pause adaptativo
                    atr_mult_val = self._get_atr_mult_for_symbol(sym) if hasattr(self, '_get_atr_mult_for_symbol') else 1.0

                    score_int = max(1, int(score * 1000))
                    order_size = position_size_kelly(self.balance, self.position_fraction, min(score_int, 5))
                    if score_int <= 2:
                        order_size *= 0.6
                    # Aplicar limites sem permitir order > balance*0.5 superar saldo min
                    order_size = min(order_size, self.balance * 0.40)
                    order_size = max(order_size, mn * 1.02)

                    if self.balance >= mn:
                        if not self._check_spread(sym, max_bps=10):
                            logger.info(f"Spread alto em {sym} — skip")
                        else:
                            smc_conf, smc_components, smc_ok = self._smc_score(sym, direction)
                            if smc_ok:
                                order_size *= min(1.0 + smc_conf, 1.5)
                                logger.info(
                                    f"SMC ✅ {direction.upper()} {sym} "
                                    f"conf={smc_conf:.0%} components={smc_components}"
                                )
                            else:
                                logger.info(
                                    f"SMC ❌ {sym} conf={smc_conf:.0%} — "
                                    f"size reduzido. components={smc_components}"
                                )

                            icon = '⬆️ LONG' if direction == 'long' else '⬇️ SHORT'
                            logger.info(f">>> {icon} {sym} [{tf_label}] score={score:.4f} size=${order_size:.2f}")
                            self._open_position(sym, price, order_size, tf_label, params, direction)

                time.sleep(5)

        except KeyboardInterrupt:
            logger.info("Bot encerrado")
        finally:
            self.save_state()


if __name__ == '__main__':
    bot = FuturesBot()
    bot.run()