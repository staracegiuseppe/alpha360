"""
Alpha360 — Scoring Engine v2
==============================
Scoring composito 0-100 con:
- Oversold strength (0-25)
- Undervaluation (0-25)  
- Momentum reversal probability (0-25)
- Financial health (0-25)

Output: BUY / WATCH / AVOID con motivazione
Anti value-trap filter integrato.
"""

import hashlib
import logging
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger("alpha360.engine")


class ScoringEngine:

    # ─── COMPONENT SCORES ──────────────────────────────────────────

    def oversold_strength(self, tech: dict) -> dict:
        """
        0-25 score. Quanto è forte il segnale di ipervenduto?
        Usa RSI + Bollinger %B + volume + divergenze.
        NON basta RSI < 30 da solo (filtra falsi segnali).
        """
        score = 0
        reasons = []

        rsi = tech.get("rsi", {})
        bb = tech.get("bollinger", {})
        vol = tech.get("volume", {})
        rsi_val = rsi.get("value", 50) if isinstance(rsi, dict) else rsi

        # RSI scoring (max 8 pt)
        if rsi_val <= 25:
            score += 8; reasons.append(f"RSI {rsi_val} estremo ipervenduto")
        elif rsi_val <= 30:
            score += 6; reasons.append(f"RSI {rsi_val} ipervenduto")
        elif rsi_val <= 35:
            score += 3; reasons.append(f"RSI {rsi_val} vicino ipervenduto")
        elif rsi_val <= 40:
            score += 1

        # Bollinger %B (max 6 pt) — conferma RSI
        pct_b = bb.get("pct_b", 0.5) if isinstance(bb, dict) else 0.5
        if pct_b <= 0.0:
            score += 6; reasons.append("Prezzo sotto Bollinger inferiore")
        elif pct_b <= 0.1:
            score += 4; reasons.append("Prezzo vicino Bollinger inferiore")
        elif pct_b <= 0.2:
            score += 2

        # RSI Divergence (max 6 pt) — segnale forte di inversione
        div = rsi.get("divergence", "NONE") if isinstance(rsi, dict) else "NONE"
        if div == "BULLISH":
            score += 6; reasons.append("Divergenza RSI bullish rilevata")
        elif div == "BEARISH":
            score -= 2  # penalità se divergenza bearish

        # Volume confirmation (max 5 pt)
        conf = vol.get("confirmation", "NONE") if isinstance(vol, dict) else "NONE"
        if vol.get("climax", False) if isinstance(vol, dict) else False:
            score += 3; reasons.append("Volume climax (possibile capitolazione)")
        if conf == "BULLISH_CONFIRMED":
            score += 2; reasons.append("Volume conferma movimento rialzista")

        return {"score": max(0, min(25, score)), "reasons": reasons}

    def undervaluation_score(self, fundamentals: dict) -> dict:
        """
        0-25 score. Quanto è sottovalutato il titolo?
        Usa valuation, growth, margins, debt — con filtro anti value-trap.
        """
        score = 0
        reasons = []
        is_value_trap = False

        val = (fundamentals.get("valuation") or "").upper()
        growth = (fundamentals.get("growth") or "").upper()
        margins = (fundamentals.get("margins") or "").upper()
        debt = (fundamentals.get("debt") or "").upper()
        eq = (fundamentals.get("earnings_quality") or "").upper()

        # Valuation (max 8 pt)
        if "CHEAP" in val or "ATTRACTIVE" in val:
            score += 8; reasons.append("Valutazione attrattiva")
        elif "FAIR" in val:
            score += 4
        elif "RICH" in val or "EXPENSIVE" in val:
            score -= 2

        # Growth (max 6 pt)
        if "STRONG" in growth or "HIGH" in growth:
            score += 6; reasons.append("Crescita forte")
        elif "SOLID" in growth or "MODERATE" in growth:
            score += 3
        elif "DECLINING" in growth or "NEGATIVE" in growth:
            score -= 4
            is_value_trap = True
            reasons.append("⚠ Growth in declino — rischio value trap")

        # Margins (max 4 pt)
        if "EXPANDING" in margins:
            score += 4
        elif "STABLE" in margins:
            score += 2
        elif "CONTRACTING" in margins:
            score -= 3
            is_value_trap = True

        # Debt (max 4 pt, o penalità)
        if "LOW" in debt or "NONE" in debt:
            score += 4; reasons.append("Debito basso")
        elif "HIGH" in debt:
            score -= 4
            is_value_trap = True
            reasons.append("⚠ Debito alto — rischio value trap")
        elif "CRITICAL" in debt:
            score -= 6
            is_value_trap = True

        # Earnings quality (max 3 pt)
        if "HIGH" in eq:
            score += 3
        elif "LOW" in eq or "POOR" in eq:
            score -= 3
            is_value_trap = True

        # VALUE TRAP FILTER: se economico MA crescita in declino + debito alto → penalizza
        if is_value_trap and score > 10:
            score = max(score - 8, 3)
            reasons.append("🔻 Value trap filter applicato")

        return {"score": max(0, min(25, score)), "reasons": reasons, "is_value_trap": is_value_trap}

    def momentum_reversal(self, tech: dict) -> dict:
        """
        0-25 score. Probabilità di inversione/rimbalzo.
        Usa MACD cross, trend, ADX, Bollinger squeeze.
        """
        score = 0
        reasons = []

        macd = tech.get("macd", {})
        adx = tech.get("adx", {})
        bb = tech.get("bollinger", {})
        trend = tech.get("trend", {})

        # MACD cross (max 8 pt)
        macd_cross = macd.get("cross", "NONE") if isinstance(macd, dict) else "NONE"
        macd_str = macd.get("strength", 0) if isinstance(macd, dict) else 0
        if macd_cross == "BULLISH_CROSS":
            score += 8; reasons.append("MACD bullish cross")
        elif macd_cross == "BEARISH_CROSS":
            score -= 3
        if macd_str >= 2:
            score += 2; reasons.append("Histogram MACD in accelerazione")
        elif macd_str <= -2:
            score -= 2

        # Trend context (max 5 pt)
        td = trend.get("direction", "") if isinstance(trend, dict) else ""
        if "STRONG_UP" in td:
            score += 5; reasons.append("Strong uptrend attivo")
        elif "UP" in td:
            score += 3
        elif "STRONG_DOWN" in td:
            score -= 3
        elif "DOWN" in td:
            score -= 1
        # MA cross
        ma_cross = trend.get("ma_cross", "NONE") if isinstance(trend, dict) else "NONE"
        if ma_cross == "GOLDEN_CROSS":
            score += 3; reasons.append("Golden cross MA50/MA200")
        elif ma_cross == "DEATH_CROSS":
            score -= 3

        # ADX trend strength (max 4 pt)
        adx_val = adx.get("value", 20) if isinstance(adx, dict) else 20
        if adx_val >= 25:
            score += 4; reasons.append(f"Trend forte (ADX {adx_val})")
        elif adx_val >= 20:
            score += 2

        # Bollinger squeeze → potenziale breakout (max 4 pt)
        if isinstance(bb, dict) and bb.get("squeeze"):
            score += 4; reasons.append("Bollinger squeeze → breakout imminente")

        # Penalità se in downtrend senza segnali di inversione
        if "DOWN" in td and macd_cross != "BULLISH_CROSS":
            score -= 2

        return {"score": max(0, min(25, score)), "reasons": reasons}

    def financial_health(self, fundamentals: dict, smart_money: dict = None,
                         asset_type: str = "STOCK") -> dict:
        """
        0-25 score. Solidità finanziaria complessiva.
        Health score 1-5 + smart money signals.
        """
        if asset_type == "ETF":
            return {"score": 15, "health_rating": 4, "reasons": ["ETF diversificato"]}

        score = 0
        reasons = []

        # Financial Health Score (1-5 scala interna)
        health = 0

        val = (fundamentals.get("valuation") or "").upper()
        growth = (fundamentals.get("growth") or "").upper()
        debt = (fundamentals.get("debt") or "").upper()
        margins = (fundamentals.get("margins") or "").upper()
        eq = (fundamentals.get("earnings_quality") or "").upper()

        if "LOW" in debt or "NONE" in debt: health += 1
        if "EXPANDING" in margins or "STABLE" in margins: health += 1
        if "STRONG" in growth or "SOLID" in growth: health += 1
        if "HIGH" in eq or "GOOD" in eq: health += 1
        if "ATTRACTIVE" in val or "FAIR" in val: health += 1

        score += health * 3  # max 15

        # Smart money signals (max 10)
        if smart_money and isinstance(smart_money, dict):
            buys = len(smart_money.get("insider_buys") or [])
            sells = len(smart_money.get("insider_sells") or [])
            cluster = (smart_money.get("cluster_signal") or "").upper()

            if buys >= 2:
                score += 4; reasons.append(f"{buys} insider buy recenti")
            elif buys >= 1:
                score += 2

            if sells >= 3:
                score -= 3; reasons.append(f"⚠ {sells} insider sell")

            if "STRONG_BUY" in cluster:
                score += 4; reasons.append("Cluster insider bullish")
            elif "STRONG_SELL" in cluster:
                score -= 3

            oc = smart_money.get("ownership_change_pct", 0) or 0
            if oc > 2:
                score += 2; reasons.append(f"Ownership istituzionale +{oc}%")
            elif oc < -2:
                score -= 2

        if not reasons:
            reasons.append(f"Health score {health}/5")

        return {"score": max(0, min(25, score)), "health_rating": health, "reasons": reasons}

    # ─── COMPOSITE SCORING ─────────────────────────────────────────

    def compute_composite_score(self, tech: dict, fundamentals: dict,
                                 smart_money: dict = None,
                                 asset_type: str = "STOCK") -> dict:
        """
        Score composito 0-100.
        4 componenti da 0-25 ciascuna.
        """
        os_result = self.oversold_strength(tech)
        uv_result = self.undervaluation_score(fundamentals)
        mr_result = self.momentum_reversal(tech)
        fh_result = self.financial_health(fundamentals, smart_money, asset_type)

        total = os_result["score"] + uv_result["score"] + mr_result["score"] + fh_result["score"]

        # Signal
        if total >= 65:
            signal = "BUY"
        elif total >= 40:
            signal = "WATCH"
        else:
            signal = "AVOID"

        # Rebound probability (basata su oversold + momentum)
        rebound_prob = min(95, max(5,
            os_result["score"] * 2 + mr_result["score"] * 1.5 + 10
        ))

        # Convergence
        scores_list = [os_result["score"], uv_result["score"],
                       mr_result["score"], fh_result["score"]]
        above_12 = sum(1 for s in scores_list if s >= 12)
        if above_12 >= 3:
            convergence = "STRONG"
        elif above_12 >= 2:
            convergence = "PARTIAL"
        elif any(s >= 18 for s in scores_list) and any(s <= 5 for s in scores_list):
            convergence = "DIVERGENT"
        else:
            convergence = "INSUFFICIENT"

        # Actionability
        if signal == "BUY" and convergence == "STRONG":
            actionability = "HIGH"
        elif signal == "BUY":
            actionability = "MEDIUM"
        elif signal == "WATCH" and convergence in ("STRONG", "PARTIAL"):
            actionability = "LOW"
        else:
            actionability = "DISCOVERY_ONLY"

        # Confidence
        confidence = min(95, max(10, round(total * 0.8 + 15)))
        if convergence == "STRONG":
            confidence = min(95, confidence + 10)
        elif convergence == "DIVERGENT":
            confidence = max(10, confidence - 15)

        all_reasons = (os_result["reasons"] + uv_result["reasons"] +
                       mr_result["reasons"] + fh_result["reasons"])

        return {
            "total_score": total,
            "signal": signal,
            "confidence": confidence,
            "convergence": convergence,
            "actionability": actionability,
            "rebound_probability": round(rebound_prob),
            "is_value_trap": uv_result.get("is_value_trap", False),
            "components": {
                "oversold_strength": os_result["score"],
                "undervaluation": uv_result["score"],
                "momentum_reversal": mr_result["score"],
                "financial_health": fh_result["score"],
            },
            "health_rating": fh_result.get("health_rating", 0),
            "reasons": all_reasons,
        }

    # ─── FULL ANALYSIS PIPELINE ────────────────────────────────────

    def run_full_analysis(self, raw: dict) -> dict:
        """Pipeline completa: raw data → analisi finale."""
        at = raw.get("asset_type", "STOCK")
        tech = raw.get("technical", {})
        fund = raw.get("fundamentals", {})
        sm = raw.get("smart_money", {})
        fresh = raw.get("freshness", {})

        composite = self.compute_composite_score(tech, fund, sm, at)

        # Build bullish/bearish from reasons
        bullish = [r for r in composite["reasons"] if not r.startswith("⚠") and not r.startswith("🔻")]
        bearish = [r for r in composite["reasons"] if r.startswith("⚠") or r.startswith("🔻")]
        # Add from raw if present
        bullish = (raw.get("bullish_factors") or bullish)[:4]
        bearish = (raw.get("bearish_factors") or bearish)[:4]

        # Data quality
        sd = fresh.get("smart_money_days", 30)
        fd = fresh.get("fundamentals_days", 30)
        if sd <= 15 and fd <= 60:
            dq = "HIGH"
        elif sd <= 30:
            dq = "MEDIUM"
        else:
            dq = "LOW"
        if at == "ETF":
            dq = "HIGH" if fd <= 30 else "MEDIUM"

        return {
            "symbol": raw.get("symbol", ""),
            "name": raw.get("name", ""),
            "market": raw.get("market", ""),
            "asset_type": at,
            "price": raw.get("price", 0),
            "change_pct": raw.get("change_pct", 0),
            "updated_at": raw.get("updated_at", datetime.now().isoformat()),
            "analyzed_at": datetime.now().isoformat(),
            # New scoring
            "final_rating": composite["signal"],
            "composite_score": composite["total_score"],
            "confidence": composite["confidence"],
            "convergence_state": composite["convergence"],
            "actionability": composite["actionability"],
            "rebound_probability": composite["rebound_probability"],
            "is_value_trap": composite["is_value_trap"],
            "health_rating": composite["health_rating"],
            "data_quality": dq,
            "components": composite["components"],
            # Legacy compat
            "scores": {
                "final_score": composite["total_score"],
                "oversold": composite["components"]["oversold_strength"],
                "undervaluation": composite["components"]["undervaluation"],
                "momentum": composite["components"]["momentum_reversal"],
                "financial_health": composite["components"]["financial_health"],
            },
            "freshness": fresh,
            "bullish_factors": bullish,
            "bearish_factors": bearish,
            "smart_money": sm,
            "technical": tech,
            "macro_sector": raw.get("macro_sector", {}),
            "fundamentals": fund,
            "trade_plan": raw.get("trade_plan", {}),
            "events": raw.get("events", []),
        }

    def get_info(self) -> dict:
        return {
            "scoring": "Composite 0-100",
            "components": {
                "oversold_strength": "0-25: RSI + Bollinger + Volume + Divergenze",
                "undervaluation": "0-25: Fondamentali + filtro anti value-trap",
                "momentum_reversal": "0-25: MACD cross + trend + ADX + squeeze",
                "financial_health": "0-25: Health 1-5 + smart money",
            },
            "signals": {
                "BUY": "score >= 65",
                "WATCH": "40 <= score < 65",
                "AVOID": "score < 40",
            },
            "filters": ["RSI confirmation (BB + volume)", "Value trap filter",
                         "RSI divergence detection", "Bollinger squeeze"],
        }

    @staticmethod
    def digest_hash(analyses: list) -> str:
        key = "|".join(f"{a.get('symbol','')}:{a.get('final_rating','')}:{a.get('composite_score',0)}"
                       for a in sorted(analyses, key=lambda x: x.get("symbol", "")))
        return hashlib.md5(key.encode()).hexdigest()[:12]

    @staticmethod
    def detect_changes(current: list, previous: list) -> list:
        if not previous:
            return [{"symbol": a["symbol"], "type": "NEW", "detail": "Prima analisi"} for a in current]
        pm = {a["symbol"]: a for a in previous}
        changes = []
        for a in current:
            p = pm.get(a["symbol"])
            if not p:
                changes.append({"symbol": a["symbol"], "type": "NEW", "detail": "Nuovo"})
            elif p.get("final_rating") != a.get("final_rating"):
                changes.append({"symbol": a["symbol"], "type": "RATING",
                                "detail": f"{p['final_rating']} → {a['final_rating']}"})
        return changes
