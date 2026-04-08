"""Intercept token from running browser via CDP and test order."""
import requests
import json
import time

# Use requests to talk to CDP directly (no playwright)
CDP = "http://localhost:9222"

# Step 1: Get target pages
print("=== CDP: Getting pages ===")
resp = requests.get(f"{CDP}/json")
pages = resp.json()
for p in pages:
    print(f"  URL: {p.get('url', 'N/A')[:80]}...")
    if "tradovate" in p.get('url', '').lower():
        print(f"\n*** Found Tradovate page: {p.get('id')[:40]}")
        target_id = p['id']
        break
else:
    print("No tradovate page found. You may need to open it first.")
    # Find any page
    target_id = pages[0]['id']

# Step 2: Execute JS to find stored credentials
print(f"\n=== Executing JS to find tokens ===")
js_find_token = """
(() => {
  const results = {};
  // Check localStorage
  for (let key of Object.keys(localStorage)) {
    try {
      const val = localStorage[key];
      if (key.toLowerCase().includes('token') || key.toLowerCase().includes('auth') || val.length > 200) {
        results['ls_' + key] = val.substring(0, 100);
      }
    } catch(e) {}
  }
  // Check cookies
  results['document_cookies'] = document.cookie;
  return results;
})()
"""

# We need WebSocket to execute JS on the page
import websocket
import threading

# Get websocket URL
ws_resp = requests.get(f"{CDP}/json/version")
ws_url = ws_resp.json().get('webSocketDebuggerUrl')
print(f"\nWebSocket URL available")

# Connect to page
ws_page = requests.get(f"{CDP}/json/{target_id}")
page_ws_url = ws_page.json().get('webSocketDebuggerUrl')
print(f"Page WebSocket URL: {page_ws_url[:60]}...")

# Execute Runtime.evaluate
ws = websocket.create_connection(page_ws_url, timeout=30)
ws.settimeout(10)

print("\n=== Capturing network requests with auth ===")

# Enable network tracking
ws.send(json.dumps({
    "id": 1,
    "method": "Network.enable",
    "params": {}
}))
while True:
    msg = json.loads(ws.recv())
    if msg.get('id') == 1:
        break

# Now capture auth headers from any future request
found_token = None

def send_and_forget(ws, method, params={}):
    ws.send(json.dumps({"method": method, "params": params}))

print("Reloading page to trigger auth requests...")

# First reload the page
ws.send(json.dumps({
    "id": 10,
    "method": "Page.reload",
    "params": {}
}))

# Listen for network responses
for i in range(200):
    try:
        msg = json.loads(ws.recv())
        if msg.get('method') == 'Network.responseReceived':
            req_url = msg.get('params', {}).get('response', {}).get('url', '')
            req_headers = msg.get('params', {}).get('response', {}).get('headers', {})
            auth = req_headers.get('authorization', '')
            if auth.startswith('Bearer '):
                found_token = auth.replace('Bearer ', '')
                print(f"\n🔑 TOKEN ENCONTRADO! ({found_token[:40]}...)")

                # Test order with this token immediately
                print("\n=== Testando ordem com token real ===")
                BASE = "https://demo.tradovateapi.com/v1"

                # Test 1: Just bearer
                headers1 = {
                    "Authorization": f"Bearer {found_token}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "accountSpec": "APEX5494170000001",
                    "accountId": 45402487,
                    "action": "Buy",
                    "symbol": "MNQ",
                    "orderQty": 1,
                    "orderType": "Market",
                }
                r = requests.post(f"{BASE}/order/placeorder", json=payload, headers=headers1, timeout=10)
                print(f"Teste 1 (apenas bearer): Status={r.status_code}")
                try: print(f"  Response: {r.json()}")
                except: print(f"  Raw: {r.text[:200]}")

                # Test 2: Include origin/referer
                headers2 = {
                    "Authorization": f"Bearer {found_token}",
                    "Content-Type": "application/json",
                    "Origin": "https://trader.tradovate.com",
                    "Referer": "https://trader.tradovate.com/",
                }
                r2 = requests.post(f"{BASE}/order/placeorder", json=payload, headers=headers2, timeout=10)
                print(f"Teste 2 (com origin/referer): Status={r2.status_code}")
                try: print(f"  Response: {r2.json()}")
                except: print(f"  Raw: {r2.text[:200]}")

                # Test 3: try OSO order
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
                r3 = requests.post(f"{BASE}/order/placeOSO", json=oso_payload, headers=headers1, timeout=10)
                print(f"Teste 3 (OSO com bearer): Status={r3.status_code}")
                try: print(f"  Response: {r3.json()}")
                except: print(f"  Raw: {r3.text[:200]}")

                break
    except Exception as e:
        print(f"Recv error: {e}")
        break
    except json.JSONDecodeError:
        continue

if not found_token:
    print("\n⚠️ Token não capturado após reload.")
    print("Tente fazer login manualmente no navegador Tradovate primeiro.")

    # At least try to get request headers from any request
    # Also try Runtime.execute to get cookies
    try:
        ws.send(json.dumps({
            "id": 20,
            "method": "Network.getAllCookies",
        }))
        # Read response
        for i in range(20):
            try:
                msg = json.loads(ws.recv())
                if msg.get('id') == 20:
                    cookies = msg.get('result', {}).get('cookies', [])
                    print(f"\n=== Cookies ({len(cookies)}) ===")
                    for c in cookies[:5]:
                        print(f"  {c['name']}: {c['value'][:50]}...")
                    if len(cookies) > 5:
                        print(f"  ... +{len(cookies)-5} more")

                    # Check for auth-like cookies
                    for c in cookies:
                        if len(c['value']) > 100:
                            print(f"\n🔑 Possível token no cookie '{c['name']}': {c['value'][:60]}...")
                    break
            except:
                pass
    except Exception as e:
        print(f"Erro ao buscar cookies: {e}")

ws.close()
print("\nDone!")
