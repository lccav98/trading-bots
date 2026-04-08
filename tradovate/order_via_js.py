"""
Place order via JavaScript EXECUTE inside the Tradovate browser page.
This uses the browser's own fetch() with its native auth headers.
"""
import json, time
from playwright.sync_api import sync_playwright

pw = sync_playwright().start()

# First try: connect to existing CDP on port 9222 (TradingView Desktop)
# This won't work for tradovate

# Second: launch our own browser
print("Lancando navegador...", flush=True)
browser = pw.chromium.launch_persistent_context(
    user_data_dir="data/browser_js_order",
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
print(f"URL: {page.url}", flush=True)

# Wait for login
print("Aguardando login... (esperando 60 segundos)", flush=True)
for i in range(12):
    page.wait_for_timeout(5000)
    url = page.url
    print(f"  [{(i+1)*5}s] URL: {url[:60]}", flush=True)
    if "trading" in url.lower() or "chart" in url.lower() or "dashboard" in url.lower():
        print("  Login detectado!", flush=True)
        break

# Wait a bit more for API requests to fire
page.wait_for_timeout(3000)

# NOW execute order via JS fetch
js_code = """
(async () => {
    try {
        const payload = {
            accountSpec: "APEX5494170000001",
            accountId: 45402487,
            action: "Buy",
            symbol: "MNQ",
            orderQty: 1,
            orderType: "Market"
        };

        const resp = await fetch(
            "https://demo.tradovateapi.com/v1/order/placeorder",
            {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(payload)
            }
        );

        const data = await resp.json();
        return JSON.stringify({status: resp.status, data: data});
    } catch(e) {
        return JSON.stringify({error: e.message});
    }
})();
"""

print("\nExecutando order via JS fetch()...", flush=True)
result = page.evaluate(js_code)
print(f"Resultado: {result}", flush=True)

# Also try via browser's own request (CORS bypass)
print("\nTambem tentando via Page.route interception...", flush=True)

# Wait and print final state
print("\nEstado final:", flush=True)
print(f"URL: {page.url}", flush=True)
print("Feche o navegador quando terminar.", flush=True)

browser.close()
pw.stop()
