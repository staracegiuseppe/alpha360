"""
Alpha360 — AI Analyzer
========================
Claude AI: analisi fondamentali, fattori bull/bear, trade plan, scoring validation.
Perplexity: smart money research (13F, Form 4, institutional), news sentiment.

Entrambi opzionali — l'app funziona anche senza API key, con dati ridotti.
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, Optional

import httpx

logger = logging.getLogger("alpha360.ai")

CLAUDE_URL = "https://api.anthropic.com/v1/messages"
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


class AIAnalyzer:

    def __init__(self, claude_api_key: str = "", perplexity_api_key: str = ""):
        self.claude_key = claude_api_key.strip()
        self.perplexity_key = perplexity_api_key.strip()
        self._cache: Dict[str, dict] = {}
        self._cache_ts: Dict[str, float] = {}
        self.CACHE_TTL = 3600  # 1 ora

    @property
    def has_claude(self) -> bool:
        return bool(self.claude_key)

    @property
    def has_perplexity(self) -> bool:
        return bool(self.perplexity_key)

    def analyze(self, symbol: str, yahoo: dict, tech: dict, vix: float) -> dict:
        """
        Analisi AI completa per un simbolo.
        1. Perplexity: smart money + news
        2. Claude: fondamentali + bullish/bearish + trade plan
        Ritorna dict con tutti i campi AI-enriched.
        """
        # Cache check
        cache_key = f"{symbol}:{datetime.now().strftime('%Y%m%d%H')}"
        if cache_key in self._cache:
            logger.info(f"[AI] {symbol} — cache hit")
            return self._cache[cache_key]

        result = {}
        price = yahoo.get("price", 0)

        # 1. Perplexity: smart money research
        if self.has_perplexity:
            try:
                sm = self._perplexity_smart_money(symbol, price)
                result.update(sm)
            except Exception as e:
                logger.error(f"[AI/Perplexity] {symbol}: {e}")

        # 2. Claude: full analysis
        if self.has_claude:
            try:
                claude = self._claude_analysis(symbol, price, tech, vix,
                                               result.get("smart_money", {}))
                result.update(claude)
            except Exception as e:
                logger.error(f"[AI/Claude] {symbol}: {e}")

        self._cache[cache_key] = result
        return result

    # ─── PERPLEXITY: Smart Money Research ──────────────────────────
    def _perplexity_smart_money(self, symbol: str, price: float) -> dict:
        """Cerca dati istituzionali, insider, 13F via Perplexity."""
        prompt = f"""Analizza i dati smart money per il titolo {symbol} (prezzo attuale: {price}).

Rispondi SOLO in formato JSON valido con questa struttura esatta:
{{
  "smart_money": {{
    "institutional_holders": [
      {{"name": "...", "shares": "...", "change": "...", "filing": "13F QX YYYY"}}
    ],
    "ownership_change_pct": 0.0,
    "insider_buys": [
      {{"name": "...", "role": "...", "amount": "...", "date": "YYYY-MM-DD", "form": "Form 4"}}
    ],
    "insider_sells": [
      {{"name": "...", "role": "...", "amount": "...", "date": "YYYY-MM-DD", "form": "Form 4"}}
    ],
    "cluster_signal": "STRONG_BUY|MODERATE_BUY|NEUTRAL|MODERATE_SELL|STRONG_SELL",
    "signal_weight_explanation": "..."
  }},
  "sm_freshness_days": 0,
  "events": [
    {{"date": "YYYY-MM-DD", "type": "INSIDER|FILING|NEWS", "desc": "...", "impact": "BULLISH|BEARISH|NEUTRAL"}}
  ]
}}

Cerca dati reali e recenti. Se il titolo è europeo/italiano, usa dati Consob. 
Se non trovi dati, indica cluster_signal come "NEUTRAL" e spiega il motivo."""

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    PERPLEXITY_URL,
                    headers={
                        "Authorization": f"Bearer {self.perplexity_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "sonar",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 2000,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                # Parse JSON from response
                return self._parse_json_response(content)
        except Exception as e:
            logger.error(f"[Perplexity] {symbol}: {e}")
            return {}

    # ─── CLAUDE: Full Analysis ─────────────────────────────────────
    def _claude_analysis(self, symbol: str, price: float, tech: dict,
                         vix: float, smart_money: dict) -> dict:
        """Analisi completa con Claude AI."""
        prompt = f"""Sei un analista finanziario quantitativo. Analizza il titolo {symbol}.

DATI ATTUALI:
- Prezzo: {price}
- RSI: {tech.get('rsi', 'N/A')}
- MACD: {tech.get('macd', 'N/A')}
- ADX: {tech.get('adx', 'N/A')}
- Trend: {tech.get('trend', 'N/A')}
- MA50 dist: {tech.get('ma50_distance_pct', 'N/A')}%
- MA200 dist: {tech.get('ma200_distance_pct', 'N/A')}%
- Support: {tech.get('support', 'N/A')}
- Resistance: {tech.get('resistance', 'N/A')}
- VIX: {vix}
- Smart Money insider buys: {len(smart_money.get('insider_buys', []))}
- Smart Money insider sells: {len(smart_money.get('insider_sells', []))}

Rispondi SOLO in formato JSON valido:
{{
  "fundamentals": {{
    "valuation": "ATTRACTIVE|FAIR|FAIR_TO_RICH|RICH (breve spiegazione)",
    "growth": "STRONG|SOLID|MODERATE|STABLE|DECLINING (breve spiegazione)",
    "margins": "EXPANDING|STABLE|CONTRACTING (breve spiegazione)",
    "debt": "NONE|LOW|MODERATE|HIGH|CRITICAL (breve spiegazione)",
    "earnings_quality": "HIGH|GOOD|MODERATE|LOW (breve spiegazione)"
  }},
  "fund_freshness_days": 15,
  "bullish_factors": [
    "Fattore 1 specifico e concreto",
    "Fattore 2 specifico e concreto",
    "Fattore 3 specifico e concreto"
  ],
  "bearish_factors": [
    "Fattore 1 specifico e concreto",
    "Fattore 2 specifico e concreto",
    "Fattore 3 specifico e concreto"
  ],
  "trade_plan": {{
    "state": "ACTIONABLE_NOW|MONITOR|DISCOVERY_ONLY|AVOID",
    "entry_zone": "prezzo1 - prezzo2 (motivazione)",
    "stop_zone": "prezzo (motivazione)",
    "target_zone": "prezzo1 - prezzo2 (motivazione)",
    "contrary_scenario": "Descrizione scenario contrario"
  }}
}}

Sii specifico con numeri e livelli di prezzo. Basa i fattori sui dati forniti.
Per titoli EU/IT, usa metriche e riferimenti europei."""

        try:
            with httpx.Client(timeout=45) as client:
                resp = client.post(
                    CLAUDE_URL,
                    headers={
                        "x-api-key": self.claude_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 2000,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = ""
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        content += block.get("text", "")
                return self._parse_json_response(content)
        except Exception as e:
            logger.error(f"[Claude] {symbol}: {e}")
            return {}

    # ─── JSON Parser ───────────────────────────────────────────────
    def _parse_json_response(self, text: str) -> dict:
        """Estrai JSON dalla risposta AI, gestendo markdown fences."""
        text = text.strip()
        # Remove markdown code fences
        if "```json" in text:
            text = text.split("```json", 1)[1]
            if "```" in text:
                text = text.split("```", 1)[0]
        elif "```" in text:
            parts = text.split("```")
            if len(parts) >= 2:
                text = parts[1]

        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"[AI] JSON parse error: {e} — text: {text[:200]}")
            return {}
