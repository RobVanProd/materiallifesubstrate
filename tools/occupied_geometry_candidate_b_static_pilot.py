"""General single-complex static query pilot with charged runtime validity."""
import argparse
import json
from pathlib import Path
import resource
import gmpy2 as g
from occupied_geometry_runtime_wire import Reader,Work,WorkLimit
from occupied_geometry_b_mesh_validity import load,check_overlap
from occupied_geometry_b_static_queries import construct,query
from occupied_geometry_exact_primitives import tetrahedron_membership


def encode(value):
    if isinstance(value,g.mpq):return str(value)
    if isinstance(value,dict):return {k:encode(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [encode(v) for v in value]
    return value


def run(view):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));work=Work();records=[];result={}
    try:
        vertices,cells,facets,owners,components=load(view,g.mpq(0),work)
        validity=check_overlap(vertices,cells,components,work)
        mesh=construct(vertices,cells,facets,owners,components,work)
        result.update(validity=validity,occupied_volume=[mesh['volume']]*2,
            boundary_triangles=[dict(vertices=p,normal_ray=n) for p,n in mesh['triangles']])
        reader=Reader(view/'8.bin',8);seen=set()
        for _ in range(reader.count):
            ident=reader.uint(8);op=reader.uint(1);size=reader.uint(8);start=reader.f.tell()
            assert ident not in seen and 1<=ident<=reader.count;seen.add(ident)
            assert op in (1,2,3,4,7),'unsupported by static single-complex pilot'
            p=tuple(reader.q() for _ in range(3)) if op in (3,4,7) else None
            assert reader.q()==0 and reader.f.tell()-start==size
            work.charge('diagnostic_query')
            if op==1:answer=dict(volume=[mesh['volume']]*2)
            elif op==2:answer=dict(boundary_reference='exact-oriented-triangles')
            elif op in (3,4):answer=query(mesh,p,work)
            else:
                member=False
                for cell in sorted(cells):
                    if tetrahedron_membership([vertices[i] for i in cells[cell]],p,work)['closed']:
                        member=True;break
                answer=dict(member=member)
            records.append(dict(id=ident,operation=op,result=answer))
        reader.end();status='STATIC_QUERY_INVENTORY_COMPLETE'
    except WorkLimit:status='STATIC_QUERY_RESOURCE_INCONCLUSIVE'
    result.update(candidate='B',status=status,queries=sorted(records,key=lambda row:row['id']),
        work=work.used,pending=work.pending,complete_row=False,complete_lab=False,
        predata_validity_certificate_used=False,promotion='NO_PROMOTION')
    return encode(result)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('view',type=Path);a=p.parse_args()
    print(json.dumps(run(a.view),sort_keys=True,separators=(',',':')))
