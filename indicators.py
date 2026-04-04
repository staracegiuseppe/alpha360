"""
Alpha360 — Technical Indicators
=================================
Calcolo indicatori tecnici avanzati da dati OHLCV.
Ogni funzione è pura: input lista numeri → output valore/dict.

Indicatori:
- RSI(14) con divergence detection
- MACD(12,26,9) con cross e histogram
- Bollinger Bands(20,2) con squeeze detection  
- ADX(14) con +DI/-DI
- Volume analysis (OBV, relative volume, climax)
- Supporti/Resistenze (pivot points + fractal)
- Trend detection (MA50/MA200 golden/death cross)
"""

import math
from typing import Dict, List, Optional, Tuple


# ─── EMA ───────────────────────────────────────────────────────────
def ema(data: list, period: int) -> list:
    if len(data) < period:
        return [sum(data) / len(data)] * len(data) if data else []
    k = 2 / (period + 1)
    result = [sum(data[:period]) / period]
    for i in range(period, len(data)):
        result.append(data[i] * k + result[-1] * (1 - k))
    return result


def sma(data: list, period: int) -> list:
    if len(data) < period:
        return [sum(data) / len(data)] * len(data) if data else []
    result = []
    for i in range(len(data) - period + 1):
        result.append(sum(data[i:i + period]) / period)
    return result


# ─── RSI ───────────────────────────────────────────────────────────
def compute_rsi(closes: list, period: int = 14) -> dict:
    """
    RSI con smoothing Wilder + divergence detection.
    Ritorna: {value, state, overbought, oversold, divergence}
    """
    if len(closes) < period + 1:
        return {"value": 50, "state": "NEUTRAL", "overbought": False,
                "oversold": False, "divergence": "NONE"}

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsi_values = []
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))

    rsi = round(rsi_values[-1], 1) if rsi_values else 50

    # Divergence detection (ultimi 20 periodi)
    divergence = _detect_rsi_divergence(closes, rsi_values)

    state = "NEUTRAL"
    if rsi >= 70:
        state = "OVERBOUGHT"
    elif rsi <= 30:
        state = "OVERSOLD"
    elif 50 < rsi < 70:
        state = "BULLISH_MOMENTUM"
    elif 30 < rsi <= 50:
        state = "BEARISH_MOMENTUM"

    return {
        "value": rsi,
        "state": state,
        "overbought": rsi >= 70,
        "oversold": rsi <= 30,
        "divergence": divergence,
        "history": rsi_values[-5:] if len(rsi_values) >= 5 else rsi_values,
    }


def _detect_rsi_divergence(closes: list, rsi_values: list) -> str:
    """
    Bullish divergence: prezzo fa lower low ma RSI fa higher low
    Bearish divergence: prezzo fa higher high ma RSI fa lower high
    """
    if len(closes) < 20 or len(rsi_values) < 10:
        return "NONE"

    # Prendi ultimi 20 periodi prezzo e RSI corrispondenti
    n = min(20, len(rsi_values))
    p = closes[-(n):]
    r = rsi_values[-(n):]

    # Trova minimi/massimi locali (semplificato: min/max di prima/seconda metà)
    half = n // 2
    p_low1, p_low2 = min(p[:half]), min(p[half:])
    r_low1 = r[p[:half].index(p_low1)]
    r_low2_idx = p[half:].index(p_low2)
    r_low2 = r[half + r_low2_idx] if half + r_low2_idx < len(r) else r[-1]

    p_high1, p_high2 = max(p[:half]), max(p[half:])
    r_high1 = r[p[:half].index(p_high1)]
    r_high2_idx = p[half:].index(p_high2)
    r_high2 = r[half + r_high2_idx] if half + r_high2_idx < len(r) else r[-1]

    # Bullish: prezzo lower low + RSI higher low
    if p_low2 < p_low1 and r_low2 > r_low1 + 2:
        return "BULLISH"

    # Bearish: prezzo higher high + RSI lower high
    if p_high2 > p_high1 and r_high2 < r_high1 - 2:
        return "BEARISH"

    return "NONE"


# ─── MACD ──────────────────────────────────────────────────────────
def compute_macd(closes: list, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """
    MACD con histogram e cross detection.
    Ritorna: {value, signal, histogram, state, cross, strength}
    """
    if len(closes) < slow + signal:
        return {"value": 0, "signal_line": 0, "histogram": 0,
                "state": "NEUTRAL", "cross": "NONE", "strength": 0}

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)

    # Allinea le lunghezze
    offset = len(ema_fast) - len(ema_slow)
    macd_line = [ema_fast[i + offset] - ema_slow[i] for i in range(len(ema_slow))]

    if len(macd_line) < signal:
        return {"value": 0, "signal_line": 0, "histogram": 0,
                "state": "NEUTRAL", "cross": "NONE", "strength": 0}

    signal_line = ema(macd_line, signal)

    # Allinea
    ml_offset = len(macd_line) - len(signal_line)
    histogram = [macd_line[i + ml_offset] - signal_line[i] for i in range(len(signal_line))]

    macd_val = round(macd_line[-1], 4)
    sig_val = round(signal_line[-1], 4)
    hist_val = round(histogram[-1], 4)

    # Cross detection
    cross = "NONE"
    if len(histogram) >= 2:
        if histogram[-2] <= 0 and histogram[-1] > 0:
            cross = "BULLISH_CROSS"
        elif histogram[-2] >= 0 and histogram[-1] < 0:
            cross = "BEARISH_CROSS"

    # State
    state = "NEUTRAL"
    if macd_val > sig_val and macd_val > 0:
        state = "STRONG_BULLISH"
    elif macd_val > sig_val:
        state = "BULLISH"
    elif macd_val < sig_val and macd_val < 0:
        state = "STRONG_BEARISH"
    elif macd_val < sig_val:
        state = "BEARISH"

    # Histogram momentum (confronto ultimi 3)
    strength = 0
    if len(histogram) >= 3:
        if histogram[-1] > histogram[-2] > histogram[-3]:
            strength = 2  # accelerating
        elif histogram[-1] > histogram[-2]:
            strength = 1
        elif histogram[-1] < histogram[-2] < histogram[-3]:
            strength = -2
        elif histogram[-1] < histogram[-2]:
            strength = -1

    return {
        "value": macd_val,
        "signal_line": sig_val,
        "histogram": hist_val,
        "state": state,
        "cross": cross,
        "strength": strength,
    }


# ─── BOLLINGER BANDS ──────────────────────────────────────────────
def compute_bollinger(closes: list, period: int = 20, std_dev: float = 2.0) -> dict:
    """
    Bollinger Bands con squeeze detection e %B.
    Ritorna: {upper, middle, lower, bandwidth, pct_b, squeeze, state}
    """
    if len(closes) < period:
        price = closes[-1] if closes else 0
        return {"upper": price, "middle": price, "lower": price,
                "bandwidth": 0, "pct_b": 0.5, "squeeze": False,
                "state": "INSUFFICIENT_DATA"}

    # SMA e deviazione standard
    window = closes[-period:]
    middle = sum(window) / period
    variance = sum((x - middle) ** 2 for x in window) / period
    std = math.sqrt(variance)

    upper = round(middle + std_dev * std, 4)
    lower = round(middle - std_dev * std, 4)
    middle = round(middle, 4)

    price = closes[-1]

    # Bandwidth (normalizzato)
    bandwidth = round((upper - lower) / middle * 100, 2) if middle > 0 else 0

    # %B (posizione del prezzo nelle bande)
    pct_b = round((price - lower) / (upper - lower), 3) if (upper - lower) > 0 else 0.5

    # Squeeze detection: bandwidth sotto il 20° percentile storico
    squeeze = False
    if len(closes) >= period * 3:
        bw_history = []
        for i in range(period, len(closes)):
            w = closes[i - period:i]
            m = sum(w) / period
            s = math.sqrt(sum((x - m) ** 2 for x in w) / period)
            bw_history.append((2 * std_dev * s) / m * 100 if m > 0 else 0)
        if bw_history:
            threshold = sorted(bw_history)[len(bw_history) // 5]  # 20th percentile
            squeeze = bandwidth <= threshold

    # State
    if pct_b >= 1.0:
        state = "ABOVE_UPPER"
    elif pct_b <= 0.0:
        state = "BELOW_LOWER"
    elif pct_b >= 0.8:
        state = "NEAR_UPPER"
    elif pct_b <= 0.2:
        state = "NEAR_LOWER"
    elif squeeze:
        state = "SQUEEZE"
    else:
        state = "NORMAL"

    return {
        "upper": upper,
        "middle": middle,
        "lower": lower,
        "bandwidth": bandwidth,
        "pct_b": pct_b,
        "squeeze": squeeze,
        "state": state,
    }


# ─── ADX ───────────────────────────────────────────────────────────
def compute_adx(highs: list, lows: list, closes: list, period: int = 14) -> dict:
    """
    ADX con +DI/-DI e trend strength classification.
    Ritorna: {value, plus_di, minus_di, trend_strength, state}
    """
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return {"value": 15, "plus_di": 0, "minus_di": 0,
                "trend_strength": "NONE", "state": "NO_TREND"}

    tr_list, plus_dm, minus_dm = [], [], []
    for i in range(1, n):
        h, l, pc = highs[i], lows[i], closes[i - 1]
        tr_list.append(max(h - l, abs(h - pc), abs(l - pc)))
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)

    # Wilder smoothing
    atr = sum(tr_list[:period]) / period
    apdm = sum(plus_dm[:period]) / period
    amdm = sum(minus_dm[:period]) / period

    dx_values = []
    for i in range(period, len(tr_list)):
        atr = (atr * (period - 1) + tr_list[i]) / period
        apdm = (apdm * (period - 1) + plus_dm[i]) / period
        amdm = (amdm * (period - 1) + minus_dm[i]) / period

        if atr == 0:
            continue
        pdi = 100 * apdm / atr
        mdi = 100 * amdm / atr
        denom = pdi + mdi
        dx = abs(pdi - mdi) / denom * 100 if denom > 0 else 0
        dx_values.append((dx, pdi, mdi))

    if not dx_values:
        return {"value": 15, "plus_di": 0, "minus_di": 0,
                "trend_strength": "NONE", "state": "NO_TREND"}

    # Smooth ADX (Wilder smoothing of DX)
    adx_val = sum(d[0] for d in dx_values[:period]) / min(period, len(dx_values))
    for i in range(period, len(dx_values)):
        adx_val = (adx_val * (period - 1) + dx_values[i][0]) / period

    adx_val = round(adx_val, 1)
    pdi_final = round(dx_values[-1][1], 1)
    mdi_final = round(dx_values[-1][2], 1)

    if adx_val >= 40:
        trend_strength = "VERY_STRONG"
    elif adx_val >= 25:
        trend_strength = "STRONG"
    elif adx_val >= 20:
        trend_strength = "MODERATE"
    else:
        trend_strength = "WEAK"

    if adx_val < 20:
        state = "NO_TREND"
    elif pdi_final > mdi_final:
        state = "UPTREND"
    else:
        state = "DOWNTREND"

    return {
        "value": adx_val,
        "plus_di": pdi_final,
        "minus_di": mdi_final,
        "trend_strength": trend_strength,
        "state": state,
    }


# ─── VOLUME ANALYSIS ──────────────────────────────────────────────
def compute_volume(closes: list, volumes: list, period: int = 20) -> dict:
    """
    Volume analysis: OBV trend, relative volume, volume climax.
    Ritorna: {obv_trend, relative_volume, climax, confirmation}
    """
    if len(closes) < 2 or len(volumes) < period:
        return {"obv_trend": "NEUTRAL", "relative_volume": 1.0,
                "climax": False, "confirmation": "NONE"}

    n = min(len(closes), len(volumes))

    # OBV
    obv = [0]
    for i in range(1, n):
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])

    # OBV trend (SMA 10 di OBV)
    obv_sma = sum(obv[-10:]) / min(10, len(obv))
    obv_trend = "BULLISH" if obv[-1] > obv_sma else "BEARISH"

    # Relative volume (vs media 20 giorni)
    avg_vol = sum(volumes[-period:]) / min(period, len(volumes))
    rel_vol = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 else 1.0

    # Volume climax (>2x media + candela grande)
    climax = rel_vol >= 2.0

    # Conferma: volume supporta il movimento del prezzo
    if len(closes) >= 2:
        price_up = closes[-1] > closes[-2]
        vol_up = volumes[-1] > avg_vol
        if price_up and vol_up:
            confirmation = "BULLISH_CONFIRMED"
        elif not price_up and vol_up:
            confirmation = "BEARISH_CONFIRMED"
        elif price_up and not vol_up:
            confirmation = "BULLISH_WEAK"
        else:
            confirmation = "BEARISH_WEAK"
    else:
        confirmation = "NONE"

    return {
        "obv_trend": obv_trend,
        "relative_volume": rel_vol,
        "climax": climax,
        "confirmation": confirmation,
    }


# ─── MOVING AVERAGES & TREND ──────────────────────────────────────
def compute_trend(closes: list) -> dict:
    """
    Trend basato su MA50 e MA200 con golden/death cross detection.
    """
    price = closes[-1] if closes else 0
    n = len(closes)

    ma50 = sum(closes[-50:]) / min(50, n) if n >= 20 else price
    ma200 = sum(closes[-200:]) / min(200, n) if n >= 50 else price

    ma50_dist = round(((price - ma50) / ma50) * 100, 2) if ma50 else 0
    ma200_dist = round(((price - ma200) / ma200) * 100, 2) if ma200 else 0

    # Trend determination
    if price > ma50 and ma50 > ma200:
        trend = "STRONG_UPTREND"
    elif price > ma50 and price > ma200:
        trend = "UPTREND"
    elif price < ma50 and ma50 < ma200:
        trend = "STRONG_DOWNTREND"
    elif price < ma50 and price < ma200:
        trend = "DOWNTREND"
    else:
        trend = "SIDEWAYS"

    # Golden/Death cross detection (MA50 vs MA200 nella recente storia)
    cross = "NONE"
    if n >= 202:
        ma50_prev = sum(closes[-51:-1]) / 50
        ma200_prev = sum(closes[-201:-1]) / 200
        if ma50_prev <= ma200_prev and ma50 > ma200:
            cross = "GOLDEN_CROSS"
        elif ma50_prev >= ma200_prev and ma50 < ma200:
            cross = "DEATH_CROSS"

    return {
        "direction": trend,
        "ma50": round(ma50, 2),
        "ma200": round(ma200, 2),
        "ma50_distance_pct": ma50_dist,
        "ma200_distance_pct": ma200_dist,
        "price_above_ma50": price > ma50,
        "price_above_ma200": price > ma200,
        "ma_cross": cross,
    }


# ─── SUPPORT / RESISTANCE ────────────────────────────────────────
def compute_support_resistance(highs: list, lows: list, closes: list) -> dict:
    """Pivot points + fractal S/R."""
    if len(closes) < 5:
        p = closes[-1] if closes else 0
        return {"support_1": p, "support_2": p, "resistance_1": p,
                "resistance_2": p, "pivot": p}

    # Classic pivot points (ultimo giorno)
    h, l, c = highs[-1], lows[-1], closes[-1]
    pivot = round((h + l + c) / 3, 2)
    s1 = round(2 * pivot - h, 2)
    s2 = round(pivot - (h - l), 2)
    r1 = round(2 * pivot - l, 2)
    r2 = round(pivot + (h - l), 2)

    return {
        "support_1": s1,
        "support_2": s2,
        "resistance_1": r1,
        "resistance_2": r2,
        "pivot": pivot,
    }


# ─── FULL TECHNICAL ANALYSIS ──────────────────────────────────────
def compute_all(closes: list, highs: list, lows: list, volumes: list) -> dict:
    """Calcola tutti gli indicatori. Entry point principale."""
    price = closes[-1] if closes else 0

    rsi = compute_rsi(closes)
    macd = compute_macd(closes)
    bb = compute_bollinger(closes)
    adx = compute_adx(highs, lows, closes)
    vol = compute_volume(closes, volumes)
    trend = compute_trend(closes)
    sr = compute_support_resistance(highs, lows, closes)

    # Composite technical state
    states = []
    if "UP" in trend["direction"]:
        states.append("Trend rialzista")
    elif "DOWN" in trend["direction"]:
        states.append("Trend ribassista")
    else:
        states.append("Laterale")

    if rsi["oversold"]:
        states.append("RSI ipervenduto")
    elif rsi["overbought"]:
        states.append("RSI ipercomprato")

    if "BULLISH" in macd["state"]:
        states.append("MACD bullish")
    elif "BEARISH" in macd["state"]:
        states.append("MACD bearish")

    if macd["cross"] != "NONE":
        states.append(f"MACD {macd['cross'].lower().replace('_', ' ')}")

    if bb["squeeze"]:
        states.append("Bollinger squeeze")

    if rsi["divergence"] != "NONE":
        states.append(f"RSI divergenza {rsi['divergence'].lower()}")

    if adx["trend_strength"] == "VERY_STRONG":
        states.append("Trend molto forte")
    elif adx["value"] < 20:
        states.append("No trend (ADX basso)")

    if vol["climax"]:
        states.append("Volume climax")

    technical_state = ", ".join(states)

    return {
        "price": price,
        "rsi": rsi,
        "macd": macd,
        "bollinger": bb,
        "adx": adx,
        "volume": vol,
        "trend": trend,
        "support_resistance": sr,
        "technical_state": technical_state,
        # Flattened fields for backward compat
        "rsi_value": rsi["value"],
        "macd_state": macd["state"],
        "adx_value": adx["value"],
        "trend_direction": trend["direction"],
        "ma50_distance_pct": trend["ma50_distance_pct"],
        "ma200_distance_pct": trend["ma200_distance_pct"],
        "support": sr["support_1"],
        "resistance": sr["resistance_1"],
    }
