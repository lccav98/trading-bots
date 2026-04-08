"""
TrxBinary Trading Bot - Fixed Balance Tracking
"""
import time
import random
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("trxbot")


class TradingBot:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.driver = None
        self.balance = 0
        self.wins = 0
        self.losses = 0
    
    def setup(self):
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
    
    def login(self):
        self.driver.get("https://app.trxbinary.com/pt/auth/login")
        time.sleep(5)
        self.driver.find_element(By.ID, "email").send_keys(self.username)
        self.driver.find_element(By.ID, "password").send_keys(self.password)
        self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(8)
        self.update_balance()
        logger.info(f"Logged in. Balance: ${self.balance}")
    
    def update_balance(self):
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
    
    def select_asset(self, asset):
        try:
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                if any(x in btn.text for x in ["EURJPY", "EURUSD", "BTCUSD"]):
                    btn.click()
                    time.sleep(2)
                    break
            
            asset_span = self.driver.find_element(By.XPATH, f"//span[contains(text(), '{asset}')]")
            self.driver.execute_script("arguments[0].click();", asset_span)
            time.sleep(1)
            self.driver.find_element(By.TAG_NAME, "body").send_keys("\u001b")
            time.sleep(1)
        except Exception as e:
            logger.error(f"Select error: {e}")
    
    def place_trade(self, direction, amount=1):
        balance_before = self.balance
        
        try:
            # Set amount
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs:
                try:
                    if inp.get_attribute('aria-valuenow'):
                        inp.clear()
                        inp.send_keys(str(int(amount)))
                        break
                except:
                    pass
            
            time.sleep(0.5)
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
            
            logger.info(f"Trade placed: {direction} ${amount}")
            
            # Wait 65s for result
            time.sleep(65)
            
            # Get new balance
            self.update_balance()
            
            # Calculate actual profit/loss
            actual_profit = self.balance - balance_before
            won = actual_profit >= 0
            
            logger.info(f"Result: {'WIN' if won else 'LOSS'} | Balance: ${self.balance} | P/L: ${actual_profit:.2f}")
            
            return won, actual_profit
            
        except Exception as e:
            logger.error(f"Trade error: {e}")
            return False, 0
    
    def run_session(self, num_trades=5):
        logger.info(f"=== Starting Session: {num_trades} trades ===")
        logger.info(f"Initial: ${self.balance}")
        
        assets = ["EURJPY", "EURUSD"]
        
        for i in range(num_trades):
            logger.info(f"\n--- Trade {i+1}/{num_trades} ---")
            
            # Select asset
            asset = random.choice(assets)
            self.select_asset(asset)
            
            # Random direction
            direction = random.choice(["CALL", "PUT"])
            
            # Place trade
            won, profit = self.place_trade(direction, amount=1)
            
            if won:
                self.wins += 1
            else:
                self.losses += 1
            
            time.sleep(2)
        
        logger.info(f"\n=== Complete ===")
        logger.info(f"Wins: {self.wins}, Losses: {self.losses}")
        logger.info(f"Final: ${self.balance}")


if __name__ == "__main__":
    bot = TradingBot("lccav@proton.me", "C&ntaur0")
    bot.setup()
    bot.login()
    bot.run_session(num_trades=5)
    bot.driver.quit()
    print("\nDone!")