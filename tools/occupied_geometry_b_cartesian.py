"""B's proof-qualified Cartesian path: derive geometry from actual vertices.

Only an authenticated validity capability enables this path. No fixture label,
grid dimensions, transform or oracle geometry is supplied to the candidate.
All geometry construction below is runtime work and is charged accordingly.
"""
import hashlib
import json
from pathlib import Path
import gmpy2 as g
from occupied_geometry_runtime_wire import Reader

ROOT='8ec8ba42956f7664c66de26ce2f760be650cba76ef7fe0820d92396206e84516'
TEMPLATE='28c0c705017590785221212fa1e1aea7e283412cff0abd8b9ed0aa5683505dd5'


def dot(a,b):return sum((x*y for x,y in zip(a,b)),g.mpq(0))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))


def construct(view,capability,work):
    token=json.loads(capability.read_text())
    assert token['root_sha256']==ROOT and token['template_sha256']==TEMPLATE
    assert token['precondition']=='complete_uniform_cartesian_six_chain_mesh'
    assert token['valid_geometry_answers'] is False and token['runtime_geometry_work_exempt'] is False
    assert set(p.name for p in view.iterdir())==set(token['files'])=={f'{i}.bin' for i in range(1,9)}
    for name,value in token['files'].items():
        path=view/name;assert path.is_file() and not path.is_symlink() and path.stat().st_size==value['size']
        with path.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==value['sha256']
    # Read one actual cell and locate its four actual vertices. Canonical
    # decoding is exempt; each geometric edge test below is explicitly charged.
    r=Reader(view/'2.bin',2);assert r.count>0;r.uint(8);ids={r.uint(8) for _ in range(4)};r.f.close();assert len(ids)==4
    r=Reader(view/'1.bin',1);vertices={};count=r.count
    for _ in range(count):
        i=r.uint(8);p=tuple(r.q() for _ in range(3))
        if i in ids:vertices[i]=p
    r.end();assert set(vertices)==ids
    pairs={}
    for i in ids:
        for j in ids:
            if i<j:
                work.charge('cell_edge_metric');d=sub(vertices[j],vertices[i]);pairs[i,j]=dot(d,d)
    shortest=min(pairs.values());assert shortest>0
    adjacency={i:[] for i in ids}
    for (i,j),d in pairs.items():
        if d==shortest:adjacency[i].append(j);adjacency[j].append(i)
    ends=[i for i in ids if len(adjacency[i])==1]
    assert len(ends)==2 and sorted(map(len,adjacency.values()))==[1,1,2,2]
    chain=[min(ends,key=lambda i:vertices[i])]
    while len(chain)<4:
        choices=[i for i in adjacency[chain[-1]] if i not in chain];assert len(choices)==1;chain.append(choices[0])
    numerator=g.isqrt(shortest.numerator);denominator=g.isqrt(shortest.denominator)
    assert numerator*numerator==shortest.numerator and denominator*denominator==shortest.denominator
    step=g.mpq(numerator,denominator)
    axes=[tuple(x/step for x in sub(vertices[chain[i+1]],vertices[chain[i]])) for i in range(3)]
    for i in range(3):
        for j in range(i,3):work.charge('basis_orthogonality');assert dot(axes[i],axes[j])==int(i==j)
    low=[None]*3;high=[None]*3;r=Reader(view/'1.bin',1)
    for _ in range(r.count):
        r.uint(8);p=tuple(r.q() for _ in range(3));work.charge('vertex_projection_extrema')
        for j,axis in enumerate(axes):
            x=dot(axis,p);low[j]=x if low[j] is None else min(low[j],x);high[j]=x if high[j] is None else max(high[j],x)
    r.end();assert all(a<b for a,b in zip(low,high))
    # The complete-grid validity precondition proves that removing internal
    # cell faces leaves precisely these six planar patches. Their actual
    # coordinates, orientation, area/volume and queries are computed here.
    work.charge('derived_boundary_triangles',12)
    return dict(axes=axes,low=low,high=high,projected_vertices=count)


def world(local,axes):return tuple(sum((local[j]*axes[j][i] for j in range(3)),g.mpq(0)) for i in range(3))


def boundary(mesh,work):
    triangles=[];axes=mesh['axes'];low=mesh['low'];high=mesh['high']
    for j in range(3):
        other=[i for i in range(3) if i!=j]
        for side in (0,1):
            points=[]
            for a,b in ((0,0),(1,0),(1,1),(0,1)):
                local=list(low);local[j]=(low,high)[side][j]
                local[other[0]]=(low,high)[a][other[0]];local[other[1]]=(low,high)[b][other[1]]
                points.append(world(local,axes))
            normal=tuple((1 if side else -1)*x for x in axes[j])
            for a,b,c in ((0,1,2),(0,2,3)):
                work.charge('boundary_patch_witness')
                triangles.append(dict(vertices=[points[a],points[b],points[c]],normal=normal))
    return triangles


def point_query(mesh,p,work):
    work.charge('boundary_face_distance_predicates',6)
    axes=mesh['axes'];lo=mesh['low'];hi=mesh['high'];u=[dot(a,p) for a in axes]
    inside=all(a<=x<=b for a,x,b in zip(lo,u,hi));answers=[]
    if inside:
        distance=min([u[j]-lo[j] for j in range(3)]+[hi[j]-u[j] for j in range(3)])
        for j in range(3):
            for side,bound in ((-1,lo[j]),(1,hi[j])):
                if abs(u[j]-bound)==distance:
                    q=u.copy();q[j]=bound;answers.append(world(q,axes))
        distance2=distance*distance
    else:
        q=[max(a,min(x,b)) for a,x,b in zip(lo,u,hi)]
        distance2=sum(((x-y)**2 for x,y in zip(u,q)),g.mpq(0));answers=[world(q,axes)]
    witnesses=[]
    for q in sorted(set(answers)):
        local=[dot(a,q) for a in axes];normals=[]
        for j in range(3):
            if local[j]==lo[j]:normals.append(tuple(-x for x in axes[j]))
            if local[j]==hi[j]:normals.append(tuple(axes[j]))
        witnesses.append(dict(point=q,normal_cone_rays=sorted(normals)))
    return dict(member=inside,distance_squared=distance2,closest=witnesses)
