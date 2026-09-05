"""Fail-closed guard for moving from withheld validation to full-tail pilots."""
import argparse
import hashlib
import json
from pathlib import Path


def check(directory):
    inventory = json.loads((directory/'inventory.json').read_text())
    expected = {(s, l, start, length) for s in ('k4_internal', 'k4_boosted')
                for l in range(5) for start in (0, 8, 32) for length in (1, 4, 16)}
    assert len(inventory) == 90
    assert {tuple(r['case']) for r in inventory} == expected
    total = 0
    for entry in inventory:
        scenario, level, start, length = entry['case']
        name = f'{scenario}-L{level}-start{start}-steps{length}'
        assert entry['status'] == 'completed' and entry['exit_code'] == 0
        payload = (directory/(name+'.json')).read_bytes()
        receipt = json.loads((directory/(name+'.receipt.json')).read_text())
        assert receipt['case'] == entry['case']
        assert receipt['output_sha256'] == entry['output_sha256'] == hashlib.sha256(payload).hexdigest()
        report = json.loads(payload)
        assert (report['scenario'], report['level'], report['start_step'], report['requested_block_steps']) == tuple(entry['case'])
        assert report['candidate'] == 'C'
        assert report['reason'] is None
        assert report['status'] == 'state_enclosure_only_physical_observers_pending'
        assert report['joint_withheld_stage_checks'] == length*3
        assert not report['physical_budgets_certified'] and report['selected_precision'] is None
        total += report['joint_withheld_stage_checks']
    assert total == 1890
    return dict(withheld_blocks=90, joint_stage_checks=total,
                full_tail_launch_gate='withheld_inventory_complete',
                physical_budgets_certified=False, promotion='NO_PROMOTION')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('directory', type=Path)
    a = p.parse_args()
    print(json.dumps(check(a.directory), sort_keys=True))
