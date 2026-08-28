#!/usr/bin/env python3
"""Independent exact-rational oracle for the Projection Foundation Lab.

This program shares no solver or transfer implementation with the C++ lab.
It evaluates a small bilinear finite basis using ``fractions.Fraction`` and an
independently written Gauss-Jordan solve.  It checks the full consistent
projection, both published FMPM recurrences, their residual identity, and the
preregistered finite-order angular counterexample.  Passing it is not a
numerical mechanics validation or a promotion decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path
from typing import Iterable, Sequence

SEED = 260828
ScalarVector = list[Q]
Matrix = list[list[Q]]
Point = tuple[Q, Q]
Vector = tuple[Q, Q]

NODES: tuple[Point, ...] = (
    (Q(0), Q(0)),
    (Q(1), Q(0)),
    (Q(0), Q(1)),
    (Q(1), Q(1)),
)
PARTICLES: tuple[Point, ...] = (
    (Q(9, 10), Q(1, 5)),
    (Q(1, 10), Q(9, 10)),
    (Q(7, 10), Q(9, 10)),
    (Q(1, 5), Q(1, 5)),
)
MASSES: tuple[Q, ...] = (Q(1),) * 4


def zeros(rows: int, columns: int) -> Matrix:
    return [[Q(0) for _ in range(columns)] for _ in range(rows)]


def identity(size: int) -> Matrix:
    result = zeros(size, size)
    for index in range(size):
        result[index][index] = Q(1)
    return result


def transpose(matrix: Sequence[Sequence[Q]]) -> Matrix:
    return [list(column) for column in zip(*matrix, strict=True)]


def matmul(left: Sequence[Sequence[Q]], right: Sequence[Sequence[Q]]) -> Matrix:
    right_t = transpose(right)
    return [
        [sum((a * b for a, b in zip(row, column, strict=True)), Q(0))
         for column in right_t]
        for row in left
    ]


def matvec(matrix: Sequence[Sequence[Q]], vector: Sequence[Q]) -> ScalarVector:
    return [
        sum((entry * value for entry, value in zip(row, vector, strict=True)), Q(0))
        for row in matrix
    ]


def add(left: Sequence[Q], right: Sequence[Q]) -> ScalarVector:
    return [a + b for a, b in zip(left, right, strict=True)]


def subtract(left: Sequence[Q], right: Sequence[Q]) -> ScalarVector:
    return [a - b for a, b in zip(left, right, strict=True)]


def scale(factor: Q, vector: Sequence[Q]) -> ScalarVector:
    return [factor * value for value in vector]


def diagonal(values: Sequence[Q]) -> Matrix:
    result = zeros(len(values), len(values))
    for index, value in enumerate(values):
        result[index][index] = value
    return result


def inverse_diagonal(values: Sequence[Q]) -> Matrix:
    if any(value == 0 for value in values):
        raise ValueError("zero lumped mass")
    return diagonal([Q(1) / value for value in values])


def solve(matrix: Sequence[Sequence[Q]], rhs: Sequence[Q]) -> ScalarVector:
    """Exact Gauss-Jordan solve with deterministic first-nonzero pivoting."""

    size = len(matrix)
    if size == 0 or any(len(row) != size for row in matrix) or len(rhs) != size:
        raise ValueError("invalid square system")
    augmented = [list(row) + [rhs[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = next(
            (row for row in range(column, size) if augmented[row][column] != 0),
            None,
        )
        if pivot is None:
            raise ValueError("singular consistent mass matrix")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        pivot_value = augmented[column][column]
        augmented[column] = [value / pivot_value for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor != 0:
                augmented[row] = [
                    value - factor * pivot_entry
                    for value, pivot_entry in zip(
                        augmented[row], augmented[column], strict=True
                    )
                ]
    return [augmented[row][-1] for row in range(size)]


def inverse(matrix: Sequence[Sequence[Q]]) -> Matrix:
    size = len(matrix)
    columns = [
        solve(matrix, [Q(1) if row == column else Q(0) for row in range(size)])
        for column in range(size)
    ]
    return transpose(columns)


def matrix_one_norm(matrix: Sequence[Sequence[Q]]) -> Q:
    return max(
        sum((abs(value) for value in column), Q(0))
        for column in transpose(matrix)
    )


def bilinear_weights(point: Point) -> ScalarVector:
    x, y = point
    weights = [(1 - x) * (1 - y), x * (1 - y), (1 - x) * y, x * y]
    assert sum(weights, Q(0)) == 1
    recovered_x = sum((weight * node[0] for weight, node in zip(weights, NODES, strict=True)), Q(0))
    recovered_y = sum((weight * node[1] for weight, node in zip(weights, NODES, strict=True)), Q(0))
    assert (recovered_x, recovered_y) == point
    return weights


def sampling_matrix() -> Matrix:
    return [bilinear_weights(point) for point in PARTICLES]


def consistent_matrix(sampling: Matrix) -> Matrix:
    weighted = [
        [MASSES[p] * value for value in row]
        for p, row in enumerate(sampling)
    ]
    return matmul(transpose(sampling), weighted)


def rhs(sampling: Matrix, particle_values: Sequence[Q]) -> ScalarVector:
    weighted = [MASSES[p] * particle_values[p] for p in range(len(PARTICLES))]
    return matvec(transpose(sampling), weighted)


def lumped_mass(sampling: Matrix) -> ScalarVector:
    return [
        sum((MASSES[p] * sampling[p][node] for p in range(len(PARTICLES))), Q(0))
        for node in range(len(NODES))
    ]


def old_fmpm(matrix: Matrix, lumped: ScalarVector, q: ScalarVector, order: int) -> ScalarVector:
    """Nairn-Hammerquist 2021 Eq. (1), alternating binomial recurrence."""

    if order < 1:
        raise ValueError("FMPM order must be positive")
    d_inverse = inverse_diagonal(lumped)
    r_operator = matmul(d_inverse, matrix)
    term = scale(Q(order), matvec(d_inverse, q))
    result = list(term)
    sign = -1
    for ell in range(2, order + 1):
        term = scale(Q(order + 1 - ell, ell), matvec(r_operator, term))
        result = add(result, scale(Q(sign), term))
        sign *= -1
    return result


def revised_fmpm(
    matrix: Matrix, lumped: ScalarVector, q: ScalarVector, order: int
) -> tuple[ScalarVector, ScalarVector]:
    """Nairn 2026 Eqs. (5)-(6), returning v(k) and delta-v(k+1)."""

    if order < 1:
        raise ValueError("FMPM order must be positive")
    d_inverse = inverse_diagonal(lumped)
    r_operator = matmul(d_inverse, matrix)
    increment = matvec(d_inverse, q)
    result = list(increment)
    for _ell in range(2, order + 1):
        increment = subtract(increment, matvec(r_operator, increment))
        result = add(result, increment)
    next_increment = subtract(increment, matvec(r_operator, increment))
    return result, next_increment


def affine_value(point: Point) -> Vector:
    x, y = point
    return (Q(2, 7) + Q(3, 5) * x - Q(1, 4) * y,
            Q(-1, 3) + Q(2, 9) * x + Q(4, 7) * y)


def rigid_value(point: Point) -> Vector:
    x, y = point
    return (-y, x)


def momentum(values: Sequence[Vector]) -> Vector:
    return tuple(
        sum((MASSES[p] * values[p][component] for p in range(len(PARTICLES))), Q(0))
        for component in range(2)
    )  # type: ignore[return-value]


def angular(values: Sequence[Vector]) -> Q:
    return sum(
        (
            MASSES[p]
            * (PARTICLES[p][0] * values[p][1] - PARTICLES[p][1] * values[p][0])
            for p in range(len(PARTICLES))
        ),
        Q(0),
    )


def vector_projection(sampling: Matrix, nodal_components: Sequence[Sequence[Q]]) -> list[Vector]:
    components = [matvec(sampling, component) for component in nodal_components]
    return [
        (components[0][particle], components[1][particle])
        for particle in range(len(PARTICLES))
    ]


def qtext(value: Q) -> str:
    return f"{value.numerator}/{value.denominator}"


def witness(digest: "hashlib._Hash", values: Iterable[Q]) -> None:
    digest.update("|".join(qtext(value) for value in values).encode("ascii"))
    digest.update(b"\n")


def run() -> dict:
    sampling = sampling_matrix()
    matrix = consistent_matrix(sampling)
    lumped = lumped_mass(sampling)
    matrix_inverse = inverse(matrix)
    condition_one = matrix_one_norm(matrix) * matrix_one_norm(matrix_inverse)
    assert condition_one == Q(2514, 343)

    digest = hashlib.sha256()
    full_affine_checks = 0
    for component in range(2):
        particle_component = [affine_value(point)[component] for point in PARTICLES]
        nodal_component = [affine_value(node)[component] for node in NODES]
        component_rhs = rhs(sampling, particle_component)
        assert component_rhs == matvec(matrix, nodal_component)
        solved = solve(matrix, component_rhs)
        assert solved == nodal_component
        assert matvec(sampling, solved) == particle_component
        witness(digest, [*component_rhs, *solved])
        full_affine_checks += 3

    rigid_particles = [rigid_value(point) for point in PARTICLES]
    rigid_components = [
        [value[component] for value in rigid_particles] for component in range(2)
    ]
    full_grid = [solve(matrix, rhs(sampling, values)) for values in rigid_components]
    full_particles = vector_projection(sampling, full_grid)
    assert full_particles == rigid_particles
    assert momentum(full_particles) == momentum(rigid_particles)
    assert angular(full_particles) == angular(rigid_particles)

    expected_angular_delta = {
        1: Q(-921401, 1895040),
        2: Q(-91802668277, 359117660160),
        3: Q(-9282539024459489, 68054233070960640),
        4: Q(-953607378962630674973, 12896549383879325122560),
    }
    angular_deltas: dict[str, str] = {}
    linear_checks = 0
    recurrence_equivalence_checks = 0
    residual_identity_checks = 0
    pic_identity_checks = 0
    for order in range(1, 5):
        new_grid: list[ScalarVector] = []
        for particle_component in rigid_components:
            component_rhs = rhs(sampling, particle_component)
            revised, next_increment = revised_fmpm(
                matrix, lumped, component_rhs, order
            )
            original = old_fmpm(matrix, lumped, component_rhs, order)
            assert revised == original
            recurrence_equivalence_checks += 1
            residual = subtract(component_rhs, matvec(matrix, revised))
            assert residual == [
                lumped[index] * next_increment[index]
                for index in range(len(lumped))
            ]
            residual_identity_checks += 1
            if order == 1:
                assert revised == [
                    component_rhs[index] / lumped[index]
                    for index in range(len(lumped))
                ]
                pic_identity_checks += 1
            new_grid.append(revised)
            witness(digest, [Q(order), *revised, *residual])
        reconstructed = vector_projection(sampling, new_grid)
        assert momentum(reconstructed) == momentum(rigid_particles)
        linear_checks += 1
        delta = angular(reconstructed) - angular(rigid_particles)
        assert delta == expected_angular_delta[order]
        angular_deltas[str(order)] = qtext(delta)

    singular_rejections = 0
    singular_sampling = [sampling[0], sampling[0], sampling[0], sampling[0]]
    try:
        solve(consistent_matrix(singular_sampling), [Q(0)] * 4)
    except ValueError:
        singular_rejections += 1
    else:
        raise AssertionError("singular mass matrix was accepted")

    result = {
        "arithmetic": "fractions.Fraction exact rationals",
        "basis": "one bilinear unit cell with four deterministically ordered nodes",
        "condition_one_exact": qtext(condition_one),
        "condition_one_decimal": float(condition_one),
        "fields": ["general_affine", "rigid_rotation"],
        "fmpm_angular_deltas": angular_deltas,
        "fmpm_linear_momentum_exact_checks": linear_checks,
        "fmpm_pic_identity_component_checks": pic_identity_checks,
        "fmpm_recurrence_equivalence_component_checks": recurrence_equivalence_checks,
        "fmpm_residual_identity_component_checks": residual_identity_checks,
        "full_affine_rhs_solve_reconstruction_checks": full_affine_checks,
        "full_rigid_linear_angular_recovery_checks": 3,
        "implementation": "independent exact Gauss-Jordan and finite recurrences",
        "scope": "finite exact projection algebra only; not floating mechanics validation",
        "seed": SEED,
        "singular_matrix_rejections": singular_rejections,
        "witness_sha256": digest.hexdigest(),
    }
    payload = json.dumps(result, indent=2, sort_keys=True)
    result["result_sha256_before_hash_field"] = hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(run(), indent=2, sort_keys=True) + "\n"
    if args.verify is not None:
        expected = args.verify.read_text(encoding="utf-8")
        if rendered != expected:
            raise SystemExit(f"projection foundation oracle mismatch: {args.verify}")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
