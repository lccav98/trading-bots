"""
Optimizer v4 — grid ampliado com thresholds menores de momentum.
Foco em encontrar config que gere >= 1 trade/dia e passe walk-forward.
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

from optimize_v2 import (
    fetch_klines, precompute_indicators, _run_hf_v2,
    score_result, top_table
)

load_dotenv()
API_KEY = os.getenv('BINANCE_API_KEY', '')
API_SECRET = os.getenv('BINANCE_API_SECRET', '')


def grid_search_df(param_grid, df, workers=4):
    keys = list(param_grid.keys())
    combos = list(itertools.product(*param_grid.values()))
    tasks = [(df, dict(zip(keys, c))) for c in combos]
    results = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_run_hf_v2, t): t for t in tasks}
        for i, future in enumerate(as_completed(futures), 1):
            r = future.result()
            if r:
                results.append(r)
            if i % 200 == 0:
                print(f"    {i}/{len(tasks)}", end='\r')
    print()
    return results


def walk_forward_test(df, param_grid, workers=4):
    split = int(len(df) * 0.7)
    df_train = df.iloc[:split].copy()
    df_test  = df.iloc[split:].copy()
    days_test = (df_test.index[-1] - df_test.index[0]).days
    print(f"\n[WF] train={len(df_train)}c test={len(df_test)}c ({days_test}d)")

    train_res = grid_search_df(param_grid, df_train, workers=workers)
    train_res = sorted(train_res, key=score_result, reverse=True)
    top_params = [r['params'] for r in train_res[:30]]

    tasks = [(df_test, p) for p in top_params]
    test_res = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_run_hf_v2, t): t for t in tasks}
        for future in as_completed(futures):
            r = future.result()
            if r:
                test_res.append(r)
    test_res = sorted(test_res, key=score_result, reverse=True)
    return train_res, test_res, days_test


def main():
    client = Client(API_KEY, API_SECRET)

    # Grid ampliado: thresholds menores + filtro EMA on/off
    param_grid = {
        'tier1':      [0.003, 0.005, 0.008],
        'tier2':      [0.008, 0.015, 0.025],
        'stop_loss':  [0.005, 0.010, 0.015],
        'trail_pct':  [0.005],
        'c1_thresh':  [0.0003, 0.0005, 0.001],   # MENOR
        'c5_thresh':  [0.0005, 0.001, 0.002],    # MENOR
        'adx_thresh': [0],                        # off
        'use_ema':    [True, False],              # ambos
        'use_stoch':  [False],
        'stoch_max':  [80],
        'atr_mult':   [2.0],
        'order_size': [1.0],
        'initial_balance': [10.0],
    }
    total = 1
    for v in param_grid.values():
        total *= len(v)
    print(f"Total combinacoes: {total}")

    configs = [
        ('TRXUSDT', Client.KLINE_INTERVAL_5MINUTE,  '5m',  90),
        ('TRXUSDT', Client.KLINE_INTERVAL_15MINUTE, '15m', 180),
    ]

    all_results = {}
    for symbol, interval, tf_label, days in configs:
        label = f"{symbol}_{tf_label}"
        print(f"\n{'='*60}\n{label} ({days}d)\n{'='*60}")
        df = fetch_klines(client, symbol, interval, days=days)
        df = precompute_indicators(df)
        print(f"  {len(df)} candles")

        train_res, test_res, test_days = walk_forward_test(df, param_grid)
        if test_res:
            # Pega a melhor que tenha >= 1 trade/dia no teste
            min_trades = max(test_days, 5)
            filtered = [r for r in test_res if r['trades'] >= min_trades and r['retorno_%'] > 0]
            if filtered:
                best = filtered[0]
                rank = "OK"
            else:
                best = test_res[0]
                rank = f"BEST-AVAIL (sem config c/ >={min_trades} trades lucrativas)"
            print(f"\n  [{rank}] ret={best['retorno_%']:+.2f}%  PF={best['profit_factor']:.2f}  "
                  f"win={best['win_rate_%']:.0f}%  trades={best['trades']}  sharpe={best['sharpe']:.2f}")
            p = best['params']
            print(f"  params: tier1={p['tier1']} tier2={p['tier2']} SL={p['stop_loss']} "
                  f"c1={p['c1_thresh']} c5={p['c5_thresh']} EMA={p['use_ema']}")

            all_results[label] = {
                'best': best,
                'min_trades_required': min_trades,
                'top_test': test_res[:5],
            }

    # Escolhe GLOBAL: melhor score entre labels
    best_overall = None
    for label, r in all_results.items():
        if r['best']['retorno_%'] > 0 and r['best']['profit_factor'] > 1.1:
            if best_overall is None or score_result(r['best']) > score_result(best_overall['best']):
                best_overall = r
                best_overall['label'] = label

    print(f"\n{'='*60}\nRESUMO\n{'='*60}")
    for label, r in all_results.items():
        b = r['best']
        print(f"  {label}: ret={b['retorno_%']:+.2f}%  PF={b['profit_factor']:.2f}  "
              f"trades={b['trades']:3d}  c1={b['params']['c1_thresh']}  c5={b['params']['c5_thresh']}")

    if best_overall:
        print(f"\nVENCEDOR: {best_overall['label']}")
        print(json.dumps(best_overall['best'], indent=2, default=str))

    with open('optimization_v4_results.json', 'w') as f:
        json.dump({
            'gerado_em': datetime.now().isoformat(),
            'all_results': all_results,
            'best_overall': best_overall,
        }, f, indent=2, default=str)


if __name__ == '__main__':
    main()
