"""Verifier-only fixed-dimensional error recurrence. No candidate is truth."""
import argparse
from dataclasses import dataclass
from fractions import Fraction as Q
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

import bounded_fractional_phase_state_oracle as frozen
from bounded_phase_tail_interval import directed
import correlation_aware_binary64_cells as cells
from defect_recurrence_tail_check import affine_image

BITS = 512
EXPONENT_LIMIT = 16384
MEMORY_BYTES = 2*1024**3


class Inconclusive(Exception):
    def __init__(self, kind, details):
        self.kind, self.details = kind, details
        super().__init__(kind)


@dataclass(frozen=True)
class Interval:
    lo: Q
    hi: Q

    def __post_init__(self):
        assert self.lo <= self.hi

    def contains(self, q):
        return self.lo <= q <= self.hi


def enclose(lo, hi):
    assert lo <= hi
    out = Interval(directed(lo, False), directed(hi, True))
    for q in (out.lo, out.hi):
        if q:
            assert q.denominator & (q.denominator-1) == 0
            n = abs(q.numerator)
            odd = n // (n & -n)
            assert odd.bit_length() <= BITS
            exponent = n.bit_length()-q.denominator.bit_length()
            if not -EXPONENT_LIMIT <= exponent <= EXPONENT_LIMIT:
                raise Inconclusive('verifier_exponent_limit', dict(exponent=exponent))
    assert out.lo <= lo <= hi <= out.hi
    return out


def decode_wire(wire):
    """Independent decoder: never uses frozen Dyadic.fraction/from_row."""
    magic = b'MLS-BOUNDED-BINARY-PHASE-v1\x00'
    assert wire.startswith(magic)
    at = len(magic)
    def integer(n, signed=False):
        nonlocal at
        assert at+n <= len(wire)
        value = int.from_bytes(wire[at:at+n], 'little', signed=signed)
        at += n
        return value
    assert integer(2) == 1 and integer(2) == 96
    assert integer(2, True) == -16382 and integer(2, True) == 16383
    time_raw, count = integer(8, True), integer(8)
    ids, masses, values = [], [], []
    for _ in range(count):
        ids.append(integer(8)); masses.append(integer(8, True))
        assert ids[-1] > 0 and masses[-1] > 0
        for _ in range(6):
            sign, bits, exponent = integer(1), integer(2), integer(2, True)
            assert sign in (0, 1) and bits == 96
            assert at+12 <= len(wire)
            mantissa = int.from_bytes(wire[at:at+12], 'big'); at += 12
            if mantissa:
                assert 2**95 <= mantissa < 2**96 and -16382 <= exponent <= 16383
                value = Q(mantissa)*Q(2)**(exponent-95)
                values.append(-value if sign else value)
            else:
                assert sign == exponent == 0
                values.append(Q())
    assert ids == sorted(set(ids)) and at == len(wire)
    return ids, masses, time_raw, values


def flat(state):
    return [q for p in sorted(state.packets, key=lambda p:p.identifier) for q in p.x+p.p]


def relative(center, error, i, j):
    return [Interval(center[6*j+a]-center[6*i+a]+error[6*j+a].lo-error[6*i+a].hi,
                     center[6*j+a]-center[6*i+a]+error[6*j+a].hi-error[6*i+a].lo)
            for a in range(3)]


def certify_cell(interval, relation, axis):
    lo, hi = interval.lo*frozen.LQ, interval.hi*frozen.LQ
    nominal = float((lo+hi)/2)
    if not math.isfinite(nominal):
        raise Inconclusive('force_cell', dict(relation=relation, axis=axis, nonfinite=True))
    bits = struct.unpack('>Q', struct.pack('>d', nominal))[0]
    if not cells.contains(lo, hi, bits):
        raise Inconclusive('force_cell', dict(relation=relation, axis=axis,
            lo_si=str(lo), hi_si=str(hi), proposed_bits=f'{bits:016x}',
            low_bits=struct.pack('>d',float(lo)).hex(), high_bits=struct.pack('>d',float(hi)).hex()))
    return nominal


def safe(model, relation, intervals):
    lower = sum((Q() if b.lo <= 0 <= b.hi else min(abs(b.lo),abs(b.hi))**2
                 for b in intervals),Q())
    floor = sum((q*q for q in frozen.reference_offset(model,relation)),Q()) / 2**48
    if lower < floor:
        raise Inconclusive('domain_enclosure', dict(relation=relation.index))


def identity(n):
    return [[Q(int(i==j)) for j in range(n)] for i in range(n)]


def operator(model, ids, masses, center, error, stage, dt):
    n = len(center)
    matrix = identity(n)
    if stage == 'drift':
        for i, mass in enumerate(masses):
            for a in range(3):
                matrix[6*i+a][6*i+3+a] = Q(dt,mass)
        return matrix, []
    lookup = {p:i for i,p in enumerate(ids)}
    geometry, cell_bits = [], []
    for relation in model.relations:
        i, j = lookup[relation.first_id], lookup[relation.second_id]
        rr = relative(center,error,i,j)
        safe(model,relation,rr)
        current = [certify_cell(b,relation.index,a) for a,b in enumerate(rr)]
        cell_bits.append([struct.pack('>d',v).hex() for v in current])
        reference = [float(q*frozen.LQ) for q in frozen.reference_offset(model,relation)]
        length, extension = frozen.path_b_geometry(current,reference,relation.rest_length)
        geometry.append((relation,i,j,length,extension))
    gs = []
    for row in model.h:
        g = 0.0
        for coefficient, geometry_value in zip(row,geometry):
            g += coefficient*geometry_value[4]
        assert math.isfinite(g)
        gs.append(g)
    for (relation,i,j,length,_),g in zip(geometry,gs):
        coefficient = Q(dt)*frozen.TQ*frozen.LQ/frozen.PQ*Q.from_float(g)/Q.from_float(length)
        for a in range(3):
            matrix[6*i+3+a][6*j+a] += coefficient
            matrix[6*i+3+a][6*i+a] -= coefficient
            matrix[6*j+3+a][6*j+a] -= coefficient
            matrix[6*j+3+a][6*i+a] += coefficient
    return matrix, cell_bits


def propagate(matrix, center, next_center, error):
    """One exact rational dot/sum per output endpoint, then outward rounding."""
    defects, out = [], []
    for row, following in zip(matrix,next_center):
        defect = sum((a*c for a,c in zip(row,center)),Q())-following
        lo = hi = defect
        for a,e in zip(row,error):
            lo += a*(e.lo if a >= 0 else e.hi)
            hi += a*(e.hi if a >= 0 else e.lo)
        defects.append(defect)
        out.append(enclose(lo,hi))
    return out, defects


def chord(model,ids,before,after,error_before,error_after):
    lookup = {p:i for i,p in enumerate(ids)}
    for relation in model.relations:
        i,j = lookup[relation.first_id],lookup[relation.second_id]
        a,b = relative(before,error_before,i,j),relative(after,error_after,i,j)
        safe(model,relation,[Interval(min(x.lo,y.lo),max(x.hi,y.hi)) for x,y in zip(a,b)])


def signed_add(accumulator, weight, sample):
    a,b = weight*sample.lo,weight*sample.hi
    return enclose(accumulator.lo+min(a,b),accumulator.hi+max(a,b))


def withheld_check(error, center, exact):
    return all(e.contains(q-c) for e,c,q in zip(error,center,flat(exact)))


def run(inputs,scenario,level,start,steps):
    model = frozen.load_models(inputs/'raw-a')['k4']
    initial_rows = [r for r in frozen.rows(inputs/'raw-a/initial_states.csv')
                    if r['scenario_id']==scenario and int(r['precision'])==96]
    candidate = frozen.phase_from_rows(initial_rows)
    parent_rows = [r for r in frozen.rows(inputs/'parent-explicit-fractional/raw-a/initial_states.csv')
                   if r['scenario_id']==scenario]
    exact = frozen.rational_from_parent_rows(parent_rows)
    # Authentication metadata is not numerical error state and is never fed
    # into propagation. This short-block runner has no full-tail entry point.
    expected = {}
    for r in frozen.iter_rows(inputs/'raw-a/representation_error.csv'):
        if r['scope']=='long_exact_prefix' and r['scenario_id']==scenario and int(r['precision'])==96 and int(r['level'])==level:
            sample = int(r['sample'])
            if sample <= start+steps:
                expected[sample] = r['candidate_state_hash']
    dt = frozen.TIMESTEPS_RAW[level]
    def authenticate(sample,state):
        assert sample in expected, 'candidate authentication row missing'
        assert frozen.phase_hash(state)==expected[sample], 'candidate differs from sealed B96'
    authenticate(0,candidate)
    for sample in range(1,start+1):
        status,candidate,*_ = frozen.one_step(model,candidate,dt,frozen.KDK)
        assert status=='accepted'
        authenticate(sample,candidate)
        exact = frozen.rational_step(model,exact,dt,frozen.KDK)
    ids,masses,_,center = decode_wire(frozen.encode_phase_state(candidate))
    error = [enclose(q-c,q-c) for q,c in zip(flat(exact),center)]
    assert withheld_check(error,center,exact)
    n = len(center)
    history = hashlib.sha256()
    checks = 0
    stage = 'initial'
    step = 0
    reason = None
    details = None
    complete_steps = 0
    try:
        for step in range(1,steps+1):
            for stage,duration,qoperation,coperation in (
                ('first_kick',dt//2,frozen.rational_kick,frozen.kick),
                ('drift',dt,frozen.rational_drift,frozen.drift),
                ('second_kick',dt//2,frozen.rational_kick,frozen.kick)):
                # Input/output candidate states are independently decoded wire
                # values. No exact comparator enters this generator call.
                following = coperation(model,candidate,duration)[0]
                wire = frozen.encode_phase_state(following)
                next_ids,next_masses,_,next_center = decode_wire(wire)
                assert next_ids==ids and next_masses==masses
                matrix,bit_cells = operator(model,ids,masses,center,error,stage,duration)
                next_error,defects = propagate(matrix,center,next_center,error)
                affine_image(matrix,center,next_center,error,next_error,defects)
                if stage=='drift':
                    chord(model,ids,center,next_center,error,next_error)
                # Only after generation: separately evolve and withhold-check.
                next_exact = qoperation(model,exact,duration)
                if not withheld_check(next_error,next_center,next_exact):
                    raise AssertionError('withheld exact target escapes defect enclosure')
                record = dict(step=start+step,stage=stage,wire=wire.hex(),cells=bit_cells,
                              defects=list(map(str,defects)),
                              error=[[str(e.lo),str(e.hi)] for e in next_error])
                history.update(json.dumps(record,sort_keys=True,separators=(',',':')).encode()+b'\n')
                checks += 1
                candidate,exact,center,error = following,next_exact,next_center,next_error
            candidate.time_raw += dt
            exact.time_raw += dt
            authenticate(start+step,candidate)
            complete_steps += 1
        status = 'withheld_block_contained'
    except Inconclusive as failure:
        status,reason,details = 'certificate_inconclusive',failure.kind,failure.details
        if reason=='force_cell' and 'lo_si' in details:
            # Diagnostic only AFTER the generator has stopped; never used to
            # narrow its interval or choose a conversion for continued work.
            relation = next(r for r in model.relations if r.index==details['relation'])
            value = frozen.rational_offset(exact,relation)[details['axis']]*frozen.LQ
            details = dict(details,withheld_exact_relative_si=str(value),
                           withheld_exact_bits=struct.pack('>d',float(value)).hex(),
                           current_target_contained=Q(details['lo_si']) <= value <= Q(details['hi_si']))
    return dict(schema='mls.defect-tail.block.v1',scenario=scenario,level=level,
        start_step=start,block_steps=steps,precision=96,verifier_bits=BITS,
        status=status,reason=reason,details=details,step=step,stage=stage,
        complete_steps=complete_steps,withheld_checks=checks,stage_stream_sha256=history.hexdigest(),
        final_error=[[str(e.lo),str(e.hi)] for e in error],
        active_error_intervals=n,active_error_endpoints=2*n,matrix_slots=n*n,
        historical_noise_symbols=0,physical_budgets_certified=False,
        selected_precision=None,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('inputs',type=Path)
    p.add_argument('--scenario',choices=['k4_internal','k4_boosted'],required=True)
    p.add_argument('--level',type=int,choices=range(5),required=True)
    p.add_argument('--start',type=int,choices=[0,8,32],required=True)
    p.add_argument('--steps',type=int,choices=[1,4,16],required=True)
    args=p.parse_args()
    if sys.platform=='linux':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(MEMORY_BYTES,MEMORY_BYTES))
    print(json.dumps(run(args.inputs,args.scenario,args.level,args.start,args.steps),sort_keys=True,indent=2))
