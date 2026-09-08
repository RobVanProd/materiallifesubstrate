"""Non-template B runtime validity pilot; not a complete geometry row."""
import argparse
import json
from pathlib import Path
import resource
import gmpy2 as g
from occupied_geometry_runtime_wire import Work,WorkLimit
from occupied_geometry_b_mesh_validity import load,check_overlap


def run(view):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));work=Work()
    try:
        vertices,cells,facets,owners,components=load(view,g.mpq(0),work)
        result=check_overlap(vertices,cells,components,work)
        result.update(status='WITHIN_COMPLEX_VALIDITY_PILOT',vertices=len(vertices),
                      cells=len(cells),facets=len(facets),boundary_facets=sum(len(o)==1 for o in owners.values()))
    except WorkLimit:
        result=dict(status='VALIDITY_RESOURCE_INCONCLUSIVE',pending=work.pending)
    result.update(candidate='B',complete_row=False,complete_lab=False,work=work.used,
                  predata_validity_certificate_used=False,promotion='NO_PROMOTION')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('view',type=Path);a=p.parse_args()
    print(json.dumps(run(a.view),sort_keys=True,separators=(',',':')))
