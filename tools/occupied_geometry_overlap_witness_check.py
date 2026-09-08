"""Independent exact validation of the input overlap witness, without a search."""
import argparse
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path

from occupied_geometry_input_check import Reader
from occupied_geometry_incidence_check import facet_components


def verify(source,witness_directory):
    record=json.loads((witness_directory/'exact-overlap-witness.json').read_text())
    paths={'vertices.bin':source/'candidate/vertices.bin',
           'tetrahedra.bin':source/'candidate/tetrahedra.bin',
           'registered-motion.bin':witness_directory/'registered-motion.bin'}
    for name,path in paths.items():
        with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        assert digest==record['files'][name]['sha256']
        assert path.stat().st_size==record['files'][name]['size']
    r=Reader(paths['vertices.bin'],1);vertices={}
    for _ in range(r.count):
        identifier=r.u(8);vertices[identifier]=tuple(r.q() for _ in range(3))
    r.end();r=Reader(paths['registered-motion.bin'],7);velocities={}
    for i in range(r.count):
        assert r.u(8)==i+1;kind=r.u(1);identifier=r.u(8);v=tuple(r.q() for _ in range(3))
        if kind==1:velocities[identifier]=v
    r.end();r=Reader(paths['tetrahedra.bin'],2);cells={}
    for _ in range(r.count):
        identifier=r.u(8);cells[identifier]=tuple(r.u(8) for _ in range(4))
    r.end();point=tuple(Q(x) for x in record['witness']);t=Q(record['time'])
    assert t==2 and record['fixture']==5 and record['level']==0
    hits=record['positive_barycentric_witnesses'];assert len(hits)==2
    assert hits[0]['cell']!=hits[1]['cell']
    complexes=facet_components(cells)
    assert len(complexes)==2 and all(len(c)==64 for c in complexes)
    first=next(c for c in complexes if hits[0]['cell'] in c)
    assert hits[1]['cell'] not in first
    component={vertex for cell in first for vertex in cells[cell]}
    assert not component.intersection(cells[hits[1]['cell']])
    other=set(vertices)-component
    assert len(component)==len(other)==25
    assert len({velocities[i] for i in component})==1
    assert len({velocities[i] for i in other})==1
    for hit in hits:
        ids=cells[hit['cell']];assert list(ids)==hit['vertices']
        p=[tuple(vertices[i][a]+t*velocities[i][a] for a in range(3)) for i in ids]
        assert [[str(x) for x in v] for v in p]==hit['coordinates']
        bary=[Q(x) for x in hit['barycentric']]
        assert sum(bary)==1 and all(x>Q(1,256) for x in bary)
        assert tuple(sum(bary[j]*p[j][a] for j in range(4)) for a in range(3))==point
        # Independently establish affine rank by exact row elimination,
        # not the witness generator's determinant expansion.
        matrix=[[p[j][a]-p[0][a] for a in range(3)] for j in (1,2,3)]
        for col in range(3):
            pivot=next(i for i in range(col,3) if matrix[i][col])
            matrix[col],matrix[pivot]=matrix[pivot],matrix[col]
            d=matrix[col][col];matrix[col]=[x/d for x in matrix[col]]
            for i in range(col+1,3):
                c=matrix[i][col];matrix[i]=[x-c*y for x,y in zip(matrix[i],matrix[col])]
    print(json.dumps(dict(status='PASS',cells=[h['cell'] for h in hits],
        complex_adjacency='shared_full_triangular_facets',
        complex_sizes=[len(c) for c in complexes],
        all_barycentric_coordinates_strictly_greater_than='1/256',
        point=list(record['witness']),time='2',candidate_evaluations=0,
        complete_input_seal=False),sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('witness',type=Path)
    a=p.parse_args();verify(a.source,a.witness)
