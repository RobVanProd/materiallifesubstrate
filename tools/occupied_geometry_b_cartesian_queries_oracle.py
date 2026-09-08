"""Independent exact face enumeration and full frozen-query comparison.

Analytical fixture information stays exclusively on this oracle side.
No candidate geometry routine is imported.
"""
import argparse
from collections import Counter
import copy
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
from occupied_geometry_input_check import Reader
from occupied_geometry_query_check import parse
from occupied_geometry_b_cartesian_oracle import check as boundary_check


def check(record,view,fixture,variant):
    domain=boundary_check(record,fixture,variant,diagnostic=False)
    rotation=domain['rotation'];translation=domain['translation']
    extent=[x*domain['scale'] for x in domain['extents']]
    planes=domain['planes'];counts=Counter()
    def forward(local):
        return tuple(translation[i]+sum(rotation[i][j]*local[j] for j in range(3)) for i in range(3))
    def expected(point):
        u=tuple(sum(rotation[j][i]*(point[j]-translation[j]) for j in range(3)) for i in range(3))
        candidates=[]
        # Enumerate and minimize over all six closed rectangles, rather than
        # copying the candidate's interior/exterior case distinction.
        for axis in range(3):
            for sign in (-1,1):
                local=[max(-extent[j],min(u[j],extent[j])) for j in range(3)]
                local[axis]=sign*extent[axis]
                p=forward(local);distance=sum((x-y)**2 for x,y in zip(p,point))
                candidates.append((distance,p))
        best=min(d for d,p in candidates)
        points=sorted({p for d,p in candidates if d==best})
        witnesses=[]
        for p in points:
            rays=sorted(n for n,d in planes.items() if sum(x*y for x,y in zip(n,p))==d)
            witnesses.append(dict(point=[str(x) for x in p],normal_cone_rays=[[str(x) for x in n] for n in rays]))
        return dict(member=all(-e<=x<=e for e,x in zip(extent,u)),
                    distance_squared=str(best),closest=witnesses)
    r=Reader(view/'8.bin',8);assert len(record['queries'])==r.count
    assert [row['id'] for row in record['queries']]==list(range(1,r.count+1))
    seen=set()
    for index in range(r.count):
        ident=r.u(8);op=r.u(1);args=parse(op,r.read(r.u(8)))
        assert 1<=ident<=r.count and ident not in seen;seen.add(ident)
        row=record['queries'][ident-1]
        assert ident==row['id'] and op==row['operation'];counts[op]+=1
        assert args[-1]==0
        if op==1:want={'volume':[str(domain['volume'])]*2}
        elif op==2:want={'boundary_reference':'exact-oriented-triangles'}
        else:assert op in (3,4,7);want=expected(args[0])
        assert row['result']==want,('query divergence',ident,op)
    r.end()
    raw=json.dumps(record['queries'],sort_keys=True,separators=(',',':')).encode()
    assert hashlib.sha256(raw).hexdigest()==record['query_stream_sha256']
    count=sum(counts.values());points=sum(counts[k] for k in (3,4,7))
    assert record['work']==record['geometry']['projected_vertices']+37+count+6*points
    return dict(status='PASS_EXACT_CARTESIAN_QUERIES',query_count=count,
        operation_counts=dict(counts),exact_global_boundary_match=True,
        hausdorff_error=['0','0'],volume_error=['0','0'],
        all_closest_sets_and_normal_cones_match=True,complete_lab=False,
        promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('record',type=Path);p.add_argument('view',type=Path)
    p.add_argument('--fixture',type=int,choices=(1,2),required=True)
    p.add_argument('--variant',type=int,choices=range(33),required=True);p.add_argument('output',type=Path)
    a=p.parse_args();assert not a.output.exists();record=json.loads(a.record.read_text())
    result=check(record,a.view,a.fixture,a.variant);mutations=[]
    for label in ('missing-query','wrong-distance','missing-normal','false-membership','wrong-boundary'):
        bad=copy.deepcopy(record)
        if label=='missing-query':bad['queries'].pop()
        elif label=='wrong-boundary':bad['boundary_triangles'][0]['normal']=['0','0','0']
        else:
            row=next(r for r in bad['queries'] if r['operation']==3)['result']
            if label=='wrong-distance':row['distance_squared']=str(Q(row['distance_squared'])+1)
            elif label=='missing-normal':row['closest'][0]['normal_cone_rays']=[]
            else:row['member']=not row['member']
        try:check(bad,a.view,a.fixture,a.variant)
        except AssertionError:mutations.append(label)
        else:raise AssertionError('mutation survived: '+label)
    result['rejected_mutations']=mutations
    a.output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(result,sort_keys=True))
