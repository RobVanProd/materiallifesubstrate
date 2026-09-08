"""Independent exact-tree / 512-bit outward audit of a C volume proof.

No candidate engine imports. Splits may be conservative; every accepted inside
or outside leaf must be independently justified, including the exterior tail.
"""
import argparse
from collections import deque
import copy
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import gmpy2 as g
from occupied_geometry_input_check import Reader


def check(view,record):
    for name,sha in record['inputs'].items():
        with (view/name).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==sha
    r=Reader(view/'6.bin',6);assert r.count==1;delta2,volume=r.q(),r.q();r.end()
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
    def mp(q):return g.mpq(q.numerator,q.denominator)
    power=delta2**3*volume**2
    with g.context(precision=512,round=g.RoundDown):
        hlo=g.rootn(g.mpfr(mp(power)),6);base=2*g.const_pi()*hlo;nlo=base*g.sqrt(base)
    with g.context(precision=512,round=g.RoundUp):
        hhi=g.rootn(g.mpfr(mp(power)),6);base=2*g.const_pi()*hhi;nhi=base*g.sqrt(base)
    radius=record['exterior_radius'];assert type(radius)is int and 1<=radius<=4194304
    with g.context(precision=512,round=g.RoundUp):
        tail=g.mpfr(mp(volume))/nlo*g.exp(-g.mpfr(radius**2)/(2*hhi))
    assert tail<g.mpfr('0.5'),'uncertified exterior'
    root=tuple((min(p[j] for p,w in values)-radius,max(p[j] for p,w in values)+radius) for j in range(3))
    half=max(b-a for a,b in root)/2
    root=tuple(((a+b)/2-half,(a+b)/2+half) for a,b in root)
    assert record['root_box']==[[str(a),str(b)] for a,b in root]
    def size(box):return (box[0][1]-box[0][0])*(box[1][1]-box[1][0])*(box[2][1]-box[2][0])
    def range_(box):
        lows=[];highs=[]
        for p,w in values:
            near=Q(0);far=Q(0)
            for x,(a,b) in zip(p,box):
                dist=max(a-x,Q(0),x-b)
                near+=dist**2;far+=max((x-a)**2,(x-b)**2)
            with g.context(precision=512,round=g.RoundUp):far_up=g.mpfr(mp(far))
            with g.context(precision=512,round=g.RoundDown):
                lows.append(g.mpfr(mp(w))*g.exp(-far_up/(2*hlo))/nhi)
                near_down=g.mpfr(mp(near))
            with g.context(precision=512,round=g.RoundUp):
                highs.append(g.mpfr(mp(w))*g.exp(-near_down/(2*hhi))/nlo)
        with g.context(precision=512,round=g.RoundDown):lo=sum(lows,g.mpfr(0))
        with g.context(precision=512,round=g.RoundUp):hi=sum(highs,g.mpfr(0))
        return lo,hi
    decisions=bytes.fromhex(record['proof_decisions_hex'])
    assert len(decisions)==record['completed_box_decisions']
    queue=deque([root]);inside=Q(0);unresolved=size(root);split=0;leaves=0
    for decision in decisions:
        assert queue and decision in (0,1,2)
        box=queue.popleft()
        if decision==2:
            widths=[b-a for a,b in box];axis=widths.index(max(widths));mid=sum(box[axis])/2
            left=list(box);right=list(box);left[axis]=(box[axis][0],mid);right[axis]=(mid,box[axis][1])
            queue.extend((tuple(left),tuple(right)));split+=1
        else:
            lo,hi=range_(box)
            assert hi<g.mpfr('0.5') if decision==0 else lo>=g.mpfr('0.5'),('invalid leaf',decision)
            unresolved-=size(box);inside+=size(box) if decision else 0;leaves+=1
    assert unresolved==sum((size(box) for box in queue),Q(0))
    assert record['occupied_volume']==[str(inside),str(inside+unresolved)]
    work=2*len(values)+radius+1+len(values)*len(decisions)+2*split
    if record['pending'] is not None:
        pending=record['pending']
        if pending['operation']=='child_cover_regions':work+=len(values)
        else:assert pending['operation']=='interval_field_primitive_contributions'
        assert pending['used']==work and pending['used']+pending['requested']>4194304
        assert record['status']=='VOLUME_RESOURCE_INCONCLUSIVE'
    else:
        assert unresolved<=volume/5000 and record['status']=='VOLUME_ENCLOSURE_COMPLETE'
    assert work==record['work']<=4194304
    return dict(status='PASS',independent_precision=512,inside_outside_leaves=leaves,
        splits=split,occupied_volume=record['occupied_volume'],work=work,
        complete_row=False,complete_lab=False,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('view','record','output'):p.add_argument(name,type=Path)
    a=p.parse_args();assert not a.output.exists();record=json.loads(a.record.read_text())
    result=check(a.view,record)
    bad=copy.deepcopy(record);bad['occupied_volume']=['-1','-1']
    try:check(a.view,bad)
    except AssertionError:result['false_volume_mutation_rejected']=True
    else:raise AssertionError('mutation survived')
    a.output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(result,sort_keys=True))
