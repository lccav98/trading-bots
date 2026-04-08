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

# Find input fields for amount and duration
print("=== All input fields ===")
inputs = driver.find_elements(By.TAG_NAME, "input")
for inp in inputs:
    inp_type = inp.get_attribute('type') or 'none'
    inp_id = inp.get_attribute('id') or ''
    inp_name = inp.get_attribute('name') or ''
    inp_placeholder = inp.get_attribute('placeholder') or ''
    print(f"  type={inp_type} id={inp_id} name={inp_name} placeholder={inp_placeholder}")

# Look for any sliders or number inputs
print("\n=== Looking for amount/duration inputs ===")
inputs = driver.find_elements(By.XPATH, "//input[@type='number' or @type='range' or contains(@class, 'amount') or contains(@class, 'value')]")
for inp in inputs[:10]:
    print(f"  {inp.get_attribute('id')} | {inp.get_attribute('class')[:40]}")

# Check what happens when we click "Comprar"
print("\n=== Looking for any modals or popups after clicking Comprar ===")
comprar_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Comprar')]")
comprar_btn.click()
time.sleep(2)

# Check if anything appeared
modals = driver.find_elements(By.XPATH, "//div[contains(@class, 'modal') or contains(@class, 'overlay') or contains(@class, 'fixed')]")
print(f"Modals/popups found: {len(modals)}")

# Look for any new elements after click
buttons_after = driver.find_elements(By.TAG_NAME, "button")
print("\n=== Buttons after clicking Comprar ===")
for btn in buttons_after:
    text = btn.text.strip()
    if text:
        print(f"  '{text}'")

driver.quit()
print("\nDone")