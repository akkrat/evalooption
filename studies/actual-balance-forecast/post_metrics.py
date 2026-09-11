"""Uniform descriptive diff metrics; does not change frozen trial outcomes."""
from runtime import *
from approach_eval.grading import changes
from approach_eval.core import git
import re,hashlib

def measure(directory):
    directory=Path(directory);candidate=directory/'workspace'
    method_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    cached=directory/'post-metrics.json'
    if cached.exists():
        value=json.loads(cached.read_text())
        if value.get('method_sha256')==method_hash:return value
    result=json.loads((directory/'result.json').read_text())
    filenames=changes(candidate)
    production=[x for x in filenames if x.startswith('packages/') and '/src/' in x and '.test.' not in x and x.endswith(('.ts','.tsx','.js','.jsx','.mjs'))]
    untracked=set(git(candidate,'ls-files','--others','--exclude-standard').splitlines())
    added={}
    for name in production:
        path=candidate/name
        if not path.is_file():continue
        if name in untracked:added[name]=set(range(1,len(path.read_text().splitlines())+1));continue
        lines=set()
        for match in re.finditer(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@',git(candidate,'diff','--unified=0','HEAD','--',name),re.M):
            start,count=int(match[1]),int(match[2] or 1);lines.update(range(start,start+count))
        added[name]=lines
    mapped={}
    for path in directory.glob('*evaluation/candidate-tests/*/coverage/coverage-final.json'):
        for filename,data in json.loads(path.read_text()).items():
            if '/candidate-tree/' not in filename:continue
            name=filename.split('/candidate-tree/',1)[1]
            if name not in added:continue
            line_counts=mapped.setdefault(name,{})
            for sid,span in data.get('statementMap',{}).items():
                line=span['start']['line'];line_counts[line]=max(line_counts.get(line,0),data['s'].get(sid,0))
    selected={name:{line:count for line,count in values.items() if line in added[name]} for name,values in mapped.items()}
    total=sum(map(len,selected.values()));covered=sum(v>0 for values in selected.values() for v in values.values())
    value={'method_sha256':method_hash,'changed_production_files':len(production),'changed_test_files':sum('.test.' in x or '/e2e/' in x for x in filenames),
           'changed_documentation_files':sum(x.endswith('.md') for x in filenames),
           'added_production_text_lines':sum(map(len,added.values())),
           'added_statement_start_lines':total,'covered_added_statement_start_lines':covered,
           'added_statement_start_line_coverage_percent':100*covered/total if total else None,
           'files_without_coverage_mapping':[x for x in production if x not in mapped],
           'definition':'Distinct newly added/changed lines that start an Istanbul statement; line hit counts are unioned across core/web tests. This excludes statement continuations, type-only lines, comments, and unsupported source. Scope counts are not quality scores.'}
    dump(directory/'post-metrics.json',value);return value
if __name__=='__main__':
    for p in (STUDY/'runs').glob('*'):
        if (p/'result.json').exists():print(p.name,json.dumps(measure(p)))
