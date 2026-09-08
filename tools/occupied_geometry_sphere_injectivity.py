"""Exact sufficient global no-overlap certificate for the mapped sphere mesh.

On each reference tetrahedron compute the affine Jacobian A exactly. Positive
definiteness of A+A^T implies strict monotonicity along every straight segment
in the convex reference octahedron. Continuity across conforming faces then
gives global injectivity, not just positive cell orientation. A failed Sylvester
test is only a failure of this sufficient certificate, not an invalid-mesh claim.
"""
import argparse
from array import array
import json
from pathlib import Path
import resource
import time

from occupied_geometry_input_check import Reader,determinant


def adjugate(a):
    return tuple(tuple((-1)**(i+j)*(a[(j+1)%3][(i+1)%3]*a[(j+2)%3][(i+2)%3]
                                  -a[(j+1)%3][(i+2)%3]*a[(j+2)%3][(i+1)%3])
                       *(-1)**(i+j) for j in range(3)) for i in range(3))


def check(root,depth):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));start=time.monotonic()
    n=1<<depth;grid=1<<256;reference=[]
    for x in range(-n,n+1):
        for y in range(-n+abs(x),n-abs(x)+1):
            zmax=n-abs(x)-abs(y)
            for z in range(-zmax,zmax+1):reference.append((x,y,z))
    r=Reader(root/'candidate/vertices.bin',1);assert r.count==len(reference);actual=[]
    for i in range(r.count):
        assert r.u(8)==i+1
        p=tuple(r.q()*grid for _ in range(3));assert all(x.denominator==1 for x in p)
        actual.append(tuple(int(x) for x in p))
    r.end();r=Reader(root/'candidate/tetrahedra.bin',2);failed=[];smallest=None
    for i in range(r.count):
        assert r.u(8)==i+1
        ids=[r.u(8)-1 for _ in range(4)]
        e=tuple(tuple(reference[ids[j]][a]-reference[ids[0]][a] for a in range(3)) for j in (1,2,3))
        f=tuple(tuple(actual[ids[j]][a]-actual[ids[0]][a] for a in range(3)) for j in (1,2,3))
        d=determinant(*e);assert d==1
        inv=adjugate(e)
        assert all(sum(inv[a][k]*e[k][b] for k in range(3))==(a==b) for a in range(3) for b in range(3))
        a=tuple(tuple(sum(inv[j][k]*f[k][l] for k in range(3)) for l in range(3)) for j in range(3))
        s=tuple(tuple(a[j][k]+a[k][j] for k in range(3)) for j in range(3))
        minors=(s[0][0],s[0][0]*s[1][1]-s[0][1]**2,determinant(*s))
        if any(x<=0 for x in minors):failed.append(dict(cell=i+1,minors=[str(x) for x in minors]))
        smallest=minors if smallest is None else tuple(min(x,y) for x,y in zip(smallest,minors))
        if i%4096==0:assert time.monotonic()-start<=1800,'input verification wall-time ceiling'
    count=r.count;r.end()
    return dict(status='PASS' if not failed else 'SUFFICIENT_CERTIFICATE_INCONCLUSIVE',
        depth=depth,cells_checked=count,failed_sylvester_cells=failed,
        minimum_scaled_sylvester_minors=[str(x) for x in smallest],
        certificate='strict_monotonicity_of_continuous_piecewise_affine_map_on_convex_reference_domain',
        candidate_evaluations=0,complete_input_seal=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--depth',type=int,required=True)
    a=p.parse_args();print(json.dumps(check(a.root,a.depth),sort_keys=True))
