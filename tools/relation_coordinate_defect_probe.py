"""Matched causal control at the parent failure, without a post-hoc equality."""
import argparse
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
import relation_coordinate_defect_tail as v
b,f=v.base,v.frozen


def probe(inputs,scenario,level):
    model=f.load_models(inputs/'raw-a')['k4']
    state=f.phase_from_rows([r for r in f.rows(inputs/'raw-a/initial_states.csv')
        if r['scenario_id']==scenario and int(r['precision'])==96])
    initial=f.rational_from_parent_rows([r for r in f.rows(inputs/'parent-explicit-fractional/raw-a/initial_states.csv')
        if r['scenario_id']==scenario])
    ids,masses,_,c=b.decode_wire(f.encode_phase_state(state));rc=v.observe(model,ids,masses,c)
    pe=[b.enclose(t-x,t-x) for t,x in zip(b.flat(initial),c)]
    re=[b.enclose(t-x,t-x) for t,x in zip(v.observe(model,ids,masses,b.flat(initial)),rc)]
    del initial
    records=[];dt=f.TIMESTEPS_RAW[level]
    for stage,duration,operation in (('first_kick',dt//2,f.kick),('drift',dt,f.drift)):
        nextstate=operation(model,state,duration)[0]
        _,_,_,nc=b.decode_wire(f.encode_phase_state(nextstate));nrc=v.observe(model,ids,masses,nc)
        pm,rm,_=v.operators(model,ids,masses,rc,re,stage,duration)
        npe,pd=b.propagate(pm,c,nc,pe);nre,rd=b.propagate(rm,rc,nrc,re)
        k=next(k for k,r in enumerate(model.relations) if r.index==5)
        records.append(dict(stage=stage,direct_position_error=[str(nre[6*k].lo),str(nre[6*k].hi)],
            direct_velocity_error=[str(nre[6*k+3].lo),str(nre[6*k+3].hi)],
            position_defect=str(rd[6*k]),velocity_defect=str(rd[6*k+3])))
        state,c,rc,pe,re=nextstate,nc,nrc,npe,nre
    r=model.relations[k];i=ids.index(r.first_id);j=ids.index(r.second_id)
    independent=b.relative(c,pe,i,j)[0];direct=v.target_relations(rc,re)[k][0]
    value=b.certify_cell(direct,5,0)
    try:b.certify_cell(independent,5,0);old_failed=False
    except b.Inconclusive:old_failed=True
    assert old_failed and direct.lo==direct.hi==0 and value==0.
    return dict(scenario=scenario,level=level,relation=5,axis=0,stages=records,
        direct_raw_interval=[str(direct.lo),str(direct.hi)],
        independent_raw_interval=[str(independent.lo),str(independent.hi)],
        independent_cell_inconclusive=old_failed,direct_cell_bits='0000000000000000',
        post_initial_exact_target_used=False,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('inputs',type=Path);a=p.parse_args()
    print(json.dumps([probe(a.inputs,s,l) for s in ('k4_internal','k4_boosted') for l in range(5)],sort_keys=True,indent=2))
