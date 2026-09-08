"""Decode a sealed input view into an oracle-free candidate directory.

Controller tool only. The candidate cannot import this tool or its input
construction dependencies. Every emitted table must match a pre-data hash.
"""
import argparse
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import resource
import struct
import tempfile
import time

from occupied_geometry_input_check import Reader
from occupied_geometry_transform_decode import expanded,raw_q
from occupied_geometry_order_decode import records
from occupied_geometry_query_decode import decoded_rows

ROOT='8ec8ba42956f7664c66de26ce2f760be650cba76ef7fe0820d92396206e84516'


def header(kind,count):return b'MLSOMG01'+struct.pack('<IIQ',1,kind,count)


def write(path,parts):
    h=hashlib.sha256();size=0
    with path.open('xb') as f:
        buffer=bytearray()
        for part in parts:
            buffer.extend(part)
            if len(buffer)>=1<<20:f.write(buffer);h.update(buffer);size+=len(buffer);buffer.clear()
        f.write(buffer);h.update(buffer);size+=len(buffer)
    with path.open('rb') as f:prefix=f.read(24)
    return dict(records=int.from_bytes(prefix[16:24],'little'),size=size,sha256=h.hexdigest())


def copy_parts(path):
    with path.open('rb') as f:
        while raw:=f.read(1<<20):yield raw


def run(package,f,k,v,tier,out):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));start=time.monotonic()
    assert not out.exists()
    seal_raw=(package/'input-root-seal.json').read_bytes()
    assert hashlib.sha256(seal_raw).hexdigest()==ROOT
    seal=json.loads(seal_raw);assert seal['data_gate_open'] and seal['candidate_evaluations']==0
    control_raw=(package/'control-manifest.json').read_bytes()
    assert hashlib.sha256(control_raw).hexdigest()==seal['manifests']['control-manifest.json']
    controls=json.loads(control_raw)['files']
    raw=(package/'control/controller-run-inventory-v1.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==seal['run_inventory_sha256']
    assert controls['control/controller-run-inventory-v1.json']['sha256']==seal['run_inventory_sha256']
    row=next(r for r in json.loads(raw)['runs'] if (r['fixture'],r['level'],r['variant'])==(f,k,v))
    transform=package/row['transform'];r=Reader(transform,9);assert r.count==1
    ident=r.u(8);matrix=tuple(tuple(r.q() for _ in range(3)) for _ in range(3))
    shift=tuple(r.q() for _ in range(3));boost=tuple(r.q() for _ in range(3))
    scale=r.q();mode=r.u(1);r.end()
    assert hashlib.sha256(transform.read_bytes()).hexdigest()==transform.name
    base=(Q(0),)*3
    if row['base_pose']:
        pose=package/row['base_pose'];r=Reader(pose,9);assert r.count==1 and r.u(8)==1
        assert tuple(tuple(r.q() for _ in range(3)) for _ in range(3))==tuple(tuple(Q(i==j) for j in range(3)) for i in range(3))
        base=tuple(r.q() for _ in range(3))
        assert tuple(r.q() for _ in range(3))==(Q(0),)*3 and r.q()==1 and r.u(1)==0;r.end()
        assert hashlib.sha256(pose.read_bytes()).hexdigest()==pose.name
    out.mkdir();files={};namespaces={int(key):value['records'] for key,value in row['views']['I2'].items()}
    with tempfile.TemporaryDirectory(prefix='mls-input-view-decode-') as tmp:
        scratch=Path(tmp)
        for kind_s,expected in sorted(row['views'][tier].items()):
            kind=int(kind_s);dest=out/f'{kind}.bin'
            if kind==7 and row['static_motion']:
                value=write(dest,[header(7,0)])
            else:
                source=package/row['source_blobs'][kind_s]
                if kind==7 and tier=='I1':
                    def selected_motion():
                        yield header(7,expected['records']);r=Reader(source,7);count=0
                        for _ in range(r.count):
                            r.u(8);target_kind=r.u(1);target=r.u(8)
                            data=b''.join(raw_q(r) for _ in range(3))
                            if target_kind==5:
                                count+=1;yield struct.pack('<QBQ',count,5,target)+data
                            else:assert target_kind==1
                        r.end();assert count==expected['records']
                    selected=scratch/'motion-selected.bin';write(selected,selected_motion());source=selected
                if kind==8:
                    query_rows=decoded_rows(source,transform)
                    parts=[header(8,len(query_rows))]
                    parts.extend(struct.pack('<QBQ',i,op,len(args))+args
                                 for i,(op,args,_) in enumerate(query_rows,1))
                elif kind in (2,3,4):parts=copy_parts(source)
                else:
                    translation=shift if kind==7 else tuple(shift[i]+scale*sum(matrix[i][j]*base[j] for j in range(3)) for i in range(3))
                    parts=expanded(source,(ident,matrix,translation,boost,scale))
                if mode:
                    intermediate=scratch/f'{kind}-unordered.bin';write(intermediate,parts)
                    seed=260908^(kind<<32)^(f<<16)^(k<<8)
                    ns={5:namespaces[5]} if tier=='I1' and kind==7 else namespaces
                    parts=records(intermediate,('reverse','shuffle','relabel')[mode-1],seed,ns)
                value=write(dest,parts)
            assert value==expected,('sealed decoded identity',f,k,v,tier,kind,value,expected)
            files[dest.name]=value
            assert time.monotonic()-start<=1800,'canonical input decoding time ceiling'
    # No controller/fixture/oracle metadata is written into the candidate view.
    assert set(p.name for p in out.iterdir())==set(files)
    print(json.dumps(dict(status='PASS_SEALED_VIEW_DECODE',files=files,root_sha256=ROOT,
                         tier=tier,candidate_evaluations=0),sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package',type=Path)
    p.add_argument('--fixture',type=int,choices=range(1,8),required=True)
    p.add_argument('--level',type=int,choices=range(5),required=True)
    p.add_argument('--variant',type=int,choices=range(33),required=True)
    p.add_argument('--tier',choices=('I1','I2'),required=True);p.add_argument('output',type=Path)
    a=p.parse_args();run(a.package,a.fixture,a.level,a.variant,a.tier,a.output)
