"""Complete canonical sphere primitive tables from pre-data weight witnesses."""
import argparse
from fractions import Fraction as Q
import hashlib
import itertools
import json
from pathlib import Path
import resource
import struct
import sys
import time

sys.dont_write_bytecode=True
import occupied_geometry_input as gen
from occupied_geometry_input_check import Reader


def fraction(pair):return Q(int(pair[0]),int(pair[1]))


def finish(root,weights,depth):
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    started=time.monotonic();deadline=started+1800
    metadata=json.loads((weights/'receipt.json').read_text());total=fraction(metadata['total'])
    values={}
    with (weights/'allocation-witnesses.jsonl').open() as f:
        for line in f:
            r=json.loads(line)
            if len(r['path'])!=depth-1:continue
            for i,v in enumerate(r['child_weights']):values[tuple(r['path'])+(i,)]=fraction(v)
    ordered=[values[p] for p in sorted(values)]
    assert len(ordered)==8**depth and sum(ordered)*8==total
    # Decode the already materialized coordinate bytes, never round again.
    reader=Reader(root/'candidate/vertices.bin',1);points=[]
    for i in range(reader.count):
        assert reader.u(8)==i+1
        points.append(tuple(reader.q() for _ in range(3)))
    reader.end()
    reference=gen.reference(depth);refpoints=sorted({p for t in reference for p in t})
    assert len(refpoints)==len(points)
    ids={p:i+1 for i,p in enumerate(refpoints)}
    by_cell={tuple(sorted(ids[p] for p in cell)):ordered[i%(8**depth)]
             for i,cell in enumerate(reference)}
    reader=Reader(root/'candidate/tetrahedra.bin',2);cells=[];facets=set();samples=[]
    for i in range(reader.count):
        assert reader.u(8)==i+1
        cell=tuple(reader.u(8) for _ in range(4));cells.append(cell)
        key=tuple(sorted(cell))
        centre=tuple(sum(points[j-1][a] for j in cell)/4 for a in range(3))
        samples.append((centre,key,by_cell[key]))
        for a in range(4):facets.add(tuple(sorted(cell[j] for j in range(4) if j!=a)))
    reader.end();facets=sorted(facets);facet_ids={f:i+1 for i,f in enumerate(facets)}
    paths=[]
    path=root/'candidate/facets.bin';paths.append(path)
    with path.open('xb') as f:
        f.write(gen.header(3,len(facets)))
        for i,face in enumerate(facets):f.write(struct.pack('<4Q',i+1,*face))
    path=root/'candidate/incidence.bin';paths.append(path)
    with path.open('xb') as f:
        f.write(gen.header(4,4*len(cells)))
        for i,cell in enumerate(cells):
            for a in range(4):
                face=[cell[j] for j in range(4) if j!=a]
                inv=sum(face[j]>face[k] for j in range(3) for k in range(j+1,3))
                f.write(struct.pack('<QBQB',i+1,a,facet_ids[tuple(sorted(face))],(a+inv)%2))
    path=root/'candidate/samples.bin';paths.append(path)
    join=root/'oracle/sample-cell-join.jsonl'
    cell_ids={tuple(sorted(c)):i+1 for i,c in enumerate(cells)}
    with path.open('xb') as f,join.open('x') as j:
        f.write(gen.header(5,len(samples)))
        for i,(centre,key,volume) in enumerate(sorted(samples)):
            f.write(struct.pack('<Q',i+1)+b''.join(gen.rational(x) for x in (*centre,volume,volume/total)))
            j.write(json.dumps([i+1,cell_ids[key]],separators=(',',':'))+'\n')
    paths.append(join)
    original=json.loads((root/'oracle/input-check.json').read_text())
    path=root/'candidate/resolution.bin';paths.append(path)
    with path.open('xb') as f:
        f.write(gen.header(6,1)+gen.rational(fraction(original['delta_squared']))+gen.rational(total))
    files={}
    for path in paths:
        with path.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
        files[str(path.relative_to(root))]=dict(size=path.stat().st_size,sha256=h)
    assert time.monotonic()<=deadline,'input wall-time ceiling'
    (root/'oracle/primitive-completion.json').write_text(json.dumps(dict(
        depth=depth,facets=len(facets),incidence=4*len(cells),samples=len(samples),
        files=files,candidate_evaluations=0,complete_input_seal=False),sort_keys=True)+'\n')
    print('PASS sphere primitive tables',depth,'seconds',time.monotonic()-started,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path)
    p.add_argument('weights',type=Path);p.add_argument('--depth',type=int,choices=range(1,6),required=True)
    a=p.parse_args();finish(a.root,a.weights,a.depth)
