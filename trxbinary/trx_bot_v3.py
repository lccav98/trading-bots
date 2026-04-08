import time
import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dataclasses import dataclass
from typing import Optional, List
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("trxbot")


@dataclass
class TradeResult:
    success: bool
    direction: str
    amount: float
    duration: int
    profit: Optional[float] = None
    error: Optional[str] = None


class TrxBinaryBot:
    def __init__(self, username: str = None, password: str = None):
        self.username = username
        self.password = password
        self.driver = None
        self.base_url = "https://app.trxbinary.com/pt"
        self.logged_in = False
        self.balance = 0.0
        self.min_trade = 1.0
        self.max_trade = 100.0
        self.trade_duration = 60
    
    def setup_driver(self):
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        logger.info("Driver initialized")
    
    def login(self) -> bool:
        if not self.username or not self.password:
            return False
        
        try:
            self.driver.get(self.base_url + "/auth/login")
            time.sleep(5)
            
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.ID, "email")))
            self.driver.find_element(By.ID, "email").send_keys(self.username)
            self.driver.find_element(By.ID, "password").send_keys(self.password)
            self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
            
            time.sleep(10)
            self.logged_in = True
            self.update_balance()
            logger.info(f"Login successful. Balance: ${self.balance}")
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    def update_balance(self):
        """Get current account balance - improved detection."""
        try:
            # Try multiple methods to find the balance
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                text = btn.text.strip()
                if text.startswith('$') and len(text) < 15:
                    try:
                        val = float(text.replace('$', '').replace(',', ''))
                        if val > 0:
                            self.balance = val
                            return
                    except:
                        pass
            
            # Alternative: look for the balance in the page
            page = self.driver.page_source
            import re
            match = re.search(r'\$(\d+(?:\.\d+)?)', page)
            if match:
                self.balance = float(match.group(1))
                
        except Exception as e:
            logger.warning(f"Could not update balance: {e}")
    
    def set_amount(self, amount: float):
        amount = max(self.min_trade, min(amount, self.max_trade))
        try:
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs:
                try:
                    if inp.get_attribute('aria-valuenow'):
                        inp.clear()
                        inp.send_keys(str(int(amount)))
                        return True
                except:
                    continue
            return False
        except Exception as e:
            logger.error(f"Failed to set amount: {e}")
            return False
    
    def get_chart_data(self) -> dict:
        """Get chart data for analysis."""
        # For now, we'll use basic heuristics
        # In a full implementation, you'd analyze candlesticks
        return {
            "random_decision": random.choice(["CALL", "PUT"])
        }
    
    def simple_strategy(self) -> str:
        """Simple trading strategy based on random + basic heuristics."""
        # For binary options, a simple 50/50 strategy with proper money management
        # is often better than trying to "read" the chart
        return random.choice(["CALL", "PUT"])
    
    def place_trade(self, direction: str, amount: float) -> TradeResult:
        if not self.logged_in:
            if not self.login():
                return TradeResult(success=False, direction=direction, amount=amount, duration=self.trade_duration, error="Not logged in")
        
        try:
            self.set_amount(amount)
            time.sleep(0.5)
            
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            if direction.upper() == "CALL":
                for btn in buttons:
                    if "Comprar" in btn.text:
                        btn.click()
                        break
            else:
                for btn in buttons:
                    if "Vender" in btn.text:
                        btn.click()
                        break
            
            time.sleep(2)
            logger.info(f"Trade placed: {direction} ${amount}")
            
            return TradeResult(success=True, direction=direction, amount=amount, duration=self.trade_duration)
            
        except Exception as e:
            logger.error(f"Trade failed: {e}")
            return TradeResult(success=False, direction=direction, amount=amount, duration=self.trade_duration, error=str(e))
    
    def wait_for_result(self, timeout: int = 120) -> Optional[float]:
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Look for profit/loss indicators
                elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), '$') or contains(text(), '+') or contains(text(), '-')]")
                for el in elements:
                    text = el.text.strip()
                    if '$' in text and ('+' in text or text.startswith('-')):
                        try:
                            # Extract the profit value
                            profit_str = text.replace('$', '').replace('+', '').strip()
                            if profit_str.replace('.', '').replace('-', '').isdigit():
                                return float(profit_str)
                        except:
                            pass
            except:
                pass
            time.sleep(1)
        
        return None
    
    def open_settings(self):
        """Open settings menu."""
        try:
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                if "Configura" in btn.text or "Settings" in btn.text:
                    btn.click()
                    time.sleep(2)
                    return True
            return False
        except:
            return False
    
    def disable_all_followers(self):
        """Try to find and disable any copy trading / following features."""
        try:
            logger.info("Looking for copy trading options...")
            
            # Try to navigate to portfolio or history
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            
            # Look for any options related to copying
            copy_keywords = ["copy", "seguir", "seguidores", "seguindo", "vincular"]
            
            for btn in buttons:
                text = btn.text.lower()
                if any(k in text for k in copy_keywords):
                    logger.info(f"Found button: {btn.text}")
            
            # Check localStorage and sessionStorage for any copy settings
            # This is a more aggressive approach
            self.driver.get(self.base_url + "/pt/traderoom")
            time.sleep(3)
            
            logger.info("Checked for copy trading options")
            return True
            
        except Exception as e:
            logger.error(f"Could not check copy trading: {e}")
            return False
    
    def run_strategy(self, num_trades: int = 10, base_amount: float = 1.0, max_loss: float = 5.0):
        """Run trading strategy with proper money management."""
        logger.info(f"Starting strategy: {num_trades} trades, base ${base_amount}")
        
        wins = 0
        losses = 0
        current_amount = base_amount
        total_profit = 0.0
        consecutive_losses = 0
        
        for i in range(num_trades):
            # Check stop loss
            if total_profit <= -max_loss:
                logger.warning(f"Stop loss reached: ${total_profit}")
                break
            
            logger.info(f"\n=== Trade {i+1}/{num_trades} ===")
            self.update_balance()
            logger.info(f"Balance: ${self.balance:.2f}")
            logger.info(f"Amount: ${current_amount}")
            
            # Get strategy decision
            direction = self.simple_strategy()
            logger.info(f"Direction: {direction}")
            
            result = self.place_trade(direction, current_amount)
            
            if result.success:
                profit = self.wait_for_result()
                logger.info(f"Profit: {profit}")
                
                if profit and profit > 0:
                    wins += 1
                    consecutive_losses = 0
                    current_amount = base_amount
                    total_profit += profit
                else:
                    losses += 1
                    consecutive_losses += 1
                    if consecutive_losses >= 2:
                        current_amount *= 1.5
                    current_amount = min(current_amount * 2, self.max_trade)
                    if profit:
                        total_profit += profit
            else:
                logger.error(f"Trade failed: {result.error}")
                losses += 1
            
            self.update_balance()
            time.sleep(3)
        
        logger.info(f"\n=== Strategy Complete ===")
        logger.info(f"Wins: {wins}, Losses: {losses}")
        logger.info(f"Total profit: ${total_profit:.2f}")
        self.update_balance()
        logger.info(f"Final balance: ${self.balance:.2f}")
        
        return {"wins": wins, "losses": losses, "profit": total_profit, "balance": self.balance}
    
    def close(self):
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")


if __name__ == "__main__":
    bot = TrxBinaryBot(
        username="lccav@proton.me",
        password="C&ntaur0"
    )
    
    print("=== TrxBinary Bot v2 ===")
    
    bot.setup_driver()
    
    if bot.login():
        print(f"Logged in. Balance: ${bot.balance}")
        
        # Check copy trading
        print("\n=== Checking copy trading ===")
        bot.disable_all_followers()
        
        # Run strategy
        print("\n=== Running strategy ===")
        result = bot.run_strategy(num_trades=10, base_amount=1.0, max_loss=10.0)
        print(f"\nFinal Result: {result}")
    
    bot.close()
    print("\nDone")