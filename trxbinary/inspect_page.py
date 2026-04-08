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

print("Opening TrxBinary...")
driver.get("https://app.trxbinary.com/pt")
time.sleep(5)

print("\n=== Page Title ===")
print(driver.title)

print("\n=== All Input Fields ===")
inputs = driver.find_elements(By.TAG_NAME, "input")
for inp in inputs:
    print(f"  type={inp.get_attribute('type')} id={inp.get_attribute('id')} name={inp.get_attribute('name')} placeholder={inp.get_attribute('placeholder')}")

print("\n=== All Buttons ===")
buttons = driver.find_elements(By.TAG_NAME, "button")
for btn in buttons:
    print(f"  text={btn.text} type={btn.get_attribute('type')} class={btn.get_attribute('class')}")

print("\n=== All Links/Forms ===")
forms = driver.find_elements(By.TAG_NAME, "form")
for form in forms:
    print(f"  action={form.get_attribute('action')} method={form.get_attribute('method')}")

driver.quit()
print("\nDone")