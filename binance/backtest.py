import os
import sys
import json
import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY', '')
API_SECRET = os.getenv('BINANCE_API_SECRET', '')

COMMISSION = 0.001  # 0.1% por ordem (taker fee Binance)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_klines(client, symbol, interval, days=90):
    since = datetime.utcnow() - timedelta(days=days)
    klines = client.get_historical_klines(
        symbol,
        interval,
        since.strftime('%d %b %Y %H:%M:%S')
    )
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades',
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    df.set_index('timestamp', inplace=True)
    return df


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(trades, initial_balance, final_balance, equity_curve):
    total_return = (final_balance - initial_balance) / initial_balance * 100
    n = len(trades)
    if n == 0:
        return {'error': 'Nenhum trade executado'}

    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    win_rate = len(wins) / n * 100

    avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0
    avg_loss = np.mean([t['pnl'] for t in losses]) if losses else 0
    profit_factor = (sum(t['pnl'] for t in wins) / abs(sum(t['pnl'] for t in losses))
                     if losses and sum(t['pnl'] for t in losses) != 0 else float('inf'))

    eq = pd.Series(equity_curve)
    returns = eq.pct_change().dropna()
    sharpe = (returns.mean() / returns.std() * math.sqrt(252)) if returns.std() > 0 else 0

    peak = eq.cummax()
    drawdown = (eq - peak) / peak * 100
    max_drawdown = drawdown.min()

    return {
        'retorno_total_%': round(total_return, 2),
        'total_trades': n,
        'win_rate_%': round(win_rate, 2),
        'profit_factor': round(profit_factor, 2),
        'avg_ganho_$': round(avg_win, 4),
        'avg_perda_$': round(avg_loss, 4),
        'max_drawdown_%': round(max_drawdown, 2),
        'sharpe_ratio': round(sharpe, 2),
        'saldo_inicial_$': round(initial_balance, 2),
        'saldo_final_$': round(final_balance, 2),
    }


# ---------------------------------------------------------------------------
# Strategy 1: MA Crossover + RSI + Bollinger Bands
# ---------------------------------------------------------------------------

def backtest_advanced(df, order_amount=10, stop_loss_pct=2, take_profit_pct=5,
                      short_period=7, long_period=25, initial_balance=100):
    df = df.copy()
    df['ma_short'] = df['close'].rolling(short_period).mean()
    df['ma_long'] = df['close'].rolling(long_period).mean()

    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + gain / loss))

    df['bb_mid'] = df['close'].rolling(20).mean()
    df['bb_std'] = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_mid'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_mid'] - 2 * df['bb_std']

    balance = initial_balance
    position = None
    entry_price = 0
    trades = []
    equity_curve = [balance]

    for i in range(long_period + 1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        price = row['close']

        if position:
            pnl_pct = (price - entry_price) / entry_price * 100
            exit_signal = False
            reason = ''

            if pnl_pct <= -stop_loss_pct:
                exit_signal, reason = True, 'stop_loss'
            elif pnl_pct >= take_profit_pct:
                exit_signal, reason = True, 'take_profit'
            elif prev['ma_short'] >= prev['ma_long'] and row['ma_short'] < row['ma_long']:
                if row['rsi'] > 30:
                    exit_signal, reason = True, 'ma_bearish'
            elif price > row['bb_upper']:
                exit_signal, reason = True, 'bb_overbought'

            if exit_signal:
                qty = order_amount / entry_price
                revenue = qty * price * (1 - COMMISSION)
                pnl = revenue - entry_cost
                balance += revenue
                trades.append({'entry': entry_price, 'exit': price, 'pnl': pnl, 'reason': reason})
                position = None

        else:
            buy_signal = False
            if prev['ma_short'] <= prev['ma_long'] and row['ma_short'] > row['ma_long']:
                if row['rsi'] < 70:
                    buy_signal = True
            elif price < row['bb_lower']:
                buy_signal = True

            if buy_signal and balance >= order_amount:
                entry_cost = order_amount * (1 + COMMISSION)
                balance -= entry_cost
                entry_price = price
                position = 'long'

        equity_curve.append(balance)

    if position:
        price = df.iloc[-1]['close']
        qty = order_amount / entry_price
        revenue = qty * price * (1 - COMMISSION)
        pnl = revenue - entry_cost
        balance += revenue
        trades.append({'entry': entry_price, 'exit': price, 'pnl': pnl, 'reason': 'fim_periodo'})
        equity_curve.append(balance)

    return compute_metrics(trades, initial_balance, balance, equity_curve), trades


# ---------------------------------------------------------------------------
# Strategy 2: Scalping (spread + momentum)
# ---------------------------------------------------------------------------

def backtest_scalping(df, order_value=2, spread_threshold=0.002,
                      profit_target=0.003, stop_loss_ratio=0.5,
                      max_hold_bars=20, initial_balance=10):
    df = df.copy()
    balance = initial_balance
    position = None
    entry_price = 0
    entry_bar = 0
    trades = []
    equity_curve = [balance]

    prices = df['close'].values

    for i in range(5, len(prices)):
        price = prices[i]
        recent = prices[i-5:i]
        change = (recent[-1] - recent[0]) / recent[0]
        momentum = 'up' if change > 0.001 else ('down' if change < -0.001 else 'neutral')

        if position:
            pnl_pct = (price - entry_price) / entry_price
            bars_held = i - entry_bar

            exit_signal = False
            if pnl_pct >= profit_target:
                exit_signal = True
            elif pnl_pct <= -(profit_target * stop_loss_ratio):
                exit_signal = True
            elif bars_held >= max_hold_bars:
                exit_signal = True

            if exit_signal:
                qty = order_value / entry_price
                revenue = qty * price * (1 - COMMISSION)
                pnl = revenue - entry_cost
                balance += revenue
                trades.append({'entry': entry_price, 'exit': price, 'pnl': pnl})
                position = None

        else:
            if momentum == 'up' and balance >= order_value:
                entry_cost = order_value * (1 + COMMISSION)
                balance -= entry_cost
                entry_price = price
                entry_bar = i
                position = 'long'

        equity_curve.append(balance)

    return compute_metrics(trades, initial_balance, balance, equity_curve), trades


# ---------------------------------------------------------------------------
# Strategy 3: High Frequency (MA5/MA10 + volatility filter)
# ---------------------------------------------------------------------------

def backtest_hf(df, order_size=1.0, profit_target=0.005, stop_loss=0.003,
                max_trades_per_cycle=3, cycle_bars=100, initial_balance=10):
    df = df.copy()
    prices = df['close'].values
    balance = initial_balance
    position = None
    entry_price = 0
    trades = []
    equity_curve = [balance]
    trade_count = 0
    cycle_start = 0

    for i in range(10, len(prices)):
        if i - cycle_start >= cycle_bars:
            cycle_start = i
            trade_count = 0

        price = prices[i]
        window = prices[i-10:i]
        ma5 = np.mean(window[-5:])
        ma10 = np.mean(window)
        std = np.std(window)
        volatility = std / ma10

        change_1 = (prices[i] - prices[i-1]) / prices[i-1] if i >= 1 else 0
        change_5 = (prices[i] - prices[i-5]) / prices[i-5] if i >= 5 else 0

        if position:
            pnl_pct = (price - entry_price) / entry_price
            if pnl_pct >= profit_target or pnl_pct <= -stop_loss:
                qty = order_size / entry_price
                revenue = qty * price * (1 - COMMISSION)
                pnl = revenue - entry_cost
                balance += revenue
                trades.append({'entry': entry_price, 'exit': price, 'pnl': pnl})
                position = None
                trade_count += 1
        else:
            if (change_1 > 0.001 and change_5 > 0.002 and volatility < 0.01
                    and trade_count < max_trades_per_cycle and balance >= order_size):
                entry_cost = order_size * (1 + COMMISSION)
                balance -= entry_cost
                entry_price = price
                position = 'long'

        equity_curve.append(balance)

    return compute_metrics(trades, initial_balance, balance, equity_curve), trades


# ---------------------------------------------------------------------------
# Strategy 4: Grid Trading
# ---------------------------------------------------------------------------

def backtest_grid(df, grid_levels=10, price_range_pct=5, order_amount=10,
                  initial_balance=100):
    df = df.copy()
    prices = df['close'].values
    base_price = prices[0]
    rng = price_range_pct / 100 * base_price
    lower = base_price - rng
    upper = base_price + rng
    step = (upper - lower) / (grid_levels - 1)
    grid = [lower + i * step for i in range(grid_levels)]

    balance = initial_balance
    asset_balance = 0
    trades = []
    equity_curve = [balance]

    # Estado de cada nível: None | 'buy_pending' | 'sell_pending'
    level_state = ['buy_pending' if grid[i] < base_price else 'sell_pending'
                   for i in range(grid_levels)]

    for price in prices[1:]:
        for idx, level_price in enumerate(grid):
            state = level_state[idx]

            if state == 'buy_pending' and price <= level_price:
                qty = order_amount / level_price
                cost = qty * level_price * (1 + COMMISSION)
                if balance >= cost:
                    balance -= cost
                    asset_balance += qty
                    level_state[idx] = 'sell_pending'
                    trades.append({'type': 'buy', 'price': level_price, 'qty': qty, 'pnl': 0})

            elif state == 'sell_pending' and price >= level_price:
                qty = order_amount / level_price
                if asset_balance >= qty:
                    revenue = qty * level_price * (1 - COMMISSION)
                    pnl = revenue - order_amount
                    balance += revenue
                    asset_balance -= qty
                    level_state[idx] = 'buy_pending'
                    trades.append({'type': 'sell', 'price': level_price, 'qty': qty, 'pnl': pnl})

        total_equity = balance + asset_balance * price
        equity_curve.append(total_equity)

    final_balance = balance + asset_balance * prices[-1]
    sell_trades = [t for t in trades if t['type'] == 'sell']
    return compute_metrics(sell_trades, initial_balance, final_balance, equity_curve), trades


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def print_result(name, symbol, interval, days, metrics):
    print(f"\n{'='*60}")
    print(f"  {name}  |  {symbol}  |  {interval}  |  {days} dias")
    print(f"{'='*60}")
    if 'error' in metrics:
        print(f"  ⚠  {metrics['error']}")
        return
    for k, v in metrics.items():
        label = k.replace('_', ' ').ljust(22)
        print(f"  {label}: {v}")


def main():
    if not API_KEY or not API_SECRET:
        print("Erro: BINANCE_API_KEY e BINANCE_API_SECRET não configurados no .env")
        sys.exit(1)

    client = Client(API_KEY, API_SECRET)
    print("Buscando dados históricos da Binance...")

    # --- Advanced (MA + RSI + BB) ---
    print("\n[1/4] Advanced Bot: TRXUSDT 15m 90 dias")
    df_trx_15m = fetch_klines(client, 'TRXUSDT', Client.KLINE_INTERVAL_15MINUTE, days=90)
    m, trades = backtest_advanced(df_trx_15m, order_amount=2, initial_balance=10)
    print_result('Advanced (MA+RSI+BB)', 'TRXUSDT', '15m', 90, m)

    print("\n[2/4] Advanced Bot: BTCUSDT 15m 90 dias")
    df_btc_15m = fetch_klines(client, 'BTCUSDT', Client.KLINE_INTERVAL_15MINUTE, days=90)
    m, _ = backtest_advanced(df_btc_15m, order_amount=10, initial_balance=100)
    print_result('Advanced (MA+RSI+BB)', 'BTCUSDT', '15m', 90, m)

    # --- Scalping ---
    print("\n[3/4] Scalping Bot: TRXUSDT 1m 30 dias")
    df_trx_1m = fetch_klines(client, 'TRXUSDT', Client.KLINE_INTERVAL_1MINUTE, days=30)
    m, _ = backtest_scalping(df_trx_1m, order_value=2, initial_balance=10)
    print_result('Scalping', 'TRXUSDT', '1m', 30, m)

    # --- High Frequency ---
    print("\n[4/4] HF Bot: TRXUSDT 3m 30 dias")
    df_trx_3m = fetch_klines(client, 'TRXUSDT', Client.KLINE_INTERVAL_3MINUTE, days=30)
    m, _ = backtest_hf(df_trx_3m, order_size=1.0, initial_balance=10)
    print_result('High Frequency', 'TRXUSDT', '3m', 30, m)

    # --- Grid ---
    print("\n[5/5] Grid Bot: TRXUSDT 15m 90 dias")
    m, _ = backtest_grid(df_trx_15m, grid_levels=10, price_range_pct=5,
                         order_amount=2, initial_balance=100)
    print_result('Grid Trading', 'TRXUSDT', '15m', 90, m)

    # Salva resultados
    results = {
        'gerado_em': datetime.now().isoformat(),
        'advanced_trxusdt': m,
    }
    with open('backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nResultados salvos em backtest_results.json")


if __name__ == '__main__':
    main()
