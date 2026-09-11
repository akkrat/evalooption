import json,sys
from pathlib import Path
from unittest.mock import patch
import pytest
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent.parent))
import continue_runner as runner


def fixture(root,multiple=False):
    source=root/'original';tree=source/'workspace';tree.mkdir(parents=True)
    (tree/'source.py').write_text('original partial work')
    task={'id':'fixture','project':'Fixture project','task':'Finish existing change','complexity':'small','source_roots':['sample'],'test_targets':['tests']}
    stages=['execute','execute-worker3','execute-worker3-worker4']
    turns=[{'index':0,'role':'user','stage':'initial','session':'user-id'}]+[{'index':i+1,'role':'agent','stage':s,'session':'session-'+s} for i,s in enumerate(stages)]
    data={'manifest.json':{'task':task,'approach':'gennady','fingerprint':'old'},
          'result.json':{'status':'budget_exhausted','dispatch_count':4,'stages':[{'stage':'setup','seconds':9999,'response':{'status':'done','message':'Setup complete','dispatches':[]}}]},
          'turns.json':turns,'conversation.json':[{'kind':'initial','user_reply':'Original task','shown_to_user':''}]}
    for i,stage in enumerate(stages[:-1]):data[f'turns/{i+1:03d}-agent-{stage}/response.json']={'status':'dispatch','message':'Waiting','dispatches':['worker assignment']*(2 if multiple else 1)}
    for name,value in data.items():
        p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))
    return source,task


def test_resume_leaf_then_each_parent_and_original_user(tmp_path):
    source,task=fixture(tmp_path);calls=[]
    class FakeCodex:
        def __init__(self,*args):self.turns=[];self.dispatch_count=0
        def call(self,role,cwd,prompt,session=None,stage='',**kwargs):
            calls.append((role,stage,session,prompt));self.turns.append({'role':role,'seconds':1,'usage':{},'estimated_api_cost_usd':0})
            if role=='reviewer':message=json.dumps({k:{'score':3,'evidence':'fixture'} for k in ['maintainability','readability','test_quality','performance','security']})
            else:message='handoff-'+stage
            return session or 'new',{'status':'done','message':message,'dispatches':[]}
    v=tmp_path/'validation-v2/fixture/validation.json';v.parent.mkdir(parents=True);v.write_text('{"valid":true}')
    grade={k:{} for k in ['hidden_counts','candidate_test_counts','candidate_added_tests']};grade.update(changed_line_coverage_percent=100,regressions=[])
    settings=json.loads((HERE.parent.parent/'evaluation.json').read_text())
    with patch.object(runner,'Codex',FakeCodex),patch.object(runner,'CACHE',tmp_path),patch.object(runner,'fingerprint',return_value='test'),patch.object(runner,'stages',return_value=[('setup','Setup {task}',True),('execute','Execute {task}',False)]),patch.object(runner,'changes',return_value=[]),patch.object(runner,'git',return_value=''),patch.object(runner,'grade',return_value=grade):
        result=runner.run_one(task,'gennady',tmp_path/'continued',settings,source)
    assert result['status']=='completed',result['error']
    assert [c[1] for c in calls[:3]]==['execute-worker3-worker4','execute-worker3','execute']
    assert [c[2] for c in calls[:3]]==['session-'+c[1] for c in calls[:3]]
    assert 'handoff-execute-worker3-worker4' in calls[1][3]
    assert 'handoff-execute-worker3' in calls[2][3]
    assert calls[3][:3]==('user','completion','user-id')
    assert result['user_interactions']==1 and result['implementation_seconds']==3
    assert (source/'workspace/source.py').read_text()=='original partial work'


def test_reject_ambiguous_dispatch_before_copy(tmp_path):
    source,task=fixture(tmp_path,multiple=True)
    with pytest.raises(ValueError,match='one unreturned worker'):runner.prepare_recovery(task,'gennady',source,tmp_path/'copy')
    assert not (tmp_path/'copy').exists()
