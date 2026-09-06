"""Direct incidence-observable defects; frozen candidate, verifier-only."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
from fractions import Fraction as Q
import defect_recurrence_tail as base

frozen = base.frozen


def observe(model, ids, masses, values):
    lookup = {p:i for i,p in enumerate(ids)}
    out = []
    for rel in model.relations:
        i,j = lookup[rel.first_id],lookup[rel.second_id]
        out += [values[6*j+a]-values[6*i+a] for a in range(3)]
        out += [values[6*j+3+a]/masses[j]-values[6*i+3+a]/masses[i] for a in range(3)]
    return out


def target_relations(center, errors):
    return [[base.Interval(center[6*k+a]+errors[6*k+a].lo,
                           center[6*k+a]+errors[6*k+a].hi) for a in range(3)]
            for k in range(len(center)//6)]


def operators(model, ids, masses, relcenter, relerror, stage, dt):
    """No packet error argument exists: only direct q can choose force cells."""
    lookup = {p:i for i,p in enumerate(ids)}
    endpoints = [(lookup[r.first_id],lookup[r.second_id]) for r in model.relations]
    packet, relation = base.identity(6*len(ids)),base.identity(6*len(endpoints))
    if stage == 'drift':
        for i,m in enumerate(masses):
            for a in range(3): packet[6*i+a][6*i+3+a] = Q(dt,m)
        for k in range(len(endpoints)):
            for a in range(3): relation[6*k+a][6*k+3+a] = Q(dt)
        return packet,relation,[]
    geometry, bit_cells = [],[]
    for r,rr in zip(model.relations,target_relations(relcenter,relerror)):
        base.safe(model,r,rr)
        converted = [base.certify_cell(b,r.index,a) for a,b in enumerate(rr)]
        bit_cells.append([struct.pack('>d',v).hex() for v in converted])
        reference = [float(q*frozen.LQ) for q in frozen.reference_offset(model,r)]
        geometry.append(frozen.path_b_geometry(converted,reference,r.rest_length))
    for b,((i,j),(length,_),hrow) in enumerate(zip(endpoints,geometry,model.h)):
        g = 0.0
        for h,(_,extension) in zip(hrow,geometry): g += h*extension
        assert math.isfinite(g) and length > 0
        alpha = Q(dt)*frozen.TQ*frozen.LQ/frozen.PQ*Q.from_float(g)/Q.from_float(length)
        for axis in range(3):
            packet[6*i+3+axis][6*j+axis] += alpha
            packet[6*i+3+axis][6*i+axis] -= alpha
            packet[6*j+3+axis][6*j+axis] -= alpha
            packet[6*j+3+axis][6*i+axis] += alpha
        # Difference of endpoint velocities under this one central relation.
        # Gather exact coefficients BEFORE taking interval images.
        for a,(u,v) in enumerate(endpoints):
            coeff = alpha*(Q(int(v==i)-int(v==j),masses[v])
                           -Q(int(u==i)-int(u==j),masses[u]))
            for axis in range(3): relation[6*a+3+axis][6*b+axis] += coeff
    return packet,relation,bit_cells


def chord(model, before, after, errors_before, errors_after):
    for r,aa,bb in zip(model.relations,target_relations(before,errors_before),
                       target_relations(after,errors_after)):
        base.safe(model,r,[base.Interval(min(a.lo,b.lo),max(a.hi,b.hi)) for a,b in zip(aa,bb)])


def run(inputs, scenario, level, start, steps):
    model = frozen.load_models(inputs/'raw-a')['k4']
    candidate = frozen.phase_from_rows([r for r in frozen.rows(inputs/'raw-a/initial_states.csv')
        if r['scenario_id']==scenario and int(r['precision'])==96])
    exact = frozen.rational_from_parent_rows([r for r in frozen.rows(
        inputs/'parent-explicit-fractional/raw-a/initial_states.csv') if r['scenario_id']==scenario])
    expected = {int(r['sample']):r['candidate_state_hash'] for r in frozen.iter_rows(inputs/'raw-a/representation_error.csv')
        if r['scope']=='long_exact_prefix' and r['scenario_id']==scenario and int(r['precision'])==96
        and int(r['level'])==level and int(r['sample'])<=start+steps}
    def authenticate(n,state):
        assert n in expected and frozen.phase_hash(state)==expected[n], 'sealed B96 mismatch'
    dt = frozen.TIMESTEPS_RAW[level]
    authenticate(0,candidate)
    for n in range(1,start+1):
        status,candidate,*_ = frozen.one_step(model,candidate,dt,frozen.KDK)
        assert status=='accepted'
        authenticate(n,candidate)
        exact = frozen.rational_step(model,exact,dt,frozen.KDK)
    ids,masses,_,center = base.decode_wire(frozen.encode_phase_state(candidate))
    rc = observe(model,ids,masses,center)
    errors = [base.enclose(t-c,t-c) for t,c in zip(base.flat(exact),center)]
    re = [base.enclose(t-c,t-c) for t,c in zip(observe(model,ids,masses,base.flat(exact)),rc)]
    history = hashlib.sha256()
    checks = complete = 0
    step,stage = 0,'initial'
    reason = details = None
    try:
        for step in range(1,steps+1):
            for stage,duration,qo,co in (
                ('first_kick',dt//2,frozen.rational_kick,frozen.kick),
                ('drift',dt,frozen.rational_drift,frozen.drift),
                ('second_kick',dt//2,frozen.rational_kick,frozen.kick)):
                following = co(model,candidate,duration)[0]
                wire = frozen.encode_phase_state(following)
                newids,newmasses,_,nc = base.decode_wire(wire)
                assert newids==ids and newmasses==masses
                nrc = observe(model,ids,masses,nc)
                pm,rm,cells = operators(model,ids,masses,rc,re,stage,duration)
                ne,pd = base.propagate(pm,center,nc,errors)
                nre,rd = base.propagate(rm,rc,nrc,re)
                base.affine_image(pm,center,nc,errors,ne,pd)
                base.affine_image(rm,rc,nrc,re,nre,rd)
                if stage=='drift': chord(model,rc,nrc,re,nre)
                # The generator has completed before the withheld target advances.
                nexact = qo(model,exact,duration)
                assert base.withheld_check(ne,nc,nexact), 'withheld packet escape'
                er = observe(model,ids,masses,base.flat(nexact))
                assert all(e.contains(t-c) for e,t,c in zip(nre,er,nrc)), 'withheld relation escape'
                record = dict(step=start+step,stage=stage,wire=wire.hex(),cells=cells,
                    packet_defects=list(map(str,pd)),relation_defects=list(map(str,rd)),
                    packet_error=[[str(e.lo),str(e.hi)] for e in ne],
                    relation_error=[[str(e.lo),str(e.hi)] for e in nre])
                history.update(json.dumps(record,sort_keys=True,separators=(',',':')).encode()+b'\n')
                checks += 1
                candidate,exact,center,rc,errors,re = following,nexact,nc,nrc,ne,nre
            candidate.time_raw += dt
            exact.time_raw += dt
            authenticate(start+step,candidate)
            complete += 1
        status = 'withheld_block_contained'
    except base.Inconclusive as failure:
        status,reason,details = 'certificate_inconclusive',failure.kind,failure.details
        if reason=='force_cell' and 'lo_si' in details:
            r = next(r for r in model.relations if r.index==details['relation'])
            value = frozen.rational_offset(exact,r)[details['axis']]*frozen.LQ
            details = dict(details,withheld_exact_relative_si=str(value),
                current_target_contained=Q(details['lo_si'])<=value<=Q(details['hi_si']))
    return dict(schema='mls.relation-coordinate-defect.block.v1',scenario=scenario,level=level,
        start_step=start,block_steps=steps,precision=96,verifier_bits=512,status=status,
        reason=reason,details=details,step=step,stage=stage,complete_steps=complete,
        withheld_checks=checks,stage_stream_sha256=history.hexdigest(),
        packet_error=[[str(e.lo),str(e.hi)] for e in errors],
        relation_error=[[str(e.lo),str(e.hi)] for e in re],
        packet_intervals=len(errors),relation_intervals=len(re),historical_noise_symbols=0,
        matrix_slots=len(errors)**2+len(re)**2,physical_budgets_certified=False,
        selected_precision=None,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path)
    p.add_argument('--scenario',choices=['k4_internal','k4_boosted'],required=True)
    p.add_argument('--level',type=int,choices=range(5),required=True)
    p.add_argument('--start',type=int,choices=[0,8,32],required=True)
    p.add_argument('--steps',type=int,choices=[1,4,16],required=True)
    a=p.parse_args()
    if sys.platform=='linux':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(base.MEMORY_BYTES,base.MEMORY_BYTES))
    print(json.dumps(run(a.inputs,a.scenario,a.level,a.start,a.steps),sort_keys=True,indent=2))
