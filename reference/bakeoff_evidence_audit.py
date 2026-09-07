"""Independent wire/stage and energy audit of the unchanged eligible baseline.

The integer rounder, not MPFR, reconstructs short stage states and local
half-ULP bounds. Long representation bounds belong only to the authenticated
KDK parent and require its separate complete replay; they are never assigned
to either implicit candidate.
"""
import argparse
from collections import defaultdict
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import bounded_integrator_bakeoff_check as c
from bakeoff_short_analysis import energy_gate

f=c.f


def read(path):return json.loads(path.read_text())


def write(path,value):
    with path.open('x') as stream:json.dump(value,stream,sort_keys=True,separators=(',',':'));stream.write('\n')


def slope(values,h):
    N=len(values)-1
    weights=[h*(Q(i)-Q(N,2)) for i in range(N+1)]
    return sum((w*y for w,y in zip(weights,values)),Q())/sum((w*w for w in weights),Q())


def energy_metrics(values,h):
    errors=[e-values[0] for e in values];N=len(errors)-1
    quarter_ends=[errors[N*j//4] for j in range(1,5)]
    # Disjoint time windows (0,T/4],..., initial sample is retained in all
    # full-horizon statistics but is not counted twice in a window mean.
    quarter_means=[]
    for j in range(4):
        window=errors[N*j//4+1:N*(j+1)//4+1]
        quarter_means.append(sum(window,Q())/len(window))
    secular=(all(v>0 for v in quarter_ends) or all(v<0 for v in quarter_ends)) and all(
        abs(quarter_ends[i])>abs(quarter_ends[i-1]) for i in range(1,4))
    return dict(maximum_excursion=str(max(map(abs,errors))),mean_offset=str(sum(errors,Q())/len(errors)),
        final_error=str(errors[-1]),signed_slope=str(slope(errors,h)),
        quarter_endpoint_errors=list(map(str,quarter_ends)),quarter_window_means=list(map(str,quarter_means)),
        inherited_secular=secular)


def short(parent,baseline,event_records=None):
    inputs=parent/'parent/parent/parent/inputs'
    models=f.load_models(inputs/'raw-a');initial=list(f.rows(inputs/'raw-a/initial_states.csv'))
    reports=[]
    for scenario in f.SCENARIOS:
        model=models['octahedron' if scenario=='octahedron_deformation' else 'k4']
        state=f.phase_from_rows([r for r in initial if r['scenario_id']==scenario and int(r['precision'])==96])
        base=f.exact_state_invariants(state)
        for level,n in enumerate(f.TIMESTEPS_RAW):
            row=read(baseline/f'{scenario}-L{level}-{f.KDK}.json')
            replay,stages,forces=f.run_trajectory(model,state,n,f.STEP_COUNTS[level],f.KDK,True)
            assert replay.status=='accepted' and len(replay.samples)==len(row['wires'])
            for wire,value,energy in zip(row['wires'],replay.samples,row['energy']):
                assert f.encode_phase_state(value).hex()==wire,'short wire mismatch'
                assert f.mechanical_energy(model,value)[2]==Q(energy),'energy observer mismatch'
            inv=row['audit']['invariants'];raw_forces=row['audit']['forces']
            physical_stages=stages[1:] # reference includes initial state; wrapper starts at first kick
            assert len(inv)==len(physical_stages)==4*f.STEP_COUNTS[level] # three stages plus committed snapshot
            assert len(raw_forces)==len(forces)==2*len(model.relations)*f.STEP_COUNTS[level]
            maxima=defaultdict(Q);bounds=defaultdict(Q)
            for item,(step,stage,value,pbound,lbound) in zip(inv,physical_stages):
                assert item['step']==step and item['stage']==stage
                assert item['level']==level and item['trajectory_id']=='bakeoff-A','stage metadata mismatch'
                p,l=f.verify_invariant_row(item,value,base,model,pbound,lbound)
                maxima['P']=max(maxima['P'],p);maxima['L']=max(maxima['L'],l)
                bounds['P']=max(bounds['P'],max(pbound));bounds['L']=max(bounds['L'],max(lbound))
                assert p<=f.MOMENTUM_BUDGET and l<=f.ANGULAR_BUDGET
            for item,(step,stage,expected) in zip(raw_forces,forces):
                assert item['step']==step and item['stage']==stage
                assert item['level']==level and item['trajectory_id']=='bakeoff-A','force metadata mismatch'
                residuals=f.verify_force_row(item,expected)
                for name,value in residuals.items():
                    maxima[name]=max(maxima[name],value)
                    assert value<=(f.MOMENTUM_BUDGET if name=='pair_momentum_residual' else f.ANGULAR_BUDGET)
            if event_records is not None:
                recorded=read(event_records/f'short-{scenario}-L{level}.json')
                groups=f.observer_groups_from_replay(model,'bakeoff-A',96,level,replay,stages,forces,base)
                digests=[hashlib.sha256(b''.join(bytes.fromhex(e) for e in group)).hexdigest() for group in groups]
                assert recorded['event_groups']==digests and recorded['checkpoint_suffix_event_groups']==digests[len(digests)//2:]
            reports.append(dict(scenario=scenario,level=level,passed=True,stages=len(inv),relations=len(forces),
                maxima={k:str(v) for k,v in maxima.items()},local_accumulated_bounds={k:str(v) for k,v in bounds.items()},
                rounding_operations=replay.operation_count,rounding_audit_sha256=replay.rounding_audit_sha256,
                energy=energy_metrics(list(map(Q,row['energy'])),Q(n)*f.TQ)))
            print(scenario+' L'+str(level)+' independent stages PASS',flush=True)
    return dict(passed=True,rows=reports,scope='all fifteen short KDK trajectories, independent integer rounding')


def wire_invariants(wire):
    ids,masses,_,v=c.decode_wire(bytes.fromhex(wire))
    p=[sum((v[6*i+3+a] for i in range(len(ids))),Q())*f.PQ for a in range(3)]
    L=[]
    for a in range(3):
        b,d=(a+1)%3,(a+2)%3
        L.append(sum((v[6*i+b]*v[6*i+3+d]-v[6*i+d]*v[6*i+3+b] for i in range(len(ids))),Q())*f.LQ*f.PQ)
    return p,L


def long(parent,tails):
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
    from relation_coordinate_defect_tail_audit import audit as parent_audit
    # Raw recurrence rows deliberately leave observer qualification pending.
    # The separately derived final audit, not those raw booleans, closes it.
    accepted=parent_audit(parent/'evidence',parent/'parent')
    assert accepted==read(parent/'evidence/result.json')
    assert accepted['full_tails_certified']==10 and accepted['selected_precision']==96
    rows=[];gates=[]
    for scenario in ('k4_internal','k4_boosted'):
        metrics=[];radii=[]
        for level,n in enumerate(f.TIMESTEPS_RAW):
            row=read(tails/f'{scenario}-L{level}.json')
            certificate=read(parent/f'evidence/full/{scenario}-L{level}.json')
            assert row['phase_precision']==96 and row['steps']==16*f.STEP_COUNTS[level]
            assert len(row['wires'])==len(row['energy'])==row['steps']+1
            assert certificate['status']=='state_horizon_enclosed_observers_pending'
            assert certificate['reason'] is None
            assert certificate['complete_steps']==row['steps'] and certificate['promotion']=='NO_PROMOTION'
            assert hashlib.sha256(b''.join(bytes.fromhex(w) for w in row['wires'])).hexdigest()==row['wire_stream']
            h=Q(n)*f.TQ;energy=energy_metrics(list(map(Q,row['energy'])),h)
            inv=[wire_invariants(w) for w in row['wires']]
            P=max(abs(v[0][a]-inv[0][0][a]) for v in inv for a in range(3))
            L=max(abs(v[1][a]-inv[0][1][a]) for v in inv for a in range(3))
            Ps=max(abs(slope([v[0][a]-inv[0][0][a] for v in inv],h)) for a in range(3))
            Ls=max(abs(slope([v[1][a]-inv[0][1][a] for v in inv],h)) for a in range(3))
            assert P<=f.MOMENTUM_BUDGET and L<=f.ANGULAR_BUDGET
            assert Ps<=f.MOMENTUM_BUDGET/16 and Ls<=f.ANGULAR_BUDGET/16
            radius=Q(certificate['partial_energy_upper_J'])
            # Energy excursions subtract the initial observation too: carry its
            # uncertainty rather than silently treating the candidate as exact.
            radii.append(2*radius);metrics.append(energy)
            rows.append(dict(scenario=scenario,level=level,energy=energy,
                energy_difference_uncertainty=str(2*radius),P=str(P),L=str(L),P_slope_abs=str(Ps),L_slope_abs=str(Ls),
                parent_certificate_sha256=hashlib.sha256((parent/f'evidence/full/{scenario}-L{level}.json').read_bytes()).hexdigest()))
        gate=dict(scenario=scenario,maximum=energy_gate([Q(v['maximum_excursion']) for v in metrics],radii),
            final=energy_gate([abs(Q(v['final_error'])) for v in metrics],radii))
        gates.append(gate)
    return dict(rows=rows,energy_gates=gates,passed=all(g['maximum'].startswith('pass') and g['final'].startswith('pass') for g in gates),
        certificate_scope='KDK only; separate authenticated full parent replay required')


if __name__=='__main__':
    import resource # Linux evidence runner, not an arithmetic dependency
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['short','long'])
    for name in ('parent','records','output'):p.add_argument(name,type=Path)
    a=p.parse_args();resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    write(a.output,(short if a.mode=='short' else long)(a.parent,a.records))
