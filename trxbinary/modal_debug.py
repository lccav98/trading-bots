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

# Click on the asset selector (where BTCUSD is shown)
print("=== Clicking on asset button ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "BTCUSD" in btn.text:
        # Get its position and size for debugging
        print(f"Found: {btn.text}")
        print(f"Location: {btn.location}")
        print(f"Size: {btn.size}")
        
        # Click it
        btn.click()
        time.sleep(3)
        break

# Now look at what opened
print("\n=== After clicking - looking for all visible content ===")
# Get all text on page to understand the modal structure
body = driver.find_element(By.TAG_NAME, "body")
print(body.text[:1500])

driver.quit()