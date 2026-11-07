// Loopback visual preview from browser-acceptance fixtures, never a device proxy.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const data = path.join(root, 'build/ha-frontend/preview.json');
if (!fs.existsSync(data)) throw new Error('Run tests/ha_integration/test_frontend_browser.py first');
const port = Number(process.argv[2] || 8775);
const coreAsset = process.argv[3] || process.env.HOME_PANEL_CORE_ASSET;
if (!coreAsset || !fs.existsSync(coreAsset)) throw new Error('Pass the installed core runtime-draft.mjs path as argument 3');
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Invalid port');
const routes = new Map([
  ['/preview.json', [data, 'application/json']],
  ['/preview.js', [path.join(root, 'tests/fixtures/ha_frontend/preview.js'), 'text/javascript']],
  ['/home_panel_static/runtime-draft.mjs', [coreAsset, 'text/javascript']],
  ...['home-panel.js', 'home-panel.css', 'draft-editor.js'].map(name => ['/home_panel_static/' + name,
    [path.join(root, 'custom_components/home_panel/www', name), name.endsWith('.css') ? 'text/css' : 'text/javascript']]),
]);
const server = http.createServer((request, response) => {
  if (request.method !== 'GET') { response.writeHead(405); response.end(); return; }
  const url = new URL(request.url, 'http://127.0.0.1');
  response.setHeader('Cache-Control', 'no-store');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
  if (url.pathname === '/') {
    response.writeHead(200, {'Content-Type':'text/html; charset=utf-8'});
    response.end('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Home Panel Preview</title><style>html,body{margin:0;height:100%;font:14px sans-serif}body{display:flex;flex-direction:column}aside{padding:8px 16px;background:#fff4ce;color:#493d12}home-panel-config{flex:1;min-height:0}</style><aside>Превью: тестовые данные, без HA/ESP32 и валидатора. Черновик только в памяти этой страницы.</aside><home-panel-config></home-panel-config><script type="module" src="/preview.js"></script></html>');
    return;
  }
  const file = routes.get(url.pathname);
  if (!file) { response.writeHead(404); response.end(); return; }
  response.writeHead(200, {'Content-Type':file[1] + '; charset=utf-8'});
  fs.createReadStream(file[0]).pipe(response);
});
server.listen(port, '127.0.0.1', () => console.log(`Fixture preview: http://127.0.0.1:${port}`));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close());
