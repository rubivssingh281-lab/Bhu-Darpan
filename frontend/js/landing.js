Chart.defaults.color = '#6f847b';
Chart.defaults.font.family = "'JetBrains Mono',monospace";
Chart.defaults.font.size = 11;
Chart.defaults.borderColor = '#e6dfce';
const GRID = '#efe7d6';
const el = id => document.getElementById(id);
const API_BASE = (window.location.hostname === 'localhost' && window.location.port === '8010')
  ? 'http://localhost:8000'
  : '';
const api = async (p, o) => {
  const url = p.startsWith('http') ? p : API_BASE + (p.startsWith('/') ? p : '/' + p);
  let res;
  for (let attempt = 0; attempt < 4; attempt++) {
    res = await fetch(url, o);
    if (res.status !== 502 && res.status !== 503 && res.status !== 504) break;
    if (attempt < 3) await new Promise(ok => setTimeout(ok, (attempt + 1) * 2000));
  }
  const text = await res.text();
  let data = {};
  if (text) {
    try { data = JSON.parse(text); } catch { data = {}; }
  }
  if (!res.ok) throw new Error(data.detail || (`Request failed (${res.status})`));
  return data;
};

// Anomaly colour scales (teal / ochre / terracotta / water)
const C = { clay: '#d2694a', ochre: '#dd9138', seaweed: '#2aa38a', ocean: '#2f7d9a', algae: '#0e9c8a' };
const scales = {
  rain: v => v < -20 ? C.clay : v < -10 ? C.ochre : v > 25 ? C.ocean : C.seaweed,
  temp: v => v > 1.8 ? C.clay : v > 1.3 ? C.ochre : C.seaweed,
  soil: v => v < 0.35 ? C.clay : v < 0.45 ? C.ochre : C.seaweed,
};
const legends = {
  rain: [['Severe deficit (< −20%)', C.clay], ['Moderate (−20 to −10%)', C.ochre], ['Near normal', C.seaweed], ['Surplus (> +25%)', C.ocean]],
  temp: [['High (> +1.8°C)', C.clay], ['Elevated (+1.3 to +1.8°C)', C.ochre], ['Normal', C.seaweed]],
  soil: [['Dry (< 0.35)', C.clay], ['Low (0.35–0.45)', C.ochre], ['Adequate (> 0.45)', C.seaweed]],
};

// ---------- Tabs ----------
const loaded = {};
function show(tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.querySelectorAll('.view').forEach(v => v.hidden = v.id !== 'v-' + tab);
  if (!loaded[tab]) { loaders[tab] && loaders[tab](); loaded[tab] = true; }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
el('tabs').addEventListener('click', e => { const b = e.target.closest('.tab'); if (b) show(b.dataset.tab); });
document.addEventListener('click', e => { const b = e.target.closest('.ov-btn[data-tab]'); if (b) { e.preventDefault(); show(b.dataset.tab); } });

// ---------- Sparkline ----------
function sparkline(values, color) {
  const w = 100, h = 34, min = Math.min(...values), max = Math.max(...values), rng = (max - min) || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1) * w).toFixed(1)},${(h - 4 - (v - min) / rng * (h - 8)).toFixed(1)}`).join(' ');
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

// ---------- Overview (EO mission hero — live telemetry + stat band) ----------
async function loadOverview() {
  const s = await api('/api/climate/current');
  const warn = cond => cond ? 'tele-value warn' : 'tele-value';
  const setTele = (id, txt, hot) => { const e = el(id); if (!e) return; e.textContent = txt; e.className = warn(hot) + (id === 'tAsOf' ? '' : ''); };
  el('tRain').textContent = (s.rainfall_anomaly_pct > 0 ? '+' : '') + s.rainfall_anomaly_pct;
  el('tRain').className = warn(s.rainfall_anomaly_pct < -20);
  el('tTemp').textContent = (s.temperature_anomaly_c > 0 ? '+' : '') + s.temperature_anomaly_c;
  el('tTemp').className = warn(s.temperature_anomaly_c > 1.3);
  el('tSoil').textContent = s.soil_moisture_index;
  el('tSoil').className = warn(s.soil_moisture_index < 0.35);
  const dd = el('tDrought'); dd.textContent = s.drought_class; dd.className = warn(['Severe', 'Moderate'].includes(s.drought_class));
  el('tAsOf').textContent = s.as_of || '—';
  el('tAsOf').style.cssText = 'font-size:14px;color:var(--muted)';

  try {
    const [d, lc] = await Promise.all([api('/api/climate/data'), api('/api/analysis/model').catch(() => ({}))]);
    const cvAcc = lc.test_accuracy != null ? (+lc.test_accuracy).toFixed(1) : '—';
    const active = d.sources.filter(x => (x.status || '').toLowerCase() === 'active').length;
    const skills = d.models.map(m => m.skill_pct).filter(v => v != null);
    const meanSkill = skills.length ? Math.round(skills.reduce((a, b) => a + b, 0) / skills.length) : null;
    const yrs = Math.round(d.record_days / 365);
    el('ovMission').innerHTML = `
          <span class="mission-chip"><span class="cdot"></span>SYSTEMS <b>NOMINAL</b></span>
          <span class="mission-chip"><span class="cdot ${active < d.sources.length ? 'amber' : ''}"></span>DATA LINK <b>${active}/${d.sources.length} ONLINE</b></span>
          <span class="mission-chip">FUSION GRID <b>0.25°</b></span>
          <span class="mission-chip">CV MODEL <b>${cvAcc}%</b></span>
          <span class="mission-chip">LAST DOWNLINK <b>${s.as_of || '—'}</b></span>`;
    el('ovStatband').innerHTML = [
      { n: (d.record_days / 1000).toFixed(1) + '<small>k</small>', l: 'Daily records · ' + yrs + ' yr' },
      { n: cvAcc + '<small>%</small>', l: 'Land-cover CNN · test' },
      { n: meanSkill != null ? '+' + meanSkill + '<small>%</small>' : '—', l: 'Mean forecast skill' },
      { n: d.sources.length, l: 'Data sources' },
      { n: '9', l: 'Districts monitored' },
      { n: '14<small>d</small>', l: 'Forecast horizon' },
    ].map(x => `<div class="statband-item"><div class="sb-num">${x.n}</div><div class="sb-lbl">${x.l}</div></div>`).join('');
  } catch { }

  // live seasonal signals (current-record hazards — summarised, detailed on Hazards)
  try {
    const [mo, dr, an] = await Promise.all([
      api('/api/hazards/monsoon'), api('/api/hazards/drought'), api('/api/hazards/analytics')]);
    const tiles = [
      { n: mo.progress_pct + '%', l: `Monsoon · JJAS ${mo.year}`, s: `${mo.received_mm} / ${mo.seasonal_normal_mm} mm normal`, col: mo.progress_pct >= 90 ? C.ocean : C.ochre },
      { n: (dr.value > 0 ? '+' : '') + dr.value, l: 'Drought index · SPI-3', s: `${dr.class} · ${dr.as_of}`, col: dr.value <= -1 ? C.clay : C.seaweed },
      { n: '+' + an.warming.slope_c_per_decade + '°C', l: 'Warming / decade', s: an.warming.span, col: C.clay },
      { n: an.extreme_rain.latest_days, l: `Heavy-rain days · ${an.extreme_rain.latest_year}`, s: `vs ${an.extreme_rain.baseline_days}/yr normal`, col: C.ocean },
    ];
    el('ovSeason').innerHTML = tiles.map(t => `<div class="season-tile"><div class="n" style="color:${t.col}">${t.n}</div><div class="l">${t.l}</div><div class="s">${t.s}</div></div>`).join('');
  } catch { el('ovSeason').innerHTML = '<div class="cs">Seasonal signals unavailable.</div>'; }

  ovStamp = Date.now();
  if (!ovTimer) {
    ovTimer = setInterval(() => { if (!document.getElementById('v-overview').hidden) loadOverview(); }, 60000);
    setInterval(ovTick, 1000);   // live "updated Ns ago" ticker
  }
  ovTick();
}
let ovStamp = 0, ovTimer = null;
function ovTick() {
  if (!ovStamp) return;
  const s = Math.round((Date.now() - ovStamp) / 1000);
  const ago = s < 60 ? s + 's ago' : Math.floor(s / 60) + 'm ' + (s % 60) + 's ago';
  el('ovLive').innerHTML = `<span class="dot" style="display:inline-block;margin-right:6px"></span>Live · auto-refresh 60s · updated ${ago}`;
}
const statusCol = { active: C.seaweed, ingesting: C.ochre, ready: C.ocean, stale: C.clay };
function srcRow(x) {
  const c = statusCol[x.status] || C.seaweed;
  const asOf = x.as_of ? ` · data to ${x.as_of}` : '';
  return `<div class="src"><span class="sd" style="background:${c}"></span><div><div class="sn">${x.name}</div><div class="sr">${x.res} · ${x.role}${asOf}</div></div><span class="st" style="background:${c}1c;color:${c}">${x.status}</span></div>`;
}

// ---------- Map (real gridded, geographic) ----------
const JK_BBOX = [32.0, 37.0, 73.0, 80.0];  // lat0,lat1,lon0,lon1
const DIST_LL = { Baramulla: [34.20, 74.35], Srinagar: [34.08, 74.80], Kishtwar: [33.31, 75.77], Doda: [33.15, 75.55], Anantnag: [33.73, 75.15], Udhampur: [32.93, 75.13], Rajouri: [33.38, 74.31], Kathua: [32.37, 75.52], Jammu: [32.73, 74.87] };
const GRID_VAR = { rain: 'rain', temp: 'tmean' };
const LEADS = [['Now', 0], ['+1 day', 1], ['+3 days', 3], ['+7 days', 7]];
let curLayer = 'rain', curGrid = null, curDistricts = [], curLead = 0, scaleRef = null, curRegion = 'jk';
let lmap = null, lOverlay = null, lMarkers = null, lastFit = null;

function initLeaflet() {
  if (lmap) return;
  lmap = L.map('map', { scrollWheelZoom: false, zoomSnap: 0.25, attributionControl: true });
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 18, attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics',
  }).addTo(lmap);
  // place-name + boundary reference labels on top of the satellite imagery
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 18, opacity: 0.9,
  }).addTo(lmap);
  lMarkers = L.layerGroup().addTo(lmap);
  lmap.on('mousemove', onMapHover);
  const bb = JK_BBOX; lmap.fitBounds([[bb[0], bb[2]], [bb[1], bb[3]]]);
  setTimeout(() => lmap.invalidateSize(), 60);
}

async function loadMap() {
  document.querySelectorAll('#v-map .toolbar .toggle[data-layer]').forEach(b => b.addEventListener('click', () => {
    if (b.disabled || (b.dataset.layer === 'soil' && curRegion === 'india')) return;   // soil is J&K-only
    document.querySelectorAll('#v-map .toolbar .toggle[data-layer]').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); curLayer = b.dataset.layer; curLead = 0; fetchLayer();
  }));
  document.querySelectorAll('#regionCtl .toggle').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('#regionCtl .toggle').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); curRegion = b.dataset.region; curLead = 0;
    // soil is J&K-only; fall back to rainfall for the national view
    if (curRegion === 'india' && curLayer === 'soil') {
      curLayer = 'rain';
      document.querySelectorAll('#v-map .toolbar .toggle[data-layer]').forEach(x => x.classList.toggle('active', x.dataset.layer === 'rain'));
    }
    const soilBtn = document.querySelector('#v-map .toggle[data-layer="soil"]');
    soilBtn.disabled = curRegion === 'india';
    soilBtn.style.opacity = curRegion === 'india' ? .4 : 1;
    soilBtn.title = curRegion === 'india' ? 'Soil moisture is modelled for the J&K pilot only' : '';
    fetchLayer();
  }));
  fetchLayer();
}
let mapView = 'stylized';
function ns(t) { return document.createElementNS('http://www.w3.org/2000/svg', t); }
function _projS(lat, lon, W, H, bb, pad) {
  const px = pad * W, py = pad * H;
  return [px + (lon - bb[2]) / (bb[3] - bb[2]) * (W - 2 * px), py + (bb[1] - lat) / (bb[1] - bb[0]) * (H - 2 * py)];
}
function _hull(P) {
  if (P.length < 3) return P;
  P = P.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cr = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo = []; for (const p of P) { while (lo.length >= 2 && cr(lo[lo.length - 2], lo[lo.length - 1], p) <= 0) lo.pop(); lo.push(p); }
  const up = []; for (let i = P.length - 1; i >= 0; i--) { const p = P[i]; while (up.length >= 2 && cr(up[up.length - 2], up[up.length - 1], p) <= 0) up.pop(); up.push(p); }
  up.pop(); lo.pop(); return lo.concat(up);
}
function renderStylized() {
  const svg = el('mapStyled'), W = 900, H = 560; svg.innerHTML = '';
  const dd = curDistricts.filter(d => d.lat != null);
  let a0 = Math.min(...dd.map(d => d.lat)), a1 = Math.max(...dd.map(d => d.lat)),
    o0 = Math.min(...dd.map(d => d.lon)), o1 = Math.max(...dd.map(d => d.lon));
  if (a1 - a0 < 0.5) { a0 -= 0.5; a1 += 0.5; } if (o1 - o0 < 0.5) { o0 -= 0.5; o1 += 0.5; }
  const bb = dd.length ? [a0, a1, o0, o1] : (curGrid && curGrid.bbox) || JK_BBOX;
  const marks = dd.map(d => ({ d, xy: _projS(d.lat, d.lon, W, H, bb, 0.1) }));
  if (marks.length >= 3) {
    let hull = _hull(marks.map(m => m.xy));
    const cx = hull.reduce((s, p) => s + p[0], 0) / hull.length, cy = hull.reduce((s, p) => s + p[1], 0) / hull.length;
    hull = hull.map(([x, y]) => { const dx = x - cx, dy = y - cy, d = Math.hypot(dx, dy) || 1; return [x + dx / d * 46, y + dy / d * 46]; });
    const poly = ns('path');
    poly.setAttribute('d', 'M' + hull.map(p => p.map(v => v.toFixed(0)).join(',')).join(' L') + ' Z');
    poly.setAttribute('fill', '#efe7d6'); poly.setAttribute('stroke', '#d8ccae'); poly.setAttribute('stroke-width', '2'); poly.setAttribute('stroke-linejoin', 'round');
    svg.appendChild(poly);
  }
  const absmax = scaleRef || (curGrid ? Math.max(Math.abs(curGrid.amin), Math.abs(curGrid.amax)) : 1) || 1;
  const big = marks.length > 10;
  marks.forEach(({ d, xy }) => {
    const col = curGrid ? anomColor(d.anomaly, curLayer, absmax) : scales.soil(d.value);
    const base = big ? 12 : 22, r = base + (curGrid ? Math.min(big ? 8 : 16, Math.abs(d.anomaly) / absmax * (big ? 8 : 16)) : 6);
    const g = ns('g'); g.style.cursor = 'pointer';
    const ring = ns('circle'); ring.setAttribute('cx', xy[0]); ring.setAttribute('cy', xy[1]); ring.setAttribute('r', r);
    ring.setAttribute('fill', col); ring.setAttribute('fill-opacity', '.28'); ring.setAttribute('stroke', col); ring.setAttribute('stroke-width', '2'); g.appendChild(ring);
    const core = ns('circle'); core.setAttribute('cx', xy[0]); core.setAttribute('cy', xy[1]); core.setAttribute('r', big ? 3.5 : 5); core.setAttribute('fill', col); g.appendChild(core);
    const t = ns('text'); t.setAttribute('x', xy[0]); t.setAttribute('y', xy[1] + r + (big ? 13 : 18)); t.setAttribute('text-anchor', 'middle');
    t.setAttribute('font-family', "'JetBrains Mono',monospace"); t.setAttribute('font-size', big ? 11 : 14); t.setAttribute('fill', '#4a4433'); t.textContent = d.name; g.appendChild(t);
    g.addEventListener('mouseenter', () => stylizedInfo(d)); g.addEventListener('click', () => stylizedInfo(d));
    svg.appendChild(g);
  });
}
function stylizedInfo(d) {
  const u = curLayer === 'rain' ? ' mm/day' : curLayer === 'temp' ? '°C' : '';
  const val = curGrid ? d.anomaly : d.value; const s = (val > 0 && curGrid) ? '+' : '';
  const nm = curLayer === 'rain' ? 'Rainfall' : curLayer === 'temp' ? 'Temperature' : 'Soil moisture';
  el('distinfo').innerHTML = curGrid
    ? `<b>${d.name}</b> — ${nm} anomaly: <b style="color:${anomColor(d.anomaly, curLayer, scaleRef || 1)}">${s}${val}${u}</b>`
    : `<b>${d.name}</b> — Soil moisture: <b>${val}</b>`;
}
function buildTimeCtl() {
  if (curLayer === 'soil') { el('timeCtl').innerHTML = ''; return; }
  el('timeCtl').innerHTML = LEADS.map(([lbl, L]) =>
    `<button class="toggle ${L === curLead ? 'active' : ''}" data-lead="${L}">${lbl}</button>`).join('');
  el('timeCtl').querySelectorAll('.toggle').forEach(b => b.addEventListener('click', () => setLead(+b.dataset.lead)));
}
async function setLead(L) {
  if (curLayer === 'soil') return;               // soil has no gridded forecast
  curLead = L; buildTimeCtl();
  if (L === 0) await loadAnalysis(); else await loadMapForecast(L);
}
// Each map request gets a sequence number; a response is applied only if no newer
// request (layer / region / lead change) has been issued since — prevents a slow,
// stale response from overwriting the current selection.
let mapReq = 0;
function proj(lat, lon, W, H, bb) { return [(lon - bb[2]) / (bb[3] - bb[2]) * W, (bb[1] - lat) / (bb[1] - bb[0]) * H]; }
function invproj(x, y, W, H, bb) { return [bb[1] - (y / H) * (bb[1] - bb[0]), bb[2] + (x / W) * (bb[3] - bb[2])]; }
function lerp3(a, b, f) { return [Math.round(a[0] + (b[0] - a[0]) * f), Math.round(a[1] + (b[1] - a[1]) * f), Math.round(a[2] + (b[2] - a[2]) * f)]; }
function anomColor(v, layer, absmax) {
  if (v == null) return '#e9e0cc';
  const t = Math.max(-1, Math.min(1, v / (absmax || 1)));
  const neg = layer === 'temp' ? [47, 125, 154] : [214, 154, 72];   // temp−: blue · rain−: ochre (dry)
  const pos = layer === 'temp' ? [210, 105, 74] : [47, 125, 154];   // temp+: terracotta · rain+: blue (wet)
  const mid = [243, 237, 224];
  const c = t < 0 ? lerp3(mid, neg, -t) : lerp3(mid, pos, t);
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}
async function fetchLayer() {
  buildTimeCtl();
  if (curLayer === 'soil') {
    const my = ++mapReq;
    const r = await api('/api/climate/districts?layer=soil');
    if (my !== mapReq) return;
    curGrid = null; scaleRef = null;
    curDistricts = r.districts.map(d => ({ name: d.name, value: d.value, anomaly: null, lat: (DIST_LL[d.name] || [null])[0], lon: (DIST_LL[d.name] || [null, null])[1] }));
    el('mapCaption').textContent = 'Soil moisture · modelled (gridded soil not yet ingested)';
    drawMap(); renderLegend(); renderRanking(); return;
  }
  await loadAnalysis();
}
async function loadAnalysis() {
  const my = ++mapReq;
  const a = await api(`/api/gridded/anomaly?var=${GRID_VAR[curLayer]}&region=${curRegion}`);
  if (my !== mapReq) return;
  curGrid = a; curDistricts = a.districts;
  scaleRef = Math.max(Math.abs(a.amin), Math.abs(a.amax)) || 1;
  el('mapCaption').textContent = `${a.source} · ${a.res_deg}° grid · ${a.period} · per-cell anomaly vs climatology`;
  drawMap(); renderLegend(); renderRanking();
}
async function loadMapForecast(L) {
  const my = ++mapReq;
  const f = await api(`/api/gridded/forecast?var=${GRID_VAR[curLayer]}&lead=${L}&region=${curRegion}`);
  if (my !== mapReq) return;
  curGrid = f; curDistricts = f.districts;
  const sk = f.skill ? `skill ${f.skill.skill_vs_clim_pct > 0 ? '+' : ''}${f.skill.skill_vs_clim_pct}% vs climatology` : '';
  el('mapCaption').textContent = [`Forecast +${L}d`, f.target_date, f.method || 'forecast', sk].filter(Boolean).join(' · ');
  drawMap(); renderLegend(); renderRanking();
}
function _gridBounds(g) {
  const r = g.res_deg, la = g.lats, lo = g.lons;
  return [[la[0] - r / 2, lo[0] - r / 2], [la[la.length - 1] + r / 2, lo[lo.length - 1] + r / 2]];
}
function _overlayURL(g) {
  const rows = g.anomaly.length, cols = g.anomaly[0].length;
  const cv = document.createElement('canvas'); cv.width = cols; cv.height = rows;
  const ctx = cv.getContext('2d');
  const absmax = scaleRef || (Math.max(Math.abs(g.amin), Math.abs(g.amax)) || 1);
  for (let i = 0; i < rows; i++) for (let j = 0; j < cols; j++) {
    const v = g.anomaly[i][j]; if (v == null) continue;
    ctx.fillStyle = anomColor(v, curLayer, absmax);
    ctx.fillRect(j, rows - 1 - i, 1, 1);   // north (highest lat index) at top
  }
  return cv.toDataURL();
}
function drawMap() {
  el('mapStyled').style.display = '';
  renderStylized();
}
function onMapHover(e) {
  const lat = e.latlng.lat, lon = e.latlng.lng;
  if (curGrid) {
    const a = curGrid; let ci = 0, cj = 0, bi = 1e9, bj = 1e9;
    a.lats.forEach((la, i) => { const dd = Math.abs(la - lat); if (dd < bi) { bi = dd; ci = i; } });
    a.lons.forEach((lo, j) => { const dd = Math.abs(lo - lon); if (dd < bj) { bj = dd; cj = j; } });
    const v = a.value[ci][cj], an = a.anomaly[ci][cj], absmax = scaleRef || Math.max(Math.abs(a.amin), Math.abs(a.amax));
    const nm = curLayer === 'rain' ? 'Rainfall' : 'Temperature', u = curLayer === 'rain' ? ' mm/day' : '°C';
    el('distinfo').innerHTML = `<b>${lat.toFixed(2)}°N, ${lon.toFixed(2)}°E</b> — ${nm}: <b>${v == null ? '—' : v}${u}</b> · anomaly <b style="color:${anomColor(an, curLayer, absmax)}">${an == null ? '—' : (an > 0 ? '+' : '') + an}</b>`;
  }
}
function renderLegend() {
  if (!curGrid) { el('legend').innerHTML = legends.soil.map(([l, c]) => `<div class="legrow"><span class="sw" style="background:${c}"></span>${l}</div>`).join(''); return; }
  const absmax = scaleRef || (Math.max(Math.abs(curGrid.amin), Math.abs(curGrid.amax)) || 1);
  const stops = [-1, -.5, 0, .5, 1].map(t => anomColor(t * absmax, curLayer, absmax));
  const unit = curLayer === 'rain' ? 'mm/day' : '°C';
  el('legend').innerHTML = `<div style="height:12px;border-radius:6px;background:linear-gradient(90deg,${stops.join(',')})"></div>
        <div style="display:flex;justify-content:space-between;font-family:var(--fm);font-size:11px;color:var(--muted);margin-top:6px"><span>−${absmax.toFixed(1)} ${unit}</span><span>0</span><span>+${absmax.toFixed(1)}</span></div>
        <div class="cs" style="margin-top:8px">Anomaly = grid value − per-cell climatology</div>`;
}
function renderRanking() {
  el('monHead').textContent = curRegion === 'india' ? 'Cities monitored' : 'Districts monitored';
  el('monSub').textContent = 'Sampled from the grid';
  el('monitored').textContent = curDistricts.map(d => d.name).join(' · ');
}

// ---------- Forecast ----------
let fcRain, fcTemp;
async function loadForecast() {
  const [r, t] = await Promise.all([api('/api/climate/forecast?var=rainfall'), api('/api/climate/forecast?var=temperature')]);
  fcRain = buildForecast('rainFc', r, C.ocean); fcTemp = buildForecast('tempFc', t, C.clay);
  const fmt = iso => new Date(iso + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  if (t.horizon) {
    el('fcMeta').innerHTML = `<span class="dot" style="display:inline-block;margin-right:6px"></span>Live outlook issued <b>${fmt(t.issued)}</b> · valid ${fmt(t.horizon.start)} → ${fmt(t.horizon.end)} (${t.horizon.days} days)`;
    el('rainFcSub').textContent = `mm/day · observed vs predicted · ±1σ · ${fmt(r.horizon.start)} → ${fmt(r.horizon.end)}`;
    el('tempFcSub').textContent = `°C · observed vs predicted · ±1σ · ${fmt(t.horizon.start)} → ${fmt(t.horizon.end)}`;
  }
  el('skill').innerHTML = `
        <div class="m"><div class="n">${t.skill.rmse}<small>°C</small></div><div class="t">Temperature RMSE · ${t.skill.skill_pct}% better than climatology (baseline ${t.skill.clim_rmse}°C)</div></div>
        <div class="m"><div class="n">${t.skill.mae}<small>°C</small></div><div class="t">Temperature MAE</div></div>
        <div class="m"><div class="n">${r.skill.rmse}<small>mm</small></div><div class="t">Rainfall RMSE · +${r.skill.skill_pct}% skill (baseline ${r.skill.clim_rmse})</div></div>
        <div class="m"><div class="n">14</div><div class="t">Day horizon · ${t.skill.model}. ${t.skill.backtest}.</div></div>`;
  try {
    const [gt, gr] = await Promise.all([api('/api/gridded/forecast/skill?var=tmean'), api('/api/gridded/forecast/skill?var=rain')]);
    const sk = (o) => (o >= 0 ? '+' : '') + o + '%';
    const gl = gt.leads;
    el('gridSkill').innerHTML = `
          <div class="m"><div class="n">${sk(gl['1'].skill_vs_clim_pct)}</div><div class="t">Temp +1-day vs climatology · ${sk(gl['1'].skill_vs_persist_pct)} vs naive persistence (RMSE ${gl['1'].rmse}°C)</div></div>
          <div class="m"><div class="n">${sk(gl['3'].skill_vs_clim_pct)}</div><div class="t">Temp +3-day vs climatology · ${sk(gl['3'].skill_vs_persist_pct)} vs naive persistence</div></div>
          <div class="m"><div class="n">${sk(gl['7'].skill_vs_clim_pct)}</div><div class="t">Temp +7-day — converges to climatology (predictability limit)</div></div>
          <div class="m"><div class="n">${gt.test_days}</div><div class="t">Backtest days · ${gt.model}</div></div>`;
  } catch { el('gridSkill').innerHTML = '<div class="cs">Ingest a multi-year grid to enable spatial validation.</div>'; }
}
function buildForecast(canvas, d, color) {
  const ctx = el(canvas).getContext('2d');
  const grad = ctx.createLinearGradient(0, 0, 0, 260); grad.addColorStop(0, color + '38'); grad.addColorStop(1, color + '04');
  const labels = [...d.observed.map(o => o.label), ...d.predicted.map(p => p.label)];
  const obs = [...d.observed.map(o => o.value), ...d.predicted.map(() => null)];
  const pad = d.observed.map(() => null);
  const pred = [...pad.slice(0, -1), d.observed.at(-1).value, ...d.predicted.map(p => p.value)];
  const up = [...pad, ...d.predicted.map(p => p.upper)];
  const lo = [...pad, ...d.predicted.map(p => p.lower)];
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels, datasets: [
        { label: 'Upper', data: up, borderWidth: 0, pointRadius: 0, fill: '+1', backgroundColor: grad },
        { label: 'Lower', data: lo, borderWidth: 0, pointRadius: 0, fill: false },
        { label: 'Predicted', data: pred, borderColor: color, borderDash: [5, 4], pointRadius: 0, tension: .38, borderWidth: 2 },
        { label: 'Observed', data: obs, borderColor: '#1b2b27', backgroundColor: '#1b2b27', pointRadius: 3, tension: .38, borderWidth: 2 },
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      plugins: { legend: { labels: { filter: i => i.text === 'Predicted' || i.text === 'Observed', boxWidth: 12 } } },
      scales: { x: { grid: { color: GRID }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } }, y: { grid: { color: GRID }, border: { display: false } } }
    }
  });
}

// ---------- Simulator ----------
let simChart, simTimer;
function loadSimulator() {
  simChart = new Chart(el('simChart'), {
    type: 'bar',
    data: {
      labels: ['Soil moisture', 'Drought risk', 'Crop stress', 'Reservoir inflow'], datasets: [
        { label: 'Baseline', data: [], backgroundColor: '#e0d8c6', borderRadius: 5 },
        { label: 'Scenario', data: [], backgroundColor: C.algae, borderRadius: 5 }]
    },
    options: { maintainAspectRatio: false, plugins: { legend: { labels: { boxWidth: 12 } } }, scales: { x: { grid: { display: false } }, y: { grid: { color: GRID }, border: { display: false } } } }
  });
  el('rainS').addEventListener('input', simUpdate); el('tempS').addEventListener('input', simUpdate);
  el('simPresets').querySelectorAll('.toggle').forEach(b => b.addEventListener('click', () => {
    el('rainS').value = b.dataset.r; el('tempS').value = b.dataset.t;
    el('simPresets').querySelectorAll('.toggle').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    simUpdate();
  }));
  simUpdate();
}
function simUpdate() {
  const rain = parseFloat(el('rainS').value), temp = parseFloat(el('tempS').value);
  el('rainV').textContent = (rain > 0 ? '+' : '') + rain + '%';
  el('tempV').textContent = (temp >= 0 ? '+' : '') + temp.toFixed(1) + '°C';
  clearTimeout(simTimer);
  simTimer = setTimeout(async () => {
    const s = await api('/api/climate/whatif', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rain_pct: rain, temp_c: temp }) });
    const col = v => v ? C.clay : C.seaweed;
    el('iSoil').textContent = s.soil_moisture_index; el('iSoil').style.color = s.soil_moisture_index < 0.35 ? C.clay : C.seaweed;
    el('iDrought').textContent = s.drought_risk_score; el('iDrought').style.color = s.drought_risk_score > 55 ? C.clay : s.drought_risk_score < 30 ? C.seaweed : C.ochre;
    el('iCrop').textContent = s.crop_water_stress; el('iCrop').style.color = ['High', 'Severe'].includes(s.crop_water_stress) ? C.clay : s.crop_water_stress === 'Low' ? C.seaweed : C.ochre;
    el('iWater').textContent = (s.reservoir_inflow_change_pct >= 0 ? '+' : '') + s.reservoir_inflow_change_pct + '%'; el('iWater').style.color = s.reservoir_inflow_change_pct < -15 ? C.clay : s.reservoir_inflow_change_pct > 10 ? C.ocean : C.ochre;
    const b = s.baseline;
    simChart.data.datasets[0].data = [b.soil_moisture_index * 100, b.drought_risk_score, b.crop_water_stress_score, 50 + b.reservoir_inflow_change_pct];
    simChart.data.datasets[1].data = [s.soil_moisture_index * 100, s.drought_risk_score, s.crop_water_stress_score, 50 + s.reservoir_inflow_change_pct];
    simChart.update();

    // narrative + water balance
    el('simNarrative').textContent = s.narrative || '';
    const bi = s.baseline_info;
    if (bi) el('simBaseline').textContent =
      `Live baseline · this season's normal (${bi.season}): rain ${bi.normal_rain_mm_day} mm/day, ` +
      `ET demand ${bi.normal_et_mm_day} mm/day, ${bi.normal_tmean_c}°C · starting from today's soil moisture ` +
      `${bi.live_soil_moisture}${bi.soil_as_of ? ' (as of ' + bi.soil_as_of + ')' : ''}`;
    const wb = s.water_balance;
    if (wb) {
      el('wbRain').textContent = wb.rain_in_mm;
      el('wbEt').textContent = wb.et_out_mm;
      el('wbNet').textContent = (wb.net_mm > 0 ? '+' : '') + wb.net_mm;
      el('wbNet').style.color = wb.net_mm >= 0 ? C.seaweed : C.clay;
      const shift = Math.round((wb.net_mm - wb.baseline_net_mm) * 10) / 10;
      el('wbDelta').textContent = (shift > 0 ? '+' : '') + shift;
      el('wbDelta').style.color = shift >= 0 ? C.ocean : C.clay;
    }
    // sector impact tiles
    const lvlCol = l => ({ Low: C.seaweed, Moderate: C.ochre, High: C.clay, Severe: '#b23b1e' }[l] || C.ochre);
    el('simSectors').innerHTML = (s.sectors || []).map(x => `
          <div class="imp">
            <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
              <div class="k">${x.name}</div>
              <span class="pill" style="font-size:11px;background:${lvlCol(x.risk_label)}22;color:${lvlCol(x.risk_label)}">${x.risk_label}</span>
            </div>
            <div style="font-size:12.5px;color:var(--ink-soft);margin-top:8px;line-height:1.5">${x.note}</div>
          </div>`).join('');
  }, 120);
}

// ---------- Data & Models ----------
async function loadData() {
  const d = await api('/api/climate/data');
  el('dataSpan').textContent = `${d.record_days.toLocaleString()} daily records · ${d.record_span}`;
  el('srcFull').innerHTML = d.sources.map(srcRow).join('');
  el('models').innerHTML = d.models.map(m => `<tr><td><b>${m.variable}</b></td><td style="color:var(--muted)">${m.type}</td><td class="mono">${m.rmse != null ? m.rmse + ' ' + m.unit + ' <span style="color:var(--muted)">(' + m.baseline_rmse + ')</span>' : '—'}</td><td class="mono" style="color:var(--seaweed)">${m.skill_pct != null ? '+' + m.skill_pct + '%' : '—'}</td></tr>`).join('');

  // --- real-time provenance KPIs ---------------------------------------- #
  const activeSrc = d.sources.filter(s => (s.status || '').toLowerCase() === 'active').length;
  const skills = d.models.map(m => m.skill_pct).filter(v => v != null);
  const meanSkill = skills.length ? Math.round(skills.reduce((a, b) => a + b, 0) / skills.length) : null;
  const years = Math.round(d.record_days / 365);
  const kpis = [
    { lbl: 'Daily records', ic: '📅', col: C.ocean, val: (d.record_days / 1000).toFixed(1), unit: 'k', meta: `${years}+ years · ${d.record_span}` },
    { lbl: 'Data sources', ic: '🛰️', col: C.algae, val: d.sources.length, unit: '', meta: `${activeSrc} active · IMD · NASA POWER · Open-Meteo · ISRO` },
    { lbl: 'AI models', ic: '🧠', col: C.seaweed, val: d.models.length, unit: '', meta: 'validated on held-out time split' },
    { lbl: 'Mean forecast skill', ic: '🎯', col: C.seaweed, val: meanSkill != null ? '+' + meanSkill : '—', unit: meanSkill != null ? '%' : '', meta: 'vs climatology baseline' },
  ];
  el('dataKpis').innerHTML = kpis.map(k => `
        <div class="card kpi">
          <div class="top"><span class="lbl">${k.lbl}</span><span class="ic" style="background:${k.col}1c;color:${k.col}">${k.ic}</span></div>
          <div class="val" style="color:${k.col}">${k.val}<small>${k.unit}</small></div>
          <div class="meta">${k.meta}</div>
        </div>`).join('');

  loadGridded();
  loadFusion();
}

// ---------- Multi-source data assimilation ----------
async function loadFusion() {
  let s; try { s = await api('/api/fusion/status'); } catch { return; }
  if (!s.vars.length) { el('fuseSources').innerHTML = '<div class="cs">Ingest a second source (openmeteo) to enable fusion.</div>'; return; }
  el('fuseTabs').innerHTML = s.vars.map((v, i) => `<button class="toggle ${i === 0 ? 'active' : ''}" data-fv="${v}">${v === 'rain' ? 'Rainfall' : 'Temperature'}</button>`).join('');
  el('fuseTabs').querySelectorAll('.toggle').forEach(b => b.addEventListener('click', () => {
    el('fuseTabs').querySelectorAll('.toggle').forEach(x => x.classList.remove('active')); b.classList.add('active'); drawFusion(b.dataset.fv);
  }));
  drawFusion(s.vars[0]);
}
async function drawFusion(v) {
  const f = await api('/api/fusion/field?var=' + v);
  el('fuseSources').innerHTML = f.sources.map(src => `
        <div style="margin-bottom:12px">
          <div class="flex between" style="display:flex;justify-content:space-between;font-size:13px"><b>${src.name}</b><span class="mono" style="color:var(--muted)">RMSE ${src.rmse} · weight ${(src.weight * 100).toFixed(0)}%</span></div>
          <div class="conf-bar" style="height:7px;background:var(--line);border-radius:5px;margin-top:5px;overflow:hidden"><i style="display:block;height:100%;width:${src.weight * 100}%;background:var(--algae)"></i></div>
        </div>`).join('');
  const better = f.reduction_vs_best_pct >= 0;
  el('fuseVal').innerHTML = `
        <div class="m"><div class="n" style="color:${better ? 'var(--seaweed)' : 'var(--ochre)'}">${f.fused_rmse}</div><div class="t">Fused RMSE (${f.units}) vs ${f.validated_against}</div></div>
        <div class="m"><div class="n" style="color:${better ? 'var(--seaweed)' : 'var(--ochre)'}">${f.reduction_vs_best_pct >= 0 ? '−' : '+'}${Math.abs(f.reduction_vs_best_pct)}%</div><div class="t">Error ${better ? 'reduction' : 'change'} vs best single source</div></div>
        <div class="m"><div class="n">±${f.spread_mean}</div><div class="t">Mean inter-source spread (max ±${f.spread_max} ${f.units})</div></div>`;
  // spread heatmap (light → terracotta = high disagreement), smoothly interpolated
  const smax = f.spread_max || 1;
  const spreadRamp = [[0, '#f3ede0'], [1, '#d2694a']];
  smoothField(el('fuseHeat'), f.spread, v => rampRGB(spreadRamp, Math.min(1, v / smax)));
  el('fuseSpreadScale').innerHTML = `<span style="display:inline-flex;align-items:center;gap:8px">0 <span style="display:inline-block;width:110px;height:10px;border-radius:5px;background:linear-gradient(90deg,#f3edE0,#d2694a)"></span> ±${f.spread_max} ${f.units} · |POWER − ERA5|</span>`;

  // method / period meta
  el('fuseMeta').innerHTML = `${f.method}<br>${f.period} · ${f.res_deg}° grid`;

  // per-district fused field — real assimilated values
  const ds = (f.districts || []).slice().sort((a, b) => a.name.localeCompare(b.name));
  // grade agreement relative to the district spread range so the column is informative
  const dmx = Math.max(1e-6, ...ds.map(x => x.spread));
  const agree = sp => { const r = sp / dmx; return r < 0.34 ? ['High', C.seaweed] : r < 0.67 ? ['Fair', C.ochre] : ['Low', C.clay]; };
  el('fuseDistricts').innerHTML = ds.length ? `
        <table class="dtable">
          <thead><tr><th>District</th><th class="r">Fused (${f.units})</th><th class="r">Anomaly</th><th class="r">Agreement</th></tr></thead>
          <tbody>${ds.map(x => {
    const [lbl, col] = agree(x.spread); return `
            <tr>
              <td><b>${x.name}</b></td>
              <td class="r mono">${x.value}</td>
              <td class="r mono" style="color:${x.anomaly > 0 ? 'var(--clay)' : 'var(--ocean)'}">${x.anomaly > 0 ? '+' : ''}${x.anomaly}</td>
              <td class="r"><span class="agree" style="background:${col}1c;color:${col}">${lbl} · ±${x.spread}</span></td>
            </tr>`;
  }).join('')}
          </tbody>
        </table>
        <div class="cs" style="margin-top:10px">Agreement = inter-source spread between POWER &amp; ERA5 at each district centroid — lower is more certain.</div>` : '<div class="cs">No district samples.</div>';
}

// ---------- Live gridded ingestion ----------
const RAMPS = {
  tmean: [[0, '#2f7d9a'], [0.5, '#dd9138'], [1, '#d2694a']],
  tmax: [[0, '#2f7d9a'], [0.5, '#dd9138'], [1, '#d2694a']],
  tmin: [[0, '#2f7d9a'], [0.5, '#dd9138'], [1, '#d2694a']],
  rain: [[0, '#efe3c8'], [0.5, '#7cc9b3'], [1, '#2f7d9a']],
};
const VAR_LABEL = { tmean: 'Mean temp', tmax: 'Max temp', tmin: 'Min temp', rain: 'Rainfall', lst: 'Surface temp (LST)', sst: 'Sea-surface temp' };
function lerp(a, b, t) { return Math.round(a + (b - a) * t); }
function hex2rgb(h) { return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]; }
function rampRGB(stops, t) {
  t = Math.max(0, Math.min(1, t));
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i][0]) {
      const [p0, c0] = stops[i - 1], [p1, c1] = stops[i];
      const f = (t - p0) / (p1 - p0 || 1); const a = hex2rgb(c0), b = hex2rgb(c1);
      return [lerp(a[0], b[0], f), lerp(a[1], b[1], f), lerp(a[2], b[2], f)];
    }
  }
  return hex2rgb(stops[stops.length - 1][1]);
}
function rampColor(stops, t) { const [r, g, b] = rampRGB(stops, t); return `rgb(${r},${g},${b})`; }
// Render a 2-D field to a canvas via a native-resolution offscreen buffer, then
// upscale with bilinear smoothing so the map reads as a continuous field, not blocks.
function smoothField(cv, values, colorFn, nullRGB = [239, 231, 214]) {
  const rows = values.length, cols = values[0].length;
  const off = document.createElement('canvas'); off.width = cols; off.height = rows;
  const octx = off.getContext('2d'), img = octx.createImageData(cols, rows);
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const v = values[r][c];
    const [rr, gg, bb] = (v == null || !isFinite(v)) ? nullRGB : colorFn(v);
    const px = ((rows - 1 - r) * cols + c) * 4;   // north on top
    img.data[px] = rr; img.data[px + 1] = gg; img.data[px + 2] = bb; img.data[px + 3] = 255;
  }
  octx.putImageData(img, 0, 0);
  const ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(off, 0, 0, cv.width, cv.height);
}
async function loadGridded() {
  let s; try { s = await api('/api/gridded/status'); } catch { return; }
  const statusCol2 = { power: C.seaweed, imd: C.ochre, mosdac: C.ocean };
  el('gridSources').innerHTML = Object.entries(s.sources).map(([k, v]) =>
    `<div class="lg"><span class="sw" style="background:${statusCol2[k]}"></span><b style="color:var(--ink);text-transform:uppercase">${k}</b> — ${v}</div>`).join('');
  const daily = s.datasets.filter(d => d.kind !== 'climatology');
  if (!daily.length) { el('gridList').innerHTML = '<div class="cs">No grids ingested yet. Run <span class="mono">python -m ingest.pipeline …</span></div>'; return; }
  el('gridList').innerHTML = daily.map(d => `
        <div class="drow"><span class="sw" style="background:${statusCol2[d.source.toLowerCase().includes('power') ? 'power' : d.source.toLowerCase().includes('imd') ? 'imd' : 'mosdac']}"></span>
          <div><div class="dnm">${d.var} · ${d.region.toUpperCase()}</div><div class="rd">${d.source} · ${d.grid_shape[0]}×${d.grid_shape[1]} @ ${d.res_deg}° · ${d.days}d</div></div>
          <span class="dvl">${d.mean} ${d.units}</span></div>`).join('');
  // One tab per variable (dedup repeats): pick the best grid — prefer the J&K pilot
  // region, then the longest / most recent record — as the representative for each var.
  const best = {};
  for (const d of daily) {
    // prefer the J&K pilot region, then the most recent grid (its live end-date)
    const score = (d.region === 'jk' ? 1e12 : 0) + Number(d.end || d.days || 0);
    if (!best[d.var] || score > best[d.var]._score) best[d.var] = { ...d, _score: score };
  }
  const vars = Object.values(best);
  el('gridTabs').innerHTML = vars.map((d, i) =>
    `<button class="toggle ${i === 0 ? 'active' : ''}" data-gid="${d.id}" data-var="${d.var}">${VAR_LABEL[d.var] || d.var}</button>`).join('');
  el('gridTabs').querySelectorAll('.toggle').forEach(b => b.addEventListener('click', () => {
    el('gridTabs').querySelectorAll('.toggle').forEach(x => x.classList.remove('active')); b.classList.add('active');
    drawHeat(b.dataset.gid, b.dataset.var);
  }));
  drawHeat(vars[0].id, vars[0].var);
}
async function drawHeat(id, varName) {
  try {
    const f = await api('/api/gridded/field?id=' + encodeURIComponent(id));
    if (!f || !Array.isArray(f.values) || !f.values.length || !Array.isArray(f.values[0])) {
      el('gridTitle').textContent = 'Grid dataset unavailable';
      el('gridScale').innerHTML = '';
      return;
    }
    const cv = el('gridHeat');
    const cols = f.values[0].length, rows = f.values.length;
    const ramp = RAMPS[varName] || RAMPS.tmean, rng = (f.vmax - f.vmin) || 1;
    smoothField(cv, f.values, v => rampRGB(ramp, (v - f.vmin) / rng));
    el('gridTitle').textContent = `${VAR_LABEL[f.var] || f.var} · ${f.source} · ${f.res_deg}° grid (${cols}×${rows})`;
    el('gridScale').innerHTML = `<span style="display:inline-flex;align-items:center;gap:8px">${f.vmin}
        <span style="display:inline-block;width:120px;height:10px;border-radius:5px;background:linear-gradient(90deg,${ramp.map(s => s[1]).join(',')})"></span>
        ${f.vmax} ${f.units} · mean ${f.mean}</span>`;
  } catch (err) {
    el('gridTitle').textContent = 'Grid dataset unavailable';
    el('gridScale').innerHTML = '';
  }
}

// ---------- Reports ----------
async function loadReports() {
  const r = await api('/api/climate/insights');
  const col = { alert: C.clay, warning: C.ochre, info: C.ocean };
  el('reports').innerHTML = r.items.map(it => `
        <div class="rep"><div class="bar" style="background:${col[it.level]}"></div>
          <div style="flex:1"><h4>${it.title}</h4><p>${it.body}</p>
            <div class="tags">${it.districts.map(d => `<span class="tg">${d}</span>`).join('')}</div></div></div>`).join('');
  loadWeather();
}
async function loadWeather() {
  const rnd = x => x == null ? '—' : Math.round(x);
  try {
    const w = await api('/api/weather/live');
    el('wxSub').textContent = 'Real-time conditions · ' + w.source;
    el('wxUpdated').textContent = w.updated_at ? 'Live · ' + w.updated_at.replace('T', ' ') + ' IST' : 'Live';
    el('wxGrid').innerHTML = w.stations.map(s => `
          <div class="wx">
            <div class="top"><div class="nm">${s.name}</div><div class="ico">${s.icon}</div></div>
            <div class="t">${rnd(s.temp_c)}°C</div>
            <div class="cond">${s.condition} · feels ${rnd(s.feels_c)}°</div>
            <div class="meta">
              <span>H ${rnd(s.high_c)}° / L ${rnd(s.low_c)}°</span>
              <span>Humidity ${s.humidity_pct != null ? s.humidity_pct + '%' : '—'}</span>
              <span>Rain ${s.rain_chance_pct != null ? s.rain_chance_pct + '%' : '—'}</span>
              <span>Wind ${rnd(s.wind_kmh)} km/h</span>
            </div>
          </div>`).join('');
  } catch (e) {
    el('wxUpdated').textContent = 'offline';
    el('wxGrid').innerHTML = '<div class="cs">Live weather is momentarily unavailable (upstream offline or rate-limited). It refreshes automatically.</div>';
  }
  loadNews();
}
// News is third-party/untrusted text — escape it before inserting into the DOM.
const esc = s => (s == null ? '' : String(s)).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
async function loadNews() {
  try {
    const n = await api('/api/weather/news');
    if (!n.configured) {
      el('newsUpdated').textContent = 'not configured';
      el('newsList').innerHTML = `<div class="cs">Live headlines aren't configured yet. Add a free news API key (NewsAPI or GNews) to <span class="mono">Backend/.env</span> as <span class="mono">NEWS_API_KEY</span> to enable this feed.</div>`;
      return;
    }
    el('newsSub').textContent = 'Live weather news · ' + esc(n.provider);
    if (!n.articles.length) { el('newsUpdated').textContent = 'live'; el('newsList').innerHTML = '<div class="cs">No recent J&amp;K weather headlines right now.</div>'; return; }
    el('newsUpdated').textContent = 'Live · ' + n.count + ' stories';
    const when = iso => { try { return new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }); } catch { return ''; } };
    el('newsList').innerHTML = n.articles.map(a => {
      const url = /^https?:\/\//i.test(a.url || '') ? a.url : '#';
      const img = /^https?:\/\//i.test(a.image || '') ? a.image : '';
      return `<div class="news-item">
            <div class="ni-text">
              <div class="nt"><a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a></div>
              ${a.summary ? `<div class="ns">${esc(a.summary)}</div>` : ''}
              <div class="nm">${esc(a.source) || 'News'}${a.published_at ? ' · ' + esc(when(a.published_at)) : ''}</div>
            </div>
            ${img ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" class="ni-img"><img src="${esc(img)}" alt="" loading="lazy" onerror="this.closest('.ni-img').style.display='none'"></a>` : ''}
          </div>`;
    }).join('');
  } catch (e) {
    el('newsUpdated').textContent = 'offline';
    el('newsList').innerHTML = '<div class="cs">Headlines are momentarily unavailable (upstream offline or rate-limited).</div>';
  }
}

// ---------- Hazards ----------
let drChart, hwChart, mnChart, wtChart, erChart, cwChart;
async function loadHazards() {
  const [h, a] = await Promise.all([api('/api/hazards'), api('/api/hazards/analytics')]);
  const d = h.drought;
  el('drSub').textContent = `${d.index} · as of ${d.as_of}`;
  el('drVal').textContent = (d.value > 0 ? '+' : '') + d.value; el('drVal').style.color = d.color;
  el('drClass').textContent = d.class; el('drClass').style.background = d.color + '22'; el('drClass').style.color = d.color;
  const spiCol = v => v <= -1.5 ? '#d2694a' : v < 0 ? '#dd9138' : v < 1 ? '#2aa38a' : '#2f7d9a';
  if (drChart) drChart.destroy();
  drChart = new Chart(el('drChart'), {
    type: 'bar',
    data: { labels: d.series.map(s => s.t), datasets: [{ data: d.series.map(s => s.spi), backgroundColor: d.series.map(s => spiCol(s.spi)), borderRadius: 2 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => 'SPI ' + c.parsed.y } } }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 6 } }, y: { grid: { color: GRID }, suggestedMin: -2.5, suggestedMax: 2.5 } } }
  });
  const hw = h.heatwave;
  el('hwStatus').textContent = hw.status; const hwc = hw.active ? '#d2694a' : '#2aa38a';
  el('hwStatus').style.background = hwc + '22'; el('hwStatus').style.color = hwc;
  el('hwAnom').textContent = (hw.recent_tmax_anomaly_c > 0 ? '+' : '') + hw.recent_tmax_anomaly_c + '°C';
  el('hwSub').textContent = `Heatwave days / year · ≥ +${hw.threshold_c}°C over normal`;
  if (hwChart) hwChart.destroy();
  hwChart = new Chart(el('hwChart'), {
    type: 'bar',
    data: { labels: hw.per_year.map(y => y.year), datasets: [{ data: hw.per_year.map(y => y.days), backgroundColor: '#d2694a', borderRadius: 4 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { grid: { color: GRID }, title: { display: true, text: 'days' } } } }
  });
  const mn = h.monsoon;
  el('mnProg').textContent = mn.progress_pct + '%';
  el('mnProg').style.color = mn.progress_pct < 80 ? '#d2694a' : mn.progress_pct > 110 ? '#2f7d9a' : '#2aa38a';
  el('mnSub').textContent = `${mn.season} ${mn.year} · onset ${mn.onset_date || '—'}`;
  el('mnDetail').textContent = `${mn.received_mm} mm of ${mn.seasonal_normal_mm} mm normal received`;
  if (mnChart) mnChart.destroy();
  mnChart = new Chart(el('mnChart'), {
    type: 'line',
    data: {
      labels: mn.curve.map(c => 'D' + c.d), datasets: [
        { label: 'Normal', data: mn.curve.map(c => c.normal), borderColor: '#b9ae97', borderDash: [5, 4], pointRadius: 0, tension: .3, borderWidth: 2 },
        { label: 'This year', data: mn.curve.map(c => c.current), borderColor: '#2aa38a', backgroundColor: 'rgba(42,163,138,.12)', fill: true, pointRadius: 0, tension: .3, borderWidth: 2 }]
    },
    options: { maintainAspectRatio: false, plugins: { legend: { labels: { boxWidth: 12 } } }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 6 } }, y: { grid: { color: GRID }, title: { display: true, text: 'mm' } } } }
  });

  // ----- Warming trend -----
  const w = a.warming;
  el('wtVal').textContent = (w.total_change_c > 0 ? '+' : '') + w.total_change_c + '°C';
  el('wtSub').textContent = `Annual mean temperature · ${w.span}`;
  el('wtDetail').innerHTML = `<b>${w.slope_c_per_decade > 0 ? '+' : ''}${w.slope_c_per_decade}°C</b> per decade · warming since 1973`;
  if (wtChart) wtChart.destroy();
  wtChart = new Chart(el('wtChart'), {
    type: 'line',
    data: {
      labels: w.series.map(s => s.year), datasets: [
        { label: 'Annual mean', data: w.series.map(s => s.mean_c), borderColor: '#c9773f', backgroundColor: 'rgba(201,119,63,.10)', fill: true, pointRadius: 0, tension: .3, borderWidth: 2 },
        { label: 'Trend', data: w.series.map(s => s.trend_c), borderColor: '#8a5a2b', borderDash: [5, 4], pointRadius: 0, borderWidth: 2 }]
    },
    options: { maintainAspectRatio: false, plugins: { legend: { labels: { boxWidth: 12 } } }, scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 6 } }, y: { grid: { color: GRID }, title: { display: true, text: '°C' } } } }
  });

  // ----- Extreme rainfall -----
  const er = a.extreme_rain;
  el('erVal').textContent = er.latest_days;
  el('erSub').textContent = `Heavy-rain days / year · ≥ ${er.threshold_mm} mm`;
  el('erDetail').innerHTML = `${er.latest_year} vs <b>${er.baseline_days}</b> / year average`;
  if (erChart) erChart.destroy();
  erChart = new Chart(el('erChart'), {
    type: 'bar',
    data: { labels: er.per_year.map(y => y.year), datasets: [{ data: er.per_year.map(y => y.days), backgroundColor: '#2f7d9a', borderRadius: 4 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { grid: { color: GRID }, title: { display: true, text: 'days' } } } }
  });

  // ----- Cold wave & frost -----
  const cw = a.coldwave;
  const cwc = cw.active ? '#3b9be6' : '#2aa38a';
  el('cwStatus').textContent = cw.status; el('cwStatus').style.background = cwc + '22'; el('cwStatus').style.color = cwc;
  el('cwVal').textContent = cw.latest_days + ' frost days';
  el('cwSub').textContent = `Frost days / year · min ≤ 0°C`;
  if (cwChart) cwChart.destroy();
  cwChart = new Chart(el('cwChart'), {
    type: 'bar',
    data: { labels: cw.per_year.map(y => y.year), datasets: [{ data: cw.per_year.map(y => y.days), backgroundColor: '#5b8fb0', borderRadius: 4 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { grid: { color: GRID }, title: { display: true, text: 'days' } } } }
  });

  // ----- Climate records -----
  const rc = a.records;
  el('rcSub').textContent = `All-time daily extremes · ${rc.record_days.toLocaleString()} days (${rc.span})`;
  el('rcHot').textContent = rc.hottest.value + '°C'; el('rcHotD').textContent = rc.hottest.date;
  el('rcCold').textContent = rc.coldest.value + '°C'; el('rcColdD').textContent = rc.coldest.date;
  el('rcWet').textContent = rc.wettest.value + ' mm'; el('rcWetD').textContent = rc.wettest.date;
}

const loaders = { overview: loadOverview, map: loadMap, forecast: loadForecast, hazards: loadHazards, simulator: loadSimulator, data: loadData, reports: loadReports };
loadOverview(); loaded.overview = true;

// ---------- Near-real-time data refresh ----------
let liveBase = 'Assimilating…';
function setLive(base, suffix) {
  liveBase = base;
  el('liveText').textContent = suffix ? base + ' · ' + suffix : base;
}
async function refreshFeed() {
  const badge = el('liveBadge'), txt = el('liveText');
  if (!badge || badge.dataset.busy === '1') return;
  badge.dataset.busy = '1';
  const base = liveBase;                 // canonical label, never the stacked text
  txt.textContent = 'Pulling latest data…';
  try {
    const r = await api('/api/ingest/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
    if (r.status === 'ok' || r.status === 'partial') {
      const e = (r.window || '').split('–').pop();
      const end = e.length === 8 ? `${e.slice(0, 4)}-${e.slice(4, 6)}-${e.slice(6)}` : e;
      setLive('Live · ' + end, r.status === 'partial' ? `${r.updated.length} layers updated` : '');
      loadOverview();                    // re-pull views that depend on gridded data
      if (loaded.map) fetchLayer();      // re-fetch only — loadMap() would re-bind listeners
    } else if (r.status === 'busy') {
      setLive(base, 'refresh already running');
    } else {
      setLive(base, 'refresh unavailable');
    }
  } catch (e) {
    setLive(base, 'offline');
  } finally {
    badge.dataset.busy = '0';
  }
}
async function updateLiveBadge() {
  try {
    const s = await api('/api/ingest/status');
    if (s && s.last_result && s.last_result.window) {
      setLive('Live · ' + s.last_result.window.split('–').pop());
      return;
    }
  } catch (e) { }
  try { const c = await api('/api/climate/current'); setLive('Assimilated · ' + c.as_of); }
  catch (e) { setLive('Data feed'); }
}
(function initFeed() {
  const badge = el('liveBadge');
  if (badge) badge.addEventListener('click', refreshFeed);
  updateLiveBadge();
})();
