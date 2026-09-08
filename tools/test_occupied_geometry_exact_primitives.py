"""Exact independent controls for predicates, not new scientific fixtures."""
from fractions import Fraction as Q
import itertools
import unittest
import gmpy2 as g
from occupied_geometry_runtime_wire import Work
from occupied_geometry_exact_primitives import tetrahedron_intersection,closest_triangle,tetrahedron_membership
from occupied_geometry_exact_primitive_oracle import oracle


class ExactPredicates(unittest.TestCase):
    def test_intersection_against_independent_vertex_enumeration(self):
        base=[tuple(map(Q,p)) for p in ((0,0,0),(1,0,0),(0,1,0),(0,0,1))]
        cases=0
        for shift in itertools.product((Q(-1),Q(0),Q(1,3),Q(1)),repeat=3):
            target=[tuple(p[i]+shift[i] for i in range(3)) for p in base]
            # Shear preserves rank and also exercises non-axis-aligned faces.
            for shear in (False,True):
                def transform(points):return [(p[0]+p[1]/3,p[1]+p[2]/5,p[2]) for p in points] if shear else points
                a,b=transform(base),transform(target)
                actual=tetrahedron_intersection(a,b,Work())
                self.assertEqual(actual,oracle(a,b));self.assertEqual(actual,tetrahedron_intersection(b,a,Work()))
                cases+=1
        self.assertEqual(cases,128)

    def test_triangle_projection(self):
        tri=[tuple(map(g.mpq,p)) for p in ((0,0,0),(1,0,0),(0,1,0))]
        for point,want in (((g.mpq(1,4),g.mpq(1,4),g.mpq(2)),(g.mpq(1,4),g.mpq(1,4),g.mpq(0))),
                           ((g.mpq(1),g.mpq(1),g.mpq(0)),(g.mpq(1,2),g.mpq(1,2),g.mpq(0))),
                           ((g.mpq(-1),g.mpq(-1),g.mpq(0)),(g.mpq(0),)*3)):
            distance,found=closest_triangle(tri,point,Work());self.assertEqual(found,want)
            self.assertEqual(distance,sum((x-y)**2 for x,y in zip(point,want)))

    def test_strict_contact_distinction(self):
        tet=[tuple(map(g.mpq,p)) for p in ((0,0,0),(1,0,0),(0,1,0),(0,0,1))]
        self.assertEqual(tetrahedron_membership(tet,(g.mpq(0),)*3,Work()),{'closed':True,'strict':False})
        self.assertEqual(tetrahedron_membership(tet,(g.mpq(1,4),)*3,Work()),{'closed':True,'strict':True})


if __name__=='__main__':unittest.main()
