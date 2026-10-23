// Browser build: runs app.py + analysis/ with Pyodide in a Web Worker, so the
// page stays responsive and weather lookups can use synchronous XHR.
// Requests are handled one at a time; user data lives in /data (IndexedDB),
// synced back after every non-GET request.
importScripts('https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js');

const BUILD = '202610231443';
let pyodide = null;
let handle = null;
let pdfReady = false;

function progress(text) { self.postMessage({ type: 'progress', text }); }

function syncfs(populate) {
  return new Promise((resolve, reject) => pyodide.FS.syncfs(populate, (err) => (err ? reject(err) : resolve())));
}

function writeFile(path, data) {
  const parts = path.split('/').filter(Boolean);
  let dir = '';
  for (const p of parts.slice(0, -1)) {
    dir += '/' + p;
    if (!pyodide.FS.analyzePath(dir).exists) pyodide.FS.mkdir(dir);
  }
  pyodide.FS.writeFile(path, data);
}

async function fetchBytes(url) {
  const resp = await fetch(`${url}?v=${BUILD}`);
  if (!resp.ok) throw new Error(`${url}: ${resp.status}`);
  return new Uint8Array(await resp.arrayBuffer());
}

async function boot() {
  progress('python');
  pyodide = await loadPyodide();
  progress('packages');
  await pyodide.loadPackage(['micropip', 'pydantic']);
  await pyodide.pyimport('micropip').install('gpxpy');
  progress('app');
  const files = JSON.parse(new TextDecoder().decode(await fetchBytes('files.json')));
  for (const f of files) writeFile('/app/' + f, await fetchBytes(f));
  pyodide.FS.mkdir('/data');
  pyodide.FS.mount(pyodide.FS.filesystems.IDBFS, {}, '/data');
  await syncfs(true);
  pyodide.runPython("import sys; sys.path.insert(0, '/app')");
  handle = pyodide.pyimport('bridge').handle;
}

// reportlab + the 5.8MB Japanese font, only when a PDF is first requested.
async function preparePdf() {
  await pyodide.pyimport('micropip').install('reportlab');
  writeFile('/app/assets/fonts/NotoSansJP-Regular.ttf', await fetchBytes('assets/fonts/NotoSansJP-Regular.ttf'));
  pdfReady = true;
}

const ready = boot().then(
  () => self.postMessage({ type: 'ready' }),
  (err) => { self.postMessage({ type: 'error', text: String(err) }); throw err; },
);

async function run(req) {
  let out;
  try {
    await ready;
    if (req.path.startsWith('/api/plan/pdf') && !pdfReady) await preparePdf();
    const res = await handle(req.method, req.path, req.body, req.fileName, req.fileBytes);
    out = res.toJs({ dict_converter: Object.fromEntries });
    res.destroy();
    if (req.method !== 'GET') await syncfs(false);
  } catch (err) {
    out = { status: 500, body: JSON.stringify({ detail: String(err) }) };
  }
  self.postMessage({ id: req.id, ...out });
}

let chain = Promise.resolve();
self.onmessage = (e) => { chain = chain.then(() => run(e.data)); };
