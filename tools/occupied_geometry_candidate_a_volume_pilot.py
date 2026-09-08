"""Registered-time A union-volume pilot; no complete-row claim."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import gmpy2 as g
from occupied_geometry_runtime_wire import Reader,Work
from occupied_geometry_a_volume import enclose


def run(view,time):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    assert set(p.name for p in view.iterdir())=={'5.bin','6.bin','7.bin','8.bin'}
    r=Reader(view/'6.bin',6);assert r.count==1;delta2,volume=r.q(),r.q();r.end()
    assert delta2>0 and volume>0
    r=Reader(view/'5.bin',5);samples={};amount=g.mpq(0)
    for _ in range(r.count):
        identifier=r.uint(8);assert identifier>0 and identifier not in samples
        samples[identifier]=(tuple(r.q() for _ in range(3)),r.q());amount+=r.q()
    r.end();assert amount==1
    r=Reader(view/'7.bin',7);vel={}
    for _ in range(r.count):
        r.uint(8);assert r.uint(1)==5;identifier=r.uint(8)
        assert identifier in samples and identifier not in vel
        vel[identifier]=tuple(r.q() for _ in range(3))
    r.end();assert not vel or set(vel)==set(samples)
    points=[];weights=[]
    for identifier,(point,weight) in sorted(samples.items()):
        v=vel.get(identifier,(g.mpq(0),)*3)
        points.append(tuple(point[j]+time*v[j] for j in range(3)));weights.append(weight)
    if not vel:assert time==0
    result=enclose(points,weights,volume,Work())
    result['proof_decisions_hex']=result.pop('proof_decisions').hex()
    result.update(candidate='A',precision=256,time=str(time),claim_scope='union-volume-query pilot only')
    result['inputs']={}
    for path in sorted(view.iterdir()):
        with path.open('rb') as f:result['inputs'][path.name]=hashlib.file_digest(f,'sha256').hexdigest()
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('view',type=Path);p.add_argument('--time',default='0')
    a=p.parse_args();print(json.dumps(run(a.view,g.mpq(a.time)),sort_keys=True,separators=(',',':')))
