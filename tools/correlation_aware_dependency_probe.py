"""Matched dependency control on identical rounded affine first-step inputs."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'reference'))
import correlation_aware_tail as v
import correlation_aware_binary64_cells as independent


def cell_bits(box):
    try:
        value = v.control.float_cell(box)
        independent.verify(box, value)
        return v.struct.pack('>d', value).hex()
    except v.control.Inconclusive:
        return None


def probe(inputs, scenario, level):
    model = v.frozen.load_models(inputs/'raw-a')['k4']
    rows = [r for r in v.frozen.rows(inputs/'parent-explicit-fractional/raw-a/initial_states.csv')
            if r['scenario_id'] == scenario]
    exact = v.frozen.rational_from_parent_rows(rows)
    state = {p.identifier: ([v.Affine.make(x) for x in p.x], [v.Affine.make(x) for x in p.p])
             for p in exact.packets}
    arithmetic = v.Arithmetic()
    cell = v.Cell(arithmetic.round_state(state), {})
    dt = v.frozen.TIMESTEPS_RAW[level]
    cell = v.drift(model, v.kick(model, cell, dt//2, arithmetic), dt, arithmetic)
    differences = []
    for relation in model.relations:
        for axis in range(3):
            a = cell.state[relation.first_id][0][axis]
            b = cell.state[relation.second_id][0][axis]
            shared = (b-a).scale(v.frozen.LQ).bounds(cell.domains)
            dropped = (b.bounds(cell.domains)-a.bounds(cell.domains)).scale(v.frozen.LQ)
            shared_bits, dropped_bits = cell_bits(shared), cell_bits(dropped)
            if shared_bits is not None and dropped_bits is None:
                differences.append(dict(relation=relation.index, axis=axis,
                    shared_interval=[str(shared.lo), str(shared.hi)],
                    independent_interval=[str(dropped.lo), str(dropped.hi)],
                    shared_bits=shared_bits, independent_bits=None))
    assert differences, 'matched dependency mutation did not reintroduce ambiguity'
    return dict(scenario=scenario, level=level, stage='step_1_second_kick_input',
                identical_input_affine_forms=True, changed_only='shared_vs_independent_subtraction',
                differences=differences, full_tail_claim=False, promotion='NO_PROMOTION')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('inputs', type=Path)
    a = p.parse_args()
    print(json.dumps([probe(a.inputs, s, l) for s in ('k4_internal', 'k4_boosted')
                     for l in range(5)], sort_keys=True, indent=2))
