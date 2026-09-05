"""Run the preregistered withheld inventory; never launches full tails."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def run_case(repo, inputs, output, case):
    scenario, level, start, length = case
    name = f'{scenario}-L{level}-start{start}-steps{length}'
    result = output / (name+'.json')
    errors = output / (name+'.stderr')
    receipt = output / (name+'.receipt.json')
    command = [sys.executable, str(repo/'reference/correlation_aware_tail.py'), str(inputs),
               '--scenario', scenario, '--level', str(level), '--start-step', str(start),
               '--block-steps', str(length), '--branching']
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    with result.open('x') as stdout, errors.open('x') as stderr:
        try:
            process = subprocess.run(command, stdout=stdout, stderr=stderr, env=env, timeout=900)
            status = 'completed' if process.returncode == 0 else 'process_failed'
            code = process.returncode
        except subprocess.TimeoutExpired:
            status, code = 'wall_budget_exhausted', None
    record = dict(case=list(case), status=status, exit_code=code,
                  command=command, promotion='NO_PROMOTION', full_tail=False,
                  output_sha256=hashlib.sha256(result.read_bytes()).hexdigest())
    receipt.write_text(json.dumps(record, sort_keys=True, indent=2)+'\n')
    if status == 'completed':
        data = json.loads(result.read_text())
        record['joint_checks'] = data['joint_withheld_stage_checks']
        record['certificate_status'] = data['status']
        record['reason'] = data['reason']
    print(json.dumps(record, sort_keys=True), flush=True)
    return record


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('inputs', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    a.output.mkdir(parents=True, exist_ok=False)
    cases = [(s, level, start, length) for s in ('k4_internal', 'k4_boosted')
             for level in (1, 2, 3, 4, 0) for start in (0, 8, 32) for length in (1, 4, 16)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda c: run_case(repo, a.inputs.resolve(), a.output, c), cases))
    (a.output/'inventory.json').write_text(json.dumps(records, sort_keys=True, indent=2)+'\n')
    assert len(records) == 90
    if any(r['status'] == 'process_failed' for r in records):
        raise SystemExit('A withheld subprocess failed: inspect preserved receipts before any tail.')
