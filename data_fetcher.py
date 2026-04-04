"""
Alpha360 — Data Fetcher
=========================
Yahoo Finance Chart API con gestione cookie consent + crumb.
Yahoo v8 blocca senza cookie → usiamo flow consent EU.
"""

import logging
import re
import time
from urllib.parse import quote
from typing import Optional

import httpx

from indicators import compute_all

logger = logging.getLogger("alpha360.fetcher")

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart"
YAHOO_CRUMB_URL = "https://query2.finance.yahoo.com/v1/test/getcrumb"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class DataFetcher:
    def __init__(self):
        self._cookies = None
        self._crumb = None
        self._crumb_ts = 0
        self._vix_cache = None
        self._vix_ts = 0
        self._client = httpx.Client(
            timeout=20,
            headers={"User-Agent": UA},
            follow_redirects=True,
        )

    def _ensure_crumb(self):
        """Ottieni cookie consent + crumb per Yahoo Finance."""
        now = time.time()
        if self._crumb and (now - self._crumb_ts) < 3600:
            return
        try:
            # Step 1: visita yahoo finance per cookie consent
            r = self._client.get("https://finance.yahoo.com/quote/AAPL")
            # Step 2: ottieni crumb
            r2 = self._client.get(YAHOO_CRUMB_URL)
            if r2.status_code == 200:
                self._crumb = r2.text.strip()
                self._crumb_ts = now
                logger.info(f"[Yahoo] Crumb obtained: {self._crumb[:8]}...")
            else:
                logger.warning(f"[Yahoo] Crumb failed: {r2.status_code}")
                self._crumb = None
        except Exception as e:
            logger.warning(f"[Yahoo] Crumb error: {e}")
            self._crumb = None

    def fetch_yahoo(self, symbol: str, period: str = "6mo", interval: str = "1d") -> Optional[dict]:
        """Fetch OHLCV data da Yahoo Finance."""
        self._ensure_crumb()
        try:
            encoded = quote(symbol, safe="")
            url = f"{YAHOO_CHART}/{encoded}"
            params = {
                "range": period,
                "interval": interval,
                "includePrePost": "false",
                "events": "div,splits",
            }
            if self._crumb:
                params["crumb"] = self._crumb

            resp = self._client.get(url, params=params)

            # Fallback: riprova senza crumb se 401
            if resp.status_code == 401:
                logger.info(f"[Yahoo] 401 for {symbol}, retrying without crumb")
                params.pop("crumb", None)
                resp = self._client.get(url, params=params)

            if resp.status_code != 200:
                logger.error(f"[Yahoo] {symbol}: HTTP {resp.status_code}")
                return None

            data = resp.json()
            chart = data.get("chart", {}).get("result", [])
            if not chart:
                logger.error(f"[Yahoo] {symbol}: empty result")
                return None

            result = chart[0]
            meta = result.get("meta", {})
            indicators = result.get("indicators", {}).get("quote", [{}])[0]
            timestamps = result.get("timestamp", [])

            closes = [c for c in (indicators.get("close") or []) if c is not None]
            highs = [h for h in (indicators.get("high") or []) if h is not None]
            lows = [lo for lo in (indicators.get("low") or []) if lo is not None]
            volumes = [v for v in (indicators.get("volume") or []) if v is not None]

            if not closes:
                return None

            price = meta.get("regularMarketPrice", closes[-1])
            prev_close = meta.get("chartPreviousClose", meta.get("previousClose", price))

            return {
                "price": price,
                "prev_close": prev_close,
                "meta": meta,
                "closes": closes,
                "highs": highs,
                "lows": lows,
                "volumes": volumes,
                "timestamps": timestamps,
            }
        except Exception as e:
            logger.error(f"[Yahoo] {symbol} error: {e}")
            return None

    def compute_technicals(self, symbol: str, yahoo_data: dict) -> dict:
        """Calcola tutti gli indicatori tecnici."""
        closes = yahoo_data.get("closes", [])
        highs = yahoo_data.get("highs", [])
        lows = yahoo_data.get("lows", [])
        volumes = yahoo_data.get("volumes", [])
        if len(closes) < 20:
            return {"trend_direction": "INSUFFICIENT_DATA", "rsi_value": 50,
                    "technical_state": "Dati insufficienti"}
        return compute_all(closes, highs, lows, volumes)

    def fetch_vix(self) -> Optional[float]:
        """VIX con cache 5 minuti."""
        now = time.time()
        if self._vix_cache and (now - self._vix_ts) < 300:
            return self._vix_cache
        try:
            data = self.fetch_yahoo("^VIX", period="5d", interval="1d")
            if data and data.get("price"):
                self._vix_cache = data["price"]
                self._vix_ts = now
                return self._vix_cache
        except Exception:
            pass
        return self._vix_cache or 18.0

    def close(self):
        self._client.close()
