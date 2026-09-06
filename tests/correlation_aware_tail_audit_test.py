import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import correlation_aware_tail_audit as audit


class AuditTests(unittest.TestCase):
    def fixture(self, root, forged=False):
        records = []
        for candidate in ('B', 'C'):
            for scenario in ('k4_internal', 'k4_boosted'):
                for level in range(5):
                    name = f'{candidate}-{scenario}-L{level}'
                    data = dict(candidate=candidate, scenario=scenario, level=level,
                        start_step=0, requested_block_steps=None, joint_withheld_stage_checks=0,
                        status='certificate_inconclusive', reason='verifier_memory_budget',
                        counters=dict(cumulative_cells=1, max_live_cells=1, splits=[]),
                        symbols_created=100, physical_budgets_certified=forged,
                        selected_precision=None, promotion='NO_PROMOTION', step=2, stage='first_kick')
                    payload = json.dumps(data).encode()
                    (root/(name+'.json')).write_bytes(payload)
                    record = dict(case=[candidate, scenario, level], status='completed', exit_code=0,
                                  output_sha256=hashlib.sha256(payload).hexdigest(),
                                  **{k: data[k] for k in ('reason', 'step', 'stage', 'symbols_created')})
                    (root/(name+'.receipt.json')).write_text(json.dumps(record))
                    records.append(record)
        (root/'inventory.json').write_text(json.dumps(records))
        (root/'launch.json').write_text(json.dumps(dict(precision_target=96,
            reference_truth='exact_rational_KDK_not_B256', gate=dict(joint_stage_checks=1890))))
        return records

    def test_complete_resource_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            self.assertEqual(len(audit.full_records(root)), 20)

    def test_forged_budget_pass_rejected_even_with_matching_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, forged=True)
            with self.assertRaises(AssertionError):
                audit.full_records(root)

    def test_omitted_full_case_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            records = self.fixture(root)
            (root/'inventory.json').write_text(json.dumps(records[:-1]))
            with self.assertRaises(AssertionError):
                audit.full_records(root)


if __name__ == '__main__':
    unittest.main()
