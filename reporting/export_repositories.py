"""Export exact upstream before/reference trees with provenance, without dependency caches."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    tasks=json.loads((ROOT/'tasks/suite.json').read_text())['tasks']
    tasks.append(json.loads((ROOT/'studies/actual-balance-forecast/study.json').read_text()))
    for task in tasks:
        repo=ROOT/'.eval-cache'/('actual-forecast.git' if task['id']=='actual-balance-forecast' else task['repo'])
        out=ROOT/'analysis/repositories'/task['id'];out.mkdir(parents=True,exist_ok=True)
        records=[]
        for kind,key in [('before','base_commit'),('reference','fix_commit')]:
            target=out/(kind+'.tar.gz')
            if not target.exists():
                subprocess.run(['git','archive','--format=tar.gz','-o',str(target),task[key]],cwd=repo,check=True)
            records.append({'kind':kind,'commit':task[key],'file':target.name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
        (out/'PROVENANCE.json').write_text(json.dumps({'task':task['id'],'repository':task['repository'],'pull_request':task['source_url'],
            'provenance':task.get('provenance',task.get('reference_provenance')),'snapshots':records,
            'restore':'Extract each archive to a separate directory. These are exact git archive source/test trees, with licenses and locks; install dependencies separately. Candidate workspaces and patches are in the run artifacts.'},indent=2)+'\n')
        print(task['id'],flush=True)


if __name__=='__main__':main()
