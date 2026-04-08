"""
API Reversa - Captura automatica de requests Tradovate Web
Intercepta todos os HTTP requests enquanto voce loga manualmente.
"""

import json
from playwright.sync_api import sync_playwright

KEYWORDS = ["auth", "login", "token", "access", "session", "password",
            "order", "trade", "account", "user", "md/", "chart",
            "position", "marketdata", "balance", "tradovateapi"]

captured = []
auth_details = []

SKIP = [
    "google.com", "facebook.com", "analytics.", "bugsnag",
    "qualtrics", "hubspot", "heapanalytics",
    "contentsquare", "t.co/", "play.google",
    "google-analytics", "connect.facebook",
    "appleid.cdn-apple.com", "doubleclick",
    "googletagmanager", "fontawesome", "gstatic",
    "fonts.gstatic", "fonts.googleapis",
    "blob:", "chrome-extension",
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.on("request", lambda req: captured.append({
        "url": req.url, "method": req.method,
        "headers": dict(req.headers), "post_data": req.post_data,
    }))

    print("=" * 60)
    print(" CAPTURA DE API TRADOVATE")
    print("=" * 60)
    print("Abrindo trader.tradovate.com...")
    print("Faca login manualmente no navegador que abriu.\n")
    print("O script verifica a cada 10s e para\ntao logo capture requests da API Tradovate.")
    print("=" * 60)

    page.goto("https://trader.tradovate.com", wait_until="networkidle", timeout=30000)
    print("Pagina carregada. Aguardando seu login...\n")

    for i in range(18):  # 3 minutos max
        page.wait_for_timeout(10000)

        relevant_count = 0
        for r in captured:
            url = r["url"].lower()
            if any(kw in url for kw in KEYWORDS) and not any(s in url for s in SKIP):
                relevant_count += 1

        elapsed = (i + 1) * 10
        print(f"  [{elapsed}s] API requests: {relevant_count} | Total: {len(captured)}")

        if relevant_count >= 5:
            print(">>> Suficiente! Salvando resultados...")
            break
    else:
        print(">>> Tempo esgotado. Salvando o que foi capturado...")

    relevant = []
    for r in captured:
        url = r["url"].lower()
        if any(kw in url for kw in KEYWORDS) and not any(s in url for s in SKIP):
            relevant.append(r)

    with open("captured_all.json", "w") as f:
        json.dump(captured, f, indent=2, default=str)
    with open("captured_relevant.json", "w") as f:
        json.dump(relevant, f, indent=2, default=str)

    print(f"\nTotal: {len(captured)} | Relevantes: {len(relevant)}")

    domains = {}
    for req in relevant:
        base = req["url"].split("?")[0]
        domains[base] = domains.get(base, 0) + 1

    print("\nEndpoints Tradovate:")
    for url, count in sorted(domains.items(), key=lambda x: -x[1]):
        print(f"  [{count}x] {url}")

    print("\n" + "=" * 60)
    print(" DETALHES DE AUTH / ORDENS / ACCOUNT")
    print("=" * 60)
    for req in relevant:
        url = req["url"].lower()
        if any(kw in url for kw in ["auth", "order", "trade", "account",
                                     "position", "balance", "token", "access",
                                     "login", "session"]):
            print(f"\nURL: {req['url']}")
            print(f"METHOD: {req['method']}")
            if req.get("post_data"):
                try:
                    pd = json.loads(req["post_data"])
                    for k in ["password", "sec", "secret", "key", "token"]:
                        if k in pd:
                            pd[k] = "***"
                    print(f"POST DATA: {json.dumps(pd, indent=2)}")
                except:
                    print(f"POST DATA: {str(req['post_data'])[:500]}")
            hdrs = dict(req.get("headers", {}))
            imp = {}
            for k, v in hdrs.items():
                kl = k.lower()
                if kl in ("authorization", "content-type", "accept", "referer",
                           "origin", "sec-fetch", "cookie", "x-auth", "x-token"):
                    imp[k] = v[:120] + "..." if len(str(v)) > 120 else v
            if imp:
                print(f"HEADERS: {json.dumps(imp, indent=4)}")

    try:
        browser.close()
    except:
        pass
    print("\n>>> Feito. Resultados em captured_relevant.json")
