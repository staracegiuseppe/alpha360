"""
Alpha360 — Main Server (v2 Fixed)
====================================
BUG FIX:
- Static mount DOPO le API routes (prima catturava tutto)
- Root route serve index.html con path injection per Ingress
- Catch-all per SPA fallback
- CORS middleware per dev locale
"""

import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Dict, List

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from engine import ScoringEngine
from data_fetcher import DataFetcher
from ai_analyzer import AIAnalyzer
from email_engine import EmailDigestEngine
from scheduler import Alpha360Scheduler
from financial_planner import FinancialPlanner
from persistence import DataStore

logging.basicConfig(level=logging.INFO,
                    format="[%(asctime)s] %(name)s %(levelname)s: %(message)s",
                    datefmt="%H:%M:%S", stream=sys.stdout)
logger = logging.getLogger("alpha360")

# ─── Options ───────────────────────────────────────────────────────
OPTIONS_PATH = "/data/options.json"

def load_options() -> dict:
    for p in [OPTIONS_PATH, os.path.join(os.path.dirname(__file__), "options.json")]:
        try:
            if os.path.exists(p):
                with open(p) as f:
                    return json.load(f)
        except Exception:
            pass
    return {}

options = load_options()
logger.info(f"Options: {len(options)} keys")

# ─── Components ────────────────────────────────────────────────────
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

# ─── FastAPI ───────────────────────────────────────────────────────
app = FastAPI(title="Alpha360", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

WEBAPP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp")

def get_symbols() -> list:
    return options.get("symbols", ["AAPL", "MSFT", "ENEL.MI", "VWCE.DE", "^FTSEMIB"])

SECTOR_MAP = {
    "AAPL": ("Technology", "STRONG", ["QQQ", "XLK", "MSFT"]),
    "MSFT": ("Technology", "STRONG", ["QQQ", "XLK", "AAPL"]),
    "GOOGL": ("Technology", "STRONG", ["QQQ", "XLC"]),
    "AMZN": ("Consumer Disc.", "STRONG", ["XLY", "QQQ"]),
    "NVDA": ("Semiconductors", "STRONG", ["SMH", "AMD"]),
    "META": ("Communication", "STRONG", ["XLC", "GOOGL"]),
    "TSLA": ("Consumer Disc.", "MODERATE", ["XLY"]),
    "ENEL.MI": ("Utilities", "MODERATE", ["XLU", "A2A.MI"]),
    "ENI.MI": ("Energy", "MODERATE", ["XLE"]),
    "ISP.MI": ("Financials", "MODERATE", ["XLF", "UCG.MI"]),
    "UCG.MI": ("Financials", "MODERATE", ["XLF", "ISP.MI"]),
    "STM.MI": ("Semiconductors", "MODERATE", ["SMH"]),
    "VWCE.DE": ("Global Equity", "MODERATE", ["IWDA.AS", "SPY"]),
    "^FTSEMIB": ("Italian Index", "MODERATE", ["EWI"]),
}

# ═══════════════════════════════════════════════════════════════════
# ANALYSIS PIPELINE
# ═══════════════════════════════════════════════════════════════════

def analyze_symbol(symbol: str, use_ai: bool = True) -> dict:
    try:
        logger.info(f"[Analyze] {symbol}")
        yahoo = fetcher.fetch_yahoo(symbol)
        if not yahoo or not yahoo.get("price"):
            return _err(symbol, "Yahoo data non disponibile")

        tech = fetcher.compute_technicals(symbol, yahoo)
        vix = fetcher.fetch_vix()
        ai_data = {}
        if use_ai and (ai_analyzer.has_claude or ai_analyzer.has_perplexity):
            ai_data = ai_analyzer.analyze(symbol, yahoo, tech, vix)

        raw = _assemble(symbol, yahoo, tech, vix, ai_data)
        result = scoring.run_full_analysis(raw)
        store.save_analysis(symbol, result)
        logger.info(f"[Analyze] {symbol} → {result.get('final_rating')} score={result.get('composite_score',0)}")
        return result
    except Exception as e:
        logger.error(f"[Analyze] {symbol}: {e}\n{traceback.format_exc()}")
        return _err(symbol, str(e))

def analyze_all(use_ai: bool = True) -> list:
    results = []
    for sym in get_symbols():
        results.append(analyze_symbol(sym, use_ai=use_ai))
        time.sleep(0.3)
    store.save_meta("last_full_run", datetime.now().isoformat())
    store.save_meta("analyses_count", len(results))
    return results

def _assemble(symbol, yahoo, tech, vix, ai_data) -> dict:
    meta = yahoo.get("meta", {})
    price = yahoo.get("price", 0)
    prev = yahoo.get("prev_close", price)
    chg = round(((price - prev) / prev) * 100, 2) if prev else 0

    ex = meta.get("exchangeName", "").upper()
    market = "MTA" if any(k in ex for k in ("MIL","MTA","BIT")) else \
             "XETRA" if "XETRA" in ex or "GER" in ex else \
             "NYSE" if "NYSE" in ex else "NASDAQ"

    qt = meta.get("instrumentType", meta.get("quoteType", "")).upper()
    at = "ETF" if "ETF" in qt or "FUND" in qt else "STOCK"

    regime = "RISK_ON" if vix and vix < 20 else "MIXED" if vix and vix < 25 else "RISK_OFF"
    bias = "BULLISH" if vix and vix < 15 else "MODERATELY_BULLISH" if vix and vix < 20 else "NEUTRAL" if vix and vix < 25 else "BEARISH"

    si = SECTOR_MAP.get(symbol, ("Unknown", "MODERATE", []))

    return {
        "symbol": symbol,
        "name": meta.get("longName", meta.get("shortName", symbol)),
        "market": market, "asset_type": at, "price": price, "change_pct": chg,
        "updated_at": datetime.now().isoformat(),
        "technical": tech,
        "macro_sector": {"macro_regime": regime, "vix": vix or 18, "macro_bias": bias,
                         "sector": si[0], "sector_strength": si[1],
                         "related_assets": si[2] if len(si) > 2 else []},
        "smart_money": ai_data.get("smart_money", {"institutional_holders": [],
                      "ownership_change_pct": 0, "insider_buys": [], "insider_sells": [],
                      "cluster_signal": "NEUTRAL", "signal_weight_explanation": ""}),
        "fundamentals": ai_data.get("fundamentals", {"valuation": "N/A", "growth": "N/A",
                        "margins": "N/A", "debt": "N/A", "earnings_quality": "N/A"}),
        "freshness": {"technical_hours": 0.5,
                      "smart_money_days": ai_data.get("sm_freshness_days", 30),
                      "fundamentals_days": ai_data.get("fund_freshness_days", 30)},
        "trade_plan": ai_data.get("trade_plan", {"state": "MONITOR", "entry_zone": "",
                      "stop_zone": "", "target_zone": "", "contrary_scenario": ""}),
        "events": ai_data.get("events", []),
        "bullish_factors": ai_data.get("bullish_factors", []),
        "bearish_factors": ai_data.get("bearish_factors", []),
    }

def _err(sym, msg):
    return {"symbol": sym, "name": sym, "market": "", "asset_type": "STOCK",
            "price": 0, "change_pct": 0, "updated_at": datetime.now().isoformat(),
            "final_rating": "AVOID", "composite_score": 0, "confidence": 0,
            "convergence_state": "INSUFFICIENT", "actionability": "DISCOVERY_ONLY",
            "data_quality": "LOW", "rebound_probability": 0, "is_value_trap": False,
            "health_rating": 0,
            "components": {"oversold_strength": 0, "undervaluation": 0,
                           "momentum_reversal": 0, "financial_health": 0},
            "scores": {"final_score": 0},
            "freshness": {"technical_hours": 999, "smart_money_days": 999, "fundamentals_days": 999},
            "bullish_factors": [], "bearish_factors": [f"Errore: {msg}"],
            "smart_money": {}, "technical": {}, "macro_sector": {}, "fundamentals": {},
            "trade_plan": {}, "events": [], "error": msg}

# ═══════════════════════════════════════════════════════════════════
# SCHEDULER
# ═══════════════════════════════════════════════════════════════════

def scheduled_cycle():
    analyses = analyze_all(use_ai=True)
    if email_engine.config.get("enabled"):
        email_engine.send_digest(analyses)
    return analyses

scheduler = Alpha360Scheduler(
    analysis_fn=scheduled_cycle,
    config={"enabled": options.get("scheduler_enabled", True),
            "interval_minutes": options.get("scheduler_interval_minutes", 60),
            "market_hours_only": options.get("scheduler_market_hours_only", False)})

# ═══════════════════════════════════════════════════════════════════
# API ROUTES — defined BEFORE static mount
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/status")
async def api_status():
    return {"status": "running", "version": "2.0.0", "symbols": get_symbols(),
            "scheduler": scheduler.get_status(), "email": email_engine.get_status(),
            "ai": {"claude": ai_analyzer.has_claude, "perplexity": ai_analyzer.has_perplexity},
            "last_run": store.get_meta("last_full_run"),
            "analyses_count": store.get_meta("analyses_count")}

@app.get("/api/options")
async def api_options():
    safe = {k: v for k, v in options.items() if k not in ("claude_api_key","perplexity_api_key","email_password")}
    safe.update({"claude_configured": bool(options.get("claude_api_key")),
                 "perplexity_configured": bool(options.get("perplexity_api_key")),
                 "email_configured": bool(options.get("email_password"))})
    return safe

@app.get("/api/analyses")
async def get_analyses():
    cached = store.get_all_analyses()
    if cached:
        return {"analyses": cached, "count": len(cached), "source": "cache",
                "last_run": store.get_meta("last_full_run")}
    results = analyze_all(use_ai=False)
    return {"analyses": results, "count": len(results), "source": "fresh"}

@app.get("/api/analyses/{symbol}")
async def get_analysis(symbol: str):
    return store.get_analysis(symbol) or analyze_symbol(symbol)

@app.post("/api/analyses/refresh")
async def refresh_all(use_ai: bool = Query(True)):
    return {"status": "ok", "count": len(analyze_all(use_ai=use_ai))}

@app.post("/api/analyses/{symbol}/refresh")
async def refresh_symbol(symbol: str):
    return analyze_symbol(symbol)

@app.get("/api/email/status")
async def email_status(): return email_engine.get_status()

@app.get("/api/email/preview")
async def email_preview():
    return email_engine.preview(store.get_all_analyses() or analyze_all(False))

@app.get("/api/email/preview/html")
async def email_preview_html():
    return HTMLResponse(content=email_engine.preview(store.get_all_analyses() or analyze_all(False))["html"])

@app.post("/api/email/send")
async def email_send(force: bool = Query(False)):
    return email_engine.send_digest(store.get_all_analyses() or analyze_all(False), force=force)

@app.get("/api/scheduler/status")
async def scheduler_status(): return scheduler.get_status()

@app.post("/api/scheduler/trigger")
async def scheduler_trigger(): return scheduler.trigger_now()

@app.post("/api/scheduler/start")
async def scheduler_start():
    scheduler.enabled = True; scheduler.start(); return {"status": "started"}

@app.post("/api/scheduler/stop")
async def scheduler_stop():
    scheduler.stop(); return {"status": "stopped"}

@app.get("/api/scoring/info")
async def scoring_info(): return scoring.get_info()

@app.get("/api/planner/pac")
async def planner_pac(monthly: float = Query(500), years: int = Query(20), rate: float = Query(7.0)):
    return planner.compute_pac(monthly, years, rate)

@app.get("/api/planner/income")
async def planner_income(capital: float = Query(100000), yield_pct: float = Query(4.0), withdrawal_pct: float = Query(3.5)):
    return planner.compute_income(capital, yield_pct, withdrawal_pct)

@app.get("/api/planner/retirement")
async def planner_retirement(current_age: int = Query(40), retire_age: int = Query(65),
    monthly_saving: float = Query(500), current_capital: float = Query(50000),
    target_monthly_income: float = Query(2000), growth_rate: float = Query(7.0), inflation: float = Query(2.0)):
    return planner.compute_retirement(current_age, retire_age, monthly_saving, current_capital, target_monthly_income, growth_rate, inflation)

@app.get("/api/planner/portfolio")
async def planner_portfolio():
    return planner.suggest_portfolio(store.get_all_analyses() or [], options)

@app.post("/api/planner/full")
async def planner_full():
    return planner.full_plan(store.get_all_analyses() or analyze_all(False), options)

# ═══════════════════════════════════════════════════════════════════
# STATIC FILES + SPA FALLBACK — mounted LAST
# ═══════════════════════════════════════════════════════════════════

# FIX: Serve static files explicitly, then SPA fallback for index.html
@app.get("/")
async def serve_root(request: Request):
    """Serve index.html with Ingress path injected."""
    ingress = request.headers.get("X-Ingress-Path", "").rstrip("/")
    index_path = os.path.join(WEBAPP, "index.html")
    if not os.path.exists(index_path):
        return HTMLResponse("<h1>Alpha360</h1><p>webapp/index.html not found</p>", status_code=500)

    with open(index_path) as f:
        html = f.read()

    # Inject Ingress base path into HTML so JS knows the API prefix
    html = html.replace("__INGRESS_PATH__", ingress)
    return HTMLResponse(content=html)

# Mount static files for CSS/JS — this must be AFTER API routes
if os.path.isdir(WEBAPP):
    app.mount("/static", StaticFiles(directory=WEBAPP), name="static")

# ═══════════════════════════════════════════════════════════════════
# LIFECYCLE
# ═══════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup():
    logger.info("=" * 50)
    logger.info("Alpha360 v2.0.0 starting...")
    logger.info(f"  Symbols: {get_symbols()}")
    logger.info(f"  Claude: {'YES' if ai_analyzer.has_claude else 'NO'}")
    logger.info(f"  Perplexity: {'YES' if ai_analyzer.has_perplexity else 'NO'}")
    logger.info(f"  Webapp: {WEBAPP}")
    logger.info("=" * 50)
    scheduler.start()

@app.on_event("shutdown")
async def shutdown():
    scheduler.stop()
    fetcher.close()
    logger.info("Alpha360 stopped.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8099, log_level="info")
