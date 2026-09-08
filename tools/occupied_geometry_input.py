"""Pre-data input construction only. Contains no A/B/C geometry evaluator."""
from __future__ import annotations

import argparse
from fractions import Fraction as Q
import hashlib
import itertools
import json
from math import gcd, isqrt
from pathlib import Path
import struct
import sys
import time

sys.dont_write_bytecode = True
import gmpy2 as mp

PARENT = '2874a31c2e5302c2ca5053e1f76fef3430ab99c3'
PRECISION = 512
GRID = 1 << 256


def uint(x: int) -> bytes:
    if x <= 0:
        raise ValueError('positive magnitude required')
    b = x.to_bytes((x.bit_length()+7)//8, 'little')
    return struct.pack('<I',len(b))+b


def sint(x: int) -> bytes:
    b = abs(x).to_bytes((abs(x).bit_length()+7)//8,'little')
    return bytes([x<0])+struct.pack('<I',len(b))+b


def rational(x: Q) -> bytes:
    return sint(x.numerator)+uint(x.denominator)


def header(kind: int, count: int) -> bytes:
    return b'MLSOMG01'+struct.pack('<IIQ',1,kind,count)


def det(a,b,c):
    return (a[0]*(b[1]*c[2]-b[2]*c[1])
            -a[1]*(b[0]*c[2]-b[2]*c[0])
            +a[2]*(b[0]*c[1]-b[1]*c[0]))


def determinant(v):
    return det(*[tuple(v[j][i]-v[0][i] for i in range(3)) for j in (1,2,3)])


def refine(t):
    # Input integer coordinates share a denominator. Output denominator doubles.
    v=[tuple(2*x for x in p) for p in t]
    a,b,c,d,e,f=[tuple(t[i][k]+t[j][k] for k in range(3))
                 for i,j in ((0,1),(0,2),(0,3),(1,2),(1,3),(2,3))]
    return ((v[0],a,b,c),(a,v[1],d,e),(b,d,v[2],f),(c,e,f,v[3]),
            (a,b,c,e),(a,b,d,e),(b,c,e,f),(b,d,e,f))


def reference(depth):
    ts=[((0,0,0),(a,0,0),(0,b,0),(0,0,c))
        for a,b,c in itertools.product((-1,1),repeat=3)]
    for _ in range(depth):
        ts=[c for t in ts for c in refine(t)]
    return ts


def nearest_sqrt_ratio(a: int,b: int) -> int:
    """Nearest-even sqrt(a/b), by exact integer comparisons."""
    n=isqrt(a//b)
    cmp=4*a-(2*n+1)**2*b
    return n+(cmp>0 or (cmp==0 and n%2==1))


def map_vertex(v, denominator):
    r2=sum(x*x for x in v); s=sum(abs(x) for x in v)
    if not r2:
        return (0,0,0)
    out=[]
    for x in v:
        if x==0:
            out.append(0); continue
        z=s*abs(x)*GRID
        n=nearest_sqrt_ratio(z*z,denominator**2*r2)
        # Separate directed MPFR enclosure of z/(denominator*sqrt(r2)).
        with mp.context(precision=PRECISION,round=mp.RoundDown):
            root_lo=mp.sqrt(mp.mpfr(r2))
        with mp.context(precision=PRECISION,round=mp.RoundUp):
            root_hi=mp.sqrt(mp.mpfr(r2))
            div_hi=mp.mpfr(denominator)*root_hi
        with mp.context(precision=PRECISION,round=mp.RoundDown):
            div_lo=mp.mpfr(denominator)*root_lo
            lo=mp.mpfr(z)/div_hi
        with mp.context(precision=PRECISION,round=mp.RoundUp):
            hi=mp.mpfr(z)/div_lo
        lower=mp.mpq(lo); upper=mp.mpq(hi)
        left=mp.mpq(2*n-1,2); right=mp.mpq(2*n+1,2)
        if not (lower>=left and upper<=right):
            raise ValueError(('unresolved mapped-coordinate rounding cell',v,x))
        if n%2 and (lower==left or upper==right):
            raise ValueError(('odd rounding-cell boundary',v,x))
        out.append(n if x>0 else -n)
    return tuple(out)


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def sphere_probe(out: Path,depth: int):
    """Partial fixture materialization; does not constitute a complete input seal."""
    started=time.monotonic(); out.mkdir(parents=True,exist_ok=False)
    (out/'candidate').mkdir(); (out/'oracle').mkdir()
    ref=reference(depth); n=2**depth
    points=sorted({p for t in ref for p in t})
    mapped=[map_vertex(p,n) for p in points]
    ids={p:i for i,p in enumerate(points)}
    records=sorted(tuple(sorted(ids[p] for p in t)) for t in ref)
    failures=[]; delta2=0; radial_lo=None; radial_hi=0
    vp=out/'candidate/vertices.bin'; tp=out/'candidate/tetrahedra.bin'
    with vp.open('xb') as f:
        f.write(header(1,len(points)))
        for i,p in enumerate(mapped):
            f.write(struct.pack('<Q',i+1))
            for x in p:f.write(rational(Q(x,GRID)))
    with tp.open('xb') as f:
        f.write(header(2,len(records)))
        for i,rec in enumerate(records):
            r=list(rec); q=[mapped[j] for j in r]
            ref_sign=determinant([points[j] for j in r])
            actual=determinant(q)
            if actual==0 or ref_sign*actual<=0:
                failures.append(dict(cell=i+1,vertex_ids=[j+1 for j in r],
                    reference_determinant=str(ref_sign),mapped_determinant=str(actual)))
            if ref_sign<0:r[-1],r[-2]=r[-2],r[-1]
            f.write(struct.pack('<5Q',i+1,*[j+1 for j in r]))
            for a,b in itertools.combinations(q,2):
                delta2=max(delta2,sum((a[j]-b[j])**2 for j in range(3)))
            radial=sum(sum(p[j] for p in q)**2 for j in range(3))
            radial_lo=radial if radial_lo is None else min(radial_lo,radial)
            radial_hi=max(radial_hi,radial)
    assert len(records)==8*8**depth
    assert len(points)==(4*n**3+6*n*n+8*n+3)//3
    r=dict(schema='mls.occupied-geometry.partial-input.v1',protocol=PARENT,
           depth=depth,level=depth-1,vertices=len(points),tetrahedra=len(records),
           mapped_orientation_failures=failures,
           delta_squared=[str(delta2),str(GRID**2)],
           radial_centroid_squared_range=[[str(radial_lo),str(16*GRID**2)],
                                           [str(radial_hi),str(16*GRID**2)]],
           complete_input_seal=False,candidate_evaluations=0,
           files={str(p.relative_to(out)):dict(size=p.stat().st_size,sha256=digest(p))
                  for p in (vp,tp)})
    (out/'oracle/input-check.json').write_text(json.dumps(r,sort_keys=True)+'\n')
    print(json.dumps(dict(depth=depth,tetrahedra=len(records),orientation_failures=len(failures),
                         seconds=time.monotonic()-started),sort_keys=True),flush=True)
    return r


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path)
    p.add_argument('--depth',type=int,choices=range(1,6),required=True)
    a=p.parse_args();r=sphere_probe(a.output,a.depth)
    sys.exit(2 if r['mapped_orientation_failures'] else 0)
