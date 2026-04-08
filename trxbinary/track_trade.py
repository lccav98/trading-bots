import time
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

# Place a trade and track what happens
print("=== Placing trade and monitoring ===")

# Set amount
inputs = driver.find_elements(By.TAG_NAME, "input")
for inp in inputs:
    try:
        if inp.get_attribute('aria-valuenow'):
            inp.clear()
            inp.send_keys("1")
            print("Amount set to $1")
            break
    except:
        pass

time.sleep(1)

# Click buy
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "Comprar" in btn.text:
        btn.click()
        print("Clicked Comprar")
        break

# Immediately after clicking - what changed?
time.sleep(2)
print("\n=== After trade - elements with $ ===")
all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '$')]")
for el in all_elements[:10]:
    text = el.text.strip()
    if text:
        print(f"  {text}")

# Wait for result (60s)
print("\nWaiting 65s for result...")
time.sleep(65)

# Check again
print("\n=== After result - elements with $ ===")
all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '$')]")
for el in all_elements[:10]:
    text = el.text.strip()
    if text:
        print(f"  {text}")

# Check history
print("\n=== Checking history ===")
for btn in buttons:
    if "Hist" in btn.text:
        btn.click()
        time.sleep(3)
        break

# Get all text from history section
history = driver.find_element(By.TAG_NAME, "body").text
# Print lines with numbers that look like transactions
import re
lines = history.split('\n')
for line in lines:
    if re.search(r'\d+\.\d+', line) and any(x in line.lower() for x in ['r$', 'ganho', 'perda', 'lucro', 'vencido']):
        print(f"  {line}")

# Final balance check
print("\n=== Final balance ===")
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

driver.quit()