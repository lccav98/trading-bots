import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
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

# Step 1: Open asset selector
print("=== Step 1: Open asset selector ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "BTCUSD" in btn.text:
        btn.click()
        time.sleep(2)
        print("Opened")
        break

# Step 2: Click Pares de moedas
print("=== Step 2: Select currency pairs ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "Pares de moedas" in btn.text:
        btn.click()
        time.sleep(2)
        print("Selected Pares de moedas")
        break

# Step 3: Look for EURJPY and click it
print("=== Step 3: Find and click EURJPY ===")
# Try to find any element with EURJPY text and click its parent button
try:
    # Look for divs containing EURJPY
    elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'EURJPY')]")
    if elements:
        # Click using JavaScript
        driver.execute_script("arguments[0].click();", elements[0])
        print("Clicked EURJPY via JS")
    else:
        print("No EURJPY found")
except Exception as e:
    print(f"Error: {e}")

time.sleep(3)

# Step 4: Press Escape to close any overlay
print("=== Step 4: Close overlays ===")
from selenium.webdriver.common.keys import Keys
driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
time.sleep(1)

# Step 5: Now check what asset is selected and try to trade
print("=== Step 5: Check current asset ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
selected_asset = None
for btn in buttons:
    text = btn.text.strip()
    if any(x in text for x in ['EUR', 'USD', 'JPY']) and len(text) < 15:
        print(f"  Selected: {text}")
        selected_asset = text
        break

if not selected_asset:
    # Asset selector might still be open, close it
    print("Closing selector...")
    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(2)
    
    # Check again
    for btn in buttons:
        text = btn.text.strip()
        if "EUR" in text or "JPY" in text:
            print(f"  Now selected: {text}")
            break

# Step 6: Try to place trade with scrolling to avoid overlay
print("=== Step 6: Place trade ===")
# First scroll down a bit
driver.execute_script("window.scrollTo(0, 300);")
time.sleep(1)

# Now find and click Comprar
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "Comprar" in btn.text:
        # Try with JS to avoid overlay issues
        try:
            btn.click()
            print("Clicked Comprar!")
        except:
            driver.execute_script("arguments[0].click();", btn)
            print("Clicked Comprar via JS!")
        break

time.sleep(2)

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