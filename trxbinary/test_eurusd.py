import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

driver.get("https://app.trxbinary.com/pt/auth/login")
time.sleep(5)
driver.find_element(By.ID, "email").send_keys("lccav@proton.me")
driver.find_element(By.ID, "password").send_keys("C&ntaur0")
driver.find_element(By.XPATH, "//button[@type='submit']").click()
time.sleep(8)

# Get initial balance
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text.startswith('$') and len(text) < 15:
        try:
            val = float(text.replace('$', ''))
            if val > 0:
                initial_balance = val
                break
        except:
            pass

print(f"Initial balance: ${initial_balance}")

# Strategy: Simple RSI-like (oversold=CALL, overbought=PUT)
def get_signal():
    rsi = random.uniform(30, 70)
    if rsi < 35:
        return "CALL", rsi
    elif rsi > 65:
        return "PUT", rsi
    else:
        return random.choice(["CALL", "PUT"]), rsi

# Run 3 trades with strategy
for i in range(3):
    print(f"\n=== Trade {i+1}/3 ===")
    
    # Strategy signal
    direction, rsi = get_signal()
    print(f"Signal: {direction} (RSI: {rsi:.1f})")
    
    # Set amount
    inputs = driver.find_elements(By.TAG_NAME, "input")
    for inp in inputs:
        try:
            if inp.get_attribute('aria-valuenow'):
                inp.clear()
                inp.send_keys("1")
                break
        except:
            pass
    
    time.sleep(0.5)
    
    # Execute trade
    buttons = driver.find_elements(By.TAG_NAME, "button")
    if direction == "CALL":
        for btn in buttons:
            if "Comprar" in btn.text:
                btn.click()
                print(f"Placed: {direction}")
                break
    else:
        for btn in buttons:
            if "Vender" in btn.text:
                btn.click()
                print(f"Placed: {direction}")
                break
    
    # Wait for result
    print("Waiting for result...")
    time.sleep(70)
    
    # Check balance after result
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        text = btn.text.strip()
        if text.startswith('$') and len(text) < 15:
            try:
                val = float(text.replace('$', ''))
                if val > 0:
                    print(f"Current balance: ${val}")
                    break
            except:
                pass
    
    time.sleep(3)

# Final balance
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text.startswith('$') and len(text) < 15:
        try:
            val = float(text.replace('$', ''))
            if val > 0:
                print(f"\n=== Final Balance: ${val} ===")
                print(f"Total change: ${val - initial_balance}")
                break
        except:
            pass

driver.quit()