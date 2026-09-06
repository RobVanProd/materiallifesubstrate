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


def frame_box(model,ids,masses,center,rc,re):
    """COM-relative errors from DIRECT relation position/velocity errors.
    Complete K4 edges are required; no endpoint error subtraction occurs.
    """
    lookup={p:i for i,p in enumerate(ids)}; total=sum(masses)
    edges={frozenset((r.first_id,r.second_id)):(k,r) for k,r in enumerate(model.relations)}
    out=[]
    for i,pid in enumerate(ids):
        for kind in ('position','momentum'):
            for axis in range(3):
                lo=hi=c=Q()
                for j,other in enumerate(ids):
                    if i==j:continue
                    k,r=edges[frozenset((pid,other))]
                    sign=1 if r.first_id==pid else -1
                    factor=-Q(sign*masses[j],total)
                    if kind=='momentum':factor*=masses[i]
                    index=6*k+axis+(3 if kind=='momentum' else 0)
                    c+=factor*rc[index]
                    ee=re[index]
                    lo+=factor*(ee.lo if factor>=0 else ee.hi)
                    hi+=factor*(ee.hi if factor>=0 else ee.lo)
                unit=f.LQ if kind=='position' else f.PQ
                out.append(dict(candidate=str(c*unit),error=[str(lo*unit),str(hi*unit)]))
    return out


def invariants(center):
    momenta=[sum((center[i+a+3] for i in range(0,len(center),6)),Q()) for a in range(3)]
    angular=[Q(),Q(),Q()]
    for i in range(0,len(center),6):
        x,p=center[i:i+3],center[i+3:i+6]
        for a in range(3):angular[a]+=x[(a+1)%3]*p[(a+2)%3]-x[(a+2)%3]*p[(a+1)%3]
    return momenta,angular


def run(inputs,invariants_path,scenario,level,frame_output=None):
    with invariants_path.open('rb') as stream:
        assert hashlib.file_digest(stream,'sha256').hexdigest()=='0e0df2142b5abdaa8e90c642a5269599b666afcfd2792a98c23e5a88c30222b7'
    tid=f'long:{scenario}:B96:L{level}'
    # Authentication is streamed, has no numerical role, and is not truth.
    rows=(r for r in f.iter_rows(invariants_path) if r['trajectory_id']==tid)
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
    initial_p,initial_l=invariants(center)
    max_p_residual=max_l_residual=max_centrality=Q()
    frames=hashlib.sha256()
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
        if frame_output is not None:
            record=dict(sample=sample,phase_hash=f.phase_hash(candidate),
                        frame=frame_box(model,ids,masses,center,rc,re))
            line=json.dumps(record,sort_keys=True,separators=(',',':'))+'\n'
            frames.update(line.encode());frame_output.write(line)
    try:
        observe_energy(0)
        for step in range(1,count+1):
            for stage,duration,operation in (
                ('first_kick',dt//2,f.kick),('drift',dt,f.drift),('second_kick',dt//2,f.kick)):
                following,_,audits=operation(model,candidate,duration)
                wire=f.encode_phase_state(following)
                ni,nm,_,nc=b.decode_wire(wire)
                assert ni==ids and nm==masses
                pp,ll=invariants(nc)
                max_p_residual=max(max_p_residual,max(abs(a-bb)*f.PQ for a,bb in zip(pp,initial_p)))
                max_l_residual=max(max_l_residual,max(abs(a-bb)*f.LQ*f.PQ for a,bb in zip(ll,initial_l)))
                if stage!='drift':
                    byid={pid:i for i,pid in enumerate(ids)}
                    for audit in audits:
                        r=audit['relation'];i=byid[r.first_id];j=byid[r.second_id]
                        rr=[center[6*j+a]-center[6*i+a] for a in range(3)]
                        for key in ('rounded_impulse','first_actual_impulse','second_actual_impulse'):
                            impulse=audit[key]
                            for a in range(3):
                                cross=rr[(a+1)%3]*impulse[(a+2)%3]-rr[(a+2)%3]*impulse[(a+1)%3]
                                max_centrality=max(max_centrality,abs(cross)*f.LQ*f.PQ)
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
        final_energy_error=[str(final_energy.lo),str(final_energy.hi)] if final_energy else None,
        final_position_upper_m=str(max(max(abs(e.lo),abs(e.hi))*f.LQ for k,e in enumerate(errors) if k%6<3)),
        final_momentum_upper_SI=str(max(max(abs(e.lo),abs(e.hi))*f.PQ for k,e in enumerate(errors) if k%6>=3)),
        candidate_momentum_residual_max=str(max_p_residual),
        candidate_angular_residual_max=str(max_l_residual),
        candidate_centrality_residual_max=str(max_centrality),
        frame_stream_sha256=frames.hexdigest() if frame_output is not None else None,
        partial_signed_slope=[str(slope.lo),str(slope.hi)],
        packet_error=[[str(e.lo),str(e.hi)] for e in errors],
        relation_error=[[str(e.lo),str(e.hi)] for e in re],
        full_horizon_certified=False,physical_budgets_certified=False,
        selected_precision=None,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path);p.add_argument('invariants',type=Path)
    p.add_argument('--scenario',choices=['k4_internal','k4_boosted'],required=True)
    p.add_argument('--level',type=int,choices=range(5),required=True);p.add_argument('--short-gate',type=Path,required=True)
    p.add_argument('--frame-output',type=Path)
    a=p.parse_args();assert json.loads(a.short_gate.read_text())==dict(
        eligible=True,blocks_passed=90,blocks_total=90,stage_checks=1890,promotion='NO_PROMOTION')
    if sys.platform=='linux':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(b.MEMORY_BYTES,b.MEMORY_BYTES))
    if a.frame_output:
        with a.frame_output.open('x') as out:result=run(a.inputs,a.invariants,a.scenario,a.level,out)
    else:result=run(a.inputs,a.invariants,a.scenario,a.level)
    print(json.dumps(result,sort_keys=True,indent=2))
