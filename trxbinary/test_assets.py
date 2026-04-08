import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# List of assets to test
ASSETS_TO_TEST = ["EURJPY", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]

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

# Get initial balance
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text.startswith('$') and len(text) < 15:
        try:
            initial = float(text.replace('$', ''))
            if initial > 0:
                print(f"Initial balance: ${initial}")
                break
        except:
            pass

def select_asset(asset_name):
    """Select an asset from the dropdown."""
    # Click asset selector
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        if "EURJPY" in btn.text or "BTCUSD" in btn.text:
            btn.click()
            time.sleep(2)
            break
    
    # Click on the asset
    try:
        asset_span = driver.find_element(By.XPATH, f"//span[contains(text(), '{asset_name}')]")
        driver.execute_script("arguments[0].click();", asset_span)
        time.sleep(1)
        
        # Close modal
        driver.find_element(By.TAG_NAME, "body").send_keys("\u001b")
        time.sleep(1)
        
        # Verify selection
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            if asset_name in btn.text:
                print(f"Selected: {btn.text}")
                return True
    except Exception as e:
        print(f"Error selecting {asset_name}: {e}")
        return False

def place_trade():
    """Place a trade and check result."""
    # Set amount
    inputs = driver.find_elements(By.TAG_NAME, "input")
    for inp in inputs:
        try:
            if inp.get_attribute('aria-valuenow'):
                inp.clear()
                inp.send_keys("1")
                break
        except:
            pass
    
    time.sleep(0.5)
    
    # Scroll
    driver.execute_script("window.scrollTo(0, 200);")
    time.sleep(0.5)
    
    # Buy
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        if "Comprar" in btn.text:
            driver.execute_script("arguments[0].click();", btn)
            break
    
    # Wait for result (60s)
    time.sleep(65)
    
    # Check new balance
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        text = btn.text.strip()
        if text.startswith('$') and len(text) < 15:
            try:
                return float(text.replace('$', ''))
            except:
                pass
    return None

# Test each asset
for asset in ASSETS_TO_TEST:
    print(f"\n{'='*40}")
    print(f"TESTING: {asset}")
    print(f"{'='*40}")
    
    # Select asset
    if not select_asset(asset):
        print(f"Failed to select {asset}")
        continue
    
    # Place trade
    print("Placing trade...")
    result_balance = place_trade()
    
    if result_balance:
        print(f"Result balance: ${result_balance}")
    else:
        print("Could not get result balance")
    
    time.sleep(3)

# Final balance
print(f"\n{'='*40}")
print("FINAL RESULTS")
print(f"{'='*40}")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.strip()
    if text.startswith('$') and len(text) < 15:
        try:
            final = float(text.replace('$', ''))
            if final > 0:
                print(f"Final balance: ${final}")
                print(f"Total change: ${final - initial}")
                break
        except:
            pass

driver.quit()