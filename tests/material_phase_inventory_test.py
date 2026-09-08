"""Independent record eligibility mutations for complete material parity."""
import copy
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import material_phase_parity as m
r=json.loads(Path(sys.argv[1]).read_text());m.report_check(r)
mutations=[('missing_case',lambda x:x['rows'].pop()),('duplicate_case',lambda x:x['rows'].__setitem__(1,x['rows'][0])),
 ('neutral_omitted',lambda x:x['rows'][0].__setitem__('neutral_parity',False)),('neutral_restart_omitted',lambda x:x['rows'][0].__setitem__('neutral_resume',False)),
 ('final_material_omitted',lambda x:x['rows'][0].__setitem__('final_state_replay',False)),('checkpoint_omitted',lambda x:x['rows'][0].__setitem__('checkpoint_suffix',False)),
 ('twin_omitted',lambda x:x['rows'][0].__setitem__('twins',False)),('atomic_omitted',lambda x:x['negatives'][0].__setitem__('atomic',False)),
 ('shortened_horizon',lambda x:x['rows'][0].__setitem__('steps',1)),('wrong_parent',lambda x:x.__setitem__('parent','wrong')),
 ('runtime_enabled_by_default',lambda x:x.__setitem__('runtime_disabled',False)),('incomplete_invocations',lambda x:x.__setitem__('invocations',254)),
 ('promotion',lambda x:x.__setitem__('promotion','PROMOTION'))]
for name,mutate in mutations:
    x=copy.deepcopy(r);mutate(x)
    try:m.report_check(x)
    except (AssertionError,KeyError):pass
    else:raise AssertionError(('record mutation escaped',name))
print(json.dumps(dict(status='PASS',rejected=[name for name,_ in mutations]),sort_keys=True))
