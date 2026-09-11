"""Post-trial browser replay with an explicitly recorded locator-only script.

Never use while any measured actor is running: serving another candidate would
create an avoidable cross-trial information channel over localhost.
"""
from runtime import *
from isolation import sandbox
import signal,time,hashlib

def source_digest(tree):
    names=subprocess.check_output([str(GIT),'ls-files','--cached','--others','--exclude-standard','-z'],cwd=tree).decode().split('\0')
    manifest={}
    for name in sorted(set(names)-{''}):
        path=tree/name
        if path.is_file():manifest[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    return {'files':len(manifest),'sha256':hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()}

def run(tree,script,output,replacements):
    tree,script,output=Path(tree).resolve(),Path(script).resolve(),Path(output).resolve()
    schedule=json.loads((STUDY/'schedule.json').read_text())
    if not all((STUDY/'runs'/a/'result.json').exists() for a in schedule['approaches']):
        raise RuntimeError('Wait for all measured actors to finish before opening a candidate QA server')
    output.mkdir(parents=True,exist_ok=False)
    before=source_digest(tree)
    shutil.copy2(STUDY/'serve.mjs',output/'serve.mjs');shutil.copy2(script,output/'browser_check.mjs')
    dump(output/'adaptations.json',{'original_sha256':hashlib.sha256((STUDY/'browser_check.mjs').read_bytes()).hexdigest(),
         'adapted_sha256':hashlib.sha256(script.read_bytes()).hexdigest(),'replacements':replacements,
         'policy':'Only control/format bindings change; same fixture, time, amounts, dates and expected outcomes. No candidate source edits.'})
    env=environment(tree);env['TMPDIR']=str(output/'tmp');Path(env['TMPDIR']).mkdir()
    ready=output/'server.json';stream=(output/'server.log').open('w')
    server=subprocess.Popen(sandbox([NODE,output/'serve.mjs',tree/'packages/desktop-client/build',0,ready],tree,output,browser=True),
                            cwd=tree,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        for _ in range(100):
            if ready.exists():break
            if server.poll() is not None:raise RuntimeError('QA server stopped')
            time.sleep(.05)
        url=json.loads(ready.read_text())['url']
        result=command(sandbox([NODE,output/'browser_check.mjs',tree,url,output],tree,output,browser=True),cwd=tree,env=env,timeout=240)
        (output/'stdout.log').write_text(result.pop('stdout'));(output/'stderr.log').write_text(result.pop('stderr'));dump(output/'command.json',result)
        value=json.loads((output/'result.json').read_text()) if (output/'result.json').exists() else {'passed':False,'checks':[],'error':'Browser infrastructure failure'}
        value['command']=result
        after=source_digest(tree)
        value['source_integrity']={'before':before,'after':after,'unchanged':before==after}
        dump(output/'result.json',value);return value
    finally:
        if server.poll() is None:
            os.killpg(server.pid,signal.SIGTERM)
            try:server.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(server.pid,signal.SIGKILL);server.wait()
        stream.close()

if __name__=='__main__':
    tree,script,output,adaptations=sys.argv[1:]
    print(json.dumps(run(tree,script,output,json.loads(Path(adaptations).read_text())),indent=2))
