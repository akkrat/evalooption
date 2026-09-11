"""macOS evaluator isolation: source/runtime only, loopback only, private outputs."""
import json
from pathlib import Path
from runtime import NODE, ROOT, CACHE, STUDY

def sandbox(args, tree, output, browser=False, extra_reads=(), readonly=False, protect_dependencies=False):
    tree, output = Path(tree).resolve(), Path(output).resolve()
    # Base package.json and Playwright installation are instrumentation, not application source.
    reads=[tree,output,NODE.parent.parent,Path('/Library/Developer/CommandLineTools'),
           CACHE/'actual-playwright',*map(Path,extra_reads)]
    writes=[output,Path('/dev/null')] + ([] if readonly else [tree])
    q=lambda x:json.dumps(str(x))
    rex=' '.join('(require-not (subpath '+q(p)+'))' for p in reads)
    wex=' '.join('(require-not (subpath '+q(p)+'))' for p in writes)
    policy='(version 1) (allow default) (deny network*) '
    if browser:
        policy+='(allow network-inbound (local ip "localhost:*")) (allow network-outbound (remote ip "localhost:*")) '
    policy+='(deny file-read-data (require-all (subpath '+q(Path.home())+') '+rex+')) '
    policy+='(deny file-write* (require-all '+wex+'))'
    if protect_dependencies:
        for dep in [tree/'node_modules',*tree.glob('packages/*/node_modules')]:
            exclusions=' '.join('(require-not (subpath '+q(dep/name)+'))' for name in ('.cache','.vite','.vite-temp'))
            policy+='(deny file-write* (require-all (subpath '+q(dep)+') '+exclusions+')) '
        policy+='(deny file-write* (subpath '+q(tree/'.git')+')) '
    return ['/usr/bin/sandbox-exec' ,'-p',policy,*map(str,args)]
