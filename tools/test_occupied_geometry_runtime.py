"""Arithmetic and work-accounting controls, not extra scientific fixtures."""
import unittest
import gmpy2 as g
from occupied_geometry_runtime_wire import Work,WorkLimit
from occupied_geometry_c_volume import parameters,field_classification,box_volume
from occupied_geometry_a_volume import radii,classification


class RuntimeArithmetic(unittest.TestCase):
    def test_ball_union_classification(self):
        points=[(g.mpq(0),)*3];weights=[g.mpq(1)];cache=radii(weights,Work())
        self.assertEqual(classification(((g.mpq(0),g.mpq(0)),)*3,points,weights,cache,Work()),1)
        self.assertEqual(classification(((g.mpq(2),g.mpq(3)),)*3,points,weights,cache,Work()),0)
        self.assertEqual(classification(((g.mpq(-2),g.mpq(2)),)*3,points,weights,cache,Work()),2)

    def test_work_is_charged_before_execution(self):
        work=Work();work.charge('bulk',4194303)
        with self.assertRaises(WorkLimit):work.charge('children',2)
        self.assertEqual(work.used,4194303)
        self.assertEqual(work.pending['requested'],2)

    def test_exact_box_volume(self):
        box=((g.mpq(-1),g.mpq(1)),(g.mpq(1,3),g.mpq(2,3)),(g.mpq(0),g.mpq(3)))
        self.assertEqual(box_volume(box),2)

    def test_gaussian_point_and_remote_box(self):
        params=parameters(g.mpq(1),g.mpq(1,10000))
        origin=(g.mpq(0),)*3
        point_box=((g.mpq(0),g.mpq(0)),)*3
        far_box=((g.mpq(10),g.mpq(11)),)*3
        self.assertEqual(field_classification(point_box,[origin],[g.mpq(1)],params,Work()),1)
        self.assertEqual(field_classification(far_box,[origin],[g.mpq(1)],params,Work()),0)
        containing=((g.mpq(-10),g.mpq(10)),)*3
        self.assertEqual(field_classification(containing,[origin],[g.mpq(1)],params,Work()),2)


if __name__=='__main__':unittest.main()
