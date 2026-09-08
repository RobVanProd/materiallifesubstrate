"""Pre-data hierarchical sphere weights; never imports a candidate evaluator.

One octant is materialized; reflection gives the other seven with unchanged
ancestry/weights. All allocation witnesses remain oracle-only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

sys.dont_write_bytecode=True
import occupied_geometry_weights as w

Q=w.Q


def ceil512(q):
    with w.UP:return Q(w.g.mpfr(q))


def floor512(q):
    with w.DOWN:return Q(w.g.mpfr(q))


def encode(q):
    return [str(q.numerator),str(q.denominator)]


def nearest(q):
    n=q.numerator//q.denominator
    rest=q-n
    return int(n+(rest>Q(1,2) or (rest==Q(1,2) and n%2)))


def sphere_total():
    a=nearest(w.PI[0]*Q(4,3)*(1<<256))
    b=nearest(w.PI[1]*Q(4,3)*(1<<256))
    assert a==b,'sphere-total rounding unresolved'
    return Q(a,1<<256)


def allocate(parent,intervals):
    mid=[(lo+hi)/2 for lo,hi in intervals];s=sum(mid)
    raw=[m/s*(1<<128) for m in mid]
    units=[int(x.numerator//x.denominator) for x in raw]
    remaining=(1<<128)-sum(units)
    assert 0<=remaining<8
    order=sorted(range(8),key=lambda i:(-(raw[i]-units[i]),i))
    for i in order[:remaining]:units[i]+=1
    child=[parent*Q(u,1<<128) for u in units]
    assert all(x>0 for x in child) and sum(child)==parent
    return child


def run(out,depth):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    started=time.monotonic();deadline=started+1800
    out.mkdir(parents=True,exist_ok=False)
    checks=w.rule_check();total=sphere_total()
    root=((0,0,0),(1,0,0),(0,1,0),(0,0,1))
    error=ceil512(max(abs(total/8-w.PI[0]/6),abs(total/8-w.PI[1]/6)))
    level=[((),root,total/8,error)]
    integral_cache={};stats=[];regions=0
    with (out/'allocation-witnesses.jsonl').open('x') as f:
        for d in range(1,depth+1):
            following=[];error_sum=Q(0)
            for path,cell,parent,parent_error in level:
                intervals=[];kids=w.children(cell)
                for child in kids:
                    key=w.canonical(child)
                    if key not in integral_cache:
                        lo,hi,n=w.integrate(key,Q(1,1<<30),deadline)
                        assert 1<=lo<=hi<=w.JMAX
                        integral_cache[key]=(floor512(lo),ceil512(hi))
                        regions+=n
                    intervals.append(integral_cache[key])
                weights=allocate(parent,intervals)
                errors=[]
                for i,child in enumerate(kids):
                    lo,hi=intervals[i]
                    # Correlated normalization: the same integral appears in
                    # numerator and denominator, so do not divide unrelated
                    # global lower/upper sums.
                    rlo=lo/(lo+sum(u for j,(_,u) in enumerate(intervals) if j!=i))
                    rhi=hi/(hi+sum(l for j,(l,_) in enumerate(intervals) if j!=i))
                    err=ceil512(max(abs(weights[i]-parent*rlo),
                                   abs(weights[i]-parent*rhi))+parent_error*rhi)
                    errors.append(err);error_sum+=err
                    following.append((path+(i,),child,weights[i],err))
                f.write(json.dumps(dict(path=list(path),parent=encode(parent),
                    parent_error=encode(parent_error),
                    mean_integrals=[[encode(l),encode(u)] for l,u in intervals],
                    child_weights=[encode(x) for x in weights],
                    child_error_bounds=[encode(x) for x in errors]),
                    sort_keys=True,separators=(',',':'))+'\n')
                if time.monotonic()>deadline:raise TimeoutError('input wall-time ceiling')
            assert sum(x[2] for x in following)==total/8
            assert 8*error_sum<=total/(1<<24),'registered physical-weight-error bound'
            row=dict(depth=d,leaf_count_per_octant=len(following),
                absolute_weight_error_upper=encode(ceil512(8*error_sum)),
                registered_upper=encode(total/(1<<24)),
                independently_integrated_regions=regions,
                distinct_integrals=len(integral_cache))
            stats.append(row);level=following
            print(json.dumps(row,sort_keys=True),flush=True)
    with (out/'leaf-weights.jsonl').open('x') as f:
        for path,cell,value,error in level:
            f.write(json.dumps(dict(path=list(path),reference_vertices=cell,
                volume=encode(value),error_upper=encode(error)),
                sort_keys=True,separators=(',',':'))+'\n')
    files={}
    for p in sorted(out.glob('*.jsonl')):
        with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
        files[p.name]=dict(size=p.stat().st_size,sha256=h)
    (out/'receipt.json').write_text(json.dumps(dict(
        schema='mls.occupied-geometry.weight-input.v1',depth=depth,
        exact_monomial_checks=checks,total=encode(total),levels=stats,files=files,
        candidate_evaluations=0,complete_input_seal=False),sort_keys=True)+'\n')
    print('PASS input weights; seconds',time.monotonic()-started,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path)
    p.add_argument('--depth',type=int,choices=range(1,6),default=5)
    a=p.parse_args();run(a.output,a.depth)
