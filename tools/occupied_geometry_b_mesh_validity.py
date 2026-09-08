"""Charged runtime validity for non-template tetrahedral inputs.

No pre-data Cartesian certificate is accepted here. Connectivity comes solely
from full stored facets. Exact pair predicates check within-component overlap;
cross-component pairs remain union-geometry obligations, not silently discarded.
"""
from occupied_geometry_runtime_wire import Reader
from occupied_geometry_exact_primitives import orientation,tetrahedron_intersection


def load(view,time,work):
    vertices={};r=Reader(view/'1.bin',1)
    for _ in range(r.count):
        ident=r.uint(8);assert ident not in vertices
        vertices[ident]=tuple(r.q() for _ in range(3))
    r.end()
    motion={};r=Reader(view/'7.bin',7)
    for _ in range(r.count):
        r.uint(8);kind=r.uint(1);ident=r.uint(8);velocity=tuple(r.q() for _ in range(3))
        assert kind in (1,5)
        if kind==1:
            assert ident in vertices and ident not in motion;motion[ident]=velocity
    r.end()
    for ident,velocity in motion.items():
        work.charge('moving_vertex_evaluation')
        vertices[ident]=tuple(x+time*v for x,v in zip(vertices[ident],velocity))
    cells={};r=Reader(view/'2.bin',2)
    for _ in range(r.count):
        ident=r.uint(8);ids=tuple(r.uint(8) for _ in range(4))
        assert ident not in cells and len(set(ids))==4 and all(i in vertices for i in ids)
        assert orientation([vertices[i] for i in ids],work)>0,'nonpositive cell orientation'
        cells[ident]=ids
    r.end()
    facets={};r=Reader(view/'3.bin',3)
    for _ in range(r.count):
        ident=r.uint(8);ids=tuple(r.uint(8) for _ in range(3))
        work.charge('stored_facet_validity')
        assert ident not in facets and len(set(ids))==3 and tuple(sorted(ids))==ids
        assert all(i in vertices for i in ids);facets[ident]=ids
    r.end()
    # Sorting/uniqueness is structural validity, not trusted generator output.
    work.charge('cell_key_uniqueness',len(cells))
    assert len({tuple(sorted(ids)) for ids in cells.values()})==len(cells)
    work.charge('facet_key_uniqueness',len(facets))
    assert len(set(facets.values()))==len(facets)
    work.charge('facet_owner_cache_entries',len(facets));owners={ident:[] for ident in facets}
    seen=set();r=Reader(view/'4.bin',4)
    for _ in range(r.count):
        cell=r.uint(8);opposite=r.uint(1);facet=r.uint(8);sign=r.uint(1)
        work.charge('stored_incidence_validity')
        assert cell in cells and opposite<4 and facet in facets and sign<2
        assert (cell,opposite) not in seen;seen.add((cell,opposite))
        face=[i for j,i in enumerate(cells[cell]) if j!=opposite]
        assert tuple(sorted(face))==facets[facet]
        inversions=sum(face[i]>face[j] for i in range(3) for j in range(i+1,3))
        assert sign==(opposite+inversions)%2
        owners[facet].append((cell,sign));assert len(owners[facet])<=2
    r.end();assert len(seen)==4*len(cells) and all(owners.values())
    work.charge('connectivity_cache_entries',len(cells));parents={i:i for i in cells}
    def root(i):
        while parents[i]!=i:i=parents[i]
        return i
    for row in owners.values():
        if len(row)==2:
            work.charge('shared_facet_connectivity')
            (a,sa),(b,sb)=row;assert sa!=sb
            a,b=sorted((root(a),root(b)));parents[b]=a
    components={i:root(i) for i in cells}
    return vertices,cells,facets,owners,components


def check_overlap(vertices,cells,components,work):
    bounds={}
    for ident,ids in cells.items():
        work.charge('cell_bounding_region')
        bounds[ident]=tuple((min(vertices[i][j] for i in ids),max(vertices[i][j] for i in ids)) for j in range(3))
    def tree(ids):
        if len(ids)==1:return (bounds[ids[0]],ids[0],None,None)
        work.charge('bvh_node')
        box=tuple((min(bounds[i][j][0] for i in ids),max(bounds[i][j][1] for i in ids)) for j in range(3))
        widths=[b-a for a,b in box];axis=widths.index(max(widths))
        ids.sort(key=lambda i:(sum(bounds[i][axis]),i));middle=len(ids)//2
        return box,None,tree(ids[:middle]),tree(ids[middle:])
    hierarchy=tree(sorted(cells));pairs=0
    def compare(a,b):
        nonlocal pairs
        work.charge('cell_pair_box_pruning')
        # Equality excludes positive-volume intersection, but is NOT evidence
        # of no contact. This routine answers only the mesh-validity question.
        if any(hi<=otherlo or otherhi<=lo for (lo,hi),(otherlo,otherhi) in zip(a[0],b[0])):return
        if a[1] is not None and b[1] is not None:
            i,j=a[1],b[1]
            if components[i]!=components[j]:return
            value=tetrahedron_intersection([vertices[k] for k in cells[i]],[vertices[k] for k in cells[j]],work)
            pairs+=1;assert value!='positive_volume_overlap',('within_complex_overlap',i,j)
        elif a[1] is None:
            compare(a[2],b);compare(a[3],b)
        else:compare(a,b[2]);compare(a,b[3])
    def self_pairs(node):
        if node[1] is None:
            self_pairs(node[2]);self_pairs(node[3]);compare(node[2],node[3])
    self_pairs(hierarchy)
    return dict(components=len(set(components.values())),exact_within_complex_pairs=pairs,
                cross_complex_union_unresolved=True)
