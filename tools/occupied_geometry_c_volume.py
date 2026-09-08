"""Candidate-only outward Gaussian occupied-volume covering kernel.

Fixed 256-bit scratch, complete all-sample sums, deterministic breadth-first
longest-side subdivision. Proof decisions are compact bytes, not sampled
volume estimates. No fixture labels or oracle are read here.
"""
from collections import deque
import gmpy2 as g
from occupied_geometry_runtime_wire import WorkLimit


def parameters(volume,delta_squared):
    values=[]
    for rounding in (g.RoundDown,g.RoundUp):
        with g.context(precision=256,round=rounding):
            pi=g.const_pi();delta=g.sqrt(g.mpfr(delta_squared))
            length=g.rootn(g.mpfr(volume),3);h2=delta*length
            normalizer=(2*pi)*g.sqrt(2*pi)*h2*g.sqrt(h2)
            values.append((h2,normalizer))
    assert 0<values[0][0]<=values[1][0] and 0<values[0][1]<=values[1][1]
    return values[0],values[1]


def field_classification(box,points,weights,params,work):
    (h2lo,nlo),(h2hi,nhi)=params
    low=g.mpfr(0);high=g.mpfr(0)
    work.charge('interval_field_primitive_contributions',len(points))
    for point,weight in zip(points,weights):
        minimum=g.mpq(0);maximum=g.mpq(0)
        for (a,b),p in zip(box,point):
            near=a-p if p<a else p-b if p>b else g.mpq(0)
            far=max(abs(a-p),abs(b-p))
            minimum+=near*near;maximum+=far*far
        # Exact distances are converted in the direction appropriate for the
        # NEGATIVE exponent; denominator endpoints must have matching polarity.
        with g.context(precision=256,round=g.RoundUp):
            max_distance=g.mpfr(maximum)
        with g.context(precision=256,round=g.RoundDown):
            exponent=-max_distance/(2*h2lo)
            term=g.mpfr(weight)/nhi*g.exp(exponent)
            low=low+term
        with g.context(precision=256,round=g.RoundDown):
            min_distance=g.mpfr(minimum)
        with g.context(precision=256,round=g.RoundUp):
            exponent=-min_distance/(2*h2hi)
            term=g.mpfr(weight)/nlo*g.exp(exponent)
            high=high+term
    return 1 if low>=g.mpfr('0.5') else 0 if high<g.mpfr('0.5') else 2


def box_volume(box):
    result=g.mpq(1)
    for a,b in box:result*=b-a
    return result


def enclose(points,weights,volume,delta_squared,work):
    work.charge('sample_weight_validation',len(weights))
    assert points and len(points)==len(weights) and sum(weights)==volume
    assert all(w>0 for w in weights)
    params=parameters(volume,delta_squared);(_,nlo),(h2hi,_)=params
    with g.context(precision=256,round=g.RoundUp):amplitude=g.mpfr(volume)/nlo
    radius=1
    while True:
        work.charge('exterior_radius_bound_update')
        with g.context(precision=256,round=g.RoundUp):
            tail=amplitude*g.exp(-g.mpfr(radius*radius)/(2*h2hi))
        if tail<g.mpfr('0.5'):break
        radius+=1
    work.charge('coordinate_extrema_primitive_contributions',len(points))
    box=tuple((min(p[i] for p in points)-radius,max(p[i] for p in points)+radius) for i in range(3))
    work.charge('root_cover_region')
    queue=deque([box]);unresolved=box_volume(box);inside=g.mpq(0);decisions=bytearray()
    # The allowed width is 1/100 of the frozen 0.02 normalized volume budget.
    tolerance=volume/5000
    try:
        while unresolved>tolerance and queue:
            current=queue.popleft();size=box_volume(current)
            classification=field_classification(current,points,weights,params,work)
            if classification<2:
                decisions.append(classification);unresolved-=size
                if classification==1:inside+=size
            else:
                work.charge('child_cover_regions',2)
                widths=[b-a for a,b in current];axis=widths.index(max(widths))
                mid=sum(current[axis])/2
                left=list(current);right=list(current)
                left[axis]=(current[axis][0],mid);right[axis]=(mid,current[axis][1])
                queue.extend((tuple(left),tuple(right)));decisions.append(2)
        status='VOLUME_ENCLOSURE_COMPLETE'
    except WorkLimit:
        # Unresolved volume still includes the popped cell if its evaluation
        # or child reservation failed; the proof stops before that decision.
        status='VOLUME_RESOURCE_INCONCLUSIVE'
    return dict(status=status,occupied_volume=[str(inside),str(inside+unresolved)],
        root_box=[[str(a),str(b)] for a,b in box],exterior_radius=radius,
        work=work.used,pending=work.pending,
        completed_box_decisions=len(decisions),proof_decisions=bytes(decisions),
        complete_row=False)
