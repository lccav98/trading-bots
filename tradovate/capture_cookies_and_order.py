"""Launch stealth browser, login, capture cookies, test orders."""
import requests, json, time
from playwright.sync_api import sync_playwright

TRADOVATE_URL = "https://trader.tradovate.com"
BASE = "https://demo.tradovateapi.com/v1"

# User credentials from settings
USER = "APEX_549417"
PASS = "A16@JTWG2@$v"

pw = sync_playwright().start()
browser = pw.chromium.launch_persistent_context(
    user_data_dir="data/browser_capture",
    headless=False,
    viewport={"width": 1400, "height": 900},
    locale="pt-BR",
    args=["--disable-blink-features=AutomationControlled",
          "--no-first-run", "--no-default-browser-check"],
)

page = browser.pages[0] if browser.pages else browser.new_page()

# Anti-detection
page.add_init_script("""
    Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
    window.chrome={runtime:{},loadTiles:function(){},csi:function(){},app:{}};
""")

print("=== Navigating to tradovate... ===")
page.goto(TRADOVATE_URL, wait_until="domcontentloaded", timeout=60000)
page.wait_for_timeout(3000)

# Auto-fill login
for sel in ['input[placeholder*="Username"]', 'input[placeholder*="Email"]', 'input[name="username"]']:
    try:
        inp = page.locator(sel).first
        if inp.is_visible({"timeout": 2000}):
            inp.fill(USER)
            print("Username filled")
            break
    except:
        pass

page.wait_for_timeout(500)
try:
    pwd = page.locator('input[type="password"]').first
    if pwd.is_visible({"timeout": 3000}):
        pwd.fill(PASS)
        print("Password filled")
except:
    pass

page.wait_for_timeout(1000)
# Click login
for sel in ['button.Login', 'button:has-text("Login")', '#login-button']:
    try:
        btn = page.locator(sel).first
        if btn.is_visible({"timeout": 2000}):
            btn.click()
            print("Login button clicked")
            break
    except:
        pass

# Press enter on password field
pwd = page.query_selector('input[type="password"]')
if pwd:
    pwd.press("Enter")
    print("Enter pressed")

print("Waiting for page to load... (resolve captcha if needed)")
print("I'll wait 30 seconds...")
page.wait_for_timeout(30000)

print(f"Current URL: {page.url}")

# Capture token from requests
captured_token = None

def on_response(response):
    global captured_token
    if captured_token:
        return
    auth = response.request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and len(auth) > 60:
        captured_token = auth.replace("Bearer ", "")
        print(f"\n🔑 Token captured!")

page.on("response", on_response)

# If not on trading page, wait longer
if "trading" not in page.url.lower() and "dashboard" not in page.url.lower():
    input("⚠️  You may need to navigate to the trading page manually. Press ENTER when ready...")
    page.wait_for_timeout(5000)

# Capture cookies
cookies = browser.cookies()
print(f"\n=== Cookies captured: {len(cookies)} ===")
cookie_dict = {c["name"]: c["value"] for c in cookies}

# Print relevant cookies
for name, val in cookie_dict.items():
    if len(val) > 20 or "token" in name.lower() or "auth" in name.lower() or "session" in name.lower():
        print(f"  {name}: {val[:80]}...")

# If no token captured from intercepted responses, try to trigger one
if not captured_token:
    print("\nReloading to capture token from requests...")
    page.reload()
    page.wait_for_timeout(10000)

if captured_token:
    print(f"\nToken full length: {len(captured_token)}")
else:
    print("⚠️ Token not captured from responses")
    # Try renew endpoint with cookies
    print("\nTrying /auth/renewaccesstoken with cookies...")
    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
    headers = {
        "Content-Type": "application/json",
        "Cookie": cookie_str,
    }
    resp = requests.post(f"{BASE}/auth/renewaccesstoken", headers=headers, timeout=10)
    print(f"  Status: {resp.status_code}")
    try:
        data = resp.json()
        if "accessToken" in data:
            captured_token = data["accessToken"]
            print(f"  Token renewed! {captured_token[:40]}...")
        else:
            print(f"  Response: {data}")
    except:
        print(f"  Raw: {resp.text[:200]}")

# Now test orders
if captured_token:
    print(f"\n{'='*50}")
    print("=== TESTING ORDERS ===")
    print(f"{'='*50}")

    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)

    tests = [
        ("Bearer only", {
            "Authorization": f"Bearer {captured_token}",
            "Content-Type": "application/json",
        }),
        ("Bearer + Origin + Referer", {
            "Authorization": f"Bearer {captured_token}",
            "Content-Type": "application/json",
            "Origin": "https://trader.tradovate.com",
            "Referer": "https://trader.tradovate.com/",
        }),
        ("Bearer + Cookies", {
            "Authorization": f"Bearer {captured_token}",
            "Content-Type": "application/json",
            "Cookie": cookie_str,
        }),
        ("Bearer + Cookies + Origin + Referer", {
            "Authorization": f"Bearer {captured_token}",
            "Content-Type": "application/json",
            "Cookie": cookie_str,
            "Origin": "https://trader.tradovate.com",
            "Referer": "https://trader.tradovate.com/",
        }),
        ("Cookies only (no bearer)", {
            "Content-Type": "application/json",
            "Cookie": cookie_str,
            "Origin": "https://trader.tradovate.com",
            "Referer": "https://trader.tradovate.com/",
        }),
    ]

    payload = {
        "accountSpec": "APEX5494170000001",
        "accountId": 45402487,
        "action": "Buy",
        "symbol": "MNQ",
        "orderQty": 1,
        "orderType": "Market",
    }

    for name, headers in tests:
        resp = requests.post(f"{BASE}/order/placeorder", json=payload, headers=headers, timeout=10)
        try:
            data = resp.json()
            has_id = "orderId" in str(data)
            print(f"\n  {'✅' if has_id else '❌'} {name}: {data}")
            if has_id:
                print("  >>> SUCCESS! This auth method works!")
                break
        except:
            print(f"\n  ❌ {name}: HTTP {resp.status_code} - {resp.text[:200]}")

    # Also test OSO
    print(f"\n  --- Testing OSO order ---")
    oso_payload = {
        "accountSpec": "APEX5494170000001",
        "accountId": 45402487,
        "action": "Buy",
        "symbol": "MNQ",
        "orderQty": 1,
        "orderType": "Market",
        "isAutomated": True,
        "bracket1": {"action": "Sell", "orderType": "Stop", "stopPrice": 24000, "orderQty": 1},
        "bracket2": {"action": "Sell", "orderType": "Limit", "price": 24500, "orderQty": 1},
    }

    best_headers = {
        "Authorization": f"Bearer {captured_token}",
        "Content-Type": "application/json",
        "Cookie": cookie_str,
        "Origin": "https://trader.tradovate.com",
        "Referer": "https://trader.tradovate.com/",
    }
    resp = requests.post(f"{BASE}/order/placeOSO", json=oso_payload, headers=best_headers, timeout=10)
    print(f"  OSO: {resp.status_code} -> {resp.json()}")
else:
    print("\n⚠️ No token available. Cannot test orders.")

print("\n\nDone!")
browser.close()
pw.stop()
