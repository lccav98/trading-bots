"""
Direct REST API client to bypass py-clob-client signature bug.
This implements L1 + L2 authentication manually.
"""
import hmac
import hashlib
import base64
import time
import json
import requests
from eth_account import Account
from eth_abi import encode
from eth_utils import keccak, to_checksum_address


class DirectCLOBClient:
    """Direct REST API client with manual signing."""
    
    CLOB_HOST = "https://clob.polymarket.com"
    
    def __init__(self, private_key: str, chain_id: int = 137, signature_type: int = 1, funder: str = None):
        self.account = Account.from_key(private_key)
        self.chain_id = chain_id
        self.signature_type = signature_type
        self.funder = funder or self.account.address
        self.api_creds = None
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
    
    def create_or_derive_api_creds(self):
        """L1 auth: Create or derive API credentials."""
        timestamp = str(int(time.time()))
        nonce = "0"
        
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
            "address": self.account.address.lower(),
            "timestamp": timestamp,
            "nonce": nonce,
            "message": "This message attests that I control the given wallet",
        }
        
        signature = self.account.sign_typed_data(domain, types, value)["signature"]
        
        headers = {
            "POLY_ADDRESS": self.account.address.lower(),
            "POLY_SIGNATURE": signature.hex(),
            "POLY_TIMESTAMP": timestamp,
            "POLY_NONCE": nonce,
        }
        
        response = requests.get(
            f"{self.CLOB_HOST}/auth/derive-api-key",
            headers=headers,
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to derive API key: {response.text}")
        
        self.api_creds = response.json()
        print(f"API Credentials: {self.api_creds}")
        return self.api_creds
    
    def _l2_sign(self, method: str, path: str, body: str = "") -> str:
        """L2 HMAC-SHA256 signing."""
        if not self.api_creds:
            raise Exception("API credentials not set")
        
        import base64
        secret = self.api_creds["secret"]
        timestamp = str(int(time.time()))
        
        message = f"{timestamp}{method}{path}"
        if body:
            message += body.replace("'", '"')
        
        h = hmac.new(
            base64.urlsafe_b64decode(secret),
            bytes(message, "utf-8"),
            hashlib.sha256
        )
        
        return base64.urlsafe_b64encode(h.digest()).decode("utf-8")
    
    def _auth_headers(self, method: str, path: str, body: str = "") -> dict:
        """Build L2 authenticated headers."""
        if not self.api_creds:
            raise Exception("API credentials not set")
        
        import base64
        secret = self.api_creds["secret"]
        timestamp = str(int(time.time()))
        
        message = f"{timestamp}{method}{path}"
        if body:
            message += body.replace("'", '"')
        
        h = hmac.new(
            base64.urlsafe_b64decode(secret),
            bytes(message, "utf-8"),
            hashlib.sha256
        )
        l2_signature = base64.urlsafe_b64encode(h.digest()).decode("utf-8")
        
        return {
            "POLY_ADDRESS": self.account.address.lower(),
            "POLY_TIMESTAMP": timestamp,
            "POLY_SIGNATURE": l2_signature,
            "POLY_API_KEY": self.api_creds["apiKey"],
            "POLY_PASSPHRASE": self.api_creds["passphrase"],
        }
    
    def get_balance_allowance(self, asset_type: str = "COLLATERAL"):
        """Get balance and allowance."""
        # Path for signature (without query params)
        path = "/balance-allowance"
        # Full URL with query params (asset_type not assetType)
        url = f"{self.CLOB_HOST}{path}?asset_type={asset_type}&signature_type=1"
        
        headers = self._auth_headers("GET", path)
        
        response = requests.get(url, headers=headers)
        print(f"Balance response status: {response.status_code}")
        print(f"Balance response text: {response.text[:500]}")
        response.raise_for_status()
        return response.json()
    
    def get_order_book(self, token_id: str):
        """Get order book for a token."""
        response = requests.get(
            f"{self.CLOB_HOST}/book?token_id={token_id}",
        )
        data = response.json()
        return {
            "bids": data.get("bids", []),
            "asks": data.get("asks", []),
            "tick_size": data.get("minimum_tick_size", "0.01"),
            "neg_risk": data.get("neg_risk", False),
        }
    
    def create_order(self, token_id: str, price: float, size: float, side: str, 
                     tick_size: str = "0.01", neg_risk: bool = False):
        """Create a signed order (L1 signing)."""
        timestamp = str(int(time.time()))
        
        order_data = {
            "asset": token_id,
            "amount": str(size),
            "price": str(price),
            "side": side,
            "feeRateBps": "0",
            "nonce": timestamp,
        }
        
        if self.signature_type == 0:
            order_data["maker"] = self.account.address.lower()
        elif self.signature_type in (1, 2):
            order_data["maker"] = self.funder.lower()
        
        domain = {
            "name": "ClobOrderDomain",
            "version": "1",
            "chainId": self.chain_id,
        }
        
        types = {
            "Order": [
                {"name": "asset", "type": "address"},
                {"name": "amount", "type": "string"},
                {"name": "price", "type": "string"},
                {"name": "side", "type": "string"},
                {"name": "feeRateBps", "type": "string"},
                {"name": "nonce", "type": "uint256"},
            ]
        }
        
        if self.signature_type in (1, 2):
            types["Order"].append({"name": "maker", "type": "address"})
        
        if self.signature_type == 0:
            order_data["maker"] = self.account.address.lower()
        
        signature = self.account.sign_typed_data(domain, types, order_data)["signature"]
        
        order = {
            "asset": token_id,
            "amount": str(size),
            "price": str(price),
            "side": side,
            "feeRateBps": "0",
            "nonce": timestamp,
            "signature": signature.hex(),
            "signatureType": self.signature_type,
        }
        
        if self.signature_type in (1, 2):
            order["maker"] = self.funder.lower()
        
        return order
    
    def post_order(self, order: dict, order_type: str = "GTC"):
        """Post the order to CLOB."""
        body = json.dumps({
            "order": order,
            "orderType": order_type,
        })
        
        headers = self._auth_headers("POST", "/orders", body)
        headers["Content-Type"] = "application/json"
        
        response = requests.post(
            f"{self.CLOB_HOST}/orders",
            headers=headers,
            data=body,
        )
        
        if response.status_code != 200:
            raise Exception(f"Order failed: {response.status_code} - {response.text}")
        
        return response.json()
    
    def create_and_post_order(self, token_id: str, price: float, size: float, side: str,
                              tick_size: str = "0.01", neg_risk: bool = False,
                              order_type: str = "GTC"):
        """Create and post order in one call."""
        order = self.create_order(token_id, price, size, side, tick_size, neg_risk)
        return self.post_order(order, order_type)


def test():
    """Test the direct client."""
    private_key = "0x64fb80146f8cd796efa27fdae9d784b71449e4e9421ea213217288f03d7eba28"
    funder = "0xa5D5A2bfcA0424bce35F8bBAbFAf019b332Eb4B3"
    
    # Use credentials from official client (which works)
    api_creds = {
        "apiKey": "cf215476-6ed3-18da-0c4a-237fd5c230b3",
        "secret": "bwSs-iX08tzoctj8lvt87y8i973n5DHkP8e5hiZwxUs=",
        "passphrase": "41566760656a32b1929d69280e6c05c6e4d396a314eb99c6d6e7a8a866480964",
    }
    
    # First, use official client to create a signed order
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import OrderArgs, PartialCreateOrderOptions
    
    official_client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=137,
        signature_type=1,
        funder=funder,
    )
    creds = official_client.create_or_derive_api_creds()
    official_client.set_api_creds(creds)
    
    # Create order with official client
    token_id = "78633590736077251574794513664747155551297291244492840448622550955320930591622"
    book = official_client.get_order_book(token_id)
    print(f"neg_risk: {book.neg_risk}, tick_size: {book.tick_size}")
    
    order_args = OrderArgs(
        token_id=token_id,
        price=0.99,
        size=0.01,
        side="BUY",
    )
    options = PartialCreateOrderOptions(tick_size=book.tick_size, neg_risk=book.neg_risk)
    
    # This will create the signed order but won't post it
    signed_order = official_client.create_order(order_args, options)
    print(f"Signed order: {signed_order.dict()}")
    
    # Now use direct client to post it
    client = DirectCLOBClient(
        private_key=private_key,
        chain_id=137,
        signature_type=1,
        funder=funder,
    )
    client.api_creds = api_creds
    
    print("\n=== Posting order via direct client ===")
    # Use exact serialization format as official client (includes "owner" field)
    body_dict = {
        "order": signed_order.dict(),
        "owner": api_creds["apiKey"],
        "orderType": "GTC",
        "postOnly": False,
    }
    body = json.dumps(body_dict, separators=(",", ":"), ensure_ascii=False)
    path = "/order"
    headers = client._auth_headers("POST", path, body)
    headers["Content-Type"] = "application/json"
    
    response = requests.post(
        f"{client.CLOB_HOST}/order",
        headers=headers,
        data=body,
    )
    print(f"Response status: {response.status_code}")
    print(f"Response text: {response.text}")


if __name__ == "__main__":
    test()