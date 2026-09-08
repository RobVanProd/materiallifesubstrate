"""Independent exact analytical-domain and oriented-boundary pilot audit."""
import argparse
from collections import Counter
import copy
from fractions import Fraction as Q
import itertools
import json
from pathlib import Path
from occupied_geometry_query_check import registered_transform


def dot(a,b):return sum(x*y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def check(record,fixture,variant,diagnostic=True):
    assert fixture in (1,2) and variant in range(33)
    rotation,translation,boost,scale,_=registered_transform(variant)
    extents=(Q(1),Q(1),Q(1)) if fixture==1 else (Q(2),Q(2),Q(1,4))
    expected=set()
    for signs in itertools.product((-1,1),repeat=3):
        p=[s*e for s,e in zip(signs,extents)]
        expected.add(tuple(translation[i]+scale*dot(rotation[i],p) for i in range(3)))
    normals={tuple(s*rotation[i][j] for i in range(3)) for j in range(3) for s in (-1,1)}
    assert len(record['boundary_triangles'])==12
    seen=set();edges=Counter();signed_volume=Q(0);faces=Counter();planes={}
    for row in record['boundary_triangles']:
        p=[tuple(Q(x) for x in v) for v in row['vertices']];n=tuple(Q(x) for x in row['normal'])
        assert len(p)==3 and len(set(p))==3 and all(v in expected for v in p) and n in normals
        area=cross(sub(p[1],p[0]),sub(p[2],p[0]));assert dot(area,n)>0,'inconsistent outward winding'
        plane=dot(n,p[0]);assert all(dot(n,v)==plane for v in p)
        assert all(dot(n,v)<=plane for v in expected)
        faces[n]+=1;planes[n]=plane
        seen.update(p);signed_volume+=dot(p[0],cross(p[1],p[2]))/6
        for i in range(3):edges[p[i],p[(i+1)%3]]+=1
    assert seen==expected and set(faces)==normals and all(count==2 for count in faces.values())
    assert all(count==1 and edges[b,a]==1 for (a,b),count in edges.items())
    volume=8*extents[0]*extents[1]*extents[2]*scale**3
    assert signed_volume==volume and record['occupied_volume']==[str(volume),str(volume)]
    if not diagnostic:
        return dict(planes=planes,extents=extents,rotation=rotation,
                    translation=translation,scale=scale,volume=volume)
    centre=translation;distance=min(plane-dot(n,centre) for n,plane in planes.items())
    closest={tuple(centre[i]+distance*n[i] for i in range(3)) for n,plane in planes.items() if plane-dot(n,centre)==distance}
    diagnostic=record['centre_diagnostic'];assert diagnostic['member'] is True
    assert Q(diagnostic['distance_squared'])==distance**2
    assert {tuple(Q(x) for x in w['point']) for w in diagnostic['closest']}==closest
    for w in diagnostic['closest']:
        p=tuple(Q(x) for x in w['point'])
        active={n for n,plane in planes.items() if dot(n,p)==plane}
        assert {tuple(Q(x) for x in n) for n in w['normal_cone_rays']}==active
    assert record['work']==record['geometry']['projected_vertices']+43
    return dict(status='PASS',oriented_triangles=12,exact_boundary_volume=str(volume),
        exact_analytical_boundary_match=True,closest_set_size=len(closest),
        complete_row=False,complete_lab=False,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('record',type=Path);p.add_argument('--fixture',type=int,choices=(1,2),required=True)
    p.add_argument('--variant',type=int,choices=range(33),required=True);p.add_argument('output',type=Path)
    a=p.parse_args();assert not a.output.exists();record=json.loads(a.record.read_text())
    result=check(record,a.fixture,a.variant)
    bad=copy.deepcopy(record);v=bad['boundary_triangles'][0]['vertices'];v[1],v[2]=v[2],v[1]
    try:check(bad,a.fixture,a.variant)
    except AssertionError:result['reversed_orientation_mutation_rejected']=True
    else:raise AssertionError('orientation mutation survived')
    a.output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(result,sort_keys=True))
