import time
import random
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

print("=== TrxBinary Demo Mode Test ===\n")

driver.get("https://app.trxbinary.com/pt/auth/login")
time.sleep(5)

driver.find_element(By.ID, "email").send_keys("lccav@proton.me")
driver.find_element(By.ID, "password").send_keys("C&ntaur0")
driver.find_element(By.XPATH, "//button[@type='submit']").click()
time.sleep(8)

# Get initial balance
def get_balance():
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        text = btn.text.strip()
        if '$' in text and len(text) < 20:
            try:
                val = float(text.replace('$', '').replace(',', ''))
                if val >= 0:
                    return val
            except:
                pass
    return 0

initial = get_balance()
print(f"Initial balance: ${initial}")

# Test 3 trades
wins = 0
losses = 0

for i in range(3):
    print(f"\n--- Trade {i+1}/3 ---")
    
    # Select EURJPY
    try:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            if any(x in btn.text for x in ["EURJPY", "EURUSD", "BTCUSD", "FOREX"]):
                btn.click()
                time.sleep(2)
                break
        
        time.sleep(1)
        eurusd = driver.find_element(By.XPATH, "//span[contains(text(), 'EURJPY')]")
        driver.execute_script("arguments[0].click();", eurusd)
        print("Selected: EURJPY")
    except Exception as e:
        print(f"Select error: {e}")
    
    time.sleep(1)
    driver.find_element(By.TAG_NAME, "body").send_keys("\u001b")
    time.sleep(1)
    
    # Set amount $10
    try:
        inputs = driver.find_elements(By.TAG_NAME, "input")
        for inp in inputs:
            if inp.get_attribute('aria-valuenow'):
                inp.clear()
                inp.send_keys("10")
                print("Amount: $10")
                break
    except:
        pass
    
    time.sleep(0.5)
    driver.execute_script("window.scrollTo(0, 200);")
    time.sleep(0.5)
    
    # Random direction
    direction = random.choice(["CALL", "PUT"])
    print(f"Direction: {direction}")
    
    try:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            if direction == "CALL" and "Comprar" in btn.text:
                driver.execute_script("arguments[0].click();", btn)
                break
            elif direction == "PUT" and "Vender" in btn.text:
                driver.execute_script("arguments[0].click();", btn)
                break
        print("Trade executed!")
    except Exception as e:
        print(f"Trade error: {e}")
    
    # Wait for result
    print("Waiting 65s...")
    time.sleep(65)
    
    # Check result
    balance_before = get_balance()
    time.sleep(2)
    balance_after = get_balance()
    
    change = balance_after - balance_before
    if change > 0:
        print(f"WIN! +${abs(change):.2f}")
        wins += 1
    elif change < 0:
        print(f"LOSS! -${abs(change):.2f}")
        losses += 1
    else:
        print("No change detected")
    
    print(f"Current balance: ${balance_after}")
    time.sleep(2)

print(f"\n=== Results ===")
final = get_balance()
print(f"Wins: {wins}, Losses: {losses}")
print(f"Initial: ${initial}, Final: ${final}")
print(f"Total change: ${final - initial}")

driver.quit()