"""A-only tails after short eligibility. B/C never fall back to this map."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import resource
import time
from run_bounded_integrator_bakeoff import initial_models,save
import bakeoff_baseline as b
f=b.f


def one(model,initial,n,count,authenticate=None,record=True):
    state=initial.clone();wires=[];energies=[];counter=0;elapsed=0.;stream=hashlib.sha256()
    for k in range(count+1):
        wire=f.encode_state(state)
        if authenticate is not None:
            assert f.state_hash(state)==authenticate[k],'full A wire differs from sealed parent'
        stream.update(wire)
        if record:
            wires.append(wire.hex());energies.append(str(f.observed_energy(model,state,f.profile_for(96))[2]))
        if k==count:break
        t=time.perf_counter()
        status,state=f.one_step(model,state,n,f.KDK,f.profile_for(96))
        elapsed+=time.perf_counter()-t
        assert status=='accepted';counter+=1
    return dict(wires=wires,energy=energies,steps=counter,wire_stream=stream.hexdigest()),elapsed


def main(parent,short_gate,out):
    assert json.loads(short_gate.read_text())['passed'],'short gate not passed'
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    out.mkdir(parents=True,exist_ok=False)
    models,mids,states=initial_models(parent)
    auth={}
    invariants=parent/'parent/evidence/candidate-auth/invariants.csv'
    with invariants.open(newline='') as stream:
        for row in csv.DictReader(stream):
            if row['stage'] in ('initial','committed'):
                auth.setdefault(row['trajectory_id'],{})[int(row['step'])]=row['state_hash']
    scientific=[];timings=[]
    for scenario in ('k4_internal','k4_boosted'):
        for level,n in enumerate(f.TIMESTEPS_RAW):
            model=models[mids[scenario]];count=16*f.STEP_COUNTS[level]
            expected=auth[f'long:{scenario}:B96:L{level}']
            warm,_=one(model,states[scenario],n,count,expected,False)
            repeats=[];row=None
            for repetition in range(5):
                result,seconds=one(model,states[scenario],n,count,expected,repetition==0)
                assert result['wire_stream']==warm['wire_stream'],'timed deterministic replay mismatch'
                repeats.append(seconds)
                if repetition==0:row=result
            assert row is not None
            checkpoint=f.decode_state(bytes.fromhex(row['wires'][count//2]))
            resumed,_=one(model,checkpoint,n,count-count//2)
            assert resumed['wires']==row['wires'][count//2:]
            assert resumed['energy']==row['energy'][count//2:]
            row.update(scenario=scenario,level=level,checkpoint_suffix=True,authenticated_samples=count+1,
                force_evaluations=2*count,mpfr_operations=(34*len(model.relations)+7*len(states[scenario].packets)+2)*count,
                solver_iterations=0,phase_precision=96)
            save(out/f'{scenario}-L{level}.json',row)
            scientific.append({k:v for k,v in row.items() if k not in ('wires','energy')})
            timings.append(dict(scenario=scenario,level=level,seconds=repeats,
                median=sorted(repeats)[2],range=[min(repeats),max(repeats)],warmups=1,
                note='candidate one_step time only; observers/authentication outside timed region'))
            print(scenario+' L'+str(level)+' full 16s PASS',flush=True)
    save(out/'inventory.json',scientific)
    save(out/'external-timing.json',timings)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('parent','short_gate','output'):p.add_argument(name,type=Path)
    a=p.parse_args();main(a.parent,a.short_gate,a.output)
