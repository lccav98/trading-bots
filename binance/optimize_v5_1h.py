"""Walk-forward TRXUSDT 1h para capturar movimentos de medio prazo."""
import os, sys, itertools
from concurrent.futures import ProcessPoolExecutor, as_completed
from binance.client import Client
from dotenv import load_dotenv
from optimize_v2 import fetch_klines, precompute_indicators, _run_hf_v2, score_result

load_dotenv()

def main():
    client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
    print("Baixando TRXUSDT 1h, 365d...")
    df = fetch_klines(client, 'TRXUSDT', Client.KLINE_INTERVAL_1HOUR, days=365)
    df = precompute_indicators(df)
    print(f"  {len(df)} candles")

    grid = {
        'tier1':      [0.01, 0.015, 0.025],
        'tier2':      [0.025, 0.04, 0.06],
        'stop_loss':  [0.015, 0.025, 0.04],
        'trail_pct':  [0.01],
        'c1_thresh':  [0.001, 0.003],
        'c5_thresh':  [0.005, 0.01, 0.02],
        'adx_thresh': [0, 20],
        'use_ema':    [True, False],
        'use_stoch':  [False],
        'stoch_max':  [80],
        'atr_mult':   [2.0],
        'order_size': [1.0],
        'initial_balance': [10.0],
    }
    keys = list(grid.keys())
    combos = list(itertools.product(*grid.values()))
    print(f"Combinacoes: {len(combos)}")

    split = int(len(df) * 0.7)
    df_train, df_test = df.iloc[:split], df.iloc[split:]
    print(f"train={len(df_train)} test={len(df_test)}")

    tasks_train = [(df_train, dict(zip(keys, c))) for c in combos]
    train_res = []
    with ProcessPoolExecutor(max_workers=4) as ex:
        for r in as_completed({ex.submit(_run_hf_v2, t): t for t in tasks_train}):
            res = r.result()
            if res:
                train_res.append(res)
    train_res.sort(key=score_result, reverse=True)

    top20 = [r['params'] for r in train_res[:20]]
    tasks_test = [(df_test, p) for p in top20]
    test_res = []
    with ProcessPoolExecutor(max_workers=4) as ex:
        for r in as_completed({ex.submit(_run_hf_v2, t): t for t in tasks_test}):
            res = r.result()
            if res:
                test_res.append(res)
    test_res.sort(key=score_result, reverse=True)

    print("\nTop 5 OOS TRXUSDT 1h:")
    for i, r in enumerate(test_res[:5], 1):
        p = r['params']
        print(f"  #{i} ret={r['retorno_%']:+.2f}% PF={r['profit_factor']:.2f} win={r['win_rate_%']:.0f}% "
              f"trades={r['trades']} sharpe={r['sharpe']:.2f}")
        print(f"      t1={p['tier1']} t2={p['tier2']} SL={p['stop_loss']} "
              f"c1={p['c1_thresh']} c5={p['c5_thresh']} EMA={p['use_ema']}")


if __name__ == '__main__':
    main()
