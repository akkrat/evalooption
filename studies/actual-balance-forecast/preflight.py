"""Real Luna actor/user protocol and pinned application sandbox calibration."""
from runtime import *
from app_codex import Codex
from approach_eval.core import config
import datetime

def main():
    directory=STUDY/'preflight'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    workspace=STUDY/'preflight/workspace'
    directory.mkdir(parents=True)
    settings=config();settings.update(turn_timeout_seconds=600,max_run_seconds=1500)
    client=Codex(directory,settings)
    user=directory/'user';user.mkdir()
    _,response=client.call('user',user,'You know only this: Actual is a personal finance application. Ask an assistant to add a balance forecast from accounts and schedules. Return status done, a brief message, and no dispatches.',stage='user-protocol')
    script='''import pathlib, subprocess, json, socket, threading, http.server, urllib.request
root=pathlib.Path.cwd()
for path in [__HIDDEN__, __GOLD__]:
 try: pathlib.Path(path).read_text()
 except PermissionError: print('HIDDEN_READ_DENIED')
 else: raise AssertionError('Hidden file was readable')
for path in [root/'packages/loot-core/src/server/main.ts',root/'node_modules/vitest/package.json',root/'.git/forbidden-probe']:
 try:
  with path.open('a') as stream: stream.write('')
 except PermissionError: print('WRITE_DENIED',path.name)
 else: raise AssertionError('Protected path was writable: '+str(path))
(root/'.workflow').mkdir(exist_ok=True)
(root/'.workflow/preflight.md').write_text('ARTIFACT_WRITE_ALLOWED')
for argv in [['node','--version'],['node','-e',"const D=require('better-sqlite3'); const d=new D(':memory:'); console.log(d.prepare('select 42 as n').get().n);d.close()"],['node','.yarn/releases/yarn-4.13.0.cjs','--version']]:
 r=subprocess.run(argv,text=True,capture_output=True);print(r.returncode,r.stdout,r.stderr);assert r.returncode==0
class Handler(http.server.BaseHTTPRequestHandler):
 def do_GET(self): self.send_response(200);self.end_headers();self.wfile.write(b'LOCAL_OK')
server=http.server.HTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
assert urllib.request.urlopen('http://127.0.0.1:'+str(server.server_port),timeout=10).read()==b'LOCAL_OK'
server.shutdown(); print('LOCAL_NETWORK_ALLOWED')
print('APP_PREFLIGHT_PASS')
'''.replace('__HIDDEN__',repr(str(STUDY/'study.json'))).replace('__GOLD__',repr(str(GOLD/'package.json')))
    _,answer=client.call('agent',workspace,'Execute this exact Python script once using the supplied Python executable '+str(sys.executable)+'. Do not change the script or fix failures. Report output; no dispatches. First execute this local-only script. Then in a separate shell command try urllib.request.urlopen(https://example.com) with a 10-second timeout to confirm external access is denied. Report its outcome too.\n'+script,stage='runtime-permissions',artifact_only=True)
    eventfile=directory/'turns/001-agent-runtime-permissions/events.jsonl'
    events=[json.loads(x) for x in eventfile.read_text().splitlines()]
    outputs=[e['item'].get('aggregated_output','') for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='command_execution' and e['item'].get('exit_code')==0]
    passed=any('APP_PREFLIGHT_PASS' in x and 'LOCAL_NETWORK_ALLOWED' in x for x in outputs) and 'was blocked: domain is not on the allowlist' in eventfile.read_text()
    dump(directory/'result.json',dict(passed=passed,response=answer,settings=settings))
    print('APP PREFLIGHT',passed,directory,flush=True)
if __name__=='__main__':main()
