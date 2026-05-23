import time
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class SessionManager:

    def __init__(self, min_vol_ratio=1.0, hours_avoid=None, active_sessions=None):
        self.min_vol_ratio    = min_vol_ratio
        self.hours_avoid      = hours_avoid or []
        self.active_sessions   = active_sessions or []
        self._last_vol_check  = 0
        self._vol_ok          = True
        self._vol_check_ttl   = 300

    def should_enter(self, vol_ratio=None):
        from datetime import datetime, timezone
        hour_utc = datetime.now(timezone.utc).hour

        if hour_utc in self.hours_avoid:
            return False, "horário restrito"

        if self.active_sessions:
            in_session = any(a <= hour_utc < b for a, b in self.active_sessions)
            if not in_session:
                return False, "fora de sessão"

        return True, "ok"

    def should_enter_volatile(self, vol_ratio=None):
        from datetime import datetime, timezone
        hour_utc = datetime.now(timezone.utc).hour

        if hour_utc in self.hours_avoid:
            return False, "horário restrito"

        if not self.active_sessions:
            return True, "ok"

        in_session = any(a <= hour_utc < b for a, b in self.active_sessions)
        if in_session:
            return True, "ok"

        if vol_ratio is not None and vol_ratio >= self.min_vol_ratio:
            return True, "fora de sessão + vol alta"

        return False, "fora de sessão"