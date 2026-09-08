"""Canonical storage-order/ID variants; no geometric reconstruction or search.

The seed is supplied by the controller from the frozen expansion rule. Candidate
code sees the decoded numerical stream, never fixture labels or this controller.
Each fully decoded stream receives its own byte count and hash before sealing.
"""
import argparse
from array import array
import hashlib
import json
import mmap
from pathlib import Path
import resource
import struct
import time

MASK=(1<<64)-1


class SplitMix:
    def __init__(self,seed):self.state=seed&MASK
    def draw(self):
        self.state=(self.state+0x9e3779b97f4a7c15)&MASK
        z=self.state
        z=((z^(z>>30))*0xbf58476d1ce4e5b9)&MASK
        z=((z^(z>>27))*0x94d049bb133111eb)&MASK
        return (z^(z>>31))&MASK
    def below(self,b):
        threshold=(1<<64)%b
        while True:
            x=self.draw()
            if x>=threshold:return x%b


def permutation(count,seed):
    assert count<1<<32
    result=array('I',range(count));rng=SplitMix(seed)
    assert result.itemsize==4
    for i in range(count-1,0,-1):
        j=rng.below(i+1)
        result[i],result[j]=result[j],result[i]
    return result


def skip_q(data,p):
    assert data[p] in (0,1)
    n=struct.unpack_from('<I',data,p+1)[0];assert n<=1024
    p+=5+n
    d=struct.unpack_from('<I',data,p)[0];assert 1<=d<=1024
    return p+4+d


def spans(data,kind,count):
    fixed={2:40,3:32,4:18}
    if kind in fixed:
        width=fixed[kind]
        assert len(data)==24+count*width
        return width,None
    offsets=array('Q',[24]);p=24
    for _ in range(count):
        if kind in (1,5,7):
            p+=17 if kind==7 else 8
            for _ in range(5 if kind==5 else 3):p=skip_q(data,p)
        elif kind==6:
            p=skip_q(data,skip_q(data,p))
        elif kind==8:
            size=struct.unpack_from('<Q',data,p+9)[0]
            p+=17+size
        else:raise ValueError('unsupported ordered payload kind')
        assert p<=len(data)
        offsets.append(p)
    assert p==len(data)
    return None,offsets


def relabel(raw,kind,count,namespaces):
    if kind==6:return raw
    out=bytearray(raw)
    def flip(offset,total):
        old=struct.unpack_from('<Q',out,offset)[0]
        assert 1<=old<=total
        struct.pack_into('<Q',out,offset,total+1-old)
    flip(0,namespaces[2] if kind==4 else count)
    if kind==2:
        for offset in (8,16,24,32):flip(offset,namespaces[1])
    elif kind==3:
        ids=struct.unpack_from('<QQQ',raw,8)
        assert tuple(sorted(ids))==ids
        mapped=tuple(sorted(namespaces[1]+1-v for v in ids))
        struct.pack_into('<QQQ',out,8,*mapped)
    elif kind==4:
        flip(9,namespaces[3]);assert out[17] in (0,1)
        out[17]^=1  # Reversing three facet IDs reverses facet orientation.
    elif kind==7:
        target=out[8];assert target in (1,5)
        flip(9,namespaces[target])
    return bytes(out)


def records(source,mode,seed,namespaces):
    with source.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
        assert data[:8]==b'MLSOMG01'
        schema,kind,count=struct.unpack_from('<IIQ',data,8)
        assert schema==1
        width,offsets=spans(data,kind,count)
        if mode=='shuffle':indices=permutation(count,seed)
        elif mode=='reverse':indices=range(count-1,-1,-1)
        elif mode=='relabel':
            if kind==4:
                assert count==4*namespaces[2]
                indices=(4*t+j for t in range(namespaces[2]-1,-1,-1) for j in range(4))
            else:indices=range(count-1,-1,-1)
        else:raise ValueError('unknown frozen order variant')
        yield data[:24]
        for index in indices:
            low=24+index*width if width else offsets[index]
            high=low+width if width else offsets[index+1]
            raw=data[low:high]
            yield relabel(raw,kind,count,namespaces) if mode=='relabel' else raw


def digest(source,mode,fixture,level,namespaces):
    start=time.monotonic()
    with source.open('rb') as f:
        prefix=f.read(24)
    kind=struct.unpack_from('<I',prefix,12)[0]
    count=struct.unpack_from('<Q',prefix,16)[0]
    seed=260908^(kind<<32)^(fixture<<16)^(level<<8)
    h=hashlib.sha256();size=0;buffer=bytearray()
    for raw in records(source,mode,seed,namespaces):
        buffer.extend(raw)
        if len(buffer)>=1<<20:
            h.update(buffer);size+=len(buffer);buffer.clear()
            assert time.monotonic()-start<=1800,'input order decoding wall-time ceiling'
    h.update(buffer);size+=len(buffer)
    assert size==source.stat().st_size
    return dict(kind=kind,records=count,mode=mode,size=size,sha256=h.hexdigest(),
                seed=seed if mode=='shuffle' else None,
                candidate_evaluations=0,complete_input_seal=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path)
    p.add_argument('--mode',choices=('reverse','shuffle','relabel'),required=True)
    p.add_argument('--fixture',type=int,choices=range(1,8),required=True)
    p.add_argument('--level',type=int,choices=range(5),required=True)
    p.add_argument('--counts',required=True,help='JSON object of primitive namespace counts')
    a=p.parse_args();resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    print(json.dumps(digest(a.source,a.mode,a.fixture,a.level,
        {int(k):v for k,v in json.loads(a.counts).items()}),sort_keys=True))
