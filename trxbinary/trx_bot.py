import time
import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from dataclasses import dataclass
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("trxbot")


@dataclass
class TradeResult:
    success: bool
    direction: str  # "CALL" or "PUT"
    amount: float
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
    
    def setup_driver(self):
        """Initialize Chrome driver."""
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        logger.info("Driver initialized")
    
    def login(self) -> bool:
        """Login to TrxBinary."""
        if not self.username or not self.password:
            logger.error("No credentials provided")
            return False
        
        try:
            self.driver.get(self.base_url + "/auth/login")
            time.sleep(5)
            
            # Wait for login form
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.ID, "email")))
            
            # Enter credentials
            self.driver.find_element(By.ID, "email").send_keys(self.username)
            self.driver.find_element(By.ID, "password").send_keys(self.password)
            self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
            
            # Wait for dashboard
            time.sleep(10)
            
            self.logged_in = True
            self.update_balance()
            logger.info(f"Login successful. Balance: ${self.balance}")
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    def update_balance(self):
        """Get current account balance."""
        try:
            # Look for balance element - it's the button with $ amount at top
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                text = btn.text.strip()
                if text.startswith('$') and text[1:].replace('.', '').isdigit():
                    self.balance = float(text.replace('$', ''))
                    return
        except Exception as e:
            logger.warning(f"Could not update balance: {e}")
    
    def set_amount(self, amount: float):
        """Set the trade amount."""
        try:
            # Find the amount input - it has no id, just an input inside the Investimentos section
            # From page source: input with value="1" and aria-valuenow="1"
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs:
                try:
                    if inp.get_attribute('aria-valuenow'):
                        # This is the amount input
                        inp.clear()
                        inp.send_keys(str(int(amount)))
                        logger.info(f"Amount set to ${amount}")
                        return True
                except:
                    continue
            
            logger.warning("Could not find amount input")
            return False
        except Exception as e:
            logger.error(f"Failed to set amount: {e}")
            return False
    
    def place_trade(self, direction: str, amount: float, asset: str = "BTCUSD") -> TradeResult:
        """
        Place a binary option trade.
        
        Args:
            direction: "CALL" (buy/up) or "PUT" (sell/down)
            amount: Trade amount in dollars
            asset: Asset to trade (default: BTCUSD)
        
        Returns:
            TradeResult with success status
        """
        if not self.logged_in:
            if not self.login():
                return TradeResult(success=False, direction=direction, amount=amount, error="Not logged in")
        
        try:
            # Set amount first
            self.set_amount(amount)
            time.sleep(0.5)
            
            # Click Comprar (CALL) or Vender (PUT)
            # From page source: "Comprar" has class "h-12 text-sm px-3 rounded-lg..."
            # "Vender" has similar class
            if direction.upper() == "CALL":
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    if "Comprar" in btn.text:
                        btn.click()
                        break
            else:  # PUT
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    if "Vender" in btn.text:
                        btn.click()
                        break
            time.sleep(2)
            
            logger.info(f"Trade placed: {direction} ${amount}")
            
            # Update balance after trade
            self.update_balance()
            
            return TradeResult(success=True, direction=direction, amount=amount)
            
        except Exception as e:
            logger.error(f"Trade failed: {e}")
            return TradeResult(success=False, direction=direction, amount=amount, error=str(e))
    
    def wait_for_result(self, timeout: int = 60) -> Optional[float]:
        """
        Wait for trade result and return profit/loss.
        
        Args:
            timeout: Seconds to wait for result
        
        Returns:
            Profit/loss amount or None if still pending
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Look for result indicators (+85%, +$0.85, etc.)
                results = self.driver.find_elements(By.XPATH, "//span[contains(@class, 'text-green') or contains(@class, 'text-red')]")
                
                for result in results:
                    text = result.text.strip()
                    if '$' in text or '%' in text:
                        if '+' in text:
                            # Positive result
                            profit = float(text.replace('$', '').replace('+', '').replace('%', ''))
                            return profit
                        elif '-' in text:
                            # Negative result
                            profit = -float(text.replace('$', '').replace('-', '').replace('%', ''))
                            return profit
                            
            except:
                pass
            
            time.sleep(1)
        
        return None
    
    def close(self):
        """Close browser."""
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")


if __name__ == "__main__":
    # Test the bot
    bot = TrxBinaryBot(
        username="lccav@proton.me",
        password="C&ntaur0"
    )
    
    print("=== TrxBinary Bot Test ===")
    
    # Setup and login
    bot.setup_driver()
    
    if bot.login():
        print(f"Logged in. Balance: ${bot.balance}")
        
        # Test placing a small trade
        result = bot.place_trade("CALL", 1.0)
        print(f"Trade result: {result}")
        
        # Wait for result
        profit = bot.wait_for_result(timeout=60)
        print(f"Profit: {profit}")
    
    bot.close()
    print("Done")