"""Controller projection of a sealed validity proof; no oracle/grid answers.

The sandbox receives a validity capability bound to exact decoded table hashes,
not the certificate's controller row identifiers or numerical construction data.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT='8ec8ba42956f7664c66de26ce2f760be650cba76ef7fe0820d92396206e84516'


def issue(package,view,f,k,v,out):
    assert not out.exists()
    raw=(package/'input-root-seal.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==ROOT
    seal=json.loads(raw);assert seal['data_gate_open']
    sha=seal['cartesian_validity_certificate_sha256'];raw=(package/'control'/sha).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==sha
    certificate=json.loads(raw)
    assert certificate['candidate_input_root']==seal['manifests']['candidate-manifest.json']
    binding=next(b for b in certificate['bindings'] if b['controller_row']==[f,k,v])
    assert binding['structural_validity_only'] and binding['template_version']=='cartesian-six-chain-v1'
    files={str(kind)+'.bin':value for kind,value in binding['decoded_I2_streams'].items()}
    assert set(p.name for p in view.iterdir())==set(files)
    for name,value in files.items():
        path=view/name
        assert not path.is_symlink() and path.stat().st_size==value['size']
        with path.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==value['sha256']
    result=dict(schema='mls.occupied-geometry.validity-capability.v1',
        root_sha256=ROOT,template_sha256=binding['template_sha256'],files=files,
        precondition='complete_uniform_cartesian_six_chain_mesh',
        valid_geometry_answers=False,runtime_geometry_work_exempt=False)
    out.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(status='ISSUED_AUTHENTICATED_VALIDITY_ONLY',sha256=hashlib.sha256(out.read_bytes()).hexdigest())))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package',type=Path);p.add_argument('view',type=Path)
    p.add_argument('--fixture',type=int,choices=(1,2),required=True);p.add_argument('--level',type=int,choices=range(5),required=True)
    p.add_argument('--variant',type=int,choices=range(33),required=True);p.add_argument('output',type=Path)
    a=p.parse_args();issue(a.package,a.view,a.fixture,a.level,a.variant,a.output)
