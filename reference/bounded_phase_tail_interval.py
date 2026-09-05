"""Noncausal 512-bit outward box pilot for the frozen rational KDK map."""
import argparse
import json
import math
import struct
import time
from dataclasses import dataclass
from fractions import Fraction as Q
from pathlib import Path
import bounded_fractional_phase_state_oracle as frozen

BITS = 512

class Inconclusive(Exception):
    pass

def directed(x, up):
    if not x:
        return Q(0)
    a = abs(x)
    e = a.numerator.bit_length() - a.denominator.bit_length()
    if a < Q(2)**e:
        e -= 1
    unit = Q(2)**(e-BITS+1)
    y = x/unit
    n = y.numerator // y.denominator
    if up and y != n:
        n += 1
    result = n*unit
    assert result >= x if up else result <= x
    return result

@dataclass(frozen=True)
class Box:
    lo: Q
    hi: Q
    def __post_init__(self):
        assert self.lo <= self.hi
    @staticmethod
    def point(x):
        return Box(Q(x), Q(x))
    def __add__(self, other):
        return Box(directed(self.lo+other.lo, False), directed(self.hi+other.hi, True))
    def __neg__(self):
        return Box(-self.hi, -self.lo)
    def __sub__(self, other):
        return self + -other
    def scale(self, q):
        a, b = self.lo*q, self.hi*q
        return Box(directed(min(a,b), False), directed(max(a,b), True))
    def contains(self, x):
        return self.lo <= x <= self.hi
    def hull(self, other):
        return Box(min(self.lo,other.lo), max(self.hi,other.hi))
    def minabs(self):
        return Q(0) if self.lo <= 0 <= self.hi else min(abs(self.lo),abs(self.hi))

def float_cell(box):
    a, b = float(box.lo), float(box.hi)
    if not math.isfinite(a) or not math.isfinite(b):
        raise Inconclusive("nonfinite binary64 endpoint")
    if struct.pack('>d',a) != struct.pack('>d',b):
        raise Inconclusive("unresolved_binary64_conversion:"+json.dumps({
            "lo":str(box.lo),"hi":str(box.hi),
            "lo_bits":struct.pack('>d',a).hex(),"hi_bits":struct.pack('>d',b).hex()}))
    return a

def offset(state, relation):
    return [b-a for a,b in zip(state[relation.first_id][0],state[relation.second_id][0])]

def safe_box(model, relation, boxes):
    ref = frozen.reference_offset(model,relation)
    lower = sum((b.minabs()**2 for b in boxes),Q())
    floor = sum((x*x for x in ref),Q()) / 2**48
    if lower < floor:
        raise Inconclusive(f"domain_enclosure_unresolved:relation={relation.index}")

def evaluate(model, state):
    geometry=[]
    for relation in model.relations:
        r=offset(state,relation)
        safe_box(model,relation,r)
        current=[]
        for axis,b in enumerate(r):
            try:
                current.append(float_cell(b.scale(frozen.LQ)))
            except Inconclusive as error:
                raise Inconclusive(f"relation={relation.index}:axis={axis}:{error}") from error
        reference=[float(x*frozen.LQ) for x in frozen.reference_offset(model,relation)]
        length,extension=frozen.path_b_geometry(current,reference,relation.rest_length)
        geometry.append((relation,r,length,extension))
    conjugates=[]
    for row in model.h:
        value=0.0
        for coefficient,g in zip(row,geometry):
            value += coefficient*g[3]
        conjugates.append(value)
    return [(g[0],g[1],Q.from_float(g[2]),Q.from_float(c)) for g,c in zip(geometry,conjugates)]

def kick(model,state,dt):
    evaluated=evaluate(model,state)
    out={i:([*x],[*p]) for i,(x,p) in state.items()}
    for relation,r,length,conjugate in evaluated:
        coefficient=dt*frozen.TQ*conjugate/length*frozen.LQ/frozen.PQ
        impulse=[b.scale(coefficient) for b in r]
        for axis,j in enumerate(impulse):
            out[relation.first_id][1][axis]=out[relation.first_id][1][axis]+j
            out[relation.second_id][1][axis]=out[relation.second_id][1][axis]-j
    return out

def drift(model,state,dt):
    out={i:([a+b.scale(Q(dt,model.masses_raw[i])) for a,b in zip(x,p)],[*p])
         for i,(x,p) in state.items()}
    for relation in model.relations:
        before,after=offset(state,relation),offset(out,relation)
        safe_box(model,relation,[a.hull(b) for a,b in zip(before,after)])
    return out

def contains(state,exact):
    return all(state[p.identifier][v][axis].contains(getattr(p,field)[axis])
               for p in exact.packets for v,field in enumerate(('x','p')) for axis in range(3))

def run(raw,parent_raw,scenario,level,start_step=0,block_steps=None):
    model=frozen.load_models(raw)['k4']
    parent_rows=[r for r in frozen.rows(parent_raw/'initial_states.csv') if r['scenario_id']==scenario]
    initial=frozen.rational_from_parent_rows(parent_rows)
    dt=frozen.TIMESTEPS_RAW[level]
    for _ in range(start_step):
        initial=frozen.rational_step(model,initial,dt,frozen.KDK)
    # This is a justified EXACT checkpoint, never a bounded checkpoint reset.
    checkpoint_hash=frozen.rational_hash(initial)
    state={p.identifier:([Box.point(x) for x in p.x],[Box.point(p_) for p_ in p.p]) for p in initial.packets}
    exact=initial
    start=time.monotonic()
    checked=0
    stage='initial'
    step=0
    try:
        for step in range(1,(block_steps or 16*frozen.STEP_COUNTS[level])+1):
            for stage,operation,qoperation,duration in (
                ('first_kick',kick,frozen.rational_kick,dt//2),
                ('drift',drift,frozen.rational_drift,dt),
                ('second_kick',kick,frozen.rational_kick,dt//2)):
                if time.monotonic()-start > 900:
                    raise Inconclusive('verifier_wall_budget')
                # Certificate generator receives only its incoming box.
                state=operation(model,state,duration)
                if exact is not None:
                    # Independent retrospective withheld-answer check follows generation.
                    exact=qoperation(model,exact,duration)
                    if not contains(state,exact):
                        raise AssertionError('certificate excludes withheld exact state')
                    checked+=1
            if exact is not None and frozen.rational_state_metrics(exact).exceeded:
                exact=None
            if exact is not None:
                exact.time_raw += dt
        status='reference_box_propagated_energy_and_candidate_budget_checks_pending'
        reason=None
    except Inconclusive as error:
        status='certification_inconclusive'
        reason=str(error)
    return dict(scenario=scenario,level=level,step=step,stage=stage,status=status,
                start_step=start_step,requested_block_steps=block_steps,
                exact_checkpoint_hash=checkpoint_hash,
                reason=reason,withheld_exact_stage_checks=checked,
                candidate_state_used=False,reference_precision_bits=BITS,
                promotion='NO_PROMOTION')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('raw',type=Path)
    p.add_argument('parent_raw',type=Path)
    p.add_argument('--scenario',required=True,choices=['k4_internal','k4_boosted'])
    p.add_argument('--level',type=int,required=True,choices=range(5))
    p.add_argument('--start-step',type=int,default=0,choices=[0,8,32])
    p.add_argument('--block-steps',type=int,choices=[1,4,16])
    a=p.parse_args()
    print(json.dumps(run(a.raw,a.parent_raw,a.scenario,a.level,a.start_step,a.block_steps),sort_keys=True,indent=2))
