import os
import sys
import json
import itertools
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY', '')
API_SECRET = os.getenv('BINANCE_API_SECRET', '')
COMMISSION = 0.001


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def fetch_klines(client, symbol, interval, days=90):
    from datetime import timedelta
    since = (datetime.utcnow() - timedelta(days=days)).strftime('%d %b %Y %H:%M:%S')
    klines = client.get_historical_klines(symbol, interval, since)
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
    n = len(trades)
    if n < 5:
        return None

    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    win_rate = len(wins) / n * 100

    gross_win = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))
    profit_factor = gross_win / gross_loss if gross_loss > 0 else float('inf')

    eq = pd.Series(equity_curve)
    returns = eq.pct_change().dropna()
    sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0

    peak = eq.cummax()
    max_dd = ((eq - peak) / peak * 100).min()

    total_return = (final_balance - initial_balance) / initial_balance * 100

    return {
        'retorno_%': round(total_return, 2),
        'trades': n,
        'win_rate_%': round(win_rate, 2),
        'profit_factor': round(profit_factor, 3),
        'sharpe': round(sharpe, 3),
        'max_drawdown_%': round(max_dd, 2),
        'saldo_final': round(final_balance, 4),
    }


# ---------------------------------------------------------------------------
# Backtests (self-contained para multiprocessing)
# ---------------------------------------------------------------------------

def _run_advanced(args):
    df, params = args
    short_period = params['short_period']
    long_period = params['long_period']
    stop_loss_pct = params['stop_loss_pct']
    take_profit_pct = params['take_profit_pct']
    order_amount = params['order_amount']
    initial_balance = params['initial_balance']

    df = df.copy()
    df['ma_short'] = df['close'].rolling(short_period).mean()
    df['ma_long'] = df['close'].rolling(long_period).mean()
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + gain / loss))
    df['bb_mid'] = df['close'].rolling(20).mean()
    std = df['close'].rolling(20).std()
    df['bb_upper'] = df['bb_mid'] + 2 * std
    df['bb_lower'] = df['bb_mid'] - 2 * std

    balance = initial_balance
    position = None
    entry_price = entry_cost = 0
    trades = []
    equity = [balance]

    for i in range(long_period + 1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        price = row['close']

        if position:
            pnl_pct = (price - entry_price) / entry_price * 100
            exit_sig = False
            if pnl_pct <= -stop_loss_pct:
                exit_sig = True
            elif pnl_pct >= take_profit_pct:
                exit_sig = True
            elif prev['ma_short'] >= prev['ma_long'] and row['ma_short'] < row['ma_long']:
                if row['rsi'] > 30:
                    exit_sig = True
            elif price > row['bb_upper']:
                exit_sig = True

            if exit_sig:
                qty = order_amount / entry_price
                revenue = qty * price * (1 - COMMISSION)
                balance += revenue
                trades.append({'pnl': revenue - entry_cost})
                position = None
        else:
            buy = False
            if prev['ma_short'] <= prev['ma_long'] and row['ma_short'] > row['ma_long']:
                if row['rsi'] < 70:
                    buy = True
            elif price < row['bb_lower']:
                buy = True

            if buy and balance >= order_amount:
                entry_cost = order_amount * (1 + COMMISSION)
                balance -= entry_cost
                entry_price = price
                position = 'long'

        equity.append(balance)

    if position:
        price = df.iloc[-1]['close']
        qty = order_amount / entry_price
        revenue = qty * price * (1 - COMMISSION)
        balance += revenue
        trades.append({'pnl': revenue - entry_cost})
        equity.append(balance)

    m = compute_metrics(trades, initial_balance, balance, equity)
    if m:
        m['params'] = params
    return m


def _run_scalping(args):
    df, params = args
    order_value = params['order_value']
    profit_target = params['profit_target']
    stop_ratio = params['stop_ratio']
    max_hold_bars = params['max_hold_bars']
    mom_threshold = params['mom_threshold']
    initial_balance = params['initial_balance']

    prices = df['close'].values
    balance = initial_balance
    position = None
    entry_price = entry_cost = 0
    entry_bar = 0
    trades = []
    equity = [balance]

    for i in range(5, len(prices)):
        price = prices[i]
        recent = prices[i - 5:i]
        change = (recent[-1] - recent[0]) / recent[0]
        momentum = 'up' if change > mom_threshold else 'neutral'

        if position:
            pnl_pct = (price - entry_price) / entry_price
            bars_held = i - entry_bar
            exit_sig = (pnl_pct >= profit_target or
                        pnl_pct <= -(profit_target * stop_ratio) or
                        bars_held >= max_hold_bars)
            if exit_sig:
                qty = order_value / entry_price
                revenue = qty * price * (1 - COMMISSION)
                balance += revenue
                trades.append({'pnl': revenue - entry_cost})
                position = None
        else:
            if momentum == 'up' and balance >= order_value:
                entry_cost = order_value * (1 + COMMISSION)
                balance -= entry_cost
                entry_price = price
                entry_bar = i
                position = 'long'

        equity.append(balance)

    m = compute_metrics(trades, initial_balance, balance, equity)
    if m:
        m['params'] = params
    return m


def _run_hf(args):
    df, params = args
    order_size = params['order_size']
    profit_target = params['profit_target']
    stop_loss = params['stop_loss']
    max_per_cycle = params['max_per_cycle']
    cycle_bars = params['cycle_bars']
    c1_thresh = params['c1_thresh']
    c5_thresh = params['c5_thresh']
    initial_balance = params['initial_balance']

    prices = df['close'].values
    balance = initial_balance
    position = None
    entry_price = entry_cost = 0
    trades = []
    equity = [balance]
    trade_count = 0
    cycle_start = 0

    for i in range(10, len(prices)):
        if i - cycle_start >= cycle_bars:
            cycle_start = i
            trade_count = 0

        price = prices[i]
        window = prices[i - 10:i]
        std = np.std(window)
        ma10 = np.mean(window)
        volatility = std / ma10 if ma10 > 0 else 0
        c1 = (prices[i] - prices[i - 1]) / prices[i - 1]
        c5 = (prices[i] - prices[i - 5]) / prices[i - 5]

        if position:
            pnl_pct = (price - entry_price) / entry_price
            if pnl_pct >= profit_target or pnl_pct <= -stop_loss:
                qty = order_size / entry_price
                revenue = qty * price * (1 - COMMISSION)
                balance += revenue
                trades.append({'pnl': revenue - entry_cost})
                position = None
                trade_count += 1
        else:
            if (c1 > c1_thresh and c5 > c5_thresh and volatility < 0.01
                    and trade_count < max_per_cycle and balance >= order_size):
                entry_cost = order_size * (1 + COMMISSION)
                balance -= entry_cost
                entry_price = price
                position = 'long'

        equity.append(balance)

    m = compute_metrics(trades, initial_balance, balance, equity)
    if m:
        m['params'] = params
    return m


def _run_grid(args):
    df, params = args
    grid_levels = params['grid_levels']
    price_range_pct = params['price_range_pct']
    order_amount = params['order_amount']
    initial_balance = params['initial_balance']

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
    equity = [balance]
    level_state = ['buy_pending' if g < base_price else 'sell_pending' for g in grid]

    for price in prices[1:]:
        for idx, lp in enumerate(grid):
            if level_state[idx] == 'buy_pending' and price <= lp:
                qty = order_amount / lp
                cost = qty * lp * (1 + COMMISSION)
                if balance >= cost:
                    balance -= cost
                    asset_balance += qty
                    level_state[idx] = 'sell_pending'

            elif level_state[idx] == 'sell_pending' and price >= lp:
                qty = order_amount / lp
                if asset_balance >= qty:
                    revenue = qty * lp * (1 - COMMISSION)
                    pnl = revenue - order_amount * (1 + COMMISSION)
                    balance += revenue
                    asset_balance -= qty
                    level_state[idx] = 'buy_pending'
                    trades.append({'pnl': pnl})

        equity.append(balance + asset_balance * price)

    final = balance + asset_balance * prices[-1]
    m = compute_metrics(trades, initial_balance, final, equity)
    if m:
        m['params'] = params
    return m


# ---------------------------------------------------------------------------
# Grid search runner
# ---------------------------------------------------------------------------

def grid_search(fn, param_grid, df, workers=4):
    keys = list(param_grid.keys())
    combos = list(itertools.product(*param_grid.values()))
    tasks = [(df, dict(zip(keys, c))) for c in combos]

    results = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fn, t): t for t in tasks}
        for i, future in enumerate(as_completed(futures), 1):
            r = future.result()
            if r:
                results.append(r)
            if i % 50 == 0 or i == len(tasks):
                print(f"  {i}/{len(tasks)} combinações testadas...", end='\r')

    print()
    results.sort(key=lambda x: (x['profit_factor'], x['sharpe']), reverse=True)
    return results


def top_table(results, n=5):
    if not results:
        print("  Nenhum resultado válido (mínimo 5 trades não atingido).")
        return
    for i, r in enumerate(results[:n], 1):
        params_str = ', '.join(f"{k}={v}" for k, v in r['params'].items()
                               if k != 'initial_balance' and k != 'order_amount'
                               and k != 'order_value' and k != 'order_size')
        print(f"\n  #{i}  retorno={r['retorno_%']:+.2f}%  win={r['win_rate_%']:.0f}%  "
              f"PF={r['profit_factor']:.2f}  sharpe={r['sharpe']:.2f}  "
              f"DD={r['max_drawdown_%']:.1f}%  trades={r['trades']}")
        print(f"       params: {params_str}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not API_KEY or not API_SECRET:
        print("Erro: credenciais não configuradas no .env")
        sys.exit(1)

    client = Client(API_KEY, API_SECRET)

    print("Buscando dados históricos...")
    df_trx_15m = fetch_klines(client, 'TRXUSDT', Client.KLINE_INTERVAL_15MINUTE, days=180)
    df_btc_15m = fetch_klines(client, 'BTCUSDT', Client.KLINE_INTERVAL_15MINUTE, days=180)
    df_trx_1m  = fetch_klines(client, 'TRXUSDT', Client.KLINE_INTERVAL_1MINUTE,  days=60)
    df_trx_3m  = fetch_klines(client, 'TRXUSDT', Client.KLINE_INTERVAL_3MINUTE,  days=60)
    print(f"  TRXUSDT 15m: {len(df_trx_15m)} candles")
    print(f"  BTCUSDT 15m: {len(df_btc_15m)} candles")
    print(f"  TRXUSDT  1m: {len(df_trx_1m)} candles")
    print(f"  TRXUSDT  3m: {len(df_trx_3m)} candles")

    all_results = {}

    # ---- Advanced: TRXUSDT ----
    print("\n[1/5] Otimizando Advanced Bot (TRXUSDT 15m) ...")
    param_grid = {
        'short_period':    [5, 7, 9, 12],
        'long_period':     [20, 25, 30, 40, 50],
        'stop_loss_pct':   [1.0, 1.5, 2.0, 3.0],
        'take_profit_pct': [2.0, 3.0, 5.0, 7.0, 10.0],
        'order_amount':    [2],
        'initial_balance': [10],
    }
    res = grid_search(_run_advanced, param_grid, df_trx_15m)
    print(f"  {len(res)} combinações lucrativas encontradas de {4*5*4*5} testadas")
    top_table(res)
    all_results['advanced_trxusdt'] = res[:10]

    # ---- Advanced: BTCUSDT ----
    print("\n[2/5] Otimizando Advanced Bot (BTCUSDT 15m) ...")
    param_grid['order_amount'] = [10]
    param_grid['initial_balance'] = [100]
    res = grid_search(_run_advanced, param_grid, df_btc_15m)
    print(f"  {len(res)} combinações válidas")
    top_table(res)
    all_results['advanced_btcusdt'] = res[:10]

    # ---- Scalping ----
    print("\n[3/5] Otimizando Scalping Bot (TRXUSDT 1m) ...")
    param_grid = {
        'profit_target':   [0.002, 0.003, 0.005, 0.007, 0.01],
        'stop_ratio':      [0.3, 0.5, 0.7, 1.0],
        'max_hold_bars':   [10, 20, 40, 80],
        'mom_threshold':   [0.0005, 0.001, 0.002],
        'order_value':     [2],
        'initial_balance': [10],
    }
    res = grid_search(_run_scalping, param_grid, df_trx_1m)
    print(f"  {len(res)} combinações válidas")
    top_table(res)
    all_results['scalping_trxusdt'] = res[:10]

    # ---- HF ----
    print("\n[4/5] Otimizando HF Bot (TRXUSDT 3m) ...")
    param_grid = {
        'profit_target': [0.003, 0.005, 0.007, 0.01],
        'stop_loss':     [0.002, 0.003, 0.005],
        'max_per_cycle': [2, 3, 5],
        'cycle_bars':    [50, 100, 200],
        'c1_thresh':     [0.0005, 0.001, 0.002],
        'c5_thresh':     [0.001, 0.002, 0.003],
        'order_size':    [1.0],
        'initial_balance': [10],
    }
    res = grid_search(_run_hf, param_grid, df_trx_3m)
    print(f"  {len(res)} combinações válidas")
    top_table(res)
    all_results['hf_trxusdt'] = res[:10]

    # ---- Grid ----
    print("\n[5/5] Otimizando Grid Bot (TRXUSDT 15m) ...")
    param_grid = {
        'grid_levels':     [5, 8, 10, 15, 20],
        'price_range_pct': [1, 2, 3, 5, 7, 10],
        'order_amount':    [2],
        'initial_balance': [100],
    }
    res = grid_search(_run_grid, param_grid, df_trx_15m)
    print(f"  {len(res)} combinações válidas")
    top_table(res)
    all_results['grid_trxusdt'] = res[:10]

    # Serializa params para JSON (converte tipos numpy)
    def to_serializable(obj):
        if isinstance(obj, dict):
            return {k: to_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [to_serializable(i) for i in obj]
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        return obj

    output = {
        'gerado_em': datetime.now().isoformat(),
        'nota': 'Top 10 por profit_factor × sharpe. Mínimo 5 trades exigido.',
        'resultados': to_serializable(all_results),
    }
    with open('optimization_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\nResultados salvos em optimization_results.json")


if __name__ == '__main__':
    main()
