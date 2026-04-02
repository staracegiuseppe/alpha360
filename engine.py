"""
Alpha360 — Scoring Engine
===========================
Score ranges:
  technical:    -40 .. +40
  macro:        -15 .. +15
  sector:       -10 .. +10
  smart_money:  -15 .. +15  (Form 4: 3.5x, 13F: 0.5x)
  fundamentals: -20 .. +20
  risk_penalty:   0 .. -15
Final: -100 .. +100 → BUY (>=25), SELL (<=-25), WATCH
"""

import hashlib
import logging
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger("alpha360.engine")

SCORE_RANGES = {
    "technical": (-40, 40), "macro": (-15, 15), "sector": (-10, 10),
    "smart_money": (-15, 15), "fundamentals": (-20, 20), "risk_penalty": (-15, 0),
}


class ScoringEngine:

    def run_full_analysis(self, raw: dict) -> dict:
        at = raw.get("asset_type", "STOCK")
        tech = raw.get("technical", {})
        macro = raw.get("macro_sector", {})
        sm = raw.get("smart_money", {})
        fund = raw.get("fundamentals", {})
        fresh = raw.get("freshness", {"technical_hours": 4, "smart_money_days": 30, "fundamentals_days": 30})

        dq = self._data_quality(fresh, sm, at)
        scores = {
            "technical": self._tech_score(tech),
            "macro": self._macro_score(macro),
            "sector": self._sector_score(macro),
            "smart_money": self._sm_score(sm, at),
            "fundamentals": self._fund_score(fund, at),
            "risk_penalty": self._risk_penalty(tech, fund, dq, fresh),
        }
        fs = sum(scores.values())
        fs = max(-100, min(100, fs))
        scores["final_score"] = fs

        conv = self._convergence(scores)
        rating = "BUY" if fs >= 25 else ("SELL" if fs <= -25 else "WATCH")
        act = self._actionability(fs, dq, conv)
        conf = self._confidence(scores, dq, fresh)

        result = {
            **{k: raw.get(k) for k in [
                "symbol", "name", "market", "asset_type", "price",
                "change_pct", "updated_at"
            ]},
            "final_rating": rating,
            "actionability": act,
            "confidence": conf,
            "data_quality": dq,
            "convergence_state": conv,
            "freshness": fresh,
            "scores": scores,
            "bullish_factors": raw.get("bullish_factors", []),
            "bearish_factors": raw.get("bearish_factors", []),
            "smart_money": sm,
            "technical": tech,
            "macro_sector": macro,
            "fundamentals": fund,
            "trade_plan": raw.get("trade_plan", {}),
            "events": raw.get("events", []),
            "analyzed_at": datetime.now().isoformat(),
        }
        return result

    def _tech_score(self, t: dict) -> int:
        s = 0.0
        trend = (t.get("trend") or "").upper()
        if "UP" in trend: s += 12
        elif "DOWN" in trend: s -= 12

        rsi = t.get("rsi")
        if rsi is not None:
            if 55 <= rsi <= 70: s += 6
            elif 40 <= rsi < 55: s += 2
            elif 30 <= rsi < 40: s -= 4
            elif rsi < 30: s -= 8
            elif rsi > 70: s += 4
            if rsi > 80: s -= 2

        macd = (t.get("macd") or "").upper()
        if "BULL" in macd: s += 8
        elif "BEAR" in macd: s -= 8

        adx = t.get("adx")
        if adx is not None:
            if adx >= 30: s += 6
            elif adx >= 20: s += 2
            else: s -= 2

        d50 = t.get("ma50_distance_pct", 0) or 0
        if d50 > 3: s += 4
        elif d50 > 0: s += 2
        elif d50 < -3: s -= 4
        elif d50 < 0: s -= 2

        d200 = t.get("ma200_distance_pct", 0) or 0
        if d200 > 0: s += 2
        elif d200 < -5: s -= 2

        return int(max(-40, min(40, s)))

    def _macro_score(self, m: dict) -> int:
        s = 0.0
        reg = (m.get("macro_regime") or "").upper()
        if reg == "RISK_ON": s += 7
        elif reg == "RISK_OFF": s -= 7

        vix = m.get("vix", 18)
        if vix and vix < 14: s += 4
        elif vix and vix < 18: s += 2
        elif vix and vix > 25: s -= 5
        elif vix and vix > 20: s -= 3

        bias = (m.get("macro_bias") or "").upper()
        if "BULLISH" in bias: s += 4
        elif "BEARISH" in bias: s -= 4

        return int(max(-15, min(15, s)))

    def _sector_score(self, m: dict) -> int:
        st = (m.get("sector_strength") or "").upper()
        if st == "STRONG": return 7
        elif st == "MODERATE": return 3
        elif st == "WEAK": return -5
        return 0

    def _sm_score(self, sm: dict, at: str) -> int:
        if at == "ETF": return 0
        s = 0.0
        buys = len(sm.get("insider_buys") or [])
        sells = len(sm.get("insider_sells") or [])
        s += buys * 3.5
        s -= sells * 2.975

        oc = sm.get("ownership_change_pct", 0) or 0
        if oc > 2: s += 1
        elif oc < -2: s -= 1

        cl = (sm.get("cluster_signal") or "").upper()
        if "STRONG_BUY" in cl: s += 4
        elif "STRONG_SELL" in cl: s -= 4
        elif "MODERATE_BUY" in cl: s += 2
        elif "MODERATE_SELL" in cl: s -= 2

        return int(max(-15, min(15, s)))

    def _fund_score(self, f: dict, at: str) -> int:
        if at == "ETF":
            v = (f.get("valuation") or "").upper()
            if "ATTRACTIVE" in v: return 8
            elif "FAIR" in v: return 4
            return 0

        s = 0.0
        v = (f.get("valuation") or "").upper()
        if "ATTRACTIVE" in v or "CHEAP" in v: s += 6
        elif "FAIR" in v: s += 2
        elif "RICH" in v or "EXPENSIVE" in v: s -= 4

        g = (f.get("growth") or "").upper()
        if "STRONG" in g or "HIGH" in g: s += 5
        elif "SOLID" in g or "MODERATE" in g: s += 3
        elif "DECLINING" in g: s -= 5

        m = (f.get("margins") or "").upper()
        if "EXPANDING" in m: s += 4
        elif "STABLE" in m: s += 1
        elif "CONTRACTING" in m: s -= 4

        d = (f.get("debt") or "").upper()
        if "LOW" in d or "NONE" in d: s += 3
        elif "HIGH" in d: s -= 4
        elif "CRITICAL" in d: s -= 6

        e = (f.get("earnings_quality") or "").upper()
        if "HIGH" in e: s += 3
        elif "GOOD" in e: s += 2
        elif "LOW" in e or "POOR" in e: s -= 4

        return int(max(-20, min(20, s)))

    def _risk_penalty(self, tech, fund, dq, fresh) -> int:
        p = 0
        rsi = tech.get("rsi", 50)
        if rsi and (rsi > 80 or rsi < 20): p -= 4
        adx = tech.get("adx", 20)
        if adx and adx < 15: p -= 3
        if dq == "LOW": p -= 5
        d = (fund.get("debt") or "").upper()
        if "HIGH" in d or "CRITICAL" in d: p -= 4
        if fresh.get("smart_money_days", 30) > 45: p -= 2
        return max(-15, p)

    def _data_quality(self, fresh, sm, at) -> str:
        if at == "ETF":
            return "HIGH" if fresh.get("fundamentals_days", 30) <= 30 else "MEDIUM"
        sd = fresh.get("smart_money_days", 30)
        fd = fresh.get("fundamentals_days", 30)
        ins = len(sm.get("insider_buys", [])) + len(sm.get("insider_sells", []))
        if sd <= 15 and fd <= 60 and ins > 0: return "HIGH"
        elif sd <= 30 or (fd <= 60 and ins > 0): return "MEDIUM"
        return "LOW"

    def _convergence(self, scores) -> str:
        ts = 1 if scores.get("technical", 0) > 5 else (-1 if scores.get("technical", 0) < -5 else 0)
        ms = 1 if scores.get("macro", 0) > 3 else (-1 if scores.get("macro", 0) < -3 else 0)
        ss = 1 if scores.get("smart_money", 0) > 3 else (-1 if scores.get("smart_money", 0) < -3 else 0)
        sigs = [x for x in [ts, ms, ss] if x != 0]
        if len(sigs) < 2: return "INSUFFICIENT"
        if all(x == sigs[0] for x in sigs):
            return "STRONG" if len(sigs) == 3 else "PARTIAL"
        if any(x > 0 for x in sigs) and any(x < 0 for x in sigs):
            return "DIVERGENT"
        return "PARTIAL"

    def _actionability(self, fs, dq, conv) -> str:
        if dq == "LOW" or conv == "INSUFFICIENT": return "DISCOVERY_ONLY"
        a = abs(fs)
        if conv == "STRONG" and a >= 30: return "HIGH"
        if conv in ("STRONG", "PARTIAL") and a >= 20: return "MEDIUM"
        if a < 15: return "DISCOVERY_ONLY"
        return "LOW"

    def _confidence(self, scores, dq, fresh) -> int:
        c = 50.0
        c += min(abs(scores.get("final_score", 0)) * 0.3, 20)
        if dq == "HIGH": c += 15
        elif dq == "LOW": c -= 20
        if fresh.get("technical_hours", 4) <= 2: c += 5
        sd = fresh.get("smart_money_days", 30)
        if sd <= 7: c += 5
        elif sd > 30: c -= 10
        if fresh.get("fundamentals_days", 30) <= 30: c += 5
        return max(10, min(95, round(c)))

    def get_info(self) -> dict:
        return {
            "score_ranges": SCORE_RANGES,
            "rating_thresholds": {"BUY": ">=25", "SELL": "<=-25", "WATCH": "in-between"},
            "convergence_matrix": {
                "STRONG": "Tecnico + Macro + Smart Money allineati",
                "PARTIAL": "2/3 layer allineati",
                "DIVERGENT": "Layer in conflitto",
                "INSUFFICIENT": "Dati insufficienti",
            },
            "weights": {
                "form4_per_event": "3.5x (fresh insider)",
                "f13_factor": "0.5x (delayed ~45 days)",
            },
        }

    @staticmethod
    def digest_hash(analyses: list) -> str:
        key = "|".join(
            f"{a['symbol']}:{a.get('final_rating','')}:{a.get('confidence',0)}:{a.get('convergence_state','')}"
            for a in sorted(analyses, key=lambda x: x.get("symbol", ""))
        )
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
                changes.append({"symbol": a["symbol"], "type": "NEW", "detail": "Nuovo titolo"})
            elif p.get("final_rating") != a.get("final_rating"):
                changes.append({"symbol": a["symbol"], "type": "RATING",
                                "detail": f"{p['final_rating']} → {a['final_rating']}"})
            elif p.get("convergence_state") != a.get("convergence_state"):
                changes.append({"symbol": a["symbol"], "type": "CONVERGENCE",
                                "detail": f"{p['convergence_state']} → {a['convergence_state']}"})
        return changes
