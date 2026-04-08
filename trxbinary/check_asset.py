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

# Check what asset is currently selected
print("=== Current asset ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if 'EUR' in text or 'USD' in text or 'Forex' in text or 'EURUSD' in text:
        print(f"  Found: {btn.text}")

# Look for asset selector
print("\n=== Looking for asset selector ===")
# Look for dropdown or selector elements
selectors = driver.find_elements(By.XPATH, "//div[contains(@class, 'select') or contains(@class, 'dropdown')]")
for s in selectors[:5]:
    try:
        text = s.text.strip()[:30]
        if text:
            print(f"  {text}")
    except:
        pass

# Check all buttons for any that might be asset related
print("\n=== All buttons with asset-like names ===")
for btn in buttons:
    text = btn.text.strip()
    if text and (len(text) > 2):
        # Check if it might be an asset
        print(f"  {text[:40]}")

# Click on asset selector and see what appears
print("\n=== Clicking first asset button ===")
asset_buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in asset_buttons:
    if "BTC" in btn.text or "EUR" in btn.text or "USD" in btn.text:
        print(f"Clicking: {btn.text[:30]}")
        btn.click()
        time.sleep(2)
        break

# Now what options are visible?
print("\n=== After clicking asset ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text and len(text) > 1:
        print(f"  {text[:40]}")

driver.quit()