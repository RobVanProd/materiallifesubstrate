"""Full inventory after the independently audited short gate."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from relation_coordinate_defect_tail_suite import gate


def run(inputs,invariants,short,output):
    reports=[json.loads(p.read_text()) for p in sorted(short.glob('k4*.json')) if not p.name.endswith('.receipt.json')]
    assert gate(reports)['eligible']
    assert gate(reports)==json.loads((short/'gate.json').read_text())
    output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    def one(case):
        s,l=case;name=f'{s}-L{l}';payload=output/(name+'.json')
        command=[sys.executable,str(repo/'reference/relation_coordinate_defect_full.py'),str(inputs),str(invariants),
                 '--scenario',s,'--level',str(l),'--short-gate',str(short/'gate.json')]
        with payload.open('x') as out,(output/(name+'.stderr')).open('x') as err:
            try:code=subprocess.run(command,stdout=out,stderr=err,timeout=3600,
                env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')).returncode
            except subprocess.TimeoutExpired:code=None
        (output/(name+'.receipt.json')).write_text(json.dumps(dict(case=list(case),exit_code=code,
            output_sha256=hashlib.sha256(payload.read_bytes()).hexdigest()),sort_keys=True)+'\n')
        assert code==0,f'preserved failing full subprocess {case}'
        r=json.loads(payload.read_text())
        print(json.dumps(dict(case=case,status=r['status'],reason=r['reason'],step=r['step'],stage=r['stage'])),flush=True)
        return r
    cases=[(s,l) for s in ('k4_internal','k4_boosted') for l in range(5)]
    with ThreadPoolExecutor(max_workers=4) as pool:reports=list(pool.map(one,cases))
    (output/'inventory.json').write_text(json.dumps(cases,separators=(',',':'))+'\n')
    print(json.dumps(dict(cases=len(reports),full_horizons=sum(r['full_horizon_certified'] for r in reports))),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('inputs','invariants','short','output'):p.add_argument(name,type=Path)
    a=p.parse_args();run(a.inputs.resolve(),a.invariants.resolve(),a.short.resolve(),a.output.resolve())
