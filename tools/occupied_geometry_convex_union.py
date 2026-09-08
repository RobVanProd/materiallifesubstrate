"""Exact convex-polyhedron intersection and union boundary primitives.

Inputs must be independently certified convex, closed, outward oriented
polyhedra. This module does not assert that arbitrary material complexes are
convex. Overlapping boundary covers are allowed; volume is inclusion-exclusion,
never a sum of overlapping occupied volumes or duplicate surface integrals.
"""
from functools import cmp_to_key
import gmpy2 as g
from occupied_geometry_exact_primitives import dot,sub,cross


def clip_polygon(polygon,normal,d,work):
    values=[]
    for p in polygon:
        work.charge('vertex_plane_predicate');values.append(dot(normal,p)-d)
    if all(v<=0 for v in values):return list(polygon),[],False
    out=[];cut=[]
    for i,a in enumerate(polygon):
        b=polygon[(i+1)%len(polygon)];va=values[i];vb=values[(i+1)%len(values)]
        if va<=0:out.append(a)
        if va==0:cut.append(a)
        if (va<0<vb) or (vb<0<va):
            work.charge('edge_plane_intersection')
            work.charge('derived_cut_vertex')
            t=va/(va-vb);p=tuple(a[j]+t*(b[j]-a[j]) for j in range(3))
            out.append(p);cut.append(p)
    out=list(dict.fromkeys(out));cut=list(dict.fromkeys(cut))
    if len(out)>=3:work.charge('clipped_polygon')
    return out if len(out)>=3 else [],cut,True


def planar_order(points,normal,work):
    points=sorted(set(points))
    if len(points)<3:return []
    centre=tuple(sum(p[j] for p in points)/len(points) for j in range(3))
    axis=next(tuple(g.mpq(i==j) for j in range(3)) for i in range(3)
              if any(cross(normal,tuple(g.mpq(i==j) for j in range(3)))))
    u=cross(normal,axis);v=cross(normal,u)
    work.charge('planar_coordinate_cache_entries',len(points))
    coords={p:(dot(sub(p,centre),u),dot(sub(p,centre),v)) for p in points}
    def compare(a,b):
        work.charge('planar_orientation_order')
        x,y=coords[a];xx,yy=coords[b]
        h=int(y<0 or (y==0 and x<0));hh=int(yy<0 or (yy==0 and xx<0))
        if h!=hh:return -1 if h<hh else 1
        determinant=x*yy-y*xx
        if determinant:return -1 if determinant>0 else 1
        aa=x*x+y*y;bb=xx*xx+yy*yy
        return (aa>bb)-(aa<bb)
    ordered=sorted(points,key=cmp_to_key(compare))
    area=tuple(sum(cross(sub(ordered[i],centre),sub(ordered[(i+1)%len(ordered)],centre))[j]
                   for i in range(len(ordered))) for j in range(3))
    if dot(area,normal)==0:return []
    assert dot(area,normal)>0
    work.charge('intersection_cap_polygon');return ordered


def intersection(faces,planes,work):
    current=[list(p) for p in faces]
    work.charge('intersection_face_copies',len(current))
    for normal,d in planes:
        next_faces=[];cuts=[];changed=False
        for polygon in current:
            clipped,points,did_change=clip_polygon(polygon,normal,d,work)
            if clipped:next_faces.append(clipped)
            cuts.extend(points);changed|=did_change
        if changed:
            cap=planar_order(cuts,normal,work)
            if cap:next_faces.append(cap)
        current=next_faces
        if not current:break
    return current


def volume(faces,work):
    result=g.mpq(0)
    for polygon in faces:
        for j in range(1,len(polygon)-1):
            work.charge('oriented_volume_triangle')
            result+=dot(polygon[0],cross(polygon[j],polygon[j+1]))/6
    assert result>=0,'non-outward or invalid intersection surface'
    return result


def exposed(faces,other_planes,work):
    result=[]
    for polygon in faces:
        normal=None
        for j in range(1,len(polygon)-1):
            work.charge('polygon_orientation_predicate')
            candidate=cross(sub(polygon[j],polygon[0]),sub(polygon[j+1],polygon[0]))
            if any(candidate):normal=candidate;break
        assert normal is not None
        remaining=list(polygon)
        for n,d in other_planes:
            if not remaining:break
            work.charge('coplanar_patch_predicate')
            work.charge('coplanar_vertex_plane_predicates',len(remaining))
            coplanar=all(dot(n,p)==d for p in remaining)
            # Opposite coplanar faces at an interior touching interface are
            # buried, not exposed just because each is a component boundary.
            if coplanar and dot(n,normal)<0:continue
            outside,_,_=clip_polygon(remaining,tuple(-x for x in n),-d,work)
            if outside:result.append(outside)
            remaining,_,_=clip_polygon(remaining,n,d,work)
        # The remainder is inside the other occupied solid and is discarded.
    return result
