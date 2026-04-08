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

print("=== Looking for ALL buttons with text ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text:
        print(f"  '{text}'")

print("\n=== After clicking Comprar ===")

# Set amount first
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

# Wait a moment
time.sleep(2)

print("\n=== Buttons AFTER clicking ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text:
        print(f"  '{text}'")

# Look for any button that might be "Execute", "Confirm", "Trade"
print("\n=== Looking for Execute/Confirm buttons ===")
all_buttons = driver.find_elements(By.XPATH, "//button")
for btn in all_buttons:
    text = btn.text.lower()
    if any(x in text for x in ['execut', 'confirm', 'enviar', 'operar', 'abrir', 'iniciar']):
        print(f"  FOUND: {btn.text}")

# Also look at what's happening in the UI - is there a status?
print("\n=== Looking for status/processing indicators ===")
# Look for any elements that might indicate trade status
elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'processando') or contains(text(), 'executando') or contains(text(), 'processing') or contains(text(), 'executing')]")
for e in elements:
    print(f"  Status: {e.text}")

driver.quit()