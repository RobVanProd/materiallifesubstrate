"""Exact pre-data runtime-validity budget audit, not a candidate evaluation."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def run(root, repo, output):
    assert not output.exists()
    rows=[]
    for fixture in ('cube','slab'):
        for level in range(5):
            path=root/f'{fixture}-k{level}/candidate/tetrahedra.bin'
            with path.open('rb') as f:
                magic,schema,kind,count=struct.unpack('<8sIIQ',f.read(24))
            assert (magic,schema,kind)==(b'MLSOMG01',1,2)
            assert count==3072*8**level
            assert path.stat().st_size==24+40*count
            # Separate exact Cartesian count derivation from physical extents.
            # Integer half-metre units avoid any floating arithmetic in audit.
            side_halves=(4,4,4) if fixture=='cube' else (8,8,1)
            subdivisions=[s*(2<<level) for s in side_halves]
            cartesian=subdivisions[0]*subdivisions[1]*subdivisions[2]
            assert 6*cartesian==count
            rows.append(dict(fixture=fixture,level=level,tetrahedra=count,
                cartesian_cells=cartesian,minimum_one_validity_predicate_per_cell_work=count,
                work_cap=4194304,exceeds_cap=count>4194304,
                input_loading_work_charged=0))
    blocked=[r for r in rows if r['exceeds_cap']]
    assert [(r['fixture'],r['level']) for r in blocked]==[('cube',4),('slab',4)]
    docs={}
    for name in ('preregistration','addendum'):
        path=repo/'docs'/f'occupied-matter-geometry-foundation-{name}.md'
        docs[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    result=dict(schema='mls.occupied-geometry.b-validity-work-preflight.v1',
        status='PRE_DATA_SCIENTIFIC_RESOURCE_SCOPE_ESCALATION',rows=rows,
        interpretation='registered per-primitive candidate validity checks are charged runtime work; input-generation validity is not a free candidate certificate',
        claim_boundary='not a universal complexity lower bound on geometry algorithms; no candidate was run',
        governing_document_sha256=docs,candidate_evaluations=0,complete_input_seal=False,
        promotion='NO_PROMOTION')
    output.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(status=result['status'],blocked_rows=blocked,candidate_evaluations=0),sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('root','repo','output'):p.add_argument(name,type=Path)
    a=p.parse_args();run(a.root,a.repo,a.output)
