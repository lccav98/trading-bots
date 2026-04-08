"""
core/executor.py — Execução de ordens via Tradovate (browser fetch async)

Como a Tradovate bloqueia ordens via API externa (renewaccesstoken so
funciona para leitura de dados), todas as ordens sao enviadas via
page.evaluate(), executando o fetch() DENTRO do navegador autenticado.

Usa Playwright ASYNC para ser compativel com o asyncio do bot principal.
"""

import asyncio
import logging
from playwright.async_api import async_playwright
from config.settings import ENV, SYMBOL

logger = logging.getLogger(__name__)
BASE_URL = {
    "demo": "https://demo.tradovateapi.com/v1",
    "live": "https://live.tradovateapi.com/v1",
}[ENV]


class OrderExecutor:
    """Executor de ordens via navegador Playwright async."""

    def __init__(self, auth, risk_manager):
        self.auth = auth
        self.risk = risk_manager
        self._pw = None
        self._browser = None
        self._page = None
        self._logged_in = False
        self._lock = asyncio.Lock()

    async def _ensure_browser(self):
        """Abre navegador com auto-login."""
        if self._page is not None:
            try:
                await self._page.content()
                return True
            except Exception:
                self._page = None

        async with self._lock:
            if self._page is not None:
                return True

            logger.info("[Executor] Lancando Playwright + Chromium...")
            try:
                self._pw = await async_playwright().start()
                self._browser = await self._pw.chromium.launch_persistent_context(
                    user_data_dir="data/browser_executor",
                    headless=False,
                    viewport={"width": 1400, "height": 900},
                    locale="pt-BR",
                    args=["--disable-blink-features=AutomationControlled",
                          "--no-first-run", "--no-default-browser-check"],
                )
                self._page = self._browser.pages[0] if self._browser.pages else await self._browser.new_page()

                # Anti-detection
                await self._page.add_init_script("""
                    Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
                    window.chrome={runtime:{}};
                """)

                logger.info("[Executor] Navegando para tradovate...")
                await self._page.goto(
                    "https://trader.tradovate.com",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                await asyncio.sleep(5)

                await self._auto_fill_login()
                self._logged_in = True
                logger.info("[Executor] Aguardando login (20s)...")
                await asyncio.sleep(20)
                logger.info(f"[Executor] URL atual: {self._page.url}")
                return True
            except Exception as e:
                logger.error(f"[Executor] Falha ao iniciar navegador: {e}")
                return False

    async def _auto_fill_login(self):
        """Preenche formulario de login e clica Login."""
        from config.settings import TRADOVATE_USERNAME, TRADOVATE_PASSWORD

        for sel in ['input[placeholder*="Username"]', 'input[placeholder*="Email"]',
                     'input[name="username"]', 'input[name="login"]',
                     'input[type="text"]']:
            try:
                inp = await self._page.wait_for_selector(sel, timeout=2000)
                if inp and await inp.is_visible():
                    await inp.fill(TRADOVATE_USERNAME)
                    logger.info("[Executor] Username preenchido")
                    break
            except Exception:
                pass

        await asyncio.sleep(0.5)

        try:
            pwd = await self._page.wait_for_selector('input[type="password"]', timeout=3000)
            if pwd and await pwd.is_visible():
                await pwd.fill(TRADOVATE_PASSWORD)
                logger.info("[Executor] Senha preenchida")
        except Exception:
            pass

        await asyncio.sleep(1)

        for sel in ['button.Login', 'button:has-text("Login")',
                    '#login-button', 'button[aria-label="Login"]']:
            try:
                btn = await self._page.wait_for_selector(sel, timeout=2000)
                if btn and await btn.is_visible():
                    await btn.click()
                    logger.info("[Executor] Botao Login clicado")
                    return
            except Exception:
                pass

        pwd = await self._page.query_selector('input[type="password"]')
        if pwd:
            await pwd.press("Enter")
            logger.info("[Executor] Enter pressionado")

    async def place_bracket_order(self, action: str, entry_price: float,
                                  atr: float = 0, strategy_score: int = 1) -> dict:
        """Place bracket order — via JS fetch dentro do navegador."""

        # Valida risco
        can, reason = self.risk.can_trade()
        if not can:
            logger.warning(f"⛔ Ordem bloqueada: {reason}")
            return {"success": False, "reason": reason}

        # Renova token do auth e abre browser se necessario
        self.auth.renew_if_needed()
        if not self._page:
            if not await self._ensure_browser():
                return {"success": False, "reason": "Browser nao inicializado"}

        # Calcula stops
        stops = self.risk.calculate_stops(action, entry_price, atr, strategy_score)
        qty = stops.get("position_size", 1)

        logger.info(
            f"📤 Enviando ordem {action} | "
            f"Entry: {entry_price} | "
            f"SL: {stops['stop_loss']} ({stops['sl_ticks']} ticks) | "
            f"TP: {stops['take_profit']} ({stops['tp_ticks']} ticks) | "
            f"Contracts: {qty} | "
            f"Risco: ${stops['risk_usd']} | "
            f"R/R: {stops['rr_ratio']}"
        )

        import json as _json_mod
        oso_json = _json_mod.dumps({
            "accountSpec": "APEX5494170000001",
            "accountId": 45402487,
            "action": action.capitalize(),
            "symbol": SYMBOL,
            "orderQty": qty,
            "orderType": "Market",
            "isAutomated": True,
            "bracket1": {
                "action": "Sell" if action == "BUY" else "Buy",
                "orderType": "Stop",
                "stopPrice": stops["stop_loss"],
                "orderQty": qty,
            },
            "bracket2": {
                "action": "Sell" if action == "BUY" else "Buy",
                "orderType": "Limit",
                "price": stops["take_profit"],
                "orderQty": qty,
            },
        })

        result = await self._execute_browser_order(oso_json, "placeOSO")

        if result["success"]:
            self.risk.register_open(action, entry_price, stops)
            logger.info(f"✅ Ordem executada! {result.get('data', {})}")
        else:
            logger.error(f"❌ Falha ao enviar ordem: {result}")

        return result

    async def _execute_browser_order(self, payload_json: str, endpoint: str) -> dict:
        """Envia ordem via page.evaluate() — request SAI do navegador."""
        api_base = BASE_URL
        try:
            js_code = (
                f'(async () => {{'
                f'  try {{'
                f'    const resp = await fetch("{api_base}/order/{endpoint}", {{'
                f'      method: "POST",'
                f'      headers: {{ "Content-Type": "application/json" }},'
                f'      body: {payload_json},'
                f'      credentials: "include"'
                f'    }});'
                f'    const text = await resp.text();'
                f'    try {{ return JSON.parse(text); }} '
                f'    catch(e) {{ return {{ raw: text, status: resp.status }}; }}'
                f'  }} catch(e) {{'
                f'    return {{ error: e.message }};'
                f'  }}'
                f'}})();'
            )
            result = await self._page.evaluate(js_code)
            logger.info(f"[Executor] JS result: {result}")

            if "orderId" in str(result):
                return {"success": True, "data": result, "stops": {"position_size": None}}

            error_text = result.get("failureText", "") or result.get("error", "") or ""
            if error_text:
                return {"success": False, "reason": error_text}
            return {"success": False, "reason": str(result)}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    async def flatten_position(self) -> dict:
        """Close open position via browser fetch."""
        logger.info("[Executor] Fechando posicao via browser...")
        try:
            import json as _json_mod
            result = await self._execute_browser_order(
                _json_mod.dumps({"accountId": 45402487, "symbol": SYMBOL}),
                "liquidateposition"
            )
            if result["success"]:
                self.risk.register_close(0)
            return result
        except Exception as e:
            return {"success": False, "reason": str(e)}

    async def close(self):
        """Shutdown browser."""
        try:
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass
        self._page = None
        self._browser = None
        self._pw = None
        self._logged_in = False

    def get_positions(self) -> list:
        """Lista posicoes abertas via API (leitura)."""
        self.auth.renew_if_needed()
        try:
            import requests as _requests
            resp = _requests.get(
                f"{BASE_URL}/position/list",
                headers=self.auth.headers(),
                timeout=10,
            )
            return resp.json() if resp.status_code == 200 else []
        except Exception:
            return []

    def get_account_status(self) -> dict:
        """Retorna status da conta via API (leitura)."""
        self.auth.renew_if_needed()
        try:
            import requests as _requests
            resp = _requests.get(
                f"{BASE_URL}/account/list",
                headers=self.auth.headers(),
                timeout=10,
            )
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return {}
        except Exception:
            return {}
