/* ============================================================
   Service Delivery Gaps Dashboard – dashboard.js
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {
  initCategoryNav();
  initDrilldownCatNav();
  initTabs();
  initDefinitionModal();

  if (typeof HAS_BATCH !== 'undefined' && HAS_BATCH && typeof BATCH_ID !== 'undefined' && BATCH_ID) {
    initHihtSection();
    // Option 3: Pre-fetch inactive CHPs in background immediately
    // Store result so it renders instantly when user clicks the tab
    prefetchTable('inactive-chps');

    // Also load the default active tab in the default active dd-cat-panel
    const defaultPanel = document.querySelector('.dd-cat-panel.active');
    if (defaultPanel) {
      const defaultTab = defaultPanel.querySelector('.tab-btn.active');
      if (defaultTab) loadTable(defaultTab.dataset.tab);
    }
  }
});

// Option 1: Manual retry — clears cache and reloads
function retryTable(tab) {
  _loaded[tab]     = false;
  _prefetched[tab] = null;
  const c = getContainer(tab);
  if (c) c.innerHTML = '<div class="table-loading">Loading…</div>';
  loadTable(tab);
}

// Pre-fetch: fetch data now, store it, render when container is ready
const _prefetched = {};
function prefetchTable(tab) {
  if (_loaded[tab] || _prefetched[tab]) return;
  const params = new URLSearchParams({
    batch: BATCH_ID || '', county: COUNTY || '',
    sub_county: SUB_COUNTY || '', chu: CHU || '',
  });
  const endpoints = {
    'inactive-chps': '/api/inactive-chps/',
  };
  const ep = endpoints[tab];
  if (!ep) return;
  const url = ep + '?' + params.toString();

  fetch(url)
    .then(r => r.json())
    .then(data => {
      _prefetched[tab] = data;
      // Try to render immediately if container already exists
      const c = getContainer(tab);
      if (c) {
        renderTable(tab, data);
        _loaded[tab] = true;
      }
      // Otherwise it will render when loadTable is called on tab click
    })
    .catch(() => {});
}

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

  const c = getContainer(tab);
  if (!c) {
    setTimeout(() => loadTable(tab), 200);
    return;
  }

  // Option 3: Use prefetched data if already available
  if (_prefetched[tab]) {
    renderTable(tab, _prefetched[tab]);
    _loaded[tab] = true;
    return;
  }

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
    'mam-sam':            '/api/mam-sam/',
    'home-deliveries':    '/api/maternal-drilldown/?view=home_deliveries&',
    'pnc-48-missed':      '/api/maternal-drilldown/?view=pnc_48hr_missed&',
    'pnc-37-missed':      '/api/maternal-drilldown/?view=pnc_3_7d_missed&',
    'pnc-status':         '/api/maternal-drilldown/?view=pnc_status&',
    'iz-all':             '/api/iz-defaulters/',
    'iz-not-referred':    '/api/iz-defaulters/?status=not_referred&',
    'iz-not-completed':   '/api/iz-defaulters/?status=not_completed&',
  };

  const ep  = endpoints[tab];
  if (!ep) return;
  const url = ep.includes('?') ? ep + params.toString() : ep + '?' + params.toString();

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
    'mam-sam':           'mam-sam-container',
    'home-deliveries':   'home-deliveries-container',
    'pnc-48-missed':     'pnc-48-missed-container',
    'pnc-37-missed':     'pnc-37-missed-container',
    'pnc-status':        'pnc-status-container',
    'iz-all':            'iz-all-container',
    'iz-not-referred':   'iz-not-referred-container',
    'iz-not-completed':  'iz-not-completed-container',
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
  else if (tab === 'mam-sam')           renderMamSamTable(c, data.results);
  else if (tab === 'home-deliveries')   renderMaternalTable(c, data.results, 'home_deliveries');
  else if (tab === 'pnc-48-missed')     renderMaternalTable(c, data.results, 'pnc_48hr_missed');
  else if (tab === 'pnc-37-missed')     renderMaternalTable(c, data.results, 'pnc_3_7d_missed');
  else if (tab === 'pnc-status')        renderMaternalTable(c, data.results, 'pnc_status');
  else if (tab === 'iz-all' || tab === 'iz-not-referred' || tab === 'iz-not-completed')
                                          renderIzDefaultersTable(c, data.results);
}

// ── MAM/SAM referrals ────────────────────────────────────────
function statusClass(status) {
  if (status === 'Not referred') return 'bad';
  if (status && status.indexOf('not completed') !== -1) return 'warn';
  return 'good';
}

function renderMamSamTable(c, rows) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th>
    <th class="num">MAM/SAM Cases</th><th class="num">Referred</th>
    <th class="num">Referral Completed</th><th>Status</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td>
      <td class="num">${r.mam_sam_total||0}</td>
      <td class="num">${r.mam_sam_referred||0}</td>
      <td class="num">${r.mam_sam_referral_completed||0}</td>
      <td class="${statusClass(r.referral_status)}">${esc(r.referral_status)}</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} CHP(s) with MAM/SAM cases</div>`;
  c.innerHTML = h;
}

// ── Maternal drill-down (home deliveries / PNC gaps / PNC status) ─────────
function renderMaternalTable(c, rows, view) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th>
    <th class="num">Total Deliveries</th><th class="num">Facility Deliveries</th>
    <th class="num">Home Deliveries</th>
    <th class="num">PNC 48hr Missed</th><th class="num">PNC 3-7d Missed</th><th>PNC Status</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td>
      <td class="num">${r.total_deliveries||0}</td>
      <td class="num">${r.facility_deliveries||0}</td>
      <td class="num ${r.home_deliveries>0?'bad':''}">${r.home_deliveries||0}</td>
      <td class="num ${r.pnc_48_missed>0?'warn':''}">${r.pnc_48_missed||0}</td>
      <td class="num ${r.pnc_37_missed>0?'warn':''}">${r.pnc_37_missed||0}</td>
      <td class="${r.pnc_status==='Both PNC visits done'?'good':r.pnc_status==='Neither PNC visit done'?'bad':'warn'}">${esc(r.pnc_status)}</td></tr>`;
  });
  const labels = {
    home_deliveries:  'CHP(s) with at least one home delivery',
    pnc_48hr_missed:  'CHP(s) with a missed PNC 48hr visit',
    pnc_3_7d_missed:  'CHP(s) with a missed PNC 3-7d visit',
    pnc_status:       'CHP(s) not completing both PNC visits',
  };
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} ${labels[view]||''}</div>`;
  c.innerHTML = h;
}

// ── Immunization defaulters ────────────────────────────────────
function renderIzDefaultersTable(c, rows) {
  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>County</th><th>Sub-County</th><th>Community Health Unit</th>
    <th>CHP Area</th><th>CHP Name</th>
    <th class="num">Defaulters</th><th class="num">Followed Up</th>
    <th class="num">Completed</th><th>Status</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td>
      <td class="num">${r.iz_defaulters||0}</td>
      <td class="num">${r.iz_defaulters_followed||0}</td>
      <td class="num">${r.iz_defaulters_completed||0}</td>
      <td class="${statusClass(r.referral_status)}">${esc(r.referral_status)}</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} CHP(s)</div>`;
  c.innerHTML = h;
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
    <th class="num">iCCM Assessments</th>
    <th class="num">Positive Diagnoses</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    h += `<tr><td class="zero">${i+1}</td><td>${esc(r.county)}</td><td>${esc(r.sub_county)}</td>
      <td><strong>${esc(r.community_health_unit)}</strong></td><td>${esc(r.chp_area)}</td>
      <td>${esc(r.chw_name)}</td>
      <td class="num good">${r.u5_rate_pct}%</td>
      <td class="num">${r.num_u5_assessed}</td>
      <td class="num">${r.iccm_assessments||0}</td>
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

// ============================================================
// HIHT tab — geography breakdown + multi-month trend
// ============================================================
function initHihtSection() {
  const levelBtns = document.querySelectorAll('.hiht-level-btn');
  if (levelBtns.length) {
    // Jump straight to the next drill-down level below whatever the
    // top-level filters have already narrowed to, instead of always
    // resetting to "Sub-County" and making the person re-pick what
    // they already selected up top.
    let defaultLevel = 'sub_county';
    if (CHU) defaultLevel = 'chp';
    else if (SUB_COUNTY) defaultLevel = 'chu';
    else if (COUNTY) defaultLevel = 'sub_county';

    levelBtns.forEach(b => b.classList.toggle('active', b.dataset.level === defaultLevel));
    levelBtns.forEach(btn => {
      btn.addEventListener('click', function () {
        levelBtns.forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        loadHihtBreakdown(this.dataset.level);
      });
    });
    loadHihtBreakdown(defaultLevel);
  }

  const trendBtns = document.querySelectorAll('.hiht-trend-level-btn');
  if (trendBtns.length) {
    // Same idea for the trend heatmap: if a county is already selected up
    // top, go straight to the sub-county trend for that county rather than
    // the all-counties view.
    let defaultTrendLevel = COUNTY ? 'sub_county' : 'county';

    trendBtns.forEach(b => b.classList.toggle('active', b.dataset.level === defaultTrendLevel));
    trendBtns.forEach(btn => {
      btn.addEventListener('click', function () {
        trendBtns.forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        loadHihtTrend(this.dataset.level);
      });
    });
    loadHihtTrend(defaultTrendLevel);
  }
}

function loadHihtBreakdown(level) {
  const c = document.getElementById('hiht-breakdown-container');
  if (!c) return;
  c.innerHTML = '<div class="table-loading">Loading…</div>';

  const dl = document.getElementById('hiht-download-link');
  if (dl) {
    const params = new URLSearchParams({
      batch: BATCH_ID || '', county: COUNTY || '',
      sub_county: SUB_COUNTY || '', chu: CHU || '', level: level,
    });
    dl.href = '/download/hiht-breakdown/?' + params.toString();
  }

  const params = new URLSearchParams({
    batch: BATCH_ID || '', county: COUNTY || '',
    sub_county: SUB_COUNTY || '', chu: CHU || '', level: level,
  });
  fetch('/api/hiht-breakdown/?' + params.toString())
    .then(r => r.json())
    .then(data => renderHihtBreakdown(c, data.results, level))
    .catch(() => { c.innerHTML = '<div class="table-empty" style="color:var(--red)">Error loading HIHT breakdown.</div>'; });
}

// Chart.js instances for the HIHT tab — kept around so a re-render (level
// switch, filter change) destroys the old chart before drawing a new one,
// rather than stacking canvases on top of each other.
let hihtBreakdownChart = null;
let hihtTrendChart = null;
const HIHT_TREND_COLORS = ['#0d6efd','#20c997','#fd7e14','#e83e8c','#6f42c1','#198754','#dc3545','#0dcaf0','#6c757d','#ffc107','#343a40','#adb5bd'];

function renderHihtBreakdown(c, rows, level) {
  if (!rows || rows.length === 0) {
    c.innerHTML = '<div class="table-empty">No data for this selection.</div>';
    if (hihtBreakdownChart) { hihtBreakdownChart.destroy(); hihtBreakdownChart = null; }
    return;
  }
  const geoLabel = { county: 'County', sub_county: 'Sub-County', chu: 'Community Health Unit', chp: 'CHP' }[level] || 'Geography';
  const geoField = { county: 'county', sub_county: 'sub_county', chu: 'community_health_unit', chp: 'chw_name' }[level] || 'county';

  renderHihtBreakdownChart(rows, geoLabel, geoField);

  let h = `<table class="data-table"><thead><tr>
    <th>#</th><th>${geoLabel}</th>
    <th class="num">Non-FP HIHTs/CHW</th><th class="num">FP HIHTs/CHW</th>
    <th class="num">Total HIHTs/CHW</th><th class="num">Total HIHTs</th><th class="num">Active CHWs</th>
  </tr></thead><tbody>`;
  rows.forEach((r, i) => {
    const rate = r.total_hihts_per_chw;
    const cls = rate == null ? '' : rate >= 8 ? 'good' : rate >= 4 ? 'warn' : 'bad';
    h += `<tr><td class="zero">${i+1}</td><td><strong>${esc(r[geoField])}</strong></td>
      <td class="num">${r.non_fp_hihts_per_chw ?? '—'}</td>
      <td class="num">${r.fp_hihts_per_chw ?? '—'}</td>
      <td class="num ${cls}">${rate ?? '—'}</td>
      <td class="num">${r.total_hihts}</td>
      <td class="num">${r.active_all}</td></tr>`;
  });
  h += `</tbody></table><div style="padding:10px 14px;font-size:12px;color:var(--text-muted)">${rows.length} ${geoLabel.toLowerCase()}(s), ranked by Total HIHTs/CHW</div>`;
  c.innerHTML = h;
}

// Grouped bar chart of Non-FP / FP / Total HIHTs per CHW, so it's easy to
// see at a glance which geographies are pulling the number up or down —
// the table underneath still has every row and the CSV has the full detail.
function renderHihtBreakdownChart(rows, geoLabel, geoField) {
  const canvas = document.getElementById('hiht-breakdown-chart');
  if (!canvas || typeof Chart === 'undefined') return;

  const TOP_N = 20;
  const top = rows.slice(0, TOP_N);
  const labels = top.map(r => r[geoField]);

  if (hihtBreakdownChart) hihtBreakdownChart.destroy();
  hihtBreakdownChart = new Chart(canvas.getContext('2d'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        // Same palette as the trend line chart below, so the two charts feel
        // like one consistent set rather than two different color schemes.
        { label: 'Non-FP HIHTs/CHW', data: top.map(r => r.non_fp_hihts_per_chw ?? 0), backgroundColor: HIHT_TREND_COLORS[0] },
        { label: 'FP HIHTs/CHW',     data: top.map(r => r.fp_hihts_per_chw ?? 0),     backgroundColor: HIHT_TREND_COLORS[2] },
        { label: 'Total HIHTs/CHW',  data: top.map(r => r.total_hihts_per_chw ?? 0),  backgroundColor: HIHT_TREND_COLORS[4] },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: rows.length > TOP_N
            ? `Top ${TOP_N} of ${rows.length} ${geoLabel.toLowerCase()}(s), by Total HIHTs/CHW`
            : `${geoLabel} comparison — HIHTs per CHW`,
        },
        legend: { position: 'bottom' },
      },
      scales: {
        x: { ticks: { autoSkip: false, maxRotation: 60, minRotation: 0, font: { size: 10 } } },
        y: { beginAtZero: true, title: { display: true, text: 'HIHTs per CHW' } },
      },
    },
  });
}

function loadHihtTrend(level) {
  const c = document.getElementById('hiht-trend-container');
  if (!c) return;
  c.innerHTML = '<div class="table-loading">Loading…</div>';

  const params = new URLSearchParams({ level: level, county: COUNTY || '', sub_county: SUB_COUNTY || '' });
  fetch('/api/hiht-trend/?' + params.toString())
    .then(r => r.json())
    .then(data => renderHihtTrend(c, data))
    .catch(() => { c.innerHTML = '<div class="table-empty" style="color:var(--red)">Error loading HIHT trend.</div>'; });
}

function renderHihtTrend(c, data) {
  if (!data.periods || data.periods.length === 0 || !data.series || data.series.length === 0) {
    c.innerHTML = '<div class="table-empty">Not enough monthly reports uploaded yet to show a trend.</div>';
    if (hihtTrendChart) { hihtTrendChart.destroy(); hihtTrendChart = null; }
    return;
  }

  renderHihtTrendChart(data);

  // Colour scale for the heatmap cells, relative to the overall min/max seen.
  let allVals = [];
  data.series.forEach(s => s.values.forEach(v => { if (v != null) allVals.push(v); }));
  const min = Math.min(...allVals), max = Math.max(...allVals);
  function cellColour(v) {
    if (v == null) return '#f0f0f0';
    const pct = max > min ? (v - min) / (max - min) : 0.5;
    // red (low) -> yellow -> green (high)
    const hue = 0 + pct * 120;
    return `hsl(${hue}, 65%, 88%)`;
  }

  let h = `<div class="table-scroll"><table class="data-table"><thead><tr><th>Geography</th>`;
  data.periods.forEach(p => { h += `<th class="num">${esc(p)}</th>`; });
  h += `</tr></thead><tbody>`;
  data.series.forEach(s => {
    h += `<tr><td><strong>${esc(s.label)}</strong></td>`;
    s.values.forEach(v => {
      h += `<td class="num" style="background:${cellColour(v)}">${v ?? '—'}</td>`;
    });
    h += `</tr>`;
  });
  h += `</tbody></table></div>
    <div style="padding:8px 14px;font-size:12px;color:var(--text-muted)">Total HIHTs/CHW per period. Greener = higher, redder = lower, relative to what's shown here.</div>`;
  c.innerHTML = h;
}

// Line chart of Total HIHTs/CHW over the last monthly reports, so a rising
// or falling trend per geography is visible at a glance. The heatmap table
// above still has every geography and every period in full.
function renderHihtTrendChart(data) {
  const canvas = document.getElementById('hiht-trend-chart');
  if (!canvas || typeof Chart === 'undefined') return;

  const MAX_SERIES = 12;
  let series = data.series;
  let capped = false;
  if (series.length > MAX_SERIES) {
    capped = true;
    series = [...series].sort((a, b) => {
      const lastVal = (vals) => { for (let i = vals.length - 1; i >= 0; i--) { if (vals[i] != null) return vals[i]; } return -Infinity; };
      return lastVal(b.values) - lastVal(a.values);
    }).slice(0, MAX_SERIES);
  }

  const datasets = series.map((s, i) => ({
    label: s.label,
    data: s.values,
    borderColor: HIHT_TREND_COLORS[i % HIHT_TREND_COLORS.length],
    backgroundColor: HIHT_TREND_COLORS[i % HIHT_TREND_COLORS.length],
    spanGaps: true,
    tension: 0.25,
  }));

  if (hihtTrendChart) hihtTrendChart.destroy();
  hihtTrendChart = new Chart(canvas.getContext('2d'), {
    type: 'line',
    data: { labels: data.periods, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: capped
            ? `Top ${MAX_SERIES} of ${data.series.length}, by most recent Total HIHTs/CHW`
            : 'Total HIHTs/CHW trend',
        },
        legend: { position: 'bottom' },
      },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: 'Total HIHTs/CHW' } },
      },
    },
  });
}