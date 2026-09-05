"""Independent rational checks for affine rounding and branch receipts.

No mechanics propagation or candidate trajectories are imported here.
"""
from fractions import Fraction as Q


def check_rounding_definitions(definitions):
    for j, (difference, slack) in enumerate(definitions):
        assert slack > 0
        assert all(0 <= i < j for i, _ in difference.coefficients)
        # Independent corner supremum on the unit hypercube.
        upper = abs(difference.center)
        for _, coefficient in difference.coefficients:
            upper += abs(coefficient)
        assert slack >= upper, 'rounding slack is inward'


def check_children(parent, children, split_id):
    assert len(children) == 2, 'branch omitted'
    a, b = children
    lo, hi = parent.domains.get(split_id, (Q(-1), Q(1)))
    mid = (lo+hi)/2
    assert a.domains[split_id] == (lo, mid)
    assert b.domains[split_id] == (mid, hi)
    for child in children:
        assert child.state == parent.state, 'state altered during partition'
        for j in set(parent.domains) | set(child.domains):
            if j != split_id:
                assert child.domains.get(j, (-1, 1)) == parent.domains.get(j, (-1, 1))


def check_signed_sum(forms, weights, result):
    center = sum((a.center*w for a, w in zip(forms, weights)), Q())
    coefficients = {}
    for a, w in zip(forms, weights):
        for j, coefficient in a.coefficients:
            coefficients[j] = coefficients.get(j, Q()) + w*coefficient
    assert result.center == center
    assert dict(result.coefficients) == {j: c for j, c in coefficients.items() if c}


def check_no_full_budget_claim(report):
    # This implementation stage has no physical observer enclosure generator.
    assert report['physical_budgets_certified'] is False
    assert report['selected_precision'] is None
    assert report['promotion'] == 'NO_PROMOTION'
