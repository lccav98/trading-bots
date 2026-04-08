import os
import time
import json
import logging
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('binance_grid_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class GridTradingBot:
    def __init__(self, config):
        self.config = config
        self.paper_mode = config.get('paper_mode', True)
        self.symbol = config.get('symbol', 'BTCUSDT')
        self.grid_levels = config.get('grid_levels', 10)
        self.price_range_pct = config.get('price_range_pct', 5)
        self.order_amount = config.get('order_amount', 10)
        self.price_precision = 2
        self.quantity_precision = 4
        
        self.client = None
        self.base_price = None
        self.grid_lines = []
        self.active_orders = []
        self.trade_history = []
        
        if not self.paper_mode:
            api_key = config.get('api_key')
            api_secret = config.get('api_secret')
            if not api_key or not api_secret:
                raise ValueError("API key and secret required for live trading")
            self.client = Client(api_key, api_secret)
            self.client.API_URL = 'https://testnet.binance.vision/api'
        
        self.balances = {'USDT': float(config.get('paper_balance', 100))}
        
    def get_current_price(self):
        if self.paper_mode:
            return self._get_paper_price()
        
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            logger.error(f"Error fetching price: {e}")
            return None
    
    def _get_paper_price(self):
        if self.paper_mode and self.client:
            try:
                ticker = self.client.get_symbol_ticker(symbol=self.symbol)
                return float(ticker['price'])
            except:
                return 50000
        return 50000
    
    def calculate_grid_levels(self):
        current_price = self.get_current_price()
        if not current_price:
            return False
        
        self.base_price = current_price
        range_half = self.price_range_pct / 100 * current_price
        lower = current_price - range_half
        upper = current_price + range_half
        
        self.grid_lines = []
        step = (upper - lower) / (self.grid_levels - 1)
        
        for i in range(self.grid_levels):
            price = lower + (i * step)
            self.grid_lines.append({
                'level': i,
                'price': round(price, self.price_precision),
                'buy_order': None,
                'sell_order': None
            })
        
        logger.info(f"Grid levels calculated: {lower:.2f} - {upper:.2f}")
        logger.info(f"Grid lines: {[g['price'] for g in self.grid_lines]}")
        return True
    
    def place_buy_order(self, level_index):
        if self.paper_mode:
            return self._paper_buy_order(level_index)
        
        level = self.grid_lines[level_index]
        if level['buy_order']:
            return None
        
        try:
            order = self.client.order_limit_buy(
                symbol=self.symbol,
                quantity=self._calculate_quantity(level['price']),
                price=level['price']
            )
            level['buy_order'] = order['orderId']
            logger.info(f"Buy order placed at {level['price']}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Buy order failed: {e}")
            return None
    
    def place_sell_order(self, level_index):
        if self.paper_mode:
            return self._paper_sell_order(level_index)
        
        level = self.grid_lines[level_index]
        if level['sell_order']:
            return None
        
        try:
            order = self.client.order_limit_sell(
                symbol=self.symbol,
                quantity=self._calculate_quantity(level['price']),
                price=level['price']
            )
            level['sell_order'] = order['orderId']
            logger.info(f"Sell order placed at {level['price']}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Sell order failed: {e}")
            return None
    
    def _calculate_quantity(self, price):
        quantity = self.order_amount / price
        return round(quantity, self.quantity_precision)
    
    def _paper_buy_order(self, level_index):
        level = self.grid_lines[level_index]
        quantity = self._calculate_quantity(level['price'])
        cost = quantity * level['price']
        
        if self.balances.get('USDT', 0) >= cost:
            self.balances['USDT'] -= cost
            asset = self.symbol.replace('USDT', '')
            self.balances[asset] = self.balances.get(asset, 0) + quantity
            level['buy_order'] = f"PAPER_{level_index}_{int(time.time())}"
            
            self.trade_history.append({
                'type': 'BUY',
                'price': level['price'],
                'quantity': quantity,
                'cost': cost,
                'time': datetime.now().isoformat()
            })
            
            logger.info(f"PAPER BUY: {quantity} @ {level['price']} = ${cost:.2f}")
            logger.info(f"Balances: {self.balances}")
            return {'orderId': level['buy_order']}
        return None
    
    def _paper_sell_order(self, level_index):
        level = self.grid_lines[level_index]
        quantity = self._calculate_quantity(level['price'])
        asset = self.symbol.replace('USDT', '')
        
        if self.balances.get(asset, 0) >= quantity:
            self.balances[asset] -= quantity
            revenue = quantity * level['price']
            self.balances['USDT'] += revenue
            level['sell_order'] = f"PAPER_{level_index}_{int(time.time())}"
            
            self.trade_history.append({
                'type': 'SELL',
                'price': level['price'],
                'quantity': quantity,
                'revenue': revenue,
                'profit': revenue - (quantity * level['price']),
                'time': datetime.now().isoformat()
            })
            
            logger.info(f"PAPER SELL: {quantity} @ {level['price']} = ${revenue:.2f}")
            logger.info(f"Balances: {self.balances}")
            return {'orderId': level['sell_order']}
        return None
    
    def check_orders(self):
        if self.paper_mode:
            return self._check_paper_orders()
        
        for level in self.grid_lines:
            if level['buy_order']:
                try:
                    order = self.client.get_order(
                        symbol=self.symbol,
                        orderId=level['buy_order']
                    )
                    if order['status'] == 'FILLED':
                        self.place_sell_order(level['level'])
                        level['buy_order'] = None
                except:
                    pass
            
            if level['sell_order']:
                try:
                    order = self.client.get_order(
                        symbol=self.symbol,
                        orderId=level['sell_order']
                    )
                    if order['status'] == 'FILLED':
                        self.place_buy_order(level['level'])
                        level['sell_order'] = None
                except:
                    pass
    
    def _check_paper_orders(self):
        current_price = self.get_current_price()
        
        for level in self.grid_lines:
            if level['buy_order'] and current_price <= level['price']:
                self.place_sell_order(level['level'])
                level['buy_order'] = None
                logger.info(f"Paper buy filled at {level['price']}")
            
            if level['sell_order'] and current_price >= level['price']:
                self.place_buy_order(level['level'])
                level['sell_order'] = None
                logger.info(f"Paper sell filled at {level['price']}")
    
    def initialize_grid(self):
        middle = self.grid_levels // 2
        for i in range(middle, self.grid_levels):
            self.place_buy_order(i)
        
        for i in range(0, middle):
            self.place_sell_order(i)
    
    def run(self, check_interval=5):
        logger.info(f"Starting Grid Trading Bot - {self.symbol}")
        logger.info(f"Paper Mode: {self.paper_mode}")
        
        if not self.calculate_grid_levels():
            logger.error("Failed to calculate grid levels")
            return
        
        self.initialize_grid()
        
        try:
            while True:
                self.check_orders()
                current = self.get_current_price()
                if current:
                    logger.info(f"Current price: {current}")
                time.sleep(check_interval)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            self.save_state()
    
    def save_state(self):
        state = {
            'grid_lines': self.grid_lines,
            'balances': self.balances,
            'trade_history': self.trade_history
        }
        with open('bot_state.json', 'w') as f:
            json.dump(state, f, indent=2)
        logger.info("State saved")


def main():
    config = {
        'paper_mode': True,
        'symbol': 'BTCUSDT',
        'grid_levels': 10,
        'price_range_pct': 5,
        'order_amount': 10,
        'paper_balance': 100,
        'api_key': os.getenv('BINANCE_API_KEY', ''),
        'api_secret': os.getenv('BINANCE_API_SECRET', '')
    }
    
    bot = GridTradingBot(config)
    bot.run(check_interval=10)


if __name__ == '__main__':
    main()