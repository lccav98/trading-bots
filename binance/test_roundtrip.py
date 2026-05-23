"""
Teste end-to-end: buy + sell imediato com valor minimo ($5).
Valida: permissoes API, execucao de ordem, step size, fees reais, slippage.
"""
import os
import time
import json
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')
symbol = 'TRXUSDT'

client = Client(api_key, api_secret)

# Saldo antes
bal_before = None
for b in client.get_account()['balances']:
    if b['asset'] == 'USDT':
        bal_before = float(b['free'])

print(f"Saldo antes: {bal_before:.8f} USDT")

# Preco atual
ticker = client.get_symbol_ticker(symbol=symbol)
price = float(ticker['price'])
print(f"Preco TRX: ${price}")

# Quantidade para ~$5.10 (acima do min_notional=$5)
target_notional = 5.10
qty = round(target_notional / price, 1)  # step=0.1
print(f"Comprando {qty} TRX (~${qty*price:.4f})")

# BUY
t0 = time.time()
order_buy = client.order_market_buy(symbol=symbol, quantity=qty)
t_buy = time.time() - t0

buy_price = float(order_buy['fills'][0]['price'])
buy_qty = float(order_buy['executedQty'])
buy_cost = float(order_buy['cummulativeQuoteQty'])
buy_fee = sum(float(f['commission']) for f in order_buy['fills'])
buy_fee_asset = order_buy['fills'][0]['commissionAsset']

print(f"\n[BUY] {buy_qty} TRX @ ${buy_price} = ${buy_cost:.4f}  ({t_buy*1000:.0f}ms)")
print(f"      fee: {buy_fee} {buy_fee_asset}")

# Aguarda 2s para simular hold
time.sleep(2)

# Saldo TRX disponivel
trx_free = 0.0
for b in client.get_account()['balances']:
    if b['asset'] == 'TRX':
        trx_free = float(b['free'])

# SELL (vende tudo que recebeu, descontando fee se foi em TRX)
sell_qty = round(trx_free, 1) if trx_free < buy_qty else buy_qty
if buy_fee_asset == 'TRX':
    sell_qty = round(buy_qty - buy_fee, 1)

print(f"\nVendendo {sell_qty} TRX")

t0 = time.time()
order_sell = client.order_market_sell(symbol=symbol, quantity=sell_qty)
t_sell = time.time() - t0

sell_price = float(order_sell['fills'][0]['price'])
sell_revenue = float(order_sell['cummulativeQuoteQty'])
sell_fee = sum(float(f['commission']) for f in order_sell['fills'])

print(f"[SELL] {sell_qty} TRX @ ${sell_price} = ${sell_revenue:.4f}  ({t_sell*1000:.0f}ms)")
print(f"       fee: {sell_fee} {order_sell['fills'][0]['commissionAsset']}")

# Saldo depois
time.sleep(1)
bal_after = None
for b in client.get_account()['balances']:
    if b['asset'] == 'USDT':
        bal_after = float(b['free'])

net_pnl = bal_after - bal_before
slippage_buy = (buy_price - price) / price * 100
slippage_sell = (sell_price - buy_price) / buy_price * 100

print(f"\n{'='*50}")
print(f"RESULTADO ROUND-TRIP")
print(f"{'='*50}")
print(f"Saldo antes:  {bal_before:.8f} USDT")
print(f"Saldo depois: {bal_after:.8f} USDT")
print(f"PnL liquido:  {net_pnl:+.8f} USDT ({net_pnl/bal_before*100:+.4f}%)")
print(f"Slippage buy:  {slippage_buy:+.4f}%")
print(f"Slippage sell: {slippage_sell:+.4f}%")
print(f"Fee total:    {buy_fee + sell_fee} (em asset variavel)")

# Salvar log
with open('test_roundtrip_result.json', 'w') as f:
    json.dump({
        'buy':  order_buy,
        'sell': order_sell,
        'bal_before': bal_before,
        'bal_after':  bal_after,
        'pnl':        net_pnl,
    }, f, indent=2, default=str)

print("\nLog salvo em test_roundtrip_result.json")
