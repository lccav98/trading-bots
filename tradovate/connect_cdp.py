"""Connect to Chrome CDP and test order via JS fetch."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

try:
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()

    # Try multiple debug ports
    ports = [9229, 9222, 9223, 9224, 9225, 9226, 9227, 9228, 9230]

    for port in ports:
        try:
            browser = pw.chromium.connect_over_cdp(f"http://localhost:{port}")
            print(f"\nConnected on port {port}!", flush=True)

            ctx = browser.contexts[0]
            pages = ctx.pages

            # Find tradovate page
            tradovate_page = None
            for p in pages:
                url = p.url
                print(f"  Tab: {url[:100]}")
                if "tradovate" in url.lower():
                    tradovate_page = p

            if not tradovate_page:
                print("\n  Opening tradovate...", flush=True)
                tradovate_page = ctx.new_page()
                tradovate_page.goto("https://trader.tradovate.com", wait_until="domcontentloaded", timeout=30000)

            if tradovate_page:
                print(f"\n  Current URL: {tradovate_page.url}", flush=True)

                # Step 1: Intercept token from existing requests
                captured_token = None

                def on_request(request):
                    global captured_token
                    if captured_token:
                        return
                    auth = request.headers.get("authorization", "")
                    if auth.startswith("Bearer ") and len(auth) > 60:
                        captured_token = auth.replace("Bearer ", "")
                        print(f"\n  [TOKEN CAPTURADO via request! {captured_token[:50]}...]", flush=True)

                tradovate_page.on("request", on_request)

                # Reload page to capture
                print("\n  Recarregando para capturar token...", flush=True)
                tradovate_page.reload()
                tradovate_page.wait_for_timeout(10000)

                if captured_token:
                    print(f"\n  Token: {captured_token[:40]}...", flush=True)

                    # Test order via JS fetch
                    js_code = f"""
                    (async () => {{
                        try {{
                            const resp = await fetch(
                                "https://demo.tradovateapi.com/v1/order/placeorder",
                                {{
                                    method: "POST",
                                    headers: {{"Content-Type": "application/json"}},
                                    body: JSON.stringify({{
                                        accountSpec: "APEX5494170000001",
                                        accountId: 45402487,
                                        action: "Buy",
                                        symbol: "MNQ",
                                        orderQty: 1,
                                        orderType: "Market"
                                    }})
                                }}
                            );
                            return await resp.json();
                        }} catch(e) {{
                            return {{error: e.message}};
                        }}
                    }})();
                    """

                    print("\n  Executando order via JS fetch() dentro do navegador...", flush=True)
                    result = tradovate_page.evaluate(js_code)
                    print(f"  Resultado: {result}", flush=True)

                else:
                    print("\n  Token NAO capturado via reload.", flush=True)
                    # Try execute JS fetch directly
                    js_code = """
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
                    print("\n  Tentando via JS fetch() direto...", flush=True)
                    result = tradovate_page.evaluate(js_code)
                    print(f"  Resultado: {result}", flush=True)

            browser.disconnect()
            break

        except Exception as e:
            if "refused" in str(e).lower() or "closed" in str(e).lower():
                pass
            else:
                print(f"Port {port}: {e}", flush=True)
    else:
        print("Could not connect to any Chrome CDP port.", flush=True)

except Exception as e:
    print(f"Error: {e}", flush=True)

print("\nDone.", flush=True)
