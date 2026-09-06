import sys
import unittest
from pathlib import Path
from fractions import Fraction as Q
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'reference'))
import correlation_aware_tail as v
import correlation_aware_affine_image_check as check


class ImageTests(unittest.TestCase):
    def fixture(self):
        ar = v.Arithmetic()
        a = ar.round(v.Affine.make(Q(1, 201)))
        state = {1: ([a, v.Affine.make(2), v.Affine.make(3)], [v.Affine.make(1)]*3),
                 2: ([v.Affine.make(4), v.Affine.make(5), v.Affine.make(6)], [v.Affine.make(-1)]*3)}
        relation = SimpleNamespace(first_id=1, second_id=2, index=0)
        model = SimpleNamespace(relations=[], masses_raw={1: 2, 2: 3})
        return ar, state, relation, model

    def test_conditioned_kick_and_orientation_mutation(self):
        ar, state, relation, model = self.fixture()
        evaluated = [(relation, v.offset(state, relation), Q(1), Q(1, 7))]
        first = len(ar.definitions)
        with patch.object(v, 'evaluate', return_value=evaluated):
            out = v.kick(model, v.Cell(state, {}), 2, ar)
        check.kick(state, out.state, evaluated, 2, v.frozen.LQ, v.frozen.PQ,
                   v.frozen.TQ, ar.definitions, first)
        out.state[1][1][0] = out.state[1][1][0]+v.Affine.make(1)
        with self.assertRaises(AssertionError):
            check.kick(state, out.state, evaluated, 2, v.frozen.LQ, v.frozen.PQ,
                       v.frozen.TQ, ar.definitions, first)

    def test_drift_and_wrong_mass_mutation(self):
        ar, state, relation, model = self.fixture()
        first = len(ar.definitions)
        out = v.drift(model, v.Cell(state, {}), 2, ar)
        check.drift(state, out.state, 2, model.masses_raw, ar.definitions, first)
        with self.assertRaises(AssertionError):
            check.drift(state, out.state, 2, {1: 7, 2: 3}, ar.definitions, first)


if __name__ == '__main__':
    unittest.main()
