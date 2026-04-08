"""
main.py — Apex Claude Trader v3 (MODO SINAIS)

Bot analisa o mercado e gera sinais claros com entry/SL/TP/contratos/R/R.
O usuário opera manualmente no site da Tradovate.

Mantém: auth, market data, risk, estratégias, adaptive threshold,
news filter, volatility detection, recovery, trading journal.
"""

import asyncio
import logging
import os
import signal
import time
import json
import sys
import winsound
from datetime import datetime

from core.auth       import TradovateAuth
from core.market_data import MarketDataFeed
from core.risk       import RiskManager
from core.recovery   import RecoveryState
from core.executor   import OrderExecutor
from core.simulator  import TradeSimulator
from core.dashboard  import start_dashboard, update_state
from skills.strategy import generate_signal, atr as calc_atr
from skills.adaptive_threshold import AdaptiveThreshold
from config.settings import SYMBOL, TIMEFRAME_MINUTES, MIN_SCORE_TO_TRADE, AUTO_EXECUTE_TRADES, DEMO_SIMULATION
from config.settings import POSITION_SIZE, MAX_DAILY_LOSS, MAX_DRAWDOWN, MAX_CONSECUTIVE_LOSSES

# NT8 ATI OIF Bridge - Enviar ordens para NT8 automaticamente
# O arquivo nt8_ati_bridge.py deve estar na mesma pasta
try:
    from nt8_ati_bridge import send_oif_order, cancel_all_orders, flatten_everything
    NT8_ATI_AVAILABLE = True
    print("[NT8] ATI OIF Bridge loaded - orders will be sent to NT8")
except ImportError:
    NT8_ATI_AVAILABLE = False
    print("[NT8] ATI OIF Bridge not available - using fallback")

# Prophet AI Forecasting - Lightweight, works on regular PCs
try:
    from prophet_integration import load_prophet, get_trend_direction
    PROPHET_AVAILABLE = True
    load_prophet()
except ImportError:
    PROPHET_AVAILABLE = False
    print("[Prophet] Not available - using traditional indicators only")

# ─────────────────────────────────────────────
# LOGGING — UTF-8 para Windows console
# ─────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)
if sys.stderr.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/trader.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# SINAL SONORO
# ─────────────────────────────────────────────
def play_alert_sound(action="BUY"):
    """Toca som diferenciado: COMPRA=ascendente, VENDA=descendente."""
    try:
        if action == "BUY":
            # Compra: bips ascendentes (tom subindo)
            winsound.Beep(800, 150)
            time.sleep(0.12)
            winsound.Beep(1000, 150)
            time.sleep(0.12)
            winsound.Beep(1200, 200)
        else:
            # Venda: bips descendentes (tom descendo)
            winsound.Beep(1200, 150)
            time.sleep(0.12)
            winsound.Beep(1000, 150)
            time.sleep(0.12)
            winsound.Beep(800, 200)
    except Exception:
        try:
            winsound.Beep(1000, 500)
        except Exception:
            pass


def play_exit_sound():
    """Som de saida de posicao — 2 bips longos e graves."""
    try:
        winsound.Beep(600, 300)
        time.sleep(0.15)
        winsound.Beep(600, 300)
    except Exception:
        pass


def play_notification_sound():
    """Soa diferente do alerta de trade — para info geral."""
    try:
        winsound.Beep(800, 100)
        time.sleep(0.05)
        winsound.Beep(1000, 100)
    except Exception:
        pass


# ─────────────────────────────────────────────
# MONITORAMENTO DE POSIÇÃO
# ─────────────────────────────────────────────
POSITION_FILE = "data/current_position.json"
ACCOUNT_SPEC = "APEX5494170000001"
ACCOUNT_ID = 45402487

class PositionTracker:
    """Acompanha posicoes abertas via API + gera alertas de saida."""
    def __init__(self, auth):
        self.auth = auth
        self.entry_price = None
        self.direction = None  # "BUY" ou "SELL"
        self.sl = None
        self.tp = None
        self.contracts = None
        self._last_alert = None
        self._has_position = False

    def _save(self):
        data = {
            "entry": self.entry_price,
            "direction": self.direction,
            "sl": self.sl,
            "tp": self.tp,
            "contracts": self.contracts,
        }
        with open(POSITION_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self):
        if os.path.exists(POSITION_FILE):
            try:
                data = json.loads(open(POSITION_FILE).read())
                self.entry_price = data.get("entry")
                self.direction = data.get("direction")
                self.sl = data.get("sl")
                self.tp = data.get("tp")
                self.contracts = data.get("contracts")
                return True
            except:
                pass
        return False

    def check_position(self, base_url):
        """Verifica se ha posicao aberta na corretora via API."""
        headers = self.auth.headers()
        try:
            import requests
            resp = requests.get(f"{base_url}/position/list", headers=headers, timeout=10)
            if resp.status_code == 200:
                positions = resp.json()
                # Filtra por nosso símbolo
                my_pos = [p for p in positions if p.get("symbol") == SYMBOL or p.get("symbol", "").startswith(SYMBOL)]
                if my_pos and len(my_pos) > 0:
                    pos = my_pos[0]
                    net = pos.get("netPos", 0)
                    if net != 0:
                        # Ha posicao aberta
                        direction = "BUY" if net > 0 else "SELL"
                        open_price = pos.get("openPrice", 0) or pos.get("avgPrice", 0)
                        current_price = pos.get("price", 0) or open_price

                        # Se detectamos nova posicao
                        if (not self._has_position or self.entry_price is None or
                            current_price != self.entry_price or direction != self.direction):
                            self._has_position = True
                            self.entry_price = current_price
                            self.direction = direction

                            # Calcula SL/TP automaticamente
                            tick_size = 0.25
                            tick_val = 0.50
                            sl_ticks = 16
                            tp_ticks = 40
                            sl_pts = sl_ticks * tick_size
                            tp_pts = tp_ticks * tick_val

                            if direction == "BUY":
                                self.sl = round(current_price - sl_pts, 2)
                                self.tp = round(current_price + tp_pts, 2)
                            else:
                                self.sl = round(current_price + sl_pts, 2)
                                self.tp = round(current_price - tp_pts, 2)
                            self.contracts = abs(net)
                            self._save()

                            ts = datetime.now().strftime("%H:%M:%S")
                            print(f"\n{'='*60}", flush=True)
                            print(f"  POSICAO DETECTADA: {direction} {SYMBOL}", flush=True)
                            print(f"  Entrada:   {current_price}", flush=True)
                            print(f"  SL:        {self.sl} ({sl_ticks} ticks = ${sl_ticks*tick_val*self.contracts:.2f})", flush=True)
                            print(f"  TP:        {self.tp} ({tp_ticks} ticks)", flush=True)
                            print(f"  Contratos: {self.contracts}", flush=True)
                            print(f"  Acompanhando via API...", flush=True)
                            print(f"{'='*60}\n", flush=True)
                        return True
                    else:
                        # Posicao foi fechada
                        if self._has_position:
                            ts = datetime.now().strftime("%H:%M:%S")
                            pnl = pos.get("pnl", 0) or 0
                            play_exit_sound()
                            print(f"\n{'='*60}", flush=True)
                            print(f"  POSICAO FECHADA!", flush=True)
                            print(f"  Hora: {ts}", flush=True)
                            print(f"  P&L:  ${pnl:.2f}", flush=True)
                            print(f"  {'='*60}\n", flush=True)
                        self._clear()
                        return False
                else:
                    # Nenhuma posicao encontrada
                    if self._has_position:
                        play_exit_sound()
                        print(f"\n{'='*60}", flush=True)
                        print(f"  POSICAO FECHADA (detectado via API)", flush=True)
                        print(f"{'='*60}\n", flush=True)
                    self._clear()
                    return False
            else:
                logger.debug(f"Position list: status {resp.status_code}")
                return self._has_position
        except Exception as e:
            logger.debug(f"Position check error: {e}")
            return self._has_position

    def check_price_alerts(self, current_price):
        """Verifica se preco esta perto do SL ou TP."""
        if not self._has_position or self.entry_price is None:
            return

        alert_key = None

        if self.direction == "BUY":
            dist_sl = current_price - self.sl
            dist_tp = self.tp - current_price
            if dist_sl <= 0:
                # SL atingido
                alert_key = "SL_HIT"
                print(f"\n  ALERTA: SL ATINGIDO! Preco ({current_price}) <= SL ({self.sl})", flush=True)
                play_exit_sound()
            elif dist_sl <= 2:  # 2 pontos do SL
                if self._last_alert != "SL_NEAR":
                    alert_key = "SL_NEAR"
                    print(f"\n  ALERTA: PRECO PROXIMO DO SL! {current_price} (SL={self.sl})", flush=True)
                    winsound.Beep(600, 500)
        else:  # SELL
            dist_sl = self.sl - current_price
            dist_tp = current_price - self.tp
            if dist_sl <= 0:
                alert_key = "SL_HIT"
                print(f"\n  ALERTA: SL ATINGIDO! Preco ({current_price}) >= SL ({self.sl})", flush=True)
                play_exit_sound()
            elif dist_sl <= 2:
                if self._last_alert != "SL_NEAR":
                    alert_key = "SL_NEAR"
                    print(f"\n  ALERTA: PRECO PROXIMO DO SL! {current_price} (SL={self.sl})", flush=True)
                    winsound.Beep(600, 500)

        # Verifica TP
        if self.direction == "BUY" and current_price >= self.tp:
            alert_key = "TP_HIT"
            print(f"\n  ALERTA: TP ATINGIDO! Preco ({current_price}) >= TP ({self.tp})", flush=True)
            winsound.Beep(1500, 150)
            time.sleep(0.1)
            winsound.Beep(1500, 150)
            time.sleep(0.1)
            winsound.Beep(1500, 300)
        elif self.direction == "SELL" and current_price <= self.tp:
            alert_key = "TP_HIT"
            print(f"\n  ALERTA: TP ATINGIDO! Preco ({current_price}) <= TP ({self.tp})", flush=True)
            winsound.Beep(1500, 150)
            time.sleep(0.1)
            winsound.Beep(1500, 150)
            time.sleep(0.1)
            winsound.Beep(1500, 300)

        if alert_key and alert_key != self._last_alert:
            self._last_alert = alert_key

    def _clear(self):
        self._has_position = False
        self.entry_price = None
        self.direction = None
        self.sl = None
        self.tp = None
        self.contracts = None
        self._last_alert = None
        if os.path.exists(POSITION_FILE):
            os.remove(POSITION_FILE)


# ─────────────────────────────────────────────
# SIGNAL LOG — registro separado de sinais
# ─────────────────────────────────────────────
SIGNAL_FILE = "data/signals.json"

def log_signal(sig: dict, stops: dict, threshold: float, trade_history: list):
    """Registra sinal e exibe no console com formatação clara."""
    action = sig["action"]
    price = sig["price"]
    atr_val = calc_atr(
        [c["high"] for c in trade_history[-20:]] if len(trade_history) >= 20 else [price],
        [c["low"] for c in trade_history[-20:]] if len(trade_history) >= 20 else [price * 0.999],
        [c["close"] for c in trade_history[-20:]] if len(trade_history) >= 20 else [price],
    )

    # Calculate stops if ATR available
    if stops:
        sl = stops["stop_loss"]
        tp = stops["take_profit"]
        contracts = stops["position_size"]
        sl_ticks = stops["sl_ticks"]
        tp_ticks = stops["tp_ticks"]
        risk_usd = stops["risk_usd"]
        reward_usd = stops["reward_usd"]
        rr = stops["rr_ratio"]
    else:
        tick_size = 0.25  # MNQ/MES default
        tick_val = 0.50
        sl_ticks = 16
        tp_ticks = 40
        sl_pts = sl_ticks * tick_size
        tp_pts = tp_ticks * tick_val
        if action == "BUY":
            sl = round(price - sl_pts, 2)
            tp = round(price + tp_pts, 2)
        else:
            sl = round(price + sl_pts, 2)
            tp = round(price - tp_pts, 2)
        contracts = 1
        risk_usd = sl_ticks * tick_val * contracts
        reward_usd = tp_ticks * tick_val * contracts
        rr = round(reward_usd / risk_usd, 2) if risk_usd > 0 else 0

    ts = datetime.now().strftime("%H:%M:%S")

    # Save to signals file
    entries = []
    if os.path.exists(SIGNAL_FILE):
        try:
            entries = json.loads(open(SIGNAL_FILE, "r", encoding="utf-8").read())
        except:
            entries = []
    entries.append({
        "timestamp": ts,
        "signal": f"{action} {SYMBOL}",
        "score": sig["score"],
        "threshold": threshold,
        "entry_price": price,
        "stop_loss": sl,
        "take_profit": tp,
        "contracts": contracts,
        "sl_ticks": sl_ticks,
        "tp_ticks": tp_ticks,
        "risk_usd": round(risk_usd, 2),
        "reward_usd": round(reward_usd, 2),
        "rr_ratio": rr,
        "reason": sig["reason"],
    })
    with open(SIGNAL_FILE, "w", encoding="utf-8") as f:
        json.dump(entries[-100:], f, indent=2, default=str)  # Keep last 100

    # Display in console
    arrow = ">>>"
    direction = f"COMPRAR {SYMBOL}" if action == "BUY" else f"VENDER {SYMBOL}"
    print(f"\n{'='*60}", flush=True)
    print(f"  SINAL: {direction}", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"  Hora:      {ts}", flush=True)
    print(f"  Score:     {sig['score']}/{int(threshold)+2} (min={threshold})", flush=True)
    print(f"  Razao:     {sig['reason']}", flush=True)
    print(f"  Entrada:   {price}", flush=True)
    print(f"  Stop Loss: {sl} ({sl_ticks} ticks = ${risk_usd:.2f})", flush=True)
    print(f"  TP:        {tp} ({tp_ticks} ticks = ${reward_usd:.2f})", flush=True)
    print(f"  Contratos: {contracts}", flush=True)
    print(f"  Risco:     ${risk_usd:.2f} | Potencial: ${reward_usd:.2f} | R/R: 1:{rr}", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"  [Operar manualmente no trader.tradovate.com]", flush=True)
    print(f"{'='*60}\n", flush=True)


def _load_trade_history() -> list:
    """Carrega histórico de trades."""
    if not os.path.exists("data/trading_journal.json"):
        return []
    try:
        return json.loads(open("data/trading_journal.json", "r", encoding="utf-8").read())
    except:
        return []


# ─────────────────────────────────────────────
# LOOP DE ANÁLISE
# ─────────────────────────────────────────────
async def analysis_loop(feed, recovery, adaptive, executor, simulator):
    """Roda a cada candle — analisa e exibe sinais."""
    mode_str = "SIMULACAO" if DEMO_SIMULATION else ("AUTO-TRADE" if AUTO_EXECUTE_TRADES else "SINAIS MANUAIS")
    logger.info("=" * 60)
    logger.info(f" MODO {mode_str} — {' trades virtuais' if DEMO_SIMULATION else ''}")
    logger.info(" " + "-" * 50)
    logger.info(f" Instrumento:       {SYMBOL}")
    logger.info(f" Timeframe:         {TIMEFRAME_MINUTES} minutos")
    logger.info(f" Estratégias:       MeanRev, Trend, SmartMoney, VWAP, Momentum, Session, VolatilityRegime")
    logger.info(f" Min Score:         {MIN_SCORE_TO_TRADE} (adaptativo)")
    logger.info(f" Stop Loss:         (fixo ou ATR-based)")
    logger.info(f" Take Profit:       (fixo ou ATR-based)")
    logger.info("=" * 60)

    trade_history = _load_trade_history()
    candles_since_last = 0
    active_trade = None  # "BUY" or "SELL" — sinal que emitiu alerta forte

    while True:
        await asyncio.sleep(TIMEFRAME_MINUTES * 60)
        candles_since_last += 1

        recovery.save()

        candles = feed.get_candles()
        if len(candles) < 50:
            ts = datetime.now().strftime("%H:%M:%S")
            logger.info(f"[{ts}] Aguardando mais candles ({len(candles)}/50)...")
            continue

        # --- Check exit signal (reversal) ---
        if active_trade is not None:
            sig_temp = generate_signal(candles)
            opposite = "SELL" if active_trade == "BUY" else "BUY"
            # Se sinal oposto aparece com score >= 2, alerta saida
            if sig_temp["action"] == opposite and sig_temp["score"] >= 2:
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"\n{'='*60}", flush=True)
                print(f"  SINAL DE SAIDA: SAIR da posicao {active_trade}!", flush=True)
                print(f"  Motivo: Sinal inverso ({opposite} score={sig_temp['score']}) detectado", flush=True)
                print(f"  Razao:  {sig_temp['reason']}", flush=True)
                print(f"  Preco atual: {sig_temp['price']}", flush=True)
                print(f"  Clique FLATTEN no tradovate para sair!", flush=True)
                print(f"{'='*60}\n", flush=True)
                # Toca alerta sonoro
                try:
                    import winsound
                    winsound.Beep(600, 500)
                    time.sleep(0.15)
                    winsound.Beep(600, 500)
                except:
                    pass
                active_trade = None
            # Se sinal forte a favor continua, mantem
            elif sig_temp["action"] == active_trade and sig_temp["score"] >= 3:
                # Sinal a favor ainda forte — mantém trade
                logger.info(f"  Trade ativo ({active_trade}) — sinal se mantem (score={sig_temp['score']})")
            # Se sinal vira HOLD, alerta saida neutra
            elif sig_temp["action"] == "HOLD":
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"\n{'='*60}", flush=True)
                print(f"  ATENCAO: Sinal ficou neutro (HOLD)", flush=True)
                print(f"  Considere sair ou mover SL para breakeven!", flush=True)
                print(f"{'='*60}\n", flush=True)
                active_trade = None

        # --- News Filter ---
        vol_check_due = (candles_since_last % 3 == 0)
        from skills.news_filter import is_news_today, is_news_impacting
        news_today, news_detail = is_news_today()
        news_impacting, impact_detail = is_news_impacting()

        if news_today and news_impacting:
            ts = datetime.now().strftime("%H:%M:%S")
            logger.warning(f"[{ts}] PAUSADO: {impact_detail} — sem sinais.")
            continue

        vol_high_reason = ""
        if vol_check_due:
            from skills.news_filter import check_volatility
            vol_is_high, vol_reason = check_volatility()
            if vol_is_high:
                vol_high_reason = vol_reason

        if vol_high_reason:
            ts = datetime.now().strftime("%H:%M:%S")
            logger.warning(f"[{ts}] PAUSADO: {vol_reason}")
            continue

        # --- Adaptive Threshold ---
        threshold = adaptive.get_current_threshold(trade_history, candles)
        cached_regime = adaptive._last_regime if hasattr(adaptive, '_last_regime') else "normal"

        # --- Signal Generation ---
        sig = generate_signal(candles)
        
        # Prophet AI confirmation (if available)
        if PROPHET_AVAILABLE and sig["action"] in ("BUY", "SELL"):
            try:
                prices = [c["close"] for c in candles]
                prophet_trend = get_trend_direction(prices)
                
                # Boost score if Prophet agrees
                if prophet_trend == sig["action"]:
                    sig["score"] = min(sig["score"] + 1, 10)
                    sig["reason"] += " [Prophet confirmed]"
                    print(f"  [Prophet] {prophet_trend} trend confirmed - score boosted")
                elif prophet_trend != "HOLD":
                    print(f"  [Prophet] WARNING: {prophet_trend} vs {sig['action']}")
            except Exception as e:
                print(f"  [Prophet] Error: {e}")
        
        ts = datetime.now().strftime("%H:%M:%S")

        # ATR para stops
        highs  = [c["high"] for c in candles[-20:]]
        lows   = [c["low"]  for c in candles[-20:]]
        closes = [c["close"] for c in candles[-20:]]
        atr_val = calc_atr(highs, lows, closes)

        extra = f" | Volatilidade: {vol_high_reason}" if vol_high_reason else ""

        # Risk manager para calculo de stops (sem travar por horario)
        risk_temp = RiskManager(account_balance=50000.0)
        stops = risk_temp.calculate_stops(
            sig["action"], sig["price"], atr_val, sig["score"]
        ) if sig["action"] in ("BUY", "SELL") else None

        # Status line
        if sig["action"] in ("BUY", "SELL"):
            action_icon = "BUY" if sig["action"] == "BUY" else "SELL"
            logger.info(
                f"[{ts}] {action_icon} {SYMBOL} @ {sig['price']} | "
                f"Score: {sig['score']}/{int(threshold)+2} | "
                f"Regime: {cached_regime} | "
                f"ATR: {atr_val:.2f} | {sig['reason']}"
            )
        else:
            logger.info(
                f"[{ts}] HOLD {SYMBOL} @ {sig['price']} | "
                f"Score: 0 | {sig['reason']}"
            )

        # Se sinal forte, exibir alerta completo
        if sig["action"] in ("BUY", "SELL"):
            # Check if we're within trading hours for signal confidence
            now_h = datetime.now().hour
            from config.settings import TRADE_START_HOUR, TRADE_END_HOUR
            in_hours = TRADE_START_HOUR <= now_h < TRADE_END_HOUR

            if sig["score"] >= threshold:
                play_alert_sound()
                print(f"\n{'='*60}", flush=True)
                arrow = "COMPRAR" if sig["action"] == "BUY" else "VENDER"
                print(f"  >>> SINAL: {arrow} {SYMBOL} <<<", flush=True)
                print(f"  Score:     {sig['score']}/{int(threshold)+2} (>= {threshold})", flush=True)
                print(f"  Entrada:   Market (atual ~{sig['price']})", flush=True)
                if stops:
                    print(f"  SL:        {stops['stop_loss']} ({stops['sl_ticks']} ticks)", flush=True)
                    print(f"  TP:        {stops['take_profit']} ({stops['tp_ticks']} ticks)", flush=True)
                    print(f"  Contratos: {stops['position_size']}", flush=True)
                    print(f"  Risco:     ${stops['risk_usd']:.2f} | "
                          f"Potencial: ${stops['reward_usd']:.2f} | "
                          f"R/R: 1:{stops['rr_ratio']}", flush=True)
                if not in_hours:
                    print(f"  ATENCAO: Fora do horario normal ({TRADE_START_HOUR}h-{TRADE_END_HOUR}h)", flush=True)
                print(f"  Motivo:    {sig['reason']}", flush=True)
                # Auto-execute OR manual
                if AUTO_EXECUTE_TRADES:
                    print(f"  EXECUTANDO ORDEM AUTOMATICA...", flush=True)
                    
                    # Try NT8 ATI first (if available)
                    nt8_result = None
                    if NT8_ATI_AVAILABLE:
                        try:
                            # Map action to NT8 format
                            nt8_action = "BUY" if sig["action"] == "buy" else "SELL"
                            # Get current price for reference
                            entry_price = sig.get("price", 0)
                            # Send to NT8
                            nt8_result = send_oif_order(
                                action=nt8_action,
                                symbol="MES",  # Configurable
                                quantity=POSITION_SIZE,
                                order_type="MARKET",
                                strategy="ApexSimpleTrend"
                            )
                            print(f"  [NT8] OIF order sent: {nt8_result}", flush=True)
                        except Exception as e:
                            print(f"  [NT8] ATI Error: {e}", flush=True)
                    
                    # Also try native executor (Tradovate API)
                    result = await executor.place_bracket_order(
                        sig["action"], sig["price"], atr_val, sig["score"]
                    )
                    if result["success"]:
                        print(f"  ✅ ORDEM ENVIADA COM SUCESSO!", flush=True)
                    else:
                        # If native failed but NT8 sent, still success
                        if nt8_result:
                            print(f"  ✅ ORDEM ENVIADA VIA NT8 ATI!", flush=True)
                        else:
                            print(f"  ❌ FALHA: {result.get('reason', 'desconhecido')}", flush=True)
                            logger.warning(f"Order failed: {result}")
                else:
                    print(f"  Operar manualmente em trader.tradovate.com", flush=True)
                print(f"{'='*60}", flush=True)

                log_signal(sig, stops, threshold, trade_history)
                active_trade = sig["action"]
            else:
                logger.info(
                    f"  Sinal fraco ({sig['score']} < {threshold}). Ignorado."
                )

        # Reload trade history
        trade_history = _load_trade_history()

        # ── Update Dashboard ──
        sig_raw = sig  # from generate_signal
        strategies = sig_raw.get("strategies", {})
        indicators = sig_raw.get("indicators", {})

        # Build trade plan
        if sig_raw["action"] in ("BUY", "SELL") and stops:
            trade_plan = {
                "direction": sig_raw["action"],
                "entry": sig_raw["price"],
                "stop_loss": stops["stop_loss"],
                "take_profit": stops["take_profit"],
                "contracts": stops["position_size"],
                "risk_usd": stops["risk_usd"],
                "reward_usd": stops["reward_usd"],
                "rr": stops["rr_ratio"],
            }
        else:
            trade_plan = {"direction": "HOLD"}

        update_state({
            "price": sig_raw["price"],
            "action": sig_raw["action"],
            "score": sig_raw["score"],
            "threshold": threshold,
            "ATR": atr_val,
            "vol_regime": cached_regime,
            "signal_reason": sig_raw["reason"],
            "strategies": strategies,
            "indicators": indicators,
            "trade_plan": trade_plan,
            "confluence": sig_raw.get("details", []),
        })


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
async def main():
    logger.info("=" * 60)
    from config.settings import ENV
    if DEMO_SIMULATION:
        mode_str = "MODO SIMULACAO VIRTUAL"
        order_str = "Trades virtuais (sem ordens reais)"
    elif AUTO_EXECUTE_TRADES:
        mode_str = "MODO AUTO-TRADE"
        order_str = "Ordens AUTOMATICAS via API Tradovate ({})".format(ENV)
    else:
        mode_str = "MODO SINAIS"
        order_str = "Sinais manuais (via trader.tradovate.com)"
    logger.info(" APEX CLAUDE TRADER v3 — {}".format(mode_str))
    logger.info(f" Instrumento:   {SYMBOL}")
    logger.info(f" Timeframe:     {TIMEFRAME_MINUTES} minutos")
    logger.info(f" Ordens:        {order_str}")
    logger.info("=" * 60)

    # 1. Autenticacao (para leitura de conta/posicoes)
    auth = TradovateAuth()
    if not await auth.authenticate():
        logger.warning("Auth falhou — sinais funcionarao sem dados da conta.")
    else:
        logger.info(f"  Conta: {auth.account_spec}")

    # 2. Market data
    feed = MarketDataFeed(auth)

    # 3. Recovery
    import requests as _requests
    risk_temp = RiskManager(account_balance=50000.0)
    from core.recovery import RecoveryState
    recovery = RecoveryState(risk_temp, None)
    recovered, reason = recovery.recover_on_startup()
    if recovered:
        logger.info(f"  Estado recuperado: {reason}")

    # 4. Position tracker
    from config.settings import TRADOVATE_API_URL, ENV
    base_url = TRADOVATE_API_URL[ENV]
    tracker = PositionTracker(auth)

    # 4b. Start dashboard
    try:
        start_dashboard()
    except Exception as e:
        logger.warning(f"Dashboard nao pôde iniciar: {e}")

    # 5. Adaptive threshold
    adaptive = AdaptiveThreshold()

    # 5b. Trade Executor (auto-orders)
    risk_for_executor = RiskManager(account_balance=50000.0)
    executor = OrderExecutor(auth, risk_for_executor)
    if AUTO_EXECUTE_TRADES:
        logger.info("🔄 Execução automática ATIVADA — ordens via API Tradovate")
    else:
        logger.info("🔒 Execução automática DESATIVADA — modo sinais")

    # 5c. Trade Simulator (virtual trades for backtesting/safe mode)
    simulator = TradeSimulator(initial_balance=50000.0)
    if DEMO_SIMULATION:
        logger.info("🎮 Simulação VIRTUAL ativada — sem ordens reais")
    else:
        logger.info("🔒 Simulação DESATIVADA — ordens reais na API (ambiente: {})".format(ENV))

    # 6. Token refresh loop
    async def token_refresher():
        while True:
            await asyncio.sleep(300)
            try:
                auth.renew_if_needed()
                if auth.token_expiry > time.time():
                    ts = datetime.now().strftime("%H:%M:%S")
                    logger.debug(f"[{ts}] Token válido até: {datetime.fromtimestamp(auth.token_expiry).strftime('%H:%M:%S')}")
            except Exception:
                pass

    # 7. Position monitor loop (verifica a cada 30s)
    async def position_monitor():
        while True:
            await asyncio.sleep(30)
            try:
                has_pos = await asyncio.to_thread(tracker.check_position, base_url)
                if has_pos:
                    # Verifica alertas de preco com ultimo candle
                    latest = feed.get_latest_candle()
                    if latest:
                        await asyncio.to_thread(tracker.check_price_alerts, latest["close"])
            except Exception as e:
                logger.debug(f"Monitor: {e}")

    # 8. Run
    await asyncio.gather(
        feed.connect(),
        analysis_loop(feed, recovery, adaptive, executor, simulator),
        token_refresher(),
        position_monitor(),
    )


def _log_and_flush(msg=None):
    """Log guaranteed to be flushed to file before process exits."""
    for handler in logging.root.handlers:
        handler.flush()
    # Also do a manual fsync on file handlers
    for h in logging.root.handlers:
        if isinstance(h, logging.FileHandler):
            h.stream.flush()
            try:
                os.fsync(h.stream.fileno())
            except Exception:
                pass


def _safe_main():
    """Run main() with robust error logging and auto-restart."""
    while True:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            # Flush log before exit
            _log_and_flush()
            logger.info("Bot encerrado pelo usuario")
            _log_and_flush()
            break
        except Exception as e:
            # Flush log BEFORE printing traceback so nothing is lost
            _log_and_flush()
            logger.exception(f"Erro fatal: {e} | Reiniciando em 5s...")
            _log_and_flush()
            time.sleep(5)


if __name__ == "__main__":
    _safe_main()
