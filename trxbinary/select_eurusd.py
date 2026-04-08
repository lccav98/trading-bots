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

# Click on asset selector (BTCUSD button)
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "BTCUSD" in btn.text or "Crypto" in btn.text:
        btn.click()
        time.sleep(2)
        print("Opened asset selector")
        break

# Click on "Pares de moedas" (Currency Pairs)
time.sleep(1)
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "Pares de moedas" in btn.text:
        btn.click()
        time.sleep(2)
        print("Clicked Pares de moedas")
        break

# Now look for EURUSD
print("\n=== Looking for EURUSD ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "EUR" in btn.text or "EURUSD" in btn.text:
        print(f"Found: {btn.text}")
        btn.click()
        print("Selected EURUSD!")
        break

time.sleep(2)

# Verify it's now EURUSD
print("\n=== Current asset ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "EUR" in btn.text or "USD" in btn.text or "Forex" in btn.text:
        print(f"  {btn.text}")

# Get balance and place trade
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text.startswith('$') and len(text) < 15:
        try:
            val = float(text.replace('$', ''))
            if val > 0:
                print(f"\nBalance: ${val}")
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
            print("Amount: $1")
            break
    except:
        pass

time.sleep(0.5)
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "Comprar" in btn.text:
        btn.click()
        print("Trade placed!")
        break

# Wait for result
print("Waiting for result...")
time.sleep(70)

# Check balance
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text.startswith('$') and len(text) < 15:
        try:
            val = float(text.replace('$', ''))
            if val > 0:
                print(f"\nFinal balance: ${val}")
                break
        except:
            pass

driver.quit()