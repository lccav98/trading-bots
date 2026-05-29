import time
import logging

logger = logging.getLogger(__name__)


class PositionManager:

    def __init__(self, commission=0.001, quote_asset='USDT'):
        self.position = None
        self.commission = commission
        self.quote_asset = quote_asset

    def is_open(self):
        return self.position is not None

    def open(self, price, qty, cost, stop_loss_pct, tier1_pct, tier2_pct, trail_pct,
             direction='long', symbol='', timeframe='', atr_mult=1.0,
             be_trigger_pct=0.008, be_offset_pct=0.003):
        stop_price = price * (1 - stop_loss_pct) if direction == 'long' else price * (1 + stop_loss_pct)
        self.position = {
            'symbol': symbol,
            'direction': direction,
            'price': price,
            'qty': qty,
            'cost': cost,
            'notional': qty * price,
            'tier1_hit': False,
            'stop_price': stop_price,
            'extreme_price': price,
            'trail_pct': trail_pct,
            'timeframe': timeframe,
            'tier1': tier1_pct,
            'tier2': tier2_pct,
            'entry_time': time.time(),
            'atr_mult': atr_mult,
            'be_trigger_pct': be_trigger_pct,
            'be_offset_pct': be_offset_pct,
        }
        icon = f"⬆️ {direction.upper()}" if direction == 'long' else f"⬇️ {direction.upper()}"
        logger.info(
            f"{icon}  {qty} @ {price:.6f} [{symbol} {timeframe}]  "
            f"stop={stop_price:.6f}  tier1={tier1_pct*100:.1f}%  tier2={tier2_pct*100:.1f}%"
        )

    def check_exit(self, price):
        if not self.position:
            return None

        pos       = self.position
        entry     = pos['price']
        direction = pos.get('direction', 'long')

        if direction == 'long':
            pnl_pct = (price - entry) / entry
            if price > pos.get('extreme_price', entry):
                pos['extreme_price'] = price
            hit_stop = price <= pos['stop_price']
        else:
            pnl_pct = (entry - price) / entry
            if price < pos.get('extreme_price', entry):
                pos['extreme_price'] = price
            hit_stop = price >= pos['stop_price']

        # Time-stop: dar mais tempo para trade se desenvolver
        max_hold_map = {'5m': 30 * 60, '15m': 240 * 60, '1h': 4 * 3600}
        base_hold = max_hold_map.get(pos.get('timeframe', '5m'), 30 * 60)
        # expandir até 50% mais se volatilidade está alta (ATR > média)
        atr_mult = pos.get('atr_mult', 1.0)
        max_hold = base_hold * (1.0 + min(max(atr_mult - 1.0, 0) * 0.5, 0.5))
        elapsed = time.time() - pos.get('entry_time', time.time())
        if elapsed > max_hold:
            if not pos.get('tier1_hit'):
                # If trade is very close to SL, give more time (avoid false breakout)
                if -0.012 <= pnl_pct <= 0.010:
                    return ('time_stop', 1.0)
            else:
                # If tier1 was hit and still in profit, close on time-stop
                if pnl_pct < 0.005:
                    return ('time_stop', 1.0)

        # --- Trailing Stop (move SL to breakeven when profitable) ---
        t1 = pos.get('tier1', 0.008)
        t2 = pos.get('tier2', 0.025)

        # When in profit, move SL to breakeven + 0.3% (guarantee profit)
        # This prevents catastrophic loss when trade turns against us
        be_trigger = pos.get('be_trigger_pct', 0.008)
        be_offset  = pos.get('be_offset_pct', 0.003)
        if not pos.get('breakeven_moved', False):
            if pnl_pct >= be_trigger:
                if direction == 'long':
                    new_stop = entry * (1 + be_offset)  # SL no breakeven + offset
                    if new_stop > pos['stop_price']:
                        pos['stop_price'] = min(new_stop, entry * (1 + be_offset + 0.002))
                        pos['breakeven_moved'] = True
                        logger.info(f"⛑️ Stop indo para breakeven: {pos['stop_price']:.6f}")
                else:
                    new_stop = entry * (1 - be_offset)
                    if new_stop < pos['stop_price']:
                        pos['stop_price'] = max(new_stop, entry * (1 - be_offset - 0.002))
                        pos['breakeven_moved'] = True
                        logger.info(f"⛑️ Stop indo para breakeven: {pos['stop_price']:.6f}")

        # After reaching breakeven, apply aggressive trailing to maximize profit
        if pos.get('breakeven_moved', False) and not pos['tier1_hit']:
            if pnl_pct >= t1 * 0.7 and pnl_pct < t1:
                # Already profitable but not at tier1, trail aggressively at 0.5%
                trail_gap = 0.005
                if direction == 'long':
                    locked_stop = entry * (1 + trail_gap)
                    if locked_stop > pos['stop_price']:
                        pos['stop_price'] = locked_stop
                else:
                    locked_stop = entry * (1 - trail_gap)
                    if locked_stop < pos['stop_price']:
                        pos['stop_price'] = locked_stop

        if hit_stop:
            reason = ('trail_stop' if pos.get('tier1_hit') else
                      'early_trail' if pos.get('breakeven_moved') else
                      'stop_loss')
            return (reason, 1.0)

        # Tier1 - take partial profit
        if not pos['tier1_hit'] and pnl_pct >= t1:
            return ('tp_tier1', 0.5)

        # Tier2 - full close
        if pos['tier1_hit']:
            # Resume trailing after tier1 (keep 1% behind high water mark)
            trail = pos.get('trail_pct', 0.015)
            if direction == 'long':
                new_stop = pos['extreme_price'] * (1 - trail)
                if new_stop > pos['stop_price']:
                    pos['stop_price'] = new_stop
            else:
                new_stop = pos['extreme_price'] * (1 + trail)
                if new_stop < pos['stop_price']:
                    pos['stop_price'] = new_stop
            if pnl_pct >= t2:
                return ('tp_tier2', 1.0)

        return None

    def close_partial(self, fraction, closed_qty=None):
        if not self.position:
            return
        if closed_qty is not None:
            self.position['qty'] -= closed_qty
            self.position['cost'] = self.position['qty'] * self.position['price']
        else:
            self.position['qty']  *= (1 - fraction)
            self.position['cost'] *= (1 - fraction)
        self.position['notional'] = self.position['qty'] * self.position['price']

    def close_full(self):
        pos = self.position.copy()
        self.position = None
        return pos

    def set_tier1_hit(self, entry_price):
        if self.position:
            self.position['tier1_hit']   = True
            self.position['stop_price']  = entry_price
            self.position['extreme_price'] = self.position.get('price', entry_price)

    def to_dict(self):
        if not self.position:
            return None
        return self.position.copy()
