import os
import time
import json
import logging
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScalpingBot:
    def __init__(self, config):
        self.config = config
        self.symbol = config.get('symbol', 'TRXUSDT')
        
        self.api_key = config.get('api_key')
        self.api_secret = config.get('api_secret')
        self.paper_mode = config.get('paper_mode', True)
        
        self.spread_threshold = config.get('spread_threshold', 0.002)
        self.profit_target = config.get('profit_target', 0.003)
        self.max_hold_time = config.get('max_hold_time', 60)
        self.order_value = config.get('order_value', 2)
        
        self.client = None
        self.balance = float(config.get('paper_balance', 2.21))
        
        self.position = None
        self.entry_price = 0
        self.entry_time = 0
        
        self.trade_history = []
        
        if not self.paper_mode and self.api_key:
            self.client = Client(self.api_key, self.api_secret)
            self._get_real_balance()
    
    def _get_real_balance(self):
        try:
            account = self.client.get_account()
            for bal in account['balances']:
                if bal['asset'] in ['USDC', 'USDT']:
                    self.balance = float(bal['free'])
                    break
        except:
            pass
    
    def get_order_book(self, limit=10):
        if self.paper_mode:
            return self._paper_order_book()
        
        try:
            depth = self.client.get_order_book(symbol=self.symbol, limit=limit)
            return {
                'bid': float(depth['bids'][0][0]),
                'ask': float(depth['asks'][0][0]),
                'bid_qty': float(depth['bids'][0][1]),
                'ask_qty': float(depth['asks'][0][1])
            }
        except:
            return None
    
    def _paper_order_book(self):
        try:
            if self.client:
                depth = self.client.get_order_book(symbol=self.symbol, limit=5)
                bid = float(depth['bids'][0][0])
                ask = float(depth['asks'][0][0])
            else:
                price = self._get_dummy_price()
                bid = price * 0.9995
                ask = price * 1.0005
        except:
            price = 0.08
            bid = price * 0.9995
            ask = price * 1.0005
        
        return {
            'bid': bid,
            'ask': ask,
            'bid_qty': 1000,
            'ask_qty': 1000
        }
    
    def _get_dummy_price(self):
        np.random.seed(int(time.time()) % 1000)
        base = 0.08
        return base + np.random.randn() * 0.002
    
    def get_current_price(self):
        ob = self.get_order_book()
        if ob:
            return (ob['bid'] + ob['ask']) / 2
        return None
    
    def calculate_spread(self):
        ob = self.get_order_book()
        if not ob:
            return 0
        
        spread = (ob['ask'] - ob['bid']) / ob['bid']
        return spread, ob
    
    def detect_momentum(self):
        prices = []
        for _ in range(5):
            ob = self.get_order_book()
            if ob:
                prices.append((ob['bid'] + ob['ask']) / 2)
            time.sleep(0.5)
        
        if len(prices) < 3:
            return 'neutral'
        
        recent = np.array(prices[-3:])
        change_pct = (recent[-1] - recent[0]) / recent[0]
        
        if change_pct > 0.001:
            return 'up'
        elif change_pct < -0.001:
            return 'down'
        return 'neutral'
    
    def execute_buy(self, price=None):
        if not price:
            ob = self.get_order_book()
            price = ob['ask']
        
        qty = self.order_value / price
        
        if self.paper_mode:
            self.balance -= self.order_value
            self.position = 'long'
            self.entry_price = price
            self.entry_time = time.time()
            
            self.trade_history.append({
                'type': 'BUY',
                'price': price,
                'qty': qty,
                'value': self.order_value,
                'time': datetime.now().isoformat()
            })
            
            logger.info(f"PAPER BUY: {qty} @ ${price:.6f} = ${self.order_value}")
            return {'orderId': f"PAPER_{int(time.time())}"}
        
        try:
            order = self.client.order_market_buy(
                symbol=self.symbol,
                quantity=round(qty, 6)
            )
            self.position = 'long'
            self.entry_price = price
            self.entry_time = time.time()
            return order
        except BinanceAPIException as e:
            logger.error(f"Buy failed: {e}")
            return None
    
    def execute_sell(self, price=None):
        if not price:
            ob = self.get_order_book()
            price = ob['bid']
        
        qty = self.order_value / self.entry_price
        
        if self.paper_mode:
            revenue = qty * price
            pnl = revenue - self.order_value
            self.balance += revenue
            
            self.trade_history.append({
                'type': 'SELL',
                'price': price,
                'qty': qty,
                'value': revenue,
                'pnl': pnl,
                'time': datetime.now().isoformat()
            })
            
            logger.info(f"PAPER SELL: {qty} @ ${price:.6f} = ${revenue:.2f} | PnL: ${pnl:.2f}")
            logger.info(f"Balance: ${self.balance:.2f}")
            
            self.position = None
            self.entry_price = 0
            return {'orderId': f"PAPER_{int(time.time())}"}
        
        try:
            order = self.client.order_market_sell(
                symbol=self.symbol,
                quantity=round(qty, 6)
            )
            self.position = None
            return order
        except BinanceAPIException as e:
            logger.error(f"Sell failed: {e}")
            return None
    
    def check_profit(self):
        if not self.position:
            return False
        
        current = self.get_current_price()
        if not current:
            return False
        
        pnl_pct = (current - self.entry_price) / self.entry_price
        
        hold_time = time.time() - self.entry_time
        
        if pnl_pct >= self.profit_target:
            logger.info(f"Take profit: {pnl_pct*100:.2f}%")
            return True
        
        if hold_time > self.max_hold_time:
            logger.info(f"Time exit: {hold_time:.0f}s")
            return True
        
        if pnl_pct <= -self.profit_target / 2:
            logger.info(f"Stop loss: {pnl_pct*100:.2f}%")
            return True
        
        return False
    
    def run(self, check_interval=2):
        logger.info(f"Starting Scalping Bot: {self.symbol}")
        logger.info(f"Paper Mode: {self.paper_mode}")
        logger.info(f"Starting Balance: ${self.balance:.2f}")
        logger.info(f"Order Value: ${self.order_value}")
        
        try:
            while True:
                spread, ob = self.calculate_spread()
                current = self.get_current_price()
                momentum = self.detect_momentum()
                
                logger.info(f"Price: ${current:.6f} | Spread: {spread*100:.3f}% | Momentum: {momentum} | Pos: {self.position}")
                
                if self.position:
                    if self.check_profit():
                        self.execute_sell()
                
                else:
                    if spread > self.spread_threshold * 2:
                        logger.info("High spread - waiting for stabilization")
                    elif momentum == 'up' and spread > self.spread_threshold:
                        logger.info("Buy signal detected")
                        self.execute_buy()
                    elif momentum == 'down' and spread > self.spread_threshold:
                        logger.info("Sell signal (short) - buying back")
                
                logger.info("-" * 60)
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            logger.info("Bot stopped")
            self.save_state()
    
    def save_state(self):
        state = {
            'position': self.position,
            'entry_price': self.entry_price,
            'balance': self.balance,
            'trade_history': self.trade_history
        }
        with open('scalping_bot_state.json', 'w') as f:
            json.dump(state, f, indent=2)


def main():
    config = {
        'paper_mode': True,
        'symbol': 'TRXUSDT',
        'api_key': os.getenv('BINANCE_API_KEY', ''),
        'api_secret': os.getenv('BINANCE_API_SECRET', ''),
        'spread_threshold': 0.002,
        'profit_target': 0.003,
        'max_hold_time': 60,
        'order_value': 2,
        'paper_balance': 2.21
    }
    
    bot = ScalpingBot(config)
    bot.run(check_interval=3)


if __name__ == '__main__':
    main()