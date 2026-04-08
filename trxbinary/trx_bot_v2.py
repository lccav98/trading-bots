import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dataclasses import dataclass
from typing import Optional
import logging
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
        self.trade_duration = 60  # seconds
    
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
        try:
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                text = btn.text.strip()
                if text.startswith('$') and text[1:].replace('.', '').isdigit():
                    self.balance = float(text.replace('$', ''))
                    return
        except:
            pass
    
    def set_amount(self, amount: float):
        amount = max(self.min_trade, min(amount, self.max_trade))
        try:
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs:
                try:
                    if inp.get_attribute('aria-valuenow'):
                        inp.clear()
                        inp.send_keys(str(int(amount)))
                        logger.info(f"Amount set to ${amount}")
                        return True
                except:
                    continue
            return False
        except Exception as e:
            logger.error(f"Failed to set amount: {e}")
            return False
    
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
            
            self.update_balance()
            return TradeResult(success=True, direction=direction, amount=amount, duration=self.trade_duration)
            
        except Exception as e:
            logger.error(f"Trade failed: {e}")
            return TradeResult(success=False, direction=direction, amount=amount, duration=self.trade_duration, error=str(e))
    
    def wait_for_result(self, timeout: int = 120):
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check for result in the trade history or popup
                spans = self.driver.find_elements(By.TAG_NAME, "span")
                for span in spans:
                    text = span.text.strip()
                    if '$' in text and ('+' in text or '-' in text):
                        if '+' in text:
                            return float(text.replace('$', '').replace('+', '').strip())
                        elif '-' in text:
                            return -float(text.replace('$', '').replace('-', '').strip())
            except:
                pass
            time.sleep(1)
        
        return None
    
    def disable_copytrading(self):
        """Navigate to copy trading settings and disable it."""
        try:
            # Find copy trading button in sidebar
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                if "Copy trading" in btn.text:
                    logger.info("Found Copy trading button")
                    btn.click()
                    time.sleep(3)
                    break
            
            # Look for disable/stop button
            # Common patterns: "Sair", "Desativar", "Stop", "Exit"
            page_text = self.driver.page_source
            
            if "stop" in page_text.lower() or "sair" in page_text.lower() or "desativar" in page_text.lower():
                disable_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for btn in disable_buttons:
                    text = btn.text.lower()
                    if any(x in text for x in ['sair', 'desativar', 'stop', 'exit', 'cancelar']):
                        logger.info(f"Clicking: {btn.text}")
                        btn.click()
                        time.sleep(2)
                        logger.info("Copy trading disabled")
                        return True
            
            logger.info("Could not find copy trading settings to disable")
            return False
            
        except Exception as e:
            logger.error(f"Failed to disable copy trading: {e}")
            return False
    
    def run_strategy(self, num_trades: int = 10, base_amount: float = 1.0):
        """Run a basic strategy with martingale."""
        logger.info(f"Starting strategy: {num_trades} trades, base amount ${base_amount}")
        
        wins = 0
        losses = 0
        current_amount = base_amount
        
        for i in range(num_trades):
            logger.info(f"\n=== Trade {i+1}/{num_trades} ===")
            logger.info(f"Balance: ${self.balance}")
            logger.info(f"Amount: ${current_amount}")
            
            # Simple strategy: random direction (50/50)
            # In a real strategy, you'd analyze the chart
            direction = random.choice(["CALL", "PUT"])
            logger.info(f"Direction: {direction}")
            
            result = self.place_trade(direction, current_amount)
            
            if result.success:
                profit = self.wait_for_result()
                logger.info(f"Result: {profit}")
                
                if profit and profit > 0:
                    wins += 1
                    current_amount = base_amount  # Reset after win
                else:
                    losses += 1
                    current_amount *= 2  # Martingale after loss
                    current_amount = min(current_amount, self.max_trade)
            else:
                logger.error(f"Trade failed: {result.error}")
                losses += 1
            
            self.update_balance()
            time.sleep(2)
        
        logger.info(f"\n=== Strategy Complete ===")
        logger.info(f"Wins: {wins}, Losses: {losses}")
        logger.info(f"Final balance: ${self.balance}")
    
    def close(self):
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")


if __name__ == "__main__":
    bot = TrxBinaryBot(
        username="lccav@proton.me",
        password="C&ntaur0"
    )
    
    print("=== TrxBinary Bot ===")
    
    bot.setup_driver()
    
    if bot.login():
        print(f"Logged in. Balance: ${bot.balance}")
        
        # Disable copy trading
        print("\n=== Checking copy trading ===")
        bot.disable_copytrading()
        
        # Run strategy
        print("\n=== Running strategy ===")
        bot.run_strategy(num_trades=5, base_amount=1.0)
    
    bot.close()
    print("\nDone")