import sys
sys.path.insert(0, '/Users/luizclaudioaraujo/Library/Python/3.9/lib/python3.9/site-packages')

import os
import json
import logging
from flask import Flask, request, jsonify
from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

API_KEY = os.getenv('BINANCE_API_KEY', '')
API_SECRET = os.getenv('BINANCE_API_SECRET', '')
SYMBOL = os.getenv('BINANCE_SYMBOL', 'BTCUSDT')
ORDER_VALUE = float(os.getenv('ORDER_VALUE', '10'))
PAPER_MODE = os.getenv('PAPER_MODE', 'true').lower() != 'false'

client = None
if not PAPER_MODE and API_KEY and API_SECRET:
    client = Client(API_KEY, API_SECRET)

state = {
    'position': None,
    'entry_price': 0,
    'balance': 100.0
}


@app.route('/webhook', methods=['POST'])
def webhook():
    global state
    
    data = request.get_json()
    logger.info(f"Received webhook: {data}")
    
    if not data:
        return jsonify({'error': 'No data received'}), 400
    
    signal = data.get('signal', '').upper()
    price = data.get('price')
    symbol = data.get('symbol', SYMBOL)
    
    if not signal:
        return jsonify({'error': 'No signal provided'}), 400
    
    logger.info(f"Signal: {signal} | Symbol: {symbol}")
    
    try:
        if signal in ['BUY', 'LONG', 'CALL', 'ENTRY']:
            result = execute_buy(symbol, price)
            state['position'] = 'long'
            state['entry_price'] = price if price else result.get('price', 0)
            return jsonify({'status': 'buy_executed', 'result': result})
        
        elif signal in ['SELL', 'CLOSE', 'EXIT']:
            if state['position'] == 'long':
                result = execute_sell(symbol, price)
                pnl = (price - state['entry_price']) if price else 0
                state['position'] = None
                state['entry_price'] = 0
                return jsonify({'status': 'sell_executed', 'pnl': pnl, 'result': result})
            return jsonify({'status': 'no_position'})
        
        else:
            return jsonify({'error': f'Unknown signal: {signal}'}), 400
            
    except Exception as e:
        logger.error(f"Error executing trade: {e}")
        return jsonify({'error': str(e)}), 500


def execute_buy(symbol, price=None):
    if not client:
        return {'orderId': 'PAPER_BUY', 'price': price, 'mode': 'paper'}
    
    try:
        if price:
            order = client.order_limit_buy(
                symbol=symbol,
                quantity=ORDER_VALUE / price,
                price=price
            )
        else:
            order = client.order_market_buy(
                symbol=symbol,
                quantity=ORDER_VALUE / client.get_symbol_ticker(symbol=symbol)['price']
            )
        logger.info(f"BUY executed: {order}")
        return order
    except BinanceAPIException as e:
        logger.error(f"Buy failed: {e}")
        raise


def execute_sell(symbol, price=None):
    if not client:
        return {'orderId': 'PAPER_SELL', 'price': price, 'mode': 'paper'}
    
    try:
        if price:
            order = client.order_limit_sell(
                symbol=symbol,
                quantity=ORDER_VALUE / price,
                price=price
            )
        else:
            order = client.order_market_sell(
                symbol=symbol,
                quantity=ORDER_VALUE / client.get_symbol_ticker(symbol=symbol)['price']
            )
        logger.info(f"SELL executed: {order}")
        return order
    except BinanceAPIException as e:
        logger.error(f"Sell failed: {e}")
        raise
        logger.error(f"Sell failed: {e}")
        raise


@app.route('/status', methods=['GET'])
def status():
    return jsonify(state)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 TradingView Webhook Bot")
    print("=" * 60)
    print(f"Symbol: {SYMBOL}")
    print(f"Order Value: ${ORDER_VALUE}")
    print(f"Mode: {'LIVE' if client else 'PAPER'}")
    print()
    print("Webserver running on http://localhost:5000")
    print()
    print("TradingView Alert URL:")
    print(f"  {{webhook.url}}/webhook")
    print()
    print("JSON format for TradingView alerts:")
    print('  {"signal": "BUY", "symbol": "BTCUSDT", "price": 50000}')
    print('  {"signal": "SELL"}')
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5001, debug=True)