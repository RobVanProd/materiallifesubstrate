"""Independent exact fixtures for the noncausal affine certificate core."""
import sys
import unittest
from fractions import Fraction as Q
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'reference'))
import correlation_aware_tail as v
import correlation_aware_tail_check as independent


class AffineTests(unittest.TestCase):
    def test_shared_subtraction(self):
        a = v.Affine.make(7, {0: Q(1, 3), 1: Q(2, 7)})
        b = v.Affine.make(9, {0: Q(1, 3), 1: Q(2, 7)})
        self.assertEqual(b-a, v.Affine.make(2))
        independent = b.bounds({}) - a.bounds({})
        self.assertLess(independent.lo, 2)
        self.assertGreater(independent.hi, 2)

    def test_affine_image_exact_enumeration(self):
        a = v.Affine.make(Q(2, 3), {0: Q(-7, 5), 1: Q(1, 11)})
        b = v.Affine.make(-4, {0: Q(3), 1: Q(1, 13)})
        result = a.scale(Q(2, 9)) + b.scale(Q(-5, 17))
        for x in (-1, 0, 1):
            for y in (-1, 0, 1):
                assignment = {0: Q(x), 1: Q(y)}
                wanted = Q(2, 9)*a.value(assignment)-Q(5, 17)*b.value(assignment)
                self.assertEqual(result.value(assignment), wanted)
                self.assertTrue(result.bounds({}).contains(wanted))

    def test_rounding_joint_witness(self):
        with patch.object(v.control, 'BITS', 8):
            ar = v.Arithmetic()
            a = ar.round(v.Affine.make(Q(1, 201)))
            b = ar.round(a.scale(Q(4, 7))+v.Affine.make(Q(1, 3)))
            witness = ar.witness()
            self.assertEqual(a.value(witness), Q(1, 201))
            self.assertEqual(b.value(witness), Q(4, 1407)+Q(1, 3))
            self.assertEqual(ar.round(v.Affine.make(Q(-1, 201))), -a)
            self.assertEqual(ar.round(a-a), v.Affine.make(0))

    def test_rounding_uniform_in_old_noise(self):
        with patch.object(v.control, 'BITS', 8):
            ar = v.Arithmetic()
            ar.round(v.Affine.make(Q(1, 201)))  # symbol 0
            original = v.Affine.make(Q(1, 3), {0: Q(7, 201)})
            out = ar.round(original)
            difference, allowance = ar.definitions[-1]
            for old in (Q(-1), Q(-1, 2), Q(), Q(1, 2), Q(1)):
                new = difference.value({0: old}) / allowance
                self.assertLessEqual(abs(new), 1)
                self.assertEqual(out.value({0: old, 1: new}), original.value({0: old}))

    def test_split_union_and_stable_tie(self):
        form = v.Affine.make(1, {0: Q(1, 7), 1: Q(-1, 7)})
        cell = v.Cell({1: ([form], [])}, {})
        children, receipt = v.split(cell, v.Ambiguous(form, 0, 0))
        self.assertEqual(receipt, (0, -1, 0, 1))
        self.assertIs(children[0].state, cell.state)
        self.assertIs(children[1].state, cell.state)
        for value in (Q(-1), Q(-1, 2), Q(), Q(1, 2), Q(1)):
            self.assertTrue(any(c.domains[0][0] <= value <= c.domains[0][1] for c in children))
        # A non-nominal child cannot be pruned without losing coverage.
        self.assertFalse(children[0].domains[0][0] <= Q(1) <= children[0].domains[0][1])

    def test_center_independence(self):
        # Recenter by adding the deterministic offset explicitly; never reset.
        a = v.Affine.make(Q(1, 3), {0: Q(1, 201)})
        for replacement in (Q(0), Q(5), Q(-4, 11)):
            nominal = v.Affine.make(replacement)
            residual = a - nominal
            self.assertEqual(nominal + residual, a)

    def test_signed_slope_dependency(self):
        a = v.Affine.make(0, {0: Q(1)})
        signed = a.scale(-1)+a.scale(1)
        self.assertEqual(signed.bounds({}), v.control.Box.point(0))
        independent_absolute = abs(-1)+abs(1)
        self.assertEqual(independent_absolute, 2)

    def test_binary64_tie_cell(self):
        half_ulp = Q(1, 2**53)
        self.assertEqual(v.control.float_cell(v.control.Box(Q(1), Q(1)+half_ulp)), 1.0)
        with self.assertRaises(v.control.Inconclusive):
            v.control.float_cell(v.control.Box(Q(1), Q(1)+half_ulp+Q(1, 2**100)))

    def test_dropped_rounding_symbol_mutation(self):
        with patch.object(v.control, 'BITS', 8):
            ar = v.Arithmetic()
            good = ar.round(v.Affine.make(Q(1, 201)))
            bad = v.Affine.make(good.center)
            self.assertNotEqual(bad.value(ar.witness()), Q(1, 201))

    def test_inward_allowance_mutation(self):
        with patch.object(v.control, 'BITS', 8):
            ar = v.Arithmetic()
            ar.round(v.Affine.make(Q(1, 201)))
            difference, allowance = ar.definitions[0]
            ar.definitions[0] = (difference, allowance/4)
            with self.assertRaises(AssertionError):
                ar.witness()

    def test_independent_rounding_checker_mutation(self):
        with patch.object(v.control, 'BITS', 8):
            ar = v.Arithmetic()
            ar.round(v.Affine.make(Q(1, 201)))
            independent.check_rounding_definitions(ar.definitions)
            difference, slack = ar.definitions[0]
            with self.assertRaises(AssertionError):
                independent.check_rounding_definitions([(difference, slack/2)])

    def test_pruned_child_and_altered_force_cell_mutations(self):
        form = v.Affine.make(0, {0: Q(1)})
        parent = v.Cell({1: ([form], [])}, {})
        children, _ = v.split(parent, v.Ambiguous(form, 0, 0))
        independent.check_children(parent, children, 0)
        with self.assertRaises(AssertionError):
            independent.check_children(parent, children[:1], 0)
        children[1].state = {1: ([v.Affine.make(5)], [])}
        with self.assertRaises(AssertionError):
            independent.check_children(parent, children, 0)

    def test_actual_branch_engine_keeps_both_children(self):
        form = v.Affine.make(0, {0: Q(1)})
        parent = v.Cell({1: ([form], [])}, {})
        def operation(model, cell, dt, arithmetic):
            interval = form.bounds(cell.domains)
            if interval.lo < 0 < interval.hi:
                raise v.Ambiguous(form, 0, 0)
            return cell
        counts = dict(cumulative_cells=1, max_live_cells=1, splits=[])
        result = v.advance(None, [parent], 1, operation, v.Arithmetic(), True,
                           counts, v.time.monotonic())
        independent.check_children(parent, result, 0)
        self.assertEqual(counts['cumulative_cells'], 3)

    def test_signed_slope_mutation_independent(self):
        form = v.Affine.make(0, {0: Q(1)})
        correct = form.scale(-1)+form
        independent.check_signed_sum([form, form], [-1, 1], correct)
        with self.assertRaises(AssertionError):
            independent.check_signed_sum([form, form], [-1, 1], form.scale(2))

    def test_checkpoint_radius_reset_mutation(self):
        form = v.Affine.make(5, {0: Q(1, 201)})
        reset = v.Affine.make(5)
        self.assertNotEqual(form.value({0: Q(1)}), reset.value({}))

    def test_resource_exhaustion_cannot_select_precision(self):
        report = dict(physical_budgets_certified=False, selected_precision=None,
                      promotion='NO_PROMOTION')
        independent.check_no_full_budget_claim(report)
        report['physical_budgets_certified'] = True
        report['selected_precision'] = 96
        with self.assertRaises(AssertionError):
            independent.check_no_full_budget_claim(report)


if __name__ == '__main__':
    unittest.main()
