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

# Check balance
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if '$' in text and len(text) < 15:
        try:
            val = float(text.replace('$', ''))
            if val > 0:
                print(f"Balance: ${val}")
                break
        except:
            pass

# Check if it's demo mode
body = driver.find_element(By.TAG_NAME, "body").text
if "demo" in body.lower():
    print("✅ Demo mode detected!")

# Test a few trades to learn patterns
print("\n=== Testing trades on demo ===")

for i in range(3):
    print(f"\n--- Trade {i+1} ---")
    
    # Select asset
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        if any(x in btn.text for x in ["EURJPY", "EURUSD"]):
            btn.click()
            time.sleep(2)
            break
    
    # Pick EURJPY or EURUSD
    try:
        asset = driver.find_element(By.XPATH, "//span[contains(text(), 'EURJPY')]")
        driver.execute_script("arguments[0].click();", asset)
    except:
        pass
    
    time.sleep(1)
    driver.find_element(By.TAG_NAME, "body").send_keys("\u001b")
    time.sleep(1)
    
    # Set amount
    inputs = driver.find_elements(By.TAG_NAME, "input")
    for inp in inputs:
        try:
            if inp.get_attribute('aria-valuenow'):
                inp.clear()
                inp.send_keys("10")
                break
        except:
            pass
    
    time.sleep(0.5)
    driver.execute_script("window.scrollTo(0, 200);")
    time.sleep(0.5)
    
    # Random direction
    direction = random.choice(["CALL", "PUT"])
    
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        if direction == "CALL" and "Comprar" in btn.text:
            driver.execute_script("arguments[0].click();", btn)
            print(f"Placed: {direction} $10")
            break
        elif direction == "PUT" and "Vender" in btn.text:
            driver.execute_script("arguments[0].click();", btn)
            print(f"Placed: {direction} $10")
            break
    
    # Wait for result
    time.sleep(70)
    
    # Check balance
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        text = btn.text.strip()
        if '$' in text and len(text) < 15:
            try:
                val = float(text.replace('$', ''))
                if val > 0:
                    print(f"Balance after: ${val}")
                    break
            except:
                pass
    
    time.sleep(2)

print("\n=== Demo test complete ===")
driver.quit()