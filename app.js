// Trail Race Planner -- three tabs in workflow order: マイレース (past races that
// build the personal pace model) / 予測 (predict) / 振り返り (saved prediction
// vs actual GPX).

const svgNS = 'http://www.w3.org/2000/svg';
function el(tag, attrs) {
  const e = document.createElementNS(svgNS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  return e;
}
function hel(tag, attrs, html) {
  const e = document.createElement(tag);
  for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
  if (html != null) e.innerHTML = html;
  return e;
}
// CP/race names come from user input or arbitrary GPX waypoint names and are
// interpolated into innerHTML -- escape them.
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}
function hmsShort(totalSeconds) {
  const t = Math.round(Math.abs(totalSeconds));
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = t % 60;
  return h + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
}
function diffText(diffS) {
  if (diffS == null) return { text: '&mdash;', cls: '' };
  const mins = Math.round(diffS / 60);
  const cls = mins > 0 ? 'diff-slow' : mins < 0 ? 'diff-fast' : '';
  return { text: t('diff.min', { v: `${mins > 0 ? '+' : ''}${mins}` }), cls };
}

async function api(path, options) {
  const resp = await pyFetch(path, options);
  if (!resp.ok) {
    let detail = resp.statusText;
    try { detail = (await resp.json()).detail || detail; } catch (e) {}
    throw new Error(serverMsg(detail));
  }
  return resp.json();
}

function showMsg(containerId, text, cls) {
  const c = document.getElementById(containerId);
  c.innerHTML = '';
  if (!text) return;
  c.appendChild(hel('div', { class: 'msg ' + cls }, text));
}

const state = {
  uploadId: null,
  summary: null,
  cps: [],
  weatherReady: false,
  weatherDate: null,
  lastPlanResult: null,
  lastPlanPayload: null,
  savedRaceId: null, // auto-saved history entry for the current upload
  filename: null,
  // Last results kept so a language switch can redraw them without refetching.
  weatherView: null, // { ok: true, mode, avg } | { ok: false, error }
  saveView: null,    // { ok: true } | { ok: false, error }
  reviewEntry: null,
};

// ---------- tabs ----------
function openTab(tabId) {
  document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('hidden', p.id !== tabId));
  document.querySelectorAll('.tab-btn').forEach((b) => b.classList.toggle('active', b.dataset.tab === tabId));
  if (tabId === 'myRacesTab') loadMyRaces();
  if (tabId === 'reviewTab') {
    document.getElementById('reviewDetailCard').classList.add('hidden');
    document.getElementById('reviewListCard').classList.remove('hidden');
    loadReviewList();
  }
  window.scrollTo({ top: 0 });
}

// ============================================================
// 予測
// ============================================================
async function handleFile(file) {
  showMsg('uploadMsg', t('course.loading'), 'info');
  const form = new FormData();
  form.append('file', file);
  try {
    const result = await api('/api/gpx/upload', { method: 'POST', body: form });
    state.uploadId = result.upload_id;
    state.summary = result.summary;
    state.cps = result.cps;
    state.lastPlanResult = null;
    state.savedRaceId = null;
    state.filename = result.filename;
    const hadWaypoints = ensureDefaultCps();
    showMsg('uploadMsg', '', '');
    renderDropzoneSub();
    document.getElementById('courseInfo').classList.remove('hidden');
    document.getElementById('raceSetupCard').classList.remove('hidden');
    const reportSection = document.getElementById('reportSection');
    reportSection.innerHTML = '';
    reportSection.classList.add('hidden');
    // Without waypoints the placeholder CPs need checking -- don't leave them
    // hidden inside the collapsed section.
    document.getElementById('cpAutoDetectWarning').classList.toggle('hidden', hadWaypoints);
    document.getElementById('editCheckpointsDetails').open = !hadWaypoints;
    renderCourseStats();
    renderCpTable();
    renderPreviewElevChart();
    state.weatherReady = false;
    state.weatherDate = null;
    fetchWeather();
  } catch (e) {
    showMsg('uploadMsg', t('common.error', { v: esc(e.message) }), 'error');
  }
}

function renderDropzoneSub() {
  const sub = document.getElementById('dropzoneSub');
  sub.textContent = state.filename ? t('course.dzPicked', { name: state.filename }) : t('course.dzSub');
}

const DEFAULT_CP_COUNT = 5;

// A course GPX without named waypoints only yields START+FINISH; pre-fill
// evenly spaced placeholder CPs. Returns true if the GPX had real waypoints.
function ensureDefaultCps() {
  if (state.cps.length > 2) return true;
  const totalKm = state.summary.total_distance_km;
  const start = state.cps[0];
  const finish = state.cps[state.cps.length - 1];
  const middle = [];
  for (let i = 1; i <= DEFAULT_CP_COUNT; i++) {
    const dist = Math.round((totalKm * i / (DEFAULT_CP_COUNT + 1)) * 10) / 10;
    middle.push({ name: `CP${i}`, dist_km: dist });
  }
  state.cps = [start, ...middle, finish];
  return false;
}

function renderCourseStats() {
  const s = state.summary;
  document.getElementById('courseStats').innerHTML = `
    <div class="stat-chip">${t('stat.distance')} <b>${s.total_distance_km} km</b></div>
    <div class="stat-chip">D+ <b>${s.total_gain_m} m</b></div>
    <div class="stat-chip">D&minus; <b>${s.total_loss_m} m</b></div>
    <div class="stat-chip">CP <b>${Math.max(0, state.cps.length - 2)}</b></div>
  `;
}

function renderCpTable() {
  const tbody = document.getElementById('cpTableBody');
  tbody.innerHTML = '';
  state.cps.forEach((cp, i) => {
    const isEndpoint = i === 0 || i === state.cps.length - 1;
    const tr = document.createElement('tr');
    if (isEndpoint) tr.className = 'row-endpoint';
    const badge = document.createElement('td');
    badge.innerHTML = `<span class="point-badge">${i === 0 ? 'START' : (i === state.cps.length - 1 ? 'FINISH' : 'CP' + i)}</span>`;
    tr.appendChild(badge);

    const nameTd = document.createElement('td');
    const nameInput = hel('input', { class: 'cp-name', value: cp.name });
    nameInput.addEventListener('input', () => { state.cps[i].name = nameInput.value; });
    nameTd.appendChild(nameInput);
    tr.appendChild(nameTd);

    const distTd = document.createElement('td');
    distTd.className = 'num';
    const distInput = hel('input', { class: 'cp-dist', type: 'number', step: '0.1', value: cp.dist_km });
    // Rebuilding the table on every keystroke would steal focus mid-number;
    // re-sort only on blur (change).
    distInput.addEventListener('input', () => {
      state.cps[i].dist_km = parseFloat(distInput.value) || 0;
      renderPreviewElevChart();
    });
    distInput.addEventListener('change', () => {
      state.cps.sort((a, b) => a.dist_km - b.dist_km);
      renderCpTable();
      renderPreviewElevChart();
    });
    distTd.appendChild(distInput);
    // Cutoff sits under the distance in the same cell -- a column of its own
    // squeezed the CP name to a couple of characters on a phone.
    // START has no cutoff; FINISH's is the race time limit.
    if (i > 0) {
      const cutoffInput = hel('input', {
        class: 'cp-cutoff', type: 'text', inputmode: 'numeric',
        placeholder: t('setup.cpCutoffPlaceholder'), value: cp.cutoff || '', 'aria-label': t('setup.cpCutoff'),
      });
      cutoffInput.addEventListener('input', () => { state.cps[i].cutoff = cutoffInput.value.trim(); });
      distTd.appendChild(hel('div', { class: 'cp-cutoff-wrap' })).appendChild(cutoffInput);
    }
    tr.appendChild(distTd);

    const delTd = document.createElement('td');
    if (!isEndpoint) {
      const delBtn = hel('button', { class: 'btn danger small', type: 'button' }, t('common.delete'));
      delBtn.addEventListener('click', () => {
        state.cps.splice(i, 1);
        renderCpTable();
        renderPreviewElevChart();
      });
      delTd.appendChild(delBtn);
    }
    tr.appendChild(delTd);
    tbody.appendChild(tr);
  });
  renderCourseStats();
}

function addCpRow() {
  const lastIdx = state.cps.length - 1;
  const prevDist = state.cps[lastIdx - 1] ? state.cps[lastIdx - 1].dist_km : 0;
  const finishDist = state.cps[lastIdx].dist_km;
  const newDist = Math.round(((prevDist + finishDist) / 2) * 10) / 10;
  state.cps.splice(lastIdx, 0, { name: `CP${lastIdx}`, dist_km: newDist });
  renderCpTable();
  renderPreviewElevChart();
}

function renderPreviewElevChart() {
  const svg = document.getElementById('previewElevSvg');
  svg.innerHTML = '';
  const profile = state.summary.elevation_profile;
  const W = 1200, H = 110, PAD_L = 10, PAD_R = 10, PAD_T = 10, PAD_B = 8;
  const plotW = W - PAD_L - PAD_R, plotH = H - PAD_T - PAD_B;
  const maxKm = profile[profile.length - 1][0];
  const elevs = profile.map((p) => p[1]);
  const eMin = Math.min(...elevs), eMax = Math.max(...elevs);
  const pad = (eMax - eMin) * 0.1 || 10;
  const lo = eMin - pad, hi = eMax + pad;
  const xOf = (km) => PAD_L + (km / maxKm) * plotW;
  const yOf = (m) => PAD_T + (1 - (m - lo) / (hi - lo)) * plotH;

  let area = 'M' + xOf(0).toFixed(1) + ' ' + (H - PAD_B).toFixed(1) + ' ';
  let line = '';
  profile.forEach((p, i) => {
    const x = xOf(p[0]), y = yOf(p[1]);
    area += 'L' + x.toFixed(1) + ' ' + y.toFixed(1) + ' ';
    line += (i === 0 ? 'M' : 'L') + x.toFixed(1) + ' ' + y.toFixed(1) + ' ';
  });
  area += 'L' + xOf(maxKm).toFixed(1) + ' ' + (H - PAD_B).toFixed(1) + ' Z';
  svg.appendChild(el('path', { d: area, class: 'elev-fill' }));
  svg.appendChild(el('path', { d: line, class: 'elev-line' }));

  state.cps.forEach((cp) => {
    const x = xOf(Math.min(cp.dist_km, maxKm));
    svg.appendChild(el('line', { x1: x, y1: PAD_T, x2: x, y2: H - PAD_B, class: 'elev-dropline' }));
  });
}

// ---------- weather (fetched automatically for the chosen race date) ----------
async function fetchWeather() {
  if (!state.uploadId) return;
  const raceStart = document.getElementById('raceStart').value;
  if (!raceStart) { showMsg('weatherMsg', t('weather.needStart'), 'error'); return; }
  const raceDate = raceStart.split('T')[0];
  state.weatherReady = false;
  state.weatherDate = raceDate;
  state.weatherView = null;
  updateRunButton();
  showMsg('weatherMsg', t('weather.fetching'), 'info');
  document.getElementById('manualWeatherGrid').classList.add('hidden');
  try {
    const result = await api('/api/weather', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ upload_id: state.uploadId, race_date: raceDate }),
    });
    if (state.weatherDate !== raceDate) return;  // date changed while fetching
    state.weatherReady = true;
    const temps = Object.values(result.diurnal_temp);
    const avgTemp = (temps.reduce((a, b) => a + b, 0) / temps.length).toFixed(1);
    state.weatherView = { ok: true, mode: result.mode, avg: avgTemp };
  } catch (e) {
    if (state.weatherDate !== raceDate) return;
    state.weatherView = { ok: false, error: e.message };
    document.getElementById('manualWeatherGrid').classList.remove('hidden');
  }
  renderWeatherMsg();
  updateRunButton();
}

function renderWeatherMsg() {
  const v = state.weatherView;
  if (!v) return;
  if (v.ok) {
    const src = t(v.mode === 'forecast' ? 'weather.forecast' : 'weather.normals');
    showMsg('weatherMsg', t('weather.ok', { src, avg: v.avg }), 'ok');
  } else {
    showMsg('weatherMsg', t('weather.fail', { e: esc(v.error) }), 'error');
  }
}

function onRaceStartChange() {
  const raceStart = document.getElementById('raceStart').value;
  if (state.uploadId && raceStart && raceStart.split('T')[0] !== state.weatherDate) fetchWeather();
}

function updateRunButton() {
  const manualTemp = document.getElementById('manualTemp').value;
  document.getElementById('runPlanBtn').disabled = !state.uploadId || (!state.weatherReady && manualTemp === '');
}

// ---------- plan ----------
async function runPlan() {
  if (!state.uploadId) return;
  const raceStart = document.getElementById('raceStart').value;
  if (!raceStart) { showMsg('planMsg', t('weather.needStart'), 'error'); return; }
  const manualTemp = document.getElementById('manualTemp').value;
  const manualHum = document.getElementById('manualHum').value;

  const payload = {
    upload_id: state.uploadId,
    race_start_local: raceStart,
    cps: state.cps.map((c) => (c.cutoff ? { name: c.name, dist_km: c.dist_km, cutoff: c.cutoff } : { name: c.name, dist_km: c.dist_km })),
    default_cp_dwell_min: parseFloat(document.getElementById('dwellMin').value) || 0,
    bodyweight_kg: parseFloat(document.getElementById('bodyweight').value) || 70,
  };
  if (!state.weatherReady && manualTemp !== '') {
    payload.manual_avg_temp_c = parseFloat(manualTemp);
    payload.manual_avg_humidity_pct = manualHum !== '' ? parseFloat(manualHum) : 60;
  }
  const targetHours = parseFloat(document.getElementById('targetHours').value);
  const targetMinutes = parseFloat(document.getElementById('targetMinutes').value);
  if (!Number.isNaN(targetHours) || !Number.isNaN(targetMinutes)) {
    payload.target_elapsed_s = (targetHours || 0) * 3600 + (targetMinutes || 0) * 60;
  }

  const btn = document.getElementById('runPlanBtn');
  btn.disabled = true;
  btn.textContent = t('setup.running');
  showMsg('planMsg', '', '');
  try {
    const result = await api('/api/plan', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    state.lastPlanResult = result;
    state.lastPlanPayload = payload;
    state.saveView = null;
    renderReport(result);
    autoSavePrediction();
  } catch (e) {
    showMsg('planMsg', t('common.error', { v: esc(e.message) }), 'error');
  } finally {
    btn.textContent = t('setup.run');
    updateRunButton();
  }
}

// GET navigation rather than fetch+blob: the Android WebView hands downloads
// to DownloadManager, which re-fetches the URL itself with a plain GET.
function downloadPlanPdf() {
  const payload = state.lastPlanPayload;
  if (!payload) return;
  const params = new URLSearchParams({
    upload_id: payload.upload_id,
    race_start_local: payload.race_start_local,
    cps: JSON.stringify(payload.cps),
    default_cp_dwell_min: String(payload.default_cp_dwell_min),
    bodyweight_kg: String(payload.bodyweight_kg),
  });
  if (payload.manual_avg_temp_c != null) params.set('manual_avg_temp_c', String(payload.manual_avg_temp_c));
  if (payload.manual_avg_humidity_pct != null) params.set('manual_avg_humidity_pct', String(payload.manual_avg_humidity_pct));
  if (payload.target_elapsed_s != null) params.set('target_elapsed_s', String(payload.target_elapsed_s));
  params.set('lang', LANG);
  pyDownload('/api/plan/pdf?' + params.toString());
}

// Every prediction is saved automatically; re-running on the same upload
// overwrites the entry saved earlier (replace_race_id) instead of adding one.
async function autoSavePrediction() {
  const result = state.lastPlanResult;
  if (!result) return;
  const name = result.filename.replace(/\.gpx$/i, '') || 'Race';
  try {
    const saved = await api('/api/race-review/save-prediction', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        upload_id: state.uploadId, race_name: name, plan_result: result,
        replace_race_id: state.savedRaceId,
      }),
    });
    state.savedRaceId = saved.race_id;
    state.saveView = { ok: true };
  } catch (e) {
    state.saveView = { ok: false, error: e.message };
  }
  renderSaveMsg();
}

function renderSaveMsg() {
  const v = state.saveView;
  if (!v || !document.getElementById('savePredictionMsg')) return;
  if (v.ok) showMsg('savePredictionMsg', t('report.saved'), 'ok');
  else showMsg('savePredictionMsg', t('report.saveFail', { e: esc(v.error) }), 'error');
}

// ---------- report ----------
function gradientLabel(category) {
  const key = 'grad.' + category;
  const label = t(key);
  return label === key ? category : label;
}

// Cutoff fields come from analysis/cutoff.py::apply_cutoffs(). day_offset is
// days after the race start date (shown as 翌日 / 2日後 ...).
function cutoffClock(clock, dayOffset) {
  return dayOffset > 0 ? t('cutoff.dayClock', { d: dayOffset === 1 ? t('cutoff.nextDay') : t('cutoff.daysLater', { n: dayOffset }), clock }) : clock;
}
function marginText(min) {
  return t('diff.min', { v: `${min > 0 ? '+' : ''}${min}` });
}

function buildCutoffCellHtml(r) {
  if (!r.cutoff_clock) return '<div class="cell-main">&mdash;</div>';
  const sub = r.cutoff_trap
    ? `<div class="cell-sub">${t('cutoff.official', { c: cutoffClock(r.cutoff_clock, r.cutoff_day_offset) })}</div>
       <div class="cell-sub cutoff-trap-note">${t('cutoff.effective', { c: cutoffClock(r.effective_cutoff_clock, r.effective_cutoff_day_offset) })}</div>`
    : `<div class="cell-sub">${t('cutoff.official', { c: cutoffClock(r.cutoff_clock, r.cutoff_day_offset) })}</div>`;
  return `<div class="cell-main cutoff-${r.cutoff_status}">${marginText(r.effective_margin_min)}</div>${sub}`;
}

function buildCpScheduleTableHtml(cpSchedule) {
  const hasCutoff = cpSchedule.some((r) => r.cutoff_clock);
  let rows = '';
  cpSchedule.forEach((r, i) => {
    const isEnd = i === 0 || i === cpSchedule.length - 1;
    const prev = i > 0 ? cpSchedule[i - 1] : null;
    const segmentTime = prev ? hmsShort(r.elapsed_s - (prev.elapsed_s + prev.dwell_min * 60)) : '&mdash;';
    rows += `<tr class="${isEnd ? 'row-endpoint' : ''}">
      <td class="col-point">
        <span class="point-badge">${esc(r.name)}</span>
        <div class="cell-sub">${r.dist_km}km</div>
      </td>
      <td class="num">
        <div class="cell-main">${i === 0 ? '&mdash;' : `+${r.gain_m}`}</div>
        <div class="cell-sub">${i === 0 ? '' : `&minus;${r.loss_m}m`}</div>
      </td>
      <td class="num"><div class="cell-main">${segmentTime}</div></td>
      <td class="num pred-col">
        <div class="cell-main">${r.arrival_clock}</div>
        <div class="cell-sub">${t('cpTable.cum', { v: hmsShort(r.elapsed_s) })}</div>
      </td>
      ${hasCutoff ? `<td class="num cutoff-col">${i === 0 ? '' : buildCutoffCellHtml(r)}</td>` : ''}
      <td class="num weather-col">
        <div class="cell-main">${r.temp_c != null ? `${r.temp_c}&deg;C` : '&mdash;'}</div>
        <div class="cell-sub">${r.feels_like_c != null ? t('cpTable.feels', { v: r.feels_like_c }) : ''}</div>
      </td>
    </tr>`;
  });
  return `
    <table class="compact-table">
      <thead><tr>
        <th>Point</th><th class="num">D+/D&minus;</th><th class="num">${t('cpTable.segment')}</th>
        <th class="num pred-col">${t('cpTable.arrival')}</th>
        ${hasCutoff ? `<th class="num cutoff-col">${t('cpTable.cutoff')}</th>` : ''}
        <th class="num weather-col">${t('cpTable.temp')}</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

// result.target_plan comes from analysis/simulate.py::compute_target_plan().
function buildTargetPlanCard(targetPlan) {
  const card = hel('div', { class: 'card' });
  if (!targetPlan.adjustment_needed) {
    card.innerHTML = `
      <h2 class="section-title">${t('target.title')}</h2>
      <p class="section-note">${t('target.notNeeded', { t: hmsShort(targetPlan.target_elapsed_s) })}</p>
    `;
    return card;
  }
  const banner = targetPlan.feasible
    ? `<p class="section-note">${t('target.feasible', { t: hmsShort(targetPlan.target_elapsed_s) })}</p>`
    : `<p class="section-note warn-note">${t('target.infeasible', { t: hmsShort(targetPlan.target_elapsed_s), best: hmsShort(targetPlan.achieved_elapsed_s) })}</p>`;
  let breakdownRows = '';
  targetPlan.category_breakdown.forEach((c) => {
    breakdownRows += `<tr>
      <td class="col-point">${esc(gradientLabel(c.category))}</td>
      <td class="num">${hmsShort(c.time_s)}</td>
      <td class="num">${c.reduction_pct}%${c.capped ? ` <span class="cell-sub">${t('target.cap')}</span>` : ''}</td>
    </tr>`;
  });
  card.innerHTML = `
    <h2 class="section-title">${t('target.title')}<span class="pro-badge">PRO</span></h2>
    ${banner}
    <table class="compact-table">
      <thead><tr><th>${t('target.terrain')}</th><th class="num">${t('target.predTime')}</th><th class="num">${t('target.paceUp')}</th></tr></thead>
      <tbody>${breakdownRows}</tbody>
    </table>
    <p class="card-footnote">${t('target.footnote')}</p>
    <h3 class="subsection-title">${t('target.schedule')}</h3>
    ${buildCpScheduleTableHtml(targetPlan.plan.cp_schedule)}
  `;
  return card;
}

function renderReport(result, scroll = true) {
  const section = document.getElementById('reportSection');
  section.classList.remove('hidden');
  section.innerHTML = '';

  const tempSign = result.temp_correction_pct >= 0 ? '+' : '';
  const summaryCard = hel('div', { class: 'card result-card' });
  summaryCard.innerHTML = `
    <div class="result-label">${t('report.finishLabel')}</div>
    <div class="result-time">${hmsShort(result.predicted_elapsed_s)}</div>
    <div class="result-sub">${t('report.finishSub', { finish: esc(result.predicted_finish_clock), start: esc(result.race_start_local.replace('T', ' ')) })}</div>
    <div class="stats-row">
      <div class="stat-chip">${t('stat.distance')} <b>${result.total_distance_km} km</b></div>
      <div class="stat-chip">D+ <b>${result.total_gain_m} m</b></div>
      <div class="stat-chip">${t('report.highest')} <b>${result.highest_point.elevation_m} m</b></div>
    </div>
    <p class="section-note" style="margin:12px 0 0;">
      ${t('report.heat', { v: tempSign + result.temp_correction_pct, base: hmsShort(result.baseline_elapsed_s) })}<br>
      ${result.was_custom_pace_model ? t('report.customModel') : t('report.standardModel')}
    </p>
  `;
  section.appendChild(summaryCard);
  const toMyRaces = document.getElementById('toMyRacesLink');
  if (toMyRaces) toMyRaces.addEventListener('click', (e) => { e.preventDefault(); openTab('myRacesTab'); });

  if (result.cutoff_summary) section.appendChild(buildCutoffCard(result));

  const cpCard = hel('div', { class: 'card' });
  cpCard.innerHTML = `<h2 class="section-title">${t('report.cpTitle')}</h2>${buildCpScheduleTableHtml(result.cp_schedule)}`;
  section.appendChild(cpCard);

  if (result.target_plan) section.appendChild(buildTargetPlanCard(result.target_plan));

  const chartCard = hel('div', { class: 'card' });
  chartCard.innerHTML = `
    <h2 class="section-title">${t('report.chartTitle')}</h2>
    <div class="chart-holder" id="reportChartHolder">
      <svg viewBox="0 0 1200 450" id="reportElevChartSvg"></svg>
      <div class="tooltip" id="reportTooltip"></div>
    </div>
  `;
  section.appendChild(chartCard);

  section.appendChild(buildNutritionCard(result));
  section.appendChild(buildMindsetCard(result));

  const actionsCard = hel('div', { class: 'card' });
  actionsCard.innerHTML = `
    <div class="actions-row">
      <button class="btn secondary" id="downloadPdfBtn" type="button">${t('report.pdf')}<span class="pro-badge">PRO</span></button>
    </div>
    <div id="savePredictionMsg"></div>
  `;
  section.appendChild(actionsCard);
  document.getElementById('downloadPdfBtn').addEventListener('click', downloadPlanPdf);
  renderSaveMsg();

  renderReportChart(result);
  if (scroll) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// result.cutoff_summary / cp_schedule cutoff fields: analysis/cutoff.py.
function buildCutoffCard(result) {
  const s = result.cutoff_summary;
  const tight = Math.round(s.tight_margin_min);
  let banner;
  if (s.missed.length) {
    banner = `<p class="section-note warn-note">${t('cutoff.over', { n: s.missed.length, list: s.missed.map(esc).join(t('my.listSep')) })}</p>`;
  } else if (s.n_tight > 0) {
    banner = `<p class="section-note warn-note">${t('cutoff.tight', { n: s.n_tight, m: tight })}</p>`;
  } else {
    banner = `<p class="section-note">${t('cutoff.allOk', { m: tight })}</p>`;
  }
  const tightest = `<div class="stats-row">
    <div class="stat-chip">${t('cutoff.tightest')} <b>${esc(s.tightest.name)} ${marginText(s.tightest.margin_min)}</b></div>
    <div class="stat-chip">${t('cutoff.count')} <b>${t('nut.cpAidN', { v: s.n_cutoffs })}</b></div>
  </div>`;
  let traps = '';
  // One card per cutoff that tightens the ones before it (analysis/cutoff.py groups them).
  s.traps.forEach((g) => {
    const names = g.cps.map((c) => esc(c.name)).join(t('my.listSep'));
    const lines = g.cps.map((c) => t('cutoff.trapLine', {
      name: esc(c.name), c: cutoffClock(c.cutoff_clock, c.cutoff_day_offset),
      e: cutoffClock(c.effective_cutoff_clock, c.effective_cutoff_day_offset), m: c.minutes_earlier,
    })).join('<br>');
    traps += `<div class="caution-card">
      <div class="caution-label">${t('cutoff.trapLabel')}</div>
      <div class="caution-title">${t('cutoff.trapTitle', { by: esc(g.by), c: cutoffClock(g.by_cutoff_clock, g.by_cutoff_day_offset) })}</div>
      <div class="caution-body">${t('cutoff.trapBody', { list: names, by: esc(g.by) })}<br>${lines}</div>
    </div>`;
  });
  const card = hel('div', { class: 'card' });
  card.innerHTML = `
    <h2 class="section-title">${t('cutoff.title')}</h2>
    ${banner}
    ${tightest}
    ${traps ? `<div class="caution-grid" style="margin-top:14px;">${traps}</div>` : ''}
    <p class="card-footnote">${t('cutoff.footnote')}</p>
  `;
  return card;
}

function nutritionNote(n) {
  if (n.note_code) return t('nut.note.' + n.note_code, { cp: esc(n.from) });
  // older servers without note_code: show the Japanese note as-is
  return n.note && n.note !== '&mdash;' && n.note !== '—' ? esc(n.note) : '';
}

function buildNutritionCard(result) {
  const s = result.nutrition_summary;
  let rows = '';
  result.nutrition_plan.forEach((n) => {
    rows += `<tr>
      <td class="col-point">
        <div class="cell-main">${esc(n.from)}&rarr;${esc(n.to)}</div>
        <div class="cell-sub">${t('nut.segSub', { min: Math.round(n.seg_h * 60), t: n.avg_feels_like_c })}</div>
      </td>
      <td class="num pred-col"><div class="cell-main">${n.water_ml.toLocaleString()}mL</div></td>
      <td class="num">
        <div class="cell-main">${n.kcal_target}kcal</div>
        <div class="cell-sub">${t('nut.kcalSub', { aid: n.cp_aid_kcal, net: n.net_kcal })}</div>
      </td>
      <td class="num pred-col gel-count">${t('nut.gelsN', { v: n.gels })}</td>
    </tr>`;
    const note = nutritionNote(n);
    if (note) {
      rows += `<tr class="note-row"><td colspan="4" class="row-note">${note}</td></tr>`;
    }
  });
  const card = hel('div', { class: 'card' });
  card.innerHTML = `
    <h2 class="section-title">${t('nut.title')}</h2>
    <div class="stats-row" style="margin-bottom:14px;">
      <div class="stat-chip accent">${t('nut.water')} <b>${s.total_water_l} L</b></div>
      <div class="stat-chip accent">${t('nut.gels')} <b>${t('nut.gelsN', { v: s.total_gels })}</b></div>
      <div class="stat-chip">${t('nut.cpAid')} <b>${t('nut.cpAidN', { v: s.n_aid_stops })}</b></div>
    </div>
    <table class="compact-table">
      <thead><tr><th>${t('nut.segment')}</th><th class="num pred-col">${t('nut.water')}</th><th class="num">${t('nut.kcal')}</th><th class="num pred-col">${t('nut.gels')}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <details class="plain-details">
      <summary class="details-summary">${t('nut.method')}</summary>
      <p class="card-footnote">
        ${t('nut.footnote', { sweat: s.estimated_sweat_l, bw: s.bodyweight_kg, kcal: s.estimated_kcal_expenditure.toLocaleString() })}
      </p>
    </details>
  `;
  return card;
}

function buildMindsetCard(result) {
  const m = result.mindset;
  let items = '';
  if (m.steepest_segment) {
    const s = m.steepest_segment;
    const gradePct = s.km > 0 ? Math.round(s.gain_m / (s.km * 1000) * 100) : 0;
    items += `<div class="caution-card">
      <div class="caution-label">${t('mind.steepLabel')}</div>
      <div class="caution-title">${t('mind.steepTitle', { from: esc(s.from), to: esc(s.to), grade: gradePct })}</div>
      <div class="caution-body">${t('mind.steepBody', { km: s.km, gain: s.gain_m })}</div>
    </div>`;
  }
  if (m.longest_segment) {
    const s = m.longest_segment;
    items += `<div class="caution-card">
      <div class="caution-label">${t('mind.longLabel')}</div>
      <div class="caution-title">${t('mind.longTitle', { from: esc(s.from), to: esc(s.to), km: s.km, t: hmsShort(s.time_s) })}</div>
      <div class="caution-body">${t('mind.longBody')}</div>
    </div>`;
  }
  if (m.hottest_segment) {
    const s = m.hottest_segment;
    items += `<div class="caution-card">
      <div class="caution-label">${t('mind.hotLabel')}</div>
      <div class="caution-title">${t('mind.hotTitle', { from: esc(s.from), to: esc(s.to), t: s.feels_like_c })}</div>
      <div class="caution-body">${t('mind.hotBody')}</div>
    </div>`;
  }
  const card = hel('div', { class: 'card' });
  card.innerHTML = `
    <h2 class="section-title">${t('mind.title')}</h2>
    <div class="caution-grid">${items || `<p class="section-note">${t('mind.none')}</p>`}</div>
  `;
  return card;
}

function renderReportChart(result) {
  const svg = document.getElementById('reportElevChartSvg');
  const profile = result.elevation_profile_timed; // [cum_km, elevation_m, elapsed_s]
  const cps = result.cp_schedule;

  const W = 1200, H = 450, PAD_L = 50, PAD_R = 40, PAD_T = 40, PAD_B = 96;
  const plotW = W - PAD_L - PAD_R, plotH = H - PAD_T - PAD_B;
  const baselineY = H - PAD_B;
  const maxKm = profile[profile.length - 1][0];
  const xOf = (km) => PAD_L + (km / maxKm) * plotW;

  const elevs = profile.map((p) => p[1]);
  const eMin = Math.min(...elevs), eMax = Math.max(...elevs);
  const ePad = (eMax - eMin) * 0.15 || 10;
  const eLo = eMin - ePad, eHi = eMax + ePad;
  const eyOf = (m) => baselineY - (m - eLo) / (eHi - eLo) * plotH;

  const rawStep = (eHi - eLo) / 5;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
  let step = [1, 2, 2.5, 5, 10].find((s) => s * magnitude >= rawStep) * magnitude;
  if (!step) step = rawStep;
  for (let v = Math.ceil(eLo / step) * step; v <= eHi; v += step) {
    const y = eyOf(v);
    svg.appendChild(el('line', { x1: PAD_L, y1: y, x2: W - PAD_R, y2: y, class: 'gridline' }));
    const t = el('text', { x: PAD_L - 10, y: y + 4, class: 'axis-label', 'text-anchor': 'end' });
    t.textContent = Math.round(v) + 'm';
    svg.appendChild(t);
  }
  svg.appendChild(el('line', { x1: PAD_L, y1: baselineY, x2: W - PAD_R, y2: baselineY, class: 'baseline-axis' }));

  let area = 'M' + xOf(profile[0][0]).toFixed(1) + ' ' + baselineY.toFixed(1) + ' ';
  let line = '';
  profile.forEach((p, i) => {
    const x = xOf(p[0]), y = eyOf(p[1]);
    area += 'L' + x.toFixed(1) + ' ' + y.toFixed(1) + ' ';
    line += (i === 0 ? 'M' : 'L') + x.toFixed(1) + ' ' + y.toFixed(1) + ' ';
  });
  area += 'L' + xOf(profile[profile.length - 1][0]).toFixed(1) + ' ' + baselineY.toFixed(1) + ' Z';
  svg.appendChild(el('path', { d: area, class: 'elev-fill' }));
  svg.appendChild(el('path', { d: line, class: 'elev-line' }));

  const peakKm = result.highest_point.dist_km, peakM = result.highest_point.elevation_m;
  const peakX = xOf(peakKm), peakY = eyOf(peakM);
  svg.appendChild(el('circle', { cx: peakX, cy: peakY, r: 4, class: 'peak-dot' }));
  const peakLabel = el('text', { x: peakX, y: Math.max(14, peakY - 8), class: 'peak-label', 'text-anchor': 'middle' });
  peakLabel.textContent = `${peakM}m`;
  svg.appendChild(peakLabel);

  cps.forEach((cp) => {
    const x = xOf(cp.dist_km);
    const y = cp.elevation_m != null ? eyOf(cp.elevation_m) : baselineY;
    svg.appendChild(el('line', { x1: x, y1: Math.max(PAD_T, y - 6), x2: x, y2: baselineY, class: 'cp-dropline' }));
    svg.appendChild(el('circle', { cx: x, cy: y, r: 5.5, class: 'cp-dot' }));
    const name = el('text', { x, y: baselineY + 22, class: 'cp-name', 'text-anchor': 'middle' });
    name.textContent = cp.name;
    svg.appendChild(name);
    const dist = el('text', { x, y: baselineY + 37, class: 'cp-dist', 'text-anchor': 'middle' });
    dist.textContent = cp.dist_km.toFixed(1) + 'km';
    svg.appendChild(dist);
    const pred = el('text', { x, y: baselineY + 53, class: 'cp-pred', 'text-anchor': 'middle' });
    pred.textContent = cp.arrival_clock;
    svg.appendChild(pred);
  });

  const crosshair = el('line', { x1: 0, y1: PAD_T, x2: 0, y2: baselineY, class: 'crosshair' });
  svg.appendChild(crosshair);
  const hoverDot = el('circle', { r: 5, class: 'hover-dot', fill: 'var(--series-1)' });
  svg.appendChild(hoverDot);
  const tooltip = document.getElementById('reportTooltip');
  const holder = document.getElementById('reportChartHolder');

  function interp(arr, km, valueIdx) {
    if (km <= arr[0][0]) return arr[0][valueIdx];
    for (let i = 1; i < arr.length; i++) {
      if (km <= arr[i][0]) {
        const d0 = arr[i - 1][0], v0 = arr[i - 1][valueIdx];
        const d1 = arr[i][0], v1 = arr[i][valueIdx];
        if (d1 === d0) return v0;
        return v0 + (km - d0) / (d1 - d0) * (v1 - v0);
      }
    }
    return arr[arr.length - 1][valueIdx];
  }
  function handleMove(evt) {
    const rect = svg.getBoundingClientRect();
    const clientX = evt.touches ? evt.touches[0].clientX : evt.clientX;
    const px = (clientX - rect.left) / rect.width * W;
    const km = Math.max(0, Math.min(maxKm, (px - PAD_L) / plotW * maxKm));
    const elev = interp(profile, km, 1);
    const s = interp(profile, km, 2);
    const x = xOf(km), y = eyOf(elev);
    crosshair.setAttribute('x1', x); crosshair.setAttribute('x2', x); crosshair.style.opacity = 1;
    hoverDot.setAttribute('cx', x); hoverDot.setAttribute('cy', y); hoverDot.style.opacity = 1;
    tooltip.innerHTML = t('report.tooltip', { km: km.toFixed(1), e: Math.round(elev), t: hmsShort(s) });
    const holderRect = holder.getBoundingClientRect();
    tooltip.style.left = (x / W * holderRect.width) + 'px';
    tooltip.style.top = (y / H * holderRect.height) + 'px';
    tooltip.style.opacity = 1;
  }
  function handleLeave() {
    crosshair.style.opacity = 0; hoverDot.style.opacity = 0; tooltip.style.opacity = 0;
  }
  svg.addEventListener('mousemove', handleMove);
  svg.addEventListener('mouseleave', handleLeave);
  svg.addEventListener('touchmove', handleMove, { passive: true });
  svg.addEventListener('touchend', handleLeave);
}

// ============================================================
// マイレース
// ============================================================
async function loadMyRaces() {
  try {
    renderMyRaces(await api('/api/my-races'));
  } catch (e) {
    showMsg('myRacesMsg', t('common.error', { v: esc(e.message) }), 'error');
  }
}

function renderMyRaces(data) {
  const status = document.getElementById('modelStatus');
  if (data.is_custom_model) {
    const n = data.races.length || data.legacy_races.length;
    status.innerHTML = `<span class="status-dot on"></span>${t('my.statusCustom', { n })}`;
  } else {
    status.innerHTML = `<span class="status-dot"></span>${t('my.statusStandard')}`;
  }

  const list = document.getElementById('myRacesList');
  list.innerHTML = '';
  if (data.legacy_races.length) {
    list.appendChild(hel('p', { class: 'section-note warn-note' },
      t('my.legacy', { list: data.legacy_races.map(esc).join(t('my.listSep')) })));
  }
  if (!data.races.length) {
    if (!data.legacy_races.length) list.appendChild(hel('p', { class: 'section-note' }, t('my.empty')));
    return;
  }
  const table = hel('table', { class: 'compact-table list-table' });
  table.innerHTML = `<thead><tr><th>${t('my.race')}</th><th class="num">${t('my.distGain')}</th><th class="num">${t('my.temp')}</th><th></th></tr></thead>`;
  const tbody = document.createElement('tbody');
  data.races.forEach((r) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><div class="cell-main">${esc(r.name)}</div><div class="cell-sub">${esc(r.start_time_utc.slice(0, 10))}</div></td>
      <td class="num"><div class="cell-main">${r.distance_km}km</div><div class="cell-sub">+${r.gain_m}m</div></td>
      <td class="num">${r.avg_temp_c != null ? r.avg_temp_c + '&deg;C' : '&mdash;'}</td>
      <td class="num"></td>
    `;
    const delBtn = hel('button', { class: 'btn danger small', type: 'button' }, t('common.delete'));
    delBtn.addEventListener('click', () => deleteMyRace(r));
    tr.lastElementChild.appendChild(delBtn);
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  list.appendChild(table);
}

async function addMyRaces(files) {
  const btn = document.getElementById('addRaceBtn');
  btn.disabled = true;
  for (const file of files) {
    showMsg('myRacesMsg', t('my.adding', { name: esc(file.name) }), 'info');
    const form = new FormData();
    form.append('file', file);
    try {
      renderMyRaces(await api('/api/my-races', { method: 'POST', body: form }));
      showMsg('myRacesMsg', t('my.added', { name: esc(file.name) }), 'ok');
    } catch (e) {
      showMsg('myRacesMsg', `${esc(file.name)}: ${esc(e.message)}`, 'error');
    }
  }
  btn.disabled = false;
}

async function deleteMyRace(race) {
  if (!confirm(t('my.confirmDelete', { name: race.name }))) return;
  try {
    renderMyRaces(await api(`/api/my-races/${race.id}`, { method: 'DELETE' }));
    showMsg('myRacesMsg', t('my.deleted', { name: esc(race.name) }), 'ok');
  } catch (e) {
    showMsg('myRacesMsg', t('common.error', { v: esc(e.message) }), 'error');
  }
}

// ============================================================
// 振り返り
// ============================================================
let currentReviewId = null;

async function loadReviewList() {
  const list = document.getElementById('reviewList');
  try {
    const entries = await api('/api/race-review/history');
    list.innerHTML = '';
    if (!entries.length) {
      list.appendChild(hel('p', { class: 'section-note' }, t('review.empty')));
      return;
    }
    const table = hel('table', { class: 'compact-table list-table clickable' });
    table.innerHTML = `<thead><tr><th>${t('my.race')}</th><th class="num">${t('my.distGain')}</th><th>${t('review.state')}</th><th></th></tr></thead>`;
    const tbody = document.createElement('tbody');
    entries.slice().reverse().forEach((e) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><div class="cell-main">${esc(e.race_name)}</div><div class="cell-sub">${t('review.savedOn', { date: esc(e.saved_at_utc.slice(0, 10)) })}</div></td>
        <td class="num"><div class="cell-main">${e.distance_km}km</div><div class="cell-sub">+${Math.round(e.gain_m)}m</div></td>
        <td><span class="tag ${e.has_actual ? 'done' : ''}">${e.has_actual ? t('review.compared') : t('review.waiting')}</span></td>
        <td class="num"></td>
      `;
      tr.addEventListener('click', () => openReview(e.race_id));
      const delBtn = hel('button', { class: 'btn danger small', type: 'button' }, t('common.delete'));
      delBtn.addEventListener('click', (ev) => { ev.stopPropagation(); deleteReview(e); });
      tr.lastElementChild.appendChild(delBtn);
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    list.appendChild(table);
  } catch (e) {
    list.innerHTML = `<div class="msg error">${t('common.error', { v: esc(e.message) })}</div>`;
  }
}

async function deleteReview(entry) {
  if (!confirm(t('review.confirmDelete', { name: entry.race_name }))) return;
  try {
    await api(`/api/race-review/${entry.race_id}`, { method: 'DELETE' });
    loadReviewList();
  } catch (e) {
    showMsg('reviewList', t('common.error', { v: esc(e.message) }), 'error');
  }
}

async function openReview(raceId) {
  try {
    const entry = await api(`/api/race-review/${raceId}`);
    currentReviewId = raceId;
    renderReviewDetail(entry);
    document.getElementById('reviewListCard').classList.add('hidden');
    document.getElementById('reviewDetailCard').classList.remove('hidden');
    window.scrollTo({ top: 0 });
  } catch (e) {
    showMsg('reviewList', t('common.error', { v: esc(e.message) }), 'error');
  }
}

function closeReview() {
  state.reviewEntry = null;
  document.getElementById('reviewDetailCard').classList.add('hidden');
  document.getElementById('reviewListCard').classList.remove('hidden');
  loadReviewList();
}

async function uploadActual(file) {
  showMsg('actualUploadMsg', t('review.comparing'), 'info');
  const form = new FormData();
  form.append('file', file);
  try {
    renderReviewDetail(await api(`/api/race-review/${currentReviewId}/upload-actual`, { method: 'POST', body: form }));
  } catch (e) {
    showMsg('actualUploadMsg', t('common.error', { v: esc(e.message) }), 'error');
  }
}

function renderReviewDetail(entry) {
  state.reviewEntry = entry;
  const card = document.getElementById('reviewDetailCard');
  const snap = entry.prediction_snapshot;
  let html = `
    <button class="link-btn" id="backToReviewList" type="button">${t('review.back')}</button>
    <h2 class="section-title" style="margin-top:10px;">${esc(snap.race_name)}</h2>
    <p class="section-note">${t('review.summary', { km: snap.total_distance_km, gain: Math.round(snap.total_gain_m), start: esc(snap.race_start_local.replace('T', ' ')) })}</p>
  `;

  if (!entry.actual_summary) {
    html += `
      <p class="section-note">${t('review.instruction')}</p>
      <div class="dropzone" id="actualDropzone">
        <div class="dz-title">${t('review.dzTitle')}</div>
        <div>${t('review.dzSub')}</div>
        <input type="file" id="actualFileInput" accept=".gpx">
      </div>
      <div id="actualUploadMsg"></div>
    `;
    card.innerHTML = html;
    const dz = document.getElementById('actualDropzone');
    const input = document.getElementById('actualFileInput');
    dz.addEventListener('click', () => input.click());
    input.addEventListener('change', () => { if (input.files.length) uploadActual(input.files[0]); });
  } else {
    const actualTotal = entry.actual_summary.actual_total_elapsed_s;
    const goalSnap = entry.goal_prediction_snapshot;
    const finishDiff = diffText(actualTotal != null ? actualTotal - snap.predicted_elapsed_s : null);
    html += `
      <div class="stats-row">
        <div class="stat-chip">${t('review.predicted')} <b>${hmsShort(snap.predicted_elapsed_s)}</b></div>
        ${goalSnap ? `<div class="stat-chip">${t('review.goal')} <b>${hmsShort(goalSnap.predicted_elapsed_s)}</b></div>` : ''}
        <div class="stat-chip accent">${t('review.actual')} <b>${actualTotal != null ? hmsShort(actualTotal) : '&mdash;'}</b></div>
        <div class="stat-chip">${t('review.diffFromPred')} <b class="${finishDiff.cls}">${finishDiff.text}</b></div>
      </div>
      <h3 class="subsection-title">${t('review.cpDiffs')}</h3>
      ${buildReviewTable(entry)}
      <p class="card-footnote">${t('review.footnote')}</p>
    `;
    card.innerHTML = html;
  }
  document.getElementById('backToReviewList').addEventListener('click', closeReview);
}

function buildReviewTable(entry) {
  const hasGoal = !!(entry.goal_cp_results && entry.goal_cp_results.length);
  const goalByName = new Map((entry.goal_cp_results || []).map((r) => [r.name, r]));
  const segByTo = new Map((entry.segment_results || []).map((s) => [s.to_name, s]));
  let rows = '';
  entry.cp_results.forEach((cp, i) => {
    const d = diffText(cp.diff_s);
    const seg = i > 0 ? segByTo.get(cp.name) : null;
    const sd = diffText(seg ? seg.diff_s : null);
    const g = hasGoal ? diffText((goalByName.get(cp.name) || {}).diff_s) : null;
    rows += `<tr class="${cp.matched ? '' : 'unmatched'}">
      <td class="col-point"><span class="point-badge">${esc(cp.name)}</span><div class="cell-sub">${cp.predicted_dist_km}km</div></td>
      <td class="num"><div class="cell-main">${cp.actual_elapsed_s != null ? hmsShort(cp.actual_elapsed_s) : '&mdash;'}</div>
        <div class="cell-sub">${t('review.predCell', { v: cp.predicted_elapsed_s != null ? hmsShort(cp.predicted_elapsed_s) : '&mdash;' })}</div></td>
      <td class="num"><div class="cell-main ${d.cls}">${i === 0 ? '&mdash;' : d.text}</div></td>
      <td class="num"><div class="cell-main ${sd.cls}">${i === 0 ? '&mdash;' : sd.text}</div></td>
      ${hasGoal ? `<td class="num"><div class="cell-main ${g.cls}">${i === 0 ? '&mdash;' : g.text}</div></td>` : ''}
    </tr>`;
  });
  return `
    <table class="compact-table">
      <thead><tr>
        <th>Point</th><th class="num">${t('review.actual')}</th><th class="num">${t('review.diff')}</th><th class="num">${t('review.segment')}</th>
        ${hasGoal ? `<th class="num">${t('review.diffFromGoal')}</th>` : ''}
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

// ============================================================
// init
// ============================================================
// Called by setLang() (i18n.js) after the static text has been switched:
// redraw whatever dynamic content is on screen from the data already held.
function onLangChange() {
  renderDropzoneSub();
  if (state.uploadId) {
    renderCpTable();
    renderWeatherMsg();
  }
  if (state.lastPlanResult) renderReport(state.lastPlanResult, false);
  ['uploadMsg', 'planMsg', 'myRacesMsg'].forEach((id) => showMsg(id, '', ''));
  const active = document.querySelector('.tab-btn.active');
  const tab = active ? active.dataset.tab : null;
  if (tab === 'myRacesTab') loadMyRaces();
  if (tab === 'reviewTab') {
    if (state.reviewEntry) renderReviewDetail(state.reviewEntry);
    else loadReviewList();
  }
}

// ---------- course from a link ----------
// ?gpx=<GPX URL>&name=<race name>&start=yyyy-MM-ddTHH:mm&cutoffs=A3=19:00,A5=23:00,FINISH=10:00
// lets another page (e.g. a race info page) open the planner with the course,
// start time and cutoffs filled in. Cutoffs are matched to CPs by the first
// word of the GPX waypoint name ("A3 Pagia ..." -> A3), START/FINISH by role.
async function loadCourseFromLink(params) {
  const gpxUrl = params.get('gpx');
  const name = (params.get('name') || '').replace(/[\/:*?"<>|]/g, ' ').trim();
  const start = params.get('start') || '';
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(start)) document.getElementById('raceStart').value = start;
  openTab('predictTab');
  showMsg('uploadMsg', t('link.loading', { name: esc(name || gpxUrl) }), 'info');
  let file;
  try {
    const resp = await fetch(gpxUrl);
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const fileName = (name || decodeURIComponent(new URL(gpxUrl, location.href).pathname.split('/').pop()).replace(/\.gpx$/i, '')) + '.gpx';
    file = new File([await resp.blob()], fileName, { type: 'application/gpx+xml' });
  } catch (e) {
    showMsg('uploadMsg', t('link.failed', { v: esc(e.message) }), 'error');
    return;
  }
  await handleFile(file);
  if (!state.uploadId) return;
  const cutoffs = {};
  (params.get('cutoffs') || '').split(',').forEach((pair) => {
    const [code, clock] = pair.split('=');
    if (code && clock) cutoffs[code.trim().toUpperCase()] = clock.trim();
  });
  let applied = 0;
  state.cps.forEach((cp, i) => {
    if (i === 0) return;
    const code = i === state.cps.length - 1 ? 'FINISH' : cp.name.trim().split(/\s/)[0].toUpperCase();
    if (cutoffs[code]) { cp.cutoff = cutoffs[code]; applied++; }
  });
  renderCpTable();
  showMsg('uploadMsg', t('link.loaded', { name: esc(name || state.filename), n: applied }), 'ok');
}

async function init() {
  applyStaticI18n();
  document.querySelectorAll('.lang-btn').forEach((b) => b.addEventListener('click', () => setLang(b.dataset.lang)));
  document.querySelectorAll('.tab-btn').forEach((b) => b.addEventListener('click', () => openTab(b.dataset.tab)));

  const dz = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  dz.addEventListener('click', () => fileInput.click());
  dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.classList.add('dragover'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
  dz.addEventListener('drop', (e) => {
    e.preventDefault();
    dz.classList.remove('dragover');
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files.length) handleFile(fileInput.files[0]);
    fileInput.value = '';
  });

  document.getElementById('addCpBtn').addEventListener('click', addCpRow);
  document.getElementById('runPlanBtn').addEventListener('click', runPlan);
  document.getElementById('manualTemp').addEventListener('input', updateRunButton);
  document.getElementById('raceStart').addEventListener('change', onRaceStartChange);

  const addRaceInput = document.getElementById('addRaceFileInput');
  document.getElementById('addRaceBtn').addEventListener('click', () => addRaceInput.click());
  addRaceInput.addEventListener('change', async () => {
    if (addRaceInput.files.length) await addMyRaces(Array.from(addRaceInput.files));
    addRaceInput.value = '';
  });

  // default race start: 30 days from now, 06:00 local
  const d = new Date();
  d.setDate(d.getDate() + 30);
  d.setHours(6, 0, 0, 0);
  const pad = (n) => String(n).padStart(2, '0');
  document.getElementById('raceStart').value =
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;

  // Start where the user is in the workflow: マイレース until a personal model
  // exists, then straight to 予測.
  let hasPersonalModel = false;
  try { hasPersonalModel = (await api('/api/my-races')).is_custom_model; } catch (e) {}
  const params = new URLSearchParams(location.search);
  if (params.get('gpx')) { await loadCourseFromLink(params); return; }
  openTab(hasPersonalModel ? 'predictTab' : 'myRacesTab');
}

init();
