// Browser build: app.js's /api/... requests go to the Python app running in
// py/worker.js instead of a local server. pyFetch() returns a real Response,
// so app.js's api() keeps working unchanged apart from fetch -> pyFetch.
const pyWorker = new Worker('py/worker.js?v=202610231624');
const pyPending = new Map();
let pySeq = 0;

const PY_STATUS = {
  python: ['計算エンジンを準備中…（初回は30秒ほどかかります）', 'Loading the prediction engine… (about 30 s the first time)'],
  packages: ['計算エンジンを準備中…（部品を読み込み中）', 'Loading the prediction engine… (packages)'],
  app: ['計算エンジンを準備中…（もうすぐです）', 'Loading the prediction engine… (almost ready)'],
  error: ['計算エンジンを読み込めませんでした。通信状態を確認して、ページを再読み込みしてください。', 'Could not load the prediction engine. Check your connection and reload the page.'],
};

function pyShowStatus(key, extra) {
  const bar = document.getElementById('pyStatus');
  if (!bar) return;
  if (!key) { bar.classList.add('hidden'); return; }
  const lang = (typeof LANG !== 'undefined' && LANG === 'en') ? 1 : 0;
  bar.textContent = PY_STATUS[key][lang] + (extra ? ` (${extra})` : '');
  bar.classList.remove('hidden');
}

pyWorker.onmessage = (e) => {
  const m = e.data;
  if (m.type === 'progress') return pyShowStatus(m.text);
  if (m.type === 'ready') return pyShowStatus(null);
  if (m.type === 'error') return pyShowStatus('error', m.text);
  const resolve = pyPending.get(m.id);
  pyPending.delete(m.id);
  if (resolve) resolve(m);
};

async function pyFetch(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  let body = null;
  let fileName = null;
  let fileBytes = null;
  if (options.body instanceof FormData) {
    const f = options.body.get('file');
    fileName = f.name;
    fileBytes = new Uint8Array(await f.arrayBuffer());
  } else if (options.body != null) {
    body = String(options.body);
  }
  const m = await new Promise((resolve) => {
    const id = ++pySeq;
    pyPending.set(id, resolve);
    pyWorker.postMessage({ id, method, path, body, fileName, fileBytes }, fileBytes ? [fileBytes.buffer] : []);
  });
  if (m.bytes_b64 != null) {
    const bin = Uint8Array.from(atob(m.bytes_b64), (c) => c.charCodeAt(0));
    return new Response(bin, { status: m.status, headers: { 'Content-Type': m.media_type, ...m.headers } });
  }
  return new Response(m.body, { status: m.status, headers: { 'Content-Type': 'application/json' } });
}

// Replaces the desktop/Android "navigate to /api/plan/pdf" download.
async function pyDownload(path) {
  const resp = await pyFetch(path);
  if (!resp.ok) {
    let detail = resp.statusText;
    try { detail = (await resp.json()).detail || detail; } catch (e) {}
    alert(serverMsg(detail));
    return;
  }
  const cd = resp.headers.get('Content-Disposition') || '';
  const mm = cd.match(/filename\*=UTF-8''([^;]+)/);
  const url = URL.createObjectURL(await resp.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = mm ? decodeURIComponent(mm[1]) : 'race-plan.pdf';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
