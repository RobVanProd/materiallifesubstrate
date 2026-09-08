"""Closed local material/phase evidence and fresh offline executable replay."""
import argparse
import gzip
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
sys.dont_write_bytecode=True
import bounded_phase_tail_bundle as base
import kernel_parity_bundle as kernel
import world_mechanics_parity as w
import material_phase_parity as m
import material_phase_checkpoint as checkpoint

MUTANTS={'swapped_identity','stale_binding','incorrect_mass','duplicate_phase_authority','legacy_coordinate_feedback','omitted_phase_state','observer_feedback','corrupted_binding'}
ALLOWED={'CMakeLists.txt','tests/CMakeLists.txt','include/mls/world.hpp','include/mls/packet_store.hpp','src/world.cpp','src/packet_store.cpp','src/checkpoint.cpp','src/world_mechanics_integration_lab.cpp'}

def audit(work,parent,sha):
    r=json.loads((work/'gcc/result.json').read_text());assert r['source_sha']==sha;expected=m.report_check(r)
    clang=json.loads((work/'clang-result.json').read_text());assert clang['source_sha']==sha and m.report_check(clang)==expected
    for row in r['rows']:
        name=row['case'];reference=parent/'evidence/gcc'/(name+'.output');out=work/'gcc'/(name+'.output')
        assert out.read_bytes()==reference.read_bytes() and w.digest(out)==row['stream_sha256']
        for ext in ('twin','neutral'):assert (work/'gcc'/(name+'.'+ext)).read_bytes()==out.read_bytes()
        for left,right in [('checkpoint','twin-checkpoint'),('output.final','twin.final'),('output.final','resume.final'),('neutral.final','neutral-resume.final')]:
            assert (work/'gcc'/(name+'.'+left)).read_bytes()==(work/'gcc'/(name+'.'+right)).read_bytes()
        assert (work/'gcc'/(name+'.checkpoint')).read_bytes()!=(work/'gcc'/(name+'.neutral-checkpoint')).read_bytes()
        for field,ext in [('checkpoint_sha256','checkpoint'),('resume_sha256','resume'),('final_sha256','output.final'),('neutral_checkpoint_sha256','neutral-checkpoint'),('neutral_final_sha256','neutral.final')]:assert w.digest(work/'gcc'/(name+'.'+ext))==row[field]
        header=(parent/'parent/evidence/gcc/full'/(name+'.input')).read_text().splitlines()[0].split();start=int(header[5]);count=int(header[4]);dt=int(header[3]);mid=start+max(1,count//2-1)
        lines=reference.read_text().splitlines();wire=next(s.split()[2] for s in lines if s.startswith(f'S {mid} '));final=next(s.split()[2] for s in lines if s.startswith(f'S {start+count} '))
        suffix=[f'S {mid} {wire} -']+[s for s in lines if int(s.split()[1])>mid]
        for ext in ('resume','neutral-resume'):assert (work/'gcc'/(name+'.'+ext)).read_text().splitlines()==suffix
        for ext,target,step,neutral in [('checkpoint',wire,mid,False),('neutral-checkpoint',wire,mid,True),('output.final',final,start+count,False),('neutral.final',final,start+count,True)]:checkpoint.check((work/'gcc'/(name+'.'+ext)).read_bytes(),target,step,dt,neutral)
        assert json.loads((work/'gcc'/(name+'.contracts')).read_text())==dict(status='PASS',single_authority=True,explicit_binding=True,exact_material_ledger=True,neutral_coexistence=True,checkpoint_mutations=6)
    for row in r['negatives']:
        name=row['case'];out=work/'gcc'/(name+'.output');assert out.read_bytes()==(parent/'parent/evidence/gcc/tests'/(name+'.output')).read_bytes() and w.digest(out)==row['stream_sha256']
        assert json.loads((work/'gcc'/(name+'.contracts')).read_text())==dict(status='PASS',atomic_rejection=True)
    mutants=json.loads((work/'source-mutations/result.json').read_text());assert mutants['status']=='PASS' and len(mutants['mutations'])==8 and {x['name'] for x in mutants['mutations']}==MUTANTS
    for x in mutants['mutations']:assert x['rejected'] and x['exit_code']!=0 and w.digest(work/'source-mutations'/x['name']/'mutant.cpp')==x['source_sha256']
    assert 'Material phase build quarantine and no legacy phase fields: PASS' in (work/'gcc-configure.log').read_text()
    legacy=(work/'legacy-tests.log').read_text();assert '100% tests passed' in legacy and 'mls.material_phase_legacy_validation' in legacy
    for name,n in [('inventory-mutations.json',13),('checkpoint-mutations.json',10)]:
        value=json.loads((work/name).read_text());assert value['status']=='PASS' and len(value['rejected'])==n
    kernel.ci_check(json.loads((work/'ci/final-run.json').read_text()),sha)
    paths=list((work/'ci/final-artifacts').rglob('result.json'));assert len(paths)==3
    for path in paths:
        compiled=json.loads(path.read_text());assert compiled['source_sha']==sha and m.report_check(compiled)==expected
    return dict(decision=m.DECISION,promotion='NO_PROMOTION',inherited_precision=96,inherited_integrator='KDK',short_trajectories=30,long_trajectories=10,long_steps=15872,long_kdk_stages=47616,twins=40,neutral_trajectories=40,checkpoint_suffixes=80,independent_material_checkpoint_checks=160,compiled_source_mutations=8,default_world_activation=False)

def check(root):
    manifest=json.loads((root/'manifest.json').read_text());seal=json.loads((root/'outer-seal.json').read_text())
    assert w.files(root)==manifest['files'] and w.digest(root/'manifest.json')==seal['manifest_sha256']
    assert manifest['source_sha']==seal['source_sha'] and manifest['parent_sha']==m.PARENT and manifest['decision']==m.DECISION
    assert manifest['promotion']==seal['promotion']=='NO_PROMOTION' and seal['payload_files']==len(manifest['files'])
    m.authenticate(root/'parent',root/'source')
    for old in (root/'parent/source').rglob('*'):
        if old.is_file():
            rel=old.relative_to(root/'parent/source').as_posix()
            if rel not in ALLOWED:assert w.digest(old)==w.digest(root/'source'/rel),('changed inherited source',rel)
    result=audit(root/'evidence',root/'parent',manifest['source_sha']);assert result==json.loads((root/'result.json').read_text())
    return dict(status='PASS',source_sha=manifest['source_sha'],payload_files=seal['payload_files'],**result)

def build(repo,parent,work,out):
    assert not out.exists() and not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();m.authenticate(parent,repo);result=audit(work,parent,sha)
    out.mkdir(parents=True);(out/'source').mkdir()
    with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',sha],cwd=repo))) as t:t.extractall(out/'source',filter='data')
    shutil.copytree(parent,out/'parent');shutil.copytree(work,out/'evidence');(out/'result.json').write_bytes(base.encode(result))
    manifest=dict(schema='mls.material-phase-unification.manifest.v1',source_sha=sha,parent_sha=m.PARENT,decision=m.DECISION,promotion='NO_PROMOTION',files=w.files(out))
    (out/'manifest.json').write_bytes(base.encode(manifest));(out/'outer-seal.json').write_bytes(base.encode(dict(source_sha=sha,promotion='NO_PROMOTION',payload_files=len(manifest['files']),manifest_sha256=w.digest(out/'manifest.json'))));return check(out)

def pack(root,target):
    check(root);assert not target.exists()
    with target.open('xb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0,compresslevel=9) as gz,tarfile.open(fileobj=gz,mode='w|',format=tarfile.PAX_FORMAT) as t:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                info=t.gettarinfo(str(path),(Path(root.name)/path.relative_to(root)).as_posix());info.uid=info.gid=0;info.uname=info.gname='';info.mode=0o644;info.mtime=0
                with path.open('rb') as f:t.addfile(info,f)
    return dict(size=target.stat().st_size,sha256=w.digest(target))

def replay(root):
    identity=check(root);tmp=Path(tempfile.mkdtemp(prefix='mls-material-replay-'));source=root/'source';build=tmp/'build'
    with tarfile.open(root/'parent/parent/dependencies/boost_1_83_0.tar.bz2') as t:t.extractall(tmp,filter='data')
    commands=[['cmake','-S',str(source),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release','-DMLS_BUILD_MATERIAL_PHASE_LAB=ON','-DBoost_NO_BOOST_CMAKE=ON','-DBOOST_ROOT='+str(tmp/'boost_1_83_0')],
      ['cmake','--build',str(build),'--target','mls_material_phase_lab','mls_validation','mls_material_phase_validation','--config','Release','--parallel','2'],
      ['ctest','--test-dir',str(build),'-C','Release','--output-on-failure','-R',r'^mls\.(validation|material_phase_legacy_validation)$']]
    for j,cmd in enumerate(commands):
        with (tmp/f'build-{j}.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    exes=[p for p in build.rglob('mls_material_phase_lab*') if p.is_file() and p.name in ('mls_material_phase_lab','mls_material_phase_lab.exe')];assert len(exes)==1
    r=m.run(exes[0],root/'parent',tmp/'replay',source);assert m.report_check(r)==m.report_check(json.loads((root/'evidence/gcc/result.json').read_text()))
    check(root);return dict(identity=identity,fresh_world_invocations=255,legacy_validation_targets=2,complete_scientific_material_checkpoint_bytes=True,replay_directory=str(tmp),older_parent_optional_full_replays=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True);b=sub.add_parser('build')
    for name in ('repo','parent','work','output'):b.add_argument(name,type=Path)
    for mode in ('check','replay'):sub.add_parser(mode).add_argument('root',type=Path)
    b=sub.add_parser('pack');b.add_argument('root',type=Path);b.add_argument('target',type=Path);a=p.parse_args()
    if a.mode=='build':r=build(a.repo.resolve(),a.parent.resolve(),a.work.resolve(),a.output.resolve())
    elif a.mode=='pack':r=pack(a.root.resolve(),a.target.resolve())
    else:r=(check if a.mode=='check' else replay)(a.root.resolve())
    print(json.dumps(r,sort_keys=True))
