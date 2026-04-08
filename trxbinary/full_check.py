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

# Get initial balance
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text.startswith('$') and len(text) < 15:
        try:
            val = float(text.replace('$', ''))
            if val > 0:
                print(f"Initial balance: ${val}")
                break
        except:
            pass

# Place trade
inputs = driver.find_elements(By.TAG_NAME, "input")
for inp in inputs:
    try:
        if inp.get_attribute('aria-valuenow'):
            inp.clear()
            inp.send_keys("1")
            break
    except:
        pass

buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "Comprar" in btn.text:
        btn.click()
        print("Trade placed, waiting...")
        break

# Wait more than 60s to ensure resolution
time.sleep(75)

# Refresh the page completely
driver.get("https://app.trxbinary.com/pt/traderoom")
time.sleep(5)

# Check balance after full refresh
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text.startswith('$') and len(text) < 15:
        try:
            val = float(text.replace('$', ''))
            if val > 0:
                print(f"After refresh balance: ${val}")
                break
        except:
            pass

# Check portfolio - might have settled trades there
print("\n=== Checking Portfolio ===")
for btn in buttons:
    if "Portf" in btn.text:
        btn.click()
        time.sleep(3)
        break

# Look at all portfolio content
body = driver.find_element(By.TAG_NAME, "body").text
# Find lines with numbers
import re
all_numbers = re.findall(r'[\d,]+\.\d+', body)
print("All numbers in portfolio:")
for n in all_numbers[:20]:
    print(f"  {n}")

# Check if there's any indication of "conta demo" or "conta real"
print("\n=== Checking for account type ===")
if "demo" in body.lower():
    print("Found: DEMO account")
elif "real" in body.lower():
    print("Found: REAL account")
else:
    print("No explicit account type found")

driver.quit()