"""Exact, disposable per-connectivity-component affine motion certificates."""
import gmpy2 as g
from occupied_geometry_exact_primitives import determinant,dot,sub


def solve(matrix,rhs):
    d=determinant(*matrix);assert d!=0
    return tuple(determinant(*[tuple(rhs[i] if j==axis else matrix[i][j] for j in range(3)) for i in range(3)])/d for axis in range(3))


def certify(vertices,cells,components,velocities,work):
    result={}
    for ident in sorted(cells):
        root=components[ident]
        if root in result:continue
        work.charge('affine_motion_certificate')
        ids=cells[ident];x=[vertices[i] for i in ids]
        v=[velocities.get(i,(g.mpq(0),)*3) for i in ids]
        matrix=[sub(x[j],x[0]) for j in (1,2,3)]
        jacobian=tuple(solve(matrix,tuple(v[j][axis]-v[0][axis] for j in (1,2,3))) for axis in range(3))
        shift=tuple(v[0][axis]-dot(jacobian[axis],x[0]) for axis in range(3))
        result[root]=dict(jacobian=jacobian,shift=shift,checked=set())
    for ident,ids in cells.items():
        row=result[components[ident]]
        for i in ids:
            if i in row['checked']:continue
            work.charge('motion_vertex_cache_entry');work.charge('affine_velocity_identity')
            assert tuple(dot(axis,vertices[i])+shift for axis,shift in zip(row['jacobian'],row['shift']))==velocities.get(i,(g.mpq(0),)*3)
            row['checked'].add(i)
    for row in result.values():row['checked_vertices']=len(row.pop('checked'))
    return result


def matrix_at(certificate,time):
    return tuple(tuple(g.mpq(i==j)+time*certificate['jacobian'][i][j] for j in range(3)) for i in range(3))


def position(certificate,point,time,work):
    work.charge('affine_point_image')
    return tuple(point[i]+time*(dot(certificate['jacobian'][i],point)+certificate['shift'][i]) for i in range(3))


def determinant_interval(certificate,left,right,work):
    """Exact Bernstein enclosure of cubic det(I+tJ), with no sampled minimum.

    Positive lower bound certifies the whole segment. A straddling enclosure
    remains inconclusive; it is not a proved inversion or permission to clamp.
    """
    assert left<=right;work.charge('affine_determinant_interval')
    values=[determinant(*matrix_at(certificate,left+(right-left)*g.mpq(j,3))) for j in range(4)]
    b0,b3=values[0],values[3]
    # Solve the exact cubic Bernstein interpolation equations at 1/3,2/3.
    a=27*values[1]-8*b0-b3;b=27*values[2]-b0-8*b3
    b1=(2*a-b)/18;b2=(2*b-a)/18
    return min(b0,b1,b2,b3),max(b0,b1,b2,b3)
