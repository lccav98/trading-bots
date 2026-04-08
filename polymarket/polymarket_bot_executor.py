"""
Polymarket Bot Executor
Módulo executor para TradingView webhook
"""

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("executor")

CLIENT = None
DEFAULT_SIZE = 1.0


def get_client():
    """Get or create CLOB client."""
    global CLIENT
    if CLIENT is None:
        try:
            key = os.getenv("POLYMARKET_PRIVATE_KEY")
            if not key:
                logger.warning("No private key, using simulated mode")
                return None
            
            CLIENT = ClobClient(
                host="https://clob.polymarket.com",
                key=key
            )
            logger.info("CLOB client initialized")
        except Exception as e:
            logger.error(f"Failed to create client: {e}")
            return None
    return CLIENT


def execute_trade(action, size=1.0):
    """
    Execute a trade from TradingView webhook signal.
    
    Args:
        action: 'BUY' or 'SELL'
        size: dollar amount to trade
    
    Returns:
        dict with result status
    """
    logger.info(f"execute_trade called: action={action}, size={size}")
    
    # For now, log the signal - real execution requires token_id
    # In production, you'd look up the token from the alert message
    
    action = action.upper()
    
    if action not in ["BUY", "SELL"]:
        return {"status": "error", "message": f"Invalid action: {action}"}
    
    client = get_client()
    
    if client is None:
        logger.info("[SIMULATION] No client, would execute:")
        logger.info(f"  Action: {action}")
        logger.info(f"  Size: ${size}")
        return {"status": "simulation", "action": action, "size": size}
    
    # TODO: Parse token from TradingView alert message
    # For now, return simulation
    logger.warning("Token ID required - add token to webhook message")
    return {"status": "error", "message": "Token ID required"}


def execute_trade_with_token(action, token_id, size=1.0):
    """
    Execute trade with specific token_id.
    
    Use this from TradingView alert message like:
    {"message": "BUY ETH-PERPETUAL 10"}
    """
    logger.info(f"execute_trade_with_token: action={action}, token={token_id}, size={size}")
    
    client = get_client()
    if client is None:
        return {"status": "simulation", "action": action, "token": token_id, "size": size}
    
    try:
        # Get order book
        book = client.get_order_book(token_id)
        
        side = "BUY" if action.upper() in ["BUY", "LONG"] else "SELL"
        
        if side == "BUY":
            if not book.asks:
                return {"status": "error", "message": "No asks available"}
            best_ask = float(book.asks[0].price)
            price = round(best_ask - 0.01, 2)
        else:
            if not book.bids:
                return {"status": "error", "message": "No bids available"}
            best_bid = float(book.bids[0].price)
            price = round(best_bid + 0.01, 2)
        
        if price <= 0:
            return {"status": "error", "message": f"Invalid price: {price}"}
        
        num_shares = size / price
        
        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=num_shares,
            side=side,
        )
        
        signed = client.create_order(order_args)
        response = client.post_order(signed, OrderType.GTC)
        
        order_id = response.get("orderID") if isinstance(response, dict) else getattr(response, "orderID", None)
        
        logger.info(f"Order placed: {side} {num_shares:.1f} @ {price}, order_id={order_id}")
        
        return {
            "status": "success",
            "action": side,
            "price": price,
            "shares": num_shares,
            "order_id": order_id
        }
        
    except Exception as e:
        logger.error(f"Trade failed: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    # Test
    print("Testing executor...")
    result = execute_trade("BUY", 1.0)
    print(f"Result: {result}")