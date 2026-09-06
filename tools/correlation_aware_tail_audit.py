"""Independent record audit for the inconclusive correlation-aware experiment."""
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path

from correlation_aware_tail_gate import check as withheld_gate

PARENT = '761c2dd6505f99a953f143a43221393370feebd0'
PARENT_MANIFEST = '60eb5920fdb10076df1c7ce899f1df78e1f98d432759d33e8914398925a9593c'
DECISION = 'stop_correlation_aware_certificate_inconclusive'


def read(path):
    return json.loads(path.read_text())


def full_records(directory):
    inventory = read(directory/'inventory.json')
    expected = {(c, s, l) for c in ('B', 'C') for s in ('k4_internal', 'k4_boosted') for l in range(5)}
    assert len(inventory) == 20 and {tuple(r['case']) for r in inventory} == expected
    result = {}
    for record in inventory:
        candidate, scenario, level = record['case']
        name = f'{candidate}-{scenario}-L{level}'
        payload = (directory/(name+'.json')).read_bytes()
        assert record == read(directory/(name+'.receipt.json'))
        assert record['status'] == 'completed' and record['exit_code'] == 0
        assert hashlib.sha256(payload).hexdigest() == record['output_sha256']
        data = json.loads(payload)
        assert (data['candidate'], data['scenario'], data['level']) == tuple(record['case'])
        assert data['start_step'] == 0 and data['requested_block_steps'] is None
        assert data['joint_withheld_stage_checks'] == 0
        assert data['status'] == 'certificate_inconclusive'
        assert data['reason'] == 'verifier_memory_budget'
        assert data['counters'] == dict(cumulative_cells=1, max_live_cells=1, splits=[])
        assert data['symbols_created'] < 4096
        assert data['physical_budgets_certified'] is False
        assert data['selected_precision'] is None and data['promotion'] == 'NO_PROMOTION'
        for key in ('reason', 'step', 'stage', 'symbols_created'):
            assert record[key] == data[key]
        assert 1 <= data['step'] < 16*(16*2**level)
        assert data['stage'] in ('first_kick', 'drift', 'second_kick')
        result[tuple(record['case'])] = data
    launch = read(directory/'launch.json')
    assert launch['precision_target'] == 96
    assert launch['reference_truth'] == 'exact_rational_KDK_not_B256'
    assert launch['gate']['joint_stage_checks'] == 1890
    return result


def audit(work):
    configuration = read(work/'toolchain.json')
    for key, expected in dict(configured_verifier_bits=512,
                              configured_address_space_bytes=2*1024**3,
                              configured_wall_seconds=900, max_active_symbols=4096,
                              max_live_cells=256, max_cumulative_cells=4096).items():
        assert configuration[key] == expected, f'changed preregistered resource: {key}'
    withheld = withheld_gate(work/'withheld')
    full = full_records(work/'full')
    repeat = full_records(work/'full-repeat')
    differences = []
    tables = []
    for case in sorted(full):
        a, b = full[case], repeat[case]
        changed = {key: [a.get(key), b.get(key)] for key in sorted(set(a)|set(b)) if a.get(key) != b.get(key)}
        if changed:
            # Allocator termination is an operational observation. Preserve it;
            # never silently call unequal raw execution records identical.
            assert set(changed) <= {'symbols_created', 'step', 'stage'}
            differences.append(dict(case=list(case), changed=changed))
        tables.append(dict(candidate=case[0], scenario=case[1], level=case[2],
            stopping_step=a['step'], stopping_stage=a['stage'],
            complete_prior_steps=a['step']-1,
            complete_prior_time_seconds=str(Q(a['step']-1, 16*2**case[2])),
            symbols_created=a['symbols_created'], reason=a['reason']))
    probe = read(work/'preliminary/matched-dependency-probe.json')
    assert len(probe) == 10
    assert {(r['scenario'], r['level']) for r in probe} == {(s, l) for s in ('k4_internal', 'k4_boosted') for l in range(5)}
    for row in probe:
        assert row['identical_input_affine_forms'] is True
        assert row['changed_only'] == 'shared_vs_independent_subtraction'
        assert len(row['differences']) == 1
        d = row['differences'][0]
        assert (d['relation'], d['axis']) == (5, 0)
        assert list(map(Q, d['shared_interval'])) == [Q(), Q()]
        assert d['shared_bits'] == '0000000000000000' and d['independent_bits'] is None
        lo, hi = map(Q, d['independent_interval'])
        assert lo < 0 < hi
    return dict(schema='mls.correlation-aware.result.v1', parent_source=PARENT,
        decision=DECISION, subclass='CERTIFICATION_INCONCLUSIVE', selected_precision=None,
        promotion='NO_PROMOTION', primary_candidate_precision=96,
        withheld_blocks=withheld['withheld_blocks'], joint_withheld_checks=1890,
        matched_dependency_controls=10, full_pilots=20, repeated_full_pilots=20,
        full_tail_budgets_certified=False, bounded_phase_structure_defect_established=False,
        scientific_resource_dispositions_reproduced=20,
        raw_full_execution_records_byte_identical=not differences,
        operational_repeat_differences=differences, full_table=tables,
        required_full_tail_quantities={name:'UNCERTIFIED' for name in (
            'position_representation_error', 'momentum_representation_error',
            'representation_energy_error', 'representation_energy_slope',
            'total_momentum_residual', 'orbital_angular_momentum_residual',
            'relation_centrality_residual', 'boosted_relative_position_error',
            'boosted_relative_momentum_error', 'safe_domain_membership')},
        limitations=[
            'The full pilots certify no full-horizon physical budget; B96 is not selected.',
            'Branching was not required before the resource stop; registered full runs do not demonstrate its effectiveness.',
            'The implementation retains historical affine cache and rounding provenance; its resource stop is not a lower bound on other verifiers.',
            'Raw allocator-stop receipts and deterministic archive materialization are distinct reproducibility claims.',
            'The polynomial observer primitives were tested but not used to manufacture a tail certificate after state inclusion stopped.'])
