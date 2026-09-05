"""Targeted signed replay: no full 16-second candidate evidence regeneration."""
import argparse
import json
from pathlib import Path
from fractions import Fraction as Q
import bounded_fractional_phase_state_oracle as f

def run(bundle, scenario, level):
    raw=bundle/'raw-a'
    parent_raw=bundle/'parent-explicit-fractional/raw-a'
    model=f.load_models(raw)['k4']
    source=json.loads((bundle/'oracle/oracle-summary.json').read_text())
    rows=f.rows(raw/'representation_error.csv')
    evidence={(int(r['precision']),int(r['sample'])):r for r in rows
              if r['scope']=='long_exact_prefix' and r['scenario_id']==scenario and int(r['level'])==level
              and int(r['precision']) in (192,256)}
    steps=max(sample for _,sample in evidence)
    initial=f.rows(raw/'initial_states.csv')
    candidates={bits:f.phase_from_rows([r for r in initial if int(r['precision'])==bits and r['scenario_id']==scenario])
                for bits in (192,256)}
    exact=f.rational_from_parent_rows([r for r in f.rows(parent_raw/'initial_states.csv') if r['scenario_id']==scenario])
    energy={bits:[] for bits in candidates}
    argmax={}
    potential_matches={bits:0 for bits in candidates}
    for sample in range(steps+1):
        qe,qu=f.rational_force_and_energy(model,exact)
        qenergy=f.rational_energy(model,exact)
        for bits,state in candidates.items():
            expected=evidence[(bits,sample)]
            assert f.phase_hash(state)==expected['candidate_state_hash']
            assert f.rational_hash(exact)==expected['control_state_hash']
            delta=f.mechanical_energy(model,state)[2]-qenergy
            energy[bits].append(delta)
            potential_matches[bits]+=f.mechanical_energy(model,state)[1]==qu
            coordinates=[(abs((p.x[axis]-q.x[axis])*f.LQ),p.identifier,axis,(p.x[axis]-q.x[axis])*f.LQ)
                         for p,q in zip(state.packets,exact.packets) for axis in range(3)]
            maximum=max(c[0] for c in coordinates)
            argmax[bits]=dict(sample=sample,magnitude=str(maximum),ties=[dict(packet=c[1],axis='xyz'[c[2]],signed_error=str(c[3])) for c in coordinates if c[0]==maximum])
        if sample==steps: break
        exact=f.rational_step(model,exact,f.TIMESTEPS_RAW[level],f.KDK)
        for bits,state in list(candidates.items()):
            status,next_state,*_=f.one_step(model,state,f.TIMESTEPS_RAW[level],f.KDK)
            assert status=='accepted'
            candidates[bits]=next_state
        if sample%50==0:
            print(f'{scenario}:L{level}:sample={sample}',flush=True,file=__import__('sys').stderr)
    result={}
    dt=f.TIMESTEPS_RAW[level]*f.TQ
    for bits,values in energy.items():
        mean=Q(len(values)-1,2)*dt
        contributions=[(i*dt-mean)*v for i,v in enumerate(values)]
        numerator=sum(contributions,Q())
        absolute_sum=sum(map(abs,contributions),Q())
        denominator=sum(((i*dt-mean)**2 for i in range(len(values))),Q())
        slope=numerator/denominator
        assert slope==f.least_squares_slope(values,dt)
        if scenario=='k4_internal':
            parent=source['long_run']['runs'][f'B{bits}:L{level}']
            assert values[-1]==Q(parent['final_energy_representation_error'])
            assert slope==Q(parent['energy_representation_least_squares_slope'])
        envelope=source['long_run']['long_exact_prefix_anchor'][str(level)]['scenarios'][scenario]['metric_envelopes']
        assert Q(argmax[bits]['magnitude'])==Q(envelope['position_final'][str(bits)])
        result[str(bits)]=dict(final_position=argmax[bits],final_energy=str(values[-1]),
            slope=str(slope),slope_numerator=str(numerator),
            slope_sum_absolute_contributions=str(absolute_sum),
            slope_denominator=str(denominator),
            cancellation_fraction=str(abs(numerator)/absolute_sum) if absolute_sum else None,
            signed_energy_samples=[str(v) for v in values],potential_binary64_matches=potential_matches[bits])
    return dict(scenario=scenario,level=level,prefix_steps=steps,samples=steps+1,
                exact_hash_matches=True,profiles=result,promotion='NO_PROMOTION')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('bundle',type=Path)
    p.add_argument('--scenario',required=True);p.add_argument('--level',type=int,required=True)
    a=p.parse_args();print(json.dumps(run(a.bundle,a.scenario,a.level),sort_keys=True,indent=2))
