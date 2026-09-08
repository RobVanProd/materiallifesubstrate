"""Independent exact decoding of partial spherical fixture bytes.

No imports of the input generator, volume integrator, or candidate algorithms.
These checks deliberately do not claim a complete occupied-domain certificate.
"""
import argparse
from fractions import Fraction
from math import gcd
from pathlib import Path
import json
import struct


class Reader:
    def __init__(self,path,kind):
        self.f=path.open('rb')
        assert self.read(8)==b'MLSOMG01'
        assert self.u(4)==1 and self.u(4)==kind
        self.count=self.u(8)
    def read(self,n):
        b=self.f.read(n);assert len(b)==n;return b
    def u(self,n):return int.from_bytes(self.read(n),'little')
    def q(self):
        sign=self.u(1);assert sign in (0,1)
        n=self.u(4);assert n<=1024
        b=self.read(n);assert not n or b[-1]!=0
        num=int.from_bytes(b,'little');assert num or sign==0
        d=self.u(4);assert 1<=d<=1024
        b=self.read(d);assert b[-1]!=0
        den=int.from_bytes(b,'little');assert den>0 and gcd(num,den)==1
        return Fraction(-num if sign else num,den)
    def end(self):assert self.f.read(1)==b'';self.f.close()


def determinant(p,q,r):
    # Independent scalar expansion, no shared geometry code.
    return (p[0]*q[1]*r[2]+p[1]*q[2]*r[0]+p[2]*q[0]*r[1]
            -p[2]*q[1]*r[0]-p[1]*q[0]*r[2]-p[0]*q[2]*r[1])


def check(root,depth):
    n=1<<depth;grid=1<<256
    expected=[]
    for x in range(-n,n+1):
        for y in range(-n+abs(x),n-abs(x)+1):
            zmax=n-abs(x)-abs(y)
            for z in range(-zmax,zmax+1):expected.append((x,y,z))
    r=Reader(root/'candidate/vertices.bin',1);assert r.count==len(expected)
    verts=[]
    for i,v in enumerate(expected):
        assert r.u(8)==i+1
        encoded=tuple(r.q()*grid for _ in range(3));assert all(x.denominator==1 for x in encoded)
        values=tuple(x.numerator for x in encoded)
        s=sum(abs(x) for x in v);q2=sum(x*x for x in v)
        for exact,raw in zip(v,values):
            if not exact:assert raw==0;continue
            assert (exact>0)==(raw>0)
            u=abs(raw); A=4*(s*abs(exact)*grid)**2;B=n*n*q2
            lower=max(0,2*u-1)**2*B;upper=(2*u+1)**2*B
            assert lower<=A<=upper
            assert (A not in (lower,upper)) or u%2==0
        verts.append(values)
    r.end()
    r=Reader(root/'candidate/tetrahedra.bin',2);assert r.count==8*n**3
    faces={};prior=None;maximum=0;minimum_radius=None;maximum_radius=0
    for i in range(r.count):
        assert r.u(8)==i+1
        ids=tuple(r.u(8)-1 for _ in range(4));assert len(set(ids))==4 and all(0<=j<len(verts) for j in ids)
        key=tuple(sorted(ids));assert prior is None or key>prior;prior=key
        ps=[verts[j] for j in ids]
        edges=[tuple(p[k]-ps[0][k] for k in range(3)) for p in ps[1:]]
        assert determinant(*edges)>0,('mapped_orientation',i+1)
        for a in range(4):
            for b in range(a):
                maximum=max(maximum,sum((ps[a][j]-ps[b][j])**2 for j in range(3)))
            f=[ids[j] for j in range(4) if j!=a]
            inv=sum(f[j]>f[k] for j in range(3) for k in range(j+1,3))
            sign=(-1)**(a+inv);fk=tuple(sorted(f));cnt,total=faces.get(fk,(0,0))
            assert cnt<2
            faces[fk]=(cnt+1,total+sign)
        radial=sum(sum(p[j] for p in ps)**2 for j in range(3))
        minimum_radius=radial if minimum_radius is None else min(minimum_radius,radial)
        maximum_radius=max(maximum_radius,radial)
    r.end();boundary=0
    for face,(count,sign) in faces.items():
        if count==2:assert sign==0
        else:
            boundary+=1
            assert all(sum(abs(x) for x in expected[j])==n for j in face),('unmatched_interior_face',face)
            assert sign*determinant(*[verts[j] for j in face])>0,('radial_boundary_orientation',face)
    assert boundary==8*n*n and len(faces)==16*n**3+4*n*n
    return dict(status='PASS',depth=depth,vertices=len(verts),tetrahedra=8*n**3,
                facets=len(faces),boundary_facets=boundary,
                delta_squared=str(Fraction(maximum,grid**2)),
                radial_squared_range=[str(Fraction(minimum_radius,16*grid**2)),str(Fraction(maximum_radius,16*grid**2))],
                complete_input_seal=False,candidate_evaluations=0)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--depth',type=int,required=True)
    a=p.parse_args();print(json.dumps(check(a.root,a.depth),sort_keys=True))
