"""Fresh independent byte checks for the narrowly authorized validity premise.

Only cube/slab rows qualify. Each subprocess receives its own 2 GiB/1800 s
ceiling. Copying and hashing inputs is included in the per-row elapsed ceiling.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


def run(package, output):
    assert not output.exists();output.mkdir()
    manifest=package/'candidate-manifest.json'
    root=hashlib.sha256(manifest.read_bytes()).hexdigest()
    files=json.loads(manifest.read_text())['files']
    inventory=json.loads((package/'control/controller-run-inventory-v1.json').read_text())['runs']
    cases=[r for r in inventory if r['fixture'] in (1,2) and r['variant']==0]
    assert len(cases)==10
    checker=Path(__file__).with_name('occupied_geometry_box_check.py').resolve()
    def one(row):
        start=time.monotonic();shape='cube' if row['fixture']==1 else 'slab';k=row['level']
        target=output/f'{shape}-k{k}';(target/'candidate').mkdir(parents=True)
        bindings={}
        for kind,name in enumerate(('vertices','tetrahedra','facets','incidence','samples','resolution'),1):
            key=row['source_blobs'][str(kind)];source=package/key
            assert key in files and source.is_file() and not source.is_symlink()
            dest=target/'candidate'/f'{name}.bin';shutil.copyfile(source,dest)
            with dest.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
            assert files[key]==dict(size=dest.stat().st_size,sha256=sha)
            bindings[str(kind)]=dict(blob=key,**files[key])
        timeout=1800-(time.monotonic()-start);assert timeout>0
        proc=subprocess.run([sys.executable,str(checker),str(target),'--fixture',shape,'--level',str(k)],
                            capture_output=True,text=True,timeout=timeout)
        (target/'stdout.log').write_text(proc.stdout)
        (target/'stderr.log').write_text(proc.stderr)
        assert proc.returncode==0,(shape,k,proc.stderr)
        result=json.loads(proc.stdout);assert result['status']=='PASS'
        elapsed=time.monotonic()-start;assert elapsed<=1800
        receipt=dict(candidate_input_root=root,fixture=row['fixture'],level=k,
            inputs=bindings,independent_check=result,
            checked_primitive_counts={name:result[name] for name in
                ('vertices','tetrahedra','facets','incidence','samples')},
            candidate_evaluations=0,complete_input_seal=False)
        (target/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,separators=(',',':'))+'\n')
        (target/'external-timing.json').write_text(json.dumps(dict(seconds=elapsed))+'\n')
        print('independent Cartesian certificate replay PASS',shape,k,flush=True)
        return receipt
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(one,cases))
    result=dict(status='PASS',candidate_input_root=root,rows=results,
        checker_sha256=hashlib.sha256(checker.read_bytes()).hexdigest(),
        candidate_evaluations=0,complete_input_seal=False)
    (output/'receipt.json').write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(status='PASS',rows=len(results),candidate_input_root=root)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();run(a.package,a.output)
