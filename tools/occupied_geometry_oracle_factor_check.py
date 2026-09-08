"""Independent byte-for-byte reconstruction of factored oracle-only records."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import time

from occupied_geometry_input_check import Reader


def check(factored, original):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    start=time.monotonic()
    receipt=json.loads((factored/'factor-receipt.json').read_bytes())
    assert set(p.name for p in factored.iterdir())==set(receipt['files'])|{'factor-receipt.json'}
    for name,record in receipt['files'].items():
        p=factored/name
        assert p.is_file() and not p.is_symlink() and p.stat().st_size==record['size']
        with p.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==record['sha256']
    r=Reader.__new__(Reader);r.f=(factored/'values.bin').open('rb')
    assert r.read(8)==b'MLSOGQ01'
    count=r.u(8);assert count==receipt['rational_values']
    values=[]
    for _ in range(count):
        q=r.q();values.append([str(q.numerator),str(q.denominator)])
    r.end()
    assert len({tuple(v) for v in values})==len(values)
    def restore(obj):
        if isinstance(obj,list):
            if obj and obj[0]=='$Q':
                assert len(obj)==2 and type(obj[1]) is int and 0<=obj[1]<len(values)
                return values[obj[1]]
            return [restore(x) for x in obj]
        if isinstance(obj,dict):return {k:restore(v) for k,v in obj.items()}
        return obj
    checked={}
    for name,want in receipt['logical_streams'].items():
        sha=hashlib.sha256();size=0;lines=0
        with (factored/name).open('rb') as encoded,(original/name).open('rb') as source:
            for row in encoded:
                obj=restore(json.loads(row))
                raw=(json.dumps(obj,sort_keys=True,separators=(',',':'))+'\n').encode('ascii')
                assert raw==source.readline(),('decoded oracle bytes',name,lines)
                sha.update(raw);size+=len(raw);lines+=1
            assert source.read(1)==b''
        actual=dict(decoded_size=size,decoded_sha256=sha.hexdigest(),records=lines)
        assert actual==want
        checked[name]=actual
        assert time.monotonic()-start<=1800
    print(json.dumps(dict(status='PASS',logical_streams=checked,
        rational_values=count,stored_bytes=receipt['stored_bytes'],
        candidate_evaluations=0,complete_input_seal=False),sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('factored',type=Path);p.add_argument('original',type=Path)
    a=p.parse_args();check(a.factored,a.original)
