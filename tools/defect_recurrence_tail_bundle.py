"""Immutable, closed-inventory packaging of the stopped short-control lab."""
import argparse
import gzip
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import bounded_phase_tail_bundle as packaging
import correlation_aware_tail_bundle as parent_bundle
from defect_recurrence_tail_audit import audit, PARENT, DECISION

PARENT_MANIFEST='926eb83a30f5c6c55e422b6a0131ef8f5cd8848f69428c437006ee7b901a6dd9'
digest,encode,files=packaging.digest,packaging.encode,packaging.files


def check(root,repo=None):
    manifest=json.loads((root/'manifest.json').read_text())
    seal=json.loads((root/'outer-seal.json').read_text())
    assert seal['manifest_sha256']==digest(root/'manifest.json')
    assert manifest['source_sha']==seal['source_sha']
    assert files(root)==manifest['files'] and seal['payload_files']==len(manifest['files'])
    assert manifest['parent_sha']==PARENT and manifest['decision']==DECISION
    assert manifest['selected_precision'] is None and manifest['promotion']=='NO_PROMOTION'
    assert digest(root/'parent/manifest.json')==PARENT_MANIFEST
    parent_bundle.check(root/'parent')
    assert json.loads((root/'parent/manifest.json').read_text())['source_sha']==PARENT
    assert audit(root/'evidence',root/'parent')==json.loads((root/'evidence/result.json').read_text())
    for old in (root/'parent/source').rglob('*'):
        if not old.is_file(): continue
        relative=old.relative_to(root/'parent/source');new=root/'source'/relative
        if str(relative)=='formal/MLSFormal/AxiomReport.lean':
            retained=[s for s in new.read_text().splitlines() if s.strip() and 'defectTail_' not in s
                      and s!='import MLSFormal.DefectRecurrenceTailCertification']
            assert retained==[s for s in old.read_text().splitlines() if s.strip()]
        else:
            assert digest(new)==digest(old),f'inherited file changed: {relative}'
    if repo:
        sha=manifest['source_sha']
        paths=subprocess.check_output(['git','ls-tree','-r','--name-only',sha],cwd=repo,text=True).splitlines()
        assert set(paths)=={str(p.relative_to(root/'source')) for p in (root/'source').rglob('*') if p.is_file()}
        for path in paths:
            expected=subprocess.check_output(['git','show',sha+':'+path],cwd=repo)
            assert __import__('hashlib').sha256(expected).hexdigest()==digest(root/'source'/path)
    return dict(status='PASS',source_sha=manifest['source_sha'],payload_files=len(manifest['files']),
                decision=DECISION,selected_precision=None,promotion='NO_PROMOTION')


def build(repo,parent,work,output):
    assert not output.exists(),'never overwrite evidence'
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()
    parent_bundle.check(parent,repo)
    assert digest(parent/'manifest.json')==PARENT_MANIFEST
    result=audit(work,parent)
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=repo,text=True).strip()
    output.mkdir(parents=True)
    (output/'source').mkdir()
    archive=subprocess.check_output(['git','archive',sha],cwd=repo)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(output/'source',filter='data')
    shutil.copytree(parent,output/'parent')
    shutil.copytree(work,output/'evidence')
    (output/'evidence/result.json').write_bytes(encode(result))
    manifest=dict(schema='mls.defect-tail.manifest.v1',source_sha=sha,source_tree=tree,
                  parent_sha=PARENT,decision=DECISION,selected_precision=None,promotion='NO_PROMOTION',
                  files=files(output))
    (output/'manifest.json').write_bytes(encode(manifest))
    (output/'outer-seal.json').write_bytes(encode(dict(schema='mls.defect-tail.outer.v1',
        source_sha=sha,manifest_sha256=digest(output/'manifest.json'),payload_files=len(manifest['files']))))
    return check(output,repo)


def pack(root,archive):
    check(root)
    assert not archive.exists(),'never overwrite archive'
    with archive.open('xb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=9) as zipped:
        with tarfile.open(fileobj=zipped,mode='w|',format=tarfile.PAX_FORMAT) as tar:
            for path in sorted(root.rglob('*')):
                if not path.is_file(): continue
                info=tar.gettarinfo(str(path),str(Path(root.name)/path.relative_to(root)))
                info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0;info.mode=0o644
                with path.open('rb') as stream: tar.addfile(info,stream)
    return dict(size=archive.stat().st_size,sha256=digest(archive))


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build')
    for name in ('repo','parent','work','output'): b.add_argument(name,type=Path)
    c=sub.add_parser('check');c.add_argument('root',type=Path);c.add_argument('--repo',type=Path)
    a=sub.add_parser('pack');a.add_argument('root',type=Path);a.add_argument('archive',type=Path)
    args=p.parse_args()
    if args.command=='build': result=build(args.repo,args.parent,args.work,args.output)
    elif args.command=='check': result=check(args.root,args.repo)
    else: result=pack(args.root,args.archive)
    print(json.dumps(result,sort_keys=True))
