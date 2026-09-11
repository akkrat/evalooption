"""Small deterministic checks for replay boundaries and coverage accounting."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import adapter

def test_replay_preserves_baseline_tests_and_rejects_source_symlink(tmp_path,monkeypatch):
    candidate=tmp_path/'candidate';candidate.mkdir()
    (candidate/'packages/p').mkdir(parents=True)
    (candidate/'packages/p/code.ts').write_text('export const answer=42;')
    (candidate/'packages/p/code.test.ts').write_text('weakened test')
    (candidate/'openspec').mkdir();(candidate/'openspec/design.md').write_text('process artifact')
    def prepare(tree):
        (tree/'packages/p').mkdir(parents=True)
        (tree/'packages/p/code.test.ts').write_text('original test')
    monkeypatch.setattr(adapter,'prepare',prepare)
    monkeypatch.setattr(adapter,'changes',lambda _:['packages/p/code.ts','packages/p/code.test.ts','openspec/design.md'])
    monkeypatch.setattr(adapter,'git',lambda *args:'packages/p/code.test.ts\n')
    monkeypatch.setattr(adapter.subprocess,'check_output',lambda *a,**k:b'original test')
    target=tmp_path/'replay';r=adapter.replay(candidate,target,restore_tests=True)
    assert (target/'packages/p/code.ts').read_text()=='export const answer=42;'
    assert (target/'packages/p/code.test.ts').read_text()=='original test'
    assert not (target/'openspec').exists()
    assert r['not_replayed']==['openspec/design.md']
    (candidate/'packages/p/code.ts').unlink();(candidate/'packages/p/code.ts').symlink_to(tmp_path/'hidden')
    import pytest
    with pytest.raises(ValueError,match='symlink'):adapter.replay(candidate,tmp_path/'bad')

def test_coverage_unions_overlapping_statement_lines_and_excludes_tests(tmp_path):
    tree=tmp_path/'tree';output=tmp_path/'coverage'
    filename=str(tree/'packages/p/code.ts');testname=str(tree/'packages/p/code.test.ts')
    for label,count in [('core',0),('web',1)]:
        p=output/label/'coverage';p.mkdir(parents=True)
        data={'statementMap':{'0':{'start':{'line':1},'end':{'line':2}},'1':{'start':{'line':2},'end':{'line':3}}},'s':{'0':count,'1':0}}
        (p/'coverage-final.json').write_text(json.dumps({filename:data,testname:data}))
    r=adapter.coverage_metrics(tree,output,['packages/p/code.ts','packages/p/code.test.ts'])
    assert r['changed_file_statement_lines_total']==3
    assert r['changed_file_statement_lines_covered']==2
    assert round(r['changed_file_statement_line_coverage_percent'],2)==66.67
