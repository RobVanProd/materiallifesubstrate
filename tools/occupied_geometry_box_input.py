"""Streaming canonical Cartesian/U input primitives, with no candidate code.

Facet ranks are derived from the twelve possible Boolean-chain triangles at
each least vertex. No adaptive reconstruction/search is performed here.
"""
import argparse
from array import array
from fractions import Fraction as Q
import hashlib
import itertools
import json
from pathlib import Path
import resource
import struct
import sys
import time

sys.dont_write_bytecode=True
import occupied_geometry_input as wire

AXES=tuple(itertools.permutations(range(3)))
PATTERNS=tuple((u,v) for u in itertools.product((0,1),repeat=3)
               for v in itertools.product((0,1),repeat=3)
               if any(u) and u!=v and all(a<=b for a,b in zip(u,v)))


class Grid:
    def __init__(self,fixture,level):
        self.fixture=fixture;self.m=1<<level;self.denom=4*self.m
        m=self.m
        self.low=(-8*m,-8*m,-m) if fixture=='slab' else (-4*m,-4*m,-m if fixture=='u' else -4*m)
        self.high=(8*m,8*m,m) if fixture=='slab' else (4*m,4*m,m if fixture=='u' else 4*m)
        self.shape=tuple(b-a+1 for a,b in zip(self.low,self.high))
        count=self.shape[0]*self.shape[1]*self.shape[2]
        self.ids=array('I',[0])*count
        self.facet_start=array('Q',[0])*count
        self.vertices=0;self.facets=0
        self.pattern_cache={};self.pattern_index={}
        for v in self.points():
            if self.has_vertex(v):
                self.vertices+=1;self.ids[self.slot(v)]=self.vertices
        for v in self.points():
            if self.id(v):
                self.facet_start[self.slot(v)]=self.facets+1
                self.facets+=len(self.pattern_codes(v))

    def points(self):return itertools.product(*(range(a,b+1) for a,b in zip(self.low,self.high)))
    def cells(self):return itertools.product(*(range(a,b) for a,b in zip(self.low,self.high)))
    def slot(self,v):
        a,b,c=(x-y for x,y in zip(v,self.low))
        return (a*self.shape[1]+b)*self.shape[2]+c
    def id(self,v):
        if any(x<a or x>b for x,a,b in zip(v,self.low,self.high)):return 0
        return self.ids[self.slot(v)]
    def inside(self,v):
        if any(x<a or x>=b for x,a,b in zip(v,self.low,self.high)):return False
        if self.fixture!='u':return True
        x,y,_=v;m=self.m
        return y < -3*m or x < -3*m or x>=3*m
    def has_vertex(self,v):
        if self.fixture!='u':return True
        return any(self.inside(tuple(v[j]-e[j] for j in range(3)))
                   for e in itertools.product((0,1),repeat=3))
    def pattern_key(self,v):
        mask=sum((v[j]<self.high[j])<<j for j in range(3))
        if self.fixture!='u':return mask,None
        owners=(self.inside(v),)+tuple(self.inside(tuple(v[j]-(j==a) for j in range(3))) for a in range(3))
        return mask,owners
    def pattern_codes(self,v):
        key=self.pattern_key(v)
        if key not in self.pattern_cache:
            mask,owners=key
            patterns=[(u,w) for u,w in PATTERNS
                      if all(not w[j] or mask&(1<<j) for j in range(3))
                      and (owners is None or owners[0] or
                           any(not w[j] and owners[j+1] for j in range(3)))]
            self.pattern_cache[key]=patterns
            self.pattern_index[key]={pair:i for i,pair in enumerate(patterns)}
        return self.pattern_cache[key]
    def patterns(self,v):
        return [(self.id(tuple(v[j]+u[j] for j in range(3))),
                 self.id(tuple(v[j]+w[j] for j in range(3))),u,w)
                for u,w in self.pattern_codes(v)]
    def facet_id(self,points):
        v,p,q=sorted(points)
        pair=(tuple(p[j]-v[j] for j in range(3)),tuple(q[j]-v[j] for j in range(3)))
        return self.facet_start[self.slot(v)]+self.pattern_index[self.pattern_key(v)][pair]


def tets(v):
    for axes in AXES:
        p=list(v);out=[tuple(p)]
        for axis in axes:p[axis]+=1;out.append(tuple(p))
        yield tuple(out)


def write_inputs(out,fixture,level):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    started=time.monotonic();deadline=started+1800
    out.mkdir(parents=True,exist_ok=False);(out/'candidate').mkdir();(out/'oracle').mkdir()
    grid=Grid(fixture,level);m=grid.m
    cubes=(44 if fixture=='u' else 512)*m**3;tet_count=6*cubes
    boundary=2*(grid.facets-2*tet_count)
    weight=Q(1,6*grid.denom**3);total=cubes*Q(1,grid.denom**3)
    # Coordinate atoms repeat, so cache exact canonical encodings only.
    atoms={n:wire.rational(Q(n,4*grid.denom))
           for n in range(4*min(grid.low),4*max(grid.high)+1)}
    paths={name:out/'candidate'/f'{name}.bin' for name in
           ('vertices','tetrahedra','facets','incidence','samples','resolution')}
    with paths['vertices'].open('xb') as f:
        f.write(wire.header(1,grid.vertices))
        for v in grid.points():
            identifier=grid.id(v)
            if identifier:f.write(struct.pack('<Q',identifier)+b''.join(atoms[4*x] for x in v))
    with paths['facets'].open('xb') as f:
        f.write(wire.header(3,grid.facets));seen=0
        for v in grid.points():
            identifier=grid.id(v)
            if not identifier:continue
            for a,b,_,_ in grid.patterns(v):
                seen+=1;f.write(struct.pack('<4Q',seen,identifier,a,b))
        assert seen==grid.facets
    with paths['tetrahedra'].open('xb') as tf,paths['incidence'].open('xb') as inf:
        tf.write(wire.header(2,tet_count));inf.write(wire.header(4,4*tet_count));seen=0
        for v in grid.cells():
            if not grid.inside(v):continue
            for cell in sorted(tets(v),key=lambda t:tuple(grid.id(p) for p in t)):
                seen+=1;oriented=list(cell)
                if wire.determinant(oriented)<0:oriented[-1],oriented[-2]=oriented[-2],oriented[-1]
                ids=[grid.id(p) for p in oriented]
                tf.write(struct.pack('<5Q',seen,*ids))
                for a in range(4):
                    face=[p for j,p in enumerate(oriented) if j!=a]
                    fi=[grid.id(p) for p in face]
                    inv=sum(fi[j]>fi[k] for j in range(3) for k in range(j+1,3))
                    inf.write(struct.pack('<QBQB',seen,a,grid.facet_id(face),(a+inv)%2))
            if time.monotonic()>deadline:raise TimeoutError('input wall-time ceiling')
        assert seen==tet_count
    with paths['samples'].open('xb') as f:
        f.write(wire.header(5,tet_count));seen=0
        suffix=wire.rational(weight)+wire.rational(weight/total)
        for x in range(grid.low[0],grid.high[0]):
            for ox in range(1,4):
                for y in range(grid.low[1],grid.high[1]):
                    for oy in (j for j in range(1,4) if j!=ox):
                        oz=6-ox-oy
                        for z in range(grid.low[2],grid.high[2]):
                            if not grid.inside((x,y,z)):continue
                            seen+=1
                            f.write(struct.pack('<Q',seen)+atoms[4*x+ox]+atoms[4*y+oy]+atoms[4*z+oz]+suffix)
        assert seen==tet_count
    with paths['resolution'].open('xb') as f:
        f.write(wire.header(6,1)+wire.rational(Q(3,grid.denom**2))+wire.rational(total))
    files={}
    for name,path in paths.items():
        with path.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
        files[path.name]=dict(size=path.stat().st_size,sha256=h)
    receipt=dict(schema='mls.occupied-geometry.partial-input.v1',fixture=fixture,level=level,
        vertices=grid.vertices,cubes=cubes,tetrahedra=tet_count,facets=grid.facets,
        boundary_facets=boundary,incidence=4*tet_count,samples=tet_count,files=files,
        complete_input_seal=False,candidate_evaluations=0)
    (out/'oracle/input-check.json').write_text(json.dumps(receipt,sort_keys=True)+'\n')
    print(json.dumps(receipt,sort_keys=True),flush=True)
    print('seconds',time.monotonic()-started,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path)
    p.add_argument('--fixture',choices=('cube','slab','u'),required=True)
    p.add_argument('--level',type=int,choices=range(5),required=True)
    a=p.parse_args();write_inputs(a.output,a.fixture,a.level)
