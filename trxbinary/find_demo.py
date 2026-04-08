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

# Check for demo account options
print("=== Checking for demo mode ===")

# Check login page for demo options
body = driver.find_element(By.TAG_NAME, "body").text
if "demo" in body.lower():
    print("Found 'demo' on page")

# Check for any toggle or switch for demo
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.lower()
    if "demo" in text or "treino" in text or "simulação" in text or "teste" in text:
        print(f"Demo button: {btn.text}")

# Check for any checkboxes or toggles
checkboxes = driver.find_elements(By.XPATH, "//input[@type='checkbox']")
print(f"\nCheckboxes found: {len(checkboxes)}")

# Try logging in with provided credentials first to see if there's a demo mode after login
driver.find_element(By.ID, "email").send_keys("lccav@proton.me")
driver.find_element(By.ID, "password").send_keys("C&ntaur0")
driver.find_element(By.XPATH, "//button[@type='submit']").click()
time.sleep(8)

print("\n=== After login ===")
# Check balance display more carefully
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if '$' in text:
        print(f"  Balance button: '{text}'")

# Look for any "demo" or "conta" text after login
body = driver.find_element(By.TAG_NAME, "body").text
if "demo" in body.lower():
    print("\nFound 'demo' after login!")
    # Find where
    for line in body.split('\n'):
        if 'demo' in line.lower():
            print(f"  {line}")

# Check for account switcher or mode selector
print("\n=== Looking for mode selector ===")
for btn in buttons:
    text = btn.text.lower()
    if 'conta' in text or 'mode' in text or 'real' in text or 'virtual' in text:
        print(f"  {btn.text}")

driver.quit()