"""Unsealed, content-addressed input package accounting; never opens data gate."""
import argparse
import hashlib
import json
from pathlib import Path


def build(root,out):
    assert not out.exists()
    files={};logical=[]
    def add(role,path,purpose):
        assert path.is_file() and not path.is_symlink()
        with path.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
        size=path.stat().st_size;key=role+'/'+sha
        if key in files:assert files[key]['size']==size
        else:files[key]=dict(size=size,sha256=sha,source=path.relative_to(root).as_posix())
        logical.append(dict(role=role,blob=key,purpose=purpose))
    for shape,levels in (('cube-k',range(5)),('slab-k',range(5)),('u-k',range(5)),
                         ('sphere-d',range(1,6)),('pair-d',range(1,6))):
        for level in levels:
            directory=root/f'{shape}{level}'
            for p in sorted((directory/'candidate').glob('*.bin')):
                add('candidate',p,'base primitive table')
            for p in sorted((directory/'oracle').glob('*')):
                if p.is_file():add('oracle',p,'input construction/validation witness')
    for p in sorted(root.glob('motion-*/motion.bin')):add('candidate',p,'prescribed linear motion')
    for fixture in range(1,8):
        add('candidate',root/f'queries-f{fixture}/candidate/queries-00.bin','base query stream')
        add('oracle',root/f'queries-f{fixture}/oracle/queries-00.jsonl','base query obligation join')
        # Every fixture receives the exact registered numerical transforms.
        for p in sorted((root/f'queries-f{fixture}/candidate').glob('transform-*.bin')):
            add('candidate',p,'global/order transform descriptor')
        add('control',root/f'query-factoring-f{fixture}.json','decoded query/join identities')
    for p in sorted((root/'factored-weight-oracle-v1').iterdir()):
        add('oracle',p,'losslessly factored exact weight witnesses')
    add('oracle',root/'full-weights-d5/receipt.json','original decoded weight inventory identities')
    add('oracle',root/'exact-controls-v1/oracle/exact-controls.json','independent analytical controls')
    for pattern in ('*independent*.log','*independent*.json','sphere-injectivity-d*.json',
                    'input-unit-*.log','lean-full-input-foundation.log'):
        for p in sorted(root.glob(pattern)):add('control',p,'preserved validation receipt')
    totals={role:sum(v['size'] for k,v in files.items() if k.startswith(role+'/'))
            for role in ('candidate','oracle','control')}
    n=sum(totals.values());cap=8<<30
    result=dict(schema='mls.occupied-geometry.unsealed-storage-preflight.v1',
        files=files,logical_references=logical,role_bytes=totals,stored_bytes=n,
        ceiling_bytes=cap,remaining_bytes=cap-n,
        pending=['complete decoded global/order/relabel identities',
                 'explicit plane base-pose descriptor','closed oracle/search inventory',
                 'complete closed manifests','new candidate/control scientific evidence'],
        full_package_fits_not_yet_established=True,candidate_evaluations=0,complete_input_seal=False)
    out.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','logical_references')},sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();build(a.root,a.output)
