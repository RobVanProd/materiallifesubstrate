"""Exact clipping controls, not additional scientific geometry fixtures."""
import unittest
import gmpy2 as g
from occupied_geometry_runtime_wire import Work
from occupied_geometry_convex_union import intersection,volume,exposed


def box(lo,hi):
    faces=[];planes=[]
    for j in range(3):
        others=[i for i in range(3) if i!=j]
        for side in (0,1):
            n=tuple(g.mpq((1 if side else -1) if i==j else 0) for i in range(3))
            planes.append((n,g.mpq(hi[j] if side else -lo[j])))
            p=[]
            for a,b in ((0,0),(1,0),(1,1),(0,1)):
                v=list(lo);v[j]=(lo,hi)[side][j];v[others[0]]=(lo,hi)[a][others[0]];v[others[1]]=(lo,hi)[b][others[1]]
                p.append(tuple(map(g.mpq,v)))
            # The handedness of the selected coordinate-plane axes is known.
            if (j==1)==bool(side):p.reverse()
            faces.append(p)
    return faces,planes


class ConvexUnion(unittest.TestCase):
    def test_union_volume_not_sum_and_buried_faces(self):
        a,pa=box((0,0,0),(1,1,1))
        self.assertEqual(volume(a,Work()),1)
        for shift in (g.mpq(0),g.mpq(1,2),g.mpq(1),g.mpq(2)):
            b,pb=box((shift,0,0),(shift+1,1,1))
            common=intersection(a,pb,Work());v=volume(common,Work())
            self.assertEqual(v,max(g.mpq(0),1-shift))
            self.assertEqual(volume(a,Work())+volume(b,Work())-v,2-max(g.mpq(0),1-shift))
            surface=exposed(a,pb,Work())+exposed(b,pa,Work())
            if shift==1:
                self.assertFalse(any(all(p[0]==1 for p in face) for face in surface))
            if shift==g.mpq(1,2):
                self.assertFalse(any(all(p[0] in (shift,g.mpq(1)) and p[0]==face[0][0] for p in face) for face in surface))


if __name__=='__main__':unittest.main()
