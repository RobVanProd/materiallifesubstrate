"""I1-only projection of frozen motion: never expose I2 vertex motion to A/C.

This is typed input selection, not geometry construction. The source I2 stream
is preserved, and the full I1 decoded byte identity is checked before sealing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import struct

from occupied_geometry_input import header
from occupied_geometry_input_check import Reader
from occupied_geometry_transform_decode import raw_q


def project(source,out):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    out.mkdir(parents=True,exist_ok=False)
    r=Reader(source/'motion.bin',7);count=0
    for _ in range(r.count):
        r.u(8);kind=r.u(1);r.u(8)
        assert kind in (1,5)
        for _ in range(3):r.q()
        count+=kind==5
    r.end()
    dst=out/'motion.bin'
    with dst.open('xb') as f:
        f.write(header(7,count));r=Reader(source/'motion.bin',7);index=0
        for _ in range(r.count):
            r.u(8);kind=r.u(1);target=r.u(8);data=b''.join(raw_q(r) for _ in range(3))
            if kind==5:
                index+=1;assert target==index
                f.write(struct.pack('<QBQ',index,5,target)+data)
        r.end();assert index==count
    # Independently decode numeric values, target identity, and absence of I2.
    a=Reader(source/'motion.bin',7);b=Reader(dst,7);assert b.count==count
    hits=0
    for _ in range(a.count):
        a.u(8);kind=a.u(1);target=a.u(8);v=tuple(a.q() for _ in range(3))
        if kind==5:
            hits+=1
            assert (b.u(8),b.u(1),b.u(8))==(hits,5,target)
            assert tuple(b.q() for _ in range(3))==v
    a.end();b.end();assert hits==count
    with dst.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    result=dict(status='PASS',schema='mls.occupied-geometry.i1-motion-projection.v1',
        records=count,size=dst.stat().st_size,sha256=sha,only_target_kind=5,
        candidate_evaluations=0,complete_input_seal=False)
    (out/'projection-check.json').write_text(json.dumps(result,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();project(a.source,a.output)
