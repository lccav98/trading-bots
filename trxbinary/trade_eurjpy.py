import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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

# Click on asset selector
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "BTCUSD" in btn.text:
        btn.click()
        time.sleep(2)
        break

# Click on Pares de moedas
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "Pares de moedas" in btn.text:
        btn.click()
        time.sleep(2)
        break

# Now let's find EURJPY since it's visible - click that instead (closest to EURUSD)
print("=== Clicking EURJPY ===")
divs = driver.find_elements(By.XPATH, "//div[contains(text(), 'EURJPY')]")
for d in divs:
    try:
        parent = d.find_element(By.XPATH, "./..")
        # Try to find button inside parent
        btn = parent.find_element(By.TAG_NAME, "button")
        btn.click()
        print("Clicked EURJPY!")
        break
    except:
        pass

time.sleep(2)

# Verify selection
print("\n=== Current asset ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if "EUR" in text or "JPY" in text:
        print(f"  {text}")

# Get balance and place trade
print("\n=== Placing trade ===")
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

# Buy
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