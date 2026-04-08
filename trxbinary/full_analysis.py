import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
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

# Get full page source to analyze
with open("page_source.html", "w", encoding="utf-8") as f:
    f.write(driver.page_source)
print("Page source saved to page_source.html")

# Look for ANY button elements in the entire page
print("\n=== All buttons on page ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    cls = btn.get_attribute('class') or ''
    if text and len(text) < 30:  # Skip empty or very long text
        print(f"  '{text}' | {cls[:60]}")

# Also look for divs that might be clickable trading buttons
print("\n=== All clickable divs ===")
clickable_divs = driver.find_elements(By.XPATH, "//div[contains(@class, 'cursor-pointer')]")
for d in clickable_divs[:30]:
    text = d.text.strip()[:30]
    cls = d.get_attribute('class') or ''
    if text:
        print(f"  '{text}' | {cls[:60]}")

# Try to find elements by their style/appearance - look for green/red colors
print("\n=== Elements with green/red styling ===")
green_elements = driver.find_elements(By.XPATH, "//*[contains(@style, 'green') or contains(@style, 'rgb(34') or contains(@class, 'green')]")
for e in green_elements[:10]:
    print(f"  {e.tag_name}: {e.text[:20]}")

driver.quit()
print("\nDone")