/**
 * Alpha360 — Frontend v2
 * FIX: API base path from server-injected __INGRESS_PATH__ (not guessed)
 * FIX: Event delegation instead of inline onclick in innerHTML
 * FIX: Error boundaries on all API calls
 * NEW: Composite score radar, rebound probability, value trap badge
 */

// ─── API (FIX: uses server-injected base path) ───────────────────
const API = {
  base: window.__API_BASE__ || '',
  async get(p) {
    try {
      const r = await fetch(this.base + p);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    } catch(e) { console.error(`GET ${p}:`, e); throw e; }
  },
  async post(p) {
    try {
      const r = await fetch(this.base + p, {method:'POST'});
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    } catch(e) { console.error(`POST ${p}:`, e); throw e; }
  },
  async html(p) {
    const r = await fetch(this.base + p);
    return r.text();
  },
};

// ─── State ────────────────────────────────────────────────────────
const S = { analyses: [], sel: 0, status: null };

// ─── Helpers ──────────────────────────────────────────────────────
const h = s => String(s||'').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const pf = v => (v>=0?'+':'')+Number(v||0).toFixed(2)+'%';
const fmt = n => Number(n||0).toLocaleString('it-IT',{maximumFractionDigits:0});
const RC = r=>({BUY:'#22c55e',SELL:'#ef4444',WATCH:'#f59e0b',AVOID:'#ef4444'})[r]||'#888';
const CC = c=>({STRONG:'#22c55e',PARTIAL:'#3b82f6',DIVERGENT:'#ef4444',INSUFFICIENT:'#64748b'})[c]||'#666';
const AC = a=>({HIGH:'#22c55e',MEDIUM:'#f59e0b',LOW:'#f97316',DISCOVERY_ONLY:'#64748b'})[a]||'#666';
const cur = a => (a.market==='MTA'||a.asset_type==='ETF')?'€':'$';

// ─── Event Delegation (FIX: no inline onclick in innerHTML) ──────
document.addEventListener('click', e => {
  const t = e.target.closest('[data-action]');
  if (!t) return;
  const action = t.dataset.action;
  const param = t.dataset.param;

  switch(action) {
    case 'select': S.sel = parseInt(param); renderAnalisi(); break;
    case 'refresh': doRefresh(); break;
    case 'tab': switchTab(param); break;
    case 'run-plan': runPlan(); break;
    case 'run-plan-ai': runPlanAI(); break;
    case 'email-send': sendEmail(false); break;
    case 'email-force': sendEmail(true); break;
    case 'email-preview': previewEmail(); break;
    case 'sched-start': schedCtrl('start'); break;
    case 'sched-stop': schedCtrl('stop'); break;
    case 'sched-trigger': schedCtrl('trigger'); break;
  }
});

// Tab switching via delegation
document.getElementById('nav-tabs').addEventListener('click', e => {
  const btn = e.target.closest('.tab-btn');
  if (!btn) return;
  switchTab(btn.dataset.tab);
});

function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab===name));
  document.querySelectorAll('.tab-content').forEach(d => d.classList.toggle('active', d.id==='tab-'+name));
  if (name==='analisi') renderAnalisi();
  else if (name==='planner') renderPlanner();
  else if (name==='email') renderEmail();
  else if (name==='config') renderConfig();
}

// ─── Init ─────────────────────────────────────────────────────────
async function init() {
  showLoad(true);
  try {
    S.status = await API.get('/api/status');
    const d = await API.get('/api/analyses');
    S.analyses = d.analyses || [];
    updNav();
  } catch(e) {
    console.error('Init:', e);
    document.getElementById('tab-analisi').innerHTML =
      `<div class="empty">❌ Errore connessione al server<br><small>${h(e.message)}</small><br><button class="btn" data-action="refresh">Riprova</button></div>`;
  }
  showLoad(false);
  renderAnalisi();
}

function showLoad(s) { document.getElementById('loading').style.display = s?'flex':'none'; }
function updNav() {
  const el = document.getElementById('nav-status');
  if (!S.status) return;
  const ai = S.status.ai||{};
  el.innerHTML = `<span class="dot ${ai.claude?'on':''}"></span>Claude <span class="dot ${ai.perplexity?'on':''}"></span>Perp <span class="dot ${S.status.scheduler?.running?'on':''}"></span>Sched`;
}

// ═══════════════════════════════════════════════════════════════════
// ANALISI TAB
// ═══════════════════════════════════════════════════════════════════
function renderAnalisi() {
  const c = document.getElementById('tab-analisi');
  if (!S.analyses.length) {
    c.innerHTML = '<div class="empty">Nessuna analisi disponibile.<br><button class="btn" data-action="refresh">🚀 Avvia Prima Analisi</button></div>';
    return;
  }
  const a = S.analyses[S.sel];
  c.innerHTML = `<div class="layout">
    <div class="sidebar">
      <div class="sb-hdr">WATCHLIST (${S.analyses.length}) <button class="btn-xs" data-action="refresh">↻</button></div>
      ${S.analyses.map((x,i)=> wlItem(x,i)).join('')}
      <div class="pp-box"><a href="https://www.paypal.com/donate/?business=staracegiuseppe%40gmail.com&currency_code=EUR" target="_blank" class="pp-btn">💙 Dona con PayPal</a></div>
    </div>
    <div class="main">${a ? dash(a) : ''}</div>
  </div>`;
}

function wlItem(a,i) {
  return `<div class="wl ${i===S.sel?'sel':''}" data-action="select" data-param="${i}">
    <div class="wl-bar" style="background:${RC(a.final_rating)}"></div>
    <div class="wl-info"><div class="wl-sym">${h(a.symbol)}</div><div class="wl-nm">${h((a.name||'').substring(0,20))}</div></div>
    <div class="wl-px"><div>${cur(a)}${a.price||0}</div><div style="color:${a.change_pct>=0?'#22c55e':'#ef4444'};font-size:10px">${pf(a.change_pct)}</div></div>
  </div>`;
}

function dash(a) {
  const sc = a.composite_score || a.scores?.final_score || 0;
  const comp = a.components || {};
  return `
    <div class="d-hdr">
      <div><div class="d-sym">${h(a.symbol)}</div><div class="d-sub">${h(a.name)} · ${h(a.market)} · ${h(a.asset_type)}</div></div>
      <div class="d-px">${cur(a)}${a.price} <span style="color:${a.change_pct>=0?'#22c55e':'#ef4444'}">${pf(a.change_pct)}</span></div>
    </div>
    <div class="d-badges">
      <span class="bdg-rt" style="background:${RC(a.final_rating)}">${a.final_rating}</span>
      <span class="bdg" style="color:${AC(a.actionability)}">${(a.actionability||'').replace(/_/g,' ')}</span>
      <span class="bdg" style="color:${CC(a.convergence_state)}">${a.convergence_state}</span>
      ${a.is_value_trap?'<span class="bdg" style="color:#ef4444;border-color:#991b1b">⚠ VALUE TRAP</span>':''}
      ${a.rebound_probability?`<span class="bdg" style="color:#06b6d4">Rimbalzo ${a.rebound_probability}%</span>`:''}
    </div>

    <!-- COMPOSITE SCORE HERO -->
    <div class="score-hero">
      <div class="score-ring"><svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="52" fill="none" stroke="#1e293b" stroke-width="8"/>
        <circle cx="60" cy="60" r="52" fill="none" stroke="${RC(a.final_rating)}" stroke-width="8"
          stroke-dasharray="${sc*3.27} 327" stroke-dashoffset="0" stroke-linecap="round" transform="rotate(-90 60 60)"/></svg>
        <div class="score-num">${sc}</div><div class="score-lbl">/ 100</div></div>
      <div class="score-bars">
        ${scoreComp('Oversold',comp.oversold_strength||0,25,'#f59e0b')}
        ${scoreComp('Underval',comp.undervaluation||0,25,'#3b82f6')}
        ${scoreComp('Momentum',comp.momentum_reversal||0,25,'#a78bfa')}
        ${scoreComp('Health',comp.financial_health||0,25,'#22c55e')}
      </div>
      <div class="score-meta">
        ${kpi('Confidence',a.confidence+'%',a.confidence>=70?'#22c55e':'#f59e0b')}
        ${kpi('Health',`${a.health_rating||0}/5`,'#06b6d4')}
        ${kpi('Data',a.data_quality||'N/A',a.data_quality==='HIGH'?'#22c55e':'#f59e0b')}
      </div>
    </div>

    <div class="grid2">
      <!-- FACTORS -->
      <div class="card"><div class="card-t">💡 Perché Conta</div>
        <div class="fl" style="color:#22c55e">▲ BULLISH</div>
        ${(a.bullish_factors||[]).map(f=>`<div class="fx"><span style="color:#22c55e">●</span>${h(f)}</div>`).join('')||'<div class="mt">—</div>'}
        <div class="fl" style="color:#ef4444;margin-top:10px">▼ BEARISH</div>
        ${(a.bearish_factors||[]).map(f=>`<div class="fx"><span style="color:#ef4444">●</span>${h(f)}</div>`).join('')||'<div class="mt">—</div>'}
      </div>
      <!-- TECHNICAL -->
      <div class="card"><div class="card-t">📈 Tecnica</div>
        ${techGrid(a.technical||{})}
        <div class="ts">${h((a.technical||{}).technical_state||'')}</div>
      </div>
      <!-- SMART MONEY -->
      <div class="card"><div class="card-t">🏦 Smart Money</div>${smBlock(a.smart_money||{})}</div>
      <!-- MACRO -->
      <div class="card"><div class="card-t">🌍 Macro & Settore</div>${macroBlock(a.macro_sector||{})}</div>
    </div>
    <!-- TRADE PLAN -->
    ${tradePlan(a.trade_plan||{})}
    <!-- EVENTS -->
    <div class="card card-f"><div class="card-t">📅 Eventi</div>
      ${(a.events||[]).sort((x,y)=>(y.date||'').localeCompare(x.date||'')).map(e=>
        `<div class="ev"><span class="ev-i">${{INSIDER:'👤',EARNINGS:'📊',TECHNICAL:'📈',NEWS:'📰'}[e.type]||'•'}</span><span class="ev-d">${h(e.date)}</span><span class="ev-t">${h(e.desc)}</span><span style="color:${({BULLISH:'#22c55e',BEARISH:'#ef4444'})[e.impact]||'#64748b'};font-size:10px">${h(e.impact)}</span></div>`
      ).join('')||'<div class="mt">Nessun evento</div>'}
    </div>`;
}

function scoreComp(label, val, max, color) {
  const pct = (val/max)*100;
  return `<div class="sc-bar"><div class="sc-bar-h"><span>${label}</span><span style="color:${color}">${val}/${max}</span></div>
    <div class="sc-bar-t"><div class="sc-bar-f" style="width:${pct}%;background:${color}"></div></div></div>`;
}

function kpi(l,v,c) { return `<div class="kpi"><div class="kpi-l">${l}</div><div class="kpi-v" style="color:${c}">${v}</div></div>`; }

function techGrid(t) {
  const rsi = t.rsi||{};
  const macd = t.macd||{};
  const bb = t.bollinger||{};
  const adx = t.adx||{};
  const vol = t.volume||{};
  const tr = t.trend||{};
  const rv = rsi.value||t.rsi_value||50;
  return `<div class="tg">
    ${tb('RSI',rv,rv>70?'#ef4444':rv<30?'#22c55e':'#e2e8f0')}
    ${tb('MACD',macd.state||t.macd_state||'—',(macd.state||'').includes('BULL')?'#22c55e':'#ef4444')}
    ${tb('ADX',adx.value||t.adx_value||'—',adx.value>25?'#22c55e':'#64748b')}
    ${tb('Trend',tr.direction||t.trend_direction||'—',(tr.direction||'').includes('UP')?'#22c55e':(tr.direction||'').includes('DOWN')?'#ef4444':'#f59e0b')}
  </div>
  <div class="tg" style="margin-top:6px">
    ${tb('BB %B',(bb.pct_b!==undefined?bb.pct_b:'—'),bb.pct_b<=0.2?'#22c55e':bb.pct_b>=0.8?'#ef4444':'#e2e8f0')}
    ${tb('Squeeze',bb.squeeze?'SÌ':'NO',bb.squeeze?'#f59e0b':'#64748b')}
    ${tb('Vol',vol.relative_volume||'—',vol.relative_volume>=1.5?'#f59e0b':'#94a3b8')}
    ${tb('RSI Div',rsi.divergence||'—',rsi.divergence==='BULLISH'?'#22c55e':rsi.divergence==='BEARISH'?'#ef4444':'#64748b')}
  </div>
  <div class="sr"><span>S: <b style="color:#22c55e">${t.support||'—'}</b></span><span>R: <b style="color:#ef4444">${t.resistance||'—'}</b></span>
    <span>MA50: <b style="color:${(t.ma50_distance_pct||0)>=0?'#22c55e':'#ef4444'}">${pf(t.ma50_distance_pct)}</b></span></div>`;
}

function tb(l,v,c) { return `<div class="tbx"><div class="tbx-l">${l}</div><div class="tbx-v" style="color:${c}">${h(v)}</div></div>`; }

function smBlock(sm) {
  if (!sm.institutional_holders?.length && !sm.insider_buys?.length && !sm.insider_sells?.length)
    return '<div class="mt">Configura Perplexity API per dati smart money</div>';
  const holders = (sm.institutional_holders||[]).map(x=>`<div class="smr">${h(x.name)} <span class="mn">${h(x.shares)} ${h(x.change)}</span></div>`).join('');
  const trades = [...(sm.insider_buys||[]).map(b=>({...b,s:'BUY'})),...(sm.insider_sells||[]).map(s=>({...s,s:'SELL'}))].map(t=>
    `<div class="smr"><span style="color:${t.s==='BUY'?'#22c55e':'#ef4444'};font-size:9px;font-weight:700">${t.s}</span> ${h(t.name)} <span class="mn">${h(t.amount)} ${h(t.date)}</span></div>`
  ).join('');
  return `<div class="sml">Istituzionali (13F, 0.5x)</div>${holders||'<div class="mt">—</div>'}
    <div class="sml" style="margin-top:8px">Insider (Form 4, 3.5x)</div>${trades||'<div class="mt">—</div>'}
    <div class="sme">Cluster: <span style="color:${sm.cluster_signal==='STRONG_BUY'?'#22c55e':'#94a3b8'}">${h(sm.cluster_signal)}</span></div>`;
}

function macroBlock(m) {
  return `<div class="tg">
    ${tb('Regime',m.macro_regime,m.macro_regime==='RISK_ON'?'#22c55e':'#ef4444')}
    ${tb('VIX',m.vix,m.vix<15?'#22c55e':m.vix<20?'#f59e0b':'#ef4444')}
    ${tb('Bias',m.macro_bias,'#3b82f6')}
    ${tb('Settore',m.sector_strength,m.sector_strength==='STRONG'?'#22c55e':'#f59e0b')}
  </div>
  <div class="tgs">${h(m.sector)} ${(m.related_assets||[]).map(r=>`<span class="tag">${h(r)}</span>`).join('')}</div>`;
}

function tradePlan(tp) {
  const sc = tp.state==='ACTIONABLE_NOW'?'#22c55e':tp.state==='MONITOR'?'#f59e0b':'#64748b';
  return `<div class="card card-f" style="border-top:2px solid ${sc}"><div class="card-t">🎯 Piano Operativo</div>
    <div class="ps" style="color:${sc}">${h((tp.state||'MONITOR').replace(/_/g,' '))}</div>
    <div class="pg">${['entry_zone','stop_zone','target_zone'].map(k=>`<div class="pb"><div class="pbl">${k.replace(/_/g,' ').toUpperCase()}</div><div style="color:${k.includes('stop')?'#ef4444':k.includes('target')?'#22c55e':'#3b82f6'}">${h(tp[k]||'—')}</div></div>`).join('')}</div>
    ${tp.contrary_scenario?`<div class="contrary">⚠ ${h(tp.contrary_scenario)}</div>`:''}
  </div>`;
}

// ═══════════════════════════════════════════════════════════════════
// PLANNER TAB
// ═══════════════════════════════════════════════════════════════════
function renderPlanner() {
  document.getElementById('tab-planner').innerHTML = `<div class="page">
    <h2>💰 Piano Finanziario</h2>
    <div class="plan-ctrl">
      <div class="pi"><label>€/mese</label><input type="number" id="pl-m" value="500" min="50" step="50"></div>
      <div class="pi"><label>Anni</label><input type="number" id="pl-y" value="20" min="1" max="50"></div>
      <div class="pi"><label>Rend. %</label><input type="number" id="pl-r" value="7" min="1" max="20" step="0.5"></div>
      <div class="pi"><label>Target €/mese</label><input type="number" id="pl-t" value="2000" min="100" step="100"></div>
      <button class="btn btn-g" data-action="run-plan">🚀 Calcola</button>
      <button class="btn" data-action="run-plan-ai">🤖 Piano AI</button>
    </div>
    <div id="plan-out"></div>
  </div>`;
}

async function runPlan() {
  const m=document.getElementById('pl-m').value, y=document.getElementById('pl-y').value,
        r=document.getElementById('pl-r').value, t=document.getElementById('pl-t').value;
  document.getElementById('plan-out').innerHTML='<div class="loading-text">Calcolo...</div>';
  try {
    const [pac,port] = await Promise.all([
      API.get(`/api/planner/pac?monthly=${m}&years=${y}&rate=${r}`),
      API.get('/api/planner/portfolio')
    ]);
    const inc = await API.get(`/api/planner/income?capital=${pac.future_value}&yield_pct=4&withdrawal_pct=3.5`);
    const ok = inc.safe_monthly_withdrawal >= t;
    document.getElementById('plan-out').innerHTML = `
      <div class="card card-f" style="border-top:2px solid ${ok?'#22c55e':'#f59e0b'}">
        <div class="card-t">📊 Risultato</div>
        <div class="kpi-row">${kpi('Investito','€'+fmt(pac.total_invested),'#94a3b8')}${kpi('Capitale','€'+fmt(pac.future_value),'#22c55e')}${kpi('Guadagno','+'+pac.gain_pct+'%','#06b6d4')}${kpi('Rendita/m','€'+fmt(inc.safe_monthly_withdrawal),ok?'#22c55e':'#ef4444')}</div>
        <div style="margin:12px 0;font-weight:700;color:${ok?'#22c55e':'#f59e0b'}">${ok?'✅ Target raggiunto!':'⚠ Gap €'+fmt(t-inc.safe_monthly_withdrawal)+'/mese'}</div>
      </div>${portfolioCard(port)}
      <div class="pp-box"><a href="https://www.paypal.com/donate/?business=staracegiuseppe%40gmail.com&currency_code=EUR" target="_blank" class="pp-btn">💙 Supporta Alpha360</a></div>`;
  } catch(e) { document.getElementById('plan-out').innerHTML=`<div class="err">${e.message}</div>`; }
}

async function runPlanAI() {
  document.getElementById('plan-out').innerHTML='<div class="loading-text">🤖 Generazione piano AI...</div>';
  try {
    const p = await API.post('/api/planner/full');
    const s = p.summary||{};
    document.getElementById('plan-out').innerHTML = `
      <div class="card card-f" style="border-top:2px solid #818cf8"><div class="card-t">🤖 Piano AI</div>
        <div class="kpi-row">${kpi('Capitale','€'+fmt(s.pac_final_capital),'#22c55e')}${kpi('Rendita','€'+fmt(s.achievable_monthly_income),'#06b6d4')}${kpi('Target','€'+fmt(s.target_monthly_income),s.is_target_achievable?'#22c55e':'#ef4444')}${kpi('Gap','€'+fmt(s.gap_to_target),s.gap_to_target<=0?'#22c55e':'#ef4444')}</div>
      </div>${portfolioCard(p.portfolio)}`;
  } catch(e) { document.getElementById('plan-out').innerHTML=`<div class="err">${e.message}</div>`; }
}

function portfolioCard(p) {
  if (!p?.allocations?.length) return '';
  const rows = p.allocations.map(a=>{
    const c=a.action==='ACCUMULA'?'#22c55e':a.action==='POSIZIONA'?'#3b82f6':a.action==='MONITORA'?'#f59e0b':'#64748b';
    return `<div class="ar"><span class="ar-s">${h(a.symbol)}</span><span style="color:${c};font-size:11px;font-weight:700">${h(a.action)}</span><span class="mn">${a.suggested_weight_pct}%</span></div>`;
  }).join('');
  return `<div class="card card-f"><div class="card-t">📊 Portfolio</div>${rows}</div>`;
}

// ═══════════════════════════════════════════════════════════════════
// EMAIL + CONFIG
// ═══════════════════════════════════════════════════════════════════
async function renderEmail() {
  let st = {}; try { st = await API.get('/api/email/status'); } catch(e) {}
  document.getElementById('tab-email').innerHTML = `<div class="page"><h2>✉ Email Digest</h2>
    <div class="ea"><button class="btn btn-g" data-action="email-send">Invia</button><button class="btn" data-action="email-force">Forza</button><button class="btn" data-action="email-preview">Preview</button></div>
    <div class="kpi-row" style="margin:12px 0">${kpi('Status',st.enabled?'ON':'OFF',st.enabled?'#22c55e':'#ef4444')}${kpi('Invii',st.send_count||0,'#06b6d4')}${kpi('Errori',st.error_count||0,st.error_count?'#ef4444':'#22c55e')}</div>
    <div id="ep-box"></div></div>`;
}
async function sendEmail(f) {
  try { const r=await API.post(`/api/email/send?force=${f}`); alert(r.status==='sent'?'✅ Inviata!':r.status+': '+(r.reason||r.error||'')); renderEmail(); }
  catch(e) { alert('Errore: '+e.message); }
}
async function previewEmail() {
  try { const html=await API.html('/api/email/preview/html');
    document.getElementById('ep-box').innerHTML=`<div class="card card-f"><div class="card-t">Preview</div><div class="ep">${html}</div></div>`;
  } catch(e) { alert(e.message); }
}

async function renderConfig() {
  let o={},sc={},si={}; try{[o,sc,si]=await Promise.all([API.get('/api/options'),API.get('/api/scheduler/status'),API.get('/api/scoring/info')]);}catch(e){}
  document.getElementById('tab-config').innerHTML = `<div class="page"><h2>⚙ Configurazione</h2>
    <div class="card card-f"><div class="card-t">📡 API</div>
      <div class="cr"><span>Claude</span><span style="color:${o.claude_configured?'#22c55e':'#ef4444'}">${o.claude_configured?'✅':'❌'}</span></div>
      <div class="cr"><span>Perplexity</span><span style="color:${o.perplexity_configured?'#22c55e':'#ef4444'}">${o.perplexity_configured?'✅':'❌'}</span></div>
      <div class="cr"><span>Email</span><span style="color:${o.email_configured?'#22c55e':'#ef4444'}">${o.email_configured?'✅':'❌'}</span></div>
      <div class="cr"><span>Simboli</span><span>${(o.symbols||[]).join(', ')}</span></div></div>
    <div class="card card-f"><div class="card-t">📬 Scheduler</div>
      <div class="kpi-row">${kpi('Stato',sc.running?'ON':'OFF',sc.running?'#22c55e':'#ef4444')}${kpi('Intervallo',(sc.interval_minutes||60)+'m','#06b6d4')}${kpi('Cicli',sc.run_count||0,'#94a3b8')}</div>
      <div class="ea" style="margin-top:10px"><button class="btn btn-g" data-action="sched-start">▶</button><button class="btn" data-action="sched-stop" style="color:#ef4444">⏸</button><button class="btn" data-action="sched-trigger">⚡ Trigger</button></div></div>
    <div class="card card-f"><div class="card-t">⚖ Scoring</div>
      <div class="cr"><span>Sistema</span><span>Composito 0-100</span></div>
      ${Object.entries(si.components||{}).map(([k,v])=>`<div class="cr"><span>${h(k)}</span><span class="mt">${h(v)}</span></div>`).join('')}
      <div class="cr"><span>Filtri</span><span class="mt">${(si.filters||[]).join(', ')}</span></div></div>
    <div class="pp-box"><a href="https://www.paypal.com/donate/?business=staracegiuseppe%40gmail.com&currency_code=EUR" target="_blank" class="pp-btn">💙 Supporta Alpha360 — Dona con PayPal</a></div></div>`;
}
async function schedCtrl(cmd) {
  try { await API.post(`/api/scheduler/${cmd}`); renderConfig(); } catch(e) { alert(e.message); }
}

// ─── Actions ──────────────────────────────────────────────────────
async function doRefresh() {
  showLoad(true);
  try { await API.post('/api/analyses/refresh?use_ai=true');
    const d = await API.get('/api/analyses'); S.analyses = d.analyses||[];
  } catch(e) { alert('Errore: '+e.message); }
  showLoad(false); renderAnalisi();
}

// ─── Boot ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
