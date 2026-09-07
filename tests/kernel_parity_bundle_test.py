"""Fail-closed inventory and exact-source CI receipt mutations."""
import copy
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import kernel_parity_bundle as b

def run(report):
    expected=b.report_check(report);count=0
    def rejected(value):
        nonlocal count
        try:b.report_check(value)
        except (AssertionError,KeyError):count+=1
        else:raise AssertionError('incomplete/false inventory accepted')
    r=copy.deepcopy(report);r['full'].pop();rejected(r)
    r=copy.deepcopy(report);r['full'][0]['case']='invented-case';rejected(r)
    r=copy.deepcopy(report);r['full'][0]['stage_bytes']=False;rejected(r)
    r=copy.deepcopy(report);r['controls']['rows'][0]['event_hashes']=False;rejected(r)
    r=copy.deepcopy(report);r['replay'][0]['passed']=False;rejected(r)
    r=copy.deepcopy(report);r['promotion']='PROMOTED';rejected(r)
    ci=dict(headSha='abc',status='completed',conclusion='success',jobs=[dict(name=n,status='completed',conclusion='success') for n in sorted(b.JOBS)])
    b.ci_check(ci,'abc')
    for field,value in [('headSha','wrong'),('conclusion','failure'),('status','in_progress')]:
        altered=copy.deepcopy(ci);altered[field]=value
        try:b.ci_check(altered,'abc')
        except AssertionError:count+=1
        else:raise AssertionError('invalid CI accepted')
    altered=copy.deepcopy(ci);altered['jobs'].pop()
    try:b.ci_check(altered,'abc')
    except AssertionError:count+=1
    else:raise AssertionError('missing CI job accepted')
    r=copy.deepcopy(report);r['replay'][0]['twin_sha256']='0'*64
    assert b.report_check(r)!=expected;count+=1
    print(json.dumps(dict(status='PASS',rejected_mutations=count),sort_keys=True))

if __name__=='__main__':run(json.loads(Path(sys.argv[1]).read_text()))
