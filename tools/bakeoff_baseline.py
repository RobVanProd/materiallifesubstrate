"""Read-only wrapper of the unchanged KDK; new bakeoff metamorphic gates."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import resource
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
from run_bounded_integrator_bakeoff import initial_models,expected_states,save,inputs
import run_bounded_fractional_phase_state_lab as f
import bounded_integrator_bakeoff_check as check


def phase(wire):return check.decode_wire(wire)[3]


def error(a,b):
    diff=[abs(x-y) for x,y in zip(phase(a),phase(b))]
    return max(q*check.f.LQ for i,q in enumerate(diff) if i%6<3),max(q*check.f.PQ for i,q in enumerate(diff) if i%6>=3)


def run(model,state,n,count,expected=None,scenario=None,level=None,path=None,events=False):
    path=path or f.KDK
    state=state.clone();energy=[];wire=[];checkpoints=[];stream=hashlib.sha256()
    inv=[];forces=[]
    base=f.exact_state_invariants(state)
    for k in range(count+1):
        current=f.encode_state(state);wire.append(current)
        if expected is not None:
            assert f.state_hash(state)==expected[(scenario,path,level,k)],'A hash differs'
        energy.append(str(f.observed_energy(model,state,f.profile_for(96))[2]))
        if k==count:break
        ev=[]
        status,new=f.one_step(model,state,n,path,f.profile_for(96),
            trajectory='bakeoff-A',step=k+1,invariant_rows=inv if events else None,
            force_rows=forces if events else None,initial_invariants=base,
            observer_events=ev if events else None)
        assert status=='accepted',status
        state=new
        stream.update(bytes.fromhex(f.state_hash(state)))
        for e in ev:stream.update(e.encode())
    return state,wire,energy,dict(stream=stream.hexdigest(),invariants=inv,forces=forces)


def rotate(model,state,perm,sign):
    import copy
    model=copy.deepcopy(model);state=state.clone()
    def vec(v):return [sign[a]*v[perm[a]] for a in range(3)]
    for p in state.packets:p.x=vec(p.x);p.p=vec(p.p)
    model.reference={pid:vec(v) for pid,v in model.reference.items()}
    return model,state


def inverse_wire(state,perm,sign):
    state=state.clone()
    def inv(v):
        out=list(v)
        for a in range(3):out[perm[a]]=sign[a]*v[a]
        return out
    # Negation at B96 must happen under the B96 context, not ambient binary53.
    with f.profile_for(96).activate():
        for p in state.packets:p.x=inv(p.x);p.p=inv(p.p)
    return f.encode_state(state)


def rotations():
    for p in itertools.permutations(range(3)):
        parity=(-1)**sum(p[i]>p[j] for i in range(3) for j in range(i+1,3))
        for s in itertools.product((-1,1),repeat=3):
            if parity*s[0]*s[1]*s[2]==1:yield p,s


def main(parent,out):
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    out.mkdir(parents=True,exist_ok=False)
    models,mids,states=initial_models(parent);expected=expected_states(parent)
    results={};short=[]
    for scenario in f.SCENARIOS:
        for level,n in enumerate(f.TIMESTEPS_RAW):
            for path in (f.KDK,f.CONTROL):
                end,wires,energy,audit=run(models[mids[scenario]],states[scenario],n,f.STEP_COUNTS[level],expected,scenario,level,path,True)
                label=f'{scenario}-L{level}-{path}'
                save(out/(label+'.json'),dict(scenario=scenario,level=level,path=path,
                    wires=[w.hex() for w in wires],energy=energy,audit=audit))
                short.append(dict(scenario=scenario,level=level,path=path,status='authenticated',steps=len(wires)-1))
                if path==f.KDK:results[(scenario,level)]=(end,wires)
                print(label+' PASS',flush=True)
    save(out/'short-inventory.json',short)
    controls=[]
    # Every attempted control has a complete trace; stop the candidate on the
    # first hard-gate violation, preserving the unattempted inventory explicitly.
    for level,n in enumerate(f.TIMESTEPS_RAW):
        for perm,sign in rotations():
            with f.profile_for(96).activate():
                model,state=rotate(models['k4'],states['k4_internal'],perm,sign)
            end,wires,energy,audit=run(model,state,n,f.STEP_COUNTS[level])
            maxx=maxp=check.Q()
            errors=[]
            for k,w in enumerate(wires):
                restored=f.decode_state(w)
                x,p=error(inverse_wire(restored,perm,sign),results[('k4_internal',level)][1][k])
                maxx=max(maxx,x);maxp=max(maxp,p);errors.append([str(x),str(p)])
            passed=maxx<=check.f.POSITION_BUDGET and maxp<=check.f.MOMENTUM_BUDGET
            row=dict(kind='proper_rotation',level=level,perm=perm,sign=sign,
                position=str(maxx),momentum=str(maxp),passed=passed,
                errors=errors,wires=[w.hex() for w in wires])
            controls.append(row)
            if not passed:
                save(out/'metamorphic-controls.json',controls)
                save(out/'baseline-status.json',dict(status='reject_integrator_frozen_budget',
                    reason='proper_rotation',level=level,position=str(maxx),momentum=str(maxp),
                    rotation_attempts=len(controls),remaining_rotations=120-len(controls),
                    new_full_tails_run=0,parent_certificate_revoked=False,promotion='NO_PROMOTION'))
                print('A proper rotation budget failure',flush=True)
                return
    save(out/'metamorphic-controls.json',controls)
    save(out/'baseline-status.json',dict(status='additional_controls_pending',rotations=120))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('parent',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();main(a.parent,a.output)
