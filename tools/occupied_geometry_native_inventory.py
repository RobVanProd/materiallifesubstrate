"""Run the independent C++ decoder and compare complete logical stream hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import time


def run(root,exe,group,out):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));assert not out.exists()
    cases=[]
    if group=='cartesian':
        for shape in ('cube','slab'):
            for k in range(5):cases.append((f'{shape}-k{k}',f'{shape}-k{k}',False,False))
    else:
        for shape in ('sphere','pair','plane'):
            for d in range(1,6):cases.append((f'{shape}-d{d}',f'{"sphere" if shape=="plane" else shape}-d{d}',shape=='plane',False))
        for k in range(5):cases.append((f'u-k{k}',f'u-k{k}',False,False))
        for prefix in ('motion-','i1-motion-'):
            for shape,levels in (('pair-d',range(1,6)),('plane-d',range(1,6)),('u-k',range(5))):
                for k in levels:cases.append((f'{prefix}{shape}{k}',f'{prefix}{shape}{k}',False,True))
    all_rows=[];pending=[]
    for label,source,plane,motion in cases:
        paths=[(7,root/source/'motion.bin')] if motion else [
            (kind,root/source/'candidate'/name) for kind,name in ((1,'vertices.bin'),(5,'samples.bin'),(6,'resolution.bin'))]
        rows={i:{} for i in range(30)};start=time.monotonic()
        for kind,path in paths:
            cmd=[str(exe.resolve()),str(path),str(root/'queries-f1/candidate')]+(['plane'] if plane else [])
            result=subprocess.run(cmd,text=True,capture_output=True,check=True,timeout=1800)
            lines=result.stdout.splitlines();assert len(lines)==30
            for i,line in enumerate(lines):
                v,k,n,size,sha=line.split();assert int(v)==i and int(k)==kind
                assert len(sha)==64 and all(c in '0123456789abcdef' for c in sha)
                rows[i][str(kind)]=dict(records=int(n),size=int(size),sha256=sha)
            assert time.monotonic()-start<=1800,('native input row ceiling',label)
            print('independent C++ input table',label,kind,flush=True)
        expected_path=root/f'decoded-{label}.json'
        if expected_path.exists():
            expected=json.loads(expected_path.read_text())
            for i,row in rows.items():
                for k,value in row.items():assert value==expected['variants'][i]['files'][k],('independent decoded input mismatch',label,i,k,value,expected['variants'][i]['files'][k])
        else:pending.append(label)
        all_rows.append(dict(dataset=label,variants=[dict(variant=i,files=row) for i,row in rows.items()]))
    cpp=Path(__file__).with_name('occupied_geometry_transform_check.cpp')
    with cpp.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    payload=dict(schema='mls.occupied-geometry.independent-native-input.v1',
        status='PASS' if not pending else 'PENDING_PYTHON_IDENTITIES',pending=pending,
        native_source_sha256=sha,datasets=all_rows,candidate_evaluations=0,complete_input_seal=False)
    out.write_text(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(status=payload['status'],datasets=len(all_rows),pending=pending,
        candidate_evaluations=0,complete_input_seal=False)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('executable',type=Path)
    p.add_argument('--group',choices=('cartesian','other'),required=True);p.add_argument('output',type=Path)
    a=p.parse_args();run(a.root,a.executable,a.group,a.output)
