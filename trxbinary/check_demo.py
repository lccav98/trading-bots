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

# Check balance
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if '$' in btn.text:
        print(f"Current balance: {btn.text}")

# Look for settings or profile to find account options
print("\n=== Looking for settings/profile ===")
for btn in buttons:
    text = btn.text.lower()
    if 'config' in text or 'settings' in text or 'perfil' in text:
        btn.click()
        time.sleep(2)
        print("Opened settings")
        break

# Check settings page for account switching
body = driver.find_element(By.TAG_NAME, "body").text

# Look for any "demo", "real", "conta" options
print("\n=== Checking for account type options ===")
lines = body.split('\n')
for line in lines:
    if any(x in line.lower() for x in ['demo', 'real', 'conta', 'saldo', 'mode']):
        print(f"  {line}")

# Look for any dropdown or selector
print("\n=== Looking for selectors ===")
selectors = driver.find_elements(By.XPATH, "//select")
print(f"Select elements: {len(selectors)}")

# Check for toggle switches
toggles = driver.find_elements(By.XPATH, "//div[contains(@class, 'toggle') or contains(@class, 'switch')]")
print(f"Toggle elements: {len(toggles)}")

# Try clicking on the balance to see if it shows different account types
print("\n=== Clicking on balance ===")
for btn in buttons:
    if '$' in btn.text and 'Dep' not in btn.text:
        btn.click()
        time.sleep(2)
        
        # Check if anything appeared
        popups = driver.find_elements(By.XPATH, "//div[contains(@class, 'modal') or contains(@class, 'fixed')]")
        for p in popups[:3]:
            text = p.text[:200]
            if text:
                print(f"  Popup: {text}")
        break

driver.quit()