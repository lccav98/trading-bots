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

# Wait for the list to load and get all visible options
print("=== Available currency pairs ===")
time.sleep(2)

# Get all buttons in the new panel
panel_buttons = driver.find_elements(By.XPATH, "//div[contains(@class, 'grid')]//button | //div[contains(@class, 'flex') and contains(@class, 'flex-col')]//button")
for btn in panel_buttons:
    text = btn.text.strip()
    if text and len(text) < 20:
        print(f"  {text}")

# Let's also look for any element containing "EUR"
print("\n=== Looking for EUR ===")
all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'EUR')]")
for el in all_elements[:10]:
    parent = el.find_element(By.XPATH, "..")
    print(f"  {el.text} (parent: {parent.tag_name})")

# Try clicking directly on EURUSD text
try:
    eurusd = driver.find_element(By.XPATH, "//button[contains(text(), 'EURUSD')]")
    eurusd.click()
    print("Clicked EURUSD!")
except:
    print("Could not find EURUSD button")

time.sleep(2)

# Check what asset is now selected
print("\n=== After selection ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if "EUR" in text:
        print(f"  Current: {text}")

driver.quit()