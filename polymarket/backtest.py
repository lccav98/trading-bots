import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import random
import requests
from datetime import datetime
from indicators.vwap import compute_session_vwap, compute_vwap_series
from indicators.rsi import compute_rsi, sma, slope_last
from indicators.macd import compute_macd
from indicators.heiken_ashi import compute_heiken_ashi, count_consecutive
from engines.regime import detect_regime
from engines.probability import score_direction, apply_time_awareness
from engines.edge import compute_edge, decide
from indicators.utils import clamp

print("=" * 60)
print("  POLYMARKET BTC 15m BACKTEST (HIGH WR)")
print("=" * 60)

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

def check_indicator_agreement(rsi_now, rsi_slope, macd, consec, vwap_now, current_price, vwap_slope, side):
    """Check if multiple indicators agree with the signal direction."""
    agreements = 0
    total = 0
    
    # RSI agreement
    if rsi_now is not None and rsi_slope is not None:
        total += 1
        if side == "UP" and rsi_now > 50 and rsi_slope > 0:
            agreements += 1
        elif side == "DOWN" and rsi_now < 50 and rsi_slope < 0:
            agreements += 1
    
    # MACD agreement
    if macd is not None:
        total += 1
        if side == "UP" and macd["hist"] > 0 and macd["histDelta"] > 0:
            agreements += 1
        elif side == "DOWN" and macd["hist"] < 0 and macd["histDelta"] < 0:
            agreements += 1
    
    # Heiken Ashi agreement
    if consec["color"] is not None:
        total += 1
        if side == "UP" and consec["color"] == "green" and consec["count"] >= 2:
            agreements += 1
        elif side == "DOWN" and consec["color"] == "red" and consec["count"] >= 2:
            agreements += 1
    
    # VWAP agreement
    if vwap_now is not None and vwap_slope is not None:
        total += 1
        if side == "UP" and current_price > vwap_now and vwap_slope > 0:
            agreements += 1
        elif side == "DOWN" and current_price < vwap_now and vwap_slope < 0:
            agreements += 1
    
    return agreements, total

def run_backtest():
    print("\n" + "=" * 60)
    print("  STEP 1: Fetching Historical Data")
    print("=" * 60)
    
    klines = fetch_historical_klines(limit=5000)
    if len(klines) < 240:
        print("Not enough data")
        return
    
    print(f"\nData range: {datetime.fromtimestamp(klines[0]['open_time']/1000)} to {datetime.fromtimestamp(klines[-1]['open_time']/1000)}")
    
    print("\n" + "=" * 60)
    print("  STEP 2: Running High Win Rate Backtest")
    print("=" * 60)
    
    print("\n  Filters applied:")
    print("  - Only STRONG signals with edge >= 0.25")
    print("  - ALL 4/4 indicators must agree")
    print("  - Only TREND_UP regime")
    print("  - Only UP signals")
    print("  - Position size: 5% of balance")
    print("  - Max 2 trades per hour")
    print("  - Stop loss: -40% of position")
    
    balance = 10.92
    starting_balance = balance
    trades = []
    equity_curve = [{"time": 0, "balance": balance}]
    
    candle_window = 15
    lookback = 240
    fee_rate = 0.02
    max_trades_per_hour = 2
    position_size_pct = 0.05
    min_edge = 0.25
    stop_loss_pct = 0.40
    
    trade_timestamps = []
    
    for i in range(lookback, len(klines) - candle_window, candle_window):
        window = klines[max(0, i-lookback):i]
        closes = [c["close"] for c in window]
        if len(closes) < 100:
            continue
        
        current_price = closes[-1]
        price_15m_ago = closes[-candle_window] if len(closes) >= candle_window else closes[0]
        btc_change_15m = (current_price - price_15m_ago) / price_15m_ago
        
        volatility = 0
        if len(closes) >= 60:
            returns = [(closes[j] - closes[j-1]) / closes[j-1] for j in range(len(closes)-60, len(closes))]
            volatility = (sum(r**2 for r in returns) / len(returns)) ** 0.5
        
        vwap_series = compute_vwap_series(window)
        vwap_now = vwap_series[-1] if vwap_series else None
        vwap_slope = None
        if vwap_series and len(vwap_series) >= 5:
            vwap_slope = (vwap_series[-1] - vwap_series[-5]) / 5
        
        rsi_now = compute_rsi(closes, 14)
        rsi_series = []
        for j in range(len(closes)):
            sub = closes[:j+1]
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
                    prev = closes[j-1] - vwap_series[j-1]
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
        
        market_up = clamp(0.5 + btc_change_15m * 50 + random.gauss(0, 0.06), 0.15, 0.85)
        market_down = 1 - market_up
        
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
            
            # Filter 1: Minimum edge
            if edge_val < min_edge:
                continue
            
            # Filter 2: Only STRONG signals
            if rec["strength"] != "STRONG":
                continue
            
            # Filter 3: No DOWN in TREND_DOWN
            if side == "DOWN" and regime["regime"] == "TREND_DOWN":
                continue
            
            # Filter 4: ALL 4/4 indicators must agree
            agreements, total = check_indicator_agreement(
                rsi_now, rsi_slope, macd, consec, vwap_now, current_price, vwap_slope, side
            )
            if agreements < 4:
                continue
            
            # Filter 5: Only TREND_UP regime
            if regime["regime"] != "TREND_UP":
                continue
            
            # Filter 6: Only UP signals
            if side == "DOWN":
                continue
            
            # Filter 7: Trade rate limit
            current_hour = klines[i]["open_time"] // 3600000
            recent_trades = [t for t in trade_timestamps if t >= current_hour]
            if len(recent_trades) >= max_trades_per_hour:
                continue
            
            # Filter 5: Trade rate limit
            current_hour = klines[i]["open_time"] // 3600000
            recent_trades = [t for t in trade_timestamps if t >= current_hour]
            if len(recent_trades) >= max_trades_per_hour:
                continue
            
            # Filter 6: Avoid high volatility periods
            if volatility > 0.02:
                continue
            
            order_size = balance * position_size_pct
            if order_size < 0.10:
                continue
            
            price_after = klines[min(i + candle_window, len(klines) - 1)]["close"]
            actual_direction = price_after - current_price
            actual_up = actual_direction > 0
            
            if side == "UP":
                buy_price = market_up
                won = actual_up
            else:
                buy_price = market_down
                won = not actual_up
            
            if won:
                shares = order_size / buy_price
                payout = shares * 1.0
                fee = payout * fee_rate
                net_payout = payout - fee - order_size
            else:
                loss = order_size * stop_loss_pct
                net_payout = -loss
            
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
            })
        
        equity_curve.append({"time": i, "balance": balance})
    
    print("\n" + "=" * 60)
    print("  BACKTEST RESULTS")
    print("=" * 60)
    
    print(f"\n  Period: {datetime.fromtimestamp(klines[0]['open_time']/1000).strftime('%Y-%m-%d %H:%M')} to {datetime.fromtimestamp(klines[-1]['open_time']/1000).strftime('%Y-%m-%d %H:%M')}")
    print(f"  Starting Balance: ${starting_balance:.2f}")
    print(f"  Final Balance: ${balance:.2f}")
    print(f"  Total PnL: ${balance - starting_balance:.2f} ({((balance - starting_balance) / starting_balance * 100):.1f}%)")
    
    if trades:
        wins = [t for t in trades if t["won"]]
        losses = [t for t in trades if not t["won"]]
        
        win_rate = len(wins) / len(trades) * 100
        avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t["pnl"] for t in losses) / len(losses) if losses else 0
        
        max_drawdown = 0
        peak = starting_balance
        for t in trades:
            if t["balance"] > peak:
                peak = t["balance"]
            dd = (peak - t["balance"]) / peak * 100
            if dd > max_drawdown:
                max_drawdown = dd
        
        gross_wins = sum(t["pnl"] for t in wins)
        gross_losses = abs(sum(t["pnl"] for t in losses))
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else float('inf')
        
        print(f"\n  --- Trade Statistics ---")
        print(f"  Total Trades: {len(trades)}")
        print(f"  Wins: {len(wins)} ({win_rate:.1f}%)")
        print(f"  Losses: {len(losses)} ({100 - win_rate:.1f}%)")
        print(f"  Avg Win: ${avg_win:.3f}")
        print(f"  Avg Loss: ${avg_loss:.3f}")
        print(f"  Profit Factor: {profit_factor:.2f}")
        print(f"  Max Drawdown: {max_drawdown:.1f}%")
        
        print(f"\n  --- Signal Distribution ---")
        sides = {}
        regimes = {}
        for t in trades:
            sides[t["side"]] = sides.get(t["side"], 0) + 1
            regimes[t["regime"]] = regimes.get(t["regime"], 0) + 1
        print(f"  Sides: {sides}")
        print(f"  Regimes: {regimes}")
        
        win_by_side = {}
        for t in trades:
            if t["side"] not in win_by_side:
                win_by_side[t["side"]] = {"wins": 0, "total": 0}
            win_by_side[t["side"]]["total"] += 1
            if t["won"]:
                win_by_side[t["side"]]["wins"] += 1
        
        print(f"\n  --- Win Rate by Side ---")
        for side, stats in win_by_side.items():
            wr = stats["wins"] / stats["total"] * 100
            print(f"  {side}: {stats['wins']}/{stats['total']} ({wr:.1f}%)")
        
        win_by_regime = {}
        for t in trades:
            if t["regime"] not in win_by_regime:
                win_by_regime[t["regime"]] = {"wins": 0, "total": 0}
            win_by_regime[t["regime"]]["total"] += 1
            if t["won"]:
                win_by_regime[t["regime"]]["wins"] += 1
        
        print(f"\n  --- Win Rate by Regime ---")
        for regime_name, stats in win_by_regime.items():
            wr = stats["wins"] / stats["total"] * 100
            print(f"  {regime_name}: {stats['wins']}/{stats['total']} ({wr:.1f}%)")
        
        win_by_agreement = {}
        for t in trades:
            if t["indicator_agreement"] not in win_by_agreement:
                win_by_agreement[t["indicator_agreement"]] = {"wins": 0, "total": 0}
            win_by_agreement[t["indicator_agreement"]]["total"] += 1
            if t["won"]:
                win_by_agreement[t["indicator_agreement"]]["wins"] += 1
        
        print(f"\n  --- Win Rate by Indicator Agreement ---")
        for agreement, stats in win_by_agreement.items():
            wr = stats["wins"] / stats["total"] * 100
            print(f"  {agreement}: {stats['wins']}/{stats['total']} ({wr:.1f}%)")
        
        print(f"\n  --- Last 15 Trades ---")
        print(f"  {'Time':<20} {'Side':<6} {'Edge':<7} {'Agree':<7} {'Regime':<12} {'Result':<7} {'PnL':<9} {'Balance':<9}")
        print(f"  {'-'*20} {'-'*6} {'-'*7} {'-'*7} {'-'*12} {'-'*7} {'-'*9} {'-'*9}")
        for t in trades[-15:]:
            result = "WIN" if t["won"] else "LOSS"
            print(f"  {t['time'][:19]:<20} {t['side']:<6} {t['edge']:<7.3f} {t['indicator_agreement']:<7} {t['regime']:<12} {result:<7} ${t['pnl']:<8.3f} ${t['balance']:<8.2f}")
    
    print(f"\n{'=' * 60}")
    print("  Backtest Complete!")
    print(f"{'=' * 60}")
    
    return trades, equity_curve

if __name__ == "__main__":
    run_backtest()
