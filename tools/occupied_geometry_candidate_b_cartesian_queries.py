"""Exact registered point queries on B's authenticated Cartesian union.

This is a query implementation, not an oracle or a full-lab disposition.
The controller must separately certify the global boundary/error gates.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import gmpy2 as g
from occupied_geometry_runtime_wire import Reader, Work
from occupied_geometry_b_cartesian import construct, boundary, point_query


def encode(value):
    if isinstance(value,g.mpq): return str(value)
    if isinstance(value,dict): return {k:encode(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [encode(v) for v in value]
    return value


def run(view,capability):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    work=Work();mesh=construct(view,capability,work)
    patches=boundary(mesh,work)
    # Materialize this observer object once, charging its construction.
    work.charge('occupied_volume_evaluation')
    volume=g.mpq(1)
    for lo,hi in zip(mesh['low'],mesh['high']): volume*=hi-lo
    reader=Reader(view/'8.bin',8);previous=None;records=[]
    for index in range(reader.count):
        ident=reader.uint(8);op=reader.uint(1);size=reader.uint(8)
        start=reader.f.tell();assert ident==index+1 and op in (1,2,3,4,7)
        point=tuple(reader.q() for _ in range(3)) if op in (3,4,7) else None
        time=reader.q();assert time==0
        assert reader.f.tell()-start==size
        # Each request is independently charged, including duplicates across
        # observable types. No zero-cost cross-query memoization.
        work.charge('diagnostic_query')
        if op==1: result={'volume':[volume,volume]}
        elif op==2: result={'boundary_reference':'exact-oriented-triangles'}
        else: result=point_query(mesh,point,work)
        records.append({'id':ident,'operation':op,'result':result})
    reader.end()
    raw=json.dumps(encode(records),sort_keys=True,separators=(',',':')).encode()
    return encode(dict(candidate='B',status='CARTESIAN_QUERY_STREAM',
        complete_row=False,complete_lab=False,query_inventory_complete=True,
        geometry=mesh,boundary_triangles=patches,occupied_volume=[volume,volume],
        queries=records,query_stream_sha256=hashlib.sha256(raw).hexdigest(),
        work=work.used,promotion='NO_PROMOTION'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('view',type=Path)
    parser.add_argument('capability',type=Path);args=parser.parse_args()
    print(json.dumps(run(args.view,args.capability),sort_keys=True,separators=(',',':')))
