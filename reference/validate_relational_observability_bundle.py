#!/usr/bin/env python3
"""Independent Candidate-C relational-observability evidence validator.

The validator reconstructs the unit-direction rigidity operator from exported
packet coordinates and retained relation endpoints.  Producer ranks, spectra,
nullspaces, margins, and metamorphic flags are claims to be checked; none is a
premise for the independent calculation.  Candidate B and Candidate D are
outside this validator's accepted vocabulary.

The wire schemas and bundle-level policy appear below the arithmetic helpers.
Keeping the mathematical path self-contained makes its implementation
independent from the C++ producer and from the earlier Mechanical Observability
validator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import pathlib
import re
import struct
import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from typing import Any, Iterable, Mapping, NoReturn, Sequence


DECIMAL_DIGITS = 90
EPSILON64 = Decimal(2) ** -52
MIN_NORMAL64 = Decimal.from_float(sys.float_info.min)
SEED = 260828
PARENT_SHA = "baa6beb0b89e70dc2a5baa141366be3f2530a19d"
ACCEPTED_C_SOURCE_SHA = "a71decf8a60c9937e568e712cf9bf13cb68c9bb7"
SUMMARY_SCHEMA = "mls.relational-observability-confirmation.summary.v1"
TOLERANCE_SCHEMA = "mls.relational-observability-confirmation.tolerances.v1"
MANIFEST_SCHEMA = "mls.relational-observability-confirmation.manifest.v1"
PRODUCER = "cpp_relational_observability_confirmation"
BRANCH = "relational-observability-confirmation"
CANDIDATE = "central_relational_representation_C"
CHECKPOINT_ENCODING = "mls.mechanical-observability.input.v1.little-endian"
INHERITED_GIT_BLOBS = {
    "include/mls/mechanical_observability_lab.hpp": (
        "e5007f63ff4984dd5e6fbbb027a26f319cc02e5c"
    ),
    "src/mechanical_observability_lab.cpp": (
        "9ed0ab945a4178286c59aad9e8f9fd9eb1ac8c87"
    ),
    "apps/mechanical_observability_diagnostic.cpp": (
        "ca8082460ba9b34264b393cfb43feaccc8583d99"
    ),
    "tests/mechanical_observability_tests.cpp": (
        "b334c2b43dcd7438403b4c87f72e442dcbaec504"
    ),
    "src/kelvin_covariance_audit.cpp": (
        "bcdad1a3edaf9fbf4528438f720261141333b394"
    ),
}
FIXTURE_HASHES = {
    "configurations": "557e4327867171aff7fcb34601e6c9548081cd2d6a3a735d2eabaf6dd3f2eb34",
    "packets": "b8525b53ace3a87d05d7fc32f0193eaa698d43b3af31321143d3314cd38d258c",
    "relations": "89c8189a64cfe27a6d4133dd2a6f5d9d38e96e29fcaea39b0512ea705e7ae6f9",
}
VERDICTS = (
    "stop_inconclusive_or_implementation_failure",
    "reject_central_relational_representation",
    "retain_only_as_mathematically_rigid_numerically_unsafe",
    "retain_central_relational_representation_for_research",
)
PROBE_FAMILIES = {
    "inherited",
    "geometry_perturbation",
    "homogeneous_deformation",
    "topology_deletion",
    "id_bijection",
}
DECISION_SCOPES = {
    "eligible_generic",
    "intentionally_flexible",
    "non_generic_control",
}
OBSERVABILITY_CLASSIFICATIONS = {
    "rigid_only",
    "resolved_nonrigid",
    "ambiguous",
    "implementation_failure",
}
SPECTRUM_CLASSIFICATIONS = {
    "accepted_nonzero",
    "resolved_zero",
    "ambiguous",
}
ANALYSIS_STATUSES = {"analyzed", "empty", "ambiguous", "numerical_failure"}
TRANSITIONS = {
    "none",
    "last_rigid",
    "first_nonrigid",
    "transition_adjacent",
    "complete_deletion",
}
RANK_REFERENCE_KINDS = {
    "exact_fraction_rref",
    "modular_lower_bound_matches_structural_upper_bound",
    "modular_lower_bound",
}
CONTROL_KINDS = {
    "inherited_translation",
    "inherited_proper_rotation",
    "inherited_rotation_translation",
    "inherited_scale_half",
    "inherited_scale_double",
    "packet_permutation",
    "relation_permutation",
    "id_reverse",
    "id_cycle",
    "id_sha256",
}
ID_BIJECTION_KINDS = {"id_reverse", "id_cycle", "id_sha256"}
LOOKUP_PHASES = {"p000", "p037_011_029"}
INHERITED_ROTATION_Q: tuple[tuple[Q, Q, Q], ...] = (
    (Q(1, 9), Q(8, 9), Q(4, 9)),
    (Q(8, 9), Q(1, 9), Q(-4, 9)),
    (Q(-4, 9), Q(4, 9), Q(-7, 9)),
)
FULL_INHERITED_IDS = frozenset(
    """
    base.bcc35.r105.original
    base.bcc35.r150.original
    base.bcc35.r180.original
    base.bcc35.r180.original.rotation
    base.bcc35.r180.original.rotation_translation
    base.bcc35.r180.original.scale_double_rotation
    base.bcc35.r180.original.scale_half_rotation
    base.bcc35.r180.original.translation
    base.corner_truncated.r150.original
    base.corner_truncated.r180.original
    base.corner_truncated.r180.original.rotation
    base.corner_truncated.r180.original.rotation_translation
    base.corner_truncated.r180.original.scale_double_rotation
    base.corner_truncated.r180.original.scale_half_rotation
    base.corner_truncated.r180.original.translation
    base.edge_truncated.r150.original
    base.edge_truncated.r180.original
    base.filament.r105.original
    base.filament.r205.original
    base.filament.r205.original.rotation
    base.filament.r205.original.rotation_translation
    base.filament.r205.original.scale_double_rotation
    base.filament.r205.original.scale_half_rotation
    base.filament.r205.original.translation
    base.free_face.r150.original
    base.free_face.r180.original
    base.jitter27.r105.original
    base.jitter27.r150.original
    base.jitter27.r180.original
    base.jitter27.r180.original.rotation
    base.jitter27.r180.original.rotation_translation
    base.jitter27.r180.original.scale_double_rotation
    base.jitter27.r180.original.scale_half_rotation
    base.jitter27.r180.original.translation
    base.sc3.r105.original
    base.sc3.r150.original
    base.sc3.r180.original
    base.sc3.r180.original.rotation
    base.sc3.r180.original.rotation_translation
    base.sc3.r180.original.scale_double_rotation
    base.sc3.r180.original.scale_half_rotation
    base.sc3.r180.original.translation
    base.sc3_deletion.delete10.original
    base.sc3_deletion.delete25.original
    base.sc3_deletion.delete40.original
    base.sheet.r105.original
    base.sheet.r150.original
    base.sheet.r150.original.rotation
    base.sheet.r150.original.rotation_translation
    base.sheet.r150.original.scale_double_rotation
    base.sheet.r150.original.scale_half_rotation
    base.sheet.r150.original.translation
    exact.cube_edge_graph
    exact.noncoplanar_underconnected
    exact.octahedron_graph
    exact.planar_square_plus_diagonal
    exact.planar_square_plus_diagonal_and_volume
    exact.tetrahedron_k4
    exact.tetrahedron_k4_minus_edge
    """.split()
)
PERTURBATION_SOURCES = (
    "base.bcc35.r180.original",
    "base.corner_truncated.r180.original",
    "base.edge_truncated.r180.original",
    "base.free_face.r180.original",
    "base.jitter27.r180.original",
    "base.sc3.r180.original",
    "base.sc3_deletion.delete25.original",
)
PERTURBATION_AMPLITUDES = (
    (1.0 / 10000.0, "1"),
    (1.0 / 1000.0, "10"),
    (1.0 / 100.0, "100"),
)
PERTURBATION_SEEDS = (260829, 260830, 260831)
DEFORMATION_MATRICES = {
    "isotropic_compression": (
        (4.0 / 5.0, 0.0, 0.0),
        (0.0, 4.0 / 5.0, 0.0),
        (0.0, 0.0, 4.0 / 5.0),
    ),
    "isotropic_expansion": (
        (5.0 / 4.0, 0.0, 0.0),
        (0.0, 5.0 / 4.0, 0.0),
        (0.0, 0.0, 5.0 / 4.0),
    ),
    "pure_shear": (
        (5.0 / 4.0, 0.0, 0.0),
        (0.0, 4.0 / 5.0, 0.0),
        (0.0, 0.0, 1.0),
    ),
    "simple_shear": (
        (1.0, 1.0 / 4.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    ),
    "general_affine": (
        (1.0, 1.0 / 5.0, -1.0 / 10.0),
        (1.0 / 10.0, 9.0 / 10.0, 1.0 / 8.0),
        (-1.0 / 12.0, 1.0 / 10.0, 11.0 / 10.0),
    ),
}
EXACT_CONTROL_EXPECTED = {
    "tetrahedron_k4": (6, 6, 6, 0),
    "tetrahedron_k4_minus_edge": (5, 7, 6, 1),
    "octahedron": (12, 6, 6, 0),
    "cube_edge": (12, 12, 6, 6),
    "planar_square_plus_diagonal": (5, 7, 6, 1),
    "planar_square_plus_diagonal_and_volume": (5, 7, 6, 1),
    "noncoplanar_underconnected": (5, 7, 6, 1),
}
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_ROWS = 8_000_000
MAX_FIELD_CHARS = 2 * 1024 * 1024
IDENTIFIER_RE = re.compile(r"[A-Za-z0-9_.:-]+")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
SOURCE_SHA_RE = re.compile(r"[0-9a-f]{40}")
MODULAR_PRIMES = (2_147_483_647, 2_147_483_629, 2_147_483_587)

Vec3Q = tuple[Q, Q, Q]
Vec3D = tuple[Decimal, Decimal, Decimal]


class ValidationError(RuntimeError):
    """A stable, user-facing rejection of invalid or inconsistent evidence."""


@dataclass
class Audit:
    checks: int = 0

    def require(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            raise ValidationError(message)


@dataclass(frozen=True)
class IndependentSpectrum:
    singular_values: tuple[Decimal, ...]
    rank: int
    nullity: int
    sigma_max: Decimal
    sigma_min_resolved: Decimal
    margin: Decimal
    threshold: Decimal
    threshold_separation: Decimal
    sweeps: int
    converged: bool


@dataclass(frozen=True)
class IndependentRank:
    rank: int
    nullity: int
    rigid_rank: int
    upper_bound: int
    method: str
    certified: bool


def reject(message: str) -> NoReturn:
    raise ValidationError(message)


def dsum(values: Iterable[Decimal]) -> Decimal:
    return sum(values, Decimal(0))


def qsum(values: Iterable[Q]) -> Q:
    return sum(values, Q(0))


def bool_text(value: str, where: str) -> bool:
    if value not in {"true", "false"}:
        reject(f"{where}: expected canonical boolean")
    return value == "true"


def unsigned(value: str, where: str, *, minimum: int = 0) -> int:
    if not re.fullmatch(r"0|[1-9][0-9]*", value):
        reject(f"{where}: expected canonical unsigned integer")
    parsed = int(value)
    if parsed < minimum:
        reject(f"{where}: integer below minimum")
    return parsed


def identifier(value: str, where: str) -> str:
    if not value or IDENTIFIER_RE.fullmatch(value) is None:
        reject(f"{where}: invalid identifier")
    return value


def binary64(value: str, where: str) -> float:
    if not isinstance(value, str) or value == "NA":
        reject(f"{where}: expected hexadecimal binary64")
    try:
        parsed = float.fromhex(value)
    except ValueError as error:
        raise ValidationError(f"{where}: invalid hexadecimal binary64") from error
    if not math.isfinite(parsed):
        reject(f"{where}: nonfinite binary64")
    if parsed == 0.0 and math.copysign(1.0, parsed) < 0:
        reject(f"{where}: negative zero")
    if parsed.hex() != value:
        reject(f"{where}: noncanonical hexadecimal binary64")
    return parsed


def signed_zero_binary64(value: str, where: str) -> float:
    """Canonical hex binary64 while preserving a null-vector sign bit."""
    if not isinstance(value, str) or value == "NA":
        reject(f"{where}: expected hexadecimal binary64")
    try:
        parsed = float.fromhex(value)
    except ValueError as error:
        raise ValidationError(f"{where}: invalid hexadecimal binary64") from error
    if not math.isfinite(parsed) or parsed.hex() != value:
        reject(f"{where}: noncanonical hexadecimal binary64")
    return parsed


def decimal64(value: str, where: str) -> Decimal:
    return Decimal.from_float(binary64(value, where))


def fraction64(value: str, where: str) -> Q:
    return Q.from_float(binary64(value, where))


def optional_binary64(value: str, where: str) -> float | None:
    return None if value == "NA" else binary64(value, where)


def extended_binary64(value: str, where: str) -> float:
    if value == "inf":
        return math.inf
    return binary64(value, where)


def sha256_text(value: str, where: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        reject(f"{where}: invalid SHA-256")
    return value


def source_sha(value: str, where: str) -> str:
    if not isinstance(value, str) or SOURCE_SHA_RE.fullmatch(value) is None:
        reject(f"{where}: invalid source SHA")
    return value


def enum_text(value: str, choices: set[str], where: str) -> str:
    if value not in choices:
        reject(f"{where}: unsupported value {value!r}")
    return value


def optional_unsigned(value: str, where: str, *, minimum: int = 0) -> int | None:
    return None if value == "NA" else unsigned(value, where, minimum=minimum)


def close_float(
    first: float,
    second: float,
    tolerance: float,
    where: str,
    *,
    scale_floor: float = 1.0,
) -> None:
    scale = max(abs(first), abs(second), scale_floor)
    if abs(first - second) > tolerance * scale:
        reject(
            f"{where}: {first.hex()} differs from {second.hex()} "
            f"beyond {tolerance:.17g} relative"
        )


def decimal_json(value: Any, where: str) -> Decimal:
    if not isinstance(value, str):
        reject(f"{where}: expected decimal string")
    try:
        parsed = Decimal(value)
    except Exception as error:
        raise ValidationError(f"{where}: invalid decimal") from error
    if not parsed.is_finite():
        reject(f"{where}: nonfinite decimal")
    return parsed


def q_rref_rank(matrix: Sequence[Sequence[Q]]) -> int:
    if not matrix:
        return 0
    width = len(matrix[0])
    if any(len(row) != width for row in matrix):
        reject("exact rank: ragged matrix")
    work = [list(row) for row in matrix]
    pivot_row = 0
    for column in range(width):
        pivot = next(
            (row for row in range(pivot_row, len(work)) if work[row][column] != 0),
            None,
        )
        if pivot is None:
            continue
        work[pivot_row], work[pivot] = work[pivot], work[pivot_row]
        divisor = work[pivot_row][column]
        work[pivot_row] = [entry / divisor for entry in work[pivot_row]]
        for row in range(len(work)):
            if row == pivot_row:
                continue
            multiplier = work[row][column]
            if multiplier == 0:
                continue
            work[row] = [
                work[row][entry] - multiplier * work[pivot_row][entry]
                for entry in range(width)
            ]
        pivot_row += 1
        if pivot_row == len(work):
            break
    return pivot_row


def modular_rank(matrix: Sequence[Sequence[Q]], prime: int) -> int:
    """Return the exact matrix rank over one deterministic prime field."""
    if not matrix:
        return 0
    width = len(matrix[0])
    if any(len(row) != width for row in matrix):
        reject("modular rank: ragged matrix")
    work: list[list[int]] = []
    for row in matrix:
        encoded: list[int] = []
        for value in row:
            denominator = value.denominator % prime
            if denominator == 0:
                reject("modular rank: registered prime divides a denominator")
            encoded.append(
                (value.numerator % prime) * pow(denominator, prime - 2, prime) % prime
            )
        work.append(encoded)
    pivot_row = 0
    for column in range(width):
        pivot = next(
            (row for row in range(pivot_row, len(work)) if work[row][column] != 0),
            None,
        )
        if pivot is None:
            continue
        work[pivot_row], work[pivot] = work[pivot], work[pivot_row]
        inverse = pow(work[pivot_row][column], prime - 2, prime)
        work[pivot_row] = [(entry * inverse) % prime for entry in work[pivot_row]]
        for row in range(pivot_row + 1, len(work)):
            multiplier = work[row][column]
            if multiplier == 0:
                continue
            work[row] = [
                (work[row][entry] - multiplier * work[pivot_row][entry]) % prime
                for entry in range(width)
            ]
        pivot_row += 1
        if pivot_row == len(work):
            break
    return pivot_row


def cross_q(first: Vec3Q, second: Vec3Q) -> Vec3Q:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def rigid_generator_rank(positions: Mapping[int, Vec3Q]) -> int:
    ids = sorted(positions)
    axes: tuple[Vec3Q, ...] = (
        (Q(1), Q(0), Q(0)),
        (Q(0), Q(1), Q(0)),
        (Q(0), Q(0), Q(1)),
    )
    columns: list[list[Q]] = []
    for axis in axes:
        columns.append([axis[component] for _packet in ids for component in range(3)])
    for omega in axes:
        columns.append(
            [component for packet in ids for component in cross_q(omega, positions[packet])]
        )
    return q_rref_rank(
        [[column[row] for column in columns] for row in range(3 * len(ids))]
    )


def displacement_rigidity_matrix(
    positions: Mapping[int, Vec3Q], edges: Sequence[tuple[int, int]]
) -> list[list[Q]]:
    """Exact row-scaled Candidate-C operator with the same kernel as unit rows."""
    ids = sorted(positions)
    index = {packet_id: offset for offset, packet_id in enumerate(ids)}
    rows: list[list[Q]] = []
    seen: set[tuple[int, int]] = set()
    for first, second in edges:
        if first == second or first not in index or second not in index:
            reject("rigidity matrix: invalid relation endpoint")
        edge = tuple(sorted((first, second)))
        if edge in seen:
            reject("rigidity matrix: duplicate central relation")
        seen.add(edge)
        delta = tuple(
            positions[second][axis] - positions[first][axis] for axis in range(3)
        )
        if all(component == 0 for component in delta):
            reject("rigidity matrix: zero-length central relation")
        row = [Q(0) for _ in range(3 * len(ids))]
        for axis in range(3):
            row[3 * index[first] + axis] = -delta[axis]
            row[3 * index[second] + axis] = delta[axis]
        rows.append(row)
    return rows


def unit_rigidity_matrix(
    positions: Mapping[int, Vec3D], edges: Sequence[tuple[int, int]]
) -> list[list[Decimal]]:
    """High-precision unit-direction Candidate-C operator."""
    ids = sorted(positions)
    index = {packet_id: offset for offset, packet_id in enumerate(ids)}
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        rows: list[list[Decimal]] = []
        seen: set[tuple[int, int]] = set()
        for first, second in edges:
            if first == second or first not in index or second not in index:
                reject("unit rigidity matrix: invalid relation endpoint")
            edge = tuple(sorted((first, second)))
            if edge in seen:
                reject("unit rigidity matrix: duplicate relation")
            seen.add(edge)
            delta = tuple(
                positions[second][axis] - positions[first][axis] for axis in range(3)
            )
            length_squared = dsum(component * component for component in delta)
            if length_squared <= 0:
                reject("unit rigidity matrix: zero-length relation")
            length = length_squared.sqrt()
            direction = tuple(component / length for component in delta)
            row = [Decimal(0) for _ in range(3 * len(ids))]
            for axis in range(3):
                row[3 * index[first] + axis] = -direction[axis]
                row[3 * index[second] + axis] = direction[axis]
            rows.append(row)
        return rows


def high_precision_singular_values(
    matrix: Sequence[Sequence[Decimal]],
    *,
    relative_correlation_tolerance: Decimal = Decimal("1e-65"),
    maximum_sweeps: int = 160,
) -> tuple[tuple[Decimal, ...], int, bool]:
    """Direct cyclic one-sided Jacobi SVD in independent Decimal arithmetic.

    This path deliberately avoids normal equations.  It returns every column
    singular value, including the numerical null tail, sorted descending.
    """
    if not matrix:
        return (), 0, True
    row_count = len(matrix)
    column_count = len(matrix[0])
    if column_count == 0 or any(len(row) != column_count for row in matrix):
        reject("high-precision SVD: empty/ragged column set")
    original_column_count = column_count
    trailing_zeros = 0
    working: Sequence[Sequence[Decimal]] = matrix
    if row_count < column_count:
        # A thin SVD of R^T has the same nonzero singular values.  Appending
        # n-m exact zeros restores the full packet-velocity-domain spectrum
        # and avoids asking a one-sided method to maintain more orthogonal
        # nonzero columns than the row space can contain.
        working = [
            [matrix[row][column] for row in range(row_count)]
            for column in range(column_count)
        ]
        trailing_zeros = column_count - row_count
        row_count, column_count = column_count, row_count
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        columns = [
            [working[row][column] for row in range(row_count)]
            for column in range(column_count)
        ]
        maximum = max((abs(entry) for column in columns for entry in column), default=Decimal(0))
        if not maximum.is_finite():
            reject("high-precision SVD: nonfinite input")
        if maximum == 0:
            return tuple(Decimal(0) for _ in range(column_count)), 0, True
        columns = [[entry / maximum for entry in column] for column in columns]
        converged = column_count < 2
        used_sweeps = 0
        for sweep in range(maximum_sweeps):
            used_sweeps = sweep + 1
            maximum_correlation = Decimal(0)
            changed = False
            for first in range(column_count):
                for second in range(first + 1, column_count):
                    left = columns[first]
                    right = columns[second]
                    alpha = dsum(entry * entry for entry in left)
                    beta = dsum(entry * entry for entry in right)
                    if alpha == 0 or beta == 0:
                        continue
                    gamma = dsum(a * b for a, b in zip(left, right, strict=True))
                    correlation = abs(gamma) / (alpha * beta).sqrt()
                    maximum_correlation = max(maximum_correlation, correlation)
                    if correlation <= relative_correlation_tolerance:
                        continue
                    tau = (beta - alpha) / (Decimal(2) * gamma)
                    sign = Decimal(1) if tau >= 0 else Decimal(-1)
                    tangent = sign / (abs(tau) + (Decimal(1) + tau * tau).sqrt())
                    cosine = Decimal(1) / (Decimal(1) + tangent * tangent).sqrt()
                    sine = tangent * cosine
                    columns[first] = [
                        cosine * a - sine * b for a, b in zip(left, right, strict=True)
                    ]
                    columns[second] = [
                        sine * a + cosine * b for a, b in zip(left, right, strict=True)
                    ]
                    changed = True
            if not changed or maximum_correlation <= relative_correlation_tolerance:
                converged = True
                break
        spectrum = sorted(
            (
                dsum(entry * entry for entry in column).sqrt() * maximum
                for column in columns
            ),
            reverse=True,
        )
        spectrum.extend(Decimal(0) for _ in range(trailing_zeros))
        if len(spectrum) != original_column_count:
            reject("high-precision SVD: internal spectrum width mismatch")
        return tuple(+value for value in spectrum), used_sweeps, converged


def independent_binary64_direct_singular_values(
    matrix: Sequence[Sequence[Decimal]],
    physical_column_count: int,
    *,
    maximum_sweeps: int = 512,
) -> tuple[tuple[float, ...], int, bool]:
    """Direct rectangular cyclic one-sided Jacobi SVD over raw ``R``.

    Only two-column inner products needed by a Jacobi rotation are formed; a
    global normal-equations matrix is never assembled.  Wide matrices use the
    thin transpose and receive only their mathematically structural zero tail.
    """
    if physical_column_count <= 0:
        reject("binary64 direct SVD: invalid physical column count")
    if not matrix:
        return tuple(0.0 for _ in range(physical_column_count)), 0, True
    row_count = len(matrix)
    column_count = len(matrix[0])
    if column_count != physical_column_count:
        reject("binary64 direct SVD: physical width mismatch")
    if any(len(row) != column_count for row in matrix):
        reject("binary64 direct SVD: ragged matrix")
    converted = [[float(entry) for entry in row] for row in matrix]
    if any(not math.isfinite(entry) for row in converted for entry in row):
        reject("binary64 direct SVD: nonfinite input")
    trailing_zeros = 0
    if row_count < column_count:
        working = [
            [converted[row][column] for row in range(row_count)]
            for column in range(column_count)
        ]
        trailing_zeros = column_count - row_count
        row_count, column_count = column_count, row_count
    else:
        working = converted
    columns = [
        [working[row][column] for row in range(row_count)]
        for column in range(column_count)
    ]
    maximum = max(
        (abs(entry) for column in columns for entry in column), default=0.0
    )
    if not math.isfinite(maximum):
        reject("binary64 direct SVD: nonfinite scale")
    if maximum == 0.0:
        return tuple(0.0 for _ in range(physical_column_count)), 0, True
    columns = [[entry / maximum for entry in column] for column in columns]
    initial_energy = math.fsum(
        entry * entry for column in columns for entry in column
    )
    dimension = max(6, row_count, physical_column_count)
    pair_factor = 32.0 * sys.float_info.epsilon
    deflation_factor = 8.0 * dimension * sys.float_info.epsilon
    converged = column_count < 2
    used_sweeps = 0
    for sweep in range(maximum_sweeps):
        used_sweeps = sweep + 1
        norms = [
            math.sqrt(max(0.0, math.fsum(entry * entry for entry in column)))
            for column in columns
        ]
        largest = max(norms, default=0.0)
        deflation_threshold = deflation_factor * largest
        changed = False
        for first in range(column_count):
            if norms[first] <= deflation_threshold:
                continue
            for second in range(first + 1, column_count):
                if norms[second] <= deflation_threshold:
                    continue
                left = columns[first]
                right = columns[second]
                alpha = math.fsum(entry * entry for entry in left)
                beta = math.fsum(entry * entry for entry in right)
                if alpha <= 0.0 or beta <= 0.0:
                    continue
                gamma = math.fsum(
                    a * b for a, b in zip(left, right, strict=True)
                )
                pair_tolerance = pair_factor * math.sqrt(alpha) * math.sqrt(beta)
                if abs(gamma) <= pair_tolerance:
                    continue
                tau = (beta - alpha) / (2.0 * gamma)
                tangent = math.copysign(
                    1.0 / (abs(tau) + math.hypot(1.0, tau)), tau
                )
                cosine = 1.0 / math.hypot(1.0, tangent)
                sine = tangent * cosine
                columns[first] = [
                    cosine * a - sine * b
                    for a, b in zip(left, right, strict=True)
                ]
                columns[second] = [
                    sine * a + cosine * b
                    for a, b in zip(left, right, strict=True)
                ]
                changed = True
        if not changed:
            converged = True
            break
    final_energy = math.fsum(
        entry * entry for column in columns for entry in column
    )
    energy_tolerance = (
        4096.0
        * dimension
        * sys.float_info.epsilon
        * max(initial_energy, 1.0)
    )
    if not math.isfinite(final_energy) or abs(final_energy - initial_energy) > energy_tolerance:
        reject("binary64 direct SVD: Frobenius-energy drift")
    if converged:
        norms = [
            math.sqrt(max(0.0, math.fsum(entry * entry for entry in column)))
            for column in columns
        ]
        largest = max(norms, default=0.0)
        deflation_threshold = deflation_factor * largest
        for first in range(column_count):
            if norms[first] <= deflation_threshold:
                continue
            for second in range(first + 1, column_count):
                if norms[second] <= deflation_threshold:
                    continue
                gamma = math.fsum(
                    a * b
                    for a, b in zip(columns[first], columns[second], strict=True)
                )
                pair_tolerance = pair_factor * norms[first] * norms[second]
                if abs(gamma) > pair_tolerance:
                    converged = False
                    break
            if not converged:
                break
    spectrum = sorted(
        (
            math.sqrt(max(0.0, math.fsum(entry * entry for entry in column)))
            * maximum
            for column in columns
        ),
        reverse=True,
    )
    spectrum.extend(0.0 for _ in range(trailing_zeros))
    if len(spectrum) != physical_column_count or any(
        not math.isfinite(value) for value in spectrum
    ):
        reject("binary64 direct SVD: invalid spectrum width/value")
    return tuple(spectrum), used_sweeps, converged


def independent_spectrum(
    matrix: Sequence[Sequence[Decimal]], rank_factor: Decimal
) -> IndependentSpectrum:
    values, sweeps, converged = high_precision_singular_values(matrix)
    if not converged:
        reject("high-precision one-sided Jacobi SVD did not converge")
    sigma_max = values[0] if values else Decimal(0)
    dimension = max(len(matrix), len(matrix[0]) if matrix else 0, 1)
    threshold = rank_factor * Decimal(dimension) * EPSILON64 * sigma_max
    rank = sum(value > threshold for value in values)
    nullity = len(values) - rank
    sigma_min = values[rank - 1] if rank else Decimal(0)
    margin = sigma_min / sigma_max if sigma_max else Decimal(0)
    separation = sigma_min / threshold if threshold else Decimal("Infinity")
    return IndependentSpectrum(
        singular_values=values,
        rank=rank,
        nullity=nullity,
        sigma_max=sigma_max,
        sigma_min_resolved=sigma_min,
        margin=margin,
        threshold=threshold,
        threshold_separation=separation,
        sweeps=sweeps,
        converged=True,
    )


def exact_or_modular_rank(
    positions: Mapping[int, Vec3Q],
    edges: Sequence[tuple[int, int]],
    *,
    exact_limit: int,
) -> tuple[int, str]:
    matrix = displacement_rigidity_matrix(positions, edges)
    if len(positions) <= exact_limit:
        return q_rref_rank(matrix), "Fraction_RREF"
    ranks = [modular_rank(matrix, prime) for prime in MODULAR_PRIMES]
    if len(set(ranks)) != 1:
        reject("deterministic modular rank controls disagree")
    return ranks[0], "three_prime_modular_lower_bound"


def independent_rank(
    positions: Mapping[int, Vec3Q],
    edges: Sequence[tuple[int, int]],
    *,
    exact_limit: int,
) -> IndependentRank:
    rank, method = exact_or_modular_rank(
        positions, edges, exact_limit=exact_limit
    )
    rigid_rank = rigid_generator_rank(positions)
    column_count = 3 * len(positions)
    upper_bound = min(len(edges), column_count - rigid_rank)
    certified = method == "Fraction_RREF" or rank == upper_bound
    if rank > upper_bound:
        reject("independent rank exceeds rigid-kernel/row upper bound")
    return IndependentRank(
        rank=rank,
        nullity=column_count - rank,
        rigid_rank=rigid_rank,
        upper_bound=upper_bound,
        method=method,
        certified=certified,
    )


def affine_span_rank(positions: Mapping[int, Vec3Q]) -> int:
    points = [positions[packet_id] for packet_id in sorted(positions)]
    if not points:
        return 0
    origin = points[0]
    return q_rref_rank(
        [
            [point[axis] - origin[axis] for axis in range(3)]
            for point in points[1:]
        ]
    )


def graph_connected(
    packet_ids: Sequence[int], edges: Sequence[tuple[int, int]]
) -> bool:
    if not packet_ids:
        return False
    adjacency = {packet_id: set() for packet_id in packet_ids}
    for first, second in edges:
        if first not in adjacency or second not in adjacency:
            reject("connectivity: dangling relation endpoint")
        adjacency[first].add(second)
        adjacency[second].add(first)
    reached = {packet_ids[0]}
    pending = [packet_ids[0]]
    while pending:
        current = pending.pop()
        for neighbor in adjacency[current] - reached:
            reached.add(neighbor)
            pending.append(neighbor)
    return len(reached) == len(packet_ids)


def minimum_incident_direction_rank(
    positions: Mapping[int, Vec3Q], edges: Sequence[tuple[int, int]]
) -> int:
    incident: dict[int, set[int]] = {packet_id: set() for packet_id in positions}
    for first, second in edges:
        incident[first].add(second)
        incident[second].add(first)
    ranks: list[int] = []
    for packet_id in sorted(positions):
        center = positions[packet_id]
        ranks.append(
            q_rref_rank(
                [
                    [positions[neighbor][axis] - center[axis] for axis in range(3)]
                    for neighbor in sorted(incident[packet_id])
                ]
            )
        )
    return min(ranks, default=0)


def exact_topology_facts(
    positions: Mapping[int, Vec3Q],
    edges: Sequence[tuple[int, int]],
    intentionally_flexible: bool,
) -> dict[str, int | bool]:
    packet_ids = sorted(positions)
    rigid_rank = rigid_generator_rank(positions)
    edge_lower_bound = max(0, 3 * len(packet_ids) - 6)
    facts: dict[str, int | bool] = {
        "affine_span_rank": affine_span_rank(positions),
        "connected": graph_connected(packet_ids, edges),
        "edge_lower_bound": edge_lower_bound,
        "min_incident_direction_rank": minimum_incident_direction_rank(
            positions, edges
        ),
        "rigid_rank": rigid_rank,
    }
    facts["generic_solid_gate"] = bool(
        facts["affine_span_rank"] == 3
        and facts["connected"]
        and len(edges) >= edge_lower_bound
        and facts["min_incident_direction_rank"] == 3
        and rigid_rank == 6
        and not intentionally_flexible
    )
    return facts


def resolved_binary64_spectrum(
    matrix: Sequence[Sequence[Decimal]], rank: int, physical_column_count: int
) -> IndependentSpectrum:
    values_float, sweeps, converged = independent_binary64_direct_singular_values(
        matrix, physical_column_count
    )
    if not converged:
        reject("independent binary64 direct Jacobi SVD did not converge")
    if not 0 <= rank <= len(values_float):
        reject("resolved spectrum: independent rank outside matrix dimensions")
    values = tuple(Decimal.from_float(value) for value in values_float)
    sigma_max = values[0] if values else Decimal(0)
    sigma_min = values[rank - 1] if rank else Decimal(0)
    margin = sigma_min / sigma_max if sigma_max else Decimal(0)
    # Rank is supplied only by the exact/certified rigidity calculation.
    nullity = physical_column_count - rank
    return IndependentSpectrum(
        singular_values=values,
        rank=rank,
        nullity=nullity,
        sigma_max=sigma_max,
        sigma_min_resolved=sigma_min,
        margin=margin,
        threshold=Decimal(0),
        threshold_separation=Decimal("Infinity"),
        sweeps=sweeps,
        converged=True,
    )


def canonical_topology_by_geometry(
    positions: Mapping[int, Vec3Q], edges: Sequence[tuple[int, int]]
) -> tuple[tuple[Vec3Q, Vec3Q], ...]:
    """Canonicalize relation topology without retaining packet labels."""
    inverse: dict[Vec3Q, int] = {}
    for packet_id, point in positions.items():
        if point in inverse:
            reject("ID canonicalization requires unique packet coordinates")
        inverse[point] = packet_id
    result: list[tuple[Vec3Q, Vec3Q]] = []
    for first, second in edges:
        if first not in positions or second not in positions or first == second:
            reject("ID canonicalization: invalid relation")
        result.append(tuple(sorted((positions[first], positions[second]))))
    canonical = tuple(sorted(result))
    if len(canonical) != len(set(canonical)):
        reject("ID canonicalization: duplicate semantic edge")
    return canonical


def packet_id_bijection_by_geometry(
    first: Mapping[int, Vec3Q], second: Mapping[int, Vec3Q]
) -> dict[int, int]:
    if len(first) != len(second):
        reject("ID renaming: packet-count mismatch")
    second_by_point: dict[Vec3Q, int] = {}
    for packet_id, point in second.items():
        if point in second_by_point:
            reject("ID renaming: target coordinates are not unique")
        second_by_point[point] = packet_id
    mapping: dict[int, int] = {}
    for packet_id, point in first.items():
        if point not in second_by_point:
            reject("ID renaming: geometry mismatch")
        mapping[packet_id] = second_by_point[point]
    if len(set(mapping.values())) != len(mapping):
        reject("ID renaming: mapping is not bijective")
    return mapping


def spectrum_delta(first: Sequence[Decimal], second: Sequence[Decimal]) -> Decimal:
    if len(first) != len(second):
        reject("spectrum comparison: dimension mismatch")
    return max(
        (
            abs(a - b) / max(abs(a), abs(b), Decimal(1))
            for a, b in zip(first, second, strict=True)
        ),
        default=Decimal(0),
    )


def normalized_operator_residual(
    actual: Sequence[Sequence[Decimal]],
    expected: Sequence[Sequence[Decimal]],
) -> Decimal:
    """Independent Frobenius residual for two raw Candidate-C operators."""
    if len(actual) != len(expected):
        reject("operator covariance: row-count mismatch")
    if not actual:
        return Decimal(0)
    width = len(actual[0])
    if any(len(row) != width for row in actual) or any(
        len(row) != width for row in expected
    ):
        reject("operator covariance: column-count mismatch")
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        difference_squared = dsum(
            (left - right) * (left - right)
            for actual_row, expected_row in zip(actual, expected, strict=True)
            for left, right in zip(actual_row, expected_row, strict=True)
        )
        expected_squared = dsum(
            value * value for row in expected for value in row
        )
        denominator = max(expected_squared.sqrt(), MIN_NORMAL64)
        return difference_squared.sqrt() / denominator


def inherited_rotated_operator(
    base: Sequence[Sequence[Decimal]],
) -> list[list[Decimal]]:
    """Apply the frozen proper rotation to every packet-vector column block."""
    if not base:
        return []
    width = len(base[0])
    if width % 3 != 0 or any(len(row) != width for row in base):
        reject("operator covariance: invalid packet-vector dimension")
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        rotation = tuple(
            tuple(Decimal(value.numerator) / Decimal(value.denominator) for value in row)
            for row in INHERITED_ROTATION_Q
        )
        result: list[list[Decimal]] = []
        for source_row in base:
            target_row = [Decimal(0) for _ in source_row]
            for packet in range(width // 3):
                for axis in range(3):
                    target_row[3 * packet + axis] = dsum(
                        rotation[axis][inner] * source_row[3 * packet + inner]
                        for inner in range(3)
                    )
            result.append(target_row)
        return result


def semantically_align_id_operator(
    base_packet_ids: Sequence[int],
    base_edges: Sequence[tuple[int, int]],
    variant_packet_ids: Sequence[int],
    variant_edges: Sequence[tuple[int, int]],
    variant: Sequence[Sequence[Decimal]],
    mapping: Mapping[int, int],
) -> list[list[Decimal]]:
    """Pull a relabelled raw operator back into the base ID coordinates.

    Central length-rate rows are objective under endpoint reversal: reversing
    an edge changes both its direction sign and its endpoint-column order, so
    those signs cancel.  The explicit edge and column maps below therefore
    implement the full semantic row/column/sign pullback without an arbitrary
    extra row sign.
    """
    if len(variant) != len(variant_edges):
        reject("ID covariance: variant row inventory")
    width = 3 * len(variant_packet_ids)
    if any(len(row) != width for row in variant):
        reject("ID covariance: variant column inventory")
    variant_row_by_edge = {
        edge: index for index, edge in enumerate(variant_edges)
    }
    variant_column_by_id = {
        packet_id: index for index, packet_id in enumerate(variant_packet_ids)
    }
    result: list[list[Decimal]] = []
    for first, second in base_edges:
        mapped_first = mapping[first]
        mapped_second = mapping[second]
        mapped_edge = tuple(sorted((mapped_first, mapped_second)))
        if mapped_edge not in variant_row_by_edge:
            reject("ID covariance: missing mapped relation")
        source = variant[variant_row_by_edge[mapped_edge]]
        target: list[Decimal] = []
        for packet_id in base_packet_ids:
            mapped_id = mapping[packet_id]
            if mapped_id not in variant_column_by_id:
                reject("ID covariance: missing mapped packet")
            offset = 3 * variant_column_by_id[mapped_id]
            target.extend(source[offset : offset + 3])
        result.append(target)
    return result


# Frozen Candidate-C wire contract.  These names are intentionally closed: an
# unexpected file or column is invalid evidence rather than an extension the
# validator silently ignores.
SUMMARY_FILE = "summary.json"
TOLERANCE_FILE = "tolerances.json"
MANIFEST_FILE = "manifest.json"
CONFIGURATION_FIELDS = tuple(
    "configuration_id,source_configuration_id,probe_family,probe_id,family,"
    "profile,transform,decision_scope,packet_count,edge_count,nominal_spacing_m,"
    "support_radius_m,geometry_scale,deformation_det,perturbation_amplitude_ratio,"
    "perturbation_seed,topology_path_step,affine_span_rank,connected,"
    "edge_lower_bound,min_incident_direction_rank,rigid_rank,generic_solid_gate,"
    "intentionally_flexible,exact_control,input_checkpoint_sha256_before,"
    "input_checkpoint_sha256_after,diagnostics_read_only_exact".split(",")
)
PACKET_FIELDS = tuple(
    "configuration_id,packet_index,packet_id,mass_quanta,x_m,y_m,z_m,"
    "vx_m_per_s,vy_m_per_s,vz_m_per_s".split(",")
)
RELATION_FIELDS = tuple(
    "configuration_id,relation_index,first_id,second_id,selection_status,"
    "selection_source,reference_length_m,row_norm,row_norm_relative_error,"
    "row_norm_tolerance,row_norm_pass".split(",")
)
OBSERVABILITY_FIELDS = tuple(
    "configuration_id,probe_family,decision_scope,operator_status,row_count,"
    "column_count,row_norm_max_relative_error,row_norm_tolerance,row_norm_pass,"
    "qr_status,qr_rank,svd_rank,rank_agreement,rank_ambiguous,nullity,rigid_rank,"
    "rigid_residual_normalized,rigid_residual_tolerance,rigid_in_kernel,"
    "nonrigid_nullity,nullspace_basis_complete,nullspace_residual_normalized,"
    "nonrigid_residual_normalized,rigid_orthogonality_residual,sigma_max,"
    "sigma_min_nonzero,mu,svd_threshold,svd_ambiguity_lower,svd_ambiguity_upper,"
    "nonzero_threshold_separation,max_resolved_zero,null_threshold_separation,"
    "clear_separation_pass,baseline_mu,mu_retention_ratio,robustness_pass,"
    "classification,decision_gate_pass".split(",")
)
SPECTRUM_FIELDS = tuple(
    "configuration_id,singular_index,singular_value,svd_threshold,threshold_ratio,"
    "classification,is_largest,is_smallest_accepted".split(",")
)
NULLSPACE_FIELDS = tuple(
    "configuration_id,mode_index,mode_operator_residual,rigid_projection_norm,"
    "nonrigid_component_norm,residual_tolerance,vector_sha256,accepted".split(",")
)
NULLSPACE_VECTOR_FIELDS = tuple(
    "configuration_id,mode_index,component_index,packet_id,axis,value".split(",")
)
METAMORPHIC_FIELDS = tuple(
    "control_id,base_configuration_id,variant_configuration_id,control_kind,"
    "physical_graph_equal,operator_covariance_residual,spectrum_residual,"
    "finite_length_scale,finite_length_residual,rank_equal,nullity_equal,"
    "nonrigid_nullity_equal,"
    "mu_relative_error,tolerance,pass".split(",")
)
ID_BIJECTION_FIELDS = tuple(
    "control_id,source_configuration_id,bijection_kind,old_packet_id,new_packet_id,"
    "inverse_packet_id,nontrivial".split(",")
)
TOPOLOGY_PATH_FIELDS = tuple(
    "path_id,configuration_id,deletion_step,removed_first_id,removed_second_id,"
    "edge_count,rank,nullity,nonrigid_nullity,sigma_min_nonzero,sigma_max,mu,"
    "nonzero_threshold_separation,rank_reference_kind,rank_certified,"
    "classification,transition".split(",")
)
LOOKUP_FIELDS = tuple(
    "configuration_id,phase_id,brute_force_edge_count,lookup_edge_count,"
    "canonical_equal,pass".split(",")
)
CHECKPOINT_FIELDS = tuple(
    "configuration_id,encoding,byte_count,payload_sha256_before,"
    "payload_sha256_roundtrip,payload_sha256_after,roundtrip_exact,"
    "diagnostics_read_only_exact,pass".split(",")
)
CSV_SCHEMAS: dict[str, tuple[str, ...]] = {
    "configurations.csv": CONFIGURATION_FIELDS,
    "packets.csv": PACKET_FIELDS,
    "relations.csv": RELATION_FIELDS,
    "observability.csv": OBSERVABILITY_FIELDS,
    "spectra.csv": SPECTRUM_FIELDS,
    "nullspace.csv": NULLSPACE_FIELDS,
    "nullspace_vectors.csv": NULLSPACE_VECTOR_FIELDS,
    "metamorphic.csv": METAMORPHIC_FIELDS,
    "id_bijections.csv": ID_BIJECTION_FIELDS,
    "topology_path.csv": TOPOLOGY_PATH_FIELDS,
    "lookup.csv": LOOKUP_FIELDS,
    "checkpoints.csv": CHECKPOINT_FIELDS,
}
REQUIRED_DATA_FILES = (*CSV_SCHEMAS, SUMMARY_FILE, TOLERANCE_FILE)
REQUIRED_FILES = (*REQUIRED_DATA_FILES, MANIFEST_FILE)


def canonical_tree(root: pathlib.Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            reject(f"bundle contains symlink: {path.relative_to(root).as_posix()}")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if path.stat().st_size > MAX_FILE_BYTES:
                reject(f"bundle file too large: {relative}")
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def read_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"cannot read {path.name}: {error}") from error
    if not isinstance(value, dict):
        reject(f"{path.name}: root must be an object")
    return value


def read_csv(path: pathlib.Path, fields: Sequence[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != tuple(fields):
                reject(f"{path.name}: header mismatch")
            rows: list[dict[str, str]] = []
            for row_index, row in enumerate(reader):
                if row_index >= MAX_ROWS:
                    reject(f"{path.name}: row limit exceeded")
                if None in row or any(value is None for value in row.values()):
                    reject(f"{path.name}: malformed row {row_index + 2}")
                if any(len(value) > MAX_FIELD_CHARS for value in row.values()):
                    reject(f"{path.name}: oversized field")
                rows.append(row)
            return rows
    except (OSError, UnicodeError, csv.Error) as error:
        raise ValidationError(f"cannot read {path.name}: {error}") from error


def require_fields(
    value: Mapping[str, Any], required: set[str], where: str
) -> None:
    missing = required - set(value)
    unexpected = set(value) - required
    if missing or unexpected:
        reject(
            f"{where}: key mismatch; missing={sorted(missing)}; "
            f"unexpected={sorted(unexpected)}"
        )


def manifest_preimage(hashes: Mapping[str, str]) -> bytes:
    return "".join(
        f"{name}={hashes[name]}\n" for name in sorted(hashes)
    ).encode("utf-8")


def verify_manifest(root: pathlib.Path, configuration_ids: Sequence[str]) -> dict[str, str]:
    manifest = read_json(root / MANIFEST_FILE)
    require_fields(
        manifest,
        {
            "schema",
            "mode",
            "source_sha",
            "branch",
            "dirty",
            "expected_rows",
            "actual_rows",
            "file_sha256",
            "pre_hash_sha256",
        },
        MANIFEST_FILE,
    )
    if manifest["schema"] != MANIFEST_SCHEMA:
        reject("manifest schema mismatch")
    if manifest["mode"] not in {"full", "smoke"}:
        reject("manifest mode")
    source_sha(manifest["source_sha"], "manifest source SHA")
    identifier(manifest["branch"], "manifest branch")
    if manifest["mode"] == "full" and manifest["branch"] != BRANCH:
        reject("full manifest branch")
    if not isinstance(manifest["dirty"], bool):
        reject("manifest dirty type")
    for key in ("expected_rows", "actual_rows", "file_sha256"):
        if not isinstance(manifest[key], dict):
            reject(f"manifest {key} must be an object")
    expected_payloads = {
        *REQUIRED_DATA_FILES,
        *(f"checkpoints/{configuration_id}.bin" for configuration_id in configuration_ids),
    }
    hashes = manifest["file_sha256"]
    if set(hashes) != expected_payloads:
        reject(
            "manifest payload inventory mismatch: "
            f"{sorted(set(hashes) ^ expected_payloads)}"
        )
    tree = canonical_tree(root)
    if set(tree) != {*expected_payloads, MANIFEST_FILE}:
        reject(
            "bundle file inventory mismatch: "
            f"{sorted(set(tree) ^ {*expected_payloads, MANIFEST_FILE})}"
        )
    checked: dict[str, str] = {}
    for name in sorted(expected_payloads):
        claimed = sha256_text(hashes[name], f"manifest {name}")
        actual = tree[name]
        if claimed != actual:
            reject(f"manifest digest mismatch for {name}")
        checked[name] = actual
    pre_hash = hashlib.sha256(manifest_preimage(checked)).hexdigest()
    if sha256_text(manifest["pre_hash_sha256"], "manifest pre-hash") != pre_hash:
        reject("manifest pre-hash mismatch")
    return checked


def parse_checkpoint(
    path: pathlib.Path,
    configuration: Mapping[str, str],
    packet_rows: Sequence[Mapping[str, str]],
    edges: Sequence[tuple[int, int]],
    audit: Audit,
) -> tuple[bytes, str]:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise ValidationError(f"cannot read checkpoint {path.name}: {error}") from error
    offset = 0

    def take(fmt: str, where: str) -> Any:
        nonlocal offset
        size = struct.calcsize(fmt)
        audit.require(offset + size <= len(payload), f"{path.name}: truncated {where}")
        values = struct.unpack_from(fmt, payload, offset)
        offset += size
        return values[0] if len(values) == 1 else values

    audit.require(payload[:8] == b"MLSMOBS1", f"{path.name}: magic")
    offset = 8
    audit.require(take("<I", "version") == 1, f"{path.name}: version")
    support = take("<d", "support radius")
    audit.require(math.isfinite(support) and support > 0.0, f"{path.name}: support")
    audit.require(
        support.hex() == configuration["support_radius_m"],
        f"{path.name}: support binding",
    )
    packet_count = take("<Q", "packet count")
    audit.require(packet_count == len(packet_rows), f"{path.name}: packet count")
    observed_ids: list[int] = []
    for index, row in enumerate(packet_rows):
        packet_id = take("<Q", f"packet {index} id")
        mass = take("<q", f"packet {index} mass")
        state = take("<6d", f"packet {index} state")
        audit.require(packet_id == int(row["packet_id"]), f"{path.name}: packet ID")
        audit.require(mass == int(row["mass_quanta"]), f"{path.name}: packet mass")
        audit.require(
            all(math.isfinite(value) for value in state),
            f"{path.name}: finite packet state",
        )
        for value, field in zip(
            state,
            ("x_m", "y_m", "z_m", "vx_m_per_s", "vy_m_per_s", "vz_m_per_s"),
            strict=True,
        ):
            audit.require(value.hex() == row[field], f"{path.name}: packet {field}")
        observed_ids.append(packet_id)
    audit.require(
        observed_ids == sorted(set(observed_ids)), f"{path.name}: canonical packet IDs"
    )
    bond_count = take("<Q", "bond count")
    observed_edges = [
        (take("<Q", f"bond {index} first"), take("<Q", f"bond {index} second"))
        for index in range(bond_count)
    ]
    audit.require(
        observed_edges == sorted(set(observed_edges))
        and all(first < second for first, second in observed_edges),
        f"{path.name}: canonical bonds",
    )
    audit.require(observed_edges == list(edges), f"{path.name}: bond binding")
    volume_count = take("<Q", "volume count")
    audit.require(volume_count == 0, f"{path.name}: Candidate-C volume state forbidden")
    audit.require(offset == len(payload), f"{path.name}: trailing bytes")
    return payload, hashlib.sha256(payload).hexdigest()


def validate_tolerances(value: Mapping[str, Any], audit: Audit) -> dict[str, float]:
    required = {
        "schema",
        "epsilon",
        "qr_roundoff_factor",
        "svd_roundoff_factor",
        "ambiguity_factor",
        "residual_factor",
        "row_norm_factor",
        "row_norm_target",
        "similarity_factor",
        "mu_retention_min",
        "perturbation_amplitudes",
        "perturbation_seeds",
        "deformations",
        "nested_deletion_preimage",
        "high_precision_deletion_steps",
        "registered_topology_transition",
        "decision_order",
    }
    require_fields(value, required, TOLERANCE_FILE)
    audit.require(value["schema"] == TOLERANCE_SCHEMA, "tolerance schema")
    audit.require(value["epsilon"] == (2.0**-52).hex(), "tolerance epsilon")
    expected_integers = {
        "qr_roundoff_factor": 512,
        "svd_roundoff_factor": 512,
        "ambiguity_factor": 8,
        "residual_factor": 4096,
        "row_norm_factor": 64,
        "similarity_factor": 16384,
    }
    for key, expected in expected_integers.items():
        audit.require(value[key] == expected, f"tolerance {key}")
    audit.require(
        value["row_norm_target"] == math.sqrt(2.0).hex(),
        "row-norm target",
    )
    audit.require(value["mu_retention_min"] == (1.0 / 1024.0).hex(), "mu retention")
    amplitudes = [(1.0 / 10000.0).hex(), (1.0 / 1000.0).hex(), (1.0 / 100.0).hex()]
    audit.require(value["perturbation_amplitudes"] == amplitudes, "perturbation amplitudes")
    audit.require(value["perturbation_seeds"] == [260829, 260830, 260831], "perturbation seeds")
    audit.require(value["decision_order"] == list(VERDICTS), "decision order")

    h = lambda value: float(value).hex()
    expected_deformations = {
        "isotropic_compression": {
            "matrix": [h(Q(4, 5))] * 3,
            "det": h(Q(64, 125)),
        },
        "isotropic_expansion": {
            "matrix": [h(Q(5, 4))] * 3,
            "det": h(Q(125, 64)),
        },
        "pure_shear": [h(Q(5, 4)), h(Q(4, 5)), h(Q(1))],
        "simple_shear": h(Q(1, 4)),
        "general_affine": [
            h(Q(1)), h(Q(1, 5)), h(Q(-1, 10)),
            h(Q(1, 10)), h(Q(9, 10)), h(Q(1, 8)),
            h(Q(-1, 12)), h(Q(1, 10)), h(Q(11, 10)),
            h(Q(11339, 12000)),
        ],
    }
    audit.require(value["deformations"] == expected_deformations, "deformation table")
    audit.require(
        value["nested_deletion_preimage"]
        == "260828|relational_observability_nested_delete_v1|first_id|second_id",
        "nested deletion preimage",
    )
    audit.require(
        value["high_precision_deletion_steps"]
        == [0, 25, 50, 52, 53, 54, 55, 75, 100, 125, 150, 158],
        "high-precision deletion steps",
    )
    audit.require(
        value["registered_topology_transition"]
        == {
            "source_configuration_id": "base.sc3.r180.original",
            "edge_count": 158,
            "transition_adjacent_before_step": 52,
            "last_rigid_step": 53,
            "first_nonrigid_step": 54,
            "first_nonrigid_exact_fraction_rank": 74,
            "transition_adjacent_after_step": 55,
            "complete_deletion_step": 158,
        },
        "registered topology transition",
    )
    return {
        "epsilon": 2.0**-52,
        "rank_factor": 512.0,
        "ambiguity_factor": 8.0,
        "residual_factor": 4096.0,
        "row_norm_factor": 64.0,
        "similarity_factor": 16384.0,
        "mu_retention_min": 1.0 / 1024.0,
    }


def validate_summary_metadata(
    value: Mapping[str, Any], *, allow_dirty: bool, audit: Audit
) -> None:
    required = {
        "schema",
        "mode",
        "provisional",
        "sweep_complete",
        "producer",
        "seed",
        "source_sha",
        "parent_sha",
        "accepted_candidate_c_source_sha",
        "branch",
        "dirty",
        "verdict",
        "no_promotion",
        "candidate",
        "candidate_b_decision_input_count",
        "candidate_d_instantiated",
        "inherited_git_blobs",
        "fixture_table_sha256",
        "counts",
        "gate_counts",
        "compiler",
        "direct_svd",
        "pre_hash_sha256",
    }
    require_fields(value, required, SUMMARY_FILE)
    audit.require(value["schema"] == SUMMARY_SCHEMA, "summary schema")
    audit.require(value["mode"] in {"full", "smoke"}, "summary mode")
    for key in (
        "provisional",
        "sweep_complete",
        "dirty",
        "no_promotion",
        "candidate_d_instantiated",
    ):
        audit.require(isinstance(value[key], bool), f"summary {key} type")
    audit.require(value["producer"] == PRODUCER, "summary producer")
    audit.require(value["seed"] == SEED, "summary seed")
    source_sha(value["source_sha"], "summary source SHA")
    audit.require(value["parent_sha"] == PARENT_SHA, "summary parent SHA")
    audit.require(
        value["accepted_candidate_c_source_sha"] == ACCEPTED_C_SOURCE_SHA,
        "summary accepted Candidate-C SHA",
    )
    identifier(value["branch"], "summary branch")
    audit.require(allow_dirty or value["dirty"] is False, "dirty source rejected")
    audit.require(value["verdict"] in VERDICTS, "summary verdict")
    audit.require(value["no_promotion"] is True, "summary no-promotion boundary")
    audit.require(value["candidate"] == CANDIDATE, "summary candidate")
    audit.require(
        value["candidate_b_decision_input_count"] == 0,
        "Candidate B decision leakage",
    )
    audit.require(value["candidate_d_instantiated"] is False, "Candidate D instantiated")
    audit.require(
        isinstance(value["inherited_git_blobs"], dict),
        "summary inherited Git blobs object",
    )
    audit.require(
        value["inherited_git_blobs"] == INHERITED_GIT_BLOBS,
        "summary inherited Git blobs",
    )
    if value["mode"] == "full":
        audit.require(value["branch"] == BRANCH, "full summary branch")
        audit.require(value["provisional"] is False, "full result is provisional")
        audit.require(value["sweep_complete"] is True, "full sweep incomplete")
        audit.require(value["dirty"] is False or allow_dirty, "full dirty source")
        audit.require(value["fixture_table_sha256"] == FIXTURE_HASHES, "fixture hashes")
    else:
        audit.require(value["provisional"] is True, "smoke result not provisional")
        audit.require(
            value["sweep_complete"] is False,
            "smoke result claims a complete sweep",
        )
        audit.require(
            value["verdict"] == VERDICTS[0],
            "provisional smoke must remain inconclusive",
        )
    for key in ("fixture_table_sha256", "counts", "gate_counts", "compiler"):
        audit.require(isinstance(value[key], dict), f"summary {key} object")
    compiler = value["compiler"]
    audit.require(
        isinstance(compiler.get("id"), str) and bool(compiler["id"]),
        "compiler ID",
    )
    audit.require(
        isinstance(compiler.get("version"), str) and bool(compiler["version"]),
        "compiler version",
    )
    audit.require(value["direct_svd"] == "rectangular_one_sided_jacobi", "direct SVD")
    sha256_text(value["pre_hash_sha256"], "summary pre-hash")


def grouped_rows(
    rows: Sequence[dict[str, str]], key: str
) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        result[row[key]].append(row)
    return dict(result)


def unique_rows(
    rows: Sequence[dict[str, str]], key: str, where: str
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        value = identifier(row[key], f"{where} {key}")
        if value in result:
            reject(f"{where}: duplicate {key} {value}")
        result[value] = row
    return result


def validate_configurations(
    rows: Sequence[dict[str, str]], audit: Audit
) -> dict[str, dict[str, str]]:
    configurations = unique_rows(rows, "configuration_id", "configurations")
    audit.require(bool(configurations), "configuration inventory empty")
    audit.require(
        [row["configuration_id"] for row in rows] == sorted(configurations),
        "configuration rows not canonical",
    )
    for configuration_id, row in configurations.items():
        source_id = identifier(
            row["source_configuration_id"], f"{configuration_id} source"
        )
        enum_text(row["probe_family"], PROBE_FAMILIES, f"{configuration_id} probe family")
        for field in ("probe_id", "family", "profile", "transform"):
            identifier(row[field], f"{configuration_id} {field}")
        enum_text(
            row["decision_scope"], DECISION_SCOPES, f"{configuration_id} decision scope"
        )
        packet_count = unsigned(row["packet_count"], f"{configuration_id} packet count", minimum=1)
        unsigned(row["edge_count"], f"{configuration_id} edge count")
        spacing = binary64(row["nominal_spacing_m"], f"{configuration_id} spacing")
        support = binary64(row["support_radius_m"], f"{configuration_id} support")
        scale = binary64(row["geometry_scale"], f"{configuration_id} scale")
        audit.require(spacing > 0.0 and support > 0.0 and scale > 0.0, f"{configuration_id}: positive scales")
        determinant = optional_binary64(row["deformation_det"], f"{configuration_id} determinant")
        if determinant is not None:
            audit.require(determinant > 0.0, f"{configuration_id}: positive determinant")
        amplitude = optional_binary64(
            row["perturbation_amplitude_ratio"], f"{configuration_id} perturbation amplitude"
        )
        if amplitude is not None:
            audit.require(amplitude >= 0.0, f"{configuration_id}: perturbation amplitude")
        optional_unsigned(row["perturbation_seed"], f"{configuration_id} perturbation seed")
        optional_unsigned(row["topology_path_step"], f"{configuration_id} topology step")
        affine_rank = unsigned(row["affine_span_rank"], f"{configuration_id} affine rank")
        edge_lower = unsigned(row["edge_lower_bound"], f"{configuration_id} edge lower bound")
        direction_rank = unsigned(
            row["min_incident_direction_rank"], f"{configuration_id} direction rank"
        )
        rigid_rank = unsigned(row["rigid_rank"], f"{configuration_id} rigid rank")
        audit.require(affine_rank <= 3 and direction_rank <= 3 and rigid_rank <= 6, f"{configuration_id}: rank bounds")
        audit.require(edge_lower == max(0, 3 * packet_count - 6), f"{configuration_id}: edge lower bound")
        for field in (
            "connected",
            "generic_solid_gate",
            "intentionally_flexible",
            "exact_control",
            "diagnostics_read_only_exact",
        ):
            bool_text(row[field], f"{configuration_id} {field}")
        sha256_text(row["input_checkpoint_sha256_before"], f"{configuration_id} checkpoint before")
        sha256_text(row["input_checkpoint_sha256_after"], f"{configuration_id} checkpoint after")
        audit.require(source_id in configurations, f"{configuration_id}: source missing")
        if row["probe_family"] == "inherited":
            if row["transform"] == "identity":
                audit.require(source_id == configuration_id, f"{configuration_id}: identity source")
            else:
                source = configurations[source_id]
                audit.require(source["probe_family"] == "inherited", f"{configuration_id}: inherited parent kind")
                audit.require(source["transform"] == "identity", f"{configuration_id}: inherited parent identity")
                audit.require(
                    source["family"] == row["family"]
                    and source["profile"] == row["profile"],
                    f"{configuration_id}: inherited parent family/profile",
                )
        if row["decision_scope"] == "eligible_generic":
            audit.require(
                bool_text(row["generic_solid_gate"], f"{configuration_id} generic gate"),
                f"{configuration_id}: eligible scope without generic gate",
            )
        if row["decision_scope"] == "intentionally_flexible":
            audit.require(
                bool_text(row["intentionally_flexible"], f"{configuration_id} flexible"),
                f"{configuration_id}: flexible scope mismatch",
            )
    return configurations


def inherited_transform_contract(
    configuration_id: str,
) -> tuple[str, str, str]:
    suffixes = (
        (".rotation_translation", "rotation_translation", "rational_quaternion_rotation_translation"),
        (".scale_double_rotation", "scale_double_rotation", "scale_double_rotation"),
        (".scale_half_rotation", "scale_half_rotation", "scale_half_rotation"),
        (".translation", "translation", "translation"),
        (".rotation", "rotation", "rational_quaternion_rotation"),
    )
    for suffix, probe_id, transform in suffixes:
        if configuration_id.endswith(suffix):
            return configuration_id.removesuffix(suffix), probe_id, transform
    return configuration_id, "original", "identity"


def validate_full_configuration_inventory(
    configurations: Mapping[str, Mapping[str, str]], audit: Audit
) -> dict[str, tuple[str, str, str]]:
    inherited = {
        configuration_id
        for configuration_id, row in configurations.items()
        if row["probe_family"] == "inherited"
    }
    audit.require(inherited == FULL_INHERITED_IDS, "full inherited configuration inventory")
    for configuration_id in sorted(inherited):
        source_id, probe_id, transform = inherited_transform_contract(configuration_id)
        row = configurations[configuration_id]
        audit.require(
            (row["source_configuration_id"], row["probe_id"], row["transform"])
            == (source_id, probe_id, transform),
            f"{configuration_id}: frozen inherited identity/transform metadata",
        )

    eligible_inherited = {
        configuration_id
        for configuration_id in inherited
        if configurations[configuration_id]["decision_scope"] == "eligible_generic"
    }
    audit.require(len(eligible_inherited) == 37, "full eligible inherited inventory")
    perturbation_ids = {
        f"geometry.{source}.a{amplitude_label}.s{seed}"
        for source in PERTURBATION_SOURCES
        for _amplitude, amplitude_label in PERTURBATION_AMPLITUDES
        for seed in PERTURBATION_SEEDS
    }
    deformation_ids = {
        f"deformation.{source}.{probe}"
        for source in eligible_inherited
        for probe in DEFORMATION_MATRICES
    }
    bijection_ids = {
        f"{kind}.{source}"
        for source in inherited
        for kind in ID_BIJECTION_KINDS
    }
    deletion_ids = {
        f"topology.base.sc3.r180.original.step{step:03d}"
        for step in range(159)
    }
    expected = (
        inherited
        | perturbation_ids
        | deformation_ids
        | bijection_ids
        | deletion_ids
    )
    audit.require(set(configurations) == expected, "full generated configuration inventory")
    for expected_family, expected_ids in (
        ("geometry_perturbation", perturbation_ids),
        ("homogeneous_deformation", deformation_ids),
        ("id_bijection", bijection_ids),
        ("topology_deletion", deletion_ids),
    ):
        actual = {
            configuration_id
            for configuration_id, row in configurations.items()
            if row["probe_family"] == expected_family
        }
        audit.require(actual == expected_ids, f"full {expected_family} inventory")

    expected_controls: dict[str, tuple[str, str, str]] = {}
    inherited_kinds = {
        "translation": "inherited_translation",
        "rational_quaternion_rotation": "inherited_proper_rotation",
        "rational_quaternion_rotation_translation": "inherited_rotation_translation",
        "scale_half_rotation": "inherited_scale_half",
        "scale_double_rotation": "inherited_scale_double",
    }
    for variant_id in sorted(inherited):
        base_id, probe_id, transform = inherited_transform_contract(variant_id)
        if transform != "identity":
            expected_controls[f"control.{probe_id}.{base_id}"] = (
                base_id,
                variant_id,
                inherited_kinds[transform],
            )
    for source_id in sorted(inherited):
        expected_controls[f"control.packet_permutation.{source_id}"] = (
            source_id,
            source_id,
            "packet_permutation",
        )
        expected_controls[f"control.relation_permutation.{source_id}"] = (
            source_id,
            source_id,
            "relation_permutation",
        )
        for kind in sorted(ID_BIJECTION_KINDS):
            expected_controls[f"control.{kind}.{source_id}"] = (
                source_id,
                f"{kind}.{source_id}",
                kind,
            )
    audit.require(len(expected_controls) == 325, "full metamorphic control count")
    return expected_controls


def validate_packets(
    rows: Sequence[dict[str, str]],
    configurations: Mapping[str, Mapping[str, str]],
    audit: Audit,
) -> tuple[
    dict[str, list[dict[str, str]]],
    dict[str, dict[int, Vec3Q]],
    dict[str, dict[int, Vec3D]],
]:
    grouped = grouped_rows(rows, "configuration_id")
    audit.require(set(grouped) == set(configurations), "packet/configuration inventory")
    exact_positions: dict[str, dict[int, Vec3Q]] = {}
    decimal_positions: dict[str, dict[int, Vec3D]] = {}
    for configuration_id in sorted(configurations):
        packet_rows = grouped[configuration_id]
        expected_count = int(configurations[configuration_id]["packet_count"])
        audit.require(len(packet_rows) == expected_count, f"{configuration_id}: packet count")
        ids: list[int] = []
        positions_q: dict[int, Vec3Q] = {}
        positions_d: dict[int, Vec3D] = {}
        for expected_index, row in enumerate(packet_rows):
            audit.require(
                unsigned(row["packet_index"], f"{configuration_id} packet index") == expected_index,
                f"{configuration_id}: packet indices",
            )
            packet_id = unsigned(row["packet_id"], f"{configuration_id} packet ID", minimum=1)
            unsigned(row["mass_quanta"], f"{configuration_id} mass", minimum=1)
            ids.append(packet_id)
            positions_q[packet_id] = tuple(
                fraction64(row[field], f"{configuration_id}/{packet_id}/{field}")
                for field in ("x_m", "y_m", "z_m")
            )  # type: ignore[assignment]
            positions_d[packet_id] = tuple(
                decimal64(row[field], f"{configuration_id}/{packet_id}/{field}")
                for field in ("x_m", "y_m", "z_m")
            )  # type: ignore[assignment]
            for field in ("vx_m_per_s", "vy_m_per_s", "vz_m_per_s"):
                binary64(row[field], f"{configuration_id}/{packet_id}/{field}")
        audit.require(ids == sorted(set(ids)), f"{configuration_id}: canonical packet IDs")
        exact_positions[configuration_id] = positions_q
        decimal_positions[configuration_id] = positions_d
    return grouped, exact_positions, decimal_positions


def validate_relations(
    rows: Sequence[dict[str, str]],
    configurations: Mapping[str, Mapping[str, str]],
    positions_q: Mapping[str, Mapping[int, Vec3Q]],
    tolerances: Mapping[str, float],
    audit: Audit,
) -> tuple[dict[str, list[dict[str, str]]], dict[str, list[tuple[int, int]]]]:
    grouped = grouped_rows(rows, "configuration_id")
    # Complete deletion legitimately has no relation rows.
    audit.require(set(grouped) <= set(configurations), "relation/configuration inventory")
    by_configuration: dict[str, list[dict[str, str]]] = {}
    edges_by_configuration: dict[str, list[tuple[int, int]]] = {}
    target = math.sqrt(2.0)
    expected_tolerance = tolerances["row_norm_factor"] * tolerances["epsilon"]
    for configuration_id in sorted(configurations):
        relation_rows = grouped.get(configuration_id, [])
        expected_count = int(configurations[configuration_id]["edge_count"])
        audit.require(len(relation_rows) == expected_count, f"{configuration_id}: edge count")
        positions = positions_q[configuration_id]
        edges: list[tuple[int, int]] = []
        for expected_index, row in enumerate(relation_rows):
            audit.require(
                unsigned(row["relation_index"], f"{configuration_id} relation index") == expected_index,
                f"{configuration_id}: relation indices",
            )
            first = unsigned(row["first_id"], f"{configuration_id} first ID", minimum=1)
            second = unsigned(row["second_id"], f"{configuration_id} second ID", minimum=1)
            audit.require(first < second, f"{configuration_id}: canonical relation endpoints")
            audit.require(first in positions and second in positions, f"{configuration_id}: dangling relation")
            audit.require(row["selection_status"] == "retained", f"{configuration_id}: relation not retained")
            identifier(row["selection_source"], f"{configuration_id} selection source")
            edges.append((first, second))
            delta = [positions[second][axis] - positions[first][axis] for axis in range(3)]
            length = math.sqrt(float(qsum(value * value for value in delta)))
            observed_length = binary64(row["reference_length_m"], f"{configuration_id} reference length")
            audit.require(length > 0.0, f"{configuration_id}: zero-length relation")
            close_float(
                observed_length,
                length,
                64.0 * tolerances["epsilon"],
                f"{configuration_id}: reference length",
                scale_floor=sys.float_info.min,
            )
            norm = binary64(row["row_norm"], f"{configuration_id} row norm")
            relative_error = binary64(
                row["row_norm_relative_error"], f"{configuration_id} row norm relative error"
            )
            row_tolerance = binary64(
                row["row_norm_tolerance"], f"{configuration_id} row norm tolerance"
            )
            close_float(row_tolerance, expected_tolerance, 8.0 * tolerances["epsilon"], f"{configuration_id}: row tolerance", scale_floor=sys.float_info.min)
            expected_error = abs(norm - target) / target
            close_float(relative_error, expected_error, 16.0 * tolerances["epsilon"], f"{configuration_id}: row norm relative error", scale_floor=sys.float_info.min)
            expected_pass = expected_error <= row_tolerance
            audit.require(
                bool_text(row["row_norm_pass"], f"{configuration_id} row norm pass") == expected_pass,
                f"{configuration_id}: row norm pass mismatch",
            )
        audit.require(edges == sorted(set(edges)), f"{configuration_id}: canonical unique relations")
        by_configuration[configuration_id] = relation_rows
        edges_by_configuration[configuration_id] = edges
    return by_configuration, edges_by_configuration


def splitmix64_once(initial: int) -> int:
    mask = (1 << 64) - 1
    value = (initial + 0x9E3779B97F4A7C15) & mask
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
    return (value ^ (value >> 31)) & mask


def independent_perturbation_direction(seed: int, packet_id: int) -> tuple[float, float, float]:
    values: list[float] = []
    for axis in range(3):
        preimage = f"{seed}|{packet_id}|{axis}".encode("ascii")
        initial = int.from_bytes(hashlib.sha256(preimage).digest()[:8], "big")
        dyadic = splitmix64_once(initial) >> 11
        values.append(dyadic / float(1 << 52) - 1.0)
    norm = math.hypot(*values)
    if norm == 0.0:
        return (1.0, 0.0, 0.0)
    return tuple(value / norm for value in values)  # type: ignore[return-value]


def apply_linear_map(
    matrix: Sequence[Sequence[float]], vector: Sequence[float]
) -> tuple[float, float, float]:
    if len(matrix) != 3 or len(vector) != 3 or any(len(row) != 3 for row in matrix):
        reject("affine reconstruction: invalid dimension")
    return tuple(
        (matrix[axis][0] * vector[0] + matrix[axis][1] * vector[1])
        + matrix[axis][2] * vector[2]
        for axis in range(3)
    )  # type: ignore[return-value]


def determinant3(matrix: Sequence[Sequence[float]]) -> float:
    return (
        matrix[0][0]
        * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1]
        * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2]
        * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def validate_derived_geometry_and_state(
    configurations: Mapping[str, Mapping[str, str]],
    packet_rows: Mapping[str, Sequence[Mapping[str, str]]],
    relation_rows: Mapping[str, Sequence[Mapping[str, str]]],
    edges: Mapping[str, Sequence[tuple[int, int]]],
    *,
    full: bool,
    audit: Audit,
) -> None:
    if not full:
        return
    packets_by_id: dict[str, dict[int, Mapping[str, str]]] = {}
    for configuration_id, rows in packet_rows.items():
        packets_by_id[configuration_id] = {
            unsigned(row["packet_id"], f"{configuration_id} derived packet ID", minimum=1): row
            for row in rows
        }

    common_fields = (
        "family",
        "profile",
        "decision_scope",
        "packet_count",
        "edge_count",
        "nominal_spacing_m",
        "support_radius_m",
        "geometry_scale",
        "generic_solid_gate",
        "intentionally_flexible",
    )

    def validate_common(configuration_id: str, source_id: str) -> None:
        row = configurations[configuration_id]
        source = configurations[source_id]
        audit.require(
            row["source_configuration_id"] == source_id,
            f"{configuration_id}: derived source binding",
        )
        for field in common_fields:
            audit.require(
                row[field] == source[field],
                f"{configuration_id}: inherited {field}",
            )
        audit.require(row["exact_control"] == "false", f"{configuration_id}: derived exact-control claim")
        audit.require(row["topology_path_step"] == "NA", f"{configuration_id}: derived topology step")
        audit.require(
            set(packets_by_id[configuration_id]) == set(packets_by_id[source_id]),
            f"{configuration_id}: derived packet-ID inventory",
        )
        audit.require(
            list(edges[configuration_id]) == list(edges[source_id]),
            f"{configuration_id}: fixed relation topology",
        )

    coordinate_fields = ("x_m", "y_m", "z_m")
    velocity_fields = ("vx_m_per_s", "vy_m_per_s", "vz_m_per_s")
    for source_id in PERTURBATION_SOURCES:
        source_packets = packets_by_id[source_id]
        spacing = binary64(
            configurations[source_id]["nominal_spacing_m"],
            f"{source_id}: perturbation spacing",
        )
        for amplitude, amplitude_label in PERTURBATION_AMPLITUDES:
            for seed in PERTURBATION_SEEDS:
                configuration_id = (
                    f"geometry.{source_id}.a{amplitude_label}.s{seed}"
                )
                validate_common(configuration_id, source_id)
                row = configurations[configuration_id]
                audit.require(
                    (row["probe_id"], row["transform"])
                    == ("jitter", "fixed_topology_jitter"),
                    f"{configuration_id}: perturbation metadata",
                )
                audit.require(
                    row["perturbation_amplitude_ratio"] == amplitude.hex()
                    and row["perturbation_seed"] == str(seed)
                    and row["deformation_det"] == "NA",
                    f"{configuration_id}: perturbation parameters",
                )
                audit.require(
                    all(
                        relation["selection_source"]
                        == "fixed_topology_perturbation"
                        for relation in relation_rows[configuration_id]
                    ),
                    f"{configuration_id}: perturbation relation provenance",
                )
                magnitude = amplitude * spacing
                for packet_id, source_packet in source_packets.items():
                    packet = packets_by_id[configuration_id][packet_id]
                    audit.require(
                        packet["mass_quanta"] == source_packet["mass_quanta"],
                        f"{configuration_id}/{packet_id}: perturbation mass",
                    )
                    for field in velocity_fields:
                        audit.require(
                            packet[field] == source_packet[field],
                            f"{configuration_id}/{packet_id}: perturbation velocity {field}",
                        )
                    direction = independent_perturbation_direction(seed, packet_id)
                    for axis, field in enumerate(coordinate_fields):
                        source_value = binary64(
                            source_packet[field],
                            f"{source_id}/{packet_id}: source {field}",
                        )
                        expected = source_value + direction[axis] * magnitude
                        observed = binary64(
                            packet[field], f"{configuration_id}/{packet_id}: {field}"
                        )
                        close_float(
                            observed,
                            expected,
                            32.0 * sys.float_info.epsilon,
                            f"{configuration_id}/{packet_id}: reconstructed {field}",
                            scale_floor=max(abs(source_value), spacing, sys.float_info.min),
                        )

    for source_id in sorted(FULL_INHERITED_IDS):
        if configurations[source_id]["decision_scope"] != "eligible_generic":
            continue
        source_packets = packets_by_id[source_id]
        for probe, matrix in DEFORMATION_MATRICES.items():
            configuration_id = f"deformation.{source_id}.{probe}"
            validate_common(configuration_id, source_id)
            row = configurations[configuration_id]
            audit.require(
                (row["probe_id"], row["transform"]) == (probe, probe),
                f"{configuration_id}: deformation metadata",
            )
            audit.require(
                row["perturbation_amplitude_ratio"] == "NA"
                and row["perturbation_seed"] == "NA",
                f"{configuration_id}: deformation perturbation fields",
            )
            observed_det = binary64(
                row["deformation_det"], f"{configuration_id}: deformation determinant"
            )
            expected_det = determinant3(matrix)
            close_float(
                observed_det,
                expected_det,
                8.0 * sys.float_info.epsilon,
                f"{configuration_id}: reconstructed determinant",
                scale_floor=sys.float_info.min,
            )
            audit.require(
                all(
                    relation["selection_source"] == "fixed_topology_deformation"
                    for relation in relation_rows[configuration_id]
                ),
                f"{configuration_id}: deformation relation provenance",
            )
            for packet_id, source_packet in source_packets.items():
                packet = packets_by_id[configuration_id][packet_id]
                audit.require(
                    packet["mass_quanta"] == source_packet["mass_quanta"],
                    f"{configuration_id}/{packet_id}: deformation mass",
                )
                for fields, label in (
                    (coordinate_fields, "position"),
                    (velocity_fields, "velocity"),
                ):
                    source_vector = tuple(
                        binary64(
                            source_packet[field],
                            f"{source_id}/{packet_id}: source {field}",
                        )
                        for field in fields
                    )
                    expected_vector = apply_linear_map(matrix, source_vector)
                    scale = max(
                        (abs(value) for value in source_vector),
                        default=sys.float_info.min,
                    )
                    scale = max(scale, sys.float_info.min)
                    for axis, field in enumerate(fields):
                        observed = binary64(
                            packet[field], f"{configuration_id}/{packet_id}: {field}"
                        )
                        close_float(
                            observed,
                            expected_vector[axis],
                            16.0 * sys.float_info.epsilon,
                            f"{configuration_id}/{packet_id}: reconstructed {label} {axis}",
                            scale_floor=scale,
                        )


def validate_relational_derivation_metadata(
    configurations: Mapping[str, Mapping[str, str]],
    packet_rows: Mapping[str, Sequence[Mapping[str, str]]],
    audit: Audit,
) -> None:
    packets_by_id = {
        configuration_id: {
            unsigned(row["packet_id"], f"{configuration_id} packet ID", minimum=1): row
            for row in rows
        }
        for configuration_id, rows in packet_rows.items()
    }
    packet_state_fields = (
        "mass_quanta",
        "x_m",
        "y_m",
        "z_m",
        "vx_m_per_s",
        "vy_m_per_s",
        "vz_m_per_s",
    )
    for configuration_id, row in configurations.items():
        if row["probe_family"] == "topology_deletion":
            source_id = row["source_configuration_id"]
            source = configurations[source_id]
            audit.require(
                (row["probe_id"], row["transform"], row["decision_scope"])
                == (
                    "nested_delete",
                    "fixed_geometry_link_deletion",
                    "non_generic_control",
                ),
                f"{configuration_id}: topology derivation metadata",
            )
            for field in (
                "family",
                "profile",
                "packet_count",
                "nominal_spacing_m",
                "support_radius_m",
                "geometry_scale",
                "intentionally_flexible",
            ):
                audit.require(
                    row[field] == source[field],
                    f"{configuration_id}: topology source {field}",
                )
            audit.require(
                row["deformation_det"] == "NA"
                and row["perturbation_amplitude_ratio"] == "NA"
                and row["perturbation_seed"] == "NA"
                and row["exact_control"] == "false",
                f"{configuration_id}: topology non-topology metadata",
            )
            source_packets = packets_by_id[source_id]
            derived_packets = packets_by_id[configuration_id]
            audit.require(
                set(derived_packets) == set(source_packets),
                f"{configuration_id}: topology packet-ID inventory",
            )
            for packet_id, source_packet in source_packets.items():
                derived_packet = derived_packets[packet_id]
                for field in packet_state_fields:
                    audit.require(
                        derived_packet[field] == source_packet[field],
                        f"{configuration_id}/{packet_id}: topology packet {field}",
                    )
        elif row["probe_family"] == "id_bijection":
            source_id = row["source_configuration_id"]
            source = configurations[source_id]
            kind = enum_text(
                row["probe_id"], ID_BIJECTION_KINDS, f"{configuration_id} bijection kind"
            )
            audit.require(
                configuration_id == f"{kind}.{source_id}"
                and row["transform"] == kind,
                f"{configuration_id}: ID-bijection identity metadata",
            )
            audit.require(
                source["probe_family"] == "inherited",
                f"{configuration_id}: ID-bijection source kind",
            )
            for field in (
                "family",
                "profile",
                "decision_scope",
                "packet_count",
                "edge_count",
                "nominal_spacing_m",
                "support_radius_m",
                "geometry_scale",
                "generic_solid_gate",
                "intentionally_flexible",
            ):
                audit.require(
                    row[field] == source[field],
                    f"{configuration_id}: ID-bijection source {field}",
                )
            audit.require(
                row["deformation_det"] == "NA"
                and row["perturbation_amplitude_ratio"] == "NA"
                and row["perturbation_seed"] == "NA"
                and row["topology_path_step"] == "NA"
                and row["exact_control"] == "false",
                f"{configuration_id}: ID-bijection derived metadata",
            )


def exact_control_name(configuration_id: str) -> str | None:
    suffix = configuration_id.removeprefix("exact.")
    aliases = {
        "cube_edge_graph": "cube_edge",
        "octahedron_graph": "octahedron",
    }
    suffix = aliases.get(suffix, suffix)
    return suffix if suffix in EXACT_CONTROL_EXPECTED else None


def validate_exact_topology_and_ranks(
    configurations: Mapping[str, Mapping[str, str]],
    positions: Mapping[str, Mapping[int, Vec3Q]],
    edges: Mapping[str, Sequence[tuple[int, int]]],
    *,
    full: bool,
    audit: Audit,
) -> tuple[dict[str, IndependentRank], dict[str, dict[str, int | bool]]]:
    ranks: dict[str, IndependentRank] = {}
    facts_by_configuration: dict[str, dict[str, int | bool]] = {}
    observed_exact_controls: dict[str, str] = {}
    for configuration_id in sorted(configurations):
        configuration = configurations[configuration_id]
        flexible = bool_text(
            configuration["intentionally_flexible"],
            f"{configuration_id} intentionally flexible",
        )
        facts = exact_topology_facts(
            positions[configuration_id], edges[configuration_id], flexible
        )
        facts_by_configuration[configuration_id] = facts
        for field in (
            "affine_span_rank",
            "edge_lower_bound",
            "min_incident_direction_rank",
            "rigid_rank",
        ):
            audit.require(
                int(configuration[field]) == facts[field],
                f"{configuration_id}: exact {field}",
            )
        for field in ("connected", "generic_solid_gate"):
            audit.require(
                bool_text(configuration[field], f"{configuration_id} {field}")
                == facts[field],
                f"{configuration_id}: exact {field}",
            )
        exact_control = bool_text(
            configuration["exact_control"], f"{configuration_id} exact control"
        )
        rank = independent_rank(
            positions[configuration_id],
            edges[configuration_id],
            exact_limit=12 if exact_control else 0,
        )
        ranks[configuration_id] = rank
        if exact_control:
            name = exact_control_name(configuration_id)
            audit.require(name is not None, f"{configuration_id}: unmapped exact control")
            if name is None:  # keeps type narrowing independent of assertions/-O
                reject(f"{configuration_id}: unmapped exact control")
            audit.require(name not in observed_exact_controls, f"duplicate exact control {name}")
            observed_exact_controls[name] = configuration_id
            expected = EXACT_CONTROL_EXPECTED[name]
            actual = (
                rank.rank,
                rank.nullity,
                rank.rigid_rank,
                rank.nullity - rank.rigid_rank,
            )
            audit.require(actual == expected, f"{configuration_id}: exact rank map")
            audit.require(rank.method == "Fraction_RREF", f"{configuration_id}: exact method")
    if full:
        audit.require(
            set(observed_exact_controls) == set(EXACT_CONTROL_EXPECTED),
            "exact-control inventory",
        )
        deletion_by_step = {
            unsigned(row["topology_path_step"], f"{configuration_id} topology step"):
            configuration_id
            for configuration_id, row in configurations.items()
            if row["probe_family"] == "topology_deletion"
        }
        audit.require(
            set(deletion_by_step) == set(range(159)),
            "certified deletion-transition inventory",
        )
        first_exact_loss: int | None = None
        for step in range(159):
            configuration_id = deletion_by_step[step]
            current = ranks[configuration_id]
            target_rank = 3 * len(positions[configuration_id]) - current.rigid_rank
            audit.require(target_rank >= 0, f"{configuration_id}: rigidity target")
            if current.rank == target_rank:
                audit.require(
                    current.certified,
                    f"{configuration_id}: full-rigidity upper-bound certification",
                )
                continue
            exact_rank = q_rref_rank(
                displacement_rigidity_matrix(
                    positions[configuration_id], edges[configuration_id]
                )
            )
            audit.require(
                current.rank <= exact_rank <= target_rank,
                f"{configuration_id}: modular/exact deletion rank bounds",
            )
            exact = IndependentRank(
                rank=exact_rank,
                nullity=3 * len(positions[configuration_id]) - exact_rank,
                rigid_rank=current.rigid_rank,
                upper_bound=current.upper_bound,
                method="Fraction_RREF_transition",
                certified=True,
            )
            ranks[configuration_id] = exact
            if exact_rank < target_rank:
                first_exact_loss = step
                break
        audit.require(first_exact_loss is not None, "deletion path never loses rigidity")
        for configuration_id, configuration in configurations.items():
            if configuration["decision_scope"] == "eligible_generic":
                audit.require(
                    ranks[configuration_id].certified,
                    f"{configuration_id}: uncertified generic decision rank",
                )
    return ranks, facts_by_configuration


def validate_spectra_and_observability(
    spectrum_rows: Sequence[dict[str, str]],
    observability_rows: Sequence[dict[str, str]],
    relation_rows: Mapping[str, Sequence[Mapping[str, str]]],
    configurations: Mapping[str, Mapping[str, str]],
    positions: Mapping[str, Mapping[int, Vec3D]],
    edges: Mapping[str, Sequence[tuple[int, int]]],
    exact_ranks: Mapping[str, IndependentRank],
    tolerances: Mapping[str, float],
    audit: Audit,
) -> tuple[
    dict[str, dict[str, str]],
    dict[str, list[dict[str, str]]],
    dict[str, IndependentSpectrum],
]:
    observability = unique_rows(
        observability_rows, "configuration_id", "observability"
    )
    audit.require(set(observability) == set(configurations), "observability inventory")
    spectra = grouped_rows(spectrum_rows, "configuration_id")
    audit.require(set(spectra) == set(configurations), "spectrum inventory")
    independent: dict[str, IndependentSpectrum] = {}
    epsilon = tolerances["epsilon"]
    ambiguity = tolerances["ambiguity_factor"]
    for configuration_id in sorted(configurations):
        configuration = configurations[configuration_id]
        claim = observability[configuration_id]
        audit.require(claim["probe_family"] == configuration["probe_family"], f"{configuration_id}: observability probe family")
        audit.require(claim["decision_scope"] == configuration["decision_scope"], f"{configuration_id}: observability scope")
        enum_text(claim["operator_status"], ANALYSIS_STATUSES, f"{configuration_id} operator status")
        enum_text(claim["qr_status"], ANALYSIS_STATUSES, f"{configuration_id} QR status")
        row_count = unsigned(claim["row_count"], f"{configuration_id} row count")
        column_count = unsigned(claim["column_count"], f"{configuration_id} column count", minimum=1)
        audit.require(row_count == len(edges[configuration_id]), f"{configuration_id}: operator rows")
        audit.require(column_count == 3 * len(positions[configuration_id]), f"{configuration_id}: operator columns")
        dimension = max(6, row_count, column_count)
        residual_tolerance = tolerances["residual_factor"] * dimension * epsilon
        row_tolerance = tolerances["row_norm_factor"] * epsilon
        observed_row_error = binary64(
            claim["row_norm_max_relative_error"], f"{configuration_id} max row error"
        )
        expected_row_error = max(
            (
                binary64(row["row_norm_relative_error"], f"{configuration_id} relation error")
                for row in relation_rows[configuration_id]
            ),
            default=0.0,
        )
        close_float(observed_row_error, expected_row_error, 16.0 * epsilon, f"{configuration_id}: max row error", scale_floor=sys.float_info.min)
        observed_row_tolerance = binary64(
            claim["row_norm_tolerance"], f"{configuration_id} row tolerance"
        )
        close_float(observed_row_tolerance, row_tolerance, 8.0 * epsilon, f"{configuration_id}: row tolerance", scale_floor=sys.float_info.min)
        row_norm_pass = all(
            bool_text(row["row_norm_pass"], f"{configuration_id} relation row pass")
            for row in relation_rows[configuration_id]
        )
        audit.require(
            bool_text(claim["row_norm_pass"], f"{configuration_id} row pass") == row_norm_pass,
            f"{configuration_id}: aggregate row-norm pass",
        )

        rows = spectra[configuration_id]
        audit.require(len(rows) == column_count, f"{configuration_id}: complete singular spectrum")
        values: list[float] = []
        for expected_index, row in enumerate(rows):
            audit.require(
                unsigned(row["singular_index"], f"{configuration_id} singular index") == expected_index,
                f"{configuration_id}: singular indices",
            )
            values.append(binary64(row["singular_value"], f"{configuration_id} singular value"))
        audit.require(
            all(values[index] >= values[index + 1] for index in range(len(values) - 1)),
            f"{configuration_id}: spectrum order",
        )
        sigma_max = values[0] if values else 0.0
        threshold = (
            tolerances["rank_factor"]
            * dimension
            * epsilon
            * max(sigma_max, sys.float_info.min)
        )
        lower = threshold / ambiguity
        upper = threshold * ambiguity
        expected_classes = [
            "accepted_nonzero"
            if value > upper
            else "resolved_zero"
            if value < lower
            else "ambiguous"
            for value in values
        ]
        accepted_indices = [
            index for index, value in enumerate(expected_classes) if value == "accepted_nonzero"
        ]
        ambiguous_indices = [
            index for index, value in enumerate(expected_classes) if value == "ambiguous"
        ]
        for index, (row, expected_class) in enumerate(zip(rows, expected_classes, strict=True)):
            enum_text(row["classification"], SPECTRUM_CLASSIFICATIONS, f"{configuration_id} spectrum classification")
            audit.require(row["classification"] == expected_class, f"{configuration_id}: singular classification {index}")
            observed_threshold = binary64(row["svd_threshold"], f"{configuration_id} spectrum threshold")
            close_float(observed_threshold, threshold, 16.0 * epsilon, f"{configuration_id}: spectrum threshold", scale_floor=sys.float_info.min)
            observed_ratio = binary64(row["threshold_ratio"], f"{configuration_id} threshold ratio")
            expected_ratio = values[index] / threshold if threshold else 0.0
            close_float(observed_ratio, expected_ratio, 64.0 * epsilon, f"{configuration_id}: threshold ratio", scale_floor=sys.float_info.min)
            audit.require(
                bool_text(row["is_largest"], f"{configuration_id} is largest") == (index == 0),
                f"{configuration_id}: largest marker",
            )
            audit.require(
                bool_text(row["is_smallest_accepted"], f"{configuration_id} smallest accepted")
                == (bool(accepted_indices) and index == accepted_indices[-1]),
                f"{configuration_id}: smallest accepted marker",
            )

        independent_rank_value = exact_ranks[configuration_id].rank
        qr_rank = unsigned(claim["qr_rank"], f"{configuration_id} QR rank")
        svd_rank = unsigned(claim["svd_rank"], f"{configuration_id} SVD rank")
        rank_agreement = qr_rank == svd_rank == independent_rank_value
        audit.require(
            bool_text(claim["rank_agreement"], f"{configuration_id} rank agreement")
            == rank_agreement,
            f"{configuration_id}: rank agreement flag",
        )
        audit.require(svd_rank == len(accepted_indices), f"{configuration_id}: SVD rank/classification")
        audit.require(
            bool_text(claim["rank_ambiguous"], f"{configuration_id} rank ambiguous")
            == (bool(ambiguous_indices) or claim["qr_status"] == "ambiguous"),
            f"{configuration_id}: rank ambiguity",
        )
        expected_nullity = column_count - independent_rank_value
        rigid_rank = exact_ranks[configuration_id].rigid_rank
        expected_nonrigid = expected_nullity - rigid_rank
        audit.require(expected_nonrigid >= 0, f"{configuration_id}: negative nonrigid nullity")
        audit.require(unsigned(claim["nullity"], f"{configuration_id} nullity") == expected_nullity, f"{configuration_id}: nullity")
        audit.require(unsigned(claim["rigid_rank"], f"{configuration_id} rigid rank") == rigid_rank, f"{configuration_id}: rigid rank")
        audit.require(unsigned(claim["nonrigid_nullity"], f"{configuration_id} nonrigid nullity") == expected_nonrigid, f"{configuration_id}: nonrigid nullity")
        observed_residual_tolerance = binary64(
            claim["rigid_residual_tolerance"], f"{configuration_id} residual tolerance"
        )
        close_float(observed_residual_tolerance, residual_tolerance, 8.0 * epsilon, f"{configuration_id}: residual tolerance", scale_floor=sys.float_info.min)
        for field in (
            "rigid_residual_normalized",
            "nullspace_residual_normalized",
            "nonrigid_residual_normalized",
            "rigid_orthogonality_residual",
        ):
            value = binary64(claim[field], f"{configuration_id} {field}")
            audit.require(value >= 0.0, f"{configuration_id}: negative {field}")
        rigid_in_kernel = bool_text(claim["rigid_in_kernel"], f"{configuration_id} rigid kernel")
        basis_complete = bool_text(claim["nullspace_basis_complete"], f"{configuration_id} basis complete")
        if claim["operator_status"] == "analyzed":
            audit.require(rigid_in_kernel and basis_complete, f"{configuration_id}: analyzed incomplete kernel evidence")
            audit.require(
                binary64(claim["rigid_residual_normalized"], f"{configuration_id} rigid residual") <= residual_tolerance,
                f"{configuration_id}: rigid residual gate",
            )
            audit.require(
                binary64(claim["nullspace_residual_normalized"], f"{configuration_id} null residual") <= residual_tolerance,
                f"{configuration_id}: null residual gate",
            )

        sigma_min = values[independent_rank_value - 1] if independent_rank_value else 0.0
        expected_mu = sigma_min / sigma_max if sigma_max else 0.0
        max_zero = max(
            (value for value, classification in zip(values, expected_classes, strict=True) if classification == "resolved_zero"),
            default=0.0,
        )
        nonzero_separation = sigma_min / upper if upper and sigma_min else 0.0
        null_separation = math.inf if max_zero == 0.0 else lower / max_zero
        numeric_claims = {
            "sigma_max": sigma_max,
            "sigma_min_nonzero": sigma_min,
            "mu": expected_mu,
            "svd_threshold": threshold,
            "svd_ambiguity_lower": lower,
            "svd_ambiguity_upper": upper,
            "nonzero_threshold_separation": nonzero_separation,
            "max_resolved_zero": max_zero,
        }
        for field, expected in numeric_claims.items():
            observed = binary64(claim[field], f"{configuration_id} {field}")
            close_float(observed, expected, 128.0 * epsilon, f"{configuration_id}: {field}", scale_floor=sys.float_info.min)
        observed_null_separation = extended_binary64(
            claim["null_threshold_separation"], f"{configuration_id} null separation"
        )
        audit.require(
            (math.isinf(observed_null_separation) and math.isinf(null_separation))
            or (
                math.isfinite(observed_null_separation)
                and math.isfinite(null_separation)
                and abs(observed_null_separation - null_separation)
                <= 128.0 * epsilon * max(1.0, abs(null_separation))
            ),
            f"{configuration_id}: null separation",
        )
        source_mu_for_retention = binary64(
            observability[configuration["source_configuration_id"]]["mu"],
            f"{configuration_id}: source margin",
        )
        current_mu_for_retention = binary64(
            claim["mu"], f"{configuration_id}: current margin"
        )
        undefined_mu_retention = (
            source_mu_for_retention == 0.0 and current_mu_for_retention > 0.0
        )
        clear = (
            not ambiguous_indices
            and claim["operator_status"] == "analyzed"
            and claim["qr_status"] == "analyzed"
            and rank_agreement
            and (independent_rank_value == 0 or nonzero_separation > 1.0)
            and null_separation > 1.0
            and not undefined_mu_retention
        )
        audit.require(
            bool_text(claim["clear_separation_pass"], f"{configuration_id} clear separation") == clear,
            f"{configuration_id}: clear separation flag",
        )
        classification = (
            "implementation_failure"
            if claim["operator_status"] == "numerical_failure"
            or undefined_mu_retention
            else "ambiguous"
            if claim["operator_status"] == "ambiguous" or ambiguous_indices
            else "resolved_nonrigid"
            if expected_nonrigid > 0
            else "rigid_only"
        )
        enum_text(claim["classification"], OBSERVABILITY_CLASSIFICATIONS, f"{configuration_id} classification")
        audit.require(claim["classification"] == classification, f"{configuration_id}: classification")

        # Independent all-configuration direct spectrum path.  Rank comes
        # solely from exact/certified rigidity arithmetic.
        matrix = unit_rigidity_matrix(positions[configuration_id], edges[configuration_id])
        independent_svd = resolved_binary64_spectrum(
            matrix, independent_rank_value, column_count
        )
        independent[configuration_id] = independent_svd
        spectrum_tolerance = tolerances["similarity_factor"] * dimension * epsilon
        independent_values = tuple(
            float(value) for value in independent_svd.singular_values
        )
        independent_sigma_max = independent_values[0] if independent_values else 0.0
        independent_threshold = (
            tolerances["rank_factor"]
            * dimension
            * epsilon
            * max(independent_sigma_max, sys.float_info.min)
        )
        independent_lower = independent_threshold / ambiguity
        independent_upper = independent_threshold * ambiguity
        independent_accepted = sum(
            value > independent_upper for value in independent_values
        )
        independent_ambiguous = any(
            independent_lower <= value <= independent_upper
            for value in independent_values
        )
        audit.require(
            independent_accepted == independent_rank_value,
            f"{configuration_id}: independent direct-SVD rank",
        )
        audit.require(
            not independent_ambiguous,
            f"{configuration_id}: independent direct-SVD ambiguity",
        )
        producer_resolved = tuple(Decimal.from_float(value) for value in values[:independent_rank_value])
        audit.require(
            spectrum_delta(producer_resolved, independent_svd.singular_values[:independent_rank_value])
            <= Decimal.from_float(spectrum_tolerance),
            f"{configuration_id}: independent resolved spectrum",
        )
        independent_mu = float(independent_svd.margin)
        close_float(expected_mu, independent_mu, spectrum_tolerance, f"{configuration_id}: independent mu")
    return observability, spectra, independent


def decimal_l2(values: Iterable[Decimal]) -> Decimal:
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        squared = dsum(value * value for value in values)
        return squared.sqrt() if squared > 0 else Decimal(0)


def decimal_dot(
    first: Sequence[Decimal], second: Sequence[Decimal]
) -> Decimal:
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        return dsum(
            left * right for left, right in zip(first, second, strict=True)
        )


def decimal_rigid_basis(positions: Mapping[int, Vec3D]) -> tuple[tuple[Decimal, ...], ...]:
    packet_ids = sorted(positions)
    zero, one = Decimal(0), Decimal(1)
    axes = ((one, zero, zero), (zero, one, zero), (zero, zero, one))
    candidates: list[list[Decimal]] = [
        [axis[component] for _packet_id in packet_ids for component in range(3)]
        for axis in axes
    ]
    for omega in axes:
        candidate: list[Decimal] = []
        for packet_id in packet_ids:
            point = positions[packet_id]
            candidate.extend(
                (
                    omega[1] * point[2] - omega[2] * point[1],
                    omega[2] * point[0] - omega[0] * point[2],
                    omega[0] * point[1] - omega[1] * point[0],
                )
            )
        candidates.append(candidate)
    basis: list[tuple[Decimal, ...]] = []
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        for candidate in candidates:
            work = list(candidate)
            for vector in basis:
                coefficient = decimal_dot(work, vector)
                work = [
                    left - coefficient * right
                    for left, right in zip(work, vector, strict=True)
                ]
            norm = decimal_l2(work)
            if norm > Decimal("1e-70"):
                basis.append(tuple(value / norm for value in work))
    return tuple(basis)


def validate_nullspace(
    rows: Sequence[dict[str, str]],
    vector_rows: Sequence[dict[str, str]],
    configurations: Mapping[str, Mapping[str, str]],
    observability: Mapping[str, Mapping[str, str]],
    positions: Mapping[str, Mapping[int, Vec3D]],
    edges: Mapping[str, Sequence[tuple[int, int]]],
    tolerances: Mapping[str, float],
    audit: Audit,
) -> None:
    grouped = grouped_rows(rows, "configuration_id")
    vectors_grouped = grouped_rows(vector_rows, "configuration_id")
    audit.require(set(grouped) == set(configurations), "nullspace inventory")
    expected_vector_configs = {
        configuration_id
        for configuration_id in configurations
        if int(observability[configuration_id]["nullity"]) > 0
    }
    audit.require(
        set(vectors_grouped) == expected_vector_configs,
        "nullspace vector inventory",
    )
    for configuration_id in sorted(configurations):
        modes = grouped[configuration_id]
        expected_count = int(observability[configuration_id]["nullity"])
        column_count = int(observability[configuration_id]["column_count"])
        audit.require(len(modes) == expected_count, f"{configuration_id}: nullspace mode count")
        dimension = max(
            6,
            int(observability[configuration_id]["row_count"]),
            column_count,
        )
        expected_tolerance = tolerances["residual_factor"] * dimension * tolerances["epsilon"]
        vector_rows_by_mode = grouped_rows(
            vectors_grouped.get(configuration_id, []), "mode_index"
        )
        audit.require(
            set(vector_rows_by_mode) == {str(index) for index in range(expected_count)},
            f"{configuration_id}: nullspace vector mode inventory",
        )
        packet_ids = sorted(positions[configuration_id])
        expected_components = [
            (packet_id, axis)
            for packet_id in packet_ids
            for axis in ("x", "y", "z")
        ]
        matrix = unit_rigidity_matrix(
            positions[configuration_id], edges[configuration_id]
        )
        matrix_norm = decimal_l2(entry for row in matrix for entry in row)
        rigid_basis = decimal_rigid_basis(positions[configuration_id])
        audit.require(
            len(rigid_basis) == int(observability[configuration_id]["rigid_rank"]),
            f"{configuration_id}: independent rigid basis rank",
        )
        maximum_residual = 0.0
        hashes: set[str] = set()
        reconstructed_vectors: list[tuple[Decimal, ...]] = []
        for expected_index, row in enumerate(modes):
            audit.require(
                unsigned(row["mode_index"], f"{configuration_id} mode index") == expected_index,
                f"{configuration_id}: nullspace indices",
            )
            components = vector_rows_by_mode[str(expected_index)]
            audit.require(
                len(components) == column_count,
                f"{configuration_id}/{expected_index}: vector width",
            )
            values: list[float] = []
            for expected_component, component_row in enumerate(components):
                audit.require(
                    unsigned(
                        component_row["component_index"],
                        f"{configuration_id}/{expected_index} component index",
                    )
                    == expected_component,
                    f"{configuration_id}/{expected_index}: component order",
                )
                packet_id, axis = expected_components[expected_component]
                audit.require(
                    unsigned(
                        component_row["packet_id"],
                        f"{configuration_id}/{expected_index} component packet",
                        minimum=1,
                    )
                    == packet_id
                    and component_row["axis"] == axis,
                    f"{configuration_id}/{expected_index}: component semantic binding",
                )
                values.append(
                    signed_zero_binary64(
                        component_row["value"],
                        f"{configuration_id}/{expected_index}/{expected_component} value",
                    )
                )
            vector = tuple(Decimal.from_float(value) for value in values)
            reconstructed_vectors.append(vector)
            vector_norm = decimal_l2(vector)
            audit.require(
                abs(float(vector_norm) - 1.0) <= expected_tolerance,
                f"{configuration_id}/{expected_index}: null-vector unit norm",
            )
            product = [decimal_dot(matrix_row, vector) for matrix_row in matrix]
            denominator = matrix_norm * vector_norm
            computed_residual = (
                decimal_l2(product) / denominator
                if denominator > 0
                else Decimal(0)
            )
            coefficients = [decimal_dot(vector, basis) for basis in rigid_basis]
            computed_projection = (
                decimal_l2(coefficients) / vector_norm
                if vector_norm > 0
                else Decimal(0)
            )
            projection_squared = min(
                Decimal(1), max(Decimal(0), computed_projection * computed_projection)
            )
            computed_nonrigid = (Decimal(1) - projection_squared).sqrt()
            residual = binary64(row["mode_operator_residual"], f"{configuration_id} mode residual")
            projection = binary64(row["rigid_projection_norm"], f"{configuration_id} rigid projection")
            nonrigid = binary64(row["nonrigid_component_norm"], f"{configuration_id} nonrigid component")
            claimed_tolerance = binary64(row["residual_tolerance"], f"{configuration_id} mode tolerance")
            close_float(claimed_tolerance, expected_tolerance, 8.0 * tolerances["epsilon"], f"{configuration_id}: mode tolerance", scale_floor=sys.float_info.min)
            audit.require(
                abs(residual - float(computed_residual)) <= expected_tolerance,
                f"{configuration_id}/{expected_index}: independently reconstructed operator residual",
            )
            audit.require(
                abs(projection - float(computed_projection)) <= expected_tolerance,
                f"{configuration_id}/{expected_index}: independently reconstructed rigid projection",
            )
            audit.require(
                abs(nonrigid * nonrigid - float(computed_nonrigid * computed_nonrigid))
                <= 2.0 * expected_tolerance,
                f"{configuration_id}/{expected_index}: independently reconstructed nonrigid component",
            )
            expected_accept = float(computed_residual) <= expected_tolerance
            audit.require(
                bool_text(row["accepted"], f"{configuration_id} mode accepted") == expected_accept,
                f"{configuration_id}: mode acceptance",
            )
            claimed_digest = sha256_text(
                row["vector_sha256"], f"{configuration_id} mode vector hash"
            )
            computed_digest = hashlib.sha256(
                b"".join(struct.pack("<d", value) for value in values)
            ).hexdigest()
            audit.require(
                claimed_digest == computed_digest,
                f"{configuration_id}/{expected_index}: vector hash binding",
            )
            audit.require(claimed_digest not in hashes, f"{configuration_id}: duplicate null-vector hash")
            hashes.add(claimed_digest)
            maximum_residual = max(maximum_residual, residual)
        for first in range(len(reconstructed_vectors)):
            for second in range(first + 1, len(reconstructed_vectors)):
                dot = decimal_dot(
                    reconstructed_vectors[first], reconstructed_vectors[second]
                )
                audit.require(
                    abs(float(dot)) <= expected_tolerance,
                    f"{configuration_id}: nullspace basis orthogonality",
                )
        observed_maximum = binary64(
            observability[configuration_id]["nullspace_residual_normalized"],
            f"{configuration_id} aggregate null residual",
        )
        close_float(
            observed_maximum,
            maximum_residual,
            64.0 * tolerances["epsilon"],
            f"{configuration_id}: aggregate null residual",
            scale_floor=sys.float_info.min,
        )


def expected_id_mapping(
    kind: str, configuration_id: str, packet_ids: Sequence[int]
) -> dict[int, int]:
    canonical = sorted(packet_ids)
    if kind == "id_reverse":
        target = list(reversed(canonical))
    elif kind == "id_cycle":
        target = canonical[1:] + canonical[:1]
    elif kind == "id_sha256":
        target = sorted(
            canonical,
            key=lambda packet_id: (
                hashlib.sha256(
                    f"{SEED}|relational_observability_id_v1|{configuration_id}|{packet_id}"
                    .encode("ascii")
                ).digest(),
                packet_id,
            ),
        )
    else:
        reject(f"unsupported ID mapping kind {kind}")
    return dict(zip(canonical, target, strict=True))


def validate_id_bijections_and_metamorphic(
    bijection_rows: Sequence[dict[str, str]],
    metamorphic_rows: Sequence[dict[str, str]],
    configurations: Mapping[str, Mapping[str, str]],
    packet_rows: Mapping[str, Sequence[Mapping[str, str]]],
    positions: Mapping[str, Mapping[int, Vec3D]],
    edges: Mapping[str, Sequence[tuple[int, int]]],
    ranks: Mapping[str, IndependentRank],
    spectra: Mapping[str, Sequence[Mapping[str, str]]],
    tolerances: Mapping[str, float],
    audit: Audit,
) -> dict[str, dict[str, str]]:
    controls = unique_rows(metamorphic_rows, "control_id", "metamorphic")
    bijections = grouped_rows(bijection_rows, "control_id")
    audit.require(set(bijections) <= set(controls), "ID-bijection/control inventory")
    row_by_packet = {
        configuration_id: {int(row["packet_id"]): row for row in rows}
        for configuration_id, rows in packet_rows.items()
    }
    for control_id in sorted(controls):
        row = controls[control_id]
        base_id = identifier(row["base_configuration_id"], f"{control_id} base")
        variant_id = identifier(row["variant_configuration_id"], f"{control_id} variant")
        audit.require(base_id in configurations and variant_id in configurations, f"{control_id}: configuration binding")
        kind = enum_text(row["control_kind"], CONTROL_KINDS, f"{control_id} kind")
        tolerance = binary64(row["tolerance"], f"{control_id} tolerance")
        dimension = max(
            6,
            len(edges[base_id]),
            3 * len(positions[base_id]),
            len(edges[variant_id]),
            3 * len(positions[variant_id]),
        )
        expected_tolerance = tolerances["similarity_factor"] * dimension * tolerances["epsilon"]
        close_float(tolerance, expected_tolerance, 8.0 * tolerances["epsilon"], f"{control_id}: tolerance", scale_floor=sys.float_info.min)
        same_rank = ranks[base_id].rank == ranks[variant_id].rank
        same_nullity = ranks[base_id].nullity == ranks[variant_id].nullity
        base_nonrigid = ranks[base_id].nullity - ranks[base_id].rigid_rank
        variant_nonrigid = ranks[variant_id].nullity - ranks[variant_id].rigid_rank
        same_nonrigid = base_nonrigid == variant_nonrigid
        audit.require(bool_text(row["rank_equal"], f"{control_id} rank equal") == same_rank, f"{control_id}: rank equality")
        audit.require(bool_text(row["nullity_equal"], f"{control_id} nullity equal") == same_nullity, f"{control_id}: nullity equality")
        audit.require(bool_text(row["nonrigid_nullity_equal"], f"{control_id} nonrigid equal") == same_nonrigid, f"{control_id}: nonrigid equality")
        base_values = [decimal64(item["singular_value"], f"{control_id} base spectrum") for item in spectra[base_id]]
        variant_values = [decimal64(item["singular_value"], f"{control_id} variant spectrum") for item in spectra[variant_id]]
        computed_spectrum_residual = spectrum_delta(base_values, variant_values)
        observed_spectrum_residual = decimal64(row["spectrum_residual"], f"{control_id} spectrum residual")
        audit.require(
            abs(observed_spectrum_residual - computed_spectrum_residual)
            <= Decimal.from_float(expected_tolerance),
            f"{control_id}: spectrum residual",
        )
        base_mu = float(base_values[ranks[base_id].rank - 1] / base_values[0]) if ranks[base_id].rank and base_values[0] else 0.0
        variant_mu = float(variant_values[ranks[variant_id].rank - 1] / variant_values[0]) if ranks[variant_id].rank and variant_values[0] else 0.0
        mu_error = abs(variant_mu - base_mu) / max(abs(base_mu), sys.float_info.min)
        observed_mu_error = binary64(row["mu_relative_error"], f"{control_id} mu error")
        close_float(observed_mu_error, mu_error, expected_tolerance, f"{control_id}: mu error", scale_floor=sys.float_info.min)
        observed_covariance = binary64(
            row["operator_covariance_residual"],
            f"{control_id} covariance residual",
        )

        physical_graph_equal = False
        semantic_mapping: dict[int, int] | None = None
        if kind in ID_BIJECTION_KINDS:
            mapping_rows = bijections.get(control_id, [])
            source_ids = sorted(positions[base_id])
            audit.require(len(mapping_rows) == len(source_ids), f"{control_id}: complete ID mapping")
            mapping: dict[int, int] = {}
            for mapping_row in mapping_rows:
                audit.require(mapping_row["source_configuration_id"] == base_id, f"{control_id}: mapping source")
                audit.require(mapping_row["bijection_kind"] == kind, f"{control_id}: mapping kind")
                old = unsigned(mapping_row["old_packet_id"], f"{control_id} old ID", minimum=1)
                new = unsigned(mapping_row["new_packet_id"], f"{control_id} new ID", minimum=1)
                inverse = unsigned(mapping_row["inverse_packet_id"], f"{control_id} inverse ID", minimum=1)
                audit.require(old not in mapping, f"{control_id}: duplicate old ID")
                audit.require(inverse == old, f"{control_id}: inverse mapping witness")
                audit.require(bool_text(mapping_row["nontrivial"], f"{control_id} nontrivial"), f"{control_id}: mapping marked trivial")
                mapping[old] = new
            audit.require(set(mapping) == set(source_ids), f"{control_id}: source ID inventory")
            audit.require(set(mapping.values()) == set(source_ids), f"{control_id}: target ID inventory")
            audit.require(mapping == expected_id_mapping(kind, base_id, source_ids), f"{control_id}: deterministic ID bijection")
            audit.require(configurations[variant_id]["source_configuration_id"] == base_id, f"{control_id}: variant source")
            for old, new in mapping.items():
                base_packet = row_by_packet[base_id][old]
                variant_packet = row_by_packet[variant_id][new]
                for field in (
                    "mass_quanta",
                    "x_m",
                    "y_m",
                    "z_m",
                    "vx_m_per_s",
                    "vy_m_per_s",
                    "vz_m_per_s",
                ):
                    audit.require(base_packet[field] == variant_packet[field], f"{control_id}: packet-state relabel {field}")
            mapped_edges = sorted(
                tuple(sorted((mapping[first], mapping[second])))
                for first, second in edges[base_id]
            )
            physical_graph_equal = mapped_edges == list(edges[variant_id])
            semantic_mapping = mapping
        else:
            audit.require(control_id not in bijections, f"{control_id}: unexpected ID map")
            physical_graph_equal = list(edges[base_id]) == list(edges[variant_id])
        audit.require(
            bool_text(row["physical_graph_equal"], f"{control_id} physical graph") == physical_graph_equal,
            f"{control_id}: physical graph equality",
        )

        # Reconstruct both raw unit-direction operators solely from exported
        # coordinates and relation endpoints.  The producer's residual and
        # singular spectra are not premises for this covariance check.
        base_packet_ids = sorted(positions[base_id])
        variant_packet_ids = sorted(positions[variant_id])
        base_operator = unit_rigidity_matrix(
            positions[base_id], edges[base_id]
        )
        variant_operator = unit_rigidity_matrix(
            positions[variant_id], edges[variant_id]
        )
        if semantic_mapping is not None:
            covariance_actual = semantically_align_id_operator(
                base_packet_ids,
                edges[base_id],
                variant_packet_ids,
                edges[variant_id],
                variant_operator,
                semantic_mapping,
            )
            covariance_expected = base_operator
        elif kind in {
            "inherited_proper_rotation",
            "inherited_rotation_translation",
            "inherited_scale_half",
            "inherited_scale_double",
        }:
            covariance_actual = variant_operator
            covariance_expected = inherited_rotated_operator(base_operator)
        elif kind in {
            "inherited_translation",
            "packet_permutation",
            "relation_permutation",
        }:
            covariance_actual = variant_operator
            covariance_expected = base_operator
        else:  # CONTROL_KINDS is closed, so reaching this is a verifier defect.
            reject(f"{control_id}: missing covariance reconstruction law")
        computed_covariance = normalized_operator_residual(
            covariance_actual, covariance_expected
        )
        covariance_agreement_tolerance = (
            tolerances["rank_factor"] * dimension * tolerances["epsilon"]
        )
        audit.require(
            abs(Decimal.from_float(observed_covariance) - computed_covariance)
            <= Decimal.from_float(covariance_agreement_tolerance),
            f"{control_id}: independently reconstructed operator covariance residual",
        )

        expected_length_scale = (
            binary64(
                configurations[variant_id]["geometry_scale"],
                f"{control_id}: variant geometry scale",
            )
            / binary64(
                configurations[base_id]["geometry_scale"],
                f"{control_id}: base geometry scale",
            )
            if kind.startswith("inherited_")
            else 1.0
        )
        observed_length_scale = binary64(
            row["finite_length_scale"], f"{control_id}: finite-length scale"
        )
        close_float(
            observed_length_scale,
            expected_length_scale,
            8.0 * tolerances["epsilon"],
            f"{control_id}: finite-length scale",
            scale_floor=sys.float_info.min,
        )
        variant_lengths: dict[tuple[int, int], float] = {}
        for first, second in edges[variant_id]:
            delta = tuple(
                float(positions[variant_id][second][axis] - positions[variant_id][first][axis])
                for axis in range(3)
            )
            variant_lengths[(first, second)] = math.hypot(*delta)
        finite_graph_equal = True
        finite_length_residual = 0.0
        expected_variant_edges: set[tuple[int, int]] = set()
        for first, second in edges[base_id]:
            mapped_first = semantic_mapping[first] if semantic_mapping is not None else first
            mapped_second = semantic_mapping[second] if semantic_mapping is not None else second
            edge = tuple(sorted((mapped_first, mapped_second)))
            expected_variant_edges.add(edge)
            if edge not in variant_lengths:
                finite_graph_equal = False
                continue
            base_delta = tuple(
                float(positions[base_id][second][axis] - positions[base_id][first][axis])
                for axis in range(3)
            )
            expected_length = expected_length_scale * math.hypot(*base_delta)
            actual_length = variant_lengths[edge]
            finite_length_residual = max(
                finite_length_residual,
                abs(actual_length - expected_length)
                / max(abs(actual_length), abs(expected_length), sys.float_info.min),
            )
        finite_graph_equal = finite_graph_equal and expected_variant_edges == set(variant_lengths)
        audit.require(
            finite_graph_equal == physical_graph_equal,
            f"{control_id}: independent finite graph equality",
        )
        observed_finite_residual = binary64(
            row["finite_length_residual"],
            f"{control_id}: finite-length residual",
        )
        audit.require(
            abs(observed_finite_residual - finite_length_residual)
            <= expected_tolerance,
            f"{control_id}: independently reconstructed finite-length residual",
        )
        expected_pass = (
            physical_graph_equal
            and same_rank
            and same_nullity
            and same_nonrigid
            and float(computed_covariance) <= tolerance
            and float(computed_spectrum_residual) <= tolerance
            and finite_length_residual <= tolerance
            and mu_error <= tolerance
        )
        audit.require(bool_text(row["pass"], f"{control_id} pass") == expected_pass, f"{control_id}: pass flag")
    return controls


def nested_deletion_order(edges: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    return sorted(
        edges,
        key=lambda edge: (
            hashlib.sha256(
                f"{SEED}|relational_observability_nested_delete_v1|{edge[0]}|{edge[1]}"
                .encode("ascii")
            ).digest(),
            edge[0],
            edge[1],
        ),
    )


def validate_topology_paths(
    rows: Sequence[dict[str, str]],
    configurations: Mapping[str, Mapping[str, str]],
    edges: Mapping[str, Sequence[tuple[int, int]]],
    ranks: Mapping[str, IndependentRank],
    observability: Mapping[str, Mapping[str, str]],
    *,
    full: bool,
    audit: Audit,
) -> set[str]:
    paths = grouped_rows(rows, "path_id")
    audit.require(bool(paths), "topology path inventory empty")
    high_precision_transition_ids: set[str] = set()
    for path_id, path_rows in sorted(paths.items()):
        identifier(path_id, "topology path ID")
        path_rows = sorted(
            path_rows,
            key=lambda row: unsigned(row["deletion_step"], f"{path_id} deletion step"),
        )
        steps = [int(row["deletion_step"]) for row in path_rows]
        audit.require(steps == list(range(len(path_rows))), f"{path_id}: contiguous deletion steps")
        first_configuration_id = path_rows[0]["configuration_id"]
        audit.require(first_configuration_id in configurations, f"{path_id}: first configuration")
        base_id = configurations[first_configuration_id]["source_configuration_id"]
        audit.require(base_id in configurations, f"{path_id}: base configuration")
        original_edges = list(edges[base_id])
        removal_order = nested_deletion_order(original_edges)
        if full:
            audit.require(path_id == "nested.sc3.r180.v1", "full topology path ID")
            audit.require(base_id == "base.sc3.r180.original", "full topology source")
            audit.require(len(path_rows) == len(original_edges) + 1, f"{path_id}: complete deletion path")
        exact_nonrigid: list[int] = []
        exact_rank_values: list[int] = []
        for row in path_rows:
            step = int(row["deletion_step"])
            configuration_id = identifier(row["configuration_id"], f"{path_id} configuration")
            audit.require(configuration_id in configurations, f"{path_id}: unknown configuration")
            config = configurations[configuration_id]
            audit.require(config["probe_family"] == "topology_deletion", f"{configuration_id}: topology probe family")
            audit.require(int(config["topology_path_step"]) == step, f"{configuration_id}: topology step binding")
            expected_edges = sorted(set(original_edges) - set(removal_order[:step]))
            audit.require(list(edges[configuration_id]) == expected_edges, f"{configuration_id}: nested deletion topology")
            expected_removed = None if step == 0 else removal_order[step - 1]
            observed_first = optional_unsigned(row["removed_first_id"], f"{configuration_id} removed first", minimum=1)
            observed_second = optional_unsigned(row["removed_second_id"], f"{configuration_id} removed second", minimum=1)
            audit.require(
                (observed_first, observed_second) == (
                    (None, None) if expected_removed is None else expected_removed
                ),
                f"{configuration_id}: removed-edge witness",
            )
            rank = ranks[configuration_id]
            nonrigid = rank.nullity - rank.rigid_rank
            exact_nonrigid.append(nonrigid)
            exact_rank_values.append(rank.rank)
            audit.require(unsigned(row["edge_count"], f"{configuration_id} path edge count") == len(expected_edges), f"{configuration_id}: path edge count")
            audit.require(unsigned(row["rank"], f"{configuration_id} path rank") == rank.rank, f"{configuration_id}: path rank")
            audit.require(unsigned(row["nullity"], f"{configuration_id} path nullity") == rank.nullity, f"{configuration_id}: path nullity")
            audit.require(unsigned(row["nonrigid_nullity"], f"{configuration_id} path nonrigid") == nonrigid, f"{configuration_id}: path nonrigid")
            # ``rank.upper_bound`` is independently derived from the physical
            # row count and rigid-motion kernel, not from producer rank fields.
            structural_upper = rank.upper_bound
            if full and step == 54:
                expected_rank_kind = "exact_fraction_rref"
                expected_certified = True
                audit.require(
                    rank.method == "Fraction_RREF_transition" and rank.rank == 74,
                    f"{configuration_id}: exact transition witness",
                )
            elif rank.rank == structural_upper:
                expected_rank_kind = "modular_lower_bound_matches_structural_upper_bound"
                expected_certified = True
            else:
                expected_rank_kind = "modular_lower_bound"
                expected_certified = False
            enum_text(
                row["rank_reference_kind"],
                RANK_REFERENCE_KINDS,
                f"{configuration_id} rank reference",
            )
            audit.require(
                row["rank_reference_kind"] == expected_rank_kind,
                f"{configuration_id}: independent rank-reference classification",
            )
            audit.require(
                bool_text(row["rank_certified"], f"{configuration_id} rank certified")
                == expected_certified,
                f"{configuration_id}: rank certification",
            )
            claim = observability[configuration_id]
            for field in ("sigma_min_nonzero", "sigma_max", "mu", "nonzero_threshold_separation"):
                audit.require(row[field] == claim[field], f"{configuration_id}: path {field} binding")
            audit.require(row["classification"] == claim["classification"], f"{configuration_id}: path classification")
            enum_text(row["transition"], TRANSITIONS, f"{configuration_id} transition")
        first_nonrigid = next(
            (step for step, count in enumerate(exact_nonrigid) if count > 0), None
        )
        last_rigid = first_nonrigid - 1 if first_nonrigid is not None else None
        transition_outer = {
            step
            for step in (
                None if last_rigid is None else last_rigid - 1,
                None if first_nonrigid is None else first_nonrigid + 1,
            )
            if step is not None and 0 <= step < len(path_rows)
        }
        for step, row in enumerate(path_rows):
            expected_transition = "none"
            if not full:
                expected_transition = "none"
            elif step == len(original_edges):
                expected_transition = "complete_deletion"
            elif first_nonrigid is not None and step == first_nonrigid:
                expected_transition = "first_nonrigid"
            elif last_rigid is not None and step == last_rigid:
                expected_transition = "last_rigid"
            elif step in transition_outer:
                expected_transition = "transition_adjacent"
            audit.require(row["transition"] == expected_transition, f"{path_id}: transition label step {step}")
        if full:
            audit.require(first_nonrigid == 54, "exact first rigidity-loss step")
            audit.require(last_rigid == 53, "exact last-rigid step")
            audit.require(transition_outer == {52, 55}, "exact transition outer steps")
        preregistered_steps = {0, 25, 50, 52, 53, 54, 55, 75, 100, 125, 150, 158}
        transition_review = set(transition_outer)
        if first_nonrigid is not None:
            transition_review.add(first_nonrigid)
        if last_rigid is not None:
            transition_review.add(last_rigid)
        for step in preregistered_steps | transition_review:
            if step < len(path_rows):
                high_precision_transition_ids.add(path_rows[step]["configuration_id"])
    return high_precision_transition_ids


def validate_lookup(
    rows: Sequence[dict[str, str]],
    configurations: Mapping[str, Mapping[str, str]],
    relation_rows: Mapping[str, Sequence[Mapping[str, str]]],
    positions: Mapping[str, Mapping[int, Vec3Q]],
    audit: Audit,
) -> None:
    seen: set[tuple[str, str]] = set()
    grouped = grouped_rows(rows, "configuration_id")
    lookup_required = {
        configuration_id
        for configuration_id, config in configurations.items()
        if config["probe_family"] == "inherited"
        and all(
            row["selection_source"] == "physical_radius"
            for row in relation_rows[configuration_id]
        )
    }
    audit.require(set(grouped) == lookup_required, "lookup configuration inventory")
    for configuration_id, phase_rows in grouped.items():
        audit.require(configuration_id in configurations, f"lookup unknown configuration {configuration_id}")
        audit.require(configurations[configuration_id]["probe_family"] == "inherited", f"{configuration_id}: derived/self-ID pseudo-lookup")
        support = fraction64(
            configurations[configuration_id]["support_radius_m"],
            f"{configuration_id} lookup support",
        )
        support_squared = support * support
        packet_ids = sorted(positions[configuration_id])
        radius_edges = [
            (first, second)
            for first_index, first in enumerate(packet_ids)
            for second in packet_ids[first_index + 1 :]
            if qsum(
                (positions[configuration_id][second][axis] - positions[configuration_id][first][axis]) ** 2
                for axis in range(3)
            )
            < support_squared
        ]
        explicit_edges = [
            (int(row["first_id"]), int(row["second_id"]))
            for row in relation_rows[configuration_id]
        ]
        audit.require(radius_edges == explicit_edges, f"{configuration_id}: exact all-pairs radius graph")
        audit.require(len(phase_rows) == len(LOOKUP_PHASES), f"{configuration_id}: lookup phase count")
        for row in phase_rows:
            phase = enum_text(row["phase_id"], LOOKUP_PHASES, f"{configuration_id} lookup phase")
            audit.require((configuration_id, phase) not in seen, f"{configuration_id}: duplicate lookup phase")
            seen.add((configuration_id, phase))
            brute = unsigned(row["brute_force_edge_count"], f"{configuration_id} brute edge count")
            lookup = unsigned(row["lookup_edge_count"], f"{configuration_id} lookup edge count")
            expected = len(radius_edges)
            audit.require(brute == lookup == expected, f"{configuration_id}: lookup edge count")
            audit.require(bool_text(row["canonical_equal"], f"{configuration_id} canonical lookup"), f"{configuration_id}: lookup topology disagreement")
            audit.require(bool_text(row["pass"], f"{configuration_id} lookup pass"), f"{configuration_id}: lookup failed")


def validate_checkpoint_table(
    root: pathlib.Path,
    rows: Sequence[dict[str, str]],
    configurations: Mapping[str, Mapping[str, str]],
    packet_rows: Mapping[str, Sequence[Mapping[str, str]]],
    edges: Mapping[str, Sequence[tuple[int, int]]],
    audit: Audit,
) -> None:
    checkpoints = unique_rows(rows, "configuration_id", "checkpoints")
    audit.require(set(checkpoints) == set(configurations), "checkpoint inventory")
    for configuration_id in sorted(configurations):
        row = checkpoints[configuration_id]
        audit.require(row["encoding"] == CHECKPOINT_ENCODING, f"{configuration_id}: checkpoint encoding")
        payload, digest = parse_checkpoint(
            root / "checkpoints" / f"{configuration_id}.bin",
            configurations[configuration_id],
            packet_rows[configuration_id],
            edges[configuration_id],
            audit,
        )
        audit.require(unsigned(row["byte_count"], f"{configuration_id} checkpoint bytes") == len(payload), f"{configuration_id}: checkpoint byte count")
        before = sha256_text(row["payload_sha256_before"], f"{configuration_id} before digest")
        roundtrip = sha256_text(row["payload_sha256_roundtrip"], f"{configuration_id} roundtrip digest")
        after = sha256_text(row["payload_sha256_after"], f"{configuration_id} after digest")
        audit.require(before == roundtrip == after == digest, f"{configuration_id}: checkpoint exact hashes")
        audit.require(configurations[configuration_id]["input_checkpoint_sha256_before"] == before, f"{configuration_id}: config before checkpoint binding")
        audit.require(configurations[configuration_id]["input_checkpoint_sha256_after"] == after, f"{configuration_id}: config after checkpoint binding")
        for field in ("roundtrip_exact", "diagnostics_read_only_exact", "pass"):
            audit.require(bool_text(row[field], f"{configuration_id} {field}"), f"{configuration_id}: checkpoint {field} failed")
        audit.require(bool_text(configurations[configuration_id]["diagnostics_read_only_exact"], f"{configuration_id} config read-only"), f"{configuration_id}: diagnostics changed state")


def select_high_precision_configurations(
    configurations: Mapping[str, Mapping[str, str]],
    controls: Mapping[str, Mapping[str, str]],
    transition_ids: set[str],
    *,
    full: bool,
) -> set[str]:
    selected = {
        configuration_id
        for configuration_id, row in configurations.items()
        if bool_text(row["exact_control"], f"{configuration_id} exact control")
    }
    if not full:
        return selected
    perturbations: dict[str, list[str]] = defaultdict(list)
    affine: dict[str, list[str]] = defaultdict(list)
    maximum_amplitude = (1.0 / 100.0).hex()
    for configuration_id, row in configurations.items():
        if (
            row["probe_family"] == "geometry_perturbation"
            and row["perturbation_amplitude_ratio"] == maximum_amplitude
        ):
            perturbations[row["family"]].append(configuration_id)
        if (
            row["probe_family"] == "homogeneous_deformation"
            and "general" in row["probe_id"]
        ):
            affine[row["family"]].append(configuration_id)
    selected.update(min(values) for values in perturbations.values())
    selected.update(min(values) for values in affine.values())
    for row in controls.values():
        if row["control_kind"] in ID_BIJECTION_KINDS:
            source = row["base_configuration_id"]
            if source == "base.sc3.r180.original":
                selected.add(row["variant_configuration_id"])
    selected.update(transition_ids)
    return selected


def validate_high_precision_subset(
    selected: set[str],
    positions: Mapping[str, Mapping[int, Vec3D]],
    edges: Mapping[str, Sequence[tuple[int, int]]],
    ranks: Mapping[str, IndependentRank],
    spectra: Mapping[str, Sequence[Mapping[str, str]]],
    tolerances: Mapping[str, float],
    audit: Audit,
) -> dict[str, dict[str, Any]]:
    report: dict[str, dict[str, Any]] = {}
    for configuration_id in sorted(selected):
        audit.require(configuration_id in positions, f"high-precision unknown configuration {configuration_id}")
        matrix = unit_rigidity_matrix(positions[configuration_id], edges[configuration_id])
        if matrix:
            values, sweeps, converged = high_precision_singular_values(matrix)
        else:
            values = tuple(
                Decimal(0) for _ in range(3 * len(positions[configuration_id]))
            )
            sweeps, converged = 0, True
        audit.require(converged, f"{configuration_id}: 90-digit direct SVD convergence")
        rank = ranks[configuration_id].rank
        audit.require(rank <= len(values), f"{configuration_id}: HP rank dimension")
        sigma_max = values[0] if values else Decimal(0)
        dimension = max(
            6,
            len(edges[configuration_id]),
            3 * len(positions[configuration_id]),
        )
        threshold = (
            Decimal(512)
            * Decimal(dimension)
            * EPSILON64
            * max(sigma_max, MIN_NORMAL64)
        )
        lower = threshold / Decimal(8)
        upper = threshold * Decimal(8)
        if rank:
            audit.require(values[rank - 1] > upper, f"{configuration_id}: HP nonzero separation")
        if rank < len(values):
            audit.require(values[rank] < lower, f"{configuration_id}: HP null separation")
        producer_values = tuple(
            decimal64(row["singular_value"], f"{configuration_id} producer spectrum")
            for row in spectra[configuration_id]
        )
        tolerance = Decimal.from_float(
            tolerances["similarity_factor"] * dimension * tolerances["epsilon"]
        )
        audit.require(
            spectrum_delta(values, producer_values) <= tolerance,
            f"{configuration_id}: 90-digit spectrum agreement",
        )
        producer_mu = (
            producer_values[rank - 1] / producer_values[0]
            if rank and producer_values[0]
            else Decimal(0)
        )
        independent_mu = values[rank - 1] / values[0] if rank and values[0] else Decimal(0)
        audit.require(
            abs(producer_mu - independent_mu) <= tolerance,
            f"{configuration_id}: 90-digit margin agreement",
        )
        report[configuration_id] = {
            "rank": rank,
            "nullity": ranks[configuration_id].nullity,
            "mu": str(independent_mu),
            "sweeps": sweeps,
        }
    return report


def validate_robustness_and_decision(
    summary: Mapping[str, Any],
    configurations: Mapping[str, Mapping[str, str]],
    observability: Mapping[str, Mapping[str, str]],
    controls: Mapping[str, Mapping[str, str]],
    tolerances: Mapping[str, float],
    audit: Audit,
) -> str:
    implementation_failure = any(
        row["classification"] in {"implementation_failure", "ambiguous"}
        for row in observability.values()
    ) or any(not bool_text(row["pass"], f"{control_id} control pass") for control_id, row in controls.items())
    rejected = False
    numerically_unsafe = False
    pass_count = fail_count = ambiguous_count = 0
    for configuration_id in sorted(configurations):
        configuration = configurations[configuration_id]
        row = observability[configuration_id]
        source_id = configuration["source_configuration_id"]
        baseline_mu = binary64(
            observability[source_id]["mu"], f"{configuration_id} source mu"
        )
        current_mu = binary64(row["mu"], f"{configuration_id} mu")
        undefined_retention = baseline_mu == 0.0 and current_mu > 0.0
        expected_retention = (
            current_mu / baseline_mu
            if baseline_mu > 0.0
            else 1.0
            if current_mu == 0.0
            else 0.0
        )
        observed_baseline = binary64(row["baseline_mu"], f"{configuration_id} baseline mu")
        observed_retention = extended_binary64(
            row["mu_retention_ratio"], f"{configuration_id} mu retention"
        )
        dimension = max(6, int(row["row_count"]), int(row["column_count"]))
        tolerance = tolerances["similarity_factor"] * dimension * tolerances["epsilon"]
        close_float(observed_baseline, baseline_mu, tolerance, f"{configuration_id}: baseline mu")
        audit.require(
            math.isfinite(observed_retention),
            f"{configuration_id}: finite mu retention",
        )
        close_float(observed_retention, expected_retention, tolerance, f"{configuration_id}: mu retention", scale_floor=sys.float_info.min)
        if undefined_retention:
            implementation_failure = True
        eligible = configuration["decision_scope"] == "eligible_generic"
        clear = bool_text(row["clear_separation_pass"], f"{configuration_id} clear")
        expected_robustness = (
            eligible
            and row["classification"] == "rigid_only"
            and clear
            and observed_retention >= tolerances["mu_retention_min"]
        )
        if eligible:
            audit.require(
                bool_text(row["robustness_pass"], f"{configuration_id} robustness") == expected_robustness,
                f"{configuration_id}: robustness flag",
            )
            if row["classification"] == "resolved_nonrigid":
                rejected = True
            if (
                configuration["probe_family"]
                in {"geometry_perturbation", "homogeneous_deformation"}
                and not expected_robustness
            ):
                numerically_unsafe = True
        else:
            audit.require(
                not bool_text(row["robustness_pass"], f"{configuration_id} robustness"),
                f"{configuration_id}: noneligible robustness claim",
            )
        scope = configuration["decision_scope"]
        expected_decision_gate = (
            expected_robustness
            if scope == "eligible_generic"
            else (
                row["operator_status"] == "analyzed"
                and clear
                and row["classification"] == "resolved_nonrigid"
            )
            if scope == "intentionally_flexible"
            else row["operator_status"] == "analyzed" and clear
        )
        audit.require(
            bool_text(row["decision_gate_pass"], f"{configuration_id} decision gate")
            == expected_decision_gate,
            f"{configuration_id}: decision-gate flag",
        )
        if scope != "eligible_generic" and not expected_decision_gate:
            implementation_failure = True
        gate_pass = bool_text(row["decision_gate_pass"], f"{configuration_id} gate")
        if row["classification"] in {"ambiguous", "implementation_failure"}:
            ambiguous_count += 1
        elif gate_pass:
            pass_count += 1
        else:
            fail_count += 1
    gate_counts = summary["gate_counts"]
    for key, expected in {
        "pass": pass_count,
        "fail": fail_count,
        "ambiguous": ambiguous_count,
    }.items():
        if key in gate_counts:
            audit.require(gate_counts[key] == expected, f"summary gate count {key}")
    verdict = (
        VERDICTS[0]
        if summary["mode"] == "smoke" or implementation_failure
        else VERDICTS[1]
        if rejected
        else VERDICTS[2]
        if numerically_unsafe
        else VERDICTS[3]
    )
    audit.require(summary["verdict"] == verdict, "preregistered verdict recomputation")
    return verdict


def validate_bundle(root: pathlib.Path, allow_dirty: bool) -> tuple[int, dict[str, Any]]:
    audit = Audit()
    audit.require(root.is_dir(), "bundle directory missing")
    summary = read_json(root / SUMMARY_FILE)
    tolerance_payload = read_json(root / TOLERANCE_FILE)
    validate_summary_metadata(summary, allow_dirty=allow_dirty, audit=audit)
    tolerances = validate_tolerances(tolerance_payload, audit)
    tables = {
        name: read_csv(root / name, fields) for name, fields in CSV_SCHEMAS.items()
    }
    configurations = validate_configurations(tables["configurations.csv"], audit)
    expected_full_controls = (
        validate_full_configuration_inventory(configurations, audit)
        if summary["mode"] == "full"
        else None
    )
    manifest_hashes = verify_manifest(root, sorted(configurations))
    manifest = read_json(root / MANIFEST_FILE)
    audit.require(manifest["mode"] == summary["mode"], "manifest/summary mode")
    audit.require(manifest["source_sha"] == summary["source_sha"], "manifest/summary source SHA")
    audit.require(manifest["branch"] == summary["branch"], "manifest/summary branch")
    audit.require(manifest["dirty"] == summary["dirty"], "manifest/summary dirty")
    actual_counts = {name: len(rows) for name, rows in tables.items()}
    audit.require(manifest["actual_rows"] == actual_counts, "manifest actual row counts")
    audit.require(manifest["expected_rows"] == actual_counts, "manifest expected row counts")
    summary_preimage = b"".join(
        f"{name}={manifest_hashes[name]}\n".encode("utf-8")
        for name in sorted(set(manifest_hashes) - {SUMMARY_FILE})
    ) + f"verdict={summary['verdict']}\n".encode("utf-8")
    audit.require(
        summary["pre_hash_sha256"] == hashlib.sha256(summary_preimage).hexdigest(),
        "summary pre-hash",
    )

    packet_rows, positions_q, positions_d = validate_packets(
        tables["packets.csv"], configurations, audit
    )
    relation_rows, edges = validate_relations(
        tables["relations.csv"], configurations, positions_q, tolerances, audit
    )
    validate_derived_geometry_and_state(
        configurations,
        packet_rows,
        relation_rows,
        edges,
        full=summary["mode"] == "full",
        audit=audit,
    )
    validate_relational_derivation_metadata(configurations, packet_rows, audit)
    exact_ranks, _topology_facts = validate_exact_topology_and_ranks(
        configurations,
        positions_q,
        edges,
        full=summary["mode"] == "full",
        audit=audit,
    )
    observability, spectra, _independent_spectra = validate_spectra_and_observability(
        tables["spectra.csv"],
        tables["observability.csv"],
        relation_rows,
        configurations,
        positions_d,
        edges,
        exact_ranks,
        tolerances,
        audit,
    )
    validate_nullspace(
        tables["nullspace.csv"],
        tables["nullspace_vectors.csv"],
        configurations,
        observability,
        positions_d,
        edges,
        tolerances,
        audit,
    )
    controls = validate_id_bijections_and_metamorphic(
        tables["id_bijections.csv"],
        tables["metamorphic.csv"],
        configurations,
        packet_rows,
        positions_d,
        edges,
        exact_ranks,
        spectra,
        tolerances,
        audit,
    )
    if expected_full_controls is not None:
        audit.require(set(controls) == set(expected_full_controls), "full metamorphic control inventory")
        for control_id, expected in expected_full_controls.items():
            row = controls[control_id]
            audit.require(
                (
                    row["base_configuration_id"],
                    row["variant_configuration_id"],
                    row["control_kind"],
                )
                == expected,
                f"{control_id}: frozen control binding",
            )
    expected_summary_counts = {
        "configurations": len(configurations),
        "inherited": sum(
            row["probe_family"] == "inherited" for row in configurations.values()
        ),
        "eligible_generic": sum(
            row["decision_scope"] == "eligible_generic"
            for row in configurations.values()
        ),
        "intentionally_flexible": sum(
            row["decision_scope"] == "intentionally_flexible"
            for row in configurations.values()
        ),
        "geometry_perturbation": sum(
            row["probe_family"] == "geometry_perturbation"
            for row in configurations.values()
        ),
        "homogeneous_deformation": sum(
            row["probe_family"] == "homogeneous_deformation"
            for row in configurations.values()
        ),
        "topology_deletion": sum(
            row["probe_family"] == "topology_deletion"
            for row in configurations.values()
        ),
        "id_bijection": sum(
            row["probe_family"] == "id_bijection"
            for row in configurations.values()
        ),
        "metamorphic_controls": len(controls),
    }
    audit.require(summary["counts"] == expected_summary_counts, "summary semantic counts")
    transition_ids = validate_topology_paths(
        tables["topology_path.csv"],
        configurations,
        edges,
        exact_ranks,
        observability,
        full=summary["mode"] == "full",
        audit=audit,
    )
    validate_lookup(
        tables["lookup.csv"], configurations, relation_rows, positions_q, audit
    )
    validate_checkpoint_table(
        root,
        tables["checkpoints.csv"],
        configurations,
        packet_rows,
        edges,
        audit,
    )
    high_precision_ids = select_high_precision_configurations(
        configurations,
        controls,
        transition_ids,
        full=summary["mode"] == "full",
    )
    high_precision_report = validate_high_precision_subset(
        high_precision_ids,
        positions_d,
        edges,
        exact_ranks,
        spectra,
        tolerances,
        audit,
    )
    verdict = validate_robustness_and_decision(
        summary, configurations, observability, controls, tolerances, audit
    )
    returned = dict(summary)
    returned["_validator_verdict"] = verdict
    returned["_independent_configuration_count"] = len(configurations)
    returned["_high_precision_subset"] = high_precision_report
    return audit.checks, returned


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=pathlib.Path, required=True)
    parser.add_argument("--compare", type=pathlib.Path)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    try:
        checks, summary = validate_bundle(args.bundle, args.allow_dirty)
        if args.compare is not None:
            if canonical_tree(args.bundle) != canonical_tree(args.compare):
                reject("twin bundles are not byte-for-byte identical")
            # The complete manifest-bound byte identity makes a second
            # expensive exact/high-precision evaluation redundant.
            checks += 1
        comparison = "; byte comparison: PASS" if args.compare is not None else ""
        print(
            "RELATIONAL OBSERVABILITY BUNDLE VALID: "
            f"{checks} checks; decision={summary['verdict']}{comparison}"
        )
        return 0
    except (OSError, ValidationError, KeyError, ValueError) as error:
        print(f"RELATIONAL OBSERVABILITY BUNDLE INVALID: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
