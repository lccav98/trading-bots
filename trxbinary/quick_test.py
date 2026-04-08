import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Quick test - just place a few trades without waiting for result
username = "lccav@proton.me"
password = "C&ntaur0"

options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

print("=== Quick TrxBinary Test ===")

# Login
driver.get("https://app.trxbinary.com/pt/auth/login")
time.sleep(5)

driver.find_element(By.ID, "email").send_keys(username)
driver.find_element(By.ID, "password").send_keys(password)
driver.find_element(By.XPATH, "//button[@type='submit']").click()
time.sleep(8)

# Find balance
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text.startswith('$') and len(text) < 15:
        try:
            val = float(text.replace('$', ''))
            if val > 0:
                print(f"Balance: ${val}")
                break
        except:
            pass

# Quick trades - just execute without waiting
for i in range(3):
    print(f"\n=== Trade {i+1} ===")
    
    # Set amount
    inputs = driver.find_elements(By.TAG_NAME, "input")
    for inp in inputs:
        try:
            if inp.get_attribute('aria-valuenow'):
                inp.clear()
                inp.send_keys("1")
                break
        except:
            continue
    
    time.sleep(0.5)
    
    # Click random direction
    direction = random.choice(["CALL", "PUT"])
    buttons = driver.find_elements(By.TAG_NAME, "button")
    
    if direction == "CALL":
        for btn in buttons:
            if "Comprar" in btn.text:
                btn.click()
                print(f"Placed: {direction} $1")
                break
    else:
        for btn in buttons:
            if "Vender" in btn.text:
                btn.click()
                print(f"Placed: {direction} $1")
                break
    
    time.sleep(3)

driver.quit()
print("\nDone!")