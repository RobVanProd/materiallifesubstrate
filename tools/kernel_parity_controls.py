"""Inherited control inventory plus C++ checkpoint/twin/malformed-input checks."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
import run_authoritative_mechanics_kernel_parity as p
import bakeoff_baseline as b
f=p.f

def generated(model,state,dt,count,level):
    wires=[f.encode_state(state).hex()]
    for k in range(1,count+1):
        status,state=f.one_step(model,state,dt,f.KDK,f.profile_for(96),level=level,step=k)
        assert status=='accepted';wires.append(f.encode_state(state).hex())
    return wires

def controls(exe,parent,out):
    out.mkdir(parents=True,exist_ok=False);models,mids,states=p.initial_models(parent/'parent');rows=[]
    rotations=json.loads((parent/'evidence/short/metamorphic-controls.json').read_text())
    for i,row in enumerate(rotations):
        level=row['level'];dt=f.TIMESTEPS_RAW[level]
        with f.profile_for(96).activate():model,state=b.rotate(models['k4'],states['k4_internal'],row['perm'],row['sign'])
        wires=row['wires'];assert f.encode_state(state).hex()==wires[0]
        name=f'rotation-{i:03d}';result=p.invoke(exe,out,name,model,wires[0],'bakeoff-A',level,dt,len(wires)-1)
        report=p.compare(result,model,wires,'bakeoff-A',level,dt,0,f.KDK);rows.append(dict(case=name,**report));print(name+' PASS',flush=True)
    inherited=json.loads((parent/'evidence/additional/controls.json').read_text())
    for i,row in enumerate(inherited):
        level=row['level'];dt=f.TIMESTEPS_RAW[level];count=f.STEP_COUNTS[level];kind=row['kind'];name=f'additional-{i:03d}-{kind}'
        if kind=='checkpoint':
            # Full phase/event checkpoint identity is tested independently below.
            continue
        if kind=='domain_crossing':
            model=models[mids['domain_crossing']];wire=row['prior_wire']
            result=p.invoke(exe,out,name,model,wire,'bakeoff-A',level,row['dt_raw'],1)
            lines=result.read_text().splitlines();details=[]
            status,_=f.one_step(model,f.decode_state(bytes.fromhex(wire)),row['dt_raw'],f.KDK,f.profile_for(96),failure_details=details)
            assert status==row['status'] and len(details)==1
            d=details[0];keys=('offending_relation_index','chord_minimum_case','comparison_lhs_num','comparison_lhs_den','comparison_rhs_num','comparison_rhs_den','domain_scratch_observed_bits','domain_scratch_limit_bits')
            expected_d='D '+' '.join(str(d[k]) for k in keys)
            assert lines==[f'S 0 {wire} -',expected_d,f'REJECT 1 {row["status"]} {row["returned_wire"]}'],lines
            rows.append(dict(case=name,status=row['status'],atomic=True));print(name+' PASS',flush=True);continue
        if kind=='reverse':
            scenario=row['scenario'];model=models[mids[scenario]]
            record=json.loads((parent/'evidence/short'/f'{scenario}-L{level}-{f.KDK}.json').read_text())
            state=f.decode_state(bytes.fromhex(record['wires'][-1]));dt=-dt;wires=generated(model,state,dt,count,level)
            assert wires[-1]==row['recovered_wire']
        elif kind.startswith('k4_'):
            # The first-packet and COM comparisons share one frozen trajectory.
            scenario=kind.split('-')[0];model=models[mids[scenario]]
            wires=json.loads((parent/'evidence/additional'/f'{scenario}-L{level}.json').read_text())['wires']
        else:
            model=copy.deepcopy(models['k4'])
            if kind=='relation_permutation':
                order=list(reversed(range(len(model.relations))));model.relations=[model.relations[i] for i in order];model.h=[[model.h[i][j] for j in order] for i in order]
            elif kind=='endpoint_reversal':model.relations=[f.exact_lab.Relation(r.index,r.second_id,r.first_id,r.rest_length) for r in model.relations]
            else:assert kind=='packet_permutation'
            wires=json.loads((parent/'evidence/additional'/f'{kind}-L{level}.json').read_text())['wires']
        result=p.invoke(exe,out,name,model,wires[0],'bakeoff-A',level,dt,len(wires)-1)
        report=p.compare(result,model,wires,'bakeoff-A',level,dt,0,f.KDK);rows.append(dict(case=name,**report));print(name+' PASS',flush=True)
    p.save(out/'controls.json',dict(rotations=120,additional_excluding_checkpoints=55,rows=rows))

def replay(exe,parent,full,out):
    out.mkdir(parents=True,exist_ok=False);models,mids,_=p.initial_models(parent/'parent');rows=[]
    for source in sorted(full.glob('*.input')):
        if source.name=='primitives.input':continue
        name=source.stem;tokens=source.read_text().split();trajectory,level,dt,count,start,path=tokens[1:7]
        level,dt,count,start=map(int,(level,dt,count,start));wire=tokens[7]
        modelname=name.split('-L')[0].split('-',1)[1];model=models[mids[modelname]]
        original=source.with_suffix('.output').read_bytes();twin=out/(name+'.twin')
        subprocess.run([str(exe),str(source),str(twin)],check=True);assert twin.read_bytes()==original,('twin',name)
        text=original.decode().splitlines();states={int(v[1]):v[2] for line in text if (v:=line.split())[0]=='S'};mid=count//2
        resumed=p.invoke(exe,out,name+'-resume',model,states[mid],trajectory,level,dt,count-mid,mid,path)
        expected=[f'S {mid} {states[mid]} -']+[line for line in text if int(line.split()[1])>mid]
        assert resumed.read_text().splitlines()==expected,('checkpoint_complete_events',name)
        rows.append(dict(case=name,steps=count,twin_sha256=hashlib.sha256(original).hexdigest(),checkpoint=mid,passed=True))
        print(name+' twin + complete checkpoint PASS',flush=True)
    p.save(out/'replay.json',rows)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['controls','replay']);ap.add_argument('executable',type=Path);ap.add_argument('parent',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--full',type=Path);a=ap.parse_args()
    if a.mode=='controls':controls(a.executable.resolve(),a.parent.resolve(),a.output.resolve())
    else:replay(a.executable.resolve(),a.parent.resolve(),a.full.resolve(),a.output.resolve())
