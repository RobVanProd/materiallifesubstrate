"""Noncausal complete-stream, material ownership and neutral-operation audit."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
import world_mechanics_parity as w
import world_mechanics_bundle as parent_bundle
import material_phase_checkpoint as checkpoint

PARENT='64a5fb7cbb6355d6aa8ad32ec4ef5ca2a5ab138f'
MANIFEST='5fdca79ff604bb4755c7a57b6e906d7e41c23f7d428ccf5cf0f31f9de1ae9eca'
ARCHIVE='ce3d4eb4e95131415f83cfac1f65e2ba061c2905f0e5db147c5663ce90d83e05'
SIZE=905443734
DECISION='retain_single_authority_material_mechanics_world_state_for_research'

def authenticate(parent,source):
    assert w.digest(parent/'manifest.json')==MANIFEST
    identity=parent_bundle.check(parent);assert identity['source_sha']==PARENT
    for rel in w.FROZEN:
        assert w.digest(source/rel)==w.digest(parent/'source'/rel),('changed frozen kernel',rel)
    return identity

def report_check(r):
    assert r['status']=='PASS' and r['promotion']=='NO_PROMOTION' and r['parent']==PARENT
    inherited=dict(r,parent=w.PARENT)
    names=w.report_check(inherited)
    assert all(x['neutral_parity'] and x['neutral_resume'] and x['final_state_replay'] for x in r['rows'])
    assert r['invocations']==255
    return {x['case']:tuple(x[k] for k in ('stream_sha256','checkpoint_sha256','resume_sha256','final_sha256','neutral_checkpoint_sha256','neutral_final_sha256')) for x in r['rows']}

def run(exe,parent,out,source):
    out.mkdir(parents=True,exist_ok=False);authenticate(parent,source)
    sealed=json.loads((parent/'evidence/gcc/result.json').read_text());expected=w.report_check(sealed)
    inputs=parent/'parent/evidence/gcc/full';rows=[];calls=0
    def call(args,log,ok=True):
        nonlocal calls
        calls+=1;w.call(exe,args,log,ok)
    try:
        for name in sorted(expected):
            inp=inputs/(name+'.input');reference=parent/'evidence/gcc'/(name+'.output')
            header=inp.read_text().splitlines()[0].split();count=int(header[4]);start=int(header[5]);mid=start+max(1,count//2-1)
            full=reference.read_text().splitlines();wire=next(s.split()[2] for s in full if s.startswith(f'S {mid} '))
            suffix=[f'S {mid} {wire} -']+[s for s in full if int(s.split()[1])>mid]
            for mode,ext,cp in [('run','output','checkpoint'),('run','twin','twin-checkpoint'),('neutral','neutral','neutral-checkpoint')]:
                call(['--research-material-phase',mode,inp,out/(name+'.'+ext),out/(name+'.'+cp)],out/(name+'.'+ext+'.log'))
                w.same(out/(name+'.'+ext),reference)
            w.same(out/(name+'.checkpoint'),out/(name+'.twin-checkpoint'))
            assert (out/(name+'.neutral-checkpoint')).read_bytes()!=(out/(name+'.checkpoint')).read_bytes(),('neutral checkpoint must retain nontrivial material change',name)
            w.same(out/(name+'.output.final'),out/(name+'.twin.final'))
            final_wire=next(s.split()[2] for s in full if s.startswith(f'S {start+count} '))
            for ext,target,target_step,changed in [('checkpoint',wire,mid,False),('neutral-checkpoint',wire,mid,True),('output.final',final_wire,start+count,False),('neutral.final',final_wire,start+count,True)]:
                checkpoint.check((out/(name+'.'+ext)).read_bytes(),target,target_step,int(header[3]),changed)
            for mode,cp,ext,final in [('resume','checkpoint','resume','output'),('resume-neutral','neutral-checkpoint','neutral-resume','neutral')]:
                dst=out/(name+'.'+ext)
                call(['--research-material-phase',mode,out/(name+'.'+cp),start+count-mid,dst],out/(name+'.'+ext+'.log'))
                assert dst.read_text().splitlines()==suffix,('complete suffix mismatch',name,mode)
                w.same(out/(name+'.'+ext+'.final'),out/(name+'.'+final+'.final'))
            contracts=out/(name+'.contracts');call(['--research-material-phase','contracts',inp,contracts],out/(name+'.contracts.log'))
            assert json.loads(contracts.read_text())==dict(status='PASS',single_authority=True,explicit_binding=True,exact_material_ledger=True,neutral_coexistence=True,checkpoint_mutations=6)
            row=dict(case=name,steps=count,twins=True,checkpoint_suffix=True,world_contracts=True,neutral_parity=True,neutral_resume=True,final_state_replay=True,
                stream_sha256=w.digest(out/(name+'.output')),checkpoint_sha256=w.digest(out/(name+'.checkpoint')),resume_sha256=w.digest(out/(name+'.resume')),
                final_sha256=w.digest(out/(name+'.output.final')),neutral_checkpoint_sha256=w.digest(out/(name+'.neutral-checkpoint')),neutral_final_sha256=w.digest(out/(name+'.neutral.final')))
            rows.append(row);w.save(out/(name+'.receipt.json'),row);print('PASS',name,flush=True)
        negatives=[];tests=parent/'parent/evidence/gcc/tests'
        for name in ('atomic-domain','coincidence','phase-underflow'):
            inp=tests/(name+'.input');dst=out/(name+'.output')
            call(['--research-material-phase','run',inp,dst,out/(name+'.unused-checkpoint')],out/(name+'.log'));w.same(dst,tests/(name+'.output'))
            contract=out/(name+'.contracts');call(['--research-material-phase','contracts',inp,contract],out/(name+'.contracts.log'))
            assert json.loads(contract.read_text())==dict(status='PASS',atomic_rejection=True)
            negatives.append(dict(case=name,atomic=True,stream_sha256=w.digest(dst)))
        for n in range(8):
            call(['--research-material-phase','run',tests/f'bad-wire-{n}.input',out/f'bad-{n}.output',out/f'bad-{n}.checkpoint'],out/f'bad-{n}.log',False)
        call(['run','missing','missing'],out/'runtime-disabled.log',False)
    except BaseException as e:
        w.save(out/'first-divergence.json',dict(completed_cases=[r['case'] for r in rows],error=repr(e)));raise
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip() if (source/'.git').exists() else 'bundled-source'
    result=dict(status='PASS',source_sha=sha,parent=PARENT,promotion='NO_PROMOTION',rows=rows,negatives=negatives,bad_wire_rejections=8,runtime_disabled=True,invocations=calls)
    report_check(result);w.save(out/'result.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('executable',type=Path);p.add_argument('parent',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    run(a.executable.resolve(),a.parent.resolve(),a.output.resolve(),Path(__file__).resolve().parents[1])
