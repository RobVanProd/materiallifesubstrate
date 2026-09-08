"""Single-complex B exact boundary/point-query path after runtime validity.

Multi-complex union boundary and swept queries are deliberately not interpreted
by this module. An unsupported inventory is not a scientific pass.
"""
from collections import deque
import gmpy2 as g
from occupied_geometry_exact_primitives import closest_triangle,orientation,cross,sub,dot


def construct(vertices,cells,facets,owners,components,work):
    assert len(set(components.values()))==1,'requires one connected complex'
    triangles=[];volume=g.mpq(0)
    for ids in cells.values():
        # Already positive, disjoint cell volumes may be added exactly.
        volume+=orientation([vertices[i] for i in ids],work)/6
    for ident,row in owners.items():
        if len(row)!=1:continue
        work.charge('derived_exterior_triangle')
        ids=list(facets[ident]);_,sign=row[0]
        if sign:ids[1],ids[2]=ids[2],ids[1]
        p=[vertices[i] for i in ids];n=cross(sub(p[1],p[0]),sub(p[2],p[0]))
        assert any(n);triangles.append((tuple(p),n))
    triangles.sort(key=lambda row:tuple(sorted(row[0])))
    bounds=[]
    for p,n in triangles:
        work.charge('triangle_bounding_region')
        bounds.append(tuple((min(v[j] for v in p),max(v[j] for v in p)) for j in range(3)))
    def tree(ids):
        if len(ids)==1:return bounds[ids[0]],ids[0],None,None
        work.charge('boundary_bvh_node')
        box=tuple((min(bounds[i][j][0] for i in ids),max(bounds[i][j][1] for i in ids)) for j in range(3))
        widths=[b-a for a,b in box];axis=widths.index(max(widths))
        ids.sort(key=lambda i:(sum(bounds[i][axis]),i));m=len(ids)//2
        return box,None,tree(ids[:m]),tree(ids[m:])
    return dict(volume=volume,triangles=triangles,tree=tree(list(range(len(triangles)))))


def query(mesh,point,work):
    # Breadth-first fixed tree order. Exact point/triangle projections furnish
    # existence witnesses; ties are never pruned or broken by feature ID.
    todo=deque([mesh['tree']]);best=None;closest={}
    while todo:
        box,ident,left,right=todo.popleft();work.charge('point_boundary_box_bound')
        lower=sum((max(a-x,g.mpq(0),x-b)**2 for x,(a,b) in zip(point,box)),g.mpq(0))
        if best is not None and lower>best:continue
        if ident is None:todo.extend((left,right));continue
        triangle,normal=mesh['triangles'][ident]
        distance,witness=closest_triangle(triangle,point,work)
        if best is None or distance<best:best=distance;closest={}
        if distance==best:
            work.charge('closest_feature_witness')
            # Use a canonical rational ray, not a falsely exact unit normal.
            factor=next(abs(x) for x in normal if x)
            ray=tuple(x/factor for x in normal)
            closest.setdefault(witness,set()).add(ray)
    assert best is not None
    return dict(distance_squared=best,closest=[dict(point=p,incident_outward_normal_rays=sorted(rays)) for p,rays in sorted(closest.items())])
