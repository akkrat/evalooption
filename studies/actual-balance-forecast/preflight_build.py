from runtime import *
from app_codex import Codex
from approach_eval.core import config
import datetime
p=STUDY/'preflight'/('build-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));p.mkdir(parents=True)
s=config();s.update(turn_timeout_seconds=900,max_run_seconds=1200)
c=Codex(p,s)
workspace=STUDY/'preflight/workspace'
script=r'''import subprocess, pathlib, os, urllib.request, json
commands=[['node','.yarn/releases/yarn-4.13.0.cjs','build:browser','--skip-translations'],['node','.yarn/releases/yarn-4.13.0.cjs','workspace','@actual-app/core','run','test:node','src/server/schedules'],['node','.yarn/releases/yarn-4.13.0.cjs','workspace','@actual-app/web','run','test','src/components/reports/getLiveRange.test.ts']]
for argv in commands:
 r=subprocess.run(argv,text=True,capture_output=True);print('EXIT',r.returncode,'COMMAND',argv,'OUTPUT',r.stdout[-3000:],r.stderr[-2000:]);assert r.returncode==0
p=pathlib.Path('.eval-output/browser-calibration.cjs');p.parent.mkdir(exist_ok=True)
p.write_text("""const fs=require('node:fs');
(async()=>{
try {fs.readFileSync('__HIDDEN__');throw Error('Hidden read allowed')}catch(e){if(e.code!=='EPERM'&&e.code!=='EACCES')throw e;console.log('BROKER_HIDDEN_DENIED')}
for(const p of ['node_modules/vitest/package.json','.git/config']){try{fs.appendFileSync(p,'');throw Error('Protected write allowed')}catch(e){if(e.code!=='EPERM'&&e.code!=='EACCES')throw e;console.log('BROKER_WRITE_DENIED')}}
const {chromium}=require('playwright');const b=await chromium.launch({headless:true});const p=await b.newPage();await p.goto('data:text/html,<h1>local</h1>');if(await p.locator('h1').innerText()!=='local')throw Error('browser failure');await b.close();console.log('CHROMIUM_OK');
try{await fetch('https://example.com',{signal:AbortSignal.timeout(3000)});throw Error('External fetch allowed')}catch(e){if(e.message==='External fetch allowed')throw e;console.log('BROKER_EXTERNAL_DENIED')}
})().catch(e=>{console.error(e);process.exit(1)})""")
request=urllib.request.Request(os.environ['ACTUAL_BROWSER_RUNNER'],data=json.dumps({'script':str(p),'timeout':30}).encode(),headers={'Content-Type':'application/json'})
r=json.load(urllib.request.urlopen(request,timeout=60));print('BROWSER_RUNNER',json.dumps(r));assert r['returncode']==0
print('APP_BUILD_PREFLIGHT_PASS')
'''.replace('__HIDDEN__',str(STUDY/'study.json'))
_,response=c.call('agent',workspace,'Execute the following exact Python script using '+str(sys.executable)+'. This is environment calibration; do not solve a feature, change source files, repair failures, or dispatch. Return status done and report output.\n'+script,stage='build-runtime')
events=[json.loads(x) for x in (p/'turns/000-agent-build-runtime/events.jsonl').read_text().splitlines()]
passed=any('APP_BUILD_PREFLIGHT_PASS' in e.get('item',{}).get('aggregated_output','') and e.get('item',{}).get('exit_code')==0 for e in events)
dump(p/'result.json',dict(passed=passed,response=response,kind='build-runtime'));print('BUILD PREFLIGHT',passed,p,flush=True)
