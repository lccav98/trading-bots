"""
Step 1: Launch stealth browser and wait for user to place a test order manually
Step 2: Intercept all the requests and capture auth info
Step 3: Replicate the same request programmatically
"""
import requests, json, time, _thread
from playwright.sync_api import sync_playwright

TRADOVATE_URL = "https://trader.tradovate.com"
ORDER_INTERCEPTED = []

print("=" * 60)
print("INTERCEPTOR DE ORDENS TRADOVATE")
print("=" * 60)
print()
print("O navegador vai abrir. Faca o seguinte:")
print("  1. Espere a pagina carregar")
print("  2. Se necessario, faca login")
print("  3. Coloque uma ordem MANUAL de compra/venda de 1 contrato MNQ")
print("     (pode usar Market Order)")
print("  4. O script vai capturar os dados da requisicao")
print()

captured_token = None
captured_cookies = {}
request_log = []

pw = sync_playwright().start()
browser = pw.chromium.launch_persistent_context(
    user_data_dir="data/browser_intercept",
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

def on_request(request):
    global captured_token, captured_cookies
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and len(auth) > 60:
        captured_token = auth.replace("Bearer ", "")
        request_log.append({
            "url": request.url,
            "method": request.method,
            "headers": dict(request.headers),
            "post_data": request.post_data,
        })

page.on("request", on_request)

page.goto(TRADOVATE_URL, wait_until="domcontentloaded", timeout=60000)
page.wait_for_timeout(3000)
print(f"Pagina carregada: {page.url}")
print("Aguardando login e ordem manual...")

# Wait for user input
input("\n>>> Coloque a ordem manual no navegador e pressione ENTER aqui >>>")

# Capture cookies
all_cookies = browser.cookies()
captured_cookies = {c["name"]: c["value"] for c in all_cookies}

print(f"\n=== Token: {'Capturado!' if captured_token else 'NAO capturado'} ===")
if captured_token:
    print(f"Token (inicio): {captured_token[:40]}...")

print(f"\n=== Cookies: {len(captured_cookies)} ===")
for name, val in captured_cookies.items():
    display_len = min(40, len(val))
    print(f"  {name}: {val[:display_len]}...")

print(f"\n=== Requests interceptados: {len(request_log)} ===")
tradovate_reqs = [r for r in request_log if "tradovateapi" in r["url"]]
print(f"  Requests para tradovateapi: {len(tradovate_reqs)}")

# Show intercepted order-related requests
for i, r in enumerate(tradovate_reqs):
    if "order" in r["url"].lower():
        print(f"\n  --- REQUEST #{i} ---")
        print(f"  URL: {r['url']}")
        print(f"  Method: {r['method']}")
        print(f"  Headers: {json.dumps(r['headers'], indent=2)}")
        if r.get('post_data'):
            print(f"  POST Data: {r['post_data'][:500]}")

# Now try to replicate
if captured_token and tradovate_reqs:
    print(f"\n{'='*50}")
    print("TESTANDO ORDENS PROGRAMATICAMENTE")
    print(f"{'='*50}")

    cookie_str = "; ".join(f"{k}={v}" for k, v in captured_cookies.items())

    # Try various header combos
    auth_combos = [
        ("Bearer token only", {"Authorization": f"Bearer {captured_token}", "Content-Type": "application/json"}),
        ("Bearer + cookies", {"Authorization": f"Bearer {captured_token}", "Content-Type": "application/json", "Cookie": cookie_str}),
        ("Bearer + cookies + origin/referer", {"Authorization": f"Bearer {captured_token}", "Content-Type": "application/json", "Cookie": cookie_str, "Origin": "https://trader.tradovate.com", "Referer": "https://trader.tradovate.com/"}),
        ("Cookies only", {"Content-Type": "application/json", "Cookie": cookie_str}),
        ("Cookies + origin/referer", {"Content-Type": "application/json", "Cookie": cookie_str, "Origin": "https://trader.tradovate.com", "Referer": "https://trader.tradovate.com/"}),
    ]

    for name, headers in auth_combos:
        payload = {
            "accountSpec": "APEX5494170000001",
            "accountId": 45402487,
            "action": "Buy",
            "symbol": "MNQ",
            "orderQty": 1,
            "orderType": "Market",
        }
        try:
            resp = requests.post("https://demo.tradovateapi.com/v1/order/placeorder",
                                 json=payload, headers=headers, timeout=10)
            try:
                data = resp.json()
            except:
                data = resp.text[:200]
            print(f"  {name}: {resp.status_code} -> {data}")
        except Exception as e:
            print(f"  {name}: ERRO - {e}")

print("\n\nDone. Feche o navegador.")
browser.close()
pw.stop()
