import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import os

options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

# Login
driver.get("https://app.trxbinary.com/pt/auth/login")
driver.find_element(By.ID, "email").send_keys("lccav@proton.me")
driver.find_element(By.ID, "password").send_keys("C&ntaur0")
driver.find_element(By.XPATH, "//button[@type='submit']").click()
time.sleep(8)

# Save screenshot
driver.save_screenshot("trxbinary_screenshot.png")
print("Screenshot saved to trxbinary_screenshot.png")

# Get page structure - look for main containers
print("\n=== Page Structure (main sections) ===")
main_divs = driver.find_elements(By.XPATH, "//div[@class and contains(@class, 'flex')]")
for d in main_divs[:20]:
    cls = d.get_attribute('class')[:100]
    children = len(d.find_elements(By.XPATH, "./*"))
    print(f"  {cls} | children: {children}")

# Look for any iframes (some trading platforms use iframes)
print("\n=== Iframes ===")
iframes = driver.find_elements(By.TAG_NAME, "iframe")
print(f"Found {len(iframes)} iframes")

# Check for canvas (trading charts often use canvas)
print("\n=== Canvas elements ===")
canvases = driver.find_elements(By.TAG_NAME, "canvas")
print(f"Found {len(canvases)} canvas elements")

# Try to find any element containing "CALL" or "PUT" text
print("\n=== Elements with trading text ===")
all_text = driver.find_elements(By.XPATH, "//*[contains(text(), 'CALL') or contains(text(), 'PUT') or contains(text(), 'M1') or contains(text(), 'M5')]")
for e in all_text[:10]:
    print(f"  {e.tag_name}: {e.text[:30]}")

driver.quit()
print("\nDone")