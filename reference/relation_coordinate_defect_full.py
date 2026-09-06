"""Time-zero continuation, never reading an exact target after initialization."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
from fractions import Fraction as Q
import relation_coordinate_defect_tail as v
b,f=v.base,v.frozen


def energy_error(model,state,center,errors,rc,re):
    """Exact quadratic kinetic difference plus certified fixed-cell potential.
    Returns target-minus-candidate; absolute budgets are sign invariant.
    """
    geometry=[]
    for r,rr in zip(model.relations,v.target_relations(rc,re)):
        b.safe(model,r,rr)
        converted=[b.certify_cell(x,r.index,a) for a,x in enumerate(rr)]
        reference=[float(q*f.LQ) for q in f.reference_offset(model,r)]
        geometry.append(f.path_b_geometry(converted,reference,r.rest_length)[1])
    gs=[]
    for row in model.h:
        g=0.
        for h,e in zip(row,geometry):g+=h*e
        gs.append(g)
    twice=0.
    for e,g in zip(geometry,gs):twice+=e*g
    potential=Q.from_float(0.5*twice)-f.mechanical_energy(model,state)[1]
    lo=hi=potential
    for i,p in enumerate(sorted(state.packets,key=lambda p:p.identifier)):
        factor=f.PQ*f.PQ/(2*p.mass_raw*f.MQ)
        for a in range(3):
            k=6*i+3+a;c=center[k];e=errors[k]
            values=[2*c*t+t*t for t in (e.lo,e.hi)]
            if e.lo<=-c<=e.hi:values.append(-c*c)
            lo+=factor*min(values);hi+=factor*max(values)
    return b.enclose(lo,hi)


def run(inputs,invariants,scenario,level):
    with invariants.open('rb') as stream:
        assert hashlib.file_digest(stream,'sha256').hexdigest()=='0e0df2142b5abdaa8e90c642a5269599b666afcfd2792a98c23e5a88c30222b7'
    tid=f'long:{scenario}:B96:L{level}'
    # Authentication is streamed, has no numerical role, and is not truth.
    rows=(r for r in f.iter_rows(invariants) if r['trajectory_id']==tid)
    authenticated=0
    def auth(step,stage,state):
        nonlocal authenticated
        r=next(rows)
        assert int(r['step'])==step and r['stage']==stage
        assert f.phase_hash(state)==r['state_hash'], 'candidate wire differs from sealed trajectory'
        authenticated+=1
    model=f.load_models(inputs/'raw-a')['k4']
    candidate=f.phase_from_rows([r for r in f.rows(inputs/'raw-a/initial_states.csv')
        if r['scenario_id']==scenario and int(r['precision'])==96])
    initial=f.rational_from_parent_rows([r for r in f.rows(inputs/'parent-explicit-fractional/raw-a/initial_states.csv')
        if r['scenario_id']==scenario])
    ids,masses,_,center=b.decode_wire(f.encode_phase_state(candidate))
    rc=v.observe(model,ids,masses,center)
    errors=[b.enclose(t-c,t-c) for t,c in zip(b.flat(initial),center)]
    re=[b.enclose(t-c,t-c) for t,c in zip(v.observe(model,ids,masses,b.flat(initial)),rc)]
    del initial
    auth(0,'initial',candidate)
    dt=f.TIMESTEPS_RAW[level];count=16*f.STEP_COUNTS[level]
    history=hashlib.sha256();checks=complete=0;step=0;stage='initial'
    maximum_x=maximum_p=maximum_energy=Q()
    slope=b.Interval(Q(),Q()); final_energy=None
    status='state_horizon_enclosed_observers_pending'
    reason=details=None
    def observe_energy(sample):
        nonlocal slope,maximum_energy,final_energy,maximum_x,maximum_p
        ev=energy_error(model,candidate,center,errors,rc,re)
        maximum_energy=max(maximum_energy,abs(ev.lo),abs(ev.hi))
        final_energy=ev
        slope=b.signed_add(slope,Q(sample*dt)*f.TQ-8,ev)
        for k,e in enumerate(errors):
            if k%6<3:maximum_x=max(maximum_x,max(abs(e.lo),abs(e.hi))*f.LQ)
            else:maximum_p=max(maximum_p,max(abs(e.lo),abs(e.hi))*f.PQ)
    try:
        observe_energy(0)
        for step in range(1,count+1):
            for stage,duration,operation in (
                ('first_kick',dt//2,f.kick),('drift',dt,f.drift),('second_kick',dt//2,f.kick)):
                following=operation(model,candidate,duration)[0]
                wire=f.encode_phase_state(following)
                ni,nm,_,nc=b.decode_wire(wire)
                assert ni==ids and nm==masses
                auth(step,stage,following)
                nrc=v.observe(model,ids,masses,nc)
                pm,rm,cells=v.operators(model,ids,masses,rc,re,stage,duration)
                ne,pd=b.propagate(pm,center,nc,errors)
                nre,rd=b.propagate(rm,rc,nrc,re)
                b.affine_image(pm,center,nc,errors,ne,pd)
                b.affine_image(rm,rc,nrc,re,nre,rd)
                if stage=='drift':v.chord(model,rc,nrc,re,nre)
                record=dict(step=step,stage=stage,wire=wire.hex(),cells=cells,
                    packet_defects=list(map(str,pd)),relation_defects=list(map(str,rd)),
                    packet_error=[[str(e.lo),str(e.hi)] for e in ne],
                    relation_error=[[str(e.lo),str(e.hi)] for e in nre])
                history.update(json.dumps(record,sort_keys=True,separators=(',',':')).encode()+b'\n')
                checks+=1
                candidate,center,rc,errors,re=following,nc,nrc,ne,nre
            candidate.time_raw+=dt
            auth(step,'committed',candidate)
            stage='energy_observer'
            observe_energy(step)
            complete+=1
    except b.Inconclusive as failure:
        status='certificate_inconclusive';reason= failure.kind;details=failure.details
    denominator=sum(((Q(n*dt)*f.TQ-8)**2 for n in range(count+1)),Q())
    # A partial signed sum is NOT the full-horizon slope certificate.
    slope=b.enclose(slope.lo/denominator,slope.hi/denominator)
    return dict(schema='mls.relation-coordinate-defect.full.v1',scenario=scenario,level=level,
        precision=96,verifier_bits=512,horizon_seconds=16,requested_steps=count,
        status=status,reason=reason,details=details,step=step,stage=stage,
        complete_steps=complete,certified_stages=checks,authenticated_candidate_wires=authenticated,
        stage_stream_sha256=history.hexdigest(),historical_noise_symbols=0,
        packet_intervals=24,relation_intervals=36,matrix_slots=1872,
        partial_position_upper_m=str(maximum_x),partial_momentum_upper_SI=str(maximum_p),
        partial_energy_upper_J=str(maximum_energy),
        partial_signed_slope=[str(slope.lo),str(slope.hi)],
        packet_error=[[str(e.lo),str(e.hi)] for e in errors],
        relation_error=[[str(e.lo),str(e.hi)] for e in re],
        full_horizon_certified=False,physical_budgets_certified=False,
        selected_precision=None,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path);p.add_argument('invariants',type=Path)
    p.add_argument('--scenario',choices=['k4_internal','k4_boosted'],required=True)
    p.add_argument('--level',type=int,choices=range(5),required=True);p.add_argument('--short-gate',type=Path,required=True)
    a=p.parse_args();assert json.loads(a.short_gate.read_text())==dict(
        eligible=True,blocks_passed=90,blocks_total=90,stage_checks=1890,promotion='NO_PROMOTION')
    if sys.platform=='linux':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(b.MEMORY_BYTES,b.MEMORY_BYTES))
    print(json.dumps(run(a.inputs,a.invariants,a.scenario,a.level),sort_keys=True,indent=2))
