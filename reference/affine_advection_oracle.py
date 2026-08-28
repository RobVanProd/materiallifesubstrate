#!/usr/bin/env python3
"""Independent exact-rational oracle for the Affine Advection laboratory.

This oracle imports no production bindings and shares no C++ implementation
helpers.  It checks only the finite-dimensional algebra of force-free global
affine velocity transport.  Passing it does not validate a transfer scheme,
trajectory integrator, continuum model, or floating-point implementation.
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


def determinant(matrix: Mat) -> Q:
    return (
        matrix[0][0]
        * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1]
        * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2]
        * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def inverse(matrix: Mat) -> Mat:
    """Return the exact inverse, rejecting a missing invertibility premise."""

    det = determinant(matrix)
    if det == 0:
        raise ValueError("I + dt*A is singular; affine evolution is undefined")
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
    result = mscale(Q(1) / det, adjugate)
    assert mmul(matrix, result) == IDENTITY
    assert mmul(result, matrix) == IDENTITY
    return result


@dataclass(frozen=True)
class AffineField:
    gradient: Mat
    offset: Vec


def velocity(field: AffineField, position: Vec) -> Vec:
    return vadd(mvec(field.gradient, position), field.offset)


def position_map(field: AffineField, position: Vec, dt: Q) -> Vec:
    """x' = (I + dt A)x + dt b = x + dt v(x)."""

    map_matrix = madd(IDENTITY, mscale(dt, field.gradient))
    mapped = vadd(mvec(map_matrix, position), vscale(dt, field.offset))
    assert mapped == vadd(position, vscale(dt, velocity(field, position)))
    return mapped


def convect_field(field: AffineField, dt: Q) -> AffineField:
    """A' = A(I + dt A)^-1 and b' = (I + dt A)^-1 b."""

    map_matrix = madd(IDENTITY, mscale(dt, field.gradient))
    map_inverse = inverse(map_matrix)
    return AffineField(
        mmul(field.gradient, map_inverse),
        mvec(map_inverse, field.offset),
    )


def advance(field: AffineField, position: Vec, dt: Q) -> tuple[AffineField, Vec]:
    initial_velocity = velocity(field, position)
    mapped = position_map(field, position, dt)
    convected = convect_field(field, dt)
    assert velocity(convected, mapped) == initial_velocity
    return convected, mapped


def advance_schedule(
    field: AffineField, position: Vec, schedule: Sequence[Q]
) -> tuple[AffineField, Vec, int]:
    material_velocity = velocity(field, position)
    preservation_checks = 0
    for dt in schedule:
        field, position = advance(field, position, dt)
        assert velocity(field, position) == material_velocity
        preservation_checks += 1
    return field, position, preservation_checks


def rotate_field(field: AffineField, orientation: Mat) -> AffineField:
    return AffineField(
        mmul(mmul(orientation, field.gradient), transpose(orientation)),
        mvec(orientation, field.offset),
    )


def qtext(value: Q) -> str:
    return f"{value.numerator}/{value.denominator}"


def flatten_matrix(matrix: Mat) -> Iterable[Q]:
    for row in matrix:
        yield from row


def witness(digest: "hashlib._Hash", values: Iterable[Q]) -> None:
    digest.update("|".join(qtext(value) for value in values).encode("ascii"))
    digest.update(b"\n")


def random_q(rng: Random) -> Q:
    return Q(rng.randint(-17, 17), rng.randint(1, 19))


def random_vec(rng: Random) -> Vec:
    return (random_q(rng), random_q(rng), random_q(rng))


def skew(angular_velocity: Vec) -> Mat:
    wx, wy, wz = angular_velocity
    return (
        (Q(0), -wz, wy),
        (wz, Q(0), -wx),
        (-wy, wx, Q(0)),
    )


FIELDS: tuple[tuple[str, AffineField], ...] = (
    (
        "translation",
        AffineField(ZERO_M, (Q(3, 2), Q(-5, 3), Q(7, 4))),
    ),
    (
        "rigid_rotation",
        AffineField(
            skew((Q(2, 3), Q(-3, 5), Q(4, 7))),
            (Q(1, 7), Q(-2, 9), Q(1, 5)),
        ),
    ),
    (
        "general_affine",
        AffineField(
            (
                (Q(1, 7), Q(-2, 9), Q(1, 5)),
                (Q(3, 11), Q(-1, 8), Q(2, 13)),
                (Q(-1, 6), Q(4, 15), Q(1, 10)),
            ),
            (Q(2, 7), Q(-3, 8), Q(5, 12)),
        ),
    ),
)


ORIENTATIONS: tuple[tuple[str, Mat], ...] = (
    ("identity", IDENTITY),
    (
        "quarter_turn_x",
        ((Q(1), Q(0), Q(0)), (Q(0), Q(0), Q(-1)), (Q(0), Q(1), Q(0))),
    ),
    (
        "quarter_turn_y",
        ((Q(0), Q(0), Q(1)), (Q(0), Q(1), Q(0)), (Q(-1), Q(0), Q(0))),
    ),
    (
        "quarter_turn_z",
        ((Q(0), Q(-1), Q(0)), (Q(1), Q(0), Q(0)), (Q(0), Q(0), Q(1))),
    ),
    (
        "axis_cycle",
        ((Q(0), Q(1), Q(0)), (Q(0), Q(0), Q(1)), (Q(1), Q(0), Q(0))),
    ),
    (
        "half_turn_xy",
        ((Q(-1), Q(0), Q(0)), (Q(0), Q(-1), Q(0)), (Q(0), Q(0), Q(1))),
    ),
)

HORIZONS: tuple[Q, ...] = (Q(1, 2), Q(2, 3), Q(3, 4))
REFINEMENTS: tuple[int, ...] = (1, 2, 4, 8)


def check_orientation(orientation: Mat) -> None:
    assert determinant(orientation) == 1
    assert mmul(orientation, transpose(orientation)) == IDENTITY
    assert mmul(transpose(orientation), orientation) == IDENTITY


def singular_rejection() -> bool:
    singular_gradient: Mat = (
        (Q(-2), Q(0), Q(0)),
        (Q(0), Q(0), Q(0)),
        (Q(0), Q(0), Q(0)),
    )
    try:
        convect_field(AffineField(singular_gradient, ZERO_V), Q(1, 2))
    except ValueError:
        return True
    raise AssertionError("a singular I + dt*A map was accepted")


def run(samples: int) -> dict:
    rng = Random(SEED)
    digest = hashlib.sha256()
    for _name, orientation in ORIENTATIONS:
        check_orientation(orientation)

    position_map_cases = 0
    material_velocity_cases = 0
    refinement_cases = 0
    stale_defect_cases = 0
    stale_gradient_cases = 0
    orientation_covariance_cases = 0
    nonzero_stale_velocity = {name: 0 for name, _field in FIELDS}
    nonzero_stale_position = {name: 0 for name, _field in FIELDS}

    for field_name, base_field in FIELDS:
        for horizon in HORIZONS:
            half = horizon / 2
            for _sample in range(samples):
                base_position = random_vec(rng)
                base_full_field, base_full_position = advance(
                    base_field, base_position, horizon
                )

                for _orientation_name, orientation in ORIENTATIONS:
                    field = rotate_field(base_field, orientation)
                    position = mvec(orientation, base_position)
                    initial_velocity = velocity(field, position)
                    full_field, full_position = advance(field, position, horizon)
                    position_map_cases += 1
                    material_velocity_cases += 1

                    # Rotation/sign-permutation covariance is exact over Q.
                    assert full_position == mvec(orientation, base_full_position)
                    assert full_field.offset == mvec(
                        orientation, base_full_field.offset
                    )
                    assert full_field.gradient == mmul(
                        mmul(orientation, base_full_field.gradient),
                        transpose(orientation),
                    )
                    orientation_covariance_cases += 1

                    # Refining one physical interval changes neither the exact
                    # convected field nor the material trajectory.
                    for pieces in REFINEMENTS[1:]:
                        piece_dt = horizon / pieces
                        refined_field, refined_position, checks = advance_schedule(
                            field, position, (piece_dt,) * pieces
                        )
                        material_velocity_cases += checks
                        assert refined_field == full_field
                        assert refined_position == full_position
                        refinement_cases += 1

                    # A stale field gives the wrong velocity after the first
                    # half-step and therefore the wrong position after the
                    # second.  Both defects are exact identities.
                    first_half_position = position_map(field, position, half)
                    stale_second_velocity = velocity(field, first_half_position)
                    velocity_defect = vsub(stale_second_velocity, initial_velocity)
                    expected_velocity_defect = vscale(
                        half, mvec(field.gradient, initial_velocity)
                    )
                    assert velocity_defect == expected_velocity_defect

                    stale_two_half_position = vadd(
                        first_half_position, vscale(half, stale_second_velocity)
                    )
                    position_defect = vsub(stale_two_half_position, full_position)
                    expected_position_defect = vscale(
                        half * half, mvec(field.gradient, initial_velocity)
                    )
                    assert position_defect == expected_position_defect
                    stale_defect_cases += 1
                    if velocity_defect != ZERO_V:
                        nonzero_stale_velocity[field_name] += 1
                    if position_defect != ZERO_V:
                        nonzero_stale_position[field_name] += 1

                    # Stale-gradient identity:
                    # A - A' = dt A^2 (I + dt A)^-1.
                    map_matrix = madd(
                        IDENTITY, mscale(horizon, field.gradient)
                    )
                    map_inverse = inverse(map_matrix)
                    expected_gradient_defect = mscale(
                        horizon,
                        mmul(
                            mmul(field.gradient, field.gradient), map_inverse
                        ),
                    )
                    gradient_defect = msub(
                        field.gradient, full_field.gradient
                    )
                    assert gradient_defect == expected_gradient_defect

                    # The corresponding intercept identity is checked as an
                    # additional guard, but is not promoted as a new contract.
                    assert vsub(field.offset, full_field.offset) == vscale(
                        horizon,
                        mvec(
                            mmul(field.gradient, map_inverse), field.offset
                        ),
                    )
                    stale_gradient_cases += 1

                    witness(
                        digest,
                        (
                            horizon,
                            determinant(map_matrix),
                            *position,
                            *initial_velocity,
                            *full_position,
                            *flatten_matrix(full_field.gradient),
                            *full_field.offset,
                            *velocity_defect,
                            *position_defect,
                            *flatten_matrix(gradient_defect),
                        ),
                    )

    assert nonzero_stale_velocity["translation"] == 0
    assert nonzero_stale_position["translation"] == 0
    assert nonzero_stale_velocity["rigid_rotation"] > 0
    assert nonzero_stale_position["rigid_rotation"] > 0
    assert nonzero_stale_velocity["general_affine"] > 0
    assert nonzero_stale_position["general_affine"] > 0

    result = {
        "seed": SEED,
        "arithmetic": "fractions.Fraction exact rationals",
        "fields": [name for name, _field in FIELDS],
        "orientations": [name for name, _matrix in ORIENTATIONS],
        "physical_dt_horizons": [qtext(value) for value in HORIZONS],
        "refinement_partitions": list(REFINEMENTS),
        "samples_per_field_orientation_dt": samples,
        "position_map_cases": position_map_cases,
        "material_velocity_preservation_cases": material_velocity_cases,
        "semigroup_refinement_cases": refinement_cases,
        "stale_position_velocity_defect_cases": stale_defect_cases,
        "stale_gradient_identity_cases": stale_gradient_cases,
        "orientation_covariance_cases": orientation_covariance_cases,
        "nonzero_stale_velocity_defects": nonzero_stale_velocity,
        "nonzero_stale_position_defects": nonzero_stale_position,
        "singular_map_rejections": int(singular_rejection()),
        "witness_sha256": digest.hexdigest(),
        "scope": (
            "exact global-affine force-free algebra only; not a transfer, "
            "trajectory, continuum, or floating-point validation"
        ),
    }
    payload = json.dumps(result, indent=2, sort_keys=True)
    result["result_sha256_before_hash_field"] = hashlib.sha256(
        payload.encode()
    ).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.samples <= 0:
        parser.error("--samples must be positive")
    result = run(args.samples)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.verify is not None:
        expected = args.verify.read_text(encoding="utf-8")
        if rendered != expected:
            raise SystemExit(f"affine advection oracle mismatch: {args.verify}")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
