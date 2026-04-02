"""
Alpha360 — Main Server
========================
FastAPI server per Home Assistant add-on.
Gestisce: analisi titoli, scoring, email digest, financial planning.
Serve la webapp via HA Ingress.
"""

import json
import logging
import os
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ─── Local modules ─────────────────────────────────────────────────
from engine import ScoringEngine
from data_fetcher import DataFetcher
from ai_analyzer import AIAnalyzer
from email_engine import EmailDigestEngine
from scheduler import Alpha360Scheduler
from financial_planner import FinancialPlanner
from persistence import DataStore

# ─── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("alpha360")

# ─── Load Options ──────────────────────────────────────────────────
OPTIONS_PATH = "/data/options.json"

def load_options() -> dict:
    try:
        if os.path.exists(OPTIONS_PATH):
            with open(OPTIONS_PATH) as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Cannot load options: {e}")
    return {}

options = load_options()
logger.info(f"Options loaded: {len(options)} keys")

# ─── Initialize components ────────────────────────────────────────
store = DataStore("/data/alpha360_store.json")
fetcher = DataFetcher()
scoring = ScoringEngine()
planner = FinancialPlanner(options)

ai_analyzer = AIAnalyzer(
    claude_api_key=options.get("claude_api_key", ""),
    perplexity_api_key=options.get("perplexity_api_key", ""),
)

email_engine = EmailDigestEngine({
    "enabled": options.get("email_enabled", True),
    "recipients": [options.get("email_to", "staracegiuseppe@gmail.com")],
    "smtp_user": options.get("email_from", ""),
    "smtp_password": options.get("email_password", ""),
    "sender": options.get("email_from", ""),
    "mode": options.get("email_mode", "full"),
    "always_send": options.get("always_send", False),
})

# ─── FastAPI App ───────────────────────────────────────────────────
app = FastAPI(title="Alpha360", version="1.0.0")

# Static files
webapp_dir = os.path.join(os.path.dirname(__file__), "webapp")
if os.path.isdir(webapp_dir):
    app.mount("/static", StaticFiles(directory=webapp_dir), name="static")

# ─── Ingress path helper ──────────────────────────────────────────
def get_ingress_path(request: Request) -> str:
    """Extract HA Ingress base path from headers."""
    ingress = request.headers.get("X-Ingress-Path", "")
    return ingress.rstrip("/")

# ─── Symbols from options ─────────────────────────────────────────
def get_symbols() -> list:
    return options.get("symbols", ["AAPL", "MSFT", "ENEL.MI", "VWCE.DE"])

# ═══════════════════════════════════════════════════════════════════
# CORE ANALYSIS PIPELINE
# ═══════════════════════════════════════════════════════════════════

def analyze_symbol(symbol: str, use_ai: bool = True) -> dict:
    """
    Pipeline completa per un singolo titolo:
    1. Fetch dati Yahoo Finance (prezzo, tecnica)
    2. Calcola indicatori tecnici
    3. Fetch VIX per contesto macro
    4. (opzionale) Arricchisci con Claude AI + Perplexity
    5. Calcola scoring Titolo 360
    6. Genera fattori bullish/bearish
    7. Salva in persistence
    """
    try:
        logger.info(f"[Analyze] {symbol} — start")

        # 1. Yahoo Finance data
        yahoo = fetcher.fetch_yahoo(symbol)
        if not yahoo or not yahoo.get("price"):
            return _error_analysis(symbol, "Yahoo data non disponibile")

        # 2. Technical indicators
        tech_data = fetcher.compute_technicals(symbol, yahoo)

        # 3. VIX
        vix = fetcher.fetch_vix()

        # 4. AI enrichment (Claude + Perplexity)
        ai_data = {}
        if use_ai and (ai_analyzer.has_claude or ai_analyzer.has_perplexity):
            ai_data = ai_analyzer.analyze(symbol, yahoo, tech_data, vix)

        # 5. Build raw data and score
        raw = _assemble_raw(symbol, yahoo, tech_data, vix, ai_data)
        result = scoring.run_full_analysis(raw)

        # 6. Save
        store.save_analysis(symbol, result)
        logger.info(f"[Analyze] {symbol} — done: {result.get('final_rating')} score={result.get('scores',{}).get('final_score',0)}")

        return result

    except Exception as e:
        logger.error(f"[Analyze] {symbol} error: {e}\n{traceback.format_exc()}")
        return _error_analysis(symbol, str(e))


def analyze_all(use_ai: bool = True) -> list:
    """Analizza tutti i simboli in watchlist."""
    symbols = get_symbols()
    results = []
    for sym in symbols:
        r = analyze_symbol(sym, use_ai=use_ai)
        results.append(r)
        time.sleep(0.5)  # rate limit Yahoo
    store.save_meta("last_full_run", datetime.now().isoformat())
    store.save_meta("analyses_count", len(results))
    return results


def _assemble_raw(symbol, yahoo, tech_data, vix, ai_data) -> dict:
    """Assembla dati grezzi nel formato input per scoring engine."""
    meta = yahoo.get("meta", {})
    price = yahoo.get("price", 0)
    prev_close = yahoo.get("prev_close", price)
    change_pct = round(((price - prev_close) / prev_close) * 100, 2) if prev_close else 0

    # Market detection
    exchange = meta.get("exchangeName", "").upper()
    market = "NASDAQ"
    if any(k in exchange for k in ("MIL", "MTA", "BIT")):
        market = "MTA"
    elif "XETRA" in exchange or "GER" in exchange:
        market = "XETRA"
    elif "NYSE" in exchange:
        market = "NYSE"

    # Asset type
    qtype = meta.get("instrumentType", meta.get("quoteType", "")).upper()
    asset_type = "ETF" if ("ETF" in qtype or "FUND" in qtype) else "STOCK"

    # Macro context from VIX
    if vix and vix < 15:
        regime, bias = "RISK_ON", "BULLISH"
    elif vix and vix < 20:
        regime, bias = "RISK_ON", "MODERATELY_BULLISH"
    elif vix and vix < 25:
        regime, bias = "MIXED", "NEUTRAL"
    else:
        regime, bias = "RISK_OFF", "BEARISH"

    # Sector mapping
    sector_info = SECTOR_MAP.get(symbol, ("Unknown", "MODERATE", []))

    # AI enriched fields
    fundamentals = ai_data.get("fundamentals", {
        "valuation": "N/A", "growth": "N/A", "margins": "N/A",
        "debt": "N/A", "earnings_quality": "N/A"
    })
    smart_money = ai_data.get("smart_money", {
        "institutional_holders": [], "ownership_change_pct": 0,
        "insider_buys": [], "insider_sells": [],
        "cluster_signal": "NEUTRAL",
        "signal_weight_explanation": "Dati non disponibili — configura API key Perplexity"
    })
    bullish = ai_data.get("bullish_factors", [])
    bearish = ai_data.get("bearish_factors", [])
    events = ai_data.get("events", [])
    trade_plan = ai_data.get("trade_plan", {
        "state": "MONITOR", "entry_zone": "", "stop_zone": "",
        "target_zone": "", "contrary_scenario": ""
    })

    # Freshness
    freshness = {
        "technical_hours": 0.5,
        "smart_money_days": ai_data.get("sm_freshness_days", 30),
        "fundamentals_days": ai_data.get("fund_freshness_days", 30),
    }

    return {
        "symbol": symbol,
        "name": meta.get("longName", meta.get("shortName", symbol)),
        "market": market,
        "asset_type": asset_type,
        "price": price,
        "change_pct": change_pct,
        "updated_at": datetime.now().isoformat(),
        "technical": tech_data,
        "macro_sector": {
            "macro_regime": regime,
            "vix": vix or 18,
            "macro_bias": bias,
            "sector": sector_info[0],
            "sector_strength": sector_info[1],
            "related_assets": sector_info[2] if len(sector_info) > 2 else [],
        },
        "smart_money": smart_money,
        "fundamentals": fundamentals,
        "freshness": freshness,
        "trade_plan": trade_plan,
        "events": events,
        "bullish_factors": bullish,
        "bearish_factors": bearish,
    }


def _error_analysis(symbol: str, error: str) -> dict:
    return {
        "symbol": symbol, "name": symbol, "market": "", "asset_type": "STOCK",
        "price": 0, "change_pct": 0, "updated_at": datetime.now().isoformat(),
        "final_rating": "WATCH", "actionability": "DISCOVERY_ONLY",
        "confidence": 0, "data_quality": "LOW", "convergence_state": "INSUFFICIENT",
        "freshness": {"technical_hours": 999, "smart_money_days": 999, "fundamentals_days": 999},
        "scores": {"final_score": 0, "technical": 0, "macro": 0, "sector": 0,
                   "smart_money": 0, "fundamentals": 0, "risk_penalty": 0},
        "bullish_factors": [], "bearish_factors": [f"Errore: {error}"],
        "smart_money": {}, "technical": {}, "macro_sector": {}, "fundamentals": {},
        "trade_plan": {}, "events": [], "error": error,
    }


# Sector mapping
SECTOR_MAP = {
    "AAPL": ("Technology", "STRONG", ["QQQ", "XLK", "MSFT"]),
    "MSFT": ("Technology", "STRONG", ["QQQ", "XLK", "AAPL"]),
    "GOOG": ("Technology", "STRONG", ["QQQ", "XLC", "META"]),
    "GOOGL": ("Technology", "STRONG", ["QQQ", "XLC", "META"]),
    "AMZN": ("Consumer Disc.", "STRONG", ["XLY", "QQQ"]),
    "NVDA": ("Semiconductors", "STRONG", ["SMH", "SOXX", "AMD"]),
    "META": ("Communication", "STRONG", ["XLC", "GOOG"]),
    "TSLA": ("Consumer Disc.", "MODERATE", ["XLY", "RIVN"]),
    "ENEL.MI": ("Utilities", "MODERATE", ["XLU", "A2A.MI"]),
    "ENI.MI": ("Energy", "MODERATE", ["XLE", "TTE.PA"]),
    "ISP.MI": ("Financials", "MODERATE", ["XLF", "UCG.MI"]),
    "UCG.MI": ("Financials", "MODERATE", ["XLF", "ISP.MI"]),
    "STM.MI": ("Semiconductors", "MODERATE", ["SMH", "ASML.AS"]),
    "A2A.MI": ("Utilities", "MODERATE", ["XLU", "ENEL.MI"]),
    "VWCE.DE": ("Global Equity", "MODERATE", ["IWDA.AS", "SPY"]),
    "SWDA.MI": ("Global Equity", "MODERATE", ["VWCE.DE", "SPY"]),
    "^FTSEMIB": ("Italian Index", "MODERATE", ["EWI", "ISP.MI"]),
}


# ═══════════════════════════════════════════════════════════════════
# SCHEDULER
# ═══════════════════════════════════════════════════════════════════

def scheduled_cycle():
    """Ciclo schedulato: analisi + email."""
    analyses = analyze_all(use_ai=True)
    if email_engine.config.get("enabled"):
        email_engine.send_digest(analyses)
    return analyses

scheduler = Alpha360Scheduler(
    analysis_fn=scheduled_cycle,
    config={
        "enabled": options.get("scheduler_enabled", True),
        "interval_minutes": options.get("scheduler_interval_minutes", 60),
        "market_hours_only": options.get("scheduler_market_hours_only", False),
    }
)


# ═══════════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════════

@app.get("/")
async def root(request: Request):
    ingress = get_ingress_path(request)
    return FileResponse(os.path.join(webapp_dir, "index.html"))


@app.get("/api/status")
async def api_status():
    return {
        "status": "running",
        "version": "1.0.0",
        "symbols": get_symbols(),
        "scheduler": scheduler.get_status(),
        "email": email_engine.get_status(),
        "ai": {
            "claude": ai_analyzer.has_claude,
            "perplexity": ai_analyzer.has_perplexity,
        },
        "last_run": store.get_meta("last_full_run"),
        "analyses_count": store.get_meta("analyses_count"),
    }


@app.get("/api/options")
async def api_options():
    """Return safe options (no secrets)."""
    safe = {k: v for k, v in options.items()
            if k not in ("claude_api_key", "perplexity_api_key", "email_password")}
    safe["claude_configured"] = bool(options.get("claude_api_key"))
    safe["perplexity_configured"] = bool(options.get("perplexity_api_key"))
    safe["email_configured"] = bool(options.get("email_password"))
    return safe


# ─── Analysis routes ───────────────────────────────────────────────
@app.get("/api/analyses")
async def get_analyses():
    """Tutte le analisi dalla cache."""
    cached = store.get_all_analyses()
    if cached:
        return {"analyses": cached, "count": len(cached), "source": "cache",
                "last_run": store.get_meta("last_full_run")}
    # Se cache vuota, analizza ora (senza AI per velocità)
    results = analyze_all(use_ai=False)
    return {"analyses": results, "count": len(results), "source": "fresh",
            "last_run": datetime.now().isoformat()}


@app.get("/api/analyses/{symbol}")
async def get_analysis(symbol: str):
    cached = store.get_analysis(symbol)
    if cached:
        return cached
    return analyze_symbol(symbol, use_ai=True)


@app.post("/api/analyses/refresh")
async def refresh_all(use_ai: bool = Query(True)):
    results = analyze_all(use_ai=use_ai)
    return {"status": "ok", "count": len(results)}


@app.post("/api/analyses/{symbol}/refresh")
async def refresh_symbol(symbol: str):
    return analyze_symbol(symbol, use_ai=True)


# ─── Email routes ──────────────────────────────────────────────────
@app.get("/api/email/status")
async def email_status():
    return email_engine.get_status()


@app.get("/api/email/preview")
async def email_preview():
    analyses = store.get_all_analyses() or analyze_all(use_ai=False)
    return email_engine.preview(analyses)


@app.get("/api/email/preview/html")
async def email_preview_html():
    analyses = store.get_all_analyses() or analyze_all(use_ai=False)
    p = email_engine.preview(analyses)
    return HTMLResponse(content=p["html"])


@app.post("/api/email/send")
async def email_send(force: bool = Query(False)):
    analyses = store.get_all_analyses() or analyze_all(use_ai=False)
    return email_engine.send_digest(analyses, force=force)


# ─── Scheduler routes ─────────────────────────────────────────────
@app.get("/api/scheduler/status")
async def scheduler_status():
    return scheduler.get_status()


@app.post("/api/scheduler/trigger")
async def scheduler_trigger():
    return scheduler.trigger_now()


@app.post("/api/scheduler/start")
async def scheduler_start():
    scheduler.enabled = True
    scheduler.start()
    return {"status": "started"}


@app.post("/api/scheduler/stop")
async def scheduler_stop():
    scheduler.stop()
    return {"status": "stopped"}


# ─── Scoring info ─────────────────────────────────────────────────
@app.get("/api/scoring/info")
async def scoring_info():
    return scoring.get_info()


# ─── Financial Planner routes ─────────────────────────────────────
@app.get("/api/planner/pac")
async def planner_pac(
    monthly: float = Query(500), years: int = Query(20),
    rate: float = Query(7.0)
):
    """Calcolo PAC (Piano di Accumulo Capitale)."""
    return planner.compute_pac(monthly, years, rate)


@app.get("/api/planner/income")
async def planner_income(
    capital: float = Query(100000), yield_pct: float = Query(4.0),
    withdrawal_pct: float = Query(3.5)
):
    """Calcolo rendita passiva da capitale."""
    return planner.compute_income(capital, yield_pct, withdrawal_pct)


@app.get("/api/planner/retirement")
async def planner_retirement(
    current_age: int = Query(40), retire_age: int = Query(65),
    monthly_saving: float = Query(500), current_capital: float = Query(50000),
    target_monthly_income: float = Query(2000),
    growth_rate: float = Query(7.0), inflation: float = Query(2.0)
):
    """Simulazione piano pensionistico completo."""
    return planner.compute_retirement(
        current_age, retire_age, monthly_saving, current_capital,
        target_monthly_income, growth_rate, inflation
    )


@app.get("/api/planner/portfolio")
async def planner_portfolio():
    """Suggerimento allocazione portfolio basato sulle analisi correnti."""
    analyses = store.get_all_analyses() or []
    return planner.suggest_portfolio(analyses, options)


@app.post("/api/planner/full")
async def planner_full():
    """Piano finanziario completo: PAC + Income + Allocazione + Proiezione."""
    analyses = store.get_all_analyses() or analyze_all(use_ai=False)
    return planner.full_plan(analyses, options)


# ═══════════════════════════════════════════════════════════════════
# LIFECYCLE
# ═══════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup():
    logger.info("=" * 50)
    logger.info("Alpha360 starting...")
    logger.info(f"  Symbols: {get_symbols()}")
    logger.info(f"  Claude AI: {'YES' if ai_analyzer.has_claude else 'NO'}")
    logger.info(f"  Perplexity: {'YES' if ai_analyzer.has_perplexity else 'NO'}")
    logger.info(f"  Email: {'YES' if options.get('email_password') else 'NO'}")
    logger.info(f"  Scheduler: {'ON' if options.get('scheduler_enabled') else 'OFF'}")
    logger.info("=" * 50)
    scheduler.start()


@app.on_event("shutdown")
async def shutdown():
    scheduler.stop()
    logger.info("Alpha360 stopped.")


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8099,
        log_level="info",
    )
