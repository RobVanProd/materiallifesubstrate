"""B structural-precondition pilot; derive actual boundary/volume at runtime."""
import argparse
import json
from pathlib import Path
import resource
import gmpy2 as g
from occupied_geometry_runtime_wire import Work
from occupied_geometry_b_cartesian import construct,boundary,point_query,world


def encode(value):
    if isinstance(value,g.mpq):return str(value)
    if isinstance(value,dict):return {k:encode(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [encode(v) for v in value]
    return value


def run(view,capability):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));work=Work()
    mesh=construct(view,capability,work);patches=boundary(mesh,work)
    work.charge('occupied_volume_evaluation');volume=g.mpq(1)
    for a,b in zip(mesh['low'],mesh['high']):volume*=b-a
    centre=world([(a+b)/2 for a,b in zip(mesh['low'],mesh['high'])],mesh['axes'])
    diagnostic=point_query(mesh,centre,work)
    return encode(dict(candidate='B',status='CARTESIAN_GEOMETRY_PILOT',
        complete_row=False,complete_lab=False,precision=256,
        geometry=mesh,occupied_volume=[volume,volume],boundary_triangles=patches,
        centre_diagnostic=diagnostic,work=work.used,
        claim_scope='root-qualified validity only; geometry derived from actual input vertices',
        promotion='NO_PROMOTION'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('view',type=Path);p.add_argument('capability',type=Path)
    a=p.parse_args();print(json.dumps(run(a.view,a.capability),sort_keys=True,separators=(',',':')))
