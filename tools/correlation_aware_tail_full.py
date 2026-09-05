"""Guarded B/C state-inclusion pilots after the complete withheld inventory.

State inclusion alone is not a physical-budget certificate or B96 selection.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from correlation_aware_tail_gate import check


def run_case(repo, inputs, output, case):
    candidate, scenario, level = case
    name = f'{candidate}-{scenario}-L{level}'
    result, errors = output/(name+'.json'), output/(name+'.stderr')
    command = [sys.executable, str(repo/'reference/correlation_aware_tail.py'),
               str(inputs), '--scenario', scenario, '--level', str(level)]
    if candidate == 'C':
        command.append('--branching')
    with result.open('x') as stdout, errors.open('x') as stderr:
        try:
            process = subprocess.run(command, stdout=stdout, stderr=stderr,
                                     env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=900)
            status, code = ('completed' if process.returncode == 0 else 'process_failed'), process.returncode
        except subprocess.TimeoutExpired:
            status, code = 'wall_budget_exhausted', None
    record = dict(case=list(case), status=status, exit_code=code, command=command,
                  output_sha256=hashlib.sha256(result.read_bytes()).hexdigest(),
                  physical_budgets_certified=False, selected_precision=None, promotion='NO_PROMOTION')
    if status == 'completed':
        payload = json.loads(result.read_text())
        assert payload['requested_block_steps'] is None and payload['start_step'] == 0
        assert payload['joint_withheld_stage_checks'] == 0
        assert not payload['physical_budgets_certified'] and payload['selected_precision'] is None
        record.update(certificate_status=payload['status'], reason=payload['reason'],
                      step=payload['step'], stage=payload['stage'],
                      symbols_created=payload['symbols_created'])
    (output/(name+'.receipt.json')).write_text(json.dumps(record, sort_keys=True, indent=2)+'\n')
    print(json.dumps({k: v for k, v in record.items() if k != 'command'}, sort_keys=True), flush=True)
    return record


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('inputs', type=Path)
    p.add_argument('withheld', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    # Check BEFORE creating output or starting any subprocess.
    gate = check(a.withheld)
    repo = Path(__file__).resolve().parents[1]
    subprocess.run(['git', 'diff', '--quiet', 'HEAD'], cwd=repo, check=True)
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    a.output.mkdir(parents=True, exist_ok=False)
    (a.output/'launch.json').write_text(json.dumps(dict(source_sha=source, gate=gate,
        withheld_inventory_sha256=hashlib.sha256((a.withheld/'inventory.json').read_bytes()).hexdigest(),
        precision_target=96, reference_truth='exact_rational_KDK_not_B256',
        physical_observers='pending', promotion='NO_PROMOTION'), sort_keys=True, indent=2)+'\n')
    cases = [(candidate, s, level) for candidate in ('B', 'C')
             for s, levels in (('k4_internal', (1, 2, 3, 4, 0)), ('k4_boosted', range(5)))
             for level in levels]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda c: run_case(repo, a.inputs.resolve(), a.output, c), cases))
    (a.output/'inventory.json').write_text(json.dumps(records, sort_keys=True, indent=2)+'\n')
    if any(r['status'] == 'process_failed' for r in records):
        raise SystemExit('Preserved subprocess failure needs independent classification.')
