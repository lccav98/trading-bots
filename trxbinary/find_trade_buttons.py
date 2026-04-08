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

# Login
driver.get("https://app.trxbinary.com/pt/auth/login")
driver.find_element(By.ID, "email").send_keys("lccav@proton.me")
driver.find_element(By.ID, "password").send_keys("C&ntaur0")
driver.find_element(By.XPATH, "//button[@type='submit']").click()
time.sleep(8)

print("=== Looking for trade buttons ===")

# Find all clickable elements that might be trade buttons
all_elements = driver.find_elements(By.XPATH, "//button | //div[@role='button'] | //span[contains(@class, 'cursor-pointer')]")

for e in all_elements:
    text = e.text.strip()[:40]
    cls = e.get_attribute('class') or ''
    # Look for potential trading buttons
    if any(x in text.lower() for x in ['call', 'put', 'buy', 'sell', 'high', 'low', 'up', 'down', 'lucro', 'operar', 'entrada']):
        print(f"  TEXT: '{text}' | CLASS: {cls[:60]}")

# Also check for specific classes that might be trading related
print("\n=== Looking for green/red colors (common for CALL/PUT) ===")
colors = driver.find_elements(By.XPATH, "//button[contains(@class, 'green') or contains(@class, 'red') or contains(@class, 'bg-green') or contains(@class, 'bg-red')]")
for e in colors[:10]:
    print(f"  {e.text[:30]} | {e.get_attribute('class')[:60]}")

# Get page source for deeper analysis
print("\n=== All visible divs with common trading classes ===")
divs = driver.find_elements(By.XPATH, "//div[contains(@class, 'trade') or contains(@class, 'option') or contains(@class, 'binary')]")
for d in divs[:10]:
    cls = d.get_attribute('class') or ''
    print(f"  {cls[:80]}")

driver.quit()
print("\nDone")