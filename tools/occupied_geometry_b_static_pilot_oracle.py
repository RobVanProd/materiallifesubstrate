"""Independent complete static-pilot check against actual boundary facets.

Uses exact face enumeration, not the candidate's boundary BVH or predicates.
The convex containment check is an audited precondition of this small oracle;
it is not assumed for arbitrary B input and is not supplied to the candidate.
"""
import argparse
from collections import Counter
from fractions import Fraction as Q
import json
from pathlib import Path
from occupied_geometry_input_check import Reader
from occupied_geometry_query_check import parse
from occupied_geometry_exact_primitive_oracle import solve,det


def dot(a,b):return sum(x*y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def check(view,record):
    vertices={};r=Reader(view/'1.bin',1)
    for _ in range(r.count):
        ident=r.u(8);vertices[ident]=tuple(r.q() for _ in range(3))
    r.end();faces=Counter();volume=Q(0);r=Reader(view/'2.bin',2)
    for _ in range(r.count):
        r.u(8);ids=[r.u(8) for _ in range(4)];p=[vertices[i] for i in ids]
        d=det([sub(p[j],p[0]) for j in (1,2,3)]);assert d>0;volume+=d/6
        for opposite in range(4):
            face=[ids[j] for j in range(4) if j!=opposite]
            sign=(-1)**(opposite+sum(face[i]>face[j] for i in range(3) for j in range(i+1,3)))
            faces[tuple(sorted(face))]+=sign
    r.end();expected={tuple(sorted(vertices[i] for i in face)) for face,sign in faces.items() if sign}
    assert all(sign in (-1,0,1) for sign in faces.values())
    triangles=[];planes=[];edges=Counter();surface_volume=Q(0)
    for row in record['boundary_triangles']:
        p=[tuple(Q(x) for x in v) for v in row['vertices']]
        n=cross(sub(p[1],p[0]),sub(p[2],p[0]));assert any(n)
        assert list(n)==[Q(x) for x in row['normal_ray']]
        d=dot(n,p[0]);assert all(dot(n,v)<=d for v in vertices.values()),'convex oracle precondition unresolved'
        triangles.append(p);planes.append((n,d));surface_volume+=det(p)/6
        for i in range(3):edges[p[i],p[(i+1)%3]]+=1
    assert len(triangles)==len(expected) and {tuple(sorted(p)) for p in triangles}==expected
    assert all(count==1 and edges[b,a]==1 for (a,b),count in edges.items())
    assert volume==surface_volume and record['occupied_volume']==[str(volume)]*2
    def projected(triangle,point):
        a,b,c=triangle;u=sub(b,a);v=sub(c,a);n=cross(u,v)
        s,t,_=solve([[u[i],v[i],n[i]] for i in range(3)],sub(point,a))
        points=[]
        if s>=0 and t>=0 and s+t<=1:points.append(tuple(a[i]+s*u[i]+t*v[i] for i in range(3)))
        for x,y in ((a,b),(b,c),(c,a)):
            e=sub(y,x);fraction=max(Q(0),min(Q(1),dot(sub(point,x),e)/dot(e,e)))
            points.append(tuple(x[i]+fraction*e[i] for i in range(3)))
        return min((dot(sub(p,point),sub(p,point)),p) for p in points)
    r=Reader(view/'8.bin',8);queries={}
    for _ in range(r.count):
        ident=r.u(8);op=r.u(1);args=parse(op,r.read(r.u(8)));assert args[-1]==0
        assert ident not in queries;queries[ident]=(op,args)
    r.end();checked=0
    for row in record['queries']:
        op,args=queries[row['id']];assert op==row['operation'];actual=row['result']
        if op==1:assert actual==dict(volume=[str(volume)]*2)
        elif op==2:assert actual==dict(boundary_reference='exact-oriented-triangles')
        elif op==7:assert actual==dict(member=all(dot(n,args[0])<=d for n,d in planes))
        else:
            assert op in (3,4);answers=[projected(p,args[0]) for p in triangles]
            best=min(d for d,p in answers);witnesses={}
            for (distance,p),(n,_) in zip(answers,planes):
                if distance!=best:continue
                factor=next(abs(x) for x in n if x)
                witnesses.setdefault(p,set()).add(tuple(x/factor for x in n))
            expected_rows=[dict(point=[str(x) for x in p],incident_outward_normal_rays=[[str(x) for x in ray] for ray in sorted(rays)]) for p,rays in sorted(witnesses.items())]
            assert actual==dict(distance_squared=str(best),closest=expected_rows),row['id']
        checked+=1
    if record['status']=='STATIC_QUERY_INVENTORY_COMPLETE':assert checked==len(queries)
    else:assert record['status']=='STATIC_QUERY_RESOURCE_INCONCLUSIVE' and checked<len(queries)
    return dict(status='PASS_INDEPENDENT_STATIC_PILOT',checked_queries=checked,
                total_queries=len(queries),exact_boundary_triangles=len(triangles),
                exact_volume=str(volume),complete_lab=False,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('view',type=Path);p.add_argument('record',type=Path)
    p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists()
    result=check(a.view,json.loads(a.record.read_text()))
    a.output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(result,sort_keys=True))
