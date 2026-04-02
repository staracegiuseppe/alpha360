/**
 * Alpha360 — Frontend Application
 * Complete vanilla JS app for HAOS add-on.
 */

// ═══════════════════════════════════════════════════════════════════
// API LAYER
// ═══════════════════════════════════════════════════════════════════
const API = {
  _base() {
    const p = window.location.pathname.replace(/\/+$/, '');
    return (p && p !== '/') ? p : '';
  },
  async get(path) {
    const r = await fetch(this._base() + path);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },
  async post(path) {
    const r = await fetch(this._base() + path, { method: 'POST' });
    return r.json();
  },
  async getHtml(path) {
    const r = await fetch(this._base() + path);
    return r.text();
  },
};

// ═══════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════
const S = {
  analyses: [],
  selected: 0,
  loading: false,
  status: null,
  planResult: null,
};

// ═══════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════
const esc = s => String(s||'').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const pct = v => (v>=0?'+':'')+Number(v||0).toFixed(2)+'%';
const RC = r => ({BUY:'#22c55e',SELL:'#ef4444',WATCH:'#f59e0b'})[r]||'#888';
const CC = c => ({STRONG:'#22c55e',PARTIAL:'#3b82f6',DIVERGENT:'#ef4444',INSUFFICIENT:'#64748b'})[c]||'#666';
const AC = a => ({HIGH:'#22c55e',MEDIUM:'#f59e0b',LOW:'#f97316',DISCOVERY_ONLY:'#64748b'})[a]||'#666';
const QC = q => ({HIGH:'#22c55e',MEDIUM:'#f59e0b',LOW:'#ef4444'})[q]||'#666';
const CI = c => ({STRONG:'◉',PARTIAL:'◎',DIVERGENT:'⊘',INSUFFICIENT:'○'})[c]||'○';
const IC = i => ({BULLISH:'#22c55e',BEARISH:'#ef4444',NEUTRAL:'#64748b'})[i]||'#666';
const cur = a => (a.market==='MTA'||a.asset_type==='ETF')?'€':'$';

// ═══════════════════════════════════════════════════════════════════
// TAB SWITCHING
// ═══════════════════════════════════════════════════════════════════
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-content').forEach(d => d.classList.toggle('active', d.id === 'tab-' + name));
  if (name === 'analisi') renderAnalisi();
  else if (name === 'planner') renderPlanner();
  else if (name === 'email') renderEmail();
  else if (name === 'impostazioni') renderSettings();
}

// ═══════════════════════════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════════════════════════
async function init() {
  showLoading(true);
  try {
    S.status = await API.get('/api/status');
    const data = await API.get('/api/analyses');
    S.analyses = data.analyses || [];
    updateNavStatus();
  } catch(e) {
    console.error('Init error:', e);
  }
  showLoading(false);
  renderAnalisi();
}

function showLoading(show) {
  document.getElementById('loading').style.display = show ? 'flex' : 'none';
}

function updateNavStatus() {
  const el = document.getElementById('nav-status');
  if (!S.status) { el.innerHTML = ''; return; }
  const ai = S.status.ai || {};
  el.innerHTML = `
    <span class="nav-dot ${ai.claude?'green':'red'}"></span>Claude
    <span class="nav-dot ${ai.perplexity?'green':'red'}"></span>Perplexity
    <span class="nav-dot ${S.status.scheduler?.running?'green':'red'}"></span>Sched
  `;
}

// ═══════════════════════════════════════════════════════════════════
// ANALISI TAB
// ═══════════════════════════════════════════════════════════════════
function renderAnalisi() {
  const container = document.getElementById('tab-analisi');
  if (!S.analyses.length) {
    container.innerHTML = '<div class="empty-state">Nessuna analisi. <button class="btn" onclick="doRefresh()">Avvia Analisi</button></div>';
    return;
  }
  const a = S.analyses[S.selected];
  container.innerHTML = `
    <div class="a-layout">
      <div class="a-sidebar">
        <div class="a-sidebar-hdr">
          WATCHLIST (${S.analyses.length})
          <button class="btn-sm" onclick="doRefresh()" title="Refresh">↻</button>
        </div>
        ${S.analyses.map((x,i) => wlItem(x,i)).join('')}
        ${paypalWidget()}
      </div>
      <div class="a-main">${a ? dashboard(a) : ''}</div>
    </div>
  `;
}

function wlItem(a, i) {
  return `<div class="wl-item ${i===S.selected?'sel':''}" onclick="selectAsset(${i})">
    <div class="wl-bar" style="background:${RC(a.final_rating)}"></div>
    <div class="wl-info"><div class="wl-sym">${esc(a.symbol)}</div><div class="wl-name">${esc(a.name||'')}</div></div>
    <div class="wl-price"><div>${cur(a)}${a.price||0}</div><div style="color:${a.change_pct>=0?'#22c55e':'#ef4444'};font-size:11px">${pct(a.change_pct)}</div></div>
  </div>`;
}

function dashboard(a) {
  const s = a.scores||{};
  return `
    <div class="d-header">
      <div><div class="d-symbol">${esc(a.symbol)}</div><div class="d-sub">${esc(a.name)} · ${esc(a.market)} · ${esc(a.asset_type)}</div></div>
      <div class="d-price">${cur(a)}${a.price} <span style="color:${a.change_pct>=0?'#22c55e':'#ef4444'}">${pct(a.change_pct)}</span></div>
      <div class="d-badges">
        <span class="badge-rating" style="background:${RC(a.final_rating)}">${a.final_rating}</span>
        <span class="badge" style="color:${AC(a.actionability)}">${(a.actionability||'').replace(/_/g,' ')}</span>
        <span class="badge" style="color:${CC(a.convergence_state)}">${CI(a.convergence_state)} ${a.convergence_state}</span>
        <span class="badge" style="color:${QC(a.data_quality)}">● ${a.data_quality}</span>
      </div>
    </div>
    <div class="kpi-row">
      ${kpi('Score',s.final_score,s.final_score>=0?'#22c55e':'#ef4444')}
      ${kpi('Confidence',a.confidence+'%',a.confidence>=70?'#22c55e':'#f59e0b')}
      ${kpi('Tech',(a.freshness?.technical_hours||0)+'h','#06b6d4')}
      ${kpi('SM',(a.freshness?.smart_money_days||0)+'d',a.freshness?.smart_money_days<=7?'#22c55e':'#f59e0b')}
    </div>
    <div class="grid2">
      ${cardScores(s)}
      ${cardFactors(a)}
      ${cardSmartMoney(a)}
      ${cardTechnical(a)}
      ${cardMacro(a)}
      ${cardFundamentals(a)}
    </div>
    ${cardTradePlan(a)}
    ${cardEvents(a)}
  `;
}

function kpi(l,v,c) { return `<div class="kpi"><div class="kpi-label">${l}</div><div class="kpi-val" style="color:${c}">${v}</div></div>`; }

function scoreBar(label, val, min, max) {
  const range = max - min;
  const pctV = ((val-min)/range)*100;
  const zero = ((0-min)/range)*100;
  const pos = val >= 0;
  const left = pos ? zero : pctV;
  const width = Math.abs(pctV - zero);
  const color = pos ? '#22c55e' : '#ef4444';
  return `<div class="sbar"><div class="sbar-hdr"><span>${label}</span><span style="color:${color};font-weight:700">${val>0?'+':''}${val}</span></div>
    <div class="sbar-track"><div class="sbar-fill" style="left:${left}%;width:${width}%;background:${color}"></div><div class="sbar-zero" style="left:${zero}%"></div></div></div>`;
}

function cardScores(s) {
  return `<div class="card"><div class="card-title">📊 Score Breakdown</div>
    ${scoreBar('Technical',s.technical||0,-40,40)}
    ${scoreBar('Macro',s.macro||0,-15,15)}
    ${scoreBar('Sector',s.sector||0,-10,10)}
    ${scoreBar('Smart Money',s.smart_money||0,-15,15)}
    ${scoreBar('Fundamentals',s.fundamentals||0,-20,20)}
    ${scoreBar('Risk Penalty',s.risk_penalty||0,-15,0)}
  </div>`;
}

function cardFactors(a) {
  const bl = (a.bullish_factors||[]).map(f=>`<div class="factor"><span style="color:#22c55e">●</span>${esc(f)}</div>`).join('');
  const br = (a.bearish_factors||[]).map(f=>`<div class="factor"><span style="color:#ef4444">●</span>${esc(f)}</div>`).join('');
  return `<div class="card"><div class="card-title">💡 Perché Conta</div>
    <div class="factor-label" style="color:#22c55e">▲ BULLISH</div>${bl||'<div class="muted">Nessun fattore</div>'}
    <div class="factor-label" style="color:#ef4444;margin-top:10px">▼ BEARISH</div>${br||'<div class="muted">Nessun fattore</div>'}
  </div>`;
}

function cardSmartMoney(a) {
  const sm = a.smart_money||{};
  const holders = (sm.institutional_holders||[]).map(h=>
    `<div class="sm-row"><span>${esc(h.name)}</span><span class="mono">${esc(h.shares)} <span style="color:${parseFloat(h.change)>=0?'#22c55e':'#ef4444'}">${esc(h.change)}</span></span></div>`
  ).join('')||'<div class="muted">N/A</div>';

  const trades = [...(sm.insider_buys||[]).map(b=>({...b,side:'BUY'})),
    ...(sm.insider_sells||[]).map(s=>({...s,side:'SELL'}))
  ].sort((x,y)=>(y.date||'').localeCompare(x.date||'')).map(t=>
    `<div class="sm-row"><span class="sm-side" style="color:${t.side==='BUY'?'#22c55e':'#ef4444'}">${t.side}</span>
    <span>${esc(t.name)}</span><span class="mono">${esc(t.amount)}</span><span class="muted">${esc(t.date)}</span></div>`
  ).join('')||'<div class="muted">Nessuna attività</div>';

  return `<div class="card"><div class="card-title">🏦 Smart Money</div>
    <div class="sm-label">INSTITUTIONAL (13F — peso 0.5x)</div>${holders}
    <div class="sm-label" style="margin-top:10px">INSIDER (Form 4 — peso 3.5x)</div>${trades}
    <div class="sm-explain">CLUSTER: <span style="color:${sm.cluster_signal==='STRONG_BUY'?'#22c55e':sm.cluster_signal==='STRONG_SELL'?'#ef4444':'#94a3b8'}">${esc(sm.cluster_signal||'N/A')}</span><br>${esc(sm.signal_weight_explanation||'')}</div>
  </div>`;
}

function cardTechnical(a) {
  const t = a.technical||{};
  const tc = v => v==='UPTREND'?'#22c55e':v==='DOWNTREND'?'#ef4444':'#f59e0b';
  return `<div class="card"><div class="card-title">📈 Tecnica</div>
    <div class="tech-grid">
      ${techBox('Trend',t.trend,tc(t.trend))}${techBox('RSI',t.rsi,t.rsi>70?'#ef4444':t.rsi<30?'#22c55e':'#e2e8f0')}
      ${techBox('MACD',t.macd,(t.macd||'').includes('BULL')?'#22c55e':'#ef4444')}${techBox('ADX',t.adx,t.adx>25?'#22c55e':'#64748b')}
    </div>
    <div class="tech-grid" style="margin-top:6px">
      ${techBox('MA50',pct(t.ma50_distance_pct),t.ma50_distance_pct>=0?'#22c55e':'#ef4444')}
      ${techBox('MA200',pct(t.ma200_distance_pct),t.ma200_distance_pct>=0?'#22c55e':'#ef4444')}
    </div>
    <div class="sr-row"><span>S: <b style="color:#22c55e">${t.support||'—'}</b></span><span>R: <b style="color:#ef4444">${t.resistance||'—'}</b></span></div>
    <div class="tech-state">${esc(t.technical_state||'')}</div>
  </div>`;
}

function techBox(l,v,c) { return `<div class="tbox"><div class="tbox-l">${l}</div><div class="tbox-v" style="color:${c}">${esc(v)}</div></div>`; }

function cardMacro(a) {
  const m = a.macro_sector||{};
  const tags = (m.related_assets||[]).map(r=>`<span class="tag">${esc(r)}</span>`).join('');
  return `<div class="card"><div class="card-title">🌍 Macro & Settore</div>
    <div class="tech-grid">
      ${techBox('Regime',m.macro_regime,m.macro_regime==='RISK_ON'?'#22c55e':'#ef4444')}
      ${techBox('VIX',m.vix,m.vix<15?'#22c55e':m.vix<20?'#f59e0b':'#ef4444')}
      ${techBox('Bias',m.macro_bias,'#3b82f6')}
      ${techBox('Settore',m.sector_strength,m.sector_strength==='STRONG'?'#22c55e':'#f59e0b')}
    </div>
    <div class="tags-row">${esc(m.sector||'')} ${tags}</div>
  </div>`;
}

function cardFundamentals(a) {
  const f = a.fundamentals||{};
  const rows = Object.entries(f).map(([k,v])=>`<div class="fund-row"><span>${esc(k.replace(/_/g,' '))}</span><span>${esc(v)}</span></div>`).join('');
  return `<div class="card"><div class="card-title">📋 Fondamentali</div>${rows||'<div class="muted">N/A</div>'}</div>`;
}

function cardTradePlan(a) {
  const tp = a.trade_plan||{};
  const sc = tp.state==='ACTIONABLE_NOW'?'#22c55e':tp.state==='MONITOR'?'#f59e0b':'#64748b';
  return `<div class="card card-full" style="border-top:2px solid ${sc}"><div class="card-title">🎯 Piano Operativo</div>
    <div class="plan-state" style="color:${sc}">${esc((tp.state||'').replace(/_/g,' '))}</div>
    <div class="plan-grid">
      <div class="plan-box"><div class="plan-label">ENTRY</div><div style="color:#3b82f6">${esc(tp.entry_zone||'—')}</div></div>
      <div class="plan-box"><div class="plan-label">STOP</div><div style="color:#ef4444">${esc(tp.stop_zone||'—')}</div></div>
      <div class="plan-box"><div class="plan-label">TARGET</div><div style="color:#22c55e">${esc(tp.target_zone||'—')}</div></div>
    </div>
    ${tp.contrary_scenario?`<div class="contrary">⚠ ${esc(tp.contrary_scenario)}</div>`:''}
  </div>`;
}

function cardEvents(a) {
  const evs = (a.events||[]).sort((x,y)=>(y.date||'').localeCompare(x.date||'')).map(e=>
    `<div class="ev-row"><span class="ev-icon">${{INSIDER:'👤',EARNINGS:'📊',TECHNICAL:'📈',NEWS:'📰',FILING:'📄'}[e.type]||'•'}</span>
    <span class="ev-date">${esc(e.date)}</span><span class="ev-desc">${esc(e.desc)}</span>
    <span style="color:${IC(e.impact)};font-size:10px;font-weight:700">${esc(e.impact)}</span></div>`
  ).join('');
  return `<div class="card card-full"><div class="card-title">📅 Timeline</div>${evs||'<div class="muted">Nessun evento</div>'}</div>`;
}

// ═══════════════════════════════════════════════════════════════════
// PLANNER TAB
// ═══════════════════════════════════════════════════════════════════
async function renderPlanner() {
  const container = document.getElementById('tab-planner');
  container.innerHTML = `
    <div class="plan-page">
      <h2>💰 Piano Finanziario</h2>
      <p class="muted">Calcola PAC, rendita e piano pensionistico integrato con le analisi dei titoli.</p>

      <div class="plan-controls">
        <div class="plan-input"><label>Versamento mensile €</label><input type="number" id="pl-monthly" value="500" min="50" step="50"></div>
        <div class="plan-input"><label>Anni accumulo</label><input type="number" id="pl-years" value="20" min="1" max="50"></div>
        <div class="plan-input"><label>Rendimento annuo %</label><input type="number" id="pl-rate" value="7" min="1" max="20" step="0.5"></div>
        <div class="plan-input"><label>Rendita mensile target €</label><input type="number" id="pl-target" value="2000" min="100" step="100"></div>
        <button class="btn btn-green" onclick="runPlan()">🚀 Calcola Piano Completo</button>
        <button class="btn" onclick="runPlanAI()">🤖 Piano con AI</button>
      </div>

      <div id="plan-results"></div>
    </div>
  `;
}

async function runPlan() {
  const monthly = document.getElementById('pl-monthly').value;
  const years = document.getElementById('pl-years').value;
  const rate = document.getElementById('pl-rate').value;
  const target = document.getElementById('pl-target').value;

  document.getElementById('plan-results').innerHTML = '<div class="loading-text">Calcolo in corso...</div>';

  try {
    const [pac, income, retire, portfolio] = await Promise.all([
      API.get(`/api/planner/pac?monthly=${monthly}&years=${years}&rate=${rate}`),
      API.get(`/api/planner/income?capital=100000&yield_pct=4&withdrawal_pct=3.5`),
      API.get(`/api/planner/retirement?current_age=40&retire_age=65&monthly_saving=${monthly}&current_capital=0&target_monthly_income=${target}&growth_rate=${rate}&inflation=2`),
      API.get('/api/planner/portfolio'),
    ]);

    // Aggiorna income con il capitale del PAC
    const incomeReal = await API.get(`/api/planner/income?capital=${pac.future_value}&yield_pct=4&withdrawal_pct=3.5`);

    document.getElementById('plan-results').innerHTML = `
      ${planSummaryCard(pac, incomeReal, retire, target)}
      ${pacCard(pac)}
      ${incomeCard(incomeReal)}
      ${retirementCard(retire)}
      ${portfolioCard(portfolio)}
      ${paypalWidget()}
    `;
  } catch(e) {
    document.getElementById('plan-results').innerHTML = `<div class="error">Errore: ${e.message}</div>`;
  }
}

async function runPlanAI() {
  document.getElementById('plan-results').innerHTML = '<div class="loading-text">🤖 Generazione piano AI completo...</div>';
  try {
    const plan = await API.post('/api/planner/full');
    const s = plan.summary||{};
    document.getElementById('plan-results').innerHTML = `
      <div class="card card-full" style="border-top:2px solid #818cf8">
        <div class="card-title">🤖 Piano Finanziario AI</div>
        <div class="kpi-row">
          ${kpi('Capitale Finale','€'+fmt(s.pac_final_capital),'#22c55e')}
          ${kpi('Rendita Mensile','€'+fmt(s.achievable_monthly_income),'#06b6d4')}
          ${kpi('Target','€'+fmt(s.target_monthly_income), s.is_target_achievable?'#22c55e':'#ef4444')}
          ${kpi('Gap','€'+fmt(s.gap_to_target), s.gap_to_target<=0?'#22c55e':'#ef4444')}
        </div>
        <div style="margin-top:12px;color:${s.is_target_achievable?'#22c55e':'#f59e0b'};font-weight:700">
          ${s.is_target_achievable?'✅ Target raggiungibile!':'⚠ Gap da colmare — aumenta versamento o periodo'}
        </div>
      </div>
      ${pacCard(plan.pac)}
      ${incomeCard(plan.income)}
      ${retirementCard(plan.retirement)}
      ${portfolioCard(plan.portfolio)}
    `;
  } catch(e) {
    document.getElementById('plan-results').innerHTML = `<div class="error">Errore: ${e.message}</div>`;
  }
}

function fmt(n) { return Number(n||0).toLocaleString('it-IT', {maximumFractionDigits:0}); }

function planSummaryCard(pac, income, retire, target) {
  const achievable = income.safe_monthly_withdrawal >= target;
  return `<div class="card card-full" style="border-top:2px solid ${achievable?'#22c55e':'#f59e0b'}">
    <div class="card-title">📊 Riepilogo Piano</div>
    <div class="kpi-row">
      ${kpi('Investito','€'+fmt(pac.total_invested),'#94a3b8')}
      ${kpi('Capitale Finale','€'+fmt(pac.future_value),'#22c55e')}
      ${kpi('Rendimento','+'+pac.gain_pct+'%','#06b6d4')}
      ${kpi('Rendita Mensile (3.5%)','€'+fmt(income.safe_monthly_withdrawal), achievable?'#22c55e':'#ef4444')}
    </div>
    <div style="margin:12px 0;font-weight:700;color:${achievable?'#22c55e':'#f59e0b'}">
      ${achievable?`✅ Con €${fmt(pac.future_value)} generi €${fmt(income.safe_monthly_withdrawal)}/mese — target raggiunto!`
        :`⚠ Rendita €${fmt(income.safe_monthly_withdrawal)}/mese vs target €${target}/mese — gap €${fmt(target - income.safe_monthly_withdrawal)}`}
    </div>
  </div>`;
}

function pacCard(pac) {
  const rows = (pac.yearly_projection||[]).filter((_,i)=>i%2===1||i===pac.yearly_projection.length-1).map(y=>
    `<div class="plan-row"><span>Anno ${y.year}</span><span>€${fmt(y.invested)}</span><span style="color:#22c55e">€${fmt(y.balance)}</span><span style="color:#06b6d4">+€${fmt(y.gain)}</span></div>`
  ).join('');
  return `<div class="card card-full"><div class="card-title">📈 PAC — Piano di Accumulo</div>
    <div class="plan-hdr"><span>Anno</span><span>Investito</span><span>Valore</span><span>Guadagno</span></div>
    ${rows}
  </div>`;
}

function incomeCard(inc) {
  return `<div class="card card-full"><div class="card-title">💸 Rendita Passiva dal Capitale</div>
    <div class="kpi-row">
      ${kpi('Capitale','€'+fmt(inc.capital),'#f1f5f9')}
      ${kpi('Dividendo/anno','€'+fmt(inc.annual_dividend_income),'#22c55e')}
      ${kpi('Prelievo sicuro/mese','€'+fmt(inc.safe_monthly_withdrawal),'#06b6d4')}
      ${kpi('Sostenibilità',inc.years_sustainable+'+ anni',inc.years_sustainable>=30?'#22c55e':'#f59e0b')}
    </div>
  </div>`;
}

function retirementCard(ret) {
  return `<div class="card card-full"><div class="card-title">🏖 Piano Pensionistico</div>
    <div class="kpi-row">
      ${kpi('Capitale a pensione','€'+fmt(ret.capital_at_retirement),'#22c55e')}
      ${kpi('Rendita target','€'+fmt(ret.target_income_inflation_adjusted)+'/m','#06b6d4')}
      ${kpi('Withdrawal rate',ret.withdrawal_rate_pct+'%',ret.withdrawal_rate_pct<=4?'#22c55e':'#ef4444')}
      ${kpi('Sostenibile?',ret.is_sustainable?'SÌ':'NO',ret.is_sustainable?'#22c55e':'#ef4444')}
    </div>
    ${!ret.is_sustainable?`<div style="margin-top:10px;color:#f59e0b">⚠ Per sostenibilità servono €${fmt(ret.extra_monthly_needed)}/mese in più</div>`:''}
  </div>`;
}

function portfolioCard(p) {
  if (!p || !p.allocations) return '';
  const rows = (p.allocations||[]).map(a=>{
    const c = a.action==='ACCUMULA'?'#22c55e':a.action==='POSIZIONA'?'#3b82f6':a.action==='MONITORA'?'#f59e0b':'#64748b';
    return `<div class="alloc-row">
      <span class="alloc-sym">${esc(a.symbol)}</span>
      <span style="color:${c};font-size:11px;font-weight:700">${esc(a.action)}</span>
      <span class="mono">${a.suggested_weight_pct}%</span>
      <span class="muted">${esc(a.entry||'')}</span>
    </div>`;
  }).join('');

  const s = p.summary||{};
  return `<div class="card card-full"><div class="card-title">📊 Allocazione Portfolio Suggerita</div>
    <div class="kpi-row">
      ${kpi('Posizioni',s.total_positions||0,'#22c55e')}
      ${kpi('Watch',s.watch_list||0,'#f59e0b')}
      ${kpi('Cash',s.cash_pct+'%','#94a3b8')}
      ${kpi('Rischio',s.risk_level||'',s.risk_level==='AGGRESSIVO'?'#ef4444':'#22c55e')}
    </div>
    <div class="alloc-hdr"><span>TITOLO</span><span>AZIONE</span><span>PESO</span><span>ENTRY</span></div>
    ${rows}
    ${(p.sells_to_avoid||[]).length?`<div style="margin-top:10px;color:#ef4444;font-size:12px">⛔ EVITA: ${p.sells_to_avoid.map(s=>s.symbol).join(', ')}</div>`:''}
  </div>`;
}

// ═══════════════════════════════════════════════════════════════════
// EMAIL TAB
// ═══════════════════════════════════════════════════════════════════
async function renderEmail() {
  const container = document.getElementById('tab-email');
  let status = {};
  try { status = await API.get('/api/email/status'); } catch(e) {}

  container.innerHTML = `
    <div class="email-page">
      <h2>✉ Email Digest</h2>
      <div class="email-actions">
        <button class="btn btn-green" onclick="sendEmail(false)">Invia Ora</button>
        <button class="btn" onclick="sendEmail(true)">Forza Invio</button>
        <button class="btn" onclick="previewEmail()">Preview HTML</button>
      </div>
      <div class="kpi-row" style="margin:16px 0">
        ${kpi('Status',status.enabled?'ON':'OFF',status.enabled?'#22c55e':'#ef4444')}
        ${kpi('Invii',status.send_count||0,'#06b6d4')}
        ${kpi('Errori',status.error_count||0,status.error_count?'#ef4444':'#22c55e')}
        ${kpi('Ultimo',status.last_sent?new Date(status.last_sent).toLocaleString('it-IT'):'Mai','#94a3b8')}
      </div>
      <div id="email-preview-box"></div>
    </div>
  `;
}

async function sendEmail(force) {
  try {
    const r = await API.post(`/api/email/send?force=${force}`);
    alert(r.status==='sent'?'✅ Inviata!':r.status+': '+(r.reason||r.error||''));
    renderEmail();
  } catch(e) { alert('Errore: '+e.message); }
}

async function previewEmail() {
  try {
    const html = await API.getHtml('/api/email/preview/html');
    document.getElementById('email-preview-box').innerHTML = `<div class="card card-full"><div class="card-title">Preview</div><div class="email-preview">${html}</div></div>`;
  } catch(e) { alert('Errore: '+e.message); }
}

// ═══════════════════════════════════════════════════════════════════
// SETTINGS TAB
// ═══════════════════════════════════════════════════════════════════
async function renderSettings() {
  const container = document.getElementById('tab-impostazioni');
  let opts = {}, sched = {}, scoring = {};
  try {
    [opts, sched, scoring] = await Promise.all([
      API.get('/api/options'),
      API.get('/api/scheduler/status'),
      API.get('/api/scoring/info'),
    ]);
  } catch(e) {}

  container.innerHTML = `
    <div class="settings-page">
      <h2>⚙ Configurazione</h2>

      <div class="card card-full"><div class="card-title">📡 API Status</div>
        <div class="cfg-row"><span>Claude AI</span><span style="color:${opts.claude_configured?'#22c55e':'#ef4444'}">${opts.claude_configured?'✅ Configurato':'❌ Non configurato'}</span></div>
        <div class="cfg-row"><span>Perplexity</span><span style="color:${opts.perplexity_configured?'#22c55e':'#ef4444'}">${opts.perplexity_configured?'✅ Configurato':'❌ Non configurato'}</span></div>
        <div class="cfg-row"><span>Email SMTP</span><span style="color:${opts.email_configured?'#22c55e':'#ef4444'}">${opts.email_configured?'✅ Configurato':'❌ Non configurato'}</span></div>
        <div class="cfg-row"><span>Destinatario</span><span>${esc(opts.email_to||'')}</span></div>
        <div class="cfg-row"><span>Simboli</span><span>${(opts.symbols||[]).join(', ')}</span></div>
      </div>

      <div class="card card-full"><div class="card-title">📬 Scheduler</div>
        <div class="kpi-row">
          ${kpi('Status',sched.running?'RUNNING':'STOPPED',sched.running?'#22c55e':'#ef4444')}
          ${kpi('Intervallo',(sched.interval_minutes||60)+'min','#06b6d4')}
          ${kpi('Cicli',sched.run_count||0,'#94a3b8')}
          ${kpi('Errori',sched.error_count||0,sched.error_count?'#ef4444':'#22c55e')}
        </div>
        <div class="email-actions" style="margin-top:12px">
          <button class="btn btn-green" onclick="schedStart()">▶ Avvia</button>
          <button class="btn" style="color:#ef4444" onclick="schedStop()">⏸ Pausa</button>
          <button class="btn" onclick="schedTrigger()">⚡ Trigger Ora</button>
        </div>
      </div>

      <div class="card card-full"><div class="card-title">⚖ Score Ranges</div>
        ${Object.entries(scoring.score_ranges||{}).map(([k,v])=>
          `<div class="cfg-row"><span>${k}</span><span>[${v[0]}, ${v[1]}]</span></div>`
        ).join('')}
        <div class="muted" style="margin-top:8px">Form 4: 3.5x per evento | 13F: 0.5x (ritardo ~45gg) | SM non ribalta tech debole</div>
      </div>

      <div class="card card-full"><div class="card-title">🧭 Convergenza</div>
        ${Object.entries(scoring.convergence_matrix||{}).map(([k,v])=>
          `<div class="cfg-row"><span style="color:${CC(k)};font-weight:700">${k}</span><span>${esc(v)}</span></div>`
        ).join('')}
      </div>

      ${paypalWidget()}
    </div>
  `;
}

async function schedStart() { await API.post('/api/scheduler/start'); renderSettings(); }
async function schedStop() { await API.post('/api/scheduler/stop'); renderSettings(); }
async function schedTrigger() {
  const r = await API.post('/api/scheduler/trigger');
  alert('Ciclo: ' + (r.status||'') + ' — ' + (r.count||0) + ' titoli');
  renderSettings();
}

// ═══════════════════════════════════════════════════════════════════
// PAYPAL WIDGET
// ═══════════════════════════════════════════════════════════════════
function paypalWidget() {
  return `<div class="paypal-box">
    <a href="https://www.paypal.com/donate/?business=staracegiuseppe%40gmail.com&currency_code=EUR"
       target="_blank" rel="noopener noreferrer" class="paypal-btn">
       💙 Supporta Alpha360 — Dona con PayPal
    </a>
  </div>`;
}

// ═══════════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════════
function selectAsset(i) { S.selected = i; renderAnalisi(); }

async function doRefresh() {
  showLoading(true);
  try {
    await API.post('/api/analyses/refresh?use_ai=true');
    const data = await API.get('/api/analyses');
    S.analyses = data.analyses || [];
  } catch(e) { alert('Errore refresh: '+e.message); }
  showLoading(false);
  renderAnalisi();
}

// ═══════════════════════════════════════════════════════════════════
// BOOT
// ═══════════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', init);
