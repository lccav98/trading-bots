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

# Open asset selector
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "BTCUSD" in btn.text:
        btn.click()
        time.sleep(2)
        break

# Click on the EURJPY span
print("=== Clicking EURJPY span ===")
eurjpy = driver.find_element(By.XPATH, "//span[contains(text(), 'EURJPY')]")
print(f"Found: {eurjpy.text}")
driver.execute_script("arguments[0].click();", eurjpy)
print("Clicked!")

time.sleep(2)

# Press ESC to close modal
driver.find_element(By.TAG_NAME, "body").send_keys("\u001b")
time.sleep(1)

# Check what's now selected
print("\n=== Current asset ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if "EUR" in text or "JPY" in text:
        print(f"Selected: {text}")
        break

# Try to trade
print("\n=== Placing trade ===")
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

time.sleep(0.5)

# Scroll to make buttons visible
driver.execute_script("window.scrollTo(0, 200);")
time.sleep(1)

# Click Comprar
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "Comprar" in btn.text:
        driver.execute_script("arguments[0].click();", btn)
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