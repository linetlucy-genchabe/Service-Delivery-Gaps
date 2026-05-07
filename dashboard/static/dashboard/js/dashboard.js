/* ============================================================
   Service Delivery Gaps Dashboard – dashboard.js
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {
  initTabs();
  initDefinitionModal();
  if (typeof HAS_BATCH !== 'undefined' && HAS_BATCH) {
    loadTable('unsupervised');
  }
});

// ── Filter submission (keeps all values) ──────────────────────
function submitFilters() {
  const form = document.getElementById('filter-form');
  if (form) form.submit();
}

// ── Tab switching ─────────────────────────────────────────────
function initTabs() {
  const btns   = document.querySelectorAll('.tab-btn');
  const panels = document.querySelectorAll('.tab-panel');
  btns.forEach(btn => {
    btn.addEventListener('click', function () {
      const tab = this.dataset.tab;
      btns.forEach(b => b.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));
      this.classList.add('active');
      document.getElementById('tab-' + tab).classList.add('active');
      loadTable(tab);
    });
  });
}

// ── Table loader ──────────────────────────────────────────────
const _loaded = {};

function loadTable(tab) {
  if (_loaded[tab]) return;
  _loaded[tab] = true;

  const params = new URLSearchParams({
    batch:      BATCH_ID || '',
    county:     COUNTY || '',
    sub_county: SUB_COUNTY || '',
    chu:        CHU || '',
  });

  const endpoints = {
    'unsupervised':       '/api/unsupervised/',
    'lp-not-supervised':  '/api/low-performers/?group=unsupervised&',
    'lp-supervised':      '/api/low-performers/?group=supervised&',
    'anc-gap':            '/api/anc-gap/',
    'same-day':           '/api/same-day-flags/',
  };

  // Build URL — handle endpoint with existing query params
  let url;
  const ep = endpoints[tab];
  if (ep.includes('?')) {
    url = ep + params.toString();
  } else {
    url = ep + '?' + params.toString();
  }

  fetch(url)
    .then(r => r.json())
    .then(data => renderTable(tab, data))
    .catch(() => {
      const c = getContainer(tab);
      if (c) c.innerHTML = '<div class="table-empty" style="color:var(--red)">Error loading data. Please refresh.</div>';
    });
}

function getContainer(tab) {
  const map = {
    'unsupervised':      'unsupervised-table-container',
    'lp-not-supervised': 'lp-not-supervised-table-container',
    'lp-supervised':     'lp-supervised-table-container',
    'anc-gap':           'anc-gap-table-container',
    'same-day':          'same-day-table-container',
  };
  return document.getElementById(map[tab]);
}

function renderTable(tab, data) {
  const c = getContainer(tab);
  if (!c) return;
  if (!data.results || data.results.length === 0) {
    c.innerHTML = '<div class="table-empty">✅ No records — great result!</div>';
    return;
  }
  if (tab === 'unsupervised')       renderUnsupervisedTable(c, data.results);
  else if (tab === 'lp-not-supervised') renderLowPerfTable(c, data.results, data.threshold, false);
  else if (tab === 'lp-supervised')     renderLowPerfTable(c, data.results, data.threshold, true);
  else if (tab === 'anc-gap')       renderAncGapTable(c, data.results);
  else if (tab === 'same-day')      renderSameDayTable(c, data.results);
}

// ── Unsupervised ──────────────────────────────────────────────
function renderUnsupervisedTable(c, rows) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th><th>CHP ID</th>
    <th class="num">HH Visits</th><th class="num">Days Synced</th><th class="num">Supervision Visits</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    const hh = r.hh_visits || 0, syn = r.days_synced || 0;
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td><td class="zero">${esc(r.chw_id)}</td>
      <td class="num ${hh===0?'bad':hh<10?'warn':''}">${hh}</td>
      <td class="num ${syn===0?'bad':''}">${syn}</td>
      <td class="num zero">0</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} unsupervised CHP(s)</div>`;
  c.innerHTML = h;
}

// ── Low Performers (both groups) ──────────────────────────────
function renderLowPerfTable(c, rows, threshold, wasSup) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th><th>CHP ID</th>
    <th class="num">HH Visits</th><th class="num">Days Synced</th>
    <th class="num">Supervision Visits</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    const hh = r.hh_visits || 0, syn = r.days_synced || 0, sv = r.supervision_visits || 0;
    const hhCls = hh === 0 ? 'bad' : hh < Math.floor(threshold/2) ? 'warn' : '';
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td><td class="zero">${esc(r.chw_id)}</td>
      <td class="num ${hhCls}">${hh}</td>
      <td class="num ${syn===0?'bad':''}">${syn}</td>
      <td class="num ${wasSup?'good':'bad'}">${sv}</td></tr>`;
  });
  const label = wasSup
    ? `${rows.length} CHP(s) supervised but still below ${threshold} HH visit threshold`
    : `${rows.length} CHP(s) below ${threshold} HH visits AND unsupervised — highest risk`;
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${label}</div>`;
  c.innerHTML = h;
}

// ── ANC Gap ───────────────────────────────────────────────────
function renderAncGapTable(c, rows) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th><th>CHP ID</th>
    <th class="num">Active Pregnancies</th><th class="num">Pregnancies Visited</th>
    <th class="num">Gap (Unvisited)</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    const gap = r.gap || (r.active_pregnancies - r.pregnancies_visited);
    const gapCls = gap > 5 ? 'bad' : gap > 2 ? 'warn' : '';
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td><td class="zero">${esc(r.chw_id)}</td>
      <td class="num">${r.active_pregnancies}</td>
      <td class="num">${r.pregnancies_visited}</td>
      <td class="num ${gapCls}">${gap}</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} CHP(s) with at least one unvisited active pregnancy</div>`;
  c.innerHTML = h;
}

// ── Same-Day Flags ────────────────────────────────────────────
function renderSameDayTable(c, rows) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>Visit Date</th><th class="num">CHPs Supervised</th><th>Flag Level</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    const cnt = r.count || 0;
    const cls = cnt >= 10 ? 'bad' : 'warn';
    const flag = cnt >= 10 ? '🔴 High' : '🟡 Moderate';
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td>
      <td>${esc(r.visit_date)}</td>
      <td class="num ${cls}">${cnt}</td>
      <td><span class="${cls}">${flag}</span></td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} CHU/date combination(s) flagged for review</div>`;
  c.innerHTML = h;
}

// ── Definition Modal ──────────────────────────────────────────
function initDefinitionModal() {
  document.querySelectorAll('.definition-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      document.getElementById('def-modal-body').textContent = this.dataset.def;
      document.getElementById('def-modal').style.display = 'flex';
    });
  });
  document.getElementById('def-modal')?.addEventListener('click', function(e) {
    if (e.target === this) closeModal();
  });
}

function closeModal() {
  document.getElementById('def-modal').style.display = 'none';
}

function esc(str) {
  if (str == null) return '—';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
