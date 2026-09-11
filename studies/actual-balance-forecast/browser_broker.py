"""Narrow local Node/browser execution service for Codex's macOS Chromium limitation.

Scripts stay inside the candidate. Seatbelt enforces filesystem and loopback bounds;
no evaluator/reference paths or credentials are passed to executed code.
"""
from runtime import *
from isolation import sandbox
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import threading,uuid

class BrowserBroker:
    def __init__(self,workspace,readonly=False):
        self.workspace=Path(workspace).resolve();self.readonly=readonly
        self.output=self.workspace/'node_modules/.cache/browser-runner';self.output.mkdir(parents=True,exist_ok=True)
        broker=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                try:
                    if self.path!='/run':raise ValueError('Only /run is supported')
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=8192:raise ValueError('Invalid request size')
                    body=json.loads(self.rfile.read(size))
                    source=(broker.workspace/body['script']).resolve(strict=True)
                    if broker.workspace not in source.parents or source.suffix not in ('.js','.mjs','.cjs'):
                        raise ValueError('Script must be a JavaScript file inside this candidate')
                    out=broker.output/uuid.uuid4().hex;out.mkdir()
                    env=environment(broker.workspace);env['TMPDIR']=str(out/'tmp');Path(env['TMPDIR']).mkdir()
                    env['ACTUAL_BROWSER_OUTPUT']=str(out)
                    argv=sandbox([NODE,source],broker.workspace,out,browser=True,
                                 extra_reads=[CACHE/'actual-instrumentation'],readonly=broker.readonly,protect_dependencies=True)
                    result=command(argv,broker.workspace,timeout=min(240,max(1,int(body.get('timeout',120)))),env=env)
                    dump(out/'result.json',result)
                    result={**result,'output_directory':str(out)}
                    status=200
                except Exception as exc:result={'error':str(exc)};status=400
                payload=json.dumps(result).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(payload)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)+'/run'
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
