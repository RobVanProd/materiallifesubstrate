"""Explicit per-primitive linear motion coefficients for the frozen benchmarks."""
import argparse
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import resource
import struct
import time

from occupied_geometry_input_check import Reader
from occupied_geometry_input import header,rational


def materialize(source,out,mode):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));started=time.monotonic()
    out.mkdir(parents=True,exist_ok=False);path=out/'motion.bin';counts={}
    for name,kind in (('vertices',1),('samples',5)):
        r=Reader(source/'candidate'/f'{name}.bin',kind);counts[kind]=r.count;r.f.close()
    with path.open('xb') as f:
        f.write(header(7,sum(counts.values())));record=0
        for name,kind in (('vertices',1),('samples',5)):
            r=Reader(source/'candidate'/f'{name}.bin',kind)
            for _ in range(r.count):
                identifier=r.u(8);p=tuple(r.q() for _ in range(3))
                if kind==5:r.q();r.q()
                if mode=='u':velocity=(-p[0]/4,Q(0),Q(0))
                elif mode=='pair':
                    assert p[0]!=0
                    velocity=(Q(1,2) if p[0]<0 else Q(-1,2),Q(0),Q(0))
                elif mode=='plane':velocity=(Q(0),Q(0),Q(-1))
                else:raise ValueError('unknown frozen motion')
                record+=1
                f.write(struct.pack('<QBQ',record,kind,identifier)+b''.join(rational(x) for x in velocity))
            r.end()
    assert record==sum(counts.values()) and time.monotonic()-started<=1800
    with path.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
    # This receipt is controller-only; the candidate receives motion.bin only.
    (out/'control-receipt.json').write_text(json.dumps(dict(mode=mode,
        targets=counts,records=record,size=path.stat().st_size,sha256=h,
        source_translation=['0','0','2'] if mode=='plane' else ['0','0','0'],
        candidate_evaluations=0,complete_input_seal=False),sort_keys=True)+'\n')
    print(json.dumps(dict(mode=mode,records=record,bytes=path.stat().st_size,
        sha256=h,seconds=time.monotonic()-started),sort_keys=True),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--mode',choices=('pair','plane','u'),required=True)
    a=p.parse_args();materialize(a.source,a.output,a.mode)
