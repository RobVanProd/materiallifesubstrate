"""Registered short eligibility corpus; deliberately has no full-tail launch."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
from defect_recurrence_tail_check import full_tail_eligible


def run(inputs,output):
    output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    cases=[(s,l,t,n) for s in ('k4_internal','k4_boosted') for l in range(5)
           for t in (0,8,32) for n in (1,4,16)]
    def one(case):
        s,l,t,n=case
        name=f'{s}-L{l}-start{t}-steps{n}'
        command=[sys.executable,str(repo/'reference/defect_recurrence_tail.py'),str(inputs),
                 '--scenario',s,'--level',str(l),'--start',str(t),'--steps',str(n)]
        payload=output/(name+'.json')
        with payload.open('x') as stdout,(output/(name+'.stderr')).open('x') as stderr:
            try:
                result=subprocess.run(command,stdout=stdout,stderr=stderr,
                    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),timeout=900)
                code=result.returncode
            except subprocess.TimeoutExpired:
                code=None
        receipt=dict(case=list(case),exit_code=code,output_sha256=hashlib.sha256(payload.read_bytes()).hexdigest())
        (output/(name+'.receipt.json')).write_text(json.dumps(receipt,sort_keys=True)+'\n')
        assert code==0, f'failed short subprocess: {case}; preserve outputs and stop'
        report=json.loads(payload.read_text())
        print(json.dumps(dict(case=case,status=report['status'],reason=report['reason'],checks=report['withheld_checks'])),flush=True)
        return report
    with ThreadPoolExecutor(max_workers=4) as pool:
        reports=list(pool.map(one,cases))
    gate=full_tail_eligible(reports)
    (output/'gate.json').write_text(json.dumps(gate,sort_keys=True,indent=2)+'\n')
    (output/'inventory.json').write_text(json.dumps(cases,separators=(',',':'))+'\n')
    print(json.dumps(gate,sort_keys=True),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();run(a.inputs.resolve(),a.output.resolve())
