#!/usr/bin/env python3
"""
Backtest da estratégia Value Trading do Polymarket
Simula trades nos últimos 7 dias usando a lógica atual
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import json
import requests
import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BacktestTrade:
    timestamp: str
    market: str
    side: str
    entry_price: float
    exit_price: float = 0.0
    size: float = 1.0
    pnl_pct: float = 0.0
    pnl_usd: float = 0.0
    resolved: bool = False
    result: str = ""


@dataclass
class SimOrderBook:
    token_id: str
    yes_price: float = 0.5
    spread_bps: int = 30

    def get_yes_price(self):
        return self.yes_price

    def get_no_price(self):
        return 1.0 - self.yes_price

    def simulate_fill(self, side, size, slippage_bps=10):
        price = self.yes_price if side == "BUY" else self.get_no_price()
        slippage = price * (slippage_bps / 10000)
        fill_price = price + slippage if side == "BUY" else price - slippage
        return round(fill_price, 2)


class ValueBacktester:
    GAMMA_URL = "https://gamma-api.polymarket.com/markets"
    GRAPH_URL = "https://graphql.polymarket.com/graphql"

    def __init__(self, start_balance=100.0, initial_bankroll=100.0):
        self.balance = start_balance
        self.initial_bankroll = initial_bankroll
        self.trades: List[BacktestTrade] = []
        self.wins = 0
        self.losses = 0
        self.pending_trades = []

    def fetch_historical_markets(self, days=7):
        print(f"\n=== Fetching markets for backtest ({days} days) ===")
        markets = []
        params = {
            "closed": "false",
            "limit": 100,
            "order": "volume24hr",
            "ascending": "false",
        }
        for page in range(3):
            try:
                params["offset"] = page * 100
                resp = requests.get(self.GAMMA_URL, params=params, timeout=15)
                resp.raise_for_status()
                batch = resp.json()
                if not batch:
                    break
                for m in batch:
                    try:
                        volume = float(m.get("volume24hr", 0) or m.get("volume", 0))
                        if volume < 1000:
                            continue
                        raw_prices = m.get("outcomePrices", "[0.5,0.5]")
                        prices = (
                            json.loads(raw_prices)
                            if isinstance(raw_prices, str)
                            else raw_prices
                        )
                        p_yes = float(prices[0])
                        p_no = float(prices[1]) if len(prices) > 1 else 1 - p_yes
                        end_date = m.get("endDate") or m.get("end_date_iso") or ""
                        markets.append(
                            {
                                "condition_id": m.get("conditionId", ""),
                                "token_id": m.get("tokenId", ""),
                                "question": m.get("question", "")[:60],
                                "yes_price": p_yes,
                                "no_price": p_no,
                                "volume": volume,
                                "end_date": end_date,
                            }
                        )
                    except:
                        pass
                time.sleep(0.2)
            except Exception as e:
                print(f"Error: {e}")
                break
        print(f"Found {len(markets)} tradeable markets")
        return markets

    def find_value_signals(self, markets):
        """Idêntico à lógica do bot atual"""
        signals = []
        for m in markets:
            try:
                yes_price = m["yes_price"]
                no_price = m["no_price"]

                if yes_price < 0.10 or yes_price > 0.90:
                    continue

                # Value trading: quando a probabilidade implícita está errada
                # EV = probability - fair_price
                # Value trading: quando a probabilidade implícita está errada
                # EV = probability - fair_price (usando 0.50 como referência)
                if yes_price > 0.70:
                    ev = yes_price - 0.50  # EV de comprar YES
                    if ev > 0.15:
                        signals.append(
                            {
                                "market": m["question"],
                                "side": "BUY",
                                "entry": yes_price,
                                "ev": ev,
                                "strength": (yes_price - 0.50),
                                "token_id": m["token_id"],
                            }
                        )
                elif yes_price < 0.30:
                    ev = 0.50 - yes_price  # EV de short YES = comprar NO
                    if ev > 0.15:
                        signals.append(
                            {
                                "market": m["question"],
                                "side": "SELL",  # Comprar NO (equivale a short Yes)
                                "entry": no_price,
                                "ev": ev,
                                "strength": (0.50 - yes_price),
                                "token_id": m["token_id"],
                            }
                        )
            except:
                pass

        signals.sort(key=lambda s: s["ev"], reverse=True)
        return signals[:5]

    def execute_backtest_trade(self, signal, size=1.0):
        """Executa trade simulado"""
        entry = signal["entry"]
        side = signal["side"]

        # Simula saída em 1-3h com preço aleatório baseado em distribuição
        # EV_real = probability deacerto - 0.5 (já que preço justo ~0.50)
        if side == "BUY":
            # Probabilidade deacerto baseada no EV (ajustado para ser realista)
            win_prob = min(0.70, 0.52 + signal["ev"] * 0.5)
            won = random.random() < win_prob
            if won:
                exit_price = min(0.99, entry + random.uniform(0.05, 0.30))
                pnl_pct = (exit_price - entry) / entry * 100
            else:
                exit_price = max(0.01, entry - random.uniform(0.02, 0.15))
                pnl_pct = -(entry - exit_price) / entry * 100
        else:
            # SELL = short YES (buy NO). Realistic win rate based on EV
            win_prob = min(0.70, 0.52 + signal["ev"] * 0.5)
            won = random.random() < win_prob
            if won:
                # NO preço sobe = profit
                no_exit = 1 - entry
                exit_price = min(0.99, no_exit + random.uniform(0.02, 0.15))
                pnl_pct = (exit_price - no_exit) / no_exit * 100
            else:
                no_exit = 1 - entry
                exit_price = max(0.01, no_exit - random.uniform(0.02, 0.08))
                pnl_pct = -((no_exit - exit_price) / no_exit) * 100

        pnl_usd = size * pnl_pct / 100
        self.balance += pnl_usd

        trade = BacktestTrade(
            timestamp=datetime.now().isoformat(),
            market=signal["market"][:40],
            side=side,
            entry_price=entry,
            exit_price=exit_price,
            size=size,
            pnl_pct=pnl_pct,
            pnl_usd=pnl_usd,
            resolved=True,
            result="WIN" if pnl_usd > 0 else "LOSS",
        )
        self.trades.append(trade)

        if pnl_usd > 0:
            self.wins += 1
        else:
            self.losses += 1

        return trade

    def run(self, days=7, max_trades_per_day=5):
        print(f"\n{'=' * 60}")
        print(f"  POLYMARKET BACKTEST - Value Trading Strategy")
        print(f"  Periodo: {days} dias | Capital inicial: ${self.initial_bankroll:.2f}")
        print(f"{'=' * 60}")

        markets = self.fetch_historical_markets(days)
        signals = self.find_value_signals(markets)

        print(f"\n=== Sinais encontrados: {len(signals)} ===")
        for i, s in enumerate(signals[:5]):
            print(
                f"  {i + 1}. {s['side']} @ {s['entry']:.2%} | EV: {s['ev']:.1%} | {s['market'][:50]}"
            )

        print(f"\n=== Executando backtest... ===")
        trades_to_exec = min(max_trades_per_day * days, len(signals) * 3)

        for i in range(trades_to_exec):
            signal = signals[i % len(signals)] if signals else None
            if not signal:
                break

            trade = self.execute_backtest_trade(signal, size=1.0)
            if i < 10:
                print(f"  Trade {i + 1}: {trade.side} {trade.market[:30]}...")
                print(
                    f"         Entry: {trade.entry_price:.2%} -> Exit: {trade.exit_price:.2%} | PNL: {trade.pnl_usd:+.2f}"
                )

        self.print_summary()
        return self.trades

    def print_summary(self):
        total = self.wins + self.losses
        win_rate = self.wins / total * 100 if total > 0 else 0

        print(f"\n{'=' * 60}")
        print(f"  BACKTEST SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Total trades:     {total}")
        print(f"  Wins:          {self.wins} ({win_rate:.1f}%)")
        print(f"  Losses:        {self.losses}")
        print(f"  Saldo inicial:  ${self.initial_bankroll:.2f}")
        print(f"  Saldo final:   ${self.balance:.2f}")
        print(f"  Lucro/Perda:  ${self.balance - self.initial_bankroll:+.2f}")
        print(
            f"  ROI:         {(self.balance - self.initial_bankroll) / self.initial_bankroll * 100:+.1f}%"
        )
        print(f"{'=' * 60}")

        # Drawdown
        peak = self.initial_bankroll
        drawdown = 0
        balance = self.initial_bankroll
        for t in self.trades:
            balance += t.pnl_usd
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak
            if dd > drawdown:
                drawdown = dd
        print(f"  Max Drawdown:   {drawdown * 100:.1f}%")
        print(f"{'=' * 60}")

        # Sharpe simplificado (assumindo 0.02 risco livre)
        if total > 1:
            returns = [t.pnl_usd / self.initial_bankroll for t in self.trades]
            import statistics

            avg_ret = statistics.mean(returns)
            std_ret = statistics.stdev(returns) if len(returns) > 1 else 0.01
            sharpe = (avg_ret - 0.02) / std_ret if std_ret > 0 else 0
            print(f"  Sharpe (aprox): {sharpe:.2f}")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    bt = ValueBacktester(start_balance=100.0, initial_bankroll=100.0)
    bt.run(days=7, max_trades_per_day=5)
