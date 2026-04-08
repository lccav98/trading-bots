"""Connect to running Chrome via CDP, capture token, test order."""
import requests
import time

# Step 1: Connect to Chrome CDP
from playwright.sync_api import sync_playwright

print("=== Connecting to Chrome CDP on port 9222 ===")

pw = sync_playwright().start()

try:
    browser = pw.chromium.connect_over_cdp("http://localhost:9222")
    print(f"Connected! Contexts: {browser.contexts}")

    ctx = browser.contexts[0]
    pages = ctx.pages
    print(f"Pages: {len(pages)}")

    # Find the tradovate page or create new
    target_page = None
    for p in pages:
        url = p.url
        print(f"  Page: {url}")
        if "tradovate" in url.lower():
            target_page = p

    if not target_page:
        print("Opening tradovate...")
        target_page = ctx.new_page()
        target_page.goto("https://trader.tradovate.com", wait_until="domcontentloaded", timeout=30000)
        # Wait for user to be on the right page
        input("Press ENTER when you're seeing the Trading page...")

    # Wait a bit
    target_page.wait_for_timeout(3000)
    print(f"Current URL: {target_page.url}")

    # Capture token from requests
    captured_token = None
    captured_cookies = {}

    def on_response(response):
        global captured_token
        if captured_token:
            return
        # Check for auth header in request
        req_headers = response.request.headers
        auth = req_headers.get("authorization", "")
        if auth.startswith("Bearer ") and len(auth) > 60:
            captured_token = auth.replace("Bearer ", "")
            print(f"\n🔑 Token capturado: {captured_token[:40]}...")

    def on_request(request):
        global captured_token
        if captured_token:
            return
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer ") and len(auth) > 60:
            captured_token = auth.replace("Bearer ", "")
            print(f"\n🔑 Token capturado (request): {captured_token[:40]}...")

    target_page.on("response", on_response)
    target_page.on("request", on_request)

    # Trigger requests by reloading
    print("Reloading page to capture auth headers...")
    target_page.reload()
    target_page.wait_for_timeout(10000)

    if not captured_token:
        print("Token not captured from headers. Trying cookies...")
        cookies = ctx.cookies()
        for c in cookies:
            print(f"  Cookie: {c['name'][:30]}... = {c['value'][:30]}...")

        # Check if there's a token-like cookie
        for c in cookies:
            if len(c['value']) > 100 or 'token' in c['name'].lower():
                print(f"\n  Possible token cookie: {c['name']}")
                print(f"  Value: {c['value'][:80]}...")

    if not captured_token:
        print("\nTrying to find token via intercepting account/list request...")
        # Navigate to cause auth request
        try:
            with target_page.expect_response("**/account/**", timeout=10000) as resp_info:
                target_page.wait_for_timeout(1000)
            resp = resp_info.value
            req_auth = resp.request.headers.get("authorization", "")
            if req_auth.startswith("Bearer "):
                captured_token = req_auth.replace("Bearer ", "")
                print(f"🔑 Token capturado de account request: {captured_token[:40]}...")
        except Exception as e:
            print(f"No account request found: {e}")

    if not captured_token:
        print("\n⚠️ Could not capture token. Trying to manually trigger one...")
        # Try to execute JS to find stored token
        try:
            storage_info = target_page.evaluate("""() => {
                const result = {};
                try {
                    for (let key of Object.keys(localStorage)) {
                        if (key.toLowerCase().includes('token') || key.toLowerCase().includes('access') || key.toLowerCase().includes('auth')) {
                            result[key] = localStorage[key];
                        }
                    }
                } catch(e) {}
                return result;
            }""")
            if storage_info:
                print(f"LocalStorage matching: {storage_info}")
        except:
            pass

    # Try order with captured token if we have it
    if captured_token:
        print(f"\n=== Testing order with captured token ===")
        BASE = "https://demo.tradovateapi.com/v1"

        # Try with just bearer
        headers = {"Authorization": f"Bearer {captured_token}", "Content-Type": "application/json"}
        payload = {
            "accountSpec": "APEX5494170000001",
            "accountId": 45402487,
            "action": "Buy",
            "symbol": "MNQ",
            "orderQty": 1,
            "orderType": "Market",
        }

        resp = requests.post(f"{BASE}/order/placeorder", json=payload, headers=headers, timeout=10)
        print(f"Bearer only: {resp.status_code} -> {resp.json()}")

        # Try with cookies + bearer
        cookies = ctx.cookies()
        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        headers_with_cookies = {
            "Authorization": f"Bearer {captured_token}",
            "Content-Type": "application/json",
            "Cookie": cookie_str,
            "Origin": "https://trader.tradovate.com",
            "Referer": "https://trader.tradovate.com/",
        }

        resp2 = requests.post(f"{BASE}/order/placeorder", json=payload, headers=headers_with_cookies, timeout=10)
        print(f"Bearer+Cookie: {resp2.status_code} -> {resp2.json()}")

    print("\nDone!")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    browser.disconnect()
    pw.stop()
