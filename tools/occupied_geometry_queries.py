"""Frozen numerical query/transform materialization. Oracle joins stay separate."""
from fractions import Fraction as Q
import argparse
from functools import reduce
import hashlib
import itertools
import json
from math import gcd
from pathlib import Path
import struct

import occupied_geometry_input as wire


def dot(a,b):return sum(x*y for x,y in zip(a,b))
def matvec(a,x):return tuple(dot(row,x) for row in a)
def multiply(a,b):return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)) for i in range(3))
I=((Q(1),Q(0),Q(0)),(Q(0),Q(1),Q(0)),(Q(0),Q(0),Q(1)))
ZERO=(Q(0),)*3


def transforms():
    rotations=[]
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((-1,1),repeat=3):
            a=tuple(tuple(Q(signs[i] if j==perm[i] else 0) for j in range(3)) for i in range(3))
            if wire.det(*a)==1:rotations.append(a)
    rotations.remove(I);rows=[(a,ZERO,ZERO,Q(1),0) for a in [I]+rotations]
    rz=((Q(3,5),Q(-4,5),Q(0)),(Q(4,5),Q(3,5),Q(0)),(Q(0),Q(0),Q(1)))
    rx=((Q(1),Q(0),Q(0)),(Q(0),Q(3,5),Q(-4,5)),(Q(0),Q(4,5),Q(3,5)))
    rows.extend([(I,(Q(3),Q(-2),Q(5)),ZERO,Q(1),0),
                 (rz,ZERO,ZERO,Q(1),0),(multiply(rx,rz),ZERO,ZERO,Q(1),0),
                 (I,ZERO,ZERO,Q(1,2),0),(I,ZERO,ZERO,Q(2),0),
                 (I,ZERO,(Q(1,4),Q(-1,2),Q(1,8)),Q(1),0)])
    rows.extend((I,ZERO,ZERO,Q(1),j) for j in (1,2,3))
    assert len(rows)==33
    return rows


def point_bytes(p):return b''.join(wire.rational(x) for x in p)


def patch(box,axis,side):
    rest=[j for j in range(3) if j!=axis]
    normal=tuple(Q(side if j==axis else 0) for j in range(3))
    for i,j in itertools.product(range(9),repeat=2):
        p=[Q(0)]*3;p[axis]=box[axis][side==1]
        for a,n in zip(rest,(i,j)):p[a]=box[a][0]+Q(n,8)*(box[a][1]-box[a][0])
        yield tuple(p),normal,0<i<8 and 0<j<8


def planar_patches(fixture):
    if fixture==1:boxes=[((Q(-1),Q(1)),)*3]
    elif fixture==2:boxes=[((Q(-2),Q(2)),(Q(-2),Q(2)),(Q(-1,4),Q(1,4))) ]
    else:boxes=[((Q(-1),Q(1)),(Q(-1),Q(-3,4)),(Q(-1,4),Q(1,4))),
                ((Q(-1),Q(-3,4)),(Q(-3,4),Q(1)),(Q(-1,4),Q(1,4))),
                ((Q(3,4),Q(1)),(Q(-3,4),Q(1)),(Q(-1,4),Q(1,4)))]
    for bi,box in enumerate(boxes):
        for axis in range(3):
            for side in (-1,1):
                if fixture==7 and bi>0 and axis==1 and side==-1:continue
                b=box
                if fixture==7 and bi==0 and axis==1 and side==1:
                    b=((Q(-3,4),Q(3,4)),box[1],box[2])
                yield (bi,axis,side),list(patch(b,axis,side))


def directions():
    result=set()
    for axis in range(3):
        rest=[j for j in range(3) if j!=axis]
        for sign in (-1,1):
            for a,b in itertools.product(range(-4,5),repeat=2):
                v=[0]*3;v[axis]=sign*4;v[rest[0]]=a;v[rest[1]]=b
                d=reduce(gcd,(abs(x) for x in v));result.add(tuple(x//d for x in v))
    assert len(result)==386
    return sorted(result)


def radial_point(direction,radius,centre):
    norm2=sum(x*x for x in direction);out=[]
    for x,c in zip(direction,centre):
        # The centre is an exact multiple of the encoding quantum.
        shift=c*wire.GRID;assert shift.denominator==1
        a=abs(x)*radius.numerator*wire.GRID
        n=wire.nearest_sqrt_ratio(a*a,radius.denominator**2*norm2)
        out.append(Q(int(shift)+(n if x>=0 else -n),wire.GRID))
    return tuple(out)


def window(low,high,moving=False):
    planes=[]
    for j in range(3):
        for sign,value in ((-1,-low[j]),(1,high[j])):
            planes.append((*(Q(sign if a==j else 0) for a in range(3)),value,
                           -value/4 if moving and j==0 else Q(0)))
    return sorted(planes)


def generate(out,fixture):
    out.mkdir(parents=True,exist_ok=False);(out/'candidate').mkdir();(out/'oracle').mkdir()
    times=[Q(j,8) for j in range(17)] if fixture in (5,6,7) else [Q(0)]
    inventory=[]
    for ordinal,(rotation,translation,boost,scale,ordering) in enumerate(transforms()):
        queries={}
        def transform(p,t):
            r=matvec(rotation,p)
            return tuple(scale*r[j]+translation[j]+t*boost[j] for j in range(3))
        def add(op,args,obligation):queries.setdefault((op,args),set()).add(obligation)
        def point_ops(p,t,ops,label):
            args=point_bytes(transform(p,t))+wire.rational(t)
            for op in ops:add(op,args,label)
        def region(planes):
            mapped=[]
            for *normal,d0,d1 in planes:
                n=matvec(rotation,normal)
                mapped.append((*n,scale*d0+dot(n,translation),scale*d1+dot(n,boost)))
            mapped.sort()
            return struct.pack('<Q',len(mapped))+b''.join(point_bytes(p) for p in mapped)
        for t in times:
            for op in (1,2):add(op,wire.rational(t),'global')
            if fixture in (1,2,7):
                def move(p):return (p[0]*(1-t/4),p[1],p[2]) if fixture==7 else p
                patches=list(planar_patches(fixture))
                rectangles=[(tuple(min(p[j] for p,_,_ in net) for j in range(3)),
                             tuple(max(p[j] for p,_,_ in net) for j in range(3)),net[0][1])
                            for _,net in patches]
                for patch_id,net in patches:
                    for p,n,interior in net:
                        point_ops(move(p),t,(3,4,7),('normal-gate:' if interior else 'patch:')+str(patch_id))
                        normals={normal for lo,hi,normal in rectangles
                                 if all(lo[j]<=p[j]<=hi[j] for j in range(3))}
                        # A coplanar subdivision seam is not a physical corner.
                        if len(normals)==1:
                            for offset in (Q(-1,64),Q(1,64)):
                                # Offset is along the current physical normal.
                                q=tuple(move(p)[j]+offset*n[j] for j in range(3))
                                point_ops(q,t,(3,7),'offset:'+str(patch_id))
                if fixture in (1,2):point_ops(ZERO,t,(3,4,7),'centre-nonunique')
            else:
                centres=[ZERO] if fixture==3 else (
                    [(Q(0),Q(0),Q(2)-t)] if fixture==6 else
                    [(Q(-3,2)+(t/2 if fixture==5 else 0),Q(0),Q(0)),
                     (Q(3,2)-(t/2 if fixture==5 else 0),Q(0),Q(0))])
                for ci,c in enumerate(centres):
                    for direction in directions():
                        for offset in (Q(0),Q(-1,64),Q(1,64)):
                            p=radial_point(direction,1+offset,c)
                            point_ops(p,t,(3,4,7) if not offset else (3,7),'sphere-chart:'+str(ci))
                    point_ops(c,t,(3,4,7),'sphere-centre-nonunique:'+str(ci))
            if fixture in (4,5):
                regions=[[(Q(-1),Q(0),Q(0),Q(0),Q(0))],[(Q(1),Q(0),Q(0),Q(0),Q(0))]]
                add(5,region(regions[0])+region(regions[1])+wire.rational(t),'pair-closest-set')
                point_ops(ZERO,t,(3,4,7),'pair-midpoint')
            if fixture==7:
                regions=[window((Q(-1),Q(0),Q(-1,8)),(Q(0),Q(3,4),Q(1,8)),True),
                         window((Q(0),Q(0),Q(-1,8)),(Q(1),Q(3,4),Q(1,8)),True)]
                add(5,region(regions[0])+region(regions[1])+wire.rational(t),'u-closest-set')
        if fixture in (5,6,7):
            for a,b in [(Q(0),Q(2))]+[(Q(j,8),Q(j+1,8)) for j in range(16)]:
                if fixture==6:
                    n=matvec(rotation,(Q(0),Q(0),Q(1)))
                    args=b'\x01'+wire.rational(a)+wire.rational(b)+point_bytes((*n,dot(n,translation),dot(n,boost)))
                else:args=b'\x00'+wire.rational(a)+wire.rational(b)+region(regions[0])+region(regions[1])
                add(6,args,'complete-swept-interval')
        if fixture==7 and ordinal==0:
            payload=wire.rational(Q(4))
            add(8,struct.pack('<QQ',1,len(payload))+payload,'singular-u-time-four')
        path=out/'candidate'/f'queries-{ordinal:02}.bin';join=out/'oracle'/f'queries-{ordinal:02}.jsonl'
        with path.open('xb') as f,join.open('x') as j:
            f.write(wire.header(8,len(queries)))
            for i,((op,args),obligations) in enumerate(sorted(queries.items())):
                f.write(struct.pack('<QBQ',i+1,op,len(args))+args)
                j.write(json.dumps(dict(query=i+1,obligations=sorted(obligations)),sort_keys=True)+'\n')
        transform_path=out/'candidate'/f'transform-{ordinal:02}.bin'
        with transform_path.open('xb') as f:
            f.write(wire.header(9,1)+struct.pack('<Q',ordinal+1)+point_bytes(
                (*[x for row in rotation for x in row],*translation,*boost,scale))+bytes([ordering]))
        with path.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
        inventory.append(dict(variant=ordinal,queries=len(queries),bytes=path.stat().st_size,sha256=h))
    (out/'oracle/query-inventory.json').write_text(json.dumps(dict(fixture=fixture,
        variants=inventory,levels=[0,1,2,3,4],candidate_evaluations=0,complete_input_seal=False),sort_keys=True)+'\n')
    print(json.dumps(dict(fixture=fixture,variants=33,queries=sum(x['queries'] for x in inventory)),sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path)
    p.add_argument('--fixture',type=int,choices=range(1,8),required=True)
    a=p.parse_args();generate(a.output,a.fixture)
