"""Exact semantic covariance across authenticated Cartesian query records.

Proof triangulations may have different internal diagonals. They are checked
as exact complete boundaries by the independent row oracle; this comparison
normalizes physical query answers, not proof-object serialization.
"""
import argparse
from fractions import Fraction as Q
import gzip
import hashlib
import json
from pathlib import Path
from occupied_geometry_input_check import Reader
from occupied_geometry_query_check import parse,registered_transform


def normalize(payload,query_path):
    record=payload['candidate'];variant=payload['variant']
    rotation,shift,boost,scale,_=registered_transform(variant)
    def inverse_point(p):
        p=list(map(Q,p))
        return tuple(sum(rotation[j][i]*(p[j]-shift[j]) for j in range(3))/scale for i in range(3))
    def inverse_normal(n):
        n=list(map(Q,n));return tuple(sum(rotation[j][i]*n[j] for j in range(3)) for i in range(3))
    expected=payload['validity_capability']['files']['8.bin']
    assert query_path.stat().st_size==expected['size']
    with query_path.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected['sha256']
    r=Reader(query_path,8);args={}
    for _ in range(r.count):
        ident=r.u(8);op=r.u(1);value=parse(op,r.read(r.u(8)));assert value[-1]==0
        assert ident not in args;args[ident]=(op,value)
    r.end();assert len(args)==len(record['queries'])==2339
    normalized=[]
    for row in record['queries']:
        op,value=args[row['id']];assert op==row['operation']
        signature=(op,tuple(str(x) for x in inverse_point(value[0])) if op in (3,4,7) else ())
        answer=row['result']
        if op==1:answer={'volume':[str(Q(x)/scale**3) for x in answer['volume']]}
        elif op==2:assert answer==dict(boundary_reference='exact-oriented-triangles')
        else:
            witnesses=[]
            for witness in answer['closest']:
                point=inverse_point(witness['point'])
                normals=sorted(inverse_normal(n) for n in witness['normal_cone_rays'])
                witnesses.append((point,normals))
            witnesses.sort()
            answer=dict(member=answer['member'],distance_squared=str(Q(answer['distance_squared'])/scale**2),
                closest=[dict(point=list(map(str,p)),normals=[list(map(str,n)) for n in ns]) for p,ns in witnesses])
        normalized.append((signature,answer))
    normalized.sort(key=lambda item:item[0]);assert len({x[0] for x in normalized})==2339
    return json.dumps(normalized,sort_keys=True,separators=(',',':')).encode()


def run(evidence_dirs,scratch_dirs):
    assert len(evidence_dirs)==len(scratch_dirs);baselines={};counts={};rows=[]
    for evidence,scratch in zip(evidence_dirs,scratch_dirs):
        manifest=json.loads((evidence/'manifest.json').read_text())
        for row in manifest['rows']:
            packed=(evidence/row['file']).read_bytes()
            assert len(packed)==row['size'] and hashlib.sha256(packed).hexdigest()==row['sha256']
            raw=gzip.decompress(packed);assert hashlib.sha256(raw).hexdigest()==row['decoded_sha256']
            payload=json.loads(raw);f,k,v=(payload[key] for key in ('fixture','level','variant'))
            assert (f,k,v)==tuple(row[key] for key in ('fixture','level','variant'))
            assert payload['independent']['status']=='PASS_EXACT_CARTESIAN_QUERIES'
            key=f'f{f}-k{k}-v{v:02}'
            normal=normalize(payload,scratch/(key+'-input')/'8.bin')
            if v==0:assert (f,k) not in baselines;baselines[f,k]=normal
            else:assert normal==baselines[f,k],('semantic covariance divergence',f,k,v)
            counts[f,k]=counts.get((f,k),0)+1
            rows.append(dict(fixture=f,level=k,variant=v,normalized_scientific_sha256=hashlib.sha256(normal).hexdigest()))
    assert all(n==33 for n in counts.values())
    return dict(status='PASS_EXACT_CARTESIAN_SEMANTIC_COVARIANCE',rows=rows,
        levels=sorted({k for f,k in counts}),complete_lab=False,promotion='NO_PROMOTION',
        proof_boundary_scope='each complete oriented boundary independently checked, not raw diagonal identity')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,nargs='+',required=True)
    p.add_argument('--scratch',type=Path,nargs='+',required=True);p.add_argument('output',type=Path)
    a=p.parse_args();assert not a.output.exists();result=run(a.evidence,a.scratch)
    a.output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(status=result['status'],rows=len(result['rows']),levels=result['levels'],promotion='NO_PROMOTION')))
