"""
core/risk.py — Risk Management Avançado (Apex Trader Funding)

Features:
  - Daily loss limit (bloqueia ordens)
  - Daily profit target (para quando atingir meta)
  - Drawdown monitoramento
  - Position sizing dinâmico (% risco fixo)
  - Trailing stop automático
  - Consecutive loss cooldown
  - Horário permitido
  - Risco por trade em 1-2% do capital
"""

import logging
from datetime import datetime, time as dtime, timedelta
from config.settings import (
    MAX_DAILY_LOSS, MAX_DRAWDOWN, POSITION_SIZE,
    STOP_LOSS_TICKS, TAKE_PROFIT_TICKS,
    TRADE_START_HOUR, TRADE_END_HOUR, MIN_SCORE_TO_TRADE,
    SYMBOL, RISK_PER_TRADE,
    MAX_CONSECUTIVE_LOSSES, MAX_DAILY_PROFIT,
    TRAILING_STOP_TRIGGER_TICKS, BREAK_EVEN_TRIGGER_TICKS,
    MAX_CONTRACTS_MINI, MAX_CONTRACTS_MICRO,
)

logger = logging.getLogger(__name__)

# Tick por instrumento
TICK_SIZE = {
    "MNQ": 0.25,
    "MES": 0.25,
    "MBT": 5.0,
    "NQ":  0.25,
    "ES":  0.25,
    "CL":  0.01,
    "GC":  0.10,
}

TICK_VALUE = {
    "MNQ": 0.50,
    "MES": 1.25,
    "MBT": 5.00,
    "NQ":  5.00,
    "ES":  12.50,
    "CL":  10.00,
    "GC":  10.00,
}


class RiskManager:
    def __init__(self, account_balance: float = 0, profit_target: float = 0):
        self.daily_pnl       = 0.0
        self.account_balance = account_balance
        self.peak_pnl       = 0.0         # Pico de P&L para trailing
        self.open_position  = None         # None | "BUY" | "SELL"
        self.entry_price    = 0.0
        self.trade_count    = 0
        self.blocked        = False
        self.block_reason   = ""
        self.wins           = 0
        self.losses         = 0
        self.consec_losses   = 0            # Consecutive losses
        self.daily_high_water = 0.0         # Maior P&L do dia
        self.session_date     = datetime.now().date()  # Data para reset diário

        # Trailing stop state
        self.trailing_active = False
        self.trailing_stop   = 0.0
        self.best_pnl_since_entry = 0.0

    def update_pnl(self, pnl: float):
        """Atualiza P&L diário e dispara trailing stop se necessário."""
        self.daily_pnl += pnl

        # Atualiza peak/water
        if self.daily_pnl > self.peak_pnl:
            self.peak_pnl = self.daily_pnl
        if self.daily_pnl > self.daily_high_water:
            self.daily_high_water = self.daily_pnl

        # Consecutive loss tracking
        if pnl < 0:
            self.consec_losses += 1
            self.losses += 1
        else:
            self.consec_losses = 0
            self.wins += 1

        if pnl > 0:
            logger.info(f"💰 Trade vencedor! P&L: +${pnl:.2f}")
        elif pnl < 0:
            logger.info(f"🔴 Trade perdedor. P&L: ${pnl:.2f}")

        self._check_limits()

    def _check_limits(self):
        """Verifica todas as condições de bloqueio."""
        # 1. Daily loss
        if self.daily_pnl <= -MAX_DAILY_LOSS:
            self.blocked = True
            self.block_reason = f"Daily loss máximo atingido: ${self.daily_pnl:.2f}"
            logger.warning(f"🚫 BLOQUEADO — {self.block_reason}")

        # 2. Consecutive losses — cooldown obrigatório
        elif self.consec_losses >= MAX_CONSECUTIVE_LOSSES:
            self.blocked = True
            self.block_reason = f"{self.consec_losses} perdas consecutivas — cooldown ativado"
            logger.warning(f"🚫 BLOQUEADO — {self.block_reason}")

        # 3. Daily profit — meta atingida
        elif MAX_DAILY_PROFIT > 0 and self.daily_pnl >= MAX_DAILY_PROFIT:
            self.blocked = True
            self.block_reason = f"Meta diária atingida: ${self.daily_pnl:.2f}"
            logger.info(f"🏆 Meta diária atingida — parando por hoje: ${self.daily_pnl:.2f}")

    def can_trade(self) -> tuple[bool, str]:
        """
        Retorna (pode_operar, motivo).
        Verifica: horário, posição, daily loss, drawdown, consec losses.
        """
        # 1. Sistema bloqueado
        if self.blocked:
            return False, self.block_reason

        # 2. Posição já aberta — sem pirâmide
        if self.open_position is not None:
            return False, f"Posição já aberta: {self.open_position}"

        # 3. Horário permitido
        now_h = datetime.now().hour
        if not (TRADE_START_HOUR <= now_h < TRADE_END_HOUR):
            return False, f"Fora do horário permitido ({TRADE_START_HOUR}h–{TRADE_END_HOUR}h)"

        # 4. Daily loss (90% threshold = warning zone)
        if self.daily_pnl <= -MAX_DAILY_LOSS * 0.9:
            return False, f"Próximo ao daily loss (${self.daily_pnl:.2f})"

        # 5. Consecutive losses
        if self.consec_losses >= MAX_CONSECUTIVE_LOSSES - 1:
            return False, f"⚠️ {self.consec_losses} perdas seguidas — perto do cooldown"

        # 6. Drawdown
        drawdown = self.peak_pnl - self.daily_pnl
        if drawdown >= MAX_DRAWDOWN:
            return False, f"Drawdown máximo: ${drawdown:.2f}"

        return True, "OK"

    def dynamic_position_size(self, entry_price: float, strategy_score: int = 1) -> int:
        """
        Calcula tamanho baseado em risco fixo % do capital.

        Se strategy_score > 3: usa 1.5x o tamanho normal (confiança alta)
        Se strategy_score <= 1: usa tamanho mínimo
        """
        tick = TICK_SIZE.get(SYMBOL, 0.25)
        tick_val = TICK_VALUE.get(SYMBOL, 0.50)

        # Risco em USD por trade
        base_risk = self.account_balance * RISK_PER_TRADE / 100
        sl_risk_per_contract = STOP_LOSS_TICKS * tick_val

        if sl_risk_per_contract == 0:
            return POSITION_SIZE

        # Limite Apex: max contracts por plano
        max_apex = MAX_CONTRACTS_MINI if SYMBOL in ("MNQ", "MES", "NQ", "ES") else MAX_CONTRACTS_MICRO

        # Contracts = risk_budget / risk_per_contract
        dynamic_size = int(base_risk / sl_risk_per_contract)
        dynamic_size = max(1, min(dynamic_size, POSITION_SIZE * 3, max_apex))

        # Ajuste por confiança da estratégia
        if strategy_score >= 4:
            dynamic_size = min(dynamic_size + 1, max_apex)
        elif strategy_score <= 1:
            dynamic_size = 1  # Mínimo

        return dynamic_size

    def calculate_stops(self, action: str, entry_price: float, atr: float = 0,
                        strategy_score: int = 1) -> dict:
        """
        Calcula SL e TP baseado em ATR — calibrado p/ volatilidade atual.

        SL = 1.0× ATR  (pontos)
        TP = 1.5× ATR  (R/R 1:1.5)

        Se sem dados, usa fallback fixo mais largo.
        """
        tick_size = TICK_SIZE.get(SYMBOL, 0.25)
        tick_val  = TICK_VALUE.get(SYMBOL, 0.50)

        if atr > 0:
            # ATR-based: 1×ATR stop, 1.5×ATR target
            sl_ticks = max(25, int(atr / tick_size))       # min 25 ticks (6.25 pts)
            tp_ticks = max(38, int(1.5 * sl_ticks / 1.0))   # R/R ~1:1.5
            # Cap maximo p/ nao ficar absurdo em dias extremos
            max_ticks_per_trade = int(150 / 4 * tick_val)   # $37.5 max risk
            sl_ticks = min(sl_ticks, max_ticks_per_trade)
            tp_ticks = min(tp_ticks, int(sl_ticks * 1.8))
        else:
            sl_ticks = STOP_LOSS_TICKS
            tp_ticks = TAKE_PROFIT_TICKS

        # Score alto = stop um pouco mais flexivel, TP mais longo
        if strategy_score >= 5:
            sl_ticks = max(int(sl_ticks * 0.9), 25)
            tp_ticks = int(tp_ticks * 1.2)

        sl_pts = sl_ticks * tick_size
        tp_pts = tp_ticks * tick_size

        if action == "BUY":
            stop_loss   = round(entry_price - sl_pts, 2)
            take_profit = round(entry_price + tp_pts, 2)
        else:
            stop_loss   = round(entry_price + sl_pts, 2)
            take_profit = round(entry_price - tp_pts, 2)

        dynamic_size = self.dynamic_position_size(entry_price, strategy_score)

        risk_usd   = sl_ticks  * tick_val * dynamic_size
        reward_usd = tp_ticks  * tick_val * dynamic_size

        return {
            "stop_loss":     stop_loss,
            "take_profit":   take_profit,
            "risk_usd":      round(risk_usd, 2),
            "reward_usd":    round(reward_usd, 2),
            "rr_ratio":      round(reward_usd / risk_usd, 2) if risk_usd > 0 else 0,
            "position_size": dynamic_size,
            "sl_ticks":      sl_ticks,
            "tp_ticks":      tp_ticks,
        }

    def update_trailing_stop(self, current_price: float):
        """Atualiza trailing stop e breakeven se preço favorável."""
        if self.open_position is None or not self.trailing_active:
            return

        tick = TICK_SIZE.get(SYMBOL, 0.25)
        tick_val = TICK_VALUE.get(SYMBOL, 0.50)
        be_dist = BREAK_EVEN_TRIGGER_TICKS * tick
        trigger_dist = TRAILING_STOP_TRIGGER_TICKS * tick

        if self.open_position == "BUY":
            pnl = current_price - self.entry_price
            # Breakeven: apos X ticks favoraveis, move SL para entry
            if pnl >= be_dist and not getattr(self, '_breakeven', False):
                self._breakeven = True
                self.trailing_stop = round(self.entry_price + 0.5 * tick, 2)
                logger.info(f"🔒 Breakeven ativado! SL movido para {self.trailing_stop}")
            # Trailing: apos Y ticks, trailing dinamico
            if pnl >= trigger_dist:
                new_stop = round(current_price - trigger_dist, 2)
                if new_stop > self.trailing_stop:
                    self.trailing_stop = new_stop
                    logger.info(f"🔼 Trailing stop: SL={new_stop}")
        else:  # SELL
            pnl = self.entry_price - current_price
            if pnl >= be_dist and not getattr(self, '_breakeven', False):
                self._breakeven = True
                self.trailing_stop = round(self.entry_price - 0.5 * tick, 2)
                logger.info(f"🔒 Breakeven ativado! SL movido para {self.trailing_stop}")
            if pnl >= trigger_dist:
                new_stop = round(current_price + trigger_dist, 2)
                if new_stop < self.trailing_stop or self.trailing_stop == 0:
                    self.trailing_stop = new_stop

        # Check if trailing stop was hit
        if self.open_position == "BUY" and current_price <= self.trailing_stop:
            logger.info(f"⚡ Trailing stop hit! Saindo em {current_price} (SL={self.trailing_stop})")
        elif self.open_position == "SELL" and current_price >= self.trailing_stop:
            logger.info(f"⚡ Trailing stop hit! Saindo em {current_price} (SL={self.trailing_stop})")

    def register_open(self, direction: str, entry_price: float, stops: dict):
        """Registra abertura de posição."""
        self.open_position = direction
        self.entry_price   = entry_price
        self.trade_count  += 1
        self.trailing_stop = stops["stop_loss"]
        self.trailing_active = True
        logger.info(
            f"📌 Posição #{self.trade_count}: {direction} @ {entry_price} | "
            f"SL={stops['stop_loss']} | TP={stops['take_profit']} | "
            f"Risco=${stops['risk_usd']} | R/R={stops['rr_ratio']}"
        )

    def register_close(self, pnl: float):
        """Registra fechamento de posição."""
        logger.info(
            f"✅ Posição fechada | P&L: ${pnl:.2f} | "
            f"Acumulado: ${self.daily_pnl + pnl:.2f} | "
            f"W:{self.wins + (1 if pnl > 0 else 0)} L:{self.losses + (1 if pnl < 0 else 0)}"
        )
        self.update_pnl(pnl)
        self.open_position  = None
        self.entry_price    = 0
        self.trailing_stop  = 0
        self.trailing_active = False
        self._breakeven      = False  # Reset breakeven flag

    def check_daily_reset(self):
        """Verifica se mudou o dia e reseta contadores diários se necessário."""
        today = datetime.now().date()
        if today != self.session_date:
            logger.info(
                f"📅 Novo dia: {today} | Reset contadores. "
                f"P&L anterior: ${self.daily_pnl:.2f} | "
                f"Trades: {self.trade_count} | W:{self.wins} L:{self.losses}"
            )
            self.daily_pnl    = 0.0
            self.peak_pnl     = 0.0
            self.daily_high_water = 0.0
            self.wins         = 0
            self.losses       = 0
            self.consec_losses = 0
            self.trade_count  = 0
            self.blocked      = False
            self.block_reason = ""
            self.session_date = today
            return True
        return False


    def status(self) -> dict:
        win_rate = (self.wins / (self.wins + self.losses) * 100) if (self.wins + self.losses) > 0 else 0
        return {
            "daily_pnl":     round(self.daily_pnl, 2),
            "peak_pnl":      round(self.peak_pnl, 2),
            "drawdown":      round(self.peak_pnl - self.daily_pnl, 2),
            "open_position": self.open_position,
            "trade_count":   self.trade_count,
            "wins":          self.wins,
            "losses":        self.losses,
            "win_rate":      round(win_rate, 1),
            "consec_losses": self.consec_losses,
            "blocked":       self.blocked,
            "block_reason":  self.block_reason,
        }
