# Alpha360 — Unified Security Analysis & Financial Planner

**Home Assistant Add-on** per analisi titoli a 360°, scoring engine, smart money tracking, piano finanziario e email digest operativi.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![HA](https://img.shields.io/badge/Home%20Assistant-Add--on-41BDF5)

## Funzionalità

### 📊 Analisi Titoli 360°
- **Scoring Engine interpretabile** con 6 componenti: Technical (±40), Macro (±15), Sector (±10), Smart Money (±15), Fundamentals (±20), Risk Penalty (-15..0)
- **Convergence Matrix**: STRONG / PARTIAL / DIVERGENT / INSUFFICIENT
- **Actionability**: HIGH / MEDIUM / LOW / DISCOVERY_ONLY
- **Form 4 insider** peso 3.5x per evento (fresh), **13F** peso 0.5x (ritardo ~45gg)
- Indicatori tecnici: RSI, MACD, ADX, MA50, MA200, Supporti/Resistenze

### 🤖 AI Enrichment
- **Claude AI**: analisi fondamentali, fattori bull/bear, trade plan
- **Perplexity**: smart money research (13F, Form 4, institutional), news

### 💰 Piano Finanziario
- **PAC** (Piano di Accumulo Capitale) con proiezione anno per anno
- **Rendita passiva** da capitale con safe withdrawal rate
- **Piano pensionistico** con fase accumulo e decumulo
- **Allocazione portfolio** suggerita basata sulle analisi
- **Simulazione completa** con target di rendita mensile

### ✉ Email Digest
- Digest operativo HTML + plain-text
- Scheduler ogni 60 minuti
- Deduplica hash-based
- Change detection (variazioni rating, convergenza)
- Gmail App Password

## Installazione

### 1. Aggiungi il repository
In Home Assistant → **Impostazioni** → **Add-on** → **Add-on Store** → **⋮** → **Repositories**

Incolla:
```
https://github.com/staracegiuseppe/alpha360
```

### 2. Installa Alpha360
Cerca "Alpha360" nello store, clicca **Installa**.

### 3. Configura
Nel tab **Configurazione** dell'add-on:

```yaml
symbols:
  - AAPL
  - MSFT
  - ENEL.MI
  - ^FTSEMIB
  - VWCE.DE
claude_api_key: "sk-ant-..."       # Opzionale: abilita analisi AI
perplexity_api_key: "pplx-..."     # Opzionale: abilita smart money
email_from: "tuamail@gmail.com"
email_password: "xxxx xxxx xxxx xxxx"  # Gmail App Password
email_to: "staracegiuseppe@gmail.com"
scheduler_enabled: true
scheduler_interval_minutes: 60
pac_monthly_amount: 500
pac_years: 20
target_monthly_income: 2000
```

### 4. Avvia
Clicca **Avvia** e poi **APRI INTERFACCIA WEB**.

## Gmail App Password

1. Vai su https://myaccount.google.com/apppasswords
2. Genera una password per "Mail" → "Altro (Alpha360)"
3. Copia la password di 16 caratteri nel campo `email_password`

## API Endpoints

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/api/status` | GET | Status generale |
| `/api/analyses` | GET | Tutte le analisi |
| `/api/analyses/{symbol}` | GET | Analisi singola |
| `/api/analyses/refresh` | POST | Forza refresh |
| `/api/planner/pac` | GET | Calcolo PAC |
| `/api/planner/income` | GET | Calcolo rendita |
| `/api/planner/retirement` | GET | Piano pensionistico |
| `/api/planner/portfolio` | GET | Allocazione suggerita |
| `/api/planner/full` | POST | Piano completo |
| `/api/email/preview` | GET | Preview email |
| `/api/email/send` | POST | Invia email |
| `/api/scheduler/trigger` | POST | Trigger manuale |

## Scoring System

```
Technical    [-40 .. +40]  → Trend, RSI, MACD, ADX, MA distance
Macro        [-15 .. +15]  → Regime, VIX, Bias
Sector       [-10 .. +10]  → Sector strength
Smart Money  [-15 .. +15]  → Form 4 (3.5x), 13F (0.5x), Cluster
Fundamentals [-20 .. +20]  → Valuation, Growth, Margins, Debt
Risk Penalty [-15 ..   0]  → Overbought, low ADX, poor data quality
─────────────────────────
Final Score  [-100 .. +100]

Rating: BUY (≥25) | SELL (≤-25) | WATCH
```

## Struttura Progetto

```
alpha360/
├── repository.yaml          # HA repository manifest
├── README.md
├── alpha360/
│   ├── config.yaml          # HA add-on config
│   ├── Dockerfile
│   ├── build.yaml
│   ├── run.sh
│   ├── requirements.txt
│   ├── server.py            # FastAPI main
│   ├── engine.py            # Scoring engine
│   ├── data_fetcher.py      # Yahoo Finance + technicals
│   ├── ai_analyzer.py       # Claude AI + Perplexity
│   ├── email_engine.py      # Email digest
│   ├── scheduler.py         # Hourly job
│   ├── financial_planner.py # PAC, income, retirement
│   ├── persistence.py       # JSON storage
│   └── webapp/
│       ├── index.html
│       ├── app.js
│       └── styles.css
```

## Supporta il progetto

Se Alpha360 ti è utile, considera una donazione:

[![PayPal](https://img.shields.io/badge/PayPal-Dona-blue?style=for-the-badge&logo=paypal)](https://www.paypal.com/donate/?business=staracegiuseppe%40gmail.com&currency_code=EUR)

## Disclaimer

Alpha360 è uno strumento di analisi e simulazione. Non costituisce consulenza finanziaria. Le decisioni di investimento sono responsabilità dell'utente. I rendimenti passati non garantiscono rendimenti futuri.

## Licenza

MIT — Giuseppe Starace
