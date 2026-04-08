import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import re

options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

# Login
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
                print(f"Initial balance: ${val}")
                initial = val
                break
        except:
            pass

# Place a trade
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
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "Comprar" in btn.text:
        btn.click()
        print("Trade placed")
        break

# Wait for result
print("Waiting for result...")
time.sleep(65)

# Refresh and check balance
driver.refresh()
time.sleep(5)

# Check balance again
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text.startswith('$') and len(text) < 15:
        try:
            val = float(text.replace('$', ''))
            if val > 0:
                print(f"Final balance: ${val}")
                print(f"Profit: ${val - initial}")
                break
        except:
            pass

# Look for any profit display
print("\n=== Looking for profit display ===")
spans = driver.find_elements(By.TAG_NAME, "span")
for span in spans:
    text = span.text.strip()
    if '+' in text and '$' in text:
        print(f"  Found: {text}")

driver.quit()