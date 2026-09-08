"""Independent streaming verification of frozen Cartesian primitive bytes.

Uses the registered lattice/Kuhn membership characterization, not the generator's
facet-ranking implementation. Checks actual facet joins and every incidence.
"""
import argparse
from array import array
from fractions import Fraction as Q
import json
import mmap
from pathlib import Path
import resource
import struct
import time

from occupied_geometry_input_check import Reader,determinant


def check(root,fixture,level):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    started=time.monotonic();m=1<<level;denom=4*m
    low=(-8*m,-8*m,-m) if fixture=='slab' else (-4*m,-4*m,-m if fixture=='u' else -4*m)
    high=(8*m,8*m,m) if fixture=='slab' else (4*m,4*m,m if fixture=='u' else 4*m)
    cubes=(44 if fixture=='u' else 512)*m**3;expected_tets=6*cubes
    def inside(p):
        return all(a<=v<b for v,a,b in zip(p,low,high)) and (
            fixture!='u' or p[1]<-3*m or p[0]<-3*m or p[0]>=3*m)
    vertices=array('i');r=Reader(root/'candidate/vertices.bin',1)
    prior=None;vertex_count=r.count
    for i in range(r.count):
        assert r.u(8)==i+1
        p=tuple(r.q()*denom for _ in range(3))
        assert all(v.denominator==1 for v in p)
        p=tuple(int(v) for v in p);assert prior is None or prior<p;prior=p
        assert all(a<=v<=b for v,a,b in zip(p,low,high))
        vertices.extend(p)
    r.end()
    def vertex(i):
        assert 1<=i<=vertex_count
        return tuple(vertices[3*(i-1):3*i])
    facets=Reader(root/'candidate/facets.bin',3);facet_count=facets.count
    counts=bytearray(facet_count);parity=array('b',[0])*facet_count
    mapped=mmap.mmap(facets.f.fileno(),0,access=mmap.ACCESS_READ)
    assert len(mapped)==24+32*facet_count
    prior=None
    for i in range(facet_count):
        number,*face=struct.unpack_from('<4Q',mapped,24+32*i)
        assert number==i+1 and 1<=face[0]<face[1]<face[2]<=vertex_count
        assert prior is None or prior<face;prior=face
    r=Reader(root/'candidate/tetrahedra.bin',2)
    incidences=Reader(root/'candidate/incidence.bin',4)
    assert r.count==expected_tets and incidences.count==4*r.count
    prior=None;maximum=0
    for i in range(r.count):
        assert r.u(8)==i+1
        ids=tuple(r.u(8) for _ in range(4));key=tuple(sorted(ids))
        assert len(set(ids))==4 and (prior is None or prior<key);prior=key
        ps=[vertex(j) for j in ids]
        ordered=sorted(ps);base=ordered[0];assert inside(base)
        # The complete set of six monotone unit-coordinate chains is exactly
        # the Kuhn partition. Canonical uniqueness plus the frozen count gives
        # completeness, without trusting generator labels or cell ordinals.
        increments=[tuple(ordered[j+1][a]-ordered[j][a] for a in range(3)) for j in range(3)]
        assert sorted(increments)==[(0,0,1),(0,1,0),(1,0,0)]
        edges=[tuple(p[a]-ps[0][a] for a in range(3)) for p in ps[1:]]
        assert determinant(*edges)==1
        for a in range(4):
            for b in range(a):maximum=max(maximum,sum((ps[a][j]-ps[b][j])**2 for j in range(3)))
            assert incidences.u(8)==i+1 and incidences.u(1)==a
            fid=incidences.u(8);sign=incidences.u(1)
            assert 1<=fid<=facet_count and sign in (0,1)
            face=[ids[j] for j in range(4) if j!=a]
            inv=sum(face[j]>face[k] for j in range(3) for k in range(j+1,3))
            assert sign==(a+inv)%2
            raw=struct.unpack_from('<4Q',mapped,24+32*(fid-1))
            assert tuple(sorted(face))==raw[1:]
            counts[fid-1]+=1;assert counts[fid-1]<=2
            parity[fid-1]+=1 if sign==0 else -1
        if i%4096==0:assert time.monotonic()-started<1800,'input verification wall-time ceiling'
    r.end();incidences.end();mapped.close();facets.f.close()
    boundary=0
    for count,sign in zip(counts,parity):
        assert count in (1,2)
        if count==2:assert sign==0
        else:boundary+=1;assert abs(sign)==1
    assert facet_count==2*expected_tets+boundary//2
    if fixture!='u':
        nx,ny,nz=(b-a for a,b in zip(low,high))
        assert vertex_count==(nx+1)*(ny+1)*(nz+1)
        assert boundary==4*(nx*ny+ny*nz+nz*nx)
    volume=Q(1,6*denom**3);total=Q(cubes,denom**3)
    r=Reader(root/'candidate/samples.bin',5);assert r.count==expected_tets
    prior=None
    for i in range(r.count):
        assert r.u(8)==i+1
        xyz=tuple(r.q() for _ in range(3));scaled=tuple(x*4*denom for x in xyz)
        assert all(x.denominator==1 for x in scaled)
        scaled=tuple(int(x) for x in scaled)
        assert prior is None or prior<scaled;prior=scaled
        assert sorted(x%4 for x in scaled)==[1,2,3]
        assert inside(tuple(x//4 for x in scaled))
        assert r.q()==volume and r.q()==volume/total
    r.end()
    r=Reader(root/'candidate/resolution.bin',6)
    assert r.count==1 and r.q()==Q(maximum,denom**2) and r.q()==total;r.end()
    assert time.monotonic()-started<1800,'input verification wall-time ceiling'
    return dict(status='PASS',fixture=fixture,level=level,vertices=vertex_count,
                tetrahedra=expected_tets,facets=facet_count,boundary_facets=boundary,
                incidence=4*expected_tets,samples=expected_tets,
                delta_squared=str(Q(maximum,denom**2)),
                candidate_evaluations=0,complete_input_seal=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path)
    p.add_argument('--fixture',choices=('cube','slab','u'),required=True)
    p.add_argument('--level',type=int,choices=range(5),required=True)
    a=p.parse_args();print(json.dumps(check(a.root,a.fixture,a.level),sort_keys=True))
