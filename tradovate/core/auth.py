"""
core/auth.py  Autenticacao Multi-Estrategia (async)

Ordem:
  1. API direta (com appId extraido do JS oficial)
  2. Chrome real via CDP (usuario faz login manual)
  3. Playwright Chromium + stealth (auto-fill correto)
"""

import concurrent.futures
import time
import json
import logging
import os
import requests
from pathlib import Path
from config.settings import (
    TRADOVATE_USERNAME, TRADOVATE_PASSWORD,
    TRADOVATE_API_URL, ENV,
    TOKEN_FILE
)

logger = logging.getLogger(__name__)
BASE_URL = TRADOVATE_API_URL[ENV]
TOKEN_PATH = Path(TOKEN_FILE)

APP_ID      = "80e6d5d7-487c-45c0-9c8e-49c28fe81c29"
APP_VERSION = "3.260403.0"

APP_IDS = [
    ("80e6d5d7-487c-45c0-9c8e-49c28fe81c29", APP_VERSION),
    ("tradovate_trader(web)", APP_VERSION),
]


def _find_chrome():
    for p in [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]:
        if Path(p).exists():
            return p
    return None


def _wait_cdp(port=9222, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            r = requests.get(f"http://localhost:{port}/json/version", timeout=2)
            if r.status_code == 200:
                return r.json().get("webSocketDebuggerUrl")
        except Exception:
            pass
        time.sleep(0.5)
    return None


def _extract_bearer_token(response):
    """Extrai bearer token de response HTTP — shared entre CDP e stealth."""
    try:
        if "accesstokenrequest" in response.url:
            data = response.json()
            if "accessToken" in data:
                return data["accessToken"]
    except Exception:
        pass
    auth_header = response.headers.get("authorization", "")
    if auth_header.startswith("Bearer ") and len(auth_header) > 60:
        return auth_header.replace("Bearer ", "")
    return None


class TradovateAuth:
    def __init__(self, browser_port=9222):
        self.access_token = None
        self.token_expiry  = 0
        self.account_id    = None
        self.account_spec  = None
        self._browser_port = browser_port

    # ───────────────────── Token management ─────────────────────

    def _load_token(self) -> bool:
        if TOKEN_PATH.exists():
            try:
                data = json.loads(TOKEN_PATH.read_text())
                self.access_token = data["token"]
                self.token_expiry = data["expiry"]
                if time.time() < self.token_expiry:
                    logger.info("Token valido carregado de sessao anterior")
                    self._post_auth_setup()
                    return True
                TOKEN_PATH.unlink(missing_ok=True)
            except Exception:
                TOKEN_PATH.unlink(missing_ok=True)
        return False

    def _save_token(self):
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(json.dumps({"token": self.access_token, "expiry": self.token_expiry}))
        logger.info("Token salvo")

    def _commit_token(self, token, source=""):
        """Centraliza setup pos-auth — evita duplicacao em 5 lugares."""
        self.access_token = token
        self.token_expiry = time.time() + 3540
        if source:
            logger.info(f"{source}: SUCESSO")
        self._post_auth_setup()
        self._save_token()
        return True

    def _post_auth_setup(self):
        try:
            self._load_account()
        except Exception as e:
            logger.debug(f"Setup conta (non-fatal): {e}")

    # ───────────────────── Main auth entry ─────────────────────

    async def authenticate(self) -> bool:
        if self._load_token():
            return True
        if self._try_api_auth():
            return True
        # Pula Chrome CDP (trava com sessoes existentes)
        logger.info("Pulando Chrome CDP, usando Chromium stealth...")
        if self._run_in_thread(self._try_chromium_stealth):
            return True
        logger.error("Todas as estrategias de auth falharam.")
        return False

    def _run_in_thread(self, method) -> bool:
        """Executa metodo sincrono em thread com timeout."""
        with concurrent.futures.ThreadPoolExecutor() as ex:
            fut = ex.submit(method)
            try:
                return fut.result(timeout=240)
            except Exception:
                return False

    # ───────────────────── Strategy 1: API ─────────────────────

    def _try_api_auth(self) -> bool:
        logger.info("[1/3] Tentando auth via API direta...")
        for app_id, app_ver in APP_IDS:
            try:
                logger.info(f"  appId='{app_id}'")
                resp = requests.post(
                    f"{BASE_URL}/auth/accesstokenrequest",
                    json={"name": TRADOVATE_USERNAME, "password": TRADOVATE_PASSWORD,
                          "appId": app_id, "appVersion": app_ver},
                    timeout=15
                )
                data = resp.json()
                if "accessToken" in data:
                    self.access_token = data["accessToken"]
                    self.token_expiry = time.time() + 3540
                    logger.info("API direta: SUCESSO")
                    self._post_auth_setup()
                    return True
                logger.info(f"  falhou: {data.get('errorText', data)}")
            except Exception as e:
                logger.info(f"  falhou: {e}")
        logger.warning("API direta: todos os appIds falharam")
        return False

    # ───────────────────── Shared: wait for login token ─────────────────────

    def _wait_for_login_token(self, page, max_steps=18):
        """Shared loop que aguarda token apos login — evita duplicacao CDP/stealth."""
        captured_token = None
        for i in range(max_steps):
            page.wait_for_timeout(10000)
            if captured_token:
                break
            if "trading" in page.url or "dashboard" in page.url:
                try:
                    with page.expect_response("**/account/list", timeout=10000) as ri:
                        page.reload()
                    auth_header = ri.value.request.headers.get("authorization", "")
                    if auth_header.startswith("Bearer ") and len(auth_header) > 60:
                        captured_token = auth_header.replace("Bearer ", "")
                        break
                except Exception:
                    pass
            logger.info(f"  Aguardando... [{(i+1)*10}s]")
        return captured_token

    # ───────────────────── Strategy 2: Chrome CDP ─────────────────────

    def _try_chrome_cdp(self) -> bool:
        logger.info("[2/3] Chrome real via CDP...")
        chrome = _find_chrome()
        if not chrome:
            logger.warning("Chrome nao encontrado, pulando")
            return False

        from playwright.sync_api import sync_playwright
        import subprocess

        with sync_playwright() as p:
            # So kill Chrome se o CDP port nao responder
            try:
                if not _wait_cdp(port=self._browser_port, timeout=3):
                    self._kill_my_chrome()
                    time.sleep(1)
                    self._launch_chrome(chrome)
            except Exception:
                self._kill_my_chrome()
                time.sleep(1)
                self._launch_chrome(chrome)

            if not _wait_cdp(port=self._browser_port, timeout=12):
                logger.error("Chrome nao abriu CDP")
                return False

            try:
                browser = p.chromium.connect_over_cdp(f"http://localhost:{self._browser_port}")
            except Exception as e:
                logger.error(f"CDP falhou: {e}")
                return False

            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.on("response", lambda r: self._on_browser_response(r))
            page.wait_for_timeout(5000)

            self._auto_fill(page)
            logger.info("Faca login no Chrome se necessario. Aguardando...")

            captured_token = self._wait_for_login_token(page, max_steps=18)
            if captured_token:
                self._commit_token(captured_token, "Chrome CDP")

            browser.disconnect()
            return captured_token is not None

    # ───────────────────── Strategy 3: Chromium stealth ─────────────────────

    def _try_chromium_stealth(self) -> bool:
        logger.info("[3/3] Chromium com stealth...")
        from playwright.sync_api import sync_playwright

        browser_dir = Path("data/browser_profile")
        browser_dir.mkdir(parents=True, exist_ok=True)
        (browser_dir / "Default" / "LOCK").unlink(missing_ok=True)

        stealth = """
            Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
            Object.defineProperty(navigator,'languages',{get:()=>['pt-BR','pt','en-US','en']});
            window.chrome={runtime:{},loadTimes:function(){},csi:function(){},app:{}};
        """

        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(browser_dir),
                headless=False,
                viewport={"width": 1400, "height": 900},
                args=["--disable-blink-features=AutomationControlled",
                      "--disable-features=site-per-process",
                      "--no-first-run", "--no-default-browser-check", "--lang=pt-BR"],
                locale="pt-BR",
            )

            page = browser.pages[0] if browser.pages else browser.new_page()
            page.add_init_script(stealth)
            page.on("response", lambda r: self._on_browser_response(r))

            page.goto("https://trader.tradovate.com", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)

            self._auto_fill(page)
            logger.info("Resolva captcha se aparecer. Aguardando...")
            page.wait_for_timeout(5000)

            captured_token = self._wait_for_login_token(page, max_steps=14)
            browser.close()

            if captured_token:
                self._commit_token(captured_token, "Chromium stealth")
                return True

            logger.warning("Chromium stealth: token nao capturado")
            return False

    # ───────────────────── Browser helpers ─────────────────────

    def _kill_my_chrome(self):
        """Mata Chrome apenas se o nosso CDP port estiver ocupado."""
        import subprocess
        try:
            out = subprocess.check_output(
                f'netstat -ano | findstr ":{self._browser_port}"', shell=True, text=True
            )
            pid = None
            for line in out.strip().split("\n"):
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
            if pid and pid != "0":
                subprocess.run(
                    ["taskkill", "/PID", pid, "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
        except Exception:
            # Fallback: mata todos os Chrome se nao conseguir identificar o PID
            import subprocess
            subprocess.run(
                ["taskkill", "/IM", "chrome.exe", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

    def _launch_chrome(self, chrome):
        import subprocess
        profile = str(Path("data/browser_profile"))
        subprocess.Popen([
            chrome, f"--remote-debugging-port={self._browser_port}",
            f"--user-data-dir={profile}", "--no-first-run",
            "--no-default-browser-check",
            "https://trader.tradovate.com"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _on_browser_response(self, response):
        """Callback shared entre CDP e stealth — armazena token em self._pending_token."""
        token = _extract_bearer_token(response)
        if token:
            self._pending_token = token

    # ───────────────────── Auto-fill login form ─────────────────────

    def _auto_fill(self, page):
        for sel in ['input[placeholder*="Username"]', 'input[placeholder*="Email"]',
                     'input[name="username"]', 'input[name="login"]',
                     'input[name="email"]', 'input[type="email"]',
                     'input[type="text"]', '#name-input']:
            try:
                inp = page.wait_for_selector(sel, timeout=2000)
                if inp and inp.is_visible():
                    inp.fill(TRADOVATE_USERNAME)
                    logger.info("Username/email preenchido")
                    break
            except Exception:
                pass

        page.wait_for_timeout(500)

        try:
            pwd = page.wait_for_selector('input[type="password"]', timeout=3000)
            if pwd and pwd.is_visible():
                pwd.fill(TRADOVATE_PASSWORD)
                logger.info("Senha preenchida")
        except Exception:
            pass

        page.wait_for_timeout(1000)

        for sel in ['button.Login', 'button:has-text("Login")',
                    '#login-button', 'button[aria-label="Login"]']:
            try:
                btn = page.wait_for_selector(sel, timeout=2000)
                if btn and btn.is_visible():
                    text = btn.inner_text().strip()
                    if text == "Login":
                        btn.click()
                        logger.info(f"Botao '{text}' clicado (id)")
                        return
            except Exception:
                pass

        for btn in page.query_selector_all("button"):
            try:
                text = btn.inner_text().strip()
                if text == "Login":
                    btn.click()
                    logger.info("Botao 'Login' clicado (search)")
                    return
            except Exception:
                pass

        pwd = page.query_selector('input[type="password"]')
        if pwd:
            pwd.press("Enter")
            logger.info("Enter pressionado no campo de senha")

    # ───────────────────── Token renewal ─────────────────────

    def renew_if_needed(self):
        if time.time() > self.token_expiry - 300:
            logger.info("Renovando token...")
            if self._try_api_auth():
                return True
            try:
                resp = requests.post(f"{BASE_URL}/auth/renewaccesstoken",
                                     headers=self.headers(), timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if "accessToken" in data:
                        self._commit_token(data["accessToken"], "Token renovado")
                        return True
            except Exception as e:
                logger.error(f"Renovacao API: {e}")
            logger.info("Renovacao API falhou. Reautenticando...")
            return self._run_in_thread(self._try_chrome_cdp) or \
                   self._run_in_thread(self._try_chromium_stealth)
        return True

    # ───────────────────── API helpers ─────────────────────

    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    def _load_account(self):
        resp = requests.get(f"{BASE_URL}/account/list", headers=self.headers(), timeout=10)
        accounts = resp.json()
        if accounts:
            if isinstance(accounts, list):
                self.account_id   = accounts[0]["id"]
                self.account_spec = accounts[0]["name"]
            else:
                self.account_id   = accounts.get("id")
                self.account_spec = accounts.get("name")
            logger.info(f"Conta: {self.account_spec} (ID: {self.account_id})")
        else:
            logger.error("Nenhuma conta encontrada")

    def is_authenticated(self) -> bool:
        if self.access_token is not None and time.time() < self.token_expiry:
            return True
        if self.access_token is None:
            return self._load_token()
        return False

    def get_accounts(self) -> list:
        """Retorna lista de contas do broker com informações completas."""
        self.renew_if_needed()
        from config.settings import TRADOVATE_API_URL, ENV
        url = f"{TRADOVATE_API_URL[ENV]}/account/list"
        resp = requests.get(url, headers=self.headers(), timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return []
