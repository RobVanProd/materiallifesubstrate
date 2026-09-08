"""Decode global query transforms using only frozen numerical query arguments.

Oracle joins are handled separately by the controller audit below. They never
enter the numerical query decoder or a candidate evaluator.
"""
import argparse
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import resource
import struct
import time

from occupied_geometry_input_check import Reader
from occupied_geometry_query_check import parse
from occupied_geometry_transform_decode import load_transform
from occupied_geometry_input import header,rational


def decoded_rows(source,transform_path):
    tr=Reader(transform_path,9);assert tr.count==1
    identifier=tr.u(8)
    matrix=tuple(tuple(tr.q() for _ in range(3)) for _ in range(3))
    translation=tuple(tr.q() for _ in range(3));boost=tuple(tr.q() for _ in range(3))
    scale=tr.q();ordering=tr.u(1);tr.end()
    assert scale>0 and ordering in range(4)
    def vector(v):return tuple(sum(row[j]*v[j] for j in range(3)) for row in matrix)
    def wire(qs):return b''.join(rational(q) for q in qs)
    def position(p,t):
        v=vector(p)
        return wire(scale*v[i]+translation[i]+t*boost[i] for i in range(3))
    def plane(p):
        n=vector(p[:3])
        return (*n,scale*p[3]+sum(n[i]*translation[i] for i in range(3)),
                scale*p[4]+sum(n[i]*boost[i] for i in range(3)))
    def region(rows):
        converted=sorted(plane(p) for p in rows)
        return struct.pack('<Q',len(converted))+b''.join(wire(p) for p in converted)
    r=Reader(source,8);result=[]
    for index in range(r.count):
        old_id=r.u(8);assert old_id==index+1
        op=r.u(1);raw=r.read(r.u(8));value=parse(op,raw)
        if op in (1,2):args=wire(value)
        elif op in (3,4,7):
            p,t=value;args=position(p,t)+rational(t)
        elif op==5:
            a,b,t=value;args=region(a)+region(b)+rational(t)
        elif op==6:
            mode,a,b,*parts=value
            args=bytes([mode])+wire((a,b))
            args+=wire(plane(parts[0])) if mode else region(parts[0])+region(parts[1])
        else:
            assert op==8
            if identifier!=1:continue  # Registered invalid control is identity-only.
            args=raw
        result.append((op,args,old_id))
    r.end()
    result.sort(key=lambda row:(row[0],row[1]))
    assert len({(op,args) for op,args,_ in result})==len(result)
    return result


def check(directory,output):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));start=time.monotonic()
    assert not output.exists()
    oracle={r['query']:r['obligations'] for r in
            map(json.loads,(directory/'oracle/queries-00.jsonl').read_text().splitlines())}
    receipts=[]
    for ordinal in range(33):
        rows=decoded_rows(directory/'candidate/queries-00.bin',
                          directory/'candidate'/f'transform-{ordinal:02}.bin')
        qhash=hashlib.sha256();ohash=hashlib.sha256();qsize=osize=0
        def compare(raw,f,h):
            assert f.read(len(raw))==raw,('factored stream mismatch',ordinal)
            h.update(raw)
            return len(raw)
        with (directory/'candidate'/f'queries-{ordinal:02}.bin').open('rb') as qf,\
             (directory/'oracle'/f'queries-{ordinal:02}.jsonl').open('rb') as of:
            qsize+=compare(header(8,len(rows)),qf,qhash)
            for new_id,(op,args,old_id) in enumerate(rows,1):
                qsize+=compare(struct.pack('<QBQ',new_id,op,len(args))+args,qf,qhash)
                join=(json.dumps(dict(query=new_id,obligations=oracle[old_id]),sort_keys=True)+'\n').encode()
                osize+=compare(join,of,ohash)
            assert qf.read(1)==of.read(1)==b''
        receipts.append(dict(variant=ordinal,records=len(rows),
            query=dict(size=qsize,sha256=qhash.hexdigest()),
            oracle_join=dict(size=osize,sha256=ohash.hexdigest())))
        print('decoded query and join variant',ordinal,flush=True)
        assert time.monotonic()-start<1800,'input decoding wall-time ceiling'
    payload=dict(status='PASS',schema='mls.occupied-geometry.query-factoring.v1',
                 streams=receipts,candidate_evaluations=0,complete_input_seal=False)
    output.write_text(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(status='PASS',variants=len(receipts),candidate_evaluations=0,complete_input_seal=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();check(a.directory,a.output)
