"""
Alpha360 — Financial Planner
===============================
Piano finanziario completo per generare rendita:
- PAC (Piano di Accumulo Capitale)
- Income da dividendi/cedole
- Simulazione pensionistica
- Allocazione portfolio suggerita basata sulle analisi
- Proiezione patrimonio nel tempo
"""

import logging
import math
from typing import Dict, List

logger = logging.getLogger("alpha360.planner")


class FinancialPlanner:

    def __init__(self, options: dict = None):
        self.options = options or {}

    def compute_pac(self, monthly: float, years: int, annual_rate: float = 7.0) -> dict:
        """
        Piano di Accumulo Capitale.
        Calcola crescita del patrimonio con versamenti mensili.
        """
        r = annual_rate / 100 / 12  # tasso mensile
        n = years * 12
        total_invested = monthly * n

        # Valore futuro rendita periodica
        if r > 0:
            future_value = monthly * ((math.pow(1 + r, n) - 1) / r)
        else:
            future_value = total_invested

        total_gain = future_value - total_invested
        gain_pct = (total_gain / total_invested * 100) if total_invested > 0 else 0

        # Proiezione anno per anno
        yearly = []
        balance = 0
        for year in range(1, years + 1):
            for m in range(12):
                balance = balance * (1 + r) + monthly
            yearly.append({
                "year": year,
                "balance": round(balance, 2),
                "invested": round(monthly * 12 * year, 2),
                "gain": round(balance - monthly * 12 * year, 2),
            })

        # Rendita mensile dal capitale finale (regola 3.5%)
        monthly_income_35 = round(future_value * 0.035 / 12, 2)
        monthly_income_4 = round(future_value * 0.04 / 12, 2)

        return {
            "monthly_investment": monthly,
            "years": years,
            "annual_rate_pct": annual_rate,
            "total_invested": round(total_invested, 2),
            "future_value": round(future_value, 2),
            "total_gain": round(total_gain, 2),
            "gain_pct": round(gain_pct, 1),
            "monthly_income_3_5_pct": monthly_income_35,
            "monthly_income_4_pct": monthly_income_4,
            "yearly_projection": yearly,
        }

    def compute_income(self, capital: float, yield_pct: float = 4.0,
                       withdrawal_pct: float = 3.5) -> dict:
        """
        Calcolo rendita passiva da capitale investito.
        Considera yield (dividendi/cedole) e safe withdrawal rate.
        """
        annual_yield = capital * yield_pct / 100
        monthly_yield = annual_yield / 12

        annual_withdrawal = capital * withdrawal_pct / 100
        monthly_withdrawal = annual_withdrawal / 12

        # Proiezione 30 anni con withdrawal
        real_rate = (yield_pct - withdrawal_pct) / 100  # crescita netta annua
        projection = []
        bal = capital
        for year in range(1, 31):
            income = bal * withdrawal_pct / 100
            growth = bal * yield_pct / 100
            bal = bal + growth - income
            projection.append({
                "year": year,
                "balance": round(bal, 2),
                "annual_income": round(income, 2),
                "monthly_income": round(income / 12, 2),
                "depleted": bal <= 0,
            })
            if bal <= 0:
                break

        years_sustainable = len([p for p in projection if not p["depleted"]])

        return {
            "capital": capital,
            "yield_pct": yield_pct,
            "withdrawal_pct": withdrawal_pct,
            "annual_dividend_income": round(annual_yield, 2),
            "monthly_dividend_income": round(monthly_yield, 2),
            "safe_annual_withdrawal": round(annual_withdrawal, 2),
            "safe_monthly_withdrawal": round(monthly_withdrawal, 2),
            "years_sustainable": years_sustainable,
            "projection_30y": projection,
        }

    def compute_retirement(self, current_age: int, retire_age: int,
                           monthly_saving: float, current_capital: float,
                           target_monthly_income: float, growth_rate: float = 7.0,
                           inflation: float = 2.0) -> dict:
        """
        Simulazione pensionistica completa.
        Fase 1: Accumulo (ora → pensione)
        Fase 2: Decumulo (pensione → fine)
        """
        years_to_retire = retire_age - current_age
        years_in_retirement = 90 - retire_age  # assumiamo vita fino a 90

        # Tasso reale (al netto inflazione)
        real_rate = (1 + growth_rate / 100) / (1 + inflation / 100) - 1
        r_monthly = real_rate / 12

        # FASE 1: Accumulo
        accumulation = []
        balance = current_capital
        for year in range(1, years_to_retire + 1):
            for m in range(12):
                balance = balance * (1 + r_monthly) + monthly_saving
            accumulation.append({
                "age": current_age + year,
                "year": year,
                "balance": round(balance, 2),
            })

        capital_at_retirement = balance

        # Target mensile aggiustato per inflazione
        inflation_factor = math.pow(1 + inflation / 100, years_to_retire)
        target_real = target_monthly_income * inflation_factor
        annual_need = target_real * 12
        withdrawal_rate = (annual_need / capital_at_retirement * 100) if capital_at_retirement > 0 else 999

        # FASE 2: Decumulo
        decumulation = []
        bal = capital_at_retirement
        # In decumulo: rendimento ridotto (più conservativo: 4% reale)
        dec_rate = 0.04 / 12
        for year in range(1, years_in_retirement + 1):
            annual_income = 0
            for m in range(12):
                withdrawal = target_real
                bal = bal * (1 + dec_rate) - withdrawal
                annual_income += withdrawal
            decumulation.append({
                "age": retire_age + year,
                "year": year,
                "balance": round(max(0, bal), 2),
                "annual_income": round(annual_income, 2),
                "depleted": bal <= 0,
            })
            if bal <= 0:
                break

        years_funded = len([d for d in decumulation if not d["depleted"]])
        is_sustainable = years_funded >= years_in_retirement

        # Gap analysis
        if not is_sustainable:
            # Quanto serve per essere sostenibile
            needed = target_real * 12 / 0.035  # usando 3.5% SWR
            gap = needed - capital_at_retirement
            extra_monthly = gap / (years_to_retire * 12) if years_to_retire > 0 else gap
        else:
            gap = 0
            extra_monthly = 0

        return {
            "current_age": current_age,
            "retire_age": retire_age,
            "monthly_saving": monthly_saving,
            "current_capital": current_capital,
            "target_monthly_income": target_monthly_income,
            "growth_rate_pct": growth_rate,
            "inflation_pct": inflation,
            "years_to_retirement": years_to_retire,
            "capital_at_retirement": round(capital_at_retirement, 2),
            "target_income_inflation_adjusted": round(target_real, 2),
            "withdrawal_rate_pct": round(withdrawal_rate, 2),
            "is_sustainable": is_sustainable,
            "years_funded": years_funded,
            "gap_to_sustainability": round(gap, 2),
            "extra_monthly_needed": round(extra_monthly, 2),
            "accumulation": accumulation,
            "decumulation": decumulation,
        }

    def suggest_portfolio(self, analyses: list, options: dict = None) -> dict:
        """
        Suggerimento allocazione portfolio basato sulle analisi correnti.
        Classifica titoli per actionability e rating.
        """
        if not analyses:
            return {"error": "Nessuna analisi disponibile", "allocations": []}

        buys = [a for a in analyses if a.get("final_rating") == "BUY"
                and a.get("actionability") in ("HIGH", "MEDIUM")]
        watches = [a for a in analyses if a.get("final_rating") == "WATCH"
                   or (a.get("final_rating") == "BUY" and a.get("actionability") in ("LOW", "DISCOVERY_ONLY"))]
        sells = [a for a in analyses if a.get("final_rating") == "SELL"]

        allocations = []
        total_score = sum(max(a.get("confidence", 0), 1) for a in buys) or 1

        for a in buys:
            weight = round(a.get("confidence", 50) / total_score * 70, 1)  # max 70% in BUY
            allocations.append({
                "symbol": a["symbol"],
                "name": a.get("name", ""),
                "rating": a["final_rating"],
                "confidence": a.get("confidence", 0),
                "convergence": a.get("convergence_state", ""),
                "actionability": a.get("actionability", ""),
                "suggested_weight_pct": weight,
                "action": "ACCUMULA" if a.get("actionability") == "HIGH" else "POSIZIONA",
                "entry": a.get("trade_plan", {}).get("entry_zone", ""),
                "stop": a.get("trade_plan", {}).get("stop_zone", ""),
                "target": a.get("trade_plan", {}).get("target_zone", ""),
            })

        for a in watches[:3]:
            allocations.append({
                "symbol": a["symbol"],
                "name": a.get("name", ""),
                "rating": a.get("final_rating", "WATCH"),
                "confidence": a.get("confidence", 0),
                "convergence": a.get("convergence_state", ""),
                "actionability": a.get("actionability", ""),
                "suggested_weight_pct": 5,
                "action": "MONITORA",
                "entry": a.get("trade_plan", {}).get("entry_zone", ""),
            })

        # Cash reserve
        allocated = sum(a["suggested_weight_pct"] for a in allocations)
        cash = max(0, 100 - allocated)
        allocations.append({
            "symbol": "CASH",
            "name": "Liquidità / Money Market",
            "rating": "—",
            "suggested_weight_pct": round(cash, 1),
            "action": "RISERVA",
        })

        # Summary
        avg_confidence = round(sum(a.get("confidence", 0) for a in buys) / len(buys), 1) if buys else 0

        return {
            "allocations": allocations,
            "summary": {
                "total_positions": len(buys),
                "watch_list": len(watches),
                "sell_signals": len(sells),
                "avg_confidence": avg_confidence,
                "cash_pct": round(cash, 1),
                "risk_level": "AGGRESSIVO" if cash < 15 else ("MODERATO" if cash < 35 else "CONSERVATIVO"),
            },
            "sells_to_avoid": [{"symbol": a["symbol"], "reason": f"Rating SELL, score {a.get('scores',{}).get('final_score',0)}"} for a in sells],
        }

    def full_plan(self, analyses: list, options: dict = None) -> dict:
        """Piano finanziario completo integrato con le analisi."""
        opts = options or self.options
        monthly = opts.get("pac_monthly_amount", 500)
        years = opts.get("pac_years", 20)
        target_income = opts.get("target_monthly_income", 2000)

        pac = self.compute_pac(monthly, years, 7.0)
        income = self.compute_income(pac["future_value"], 4.0, 3.5)
        retirement = self.compute_retirement(
            current_age=40, retire_age=65,
            monthly_saving=monthly, current_capital=0,
            target_monthly_income=target_income,
            growth_rate=7.0, inflation=2.0
        )
        portfolio = self.suggest_portfolio(analyses, opts)

        # Sintesi operativa
        summary = {
            "pac_monthly": monthly,
            "pac_years": years,
            "pac_final_capital": pac["future_value"],
            "achievable_monthly_income": income["safe_monthly_withdrawal"],
            "target_monthly_income": target_income,
            "gap_to_target": round(target_income - income["safe_monthly_withdrawal"], 2),
            "is_target_achievable": income["safe_monthly_withdrawal"] >= target_income,
            "recommended_positions": len([a for a in portfolio.get("allocations", [])
                                          if a.get("action") in ("ACCUMULA", "POSIZIONA")]),
            "portfolio_risk": portfolio.get("summary", {}).get("risk_level", ""),
        }

        return {
            "summary": summary,
            "pac": pac,
            "income": income,
            "retirement": retirement,
            "portfolio": portfolio,
            "generated_at": __import__("datetime").datetime.now().isoformat(),
        }
