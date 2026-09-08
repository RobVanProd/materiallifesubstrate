"""Explicit factored sphere-plane base pose and independently checked decode."""
import argparse
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import resource
import struct
import time

from occupied_geometry_input import header,rational
from occupied_geometry_input_check import Reader
from occupied_geometry_transform_decode import expanded


def build(source,out):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));start=time.monotonic()
    out.mkdir(parents=True,exist_ok=False)
    (out/'candidate').mkdir()
    m=tuple(tuple(Q(i==j) for j in range(3)) for i in range(3))
    b=(Q(0),Q(0),Q(2));v=(Q(0),)*3;scale=Q(1)
    pose=header(9,1)+struct.pack('<Q',1)+b''.join(rational(x) for x in
        (*[x for row in m for x in row],*b,*v,scale))+b'\0'
    (out/'base-pose.bin').write_bytes(pose)
    files={}
    for name,kind in (('vertices',1),('samples',5)):
        src=source/'candidate'/f'{name}.bin';dst=out/'candidate'/f'{name}.bin'
        with dst.open('xb') as f:
            for raw in expanded(src,(1,m,b,v,scale)):f.write(raw)
        # Independent direct coordinate equality, not a second call to expanded.
        a=Reader(src,kind);r=Reader(dst,kind);assert a.count==r.count
        for index in range(a.count):
            assert a.u(8)==r.u(8)==index+1
            assert a.q()==r.q() and a.q()==r.q()
            assert r.q()-a.q()==2
            if kind==5:assert a.q()==r.q() and a.q()==r.q()
        a.end();r.end()
        with dst.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
        files[str(kind)]=dict(size=dst.stat().st_size,sha256=h,records=index+1)
        assert time.monotonic()-start<=1800
    result=dict(status='PASS',base_pose_sha256=hashlib.sha256(pose).hexdigest(),
                files=files,candidate_evaluations=0,complete_input_seal=False)
    (out/'independent-pose-check.json').write_text(json.dumps(result,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();build(a.source,a.output)
