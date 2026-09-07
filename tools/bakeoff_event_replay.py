"""Full canonical observer-event checkpoint replay, with absolute stage labels."""
import argparse
import hashlib
import json
from pathlib import Path
import run_bounded_fractional_phase_state_lab as f
from run_bounded_integrator_bakeoff import initial_models,save


def replay(model,wires,level,trajectory,start=0):
    n=f.TIMESTEPS_RAW[level];state=f.decode_state(bytes.fromhex(wires[start]));groups=[]
    for k in range(start+1,len(wires)):
        events=[]
        status,state=f.one_step(model,state,n,f.KDK,f.profile_for(96),trajectory=trajectory,level=level,step=k,observer_events=events)
        assert status=='accepted' and f.encode_state(state).hex()==wires[k]
        energy=f.observed_energy(model,state,f.profile_for(96))
        events.append(f.observer_event_digest('energy',f.energy_observer_row(trajectory,96,level,k,state,energy)))
        assert len(events)==2*len(model.relations)+5
        groups.append(hashlib.sha256(b''.join(bytes.fromhex(e) for e in events)).hexdigest())
    return groups


def run(parent,short,tails,out):
    out.mkdir(parents=True,exist_ok=False);models,mids,_=initial_models(parent);rows=[]
    for scope,scenarios,directory in [('short',f.SCENARIOS,short),('long',('k4_internal','k4_boosted'),tails)]:
        for scenario in scenarios:
            for level in range(5):
                name=f'{scenario}-L{level}'+(f'-{f.KDK}' if scope=='short' else '')
                wires=json.loads((directory/(name+'.json')).read_text())['wires']
                trajectory='bakeoff-A' if scope=='short' else 'bakeoff-A-long:'+scenario
                original=replay(models[mids[scenario]],wires,level,trajectory)
                resumed=replay(models[mids[scenario]],wires,level,trajectory,len(original)//2)
                assert resumed==original[len(original)//2:],'complete observer suffix changed'
                row=dict(scope=scope,scenario=scenario,level=level,trajectory=trajectory,steps=len(original),
                    passed=True,event_groups=original,checkpoint_suffix_event_groups=resumed)
                save(out/f'{scope}-{scenario}-L{level}.json',row)
                rows.append({k:v for k,v in row.items() if k not in ('event_groups','checkpoint_suffix_event_groups')})
                print(scope+' '+scenario+' L'+str(level)+' complete event replay PASS',flush=True)
    save(out/'inventory.json',rows)


if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    p=argparse.ArgumentParser()
    for name in ('parent','short','tails','output'):p.add_argument(name,type=Path)
    a=p.parse_args();run(a.parent,a.short,a.tails,a.output)
