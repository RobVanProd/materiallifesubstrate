"""Independent closed-file audit of the fresh pre-seal input package.

This verifies provenance/closure, not geometry validity by itself. It cannot
open the data gate or manufacture a successful fixture validity assessment.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


def unique(pairs):
    d={}
    for k,v in pairs:
        assert k not in d, ('duplicate key',k)
        d[k]=v
    return d


def read(path):
    raw=path.read_bytes()
    value=json.loads(raw,object_pairs_hook=unique)
    assert raw==(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode('ascii')
    return value


def valid_path(path):
    p=PurePosixPath(path)
    assert path and not p.is_absolute() and str(p)==path
    assert all(x not in ('.','..','') for x in p.parts)
    assert '\\' not in path and path.isascii()
    return p


def check(root):
    manifest_names={f'{r}-manifest.json' for r in ('candidate','oracle','control')}
    expected={};manifest_hashes={}
    for role in ('candidate','oracle','control'):
        path=root/f'{role}-manifest.json'
        assert not path.is_symlink()
        raw=path.read_bytes();manifest_hashes[path.name]=hashlib.sha256(raw).hexdigest()
        value=read(path);assert set(value)=={'files'}
        for relative,record in value['files'].items():
            p=valid_path(relative)
            assert p.parts[0]==role and relative not in expected
            assert set(record)=={'size','sha256'}
            assert type(record['size']) is int and record['size']>=0
            assert re.fullmatch('[0-9a-f]{64}',record['sha256'])
            if role!='control':assert p.parts== (role,record['sha256'])
            expected[relative]=record
    actual=set();total=0
    for path in root.rglob('*'):
        assert not path.is_symlink(), ('symlink',path)
        if path.is_dir():continue
        assert path.is_file()
        relative=path.relative_to(root).as_posix();actual.add(relative)
        total+=path.stat().st_size
    assert actual==set(expected)|manifest_names, ('extra/missing files',actual^(set(expected)|manifest_names))
    assert total<=8589934592, ('evidence ceiling',total)
    for relative,record in sorted(expected.items()):
        path=root/relative
        assert path.stat().st_size==record['size'],('size',relative)
        with path.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
        assert sha==record['sha256'],('hash',relative)
    recipe=read(root/'control/package-recipe.json')
    assert recipe['parent_sha']=='639ab635769a7d244aa255281acbabad78c27057'
    assert recipe['candidate_evaluations']==0 and recipe['complete_input_seal'] is False
    assert re.fullmatch('[0-9a-f]{40}',recipe['source_sha'])
    for key,source in recipe['source_aliases'].items():
        assert key in expected
        valid_path(source)
    inventory=read(root/recipe['run_inventory'])
    assert len(inventory['runs'])==1155
    for row in inventory['runs']:
        for key in [*row['source_blobs'].values(),row['transform']]+([row['base_pose']] if row['base_pose'] else []):
            assert key in expected and key.startswith('candidate/')
    receipt=read(root/'control/run-inventory-independent-v1.json')
    assert receipt['status']=='PASS' and receipt['runs']==1155 and receipt['views']==2310
    assert len(receipt['rejected_mutations'])==6
    return dict(status='PASS_CLOSED_INPUT_FILES_NOT_DATA_GATE',source_sha=recipe['source_sha'],
        files=len(expected),stored_bytes=total,remaining_bytes=8589934592-total,
        manifests=manifest_hashes,runs=1155,views=2310,
        candidate_evaluations=0,complete_input_seal=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();assert not a.output.exists()
    result=check(a.root)
    a.output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(result,sort_keys=True))
