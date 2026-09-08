"""Decoded I1 motion identities for the three frozen storage-order variants."""
import argparse
import json
from pathlib import Path
import resource

from occupied_geometry_input_check import Reader
from occupied_geometry_order_decode import digest


def run(root,out):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30));assert not out.exists();rows=[]
    for fixture,stem,start in ((5,'pair-d',1),(6,'plane-d',1),(7,'u-k',0)):
        for level in range(5):
            source=root/f'i1-motion-{stem}{level+start}'/'motion.bin'
            r=Reader(source,7);count=r.count;r.f.close()
            for variant,mode in ((30,'reverse'),(31,'shuffle'),(32,'relabel')):
                result=digest(source,mode,fixture,level,{5:count})
                rows.append(dict(fixture=fixture,level=level,variant=variant,stream=result))
    payload=dict(status='PASS',schema='mls.occupied-geometry.i1-motion-orders.v1',
        streams=rows,candidate_evaluations=0,complete_input_seal=False)
    out.write_text(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(status='PASS',streams=len(rows),candidate_evaluations=0,complete_input_seal=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();run(a.root,a.output)
