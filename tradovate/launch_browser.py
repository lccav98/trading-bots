"""Launch Chromium via Playwright for Tradovate login."""
import json, time, sys, requests as _requests
from playwright.sync_api import sync_playwright

print("Lancando navegador stealth...", flush=True)

pw = sync_playwright().start()
browser = pw.chromium.launch_persistent_context(
    user_data_dir="data/browser_trader",
    headless=False,
    viewport={"width": 1400, "height": 900},
    locale="pt-BR",
    args=["--disable-blink-features=AutomationControlled",
          "--no-first-run", "--no-default-browser-check"],
)

page = browser.pages[0] if browser.pages else browser.new_page()

page.add_init_script("""
    Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
    window.chrome={runtime:{}};
""")

page.goto("https://trader.tradovate.com", wait_until="domcontentloaded", timeout=60000)
captured_token = None
captured_cookies = {}

def on_request(request):
    global captured_token
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and len(auth) > 60:
        captured_token = auth.replace("Bearer ", "")
        print(f"\n[Token capturado! {captured_token[:40]}...]", flush=True)

page.on("request", on_request)

print(f"URL: {page.url}", flush=True)
print("Aguardando 30 segundos para carregar/login...\n", flush=True)

# Wait 30s for page to load and for user to login
page.wait_for_timeout(30000)

# Capture cookies
all_cookies = browser.cookies()
captured_cookies = {c["name"]: c["value"] for c in all_cookies}
print(f"\nCookies: {len(captured_cookies)}", flush=True)

if not captured_token:
    print("Token nao capturado. Recarregando para forcar requests de auth...\n", flush=True)
    page.reload()
    page.wait_for_timeout(10000)
    if not captured_token:
        print("Ainda sem token. Tentando renew API...\n", flush=True)

payload = {
    "accountSpec": "APEX5494170000001",
    "accountId": 45402487,
    "action": "Buy",
    "symbol": "MNQ",
    "orderQty": 1,
    "orderType": "Market",
}

if captured_token:
    print(f"Token: {captured_token[:40]}...\n", flush=True)

    cookie_str = "; ".join(f"{k}={v}" for k, v in captured_cookies.items())

    combos = [
        ("Bearer", {"Authorization": f"Bearer {captured_token}", "Content-Type": "application/json"}),
        ("Bearer+Cookie+Origin", {
            "Authorization": f"Bearer {captured_token}",
            "Content-Type": "application/json",
            "Cookie": cookie_str,
            "Origin": "https://trader.tradovate.com",
            "Referer": "https://trader.tradovate.com/",
        }),
        ("Cookie+Origin", {
            "Content-Type": "application/json",
            "Cookie": cookie_str,
            "Origin": "https://trader.tradovate.com",
            "Referer": "https://trader.tradovate.com/",
        }),
    ]

    for name, headers in combos:
        try:
            resp = _requests.post(
                "https://demo.tradovateapi.com/v1/order/placeorder",
                json=payload, headers=headers, timeout=10
            )
            try: data = resp.json()
            except: data = resp.text[:200]
            ok = "orderId" in str(data)
            print(f"  {'OK!' if ok else 'FAIL'} {name}: {data}", flush=True)
            if ok:
                print("  >>> ENCONTRADO METODO QUE FUNCIONA! <<<", flush=True)
        except Exception as e:
            print(f"  FAIL {name}: {e}", flush=True)
else:
    cookie_str = "; ".join(f"{k}={v}" for k, v in captured_cookies.items())
    print("Tentando renew com cookies...", flush=True)
    try:
        resp = _requests.post(
            "https://demo.tradovateapi.com/v1/auth/renewaccesstoken",
            headers={"Content-Type": "application/json", "Cookie": cookie_str,
                     "Origin": "https://trader.tradovate.com", "Referer": "https://trader.tradovate.com/"},
            timeout=10
        )
        data = resp.json()
        if "accessToken" in data:
            print("Token renovado! Testando ordem...", flush=True)
            ct = data["accessToken"]
            h = {"Authorization": f"Bearer {ct}", "Content-Type": "application/json",
                 "Cookie": cookie_str, "Origin": "https://trader.tradovate.com",
                 "Referer": "https://trader.tradovate.com/"}
            resp2 = _requests.post("https://demo.tradovateapi.com/v1/order/placeorder",
                                   json=payload, headers=h, timeout=10)
            print(f"  Order: {resp2.json()}", flush=True)
        else:
            print(f"  Renew: {data}", flush=True)
    except Exception as e:
        print(f"  Error: {e}", flush=True)

print("\n\nFeche a janela do navegador quando terminar.", flush=True)
browser.close()
pw.stop()
