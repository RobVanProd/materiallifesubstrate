"""Closed local evidence and offline rebuild/replay for quarantined World parity."""
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

DECISION='retain_cpp_kernel_world_integration_for_research'
MUTANTS={'omitted_transition','double_transition','legacy_double_drift','premature_clock','failed_step_commit','checkpoint_omission','changed_packet_id','observer_feedback'}

def audit(work,parent,sha):
    r=json.loads((work/'gcc/result.json').read_text());assert r['source_sha']==sha
    expected=w.report_check(r)
    assert w.report_check(json.loads((work/'clang-result.json').read_text()))==expected
    primary=parent/'evidence/gcc/full'
    for row in r['rows']:
        name=row['case'];out=work/'gcc'/(name+'.output');reference=primary/(name+'.output')
        assert out.read_bytes()==reference.read_bytes()
        assert w.digest(out)==row['stream_sha256']
        assert out.read_bytes()==(work/'gcc'/(name+'.twin')).read_bytes()
        cp=work/'gcc'/(name+'.checkpoint')
        assert w.digest(cp)==row['checkpoint_sha256']
        assert cp.read_bytes()==(work/'gcc'/(name+'.twin-checkpoint')).read_bytes()
        head=(primary/(name+'.input')).read_text().splitlines()[0].split();count=int(head[4]);start=int(head[5]);mid=start+max(1,count//2)
        lines=out.read_text().splitlines();wire=next(x.split()[2] for x in lines if x.startswith(f'S {mid} '))
        suffix=[f'S {mid} {wire} -']+[x for x in lines if int(x.split()[1])>mid]
        resumed=work/'gcc'/(name+'.resume');assert resumed.read_text().splitlines()==suffix and w.digest(resumed)==row['resume_sha256']
        assert json.loads((work/'gcc'/(name+'.contracts')).read_text())['status']=='PASS'
    for row in r['negatives']:
        name=row['case'];out=work/'gcc'/(name+'.output')
        assert out.read_bytes()==(parent/'evidence/gcc/tests'/(name+'.output')).read_bytes()
        assert w.digest(out)==row['stream_sha256']
        assert json.loads((work/'gcc'/(name+'.contracts')).read_text())==dict(status='PASS',atomic_rejection=True)
    mutants=json.loads((work/'source-mutations/result.json').read_text())
    assert mutants['status']=='PASS' and len(mutants['mutations'])==8 and {x['name'] for x in mutants['mutations']}==MUTANTS
    for x in mutants['mutations']:
        assert x['rejected'] is True and x['exit_code']!=0
        assert w.digest(work/'source-mutations'/x['name']/'mutant.cpp')==x['source_sha256']
    assert 'World integration build quarantine: PASS' in (work/'gcc-configure.log').read_text()
    legacy=(work/'legacy-tests.log').read_text()
    assert '100% tests passed' in legacy and 'mls.world_research_legacy_validation' in legacy and 'mls.validation' in legacy
    assert json.loads((work/'inventory-mutations.json').read_text())['status']=='PASS'
    kernel.ci_check(json.loads((work/'ci/final-run.json').read_text()),sha)
    reports=list((work/'ci/final-artifacts').rglob('result.json'));assert len(reports)==3
    for path in reports:
        compiled=json.loads(path.read_text());assert compiled['source_sha']==sha
        assert w.report_check(compiled)==expected,('compiler World bytes differ',path)
    return dict(decision=DECISION,promotion='NO_PROMOTION',inherited_precision=96,inherited_integrator='KDK',short_trajectories=30,long_trajectories=10,long_steps=15872,long_kdk_stages=47616,twins=40,complete_checkpoint_suffixes=40,compiled_source_mutations=8,atomic_rejection_controls=3,default_world_activation=False)

def build(repo,parent,work,out):
    assert not out.exists(),'never replace a seal or failed seal attempt'
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    w.authenticate(parent,repo);result=audit(work,parent,sha)
    out.mkdir(parents=True);(out/'source').mkdir()
    archive=subprocess.check_output(['git','archive',sha],cwd=repo)
    with tarfile.open(fileobj=io.BytesIO(archive)) as t:t.extractall(out/'source',filter='data')
    shutil.copytree(parent,out/'parent');shutil.copytree(work,out/'evidence')
    (out/'result.json').write_bytes(base.encode(result))
    manifest=dict(schema='mls.world-mechanics-integration.manifest.v1',source_sha=sha,parent_sha=w.PARENT,decision=DECISION,promotion='NO_PROMOTION',files=base.files(out))
    (out/'manifest.json').write_bytes(base.encode(manifest))
    (out/'outer-seal.json').write_bytes(base.encode(dict(source_sha=sha,manifest_sha256=w.digest(out/'manifest.json'),payload_files=len(manifest['files']),promotion='NO_PROMOTION')))
    return check(out)

def check(root):
    m=json.loads((root/'manifest.json').read_text());s=json.loads((root/'outer-seal.json').read_text())
    assert base.files(root)==m['files'] and w.digest(root/'manifest.json')==s['manifest_sha256']
    assert s['source_sha']==m['source_sha'] and s['payload_files']==len(m['files'])
    assert m['parent_sha']==w.PARENT and m['decision']==DECISION and m['promotion']==s['promotion']=='NO_PROMOTION'
    w.authenticate(root/'parent',root/'source')
    allowed={'CMakeLists.txt','tests/CMakeLists.txt','include/mls/world.hpp','src/world.cpp','src/checkpoint.cpp'}
    for old in (root/'parent/source').rglob('*'):
        if old.is_file():
            rel=str(old.relative_to(root/'parent/source'))
            if rel not in allowed:assert w.digest(old)==w.digest(root/'source'/rel),('unrelated inherited source change',rel)
    result=audit(root/'evidence',root/'parent',m['source_sha']);assert result==json.loads((root/'result.json').read_text())
    return dict(status='PASS',source_sha=m['source_sha'],payload_files=len(m['files']),**result)

def pack(root,target):
    check(root);assert not target.exists()
    with target.open('xb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0,compresslevel=9) as gz,tarfile.open(fileobj=gz,mode='w|',format=tarfile.PAX_FORMAT) as t:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                info=t.gettarinfo(str(path),str(Path(root.name)/path.relative_to(root)));info.uid=info.gid=0;info.uname=info.gname='';info.mode=0o644;info.mtime=0
                with path.open('rb') as f:t.addfile(info,f)
    return dict(size=target.stat().st_size,sha256=w.digest(target))

def replay(root):
    identity=check(root);tmp=Path(tempfile.mkdtemp(prefix='mls-world-replay-'));source=root/'source'
    with tarfile.open(root/'parent/dependencies/boost_1_83_0.tar.bz2') as t:t.extractall(tmp,filter='data')
    build=tmp/'build'
    commands=[['cmake','-S',str(source),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release','-DMLS_BUILD_WORLD_MECHANICS_LAB=ON','-DBoost_NO_BOOST_CMAKE=ON','-DBOOST_ROOT='+str(tmp/'boost_1_83_0')],
              ['cmake','--build',str(build),'--target','mls_world_mechanics_lab','mls_validation','mls_world_research_validation','--config','Release','--parallel','2'],
              ['ctest','--test-dir',str(build),'-C','Release','--output-on-failure','-R',r'^mls\.(validation|world_research_legacy_validation)$']]
    for i,cmd in enumerate(commands):
        with (tmp/f'build-{i}.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    executables=[p for p in build.rglob('mls_world_mechanics_lab*') if p.is_file() and p.name in ('mls_world_mechanics_lab','mls_world_mechanics_lab.exe')];assert len(executables)==1
    r=w.run(executables[0],root/'parent',tmp/'replay',source)
    expected=json.loads((root/'evidence/gcc/result.json').read_text());assert w.report_check(r)==w.report_check(expected)
    check(root)
    return dict(identity=identity,fresh_world_invocations=175,legacy_validation_targets=2,complete_scientific_and_checkpoint_bytes=True,replay_directory=str(tmp),older_parent_optional_full_replays=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build')
    for n in ('repo','parent','work','output'):b.add_argument(n,type=Path)
    for n in ('check','replay'):b=sub.add_parser(n);b.add_argument('root',type=Path)
    b=sub.add_parser('pack');b.add_argument('root',type=Path);b.add_argument('target',type=Path)
    a=p.parse_args()
    if a.command=='build':r=build(a.repo.resolve(),a.parent.resolve(),a.work.resolve(),a.output.resolve())
    elif a.command=='pack':r=pack(a.root.resolve(),a.target.resolve())
    else:r=(check if a.command=='check' else replay)(a.root.resolve())
    print(json.dumps(r,sort_keys=True))
