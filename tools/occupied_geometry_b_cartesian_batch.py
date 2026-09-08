"""Controller batch for the registered Cartesian query inventory only.

Inputs are materialized from the sealed root. Candidate execution remains
isolated, and the independent oracle runs afterward. Raw execution directories
are retained; lossless compressed records are the portable evidence objects.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from occupied_geometry_b_cartesian_queries_oracle import check


def invoke(arguments,log):
    with log.open('xb') as stream:
        result=subprocess.run([sys.executable,*map(str,arguments)],stdout=stream,
                              stderr=subprocess.STDOUT,timeout=1900)
    assert result.returncode==0,(str(log),result.returncode)


def run(package,scratch,evidence,levels,variants):
    assert not scratch.exists() and not evidence.exists()
    scratch.mkdir();evidence.mkdir();rows=[];tools=Path(__file__).resolve().parent
    for fixture in (1,2):
        for level in levels:
            for variant in variants:
                key=f'f{fixture}-k{level}-v{variant:02}'
                view=scratch/(key+'-input');output=scratch/(key+'-twins')
                invoke([tools/'occupied_geometry_materialize_view.py',package,
                    '--fixture',fixture,'--level',level,'--variant',variant,
                    '--tier','I2',view],scratch/(key+'-decode.log'))
                invoke([tools/'occupied_geometry_candidate_sandbox.py',view,output,
                    '--volume','--queries','--candidate','B','--package',package,
                    '--fixture',fixture,'--level',level,'--variant',variant],
                    scratch/(key+'-execute.log'))
                raw=(output/'twin-0.json').read_bytes()
                assert raw==(output/'twin-1.json').read_bytes()
                record=json.loads(raw);verified=check(record,view,fixture,variant)
                payload=dict(fixture=fixture,level=level,variant=variant,
                    candidate=record,independent=verified,
                    isolation=json.loads((output/'receipt.json').read_text()),
                    validity_capability=json.loads((output/'capability.json').read_text()),
                    decoded_input_receipt=(scratch/(key+'-decode.log')).read_text())
                encoded=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()+b'\n'
                compressed=gzip.compress(encoded,mtime=0)
                assert gzip.decompress(compressed)==encoded
                name=key+'.json.gz';(evidence/name).write_bytes(compressed)
                row=dict(fixture=fixture,level=level,variant=variant,file=name,
                    size=len(compressed),sha256=hashlib.sha256(compressed).hexdigest(),
                    decoded_sha256=hashlib.sha256(encoded).hexdigest(),
                    query_count=verified['query_count'],work=record['work'])
                rows.append(row)
                (evidence/'progress.json').write_text(json.dumps(dict(rows=rows,
                    complete_lab=False,promotion='NO_PROMOTION'),sort_keys=True,separators=(',',':'))+'\n')
                print(json.dumps(dict(completed=key,work=record['work'],queries=verified['query_count'])),flush=True)
    manifest=dict(status='PASS_REGISTERED_CARTESIAN_QUERY_SUBSET',rows=rows,
        complete_lab=False,promotion='NO_PROMOTION')
    (evidence/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package',type=Path)
    p.add_argument('scratch',type=Path);p.add_argument('evidence',type=Path)
    p.add_argument('--levels',type=int,nargs='+',choices=range(5),required=True)
    p.add_argument('--variants',type=int,nargs='+',choices=range(33),required=True)
    a=p.parse_args();run(a.package,a.scratch,a.evidence,sorted(set(a.levels)),sorted(set(a.variants)))
