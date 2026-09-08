"""Pre-data logical stream identities for the registered global variants.

No candidate is imported or called. Existing receipts are never overwritten.
This emits partial controller receipts, never the complete input seal itself.
"""
import argparse
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import resource
import time

from occupied_geometry_input_check import Reader
from occupied_geometry_transform_decode import load_transform,expanded,rotation_digests


NAMES=('vertices','tetrahedra','facets','incidence','samples','resolution')


def hash_file(path):
    with path.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(size=path.stat().st_size,sha256=h)


def hash_stream(source,tr):
    start=time.monotonic();h=hashlib.sha256();n=0;buffer=bytearray()
    for raw in expanded(source,tr):
        buffer.extend(raw)
        if len(buffer)>=1<<20:
            h.update(buffer);n+=len(buffer);buffer.clear()
            assert time.monotonic()-start<=1800
    h.update(buffer);n+=len(buffer)
    return dict(size=n,sha256=h.hexdigest())


def run(source,transforms,out,plane=False,motion=False):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    assert not out.exists()
    variants=[load_transform(transforms/f'transform-{i:02}.bin') for i in range(30)]
    base=(Q(0),Q(0),Q(2)) if plane else (Q(0),)*3
    paths=[(7,source/'motion.bin')] if motion else [(i+1,source/'candidate'/f'{name}.bin') for i,name in enumerate(NAMES)]
    result=[dict(variant=i,files={}) for i in range(30)]
    elapsed=[0.0]*30;inputs={}
    for kind,path in paths:
        r=Reader(path,kind);count=r.count;r.f.close()
        start=time.monotonic();original=hash_file(path)
        inputs[str(kind)]=dict(**original,records=count)
        dt=time.monotonic()-start
        elapsed=[v+dt for v in elapsed]
        if kind in (2,3,4):
            for row in result:row['files'][str(kind)]=dict(**original,records=count)
            continue
        start=time.monotonic()
        if kind==6:
            batch=[dict(**original,records=count)]*24
        else:
            batch=rotation_digests(path,variants[:24],base)
        dt=time.monotonic()-start
        for i,b in enumerate(batch):
            elapsed[i]+=dt
            result[i]['files'][str(kind)]={k:b[k] for k in ('size','sha256','records')}
        for i in range(24,30):
            start=time.monotonic()
            identifier,matrix,b,v,scale=variants[i]
            if kind!=7:
                b=tuple(b[j]+scale*sum(matrix[j][k]*base[k] for k in range(3)) for j in range(3))
            tr=(identifier,matrix,b,v,scale)
            result[i]['files'][str(kind)]=dict(**hash_stream(path,tr),records=count)
            elapsed[i]+=time.monotonic()-start
        assert max(elapsed)<=1800,('input variant cumulative decoding ceiling',elapsed)
        print('input table decoded',source.name,kind,count,flush=True)
    payload=dict(schema='mls.occupied-geometry.global-decoded-streams.v1',
        source_files=inputs,base_translation=[str(x) for x in base],
        variants=result,candidate_evaluations=0,complete_input_seal=False,
        decoder_sources={p.name:hash_file(p) for p in (
            Path(__file__),Path(__file__).with_name('occupied_geometry_transform_decode.py'),
            Path(__file__).with_name('occupied_geometry_input_check.py'),
            Path(__file__).with_name('occupied_geometry_input.py'))})
    out.write_text(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(status='PASS',variants=30,source=source.name,
        largest_conservative_variant_seconds=max(elapsed),candidate_evaluations=0,complete_input_seal=False)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path)
    p.add_argument('transforms',type=Path);p.add_argument('out',type=Path)
    p.add_argument('--plane',action='store_true');p.add_argument('--motion',action='store_true')
    a=p.parse_args();run(a.source,a.transforms,a.out,a.plane,a.motion)
