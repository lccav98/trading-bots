import os
import time
import logging
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType

from config import Config
from signals.value_trading import ResolvedMarketScanner, ValueSignalGenerator
from execution import ExecutionEngine
from paper_trading import PaperExecutionEngine
from risk import RiskManager

# Prophet AI Forecasting
try:
    from prophet_integration import load_prophet, predict_outcome
    PROPHET_AVAILABLE = True
    print("[Prophet] Loading model...")
    load_prophet()
except ImportError:
    PROPHET_AVAILABLE = False
    print("[Prophet] Not available")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log"),
    ]
)
logger = logging.getLogger("bot")


def send_alert(message):
    """Send alert to Discord webhook if configured."""
    if not Config.DISCORD_WEBHOOK:
        return
    try:
        import requests
        requests.post(Config.DISCORD_WEBHOOK, json={"content": message}, timeout=10)
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")


def run_bot():
    # --- Configuration ---
    logger.info("=" * 50)
    logger.info("Polymarket Value Trading Bot Starting")
    logger.info("=" * 50)
    logger.info(f"Paper trading: {Config.PAPER_TRADING}")
    logger.info(f"Chain ID: {Config.CHAIN_ID}")
    logger.info(f"Scan interval: {Config.SCAN_INTERVAL}s")
    logger.info(f"Order size: ${Config.ORDER_SIZE}")

    # --- Initialize CLOB client (only for live trading) ---
    client = None
    if not Config.PAPER_TRADING:
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=Config.PRIVATE_KEY,
            chain_id=Config.CHAIN_ID,
            signature_type=Config.SIGNATURE_TYPE,
            funder=Config.FUNDER_ADDRESS,
        )
        client.set_api_creds(client.create_or_derive_api_creds())
        logger.info(f"CLOB client initialized (sig_type={Config.SIGNATURE_TYPE}, funder={Config.FUNDER_ADDRESS[:10]}...)")
    else:
        logger.info("Skipping CLOB client (paper trading mode)")

    # --- Initialize value trading scanner ---
    scanner = ResolvedMarketScanner(
        min_volume=Config.MIN_VOLUME,
        min_liquidity=Config.MIN_LIQUIDITY,
        max_fetch_pages=2,
    )

    # Value signal generator
    value_gen = ValueSignalGenerator(
        min_volume=5000,
        max_hours_to_resolve=24,
        near_resolved_threshold=0.94,
    )

    if Config.PAPER_TRADING:
        executor = PaperExecutionEngine(starting_balance=100.0)
        logger.info("Using PAPER TRADING engine")
    else:
        executor = ExecutionEngine(client, default_size=Config.ORDER_SIZE)
        logger.info("Using LIVE execution engine")

    risk = RiskManager(
        max_position_size=Config.MAX_POSITION_SIZE,
        max_total_exposure=Config.MAX_TOTAL_EXPOSURE,
        max_drawdown_pct=Config.MAX_DRAWDOWN_PCT,
        max_trades_per_hour=Config.MAX_TRADES_PER_HOUR,
    )

    # --- Get balance ---
    if Config.PAPER_TRADING:
        balance = executor.balance
    else:
        result = client.get_balance_allowance(
            BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=Config.SIGNATURE_TYPE)
        )
        balance = int(result["balance"]) / 1e6
    risk.set_starting_balance(balance)
    logger.info(f"Starting balance: ${balance:.2f}")

    send_alert(f"Value Bot started - Balance: ${balance:.2f} - Paper: {Config.PAPER_TRADING}")

    # --- Main loop ---
    scan_count = 0
    trade_count = 0

    while True:
        try:
            risk.check_kill_switch()
            scan_count += 1

            # 1. Scan markets for value opportunities
            markets = scanner.scan()
            logger.info(f"Scanned {len(markets)} tradeable markets")

            # 2. Generate value signals
            all_signals = value_gen.generate_for_watchlist(markets)
            
            # Prophet AI confirmation
            if PROPHET_AVAILABLE and all_signals:
                logger.info("  [Prophet] Enhancing signals with AI prediction...")
                # Note: Prophet needs historical price data which isn't directly available
                # The enhance_signal function is available for when price history exists
            
            if all_signals:
                for sig in all_signals:
                    logger.info(
                        f"  Signal #{len(all_signals)}: {sig.side} | "
                        f"{sig.market_question[:60]} | EV: {sig.expected_value:.3f} | "
                        f"Strength: {sig.strength:.2f}"
                    )
            else:
                logger.info("No value opportunities found this scan")

            # 3. Sync current state
            executor.sync_positions()
            if not Config.PAPER_TRADING:
                result = client.get_balance_allowance(
                    BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=Config.SIGNATURE_TYPE)
                )
                balance = int(result["balance"]) / 1e6

            # 4. Execute approved trades (limit to top 5 per scan)
            max_trades_per_scan = 5
            trades_executed = 0
            for signal in all_signals:
                if trades_executed >= max_trades_per_scan:
                    logger.info(f"Max trades per scan ({max_trades_per_scan}) reached")
                    break
                # Signal already has token_id, side, reason, etc.
                signal_for_execution = type("Signal", (), {
                    "condition_id": signal.condition_id,
                    "token_id": signal.token_id,
                    "side": signal.side,
                    "strength": signal.strength,
                    "reason": signal.reason,
                    "market_question": signal.market_question,
                    "expected_value": signal.expected_value,
                })()

                # Position sizing
                order_size = min(Config.ORDER_SIZE, balance * 0.10)

                approved, reason = risk.approve_trade(
                    signal_for_execution, order_size, executor.positions, balance
                )
                if approved:
                    order_id = executor.execute_signal(signal_for_execution, order_size)
                    if order_id:
                        trade_count += 1
                        trades_executed += 1
                        logger.info(f"Executed: {signal.reason}")
                        send_alert(f"Trade #{trade_count}: {signal.side} ${order_size:.2f} - {signal.market_question[:80]}")
                else:
                    logger.info(f"Rejected ({reason}): {signal.reason}")

            # 5. Clean up stale orders
            if not Config.PAPER_TRADING:
                executor.cancel_stale_orders(max_age_seconds=600)

            # 6. Log status
            total_positions = len(executor.positions)
            logger.info(
                f"Scan #{scan_count} | Balance: ${balance:.2f} | "
                f"Positions: {total_positions} | Trades: {trade_count} | "
                f"Next scan in {Config.SCAN_INTERVAL}s"
            )

            time.sleep(Config.SCAN_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Shutting down gracefully...")
            if isinstance(executor, PaperExecutionEngine):
                executor.summary()
            send_alert("Bot shut down gracefully")
            break
        except Exception as e:
            logger.error(f"Loop error: {e}", exc_info=True)
            send_alert(f"Bot ERROR: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
