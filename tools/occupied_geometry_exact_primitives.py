"""Exact rational geometry primitives; no fixture or oracle dependencies.

All public primitive evaluations consume the caller's shared work counter.
These predicates do not themselves establish a complete mesh/union certificate.
"""
import itertools
import gmpy2 as g


def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def dot(a,b):return sum((x*y for x,y in zip(a,b)),g.mpq(0))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def determinant(a,b,c):return dot(a,cross(b,c))


def orientation(tet,work):
    work.charge('tetrahedron_orientation')
    assert len(tet)==4
    return determinant(sub(tet[1],tet[0]),sub(tet[2],tet[0]),sub(tet[3],tet[0]))


def halfspaces(tet):
    """Internal fixed-size algebra: outward planes n.x <= d."""
    planes=[]
    for opposite in range(4):
        p=[tet[i] for i in range(4) if i!=opposite]
        n=cross(sub(p[1],p[0]),sub(p[2],p[0]));d=dot(n,p[0])
        value=dot(n,tet[opposite])-d
        assert value!=0,'degenerate tetrahedron'
        if value>0:n=tuple(-x for x in n);d=-d
        planes.append((n,d))
    return planes


def tetrahedron_membership(tet,point,work):
    work.charge('tetrahedron_membership')
    values=[dot(n,point)-d for n,d in halfspaces(tet)]
    return dict(closed=all(x<=0 for x in values),strict=all(x<0 for x in values))


def tetrahedron_intersection(a,b,work):
    """Full-dimensional convex tetrahedra: SAT with face/edge axes.

    Strictly separated projections imply disjointness. Equality on a separating
    plane means contact, not positive-volume overlap. No epsilon is introduced.
    """
    work.charge('tetrahedron_pair_intersection')
    axes=[n for n,d in halfspaces(a)]+[n for n,d in halfspaces(b)]
    ea=[sub(a[j],a[i]) for i,j in itertools.combinations(range(4),2)]
    eb=[sub(b[j],b[i]) for i,j in itertools.combinations(range(4),2)]
    axes.extend(cross(u,v) for u in ea for v in eb)
    touching=False
    for n in axes:
        if not any(n):continue
        aa=[dot(n,p) for p in a];bb=[dot(n,p) for p in b]
        gap=max(min(aa)-max(bb),min(bb)-max(aa))
        if gap>0:return 'disjoint'
        touching|=gap==0
    return 'touching' if touching else 'positive_volume_overlap'


def closest_triangle(triangle,point,work):
    """Unique metric projection to a closed nondegenerate triangle."""
    work.charge('point_triangle_distance')
    a,b,c=triangle;u=sub(b,a);v=sub(c,a);w=sub(point,a)
    uu=dot(u,u);uv=dot(u,v);vv=dot(v,v);wu=dot(w,u);wv=dot(w,v)
    denominator=uu*vv-uv*uv;assert denominator>0
    s=(wu*vv-wv*uv)/denominator;t=(wv*uu-wu*uv)/denominator
    points=[]
    if s>=0 and t>=0 and s+t<=1:
        points.append(tuple(a[i]+s*u[i]+t*v[i] for i in range(3)))
    for x,y in ((a,b),(b,c),(c,a)):
        edge=sub(y,x);q=max(g.mpq(0),min(g.mpq(1),dot(sub(point,x),edge)/dot(edge,edge)))
        points.append(tuple(x[i]+q*edge[i] for i in range(3)))
    distances=[dot(sub(p,point),sub(p,point)) for p in points]
    best=min(distances);witnesses={p for d,p in zip(distances,points) if d==best}
    assert len(witnesses)==1
    return best,next(iter(witnesses))
