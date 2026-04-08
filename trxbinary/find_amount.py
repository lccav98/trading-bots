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
options.add_argument("--disable-blink-features=AutomationControlled")

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

driver.get("https://app.trxbinary.com/pt/auth/login")
time.sleep(5)
WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "email")))

driver.find_element(By.ID, "email").send_keys("lccav@proton.me")
driver.find_element(By.ID, "password").send_keys("C&ntaur0")
driver.find_element(By.XPATH, "//button[@type='submit']").click()
time.sleep(10)

# Look specifically at the bottom section where the trade buttons are
print("=== Looking at trade control section ===")

# Find parent containers of Comprar/Vender buttons
comprar = driver.find_element(By.XPATH, "//button[contains(text(), 'Comprar')]")
parent_div = comprar.find_element(By.XPATH, "./../..")  # Go up 2 levels
print(f"Parent classes: {parent_div.get_attribute('class')[:100]}")

# Get all children of this parent
children = parent_div.find_elements(By.XPATH, ".//*")
print(f"Number of child elements: {len(children)}")

# Look for any input, select, or number elements in this area
print("\n=== Inputs in trade area ===")
all_inputs = driver.find_elements(By.TAG_NAME, "input")
for inp in all_inputs:
    parent = inp.find_element(By.XPATH, "..")
    parent_class = parent.get_attribute('class') or ''
    if 'trade' in parent_class.lower() or 'option' in parent_class.lower() or 'amount' in parent_class.lower():
        print(f"  Found: {inp.get_attribute('class')[:50]}")

# Let's also check what the input with value=1 is about
print("\n=== The input field found ===")
input_elem = driver.find_element(By.XPATH, "//input[@value='1']")
print(f"Class: {input_elem.get_attribute('class')}")
print(f"Parent: {input_elem.find_element(By.XPATH, '..').get_attribute('class')[:80]}")

# Try to interact with it - maybe it's the amount
input_elem.clear()
input_elem.send_keys("10")
print("Changed value to 10")

# Click Comprar after changing amount
time.sleep(1)
comprar.click()
time.sleep(3)

# Check if any confirmation appeared
print("\n=== Looking for confirmation dialog ===")
dialogs = driver.find_elements(By.XPATH, "//div[contains(@class, 'dialog') or contains(@class, 'confirm') or contains(@role, 'dialog')]")
print(f"Dialogs found: {len(dialogs)}")

# Take screenshot after click
driver.save_screenshot("after_trade_click.png")
print("Saved screenshot after_trade_click.png")

driver.quit()
print("\nDone")