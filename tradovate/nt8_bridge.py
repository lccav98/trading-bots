# NT8 Order Bridge - Python Side
# Writes orders to file, NT8 reads and executes

import os
import json
import time
from datetime import datetime

ORDERS_FILE = "C:/Users/OpAC BV/Documents/NinjaTrader 8/incoming/orders.json"

def send_order_to_nt8(action, price, sl, tp, contracts=1):
    """
    Envia ordem para NT8 via arquivo
    action: 'BUY' ou 'SELL'
    price: preço de entrada
    sl: stop loss
    tp: take profit
    """
    order = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "price": price,
        "sl": sl,
        "tp": tp,
        "contracts": contracts,
        "symbol": "MES",
        "status": "PENDING"
    }
    
    # Read existing orders
    orders = []
    if os.path.exists(ORDERS_FILE):
        try:
            with open(ORDERS_FILE, 'r') as f:
                orders = json.load(f)
        except:
            orders = []
    
    # Add new order
    orders.append(order)
    
    # Write back
    with open(ORDERS_FILE, 'w') as f:
        json.dump(orders, f, indent=2)
    
    print(f"Order sent to NT8: {action} {contracts} MES @ {price}")
    return True

def get_order_status(order_id):
    """Check if order was executed"""
    if not os.path.exists(ORDERS_FILE):
        return None
    
    try:
        with open(ORDERS_FILE, 'r') as f:
            orders = json.load(f)
        
        for o in orders:
            if o.get("timestamp") == order_id:
                return o.get("status")
    except:
        pass
    
    return None

def clear_orders():
    """Clear processed orders"""
    if os.path.exists(ORDERS_FILE):
        try:
            with open(ORDERS_FILE, 'w') as f:
                json.dump([], f)
        except:
            pass

# Test
if __name__ == "__main__":
    # Create directory if needed
    os.makedirs("C:/Users/OpAC BV/Documents/NinjaTrader 8/incoming", exist_ok=True)
    
    # Test order
    send_order_to_nt8("BUY", 5800.00, 5790.00, 5820.00, 1)
    print("Test order sent!")