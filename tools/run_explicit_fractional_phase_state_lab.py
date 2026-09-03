#!/usr/bin/env python3
"""Materialize the Explicit Fractional Phase-State Lab raw evidence.

The candidate phase state is exact reduced ``gmpy2.mpq`` arithmetic.  Binary64
is used only by the frozen Path-B force geometry and constitutive evaluation;
the resulting relation length and conjugate bit patterns are reconstructed as
exact rationals before the authoritative central impulse is formed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import shutil
import statistics
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

try:
    import gmpy2
    from gmpy2 import mpq as Fraction
except ImportError as error:
    raise SystemExit(
        "gmpy2 2.3.1 is required for exact rational evidence materialization"
    ) from error

if gmpy2.version() != "2.3.1":
    raise SystemExit(
        f"gmpy2 2.3.1 is required; found {gmpy2.version()}"
    )


if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)


PARENT_SHA = "6dfaf29821ded7e1349358c671b52e73f345c26a"
PARENT_TAG = "phase-space-time-corefinement-lab-evidence-v1"
PARENT_TAG_OBJECT = "b4df81ae41b9b341ae49f564e784976f8b731084"
PARENT_ARCHIVE_SHA256 = (
    "cf3427082fc66426c4074e615decbc5353ba0bc216a1b480f0c688e18f8f3c8d"
)
PARENT_ARCHIVE_SIZE = 4_481_719
BRANCH = "explicit-fractional-phase-state-lab"
KDK = "fractional_kick_drift_kick"
CONTROL = "fractional_symplectic_euler_control"
LEVELS = tuple(range(5))
TIMESTEPS_RAW = (62_500_000, 31_250_000, 15_625_000, 7_812_500, 3_906_250)
STEP_COUNTS = (16, 32, 64, 128, 256)
SCENARIOS = ("k4_breathing", "k4_internal", "octahedron_deformation")

LQ = Fraction(1, 128_000_000_000)
MQ = Fraction(1, 524_288)
TQ = Fraction(1, 1_000_000_000)
PQ = Fraction(1, 67_108_864)
EQ = Fraction(1, 8_589_934_592)
FQ = Fraction(1_953_125, 131_072)
SAFE_SQUARED_RATIO = Fraction(1, 2**48)
SIGNED64_MIN = -(2**63)
SIGNED64_MAX = 2**63 - 1

MAX_COMPONENT_BITS = 262_144
MEDIAN_COMPONENT_BITS = 131_072
MAX_CHECKPOINT_BYTES = 8_388_608

PARENT_HASHES = {
    "bridge_contracts.csv": "93a5730fb67023b089366893dafe9f34be983e03abdf4ba5c6cb4fefd0a7366d",
    "checkpoint.csv": "1429269754b0e5583e518c75fa50866e65b6a161f350c23d7c93f09f39b99f04",
    "covariance.csv": "7f9eaa75cd4c2efcc475dc5fbc08de6f15ffa26b07a47d0f867784f7fab4c705",
    "domain.csv": "298741726b34711257526b5c4ca604a90924acacdc16c5830913eeb37bc06a8a",
    "endpoints.csv": "20712bdf438f55cc74638eb40a2539799d7b324349a9f3ae61acf68a53aaf972",
    "energies.csv": "55b6510995a99d60b578d33bade20f061676804cb80012b72a46e0ab2fa74772",
    "force_operator.csv": "d5d9a19ea6f8a5cdd25810f2e6a1e35ed039e45463d56a3f208c8b9151698ed7",
    "initial_states.csv": "c018a437ab10e8f6786fcfe8ff0be4bbad45dbc3a83118b8dfef46b275b4ad21",
    "long_energy.csv": "4251e29b09b922c76d487b9884fc5e560f73cf0a2eed083ffbc85fd3a6566099",
    "mapping.csv": "129668990414470cf33cdc234177896562acd34b800440a85e4867ca5a4d856f",
    "metadata.csv": "8b7a456878b2d8e3f75550cb8cb434f9e861c5e6f4249d46dda8045fca3d5cb0",
    "parent_fingerprint.csv": "9802cf098a77f21b2d30e9abc8c045cd2425efcf0e2d47f7bd2d31bbc2f73e4f",
    "primitive_diagnostics.csv": "7bc891be789f853566757009855317569a96e29b1ff99250bea7808b0470f858",
    "reference_packets.csv": "907cc08a3f6a8db48143e35d0ee247dccf687cc42ba617f28ff213219312994f",
    "relation_primitive_diagnostics.csv": "aed093b5e8329bb9e5d16de5619e546e37675fb2cfeb7b7097f9283b0bec4399",
    "relations.csv": "5b50a04399f9868a9fdc0fe3e263e162aa3a4d52b0be03b11a6cb17a689bece0",
    "reversibility.csv": "5dd215fbe8e6c9743dd072cf43791410ceacf6ab8ef2d1c3107fece759752c28",
    "units.csv": "5f7310161e356739c5bf0989b47c58fe35eb5d5241f7e3542da276f1d77c0e77",
}


class LabError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LabError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_rows(path: Path, fields: tuple[str, ...], rows: Iterable[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: str(row.get(key, "")) for key in fields})


def ratio_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def float_bits(value: float) -> int:
    return struct.unpack(">Q", struct.pack(">d", value))[0]


def float_from_bits(value: str | int) -> float:
    return struct.unpack(">d", struct.pack(">Q", int(value)))[0]


def exact_float(value: float) -> Fraction:
    require(math.isfinite(value), "nonfinite binary64 cannot enter exact state")
    return Fraction(*value.as_integer_ratio())


def clone_vector(value: list[Fraction]) -> list[Fraction]:
    return list(value)


@dataclass
class Packet:
    identifier: int
    mass_raw: int
    x: list[Fraction]
    p: list[Fraction]

    def clone(self) -> "Packet":
        return Packet(self.identifier, self.mass_raw, clone_vector(self.x), clone_vector(self.p))


@dataclass
class State:
    time_raw: int
    packets: list[Packet]

    def clone(self) -> "State":
        return State(self.time_raw, [packet.clone() for packet in self.packets])


@dataclass(frozen=True)
class Relation:
    index: int
    first_id: int
    second_id: int
    rest_length: float


@dataclass
class Model:
    identifier: str
    reference: dict[int, list[Fraction]]
    masses_raw: dict[int, int]
    relations: list[Relation]
    h: list[list[float]]


@dataclass
class ForceRelation:
    relation: Relation
    offset_raw: list[Fraction]
    length: float
    conjugate: float
    extension: float


@dataclass
class RunResult:
    status: str
    initial: State
    final: State
    requested_steps: int
    completed_steps: int
    energies: list[float]
    events: list[str]
    complexity_exceeded: bool


def canonical_packets(state: State) -> list[Packet]:
    packets = sorted((packet.clone() for packet in state.packets), key=lambda value: value.identifier)
    require(len({packet.identifier for packet in packets}) == len(packets), "duplicate packet ID")
    require(all(packet.identifier > 0 and packet.mass_raw > 0 for packet in packets), "invalid packet")
    return packets


def floor_fraction(value: Fraction) -> int:
    return value.numerator // value.denominator


def split_raw(value: Fraction) -> tuple[int, Fraction]:
    coarse = floor_fraction(value + Fraction(1, 2))
    require(SIGNED64_MIN <= coarse <= SIGNED64_MAX, "fractional state coarse carry overflow")
    residual = value - coarse
    require(Fraction(-1, 2) <= residual < Fraction(1, 2), "noncanonical residual")
    require(residual.denominator > 0, "nonpositive residual denominator")
    return coarse, residual


def encode_unsigned(value: int) -> bytes:
    require(value >= 0, "negative unsigned integer")
    magnitude = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return len(magnitude).to_bytes(8, "little") + magnitude


def encode_signed(value: int) -> bytes:
    return (b"\x01" if value < 0 else b"\x00") + encode_unsigned(abs(value))


def encode_fraction(value: Fraction) -> bytes:
    return encode_signed(value.numerator) + encode_unsigned(value.denominator)


def encode_state(state: State) -> bytes:
    output = bytearray(b"MLS-FRACTIONAL-PHASE-v1\x00")
    output.extend(encode_signed(state.time_raw))
    packets = canonical_packets(state)
    output.extend(len(packets).to_bytes(8, "little"))
    for packet in packets:
        output.extend(packet.identifier.to_bytes(8, "little"))
        output.extend(packet.mass_raw.to_bytes(8, "little", signed=True))
        for vector in (packet.x, packet.p):
            for value in vector:
                coarse, residual = split_raw(value)
                output.extend(coarse.to_bytes(8, "little", signed=True))
                output.extend(encode_fraction(residual))
    return bytes(output)


def decode_state(data: bytes) -> State:
    prefix = b"MLS-FRACTIONAL-PHASE-v1\x00"
    require(data.startswith(prefix), "checkpoint magic differs")
    cursor = len(prefix)

    def unsigned() -> int:
        nonlocal cursor
        require(cursor + 8 <= len(data), "truncated checkpoint length")
        count = int.from_bytes(data[cursor:cursor + 8], "little")
        cursor += 8
        require(cursor + count <= len(data), "truncated checkpoint magnitude")
        require(count == 0 or data[cursor] != 0, "nonminimal checkpoint magnitude")
        value = int.from_bytes(data[cursor:cursor + count], "big")
        cursor += count
        return value

    def signed() -> int:
        nonlocal cursor
        require(cursor < len(data) and data[cursor] in (0, 1), "invalid checkpoint sign")
        negative = data[cursor] == 1
        cursor += 1
        value = unsigned()
        require(not (negative and value == 0), "negative checkpoint zero")
        return -value if negative else value

    def fraction() -> Fraction:
        numerator = signed()
        denominator = unsigned()
        require(denominator > 0, "zero checkpoint denominator")
        result = Fraction(numerator, denominator)
        require(result.numerator == numerator and result.denominator == denominator,
                "unreduced checkpoint fraction")
        return result

    time_raw = signed()
    require(cursor + 8 <= len(data), "truncated checkpoint packet count")
    count = int.from_bytes(data[cursor:cursor + 8], "little")
    cursor += 8
    packets: list[Packet] = []
    for _ in range(count):
        require(cursor + 16 <= len(data), "truncated checkpoint packet")
        identifier = int.from_bytes(data[cursor:cursor + 8], "little")
        cursor += 8
        mass_raw = int.from_bytes(data[cursor:cursor + 8], "little", signed=True)
        cursor += 8
        vectors: list[list[Fraction]] = []
        for _kind in range(2):
            vector: list[Fraction] = []
            for _axis in range(3):
                require(cursor + 8 <= len(data), "truncated checkpoint coarse value")
                coarse = int.from_bytes(data[cursor:cursor + 8], "little", signed=True)
                cursor += 8
                residual = fraction()
                require(Fraction(-1, 2) <= residual < Fraction(1, 2),
                        "checkpoint residual outside canonical interval")
                vector.append(Fraction(coarse) + residual)
            vectors.append(vector)
        packets.append(Packet(identifier, mass_raw, vectors[0], vectors[1]))
    require(cursor == len(data), "checkpoint trailing bytes")
    state = State(time_raw, packets)
    require(encode_state(state) == data, "checkpoint canonical round trip differs")
    return state


def state_hash(state: State) -> str:
    return hashlib.sha256(encode_state(state)).hexdigest()


def fraction_hash(value: Fraction) -> str:
    return hashlib.sha256(encode_fraction(value)).hexdigest()


def rational_vector_hash(value: Iterable[Fraction]) -> str:
    digest = hashlib.sha256()
    for component in value:
        digest.update(encode_fraction(component))
    return digest.hexdigest()


def vector_add(first: list[Fraction], second: list[Fraction]) -> list[Fraction]:
    return [first[axis] + second[axis] for axis in range(3)]


def vector_sub(first: list[Fraction], second: list[Fraction]) -> list[Fraction]:
    return [first[axis] - second[axis] for axis in range(3)]


def vector_scale(scale: Fraction, value: list[Fraction]) -> list[Fraction]:
    return [scale * component for component in value]


def dot(first: list[Fraction], second: list[Fraction]) -> Fraction:
    return sum((first[axis] * second[axis] for axis in range(3)), Fraction())


def cross(first: list[Fraction], second: list[Fraction]) -> list[Fraction]:
    return [
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    ]


def exact_invariants(state: State) -> tuple[list[Fraction], list[Fraction]]:
    momentum = [Fraction(), Fraction(), Fraction()]
    angular = [Fraction(), Fraction(), Fraction()]
    for packet in state.packets:
        momentum = vector_add(momentum, packet.p)
        angular = vector_add(angular, cross(packet.x, packet.p))
    return momentum, angular


def invariant_hash(value: tuple[list[Fraction], list[Fraction]]) -> tuple[str, str]:
    return rational_vector_hash(value[0]), rational_vector_hash(value[1])


def _quick_two_sum(larger: float, smaller: float) -> tuple[float, float]:
    total = larger + smaller
    return total, smaller - (total - larger)


def _two_sum(first: float, second: float) -> tuple[float, float]:
    total = first + second
    virtual_second = total - first
    error = (first - (total - virtual_second)) + (second - virtual_second)
    return total, error


def _two_difference(first: float, second: float) -> tuple[float, float]:
    difference = first - second
    virtual_second = first - difference
    error = (first - (difference + virtual_second)) + (virtual_second - second)
    return difference, error


def _dd_add(first: tuple[float, float], second: tuple[float, float]) -> tuple[float, float]:
    total = first[0] + second[0]
    virtual_second = total - first[0]
    error = (first[0] - (total - virtual_second)) + (second[0] - virtual_second)
    error += first[1] + second[1]
    return _quick_two_sum(total, error)


def _dd_sub(first: tuple[float, float], second: tuple[float, float]) -> tuple[float, float]:
    return _dd_add(first, (-second[0], -second[1]))


def _dd_mul(first: tuple[float, float], second: tuple[float, float]) -> tuple[float, float]:
    product = first[0] * second[0]
    error = math.fma(first[0], second[0], -product)
    error += first[0] * second[1] + first[1] * second[0]
    error += first[1] * second[1]
    return _quick_two_sum(product, error)


def _dd_div(numerator: tuple[float, float], denominator: tuple[float, float]) -> tuple[float, float]:
    require(denominator[0] != 0.0, "Path-B double-double division by zero")
    quotient = (numerator[0] / denominator[0], 0.0)
    for _ in range(2):
        residual = _dd_sub(numerator, _dd_mul(denominator, quotient))
        quotient = _dd_add(quotient, (residual[0] / denominator[0], 0.0))
    return _quick_two_sum(quotient[0], quotient[1])


def stable_norm(value: list[float]) -> float:
    scale = max(abs(value[0]), abs(value[1]), abs(value[2]))
    if scale == 0.0:
        return 0.0
    normalized = [component / scale for component in value]
    squared = normalized[0] * normalized[0]
    squared += normalized[1] * normalized[1]
    squared += normalized[2] * normalized[2]
    return scale * math.sqrt(squared)


def path_b_geometry(current_raw: list[Fraction], reference_raw: list[Fraction],
                    frozen_reference_length: float) -> tuple[float, float, list[float]]:
    current = [float(component * LQ) for component in current_raw]
    reference = [float(component * LQ) for component in reference_raw]
    length = stable_norm(current)
    require(length > 0.0 and math.isfinite(length), "unresolved fractional relation length")
    numerator = (0.0, 0.0)
    for axis in range(3):
        difference = _two_difference(current[axis], reference[axis])
        total = _two_sum(current[axis], reference[axis])
        numerator = _dd_add(numerator, _dd_mul(difference, total))
    denominator = length + frozen_reference_length
    require(denominator > 0.0 and math.isfinite(denominator), "invalid Path-B denominator")
    extension = _dd_div(numerator, (denominator, 0.0))[0]
    direction = [component / length for component in current]
    require(math.isfinite(extension) and all(math.isfinite(value) for value in direction),
            "nonfinite Path-B geometry")
    return length, extension, direction


def packet_lookup(state: State) -> dict[int, Packet]:
    return {packet.identifier: packet for packet in state.packets}


def relation_offset(state: State, relation: Relation) -> list[Fraction]:
    lookup = packet_lookup(state)
    return vector_sub(lookup[relation.second_id].x, lookup[relation.first_id].x)


def reference_offset(model: Model, relation: Relation) -> list[Fraction]:
    return vector_sub(model.reference[relation.second_id], model.reference[relation.first_id])


def relation_is_safe(offset: list[Fraction], reference: list[Fraction]) -> bool:
    reference_squared = dot(reference, reference)
    return reference_squared > 0 and dot(offset, offset) >= SAFE_SQUARED_RATIO * reference_squared


def chord_is_safe(initial: list[Fraction], final: list[Fraction],
                  reference: list[Fraction]) -> bool:
    delta = vector_sub(final, initial)
    delta_squared = dot(delta, delta)
    parameter = Fraction()
    if delta_squared > 0:
        parameter = -dot(initial, delta) / delta_squared
        parameter = max(Fraction(), min(Fraction(1), parameter))
    minimum = vector_add(initial, vector_scale(parameter, delta))
    return relation_is_safe(minimum, reference)


def force_and_energy(model: Model, state: State) -> tuple[list[ForceRelation], float]:
    geometry: list[tuple[Relation, list[Fraction], float, float]] = []
    for relation in model.relations:
        current = relation_offset(state, relation)
        reference = reference_offset(model, relation)
        require(relation_is_safe(current, reference), "force_domain_failure")
        length, extension, _direction = path_b_geometry(current, reference, relation.rest_length)
        geometry.append((relation, current, length, extension))
    conjugates: list[float] = []
    for row in range(len(model.relations)):
        value = 0.0
        for column in range(len(model.relations)):
            value += model.h[row][column] * geometry[column][3]
        require(math.isfinite(value), "nonfinite force conjugate")
        conjugates.append(value)
    energy_twice = 0.0
    for index, entry in enumerate(geometry):
        energy_twice += entry[3] * conjugates[index]
    require(math.isfinite(energy_twice), "nonfinite accepted potential")
    relations = [
        ForceRelation(entry[0], entry[1], entry[2], conjugates[index], entry[3])
        for index, entry in enumerate(geometry)
    ]
    return relations, 0.5 * energy_twice


def kinetic_energy_exact(state: State) -> Fraction:
    result = Fraction()
    for packet in state.packets:
        physical_squared = dot(packet.p, packet.p) * PQ * PQ
        physical_mass = packet.mass_raw * MQ
        result += physical_squared / (2 * physical_mass)
    return result


def mechanical_energy(model: Model, state: State) -> float:
    _relations, potential = force_and_energy(model, state)
    return float(kinetic_energy_exact(state)) + potential


def validate_state(state: State) -> None:
    require(state.time_raw >= SIGNED64_MIN and state.time_raw <= SIGNED64_MAX,
            "fractional state time overflow")
    require(len(canonical_packets(state)) == len(state.packets), "packet canonicalization failed")
    for packet in state.packets:
        for value in packet.x + packet.p:
            split_raw(value)


def record_invariant(rows: list[dict[str, object]], trajectory: str, level: int,
                     step: int, stage: str, state: State,
                     initial: tuple[list[Fraction], list[Fraction]]) -> None:
    current = exact_invariants(state)
    momentum_hash, angular_hash = invariant_hash(current)
    rows.append({
        "trajectory_id": trajectory,
        "level": level,
        "step": step,
        "stage": stage,
        "momentum_hash": momentum_hash,
        "angular_hash": angular_hash,
        "momentum_equal_initial": str(current[0] == initial[0]).lower(),
        "angular_equal_initial": str(current[1] == initial[1]).lower(),
    })
    require(current == initial, "fractional exact invariant changed")


def complexity_rows(state: State, trajectory: str, level: int, step: int,
                    phase_rows: list[dict[str, object]]) -> tuple[int, float, int, bool]:
    bit_lengths: list[int] = []
    checkpoint_bytes = len(encode_state(state))
    for packet in canonical_packets(state):
        for kind, vector in (("position", packet.x), ("momentum", packet.p)):
            for axis, value in zip("xyz", vector):
                _coarse, residual = split_raw(value)
                numerator_bits = abs(residual.numerator).bit_length()
                denominator_bits = residual.denominator.bit_length()
                bit_lengths.extend((numerator_bits, denominator_bits))
                phase_rows.append({
                    "trajectory_id": trajectory,
                    "level": level,
                    "step": step,
                    "time_raw": state.time_raw,
                    "packet_id": packet.identifier,
                    "phase": kind,
                    "axis": axis,
                    "residual_hash": fraction_hash(residual),
                    "numerator_bits": numerator_bits,
                    "denominator_bits": denominator_bits,
                    "checkpoint_bytes": checkpoint_bytes,
                })
    maximum = max(bit_lengths, default=0)
    median = statistics.median(bit_lengths) if bit_lengths else 0.0
    exceeded = maximum > MAX_COMPONENT_BITS or median > MEDIAN_COMPONENT_BITS or checkpoint_bytes > MAX_CHECKPOINT_BYTES
    return maximum, median, checkpoint_bytes, exceeded


def kick(model: Model, state: State, interval_raw: int, trajectory: str, level: int,
         step: int, stage: str, force_rows: list[dict[str, object]] | None) -> State:
    result = state.clone()
    relations, _potential = force_and_energy(model, state)
    lookup = packet_lookup(result)
    dt = interval_raw * TQ
    for evaluated in relations:
        require(evaluated.length > 0.0, "zero binary64 relation length")
        coefficient = dt * exact_float(evaluated.conjugate) / exact_float(evaluated.length)
        delta_raw = vector_scale(coefficient * LQ / PQ, evaluated.offset_raw)
        central_cross = cross(delta_raw, evaluated.offset_raw)
        require(central_cross == [Fraction(), Fraction(), Fraction()],
                "fractional impulse lost exact centrality")
        first = lookup[evaluated.relation.first_id]
        second = lookup[evaluated.relation.second_id]
        first.p = vector_add(first.p, delta_raw)
        second.p = vector_sub(second.p, delta_raw)
        if force_rows is not None:
            coefficient_bits = max(abs(coefficient.numerator).bit_length(), coefficient.denominator.bit_length())
            impulse_bits = max(
                max(abs(component.numerator).bit_length(), component.denominator.bit_length())
                for component in delta_raw
            )
            force_rows.append({
                "trajectory_id": trajectory,
                "level": level,
                "step": step,
                "stage": stage,
                "relation_index": evaluated.relation.index,
                "first_id": evaluated.relation.first_id,
                "second_id": evaluated.relation.second_id,
                "length_bits": float_bits(evaluated.length),
                "conjugate_bits": float_bits(evaluated.conjugate),
                "coefficient_hash": fraction_hash(coefficient),
                "coefficient_bits": coefficient_bits,
                "impulse_hash": rational_vector_hash(delta_raw),
                "impulse_bits": impulse_bits,
                "central_cross_zero": "true",
            })
    validate_state(result)
    return result


def drift(model: Model, state: State, interval_raw: int) -> State:
    result = state.clone()
    initial_offsets = [relation_offset(state, relation) for relation in model.relations]
    for packet in result.packets:
        displacement = vector_scale(Fraction(interval_raw, packet.mass_raw), packet.p)
        packet.x = vector_add(packet.x, displacement)
    for relation, initial in zip(model.relations, initial_offsets):
        final = relation_offset(result, relation)
        reference = reference_offset(model, relation)
        require(chord_is_safe(initial, final, reference), "chord_domain_failure")
    validate_state(result)
    return result


def one_step(model: Model, state: State, interval_raw: int, path: str,
             trajectory: str, level: int, step: int,
             invariant_rows: list[dict[str, object]] | None,
             force_rows: list[dict[str, object]] | None,
             initial_invariants: tuple[list[Fraction], list[Fraction]]) -> tuple[str, State]:
    prior = state.clone()
    try:
        force_and_energy(model, prior)
        if path == KDK:
            require(interval_raw % 2 == 0, "fractional KDK half-step is not integral time")
            work = kick(model, prior, interval_raw // 2, trajectory, level, step,
                        "first_kick", force_rows)
            if invariant_rows is not None:
                record_invariant(invariant_rows, trajectory, level, step, "first_kick", work, initial_invariants)
            work = drift(model, work, interval_raw)
            if invariant_rows is not None:
                record_invariant(invariant_rows, trajectory, level, step, "drift", work, initial_invariants)
            work = kick(model, work, interval_raw // 2, trajectory, level, step,
                        "second_kick", force_rows)
            if invariant_rows is not None:
                record_invariant(invariant_rows, trajectory, level, step, "second_kick", work, initial_invariants)
        elif path == CONTROL:
            work = kick(model, prior, interval_raw, trajectory, level, step,
                        "full_kick", force_rows)
            if invariant_rows is not None:
                record_invariant(invariant_rows, trajectory, level, step, "full_kick", work, initial_invariants)
            work = drift(model, work, interval_raw)
            if invariant_rows is not None:
                record_invariant(invariant_rows, trajectory, level, step, "drift", work, initial_invariants)
        else:
            raise LabError("unknown fractional integrator path")
        work.time_raw += interval_raw
        validate_state(work)
        if invariant_rows is not None:
            record_invariant(invariant_rows, trajectory, level, step, "committed", work, initial_invariants)
        return "accepted", work
    except LabError as error:
        if str(error) in {"force_domain_failure", "chord_domain_failure"}:
            require(encode_state(prior) == encode_state(state), "domain rejection mutated prior state")
            return str(error), prior
        raise


def run_trajectory(model: Model, initial: State, interval_raw: int, steps: int,
                   path: str, trajectory: str, level: int,
                   invariant_rows: list[dict[str, object]] | None = None,
                   force_rows: list[dict[str, object]] | None = None,
                   phase_rows: list[dict[str, object]] | None = None,
                   enforce_complexity: bool = True) -> RunResult:
    state = initial.clone()
    initial_invariants = exact_invariants(state)
    energies = [mechanical_energy(model, state)]
    events: list[str] = []
    complexity_exceeded = False
    if invariant_rows is not None:
        record_invariant(invariant_rows, trajectory, level, 0, "initial", state, initial_invariants)
    if phase_rows is not None:
        _maximum, _median, _bytes, complexity_exceeded = complexity_rows(
            state, trajectory, level, 0, phase_rows)
    completed = 0
    status = "accepted"
    for step in range(1, steps + 1):
        status, next_state = one_step(
            model, state, interval_raw, path, trajectory, level, step,
            invariant_rows, force_rows, initial_invariants)
        if status != "accepted":
            break
        state = next_state
        completed = step
        events.append(state_hash(state))
        energies.append(mechanical_energy(model, state))
        if phase_rows is not None:
            _maximum, _median, _bytes, exceeded = complexity_rows(
                state, trajectory, level, step, phase_rows)
            complexity_exceeded = complexity_exceeded or exceeded
            if enforce_complexity and exceeded:
                status = "complexity_budget_exceeded"
                break
    return RunResult(status, initial.clone(), state, steps, completed, energies,
                     events, complexity_exceeded)


def relative_maximum(first: State, second: State, momentum: bool = False) -> Fraction:
    first_packets = canonical_packets(first)
    second_packets = canonical_packets(second)
    require([value.identifier for value in first_packets] == [value.identifier for value in second_packets],
            "covariance packet IDs differ")
    vectors_first = [value.p if momentum else value.x for value in first_packets]
    vectors_second = [value.p if momentum else value.x for value in second_packets]
    maximum = Fraction()
    for index in range(1, len(first_packets)):
        for axis in range(3):
            first_relative = vectors_first[index][axis] - vectors_first[0][axis]
            second_relative = vectors_second[index][axis] - vectors_second[0][axis]
            maximum = max(maximum, abs(first_relative - second_relative))
    return maximum


def inverse_rotate_state(state: State) -> State:
    result = state.clone()
    for packet in result.packets:
        packet.x = [packet.x[1], -packet.x[0], packet.x[2]]
        packet.p = [packet.p[1], -packet.p[0], packet.p[2]]
    return result


def full_state_row(prefix: dict[str, object], packet: Packet) -> dict[str, object]:
    row = dict(prefix)
    row.update({"packet_id": packet.identifier, "mass_raw": packet.mass_raw})
    for name, vector in (("x", packet.x), ("p", packet.p)):
        for axis, value in zip("xyz", vector):
            coarse, residual = split_raw(value)
            row[f"{name}{axis}_coarse"] = coarse
            row[f"{name}{axis}_num"] = residual.numerator
            row[f"{name}{axis}_den"] = residual.denominator
    return row


STATE_FIELDS = (
    "scenario_id", "model_id", "path", "level", "dt_raw", "steps", "status",
    "completed_steps", "time_raw", "state_hash", "packet_id", "mass_raw",
    "xx_coarse", "xx_num", "xx_den", "xy_coarse", "xy_num", "xy_den",
    "xz_coarse", "xz_num", "xz_den", "px_coarse", "px_num", "px_den",
    "py_coarse", "py_num", "py_den", "pz_coarse", "pz_num", "pz_den",
)


def verify_parent(parent_raw: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for filename, expected in sorted(PARENT_HASHES.items()):
        path = parent_raw / filename
        require(path.is_file(), f"parent raw missing {filename}")
        actual = sha256_file(path)
        rows.append({"file": filename, "sha256": actual, "expected_sha256": expected,
                     "passed": str(actual == expected).lower()})
        require(actual == expected, f"stop_inconclusive_or_wrong_parent: {filename}")
    return rows


def load_models(parent_raw: Path) -> dict[str, Model]:
    references: dict[str, dict[int, list[Fraction]]] = {}
    masses: dict[str, dict[int, int]] = {}
    for row in read_rows(parent_raw / "reference_packets.csv"):
        if row["level"] != "0":
            continue
        model_id = row["model_id"]
        identifier = int(row["packet_id"])
        references.setdefault(model_id, {})[identifier] = [
            Fraction(int(row[f"{axis}_raw"])) for axis in "xyz"
        ]
        masses.setdefault(model_id, {})[identifier] = int(row["mass_raw"])
    relation_groups: dict[str, list[Relation]] = {}
    for row in read_rows(parent_raw / "relations.csv"):
        relation_groups.setdefault(row["model_id"], []).append(Relation(
            int(row["relation_index"]), int(row["first_id"]), int(row["second_id"]),
            float_from_bits(row["rest_length_bits"])))
    operator_rows: dict[str, list[dict[str, str]]] = {}
    for row in read_rows(parent_raw / "force_operator.csv"):
        operator_rows.setdefault(row["model_id"], []).append(row)
    result: dict[str, Model] = {}
    for model_id, relations in relation_groups.items():
        relations.sort(key=lambda value: value.index)
        count = len(relations)
        h = [[0.0 for _ in range(count)] for _ in range(count)]
        for row in operator_rows[model_id]:
            h[int(row["row"])][int(row["column"])] = float_from_bits(row["h_bits"])
        result[model_id] = Model(model_id, references[model_id], masses[model_id], relations, h)
    return result


def load_states(parent_raw: Path) -> tuple[dict[str, str], dict[str, State], dict[str, bool]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in read_rows(parent_raw / "initial_states.csv"):
        if row["level"] == "0":
            grouped.setdefault(row["scenario_id"], []).append(row)
    models: dict[str, str] = {}
    states: dict[str, State] = {}
    convergence: dict[str, bool] = {}
    for scenario, values in grouped.items():
        values.sort(key=lambda row: int(row["packet_id"]))
        models[scenario] = values[0]["model_id"]
        convergence[scenario] = values[0]["convergence"] == "true"
        states[scenario] = State(0, [Packet(
            int(row["packet_id"]), int(row["mass_raw"]),
            [Fraction(int(row[f"{axis}_raw"])) for axis in "xyz"],
            [Fraction(int(row[f"p{axis}_raw"])) for axis in "xyz"],
        ) for row in values])
    require(set(SCENARIOS).issubset(states), "parent decisive scenario missing")
    return models, states, convergence


def git_identity(source: Path) -> tuple[str, str, bool]:
    def run(*arguments: str) -> str:
        return subprocess.check_output(["git", *arguments], cwd=source, text=True).strip()
    sha = run("rev-parse", "HEAD")
    branch = run("rev-parse", "--abbrev-ref", "HEAD")
    dirty = bool(run("status", "--porcelain"))
    return sha, branch, dirty


def materialize(parent_raw: Path, output: Path, source: Path) -> None:
    parent_rows = verify_parent(parent_raw)
    models = load_models(parent_raw)
    scenario_models, states, convergence = load_states(parent_raw)
    source_sha, source_branch, source_dirty = git_identity(source)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    endpoint_rows: list[dict[str, object]] = []
    initial_rows: list[dict[str, object]] = []
    energy_rows: list[dict[str, object]] = []
    invariant_rows: list[dict[str, object]] = []
    force_rows: list[dict[str, object]] = []
    phase_rows: list[dict[str, object]] = []
    reversibility_rows: list[dict[str, object]] = []
    covariance_rows: list[dict[str, object]] = []
    checkpoint_rows: list[dict[str, object]] = []
    domain_rows: list[dict[str, object]] = []
    long_energy_rows: list[dict[str, object]] = []

    for scenario in sorted(states):
        initial = states[scenario]
        prefix = {
            "scenario_id": scenario, "model_id": scenario_models[scenario], "path": "initial",
            "level": 0, "dt_raw": 0, "steps": 0, "status": "initial",
            "completed_steps": 0, "time_raw": initial.time_raw, "state_hash": state_hash(initial),
        }
        for packet in canonical_packets(initial):
            initial_rows.append(full_state_row(prefix, packet))

    primary_results: dict[tuple[str, str, int], RunResult] = {}
    for level, (dt_raw, steps) in enumerate(zip(TIMESTEPS_RAW, STEP_COUNTS)):
        print(
            f"fractional phase level {level}: dt_raw={dt_raw} steps={steps}",
            flush=True,
        )
        for scenario in SCENARIOS:
            model = models[scenario_models[scenario]]
            initial = states[scenario]
            for path in (CONTROL, KDK):
                trajectory = f"short:{scenario}:{path}:L{level}"
                result = run_trajectory(
                    model, initial, dt_raw, steps, path, trajectory, level,
                    invariant_rows, force_rows, phase_rows)
                primary_results[(scenario, path, level)] = result
                prefix = {
                    "scenario_id": scenario, "model_id": model.identifier, "path": path,
                    "level": level, "dt_raw": dt_raw, "steps": steps, "status": result.status,
                    "completed_steps": result.completed_steps, "time_raw": result.final.time_raw,
                    "state_hash": state_hash(result.final),
                }
                for packet in canonical_packets(result.final):
                    endpoint_rows.append(full_state_row(prefix, packet))
                for sample, value in enumerate(result.energies):
                    energy_rows.append({"scenario_id": scenario, "path": path, "level": level,
                                        "sample": sample, "dt_raw": dt_raw,
                                        "mechanical_energy_bits": float_bits(value)})

            forward = primary_results[(scenario, KDK, level)]
            backward = run_trajectory(
                model, forward.final, -dt_raw, steps, KDK,
                f"reverse:{scenario}:L{level}", level, enforce_complexity=False)
            recovered = encode_state(backward.final) == encode_state(initial)
            reversibility_rows.append({
                "scenario_id": scenario, "level": level, "dt_raw": dt_raw, "steps": steps,
                "forward_status": forward.status, "backward_status": backward.status,
                "initial_hash": state_hash(initial), "recovered_hash": state_hash(backward.final),
                "complete_state_identical": str(recovered).lower(),
            })

        baseline = primary_results[("k4_internal", KDK, level)]
        for kind, scenario, transform in (
            ("translation", "k4_translated", lambda value: value),
            ("galilean_boost", "k4_boosted", lambda value: value),
            ("proper_lattice_rotation", "k4_rotated", inverse_rotate_state),
        ):
            model = models[scenario_models[scenario]]
            candidate = run_trajectory(model, states[scenario], dt_raw, steps, KDK,
                                       f"covariance:{kind}:L{level}", level,
                                       enforce_complexity=False)
            transformed = transform(candidate.final)
            covariance_rows.append({
                "kind": kind, "level": level, "dt_raw": dt_raw,
                "position_discrepancy_hash": fraction_hash(relative_maximum(baseline.final, transformed)),
                "position_discrepancy_num": relative_maximum(baseline.final, transformed).numerator,
                "position_discrepancy_den": relative_maximum(baseline.final, transformed).denominator,
                "momentum_discrepancy_hash": fraction_hash(relative_maximum(baseline.final, transformed, True)),
                "momentum_discrepancy_num": relative_maximum(baseline.final, transformed, True).numerator,
                "momentum_discrepancy_den": relative_maximum(baseline.final, transformed, True).denominator,
                "status": candidate.status,
            })

        permuted = states["k4_internal"].clone()
        permuted.packets.reverse()
        permutation_run = run_trajectory(models["k4"], permuted, dt_raw, steps, KDK,
                                         f"covariance:packet_permutation:L{level}", level,
                                         enforce_complexity=False)
        covariance_rows.append({
            "kind": "packet_permutation", "level": level, "dt_raw": dt_raw,
            "position_discrepancy_hash": fraction_hash(relative_maximum(baseline.final, permutation_run.final)),
            "position_discrepancy_num": relative_maximum(baseline.final, permutation_run.final).numerator,
            "position_discrepancy_den": relative_maximum(baseline.final, permutation_run.final).denominator,
            "momentum_discrepancy_hash": fraction_hash(relative_maximum(baseline.final, permutation_run.final, True)),
            "momentum_discrepancy_num": relative_maximum(baseline.final, permutation_run.final, True).numerator,
            "momentum_discrepancy_den": relative_maximum(baseline.final, permutation_run.final, True).denominator,
            "status": permutation_run.status,
        })

        half_steps = steps // 2
        first = run_trajectory(models["k4"], states["k4_internal"], dt_raw, half_steps, KDK,
                               f"checkpoint:first:L{level}", level, enforce_complexity=False)
        encoded = encode_state(first.final)
        decoded = decode_state(encoded)
        second = run_trajectory(models["k4"], decoded, dt_raw, half_steps, KDK,
                                f"checkpoint:second:L{level}", level, enforce_complexity=False)
        suffix_identical = second.events == baseline.events[half_steps:]
        checkpoint_rows.append({
            "scenario_id": "k4_internal", "level": level, "dt_raw": dt_raw, "steps": steps,
            "checkpoint_step": half_steps, "checkpoint_hash": hashlib.sha256(encoded).hexdigest(),
            "checkpoint_bytes": len(encoded), "decoded_hash": state_hash(decoded),
            "whole_final_hash": state_hash(baseline.final), "resumed_final_hash": state_hash(second.final),
            "event_suffix_identical": str(suffix_identical).lower(),
            "canonical_round_trip": str(encode_state(decoded) == encoded).lower(),
        })

        crossing = states["domain_crossing"]
        status, rejected = one_step(
            models["pair"], crossing, 1_000_000_000, KDK,
            f"domain:L{level}", level, 1, None, None, exact_invariants(crossing))
        domain_rows.append({
            "scenario_id": "domain_crossing", "level": level, "status": status,
            "prior_hash": state_hash(crossing), "returned_hash": state_hash(rejected),
            "time_unchanged": str(rejected.time_raw == crossing.time_raw).lower(),
            "state_unchanged": str(encode_state(rejected) == encode_state(crossing)).lower(),
            "energy_ledger_present": "false",
        })

        long_trajectory = f"long:k4_internal:L{level}"
        long_run = run_trajectory(
            models["k4"], states["k4_internal"], dt_raw, steps * 16, KDK,
            long_trajectory, level, phase_rows=phase_rows)
        for sample, value in enumerate(long_run.energies):
            long_energy_rows.append({
                "scenario_id": "k4_internal", "level": level, "dt_raw": dt_raw,
                "sample": sample, "status": long_run.status,
                "mechanical_energy_bits": float_bits(value),
            })
        print(
            f"fractional phase level {level}: complete; "
            f"long_status={long_run.status} long_steps={long_run.completed_steps}",
            flush=True,
        )

    obstruction_rows = []
    for relation_gcd, momentum_gcd, relation_sq, momentum_sq in (
        (1, 1, 14, 77), (2, 3, 56, 693), (5, 7, 350, 3773),
    ):
        impulse_squared = (PQ / LQ) ** 2 * Fraction(relation_sq, relation_gcd**2)
        drift_squared = (LQ / PQ) ** 2 * Fraction(momentum_sq, momentum_gcd**2)
        product = impulse_squared * drift_squared
        expected = Fraction(relation_sq * momentum_sq, relation_gcd**2 * momentum_gcd**2)
        obstruction_rows.append({
            "relation_gcd": relation_gcd, "momentum_gcd": momentum_gcd,
            "relation_squared": relation_sq, "momentum_squared": momentum_sq,
            "minimum_impulse_squared": ratio_text(impulse_squared),
            "minimum_drift_squared": ratio_text(drift_squared),
            "product": ratio_text(product), "expected_product": ratio_text(expected),
            "unit_independent": str(product == expected).lower(),
        })

    metadata_rows = [
        {"key": "schema", "value": "mls.explicit-fractional-phase-state.raw.v1"},
        {"key": "accepted_parent_sha", "value": PARENT_SHA},
        {"key": "accepted_parent_tag", "value": PARENT_TAG},
        {"key": "accepted_parent_tag_object", "value": PARENT_TAG_OBJECT},
        {"key": "accepted_parent_archive_sha256", "value": PARENT_ARCHIVE_SHA256},
        {"key": "accepted_parent_archive_size", "value": PARENT_ARCHIVE_SIZE},
        {"key": "source_sha", "value": source_sha},
        {"key": "configured_source_branch", "value": source_branch},
        {"key": "source_dirty", "value": str(source_dirty).lower()},
        {"key": "branch", "value": BRANCH},
        {"key": "candidate", "value": "exact_reduced_rational_packet_phase_state"},
        {"key": "rational_arithmetic_backend", "value": "gmpy2.mpq-2.3.1"},
        {"key": "force_geometry", "value": "cancellation_resistant_binary64"},
        {"key": "safe_domain", "value": "2^-24"},
        {"key": "coarse_integer_width", "value": "signed64"},
        {"key": "fractional_denominator", "value": "unbounded_exact_reduced"},
        {"key": "relation_remainder_present", "value": "false"},
        {"key": "energy_discrepancy_stored", "value": "false"},
        {"key": "maximum_component_bits", "value": MAX_COMPONENT_BITS},
        {"key": "median_component_bits", "value": MEDIAN_COMPONENT_BITS},
        {"key": "maximum_checkpoint_bytes", "value": MAX_CHECKPOINT_BYTES},
        {"key": "promotion", "value": "NO_PROMOTION"},
    ]
    unit_rows = [{
        "Lq": ratio_text(LQ), "Mq": ratio_text(MQ), "Tq": ratio_text(TQ),
        "Pq": ratio_text(PQ), "Eq": ratio_text(EQ), "Fq": ratio_text(FQ),
        "canonical_interval": "[-1/2,1/2)", "fixed_across_levels": "true",
    }]

    write_rows(output / "metadata.csv", ("key", "value"), metadata_rows)
    write_rows(output / "units.csv", tuple(unit_rows[0]), unit_rows)
    write_rows(output / "parent_fingerprint.csv", ("file", "sha256", "expected_sha256", "passed"), parent_rows)
    for filename in ("reference_packets.csv", "relations.csv", "force_operator.csv"):
        shutil.copyfile(parent_raw / filename, output / filename)
    write_rows(output / "initial_states.csv", STATE_FIELDS, initial_rows)
    write_rows(output / "endpoints.csv", STATE_FIELDS, endpoint_rows)
    write_rows(output / "energies.csv", ("scenario_id", "path", "level", "sample", "dt_raw", "mechanical_energy_bits"), energy_rows)
    write_rows(output / "invariants.csv", ("trajectory_id", "level", "step", "stage", "momentum_hash", "angular_hash", "momentum_equal_initial", "angular_equal_initial"), invariant_rows)
    write_rows(output / "force_audit.csv", ("trajectory_id", "level", "step", "stage", "relation_index", "first_id", "second_id", "length_bits", "conjugate_bits", "coefficient_hash", "coefficient_bits", "impulse_hash", "impulse_bits", "central_cross_zero"), force_rows)
    write_rows(output / "state_complexity.csv", ("trajectory_id", "level", "step", "time_raw", "packet_id", "phase", "axis", "residual_hash", "numerator_bits", "denominator_bits", "checkpoint_bytes"), phase_rows)
    write_rows(output / "reversibility.csv", ("scenario_id", "level", "dt_raw", "steps", "forward_status", "backward_status", "initial_hash", "recovered_hash", "complete_state_identical"), reversibility_rows)
    write_rows(output / "covariance.csv", ("kind", "level", "dt_raw", "position_discrepancy_hash", "position_discrepancy_num", "position_discrepancy_den", "momentum_discrepancy_hash", "momentum_discrepancy_num", "momentum_discrepancy_den", "status"), covariance_rows)
    write_rows(output / "checkpoint.csv", ("scenario_id", "level", "dt_raw", "steps", "checkpoint_step", "checkpoint_hash", "checkpoint_bytes", "decoded_hash", "whole_final_hash", "resumed_final_hash", "event_suffix_identical", "canonical_round_trip"), checkpoint_rows)
    write_rows(output / "domain.csv", ("scenario_id", "level", "status", "prior_hash", "returned_hash", "time_unchanged", "state_unchanged", "energy_ledger_present"), domain_rows)
    write_rows(output / "long_energy.csv", ("scenario_id", "level", "dt_raw", "sample", "status", "mechanical_energy_bits"), long_energy_rows)
    write_rows(output / "obstruction.csv", tuple(obstruction_rows[0]), obstruction_rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    try:
        materialize(arguments.parent_raw, arguments.output, arguments.source)
        print("EXPLICIT FRACTIONAL PHASE STATE RAW COMPLETE: exact_rational NO_PROMOTION")
        return 0
    except (OSError, ValueError, ArithmeticError, LabError) as error:
        print(f"EXPLICIT FRACTIONAL PHASE STATE FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
