"""Post-stop causal diagnostic. No exact answer is fed back to propagation."""
from fractions import Fraction as Q
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
import bounded_fractional_phase_state_oracle as f
import defect_recurrence_tail as d


def probe(inputs,scenario,level):
    model=f.load_models(inputs/'raw-a')['k4']
    initial=f.rows(inputs/'raw-a/initial_states.csv')
    c=f.phase_from_rows([r for r in initial if r['scenario_id']==scenario and int(r['precision'])==96])
    q=f.rational_from_parent_rows([r for r in f.rows(inputs/'parent-explicit-fractional/raw-a/initial_states.csv') if r['scenario_id']==scenario])
    ids,masses,_,center=d.decode_wire(f.encode_phase_state(c))
    error=[d.enclose(x-y,x-y) for x,y in zip(d.flat(q),center)]
    for stage,dt,cfn,qfn in [('first_kick',f.TIMESTEPS_RAW[level]//2,f.kick,f.rational_kick),
                            ('drift',f.TIMESTEPS_RAW[level],f.drift,f.rational_drift)]:
        following=cfn(model,c,dt)[0]
        after=d.decode_wire(f.encode_phase_state(following))[3]
        a,_=d.operator(model,ids,masses,center,error,stage,dt)
        next_error,defects=d.propagate(a,center,after,error)
        d.affine_image(a,center,after,error,next_error,defects)
        q=qfn(model,q,dt)  # afterward, diagnostic only
        assert d.withheld_check(next_error,after,q)
        c,center,error=following,after,next_error
    relation=next(r for r in model.relations if r.index==5)
    i,j=ids.index(relation.first_id),ids.index(relation.second_id)
    truth=d.flat(q)
    a,b=truth[6*i]-center[6*i],truth[6*j]-center[6*j]
    assert center[6*i]==center[6*j] and a==b
    assert error[6*i]==error[6*j] and error[6*i].lo<error[6*i].hi
    rr=d.relative(center,error,i,j)[0]
    assert rr.lo<0<rr.hi
    return dict(scenario=scenario,level=level,relation=5,axis=0,
                candidate_relative_raw='0',exact_relative_raw='0',
                exact_endpoint_errors=[str(a),str(b)],
                endpoint_error_interval=[str(error[6*i].lo),str(error[6*i].hi)],
                independent_relative_interval_si=[str(rr.lo*f.LQ),str(rr.hi*f.LQ)],
                exact_error_equality_is_not_used_by_generator=True,
                historical_symbols=0,promotion='NO_PROMOTION')


if __name__=='__main__':
    root=Path(sys.argv[1])
    print(json.dumps([probe(root,s,l) for s in ('k4_internal','k4_boosted') for l in range(5)],sort_keys=True,indent=2))
