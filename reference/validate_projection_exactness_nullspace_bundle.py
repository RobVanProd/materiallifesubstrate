#!/usr/bin/env python3
"""Independent validator for Projection Exactness + Nullspace evidence.

The C++ producer and this validator deliberately share no implementation.
For every exported assembly this script reconstructs the Gram matrix and RHS
from particle masses and sparse sampling rows, evaluates the analytic affine
witness, separates solver backward/forward/reconstruction errors, and checks
null modes at both centers and basis gradients.  It validates evidence
integrity and preregistered decisions; it cannot promote a mechanics method.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SEED = 260828
SUMMARY_SCHEMA = "mls.projection-exactness-nullspace.summary.v1"
MANIFEST_SCHEMA = "mls.projection-exactness-nullspace.manifest.v1"
SOURCE_PARENT_SHA = "beac8861314e9a2c18e59fd65c426cfdbf75882c"
EPS64 = Decimal(2) ** -52
EPS_DD = Decimal(2) ** -104
MIN_NORMAL = Decimal.from_float(sys.float_info.min)
FORWARD_LIMIT = Decimal("5e-10")
PCG_LEGACY_RESIDUAL_LIMIT = Decimal.from_float(5.0e-12)
GRADIENT_ABSOLUTE_FLOOR = Decimal("1e-10")
GRADIENT_BOUND_MULTIPLIER = Decimal("1e4")
DECIMAL_PRECISION = 100
getcontext().prec = DECIMAL_PRECISION

EXPECTED_TOLERANCES = {
    "gradient_absolute_floor_per_s": "1e-10",
    "gradient_visible_bound_multiplier": "1e4",
    "high_precision_normalized_backward_formula": "2^12*n*2^-104",
    "high_precision_normalized_forward": "5e-10",
    "high_precision_normalized_reconstruction": "5e-10",
    "null_normalized_formula": "512*max(P,N)*2^-52",
}
PRIOR_FAILURE_SYSTEM_IDS = frozenset({
    "main_general_affine_t0_l1_p000_p012_sppp",
    "main_general_affine_t0_l1_p049_001_083_p210_sppm",
})
SMOKE_SYSTEM_IDS = (
    "main_general_affine_t0_l1_p000_p012_sppp",
    "main_rigid_rotation_t4_l1_p000_p012_sppp",
    "full_rank_micro_p000_p012_sppp",
    "singular_ppc1_p049_001_083_p012_sppp",
)
CPP_NULL_STATUS_RANK_METHOD = (
    "deterministic binary64 Householder column-pivoted QR of sqrt(W)S; "
    "numerical threshold=128*max(P,N)*epsilon*first pivot by frozen default; "
    "not certification"
)

SYSTEM_FIELDS = tuple(
    "system_id,case_class,field,phase,orientation,level,time_quanta,"
    "time_quantum_numerator_s,time_quantum_denominator_s,time_s,h_m,dx_p_m,"
    "kg_per_mass_quantum,exact_mass_quanta,grid_origin_x_m,grid_origin_y_m,"
    "grid_origin_z_m,particle_count,node_count,matrix_nnz,rank_upper_bound,"
    "max_stencil_size,max_particle_contributions_per_node,max_matrix_row_nnz,"
    "a00_per_s,a01_per_s,a02_per_s,a10_per_s,a11_per_s,a12_per_s,a20_per_s,"
    "a21_per_s,a22_per_s,b0_m_per_s,b1_m_per_s,b2_m_per_s,"
    "full_solve_applicable,high_precision_applicable,nullspace_applicable,"
    "assembly_exported,assembly_payload_sha256,input_checkpoint_sha256_before,"
    "input_checkpoint_sha256_after,diagnostics_read_only_exact".split(",")
)
PARTICLE_FIELDS = tuple(
    "system_id,particle_index,particle_id,mass_kg,x_m,y_m,z_m,vx_m_per_s,"
    "vy_m_per_s,vz_m_per_s".split(",")
)
NODE_FIELDS = tuple(
    "system_id,node_index,grid_i,grid_j,grid_k,x_m,y_m,z_m,"
    "analytic_gx_m_per_s,analytic_gy_m_per_s,analytic_gz_m_per_s,"
    "pcg_available,pcg_vhat_x_m_per_s,pcg_vhat_y_m_per_s,"
    "pcg_vhat_z_m_per_s,hp_available,hp_vhat_x_m_per_s,"
    "hp_vhat_y_m_per_s,hp_vhat_z_m_per_s".split(",")
)
STENCIL_FIELDS = tuple(
    "system_id,particle_index,node_index,weight,grad_x_per_m,grad_y_per_m,"
    "grad_z_per_m".split(",")
)
MATRIX_FIELDS = tuple("system_id,row_node_index,column_node_index,value_kg".split(","))
RHS_FIELDS = tuple("system_id,node_index,component,value_kg_m_per_s".split(","))
WITNESS_FIELDS = tuple(
    "system_id,component,mg_minus_q_l2_kg_m_per_s,mgq_denominator_kg_m_per_s,"
    "normalized_mg_minus_q,mgq_roundoff_bound,mgq_pass,"
    "sg_minus_v_l2_m_per_s_sqrt_kg,"
    "sgv_denominator_m_per_s_sqrt_kg,normalized_sg_minus_v,sgv_roundoff_bound,"
    "sgv_pass,partition_max_residual,partition_roundoff_bound,partition_pass,"
    "linear_reproduction_max_residual_m,linear_reproduction_roundoff_bound_m,"
    "linear_reproduction_pass,gradient_partition_max_residual_per_m,"
    "gradient_partition_roundoff_bound_per_m,gradient_partition_pass,pass"
    .split(",")
)
SOLVE_FIELDS = tuple(
    "system_id,component,status,accuracy_classification,solver,iterations,"
    "legacy_residual_applicable,legacy_normalized_residual,"
    "legacy_normalized_residual_threshold,legacy_termination_reason,"
    "backward_residual_l2_kg_m_per_s,backward_denominator_kg_m_per_s,"
    "normalized_backward_residual,grid_forward_lumped_numerator_m_per_s_sqrt_kg,"
    "grid_forward_lumped_denominator_m_per_s_sqrt_kg,normalized_forward_error,"
    "reconstruction_mass_numerator_m_per_s_sqrt_kg,"
    "reconstruction_mass_denominator_m_per_s_sqrt_kg,"
    "normalized_reconstruction_error,raw_condition_value,raw_condition_kind,"
    "preconditioned_condition_value,preconditioned_condition_kind,"
    "condition_times_normalized_residual".split(",")
)
HIGH_PRECISION_FIELDS = tuple(
    "system_id,component,status,method,precision_bits,decimal_digits,rank,"
    "rank_method,rank_is_certified,regularization,node_dropping,basis_altered,"
    "promotion_eligible,pivot_threshold_relative,smallest_pivot_abs_kg,"
    "largest_pivot_abs_kg,backward_residual_l2_kg_m_per_s,"
    "backward_denominator_kg_m_per_s,normalized_backward_residual,"
    "grid_forward_lumped_numerator_m_per_s_sqrt_kg,"
    "grid_forward_lumped_denominator_m_per_s_sqrt_kg,normalized_forward_error,"
    "reconstruction_mass_numerator_m_per_s_sqrt_kg,"
    "reconstruction_mass_denominator_m_per_s_sqrt_kg,"
    "normalized_reconstruction_error,condition_value,condition_kind".split(",")
)
HIGH_PRECISION_PIVOT_FIELDS = tuple(
    "system_id,step,original_row_index,original_column_index,pivot_abs_kg,"
    "pivot_threshold_kg,status,promotion_eligible".split(",")
)
NULLSPACE_MODE_FIELDS = tuple(
    "system_id,mode_index,node_index,z_value_m_per_s,method,singular_value_sqrt_kg,"
    "representative_value_m_per_s,shifted_value_m_per_s".split(",")
)
NULLSPACE_STATUS_FIELDS = tuple(
    "system_id,status,node_count,particle_count,threshold_rank,rank_available,"
    "rank_method,rank_is_certified,nullity,numerical_rank_threshold_sqrt_kg,"
    "largest_qr_diagonal_sqrt_kg,smallest_accepted_qr_diagonal_sqrt_kg,"
    "constructed_mode_count,basis_complete,promotion_eligible".split(",")
)
NULLSPACE_METRIC_FIELDS = tuple(
    "system_id,mode_index,rank,rank_method,rank_is_certified,"
    "mz_l2_kg_m_per_s,mz_denominator_kg_m_per_s,mz_normalized,"
    "sz_l2_m_per_s,sz_denominator_m_per_s,sz_normalized,"
    "gradient_max_per_s,gradient_rms_per_s,gradient_roundoff_bound_per_s,"
    "visibility_ratio,gradient_visible,alpha_dimensionless,representative_component,"
    "representative_kind,base_residual_normalized,shifted_residual_normalized,"
    "residual_change_l2_kg_m_per_s,residual_change_denominator_kg_m_per_s,"
    "residual_change_normalized,"
    "reconstruction_delta_normalized,phase,orientation,promotion_eligible,pass"
    .split(",")
)

CSV_SCHEMAS = {
    "systems.csv": SYSTEM_FIELDS,
    "particles.csv": PARTICLE_FIELDS,
    "nodes.csv": NODE_FIELDS,
    "stencils.csv": STENCIL_FIELDS,
    "matrix.csv": MATRIX_FIELDS,
    "rhs.csv": RHS_FIELDS,
    "witness.csv": WITNESS_FIELDS,
    "solve_diagnostics.csv": SOLVE_FIELDS,
    "high_precision.csv": HIGH_PRECISION_FIELDS,
    "high_precision_pivots.csv": HIGH_PRECISION_PIVOT_FIELDS,
    "nullspace_modes.csv": NULLSPACE_MODE_FIELDS,
    "nullspace_status.csv": NULLSPACE_STATUS_FIELDS,
    "nullspace_metrics.csv": NULLSPACE_METRIC_FIELDS,
}
REQUIRED_FILES = (*CSV_SCHEMAS, "summary.json")
CONDITION_KINDS = {
    "dense_numerical_estimate", "ritz_lanczos_estimate",
    "high_precision_inverse_norm_estimate", "unavailable",
}
PCG_CONDITION_KINDS = {
    "dense_numerical_estimate", "ritz_lanczos_estimate", "unavailable",
}
STATUS_VALUES = {
    "solved", "empty", "structurally_rank_deficient",
    "numerically_rank_deficient", "ill_conditioned", "breakdown",
    "iteration_limit", "residual_failed", "numerical_failure", "numerical_overflow",
    "size_limit", "not_run_witness_failure",
}
NULLSPACE_STATUS_VALUES = {
    "analyzed", "empty", "size_limit", "numerical_failure",
    "not_run_witness_failure",
}
SHA64_RE = re.compile(r"[0-9a-f]{64}\Z")
SHA40_RE = re.compile(r"[0-9a-f]{40}\Z")
INT_RE = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")
HEX_RE = re.compile(r"-?0x[0-9a-f]+(?:\.[0-9a-f]+)?p[+-][0-9]+\Z")
DEC_RE = re.compile(
    r"-?(?:0(?:\.[0-9]+)?|[1-9](?:\.[0-9]+)?)e[+-](?:0|[1-9][0-9]*)\Z"
)


class InvalidBundle(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidBundle(message)


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def reject_json_constant(value: str) -> None:
    raise InvalidBundle(f"nonstandard JSON constant {value!r}")


def read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_json_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InvalidBundle(f"cannot read strict JSON {path.name}: {error}") from error
    require(isinstance(value, dict), f"{path.name}: root must be an object")
    return value


def read_csv(path: Path, fields: Sequence[str]) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            require(tuple(reader.fieldnames or ()) == tuple(fields), f"{path.name}: header mismatch")
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        raise InvalidBundle(f"cannot read {path.name}: {error}") from error
    for line, row in enumerate(rows, 2):
        require(None not in row, f"{path.name}:{line}: excess column")
        require(all(value is not None for value in row.values()), f"{path.name}:{line}: missing column")
    return rows


def integer(text: str, where: str, *, minimum: int | None = None) -> int:
    require(INT_RE.fullmatch(text) is not None, f"{where}: noncanonical integer {text!r}")
    value = int(text)
    require(minimum is None or value >= minimum, f"{where}: integer below {minimum}")
    return value


def boolean(text: str, where: str) -> bool:
    require(text in {"true", "false"}, f"{where}: expected true/false")
    return text == "true"


def binary64(text: str, where: str, *, optional: bool = False) -> Decimal | None:
    if text == "NA":
        require(optional, f"{where}: unexpected NA")
        return None
    require(HEX_RE.fullmatch(text) is not None, f"{where}: expected lowercase hexadecimal binary64")
    try:
        value = float.fromhex(text)
    except ValueError as error:
        raise InvalidBundle(f"{where}: invalid hexadecimal binary64") from error
    require(math.isfinite(value), f"{where}: nonfinite binary64")
    require(text == value.hex(), f"{where}: noncanonical hexadecimal binary64 {text!r}")
    return Decimal.from_float(value)


def decimal_number(text: str, where: str, *, optional: bool = False) -> Decimal | None:
    if text == "NA":
        require(optional, f"{where}: unexpected NA")
        return None
    require(DEC_RE.fullmatch(text) is not None, f"{where}: noncanonical decimal {text!r}")
    value = Decimal(text)
    require(value.is_finite(), f"{where}: nonfinite decimal")
    return value


def numeric(text: str, where: str, *, optional: bool = False) -> Decimal | None:
    if text == "NA":
        require(optional, f"{where}: unexpected NA")
        return None
    if text.startswith(("0x", "-0x")):
        return binary64(text, where)
    return decimal_number(text, where)


def l2(values: Iterable[Decimal]) -> Decimal:
    return sum((value * value for value in values), Decimal(0)).sqrt()


def gamma(operations: int) -> Decimal:
    require(operations > 0, "gamma operation count must be positive")
    denominator = Decimal(1) - Decimal(operations) * EPS64
    require(denominator > 0, "gamma denominator is nonpositive")
    return Decimal(operations) * EPS64 / denominator


def close_reported(
    actual: Decimal,
    expected: Decimal,
    where: str,
    *,
    factor: Decimal = Decimal("5e-11"),
    absolute_allowance: Decimal = Decimal(0),
) -> None:
    scale = max(abs(expected), Decimal("1e-90"))
    require(abs(actual - expected) <= factor * scale + absolute_allowance + Decimal("1e-90"),
            f"{where}: {actual} does not reproduce {expected}")


def manifest_payload(hashes: Mapping[str, str]) -> bytes:
    lines = ["{", '  "algorithm": "SHA-256",', '  "files": {']
    names = sorted(hashes)
    for index, name in enumerate(names):
        comma = "," if index + 1 < len(names) else ""
        lines.append(f"    {json.dumps(name)}: {json.dumps(hashes[name])}{comma}")
    lines.extend(("  },", f'  "schema": {json.dumps(MANIFEST_SCHEMA)}', "}"))
    return "\n".join(lines).encode()


def validate_manifest(bundle: Path) -> None:
    require(bundle.is_dir() and not bundle.is_symlink(), "bundle root must be a real directory")
    expected_children = {*REQUIRED_FILES, "manifest.json"}
    children = list(bundle.iterdir())
    require({path.name for path in children} == expected_children,
            "unexpected/missing bundle child")
    require(all(path.is_file() and not path.is_symlink() for path in children),
            "every bundle child must be a regular non-link file")
    manifest = read_json(bundle / "manifest.json")
    require(set(manifest) == {"algorithm", "files", "pre_hash_sha256", "schema"},
            "manifest key set mismatch")
    require(manifest.get("schema") == MANIFEST_SCHEMA, "manifest schema mismatch")
    require(manifest.get("algorithm") == "SHA-256", "manifest algorithm mismatch")
    files = manifest.get("files")
    require(isinstance(files, dict), "manifest files must be an object")
    require(set(files) == set(REQUIRED_FILES), "manifest file set mismatch")
    hashes: dict[str, str] = {}
    for name in REQUIRED_FILES:
        digest = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
        require(files.get(name) == digest, f"manifest digest mismatch for {name}")
        hashes[name] = digest
    require(manifest.get("pre_hash_sha256") == hashlib.sha256(manifest_payload(hashes)).hexdigest(),
            "manifest pre-hash mismatch")


def assembly_digest(system_id: str, tables: Mapping[str, list[dict[str, str]]]) -> str:
    digest = hashlib.sha256()
    digest.update(b"MLS-PROJECTION-EXACTNESS-ASSEMBLY-v1\n")
    for name in ("particles.csv", "nodes.csv", "stencils.csv", "matrix.csv", "rhs.csv"):
        for row in tables[name]:
            if row["system_id"] != system_id:
                continue
            digest.update(name.encode("ascii"))
            for field in CSV_SCHEMAS[name]:
                digest.update(b"\0")
                digest.update(row[field].encode("utf-8"))
            digest.update(b"\n")
    return digest.hexdigest()


def group_unique(rows: Sequence[dict[str, str]], key_fields: Sequence[str], name: str) -> dict[tuple[str, ...], dict[str, str]]:
    result: dict[tuple[str, ...], dict[str, str]] = {}
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        require(key not in result, f"{name}: duplicate key {key}")
        result[key] = row
    return result


def matmul3(lhs: Sequence[Sequence[float]], rhs: Sequence[Sequence[float]]) -> list[list[float]]:
    result = [[0.0] * 3 for _ in range(3)]
    for row in range(3):
        for column in range(3):
            for inner in range(3):
                result[row][column] += lhs[row][inner] * rhs[inner][column]
    return result


def matvec3(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> list[float]:
    return [
        matrix[row][0] * vector[0]
        + matrix[row][1] * vector[1]
        + matrix[row][2] * vector[2]
        for row in range(3)
    ]


def transpose3(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    return [[matrix[column][row] for column in range(3)] for row in range(3)]


def inverse3(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    a = matrix
    determinant = (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )
    require(math.isfinite(determinant) and determinant != 0.0, "registered affine map is singular")
    adjugate = [
        [a[1][1] * a[2][2] - a[1][2] * a[2][1],
         a[0][2] * a[2][1] - a[0][1] * a[2][2],
         a[0][1] * a[1][2] - a[0][2] * a[1][1]],
        [a[1][2] * a[2][0] - a[1][0] * a[2][2],
         a[0][0] * a[2][2] - a[0][2] * a[2][0],
         a[0][2] * a[1][0] - a[0][0] * a[1][2]],
        [a[1][0] * a[2][1] - a[1][1] * a[2][0],
         a[0][1] * a[2][0] - a[0][0] * a[2][1],
         a[0][0] * a[1][1] - a[0][1] * a[1][0]],
    ]
    return [[value * (1.0 / determinant) for value in row] for row in adjugate]


def registered_orientation(name: str) -> list[list[float]]:
    if name == "p012_sppp":
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    require(name == "p210_sppm", f"unregistered orientation {name!r}")
    return [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]


def registered_phase(name: str) -> list[float]:
    if name == "p000":
        return [0.0, 0.0, 0.0]
    require(name == "p049_001_083", f"unregistered phase {name!r}")
    return [0.49, 0.01, 0.83]


def registered_base_field(name: str) -> tuple[list[list[float]], list[float]]:
    if name == "translation":
        return [[0.0] * 3 for _ in range(3)], [9.0 / 20.0, -3.0 / 10.0, 1.0 / 5.0]
    if name == "rigid_rotation":
        omega = [3.0 / 10.0, -1.0 / 5.0, 2.0 / 5.0]
        return [
            [0.0, -omega[2], omega[1]],
            [omega[2], 0.0, -omega[0]],
            [-omega[1], omega[0], 0.0],
        ], [3.0 / 20.0, -1.0 / 10.0, 1.0 / 20.0]
    require(name == "general_affine", f"unregistered affine field {name!r}")
    return [
        [3.0 / 20.0, 2.0 / 5.0, 7.0 / 20.0],
        [1.0 / 4.0, -1.0 / 10.0, -11.0 / 20.0],
        [-3.0 / 10.0, 7.0 / 10.0, 1.0 / 5.0],
    ], [111.0 / 125.0, -129.0 / 200.0, -74.0 / 125.0]


def registered_expectations() -> list[dict[str, Any]]:
    levels = (
        (0, 0.5, 0.25, 4, 64),
        (1, 0.25, 0.125, 8, 8),
        (2, 0.125, 0.0625, 16, 1),
    )
    result: list[dict[str, Any]] = []
    for field in ("translation", "rigid_rotation", "general_affine"):
        for time_quanta in (0, 4):
            for phase in ("p000", "p049_001_083"):
                for orientation in ("p012_sppp", "p210_sppm"):
                    for level, h, dx, particle_axis, mass_quanta in levels:
                        hp = field == "general_affine" and time_quanta == 0 and level == 1 and (
                            (phase, orientation) == ("p000", "p012_sppp")
                            or (phase, orientation) == ("p049_001_083", "p210_sppm")
                        )
                        null = field == "general_affine" and level == 0
                        result.append({
                            "system_id": f"main_{field}_t{time_quanta}_l{level}_{phase}_{orientation}",
                            "case_class": "main", "field": field, "phase": phase,
                            "orientation": orientation, "level": level,
                            "time_quanta": time_quanta, "h": h, "dx": dx,
                            "particle_axis": particle_axis, "mass_quanta": mass_quanta,
                            "hp": hp, "null": null, "exported": hp or null,
                        })
    for phase, orientation in (
        ("p000", "p012_sppp"),
        ("p049_001_083", "p210_sppm"),
    ):
        result.append({
            "system_id": f"full_rank_micro_{phase}_{orientation}",
            "case_class": "full_rank_micro", "field": "general_affine",
            "phase": phase, "orientation": orientation, "level": 0,
            "time_quanta": 0, "h": 0.5, "dx": 0.125,
            "particle_axis": 8, "mass_quanta": 8,
            "hp": True, "null": False, "exported": True,
        })
    for orientation in ("p012_sppp", "p210_sppm"):
        result.append({
            "system_id": f"singular_ppc1_p049_001_083_{orientation}",
            "case_class": "singular_ppc1", "field": "general_affine",
            "phase": "p049_001_083", "orientation": orientation, "level": 1,
            "time_quanta": 0, "h": 0.25, "dx": 0.25,
            "particle_axis": 4, "mass_quanta": 64,
            "hp": False, "null": True, "exported": True,
        })
    return result


def expected_field_and_origin(expected: Mapping[str, Any]) -> tuple[list[list[float]], list[float], list[float]]:
    rotation = registered_orientation(str(expected["orientation"]))
    base_a, base_b = registered_base_field(str(expected["field"]))
    initial_a = matmul3(matmul3(rotation, base_a), transpose3(rotation))
    initial_b = matvec3(rotation, base_b)
    time_s = float(expected["time_quanta"]) * (1.0 / 160.0)
    deformation = [[(1.0 if row == column else 0.0) + time_s * initial_a[row][column]
                    for column in range(3)] for row in range(3)]
    inverse = inverse3(deformation)
    field_a = matmul3(initial_a, inverse)
    field_b = matvec3(inverse, initial_b)
    phase = [float(expected["h"]) * value for value in registered_phase(str(expected["phase"]))]
    origin = matvec3(rotation, phase)
    return field_a, field_b, origin


def close_binary_registration(actual: Decimal, expected: float, where: str) -> None:
    expected_decimal = Decimal.from_float(expected)
    allowance = Decimal(128) * EPS64 * max(abs(expected_decimal), Decimal(1))
    require(abs(actual - expected_decimal) <= allowance,
            f"{where}: {actual} differs from registered {expected_decimal}")


def validate_registered_matrix(
    systems: Sequence[dict[str, str]], oracle_fixture: bool,
    smoke_provisional: bool = False,
) -> None:
    if oracle_fixture:
        require(len(systems) == 2, "oracle fixture must contain two systems")
        require(sum(boolean(row["high_precision_applicable"], "hp applicable") for row in systems) == 1,
                "oracle fixture HP selection mismatch")
        require(sum(boolean(row["nullspace_applicable"], "null applicable") for row in systems) == 1,
                "oracle fixture null selection mismatch")
        require(all(boolean(row["assembly_exported"], "assembly exported") for row in systems),
                "oracle fixture must export both systems")
        return
    all_expected_rows = registered_expectations()
    expected_by_id = {
        str(expected["system_id"]): expected for expected in all_expected_rows
    }
    expected_rows = (
        [expected_by_id[system_id] for system_id in SMOKE_SYSTEM_IDS]
        if smoke_provisional else all_expected_rows
    )
    expected_count = 4 if smoke_provisional else 76
    require(len(systems) == len(expected_rows) == expected_count,
            f"expected {expected_count} systems, found {len(systems)}")
    require([row["system_id"] for row in systems] == [str(row["system_id"]) for row in expected_rows],
            "registered system IDs/order mismatch")
    for row, expected in zip(systems, expected_rows, strict=True):
        sid = row["system_id"]
        for field in ("case_class", "field", "phase", "orientation"):
            require(row[field] == str(expected[field]), f"{sid}: registered {field} mismatch")
        require(integer(row["level"], f"{sid} level") == expected["level"],
                f"{sid}: registered level mismatch")
        require(integer(row["time_quanta"], f"{sid} time") == expected["time_quanta"],
                f"{sid}: registered time mismatch")
        require(boolean(row["full_solve_applicable"], f"{sid} PCG selection"),
                f"{sid}: every registered system requires the PCG control")
        require(boolean(row["high_precision_applicable"], f"{sid} HP selection") == expected["hp"],
                f"{sid}: exact HP4 selection mismatch")
        require(boolean(row["nullspace_applicable"], f"{sid} null selection") == expected["null"],
                f"{sid}: exact null10 selection mismatch")
        require(boolean(row["assembly_exported"], f"{sid} export selection") == expected["exported"],
                f"{sid}: exact HP4/null10 export union mismatch")


def validate_system_metadata(systems: Sequence[dict[str, str]], tables: Mapping[str, list[dict[str, str]]], oracle_fixture: bool) -> None:
    seen: set[str] = set()
    raw_names = ("particles.csv", "nodes.csv", "stencils.csv", "matrix.csv", "rhs.csv")
    registered = {str(value["system_id"]): value for value in registered_expectations()}
    for row in systems:
        sid = row["system_id"]
        require(sid and sid not in seen, f"duplicate/empty system_id {sid!r}")
        seen.add(sid)
        time_quanta = integer(row["time_quanta"], f"{sid} time_quanta", minimum=0)
        numerator = integer(row["time_quantum_numerator_s"], f"{sid} time numerator", minimum=1)
        denominator = integer(row["time_quantum_denominator_s"], f"{sid} time denominator", minimum=1)
        time_s = binary64(row["time_s"], f"{sid} time_s")
        require(time_s == Decimal.from_float(float(time_quanta * numerator / denominator)), f"{sid}: physical time mismatch")
        h = binary64(row["h_m"], f"{sid} h_m") or Decimal(0)
        dx = binary64(row["dx_p_m"], f"{sid} dx_p_m") or Decimal(0)
        mass_quantum = binary64(row["kg_per_mass_quantum"], f"{sid} kg_per_mass_quantum") or Decimal(0)
        require(h > 0 and dx > 0 and mass_quantum > 0, f"{sid}: h/dx/mass quantum must be positive")
        particle_count = integer(row["particle_count"], f"{sid} particle_count", minimum=1)
        node_count = integer(row["node_count"], f"{sid} node_count", minimum=1)
        integer(row["matrix_nnz"], f"{sid} matrix nnz", minimum=1)
        require(integer(row["rank_upper_bound"], f"{sid} rank upper", minimum=1) == min(particle_count, node_count),
                f"{sid}: rank upper bound mismatch")
        require(integer(row["max_stencil_size"], f"{sid} max stencil", minimum=1) <= node_count, f"{sid}: bad max stencil")
        require(integer(row["max_particle_contributions_per_node"], f"{sid} max contributions", minimum=1) <= particle_count,
                f"{sid}: max contributions exceeds particle count")
        require(integer(row["max_matrix_row_nnz"], f"{sid} max row nnz", minimum=1) <= node_count,
                f"{sid}: max row nnz exceeds node count")
        require(integer(row["exact_mass_quanta"], f"{sid} mass quanta", minimum=1) == (particle_count if oracle_fixture else 4096),
                f"{sid}: exact mass registration mismatch")
        if not oracle_fixture:
            expected = registered[sid]
            require((numerator, denominator) == (1, 160), f"{sid}: clock quantum is not 1/160 s")
            close_binary_registration(h, float(expected["h"]), f"{sid} h")
            close_binary_registration(dx, float(expected["dx"]), f"{sid} dx")
            close_binary_registration(mass_quantum, 1.0 / 4096.0, f"{sid} mass quantum")
            require(particle_count == int(expected["particle_axis"]) ** 3,
                    f"{sid}: registered particle count mismatch")
            require(integer(row["max_stencil_size"], f"{sid} max stencil") == 27,
                    f"{sid}: quadratic B-spline stencil size must be 27")
            expected_a, expected_b, expected_origin = expected_field_and_origin(expected)
            for component, field in enumerate(("grid_origin_x_m", "grid_origin_y_m", "grid_origin_z_m")):
                close_binary_registration(binary64(row[field], f"{sid} {field}") or Decimal(0),
                                          expected_origin[component], f"{sid} {field}")
            for matrix_row in range(3):
                for column in range(3):
                    field = f"a{matrix_row}{column}_per_s"
                    close_binary_registration(binary64(row[field], f"{sid} {field}") or Decimal(0),
                                              expected_a[matrix_row][column], f"{sid} {field}")
            for component in range(3):
                field = f"b{component}_m_per_s"
                close_binary_registration(binary64(row[field], f"{sid} {field}") or Decimal(0),
                                          expected_b[component], f"{sid} {field}")
        before, after = row["input_checkpoint_sha256_before"], row["input_checkpoint_sha256_after"]
        require(SHA64_RE.fullmatch(before) is not None and before == after, f"{sid}: checkpoint read-only hash mismatch")
        require(boolean(row["diagnostics_read_only_exact"], f"{sid} read-only"), f"{sid}: diagnostics mutated checkpoint")
        exported = boolean(row["assembly_exported"], f"{sid} assembly exported")
        raw_counts = {name: sum(item["system_id"] == sid for item in tables[name]) for name in raw_names}
        if exported:
            require(SHA64_RE.fullmatch(row["assembly_payload_sha256"]) is not None, f"{sid}: bad assembly digest")
            require(row["assembly_payload_sha256"] == assembly_digest(sid, tables), f"{sid}: assembly payload digest mismatch")
            require(all(count > 0 for count in raw_counts.values()), f"{sid}: incomplete raw assembly export")
        else:
            require(row["assembly_payload_sha256"] == "NA", f"{sid}: nonexported assembly digest must be NA")
            require(all(count == 0 for count in raw_counts.values()), f"{sid}: nonexported assembly leaked raw rows")


def expected_registered_particles(expected: Mapping[str, Any]) -> list[tuple[list[float], list[float], float]]:
    base_a, base_b = registered_base_field(str(expected["field"]))
    rotation = registered_orientation(str(expected["orientation"]))
    spacing = float(expected["dx"])
    time_s = float(expected["time_quanta"]) * (1.0 / 160.0)
    mass = float(expected["mass_quanta"]) * (1.0 / 4096.0)
    result: list[tuple[list[float], list[float], float]] = []
    for ix in range(int(expected["particle_axis"])):
        for iy in range(int(expected["particle_axis"])):
            for iz in range(int(expected["particle_axis"])):
                base_position = [
                    -0.5 + (float(index) + 0.5) * spacing
                    for index in (ix, iy, iz)
                ]
                base_velocity = [
                    value + base_b[row]
                    for row, value in enumerate(matvec3(base_a, base_position))
                ]
                oriented_position = matvec3(rotation, base_position)
                oriented_velocity = matvec3(rotation, base_velocity)
                ballistic = [
                    oriented_position[component] + time_s * oriented_velocity[component]
                    for component in range(3)
                ]
                result.append((ballistic, oriented_velocity, mass))
    return result


def quadratic_axis_samples(position: float, origin: float, spacing: float) -> list[tuple[int, float]]:
    normalized = (position - origin) / spacing
    base = math.floor(normalized - 0.5)
    coordinate = normalized - float(base)
    left = 1.5 - coordinate
    middle = coordinate - 1.0
    right = coordinate - 0.5
    return [
        (base, 0.5 * left * left),
        (base + 1, 0.75 - middle * middle),
        (base + 2, 0.5 * right * right),
    ]


def expected_stencil_indices(
    position: Sequence[Decimal], origin: Sequence[Decimal], spacing: Decimal,
) -> list[tuple[int, int, int]]:
    axes = [
        quadratic_axis_samples(float(position[axis]), float(origin[axis]), float(spacing))
        for axis in range(3)
    ]
    result: list[tuple[int, int, int]] = []
    for ix, wx in axes[0]:
        for iy, wy in axes[1]:
            for iz, wz in axes[2]:
                if wx * wy * wz != 0.0:
                    result.append((ix, iy, iz))
    return result


def quadratic_axis_basis_decimal(
    particle: Decimal, node: Decimal, spacing: Decimal,
) -> tuple[Decimal, Decimal]:
    relative = (particle - node) / spacing
    magnitude = abs(relative)
    if magnitude < Decimal("0.5"):
        return Decimal("0.75") - relative * relative, -Decimal(2) * relative / spacing
    if magnitude < Decimal("1.5"):
        distance = Decimal("1.5") - magnitude
        sign = Decimal(-1) if relative < 0 else Decimal(1)
        return Decimal("0.5") * distance * distance, -distance * sign / spacing
    return Decimal(0), Decimal(0)


def quadratic_basis_decimal(
    particle: Sequence[Decimal], node: Sequence[Decimal], spacing: Decimal,
) -> tuple[Decimal, list[Decimal]]:
    axes = [quadratic_axis_basis_decimal(particle[axis], node[axis], spacing) for axis in range(3)]
    weights = [value[0] for value in axes]
    return (
        weights[0] * weights[1] * weights[2],
        [
            axes[0][1] * weights[1] * weights[2],
            weights[0] * axes[1][1] * weights[2],
            weights[0] * weights[1] * axes[2][1],
        ],
    )


def require_basis_close(actual: Decimal, expected: Decimal, where: str) -> None:
    allowance = Decimal(512) * EPS64 * max(abs(expected), Decimal(1))
    require(abs(actual - expected) <= allowance,
            f"{where}: exported basis value {actual} differs from analytic {expected}")


def validate_exported_system(
    system: Mapping[str, str],
    tables: Mapping[str, list[dict[str, str]]],
    witness_index: Mapping[tuple[str, ...], dict[str, str]],
    solve_index: Mapping[tuple[str, ...], dict[str, str]],
    hp_index: Mapping[tuple[str, ...], dict[str, str]],
) -> dict[str, Any]:
    sid = system["system_id"]
    particles = [row for row in tables["particles.csv"] if row["system_id"] == sid]
    nodes = [row for row in tables["nodes.csv"] if row["system_id"] == sid]
    stencils = [row for row in tables["stencils.csv"] if row["system_id"] == sid]
    matrix_rows = [row for row in tables["matrix.csv"] if row["system_id"] == sid]
    rhs_rows = [row for row in tables["rhs.csv"] if row["system_id"] == sid]
    p_count = integer(system["particle_count"], f"{sid} P")
    n_count = integer(system["node_count"], f"{sid} N")
    require(len(particles) == p_count and len(nodes) == n_count, f"{sid}: particle/node row count mismatch")
    require([integer(row["particle_index"], f"{sid} p index") for row in particles] == list(range(p_count)), f"{sid}: particle order mismatch")
    require([integer(row["node_index"], f"{sid} node index") for row in nodes] == list(range(n_count)), f"{sid}: node order mismatch")
    masses = [binary64(row["mass_kg"], f"{sid} mass") or Decimal(0) for row in particles]
    require(all(value > 0 for value in masses), f"{sid}: nonpositive mass")
    particle_ids = [integer(row["particle_id"], f"{sid} particle ID", minimum=1) for row in particles]
    require(particle_ids == list(range(1, p_count + 1)), f"{sid}: particle IDs/order mismatch")
    positions = [[binary64(row[field], f"{sid} particle position") or Decimal(0) for field in ("x_m", "y_m", "z_m")] for row in particles]
    particle_velocity = [[binary64(row[field], f"{sid} particle velocity") or Decimal(0) for field in ("vx_m_per_s", "vy_m_per_s", "vz_m_per_s")] for row in particles]
    node_positions = [[binary64(row[field], f"{sid} node position") or Decimal(0) for field in ("x_m", "y_m", "z_m")] for row in nodes]
    node_grid = [tuple(integer(row[field], f"{sid} node grid index") for field in ("grid_i", "grid_j", "grid_k")) for row in nodes]
    require(node_grid == sorted(node_grid) and len(set(node_grid)) == n_count,
            f"{sid}: active nodes are not unique lexicographic grid indices")
    analytic = [[binary64(nodes[node][field], f"{sid} analytic g") or Decimal(0) for node in range(n_count)] for field in ("analytic_gx_m_per_s", "analytic_gy_m_per_s", "analytic_gz_m_per_s")]
    for node, row in enumerate(nodes):
        for prefix, available_field, value_fields, parser in (
            ("PCG", "pcg_available", ("pcg_vhat_x_m_per_s", "pcg_vhat_y_m_per_s", "pcg_vhat_z_m_per_s"), binary64),
            ("HP", "hp_available", ("hp_vhat_x_m_per_s", "hp_vhat_y_m_per_s", "hp_vhat_z_m_per_s"), decimal_number),
        ):
            available = boolean(row[available_field], f"{sid} node {node} {prefix} availability")
            if available:
                for field in value_fields:
                    parser(row[field], f"{sid} node {node} {prefix} value")
            else:
                require(all(row[field] == "NA" for field in value_fields),
                        f"{sid}: unavailable {prefix} node has stray values")
    A = [[binary64(system[f"a{row}{column}_per_s"], f"{sid} A") or Decimal(0) for column in range(3)] for row in range(3)]
    b = [binary64(system[f"b{component}_m_per_s"], f"{sid} b") or Decimal(0) for component in range(3)]
    h = binary64(system["h_m"], f"{sid} h") or Decimal(0)
    origin = [binary64(system[field], f"{sid} grid origin") or Decimal(0)
              for field in ("grid_origin_x_m", "grid_origin_y_m", "grid_origin_z_m")]
    for node, index in enumerate(node_grid):
        for component in range(3):
            expected_position = origin[component] + Decimal(index[component]) * h
            require_basis_close(node_positions[node][component], expected_position,
                                f"{sid} node {node} position[{component}]")
    if system["case_class"] in {"main", "full_rank_micro", "singular_ppc1"}:
        expected = {str(value["system_id"]): value for value in registered_expectations()}[sid]
        registered_particles = expected_registered_particles(expected)
        require(len(registered_particles) == p_count, f"{sid}: registered particle lattice size mismatch")
        for particle, (expected_position, expected_velocity, expected_mass) in enumerate(registered_particles):
            close_binary_registration(masses[particle], expected_mass, f"{sid} particle {particle} mass")
            for component in range(3):
                close_binary_registration(positions[particle][component], expected_position[component],
                                          f"{sid} particle {particle} position[{component}]")
                close_binary_registration(particle_velocity[particle][component], expected_velocity[component],
                                          f"{sid} particle {particle} velocity[{component}]")
    expected_total_mass = (binary64(system["kg_per_mass_quantum"], f"{sid} mass quantum") or Decimal(0)) * Decimal(
        integer(system["exact_mass_quanta"], f"{sid} exact mass"))
    require(abs(sum(masses, Decimal(0)) - expected_total_mass) <= Decimal(128) * EPS64 * max(expected_total_mass, Decimal(1)),
            f"{sid}: exported masses do not match exact registered mass")
    S = [[Decimal(0)] * n_count for _ in range(p_count)]
    gradients = [[[Decimal(0)] * 3 for _ in range(n_count)] for _ in range(p_count)]
    seen_stencil: set[tuple[int, int]] = set()
    for row in stencils:
        p = integer(row["particle_index"], f"{sid} stencil p")
        node = integer(row["node_index"], f"{sid} stencil node")
        require(0 <= p < p_count and 0 <= node < n_count and (p, node) not in seen_stencil, f"{sid}: bad/duplicate stencil key")
        seen_stencil.add((p, node))
        weight = binary64(row["weight"], f"{sid} weight") or Decimal(0)
        require(weight > 0, f"{sid}: nonpositive exported weight")
        S[p][node] = weight
        gradients[p][node] = [binary64(row[field], f"{sid} gradient") or Decimal(0) for field in ("grad_x_per_m", "grad_y_per_m", "grad_z_per_m")]
        expected_weight, expected_gradient = quadratic_basis_decimal(
            positions[p], node_positions[node], h)
        require_basis_close(weight, expected_weight, f"{sid} stencil ({p},{node}) weight")
        for component in range(3):
            require_basis_close(gradients[p][node][component], expected_gradient[component],
                                f"{sid} stencil ({p},{node}) gradient[{component}]")
    grid_lookup = {index: node for node, index in enumerate(node_grid)}
    expected_stencil_keys: set[tuple[int, int]] = set()
    expected_node_indices: set[tuple[int, int, int]] = set()
    for particle in range(p_count):
        for index in expected_stencil_indices(positions[particle], origin, h):
            expected_node_indices.add(index)
            require(index in grid_lookup, f"{sid}: analytic stencil node {index} is absent")
            expected_stencil_keys.add((particle, grid_lookup[index]))
    require(set(node_grid) == expected_node_indices, f"{sid}: active-node set differs from analytic B-spline support")
    require(seen_stencil == expected_stencil_keys, f"{sid}: stencil sparsity differs from analytic B-spline support")
    stencil_sizes = [sum(value != 0 for value in row) for row in S]
    contributions = [sum(S[p][node] != 0 for p in range(p_count)) for node in range(n_count)]
    require(max(stencil_sizes) == integer(system["max_stencil_size"], f"{sid} max stencil"), f"{sid}: max stencil mismatch")
    require(max(contributions) == integer(system["max_particle_contributions_per_node"], f"{sid} max contributions"), f"{sid}: max contribution mismatch")
    M_export: dict[tuple[int, int], Decimal] = {}
    for row in matrix_rows:
        key = (integer(row["row_node_index"], f"{sid} M row"), integer(row["column_node_index"], f"{sid} M column"))
        require(0 <= key[0] < n_count and 0 <= key[1] < n_count and key not in M_export, f"{sid}: bad/duplicate M key")
        value = binary64(row["value_kg"], f"{sid} M value") or Decimal(0)
        require(value != 0, f"{sid}: sparse M contains zero")
        M_export[key] = value
    require(len(M_export) == integer(system["matrix_nnz"], f"{sid} matrix nnz"), f"{sid}: matrix nnz mismatch")
    max_row_nnz = max(sum((row, column) in M_export for column in range(n_count)) for row in range(n_count))
    require(max_row_nnz == integer(system["max_matrix_row_nnz"], f"{sid} max row nnz"), f"{sid}: max row nnz mismatch")
    M_rebuilt: dict[tuple[int, int], Decimal] = defaultdict(Decimal)
    q_rebuilt = [[Decimal(0)] * n_count for _ in range(3)]
    for p in range(p_count):
        support = [node for node in range(n_count) if S[p][node] != 0]
        for i in support:
            q_factor = masses[p] * S[p][i]
            for component in range(3):
                q_rebuilt[component][i] += q_factor * particle_velocity[p][component]
            for j in support:
                M_rebuilt[(i, j)] += masses[p] * S[p][i] * S[p][j]
    require(set(M_rebuilt) == set(M_export), f"{sid}: rebuilt/exported M sparsity mismatch")
    assembly_relative = max(
        abs(M_export[key] - value) / max(abs(value), MIN_NORMAL) for key, value in M_rebuilt.items()
    )
    require(assembly_relative <= Decimal(64) * gamma(max(contributions)), f"{sid}: M assembly exceeds roundoff budget")
    rhs_export: dict[tuple[int, int], Decimal] = {}
    for row in rhs_rows:
        key = (integer(row["component"], f"{sid} rhs component"), integer(row["node_index"], f"{sid} rhs node"))
        require(0 <= key[0] < 3 and 0 <= key[1] < n_count and key not in rhs_export, f"{sid}: bad/duplicate rhs key")
        rhs_export[key] = binary64(row["value_kg_m_per_s"], f"{sid} rhs") or Decimal(0)
    require(len(rhs_export) == 3 * n_count, f"{sid}: incomplete rhs")
    rhs_scale = max(max(abs(value) for value in q_rebuilt[c]) for c in range(3))
    rhs_error = max(abs(rhs_export[(c, node)] - q_rebuilt[c][node]) for c in range(3) for node in range(n_count))
    require(rhs_error <= Decimal(64) * gamma(max(contributions)) * max(rhs_scale, MIN_NORMAL), f"{sid}: q assembly exceeds roundoff budget")
    for node in range(n_count):
        expected = [sum((A[row][column] * node_positions[node][column] for column in range(3)), b[row]) for row in range(3)]
        for component in range(3):
            require(abs(analytic[component][node] - expected[component]) <= Decimal(64) * gamma(4) * max(abs(expected[component]), Decimal(1)), f"{sid}: analytic nodal field mismatch")
    for p in range(p_count):
        expected = [sum((A[row][column] * positions[p][column] for column in range(3)), b[row]) for row in range(3)]
        for component in range(3):
            require(abs(particle_velocity[p][component] - expected[component]) <= Decimal(64) * gamma(4) * max(abs(expected[component]), Decimal(1)), f"{sid}: particle affine field mismatch")
    partition = max(abs(sum(row, Decimal(0)) - 1) for row in S)
    linear = max(l2(sum((S[p][node] * node_positions[node][c] for node in range(n_count)), Decimal(0)) - positions[p][c] for c in range(3)) for p in range(p_count))
    derivative_partition = max(l2(sum((gradients[p][node][c] for node in range(n_count)), Decimal(0)) for c in range(3)) for p in range(p_count))
    max_point_norm = max(l2(point) for point in positions)
    h = binary64(system["h_m"], f"{sid} h") or Decimal(0)
    s, c, r = max(stencil_sizes), max(contributions), max_row_nnz
    expected_bounds = {
        "partition": Decimal(32) * gamma(s),
        "linear": Decimal(64) * gamma(s) * max(Decimal(1), h, max_point_norm),
        "gradient": Decimal(64) * gamma(3 * s) * max(Decimal(1), Decimal(1) / h),
        "sgv": Decimal(128) * gamma(s),
        "mgq": Decimal(128) * gamma(max(r, c, 2 * s)),
    }
    witness_all = True
    matrix_frobenius = l2(M_export.values())
    lumped = [sum((masses[p] * S[p][node] for p in range(p_count)), Decimal(0)) for node in range(n_count)]
    reconstructed_affine = [
        [sum((S[p][node] * analytic[component][node] for node in range(n_count)), Decimal(0))
         for component in range(3)]
        for p in range(p_count)
    ]
    sg_residual = sum((
        masses[p] * sum((
            (reconstructed_affine[p][component] - particle_velocity[p][component]) ** 2
            for component in range(3)
        ), Decimal(0))
        for p in range(p_count)
    ), Decimal(0)).sqrt()
    sg_denominator = max(
        sum((
            masses[p] * sum((particle_velocity[p][component] ** 2 for component in range(3)), Decimal(0))
            for p in range(p_count)
        ), Decimal(0)).sqrt(),
        sum(masses, Decimal(0)).sqrt(),
    )
    sg_normalized = sg_residual / sg_denominator
    repeated_sg_fields = (
        "sg_minus_v_l2_m_per_s_sqrt_kg",
        "sgv_denominator_m_per_s_sqrt_kg",
        "normalized_sg_minus_v",
    )
    require(len({
        tuple(witness_index[(sid, str(component))][field] for field in repeated_sg_fields)
        for component in range(3)
    }) == 1, f"{sid}: vector Sg witness fields are not repeated across axes")
    pcg_metrics: dict[int, dict[str, Decimal] | None] = {}
    for component in range(3):
        row = witness_index[(sid, str(component))]
        mg = [sum((M_export.get((i, j), Decimal(0)) * analytic[component][j] for j in range(n_count)), Decimal(0)) for i in range(n_count)]
        mg_residual = l2(mg[i] - rhs_export[(component, i)] for i in range(n_count))
        mg_denominator = l2(sum((abs(M_export.get((i, j), Decimal(0))) * abs(analytic[component][j]) for j in range(n_count)), Decimal(0)) for i in range(n_count)) + l2(rhs_export[(component, i)] for i in range(n_count))
        require(mg_denominator > 0, f"{sid}: zero Mg-q denominator")
        mg_normalized = mg_residual / mg_denominator
        for name, expected, allowance in (
            ("mg_minus_q_l2_kg_m_per_s", mg_residual, expected_bounds["mgq"] * mg_denominator / Decimal(1024)),
            ("mgq_denominator_kg_m_per_s", mg_denominator, Decimal(0)),
            ("normalized_mg_minus_q", mg_normalized, expected_bounds["mgq"] / Decimal(1024)),
            ("sg_minus_v_l2_m_per_s_sqrt_kg", sg_residual, expected_bounds["sgv"] * sg_denominator / Decimal(1024)),
            ("sgv_denominator_m_per_s_sqrt_kg", sg_denominator, Decimal(0)),
            ("normalized_sg_minus_v", sg_normalized, expected_bounds["sgv"] / Decimal(1024)),
            ("partition_max_residual", partition, expected_bounds["partition"] / Decimal(1024)),
            ("linear_reproduction_max_residual_m", linear, expected_bounds["linear"] / Decimal(1024)),
            ("gradient_partition_max_residual_per_m", derivative_partition, expected_bounds["gradient"] / Decimal(1024)),
        ):
            close_reported(numeric(row[name], f"{sid} witness {name}") or Decimal(0), expected,
                           f"{sid} witness {name}", absolute_allowance=allowance)
        for field, expected in (
            ("mgq_roundoff_bound", expected_bounds["mgq"]), ("sgv_roundoff_bound", expected_bounds["sgv"]),
            ("partition_roundoff_bound", expected_bounds["partition"]),
            ("linear_reproduction_roundoff_bound_m", expected_bounds["linear"]),
            ("gradient_partition_roundoff_bound_per_m", expected_bounds["gradient"]),
        ):
            close_reported(numeric(row[field], f"{sid} {field}") or Decimal(0), expected, f"{sid} {field}")
        decisions = {
            "mgq_pass": mg_normalized <= expected_bounds["mgq"], "sgv_pass": sg_normalized <= expected_bounds["sgv"],
            "partition_pass": partition <= expected_bounds["partition"],
            "linear_reproduction_pass": linear <= expected_bounds["linear"],
            "gradient_partition_pass": derivative_partition <= expected_bounds["gradient"],
        }
        for field, expected in decisions.items():
            require(boolean(row[field], f"{sid} {field}") == expected, f"{sid}: witness decision mismatch {field}")
        passed = all(decisions.values())
        require(boolean(row["pass"], f"{sid} witness pass") == passed, f"{sid}: witness aggregate mismatch")
        witness_all &= passed

        solve = solve_index[(sid, str(component))]
        pcg_available = boolean(nodes[0]["pcg_available"], f"{sid} pcg available")
        require(all(boolean(node["pcg_available"], f"{sid} pcg available") == pcg_available for node in nodes), f"{sid}: mixed PCG availability")
        if pcg_available:
            require(solve["solver"] == "pcg_control" and solve["status"] == "solved",
                    f"{sid}: available PCG is not a solved legacy control")
            solution = [binary64(nodes[node][("pcg_vhat_x_m_per_s", "pcg_vhat_y_m_per_s", "pcg_vhat_z_m_per_s")[component]], f"{sid} pcg solution") or Decimal(0) for node in range(n_count)]
            pcg_metrics[component] = validate_solve_metrics(
                sid, component, solve, solution, analytic[component],
                particle_velocity, masses, S, M_export, rhs_export, lumped)
        else:
            unavailable_fields = (
                "backward_residual_l2_kg_m_per_s", "backward_denominator_kg_m_per_s",
                "normalized_backward_residual", "grid_forward_lumped_numerator_m_per_s_sqrt_kg",
                "grid_forward_lumped_denominator_m_per_s_sqrt_kg", "normalized_forward_error",
                "reconstruction_mass_numerator_m_per_s_sqrt_kg",
                "reconstruction_mass_denominator_m_per_s_sqrt_kg", "normalized_reconstruction_error",
            )
            require(solve["solver"] == "pcg_control" and solve["status"] in STATUS_VALUES
                    and solve["status"] != "solved"
                    and integer(solve["iterations"], f"{sid} failed PCG iterations", minimum=0) >= 0,
                    f"{sid}: invalid failed PCG control row")
            require(all(solve[field] == "NA" for field in unavailable_fields)
                    and solve["accuracy_classification"] == "not_available",
                    f"{sid}: unavailable PCG has stray solution metrics/classification")
            validate_pcg_conditions(sid, solve, None)
            pcg_metrics[component] = None
    return {"witness_all": witness_all, "matrix_frobenius": matrix_frobenius, "S": S, "gradients": gradients,
            "masses": masses, "M": M_export, "rhs": rhs_export, "analytic": analytic, "particles": particle_velocity,
            "nodes": nodes, "lumped": lumped, "pcg_metrics": pcg_metrics}


def projection_metrics(
    component: int, solution: Sequence[Decimal], analytic: Sequence[Decimal],
    particle_velocity: Sequence[Sequence[Decimal]], masses: Sequence[Decimal],
    S: Sequence[Sequence[Decimal]], M: Mapping[tuple[int, int], Decimal],
    rhs: Mapping[tuple[int, int], Decimal], lumped: Sequence[Decimal],
) -> dict[str, Decimal]:
    n_count = len(solution)
    residual = [sum((M.get((i, j), Decimal(0)) * solution[j] for j in range(n_count)), Decimal(0)) - rhs[(component, i)] for i in range(n_count)]
    matrix_frobenius = l2(M.values())
    backward_denominator = matrix_frobenius * l2(solution) + l2(rhs[(component, i)] for i in range(n_count))
    forward = [solution[i] - analytic[i] for i in range(n_count)]
    forward_numerator = sum((lumped[i] * forward[i] ** 2 for i in range(n_count)), Decimal(0)).sqrt()
    forward_denominator = max(sum((lumped[i] * analytic[i] ** 2 for i in range(n_count)), Decimal(0)).sqrt(), sum(lumped, Decimal(0)).sqrt())
    reconstructed = [sum((S[p][i] * solution[i] for i in range(n_count)), Decimal(0)) for p in range(len(S))]
    recon = [reconstructed[p] - particle_velocity[p][component] for p in range(len(S))]
    recon_numerator = sum((masses[p] * recon[p] ** 2 for p in range(len(S))), Decimal(0)).sqrt()
    recon_denominator = max(sum((masses[p] * particle_velocity[p][component] ** 2 for p in range(len(S))), Decimal(0)).sqrt(), sum(masses, Decimal(0)).sqrt())
    return {
        "backward": l2(residual), "backward_denominator": backward_denominator,
        "normalized_backward": l2(residual) / backward_denominator,
        "forward": forward_numerator, "forward_denominator": forward_denominator,
        "normalized_forward": forward_numerator / forward_denominator,
        "reconstruction": recon_numerator, "reconstruction_denominator": recon_denominator,
        "normalized_reconstruction": recon_numerator / recon_denominator,
    }


def decimal_complete_pivot_reference(
    matrix: Mapping[tuple[int, int], Decimal], rhs: Sequence[Decimal], size: int,
) -> tuple[list[Decimal], int]:
    """Independent 100-digit dense solve of the exact exported binary64 system."""
    work = [[matrix.get((row, column), Decimal(0)) for column in range(size)] for row in range(size)]
    value = list(rhs)
    permutation = list(range(size))
    largest = max(abs(entry) for row in work for entry in row)
    threshold = largest * Decimal("1e-80")
    rank = 0
    for index in range(size):
        pivot_row, pivot_column = max(
            ((row, column) for row in range(index, size) for column in range(index, size)),
            key=lambda item: abs(work[item[0]][item[1]]),
        )
        if abs(work[pivot_row][pivot_column]) <= threshold:
            break
        work[index], work[pivot_row] = work[pivot_row], work[index]
        value[index], value[pivot_row] = value[pivot_row], value[index]
        for row in range(size):
            work[row][index], work[row][pivot_column] = work[row][pivot_column], work[row][index]
        permutation[index], permutation[pivot_column] = permutation[pivot_column], permutation[index]
        pivot = work[index][index]
        for row in range(index + 1, size):
            factor = work[row][index] / pivot
            work[row][index] = Decimal(0)
            for column in range(index + 1, size):
                work[row][column] -= factor * work[index][column]
            value[row] -= factor * value[index]
        rank += 1
    if rank != size:
        return [], rank
    permuted = [Decimal(0)] * size
    for row in range(size - 1, -1, -1):
        tail = sum((work[row][column] * permuted[column] for column in range(row + 1, size)), Decimal(0))
        permuted[row] = (value[row] - tail) / work[row][row]
    solution = [Decimal(0)] * size
    for position, original_column in enumerate(permutation):
        solution[original_column] = permuted[position]
    return solution, rank


def pcg_accuracy_classification(
    status: str,
    normalized_forward: Decimal | None,
    normalized_reconstruction: Decimal | None,
) -> str:
    if status != "solved":
        return "not_available"
    require(normalized_forward is not None and normalized_reconstruction is not None,
            "solved PCG accuracy classification lacks forward metrics")
    if normalized_forward > FORWARD_LIMIT or normalized_reconstruction > FORWARD_LIMIT:
        return "backward_pass_forward_fail"
    return "backward_and_forward_pass"


def validate_legacy_pcg_provenance(sid: str, row: Mapping[str, str]) -> None:
    applicable = boolean(
        row["legacy_residual_applicable"], f"{sid} legacy residual applicable")
    residual = binary64(
        row["legacy_normalized_residual"], f"{sid} legacy residual",
        optional=True)
    threshold = binary64(
        row["legacy_normalized_residual_threshold"],
        f"{sid} legacy residual threshold") or Decimal(0)
    require(threshold == PCG_LEGACY_RESIDUAL_LIMIT,
            f"{sid}: legacy PCG threshold is not the frozen 5e-12")
    require(bool(row["legacy_termination_reason"].strip()),
            f"{sid}: empty legacy PCG termination reason")
    if applicable:
        require(residual is not None and residual >= 0,
                f"{sid}: applicable legacy residual is unavailable/negative")
    else:
        require(residual is None,
                f"{sid}: inapplicable legacy residual has a numeric value")
    if row["status"] == "solved":
        require(applicable and residual is not None and residual <= threshold,
                f"{sid}: solved legacy PCG did not meet its frozen residual threshold")
    if row["status"] == "not_run_witness_failure":
        require(not applicable and residual is None
                and row["legacy_termination_reason"] == "not_run_witness_failure",
                f"{sid}: witness-stop legacy PCG provenance mismatch")


def validate_pcg_conditions(
    sid: str,
    row: Mapping[str, str],
    normalized_backward: Decimal | None,
) -> None:
    require(row["raw_condition_kind"] in PCG_CONDITION_KINDS
            and row["preconditioned_condition_kind"] in PCG_CONDITION_KINDS,
            f"{sid}: invalid condition provenance")
    raw = numeric(row["raw_condition_value"], f"{sid} raw condition", optional=True)
    preconditioned = numeric(
        row["preconditioned_condition_value"], f"{sid} preconditioned condition",
        optional=True)
    budget = numeric(
        row["condition_times_normalized_residual"], f"{sid} condition residual",
        optional=True)
    if raw is None:
        require(row["raw_condition_kind"] == "unavailable",
                f"{sid}: unavailable raw condition contract")
    else:
        require(raw >= 1 and row["raw_condition_kind"] != "unavailable",
                f"{sid}: bad raw condition estimate")
    if preconditioned is None:
        require(row["preconditioned_condition_kind"] == "unavailable",
                f"{sid}: unavailable preconditioned condition contract")
    else:
        require(preconditioned >= 1 and row["preconditioned_condition_kind"] != "unavailable",
                f"{sid}: bad preconditioned condition estimate")
    if normalized_backward is None:
        require(budget is None,
                f"{sid}: unavailable residual cannot have condition-times-residual")
    elif raw is None:
        require(budget is None,
                f"{sid}: unavailable raw condition cannot have a condition budget")
    else:
        require(budget is not None, f"{sid}: available raw condition lacks condition budget")
        close_reported(budget, raw * normalized_backward, f"{sid} condition*eta")


def validate_solve_metrics(
    sid: str, component: int, row: Mapping[str, str], solution: Sequence[Decimal],
    analytic: Sequence[Decimal], particle_velocity: Sequence[Sequence[Decimal]], masses: Sequence[Decimal],
    S: Sequence[Sequence[Decimal]], M: Mapping[tuple[int, int], Decimal],
    rhs: Mapping[tuple[int, int], Decimal], lumped: Sequence[Decimal],
    *, high_precision: bool = False,
) -> dict[str, Decimal]:
    metrics = projection_metrics(component, solution, analytic, particle_velocity, masses, S, M, rhs, lumped)
    mappings = (
        ("backward_residual_l2_kg_m_per_s", "backward"),
        ("backward_denominator_kg_m_per_s", "backward_denominator"),
        ("normalized_backward_residual", "normalized_backward"),
        ("grid_forward_lumped_numerator_m_per_s_sqrt_kg", "forward"),
        ("grid_forward_lumped_denominator_m_per_s_sqrt_kg", "forward_denominator"),
        ("normalized_forward_error", "normalized_forward"),
        ("reconstruction_mass_numerator_m_per_s_sqrt_kg", "reconstruction"),
        ("reconstruction_mass_denominator_m_per_s_sqrt_kg", "reconstruction_denominator"),
        ("normalized_reconstruction_error", "normalized_reconstruction"),
    )
    for field, name in mappings:
        allowance = Decimal(0)
        if name in {"forward", "reconstruction"}:
            denominator_name = "forward_denominator" if name == "forward" else "reconstruction_denominator"
            allowance = FORWARD_LIMIT * metrics[denominator_name] / Decimal(1024)
        elif name in {"normalized_forward", "normalized_reconstruction"}:
            allowance = FORWARD_LIMIT / Decimal(1024)
        elif high_precision and name == "backward":
            allowance = (Decimal(2) ** 12 * Decimal(len(solution)) * EPS_DD
                         * metrics["backward_denominator"] / Decimal(1024))
        elif high_precision and name == "normalized_backward":
            allowance = Decimal(2) ** 12 * Decimal(len(solution)) * EPS_DD / Decimal(1024)
        close_reported(numeric(row[field], f"{sid} solve {field}") or Decimal(0), metrics[name],
                       f"{sid} solve {field}", absolute_allowance=allowance)
    if not high_precision:
        validate_pcg_conditions(sid, row, metrics["normalized_backward"])
        require(row["accuracy_classification"] == pcg_accuracy_classification(
            row["status"], metrics["normalized_forward"],
            metrics["normalized_reconstruction"]),
            f"{sid}: PCG accuracy classification mismatch")
        integer(row["iterations"], f"{sid} iterations", minimum=0)
    require(row["status"] in STATUS_VALUES, f"{sid}: invalid solve status")
    return metrics


def expected_metric_only_witness_bounds(system: Mapping[str, str]) -> dict[str, Decimal]:
    sid = system["system_id"]
    s = integer(system["max_stencil_size"], f"{sid} s", minimum=1)
    c = integer(system["max_particle_contributions_per_node"], f"{sid} c", minimum=1)
    r = integer(system["max_matrix_row_nnz"], f"{sid} r", minimum=1)
    h = binary64(system["h_m"], f"{sid} h") or Decimal(0)
    expected = {str(value["system_id"]): value for value in registered_expectations()}[sid]
    points = expected_registered_particles(expected)
    max_point_norm = max(
        Decimal.from_float(math.sqrt(sum(value * value for value in position)))
        for position, _velocity, _mass in points
    )
    return {
        "partition": Decimal(32) * gamma(s),
        "linear": Decimal(64) * gamma(s) * max(Decimal(1), h, max_point_norm),
        "gradient": Decimal(64) * gamma(3 * s) * max(Decimal(1), Decimal(1) / h),
        "sgv": Decimal(128) * gamma(s),
        "mgq": Decimal(128) * gamma(max(r, c, 2 * s)),
    }


def validate_metric_only_system(
    system: Mapping[str, str],
    witness_index: Mapping[tuple[str, ...], dict[str, str]],
    solve_index: Mapping[tuple[str, ...], dict[str, str]],
) -> bool:
    sid = system["system_id"]
    bounds = expected_metric_only_witness_bounds(system)
    all_witness = True
    shared_fields = (
        "partition_max_residual", "partition_roundoff_bound",
        "linear_reproduction_max_residual_m", "linear_reproduction_roundoff_bound_m",
        "gradient_partition_max_residual_per_m", "gradient_partition_roundoff_bound_per_m",
    )
    shared_values: dict[str, Decimal] = {}
    shared_sg_fields: tuple[str, str, str] | None = None
    for component in range(3):
        row = witness_index[(sid, str(component))]
        mg = numeric(row["mg_minus_q_l2_kg_m_per_s"], f"{sid} Mg residual") or Decimal(0)
        mg_denominator = numeric(row["mgq_denominator_kg_m_per_s"], f"{sid} Mg denominator") or Decimal(0)
        mg_normalized = numeric(row["normalized_mg_minus_q"], f"{sid} Mg normalized") or Decimal(0)
        sg = numeric(row["sg_minus_v_l2_m_per_s_sqrt_kg"], f"{sid} Sg residual") or Decimal(0)
        sg_denominator = numeric(row["sgv_denominator_m_per_s_sqrt_kg"], f"{sid} Sg denominator") or Decimal(0)
        sg_normalized = numeric(row["normalized_sg_minus_v"], f"{sid} Sg normalized") or Decimal(0)
        sg_fields = (
            row["sg_minus_v_l2_m_per_s_sqrt_kg"],
            row["sgv_denominator_m_per_s_sqrt_kg"],
            row["normalized_sg_minus_v"],
        )
        if shared_sg_fields is None:
            shared_sg_fields = sg_fields
        else:
            require(sg_fields == shared_sg_fields,
                    f"{sid}: vector Sg witness fields are not repeated across axes")
        require(mg >= 0 and sg >= 0 and mg_denominator > 0 and sg_denominator > 0,
                f"{sid}: invalid metric-only witness norm")
        close_reported(mg_normalized, mg / mg_denominator, f"{sid} Mg quotient",
                       absolute_allowance=bounds["mgq"] / Decimal(1024))
        close_reported(sg_normalized, sg / sg_denominator, f"{sid} Sg quotient",
                       absolute_allowance=bounds["sgv"] / Decimal(1024))
        values = {field: numeric(row[field], f"{sid} {field}") or Decimal(0) for field in shared_fields}
        if component == 0:
            shared_values = values
        else:
            for field in shared_fields:
                close_reported(values[field], shared_values[field], f"{sid} repeated {field}")
        for field, expected_bound in (
            ("mgq_roundoff_bound", bounds["mgq"]),
            ("sgv_roundoff_bound", bounds["sgv"]),
            ("partition_roundoff_bound", bounds["partition"]),
            ("linear_reproduction_roundoff_bound_m", bounds["linear"]),
            ("gradient_partition_roundoff_bound_per_m", bounds["gradient"]),
        ):
            close_reported(numeric(row[field], f"{sid} {field}") or Decimal(0), expected_bound,
                           f"{sid} {field}")
        decisions = {
            "mgq_pass": mg_normalized <= bounds["mgq"],
            "sgv_pass": sg_normalized <= bounds["sgv"],
            "partition_pass": values["partition_max_residual"] <= bounds["partition"],
            "linear_reproduction_pass": values["linear_reproduction_max_residual_m"] <= bounds["linear"],
            "gradient_partition_pass": values["gradient_partition_max_residual_per_m"] <= bounds["gradient"],
        }
        for field, expected_decision in decisions.items():
            require(boolean(row[field], f"{sid} {field}") == expected_decision,
                    f"{sid}: metric-only witness decision mismatch {field}")
        passed = all(decisions.values())
        require(boolean(row["pass"], f"{sid} witness pass") == passed,
                f"{sid}: metric-only witness aggregate mismatch")
        all_witness &= passed

        solve = solve_index[(sid, str(component))]
        require(solve["solver"] == "pcg_control" and solve["status"] in STATUS_VALUES,
                f"{sid}: invalid metric-only PCG identity/status")
        iterations = integer(solve["iterations"], f"{sid} PCG iterations", minimum=0)
        metric_fields = (
            "backward_residual_l2_kg_m_per_s", "backward_denominator_kg_m_per_s",
            "normalized_backward_residual", "grid_forward_lumped_numerator_m_per_s_sqrt_kg",
            "grid_forward_lumped_denominator_m_per_s_sqrt_kg", "normalized_forward_error",
            "reconstruction_mass_numerator_m_per_s_sqrt_kg",
            "reconstruction_mass_denominator_m_per_s_sqrt_kg", "normalized_reconstruction_error",
        )
        if solve["status"] == "solved":
            metrics = {field: numeric(solve[field], f"{sid} solve {field}") or Decimal(0) for field in metric_fields}
            require(metrics["backward_residual_l2_kg_m_per_s"] >= 0
                    and metrics["grid_forward_lumped_numerator_m_per_s_sqrt_kg"] >= 0
                    and metrics["reconstruction_mass_numerator_m_per_s_sqrt_kg"] >= 0
                    and metrics["backward_denominator_kg_m_per_s"] > 0
                    and metrics["grid_forward_lumped_denominator_m_per_s_sqrt_kg"] > 0
                    and metrics["reconstruction_mass_denominator_m_per_s_sqrt_kg"] > 0,
                    f"{sid}: invalid metric-only solve norms")
            for normalized, numerator, denominator in (
                ("normalized_backward_residual", "backward_residual_l2_kg_m_per_s", "backward_denominator_kg_m_per_s"),
                ("normalized_forward_error", "grid_forward_lumped_numerator_m_per_s_sqrt_kg", "grid_forward_lumped_denominator_m_per_s_sqrt_kg"),
                ("normalized_reconstruction_error", "reconstruction_mass_numerator_m_per_s_sqrt_kg", "reconstruction_mass_denominator_m_per_s_sqrt_kg"),
            ):
                allowance = FORWARD_LIMIT / Decimal(1024) if normalized != "normalized_backward_residual" else Decimal(0)
                close_reported(metrics[normalized], metrics[numerator] / metrics[denominator],
                               f"{sid} solve quotient {normalized}", absolute_allowance=allowance)
            validate_pcg_conditions(
                sid, solve, metrics["normalized_backward_residual"])
            require(solve["accuracy_classification"] == pcg_accuracy_classification(
                solve["status"], metrics["normalized_forward_error"],
                metrics["normalized_reconstruction_error"]),
                f"{sid}: metric-only PCG accuracy classification mismatch")
        else:
            require(iterations >= 0 and all(solve[field] == "NA" for field in metric_fields)
                    and solve["accuracy_classification"] == "not_available",
                    f"{sid}: failed PCG has stray metric-only values")
            validate_pcg_conditions(sid, solve, None)
    return all_witness


def validate_high_precision(
    system: Mapping[str, str], data: Mapping[str, Any],
    hp_index: Mapping[tuple[str, ...], dict[str, str]],
    pivot_rows: Sequence[dict[str, str]],
) -> tuple[bool, bool]:
    sid = system["system_id"]
    selected = boolean(system["high_precision_applicable"], f"{sid} HP selected")
    rows = [hp_index.get((sid, str(component))) for component in range(3)]
    if not selected:
        require(all(row is None for row in rows), f"{sid}: unselected high precision rows")
        require(not pivot_rows, f"{sid}: unselected high precision pivot rows")
        return False, False
    require(all(row is not None for row in rows), f"{sid}: missing high precision component")
    present_rows = [row for row in rows if row is not None]
    repeated_metadata = (
        "status", "method", "precision_bits", "decimal_digits", "rank",
        "rank_method", "rank_is_certified", "regularization", "node_dropping",
        "basis_altered", "promotion_eligible", "pivot_threshold_relative",
        "smallest_pivot_abs_kg", "largest_pivot_abs_kg", "condition_value",
        "condition_kind",
    )
    require(all(len({row[field] for row in present_rows}) == 1
                for field in repeated_metadata),
            f"{sid}: inconsistent HP component metadata")
    reported_rank = integer(present_rows[0]["rank"], f"{sid} HP rank", minimum=0)
    hp_status = present_rows[0]["status"]
    require([integer(row["step"], f"{sid} HP pivot step", minimum=0)
             for row in pivot_rows] == list(range(reported_rank)),
            f"{sid}: HP pivot trace must contain exactly threshold_rank accepted steps")
    n_count = len(data["nodes"])
    pivot_rows_original: list[int] = []
    pivot_columns_original: list[int] = []
    pivot_values: list[Decimal] = []
    pivot_thresholds: list[Decimal] = []
    for row in pivot_rows:
        original_row = integer(
            row["original_row_index"], f"{sid} HP original pivot row", minimum=0)
        original_column = integer(
            row["original_column_index"], f"{sid} HP original pivot column", minimum=0)
        require(original_row < n_count and original_column < n_count,
                f"{sid}: HP pivot original index is out of range")
        pivot_rows_original.append(original_row)
        pivot_columns_original.append(original_column)
        pivot = decimal_number(row["pivot_abs_kg"], f"{sid} HP pivot") or Decimal(0)
        threshold = decimal_number(
            row["pivot_threshold_kg"], f"{sid} HP pivot threshold") or Decimal(0)
        require(pivot > threshold >= 0, f"{sid}: HP trace contains an unaccepted pivot")
        require(row["status"] == hp_status, f"{sid}: HP pivot status mismatch")
        require(not boolean(row["promotion_eligible"], f"{sid} HP pivot promotion"),
                f"{sid}: HP pivot trace marked promotion eligible")
        pivot_values.append(pivot)
        pivot_thresholds.append(threshold)
    require(len(set(pivot_rows_original)) == len(pivot_rows_original)
            and len(set(pivot_columns_original)) == len(pivot_columns_original),
            f"{sid}: HP pivot trace reuses an original row/column")
    if pivot_rows:
        relative_threshold = decimal_number(
            present_rows[0]["pivot_threshold_relative"],
            f"{sid} HP relative pivot threshold") or Decimal(0)
        expected_absolute_threshold = (
            max(abs(value) for value in data["M"].values()) * relative_threshold
        )
        for threshold in pivot_thresholds:
            close_reported(
                threshold, expected_absolute_threshold,
                f"{sid} HP absolute pivot threshold")
        expected_first_row, expected_first_column = max(
            ((row, column) for row in range(n_count) for column in range(n_count)),
            key=lambda key: abs(data["M"].get(key, Decimal(0))),
        )
        require((pivot_rows_original[0], pivot_columns_original[0])
                == (expected_first_row, expected_first_column),
                f"{sid}: HP first complete pivot index mismatch")
        close_reported(
            pivot_values[0], abs(data["M"].get(
                (expected_first_row, expected_first_column), Decimal(0))),
            f"{sid} HP first complete pivot")
        reported_smallest = decimal_number(
            present_rows[0]["smallest_pivot_abs_kg"], f"{sid} smallest HP pivot")
        reported_largest = decimal_number(
            present_rows[0]["largest_pivot_abs_kg"], f"{sid} largest HP pivot")
        require(reported_smallest is not None and reported_largest is not None,
                f"{sid}: accepted HP pivots lack extrema")
        close_reported(reported_smallest, min(pivot_values), f"{sid} HP pivot minimum")
        close_reported(reported_largest, max(pivot_values), f"{sid} HP pivot maximum")
    else:
        require(reported_rank == 0, f"{sid}: positive HP rank lacks pivot trace")
        require(all(row["smallest_pivot_abs_kg"] == "NA"
                    and row["largest_pivot_abs_kg"] == "NA"
                    for row in present_rows),
                f"{sid}: rank-zero HP solve has accepted-pivot extrema")
    nodes = data["nodes"]
    availability = [boolean(node["hp_available"], f"{sid} HP available") for node in nodes]
    require(all(value == availability[0] for value in availability), f"{sid}: mixed HP node availability")
    available = availability[0]
    all_pass = True
    contradiction = False
    python_micro_solutions: list[list[Decimal]] | None = None
    if system["case_class"] == "full_rank_micro":
        python_micro_solutions = []
        for component in range(3):
            rhs = [data["rhs"][(component, node)] for node in range(len(nodes))]
            solution, rank = decimal_complete_pivot_reference(data["M"], rhs, len(nodes))
            require(rank == len(nodes), f"{sid}: independent Decimal micro solve is rank deficient {rank}/{len(nodes)}")
            metrics = projection_metrics(
                component, solution, data["analytic"][component], data["particles"],
                data["masses"], data["S"], data["M"], data["rhs"], data["lumped"],
            )
            require(metrics["normalized_backward"] <= Decimal("1e-60"), f"{sid}: Decimal micro backward failure")
            require(metrics["normalized_forward"] <= FORWARD_LIMIT and metrics["normalized_reconstruction"] <= FORWARD_LIMIT,
                    f"{sid}: independent Decimal micro affine recovery failure")
            python_micro_solutions.append(solution)
    for component, optional_row in enumerate(rows):
        assert optional_row is not None
        row = optional_row
        require(row["status"] in STATUS_VALUES, f"{sid}: invalid HP status")
        precision_bits = integer(row["precision_bits"], f"{sid} HP bits", minimum=100)
        decimal_digits = integer(row["decimal_digits"], f"{sid} HP digits", minimum=30)
        reported_rank = integer(row["rank"], f"{sid} HP rank", minimum=0)
        registered = system["case_class"] in {"main", "full_rank_micro", "singular_ppc1"}
        if registered:
            require(precision_bits == 106 and decimal_digits == 40
                    and row["method"] == "fma_double_double_complete_pivot"
                    and row["rank_method"] == "dense_complete_pivot_double_double_threshold",
                    f"{sid}: HP arithmetic/method metadata mismatch")
            expected_relative_threshold = Decimal(2) ** 12 * Decimal(len(nodes)) * EPS_DD
            close_reported(decimal_number(row["pivot_threshold_relative"], f"{sid} HP pivot threshold") or Decimal(0),
                           expected_relative_threshold, f"{sid} HP pivot threshold")
            require(row["condition_value"] == "NA" and row["condition_kind"] == "unavailable",
                    f"{sid}: C++ HP condition diagnostic must remain unavailable")
        else:
            require(precision_bits >= 100, f"{sid}: HP precision not substantially above binary64")
        require(row["regularization"] == "none" and not boolean(row["node_dropping"], f"{sid} node drop") and not boolean(row["basis_altered"], f"{sid} basis altered"), f"{sid}: HP modified system")
        require(not boolean(row["promotion_eligible"], f"{sid} HP promotion"), f"{sid}: HP diagnostic marked promotion eligible")
        require(not boolean(row["rank_is_certified"], f"{sid} HP rank certified"), f"{sid}: numerical HP rank mislabeled certified")
        require(row["condition_kind"] in CONDITION_KINDS, f"{sid}: invalid HP condition provenance")
        if row["status"] != "solved":
            require(not available, f"{sid}: failed HP solve exported solution")
            require(all(row[field] == "NA" for field in (
                "backward_residual_l2_kg_m_per_s", "backward_denominator_kg_m_per_s",
                "normalized_backward_residual", "grid_forward_lumped_numerator_m_per_s_sqrt_kg",
                "grid_forward_lumped_denominator_m_per_s_sqrt_kg", "normalized_forward_error",
                "reconstruction_mass_numerator_m_per_s_sqrt_kg",
                "reconstruction_mass_denominator_m_per_s_sqrt_kg", "normalized_reconstruction_error",
            )), f"{sid}: failed HP solve has stray solution metrics")
            require(row["condition_value"] == "NA" and row["condition_kind"] == "unavailable",
                    f"{sid}: failed HP solve has a condition estimate")
            all_pass = False
            continue
        require(available, f"{sid}: solved HP lacks values")
        require(reported_rank == len(nodes), f"{sid}: solved HP is not numerically full rank")
        smallest = decimal_number(row["smallest_pivot_abs_kg"], f"{sid} smallest HP pivot") or Decimal(0)
        largest = decimal_number(row["largest_pivot_abs_kg"], f"{sid} largest HP pivot") or Decimal(0)
        require(Decimal(0) < smallest <= largest, f"{sid}: invalid HP pivot diagnostic")
        if not registered:
            condition_value = decimal_number(
                row["condition_value"], f"{sid} HP condition", optional=True)
            if condition_value is None:
                require(row["condition_kind"] == "unavailable",
                        f"{sid}: unavailable HP condition contract")
            else:
                require(condition_value >= 1 and row["condition_kind"] != "unavailable",
                        f"{sid}: invalid HP condition estimate")
        solution = [decimal_number(nodes[node][("hp_vhat_x_m_per_s", "hp_vhat_y_m_per_s", "hp_vhat_z_m_per_s")[component]], f"{sid} HP solution") or Decimal(0) for node in range(len(nodes))]
        metrics = validate_solve_metrics(sid, component, row, solution, data["analytic"][component], data["particles"], data["masses"], data["S"], data["M"], data["rhs"], data["lumped"], high_precision=True)
        if python_micro_solutions is not None:
            difference = [solution[node] - python_micro_solutions[component][node] for node in range(len(nodes))]
            difference_norm = sum((data["lumped"][node] * difference[node] ** 2 for node in range(len(nodes))), Decimal(0)).sqrt()
            reference_norm = max(
                sum((data["lumped"][node] * python_micro_solutions[component][node] ** 2 for node in range(len(nodes))), Decimal(0)).sqrt(),
                sum(data["lumped"], Decimal(0)).sqrt(),
            )
            require(difference_norm / reference_norm <= FORWARD_LIMIT,
                    f"{sid}: C++ high precision disagrees with independent Decimal micro solve")
        n_count = len(nodes)
        backward_limit = Decimal(2) ** 12 * Decimal(n_count) * EPS_DD
        component_pass = metrics["normalized_backward"] <= backward_limit and metrics["normalized_forward"] <= FORWARD_LIMIT and metrics["normalized_reconstruction"] <= FORWARD_LIMIT
        if metrics["normalized_backward"] <= backward_limit and not component_pass:
            contradiction = True
        all_pass &= component_pass
    return all_pass, contradiction


def require_independent_modes(sid: str, modes: Sequence[Sequence[Decimal]]) -> None:
    if not modes:
        return
    row_count = len(modes[0])
    column_count = len(modes)
    require(all(len(mode) == row_count for mode in modes), f"{sid}: ragged null basis")
    work = [[modes[column][row] for column in range(column_count)] for row in range(row_count)]
    scale = max(abs(value) for row in work for value in row)
    threshold = max(scale * Decimal("1e-40"), Decimal("1e-90"))
    rank = 0
    for column in range(column_count):
        pivot = max(range(rank, row_count), key=lambda row: abs(work[row][column]))
        require(abs(work[pivot][column]) > threshold,
                f"{sid}: null mode vectors are linearly dependent at column {column}")
        work[rank], work[pivot] = work[pivot], work[rank]
        pivot_value = work[rank][column]
        for row in range(rank + 1, row_count):
            if abs(work[row][column]) <= threshold:
                continue
            factor = work[row][column] / pivot_value
            for trailing in range(column, column_count):
                work[row][trailing] -= factor * work[rank][trailing]
        rank += 1
    require(rank == column_count, f"{sid}: incomplete independent null basis")


def independent_weighted_sampling_rank(
    sampling: Sequence[Sequence[Decimal]], masses: Sequence[Decimal],
) -> tuple[int, Decimal, Decimal, Decimal]:
    row_count = len(sampling)
    column_count = len(sampling[0]) if sampling else 0
    mass_scales = [mass.sqrt() for mass in masses]
    columns = [
        [mass_scales[row] * sampling[row][column] for row in range(row_count)]
        for column in range(column_count)
    ]
    norms = [l2(column) for column in columns]
    first_pivot = max(norms, default=Decimal(0))
    threshold = Decimal(128) * Decimal(max(row_count, column_count)) * EPS64 * max(first_pivot, MIN_NORMAL)
    rank = 0
    accepted_diagonals: list[Decimal] = []
    while rank < min(row_count, column_count):
        pivot = max(range(rank, column_count), key=lambda column: norms[column])
        if norms[pivot] <= threshold:
            break
        columns[rank], columns[pivot] = columns[pivot], columns[rank]
        norms[rank], norms[pivot] = norms[pivot], norms[rank]
        norm = l2(columns[rank])
        if norm <= threshold:
            break
        q = [value / norm for value in columns[rank]]
        accepted_diagonals.append(norm)
        for column in range(rank + 1, column_count):
            # Two passes make this an independent high-precision reorthogonalized
            # CPQR check rather than a transcription of the producer Householder QR.
            for _pass in range(2):
                projection = sum((q[row] * columns[column][row] for row in range(row_count)), Decimal(0))
                for row in range(row_count):
                    columns[column][row] -= projection * q[row]
            norms[column] = l2(columns[column])
        rank += 1
    smallest = min(accepted_diagonals, default=Decimal(0))
    return rank, threshold, first_pivot, smallest


def validate_nullspace_status(
    system: Mapping[str, str], data: Mapping[str, Any],
    row: Mapping[str, str], oracle_fixture: bool,
) -> tuple[bool, int | None]:
    sid = system["system_id"]
    n_count = len(data["nodes"])
    p_count = len(data["S"])
    require(integer(row["node_count"], f"{sid} null status N") == n_count
            and integer(row["particle_count"], f"{sid} null status P") == p_count,
            f"{sid}: null status dimensions mismatch")
    require(row["status"] in NULLSPACE_STATUS_VALUES,
            f"{sid}: invalid nullspace status")
    require(not boolean(row["promotion_eligible"], f"{sid} null status promotion"),
            f"{sid}: null status marked promotion eligible")
    analyzed = row["status"] == "analyzed"
    require(boolean(row["rank_available"], f"{sid} rank available") == analyzed,
            f"{sid}: null rank availability/status mismatch")
    if not analyzed:
        require(row["threshold_rank"] == "NA" and row["nullity"] == "NA"
                and row["numerical_rank_threshold_sqrt_kg"] == "NA"
                and row["largest_qr_diagonal_sqrt_kg"] == "NA"
                and row["smallest_accepted_qr_diagonal_sqrt_kg"] == "NA"
                and integer(row["constructed_mode_count"],
                            f"{sid} stopped constructed modes", minimum=0) == 0
                and not boolean(row["basis_complete"], f"{sid} stopped basis complete")
                and not boolean(row["rank_is_certified"], f"{sid} stopped rank certified"),
                f"{sid}: unavailable null rank has stray diagnostics")
        if row["status"] == "not_run_witness_failure":
            require(row["rank_method"] == "not_run",
                    f"{sid}: witness-stop null rank method mismatch")
        else:
            require(row["rank_method"] in {
                "unavailable", "householder_cpqr_sqrt_w_s",
                CPP_NULL_STATUS_RANK_METHOD,
            },
                    f"{sid}: failed null rank method mismatch")
        return False, None

    rank = integer(row["threshold_rank"], f"{sid} null status rank", minimum=0)
    nullity = integer(row["nullity"], f"{sid} null status nullity", minimum=1)
    constructed = integer(
        row["constructed_mode_count"], f"{sid} constructed mode count", minimum=0)
    basis_complete = boolean(row["basis_complete"], f"{sid} basis complete")
    require(rank < n_count and nullity == n_count - rank and constructed <= nullity,
            f"{sid}: analyzed null rank/nullity/mode-count mismatch")
    require(not basis_complete or constructed == nullity,
            f"{sid}: complete basis has incomplete constructed-mode count")
    if oracle_fixture:
        require(row["rank_method"] == "exact_sampling_rref"
                and boolean(row["rank_is_certified"], f"{sid} exact rank certified"),
                f"{sid}: oracle null status rank provenance mismatch")
    else:
        require(row["rank_method"] == CPP_NULL_STATUS_RANK_METHOD
                and not boolean(row["rank_is_certified"], f"{sid} rank certified"),
                f"{sid}: numerical null status rank provenance mismatch")
    independent_rank, independent_threshold, first_diagonal, _smallest = (
        independent_weighted_sampling_rank(data["S"], data["masses"])
    )
    require(rank == independent_rank,
            f"{sid}: null status rank disagrees with independent weighted sampling rank")
    threshold = numeric(
        row["numerical_rank_threshold_sqrt_kg"], f"{sid} null rank threshold") or Decimal(0)
    largest = numeric(
        row["largest_qr_diagonal_sqrt_kg"], f"{sid} largest QR diagonal") or Decimal(0)
    smallest = numeric(
        row["smallest_accepted_qr_diagonal_sqrt_kg"],
        f"{sid} smallest accepted QR diagonal") or Decimal(0)
    close_reported(threshold, independent_threshold, f"{sid} null rank threshold")
    close_reported(largest, first_diagonal, f"{sid} largest QR diagonal")
    require(threshold < smallest <= largest,
            f"{sid}: invalid accepted QR diagonal range")
    return True, rank


def validate_nullspace(
    system: Mapping[str, str], data: Mapping[str, Any], mode_rows: Sequence[dict[str, str]],
    metric_rows: Sequence[dict[str, str]], oracle_fixture: bool,
) -> tuple[int, int, bool]:
    sid = system["system_id"]
    selected = boolean(system["nullspace_applicable"], f"{sid} null selected")
    if not selected:
        require(not mode_rows and not metric_rows, f"{sid}: unselected nullspace rows")
        return 0, 0, False
    require(mode_rows and metric_rows, f"{sid}: selected nullspace evidence missing")
    modes_by_index: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in mode_rows:
        modes_by_index[integer(row["mode_index"], f"{sid} mode index", minimum=0)].append(row)
    metric_index = group_unique(metric_rows, ("system_id", "mode_index"), f"{sid} null metrics")
    n_count, p_count = len(data["nodes"]), len(data["S"])
    reported_ranks = {
        integer(row["rank"], f"{sid} null rank", minimum=0)
        for row in metric_rows
    }
    require(len(reported_ranks) == 1, f"{sid}: inconsistent nullspace ranks")
    rank = next(iter(reported_ranks))
    require(rank < n_count, f"{sid}: selected singular system has no reported nullspace")
    require(rank <= min(p_count, n_count), f"{sid}: reported sampling rank exceeds its structural bound")
    independent_rank, _threshold, _largest, _smallest = independent_weighted_sampling_rank(
        data["S"], data["masses"])
    require(rank == independent_rank,
            f"{sid}: reported QR rank {rank} disagrees with independent weighted-sampling rank {independent_rank}")
    expected_mode_indices = set(range(n_count - rank))
    require(set(modes_by_index) == expected_mode_indices,
            f"{sid}: null mode indices/count are not exactly 0..N-rank-1")
    require({int(key[1]) for key in metric_index} == expected_mode_indices,
            f"{sid}: mode/metric key mismatch")
    accepted = visible = 0
    ambiguous = False
    independent_vectors: list[list[Decimal]] = []
    for mode_index in range(n_count - rank):
        rows = modes_by_index[mode_index]
        require([integer(row["node_index"], f"{sid} mode node") for row in rows] == list(range(n_count)), f"{sid}: incomplete mode vector")
        metric = metric_index[(sid, str(mode_index))]
        require(metric["phase"] == system["phase"] and metric["orientation"] == system["orientation"], f"{sid}: null phase/orientation mismatch")
        require(not boolean(metric["promotion_eligible"], f"{sid} null promotion"), f"{sid}: null diagnostic marked promotion eligible")
        if oracle_fixture:
            require(metric["rank_method"] == "exact_sampling_rref"
                    and boolean(metric["rank_is_certified"], f"{sid} exact rank certified"),
                    f"{sid}: oracle rank method/certification mismatch")
            expected_mode_method = "exact_sampling_rref"
        else:
            require(metric["rank_method"] == "householder_cpqr_sqrt_w_s"
                    and not boolean(metric["rank_is_certified"], f"{sid} rank certified"),
                    f"{sid}: numerical QR rank method/certification mismatch")
            expected_mode_method = "householder_cpqr_sqrt_w_s"
        require(all(row["method"] == expected_mode_method and row["singular_value_sqrt_kg"] == "NA" for row in rows),
                f"{sid}: null vector method/singular-value metadata mismatch")
        z = [binary64(row["z_value_m_per_s"], f"{sid} z") or Decimal(0) for row in rows]
        require(abs(max(abs(value) for value in z) - 1) <= Decimal("1e-14"), f"{sid}: null mode not unit amplitude")
        independent_vectors.append(z)
        component = integer(metric["representative_component"], f"{sid} representative component")
        require(component == 0 and metric["representative_kind"] == "analytic_affine",
                f"{sid}: null representative must be analytic affine component 0")
        alpha = binary64(metric["alpha_dimensionless"], f"{sid} alpha") or Decimal(0)
        require(alpha == Decimal(1), f"{sid}: null perturbation alpha must be exactly one")
        representative = [binary64(row["representative_value_m_per_s"], f"{sid} representative") or Decimal(0) for row in rows]
        require(representative == data["analytic"][component],
                f"{sid}: null representative differs from exported analytic witness")
        shifted = [binary64(row["shifted_value_m_per_s"], f"{sid} shifted") or Decimal(0) for row in rows]
        shift_roundoff = max(abs(shifted[i] - (representative[i] + alpha * z[i])) for i in range(n_count))
        require(shift_roundoff <= Decimal(64) * gamma(2) * max(max(abs(value) for value in shifted), Decimal(1)), f"{sid}: shifted solution encoding mismatch")
        Mz = [sum((data["M"].get((i, j), Decimal(0)) * z[j] for j in range(n_count)), Decimal(0)) for i in range(n_count)]
        Sz = [sum((data["S"][p][i] * z[i] for i in range(n_count)), Decimal(0)) for p in range(p_count)]
        matrix_frobenius = l2(data["M"].values())
        sampling_frobenius = l2(value for row in data["S"] for value in row)
        mz_denominator = max(matrix_frobenius * l2(z), MIN_NORMAL)
        sz_denominator = max(sampling_frobenius * l2(z), MIN_NORMAL)
        mz_normalized = l2(Mz) / mz_denominator
        sz_normalized = l2(Sz) / sz_denominator
        gradients = [
            [sum((z[node] * data["gradients"][p][node][component_] for node in range(n_count)), Decimal(0)) for component_ in range(3)]
            for p in range(p_count)
        ]
        gradient_norms = [l2(value) for value in gradients]
        gradient_max = max(gradient_norms)
        gradient_rms = (sum((value * value for value in gradient_norms), Decimal(0)) / Decimal(p_count)).sqrt()
        s = integer(system["max_stencil_size"], f"{sid} s")
        per_particle_bounds = [
            Decimal(128) * gamma(3 * s) * sum((abs(z[node]) * l2(data["gradients"][p][node]) for node in range(n_count)), Decimal(0))
            for p in range(p_count)
        ]
        gradient_bound = max(per_particle_bounds)
        visibility_threshold = max(GRADIENT_ABSOLUTE_FLOOR, GRADIENT_BOUND_MULTIPLIER * gradient_bound)
        gradient_visible = gradient_max > visibility_threshold
        visibility_ratio = gradient_max / gradient_bound if gradient_bound > 0 else Decimal("Infinity")
        null_limit = Decimal(512) * Decimal(max(p_count, n_count)) * EPS64
        base_metrics = projection_metrics(component, representative, data["analytic"][component], data["particles"], data["masses"], data["S"], data["M"], data["rhs"], data["lumped"])
        shifted_metrics = projection_metrics(component, shifted, data["analytic"][component], data["particles"], data["masses"], data["S"], data["M"], data["rhs"], data["lumped"])
        base_residual = [
            sum((data["M"].get((i, j), Decimal(0)) * representative[j] for j in range(n_count)), Decimal(0))
            - data["rhs"][(component, i)]
            for i in range(n_count)
        ]
        shifted_residual = [
            sum((data["M"].get((i, j), Decimal(0)) * shifted[j] for j in range(n_count)), Decimal(0))
            - data["rhs"][(component, i)]
            for i in range(n_count)
        ]
        residual_change = l2(
            shifted_residual[i] - base_residual[i] for i in range(n_count))
        residual_change_normalized = residual_change / mz_denominator
        reconstructed_base = [sum((data["S"][p][i] * representative[i] for i in range(n_count)), Decimal(0)) for p in range(p_count)]
        reconstructed_shift = [sum((data["S"][p][i] * shifted[i] for i in range(n_count)), Decimal(0)) for p in range(p_count)]
        recon_delta = l2(reconstructed_shift[p] - reconstructed_base[p] for p in range(p_count)) / sz_denominator
        expected = {
            "mz_l2_kg_m_per_s": l2(Mz), "mz_denominator_kg_m_per_s": mz_denominator, "mz_normalized": mz_normalized,
            "sz_l2_m_per_s": l2(Sz), "sz_denominator_m_per_s": sz_denominator, "sz_normalized": sz_normalized,
            "gradient_max_per_s": gradient_max, "gradient_rms_per_s": gradient_rms,
            "gradient_roundoff_bound_per_s": gradient_bound,
            "base_residual_normalized": base_metrics["normalized_backward"],
            "shifted_residual_normalized": shifted_metrics["normalized_backward"],
            "residual_change_l2_kg_m_per_s": residual_change,
            "residual_change_denominator_kg_m_per_s": mz_denominator,
            "residual_change_normalized": residual_change_normalized,
            "reconstruction_delta_normalized": recon_delta,
        }
        reporting_allowances = {
            "mz_l2_kg_m_per_s": null_limit * mz_denominator / Decimal(1024),
            "mz_normalized": null_limit / Decimal(1024),
            "sz_l2_m_per_s": null_limit * sz_denominator / Decimal(1024),
            "sz_normalized": null_limit / Decimal(1024),
            "base_residual_normalized": null_limit / Decimal(1024),
            "shifted_residual_normalized": null_limit / Decimal(1024),
            "residual_change_l2_kg_m_per_s": null_limit * mz_denominator / Decimal(1024),
            "residual_change_normalized": null_limit / Decimal(1024),
            "reconstruction_delta_normalized": null_limit / Decimal(1024),
        }
        for field, value in expected.items():
            close_reported(numeric(metric[field], f"{sid} null {field}") or Decimal(0), value,
                           f"{sid} null {field}",
                           absolute_allowance=reporting_allowances.get(field, Decimal(0)))
        reported_ratio = numeric(metric["visibility_ratio"], f"{sid} visibility ratio", optional=True)
        if gradient_bound == 0:
            require(metric["visibility_ratio"] == "inf", f"{sid}: zero-bound visibility must be inf")
        else:
            require(reported_ratio is not None, f"{sid}: missing visibility ratio")
            close_reported(reported_ratio, visibility_ratio, f"{sid} visibility ratio")
        require(boolean(metric["gradient_visible"], f"{sid} gradient visible") == gradient_visible, f"{sid}: gradient decision mismatch")
        mode_pass = (
            mz_normalized <= null_limit
            and sz_normalized <= null_limit
            and residual_change_normalized <= null_limit
            and recon_delta <= null_limit
        )
        require(boolean(metric["pass"], f"{sid} null pass") == mode_pass, f"{sid}: null acceptance mismatch")
        if metric["representative_kind"] == "diagnostic_pseudoinverse":
            require(not boolean(metric["promotion_eligible"], f"{sid} pseudoinverse promotion"), f"{sid}: pseudoinverse promotion leak")
        if mode_pass:
            accepted += 1
            visible += int(gradient_visible)
        else:
            ambiguous = True
    require_independent_modes(sid, independent_vectors)
    return accepted, visible, ambiguous


def expected_authoritative_input_sha256() -> dict[str, str]:
    source_root = Path(__file__).resolve().parents[1]
    authoritative_paths = {
        "contract": source_root / "docs/projection-exactness-nullspace-contract.md",
        "independent_oracle_canonical_sha256":
            source_root / "tests/projection_exactness_nullspace_oracle.canonical.json",
        "preregistration":
            source_root / "docs/projection-exactness-nullspace-preregistration.md",
    }
    return {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in authoritative_paths.items()
    }


def validate_summary_provenance(
    summary: Mapping[str, Any], oracle_fixture: bool,
    smoke_provisional: bool = False,
) -> None:
    require(summary.get("schema") == SUMMARY_SCHEMA and summary.get("seed") == SEED,
            "summary schema/seed mismatch")
    require(summary.get("branch") == "projection-exactness-nullspace-lab",
            "summary branch mismatch")
    for field in (
        "analytic_witness_all_pass", "diagnostic_pseudoinverse_promotion_eligible",
        "high_precision_all_pass", "promotion", "singular_center_invariant",
        "singular_gradient_visible",
    ):
        require(type(summary.get(field)) is bool,
                f"summary {field} must be a JSON boolean")
    if oracle_fixture:
        expected_keys = {
            "analytic_witness_all_pass", "branch", "decision",
            "diagnostic_pseudoinverse_promotion_eligible", "high_precision_all_pass",
            "mode", "oracle", "pcg_miss_observed", "producer", "promotion",
            "registered_system_ids", "row_counts", "schema", "seed",
            "singular_center_invariant", "singular_gradient_visible", "source_sha",
            "tolerances",
        }
        require(set(summary) == expected_keys, "oracle summary key set mismatch")
        require(summary.get("mode") == "oracle_fixture"
                and summary.get("producer") == "python_independent_fixture",
                "not an oracle fixture")
        require(summary.get("source_sha") == "0" * 40,
                "oracle fixture source SHA mismatch")
        canonical_path = (
            Path(__file__).resolve().parents[1]
            / "tests/projection_exactness_nullspace_oracle.canonical.json"
        )
        require(summary.get("oracle") == read_json(canonical_path),
                "oracle fixture result differs from canonical oracle")
    else:
        expected_keys = {
            "analytic_witness_all_pass", "authoritative_input_sha256", "branch",
            "compiler_id", "compiler_version", "configured_source_branch", "decision",
            "diagnostic_pseudoinverse_promotion_eligible", "high_precision_all_pass",
            "hp_subset_paired_recovery_component_count",
            "hp_subset_pcg_nonrecovery_component_count", "mode", "parent_sha",
            "pcg_solved_gate_miss_component_count", "pcg_status_component_counts",
            "prior_failure_geometry_paired_recovery_component_count",
            "prior_failure_geometry_pcg_nonrecovery_component_count", "producer",
            "promotion", "provisional", "registered_system_ids", "row_counts", "schema",
            "seed", "singular_center_invariant", "singular_gradient_visible", "source_dirty",
            "source_sha", "supported_findings", "sweep_complete", "tolerances",
            "tool_language",
        }
        require(set(summary) == expected_keys, "full summary key set mismatch")
        require(summary.get("mode") == ("smoke" if smoke_provisional else "full")
                and summary.get("producer") == "cpp_projection_exactness_nullspace_lab",
                "wrong C++ evidence mode/producer")
        require(isinstance(summary.get("source_sha"), str)
                and SHA40_RE.fullmatch(str(summary["source_sha"])) is not None,
                "bad source SHA")
        require(summary.get("parent_sha") == SOURCE_PARENT_SHA,
                "accepted parent SHA mismatch")
        configured_branch = summary.get("configured_source_branch")
        if smoke_provisional:
            # Historical smoke diagnostics are intentionally rerun on later
            # descendant branches.  Preserve exact branch binding for sealed
            # full evidence, but require honest, nonempty provenance for a
            # provisional compatibility smoke.
            require(isinstance(configured_branch, str)
                    and configured_branch.strip() not in {"", "unknown"},
                    "configured source branch is empty/unknown")
        else:
            require(configured_branch == "projection-exactness-nullspace-lab",
                    "configured source branch mismatch")
        require(type(summary.get("source_dirty")) is bool,
                "source_dirty must be a JSON boolean")
        if smoke_provisional:
            require(summary.get("provisional") is True
                    and summary.get("sweep_complete") is False,
                    "smoke provisional/sweep provenance mismatch")
        else:
            require(summary.get("source_dirty") is False
                    and summary.get("provisional") is False
                    and summary.get("sweep_complete") is True,
                    "final source/provisional/sweep provenance mismatch")
        require(summary.get("tool_language") == "C++20", "tool language mismatch")
        require(isinstance(summary.get("compiler_id"), str)
                and str(summary["compiler_id"]).strip() not in {"", "unknown"}
                and isinstance(summary.get("compiler_version"), str)
                and str(summary["compiler_version"]).strip() not in {"", "unknown"},
                "compiler provenance is empty/unknown")
        require(summary.get("authoritative_input_sha256")
                == expected_authoritative_input_sha256(),
                "authoritative input digest mismatch")
        status_counts = summary.get("pcg_status_component_counts")
        require(isinstance(status_counts, dict) and status_counts
                and set(status_counts) <= STATUS_VALUES
                and all(type(value) is int and value > 0 for value in status_counts.values()),
                "invalid PCG status component counts")
        for field in (
            "pcg_solved_gate_miss_component_count",
            "hp_subset_paired_recovery_component_count",
            "hp_subset_pcg_nonrecovery_component_count",
            "prior_failure_geometry_paired_recovery_component_count",
            "prior_failure_geometry_pcg_nonrecovery_component_count",
        ):
            require(type(summary.get(field)) is int and int(summary[field]) >= 0,
                    f"invalid summary count {field}")
    require(summary.get("tolerances") == EXPECTED_TOLERANCES,
            "summary tolerance contract mismatch")


def validate_bundle(
    bundle: Path, oracle_fixture: bool, smoke_provisional: bool = False,
) -> dict[str, Any]:
    validate_manifest(bundle)
    tables = {name: read_csv(bundle / name, fields) for name, fields in CSV_SCHEMAS.items()}
    summary = read_json(bundle / "summary.json")
    require(not (oracle_fixture and smoke_provisional),
            "oracle fixture and smoke provisional modes are mutually exclusive")
    validate_summary_provenance(summary, oracle_fixture, smoke_provisional)
    row_counts = summary.get("row_counts")
    require(isinstance(row_counts, dict)
            and all(type(value) is int and value >= 0 for value in row_counts.values())
            and row_counts == {name: len(rows) for name, rows in tables.items()},
            "summary row counts mismatch")
    systems = tables["systems.csv"]
    validate_registered_matrix(systems, oracle_fixture, smoke_provisional)
    validate_system_metadata(systems, tables, oracle_fixture)
    ids = {row["system_id"] for row in systems}
    require(summary.get("registered_system_ids") == [row["system_id"] for row in systems], "registered system order mismatch")
    for name, rows in tables.items():
        if name != "systems.csv":
            require(all(row["system_id"] in ids for row in rows), f"{name}: unknown system")
    witness_index = group_unique(tables["witness.csv"], ("system_id", "component"), "witness")
    solve_index = group_unique(tables["solve_diagnostics.csv"], ("system_id", "component"), "solve")
    hp_index = group_unique(tables["high_precision.csv"], ("system_id", "component"), "high precision")
    require(len(witness_index) == 3 * len(systems) and len(solve_index) == 3 * len(systems), "all systems need three witness/solve components")
    for system in systems:
        sid = system["system_id"]
        solve_rows = [solve_index[(sid, str(component))] for component in range(3)]
        require(len({row["legacy_termination_reason"] for row in solve_rows}) == 1,
                f"{sid}: inconsistent legacy PCG termination reasons")
        for row in solve_rows:
            validate_legacy_pcg_provenance(sid, row)
    exported_data: dict[str, dict[str, Any]] = {}
    witness_all = True
    for system in systems:
        if boolean(system["assembly_exported"], "assembly exported"):
            data = validate_exported_system(system, tables, witness_index, solve_index, hp_index)
            exported_data[system["system_id"]] = data
            witness_all &= data["witness_all"]
        else:
            witness_all &= validate_metric_only_system(system, witness_index, solve_index)
            for component in range(3):
                require((system["system_id"], str(component)) not in hp_index,
                        "nonexported system cannot be HP selected")
    pcg_status_component_counts = dict(sorted(Counter(
        row["status"] for row in tables["solve_diagnostics.csv"]
    ).items()))
    pcg_solved_gate_miss_component_count = 0
    hp_subset_pcg_nonrecovery_component_count = 0
    prior_failure_geometry_pcg_nonrecovery_component_count = 0
    pcg_nonrecovery_by_system: dict[str, int] = defaultdict(int)
    for system in systems:
        sid = system["system_id"]
        for component in range(3):
            solve = solve_index[(sid, str(component))]
            solved = solve["status"] == "solved"
            gate_miss = False
            if solved:
                exported_metrics = (
                    exported_data.get(sid, {}).get("pcg_metrics", {}).get(component)
                )
                if exported_metrics is None:
                    forward = numeric(
                        solve["normalized_forward_error"], f"{sid} PCG forward") or Decimal(0)
                    reconstruction = numeric(
                        solve["normalized_reconstruction_error"],
                        f"{sid} PCG reconstruction") or Decimal(0)
                else:
                    forward = exported_metrics["normalized_forward"]
                    reconstruction = exported_metrics["normalized_reconstruction"]
                gate_miss = forward > FORWARD_LIMIT or reconstruction > FORWARD_LIMIT
                pcg_solved_gate_miss_component_count += int(gate_miss)
            nonrecovery = not solved or gate_miss
            pcg_nonrecovery_by_system[sid] += int(nonrecovery)
            if boolean(system["high_precision_applicable"], f"{sid} HP"):
                hp_subset_pcg_nonrecovery_component_count += int(nonrecovery)
            if sid in PRIOR_FAILURE_SYSTEM_IDS:
                prior_failure_geometry_pcg_nonrecovery_component_count += int(nonrecovery)

    hp_all = True
    contradiction = False
    hp_subset_paired_recovery_component_count = 0
    prior_failure_geometry_paired_recovery_component_count = 0
    hp_pivots_by_system: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in tables["high_precision_pivots.csv"]:
        hp_pivots_by_system[row["system_id"]].append(row)
    for system in systems:
        sid = system["system_id"]
        if boolean(system["high_precision_applicable"], f"{sid} HP"):
            require(sid in exported_data, f"{sid}: HP system lacks export")
            passed, contradicted = validate_high_precision(
                system, exported_data[sid], hp_index,
                hp_pivots_by_system[sid])
            hp_all &= passed
            contradiction |= contradicted
            if passed:
                hp_subset_paired_recovery_component_count += (
                    pcg_nonrecovery_by_system[sid])
                if sid in PRIOR_FAILURE_SYSTEM_IDS:
                    prior_failure_geometry_paired_recovery_component_count += (
                        pcg_nonrecovery_by_system[sid])
        else:
            require(not any(key[0] == sid for key in hp_index), f"{sid}: unexpected HP rows")
            require(not hp_pivots_by_system[sid], f"{sid}: unexpected HP pivot rows")
    solve_not_run = [
        row["status"] == "not_run_witness_failure"
        for row in tables["solve_diagnostics.csv"]
    ]
    hp_not_run = [
        row["status"] == "not_run_witness_failure"
        for row in tables["high_precision.csv"]
    ]
    if witness_all:
        require(not any(solve_not_run) and not any(hp_not_run),
                "not_run_witness_failure is forbidden when all witnesses pass")
    else:
        require(all(solve_not_run) and all(hp_not_run)
                and not tables["high_precision_pivots.csv"],
                "witness failure must stop every PCG/HP invocation")
    mode_by_system: dict[str, list[dict[str, str]]] = defaultdict(list)
    status_index = group_unique(
        tables["nullspace_status.csv"], ("system_id",), "nullspace status")
    metric_by_system: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in tables["nullspace_modes.csv"]:
        mode_by_system[row["system_id"]].append(row)
    for row in tables["nullspace_metrics.csv"]:
        metric_by_system[row["system_id"]].append(row)
    accepted_modes = visible_modes = 0
    null_ambiguous = False
    for system in systems:
        sid = system["system_id"]
        if boolean(system["nullspace_applicable"], f"{sid} null"):
            require(sid in exported_data, f"{sid}: null system lacks export")
            require((sid,) in status_index, f"{sid}: selected null status row missing")
            status_row = status_index[(sid,)]
            analyzed, _status_rank = validate_nullspace_status(
                system, exported_data[sid], status_row, oracle_fixture)
            grouped_modes: dict[int, list[dict[str, str]]] = defaultdict(list)
            for row in mode_by_system[sid]:
                grouped_modes[integer(
                    row["mode_index"], f"{sid} serialized mode index", minimum=0
                )].append(row)
            constructed = integer(
                status_row["constructed_mode_count"],
                f"{sid} status constructed modes", minimum=0)
            require(len(grouped_modes) == constructed,
                    f"{sid}: status/serialized constructed-mode count mismatch")
            serialized_widths_complete = all(
                [integer(row["node_index"], f"{sid} serialized mode node", minimum=0)
                 for row in grouped_modes[mode_index]]
                == list(range(len(exported_data[sid]["nodes"])))
                for mode_index in grouped_modes
            )
            nullity = (
                integer(status_row["nullity"], f"{sid} status nullity", minimum=1)
                if analyzed else 0
            )
            actual_basis_complete = (
                analyzed
                and constructed == nullity
                and set(grouped_modes) == set(range(nullity))
                and serialized_widths_complete
            )
            require(boolean(status_row["basis_complete"], f"{sid} basis complete")
                    == actual_basis_complete,
                    f"{sid}: null basis completeness status mismatch")
            if not witness_all:
                require(status_index[(sid,)]["status"] == "not_run_witness_failure"
                        and not mode_by_system[sid] and not metric_by_system[sid],
                        f"{sid}: witness-stop null diagnosis contract mismatch")
                null_ambiguous = True
            elif analyzed and actual_basis_complete:
                accepted, visible, ambiguous = validate_nullspace(
                    system, exported_data[sid], mode_by_system[sid],
                    metric_by_system[sid], oracle_fixture)
                accepted_modes += accepted
                visible_modes += visible
                null_ambiguous |= ambiguous or accepted == 0
            else:
                require(not metric_by_system[sid],
                        f"{sid}: incomplete null basis emitted acceptance metrics")
                null_ambiguous = True
        else:
            require(not mode_by_system[sid] and not metric_by_system[sid], f"{sid}: unexpected null rows")
            require((sid,) not in status_index, f"{sid}: unexpected null status row")
    if not witness_all:
        decision = "stop_assembly_or_basis_inconsistency"
    elif contradiction:
        decision = "stop_contradiction_or_implementation_defect"
    elif visible_modes > 0:
        decision = "stop_center_state_gradient_nullspace_blocker"
    elif null_ambiguous or not hp_all:
        decision = "stop_inconclusive_rank_or_solver_diagnosis"
    else:
        decision = "stop_retain_quotient_or_gauge_for_future_lab"
    require(summary.get("analytic_witness_all_pass") == witness_all, "summary witness result mismatch")
    require(summary.get("high_precision_all_pass") == hp_all, "summary HP result mismatch")
    if oracle_fixture:
        require(summary.get("pcg_miss_observed")
                == (pcg_solved_gate_miss_component_count > 0),
                "oracle summary PCG miss mismatch")
    else:
        require(summary.get("pcg_status_component_counts") == pcg_status_component_counts,
                "summary PCG status component counts mismatch")
        require(summary.get("pcg_solved_gate_miss_component_count")
                == pcg_solved_gate_miss_component_count,
                "summary solved PCG gate-miss count mismatch")
        require(summary.get("hp_subset_pcg_nonrecovery_component_count")
                == hp_subset_pcg_nonrecovery_component_count,
                "summary HP-subset PCG nonrecovery count mismatch")
        require(summary.get("hp_subset_paired_recovery_component_count")
                == hp_subset_paired_recovery_component_count,
                "summary HP-subset paired recovery count mismatch")
        require(summary.get("prior_failure_geometry_pcg_nonrecovery_component_count")
                == prior_failure_geometry_pcg_nonrecovery_component_count,
                "summary prior-failure PCG nonrecovery count mismatch")
        require(summary.get("prior_failure_geometry_paired_recovery_component_count")
                == prior_failure_geometry_paired_recovery_component_count,
                "summary prior-failure paired recovery count mismatch")
    require(summary.get("singular_center_invariant") == (accepted_modes > 0 and not null_ambiguous), "summary null invariance mismatch")
    require(summary.get("singular_gradient_visible") == (visible_modes > 0), "summary gradient visibility mismatch")
    require(summary.get("diagnostic_pseudoinverse_promotion_eligible") is False, "pseudoinverse promotion gate mismatch")
    if smoke_provisional:
        require(summary.get("supported_findings") == [],
                "provisional smoke must suppress scientific findings")
    elif not oracle_fixture:
        expected_findings: list[str] = []
        if hp_subset_paired_recovery_component_count > 0:
            expected_findings.append(
                "paired_high_precision_recovery_after_pcg_nonrecovery")
        if prior_failure_geometry_paired_recovery_component_count > 0:
            expected_findings.append("prior_affine_failure_is_solver_or_conditioning")
        if contradiction:
            expected_findings.append("high_precision_forward_contradiction_or_implementation_defect")
        if accepted_modes > 0:
            expected_findings.append("center_invisible_numerical_null_modes")
        if visible_modes > 0:
            expected_findings.append("center_invisible_gradient_visible_modes")
        require(summary.get("supported_findings") == expected_findings,
                "summary supported findings mismatch")
    expected_decision = (
        "smoke_provisional_no_scientific_decision"
        if smoke_provisional else decision
    )
    require(summary.get("decision") == expected_decision,
            f"bounded decision mismatch: {summary.get('decision')} != {expected_decision}")
    require(summary.get("promotion") is False, "projection method was promoted")
    return {"systems": len(systems), "exported": len(exported_data), "accepted_modes": accepted_modes,
            "visible_modes": visible_modes, "decision": expected_decision}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--compare", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--oracle-fixture", action="store_true")
    modes.add_argument("--smoke-provisional", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = validate_bundle(
            args.bundle.resolve(), args.oracle_fixture, args.smoke_provisional)
        if args.compare:
            other = validate_bundle(
                args.compare.resolve(), args.oracle_fixture,
                args.smoke_provisional)
            require(result == other, "compared bundle semantic summary differs")
            left = {path.name: path.read_bytes() for path in args.bundle.iterdir() if path.is_file()}
            right = {path.name: path.read_bytes() for path in args.compare.iterdir() if path.is_file()}
            require(left == right, "compared bundles are not byte-identical")
    except (InvalidBundle, OSError, UnicodeError, csv.Error, ArithmeticError, ValueError) as error:
        print(f"PROJECTION EXACTNESS NULLSPACE BUNDLE INVALID: {error}", file=sys.stderr)
        return 1
    print(
        "PROJECTION EXACTNESS NULLSPACE BUNDLE VALID: "
        f"systems={result['systems']} exported={result['exported']} "
        f"accepted_modes={result['accepted_modes']} visible_modes={result['visible_modes']} "
        f"decision={result['decision']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
