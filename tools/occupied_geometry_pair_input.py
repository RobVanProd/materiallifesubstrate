"""Canonical two-sphere input composition; no candidate occupied-geometry query."""
import argparse
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import resource
import struct
import time

import occupied_geometry_input as wire
from occupied_geometry_input_check import Reader


def build(source,out):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));started=time.monotonic()
    out.mkdir(parents=True,exist_ok=False);(out/'candidate').mkdir();(out/'oracle').mkdir()
    names=('vertices','tetrahedra','facets','incidence','samples','resolution')
    counts={}
    for kind,name in enumerate(names,1):
        r=Reader(source/'candidate'/f'{name}.bin',kind);counts[kind]=r.count;r.f.close()
    files={}
    for kind,name in enumerate(names,1):
        path=out/'candidate'/f'{name}.bin'
        with path.open('xb') as f:
            f.write(wire.header(kind,1 if kind==6 else 2*counts[kind]))
            for side in range(1 if kind==6 else 2):
                r=Reader(source/'candidate'/f'{name}.bin',kind)
                for i in range(r.count):
                    if kind==6:
                        delta=r.q();total=r.q();f.write(wire.rational(delta)+wire.rational(2*total));continue
                    identifier=r.u(8)
                    if kind in (1,5):
                        assert identifier==i+1
                        xyz=[r.q() for _ in range(3)];xyz[0]+=Q(-3,2) if side==0 else Q(3,2)
                        f.write(struct.pack('<Q',identifier+side*counts[kind]))
                        f.write(b''.join(wire.rational(x) for x in xyz))
                        if kind==5:f.write(wire.rational(r.q())+wire.rational(r.q()/2))
                    elif kind in (2,3):
                        assert identifier==i+1
                        ids=[r.u(8)+side*counts[1] for _ in range(4 if kind==2 else 3)]
                        f.write(struct.pack('<'+'Q'*(1+len(ids)),identifier+side*counts[kind],*ids))
                    else:
                        opposite=r.u(1);facet=r.u(8);parity=r.u(1)
                        f.write(struct.pack('<QBQB',identifier+side*counts[2],opposite,
                                            facet+side*counts[3],parity))
                r.end()
        with path.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
        files[path.name]=dict(size=path.stat().st_size,sha256=h)
    assert time.monotonic()-started<=1800,'input wall-time ceiling'
    (out/'oracle/input-check.json').write_text(json.dumps(dict(
        schema='mls.occupied-geometry.partial-pair-input.v1',
        source_counts=counts,files=files,candidate_evaluations=0,complete_input_seal=False),sort_keys=True)+'\n')
    print('PASS pair input composition; seconds',time.monotonic()-started,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();build(a.source,a.output)
