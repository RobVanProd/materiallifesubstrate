"""Independent Python-integer rational replay of all short KDK comparators.

Unlike the generator's GMP-rational target this uses the separately implemented
reference equations and Python Fraction. No bounded trajectory supplies target
state or force scalars; candidate wires are read only to measure discrepancies.
"""
import argparse
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import bounded_integrator_bakeoff_check as c
from bakeoff_final_audit import phase
f=c.f


def run(parent,short,expected):
    inputs=parent/'parent/parent/parent/inputs';models=f.load_models(inputs/'raw-a')
    initial=list(f.rows(inputs/'parent-explicit-fractional/raw-a/initial_states.csv'))
    results=[]
    for scenario in f.SCENARIOS:
        for level,n in enumerate(f.TIMESTEPS_RAW):
            model=models['octahedron' if scenario=='octahedron_deformation' else 'k4']
            target=f.rational_from_parent_rows([r for r in initial if r['scenario_id']==scenario])
            row=json.loads((short/f'{scenario}-L{level}-{f.KDK}.json').read_text())
            maxx=maxp=maxe=Q();stream=hashlib.sha256()
            for k,(wire,energy) in enumerate(zip(row['wires'],row['energy'])):
                state=phase(wire)
                ex=max(abs(a.x[j]-b.x[j])*f.LQ for a,b in zip(target.packets,state.packets) for j in range(3))
                ep=max(abs(a.p[j]-b.p[j])*f.PQ for a,b in zip(target.packets,state.packets) for j in range(3))
                ee=abs(f.rational_energy(model,target)-Q(energy))
                maxx=max(maxx,ex);maxp=max(maxp,ep);maxe=max(maxe,ee)
                for q in (ex,ep,ee):stream.update(str(q).encode()+b'\n')
                if k<f.STEP_COUNTS[level]:target=f.rational_step(model,target,n,f.KDK)
            calculated=dict(scenario=scenario,level=level,samples=f.STEP_COUNTS[level]+1,
                x=str(maxx),p=str(maxp),energy=str(maxe),comparisons_sha256=stream.hexdigest(),
                passed=maxx<=f.POSITION_BUDGET and maxp<=f.MOMENTUM_BUDGET and maxe<=f.ENERGY_BUDGET)
            assert calculated==json.loads((expected/f'{scenario}-L{level}.json').read_text()),'independent exact comparator mismatch'
            assert calculated['passed'];results.append(calculated)
            print(scenario+' L'+str(level)+' Python-integer exact target PASS',flush=True)
    return dict(passed=True,rows=results,backend='Python integer Fraction; independent reference KDK')


if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    p=argparse.ArgumentParser()
    for name in ('parent','short','expected','output'):p.add_argument(name,type=Path)
    a=p.parse_args();result=run(a.parent,a.short,a.expected)
    with a.output.open('x') as stream:json.dump(result,stream,sort_keys=True);stream.write('\n')
