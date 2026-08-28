#!/usr/bin/env python3
"""Independent exact oracle for MLS-0 baseline-hardening contracts.

This file imports no C++ binding and shares no production implementation code.
It is intentionally small enough for external reviewers to replace wholesale.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
from random import Random
from typing import Iterable, Sequence

SEED = 260828
Vec3 = tuple[int, int, int]
Edge = tuple[int, int, int]


def add(left: Vec3, right: Vec3) -> Vec3:
    return tuple(a + b for a, b in zip(left, right, strict=True))  # type: ignore[return-value]


def subtract(left: Vec3, right: Vec3) -> Vec3:
    return tuple(a - b for a, b in zip(left, right, strict=True))  # type: ignore[return-value]


def cross(left: Vec3, right: Vec3) -> Vec3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def within_support(first: Vec3, second: Vec3, radius: int) -> bool:
    if radius <= 0:
        raise ValueError("radius must be positive")
    delta = subtract(first, second)
    return sum(component * component for component in delta) <= radius * radius


def canonical_graph(atoms: Sequence[int], edges: Iterable[Edge]) -> tuple:
    if not atoms:
        raise ValueError("empty graph")
    normalized: dict[tuple[int, int], int] = {}
    neighbors = [set() for _ in atoms]
    for first, second, order in edges:
        if first == second or not (0 <= first < len(atoms) and 0 <= second < len(atoms)):
            raise ValueError("invalid edge")
        if order <= 0:
            raise ValueError("invalid order")
        pair = tuple(sorted((first, second)))
        if pair in normalized:
            raise ValueError("parallel edge")
        normalized[pair] = order
        neighbors[first].add(second)
        neighbors[second].add(first)

    visited = {0}
    pending = [0]
    while pending:
        current = pending.pop()
        for neighbor in neighbors[current] - visited:
            visited.add(neighbor)
            pending.append(neighbor)
    if len(visited) != len(atoms):
        raise ValueError("disconnected graph")

    encodings = []
    for new_to_old in itertools.permutations(range(len(atoms))):
        labels = tuple(atoms[old] for old in new_to_old)
        orders = tuple(
            normalized.get(tuple(sorted((new_to_old[first], new_to_old[second]))), 0)
            for first in range(len(atoms))
            for second in range(first + 1, len(atoms))
        )
        encodings.append((labels, orders))
    return min(encodings)


def kinetic(momentum: Vec3, mass: int, scale: int = 1) -> int:
    return sum(component * component for component in momentum) // mass // scale // 2


def impulse_transition(
    first: Vec3,
    second: Vec3,
    impulse: Vec3,
    stored: int,
    heat: int,
    mass: int,
) -> tuple[Vec3, Vec3, int, int]:
    before = kinetic(first, mass) + kinetic(second, mass)
    first_after = add(first, impulse)
    second_after = subtract(second, impulse)
    delta = kinetic(first_after, mass) + kinetic(second_after, mass) - before
    if delta >= 0:
        stored -= delta
    else:
        heat -= delta
    if stored < 0:
        raise ValueError("stored energy overdraw")
    return first_after, second_after, stored, heat


def run() -> dict:
    rng = Random(SEED)
    angular_cases = 0
    for _ in range(10_000):
        r1 = tuple(rng.randint(-10_000, 10_000) for _ in range(3))
        r2 = tuple(rng.randint(-10_000, 10_000) for _ in range(3))
        p1 = tuple(rng.randint(-1_000, 1_000) for _ in range(3))
        p2 = tuple(rng.randint(-1_000, 1_000) for _ in range(3))
        impulse = tuple(rng.randint(-100, 100) for _ in range(3))
        before = add(cross(r1, p1), cross(r2, p2))
        after = add(cross(r1, add(p1, impulse)), cross(r2, subtract(p2, impulse)))
        assert subtract(after, before) == cross(subtract(r1, r2), impulse)
        angular_cases += 1

    counterexample = cross((1, 0, 0), (0, 1, 0))
    assert counterexample == (0, 0, 1)

    support_cases = 0
    offsets = ((10, 0, 0), (6, 8, 0), (6, 6, 5))
    for phase in range(-199, 200):
        origin = (phase, phase * 3, -phase * 2)
        for offset in offsets:
            assert within_support(origin, add(origin, offset), 10)
            support_cases += 1
        assert not within_support(origin, add(origin, (6, 8, 1)), 10)
        support_cases += 1

    first = canonical_graph(
        (2, 7, 2, 11), ((0, 1, 1), (1, 2, 2), (2, 3, 1), (0, 3, 3)))
    renumbered = canonical_graph(
        (7, 11, 2, 2), ((1, 3, 1), (3, 0, 2), (1, 2, 3), (0, 2, 1)))
    assert first == renumbered
    rejected_graph_cases = 0
    for atoms, edges in (
        ((2, 7, 11), ((0, 1, 1),)),
        ((2, 7), ((0, 1, 1), (1, 0, 2))),
    ):
        try:
            canonical_graph(atoms, edges)
        except ValueError:
            rejected_graph_cases += 1
        else:
            raise AssertionError("invalid graph was accepted")

    first_momentum = (0, 0, 0)
    second_momentum = (0, 0, 0)
    stored_before = 1_000
    heat_before = 1_000
    first_momentum, second_momentum, stored, heat = impulse_transition(
        first_momentum, second_momentum, (20, 0, 0), stored_before, heat_before, 10
    )
    first_momentum, second_momentum, stored, heat = impulse_transition(
        first_momentum, second_momentum, (-20, 0, 0), stored, heat, 10
    )
    assert first_momentum == second_momentum == (0, 0, 0)
    assert stored < stored_before and heat > heat_before
    assert stored + heat == stored_before + heat_before

    result = {
        "seed": SEED,
        "angular_delta_cases": angular_cases,
        "noncentral_counterexample_delta": list(counterexample),
        "support_translation_cases": support_cases,
        "canonical_isomorphism_cases": 1,
        "rejected_graph_cases": rejected_graph_cases,
        "dissipative_cycle_cases": 1,
    }
    payload = json.dumps(result, indent=2, sort_keys=True)
    result["result_sha256_before_hash_field"] = hashlib.sha256(payload.encode()).hexdigest()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    result = run()
    if args.verify is not None:
        expected = json.loads(args.verify.read_text(encoding="utf-8"))
        if result != expected:
            raise SystemExit("hardening oracle result differs from canonical witness")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
