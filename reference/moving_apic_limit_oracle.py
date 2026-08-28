#!/usr/bin/env python3
"""Exact finite-sum oracle for the moving-APIC global-affine limit.

This file independently evaluates Jiang--Schroeder--Teran (JCP 2017)
Equation (38); it does not import production code or the earlier affine oracle.
For old offsets ``r_i = x_i^n - x_p^n``, new offsets
``s_i = x_i^{n+1} - x_p^{n+1}``, and force-free grid velocities ``u_i``, the
complete update evaluated here is

    B_next = 1/2 sum_i w_i [
        u_i (r_i + s_i)^T + (r_i - s_i) u_i^T].

Under the checked finite-sum assumptions

    sum_i w_i = 1,
    sum_i w_i r_i = 0,
    D_old = sum_i w_i r_i r_i^T,
    u_i = A x_i + b,
    x_i_next = x_i + dt u_i,

the direct sum reduces to ``B_next = A D_old``.  The reduction is tested, not
assumed.  Only under the additional explicit laboratory assumption
``D_next = D_old`` does ``C_next = B_next D_next^-1 = A`` follow.  The exact
force-free convected gradient is instead ``A (I + dt A)^-1``.  Their
discrepancy is checked without floating point, including nonsymmetric ``A``
and anisotropic, noncommuting ``D_old`` cases.

In particular, writing ``M = I + dt A``, affine reproduction gives
``s_i = M r_i`` and ``u_i = v_p + A r_i``.  Partition of unity and the zero
first moment remove every ``v_p`` term, so the two complete Eq. (38) sums are

    sum_i w_i u_i (r_i + s_i)^T = A D_old (I + M)^T,
    sum_i w_i (r_i - s_i) u_i^T = (I - M) D_old A^T.

Their ``dt A D_old A^T`` terms cancel even when ``A`` is nonsymmetric and
``D_old`` is anisotropic, leaving ``2 B_next = 2 A D_old``.

Passing this oracle establishes finite rational identities only.  It does not
validate a numerical transfer implementation or promote a mechanics method.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction as Q
from pathlib import Path
from random import Random
from typing import Iterable, Sequence, Tuple

SEED = 260828

Vec = Tuple[Q, Q, Q]
Mat = Tuple[Vec, Vec, Vec]
WeightedOffset = Tuple[Q, Vec]

ZERO_V: Vec = (Q(0), Q(0), Q(0))
ZERO_M: Mat = (ZERO_V, ZERO_V, ZERO_V)
IDENTITY: Mat = (
    (Q(1), Q(0), Q(0)),
    (Q(0), Q(1), Q(0)),
    (Q(0), Q(0), Q(1)),
)


def vadd(left: Vec, right: Vec) -> Vec:
    return tuple(left[i] + right[i] for i in range(3))  # type: ignore[return-value]


def vsub(left: Vec, right: Vec) -> Vec:
    return tuple(left[i] - right[i] for i in range(3))  # type: ignore[return-value]


def vscale(factor: Q, value: Vec) -> Vec:
    return tuple(factor * value[i] for i in range(3))  # type: ignore[return-value]


def dot(left: Vec, right: Vec) -> Q:
    return sum((left[i] * right[i] for i in range(3)), Q(0))


def mvec(matrix: Mat, value: Vec) -> Vec:
    return tuple(dot(matrix[row], value) for row in range(3))  # type: ignore[return-value]


def madd(left: Mat, right: Mat) -> Mat:
    return tuple(vadd(left[row], right[row]) for row in range(3))  # type: ignore[return-value]


def msub(left: Mat, right: Mat) -> Mat:
    return tuple(vsub(left[row], right[row]) for row in range(3))  # type: ignore[return-value]


def mscale(factor: Q, matrix: Mat) -> Mat:
    return tuple(vscale(factor, matrix[row]) for row in range(3))  # type: ignore[return-value]


def transpose(matrix: Mat) -> Mat:
    return tuple(
        tuple(matrix[row][column] for row in range(3))
        for column in range(3)
    )  # type: ignore[return-value]


def mmul(left: Mat, right: Mat) -> Mat:
    right_t = transpose(right)
    return tuple(
        tuple(dot(left[row], right_t[column]) for column in range(3))
        for row in range(3)
    )  # type: ignore[return-value]


def outer(left: Vec, right: Vec) -> Mat:
    return tuple(
        tuple(left[row] * right[column] for column in range(3))
        for row in range(3)
    )  # type: ignore[return-value]


def determinant(matrix: Mat) -> Q:
    return (
        matrix[0][0]
        * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1]
        * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2]
        * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def inverse(matrix: Mat, label: str) -> Mat:
    determinant_value = determinant(matrix)
    if determinant_value == 0:
        raise ValueError(f"{label} is singular")
    adjugate: Mat = (
        (
            matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1],
            matrix[0][2] * matrix[2][1] - matrix[0][1] * matrix[2][2],
            matrix[0][1] * matrix[1][2] - matrix[0][2] * matrix[1][1],
        ),
        (
            matrix[1][2] * matrix[2][0] - matrix[1][0] * matrix[2][2],
            matrix[0][0] * matrix[2][2] - matrix[0][2] * matrix[2][0],
            matrix[0][2] * matrix[1][0] - matrix[0][0] * matrix[1][2],
        ),
        (
            matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0],
            matrix[0][1] * matrix[2][0] - matrix[0][0] * matrix[2][1],
            matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0],
        ),
    )
    result = mscale(Q(1) / determinant_value, adjugate)
    assert mmul(matrix, result) == IDENTITY
    assert mmul(result, matrix) == IDENTITY
    return result


@dataclass(frozen=True)
class AffineField:
    gradient: Mat
    offset: Vec


@dataclass(frozen=True)
class Eq38Result:
    particle_position: Vec
    particle_velocity: Vec
    b_next: Mat


def velocity(field: AffineField, position: Vec) -> Vec:
    return vadd(mvec(field.gradient, position), field.offset)


def moment_matrix(stencil: Sequence[WeightedOffset]) -> Mat:
    result = ZERO_M
    for weight, offset in stencil:
        result = madd(result, mscale(weight, outer(offset, offset)))
    return result


def check_stencil(stencil: Sequence[WeightedOffset]) -> Mat:
    assert stencil
    assert all(weight >= 0 for weight, _offset in stencil)
    assert sum((weight for weight, _offset in stencil), Q(0)) == 1
    first_moment = ZERO_V
    for weight, offset in stencil:
        first_moment = vadd(first_moment, vscale(weight, offset))
    assert first_moment == ZERO_V
    result = moment_matrix(stencil)
    inverse(result, "D_old")
    return result


def is_centrally_symmetric(stencil: Sequence[WeightedOffset]) -> bool:
    """Check weighted support symmetry about the particle at the origin."""

    weight_by_offset: dict[Vec, Q] = {}
    for weight, offset in stencil:
        weight_by_offset[offset] = weight_by_offset.get(offset, Q(0)) + weight
    return all(
        weight == weight_by_offset.get(vscale(Q(-1), offset), Q(0))
        for offset, weight in weight_by_offset.items()
    )


def equation_38_force_free(
    field: AffineField,
    particle_position: Vec,
    dt: Q,
    stencil: Sequence[WeightedOffset],
) -> Eq38Result:
    """Evaluate JST Equation (38) as written, without using its reduction."""

    old_grid_positions: list[Vec] = []
    new_grid_positions: list[Vec] = []
    grid_velocities: list[Vec] = []
    for _weight, old_offset in stencil:
        old_grid_position = vadd(particle_position, old_offset)
        grid_velocity = velocity(field, old_grid_position)
        new_grid_position = vadd(
            old_grid_position, vscale(dt, grid_velocity)
        )
        old_grid_positions.append(old_grid_position)
        new_grid_positions.append(new_grid_position)
        grid_velocities.append(grid_velocity)

    # Equations (39) and (37), evaluated from the same old weights.
    particle_position_next = ZERO_V
    particle_velocity_next = ZERO_V
    for (weight, _old_offset), new_grid_position, grid_velocity in zip(
        stencil, new_grid_positions, grid_velocities, strict=True
    ):
        particle_position_next = vadd(
            particle_position_next, vscale(weight, new_grid_position)
        )
        particle_velocity_next = vadd(
            particle_velocity_next, vscale(weight, grid_velocity)
        )

    # Complete Equation (38).  Keeping both outer-product terms here is an
    # intentional independence boundary: B_next = A D_old is not substituted.
    b_next = ZERO_M
    for (
        (weight, _old_offset),
        old_grid_position,
        new_grid_position,
        grid_velocity,
    ) in zip(
        stencil,
        old_grid_positions,
        new_grid_positions,
        grid_velocities,
        strict=True,
    ):
        old_relative = vsub(old_grid_position, particle_position)
        new_relative = vsub(new_grid_position, particle_position_next)
        first = outer(
            grid_velocity, vadd(old_relative, new_relative)
        )
        second = outer(
            vsub(old_relative, new_relative), grid_velocity
        )
        b_next = madd(
            b_next, mscale(weight / 2, madd(first, second))
        )

    return Eq38Result(
        particle_position_next, particle_velocity_next, b_next
    )


def convect(field: AffineField, dt: Q) -> AffineField:
    map_matrix = madd(IDENTITY, mscale(dt, field.gradient))
    map_inverse = inverse(map_matrix, "I + dt A")
    return AffineField(
        mmul(field.gradient, map_inverse),
        mvec(map_inverse, field.offset),
    )


def analytic_advance(
    field: AffineField, particle_position: Vec, dt: Q
) -> tuple[AffineField, Vec]:
    particle_velocity = velocity(field, particle_position)
    next_position = vadd(
        particle_position, vscale(dt, particle_velocity)
    )
    next_field = convect(field, dt)
    assert velocity(next_field, next_position) == particle_velocity
    return next_field, next_position


def analytic_schedule(
    field: AffineField, particle_position: Vec, schedule: Sequence[Q]
) -> tuple[AffineField, Vec]:
    material_velocity = velocity(field, particle_position)
    for dt in schedule:
        field, particle_position = analytic_advance(
            field, particle_position, dt
        )
        assert velocity(field, particle_position) == material_velocity
    return field, particle_position


def symmetric_stencil(
    vectors: Sequence[Vec], node_weights: Sequence[Q]
) -> tuple[WeightedOffset, ...]:
    assert len(vectors) == len(node_weights)
    center_weight = Q(1) - 2 * sum(node_weights, Q(0))
    assert center_weight >= 0
    result: list[WeightedOffset] = [(center_weight, ZERO_V)]
    for vector, weight in zip(vectors, node_weights, strict=True):
        result.append((weight, vector))
        result.append((weight, vscale(Q(-1), vector)))
    return tuple(result)


STENCILS: tuple[tuple[str, tuple[WeightedOffset, ...]], ...] = (
    (
        "axis_anisotropic",
        symmetric_stencil(
            (
                (Q(1), Q(0), Q(0)),
                (Q(0), Q(2), Q(0)),
                (Q(0), Q(0), Q(3)),
            ),
            (Q(1, 12), Q(1, 10), Q(1, 8)),
        ),
    ),
    (
        "skew_anisotropic",
        symmetric_stencil(
            (
                (Q(2), Q(1), Q(0)),
                (Q(-1), Q(3), Q(1)),
                (Q(1), Q(-2), Q(4)),
            ),
            (Q(1, 12), Q(1, 8), Q(1, 10)),
        ),
    ),
    (
        "fractional_skew_anisotropic",
        symmetric_stencil(
            (
                (Q(3, 2), Q(-1, 3), Q(2, 5)),
                (Q(1, 4), Q(5, 3), Q(-2, 7)),
                (Q(-3, 8), Q(1, 6), Q(7, 4)),
            ),
            (Q(1, 9), Q(1, 11), Q(1, 13)),
        ),
    ),
    (
        "irregular_tetrahedral_positive",
        (
            (Q(15, 61), (Q(2), Q(0), Q(0))),
            (Q(10, 61), (Q(0), Q(3), Q(0))),
            (Q(6, 61), (Q(0), Q(0), Q(5))),
            (Q(30, 61), (Q(-1), Q(-1), Q(-1))),
        ),
    ),
)


FIELDS: tuple[tuple[str, AffineField], ...] = (
    ("translation", AffineField(ZERO_M, (Q(2, 3), Q(-3, 5), Q(5, 7)))),
    (
        "nonsymmetric_upper",
        AffineField(
            (
                (Q(0), Q(2, 5), Q(-1, 7)),
                (Q(0), Q(0), Q(3, 8)),
                (Q(0), Q(0), Q(0)),
            ),
            (Q(1, 6), Q(-2, 9), Q(4, 11)),
        ),
    ),
    (
        "nonsymmetric_dense",
        AffineField(
            (
                (Q(1, 7), Q(2, 5), Q(-1, 4)),
                (Q(-3, 8), Q(1, 9), Q(2, 7)),
                (Q(1, 6), Q(-2, 11), Q(1, 10)),
            ),
            (Q(-2, 7), Q(3, 10), Q(1, 8)),
        ),
    ),
    (
        "skew_rotation_control",
        AffineField(
            (
                (Q(0), Q(-3, 7), Q(-2, 5)),
                (Q(3, 7), Q(0), Q(-1, 3)),
                (Q(2, 5), Q(1, 3), Q(0)),
            ),
            (Q(1, 9), Q(-1, 5), Q(2, 11)),
        ),
    ),
)

HORIZONS: tuple[Q, ...] = (Q(1, 3), Q(2, 5), Q(3, 7))
REFINEMENTS: tuple[int, ...] = (1, 2, 4, 8)
PAIR_OFFSET: Vec = (Q(2, 3), Q(-3, 5), Q(5, 7))


def qtext(value: Q) -> str:
    return f"{value.numerator}/{value.denominator}"


def flatten_matrix(matrix: Mat) -> Iterable[Q]:
    for row in matrix:
        yield from row


def witness(digest: "hashlib._Hash", values: Iterable[Q]) -> None:
    digest.update("|".join(qtext(value) for value in values).encode("ascii"))
    digest.update(b"\n")


def random_q(rng: Random) -> Q:
    return Q(rng.randint(-13, 13), rng.randint(1, 17))


def random_vec(rng: Random) -> Vec:
    return (random_q(rng), random_q(rng), random_q(rng))


def check_singular_rejections() -> dict[str, int]:
    singular_gradient: Mat = (
        (Q(-2), Q(0), Q(0)),
        (Q(0), Q(0), Q(0)),
        (Q(0), Q(0), Q(0)),
    )
    advection_rejections = 0
    try:
        convect(AffineField(singular_gradient, ZERO_V), Q(1, 2))
    except ValueError:
        advection_rejections += 1
    else:
        raise AssertionError("singular I + dt A was accepted")

    singular_d: Mat = (
        (Q(1), Q(0), Q(0)),
        (Q(0), Q(0), Q(0)),
        (Q(0), Q(0), Q(0)),
    )
    moment_rejections = 0
    try:
        inverse(singular_d, "D_next")
    except ValueError:
        moment_rejections += 1
    else:
        raise AssertionError("singular D_next was accepted")
    return {
        "I_plus_dt_A": advection_rejections,
        "D_next": moment_rejections,
    }


def run(samples: int) -> dict:
    rng = Random(SEED)
    digest = hashlib.sha256()

    stencil_moments: dict[str, Mat] = {}
    non_centrally_symmetric_stencils: list[str] = []
    for stencil_name, stencil in STENCILS:
        d_old = check_stencil(stencil)
        # Every registered witness is intentionally anisotropic.
        assert not (
            d_old[0][0] == d_old[1][1] == d_old[2][2]
            and all(
                d_old[row][column] == 0
                for row in range(3)
                for column in range(3)
                if row != column
            )
        )
        stencil_moments[stencil_name] = d_old
        if not is_centrally_symmetric(stencil):
            non_centrally_symmetric_stencils.append(stencil_name)

    assert "irregular_tetrahedral_positive" in non_centrally_symmetric_stencils

    base_cases = 0
    direct_eq38_evaluations = 0
    c_next_fixed_d_cases = 0
    convected_discrepancy_cases = 0
    analytic_semigroup_cases = 0
    fixed_d_refinement_witnesses = 0
    center_ballistic_refinement_witnesses = 0
    global_intercept_inconsistency_cases = 0
    nonzero_convected_discrepancies = {name: 0 for name, _ in FIELDS}
    nonzero_global_intercept_inconsistencies = {
        name: 0 for name, _ in FIELDS
    }
    nonsymmetric_anisotropic_cases = 0
    noncommuting_a_d_cases = 0

    for field_name, base_field in FIELDS:
        for stencil_name, stencil in STENCILS:
            d_old = stencil_moments[stencil_name]
            d_inverse = inverse(d_old, "D_next = D_old")
            for horizon in HORIZONS:
                for _sample in range(samples):
                    particle_position = random_vec(rng)
                    field = AffineField(
                        base_field.gradient,
                        vadd(base_field.offset, vscale(Q(1, 19), random_vec(rng))),
                    )
                    particle_velocity = velocity(field, particle_position)

                    # Evaluate the complete finite Eq. (38) sum first.
                    result = equation_38_force_free(
                        field, particle_position, horizon, stencil
                    )
                    direct_eq38_evaluations += 1
                    expected_position = vadd(
                        particle_position,
                        vscale(horizon, particle_velocity),
                    )
                    assert result.particle_position == expected_position
                    assert result.particle_velocity == particle_velocity
                    derived_b_next = mmul(field.gradient, d_old)
                    assert result.b_next == derived_b_next
                    base_cases += 1

                    # This conclusion deliberately uses D_next = D_old.
                    c_next = mmul(result.b_next, d_inverse)
                    assert c_next == field.gradient
                    c_next_fixed_d_cases += 1

                    if field.gradient != transpose(field.gradient):
                        nonsymmetric_anisotropic_cases += 1
                    if mmul(field.gradient, d_old) != mmul(
                        d_old, field.gradient
                    ):
                        noncommuting_a_d_cases += 1

                    exact_field, exact_position = analytic_advance(
                        field, particle_position, horizon
                    )
                    assert exact_position == expected_position
                    map_matrix = madd(
                        IDENTITY, mscale(horizon, field.gradient)
                    )
                    map_inverse = inverse(map_matrix, "I + dt A")
                    discrepancy = msub(c_next, exact_field.gradient)
                    expected_discrepancy = mscale(
                        horizon,
                        mmul(
                            mmul(field.gradient, field.gradient),
                            map_inverse,
                        ),
                    )
                    assert discrepancy == expected_discrepancy
                    convected_discrepancy_cases += 1
                    if discrepancy != ZERO_M:
                        nonzero_convected_discrepancies[field_name] += 1

                    # The analytically convected affine field is an exact
                    # semigroup.  In contrast, direct Eq. (38) with the same
                    # D at every step returns the pre-advection gradient A on
                    # every refinement, so its full-horizon discrepancy does
                    # not shrink.  Center velocity/trajectory still remain
                    # exactly ballistic; the defect is in transported affine
                    # representation state, not the material center path.
                    for pieces in REFINEMENTS:
                        piece_dt = horizon / pieces
                        analytic_field, analytic_position = analytic_schedule(
                            field,
                            particle_position,
                            (piece_dt,) * pieces,
                        )
                        assert analytic_field == exact_field
                        assert analytic_position == exact_position
                        if pieces > 1:
                            analytic_semigroup_cases += 1

                        local_position = particle_position
                        stale_gradient = field.gradient
                        for _piece in range(pieces):
                            local_offset = vsub(
                                particle_velocity,
                                mvec(stale_gradient, local_position),
                            )
                            local_result = equation_38_force_free(
                                AffineField(stale_gradient, local_offset),
                                local_position,
                                piece_dt,
                                stencil,
                            )
                            direct_eq38_evaluations += 1
                            assert local_result.particle_velocity == particle_velocity
                            stale_gradient = mmul(
                                local_result.b_next, d_inverse
                            )
                            assert stale_gradient == field.gradient
                            local_position = local_result.particle_position
                        assert local_position == exact_position
                        assert stale_gradient == field.gradient
                        assert msub(
                            stale_gradient, exact_field.gradient
                        ) == discrepancy
                        fixed_d_refinement_witnesses += 1
                        center_ballistic_refinement_witnesses += 1

                    # Two material centers retain different velocities.  A
                    # stale shared A then implies particle-local offsets that
                    # disagree by -dt A^2 (x_p - x_q), whereas the convected
                    # field has one shared offset and reproduces both.
                    second_position = vadd(particle_position, PAIR_OFFSET)
                    second_velocity = velocity(field, second_position)
                    second_next = vadd(
                        second_position, vscale(horizon, second_velocity)
                    )
                    first_stale_offset = vsub(
                        particle_velocity,
                        mvec(field.gradient, expected_position),
                    )
                    second_stale_offset = vsub(
                        second_velocity,
                        mvec(field.gradient, second_next),
                    )
                    offset_disagreement = vsub(
                        first_stale_offset, second_stale_offset
                    )
                    expected_offset_disagreement = vscale(
                        -horizon,
                        mvec(
                            mmul(field.gradient, field.gradient),
                            vsub(particle_position, second_position),
                        ),
                    )
                    assert offset_disagreement == expected_offset_disagreement
                    assert velocity(exact_field, expected_position) == particle_velocity
                    assert velocity(exact_field, second_next) == second_velocity
                    global_intercept_inconsistency_cases += 1
                    if offset_disagreement != ZERO_V:
                        nonzero_global_intercept_inconsistencies[field_name] += 1

                    witness(
                        digest,
                        (
                            horizon,
                            *particle_position,
                            *field.offset,
                            *flatten_matrix(field.gradient),
                            *flatten_matrix(d_old),
                            *flatten_matrix(result.b_next),
                            *flatten_matrix(c_next),
                            *flatten_matrix(exact_field.gradient),
                            *flatten_matrix(discrepancy),
                            *offset_disagreement,
                        ),
                    )

    assert nonsymmetric_anisotropic_cases > 0
    assert noncommuting_a_d_cases > 0
    assert nonzero_convected_discrepancies["translation"] == 0
    assert nonzero_global_intercept_inconsistencies["translation"] == 0
    for field_name in (
        "nonsymmetric_upper",
        "nonsymmetric_dense",
        "skew_rotation_control",
    ):
        assert nonzero_convected_discrepancies[field_name] > 0
        assert nonzero_global_intercept_inconsistencies[field_name] > 0

    result = {
        "seed": SEED,
        "arithmetic": "fractions.Fraction exact rationals",
        "equation": "Jiang-Schroeder-Teran JCP 2017 Eq. 38 complete finite sum",
        "assumptions": [
            "finite nonnegative old weights sum to one",
            "weighted old particle-to-grid offsets sum to zero",
            "D_old is the invertible weighted second moment",
            "the old grid velocity field is globally affine",
            "force-free grid velocities are unchanged",
            "old/new grid and particle positions use the same explicit affine map",
            "D_next = D_old only for the reported C_next conclusion",
            "I + dt A is invertible where the convected field is evaluated",
        ],
        "fields": [name for name, _field in FIELDS],
        "anisotropic_stencils": [name for name, _stencil in STENCILS],
        "non_centrally_symmetric_stencils": non_centrally_symmetric_stencils,
        "physical_dt_horizons": [qtext(value) for value in HORIZONS],
        "refinement_partitions": list(REFINEMENTS),
        "samples_per_field_stencil_dt": samples,
        "base_eq38_identity_cases": base_cases,
        "direct_complete_eq38_evaluations": direct_eq38_evaluations,
        "c_next_under_d_next_equals_d_old_cases": c_next_fixed_d_cases,
        "convected_gradient_discrepancy_cases": convected_discrepancy_cases,
        "analytic_semigroup_refinement_cases": analytic_semigroup_cases,
        "fixed_d_stale_gradient_refinement_witnesses": fixed_d_refinement_witnesses,
        "center_ballistic_refinement_witnesses": center_ballistic_refinement_witnesses,
        "global_intercept_inconsistency_cases": global_intercept_inconsistency_cases,
        "nonsymmetric_A_anisotropic_D_cases": nonsymmetric_anisotropic_cases,
        "noncommuting_A_D_cases": noncommuting_a_d_cases,
        "nonzero_convected_gradient_discrepancies": nonzero_convected_discrepancies,
        "nonzero_global_intercept_inconsistencies": (
            nonzero_global_intercept_inconsistencies
        ),
        "singular_rejections": check_singular_rejections(),
        "derived_identity": "B_next = A D_old (derived from the complete Eq. 38 sum)",
        "fixed_D_consequence": "C_next = A, not generally A(I + dt A)^-1",
        "witness_sha256": digest.hexdigest(),
        "scope": (
            "exact finite global-affine force-free algebra only; not numerical "
            "transfer validation or mechanics promotion"
        ),
    }
    payload = json.dumps(result, indent=2, sort_keys=True)
    result["result_sha256_before_hash_field"] = hashlib.sha256(
        payload.encode()
    ).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.samples <= 0:
        parser.error("--samples must be positive")
    result = run(args.samples)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.verify is not None:
        expected = args.verify.read_text(encoding="utf-8")
        if rendered != expected:
            raise SystemExit(f"moving APIC limit oracle mismatch: {args.verify}")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
