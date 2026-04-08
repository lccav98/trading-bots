import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

username = "lccav@proton.me"
password = "C&ntaur0"

options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

print("Opening TrxBinary login...")
driver.get("https://app.trxbinary.com/pt/auth/login")
time.sleep(3)

# Login
driver.find_element(By.ID, "email").send_keys(username)
driver.find_element(By.ID, "password").send_keys(password)
driver.find_element(By.XPATH, "//button[@type='submit']").click()

print("Logging in...")
time.sleep(8)

print("\n=== Current URL ===")
print(driver.current_url)

print("\n=== Page Title ===")
print(driver.title)

print("\n=== Balance Elements ===")
# Look for balance/saldo
elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'R$') or contains(text(), 'saldo') or contains(text(), 'balance')]")
for e in elements[:10]:
    print(f"  {e.text}")

print("\n=== All Buttons ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons[:15]:
    text = btn.text.strip()[:30]
    if text:
        print(f"  {text} | class: {btn.get_attribute('class')[:50]}")

print("\n=== Trade Section ===")
# Look for CALL/PUT buttons
trade_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'call') or contains(@class, 'put') or contains(@class, 'high') or contains(@class, 'low')]")
for btn in trade_buttons[:10]:
    print(f"  {btn.text[:20]} | {btn.get_attribute('class')}")

driver.quit()
print("\nDone")