"""
TrxBinary Demo Trading Bot - Testing strategies
"""
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

class DemoBot:
    def __init__(self):
        self.driver = None
        self.balance = 0
        self.wins = 0
        self.losses = 0
        self.trades = []
    
    def setup(self):
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
    
    def login(self):
        self.driver.get("https://app.trxbinary.com/pt/auth/login")
        time.sleep(5)
        self.driver.find_element(By.ID, "email").send_keys("lccav@proton.me")
        self.driver.find_element(By.ID, "password").send_keys("C&ntaur0")
        self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(8)
        self.update_balance()
        print(f"Logged in. Demo Balance: ${self.balance}")
    
    def update_balance(self):
        buttons = self.driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            text = btn.text.strip()
            if '$' in text and len(text) < 20:
                try:
                    val = float(text.replace('$', '').replace(',', ''))
                    if val >= 0:
                        self.balance = val
                        return
                except:
                    pass
    
    def select_asset(self, asset):
        try:
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                if any(x in btn.text for x in ["EURJPY", "EURUSD", "BTCUSD", "FOREX"]):
                    btn.click()
                    time.sleep(2)
                    break
            
            el = self.driver.find_element(By.XPATH, f"//span[contains(text(), '{asset}')]")
            self.driver.execute_script("arguments[0].click();", el)
            time.sleep(1)
            self.driver.find_element(By.TAG_NAME, "body").send_keys("\u001b")
            time.sleep(1)
            return True
        except:
            return False
    
    def execute_trade(self, direction, amount=10):
        balance_before = self.balance
        
        # Set amount
        inputs = self.driver.find_elements(By.TAG_NAME, "input")
        for inp in inputs:
            try:
                if inp.get_attribute('aria-valuenow'):
                    inp.clear()
                    inp.send_keys(str(amount))
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
        
        # Wait longer for balance to update
        print(f"Waiting for result...")
        time.sleep(75)
        
        # Get balance after
        self.update_balance()
        
        # Calculate result
        change = self.balance - balance_before
        
        # Determine win/loss (payout is ~85%, so $10 bet = $8.50 profit)
        if change > 0:
            won = True
            self.wins += 1
        elif change < 0:
            won = False
            self.losses += 1
        else:
            won = None  # Still processing
        
        self.trades.append({
            "direction": direction,
            "amount": amount,
            "before": balance_before,
            "after": self.balance,
            "change": change,
            "won": won
        })
        
        return won, change
    
    def run_test(self, num_trades=5, amount=10):
        print(f"\n=== Demo Trading Test: {num_trades} trades ===")
        print(f"Starting balance: ${self.balance}\n")
        
        assets = ["EURJPY", "EURUSD"]
        
        for i in range(num_trades):
            print(f"--- Trade {i+1}/{num_trades} ---")
            
            # Alternate assets
            asset = assets[i % len(assets)]
            self.select_asset(asset)
            
            # Random direction (50/50)
            direction = random.choice(["CALL", "PUT"])
            print(f"Asset: {asset}, Direction: {direction}, Amount: ${amount}")
            
            won, change = self.execute_trade(direction, amount)
            
            if won == True:
                print(f"WIN! +${change:.2f}")
            elif won == False:
                print(f"LOSS! -${abs(change):.2f}")
            else:
                print(f"Result pending... Balance: ${self.balance}")
            
            print(f"Current: ${self.balance}\n")
            time.sleep(2)
        
        print("=== Results ===")
        self.update_balance()
        print(f"Total trades: {num_trades}")
        print(f"Wins: {self.wins}, Losses: {self.losses}")
        print(f"Final balance: ${self.balance}")


if __name__ == "__main__":
    bot = DemoBot()
    bot.setup()
    bot.login()
    bot.run_test(num_trades=5, amount=10)
    bot.driver.quit()
    print("\nDone!")