"""Fresh-bundle verification; defaults to replaying all new withheld blocks.

Does not replay the old full rational prefixes or memory-exhaustion pilots.
Those scopes are distinct from authenticated records and withheld replay.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

import bounded_phase_tail_verify as parent_verify
import correlation_aware_tail_bundle as bundle
import correlation_aware_dependency_probe as dependency
from correlation_aware_tail_gate import check as withheld_gate


def verify(root, records_only=False):
    identity = bundle.check(root)
    parent = root/'parent'
    historical = parent_verify.verify(parent/'inputs', parent/'evidence')
    source = root/'source'
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for name in ('bounded_phase_tail_test.py', 'correlation_aware_tail_test.py',
                 'correlation_aware_tail_observers_test.py', 'correlation_aware_tail_gate_test.py',
                 'correlation_aware_binary64_cells_test.py', 'correlation_aware_affine_image_test.py',
                 'correlation_aware_tail_audit_test.py'):
        subprocess.run([sys.executable, str(source/'tests'/name)], cwd=source, env=env, check=True)
    expected = json.loads((root/'evidence/preliminary/matched-dependency-probe.json').read_text())
    actual = [dependency.probe(parent/'inputs', scenario, level)
              for scenario in ('k4_internal', 'k4_boosted') for level in range(5)]
    assert actual == expected
    replayed = 0
    replay_directory = None
    if not records_only:
        # Keep receipts even if replay fails; never erase a failed attempt.
        temp = Path(tempfile.mkdtemp(prefix='mls-correlated-withheld-'))
        replay_directory = str(temp)
        output = temp/'replay'
        with (temp/'runner.log').open('w') as log:
            subprocess.run([sys.executable, str(source/'tools/correlation_aware_tail_withheld.py'),
                            str(parent/'inputs'), str(output)], cwd=source, env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        replayed = withheld_gate(output)['joint_stage_checks']
        for scenario in ('k4_internal', 'k4_boosted'):
            for level in range(5):
                for start in (0, 8, 32):
                    for length in (1, 4, 16):
                        name = f'{scenario}-L{level}-start{start}-steps{length}.json'
                        assert (output/name).read_bytes() == (root/'evidence/withheld'/name).read_bytes(), name
    # Detect any accidental generated payload, including bytecode.
    bundle.check(root)
    result = json.loads((root/'evidence/result.json').read_text())
    return dict(identity=identity, parent_record_verification=historical,
                new_unit_tests=33, parent_unit_tests=10, independent_affine_stage_checks=30,
                matched_dependency_controls=10, new_withheld_stage_checks_replayed=replayed,
                preserved_withheld_replay_directory=replay_directory,
                records_only=records_only, old_full_prefix_replay=False,
                memory_exhaustion_pilots_replayed=False,
                authenticated_primary_and_repeat_pilots=40,
                raw_memory_execution_records_byte_identical=result['raw_full_execution_records_byte_identical'],
                decision=result['decision'], selected_precision=None,
                physical_budgets_certified=False, promotion='NO_PROMOTION')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('root', type=Path)
    p.add_argument('--records-only', action='store_true')
    a = p.parse_args()
    print(json.dumps(verify(a.root.resolve(), a.records_only), sort_keys=True))
