"""Local-only immutable bakeoff packaging. Never creates a tag or release."""
import argparse
import gzip
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
import bakeoff_final_audit as scientific
import bounded_phase_tail_bundle as packaging
import relation_coordinate_defect_tail_bundle as parent_bundle

digest,encode,files=packaging.digest,packaging.encode,packaging.files
PARENT_MANIFEST='6f33d5586dc75250ca4356aedb6cc58da62f8b153e62bf6b4d55e620ea12e818'
BASELINE='c4ac14cdcd46f948c1640535164c5bee400b4811868a572fe3873646cbed06de'
REQUIRED_JOBS={'C++ / Linux GCC','C++ / Linux Clang','C++ / Windows MSVC',
               'Python exact oracle','Pinned Lean build and axiom output'}
INPUTS={
 'controls-a':'bakeoff-controls-development-v2','controls-b':'bakeoff-controls-development-v3',
 'short':'bakeoff-baseline-development-v1','additional':'bakeoff-baseline-controls-development-v3',
 'exact':'bakeoff-baseline-exact-development-v1','tails':'bakeoff-baseline-tails-development-v1',
 'smooth.json':'bakeoff-smooth-development-v1.json','short-analysis.json':'bakeoff-short-analysis-development-v2.json',
 'short-audit.json':'bakeoff-short-audit-development-v2.json','long-audit.json':'bakeoff-long-audit-development-v2.json',
 'midpoint-independent.json':'bakeoff-midpoint-independent-development-v1.json',
 'external-short-timing.json':'bakeoff-short-external-timing-v1.json',
 'parent-full-replay.log':'bakeoff-parent-full-replay.log','lean-axioms.log':'bakeoff-final-lean-axioms.log',
 'prior-lean-axioms.log':'bakeoff-lean-axioms.log',
 'exact-independent.json':'bakeoff-exact-independent-v1.json',
 'exact-independent.log':'bakeoff-exact-independent-v1.log',
 'failures/initial-control-driver':'bakeoff-controls-development-v1',
 'failures/incorrect-domain-duration':'bakeoff-baseline-controls-development-v1',
 'prior-additional-summary':'bakeoff-baseline-controls-development-v2',
 'prior-short-analysis.json':'bakeoff-short-analysis-development-v1.json'}


def ci_check(ci,sha):
    assert ci['headSha']==sha and ci['status']=='completed' and ci['conclusion']=='success','final source CI not green'
    assert {j['name'] for j in ci['jobs']}==REQUIRED_JOBS,'incomplete CI job inventory'
    assert all(j['status']=='completed' and j['conclusion']=='success' for j in ci['jobs']),'required CI job failed'


def prepare(repo,parent,work):
    assert not work.exists(),'never overwrite a work inventory'
    work.mkdir(parents=True)
    for target,original in INPUTS.items():
        src=repo/'build'/original;dst=work/target;dst.parent.mkdir(parents=True,exist_ok=True)
        if src.is_dir():shutil.copytree(src,dst)
        else:shutil.copyfile(src,dst)
    result=scientific.audit(work,parent,deep=True)
    (work/'result.json').write_bytes(encode(result))
    return result


def check(root,repo=None,deep=False):
    manifest=json.loads((root/'manifest.json').read_text());seal=json.loads((root/'outer-seal.json').read_text())
    assert seal['manifest_sha256']==digest(root/'manifest.json')
    assert seal['source_sha']==manifest['source_sha'] and seal['promotion']=='NO_PROMOTION'
    assert files(root)==manifest['files'] and seal['payload_files']==len(manifest['files'])
    assert manifest['parent_sha']==scientific.PARENT and manifest['selected_precision']==96
    assert manifest['decision']==scientific.DECISION and manifest['promotion']=='NO_PROMOTION'
    assert digest(root/'parent/manifest.json')==PARENT_MANIFEST
    parent_bundle.check(root/'parent')
    assert digest(root/'source/tools/run_bounded_fractional_phase_state_lab.py')==BASELINE
    for old in (root/'parent/source').rglob('*'):
        if not old.is_file():continue
        path=old.relative_to(root/'parent/source');new=root/'source'/path
        if str(path)=='formal/MLSFormal/AxiomReport.lean':
            kept=[s for s in new.read_text().splitlines() if s.strip() and 'bakeoff_' not in s
                  and s!='import MLSFormal.BoundedIntegratorBakeoff']
            assert kept==[s for s in old.read_text().splitlines() if s.strip()]
        else:assert digest(new)==digest(old),'inherited source altered: '+str(path)
    ci_check(json.loads((root/'evidence/ci/final-run.json').read_text()),manifest['source_sha'])
    result=scientific.audit(root/'evidence',root/'parent',deep)
    assert result==json.loads((root/'evidence/result.json').read_text())
    if repo:
        sha=manifest['source_sha']
        paths=subprocess.check_output(['git','ls-tree','-r','--name-only',sha],cwd=repo,text=True).splitlines()
        assert set(paths)=={str(p.relative_to(root/'source')) for p in (root/'source').rglob('*') if p.is_file()}
        import hashlib
        for path in paths:
            expected=subprocess.check_output(['git','show',sha+':'+path],cwd=repo)
            assert hashlib.sha256(expected).hexdigest()==digest(root/'source'/path)
    return dict(status='PASS',source_sha=manifest['source_sha'],payload_files=len(manifest['files']),
        decision=scientific.DECISION,selected_precision=96,promotion='NO_PROMOTION',deep_new_arithmetic_replay=deep)


def build(repo,parent,work,output):
    assert not output.exists(),'never replace a sealed or attempted inventory'
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip(),'commit source first'
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    ci_check(json.loads((work/'ci/final-run.json').read_text()),sha)
    assert digest(parent/'manifest.json')==PARENT_MANIFEST
    assert scientific.audit(work,parent)==json.loads((work/'result.json').read_text())
    output.mkdir(parents=True);(output/'source').mkdir()
    archive=subprocess.check_output(['git','archive',sha],cwd=repo)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(output/'source',filter='data')
    shutil.copytree(parent,output/'parent');shutil.copytree(work,output/'evidence')
    manifest=dict(schema='mls.bounded-integrator-bakeoff.manifest.v1',source_sha=sha,
        source_tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=repo,text=True).strip(),
        parent_sha=scientific.PARENT,decision=scientific.DECISION,selected_precision=96,promotion='NO_PROMOTION',files=files(output))
    (output/'manifest.json').write_bytes(encode(manifest))
    (output/'outer-seal.json').write_bytes(encode(dict(schema='mls.bounded-integrator-bakeoff.outer.v1',
        source_sha=sha,manifest_sha256=digest(output/'manifest.json'),payload_files=len(manifest['files']),promotion='NO_PROMOTION')))
    return check(output,repo)


def pack(root,archive):
    check(root);assert not archive.exists(),'never replace an archive'
    with archive.open('xb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=9) as compressed:
        with tarfile.open(fileobj=compressed,mode='w|',format=tarfile.PAX_FORMAT) as tar:
            for path in sorted(root.rglob('*')):
                if not path.is_file():continue
                info=tar.gettarinfo(str(path),str(Path(root.name)/path.relative_to(root)))
                info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0;info.mode=0o644
                with path.open('rb') as stream:tar.addfile(info,stream)
    return dict(size=archive.stat().st_size,sha256=digest(archive))


if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare')
    for name in ('repo','parent','work'):a.add_argument(name,type=Path)
    a=sub.add_parser('build')
    for name in ('repo','parent','work','output'):a.add_argument(name,type=Path)
    a=sub.add_parser('check');a.add_argument('root',type=Path);a.add_argument('--repo',type=Path);a.add_argument('--deep',action='store_true')
    a=sub.add_parser('pack');a.add_argument('root',type=Path);a.add_argument('archive',type=Path)
    a=p.parse_args()
    if a.command=='prepare':result=prepare(a.repo,a.parent,a.work)
    elif a.command=='build':result=build(a.repo,a.parent,a.work,a.output)
    elif a.command=='check':result=check(a.root,a.repo,a.deep)
    else:result=pack(a.root,a.archive)
    print(json.dumps(result,sort_keys=True))
