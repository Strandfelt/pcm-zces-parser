"""Standalone HTML page: stage profile linked to a route map.

    page = profile_html(stage_view(doc, cds))

The page has no dependencies except two Google Fonts (with fallbacks), so it
works offline with system fonts.
"""
import html
import json

TEMPLATE = r"""<title>__TITLE__</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
__LEAFLET__
<style>
/* Road-book layout: stage header, full-width gradient-coloured profile, then map beside the event list. */
:root {
  --bg: #f3f4f1; --panel: #ffffff; --ink: #1d2422; --muted: #66706b; --rule: #d9ddd8; --grid: #e6e9e5;
  --route: #1f5f8b; --route-hi: #e0a100;
  --g0: #cfe0c3; --g1: #f1d98a; --g2: #ee9f4f; --g3: #d65a3a; --g4: #8f1f2c;
  --kom: #c8102e; --sprint: #1f8a4c; --pave: #7a6a55; --gravel: #b9925a; --hi: rgba(224,161,0,.18);
  --f-display: "Barlow Condensed", "Arial Narrow", "Roboto Condensed", sans-serif;
  --f-body: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  --f-data: "IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #151a19; --panel: #1c2321; --ink: #e5ebe7; --muted: #95a19b; --rule: #2e3835; --grid: #26302d;
  --route: #6fb4e3; --route-hi: #f3bd2c;
  --g0: #3f5a3c; --g1: #8d7a35; --g2: #b26a2c; --g3: #c24d32; --g4: #e07a86;
  --kom: #ff5a6e; --sprint: #4fc283; --pave: #b9a68a; --gravel: #d6b37a; --hi: rgba(243,189,44,.16); color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #151a19; --panel: #1c2321; --ink: #e5ebe7; --muted: #95a19b; --rule: #2e3835; --grid: #26302d;
  --route: #6fb4e3; --route-hi: #f3bd2c;
  --g0: #3f5a3c; --g1: #8d7a35; --g2: #b26a2c; --g3: #c24d32; --g4: #e07a86;
  --kom: #ff5a6e; --sprint: #4fc283; --pave: #b9a68a; --gravel: #d6b37a; --hi: rgba(243,189,44,.16); color-scheme: dark }
* { box-sizing: border-box }
body { background: var(--bg); color: var(--ink); font: 14px/1.5 var(--f-body); margin: 0 }
.wrap { max-width: 1180px; margin: 0 auto; padding-block: 28px 40px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px }
.wrap > * { min-width: 0 }
header { display: grid; gap: 6px }
.eyebrow { font: 500 12px/1 var(--f-data); letter-spacing: .08em; text-transform: uppercase; color: var(--muted) }
h1 { font: 700 clamp(30px, 5vw, 48px)/1.02 var(--f-display); letter-spacing: .01em; margin: 0; text-wrap: balance; text-transform: uppercase }
.region { color: var(--muted); font-size: 15px }
.stats { display: flex; flex-wrap: wrap; gap: 6px 22px; margin-top: 6px; font: 500 13px var(--f-data); font-variant-numeric: tabular-nums }
.stats b { font: 600 22px/1 var(--f-display); letter-spacing: .02em; margin-right: 4px; color: var(--ink) }
.stats span { color: var(--muted) }
.panel { background: var(--panel); border: 1px solid var(--rule); border-radius: 6px }
.profile { padding: 12px 12px 6px; position: relative }
#prof, #map { display: block; width: 100%; height: auto }
.legend { display: flex; flex-wrap: wrap; gap: 4px 14px; padding: 2px 8px 8px; color: var(--muted); font: 12px var(--f-data) }
.legend i { display: inline-block; width: 18px; height: 9px; margin-right: 5px; vertical-align: -1px; border-radius: 1px }
.lower { display: grid; grid-template-columns: minmax(0, 380px) minmax(0, 1fr); gap: 18px; align-items: start }
@media (max-width: 760px) { .lower { grid-template-columns: minmax(0, 1fr) } }
.map { padding: 8px; position: sticky; top: calc(env(safe-area-inset-top, 0px) + 12px) }
.map figcaption { font: 12px var(--f-data); color: var(--muted); padding: 6px 4px 2px }
#lmap { width: 100%; aspect-ratio: 1; max-width: 100%; border-radius: 4px; background: var(--grid) }
.leaflet-container { font: 12px var(--f-body) }
a.osm { color: var(--route); text-decoration: none; white-space: nowrap }
a.osm:hover, a.osm:focus-visible { text-decoration: underline }
.events { overflow-x: auto }
table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums }
th { text-align: left; font: 500 11px var(--f-data); letter-spacing: .08em; text-transform: uppercase; color: var(--muted);
  padding: 10px 12px; border-bottom: 1px solid var(--rule) }
td { padding: 8px 12px; border-bottom: 1px solid var(--grid); vertical-align: top }
tr:last-child td { border-bottom: 0 }
td.km { font: 500 13px var(--f-data); white-space: nowrap; width: 1%; color: var(--muted) }
td.name { font-weight: 500 }
td.detail { color: var(--muted); font-size: 13px }
tbody tr { cursor: default }
tbody tr:hover, tbody tr.on { background: var(--hi) }
tbody tr:focus-visible { outline: 2px solid var(--route-hi); outline-offset: -2px }
.badge { display: inline-grid; place-items: center; width: 20px; height: 20px; border-radius: 50%; font: 700 11px var(--f-display);
  margin-right: 8px; vertical-align: -5px; color: #fff }
.b-kom { background: radial-gradient(circle at 30% 30%, #fff 0 2px, transparent 2.5px) 0 0/7px 7px, var(--kom) }
.b-sprint { background: var(--sprint) }
.b-climb { background: var(--g3) }
.b-cobbles { background: repeating-linear-gradient(45deg, var(--pave) 0 3px, transparent 3px 5px), var(--panel); border: 1px solid var(--pave) }
.b-gravel { background: radial-gradient(circle, var(--gravel) 1.2px, transparent 1.6px) 0 0/4px 4px, var(--panel); border: 1px solid var(--gravel) }
.b-start { background: var(--route) }
.b-finish { background: conic-gradient(#111 0 25%, #fff 0 50%, #111 0 75%, #fff 0) 0 0/8px 8px; border: 1px solid #111 }
.stars { color: var(--pave); letter-spacing: 1px }
.tip { position: absolute; pointer-events: none; background: var(--ink); color: var(--panel); font: 12px/1.4 var(--f-data);
  padding: 6px 8px; border-radius: 4px; white-space: nowrap; transform: translate(-50%, -100%); font-variant-numeric: tabular-nums }
.note { color: var(--muted); font-size: 12px }
svg text { fill: var(--muted); font: 11px var(--f-data) }
svg .label { fill: var(--ink); font: 600 12px var(--f-display); letter-spacing: .03em }
@media (prefers-reduced-motion: no-preference) { tbody tr { transition: background .12s } }
</style>
<div class="wrap">
  <header>
    <div class="eyebrow">Pro Cycling Manager stage · __FILE__</div>
    <h1 id="name"></h1>
    <div class="region" id="region"></div>
    <div class="stats" id="stats"></div>
  </header>
  <section class="panel profile" aria-label="Elevation profile">
    <svg id="prof" role="img" aria-label="Elevation profile with climbs, sprints and sectors"></svg>
    <div class="tip" id="tip" hidden></div>
    <div class="legend" id="legend"></div>
  </section>
  <div class="lower">
    <figure class="panel map" style="margin:0">
      <div id="lmap" hidden></div>
      <svg id="map" role="img" aria-label="Route map"></svg>
      <figcaption id="mapcap">Route map · north up · grey lines are the stage’s other roads</figcaption>
    </figure>
    <section class="panel events" aria-label="Race events">
      <table><thead><tr><th>km</th><th>Event</th><th>Details</th></tr></thead><tbody id="rows"></tbody></table>
    </section>
  </div>
  <p class="note" id="note"></p>
</div>
<script id="stage-data" type="application/json">__DATA__</script>
<script>
(function () {
  const D = JSON.parse(document.getElementById('stage-data').textContent);
  const S = D.samples, N = S.length, NS = 'http://www.w3.org/2000/svg';
  const km = S.map(s => s[0]), alt = S.map(s => s[1]);
  const el = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
  const fmt = (v, d = 1) => v.toFixed(d);
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  // ---- gradients (computed by the parser, 500 m window) and their classes
  const grad = D.gradients;
  const GCLS = [[3, '--g0', '< 3 %'], [6, '--g1', '3–6 %'], [9, '--g2', '6–9 %'], [12, '--g3', '9–12 %'], [1e9, '--g4', '> 12 %']];
  const gcls = g => GCLS.findIndex(c => g < c[0]);
  const idxAt = k => { let lo = 0, hi = N - 1; while (lo < hi) { const m = (lo + hi) >> 1; if (km[m] < k) lo = m + 1; else hi = m; } return lo; };

  // ---- events (KOMs that top a climb are attached to it by the parser)
  const ev = D.events;
  const climbs = ev.filter(e => e.kind === 'climb');
  const shown = ev.filter(e => !e.merged);

  // ---- header
  document.getElementById('name').textContent = D.name || 'Stage';
  document.getElementById('region').textContent = D.region || '';
  const sectorKm = kind => ev.filter(e => e.kind === kind).reduce((t, e) => t + (e.end_km - e.km), 0);
  const stats = [[fmt(D.distance_km), 'km'], [Math.round(D.gain_m).toLocaleString('en'), 'm climbing'], [Math.round(D.max_alt), 'm highest point'],
    [climbs.length, climbs.length === 1 ? 'climb' : 'climbs']];
  if (sectorKm('cobbles') > 0) stats.push([fmt(sectorKm('cobbles')), 'km cobbles']);
  if (sectorKm('gravel') > 0) stats.push([fmt(sectorKm('gravel')), 'km gravel']);
  document.getElementById('stats').innerHTML = stats.map(s => `<div><b>${s[0]}</b><span>${s[1]}</span></div>`).join('');
  document.getElementById('note').textContent = ({
    cds: 'Elevation and race points from the stage’s .cds file; route, climbs and sectors from the .zces file.',
    'cds-approx': 'Elevation from the stage’s .cds file. The route could not be matched to it exactly, so map positions are approximate.',
    zces: 'Elevation from the .zces road geometry (no .cds file used), so it may differ slightly from the game’s profile.'
  })[D.profile_source] + ' Game units converted to metres (distance ×10, height ×7.5).' +
    (D.geo ? ' Coordinates come from the stage’s terrain bounds: the game world is the real area at 1:10 scale, so positions are as accurate as the stage’s own roads.' : ' This stage has no real-world location.');
  document.getElementById('legend').innerHTML = GCLS.map(c => `<span><i style="background:var(${c[1]})"></i>${c[2]}</span>`).join('') +
    '<span><i class="b-cobbles" style="height:9px"></i>cobbles</span><span><i class="b-gravel" style="height:9px"></i>gravel</span>';

  // ---- event list
  const LABEL = { start: 'Start', finish: 'Finish', kom: 'KOM', sprint: 'Sprint', climb: 'Climb', cobbles: 'Cobbles', gravel: 'Gravel' };
  const BADGE = { start: '', finish: '', kom: '', sprint: 'S', climb: '▲', cobbles: '', gravel: '' };
  const stars = n => '<span class="stars">' + '★'.repeat(n) + '</span>';
  function detail(e) {
    if (e.kind === 'climb') {
      let s = `${fmt(e.end_km - e.km)} km · ${fmt(e.avg)} % avg · ${fmt(e.max)} % max`;
      if (e.kom) s += ` · KOM category code ${e.kom.code}`;
      return s;
    }
    if (e.kind === 'cobbles' || e.kind === 'gravel') return `${stars(e.stars)} · ${fmt(e.end_km - e.km)} km`;
    if (e.kind === 'kom') return `category code ${e.code}`;
    if (e.kind === 'finish') return e.summit ? 'Summit finish' : 'Flat finish';
    return '';
  }
  const rows = document.getElementById('rows');
  shown.forEach((e, i) => {
    const tr = document.createElement('tr');
    tr.tabIndex = 0; tr.dataset.i = i;
    const kind = e.kind === 'climb' && e.kom ? 'kom' : e.kind;
    let link = '';
    if (D.geo) {
      const s = S[idxAt(e.kind === 'climb' ? e.end_km : Math.max(km[0], e.km))];
      link = ` · <a class="osm" href="https://www.openstreetmap.org/?mlat=${s[4]}&amp;mlon=${s[5]}#map=15/${s[4]}/${s[5]}" target="_blank" rel="noopener">${s[4].toFixed(4)}, ${s[5].toFixed(4)} ↗</a>`;
    }
    tr.innerHTML = `<td class="km">${fmt(Math.max(0, e.km))}</td><td class="name"><span class="badge b-${kind}">${BADGE[kind]}</span>${(e.name || LABEL[e.kind]).replace(/</g, '&lt;')}</td><td class="detail">${LABEL[e.kind]}${detail(e) ? ' · ' + detail(e) : ''}${link}</td>`;
    const on = () => highlight(e, tr), off = () => highlight(null);
    tr.addEventListener('mouseenter', on); tr.addEventListener('mouseleave', off);
    tr.addEventListener('focus', on); tr.addEventListener('blur', off);
    rows.appendChild(tr);
  });

  // ---- map: OpenStreetMap basemap (Leaflet) when available, otherwise a drawn map
  const MARK = e => ({ start: '--route', finish: '--ink', kom: '--kom', sprint: '--sprint', climb: e.kom ? '--kom' : '--g3' })[e.kind];
  const markable = shown.filter(e => ['start', 'finish', 'kom', 'sprint', 'climb'].includes(e.kind));
  const at = k => S[idxAt(k)];
  const M = D.geo && D.basemap && window.L ? leafletMap() : svgMap();

  function leafletMap() {
    const box = document.getElementById('lmap');
    box.hidden = false;
    document.getElementById('map').remove();
    document.getElementById('mapcap').textContent = 'Route on OpenStreetMap · hover the route or the profile';
    const lm = L.map(box, { scrollWheelZoom: false, zoomSnap: 0.25 });
    lm.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      { maxZoom: 18, attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).addTo(lm);
    const ll = S.map(s => [s[4], s[5]]);
    const route = L.polyline(ll, { color: css('--route'), weight: 4, opacity: .9 }).addTo(lm);
    lm.fitBounds(route.getBounds(), { padding: [14, 14] });
    const hi = L.polyline([], { color: css('--route-hi'), weight: 8, opacity: .95 }).addTo(lm);
    for (const e of markable) {
      const s = at(e.kind === 'climb' ? e.end_km : e.km);
      L.circleMarker([s[4], s[5]], { radius: e.kind === 'start' || e.kind === 'finish' ? 7 : 5, color: '#fff', weight: 2,
        fillColor: css(MARK(e)), fillOpacity: 1 }).bindTooltip(e.name || LABEL[e.kind]).addTo(lm);
    }
    const dot = L.circleMarker([0, 0], { radius: 7, color: css('--ink'), weight: 2, fillColor: css('--route-hi'), fillOpacity: 1 });
    lm.on('mousemove', ev => {
      const p = ev.containerPoint;
      let best = -1, bd = 30 * 30;
      for (let i = 0; i < N; i += 1) {
        const q = lm.latLngToContainerPoint(ll[i]), d = (q.x - p.x) ** 2 + (q.y - p.y) ** 2;
        if (d < bd) { bd = d; best = i; }
      }
      cursor(best);
    });
    lm.on('mouseout', () => cursor(-1));
    return {
      dot(i) { if (i < 0) dot.remove(); else dot.setLatLng(ll[i]).addTo(lm); },
      hi(a, b) { hi.setLatLngs(a < 0 ? [] : ll.slice(a, b + 1)); },
    };
  }

  function svgMap() {
  const map = document.getElementById('map');
  let mx0 = Infinity, my0 = Infinity, mx1 = -Infinity, my1 = -Infinity;
  for (const s of S) { mx0 = Math.min(mx0, s[2]); mx1 = Math.max(mx1, s[2]); my0 = Math.min(my0, s[3]); my1 = Math.max(my1, s[3]); }
  const span = Math.max(mx1 - mx0, my1 - my0) * 1.08 || 1, cx = (mx0 + mx1) / 2, cy = (my0 + my1) / 2;
  const MV = 1000, mpx = x => (x - cx) / span * MV + MV / 2, mpy = y => MV / 2 - (y - cy) / span * MV;
  map.setAttribute('viewBox', `0 0 ${MV} ${MV}`);
  if (D.geo) document.getElementById('mapcap').textContent =
    `Route map · north up · ${S[0][4].toFixed(3)}°, ${S[0][5].toFixed(3)}° at the start · grey lines are the stage’s other roads`;
  const ctx = el('g', { fill: 'none', stroke: 'var(--rule)', 'stroke-width': 2.2, 'stroke-linecap': 'round' }, map);
  for (const r of D.roads) {
    let d = '';
    for (let i = 0; i < r.length; i += 2) d += (i ? 'L' : 'M') + mpx(r[i]).toFixed(1) + ' ' + mpy(r[i + 1]).toFixed(1);
    el('path', { d }, ctx);
  }
  const routeD = S.map((s, i) => (i ? 'L' : 'M') + mpx(s[2]).toFixed(1) + ' ' + mpy(s[3]).toFixed(1)).join('');
  el('path', { d: routeD, fill: 'none', stroke: 'var(--panel)', 'stroke-width': 9, 'stroke-linejoin': 'round' }, map);
  el('path', { d: routeD, fill: 'none', stroke: 'var(--route)', 'stroke-width': 4.5, 'stroke-linejoin': 'round' }, map);
  const mapHi = el('path', { d: '', fill: 'none', stroke: 'var(--route-hi)', 'stroke-width': 9, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, map);
  const mapMarks = el('g', {}, map);
  for (const e of markable) {
    const s = at(e.kind === 'climb' ? e.end_km : e.km), x = mpx(s[2]), y = mpy(s[3]);
    el('circle', { cx: x, cy: y, r: e.kind === 'finish' || e.kind === 'start' ? 13 : 9, fill: `var(${MARK(e)})`, stroke: 'var(--panel)', 'stroke-width': 3 }, mapMarks);
  }
  const mapDot = el('circle', { r: 14, fill: 'var(--route-hi)', stroke: 'var(--ink)', 'stroke-width': 3, visibility: 'hidden' }, map);
  const pt = map.createSVGPoint();
  map.addEventListener('mousemove', ev => {
    pt.x = ev.clientX; pt.y = ev.clientY;
    const p = pt.matrixTransform(map.getScreenCTM().inverse());
    let best = 0, bd = Infinity;
    for (let i = 0; i < N; i++) { const dx = mpx(S[i][2]) - p.x, dy = mpy(S[i][3]) - p.y, d = dx * dx + dy * dy; if (d < bd) { bd = d; best = i; } }
    if (bd < 60 * 60) cursor(best); else cursor(-1);
  });
  map.addEventListener('mouseleave', () => cursor(-1));
  return {
    dot(i) {
      mapDot.setAttribute('visibility', i < 0 ? 'hidden' : 'visible');
      if (i >= 0) { mapDot.setAttribute('cx', mpx(S[i][2])); mapDot.setAttribute('cy', mpy(S[i][3])); }
    },
    hi(a, b) {
      mapHi.setAttribute('d', a < 0 ? '' : S.slice(a, b + 1).map((s, j) => (j ? 'L' : 'M') + mpx(s[2]).toFixed(1) + ' ' + mpy(s[3]).toFixed(1)).join(''));
    },
  };
  }

  // ---- profile
  const prof = document.getElementById('prof'), tip = document.getElementById('tip');
  let P = null;
  function drawProfile() {
    const W = Math.max(320, prof.parentNode.clientWidth - 24);
    const narrow = W < 560;
    const longest = Math.max(4, ...shown.filter(e => ['climb', 'kom', 'sprint', 'finish', 'start'].includes(e.kind))
      .map(e => Math.min((e.name || '').length + (e.kind === 'climb' ? 6 : 0), narrow ? 14 : 22)));
    const labelBand = Math.round(34 + longest * 6.6);
    const H = labelBand + (narrow ? 170 : 240) + 62;
    const m = { l: 46, r: 14, t: labelBand, b: 62 };
    prof.setAttribute('viewBox', `0 0 ${W} ${H}`);
    prof.innerHTML = '';
    const defs = el('defs', {}, prof);
    const pv = el('pattern', { id: 'pave', width: 6, height: 6, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' }, defs);
    el('rect', { width: 3, height: 6, fill: 'var(--pave)' }, pv);
    const gv = el('pattern', { id: 'grav', width: 5, height: 5, patternUnits: 'userSpaceOnUse' }, defs);
    el('circle', { cx: 2.5, cy: 2.5, r: 1.3, fill: 'var(--gravel)' }, gv);
    const lo0 = Math.min(...alt), hi0 = Math.max(...alt);
    const step = niceStep((hi0 - lo0) / 4 || 10);
    const ylo = Math.max(0, Math.floor(lo0 / step) * step - (lo0 < step ? 0 : step)), yhi = Math.ceil(hi0 / step) * step + (hi0 - lo0 < 30 ? step : 0);
    const x = k => m.l + (k - km[0]) / (km[N - 1] - km[0]) * (W - m.l - m.r);
    const y = a => m.t + (1 - (a - ylo) / (yhi - ylo)) * (H - m.t - m.b);
    const base = y(ylo);
    P = { x, y, W, H, m, base };
    // grid
    const grid = el('g', {}, prof);
    for (let a = ylo; a <= yhi + 1e-6; a += step) {
      el('line', { x1: m.l, x2: W - m.r, y1: y(a), y2: y(a), stroke: 'var(--grid)', 'stroke-width': 1 }, grid);
      el('text', { x: m.l - 6, y: y(a) + 4, 'text-anchor': 'end' }, grid).textContent = Math.round(a);
    }
    el('text', { x: m.l - 6, y: m.t - 8, 'text-anchor': 'end' }, grid).textContent = 'm';
    const kstep = niceStep((km[N - 1] - km[0]) / (narrow ? 5 : 10));
    for (let k = Math.ceil(km[0] / kstep) * kstep; k <= km[N - 1] + 1e-6; k += kstep) {
      el('line', { x1: x(k), x2: x(k), y1: base, y2: base + 4, stroke: 'var(--muted)' }, grid);
      el('text', { x: x(k), y: base + 16, 'text-anchor': 'middle' }, grid).textContent = Math.round(k);
    }
    el('text', { x: W - m.r, y: base + 16, 'text-anchor': 'end' }, grid).textContent = 'km';
    // highlight band (under the fill)
    P.band = el('rect', { y: m.t - 4, height: base - m.t + 4, fill: 'var(--hi)', visibility: 'hidden' }, prof);
    // gradient-coloured fill, one polygon per run of equal class
    const fill = el('g', {}, prof);
    let i0 = 0;
    for (let i = 1; i <= N; i++) {
      if (i < N && gcls(grad[i]) === gcls(grad[i0])) continue;
      const a = Math.max(0, i0 - 1), b = Math.min(N - 1, i);
      let d = `M${x(km[a])} ${base}`;
      for (let j = a; j <= b; j++) d += `L${x(km[j]).toFixed(1)} ${y(alt[j]).toFixed(1)}`;
      d += `L${x(km[b])} ${base}Z`;
      el('path', { d, fill: `var(${GCLS[gcls(grad[i0])][1]})` }, fill);
      i0 = i;
    }
    el('path', { d: km.map((k, j) => (j ? 'L' : 'M') + x(k).toFixed(1) + ' ' + y(alt[j]).toFixed(1)).join(''), fill: 'none', stroke: 'var(--ink)', 'stroke-width': 1.4 }, prof);
    el('line', { x1: m.l, x2: W - m.r, y1: base, y2: base, stroke: 'var(--muted)' }, prof);
    // sector strips under the axis
    const strips = [['cobbles', 'url(#pave)', 'var(--pave)', base + 26], ['gravel', 'url(#grav)', 'var(--gravel)', base + 42]];
    for (const [kind, pat, col, sy] of strips) {
      const list = ev.filter(e => e.kind === kind);
      if (!list.length) continue;
      el('text', { x: m.l - 6, y: sy + 8, 'text-anchor': 'end' }, prof).textContent = kind === 'cobbles' ? 'pavé' : 'gravel';
      el('line', { x1: m.l, x2: W - m.r, y1: sy + 5, y2: sy + 5, stroke: 'var(--grid)' }, prof);
      for (const e of list) {
        const w = Math.max(2.5, x(e.end_km) - x(e.km));
        el('rect', { x: x(e.km), y: sy, width: w, height: 10, fill: pat, stroke: col, 'stroke-width': 1 }, prof);
      }
    }
    // labels: climbs (at summit) and race points, as vertical text above the profile
    const lab = shown.filter(e => ['climb', 'kom', 'sprint', 'finish', 'start'].includes(e.kind))
      .map(e => ({ e, k: e.kind === 'climb' ? e.end_km : Math.max(km[0], e.km) })).sort((a, b) => a.k - b.k);
    const gap = 13; let last = -1e9;
    for (const L of lab) { L.px = x(L.k); L.lx = Math.max(L.px, last + gap); last = L.lx; }
    for (let i = lab.length - 1, nxt = W - m.r + gap; i >= 0; i--) { lab[i].lx = Math.min(lab[i].lx, nxt - gap); nxt = lab[i].lx; }
    const lg = el('g', {}, prof);
    for (const L of lab) {
      const e = L.e, py = y(alt[idxAt(L.k)]);
      const kind = e.kind === 'climb' && e.kom ? 'kom' : e.kind;
      const col = { kom: 'var(--kom)', sprint: 'var(--sprint)', climb: 'var(--g3)', finish: 'var(--ink)', start: 'var(--route)' }[kind];
      el('path', { d: `M${L.px} ${py - 2}L${L.px} ${m.t - 2}L${L.lx} ${m.t - 10}`, fill: 'none', stroke: col, 'stroke-width': 1, 'stroke-dasharray': '2 2' }, lg);
      el('circle', { cx: L.lx, cy: m.t - 14, r: 4.5, fill: col }, lg);
      let name = e.name || LABEL[e.kind];
      if (e.kind === 'climb') name += `  ${fmt(e.avg)}%`;
      if (name.length > (narrow ? 14 : 22)) name = name.slice(0, narrow ? 13 : 21) + '…';
      const t = el('text', { class: 'label', x: L.lx + 4, y: m.t - 22, transform: `rotate(-90 ${L.lx + 4} ${m.t - 22})` }, lg);
      t.textContent = name;
      t.setAttribute('x', L.lx + 4 - 0); t.setAttribute('dy', 0);
    }
    P.cursor = el('line', { y1: m.t - 4, y2: base, stroke: 'var(--ink)', 'stroke-width': 1, visibility: 'hidden' }, prof);
    P.dot = el('circle', { r: 4, fill: 'var(--route-hi)', stroke: 'var(--ink)', 'stroke-width': 1.5, visibility: 'hidden' }, prof);
    el('rect', { x: m.l, y: m.t - 4, width: W - m.l - m.r, height: base - m.t + 4, fill: 'transparent', id: 'hit' }, prof);
  }
  function niceStep(v) { const p = Math.pow(10, Math.floor(Math.log10(v))), f = v / p; return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p; }

  function cursor(i) {
    if (!P) return;
    const vis = i >= 0 ? 'visible' : 'hidden';
    P.cursor.setAttribute('visibility', vis); P.dot.setAttribute('visibility', vis);
    M.dot(i);
    tip.hidden = i < 0;
    if (i < 0) return;
    const px = P.x(km[i]), py = P.y(alt[i]);
    P.cursor.setAttribute('x1', px); P.cursor.setAttribute('x2', px);
    P.dot.setAttribute('cx', px); P.dot.setAttribute('cy', py);
    const inside = ev.filter(e => e.end_km !== undefined && km[i] >= e.km && km[i] <= e.end_km).map(e => e.name);
    tip.innerHTML = `${fmt(km[i])} km · ${Math.round(alt[i])} m · ${grad[i] >= 0 ? '+' : ''}${fmt(grad[i])} %` +
      (D.geo ? `<br>${S[i][4].toFixed(5)}, ${S[i][5].toFixed(5)}` : '') +
      (inside.length ? `<br>${inside[0].replace(/</g, '&lt;')}` : '');
    const box = prof.getBoundingClientRect(), scale = box.width / P.W;
    tip.style.left = Math.min(Math.max(12 + px * scale, 80), box.width - 70) + 'px';
    tip.style.top = (12 + (py - 10) * scale) + 'px';
  }
  function highlight(e, tr) {
    for (const r of rows.children) r.classList.toggle('on', r === tr);
    if (!e) { P.band.setAttribute('visibility', 'hidden'); M.hi(-1); cursor(-1); return; }
    const k0 = e.km, k1 = e.end_km !== undefined ? e.end_km : e.km;
    if (e.end_km !== undefined) {
      P.band.setAttribute('x', P.x(Math.max(km[0], k0))); P.band.setAttribute('width', Math.max(2, P.x(k1) - P.x(Math.max(km[0], k0))));
      P.band.setAttribute('visibility', 'visible');
      const a = idxAt(k0), b = idxAt(k1);
      M.hi(a, b);
      cursor(b);
    } else { P.band.setAttribute('visibility', 'hidden'); M.hi(-1); cursor(idxAt(k0)); }
  }
  prof.addEventListener('mousemove', ev => {
    if (!P) return;
    const box = prof.getBoundingClientRect(), px = (ev.clientX - box.left) / box.width * P.W;
    if (px < P.m.l || px > P.W - P.m.r) { cursor(-1); return; }
    const k = km[0] + (px - P.m.l) / (P.W - P.m.l - P.m.r) * (km[N - 1] - km[0]);
    cursor(idxAt(k));
  });
  prof.addEventListener('mouseleave', () => cursor(-1));
  drawProfile();
  let rt; new ResizeObserver(() => { clearTimeout(rt); rt = setTimeout(drawProfile, 80); }).observe(prof.parentNode);
})();
</script>
"""


LEAFLET = ('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">\n'
           '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>')


def profile_html(view, source_name='', standalone=True):
    """Render the page. `standalone` wraps it in a full HTML document; without
    it the result is the page body as published by claude.ai Artifacts."""
    # The standalone file shows the route on OpenStreetMap tiles (Leaflet). A
    # claude.ai artifact cannot load map tiles, so it keeps the drawn map.
    view = dict(view, basemap=bool(standalone and view.get('geo')))
    data = json.dumps(view, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    title = view.get('name') or 'Stage profile'
    leaflet = (LEAFLET if view['basemap'] else '')
    page = (TEMPLATE.replace('__TITLE__', html.escape(title + ' profile'))
            .replace('__LEAFLET__', leaflet)
            .replace('__FILE__', html.escape(source_name))
            .replace('__DATA__', data))
    if standalone:
        page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                + page.replace('<div class="wrap">', '</head>\n<body>\n<div class="wrap">', 1)
                + '</body>\n</html>\n')
    return page
