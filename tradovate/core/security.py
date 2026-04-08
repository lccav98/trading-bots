"""
core/security.py — Security hardening for the Tradovate trading bot

Provides:
  - Token rotation guard (detects 401 patterns suggesting token leak)
  - Rate limit protection (throttles >60 req/min per endpoint)
  - Credential leak detection (credentials echoed in error responses)
  - API response validation (domain / SSL verification)
  - Emergency kill switch (catastrophic P&L drawdown → flatten, revoke, exit)
  - Security audit log (logs/security_audit.log)
"""

import collections
import json
import logging
import os
import signal
import sys
import time

import requests

from config.settings import (
    TRADOVATE_USERNAME,
    TRADOVATE_PASSWORD,
    TRADOVATE_API_URL,
    ENV,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CATASTROPHIC_LOSS = float(os.getenv("CATASTROPHIC_LOSS", "4000.0"))
MAX_401_PER_WINDOW = int(os.getenv("MAX_401_PER_WINDOW", "3"))
AUTH_FAILURE_WINDOW = int(os.getenv("AUTH_FAILURE_WINDOW", "600"))       # seconds
MAX_REQUESTS_PER_MINUTE = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))

EXPECTED_DOMAINS = {"demo.tradovateapi.com", "live.tradovateapi.com",
                    "tradovateapi.com"}

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Audit log setup
# ---------------------------------------------------------------------------

def _ensure_audit_logger():
    """Return a dedicated logger that writes to logs/security_audit.log."""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "security_audit.log")

    audit = logging.getLogger("security_audit")
    audit.setLevel(logging.INFO)
    # Avoid duplicate handlers on reload
    if not audit.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        audit.addHandler(handler)
    return audit


_audit_log = _ensure_audit_logger()


# ---------------------------------------------------------------------------
# SecurityGuard
# ---------------------------------------------------------------------------

class SecurityGuard:
    """Security hardening layer for the Tradovate trading bot."""

    def __init__(self, auth, risk_manager, executor=None):
        """
        Parameters
        ----------
        auth : TradovateAuth
            The auth object (provides token, credentials, headers).
        risk_manager : RiskManager
            Risk manager (provides daily_pnl, flatten access).
        executor : OrderExecutor, optional
            Order executor used for emergency flatten.
        """
        self.auth = auth
        self.risk = risk_manager
        self.executor = executor

        # ---- Token rotation guard ----
        self._401_timestamps: collections.deque = collections.deque()

        # ---- Rate limit protection ----
        # endpoint -> deque of timestamps
        self._call_log: dict[str, collections.deque] = {}

        # ---- Rate limit defaults ----
        self.max_requests_per_minute = MAX_REQUESTS_PER_MINUTE

        # ---- Credential leak detection ----
        self._secrets = [
            s for s in (TRADOVATE_USERNAME, TRADOVATE_PASSWORD) if s
        ]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def check_response(self, resp: requests.Response) -> dict:
        """
        Validate an HTTP response for security issues.

        Returns a dict with keys:
            ok : bool          — response passed all checks
            alerts : list[str] — any security alerts raised
        """
        alerts: list[str] = []

        # 1. Token rotation / 401 guard
        if resp.status_code == 401:
            now = time.time()
            self._401_timestamps.append(now)
            self._prune_401s(now)

            if len(self._401_timestamps) > MAX_401_PER_WINDOW:
                msg = (
                    f"Token failure spike: {len(self._401_timestamps)} "
                    f"401s in last {AUTH_FAILURE_WINDOW}s. "
                    f"Forcing full re-auth."
                )
                alerts.append(msg)
                logger.warning(msg)
                self.audit_event("TOKEN_ROTATION_FORCE", msg)
                self.auth.renew_if_needed()

        # 2. Credential leak detection
        try:
            body_text = resp.text
        except Exception:
            body_text = ""

        for secret in self._secrets:
            if secret and secret in body_text:
                msg = (
                    f"CREDENTIAL LEAK DETECTED — '{secret[:3]}...' "
                    f"found in response body from {resp.url}. "
                    f"Suggest immediate password change."
                )
                alerts.append(msg)
                logger.critical(msg)
                self.audit_event("CREDENTIAL_LEAK", msg)

        # 3. Domain / MITM validation
        domain_ok, domain_msg = self._validate_domain(resp)
        if not domain_ok:
            alerts.append(domain_msg)
            logger.warning(domain_msg)
            self.audit_event("INVALID_DOMAIN", domain_msg)

        # 4. SSL cert validity
        if not getattr(resp, "verify", True):
            ssl_msg = f"SSL certificate NOT verified for {resp.url}"
            alerts.append(ssl_msg)
            logger.warning(ssl_msg)
            self.audit_event("SSL_INVALID", ssl_msg)

        ok = resp.status_code < 400 and not alerts
        return {"ok": ok, "alerts": alerts}

    def record_api_call(self, endpoint: str) -> float:
        """
        Record an API call and enforce rate limiting.

        Returns the number of seconds to wait (backoff), or 0.0 if ok.
        """
        now = time.time()

        if endpoint not in self._call_log:
            self._call_log[endpoint] = collections.deque()

        self._call_log[endpoint].append(now)

        # Prune calls older than 60 seconds
        window_start = now - 60.0
        while self._call_log[endpoint] and self._call_log[endpoint][0] < window_start:
            self._call_log[endpoint].popleft()

        count = len(self._call_log[endpoint])

        if count > self.max_requests_per_minute:
            # Exponential backoff: 2^(count - limit) seconds, capped at 60s
            excess = count - self.max_requests_per_minute
            backoff = min(2 ** excess, 60.0)

            msg = (
                f"Rate limit exceeded on {endpoint}: {count} calls/min. "
                f"Throttling for {backoff:.1f}s."
            )
            logger.warning(msg)
            self.audit_event("RATE_LIMIT_THROTTLE", msg)
            return backoff

        return 0.0

    def emergency_kill(self, reason: str = "UNKNOWN"):
        """
        Full emergency shutdown:

        1. Flatten all positions via the executor
        2. Revoke the auth token (delete from disk)
        3. Save state
        4. Log to audit
        5. Exit the process
        """
        msg = f"EMERGENCY KILL SWITCH — reason: {reason}"
        logger.critical(msg)
        self.audit_event("EMERGENCY_KILL", msg)

        # 1. Flatten positions
        if self.executor:
            try:
                self.executor.flatten_position()
                logger.info("Positions flattened.")
            except Exception as e:
                logger.error(f"Failed to flatten positions: {e}")

        # 2. Revoke token
        self._revoke_token()

        # 3. Save state (snapshot of risk + reason)
        self._save_emergency_state(reason)

        # 4. Send SIGTERM to self so the main loop can clean up if needed
        logger.critical("Process will now exit via SIGTERM.")
        os.kill(os.getpid(), signal.SIGTERM)

        # Fallback — if signal was caught/handled
        sys.exit(1)

    def audit_event(self, event_type: str, details: str):
        """Write an entry to the security audit log."""
        _audit_log.info("[%s] %s", event_type, details)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prune_401s(self, now: float):
        """Remove 401 timestamps outside the tracking window."""
        cutoff = now - AUTH_FAILURE_WINDOW
        while self._401_timestamps and self._401_timestamps[0] < cutoff:
            self._401_timestamps.popleft()

    def _validate_domain(self, resp: requests.Response) -> tuple[bool, str]:
        """Check the response came from an expected Tradovate domain."""
        try:
            hostname = resp.url.split("/")[2]  # e.g. demo.tradovateapi.com
            # Strip port if present
            hostname = hostname.split(":")[0]
            for domain in EXPECTED_DOMAINS:
                if hostname.endswith(domain):
                    return True, ""
            return False, (
                f"Unexpected response domain: {hostname}. "
                f"Expected one of {EXPECTED_DOMAINS}. Possible MITM."
            )
        except Exception as e:
            return False, f"Could not validate response domain: {e}"

    def _revoke_token(self):
        """Delete cached auth token from disk."""
        from pathlib import Path

        from config.settings import TOKEN_FILE

        token_path = Path(TOKEN_FILE)
        if token_path.exists():
            try:
                token_path.unlink()
                logger.info("Auth token revoked (deleted from disk).")
                self.audit_event("TOKEN_REVOKED", f"Deleted {token_path}")
            except Exception as e:
                logger.error(f"Failed to revoke token: {e}")

        self.auth.access_token = None
        self.auth.token_expiry = 0

    def _save_emergency_state(self, reason: str):
        """Persist an emergency state snapshot for post-mortem."""
        state_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data"
        )
        os.makedirs(state_dir, exist_ok=True)
        state_path = os.path.join(state_dir, "emergency_state.json")

        snapshot = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "reason": reason,
            "daily_pnl": getattr(self.risk, "daily_pnl", None),
            "peak_pnl": getattr(self.risk, "peak_pnl", None),
            "open_position": getattr(self.risk, "open_position", None),
            "entry_price": getattr(self.risk, "entry_price", None),
            "trade_count": getattr(self.risk, "trade_count", None),
            "wins": getattr(self.risk, "wins", None),
            "losses": getattr(self.risk, "losses", None),
        }

        try:
            with open(state_path, "w") as f:
                json.dump(snapshot, f, indent=2, default=str)
            logger.info(f"Emergency state saved to {state_path}")
        except Exception as e:
            logger.error(f"Failed to save emergency state: {e}")
