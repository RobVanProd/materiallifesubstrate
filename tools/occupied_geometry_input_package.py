"""Build a closed pre-seal input staging package. Never writes a data-gate seal.

Copies are content addressed but not compressed. A separate audit must hash
the fresh copies, verify role closure, and establish the input gate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)+'\n').encode('ascii')


def digest(path):
    with path.open('rb') as f:
        sha=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(size=path.stat().st_size,sha256=sha)


def run(root, preflight, repo, out):
    assert not out.exists()
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip(), 'commit sources before packaging'
    source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    plan=json.loads(preflight.read_text())
    for name in ('native-cartesian-v1.json','native-other-v1.json',
                 'native-orders-cartesian-v1.json','native-orders-other-v1.json',
                 'run-inventory-independent-v1.json','final-query-joins-v1.json'):
        assert json.loads((root/name).read_text())['status']=='PASS'
    out.mkdir()
    files={}
    def copy(source, relative):
        assert source.is_file() and not source.is_symlink()
        target=out/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        assert not target.exists()
        shutil.copyfile(source,target)
        files[relative]=digest(target)
        return files[relative]
    for key,entry in sorted(plan['files'].items()):
        actual=copy(root/entry['source'],key)
        assert actual==dict(size=entry['size'],sha256=entry['sha256'])
    for name in ('controller-run-inventory-v1.json','run-inventory-independent-v1.json'):
        copy(root/name,'control/'+name)
    tracked=subprocess.check_output(['git','ls-files'],cwd=repo,text=True).splitlines()
    snapshots=[p for p in tracked if p.startswith(('tools/occupied_geometry',
        'tools/test_occupied_geometry','docs/occupied-matter-geometry')) or
        p=='formal/MLSFormal/OccupiedMatterGeometryFoundation.lean']
    for p in snapshots:
        copy(repo/p,'control/source/'+p)
    descriptor=dict(schema='mls.occupied-geometry.input-staging.v1',
        source_sha=source_sha,parent_sha='639ab635769a7d244aa255281acbabad78c27057',
        candidate_evaluations=0,complete_input_seal=False,
        run_inventory='control/controller-run-inventory-v1.json',
        source_aliases={p:entry['source'] for p,entry in plan['files'].items()},
        input_source_to_blob={entry['source']:entry['blob'] for entry in plan['logical_references']},
        governing_documents={p:digest(repo/p) for p in snapshots if p.startswith('docs/')},
        frozen_evidence_ceiling_bytes=8<<30,
        pending=['independent fresh-copy manifest audit','complete input-gate assessment',
                 'new candidate evidence remains subject to the same total ceiling'])
    descriptor_path=out/'control/package-recipe.json'
    descriptor_path.write_bytes(encoded(descriptor))
    files['control/package-recipe.json']=digest(descriptor_path)
    # Physical oracle and candidate roles have no source-path alias metadata.
    for role in ('candidate','oracle','control'):
        value=dict(files={p:v for p,v in files.items() if p.startswith(role+'/')})
        target=out/f'{role}-manifest.json';target.write_bytes(encoded(value))
    total=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    assert total<=8<<30, ('frozen evidence ceiling',total)
    print(json.dumps(dict(status='STAGED_NOT_SEALED',source_sha=source_sha,
        stored_bytes=total,remaining_bytes=(8<<30)-total,files=len(files),
        candidate_evaluations=0,complete_input_seal=False),sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('root','preflight','repo','output'):p.add_argument(name,type=Path)
    a=p.parse_args();run(a.root,a.preflight,a.repo,a.output)
