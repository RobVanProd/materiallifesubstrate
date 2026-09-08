"""Pre-data full-facet connectivity checks; never uses object/body labels."""
from collections import defaultdict


def facet_components(cells):
    """Return maximal cell components, with a shared full facet as adjacency.

This checks topology only. Orientation, gaps and within-complex spatial overlap
remain separate obligations and cannot be inferred from graph connectivity.
"""
    facets=defaultdict(list);seen=set();parent={i:i for i in cells}
    def root(i):
        while i!=parent[i]:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for identifier,vertices in cells.items():
        key=tuple(sorted(vertices))
        if len(key)!=4 or len(set(key))!=4 or key in seen:
            raise ValueError('duplicate or degenerate cell incidence')
        seen.add(key)
        for opposite in range(4):
            face=tuple(key[j] for j in range(4) if j!=opposite)
            owners=facets[face];owners.append(identifier)
            if len(owners)>2:raise ValueError('nonmanifold full-facet incidence')
            if len(owners)==2:
                a,b=sorted((root(owners[0]),root(owners[1])));parent[b]=a
    result=defaultdict(list)
    for identifier in sorted(cells):result[root(identifier)].append(identifier)
    return tuple(sorted(tuple(ids) for ids in result.values()))
