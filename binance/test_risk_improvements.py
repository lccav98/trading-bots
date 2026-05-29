"""
Testes de regressão para as melhorias de gestão de risco do bot de futuros.

Cobre lógica pura (sem rede / sem API Binance):
- Breakeven do PositionManager (defaults inalterados + parametrização)
- Circuit breaker de drawdown de sessão (FuturesBot._check_drawdown)

Rodar:  PAPER_MODE=true python3 -m pytest test_risk_improvements.py -v
   ou:  PAPER_MODE=true python3 test_risk_improvements.py
"""
import os
import time

os.environ.setdefault('PAPER_MODE', 'true')

from core.position import PositionManager


def test_breakeven_defaults_inalterados():
    """Com defaults, o breakeven move o stop para entry+0.3% ao atingir +0.8%."""
    pm = PositionManager(commission=0.0005)
    pm.open(price=100.0, qty=1, cost=100, stop_loss_pct=0.015, tier1_pct=0.005,
            tier2_pct=0.015, trail_pct=0.005, direction='long', symbol='X', timeframe='15m')
    assert abs(pm.position['stop_price'] - 98.5) < 1e-9
    pm.check_exit(100.9)  # +0.9% > gatilho 0.8%
    assert pm.position.get('breakeven_moved')
    assert abs(pm.position['stop_price'] - 100.3) < 1e-9


def test_breakeven_configuravel():
    """Gatilho e offset customizados são respeitados."""
    pm = PositionManager(commission=0.0005)
    pm.open(price=100.0, qty=1, cost=100, stop_loss_pct=0.02, tier1_pct=0.05,
            tier2_pct=0.08, trail_pct=0.01, direction='long', symbol='Y', timeframe='15m',
            be_trigger_pct=0.015, be_offset_pct=0.006)
    pm.check_exit(100.9)   # +0.9% < gatilho 1.5% -> não move
    assert not pm.position.get('breakeven_moved')
    pm.check_exit(101.7)   # +1.7% >= 1.5% -> move para entry+0.6%
    assert pm.position.get('breakeven_moved')
    assert abs(pm.position['stop_price'] - 100.6) < 1e-9


def test_circuit_breaker_drawdown():
    """Dispara ao ultrapassar o drawdown máximo; ignora quedas menores; atualiza o pico."""
    from hf_bot_futures import FuturesBot
    bot = FuturesBot.__new__(FuturesBot)  # evita __init__ (sem rede)
    bot.balance = bot.equity_peak = 100.0
    bot.max_session_drawdown = 0.08
    bot.dd_pause_seconds = 14400
    bot.dd_blocked_until = 0.0

    assert bot._check_drawdown() is False          # sem drawdown
    bot.balance = 95.0
    assert bot._check_drawdown() is False           # -5% < 8%
    bot.balance = 91.0
    assert bot._check_drawdown() is True             # -9% >= 8% -> bloqueia
    assert bot.dd_blocked_until > time.time()

    bot.balance = 120.0
    bot.dd_blocked_until = 0.0
    assert bot._check_drawdown() is False
    assert bot.equity_peak == 120.0                  # pico atualizado


if __name__ == '__main__':
    test_breakeven_defaults_inalterados()
    print('T1 OK: breakeven defaults inalterados')
    test_breakeven_configuravel()
    print('T2 OK: breakeven configuravel')
    test_circuit_breaker_drawdown()
    print('T3 OK: circuit breaker de drawdown')
    print('\nTODOS OS TESTES PASSARAM')
