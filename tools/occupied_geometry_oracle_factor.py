"""Lossless exact-value factoring of pre-data oracle witness records.

Not transport compression: each distinct rational is stored once in the frozen
Q wire encoding, and typed JSON records reference that value table. The complete
original canonical JSON streams must be reproduced byte-for-byte independently.
No candidate input, witness, numerical bound or record is removed or recomputed.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import resource
import struct
import time

from occupied_geometry_input import rational


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode('ascii')


def build(source, output):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    start=time.monotonic()
    output.mkdir(parents=True,exist_ok=False)
    ids={}
    records={}
    with (output/'values.bin').open('xb+') as values:
        values.write(b'MLSOGQ01'+struct.pack('<Q',0))
        def factor(value):
            if isinstance(value,list):
                assert not value or value[0]!='$Q'
                if len(value)==2 and all(isinstance(x,str) for x in value):
                    integers=tuple(int(x) for x in value)
                    assert list(map(str,integers))==value
                    q=Fraction(*integers)
                    assert (q.numerator,q.denominator)==integers
                    key=tuple(value)
                    if key not in ids:
                        ids[key]=len(ids)
                        values.write(rational(q))
                    return ['$Q',ids[key]]
                return [factor(v) for v in value]
            if isinstance(value,dict):
                return {k:factor(value[k]) for k in sorted(value)}
            assert isinstance(value,(str,int,bool)) or value is None
            return value
        for name in ('allocation-witnesses.jsonl','leaf-weights.jsonl'):
            h=hashlib.sha256();size=0;count=0
            with (source/name).open('rb') as src,(output/name).open('xb') as dst:
                for raw in src:
                    obj=json.loads(raw)
                    assert canonical(obj)==raw
                    h.update(raw);size+=len(raw);count+=1
                    dst.write(canonical(factor(obj)))
            records[name]=dict(decoded_size=size,decoded_sha256=h.hexdigest(),records=count)
            assert time.monotonic()-start<=1800
        values.seek(8);values.write(struct.pack('<Q',len(ids)))
    files={}
    for p in sorted(output.iterdir()):
        with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
        files[p.name]=dict(size=p.stat().st_size,sha256=sha)
    result=dict(schema='mls.occupied-geometry.oracle-rational-factoring.v1',
                rational_values=len(ids),files=files,logical_streams=records,
                stored_bytes=sum(x['size'] for x in files.values()),
                candidate_evaluations=0,complete_input_seal=False)
    (output/'factor-receipt.json').write_bytes(canonical(result))
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();build(a.source,a.output)
