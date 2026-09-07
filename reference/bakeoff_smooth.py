"""Independent inherited 110-digit ODE reference, never candidate state."""
import argparse
from decimal import Decimal, getcontext
from fractions import Fraction as Q
import json
from pathlib import Path
import bounded_fractional_phase_state_oracle as f


def run(parent):
    getcontext().prec=110
    raw=parent/'parent/parent/parent/inputs/raw-a'
    originals=f.load_models(raw); rows=f.rows(raw/'initial_states.csv')
    models={}
    for key,m in originals.items():
        ids=sorted(m.reference)
        models[key]=f.foundation.Model(ids,[f.decimal_value(Q(m.masses_raw[i])*f.MQ) for i in ids],
            [[f.decimal_value(v*f.LQ) for v in m.reference[i]] for i in ids],
            [(r.first_id,r.second_id) for r in m.relations],
            [[f.decimal_value(Q.from_float(x)) for x in row] for row in m.h])
    initial={}
    for scenario in f.SCENARIOS:
        selected=[r for r in rows if r['scenario_id']==scenario and int(r['precision'])==96]
        state=f.phase_from_rows(selected)
        initial[scenario]=(selected[0]['model_id'],
            [[f.decimal_value(v*f.LQ) for v in p.x] for p in state.packets],
            [[f.decimal_value(v*f.PQ) for v in p.p] for p in state.packets])
    reference,refinement=f.foundation.oracle_states(models,initial)
    return dict(precision_decimal=110,base_counts=[128,256],levels=6,
        endpoint={k:list(map(str,v)) for k,v in reference.items()},
        refinement={k:str(v) for k,v in refinement.items()},status='PASS')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('parent',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();result=run(a.parent)
    with a.output.open('x') as stream:json.dump(result,stream,sort_keys=True);stream.write('\n')
    print(json.dumps(dict(status=result['status'],refinement=result['refinement']),sort_keys=True))
