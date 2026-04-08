import requests
import json
import logging
import time
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger("signals.value")


@dataclass
class ValueSignal:
    condition_id: str
    token_id: str
    side: str
    strength: float
    reason: str
    market_question: str = ""
    token_id_up: str = ""
    token_id_down: str = ""
    expected_value: float = 0.0


class ResolvedMarketScanner:
    """Fetches Polymarket markets ordered by volume."""

    GAMMA_URL = "https://gamma-api.polymarket.com/markets"

    def __init__(self, min_volume=10000, min_liquidity=500, max_fetch_pages=2):
        self.min_volume = min_volume
        self.min_liquidity = min_liquidity
        self.max_fetch_pages = max_fetch_pages
        self._last_fetch = None
        self._last_fetch_time = 0
        self._cache_ttl = 180

    def fetch_all_active(self):
        now = time.time()
        if self._last_fetch and (now - self._last_fetch_time) < self._cache_ttl:
            logger.info(f"Using cached market list ({len(self._last_fetch)} markets)")
            return self._last_fetch

        markets = []
        params = {
            "closed": "false",
            "limit": 100,
            "order": "volume24hr",
            "ascending": "false",
        }
        pages = 0

        while pages < self.max_fetch_pages:
            try:
                params["offset"] = pages * 100
                resp = requests.get(self.GAMMA_URL, params=params, timeout=15)
                resp.raise_for_status()
                batch = resp.json()
                if not batch:
                    break
                markets.extend(batch)
                pages += 1
                time.sleep(0.2)
            except Exception as e:
                logger.error(f"Error fetching markets page {pages}: {e}")
                break

        self._last_fetch = markets
        self._last_fetch_time = now
        logger.info(f"Fetched {len(markets)} markets from {pages} pages")
        return markets

    def parse_market(self, m):
        try:
            raw_prices = m.get("outcomePrices", "[0.5,0.5]")
            prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
            p_yes = float(prices[0])
            p_no = float(prices[1]) if len(prices) > 1 else 1 - p_yes
        except (ValueError, IndexError, TypeError):
            return None

        try:
            raw_tokens = m.get("clobTokenIds", "[]")
            tokens = json.loads(raw_tokens) if isinstance(raw_tokens, str) else raw_tokens
        except (ValueError, TypeError):
            tokens = []

        return {
            "condition_id": m.get("conditionId", ""),
            "question": m.get("question", ""),
            "price": p_yes,
            "price_no": p_no,
            "token_ids": tokens,
            "token_id_yes": tokens[0] if len(tokens) > 0 else "",
            "token_id_no": tokens[1] if len(tokens) > 1 else "",
            "volume_24h": float(m.get("volume24hr", 0)),
            "liquidity": float(m.get("liquidityClob", 0)),
            "end_date": m.get("endDate", ""),
            "slug": m.get("slug", ""),
        }

    def scan(self):
        raw = self.fetch_all_active()
        markets = []
        for m in raw:
            parsed = self.parse_market(m)
            if parsed is None:
                continue
            if parsed["volume_24h"] < self.min_volume:
                continue
            markets.append(parsed)
        return markets


class ValueSignalGenerator:
    """
    SAFE VALUE BETTING - REVISED AFTER DISASTER (08/04/2026)

    Lessons learned:
    - NEVER bet against Bitcoin in uptrend = always loses
    - NEVER take probabilities < 10% (terrible odds)
    - EV >= 5% is NOT enough - need better analysis
    - Avoid crypto/near-crypto markets (too unpredictable)
    
    New rules:
    - MIN_PROBABILITY = 0.40 (40%) - only bet on likely outcomes
    - EXCLUDE crypto-related markets
    - Only markets resolving in 1-6 hours (not days)
    - Require EV >= 10% (was 5%)
    """

    # Safe thresholds
    MIN_EXPECTED_VALUE = 0.10  # 10% EV (raised from 5%)
    MAX_PRICE = 0.90  # Don't buy above 90%
    MAX_SIGNALS_PER_SCAN = 3
    MAX_HOURS_TO_RESOLVE = 6  # Shorter = less risk
    MIN_PROBABILITY = 0.40  # 40% minimum
    
    # Block crypto markets
    BLOCKED_KEYWORDS = [
        "bitcoin", "btc", "ethereum", "eth", "crypto", 
        "solana", "dogecoin", "ether", "blockchain",
        "dip to", "below $", "above $"  # Too speculative
    ]
    
    # Block news/outdated events
    BLOCKED_NEWS_KEYWORDS = [
        "will the price",  # Future price predictions
        "will be above", "will be below",  # Price targets
        "january", "february", "march", "april",  # Far future
        "may", "june", "july", "august",  # Far future
        "september", "october", "november", "december"  # Far future
    ]
    
    # Only events in reasonable time
    MIN_HOURS = 0.5  # At least 30 minutes
    MAX_HOURS_TO_RESOLVE = 12  # Relaxed to 12 hours (was 6)

    def __init__(self, min_volume=5000, max_hours_to_resolve=24, near_resolved_threshold=0.94):
        self.min_volume = min_volume
        self.max_hours_to_resolve = max_hours_to_resolve
        self.near_resolved_threshold = near_resolved_threshold

    def _parse_end_date(self, date_str):
        if not date_str:
            return None
        try:
            if isinstance(date_str, str):
                end_ts = datetime.fromisoformat(date_str.replace("Z", "+00:00")).timestamp()
            else:
                end_ts = float(date_str)
            hours_left = (end_ts - datetime.now(timezone.utc).timestamp()) / 3600
            return max(0, hours_left)
        except Exception:
            return None

    def generate_for_watchlist(self, watchlist):
        signals = []

        for m in watchlist:
            p_yes = m.get("price", 0.5)
            p_no = m.get("price_no", 0.5)
            volume = m.get("volume_24h", 0)
            question = m.get("question", "")
            hours_left = self._parse_end_date(m.get("end_date", ""))

            if volume < self.min_volume:
                continue
            
            # BLOCK CRYPTO AND SPECULATIVE MARKETS (after disaster)
            q_lower = question.lower()
            for blocked in self.BLOCKED_KEYWORDS:
                if blocked in q_lower:
                    logger.info(f"Skipping blocked: {question[:50]}...")
                    continue
                        
            # BLOCK NEWS/FAR-FUTURE MARKETS
            for blocked in self.BLOCKED_NEWS_KEYWORDS:
                if blocked in q_lower:
                    logger.info(f"Skipping far-future/news: {question[:50]}...")
                    continue
            
            # Must resolve in reasonable time
            if hours_left is None or hours_left < self.MIN_HOURS or hours_left > self.MAX_HOURS_TO_RESOLVE:
                continue

            # --- STRATEGY 1: Near-resolved markets (YES > 94% or NO > 94%)
            # Buying the likely side at a slight discount, resolving to $1.00
            # Skip markets already at $0.95+ (effectively resolved, zero edge)
            if p_yes >= self.near_resolved_threshold and p_yes < self.MAX_PRICE:
                # BUY YES at p_yes. If YES resolves (very likely), payout = $1.00
                payout_pct = round((1.0 - p_yes) / p_yes * 100, 1)
                # Only accept if EV >= 5% AND resolving soon
                expected_val = round((1.0 - p_yes), 4)
                if expected_val >= self.MIN_EXPECTED_VALUE and hours_left is not None and hours_left <= self.MAX_HOURS_TO_RESOLVE:
                    urgency_bonus = max(0, (self.MAX_HOURS_TO_RESOLVE - hours_left) / self.MAX_HOURS_TO_RESOLVE)
                    signals.append(ValueSignal(
                        condition_id=m["condition_id"],
                        token_id=m.get("token_id_yes", ""),
                        side="BUY",
                        strength=min(round(p_yes * urgency_bonus, 2), 1.0),
                        reason=f"Near-resolved: BUY YES ${p_yes:.3f} -> $1.00 | +{payout_pct}% in {hours_left:.0f}h | {question[:70]}",
                        market_question=question,
                        token_id_up=m.get("token_id_yes", ""),
                        token_id_down=m.get("token_id_no", ""),
                        expected_value=expected_val,
                    ))

            elif p_no >= self.near_resolved_threshold and p_no < self.MAX_PRICE:
                payout_pct = round((1.0 - p_no) / p_no * 100, 1)
                expected_val = round((1.0 - p_no), 4)
                if expected_val >= self.MIN_EXPECTED_VALUE and hours_left is not None and hours_left <= self.MAX_HOURS_TO_RESOLVE:
                    urgency_bonus = max(0, (self.MAX_HOURS_TO_RESOLVE - hours_left) / self.MAX_HOURS_TO_RESOLVE)
                    signals.append(ValueSignal(
                        condition_id=m["condition_id"],
                        token_id=m.get("token_id_no", ""),
                        side="BUY",
                        strength=min(round(p_no * urgency_bonus, 2), 1.0),
                        reason=f"Near-resolved: BUY NO ${p_no:.3f} -> $1.00 | +{payout_pct}% in {hours_left:.0f}h | {question[:70]}",
                        market_question=question,
                        token_id_up=m.get("token_id_yes", ""),
                        token_id_down=m.get("token_id_no", ""),
                        expected_value=expected_val,
                    ))

            # --- STRATEGY 2: Undervalued markets today (70-90% with <12h left)
            elif hours_left is not None and 0 < hours_left <= 12:
                prob = max(p_yes, p_no)
                if prob >= self.MIN_PROBABILITY and prob < self.MAX_PRICE:
                    side = "YES" if p_yes > p_no else "NO"
                    price = max(p_yes, p_no)
                    token = m.get("token_id_yes", "") if side == "YES" else m.get("token_id_no", "")
                    payout_pct = round((1.0 - price) / price * 100, 1)
                    expected_val = round((1.0 - price), 4)
                    
                    # Score based on EV and urgency
                    # Higher score = better trade
                    urgency_score = (12 - hours_left) / 12  # 0 to 1
                    final_score = expected_val * 0.7 + urgency_score * 0.3
                    
                    # Only accept if EV >= 5%
                    if expected_val >= self.MIN_EXPECTED_VALUE:
                        signals.append(ValueSignal(
                            condition_id=m["condition_id"],
                            token_id=token,
                            side="BUY",
                            strength=min(round(final_score, 2), 1.0),
                            reason=f"Today {hours_left:.0f}h: BUY {side} ${price:.3f} -> $1.00 | +{payout_pct}% | {question[:70]}",
                            market_question=question,
                            token_id_up=m.get("token_id_yes", ""),
                            token_id_down=m.get("token_id_no", ""),
                            expected_value=expected_val,
                        ))

        # Sort: highest expected value first
        signals.sort(key=lambda s: s.expected_value, reverse=True)
        
        # Limit to max signals per scan
        signals = signals[:self.MAX_SIGNALS_PER_SCAN]

        logger.info(f"Value signals: {len(signals)} (filtered: EV >= {self.MIN_EXPECTED_VALUE*100}%, max {self.MAX_SIGNALS_PER_SCAN}, hours <= {self.MAX_HOURS_TO_RESOLVE})")
        return signals
