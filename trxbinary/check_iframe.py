import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

driver.get("https://app.trxbinary.com/pt/auth/login")
driver.find_element(By.ID, "email").send_keys("lccav@proton.me")
driver.find_element(By.ID, "password").send_keys("C&ntaur0")
driver.find_element(By.XPATH, "//button[@type='submit']").click()
time.sleep(8)

# Check iframe
print("=== Iframe Details ===")
iframe = driver.find_element(By.TAG_NAME, "iframe")
print(f"src: {iframe.get_attribute('src')}")
print(f"id: {iframe.get_attribute('id')}")
print(f"class: {iframe.get_attribute('class')}")

# Switch to iframe
driver.switch_to.frame(iframe)
print("\n=== Inside iframe ===")

# Now look for buttons inside iframe
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons[:20]:
    text = btn.text.strip()[:40]
    if text:
        cls = btn.get_attribute('class') or ''
        print(f"  '{text}' | class: {cls[:80]}")

# Look for any clickable areas
print("\n=== Clickable elements ===")
clickables = driver.find_elements(By.XPATH, "//*[contains(@class, 'cursor-pointer')]")
for c in clickables[:20]:
    text = c.text.strip()[:30]
    if text:
        print(f"  '{text}'")

driver.switch_to.default_content()
driver.quit()
print("\nDone")