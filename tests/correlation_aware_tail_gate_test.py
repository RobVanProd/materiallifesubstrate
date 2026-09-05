import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import correlation_aware_tail_gate as gate


class GateTests(unittest.TestCase):
    def fixture(self, directory):
        inventory = []
        for scenario in ('k4_internal', 'k4_boosted'):
            for level in range(5):
                for start in (0, 8, 32):
                    for length in (1, 4, 16):
                        name = f'{scenario}-L{level}-start{start}-steps{length}'
                        report = dict(scenario=scenario, level=level, start_step=start,
                                      requested_block_steps=length, candidate='C', reason=None,
                                      status='state_enclosure_only_physical_observers_pending',
                                      joint_withheld_stage_checks=3*length,
                                      physical_budgets_certified=False, selected_precision=None)
                        payload = json.dumps(report).encode()
                        (directory/(name+'.json')).write_bytes(payload)
                        receipt = dict(case=[scenario, level, start, length], status='completed',
                                       exit_code=0, output_sha256=hashlib.sha256(payload).hexdigest())
                        (directory/(name+'.receipt.json')).write_text(json.dumps(receipt))
                        inventory.append(receipt)
        (directory/'inventory.json').write_text(json.dumps(inventory))
        return inventory

    def test_complete_inventory_and_missing_case(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            inventory = self.fixture(p)
            self.assertEqual(gate.check(p)['joint_stage_checks'], 1890)
            (p/'inventory.json').write_text(json.dumps(inventory[:-1]))
            with self.assertRaises(AssertionError):
                gate.check(p)

    def test_exhaustion_cannot_satisfy_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            inventory = self.fixture(p)
            inventory[0]['status'] = 'wall_budget_exhausted'
            (p/'inventory.json').write_text(json.dumps(inventory))
            with self.assertRaises(AssertionError):
                gate.check(p)

    def test_payload_substitution_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            self.fixture(p)
            (p/'k4_internal-L0-start0-steps1.json').write_text('{}')
            with self.assertRaises(AssertionError):
                gate.check(p)


if __name__ == '__main__':
    unittest.main()
