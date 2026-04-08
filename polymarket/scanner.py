import requests
import json
import time
import logging

logger = logging.getLogger("scanner")

class MarketScanner:
    """Scans Polymarket's Gamma API for tradeable markets."""

    GAMMA_URL = "https://gamma-api.polymarket.com"

    def __init__(self, min_volume=1000, min_liquidity=500, max_markets=30, max_pages=3):
        self.min_volume = min_volume
        self.min_liquidity = min_liquidity
        self.max_markets = max_markets
        self.max_pages = max_pages
        self._cache = None
        self._cache_time = 0
        self._cache_ttl = 120

    def fetch_active_markets(self):
        """Fetch top active, non-resolved markets (limited pages for speed)."""
        markets = []
        offset = 0
        limit = 100
        pages_fetched = 0

        while pages_fetched < self.max_pages:
            try:
                resp = requests.get(
                    f"{self.GAMMA_URL}/markets",
                    params={
                        "closed": "false",
                        "limit": limit,
                        "offset": offset,
                        "order": "volume24hr",
                        "ascending": "false",
                    },
                    timeout=15
                )
                resp.raise_for_status()
                batch = resp.json()
                if not batch:
                    break
                markets.extend(batch)
                offset += limit
                pages_fetched += 1
                time.sleep(0.3)
            except Exception as e:
                logger.error(f"Error fetching markets: {e}")
                break

        return markets

    def filter_markets(self, markets):
        """Filter to markets worth trading."""
        watchlist = []

        for m in markets:
            volume_24h = float(m.get("volume24hr", 0))
            liquidity = float(m.get("liquidityClob", 0))

            if volume_24h < self.min_volume:
                continue
            if liquidity < self.min_liquidity:
                continue

            raw_tokens = m.get("clobTokenIds", [])
            if isinstance(raw_tokens, str):
                try:
                    tokens = json.loads(raw_tokens)
                except (json.JSONDecodeError, TypeError):
                    continue
            else:
                tokens = raw_tokens

            if not tokens:
                continue

            raw_prices = m.get("outcomePrices", "[0.5,0.5]")
            if isinstance(raw_prices, str):
                try:
                    prices = json.loads(raw_prices)
                except (json.JSONDecodeError, TypeError):
                    prices = [0.5, 0.5]
            else:
                prices = raw_prices

            try:
                price = float(prices[0])
            except (ValueError, IndexError, TypeError):
                continue

            if price > 0.95 or price < 0.05:
                continue

            watchlist.append({
                "condition_id": m["conditionId"],
                "question": m["question"],
                "token_ids": tokens,
                "price": price,
                "volume_24h": volume_24h,
                "liquidity": liquidity,
                "slug": m.get("slug", ""),
                "end_date": m.get("endDate", ""),
            })

        watchlist.sort(key=lambda x: x["volume_24h"], reverse=True)
        return watchlist[:self.max_markets]

    def scan(self):
        """Full scan: fetch, filter, return watchlist."""
        import time as _time
        now = _time.time()
        if self._cache and (now - self._cache_time) < self._cache_ttl:
            logger.info(f"Using cached watchlist ({len(self._cache)} markets)")
            return self._cache

        logger.info("Starting market scan...")
        raw = self.fetch_active_markets()
        logger.info(f"Fetched {len(raw)} raw markets")
        filtered = self.filter_markets(raw)
        logger.info(f"Filtered to {len(filtered)} tradeable markets")

        self._cache = filtered
        self._cache_time = now
        return filtered
