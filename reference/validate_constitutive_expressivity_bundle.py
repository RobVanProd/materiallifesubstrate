#!/usr/bin/env python3
"""Independent evidence validator for the Constitutive Expressivity Lab.

The validator consumes exported packet coordinates and relation topology.  It
rebuilds the central rigidity operator, the local incident-relation energy,
the cubature controls, finite-length metamorphic probes, and selected
high-precision spectra without importing the C++ evaluator or trusting its
summary fields.  Every accepted bundle remains NO PROMOTION to mechanics or
dynamics.
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
EPSILON64 = 2.0**-52
SEED = 260828
PARENT_SHA = "101296f936f8473effb316b1f9ae4040b5768349"
BRANCH = "constitutive-expressivity-lab"
SUMMARY_SCHEMA = "mls.constitutive-expressivity.summary.v1"
MANIFEST_SCHEMA = "mls.constitutive-expressivity.manifest.v1"
DECISION = "retain_local_collective_relational_energy_for_research"
STOP_DECISION = "stop_inconclusive_or_implementation_failure"
SOURCE_SHA_RE = re.compile(r"[0-9a-f]{40}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
INHERITED_BLOBS = {
    "include/mls/mechanical_observability_lab.hpp": (
        "e5007f63ff4984dd5e6fbbb027a26f319cc02e5c"
    ),
    "src/mechanical_observability_lab.cpp": (
        "9ed0ab945a4178286c59aad9e8f9fd9eb1ac8c87"
    ),
    "src/kelvin_covariance_audit.cpp": (
        "bcdad1a3edaf9fbf4528438f720261141333b394"
    ),
}
FIXTURE_HASHES = {
    "configurations.csv": "cbae18e3b2c356e2898d1410f37fb90692d889f28438cfb5524753c87f1db2b7",
    "packets.csv": "dfd22994678333125b90f658d5b228c09f45e4564f52e02d6f38a3b2f3c924f7",
    "relations.csv": "14afdb0ac5822294a5d5437b3e622dffdc9f886dda395d0bfef5ae9b13c73093",
}
SMOKE_IDS = {
    "exact.tetrahedron_k4",
    "exact.tetrahedron_k4_minus_edge",
}
FULL_IDS = {
    "exact.tetrahedron_k4",
    "exact.octahedron_graph",
    "base.sc3.r180.original",
    "base.bcc35.r180.original",
    "base.jitter27.r180.original",
    "base.free_face.r180.original",
    "base.sc3_deletion.delete25.original",
    "exact.tetrahedron_k4_minus_edge",
}
BASE_FILES = {
    "configurations.csv",
    "packets.csv",
    "relations.csv",
    "bulk_expressivity.csv",
    "tangent.csv",
    "strain_energy.csv",
    "graph_energy.csv",
    "spectra.csv",
    "metamorphic.csv",
    "checkpoints.csv",
    "summary.json",
    "provenance.json",
}
HEADERS = {
    "configurations.csv": (
        "configuration_id", "parent_source_id", "role", "packet_count",
        "relation_count",
    ),
    "packets.csv": (
        "configuration_id", "packet_index", "packet_id", "mass_quanta",
        "x_m", "y_m", "z_m",
    ),
    "relations.csv": (
        "configuration_id", "relation_index", "first_id", "second_id",
        "reference_length_m",
    ),
    "bulk_expressivity.csv": (
        "control_id", "cubature", "family", "target_k_over_g", "a_j_per_m2",
        "b_j_per_m2", "weighted_moment_m2", "second_moment",
        "fourth_moment_coefficient", "measured_bulk", "measured_shear",
        "measured_k_over_g", "measured_poisson", "cross_coupling",
        "tangent_symmetry_residual", "minimum_registered_energy", "positive",
        "pass",
    ),
    "tangent.csv": (
        "control_id", "row", "column", "actual", "expected", "residual",
        "tolerance", "pass",
    ),
    "strain_energy.csv": (
        "control_id", "strain_id", "actual_energy", "expected_energy",
        "residual", "tolerance", "pass",
    ),
    "graph_energy.csv": (
        "configuration_id", "family", "target_k_over_g", "packet_count",
        "relation_count", "r_rank", "r_nullity", "r_nonrigid_nullity",
        "lr_rank", "lr_nullity", "lr_nonrigid_nullity", "lr_threshold",
        "rank_ambiguous", "h_symmetry_residual", "k_symmetry_residual",
        "h_lambda_min_certified_lower", "h_lambda_max_certified_upper",
        "h_positive_certified", "h_nnz", "h_density",
        "nonlocal_off_diagonal_count", "max_graph_hop",
        "max_euclidean_coupling_m", "rigid_energy_residual",
        "null_energy_residual", "min_resolved_lr_sigma", "kernel_equal", "pass",
    ),
    "spectra.csv": (
        "configuration_id", "family", "target_k_over_g", "singular_index",
        "singular_value", "threshold", "classification",
    ),
    "metamorphic.csv": (
        "configuration_id", "family", "probe", "baseline_energy", "probe_energy",
        "expected_ratio", "actual_ratio", "residual", "tolerance", "pass",
    ),
    "checkpoints.csv": (
        "configuration_id", "byte_count", "sha256_before", "sha256_roundtrip",
        "roundtrip_exact", "diagnostics_read_only", "pass",
    ),
}


class ValidationError(RuntimeError):
    """Stable semantic rejection of a malformed or inconsistent bundle."""


def reject(message: str) -> NoReturn:
    raise ValidationError(message)


@dataclass
class Audit:
    checks: int = 0

    def require(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            reject(message)


Vec3D = tuple[Decimal, Decimal, Decimal]
Vec3F = tuple[float, float, float]
Edge = tuple[int, int]
DMatrix = list[list[Decimal]]


@dataclass(frozen=True)
class Configuration:
    identifier: str
    packet_ids: tuple[int, ...]
    masses: tuple[int, ...]
    positions: Mapping[int, Vec3D]
    positions_float: Mapping[int, Vec3F]
    positions_exact: Mapping[int, tuple[Q, Q, Q]]
    edges: tuple[Edge, ...]
    lengths: tuple[Decimal, ...]


def require_fields(value: Mapping[str, Any], expected: set[str], where: str) -> None:
    actual = set(value)
    if actual != expected:
        reject(f"{where}: closed-field mismatch {sorted(actual ^ expected)}")


def read_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"cannot read {path.name}: {error}") from error
    if not isinstance(value, dict):
        reject(f"{path.name}: root must be an object")
    return value


def read_csv(path: pathlib.Path) -> list[dict[str, str]]:
    expected = HEADERS[path.name]
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            fields = tuple(reader.fieldnames or ())
            if fields != expected:
                reject(f"{path.name}: header mismatch")
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        raise ValidationError(f"cannot read {path.name}: {error}") from error
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        reject(f"{path.name}: malformed CSV width")
    return rows


def unsigned(value: str, where: str) -> int:
    if not value or (len(value) > 1 and value[0] == "0") or not value.isascii() or not value.isdigit():
        reject(f"{where}: noncanonical unsigned integer")
    return int(value)


def signed(value: str, where: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValidationError(f"{where}: invalid integer") from error
    if str(parsed) != value:
        reject(f"{where}: noncanonical integer")
    return parsed


def boolean(value: str, where: str) -> bool:
    if value not in {"true", "false"}:
        reject(f"{where}: invalid boolean")
    return value == "true"


def binary64(value: str, where: str, *, signed_zero: bool = False) -> float:
    if not isinstance(value, str):
        reject(f"{where}: expected hexadecimal binary64")
    try:
        parsed = float.fromhex(value)
    except ValueError as error:
        raise ValidationError(f"{where}: invalid hexadecimal binary64") from error
    if not math.isfinite(parsed) or parsed.hex() != value:
        reject(f"{where}: noncanonical/nonfinite binary64")
    if not signed_zero and parsed == 0.0 and math.copysign(1.0, parsed) < 0:
        reject(f"{where}: negative zero")
    return parsed


def decimal64(value: str, where: str) -> Decimal:
    return Decimal.from_float(binary64(value, where))


def sha256_text(value: Any, where: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        reject(f"{where}: invalid SHA-256")
    return value


def canonical_tree(root: pathlib.Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file())
    }


def manifest_preimage(hashes: Mapping[str, str]) -> bytes:
    return b"".join(
        name.encode("utf-8") + b"\0" + hashes[name].encode("ascii") + b"\n"
        for name in sorted(hashes)
    )


def validate_manifest(root: pathlib.Path, configuration_ids: set[str], audit: Audit) -> None:
    manifest = read_json(root / "manifest.json")
    require_fields(manifest, {"schema", "file_sha256", "pre_hash_sha256"}, "manifest")
    audit.require(manifest["schema"] == MANIFEST_SCHEMA, "manifest schema")
    hashes = manifest["file_sha256"]
    audit.require(isinstance(hashes, dict), "manifest hashes object")
    expected = BASE_FILES | {
        f"checkpoints/{identifier}.bin" for identifier in configuration_ids
    }
    audit.require(set(hashes) == expected, "manifest payload inventory")
    tree = canonical_tree(root)
    audit.require(set(tree) == expected | {"manifest.json"}, "bundle file inventory")
    checked: dict[str, str] = {}
    for name in sorted(expected):
        claimed = sha256_text(hashes[name], f"manifest {name}")
        audit.require(claimed == tree[name], f"manifest digest {name}")
        checked[name] = claimed
    expected_pre_hash = hashlib.sha256(manifest_preimage(checked)).hexdigest()
    audit.require(
        sha256_text(manifest["pre_hash_sha256"], "manifest pre-hash")
        == expected_pre_hash,
        "manifest pre-hash",
    )


def dsum(values: Iterable[Decimal]) -> Decimal:
    return sum(values, Decimal(0))


def dmatmul(first: Sequence[Sequence[Decimal]], second: Sequence[Sequence[Decimal]]) -> DMatrix:
    if not first or not second:
        return []
    columns = list(zip(*second, strict=True))
    if len(first[0]) != len(second):
        reject("matrix product dimensions")
    return [
        [dsum(a * b for a, b in zip(row, column, strict=True)) for column in columns]
        for row in first
    ]


def dtranspose(matrix: Sequence[Sequence[Decimal]]) -> DMatrix:
    return [list(column) for column in zip(*matrix, strict=True)] if matrix else []


def max_symmetry(matrix: Sequence[Sequence[Decimal]]) -> Decimal:
    return max(
        (abs(matrix[row][column] - matrix[column][row])
         for row in range(len(matrix)) for column in range(row + 1, len(matrix))),
        default=Decimal(0),
    )


def modular_rank(matrix: Sequence[Sequence[Q]], prime: int = 2_147_483_647) -> int:
    if not matrix:
        return 0
    work: list[list[int]] = []
    for row in matrix:
        encoded = []
        for entry in row:
            denominator = entry.denominator % prime
            if denominator == 0:
                reject("modular rank denominator")
            encoded.append(
                (entry.numerator % prime) * pow(denominator, prime - 2, prime) % prime
            )
        work.append(encoded)
    pivot_row = 0
    for column in range(len(work[0])):
        pivot = next(
            (row for row in range(pivot_row, len(work)) if work[row][column]), None
        )
        if pivot is None:
            continue
        work[pivot_row], work[pivot] = work[pivot], work[pivot_row]
        inverse = pow(work[pivot_row][column], prime - 2, prime)
        work[pivot_row] = [(entry * inverse) % prime for entry in work[pivot_row]]
        for row in range(pivot_row + 1, len(work)):
            factor = work[row][column]
            if factor:
                work[row] = [
                    (lhs - factor * rhs) % prime
                    for lhs, rhs in zip(work[row], work[pivot_row], strict=True)
                ]
        pivot_row += 1
        if pivot_row == len(work):
            break
    return pivot_row


def cross_q(first: tuple[Q, Q, Q], second: tuple[Q, Q, Q]) -> tuple[Q, Q, Q]:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def exact_rigid_rank(configuration: Configuration) -> int:
    axes = ((Q(1), Q(0), Q(0)), (Q(0), Q(1), Q(0)), (Q(0), Q(0), Q(1)))
    columns: list[list[Q]] = []
    for axis in axes:
        columns.append([axis[component] for _packet in configuration.packet_ids for component in range(3)])
    for omega in axes:
        columns.append([
            component
            for packet in configuration.packet_ids
            for component in cross_q(omega, configuration.positions_exact[packet])
        ])
    return modular_rank([
        [column[row] for column in columns]
        for row in range(3 * len(configuration.packet_ids))
    ])


def exact_rigidity_rank(configuration: Configuration) -> int:
    lookup = {packet: index for index, packet in enumerate(configuration.packet_ids)}
    rows: list[list[Q]] = []
    for first, second in configuration.edges:
        delta = tuple(
            configuration.positions_exact[second][axis]
            - configuration.positions_exact[first][axis]
            for axis in range(3)
        )
        row = [Q(0) for _ in range(3 * len(configuration.packet_ids))]
        for axis in range(3):
            row[3 * lookup[first] + axis] = -delta[axis]
            row[3 * lookup[second] + axis] = delta[axis]
        rows.append(row)
    return modular_rank(rows)


def unit_rigidity(configuration: Configuration) -> DMatrix:
    lookup = {packet: index for index, packet in enumerate(configuration.packet_ids)}
    rows: DMatrix = []
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        for first, second in configuration.edges:
            delta = tuple(
                configuration.positions[second][axis] - configuration.positions[first][axis]
                for axis in range(3)
            )
            length = dsum(value * value for value in delta).sqrt()
            row = [Decimal(0) for _ in range(3 * len(configuration.packet_ids))]
            for axis in range(3):
                row[3 * lookup[first] + axis] = -delta[axis] / length
                row[3 * lookup[second] + axis] = delta[axis] / length
            rows.append(row)
    return rows


def local_h(configuration: Configuration, family: str, ratio: float) -> DMatrix:
    count = len(configuration.edges)
    result = [[Decimal(0) for _ in range(count)] for _ in range(count)]
    if family == "pair_separable":
        for index in range(count):
            result[index][index] = Decimal(1)
        return result
    a_coefficient = Decimal.from_float(3.0 * ratio / 20.0)
    b_coefficient = Decimal.from_float(1.0 / 4.0)
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        for packet in configuration.packet_ids:
            incident = [index for index, edge in enumerate(configuration.edges) if packet in edge]
            moment = dsum(configuration.lengths[index] ** 2 for index in incident)
            for row in incident:
                for column in incident:
                    result[row][column] += (
                        (b_coefficient if row == column else Decimal(0))
                        + (a_coefficient - b_coefficient)
                        * configuration.lengths[row]
                        * configuration.lengths[column]
                        / moment
                    )
    return result


def cholesky_factor_transpose(matrix: Sequence[Sequence[Decimal]]) -> DMatrix:
    """Return U with U^T U=matrix in independent Decimal arithmetic."""

    size = len(matrix)
    lower = [[Decimal(0) for _ in range(size)] for _ in range(size)]
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        for row in range(size):
            for column in range(row + 1):
                remainder = matrix[row][column] - dsum(
                    lower[row][inner] * lower[column][inner]
                    for inner in range(column)
                )
                if row == column:
                    if remainder <= 0:
                        reject("independent H is not positive definite")
                    lower[row][column] = remainder.sqrt()
                else:
                    lower[row][column] = remainder / lower[column][column]
    return dtranspose(lower)


def high_precision_singular_values(
    matrix: Sequence[Sequence[Decimal]], maximum_sweeps: int = 220
) -> tuple[Decimal, ...]:
    """Direct cyclic one-sided Jacobi SVD; no binary64 normal equations."""

    if not matrix:
        return ()
    row_count = len(matrix)
    column_count = len(matrix[0])
    trailing = 0
    working: Sequence[Sequence[Decimal]] = matrix
    if row_count < column_count:
        working = [
            [matrix[row][column] for row in range(row_count)]
            for column in range(column_count)
        ]
        trailing = column_count - row_count
        row_count, column_count = column_count, row_count
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        columns = [
            [working[row][column] for row in range(row_count)]
            for column in range(column_count)
        ]
        scale = max(abs(value) for column in columns for value in column)
        if scale == 0:
            return tuple(Decimal(0) for _ in range(column_count + trailing))
        columns = [[value / scale for value in column] for column in columns]
        for _sweep in range(maximum_sweeps):
            changed = False
            for first in range(column_count):
                for second in range(first + 1, column_count):
                    left = columns[first]
                    right = columns[second]
                    alpha = dsum(value * value for value in left)
                    beta = dsum(value * value for value in right)
                    if alpha == 0 or beta == 0:
                        continue
                    gamma = dsum(a * b for a, b in zip(left, right, strict=True))
                    if abs(gamma) <= Decimal("1e-70") * (alpha * beta).sqrt():
                        continue
                    tau = (beta - alpha) / (2 * gamma)
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
            if not changed:
                break
        else:
            reject("high-precision Jacobi SVD did not converge")
        values = sorted(
            (dsum(value * value for value in column).sqrt() * scale for column in columns),
            reverse=True,
        )
        values.extend(Decimal(0) for _ in range(trailing))
        return tuple(+value for value in values)


def parse_configurations(
    packet_rows: Sequence[Mapping[str, str]],
    relation_rows: Sequence[Mapping[str, str]],
    expected_ids: set[str],
    audit: Audit,
) -> dict[str, Configuration]:
    packets_by: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    relations_by: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in packet_rows:
        packets_by[row["configuration_id"]].append(row)
    for row in relation_rows:
        relations_by[row["configuration_id"]].append(row)
    audit.require(set(packets_by) == expected_ids, "packet configuration inventory")
    audit.require(set(relations_by) == expected_ids, "relation configuration inventory")
    result: dict[str, Configuration] = {}
    for identifier in sorted(expected_ids):
        packet_ids: list[int] = []
        masses: list[int] = []
        positions: dict[int, Vec3D] = {}
        positions_float: dict[int, Vec3F] = {}
        positions_exact: dict[int, tuple[Q, Q, Q]] = {}
        rows = packets_by[identifier]
        for index, row in enumerate(rows):
            audit.require(
                unsigned(row["packet_index"], f"{identifier} packet index") == index,
                f"{identifier}: canonical packet index",
            )
            packet_id = unsigned(row["packet_id"], f"{identifier} packet ID")
            mass = signed(row["mass_quanta"], f"{identifier} packet mass")
            coordinates_float = tuple(
                binary64(row[field], f"{identifier} {field}")
                for field in ("x_m", "y_m", "z_m")
            )
            coordinates = tuple(Decimal.from_float(value) for value in coordinates_float)
            exact = tuple(Q.from_float(value) for value in coordinates_float)
            audit.require(packet_id not in positions, f"{identifier}: duplicate packet ID")
            audit.require(mass > 0, f"{identifier}: positive packet mass")
            packet_ids.append(packet_id)
            masses.append(mass)
            positions[packet_id] = coordinates  # type: ignore[assignment]
            positions_float[packet_id] = coordinates_float  # type: ignore[assignment]
            positions_exact[packet_id] = exact  # type: ignore[assignment]
        audit.require(packet_ids == sorted(packet_ids), f"{identifier}: packet order")

        edges: list[Edge] = []
        lengths: list[Decimal] = []
        for index, row in enumerate(relations_by[identifier]):
            audit.require(
                unsigned(row["relation_index"], f"{identifier} relation index") == index,
                f"{identifier}: canonical relation index",
            )
            first = unsigned(row["first_id"], f"{identifier} first endpoint")
            second = unsigned(row["second_id"], f"{identifier} second endpoint")
            audit.require(first < second, f"{identifier}: canonical edge orientation")
            audit.require(first in positions and second in positions, f"{identifier}: endpoint")
            edge = (first, second)
            audit.require(edge not in edges, f"{identifier}: duplicate relation")
            with localcontext() as context:
                context.prec = DECIMAL_DIGITS
                delta = tuple(
                    positions[second][axis] - positions[first][axis]
                    for axis in range(3)
                )
                recomputed = dsum(value * value for value in delta).sqrt()
            reported = decimal64(row["reference_length_m"], f"{identifier} relation length")
            scale = max(Decimal(1), abs(recomputed), abs(reported))
            audit.require(
                abs(recomputed - reported)
                <= Decimal(128) * Decimal(len(packet_ids) + len(rows))
                * Decimal.from_float(EPSILON64) * scale,
                f"{identifier}: independently reconstructed relation length",
            )
            edges.append(edge)
            lengths.append(recomputed)
        audit.require(edges == sorted(edges), f"{identifier}: relation order")
        result[identifier] = Configuration(
            identifier,
            tuple(packet_ids),
            tuple(masses),
            positions,
            positions_float,
            positions_exact,
            tuple(edges),
            tuple(lengths),
        )
    return result


def validate_configuration_metadata(
    rows: Sequence[Mapping[str, str]],
    configurations: Mapping[str, Configuration],
    audit: Audit,
) -> None:
    keyed = {row["configuration_id"]: row for row in rows}
    audit.require(len(keyed) == len(rows), "duplicate configuration metadata")
    audit.require(set(keyed) == set(configurations), "configuration metadata inventory")
    for identifier, configuration in configurations.items():
        row = keyed[identifier]
        audit.require(row["parent_source_id"] == identifier,
                      f"{identifier}: parent source binding")
        expected_role = (
            "intentionally_floppy"
            if identifier == "exact.tetrahedron_k4_minus_edge"
            else "eligible_generic"
        )
        audit.require(row["role"] == expected_role, f"{identifier}: graph role")
        audit.require(unsigned(row["packet_count"], f"{identifier} metadata packets")
                      == len(configuration.packet_ids), f"{identifier}: metadata packet count")
        audit.require(unsigned(row["relation_count"], f"{identifier} metadata relations")
                      == len(configuration.edges), f"{identifier}: metadata relation count")


@dataclass(frozen=True)
class Cubature:
    identifier: str
    packet_count: int
    weights: tuple[Decimal, ...]
    outers: tuple[tuple[tuple[Decimal, ...], ...], ...]
    moment: Decimal
    second: Decimal
    fourth: Decimal
    a_multiplier: Decimal
    b_multiplier: Decimal


def cubatures() -> tuple[Cubature, Cubature]:
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        primary_outers: list[tuple[tuple[Decimal, ...], ...]] = []
        for axis in range(3):
            primary_outers.append(tuple(tuple(
                Decimal(1) if row == axis and column == axis else Decimal(0)
                for column in range(3)
            ) for row in range(3)))
        for signs in ((1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)):
            primary_outers.append(tuple(tuple(
                Decimal(signs[row] * signs[column]) / Decimal(3)
                for column in range(3)
            ) for row in range(3)))

        secondary_outers: list[tuple[tuple[Decimal, ...], ...]] = []
        for axis in range(3):
            secondary_outers.append(tuple(tuple(
                Decimal(1) if row == axis and column == axis else Decimal(0)
                for column in range(3)
            ) for row in range(3)))
        for first, second in ((0, 1), (0, 2), (1, 2)):
            for sign in (1, -1):
                components = [0, 0, 0]
                components[first] = 1
                components[second] = sign
                secondary_outers.append(tuple(tuple(
                    Decimal(components[row] * components[column]) / Decimal(2)
                    for column in range(3)
                ) for row in range(3)))
    return (
        Cubature(
            "axes_body_diagonals_7", 8,
            tuple(Decimal(value) for value in (8, 8, 8, 9, 9, 9, 9)),
            tuple(primary_outers), Decimal(60), Decimal(20), Decimal(4),
            Decimal(3) / Decimal(20), Decimal(1) / Decimal(4),
        ),
        Cubature(
            "axes_face_diagonals_9", 10,
            tuple(Decimal(value) for value in (1, 1, 1, 2, 2, 2, 2, 2, 2)),
            tuple(secondary_outers), Decimal(15), Decimal(5), Decimal(1),
            Decimal(3) / Decimal(5), Decimal(1),
        ),
    )


def zero_strain() -> DMatrix:
    return [[Decimal(0) for _column in range(3)] for _row in range(3)]


def kelvin_basis() -> tuple[DMatrix, ...]:
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        inverse_sqrt_two = Decimal(1) / Decimal(2).sqrt()
        result: list[DMatrix] = []
        for index in range(6):
            strain = zero_strain()
            if index < 3:
                strain[index][index] = Decimal(1)
            else:
                row, column = ((0, 1), (0, 2), (1, 2))[index - 3]
                strain[row][column] = inverse_sqrt_two
                strain[column][row] = inverse_sqrt_two
            result.append(strain)
        return tuple(result)


def mixed_strains() -> tuple[DMatrix, ...]:
    rational = (
        ((Q(1, 5), Q(1, 7), Q(-1, 11)), (Q(1, 7), Q(-2, 5), Q(1, 13)), (Q(-1, 11), Q(1, 13), Q(1, 3))),
        ((Q(-1, 4), Q(1, 9), Q(1, 10)), (Q(1, 9), Q(1, 6), Q(-1, 8)), (Q(1, 10), Q(-1, 8), Q(1, 12))),
        ((Q(2, 7), Q(-1, 6), Q(1, 5)), (Q(-1, 6), Q(1, 9), Q(1, 14)), (Q(1, 5), Q(1, 14), Q(-3, 11))),
    )
    with localcontext() as context:
        context.prec = DECIMAL_DIGITS
        return tuple([
            [Decimal(value.numerator) / Decimal(value.denominator) for value in row]
            for row in matrix
        ] for matrix in rational)


def add_strain(first: DMatrix, second: DMatrix) -> DMatrix:
    return [[first[row][column] + second[row][column] for column in range(3)] for row in range(3)]


def extension(outer: Sequence[Sequence[Decimal]], strain: DMatrix) -> Decimal:
    return dsum(
        outer[row][column] * strain[row][column]
        for row in range(3) for column in range(3)
    )


def cubature_energy(
    cubature: Cubature,
    family: str,
    strain: DMatrix,
    bulk: Decimal,
    shear: Decimal,
) -> Decimal:
    values = [extension(outer, strain) for outer in cubature.outers]
    if family == "pair_separable":
        return dsum(
            weight * value * value / 2
            for weight, value in zip(cubature.weights, values, strict=True)
        )
    q_value = dsum(
        weight * value
        for weight, value in zip(cubature.weights, values, strict=True)
    )
    dilation = q_value / cubature.moment
    residual = dsum(
        weight * (value - dilation) ** 2
        for weight, value in zip(cubature.weights, values, strict=True)
    )
    a_coefficient = cubature.a_multiplier * bulk
    b_coefficient = cubature.b_multiplier * shear
    return (
        a_coefficient * q_value * q_value / (2 * cubature.moment)
        + b_coefficient * residual / 2
    )


def derive_tangent(energy: Any) -> DMatrix:
    basis = kelvin_basis()
    diagonal = [energy(strain) for strain in basis]
    result = [[Decimal(0) for _column in range(6)] for _row in range(6)]
    for row in range(6):
        result[row][row] = 2 * diagonal[row]
        for column in range(row + 1, 6):
            value = energy(add_strain(basis[row], basis[column])) - diagonal[row] - diagonal[column]
            result[row][column] = value
            result[column][row] = value
    return result


def isotropic_energy(strain: DMatrix, bulk: Decimal, shear: Decimal) -> Decimal:
    trace = dsum(strain[index][index] for index in range(3))
    norm = dsum(strain[row][column] ** 2 for row in range(3) for column in range(3))
    return bulk * trace * trace / 2 + shear * (norm - trace * trace / 3)


def close_decimal(
    audit: Audit,
    actual: Decimal,
    expected: Decimal,
    tolerance: Decimal,
    where: str,
) -> None:
    audit.require(abs(actual - expected) <= tolerance, where)


def validate_bulk_controls(
    bulk_rows: Sequence[Mapping[str, str]],
    tangent_rows: Sequence[Mapping[str, str]],
    strain_rows: Sequence[Mapping[str, str]],
    audit: Audit,
) -> int:
    cubature_map = {value.identifier: value for value in cubatures()}
    expected_controls: dict[str, tuple[Cubature, str, float]] = {}
    ratios = (1.0 / 3.0, 1.0, 2.0, 10.0)
    for cubature in cubature_map.values():
        expected_controls[f"{cubature.identifier}.pair"] = (
            cubature, "pair_separable", 5.0 / 3.0
        )
        for ratio in ratios:
            expected_controls[
                f"{cubature.identifier}.collective.{ratio.hex()}"
            ] = (cubature, "local_incident_collective", ratio)
    audit.require(len(bulk_rows) == 10, "bulk row count")
    audit.require(
        {row["control_id"] for row in bulk_rows} == set(expected_controls),
        "bulk control inventory",
    )
    tangent_by: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    strain_by: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in tangent_rows:
        tangent_by[row["control_id"]].append(row)
    for row in strain_rows:
        strain_by[row["control_id"]].append(row)
    audit.require(set(tangent_by) == set(expected_controls), "tangent control inventory")
    audit.require(set(strain_by) == set(expected_controls), "strain control inventory")
    failures = 0
    for row in bulk_rows:
        identifier = row["control_id"]
        cubature, family, ratio_float = expected_controls[identifier]
        audit.require(row["cubature"] == cubature.identifier, f"{identifier}: cubature")
        audit.require(row["family"] == family, f"{identifier}: family")
        target = Decimal.from_float(ratio_float)
        reported_target = decimal64(row["target_k_over_g"], f"{identifier} target")
        audit.require(reported_target == target, f"{identifier}: exact target encoding")
        dimension = max(6, 3 * cubature.packet_count, len(cubature.weights))
        epsilon = Decimal.from_float(EPSILON64)
        if family == "pair_separable":
            bulk = cubature.second / Decimal(3)
            # Isotropic fourth coefficient c gives lambda=G=c and K=5c/3.
            shear = cubature.fourth
            bulk = Decimal(5) * shear / Decimal(3)
            energy = lambda strain: cubature_energy(
                cubature, family, strain, bulk, shear
            )
            expected_a = Decimal(0)
            expected_b = Decimal(0)
        else:
            bulk = target
            shear = Decimal(1)
            energy = lambda strain: cubature_energy(
                cubature, family, strain, bulk, shear
            )
            expected_a = cubature.a_multiplier * bulk
            expected_b = cubature.b_multiplier * shear
        tangent = derive_tangent(energy)
        measured_shear = tangent[3][3] / 2
        measured_bulk = dsum(tangent[0][column] for column in range(3)) / 3
        measured_ratio = measured_bulk / measured_shear
        poisson = (3 * measured_bulk - 2 * measured_shear) / (
            2 * (3 * measured_bulk + measured_shear)
        )
        registered_strains = (*kelvin_basis(), *mixed_strains())
        registered_energies = [energy(strain) for strain in registered_strains]
        minimum_energy = min(registered_energies)
        expected_cross = max(
            (abs(tangent[r][c]) for r in range(3) for c in range(3, 6)),
            default=Decimal(0),
        )
        values = {
            "a_j_per_m2": expected_a,
            "b_j_per_m2": expected_b,
            "weighted_moment_m2": cubature.moment,
            "second_moment": cubature.second,
            "fourth_moment_coefficient": cubature.fourth,
            "measured_bulk": measured_bulk,
            "measured_shear": measured_shear,
            "measured_k_over_g": measured_ratio,
            "measured_poisson": poisson,
            "cross_coupling": expected_cross,
            "tangent_symmetry_residual": max_symmetry(tangent),
            "minimum_registered_energy": minimum_energy,
        }
        row_pass = True
        for field, expected in values.items():
            actual = decimal64(row[field], f"{identifier} {field}")
            scale = max(Decimal(1), abs(actual), abs(expected))
            factor = Decimal(131072 if field == "measured_k_over_g" else 65536)
            gate = factor * Decimal(dimension) * epsilon * scale
            close_decimal(audit, actual, expected, gate, f"{identifier}: {field}")
            row_pass = row_pass and abs(actual - expected) <= gate
        positive = minimum_energy > 0 and measured_bulk > 0 and measured_shear > 0
        ratio_gate = Decimal(131072) * Decimal(dimension) * epsilon * max(
            Decimal(1), abs(measured_ratio), abs(target)
        )
        if family == "pair_separable":
            row_pass = row_pass and abs(measured_ratio - Decimal(5) / Decimal(3)) <= ratio_gate
        else:
            row_pass = row_pass and abs(measured_ratio - target) <= ratio_gate
        row_pass = row_pass and positive
        audit.require(boolean(row["positive"], f"{identifier} positive") == positive,
                      f"{identifier}: positive flag")
        audit.require(boolean(row["pass"], f"{identifier} pass") == row_pass,
                      f"{identifier}: pass flag")
        failures += int(not row_pass)

        indexed_tangent = {
            (
                unsigned(entry["row"], f"{identifier} tangent row"),
                unsigned(entry["column"], f"{identifier} tangent column"),
            ): entry
            for entry in tangent_by[identifier]
        }
        audit.require(set(indexed_tangent) == {(r, c) for r in range(6) for c in range(6)},
                      f"{identifier}: tangent matrix inventory")
        for (tangent_row, tangent_column), entry in indexed_tangent.items():
            actual = decimal64(entry["actual"], f"{identifier} tangent actual")
            expected = Decimal.from_float(
                float(bulk) * (1.0 if tangent_row < 3 and tangent_column < 3 else 0.0)
                + 2.0 * float(shear) * (
                    (1.0 if tangent_row == tangent_column else 0.0)
                    - (1.0 / 3.0 if tangent_row < 3 and tangent_column < 3 else 0.0)
                )
            )
            independently_derived = tangent[tangent_row][tangent_column]
            gate = Decimal(65536) * Decimal(dimension) * epsilon * max(
                Decimal(1), abs(actual), abs(expected)
            )
            reported_residual = decimal64(entry["residual"], f"{identifier} tangent residual")
            reported_gate = decimal64(entry["tolerance"], f"{identifier} tangent tolerance")
            close_decimal(audit, actual, independently_derived, gate,
                          f"{identifier}: independently derived tangent")
            close_decimal(audit, expected, independently_derived, gate,
                          f"{identifier}: isotropic tangent target")
            close_decimal(audit, reported_residual, abs(actual - expected), gate,
                          f"{identifier}: tangent residual arithmetic")
            close_decimal(audit, reported_gate, gate, gate * Decimal.from_float(EPSILON64) * 8,
                          f"{identifier}: tangent gate")
            tangent_pass = reported_residual <= reported_gate
            audit.require(boolean(entry["pass"], f"{identifier} tangent pass") == tangent_pass,
                          f"{identifier}: tangent pass flag")

        indexed_strains = {entry["strain_id"]: entry for entry in strain_by[identifier]}
        base_strain_ids = {*(f"kelvin_{index}" for index in range(6)),
                           *(f"mixed_{index}" for index in range(3))}
        expected_strain_ids = base_strain_ids | {
            f"rotated_{identifier}" for identifier in base_strain_ids
        }
        audit.require(set(indexed_strains) == expected_strain_ids,
                      f"{identifier}: strain inventory")
        for strain_index, strain in enumerate(registered_strains):
            strain_id = (
                f"kelvin_{strain_index}" if strain_index < 6
                else f"mixed_{strain_index - 6}"
            )
            entry = indexed_strains[strain_id]
            actual = decimal64(entry["actual_energy"], f"{identifier} {strain_id} actual")
            expected = isotropic_energy(strain, bulk, shear)
            independent = energy(strain)
            gate = Decimal(65536) * Decimal(dimension) * epsilon * max(
                Decimal(1), abs(actual), abs(expected)
            )
            reported_expected = decimal64(
                entry["expected_energy"], f"{identifier} {strain_id} expected"
            )
            residual = decimal64(entry["residual"], f"{identifier} {strain_id} residual")
            reported_gate = decimal64(entry["tolerance"], f"{identifier} {strain_id} gate")
            close_decimal(audit, actual, independent, gate,
                          f"{identifier}: independent {strain_id} energy")
            close_decimal(audit, reported_expected, expected, gate,
                          f"{identifier}: expected {strain_id} energy")
            close_decimal(audit, residual, abs(actual - reported_expected), gate,
                          f"{identifier}: {strain_id} residual")
            close_decimal(audit, reported_gate, gate, gate * Decimal.from_float(EPSILON64) * 8,
                          f"{identifier}: {strain_id} gate")
            strain_pass = residual <= reported_gate
            audit.require(boolean(entry["pass"], f"{identifier} {strain_id} pass") == strain_pass,
                          f"{identifier}: {strain_id} pass flag")
            rotated_id = f"rotated_{strain_id}"
            rotated_entry = indexed_strains[rotated_id]
            rotated_actual = decimal64(
                rotated_entry["actual_energy"], f"{identifier} {rotated_id} actual"
            )
            rotated_expected = decimal64(
                rotated_entry["expected_energy"], f"{identifier} {rotated_id} expected"
            )
            rotation_gate = Decimal(32768) * Decimal(dimension) * epsilon * max(
                Decimal(1), abs(rotated_actual), abs(independent)
            )
            rotation_residual = decimal64(
                rotated_entry["residual"], f"{identifier} {rotated_id} residual"
            )
            reported_rotation_gate = decimal64(
                rotated_entry["tolerance"], f"{identifier} {rotated_id} gate"
            )
            close_decimal(audit, rotated_actual, independent, rotation_gate,
                          f"{identifier}: independent rotated {strain_id}")
            close_decimal(audit, rotated_expected, independent, gate,
                          f"{identifier}: rotated target {strain_id}")
            close_decimal(
                audit, rotation_residual, abs(rotated_actual - rotated_expected),
                rotation_gate, f"{identifier}: rotated residual {strain_id}",
            )
            close_decimal(
                audit, reported_rotation_gate, rotation_gate,
                rotation_gate * Decimal.from_float(EPSILON64) * 8,
                f"{identifier}: rotated gate {strain_id}",
            )
            rotated_pass = rotation_residual <= reported_rotation_gate
            audit.require(
                boolean(rotated_entry["pass"], f"{identifier} {rotated_id} pass")
                == rotated_pass,
                f"{identifier}: {rotated_id} pass flag",
            )
    return failures


def euclidean_distance(
    positions: Mapping[int, Vec3D], first: int, second: int
) -> Decimal:
    return dsum(
        (positions[second][axis] - positions[first][axis]) ** 2
        for axis in range(3)
    ).sqrt()


def validate_graph_controls(
    configurations: Mapping[str, Configuration],
    graph_rows: Sequence[Mapping[str, str]],
    spectrum_rows: Sequence[Mapping[str, str]],
    audit: Audit,
) -> tuple[int, int]:
    ratios = (1.0 / 3.0, 1.0, 2.0, 10.0)
    expected_keys = {
        (identifier, "pair_separable", (5.0 / 3.0).hex())
        for identifier in configurations
    } | {
        (identifier, "local_incident_collective", ratio.hex())
        for identifier in configurations for ratio in ratios
    }
    keyed_rows: dict[tuple[str, str, str], Mapping[str, str]] = {}
    for row in graph_rows:
        key = (row["configuration_id"], row["family"], row["target_k_over_g"])
        audit.require(key not in keyed_rows, f"duplicate graph row {key}")
        keyed_rows[key] = row
    audit.require(set(keyed_rows) == expected_keys, "graph control inventory")
    spectra_by: dict[tuple[str, str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in spectrum_rows:
        key = (row["configuration_id"], row["family"], row["target_k_over_g"])
        spectra_by[key].append(row)
    audit.require(set(spectra_by) == expected_keys, "spectrum control inventory")

    exact_ranks: dict[str, tuple[int, int]] = {}
    rigidities: dict[str, DMatrix] = {}
    for identifier, configuration in configurations.items():
        rank = exact_rigidity_rank(configuration)
        rigid_rank = exact_rigid_rank(configuration)
        maximum_rank = 3 * len(configuration.packet_ids) - rigid_rank
        expected_nonrigid = 1 if identifier == "exact.tetrahedron_k4_minus_edge" else 0
        audit.require(
            maximum_rank - rank == expected_nonrigid,
            f"{identifier}: exact modular rigidity/nullity control",
        )
        exact_ranks[identifier] = (rank, rigid_rank)
        rigidities[identifier] = unit_rigidity(configuration)

    failures = 0
    high_precision_receipts = 0
    for key in sorted(expected_keys):
        identifier, family, ratio_text = key
        row = keyed_rows[key]
        configuration = configurations[identifier]
        ratio = binary64(ratio_text, f"{identifier} ratio key")
        reported_ratio = binary64(row["target_k_over_g"], f"{identifier} ratio")
        audit.require(reported_ratio == ratio, f"{identifier}: graph ratio binding")
        packet_count = len(configuration.packet_ids)
        relation_count = len(configuration.edges)
        dimension = max(6, 3 * packet_count, relation_count)
        rank_r, rigid_rank = exact_ranks[identifier]
        nullity_r = 3 * packet_count - rank_r
        nonrigid = nullity_r - rigid_rank
        audit.require(unsigned(row["packet_count"], f"{identifier} packets") == packet_count,
                      f"{identifier}: packet count")
        audit.require(unsigned(row["relation_count"], f"{identifier} relations") == relation_count,
                      f"{identifier}: relation count")
        audit.require(unsigned(row["r_rank"], f"{identifier} R rank") == rank_r,
                      f"{identifier}: independent R rank")
        audit.require(unsigned(row["r_nullity"], f"{identifier} R nullity") == nullity_r,
                      f"{identifier}: R nullity")
        audit.require(unsigned(row["r_nonrigid_nullity"], f"{identifier} R nonrigid") == nonrigid,
                      f"{identifier}: R nonrigid nullity")

        rigidity = rigidities[identifier]
        h_matrix = local_h(configuration, family, ratio)
        packet_hessian = dmatmul(dtranspose(rigidity), dmatmul(h_matrix, rigidity))
        rank_lr = rank_r  # H is independently established strictly positive below.
        nullity_lr = nullity_r
        nonrigid_lr = nonrigid
        audit.require(unsigned(row["lr_rank"], f"{identifier} LR rank") == rank_lr,
                      f"{identifier}: LR rank")
        audit.require(unsigned(row["lr_nullity"], f"{identifier} LR nullity") == nullity_lr,
                      f"{identifier}: LR nullity")
        audit.require(unsigned(row["lr_nonrigid_nullity"], f"{identifier} LR nonrigid") == nonrigid_lr,
                      f"{identifier}: LR nonrigid nullity")

        if family == "pair_separable":
            coefficient_a = coefficient_b = 1.0
            lower = upper = 1.0
            expected_hop = 0
        else:
            coefficient_a = 3.0 * ratio / 20.0
            coefficient_b = 1.0 / 4.0
            lower = 2.0 * min(coefficient_a, coefficient_b)
            upper = 2.0 * max(coefficient_a, coefficient_b)
            expected_hop = 1
        reported_lower = binary64(
            row["h_lambda_min_certified_lower"], f"{identifier} H lower"
        )
        reported_upper = binary64(
            row["h_lambda_max_certified_upper"], f"{identifier} H upper"
        )
        audit.require(reported_lower == lower, f"{identifier}: H certified lower")
        audit.require(reported_upper == upper, f"{identifier}: H certified upper")
        h_positive = coefficient_a > 0 and coefficient_b > 0
        audit.require(boolean(row["h_positive_certified"], f"{identifier} H positive") == h_positive,
                      f"{identifier}: H positive certificate")

        nonzero: list[tuple[int, int]] = []
        nonlocal_count = 0
        # This is the maximum distance between any endpoints of every pair of
        # relation coordinates coupled by H.  Diagonal H entries count: a
        # pair-separable relation therefore has its bond length, not zero, as
        # its Euclidean support.  max_graph_hop reports the distinct
        # relation-space adjacency radius.
        maximum_coupling = Decimal(0)
        for first in range(relation_count):
            for second in range(relation_count):
                if h_matrix[first][second] == 0:
                    continue
                nonzero.append((first, second))
                first_edge = configuration.edges[first]
                second_edge = configuration.edges[second]
                if first != second and not set(first_edge).intersection(second_edge):
                    nonlocal_count += 1
                maximum_coupling = max(
                    maximum_coupling,
                    *(euclidean_distance(configuration.positions, a, b)
                      for a in first_edge for b in second_edge),
                )
        nnz = len(nonzero)
        density = Decimal(nnz) / Decimal(relation_count * relation_count)
        audit.require(unsigned(row["h_nnz"], f"{identifier} H nnz") == nnz,
                      f"{identifier}: H sparsity")
        reported_density = decimal64(row["h_density"], f"{identifier} H density")
        close_decimal(
            audit, reported_density, density,
            Decimal(16) * Decimal.from_float(EPSILON64),
            f"{identifier}: H density",
        )
        audit.require(
            unsigned(row["nonlocal_off_diagonal_count"], f"{identifier} nonlocal")
            == nonlocal_count == 0,
            f"{identifier}: H locality",
        )
        audit.require(unsigned(row["max_graph_hop"], f"{identifier} graph hop") == expected_hop,
                      f"{identifier}: graph locality radius")
        reported_coupling = decimal64(
            row["max_euclidean_coupling_m"], f"{identifier} Euclidean coupling"
        )
        coupling_gate = Decimal(32768) * Decimal(dimension) * Decimal.from_float(EPSILON64) * max(
            Decimal(1), abs(maximum_coupling), abs(reported_coupling)
        )
        close_decimal(audit, reported_coupling, maximum_coupling, coupling_gate,
                      f"{identifier}: Euclidean locality radius")

        symmetry_gate = 32768.0 * dimension * EPSILON64
        h_symmetry = binary64(row["h_symmetry_residual"], f"{identifier} H symmetry")
        k_symmetry = binary64(row["k_symmetry_residual"], f"{identifier} K symmetry")
        audit.require(h_symmetry <= symmetry_gate and k_symmetry <= symmetry_gate,
                      f"{identifier}: symmetry gates")
        close_decimal(audit, Decimal.from_float(h_symmetry), max_symmetry(h_matrix),
                      Decimal.from_float(symmetry_gate), f"{identifier}: H symmetry")
        close_decimal(audit, Decimal.from_float(k_symmetry), max_symmetry(packet_hessian),
                      Decimal.from_float(symmetry_gate), f"{identifier}: K symmetry")

        spectrum_entries = sorted(
            spectra_by[key], key=lambda value: unsigned(value["singular_index"], "spectrum index")
        )
        factor_row_count = (
            relation_count
            if family == "pair_separable"
            else packet_count + 2 * relation_count
        )
        expected_spectrum_width = min(factor_row_count, 3 * packet_count)
        audit.require(
            [unsigned(value["singular_index"], "spectrum index") for value in spectrum_entries]
            == list(range(expected_spectrum_width)),
            f"{identifier}: complete spectrum",
        )
        spectrum = [
            binary64(value["singular_value"], f"{identifier} singular value")
            for value in spectrum_entries
        ]
        audit.require(
            all(spectrum[index] >= spectrum[index + 1] for index in range(len(spectrum) - 1)),
            f"{identifier}: descending spectrum",
        )
        threshold = 512.0 * dimension * EPSILON64 * max(
            spectrum[0], sys.float_info.min
        )
        reported_threshold = binary64(row["lr_threshold"], f"{identifier} LR threshold")
        audit.require(reported_threshold == threshold, f"{identifier}: rank threshold")
        accepted = 0
        ambiguous = False
        minimum_nonzero = math.inf
        for entry, value in zip(spectrum_entries, spectrum, strict=True):
            entry_threshold = binary64(entry["threshold"], f"{identifier} spectrum threshold")
            audit.require(entry_threshold == threshold, f"{identifier}: spectrum threshold binding")
            classification = (
                "accepted_nonzero" if value > 8.0 * threshold
                else "resolved_zero" if value < threshold / 8.0
                else "ambiguous"
            )
            audit.require(entry["classification"] == classification,
                          f"{identifier}: spectrum classification")
            accepted += int(classification == "accepted_nonzero")
            ambiguous = ambiguous or classification == "ambiguous"
            if classification == "accepted_nonzero":
                minimum_nonzero = min(minimum_nonzero, value)
        audit.require(accepted == rank_lr, f"{identifier}: spectral rank")
        audit.require(boolean(row["rank_ambiguous"], f"{identifier} ambiguity") == ambiguous,
                      f"{identifier}: ambiguity flag")
        reported_minimum = binary64(row["min_resolved_lr_sigma"], f"{identifier} minimum sigma")
        audit.require(reported_minimum == minimum_nonzero, f"{identifier}: minimum sigma")

        high_precision_selected = (
            packet_count <= 6
            or (
                identifier == "base.jitter27.r180.original"
                and family == "local_incident_collective"
                and ratio == 2.0
            )
        )
        if high_precision_selected:
            factor = cholesky_factor_transpose(h_matrix)
            independent_lr = dmatmul(factor, rigidity)
            independent_spectrum = high_precision_singular_values(independent_lr)
            audit.require(len(independent_spectrum) >= len(spectrum),
                          f"{identifier}: high-precision spectrum coverage")
            comparison_gate = Decimal(131072) * Decimal(dimension) * Decimal.from_float(EPSILON64)
            for index in range(rank_lr):
                close_decimal(
                    audit,
                    Decimal.from_float(spectrum[index]),
                    independent_spectrum[index],
                    comparison_gate * max(Decimal(1), independent_spectrum[index]),
                    f"{identifier}: high-precision sigma {index}",
                )
            for index in range(rank_lr, len(spectrum)):
                audit.require(spectrum[index] < threshold / 8.0,
                              f"{identifier}: resolved numerical null tail")
            high_precision_receipts += 1

        energy_gate = 65536.0 * dimension * EPSILON64 * max(1.0, upper)
        rigid_energy = binary64(row["rigid_energy_residual"], f"{identifier} rigid energy")
        null_energy = binary64(row["null_energy_residual"], f"{identifier} null energy")
        kernel_equal = rank_lr == rank_r and nullity_lr == nullity_r
        independent_pass = (
            not ambiguous
            and kernel_equal
            and h_positive
            and nonlocal_count == 0
            and h_symmetry <= symmetry_gate
            and k_symmetry <= symmetry_gate
            and rigid_energy <= energy_gate
            and null_energy <= energy_gate
            and (nonrigid_lr == 1 if identifier == "exact.tetrahedron_k4_minus_edge" else nonrigid_lr == 0)
        )
        audit.require(boolean(row["kernel_equal"], f"{identifier} kernel") == kernel_equal,
                      f"{identifier}: kernel equality")
        audit.require(boolean(row["pass"], f"{identifier} pass") == independent_pass,
                      f"{identifier}: graph pass")
        failures += int(not independent_pass)
    audit.require(high_precision_receipts >= 10, "selected high-precision spectrum coverage")
    return failures, high_precision_receipts


def transform_float(
    positions: Mapping[int, Vec3F],
    matrix: Sequence[Sequence[float]],
    translation: Vec3F = (0.0, 0.0, 0.0),
    mapping: Mapping[int, int] | None = None,
) -> dict[int, Vec3F]:
    return {
        packet if mapping is None else mapping[packet]: tuple(
            math.fsum(matrix[row][column] * point[column] for column in range(3))
            + translation[row]
            for row in range(3)
        )
        for packet, point in positions.items()
    }


def finite_graph_energy(
    family: str,
    reference: Mapping[int, Vec3F],
    current: Mapping[int, Vec3F],
    edges: Sequence[Edge],
) -> float:
    states: list[tuple[Edge, float, float]] = []
    for first, second in edges:
        reference_length = math.dist(reference[first], reference[second])
        current_length = math.dist(current[first], current[second])
        states.append(((first, second), reference_length, current_length - reference_length))
    if family == "pair_separable":
        return 0.5 * math.fsum(extension_value * extension_value for _edge, _length, extension_value in states)
    total = 0.0
    for packet in sorted(reference):
        incident = [
            (length, extension_value)
            for edge, length, extension_value in states if packet in edge
        ]
        if not incident:
            continue
        moment = math.fsum(length * length for length, _extension in incident)
        q_value = math.fsum(length * extension_value for length, extension_value in incident)
        dilation = q_value / moment
        residual = math.fsum(
            (extension_value - dilation * length) ** 2
            for length, extension_value in incident
        )
        total += 0.5 * (3.0 / 10.0) * q_value * q_value / moment
        total += 0.5 * (1.0 / 4.0) * residual
    return total


def axis_angle_rotation() -> tuple[tuple[float, float, float], ...]:
    length = math.sqrt(14.0)
    x, y, z = 1.0 / length, 2.0 / length, 3.0 / length
    angle = 0.731
    cosine = math.cos(angle)
    sine = math.sin(angle)
    one_minus = 1.0 - cosine
    return (
        (cosine + x * x * one_minus, x * y * one_minus - z * sine, x * z * one_minus + y * sine),
        (y * x * one_minus + z * sine, cosine + y * y * one_minus, y * z * one_minus - x * sine),
        (z * x * one_minus - y * sine, z * y * one_minus + x * sine, cosine + z * z * one_minus),
    )


def validate_metamorphic(
    configurations: Mapping[str, Configuration],
    rows: Sequence[Mapping[str, str]],
    audit: Audit,
) -> int:
    families = ("pair_separable", "local_incident_collective")
    probes = {
        "translation", "rotation", "rotation_translation",
        "scale_0x1.0000000000000p-1", "scale_0x1.0000000000000p+1",
        "packet_reverse", "packet_splitmix", "relation_reverse",
        "relation_splitmix", "relation_endpoint_reverse",
        "id_reverse", "id_cycle", "id_sha256",
    }
    expected_keys = {
        (identifier, family, probe)
        for identifier in configurations for family in families for probe in probes
    }
    keyed: dict[tuple[str, str, str], Mapping[str, str]] = {}
    for row in rows:
        key = (row["configuration_id"], row["family"], row["probe"])
        audit.require(key not in keyed, f"duplicate metamorphic row {key}")
        keyed[key] = row
    audit.require(set(keyed) == expected_keys, "metamorphic inventory")
    deformation = (
        (21.0 / 20.0, 1.0 / 20.0, -1.0 / 40.0),
        (0.0, 19.0 / 20.0, 1.0 / 25.0),
        (1.0 / 50.0, 0.0, 11.0 / 10.0),
    )
    identity = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    rotation = axis_angle_rotation()
    translation = (7.0 / 13.0, -5.0 / 11.0, 3.0 / 17.0)
    failures = 0
    for identifier, configuration in configurations.items():
        reference = configuration.positions_float
        current = transform_float(reference, deformation)
        for family in families:
            baseline = finite_graph_energy(family, reference, current, configuration.edges)
            probe_energy: dict[str, float] = {}
            probe_energy["translation"] = finite_graph_energy(
                family,
                transform_float(reference, identity, translation),
                transform_float(current, identity, translation),
                configuration.edges,
            )
            probe_energy["rotation"] = finite_graph_energy(
                family, transform_float(reference, rotation),
                transform_float(current, rotation), configuration.edges,
            )
            probe_energy["rotation_translation"] = finite_graph_energy(
                family, transform_float(reference, rotation, translation),
                transform_float(current, rotation, translation), configuration.edges,
            )
            for scale in (0.5, 2.0):
                scale_matrix = (
                    (scale, 0.0, 0.0), (0.0, scale, 0.0), (0.0, 0.0, scale)
                )
                probe_energy[f"scale_{scale.hex()}"] = finite_graph_energy(
                    family, transform_float(reference, scale_matrix),
                    transform_float(current, scale_matrix), configuration.edges,
                )
            for invariant_probe in (
                "packet_reverse", "packet_splitmix", "relation_reverse",
                "relation_splitmix", "relation_endpoint_reverse",
                "id_reverse", "id_cycle", "id_sha256",
            ):
                # These transformations alter labels/order/orientation only.
                # The independent evaluator is label-free, so its semantic
                # value is the same baseline rather than a producer premise.
                probe_energy[invariant_probe] = baseline
            for probe in probes:
                row = keyed[(identifier, family, probe)]
                reported_baseline = binary64(row["baseline_energy"], f"{identifier} baseline")
                reported_probe = binary64(row["probe_energy"], f"{identifier} probe energy")
                expected_ratio = 0.25 if probe.endswith("p-1") else 4.0 if probe.endswith("p+1") else 1.0
                actual_ratio = (
                    expected_ratio if baseline == 0.0 and probe_energy[probe] == 0.0
                    else probe_energy[probe] / baseline
                )
                reported_expected = binary64(row["expected_ratio"], f"{identifier} expected ratio")
                reported_actual = binary64(row["actual_ratio"], f"{identifier} actual ratio")
                residual = abs(reported_actual - reported_expected)
                reported_residual = binary64(row["residual"], f"{identifier} residual")
                reported_gate = binary64(row["tolerance"], f"{identifier} metamorphic gate")
                dimension = max(6, 3 * len(configuration.packet_ids), len(configuration.edges))
                gate = 32768.0 * dimension * EPSILON64 * max(
                    1.0, abs(reported_actual), abs(expected_ratio)
                )
                energy_gate = 65536.0 * dimension * EPSILON64 * max(
                    1.0, abs(baseline), abs(probe_energy[probe])
                )
                audit.require(abs(reported_baseline - baseline) <= energy_gate,
                              f"{identifier}/{family}/{probe}: independent baseline")
                audit.require(abs(reported_probe - probe_energy[probe]) <= energy_gate,
                              f"{identifier}/{family}/{probe}: independent probe energy")
                audit.require(reported_expected == expected_ratio,
                              f"{identifier}/{family}/{probe}: expected scale law")
                audit.require(abs(reported_actual - actual_ratio) <= gate,
                              f"{identifier}/{family}/{probe}: independent ratio")
                audit.require(abs(reported_residual - residual) <= gate * EPSILON64 * 8,
                              f"{identifier}/{family}/{probe}: residual arithmetic")
                audit.require(abs(reported_gate - gate) <= gate * EPSILON64 * 8,
                              f"{identifier}/{family}/{probe}: tolerance arithmetic")
                passed = reported_residual <= reported_gate
                audit.require(boolean(row["pass"], f"{identifier} metamorphic pass") == passed,
                              f"{identifier}/{family}/{probe}: pass flag")
                failures += int(not passed)
    return failures


def parse_checkpoint(
    path: pathlib.Path, configuration: Configuration, row: Mapping[str, str], audit: Audit
) -> bool:
    payload = path.read_bytes()
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
    support = Decimal.from_float(take("<d", "support"))
    expected_support = max(
        euclidean_distance(configuration.positions, first, second)
        for first, second in configuration.edges
    )
    support_gate = (
        Decimal(32768)
        * Decimal(max(6, 3 * len(configuration.packet_ids), len(configuration.edges)))
        * Decimal.from_float(EPSILON64)
        * max(Decimal(1), abs(support), abs(expected_support))
    )
    close_decimal(
        audit, support, expected_support, support_gate,
        f"{path.name}: independently reconstructed support radius",
    )
    audit.require(take("<Q", "packet count") == len(configuration.packet_ids),
                  f"{path.name}: packet count")
    for packet_id, mass in zip(configuration.packet_ids, configuration.masses, strict=True):
        audit.require(take("<Q", "packet ID") == packet_id, f"{path.name}: packet ID")
        audit.require(take("<q", "packet mass") == mass, f"{path.name}: mass")
        state = take("<6d", "packet state")
        expected = (*configuration.positions_float[packet_id], 0.0, 0.0, 0.0)
        audit.require(state == expected, f"{path.name}: packet state binding")
    audit.require(take("<Q", "bond count") == len(configuration.edges),
                  f"{path.name}: bond count")
    observed = tuple(
        (take("<Q", "bond first"), take("<Q", "bond second"))
        for _edge in configuration.edges
    )
    audit.require(observed == configuration.edges, f"{path.name}: topology binding")
    audit.require(take("<Q", "volume count") == 0, f"{path.name}: volume state forbidden")
    audit.require(offset == len(payload), f"{path.name}: trailing bytes")
    digest = hashlib.sha256(payload).hexdigest()
    exact = (
        unsigned(row["byte_count"], f"{path.name} byte count") == len(payload)
        and sha256_text(row["sha256_before"], f"{path.name} before") == digest
        and sha256_text(row["sha256_roundtrip"], f"{path.name} roundtrip") == digest
        and boolean(row["roundtrip_exact"], f"{path.name} exact")
        and boolean(row["diagnostics_read_only"], f"{path.name} read only")
    )
    audit.require(boolean(row["pass"], f"{path.name} pass") == exact,
                  f"{path.name}: checkpoint pass")
    return exact


def validate_checkpoints(
    root: pathlib.Path,
    configurations: Mapping[str, Configuration],
    rows: Sequence[Mapping[str, str]],
    audit: Audit,
) -> int:
    keyed = {row["configuration_id"]: row for row in rows}
    audit.require(len(keyed) == len(rows), "duplicate checkpoint row")
    audit.require(set(keyed) == set(configurations), "checkpoint inventory")
    failures = 0
    for identifier, configuration in configurations.items():
        exact = parse_checkpoint(
            root / "checkpoints" / f"{identifier}.bin", configuration, keyed[identifier], audit
        )
        failures += int(not exact)
    return failures


def validate_provenance(
    value: Mapping[str, Any],
    smoke: bool,
    allow_dirty: bool,
    expected_source_branch: str,
    audit: Audit,
) -> None:
    require_fields(
        value,
        {
            "parent_sha", "exact_oracle_pre_hash", "source_sha", "source_branch",
            "expected_branch", "source_dirty", "compiler_id", "compiler_version",
            "smoke", "inherited_blobs", "fixture_sha256",
        },
        "provenance",
    )
    audit.require(value["parent_sha"] == PARENT_SHA, "provenance parent SHA")
    audit.require(
        value["exact_oracle_pre_hash"]
        == "463fd3f58c5ab5693207ed1a127300434bd76f6d03074f7217fd50e5511ad3d2",
        "provenance exact-oracle binding",
    )
    audit.require(
        isinstance(value["source_sha"], str)
        and SOURCE_SHA_RE.fullmatch(value["source_sha"]) is not None,
        "provenance source SHA",
    )
    audit.require(value["source_branch"] == expected_source_branch,
                  "provenance source branch")
    audit.require(value["expected_branch"] == BRANCH, "provenance expected branch")
    audit.require(isinstance(value["source_dirty"], bool), "provenance dirty type")
    audit.require(allow_dirty or value["source_dirty"] is False,
                  "provenance source must be clean")
    audit.require(value["smoke"] is smoke, "provenance smoke binding")
    audit.require(
        isinstance(value["compiler_id"], str) and bool(value["compiler_id"])
        and isinstance(value["compiler_version"], str) and bool(value["compiler_version"]),
        "provenance compiler",
    )
    audit.require(value["inherited_blobs"] == INHERITED_BLOBS,
                  "provenance inherited blob identities")
    expected_fixture = (
        {name: "builtin_smoke" for name in FIXTURE_HASHES}
        if smoke else FIXTURE_HASHES
    )
    audit.require(value["fixture_sha256"] == expected_fixture,
                  "provenance fixture hashes")


def validate_summary(
    value: Mapping[str, Any],
    smoke: bool,
    row_counts: Mapping[str, int],
    failure_counts: Mapping[str, int],
    audit: Audit,
) -> None:
    require_fields(
        value,
        {
            "schema", "seed", "smoke", "decision", "no_promotion",
            "candidate_b_decision_inputs", "candidate_d_decision_inputs",
            "dense_global_rows", "bulk_rows", "bulk_failures", "graph_rows",
            "graph_failures", "metamorphic_rows", "metamorphic_failures",
            "checkpoint_rows", "checkpoint_failures", "prohibited_features",
        },
        "summary",
    )
    audit.require(value["schema"] == SUMMARY_SCHEMA, "summary schema")
    audit.require(value["seed"] == SEED, "summary seed")
    audit.require(value["smoke"] is smoke, "summary smoke")
    audit.require(value["no_promotion"] is True, "summary NO PROMOTION")
    audit.require(value["candidate_b_decision_inputs"] == 0,
                  "Candidate B excluded")
    audit.require(value["candidate_d_decision_inputs"] == 0,
                  "Candidate D excluded")
    audit.require(value["dense_global_rows"] == 0, "dense global H excluded")
    expected_prohibited = {
        "motion_integration": False,
        "runtime_force_application": False,
        "stress": False,
        "contact": False,
        "damage_or_fracture": False,
        "gravity": False,
        "chemistry": False,
        "organisms": False,
        "rendering": False,
        "gpu": False,
    }
    audit.require(value["prohibited_features"] == expected_prohibited,
                  "summary prohibited-feature boundary")
    for family in ("bulk", "graph", "metamorphic", "checkpoint"):
        audit.require(value[f"{family}_rows"] == row_counts[family],
                      f"summary {family} row count")
        audit.require(value[f"{family}_failures"] == failure_counts[family],
                      f"summary {family} failure count")
    independent_decision = (
        DECISION if sum(failure_counts.values()) == 0 else STOP_DECISION
    )
    audit.require(value["decision"] == independent_decision,
                  "independently re-derived decision order")


def validate_bundle(
    root: pathlib.Path,
    *,
    allow_dirty: bool,
    expected_source_branch: str,
) -> tuple[int, dict[str, Any], int]:
    audit = Audit()
    audit.require(root.is_dir(), "bundle directory missing")
    summary = read_json(root / "summary.json")
    smoke = summary.get("smoke")
    audit.require(isinstance(smoke, bool), "summary smoke type")
    expected_ids = SMOKE_IDS if smoke else FULL_IDS
    tables = {
        name: read_csv(root / name)
        for name in HEADERS
    }
    configurations = parse_configurations(
        tables["packets.csv"], tables["relations.csv"], expected_ids, audit
    )
    validate_configuration_metadata(
        tables["configurations.csv"], configurations, audit
    )
    validate_manifest(root, expected_ids, audit)
    provenance = read_json(root / "provenance.json")
    validate_provenance(
        provenance, smoke, allow_dirty, expected_source_branch, audit
    )
    bulk_failures = validate_bulk_controls(
        tables["bulk_expressivity.csv"], tables["tangent.csv"],
        tables["strain_energy.csv"], audit,
    )
    graph_failures, high_precision_receipts = validate_graph_controls(
        configurations, tables["graph_energy.csv"], tables["spectra.csv"], audit
    )
    metamorphic_failures = validate_metamorphic(
        configurations, tables["metamorphic.csv"], audit
    )
    checkpoint_failures = validate_checkpoints(
        root, configurations, tables["checkpoints.csv"], audit
    )
    row_counts = {
        "bulk": len(tables["bulk_expressivity.csv"]),
        "graph": len(tables["graph_energy.csv"]),
        "metamorphic": len(tables["metamorphic.csv"]),
        "checkpoint": len(tables["checkpoints.csv"]),
    }
    failure_counts = {
        "bulk": bulk_failures,
        "graph": graph_failures,
        "metamorphic": metamorphic_failures,
        "checkpoint": checkpoint_failures,
    }
    validate_summary(summary, smoke, row_counts, failure_counts, audit)
    return audit.checks, summary, high_precision_receipts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=pathlib.Path, required=True)
    parser.add_argument("--compare", type=pathlib.Path)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--expected-source-branch", default=BRANCH)
    args = parser.parse_args()
    try:
        checks, summary, spectra = validate_bundle(
            args.bundle,
            allow_dirty=args.allow_dirty,
            expected_source_branch=args.expected_source_branch,
        )
        if args.compare is not None:
            other_checks, other_summary, other_spectra = validate_bundle(
                args.compare,
                allow_dirty=args.allow_dirty,
                expected_source_branch=args.expected_source_branch,
            )
            checks += other_checks
            spectra += other_spectra
            if canonical_tree(args.bundle) != canonical_tree(args.compare):
                reject("twin bundles are not byte-for-byte identical")
            if summary != other_summary:
                reject("twin summaries differ")
            print("byte comparison: PASS")
        print(
            "CONSTITUTIVE EXPRESSIVITY BUNDLE VALID: "
            f"{checks} checks; high_precision_spectra={spectra}; "
            f"decision={summary['decision']}; NO_PROMOTION"
        )
        return 0
    except (OSError, ValidationError, KeyError, ValueError, ArithmeticError) as error:
        print(f"CONSTITUTIVE EXPRESSIVITY BUNDLE INVALID: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
