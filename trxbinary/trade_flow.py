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

# Navigate to login page and wait for load
driver.get("https://app.trxbinary.com/pt/auth/login")
time.sleep(5)

# Wait for login form
WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "email")))

# Login
driver.find_element(By.ID, "email").send_keys("lccav@proton.me")
driver.find_element(By.ID, "password").send_keys("C&ntaur0")
driver.find_element(By.XPATH, "//button[@type='submit']").click()

# Wait for dashboard to load
time.sleep(10)

print("=== After login - checking current state ===")
print(f"URL: {driver.current_url}")

# Check for any cookie banner or popup
try:
    cookie_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Aceitar') or contains(text(), 'Accept')]")
    cookie_btn.click()
    time.sleep(1)
except:
    pass

# Find input fields
print("\n=== All input fields on trading page ===")
inputs = driver.find_elements(By.TAG_NAME, "input")
for inp in inputs:
    inp_type = inp.get_attribute('type') or 'none'
    inp_id = inp.get_attribute('id') or ''
    inp_name = inp.get_attribute('name') or ''
    inp_placeholder = inp.get_attribute('placeholder') or ''
    inp_value = inp.get_attribute('value') or ''
    print(f"  type={inp_type} id={inp_id} name={inp_name} placeholder={inp_placeholder} value={inp_value[:20]}")

# Try to click "Comprar" and see what happens
print("\n=== Clicking Comprar ===")
try:
    comprar_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Comprar')]")))
    comprar_btn.click()
    time.sleep(3)
    print("Clicked Comprar")
    
    # Check for any popups
    print("\n=== Looking for any modal or confirmation ===")
    overlays = driver.find_elements(By.XPATH, "//div[contains(@class, 'modal') or contains(@class, 'fixed') or contains(@class, 'absolute')]")
    print(f"Overlay elements found: {len(overlays)}")
    
    # Check page source after click
    with open("after_click.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("Saved after_click.html")
except Exception as e:
    print(f"Error clicking: {e}")

driver.quit()
print("\nDone")