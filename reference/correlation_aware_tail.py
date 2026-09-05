"""Verifier-only shared affine state; frozen mechanics are imported unchanged.

This module certifies state inclusion, not a completed physical-budget result.
Exact witness reconstruction is retrospective and never used by propagation.
"""
import argparse
import json
import math
import struct
import time
from dataclasses import dataclass
from fractions import Fraction as Q
from pathlib import Path

import bounded_phase_tail_interval as control
import bounded_fractional_phase_state_oracle as frozen
import correlation_aware_tail_check as independent

MAX_LIVE = 256
MAX_CELLS = 4096
MAX_SYMBOLS = 4096
WALL_SECONDS = 900
MEMORY_BYTES = 2 * 1024**3


class Limit(control.Inconclusive):
    pass


@dataclass(frozen=True)
class Affine:
    center: Q
    coefficients: tuple = ()

    @staticmethod
    def make(center, coefficients=None):
        return Affine(Q(center), tuple(sorted((j, Q(v)) for j, v in
                      (coefficients or {}).items() if v)))

    def scale(self, value):
        return Affine.make(self.center * value,
                           {j: v * value for j, v in self.coefficients})

    def __add__(self, other):
        coefficients = dict(self.coefficients)
        for j, v in other.coefficients:
            coefficients[j] = coefficients.get(j, Q()) + v
        return Affine.make(self.center + other.center, coefficients)

    def __neg__(self):
        return self.scale(-1)

    def __sub__(self, other):
        return self + -other

    def bounds(self, domains):
        lo = hi = self.center
        for j, v in self.coefficients:
            a, b = domains.get(j, (Q(-1), Q(1)))
            lo += min(v*a, v*b)
            hi += max(v*a, v*b)
        # These exact rational sums are outward enclosures without deficits.
        return control.Box(lo, hi)

    def value(self, assignment):
        return self.center + sum((v * assignment[j] for j, v in self.coefficients), Q())


class Arithmetic:
    def __init__(self):
        self.definitions = []
        self.cache = {}

    def round(self, form):
        # Opposite/equal affine expressions share the SAME rounding symbol.
        lead = form.center or next((v for _, v in form.coefficients), Q())
        if lead < 0:
            return -self.round(-form)
        if form in self.cache:
            return self.cache[form]
        c = control.directed(form.center, False)
        coefficients = {j: control.directed(v, False) for j, v in form.coefficients}
        rounded = Affine.make(c, coefficients)
        difference = form - rounded
        slack = control.directed(abs(difference.center) +
                                 sum((abs(v) for _, v in difference.coefficients), Q()), True)
        if slack:
            j = len(self.definitions)
            self.definitions.append((difference, slack))
            coefficients[j] = slack
        result = Affine.make(c, coefficients)
        self.cache[form] = result
        return result

    def witness(self, previous=None):
        # Independently reconstruct ONE simultaneous assignment from exact
        # discarded terms. Propagation has no access to this assignment.
        assignment = dict(previous or {})
        for j in range(len(assignment), len(self.definitions)):
            difference, slack = self.definitions[j]
            assignment[j] = difference.value(assignment) / slack
            assert abs(assignment[j]) <= 1, 'outward coefficient allowance failed'
        return assignment

    def round_state(self, state):
        result = {i: tuple([self.round(a) for a in vector] for vector in pair)
                  for i, pair in state.items()}
        active = {j for pair in result.values() for vector in pair
                  for a in vector for j, _ in a.coefficients}
        if len(active) > MAX_SYMBOLS:
            raise Limit('active_shared_symbol_limit')
        return result


@dataclass
class Cell:
    state: dict
    domains: dict
    path: tuple = ()


class Ambiguous(control.Inconclusive):
    def __init__(self, form, relation, axis):
        super().__init__(f'ambiguous_conversion:relation={relation}:axis={axis}')
        self.form, self.relation, self.axis = form, relation, axis


def offset(state, relation):
    return [b-a for a, b in zip(state[relation.first_id][0], state[relation.second_id][0])]


def evaluate(model, cell):
    geometry = []
    for relation in model.relations:
        r = offset(cell.state, relation)
        control.safe_box(model, relation, [a.bounds(cell.domains) for a in r])
        current = []
        for axis, a in enumerate(r):
            physical = a.scale(frozen.LQ)
            try:
                current.append(control.float_cell(physical.bounds(cell.domains)))
            except control.Inconclusive as error:
                raise Ambiguous(physical, relation.index, axis) from error
        reference = [float(a * frozen.LQ) for a in frozen.reference_offset(model, relation)]
        length, extension = frozen.path_b_geometry(current, reference, relation.rest_length)
        geometry.append((relation, r, length, extension))
    conjugates = []
    for row in model.h:
        value = 0.0
        for coefficient, g in zip(row, geometry):
            value += coefficient*g[3]
        conjugates.append(value)
    return [(a[0], a[1], Q.from_float(a[2]), Q.from_float(g))
            for a, g in zip(geometry, conjugates)]


def kick(model, cell, dt, arithmetic):
    evaluated = evaluate(model, cell)
    out = {i: ([*x], [*p]) for i, (x, p) in cell.state.items()}
    for relation, r, length, conjugate in evaluated:
        alpha = dt * frozen.TQ * conjugate / length * frozen.LQ / frozen.PQ
        for axis, value in enumerate(r):
            impulse = value.scale(alpha)
            out[relation.first_id][1][axis] = out[relation.first_id][1][axis] + impulse
            out[relation.second_id][1][axis] = out[relation.second_id][1][axis] - impulse
    # Compose the exact affine stage BEFORE rounding its coefficients.
    return Cell(arithmetic.round_state(out), cell.domains, cell.path)


def drift(model, cell, dt, arithmetic):
    out = {i: ([a+b.scale(Q(dt, model.masses_raw[i])) for a, b in zip(x, p)], [*p])
           for i, (x, p) in cell.state.items()}
    for relation in model.relations:
        before, after = offset(cell.state, relation), offset(out, relation)
        control.safe_box(model, relation, [a.bounds(cell.domains).hull(b.bounds(cell.domains))
                                           for a, b in zip(before, after)])
    return Cell(arithmetic.round_state(out), cell.domains, cell.path)


def split(cell, ambiguity):
    contributions = [(abs(v)*(cell.domains.get(j, (-1, 1))[1] -
                             cell.domains.get(j, (-1, 1))[0]), j)
                     for j, v in ambiguity.form.coefficients]
    contributions = [(size, j) for size, j in contributions if size]
    if not contributions:
        raise Limit('ambiguous_conversion_without_splittable_generator')
    _, j = min(contributions, key=lambda pair: (-pair[0], pair[1]))
    lo, hi = cell.domains.get(j, (Q(-1), Q(1)))
    mid = (lo + hi) / 2
    children = []
    for side, interval in enumerate(((lo, mid), (mid, hi))):
        domains = dict(cell.domains)
        domains[j] = interval
        children.append(Cell(cell.state, domains, cell.path + ((j, side),)))
    return children, (j, lo, mid, hi)


def advance(model, cells, dt, operation, arithmetic, branching, counters, start):
    pending, out = list(cells), []
    while pending:
        if time.monotonic() - start > WALL_SECONDS:
            raise Limit('verifier_wall_budget')
        cell = pending.pop(0)
        try:
            out.append(operation(model, cell, dt, arithmetic))
        except Ambiguous as ambiguity:
            if not branching:
                raise
            if counters['cumulative_cells'] + 2 > MAX_CELLS:
                raise Limit('cumulative_cell_limit:' + str(ambiguity))
            if len(pending) + len(out) + 2 > MAX_LIVE:
                raise Limit('live_cell_limit:' + str(ambiguity))
            children, coverage = split(cell, ambiguity)
            j, lo, mid, hi = coverage
            independent.check_children(cell, children, j)
            # Exact coverage receipt; midpoint belongs to BOTH closed children.
            assert lo <= mid <= hi
            assert children[0].domains[j] == (lo, mid)
            assert children[1].domains[j] == (mid, hi)
            counters['cumulative_cells'] += 2
            counters['splits'].append([j, str(lo), str(mid), str(hi)])
            pending[0:0] = children
        counters['max_live_cells'] = max(counters['max_live_cells'], len(pending)+len(out))
    return out


def joint_witness(cells, exact, arithmetic, assignment=None):
    assignment = arithmetic.witness() if assignment is None else assignment
    for cell in cells:
        if not all(lo <= assignment[j] <= hi for j, (lo, hi) in cell.domains.items()):
            continue
        if all(cell.state[p.identifier][v][axis].value(assignment) == getattr(p, field)[axis]
               for p in exact.packets for v, field in enumerate(('x', 'p')) for axis in range(3)):
            return True
    return False


def run(inputs, scenario, level, branching=False, start_step=0, block_steps=None):
    model = frozen.load_models(inputs/'raw-a')['k4']
    rows = [r for r in frozen.rows(inputs/'parent-explicit-fractional/raw-a/initial_states.csv')
            if r['scenario_id'] == scenario]
    exact = frozen.rational_from_parent_rows(rows)
    dt = frozen.TIMESTEPS_RAW[level]
    for _ in range(start_step):
        exact = frozen.rational_step(model, exact, dt, frozen.KDK)
    checkpoint_hash = frozen.rational_hash(exact)
    state = {p.identifier: ([Affine.make(x) for x in p.x], [Affine.make(x) for x in p.p])
             for p in exact.packets}
    arithmetic = Arithmetic()
    cells = [Cell(arithmetic.round_state(state), {})]
    witness = arithmetic.witness()
    assert joint_witness(cells, exact, arithmetic, witness)
    if block_steps is None:
        # Full-tail generation does not read any comparator after initialization.
        # Comparator replay belongs only to explicitly withheld block tests.
        exact = None
    counters = dict(cumulative_cells=1, max_live_cells=1, splits=[])
    start, checks, step, stage, reason = time.monotonic(), 0, 0, 'initial', None
    try:
        for step in range(1, (block_steps or 16*frozen.STEP_COUNTS[level])+1):
            for stage, operation, qoperation, duration in (
                    ('first_kick', kick, frozen.rational_kick, dt//2),
                    ('drift', drift, frozen.rational_drift, dt),
                    ('second_kick', kick, frozen.rational_kick, dt//2)):
                cells = advance(model, cells, duration, operation, arithmetic,
                                branching, counters, start)
                if exact is not None:
                    exact = qoperation(model, exact, duration)
                    witness = arithmetic.witness(witness)
                    assert joint_witness(cells, exact, arithmetic, witness), 'joint withheld containment failed'
                    checks += 1
            if exact is not None:
                exact.time_raw += dt
                if frozen.rational_state_metrics(exact).exceeded:
                    exact = None
        status = 'state_enclosure_only_physical_observers_pending'
    except (control.Inconclusive, MemoryError) as error:
        status = 'certificate_inconclusive'
        reason = str(error) or 'verifier_memory_budget'
    independent.check_rounding_definitions(arithmetic.definitions)
    return dict(schema='mls.correlation-aware.state-pilot.v1', scenario=scenario, level=level,
                candidate='C' if branching else 'B', start_step=start_step,
                requested_block_steps=block_steps, exact_checkpoint_hash=checkpoint_hash,
                step=step, stage=stage, status=status, reason=reason,
                joint_withheld_stage_checks=checks, symbols_created=len(arithmetic.definitions),
                counters=counters, physical_budgets_certified=False,
                selected_precision=None, promotion='NO_PROMOTION')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('inputs', type=Path)
    p.add_argument('--scenario', choices=['k4_internal', 'k4_boosted'], required=True)
    p.add_argument('--level', type=int, choices=range(5), required=True)
    p.add_argument('--branching', action='store_true')
    p.add_argument('--start-step', type=int, choices=[0, 8, 32], default=0)
    p.add_argument('--block-steps', type=int, choices=[1, 4, 16])
    a = p.parse_args()
    # Linux evidence runner enforces the preregistered address-space ceiling.
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    print(json.dumps(run(a.inputs, a.scenario, a.level, a.branching,
                         a.start_step, a.block_steps), sort_keys=True, indent=2))
