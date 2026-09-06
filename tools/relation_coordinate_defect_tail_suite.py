"""Fixed short inventory. No full-tail dispatch before all 90 controls pass."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

CASES=[(s,l,t,n) for s in ('k4_internal','k4_boosted') for l in range(5)
       for t in (0,8,32) for n in (1,4,16)]


def gate(reports):
    assert len(reports)==90
    assert {(r['scenario'],r['level'],r['start_step'],r['block_steps']) for r in reports}==set(CASES)
    passed=0
    for r in reports:
        assert r['precision']==96 and r['verifier_bits']==512
        assert (r['packet_intervals'],r['relation_intervals'],r['matrix_slots'])==(24,36,1872)
        assert r['historical_noise_symbols']==0 and r['promotion']=='NO_PROMOTION'
        assert r['selected_precision'] is None and not r['physical_budgets_certified']
        if r['status']=='withheld_block_contained':
            assert r['reason'] is None and r['complete_steps']==r['block_steps']
            assert r['withheld_checks']==3*r['block_steps']
            passed+=1
        else:
            assert r['status']=='certificate_inconclusive' and r['reason'] in (
                'force_cell','domain_enclosure','verifier_exponent_limit','verifier_resource_limit')
    return dict(eligible=passed==90,blocks_passed=passed,blocks_total=90,
        stage_checks=sum(r['withheld_checks'] for r in reports),promotion='NO_PROMOTION')


def run(inputs,output):
    output.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1]
    def one(case):
        s,l,t,n=case;name=f'{s}-L{l}-start{t}-steps{n}'
        payload=output/(name+'.json')
        command=[sys.executable,str(repo/'reference/relation_coordinate_defect_tail.py'),str(inputs),
                 '--scenario',s,'--level',str(l),'--start',str(t),'--steps',str(n)]
        with payload.open('x') as out,(output/(name+'.stderr')).open('x') as err:
            try: code=subprocess.run(command,stdout=out,stderr=err,timeout=900,
                env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')).returncode
            except subprocess.TimeoutExpired: code=None
        receipt=dict(case=list(case),exit_code=code,output_sha256=hashlib.sha256(payload.read_bytes()).hexdigest())
        (output/(name+'.receipt.json')).write_text(json.dumps(receipt,sort_keys=True)+'\n')
        assert code==0, f'preserved failing subprocess {case}'
        report=json.loads(payload.read_text())
        print(json.dumps(dict(case=case,status=report['status'],reason=report['reason'],
                              checks=report['withheld_checks'])),flush=True)
        return report
    with ThreadPoolExecutor(max_workers=4) as pool: reports=list(pool.map(one,CASES))
    result=gate(reports)
    (output/'gate.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    (output/'inventory.json').write_text(json.dumps(CASES,separators=(',',':'))+'\n')
    print(json.dumps(result,sort_keys=True),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();run(a.inputs.resolve(),a.output.resolve())
