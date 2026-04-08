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

# Try to find all buttons in the modal - let's search more broadly
# The EURJPY is visible so it must be clickable somehow
print("=== Searching for all buttons in modal ===")

# Try finding elements that are in the visible asset list
# They might be in a list or grid container
all_buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in all_buttons:
    text = btn.text.strip()
    # Filter for asset buttons - they have pattern like "EURJPY" or "EUR/JPY"
    if "/" in text or (len(text) >= 3 and len(text) <= 10):
        # Check if it looks like an asset
        if any(currency in text for currency in ['EUR', 'USD', 'JPY', 'GBP', 'AUD', 'CAD', 'CHF']):
            print(f"Asset button: {text}")

# Try finding by EUR and JPY separately
print("\n=== Looking for EUR-related elements ===")
elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'EUR')]")
for el in elements[:10]:
    try:
        tag = el.tag_name
        parent = el.find_element(By.XPATH, "..").tag_name
        print(f"  {tag} > {parent}: {el.text[:30]}")
    except:
        pass

# Let's try clicking on the position where EURJPY would be (it's in the list around position 90)
# From earlier output: EURJPY appears after EURGBP - let's use coordinates
# But first, let's try finding via the list items

# Search for any element containing "/" and "JPY"
print("\n=== Looking for /JPY ===")
jpy_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '/JPY')]")
for el in jpy_elements[:5]:
    print(f"  Found: {el.text}")

driver.quit()