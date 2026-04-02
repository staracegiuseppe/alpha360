"""
Alpha360 — Data Fetcher
=========================
Yahoo Finance Chart API v8 per prezzi e dati storici.
Calcolo indicatori tecnici: RSI, MACD, ADX, MA50, MA200, S/R.
VIX fetch per contesto macro.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger("alpha360.fetcher")

YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


class DataFetcher:

    def __init__(self):
        self._vix_cache = None
        self._vix_ts = 0

    def fetch_yahoo(self, symbol: str, period: str = "6mo", interval: str = "1d") -> dict:
        """
        Fetch dati da Yahoo Finance Chart API v8.
        Ritorna: {price, prev_close, meta, closes, highs, lows, volumes, timestamps}
        """
        try:
            encoded = quote(symbol, safe="")
            url = f"{YAHOO_BASE}/{encoded}"
            params = {"range": period, "interval": interval, "includePrePost": "false"}

            with httpx.Client(timeout=15, headers=HEADERS, follow_redirects=True) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

            chart = data.get("chart", {}).get("result", [{}])[0]
            meta = chart.get("meta", {})
            indicators = chart.get("indicators", {}).get("quote", [{}])[0]
            timestamps = chart.get("timestamp", [])

            closes = [c for c in (indicators.get("close") or []) if c is not None]
            highs = [h for h in (indicators.get("high") or []) if h is not None]
            lows = [lo for lo in (indicators.get("low") or []) if lo is not None]
            volumes = [v for v in (indicators.get("volume") or []) if v is not None]

            price = meta.get("regularMarketPrice", closes[-1] if closes else 0)
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
            return {}

    def fetch_vix(self) -> Optional[float]:
        """Fetch VIX con cache 5 minuti."""
        now = time.time()
        if self._vix_cache and (now - self._vix_ts) < 300:
            return self._vix_cache

        try:
            data = self.fetch_yahoo("^VIX", period="5d", interval="1d")
            vix = data.get("price", 18.0)
            self._vix_cache = vix
            self._vix_ts = now
            return vix
        except Exception:
            return self._vix_cache or 18.0

    def compute_technicals(self, symbol: str, yahoo_data: dict) -> dict:
        """Calcola indicatori tecnici dai dati Yahoo."""
        closes = yahoo_data.get("closes", [])
        highs = yahoo_data.get("highs", [])
        lows = yahoo_data.get("lows", [])

        if len(closes) < 20:
            return {"trend": "INSUFFICIENT_DATA", "rsi": 50, "macd": "NEUTRAL",
                    "adx": 15, "ma50_distance_pct": 0, "ma200_distance_pct": 0,
                    "support": 0, "resistance": 0, "technical_state": "Dati insufficienti"}

        price = closes[-1]

        # RSI (14 periodi)
        rsi = self._compute_rsi(closes, 14)

        # MACD
        macd_val, signal_val, macd_state = self._compute_macd(closes)

        # ADX (14 periodi)
        adx = self._compute_adx(highs, lows, closes, 14)

        # Medie mobili
        ma50 = sum(closes[-50:]) / min(50, len(closes)) if len(closes) >= 20 else price
        ma200 = sum(closes[-200:]) / min(200, len(closes)) if len(closes) >= 50 else price

        ma50_dist = round(((price - ma50) / ma50) * 100, 2) if ma50 else 0
        ma200_dist = round(((price - ma200) / ma200) * 100, 2) if ma200 else 0

        # Trend
        if price > ma50 and ma50 > ma200 and ma50_dist > 0:
            trend = "UPTREND"
        elif price < ma50 and ma50 < ma200 and ma50_dist < 0:
            trend = "DOWNTREND"
        else:
            trend = "SIDEWAYS"

        # Supporto e Resistenza (ultimi 20 giorni)
        recent_lows = lows[-20:] if len(lows) >= 20 else lows
        recent_highs = highs[-20:] if len(highs) >= 20 else highs
        support = round(min(recent_lows), 2) if recent_lows else 0
        resistance = round(max(recent_highs), 2) if recent_highs else 0

        # Stato tecnico sintetico
        states = []
        if trend == "UPTREND": states.append("Trend rialzista")
        elif trend == "DOWNTREND": states.append("Trend ribassista")
        else: states.append("Laterale")

        if rsi > 70: states.append("RSI overbought")
        elif rsi < 30: states.append("RSI oversold")
        elif rsi > 55: states.append("momentum positivo")

        if "BULL" in macd_state: states.append("MACD bullish")
        elif "BEAR" in macd_state: states.append("MACD bearish")

        if adx > 25: states.append("trend forte (ADX)")
        elif adx < 15: states.append("no trend (ADX basso)")

        tech_state = ", ".join(states)

        return {
            "trend": trend,
            "rsi": round(rsi, 1),
            "macd": macd_state,
            "macd_value": round(macd_val, 4) if macd_val else 0,
            "macd_signal": round(signal_val, 4) if signal_val else 0,
            "adx": round(adx, 1),
            "ma50_distance_pct": ma50_dist,
            "ma200_distance_pct": ma200_dist,
            "ma50": round(ma50, 2),
            "ma200": round(ma200, 2),
            "support": support,
            "resistance": resistance,
            "technical_state": tech_state,
        }

    # ─── RSI ───────────────────────────────────────────────────────
    def _compute_rsi(self, closes: list, period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    # ─── MACD ──────────────────────────────────────────────────────
    def _compute_macd(self, closes: list) -> tuple:
        if len(closes) < 26:
            return 0, 0, "NEUTRAL"

        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        macd_line = [ema12[i] - ema26[i] for i in range(len(ema26))]

        if len(macd_line) < 9:
            return 0, 0, "NEUTRAL"

        signal_line = self._ema(macd_line, 9)

        macd_val = macd_line[-1]
        signal_val = signal_line[-1]

        # Cross detection
        if len(macd_line) >= 2 and len(signal_line) >= 2:
            prev_diff = macd_line[-2] - signal_line[-2]
            curr_diff = macd_val - signal_val
            if prev_diff <= 0 and curr_diff > 0:
                return macd_val, signal_val, "BULLISH_CROSS"
            elif prev_diff >= 0 and curr_diff < 0:
                return macd_val, signal_val, "BEARISH_CROSS"

        if macd_val > signal_val:
            return macd_val, signal_val, "BULLISH"
        else:
            return macd_val, signal_val, "BEARISH"

    # ─── ADX ───────────────────────────────────────────────────────
    def _compute_adx(self, highs: list, lows: list, closes: list, period: int = 14) -> float:
        n = min(len(highs), len(lows), len(closes))
        if n < period + 1:
            return 15.0

        tr_list = []
        plus_dm = []
        minus_dm = []

        for i in range(1, n):
            h = highs[i]
            l = lows[i]
            pc = closes[i - 1]
            tr = max(h - l, abs(h - pc), abs(l - pc))
            tr_list.append(tr)

            up = highs[i] - highs[i - 1]
            down = lows[i - 1] - lows[i]
            plus_dm.append(up if up > down and up > 0 else 0)
            minus_dm.append(down if down > up and down > 0 else 0)

        if len(tr_list) < period:
            return 15.0

        atr = sum(tr_list[:period]) / period
        apdm = sum(plus_dm[:period]) / period
        amdm = sum(minus_dm[:period]) / period

        for i in range(period, len(tr_list)):
            atr = (atr * (period - 1) + tr_list[i]) / period
            apdm = (apdm * (period - 1) + plus_dm[i]) / period
            amdm = (amdm * (period - 1) + minus_dm[i]) / period

        if atr == 0:
            return 15.0

        plus_di = 100 * apdm / atr
        minus_di = 100 * amdm / atr
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0

        return dx  # Simplified — single-period DX as proxy for ADX

    # ─── EMA helper ────────────────────────────────────────────────
    def _ema(self, data: list, period: int) -> list:
        if len(data) < period:
            return data[:]
        k = 2 / (period + 1)
        ema = [sum(data[:period]) / period]
        for val in data[period:]:
            ema.append(val * k + ema[-1] * (1 - k))
        return ema
