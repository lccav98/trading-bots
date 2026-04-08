"""
TrxBinary Trading Bot - Complete Trading System
"""
import time
import random
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("trxbot")


@dataclass
class TradeResult:
    asset: str
    direction: str
    amount: float
    won: bool
    profit: float


class TradingBot:
    def __init__(self, username, password, initial_balance=18.91):
        self.username = username
        self.password = password
        self.driver = None
        self.base_url = "https://app.trxbinary.com/pt"
        self.balance = initial_balance
        self.initial_balance = initial_balance
        
        # Config
        self.min_trade = 1
        self.max_trade = 10
        self.base_amount = 1
        self.stop_loss = 5  # Stop if lose $5
        self.take_profit = 10  # Take if gain $10
        self.trade_duration = 65
        
        # Tracking
        self.wins = 0
        self.losses = 0
        self.consecutive_losses = 0
    
    def setup(self):
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        logger.info("Driver initialized")
    
    def login(self):
        self.driver.get(self.base_url + "/auth/login")
        time.sleep(5)
        
        self.driver.find_element(By.ID, "email").send_keys(self.username)
        self.driver.find_element(By.ID, "password").send_keys(self.password)
        self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(8)
        
        self.update_balance()
        logger.info(f"Logged in. Balance: ${self.balance}")
    
    def update_balance(self):
        try:
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                text = btn.text.strip()
                if text.startswith('$') and len(text) < 15:
                    try:
                        val = float(text.replace('$', ''))
                        if val > 0:
                            self.balance = val
                            return
                    except:
                        pass
        except:
            pass
    
    def select_asset(self, asset_name):
        """Select trading asset."""
        try:
            # Open selector
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                if any(x in btn.text for x in ["EURJPY", "EURUSD", "BTCUSD", "GBP", "USD", "AUD"]):
                    btn.click()
                    time.sleep(2)
                    break
            
            # Select asset
            asset_span = self.driver.find_element(By.XPATH, f"//span[contains(text(), '{asset_name}')]")
            self.driver.execute_script("arguments[0].click();", asset_span)
            time.sleep(1)
            
            # Close modal
            self.driver.find_element(By.TAG_NAME, "body").send_keys("\u001b")
            time.sleep(1)
            
            return True
        except Exception as e:
            logger.error(f"Error selecting asset: {e}")
            return False
    
    def set_amount(self, amount):
        amount = max(self.min_trade, min(amount, self.max_trade))
        try:
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs:
                try:
                    if inp.get_attribute('aria-valuenow'):
                        inp.clear()
                        inp.send_keys(str(int(amount)))
                        return amount
                except:
                    pass
        except:
            pass
        return self.base_amount
    
    def get_signal(self):
        """Simple strategy - RSI-like random with trend"""
        rsi = random.uniform(25, 75)
        
        if rsi < 35:
            return "CALL", "HIGH"
        elif rsi > 65:
            return "PUT", "HIGH"
        elif rsi < 45:
            return "CALL", "MEDIUM"
        elif rsi > 55:
            return "PUT", "MEDIUM"
        else:
            return random.choice(["CALL", "PUT"]), "LOW"
    
    def place_trade(self, asset, direction, amount):
        """Execute a trade."""
        try:
            self.set_amount(amount)
            time.sleep(0.5)
            
            # Scroll
            self.driver.execute_script("window.scrollTo(0, 200);")
            time.sleep(0.5)
            
            # Execute
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                if direction == "CALL" and "Comprar" in btn.text:
                    self.driver.execute_script("arguments[0].click();", btn)
                    break
                elif direction == "PUT" and "Vender" in btn.text:
                    self.driver.execute_script("arguments[0].click();", btn)
                    break
            
            time.sleep(self.trade_duration)
            
            # Check result
            self.update_balance()
            
            # Determine win/lose ( payout 85% = $0.85 profit on $1 bet)
            profit = self.balance - amount
            won = profit >= 0
            
            return TradeResult(
                asset=asset,
                direction=direction,
                amount=amount,
                won=won,
                profit=profit
            )
            
        except Exception as e:
            logger.error(f"Trade error: {e}")
            return None
    
    def calculate_amount(self):
        """Smart position sizing - martingale with cap"""
        if self.consecutive_losses == 0:
            return self.base_amount
        else:
            # Martingale: double after loss, max 3x
            mult = min(2 ** self.consecutive_losses, 8)
            amount = self.base_amount * mult
            return max(self.min_trade, min(amount, self.max_trade))
    
    def run_session(self, max_trades=20):
        """Run a complete trading session."""
        logger.info(f"=== Starting Session ===")
        logger.info(f"Initial: ${self.initial_balance}")
        logger.info(f"Stop Loss: ${self.stop_loss}, Take Profit: ${self.take_profit}")
        
        # Assets to trade (working ones)
        working_assets = ["EURJPY", "EURUSD"]
        
        for i in range(max_trades):
            # Check limits
            profit = self.balance - self.initial_balance
            
            if profit >= self.take_profit:
                logger.info(f"🎯 TAKE PROFIT reached: +${profit:.2f}")
                break
            if profit <= -self.stop_loss:
                logger.info(f"🛑 STOP LOSS reached: -${abs(profit):.2f}")
                break
            
            logger.info(f"\n--- Trade {i+1}/{max_trades} ---")
            self.update_balance()
            logger.info(f"Balance: ${self.balance:.2f}, Profit: ${profit:.2f}")
            
            # Select random working asset
            asset = random.choice(working_assets)
            if not self.select_asset(asset):
                logger.error(f"Could not select {asset}")
                continue
            
            # Get signal
            direction, confidence = self.get_signal()
            amount = self.calculate_amount()
            
            logger.info(f"Asset: {asset}, Direction: {direction} ({confidence}), Amount: ${amount}")
            
            # Execute
            result = self.place_trade(asset, direction, amount)
            
            if result:
                if result.won:
                    self.wins += 1
                    self.consecutive_losses = 0
                    logger.info(f"✅ WIN! Profit: +${result.profit:.2f}")
                else:
                    self.losses += 1
                    self.consecutive_losses += 1
                    logger.info(f"❌ LOSS! Loss: -${abs(result.profit):.2f}")
            
            time.sleep(2)
        
        # Summary
        logger.info(f"\n=== Session Complete ===")
        logger.info(f"Wins: {self.wins}, Losses: {self.losses}")
        self.update_balance()
        logger.info(f"Final Balance: ${self.balance:.2f}")
        logger.info(f"Total Profit: ${self.balance - self.initial_balance:.2f}")
        
        return {
            "wins": self.wins,
            "losses": self.losses,
            "final_balance": self.balance,
            "total_profit": self.balance - self.initial_balance
        }


if __name__ == "__main__":
    bot = TradingBot(
        username="lccav@proton.me",
        password="C&ntaur0",
        initial_balance=18.91
    )
    
    print("=== TrxBinary Trading Bot ===")
    
    bot.setup()
    bot.login()
    
    result = bot.run_session(max_trades=10)
    
    print(f"\n=== RESULT ===")
    print(f"Wins: {result['wins']}")
    print(f"Losses: {result['losses']}")
    print(f"Final: ${result['final_balance']:.2f}")
    print(f"Profit: ${result['total_profit']:.2f}")
    
    bot.driver.quit()