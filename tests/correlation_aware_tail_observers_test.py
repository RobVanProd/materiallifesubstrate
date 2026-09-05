import sys
import unittest
from fractions import Fraction as Q
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'reference'))
import correlation_aware_tail_observers as o


class ObserverTests(unittest.TestCase):
    def test_product_corner_and_interior_exact_values(self):
        a = o.Affine.make(Q(1, 3), {0: Q(1, 201), 1: Q(-2, 7)})
        b = o.Affine.make(Q(-5, 7), {0: Q(3, 5), 1: Q(7, 11)})
        envelope = o.product(a, b)
        for x in (Q(-1), Q(-1, 2), Q(), Q(1, 2), Q(1)):
            for y in (Q(-1), Q(), Q(1)):
                point = {0: x, 1: y}
                wanted = a.value(point)*b.value(point)
                self.assertLessEqual(abs(wanted-envelope.linear.value(point)), envelope.radius)
                self.assertTrue(envelope.bounds({}).contains(wanted))

    def test_signed_slope_shared_noise_cancels(self):
        common = o.Envelope(o.Affine.make(5, {0: Q(1, 201)}))
        observed = o.slope([common]*3, [Q(0), Q(1), Q(2)])
        self.assertEqual(observed.bounds({}), o.Box.point(0))

    def test_slope_bounds_actual_signed_quadratic_values(self):
        forms = [o.Affine.make(i, {0: Q(i+1, 201)}) for i in range(3)]
        values = [o.product(a, a) for a in forms]
        envelope = o.slope(values, [Q(), Q(1), Q(2)])
        for eta in (Q(-1), Q(), Q(1)):
            actual = (forms[2].value({0: eta})**2-forms[0].value({0: eta})**2)/2
            self.assertTrue(envelope.bounds({}).contains(actual))

    def test_zero_quadratic_remainder_mutation(self):
        a = o.Affine.make(0, {0: Q(1, 201)})
        correct = o.product(a, a)
        inward = o.Envelope(correct.linear)
        wanted = Q(1, 201)**2
        self.assertTrue(correct.bounds({}).contains(wanted))
        self.assertFalse(inward.bounds({}).contains(wanted))

    def test_kinetic_and_angular_exact_fixture(self):
        x = [o.Affine.make(1, {0: Q(1, 3)}), o.Affine.make(2), o.Affine.make(3)]
        p = [o.Affine.make(-1), o.Affine.make(5, {0: Q(2, 7)}), o.Affine.make(7)]
        state = {1: (x, p)}
        kinetic = o.kinetic(state, {1: 2}, Q(1), Q(1))
        angular = o.angular(state, Q(1), Q(1))
        for eta in (Q(-1), Q(), Q(1)):
            xx, pp = [[a.value({0: eta}) for a in vector] for vector in (x, p)]
            self.assertTrue(kinetic.bounds({}).contains(sum((v*v for v in pp), Q())/4))
            for axis, j, k in ((0, 1, 2), (1, 2, 0), (2, 0, 1)):
                self.assertTrue(angular[axis].bounds({}).contains(xx[j]*pp[k]-xx[k]*pp[j]))


if __name__ == '__main__':
    unittest.main()
