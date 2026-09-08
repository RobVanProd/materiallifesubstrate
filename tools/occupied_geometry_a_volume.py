"""Candidate A union-volume cover. Overlaps are never summed as occupied volume."""
from collections import deque
import gmpy2 as g
from occupied_geometry_runtime_wire import WorkLimit


def radii(weights,work):
    result={}
    with g.context(precision=256,round=g.RoundDown):pi_lo=g.const_pi()
    with g.context(precision=256,round=g.RoundUp):pi_hi=g.const_pi()
    for weight in weights:
        if weight in result:continue
        work.charge('radius_cache_entry')
        work.charge('radius_enclosure_update')
        with g.context(precision=256,round=g.RoundDown):
            lo=g.rootn(3*g.mpfr(weight)/(4*pi_hi),3);lo2=lo*lo
        with g.context(precision=256,round=g.RoundUp):
            hi=g.rootn(3*g.mpfr(weight)/(4*pi_lo),3);hi2=hi*hi
        assert 0<lo<=hi
        result[weight]=(g.mpq(lo2),g.mpq(hi2),g.mpq(hi))
    return result


def classification(box,points,weights,cache,work):
    work.charge('sphere_box_predicates',len(points))
    inside=False;outside=True
    for p,w in zip(points,weights):
        minimum=g.mpq(0);maximum=g.mpq(0)
        for x,(a,b) in zip(p,box):
            near=max(a-x,g.mpq(0),x-b)
            minimum+=near*near;maximum+=max((a-x)**2,(b-x)**2)
        low2,high2,_=cache[w]
        inside|=maximum<=low2
        outside&=minimum>high2
    return 1 if inside else 0 if outside else 2


def size(box):
    result=g.mpq(1)
    for a,b in box:result*=b-a
    return result


def enclose(points,weights,volume,work):
    work.charge('sample_weight_validation',len(weights))
    assert points and len(points)==len(weights) and all(w>0 for w in weights) and sum(weights)==volume
    cache=radii(weights,work)
    work.charge('coordinate_extrema_primitive_contributions',len(points))
    radius=max(v[2] for v in cache.values())
    root=tuple((min(p[j] for p in points)-radius,max(p[j] for p in points)+radius) for j in range(3))
    work.charge('root_cover_region');queue=deque([root]);inside=g.mpq(0);unresolved=size(root)
    proof=bytearray()
    try:
        while unresolved>volume/5000 and queue:
            box=queue.popleft();code=classification(box,points,weights,cache,work)
            if code<2:
                amount=size(box);unresolved-=amount
                if code:inside+=amount
                proof.append(code)
            else:
                work.charge('child_cover_regions',2)
                widths=[b-a for a,b in box];j=widths.index(max(widths));mid=sum(box[j])/2
                left=list(box);right=list(box);left[j]=(box[j][0],mid);right[j]=(mid,box[j][1])
                queue.extend((tuple(left),tuple(right)));proof.append(2)
        status='VOLUME_ENCLOSURE_COMPLETE'
    except WorkLimit:status='VOLUME_RESOURCE_INCONCLUSIVE'
    return dict(status=status,occupied_volume=[str(inside),str(inside+unresolved)],
        root_box=[[str(a),str(b)] for a,b in root],radius_upper=str(radius),
        unique_radius_count=len(cache),work=work.used,pending=work.pending,
        completed_box_decisions=len(proof),proof_decisions=bytes(proof),complete_row=False)
