"""Noncausal parity harness: C++ gets model + initial state, never next states."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
sys.dont_write_bytecode=True
import run_bounded_fractional_phase_state_lab as f
from run_bounded_integrator_bakeoff import initial_models

PARENT='a1497dabf8ed8788e67cd0f739c13d0129d72977'
MANIFEST='48bc04568aa5af67e5fd852c2a65e866ab8d7e16fd4b58535827310d24997626'

def save(path,obj):
    with path.open('x') as stream:json.dump(obj,stream,sort_keys=True,separators=(',',':'));stream.write('\n')

def model_text(model):
    lines=[str(len(model.relations))]
    for r in model.relations:
        vals=[r.index,r.first_id,r.second_id,f.float_bits(r.rest_length)]
        for q in f.exact_reference_offset(model,r):vals.extend((q.numerator,q.denominator))
        lines.append(' '.join(map(str,vals)))
    for row in model.h:lines.append(' '.join(str(f.float_bits(v)) for v in row))
    return '\n'.join(lines)+'\n'

def invoke(exe,out,name,model,wire,trajectory,level,dt,count,start=0,path='KDK'):
    inp=out/(name+'.input');result=out/(name+'.output')
    inp.write_text(f'run {trajectory} {level} {dt} {count} {start} {path}\n{wire}\n'+model_text(model))
    command=[str(exe),str(inp),str(result)]
    completed=subprocess.run(command,capture_output=True,text=True)
    assert completed.returncode==0,(command,completed.stderr,result.read_text()[:1000])
    return result

def primitives(exe,out):
    rng=random.Random(260907);values=[f.Fraction(0),f.Fraction(1),f.Fraction(-1)]
    for e in (-16382,-200,-96,-1,0,95,300,16383):
        for j in (-3,-2,-1,0,1,2,3):
            q=f.Fraction(2**e) if e>=0 else f.Fraction(1,2**-e)
            values.extend([q*(1+f.Fraction(j,2**97)),-q*(1+f.Fraction(j,2**97))])
    for _ in range(1000):values.append(f.Fraction(rng.randrange(-2**200,2**200),rng.randrange(1,2**150)))
    inp=out/'primitives.input';dst=out/'primitives.output'
    inp.write_text('round\n'+''.join(f'{q.numerator} {q.denominator}\n' for q in values))
    subprocess.run([str(exe),str(inp),str(dst)],check=True)
    rows=dst.read_text().splitlines();assert len(rows)==len(values)
    for i,(q,row) in enumerate(zip(values,rows)):
        try:
            with f.profile_for(96).activate() as ctx:z=f.rounded_fraction(ctx,96,q,'parity_primitive')
            expected=f.encode_component(z,96).hex()
        except f.LabError:expected='ERROR'
        assert row.startswith('ERROR') if expected=='ERROR' else row==expected,(i,str(q),row,expected)
    save(out/'primitive-result.json',dict(passed=len(rows),seed=260907))

def compare(result,model,wires,trajectory,level,dt,start,path,event_groups=None):
    rows=result.read_text().splitlines();states={};events={};stages={};geometries={}
    for line in rows:
        cols=line.split();kind=cols[0];k=int(cols[1])
        if kind=='S':states[k]=(cols[2],cols[3])
        elif kind=='E':events.setdefault(k,[]).append(cols[2])
        elif kind=='T':stages[(k,cols[2])]=cols[3]
        elif kind=='G':geometries.setdefault((k,cols[2]),[]).append(tuple(map(int,cols[3:])))
        else:raise AssertionError(('cpp_rejection',line))
    assert len(states)==len(wires)-start
    state=f.decode_state(bytes.fromhex(wires[start]));checked=0
    for k in range(start+1,len(wires)):
        assert states[k][0]==wires[k],('state',k,states[k][0],wires[k])
        expected_events=[];invs=[];forces=[]
        status,new=f.one_step(model,state,dt,path,f.profile_for(96),trajectory=trajectory,level=level,step=k,
            invariant_rows=invs,force_rows=forces,observer_events=expected_events)
        assert status=='accepted' and f.encode_state(new).hex()==wires[k],('sealed_reference',k)
        expected_events.append(f.observer_event_digest('energy',f.energy_observer_row(trajectory,96,level,k,new,f.observed_energy(model,new,f.profile_for(96)))))
        assert events[k]==expected_events,('events',k,next((i for i,(a,b) in enumerate(zip(events[k],expected_events)) if a!=b),None),events[k],expected_events)
        group=hashlib.sha256(b''.join(bytes.fromhex(e) for e in expected_events)).hexdigest()
        assert states[k][1]==group,('group',k)
        if event_groups is not None:assert group==event_groups[k-1],('sealed_event',k)
        for inv in invs:
            if inv['stage']=='committed':continue
            wire=stages[k,inv['stage']]
            assert hashlib.sha256(bytes.fromhex(wire)).hexdigest()==inv['state_hash'],('stage',k,inv['stage'])
        # Independently reconstruct the binary64 conversion inputs for both kicks.
        for label,st in ([('first_kick',state),('second_kick',f.decode_state(bytes.fromhex(stages[k,'drift'])))] if path==f.KDK else [('full_kick',state)]):
            evaluated,_=f.force_and_energy(model,st,f.profile_for(96));expected=[]
            with f.profile_for(96).activate() as ctx:
                for g in evaluated:
                    bits=[f.float_bits(float(f.rounded_mul(ctx,96,x,f.profile_for(96).lq,'diagnostic'))) for x in g.offset]
                    expected.append(tuple([g.relation.index,*bits,f.float_bits(g.length),f.float_bits(g.extension),f.float_bits(g.conjugate)]))
            assert geometries[k,label]==expected,('geometry',k,label)
        checked+=len(expected_events);state=new
    return dict(steps=len(wires)-1-start,events=checked,state_bytes=True,stage_bytes=True,force_bits=True,event_hashes=True)

def run(exe,parent,out,limit=None):
    out.mkdir(parents=True,exist_ok=False)
    assert hashlib.sha256((parent/'manifest.json').read_bytes()).hexdigest()==MANIFEST
    assert json.loads((parent/'manifest.json').read_text())['source_sha']==PARENT
    for name,entry in json.loads((parent/'manifest.json').read_text())['files'].items():
        target=parent/name
        assert target.is_file() and target.stat().st_size==entry['size'],('parent_size',name)
        with target.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==entry['sha256'],('parent_hash',name)
    primitives(exe,out)
    models,mids,_=initial_models(parent/'parent');inventory=[]
    for scope,scenarios in [('short',f.SCENARIOS),('long',('k4_internal','k4_boosted'))]:
        for scenario in scenarios:
            for level in range(5):
                for path in ((f.KDK,f.CONTROL) if scope=='short' else (f.KDK,)):
                    name=f'{scenario}-L{level}'+('-'+path if scope=='short' else '')
                    source=parent/'evidence'/('short' if scope=='short' else 'tails')/(name+'.json')
                    wires=json.loads(source.read_text())['wires']
                    if limit is not None:wires=wires[:limit+1]
                    trajectory='bakeoff-A' if scope=='short' else 'bakeoff-A-long:'+scenario
                    groups=None
                    if path==f.KDK:groups=json.loads((parent/'evidence/event-replay'/f'{scope}-{scenario}-L{level}.json').read_text())['event_groups']
                    name=scope+'-'+name;model=models[mids[scenario]];dt=f.TIMESTEPS_RAW[level]
                    result=invoke(exe,out,name,model,wires[0],trajectory,level,dt,len(wires)-1,path='KDK' if path==f.KDK else 'CONTROL')
                    try:report=compare(result,model,wires,trajectory,level,dt,0,path,groups)
                    except Exception as e:
                        save(out/'first-divergence.json',dict(case=name,reason=repr(e),decision='stop_cpp_kernel_semantic_divergence',promotion='NO_PROMOTION'))
                        raise
                    report['case']=name;inventory.append(report);print(name+' PASS',flush=True)
    save(out/'inventory.json',inventory)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('executable',type=Path);p.add_argument('parent',type=Path);p.add_argument('output',type=Path);p.add_argument('--limit',type=int);a=p.parse_args()
    run(a.executable.resolve(),a.parent.resolve(),a.output.resolve(),a.limit)
