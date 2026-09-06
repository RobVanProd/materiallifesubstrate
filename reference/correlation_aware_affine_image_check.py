"""Independent sparse-row verification of conditioned kick/drift images."""
from fractions import Fraction as Q


def normal(center, coefficients):
    return center, {j: value for j, value in coefficients.items() if value}


def expanded(form, definitions, first_new):
    center, coefficients = form.center, dict(form.coefficients)
    for j in range(len(definitions)-1, first_new-1, -1):
        factor = coefficients.pop(j, Q())
        if not factor:
            continue
        difference, slack = definitions[j]
        factor /= slack
        center += factor*difference.center
        for old, value in difference.coefficients:
            coefficients[old] = coefficients.get(old, Q())+factor*value
    return normal(center, coefficients)


def row_image(state, row):
    center, coefficients = Q(), {}
    for (identifier, vector, axis), factor in row.items():
        form = state[identifier][vector][axis]
        center += factor*form.center
        for j, value in form.coefficients:
            coefficients[j] = coefficients.get(j, Q())+factor*value
    return normal(center, coefficients)


def identity_rows(state):
    return {(i, vector, axis): {(i, vector, axis): Q(1)} for i in state
            for vector in range(2) for axis in range(3)}


def check_rows(before, after, rows, definitions, first_new):
    assert set(before) == set(after)
    for key, row in rows.items():
        identifier, vector, axis = key
        assert expanded(after[identifier][vector][axis], definitions, first_new) == row_image(before, row), 'affine stage image mismatch'


def kick(before, after, evaluated, dt, Lq, Pq, Tq, definitions, first_new):
    rows = identity_rows(before)
    for relation, _, length, conjugate in evaluated:
        alpha = Q(dt)*Tq*Lq*conjugate/(Pq*length)
        for axis in range(3):
            for target, sign in ((relation.first_id, 1), (relation.second_id, -1)):
                row = rows[(target, 1, axis)]
                for source, orientation in ((relation.first_id, -1), (relation.second_id, 1)):
                    key = (source, 0, axis)
                    row[key] = row.get(key, Q()) + sign*orientation*alpha
    check_rows(before, after, rows, definitions, first_new)


def drift(before, after, dt, masses, definitions, first_new):
    rows = identity_rows(before)
    for identifier in before:
        for axis in range(3):
            rows[(identifier, 0, axis)][(identifier, 1, axis)] = Q(dt, masses[identifier])
    check_rows(before, after, rows, definitions, first_new)
