/* ============================================================
   Service Delivery Gaps Dashboard – dashboard.js
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {
  initCategoryNav();
  initDrilldownCatNav();
  initTabs();
  initDefinitionModal();
  // Load the default active tab in the default active dd-cat-panel
  if (typeof HAS_BATCH !== 'undefined' && HAS_BATCH && typeof BATCH_ID !== 'undefined' && BATCH_ID) {
    const defaultPanel = document.querySelector('.dd-cat-panel.active');
    if (defaultPanel) {
      const defaultTab = defaultPanel.querySelector('.tab-btn.active');
      if (defaultTab) loadTable(defaultTab.dataset.tab);
    }
  }
});

// ── Filter submission ─────────────────────────────────────────
function submitFilters() {
  const form = document.getElementById('filter-form');
  if (form) form.submit();
}

// ── Category nav ──────────────────────────────────────────────
function initCategoryNav() {
  const btns     = document.querySelectorAll('.cat-btn');
  const sections = document.querySelectorAll('.cat-section');
  btns.forEach(btn => {
    btn.addEventListener('click', function () {
      btns.forEach(b => b.classList.remove('active'));
      sections.forEach(s => s.classList.remove('active'));
      this.classList.add('active');
      const sec = document.getElementById('section-' + this.dataset.section);
      if (sec) sec.classList.add('active');
    });
  });
}

// ── Drill-down category nav ───────────────────────────────────
function initDrilldownCatNav() {
  const btns   = document.querySelectorAll('.dd-cat-btn');
  const panels = document.querySelectorAll('.dd-cat-panel');
  btns.forEach(btn => {
    btn.addEventListener('click', function () {
      btns.forEach(b => b.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));
      this.classList.add('active');
      const panel = document.getElementById(this.dataset.ddcat);
      if (panel) {
        panel.classList.add('active');
        // Always load the active tab in this panel when switching to it
        const activeTab = panel.querySelector('.tab-btn.active');
        if (activeTab) loadTable(activeTab.dataset.tab);
      }
    });
  });
}

// ── Tab switching ─────────────────────────────────────────────
function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      const tab    = this.dataset.tab;
      // scope to the nearest tab-bar parent container
      const panel  = this.closest('.dd-cat-panel') || document;
      panel.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      panel.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
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

  const params = new URLSearchParams({
    batch: BATCH_ID || '', county: COUNTY || '',
    sub_county: SUB_COUNTY || '', chu: CHU || '',
  });

  const endpoints = {
    'inactive-chps':      '/api/inactive-chps/',
    'unsupervised':       '/api/unsupervised/',
    'lp-not-supervised':  '/api/low-performers/?group=unsupervised&',
    'lp-supervised':      '/api/low-performers/?group=supervised&',
    'supervised-3plus':   '/api/supervised-3plus/',
    'anc-gap':            '/api/anc-gap/',
    'zero-pregnancies':   '/api/zero-pregnancies/',
    'u5-high-hh':         '/api/u5-gap/?type=high_hh_low_u5&',
    'u5-high-u5':         '/api/u5-gap/?type=high_u5_low_pos&',
    'low-iccm':           '/api/low-iccm/',
    'zero-positive':      '/api/zero-positive/',
    'same-day':           '/api/same-day-flags/',
  };

  const ep  = endpoints[tab];
  if (!ep) return;
  const url = ep.includes('?') ? ep + params.toString() : ep + '?' + params.toString();

  // Mark loading
  const c = getContainer(tab);
  if (!c) return;
  c.innerHTML = '<div class="table-loading">Loading…</div>';

  fetch(url)
    .then(r => r.json())
    .then(data => {
      renderTable(tab, data);
      _loaded[tab] = true;  // cache only after successful render
    })
    .catch(() => {
      c.innerHTML = '<div class="table-empty" style="color:var(--red)">Error loading data. Click the tab to retry.</div>';
    });
}

function getContainer(tab) {
  const map = {
    'inactive-chps':     'inactive-chps-container',
    'unsupervised':      'unsupervised-table-container',
    'lp-not-supervised': 'lp-not-supervised-table-container',
    'lp-supervised':     'lp-supervised-table-container',
    'supervised-3plus':  'supervised-3plus-container',
    'anc-gap':           'anc-gap-table-container',
    'zero-pregnancies':  'zero-pregnancies-container',
    'u5-high-hh':        'u5-high-hh-container',
    'u5-high-u5':        'u5-high-u5-container',
    'low-iccm':          'low-iccm-container',
    'zero-positive':     'zero-positive-container',
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
  if      (tab === 'inactive-chps')    renderInactiveChpsTable(c, data.results);
  else if (tab === 'unsupervised')      renderUnsupervisedTable(c, data.results);
  else if (tab === 'lp-not-supervised') renderLowPerfTable(c, data.results, data.threshold, false);
  else if (tab === 'lp-supervised')     renderLowPerfTable(c, data.results, data.threshold, true);
  else if (tab === 'supervised-3plus')  renderSup3PlusTable(c, data.results);
  else if (tab === 'anc-gap')           renderAncGapTable(c, data.results);
  else if (tab === 'zero-pregnancies')  renderZeroPregnanciesTable(c, data.results);
  else if (tab === 'u5-high-hh')        renderU5HighHHTable(c, data.results);
  else if (tab === 'u5-high-u5')        renderU5HighU5Table(c, data.results);
  else if (tab === 'low-iccm')          renderLowICCMTable(c, data.results);
  else if (tab === 'zero-positive')     renderZeroPositiveTable(c, data.results);
  else if (tab === 'same-day')          renderSameDayTable(c, data.results);
}

// ── Inactive CHPs ─────────────────────────────────────────────
function renderInactiveChpsTable(c, rows) {
  if (!rows || rows.length === 0) {
    c.innerHTML = '<div class="table-empty">✅ No inactive CHPs found.</div>';
    return;
  }
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td>
      <td>${esc(r.chp_area)}</td><td>${esc(r.chw_name)}</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} inactive CHP(s)</div>`;
  c.innerHTML = h;
}

// ── Unsupervised ──────────────────────────────────────────────
function renderUnsupervisedTable(c, rows) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th>
    <th class="num">HH Visits</th><th class="num">Days Synced</th><th class="num">Supervision Visits</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    const hh = r.hh_visits || 0, syn = r.days_synced || 0;
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td>
      <td class="num ${hh===0?'bad':hh<10?'warn':''}">${hh}</td>
      <td class="num ${syn===0?'bad':''}">${syn}</td>
      <td class="num zero">0</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} unsupervised CHP(s)</div>`;
  c.innerHTML = h;
}

// ── Low Performers ────────────────────────────────────────────
function renderLowPerfTable(c, rows, threshold, wasSup) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th>
    <th class="num">HH Visits</th><th class="num">Days Synced</th><th class="num">Supervision Visits</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    const hh = r.hh_visits || 0, syn = r.days_synced || 0, sv = r.supervision_visits || 0;
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td>
      <td class="num ${hh===0?'bad':hh<Math.floor(threshold/2)?'warn':''}">${hh}</td>
      <td class="num ${syn===0?'bad':''}">${syn}</td>
      <td class="num ${wasSup?'good':'bad'}">${sv}</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} CHP(s)</div>`;
  c.innerHTML = h;
}

// ── Supervised 3+ ─────────────────────────────────────────────
function renderSup3PlusTable(c, rows) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th>
    <th class="num">HH Visits</th><th class="num">Supervision Visits</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    const sv = r.supervision_visits || 0;
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td>
      <td class="num">${r.hh_visits||0}</td>
      <td class="num warn">${sv}</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} CHP(s) with 3+ supervision visits</div>`;
  c.innerHTML = h;
}

// ── Zero Active Pregnancies ───────────────────────────────────
function renderZeroPregnanciesTable(c, rows) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th>
    <th class="num">HH Visits</th><th class="num">Pregnancies Registered</th><th class="num">Active Pregnancies</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td>
      <td class="num">${r.hh_visits||0}</td>
      <td class="num">${r.pregnancies_registered||0}</td>
      <td class="num bad">0</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} CHP(s) with zero active pregnancies</div>`;
  c.innerHTML = h;
}

// ── ANC Gap ───────────────────────────────────────────────────
function renderAncGapTable(c, rows) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th>
    <th class="num">Active Pregnancies</th><th class="num">Visited</th><th class="num">Gap</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    const gap = r.gap || (r.active_pregnancies - r.pregnancies_visited);
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td>
      <td class="num">${r.active_pregnancies}</td>
      <td class="num">${r.pregnancies_visited}</td>
      <td class="num ${gap>5?'bad':gap>2?'warn':''}">${gap}</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} CHP(s) with unvisited pregnancies</div>`;
  c.innerHTML = h;
}

// ── Zero Positive Diagnoses ───────────────────────────────────
function renderZeroPositiveTable(c, rows) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th>
    <th class="num">HH Visits</th><th class="num">U5 Assessed</th>
    <th class="num">iCCM Assessments</th><th class="num">Positive Diagnoses</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td>
      <td class="num">${r.hh_visits||0}</td>
      <td class="num">${r.num_u5_assessed||0}</td>
      <td class="num">${r.iccm_assessments||0}</td>
      <td class="num bad">0</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} CHP(s) with zero positive diagnoses</div>`;
  c.innerHTML = h;
}

// ── Low iCCM Assessments ──────────────────────────────────────
function renderLowICCMTable(c, rows) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th>
    <th class="num">HH Visits</th><th class="num">iCCM Assessments</th>
    <th class="num">Registered U5</th><th class="num">U5 Assessed</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    const iccm = r.iccm_assessments || 0;
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td>
      <td class="num">${r.hh_visits||0}</td>
      <td class="num ${iccm===0?'bad':'warn'}">${iccm}</td>
      <td class="num">${r.registered_children_u5||0}</td>
      <td class="num">${r.num_u5_assessed||0}</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} CHP(s) with fewer than 5 iCCM assessments</div>`;
  c.innerHTML = h;
}

// ── U5 High HH Low Assessment ─────────────────────────────────
function renderU5HighHHTable(c, rows) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th>
    <th class="num">HH Rate</th><th class="num">Registered U5</th>
    <th class="num">U5 Assessed</th><th class="num">U5 Assessment Rate</th>
    <th class="num">iCCM Assessments</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td>
      <td class="num good">${r.hh_rate_pct}%</td>
      <td class="num">${r.registered_children_u5}</td>
      <td class="num">${r.num_u5_assessed}</td>
      <td class="num bad">${r.u5_rate_pct}%</td>
      <td class="num ${(r.iccm_assessments||0)<5?'warn':''}">${r.iccm_assessments||0}</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} CHP(s) with high HH coverage but low U5 assessment</div>`;
  c.innerHTML = h;
}

// ── U5 High Assessment Low Positive ──────────────────────────
function renderU5HighU5Table(c, rows) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th>
    <th class="num">U5 Assessment Rate</th><th class="num">U5 Assessed</th>
    <th class="num">Positive Diagnoses</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td>
      <td class="num good">${r.u5_rate_pct}%</td>
      <td class="num">${r.num_u5_assessed}</td>
      <td class="num ${r.positive_diagnoses_u5===0?'bad':'warn'}">${r.positive_diagnoses_u5}</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} CHP(s) with high U5 assessment but fewer than 5 positive diagnoses</div>`;
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
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td>
      <td>${esc(r.visit_date)}</td>
      <td class="num ${cls}">${cnt}</td>
      <td><span class="${cls}">${cnt>=10?'🔴 High':'🟡 Moderate'}</span></td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} CHU/date combination(s) flagged</div>`;
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

function closeModal() { document.getElementById('def-modal').style.display = 'none'; }

function esc(str) {
  if (str == null) return '—';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}