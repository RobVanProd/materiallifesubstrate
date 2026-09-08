"""Controller batch of the first volume query; retains incomplete-row scope."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from occupied_geometry_a_volume_oracle import check as check_a
from occupied_geometry_c_volume_oracle import check as check_c


def call(arguments,log):
    with log.open('xb') as f:
        outcome=subprocess.run([sys.executable,*map(str,arguments)],stdout=f,stderr=subprocess.STDOUT,timeout=1900)
    assert outcome.returncode==0,(str(log),outcome.returncode)


def run(package,scratch,evidence,levels):
    assert not scratch.exists() and not evidence.exists();scratch.mkdir();evidence.mkdir()
    tools=Path(__file__).resolve().parent;rows=[]
    for level in levels:
        for fixture in range(1,8):
            key=f'f{fixture}-k{level}-v00';view=scratch/(key+'-input')
            call([tools/'occupied_geometry_materialize_view.py',package,'--fixture',fixture,
                '--level',level,'--variant',0,'--tier','I1',view],scratch/(key+'-decode.log'))
            for candidate,check in (('A',check_a),('C',check_c)):
                out=scratch/(key+'-'+candidate)
                call([tools/'occupied_geometry_candidate_sandbox.py',view,out,'--candidate',candidate,'--volume'],scratch/(key+'-'+candidate+'.log'))
                raw=(out/'twin-0.json').read_bytes();assert raw==(out/'twin-1.json').read_bytes()
                record=json.loads(raw);verified=check(view,record)
                payload=dict(fixture=fixture,level=level,variant=0,candidate=record,independent=verified,
                    isolation=json.loads((out/'receipt.json').read_text()),
                    input_decode_receipt=(scratch/(key+'-decode.log')).read_text())
                encoded=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()+b'\n'
                compressed=gzip.compress(encoded,mtime=0);assert gzip.decompress(compressed)==encoded
                name=key+'-'+candidate+'.json.gz';(evidence/name).write_bytes(compressed)
                rows.append(dict(file=name,size=len(compressed),sha256=hashlib.sha256(compressed).hexdigest(),
                    decoded_sha256=hashlib.sha256(encoded).hexdigest(),fixture=fixture,level=level,
                    candidate=candidate,status=record['status'],work=record['work']))
                (evidence/'progress.json').write_text(json.dumps(dict(rows=rows,complete_lab=False),sort_keys=True,separators=(',',':'))+'\n')
                print(json.dumps(rows[-1]),flush=True)
    (evidence/'manifest.json').write_text(json.dumps(dict(rows=rows,complete_lab=False,promotion='NO_PROMOTION'),sort_keys=True,separators=(',',':'))+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package',type=Path);p.add_argument('scratch',type=Path)
    p.add_argument('evidence',type=Path);p.add_argument('--levels',type=int,nargs='+',choices=range(4),required=True)
    a=p.parse_args();run(a.package,a.scratch,a.evidence,sorted(set(a.levels)))
