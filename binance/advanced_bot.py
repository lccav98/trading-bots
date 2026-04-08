import os
import time
import json
import logging
import asyncio
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException
import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AdvancedTradingBot:
    def __init__(self, config):
        self.config = config
        self.paper_mode = config.get('paper_mode', True)
        self.symbol = config.get('symbol', 'BTCUSDT')
        
        self.strategy = config.get('strategy', 'ma_crossover')
        
        self.short_period = config.get('short_period', 7)
        self.long_period = config.get('long_period', 25)
        
        self.order_amount = config.get('order_amount', 10)
        self.stop_loss_pct = config.get('stop_loss_pct', 2)
        self.take_profit_pct = config.get('take_profit_pct', 5)
        
        self.client = None
        self.position = None
        self.entry_price = 0
        self.balance = float(config.get('paper_balance', 100))
        
        self.price_precision = 2
        self.quantity_precision = 4
        
        self.trade_history = []
        self.current_price = 0
        
        if not self.paper_mode:
            api_key = config.get('api_key')
            api_secret = config.get('api_secret')
            if not api_key or not api_secret:
                raise ValueError("API key required for live trading")
            self.client = Client(api_key, api_secret)
    
    def get_price_data(self, interval='15m', limit=100):
        if self.paper_mode:
            return self._generate_dummy_data()
        
        try:
            klines = self.client.get_klines(
                symbol=self.symbol,
                interval=interval,
                limit=limit
            )
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])
            
            df['close'] = df['close'].astype(float)
            return df
        except BinanceAPIException as e:
            logger.error(f"Error getting price data: {e}")
            return None
    
    def _generate_dummy_data(self):
        base_price = 50000
        np.random.seed(42)
        
        data = []
        for i in range(100):
            change = np.random.randn() * 200
            base_price += change
            data.append({
                'timestamp': i * 900000,
                'close': base_price
            })
        
        df = pd.DataFrame(data)
        return df
    
    def calculate_ma(self, df):
        df['ma_short'] = df['close'].rolling(window=self.short_period).mean()
        df['ma_long'] = df['close'].rolling(window=self.long_period).mean()
        return df
    
    def calculate_rsi(self, df, period=14):
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        return df
    
    def calculate_bollinger(self, df, period=20):
        df['bb_middle'] = df['close'].rolling(window=period).mean()
        df['bb_std'] = df['close'].rolling(window=period).std()
        df['bb_upper'] = df['bb_middle'] + (2 * df['bb_std'])
        df['bb_lower'] = df['bb_middle'] - (2 * df['bb_std'])
        return df
    
    def generate_signal(self, df):
        if df is None or len(df) < self.long_period:
            return 'HOLD', {}
        
        df = self.calculate_ma(df)
        df = self.calculate_rsi(df)
        df = self.calculate_bollinger(df)
        
        last = df.iloc[-1]
        
        prev_ma_short = df.iloc[-2]['ma_short']
        prev_ma_long = df.iloc[-2]['ma_long']
        curr_ma_short = last['ma_short']
        curr_ma_long = last['ma_long']
        
        signal = 'HOLD'
        reason = {}
        
        if prev_ma_short <= prev_ma_long and curr_ma_short > curr_ma_long:
            if last['rsi'] < 70:
                signal = 'BUY'
                reason = {
                    'ma_cross': 'bullish',
                    'rsi': last['rsi'],
                    'price': last['close']
                }
        
        elif prev_ma_short >= prev_ma_long and curr_ma_short < curr_ma_long:
            if last['rsi'] > 30:
                signal = 'SELL'
                reason = {
                    'ma_cross': 'bearish',
                    'rsi': last['rsi'],
                    'price': last['close']
                }
        
        if last['close'] < last['bb_lower'] and signal == 'HOLD':
            signal = 'BUY'
            reason = {'bb': 'oversold', 'rsi': last['rsi']}
        
        elif last['close'] > last['bb_upper'] and signal == 'HOLD':
            signal = 'SELL'
            reason = {'bb': 'overbought', 'rsi': last['rsi']}
        
        return signal, {
            'price': last['close'],
            'ma_short': last['ma_short'],
            'ma_long': last['ma_long'],
            'rsi': last['rsi'],
            'bb_upper': last['bb_upper'],
            'bb_lower': last['bb_lower'],
            **reason
        }
    
    def check_stop_take(self, current_price):
        if not self.position:
            return None
        
        pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
        
        if self.position == 'LONG':
            if pnl_pct <= -self.stop_loss_pct:
                return 'STOP_LOSS'
            if pnl_pct >= self.take_profit_pct:
                return 'TAKE_PROFIT'
        
        elif self.position == 'SHORT':
            if pnl_pct >= self.stop_loss_pct:
                return 'STOP_LOSS'
            if pnl_pct <= -self.take_profit_pct:
                return 'TAKE_PROFIT'
        
        return None
    
    def execute_buy(self, price):
        quantity = self.order_amount / price
        
        if self.paper_mode:
            self.balance -= self.order_amount
            self.position = 'LONG'
            self.entry_price = price
            
            self.trade_history.append({
                'type': 'BUY',
                'price': price,
                'quantity': quantity,
                'time': datetime.now().isoformat()
            })
            
            logger.info(f"PAPER BUY: {quantity} @ {price}")
            return {'orderId': f"PAPER_BUY_{int(time.time())}"}
        
        try:
            order = self.client.order_market_buy(
                symbol=self.symbol,
                quantity=round(quantity, self.quantity_precision)
            )
            self.position = 'LONG'
            return order
        except BinanceAPIException as e:
            logger.error(f"Buy order failed: {e}")
            return None
    
    def execute_sell(self, price):
        quantity = self.order_amount / price
        
        if self.paper_mode:
            self.balance += self.order_amount * (price / self.entry_price)
            self.trade_history.append({
                'type': 'SELL',
                'price': price,
                'quantity': quantity,
                'pnl': (price - self.entry_price) * quantity,
                'time': datetime.now().isoformat()
            })
            
            logger.info(f"PAPER SELL: {quantity} @ {price}")
            self.position = None
            self.entry_price = 0
            return {'orderId': f"PAPER_SELL_{int(time.time())}"}
        
        try:
            order = self.client.order_market_sell(
                symbol=self.symbol,
                quantity=round(quantity, self.quantity_precision)
            )
            self.position = None
            return order
        except BinanceAPIException as e:
            logger.error(f"Sell order failed: {e}")
            return None
    
    def get_current_price(self):
        if self.paper_mode:
            return 50000 + np.random.randn() * 100
        
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            return float(ticker['price'])
        except:
            return None
    
    def run(self, check_interval=30):
        logger.info(f"Starting Advanced Trading Bot - {self.symbol}")
        logger.info(f"Strategy: {self.strategy}")
        logger.info(f"Paper Mode: {self.paper_mode}")
        
        try:
            while True:
                df = self.get_price_data()
                signal, data = self.generate_signal(df)
                
                current_price = data.get('price', 0)
                
                logger.info(f"Price: {current_price:.2f} | MA Short: {data.get('ma_short', 0):.2f} | MA Long: {data.get('ma_long', 0):.2f} | RSI: {data.get('rsi', 0):.1f}")
                logger.info(f"Signal: {signal} | Position: {self.position}")
                
                exit_reason = self.check_stop_take(current_price)
                if exit_reason:
                    logger.info(f"Exit: {exit_reason}")
                    self.execute_sell(current_price)
                
                elif signal == 'BUY' and not self.position:
                    logger.info(f"Executing BUY")
                    self.execute_buy(current_price)
                
                elif signal == 'SELL' and self.position:
                    logger.info(f"Executing SELL")
                    self.execute_sell(current_price)
                
                logger.info(f"Balance: ${self.balance:.2f}")
                logger.info("-" * 50)
                
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            self.save_state()
    
    def save_state(self):
        state = {
            'position': self.position,
            'entry_price': self.entry_price,
            'balance': self.balance,
            'trade_history': self.trade_history
        }
        with open('advanced_bot_state.json', 'w') as f:
            json.dump(state, f, indent=2)


def main():
    config = {
        'paper_mode': True,
        'symbol': os.getenv('BINANCE_SYMBOL', 'BTCUSDT'),
        'strategy': 'ma_crossover',
        'short_period': 7,
        'long_period': 25,
        'order_amount': 10,
        'stop_loss_pct': 2,
        'take_profit_pct': 5,
        'paper_balance': 100,
        'api_key': os.getenv('BINANCE_API_KEY', ''),
        'api_secret': os.getenv('BINANCE_API_SECRET', '')
    }
    
    bot = AdvancedTradingBot(config)
    bot.run(check_interval=30)


if __name__ == '__main__':
    main()