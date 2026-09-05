"""Exact arithmetic and fail-closed controls for the tail certificate pilot."""
import sys
import unittest
from pathlib import Path
from fractions import Fraction as Q
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reference'))
import bounded_phase_tail_interval as v
import bounded_phase_tail_stage_one as audit


class ArithmeticTests(unittest.TestCase):
    def test_directed_independent_grid(self):
        # Independent integer floor/ceiling on a prescribed binade grid.
        for bits in (4, 8, 512):
            with patch.object(v, 'BITS', bits):
                for numerator in range(-40, 41):
                    for denominator in (3, 7, 201):
                        x = Q(numerator, denominator)
                        lo, hi = v.directed(x, False), v.directed(x, True)
                        self.assertLessEqual(lo, x)
                        self.assertGreaterEqual(hi, x)
                        if x:
                            magnitude = abs(x)
                            exponent = -20
                            while Q(2) ** (exponent + 1) <= magnitude:
                                exponent += 1
                            unit = Q(2) ** (exponent - bits + 1)
                            z = x / unit
                            lower = z.numerator // z.denominator
                            upper = -((-z.numerator) // z.denominator)
                            self.assertEqual(lo, lower * unit)
                            self.assertEqual(hi, upper * unit)

    def test_interval_operations(self):
        with patch.object(v, 'BITS', 8):
            a, b = v.Box(Q(-1, 3), Q(2, 7)), v.Box(Q(1, 201), Q(4, 3))
            for x in (a.lo, (a.lo+a.hi)/2, a.hi):
                for y in (b.lo, (b.lo+b.hi)/2, b.hi):
                    self.assertTrue((a+b).contains(x+y))
                    self.assertTrue((a-b).contains(x-y))
                    for c in (Q(-7, 3), Q(0), Q(1, 201)):
                        self.assertTrue(a.scale(c).contains(x*c))

    def test_rounding_counterexamples(self):
        self.assertEqual(audit.controls()[0]['excess'], '25/2')
        self.assertEqual(audit.controls()[1]['excess'], '4')

    def test_signed_sum_enclosures(self):
        for values in ((Q(1),Q(1,201),Q(-1)),
                       (Q(1),Q(1,1024),Q(-1)),
                       (Q(1,3),Q(-1,3),Q(1,201))):
            for bits in (192,256):
                observed, bound = Q(0), Q(0)
                for value in values:
                    observed, slack = audit.nearest(observed+value, bits)
                    bound += slack
                self.assertLessEqual(abs(observed-sum(values)), bound)

    def test_unjustified_zero_radius_restart_mutation(self):
        prior = v.Box(Q(1,3),Q(2,3))
        restarted = v.Box.point(Q(1,2))
        self.assertTrue(prior.contains(Q(2,3)))
        self.assertFalse(restarted.contains(Q(2,3)))

    def test_omitted_rounding_and_inward_mutations(self):
        x = Q(1,201)
        with patch.object(v, 'BITS', 8):
            sound = v.Box.point(x).scale(Q(1))
            self.assertTrue(sound.contains(x))
            omitted = v.Box.point(v.directed(x,False))
            inward = v.Box(v.directed(x,True),v.directed(x,True))
            self.assertFalse(omitted.contains(x))
            self.assertFalse(inward.contains(x))

    def test_uncertified_scalar_mutation(self):
        b=v.Box(Q(1)-Q(1,2**52),Q(1)+Q(1,2**52))
        with self.assertRaises(v.Inconclusive):
            v.float_cell(b)
        # Picking the center value would hide two genuinely possible outputs.
        self.assertNotEqual(float(b.lo),float(b.hi))
        self.assertEqual(v.float_cell(v.Box.point(Q(1,3))),float(Q(1,3)))

    def test_domain_crossing_mutation(self):
        from types import SimpleNamespace
        relation=SimpleNamespace(index=0)
        with patch.object(v.frozen,'reference_offset',return_value=(Q(1),Q(0),Q(0))):
            before=[v.Box.point(Q(1)),v.Box.point(0),v.Box.point(0)]
            after=[v.Box.point(Q(-1)),v.Box.point(0),v.Box.point(0)]
            v.safe_box(None,relation,before)
            v.safe_box(None,relation,after)
            with self.assertRaises(v.Inconclusive):
                v.safe_box(None,relation,[a.hull(b) for a,b in zip(before,after)])

    def test_mutated_directed_implementation_is_detected(self):
        original=v.directed
        with patch.object(v,'BITS',8):
            # Mutate an actual arithmetic primitive, not just an evidence flag.
            with patch.object(v,'directed',side_effect=lambda x,up: original(x,False)):
                self.assertFalse(v.Box.point(Q(1,201)).scale(Q(1)).contains(Q(1,201)))

    def test_nested_manifest_is_payload(self):
        import tempfile
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
        import bounded_phase_tail_bundle as bundle
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'nested').mkdir()
            (root/'nested'/'manifest.json').write_text('must be covered')
            (root/'manifest.json').write_text('root metadata')
            self.assertEqual(set(bundle.files(root)),{'nested/manifest.json'})

if __name__ == '__main__':
    unittest.main()
