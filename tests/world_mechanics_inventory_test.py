import copy
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import world_mechanics_parity as w

def run(r):
    expected=w.report_check(r);mutations=[]
    def bad(name,change):
        x=copy.deepcopy(r);change(x)
        try:w.report_check(x)
        except (AssertionError,KeyError):mutations.append(name)
        else:raise AssertionError(('invalid evidence accepted',name))
    bad('omitted_case',lambda x:x['rows'].pop())
    bad('wrong_case',lambda x:x['rows'][0].update(case='other'))
    bad('wrong_steps',lambda x:x['rows'][0].update(steps=0))
    for field in ('twins','checkpoint_suffix','world_contracts'):
        bad(field,lambda x:x['rows'][0].update({field:False}))
    bad('domain_pass',lambda x:x['negatives'][0].update(atomic=False))
    bad('wrong_parent',lambda x:x.update(parent='wrong'))
    bad('promotion',lambda x:x.update(promotion='PROMOTED'))
    bad('runtime_enabled_default',lambda x:x.update(runtime_disabled=False))
    x=copy.deepcopy(r);x['rows'][0]['stream_sha256']='0'*64
    assert w.report_check(x)!=expected;mutations.append('changed_scientific_stream')
    print(json.dumps(dict(status='PASS',rejected_mutations=mutations),sort_keys=True))
if __name__=='__main__':run(json.loads(Path(sys.argv[1]).read_text()))
