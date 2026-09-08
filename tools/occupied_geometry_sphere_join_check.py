"""Independent complete sphere-table join and exact allocated-weight audit.

Does not import the sphere materializer, its reference enumerator or finisher.
The already independently replayed allocation records are numerical witnesses.
"""
import argparse
from fractions import Fraction as Q
import itertools
import json
from pathlib import Path
import resource
import time

from occupied_geometry_input_check import Reader


def children(cell):
    vertices=[tuple(2*x for x in p) for p in cell]
    for a,b in ((0,1),(0,2),(0,3),(1,2),(1,3),(2,3)):
        vertices.append(tuple(cell[a][j]+cell[b][j] for j in range(3)))
    indices=((0,4,5,6),(4,1,7,8),(5,7,2,9),(6,8,9,3),
             (4,5,6,8),(4,5,7,8),(5,6,8,9),(5,7,8,9))
    return tuple(tuple(vertices[j] for j in row) for row in indices)


def fraction(x):return Q(int(x[0]),int(x[1]))


def check(root,weights,depth):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));start=time.monotonic()
    n=2**depth;grid=2**256;total=fraction(json.loads((weights/'receipt.json').read_text())['total'])
    expected_weights={}
    with (weights/'allocation-witnesses.jsonl').open() as f:
        for raw in f:
            row=json.loads(raw)
            if len(row['path'])!=depth-1:continue
            for j,value in enumerate(row['child_weights']):expected_weights[tuple(row['path'])+(j,)]=fraction(value)
    assert len(expected_weights)==8**depth and 8*sum(expected_weights.values())==total
    reference=[p for p in itertools.product(range(-n,n+1),repeat=3) if sum(abs(x) for x in p)<=n]
    ids={p:i+1 for i,p in enumerate(reference)}
    r=Reader(root/'candidate/vertices.bin',1);assert r.count==len(reference);points=[]
    for i in range(r.count):
        assert r.u(8)==i+1
        p=tuple(r.q()*grid for _ in range(3));assert all(x.denominator==1 for x in p)
        points.append(tuple(x.numerator for x in p))
    r.end()
    one=[((),((0,0,0),(1,0,0),(0,1,0),(0,0,1)))]
    for _ in range(depth):one=[(path+(j,),child) for path,cell in one for j,child in enumerate(children(cell))]
    expected_cells={}
    for sign in itertools.product((-1,1),repeat=3):
        for path,cell in one:
            key=tuple(sorted(ids[tuple(sign[j]*p[j] for j in range(3))] for p in cell))
            assert key not in expected_cells;expected_cells[key]=expected_weights[path]
    r=Reader(root/'candidate/tetrahedra.bin',2);assert r.count==8*n**3
    cells=[];faces=set();samples=[];prior=None
    for i in range(r.count):
        assert r.u(8)==i+1;cell=tuple(r.u(8) for _ in range(4));key=tuple(sorted(cell))
        assert key in expected_cells and (prior is None or prior<key);prior=key
        cells.append(cell);centre=tuple(sum(points[v-1][j] for v in cell) for j in range(3))
        samples.append((centre,key,i+1,expected_cells[key]))
        for opposite in range(4):faces.add(tuple(sorted(cell[j] for j in range(4) if j!=opposite)))
    r.end();assert len(cells)==len(expected_cells)
    sorted_faces=sorted(faces);face_ids={v:i+1 for i,v in enumerate(sorted_faces)}
    r=Reader(root/'candidate/facets.bin',3);assert r.count==len(sorted_faces)
    for i,face in enumerate(sorted_faces):assert r.u(8)==i+1 and tuple(r.u(8) for _ in range(3))==face
    r.end();r=Reader(root/'candidate/incidence.bin',4);assert r.count==4*len(cells)
    for i,cell in enumerate(cells):
        for opposite in range(4):
            face=tuple(cell[j] for j in range(4) if j!=opposite)
            parity=(opposite+sum(face[j]>face[k] for j in range(3) for k in range(j+1,3)))%2
            assert (r.u(8),r.u(1),r.u(8),r.u(1))==(i+1,opposite,face_ids[tuple(sorted(face))],parity)
    r.end();r=Reader(root/'candidate/samples.bin',5);assert r.count==len(samples)
    sums=[Q(0),Q(0)]
    with (root/'oracle/sample-cell-join.jsonl').open() as joins:
        for i,(centre,key,cell_id,volume) in enumerate(sorted(samples)):
            assert r.u(8)==i+1
            assert tuple(r.q()*4*grid for _ in range(3))==centre
            actual_volume,amount=r.q(),r.q()
            assert actual_volume==volume and amount*total==volume
            sums[0]+=actual_volume;sums[1]+=amount
            assert json.loads(joins.readline())==[i+1,cell_id]
        assert joins.read(1)==''
    r.end();assert sums==[total,1]
    independent=json.loads((root/'independent-check.json').read_text())
    r=Reader(root/'candidate/resolution.bin',6);assert r.count==1
    assert r.q()==Q(independent['delta_squared']) and r.q()==total;r.end()
    assert time.monotonic()-start<=1800
    print(json.dumps(dict(status='PASS',depth=depth,cells=len(cells),samples=len(samples),
        exact_sample_cell_weight_joins=True,facets=len(faces),incidence=4*len(cells),
        candidate_evaluations=0,complete_input_seal=False),sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('weights',type=Path)
    p.add_argument('--depth',type=int,choices=range(1,6),required=True)
    a=p.parse_args();check(a.root,a.weights,a.depth)
