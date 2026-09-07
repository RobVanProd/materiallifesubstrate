"""Remaining unchanged-baseline replay, covariance and exact-prefix checks."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import resource
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
import bakeoff_baseline as b
from run_bounded_integrator_bakeoff import initial_models,inputs,save
f=b.f;Q=b.check.Q


def relative_difference(first,second,com=False):
    ids,masses,_,a=b.check.decode_wire(first); _,_,_,z=b.check.decode_wire(second)
    ex=ep=Q()
    for k in range(6):
        if com:
            if k<3:
                ca=sum((m*a[6*i+k] for i,m in enumerate(masses)),Q())/sum(masses)
                cz=sum((m*z[6*i+k] for i,m in enumerate(masses)),Q())/sum(masses)
            else:
                ca=sum((a[6*i+k] for i in range(len(ids))),Q())/sum(masses)
                cz=sum((z[6*i+k] for i in range(len(ids))),Q())/sum(masses)
        else:ca=a[k];cz=z[k]
        for i,m in enumerate(masses):
            factor=m if com and k>=3 else 1
            e=abs((a[6*i+k]-factor*ca)-(z[6*i+k]-factor*cz))
            if k<3:ex=max(ex,e*b.check.f.LQ)
            else:ep=max(ep,e*b.check.f.PQ)
    return ex,ep


def main(parent,baseline,out):
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    out.mkdir(parents=True,exist_ok=False)
    models,mids,states=initial_models(parent)
    controls=[]
    for scenario in f.SCENARIOS:
        for level,n in enumerate(f.TIMESTEPS_RAW):
            count=f.STEP_COUNTS[level];model=models[mids[scenario]]
            record=json.loads((baseline/f'{scenario}-L{level}-{f.KDK}.json').read_text())
            final=f.decode_state(bytes.fromhex(record['wires'][-1]))
            reverse,*_=b.run(model,final,-n,count)
            ex,ep=b.error(f.encode_state(reverse),f.encode_state(states[scenario]))
            row=dict(kind='reverse',scenario=scenario,level=level,x=str(ex),p=str(ep),
                passed=ex<=b.check.f.POSITION_BUDGET and ep<=b.check.f.MOMENTUM_BUDGET,
                recovered_wire=f.encode_state(reverse).hex())
            controls.append(row)
            midpoint=f.decode_state(bytes.fromhex(record['wires'][count//2]))
            resumed,wires,energy,audit=b.run(model,midpoint,n,count-count//2)
            assert [w.hex() for w in wires]==record['wires'][count//2:],'checkpoint suffix differs'
            assert energy==record['energy'][count//2:],'checkpoint observer differs'
            controls.append(dict(kind='checkpoint',scenario=scenario,level=level,passed=True,
                state_suffix_sha256=hashlib.sha256(b''.join(wires)).hexdigest()))
    for level,n in enumerate(f.TIMESTEPS_RAW):
        record=json.loads((baseline/f'k4_internal-L{level}-{f.KDK}.json').read_text())
        for scenario in ('k4_translated','k4_boosted'):
            end,wires,_,_=b.run(models[mids[scenario]],states[scenario],n,f.STEP_COUNTS[level])
            save(out/f'{scenario}-L{level}.json',dict(wires=[w.hex() for w in wires]))
            for com in (False,True):
                ex=ep=Q()
                for k,w in enumerate(wires):
                    x,p=relative_difference(w,bytes.fromhex(record['wires'][k]),com)
                    ex=max(ex,x);ep=max(ep,p)
                controls.append(dict(kind=scenario+('-com' if com else '-first-packet'),level=level,
                    x=str(ex),p=str(ep),passed=ex<=b.check.f.POSITION_BUDGET and ep<=b.check.f.MOMENTUM_BUDGET))
        for kind in ('packet_permutation','relation_permutation','endpoint_reversal'):
            model=copy.deepcopy(models['k4']);state=states['k4_internal'].clone()
            if kind=='packet_permutation':state.packets.reverse()
            elif kind=='relation_permutation':
                order=list(reversed(range(len(model.relations))))
                model.relations=[model.relations[i] for i in order]
                model.h=[[model.h[i][j] for j in order] for i in order]
            else:
                model.relations=[f.exact_lab.Relation(r.index,r.second_id,r.first_id,r.rest_length) for r in model.relations]
            _,wires,_,_=b.run(model,state,n,f.STEP_COUNTS[level])
            save(out/f'{kind}-L{level}.json',dict(wires=[w.hex() for w in wires]))
            ex=ep=Q()
            for k,w in enumerate(wires):
                x,p=b.error(w,bytes.fromhex(record['wires'][k]));ex=max(ex,x);ep=max(ep,p)
            controls.append(dict(kind=kind,level=level,x=str(ex),p=str(ep),
                passed=ex<=b.check.f.POSITION_BUDGET and ep<=b.check.f.MOMENTUM_BUDGET))
        initial=states['domain_crossing'];prior=f.encode_state(initial)
        # Frozen inherited diagnostic duration is one second at every label;
        # it is not the convergence timestep (see parent runner/domain.csv).
        status,returned=f.one_step(models[mids['domain_crossing']],initial,1_000_000_000,f.KDK,f.profile_for(96))
        controls.append(dict(kind='domain_crossing',level=level,status=status,
            dt_raw=1_000_000_000,prior_wire=prior.hex(),returned_wire=f.encode_state(returned).hex(),
            passed=status!='accepted' and f.encode_state(returned)==prior))
    save(out/'controls.json',controls)
    save(out/'summary.json',dict(passed=all(r['passed'] for r in controls),rows=len(controls),
        failures=[r for r in controls if not r['passed']]))
    print(json.dumps(dict(rows=len(controls),failures=[r for r in controls if not r['passed']]),sort_keys=True),flush=True)


def exact_prefix(parent,baseline,out):
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    out.mkdir(parents=True,exist_ok=False)
    models,mids,states=initial_models(parent)
    _,exact_states=f.load_exact_states(inputs(parent)/'parent-explicit-fractional/raw-a')
    summaries=[]
    for scenario in f.SCENARIOS:
        for level,n in enumerate(f.TIMESTEPS_RAW):
            count=f.STEP_COUNTS[level];model=models[mids[scenario]]
            record=json.loads((baseline/f'{scenario}-L{level}-{f.KDK}.json').read_text())
            target=exact_states[scenario].clone();initial_inv=f.exact_lab.exact_invariants(target)
            maxx=maxp=maxe=f.Fraction(0);step_hash=hashlib.sha256()
            for k in range(count+1):
                state=f.decode_state(bytes.fromhex(record['wires'][k]))
                ex=ep=f.Fraction(0)
                for a,p in zip(sorted(target.packets,key=lambda p:p.identifier),f.canonical_packets(state)):
                    ex=max(ex,max(abs(q-f.exact_dyadic(v))*f.LQ for q,v in zip(a.x,p.x)))
                    ep=max(ep,max(abs(q-f.exact_dyadic(v))*f.PQ for q,v in zip(a.p,p.p)))
                _,potential=f.exact_lab.force_and_energy(model,target)
                energy=f.exact_lab.kinetic_energy_exact(target)+f.exact_float(potential)
                ee=abs(energy-f.Fraction(record['energy'][k]))
                maxx=max(maxx,ex);maxp=max(maxp,ep);maxe=max(maxe,ee)
                for q in (ex,ep,ee):step_hash.update(str(q).encode()+b'\n')
                if k==count:break
                status,target=f.exact_lab.one_step(model,target,n,f.exact_lab.KDK,'bakeoff-Q',level,k+1,None,None,initial_inv)
                assert status=='accepted'
            row=dict(scenario=scenario,level=level,samples=count+1,x=str(maxx),p=str(maxp),energy=str(maxe),
                comparisons_sha256=step_hash.hexdigest(),passed=maxx<=f.LQ/2**20 and maxp<=f.PQ/2**20 and maxe<=f.EQ/2**20)
            save(out/f'{scenario}-L{level}.json',row);summaries.append(row)
            print(scenario+' L'+str(level)+' exact prefix '+str(row['passed']),flush=True)
    save(out/'summary.json',dict(passed=all(r['passed'] for r in summaries),rows=summaries))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['controls','exact']);p.add_argument('parent',type=Path)
    p.add_argument('baseline',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();(main if a.mode=='controls' else exact_prefix)(a.parent,a.baseline,a.output)
