"""Exact pre-data audit of the mandatory moving-pair parcel-validity boundary.

This does not instantiate A/B/C or measure any candidate error. It checks
whether prescribed input motion preserves the stated global non-overlap rule.
"""
import argparse
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import struct

import occupied_geometry_input as encoding
from occupied_geometry_input_check import Reader,determinant


def det4(p):
    return determinant(*(tuple(p[i][a]-p[0][a] for a in range(3)) for i in (1,2,3)))


def audit(source,out):
    out.mkdir(parents=True,exist_ok=False)
    points={};counts={};material=[]
    for name,kind in (('vertices',1),('samples',5)):
        r=Reader(source/'candidate'/f'{name}.bin',kind);counts[kind]=r.count
        for _ in range(r.count):
            identifier=r.u(8);p=tuple(r.q() for _ in range(3))
            assert p[0]!=0
            velocity=(Q(1,2) if p[0]<0 else Q(-1,2),Q(0),Q(0))
            material.append((kind,identifier,velocity))
            if kind==1:points[identifier]=p
            else:r.q();r.q()
        r.end()
    motion=out/'registered-motion.bin'
    with motion.open('xb') as f:
        f.write(encoding.header(7,len(material)))
        for i,(kind,identifier,v) in enumerate(material):
            f.write(struct.pack('<QBQ',i+1,kind,identifier)+b''.join(encoding.rational(x) for x in v))
    # Decode actual motion bytes afresh, independently of their construction.
    r=Reader(motion,7);velocities={}
    for i in range(r.count):
        assert r.u(8)==i+1;kind=r.u(1);identifier=r.u(8);v=tuple(r.q() for _ in range(3))
        if kind==1:velocities[identifier]=v
    r.end();assert set(velocities)==set(points)
    r=Reader(source/'candidate/tetrahedra.bin',2);cells=[];parent={i:i for i in points}
    def find(i):
        while parent[i]!=i:i=parent[i]
        return i
    for _ in range(r.count):
        identifier=r.u(8);ids=tuple(r.u(8) for _ in range(4));cells.append((identifier,ids))
        for v in ids[1:]:parent[find(v)]=find(ids[0])
    r.end();assert len({find(i) for i in points})==2
    t=Q(2);witness=(Q(1,32),Q(1,16),Q(3,32));hits=[]
    for identifier,ids in cells:
        p=[tuple(points[i][a]+t*velocities[i][a] for a in range(3)) for i in ids]
        d=det4(p);assert d>0
        bary=[]
        for i in range(4):
            replaced=list(p);replaced[i]=witness;bary.append(det4(replaced)/d)
        assert sum(bary)==1
        if all(x>0 for x in bary):
            reconstructed=tuple(sum(bary[j]*p[j][a] for j in range(4)) for a in range(3))
            assert reconstructed==witness
            hits.append(dict(cell=identifier,vertices=ids,component_root=find(ids[0]),
                coordinates=[[str(x) for x in v] for v in p],
                barycentric=[str(x) for x in bary],determinant=str(d)))
    assert len(hits)==2 and hits[0]['component_root']!=hits[1]['component_root']
    files={}
    for path in [source/'candidate/vertices.bin',source/'candidate/tetrahedra.bin',motion]:
        with path.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
        files[path.name]=dict(size=path.stat().st_size,sha256=h)
    result=dict(schema='mls.occupied-geometry.prescribed-motion-validity-audit.v1',
        status='EXACT_CROSS_COMPONENT_INTERIOR_OVERLAP_AT_REGISTERED_TIME',
        fixture=5,level=0,time=str(t),witness=[str(x) for x in witness],
        positive_barycentric_witnesses=hits,files=files,
        global_nonoverlap_at_this_time=False,
        candidate_evaluations=0,complete_input_seal=False,
        interpretation='Protocol scope requires review; this is not a candidate geometry rejection.')
    (out/'exact-overlap-witness.json').write_text(json.dumps(result,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();audit(a.source,a.output)
