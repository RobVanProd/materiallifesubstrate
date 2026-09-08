"""Close the registered input gate only after every named pre-data audit passes."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from occupied_geometry_input_package_check import check as check_package
from occupied_geometry_cartesian_certificate_check import check as check_certificate


def seal(package):
    destination=package/'input-root-seal.json';assert not destination.exists()
    closed=check_package(package)
    recipe=json.loads((package/'control/package-recipe.json').read_text())
    aliases={source:package/blob for source,blob in recipe['input_source_to_blob'].items()}
    gates=[]
    def require(name, expected=None):
        path=aliases[name];objects=[]
        for line in path.read_text().splitlines():
            try:value=json.loads(line)
            except json.JSONDecodeError:continue
            if isinstance(value,dict):objects.append(value)
        assert objects,('no receipt',name)
        value=objects[-1];assert value.get('status')=='PASS',('input gate',name,value)
        assert value.get('candidate_evaluations',0)==0
        if expected:
            for k,v in expected.items():assert value[k]==v,(name,k)
        gates.append(dict(receipt=path.relative_to(package).as_posix(),
                          sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        return value
    for shape in ('cube','slab','u'):
        for k in range(5):require(f'{shape}-k{k}-independent.log',dict(level=k,fixture=shape))
    for d in range(1,6):
        require(f'sphere-d{d}/independent-check.json',dict(depth=d,tetrahedra=8*8**d))
        require(f'sphere-d{d}-joins-independent-v1.log',dict(depth=d,exact_sample_cell_weight_joins=True))
        require(f'sphere-injectivity-d{d}.json',dict(depth=d,failed_sylvester_cells=[]))
        require(f'pair-d{d}-independent.log')
        require(f'plane-d{d}/independent-pose-check.json')
        for shape in ('pair','plane'):require(f'motion-{shape}-d{d}-independent.log')
        require(f'motion-u-k{d-1}-independent.log')
    require('weight-independent-replay-regrouped.log',dict(independent_binomial_integrals=32768,child_allocations_checked=37448))
    require('oracle-factor-independent-v1.log',dict(rational_values=90570))
    require('oracle-domain-independent-v1.log',dict(domains=7,exact_directed_constant_rounding=True))
    require('moving-pair-validity-d1/independent-full-facet-check.json',dict(complex_sizes=[64,64]))
    for f in range(1,8):
        require(f'queries-f{f}-independent-strict-v2.log',dict(fixture=f,independently_reconstructed_finite_point_nets=True))
        require(f'query-factoring-f{f}.json')
    for name,count in (('native-cartesian-v1.json',10),('native-other-v1.json',50)):
        value=require(name,dict(pending=[]));assert len(value['datasets'])==count
    for name,count in (('native-orders-cartesian-v1.json',10),('native-orders-other-v1.json',25)):
        assert len(require(name)['rows'])==count
    require('i1-motion-orders-v1.json')
    require('final-query-joins-v1.json')
    certificate=json.loads(aliases['cartesian-validity-v1/certificate.json'].read_text())
    # The independent certificate verifier reads only the root-bound replay
    # receipt here; all ten full-byte replays were performed before packaging.
    with tempfile.TemporaryDirectory(prefix='mls-cartesian-seal-check-') as tmp:
        p=Path(tmp);(p/'receipt.json').write_bytes(aliases['cartesian-validity-v1/replay/receipt.json'].read_bytes())
        certificate_result=check_certificate(package,p,certificate)
    require('cartesian-validity-v1/independent-check.json',dict(certified_bindings=330,independent_full_byte_rows=10))
    lean=aliases['lean-cartesian-certificate-v1.log'].read_text()
    assert 'Build completed successfully (2146 jobs).' in lean
    assert 'error:' not in lean
    gates.append(dict(receipt=aliases['lean-cartesian-certificate-v1.log'].relative_to(package).as_posix(),
                      sha256=hashlib.sha256(lean.encode()).hexdigest()))
    result=dict(schema='mls.occupied-geometry.complete-input-root.v1',
        generator_source_sha=recipe['source_sha'],parent_sha=recipe['parent_sha'],
        manifests=closed['manifests'],governing_documents=recipe['governing_documents'],
        run_inventory_sha256=hashlib.sha256((package/recipe['run_inventory']).read_bytes()).hexdigest(),
        runs=1155,views=2310,input_audits=gates,
        cartesian_validity_certificate_sha256=hashlib.sha256(aliases['cartesian-validity-v1/certificate.json'].read_bytes()).hexdigest(),
        cartesian_validity_result=certificate_result,
        candidate_evaluations=0,complete_input_seal=True,data_gate_open=True,
        promotion='NO_PROMOTION',new_geometry_evidence_ceiling_bytes=8589934592,
        stored_bytes_before_root_seal=closed['stored_bytes'])
    raw=(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n').encode('ascii')
    assert closed['stored_bytes']+len(raw)<=8589934592
    destination.write_bytes(raw)
    print(json.dumps(dict(status='INPUT_SEALED',root_sha256=hashlib.sha256(raw).hexdigest(),
        stored_bytes=closed['stored_bytes']+len(raw),remaining_bytes=8589934592-closed['stored_bytes']-len(raw),
        candidate_evaluations=0,data_gate_open=True,promotion='NO_PROMOTION'),sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package',type=Path)
    seal(p.parse_args().package)
