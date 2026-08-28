#!/usr/bin/env python3
"""Deterministic, dependency-free exact-arithmetic oracle for MLS.

This suite is intentionally independent of the C++ implementation.  It checks the
accounting contracts that an implementation must satisfy and emits a canonical,
self-hashed JSON result.  All randomized cases use the local SplitMix64 generator,
so results do not depend on Python's ``random`` implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from random import Random
from typing import Any, Callable, Iterable, Mapping, Sequence


SEED = 260_828
SCHEMA = "mls.exact-validation.v1"
SUITE_VERSION = 1
MASK64 = (1 << 64) - 1


class ValidationFailure(RuntimeError):
    """Raised at the first violated invariant."""


class SplitMix64:
    """Small, fully specified pseudo-random generator used by every test."""

    def __init__(self, seed: int) -> None:
        self.state = seed & MASK64

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK64
        value = self.state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
        return (value ^ (value >> 31)) & MASK64

    def below(self, stop: int) -> int:
        if stop <= 0:
            raise ValueError("stop must be positive")
        # Rejection sampling avoids modulo bias and is specified in integer terms.
        limit = ((1 << 64) // stop) * stop
        while True:
            value = self.next_u64()
            if value < limit:
                return value % stop

    def integer(self, low: int, high: int) -> int:
        if high < low:
            raise ValueError("empty integer interval")
        return low + self.below(high - low + 1)

    def choose(self, values: Sequence[Any]) -> Any:
        return values[self.below(len(values))]


class Evidence:
    """Streaming digest of all generated witnesses, not only pass/fail counts."""

    def __init__(self) -> None:
        self._hash = hashlib.sha256()

    def add(self, *values: Any) -> None:
        encoded = json.dumps(
            _json_value(values), ensure_ascii=True, separators=(",", ":"), sort_keys=True
        ).encode("ascii")
        self._hash.update(len(encoded).to_bytes(8, "big"))
        self._hash.update(encoded)

    def hexdigest(self) -> str:
        return self._hash.hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"unsupported evidence value: {type(value)!r}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationFailure(message)


def _result(cases: int, evidence: Evidence, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "cases": cases,
        "evidence_sha256": evidence.hexdigest(),
        "status": "pass",
    }
    result.update(extra)
    return result


@dataclass(frozen=True)
class Counts:
    conservative_pair_transfers: int
    momentum_exchanges: int
    reaction_extents: int
    energy_ledger_conversions: int
    sparse_aggregations: int
    dynamic_similarity_transforms: int
    camera_invariance_runs: int
    deterministic_replays: int
    rotation_equivariance_cases: int


COUNTS = {
    "quick": Counts(1_000, 1_000, 1_000, 1_000, 250, 100, 32, 16, 100),
    "full": Counts(100_000, 100_000, 100_000, 100_000, 25_000, 10_000, 1_000, 256, 10_000),
}


PROVENANCE_HASH_V0 = "92405699657c404e4dcd324a16ca0d3cd0e7a82ff395ccfb277c47c10766a2da"


def run_provenance_suite(mode: str) -> dict[str, Any]:
    """Reproduce reference/exact_arithmetic_v0.py, including PRNG call order.

    The full-mode payload is deliberately byte-for-byte/hash compatible with the
    supplied v0 provenance result.  Keep extensions out of this payload: changing
    the historical result would destroy the audit trail.
    """

    counts = COUNTS[mode]
    provenance_rng = Random(SEED)

    def pair_transfer(n: int) -> int:
        for _ in range(n):
            first = provenance_rng.randint(0, 10_000)
            second = provenance_rng.randint(0, 10_000)
            amount = provenance_rng.randint(0, first)
            next_first, next_second = first - amount, second + amount
            _require(next_first >= 0 and next_second >= 0, "provenance pair transfer became negative")
            _require(next_first + next_second == first + second, "provenance pair transfer leaked")
        return n

    def momentum_exchange(n: int) -> int:
        for _ in range(n):
            first = provenance_rng.randint(-10_000, 10_000)
            second = provenance_rng.randint(-10_000, 10_000)
            impulse = provenance_rng.randint(-1_000, 1_000)
            _require(
                first + impulse + second - impulse == first + second,
                "provenance momentum exchange leaked",
            )
        return n

    provenance_comp: dict[str, tuple[int, int, int]] = {
        "A": (1, 0, 0),
        "B": (0, 1, 0),
        "C": (0, 0, 1),
        "AB": (1, 1, 0),
        "AC": (1, 0, 1),
        "BC": (0, 1, 1),
        "ABC": (1, 1, 1),
    }
    provenance_reactions: dict[str, dict[str, int]] = {
        "A+B->AB": {"A": -1, "B": -1, "AB": 1},
        "A+C->AC": {"A": -1, "C": -1, "AC": 1},
        "B+C->BC": {"B": -1, "C": -1, "BC": 1},
        "AB+C->ABC": {"AB": -1, "C": -1, "ABC": 1},
        "AC+B->ABC": {"AC": -1, "B": -1, "ABC": 1},
        "BC+A->ABC": {"BC": -1, "A": -1, "ABC": 1},
    }

    def provenance_element_delta(stoich: Mapping[str, int]) -> tuple[int, int, int]:
        return tuple(
            sum(provenance_comp[species][element] * coefficient for species, coefficient in stoich.items())
            for element in range(3)
        )  # type: ignore[return-value]

    def provenance_inventory(state: Mapping[str, Fraction]) -> tuple[Fraction, Fraction, Fraction]:
        return tuple(
            sum((state.get(species, Fraction(0)) * provenance_comp[species][element] for species in provenance_comp), Fraction(0))
            for element in range(3)
        )  # type: ignore[return-value]

    def stoichiometry(n: int) -> tuple[int, int]:
        for name, reaction in provenance_reactions.items():
            _require(provenance_element_delta(reaction) == (0, 0, 0), f"unbalanced provenance reaction {name}")
        names = list(provenance_reactions)
        for _ in range(n):
            state = {species: Fraction(provenance_rng.randint(0, 1_000)) for species in provenance_comp}
            name = provenance_rng.choice(names)
            reaction = provenance_reactions[name]
            reactants = [species for species, coefficient in reaction.items() if coefficient < 0]
            max_extent = min(state[species] // (-reaction[species]) for species in reactants)
            extent = Fraction(provenance_rng.randint(0, int(max_extent)))
            before = provenance_inventory(state)
            after = dict(state)
            for species, coefficient in reaction.items():
                after[species] += extent * coefficient
                _require(after[species] >= 0, "negative provenance reaction amount")
            _require(provenance_inventory(after) == before, "provenance reaction changed element inventory")
        return n, len(provenance_reactions)

    def energy_ledger(n: int) -> int:
        for _ in range(n):
            thermal = provenance_rng.randint(0, 10_000)
            chemical = provenance_rng.randint(0, 10_000)
            mechanical = provenance_rng.randint(0, 10_000)
            reservoir = provenance_rng.randint(0, 10_000)
            amount = provenance_rng.randint(0, chemical)
            before = thermal + chemical + mechanical + reservoir
            thermal += amount
            chemical -= amount
            _require(chemical >= 0, "negative provenance chemical energy")
            _require(thermal + chemical + mechanical + reservoir == before, "provenance internal energy leak")
            boundary_amount = provenance_rng.randint(0, reservoir)
            thermal += boundary_amount
            reservoir -= boundary_amount
            _require(reservoir >= 0, "negative provenance reservoir")
            _require(thermal + chemical + mechanical + reservoir == before, "provenance boundary energy leak")
        return n

    def aggregation(n: int) -> int:
        for _ in range(n):
            fine = [
                {
                    "mass": provenance_rng.randint(0, 1_000),
                    "energy": provenance_rng.randint(0, 1_000),
                    "A": provenance_rng.randint(0, 1_000),
                    "B": provenance_rng.randint(0, 1_000),
                }
                for _ in range(provenance_rng.randint(1, 64))
            ]
            coarse = {key: sum(cell[key] for cell in fine) for key in fine[0]}
            for key in coarse:
                _require(coarse[key] == sum(cell[key] for cell in fine), "provenance aggregation leak")
        return n

    def qint(low: int, high: int) -> Fraction:
        return Fraction(provenance_rng.randint(low, high), provenance_rng.randint(1, 23))

    def similarity(n: int) -> int:
        for _ in range(n):
            alpha, beta, density, velocity, length, viscosity, gravity, diffusivity, rate = (
                qint(1, 20) for _ in range(9)
            )
            scaled_velocity = alpha / beta * velocity
            scaled_length = alpha * length
            scaled_viscosity = alpha * alpha / beta * viscosity
            scaled_gravity = alpha / (beta * beta) * gravity
            scaled_diffusivity = alpha * alpha / beta * diffusivity
            scaled_rate = rate / beta
            _require(
                density * scaled_velocity * scaled_length / scaled_viscosity
                == density * velocity * length / viscosity,
                "provenance Reynolds transform failed",
            )
            _require(
                scaled_velocity * scaled_velocity / (scaled_gravity * scaled_length)
                == velocity * velocity / (gravity * length),
                "provenance Froude transform failed",
            )
            _require(
                scaled_velocity * scaled_length / scaled_diffusivity == velocity * length / diffusivity,
                "provenance Peclet transform failed",
            )
            _require(
                scaled_rate * scaled_length / scaled_velocity == rate * length / velocity,
                "provenance Damkohler transform failed",
            )
        return n

    results: dict[str, Any] = {
        "seed": SEED,
        "pair_transfer_cases": pair_transfer(counts.conservative_pair_transfers),
        "momentum_exchange_cases": momentum_exchange(counts.momentum_exchanges),
    }
    stoichiometry_cases, reaction_count = stoichiometry(counts.reaction_extents)
    results["stoichiometric_reactions_balanced"] = reaction_count
    results["stoichiometric_random_extent_cases"] = stoichiometry_cases
    results["energy_ledger_cases"] = energy_ledger(counts.energy_ledger_conversions)
    results["hierarchical_aggregation_cases"] = aggregation(counts.sparse_aggregations)
    results["coarse_grain_counterexample"] = {
        "fine_reactable": False,
        "coarse_reactable": True,
        "A_conserved": True,
        "B_conserved": True,
        "meaning": "conservative aggregation can create a false local affordance",
    }
    results["dynamic_similarity_cases"] = similarity(counts.dynamic_similarity_transforms)
    pretty_payload = json.dumps(results, sort_keys=True, indent=2)
    results["result_sha256_before_hash_field"] = hashlib.sha256(pretty_payload.encode()).hexdigest()
    if mode == "full":
        _require(
            results["result_sha256_before_hash_field"] == PROVENANCE_HASH_V0,
            "full provenance hash drifted from reference/exact_arithmetic_v0.py",
        )
    return results


def conservative_pair_transfers(rng: SplitMix64, cases: int) -> dict[str, Any]:
    evidence = Evidence()
    for case in range(cases):
        denominator = rng.integer(1, 10_000)
        left_n = rng.integer(0, 1_000_000)
        right_n = rng.integer(0, 1_000_000)
        # Positive transfer moves left -> right; negative moves right -> left.
        transfer_n = rng.integer(-right_n, left_n)
        left = Fraction(left_n, denominator)
        right = Fraction(right_n, denominator)
        transfer = Fraction(transfer_n, denominator)
        next_left = left - transfer
        next_right = right + transfer
        _require(next_left >= 0 and next_right >= 0, f"negative quantity in pair case {case}")
        _require(next_left + next_right == left + right, f"quantity leak in pair case {case}")
        evidence.add(case, denominator, left_n, right_n, transfer_n, next_left, next_right)
    return _result(cases, evidence, residual="0/1", non_negative=True)


def momentum_exchanges(rng: SplitMix64, cases: int) -> dict[str, Any]:
    evidence = Evidence()
    for case in range(cases):
        denominator = rng.integer(1, 100_000)
        first = tuple(Fraction(rng.integer(-1_000_000, 1_000_000), denominator) for _ in range(3))
        second = tuple(Fraction(rng.integer(-1_000_000, 1_000_000), denominator) for _ in range(3))
        impulse = tuple(Fraction(rng.integer(-100_000, 100_000), denominator) for _ in range(3))
        next_first = tuple(first[axis] + impulse[axis] for axis in range(3))
        next_second = tuple(second[axis] - impulse[axis] for axis in range(3))
        before = tuple(first[axis] + second[axis] for axis in range(3))
        after = tuple(next_first[axis] + next_second[axis] for axis in range(3))
        _require(after == before, f"momentum leak in exchange case {case}")
        evidence.add(case, denominator, first, second, impulse, after)
    return _result(cases, evidence, residual=["0/1", "0/1", "0/1"])


# Element order is A, B, C, D, E, F, G, H.  Names are labels used only by the
# reference oracle; the C++ engine derives compound identity from graph structure.
COMPOSITIONS: tuple[tuple[int, ...], ...] = (
    (1, 0, 0, 0, 0, 0, 0, 0),  # A
    (0, 1, 0, 0, 0, 0, 0, 0),  # B
    (0, 0, 1, 0, 0, 0, 0, 0),  # C
    (0, 0, 0, 1, 0, 0, 0, 0),  # D
    (0, 0, 0, 0, 1, 0, 0, 0),  # E
    (0, 0, 0, 0, 0, 1, 0, 0),  # F
    (0, 0, 0, 0, 0, 0, 1, 0),  # G
    (1, 1, 0, 0, 0, 0, 0, 0),  # AB
    (1, 2, 0, 0, 0, 0, 0, 0),  # ABB
    (0, 0, 2, 0, 0, 0, 0, 0),  # CC
    (0, 1, 1, 0, 0, 0, 0, 0),  # BC
    (0, 0, 0, 1, 1, 0, 0, 0),  # DE
    (0, 0, 0, 0, 0, 1, 1, 0),  # FG
    (0, 0, 0, 1, 0, 1, 0, 0),  # DF
    (0, 0, 0, 0, 1, 0, 1, 0),  # EG
    (1, 1, 1, 0, 0, 0, 0, 0),  # ABC
)

# Stoichiometric coefficients: negative consumes and positive produces.
REACTIONS: tuple[tuple[tuple[int, int], ...], ...] = (
    ((0, -1), (1, -1), (7, 1)),                  # A + B -> AB
    ((7, -1), (1, -1), (8, 1)),                  # AB + B -> ABB
    ((9, -1), (2, 2)),                            # CC -> 2 C
    ((7, -1), (2, -1), (0, 1), (10, 1)),         # AB + C -> A + BC
    ((11, -1), (12, -1), (13, 1), (14, 1)),      # DE + FG -> DF + EG
    ((7, -1), (2, -1), (15, 1)),                 # AB + C -> ABC
)


def _inventory(amounts: Sequence[int]) -> tuple[int, ...]:
    return tuple(
        sum(amounts[species] * COMPOSITIONS[species][element] for species in range(len(COMPOSITIONS)))
        for element in range(8)
    )


def stoichiometric_balance(rng: SplitMix64, cases: int) -> dict[str, Any]:
    definition_evidence = Evidence()
    for reaction_index, reaction in enumerate(REACTIONS):
        delta = tuple(
            sum(coefficient * COMPOSITIONS[species][element] for species, coefficient in reaction)
            for element in range(8)
        )
        _require(delta == (0,) * 8, f"reaction definition {reaction_index} is unbalanced: {delta}")
        definition_evidence.add(reaction_index, reaction, delta)

    extent_evidence = Evidence()
    for case in range(cases):
        reaction_index = rng.below(len(REACTIONS))
        reaction = REACTIONS[reaction_index]
        extent = rng.integer(0, 100_000)
        amounts = [rng.integer(0, 1_000_000) for _ in COMPOSITIONS]
        # Add exactly enough reserve so every generated extent is physically legal.
        for species, coefficient in reaction:
            if coefficient < 0:
                amounts[species] += -coefficient * extent
        before = _inventory(amounts)
        after_amounts = list(amounts)
        for species, coefficient in reaction:
            after_amounts[species] += coefficient * extent
        _require(min(after_amounts) >= 0, f"negative species amount in reaction case {case}")
        after = _inventory(after_amounts)
        _require(after == before, f"element inventory leak in reaction case {case}")
        extent_evidence.add(case, reaction_index, extent, before, after)

    return {
        "balanced_definitions": _result(len(REACTIONS), definition_evidence, balanced=f"{len(REACTIONS)}/{len(REACTIONS)}"),
        "random_extents": _result(cases, extent_evidence, element_residual=[0] * 8, non_negative=True),
        "status": "pass",
    }


def energy_ledger_closure(rng: SplitMix64, cases: int) -> dict[str, Any]:
    evidence = Evidence()
    world_channels = 5  # chemical, thermal, kinetic, strain, field
    reservoir_channels = 3  # source, heat sink, other declared boundary
    channel_count = world_channels + reservoir_channels
    for case in range(cases):
        channels = [rng.integer(0, 10_000_000) for _ in range(channel_count)]
        before_world = sum(channels[:world_channels])
        before_reservoir = sum(channels[world_channels:])
        transfers: list[tuple[int, int, int]] = []
        for _ in range(4):
            source = rng.below(channel_count)
            destination = rng.below(channel_count - 1)
            if destination >= source:
                destination += 1
            amount = rng.integer(0, channels[source])
            channels[source] -= amount
            channels[destination] += amount
            transfers.append((source, destination, amount))
        after_world = sum(channels[:world_channels])
        after_reservoir = sum(channels[world_channels:])
        world_delta = after_world - before_world
        reservoir_delta = after_reservoir - before_reservoir
        _require(min(channels) >= 0, f"negative energy account in case {case}")
        _require(world_delta + reservoir_delta == 0, f"energy ledger failed to close in case {case}")
        evidence.add(case, transfers, world_delta, reservoir_delta, sum(channels))
    return _result(cases, evidence, unified_residual=0, non_negative=True)


def sparse_aggregation(rng: SplitMix64, cases: int) -> dict[str, Any]:
    evidence = Evidence()
    components = 12  # mass, energy, px/py/pz, and seven element inventories
    for case in range(cases):
        packet_count = rng.integer(1, 8)
        packets: list[tuple[tuple[int, int, int], tuple[int, ...]]] = []
        for _ in range(packet_count):
            coordinate = tuple(rng.integer(-1_000_000, 1_000_000) for _ in range(3))
            extensive = (
                rng.integer(0, 1_000_000),
                rng.integer(0, 10_000_000),
                rng.integer(-1_000_000, 1_000_000),
                rng.integer(-1_000_000, 1_000_000),
                rng.integer(-1_000_000, 1_000_000),
                *(rng.integer(0, 1_000_000) for _ in range(7)),
            )
            packets.append((coordinate, extensive))

        direct = tuple(sum(packet[1][index] for packet in packets) for index in range(components))
        bricks: dict[tuple[int, int, int], list[int]] = {}
        for coordinate, extensive in packets:
            brick = tuple(axis // 8 for axis in coordinate)
            aggregate = bricks.setdefault(brick, [0] * components)
            for index, value in enumerate(extensive):
                aggregate[index] += value
        hierarchical = tuple(sum(values[index] for values in bricks.values()) for index in range(components))
        _require(hierarchical == direct, f"hierarchical aggregation changed extensive state in case {case}")
        evidence.add(case, packet_count, direct, sorted((key, tuple(value)) for key, value in bricks.items()))
    return _result(cases, evidence, components=components, residual=[0] * components)


def dynamic_similarity(rng: SplitMix64, cases: int) -> dict[str, Any]:
    evidence = Evidence()
    for case in range(cases):
        length = Fraction(rng.integer(1, 1_000_000), rng.integer(1, 10_000))
        velocity = Fraction(rng.integer(1, 1_000_000), rng.integer(1, 10_000))
        gravity = Fraction(rng.integer(1, 1_000_000), rng.integer(1, 10_000))
        viscosity = Fraction(rng.integer(1, 1_000_000), rng.integer(1, 10_000))
        diffusivity = Fraction(rng.integer(1, 1_000_000), rng.integer(1, 10_000))
        rate = Fraction(rng.integer(1, 1_000_000), rng.integer(1, 10_000))
        alpha = Fraction(rng.integer(1, 10_000), rng.integer(1, 10_000))
        beta = Fraction(rng.integer(1, 10_000), rng.integer(1, 10_000))

        reynolds = velocity * length / viscosity
        froude_squared = velocity * velocity / (gravity * length)
        peclet = velocity * length / diffusivity
        damkohler = rate * length / velocity

        scaled_length = alpha * length
        scaled_velocity = alpha * velocity / beta
        scaled_gravity = alpha * gravity / (beta * beta)
        scaled_viscosity = alpha * alpha * viscosity / beta
        scaled_diffusivity = alpha * alpha * diffusivity / beta
        scaled_rate = rate / beta

        scaled = (
            scaled_velocity * scaled_length / scaled_viscosity,
            scaled_velocity * scaled_velocity / (scaled_gravity * scaled_length),
            scaled_velocity * scaled_length / scaled_diffusivity,
            scaled_rate * scaled_length / scaled_velocity,
        )
        original = (reynolds, froude_squared, peclet, damkohler)
        _require(scaled == original, f"dynamic-similarity transform failed in case {case}")
        evidence.add(case, alpha, beta, original, scaled)
    return _result(cases, evidence, invariants=["Re", "Fr^2", "Pe", "Da"], residual=["0/1"] * 4)


ROTATIONS: tuple[tuple[tuple[int, int, int], ...], ...]


def _permutation_parity(permutation: tuple[int, int, int]) -> int:
    inversions = sum(
        permutation[first] > permutation[second]
        for first in range(3)
        for second in range(first + 1, 3)
    )
    return -1 if inversions % 2 else 1


def _proper_cube_rotations() -> tuple[tuple[tuple[int, int, int], ...], ...]:
    permutations = ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0))
    matrices: list[tuple[tuple[int, int, int], ...]] = []
    for permutation in permutations:
        parity = _permutation_parity(permutation)
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    if parity * sx * sy * sz != 1:
                        continue
                    signs = (sx, sy, sz)
                    rows = []
                    for row in range(3):
                        rows.append(tuple(signs[row] if column == permutation[row] else 0 for column in range(3)))
                    matrices.append(tuple(rows))
    _require(len(matrices) == 24 and len(set(matrices)) == 24, "cube rotation construction failed")
    return tuple(matrices)


ROTATIONS = _proper_cube_rotations()


def _rotate(matrix: tuple[tuple[int, int, int], ...], vector: Sequence[int]) -> tuple[int, int, int]:
    return tuple(sum(matrix[row][column] * vector[column] for column in range(3)) for row in range(3))  # type: ignore[return-value]


def rotation_equivariance(rng: SplitMix64, cases: int) -> dict[str, Any]:
    evidence = Evidence()
    for case in range(cases):
        displacement = tuple(rng.integer(-10_000, 10_000) for _ in range(3))
        if displacement == (0, 0, 0):
            displacement = (1, 0, 0)
        coefficient = rng.integer(-1_000, 1_000)
        rotation_index = rng.below(len(ROTATIONS))
        matrix = ROTATIONS[rotation_index]
        impulse = tuple(coefficient * component for component in displacement)
        rotated_displacement = _rotate(matrix, displacement)
        rotated_impulse = _rotate(matrix, impulse)
        recomputed_impulse = tuple(coefficient * component for component in rotated_displacement)
        norm_squared = sum(component * component for component in displacement)
        rotated_norm_squared = sum(component * component for component in rotated_displacement)
        _require(rotated_impulse == recomputed_impulse, f"central interaction is not rotation-equivariant in case {case}")
        _require(rotated_norm_squared == norm_squared, f"rotation changed squared distance in case {case}")
        evidence.add(case, rotation_index, displacement, coefficient, rotated_displacement, recomputed_impulse)
    return _result(cases, evidence, rotation_group_size=len(ROTATIONS), residual=[0, 0, 0])


def coarse_graining_false_affordance() -> dict[str, Any]:
    evidence = Evidence()
    fine = ({"A": 1, "B": 0}, {"A": 0, "B": 1})
    fine_reaction_sites = sum(cell["A"] > 0 and cell["B"] > 0 for cell in fine)
    coarse = {element: sum(cell[element] for cell in fine) for element in ("A", "B")}
    coarse_reaction_sites = int(coarse["A"] > 0 and coarse["B"] > 0)
    _require(coarse == {"A": 1, "B": 1}, "coarse merge did not conserve inventory")
    _require(fine_reaction_sites == 0, "fine state unexpectedly enables local reaction")
    _require(coarse_reaction_sites == 1, "counterexample failed to expose invented affordance")
    evidence.add(fine, coarse, fine_reaction_sites, coarse_reaction_sites)
    return _result(
        1,
        evidence,
        inventory_conserved=True,
        fine_local_reaction_enabled=False,
        coarse_local_reaction_enabled=True,
        conclusion="extensive conservation is necessary but insufficient for lossy physics LOD",
    )


def _state_digest(state: Mapping[str, Any]) -> str:
    data = json.dumps(state, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def _initial_reference_world(seed: int) -> dict[str, Any]:
    rng = SplitMix64(seed)
    packets = []
    for packet_id in range(8):
        packets.append(
            {
                "elements": [rng.integer(1_000, 10_000) for _ in range(4)],
                "energy": [rng.integer(1_000, 10_000) for _ in range(4)],
                "momentum": [rng.integer(-10_000, 10_000) for _ in range(3)],
                "packet_id": packet_id,
            }
        )
    return {"packets": packets, "reservoirs": [1_000_000, 1_000_000], "tick": 0}


def _step_reference_world(state: dict[str, Any], rng: SplitMix64) -> None:
    packets = state["packets"]
    first = rng.below(len(packets))
    second = rng.below(len(packets) - 1)
    if second >= first:
        second += 1
    channel = rng.below(4)
    amount = rng.integer(0, packets[first]["elements"][channel])
    packets[first]["elements"][channel] -= amount
    packets[second]["elements"][channel] += amount

    impulse = [rng.integer(-100, 100) for _ in range(3)]
    for axis in range(3):
        packets[first]["momentum"][axis] += impulse[axis]
        packets[second]["momentum"][axis] -= impulse[axis]

    source = rng.below(10)
    destination = rng.below(9)
    if destination >= source:
        destination += 1
    accounts = [packet["energy"] for packet in packets]

    def energy_ref(index: int) -> tuple[list[int], int]:
        if index < 8:
            return accounts[index], rng.below(4)
        return state["reservoirs"], index - 8

    source_account, source_channel = energy_ref(source)
    destination_account, destination_channel = energy_ref(destination)
    energy_amount = rng.integer(0, source_account[source_channel])
    source_account[source_channel] -= energy_amount
    destination_account[destination_channel] += energy_amount
    state["tick"] += 1


def _run_reference_world(seed: int, steps: int, observer: Callable[[Mapping[str, Any], int], None] | None) -> dict[str, Any]:
    state = _initial_reference_world(seed)
    dynamics_rng = SplitMix64(seed ^ 0xD1B54A32D192ED03)
    if observer is not None:
        observer(state, 0)
    for tick in range(steps):
        _step_reference_world(state, dynamics_rng)
        if observer is not None:
            observer(state, tick + 1)
    return state


def deterministic_replay(rng: SplitMix64, cases: int) -> dict[str, Any]:
    evidence = Evidence()
    for case in range(cases):
        scenario_seed = rng.next_u64()
        steps = 24 + rng.below(41)
        first = _run_reference_world(scenario_seed, steps, None)
        second = _run_reference_world(scenario_seed, steps, None)
        first_hash = _state_digest(first)
        second_hash = _state_digest(second)
        _require(first_hash == second_hash and first == second, f"deterministic replay diverged in case {case}")
        evidence.add(case, scenario_seed, steps, first_hash)
    return _result(cases, evidence, replay_match=True)


def camera_invariance(rng: SplitMix64, cases: int) -> dict[str, Any]:
    evidence = Evidence()
    for case in range(cases):
        scenario_seed = rng.next_u64()
        steps = 16 + rng.below(33)
        observation_hash = hashlib.sha256()

        def arbitrary_camera_observer(state: Mapping[str, Any], tick: int) -> None:
            # Camera parameters are deliberately consumed only here, outside dynamics.
            camera = (
                rng.integer(-1_000_000, 1_000_000),
                rng.integer(-1_000_000, 1_000_000),
                rng.integer(-1_000_000, 1_000_000),
                rng.integer(1, 179),
            )
            observation_hash.update(f"{tick}:{camera}:{_state_digest(state)}".encode("ascii"))

        renderer_disabled = _run_reference_world(scenario_seed, steps, None)
        observed = _run_reference_world(scenario_seed, steps, arbitrary_camera_observer)
        disabled_hash = _state_digest(renderer_disabled)
        observed_hash = _state_digest(observed)
        _require(disabled_hash == observed_hash and renderer_disabled == observed, f"camera affected physics in case {case}")
        evidence.add(case, scenario_seed, steps, disabled_hash, observation_hash.hexdigest())
    return _result(cases, evidence, renderer_disabled_hash_match=True, camera_is_observer_only=True)


def exploit_quarantine_matrix() -> dict[str, Any]:
    evidence = Evidence()
    controls = (
        ("timestep_refinement", "rerun at smaller timestep"),
        ("spatial_refinement", "rerun at finer physical resolution"),
        ("grid_rotation", "rerun under proper cubic rotations and off-axis orientations"),
        ("strict_arithmetic", "rerun with stricter deterministic arithmetic"),
        ("alternate_solver", "rerun with an independent solver where practical"),
        ("unified_ledger", "audit complete matter, element, momentum, and energy ledgers"),
    )
    for control in controls:
        evidence.add(control)
    return _result(len(controls), evidence, controls=[{"id": item[0], "requirement": item[1]} for item in controls])


def run_extension_suite(mode: str) -> dict[str, Any]:
    counts = COUNTS[mode]
    # A separate substream per test prevents changing one test's case count from
    # silently changing every later test's witnesses.
    root_rng = SplitMix64(SEED)

    def stream() -> SplitMix64:
        return SplitMix64(root_rng.next_u64())

    results = {
        "camera_invariance": camera_invariance(stream(), counts.camera_invariance_runs),
        "coarse_graining_false_affordance": coarse_graining_false_affordance(),
        "conservative_pair_transfers": conservative_pair_transfers(stream(), counts.conservative_pair_transfers),
        "deterministic_replay": deterministic_replay(stream(), counts.deterministic_replays),
        "dynamic_similarity": dynamic_similarity(stream(), counts.dynamic_similarity_transforms),
        "energy_ledger_closure": energy_ledger_closure(stream(), counts.energy_ledger_conversions),
        "exploit_quarantine_matrix": exploit_quarantine_matrix(),
        "momentum_exchanges": momentum_exchanges(stream(), counts.momentum_exchanges),
        "rotation_equivariance": rotation_equivariance(stream(), counts.rotation_equivariance_cases),
        "sparse_aggregation": sparse_aggregation(stream(), counts.sparse_aggregations),
        "stoichiometric_balance": stoichiometric_balance(stream(), counts.reaction_extents),
    }
    # These are coverage statements, not claims that empirical gates have passed.
    gate_coverage = {
        "G0_formal_accounting": {
            "coverage": "reference-oracle",
            "tests": ["conservative_pair_transfers", "momentum_exchanges", "energy_ledger_closure", "stoichiometric_balance"],
        },
        "G1_conservation_stress": {
            "coverage": "reference-oracle",
            "tests": ["conservative_pair_transfers", "momentum_exchanges", "energy_ledger_closure", "sparse_aggregation"],
        },
        "G2_mechanics_benchmarks": {
            "coverage": "scaffold-only",
            "tests": ["momentum_exchanges", "rotation_equivariance"],
        },
        "G3_transport": {
            "coverage": "accounting-only",
            "tests": ["conservative_pair_transfers", "energy_ledger_closure"],
        },
        "G4_chemistry": {"coverage": "stoichiometry-only", "tests": ["stoichiometric_balance"]},
        "G5_rotation_isotropy": {"coverage": "cubic-rotation-scaffold", "tests": ["rotation_equivariance"]},
        "G6_fracture_cutting": {"coverage": "not-covered", "tests": []},
        "G7_affordance_gauntlet": {
            "coverage": "coarse-graining-counterexample-only",
            "tests": ["coarse_graining_false_affordance"],
        },
    }
    return {
        "arithmetic": "exact integer quanta and fractions.Fraction; no floating point",
        "gate_coverage": gate_coverage,
        "mode": mode,
        "prng": "SplitMix64",
        "results": results,
        "schema": SCHEMA,
        "seed": SEED,
        "status": "pass",
        "suite_version": SUITE_VERSION,
    }


def run_suite(mode: str) -> dict[str, Any]:
    return {
        "extensions": run_extension_suite(mode),
        "mode": mode,
        "provenance_v0": run_provenance_suite(mode),
        "schema": SCHEMA,
        "seed": SEED,
        "status": "pass",
        "suite_version": SUITE_VERSION,
    }


def canonical_payload_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("ascii")


def seal(payload: dict[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()
    return {**payload, "pre_hash_sha256": digest}


def canonical_output_bytes(output: Mapping[str, Any]) -> bytes:
    return canonical_payload_bytes(output) + b"\n"


def provenance_output_bytes(output: Mapping[str, Any]) -> bytes:
    return (json.dumps(output, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("ascii")


def _verify_seal(output: Mapping[str, Any]) -> None:
    expected = output.get("pre_hash_sha256")
    payload = {key: value for key, value in output.items() if key != "pre_hash_sha256"}
    actual = hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()
    _require(isinstance(expected, str) and expected == actual, "stored pre-hash does not match canonical payload")


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=sorted(COUNTS), default="quick")
    parser.add_argument("--output", type=Path, help="write canonical JSON to this path")
    parser.add_argument("--verify", type=Path, help="compare generated canonical JSON with this file")
    parser.add_argument(
        "--provenance-only",
        action="store_true",
        help="emit the historical v0 result only (full mode matches reference/validation_results_v0.json)",
    )
    parser.add_argument("--print-json", action="store_true", help="print canonical JSON instead of a one-line summary")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if arguments.provenance_only:
            output = run_provenance_suite(arguments.mode)
            encoded = provenance_output_bytes(output)
            displayed_hash = output["result_sha256_before_hash_field"]
        else:
            output = seal(run_suite(arguments.mode))
            _verify_seal(output)
            encoded = canonical_output_bytes(output)
            displayed_hash = output["pre_hash_sha256"]
        if arguments.output is not None:
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_bytes(encoded)
        if arguments.verify is not None:
            expected = arguments.verify.read_bytes()
            _require(expected == encoded, f"canonical output differs from {arguments.verify}")
        if arguments.print_json:
            sys.stdout.buffer.write(encoded)
        else:
            print(
                f"MLS exact validation: PASS mode={arguments.mode} seed={SEED} "
                f"pre_hash_sha256={displayed_hash}"
            )
        return 0
    except (OSError, ValidationFailure, ValueError) as error:
        print(f"MLS exact validation: FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
