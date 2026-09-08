"""Exact binomial-polynomial replay of pre-data sphere-weight witnesses.

This executable does not import the materializer. It evaluates the frozen
Taylor polynomial by direct binomial expansion, not the materializer recurrence.
Both implement the same registered interval-Taylor enclosure construction.

The degree-12 Taylor polynomial is integrated by an exact rational simplex rule
whose monomial identities are checked independently before use. Only the radial
factor and the Taylor remainder need directed 512-bit arithmetic.
"""
import argparse
from functools import lru_cache
import heapq
import itertools
import json
from math import comb, factorial, gcd
from pathlib import Path
import sys
import time

sys.dont_write_bytecode=True
import gmpy2 as g

Q=g.mpq
DOWN=g.context(precision=512,round=g.RoundDown)
UP=g.context(precision=512,round=g.RoundUp)


def compositions(n,k):
    if k==1:
        yield (n,);return
    for j in range(n+1):
        for t in compositions(n-j,k-1):yield (j,)+t


def rule():
    # Exact degree-13 tetrahedron cubature, normalized to unit total weight.
    out=[];s=6
    for i in range(s+1):
        den=4+2*(s-i)
        w=Q(6*(-1)**i*den**(2*s+1),2**(2*s)*factorial(i)*factorial(4+2*s-i))
        for b in compositions(s-i,4):
            out.append((tuple(Q(2*x+1,den) for x in b),w))
    return out


RULE=rule()
BETA=[Q(1)]
for i in range(1,13):BETA.append(-BETA[-1]*Q(2*i+1,2*i))


def rule_check():
    checks=0
    for total in range(14):
        for abc in compositions(total,3):
            actual=sum(w*p[1]**abc[0]*p[2]**abc[1]*p[3]**abc[2] for p,w in RULE)
            exact=Q(6*factorial(abc[0])*factorial(abc[1])*factorial(abc[2]),factorial(3+total))
            assert actual==exact,(abc,actual,exact)
            checks+=1
    return checks


def atan_interval(n):
    s=Q(0);j=0
    while True:
        s+=Q((-1)**j,(2*j+1)*n**(2*j+1));j+=1
        t=Q((-1)**j,(2*j+1)*n**(2*j+1))
        if abs(t)<=Q(1,1<<608):return min(s,s+t),max(s,s+t)


def pi_interval():
    a,b=atan_interval(5);c,d=atan_interval(239)
    lo,hi=16*a-4*d,16*b-4*c
    assert hi-lo<=Q(1,1<<600)
    with DOWN:l=g.mpfr(lo)
    with UP:u=g.mpfr(hi)
    return Q(l),Q(u)


PI=pi_interval()
with UP: JMAX=Q(3*g.sqrt(g.mpfr(3)))
WABS=sum(abs(w) for _,w in RULE)


def children(t):
    v=[tuple(2*x for x in p) for p in t]
    a,b,c,d,e,f=[tuple(t[i][k]+t[j][k] for k in range(3))
                 for i,j in ((0,1),(0,2),(0,3),(1,2),(1,3),(2,3))]
    return ((v[0],a,b,c),(a,v[1],d,e),(b,d,v[2],f),(c,e,f,v[3]),
            (a,b,c,e),(a,b,d,e),(b,c,e,f),(b,d,e,f))


def canonical(t):
    h=0
    for p in t:
        for x in p:h=gcd(h,abs(x))
    return min(tuple(tuple(abs(p[j])//h for j in axes) for p in t)
               for axes in itertools.permutations(range(3)))


def origin_octant(t):
    nz=[p for p in t if any(p)]
    if len(nz)!=3:return False
    return len({sum(p) for p in nz})==1 and all(sum(x!=0 for x in p)==1 for p in nz) and len({next(j for j,x in enumerate(p) if x) for p in nz})==3


def polynomial_at(c,u):
    a=sum(x*x for x in c); b=2*sum(x*y for x,y in zip(c,u))/a
    v=sum(x*x for x in u)/a;s0=sum(c);s1=sum(u)
    ns=(s0**3,3*s0*s0*s1,3*s0*s1*s1,s1**3)
    bp=[Q(1)];vp=[Q(1)]
    for _ in range(12):bp.append(bp[-1]*b);vp.append(vp[-1]*v)
    # Exact rational regrouping of the direct binomial polynomial. This is
    # still independent of the materializer's coefficient recurrence; summing
    # the four numerator terms once avoids redundant large-rational products.
    numerator_prefix=[sum(ns[:k+1]) for k in range(4)]
    return sum(BETA[m]*comb(m,j)*bp[m-j]*vp[j]*numerator_prefix[min(3,12-m-j)]
               for m in range(13) for j in range(min(m,12-m)+1))


@lru_cache(maxsize=32768)
def local_bound(t):
    if origin_octant(t):return PI
    c=tuple(Q(sum(p[j] for p in t),4) for j in range(3))
    us=[tuple(Q(p[j])-c[j] for j in range(3)) for p in t]
    a=sum(x*x for x in c)
    B=2*max(abs(sum(x*y for x,y in zip(c,u))) for u in us)/a
    C=max(sum(x*x for x in u) for u in us)/a
    if B+C>=1:return Q(1),JMAX
    s0=sum(c);s1=max(abs(sum(u)) for u in us)
    ns=(s0**3,3*s0*s0*s1,3*s0*s1*s1,s1**3)
    partial=sum(abs(BETA[m])*comb(m,j)*B**(m-j)*C**j*ns[l]
                for m in range(13) for j in range(m+1)
                for l in range(min(3,12-m-j)+1))
    # Positive coefficient majorant bounds the multivariate Taylor tail.
    with DOWN:
        amin=g.mpfr(a);rootlo=g.sqrt(amin);factorlo=amin*rootlo
        zmin=g.mpfr(1-B-C);zrootlo=g.sqrt(zmin);denlo=zmin*zrootlo
    with UP:
        amax=g.mpfr(a);rootup=g.sqrt(amax);factorup=amax*rootup
        total=g.mpfr((s0+s1)**3)/denlo
        rem=max(Q(0),Q(total)-partial)/Q(factorlo)
    if rem>Q(1,16):return Q(1),JMAX
    pol=Q(0)
    for lam,w in RULE:
        u=tuple(sum(lam[i]*t[i][j] for i in range(4))-c[j] for j in range(3))
        pol+=w*polynomial_at(c,u)
    vals=(pol/Q(factorlo),pol/Q(factorup))
    return max(Q(1),min(vals)-rem),min(JMAX,max(vals)+rem)


def integrate(t,width,deadline):
    t=canonical(t);lo,hi=local_bound(t)
    queue=[(-(hi-lo),(),t,Q(1),lo,hi)];count=1
    while hi-lo>width:
        if time.monotonic()>deadline:raise TimeoutError('frozen input-preparation wall-time ceiling')
        _,path,cell,w,l,u=heapq.heappop(queue);lo-=w*l;hi-=w*u
        for j,ch in enumerate(children(cell)):
            ch=canonical(ch);cl,cu=local_bound(ch);cw=w/8
            lo+=cw*cl;hi+=cw*cu
            heapq.heappush(queue,(-cw*(cu-cl),path+(j,),ch,cw,cl,cu));count+=1
    return lo,hi,count



def decode(pair):return Q(int(pair[0]),int(pair[1]))


def rounded_up(q):
    with UP:return Q(g.mpfr(q))


def rounded_down(q):
    with DOWN:return Q(g.mpfr(q))


def nearest_integer(q):
    n=q.numerator//q.denominator;r=q-n
    return int(n+(r>Q(1,2) or (r==Q(1,2) and n%2)))


def replay(directory):
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    started=time.monotonic();deadline=started+1800
    metadata=json.loads((directory/'receipt.json').read_text())
    w0=nearest_integer(PI[0]*Q(4,3)*(1<<256))
    assert w0==nearest_integer(PI[1]*Q(4,3)*(1<<256))
    total=Q(w0,1<<256);assert total==decode(metadata['total'])
    initial_error=rounded_up(max(abs(total/8-PI[0]/6),abs(total/8-PI[1]/6)))
    root=((0,0,0),(1,0,0),(0,1,0),(0,0,1))
    expected={(): (root,total/8,initial_error)};cache={};seen=set();checks=0
    monomials=rule_check()
    with (directory/'allocation-witnesses.jsonl').open() as f:
        for line in f:
            row=json.loads(line);path=tuple(row['path'])
            assert path not in seen and path in expected;seen.add(path)
            cell,weight,error=expected[path]
            assert decode(row['parent'])==weight and decode(row['parent_error'])==error
            kids=children(cell);intervals=[]
            for child in kids:
                key=canonical(child)
                if key not in cache:
                    lo,hi,_=integrate(key,Q(1,1<<30),deadline)
                    cache[key]=(rounded_down(lo),rounded_up(hi))
                intervals.append(cache[key])
            reported=[tuple(decode(x) for x in pair) for pair in row['mean_integrals']]
            assert intervals==reported,('integral replay',path)
            mids=[(lo+hi)/2 for lo,hi in intervals];normalizer=sum(mids)
            scaled=[m/normalizer*(1<<128) for m in mids]
            units=[int(x.numerator//x.denominator) for x in scaled]
            order=sorted(range(8),key=lambda i:(-(scaled[i]-units[i]),i))
            for i in order[:(1<<128)-sum(units)]:units[i]+=1
            actual=[decode(x) for x in row['child_weights']]
            assert actual==[weight*Q(n,1<<128) for n in units]
            assert sum(actual)==weight and all(x>0 for x in actual)
            for i,(child,(lo,hi)) in enumerate(zip(kids,intervals)):
                rlo=lo/(lo+sum(u for j,(_,u) in enumerate(intervals) if j!=i))
                rhi=hi/(hi+sum(l for j,(l,_) in enumerate(intervals) if j!=i))
                lower_delta=actual[i]-weight*rlo;upper_delta=actual[i]-weight*rhi
                bound=rounded_up(max(abs(lower_delta),abs(upper_delta))+error*rhi)
                assert decode(row['child_error_bounds'][i])==bound
                expected[path+(i,)]=(child,actual[i],bound);checks+=1
            if len(seen)%128==0:print('weight replay parent nodes',len(seen),flush=True)
            assert time.monotonic()<=deadline,'input replay wall-time ceiling'
    depth=metadata['depth']
    assert seen=={p for p in expected if len(p)<depth}
    for level in range(1,depth+1):
        values=[(v,e) for p,(_,v,e) in expected.items() if len(p)==level]
        assert len(values)==8**level
        assert 8*sum(v for v,_ in values)==total
        assert 8*sum(e for _,e in values)<=total/(1<<24)
    with (directory/'leaf-weights.jsonl').open() as f:
        leaves=set()
        for line in f:
            row=json.loads(line);path=tuple(row['path'])
            assert len(path)==depth and path not in leaves;leaves.add(path)
            cell,value,error=expected[path]
            assert row['reference_vertices']==[list(v) for v in cell]
            assert decode(row['volume'])==value and decode(row['error_upper'])==error
        assert len(leaves)==8**depth
    print(json.dumps(dict(status='PASS',exact_monomial_checks=monomials,
        child_allocations_checked=checks,independent_binomial_integrals=len(cache),
        candidate_evaluations=0,complete_input_seal=False),sort_keys=True),flush=True)
    print('seconds',time.monotonic()-started,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path)
    a=p.parse_args();replay(a.directory)
