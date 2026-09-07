"""Noncausal World/accepted-kernel byte comparison and ownership controls."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode=True
import kernel_parity_bundle as parent_bundle

PARENT='e2f37a6f5d48432eb909b0a42948868c9771b036'
MANIFEST='fc81fd9d1c373eeb9775394b4864405a2ae0b8a6202df671000cf00d5a08115f'
ARCHIVE='89558130222a5cf33353b01e71f06cf93437ab446652cbea93577c1d6f7e75e2'
FROZEN=('src/authoritative_mechanics_kernel_parity_lab.cpp','include/mls/authoritative_mechanics_kernel_parity_lab.hpp','apps/authoritative_mechanics_kernel_parity.cpp')

def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(path,value):
    with path.open('x') as f:json.dump(value,f,sort_keys=True);f.write('\n')
def authenticate(parent,source):
    assert digest(parent/'manifest.json')==MANIFEST
    identity=parent_bundle.check(parent);assert identity['source_sha']==PARENT
    for rel in FROZEN:assert digest(source/rel)==digest(parent/'source'/rel),('changed kernel',rel)
    for rel in ('include/mls/world.hpp','src/world.cpp','src/checkpoint.cpp'):
        new=(source/rel).read_text();old=(parent/'source'/rel).read_text()
        stripped=re.sub(r'^#ifdef MLS_RESEARCH_WORLD_MECHANICS\n.*?^#endif\n','',new,flags=re.M|re.S)
        assert [line for line in stripped.splitlines() if line.strip()]==[line for line in old.splitlines() if line.strip()],('changed legacy World code outside quarantine',rel)
    return identity
def call(exe,args,log,ok=True):
    result=subprocess.run([str(exe),*map(str,args)],capture_output=True)
    log.write_bytes(result.stdout+result.stderr)
    assert (result.returncode==0)==ok,(args,result.returncode,result.stderr.decode(errors='replace'))
def same(actual,expected):
    a=actual.read_bytes();b=expected.read_bytes()
    if a!=b:
        lines_a=a.splitlines();lines_b=b.splitlines()
        line=next((i for i,(x,y) in enumerate(zip(lines_a,lines_b)) if x!=y),min(len(lines_a),len(lines_b)))
        raise AssertionError(dict(first_line=line,actual=lines_a[line].decode() if line<len(lines_a) else 'EOF',expected=lines_b[line].decode() if line<len(lines_b) else 'EOF'))
def run(exe,parent,out,source,limit=None):
    out.mkdir(parents=True,exist_ok=False)
    authenticate(parent,source)
    original=json.loads((parent/'evidence/gcc/result.json').read_text())
    expected=parent_bundle.report_check(original)
    rows=[]
    try:
        for name in sorted(expected):
            inp=parent/'evidence/gcc/full'/(name+'.input');reference=inp.with_suffix('.output')
            header=inp.read_text().splitlines()[0].split();count=int(header[4]);start=int(header[5])
            if limit is not None and len(rows)>=limit:break
            dst=out/(name+'.output');cp=out/(name+'.checkpoint')
            call(exe,['--research-world-mechanics','run',inp,dst,cp],out/(name+'.log'))
            same(dst,reference)
            twin=out/(name+'.twin');twin_cp=out/(name+'.twin-checkpoint')
            call(exe,['--research-world-mechanics','run',inp,twin,twin_cp],out/(name+'.twin-log'))
            same(twin,dst);same(cp,twin_cp)
            mid=start+max(1,count//2);resume=out/(name+'.resume')
            call(exe,['--research-world-mechanics','resume',cp,start+count-mid,resume],out/(name+'.resume-log'))
            full=reference.read_text().splitlines()
            wire=next(s.split()[2] for s in full if s.startswith(f'S {mid} '))
            suffix=[f'S {mid} {wire} -']+[s for s in full if int(s.split()[1])>mid]
            assert resume.read_text().splitlines()==suffix,('checkpoint suffix',name)
            contracts=out/(name+'.contracts')
            call(exe,['--research-world-mechanics','contracts',inp,contracts],out/(name+'.contracts-log'))
            assert json.loads(contracts.read_text())['status']=='PASS'
            row=dict(case=name,steps=count,stream_sha256=digest(dst),checkpoint_sha256=digest(cp),resume_sha256=digest(resume),twins=True,checkpoint_suffix=True,world_contracts=True)
            assert row['stream_sha256']==expected[name]
            rows.append(row);save(out/(name+'.receipt.json'),row)
            print('PASS',name,flush=True)
        negatives=[]
        for name in ('atomic-domain','coincidence','phase-underflow'):
            inp=parent/'evidence/gcc/tests'/(name+'.input');dst=out/(name+'.output')
            call(exe,['--research-world-mechanics','run',inp,dst,out/(name+'.unused-checkpoint')],out/(name+'.log'))
            same(dst,inp.with_suffix('.output'))
            control=out/(name+'.contracts')
            call(exe,['--research-world-mechanics','contracts',inp,control],out/(name+'.contracts-log'))
            assert json.loads(control.read_text())==dict(status='PASS',atomic_rejection=True)
            negatives.append(dict(case=name,atomic=True,stream_sha256=digest(dst)))
        for i in range(8):
            inp=parent/'evidence/gcc/tests'/f'bad-wire-{i}.input'
            call(exe,['--research-world-mechanics','run',inp,out/f'bad-{i}.output',out/f'bad-{i}.checkpoint'],out/f'bad-{i}.log',False)
        call(exe,['run','missing','missing'],out/'runtime-disabled.log',False)
    except BaseException as e:
        save(out/'first-divergence.json',dict(disposition='stop_world_kernel_semantic_divergence_or_contract_failure',completed_cases=[r['case'] for r in rows],error=repr(e)))
        raise
    result=dict(status='PASS',source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip() if (source/'.git').exists() else 'bundled-source',promotion='NO_PROMOTION',parent=PARENT,rows=rows,negatives=negatives,bad_wire_rejections=8,runtime_disabled=True)
    save(out/'result.json',result);return result

def report_check(r):
    assert r['status']=='PASS' and r['promotion']=='NO_PROMOTION' and r['parent']==PARENT
    names={f'short-{s}-L{l}-{m}' for s in parent_bundle.parity.f.SCENARIOS for l in range(5) for m in (parent_bundle.parity.f.KDK,parent_bundle.parity.f.CONTROL)}|{f'long-{s}-L{l}' for s in ('k4_internal','k4_boosted') for l in range(5)}
    assert len(r['rows'])==40 and {x['case'] for x in r['rows']}==names
    assert sum(x['steps'] for x in r['rows'] if x['case'].startswith('short-'))==2976
    assert sum(x['steps'] for x in r['rows'] if x['case'].startswith('long-'))==15872
    assert all(x['twins'] and x['checkpoint_suffix'] and x['world_contracts'] for x in r['rows'])
    assert len(r['negatives'])==3 and {x['case'] for x in r['negatives']}=={'atomic-domain','coincidence','phase-underflow'} and all(x['atomic'] for x in r['negatives'])
    assert r['bad_wire_rejections']==8 and r['runtime_disabled'] is True
    return {x['case']:(x['stream_sha256'],x['checkpoint_sha256'],x['resume_sha256']) for x in r['rows']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('executable',type=Path);p.add_argument('parent',type=Path);p.add_argument('output',type=Path);p.add_argument('--limit',type=int);a=p.parse_args()
    run(a.executable.resolve(),a.parent.resolve(),a.output.resolve(),Path(__file__).resolve().parents[1],a.limit)
