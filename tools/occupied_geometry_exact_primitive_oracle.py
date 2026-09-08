"""Independent rational intersection-vertex/rank oracle (no candidate imports)."""
from fractions import Fraction as Q
import itertools


def det(m):
    return (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])
           -m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
           +m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))


def solve(m,b):
    d=det(m)
    if d==0:return None
    return tuple(det([[b[i] if j==axis else m[i][j] for j in range(3)] for i in range(3)])/d for axis in range(3))


def oracle(a,b):
    planes=[]
    for tet in (a,b):
        basis=[[tet[j+1][i]-tet[0][i] for j in range(3)] for i in range(3)]
        rows=[]
        for axis in range(3):
            row=solve([list(x) for x in zip(*basis)],[Q(i==axis) for i in range(3)])
            assert row is not None
            rows.append(row)
            planes.append((tuple(-x for x in row),-sum(row[i]*tet[0][i] for i in range(3))))
        n=tuple(sum(row[i] for row in rows) for i in range(3))
        planes.append((n,1+sum(n[i]*tet[0][i] for i in range(3))))
    vertices=set()
    for selected in itertools.combinations(planes,3):
        p=solve([list(n) for n,d in selected],[d for n,d in selected])
        if p is not None and all(sum(n[i]*p[i] for i in range(3))<=d for n,d in planes):vertices.add(p)
    if not vertices:return 'disjoint'
    origin=min(vertices);differences=[tuple(p[i]-origin[i] for i in range(3)) for p in vertices if p!=origin]
    for selected in itertools.combinations(differences,3):
        if det(selected)!=0:return 'positive_volume_overlap'
    return 'touching'
