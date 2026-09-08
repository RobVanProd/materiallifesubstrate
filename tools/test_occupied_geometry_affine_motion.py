import unittest
import gmpy2 as g
from occupied_geometry_runtime_wire import Work
from occupied_geometry_affine_motion import certify,position,determinant_interval


class Motion(unittest.TestCase):
    def test_translation_and_linear_collapse(self):
        vertices={i:tuple(map(g.mpq,p)) for i,p in enumerate(((0,0,0),(1,0,0),(0,1,0),(0,0,1)),1)}
        cells={1:(1,2,3,4)};components={1:1}
        for collapse in (False,True):
            velocity={i:(-p[0]/4 if collapse else g.mpq(2),g.mpq(0),g.mpq(0)) for i,p in vertices.items()}
            c=certify(vertices,cells,components,velocity,Work())[1]
            low,high=determinant_interval(c,g.mpq(0),g.mpq(2),Work())
            self.assertEqual((low,high),(g.mpq(1,2),g.mpq(1)) if collapse else (g.mpq(1),g.mpq(1)))
            self.assertEqual(position(c,vertices[2],g.mpq(2),Work())[0],g.mpq(1,2) if collapse else g.mpq(5))
            if collapse:self.assertEqual(determinant_interval(c,g.mpq(4),g.mpq(4),Work()),(0,0))


if __name__=='__main__':unittest.main()
