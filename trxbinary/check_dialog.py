import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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

print("=== Checking for confirmation dialogs ===")

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

# Click Comprar
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "Comprar" in btn.text:
        btn.click()
        print("Clicked Comprar")
        break

# IMMEDIATELY check for any popups/modals/dialogs that appeared
time.sleep(1)

print("\n=== Looking for any dialogs ===")
# Look for any fixed/absolute positioned elements that might be dialogs
dialogs = driver.find_elements(By.XPATH, "//div[contains(@class, 'fixed') or contains(@class, 'absolute')]")
for d in dialogs[:10]:
    try:
        text = d.text.strip()[:100]
        if text:
            cls = d.get_attribute('class')[:50]
            print(f"  Dialog: {text} | class: {cls}")
    except:
        pass

# Check for any form or confirmation
print("\n=== Looking for any forms after click ===")
forms = driver.find_elements(By.TAG_NAME, "form")
print(f"Forms found: {len(forms)}")

# Wait and see if something appears
print("\nWaiting 3s to see if confirmation appears...")
time.sleep(3)

# Check again for any new elements
dialogs = driver.find_elements(By.XPATH, "//div[contains(@class, 'fixed') or contains(@class, 'modal')]")
for d in dialogs[:10]:
    try:
        text = d.text.strip()[:100]
        if text and len(text) > 5:
            print(f"  New dialog: {text}")
    except:
        pass

# Check the entire page for anything that looks like a confirmation
print("\n=== Page text after click ===")
body = driver.find_element(By.TAG_NAME, "body").text
if "confirme" in body.lower() or "confirmar" in body.lower() or "confirmação" in body.lower():
    print("FOUND: Confirmation required!")
    # Find where
    lines = body.split('\n')
    for i, line in enumerate(lines):
        if any(x in line.lower() for x in ['confirme', 'confirmar', 'confirmação']):
            print(f"  Line {i}: {line}")
else:
    print("No confirmation text found")

driver.quit()