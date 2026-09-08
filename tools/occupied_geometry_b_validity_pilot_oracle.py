"""Independent all-pairs audit of a small general-mesh validity pilot.

Uses rational intersection-vertex enumeration, not candidate SAT/BVH routines.
This bounded control is not a replacement for the full geometry inventory.
"""
import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
from occupied_geometry_input_check import Reader
from occupied_geometry_incidence_check import facet_components
from occupied_geometry_exact_primitive_oracle import oracle,det


def check(view,record):
    vertices={};r=Reader(view/'1.bin',1)
    for _ in range(r.count):
        ident=r.u(8);vertices[ident]=tuple(r.q() for _ in range(3))
    r.end();cells={};r=Reader(view/'2.bin',2)
    assert r.count<=512,'this control is intentionally small, not a full-row substitute'
    for _ in range(r.count):
        ident=r.u(8);ids=tuple(r.u(8) for _ in range(4));cells[ident]=ids
        p=[vertices[i] for i in ids]
        assert det([[p[j+1][i]-p[0][i] for i in range(3)] for j in range(3)])>0
    r.end();groups=facet_components(cells)
    root={i:j for j,group in enumerate(groups) for i in group};counts=Counter();tested=0
    for i,j in itertools.combinations(sorted(cells),2):
        if root[i]!=root[j]:continue
        a=[vertices[k] for k in cells[i]];b=[vertices[k] for k in cells[j]]
        # Only strict box separation skips the independent LP/rank control.
        if any(max(p[k] for p in a)<min(p[k] for p in b) or max(p[k] for p in b)<min(p[k] for p in a) for k in range(3)):
            counts['disjoint']+=1;continue
        value=oracle(a,b);tested+=1;counts[value]+=1
        assert value!='positive_volume_overlap',(i,j)
    assert record['status']=='WITHIN_COMPLEX_VALIDITY_PILOT'
    assert record['predata_validity_certificate_used'] is False
    assert record['cells']==len(cells) and record['vertices']==len(vertices) and record['components']==len(groups)
    return dict(status='PASS_INDEPENDENT_SMALL_MESH_VALIDITY',all_within_component_pairs=sum(counts.values()),
                exact_vertex_enumerations=tested,classification_counts=dict(counts),
                complete_row=False,complete_lab=False,promotion='NO_PROMOTION')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('view',type=Path);p.add_argument('record',type=Path)
    p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists()
    result=check(a.view,json.loads(a.record.read_text()))
    a.output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(result,sort_keys=True))
