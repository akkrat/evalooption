"""Create, verify, and safely extract a portable evidence archive (stdlib only)."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1]
ROOTS=['approach_eval','reporting','scripts','tests','docs','tasks','runs','studies','analysis','reports',
       'README.md','.gitignore','pyproject.toml','requirements.lock','evaluation.json',
       '.eval-cache/validation-v2','.eval-cache/actual-instrumentation/package.json',
       '.eval-cache/actual-instrumentation/yarn.lock','.eval-cache/actual-forecast/base/yarn.lock']
SKIP={'.git','.venv','node_modules','__pycache__','.pytest_cache','.cache','.runtime-cache','.DS_Store','exports',
      'auth.json','credentials.json','.env','.env.local','.env.production','.env.development'}
TREES={'workspace','candidate-tree','regression-tree','hidden-tree','base','gold','base-hidden'}


def excluded(relative):
    parts=relative.parts
    if any(p in SKIP or p.endswith('.egg-info') or p.endswith('.pyc') for p in parts):return True
    # Keep evaluator build logs. Only omit generated bundles inside test repository trees.
    return any(p in ('build','dist') and any(q in TREES for q in parts[:i]) for i,p in enumerate(parts))


def inventory(root, roots):
    found={};skipped=[]
    for name in roots:
        entry=root/name
        if not entry.exists():continue
        if entry.is_file() and not entry.is_symlink():found[name]=entry;continue
        for base,dirs,files in os.walk(entry,followlinks=False):
            dirs.sort();files.sort()
            for name in list(dirs):
                p=Path(base)/name;r=p.relative_to(root)
                if p.is_symlink() or excluded(r):
                    skipped.append({'path':str(r),'reason':'symlink' if p.is_symlink() else 'dependency/cache/generated directory'})
                    dirs.remove(name)
            for name in files:
                p=Path(base)/name;r=p.relative_to(root)
                if p.is_symlink() or excluded(r):
                    skipped.append({'path':str(r),'reason':'symlink' if p.is_symlink() else 'excluded file'})
                    continue
                if p.is_file():found[str(r)]=p
    return sorted(found.items()),skipped


class HashedReader:
    def __init__(self,file):self.file=file;self.hash=hashlib.sha256()
    def read(self,n=-1):
        data=self.file.read(n);self.hash.update(data);return data


def create(output, root=ROOT, roots=ROOTS):
    output=output.resolve()
    if output.exists():raise FileExistsError(f'Archive exists; choose a new filename: {output}')
    files,skipped=inventory(root,roots)
    total=sum(p.stat().st_size for _,p in files)
    print(f'Archiving {len(files):,} files / {total/1e9:.2f} GB before compression',flush=True)
    records=[];output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_name(output.name+'.partial')
    if temp.exists():raise FileExistsError(f'Partial archive exists: {temp}')
    revision=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True).stdout.strip() or None
    try:
        with temp.open('xb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=6) as compressed,tarfile.open(fileobj=compressed,mode='w|',format=tarfile.PAX_FORMAT) as tar:
            for i,(name,path) in enumerate(files):
                stat=path.stat();info=tarfile.TarInfo(name);info.size=stat.st_size;info.mode=0o755 if stat.st_mode&0o111 else 0o644
                with path.open('rb') as f:
                    reader=HashedReader(f);tar.addfile(info,reader)
                after=path.stat()
                if (stat.st_size,stat.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise RuntimeError(f'File changed during export: {name}')
                records.append({'path':name,'bytes':info.size,'sha256':reader.hash.hexdigest()})
                if i and i%20000==0:print(f'  {i:,}/{len(files):,}',flush=True)
            manifest={'schema_version':1,'harness_git_commit':revision,'files':records,'exclusions':skipped,
                      'scope':'All local runs (including calibration), application studies, new reference analysis, report, upstream before/reference source archives, frozen engines and authored harness code. No global Codex auth or session store.',
                      'limitations':['Dependencies, browser binaries, Git object databases, runtime caches and generated application bundles are excluded. Evaluator build logs are retained.',
                                     'Raw evidence is byte-preserved; transcripts and logs may contain local absolute paths and developer prose. They are not anonymized.',
                                     'Source snapshots retain licenses. Install pinned dependencies separately to rerun tests. Report rebuild needs only Python and data.json.'],
                      'restore':'python3 reporting/archive_results.py --verify ARCHIVE; then --extract ARCHIVE --destination NEW_DIRECTORY. Open reports/comparison/index.html. Rebuild with python3 reporting/build_report.py --from-data reports/comparison/data.json.'}
            payload=(json.dumps(manifest,indent=2)+'\n').encode();info=tarfile.TarInfo('ARCHIVE_MANIFEST.json');info.size=len(payload);info.mode=0o644;tar.addfile(info,io.BytesIO(payload))
        temp.replace(output)
    except BaseException:
        # Keep a failed export visible for diagnosis; never advertise it as complete.
        raise
    checksum=hash_file(output)
    output.with_name(output.name+'.sha256').write_text(checksum+'  '+output.name+'\n')
    print(f'Created {output} ({output.stat().st_size/1e6:.1f} MB); SHA-256 {checksum}',flush=True)
    return manifest


def hash_file(path):
    with path.open('rb') as f:return hash_stream(f)


def hash_stream(file):
    h=hashlib.sha256()
    while chunk:=file.read(1024*1024):h.update(chunk)
    return h.hexdigest()


def safe_name(name):
    p=PurePosixPath(name)
    return bool(name) and not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name and str(p)==name


def verify(path):
    actual={};manifest=None
    with tarfile.open(path,'r|gz') as tar:
        for member in tar:
            if not member.isfile() or not safe_name(member.name):raise ValueError(f'Unsafe archive member: {member.name}')
            if member.name in actual or (member.name=='ARCHIVE_MANIFEST.json' and manifest is not None):raise ValueError('Duplicate archive path')
            f=tar.extractfile(member)
            if member.name=='ARCHIVE_MANIFEST.json':
                if member.size>150_000_000:raise ValueError('Manifest exceeds size limit')
                manifest=json.load(f)
            else:actual[member.name]={'sha256':hash_stream(f),'bytes':member.size}
    if not manifest or manifest.get('schema_version')!=1:raise ValueError('Missing or unsupported manifest')
    records=manifest['files'];expected={r['path']:{k:r[k] for k in ('sha256','bytes')} for r in records}
    if len(expected)!=len(records) or actual!=expected:raise ValueError('Manifest mismatch: missing, extra, duplicate or corrupted files')
    print(f'Verified {len(actual):,} files and SHA-256 checksums',flush=True)
    return manifest


def extract(path,destination):
    manifest=verify(path)
    destination=destination.resolve()
    if destination.exists():raise FileExistsError('Extraction destination must not exist')
    destination.mkdir(parents=True)
    with tarfile.open(path,'r:gz') as tar:tar.extractall(destination,filter='data')
    print(f'Extracted to {destination}',flush=True)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--verify',type=Path);mode.add_argument('--extract',type=Path)
    parser.add_argument('--destination',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'exports/evaluation-results.tar.gz')
    parser.add_argument('--list',action='store_true',help='Show archive scope and size without creating it')
    args=parser.parse_args()
    if args.verify:verify(args.verify)
    elif args.extract:
        if not args.destination:parser.error('--extract requires --destination')
        extract(args.extract,args.destination)
    elif args.list:
        files,skipped=inventory(ROOT,ROOTS);print(json.dumps({'files':len(files),'bytes':sum(p.stat().st_size for _,p in files),'excluded_entries':len(skipped),'roots':ROOTS},indent=2))
    else:create(args.output)


if __name__=='__main__':main()
