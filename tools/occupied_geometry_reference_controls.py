"""Exact pre-data analytical controls, physically separated from candidate input."""
import argparse
from fractions import Fraction as Q
import hashlib
import json
from math import isqrt
from pathlib import Path


def quadratic(a,b,c):
    a,b,c=map(Q,(a,b,c));times=[Q(0),Q(2)]
    if a>0 and 0<=-b/(2*a)<=2:times.append(-b/(2*a))
    value=lambda t:a*t*t+b*t+c
    minimum=min((value(t),t) for t in times)
    first=None
    if c<=0:first=Q(0)
    elif minimum[0]<=0:
        if not a:first=-c/b
        else:
            discriminant=b*b-4*a*c
            sn=isqrt(discriminant.numerator);sd=isqrt(discriminant.denominator)
            assert Q(sn*sn,sd*sd)==discriminant
            roots=[(-b-Q(sn,sd))/(2*a),(-b+Q(sn,sd))/(2*a)]
            first=min(t for t in roots if 0<=t<=2)
        assert value(first)==0
    assert (first is not None)==(minimum[0]<=0)
    return dict(coefficients=[str(x) for x in (a,b,c)],
                minimum_value=str(minimum[0]),minimizing_time=str(minimum[1]),
                first_nonpositive_time=None if first is None else str(first))


def build(out):
    out.mkdir(parents=True,exist_ok=False);oracle=out/'oracle';oracle.mkdir()
    triples=((0,0,1),(0,0,0),(0,0,-1),(1,-2,1),(1,0,1),
             (1,-6,8),(1,2,0),(1,-3,2),(1,1,-2))
    rows=[quadratic(*t) for t in triples]
    assert [r['first_nonpositive_time'] for r in rows]==[None,'0','0','1',None,'2','0','1','0']
    linear=((0,-1,2),(0,-1,1),(0,1,0),(0,-1,0),(0,0,1),(0,0,0),(0,0,-1))
    planes=[quadratic(*t) for t in linear]
    assert [r['first_nonpositive_time'] for r in planes]==['2','1','0','0',None,'0','0']
    domains=[]
    for half_extents in ((Q(1),Q(1),Q(1)),(Q(2),Q(1),Q(1,2))):
        volume=8*half_extents[0]*half_extents[1]*half_extents[2]
        domains.append(dict(axis_aligned_half_extents=[str(x) for x in half_extents],
                            volume=str(volume),centroid=['0','0','0']))
    assert domains[0]['volume']==domains[1]['volume']=='8'
    assert domains[0]['axis_aligned_half_extents']!=domains[1]['axis_aligned_half_extents']
    payload=dict(schema='mls.occupied-geometry.exact-oracle-controls.v1',
        interval=['0','2'],quadratics=rows,planes=planes,
        equal_volume_equal_centroid_distinct_domain_witnesses=domains,
        witness_scope='Hypothetical domains with other accepted fields held fixed; not new candidate fixtures or runtime state.',
        candidate_evaluations=0,complete_input_seal=False)
    path=oracle/'exact-controls.json'
    path.write_text(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n')
    with path.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
    print(json.dumps(dict(status='PASS',quadratics=9,planes=7,domain_witnesses=2,
        bytes=path.stat().st_size,sha256=h,candidate_evaluations=0,complete_input_seal=False),sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path)
    a=p.parse_args();build(a.output)
