#!/usr/bin/env python3
"""Independent validator for Conservative Force Consistency evidence.

The validator reconstructs the frozen symmetric relation operator, finite
energy, analytic gradient, balances, power, reference and finite tangents,
objectivity/scaling comparisons, and the noncoincident collapse path from the
closed exported tables.  It never imports or calls the C++ force evaluator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import pathlib
import platform
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal as D
from decimal import localcontext
from fractions import Fraction
from typing import Any, Iterable, Mapping, NoReturn, Sequence

from conservative_force_oracle import (
    build_local_collective_h,
    CoincidentRelationError,
    RelationModel,
    cross,
    directional_derivative,
    dtext,
    dot,
    evaluate,
    extrapolate_polynomial_at_zero,
    flatten,
    force_vector,
    matmul,
    matvec,
    max_abs,
    norm,
    numerical_force_jacobian,
    rigidity,
    shifted,
    tangent_decomposition,
    total_force,
    total_torque,
    transpose,
    unflatten,
    vsub,
)


DIGITS = 100
EPSILON64 = D(2) ** -52
TINY64 = D.from_float(float.fromhex("0x1.0000000000000p-1022"))
SEED = 260828
PARENT_SHA = "2de8843faf76a75d16b3a3012897e719291c52cf"
PARENT_EVIDENCE = "constitutive-expressivity-lab-evidence-v1"
BRANCH = "conservative-force-consistency-lab"
SUMMARY_SCHEMA = "mls.conservative-force-consistency.summary.v1"
PROVENANCE_SCHEMA = "mls.conservative-force-consistency.provenance.v1"
MANIFEST_SCHEMA = "mls.conservative-force-consistency.manifest.v1"
RAW_SUMMARY_SCHEMA = "mls.conservative-force-consistency.raw-summary.v1"
RAW_PROVENANCE_SCHEMA = "mls.conservative-force-consistency.raw-provenance.v1"
RAW_MANIFEST_SCHEMA = "mls.conservative-force-consistency.raw-manifest.v1"
PREREGISTRATION_COMMIT = "3b84f6cbb685aed9895a8954e9bcd53a41caa790"
PARENT_OUTER_PRE_HASH = "5382848fab2c84b7fad4eb43647e368c492cd245d27c10f552c01edffdc0842c"
PARENT_ARCHIVE_SHA256 = "1bc4dccee877cd4a3d4ee05df7d3aab00d4643b400186a6a5ef5447b6cbb1123"
PARENT_BUNDLE_MANIFEST_PRE_HASH = "18b1af6837f2c67204094498eedd2a8d8eabaf315ebae1d58c4b2073b778973f"
PARENT_TABLE_SHA256 = {
    "configurations.csv": "45d162381ec723dd9ce744f2cc23c4d21435a52b7c7e60a182073ee19a08d60e",
    "packets.csv": "843c9cb22c0b55e07c207135125a8334b0dd170a0f708aa1fb50f34d4c5d7363",
    "relations.csv": "0b2e21dcbf26454af316bec9323627aa1488ebc7aa1f14c006bfb41a231e0e6f",
    "graph_energy.csv": "c1173a8c167d3076a6e8afcb756e539020a8a12fb2e49bb11af3205f0613d874",
    "provenance.json": "396e3273159d833ae59669e71ca5b5543e30d8c088c617aa102d5abf1508f414",
}
SYMMETRIC_FREEZE_CONTRACT = "binary64_pair_average_mirrored_v1"
DECISION = "retain_conservative_relational_force_for_research"
DEGENERACY_DECISION = "retain_force_but_block_dynamics_on_degeneracy"
ALLOWED_DECISIONS = {
    DECISION,
    DEGENERACY_DECISION,
    "stop_inconclusive_or_implementation_failure",
    "reject_force_implementation",
    "reject_force_conservation",
    "reject_finite_force_consistency",
}
SOURCE_SHA_RE = re.compile(r"[0-9a-f]{40}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
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
HP_IDS = {
    "exact.tetrahedron_k4",
    "exact.octahedron_graph",
    "base.jitter27.r180.original",
}
RATIOS = {"1/3": D(1) / D(3), "2": D(2), "10": D(10)}
INHERITED_BLOBS = {
    "include/mls/constitutive_expressivity_lab.hpp": "ba5743419cd956d9bc77b979ea3ec803cd5c4547",
    "src/constitutive_expressivity_lab.cpp": "1186bc643b8677ca8d72dba4347e26d5d07e8031",
    "apps/constitutive_expressivity_diagnostic.cpp": "ed6fd9eb0704262ca041c30fe8e091e4923028a6",
    "docs/constitutive-expressivity-preregistration.md": "4afa56de497035338b1c9b9299740b2691f471c3",
}

RAW_BASE_FILES = {
    "raw_summary.json",
    "raw_provenance.json",
    "configurations.csv",
    "reference_packets.csv",
    "relations.csv",
    "operators.csv",
    "h_matrix.csv",
    "current_packets.csv",
    "force_evaluations.csv",
    "relation_forces.csv",
    "packet_forces.csv",
    "reference_tangent.csv",
    "finite_tangent.csv",
    "metamorphic.csv",
    "compression.csv",
}

FINAL_ROOT_FILES = {
    "summary.json",
    "provenance.json",
    "independent_directional_derivatives.csv",
    "independent_finite_tangent.csv",
}

HEADERS = {
    "configurations.csv": (
        "configuration_id", "parent_source_id", "role", "packet_count", "relation_count",
    ),
    "reference_packets.csv": (
        "configuration_id", "packet_index", "packet_id", "semantic_packet_id",
        "mass_quanta", "x_m", "y_m", "z_m",
    ),
    "relations.csv": (
        "configuration_id", "relation_index", "first_id", "second_id",
        "semantic_first_id", "semantic_second_id", "reference_length_m", "weight",
    ),
    "operators.csv": (
        "operator_id", "configuration_id", "family", "target_k_over_g",
        "a_j_per_m2", "b_j_per_m2",
    ),
    "h_matrix.csv": (
        "operator_id", "row_relation_index", "column_relation_index",
        "parent_value_j_per_m2", "frozen_value_j_per_m2", "correction_j_per_m2",
    ),
    "current_packets.csv": (
        "evaluation_id", "packet_index", "packet_id", "semantic_packet_id",
        "x_m", "y_m", "z_m", "vx_m_per_s", "vy_m_per_s", "vz_m_per_s",
    ),
    "force_evaluations.csv": (
        "evaluation_id", "operator_id", "probe", "velocity_probe", "status", "energy_j",
        "extension_power_w", "negative_force_power_w", "power_residual_w",
        "total_force_x_n", "total_force_y_n", "total_force_z_n",
        "total_torque_origin_x_nm", "total_torque_origin_y_nm", "total_torque_origin_z_nm",
        "total_torque_shifted_x_nm", "total_torque_shifted_y_nm", "total_torque_shifted_z_nm",
        "balance_scale_force_n", "balance_scale_torque_nm", "balance_scale_power_w",
        "tolerance_force_n", "tolerance_torque_nm", "tolerance_power_w", "pass",
    ),
    "relation_forces.csv": (
        "evaluation_id", "relation_index", "first_id", "second_id", "reference_length_m",
        "current_length_m", "extension_m", "conjugate_force_n", "direction_x", "direction_y",
        "direction_z",
    ),
    "packet_forces.csv": (
        "evaluation_id", "packet_index", "packet_id", "semantic_packet_id",
        "force_x_n", "force_y_n", "force_z_n",
    ),
    "independent_directional_derivatives.csv": (
        "evaluation_id", "direction_id", "direction_kind", "step_index", "h_over_l", "h_m",
        "analytic_derivative_n", "cpp_analytic_derivative_n", "cpp_gradient_residual_n",
        "centered_decimal_derivative_n", "raw_residual_n",
        "extrapolated_decimal_derivative_n", "extrapolated_residual_n",
        "relative_tolerance", "absolute_tolerance_n", "decimal_digits", "raw_converged", "pass",
    ),
    "reference_tangent.csv": (
        "operator_id", "evaluation_id", "direction_id", "direction_kind", "epsilon_index",
        "epsilon_over_l", "epsilon_m", "error_infinity_scaled", "observed_order",
        "minimum_relative_error", "three_consecutive_decreases", "median_order", "pass",
    ),
    "finite_tangent.csv": (
        "evaluation_id", "row_dof", "column_dof", "row_semantic_packet_id", "row_axis",
        "column_semantic_packet_id", "column_axis", "step_index", "h_over_l",
        "material_n_per_m", "geometric_n_per_m", "total_energy_hessian_n_per_m",
        "force_jacobian_n_per_m", "raw_binary64_force_jacobian_n_per_m",
        "raw_gradient_residual_n_per_m", "decomposition_residual_n_per_m",
        "symmetry_residual_n_per_m", "tolerance_n_per_m", "pass",
    ),
    "independent_finite_tangent.csv": (
        "evaluation_id", "row_dof", "column_dof", "row_semantic_packet_id", "row_axis",
        "column_semantic_packet_id", "column_axis", "step_index", "h_over_l",
        "material_n_per_m", "geometric_n_per_m", "total_energy_hessian_n_per_m",
        "force_jacobian_n_per_m", "raw_independent_force_jacobian_n_per_m",
        "raw_gradient_residual_n_per_m", "independent_extrapolated_force_jacobian_n_per_m",
        "decomposition_residual_n_per_m", "gradient_residual_n_per_m",
        "symmetry_residual_n_per_m", "tolerance_n_per_m", "pass",
    ),
    "metamorphic.csv": (
        "baseline_evaluation_id", "probe_evaluation_id", "probe", "packet_coordinate_map",
        "relation_coordinate_map", "transformed_h_sha256", "scale", "expected_energy_ratio", "actual_energy_ratio",
        "energy_residual_j", "force_covariance_residual_n", "tangent_covariance_residual_n_per_m",
        "relation_conjugate_residual_n", "energy_tolerance_j", "force_tolerance_n",
        "tangent_tolerance_n_per_m", "conjugate_tolerance_n", "scaling_ratio_tolerance", "pass",
    ),
    "compression.csv": (
        "operator_id", "evaluation_id", "relation_index", "length_ratio",
        "registered_domain_row", "status", "minimum_length_m", "force_norm_n",
        "material_tangent_norm_n_per_m", "geometric_tangent_norm_n_per_m",
        "total_tangent_norm_n_per_m", "condition_estimate", "binary64_gradient_error_n",
        "ulp_coordinate_sensitivity_n", "adjacent_length_resolved", "pass",
    ),
}


class ValidationError(RuntimeError):
    pass


def reject(message: str) -> NoReturn:
    raise ValidationError(message)


@dataclass
class Audit:
    checks: int = 0

    def require(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            reject(message)


@dataclass
class ScientificFindings:
    inconclusive_failures: int = 0
    inconclusive_reasons: list[str] = field(default_factory=list)
    energy_gradient_failures: int = 0
    force_conservation_failures: int = 0
    finite_consistency_failures: int = 0
    degeneracy_failures: int = 0
    producer_failure_rows: int = 0

    def inconclusive(self, condition: bool, reason: str) -> bool:
        if not condition:
            self.inconclusive_failures += 1
            if reason not in self.inconclusive_reasons:
                self.inconclusive_reasons.append(reason)
        return condition

    def energy(self, condition: bool) -> bool:
        if not condition:
            self.energy_gradient_failures += 1
        return condition

    def conservation(self, condition: bool) -> bool:
        if not condition:
            self.force_conservation_failures += 1
        return condition

    def finite(self, condition: bool) -> bool:
        if not condition:
            self.finite_consistency_failures += 1
        return condition

    def degeneracy(self, condition: bool) -> bool:
        if not condition:
            self.degeneracy_failures += 1
        return condition

    def decision(self) -> str:
        if self.inconclusive_failures:
            return "stop_inconclusive_or_implementation_failure"
        if self.energy_gradient_failures:
            return "reject_force_implementation"
        if self.force_conservation_failures:
            return "reject_force_conservation"
        if self.finite_consistency_failures:
            return "reject_finite_force_consistency"
        if self.degeneracy_failures:
            return DEGENERACY_DECISION
        return DECISION


def within(actual: D, expected: D, tolerance: D) -> bool:
    return abs(actual - expected) <= tolerance


@dataclass(frozen=True)
class Configuration:
    identifier: str
    role: str
    packet_ids: tuple[int, ...]
    semantic_ids: tuple[int, ...]
    actual_to_semantic: Mapping[int, int]
    reference: Mapping[int, tuple[D, D, D]]
    relations: tuple[tuple[int, int], ...]
    actual_relations: tuple[tuple[int, int], ...]
    lengths: tuple[D, ...]
    weights: tuple[D, ...]


@dataclass(frozen=True)
class Operator:
    identifier: str
    configuration_id: str
    ratio_text: str
    ratio: D
    a: D
    b: D
    parent_h: tuple[tuple[D, ...], ...]
    frozen_h: tuple[tuple[D, ...], ...]


def require_fields(value: Mapping[str, Any], expected: set[str], where: str) -> None:
    if set(value) != expected:
        reject(f"{where}: closed-field mismatch {sorted(set(value) ^ expected)}")


def read_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"cannot read {path.name}: {error}") from error
    if not isinstance(value, dict):
        reject(f"{path.name}: root must be an object")
    return value


def read_csv(path: pathlib.Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != HEADERS[path.name]:
                reject(f"{path.name}: header mismatch")
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        raise ValidationError(f"cannot read {path.name}: {error}") from error
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        reject(f"{path.name}: malformed CSV width")
    return rows


def unsigned(value: str, where: str) -> int:
    if not value or not value.isascii() or not value.isdigit() or (len(value) > 1 and value[0] == "0"):
        reject(f"{where}: noncanonical unsigned integer")
    return int(value)


def boolean(value: str, where: str) -> bool:
    if value not in {"true", "false"}:
        reject(f"{where}: invalid boolean")
    return value == "true"


def binary64(value: str, where: str) -> float:
    try:
        result = float.fromhex(value)
    except ValueError as error:
        raise ValidationError(f"{where}: invalid binary64") from error
    if not math.isfinite(result) or result.hex() != value:
        reject(f"{where}: noncanonical/nonfinite binary64")
    if result == 0 and math.copysign(1.0, result) < 0:
        reject(f"{where}: negative zero")
    return result


def decimal64(value: str, where: str) -> D:
    return D.from_float(binary64(value, where))


def decimal_text(value: str, where: str) -> D:
    try:
        result = D(value)
    except ArithmeticError as error:
        raise ValidationError(f"{where}: invalid decimal") from error
    if not result.is_finite() or value != format(result.normalize(), "E") and not (result == 0 and value == "0"):
        reject(f"{where}: noncanonical decimal")
    return result


def close(actual: D, expected: D, tolerance: D, where: str, audit: Audit) -> None:
    audit.require(abs(actual - expected) <= tolerance, where)


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


def validate_manifest(
    root: pathlib.Path, expected_files: set[str], schema: str, audit: Audit
) -> None:
    manifest = read_json(root / "manifest.json")
    require_fields(manifest, {"schema", "file_sha256", "pre_hash_sha256"}, "manifest")
    audit.require(manifest["schema"] == schema, "manifest schema")
    hashes = manifest["file_sha256"]
    audit.require(isinstance(hashes, dict), "manifest hashes object")
    audit.require(set(hashes) == expected_files, "manifest closed payload inventory")
    tree = canonical_tree(root)
    audit.require(set(tree) == expected_files | {"manifest.json"}, "closed bundle inventory")
    for name in sorted(expected_files):
        claimed = hashes[name]
        audit.require(isinstance(claimed, str) and SHA256_RE.fullmatch(claimed) is not None, f"manifest hash {name}")
        audit.require(tree[name] == claimed, f"manifest digest {name}")
    expected = hashlib.sha256(manifest_preimage(hashes)).hexdigest()
    audit.require(manifest["pre_hash_sha256"] == expected, "manifest pre-hash")


def parse_map(value: str, where: str) -> dict[int, int]:
    result: dict[int, int] = {}
    for entry in value.split(";"):
        parts = entry.split(":")
        if len(parts) != 2:
            reject(f"{where}: malformed coordinate map")
        first = unsigned(parts[0], where)
        second = unsigned(parts[1], where)
        if first in result:
            reject(f"{where}: duplicate coordinate source")
        result[first] = second
    audit_values = list(result)
    if audit_values != sorted(audit_values) or len(set(result.values())) != len(result):
        reject(f"{where}: map must be canonical bijection")
    return result


def canonical_binary64_hex(value: D) -> str:
    result = float(value)
    return "0x0.0p+0" if result == 0.0 else result.hex()


def metamorphic_h_sha256(matrix: Sequence[Sequence[D]]) -> str:
    lines = [
        "mls.conservative-force-consistency.metamorphic-h.v1",
        f"dimension={len(matrix)}",
    ]
    lines.extend(
        canonical_binary64_hex(value)
        for matrix_row in matrix
        for value in matrix_row
    )
    return hashlib.sha256(("\n".join(lines) + "\n").encode("ascii")).hexdigest()


def scale_dimension(packet_count: int, relation_count: int) -> D:
    return D(max(6, 3 * packet_count, relation_count))


def arithmetic_tolerance(dimension: D, scale: D, multiplier: int) -> D:
    return D(multiplier) * dimension * EPSILON64 * max(abs(scale), TINY64)


def decimal_accumulation_tolerance(dimension: D, absolute_term_scale: D) -> D:
    """Roundoff allowance for a Decimal-100 reduction of physical terms.

    This is not a physical/numerical gate relaxation.  It prevents the
    independent Decimal implementation's final finite-precision reduction
    residue from being compared to the much smaller binary64-normal `tiny`
    floor when the exact algebraic result is zero.  The scale remains in the
    quantity's physical unit and is formed from the absolute terms being
    reduced.
    """

    return D(10) ** D(-DIGITS + 8) * dimension * max(
        abs(absolute_term_scale), TINY64
    )


def registered_raw_convergence(errors: Sequence[D], floor: D) -> bool:
    """Require each preregistered transition to improve until the floor.

    Reaching the registered absolute/relative floor may end strict ordering,
    but a later floor value cannot excuse an earlier growing transition.
    """

    if len(errors) != 4:
        reject("registered raw convergence requires four levels")
    at_floor = errors[0] <= floor
    for index in range(3):
        if at_floor:
            # Reaching the numerical floor is not a licence for a later raw
            # estimate to re-emerge above it.  The complete registered
            # sequence remains evidence even after floor arrival.
            if errors[index + 1] > floor:
                return False
            continue
        if errors[index + 1] <= floor:
            at_floor = True
            continue
        if errors[index + 1] >= errors[index]:
            return False
    return True


def converges_until_floor(errors: Sequence[D], floor: D) -> bool:
    """Arbitrary-length form of the registered no-reemergence rule."""

    if not errors:
        return False
    at_floor = errors[0] <= floor
    for previous, current in zip(errors, errors[1:]):
        if at_floor:
            if current > floor:
                return False
            continue
        if current <= floor:
            at_floor = True
            continue
        if current >= previous:
            return False
    return True


def vector_norm_decimal(value: Sequence[D]) -> D:
    return sum((entry * entry for entry in value), D(0)).sqrt()


def vector_norm64(value: Sequence[float]) -> float:
    return math.sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2])


def stable_norm64(value: Sequence[float]) -> float:
    scale = max(abs(value[0]), abs(value[1]), abs(value[2]))
    if scale == 0.0:
        return 0.0
    scaled = [entry / scale for entry in value]
    return scale * math.sqrt(
        scaled[0] * scaled[0] + scaled[1] * scaled[1] + scaled[2] * scaled[2]
    )


def round_binary_fraction(value: Fraction, precision: int) -> Fraction:
    """Round an exact rational to a normal binary significand, ties-to-even."""

    if value == 0:
        return Fraction(0)
    sign = -1 if value < 0 else 1
    value = abs(value)
    numerator = value.numerator
    denominator = value.denominator
    exponent = numerator.bit_length() - denominator.bit_length()
    if exponent >= 0:
        if numerator < (denominator << exponent):
            exponent -= 1
    elif numerator * (1 << (-exponent)) < denominator:
        exponent -= 1
    shift = exponent - precision + 1
    scaled = (
        value / Fraction(1 << shift)
        if shift >= 0
        else value * Fraction(1 << (-shift))
    )
    quotient, remainder = divmod(scaled.numerator, scaled.denominator)
    twice = 2 * remainder
    if twice > scaled.denominator or (
        twice == scaled.denominator and quotient % 2 == 1
    ):
        quotient += 1
    rounded = (
        Fraction(quotient * (1 << shift))
        if shift >= 0
        else Fraction(quotient, 1 << (-shift))
    )
    return sign * rounded


def extended_product_sum(
    products: Iterable[tuple[float, float]], precision: int
) -> float:
    """Model a finite-significand extended accumulation loop."""

    accumulated = Fraction(0)
    for lhs, rhs in products:
        lhs_fraction = Fraction(*lhs.as_integer_ratio())
        rhs_fraction = Fraction(*rhs.as_integer_ratio())
        product = round_binary_fraction(lhs_fraction * rhs_fraction, precision)
        accumulated = round_binary_fraction(accumulated + product, precision)
    return float(accumulated)


def extended_sum(values: Iterable[float], precision: int) -> float:
    accumulated = Fraction(0)
    for value in values:
        accumulated = round_binary_fraction(
            accumulated + Fraction(*value.as_integer_ratio()), precision
        )
    return float(accumulated)


@dataclass(frozen=True)
class Binary64Evaluation:
    energy: float
    lengths: tuple[float, ...]
    forces: Mapping[int, tuple[float, float, float]]


def binary64_evaluate(
    model: RelationModel,
    current_decimal: Mapping[int, tuple[D, D, D]],
    extended_precision: int = 53,
) -> Binary64Evaluation:
    current = {
        packet_id: tuple(float(value) for value in current_decimal[packet_id])
        for packet_id in model.packet_ids
    }
    h = [[float(value) for value in row] for row in model.h]
    l0 = [float(value) for value in model.reference_lengths]
    lengths: list[float] = []
    extensions: list[float] = []
    directions: list[tuple[float, float, float]] = []
    for index, (first, second) in enumerate(model.relations):
        offset = tuple(current[second][axis] - current[first][axis] for axis in range(3))
        length = stable_norm64(offset)
        if length == 0.0:
            raise CoincidentRelationError("binary64 relation coincidence")
        lengths.append(length)
        extensions.append(length - l0[index])
        directions.append(tuple(offset[axis] / length for axis in range(3)))
    conjugates = [
        extended_product_sum(
            [
                (h[row][column], extensions[column])
                for column in range(len(extensions))
            ],
            extended_precision,
        )
        for row in range(len(extensions))
    ]
    energy = 0.5 * extended_product_sum(
        [
            (extensions[index], conjugates[index])
            for index in range(len(extensions))
        ],
        extended_precision,
    )
    accumulated = {
        packet_id: [[], [], []] for packet_id in model.packet_ids
    }
    for index, (first, second) in enumerate(model.relations):
        for axis in range(3):
            relation_force = conjugates[index] * directions[index][axis]
            accumulated[first][axis].append(relation_force)
            accumulated[second][axis].append(-relation_force)
    forces = {
        packet_id: tuple(
            extended_sum(values, extended_precision)
            for values in accumulated[packet_id]
        )
        for packet_id in model.packet_ids
    }
    return Binary64Evaluation(energy, tuple(lengths), forces)  # type: ignore[arg-type]


def binary64_rigidity_matrix(
    model: RelationModel,
    current_decimal: Mapping[int, tuple[D, D, D]],
) -> list[list[float]]:
    """Reproduce the producer's ordered binary64 central rigidity matrix."""

    current = {
        packet_id: tuple(float(value) for value in current_decimal[packet_id])
        for packet_id in model.packet_ids
    }
    lookup = {packet_id: index for index, packet_id in enumerate(model.packet_ids)}
    result = [
        [0.0 for _ in range(3 * len(model.packet_ids))]
        for _ in model.relations
    ]
    for relation_index, (first, second) in enumerate(model.relations):
        offset = tuple(
            current[second][axis] - current[first][axis] for axis in range(3)
        )
        length = stable_norm64(offset)
        if length == 0.0:
            raise CoincidentRelationError("binary64 rigidity coincidence")
        direction = tuple(value / length for value in offset)
        for axis in range(3):
            result[relation_index][3 * lookup[first] + axis] = -direction[axis]
            result[relation_index][3 * lookup[second] + axis] = direction[axis]
    return result


def binary64_reference_tangent_error(
    model: RelationModel,
    current: Mapping[int, tuple[D, D, D]],
    direction: Sequence[D],
    epsilon: float,
    parent_h_scale: float,
) -> float:
    """Reproduce the raw producer's reference-tangent scalar diagnostic."""

    rigidity64 = binary64_rigidity_matrix(model, model.reference)
    h64 = [[float(value) for value in row] for row in model.h]
    relation_count = len(rigidity64)
    coordinate_count = len(rigidity64[0])
    h_times_r = [
        [0.0 for _ in range(coordinate_count)]
        for _ in range(relation_count)
    ]
    for row in range(relation_count):
        for column in range(coordinate_count):
            value = 0.0
            for inner in range(relation_count):
                value += h64[row][inner] * rigidity64[inner][column]
            h_times_r[row][column] = value
    force_jacobian = [
        [0.0 for _ in range(coordinate_count)]
        for _ in range(coordinate_count)
    ]
    for row in range(coordinate_count):
        for column in range(coordinate_count):
            value = 0.0
            for relation in range(relation_count):
                value += (
                    rigidity64[relation][row]
                    * h_times_r[relation][column]
                )
            force_jacobian[row][column] = -value
    direction64 = [float(value) for value in direction]
    target: list[float] = []
    for row in range(coordinate_count):
        value = 0.0
        for column in range(coordinate_count):
            value += force_jacobian[row][column] * direction64[column]
        target.append(value)
    evaluated = binary64_evaluate(model, current)
    actual = [
        component / epsilon
        for packet_id in model.packet_ids
        for component in evaluated.forces[packet_id]
    ]
    target_scale = max((abs(value) for value in target), default=0.0)
    denominator = max(target_scale, parent_h_scale)
    return max(
        abs(lhs - rhs) for lhs, rhs in zip(actual, target, strict=True)
    ) / denominator


def binary64_shifted_axis(
    current: Mapping[int, tuple[D, D, D]],
    packet_ids: Sequence[int],
    dof: int,
    step: float,
) -> dict[int, tuple[D, D, D]]:
    packet_index, axis = divmod(dof, 3)
    target = packet_ids[packet_index]
    result: dict[int, tuple[D, D, D]] = {}
    for packet_id in packet_ids:
        values = [float(value) for value in current[packet_id]]
        if packet_id == target:
            values[axis] = values[axis] + step
        result[packet_id] = tuple(D.from_float(value) for value in values)  # type: ignore[assignment]
    return result


def binary64_force_jacobian_entry(
    model: RelationModel,
    current: Mapping[int, tuple[D, D, D]],
    row: int,
    column: int,
    h_over_l: float,
) -> float:
    characteristic = max(float(value) for value in model.reference_lengths)
    step = h_over_l * characteristic
    plus = binary64_evaluate(
        model, binary64_shifted_axis(current, model.packet_ids, column, step)
    ).forces
    minus = binary64_evaluate(
        model, binary64_shifted_axis(current, model.packet_ids, column, -step)
    ).forces
    packet_id = model.packet_ids[row // 3]
    axis = row % 3
    numerator = plus[packet_id][axis] - minus[packet_id][axis]
    return numerator / (2.0 * step)


def binary64_force_jacobian_matrix(
    model: RelationModel,
    current: Mapping[int, tuple[D, D, D]],
    h_over_l: float,
    extended_precision: int = 53,
) -> list[list[float]]:
    size = 3 * len(model.packet_ids)
    characteristic = max(float(value) for value in model.reference_lengths)
    step = h_over_l * characteristic
    result = [[0.0 for _ in range(size)] for _ in range(size)]
    for column in range(size):
        plus = binary64_evaluate(
            model, binary64_shifted_axis(current, model.packet_ids, column, step),
            extended_precision,
        ).forces
        minus = binary64_evaluate(
            model, binary64_shifted_axis(current, model.packet_ids, column, -step),
            extended_precision,
        ).forces
        for row in range(size):
            packet_id = model.packet_ids[row // 3]
            axis = row % 3
            result[row][column] = (
                plus[packet_id][axis] - minus[packet_id][axis]
            ) / (2.0 * step)
    return result


def binary64_shifted_vector(
    current: Mapping[int, tuple[D, D, D]],
    packet_ids: Sequence[int],
    packet_id: int,
    direction: Sequence[float],
    step: float,
) -> dict[int, tuple[D, D, D]]:
    result: dict[int, tuple[D, D, D]] = {}
    for candidate in packet_ids:
        values = [float(value) for value in current[candidate]]
        if candidate == packet_id:
            values = [values[axis] + step * direction[axis] for axis in range(3)]
        result[candidate] = tuple(D.from_float(value) for value in values)  # type: ignore[assignment]
    return result


def binary64_compression_diagnostics(
    payload: EvaluationPayload,
    ratio: float,
) -> tuple[D, D, bool]:
    model = payload.model
    first, second = model.relations[0]
    reference_offset = tuple(
        float(model.reference[second][axis]) - float(model.reference[first][axis])
        for axis in range(3)
    )
    reference_length = stable_norm64(reference_offset)
    direction = tuple(value / reference_length for value in reference_offset)
    step = min(reference_length * 1.0e-8, ratio * reference_length * 0.25)
    plus_current = binary64_shifted_vector(
        payload.current, model.packet_ids, second, direction, step
    )
    minus_current = binary64_shifted_vector(
        payload.current, model.packet_ids, second, direction, -step
    )
    plus_energy = binary64_evaluate(model, plus_current).energy
    minus_energy = binary64_evaluate(model, minus_current).energy
    numeric = (plus_energy - minus_energy) / (2.0 * step)
    base = binary64_evaluate(model, payload.current)
    analytic = -sum(
        base.forces[second][axis] * direction[axis] for axis in range(3)
    )
    gradient_error = abs(numeric - analytic)

    axis = max(range(3), key=lambda index: abs(direction[index]))
    adjacent: dict[int, tuple[D, D, D]] = dict(payload.current)
    adjacent_values = [float(value) for value in payload.current[second]]
    adjacent_values[axis] = math.nextafter(
        adjacent_values[axis], math.inf if direction[axis] >= 0.0 else -math.inf
    )
    adjacent[second] = tuple(D.from_float(value) for value in adjacent_values)  # type: ignore[assignment]
    adjacent_evaluation = binary64_evaluate(model, adjacent)
    differences = [
        adjacent_evaluation.forces[packet_id][component]
        - base.forces[packet_id][component]
        for packet_id in model.packet_ids
        for component in range(3)
    ]
    sensitivity = math.sqrt(sum(value * value for value in differences))
    adjacent_resolved = adjacent_evaluation.lengths[0] != base.lengths[0]
    return D.from_float(gradient_error), D.from_float(sensitivity), adjacent_resolved


def high_precision_compression_gradient(
    payload: EvaluationPayload,
    evaluation: Any,
    first_id: int,
    second_id: int,
) -> tuple[D, D, bool]:
    """Independent Decimal-100 collapse derivative and raw convergence."""

    with localcontext() as context:
        context.prec = DIGITS
        reference_offset = vsub(
            payload.model.reference[second_id],
            payload.model.reference[first_id],
        )
        reference_direction = tuple(
            value / norm(reference_offset) for value in reference_offset
        )
        direction = [D(0)] * (3 * len(payload.model.packet_ids))
        second_index = payload.model.packet_ids.index(second_id)
        for axis in range(3):
            direction[3 * second_index + axis] = reference_direction[axis]
        analytic = -dot(force_vector(payload.model, payload.current), direction)
        min_length = min(evaluation.lengths)
        steps = [min_length * value for value in HP_STEP_RATIOS]
        raw = [
            directional_derivative(
                payload.model, payload.current, direction, step
            )
            for step in steps
        ]
        raw_residuals = [abs(value - analytic) for value in raw]
        extrapolated = extrapolate_polynomial_at_zero(
            [step * step for step in steps], raw
        )
        error = abs(extrapolated - analytic)
        allowed = max(D("1e-55"), D("1e-45") * abs(analytic))
        return error, allowed, registered_raw_convergence(
            raw_residuals, allowed
        )


def symmetric_eigenvalues_decimal(matrix: Sequence[Sequence[D]]) -> list[D]:
    """Independent high-precision cyclic Jacobi spectrum of a symmetric matrix."""

    with localcontext() as context:
        context.prec = DIGITS
        work = [[+entry for entry in row] for row in matrix]
        size = len(work)
        if size == 0:
            return []
        tolerance = D(10) ** D(-88)
        for _iteration in range(40000):
            candidates = [
                (abs(work[row][column]), row, column)
                for row in range(size)
                for column in range(row + 1, size)
            ]
            if not candidates:
                return [work[0][0]]
            magnitude, pivot, column = max(candidates)
            if magnitude <= tolerance:
                return sorted((+work[index][index] for index in range(size)))
            apq = work[pivot][column]
            tau = (work[column][column] - work[pivot][pivot]) / (D(2) * apq)
            sign = D(1) if tau >= 0 else -D(1)
            tangent = sign / (abs(tau) + (D(1) + tau * tau).sqrt())
            cosine = D(1) / (D(1) + tangent * tangent).sqrt()
            sine = tangent * cosine
            app = work[pivot][pivot]
            aqq = work[column][column]
            for index in range(size):
                if index in (pivot, column):
                    continue
                aip = work[index][pivot]
                aiq = work[index][column]
                work[index][pivot] = cosine * aip - sine * aiq
                work[pivot][index] = work[index][pivot]
                work[index][column] = sine * aip + cosine * aiq
                work[column][index] = work[index][column]
            work[pivot][pivot] = (
                cosine * cosine * app
                - D(2) * sine * cosine * apq
                + sine * sine * aqq
            )
            work[column][column] = (
                sine * sine * app
                + D(2) * sine * cosine * apq
                + cosine * cosine * aqq
            )
            work[pivot][column] = D(0)
            work[column][pivot] = D(0)
        reject("high-precision tangent eigensolver did not converge")


def independent_condition_estimate(matrix: Sequence[Sequence[D]], dimension: D) -> D | None:
    singular = sorted((abs(value) for value in symmetric_eigenvalues_decimal(matrix)), reverse=True)
    sigma_max = singular[0] if singular else D(0)
    threshold = D(512) * dimension * EPSILON64 * max(sigma_max, TINY64)
    if any(threshold / D(8) <= value <= D(8) * threshold for value in singular):
        return None
    resolved = [value for value in singular if value > D(8) * threshold]
    if not resolved:
        return None
    return sigma_max / min(resolved)


def parse_configurations(root: pathlib.Path, audit: Audit) -> dict[str, Configuration]:
    configuration_rows = read_csv(root / "configurations.csv")
    packet_rows = read_csv(root / "reference_packets.csv")
    relation_rows = read_csv(root / "relations.csv")
    by_packet: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_relation: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in packet_rows:
        by_packet[row["configuration_id"]].append(row)
    for row in relation_rows:
        by_relation[row["configuration_id"]].append(row)
    result: dict[str, Configuration] = {}
    for row in configuration_rows:
        identifier = row["configuration_id"]
        audit.require(identifier not in result, f"duplicate configuration {identifier}")
        audit.require(identifier in FULL_IDS, f"unregistered configuration {identifier}")
        audit.require(row["parent_source_id"] == identifier, f"parent source {identifier}")
        packet_count = unsigned(row["packet_count"], f"{identifier} packet count")
        relation_count = unsigned(row["relation_count"], f"{identifier} relation count")
        packets = by_packet.pop(identifier, [])
        relations = by_relation.pop(identifier, [])
        audit.require(len(packets) == packet_count, f"{identifier} packet row count")
        audit.require(len(relations) == relation_count, f"{identifier} relation row count")
        packets.sort(key=lambda entry: unsigned(entry["packet_index"], "packet index"))
        audit.require(
            [unsigned(entry["packet_index"], "packet index") for entry in packets]
            == list(range(packet_count)),
            f"{identifier} packet indices",
        )
        actual_ids = tuple(unsigned(entry["packet_id"], "packet id") for entry in packets)
        semantic_ids = tuple(
            unsigned(entry["semantic_packet_id"], "semantic packet id") for entry in packets
        )
        audit.require(len(set(actual_ids)) == packet_count, f"{identifier} actual ID bijection")
        audit.require(len(set(semantic_ids)) == packet_count, f"{identifier} semantic ID bijection")
        audit.require(
            list(actual_ids) == sorted(actual_ids)
            and list(semantic_ids) == sorted(semantic_ids),
            f"{identifier} accepted parent packet coordinate ordering",
        )
        mapping = dict(zip(actual_ids, semantic_ids, strict=True))
        reference = {
            semantic_id: (
                decimal64(entry["x_m"], f"{identifier} x"),
                decimal64(entry["y_m"], f"{identifier} y"),
                decimal64(entry["z_m"], f"{identifier} z"),
            )
            for entry, semantic_id in zip(packets, semantic_ids, strict=True)
        }
        for entry in packets:
            audit.require(unsigned(entry["mass_quanta"], "mass quanta") > 0, f"{identifier} positive mass")
        relations.sort(key=lambda entry: unsigned(entry["relation_index"], "relation index"))
        audit.require(
            [unsigned(entry["relation_index"], "relation index") for entry in relations]
            == list(range(relation_count)),
            f"{identifier} relation indices",
        )
        semantic_edges: list[tuple[int, int]] = []
        actual_edges: list[tuple[int, int]] = []
        lengths: list[D] = []
        weights: list[D] = []
        dimension = scale_dimension(packet_count, relation_count)
        for relation in relations:
            actual_edge = (
                unsigned(relation["first_id"], "relation first ID"),
                unsigned(relation["second_id"], "relation second ID"),
            )
            semantic_edge = (
                unsigned(relation["semantic_first_id"], "semantic first ID"),
                unsigned(relation["semantic_second_id"], "semantic second ID"),
            )
            audit.require(actual_edge[0] in mapping and actual_edge[1] in mapping, f"{identifier} endpoint exists")
            audit.require(
                semantic_edge == (mapping[actual_edge[0]], mapping[actual_edge[1]]),
                f"{identifier} semantic endpoint map",
            )
            audit.require(semantic_edge[0] < semantic_edge[1], f"{identifier} canonical semantic edge")
            length = decimal64(relation["reference_length_m"], f"{identifier} reference length")
            weight = decimal64(relation["weight"], f"{identifier} relation weight")
            audit.require(length > 0 and weight > 0, f"{identifier} positive relation data")
            recomputed = norm(vsub(reference[semantic_edge[1]], reference[semantic_edge[0]]))
            tolerance = arithmetic_tolerance(dimension, max(length, recomputed), 65536)
            close(recomputed, length, tolerance, f"{identifier} frozen reference length", audit)
            actual_edges.append(actual_edge)
            semantic_edges.append(semantic_edge)
            lengths.append(length)
            weights.append(weight)
        audit.require(len(set(semantic_edges)) == relation_count, f"{identifier} unique semantic relations")
        audit.require(
            semantic_edges == sorted(semantic_edges),
            f"{identifier} accepted parent relation coordinate ordering",
        )
        result[identifier] = Configuration(
            identifier,
            row["role"],
            actual_ids,
            tuple(sorted(semantic_ids)),
            mapping,
            reference,
            tuple(semantic_edges),
            tuple(actual_edges),
            tuple(lengths),
            tuple(weights),
        )
    audit.require(not by_packet and not by_relation, "orphan configuration payload")
    return result


def parse_operators(
    root: pathlib.Path,
    configurations: Mapping[str, Configuration],
    audit: Audit,
) -> dict[str, Operator]:
    rows = read_csv(root / "operators.csv")
    h_rows = read_csv(root / "h_matrix.csv")
    grouped_h: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in h_rows:
        grouped_h[row["operator_id"]].append(row)
    result: dict[str, Operator] = {}
    per_configuration: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        identifier = row["operator_id"]
        configuration_id = row["configuration_id"]
        audit.require(identifier not in result, f"duplicate operator {identifier}")
        audit.require(configuration_id in configurations, f"operator configuration {identifier}")
        audit.require(row["family"] == "local_incident_collective", f"operator family {identifier}")
        ratio_text = row["target_k_over_g"]
        audit.require(ratio_text in RATIOS, f"operator ratio {identifier}")
        ratio = RATIOS[ratio_text]
        a_value = decimal64(row["a_j_per_m2"], f"{identifier} A")
        b_value = decimal64(row["b_j_per_m2"], f"{identifier} B")
        coefficient_tolerance = arithmetic_tolerance(D(6), max(abs(a_value), abs(b_value), TINY64), 65536)
        close(a_value, D(3) * ratio / D(20), coefficient_tolerance, f"{identifier} A map", audit)
        close(b_value, D(1) / D(4), coefficient_tolerance, f"{identifier} B map", audit)
        configuration = configurations[configuration_id]
        count = len(configuration.relations)
        entries = grouped_h.pop(identifier, [])
        audit.require(len(entries) == count * count, f"{identifier} complete H")
        parent = [[D(0) for _ in range(count)] for _ in range(count)]
        frozen = [[D(0) for _ in range(count)] for _ in range(count)]
        seen: set[tuple[int, int]] = set()
        float_parent: dict[tuple[int, int], float] = {}
        float_frozen: dict[tuple[int, int], float] = {}
        float_correction: dict[tuple[int, int], float] = {}
        for entry in entries:
            row_index = unsigned(entry["row_relation_index"], "H row")
            column_index = unsigned(entry["column_relation_index"], "H column")
            audit.require(row_index < count and column_index < count, f"{identifier} H bounds")
            audit.require((row_index, column_index) not in seen, f"{identifier} duplicate H")
            seen.add((row_index, column_index))
            p_float = binary64(entry["parent_value_j_per_m2"], f"{identifier} parent H")
            f_float = binary64(entry["frozen_value_j_per_m2"], f"{identifier} frozen H")
            c_float = binary64(entry["correction_j_per_m2"], f"{identifier} correction H")
            parent[row_index][column_index] = D.from_float(p_float)
            frozen[row_index][column_index] = D.from_float(f_float)
            float_parent[row_index, column_index] = p_float
            float_frozen[row_index, column_index] = f_float
            float_correction[row_index, column_index] = c_float
        audit.require(seen == {(i, j) for i in range(count) for j in range(count)}, f"{identifier} H coordinates")
        max_parent = max((abs(value) for matrix_row in parent for value in matrix_row), default=D(0))
        correction_bound = arithmetic_tolerance(
            scale_dimension(len(configuration.packet_ids), count), max_parent, 32768
        )
        for i in range(count):
            for j in range(count):
                expected = (
                    float_parent[i, i]
                    if i == j
                    else (float_parent[i, j] + float_parent[j, i]) * 0.5
                )
                audit.require(float_frozen[i, j] == expected, f"{identifier} H symmetric freeze")
                audit.require(float_frozen[i, j] == float_frozen[j, i], f"{identifier} H mirrored bytes")
                audit.require(
                    float_correction[i, j] == float_frozen[i, j] - float_parent[i, j],
                    f"{identifier} H correction",
                )
                audit.require(
                    abs(D.from_float(float_correction[i, j])) <= correction_bound,
                    f"{identifier} H correction bound",
                )
        # Rebuild the accepted incident-star parent operator from the exported
        # reference geometry, frozen relation weights, and declared A/B
        # coefficients.  The comparison is against H_parent, never H_force;
        # the latter is separately derived by the audited symmetric freeze.
        independent_parent = build_local_collective_h(
            configuration.reference,
            configuration.relations,
            configuration.weights,
            a_value,
            b_value,
        )
        parent_scale = max(
            max_parent,
            max_abs(value for matrix_row in independent_parent for value in matrix_row),
            TINY64,
        )
        parent_arithmetic_bound = arithmetic_tolerance(
            scale_dimension(len(configuration.packet_ids), count),
            parent_scale,
            65536,
        )
        for i in range(count):
            for j in range(count):
                audit.require(
                    abs(parent[i][j] - independent_parent[i][j])
                    <= parent_arithmetic_bound,
                    f"{identifier} accepted parent H reconstruction {i},{j}",
                )
        per_configuration[configuration_id].add(ratio_text)
        result[identifier] = Operator(
            identifier,
            configuration_id,
            ratio_text,
            ratio,
            a_value,
            b_value,
            tuple(tuple(value for value in matrix_row) for matrix_row in parent),
            tuple(tuple(value for value in matrix_row) for matrix_row in frozen),
        )
    audit.require(not grouped_h, "orphan H rows")
    for configuration_id in configurations:
        audit.require(per_configuration[configuration_id] == set(RATIOS), f"{configuration_id} policy inventory")
    return result


def relation_model(
    configuration: Configuration, operator: Operator, reference_scale: D = D(1)
) -> RelationModel:
    dimension = scale_dimension(len(configuration.packet_ids), len(configuration.relations))
    tolerance = arithmetic_tolerance(
        dimension,
        max(configuration.lengths, default=TINY64),
        65536,
    )
    return RelationModel(
        configuration.semantic_ids,
        {
            packet_id: tuple(reference_scale * value for value in point)
            for packet_id, point in configuration.reference.items()
        },
        configuration.relations,
        tuple(reference_scale * value for value in configuration.lengths),
        operator.frozen_h,
        tolerance,
    )


@dataclass(frozen=True)
class EvaluationPayload:
    identifier: str
    row: Mapping[str, str]
    operator: Operator
    configuration: Configuration
    model: RelationModel
    actual_to_semantic: Mapping[int, int]
    emitted_actual_ids: tuple[int, ...]
    emitted_semantic_ids: tuple[int, ...]
    current: Mapping[int, tuple[D, D, D]]
    velocity: Mapping[int, tuple[D, D, D]]


def parse_evaluation_payloads(
    root: pathlib.Path,
    configurations: Mapping[str, Configuration],
    operators: Mapping[str, Operator],
    audit: Audit,
) -> tuple[
    dict[str, EvaluationPayload],
    dict[str, list[dict[str, str]]],
    dict[str, list[dict[str, str]]],
]:
    evaluation_rows = read_csv(root / "force_evaluations.csv")
    current_rows = read_csv(root / "current_packets.csv")
    relation_rows = read_csv(root / "relation_forces.csv")
    packet_force_rows = read_csv(root / "packet_forces.csv")
    grouped_current: dict[str, list[dict[str, str]]] = defaultdict(list)
    grouped_relations: dict[str, list[dict[str, str]]] = defaultdict(list)
    grouped_forces: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in current_rows:
        grouped_current[row["evaluation_id"]].append(row)
    for row in relation_rows:
        grouped_relations[row["evaluation_id"]].append(row)
    for row in packet_force_rows:
        grouped_forces[row["evaluation_id"]].append(row)
    result: dict[str, EvaluationPayload] = {}
    for row in evaluation_rows:
        identifier = row["evaluation_id"]
        operator_id = row["operator_id"]
        audit.require(identifier not in result, f"duplicate evaluation {identifier}")
        audit.require(operator_id in operators, f"evaluation operator {identifier}")
        operator = operators[operator_id]
        configuration = configurations[operator.configuration_id]
        packets = grouped_current.pop(identifier, [])
        packet_count = len(configuration.packet_ids)
        audit.require(len(packets) == packet_count, f"{identifier} current packet count")
        packets.sort(key=lambda entry: unsigned(entry["packet_index"], "current packet index"))
        audit.require(
            [unsigned(entry["packet_index"], "current packet index") for entry in packets]
            == list(range(packet_count)),
            f"{identifier} current packet indices",
        )
        actual_ids = [unsigned(entry["packet_id"], "current packet ID") for entry in packets]
        semantic_ids = [
            unsigned(entry["semantic_packet_id"], "current semantic ID") for entry in packets
        ]
        audit.require(len(set(actual_ids)) == packet_count, f"{identifier} actual ID bijection")
        audit.require(set(semantic_ids) == set(configuration.semantic_ids), f"{identifier} semantic ID bijection")
        mapping = dict(zip(actual_ids, semantic_ids, strict=True))
        current = {
            semantic_id: (
                decimal64(entry["x_m"], f"{identifier} current x"),
                decimal64(entry["y_m"], f"{identifier} current y"),
                decimal64(entry["z_m"], f"{identifier} current z"),
            )
            for entry, semantic_id in zip(packets, semantic_ids, strict=True)
        }
        velocity = {
            semantic_id: (
                decimal64(entry["vx_m_per_s"], f"{identifier} velocity x"),
                decimal64(entry["vy_m_per_s"], f"{identifier} velocity y"),
                decimal64(entry["vz_m_per_s"], f"{identifier} velocity z"),
            )
            for entry, semantic_id in zip(packets, semantic_ids, strict=True)
        }
        reference_scale = (
            D("0.5") if row["probe"] == "similarity_half"
            else D(2) if row["probe"] == "similarity_two"
            else D(1)
        )
        result[identifier] = EvaluationPayload(
            identifier,
            row,
            operator,
            configuration,
            relation_model(configuration, operator, reference_scale),
            mapping,
            tuple(actual_ids),
            tuple(semantic_ids),
            current,
            velocity,
        )
    audit.require(not grouped_current, "orphan current packet rows")
    return result, grouped_relations, grouped_forces


def vector3_from_row(row: Mapping[str, str], names: Sequence[str], where: str) -> tuple[D, D, D]:
    return tuple(decimal64(row[name], f"{where} {name}") for name in names)  # type: ignore[return-value]


def validate_force_evaluations(
    payloads: Mapping[str, EvaluationPayload],
    relation_rows: Mapping[str, list[dict[str, str]]],
    packet_force_rows: Mapping[str, list[dict[str, str]]],
    audit: Audit,
    findings: ScientificFindings,
) -> tuple[int, int]:
    valid_count = 0
    coincident_count = 0
    for identifier, payload in payloads.items():
        row = payload.row
        status = row["status"]
        relations = list(relation_rows.get(identifier, []))
        forces = list(packet_force_rows.get(identifier, []))
        if status == "coincident_relation":
            coincident_count += 1
            audit.require(not relations and not forces, f"{identifier} coincidence partial force output")
            physical_fields = (
                "energy_j", "extension_power_w", "negative_force_power_w", "power_residual_w",
                "total_force_x_n", "total_force_y_n", "total_force_z_n",
                "total_torque_origin_x_nm", "total_torque_origin_y_nm", "total_torque_origin_z_nm",
                "total_torque_shifted_x_nm", "total_torque_shifted_y_nm", "total_torque_shifted_z_nm",
                "balance_scale_force_n", "balance_scale_torque_nm", "balance_scale_power_w",
                "tolerance_force_n", "tolerance_torque_nm", "tolerance_power_w",
            )
            audit.require(
                all(row[name] == "not_emitted" for name in physical_fields),
                f"{identifier} coincidence physical fields",
            )
            try:
                evaluate(payload.model, payload.current)
            except CoincidentRelationError:
                pass
            else:
                reject(f"{identifier} false coincidence status")
            audit.require(boolean(row["pass"], f"{identifier} pass"), f"{identifier} coincidence gate")
            continue
        audit.require(status == "valid_noncoincident", f"{identifier} domain status")
        valid_count += 1
        with localcontext() as context:
            context.prec = DIGITS
            shifted_origin = (
                D(7) / D(13),
                -D(5) / D(11),
                D(3) / D(17),
            )
            energy_gate = True
            conservation_gate = True
            expected = evaluate(payload.model, payload.current)
            dimension = scale_dimension(
                len(payload.configuration.packet_ids), len(payload.configuration.relations)
            )
            is_reference = row["probe"] == "reference"
            h_scale = max_abs(
                value for matrix_row in payload.operator.parent_h for value in matrix_row
            )
            length_scale = max(payload.model.reference_lengths)
            reference_length_bound = arithmetic_tolerance(
                dimension, length_scale, 65536
            )
            reference_force_bound = arithmetic_tolerance(
                dimension, h_scale * length_scale, 65536
            )
            reference_energy_bound = max(
                TINY64,
                reference_force_bound * reference_length_bound * dimension,
            )
            energy_value = decimal64(row["energy_j"], f"{identifier} energy")
            # Frozen binary64 reference lengths need not equal the exact
            # Decimal norm of the exported binary64 coordinates.  Carry the
            # declared representation-roundoff bound through every state;
            # this matters especially for a deformation that is exactly the
            # reference geometry but has a non-`reference` probe label.
            representation_energy_bound = reference_force_bound * dimension * (
                max_abs(expected.extensions) + reference_length_bound
            )
            energy_tolerance = max(
                reference_energy_bound if is_reference else D(0),
                representation_energy_bound,
                arithmetic_tolerance(
                    dimension,
                    max(abs(expected.energy), abs(energy_value), TINY64),
                    131072,
                ),
            )
            energy_gate &= findings.energy(within(energy_value, expected.energy, energy_tolerance))

            audit.require(len(relations) == len(payload.configuration.relations), f"{identifier} relation force count")
            relations.sort(key=lambda entry: unsigned(entry["relation_index"], "relation force index"))
            audit.require(
                [unsigned(entry["relation_index"], "relation force index") for entry in relations]
                == list(range(len(relations))),
                f"{identifier} relation force indices",
            )
            expected_edge_to_index = {
                edge: index for index, edge in enumerate(payload.configuration.relations)
            }
            seen_semantic_edges: set[tuple[int, int]] = set()
            for _coordinate_index, relation in enumerate(relations):
                first_actual = unsigned(relation["first_id"], "relation force first ID")
                second_actual = unsigned(relation["second_id"], "relation force second ID")
                audit.require(
                    first_actual in payload.actual_to_semantic and second_actual in payload.actual_to_semantic,
                    f"{identifier} relation output endpoint",
                )
                semantic_edge = (
                    payload.actual_to_semantic[first_actual],
                    payload.actual_to_semantic[second_actual],
                )
                canonical_semantic_edge = tuple(sorted(semantic_edge))
                audit.require(
                    canonical_semantic_edge in expected_edge_to_index
                    and canonical_semantic_edge not in seen_semantic_edges,
                    f"{identifier} semantic relation force coordinate",
                )
                seen_semantic_edges.add(canonical_semantic_edge)  # type: ignore[arg-type]
                index = expected_edge_to_index[canonical_semantic_edge]  # type: ignore[index]
                expected_edge = payload.configuration.relations[index]
                audit.require(
                    semantic_edge == expected_edge or semantic_edge == tuple(reversed(expected_edge)),
                    f"{identifier} semantic relation force coordinate",
                )
                comparisons = (
                    (decimal64(relation["reference_length_m"], "relation reference"), payload.model.reference_lengths[index], "reference"),
                    (decimal64(relation["current_length_m"], "relation current"), expected.lengths[index], "length"),
                    (decimal64(relation["extension_m"], "relation extension"), expected.extensions[index], "extension"),
                    (decimal64(relation["conjugate_force_n"], "relation conjugate"), expected.conjugates[index], "conjugate"),
                )
                for actual, expected_value, label in comparisons:
                    representation_bound = (
                        reference_force_bound
                        if label == "conjugate"
                        else reference_length_bound
                    )
                    tolerance = max(
                        representation_bound,
                        arithmetic_tolerance(
                            dimension,
                            max(abs(actual), abs(expected_value), TINY64),
                            131072,
                        ),
                    )
                    energy_gate &= findings.energy(within(actual, expected_value, tolerance))
                exported_direction = vector3_from_row(
                    relation,
                    ("direction_x", "direction_y", "direction_z"),
                    f"{identifier} direction",
                )
                signed_expected = expected.directions[index]
                if semantic_edge != expected_edge:
                    signed_expected = tuple(-value for value in signed_expected)  # type: ignore[assignment]
                for axis in range(3):
                    energy_gate &= findings.energy(
                        within(
                            exported_direction[axis],
                            signed_expected[axis],
                            arithmetic_tolerance(
                                dimension,
                                max(abs(exported_direction[axis]), abs(signed_expected[axis]), TINY64),
                                131072,
                            ),
                        )
                    )
            audit.require(
                seen_semantic_edges == set(payload.configuration.relations),
                f"{identifier} complete semantic relation output",
            )

            audit.require(len(forces) == len(payload.configuration.packet_ids), f"{identifier} packet force count")
            forces.sort(key=lambda entry: unsigned(entry["packet_index"], "packet force index"))
            exported_forces: dict[int, tuple[D, D, D]] = {}
            for force_row in forces:
                actual_id = unsigned(force_row["packet_id"], "packet force ID")
                semantic_id = unsigned(force_row["semantic_packet_id"], "packet force semantic ID")
                audit.require(payload.actual_to_semantic.get(actual_id) == semantic_id, f"{identifier} force semantic map")
                audit.require(semantic_id not in exported_forces, f"{identifier} duplicate semantic force")
                exported = vector3_from_row(
                    force_row, ("force_x_n", "force_y_n", "force_z_n"), f"{identifier} force"
                )
                exported_forces[semantic_id] = exported
                for axis in range(3):
                    tolerance = max(
                        reference_force_bound,
                        arithmetic_tolerance(
                            dimension,
                            max(TINY64, abs(expected.forces[semantic_id][axis]), abs(exported[axis])),
                            131072,
                        ),
                    )
                    energy_gate &= findings.energy(
                        within(exported[axis], expected.forces[semantic_id][axis], tolerance)
                    )

            expected_total_force = total_force(expected.forces)
            expected_torque_origin = total_torque(
                payload.current, expected.forces, (D(0), D(0), D(0))
            )
            expected_torque_shifted = total_torque(
                payload.current, expected.forces, shifted_origin
            )
            exported_total_force = vector3_from_row(
                row, ("total_force_x_n", "total_force_y_n", "total_force_z_n"), identifier
            )
            exported_torque_origin = vector3_from_row(
                row,
                ("total_torque_origin_x_nm", "total_torque_origin_y_nm", "total_torque_origin_z_nm"),
                identifier,
            )
            exported_torque_shifted = vector3_from_row(
                row,
                ("total_torque_shifted_x_nm", "total_torque_shifted_y_nm", "total_torque_shifted_z_nm"),
                identifier,
            )
            force_scale = decimal64(row["balance_scale_force_n"], f"{identifier} force scale")
            torque_scale = decimal64(row["balance_scale_torque_nm"], f"{identifier} torque scale")
            power_scale = decimal64(row["balance_scale_power_w"], f"{identifier} power scale")
            reconstructed_force_scale = sum(
                (abs(component) for force in exported_forces.values() for component in force),
                D(0),
            )
            reconstructed_torque_origin_scale = D(0)
            reconstructed_torque_shifted_scale = D(0)
            for packet_id in payload.model.packet_ids:
                torque_terms = cross(payload.current[packet_id], exported_forces[packet_id])
                shifted_terms = cross(
                    vsub(payload.current[packet_id], shifted_origin),
                    exported_forces[packet_id],
                )
                reconstructed_torque_origin_scale += sum(
                    (abs(value) for value in torque_terms), D(0)
                )
                reconstructed_torque_shifted_scale += sum(
                    (abs(value) for value in shifted_terms), D(0)
                )
            # Power reduction error is controlled by the elementary relation
            # endpoint terms, before packet-force assembly can cancel them.
            # The assembled packet work remains an independently reported
            # identity value, but is not the sole arithmetic scale.
            reconstructed_endpoint_power_scale = D(0)
            reconstructed_relation_power_scale = D(0)
            for relation in relations:
                first_actual = unsigned(relation["first_id"], "power relation first")
                second_actual = unsigned(relation["second_id"], "power relation second")
                first = payload.actual_to_semantic[first_actual]
                second = payload.actual_to_semantic[second_actual]
                direction = vector3_from_row(
                    relation,
                    ("direction_x", "direction_y", "direction_z"),
                    f"{identifier} power relation direction",
                )
                conjugate = decimal64(
                    relation["conjugate_force_n"],
                    f"{identifier} power relation conjugate",
                )
                extension_rate = dot(
                    direction,
                    vsub(payload.velocity[second], payload.velocity[first]),
                )
                endpoint_force = tuple(conjugate * value for value in direction)
                reconstructed_endpoint_power_scale += abs(
                    dot(endpoint_force, payload.velocity[first])
                ) + abs(
                    dot(
                        tuple(-value for value in endpoint_force),
                        payload.velocity[second],
                    )
                )
                reconstructed_relation_power_scale += abs(
                    conjugate * extension_rate
                )
            reconstructed_torque_scale = max(
                reconstructed_torque_origin_scale,
                reconstructed_torque_shifted_scale,
            )
            reconstructed_power_scale = (
                reconstructed_endpoint_power_scale
                + reconstructed_relation_power_scale
            )
            for actual_scale, expected_scale, label in (
                (force_scale, reconstructed_force_scale, "force"),
                (torque_scale, reconstructed_torque_scale, "torque"),
                (power_scale, reconstructed_power_scale, "power"),
            ):
                close(
                    actual_scale,
                    expected_scale,
                    arithmetic_tolerance(dimension, max(abs(actual_scale), abs(expected_scale), TINY64), 131072),
                    f"{identifier} independently reconstructed {label} scale",
                    audit,
                )
            expected_force_tolerance = arithmetic_tolerance(dimension, force_scale, 65536)
            expected_torque_tolerance = arithmetic_tolerance(dimension, torque_scale, 65536)
            expected_power_tolerance = arithmetic_tolerance(dimension, power_scale, 65536)
            force_tolerance = decimal64(row["tolerance_force_n"], f"{identifier} force tolerance")
            torque_tolerance = decimal64(row["tolerance_torque_nm"], f"{identifier} torque tolerance")
            power_tolerance = decimal64(row["tolerance_power_w"], f"{identifier} power tolerance")
            close(force_tolerance, expected_force_tolerance, arithmetic_tolerance(dimension, expected_force_tolerance, 16), f"{identifier} registered force tolerance", audit)
            close(torque_tolerance, expected_torque_tolerance, arithmetic_tolerance(dimension, expected_torque_tolerance, 16), f"{identifier} registered torque tolerance", audit)
            close(power_tolerance, expected_power_tolerance, arithmetic_tolerance(dimension, expected_power_tolerance, 16), f"{identifier} registered power tolerance", audit)
            expected_force_arithmetic = decimal_accumulation_tolerance(
                dimension,
                sum(
                    (
                        abs(component)
                        for force in expected.forces.values()
                        for component in force
                    ),
                    D(0),
                ),
            )
            expected_torque_origin_arithmetic = decimal_accumulation_tolerance(
                dimension,
                sum(
                    (
                        abs(component)
                        for packet_id in payload.model.packet_ids
                        for component in cross(
                            payload.current[packet_id],
                            expected.forces[packet_id],
                        )
                    ),
                    D(0),
                ),
            )
            expected_torque_shifted_arithmetic = decimal_accumulation_tolerance(
                dimension,
                sum(
                    (
                        abs(component)
                        for packet_id in payload.model.packet_ids
                        for component in cross(
                            vsub(payload.current[packet_id], shifted_origin),
                            expected.forces[packet_id],
                        )
                    ),
                    D(0),
                ),
            )
            conservation_gate &= findings.conservation(
                vector_norm_decimal(exported_total_force) <= force_tolerance
                and vector_norm_decimal(exported_torque_origin) <= torque_tolerance
                and vector_norm_decimal(exported_torque_shifted) <= torque_tolerance
                and vector_norm_decimal(expected_total_force) <= max(
                    force_tolerance, expected_force_arithmetic,
                )
                and vector_norm_decimal(expected_torque_origin) <= max(
                    torque_tolerance, expected_torque_origin_arithmetic,
                )
                and vector_norm_decimal(expected_torque_shifted) <= max(
                    torque_tolerance, expected_torque_shifted_arithmetic,
                )
                and max_abs(
                    exported_total_force[axis] - expected_total_force[axis]
                    for axis in range(3)
                ) <= max(force_tolerance, expected_force_arithmetic)
                and max_abs(
                    exported_torque_origin[axis] - expected_torque_origin[axis]
                    for axis in range(3)
                ) <= max(torque_tolerance, expected_torque_origin_arithmetic)
                and max_abs(
                    exported_torque_shifted[axis] - expected_torque_shifted[axis]
                    for axis in range(3)
                ) <= max(torque_tolerance, expected_torque_shifted_arithmetic)
            )

            r_matrix = rigidity(payload.model, payload.current)
            velocity = flatten(payload.velocity, payload.model.packet_ids)
            extension_power = dot(expected.conjugates, matvec(r_matrix, velocity))
            negative_force_power = -dot(force_vector(payload.model, payload.current), velocity)
            power_residual = extension_power - negative_force_power
            exported_extension_power = decimal64(row["extension_power_w"], f"{identifier} extension power")
            exported_negative_force_power = decimal64(row["negative_force_power_w"], f"{identifier} negative force power")
            exported_power_residual = decimal64(row["power_residual_w"], f"{identifier} power residual")
            power_compare = arithmetic_tolerance(
                dimension,
                max(TINY64, abs(extension_power), abs(negative_force_power)),
                131072,
            )
            velocity_scale = max_abs(
                component
                for velocity_value in payload.velocity.values()
                for component in velocity_value
            )
            power_compare = max(
                power_compare,
                reference_force_bound * velocity_scale * dimension,
            )
            energy_gate &= findings.energy(
                within(exported_extension_power, extension_power, power_compare)
                and within(exported_negative_force_power, negative_force_power, power_compare)
                and within(exported_power_residual, power_residual, power_compare)
                and abs(exported_power_residual) <= power_tolerance
            )
            if is_reference:
                exported_extensions = [
                    decimal64(relation["extension_m"], "reference extension")
                    for relation in relations
                ]
                exported_conjugates = [
                    decimal64(relation["conjugate_force_n"], "reference conjugate")
                    for relation in relations
                ]
                energy_gate &= findings.energy(
                    energy_value == 0
                    and max_abs(exported_extensions) == 0
                    and max_abs(exported_conjugates) == 0
                    and max_abs(value for force in exported_forces.values() for value in force)
                    == 0
                    and abs(expected.energy) <= reference_energy_bound
                    and max_abs(expected.extensions) <= reference_length_bound
                    and max_abs(expected.conjugates) <= reference_force_bound
                    and max_abs(force_vector(payload.model, payload.current))
                    <= reference_force_bound
                )
            # The producer-local pass predicate has no access to the
            # independent Decimal reconstruction.  Keep it separate so a
            # genuine independent gradient disagreement seals as a bounded
            # rejection rather than becoming a schema failure.
            producer_pass = (
                vector_norm_decimal(exported_total_force) <= force_tolerance
                and vector_norm_decimal(exported_torque_origin) <= torque_tolerance
                and vector_norm_decimal(exported_torque_shifted) <= torque_tolerance
                and abs(exported_power_residual) <= power_tolerance
            )
            findings.producer_failure_rows += int(not producer_pass)
            if not producer_pass:
                findings.conservation(False)
            audit.require(
                boolean(row["pass"], f"{identifier} pass") == producer_pass,
                f"{identifier} producer pass mismatch",
            )
    audit.require(set(relation_rows) <= set(payloads), "orphan relation force evaluations")
    audit.require(set(packet_force_rows) <= set(payloads), "orphan packet force evaluations")
    return valid_count, coincident_count


HP_STEP_RATIOS = (D("1e-8"), D("1e-12"), D("1e-16"), D("1e-20"))

GENERAL_DEFORMATION = (
    (D(21) / D(20), D(1) / D(20), -D(1) / D(40)),
    (D(0), D(19) / D(20), D(1) / D(25)),
    (D(1) / D(50), D(0), D(11) / D(10)),
)
SHEAR_DEFORMATION = (
    (D(1), D(3) / D(20), D(0)),
    (D(0), D(1), D(1) / D(20)),
    (D(0), D(0), D(1)),
)
COMPRESSION_DEFORMATION = (
    (D(4) / D(5), D(0), D(0)),
    (D(0), D(9) / D(10), D(0)),
    (D(0), D(0), D(17) / D(20)),
)
AFFINE_VELOCITY_GRADIENT = (
    (D(1) / D(7), -D(1) / D(11), D(1) / D(13)),
    (D(2) / D(17), -D(1) / D(19), D(1) / D(23)),
    (-D(1) / D(29), D(2) / D(31), D(1) / D(37)),
)
AFFINE_VELOCITY_INTERCEPT = (D(1) / D(5), -D(1) / D(7), D(1) / D(11))
BASE_VELOCITY_LABELS = (
    "translation_x", "translation_y", "translation_z",
    "rotation_x", "rotation_y", "rotation_z",
    "affine", "random_0", "random_1",
)
HP_DIRECTION_LABELS = tuple(
    [f"direction.translation_{axis}" for axis in "xyz"]
    + [f"direction.rotation_{axis}" for axis in "xyz"]
    + [f"direction.random_{index}" for index in range(6)]
)
REFERENCE_DIRECTION_LABELS = (
    "random_0", "random_1", "random_2", "isotropic", "pure_shear",
    "general_affine",
)


def centroid_decimal(
    points: Mapping[int, tuple[D, D, D]], packet_ids: Sequence[int]
) -> tuple[D, D, D]:
    sums = [0.0, 0.0, 0.0]
    for packet_id in packet_ids:
        for axis in range(3):
            sums[axis] += float(points[packet_id][axis])
    return tuple(
        D.from_float(sums[axis] / float(len(packet_ids))) for axis in range(3)
    )  # type: ignore[return-value]


def deform_about_centroid_decimal(
    points: Mapping[int, tuple[D, D, D]],
    packet_ids: Sequence[int],
    deformation: Sequence[Sequence[D]],
) -> dict[int, tuple[D, D, D]]:
    center = tuple(float(value) for value in centroid_decimal(points, packet_ids))
    matrix = [[float(value) for value in row] for row in deformation]
    result: dict[int, tuple[D, D, D]] = {}
    for packet_id in packet_ids:
        offset = [float(points[packet_id][axis]) - center[axis] for axis in range(3)]
        transformed = []
        for axis in range(3):
            value = matrix[axis][0] * offset[0]
            value += matrix[axis][1] * offset[1]
            value += matrix[axis][2] * offset[2]
            transformed.append(D.from_float(center[axis] + value))
        result[packet_id] = tuple(transformed)  # type: ignore[assignment]
    return result


def normalized_rigid_vectors_decimal(
    points: Mapping[int, tuple[D, D, D]],
    packet_ids: Sequence[int],
    translation_axis: int | None,
    rotation_axis: int | None,
) -> dict[int, tuple[D, D, D]]:
    center = tuple(float(value) for value in centroid_decimal(points, packet_ids))
    raw64: dict[int, tuple[float, float, float]] = {}
    squared = 0.0
    for packet_id in packet_ids:
        offset = [float(points[packet_id][axis]) - center[axis] for axis in range(3)]
        rotation = [0.0, 0.0, 0.0]
        if rotation_axis == 0:
            rotation = [0.0, -offset[2], offset[1]]
        elif rotation_axis == 1:
            rotation = [offset[2], 0.0, -offset[0]]
        elif rotation_axis == 2:
            rotation = [-offset[1], offset[0], 0.0]
        value = tuple(
            (1.0 if axis == translation_axis else 0.0) + rotation[axis]
            for axis in range(3)
        )
        raw64[packet_id] = value  # type: ignore[assignment]
        squared += value[0] * value[0] + value[1] * value[1] + value[2] * value[2]
    if squared == 0.0:
        reject("registered rigid velocity is degenerate")
    inverse = 1.0 / math.sqrt(squared)
    return {
        packet_id: tuple(D.from_float(inverse * value) for value in raw64[packet_id])  # type: ignore[misc]
        for packet_id in packet_ids
    }


def registered_base_velocity(
    points: Mapping[int, tuple[D, D, D]],
    packet_ids: Sequence[int],
    label: str,
    stream: int,
) -> dict[int, tuple[D, D, D]]:
    if label.startswith("translation_"):
        axis = {"x": 0, "y": 1, "z": 2}.get(label.removeprefix("translation_"))
        if axis is None:
            reject(f"unregistered base translation {label}")
        return normalized_rigid_vectors_decimal(points, packet_ids, axis, None)
    if label.startswith("rotation_"):
        axis = {"x": 0, "y": 1, "z": 2}.get(label.removeprefix("rotation_"))
        if axis is None:
            reject(f"unregistered base rotation {label}")
        return normalized_rigid_vectors_decimal(points, packet_ids, None, axis)
    if label == "affine":
        gradient = [[float(value) for value in row] for row in AFFINE_VELOCITY_GRADIENT]
        intercept = [float(value) for value in AFFINE_VELOCITY_INTERCEPT]
        result: dict[int, tuple[D, D, D]] = {}
        for packet_id in packet_ids:
            point = [float(value) for value in points[packet_id]]
            velocity: list[D] = []
            for axis in range(3):
                value = gradient[axis][0] * point[0]
                value += gradient[axis][1] * point[1]
                value += gradient[axis][2] * point[2]
                velocity.append(D.from_float(value + intercept[axis]))
            result[packet_id] = tuple(velocity)  # type: ignore[assignment]
        return result
    if label in {"random_0", "random_1"}:
        random_stream = stream if label == "random_0" else stream ^ 0x51A7D3
        values = registered_random_direction(len(packet_ids), random_stream)
        return unflatten(values, packet_ids)
    reject(f"unregistered base velocity {label}")


def require_registered_state(
    payload: EvaluationPayload,
    expected_current: Mapping[int, tuple[D, D, D]],
    expected_velocity: Mapping[int, tuple[D, D, D]],
    audit: Audit,
    label: str,
) -> None:
    audit.require(
        payload.emitted_actual_ids == payload.configuration.packet_ids
        and payload.emitted_semantic_ids == payload.configuration.semantic_ids,
        f"{label} canonical identity/order",
    )
    audit.require(
        set(expected_current) == set(payload.model.packet_ids)
        and set(expected_velocity) == set(payload.model.packet_ids),
        f"{label} expected packet inventory",
    )
    for packet_id in payload.model.packet_ids:
        for axis in range(3):
            expected_coordinate = float(expected_current[packet_id][axis])
            actual_coordinate = float(payload.current[packet_id][axis])
            coordinate_ulp = max(
                math.ulp(expected_coordinate), math.ulp(actual_coordinate)
            )
            audit.require(
                abs(actual_coordinate - expected_coordinate) <= 4.0 * coordinate_ulp,
                f"{label} registered coordinate {packet_id}/{axis}",
            )
            expected_component = float(expected_velocity[packet_id][axis])
            actual_component = float(payload.velocity[packet_id][axis])
            velocity_ulp = max(
                math.ulp(expected_component), math.ulp(actual_component)
            )
            audit.require(
                abs(actual_component - expected_component) <= 4.0 * velocity_ulp,
                f"{label} registered velocity {packet_id}/{axis}",
            )


def realized_rigid_basis(
    model: RelationModel, audit: Audit, label: str
) -> tuple[tuple[D, ...], ...]:
    """Construct an orthonormal basis of the realized 3-D rigid subspace."""

    packet_ids = model.packet_ids
    dimension = scale_dimension(len(packet_ids), len(model.relations))
    unit_tolerance = arithmetic_tolerance(dimension, D(1), 262144)
    center = centroid_decimal(model.reference, packet_ids)
    candidates: list[list[D]] = []
    for axis in range(3):
        candidates.append([
            D(1) if component % 3 == axis else D(0)
            for component in range(3 * len(packet_ids))
        ])
    for axis in range(3):
        omega = tuple(D(1) if component == axis else D(0) for component in range(3))
        rotation_map = {
            packet_id: cross(
                omega, vsub(model.reference[packet_id], center)
            )
            for packet_id in packet_ids
        }
        candidates.append(flatten(rotation_map, packet_ids))
    rigid_basis: list[list[D]] = []
    for candidate in candidates:
        residual = list(candidate)
        for basis in rigid_basis:
            coefficient = dot(residual, basis)
            residual = [
                value - coefficient * basis_value
                for value, basis_value in zip(residual, basis, strict=True)
            ]
        magnitude = norm(residual)
        audit.require(
            magnitude > unit_tolerance,
            f"{label} realized six-dimensional rigid space",
        )
        rigid_basis.append([value / magnitude for value in residual])
    return tuple(tuple(value for value in basis) for basis in rigid_basis)


def validate_floppy_direction(
    payload: EvaluationPayload,
    direction_map: Mapping[int, tuple[D, D, D]],
    audit: Audit,
) -> None:
    """Establish that the exported control is a genuine non-rigid R0 mode."""

    packet_ids = payload.model.packet_ids
    direction = flatten(direction_map, packet_ids)
    dimension = scale_dimension(len(packet_ids), len(payload.model.relations))
    unit_tolerance = arithmetic_tolerance(dimension, D(1), 262144)
    audit.require(
        abs(norm(direction) - D(1)) <= unit_tolerance,
        f"{payload.operator.identifier} floppy direction normalization",
    )
    r0 = rigidity(payload.model, payload.model.reference)
    kernel_residual = norm(matvec(r0, direction))
    audit.require(
        kernel_residual <= arithmetic_tolerance(dimension, D(1), 1048576),
        f"{payload.operator.identifier} floppy direction R0 kernel",
    )

    rigid_basis = realized_rigid_basis(
        payload.model, audit, payload.operator.identifier
    )
    nonrigid = list(direction)
    rigid_coefficients: list[D] = []
    for basis in rigid_basis:
        coefficient = dot(nonrigid, basis)
        rigid_coefficients.append(dot(direction, basis))
        nonrigid = [
            value - coefficient * basis_value
            for value, basis_value in zip(nonrigid, basis, strict=True)
        ]
    orthogonality_tolerance = arithmetic_tolerance(
        dimension, D(1), 1048576
    )
    audit.require(
        all(abs(value) <= orthogonality_tolerance for value in rigid_coefficients),
        f"{payload.operator.identifier} floppy direction rigid orthogonality",
    )
    audit.require(
        abs(norm(nonrigid) - D(1)) <= orthogonality_tolerance,
        f"{payload.operator.identifier} floppy direction unit non-rigid content",
    )


def require_exact_compression_state(
    payload: EvaluationPayload,
    ratio: D,
    audit: Audit,
    label: str,
) -> None:
    """Reproduce the registered power-of-two endpoint move bit-for-bit."""

    audit.require(
        payload.emitted_actual_ids == payload.configuration.packet_ids
        and payload.emitted_semantic_ids == payload.configuration.semantic_ids,
        f"{label} canonical compression identity/order",
    )
    first, second = payload.model.relations[0]
    ratio64 = float(ratio)
    expected: dict[int, tuple[D, D, D]] = dict(payload.model.reference)
    expected_second: list[D] = []
    for axis in range(3):
        first64 = float(payload.model.reference[first][axis])
        second64 = float(payload.model.reference[second][axis])
        offset64 = second64 - first64
        moved64 = first64 + ratio64 * offset64
        expected_second.append(D.from_float(moved64))
    expected[second] = tuple(expected_second)  # type: ignore[assignment]
    audit.require(
        all(
            payload.current[packet_id][axis] == expected[packet_id][axis]
            for packet_id in payload.model.packet_ids
            for axis in range(3)
        ),
        f"{label} exact registered compression coordinates",
    )
    audit.require(
        all(
            payload.velocity[packet_id][axis] == 0
            for packet_id in payload.model.packet_ids
            for axis in range(3)
        ),
        f"{label} exact zero compression velocity",
    )


def splitmix64(value: int) -> tuple[int, int]:
    mask = (1 << 64) - 1
    value = (value + 0x9E3779B97F4A7C15) & mask
    mixed = value
    mixed = ((mixed ^ (mixed >> 30)) * 0xBF58476D1CE4E5B9) & mask
    mixed = ((mixed ^ (mixed >> 27)) * 0x94D049BB133111EB) & mask
    mixed ^= mixed >> 31
    return value, mixed & mask


def deterministic_permutation(count: int, stream: int) -> list[int]:
    result = list(range(count))
    state = SEED ^ stream
    for remaining in range(count, 1, -1):
        state, mixed = splitmix64(state)
        selected = mixed % remaining
        result[remaining - 1], result[selected] = result[selected], result[remaining - 1]
    return result


def old_to_new_map(new_to_old: Sequence[int]) -> dict[int, int]:
    result = {old: new for new, old in enumerate(new_to_old)}
    if set(result) != set(range(len(new_to_old))):
        reject("deterministic permutation is not a bijection")
    return result


def registered_random_direction(packet_count: int, stream: int) -> list[D]:
    state = SEED ^ stream
    raw: list[float] = []
    scale = 1.0 / 9007199254740992.0
    squared = 0.0
    for _ in range(3 * packet_count):
        state, mixed = splitmix64(state)
        raw.append(2.0 * float(mixed >> 11) * scale - 1.0)
    for packet in range(packet_count):
        x, y, z = raw[3 * packet : 3 * packet + 3]
        squared += x * x + y * y + z * z
    inverse = 1.0 / math.sqrt(squared)
    return [D.from_float(inverse * value) for value in raw]


def canonical_operator_indices(
    payloads: Mapping[str, EvaluationPayload],
) -> dict[str, int]:
    operators = {payload.operator.identifier: payload.operator for payload in payloads.values()}
    ratio_order = {"1/3": 0, "2": 1, "10": 2}
    ordered = sorted(
        operators,
        key=lambda identifier: (
            operators[identifier].configuration_id,
            ratio_order[operators[identifier].ratio_text],
        ),
    )
    return {identifier: index for index, identifier in enumerate(ordered)}


def normalized_affine_direction_decimal(
    points: Mapping[int, tuple[D, D, D]],
    packet_ids: Sequence[int],
    matrix: Sequence[Sequence[D]],
) -> list[D]:
    center = tuple(float(value) for value in centroid_decimal(points, packet_ids))
    matrix64 = [[float(value) for value in row] for row in matrix]
    raw: list[float] = []
    squared = 0.0
    for packet_id in packet_ids:
        offset = [float(points[packet_id][axis]) - center[axis] for axis in range(3)]
        vector: list[float] = []
        for axis in range(3):
            value = matrix64[axis][0] * offset[0]
            value += matrix64[axis][1] * offset[1]
            value += matrix64[axis][2] * offset[2]
            vector.append(value)
        raw.extend(vector)
        squared += vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2]
    if squared == 0.0:
        reject("registered affine direction is degenerate")
    inverse = 1.0 / math.sqrt(squared)
    return [D.from_float(inverse * value) for value in raw]


def validate_registered_evaluation_inventory(
    payloads: Mapping[str, EvaluationPayload],
    operators: Mapping[str, Operator],
    *,
    full: bool,
    audit: Audit,
) -> None:
    """Bind every raw evaluation to the frozen semantic experiment.

    This check happens before any force value is interpreted.  A producer
    cannot substitute a different deformation/velocity field which happens
    to be self-consistent with its own force table.
    """

    expected: dict[str, tuple[str, str]] = {}
    operator_indices = canonical_operator_indices(payloads)
    deformation_probes = (
        ("F_general", GENERAL_DEFORMATION),
        ("F_shear", SHEAR_DEFORMATION),
        ("F_compress", COMPRESSION_DEFORMATION),
    )
    metamorphic_probes = (
        "current_translation", "common_rotation", "common_rotation_translation",
        "similarity_half", "similarity_two", "packet_reverse", "packet_splitmix",
        "relation_reverse", "relation_splitmix", "id_reverse", "id_cyclic",
        "id_sha256", "endpoint_reverse",
    ) if full else (
        "current_translation", "common_rotation", "common_rotation_translation",
    )

    def register(identifier: str, probe: str, velocity: str) -> None:
        audit.require(identifier not in expected, f"duplicate registered evaluation {identifier}")
        expected[identifier] = (probe, velocity)

    for operator_id, operator in operators.items():
        related = [payload for payload in payloads.values() if payload.operator.identifier == operator_id]
        audit.require(related, f"{operator_id} evaluation inventory")
        sample = related[0]
        reference = sample.configuration.reference
        packet_ids = sample.configuration.semantic_ids
        operator_index = operator_indices[operator_id]

        reference_id = f"{operator_id}.reference.zero"
        register(reference_id, "reference", "zero")
        reference_payload = payloads.get(reference_id)
        if reference_payload is not None:
            zero = {packet_id: (D(0), D(0), D(0)) for packet_id in packet_ids}
            require_registered_state(reference_payload, reference, zero, audit, reference_id)

        for probe_index, (probe, deformation) in enumerate(deformation_probes):
            current = deform_about_centroid_decimal(reference, packet_ids, deformation)
            velocity_labels = BASE_VELOCITY_LABELS if full else ("translation_x",)
            for velocity_label in velocity_labels:
                identifier = f"{operator_id}.{probe}.{velocity_label}"
                register(identifier, probe, velocity_label)
                payload = payloads.get(identifier)
                if payload is not None:
                    velocity = registered_base_velocity(
                        current, packet_ids, velocity_label,
                        operator_index * 17 + probe_index,
                    )
                    require_registered_state(payload, current, velocity, audit, identifier)

        direction_labels = (
            HP_DIRECTION_LABELS
            if full and operator.configuration_id in HP_IDS
            else ("direction.translation_x",) if not full
            else ()
        )
        direction_current = deform_about_centroid_decimal(
            reference, packet_ids, GENERAL_DEFORMATION
        )
        for direction_label in direction_labels:
            identifier = f"{operator_id}.{direction_label}"
            register(identifier, "general", direction_label)
            payload = payloads.get(identifier)
            if payload is None:
                continue
            if direction_label.startswith("direction.random_"):
                random_index = unsigned(
                    direction_label.removeprefix("direction.random_"),
                    f"{identifier} random index",
                )
                flat_velocity = registered_random_direction(
                    len(packet_ids), operator_index * 101 + random_index
                )
                velocity = unflatten(flat_velocity, packet_ids)
            else:
                velocity = registered_base_velocity(
                    direction_current,
                    packet_ids,
                    direction_label.removeprefix("direction."),
                    0,
                )
            require_registered_state(
                payload, direction_current, velocity, audit, identifier
            )

        reference_labels = REFERENCE_DIRECTION_LABELS if full else ("random_0",)
        reference_ratios = tuple(D(2) ** -power for power in (6, 9, 12, 15, 18, 21))
        for direction_label in reference_labels:
            for level, ratio in enumerate(reference_ratios):
                identifier = f"{operator_id}.reference_tangent.{direction_label}.{level}"
                register(identifier, "reference_tangent", direction_label)
                payload = payloads.get(identifier)
                if payload is None:
                    continue
                direction = registered_reference_direction(
                    payload, direction_label, operator_index
                )
                direction_map = unflatten(direction, packet_ids)
                epsilon = max(payload.model.reference_lengths) * ratio
                current = {
                    packet_id: tuple(
                        reference[packet_id][axis]
                        + epsilon * direction_map[packet_id][axis]
                        for axis in range(3)
                    )  # type: ignore[misc]
                    for packet_id in packet_ids
                }
                require_registered_state(
                    payload, current, direction_map, audit, identifier
                )

        if full and operator.configuration_id == "exact.tetrahedron_k4_minus_edge":
            floppy_direction: Mapping[int, tuple[D, D, D]] | None = None
            for level, ratio in enumerate(
                tuple(D(2) ** -power for power in (8, 12, 16, 20))
            ):
                identifier = f"{operator_id}.floppy_mechanism.{level}"
                register(identifier, "floppy_mechanism", "floppy_mechanism")
                payload = payloads.get(identifier)
                if payload is None:
                    continue
                if floppy_direction is None:
                    floppy_direction = payload.velocity
                    validate_floppy_direction(
                        payload, floppy_direction, audit
                    )
                dimension = scale_dimension(len(packet_ids), len(payload.model.relations))
                audit.require(
                    max_abs(
                        payload.velocity[packet_id][axis]
                        - floppy_direction[packet_id][axis]
                        for packet_id in packet_ids for axis in range(3)
                    ) <= arithmetic_tolerance(dimension, D(1), 131072),
                    f"{identifier} fixed floppy direction",
                )
                epsilon = max(payload.model.reference_lengths) * ratio
                current = {
                    packet_id: tuple(
                        reference[packet_id][axis]
                        + epsilon * floppy_direction[packet_id][axis]
                        for axis in range(3)
                    )  # type: ignore[misc]
                    for packet_id in packet_ids
                }
                require_registered_state(
                    payload, current, floppy_direction, audit, identifier
                )

        finite_selected = operator.configuration_id in HP_IDS or not full
        if finite_selected:
            for finite_probe, deformation in (
                ("general", GENERAL_DEFORMATION),
                ("compress", COMPRESSION_DEFORMATION),
            ):
                identifier = f"{operator_id}.finite_tangent.{finite_probe}"
                register(identifier, finite_probe, "zero")
                payload = payloads.get(identifier)
                if payload is not None:
                    current = deform_about_centroid_decimal(
                        reference, packet_ids, deformation
                    )
                    zero = {packet_id: (D(0), D(0), D(0)) for packet_id in packet_ids}
                    require_registered_state(payload, current, zero, audit, identifier)

        baseline_id = f"{operator_id}.metamorphic.baseline"
        register(baseline_id, "F_general", "affine")
        baseline = payloads.get(baseline_id)
        if baseline is not None:
            current = deform_about_centroid_decimal(
                reference, packet_ids, GENERAL_DEFORMATION
            )
            velocity = registered_base_velocity(current, packet_ids, "affine", 0)
            require_registered_state(baseline, current, velocity, audit, baseline_id)
        for probe in metamorphic_probes:
            register(f"{operator_id}.metamorphic.{probe}", probe, "affine_transformed")

        if operator.configuration_id in {
            "exact.tetrahedron_k4", "exact.octahedron_graph"
        }:
            powers = (0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48)
            if not full:
                powers = powers[:3]
            for level, _power in enumerate(powers):
                register(f"{operator_id}.compression.{level}", "compression", "zero")
            register(
                f"{operator_id}.compression.coincident",
                "compression_coincident",
                "zero",
            )

    audit.require(set(payloads) == set(expected), "closed registered evaluation inventory")
    for identifier, (probe, velocity) in expected.items():
        payload = payloads[identifier]
        audit.require(
            payload.row["probe"] == probe
            and payload.row["velocity_probe"] == velocity,
            f"{identifier} registered probe identity",
        )


def independent_rigid_direction(
    payload: EvaluationPayload, label: str, operator_index: int
) -> list[D]:
    packet_ids = payload.model.packet_ids
    if label.startswith("direction.translation_"):
        axis_name = label.removeprefix("direction.translation_")
        axis = {"x": 0, "y": 1, "z": 2}.get(axis_name)
        if axis is None:
            reject(f"{payload.identifier}: unknown translation direction")
        magnitude = D(len(packet_ids)).sqrt()
        return [
            (D(1) / magnitude if component % 3 == axis else D(0))
            for component in range(3 * len(packet_ids))
        ]
    if label.startswith("direction.rotation_"):
        axis_name = label.removeprefix("direction.rotation_")
        axis = {"x": 0, "y": 1, "z": 2}.get(axis_name)
        if axis is None:
            reject(f"{payload.identifier}: unknown rotation direction")
        centroid = tuple(
            sum((payload.current[packet_id][component] for packet_id in packet_ids), D(0))
            / D(len(packet_ids))
            for component in range(3)
        )
        omega = tuple(D(1) if component == axis else D(0) for component in range(3))
        vectors = {
            packet_id: cross(omega, vsub(payload.current[packet_id], centroid))
            for packet_id in packet_ids
        }
        raw = flatten(vectors, packet_ids)
        magnitude = norm(raw)
        if magnitude == 0:
            reject(f"{payload.identifier}: degenerate rigid rotation direction")
        return [value / magnitude for value in raw]
    if label.startswith("direction.random_"):
        random_index = unsigned(
            label.removeprefix("direction.random_"),
            f"{payload.identifier} random direction index",
        )
        if random_index >= 6:
            reject(f"{payload.identifier}: unregistered random direction")
        return registered_random_direction(
            len(packet_ids), operator_index * 101 + random_index
        )
    reject(f"{payload.identifier}: unregistered independent direction")


def compute_independent_directional_rows(
    payloads: Mapping[str, EvaluationPayload],
    packet_force_rows: Mapping[str, list[dict[str, str]]],
    audit: Audit,
    findings: ScientificFindings,
    *,
    full: bool,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    labels_by_operator: dict[str, set[str]] = defaultdict(set)
    operator_indices = canonical_operator_indices(payloads)
    for identifier in sorted(payloads):
        payload = payloads[identifier]
        label = payload.row["velocity_probe"]
        if (
            payload.configuration.identifier not in HP_IDS
            or payload.row["probe"] != "general"
            or not label.startswith("direction.")
            or payload.row["status"] != "valid_noncoincident"
        ):
            continue
        if label.startswith("direction.translation_"):
            kind = "translation"
        elif label.startswith("direction.rotation_"):
            kind = "rotation"
        elif label.startswith("direction.random_"):
            kind = "splitmix64_random"
        else:
            reject(f"{identifier}: unregistered high-precision direction")
        direction = independent_rigid_direction(
            payload, label, operator_indices[payload.operator.identifier]
        )
        exported_direction = flatten(payload.velocity, payload.model.packet_ids)
        dimension = scale_dimension(
            len(payload.configuration.packet_ids), len(payload.configuration.relations)
        )
        direction_tolerance = arithmetic_tolerance(dimension, D(1), 131072)
        audit.require(
            max_abs(a - b for a, b in zip(direction, exported_direction, strict=True))
            <= direction_tolerance,
            f"{identifier} independent direction reconstruction",
        )
        audit.require(abs(norm(direction) - D(1)) <= direction_tolerance, f"{identifier} normalized direction")
        with localcontext() as context:
            context.prec = DIGITS
            force = force_vector(payload.model, payload.current)
            analytic = -dot(force, direction)
            exported_forces: dict[int, tuple[D, D, D]] = {}
            for force_row in packet_force_rows.get(identifier, []):
                actual_id = unsigned(force_row["packet_id"], "directional C++ packet ID")
                semantic_id = unsigned(force_row["semantic_packet_id"], "directional C++ semantic ID")
                audit.require(
                    payload.actual_to_semantic.get(actual_id) == semantic_id
                    and semantic_id not in exported_forces,
                    f"{identifier} directional C++ force map",
                )
                exported_forces[semantic_id] = vector3_from_row(
                    force_row,
                    ("force_x_n", "force_y_n", "force_z_n"),
                    f"{identifier} directional C++ force",
                )
            audit.require(
                set(exported_forces) == set(payload.model.packet_ids),
                f"{identifier} directional C++ force inventory",
            )
            cpp_analytic = -dot(
                flatten(exported_forces, payload.model.packet_ids), direction
            )
            characteristic = max(payload.model.reference_lengths)
            steps = [characteristic * ratio for ratio in HP_STEP_RATIOS]
            raw = [
                directional_derivative(payload.model, payload.current, direction, step)
                for step in steps
            ]
            raw_residuals = [abs(value - analytic) for value in raw]
            extrapolated = extrapolate_polynomial_at_zero(
                [step * step for step in steps], raw
            )
            extrapolated_residual = abs(extrapolated - analytic)
            cpp_gradient_residual = max(
                abs(cpp_analytic - analytic), abs(cpp_analytic - extrapolated)
            )
            absolute_tolerance = D("1e-55")
            relative_tolerance = D("1e-45")
            allowed = max(absolute_tolerance, relative_tolerance * abs(analytic))
            raw_converged = registered_raw_convergence(raw_residuals, allowed)
            cpp_work_scale = max(
                sum(
                    (
                        abs(force_component * direction_component)
                        for force_component, direction_component in zip(
                            flatten(exported_forces, payload.model.packet_ids),
                            direction,
                            strict=True,
                        )
                    ),
                    D(0),
                ),
                sum(
                    (
                        abs(force_component * direction_component)
                        for force_component, direction_component in zip(
                            force,
                            direction,
                            strict=True,
                        )
                    ),
                    D(0),
                ),
                TINY64,
            )
            h_scale = max_abs(
                value
                for matrix_row in payload.operator.parent_h
                for value in matrix_row
            )
            reference_force_bound = arithmetic_tolerance(
                dimension,
                h_scale * max(payload.model.reference_lengths),
                65536,
            )
            representation_work_bound = reference_force_bound * sum(
                (abs(value) for value in direction), D(0)
            )
            cpp_allowed = max(
                representation_work_bound,
                arithmetic_tolerance(
                dimension,
                cpp_work_scale,
                131072,
                ),
            )
            findings.inconclusive(
                raw_converged, "directional_raw_nonconvergence"
            )
            passed = (
                extrapolated_residual <= allowed
                and cpp_gradient_residual <= cpp_allowed
            )
            if kind in {"translation", "rotation"}:
                passed = passed and abs(analytic) <= absolute_tolerance
            findings.energy(passed)
            evidence_pass = passed and raw_converged
            audit.require(
                label not in labels_by_operator[payload.operator.identifier],
                f"{payload.operator.identifier} duplicate directional label {label}",
            )
            labels_by_operator[payload.operator.identifier].add(label)
            for step_index, (ratio, step, value, residual) in enumerate(
                zip(HP_STEP_RATIOS, steps, raw, raw_residuals, strict=True)
            ):
                rows.append(
                    {
                        "evaluation_id": identifier,
                        "direction_id": label.removeprefix("direction."),
                        "direction_kind": kind,
                        "step_index": str(step_index),
                        "h_over_l": dtext(ratio),
                        "h_m": dtext(step),
                        "analytic_derivative_n": dtext(analytic),
                        "cpp_analytic_derivative_n": dtext(cpp_analytic),
                        "cpp_gradient_residual_n": dtext(cpp_gradient_residual),
                        "centered_decimal_derivative_n": dtext(value),
                        "raw_residual_n": dtext(residual),
                        "extrapolated_decimal_derivative_n": dtext(extrapolated),
                        "extrapolated_residual_n": dtext(extrapolated_residual),
                        "relative_tolerance": dtext(relative_tolerance),
                        "absolute_tolerance_n": dtext(absolute_tolerance),
                        "decimal_digits": str(DIGITS),
                        "raw_converged": "true" if raw_converged else "false",
                        "pass": "true" if evidence_pass else "false",
                    }
                )
    expected_operator_ids = {
        operator_id
        for operator_id, payload_operator in {
            payload.operator.identifier: payload.operator for payload in payloads.values()
        }.items()
        if payload_operator.configuration_id in HP_IDS
    }
    expected_labels = set(HP_DIRECTION_LABELS if full else ("direction.translation_x",))
    for operator_id in expected_operator_ids:
        audit.require(
            labels_by_operator[operator_id] == expected_labels,
            f"{operator_id} directional inventory",
        )
    audit.require(
        set(labels_by_operator) == expected_operator_ids,
        "closed directional operator inventory",
    )
    return rows


def compute_independent_finite_tangent_rows(
    raw_root: pathlib.Path,
    payloads: Mapping[str, EvaluationPayload],
    audit: Audit,
    findings: ScientificFindings,
    *,
    full: bool,
) -> list[dict[str, str]]:
    raw_rows = read_csv(raw_root / "finite_tangent.csv")
    evaluation_ids = sorted({row["evaluation_id"] for row in raw_rows})
    result: list[dict[str, str]] = []
    for evaluation_id in evaluation_ids:
        audit.require(evaluation_id in payloads, f"finite tangent evaluation {evaluation_id}")
        payload = payloads[evaluation_id]
        audit.require(
            payload.configuration.identifier in HP_IDS or not full,
            f"finite tangent graph {evaluation_id}",
        )
        audit.require(payload.row["probe"] in {"general", "compress"}, f"finite tangent probe {evaluation_id}")
        with localcontext() as context:
            context.prec = DIGITS
            material, geometric, total = tangent_decomposition(payload.model, payload.current)
            size = 3 * len(payload.model.packet_ids)
            characteristic = max(payload.model.reference_lengths)
            steps = [characteristic * ratio for ratio in HP_STEP_RATIOS]
            raw_matrices = [
                numerical_force_jacobian(payload.model, payload.current, step)
                for step in steps
            ]
            extrapolated = [
                [
                    extrapolate_polynomial_at_zero(
                        [step * step for step in steps],
                        [matrix[row][column] for matrix in raw_matrices],
                    )
                    for column in range(size)
                ]
                for row in range(size)
            ]
            scale = max(TINY64, max_abs(value for matrix_row in total for value in matrix_row))
            tolerance = max(D("1e-50"), D("1e-40") * scale)
            decomposition_residual = max_abs(
                total[row][column] - material[row][column] - geometric[row][column]
                for row in range(size)
                for column in range(size)
            )
            symmetry_residual = max_abs(
                total[row][column] - total[column][row]
                for row in range(size)
                for column in range(size)
            )
            gradient_residual = max_abs(
                extrapolated[row][column] + total[row][column]
                for row in range(size)
                for column in range(size)
            )
            raw_level_residuals = [
                max_abs(
                    raw_matrix[row][column] + total[row][column]
                    for row in range(size)
                    for column in range(size)
                )
                for raw_matrix in raw_matrices
            ]
            raw_converged = registered_raw_convergence(
                raw_level_residuals, tolerance
            )
            findings.inconclusive(
                raw_converged, "finite_tangent_raw_nonconvergence"
            )
            tangent_pass = max(
                decomposition_residual, symmetry_residual, gradient_residual
            ) <= tolerance
            findings.finite(tangent_pass)
            evidence_pass = tangent_pass and raw_converged
            for row in range(size):
                for column in range(size):
                    packet_row = payload.model.packet_ids[row // 3]
                    packet_column = payload.model.packet_ids[column // 3]
                    for step_index, (ratio, raw_matrix) in enumerate(
                        zip(HP_STEP_RATIOS, raw_matrices, strict=True)
                    ):
                        raw_residual = abs(raw_matrix[row][column] + total[row][column])
                        result.append(
                            {
                                "evaluation_id": evaluation_id,
                                "row_dof": str(row),
                                "column_dof": str(column),
                                "row_semantic_packet_id": str(packet_row),
                                "row_axis": str(row % 3),
                                "column_semantic_packet_id": str(packet_column),
                                "column_axis": str(column % 3),
                                "step_index": str(step_index),
                                "h_over_l": dtext(ratio),
                                "material_n_per_m": dtext(material[row][column]),
                                "geometric_n_per_m": dtext(geometric[row][column]),
                                "total_energy_hessian_n_per_m": dtext(total[row][column]),
                                "force_jacobian_n_per_m": dtext(-total[row][column]),
                                "raw_independent_force_jacobian_n_per_m": dtext(raw_matrix[row][column]),
                                "raw_gradient_residual_n_per_m": dtext(raw_residual),
                                "independent_extrapolated_force_jacobian_n_per_m": dtext(extrapolated[row][column]),
                                "decomposition_residual_n_per_m": dtext(decomposition_residual),
                                "gradient_residual_n_per_m": dtext(gradient_residual),
                                "symmetry_residual_n_per_m": dtext(symmetry_residual),
                                "tolerance_n_per_m": dtext(tolerance),
                                "pass": "true" if evidence_pass else "false",
                            }
                        )
    expected_operator_ids = {
        payload.operator.identifier
        for payload in payloads.values()
        if payload.operator.configuration_id in HP_IDS or not full
    }
    expected_evaluation_ids = {
        f"{operator_id}.finite_tangent.{probe}"
        for operator_id in expected_operator_ids
        for probe in ("general", "compress")
    }
    audit.require(
        set(evaluation_ids) == expected_evaluation_ids,
        "finite tangent registered evaluation inventory",
    )
    return result


def registered_reference_direction(
    payload: EvaluationPayload,
    direction_id: str,
    operator_index: int,
) -> list[D]:
    packet_ids = payload.model.packet_ids
    if direction_id.startswith("random_"):
        random_index = unsigned(
            direction_id.removeprefix("random_"),
            f"{payload.identifier} reference random index",
        )
        if random_index >= 3:
            reject(f"{payload.identifier}: unregistered reference random direction")
        return registered_random_direction(
            len(packet_ids), operator_index * 31 + random_index
        )
    if direction_id == "isotropic":
        matrix = tuple(
            tuple(D(1) if row == column else D(0) for column in range(3))
            for row in range(3)
        )
    elif direction_id == "pure_shear":
        matrix = (
            (D(0), D("0.5"), D(0)),
            (D("0.5"), D(0), D(0)),
            (D(0), D(0), D(0)),
        )
    elif direction_id == "general_affine":
        matrix = (
            (D(21) / D(20), D(1) / D(20), -D(1) / D(40)),
            (D(0), D(19) / D(20), D(1) / D(25)),
            (D(1) / D(50), D(0), D(11) / D(10)),
        )
    else:
        reject(f"{payload.identifier}: unregistered reference direction")
    return normalized_affine_direction_decimal(
        payload.model.reference, packet_ids, matrix
    )


def validate_reference_tangent(
    raw_root: pathlib.Path,
    payloads: Mapping[str, EvaluationPayload],
    operators: Mapping[str, Operator],
    audit: Audit,
    findings: ScientificFindings,
    *,
    full: bool,
) -> int:
    rows = read_csv(raw_root / "reference_tangent.csv")
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["operator_id"], row["direction_id"]].append(row)
    normal_counts: dict[str, int] = defaultdict(int)
    operator_indices = canonical_operator_indices(payloads)
    for (operator_id, direction_id), group in grouped.items():
        audit.require(operator_id in operators, f"reference tangent operator {operator_id}")
        group.sort(key=lambda entry: unsigned(entry["epsilon_index"], "reference epsilon index"))
        direction_kind = group[0]["direction_kind"]
        audit.require(
            all(row["direction_id"] == direction_id and row["direction_kind"] == direction_kind for row in group),
            f"{operator_id}/{direction_id} reference direction identity",
        )
        expected_ratios = (
            tuple(D(2) ** -power for power in (8, 12, 16, 20))
            if direction_kind == "floppy_mechanism"
            else tuple(D(2) ** -power for power in (6, 9, 12, 15, 18, 21))
        )
        audit.require(len(group) == len(expected_ratios), f"reference tangent levels {operator_id}/{direction_id}")
        errors: list[D] = []
        directions: list[list[D]] = []
        report_gate = True
        exported_errors: list[float] = []
        for index, (row, expected_ratio) in enumerate(zip(group, expected_ratios, strict=True)):
            audit.require(unsigned(row["epsilon_index"], "reference epsilon index") == index, f"reference epsilon index {operator_id}/{direction_id}")
            evaluation_id = row["evaluation_id"]
            audit.require(evaluation_id in payloads, f"reference tangent evaluation {evaluation_id}")
            payload = payloads[evaluation_id]
            audit.require(payload.operator.identifier == operator_id, f"reference tangent binding {evaluation_id}")
            ratio = decimal64(row["epsilon_over_l"], f"{evaluation_id} epsilon ratio")
            ratio_tolerance = arithmetic_tolerance(D(6), expected_ratio, 64)
            close(ratio, expected_ratio, ratio_tolerance, f"{evaluation_id} epsilon ratio", audit)
            characteristic = max(payload.model.reference_lengths)
            epsilon = decimal64(row["epsilon_m"], f"{evaluation_id} epsilon")
            close(
                epsilon,
                characteristic * expected_ratio,
                arithmetic_tolerance(D(6), epsilon, 65536),
                f"{evaluation_id} epsilon dimension",
                audit,
            )
            exported_direction = flatten(payload.velocity, payload.model.packet_ids)
            direction = (
                exported_direction
                if direction_kind == "floppy_mechanism"
                else registered_reference_direction(
                    payload,
                    direction_id,
                    operator_indices[payload.operator.identifier],
                )
            )
            direction_norm = norm(direction)
            audit.require(abs(direction_norm - D(1)) <= arithmetic_tolerance(D(3 * len(payload.model.packet_ids)), D(1), 131072), f"{evaluation_id} tangent direction norm")
            audit.require(
                max_abs(
                    expected_value - actual_value
                    for expected_value, actual_value in zip(
                        direction, exported_direction, strict=True
                    )
                )
                <= arithmetic_tolerance(
                    D(3 * len(payload.model.packet_ids)), D(1), 131072
                ),
                f"{evaluation_id} independently reconstructed reference direction",
            )
            directions.append(direction)
            reference_r = rigidity(payload.model, payload.model.reference)
            reference_k = matmul(transpose(reference_r), matmul(payload.model.h, reference_r))
            expected_linear = [-value for value in matvec(reference_k, direction)]
            actual = [value / epsilon for value in force_vector(payload.model, payload.current)]
            denominator = max(
                max_abs(expected_linear),
                max_abs(value for matrix_row in payload.operator.parent_h for value in matrix_row),
                TINY64,
            )
            error = max_abs(a - b for a, b in zip(actual, expected_linear, strict=True)) / denominator
            errors.append(error)
            exported_error_float = binary64(row["error_infinity_scaled"], f"{evaluation_id} tangent error")
            exported_errors.append(exported_error_float)
            reproduced_binary64_error = binary64_reference_tangent_error(
                payload.model,
                payload.current,
                direction,
                float(epsilon),
                max(
                    abs(float(value))
                    for matrix_row in payload.operator.parent_h
                    for value in matrix_row
                ),
            )
            audit.require(
                exported_error_float == reproduced_binary64_error,
                f"{evaluation_id} independently reproduced binary64 tangent error",
            )
        # Bind every producer convergence field to the exact binary64
        # recurrence used by the raw producer.  These are diagnostic fields,
        # but they are not accepted as arbitrary rehashed metadata.
        divisor = 16.0 if direction_kind == "floppy_mechanism" else 8.0
        producer_orders = [0.0] * len(exported_errors)
        for index in range(1, len(exported_errors)):
            if exported_errors[index] > 0.0 and exported_errors[index - 1] > 0.0:
                producer_orders[index] = math.log(
                    exported_errors[index - 1] / exported_errors[index]
                ) / math.log(divisor)
        producer_minimum = min(exported_errors)
        producer_median_values = sorted(producer_orders[1:4])
        producer_median = producer_median_values[1]
        producer_decreases = all(
            exported_errors[index + 1] < exported_errors[index]
            for index in range(3)
        )
        dimension = scale_dimension(
            len(payloads[group[0]["evaluation_id"]].model.packet_ids),
            len(payloads[group[0]["evaluation_id"]].model.relations),
        )
        reference_floor = arithmetic_tolerance(dimension, D(1), 262144)
        producer_convergence = converges_until_floor(
            [D.from_float(value) for value in exported_errors], reference_floor
        )
        producer_initially_at_floor = (
            D.from_float(exported_errors[0]) <= reference_floor
        )
        for index, row in enumerate(group):
            close(
                decimal64(row["observed_order"], "reference observed order"),
                D.from_float(producer_orders[index]),
                arithmetic_tolerance(
                    D(6),
                    max(
                        abs(decimal64(row["observed_order"], "reference observed order scale")),
                        abs(D.from_float(producer_orders[index])),
                        TINY64,
                    ),
                    64,
                ),
                f"{operator_id}/{direction_id} observed order {index}",
                audit,
            )
            close(
                decimal64(row["minimum_relative_error"], "reference minimum"),
                D.from_float(producer_minimum),
                arithmetic_tolerance(D(6), max(TINY64, abs(D.from_float(producer_minimum))), 64),
                f"{operator_id}/{direction_id} producer minimum",
                audit,
            )
            close(
                decimal64(row["median_order"], "reference median"),
                D.from_float(producer_median),
                arithmetic_tolerance(
                    D(6),
                    max(
                        abs(decimal64(row["median_order"], "reference median scale")),
                        abs(D.from_float(producer_median)),
                        TINY64,
                    ),
                    64,
                ),
                f"{operator_id}/{direction_id} producer median",
                audit,
            )
            audit.require(
                boolean(row["three_consecutive_decreases"], "reference decreases")
                == producer_decreases,
                f"{operator_id}/{direction_id} producer decrease flag",
            )
        direction_difference = max_abs(
            first - second
            for direction in directions[1:]
            for first, second in zip(directions[0], direction, strict=True)
        )
        audit.require(direction_difference <= arithmetic_tolerance(D(len(directions[0])), D(1), 131072), f"{operator_id}/{direction_id} fixed direction")
        if direction_kind == "floppy_mechanism":
            independent_convergence = converges_until_floor(errors, reference_floor)
            independent_initially_at_floor = errors[0] <= reference_floor
            group_pass = (
                report_gate
                and independent_convergence
                and (
                    independent_initially_at_floor
                    or all(errors[index + 1] < errors[index] for index in range(3))
                )
            )
            findings.finite(group_pass)
            producer_pass = producer_convergence and (
                producer_initially_at_floor
                or (
                    producer_decreases
                    and D("0.75")
                    <= D.from_float(producer_median)
                    <= D("1.25")
                )
            )
            findings.producer_failure_rows += len(group) * int(not producer_pass)
            if not producer_pass:
                findings.finite(False)
            for row in group:
                audit.require(
                    boolean(row["pass"], "floppy reference pass") == producer_pass,
                    f"{operator_id} floppy producer pass mismatch",
                )
            continue
        normal_counts[operator_id] += 1
        decrease_gate = all(errors[index + 1] < errors[index] for index in range(3))
        independent_convergence = converges_until_floor(errors, reference_floor)
        independent_initially_at_floor = errors[0] <= reference_floor
        orders = [
            (errors[index] / errors[index + 1]).ln() / D(8).ln()
            for index in range(3)
            if errors[index] != 0 and errors[index + 1] != 0
        ]
        audit.require(len(orders) >= 3, f"{operator_id}/{direction_id} observed orders")
        sorted_orders = sorted(orders)
        median = sorted_orders[len(sorted_orders) // 2]
        group_pass = (
            report_gate
            and independent_convergence
            and (
                independent_initially_at_floor
                or (decrease_gate and D("0.75") <= median <= D("1.25"))
            )
            and min(errors) <= D("2e-5")
        )
        findings.finite(group_pass)
        producer_pass = (
            producer_convergence
            and (
                producer_initially_at_floor
                or (producer_decreases and 0.75 <= producer_median <= 1.25)
            )
            and producer_minimum <= 2.0e-5
        )
        findings.producer_failure_rows += len(group) * int(not producer_pass)
        if not producer_pass:
            findings.finite(False)
        for row in group:
            audit.require(
                boolean(row["pass"], "reference tangent pass") == producer_pass,
                f"{operator_id}/{direction_id} producer pass mismatch",
            )
    expected_normal_labels = set(
        REFERENCE_DIRECTION_LABELS if full else ("random_0",)
    )
    observed_labels: dict[str, set[str]] = defaultdict(set)
    for operator_id, direction_id in grouped:
        if direction_id != "floppy_mechanism":
            observed_labels[operator_id].add(direction_id)
    for operator_id in operators:
        audit.require(
            observed_labels[operator_id] == expected_normal_labels,
            f"{operator_id} registered reference directions",
        )
        audit.require(
            normal_counts[operator_id] == len(expected_normal_labels),
            f"{operator_id} reference direction count",
        )
        floppy_expected = (
            full
            and operators[operator_id].configuration_id
            == "exact.tetrahedron_k4_minus_edge"
        )
        audit.require(
            ((operator_id, "floppy_mechanism") in grouped) == floppy_expected,
            f"{operator_id} floppy mechanism inventory",
        )
    return len(rows)


def validate_raw_finite_tangent(
    raw_root: pathlib.Path,
    payloads: Mapping[str, EvaluationPayload],
    audit: Audit,
    findings: ScientificFindings,
    *,
    full: bool,
) -> int:
    rows = read_csv(raw_root / "finite_tangent.csv")
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["evaluation_id"]].append(row)
    expected_operator_ids = {
        payload.operator.identifier
        for payload in payloads.values()
        if payload.operator.configuration_id in HP_IDS or not full
    }
    expected_evaluation_ids = {
        f"{operator_id}.finite_tangent.{probe}"
        for operator_id in expected_operator_ids
        for probe in ("general", "compress")
    }
    audit.require(
        set(grouped) == expected_evaluation_ids,
        "raw finite tangent evaluation inventory",
    )
    for evaluation_id, group in grouped.items():
        audit.require(evaluation_id in payloads, f"raw finite evaluation {evaluation_id}")
        payload = payloads[evaluation_id]
        material, geometric, total = tangent_decomposition(payload.model, payload.current)
        size = len(total)
        audit.require(len(group) == size * size * 4, f"{evaluation_id} raw finite matrix rows")
        seen: set[tuple[int, int, int]] = set()
        dimension = scale_dimension(len(payload.model.packet_ids), len(payload.model.relations))
        matrix_scale = max(
            max_abs(value for matrix_row in material for value in matrix_row),
            max_abs(value for matrix_row in geometric for value in matrix_row),
            max_abs(value for matrix_row in total for value in matrix_row),
            TINY64,
        )
        tolerance = arithmetic_tolerance(dimension, matrix_scale, 262144)
        raw_matrices = [
            binary64_force_jacobian_matrix(
                payload.model, payload.current, float(HP_STEP_RATIOS[index])
            )
            for index in range(4)
        ]
        exported_total: dict[tuple[int, int, int], D] = {}
        parsed_rows: list[tuple[dict[str, str], int, int, int, bool]] = []
        for row in group:
            row_dof = unsigned(row["row_dof"], "finite row dof")
            column_dof = unsigned(row["column_dof"], "finite column dof")
            step_index = unsigned(row["step_index"], "finite step index")
            audit.require(row_dof < size and column_dof < size and step_index < 4, f"{evaluation_id} finite coordinate bounds")
            audit.require((row_dof, column_dof, step_index) not in seen, f"{evaluation_id} duplicate finite coordinate")
            seen.add((row_dof, column_dof, step_index))
            audit.require(unsigned(row["row_semantic_packet_id"], "finite row packet") == payload.model.packet_ids[row_dof // 3], f"{evaluation_id} finite row semantic")
            audit.require(unsigned(row["column_semantic_packet_id"], "finite column packet") == payload.model.packet_ids[column_dof // 3], f"{evaluation_id} finite column semantic")
            audit.require(unsigned(row["row_axis"], "finite row axis") == row_dof % 3, f"{evaluation_id} finite row axis")
            audit.require(unsigned(row["column_axis"], "finite column axis") == column_dof % 3, f"{evaluation_id} finite column axis")
            ratio = decimal64(row["h_over_l"], "finite h/L")
            close(ratio, HP_STEP_RATIOS[step_index], arithmetic_tolerance(D(6), HP_STEP_RATIOS[step_index], 64), f"{evaluation_id} finite step", audit)
            comparisons = (
                ("material_n_per_m", material[row_dof][column_dof]),
                ("geometric_n_per_m", geometric[row_dof][column_dof]),
                ("total_energy_hessian_n_per_m", total[row_dof][column_dof]),
                ("force_jacobian_n_per_m", -total[row_dof][column_dof]),
            )
            analytic_pass = True
            for field, expected in comparisons:
                analytic_pass &= within(
                    decimal64(row[field], f"{evaluation_id} {field}"),
                    expected,
                    tolerance,
                )
            raw_value = decimal64(row["raw_binary64_force_jacobian_n_per_m"], "raw finite difference")
            raw_residual = decimal64(row["raw_gradient_residual_n_per_m"], "raw finite residual")
            independent_raw = D.from_float(raw_matrices[step_index][row_dof][column_dof])
            raw_tolerance = arithmetic_tolerance(
                dimension,
                max(abs(raw_value), abs(independent_raw), matrix_scale),
                1048576,
            )
            audit.require(
                within(raw_value, independent_raw, raw_tolerance),
                f"{evaluation_id} independently reproduced binary64 finite difference {row_dof},{column_dof},{step_index}",
            )
            audit.require(
                within(
                    raw_residual,
                    raw_value + total[row_dof][column_dof],
                    raw_tolerance,
                ),
                f"{evaluation_id} raw finite residual {row_dof},{column_dof},{step_index}",
            )
            decomposition = decimal64(row["decomposition_residual_n_per_m"], "finite decomposition")
            symmetry = decimal64(row["symmetry_residual_n_per_m"], "finite symmetry")
            exported_tolerance = decimal64(row["tolerance_n_per_m"], "finite tolerance")
            close(
                exported_tolerance,
                tolerance,
                arithmetic_tolerance(D(6), max(exported_tolerance, tolerance), 16),
                f"{evaluation_id} finite registered tolerance",
                audit,
            )
            expected_decomposition = abs(
                decimal64(row["total_energy_hessian_n_per_m"], "finite total")
                - decimal64(row["material_n_per_m"], "finite material")
                - decimal64(row["geometric_n_per_m"], "finite geometric")
            )
            audit.require(
                within(decomposition, expected_decomposition, tolerance),
                f"{evaluation_id} finite decomposition field",
            )
            exported_total[row_dof, column_dof, step_index] = decimal64(
                row["total_energy_hessian_n_per_m"], "finite total cache"
            )
            local_pass = decomposition <= exported_tolerance and symmetry <= exported_tolerance
            parsed_rows.append((row, row_dof, column_dof, step_index, analytic_pass))
            findings.finite(analytic_pass and decomposition <= tolerance and symmetry <= tolerance)
            findings.producer_failure_rows += int(not local_pass)
            if not local_pass:
                findings.finite(False)
            audit.require(
                boolean(row["pass"], f"{evaluation_id} finite pass") == local_pass,
                f"{evaluation_id} finite producer pass mismatch",
            )
        for row, row_dof, column_dof, step_index, _analytic_pass in parsed_rows:
            symmetry = decimal64(row["symmetry_residual_n_per_m"], "finite symmetry")
            expected_symmetry = abs(
                exported_total[row_dof, column_dof, step_index]
                - exported_total[column_dof, row_dof, step_index]
            )
            audit.require(
                within(symmetry, expected_symmetry, tolerance),
                f"{evaluation_id} finite symmetry field {row_dof},{column_dof},{step_index}",
            )
        audit.require(len(seen) == size * size * 4, f"{evaluation_id} complete finite coordinates")
    return len(rows)


def validate_compression(
    raw_root: pathlib.Path,
    payloads: Mapping[str, EvaluationPayload],
    operators: Mapping[str, Operator],
    audit: Audit,
    findings: ScientificFindings,
    *,
    full: bool,
) -> tuple[int, int]:
    rows = read_csv(raw_root / "compression.csv")
    selected_operators = {
        identifier
        for identifier, operator in operators.items()
        if operator.configuration_id in {"exact.tetrahedron_k4", "exact.octahedron_graph"}
    }
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["operator_id"]].append(row)
    audit.require(set(grouped) == selected_operators, "compression operator inventory")
    registered_degeneracies = 0
    hp_checks = 0
    expected_ratios = [D(2) ** -power for power in (0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48)]
    if not full:
        expected_ratios = expected_ratios[:3]
    for operator_id, group in grouped.items():
        group.sort(key=lambda entry: decimal64(entry["length_ratio"], "compression ratio"), reverse=True)
        audit.require(len(group) == len(expected_ratios) + 1, f"{operator_id} compression row inventory")
        positive_rows = [row for row in group if row["status"] == "valid_noncoincident"]
        coincidence_rows = [row for row in group if row["status"] == "coincident_relation"]
        audit.require(len(positive_rows) == len(expected_ratios) and len(coincidence_rows) == 1, f"{operator_id} compression domain inventory")
        for index, (row, expected_ratio) in enumerate(zip(positive_rows, expected_ratios, strict=True)):
            evaluation_id = row["evaluation_id"]
            audit.require(evaluation_id in payloads, f"compression evaluation {evaluation_id}")
            payload = payloads[evaluation_id]
            audit.require(
                row["status"] == payload.row["status"] == "valid_noncoincident",
                f"{evaluation_id} linked positive compression status",
            )
            ratio = decimal64(row["length_ratio"], f"{evaluation_id} compression ratio")
            close(ratio, expected_ratio, arithmetic_tolerance(D(6), expected_ratio, 64), f"{evaluation_id} compression ratio", audit)
            relation_index = unsigned(row["relation_index"], "compression relation")
            audit.require(relation_index == 0, f"{evaluation_id} lowest semantic relation")
            first_id, second_id = payload.model.relations[relation_index]
            require_exact_compression_state(
                payload, expected_ratio, audit, evaluation_id
            )
            evaluation = evaluate(payload.model, payload.current)
            actual_ratio = evaluation.lengths[relation_index] / payload.model.reference_lengths[relation_index]
            ratio_pass = within(
                actual_ratio,
                expected_ratio,
                arithmetic_tolerance(D(6), expected_ratio, 131072),
            )
            registered = index <= 8
            audit.require(boolean(row["registered_domain_row"], "registered compression") == registered, f"{evaluation_id} registered compression flag")
            material, geometric, total = tangent_decomposition(payload.model, payload.current)
            recorded_force_norm = decimal64(row["force_norm_n"], f"{evaluation_id} force norm")
            independent_force_norm = norm(force_vector(payload.model, payload.current))
            dimension = scale_dimension(len(payload.model.packet_ids), len(payload.model.relations))
            h_scale = max_abs(
                value
                for matrix_row in payload.operator.parent_h
                for value in matrix_row
            )
            reference_force_bound = arithmetic_tolerance(
                dimension,
                h_scale * max(payload.model.reference_lengths),
                65536,
            )
            tolerance = max(
                arithmetic_tolerance(
                    dimension,
                    max(abs(recorded_force_norm), independent_force_norm, TINY64),
                    262144,
                ),
                reference_force_bound
                * D(3 * len(payload.model.packet_ids)).sqrt(),
            )
            force_metric_pass = within(recorded_force_norm, independent_force_norm, tolerance)
            if registered:
                findings.energy(ratio_pass and force_metric_pass)
            minimum_length = decimal64(row["minimum_length_m"], f"{evaluation_id} minimum length")
            audit.require(
                within(
                    minimum_length,
                    min(evaluation.lengths),
                    arithmetic_tolerance(
                        dimension,
                        max(minimum_length, min(evaluation.lengths), TINY64),
                        131072,
                    ),
                ),
                f"{evaluation_id} minimum length diagnostic",
            )
            tangent_metric_pass = True
            representation_tangent_bound = (
                reference_force_bound
                * dimension
                / max(min(evaluation.lengths), TINY64)
            )
            for field, expected in (
                ("material_tangent_norm_n_per_m", sum((value * value for matrix_row in material for value in matrix_row), D(0)).sqrt()),
                ("geometric_tangent_norm_n_per_m", sum((value * value for matrix_row in geometric for value in matrix_row), D(0)).sqrt()),
                ("total_tangent_norm_n_per_m", sum((value * value for matrix_row in total for value in matrix_row), D(0)).sqrt()),
            ):
                tangent_metric_pass &= within(
                    decimal64(row[field], f"{evaluation_id} {field}"),
                    expected,
                    max(
                        arithmetic_tolerance(
                            dimension, max(TINY64, expected), 262144
                        ),
                        representation_tangent_bound,
                    ),
                )
            if registered:
                findings.finite(tangent_metric_pass)
            binary64_gradient = decimal64(row["binary64_gradient_error_n"], f"{evaluation_id} binary64 gradient")
            ulp_sensitivity = decimal64(row["ulp_coordinate_sensitivity_n"], f"{evaluation_id} ulp sensitivity")
            expected_binary64_gradient, expected_ulp_sensitivity, expected_adjacent = (
                binary64_compression_diagnostics(payload, float(expected_ratio))
            )
            binary_diagnostic_tolerance = arithmetic_tolerance(
                dimension,
                max(
                    abs(binary64_gradient),
                    abs(expected_binary64_gradient),
                    abs(ulp_sensitivity),
                    abs(expected_ulp_sensitivity),
                    independent_force_norm,
                    TINY64,
                ),
                1048576,
            )
            audit.require(
                within(binary64_gradient, expected_binary64_gradient, binary_diagnostic_tolerance),
                f"{evaluation_id} independently reproduced binary64 collapse gradient",
            )
            audit.require(
                within(ulp_sensitivity, expected_ulp_sensitivity, binary_diagnostic_tolerance),
                f"{evaluation_id} independently reproduced one-ulp sensitivity",
            )
            independent_condition = independent_condition_estimate(total, dimension)
            if row["condition_estimate"] == "unresolved":
                audit.require(independent_condition is None, f"{evaluation_id} condition classification")
                condition_resolved = False
            else:
                condition = decimal64(row["condition_estimate"], f"{evaluation_id} condition")
                audit.require(independent_condition is not None, f"{evaluation_id} condition classification")
                relative_condition_error = abs(condition - independent_condition) / max(TINY64, independent_condition)
                audit.require(
                    relative_condition_error <= D("1e-8") and condition >= 0,
                    f"{evaluation_id} condition estimate",
                )
                condition_resolved = True

            # Independent collapse gradient direction: a deterministic full
            # packet direction, with steps scaled to the current minimum
            # positive relation length so no sample crosses coincidence.
            hp_error, hp_allowed, hp_raw_converged = (
                high_precision_compression_gradient(
                    payload, evaluation, first_id, second_id
                )
            )
            hp_checks += 1
            findings.inconclusive(
                hp_raw_converged,
                "compression_directional_raw_nonconvergence",
            )
            exported_adjacent = boolean(row["adjacent_length_resolved"], "adjacent length resolved")
            audit.require(
                exported_adjacent == expected_adjacent,
                f"{evaluation_id} independently reproduced adjacent-length status",
            )
            degeneracy_pass = (
                condition_resolved
                and hp_raw_converged
                and hp_error <= hp_allowed
                and (not registered or expected_adjacent)
            )
            if registered:
                if not findings.degeneracy(degeneracy_pass):
                    registered_degeneracies += 1
            producer_pass = (not registered or exported_adjacent)
            findings.producer_failure_rows += int(not producer_pass)
            if not producer_pass:
                findings.degeneracy(False)
            audit.require(
                boolean(row["pass"], f"{evaluation_id} compression pass") == producer_pass,
                f"{evaluation_id} compression producer gate mismatch",
            )
        coincidence = coincidence_rows[0]
        audit.require(coincidence["evaluation_id"] in payloads, f"{operator_id} coincidence evaluation")
        audit.require(
            unsigned(coincidence["relation_index"], "coincidence relation index") == 0
            and decimal64(coincidence["length_ratio"], "coincidence length ratio") == 0,
            f"{operator_id} registered coincidence relation",
        )
        coincidence_payload = payloads[coincidence["evaluation_id"]]
        audit.require(
            coincidence["status"] == coincidence_payload.row["status"]
            == "coincident_relation",
            f"{operator_id} linked coincidence status",
        )
        require_exact_compression_state(
            coincidence_payload, D(0), audit, coincidence["evaluation_id"]
        )
        audit.require(not boolean(coincidence["registered_domain_row"], "coincidence registered row"), f"{operator_id} coincidence not positive domain")
        audit.require(
            all(
                coincidence[field] == "not_emitted"
                for field in (
                    "minimum_length_m", "force_norm_n",
                    "material_tangent_norm_n_per_m", "geometric_tangent_norm_n_per_m",
                    "total_tangent_norm_n_per_m", "condition_estimate",
                    "binary64_gradient_error_n", "ulp_coordinate_sensitivity_n",
                )
            ),
            f"{operator_id} coincidence diagnostics not emitted",
        )
        audit.require(not boolean(coincidence["adjacent_length_resolved"], "coincidence adjacent"), f"{operator_id} coincidence adjacent false")
        audit.require(boolean(coincidence["pass"], "coincidence pass"), f"{operator_id} coincidence failed closed")
    return len(rows), registered_degeneracies


def rotation_matrix_decimal() -> tuple[tuple[D, D, D], ...]:
    axis_float = [1.0, 2.0, 3.0]
    magnitude = math.sqrt(sum(value * value for value in axis_float))
    axis = [value / magnitude for value in axis_float]
    cosine = math.cos(0.731)
    sine = math.sin(0.731)
    one_minus = 1.0 - cosine
    x, y, z = axis
    matrix = (
        (cosine + x * x * one_minus, x * y * one_minus - z * sine, x * z * one_minus + y * sine),
        (y * x * one_minus + z * sine, cosine + y * y * one_minus, y * z * one_minus - x * sine),
        (z * x * one_minus - y * sine, z * y * one_minus + x * sine, cosine + z * z * one_minus),
    )
    return tuple(tuple(D.from_float(value) for value in row) for row in matrix)


def block_transform_matrix(
    matrix: Sequence[Sequence[D]], rotation: Sequence[Sequence[D]], scale: D
) -> list[list[D]]:
    packet_count = len(matrix) // 3
    result = [[D(0) for _ in range(len(matrix))] for _ in range(len(matrix))]
    for packet_row in range(packet_count):
        for packet_column in range(packet_count):
            block = [
                [matrix[3 * packet_row + i][3 * packet_column + j] for j in range(3)]
                for i in range(3)
            ]
            transformed = matmul(rotation, matmul(block, transpose(rotation)))
            for i in range(3):
                for j in range(3):
                    result[3 * packet_row + i][3 * packet_column + j] = scale * transformed[i][j]
    return result


def validate_metamorphic(
    raw_root: pathlib.Path,
    payloads: Mapping[str, EvaluationPayload],
    relation_rows: Mapping[str, list[dict[str, str]]],
    operators: Mapping[str, Operator],
    audit: Audit,
    findings: ScientificFindings,
    *,
    full: bool,
) -> int:
    rows = read_csv(raw_root / "metamorphic.csv")
    expected_probes = {
        "current_translation",
        "common_rotation",
        "common_rotation_translation",
        "similarity_half",
        "similarity_two",
        "packet_reverse",
        "packet_splitmix",
        "relation_reverse",
        "relation_splitmix",
        "id_reverse",
        "id_cyclic",
        "id_sha256",
        "endpoint_reverse",
    }
    if not full:
        expected_probes = {
            "current_translation", "common_rotation",
            "common_rotation_translation",
        }
    counts: dict[str, set[str]] = defaultdict(set)
    operator_indices = canonical_operator_indices(payloads)
    rotation = rotation_matrix_decimal()
    identity = tuple(
        tuple(D(1) if row == column else D(0) for column in range(3))
        for row in range(3)
    )
    for row in rows:
        baseline_id = row["baseline_evaluation_id"]
        probe_id = row["probe_evaluation_id"]
        probe = row["probe"]
        audit.require(baseline_id in payloads and probe_id in payloads, f"metamorphic evaluation {probe_id}")
        baseline = payloads[baseline_id]
        candidate = payloads[probe_id]
        audit.require(baseline.operator.identifier == candidate.operator.identifier, f"metamorphic operator {probe_id}")
        audit.require(probe in expected_probes, f"metamorphic probe {probe}")
        audit.require(
            probe not in counts[baseline.operator.identifier],
            f"duplicate metamorphic probe {baseline.operator.identifier}/{probe}",
        )
        counts[baseline.operator.identifier].add(probe)
        packet_map = parse_map(row["packet_coordinate_map"], f"{probe_id} packet map")
        relation_map = parse_map(row["relation_coordinate_map"], f"{probe_id} relation map")
        audit.require(len(packet_map) == len(baseline.model.packet_ids), f"{probe_id} packet map size")
        audit.require(len(relation_map) == len(baseline.model.relations), f"{probe_id} relation map size")
        audit.require(
            set(packet_map) == set(range(len(packet_map)))
            and set(packet_map.values()) == set(range(len(packet_map))),
            f"{probe_id} packet coordinate bijection",
        )
        audit.require(set(relation_map) == set(range(len(relation_map))) and set(relation_map.values()) == set(range(len(relation_map))), f"{probe_id} relation coordinate bijection")
        operator_index = operator_indices[baseline.operator.identifier]
        packet_count = len(baseline.model.packet_ids)
        relation_count = len(baseline.model.relations)
        packet_new_to_old = list(range(packet_count))
        relation_new_to_old = list(range(relation_count))
        if probe == "packet_reverse":
            packet_new_to_old.reverse()
        elif probe == "packet_splitmix":
            packet_new_to_old = deterministic_permutation(
                packet_count, operator_index + 901
            )
        elif probe == "relation_reverse":
            relation_new_to_old.reverse()
        elif probe == "relation_splitmix":
            relation_new_to_old = deterministic_permutation(
                relation_count, operator_index + 1901
            )
        expected_packet_map = old_to_new_map(packet_new_to_old)
        expected_relation_map = old_to_new_map(relation_new_to_old)
        transformed_h = [
            [
                baseline.model.h[relation_new_to_old[i]][relation_new_to_old[j]]
                for j in range(relation_count)
            ]
            for i in range(relation_count)
        ]
        expected_h_digest = metamorphic_h_sha256(transformed_h)
        audit.require(
            row["transformed_h_sha256"] == expected_h_digest,
            f"{probe_id} transformed H digest",
        )
        base_actual_ids = list(baseline.emitted_actual_ids)
        expected_actual_ids = [base_actual_ids[index] for index in packet_new_to_old]
        expected_semantic_ids = [
            baseline.emitted_semantic_ids[index] for index in packet_new_to_old
        ]
        if probe in {"id_reverse", "id_cyclic", "id_sha256"}:
            targets = list(base_actual_ids)
            if probe == "id_reverse":
                targets.reverse()
            elif probe == "id_cyclic":
                targets = targets[1:] + targets[:1]
            else:
                targets.sort(
                    key=lambda packet_id: hashlib.sha256(
                        f"{packet_id}.{SEED}".encode("ascii")
                    ).hexdigest()
                )
            renaming = dict(zip(base_actual_ids, targets, strict=True))
            expected_actual_ids = [renaming[packet_id] for packet_id in base_actual_ids]
            expected_semantic_ids = list(baseline.emitted_semantic_ids)
            canonical_new_ids = sorted(expected_actual_ids)
            expected_packet_map = {
                old_index: canonical_new_ids.index(renaming[base_actual_ids[old_index]])
                for old_index in range(packet_count)
            }
        audit.require(packet_map == expected_packet_map, f"{probe_id} registered packet map")
        audit.require(relation_map == expected_relation_map, f"{probe_id} registered relation map")
        audit.require(
            list(candidate.emitted_actual_ids) == expected_actual_ids
            and list(candidate.emitted_semantic_ids) == expected_semantic_ids,
            f"{probe_id} submitted packet order/ID transform",
        )
        probe_relations = sorted(
            relation_rows.get(probe_id, []),
            key=lambda entry: unsigned(entry["relation_index"], "metamorphic relation index"),
        )
        audit.require(len(probe_relations) == relation_count, f"{probe_id} relation transform inventory")
        for new_index, relation_row in enumerate(probe_relations):
            first_actual = unsigned(relation_row["first_id"], "metamorphic first ID")
            second_actual = unsigned(relation_row["second_id"], "metamorphic second ID")
            semantic_edge = (
                candidate.actual_to_semantic[first_actual],
                candidate.actual_to_semantic[second_actual],
            )
            expected_edge = baseline.model.relations[relation_new_to_old[new_index]]
            if probe == "endpoint_reverse":
                expected_edge = (expected_edge[1], expected_edge[0])
            audit.require(
                semantic_edge == expected_edge,
                f"{probe_id} registered relation ordering/orientation {new_index}",
            )
        scale = decimal64(row["scale"], f"{probe_id} scale")
        if probe == "similarity_half":
            expected_scale = D("0.5")
        elif probe == "similarity_two":
            expected_scale = D(2)
        else:
            expected_scale = D(1)
        close(scale, expected_scale, arithmetic_tolerance(D(6), expected_scale, 64), f"{probe_id} scale declaration", audit)
        base_eval = evaluate(baseline.model, baseline.current)
        probe_eval = evaluate(candidate.model, candidate.current)
        expected_energy_ratio = expected_scale * expected_scale
        actual_energy_ratio = probe_eval.energy / base_eval.energy
        energy_residual = abs(probe_eval.energy - expected_energy_ratio * base_eval.energy)
        if probe in {"common_rotation", "common_rotation_translation"}:
            q_matrix = rotation
        else:
            q_matrix = identity
        dimension = scale_dimension(
            len(baseline.model.packet_ids), len(baseline.model.relations)
        )
        translation = (
            (D.from_float(7.0 / 13.0), D.from_float(-5.0 / 11.0), D.from_float(3.0 / 17.0))
            if probe in {"current_translation", "common_rotation_translation"}
            else (D(0), D(0), D(0))
        )
        coordinate_scale = max(
            max_abs(value for point in baseline.current.values() for value in point),
            max_abs(value for point in candidate.current.values() for value in point),
            TINY64,
        )
        velocity_scale = max(
            max_abs(value for vector in baseline.velocity.values() for value in vector),
            max_abs(value for vector in candidate.velocity.values() for value in vector),
            TINY64,
        )
        coordinate_tolerance = arithmetic_tolerance(dimension, coordinate_scale, 131072)
        velocity_tolerance = arithmetic_tolerance(dimension, velocity_scale, 131072)
        for packet_id in baseline.model.packet_ids:
            expected_point = tuple(
                expected_scale * dot(q_matrix[axis], baseline.current[packet_id])
                + translation[axis]
                for axis in range(3)
            )
            expected_velocity = tuple(
                expected_scale * dot(q_matrix[axis], baseline.velocity[packet_id])
                for axis in range(3)
            )
            audit.require(
                max_abs(
                    candidate.current[packet_id][axis] - expected_point[axis]
                    for axis in range(3)
                ) <= coordinate_tolerance,
                f"{probe_id} registered coordinate transform",
            )
            audit.require(
                max_abs(
                    candidate.velocity[packet_id][axis] - expected_velocity[axis]
                    for axis in range(3)
                ) <= velocity_tolerance,
                f"{probe_id} registered velocity transform",
            )
        expected_forces = {
            packet_id: tuple(
                expected_scale * dot(q_matrix[axis], base_eval.forces[packet_id])
                for axis in range(3)
            )
            for packet_id in baseline.model.packet_ids
        }
        force_residual = max(
            vector_norm_decimal(
                tuple(
                    probe_eval.forces[packet_id][axis]
                    - expected_forces[packet_id][axis]
                    for axis in range(3)
                )
            )
            for packet_id in baseline.model.packet_ids
        )
        conjugate_residual = max_abs(
            probe_eval.conjugates[index] - expected_scale * base_eval.conjugates[index]
            for index in range(len(base_eval.conjugates))
        )
        _base_material, _base_geometric, base_tangent = tangent_decomposition(
            baseline.model, baseline.current
        )
        _probe_material, _probe_geometric, probe_tangent = tangent_decomposition(
            candidate.model, candidate.current
        )
        expected_tangent = block_transform_matrix(base_tangent, q_matrix, D(1))
        tangent_residual = max_abs(
            probe_tangent[i][j] - expected_tangent[i][j]
            for i in range(len(base_tangent))
            for j in range(len(base_tangent))
        )
        energy_tolerance = decimal64(row["energy_tolerance_j"], f"{probe_id} energy tolerance")
        force_tolerance = decimal64(row["force_tolerance_n"], f"{probe_id} force tolerance")
        tangent_tolerance = decimal64(row["tangent_tolerance_n_per_m"], f"{probe_id} tangent tolerance")
        conjugate_tolerance = decimal64(row["conjugate_tolerance_n"], f"{probe_id} conjugate tolerance")
        ratio_tolerance = decimal64(row["scaling_ratio_tolerance"], f"{probe_id} ratio tolerance")
        expected_energy_tolerance = arithmetic_tolerance(
            dimension,
            max(expected_energy_ratio * abs(base_eval.energy), abs(probe_eval.energy), TINY64),
            65536,
        )
        expected_force_scale = max(
            max(
                vector_norm_decimal(expected_forces[packet_id])
                for packet_id in baseline.model.packet_ids
            ),
            max(
                vector_norm_decimal(probe_eval.forces[packet_id])
                for packet_id in baseline.model.packet_ids
            ),
            TINY64,
        )
        expected_force_tolerance = arithmetic_tolerance(
            dimension,
            expected_force_scale,
            65536,
        )
        expected_tangent_tolerance = arithmetic_tolerance(
            dimension,
            max(
                max_abs(value for matrix_row in base_tangent for value in matrix_row),
                max_abs(value for matrix_row in probe_tangent for value in matrix_row),
                TINY64,
            ),
            262144,
        )
        expected_conjugate_tolerance = arithmetic_tolerance(
            dimension,
            max(
                expected_scale * max_abs(base_eval.conjugates),
                max_abs(probe_eval.conjugates),
                TINY64,
            ),
            65536,
        )
        expected_ratio_tolerance = arithmetic_tolerance(
            dimension,
            D(1),
            131072,
        )
        for actual_tolerance, expected_tolerance, label in (
            (energy_tolerance, expected_energy_tolerance, "energy"),
            (force_tolerance, expected_force_tolerance, "force"),
            (tangent_tolerance, expected_tangent_tolerance, "tangent"),
            (conjugate_tolerance, expected_conjugate_tolerance, "conjugate"),
            (ratio_tolerance, expected_ratio_tolerance, "ratio"),
        ):
            close(
                actual_tolerance,
                expected_tolerance,
                arithmetic_tolerance(D(6), max(actual_tolerance, expected_tolerance), 16),
                f"{probe_id} {label} tolerance scale",
                audit,
            )
        exported_expected_ratio = decimal64(row["expected_energy_ratio"], f"{probe_id} expected ratio")
        exported_actual_ratio = decimal64(row["actual_energy_ratio"], f"{probe_id} actual ratio")
        exported_energy_residual = decimal64(row["energy_residual_j"], f"{probe_id} energy residual")
        exported_force_residual = decimal64(row["force_covariance_residual_n"], f"{probe_id} force residual")
        exported_conjugate_residual = decimal64(row["relation_conjugate_residual_n"], f"{probe_id} conjugate residual")
        exported_tangent_residual = decimal64(row["tangent_covariance_residual_n_per_m"], f"{probe_id} tangent residual")
        energy_pass = (
            within(
                exported_expected_ratio,
                expected_energy_ratio,
                ratio_tolerance,
            )
            and within(exported_actual_ratio, actual_energy_ratio, ratio_tolerance)
            and within(exported_energy_residual, energy_residual, energy_tolerance)
            and within(exported_force_residual, force_residual, force_tolerance)
            and within(exported_conjugate_residual, conjugate_residual, conjugate_tolerance)
            and abs(actual_energy_ratio - expected_energy_ratio) <= ratio_tolerance
            and energy_residual <= energy_tolerance
            and force_residual <= force_tolerance
            and conjugate_residual <= conjugate_tolerance
        )
        finite_pass = (
            within(exported_tangent_residual, tangent_residual, tangent_tolerance)
            and tangent_residual <= tangent_tolerance
        )
        findings.energy(energy_pass)
        findings.finite(finite_pass)
        producer_energy_pass = (
            exported_energy_residual <= energy_tolerance
            and exported_force_residual <= force_tolerance
            and exported_conjugate_residual <= conjugate_tolerance
            and abs(exported_actual_ratio - exported_expected_ratio) <= ratio_tolerance
        )
        producer_finite_pass = exported_tangent_residual <= tangent_tolerance
        producer_pass = producer_energy_pass and producer_finite_pass
        findings.producer_failure_rows += int(not producer_pass)
        if not producer_energy_pass:
            findings.energy(False)
        if not producer_finite_pass:
            findings.finite(False)
        audit.require(
            boolean(row["pass"], f"{probe_id} pass") == producer_pass,
            f"{probe_id} producer metamorphic pass mismatch",
        )
    for operator_id in operators:
        audit.require(counts[operator_id] == expected_probes, f"{operator_id} metamorphic inventory")
    return len(rows)


RAW_SUMMARY_FIELDS = {
    "schema", "seed", "full", "stage_status", "final_decision_emitted",
    "no_promotion", "promotion_permitted", "configuration_count", "operator_count",
    "force_evaluation_count", "valid_evaluation_count", "coincident_failure_count",
    "reference_tangent_row_count", "finite_tangent_row_count", "metamorphic_row_count",
    "compression_row_count", "raw_registered_failures", "exact_coincidence_failed_closed",
    "result_boundary",
}
RAW_PROVENANCE_FIELDS = {
    "schema", "source_sha", "source_branch", "accepted_parent_sha", "parent_evidence_tag",
    "preregistration_commit", "seed", "full", "dirty", "compiler_id", "compiler_version",
    "build_type", "binary64_contract", "inherited_blobs", "symmetric_freeze_contract", "parent_outer_pre_hash",
    "parent_archive_sha256", "parent_bundle_manifest_pre_hash", "parent_table_sha256",
}
FINAL_SUMMARY_FIELDS = {
    "schema", "decision", "no_promotion", "promotion_permitted", "seed", "full",
    "configuration_count", "operator_count", "force_evaluation_count", "valid_evaluation_count",
    "coincident_failure_count", "directional_derivative_row_count",
    "reference_tangent_row_count", "finite_tangent_row_count", "metamorphic_row_count",
    "compression_row_count", "producer_failure_rows", "inconclusive_failure_events", "inconclusive_reasons",
    "energy_gradient_failure_events", "force_conservation_failure_events",
    "finite_consistency_failure_events", "degeneracy_failure_events",
    "all_registered_noncoincident_cases_passed", "exact_coincidence_failed_closed",
    "prohibited_features_absent", "result_boundary",
}
FINAL_PROVENANCE_FIELDS = RAW_PROVENANCE_FIELDS | {
    "materializer_python_version", "high_precision_implementation", "decimal_digits",
    "exact_oracle_pre_hash", "producer_manifest_pre_hash", "producer_tree_sha256",
    "materializer_source_sha",
}


def validate_raw_metadata(
    raw_root: pathlib.Path,
    *,
    allow_dirty: bool,
    audit: Audit,
) -> tuple[dict[str, Any], dict[str, Any]]:
    summary = read_json(raw_root / "raw_summary.json")
    provenance = read_json(raw_root / "raw_provenance.json")
    require_fields(summary, RAW_SUMMARY_FIELDS, "raw summary")
    require_fields(provenance, RAW_PROVENANCE_FIELDS, "raw provenance")
    audit.require(summary["schema"] == RAW_SUMMARY_SCHEMA, "raw summary schema")
    audit.require(provenance["schema"] == RAW_PROVENANCE_SCHEMA, "raw provenance schema")
    for where, value in (("raw summary seed", summary["seed"]), ("raw provenance seed", provenance["seed"])):
        audit.require(type(value) is int and value == SEED, where)
    audit.require(type(summary["full"]) is bool and type(provenance["full"]) is bool and summary["full"] == provenance["full"], "raw full agreement")
    audit.require(summary["stage_status"] == "pending_independent_stage", "raw stage status")
    audit.require(summary["final_decision_emitted"] is False, "raw no final decision")
    audit.require(summary["no_promotion"] == "NO_PROMOTION", "raw NO_PROMOTION token")
    audit.require(summary["promotion_permitted"] is False, "raw promotion forbidden")
    audit.require(summary["result_boundary"] == "NO_PROMOTION to dynamics", "raw result boundary")
    audit.require(provenance["source_branch"] == BRANCH, "raw source branch")
    audit.require(isinstance(provenance["source_sha"], str) and SOURCE_SHA_RE.fullmatch(provenance["source_sha"]) is not None, "raw source SHA")
    audit.require(provenance["accepted_parent_sha"] == PARENT_SHA, "raw accepted parent")
    audit.require(provenance["parent_evidence_tag"] == PARENT_EVIDENCE, "raw parent evidence")
    audit.require(provenance["preregistration_commit"] == PREREGISTRATION_COMMIT, "raw preregistration commit")
    audit.require(
        provenance["binary64_contract"]
        == "iec559_size8_digits53_explicit_order_fp_contract_off_v1",
        "raw binary64 contract",
    )
    audit.require(provenance["inherited_blobs"] == INHERITED_BLOBS, "raw inherited blobs")
    audit.require(provenance["symmetric_freeze_contract"] == SYMMETRIC_FREEZE_CONTRACT, "raw symmetric freeze contract")
    audit.require(provenance["parent_outer_pre_hash"] == PARENT_OUTER_PRE_HASH, "raw parent outer pre-hash")
    audit.require(provenance["parent_archive_sha256"] == PARENT_ARCHIVE_SHA256, "raw parent archive")
    audit.require(provenance["parent_bundle_manifest_pre_hash"] == PARENT_BUNDLE_MANIFEST_PRE_HASH, "raw parent manifest")
    if provenance["full"]:
        audit.require(provenance["parent_table_sha256"] == PARENT_TABLE_SHA256, "raw parent tables")
    else:
        audit.require(provenance["parent_table_sha256"] == "builtin_smoke", "raw smoke parent marker")
    audit.require(type(provenance["dirty"]) is bool, "raw dirty type")
    if not allow_dirty:
        audit.require(provenance["dirty"] is False, "raw source dirty")
    for field in (
        "configuration_count", "operator_count", "force_evaluation_count", "valid_evaluation_count",
        "coincident_failure_count", "reference_tangent_row_count", "finite_tangent_row_count",
        "metamorphic_row_count", "compression_row_count", "raw_registered_failures",
    ):
        audit.require(type(summary[field]) is int and summary[field] >= 0, f"raw summary {field}")
    audit.require(type(summary["exact_coincidence_failed_closed"]) is bool, "raw coincidence flag")
    return summary, provenance


def producer_tree_sha256(raw_root: pathlib.Path) -> str:
    tree = canonical_tree(raw_root)
    return hashlib.sha256(manifest_preimage(tree)).hexdigest()


def write_csv(path: pathlib.Path, header: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: pathlib.Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def seal_manifest(root: pathlib.Path, payload_files: set[str], schema: str) -> dict[str, Any]:
    hashes = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in sorted(payload_files)
    }
    value = {
        "schema": schema,
        "file_sha256": hashes,
        "pre_hash_sha256": hashlib.sha256(manifest_preimage(hashes)).hexdigest(),
    }
    write_json(root / "manifest.json", value)
    return value


def raw_pipeline(
    raw_root: pathlib.Path,
    *,
    allow_dirty: bool,
) -> tuple[
    Audit,
    dict[str, Configuration],
    dict[str, Operator],
    dict[str, EvaluationPayload],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, int],
    ScientificFindings,
]:
    audit = Audit()
    findings = ScientificFindings()
    validate_manifest(raw_root, RAW_BASE_FILES, RAW_MANIFEST_SCHEMA, audit)
    raw_summary, raw_provenance = validate_raw_metadata(
        raw_root, allow_dirty=allow_dirty, audit=audit
    )
    configurations = parse_configurations(raw_root, audit)
    operators = parse_operators(raw_root, configurations, audit)
    payloads, relation_rows, packet_rows = parse_evaluation_payloads(
        raw_root, configurations, operators, audit
    )
    full = bool(raw_summary["full"])
    validate_registered_evaluation_inventory(
        payloads, operators, full=full, audit=audit
    )
    valid_count, coincident_count = validate_force_evaluations(
        payloads, relation_rows, packet_rows, audit, findings
    )
    reference_count = validate_reference_tangent(
        raw_root, payloads, operators, audit, findings, full=full
    )
    raw_finite_count = validate_raw_finite_tangent(
        raw_root, payloads, audit, findings, full=full
    )
    metamorphic_count = validate_metamorphic(
        raw_root, payloads, relation_rows, operators, audit, findings, full=full
    )
    compression_count, degeneracy_failures = validate_compression(
        raw_root, payloads, operators, audit, findings, full=full
    )
    independent_directional = compute_independent_directional_rows(
        payloads, packet_rows, audit, findings, full=full
    )
    independent_finite = compute_independent_finite_tangent_rows(
        raw_root, payloads, audit, findings, full=full
    )
    counts = {
        "configuration_count": len(configurations),
        "operator_count": len(operators),
        "force_evaluation_count": len(payloads),
        "valid_evaluation_count": valid_count,
        "coincident_failure_count": coincident_count,
        "reference_tangent_row_count": reference_count,
        "raw_finite_tangent_row_count": raw_finite_count,
        "metamorphic_row_count": metamorphic_count,
        "compression_row_count": compression_count,
        "degeneracy_failures": findings.degeneracy_failures,
    }
    for field in (
        "configuration_count", "operator_count", "force_evaluation_count",
        "valid_evaluation_count", "coincident_failure_count", "reference_tangent_row_count",
        "finite_tangent_row_count", "metamorphic_row_count", "compression_row_count",
    ):
        expected = counts["raw_finite_tangent_row_count"] if field == "finite_tangent_row_count" else counts[field]
        audit.require(raw_summary[field] == expected, f"raw summary count {field}")
    audit.require(
        raw_summary["raw_registered_failures"] == findings.producer_failure_rows,
        "raw registered failure count",
    )
    audit.require(raw_summary["exact_coincidence_failed_closed"] is True, "raw coincidence gate")
    if raw_provenance["full"]:
        audit.require(set(configurations) == FULL_IDS, "full configuration inventory")
    return (
        audit,
        configurations,
        operators,
        payloads,
        raw_summary,
        raw_provenance,
        independent_directional,
        independent_finite,
        counts,
        findings,
    )


def materialize_into(
    raw_root: pathlib.Path, output: pathlib.Path, *, allow_dirty: bool
) -> tuple[int, str, str]:
    (
        audit,
        _configurations,
        _operators,
        _payloads,
        raw_summary,
        raw_provenance,
        directional_rows,
        finite_rows,
        counts,
        findings,
    ) = raw_pipeline(raw_root, allow_dirty=allow_dirty)
    if output.exists():
        if not output.is_dir() or any(output.iterdir()):
            reject("materialize staging destination is not an empty directory")
    else:
        output.mkdir(parents=True)
    shutil.copytree(raw_root, output / "producer")
    write_csv(
        output / "independent_directional_derivatives.csv",
        HEADERS["independent_directional_derivatives.csv"],
        directional_rows,
    )
    write_csv(
        output / "independent_finite_tangent.csv",
        HEADERS["independent_finite_tangent.csv"],
        finite_rows,
    )
    decision = findings.decision()
    summary = {
        "schema": SUMMARY_SCHEMA,
        "decision": decision,
        "no_promotion": "NO_PROMOTION",
        "promotion_permitted": False,
        "seed": SEED,
        "full": raw_summary["full"],
        "configuration_count": counts["configuration_count"],
        "operator_count": counts["operator_count"],
        "force_evaluation_count": counts["force_evaluation_count"],
        "valid_evaluation_count": counts["valid_evaluation_count"],
        "coincident_failure_count": counts["coincident_failure_count"],
        "directional_derivative_row_count": len(directional_rows),
        "reference_tangent_row_count": counts["reference_tangent_row_count"],
        "finite_tangent_row_count": len(finite_rows),
        "metamorphic_row_count": counts["metamorphic_row_count"],
        "compression_row_count": counts["compression_row_count"],
        "producer_failure_rows": findings.producer_failure_rows,
        "inconclusive_failure_events": findings.inconclusive_failures,
        "inconclusive_reasons": sorted(findings.inconclusive_reasons),
        "energy_gradient_failure_events": findings.energy_gradient_failures,
        "force_conservation_failure_events": findings.force_conservation_failures,
        "finite_consistency_failure_events": findings.finite_consistency_failures,
        "degeneracy_failure_events": findings.degeneracy_failures,
        "all_registered_noncoincident_cases_passed": (
            findings.inconclusive_failures == 0
            and findings.producer_failure_rows == 0
            and findings.energy_gradient_failures == 0
            and findings.force_conservation_failures == 0
            and findings.finite_consistency_failures == 0
            and findings.degeneracy_failures == 0
        ),
        "exact_coincidence_failed_closed": True,
        "prohibited_features_absent": True,
        "result_boundary": "NO_PROMOTION to dynamics",
    }
    write_json(output / "summary.json", summary)
    canonical_path = pathlib.Path(__file__).resolve().parents[1] / "tests" / "conservative_force_oracle.canonical.json"
    canonical = read_json(canonical_path)
    exact_oracle_pre_hash = canonical.get("result_sha256_before_hash_field")
    if not isinstance(exact_oracle_pre_hash, str) or SHA256_RE.fullmatch(exact_oracle_pre_hash) is None:
        reject("exact oracle canonical pre-hash")
    raw_manifest = read_json(raw_root / "manifest.json")
    provenance = dict(raw_provenance)
    provenance.update(
        {
            "schema": PROVENANCE_SCHEMA,
            "materializer_python_version": platform.python_version(),
            "high_precision_implementation": (
                "independent Decimal-100 reconstruction and degree-3 extrapolation in h^2"
            ),
            "decimal_digits": DIGITS,
            "exact_oracle_pre_hash": exact_oracle_pre_hash,
            "producer_manifest_pre_hash": raw_manifest["pre_hash_sha256"],
            "producer_tree_sha256": producer_tree_sha256(raw_root),
            "materializer_source_sha": raw_provenance["source_sha"],
        }
    )
    write_json(output / "provenance.json", provenance)
    producer_files = {
        f"producer/{name}" for name in RAW_BASE_FILES | {"manifest.json"}
    }
    payload_files = FINAL_ROOT_FILES | producer_files
    manifest = seal_manifest(output, payload_files, MANIFEST_SCHEMA)
    return audit.checks, manifest["pre_hash_sha256"], decision


def materialize(
    raw_root: pathlib.Path, output: pathlib.Path, *, allow_dirty: bool
) -> tuple[int, str, str]:
    raw_root = raw_root.resolve()
    output = output.absolute()
    parent = output.parent.resolve()
    if output.exists():
        reject("materialize destination already exists")
    if not parent.is_dir():
        reject("materialize destination parent does not exist")
    staging = pathlib.Path(
        tempfile.mkdtemp(prefix=f".{output.name}.materialize-", dir=parent)
    ).resolve()
    if staging.parent != parent:
        reject("materialize staging escaped destination parent")
    try:
        result = materialize_into(raw_root, staging, allow_dirty=allow_dirty)
        if output.exists():
            reject("materialize destination appeared before publish")
        os.rename(staging, output)
        return result
    except BaseException:
        if staging.exists() and staging.parent == parent:
            shutil.rmtree(staging)
        raise


def final_payload_files() -> set[str]:
    return FINAL_ROOT_FILES | {
        f"producer/{name}" for name in RAW_BASE_FILES | {"manifest.json"}
    }


def validate_final_bundle(
    root: pathlib.Path,
    *,
    allow_dirty: bool,
) -> tuple[int, dict[str, Any]]:
    outer_audit = Audit()
    validate_manifest(root, final_payload_files(), MANIFEST_SCHEMA, outer_audit)
    (
        raw_audit,
        configurations,
        operators,
        payloads,
        raw_summary,
        raw_provenance,
        expected_directional,
        expected_finite,
        counts,
        findings,
    ) = raw_pipeline(root / "producer", allow_dirty=allow_dirty)
    directional = read_csv(root / "independent_directional_derivatives.csv")
    finite = read_csv(root / "independent_finite_tangent.csv")
    outer_audit.require(directional == expected_directional, "independent directional table reconstruction")
    outer_audit.require(finite == expected_finite, "independent finite tangent table reconstruction")

    summary = read_json(root / "summary.json")
    provenance = read_json(root / "provenance.json")
    require_fields(summary, FINAL_SUMMARY_FIELDS, "final summary")
    require_fields(provenance, FINAL_PROVENANCE_FIELDS, "final provenance")
    outer_audit.require(summary["schema"] == SUMMARY_SCHEMA, "final summary schema")
    outer_audit.require(provenance["schema"] == PROVENANCE_SCHEMA, "final provenance schema")
    decision = findings.decision()
    outer_audit.require(summary["decision"] == decision and decision in ALLOWED_DECISIONS, "final decision reconstruction")
    outer_audit.require(summary["no_promotion"] == "NO_PROMOTION", "final NO_PROMOTION token")
    outer_audit.require(summary["promotion_permitted"] is False, "final promotion forbidden")
    outer_audit.require(summary["seed"] == SEED and summary["full"] == raw_summary["full"], "final seed/full")
    expected_counts = {
        "configuration_count": len(configurations),
        "operator_count": len(operators),
        "force_evaluation_count": len(payloads),
        "valid_evaluation_count": counts["valid_evaluation_count"],
        "coincident_failure_count": counts["coincident_failure_count"],
        "directional_derivative_row_count": len(expected_directional),
        "reference_tangent_row_count": counts["reference_tangent_row_count"],
        "finite_tangent_row_count": len(expected_finite),
        "metamorphic_row_count": counts["metamorphic_row_count"],
        "compression_row_count": counts["compression_row_count"],
        "producer_failure_rows": findings.producer_failure_rows,
        "inconclusive_failure_events": findings.inconclusive_failures,
        "energy_gradient_failure_events": findings.energy_gradient_failures,
        "force_conservation_failure_events": findings.force_conservation_failures,
        "finite_consistency_failure_events": findings.finite_consistency_failures,
        "degeneracy_failure_events": findings.degeneracy_failures,
    }
    for field, expected in expected_counts.items():
        outer_audit.require(summary[field] == expected, f"final summary {field}")
    outer_audit.require(
        summary["inconclusive_reasons"] == sorted(findings.inconclusive_reasons),
        "final inconclusive reasons",
    )
    expected_noncoincident = (
        findings.inconclusive_failures == 0
        and findings.producer_failure_rows == 0
        and findings.energy_gradient_failures == 0
        and findings.force_conservation_failures == 0
        and findings.finite_consistency_failures == 0
        and findings.degeneracy_failures == 0
    )
    outer_audit.require(
        summary["all_registered_noncoincident_cases_passed"] is expected_noncoincident,
        "final noncoincident gate",
    )
    outer_audit.require(summary["exact_coincidence_failed_closed"] is True, "final coincidence gate")
    outer_audit.require(summary["prohibited_features_absent"] is True, "final prohibited-feature gate")
    outer_audit.require(summary["result_boundary"] == "NO_PROMOTION to dynamics", "final boundary")

    for field in RAW_PROVENANCE_FIELDS - {"schema"}:
        outer_audit.require(provenance[field] == raw_provenance[field], f"final/raw provenance {field}")
    outer_audit.require(provenance["materializer_source_sha"] == provenance["source_sha"], "materializer/source SHA")
    outer_audit.require(provenance["decimal_digits"] == DIGITS, "final decimal digits")
    outer_audit.require(
        provenance["high_precision_implementation"]
        == "independent Decimal-100 reconstruction and degree-3 extrapolation in h^2",
        "final high precision implementation",
    )
    outer_audit.require(
        isinstance(provenance["materializer_python_version"], str)
        and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", provenance["materializer_python_version"])
        is not None,
        "materializer Python version",
    )
    canonical = read_json(
        pathlib.Path(__file__).resolve().parents[1]
        / "tests"
        / "conservative_force_oracle.canonical.json"
    )
    outer_audit.require(
        provenance["exact_oracle_pre_hash"]
        == canonical["result_sha256_before_hash_field"],
        "final exact oracle binding",
    )
    producer_manifest = read_json(root / "producer" / "manifest.json")
    outer_audit.require(
        provenance["producer_manifest_pre_hash"]
        == producer_manifest["pre_hash_sha256"],
        "final producer manifest binding",
    )
    outer_audit.require(
        provenance["producer_tree_sha256"] == producer_tree_sha256(root / "producer"),
        "final producer tree binding",
    )
    return outer_audit.checks + raw_audit.checks, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize_parser = subparsers.add_parser("materialize")
    materialize_parser.add_argument("--producer", type=pathlib.Path, required=True)
    materialize_parser.add_argument("--output", type=pathlib.Path, required=True)
    materialize_parser.add_argument("--allow-dirty", action="store_true")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--bundle", type=pathlib.Path, required=True)
    validate_parser.add_argument("--compare", type=pathlib.Path)
    validate_parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "materialize":
            checks, pre_hash, decision = materialize(
                args.producer.resolve(), args.output.resolve(), allow_dirty=args.allow_dirty
            )
            print(
                "CONSERVATIVE FORCE BUNDLE MATERIALIZED: "
                f"{checks} independent checks; pre_hash={pre_hash}; "
                f"decision={decision}"
            )
            print("NO_PROMOTION")
            return 0
        bundle = args.bundle.resolve()
        if args.compare is not None:
            compare = args.compare.resolve()
            if bundle == compare:
                reject("twin bundle paths must be distinct")
            if canonical_tree(bundle) != canonical_tree(compare):
                reject("twin bundles are not byte-for-byte identical")
        checks, summary = validate_final_bundle(bundle, allow_dirty=args.allow_dirty)
        if args.compare is not None:
            print("byte comparison: PASS")
        print(
            "CONSERVATIVE FORCE BUNDLE VALID: "
            f"{checks} checks; decision={summary['decision']}"
        )
        print("NO_PROMOTION")
        return 0
    except (OSError, ValidationError, KeyError, ValueError, ArithmeticError) as error:
        print(f"CONSERVATIVE FORCE BUNDLE INVALID: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
