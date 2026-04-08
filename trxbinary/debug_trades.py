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

print("=== Checking ALL $ values on page ===")
# Find ALL elements that contain dollar signs
all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '$')]")
for el in all_elements:
    text = el.text.strip()
    if text:
        parent = el.find_element(By.XPATH, "..").tag_name
        print(f"  {text[:50]} (parent: {parent})")

print("\n=== Checking Histórico ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    if "Hist" in btn.text:
        btn.click()
        time.sleep(3)
        break

# Look at history table
print("\nHistory content:")
history_text = driver.find_element(By.TAG_NAME, "body").text
# Find anything with numbers and dates
import re
matches = re.findall(r'\d{2}/\d{2}/\d{4}.*\d+\.\d+', history_text)
for m in matches[:10]:
    print(f"  {m}")

print("\n=== Checking page source for 'result' or 'status' ===")
if "vencido" in history_text.lower() or "ganho" in history_text.lower() or "perda" in history_text.lower():
    print("Found trade results!")
else:
    print("No trade results found in history")

driver.quit()