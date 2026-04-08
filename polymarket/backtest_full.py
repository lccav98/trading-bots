import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import json
import random
import requests
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from indicators.vwap import compute_session_vwap, compute_vwap_series
from indicators.rsi import compute_rsi, sma, slope_last
from indicators.macd import compute_macd
from indicators.heiken_ashi import compute_heiken_ashi, count_consecutive
from engines.regime import detect_regime
from engines.probability import score_direction, apply_time_awareness
from engines.edge import compute_edge, decide
from indicators.utils import clamp

print("=" * 70)
print("  POLYMARKET BTC 15m BACKTEST - PROFITABILITY + ORDER SIMULATION")
print("=" * 70)

# =============================================================================
# ORDER BOOK & EXECUTION SIMULATION
# =============================================================================

@dataclass
class SimulatedOrderBook:
    """Simulates a Polymarket CLOB order book."""
    token_id: str
    bids: list = field(default_factory=list)
    asks: list = field(default_factory=list)
    tick_size: str = "0.01"
    neg_risk: bool = False
    last_trade_price: str = "0.50"

    @classmethod
    def from_market_price(cls, token_id, yes_price, spread_bps=30):
        spread = yes_price * (spread_bps / 10000)
        best_bid = round(yes_price - spread / 2, 2)
        best_ask = round(yes_price + spread / 2, 2)
        best_bid = max(0.01, min(0.99, best_bid))
        best_ask = max(0.01, min(0.99, best_ask))
        if best_ask <= best_bid:
            best_ask = round(best_bid + 0.01, 2)

        bids = [{"price": str(round(best_bid - i * 0.01, 2)), "size": str(random.uniform(50, 500))}
                for i in range(5)]
        asks = [{"price": str(round(best_ask + i * 0.01, 2)), "size": str(random.uniform(50, 500))}
                for i in range(5)]

        return cls(
            token_id=token_id,
            bids=bids,
            asks=asks,
            last_trade_price=str(yes_price),
        )


@dataclass
class SimulatedOrder:
    """Represents a simulated order."""
    order_id: str
    token_id: str
    side: str
    price: float
    size: float
    status: str = "pending"
    created_at: float = 0
    filled_at: float = 0
    fill_price: float = 0
    error: str = ""


class OrderExecutionSimulator:
    """Simulates the full order lifecycle: create -> sign -> post -> fill."""

    def __init__(self, fee_rate=0.02, slippage_bps=10, latency_ms=500,
                 signature_fail_rate=0.0, order_reject_rate=0.0):
        self.fee_rate = fee_rate
        self.slippage_bps = slippage_bps
        self.latency_ms = latency_ms
        self.signature_fail_rate = signature_fail_rate
        self.order_reject_rate = order_reject_rate
        self.order_counter = 0
        self.orders = []
        self.signature_failures = 0
        self.order_rejections = 0
        self.total_fees = 0
        self.total_slippage = 0

    def get_order_book(self, token_id, yes_price):
        book = SimulatedOrderBook.from_market_price(token_id, yes_price)
        return book

    def create_and_post_order(self, token_id, side, price, size, book):
        self.order_counter += 1
        order = SimulatedOrder(
            order_id=f"sim-{self.order_counter:06d}",
            token_id=token_id,
            side=side,
            price=price,
            size=size,
            created_at=time.time(),
        )

        if random.random() < self.signature_fail_rate:
            order.status = "signature_failed"
            order.error = "invalid signature"
            self.signature_failures += 1
            self.orders.append(order)
            return order

        if random.random() < self.order_reject_rate:
            order.status = "rejected"
            order.error = "order rejected by exchange"
            self.order_rejections += 1
            self.orders.append(order)
            return order

        slippage = price * (self.slippage_bps / 10000)
        if side == "BUY":
            fill_price = round(price + slippage, 2)
        else:
            fill_price = round(price - slippage, 2)
        fill_price = max(0.01, min(0.99, fill_price))

        order.status = "filled"
        order.fill_price = fill_price
        order.filled_at = time.time()
        self.total_slippage += abs(fill_price - price) * size
        self.orders.append(order)
        return order

    def get_stats(self):
        filled = [o for o in self.orders if o.status == "filled"]
        failed = [o for o in self.orders if o.status == "signature_failed"]
        rejected = [o for o in self.orders if o.status == "rejected"]
        return {
            "total_orders": len(self.orders),
            "filled": len(filled),
            "signature_failures": len(failed),
            "rejected": len(rejected),
            "fill_rate": len(filled) / len(self.orders) if self.orders else 0,
            "total_fees": self.total_fees,
            "total_slippage_cost": self.total_slippage,
        }


# =============================================================================
# DATA FETCHING
# =============================================================================

def fetch_historical_klines(symbol="BTCUSDT", interval="1m", limit=5000):
    print(f"\nFetching {limit} {interval} klines for {symbol}...")
    all_klines = []
    end_time = None
    while len(all_klines) < limit:
        params = {"symbol": symbol, "interval": interval, "limit": min(1000, limit - len(all_klines))}
        if end_time:
            params["endTime"] = end_time
        resp = requests.get("https://api.binance.com/api/v3/klines", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        candles = []
        for k in data:
            candles.append({
                "open_time": k[0], "open": float(k[1]), "high": float(k[2]),
                "low": float(k[3]), "close": float(k[4]), "volume": float(k[5]),
                "close_time": k[6],
            })
        all_klines = candles + all_klines
        end_time = data[0][0] - 1
        time.sleep(0.2)
    print(f"Fetched {len(all_klines)} candles")
    return all_klines


# =============================================================================
# BACKTEST ENGINE
# =============================================================================

def run_backtest():
    print("\n" + "=" * 70)
    print("  STEP 1: Fetching Historical Data")
    print("=" * 70)

    klines = fetch_historical_klines(limit=5000)
    if len(klines) < 240:
        print("Not enough data")
        return

    start_dt = datetime.fromtimestamp(klines[0]["open_time"] / 1000)
    end_dt = datetime.fromtimestamp(klines[-1]["open_time"] / 1000)
    print(f"\nData range: {start_dt} to {end_dt}")
    print(f"Total candles: {len(klines)} ({len(klines)/60:.0f} hours of data)")

    # ========================================================================
    # CONFIGURATION
    # ========================================================================
    print("\n" + "=" * 70)
    print("  STEP 2: Configuration")
    print("=" * 70)

    configs = {
        "CONSERVADOR": {
            "starting_balance": 10.92,
            "position_size_pct": 0.05,
            "min_edge": 0.25,
            "max_trades_per_hour": 2,
            "stop_loss_pct": 0.40,
            "require_regime": "TREND_UP",
            "allow_down_signals": False,
            "require_strong": True,
            "min_indicator_agreement": 4,
            "avoid_high_volatility": True,
            "volatility_threshold": 0.02,
            "fee_rate": 0.02,
            "slippage_bps": 10,
            "signature_fail_rate": 0.0,
            "order_reject_rate": 0.0,
        },
        "MODERADO": {
            "starting_balance": 10.92,
            "position_size_pct": 0.10,
            "min_edge": 0.15,
            "max_trades_per_hour": 5,
            "stop_loss_pct": 0.50,
            "require_regime": None,
            "allow_down_signals": True,
            "require_strong": False,
            "min_indicator_agreement": 3,
            "avoid_high_volatility": False,
            "volatility_threshold": 0.03,
            "fee_rate": 0.02,
            "slippage_bps": 15,
            "signature_fail_rate": 0.0,
            "order_reject_rate": 0.0,
        },
        "AGRESSIVO": {
            "starting_balance": 10.92,
            "position_size_pct": 0.15,
            "min_edge": 0.05,
            "max_trades_per_hour": 10,
            "stop_loss_pct": 0.60,
            "require_regime": None,
            "allow_down_signals": True,
            "require_strong": False,
            "min_indicator_agreement": 2,
            "avoid_high_volatility": False,
            "volatility_threshold": 0.05,
            "fee_rate": 0.02,
            "slippage_bps": 20,
            "signature_fail_rate": 0.0,
            "order_reject_rate": 0.05,
        },
    }

    for name in configs:
        c = configs[name]
        print(f"\n  {name}:")
        print(f"    Position size: {c['position_size_pct']*100:.0f}% of balance")
        print(f"    Min edge: {c['min_edge']:.2f}")
        print(f"    Max trades/hr: {c['max_trades_per_hour']}")
        print(f"    Stop loss: {c['stop_loss_pct']*100:.0f}%")
        print(f"    Regime filter: {c['require_regime'] or 'ANY'}")
        print(f"    Min indicator agreement: {c['min_indicator_agreement']}/4")

    # ========================================================================
    # RUN BACKTEST FOR EACH CONFIG
    # ========================================================================
    print("\n" + "=" * 70)
    print("  STEP 3: Running Backtests")
    print("=" * 70)

    all_results = {}

    for config_name, cfg in configs.items():
        print(f"\n{'=' * 70}")
        print(f"  Running: {config_name}")
        print(f"{'=' * 70}")

        results = run_single_backtest(klines, cfg, config_name, start_dt, end_dt)
        all_results[config_name] = results

    # ========================================================================
    # COMPARATIVE RESULTS
    # ========================================================================
    print("\n" + "=" * 70)
    print("  COMPARATIVE RESULTS")
    print("=" * 70)

    print(f"\n  {'Config':<15} {'Trades':>7} {'Win%':>7} {'PnL':>10} {'Return%':>9} {'MaxDD%':>8} {'ProfitF':>9} {'Fill%':>7}")
    print(f"  {'-'*15} {'-'*7} {'-'*7} {'-'*10} {'-'*9} {'-'*8} {'-'*9} {'-'*7}")

    for name, results in all_results.items():
        stats = results["stats"]
        print(f"  {name:<15} {stats['total_trades']:>7} {stats['win_rate']:>6.1f}% "
              f"${stats['total_pnl']:>8.2f} {stats['return_pct']:>8.1f}% "
              f"{stats['max_drawdown_pct']:>7.1f}% {stats['profit_factor']:>8.2f} "
              f"{stats['order_stats']['fill_rate']*100:>6.1f}%")

    print(f"\n{'=' * 70}")
    print("  Backtest Complete!")
    print(f"{'=' * 70}")

    return all_results


def check_indicator_agreement(rsi_now, rsi_slope, macd, consec, vwap_now, current_price, vwap_slope, side):
    agreements = 0
    total = 0

    if rsi_now is not None and rsi_slope is not None:
        total += 1
        if side == "UP" and rsi_now > 50 and rsi_slope > 0:
            agreements += 1
        elif side == "DOWN" and rsi_now < 50 and rsi_slope < 0:
            agreements += 1

    if macd is not None:
        total += 1
        if side == "UP" and macd["hist"] > 0 and macd["histDelta"] > 0:
            agreements += 1
        elif side == "DOWN" and macd["hist"] < 0 and macd["histDelta"] < 0:
            agreements += 1

    if consec["color"] is not None:
        total += 1
        if side == "UP" and consec["color"] == "green" and consec["count"] >= 2:
            agreements += 1
        elif side == "DOWN" and consec["color"] == "red" and consec["count"] >= 2:
            agreements += 1

    if vwap_now is not None and vwap_slope is not None:
        total += 1
        if side == "UP" and current_price > vwap_now and vwap_slope > 0:
            agreements += 1
        elif side == "DOWN" and current_price < vwap_now and vwap_slope < 0:
            agreements += 1

    return agreements, total


def simulate_market_prices(btc_price, btc_change_15m, seed=None):
    if seed is not None:
        random.seed(seed)

    yes_price = clamp(0.5 + btc_change_15m * 50 + random.gauss(0, 0.06), 0.15, 0.85)
    no_price = 1.0 - yes_price
    return yes_price, no_price


def run_single_backtest(klines, cfg, config_name, start_dt, end_dt):
    random.seed(42)

    balance = cfg["starting_balance"]
    starting_balance = balance
    trades = []
    equity_curve = [{"time": 0, "balance": balance}]

    candle_window = 15
    lookback = 240
    trade_timestamps = []

    executor = OrderExecutionSimulator(
        fee_rate=cfg["fee_rate"],
        slippage_bps=cfg["slippage_bps"],
        latency_ms=500,
        signature_fail_rate=cfg["signature_fail_rate"],
        order_reject_rate=cfg["order_reject_rate"],
    )

    signals_generated = 0
    signals_filtered = 0
    filter_reasons = {}

    for i in range(lookback, len(klines) - candle_window, candle_window):
        window = klines[max(0, i - lookback):i]
        closes = [c["close"] for c in window]
        if len(closes) < 100:
            continue

        current_price = closes[-1]
        price_15m_ago = closes[-candle_window] if len(closes) >= candle_window else closes[0]
        btc_change_15m = (current_price - price_15m_ago) / price_15m_ago

        volatility = 0
        if len(closes) >= 60:
            returns = [(closes[j] - closes[j - 1]) / closes[j - 1] for j in range(len(closes) - 60, len(closes))]
            volatility = (sum(r ** 2 for r in returns) / len(returns)) ** 0.5

        vwap_series = compute_vwap_series(window)
        vwap_now = vwap_series[-1] if vwap_series else None
        vwap_slope = None
        if vwap_series and len(vwap_series) >= 5:
            vwap_slope = (vwap_series[-1] - vwap_series[-5]) / 5

        rsi_now = compute_rsi(closes, 14)
        rsi_series = []
        for j in range(len(closes)):
            sub = closes[:j + 1]
            r = compute_rsi(sub, 14)
            if r is not None:
                rsi_series.append(r)
        rsi_slope = slope_last(rsi_series, 3) if rsi_series else None

        macd = compute_macd(closes, 12, 26, 9)
        ha = compute_heiken_ashi(window)
        consec = count_consecutive(ha)

        volume_recent = sum(c["volume"] for c in window[-20:]) if len(window) >= 20 else 0
        volume_avg = sum(c["volume"] for c in window[-120:]) / 6 if len(window) >= 120 else 0

        vwap_cross_count = 0
        if vwap_series and len(closes) >= 20:
            for j in range(len(closes) - 19, len(closes)):
                if j > 0 and j < len(vwap_series):
                    prev = closes[j - 1] - vwap_series[j - 1]
                    cur = closes[j] - vwap_series[j]
                    if prev != 0 and ((prev > 0 and cur < 0) or (prev < 0 and cur > 0)):
                        vwap_cross_count += 1

        failed_vwap_reclaim = False
        if vwap_now is not None and len(vwap_series) >= 3:
            failed_vwap_reclaim = closes[-1] < vwap_now and closes[-2] > vwap_series[-2]

        regime = detect_regime(
            price=current_price, vwap=vwap_now, vwap_slope=vwap_slope,
            vwap_cross_count=vwap_cross_count, volume_recent=volume_recent, volume_avg=volume_avg,
        )

        scored = score_direction(
            price=current_price, vwap=vwap_now, vwap_slope=vwap_slope,
            rsi=rsi_now, rsi_slope=rsi_slope, macd=macd,
            heiken_color=consec["color"], heiken_count=consec["count"],
            failed_vwap_reclaim=failed_vwap_reclaim,
        )

        time_left = candle_window
        time_aware = apply_time_awareness(scored["raw_up"], time_left, candle_window)

        market_up, market_down = simulate_market_prices(current_price, btc_change_15m, seed=i)

        edge = compute_edge(
            model_up=time_aware["adjusted_up"], model_down=time_aware["adjusted_down"],
            market_yes=market_up, market_no=market_down,
        )

        rec = decide(
            remaining_minutes=time_left, edge_up=edge["edge_up"], edge_down=edge["edge_down"],
            model_up=time_aware["adjusted_up"], model_down=time_aware["adjusted_down"],
        )

        if rec["action"] == "ENTER":
            side = rec["side"]
            edge_val = edge["edge_up"] if side == "UP" else edge["edge_down"]
            signals_generated += 1

            if cfg["require_strong"] and rec["strength"] != "STRONG":
                signals_filtered += 1
                filter_reasons["not_strong"] = filter_reasons.get("not_strong", 0) + 1
                continue

            if edge_val < cfg["min_edge"]:
                signals_filtered += 1
                filter_reasons["low_edge"] = filter_reasons.get("low_edge", 0) + 1
                continue

            if cfg["require_regime"] and regime["regime"] != cfg["require_regime"]:
                signals_filtered += 1
                filter_reasons["wrong_regime"] = filter_reasons.get("wrong_regime", 0) + 1
                continue

            if not cfg["allow_down_signals"] and side == "DOWN":
                signals_filtered += 1
                filter_reasons["down_blocked"] = filter_reasons.get("down_blocked", 0) + 1
                continue

            agreements, total = check_indicator_agreement(
                rsi_now, rsi_slope, macd, consec, vwap_now, current_price, vwap_slope, side
            )
            if agreements < cfg["min_indicator_agreement"]:
                signals_filtered += 1
                filter_reasons["low_agreement"] = filter_reasons.get("low_agreement", 0) + 1
                continue

            if cfg["avoid_high_volatility"] and volatility > cfg["volatility_threshold"]:
                signals_filtered += 1
                filter_reasons["high_volatility"] = filter_reasons.get("high_volatility", 0) + 1
                continue

            current_hour = klines[i]["open_time"] // 3600000
            recent_trades = [t for t in trade_timestamps if t >= current_hour]
            if len(recent_trades) >= cfg["max_trades_per_hour"]:
                signals_filtered += 1
                filter_reasons["rate_limit"] = filter_reasons.get("rate_limit", 0) + 1
                continue

            order_size = balance * cfg["position_size_pct"]
            if order_size < 0.10:
                continue

            # === ORDER EXECUTION SIMULATION ===
            token_id = f"btc_15m_{side.lower()}_{i}"
            book = executor.get_order_book(token_id, market_up if side == "UP" else market_down)

            if side == "UP":
                entry_price = float(book.asks[0]["price"])
            else:
                entry_price = float(book.bids[0]["price"])

            order = executor.create_and_post_order(token_id, side, entry_price, order_size, book)

            if order.status != "filled":
                trades.append({
                    "time": datetime.fromtimestamp(klines[i]["open_time"] / 1000).isoformat(),
                    "side": side,
                    "size": order_size,
                    "model_up": time_aware["adjusted_up"],
                    "model_down": time_aware["adjusted_down"],
                    "market_up": market_up,
                    "market_down": market_down,
                    "edge": edge_val,
                    "regime": regime["regime"],
                    "phase": rec["phase"],
                    "strength": rec["strength"],
                    "indicator_agreement": f"{agreements}/{total}",
                    "btc_change_15m": btc_change_15m,
                    "actual_direction": "N/A",
                    "won": False,
                    "pnl": 0,
                    "balance": balance,
                    "volatility": volatility,
                    "order_status": order.status,
                    "order_error": order.error,
                    "fill_price": 0,
                    "entry_price": entry_price,
                })
                continue

            # Determine outcome using actual BTC price movement
            price_after = klines[min(i + candle_window, len(klines) - 1)]["close"]
            actual_direction = price_after - current_price
            actual_up = actual_direction > 0

            if side == "UP":
                won = actual_up
            else:
                won = not actual_up

            fill_price = order.fill_price
            shares = order_size / fill_price
            fee = order_size * cfg["fee_rate"]

            if won:
                payout = shares * 1.0
                net_payout = payout - fee - order_size
            else:
                loss = order_size * cfg["stop_loss_pct"]
                net_payout = -loss + fee

            balance += net_payout
            trade_timestamps.append(current_hour)

            trades.append({
                "time": datetime.fromtimestamp(klines[i]["open_time"] / 1000).isoformat(),
                "side": side,
                "size": order_size,
                "model_up": time_aware["adjusted_up"],
                "model_down": time_aware["adjusted_down"],
                "market_up": market_up,
                "market_down": market_down,
                "edge": edge_val,
                "regime": regime["regime"],
                "phase": rec["phase"],
                "strength": rec["strength"],
                "indicator_agreement": f"{agreements}/{total}",
                "btc_change_15m": btc_change_15m,
                "actual_direction": "UP" if actual_up else "DOWN",
                "won": won,
                "pnl": net_payout,
                "balance": balance,
                "volatility": volatility,
                "order_status": order.status,
                "order_error": "",
                "fill_price": fill_price,
                "entry_price": entry_price,
            })

        equity_curve.append({"time": i, "balance": balance})

    # === COMPUTE STATISTICS ===
    wins = [t for t in trades if t["won"]]
    losses = [t for t in trades if not t["won"] and t["order_status"] == "filled"]
    failed_orders = [t for t in trades if t["order_status"] != "filled"]

    total_pnl = balance - starting_balance
    return_pct = (total_pnl / starting_balance) * 100 if starting_balance > 0 else 0

    win_rate = len(wins) / len([t for t in trades if t["order_status"] == "filled"]) * 100 if [t for t in trades if t["order_status"] == "filled"] else 0

    max_drawdown = 0
    peak = starting_balance
    for t in trades:
        if t["balance"] > peak:
            peak = t["balance"]
        dd = (peak - t["balance"]) / peak * 100 if peak > 0 else 0
        if dd > max_drawdown:
            max_drawdown = dd

    gross_wins = sum(t["pnl"] for t in wins)
    gross_losses = abs(sum(t["pnl"] for t in losses))
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else float("inf") if gross_wins > 0 else 0

    order_stats = executor.get_stats()

    stats = {
        "total_trades": len(trades),
        "filled_trades": len([t for t in trades if t["order_status"] == "filled"]),
        "failed_orders": len(failed_orders),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "return_pct": return_pct,
        "max_drawdown_pct": max_drawdown,
        "profit_factor": profit_factor,
        "avg_win": sum(t["pnl"] for t in wins) / len(wins) if wins else 0,
        "avg_loss": sum(t["pnl"] for t in losses) / len(losses) if losses else 0,
        "signals_generated": signals_generated,
        "signals_filtered": signals_filtered,
        "filter_reasons": filter_reasons,
        "order_stats": order_stats,
    }

    # === PRINT RESULTS ===
    print(f"\n  --- {config_name} Results ---")
    print(f"  Period: {start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Starting Balance: ${starting_balance:.2f}")
    print(f"  Final Balance: ${balance:.2f}")
    print(f"  Total PnL: ${total_pnl:.2f} ({return_pct:.1f}%)")
    print(f"  Max Drawdown: {max_drawdown:.1f}%")
    print(f"  Profit Factor: {profit_factor:.2f}")

    print(f"\n  --- Trade Breakdown ---")
    print(f"  Signals Generated: {signals_generated}")
    print(f"  Signals Filtered: {signals_filtered}")
    print(f"  Filled Trades: {stats['filled_trades']}")
    print(f"  Failed Orders: {stats['failed_orders']}")
    print(f"  Wins: {len(wins)} | Losses: {len(losses)}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Avg Win: ${stats['avg_win']:.3f} | Avg Loss: ${stats['avg_loss']:.3f}")

    if filter_reasons:
        print(f"\n  --- Filter Reasons ---")
        for reason, count in sorted(filter_reasons.items(), key=lambda x: -x[1]):
            print(f"    {reason}: {count}")

    print(f"\n  --- Order Execution Stats ---")
    print(f"  Total Orders: {order_stats['total_orders']}")
    print(f"  Fill Rate: {order_stats['fill_rate']*100:.1f}%")
    print(f"  Signature Failures: {order_stats['signature_failures']}")
    print(f"  Rejected Orders: {order_stats['rejected']}")
    print(f"  Slippage Cost: ${executor.total_slippage:.4f}")

    if trades:
        print(f"\n  --- Last 10 Trades ---")
        print(f"  {'Time':<20} {'Side':<5} {'Edge':<6} {'Regime':<12} {'Order':<10} {'Result':<6} {'PnL':<9} {'Balance':<9}")
        print(f"  {'-'*20} {'-'*5} {'-'*6} {'-'*12} {'-'*10} {'-'*6} {'-'*9} {'-'*9}")
        for t in trades[-10:]:
            if t["order_status"] == "filled":
                result = "WIN" if t["won"] else "LOSS"
                order_status = "FILLED"
            else:
                result = "FAIL"
                order_status = t["order_status"][:10]
            print(f"  {t['time'][:19]:<20} {t['side']:<5} {t['edge']:<6.3f} {t['regime']:<12} {order_status:<10} {result:<6} ${t['pnl']:<8.3f} ${t['balance']:<8.2f}")

    return {
        "stats": stats,
        "trades": trades,
        "equity_curve": equity_curve,
        "config": cfg,
    }


if __name__ == "__main__":
    run_backtest()
