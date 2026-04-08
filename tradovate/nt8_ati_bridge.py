# NT8 ATI OIF Bridge - Python sends orders to NT8 via file
# Uses NinjaTrader's built-in Automated Trading Interface (ATI)

import os
import time

# NT8 incoming folder (Documents/NinjaTrader 8/incoming)
INCOMING_DIR = os.path.expanduser("~/Documents/NinjaTrader 8/incoming")
os.makedirs(INCOMING_DIR, exist_ok=True)

def send_oif_order(action, symbol, quantity, order_type="MARKET", limit_price="", stop_price="", account="", strategy=""):
    """
    Send order via NT8 ATI File Interface (OIF)
    
    action: BUY or SELL
    symbol: MES, MNQ, etc.
    quantity: number of contracts
    order_type: MARKET, LIMIT, STOP, etc.
    """
    
    # Format: PLACE;ACCOUNT;INSTRUMENT;ACTION;QTY;ORDER TYPE;[LIMIT];[STOP];TIF;;[ORDER ID];[STRATEGY];[STRATEGY ID]
    
    # Account defaults to first available if empty
    account_str = account if account else ""
    
    # Build OIF line
    parts = [
        "PLACE",
        account_str,
        symbol,
        action.upper(),
        str(quantity),
        order_type,
        limit_price if limit_price else "",
        stop_price if stop_price else "",
        "DAY",  # Time in force
        "",    # OCO ID
        "",    # Order ID
        strategy,  # Strategy name
        ""     # Strategy ID
    ]
    
    oif_line = ";".join(parts)
    
    # Generate unique filename
    timestamp = int(time.time() * 1000)
    filename = f"oif_{timestamp}.txt"
    filepath = os.path.join(INCOMING_DIR, filename)
    
    # Write file
    with open(filepath, 'w') as f:
        f.write(oif_line)
    
    print(f"[OIF] Sent: {filename} -> {oif_line}")
    return filename

def cancel_all_orders():
    """Cancel all pending orders"""
    filename = f"oif_cancel_{int(time.time()*1000)}.txt"
    filepath = os.path.join(INCOMING_DIR, filename)
    
    with open(filepath, 'w') as f:
        f.write("CANCELALLORDERS;;;;;;")
    
    print(f"[OIF] Cancel all orders sent")

def flatten_everything():
    """Close all positions"""
    filename = f"oif_flatten_{int(time.time()*1000)}.txt"
    filepath = os.path.join(INCOMING_DIR, filename)
    
    with open(filepath, 'w') as f:
        f.write("FLATTENEVERYTHING;;;;;")
    
    print(f"[OIF] Flatten sent")

# Test
if __name__ == "__main__":
    print("=" * 50)
    print("NT8 ATI OIF Bridge - Test")
    print("=" * 50)
    print()
    print(f"Incoming folder: {INCOMING_DIR}")
    print()
    
    # Test buy order
    send_oif_order("BUY", "MES", 1, "MARKET", "", "", "", "ApexSimpleTrend")
    
    print()
    print("Order sent! NT8 should process it automatically.")
    print()
    print("Note: Enable ATI in NT8 first:")
    print("  Tools -> Options -> Automated Trading -> Enable ATI")