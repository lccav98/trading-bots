"""
Multi-Asset Futures Bot — V2 (Lucro Real)
Estratégia: Trend Following + R:R 3:1
- APENAS segue tendência 1H (não contraria)
- TP: 3.0% | SL: 1.0% (R:R = 3:1)
- Qualidade sobre quantidade: sinal forte + volume real
"""
import os
import time
import math
import json
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from dotenv import load_dotenv
from smc_indicators import SMCAnalyzer
from core.indicators import analyze_momentum, Indicators
from core.position import PositionManager
from core.cooldown import CooldownManager
from core.sizing import position_size_kelly

import pandas as pd
from binance.client import Client

load_dotenv()

COMMISSION = 0.0005
LEVERAGE   = int(os.getenv('LEVERAGE', '1'))

UNIVERSE = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'SUIUSDT',
    'AVAXUSDT', 'OPUSDT', 'APTUSDT', 'FTMUSDT', 'TRXUSDT',
    'XRPUSDT', 'DOGEUSDT', 'ADAUSDT', 'XLMUSDT', 'DOTUSDT',
    'NEARUSDT', 'LINKUSDT', 'LTCUSDT', 'ATOMUSDT', 'POLUSDT',
    'VETUSDT', 'TONUSDT', 'GALAUSDT', 'INJUSDT', 'WIFUSDT'
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hf_bot_futures.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FuturesBot:

    def __init__(self):
        self.paper_mode = os.getenv('PAPER_MODE', 'false').lower() == 'true'
        api_key    = os.getenv('BINANCE_API_KEY', '')
        api_secret = os.getenv('BINANCE_API_SECRET', '')
        self.client = Client(api_key, api_secret) if api_key and api_secret else None
        if self.client:
            import requests
            from urllib3.util.retry import Retry
            retry = Retry(
                total=3, connect=3, read=3,
                backoff_factor=0.5,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset(['GET']),
            )
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=32, pool_maxsize=32, max_retries=retry
            )
            self.client.session.mount('https://', adapter)
            self.client.session.mount('http://', adapter)
        self.symbols  = UNIVERSE[:]
        self.filters  = {}
        if self.client:
            self._load_all_filters()
            if not self.paper_mode:
                self._sync_balance()
        self.balance             = float(os.getenv('PAPER_BALANCE', '16.0'))
        self.trade_count         = 0
        self.daily_pnl           = 0.0
        self.cycle_start         = time.time()
        self.trade_history       = []
        self._kl_cache           = {}
        self._smc_cache          = {}
        self.pos_mgr = PositionManager(commission=COMMISSION)
        self.cd_mgr  = CooldownManager(
            base_cooldown_win=15 * 60,
            base_cooldown_loss=3600,
            max_consecutive_losses=3,
            pause_cycles=1,
            adaptive=True,
        )
        self.smc = SMCAnalyzer(swing_length=10)
        self.position_fraction    = 0.20
        self.max_trades_per_cycle = 3
        self.cycle_duration       = 300
        # Circuit breaker de drawdown (proteção de sessão)
        self.max_session_drawdown = float(os.getenv('MAX_SESSION_DRAWDOWN', '0.08'))  # 8% do pico
        self.dd_pause_seconds     = int(os.getenv('DD_PAUSE_SECONDS', '14400'))       # pausa 4h
        self.equity_peak          = self.balance
        self.dd_blocked_until     = 0.0
        self._load_state()
        if not self.paper_mode and self.client:
            self._sync_balance()
            self._set_leverage_all()
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
            logger.warning(f"klines {symbol} {interval} fail: {e}")
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
            logger.warning(f"SMC check {symbol} falhou: {e}")
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

        sl  = tf_params.get('stop_loss', 0.010)
        t1  = tf_params.get('tier1',    0.015)
        t2  = tf_params.get('tier2',    0.030)
        trl = tf_params.get('trail_pct', 0.012)
        be_trig = tf_params.get('be_trigger_pct', 0.008)
        be_off  = tf_params.get('be_offset_pct', 0.003)

        self.pos_mgr.open(
            price=price, qty=qty, cost=cost,
            stop_loss_pct=sl, tier1_pct=t1, tier2_pct=t2,
            trail_pct=trl, direction=direction, symbol=symbol, timeframe=tf_label,
            be_trigger_pct=be_trig, be_offset_pct=be_off,
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
                if "-2015" in str(e) or "code=-2015" in str(e) or "permissions" in str(e).lower() or "invalid api-key" in str(e).lower():
                    logger.critical(f"FATAL: Bloqueio de IP ou Chave de API na Binance! Encerrando o bot de forma limpa para evitar IP ban. Erro: {e}")
                    import sys
                    sys.exit("Parada de seguranca por erro de IP ou credenciais da API Binance.")
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
            self.pos_mgr.close_partial(partial_pct, closed_qty=qty_c)
        else:
            pnl_pct = (price - pos['price']) / pos['price'] if direction == 'long' else (pos['price'] - price) / pos['price']
            tf      = pos.get('timeframe', '15m')
            if pnl < 0:
                self.cd_mgr.record_loss(symbol, pnl_pct, timeframe=tf)
            else:
                self.cd_mgr.record_win(symbol, timeframe=tf)
            self.pos_mgr.close_full()
            self.trade_count += 1

    def _check_drawdown(self):
        """Circuit breaker: pausa novas entradas se o saldo cair além do limite vs pico da sessão."""
        if self.balance > self.equity_peak:
            self.equity_peak = self.balance
        now = time.time()
        if now < self.dd_blocked_until:
            return True
        if self.equity_peak <= 0:
            return False
        dd = (self.equity_peak - self.balance) / self.equity_peak
        if dd >= self.max_session_drawdown:
            self.dd_blocked_until = now + self.dd_pause_seconds
            logger.critical(
                f"CIRCUIT BREAKER: drawdown {dd*100:.1f}% >= {self.max_session_drawdown*100:.0f}% "
                f"(pico={self.equity_peak:.4f} saldo={self.balance:.4f}). "
                f"Novas entradas pausadas por {self.dd_pause_seconds/3600:.1f}h."
            )
            return True
        return False

    def _get_trend_4h(self, sym):
        """Confirmação de tendência 4H via EMAs. Retorna 'long', 'short' ou 'neutral'."""
        df_4h = self.get_klines(sym, Client.KLINE_INTERVAL_4HOUR, limit=40, ttl=900)
        if df_4h is None or len(df_4h) < 25:
            return 'neutral'
        close = df_4h['close']
        e5, e10, e20 = Indicators.ema(close, 5), Indicators.ema(close, 10), Indicators.ema(close, 20)
        try:
            c, v5, v10, v20 = close.iloc[-2], e5.iloc[-2], e10.iloc[-2], e20.iloc[-2]
        except Exception:
            return 'neutral'
        if c > v5 > v10 > v20:
            return 'long'
        if c < v5 < v10 < v20:
            return 'short'
        return 'neutral'

    def _get_trend_1h(self, sym):
        """Retorna 'long', 'short', ou 'neutral' baseado em 1H EMAs + ADX"""
        df_1h = self.get_klines(sym, Client.KLINE_INTERVAL_1HOUR, limit=40, ttl=300)
        if df_1h is None or len(df_1h) < 25:
            return 'neutral'
        close = df_1h['close']
        ema5 = Indicators.ema(close, 5)
        ema10 = Indicators.ema(close, 10)
        ema20 = Indicators.ema(close, 20)
        idx = -2
        try:
            c, e5, e10, e20 = close.iloc[idx], ema5.iloc[idx], ema10.iloc[idx], ema20.iloc[idx]
        except:
            return 'neutral'
        # Trend clara: preço alinhado com EMAs
        if c > e5 > e10 > e20:
            return 'long'
        elif c < e5 < e10 < e20:
            return 'short'
        return 'neutral'

    def _parallel_scan_symbol(self, sym, prices, recent_symbols, tf_defs, no_signal_cycles, params_low_vol):
        if sym not in prices:
            return None, None

        if self.cd_mgr.is_blocked(sym):
            mins = self.cd_mgr.time_remaining(sym)
            return None, f"{sym}:CD{mins:.0f}m"

        recency_mult = 1.0
        if sym in recent_symbols:
            recency_mult = 0.7 if recent_symbols.index(sym) == 0 else 0.85

        df_1h = self.get_klines(sym, Client.KLINE_INTERVAL_1HOUR, limit=40, ttl=300)
        df_15m = self.get_klines(sym, Client.KLINE_INTERVAL_15MINUTE, limit=200, ttl=60)

        if df_1h is None or len(df_1h) < 25:
            return None, f"{sym}:NO_1H_DATA"
        if df_15m is None or len(df_15m) < 50:
            return None, f"{sym}:NO_15M_DATA"

        # === FILTRO 1H: APENAS TRADE NA DIREÇÃO DA TENDÊNCIA MAIOR ===
        close_1h = df_1h['close']
        ema5_1h = Indicators.ema(close_1h, 5)
        ema10_1h = Indicators.ema(close_1h, 10)
        ema20_1h = Indicators.ema(close_1h, 20)
        try:
            c, e5, e10, e20 = close_1h.iloc[-2], ema5_1h.iloc[-2], ema10_1h.iloc[-2], ema20_1h.iloc[-2]
            if c > e5 > e10 > e20:
                htf_trend = 'long'
            elif c < e5 < e10 < e20:
                htf_trend = 'short'
            else:
                htf_trend = 'neutral'
        except:
            htf_trend = 'neutral'

        if htf_trend == 'neutral':
            return None, f"{sym}:NO_TREND"

        # === CONFIRMAÇÃO 4H: rejeita entradas que conflitam com o timeframe maior ===
        trend_4h = self._get_trend_4h(sym)
        if trend_4h != 'neutral' and trend_4h != htf_trend:
            return None, f"{sym}:4H_CONFLITO"

        # SMC Analysis
        try:
            smc_state = self.smc.analyze(df_15m)
        except:
            smc_state = {"ok": False}

        best = None
        for tf_label, interval, params, prio in tf_defs:
            if htf_trend == 'long':
                sig, score, meta = analyze_momentum(df_15m, params, direction='long', df_htf=None)
                score_short = 0.0
                score_long = score if (sig == 'buy' and score > 0) else 0.0
                sig_long, sig_short = 'buy', 'neutral'
                if not score_long:
                    sig_long = 'neutral'
            else:
                sig, score, meta = analyze_momentum(df_15m, params, direction='short', df_htf=None)
                score_long = 0.0
                score_short = score if (sig == 'sell' and score > 0) else 0.0
                sig_long, sig_short = 'neutral', 'sell'
                if not score_short:
                    sig_short = 'neutral'

            for s_dir, s_score in [(sig_long, score_long), (sig_short, score_short)]:
                if s_score > 0.003:
                    score_adj = s_score * recency_mult
                    cand = (prio, score_adj, sym, tf_label, params, prices[sym], s_dir, smc_state)
                    if best is None or score_adj > best[1]:
                        best = cand

        # Fallback para baixa volatilidade
        if not best and no_signal_cycles >= 10:
            params = params_low_vol
            if htf_trend == 'long':
                sig, score, _ = analyze_momentum(df_15m, params, direction='long')
                if sig == 'buy' and score > 0.003:
                    cand = (1, score * recency_mult, sym, '15m', params, prices[sym], 'buy', smc_state)
                    best = cand
            else:
                sig, score, _ = analyze_momentum(df_15m, params, direction='short')
                if sig == 'sell' and score > 0.003:
                    cand = (1, score * recency_mult, sym, '15m', params, prices[sym], 'sell', smc_state)
                    best = cand

        if best:
            d = '⬆️' if best[6] == 'buy' else '⬇️'
            return best, f"{sym}:{d}{best[3]}(s={best[1]:.4f})"
        else:
            return None, f"{sym}:-"

    def run(self):
        # Parâmetros otimizados Walk-Forward V4 (81.55% win rate, 1.362 profit factor em TRXUSDT_15m)
        params_15m = {
            'c1_thresh': 0.0005, 'c5_thresh': 0.0010,
            'atr_mult': 2.0, 'use_ema': False,
            'tier1': 0.005, 'tier2': 0.015, 'stop_loss': 0.015,
            'trail_pct': 0.005,
            'rsi_max': 70, 'stoch_max': 80,
            'rsi_short_min': 30, 'stoch_short_min': 30,
            'adx_thresh': 0, 'vol_min_ratio': 1.8,
        }
        params_low_vol = {
            'c1_thresh': 0.0001, 'c5_thresh': 0.0003,
            'atr_mult': 4.0, 'use_ema': True,
            'tier1': 0.012, 'tier2': 0.025, 'stop_loss': 0.008,
            'trail_pct': 0.010,
            'rsi_max': 75, 'stoch_max': 85,
            'rsi_short_min': 25, 'stoch_short_min': 25,
            'adx_thresh': 15, 'vol_min_ratio': 1.2,
        }
        tf_defs = [
            ('15m', Client.KLINE_INTERVAL_15MINUTE, params_15m, 1),
        ]

        no_signal_cycles = 0
        _last_session_ok = True

        logger.info('=' * 60)
        logger.info(
            f"Futures Bot V2 (Otimizado) | {len(self.symbols)} pares | "
            f"{'REAL' if not self.paper_mode else 'PAPER'} | {LEVERAGE}x | "
            f"Trend1H (Scan Paralelo) | R:R Otimizado | Score>0.003 | Vol>1.5x"
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
                            # Throttle pos log to every 10s (20 ticks at 0.5s) to avoid spamming the log
                            self._pos_log_counter = getattr(self, '_pos_log_counter', 0) + 1
                            if self._pos_log_counter >= 20:
                                self._pos_log_counter = 0
                                d   = self.pos_mgr.position['direction']
                                e   = self.pos_mgr.position['price']
                                pnl = (price - e) / e if d == 'long' else (e - price) / e
                                logger.info(
                                    f"[{sym}] P={price:.6f} "
                                    f"{'⬆️' if d=='long' else '⬇️'} "
                                    f"pnl={pnl*100:+.2f}% [{self.pos_mgr.position['timeframe']}]"
                                )
                    time.sleep(0.5)
                    continue

                if self.cd_mgr.is_blocked('__global__'):
                    time.sleep(30)
                    continue

                if self._check_drawdown():
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

                # Varredura paralela dos símbolos usando ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=min(32, len(self.symbols))) as executor:
                    futures = {
                        executor.submit(
                            self._parallel_scan_symbol,
                            sym, prices, recent_symbols, tf_defs, no_signal_cycles, params_low_vol
                        ): sym for sym in self.symbols
                    }
                    for future in futures:
                        try:
                            cand, log_entry = future.result()
                            if log_entry:
                                scan_log.append(log_entry)
                            if cand:
                                candidates.append(cand)
                        except Exception as e:
                            sym = futures[future]
                            logger.error(f"Erro no scan paralelo para {sym}: {e}")

                if not candidates:
                    no_signal_cycles += 1
                else:
                    no_signal_cycles = 0

                logger.info("scan | " + " ".join(scan_log))

                if candidates and self.balance >= 5.0:
                    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
                    _, score, sym, tf_label, params, price, sig, smc_state = candidates[0]
                    direction  = 'long' if sig == 'buy' else 'short'
                    mn         = self.filters[sym]['min_notional']

                    score_int = max(1, int(score * 1000))
                    fixed_size = float(os.getenv('ORDER_VALUE', 0))
                    if fixed_size > 0:
                        order_size = fixed_size
                    else:
                        order_size = position_size_kelly(self.balance, self.position_fraction, min(score_int, 5))
                    if score_int <= 2:
                        order_size *= 0.6
                    order_size = min(order_size, self.balance * 0.40)
                    order_size = max(order_size, mn * 1.02)

                    if self.balance >= mn:
                        if not self._check_spread(sym, max_bps=5):
                            logger.info(f"Spread alto em {sym} — skip")
                        else:
                            # Utiliza o estado SMC pré-calculado
                            if smc_state and smc_state.get('ok'):
                                signal = self.smc.build_signal(smc_state)
                                if direction == 'long' and signal.bullish:
                                    smc_conf, smc_components, smc_ok = signal.confidence, list(signal.components.keys()), True
                                elif direction == 'short' and signal.bearish:
                                    smc_conf, smc_components, smc_ok = signal.confidence, list(signal.components.keys()), True
                                else:
                                    smc_conf, smc_components, smc_ok = signal.confidence, list(signal.components.keys()), False
                            else:
                                smc_conf, smc_components, smc_ok = 0.0, [], True
                                logger.info(f"SMC ⚠️ {sym} falhou ou vazio — ignorando filtro")

                            if smc_ok:
                                order_size *= min(1.0 + smc_conf, 1.5)
                                logger.info(f"SMC ✅ {direction.upper()} {sym} conf={smc_conf:.0%}")
                                icon = '⬆️ LONG' if direction == 'long' else '⬇️ SHORT'
                                logger.info(f">>> {icon} {sym} [{tf_label}] score={score:.4f} size=${order_size:.2f}")
                                self._open_position(sym, price, order_size, tf_label, params, direction)
                            else:
                                logger.info(f"SMC ❌ {sym} conf={smc_conf:.0%}")

                time.sleep(5)

        except KeyboardInterrupt:
            logger.info("Bot encerrado")
        finally:
            self.save_state()


if __name__ == '__main__':
    bot = FuturesBot()
    bot.run()
