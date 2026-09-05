"""Closed-inventory, reproducible packaging for the narrow NO_PROMOTION audit."""
import argparse
import gzip
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

PARENT='17532284c2f0878e908f6a613f4c2e3baa47cbcd'
DECISION='stop_certificate_unsound_or_inconclusive'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def encode(obj):return (json.dumps(obj,sort_keys=True,indent=2)+'\n').encode()

def files(root):
    assert not any(p.is_symlink() for p in root.rglob('*'))
    return {str(p.relative_to(root)):dict(size=p.stat().st_size,sha256=digest(p))
            for p in sorted(root.rglob('*')) if p.is_file() and str(p.relative_to(root)) not in ('manifest.json','outer-seal.json')}

def build(repo,parent,output):
    assert not output.exists(),'refusing to replace any existing evidence directory'
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip(),'commit source first'
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=repo,text=True).strip()
    output.mkdir(parents=True)
    source=output/'source';source.mkdir()
    archive=subprocess.check_output(['git','archive',sha],cwd=repo)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(source,filter='data')
    input_files=['oracle/oracle-summary.json',
        *['raw-a/'+name for name in ('reference_packets.csv','relations.csv','force_operator.csv','initial_states.csv','representation_error.csv')],
        'parent-explicit-fractional/raw-a/initial_states.csv']
    for relative in input_files:
        target=output/'inputs'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(parent/relative,target)
    evidence=output/'evidence';evidence.mkdir()
    targets={'stage-one.json':'bounded-phase-tail-stage-one-v2.json',
             'pilot-suite.json':'bounded-phase-tail-pilot-suite-a.json',
             **{f'prefix-internal-L{i}.json':f'bounded-phase-tail-prefix-internal-L{i}.json' for i in (1,2,3,4)},
             'prefix-boosted-L4.json':'bounded-phase-tail-prefix-boosted-L4.json'}
    for name,original in targets.items():shutil.copyfile(repo/'build'/original,evidence/name)
    manifest=dict(schema='mls.bounded-phase-tail.manifest.v1',source_sha=sha,source_tree=tree,
        parent_sha=PARENT,decision=DECISION,selected_precision=None,promotion='NO_PROMOTION',
        full_tails_certified=False,files=files(output))
    (output/'manifest.json').write_bytes(encode(manifest))
    seal=dict(schema='mls.bounded-phase-tail.outer.v1',source_sha=sha,
        manifest_sha256=digest(output/'manifest.json'),payload_files=len(manifest['files']),
        promotion='NO_PROMOTION')
    (output/'outer-seal.json').write_bytes(encode(seal))
    return seal

def check(root,repo=None):
    seal=json.loads((root/'outer-seal.json').read_text())
    manifest=json.loads((root/'manifest.json').read_text())
    assert digest(root/'manifest.json')==seal['manifest_sha256']
    assert files(root)==manifest['files']
    assert seal['payload_files']==len(manifest['files'])
    assert seal['source_sha']==manifest['source_sha']
    assert manifest['parent_sha']==PARENT and manifest['decision']==DECISION
    assert manifest['selected_precision'] is None and manifest['promotion']=='NO_PROMOTION'
    assert manifest['full_tails_certified'] is False
    if repo:
        sha=manifest['source_sha']
        paths=subprocess.check_output(['git','ls-tree','-r','--name-only',sha],cwd=repo,text=True).splitlines()
        assert set(paths)=={str(p.relative_to(root/'source')) for p in (root/'source').rglob('*') if p.is_file()}
        for path in paths:
            expected=subprocess.check_output(['git','show',sha+':'+path],cwd=repo)
            assert hashlib.sha256(expected).hexdigest()==digest(root/'source'/path)
    return dict(source_sha=manifest['source_sha'],payload_files=len(manifest['files']),status='PASS')

def pack(root,archive):
    assert not archive.exists(),'refusing to replace an existing archive'
    check(root)
    with archive.open('xb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=9) as zipped:
        with tarfile.open(fileobj=zipped,mode='w|',format=tarfile.PAX_FORMAT) as tar:
            for path in sorted(root.rglob('*')):
                if not path.is_file():continue
                info=tar.gettarinfo(str(path),str(Path(root.name)/path.relative_to(root)))
                info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0;info.mode=0o644
                with path.open('rb') as stream:tar.addfile(info,stream)
    return dict(size=archive.stat().st_size,sha256=digest(archive))

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build');b.add_argument('repo',type=Path);b.add_argument('parent',type=Path);b.add_argument('output',type=Path)
    c=sub.add_parser('check');c.add_argument('root',type=Path);c.add_argument('--repo',type=Path)
    a=sub.add_parser('pack');a.add_argument('root',type=Path);a.add_argument('archive',type=Path)
    args=p.parse_args()
    if args.command=='build':result=build(args.repo,args.parent,args.output)
    elif args.command=='check':result=check(args.root,args.repo)
    else:result=pack(args.root,args.archive)
    print(json.dumps(result,sort_keys=True))
