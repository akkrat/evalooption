"""Pinned workflows adapted only for this Node/Yarn application runtime."""
from runtime import *
from approach_eval.workflows import stages as original_stages,install as original_install,TOOLING

def stages(approach):
    return [(name,template.replace('existing Python library','existing TypeScript application').replace('library scope','application scope'),review)
            for name,template,review in original_stages(approach)]

def install(approach,tree,task):
    tree=Path(tree)
    if approach!='gennady':
        old=os.environ.get('PATH','')
        os.environ['PATH']=str(NODE.parent)+':'+old
        try:return original_install(approach,tree,task)
        finally:os.environ['PATH']=old
    package=TOOLING/'gennady'
    shutil.copytree(package/'ai/directives',tree/'ai/directives')
    shutil.copytree(package/'ai/skills',tree/'.agents/skills')
    for path in (tree/'.agents/skills').rglob('SKILL.md'):
        path.write_text(path.read_text().replace('~/Developer/gennady/',''))
    gates=[('typecheck',['typecheck']),('lint',['lint']),
           ('core-tests',['workspace','@actual-app/core','run','test:node']),
           ('web-tests',['workspace','@actual-app/web','run','test'])]
    text='stack:\n  use: [anystack]\n  anystack:\n    extraGates:\n'
    for name,args in gates:
        text+='      - id: '+name+'\n        argv: '+json.dumps([str(NODE),YARN,*args])+'\n        timeout: 15m\n'
    (tree/'gennady.yaml').write_text(text)
