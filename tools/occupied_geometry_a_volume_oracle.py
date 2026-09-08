"""Independent 512-bit radii and exact union-cover audit for the A pilot."""
import argparse
from collections import deque
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import gmpy2 as g
from occupied_geometry_input_check import Reader


def check(view,record):
    assert record['candidate']=='A' and record['precision']==256
    for name,sha in record['inputs'].items():
        with (view/name).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==sha
    r=Reader(view/'6.bin',6);assert r.count==1;r.q();volume=r.q();r.end()
    r=Reader(view/'5.bin',5);samples={}
    for _ in range(r.count):
        i=r.u(8);assert i not in samples
        samples[i]=(tuple(r.q() for _ in range(3)),r.q());assert r.q()>0
    r.end();assert sum(w for p,w in samples.values())==volume
    r=Reader(view/'7.bin',7);vel={}
    for _ in range(r.count):
        r.u(8);assert r.u(1)==5;i=r.u(8);assert i not in vel
        vel[i]=tuple(r.q() for _ in range(3))
    r.end();t=Q(record['time']);assert vel or t==0
    assert not vel or set(vel)==set(samples)
    values=[(tuple(p[j]+t*vel.get(i,(Q(0),)*3)[j] for j in range(3)),w) for i,(p,w) in sorted(samples.items())]
    cache={}
    with g.context(precision=512,round=g.RoundDown):pi_lo=g.const_pi()
    with g.context(precision=512,round=g.RoundUp):pi_hi=g.const_pi()
    for p,w in values:
        if w in cache:continue
        # Radius squared directly, via cube root of (3V/(4pi))^2.
        q=g.mpq(w.numerator,w.denominator)
        with g.context(precision=512,round=g.RoundDown):
            x=3*g.mpfr(q)/(4*pi_hi);low=g.rootn(x*x,3)
        with g.context(precision=512,round=g.RoundUp):
            x=3*g.mpfr(q)/(4*pi_lo);high=g.rootn(x*x,3);radius=g.sqrt(high)
        cache[w]=(Q(g.mpq(low)),Q(g.mpq(high)),Q(g.mpq(radius)))
    reported_radius=Q(record['radius_upper'])
    assert reported_radius>=max(v[2] for v in cache.values())
    assert record['unique_radius_count']==len(cache)
    root=tuple((min(p[j] for p,w in values)-reported_radius,
                max(p[j] for p,w in values)+reported_radius) for j in range(3))
    half=max(b-a for a,b in root)/2
    root=tuple(((a+b)/2-half,(a+b)/2+half) for a,b in root)
    assert record['root_box']==[[str(a),str(b)] for a,b in root]
    def size(box):return (box[0][1]-box[0][0])*(box[1][1]-box[1][0])*(box[2][1]-box[2][0])
    def validate(box,decision):
        inside=False;outside=True
        for p,w in values:
            near=Q(0);far=Q(0)
            for x,(a,b) in zip(p,box):
                distance=max(a-x,Q(0),x-b);near+=distance**2
                far+=max((x-a)**2,(x-b)**2)
            lo,hi,_=cache[w]
            inside|=far<=lo;outside&=near>hi
        assert inside if decision else outside,('invalid union leaf',decision)
    decisions=bytes.fromhex(record['proof_decisions_hex'])
    assert len(decisions)==record['completed_box_decisions']
    queue=deque([root]);inside=Q(0);unresolved=size(root);splits=0;leaves=0
    for decision in decisions:
        assert queue and decision in (0,1,2);box=queue.popleft()
        if decision==2:
            widths=[b-a for a,b in box];axis=widths.index(max(widths));mid=sum(box[axis])/2
            left=list(box);right=list(box);left[axis]=(box[axis][0],mid);right[axis]=(mid,box[axis][1])
            queue.extend((tuple(left),tuple(right)));splits+=1
        else:
            validate(box,decision);unresolved-=size(box)
            if decision:inside+=size(box)
            leaves+=1
    assert unresolved==sum((size(b) for b in queue),Q(0))
    assert record['occupied_volume']==[str(inside),str(inside+unresolved)]
    work=2*len(values)+2*len(cache)+1+len(values)*len(decisions)+2*splits
    if record['pending']:
        pending=record['pending']
        if pending['operation']=='child_cover_regions':work+=len(values)
        else:assert pending['operation']=='sphere_box_predicates'
        assert pending['used']==work and pending['used']+pending['requested']>4194304
        assert record['status']=='VOLUME_RESOURCE_INCONCLUSIVE'
    else:assert unresolved<=volume/5000 and record['status']=='VOLUME_ENCLOSURE_COMPLETE'
    assert record['work']==work<=4194304
    return dict(status='PASS',independent_precision=512,inside_outside_leaves=leaves,
        splits=splits,work=work,occupied_volume=record['occupied_volume'],
        complete_row=False,complete_lab=False,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('view','record','output'):p.add_argument(name,type=Path)
    a=p.parse_args();assert not a.output.exists()
    result=check(a.view,json.loads(a.record.read_text()))
    a.output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(result,sort_keys=True))
