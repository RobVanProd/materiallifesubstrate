"""Construct the authorized structural certificate, never geometry answers."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode('ascii')


def build(package, replay, output):
    assert not output.exists()
    manifest=package/'candidate-manifest.json'
    root=hashlib.sha256(manifest.read_bytes()).hexdigest()
    checked=json.loads((replay/'receipt.json').read_text())
    assert checked['status']=='PASS' and checked['candidate_input_root']==root
    template=[]
    for axes in itertools.permutations(range(3)):
        vertices=[[0,0,0]]
        for axis in axes:
            v=vertices[-1].copy();v[axis]+=1;vertices.append(v)
        # Barycentric linear forms in columns (1,x,y,z).
        forms=[[1,0,0,0]]+[[0,0,0,0] for _ in range(3)]
        forms[0][axes[0]+1]=-1
        forms[1][axes[0]+1]=1;forms[1][axes[1]+1]=-1
        forms[2][axes[1]+1]=1;forms[2][axes[2]+1]=-1
        forms[3][axes[2]+1]=1
        inversions=sum(axes[i]>axes[j] for i in range(3) for j in range(i+1,3))
        if inversions%2:
            vertices[2],vertices[3]=vertices[3],vertices[2]
            forms[2],forms[3]=forms[3],forms[2]
        template.append(dict(order=list(axes),vertices=vertices,barycentric_forms=forms))
    template_id=hashlib.sha256(canonical(template)).hexdigest()
    inventory=json.loads((package/'control/controller-run-inventory-v1.json').read_text())['runs']
    bindings=[]
    for row in inventory:
        f,k,v=row['fixture'],row['level'],row['variant']
        if f not in (1,2):continue
        m=1<<k
        low=(-4*m,-4*m,-4*m) if f==1 else (-8*m,-8*m,-m)
        dimensions=(8*m,8*m,8*m) if f==1 else (16*m,16*m,2*m)
        bindings.append(dict(controller_row=[f,k,v],candidate_input_root=root,
            grid=dict(origin_numerators=list(low),coordinate_denominator=4*m,
                      cell_counts=list(dimensions)),template_version='cartesian-six-chain-v1',
            template_sha256=template_id,transform_blob=row['transform'],
            source_blobs=row['source_blobs'],decoded_I2_streams=row['views']['I2'],
            ordering=row['order'],structural_validity_only=True))
    assert len(bindings)==330
    result=dict(schema='mls.occupied-geometry.cartesian-structural-certificate.v1',
        candidate_input_root=root,template=template,template_sha256=template_id,
        independent_replay_sha256=hashlib.sha256((replay/'receipt.json').read_bytes()).hexdigest(),
        bindings=bindings,scope='B registered Cartesian cube/slab only',
        geometry_answers=[],runtime_geometry_work_exempt=False,
        candidate_evaluations=0,complete_input_seal=False)
    output.write_bytes(canonical(result))
    print(json.dumps(dict(status='CONSTRUCTED_PENDING_INDEPENDENT_CHECK',bindings=330,
                         template_sha256=template_id,candidate_input_root=root)))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('package','replay','output'):p.add_argument(name,type=Path)
    a=p.parse_args();build(a.package,a.replay,a.output)
