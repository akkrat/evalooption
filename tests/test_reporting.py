import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

import pytest
from reporting.archive_results import create, extract, inventory, safe_name, verify
from reporting.build_report import actors, render


def malicious_archive(path, name, kind=tarfile.REGTYPE):
    with tarfile.open(path,'w:gz') as tar:
        item=tarfile.TarInfo(name);item.type=kind;item.size=0
        tar.addfile(item,io.BytesIO())


@pytest.mark.parametrize('name',['../escape','/absolute','a/../../b','a\\b','C:/escape','a//b','./a'])
def test_unsafe_paths_rejected(tmp_path,name):
    assert not safe_name(name)
    p=tmp_path/'bad.tar.gz';malicious_archive(p,name)
    with pytest.raises(ValueError):verify(p)


def test_archive_preserves_evidence_excludes_dependencies_and_links(tmp_path):
    root=tmp_path/'project';root.mkdir()
    paths={'runs/a/evaluation/build/stdout.log':b'build evidence',
           'runs/a/workspace/src/a.py':b'print(1)\n',
           'runs/a/workspace/build/bundle.js':b'generated',
           'runs/a/workspace/node_modules/secret':b'dependency',
           'runs/a/auth.json':b'credential'}
    for name,data in paths.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    (root/'runs/outside').symlink_to(tmp_path,target_is_directory=True)
    archive=tmp_path/'results.tar.gz';manifest=create(archive,root,['runs'])
    names={x['path'] for x in manifest['files']}
    assert names=={'runs/a/evaluation/build/stdout.log','runs/a/workspace/src/a.py'}
    assert verify(archive)['files']==manifest['files']
    destination=tmp_path/'restored';extract(archive,destination)
    assert (destination/'runs/a/evaluation/build/stdout.log').read_bytes()==b'build evidence'
    with pytest.raises(FileExistsError):extract(archive,destination)
    with pytest.raises(FileExistsError):create(archive,root,['runs'])


def test_manifest_corruption_and_symlinks_rejected(tmp_path):
    p=tmp_path/'bad.tar.gz';malicious_archive(p,'link',tarfile.SYMTYPE)
    with pytest.raises(ValueError):verify(p)
    with tarfile.open(p,'w:gz') as tar:
        data=b'wrong';item=tarfile.TarInfo('file');item.size=len(data);tar.addfile(item,io.BytesIO(data))
        data=json.dumps({'schema_version':1,'files':[{'path':'file','bytes':5,'sha256':'0'*64}]}).encode()
        item=tarfile.TarInfo('ARCHIVE_MANIFEST.json');item.size=len(data);tar.addfile(item,io.BytesIO(data))
    with pytest.raises(ValueError,match='mismatch'):verify(p)


def test_html_data_cannot_close_script_and_rebuild_is_deterministic(tmp_path):
    data={'message':'</script><script>alert("x")</script> & <html>', 'generated_at':'fixed'}
    p=render(data,tmp_path/'report');first=p.read_bytes()
    assert b'<script>alert' not in first
    assert b'\\u003c/script\\u003e' in first
    assert json.loads((p.parent/'data.json').read_text())==data
    render(data,p.parent);assert p.read_bytes()==first


def test_actor_cost_includes_simulated_user_and_workers_but_not_review():
    r={'usage_by_role':{'user':{'estimated_api_cost_usd':1,'input_tokens':2},'agent':{'estimated_api_cost_usd':3},
                       'worker':{'estimated_api_cost_usd':4,'partial_usage_turns':1},'reviewer':{'estimated_api_cost_usd':100}}}
    a=actors(r);assert a['estimated_api_cost_usd']==8;assert a['input_tokens']==2;assert a['partial']
