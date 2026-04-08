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

# Login
driver.get("https://app.trxbinary.com/pt/auth/login")
time.sleep(5)
driver.find_element(By.ID, "email").send_keys("lccav@proton.me")
driver.find_element(By.ID, "password").send_keys("C&ntaur0")
driver.find_element(By.XPATH, "//button[@type='submit']").click()
time.sleep(8)

# Look for balance indicators - check page source for "demo" vs "real"
print("=== Looking for balance types ===")

# Search for any balance-related text
all_text = driver.find_element(By.TAG_NAME, "body").text
lines = all_text.split('\n')
for line in lines[:30]:
    if 'saldo' in line.lower() or 'balance' in line.lower() or '$' in line:
        print(f"  {line}")

# Look for any mode indicator (demo/real)
print("\n=== Looking for account type ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    text = btn.text.lower()
    if 'demo' in text or 'real' in text or 'conta' in text or 'conta' in text:
        print(f"  Button: {btn.text}")

# Check if there's a "Portfólio" or wallet section
print("\n=== Looking for portfolio/wallet ===")
for btn in buttons:
    if "Portf" in btn.text or "Carteira" in btn.text:
        btn.click()
        time.sleep(3)
        print("Clicked portfolio")
        
        # Look at the page now
        portfolio_text = driver.find_element(By.TAG_NAME, "body").text
        print("\nPortfolio content (first 500 chars):")
        print(portfolio_text[:500])
        break

driver.quit()