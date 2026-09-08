"""Independent exact template, lattice and root-binding certificate checks.

No imports from the certificate constructor or Cartesian fixture generator.
The global extension argument is documented in the accompanying proof note;
the finite checks establish its template and byte-instantiation premises.
"""
import argparse
from collections import Counter
import copy
from fractions import Fraction as Q
import hashlib
import itertools
import json
from pathlib import Path

from occupied_geometry_input_check import Reader


def determinant(a,b,c):
    return a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])


def check_template(template):
    assert len(template)==6
    # Enumerate subsets of cube corners, selecting all maximal Boolean chains.
    corners=list(itertools.product((0,1),repeat=3));chains=set()
    for subset in itertools.combinations(corners,4):
        chain=sorted(subset,key=sum)
        if [sum(p) for p in chain]!=[0,1,2,3]:continue
        if all(all(a<=b for a,b in zip(chain[i],chain[i+1])) for i in range(3)):
            chains.add(tuple(chain))
    assert len(chains)==6
    seen=set();orders=[];facets={}
    for tet in template:
        vertices=[tuple(v) for v in tet['vertices']]
        chain=tuple(sorted(vertices,key=sum));assert chain in chains and chain not in seen;seen.add(chain)
        edges=[tuple(vertices[i][j]-vertices[0][j] for j in range(3)) for i in (1,2,3)]
        assert determinant(*edges)==1
        axes=tuple(next(j for j in range(3) if chain[i+1][j]!=chain[i][j]) for i in range(3))
        assert list(axes)==tet['order'];orders.append(axes)
        forms=tet['barycentric_forms'];assert len(forms)==4 and all(len(p)==4 for p in forms)
        # Exact affine delta property uniquely identifies barycentric coordinates.
        for i,form in enumerate(forms):
            for j,p in enumerate(vertices):
                assert sum(a*b for a,b in zip(form,(1,*p)))==int(i==j)
        assert [sum(form[j] for form in forms) for j in range(4)]==[1,0,0,0]
        # Identify nonnegativity with the four sorted-coordinate inequalities.
        expected=[[1,0,0,0]]+[[0,0,0,0] for _ in range(3)]
        expected[0][axes[0]+1]=-1
        for i in (1,2):expected[i][axes[i-1]+1]=1;expected[i][axes[i]+1]=-1
        expected[3][axes[2]+1]=1
        assert sorted(forms)==sorted(expected)
        for omitted in range(4):
            face=[p for j,p in enumerate(vertices) if j!=omitted]
            parity=(omitted+sum(face[i]>face[j] for i in range(3) for j in range(i+1,3)))%2
            key=tuple(sorted(face));facets.setdefault(key,[]).append(1 if parity==0 else -1)
    assert seen==chains and len(set(orders))==6
    for a,b in itertools.combinations(orders,2):
        assert any(a.index(i)<a.index(j) and b.index(j)<b.index(i) for i in range(3) for j in range(3))
    boundary={}
    for face,signs in facets.items():
        assert len(signs) in (1,2)
        if len(signs)==2:assert sum(signs)==0
        else:
            axes=[(j,face[0][j]) for j in range(3) if all(p[j]==face[0][j] for p in face)]
            assert len(axes)==1
            boundary[face]=signs[0]
    assert len(boundary)==12
    assert Counter((j,s) for face in boundary for j in range(3) for s in (0,1)
                   if all(p[j]==s for p in face))==Counter({(j,s):2 for j in range(3) for s in (0,1)})
    for axis in range(3):
        low={tuple(tuple(p[j]+int(j==axis) for j in range(3)) for p in face):sign
             for face,sign in boundary.items() if all(p[axis]==0 for p in face)}
        high={face:sign for face,sign in boundary.items() if all(p[axis]==1 for p in face)}
        assert set(low)==set(high) and all(low[f]==-high[f] for f in low)
    return dict(tetrahedra=6,determinants_one=6,interior_face_pairs=6,
                boundary_triangles=12,neighbor_axis_matches=3,strict_order_pair_checks=15)


def check(package,replay,certificate):
    root=hashlib.sha256((package/'candidate-manifest.json').read_bytes()).hexdigest()
    assert certificate['candidate_input_root']==root
    assert certificate['geometry_answers']==[] and certificate['runtime_geometry_work_exempt'] is False
    assert certificate['scope']=='B registered Cartesian cube/slab only'
    template=check_template(certificate['template'])
    encoded=(json.dumps(certificate['template'],sort_keys=True,separators=(',',':'))+'\n').encode('ascii')
    template_sha=hashlib.sha256(encoded).hexdigest();assert certificate['template_sha256']==template_sha
    receipt=json.loads((replay/'receipt.json').read_text())
    assert receipt['status']=='PASS' and receipt['candidate_input_root']==root
    assert certificate['independent_replay_sha256']==hashlib.sha256((replay/'receipt.json').read_bytes()).hexdigest()
    verified={(r['fixture'],r['level']):r for r in receipt['rows']};assert len(verified)==10
    rows=json.loads((package/'control/controller-run-inventory-v1.json').read_text())['runs']
    inventory={(r['fixture'],r['level'],r['variant']):r for r in rows}
    bindings=certificate['bindings'];assert len(bindings)==330
    assert [tuple(b['controller_row']) for b in bindings]==[(f,k,v) for f in (1,2) for k in range(5) for v in range(33)]
    for b in bindings:
        f,k,v=b['controller_row'];row=inventory[f,k,v];checked=verified[f,k]
        assert b['candidate_input_root']==root and b['template_sha256']==template_sha
        assert b['template_version']=='cartesian-six-chain-v1' and b['structural_validity_only'] is True
        assert b['source_blobs']==row['source_blobs'] and b['decoded_I2_streams']==row['views']['I2']
        assert b['transform_blob']==row['transform'] and b['ordering']==row['order']
        m=2**k;dimensions=[8*m]*3 if f==1 else [16*m,16*m,2*m]
        origin=[-n//2 for n in dimensions]
        assert b['grid']==dict(origin_numerators=origin,coordinate_denominator=4*m,cell_counts=dimensions)
        assert checked['independent_check']['tetrahedra']==6*dimensions[0]*dimensions[1]*dimensions[2]
        for kind in range(1,7):assert checked['inputs'][str(kind)]['blob']==row['source_blobs'][str(kind)]
        path=package/b['transform_blob'];assert hashlib.sha256(path.read_bytes()).hexdigest()==path.name
        r=Reader(path,9);assert r.count==1 and r.u(8)==v+1
        matrix=[[r.q() for _ in range(3)] for _ in range(3)]
        translation=[r.q() for _ in range(3)];boost=[r.q() for _ in range(3)]
        scale=r.q();order=r.u(1);r.end()
        assert scale>0 and determinant(*matrix)==1
        for i in range(3):
            for j in range(3):assert sum(matrix[a][i]*matrix[a][j] for a in range(3))==int(i==j)
        for tet in certificate['template']:
            ps=tet['vertices']
            edges=[[Q(ps[i][j]-ps[0][j],4*m) for j in range(3)] for i in (1,2,3)]
            transformed=[[scale*sum(matrix[i][j]*edge[j] for j in range(3))
                          for i in range(3)] for edge in edges]
            assert determinant(*transformed)==(scale/Q(4*m))**3>0
        assert order==(0 if v<30 else v-29)
    return dict(status='PASS',candidate_input_root=root,template_checks=template,
                certified_bindings=330,independent_full_byte_rows=10,
                candidate_evaluations=0,complete_input_seal=False)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('package','replay','certificate','output'):p.add_argument(name,type=Path)
    a=p.parse_args();assert not a.output.exists()
    value=json.loads(a.certificate.read_text());result=check(a.package,a.replay,value)
    rejected=[]
    for mode in ('wrong_root','changed_vertex','changed_grid','changed_transform','changed_stream','geometry_answer'):
        bad=copy.deepcopy(value)
        if mode=='wrong_root':bad['candidate_input_root']='0'*64
        elif mode=='changed_vertex':bad['template'][0]['vertices'][0][0]=2
        elif mode=='changed_grid':bad['bindings'][0]['grid']['cell_counts'][0]+=1
        elif mode=='changed_transform':bad['bindings'][0]['transform_blob']=bad['bindings'][1]['transform_blob']
        elif mode=='changed_stream':bad['bindings'][0]['decoded_I2_streams']['1']['sha256']='0'*64
        else:bad['geometry_answers']=['forbidden precomputed result']
        try:check(a.package,a.replay,bad)
        except AssertionError:rejected.append(mode)
        else:raise AssertionError(('mutation survived',mode))
    result['rejected_mutations']=rejected
    a.output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(result,sort_keys=True))
