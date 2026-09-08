"""Independent 512-bit/exact audit of the Candidate C amplitude pilot.

Uses the independently derived identity M^2=V/((2*pi)^3*Delta^3),
not the candidate's cube-root/bandwidth/normalizer evaluation graph.
"""
import argparse
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import gmpy2 as g

from occupied_geometry_input_check import Reader


def check(view,record):
    assert record['candidate']=='C' and record['precision']==256 and record['complete_row'] is False
    for name,sha in record['inputs'].items():
        with (view/name).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==sha
    r=Reader(view/'5.bin',5);n=r.count;total=Q(0);ids=[]
    for _ in range(n):
        ids.append(r.u(8))
        for _ in range(3):r.q()
        total+=r.q();assert r.q()>0
    r.end();assert len(set(ids))==n and min(ids)>0
    r=Reader(view/'6.bin',6);assert r.count==1
    delta2,volume=r.q(),r.q();r.end();assert total==volume>0 and delta2>0
    v=g.mpq(volume.numerator,volume.denominator);d=g.mpq(delta2.numerator,delta2.denominator)
    with g.context(precision=512,round=g.RoundDown):
        pi_lo=g.const_pi();dlo=g.mpfr(d);den_lo=8*pi_lo*pi_lo*pi_lo*dlo*g.sqrt(dlo)
    with g.context(precision=512,round=g.RoundUp):
        pi_hi=g.const_pi();dhi=g.mpfr(d);den_hi=8*pi_hi*pi_hi*pi_hi*dhi*g.sqrt(dhi)
        upper=g.sqrt(g.mpfr(v)/den_lo)
    with g.context(precision=512,round=g.RoundDown):
        lower=g.sqrt(g.mpfr(v)/den_hi)
    assert 0<lower<=upper
    reported=g.mpq(record['global_field_upper'])
    assert reported>=g.mpq(upper), 'reported upper does not cover independent outward envelope'
    assert record['work']==n+1 and record['sample_count']==n
    empty=reported<g.mpq(1,2)
    assert (record['status']=='PILOT_GLOBAL_EMPTY_CERTIFIED')==empty
    assert record['occupied_volume_interval']==(['0','0'] if empty else None)
    return dict(status='PASS',independent_precision=512,
        amplitude_enclosure=[str(g.mpq(lower)),str(g.mpq(upper))],
        exact_input_volume=str(volume),exact_delta_squared=str(delta2),
        global_empty=empty,complete_row=False,complete_lab=False,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('view','record','output'):p.add_argument(name,type=Path)
    a=p.parse_args();assert not a.output.exists();record=json.loads(a.record.read_text())
    result=check(a.view,record)
    changed=dict(record,global_field_upper='0')
    try:check(a.view,changed)
    except AssertionError:result['understated_bound_mutation_rejected']=True
    else:raise AssertionError('bad bound survived')
    a.output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(result,sort_keys=True))
