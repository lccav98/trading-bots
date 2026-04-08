import requests
import time
import hmac
import hashlib
import base64
import json
import logging
from eth_account import Account

logger = logging.getLogger("execution.proxy")

class PolymarketProxyClient:
    """
    Direct Polymarket CLOB API client with proper proxy wallet support.
    Bypasses py_clob_client's signature bug for signature_type=1.
    """
    
    CLOB_HOST = "https://clob.polymarket.com"
    
    def __init__(self, private_key, chain_id=137, signature_type=1, funder=None):
        self.private_key = private_key
        self.chain_id = chain_id
        self.signature_type = signature_type
        self.account = Account.from_key(private_key)
        self.funder = funder or self.account.address
        self.api_key = None
        self.api_secret = None
        self.api_passphrase = None
        self._authenticate()
        logger.info(f"PolymarketProxyClient initialized: funder={self.funder[:10]}... sig_type={self.signature_type}")
    
    def _authenticate(self):
        """Create or derive API credentials."""
        timestamp = int(time.time())
        nonce = 0
        message = "This message attests that I control the given wallet"
        
        from eth_account.messages import encode_structured_data
        
        domain = {
            "name": "ClobAuthDomain",
            "version": "1",
            "chainId": self.chain_id,
        }
        
        types = {
            "ClobAuth": [
                {"name": "address", "type": "address"},
                {"name": "timestamp", "type": "string"},
                {"name": "nonce", "type": "uint256"},
                {"name": "message", "type": "string"},
            ]
        }
        
        value = {
            "address": self.account.address,
            "timestamp": str(timestamp),
            "nonce": nonce,
            "message": message,
        }
        
        signed = Account.sign_typed_data(self.private_key, domain, types, value)
        signature = "0x" + signed.signature.hex()
        
        headers = {
            "POLY_ADDRESS": self.account.address,
            "POLY_SIGNATURE": signature,
            "POLY_TIMESTAMP": str(timestamp),
            "POLY_NONCE": str(nonce),
        }
        
        try:
            resp = requests.post(
                f"{self.CLOB_HOST}/auth/api-key",
                headers=headers,
                timeout=10
            )
            if resp.status_code == 200:
                creds = resp.json()
                self.api_key = creds["apiKey"]
                self.api_secret = creds["secret"]
                self.api_passphrase = creds["passphrase"]
                logger.info(f"API key created: {self.api_key}")
                return
        except Exception as e:
            logger.debug(f"Create API key failed: {e}")
        
        try:
            resp = requests.get(
                f"{self.CLOB_HOST}/auth/derive-api-key",
                headers=headers,
                timeout=10
            )
            if resp.status_code == 200:
                creds = resp.json()
                self.api_key = creds["apiKey"]
                self.api_secret = creds["secret"]
                self.api_passphrase = creds["passphrase"]
                logger.info(f"API key derived: {self.api_key}")
                return
        except Exception as e:
            logger.error(f"Derive API key failed: {e}")
        
        raise Exception("Failed to authenticate with Polymarket CLOB")
    
    def _sign_l2(self, method, path, body=None, timestamp=None):
        """Create L2 HMAC signature."""
        if timestamp is None:
            timestamp = int(time.time())
        
        if body is None:
            body_str = ""
        else:
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        
        message = f"{timestamp}{method}{path}{body_str}"
        
        signature = base64.b64encode(
            hmac.new(
                base64.b64encode(self.api_secret.encode()),
                message.encode(),
                hashlib.sha256
            ).digest()
        ).decode()
        
        return {
            "POLY_ADDRESS": self.funder,
            "POLY_SIGNATURE": signature,
            "POLY_TIMESTAMP": str(timestamp),
            "POLY_API_KEY": self.api_key,
            "POLY_PASSPHRASE": self.api_passphrase,
        }
    
    def get_order_book(self, token_id):
        """Get order book for a token."""
        resp = requests.get(
            f"{self.CLOB_HOST}/book",
            params={"token_id": token_id},
            timeout=10
        )
        return resp.json()
    
    def get_tick_size(self, token_id):
        """Get tick size for a token."""
        resp = requests.get(
            f"{self.CLOB_HOST}/tick-size",
            params={"token_id": token_id},
            timeout=10
        )
        return resp.json().get("minimum_tick_size", "0.01")
    
    def get_neg_risk(self, token_id):
        """Get neg_risk flag for a token."""
        resp = requests.get(
            f"{self.CLOB_HOST}/neg-risk",
            params={"token_id": token_id},
            timeout=10
        )
        return resp.json().get("neg_risk", False)
    
    def get_balance(self):
        """Get USDC balance."""
        path = "/balance-allowance"
        timestamp = int(time.time())
        headers = self._sign_l2("GET", path, None, timestamp)
        
        resp = requests.get(
            f"{self.CLOB_HOST}{path}",
            headers=headers,
            params={"asset_type": "COLLATERAL"},
            timeout=10
        )
        return resp.json()
    
    def create_and_post_order(self, token_id, price, size, side, tick_size="0.01", neg_risk=False):
        """Create and post a limit order with proper proxy wallet signing."""
        decimals = len(tick_size.split(".")[-1])
        price = round(price, decimals)
        size = round(size, 2)
        
        if side == "BUY":
            maker_amount = int(round(size * price, 6) * 1e6)
            taker_amount = int(round(size, 2) * 1e6)
        else:
            maker_amount = int(round(size, 2) * 1e6)
            taker_amount = int(round(size * price, 6) * 1e6)
        
        order_data = {
            "order": {
                "salt": int(time.time() * 1000),
                "maker": self.funder.lower(),
                "signer": self.account.address.lower(),
                "taker": "0x0000000000000000000000000000000000000000",
                "tokenId": str(token_id),
                "makerAmount": str(maker_amount),
                "takerAmount": str(taker_amount),
                "expiration": "0",
                "nonce": "0",
                "feeRateBps": "0",
                "side": side,
                "signatureType": self.signature_type,
            },
            "owner": self.api_key,
            "orderType": "GTC",
            "postOnly": False,
        }
        
        path = "/order"
        timestamp = int(time.time())
        headers = self._sign_l2("POST", path, order_data, timestamp)
        headers["Content-Type"] = "application/json"
        
        resp = requests.post(
            f"{self.CLOB_HOST}{path}",
            headers=headers,
            json=order_data,
            timeout=15
        )
        
        return resp.json()
    
    def cancel_order(self, order_id):
        """Cancel an order."""
        path = "/order"
        timestamp = int(time.time())
        body = {"orderID": order_id}
        
        headers = self._sign_l2("DELETE", path, body, timestamp)
        headers["Content-Type"] = "application/json"
        
        resp = requests.delete(
            f"{self.CLOB_HOST}{path}",
            headers=headers,
            json=body,
            timeout=10
        )
        
        return resp.json()
