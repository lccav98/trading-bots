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

# Open asset selector
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "BTCUSD" in btn.text:
        btn.click()
        time.sleep(2)
        break

# Click on EURJPY - the text "EURJPY" appears in the modal
# Let's try to find elements that contain this text
print("=== Looking for EURJPY button ===")
# The structure seems to be: div > div > button or similar
# Let's try to find any button that contains "EURJPY" in text
eurjpy_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'EURJPY')]")
print(f"Found {len(eurjpy_buttons)} buttons with EURJPY")

if not eurjpy_buttons:
    # Try finding via divs with the text
    eurjpy_divs = driver.find_elements(By.XPATH, "//div[contains(text(), 'EURJPY')]")
    print(f"Found {len(eurjpy_divs)} divs with EURJPY")
    
    # Try clicking one of them
    if eurjpy_divs:
        for d in eurjpy_divs:
            try:
                print(f"Trying to click: {d.text}")
                driver.execute_script("arguments[0].click();", d)
                print("Clicked!")
                break
            except:
                pass

time.sleep(2)

# Press ESC to close
driver.find_element(By.TAG_NAME, "body").send_keys("\u001b")
time.sleep(1)

# Check what's now selected
print("\n=== Current selection ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if "EUR" in text or "JPY" in text:
        print(f"Selected: {text}")
        break

# If nothing, might need to click the actual asset button from the list differently
# Let's try scrolling and finding the EURJPY button more directly
print("\n=== Trying with scroll ===")
driver.execute_script("window.scrollTo(0, 200);")
time.sleep(1)

# Refresh the search
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "EURJPY" in btn.text:
        print(f"Found: {btn.text}")
        try:
            btn.click()
            print("Clicked EURJPY!")
        except:
            driver.execute_script("arguments[0].click();", btn)
        break

time.sleep(2)

# Close modal
driver.find_element(By.TAG_NAME, "body").send_keys("\u001b")
time.sleep(1)

# Now check
print("\n=== After selection ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if "EUR" in text and len(text) < 15:
        print(f"FINAL: {text}")
        break

driver.quit()