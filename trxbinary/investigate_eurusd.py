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
            initial = float(text.replace('$', ''))
            if initial > 0:
                print(f"Initial: ${initial}")
                break
        except:
            pass

# Select EURUSD
print("\n=== Selecting EURUSD ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "EURJPY" in btn.text or "EURUSD" in btn.text or "BTCUSD" in btn.text:
        btn.click()
        time.sleep(2)
        break

# Find and click EURUSD
try:
    eurusd = driver.find_element(By.XPATH, "//span[contains(text(), 'EURUSD')]")
    driver.execute_script("arguments[0].click();", eurusd)
    print("Clicked EURUSD!")
except Exception as e:
    print(f"Error: {e}")

time.sleep(1)
driver.find_element(By.TAG_NAME, "body").send_keys("\u001b")
time.sleep(1)

# Verify selection
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "EURUSD" in btn.text:
        print(f"Selected: {btn.text}")

# Check the payout for EURUSD
print("\n=== Checking payout ===")
spans = driver.find_elements(By.TAG_NAME, "span")
for span in spans:
    text = span.text.strip()
    if "85%" in text or "payout" in text.lower() or "rentabilidade" in text.lower():
        print(f"  {text}")

# Place a SINGLE $1 trade
print("\n=== Placing ONE $1 trade ===")
inputs = driver.find_elements(By.TAG_NAME, "input")
for inp in inputs:
    try:
        if inp.get_attribute('aria-valuenow'):
            print(f"Current input value: {inp.get_attribute('value')}")
            inp.clear()
            inp.send_keys("1")
            print("Set to $1")
            break
    except:
        pass

time.sleep(1)

# Verify amount was set correctly
inputs = driver.find_elements(By.TAG_NAME, "input")
for inp in inputs:
    try:
        if inp.get_attribute('aria-valuenow'):
            print(f"Verified amount: {inp.get_attribute('value')}")
    except:
        pass

# Click buy
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "Comprar" in btn.text:
        driver.execute_script("arguments[0].click();", btn)
        print("Trade executed!")
        break

# Wait for result
print("Waiting 65s for result...")
time.sleep(65)

# Check balance
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text.startswith('$') and len(text) < 15:
        try:
            final = float(text.replace('$', ''))
            if final > 0:
                print(f"\nFinal: ${final}")
                print(f"Change: ${final - initial}")
                
                # Expected: if win +$0.85, if lose -$1
                if final - initial > 0:
                    print("✅ WIN")
                else:
                    print("❌ LOSS")
                break
        except:
            pass

driver.quit()