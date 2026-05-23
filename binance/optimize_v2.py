"""
Optimizador v2 do HF Bot — espelha logica real do bot:
- Triple EMA alignment (on/off)
- Stoch RSI filter (on/off, threshold variavel)
- ADX filter (threshold variavel, inclui 0 = off)
- Multi-tier exits (tier1, tier2, trailing)
- Score-based sizing (opcional)

Usa walk-forward: treina em primeiros 70% dos dados, valida em ultimos 30%.
Seleciona params pelo desempenho OUT-OF-SAMPLE (validacao).
"""
import os
import sys
import json
import itertools
from datetime import datetime, timedelta
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
# Data fetch
# ---------------------------------------------------------------------------

def fetch_klines(client, symbol, interval, days=90):
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
# Indicators (vetorizados, calculados UMA VEZ por dataframe)
# ---------------------------------------------------------------------------

def precompute_indicators(df):
    close = df['close']
    high  = df['high']
    low   = df['low']

    df = df.copy()
    df['ema5']  = close.ewm(span=5,  adjust=False).mean()
    df['ema10'] = close.ewm(span=10, adjust=False).mean()
    df['ema21'] = close.ewm(span=21, adjust=False).mean()

    # RSI
    delta = close.diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi   = 100 - (100 / (1 + gain / (loss + 1e-10)))

    # Stoch RSI %K
    rsi_min = rsi.rolling(14).min()
    rsi_max = rsi.rolling(14).max()
    stoch   = 100 * (rsi - rsi_min) / (rsi_max - rsi_min + 1e-10)
    df['stoch_k'] = stoch.rolling(3).mean()

    # ATR
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    df['atr']     = tr.rolling(14).mean()
    df['atr_avg'] = df['atr'].rolling(100).mean()

    # ADX
    dm_plus  = high.diff()
    dm_minus = -low.diff()
    dm_plus  = dm_plus.where((dm_plus > dm_minus) & (dm_plus > 0), 0.0)
    dm_minus = dm_minus.where((dm_minus > dm_plus) & (dm_minus > 0), 0.0)
    atr_val  = tr.rolling(14).mean()
    di_plus  = 100 * dm_plus.rolling(14).mean() / (atr_val + 1e-10)
    di_minus = 100 * dm_minus.rolling(14).mean() / (atr_val + 1e-10)
    dx       = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus + 1e-10)
    df['adx'] = dx.rolling(14).mean()

    df['c1'] = close.pct_change(1)
    df['c5'] = close.pct_change(5)

    return df.dropna()


# ---------------------------------------------------------------------------
# Backtest que espelha hf_bot.py
# ---------------------------------------------------------------------------

def _run_hf_v2(args):
    df, params = args

    tier1      = params['tier1']
    tier2      = params['tier2']
    stop_loss  = params['stop_loss']
    trail_pct  = params['trail_pct']
    c1_thresh  = params['c1_thresh']
    c5_thresh  = params['c5_thresh']
    adx_thresh = params['adx_thresh']
    use_ema    = params['use_ema']
    use_stoch  = params['use_stoch']
    stoch_max  = params['stoch_max']
    atr_mult   = params['atr_mult']
    order_size = params['order_size']
    initial    = params['initial_balance']

    close   = df['close'].values
    ema5    = df['ema5'].values
    ema10   = df['ema10'].values
    ema21   = df['ema21'].values
    stoch_k = df['stoch_k'].values
    adx     = df['adx'].values
    atr     = df['atr'].values
    atr_avg = df['atr_avg'].values
    c1arr   = df['c1'].values
    c5arr   = df['c5'].values

    balance   = initial
    position  = None
    trades    = []
    equity    = [balance]
    tier1_hit = False
    stop_p    = 0.0
    entry_p   = 0.0
    entry_cost = 0.0
    entry_qty  = 0.0

    for i in range(len(df)):
        price = close[i]

        if position:
            pnl_pct = (price - entry_p) / entry_p

            # trailing
            if tier1_hit:
                new_stop = price * (1 - trail_pct)
                if new_stop > stop_p:
                    stop_p = new_stop

            # stop loss
            if price <= stop_p:
                revenue = entry_qty * price * (1 - COMMISSION)
                pnl     = revenue - entry_cost
                balance += revenue
                trades.append({'pnl': pnl})
                position = None
                tier1_hit = False
            # tier1
            elif not tier1_hit and pnl_pct >= tier1:
                qty_half      = entry_qty * 0.5
                cost_half     = entry_cost * 0.5
                revenue       = qty_half * price * (1 - COMMISSION)
                balance      += revenue
                trades.append({'pnl': revenue - cost_half})
                entry_qty    *= 0.5
                entry_cost   *= 0.5
                tier1_hit     = True
                stop_p        = entry_p  # break-even
            # tier2
            elif tier1_hit and pnl_pct >= tier2:
                revenue = entry_qty * price * (1 - COMMISSION)
                balance += revenue
                trades.append({'pnl': revenue - entry_cost})
                position = None
                tier1_hit = False
        else:
            # Entry signal
            c1  = c1arr[i]
            c5  = c5arr[i]
            momentum_ok = (c1 > c1_thresh) and (c5 > c5_thresh)
            ema_ok      = (not use_ema) or (ema5[i] > ema10[i] > ema21[i])
            trend_ok    = (adx_thresh == 0) or (adx[i] >= adx_thresh)
            stoch_ok    = (not use_stoch) or (stoch_k[i] < stoch_max)
            atr_ok      = atr[i] <= atr_avg[i] * atr_mult

            if momentum_ok and ema_ok and trend_ok and stoch_ok and atr_ok and balance >= order_size:
                entry_qty  = order_size / price
                entry_cost = order_size * (1 + COMMISSION)
                balance   -= entry_cost
                entry_p    = price
                stop_p     = price * (1 - stop_loss)
                tier1_hit  = False
                position   = 'long'

        equity.append(balance + (entry_qty * price if position else 0))

    # Fechar posição aberta no final (marked-to-market)
    if position:
        revenue = entry_qty * close[-1] * (1 - COMMISSION)
        balance += revenue
        trades.append({'pnl': revenue - entry_cost})

    n = len(trades)
    if n < 5:
        return None

    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    win_rate = len(wins) / n * 100
    gross_win = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))
    pf = gross_win / gross_loss if gross_loss > 0 else 999.0

    eq = pd.Series(equity)
    returns = eq.pct_change().dropna()
    sharpe = (returns.mean() / returns.std() * np.sqrt(252 * 24 * 20)) if returns.std() > 0 else 0

    peak = eq.cummax()
    max_dd = ((eq - peak) / peak * 100).min()

    total_return = (balance - initial) / initial * 100

    return {
        'retorno_%': round(total_return, 2),
        'trades': n,
        'win_rate_%': round(win_rate, 2),
        'profit_factor': round(pf, 3),
        'sharpe': round(float(sharpe), 3),
        'max_drawdown_%': round(float(max_dd), 2),
        'saldo_final': round(balance, 4),
        'params': params,
    }


# ---------------------------------------------------------------------------
# Grid search runner
# ---------------------------------------------------------------------------

def grid_search(param_grid, df, workers=4, label=""):
    keys = list(param_grid.keys())
    combos = list(itertools.product(*param_grid.values()))
    tasks = [(df, dict(zip(keys, c))) for c in combos]

    print(f"  {label}: {len(tasks)} combinacoes...")
    results = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_run_hf_v2, t): t for t in tasks}
        for i, future in enumerate(as_completed(futures), 1):
            r = future.result()
            if r:
                results.append(r)
            if i % 100 == 0 or i == len(tasks):
                print(f"    {i}/{len(tasks)} processadas", end='\r')

    print()
    return results


def score_result(r):
    """Ranking: profit_factor × sqrt(trades) × (1 + sharpe/10) − penalidade_DD"""
    if not r:
        return -999
    pf = min(r['profit_factor'], 10)  # cap p/ evitar infinitos dominando
    trades = r['trades']
    sharpe = r['sharpe']
    dd = abs(r['max_drawdown_%'])
    return pf * np.sqrt(trades) * (1 + sharpe / 10) - dd * 0.1


def top_table(results, n=5):
    if not results:
        print("  Nenhum resultado valido.")
        return
    results = sorted(results, key=score_result, reverse=True)
    for i, r in enumerate(results[:n], 1):
        p = r['params']
        filters = []
        if p['use_ema']:   filters.append("EMA")
        if p['use_stoch']: filters.append(f"Stoch<{p['stoch_max']}")
        if p['adx_thresh'] > 0: filters.append(f"ADX>={p['adx_thresh']}")
        filters_str = "+".join(filters) if filters else "sem-filtros"
        print(f"  #{i}  ret={r['retorno_%']:+7.2f}%  win={r['win_rate_%']:.0f}%  "
              f"PF={r['profit_factor']:5.2f}  sharpe={r['sharpe']:5.2f}  "
              f"DD={r['max_drawdown_%']:6.1f}%  trades={r['trades']:3d}  "
              f"score={score_result(r):6.2f}")
        print(f"       t1={p['tier1']}  t2={p['tier2']}  SL={p['stop_loss']}  "
              f"c1={p['c1_thresh']}  c5={p['c5_thresh']}  trail={p['trail_pct']}  [{filters_str}]")


# ---------------------------------------------------------------------------
# Walk-forward validation
# ---------------------------------------------------------------------------

def walk_forward(param_grid, df, train_pct=0.7, workers=4):
    """Split 70/30 — otimiza em train, valida em test, retorna resultados do test."""
    split = int(len(df) * train_pct)
    df_train = df.iloc[:split].copy()
    df_test  = df.iloc[split:].copy()

    print(f"\n{'='*70}")
    print(f"Walk-forward split: {len(df_train)} candles treino / {len(df_test)} candles teste")
    print(f"{'='*70}")

    print("\n[TREINO — in-sample]")
    train_results = grid_search(param_grid, df_train, workers=workers, label="treino")
    train_results = sorted(train_results, key=score_result, reverse=True)

    print("\nTop 10 in-sample:")
    top_table(train_results, n=10)

    # Valida top 20 do treino no teste
    top_params = [r['params'] for r in train_results[:20]]
    print(f"\n[TESTE — out-of-sample] validando top-20 do treino...")

    tasks = [(df_test, p) for p in top_params]
    test_results = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_run_hf_v2, t): t for t in tasks}
        for future in as_completed(futures):
            r = future.result()
            if r:
                test_results.append(r)

    test_results = sorted(test_results, key=score_result, reverse=True)
    print("\nTop 10 out-of-sample (validados no teste):")
    top_table(test_results, n=10)

    return train_results, test_results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not API_KEY or not API_SECRET:
        print("Erro: credenciais no .env")
        sys.exit(1)

    client = Client(API_KEY, API_SECRET)

    symbol = os.getenv('BINANCE_SYMBOL', 'TRXUSDT')
    print(f"Buscando {symbol} 3m — 120 dias...")
    df = fetch_klines(client, symbol, Client.KLINE_INTERVAL_3MINUTE, days=120)
    print(f"  {len(df)} candles carregados")

    print("Precomputando indicadores...")
    df = precompute_indicators(df)
    print(f"  {len(df)} candles apos remocao NaN")

    # Grid reduzido, mas com filtros como variaveis
    param_grid = {
        'tier1':      [0.003, 0.005, 0.007],
        'tier2':      [0.007, 0.010, 0.015],
        'stop_loss':  [0.003, 0.005, 0.007],
        'trail_pct':  [0.003],
        'c1_thresh':  [0.001, 0.002, 0.003],
        'c5_thresh':  [0.001, 0.002],
        'adx_thresh': [0, 20, 30],         # 0 = filtro off
        'use_ema':    [True, False],
        'use_stoch':  [True, False],
        'stoch_max':  [80],
        'atr_mult':   [2.0],
        'order_size': [1.0],
        'initial_balance': [10.0],
    }

    total = 1
    for v in param_grid.values():
        total *= len(v)
    print(f"Total de combinacoes: {total}")

    train_res, test_res = walk_forward(param_grid, df, train_pct=0.7, workers=4)

    # Salva melhor OUT-OF-SAMPLE
    if test_res:
        best = test_res[0]
        print("\n" + "="*70)
        print("MELHOR CONFIG (validada out-of-sample):")
        print("="*70)
        print(json.dumps(best, indent=2, default=str))

        with open('optimization_v2_results.json', 'w', encoding='utf-8') as f:
            json.dump({
                'gerado_em':   datetime.now().isoformat(),
                'symbol':      symbol,
                'dias':        120,
                'train_top10': train_res[:10],
                'test_top10':  test_res[:10],
                'melhor':      best,
            }, f, indent=2, default=str, ensure_ascii=False)
        print("\nSalvo em optimization_v2_results.json")


if __name__ == '__main__':
    main()
