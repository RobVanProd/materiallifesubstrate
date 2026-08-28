#!/usr/bin/env python3
"""Independent exact-rational oracle for the Time + Transfer laboratory.

This file deliberately does not import, bind, or translate C++ implementation
helpers. It checks the finite algebraic transfer identities over Fraction. It
does not validate continuum mechanics or floating-point convergence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path
from random import Random
from typing import Dict, Iterable, List, Sequence, Tuple

SEED = 260828
Vec = Tuple[Q, Q, Q]
Mat = Tuple[Vec, Vec, Vec]
Index = Tuple[int, int, int]


def vadd(a: Vec, b: Vec) -> Vec:
    return tuple(a[i] + b[i] for i in range(3))  # type: ignore[return-value]


def vsub(a: Vec, b: Vec) -> Vec:
    return tuple(a[i] - b[i] for i in range(3))  # type: ignore[return-value]


def scale(s: Q, v: Vec) -> Vec:
    return tuple(s * v[i] for i in range(3))  # type: ignore[return-value]


def dot(a: Vec, b: Vec) -> Q:
    return sum((a[i] * b[i] for i in range(3)), Q(0))


def cross(a: Vec, b: Vec) -> Vec:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def mvec(a: Mat, x: Vec) -> Vec:
    return tuple(dot(a[row], x) for row in range(3))  # type: ignore[return-value]


def madd(a: Mat, b: Mat) -> Mat:
    return tuple(vadd(a[row], b[row]) for row in range(3))  # type: ignore[return-value]


def mscale(s: Q, a: Mat) -> Mat:
    return tuple(scale(s, a[row]) for row in range(3))  # type: ignore[return-value]


def mmul(a: Mat, b: Mat) -> Mat:
    bt = tuple(tuple(b[row][column] for row in range(3)) for column in range(3))
    return tuple(
        tuple(dot(a[row], bt[column]) for column in range(3))
        for row in range(3)
    )  # type: ignore[return-value]


def outer(a: Vec, b: Vec) -> Mat:
    return tuple(
        tuple(a[row] * b[column] for column in range(3))
        for row in range(3)
    )  # type: ignore[return-value]


ZERO_V: Vec = (Q(0), Q(0), Q(0))
ZERO_M: Mat = (ZERO_V, ZERO_V, ZERO_V)
IDENTITY: Mat = ((Q(1), Q(0), Q(0)), (Q(0), Q(1), Q(0)), (Q(0), Q(0), Q(1)))


def determinant(a: Mat) -> Q:
    return (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )


def inverse(a: Mat) -> Mat:
    det = determinant(a)
    if det == 0:
        raise AssertionError("oracle moment matrix is singular")
    adj: Mat = (
        (
            a[1][1] * a[2][2] - a[1][2] * a[2][1],
            a[0][2] * a[2][1] - a[0][1] * a[2][2],
            a[0][1] * a[1][2] - a[0][2] * a[1][1],
        ),
        (
            a[1][2] * a[2][0] - a[1][0] * a[2][2],
            a[0][0] * a[2][2] - a[0][2] * a[2][0],
            a[0][2] * a[1][0] - a[0][0] * a[1][2],
        ),
        (
            a[1][0] * a[2][1] - a[1][1] * a[2][0],
            a[0][1] * a[2][0] - a[0][0] * a[2][1],
            a[0][0] * a[1][1] - a[0][1] * a[1][0],
        ),
    )
    return mscale(Q(1, 1) / det, adj)


def axis_stencil(position: Q, origin: Q, spacing: Q) -> List[Tuple[int, Q, Q]]:
    normalized = (position - origin) / spacing
    base = (normalized - Q(1, 2)).numerator // (normalized - Q(1, 2)).denominator
    f = normalized - base
    weights = (
        Q(1, 2) * (Q(3, 2) - f) ** 2,
        Q(3, 4) - (f - 1) ** 2,
        Q(1, 2) * (f - Q(1, 2)) ** 2,
    )
    return [
        (base + offset, weights[offset], origin + (base + offset) * spacing)
        for offset in range(3)
    ]


def stencil(position: Vec, origin: Vec, spacing: Q) -> List[Tuple[Index, Q, Vec, Vec]]:
    axes = [axis_stencil(position[d], origin[d], spacing) for d in range(3)]
    result = []
    for ix, wx, x in axes[0]:
        for iy, wy, y in axes[1]:
            for iz, wz, z in axes[2]:
                node = (x, y, z)
                result.append(((ix, iy, iz), wx * wy * wz, node, vsub(node, position)))
    return result


def qtext(value: Q) -> str:
    return f"{value.numerator}/{value.denominator}"


def witness(hasher: "hashlib._Hash", values: Iterable[Q]) -> None:
    hasher.update("|".join(qtext(value) for value in values).encode("ascii"))
    hasher.update(b"\n")


def flatten_vectors(values: Iterable[Vec]) -> Iterable[Q]:
    for value in values:
        yield from value


def random_q(rng: Random, low: int = -9, high: int = 9) -> Q:
    return Q(rng.randint(low, high), rng.randint(1, 11))


def random_vec(rng: Random) -> Vec:
    return (random_q(rng), random_q(rng), random_q(rng))


def random_mat(rng: Random) -> Mat:
    return (random_vec(rng), random_vec(rng), random_vec(rng))


def check_kernel_moments(rng: Random, cases: int, digest: "hashlib._Hash") -> None:
    for _ in range(cases):
        spacing = Q(rng.randint(1, 9), rng.randint(1, 9))
        position = random_vec(rng)
        origin = random_vec(rng)
        samples = stencil(position, origin, spacing)
        weight_sum = sum((weight for _, weight, _, _ in samples), Q(0))
        first = ZERO_V
        second = ZERO_M
        for _, weight, _, offset in samples:
            first = vadd(first, scale(weight, offset))
            second = madd(second, mscale(weight, outer(offset, offset)))
        assert weight_sum == 1
        assert first == ZERO_V
        assert second == mscale(spacing * spacing / 4, IDENTITY)
        witness(digest, (weight_sum, *first, *flatten_vectors(second)))


def check_transfers(rng: Random, cases: int, digest: "hashlib._Hash") -> None:
    for _ in range(cases):
        spacing = Q(rng.randint(1, 6), rng.randint(1, 6))
        origin = random_vec(rng)
        particles = []
        for _particle in range(4):
            particles.append((Q(rng.randint(1, 17)), random_vec(rng), random_vec(rng), random_mat(rng)))

        pic: Dict[Index, Tuple[Q, Vec, Vec]] = {}
        apic: Dict[Index, Tuple[Q, Vec, Vec]] = {}
        p_mass = Q(0)
        p_momentum = ZERO_V
        p_center_angular = ZERO_V
        p_affine_angular = ZERO_V
        for mass, position, velocity, affine in particles:
            p_mass += mass
            momentum = scale(mass, velocity)
            p_momentum = vadd(p_momentum, momentum)
            p_center_angular = vadd(p_center_angular, cross(position, momentum))
            for index, weight, node, offset in stencil(position, origin, spacing):
                if weight == 0:
                    continue
                weighted_mass = mass * weight
                pic_mass, pic_q, _ = pic.get(index, (Q(0), ZERO_V, node))
                apic_mass, apic_q, _ = apic.get(index, (Q(0), ZERO_V, node))
                pic[index] = (
                    pic_mass + weighted_mass,
                    vadd(pic_q, scale(weighted_mass, velocity)),
                    node,
                )
                affine_velocity = mvec(affine, offset)
                apic[index] = (
                    apic_mass + weighted_mass,
                    vadd(apic_q, scale(weighted_mass, vadd(velocity, affine_velocity))),
                    node,
                )
                p_affine_angular = vadd(
                    p_affine_angular,
                    scale(weighted_mass, cross(offset, affine_velocity)),
                )

        for grid in (pic, apic):
            assert sum((mass for mass, _, _ in grid.values()), Q(0)) == p_mass
            assert tuple(
                sum((momentum[d] for _, momentum, _ in grid.values()), Q(0))
                for d in range(3)
            ) == p_momentum
        pic_angular = ZERO_V
        apic_angular = ZERO_V
        for _, momentum, node in pic.values():
            pic_angular = vadd(pic_angular, cross(node, momentum))
        for _, momentum, node in apic.values():
            apic_angular = vadd(apic_angular, cross(node, momentum))
        assert pic_angular == p_center_angular
        assert apic_angular == vadd(p_center_angular, p_affine_angular)

        # A global affine field is exactly represented by APIC on every occupied
        # node and reconstructed back to each particle.
        matrix = random_mat(rng)
        translation = random_vec(rng)
        affine_particles = [
            (mass, position, vadd(mvec(matrix, position), translation))
            for mass, position, _, _ in particles
        ]
        grid: Dict[Index, Tuple[Q, Vec, Vec]] = {}
        particle_augmented_energy = Q(0)
        for mass, position, velocity in affine_particles:
            particle_augmented_energy += mass * dot(velocity, velocity) / 2
            for index, weight, node, offset in stencil(position, origin, spacing):
                if weight == 0:
                    continue
                weighted_mass = mass * weight
                node_velocity = vadd(velocity, mvec(matrix, offset))
                old_mass, old_q, _ = grid.get(index, (Q(0), ZERO_V, node))
                grid[index] = (
                    old_mass + weighted_mass,
                    vadd(old_q, scale(weighted_mass, node_velocity)),
                    node,
                )
                affine_velocity = mvec(matrix, offset)
                particle_augmented_energy += mass * weight * dot(affine_velocity, affine_velocity) / 2

        grid_energy = Q(0)
        velocities: Dict[Index, Vec] = {}
        for index, (mass, momentum, node) in grid.items():
            velocity = scale(Q(1, 1) / mass, momentum)
            assert velocity == vadd(mvec(matrix, node), translation)
            velocities[index] = velocity
            grid_energy += mass * dot(velocity, velocity) / 2
        assert grid_energy == particle_augmented_energy

        for _mass, position, expected_velocity in affine_particles:
            reconstructed_velocity = ZERO_V
            b_moment = ZERO_M
            d_moment = ZERO_M
            for index, weight, _node, offset in stencil(position, origin, spacing):
                if weight == 0:
                    continue
                reconstructed_velocity = vadd(
                    reconstructed_velocity, scale(weight, velocities[index]))
                b_moment = madd(b_moment, mscale(weight, outer(velocities[index], offset)))
                d_moment = madd(d_moment, mscale(weight, outer(offset, offset)))
            reconstructed_matrix = mmul(b_moment, inverse(d_moment))
            assert reconstructed_velocity == expected_velocity
            assert reconstructed_matrix == matrix

        witness(
            digest,
            (
                p_mass,
                *p_momentum,
                *p_center_angular,
                *p_affine_angular,
                *pic_angular,
                *apic_angular,
                grid_energy,
            ),
        )


def angular_counterexample() -> Dict[str, bool]:
    spacing = Q(1)
    origin: Vec = (Q(1, 7), Q(2, 7), Q(3, 7))
    position: Vec = (Q(1, 4), Q(-1, 8), Q(1, 2))
    velocity: Vec = (Q(1, 4), Q(1, 2), Q(0))
    rotation: Mat = ((Q(0), Q(-2), Q(0)), (Q(2), Q(0), Q(0)), ZERO_V)
    mass = Q(3)
    center = cross(position, scale(mass, velocity))
    affine = ZERO_V
    grid = ZERO_V
    for _index, weight, node, offset in stencil(position, origin, spacing):
        local = mvec(rotation, offset)
        affine = vadd(affine, scale(mass * weight, cross(offset, local)))
        grid = vadd(
            grid,
            cross(node, scale(mass * weight, vadd(velocity, local))),
        )
    assert grid != center
    assert grid == vadd(center, affine)
    return {
        "center_only_not_conserved_by_apic_p2g": True,
        "augmented_apic_angular_identity_holds": True,
    }


def run(cases: int) -> dict:
    rng = Random(SEED)
    digest = hashlib.sha256()
    check_kernel_moments(rng, cases, digest)
    check_transfers(rng, cases, digest)
    result = {
        "seed": SEED,
        "kernel_exact_rational_cases": cases,
        "pic_apic_exact_rational_cases": cases,
        "flip_zero_update_identity": True,
        "angular_counterexample": angular_counterexample(),
        "witness_sha256": digest.hexdigest(),
        "scope": "finite exact transfer algebra only; not continuum mechanics",
    }
    payload = json.dumps(result, indent=2, sort_keys=True)
    result["result_sha256_before_hash_field"] = hashlib.sha256(payload.encode()).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=1_000)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.cases <= 0:
        parser.error("--cases must be positive")
    result = run(args.cases)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.verify is not None:
        expected = args.verify.read_text(encoding="utf-8")
        if rendered != expected:
            raise SystemExit(f"transfer oracle mismatch: {args.verify}")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
