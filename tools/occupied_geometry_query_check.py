"""Independent semantic query inventory and exact transform checks."""
import argparse
from fractions import Fraction as Q
import io
import itertools
import json
from math import gcd
from pathlib import Path
import resource
import time
import gmpy2 as g
from occupied_geometry_input_check import Reader,determinant


def point(r):return tuple(r.q() for _ in range(3))
def dot(a,b):return sum(x*y for x,y in zip(a,b))


def registered_transform(ordinal):
    """Reconstruct the fixed inventory without importing its writer."""
    identity = tuple(tuple(Q(i == j) for j in range(3)) for i in range(3))
    rotations = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((-1, 1), repeat=3):
            m = tuple(tuple(Q(signs[i] if j == perm[i] else 0)
                            for j in range(3)) for i in range(3))
            if determinant(*m) == 1 and m != identity:
                rotations.append(m)
    rotations.insert(0, identity)
    zero = (Q(0),) * 3
    matrix, translation, boost, scale, order = identity, zero, zero, Q(1), 0
    if ordinal < 24:
        matrix = rotations[ordinal]
    elif ordinal == 24:
        translation = tuple(map(Q, (3, -2, 5)))
    elif ordinal in (25, 26):
        rz = ((Q(3,5),Q(-4,5),Q(0)),(Q(4,5),Q(3,5),Q(0)),(Q(0),Q(0),Q(1)))
        rx = ((Q(1),Q(0),Q(0)),(Q(0),Q(3,5),Q(-4,5)),(Q(0),Q(4,5),Q(3,5)))
        matrix = rz if ordinal == 25 else tuple(tuple(
            sum(rx[i][k] * rz[k][j] for k in range(3)) for j in range(3)) for i in range(3))
    elif ordinal in (27, 28):
        scale = Q(1,2) if ordinal == 27 else Q(2)
    elif ordinal == 29:
        boost = (Q(1,4), Q(-1,2), Q(1,8))
    elif ordinal in (30, 31, 32):
        order = ordinal - 29
    else:
        raise ValueError('unregistered transform')
    return matrix, translation, boost, scale, order


def registered_regions(fixture, time):
    if fixture in (4, 5):
        return (((Q(-1),Q(0),Q(0),Q(0),Q(0)),),
                ((Q(1),Q(0),Q(0),Q(0),Q(0)),))
    assert fixture == 7
    def box(bounds):
        result = []
        for axis, (low, high) in enumerate(bounds):
            for sign, d in ((-1, -low), (1, high)):
                n = [Q(0)] * 3
                n[axis] = Q(sign)
                result.append((*n, d, -d/4 if axis == 0 else Q(0)))
        return tuple(sorted(result))
    return tuple(box(((left,right),(Q(0),Q(3,4)),(Q(-1,8),Q(1,8))))
                 for left,right in ((Q(-1),Q(0)),(Q(0),Q(1))))


def region(r):
    planes=[tuple(r.q() for _ in range(5)) for _ in range(r.u(8))]
    assert planes==sorted(planes) and all(any(p[:3]) for p in planes)
    return tuple(planes)


def parse(op,data):
    r=Reader.__new__(Reader);r.f=io.BytesIO(data)
    if op in (1,2):value=(r.q(),)
    elif op in (3,4,7):value=(point(r),r.q())
    elif op==5:value=(region(r),region(r),r.q())
    elif op==6:
        mode=r.u(1);assert mode in (0,1)
        a,b=r.q(),r.q();assert 0<=a<=b<=2
        value=(mode,a,b,region(r),region(r)) if not mode else (mode,a,b,tuple(r.q() for _ in range(5)))
    elif op==8:
        identifier=r.u(8);size=r.u(8);raw=r.read(size)
        rr=Reader.__new__(Reader);rr.f=io.BytesIO(raw)
        t=rr.q();rr.end();assert identifier==1 and t==4
        value=(identifier,t)
    else:raise AssertionError('unknown query operation')
    r.end();return value


def round_integer(q):
    q=Q(int(q.numerator),int(q.denominator));n=q.numerator//q.denominator;s=q-n
    return n+(s>Q(1,2) or (s==Q(1,2) and n%2))


def exact_query_point(v,radius,c):
    norm=sum(x*x for x in v);grid=1<<256;result=[]
    with g.context(precision=512,round=g.RoundDown):lo=g.sqrt(g.mpfr(norm))
    with g.context(precision=512,round=g.RoundUp):hi=g.sqrt(g.mpfr(norm))
    for x,shift in zip(v,c):
        a=g.mpq(abs(x)*radius.numerator*grid,radius.denominator)
        with g.context(precision=512,round=g.RoundDown):lower=g.mpfr(a)/hi
        with g.context(precision=512,round=g.RoundUp):upper=g.mpfr(a)/lo
        n=round_integer(g.mpq(lower));assert n==round_integer(g.mpq(upper))
        result.append(shift+Q(n if x>=0 else -n,grid))
    return tuple(result)


def sphere_expected(fixture,t):
    directions=set()
    for v in itertools.product(range(-4,5),repeat=3):
        if max(abs(x) for x in v)!=4:continue
        h=gcd(gcd(abs(v[0]),abs(v[1])),abs(v[2]))
        directions.add(tuple(x//h for x in v))
    assert len(directions)==386
    zero=(Q(0),)*3
    centres=[zero] if fixture==3 else ([(Q(0),Q(0),2-t)] if fixture==6 else
        [(Q(-3,2)+(t/2 if fixture==5 else 0),Q(0),Q(0)),
         (Q(3,2)-(t/2 if fixture==5 else 0),Q(0),Q(0))])
    normal=set(centres);other=set(centres)
    for c in centres:
        for v in directions:
            for radius in (Q(63,64),Q(1),Q(65,64)):
                p=exact_query_point(v,radius,c);other.add(p)
                if radius==1:normal.add(p)
    if fixture in (4,5):normal.add(zero);other.add(zero)
    return {3:other,4:normal,7:other}


def rectangles(fixture):
    if fixture in (1,2):
        extent=[(Q(-1),Q(1))]*3 if fixture==1 else [(Q(-2),Q(2)),(Q(-2),Q(2)),(Q(-1,4),Q(1,4))]
        return [(a,extent[a][s==1],*[extent[j] for j in range(3) if j!=a],s)
                for a in range(3) for s in (-1,1)]
    z=(Q(-1,4),Q(1,4));bottom=(Q(-1),Q(-3,4));arm=(Q(-3,4),Q(1))
    result=[(0,Q(-1),bottom,z,-1),(0,Q(1),bottom,z,1),
            (1,Q(-1),(Q(-1),Q(1)),z,-1),
            (1,Q(-3,4),(Q(-3,4),Q(3,4)),z,1)]
    for sign in (-1,1):result.append((2,Q(sign,4),(Q(-1),Q(1)),bottom,sign))
    for left,right in ((Q(-1),Q(-3,4)),(Q(3,4),Q(1))):
        result.extend([(0,left,arm,z,-1),(0,right,arm,z,1),(1,Q(1),(left,right),z,1)])
        for sign in (-1,1):result.append((2,Q(sign,4),(left,right),arm,sign))
    assert len(result)==16;return result


def planar_expected(fixture,t):
    rects=rectangles(fixture);net=set()
    for axis,fixed,u,v,sign in rects:
        rest=[j for j in range(3) if j!=axis]
        for i,j in itertools.product(range(9),repeat=2):
            p=[Q(0)]*3;p[axis]=fixed;p[rest[0]]=u[0]+Q(i,8)*(u[1]-u[0]);p[rest[1]]=v[0]+Q(j,8)*(v[1]-v[0]);net.add(tuple(p))
    def move(p):return (p[0]*(1-t/4),p[1],p[2]) if fixture==7 else p
    normal={move(p) for p in net};other=set(normal)
    for p in net:
        normals=set()
        for axis,fixed,u,v,sign in rects:
            a,b=[j for j in range(3) if j!=axis]
            if p[axis]==fixed and u[0]<=p[a]<=u[1] and v[0]<=p[b]<=v[1]:normals.add((axis,sign))
        if len(normals)==1:
            axis,sign=next(iter(normals))
            for d in (Q(-1,64),Q(1,64)):
                q=list(move(p));q[axis]+=sign*d;other.add(tuple(q))
    if fixture in (1,2):normal.add((Q(0),)*3);other.add((Q(0),)*3)
    return {3:other,4:normal,7:other}


def check(directory,fixture):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));started=time.monotonic()
    times=[Q(j,8) for j in range(17)] if fixture in (5,6,7) else [Q(0)]
    expected={t:(planar_expected(fixture,t) if fixture in (1,2,7) else sphere_expected(fixture,t)) for t in times}
    baseline=None;rows=[]
    for ordinal in range(33):
        tr=Reader(directory/'candidate'/f'transform-{ordinal:02}.bin',9)
        assert tr.count==1 and tr.u(8)==ordinal+1
        matrix=tuple(point(tr) for _ in range(3));translation=point(tr);boost=point(tr);scale=tr.q();order=tr.u(1);tr.end()
        assert (matrix,translation,boost,scale,order)==registered_transform(ordinal),('registered transform',ordinal)
        assert determinant(*matrix)==1 and scale in (Q(1,2),Q(1),Q(2)) and order in range(4)
        assert all(dot(matrix[i],matrix[j])==(i==j) for i in range(3) for j in range(3))
        def inverse(p,t):
            q=tuple((p[j]-translation[j]-t*boost[j])/scale for j in range(3))
            return tuple(sum(matrix[j][i]*q[j] for j in range(3)) for i in range(3))
        def plane(p):
            n=p[:3];back=tuple(sum(matrix[j][i]*n[j] for j in range(3)) for i in range(3))
            return (*back,(p[3]-dot(n,translation))/scale,(p[4]-dot(n,boost))/scale)
        def regions(r):return tuple(sorted(plane(p) for p in r))
        found={t:{op:set() for op in (3,4,7)} for t in times};all_semantic=set();prior=None
        r=Reader(directory/'candidate'/f'queries-{ordinal:02}.bin',8)
        for i in range(r.count):
            assert r.u(8)==i+1
            op=r.u(1);data=r.read(r.u(8));key=(op,data)
            assert prior is None or prior<key;prior=key;value=parse(op,data)
            if op in (3,4,7):
                p,t=value;assert t in expected;p=inverse(p,t);found[t][op].add(p);value=(p,t)
            elif op==5:value=(regions(value[0]),regions(value[1]),value[2])
            elif op==6:
                mode,a,b,*rest=value
                value=(mode,a,b,*([regions(x) for x in rest] if not mode else [plane(rest[0])]))
            if op!=8:all_semantic.add((op,value))
            else:assert fixture==7 and ordinal==0
        count=r.count;r.end();assert found==expected,('finite point inventory',fixture,ordinal)
        assert {v[0] for op,v in all_semantic if op==1}==set(times)
        assert {v[0] for op,v in all_semantic if op==2}==set(times)
        expected_separations = {(5, (*registered_regions(fixture,t),t)) for t in times} if fixture in (4,5,7) else set()
        assert {(op,v) for op,v in all_semantic if op==5}==expected_separations,('registered closed selectors',fixture,ordinal)
        if fixture in (5,6,7):
            assert {(v[1],v[2]) for op,v in all_semantic if op==6}=={(Q(0),Q(2))}|{(Q(j,8),Q(j+1,8)) for j in range(16)}
        if baseline is None:baseline=all_semantic
        else:assert all_semantic==baseline,('exact transform query covariance',fixture,ordinal)
        joins=[json.loads(x) for x in (directory/'oracle'/f'queries-{ordinal:02}.jsonl').read_text().splitlines()]
        assert [j['query'] for j in joins]==list(range(1,count+1)) and all(j['obligations'] for j in joins)
        rows.append(count)
        print('query variant checked',fixture,ordinal,count,flush=True)
        assert time.monotonic()-started<1800,'input query verification wall-time ceiling'
    print(json.dumps(dict(status='PASS',fixture=fixture,variant_counts=rows,
        independently_reconstructed_finite_point_nets=True,
        candidate_evaluations=0,complete_input_seal=False),sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path)
    p.add_argument('--fixture',type=int,choices=range(1,8),required=True)
    a=p.parse_args();check(a.directory,a.fixture)
