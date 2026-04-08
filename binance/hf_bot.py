import os
import time
import json
import logging
from datetime import datetime
from binance.client import Client
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HighFrequencyBot:
    def __init__(self, config):
        self.config = config
        self.symbol = config.get('symbol', 'TRXUSDT')
        
        self.api_key = config.get('api_key')
        self.api_secret = config.get('api_secret')
        self.paper_mode = config.get('paper_mode', True)
        
        self.order_size = config.get('order_size', 1.5)
        self.profit_target = config.get('profit_target', 0.005)
        self.stop_loss = config.get('stop_loss', 0.003)
        self.max_trades_per_cycle = config.get('max_trades_per_cycle', 3)
        
        self.client = None
        self.balance = float(config.get('paper_balance', 2.21))
        
        self.position = None
        self.entry_price = 0
        self.trade_count = 0
        self.daily_pnl = 0
        
        self.trade_history = []
        
        if not self.paper_mode:
            self.client = Client(self.api_key, self.api_secret)
            self._sync_balance()
    
    def _sync_balance(self):
        try:
            account = self.client.get_account()
            for bal in account['balances']:
                if bal['asset'] in ['USDC', 'USDT']:
                    self.balance = float(bal['free'])
                    break
        except:
            pass
    
    def get_ticker(self):
        if self.paper_mode:
            return self._paper_ticker()
        
        try:
            return self.client.get_symbol_ticker(symbol=self.symbol)
        except:
            return None
    
    def _paper_ticker(self):
        try:
            if self.client:
                return self.client.get_symbol_ticker(symbol=self.symbol)
        except:
            pass
        
        np.random.seed(int(time.time() * 1000) % 1000000)
        base = 0.08
        return {'price': str(base + np.random.randn() * 0.001)}
    
    def get_price(self):
        t = self.get_ticker()
        if t:
            return float(t['price'])
        return None
    
    def get_recent_prices(self, count=10, interval=0.5):
        prices = []
        for _ in range(count):
            p = self.get_price()
            if p:
                prices.append(p)
            time.sleep(interval)
        return prices
    
    def analyze_market(self):
        prices = self.get_recent_prices(10, 0.3)
        
        if len(prices) < 5:
            return 'neutral', {}
        
        prices = np.array(prices)
        
        ma5 = np.mean(prices[-5:])
        ma10 = np.mean(prices)
        std = np.std(prices)
        
        change_1m = (prices[-1] - prices[-2]) / prices[-2] if len(prices) >= 2 else 0
        change_5m = (prices[-1] - prices[0]) / prices[0]
        
        volatility = std / ma10
        
        signal = 'neutral'
        entry_price = prices[-1]
        
        if change_1m > 0.001 and change_5m > 0.002 and volatility < 0.01:
            signal = 'buy'
        elif change_1m < -0.001 and change_5m < -0.002 and volatility < 0.01:
            signal = 'sell'
        
        return signal, {
            'price': entry_price,
            'ma5': ma5,
            'ma10': ma10,
            'volatility': volatility,
            'change_1m': change_1m,
            'change_5m': change_5m,
            'std': std
        }
    
    def execute_order(self, side, price=None):
        if not price:
            price = self.get_price()
        
        qty = self.order_size / price
        
        if self.paper_mode:
            return self._paper_order(side, price, qty)
        
        try:
            if side == 'buy':
                order = self.client.order_market_buy(
                    symbol=self.symbol,
                    quantity=round(qty, 6)
                )
            else:
                order = self.client.order_market_sell(
                    symbol=self.symbol,
                    quantity=round(qty, 6)
                )
            return order
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return None
    
    def _paper_order(self, side, price, qty):
        if side == 'buy':
            self.balance -= self.order_size
            self.position = {'side': 'long', 'price': price, 'qty': qty}
            self.trade_history.append({
                'type': 'BUY',
                'price': price,
                'qty': qty,
                'time': datetime.now().isoformat()
            })
            logger.info(f"PAPER BUY: {qty} @ ${price:.6f}")
        else:
            revenue = qty * price
            pnl = revenue - self.order_size
            self.balance += revenue
            self.daily_pnl += pnl
            
            self.trade_history.append({
                'type': 'SELL',
                'price': price,
                'qty': qty,
                'pnl': pnl,
                'time': datetime.now().isoformat()
            })
            
            logger.info(f"PAPER SELL: {qty} @ ${price:.6f} | PnL: ${pnl:.3f}")
            self.position = None
        
        return {'orderId': f"PAPER_{int(time.time())}"}
    
    def check_exit(self):
        if not self.position:
            return False
        
        current = self.get_price()
        if not current:
            return False
        
        entry = self.position['price']
        pnl_pct = (current - entry) / entry
        
        if pnl_pct >= self.profit_target:
            logger.info(f"Take profit: +{pnl_pct*100:.2f}%")
            return True
        
        if pnl_pct <= -self.stop_loss:
            logger.info(f"Stop loss: {pnl_pct*100:.2f}%")
            return True
        
        return False
    
    def run(self, cycle_duration=300, check_interval=2):
        logger.info(f"Starting HF Bot: {self.symbol}")
        logger.info(f"Paper: {self.paper_mode} | Balance: ${self.balance:.2f}")
        
        cycle_start = time.time()
        
        try:
            while True:
                if time.time() - cycle_start > cycle_duration:
                    logger.info(f"Day ended. PnL: ${self.daily_pnl:.2f}")
                    self.save_state()
                    cycle_start = time.time()
                    self.daily_pnl = 0
                
                signal, data = self.analyze_market()
                price = data.get('price', 0)
                
                logger.info(f"Price: ${price:.6f} | Signal: {signal} | Vol: {data.get('volatility',0)*100:.2f}% | Pos: {self.position is not None}")
                
                if self.position:
                    if self.check_exit():
                        self.execute_order('sell')
                        self.trade_count += 1
                
                elif signal == 'buy' and self.trade_count < self.max_trades_per_cycle:
                    if self.balance >= self.order_size:
                        self.execute_order('buy')
                    else:
                        logger.warning("Insufficient balance")
                
                logger.info(f"Balance: ${self.balance:.2f} | Trades: {self.trade_count}")
                logger.info("-" * 50)
                
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            logger.info("Bot stopped")
            self.save_state()
    
    def save_state(self):
        with open('hf_bot_state.json', 'w') as f:
            json.dump({
                'balance': self.balance,
                'trade_count': self.trade_count,
                'daily_pnl': self.daily_pnl,
                'history': self.trade_history[-20:]
            }, f, indent=2)


def main():
    config = {
        'paper_mode': True,
        'symbol': 'TRXUSDT',
        'api_key': os.getenv('BINANCE_API_KEY', 'gcwxR2FS2BCk73p2ela2aYJeIkINnUI61mQs0BKYwiUeMiwwoND2o0oLGGPds87l'),
        'api_secret': os.getenv('BINANCE_API_SECRET', 'Svxgu8UbDFGPG4IdsA5hMSBgqZ96URBh7Qqr8ZcpdeW1AvuYuL5pYwUJX8KzxOuB'),
        'order_size': 1.0,
        'profit_target': 0.005,
        'stop_loss': 0.003,
        'max_trades_per_cycle': 3,
        'paper_balance': 2.21
    }
    
    bot = HighFrequencyBot(config)
    bot.run(cycle_duration=300, check_interval=3)


if __name__ == '__main__':
    main()