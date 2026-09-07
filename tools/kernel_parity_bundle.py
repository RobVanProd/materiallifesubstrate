"""Local-only, closed-source kernel parity sealing and offline executable replay."""
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
import bounded_integrator_bakeoff_bundle as parent_bundle
import run_authoritative_mechanics_kernel_parity as parity
import kernel_parity_ci as ci

DECISION='retain_cpp_b96_path_b_kdk_kernel_parity_for_research'
JOBS={'C++ / Linux GCC','C++ / Linux Clang','C++ / Windows MSVC','Python exact oracle','Pinned Lean build and axiom output'}

def ci_check(record,sha):
    assert record['headSha']==sha and record['status']=='completed' and record['conclusion']=='success'
    assert {j['name'] for j in record['jobs']}==JOBS
    assert all(j['conclusion']=='success' and j['status']=='completed' for j in record['jobs'])

def report_check(report):
    assert report['status']=='PASS' and report['promotion']=='NO_PROMOTION'
    full=report['full'];assert len(full)==40 and len({r['case'] for r in full})==40
    expected={f'short-{s}-L{l}-{method}' for s in parity.f.SCENARIOS for l in range(5) for method in (parity.f.KDK,parity.f.CONTROL)}|{f'long-{s}-L{l}' for s in ('k4_internal','k4_boosted') for l in range(5)}
    assert {r['case'] for r in full}==expected
    assert sum(r['steps'] for r in full if r['case'].startswith('long-'))==15872
    assert sum(r['steps'] for r in full if r['case'].startswith('short-'))==2976
    for row in full:assert all(row[k] is True for k in ('state_bytes','stage_bytes','force_bits','event_hashes'))
    controls=report['controls'];assert controls['rotations']==120 and controls['additional_excluding_checkpoints']==55 and len(controls['rows'])==175
    assert len({r['case'] for r in controls['rows']})==175
    for r in controls['rows']:
        if r.get('atomic'):assert r['status']=='chord_domain_failure'
        else:assert all(r[k] is True for k in ('state_bytes','stage_bytes','force_bits','event_hashes'))
    assert len(report['replay'])==40 and all(r['passed'] is True for r in report['replay'])
    assert {r['case'] for r in report['replay']}=={r['case'] for r in full}
    assert report['tests']['status']=='PASS'
    return {r['case']:r['twin_sha256'] for r in report['replay']}

def audit(evidence,sha):
    local=json.loads((evidence/'gcc/result.json').read_text());expected=report_check(local)
    clang=json.loads((evidence/'clang-result.json').read_text());assert report_check(clang)==expected
    for case,digest in expected.items():assert base.digest(evidence/'gcc/full'/(case+'.output'))==digest
    # A complete checkpoint suffix is tied to its primary raw scientific stream.
    for row in local['replay']:
        name=row['case'];mid=row['checkpoint'];lines=(evidence/'gcc/full'/(name+'.output')).read_text().splitlines()
        state=next(s.split()[2] for s in lines if s.startswith(f'S {mid} '))
        target=[f'S {mid} {state} -']+[s for s in lines if int(s.split()[1])>mid]
        assert (evidence/'gcc/replay'/(name+'-resume.output')).read_text().splitlines()==target
        assert base.digest(evidence/'gcc/replay'/(name+'.twin'))==expected[name]
    controls=json.loads((evidence/'source-mutations/result.json').read_text());assert controls['status']=='PASS'
    assert len(controls['mutations'])==7 and all(r['rejected'] and r['exit_code']!=0 for r in controls['mutations'])
    ci_check(json.loads((evidence/'ci/final-run.json').read_text()),sha)
    candidates=list((evidence/'ci/final-artifacts').rglob('result.json'))
    assert len(candidates)==3,('CI parity inventory',candidates)
    for path in candidates:
        report=json.loads(path.read_text());assert report['source_sha']==sha
        assert report_check(report)==expected,('cross-platform scientific bytes',path)
    return dict(decision=DECISION,selected_precision=96,promotion='NO_PROMOTION',short_trajectories=30,long_trajectories=10,
                long_steps=15872,long_kdk_stages=47616,rotations=120,additional_controls=70,checkpoint_and_twin_cases=40,
                compiler_parity=['GCC','Clang','MSVC'],first_primitive_failure_preserved=True)

def build(repo,parent,work,boost,output):
    assert not output.exists(),'never overwrite a seal or attempted seal'
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    result=audit(work,sha)
    assert base.digest(parent/'manifest.json')==parity.MANIFEST and base.digest(boost)==ci.BOOST_HASH
    output.mkdir(parents=True);(output/'source').mkdir()
    archive=subprocess.check_output(['git','archive',sha],cwd=repo)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(output/'source',filter='data')
    shutil.copytree(parent,output/'parent');shutil.copytree(work,output/'evidence')
    (output/'dependencies').mkdir();shutil.copyfile(boost,output/'dependencies/boost_1_83_0.tar.bz2')
    (output/'result.json').write_bytes(base.encode(result))
    manifest=dict(schema='mls.kernel-parity.manifest.v1',source_sha=sha,parent_sha=parity.PARENT,
                  promotion='NO_PROMOTION',decision=DECISION,files=base.files(output))
    (output/'manifest.json').write_bytes(base.encode(manifest))
    (output/'outer-seal.json').write_bytes(base.encode(dict(source_sha=sha,manifest_sha256=base.digest(output/'manifest.json'),payload_files=len(manifest['files']),promotion='NO_PROMOTION')))
    return check(output)

def check(root):
    manifest=json.loads((root/'manifest.json').read_text());seal=json.loads((root/'outer-seal.json').read_text())
    assert base.files(root)==manifest['files'] and base.digest(root/'manifest.json')==seal['manifest_sha256']
    assert seal['source_sha']==manifest['source_sha'] and seal['payload_files']==len(manifest['files'])
    assert manifest['parent_sha']==parity.PARENT and manifest['decision']==DECISION
    assert manifest['promotion']==seal['promotion']=='NO_PROMOTION'
    assert base.digest(root/'parent/manifest.json')==parity.MANIFEST
    parent_bundle.check(root/'parent')
    for old in (root/'parent/source').rglob('*'):
        if old.is_file():
            relative=old.relative_to(root/'parent/source');new=root/'source'/relative
            if relative==Path('CMakeLists.txt'):
                text=new.read_text();a=text.index('# Isolated parity lab;');b=text.index('add_library(mls_core',a)
                assert text[:a]+text[b:]==old.read_text(),'unrelated CMake change'
            else:assert base.digest(old)==base.digest(new),('inherited source changed',relative)
    assert base.digest(root/'dependencies/boost_1_83_0.tar.bz2')==ci.BOOST_HASH
    result=audit(root/'evidence',manifest['source_sha']);assert result==json.loads((root/'result.json').read_text())
    return dict(status='PASS',source_sha=manifest['source_sha'],payload_files=len(manifest['files']),**result)

def replay(root):
    identity=check(root);tmp=Path(tempfile.mkdtemp(prefix='mls-kernel-parity-replay-'))
    with tarfile.open(root/'dependencies/boost_1_83_0.tar.bz2') as tar:tar.extractall(tmp,filter='data')
    build=tmp/'build';source=root/'source';env=dict(__import__('os').environ,PYTHONDONTWRITEBYTECODE='1')
    commands=[['cmake','-S',str(source),'-B',str(build),'-DMLS_BUILD_KERNEL_PARITY_LAB=ON','-DCMAKE_BUILD_TYPE=Release','-DBoost_NO_BOOST_CMAKE=ON','-DBOOST_ROOT='+str(tmp/'boost_1_83_0')],
              ['cmake','--build',str(build),'--target','mls_kernel_parity_lab','--config','Release','--parallel','2']]
    for i,cmd in enumerate(commands):
        with (tmp/f'build-{i}.log').open('w') as log:subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    binaries=[p for p in build.rglob('mls_kernel_parity_lab*') if p.is_file() and p.name in ('mls_kernel_parity_lab','mls_kernel_parity_lab.exe')];assert len(binaries)==1
    exe=binaries[0];checked=0
    for path in sorted((root/'evidence/gcc/full').glob('*.input')):
        out=tmp/(path.stem+'.output');subprocess.run([str(exe),str(path),str(out)],env=env,check=True)
        assert out.read_bytes()==path.with_suffix('.output').read_bytes(),('fresh C++ parity',path.name)
        checked+=1
    for directory in ('controls','replay'):
        for path in sorted((root/'evidence/gcc'/directory).glob('*.input')):
            out=tmp/(directory+'-'+path.stem+'.output');subprocess.run([str(exe),str(path),str(out)],env=env,check=True)
            assert out.read_bytes()==path.with_suffix('.output').read_bytes(),('fresh control',path.name)
            checked+=1
    with (tmp/'tests.log').open('w') as log:subprocess.run([sys.executable,str(source/'tests/kernel_parity_test.py'),str(exe),str(root/'parent'),str(tmp/'tests')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    check(root)
    return dict(identity=identity,fresh_compiled_cpp_invocations=checked,boundary_and_mutation_tests=True,replay_directory=str(tmp),earlier_parent_full_replays=False)

def pack(root,target):
    check(root);assert not target.exists()
    with target.open('xb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0,compresslevel=9) as zipped,tarfile.open(fileobj=zipped,mode='w|',format=tarfile.PAX_FORMAT) as tar:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                info=tar.gettarinfo(str(path),str(Path(root.name)/path.relative_to(root)));info.uid=info.gid=0;info.uname=info.gname='';info.mode=0o644;info.mtime=0
                with path.open('rb') as stream:tar.addfile(info,stream)
    return dict(size=target.stat().st_size,sha256=base.digest(target))

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build')
    for k in ('repo','parent','work','boost','output'):b.add_argument(k,type=Path)
    for name in ('check','replay'):
        b=sub.add_parser(name);b.add_argument('root',type=Path)
    b=sub.add_parser('pack');b.add_argument('root',type=Path);b.add_argument('target',type=Path)
    a=p.parse_args()
    if a.command=='build':r=build(a.repo.resolve(),a.parent.resolve(),a.work.resolve(),a.boost.resolve(),a.output.resolve())
    elif a.command=='pack':r=pack(a.root.resolve(),a.target.resolve())
    else:r=(check if a.command=='check' else replay)(a.root.resolve())
    print(json.dumps(r,sort_keys=True))
