"""Connect to Chrome CDP, intercept token, test orders."""
import requests, json, time
from playwright.sync_api import sync_playwright

print("Conectando ao Chrome via CDP on port 9229...", flush=True)

pw = sync_playwright().start()

try:
    browser = pw.chromium.connect_over_cdp("http://localhost:9229")
    print("Conectado!", flush=True)

    ctx = browser.contexts[0]
    pages = ctx.pages

    tradovate_page = None
    for p in pages:
        url = p.url
        print(f"  Tab: {url[:100]}")
        if "tradovate" in url.lower():
            tradovate_page = p

    if not tradovate_page:
        print("  Abrindo tradovate...", flush=True)
        tradovate_page = ctx.new_page()
        tradovate_page.goto("https://trader.tradovate.com", wait_until="domcontentloaded", timeout=30000)

    print(f"\n  URL atual: {tradovate_page.url}", flush=True)

    # Capture token from intercepted requests
    captured_token = None

    def on_response(response):
        global captured_token
        if captured_token:
            return
        auth = response.request.headers.get("authorization", "")
        if auth.startswith("Bearer ") and len(auth) > 60:
            captured_token = auth.replace("Bearer ", "")
            print(f"\n  [TOKEN via request!]", flush=True)

    def on_request(request):
        global captured_token
        if captured_token:
            return
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer ") and len(auth) > 60:
            captured_token = auth.replace("Bearer ", "")
            print(f"\n  [TOKEN via request headers!]", flush=True)

    tradovate_page.on("response", on_response)
    tradovate_page.on("request", on_request)

    # Reload to trigger authenticated requests
    print("\n  Recarregando pagina para capturar token...", flush=True)
    tradovate_page.reload()
    tradovate_page.wait_for_timeout(15000)

    if captured_token:
        print(f"\n  TOKEN CAPTURADO: {captured_token[:50]}...", flush=True)

        # Now test order via API with this token
        import requests as _requests
        BASE = "https://demo.tradovateapi.com/v1"

        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in ctx.cookies())

        combos = [
            ("Bearer only", {"Authorization": f"Bearer {captured_token}", "Content-Type": "application/json"}),
            ("Bearer + cookies + origin", {
                "Authorization": f"Bearer {captured_token}",
                "Content-Type": "application/json",
                "Cookie": cookie_str,
                "Origin": "https://trader.tradovate.com",
                "Referer": "https://trader.tradovate.com/",
            }),
        ]

        payload = {
            "accountSpec": "APEX5494170000001",
            "accountId": 45402487,
            "action": "Buy", "symbol": "MNQ",
            "orderQty": 1, "orderType": "Market",
        }

        for name, headers in combos:
            try:
                resp = _requests.post(f"{BASE}/order/placeorder", json=payload, headers=headers, timeout=10)
                try: data = resp.json()
                except: data = resp.text[:200]
                ok = "orderId" in str(data)
                print(f"  {'OK!' if ok else 'FAIL'} {name}: {data}", flush=True)
            except Exception as e:
                print(f"  FAIL {name}: {e}", flush=True)

    else:
        print("\n  Token nao capturado via interceptacao.", flush=True)
        print("  Testando ordem via JS fetch() dentro do navegador...", flush=True)

        js_order = """
        (async () => {
            try {
                const resp = await fetch(
                    "https://demo.tradovateapi.com/v1/order/placeorder",
                    {
                        method: "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({
                            accountSpec: "APEX5494170000001",
                            accountId: 45402487,
                            action: "Buy",
                            symbol: "MNQ",
                            orderQty: 1,
                            orderType: "Market"
                        })
                    }
                );
                return await resp.json();
            } catch(e) {
                return {error: e.message};
            }
        })();
        """

        result = tradovate_page.evaluate(js_order)
        print(f"\n  Order JS result: {result}", flush=True)

        if captured_token:
            # Also try via renew API
            import requests as _requests
            resp = _requests.post(
                "https://demo.tradovateapi.com/v1/auth/renewaccesstoken",
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            print(f"  Renew API: {resp.status_code} -> {resp.json()}", flush=True)

    browser.disconnect()

except Exception as e:
    print(f"Error: {e}", flush=True)

pw.stop()
print("\nDone!", flush=True)
