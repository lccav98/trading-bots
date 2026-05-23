"""
Optimizer v3 — testa multiplos (symbol, timeframe) combos para achar edge
que sobreviva walk-forward. Foco em targets maiores (1-2%) para diluir comissao.
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
        for future in as_completed(futures):
            r = future.result()
            if r:
                results.append(r)
    return results


def walk_forward_test(df, param_grid, label, workers=4):
    split = int(len(df) * 0.7)
    df_train = df.iloc[:split].copy()
    df_test  = df.iloc[split:].copy()
    print(f"\n[{label}] train={len(df_train)} test={len(df_test)}")

    train_res = grid_search_df(param_grid, df_train, workers=workers)
    train_res = sorted(train_res, key=score_result, reverse=True)

    top_params = [r['params'] for r in train_res[:20]]
    tasks = [(df_test, p) for p in top_params]
    test_res = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_run_hf_v2, t): t for t in tasks}
        for future in as_completed(futures):
            r = future.result()
            if r:
                test_res.append(r)
    test_res = sorted(test_res, key=score_result, reverse=True)

    if test_res:
        best = test_res[0]
        print(f"  Best OOS: ret={best['retorno_%']:+.2f}%  PF={best['profit_factor']:.2f}  "
              f"win={best['win_rate_%']:.0f}%  trades={best['trades']}  sharpe={best['sharpe']:.2f}")
    return train_res, test_res


def main():
    client = Client(API_KEY, API_SECRET)

    # Grid reduzido com targets MAIORES
    param_grid = {
        'tier1':      [0.005, 0.010, 0.015],
        'tier2':      [0.010, 0.020, 0.030],
        'stop_loss':  [0.005, 0.010, 0.015],
        'trail_pct':  [0.005],
        'c1_thresh':  [0.001, 0.002, 0.004],
        'c5_thresh':  [0.002, 0.005],
        'adx_thresh': [0, 25],
        'use_ema':    [True, False],
        'use_stoch':  [False],
        'stoch_max':  [80],
        'atr_mult':   [2.0],
        'order_size': [1.0],
        'initial_balance': [10.0],
    }
    total = 1
    for v in param_grid.values():
        total *= len(v)
    print(f"Combinacoes por (symbol,tf): {total}")

    test_configs = [
        ('TRXUSDT', Client.KLINE_INTERVAL_5MINUTE,  '5m', 90),
        ('TRXUSDT', Client.KLINE_INTERVAL_15MINUTE, '15m', 180),
        ('BTCUSDT', Client.KLINE_INTERVAL_5MINUTE,  '5m', 90),
        ('BTCUSDT', Client.KLINE_INTERVAL_15MINUTE, '15m', 180),
        ('ETHUSDT', Client.KLINE_INTERVAL_15MINUTE, '15m', 180),
        ('SOLUSDT', Client.KLINE_INTERVAL_15MINUTE, '15m', 180),
    ]

    all_results = {}
    best_overall = None

    for symbol, interval, tf_label, days in test_configs:
        label = f"{symbol}_{tf_label}"
        print(f"\n{'='*70}")
        print(f"Testando {symbol} {tf_label} ({days} dias)")
        print(f"{'='*70}")
        try:
            df = fetch_klines(client, symbol, interval, days=days)
            df = precompute_indicators(df)
            print(f"  {len(df)} candles apos indicadores")
        except Exception as e:
            print(f"  Erro: {e}")
            continue

        train_res, test_res = walk_forward_test(df, param_grid, label)
        if test_res:
            best = test_res[0]
            all_results[label] = {
                'best_oos':  best,
                'train_top3': train_res[:3],
                'test_top3':  test_res[:3],
            }
            if best['retorno_%'] > 0 and best['profit_factor'] > 1.1:
                if best_overall is None or score_result(best) > score_result(best_overall['result']):
                    best_overall = {'label': label, 'result': best, 'symbol': symbol, 'interval': tf_label}

    # Relatorio final
    print(f"\n{'='*70}")
    print("RESUMO — melhor OOS por (symbol, timeframe)")
    print(f"{'='*70}")
    for label, r in all_results.items():
        b = r['best_oos']
        status = "OK" if b['retorno_%'] > 0 and b['profit_factor'] > 1.1 else "FAIL"
        print(f"  [{status}] {label}: ret={b['retorno_%']:+7.2f}%  PF={b['profit_factor']:5.2f}  "
              f"win={b['win_rate_%']:.0f}%  trades={b['trades']:3d}")

    if best_overall:
        print(f"\n{'='*70}")
        print(f"VENCEDOR GLOBAL: {best_overall['label']}")
        print(f"{'='*70}")
        print(json.dumps(best_overall['result'], indent=2, default=str))
    else:
        print("\nNenhuma config passou no walk-forward (ret>0, PF>1.1)")
        print("Possiveis causas: (a) mercado muito ruidoso, (b) estrategia sem edge,")
        print("(c) grid precisa ser mais amplo.")

    with open('optimization_v3_results.json', 'w', encoding='utf-8') as f:
        json.dump({
            'gerado_em':    datetime.now().isoformat(),
            'all_results':  all_results,
            'best_overall': best_overall,
        }, f, indent=2, default=str, ensure_ascii=False)
    print("\nSalvo em optimization_v3_results.json")


if __name__ == '__main__':
    main()
