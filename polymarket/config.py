import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    PRIVATE_KEY = os.environ.get("POLYMARKET_PRIVATE_KEY", "")
    CHAIN_ID = int(os.environ.get("CHAIN_ID", "137"))
    SIGNATURE_TYPE = int(os.environ.get("SIGNATURE_TYPE", "1"))
    FUNDER_ADDRESS = os.environ.get("FUNDER_ADDRESS", "")
    SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL", "300"))
    ORDER_SIZE = float(os.environ.get("ORDER_SIZE", "1.0"))
    MIN_VOLUME = float(os.environ.get("MIN_VOLUME", "1000"))
    MIN_LIQUIDITY = float(os.environ.get("MIN_LIQUIDITY", "500"))
    MAX_POSITION_SIZE = float(os.environ.get("MAX_POSITION_SIZE", "2.0"))
    MAX_TOTAL_EXPOSURE = float(os.environ.get("MAX_TOTAL_EXPOSURE", "3.0"))
    MAX_DRAWDOWN_PCT = float(os.environ.get("MAX_DRAWDOWN_PCT", "0.15"))
    MAX_TRADES_PER_HOUR = int(os.environ.get("MAX_TRADES_PER_HOUR", "20"))
    PAPER_TRADING = os.environ.get("PAPER_TRADING", "true").lower() == "true"
    DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
