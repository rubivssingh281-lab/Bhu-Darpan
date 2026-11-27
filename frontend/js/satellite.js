// ============ Chart.js defaults (light theme) ============
Chart.defaults.color = '#857b67';
Chart.defaults.font.family = "'JetBrains Mono',monospace";
Chart.defaults.font.size = 11;
Chart.defaults.borderColor = '#e6dfce';
const GRID = '#ece6d8';
const INK = '#2b2618';

const CLASS_HEX = { Forest: '#2E7D32', Water: '#1565C0', Agriculture: '#D9A520', Urban: '#E53935', Others: '#9E9E9E' };
const OBJ_HEX = { Building: '#E53935', Road: '#DD9138', 'Water Body': '#1565C0', Vegetation: '#2E7D32', Farmland: '#B0951F' };

const el = (id) => document.getElementById(id);
const store = { token: localStorage.getItem('bd_token') || null, user: null };
async function api(path, { method = 'GET', body, form } = {}) {
  const headers = {};
  if (store.token) headers.Authorization = 'Bearer ' + store.token;
  let payload;
  if (form) {
    payload = form;
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const API_BASE = (window.location.hostname === 'localhost' && window.location.port === '8010')
    ? 'http://localhost:8000'
    : '';
  const fullPath = path.startsWith('http') ? path : API_BASE + (path.startsWith('/') ? path : '/' + path);
  let res;
  for (let attempt = 0; attempt < 4; attempt++) {
    res = await fetch(fullPath, { method, headers, body: payload });
    if (res.status !== 502 && res.status !== 503 && res.status !== 504) break;
    if (attempt < 3) await new Promise(ok => setTimeout(ok, (attempt + 1) * 2000));
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || ('Request failed (' + res.status + ')'));
  return data;
}
function toast(msg) { const t = document.createElement('div'); t.className = 'toast'; t.textContent = msg; document.body.appendChild(t); setTimeout(() => t.remove(), 3200); }
function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

// ============ AUTH (password + email OTP) ============
let authMode = 'login';     // 'login' | 'register'
let authStep = 'cred';      // 'cred' | 'otp'
let pendingEmail = '', pendingPurpose = 'login';

function setTabs() {
  [...el('authTabs').children].forEach(b => b.classList.toggle('on', b.dataset.mode === authMode));
}
function renderAuthMode() {
  authStep = 'cred';
  const isLogin = authMode === 'login';
  el('authTitle').textContent = isLogin ? 'Welcome back' : 'Create account';
  el('authSub').textContent = isLogin ? 'Sign in to the J&K climate & satellite twin' : 'Create your analysis account';
  el('credStep').hidden = false; el('otpStep').hidden = true;
  el('nameField').hidden = isLogin; el('passField').hidden = false;
  el('orgField').hidden = isLogin; el('roleField').hidden = isLogin;
  el('authBtn').textContent = isLogin ? 'Sign in' : 'Send verification code';
  if (el('googleAuthBtn')) {
    el('googleAuthBtn').hidden = false;
    el('googleAuthText').textContent = isLogin ? 'Sign in with Google' : 'Sign up with Google';
  }
  if (el('authDivider')) el('authDivider').hidden = false;
  el('authAlt').hidden = !isLogin;      // OTP-login link only when signing in
  el('otpBack').hidden = true;
  el('authSwitch').innerHTML = '';
  el('authErr').hidden = true; el('authOtp').value = '';
  setTabs();
}
function goOtpStep(email, purpose, resp) {
  authStep = 'otp'; pendingEmail = email; pendingPurpose = purpose;
  el('credStep').hidden = true; el('otpStep').hidden = false;
  if (el('googleAuthBtn')) el('googleAuthBtn').hidden = true;
  if (el('authDivider')) el('authDivider').hidden = true;
  el('authAlt').hidden = true; el('otpBack').hidden = false;
  el('otpEmail').textContent = email;
  el('authTitle').textContent = 'Check your email';
  el('authSub').textContent = resp.delivery === 'email'
    ? 'We sent a 6-digit code to your inbox.'
    : 'Enter the code below to continue.';
  el('authBtn').textContent = 'Verify & continue';
  if (resp.dev_otp) { el('otpHint').hidden = false; el('otpHint').innerHTML = 'Dev mode (no SMTP configured): your code is <b>' + resp.dev_otp + '</b>'; }
  else el('otpHint').hidden = true;
  el('authOtp').focus();
}

[...el('authTabs').children].forEach(b => b.onclick = () => { authMode = b.dataset.mode; renderAuthMode(); });
el('altOtp').onclick = async () => {
  const email = el('authEmail').value.trim();
  if (!email) { el('authErr').textContent = 'Enter your email first.'; el('authErr').hidden = false; return; }
  el('authErr').hidden = true; el('authBtn').disabled = true;
  try { const r = await api('/api/auth/request-otp', { method: 'POST', body: { email } }); goOtpStep(email, 'login', r); }
  catch (ex) { el('authErr').textContent = ex.message; el('authErr').hidden = false; }
  finally { el('authBtn').disabled = false; }
};
if (el('googleAuthBtn')) {
  el('googleAuthBtn').onclick = async () => {
    el('authErr').hidden = true;
    el('googleAuthBtn').disabled = true;
    const originalText = el('googleAuthText').textContent;
    el('googleAuthText').textContent = 'Connecting to Google...';
    try {
      const creds = await signInWithGoogleFirebase();
      const resp = await api('/api/auth/firebase', {
        method: 'POST',
        body: {
          id_token: creds.idToken,
          email: creds.email,
          name: creds.name,
          photo_url: creds.photo_url
        }
      });
      toast('Signed in as ' + (resp.user.name || resp.user.email));
      finishAuth(resp);
    } catch (ex) {
      let msg = ex.message || 'Google sign-in failed.';
      if (msg.includes('auth/popup-closed-by-user')) {
        msg = 'Sign-in popup closed before completion.';
      } else if (msg.includes('auth/cancelled-popup-request')) {
        msg = 'Sign-in was cancelled.';
      } else if (msg.includes('auth/configuration-not-found') || msg.includes('auth/operation-not-allowed')) {
        msg = 'Enable Google Sign-In in Firebase Console -> Authentication -> Sign-in method.';
      } else if (msg.includes('auth/unauthorized-domain')) {
        msg = 'Authorize this domain in Firebase Console -> Authentication -> Settings -> Authorized domains.';
      } else if (msg.includes('AIzaSy_YOUR_API_KEY_HERE') || msg.includes('API key not valid')) {
        msg = 'Firebase Configuration Needed: Please update your API key in js/firebase-config.js.';
      }
      el('authErr').textContent = msg;
      el('authErr').hidden = false;
    } finally {
      el('googleAuthBtn').disabled = false;
      el('googleAuthText').textContent = originalText;
    }
  };
}
el('toBack').onclick = () => renderAuthMode();
el('otpResend').onclick = async () => {
  el('authErr').hidden = true;
  try {
    let r;
    if (pendingPurpose === 'register')
      r = await api('/api/auth/register', { method: 'POST', body: { name: el('authName').value.trim() || pendingEmail.split('@')[0], email: pendingEmail, password: el('authPass').value, organization: el('authOrg').value.trim(), role: el('authRole').value.trim() } });
    else r = await api('/api/auth/request-otp', { method: 'POST', body: { email: pendingEmail } });
    goOtpStep(pendingEmail, pendingPurpose, r); toast('New code sent');
  } catch (ex) { el('authErr').textContent = ex.message; el('authErr').hidden = false; }
};

function finishAuth(r) { store.token = r.token; store.user = r.user; localStorage.setItem('bd_token', r.token); enterApp(); }

el('authForm').addEventListener('submit', async (e) => {
  e.preventDefault(); el('authErr').hidden = true; el('authBtn').disabled = true;
  try {
    if (authStep === 'otp') {
      const r = await api('/api/auth/verify-otp', { method: 'POST', body: { email: pendingEmail, code: el('authOtp').value.trim() } });
      finishAuth(r); return;
    }
    const email = el('authEmail').value.trim();
    if (authMode === 'login') {
      const r = await api('/api/auth/login', { method: 'POST', body: { email, password: el('authPass').value } });
      finishAuth(r);
    } else {
      const r = await api('/api/auth/register', { method: 'POST', body: { name: el('authName').value.trim(), email, password: el('authPass').value, organization: el('authOrg').value.trim(), role: el('authRole').value.trim() } });
      goOtpStep(email, 'register', r);
    }
  } catch (ex) { el('authErr').textContent = ex.message; el('authErr').hidden = false; }
  finally { el('authBtn').disabled = false; }
});
el('logoutBtn').addEventListener('click', () => { localStorage.removeItem('bd_token'); store.token = null; store.user = null; window.location.href = '/'; });

let climateReady = false;
function enterApp() {
  el('authOverlay').hidden = true; el('appShell').hidden = false;
  const nm = store.user?.name || store.user?.email || 'user';
  const em = store.user?.email || '';
  el('navUser').textContent = nm;
  el('acctEmail').textContent = em;
  const initial = (nm || 'U').trim().charAt(0).toUpperCase() || 'U';
  el('acctInitial').textContent = initial;
  el('acctAv').textContent = initial;
  const esc = s => (s == null ? '' : String(s)).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const u = store.user || {};
  const rows = [];
  if (u.organization) rows.push(['Organization', esc(u.organization)]);
  if (u.role) rows.push(['Role', esc(u.role)]);
  if (u.created_at) rows.push(['Member since', esc((u.created_at || '').split(' ')[0])]);
  rows.push(['Status', '<span class="acct-badge">✓ Verified</span>']);
  el('acctDetails').innerHTML = rows.map(([k, v]) => `<div class="acct-row"><span class="k">${k}</span><span class="v">${v}</span></div>`).join('');
  initAccount();
  if (!climateReady) { initClimate(); climateReady = true; }
  loadDashboard(); loadReports(); loadChangeHistory(); loadDisasterHistory();
  initScrollSpy();
  initDisaster();
}
let acctReady = false;
function initAccount() {
  if (acctReady) return; acctReady = true;
  const btn = el('acctBtn'), panel = el('acctPanel');
  const close = () => { panel.hidden = true; btn.classList.remove('open'); };
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const willOpen = panel.hidden;
    panel.hidden = !willOpen;
    btn.classList.toggle('open', willOpen);
  });
  panel.addEventListener('click', (e) => e.stopPropagation());
  document.addEventListener('click', close);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
}
let disReady = false, disScene = null, disBefore = null;
function initDisaster() {
  if (disReady) return; disReady = true;
  const bind = (zone, input, prev, empty, set) => {
    const z = el(zone), i = el(input);
    z.addEventListener('click', () => i.click());
    z.addEventListener('dragover', e => { e.preventDefault(); z.classList.add('drag'); });
    z.addEventListener('dragleave', () => z.classList.remove('drag'));
    z.addEventListener('drop', e => { e.preventDefault(); z.classList.remove('drag'); const f = e.dataTransfer.files[0]; if (f) put(f); });
    i.addEventListener('change', e => { const f = e.target.files[0]; if (f) put(f); });
    function put(f) { set(f); const img = el(prev); img.src = URL.createObjectURL(f); img.hidden = false; el(empty).hidden = true; el('disRun').disabled = !disScene; el('disClear').hidden = false; }
  };
  bind('dzDis', 'disFile', 'dzDisPrev', 'dzDisEmpty', f => disScene = f);
  bind('dzDisB', 'disBefore', 'dzDisBPrev', 'dzDisBEmpty', f => disBefore = f);
  el('disClear').onclick = () => {
    disScene = disBefore = null;
    ['dzDisPrev', 'dzDisBPrev'].forEach(id => { el(id).hidden = true; el(id).src = ''; });
    ['dzDisEmpty', 'dzDisBEmpty'].forEach(id => el(id).hidden = false);
    el('disRun').disabled = true; el('disClear').hidden = true; el('disResult').hidden = true; el('disErr').hidden = true;
  };
  el('disRun').onclick = runDisaster;
  el('disCopy').onclick = () => { navigator.clipboard.writeText(el('disAlert').textContent).then(() => toast('Alert copied')); };
  const syncBasemap = () => {
    const on = el('disUseBasemap').checked;
    el('disManualBefore').hidden = on;
    el('disBasemapNote').hidden = !on;
    if (on) { disBefore = null; el('dzDisBPrev').hidden = true; el('dzDisBPrev').src = ''; el('dzDisBEmpty').hidden = false; }
  };
  el('disUseBasemap').addEventListener('change', syncBasemap);
  syncBasemap();
}
async function runDisaster() {
  if (!disScene) return;
  const useBase = el('disUseBasemap').checked;
  const lat = el('disLat').value.trim(), lon = el('disLon').value.trim();
  if (useBase && (!lat || !lon)) {
    el('disErr').textContent = 'Enter latitude & longitude so the "before" baseline can be fetched from the satellite map.';
    el('disErr').hidden = false; return;
  }
  el('disErr').hidden = true; el('disProc').hidden = false; el('disRun').disabled = true;
  try {
    const fd = new FormData();
    fd.append('file', disScene);
    if (useBase) { fd.append('use_basemap', 'true'); fd.append('extent_km', '3'); }
    else if (disBefore) fd.append('before', disBefore);
    if (el('disRegion').value.trim()) fd.append('region', el('disRegion').value.trim());
    if (lat) fd.append('lat', lat);
    if (lon) fd.append('lon', lon);
    const r = await api('/api/disaster/detect', { method: 'POST', form: fd });
    renderDisaster(r);
  } catch (ex) { el('disErr').textContent = ex.message; el('disErr').hidden = false; }
  finally { el('disProc').hidden = true; el('disRun').disabled = false; }
}
const SEV_COL = { None: '#8a8f98', Low: '#0e9c8a', Moderate: '#dd9138', High: '#d2694a', Severe: '#b23b1e' };
function renderDisaster(r) {
  const sevCol = SEV_COL;
  el('disPrimary').textContent = r.primary;
  el('disMode').textContent = (r.mode === 'change' ? 'Pre/post change analysis' : 'Single-scene assessment') + ' · ' + r.detected_at;
  const sc = sevCol[r.severity] || '#8a8f98';
  el('disSeverity').textContent = 'Severity: ' + r.severity;
  el('disSeverity').style.background = sc + '22'; el('disSeverity').style.color = sc;
  el('disAffected').textContent = 'Affected ~' + r.affected_area_pct + '%';
  const ov = el('disOverlay');
  if (r.overlay_url) { ov.src = r.overlay_url; ov.hidden = false; el('disNoOverlay').hidden = true; }
  else { ov.hidden = true; el('disNoOverlay').hidden = false; }
  const bb = el('disBaselineBox');
  if (r.baseline_url) { el('disBaseline').src = r.baseline_url; el('disBaselineSrc').textContent = r.baseline_source || 'Esri World Imagery'; bb.hidden = false; }
  else bb.hidden = true;
  el('disDetections').innerHTML = r.detections.length ? r.detections.map(d => `
        <div class="dis-row">
          <div class="dh"><span class="dn">${d.type}</span><span class="dc">${Math.round(d.confidence * 100)}% confidence</span></div>
          <div class="dis-bar"><i style="width:${Math.round(d.confidence * 100)}%;background:${sc}"></i></div>
          <div class="de">${d.evidence}</div>
        </div>`).join('') : '<div class="card-sub">No disaster signature detected in this scene.</div>';
  el('disAlert').textContent = r.authority_alert;
  const ex = r.exposure || {};
  el('disExposure').innerHTML = `<div class="card-sub" style="margin-bottom:6px;color:var(--teal);font-weight:600">Exposure estimate</div>
        <div style="font-size:13px;color:var(--ink-soft);line-height:1.6">Built-up cover <b>${ex.builtup_pct ?? '—'}%</b>${ex.builtup_in_impact_pct > 0.5 ? `, <b>${ex.builtup_in_impact_pct}%</b> within the impact zone` : ''}. ${ex.note || ''}</div>`;
  if (r.carbon_flux && r.carbon_flux.carbon_flux_tco2e > 0) {
    const cf = r.carbon_flux;
    el('disExposure').innerHTML += `<div style="margin-top:8px;padding-top:8px;border-top:1px dashed var(--line);font-size:12.5px;color:var(--forest)">🌿 <b>Ecological Carbon Flux:</b> ~${cf.carbon_flux_tco2e} tCO₂e (${cf.biomass_loss_tons} tons biomass over ~${cf.forest_loss_ha} ha)</div>`;
  }
  el('disLimits').innerHTML = '<b>Limitations:</b><br>• ' + (r.limitations || []).join('<br>• ');
  el('disResult').hidden = false;
  el('disResult').scrollIntoView({ behavior: 'smooth', block: 'start' });
  loadDisasterHistory();
}
async function loadDisasterHistory() {
  let items; try { items = await api('/api/disaster/history'); } catch { return; }
  const sub = el('disHistSub'), cnt = el('disHistCount'), list = el('disHistoryList');
  if (cnt) cnt.textContent = items.length;
  if (sub) sub.textContent = items.length ? `${items.length} scan${items.length > 1 ? 's' : ''} on record` : 'No scans yet';
  if (!list) return;
  if (!items.length) { list.innerHTML = '<div class="empty"><div class="em-ic">🛑</div>No disaster scans yet — assess a scene above to build a history.</div>'; return; }
  list.innerHTML = items.map(d => {
    const sc = SEV_COL[d.severity] || '#8a8f98';
    const thumb = d.overlay_url
      ? `<img src="${d.overlay_url}" alt="" />`
      : `<div style="width:46px;height:46px;border-radius:8px;background:var(--panel-2);display:grid;place-items:center;font-size:18px;flex-shrink:0">🛑</div>`;
    const loc = d.location && d.location.lat != null ? ` · ${d.location.lat}, ${d.location.lon}` : '';
    return `<div class="ritem">${thumb}
          <div><div class="rn">${d.primary || 'Assessment'} <span style="color:var(--muted);font-weight:400">— ${d.name || 'scene'}</span></div>
            <div class="rd">${d.created_at} · ${d.region || 'J&K'}${loc}</div></div>
          <span class="rc"><span class="dis-badge" style="background:${sc}22;color:${sc}">${d.severity} · ~${d.affected_area_pct ?? 0}%</span></span></div>`;
  }).join('');
}
// ---- Dedicated per-tab views: each nav link shows its own page ----
const VIEWS = {
  region: ['top', 'metrics', 'region'],
  scenario: ['scenario'],
  forecast: ['forecast'],
  disaster: ['disaster'],
  workspace: ['workspace', 'change'],
  dashboard: ['dashboard'],
  reports: ['reports'],
};
const ALL_SECTIONS = Object.values(VIEWS).flat();
let currentView = null;
function showView(view) {
  if (!VIEWS[view]) view = 'region';
  currentView = view;
  const show = new Set(VIEWS[view]);
  ALL_SECTIONS.forEach(id => { const s = document.getElementById(id); if (s) s.hidden = !show.has(id); });
  // reveal-on-scroll never fires for a section that loaded hidden, so force it visible
  VIEWS[view].forEach(id => { const s = document.getElementById(id); if (s) s.querySelectorAll('.reveal').forEach(r => r.classList.add('in')); });
  document.querySelectorAll('.navlinks a').forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#' + view));
  if (view === 'region' && typeof satMap !== 'undefined' && satMap) { setTimeout(fitSat, 60); setTimeout(fitSat, 220); }
  history.replaceState(null, '', '#' + view);
  window.scrollTo(0, 0);
}
let navReady = false;
function initScrollSpy() {
  if (navReady) return; navReady = true;
  // intercept every in-page anchor that targets a view (nav links + hero CTAs + buttons)
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    const id = a.getAttribute('href').slice(1);
    const owner = VIEWS[id] ? id : Object.keys(VIEWS).find(v => VIEWS[v].includes(id));
    if (!owner) return;
    a.addEventListener('click', e => { e.preventDefault(); showView(owner); });
  });
  const hash = (location.hash || '').slice(1);
  const start = VIEWS[hash] ? hash : (Object.keys(VIEWS).find(v => VIEWS[v].includes(hash)) || 'region');
  showView(start);
}
// model accuracy straight from the metrics files (never hard-coded in the page)
async function loadModelInfo() {
  try {
    const m = await api('/api/analysis/model');
    if (m.test_accuracy_10class == null) return;
    const pe = m.pipeline_eval;
    el('lcModelFeat').textContent = `Land-cover CNN trained on EuroSAT — ${m.test_accuracy_10class}% held-out test accuracy (${m.test_accuracy}% on the 5 app classes)`
      + (pe ? `; full segmentation pipeline ${pe.eurosat_accuracy_pct}% on EuroSAT test tiles.` : '.');
    el('disModelAcc').textContent = ` (${m.test_accuracy_10class}% held-out test)`;
  } catch { }
}

async function boot() {
  loadModelInfo();
  renderAuthMode();
  if (store.token) { try { store.user = await api('/api/auth/me'); enterApp(); return; } catch { localStorage.removeItem('bd_token'); store.token = null; } }
  el('authOverlay').hidden = false;
}

/* =========================================================
   CLIMATE TWIN (client-side prototype for Jammu & Kashmir)
   ========================================================= */
function initClimate() { loadClimateOverview(); initMap(); initWhatIf(); initForecasts(); }

// ---- Current climate state (live KPIs, summary, pipeline, districts) ----
const CC = { clay: '#d2694a', ochre: '#dd9138', teal: '#2aa38a', ocean: '#2f7d9a' };
const rainCol = p => p < -20 ? CC.clay : p < -10 ? CC.ochre : p > 25 ? CC.ocean : CC.teal;
const soilCol = v => v < 0.35 ? CC.clay : v < 0.45 ? CC.ochre : CC.teal;
function csparkline(values, color) {
  if (!values || !values.length) return '';
  const w = 100, h = 34, mn = Math.min(...values), mx = Math.max(...values), rng = (mx - mn) || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1) * w).toFixed(1)},${(h - 4 - (v - mn) / rng * (h - 8)).toFixed(1)}`).join(' ');
  return `<svg class="cspark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}
let satOvStamp = 0, satOvTimer = null;
function satOvTick() {
  if (!satOvStamp) return;
  const s = Math.round((Date.now() - satOvStamp) / 1000);
  const ago = s < 60 ? s + 's ago' : Math.floor(s / 60) + 'm ' + (s % 60) + 's ago';
  const e = el('satOvLive'); if (e) e.innerHTML = `<span class="pulse" style="display:inline-block;margin-right:6px"></span>Live · auto-refresh 60s · updated ${ago}`;
}
async function loadClimateOverview() {
  let s; try { s = await api('/api/climate/current'); } catch { return; }
  const ra = (s.rainfall_anomaly_pct > 0 ? '+' : '') + s.rainfall_anomaly_pct;
  const dCol = { Severe: CC.clay, Moderate: CC.ochre, Mild: CC.ochre, Normal: CC.teal }[s.drought_class] || CC.teal;
  const kpis = [
    { lbl: 'Rainfall anomaly', ic: '🌧️', col: rainCol(s.rainfall_anomaly_pct), val: ra, unit: '%', meta: '90-day vs normal', spark: s.spark_precip },
    { lbl: 'Temperature anomaly', ic: '🌡️', col: s.temperature_anomaly_c > 1.3 ? CC.clay : CC.teal, val: (s.temperature_anomaly_c > 0 ? '+' : '') + s.temperature_anomaly_c, unit: '°C', meta: 'vs 1973–2023 normal', spark: s.spark_temp },
    { lbl: 'Soil moisture', ic: '💧', col: soilCol(s.soil_moisture_index), val: s.soil_moisture_index, unit: '/1.0', meta: 'root-zone index', spark: s.spark_precip },
    { lbl: 'Drought risk', ic: '🍃', col: dCol, val: s.drought_class, unit: '', meta: 'SPI-based class', spark: s.spark_temp },
  ];
  el('satKpis').innerHTML = kpis.map(k => `<div class="ckpi"><div class="ktop"><span class="lbl">${k.lbl}</span><span class="ic" style="background:${k.col}1c;color:${k.col}">${k.ic}</span></div><div class="val" style="color:${k.col}">${k.val}<small>${k.unit}</small></div><div class="meta">${k.meta}</div>${csparkline(k.spark, k.col)}</div>`).join('');

  const severe = s.drought_class === 'Severe' || s.temperature_anomaly_c > 1.3 || s.rainfall_anomaly_pct < -20;
  const watch = s.drought_class === 'Moderate' || s.drought_class === 'Mild';
  const stCol = severe ? CC.clay : watch ? CC.ochre : CC.teal, stLbl = severe ? 'Alert' : watch ? 'Watch' : 'Normal';
  const sevPct = ({ Normal: 20, Mild: 45, Moderate: 70, Severe: 95 })[s.drought_class] || 20;
  el('satSummary').innerHTML = `
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;flex-wrap:wrap"><span style="background:${stCol}1c;color:${stCol};font-family:var(--font-mono);font-size:11px;font-weight:600;padding:4px 11px;border-radius:20px">${stLbl}</span><span style="font-size:13px;color:var(--ink-soft)">${s.drought_class} drought · rainfall ${ra}% and temperature ${s.temperature_anomaly_c > 0 ? '+' : ''}${s.temperature_anomaly_c}°C vs the 1973–2023 normal.</span></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:11px 22px;font-size:13.5px;color:var(--ink-soft)">
          <div>Mean temperature <b>${s.mean_temp_c}°C</b></div><div>30-day precipitation <b>${s.precip_30d_mm} mm</b></div>
          <div>Rainfall anomaly <b>${ra}%</b></div><div>Warming trend <b>+${s.warming_trend_c_per_decade}°C/decade</b></div>
          <div>Districts monitored <b>9</b></div><div>Last assimilation <b>${s.as_of || '—'}</b></div></div>
        <div style="margin-top:18px"><div style="display:flex;justify-content:space-between;font-family:var(--font-mono);font-size:11.5px;color:var(--muted);margin-bottom:6px"><span>Soil-moisture index</span><span>${s.soil_moisture_index} / 1.0</span></div><div class="cbar"><i style="width:${(s.soil_moisture_index * 100).toFixed(0)}%;background:${soilCol(s.soil_moisture_index)}"></i></div></div>
        <div style="margin-top:13px"><div style="display:flex;justify-content:space-between;font-family:var(--font-mono);font-size:11.5px;color:var(--muted);margin-bottom:6px"><span>Drought severity</span><span>${s.drought_class}</span></div><div class="cbar"><i style="width:${sevPct}%;background:${stCol}"></i></div></div>`;

  try {
    const d = await api('/api/climate/data');
    const scol = { active: CC.teal, ingesting: CC.ochre, ready: CC.ocean, stale: CC.clay };
    const byLive = d.sources.slice().sort((a, b) => (b.status === 'active') - (a.status === 'active'));
    el('satPipe').innerHTML = byLive.slice(0, 4).map(x => { const c = scol[x.status] || CC.teal; return `<div class="csrc"><span class="sd" style="background:${c}"></span><div><div class="sn">${x.name}</div><div class="sr">${x.res} · ${x.role}</div></div><span class="st" style="background:${c}1c;color:${c}">${x.status}</span></div>`; }).join('');
  } catch { }
  try {
    const dj = await api('/api/climate/districts?layer=rain');
    el('satDistricts').innerHTML = dj.districts.map(t => { const tc = t.temp > 1.3 ? CC.clay : t.temp > 0.6 ? CC.ochre : CC.teal; return `<div class="cdist"><div class="dn">${t.name}</div><div class="dm"><span style="color:${rainCol(t.rain)}">🌧 ${t.rain > 0 ? '+' : ''}${t.rain}%</span><span style="color:${tc}">🌡 ${t.temp > 0 ? '+' : ''}${t.temp}°</span><span style="color:${soilCol(t.soil)}">💧 ${t.soil}</span></div></div>`; }).join('');
  } catch { el('satDistricts').innerHTML = '<div class="card-sub">District layer unavailable.</div>'; }

  satOvStamp = Date.now();
  if (!satOvTimer) { satOvTimer = setInterval(() => { if (currentView === 'region') loadClimateOverview(); }, 60000); setInterval(satOvTick, 1000); }
  satOvTick();
}

// ---- District/city map (real gridded, region-aware) ----
const GRID_VAR = { rain: 'rain', temp: 'tmean' };
let currentLayer = 'rain', mapRegion = 'jk', mapData = null, mapAbsmax = 1;
function lerp3(a, b, f) { return [Math.round(a[0] + (b[0] - a[0]) * f), Math.round(a[1] + (b[1] - a[1]) * f), Math.round(a[2] + (b[2] - a[2]) * f)]; }
function anomColor(v, layer, absmax) {
  if (v == null) return '#e9e0cc';
  const t = Math.max(-1, Math.min(1, v / (absmax || 1)));
  const neg = layer === 'temp' ? [47, 125, 154] : [214, 154, 72];
  const pos = layer === 'temp' ? [210, 105, 74] : [47, 125, 154];
  const mid = [243, 237, 224];
  const c = t < 0 ? lerp3(mid, neg, -t) : lerp3(mid, pos, t);
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}
let satMap = null, satOverlay = null, satMarkers = null, satFit = null, satBounds = null;
function fitSat() {
  if (!satMap || !satBounds) return;
  satMap.invalidateSize();
  // instant (non-animated) fit: deterministic even if the tab is backgrounded mid-switch
  satMap.fitBounds(satBounds, { padding: [12, 12], animate: false });
}
function initLeafletSat() {
  if (satMap) return;
  satMap = L.map('districtMap', { scrollWheelZoom: false, zoomSnap: 0.25 });
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 18, attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics',
  }).addTo(satMap);
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18, opacity: 0.9 }).addTo(satMap);
  satMarkers = L.layerGroup().addTo(satMap);
  satMap.on('mousemove', onSatHover);
  setTimeout(() => satMap.invalidateSize(), 60);
}
function initMap() {
  document.querySelectorAll('#omRegion .toggle').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('#omRegion .toggle').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); mapRegion = b.dataset.region;
    el('regionTitle').textContent = mapRegion === 'india' ? 'All India' : 'Jammu & Kashmir';
    el('monitoredHead').textContent = mapRegion === 'india' ? 'Cities monitored' : 'Districts monitored';
    fetchMap();
  }));
  document.querySelectorAll('#region .map-toolbar .toggle[data-layer]').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('#region .map-toolbar .toggle[data-layer]').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); currentLayer = b.dataset.layer; fetchMap();
  }));
  initLeafletSat();
  fetchMap();
}
async function fetchMap() {
  try { mapData = await api('/api/gridded/anomaly?var=' + GRID_VAR[currentLayer] + '&region=' + mapRegion); }
  catch { el('districtInfo').textContent = 'Ingest gridded data for this region to view the map.'; return; }
  mapAbsmax = Math.max(Math.abs(mapData.amin), Math.abs(mapData.amax)) || 1;
  el('monitoredList').textContent = mapData.districts.map(d => d.name).join(' · ');
  drawSatMap(); renderLegend();
}
function _gridBounds(g) {
  const r = g.res_deg, la = g.lats, lo = g.lons;
  return [[la[0] - r / 2, lo[0] - r / 2], [la[la.length - 1] + r / 2, lo[lo.length - 1] + r / 2]];
}
function _overlayURL(g) {
  const rows = g.anomaly.length, cols = g.anomaly[0].length;
  const cv = document.createElement('canvas'); cv.width = cols; cv.height = rows;
  const ctx = cv.getContext('2d');
  for (let i = 0; i < rows; i++) for (let j = 0; j < cols; j++) {
    const v = g.anomaly[i][j]; if (v == null) continue;
    ctx.fillStyle = anomColor(v, currentLayer, mapAbsmax);
    ctx.fillRect(j, rows - 1 - i, 1, 1);
  }
  return cv.toDataURL();
}
function drawSatMap() {
  if (!satMap) return;
  satMap.invalidateSize();
  if (satOverlay) { satMap.removeLayer(satOverlay); satOverlay = null; }
  satOverlay = L.imageOverlay(_overlayURL(mapData), _gridBounds(mapData), { opacity: 0.6, interactive: false }).addTo(satMap);
  satMarkers.clearLayers();
  mapData.districts.forEach(d => {
    if (d.lat == null) return;
    L.circleMarker([d.lat, d.lon], { radius: 4, color: '#1b2b27', weight: 2, fillColor: '#1b2b27', fillOpacity: 1 })
      .bindTooltip(d.name, { permanent: true, direction: 'right', className: 'mk-label', offset: [4, 0] }).addTo(satMarkers);
  });
  const bb = mapData.bbox; satBounds = [[bb[0], bb[2]], [bb[1], bb[3]]];
  if (satFit !== mapRegion) {
    fitSat(); setTimeout(fitSat, 150); satFit = mapRegion;   // re-fit after layout settles
  }
}
function onSatHover(e) {
  if (!mapData) return;
  const lat = e.latlng.lat, lon = e.latlng.lng, a = mapData;
  let ci = 0, cj = 0, bi = 1e9, bj = 1e9;
  a.lats.forEach((la, i) => { const dd = Math.abs(la - lat); if (dd < bi) { bi = dd; ci = i; } });
  a.lons.forEach((lo, j) => { const dd = Math.abs(lo - lon); if (dd < bj) { bj = dd; cj = j; } });
  const v = a.value[ci][cj], an = a.anomaly[ci][cj];
  const nm = currentLayer === 'rain' ? 'Rainfall' : 'Temperature', u = currentLayer === 'rain' ? ' mm/day' : '°C';
  el('districtInfo').innerHTML = `<b>${lat.toFixed(2)}°N, ${lon.toFixed(2)}°E</b> — ${nm}: <b>${v == null ? '—' : v}${u}</b> · anomaly <b style="color:${anomColor(an, currentLayer, mapAbsmax)}">${an == null ? '—' : (an > 0 ? '+' : '') + an}</b>`;
}
function renderLegend() {
  const stops = [-1, -.5, 0, .5, 1].map(t => anomColor(t * mapAbsmax, currentLayer, mapAbsmax));
  const unit = currentLayer === 'rain' ? 'mm/day' : '°C';
  el('legendBox').innerHTML = `<div style="height:12px;border-radius:6px;background:linear-gradient(90deg,${stops.join(',')})"></div>
        <div style="display:flex;justify-content:space-between;font-family:var(--font-mono);font-size:11px;color:var(--muted);margin-top:6px"><span>−${mapAbsmax.toFixed(1)}</span><span>0</span><span>+${mapAbsmax.toFixed(1)} ${unit}</span></div>
        <div style="font-family:var(--font-mono);font-size:11px;color:var(--muted);margin-top:8px">Anomaly = value − per-cell climatology</div>`;
}

// ---- What-if scenario (live API) ----
let whatIfChart, wiTimer;
function initWhatIf() {
  whatIfChart = new Chart(el('whatIfChart'), {
    type: 'bar',
    data: {
      labels: ['Soil moisture', 'Drought risk', 'Crop stress', 'Reservoir inflow'], datasets: [
        { label: 'Baseline', data: [], backgroundColor: '#d8cfb8', borderRadius: 4 },
        { label: 'Scenario', data: [], backgroundColor: '#14b8a6', borderRadius: 4 },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 400 },
      plugins: { legend: { labels: { color: '#857b67' } } },
      scales: { x: { grid: { display: false } }, y: { grid: { color: GRID }, border: { display: false } } }
    }
  });
  el('rainSlider').addEventListener('input', updateWhatIf);
  el('tempSlider').addEventListener('input', updateWhatIf);
  document.querySelectorAll('#scenarioPresets .preset-chip').forEach(btn => btn.addEventListener('click', () => {
    el('rainSlider').value = btn.dataset.rain; el('tempSlider').value = btn.dataset.temp; updateWhatIf();
  }));
  updateWhatIf();
}
const LVL_COL = { Low: '#2aa38a', Moderate: '#dd9138', Medium: '#dd9138', High: '#d2694a', Severe: '#b3402a' };
function updateWhatIf() {
  const rain = parseFloat(el('rainSlider').value), temp = parseFloat(el('tempSlider').value);
  el('rainVal').textContent = (rain > 0 ? '+' : '') + rain + '%';
  el('tempVal').textContent = (temp >= 0 ? '+' : '') + temp.toFixed(1) + '°C';
  clearTimeout(wiTimer);
  wiTimer = setTimeout(async () => {
    let s; try { s = await api('/api/climate/whatif', { method: 'POST', body: { rain_pct: rain, temp_c: temp } }); } catch { return; }
    const set = (id, txt, cls) => { const e = el(id); e.textContent = txt; e.className = 'v ' + cls; e.classList.remove('flash'); void e.offsetWidth; e.classList.add('flash'); };
    set('impSoil', s.soil_moisture_index, s.soil_moisture_index < 0.35 ? 'up' : s.soil_moisture_index > 0.45 ? 'down' : '');
    set('impDrought', s.drought_risk_score, s.drought_risk_score > 55 ? 'up' : s.drought_risk_score < 30 ? 'down' : 'warn');
    set('impCrop', s.crop_water_stress, ['High', 'Severe'].includes(s.crop_water_stress) ? 'up' : s.crop_water_stress === 'Low' ? 'down' : 'warn');
    set('impWater', (s.reservoir_inflow_change_pct >= 0 ? '+' : '') + s.reservoir_inflow_change_pct + '%', s.reservoir_inflow_change_pct < -15 ? 'up' : s.reservoir_inflow_change_pct > 10 ? 'down' : '');
    const b = s.baseline;
    whatIfChart.data.datasets[0].data = [b.soil_moisture_index * 100, b.drought_risk_score, b.crop_water_stress_score, 50 + b.reservoir_inflow_change_pct];
    whatIfChart.data.datasets[1].data = [s.soil_moisture_index * 100, s.drought_risk_score, s.crop_water_stress_score, 50 + s.reservoir_inflow_change_pct];
    whatIfChart.update('active');

    // sector impact panel
    if (s.sectors) el('scSectors').innerHTML = s.sectors.map(x => {
      const c = LVL_COL[x.risk_label] || '#857b67';
      return `<div class="sector-row"><div><div class="sname">${x.name}</div><div class="snote">${x.note}</div></div>
            <span class="sector-badge" style="background:${c}1c;color:${c}">${x.risk_label} · ${x.risk_score}</span></div>`;
    }).join('');
    // water balance panel
    const w = s.water_balance;
    if (w) el('scWater').innerHTML = `
          <div class="wb-row"><span>Rainfall input</span><b>${w.rain_in_mm} mm/day <span style="color:var(--muted)">(normal ${w.baseline_rain_mm})</span></b></div>
          <div class="wb-row"><span>Evapotranspiration demand</span><b>${w.et_out_mm} mm/day <span style="color:var(--muted)">(normal ${w.baseline_et_mm})</span></b></div>
          <div class="wb-row"><span>Net balance</span><b style="color:${w.net_mm < 0 ? 'var(--terracotta)' : 'var(--teal)'}">${w.net_mm > 0 ? '+' : ''}${w.net_mm} mm/day <span style="color:var(--muted)">(normal ${w.baseline_net_mm})</span></b></div>`;
    if (s.narrative) el('scNarrative').textContent = s.narrative;
    const bi = s.baseline_info;
    if (bi && el('scNarrative')) el('scNarrative').textContent +=
      ` Baseline: this season's normal (${bi.season}) from today's soil moisture ${bi.live_soil_moisture}` +
      `${bi.soil_as_of ? ' (as of ' + bi.soil_as_of + ')' : ''}.`;
  }, 120);
}

// ---- 14-day forecasts (real ML ensemble) ----
function buildForecast(canvasId, d, color, unit) {
  const ctx = el(canvasId).getContext('2d');
  const grad = ctx.createLinearGradient(0, 0, 0, 260); grad.addColorStop(0, color + '40'); grad.addColorStop(1, color + '05');
  const labels = [...d.observed.map(o => o.label), ...d.predicted.map(p => p.label)];
  const obs = [...d.observed.map(o => o.value), ...d.predicted.map(() => null)];
  const pad = d.observed.map(() => null);
  const pred = [...pad.slice(0, -1), d.observed.at(-1).value, ...d.predicted.map(p => p.value)];
  const up = [...pad, ...d.predicted.map(p => p.upper)];
  const lo = [...pad, ...d.predicted.map(p => p.lower)];
  new Chart(ctx, {
    type: 'line',
    data: {
      labels, datasets: [
        { label: 'Upper band', data: up, borderWidth: 0, pointRadius: 0, fill: '+1', backgroundColor: grad },
        { label: 'Lower band', data: lo, borderWidth: 0, pointRadius: 0, fill: false },
        { label: 'Predicted', data: pred, borderColor: color, backgroundColor: color, borderDash: [5, 4], pointRadius: 0, tension: 0.4, borderWidth: 2 },
        { label: 'Observed', data: obs, borderColor: INK, backgroundColor: INK, pointRadius: 3, tension: 0.4, borderWidth: 2 },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      plugins: { legend: { labels: { filter: (i) => i.text === 'Predicted' || i.text === 'Observed' } } },
      scales: { x: { grid: { color: GRID }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } }, y: { grid: { color: GRID }, title: { display: true, text: unit }, border: { display: false } } }
    }
  });
}
async function initForecasts() {
  try {
    const [r, t, sm, dr] = await Promise.all([
      api('/api/climate/forecast?var=rainfall'),
      api('/api/climate/forecast?var=temperature'),
      api('/api/climate/forecast?var=soil'),
      api('/api/climate/forecast?var=drought'),
    ]);
    buildForecast('rainChart', r, '#14b8a6', 'mm/day');
    buildForecast('tempChart', t, '#d2694a', '°C');
    buildForecast('soilChart', sm, '#1565C0', 'index');
    buildForecast('droughtChart', dr, '#dd9138', '/100');
    const sk = (v) => (v > 0 ? '+' : '') + v + '%';
    if (t.skill) {
      el('fcTempSkill').innerHTML = sk(t.skill.skill_pct);
      el('fcTempRmse').innerHTML = t.skill.rmse + '<small>°C</small>';
    }
    if (r.skill) {
      el('fcRainSkill').innerHTML = sk(r.skill.skill_pct);
      el('fcRainRmse').innerHTML = r.skill.rmse + '<small>mm</small>';
    }
  } catch { }
}

/* =========================================================
   SATELLITE ANALYSIS (backend-powered)
   ========================================================= */
let selectedFile = null, donutChart = null;
const dz = el('dropzone'), fi = el('fileInput');
dz.addEventListener('click', () => fi.click());
dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.classList.add('drag'); });
dz.addEventListener('dragleave', () => dz.classList.remove('drag'));
dz.addEventListener('drop', (e) => { e.preventDefault(); dz.classList.remove('drag'); pickFile(e.dataTransfer.files[0]); });
fi.addEventListener('change', (e) => pickFile(e.target.files[0]));
function pickFile(f) {
  if (!f) return; selectedFile = f;
  el('dzEmpty').hidden = true; const img = el('dzPreview'); img.src = URL.createObjectURL(f); img.hidden = false;
  el('fileName').textContent = 'Selected: ' + f.name;
  if (!el('optName').value) el('optName').value = f.name.replace(/\.[^.]+$/, '');
  el('runBtn').disabled = false; el('clearBtn').hidden = false;
}
el('optClusters').addEventListener('input', (e) => el('clusterVal').textContent = e.target.value);
el('clearBtn').addEventListener('click', resetUpload);
el('newBtn').addEventListener('click', () => { resetUpload(); if (typeof showView === 'function') showView('workspace'); });
function resetUpload() {
  selectedFile = null; fi.value = '';
  el('dzEmpty').hidden = false; el('dzPreview').hidden = true; el('fileName').textContent = '';
  el('optName').value = ''; el('optLat').value = ''; el('optLon').value = '';
  el('runBtn').disabled = true; el('clearBtn').hidden = true;
  el('resultArea').hidden = true; el('uploadArea').hidden = false; el('uploadErr').hidden = true;
}
el('runBtn').addEventListener('click', async () => {
  if (!selectedFile) return;
  el('uploadErr').hidden = true; el('processing').hidden = false; el('runBtn').disabled = true;
  try {
    const fd = new FormData(); fd.append('file', selectedFile);
    if (el('optName').value) fd.append('name', el('optName').value);
    if (el('optLat').value) fd.append('lat', el('optLat').value);
    if (el('optLon').value) fd.append('lon', el('optLon').value);
    fd.append('clusters', el('optClusters').value);
    const a = await api('/api/analysis', { method: 'POST', form: fd });
    renderResult(a); toast('Analysis complete — ' + a.name); loadDashboard(); loadReports();
  } catch (ex) { el('uploadErr').textContent = ex.message; el('uploadErr').hidden = false; }
  finally { el('processing').hidden = true; el('runBtn').disabled = false; }
});
function renderResult(a) {
  el('uploadArea').hidden = true; el('resultArea').hidden = false;
  el('resTitle').textContent = '✓ ' + a.name;
  const accTxt = (a.model_accuracy != null) ? ` · ${a.model_accuracy}% test acc` : '';
  el('resMeta').textContent = `Confidence ${a.confidence}%${accTxt} · ${a.width}×${a.height}px · ${a.created_at}`;
  el('resDim').textContent = a.model_type ? `${a.width} × ${a.height} px · ${a.model_type}` : `${a.width} × ${a.height} px · 5 classes`;
  el('resObjCount').textContent = (a.objects?.length || 0) + ' detections';
  el('resOrig').src = a.original_url; el('resSeg').src = a.segmentation_url; el('resDet').src = a.detection_url;
  if (a.report_url) { el('resPdf').href = a.report_url; el('resPdf').hidden = false; } else el('resPdf').hidden = true;
  if (donutChart) donutChart.destroy(); donutChart = landDonut('resDonut', a.land_cover);
  el('resLegend').innerHTML = Object.entries(a.land_cover).map(([k, v]) => `<div class="lg"><span class="sw" style="background:${CLASS_HEX[k]}"></span>${k} — <b style="color:var(--text)">${v.toFixed(1)}%</b></div>`).join('');
  const counts = a.object_counts || {};
  el('resObjs').innerHTML = Object.keys(counts).length ? Object.entries(counts).map(([k, v]) => `<div class="objchip"><span class="sw" style="width:10px;height:10px;border-radius:3px;background:${OBJ_HEX[k] || '#888'}"></span>${k} <b>${v}</b></div>`).join('') : '<span class="mono" style="color:var(--muted)">No discrete objects detected.</span>';
  el('gaugeArc').style.strokeDashoffset = 289 * (1 - a.confidence / 100); el('gaugeVal').textContent = a.confidence + '%';
  el('resultArea').scrollIntoView({ behavior: 'smooth' });
}
function landDonut(canvasId, lc) {
  const labels = Object.keys(lc), values = labels.map(k => lc[k]);
  return new Chart(el(canvasId), {
    type: 'doughnut',
    data: { labels, datasets: [{ data: values, backgroundColor: labels.map(k => CLASS_HEX[k]), borderColor: '#fffefb', borderWidth: 2, hoverOffset: 6 }] },
    options: { cutout: '62%', maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 12, padding: 12 } }, tooltip: { callbacks: { label: (c) => ' ' + c.label + ': ' + c.parsed.toFixed(1) + '%' } } } }
  });
}

// ---- Change detection ----
let beforeFile = null, afterFile = null, chDeltaChart = null;
function wireDz(dzId, emptyId, prevId, inputId, setter) {
  const d = el(dzId), inp = el(inputId);
  d.addEventListener('click', () => inp.click());
  d.addEventListener('dragover', (e) => { e.preventDefault(); d.classList.add('drag'); });
  d.addEventListener('dragleave', () => d.classList.remove('drag'));
  d.addEventListener('drop', (e) => { e.preventDefault(); d.classList.remove('drag'); handle(e.dataTransfer.files[0]); });
  inp.addEventListener('change', (e) => handle(e.target.files[0]));
  function handle(f) { if (!f) return; setter(f); el(emptyId).hidden = true; const img = el(prevId); img.src = URL.createObjectURL(f); img.hidden = false; checkChangeReady(); }
}
wireDz('beforeDz', 'beforeEmpty', 'beforePrev', 'beforeInput', (f) => beforeFile = f);
wireDz('afterDz', 'afterEmpty', 'afterPrev', 'afterInput', (f) => afterFile = f);
function checkChangeReady() { el('changeBtn').disabled = !(beforeFile && afterFile); el('changeClear').hidden = !(beforeFile || afterFile); }
el('changeClear').addEventListener('click', () => {
  beforeFile = afterFile = null; el('beforeInput').value = ''; el('afterInput').value = '';
  el('beforeEmpty').hidden = false; el('afterEmpty').hidden = false; el('beforePrev').hidden = true; el('afterPrev').hidden = true;
  el('changeResult').hidden = true; checkChangeReady();
});
el('changeBtn').addEventListener('click', async () => {
  el('changeErr').hidden = true; el('changeProc').hidden = false; el('changeBtn').disabled = true;
  try {
    const fd = new FormData(); fd.append('before', beforeFile); fd.append('after', afterFile);
    if (el('changeName').value) fd.append('name', el('changeName').value);
    const c = await api('/api/change', { method: 'POST', form: fd });
    renderChange(c); toast('Change detection complete'); loadChangeHistory();
  } catch (ex) { el('changeErr').textContent = ex.message; el('changeErr').hidden = false; }
  finally { el('changeProc').hidden = true; el('changeBtn').disabled = false; }
});
function renderChange(c) {
  el('changeResult').hidden = false;
  el('chBefore').src = c.before_url; el('chAfter').src = c.after_url; el('chMap').src = c.change_map_url;
  el('chPercent').textContent = c.changed_percent + '%';
  const chAcc = (c.model_accuracy != null) ? ' · ' + c.model_accuracy + '% test acc' : '';
  let trTxt = '';
  if (c.transitions && c.transitions.length) {
    const t = c.transitions[0];
    trTxt = ` · main shift ${t.from}→${t.to} (${t.pct}%)`;
  }
  el('chConf').textContent = 'of the scene changed · confidence ' + c.confidence + '%' + chAcc + trTxt;
  const labels = Object.keys(c.class_deltas), vals = labels.map(k => c.class_deltas[k]);
  if (chDeltaChart) chDeltaChart.destroy();
  chDeltaChart = new Chart(el('chDeltaChart'), {
    type: 'bar',
    data: { labels, datasets: [{ data: vals, backgroundColor: vals.map(v => v >= 0 ? '#2E7D32' : '#E53935'), borderRadius: 5 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { grid: { color: GRID }, ticks: { callback: (v) => v + '%' } } } }
  });

  if (c.ecological_impact) {
    const eco = c.ecological_impact;
    const ecoCard = el('chEcoCard');
    if (ecoCard) {
      ecoCard.style.display = 'block';
      el('chEcoDetails').innerHTML = `
            Forest Delta: <b>${eco.forest_loss_ha > 0 ? '-' + eco.forest_loss_ha : '0'} ha</b> · 
            Estimated Biomass Flux: <b>${eco.biomass_loss_tons > 0 ? '-' + eco.biomass_loss_tons + ' t' : 'Stable'}</b> · 
            Gross Carbon Flux: <b>${eco.carbon_flux_tco2e > 0 ? '+' + eco.carbon_flux_tco2e + ' tCO₂e' : '0 tCO₂e'}</b>
          `;
    }
  }
  el('changeResult').scrollIntoView({ behavior: 'smooth' });
}
async function loadChangeHistory() {
  try {
    const items = await api('/api/change');
    if (!items.length) { el('changeHistory').hidden = true; return; }
    el('changeHistory').hidden = false;
    el('changeHistoryList').innerHTML = items.map(h => `<div class="ritem"><div><div class="rn">${h.name}</div><div class="rd">${h.created_at}</div></div><span class="rc"><span class="tag" style="background:#fbeae4;color:#b8492c">${h.changed_percent}% changed</span> · ${h.confidence}%</span></div>`).join('');
  } catch { }
}

// ---- Dashboard ----
let dashDonut = null, dashBar = null, dashLine = null, dashObj = null;
async function loadDashboard() {
  let d; try { d = await api('/api/dashboard'); } catch { return; }
  if (d.totals.images === 0) { el('dashEmpty').hidden = false; el('dashContent').hidden = true; return; }
  el('dashEmpty').hidden = true; el('dashContent').hidden = false;
  const lc = d.land_cover;
  if (dashDonut) dashDonut.destroy(); dashDonut = landDonut('dashDonut', lc);
  const dl = d.land_cover_delta, dlL = Object.keys(dl), dlV = dlL.map(k => dl[k]);
  if (dashBar) dashBar.destroy();
  dashBar = new Chart(el('dashBar'), { type: 'bar', data: { labels: dlL, datasets: [{ data: dlV, backgroundColor: dlV.map(v => v >= 0 ? '#2E7D32' : '#E53935'), borderRadius: 5 }] }, options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { grid: { color: GRID }, ticks: { callback: (v) => v + '%' } } } } });
  const ot = d.object_totals, otL = Object.keys(ot), otV = otL.map(k => ot[k]);
  el('dashObjSub').textContent = 'Total detections across all scenes (' + d.totals.objects + ')';
  if (dashObj) dashObj.destroy();
  dashObj = new Chart(el('dashObjChart'), { type: 'bar', data: { labels: otL, datasets: [{ data: otV, backgroundColor: '#14b8a6', borderRadius: 5 }] }, options: { indexAxis: 'y', maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { color: GRID }, ticks: { precision: 0 } }, y: { grid: { display: false } } } } });
  const tr = d.trend, trL = tr.map((x, i) => x.name?.slice(0, 10) || ('#' + (i + 1))), trV = tr.map(x => x.confidence);
  el('dashConfSub').textContent = 'Average confidence: ' + d.avg_confidence + '%';
  if (dashLine) dashLine.destroy();
  dashLine = new Chart(el('dashLine'), { type: 'line', data: { labels: trL, datasets: [{ data: trV, borderColor: '#14b8a6', backgroundColor: 'rgba(20,184,166,.14)', fill: true, tension: .35, pointRadius: 3, pointBackgroundColor: '#14b8a6' }] }, options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { min: 0, max: 100, grid: { color: GRID }, ticks: { callback: (v) => v + '%' } } } } });
  el('recentList').innerHTML = d.recent.map(r => `<div class="ritem" data-id="${r.id}"><img src="${r.thumb}" alt="" /><div><div class="rn">${r.name}</div><div class="rd">${r.created_at}</div></div><span class="rc"><span class="tag" style="background:${(CLASS_HEX[r.dominant] || '#888')}22;color:${CLASS_HEX[r.dominant] || '#777'}">${r.dominant}</span> · ${r.confidence}%</span></div>`).join('');
  el('recentList').querySelectorAll('.ritem').forEach(item => item.addEventListener('click', () => openAnalysis(item.dataset.id)));
}
async function openAnalysis(id) { try { const a = await api('/api/analysis/' + id); renderResult(a); el('uploadArea').hidden = true; } catch (ex) { toast(ex.message); } }

// ---- Reports ----
async function loadReports() {
  let items; try { items = await api('/api/analysis'); } catch { return; }
  const withReport = items.filter(a => a.report_url).length;
  const rc = el('repCount'); if (rc) rc.textContent = withReport || items.length;
  if (!items.length) { el('reportsList').innerHTML = '<div class="empty"><div class="em-ic">▤</div>No reports yet — analyse a scene to generate one.</div>'; return; }
  el('reportsList').innerHTML = items.map(a => `<div class="ritem"><img src="${a.segmentation_url}" alt="" /><div><div class="rn">${a.name}</div><div class="rd">${a.created_at} · ${a.confidence}%</div></div><span class="rc">${a.report_url ? `<a class="btn btn-ghost btn-sm" href="${a.report_url}" target="_blank" rel="noreferrer">▤ PDF</a>` : '<span style="color:var(--muted)">no report</span>'}</span></div>`).join('');
}

// ---- Reveal on scroll ----
const io = new IntersectionObserver((entries) => entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { threshold: .12 });
document.querySelectorAll('.reveal').forEach(x => io.observe(x));

boot();
