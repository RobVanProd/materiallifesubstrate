"""Fixed inventory of fully decoded reverse/shuffle/relabel input identities."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import time

from occupied_geometry_input_check import Reader
from occupied_geometry_order_decode import digest


NAMES=('vertices','tetrahedra','facets','incidence','samples','resolution')


def run(root,fixture,level,out):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));assert not out.exists()
    name={1:f'cube-k{level}',2:f'slab-k{level}',3:f'sphere-d{level+1}',
          4:f'pair-d{level+1}',5:f'pair-d{level+1}',6:f'sphere-d{level+1}',7:f'u-k{level}'}[fixture]
    tables={i+1:root/name/'candidate'/f'{n}.bin' for i,n in enumerate(NAMES)}
    if fixture==6:
        for kind in (1,5):tables[kind]=root/f'plane-d{level+1}/candidate'/f'{NAMES[kind-1]}.bin'
    motion={5:f'motion-pair-d{level+1}',6:f'motion-plane-d{level+1}',7:f'motion-u-k{level}'}
    if fixture in motion:tables[7]=root/motion[fixture]/'motion.bin'
    counts={}
    for kind,path in tables.items():
        r=Reader(path,kind);counts[kind]=r.count;r.f.close()
    rows=[]
    for variant,mode in ((30,'reverse'),(31,'shuffle'),(32,'relabel')):
        start=time.monotonic();row=dict(variant=variant,files={})
        query=root/f'queries-f{fixture}/candidate/queries-{variant:02}.bin'
        for kind,path in (*tables.items(),(8,query)):
            row['files'][str(kind)]=digest(path,mode,fixture,level,counts)
            assert time.monotonic()-start<=1800,('input variant aggregate decoding ceiling',fixture,level,mode)
            print('order input table decoded',fixture,level,mode,kind,flush=True)
        rows.append(row)
    sources={}
    for name in ('occupied_geometry_order_inventory.py','occupied_geometry_order_decode.py'):
        p=Path(__file__).with_name(name)
        with p.open('rb') as f:sources[name]=hashlib.file_digest(f,'sha256').hexdigest()
    result=dict(schema='mls.occupied-geometry.order-decoded-streams.v1',
        fixture=fixture,level=level,namespace_counts=counts,variants=rows,
        decoder_sources=sources,candidate_evaluations=0,complete_input_seal=False)
    out.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(status='PASS',fixture=fixture,level=level,
        variants=3,candidate_evaluations=0,complete_input_seal=False)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path)
    p.add_argument('--fixture',type=int,choices=range(1,8),required=True)
    p.add_argument('--level',type=int,choices=range(5),required=True)
    p.add_argument('output',type=Path);a=p.parse_args();run(a.root,a.fixture,a.level,a.output)
