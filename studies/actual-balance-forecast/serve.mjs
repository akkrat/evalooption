// Evaluator-owned static serving and clock instrumentation; never changes source files.
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';

const [directory, portArg = '43171', readyFile] = process.argv.slice(2);
if (!directory) throw new Error('Usage: serve.mjs BUILD_DIRECTORY [PORT] [READY_FILE]');
const root = fs.realpathSync(directory);
const epoch = Date.parse('2017-01-01T12:00:00Z');
const shim = `;(()=>{const k=Symbol.for('actual-eval-clock');if(globalThis[k]===${epoch})return;const D=globalThis.Date;let F;F=new Proxy(D,{construct(t,a,n){return Reflect.construct(t,a.length?a:[${epoch}],n===F?t:n)},apply(){return new D(${epoch}).toString()},get(t,p,r){return p==='now'?()=>${epoch}:Reflect.get(t,p,r)}});globalThis.Date=F;globalThis[k]=${epoch};})();\n`;
const mime = {'.html':'text/html', '.js':'application/javascript', '.mjs':'application/javascript',
  '.css':'text/css', '.json':'application/json', '.svg':'image/svg+xml', '.png':'image/png',
  '.jpg':'image/jpeg', '.wasm':'application/wasm', '.woff':'font/woff', '.woff2':'font/woff2',
  '.ttf':'font/ttf', '.webmanifest':'application/manifest+json', '.txt':'text/plain'};
const server = http.createServer((req, res) => {
  res.setHeader('Cross-Origin-Opener-Policy', 'same-origin');
  res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp');
  res.setHeader('Cross-Origin-Resource-Policy', 'same-origin');
  res.setHeader('Cache-Control', 'no-store');
  let pathname;
  try { pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname); }
  catch { res.writeHead(400); res.end(); return; }
  let file = path.resolve(root, '.' + pathname);
  const relative = path.relative(root, file);
  if (relative.startsWith('..') || path.isAbsolute(relative) || pathname.includes('\0')) {
    res.writeHead(403); res.end(); return;
  }
  if (!fs.existsSync(file) || !fs.statSync(file).isFile()) {
    if (path.extname(pathname)) { res.writeHead(404); res.end(); return; }
    file = path.join(root, 'index.html');
  }
  const real = fs.realpathSync(file);
  if (!real.startsWith(root + path.sep)) { res.writeHead(403); res.end(); return; }
  const extension = path.extname(file);
  res.setHeader('Content-Type', mime[extension] || 'application/octet-stream');
  if (extension === '.js' || extension === '.mjs') {
    let code = fs.readFileSync(file, 'utf8');
    // Preserve an existing classic-script strict-mode directive.
    const directive = code.match(/^(\s*(?:(?:\/\*[\s\S]*?\*\/|\/\/[^\n]*\n)\s*)*)(['"])use strict\2;?/);
    const position = directive ? directive[0].length : 0;
    code = code.slice(0, position) + '\n' + shim + code.slice(position);
    res.end(code);
  } else fs.createReadStream(file).pipe(res);
});
server.listen(Number(portArg), '127.0.0.1', () => {
  const address = server.address();
  const record = {url: `http://127.0.0.1:${address.port}`, root, epoch, pid: process.pid};
  if (readyFile) fs.writeFileSync(readyFile, JSON.stringify(record, null, 2));
  console.log(JSON.stringify(record));
});
