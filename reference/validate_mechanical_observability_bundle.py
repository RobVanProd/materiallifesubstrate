#!/usr/bin/env python3
"""Independent validator for the MLS mechanical-observability evidence.

The validator shares no C++ implementation.  It reconstructs packet
neighborhoods, corrected moments, central-distance and oriented-volume rows,
selected exact ranks, affine images, rigid generators, and the preregistered
decision from exported evidence.  It never promotes a representation: every
accepted bundle remains a bounded diagnostic result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import math
import re
import struct
import sys
import tempfile
from collections import defaultdict
from decimal import ROUND_FLOOR, Decimal, getcontext, localcontext
from fractions import Fraction as Q
from pathlib import Path
from typing import Any, Iterable, Mapping, NoReturn, Sequence


SEED = 260828
SUMMARY_SCHEMA = "mls.mechanical-observability.summary.v2"
MANIFEST_SCHEMA = "mls.mechanical-observability.manifest.v1"
ACCEPTED_PARENT_SHA = "2e175396ff30faea8a4d96d5a0336ab9ba042f12"
BRANCH = "mechanical-observability-lab"
PRODUCER = "cpp_mechanical_observability_lab"
EPS64 = Decimal(2) ** -52
MIN_NORMAL = Decimal.from_float(sys.float_info.min)
DECIMAL_DIGITS = 100
MAX_DENSE_OPERATOR_CELLS = 2_000_000
MAX_OPERATOR_DIMENSION = 10_000
MAX_BUNDLE_BYTES = 3 * 1024 * 1024 * 1024
MAX_CSV_LINE_BYTES = 4 * 1024 * 1024
MAX_CSV_FIELD_CHARS = 2 * 1024 * 1024
getcontext().prec = 120

CONFIGURATION_FIELDS = tuple(
    "configuration_id,base_configuration_id,family,variant,profile,transform,"
    "lookup_phase,packet_count,nominal_spacing_m,support_radius_m,geometry_scale,"
    "affine_span_rank,connected,edge_count,edge_lower_bound,"
    "min_incident_direction_rank,rigid_generator_rank,generic_solid_gate,"
    "intentionally_flexible,decision_driving,packet_payload_sha256,"
    "neighbor_payload_sha256,relation_payload_sha256,"
    "input_checkpoint_sha256_before,input_checkpoint_sha256_after,"
    "diagnostics_read_only_exact".split(",")
)
PACKET_FIELDS = tuple(
    "configuration_id,packet_index,packet_id,mass_quanta,x_m,y_m,z_m,"
    "vx_m_per_s,vy_m_per_s,vz_m_per_s,jitter_dx_m,jitter_dy_m,jitter_dz_m".split(",")
)
NEIGHBOR_PAIR_FIELDS = tuple(
    "configuration_id,lookup_phase,low_packet_id,high_packet_id,"
    "distance_squared_m2,support_radius_squared_m2,brute_force_eligible,"
    "lookup_eligible,agreement,weight".split(",")
)
RELATION_FIELDS = tuple(
    "configuration_id,relation_index,relation_id,relation_kind,center_id,"
    "first_id,second_id,third_id,selection_status,selection_source,"
    "reference_value,reference_units,selection_score_m4".split(",")
)
OPERATOR_STATUS_FIELDS = tuple(
    "operator_id,configuration_id,candidate,operator_role,observable_kind,"
    "build_status,packet_count,relation_count,row_count,column_count,raw_exported,"
    "operator_payload_sha256,row_normalization_complete,first_invalid_row,"
    "rank_applicable,b_rank_eligible,generic_solid_gate,decision_driving,"
    "promotion_eligible,failure_stage,failure_reason,failure_witness_row,"
    "failure_witness_column,failure_witness_value,failure_witness_ieee754_bits,"
    "failure_witness_class".split(",")
)
OPERATOR_ENTRY_FIELDS = tuple(
    "operator_id,row_index,column_index,domain_kind,domain_id,velocity_component,"
    "row_kind,row_owner_id,row_component,value,units".split(",")
)
MOMENT_DIAGNOSTIC_FIELDS = tuple(
    "operator_id,packet_id,neighbor_count,m00_m2,m01_m2,m02_m2,m10_m2,m11_m2,"
    "m12_m2,m20_m2,m21_m2,m22_m2,symmetry_residual,smallest_eigenvalue_m2,"
    "largest_eigenvalue_m2,condition_number,condition_kind,"
    "inverse_residual_normalized,inverse_residual_tolerance,status,inverse_emitted"
    .split(",")
)
AFFINE_OBJECTIVITY_FIELDS = tuple(
    "operator_id,test_id,test_kind,field,packet_id,relation_id,component,"
    "measured_value,target_value,absolute_error,normalization_scale,"
    "normalized_error,operation_count,roundoff_bound,pass,units".split(",")
)
INVARIANCE_FIELDS = tuple(
    "comparison_id,base_operator_id,transformed_operator_id,transform_kind,scale,"
    "lookup_phase,topology_match,relation_ids_match,rank_match,nullity_match,"
    "base_build_status,transformed_build_status,build_status_match,metrics_available,"
    "normalized_residual_delta,max_scaled_singular_value_delta,tolerance,"
    "canonical_bytes_match,pass".split(",")
)
RIGID_BASIS_FIELDS = tuple(
    "operator_id,basis_kind,mode_index,dof_index,domain_kind,domain_id,"
    "velocity_component,value".split(",")
)
RANK_STATUS_FIELDS = tuple(
    "operator_id,record_kind,pivot_step,permuted_column_index,diagonal_magnitude,"
    "accepted_pivot,status,row_count,column_count,rank,nullity,rigid_rank,"
    "nonrigid_nullity,threshold,ambiguity_lower,ambiguity_upper,rank_ambiguous,"
    "rank_method,rank_is_certified,basis_complete,rigid_in_kernel,"
    "kernel_equals_rigid_subspace,normalized_rigid_residual,"
    "normalized_null_residual,normalized_nonrigid_residual,"
    "rigid_orthogonality_residual,residual_tolerance,generic_observability_pass,"
    "promotion_eligible,failure_stage,failure_reason".split(",")
)
NULLSPACE_MODE_FIELDS = tuple(
    "operator_id,basis_kind,mode_index,dof_index,domain_kind,domain_id,"
    "velocity_component,value".split(",")
)
NULLSPACE_METRIC_FIELDS = tuple(
    "operator_id,basis_kind,mode_index,operator_image_l2,operator_denominator,"
    "normalized_operator_residual,rigid_projection_l2,"
    "rigid_orthogonality_residual,roundoff_bound,pass,promotion_eligible".split(",")
)
GRID_GAUGE_FIELDS = tuple(
    "operator_id,sampling_operator_id,derivative_operator_id,mode_index,"
    "representative_component,sampling_residual_normalized,derivative_max_per_s,"
    "derivative_rms_per_s,derivative_roundoff_bound_per_s,visibility_ratio,"
    "gradient_visible,accepted,pass,promotion_eligible".split(",")
)
EXACT_REFERENCE_FIELDS = tuple(
    "reference_id,configuration_id,candidate,operator_id,arithmetic,"
    "precision_digits,row_count,column_count,rank,nullity,rigid_rank,"
    "nonrigid_nullity,rigid_in_kernel,kernel_equals_rigid_span,source,pass,"
    "promotion_eligible".split(",")
)
GRID_NODE_FIELDS = tuple(
    "sampling_operator_id,derivative_operator_id,configuration_id,lookup_phase,"
    "node_index,node_id,grid_i,grid_j,grid_k,x_m,y_m,z_m".split(",")
)
CHECKPOINT_FIELDS = tuple(
    "configuration_id,checkpoint_kind,encoding,byte_count,payload_sha256,payload_hex".split(",")
)
PERMUTATION_CONTROL_FIELDS = tuple(
    "control_id,operator_id,configuration_id,permutation_kind,permutation_seed,"
    "packet_order,relation_order,row_count,column_count,entry_count,raw_payload_sha256,"
    "raw_dense_payload_sha256,"
    "canonical_payload_sha256,baseline_payload_sha256,canonical_bytes_match,"
    "promotion_eligible".split(",")
)
PERMUTATION_ENTRY_FIELDS = tuple(
    "control_id,operator_id,row_index,column_index,domain_kind,domain_id,"
    "velocity_component,row_kind,row_owner_id,row_component,value,units".split(",")
)

CSV_SCHEMAS = {
    "configurations.csv": CONFIGURATION_FIELDS,
    "packets.csv": PACKET_FIELDS,
    "neighbor_pairs.csv": NEIGHBOR_PAIR_FIELDS,
    "relations.csv": RELATION_FIELDS,
    "operator_status.csv": OPERATOR_STATUS_FIELDS,
    "operator_entries.csv": OPERATOR_ENTRY_FIELDS,
    "moment_diagnostics.csv": MOMENT_DIAGNOSTIC_FIELDS,
    "affine_objectivity.csv": AFFINE_OBJECTIVITY_FIELDS,
    "invariance.csv": INVARIANCE_FIELDS,
    "rigid_basis.csv": RIGID_BASIS_FIELDS,
    "rank_status.csv": RANK_STATUS_FIELDS,
    "nullspace_modes.csv": NULLSPACE_MODE_FIELDS,
    "nullspace_metrics.csv": NULLSPACE_METRIC_FIELDS,
    "grid_gauge.csv": GRID_GAUGE_FIELDS,
    "exact_reference.csv": EXACT_REFERENCE_FIELDS,
    "grid_nodes.csv": GRID_NODE_FIELDS,
    "checkpoints.csv": CHECKPOINT_FIELDS,
    "permutation_controls.csv": PERMUTATION_CONTROL_FIELDS,
    "permutation_entries.csv": PERMUTATION_ENTRY_FIELDS,
}
REQUIRED_FILES = (*CSV_SCHEMAS, "summary.json")
MAX_FILE_BYTES: Mapping[str, int] = {
    **{name: 256 * 1024 * 1024 for name in CSV_SCHEMAS},
    "operator_entries.csv": 768 * 1024 * 1024,
    "nullspace_modes.csv": 1536 * 1024 * 1024,
    "rigid_basis.csv": 512 * 1024 * 1024,
    "summary.json": 512 * 1024,
    "manifest.json": 128 * 1024,
}
MAX_CSV_ROWS: Mapping[str, int] = {
    **{name: 2_000_000 for name in CSV_SCHEMAS},
    "operator_entries.csv": 8_000_000,
    "nullspace_modes.csv": 16_000_000,
    "rigid_basis.csv": 6_000_000,
}

# Every integer-valued CSV cell has one canonical wire spelling.  Optional
# cells use the literal ``NA``; all other values are base-ten without leading
# zeroes, a leading plus sign, or negative zero.  Keeping this table explicit
# also makes schema additions fail closed until their integer semantics are
# classified here.
INTEGER_CELLS: Mapping[str, Mapping[str, bool]] = {
    "configurations.csv": {
        "packet_count": False, "affine_span_rank": False, "edge_count": False,
        "edge_lower_bound": False, "min_incident_direction_rank": False,
        "rigid_generator_rank": False,
    },
    "packets.csv": {"packet_index": False, "packet_id": False, "mass_quanta": False},
    "neighbor_pairs.csv": {"low_packet_id": False, "high_packet_id": False},
    "relations.csv": {
        "relation_index": False, "center_id": True, "first_id": True,
        "second_id": True, "third_id": True,
    },
    "operator_status.csv": {
        "packet_count": False, "relation_count": False, "row_count": False,
        "column_count": False, "first_invalid_row": True,
        "failure_witness_row": True, "failure_witness_column": True,
    },
    "operator_entries.csv": {
        "row_index": False, "column_index": False, "domain_id": False,
    },
    "moment_diagnostics.csv": {"packet_id": False, "neighbor_count": False},
    "affine_objectivity.csv": {"packet_id": True, "operation_count": False},
    "rigid_basis.csv": {
        "mode_index": False, "dof_index": False, "domain_id": False,
    },
    "rank_status.csv": {
        "pivot_step": True, "permuted_column_index": True, "row_count": False,
        "column_count": False, "rank": False, "nullity": False,
        "rigid_rank": False, "nonrigid_nullity": True,
    },
    "nullspace_modes.csv": {
        "mode_index": False, "dof_index": False, "domain_id": False,
    },
    "nullspace_metrics.csv": {"mode_index": False},
    "grid_gauge.csv": {"mode_index": False},
    "exact_reference.csv": {
        "precision_digits": False, "row_count": False, "column_count": False,
        "rank": False, "nullity": False, "rigid_rank": False,
        "nonrigid_nullity": False,
    },
    "grid_nodes.csv": {
        "node_index": False, "node_id": False, "grid_i": False,
        "grid_j": False, "grid_k": False,
    },
    "checkpoints.csv": {"byte_count": False},
    "permutation_controls.csv": {
        "permutation_seed": False, "row_count": False, "column_count": False,
        "entry_count": False,
    },
    "permutation_entries.csv": {
        "row_index": False, "column_index": False, "domain_id": False,
    },
}
SIGNED_INTEGER_CELLS = frozenset({("grid_nodes.csv", field) for field in ("grid_i", "grid_j", "grid_k")})

SUMMARY_KEY_ORDER = (
        "schema",
        "mode",
        "provisional",
        "sweep_complete",
        "producer",
        "seed",
        "source_sha",
        "parent_sha",
        "branch",
        "dirty",
        "registered_configuration_ids",
        "registered_operator_ids",
        "checkpoint_round_trip_all_pass",
        "diagnostics_read_only_all_exact",
        "neighbor_lookup_all_agree",
        "negative_control_reproduced",
        "affine_objectivity_all_pass",
        "finite_objectivity_all_pass",
        "invariance_all_pass",
        "decisive_rank_rows_all_unambiguous",
        "raw_decision_rows_all_exported",
        "independent_reference_all_pass",
        "nondeterminism_detected",
        "candidate_findings",
        "decision",
        "promotion",
        "row_counts",
        "tolerances",
)
SUMMARY_KEYS = frozenset(SUMMARY_KEY_ORDER)
MANIFEST_KEY_ORDER = ("algorithm", "files", "pre_hash_sha256", "schema")
SUMMARY_CONTRACT_KEYS = (
    "checkpoint_round_trip_all_pass",
    "diagnostics_read_only_all_exact",
    "neighbor_lookup_all_agree",
    "negative_control_reproduced",
    "affine_objectivity_all_pass",
    "finite_objectivity_all_pass",
    "invariance_all_pass",
    "decisive_rank_rows_all_unambiguous",
    "raw_decision_rows_all_exported",
    "independent_reference_all_pass",
)
VALIDATOR_FINDINGS_SCHEMA = "mls.mechanical-observability.validator-findings.v1"
EXPECTED_TOLERANCES = {
    "moment_condition_number_max": "1e10",
    "moment_inverse_residual_formula": "4096*3*epsilon64",
    "rank_threshold_formula": "512*max(m,n)*epsilon64*max(d0,minnormal)",
    "rank_ambiguity_factor": "8",
    "rank_residual_formula": "4096*max(m,n)*epsilon64",
    "affine_normalized_formula": "4096*max(m,n)*epsilon64",
    "finite_roundoff_formula": "256*gamma(operation_count)*operand_scale+256*minnormal",
    "invariance_formula": "16384*max(m,n)*epsilon64",
    "grid_gauge_absolute_floor_per_s": "1e-10",
    "grid_gauge_roundoff_multiplier": "1e4",
}
DECISIONS = {
    "stop_inconclusive_or_implementation_failure",
    "retain_central_relational_representation_for_research",
    "retain_volume_enriched_relational_representation_for_research",
    "stop_reconsider_packet_abstraction",
}
CANDIDATE_FINDINGS = {
    "A": {"negative_control_reproduced", "negative_control_failed"},
    "B": {
        "reject_averaged_single_gradient_packet_kinematics",
        "no_resolved_eligible_nonrigid_mode",
        "inconclusive",
    },
    "C": {
        "retain_central_relational_representation_for_research",
        "generic_nonrigid_mode_triggers_d",
        "inconclusive",
    },
    "D": {
        "not_triggered",
        "retain_volume_enriched_relational_representation_for_research",
        "stop_reconsider_packet_abstraction",
        "inconclusive",
    },
}
EXACT_CLAIMS = {
    "tetrahedron_k4": (6, 6, 0),
    "tetrahedron_k4_minus_edge": (5, 7, 1),
    "octahedron_graph": (12, 6, 0),
    "cube_edge_graph": (12, 12, 6),
    "planar_square_plus_diagonal": (5, 7, 1),
    "planar_square_plus_diagonal_and_volume": (6, 6, 0),
}
EXACT_BINDINGS = {
    "tetrahedron_k4": ("exact.tetrahedron_k4", "C", "exact.tetrahedron_k4.C"),
    "tetrahedron_k4_minus_edge": (
        "exact.tetrahedron_k4_minus_edge", "C", "exact.tetrahedron_k4_minus_edge.C"
    ),
    "octahedron_graph": ("exact.octahedron_graph", "C", "exact.octahedron_graph.C"),
    "cube_edge_graph": ("exact.cube_edge_graph", "C", "exact.cube_edge_graph.C"),
    "planar_square_plus_diagonal": (
        "exact.planar_square_plus_diagonal", "C", "exact.planar_square_plus_diagonal.C"
    ),
    "planar_square_plus_diagonal_and_volume": (
        "exact.planar_square_plus_diagonal_and_volume",
        "D",
        "exact.planar_square_plus_diagonal_and_volume.D",
    ),
}
K4_EDGES = tuple(itertools.combinations(range(1, 5), 2))
SQUARE_DIAGONAL_EDGES = ((1, 2), (1, 3), (1, 4), (2, 3), (3, 4))
FROZEN_EXACT_EDGES: Mapping[str, tuple[tuple[int, int], ...]] = {
    "exact.noncoplanar_underconnected": K4_EDGES[:-1],
    "exact.tetrahedron_k4": K4_EDGES,
    "exact.tetrahedron_k4_minus_edge": K4_EDGES[:-1],
    "exact.octahedron_graph": tuple(
        (first, second)
        for first in range(1, 7)
        for second in range(first + 1, 7)
        if (first, second) not in {(1, 2), (3, 4), (5, 6)}
    ),
    "exact.cube_edge_graph": (
        (1, 2), (1, 3), (1, 5), (2, 4), (2, 6), (3, 4),
        (3, 7), (4, 8), (5, 6), (5, 7), (6, 8), (7, 8),
    ),
    "exact.planar_square_plus_diagonal": SQUARE_DIAGONAL_EDGES,
    "exact.planar_square_plus_diagonal_and_volume": SQUARE_DIAGONAL_EDGES,
}

LOOKUP_PHASES = ("p000", "p037_011_029")
A_REPRESENTATIVES = (
    "base.bcc35.r180.original",
    "base.corner_truncated.r180.original",
    "base.filament.r205.original",
    "base.jitter27.r180.original",
    "base.sc3.r180.original",
    "base.sheet.r150.original",
)
A_ROW_COMPONENTS = ("xx", "yy", "zz", "xy", "xz", "yz")
AXES = ("x", "y", "z")

# ``--allow-smoke`` is a convenience for the one preregistered, byte-authentic
# positive control.  It is not permission for a producer to choose a favorable
# subset of the full configuration matrix.
SMOKE_CONFIGURATION_IDS = frozenset({
    "base.filament.r205.original",
    "base.filament.r205.original.translation",
    "exact.planar_square_plus_diagonal_and_volume",
})
SMOKE_OPERATOR_IDS = frozenset({
    "base.filament.r205.original.A.p000.D",
    "base.filament.r205.original.A.p000.S",
    "base.filament.r205.original.A.p037_011_029.D",
    "base.filament.r205.original.A.p037_011_029.S",
    "base.filament.r205.original.B",
    "base.filament.r205.original.C",
    "base.filament.r205.original.D",
    "base.filament.r205.original.translation.B",
    "base.filament.r205.original.translation.C",
    "base.filament.r205.original.translation.D",
    "exact.planar_square_plus_diagonal_and_volume.B",
    "exact.planar_square_plus_diagonal_and_volume.C",
    "exact.planar_square_plus_diagonal_and_volume.D",
})

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
INT_RE = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")
UINT_RE = re.compile(r"(?:0|[1-9][0-9]*)\Z")
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:+/-]*\Z")
HEX_RE = re.compile(r"-?0x[0-9a-f]+(?:\.[0-9a-f]+)?p[+-][0-9]+\Z")
IEEE754_BITS_RE = re.compile(r"[0-9a-f]{16}\Z")


class InvalidBundle(RuntimeError):
    """Raised for any integrity, schema, semantic, or decision mismatch."""


def fail(message: str) -> NoReturn:
    raise InvalidBundle(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def reject_json_constant(value: str) -> NoReturn:
    fail(f"nonstandard JSON constant {value!r}")


def read_json(path: Path) -> Mapping[str, Any]:
    try:
        raw = path.read_bytes()
        require(len(raw) <= MAX_FILE_BYTES.get(path.name, 512 * 1024),
                f"{path.name}: JSON exceeds frozen byte cap")
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_json_constant,
        )
        canonical = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        require(raw == canonical, f"{path.name}: noncanonical JSON bytes")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        fail(f"cannot read strict JSON {path.name}: {error}")
    require(isinstance(value, dict), f"{path.name}: root must be an object")
    return value


def read_csv(path: Path, fields: Sequence[str]) -> list[dict[str, str]]:
    try:
        raw = path.read_bytes()
        require(len(raw) <= MAX_FILE_BYTES[path.name],
                f"{path.name}: CSV exceeds frozen byte cap")
        require(raw.endswith(b"\n"), f"{path.name}: missing canonical terminal LF")
        require(b"\r" not in raw, f"{path.name}: CR is forbidden")
        line_start = 0
        for line_end, byte in enumerate(raw):
            if byte == 10:
                require(line_end - line_start <= MAX_CSV_LINE_BYTES,
                        f"{path.name}: CSV line exceeds frozen byte cap")
                line_start = line_end + 1
        text_value = raw.decode("utf-8")
        stream = io.StringIO(text_value, newline="")
        reader = csv.DictReader(stream, dialect="excel", strict=True)
        require(tuple(reader.fieldnames or ()) == tuple(fields), f"{path.name}: header mismatch")
        rows: list[dict[str, str]] = []
        for row in reader:
            require(len(rows) < MAX_CSV_ROWS[path.name],
                    f"{path.name}: CSV exceeds frozen row cap")
            require(all(value is None or len(value) <= MAX_CSV_FIELD_CHARS
                        for value in row.values()),
                    f"{path.name}: CSV field exceeds frozen character cap")
            rows.append(row)
    except (OSError, UnicodeError, csv.Error) as error:
        fail(f"cannot read {path.name}: {error}")
    for line, row in enumerate(rows, 2):
        require(None not in row, f"{path.name}:{line}: excess column")
        require(all(value is not None for value in row.values()), f"{path.name}:{line}: missing column")
    canonical_stream = io.StringIO(newline="")
    writer = csv.writer(canonical_stream, dialect="excel", lineterminator="\n")
    writer.writerow(fields)
    writer.writerows([[row[field] for field in fields] for row in rows])
    require(canonical_stream.getvalue().encode("utf-8") == raw,
            f"{path.name}: noncanonical RFC-4180 quoting or bytes")
    return rows


def validate_canonical_integer_cells(
    tables: Mapping[str, Sequence[Mapping[str, str]]],
) -> None:
    require(set(INTEGER_CELLS) <= set(tables), "canonical integer schema/table inventory")
    for table_name, field_contract in INTEGER_CELLS.items():
        require(set(field_contract) <= set(CSV_SCHEMAS[table_name]),
                f"{table_name}: unknown canonical integer field")
        for row_index, row in enumerate(tables[table_name], 2):
            for field, optional in field_contract.items():
                value = row[field]
                if optional and value == "NA":
                    continue
                where = f"{table_name}:{row_index}:{field}"
                if (table_name, field) in SIGNED_INTEGER_CELLS:
                    integer(value, where)
                else:
                    unsigned(value, where)


def integer(text: str, where: str, *, minimum: int | None = None) -> int:
    require(INT_RE.fullmatch(text) is not None, f"{where}: noncanonical integer {text!r}")
    value = int(text)
    require(minimum is None or value >= minimum, f"{where}: integer below {minimum}")
    return value


def unsigned(text: str, where: str, *, minimum: int = 0) -> int:
    require(UINT_RE.fullmatch(text) is not None, f"{where}: noncanonical unsigned integer {text!r}")
    value = int(text)
    require(value >= minimum, f"{where}: integer below {minimum}")
    return value


def boolean(text: str, where: str) -> bool:
    require(text in {"true", "false"}, f"{where}: expected true/false")
    return text == "true"


def identifier(text: str, where: str, *, optional: bool = False) -> str | None:
    if optional and text == "NA":
        return None
    require(ID_RE.fullmatch(text) is not None, f"{where}: invalid identifier {text!r}")
    return text


def binary64(text: str, where: str, *, optional: bool = False) -> Decimal | None:
    if optional and text == "NA":
        return None
    require(HEX_RE.fullmatch(text) is not None, f"{where}: noncanonical binary64 {text!r}")
    try:
        value = float.fromhex(text)
    except ValueError as error:
        fail(f"{where}: invalid binary64: {error}")
    require(math.isfinite(value), f"{where}: nonfinite binary64")
    require(not (value == 0.0 and math.copysign(1.0, value) < 0), f"{where}: negative zero")
    require(value.hex() == text, f"{where}: binary64 text is not canonical")
    return Decimal.from_float(value)


def ieee754_witness(bits: str, value_class: str, where: str) -> float:
    """Decode one canonical IEEE-754 failure witness and bind its class."""

    require(IEEE754_BITS_RE.fullmatch(bits) is not None,
            f"{where}: noncanonical IEEE-754 witness bits")
    value = struct.unpack(">d", bytes.fromhex(bits))[0]
    if value_class == "positive_infinity":
        require(math.isinf(value) and value > 0, f"{where}: +infinity witness mismatch")
    elif value_class == "negative_infinity":
        require(math.isinf(value) and value < 0, f"{where}: -infinity witness mismatch")
    elif value_class in {"quiet_nan", "signaling_nan"}:
        require(math.isnan(value), f"{where}: NaN witness mismatch")
        quiet = bool(int(bits, 16) & (1 << 51))
        require(quiet == (value_class == "quiet_nan"),
                f"{where}: NaN quiet/signaling class mismatch")
    else:
        fail(f"{where}: unsupported IEEE-754 witness class {value_class!r}")
    return value


def fraction64(text: str, where: str) -> Q:
    binary64(text, where)
    return Q.from_float(float.fromhex(text))


def sha256(text: str, where: str) -> str:
    require(SHA256_RE.fullmatch(text) is not None, f"{where}: invalid SHA-256")
    return text


def manifest_payload(hashes: Mapping[str, str]) -> bytes:
    names = sorted(hashes)
    lines = ["{", '  "algorithm": "SHA-256",', '  "files": {']
    for index, name in enumerate(names):
        comma = "," if index + 1 < len(names) else ""
        lines.append(f"    {json.dumps(name)}: {json.dumps(hashes[name])}{comma}")
    lines.extend(("  },", f'  "schema": {json.dumps(MANIFEST_SCHEMA)}', "}"))
    return "\n".join(lines).encode("utf-8")


def grouped_payload_digest(prefix: bytes, fields: Sequence[str], rows: Sequence[Mapping[str, str]]) -> str:
    digest = hashlib.sha256()
    digest.update(prefix)
    digest.update(b"\n")
    for row in rows:
        for field in fields:
            digest.update(b"\0")
            digest.update(row[field].encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def canonical_operator_payload(matrix: Sequence[Sequence[Decimal]]) -> bytes:
    rows = len(matrix)
    columns = len(matrix[0]) if matrix else 0
    require(all(len(row) == columns for row in matrix), "canonical operator ragged matrix")
    payload = bytearray(b"MLS-MECHANICAL-OBSERVABILITY-CANONICAL-OPERATOR-v1\n")
    payload.extend(struct.pack("<QQ", rows, columns))
    for row in matrix:
        for value in row:
            number = float(value)
            require(math.isfinite(number) and Decimal.from_float(number) == value,
                    "canonical operator value is not binary64")
            payload.extend(struct.pack("<d", number))
    return bytes(payload)


def packet_permutation(configuration_id: str, packet_ids: Sequence[int]) -> list[int]:
    canonical = sorted(packet_ids)
    ordered = sorted(
        canonical,
        key=lambda packet_id: (
            hashlib.sha256(
                f"{SEED}|packet_permutation|{configuration_id}|{packet_id}".encode("ascii")
            ).digest(),
            packet_id,
        ),
    )
    if len(ordered) > 1 and ordered == canonical:
        ordered = ordered[1:] + ordered[:1]
    return ordered


def relation_permutation(
    configuration_id: str, candidate: str, canonical_relation_ids: Sequence[str]
) -> list[str]:
    canonical = list(canonical_relation_ids)
    ordered = sorted(
        canonical,
        key=lambda relation_id: (
            hashlib.sha256(
                f"{SEED}|relation_permutation|{configuration_id}|{candidate}|{relation_id}"
                .encode("ascii")
            ).digest(),
            relation_id,
        ),
    )
    if len(ordered) > 1 and ordered == canonical:
        ordered = ordered[1:] + ordered[:1]
    return ordered


def raw_permuted_operator_payload(matrix: Sequence[Sequence[Decimal]]) -> bytes:
    rows = len(matrix)
    columns = len(matrix[0]) if matrix else 0
    require(all(len(row) == columns for row in matrix), "raw permuted operator ragged matrix")
    payload = bytearray(b"MLS-MECHANICAL-OBSERVABILITY-RAW-PERMUTED-OPERATOR-v2\n")
    payload.extend(struct.pack("<QQ", rows, columns))
    for row in matrix:
        for value in row:
            number = float(value)
            require(math.isfinite(number) and Decimal.from_float(number) == value,
                    "raw permuted operator value is not binary64")
            payload.extend(struct.pack("<d", number))
    return bytes(payload)


def verify_manifest(bundle: Path) -> None:
    manifest = read_json(bundle / "manifest.json")
    require(tuple(manifest) == MANIFEST_KEY_ORDER, "manifest key order")
    require(manifest["algorithm"] == "SHA-256", "manifest algorithm")
    require(manifest["schema"] == MANIFEST_SCHEMA, "manifest schema")
    files = manifest["files"]
    require(isinstance(files, dict), "manifest files must be an object")
    require(set(files) == set(REQUIRED_FILES), "manifest file inventory mismatch")
    require(tuple(files) == tuple(sorted(REQUIRED_FILES)), "manifest file key order")
    actual_inventory = {
        path.name
        for path in bundle.iterdir()
        if path.is_file() and not path.is_symlink()
    }
    require(actual_inventory == {*REQUIRED_FILES, "manifest.json"}, "bundle regular-file inventory mismatch")
    for path in bundle.iterdir():
        require(path.is_file() and not path.is_symlink(), f"unexpected non-regular entry {path.name}")
    checked: dict[str, str] = {}
    for name in REQUIRED_FILES:
        claimed = files.get(name)
        require(isinstance(claimed, str), f"manifest hash type for {name}")
        sha256(claimed, f"manifest {name}")
        actual = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
        require(claimed == actual, f"manifest digest mismatch for {name}")
        checked[name] = actual
    expected_pre_hash = hashlib.sha256(manifest_payload(checked)).hexdigest()
    require(manifest["pre_hash_sha256"] == expected_pre_hash, "manifest pre-hash mismatch")


def regular_bundle_inventory(bundle: Path) -> set[str]:
    try:
        entries = list(bundle.iterdir())
    except OSError as error:
        fail(f"cannot enumerate bundle: {error}")
    require(all(path.is_file() and not path.is_symlink() for path in entries),
            "bundle contains a non-regular or symbolic entry")
    return {path.name for path in entries}


def bounded_file_sizes(bundle: Path) -> dict[str, int]:
    sizes: dict[str, int] = {}
    total = 0
    for name in (*REQUIRED_FILES, "manifest.json"):
        path = bundle / name
        try:
            stat_result = path.stat()
        except OSError as error:
            fail(f"cannot stat {name}: {error}")
        require(path.is_file() and not path.is_symlink(), f"{name}: not a regular file")
        cap = MAX_FILE_BYTES[name]
        require(stat_result.st_size <= cap,
                f"{name}: file exceeds frozen byte cap {cap}")
        sizes[name] = stat_result.st_size
        total += stat_result.st_size
        require(total <= MAX_BUNDLE_BYTES, "bundle exceeds frozen total byte cap")
    return sizes


def bounded_copy(source: Path, target: Path, expected_size: int) -> tuple[int, str]:
    digest = hashlib.sha256()
    copied = 0
    try:
        with source.open("rb") as input_stream, target.open("xb") as output_stream:
            while True:
                chunk = input_stream.read(1024 * 1024)
                if not chunk:
                    break
                copied += len(chunk)
                require(copied <= expected_size,
                        f"{source.name}: grew during bounded snapshot copy")
                digest.update(chunk)
                output_stream.write(chunk)
    except OSError as error:
        fail(f"cannot snapshot {source.name}: {error}")
    require(copied == expected_size, f"{source.name}: size changed during snapshot copy")
    return copied, digest.hexdigest()


def capture_bundle_snapshot(bundle: Path, snapshot: Path) -> dict[str, str]:
    """Digest-copy one manifest-bound live tree into private immutable input."""
    require(bundle.is_dir(), f"bundle is not a directory: {bundle}")
    expected_inventory = {*REQUIRED_FILES, "manifest.json"}
    require(regular_bundle_inventory(bundle) == expected_inventory,
            "bundle regular-file inventory mismatch")
    sizes = bounded_file_sizes(bundle)
    snapshot.mkdir(parents=True, exist_ok=False)
    _manifest_size, manifest_digest = bounded_copy(
        bundle / "manifest.json", snapshot / "manifest.json", sizes["manifest.json"]
    )
    manifest = read_json(snapshot / "manifest.json")
    require(tuple(manifest) == MANIFEST_KEY_ORDER, "manifest key order")
    files = manifest.get("files")
    require(isinstance(files, dict) and set(files) == set(REQUIRED_FILES),
            "manifest file inventory mismatch")
    signature = {"manifest.json": manifest_digest}
    for name in REQUIRED_FILES:
        claimed = files[name]
        require(isinstance(claimed, str), f"manifest hash type for {name}")
        sha256(claimed, f"manifest {name}")
        _copied, actual = bounded_copy(bundle / name, snapshot / name, sizes[name])
        require(actual == claimed, f"manifest digest mismatch for {name}")
        signature[name] = actual
    verify_manifest(snapshot)
    return signature


def require_live_bundle_unchanged(bundle: Path, signature: Mapping[str, str]) -> None:
    require(regular_bundle_inventory(bundle) == set(signature),
            "live bundle inventory changed during validation")
    sizes = bounded_file_sizes(bundle)
    for name, expected in signature.items():
        try:
            digest = hashlib.sha256()
            observed = 0
            with (bundle / name).open("rb") as stream:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    observed += len(chunk)
                    require(observed <= sizes[name],
                            f"live {name} grew during validation rescan")
                    digest.update(chunk)
            require(observed == sizes[name], f"live {name} size changed during rescan")
            actual = digest.hexdigest()
        except OSError as error:
            fail(f"cannot rescan live {name}: {error}")
        require(actual == expected, f"live bundle changed during validation: {name}")


def dsum(values: Iterable[Decimal]) -> Decimal:
    return sum(values, Decimal(0))


def qsum(values: Iterable[Q]) -> Q:
    return sum(values, Q(0))


def decimal_dot(first: Sequence[Decimal], second: Sequence[Decimal]) -> Decimal:
    require(len(first) == len(second), "decimal dot size mismatch")
    return dsum(a * b for a, b in zip(first, second, strict=True))


def decimal_norm(values: Iterable[Decimal]) -> Decimal:
    values_list = list(values)
    return dsum(value * value for value in values_list).sqrt()


def decimal_matrix_norm(matrix: Sequence[Sequence[Decimal]]) -> Decimal:
    return decimal_norm(value for row in matrix for value in row)


def decimal_matvec(matrix: Sequence[Sequence[Decimal]], vector: Sequence[Decimal]) -> list[Decimal]:
    return [decimal_dot(row, vector) for row in matrix]


def decimal_inverse3(matrix: Sequence[Sequence[Decimal]]) -> list[list[Decimal]]:
    require(len(matrix) == 3 and all(len(row) == 3 for row in matrix), "inverse3 shape")
    a = matrix
    determinant = (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )
    require(determinant != 0, "singular independently reconstructed 3x3 moment")
    return [
        [
            (a[1][1] * a[2][2] - a[1][2] * a[2][1]) / determinant,
            (a[0][2] * a[2][1] - a[0][1] * a[2][2]) / determinant,
            (a[0][1] * a[1][2] - a[0][2] * a[1][1]) / determinant,
        ],
        [
            (a[1][2] * a[2][0] - a[1][0] * a[2][2]) / determinant,
            (a[0][0] * a[2][2] - a[0][2] * a[2][0]) / determinant,
            (a[0][2] * a[1][0] - a[0][0] * a[1][2]) / determinant,
        ],
        [
            (a[1][0] * a[2][1] - a[1][1] * a[2][0]) / determinant,
            (a[0][1] * a[2][0] - a[0][0] * a[2][1]) / determinant,
            (a[0][0] * a[1][1] - a[0][1] * a[1][0]) / determinant,
        ],
    ]


def symmetric_eigenvalues3_decimal(matrix: Sequence[Sequence[Decimal]]) -> list[Decimal]:
    work = [list(row) for row in matrix]
    with localcontext() as context:
        context.prec = 120
        for _iteration in range(160):
            first, second = max(((0, 1), (0, 2), (1, 2)),
                                key=lambda pair: abs(work[pair[0]][pair[1]]))
            off = work[first][second]
            scale = max(Decimal(1), *(abs(work[index][index]) for index in range(3)))
            if abs(off) <= Decimal(10) ** -105 * scale:
                break
            tau = (work[second][second] - work[first][first]) / (Decimal(2) * off)
            sign = Decimal(1) if tau >= 0 else Decimal(-1)
            tangent = sign / (abs(tau) + (Decimal(1) + tau * tau).sqrt())
            cosine = Decimal(1) / (Decimal(1) + tangent * tangent).sqrt()
            sine = tangent * cosine
            app, aqq = work[first][first], work[second][second]
            work[first][first] = cosine * cosine * app - Decimal(2) * sine * cosine * off \
                + sine * sine * aqq
            work[second][second] = sine * sine * app + Decimal(2) * sine * cosine * off \
                + cosine * cosine * aqq
            work[first][second] = work[second][first] = Decimal(0)
            for other in range(3):
                if other in (first, second):
                    continue
                aip, aiq = work[other][first], work[other][second]
                work[other][first] = work[first][other] = cosine * aip - sine * aiq
                work[other][second] = work[second][other] = sine * aip + cosine * aiq
        return sorted(work[index][index] for index in range(3))


def decimal_rank(matrix: Sequence[Sequence[Decimal]], tolerance: Decimal = Decimal("1e-40")) -> int:
    work = [list(row) for row in matrix]
    if not work:
        return 0
    rows, columns = len(work), len(work[0])
    scale = max((abs(value) for row in work for value in row), default=Decimal(0))
    if scale == 0:
        return 0
    threshold = tolerance * scale
    rank = 0
    for column in range(columns):
        pivot = max(range(rank, rows), key=lambda row: abs(work[row][column]), default=rank)
        if rank >= rows or abs(work[pivot][column]) <= threshold:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        divisor = work[rank][column]
        for row in range(rank + 1, rows):
            if abs(work[row][column]) <= threshold:
                continue
            multiplier = work[row][column] / divisor
            for entry in range(column, columns):
                work[row][entry] -= multiplier * work[rank][entry]
        rank += 1
        if rank == rows:
            break
    return rank


def decimal_rank_absolute(
    matrix: Sequence[Sequence[Decimal]], threshold: Decimal
) -> int:
    if not matrix:
        return 0
    work = [list(row) for row in matrix]
    rows, columns = len(work), len(work[0])
    rank = 0
    for column in range(columns):
        pivot = max(range(rank, rows), key=lambda row: abs(work[row][column]), default=rank)
        if rank >= rows or abs(work[pivot][column]) <= threshold:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        pivot_value = work[rank][column]
        for row in range(rank + 1, rows):
            if work[row][column] == 0:
                continue
            multiplier = work[row][column] / pivot_value
            for item in range(column, columns):
                work[row][item] -= multiplier * work[rank][item]
        rank += 1
        if rank == rows:
            break
    return rank


def decimal_nullspace_basis(
    matrix: Sequence[Sequence[Decimal]], threshold: Decimal
) -> list[list[Decimal]]:
    """Construct a deterministic high-precision null basis by pivoted RREF."""

    if not matrix:
        return []
    work = [list(row) for row in matrix]
    rows, columns = len(work), len(work[0])
    require(all(len(row) == columns for row in work), "nullspace matrix is ragged")
    pivot_columns: list[int] = []
    pivot_row = 0
    for column in range(columns):
        if pivot_row == rows:
            break
        selected = max(range(pivot_row, rows), key=lambda row: abs(work[row][column]))
        if abs(work[selected][column]) <= threshold:
            continue
        work[pivot_row], work[selected] = work[selected], work[pivot_row]
        divisor = work[pivot_row][column]
        for item in range(column, columns):
            work[pivot_row][item] /= divisor
        for row in range(rows):
            if row == pivot_row or abs(work[row][column]) <= threshold:
                continue
            multiplier = work[row][column]
            for item in range(column, columns):
                work[row][item] -= multiplier * work[pivot_row][item]
        pivot_columns.append(column)
        pivot_row += 1
    free_columns = [column for column in range(columns) if column not in pivot_columns]
    basis: list[list[Decimal]] = []
    for free_column in free_columns:
        vector = [Decimal(0)] * columns
        vector[free_column] = Decimal(1)
        for row, column in enumerate(pivot_columns):
            vector[column] = -work[row][free_column]
        basis.append(vector)
    return basis


def matrix_from_columns(columns: Sequence[Sequence[Decimal]]) -> list[list[Decimal]]:
    if not columns:
        return []
    return [[column[row] for column in columns] for row in range(len(columns[0]))]


def column_rank(columns: Sequence[Sequence[Decimal]], tolerance: Decimal = Decimal("1e-40")) -> int:
    return decimal_rank(matrix_from_columns(columns), tolerance) if columns else 0


def normalized_rows(matrix: Sequence[Sequence[Decimal]]) -> list[list[Decimal]]:
    result: list[list[Decimal]] = []
    for row in matrix:
        norm = decimal_norm(row)
        require(norm > 0, "operator contains zero row")
        result.append([value / norm for value in row])
    return result


def decimal_householder_qrcp_trace(
    matrix: Sequence[Sequence[Decimal]],
    *,
    claimed_permutation: Sequence[int] | None = None,
    unresolved_floor: Decimal = Decimal(0),
) -> tuple[list[int], list[Decimal]]:
    """Independently reproduce the registered complete Householder-QRCP trace.

    The producer evaluates the same algebra in binary64 with extended
    accumulators.  This reference keeps the exported binary64 matrix in a
    120-digit Decimal context so pivot identity and diagonal magnitudes can be
    checked without accepting the producer trace as a premise.
    """

    if not matrix:
        return [], []
    # Keep the evolving factor in binary64, as the producer does, while all
    # norm/dot reductions below use Decimal as an independent extended
    # accumulator before their documented binary64 cast.
    factor = [[float(value) for value in row] for row in matrix]
    rows, columns = len(factor), len(factor[0])
    permutation = list(range(columns))
    diagonals: list[Decimal] = []
    for step in range(min(rows, columns)):
        trailing_norms = [
            dsum(Decimal.from_float(factor[row][column]) ** 2
                 for row in range(step, rows))
            for column in range(step, columns)
        ]
        independently_selected_offset = max(
            range(len(trailing_norms)), key=lambda offset: trailing_norms[offset]
        )
        selected = step + independently_selected_offset
        if claimed_permutation is not None:
            require(len(claimed_permutation) == columns,
                    "independent QRCP claimed-permutation length")
            claimed_original = claimed_permutation[step]
            require(claimed_original in permutation[step:],
                    "independent QRCP claimed-permutation suffix")
            selected = permutation.index(claimed_original, step)
            maximum_squared = trailing_norms[independently_selected_offset]
            selected_squared = trailing_norms[selected - step]
            if maximum_squared == 0:
                # The registered algorithm performs no arbitrary permutation of
                # an identically zero suffix.  Enforcing that fact prevents a
                # fabricated suffix trace from escaping through the early exit.
                require(selected == step,
                        f"independent QRCP permuted zero suffix at step {step}")
            elif maximum_squared.sqrt() > unresolved_floor:
                tie_budget = (
                    Decimal(512) * Decimal(max(rows, columns)) * EPS64
                    * max(maximum_squared, MIN_NORMAL)
                )
                require(maximum_squared - selected_squared <= tie_budget,
                        "independent QRCP selected nonmaximal pivot at step "
                        f"{step}: selected2={selected_squared} max2={maximum_squared} "
                        f"budget={tie_budget}")
        selected_norm = math.sqrt(float(max(trailing_norms[selected - step], Decimal(0))))
        if selected_norm == 0.0:
            diagonals.append(Decimal(0))
            continue
        if selected != step:
            for row in range(rows):
                factor[row][step], factor[row][selected] = (
                    factor[row][selected], factor[row][step]
                )
            permutation[step], permutation[selected] = (
                permutation[selected], permutation[step]
            )
        column_norm = math.sqrt(float(dsum(
            Decimal.from_float(factor[row][step]) ** 2 for row in range(step, rows)
        )))
        first = factor[step][step]
        alpha = -column_norm if first >= 0 else column_norm
        reflector = [factor[row][step] for row in range(step, rows)]
        reflector[0] -= alpha
        reflector_squared = dsum(Decimal.from_float(value) ** 2 for value in reflector)
        require(reflector_squared > 0, "independent QRCP degenerate reflector")
        for column in range(step, columns):
            product = dsum(
                Decimal.from_float(reflector[row - step])
                * Decimal.from_float(factor[row][column])
                for row in range(step, rows)
            )
            scale = float(Decimal(2) * product / reflector_squared)
            for row in range(step, rows):
                factor[row][column] -= scale * reflector[row - step]
        factor[step][step] = alpha
        for row in range(step + 1, rows):
            factor[row][step] = 0.0
        diagonals.append(Decimal.from_float(abs(alpha)))
    # The evidence format records one pivot entry per column.  Wide matrices
    # append structural-zero free columns after the Householder steps.
    diagonals.extend(Decimal(0) for _ in range(columns - len(diagonals)))
    return permutation, diagonals


def symmetric_tridiagonal_binary64(
    matrix: Sequence[Sequence[float]],
) -> tuple[list[float], list[float]]:
    """Householder-reduce a symmetric matrix for an independent spectrum."""

    work = [list(row) for row in matrix]
    dimension = len(work)
    for step in range(max(0, dimension - 2)):
        vector = [work[row][step] for row in range(step + 1, dimension)]
        norm = math.sqrt(math.fsum(value * value for value in vector))
        if norm == 0.0:
            continue
        alpha = -math.copysign(norm, vector[0])
        vector[0] -= alpha
        vector_norm = math.sqrt(math.fsum(value * value for value in vector))
        if vector_norm == 0.0:
            continue
        vector = [value / vector_norm for value in vector]
        start = step + 1
        product = [
            2.0 * math.fsum(
                work[start + row][start + column] * vector[column]
                for column in range(len(vector))
            )
            for row in range(len(vector))
        ]
        correction = -math.fsum(
            vector[index] * product[index] for index in range(len(vector))
        )
        product = [
            product[index] + correction * vector[index]
            for index in range(len(vector))
        ]
        for row in range(len(vector)):
            for column in range(row, len(vector)):
                value = (
                    work[start + row][start + column]
                    - vector[row] * product[column]
                    - product[row] * vector[column]
                )
                work[start + row][start + column] = value
                work[start + column][start + row] = value
        work[start][step] = work[step][start] = alpha
        for row in range(start + 1, dimension):
            work[row][step] = work[step][row] = 0.0
    diagonal = [work[index][index] for index in range(dimension)]
    off_diagonal = [work[index + 1][index] for index in range(dimension - 1)]
    return diagonal, off_diagonal


def tridiagonal_eigenvalues_binary64(
    diagonal: Sequence[float], off_diagonal: Sequence[float]
) -> list[float]:
    """Return all symmetric-tridiagonal eigenvalues via Sturm bisection."""

    dimension = len(diagonal)
    if dimension == 0:
        return []
    lower = min(
        diagonal[index]
        - (abs(off_diagonal[index - 1]) if index else 0.0)
        - (abs(off_diagonal[index]) if index + 1 < dimension else 0.0)
        for index in range(dimension)
    )
    upper = max(
        diagonal[index]
        + (abs(off_diagonal[index - 1]) if index else 0.0)
        + (abs(off_diagonal[index]) if index + 1 < dimension else 0.0)
        for index in range(dimension)
    )
    padding = 64.0 * sys.float_info.epsilon * max(1.0, abs(lower), abs(upper))
    lower -= padding
    upper += padding
    tiny = sys.float_info.min ** 0.5

    def count_below(value: float) -> int:
        pivot = diagonal[0] - value
        count = int(pivot < 0.0)
        for index in range(1, dimension):
            if abs(pivot) < tiny:
                pivot = -tiny if pivot < 0.0 else tiny
            pivot = diagonal[index] - value - off_diagonal[index - 1] ** 2 / pivot
            count += int(pivot < 0.0)
        return count

    result: list[float] = []
    for target in range(dimension):
        low, high = lower, upper
        for _iteration in range(96):
            midpoint = low + (high - low) / 2.0
            if midpoint == low or midpoint == high:
                break
            if count_below(midpoint) <= target:
                low = midpoint
            else:
                high = midpoint
        result.append(low + (high - low) / 2.0)
    return result


def singular_values_reference(
    matrix: Sequence[Sequence[Decimal]],
) -> tuple[list[Decimal], Decimal]:
    """Direct Golub--Kahan bidiagonal SVD using only binary64 primitives.

    Forming ``A^T A`` squares the condition number and can erase a resolved
    singular mode long before the registered QR rank band.  This path instead
    bidiagonalizes A directly and diagonalizes that bidiagonal matrix.  The
    returned absolute backward-error budget is deliberately conservative and
    is used to quarantine, rather than compare, any value that is not resolved
    above the algorithm/roundoff band.
    """

    if not matrix or not matrix[0]:
        return [], Decimal(0)
    require(all(len(row) == len(matrix[0]) for row in matrix),
            "direct SVD received a ragged matrix")
    values = [[float(value) for value in row] for row in matrix]
    if len(values) < len(values[0]):
        values = [list(column) for column in zip(*values, strict=True)]
    m, n = len(values), len(values[0])
    s = [0.0] * n
    e = [0.0] * n
    work = [0.0] * m
    nct = min(m - 1, n)
    nrt = max(0, min(n - 2, m))
    for k in range(max(nct, nrt)):
        if k < nct:
            s[k] = math.hypot(*(values[row][k] for row in range(k, m)))
            if s[k] != 0.0:
                if values[k][k] < 0.0:
                    s[k] = -s[k]
                for row in range(k, m):
                    values[row][k] /= s[k]
                values[k][k] += 1.0
            s[k] = -s[k]
        for column in range(k + 1, n):
            if k < nct and s[k] != 0.0:
                factor = -math.fsum(
                    values[row][k] * values[row][column]
                    for row in range(k, m)
                ) / values[k][k]
                for row in range(k, m):
                    values[row][column] += factor * values[row][k]
            e[column] = values[k][column]
        if k < nrt:
            e[k] = math.hypot(*(e[column] for column in range(k + 1, n)))
            if e[k] != 0.0:
                if e[k + 1] < 0.0:
                    e[k] = -e[k]
                for column in range(k + 1, n):
                    e[column] /= e[k]
                e[k + 1] += 1.0
            e[k] = -e[k]
            if k + 1 < m and e[k] != 0.0:
                for row in range(k + 1, m):
                    work[row] = 0.0
                for column in range(k + 1, n):
                    for row in range(k + 1, m):
                        work[row] += e[column] * values[row][column]
                for column in range(k + 1, n):
                    factor = -e[column] / e[k + 1]
                    for row in range(k + 1, m):
                        values[row][column] += factor * work[row]

    if nct < n:
        s[nct] = values[nct][nct]
    if nrt + 1 < n:
        e[nrt] = values[nrt][n - 1]
    e[n - 1] = 0.0
    active = n
    iterations = 0
    iteration_cap = 4096 * max(1, n)
    tiny = sys.float_info.min
    epsilon = sys.float_info.epsilon
    while active > 0:
        require(iterations <= iteration_cap, "direct SVD iteration limit")
        split = active - 2
        while split >= -1:
            if split == -1:
                break
            if abs(e[split]) <= tiny + epsilon * (
                abs(s[split]) + abs(s[split + 1])
            ):
                e[split] = 0.0
                break
            split -= 1
        if split == active - 2:
            case = 4
        else:
            scan = active - 1
            while scan >= split:
                if scan == split:
                    break
                scale = (abs(e[scan]) if scan != active else 0.0) + (
                    abs(e[scan - 1]) if scan != split + 1 else 0.0
                )
                if abs(s[scan]) <= tiny + epsilon * scale:
                    s[scan] = 0.0
                    break
                scan -= 1
            if scan == split:
                case = 3
            elif scan == active - 1:
                case = 1
            else:
                case = 2
                split = scan
        split += 1

        if case == 1:
            factor = e[active - 2]
            e[active - 2] = 0.0
            for index in range(active - 2, split - 1, -1):
                magnitude = math.hypot(s[index], factor)
                cosine = s[index] / magnitude if magnitude else 1.0
                sine = factor / magnitude if magnitude else 0.0
                s[index] = magnitude
                if index != split:
                    factor = -sine * e[index - 1]
                    e[index - 1] *= cosine
        elif case == 2:
            factor = e[split - 1]
            e[split - 1] = 0.0
            for index in range(split, active):
                magnitude = math.hypot(s[index], factor)
                cosine = s[index] / magnitude if magnitude else 1.0
                sine = factor / magnitude if magnitude else 0.0
                s[index] = magnitude
                factor = -sine * e[index]
                e[index] *= cosine
        elif case == 3:
            scale = max(
                abs(s[active - 1]), abs(s[active - 2]), abs(e[active - 2]),
                abs(s[split]), abs(e[split]),
            )
            require(scale > 0.0 and math.isfinite(scale),
                    "direct SVD invalid QR scale")
            last = s[active - 1] / scale
            previous = s[active - 2] / scale
            off = e[active - 2] / scale
            first = s[split] / scale
            first_off = e[split] / scale
            b_value = ((previous + last) * (previous - last) + off * off) / 2.0
            c_value = (last * off) ** 2
            shift = 0.0
            if b_value != 0.0 or c_value != 0.0:
                shift = math.sqrt(b_value * b_value + c_value)
                if b_value < 0.0:
                    shift = -shift
                shift = c_value / (b_value + shift)
            factor = (first + last) * (first - last) + shift
            carry = first * first_off
            for index in range(split, active - 1):
                magnitude = math.hypot(factor, carry)
                cosine = factor / magnitude if magnitude else 1.0
                sine = carry / magnitude if magnitude else 0.0
                if index != split:
                    e[index - 1] = magnitude
                factor = cosine * s[index] + sine * e[index]
                e[index] = cosine * e[index] - sine * s[index]
                carry = sine * s[index + 1]
                s[index + 1] *= cosine
                magnitude = math.hypot(factor, carry)
                cosine = factor / magnitude if magnitude else 1.0
                sine = carry / magnitude if magnitude else 0.0
                s[index] = magnitude
                factor = cosine * e[index] + sine * s[index + 1]
                s[index + 1] = -sine * e[index] + cosine * s[index + 1]
                carry = sine * e[index + 1]
                e[index + 1] *= cosine
            e[active - 2] = factor
            iterations += 1
        else:
            if s[split] <= 0.0:
                s[split] = -s[split]
            while split < active - 1 and s[split] < s[split + 1]:
                s[split], s[split + 1] = s[split + 1], s[split]
                split += 1
            active -= 1
            iterations = 0

    require(all(math.isfinite(value) and value >= 0.0 for value in s),
            "direct SVD produced nonfinite/negative value")
    result = [abs(Decimal.from_float(value)) for value in sorted(s, reverse=True)]
    matrix_norm = decimal_matrix_norm(matrix)
    backward_error = (
        Decimal(256) * Decimal(max(m, n)) * EPS64 * max(matrix_norm, MIN_NORMAL)
    )
    return result, backward_error


def orthonormalize_columns(
    columns: Sequence[Sequence[Decimal]], relative_tolerance: Decimal
) -> list[list[Decimal]]:
    result: list[list[Decimal]] = []
    for column in columns:
        residual = list(column)
        original_norm = decimal_norm(residual)
        for _pass in range(2):
            for basis in result:
                coefficient = decimal_dot(basis, residual)
                residual = [value - coefficient * direction
                            for value, direction in zip(residual, basis, strict=True)]
        norm = decimal_norm(residual)
        if norm > relative_tolerance * max(original_norm, MIN_NORMAL):
            result.append([value / norm for value in residual])
    return result


def subspace_projection_residual(
    vector: Sequence[Decimal], orthonormal_basis: Sequence[Sequence[Decimal]]
) -> Decimal:
    residual = list(vector)
    for basis in orthonormal_basis:
        coefficient = decimal_dot(basis, residual)
        residual = [value - coefficient * direction
                    for value, direction in zip(residual, basis, strict=True)]
    return decimal_norm(residual) / max(decimal_norm(vector), MIN_NORMAL)


def orthonormality_residual(columns: Sequence[Sequence[Decimal]]) -> Decimal:
    return decimal_norm(
        decimal_dot(columns[first], columns[second])
        - (Decimal(1) if first == second else Decimal(0))
        for first in range(len(columns))
        for second in range(len(columns))
    )


def restricted_operator_norm(
    matrix: Sequence[Sequence[Decimal]],
    orthonormal_basis: Sequence[Sequence[Decimal]],
) -> Decimal:
    """Return an independently resolved induced 2-norm on a subspace."""
    if not matrix or not orthonormal_basis:
        return Decimal(0)
    restricted = [
        [decimal_dot(row, mode) for mode in orthonormal_basis]
        for row in matrix
    ]
    singular_values, backward_error = singular_values_reference(restricted)
    return max(
        Decimal(0),
        (singular_values[0] if singular_values else Decimal(0)) - backward_error,
    )


def q_rref_rank(matrix: Sequence[Sequence[Q]]) -> int:
    work = [list(row) for row in matrix]
    if not work:
        return 0
    rows, columns = len(work), len(work[0])
    rank = 0
    for column in range(columns):
        pivot = next((row for row in range(rank, rows) if work[row][column] != 0), None)
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        divisor = work[rank][column]
        work[rank] = [value / divisor for value in work[rank]]
        for row in range(rows):
            if row == rank or work[row][column] == 0:
                continue
            multiplier = work[row][column]
            work[row] = [
                work[row][entry] - multiplier * work[rank][entry]
                for entry in range(columns)
            ]
        rank += 1
        if rank == rows:
            break
    return rank


def vector_subtract(first: Sequence[Decimal], second: Sequence[Decimal]) -> list[Decimal]:
    return [a - b for a, b in zip(first, second, strict=True)]


def cross(first: Sequence[Decimal], second: Sequence[Decimal]) -> list[Decimal]:
    return [
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    ]


def q_cross(first: Sequence[Q], second: Sequence[Q]) -> list[Q]:
    return [
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    ]


def close_decimal(actual: Decimal, expected: Decimal, *, factor: Decimal = Decimal("1e-11")) -> bool:
    scale = max(Decimal(1), abs(actual), abs(expected))
    return abs(actual - expected) <= factor * scale


def gamma_n(operation_count: int) -> Decimal:
    require(operation_count >= 0, "negative floating operation count")
    product = Decimal(operation_count) * EPS64
    require(product < 1, "floating operation count exceeds gamma domain")
    return product / (Decimal(1) - product)


def forward_error_budget(
    physical_scale: Decimal, operation_count: int, *, safety_factor: int = 16
) -> Decimal:
    """Conservative binary64 forward-error envelope without a unitless floor."""

    require(physical_scale >= 0, "negative forward-error scale")
    scale = max(physical_scale, MIN_NORMAL)
    return (
        Decimal(safety_factor) * gamma_n(operation_count) * scale
        + Decimal(safety_factor) * MIN_NORMAL
    )


def require_forward_close(
    actual: Decimal,
    expected: Decimal,
    *,
    physical_scale: Decimal,
    operation_count: int,
    where: str,
    safety_factor: int = 16,
) -> None:
    budget = forward_error_budget(
        physical_scale, operation_count, safety_factor=safety_factor
    )
    require(abs(actual - expected) <= budget,
            f"{where}: exceeds independent binary64 forward-error budget")


def require_string_list(value: Any, where: str) -> list[str]:
    require(isinstance(value, list), f"{where}: expected array")
    result: list[str] = []
    for index, item in enumerate(value):
        require(isinstance(item, str), f"{where}[{index}]: expected string")
        identifier(item, f"{where}[{index}]")
        result.append(item)
    require(result == sorted(set(result)), f"{where}: must be sorted and unique")
    return result


def validate_summary(summary: Mapping[str, Any], tables: Mapping[str, list[dict[str, str]]]) -> None:
    require(tuple(summary) == SUMMARY_KEY_ORDER, "summary key order mismatch")
    require(summary["schema"] == SUMMARY_SCHEMA, "summary schema")
    require(summary["mode"] in {"full", "smoke", "failure_fixture"}, "summary mode")
    require(type(summary["provisional"]) is bool, "summary provisional: expected JSON boolean")
    require(type(summary["sweep_complete"]) is bool,
            "summary sweep_complete: expected JSON boolean")
    require(
        (summary["provisional"], summary["sweep_complete"])
        == ((False, True) if summary["mode"] == "full" else (True, False)),
        "summary mode/provisional/sweep-complete contract",
    )
    require(summary["producer"] == PRODUCER, "summary producer")
    require(summary["seed"] == SEED, "summary seed")
    require(summary["parent_sha"] == ACCEPTED_PARENT_SHA, "summary accepted parent")
    require(summary["branch"] == BRANCH, "summary branch")
    require(isinstance(summary["source_sha"], str), "summary source SHA type")
    require(SOURCE_SHA_RE.fullmatch(summary["source_sha"]) is not None, "summary source SHA")
    boolean_keys = (
        "dirty",
        "checkpoint_round_trip_all_pass",
        "diagnostics_read_only_all_exact",
        "neighbor_lookup_all_agree",
        "negative_control_reproduced",
        "affine_objectivity_all_pass",
        "finite_objectivity_all_pass",
        "invariance_all_pass",
        "decisive_rank_rows_all_unambiguous",
        "raw_decision_rows_all_exported",
        "independent_reference_all_pass",
        "nondeterminism_detected",
        "promotion",
    )
    for key in boolean_keys:
        require(type(summary[key]) is bool, f"summary {key}: expected JSON boolean")
    require(summary["promotion"] is False, "summary promotion must be false")
    registered_configurations = require_string_list(
        summary["registered_configuration_ids"], "registered_configuration_ids"
    )
    registered_operators = require_string_list(
        summary["registered_operator_ids"], "registered_operator_ids"
    )
    require(
        registered_configurations
        == sorted(row["configuration_id"] for row in tables["configurations.csv"]),
        "registered configuration IDs differ from table",
    )
    require(
        registered_operators == sorted(row["operator_id"] for row in tables["operator_status.csv"]),
        "registered operator IDs differ from table",
    )
    if summary["mode"] in {"smoke", "failure_fixture"}:
        require(set(registered_configurations) == SMOKE_CONFIGURATION_IDS,
                "smoke configuration inventory differs from preregistered control")
        require(set(registered_operators) == SMOKE_OPERATOR_IDS,
                "smoke operator inventory differs from preregistered control")
    counts = summary["row_counts"]
    require(isinstance(counts, dict), "summary row_counts type")
    require(set(counts) == set(CSV_SCHEMAS), "summary row_counts key set")
    require(tuple(counts) == tuple(sorted(CSV_SCHEMAS)), "summary row_counts key order")
    for name, rows in tables.items():
        require(type(counts[name]) is int and counts[name] == len(rows), f"summary row count {name}")
    tolerances = summary["tolerances"]
    require(tolerances == EXPECTED_TOLERANCES, "summary tolerance contract mismatch")
    require(tuple(tolerances) == tuple(EXPECTED_TOLERANCES), "summary tolerance key order")
    findings = summary["candidate_findings"]
    require(isinstance(findings, dict) and set(findings) == set(CANDIDATE_FINDINGS), "candidate findings keys")
    require(tuple(findings) == tuple(CANDIDATE_FINDINGS), "candidate findings key order")
    for candidate, allowed in CANDIDATE_FINDINGS.items():
        require(findings[candidate] in allowed, f"candidate {candidate} finding")
    require(summary["decision"] in DECISIONS, "summary decision enum")


def require_table_order(tables: Mapping[str, list[dict[str, str]]]) -> None:
    def numeric(value: str) -> int:
        return int(value) if value != "NA" else -1

    keys: dict[str, Any] = {
        "configurations.csv": lambda row: (row["configuration_id"],),
        "packets.csv": lambda row: (row["configuration_id"], numeric(row["packet_index"])),
        "neighbor_pairs.csv": lambda row: (
            row["configuration_id"], row["lookup_phase"],
            numeric(row["low_packet_id"]), numeric(row["high_packet_id"]),
        ),
        "relations.csv": lambda row: (row["configuration_id"], numeric(row["relation_index"])),
        "operator_status.csv": lambda row: (row["operator_id"],),
        "operator_entries.csv": lambda row: (
            row["operator_id"], numeric(row["row_index"]), numeric(row["column_index"]),
        ),
        "moment_diagnostics.csv": lambda row: (row["operator_id"], numeric(row["packet_id"])),
        "affine_objectivity.csv": lambda row: (row["operator_id"], row["test_id"]),
        "invariance.csv": lambda row: (row["comparison_id"],),
        "rigid_basis.csv": lambda row: (
            row["operator_id"], row["basis_kind"], numeric(row["mode_index"]),
            numeric(row["dof_index"]),
        ),
        "rank_status.csv": lambda row: (
            row["operator_id"], 0 if row["record_kind"] == "summary" else 1,
            numeric(row["pivot_step"]),
        ),
        "nullspace_modes.csv": lambda row: (
            row["operator_id"], row["basis_kind"], numeric(row["mode_index"]),
            numeric(row["dof_index"]),
        ),
        "nullspace_metrics.csv": lambda row: (
            row["operator_id"], row["basis_kind"], numeric(row["mode_index"]),
        ),
        "grid_gauge.csv": lambda row: (row["operator_id"], numeric(row["mode_index"])),
        "exact_reference.csv": lambda row: (row["reference_id"],),
        "grid_nodes.csv": lambda row: (
            row["sampling_operator_id"], numeric(row["node_index"]),
        ),
        "checkpoints.csv": lambda row: (
            row["configuration_id"],
            {
                "authoritative_before": 0,
                "round_trip_reserialized": 1,
                "after_diagnostics": 2,
            }.get(row["checkpoint_kind"], 99),
        ),
        "permutation_controls.csv": lambda row: (row["control_id"],),
        "permutation_entries.csv": lambda row: (
            row["control_id"], numeric(row["row_index"]), numeric(row["column_index"]),
        ),
    }
    for name, rows in tables.items():
        actual = [keys[name](row) for row in rows]
        require(actual == sorted(actual), f"{name}: rows not in deterministic order")
        require(len(actual) == len(set(actual)), f"{name}: duplicate deterministic key")


def validate_packet_tables(
    configurations: Sequence[dict[str, str]],
    packet_rows: Sequence[dict[str, str]],
) -> tuple[
    dict[str, list[dict[str, str]]],
    dict[str, dict[int, tuple[Decimal, Decimal, Decimal]]],
    dict[str, dict[int, tuple[Q, Q, Q]]],
]:
    by_configuration: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in packet_rows:
        by_configuration[row["configuration_id"]].append(row)
    configuration_ids = {row["configuration_id"] for row in configurations}
    require(set(by_configuration) == configuration_ids, "packets/configurations ID mismatch")
    decimal_positions: dict[str, dict[int, tuple[Decimal, Decimal, Decimal]]] = {}
    fraction_positions: dict[str, dict[int, tuple[Q, Q, Q]]] = {}
    for configuration in configurations:
        configuration_id = configuration["configuration_id"]
        identifier(configuration_id, f"configuration {configuration_id}")
        rows = by_configuration[configuration_id]
        expected_count = unsigned(configuration["packet_count"], f"{configuration_id} packet_count", minimum=1)
        require(len(rows) == expected_count, f"{configuration_id}: packet count mismatch")
        ids: list[int] = []
        positions_d: dict[int, tuple[Decimal, Decimal, Decimal]] = {}
        positions_q: dict[int, tuple[Q, Q, Q]] = {}
        for expected_index, row in enumerate(rows):
            require(
                unsigned(row["packet_index"], f"{configuration_id} packet_index") == expected_index,
                f"{configuration_id}: packet indices not contiguous",
            )
            packet_id = unsigned(row["packet_id"], f"{configuration_id} packet_id", minimum=1)
            unsigned(row["mass_quanta"], f"{configuration_id} mass_quanta", minimum=1)
            ids.append(packet_id)
            values_d = tuple(
                binary64(row[field], f"{configuration_id}/{packet_id}/{field}")
                for field in ("x_m", "y_m", "z_m")
            )
            values_q = tuple(
                fraction64(row[field], f"{configuration_id}/{packet_id}/{field}")
                for field in ("x_m", "y_m", "z_m")
            )
            positions_d[packet_id] = values_d  # type: ignore[assignment]
            positions_q[packet_id] = values_q  # type: ignore[assignment]
            for field in (
                "vx_m_per_s", "vy_m_per_s", "vz_m_per_s",
                "jitter_dx_m", "jitter_dy_m", "jitter_dz_m",
            ):
                binary64(row[field], f"{configuration_id}/{packet_id}/{field}")
        require(ids == sorted(set(ids)), f"{configuration_id}: packet IDs not canonical")
        digest = grouped_payload_digest(
            b"MLS-MECHANICAL-OBSERVABILITY-PACKETS-v1", PACKET_FIELDS, rows
        )
        require(configuration["packet_payload_sha256"] == digest, f"{configuration_id}: packet digest")
        decimal_positions[configuration_id] = positions_d
        fraction_positions[configuration_id] = positions_q
    return by_configuration, decimal_positions, fraction_positions


def exact_affine_rank(points: Sequence[tuple[Q, Q, Q]]) -> int:
    matrix = [[point[0], point[1], point[2], Q(1)] for point in points]
    return max(0, q_rref_rank(matrix) - 1)


def exact_direction_rank(
    center: tuple[Q, Q, Q], neighbors: Sequence[tuple[Q, Q, Q]]
) -> int:
    matrix = [[neighbor[axis] - center[axis] for axis in range(3)] for neighbor in neighbors]
    return q_rref_rank(matrix)


def numerical_affine_rank(points: Sequence[Sequence[Decimal]]) -> int:
    if not points:
        return 0
    origin = points[0]
    return decimal_rank(
        [[point[axis] - origin[axis] for axis in range(3)] for point in points[1:]],
        Decimal("1e-12"),
    )


def numerical_direction_rank(
    center: Sequence[Decimal], neighbors: Sequence[Sequence[Decimal]]
) -> int:
    return decimal_rank(
        [[neighbor[axis] - center[axis] for axis in range(3)] for neighbor in neighbors],
        Decimal("1e-12"),
    )


def numerical_rigid_rank(points: Sequence[Sequence[Decimal]]) -> int:
    if not points:
        return 0
    centroid = [dsum(point[axis] for point in points) / Decimal(len(points)) for axis in range(3)]
    axes = (
        (Decimal(1), Decimal(0), Decimal(0)),
        (Decimal(0), Decimal(1), Decimal(0)),
        (Decimal(0), Decimal(0), Decimal(1)),
    )
    columns: list[list[Decimal]] = []
    for axis in axes:
        columns.append([axis[component] for _point in points for component in range(3)])
    for omega in axes:
        columns.append(
            [
                component
                for point in points
                for component in cross(omega, [point[axis] - centroid[axis] for axis in range(3)])
            ]
        )
    matrix = [[column[row] for column in columns] for row in range(3 * len(points))]
    return decimal_rank(matrix, Decimal("1e-12"))


def graph_connected(packet_ids: Sequence[int], edges: Sequence[tuple[int, int]]) -> bool:
    if not packet_ids:
        return False
    adjacency: dict[int, set[int]] = {packet_id: set() for packet_id in packet_ids}
    for first, second in edges:
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


def rigid_generator_rank(points: Sequence[tuple[Q, Q, Q]]) -> int:
    columns: list[list[Q]] = []
    axes = ((Q(1), Q(0), Q(0)), (Q(0), Q(1), Q(0)), (Q(0), Q(0), Q(1)))
    for axis in axes:
        columns.append([axis[component] for _point in points for component in range(3)])
    for omega in axes:
        columns.append(
            [component for point in points for component in q_cross(omega, point)]
        )
    matrix = [[column[row] for column in columns] for row in range(3 * len(points))]
    return q_rref_rank(matrix)


def derive_generic_solid_facts(
    positions: Mapping[int, tuple[Q, Q, Q]],
    retained_edges: Sequence[tuple[int, int]],
    intentionally_flexible: bool,
) -> dict[str, int | bool]:
    """Derive the preregistered generic-solid topology gate exactly."""

    packet_ids = sorted(positions)
    incident: dict[int, set[int]] = {packet_id: set() for packet_id in packet_ids}
    for first, second in retained_edges:
        require(first in incident and second in incident and first != second,
                "generic-solid facts: invalid edge endpoint")
        incident[first].add(second)
        incident[second].add(first)
    affine_rank = exact_affine_rank([positions[packet_id] for packet_id in packet_ids])
    connected = graph_connected(packet_ids, retained_edges)
    direction_ranks = [
        exact_direction_rank(
            positions[packet_id],
            [positions[neighbor] for neighbor in sorted(incident[packet_id])],
        )
        for packet_id in packet_ids
    ]
    minimum_direction_rank = min(direction_ranks, default=0)
    rigid_rank = rigid_generator_rank([positions[packet_id] for packet_id in packet_ids])
    edge_lower_bound = max(0, 3 * len(packet_ids) - 6)
    generic_gate = (
        affine_rank == 3
        and connected
        and len(retained_edges) >= edge_lower_bound
        and minimum_direction_rank == 3
        and rigid_rank == 6
        and not intentionally_flexible
    )
    return {
        "affine_rank": affine_rank,
        "connected": connected,
        "edge_count": len(retained_edges),
        "edge_lower_bound": edge_lower_bound,
        "minimum_direction_rank": minimum_direction_rank,
        "rigid_rank": rigid_rank,
        "generic_solid_gate": generic_gate,
    }


def q_rigid_generators(
    positions: Mapping[int, tuple[Q, Q, Q]],
) -> list[list[Q]]:
    packet_ids = sorted(positions)
    axes = ((Q(1), Q(0), Q(0)), (Q(0), Q(1), Q(0)), (Q(0), Q(0), Q(1)))
    columns: list[list[Q]] = []
    for axis in axes:
        columns.append([axis[component] for _packet in packet_ids for component in range(3)])
    for omega in axes:
        columns.append([
            component
            for packet_id in packet_ids
            for component in q_cross(omega, positions[packet_id])
        ])
    return columns


def validate_neighbors(
    configurations: Sequence[dict[str, str]],
    rows: Sequence[dict[str, str]],
    positions: Mapping[str, Mapping[int, tuple[Decimal, Decimal, Decimal]]],
) -> tuple[dict[str, dict[str, set[tuple[int, int]]]], bool]:
    by_configuration: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_phase: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_configuration[row["configuration_id"]].append(row)
        by_phase[(row["configuration_id"], row["lookup_phase"])].append(row)
    configuration_ids = {row["configuration_id"] for row in configurations}
    require(set(by_configuration) == configuration_ids, "neighbor/configuration ID mismatch")
    eligible: dict[str, dict[str, set[tuple[int, int]]]] = defaultdict(dict)
    all_lookup_agree = True
    for configuration in configurations:
        configuration_id = configuration["configuration_id"]
        config_rows = by_configuration[configuration_id]
        digest = grouped_payload_digest(
            b"MLS-MECHANICAL-OBSERVABILITY-NEIGHBORS-v1",
            NEIGHBOR_PAIR_FIELDS,
            config_rows,
        )
        require(configuration["neighbor_payload_sha256"] == digest, f"{configuration_id}: neighbor digest")
        support = binary64(configuration["support_radius_m"], f"{configuration_id} support")
        require(support is not None and support > 0, f"{configuration_id}: nonpositive support")
        packet_ids = sorted(positions[configuration_id])
        expected_pairs = set(itertools.combinations(packet_ids, 2))
        phases = sorted({row["lookup_phase"] for row in config_rows})
        require(tuple(phases) == LOOKUP_PHASES,
                f"{configuration_id}: lookup phases differ from frozen p000+p037 matrix")
        require(configuration["lookup_phase"] in phases, f"{configuration_id}: declared phase absent")
        for phase in phases:
            phase_rows = by_phase[(configuration_id, phase)]
            actual_pairs: set[tuple[int, int]] = set()
            phase_eligible: set[tuple[int, int]] = set()
            for row in phase_rows:
                low = unsigned(row["low_packet_id"], f"{configuration_id}/{phase} low", minimum=1)
                high = unsigned(row["high_packet_id"], f"{configuration_id}/{phase} high", minimum=1)
                require(low < high and low in positions[configuration_id] and high in positions[configuration_id],
                        f"{configuration_id}/{phase}: invalid pair")
                pair = (low, high)
                require(pair not in actual_pairs, f"{configuration_id}/{phase}: duplicate pair")
                actual_pairs.add(pair)
                offset = vector_subtract(positions[configuration_id][high], positions[configuration_id][low])
                distance_squared = decimal_dot(offset, offset)
                support_squared = support * support
                emitted_distance = binary64(
                    row["distance_squared_m2"], f"{configuration_id}/{phase}/{pair} distance"
                )
                emitted_support = binary64(
                    row["support_radius_squared_m2"], f"{configuration_id}/{phase}/{pair} support2"
                )
                assert emitted_distance is not None and emitted_support is not None
                require(close_decimal(emitted_distance, distance_squared, factor=Decimal("2e-14")),
                        f"{configuration_id}/{phase}/{pair}: distance mismatch")
                require(close_decimal(emitted_support, support_squared, factor=Decimal("2e-14")),
                        f"{configuration_id}/{phase}/{pair}: support-square mismatch")
                independently_eligible = distance_squared > 0 and distance_squared < support_squared
                brute = boolean(row["brute_force_eligible"], f"{configuration_id}/{phase}/{pair} brute")
                lookup = boolean(row["lookup_eligible"], f"{configuration_id}/{phase}/{pair} lookup")
                agreement = boolean(row["agreement"], f"{configuration_id}/{phase}/{pair} agreement")
                require(brute == independently_eligible, f"{configuration_id}/{phase}/{pair}: brute-force mismatch")
                independently_agrees = lookup == brute
                require(agreement == independently_agrees,
                        f"{configuration_id}/{phase}/{pair}: agreement flag mismatch")
                all_lookup_agree = all_lookup_agree and independently_agrees
                weight = binary64(row["weight"], f"{configuration_id}/{phase}/{pair} weight", optional=True)
                if independently_eligible:
                    expected_weight = (Decimal(1) - distance_squared / support_squared) ** 2
                    require(weight is not None and close_decimal(weight, expected_weight, factor=Decimal("4e-14")),
                            f"{configuration_id}/{phase}/{pair}: weight mismatch")
                    phase_eligible.add(pair)
                else:
                    require(weight is None, f"{configuration_id}/{phase}/{pair}: ineligible weight must be NA")
            require(actual_pairs == expected_pairs, f"{configuration_id}/{phase}: incomplete pair matrix")
            eligible[configuration_id][phase] = phase_eligible
        first = eligible[configuration_id][phases[0]]
        require(all(eligible[configuration_id][phase] == first for phase in phases),
                f"{configuration_id}: grid-phase neighbor eligibility changed")
    return eligible, all_lookup_agree


def volume6_decimal(
    points: Mapping[int, tuple[Decimal, Decimal, Decimal]],
    sites: tuple[int, int, int, int],
) -> Decimal:
    center, first, second, third = (points[index] for index in sites)
    a = vector_subtract(first, center)
    b = vector_subtract(second, center)
    c = vector_subtract(third, center)
    return decimal_dot(a, cross(b, c))


def volume_score_decimal(
    points: Mapping[int, tuple[Decimal, Decimal, Decimal]],
    sites: tuple[int, int, int, int],
) -> Decimal:
    center, first, second, third = (points[index] for index in sites)
    a = vector_subtract(first, center)
    b = vector_subtract(second, center)
    c = vector_subtract(third, center)
    return dsum(decimal_dot(value, value) for value in (cross(b, c), cross(c, a), cross(a, b)))


def volume_score_fraction(
    points: Mapping[int, tuple[Q, Q, Q]], sites: tuple[int, int, int, int]
) -> Q:
    center, first, second, third = (points[index] for index in sites)
    a = [first[axis] - center[axis] for axis in range(3)]
    b = [second[axis] - center[axis] for axis in range(3)]
    c = [third[axis] - center[axis] for axis in range(3)]
    return qsum(
        qsum(component * component for component in vector)
        for vector in (q_cross(b, c), q_cross(c, a), q_cross(a, b))
    )


def validate_frozen_exact_edge_inventory(
    configuration_id: str,
    retained_edges: Sequence[tuple[int, int]],
    deleted_edges: Sequence[tuple[int, int]],
) -> None:
    expected = FROZEN_EXACT_EDGES.get(configuration_id)
    if expected is None:
        return
    require(
        tuple(retained_edges) == expected and not deleted_edges,
        f"{configuration_id}: exact-control canonical edge set mismatch",
    )


def validate_relations(
    configurations: Sequence[dict[str, str]],
    rows: Sequence[dict[str, str]],
    positions_d: Mapping[str, Mapping[int, tuple[Decimal, Decimal, Decimal]]],
    positions_q: Mapping[str, Mapping[int, tuple[Q, Q, Q]]],
) -> dict[str, dict[str, Any]]:
    by_configuration: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_configuration[row["configuration_id"]].append(row)
    configuration_ids = {row["configuration_id"] for row in configurations}
    require(set(by_configuration) == configuration_ids, "relation/configuration ID mismatch")
    topology: dict[str, dict[str, Any]] = {}
    for configuration in configurations:
        configuration_id = configuration["configuration_id"]
        config_rows = by_configuration[configuration_id]
        digest = grouped_payload_digest(
            b"MLS-MECHANICAL-OBSERVABILITY-RELATIONS-v1", RELATION_FIELDS, config_rows
        )
        require(configuration["relation_payload_sha256"] == digest, f"{configuration_id}: relation digest")
        relation_ids: set[str] = set()
        retained_edges: list[tuple[int, int]] = []
        deleted_edges: list[tuple[int, int]] = []
        volumes: list[tuple[int, int, int, int]] = []
        references: dict[str, tuple[str, Decimal]] = {}
        incident: dict[int, set[int]] = defaultdict(set)
        for expected_index, row in enumerate(config_rows):
            require(unsigned(row["relation_index"], f"{configuration_id} relation index") == expected_index,
                    f"{configuration_id}: relation indices not contiguous")
            relation_id = row["relation_id"]
            identifier(relation_id, f"{configuration_id} relation ID")
            require(relation_id not in relation_ids, f"{configuration_id}: duplicate relation ID")
            relation_ids.add(relation_id)
            kind = row["relation_kind"]
            require(kind in {"bond", "oriented_volume"}, f"{configuration_id}: relation kind")
            status = row["selection_status"]
            require(status in {"retained", "deleted"}, f"{configuration_id}: selection status")
            identifier(row["selection_source"], f"{configuration_id}: selection source")
            reference = binary64(row["reference_value"], f"{configuration_id}/{relation_id} reference")
            assert reference is not None
            references[relation_id] = (kind, reference)
            if kind == "bond":
                require(row["center_id"] == "NA" and row["third_id"] == "NA",
                        f"{configuration_id}/{relation_id}: bond optional IDs")
                first = unsigned(row["first_id"], f"{configuration_id}/{relation_id} first", minimum=1)
                second = unsigned(row["second_id"], f"{configuration_id}/{relation_id} second", minimum=1)
                require(relation_id == f"bond.{first}.{second}",
                        f"{configuration_id}/{relation_id}: bond ID encoding")
                require(first < second and first in positions_d[configuration_id] and second in positions_d[configuration_id],
                        f"{configuration_id}/{relation_id}: noncanonical bond")
                require(row["reference_units"] == "m" and row["selection_score_m4"] == "NA",
                        f"{configuration_id}/{relation_id}: bond units/score")
                offset = vector_subtract(positions_d[configuration_id][second], positions_d[configuration_id][first])
                expected_length = decimal_dot(offset, offset).sqrt()
                require(close_decimal(reference, expected_length, factor=Decimal("3e-14")),
                        f"{configuration_id}/{relation_id}: length mismatch")
                if configuration_id.startswith("exact."):
                    expected_source = "exact_control"
                elif configuration["profile"].startswith("delete") and status == "deleted":
                    expected_source = f"sha256_deletion_{configuration['profile'][6:]}"
                else:
                    expected_source = "physical_radius"
                require(row["selection_source"] == expected_source,
                        f"{configuration_id}/{relation_id}: bond provenance")
                if status == "retained":
                    retained_edges.append((first, second))
                    incident[first].add(second)
                    incident[second].add(first)
                else:
                    deleted_edges.append((first, second))
            else:
                require(status == "retained", f"{configuration_id}/{relation_id}: volume cannot be deleted")
                center = unsigned(row["center_id"], f"{configuration_id}/{relation_id} center", minimum=1)
                others = tuple(
                    unsigned(row[field], f"{configuration_id}/{relation_id} {field}", minimum=1)
                    for field in ("first_id", "second_id", "third_id")
                )
                require(list(others) == sorted(set(others)) and center not in others,
                        f"{configuration_id}/{relation_id}: noncanonical volume tuple")
                require(all(site in positions_d[configuration_id] for site in (center, *others)),
                        f"{configuration_id}/{relation_id}: unresolved volume site")
                require(row["reference_units"] == "m3", f"{configuration_id}/{relation_id}: volume units")
                sites = (center, *others)
                require(relation_id == "volume." + ".".join(str(site) for site in sites),
                        f"{configuration_id}/{relation_id}: volume ID encoding")
                expected_volume = volume6_decimal(positions_d[configuration_id], sites)
                require(close_decimal(reference, expected_volume, factor=Decimal("5e-14")),
                        f"{configuration_id}/{relation_id}: volume mismatch")
                score = binary64(row["selection_score_m4"], f"{configuration_id}/{relation_id} score")
                assert score is not None
                expected_score = volume_score_decimal(positions_d[configuration_id], sites)
                require(close_decimal(score, expected_score, factor=Decimal("8e-14")),
                        f"{configuration_id}/{relation_id}: volume score mismatch")
                expected_source = "exact_control" if configuration_id.startswith("exact.") \
                    else "volume_enrichment"
                require(row["selection_source"] == expected_source,
                        f"{configuration_id}/{relation_id}: volume provenance")
                volumes.append(sites)
        require(len(retained_edges) == len(set(retained_edges)), f"{configuration_id}: duplicate retained edge")
        require(len(deleted_edges) == len(set(deleted_edges)), f"{configuration_id}: duplicate deleted edge")
        require(not set(retained_edges) & set(deleted_edges), f"{configuration_id}: retained/deleted overlap")
        validate_frozen_exact_edge_inventory(
            configuration_id, retained_edges, deleted_edges
        )
        require(len({sites[0] for sites in volumes}) == len(volumes),
                f"{configuration_id}: more than one volume tuple for a center")
        if configuration_id.startswith("exact."):
            expected_volume_set = {(1, 2, 3, 4)} if configuration_id == \
                "exact.planar_square_plus_diagonal_and_volume" else set()
            require(set(volumes) == expected_volume_set,
                    f"{configuration_id}: exact-control volume set mismatch")
        packet_ids = sorted(positions_q[configuration_id])
        facts = derive_generic_solid_facts(
            positions_q[configuration_id],
            retained_edges,
            boolean(configuration["intentionally_flexible"], f"{configuration_id} flexible"),
        )
        affine_rank = int(facts["affine_rank"])
        connected = bool(facts["connected"])
        minimum_direction_rank = int(facts["minimum_direction_rank"])
        rigid_rank = int(facts["rigid_rank"])
        edge_lower_bound = int(facts["edge_lower_bound"])
        generic_gate = bool(facts["generic_solid_gate"])
        require(unsigned(configuration["affine_span_rank"], f"{configuration_id} affine rank") == affine_rank,
                f"{configuration_id}: affine rank mismatch")
        require(boolean(configuration["connected"], f"{configuration_id} connected") == connected,
                f"{configuration_id}: connectivity mismatch")
        require(unsigned(configuration["edge_count"], f"{configuration_id} edge count") == len(retained_edges),
                f"{configuration_id}: retained edge count mismatch")
        require(unsigned(configuration["edge_lower_bound"], f"{configuration_id} edge lower") == edge_lower_bound,
                f"{configuration_id}: edge lower bound mismatch")
        require(unsigned(configuration["min_incident_direction_rank"], f"{configuration_id} direction rank") == minimum_direction_rank,
                f"{configuration_id}: incident direction rank mismatch")
        require(unsigned(configuration["rigid_generator_rank"], f"{configuration_id} rigid rank") == rigid_rank,
                f"{configuration_id}: rigid rank mismatch")
        require(boolean(configuration["generic_solid_gate"], f"{configuration_id} generic gate") == generic_gate,
                f"{configuration_id}: generic-solid gate mismatch")
        expected_enrichment: list[tuple[int, int, int, int]] = []
        if configuration["base_configuration_id"] == configuration_id:
            for center in packet_ids:
                triples = list(itertools.combinations(sorted(incident[center]), 3))
                if not triples:
                    continue
                scored = [
                    (volume_score_fraction(
                        positions_q[configuration_id], (center, *triple)
                    ), triple)
                    for triple in triples
                ]
                maximum = max(score for score, _triple in scored)
                if maximum > 0:
                    selected = min(
                        triple for score, triple in scored if score == maximum
                    )
                    expected_enrichment.append((center, *selected))
        topology[configuration_id] = {
            "base_configuration_id": configuration["base_configuration_id"],
            "retained_edges": retained_edges,
            "deleted_edges": deleted_edges,
            "volumes": volumes,
            "references": references,
            "generic_solid_gate": generic_gate,
            "rigid_rank": rigid_rank,
            "expected_enrichment": expected_enrichment,
        }
    configurations_by_id = {row["configuration_id"]: row for row in configurations}
    for configuration_id, configuration in configurations_by_id.items():
        base_id = configuration["base_configuration_id"]
        if base_id == configuration_id or base_id not in topology:
            topology[configuration_id]["base_topology_match"] = True
            topology[configuration_id]["base_relation_ids_match"] = True
            continue
        topology[configuration_id]["base_topology_match"] = (
            topology[configuration_id]["retained_edges"]
            == topology[base_id]["retained_edges"]
            and topology[configuration_id]["deleted_edges"]
            == topology[base_id]["deleted_edges"]
            and topology[configuration_id]["volumes"]
            == topology[base_id]["volumes"]
        )
        current_references = topology[configuration_id]["references"]
        base_references = topology[base_id]["references"]
        relation_ids_match = set(current_references) == set(base_references)
        if relation_ids_match:
            relation_ids_match = all(
                current_references[relation_id][0] == kind
                for relation_id, (kind, _value) in base_references.items()
            )
        topology[configuration_id]["base_relation_ids_match"] = relation_ids_match
        scale_value = binary64(configuration["geometry_scale"], f"{configuration_id} geometry scale")
        assert scale_value is not None
        for relation_id, (kind, base_value) in base_references.items():
            if relation_id not in current_references:
                continue
            current_kind, current_value = current_references[relation_id]
            require(current_kind == kind, f"{configuration_id}/{relation_id}: relation kind changed")
            exponent = 1 if kind == "bond" else 3
            require(close_decimal(current_value, base_value * scale_value**exponent,
                                  factor=Decimal("2e-12")),
                    f"{configuration_id}/{relation_id}: finite objectivity/scale mismatch")
    for configuration_id, facts in topology.items():
        base_id = facts["base_configuration_id"]
        facts["frozen_enrichment"] = (
            topology[base_id]["expected_enrichment"]
            if base_id in topology else facts["expected_enrichment"]
        )
        if not configuration_id.startswith("exact.") and facts["volumes"]:
            require(
                facts["volumes"] == facts["frozen_enrichment"],
                f"{configuration_id}: D tuples differ from base-geometry selector",
            )
    return topology


def dense_operator(
    status: Mapping[str, str], entries: Sequence[Mapping[str, str]]
) -> list[list[Decimal]]:
    rows = unsigned(status["row_count"], f"{status['operator_id']} row count")
    columns = unsigned(status["column_count"], f"{status['operator_id']} column count")
    matrix = [[Decimal(0) for _ in range(columns)] for _ in range(rows)]
    seen: set[tuple[int, int]] = set()
    for entry in entries:
        row = unsigned(entry["row_index"], f"{status['operator_id']} row index")
        column = unsigned(entry["column_index"], f"{status['operator_id']} column index")
        require(row < rows and column < columns, f"{status['operator_id']}: entry out of range")
        require((row, column) not in seen, f"{status['operator_id']}: duplicate sparse entry")
        seen.add((row, column))
        value = binary64(entry["value"], f"{status['operator_id']}/{row}/{column} value")
        assert value is not None
        require(value != 0, f"{status['operator_id']}: explicit sparse zero")
        matrix[row][column] = value
    return matrix


def bond_rows_decimal(
    positions: Mapping[int, tuple[Decimal, Decimal, Decimal]],
    packet_ids: Sequence[int],
    relations: Sequence[Mapping[str, str]],
) -> list[list[Decimal]]:
    packet_index = {packet_id: index for index, packet_id in enumerate(packet_ids)}
    rows: list[list[Decimal]] = []
    for relation in relations:
        if relation["relation_kind"] != "bond" or relation["selection_status"] != "retained":
            continue
        first, second = int(relation["first_id"]), int(relation["second_id"])
        offset = vector_subtract(positions[second], positions[first])
        length = decimal_dot(offset, offset).sqrt()
        require(length > 0, "coincident retained bond")
        direction = [value / length for value in offset]
        row = [Decimal(0)] * (3 * len(packet_ids))
        for axis in range(3):
            row[3 * packet_index[first] + axis] = -direction[axis]
            row[3 * packet_index[second] + axis] = direction[axis]
        rows.append(row)
    return rows


def volume_rows_decimal(
    positions: Mapping[int, tuple[Decimal, Decimal, Decimal]],
    packet_ids: Sequence[int],
    relations: Sequence[Mapping[str, str]],
) -> list[list[Decimal]]:
    packet_index = {packet_id: index for index, packet_id in enumerate(packet_ids)}
    rows: list[list[Decimal]] = []
    for relation in relations:
        if relation["relation_kind"] != "oriented_volume" or relation["selection_status"] != "retained":
            continue
        center = int(relation["center_id"])
        first, second, third = (
            int(relation[field]) for field in ("first_id", "second_id", "third_id")
        )
        a = vector_subtract(positions[first], positions[center])
        b = vector_subtract(positions[second], positions[center])
        c = vector_subtract(positions[third], positions[center])
        gradients = {
            first: cross(b, c),
            second: cross(c, a),
            third: cross(a, b),
        }
        gradients[center] = [
            -(gradients[first][axis] + gradients[second][axis] + gradients[third][axis])
            for axis in range(3)
        ]
        row = [Decimal(0)] * (3 * len(packet_ids))
        for packet_id, gradient in gradients.items():
            for axis in range(3):
                row[3 * packet_index[packet_id] + axis] = gradient[axis]
        rows.append(row)
    return rows


def reconstruct_corrected_gradient(
    positions: Mapping[int, tuple[Decimal, Decimal, Decimal]],
    support: Decimal,
) -> tuple[list[list[Decimal]], dict[int, dict[str, Any]]]:
    packet_ids = sorted(positions)
    packet_index = {packet_id: index for index, packet_id in enumerate(packet_ids)}
    count = len(packet_ids)
    result = [[Decimal(0) for _ in range(3 * count)] for _ in range(6 * count)]
    moments: dict[int, dict[str, Any]] = {}
    square_root_two = Decimal(2).sqrt()
    support_squared = support * support
    for center_index, center_id in enumerate(packet_ids):
        center = positions[center_id]
        neighbors: list[tuple[int, list[Decimal], Decimal]] = []
        moment = [[Decimal(0) for _ in range(3)] for _ in range(3)]
        for neighbor_id in packet_ids:
            if neighbor_id == center_id:
                continue
            offset = vector_subtract(positions[neighbor_id], center)
            radius_squared = decimal_dot(offset, offset)
            if not (radius_squared > 0 and radius_squared < support_squared):
                continue
            weight = (Decimal(1) - radius_squared / support_squared) ** 2
            neighbors.append((neighbor_id, offset, weight))
            for row in range(3):
                for column in range(3):
                    moment[row][column] += weight * offset[row] * offset[column]
        rank = decimal_rank(moment, Decimal("1e-80"))
        inverse = decimal_inverse3(moment) if rank == 3 else None
        moments[center_id] = {
            "neighbor_count": len(neighbors),
            "moment": moment,
            "rank": rank,
            "inverse": inverse,
        }
        if inverse is None:
            continue
        # coefficient[velocity component][gradient column][source packet]
        coefficient: dict[int, list[Decimal]] = {}
        summed = [Decimal(0), Decimal(0), Decimal(0)]
        for neighbor_id, offset, weight in neighbors:
            values = [
                weight * dsum(offset[axis] * inverse[axis][column] for axis in range(3))
                for column in range(3)
            ]
            coefficient[neighbor_id] = values
            for column in range(3):
                summed[column] += values[column]
        coefficient[center_id] = [-value for value in summed]
        moments[center_id]["coefficient"] = coefficient
        for source_id, gradient_columns in coefficient.items():
            source = packet_index[source_id]
            # xx, yy, zz
            result[6 * center_index + 0][3 * source + 0] = gradient_columns[0]
            result[6 * center_index + 1][3 * source + 1] = gradient_columns[1]
            result[6 * center_index + 2][3 * source + 2] = gradient_columns[2]
            # sqrt(2)*sym(G) off-diagonals = (G_ab + G_ba)/sqrt(2).
            result[6 * center_index + 3][3 * source + 0] = gradient_columns[1] / square_root_two
            result[6 * center_index + 3][3 * source + 1] = gradient_columns[0] / square_root_two
            result[6 * center_index + 4][3 * source + 0] = gradient_columns[2] / square_root_two
            result[6 * center_index + 4][3 * source + 2] = gradient_columns[0] / square_root_two
            result[6 * center_index + 5][3 * source + 1] = gradient_columns[2] / square_root_two
            result[6 * center_index + 5][3 * source + 2] = gradient_columns[1] / square_root_two
    return result, moments


def compare_matrices(
    actual: Sequence[Sequence[Decimal]],
    expected: Sequence[Sequence[Decimal]],
    where: str,
    *,
    factor: Decimal | None = None,
) -> None:
    require(len(actual) == len(expected), f"{where}: row count mismatch")
    require(all(len(a) == len(e) for a, e in zip(actual, expected, strict=True)),
            f"{where}: column count mismatch")
    dimensions = max(len(expected), len(expected[0]) if expected else 0, 1)
    relative_factor = factor or (Decimal(64) * Decimal(dimensions) * EPS64)
    for row, (actual_row, expected_row) in enumerate(zip(actual, expected, strict=True)):
        row_scale = max((abs(value) for value in expected_row), default=MIN_NORMAL)
        for column, (actual_value, expected_value) in enumerate(
            zip(actual_row, expected_row, strict=True)
        ):
            # Nonzero formula cells can suffer cancellation.  Bound their
            # absolute error by the row's independently rebuilt scale and the
            # registered binary64 operation-count family, never by a unit
            # absolute floor.
            budget = relative_factor * max(row_scale, MIN_NORMAL)
            require(abs(actual_value - expected_value) <= budget,
                    f"{where}: entry ({row},{column}) mismatch")


def quadratic_axis_basis_decimal(
    particle: Decimal, node: Decimal, spacing: Decimal
) -> tuple[Decimal, Decimal]:
    relative = (particle - node) / spacing
    magnitude = abs(relative)
    if magnitude < Decimal("0.5"):
        return Decimal("0.75") - relative * relative, -Decimal(2) * relative / spacing
    if magnitude < Decimal("1.5"):
        distance = Decimal("1.5") - magnitude
        sign = Decimal(1) if relative >= 0 else Decimal(-1)
        return Decimal("0.5") * distance * distance, -distance * sign / spacing
    return Decimal(0), Decimal(0)


def validate_candidate_a_inputs(
    rows: Sequence[dict[str, str]],
    configurations: Mapping[str, Mapping[str, str]],
    positions: Mapping[str, Mapping[int, tuple[Decimal, Decimal, Decimal]]],
    status_by_id: Mapping[str, Mapping[str, str]],
    entries: Sequence[dict[str, str]],
    matrices: Mapping[str, list[list[Decimal]]],
    *,
    injected_zero_fixture_target: str | None = None,
) -> dict[str, dict[str, Any]]:
    by_sampling: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_sampling[row["sampling_operator_id"]].append(row)
    expected_sampling = {
        f"{config_id}.A.{phase}.S"
        for config_id in A_REPRESENTATIVES if config_id in configurations
        for phase in LOOKUP_PHASES
    }
    require(set(by_sampling) == expected_sampling, "Candidate-A grid-control inventory mismatch")
    entries_by_operator: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in entries:
        entries_by_operator[row["operator_id"]].append(row)
    controls: dict[str, dict[str, Any]] = {}
    phase_fraction = {
        "p000": (Decimal(0), Decimal(0), Decimal(0)),
        "p037_011_029": (Decimal("0.37"), Decimal("0.11"), Decimal("0.29")),
    }
    for sampling_id, node_rows in by_sampling.items():
        first = node_rows[0]
        config_id = first["configuration_id"]
        phase = first["lookup_phase"]
        derivative_id = sampling_id[:-1] + "D"
        require(first["derivative_operator_id"] == derivative_id,
                f"{sampling_id}: derivative ID")
        require(sampling_id == f"{config_id}.A.{phase}.S",
                f"{sampling_id}: A ID/configuration/phase binding")
        require(all(row["configuration_id"] == config_id
                    and row["lookup_phase"] == phase
                    and row["derivative_operator_id"] == derivative_id
                    for row in node_rows), f"{sampling_id}: inconsistent grid-node group")
        require(sampling_id in status_by_id and derivative_id in status_by_id,
                f"{sampling_id}: missing S/D status")
        sampling_status, derivative_status = status_by_id[sampling_id], status_by_id[derivative_id]
        expected_status = (
            (sampling_status, "negative_control_sampling", "frozen_quadratic_sampling"),
            (derivative_status, "negative_control_derivative",
             "frozen_quadratic_symmetric_gradient"),
        )
        pair_complete = candidate_a_pair_complete(sampling_id, status_by_id)
        for status, role, observable in expected_status:
            require(status["candidate"] == "A" and status["configuration_id"] == config_id,
                    f"{status['operator_id']}: A status binding")
            require(status["operator_role"] == role and status["observable_kind"] == observable,
                    f"{status['operator_id']}: A status semantics")
            require(status["build_status"] in {"built", "numerical_failure"}
                    and boolean(status["decision_driving"], f"{status['operator_id']} decision")
                    and not boolean(status["promotion_eligible"], f"{status['operator_id']} promotion"),
                    f"{status['operator_id']}: A status gate")
            expected_rank = status is sampling_status and pair_complete
            require(boolean(status["rank_applicable"], f"{status['operator_id']} rank")
                    == expected_rank, f"{status['operator_id']}: A rank applicability")
        h = binary64(configurations[config_id]["nominal_spacing_m"], f"{config_id} A spacing")
        assert h is not None
        origin = tuple(value * h for value in phase_fraction[phase])
        expected_indices: set[tuple[int, int, int]] = set()
        for point in positions[config_id].values():
            base = tuple(int((((point[axis] - origin[axis]) / h) - Decimal("0.5"))
                             .to_integral_value(rounding=ROUND_FLOOR)) for axis in range(3))
            expected_indices.update((base[0] + dx, base[1] + dy, base[2] + dz)
                                    for dx in range(3) for dy in range(3) for dz in range(3))
        ordered_indices = sorted(expected_indices)
        require(len(node_rows) == len(ordered_indices), f"{sampling_id}: active-node count")
        nodes: list[tuple[Decimal, Decimal, Decimal]] = []
        for expected_index, (row, grid_index) in enumerate(zip(
            node_rows, ordered_indices, strict=True
        )):
            require(unsigned(row["node_index"], f"{sampling_id} node index") == expected_index,
                    f"{sampling_id}: noncontiguous node index")
            require(unsigned(row["node_id"], f"{sampling_id} node ID", minimum=1)
                    == expected_index + 1, f"{sampling_id}: scoped node ID")
            actual_grid = tuple(integer(row[field], f"{sampling_id}/{expected_index}/{field}")
                                for field in ("grid_i", "grid_j", "grid_k"))
            require(actual_grid == grid_index, f"{sampling_id}: active-node index mismatch")
            emitted = tuple(binary64(row[field], f"{sampling_id}/{expected_index}/{field}")
                            for field in ("x_m", "y_m", "z_m"))
            assert all(value is not None for value in emitted)
            expected_position = tuple(origin[axis] + Decimal(grid_index[axis]) * h
                                      for axis in range(3))
            for axis in range(3):
                require_forward_close(
                    emitted[axis], expected_position[axis],
                    physical_scale=max(abs(origin[axis]), abs(Decimal(grid_index[axis]) * h)),
                    operation_count=3, safety_factor=8,
                    where=f"{sampling_id}: node coordinate {axis}",
                )
            # The exported coordinate is reporting evidence only.  Every
            # downstream S/D/gauge reconstruction uses the independently
            # derived coordinate so a tolerated reporting perturbation cannot
            # steer the reference operator.
            nodes.append(expected_position)
        packet_ids = sorted(positions[config_id])
        node_count = len(nodes)
        sampling = [[Decimal(0)] * (3 * node_count) for _ in range(3 * len(packet_ids))]
        derivative = [[Decimal(0)] * (3 * node_count) for _ in range(6 * len(packet_ids))]
        index_lookup = {value: index for index, value in enumerate(ordered_indices)}
        gradient_stencils: list[dict[int, tuple[Decimal, Decimal, Decimal]]] = []
        for packet_index, packet_id in enumerate(packet_ids):
            point = positions[config_id][packet_id]
            base = tuple(int((((point[axis] - origin[axis]) / h) - Decimal("0.5"))
                             .to_integral_value(rounding=ROUND_FLOOR)) for axis in range(3))
            packet_gradients: dict[int, tuple[Decimal, Decimal, Decimal]] = {}
            for dx in range(3):
                for dy in range(3):
                    for dz in range(3):
                        grid_index = (base[0] + dx, base[1] + dy, base[2] + dz)
                        node_index = index_lookup[grid_index]
                        node = nodes[node_index]
                        axes = [quadratic_axis_basis_decimal(point[axis], node[axis], h)
                                for axis in range(3)]
                        weight = axes[0][0] * axes[1][0] * axes[2][0]
                        gradient = (
                            axes[0][1] * axes[1][0] * axes[2][0],
                            axes[0][0] * axes[1][1] * axes[2][0],
                            axes[0][0] * axes[1][0] * axes[2][1],
                        )
                        packet_gradients[node_index] = gradient
                        for axis in range(3):
                            sampling[3 * packet_index + axis][3 * node_index + axis] = weight
                        derivative[6 * packet_index + 0][3 * node_index + 0] = gradient[0]
                        derivative[6 * packet_index + 1][3 * node_index + 1] = gradient[1]
                        derivative[6 * packet_index + 2][3 * node_index + 2] = gradient[2]
                        derivative[6 * packet_index + 3][3 * node_index + 0] = gradient[1] / 2
                        derivative[6 * packet_index + 3][3 * node_index + 1] = gradient[0] / 2
                        derivative[6 * packet_index + 4][3 * node_index + 0] = gradient[2] / 2
                        derivative[6 * packet_index + 4][3 * node_index + 2] = gradient[0] / 2
                        derivative[6 * packet_index + 5][3 * node_index + 1] = gradient[2] / 2
                        derivative[6 * packet_index + 5][3 * node_index + 2] = gradient[1] / 2
            gradient_stencils.append(packet_gradients)
        require(int(sampling_status["row_count"]) == 3 * len(packet_ids)
                and int(sampling_status["column_count"]) == 3 * node_count,
                f"{sampling_id}: S dimensions")
        require(int(derivative_status["row_count"]) == 6 * len(packet_ids)
                and int(derivative_status["column_count"]) == 3 * node_count,
                f"{derivative_id}: D dimensions")
        for operator_id, expected in (
            (sampling_id, sampling), (derivative_id, derivative),
        ):
            if boolean(status_by_id[operator_id]["raw_exported"],
                       f"{operator_id}: A raw export"):
                require(operator_id in matrices, f"{operator_id}: missing exported A matrix")
                if operator_id == injected_zero_fixture_target:
                    require(
                        all(value == 0 for row in matrices[operator_id] for value in row),
                        f"{operator_id}: failure-fixture matrix is not exactly zero",
                    )
                else:
                    compare_matrices(matrices[operator_id], expected,
                                     f"{operator_id} rebuilt A operator")
            else:
                require(operator_id not in matrices,
                        f"{operator_id}: unexported A matrix present")
        for operator_id, is_sampling in ((sampling_id, True), (derivative_id, False)):
            block = 3 if is_sampling else 6
            for entry in entries_by_operator[operator_id]:
                row_index = int(entry["row_index"])
                column = int(entry["column_index"])
                packet_index = row_index // block
                node_index = column // 3
                require(entry["domain_kind"] == "grid_node"
                        and int(entry["domain_id"]) == node_index + 1
                        and entry["velocity_component"] == AXES[column % 3],
                        f"{operator_id}: A domain semantic columns")
                require(node_index in gradient_stencils[packet_index],
                        f"{operator_id}: unexpected structural grid-stencil entry")
                require(unsigned(entry["row_owner_id"], f"{operator_id} row owner", minimum=1)
                        == packet_ids[packet_index],
                        f"{operator_id}: A row owner")
                if is_sampling:
                    require(entry["row_kind"] == "packet_velocity_sample"
                            and entry["row_component"] == AXES[row_index % 3]
                            and column % 3 == row_index % 3
                            and entry["units"] == "dimensionless",
                            f"{operator_id}: S row semantics")
                else:
                    allowed_axes = {
                        "xx": {0}, "yy": {1}, "zz": {2},
                        "xy": {0, 1}, "xz": {0, 2}, "yz": {1, 2},
                    }
                    require(entry["row_kind"] == "packet_symmetric_gradient"
                            and entry["row_component"] == A_ROW_COMPONENTS[row_index % 6]
                            and column % 3 in allowed_axes[entry["row_component"]]
                            and entry["units"] == "per_m",
                            f"{operator_id}: D row semantics")
        controls[sampling_id] = {
            "derivative_id": derivative_id,
            "sampling": sampling,
            "derivative": derivative,
            "node_count": node_count,
            "packet_ids": packet_ids,
            "gradient_stencils": gradient_stencils,
            "available": pair_complete,
        }
    return controls


def validate_failure_fixture_contract(
    summary: Mapping[str, Any],
    status_by_id: Mapping[str, Mapping[str, str]],
) -> str | None:
    """Validate the two closed, promotion-ineligible partial-A fixtures.

    The fixture deliberately replaces exactly one p000 pre-normalization A
    matrix by zeros.  Its purpose is to exercise the evidence state machine,
    not to stand in for a physical result.  Every other operator follows the
    ordinary smoke contract.
    """

    if summary["mode"] != "failure_fixture":
        return None
    allowed_targets = {
        "base.filament.r205.original.A.p000.S",
        "base.filament.r205.original.A.p000.D",
    }
    failed_a = {
        operator_id for operator_id, status in status_by_id.items()
        if status["candidate"] == "A" and status["build_status"] != "built"
    }
    require(len(failed_a) == 1 and failed_a <= allowed_targets,
            "failure fixture must contain exactly one registered partial-A failure")
    target = next(iter(failed_a))
    status = status_by_id[target]
    require(
        status["build_status"] == "numerical_failure"
        and status["failure_stage"] == "row_normalization"
        and status["failure_reason"] == "zero_row_norm"
        and status["failure_witness_row"] == "0"
        and status["first_invalid_row"] == "0"
        and status["row_normalization_complete"] == "false"
        and status["raw_exported"] == "true"
        and status["rank_applicable"] == "false",
        f"{target}: failure-fixture status convention",
    )
    sampling_id, derivative_id = candidate_a_pair_ids(target)
    partner_id = derivative_id if target == sampling_id else sampling_id
    partner = status_by_id[partner_id]
    require(
        partner["build_status"] == "built"
        and partner["raw_exported"] == "true"
        and partner["rank_applicable"] == "false",
        f"{target}: failure-fixture partner convention",
    )
    require(all(
        other["build_status"] == "built"
        for operator_id, other in status_by_id.items()
        if other["candidate"] == "A" and operator_id not in {target, partner_id}
    ), "failure fixture contains an additional Candidate-A failure")
    for operator_id, other in status_by_id.items():
        if other["candidate"] == "A":
            continue
        if other["candidate"] == "B":
            expected_build = "singular_local_moment"
        elif other["candidate"] == "C":
            expected_build = "built"
        else:
            expected_build = (
                "built"
                if operator_id == "exact.planar_square_plus_diagonal_and_volume.D"
                else "not_triggered"
            )
        require(other["build_status"] == expected_build,
                f"{operator_id}: failure fixture differs from ordinary smoke status")
    return target


def validate_b_moment_eligibility(
    configurations: Mapping[str, Mapping[str, str]],
    positions: Mapping[str, Mapping[int, tuple[Decimal, Decimal, Decimal]]],
    status_by_id: Mapping[str, Mapping[str, str]],
    moment_rows: Sequence[dict[str, str]],
) -> dict[str, bool]:
    by_operator: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in moment_rows:
        by_operator[row["operator_id"]].append(row)
    expected_operators = {f"{config_id}.B" for config_id in configurations}
    require(set(by_operator) == expected_operators, "B moment diagnostic inventory mismatch")
    eligibility: dict[str, bool] = {}
    tolerance = Decimal(4096) * Decimal(3) * EPS64

    def binary64_moment(
        packet_id: int, packet_positions: Mapping[int, tuple[Decimal, Decimal, Decimal]],
        support_radius: Decimal,
    ) -> list[list[float]]:
        center = tuple(float(value) for value in packet_positions[packet_id])
        radius = float(support_radius)
        result = [[0.0] * 3 for _ in range(3)]
        for candidate_id in sorted(packet_positions):
            if candidate_id == packet_id:
                continue
            candidate = tuple(float(value) for value in packet_positions[candidate_id])
            offset = tuple(candidate[axis] - center[axis] for axis in range(3))
            local_scale = max(abs(offset[0]), abs(offset[1]), abs(offset[2]), radius)
            normalized = tuple(value / local_scale for value in offset)
            normalized_radius = radius / local_scale
            distance_squared = (
                normalized[0] * normalized[0]
                + normalized[1] * normalized[1]
                + normalized[2] * normalized[2]
            )
            radius_squared = normalized_radius * normalized_radius
            if not (distance_squared > 0.0 and distance_squared < radius_squared):
                continue
            squared_ratio = distance_squared / radius_squared
            complement = 1.0 - squared_ratio
            weight = complement * complement
            for matrix_row in range(3):
                for matrix_column in range(3):
                    result[matrix_row][matrix_column] += (
                        weight * offset[matrix_row] * offset[matrix_column]
                    )
        return result

    def binary64_inverse(matrix: Sequence[Sequence[float]]) -> list[list[float]] | None:
        scale = max(abs(value) for row in matrix for value in row)
        if not (scale > 0.0 and math.isfinite(scale)):
            return None
        reciprocal_scale = 1.0 / scale
        a = [[value * reciprocal_scale for value in row] for row in matrix]
        determinant = (
            a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
            - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
            + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
        )
        if not (determinant > 0.0 and math.isfinite(determinant)):
            return None
        cofactors = [
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
        factor = 1.0 / (determinant * scale)
        inverse = [[value * factor for value in row] for row in cofactors]
        return inverse if all(math.isfinite(value) for row in inverse for value in row) else None

    def stable_l2_reference(values: Sequence[float]) -> float:
        scale = 0.0
        scaled_squared = Decimal(0)
        for value in values:
            magnitude = abs(value)
            if magnitude == 0.0:
                continue
            if scale < magnitude:
                ratio = scale / magnitude
                ratio_q = Decimal.from_float(ratio)
                scaled_squared = Decimal(1) + scaled_squared * ratio_q * ratio_q
                scale = magnitude
            else:
                ratio = magnitude / scale
                ratio_q = Decimal.from_float(ratio)
                scaled_squared += ratio_q * ratio_q
        return 0.0 if scale == 0.0 else scale * math.sqrt(float(scaled_squared))

    def binary64_inverse_residual(
        matrix: Sequence[Sequence[float]], inverse: Sequence[Sequence[float]]
    ) -> Decimal:
        residual: list[float] = []
        for matrix_row in range(3):
            for matrix_column in range(3):
                accumulator = dsum(
                    Decimal.from_float(matrix[matrix_row][inner])
                    * Decimal.from_float(inverse[inner][matrix_column])
                    for inner in range(3)
                )
                if matrix_row == matrix_column:
                    accumulator -= Decimal(1)
                residual.append(float(accumulator))
        numerator = stable_l2_reference(residual)
        matrix_norm = stable_l2_reference([value for row in matrix for value in row])
        inverse_norm = stable_l2_reference([value for row in inverse for value in row])
        denominator = max(1.0, matrix_norm * inverse_norm)
        return Decimal.from_float(numerator / denominator)

    for operator_id in sorted(expected_operators):
        config_id = status_by_id[operator_id]["configuration_id"]
        support = binary64(configurations[config_id]["support_radius_m"],
                           f"{config_id} B support")
        assert support is not None
        _operator, reconstructed = reconstruct_corrected_gradient(positions[config_id], support)
        rows = by_operator[operator_id]
        packet_ids = sorted(positions[config_id])
        require([int(row["packet_id"]) for row in rows] == packet_ids,
                f"{operator_id}: moment packet inventory/order")
        independent_statuses: list[str] = []
        for row in rows:
            packet_id = int(row["packet_id"])
            item = reconstructed[packet_id]
            moment = item["moment"]
            require(int(row["neighbor_count"]) == item["neighbor_count"],
                    f"{operator_id}/{packet_id}: independent neighbor count")
            for matrix_row in range(3):
                for matrix_column in range(3):
                    field = f"m{matrix_row}{matrix_column}_m2"
                    emitted = binary64(row[field], f"{operator_id}/{packet_id}/{field}")
                    assert emitted is not None
                    require(close_decimal(emitted, moment[matrix_row][matrix_column],
                                          factor=Decimal("8e-14")),
                            f"{operator_id}/{packet_id}: moment entry mismatch")
            symmetry = decimal_norm(
                moment[row_index][column_index] - moment[column_index][row_index]
                for row_index in range(3) for column_index in range(3)
            ) / max(decimal_matrix_norm(moment), MIN_NORMAL)
            emitted_symmetry = binary64(row["symmetry_residual"],
                                        f"{operator_id}/{packet_id} symmetry")
            assert emitted_symmetry is not None
            require(close_decimal(emitted_symmetry, symmetry, factor=Decimal("2e-13")),
                    f"{operator_id}/{packet_id}: symmetry residual")
            eigenvalues = symmetric_eigenvalues3_decimal(moment)
            smallest, largest = eigenvalues[0], eigenvalues[-1]
            emitted_smallest = binary64(row["smallest_eigenvalue_m2"],
                                        f"{operator_id}/{packet_id} smallest")
            emitted_largest = binary64(row["largest_eigenvalue_m2"],
                                       f"{operator_id}/{packet_id} largest")
            assert emitted_smallest is not None and emitted_largest is not None
            eigen_scale = max(Decimal(1), abs(largest))
            require(abs(emitted_smallest - smallest) <= Decimal("2e-12") * eigen_scale
                    and abs(emitted_largest - largest) <= Decimal("2e-12") * eigen_scale,
                    f"{operator_id}/{packet_id}: independent moment spectrum")
            singular_floor = Decimal(64) * EPS64 * max(largest, MIN_NORMAL)
            if not (largest > 0) or not (smallest > singular_floor):
                expected_status = "singular_local_moment"
                expected_condition: Decimal | None = None
                expected_residual: Decimal | None = None
            else:
                expected_condition = largest / smallest
                if expected_condition > Decimal("1e10"):
                    expected_status = "ill_conditioned_local_moment"
                    expected_residual = None
                else:
                    inverse = decimal_inverse3(moment)
                    residual_matrix = [
                        [dsum(moment[row_index][inner] * inverse[inner][column_index]
                              for inner in range(3)) - (Decimal(1) if row_index == column_index else Decimal(0))
                         for column_index in range(3)]
                        for row_index in range(3)
                    ]
                    expected_residual = decimal_matrix_norm(residual_matrix) / max(
                        Decimal(1), decimal_matrix_norm(moment) * decimal_matrix_norm(inverse)
                    )
                    expected_status = "built" if expected_residual <= tolerance else "numerical_failure"
            independent_statuses.append(expected_status)
            require(row["condition_kind"] == "dense_symmetric_eigen_estimate",
                    f"{operator_id}/{packet_id}: condition kind")
            emitted_condition = binary64(row["condition_number"],
                                         f"{operator_id}/{packet_id} condition", optional=True)
            if expected_condition is None:
                require(emitted_condition is None,
                        f"{operator_id}/{packet_id}: singular condition must be NA")
            else:
                condition_budget = Decimal(8192) * EPS64 * max(
                    Decimal(1), abs(expected_condition)
                )
                require(emitted_condition is not None
                        and abs(emitted_condition - expected_condition) <= condition_budget,
                        f"{operator_id}/{packet_id}: independent condition number")
            emitted_tolerance = binary64(row["inverse_residual_tolerance"],
                                         f"{operator_id}/{packet_id} inverse tolerance")
            assert emitted_tolerance is not None
            require(close_decimal(emitted_tolerance, tolerance, factor=Decimal("3e-15")),
                    f"{operator_id}/{packet_id}: inverse tolerance")
            emitted_residual = binary64(row["inverse_residual_normalized"],
                                        f"{operator_id}/{packet_id} inverse residual", optional=True)
            inverse_emitted = boolean(row["inverse_emitted"],
                                      f"{operator_id}/{packet_id} inverse emitted")
            if expected_status == "built":
                require(emitted_residual is not None and emitted_residual <= tolerance
                        and expected_residual is not None and expected_residual <= tolerance
                        and inverse_emitted,
                        f"{operator_id}/{packet_id}: independent inverse acceptance")
                replay_moment = binary64_moment(packet_id, positions[config_id], support)
                replay_inverse = binary64_inverse(replay_moment)
                require(replay_inverse is not None,
                        f"{operator_id}/{packet_id}: binary64 inverse replay failed")
                replay_residual = binary64_inverse_residual(replay_moment, replay_inverse)
                require(emitted_residual >= 0,
                        f"{operator_id}/{packet_id}: negative inverse residual")
                residual_budget = Decimal(16) * EPS64 * max(
                    Decimal(1), expected_condition or Decimal(1)
                )
                require(abs(emitted_residual - replay_residual) <= residual_budget,
                        f"{operator_id}/{packet_id}: inverse residual replay mismatch")
            else:
                require(emitted_residual is None and not inverse_emitted,
                        f"{operator_id}/{packet_id}: rejected inverse must be absent")
            require(row["status"] == expected_status,
                    f"{operator_id}/{packet_id}: independently derived moment status")
        aggregate = next((value for value in independent_statuses if value != "built"), "built")
        require(status_by_id[operator_id]["build_status"] == aggregate,
                f"{operator_id}: independently derived aggregate B status")
        if aggregate != "built":
            witness_packet = next(
                packet_id for packet_id, item_status in zip(
                    packet_ids, independent_statuses, strict=True
                ) if item_status == aggregate
            )
            require(int(status_by_id[operator_id]["failure_witness_row"])
                    == witness_packet,
                    f"{operator_id}: local-moment witness is not first matching packet")
        eligible = aggregate == "built"
        require(boolean(status_by_id[operator_id]["b_rank_eligible"],
                        f"{operator_id} B eligibility") == eligible,
                f"{operator_id}: independently derived B eligibility")
        eligibility[operator_id] = eligible
    return eligibility


def validate_operator_failure_witness(
    status: Mapping[str, str], packet_ids: Sequence[int]
) -> tuple[str, str]:
    """Validate the closed construction/normalization failure wire.

    This validates representation of an attempted operator separately from
    whether the attempted numerical contract succeeded.  Unsupported failure
    stories remain malformed evidence; supported failures are preserved for a
    later mandatory stop decision.
    """

    operator_id = status["operator_id"]
    candidate = status["candidate"]
    build_status = status["build_status"]
    stage = status["failure_stage"]
    reason = status["failure_reason"]
    row = status["failure_witness_row"]
    column = status["failure_witness_column"]
    value = status["failure_witness_value"]
    bits = status["failure_witness_ieee754_bits"]
    value_class = status["failure_witness_class"]
    witness = (stage, reason, row, column, value, bits, value_class)

    if build_status == "built":
        require(witness == ("NA",) * 7,
                f"{operator_id}: successful operator has failure witness")
        return stage, reason
    if candidate == "D" and build_status == "not_triggered":
        require(
            witness == (
                "not_attempted", "global_d_not_triggered", "NA", "NA",
                "NA", "NA", "none",
            ),
            f"{operator_id}: nontriggered-D witness convention",
        )
        return stage, reason
    if candidate == "B" and build_status in {
        "singular_local_moment", "ill_conditioned_local_moment",
        "numerical_failure",
    }:
        require(
            stage == "local_moment" and reason == build_status
            and row != "NA" and unsigned(
                row, f"{operator_id}: local-moment witness packet", minimum=1
            ) in packet_ids
            and column == "NA" and value == "NA" and bits == "NA"
            and value_class == "moment_diagnostics",
            f"{operator_id}: local-moment failure witness convention",
        )
        return stage, reason
    require(candidate in {"A", "C", "D"} and build_status == "numerical_failure",
            f"{operator_id}: unsupported operator failure status")
    unsigned(row, f"{operator_id}: failure row")
    if stage == "row_normalization":
        require(column == "NA", f"{operator_id}: row-norm witness column")
        if reason == "zero_row_norm":
            require(value == "0x0.0p+0" and bits == "0000000000000000"
                    and value_class == "finite_zero",
                    f"{operator_id}: zero-row witness convention")
        elif reason == "nonfinite_row_norm":
            require(value == "NA", f"{operator_id}: nonfinite norm witness value")
            ieee754_witness(bits, value_class, f"{operator_id}: nonfinite row norm")
        else:
            fail(f"{operator_id}: unsupported row-normalization failure reason")
    elif stage == "operator_construction" and reason == "nonfinite_operator_cell":
        unsigned(column, f"{operator_id}: failure column")
        require(value == "NA", f"{operator_id}: nonfinite cell witness value")
        ieee754_witness(bits, value_class, f"{operator_id}: nonfinite operator cell")
    else:
        fail(f"{operator_id}: unsupported construction failure witness")
    return stage, reason


def candidate_a_pair_ids(operator_id: str) -> tuple[str, str]:
    """Return the sampling/derivative IDs for one frozen Candidate-A pair."""

    require(operator_id.endswith((".S", ".D")),
            f"{operator_id}: Candidate-A operator must end in .S or .D")
    prefix = operator_id[:-1]
    return prefix + "S", prefix + "D"


def candidate_a_pair_complete(
    operator_id: str,
    status_by_id: Mapping[str, Mapping[str, str]],
) -> bool:
    """Whether both causally coupled halves of an A control were built.

    The frozen quadratic sampling operator is meaningful for the negative
    control only together with its derivative operator.  A successful half is
    still retained as raw evidence when its partner fails, but neither half is
    rank-applicable and no rank/null/gauge evidence is permitted for the pair.
    """

    sampling_id, derivative_id = candidate_a_pair_ids(operator_id)
    require(sampling_id in status_by_id and derivative_id in status_by_id,
            f"{operator_id}: incomplete Candidate-A status pair")
    sampling = status_by_id[sampling_id]
    derivative = status_by_id[derivative_id]
    require(sampling["candidate"] == "A" and derivative["candidate"] == "A",
            f"{operator_id}: Candidate-A pair candidate mismatch")
    return (
        sampling["build_status"] == "built"
        and derivative["build_status"] == "built"
    )


def expected_operator_rank_applicable(
    operator_id: str,
    status_by_id: Mapping[str, Mapping[str, str]],
) -> bool:
    """Frozen rank-inventory rule, shared by every validation layer."""

    status = status_by_id[operator_id]
    if status["candidate"] != "A":
        return status["build_status"] == "built"
    return (
        operator_id.endswith(".S")
        and candidate_a_pair_complete(operator_id, status_by_id)
    )


def require_nonfinite_reference_cell(
    status: Mapping[str, str], matrix: Sequence[Sequence[Decimal]], where: str
) -> None:
    """Bind an unencodable construction failure to the rebuilt cell when possible."""

    row = int(status["failure_witness_row"])
    column = int(status["failure_witness_column"])
    require(row < len(matrix) and matrix and column < len(matrix[0]),
            f"{where}: nonfinite witness outside rebuilt matrix")
    try:
        rounded = float(matrix[row][column])
    except OverflowError:
        rounded = math.copysign(math.inf, -1.0 if matrix[row][column] < 0 else 1.0)
    require(not math.isfinite(rounded),
            f"{where}: construction nonfinite was not independently reproduced")
    expected_bits = struct.pack(">d", rounded).hex()
    require(status["failure_witness_ieee754_bits"] == expected_bits,
            f"{where}: nonfinite witness bits differ from rebuilt cell")


def validate_operator_tables(
    configurations: Sequence[dict[str, str]],
    generic_configurations: set[str],
    packet_rows: Mapping[str, list[dict[str, str]]],
    positions: Mapping[str, Mapping[int, tuple[Decimal, Decimal, Decimal]]],
    relation_rows: Sequence[dict[str, str]],
    status_rows: Sequence[dict[str, str]],
    entry_rows: Sequence[dict[str, str]],
    moment_rows: Sequence[dict[str, str]],
    grid_node_rows: Sequence[dict[str, str]],
) -> tuple[
    dict[str, dict[str, str]],
    dict[str, list[list[Decimal]]],
    dict[str, list[dict[str, str]]],
    dict[str, list[list[Decimal]]],
]:
    configurations_by_id = {row["configuration_id"]: row for row in configurations}
    relations_by_configuration: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in relation_rows:
        relations_by_configuration[row["configuration_id"]].append(row)
    status_by_id: dict[str, dict[str, str]] = {}
    entries_by_operator: dict[str, list[dict[str, str]]] = defaultdict(list)
    moments_by_operator: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in entry_rows:
        entries_by_operator[row["operator_id"]].append(row)
    for row in moment_rows:
        moments_by_operator[row["operator_id"]].append(row)
    a_node_counts: dict[str, int] = defaultdict(int)
    for row in grid_node_rows:
        a_node_counts[row["sampling_operator_id"]] += 1
    matrices: dict[str, list[list[Decimal]]] = {}
    reference_matrices: dict[str, list[list[Decimal]]] = {}
    allowed_build_status = {
        "built", "empty", "singular_local_moment", "ill_conditioned_local_moment",
        "numerical_failure", "not_triggered",
    }
    for status in status_rows:
        operator_id = status["operator_id"]
        identifier(operator_id, f"operator {operator_id}")
        require(operator_id not in status_by_id, f"duplicate operator {operator_id}")
        status_by_id[operator_id] = status

    # Validate only after indexing the complete inventory.  Candidate A's
    # rank contract is deliberately pair-level: S may be ranked only when both
    # S and D built, so a one-pass, per-row rule would accept an S-only control.
    for status in status_rows:
        operator_id = status["operator_id"]
        configuration_id = status["configuration_id"]
        require(configuration_id in configurations_by_id, f"{operator_id}: unknown configuration")
        candidate = status["candidate"]
        require(candidate in {"A", "B", "C", "D"}, f"{operator_id}: candidate")
        require(status["build_status"] in allowed_build_status, f"{operator_id}: build status")
        packet_count = unsigned(status["packet_count"], f"{operator_id} packet count")
        require(packet_count == len(packet_rows[configuration_id]), f"{operator_id}: packet count mismatch")
        rows = unsigned(status["row_count"], f"{operator_id} rows")
        columns = unsigned(status["column_count"], f"{operator_id} columns")
        retained_relations = [
            row for row in relations_by_configuration[configuration_id]
            if row["selection_status"] == "retained"
        ]
        build_status = status["build_status"]
        built = build_status == "built"
        failure_stage, _failure_reason = validate_operator_failure_witness(
            status, [int(row["packet_id"]) for row in packet_rows[configuration_id]]
        )
        if candidate == "A":
            sampling_id = operator_id if operator_id.endswith(".S") else operator_id[:-1] + "S"
            node_count = a_node_counts.get(sampling_id, 0)
            expected_rows = (3 if operator_id.endswith(".S") else 6) * packet_count
            expected_columns = 3 * node_count
        elif candidate == "B":
            expected_rows = 6 * packet_count if built else 0
            expected_columns = 3 * packet_count if built else 0
        elif candidate == "C":
            constructed = build_status in {"built", "numerical_failure"}
            expected_rows = len([row for row in retained_relations
                                 if row["relation_kind"] == "bond"]) if constructed else 0
            expected_columns = 3 * packet_count if constructed else 0
        else:
            constructed = build_status in {"built", "numerical_failure"}
            expected_rows = len(retained_relations) if constructed else 0
            expected_columns = 3 * packet_count if constructed else 0
        require((rows, columns) == (expected_rows, expected_columns),
                f"{operator_id}: independently bounded operator dimensions")
        require(rows <= MAX_OPERATOR_DIMENSION and columns <= MAX_OPERATOR_DIMENSION
                and rows * columns <= MAX_DENSE_OPERATOR_CELLS,
                f"{operator_id}: dense operator dimensions exceed validator cap")
        raw_exported = boolean(status["raw_exported"], f"{operator_id} raw_exported")
        normalization_complete = boolean(
            status["row_normalization_complete"], f"{operator_id} normalization"
        )
        expected_raw = built or failure_stage == "row_normalization"
        require(raw_exported == expected_raw,
                f"{operator_id}: raw export/failure-stage convention")
        require(normalization_complete == built,
                f"{operator_id}: normalization-complete/build convention")
        expected_invalid = status["failure_witness_row"] \
            if failure_stage == "row_normalization" else "NA"
        require(status["first_invalid_row"] == expected_invalid,
                f"{operator_id}: first-invalid-row convention")
        if failure_stage == "row_normalization":
            require(int(expected_invalid) < rows,
                    f"{operator_id}: normalization witness row out of range")
        if failure_stage == "operator_construction":
            require(int(status["failure_witness_row"]) < rows
                    and int(status["failure_witness_column"]) < columns,
                    f"{operator_id}: construction witness index out of range")
        promotion = boolean(status["promotion_eligible"], f"{operator_id} promotion")
        require(not promotion, f"{operator_id}: promotion must remain false")
        generic_gate = boolean(status["generic_solid_gate"], f"{operator_id} generic gate")
        expected_generic = candidate != "A" and configuration_id in generic_configurations
        require(generic_gate == expected_generic,
                f"{operator_id}: generic gate differs from candidate/configuration")
        if candidate in {"B", "C", "D"}:
            require(columns in {0, 3 * packet_count}, f"{operator_id}: packet-domain width")
        expected_decision = (
            True if candidate == "A"
            else expected_generic if candidate == "B"
            else candidate == "C"
            or (expected_generic and build_status != "not_triggered")
        )
        require(boolean(status["decision_driving"], f"{operator_id} decision driving")
                == expected_decision,
                f"{operator_id}: attempted/decision-driving convention")
        expected_rank_applicable = expected_operator_rank_applicable(
            operator_id, status_by_id
        )
        require(boolean(status["rank_applicable"], f"{operator_id} rank applicable")
                == expected_rank_applicable,
                f"{operator_id}: rank-applicable/build convention")
        require(boolean(status["b_rank_eligible"], f"{operator_id} B eligibility")
                == (candidate == "B" and built),
                f"{operator_id}: B eligibility convention")
        if raw_exported:
            digest = grouped_payload_digest(
                b"MLS-MECHANICAL-OBSERVABILITY-OPERATOR-v1",
                OPERATOR_ENTRY_FIELDS,
                entries_by_operator[operator_id],
            )
            require(status["operator_payload_sha256"] == digest, f"{operator_id}: operator digest")
            matrix = dense_operator(status, entries_by_operator[operator_id])
            matrices[operator_id] = matrix
            if status["build_status"] == "built":
                require(rows > 0 and columns > 0, f"{operator_id}: built empty operator")
                require(all(any(value != 0 for value in row) for row in matrix),
                        f"{operator_id}: zero operator row")
        else:
            require(not entries_by_operator[operator_id], f"{operator_id}: stray unexported entries")
            require(status["operator_payload_sha256"] == "NA", f"{operator_id}: unexported digest")

        packet_ids = [int(row["packet_id"]) for row in packet_rows[configuration_id]]
        for entry in entries_by_operator[operator_id]:
            require(entry["velocity_component"] in {"x", "y", "z"},
                    f"{operator_id}: velocity component")
            column = int(entry["column_index"])
            if candidate in {"B", "C", "D"}:
                require(entry["domain_kind"] == "packet", f"{operator_id}: domain kind")
                require(int(entry["domain_id"]) == packet_ids[column // 3],
                        f"{operator_id}: domain ID/column mismatch")
                require(entry["velocity_component"] == ("x", "y", "z")[column % 3],
                        f"{operator_id}: component/column mismatch")
                row_index = int(entry["row_index"])
                if candidate == "B":
                    require(entry["row_kind"] == "symmetric_gradient"
                            and unsigned(entry["row_owner_id"],
                                         f"{operator_id} B row owner", minimum=1)
                            == packet_ids[row_index // 6]
                            and entry["row_component"] == A_ROW_COMPONENTS[row_index % 6]
                            and entry["units"] == "per_m",
                            f"{operator_id}: B semantic columns")
                else:
                    retained = [row for row in relations_by_configuration[configuration_id]
                                if row["selection_status"] == "retained"]
                    expected_relation = retained[row_index]
                    is_bond = expected_relation["relation_kind"] == "bond"
                    require(entry["row_owner_id"] == expected_relation["relation_id"],
                            f"{operator_id}: relation row owner")
                    require(entry["row_kind"] == (
                        "bond_length_rate" if is_bond else "oriented_volume_rate"
                    ), f"{operator_id}: relation row kind")
                    require(entry["row_component"] == ("length" if is_bond else "volume")
                            and entry["units"] == ("one" if is_bond else "m2"),
                            f"{operator_id}: relation row component/units")
            else:
                require(entry["domain_kind"] == "grid_node", f"{operator_id}: A domain kind")

        if not raw_exported and failure_stage == "operator_construction":
            relations = relations_by_configuration[configuration_id]
            packet_ids = [int(row["packet_id"]) for row in packet_rows[configuration_id]]
            if candidate == "C":
                failed_reference = bond_rows_decimal(
                    positions[configuration_id], packet_ids, relations
                )
            elif candidate == "D":
                failed_reference = bond_rows_decimal(
                    positions[configuration_id], packet_ids, relations
                )
                failed_reference.extend(volume_rows_decimal(
                    positions[configuration_id], packet_ids, relations
                ))
            else:
                failed_reference = []
            if failed_reference:
                require_nonfinite_reference_cell(
                    status, failed_reference, f"{operator_id}: construction failure"
                )
        if not raw_exported:
            continue
        emitted = matrices[operator_id]
        relations = relations_by_configuration[configuration_id]
        if candidate == "B":
            support = binary64(configurations_by_id[configuration_id]["support_radius_m"],
                               f"{configuration_id} support")
            assert support is not None
            expected, reconstructed_moments = reconstruct_corrected_gradient(
                positions[configuration_id], support
            )
            reference_matrices[operator_id] = expected
            require(all(item["rank"] == 3 for item in reconstructed_moments.values()),
                    f"{operator_id}: exported B has singular reconstructed moment")
            component_axes = {
                "xx": {0}, "yy": {1}, "zz": {2},
                "xy": {0, 1}, "xz": {0, 2}, "yz": {1, 2},
            }
            for entry in entries_by_operator[operator_id]:
                owner = unsigned(entry["row_owner_id"],
                                 f"{operator_id} structural B row owner", minimum=1)
                source = int(entry["domain_id"])
                axis = int(entry["column_index"]) % 3
                require(source in reconstructed_moments[owner]["coefficient"]
                        and axis in component_axes[entry["row_component"]],
                        f"{operator_id}: unexpected structural B entry")
            compare_matrices(emitted, expected, f"{operator_id} corrected-gradient")
            emitted_moments = moments_by_operator[operator_id]
            require(len(emitted_moments) == packet_count, f"{operator_id}: moment row count")
            for row in emitted_moments:
                packet_id = int(row["packet_id"])
                require(packet_id in reconstructed_moments, f"{operator_id}: unknown moment packet")
                reconstructed = reconstructed_moments[packet_id]
                require(int(row["neighbor_count"]) == reconstructed["neighbor_count"],
                        f"{operator_id}/{packet_id}: neighbor count")
                moment = reconstructed["moment"]
                for matrix_row in range(3):
                    for matrix_column in range(3):
                        field = f"m{matrix_row}{matrix_column}_m2"
                        emitted_value = binary64(row[field], f"{operator_id}/{packet_id}/{field}")
                        assert emitted_value is not None
                        require(close_decimal(emitted_value, moment[matrix_row][matrix_column],
                                              factor=Decimal("8e-14")),
                                f"{operator_id}/{packet_id}: moment mismatch")
                require(row["condition_kind"] == "dense_symmetric_eigen_estimate",
                        f"{operator_id}/{packet_id}: condition kind")
                require(row["status"] == "built" and boolean(row["inverse_emitted"],
                                                               f"{operator_id}/{packet_id} inverse"),
                        f"{operator_id}/{packet_id}: accepted moment status")
                symmetry = binary64(row["symmetry_residual"],
                                    f"{operator_id}/{packet_id} symmetry")
                smallest = binary64(row["smallest_eigenvalue_m2"],
                                    f"{operator_id}/{packet_id} smallest eigenvalue")
                largest = binary64(row["largest_eigenvalue_m2"],
                                   f"{operator_id}/{packet_id} largest eigenvalue")
                condition = binary64(row["condition_number"],
                                     f"{operator_id}/{packet_id} condition")
                assert symmetry is not None and smallest is not None
                assert largest is not None and condition is not None
                require(symmetry <= Decimal(4096) * Decimal(3) * EPS64,
                        f"{operator_id}/{packet_id}: moment symmetry gate")
                require(smallest > 0 and largest >= smallest,
                        f"{operator_id}/{packet_id}: moment positive-definiteness")
                require(close_decimal(condition, largest / smallest, factor=Decimal("2e-10")),
                        f"{operator_id}/{packet_id}: condition ratio mismatch")
                require(condition <= Decimal("1e10"),
                        f"{operator_id}/{packet_id}: accepted ill-conditioned moment")
                residual = binary64(row["inverse_residual_normalized"],
                                    f"{operator_id}/{packet_id} inverse residual")
                tolerance = binary64(row["inverse_residual_tolerance"],
                                     f"{operator_id}/{packet_id} inverse tolerance")
                assert residual is not None and tolerance is not None
                require(close_decimal(tolerance, Decimal(4096) * Decimal(3) * EPS64,
                                      factor=Decimal("3e-15")),
                        f"{operator_id}/{packet_id}: inverse tolerance formula")
                require(residual <= tolerance, f"{operator_id}/{packet_id}: inverse residual gate")
        elif candidate == "C":
            expected = bond_rows_decimal(positions[configuration_id], packet_ids, relations)
            reference_matrices[operator_id] = expected
            retained = [row for row in relations if row["selection_status"] == "retained"]
            for entry in entries_by_operator[operator_id]:
                relation = retained[int(entry["row_index"])]
                require(int(entry["domain_id"]) in {
                    int(relation["first_id"]), int(relation["second_id"])
                }, f"{operator_id}: unexpected structural bond entry")
            compare_matrices(emitted, expected, f"{operator_id} central-bond")
        elif candidate == "D":
            expected = bond_rows_decimal(positions[configuration_id], packet_ids, relations)
            expected.extend(volume_rows_decimal(positions[configuration_id], packet_ids, relations))
            reference_matrices[operator_id] = expected
            retained = [row for row in relations if row["selection_status"] == "retained"]
            for entry in entries_by_operator[operator_id]:
                relation = retained[int(entry["row_index"])]
                allowed = {int(relation["first_id"]), int(relation["second_id"])}
                if relation["relation_kind"] == "oriented_volume":
                    allowed.update({int(relation["center_id"]), int(relation["third_id"])})
                require(int(entry["domain_id"]) in allowed,
                        f"{operator_id}: unexpected structural enriched entry")
            compare_matrices(emitted, expected, f"{operator_id} enriched-relation")
        if failure_stage == "row_normalization":
            failure_row = int(status["failure_witness_row"])
            row_values = emitted[failure_row]
            exact_norm = decimal_norm(row_values)
            if status["failure_reason"] == "zero_row_norm":
                require(exact_norm == 0,
                        f"{operator_id}: zero-row witness does not match raw matrix")
            else:
                try:
                    rounded_norm = float(exact_norm)
                except OverflowError:
                    rounded_norm = math.inf
                require(math.isinf(rounded_norm) and rounded_norm > 0,
                        f"{operator_id}: nonfinite-row witness not independently reproduced")
                require(status["failure_witness_ieee754_bits"] == "7ff0000000000000"
                        and status["failure_witness_class"] == "positive_infinity",
                        f"{operator_id}: row-norm overflow witness bits")
    require(set(entries_by_operator) <= set(status_by_id), "entries for unknown operator")
    require(set(moments_by_operator) <= set(status_by_id), "moments for unknown operator")
    return status_by_id, matrices, moments_by_operator, reference_matrices


def q_relation_matrix(
    positions: Mapping[int, tuple[Q, Q, Q]],
    relations: Sequence[Mapping[str, str]],
    *,
    include_volumes: bool,
) -> list[list[Q]]:
    packet_ids = sorted(positions)
    packet_index = {packet_id: index for index, packet_id in enumerate(packet_ids)}
    result: list[list[Q]] = []
    for relation in relations:
        if relation["selection_status"] != "retained":
            continue
        if relation["relation_kind"] == "bond":
            first, second = int(relation["first_id"]), int(relation["second_id"])
            displacement = [positions[second][axis] - positions[first][axis] for axis in range(3)]
            row = [Q(0)] * (3 * len(packet_ids))
            for axis in range(3):
                row[3 * packet_index[first] + axis] = -displacement[axis]
                row[3 * packet_index[second] + axis] = displacement[axis]
            result.append(row)
        elif include_volumes:
            center = int(relation["center_id"])
            first, second, third = (
                int(relation[field]) for field in ("first_id", "second_id", "third_id")
            )
            a = [positions[first][axis] - positions[center][axis] for axis in range(3)]
            b = [positions[second][axis] - positions[center][axis] for axis in range(3)]
            c = [positions[third][axis] - positions[center][axis] for axis in range(3)]
            gradients = {first: q_cross(b, c), second: q_cross(c, a), third: q_cross(a, b)}
            gradients[center] = [
                -(gradients[first][axis] + gradients[second][axis] + gradients[third][axis])
                for axis in range(3)
            ]
            row = [Q(0)] * (3 * len(packet_ids))
            for packet_id, gradient in gradients.items():
                for axis in range(3):
                    row[3 * packet_index[packet_id] + axis] = gradient[axis]
            result.append(row)
    return result


def validate_permutation_controls(
    control_rows: Sequence[dict[str, str]],
    alternate_rows: Sequence[dict[str, str]],
    status_by_id: Mapping[str, Mapping[str, str]],
    packet_rows: Mapping[str, Sequence[Mapping[str, str]]],
    relation_rows: Sequence[Mapping[str, str]],
    baseline_entries: Sequence[Mapping[str, str]],
    matrices: Mapping[str, list[list[Decimal]]],
) -> dict[str, bool]:
    """Rebuild the genuinely order-sensitive v2 permutation artifact."""

    controls = {row["control_id"]: row for row in control_rows}
    require(len(controls) == len(control_rows), "duplicate permutation control ID")
    by_control: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in alternate_rows:
        by_control[row["control_id"]].append(row)
    expected_operators = {
        operator_id for operator_id, status in status_by_id.items()
        if status["candidate"] in {"B", "C", "D"} and status["build_status"] == "built"
    }
    expected_controls = {f"permutation.{operator_id}" for operator_id in expected_operators}
    require(set(controls) == expected_controls,
            "packet-permutation control inventory mismatch")
    require(set(by_control) == expected_controls,
            "packet-permutation raw artifact inventory mismatch")
    baseline_by_cell = {
        (row["operator_id"], int(row["row_index"]), int(row["column_index"])): row
        for row in baseline_entries
    }
    require(len(baseline_by_cell) == len(baseline_entries),
            "duplicate baseline operator cell before permutation comparison")
    relations_by_configuration: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for relation in relation_rows:
        relations_by_configuration[relation["configuration_id"]].append(relation)
    independently_passing: dict[str, bool] = {}
    for control_id in sorted(expected_controls):
        row = controls[control_id]
        operator_id = row["operator_id"]
        require(control_id == f"permutation.{operator_id}",
                f"{control_id}: control/operator binding")
        status = status_by_id[operator_id]
        configuration_id = status["configuration_id"]
        require(row["configuration_id"] == configuration_id,
                f"{control_id}: configuration binding")
        require(row["permutation_kind"] == "sha256_packet_relation_permutation_v2",
                f"{control_id}: permutation kind")
        require(unsigned(row["permutation_seed"], f"{control_id} seed") == SEED,
                f"{control_id}: permutation seed")
        packet_ids = [int(packet["packet_id"]) for packet in packet_rows[configuration_id]]
        expected_order = packet_permutation(configuration_id, packet_ids)
        require(len(expected_order) <= 1 or expected_order != sorted(packet_ids),
                f"{control_id}: packet permutation is identity")
        require(row["packet_order"] == ":".join(str(value) for value in expected_order),
                f"{control_id}: independently derived packet order")
        canonical_packets = sorted(packet_ids)
        canonical_packet_index = {
            packet_id: index for index, packet_id in enumerate(canonical_packets)
        }
        candidate = status["candidate"]
        if candidate == "B":
            canonical_relations: list[str] = []
            expected_relation_order: list[str] = []
            require(row["relation_order"] == "NA",
                    f"{control_id}: B relation order must be NA")
        else:
            configuration_relations = relations_by_configuration[configuration_id]
            canonical_relations = [
                relation["relation_id"] for relation in configuration_relations
                if relation["selection_status"] == "retained"
                and relation["relation_kind"] == "bond"
            ]
            if candidate == "D":
                canonical_relations.extend(
                    relation["relation_id"] for relation in configuration_relations
                    if relation["selection_status"] == "retained"
                    and relation["relation_kind"] == "oriented_volume"
                )
            expected_relation_order = relation_permutation(
                configuration_id, candidate, canonical_relations
            )
            require(len(expected_relation_order) <= 1
                    or expected_relation_order != canonical_relations,
                    f"{control_id}: relation permutation is identity")
            require(row["relation_order"] == ":".join(expected_relation_order),
                    f"{control_id}: independently derived relation order")
        canonical_relation_index = {
            relation_id: index for index, relation_id in enumerate(canonical_relations)
        }
        rows = unsigned(row["row_count"], f"{control_id} rows")
        columns = unsigned(row["column_count"], f"{control_id} columns")
        require(rows == int(status["row_count"]) and columns == int(status["column_count"]),
                f"{control_id}: operator dimensions")
        group = by_control[control_id]
        require(unsigned(row["entry_count"], f"{control_id} entries") == len(group),
                f"{control_id}: entry count")
        require(sha256(row["raw_payload_sha256"], f"{control_id} raw digest")
                == grouped_payload_digest(
                    b"MLS-MECHANICAL-OBSERVABILITY-PERMUTATION-OPERATOR-v2",
                    PERMUTATION_ENTRY_FIELDS,
                    group,
                ), f"{control_id}: independently computed raw digest")
        alternate_raw = [[Decimal(0)] * columns for _ in range(rows)]
        expected_raw = [[Decimal(0)] * columns for _ in range(rows)]
        for raw_row in range(rows):
            if candidate == "B":
                raw_packet = expected_order[raw_row // 6]
                canonical_row = 6 * canonical_packet_index[raw_packet] + raw_row % 6
            else:
                canonical_row = canonical_relation_index[expected_relation_order[raw_row]]
            for raw_column in range(columns):
                raw_packet = expected_order[raw_column // 3]
                canonical_column = (
                    3 * canonical_packet_index[raw_packet] + raw_column % 3
                )
                expected_raw[raw_row][raw_column] = matrices[operator_id][
                    canonical_row
                ][canonical_column]
        seen: set[tuple[int, int]] = set()
        for entry in group:
            require(entry["operator_id"] == operator_id,
                    f"{control_id}: alternate operator binding")
            row_index = int(entry["row_index"])
            column_index = int(entry["column_index"])
            require(0 <= row_index < rows and 0 <= column_index < columns,
                    f"{control_id}: alternate entry bounds")
            key = (row_index, column_index)
            require(key not in seen, f"{control_id}: duplicate alternate entry")
            seen.add(key)
            value = binary64(entry["value"], f"{control_id}/{row_index}/{column_index}")
            assert value is not None
            require(value != 0, f"{control_id}: explicit alternate zero")
            alternate_raw[row_index][column_index] = value
            raw_packet = expected_order[column_index // 3]
            require(entry["domain_kind"] == "packet"
                    and unsigned(entry["domain_id"], f"{control_id}: packet domain", minimum=1)
                    == raw_packet
                    and entry["velocity_component"] == AXES[column_index % 3],
                    f"{control_id}: raw column semantic mapping")
            if candidate == "B":
                owner = expected_order[row_index // 6]
                require(unsigned(entry["row_owner_id"], f"{control_id}: B row owner", minimum=1)
                        == owner,
                        f"{control_id}: raw B row owner")
                canonical_row = 6 * canonical_packet_index[owner] + row_index % 6
            else:
                identifier(entry["row_owner_id"], f"{control_id}: relational row owner")
                relation_id = expected_relation_order[row_index]
                require(entry["row_owner_id"] == relation_id,
                        f"{control_id}: raw relation row owner")
                canonical_row = canonical_relation_index[relation_id]
            canonical_column = 3 * canonical_packet_index[raw_packet] + column_index % 3
            baseline = baseline_by_cell.get((operator_id, canonical_row, canonical_column))
            require(baseline is not None, f"{control_id}: alternate structural-zero entry")
            for field in PERMUTATION_ENTRY_FIELDS:
                if field == "control_id":
                    require(entry[field] == control_id, f"{control_id}: alternate control ID")
                elif field in {"row_index", "column_index", "value"}:
                    continue
                else:
                    require(entry[field] == baseline[field],
                            f"{control_id}: alternate semantic/value field {field}")
        raw_matches_reference = alternate_raw == expected_raw
        raw_dense_hash = hashlib.sha256(
            raw_permuted_operator_payload(alternate_raw)
        ).hexdigest()
        require(sha256(row["raw_dense_payload_sha256"], f"{control_id} raw dense hash")
                == raw_dense_hash,
                f"{control_id}: raw dense payload hash")
        alternate = [[Decimal(0)] * columns for _ in range(rows)]
        for raw_row in range(rows):
            if candidate == "B":
                canonical_row = (
                    6 * canonical_packet_index[expected_order[raw_row // 6]] + raw_row % 6
                )
            else:
                canonical_row = canonical_relation_index[expected_relation_order[raw_row]]
            for raw_column in range(columns):
                canonical_column = (
                    3 * canonical_packet_index[expected_order[raw_column // 3]]
                    + raw_column % 3
                )
                alternate[canonical_row][canonical_column] = alternate_raw[raw_row][raw_column]
        canonical_matches_reference = alternate == matrices[operator_id]
        baseline_hash = hashlib.sha256(canonical_operator_payload(matrices[operator_id])).hexdigest()
        alternate_hash = hashlib.sha256(canonical_operator_payload(alternate)).hexdigest()
        require(sha256(row["baseline_payload_sha256"], f"{control_id} baseline hash")
                == baseline_hash, f"{control_id}: baseline canonical hash")
        require(sha256(row["canonical_payload_sha256"], f"{control_id} alternate hash")
                == alternate_hash, f"{control_id}: alternate canonical hash")
        equal = baseline_hash == alternate_hash and canonical_matches_reference \
            and raw_matches_reference
        require(
            boolean(row["canonical_bytes_match"], f"{control_id} byte equality") == equal,
            f"{control_id}: independently compared canonical bytes",
        )
        require(not boolean(row["promotion_eligible"], f"{control_id} promotion"),
                f"{control_id}: promotion")
        independently_passing[control_id] = equal
    return independently_passing


def validate_exact_references(
    rows: Sequence[dict[str, str]],
    status_by_id: Mapping[str, Mapping[str, str]],
    positions: Mapping[str, Mapping[int, tuple[Q, Q, Q]]],
    relations: Sequence[dict[str, str]],
    *,
    full: bool,
) -> tuple[dict[str, tuple[int, int, int]], bool]:
    relations_by_configuration: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in relations:
        relations_by_configuration[row["configuration_id"]].append(row)
    references = {row["reference_id"]: row for row in rows}
    require(len(references) == len(rows), "duplicate exact reference ID")
    if full:
        require(set(references) == set(EXACT_CLAIMS), "full exact-reference set mismatch")
    else:
        require(set(references) <= set(EXACT_CLAIMS) and references, "smoke exact-reference set")
    verified: dict[str, tuple[int, int, int]] = {}
    all_pass = True
    for reference_id, row in references.items():
        expected_rank, expected_nullity, expected_nonrigid = EXACT_CLAIMS[reference_id]
        expected_configuration, expected_candidate, expected_operator = EXACT_BINDINGS[reference_id]
        configuration_id = row["configuration_id"]
        require(configuration_id == expected_configuration,
                f"{reference_id}: exact configuration binding")
        require(configuration_id in positions, f"{reference_id}: unknown configuration")
        operator_id = row["operator_id"]
        require(operator_id in status_by_id, f"{reference_id}: unknown operator")
        candidate = row["candidate"]
        require(candidate == expected_candidate and operator_id == expected_operator,
                f"{reference_id}: exact candidate/operator binding")
        require(status_by_id[operator_id]["candidate"] == candidate,
                f"{reference_id}: candidate/operator mismatch")
        require(status_by_id[operator_id]["configuration_id"] == configuration_id,
                f"{reference_id}: operator/configuration mismatch")
        include_volumes = candidate == "D"
        matrix = q_relation_matrix(
            positions[configuration_id], relations_by_configuration[configuration_id],
            include_volumes=include_volumes,
        )
        rank = q_rref_rank(matrix)
        column_count = 3 * len(positions[configuration_id])
        nullity = column_count - rank
        rigid_columns = q_rigid_generators(positions[configuration_id])
        rigid_matrix = [
            [column[dof] for column in rigid_columns] for dof in range(column_count)
        ]
        rigid_rank = q_rref_rank(rigid_matrix)
        nonrigid = nullity - rigid_rank
        rigid_in_kernel = all(
            qsum(matrix_row[dof] * column[dof] for dof in range(column_count)) == 0
            for matrix_row in matrix for column in rigid_columns
        )
        augmented_rank = q_rref_rank([
            *matrix,
            *[[column[dof] for dof in range(column_count)] for column in rigid_columns],
        ])
        kernel_equals_rigid = (
            rigid_in_kernel and nullity == rigid_rank and augmented_rank == column_count
        )
        claim_pass = (
            (rank, nullity, nonrigid)
            == (expected_rank, expected_nullity, expected_nonrigid)
            and rigid_in_kernel
            and kernel_equals_rigid == (expected_nonrigid == 0)
        )
        require(row["arithmetic"] == "Fraction_RREF", f"{reference_id}: arithmetic")
        require(unsigned(row["precision_digits"], f"{reference_id} precision") == 0,
                f"{reference_id}: Fraction precision must be zero")
        require(unsigned(row["row_count"], f"{reference_id} rows") == len(matrix),
                f"{reference_id}: row count")
        require(unsigned(row["column_count"], f"{reference_id} columns") == column_count,
                f"{reference_id}: column count")
        require(unsigned(row["rank"], f"{reference_id} rank") == rank,
                f"{reference_id}: emitted rank")
        require(unsigned(row["nullity"], f"{reference_id} nullity") == nullity,
                f"{reference_id}: emitted nullity")
        require(unsigned(row["rigid_rank"], f"{reference_id} rigid rank") == rigid_rank,
                f"{reference_id}: emitted rigid rank")
        require(unsigned(row["nonrigid_nullity"], f"{reference_id} nonrigid") == nonrigid,
                f"{reference_id}: emitted nonrigid")
        require(boolean(row["rigid_in_kernel"], f"{reference_id} rigid kernel")
                == rigid_in_kernel,
                f"{reference_id}: rigid kernel mismatch")
        require(boolean(row["kernel_equals_rigid_span"], f"{reference_id} kernel equality")
                == kernel_equals_rigid, f"{reference_id}: kernel equality mismatch")
        require(row["source"] == "independent_fraction_rref",
                f"{reference_id}: source")
        require(boolean(row["pass"], f"{reference_id} pass") == claim_pass,
                f"{reference_id}: exact pass differs from independent result")
        require(not boolean(row["promotion_eligible"], f"{reference_id} promotion"),
                f"{reference_id}: promotion")
        verified[operator_id] = (rank, nullity, nonrigid)
        all_pass = all_pass and claim_pass
    return verified, all_pass


def expected_rigid_generators_decimal(
    positions: Mapping[int, tuple[Decimal, Decimal, Decimal]],
) -> list[list[Decimal]]:
    packet_ids = sorted(positions)
    centroid = [
        dsum(positions[packet_id][axis] for packet_id in packet_ids) / Decimal(len(packet_ids))
        for axis in range(3)
    ]
    columns: list[list[Decimal]] = []
    axes = (
        (Decimal(1), Decimal(0), Decimal(0)),
        (Decimal(0), Decimal(1), Decimal(0)),
        (Decimal(0), Decimal(0), Decimal(1)),
    )
    for axis in axes:
        columns.append([axis[component] for _packet in packet_ids for component in range(3)])
    for omega in axes:
        column: list[Decimal] = []
        for packet_id in packet_ids:
            relative = [positions[packet_id][axis] - centroid[axis] for axis in range(3)]
            column.extend(cross(omega, relative))
        columns.append(column)
    return columns


def basis_columns(
    rows: Sequence[Mapping[str, str]],
    operator_id: str,
    basis_kind: str,
    column_count: int,
) -> list[list[Decimal]]:
    selected = [
        row for row in rows
        if row["operator_id"] == operator_id and row["basis_kind"] == basis_kind
    ]
    if not selected:
        return []
    mode_ids = sorted({int(row["mode_index"]) for row in selected})
    require(mode_ids == list(range(len(mode_ids))), f"{operator_id}/{basis_kind}: mode indices")
    result: list[list[Decimal]] = []
    for mode in mode_ids:
        mode_rows = [row for row in selected if int(row["mode_index"]) == mode]
        require(len(mode_rows) == column_count, f"{operator_id}/{basis_kind}/{mode}: incomplete mode")
        values = [Decimal(0)] * column_count
        for expected_dof, row in enumerate(mode_rows):
            dof = int(row["dof_index"])
            require(dof == expected_dof, f"{operator_id}/{basis_kind}/{mode}: dof order")
            value = binary64(row["value"], f"{operator_id}/{basis_kind}/{mode}/{dof}")
            assert value is not None
            values[dof] = value
        result.append(values)
    return result


def validate_rank_status_wire(
    operator_id: str,
    status_name: str,
    failure_stage: str,
    ambiguous: bool,
) -> None:
    """Bind rank outcome status to its only legal failure stage."""

    require(status_name in {"analyzed", "ambiguous", "numerical_failure"},
            f"{operator_id}: rank status enum")
    expected_status = (
        "ambiguous" if failure_stage == "rank_estimation"
        else "numerical_failure" if failure_stage == "basis_construction"
        else "analyzed"
    )
    require(status_name == expected_status
            and (status_name == "ambiguous") == ambiguous,
            f"{operator_id}: rank status/failure-stage mismatch")


def validate_rank_and_bases(
    status_by_id: Mapping[str, Mapping[str, str]],
    matrices: Mapping[str, list[list[Decimal]]],
    reference_matrices: Mapping[str, list[list[Decimal]]],
    positions: Mapping[str, Mapping[int, tuple[Decimal, Decimal, Decimal]]],
    rank_rows: Sequence[dict[str, str]],
    rigid_rows: Sequence[dict[str, str]],
    null_rows: Sequence[dict[str, str]],
    metric_rows: Sequence[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    for row in rank_rows:
        operator_id = row["operator_id"]
        require(operator_id in status_by_id, f"rank_status: unknown operator {operator_id}")
        kind = row["record_kind"]
        require(kind in {"summary", "pivot"},
                f"{operator_id}: unknown rank record kind {kind!r}")
        if kind == "summary":
            require(
                row["pivot_step"] == "NA"
                and row["permuted_column_index"] == "NA"
                and row["diagonal_magnitude"] == "NA"
                and row["accepted_pivot"] == "NA",
                f"{operator_id}: rank summary pivot cells must be NA",
            )
        else:
            unsigned(row["pivot_step"], f"{operator_id}: pivot step")
            unsigned(row["permuted_column_index"], f"{operator_id}: pivot column")
            diagonal = binary64(row["diagonal_magnitude"], f"{operator_id}: pivot diagonal")
            require(diagonal is not None and diagonal >= 0,
                    f"{operator_id}: pivot diagonal must be nonnegative binary64")
            boolean(row["accepted_pivot"], f"{operator_id}: accepted pivot")
    for table_name, evidence_rows in (("rigid_basis", rigid_rows), ("nullspace_modes", null_rows)):
        for row in evidence_rows:
            operator_id = row["operator_id"]
            require(operator_id in status_by_id, f"{table_name}: unknown operator {operator_id}")
            status = status_by_id[operator_id]
            dof = unsigned(row["dof_index"], f"{operator_id}/{table_name} dof")
            require(dof < int(status["column_count"]), f"{operator_id}/{table_name}: dof range")
            require(row["velocity_component"] == AXES[dof % 3],
                    f"{operator_id}/{table_name}: component/dof")
            binary64(row["value"], f"{operator_id}/{table_name}/{row['basis_kind']} value")
            if table_name == "rigid_basis":
                require(row["basis_kind"] in {"raw_generator", "orthonormal"},
                        f"{operator_id}: unknown rigid basis kind {row['basis_kind']!r}")
            if status["candidate"] == "A":
                require(table_name == "nullspace_modes"
                        and row["basis_kind"] == "sampling_null"
                        and row["domain_kind"] == "grid_node"
                        and int(row["domain_id"]) == dof // 3 + 1,
                        f"{operator_id}/{table_name}: A basis semantics")
            else:
                packet_ids = sorted(positions[status["configuration_id"]])
                require(row["domain_kind"] == "packet"
                        and int(row["domain_id"]) == packet_ids[dof // 3],
                        f"{operator_id}/{table_name}: packet basis semantics")
    rank_by_operator: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rank_rows:
        rank_by_operator[row["operator_id"]].append(row)
    metric_lookup = {
        (row["operator_id"], row["basis_kind"], int(row["mode_index"])): row
        for row in metric_rows
    }
    require(len(metric_lookup) == len(metric_rows), "duplicate nullspace metric key")
    expected_metric_keys: set[tuple[str, str, int]] = set()
    summaries: dict[str, dict[str, Any]] = {}
    for operator_id, status in status_by_id.items():
        applicable = boolean(status["rank_applicable"], f"{operator_id} rank applicable")
        if not applicable:
            require(operator_id not in rank_by_operator, f"{operator_id}: stray rank rows")
            require(not any(row["operator_id"] == operator_id for row in rigid_rows),
                    f"{operator_id}: stray rigid basis")
            require(not any(row["operator_id"] == operator_id for row in null_rows),
                    f"{operator_id}: stray null basis")
            continue
        require(operator_id in matrices, f"{operator_id}: ranked operator lacks raw matrix")
        require(operator_id in reference_matrices,
                f"{operator_id}: ranked operator lacks independent rebuilt matrix")
        rows = rank_by_operator.get(operator_id, [])
        summary_candidates = [row for row in rows if row["record_kind"] == "summary"]
        require(len(summary_candidates) == 1, f"{operator_id}: requires one rank summary")
        summary = summary_candidates[0]
        pivots = [row for row in rows if row["record_kind"] == "pivot"]
        failure_stage = summary["failure_stage"]
        failure_reason = summary["failure_reason"]
        require(
            (failure_stage == "NA" and failure_reason == "NA")
            or (
                failure_stage == "rank_estimation"
                and failure_reason == "ambiguity_band_overlap"
            )
            or (
                failure_stage == "basis_construction"
                and failure_reason in {
                    "incomplete_kernel", "rigid_span_failure",
                    "nonrigid_quotient_failure", "nonfinite_basis",
                }
            ),
            f"{operator_id}: rank failure stage/reason convention",
        )
        column_count = int(status["column_count"])
        row_count = int(status["row_count"])
        require(len(pivots) == column_count, f"{operator_id}: incomplete pivot trace")
        invariant_fields = [field for field in RANK_STATUS_FIELDS if field not in {
            "record_kind", "pivot_step", "permuted_column_index", "diagonal_magnitude",
            "accepted_pivot",
        }]
        for step, row in enumerate(pivots):
            require(int(row["pivot_step"]) == step, f"{operator_id}: pivot step")
            for field in invariant_fields:
                require(row[field] == summary[field],
                        f"{operator_id}: pivot summary divergence {field}")
        permutation = [int(row["permuted_column_index"]) for row in pivots]
        require(sorted(permutation) == list(range(column_count)),
                f"{operator_id}: invalid column permutation")
        require(int(summary["row_count"]) == row_count
                and int(summary["column_count"]) == column_count,
                f"{operator_id}: rank/operator dimensions")
        rank, nullity = int(summary["rank"]), int(summary["nullity"])
        rigid_rank = int(summary["rigid_rank"])
        nonrigid = None if summary["nonrigid_nullity"] == "NA" \
            else int(summary["nonrigid_nullity"])
        require(rank + nullity == column_count
                and (nonrigid is None or nonrigid >= 0),
                f"{operator_id}: rank/nullity partition")
        require(summary["rank_method"] == "binary64_householder_qrcp_threshold_estimate"
                and not boolean(summary["rank_is_certified"], f"{operator_id} certified"),
                f"{operator_id}: numerical rank label")
        require(not boolean(summary["promotion_eligible"], f"{operator_id} rank promotion"),
                f"{operator_id}: rank promotion")
        diagonals = [binary64(row["diagonal_magnitude"], f"{operator_id}/pivot diagonal")
                     for row in pivots]
        assert all(value is not None for value in diagonals)
        require(all(value >= 0 for value in diagonals), f"{operator_id}: negative QR diagonal")
        matrix = normalized_rows(matrices[operator_id])
        independent_permutation, independent_diagonals = decimal_householder_qrcp_trace(
            matrix, claimed_permutation=permutation, unresolved_floor=Decimal(0)
        )
        require(permutation == independent_permutation,
                f"{operator_id}: independent QRCP pivot replay mismatch")
        require(len(independent_diagonals) == len(diagonals),
                f"{operator_id}: independent QRCP diagonal count")
        independent_first = independent_diagonals[0] if independent_diagonals else MIN_NORMAL
        expected_threshold = (
            Decimal(512) * Decimal(max(row_count, column_count)) * EPS64
            * max(independent_first, MIN_NORMAL)
        )
        expected_lower = expected_threshold / Decimal(8)
        expected_upper = expected_threshold * Decimal(8)
        threshold = binary64(summary["threshold"], f"{operator_id} rank threshold")
        emitted_lower = binary64(summary["ambiguity_lower"], f"{operator_id} ambiguity lower")
        emitted_upper = binary64(summary["ambiguity_upper"], f"{operator_id} ambiguity upper")
        assert threshold is not None and emitted_lower is not None and emitted_upper is not None
        for name, emitted, expected in (
            ("threshold", threshold, expected_threshold),
            ("ambiguity lower", emitted_lower, expected_lower),
            ("ambiguity upper", emitted_upper, expected_upper),
        ):
            require_forward_close(
                emitted, expected, physical_scale=expected, operation_count=6,
                safety_factor=8, where=f"{operator_id}: QR {name} formula",
            )
        accepted = [value > expected_threshold for value in independent_diagonals]
        require([boolean(row["accepted_pivot"], f"{operator_id} accepted pivot") for row in pivots]
                == accepted and sum(accepted) == rank,
                f"{operator_id}: independently derived pivot acceptance/rank")
        trace_ambiguous = any(
            expected_lower <= value <= expected_upper for value in independent_diagonals
        )
        ambiguous = boolean(summary["rank_ambiguous"], f"{operator_id} ambiguous")
        require(ambiguous == trace_ambiguous, f"{operator_id}: independent QR ambiguity trace")
        status_name = summary["status"]
        validate_rank_status_wire(
            operator_id, status_name, failure_stage, ambiguous
        )
        for step, (emitted, independent) in enumerate(zip(
            diagonals, independent_diagonals, strict=True
        )):
            qr_scale = max(abs(emitted), abs(independent), independent_first, MIN_NORMAL)
            qr_error = Decimal(256) * Decimal(max(row_count, column_count)) * EPS64 * qr_scale
            require(abs(emitted - independent) <= qr_error,
                    f"{operator_id}: independent QRCP diagonal {step} mismatch")
        rank_at_lower = decimal_rank_absolute(matrix, expected_lower)
        rank_at_upper = decimal_rank_absolute(matrix, expected_upper)
        independent_ambiguous = rank_at_lower != rank_at_upper
        require(independent_ambiguous == ambiguous,
                f"{operator_id}: independent 120-digit rank interval/ambiguity mismatch")
        if not independent_ambiguous:
            require(rank == rank_at_lower, f"{operator_id}: independent 120-digit rank mismatch")
        reference_matrix = normalized_rows(reference_matrices[operator_id])
        reference_rank_lower = decimal_rank_absolute(reference_matrix, expected_lower)
        reference_rank_upper = decimal_rank_absolute(reference_matrix, expected_upper)
        reference_ambiguous = reference_rank_lower != reference_rank_upper
        reference_rank_agreement = (
            reference_ambiguous == independent_ambiguous
            and reference_rank_lower == rank_at_lower
            and reference_rank_upper == rank_at_upper
        )
        independent_nullity = column_count - rank_at_upper if independent_ambiguous \
            else column_count - rank_at_lower
        tolerance = Decimal(4096) * Decimal(max(row_count, column_count)) * EPS64
        emitted_tolerance = binary64(summary["residual_tolerance"],
                                     f"{operator_id} residual tolerance")
        assert emitted_tolerance is not None
        require(close_decimal(emitted_tolerance, tolerance, factor=Decimal("5e-15")),
                f"{operator_id}: residual tolerance formula")
        matrix_norm = decimal_matrix_norm(matrix)
        reference_matrix_norm = decimal_matrix_norm(reference_matrix)

        if failure_stage in {"rank_estimation", "basis_construction"}:
            independent_basis_agreement = True
            if failure_stage == "basis_construction":
                independently_constructed = decimal_nullspace_basis(
                    matrix, expected_lower
                )
                independently_constructed_q = orthonormalize_columns(
                    independently_constructed, Decimal(16) * tolerance
                )
                independent_basis_succeeded = (
                    len(independently_constructed) == independent_nullity
                    and len(independently_constructed_q) == independent_nullity
                    and orthonormality_residual(independently_constructed_q) <= tolerance
                    and all(
                        decimal_norm(decimal_matvec(matrix, mode))
                        <= tolerance * max(matrix_norm * decimal_norm(mode), MIN_NORMAL)
                        for mode in independently_constructed_q
                    )
                )
                # A well-formed producer failure is evidence even when the
                # independent oracle succeeds.  Preserve that disagreement as
                # an implementation finding; only malformed failure evidence
                # is structurally invalid.
                independent_basis_agreement = not independent_basis_succeeded
            require(nonrigid is None,
                    f"{operator_id}: failed rank/basis nonrigid quotient must be NA")
            require(summary["basis_complete"] == "false",
                    f"{operator_id}: failed basis must be incomplete")
            for field in (
                "rigid_in_kernel", "kernel_equals_rigid_subspace",
                "normalized_rigid_residual", "normalized_null_residual",
                "normalized_nonrigid_residual", "rigid_orthogonality_residual",
                "generic_observability_pass",
            ):
                require(summary[field] == "NA",
                        f"{operator_id}: unevaluated {field} must be NA")
            require(not any(row["operator_id"] == operator_id for row in null_rows),
                    f"{operator_id}: failed basis has nullspace rows")
            require(not any(row["operator_id"] == operator_id for row in metric_rows),
                    f"{operator_id}: failed basis has metric rows")
            if status["candidate"] == "A":
                require(not any(row["operator_id"] == operator_id for row in rigid_rows),
                        f"{operator_id}: failed A rank has rigid rows")
                independent_rigid_rank = 0
            else:
                expected_raw = expected_rigid_generators_decimal(
                    positions[status["configuration_id"]]
                )
                rigid_kinds = {
                    row["basis_kind"] for row in rigid_rows
                    if row["operator_id"] == operator_id
                }
                require(rigid_kinds == {"raw_generator"},
                        f"{operator_id}: failed basis rigid-row convention")
                rigid_raw = basis_columns(
                    rigid_rows, operator_id, "raw_generator", column_count
                )
                require(len(rigid_raw) == 6, f"{operator_id}: failed basis raw generators")
                for index, expected in enumerate(expected_raw):
                    require(decimal_norm(vector_subtract(rigid_raw[index], expected))
                            <= Decimal("3e-12") * max(Decimal(1), decimal_norm(expected)),
                            f"{operator_id}: failed basis rigid generator {index}")
                independent_rigid_rank = column_rank(expected_raw, Decimal("1e-40"))
            require(rigid_rank == independent_rigid_rank,
                    f"{operator_id}: failed basis rigid rank")
            summaries[operator_id] = {
                "status": status_name,
                "rank": rank,
                "nullity": independent_nullity,
                "rigid_rank": independent_rigid_rank,
                "nonrigid_nullity": None,
                "ambiguous": ambiguous,
                "basis_complete": False,
                "kernel_equals_rigid": False,
                "generic_pass": False,
                "contract_pass": False,
                "reference_rank_match": reference_rank_agreement,
                "snapshot_residual": Decimal(0),
                "failure_stage": failure_stage,
                "failure_reason": failure_reason,
                "independent_basis_agreement": independent_basis_agreement,
            }
            continue

        if status["candidate"] == "A":
            independent_rigid_rank = 0
            require(rigid_rank == 0 and nonrigid == nullity,
                    f"{operator_id}: A rigid/nonrigid convention")
            require(not any(row["operator_id"] == operator_id for row in rigid_rows),
                    f"{operator_id}: A has rigid basis")
            complete = basis_columns(null_rows, operator_id, "sampling_null", column_count)
            nonrigid_basis: list[list[Decimal]] = []
            rigid_q: list[list[Decimal]] = []
            basis_kinds = {row["basis_kind"] for row in null_rows if row["operator_id"] == operator_id}
            require(basis_kinds <= {"sampling_null"}, f"{operator_id}: A null basis kind")
            derived_rigid_in_kernel = True
            rigid_contract = True
            derived_kernel_equals = independent_nullity == 0
            derived_nonrigid = independent_nullity
        else:
            expected_raw = expected_rigid_generators_decimal(positions[status["configuration_id"]])
            rigid_kinds = {
                row["basis_kind"] for row in rigid_rows if row["operator_id"] == operator_id
            }
            require(rigid_kinds == {"raw_generator", "orthonormal"},
                    f"{operator_id}: rigid basis inventory")
            rigid_raw = basis_columns(rigid_rows, operator_id, "raw_generator", column_count)
            rigid_q = basis_columns(rigid_rows, operator_id, "orthonormal", column_count)
            require(len(rigid_raw) == 6, f"{operator_id}: six raw rigid generators")
            for index, expected in enumerate(expected_raw):
                require(decimal_norm(vector_subtract(rigid_raw[index], expected))
                        <= Decimal("3e-12") * max(Decimal(1), decimal_norm(expected)),
                        f"{operator_id}: rigid generator {index}")
            independent_rigid_rank = column_rank(expected_raw, Decimal("1e-40"))
            require(rigid_rank == independent_rigid_rank and len(rigid_q) == rigid_rank,
                    f"{operator_id}: independently derived rigid rank/Q width")
            gram_error = orthonormality_residual(rigid_q)
            require(gram_error <= tolerance, f"{operator_id}: rigid Q not orthonormal")
            require(all(subspace_projection_residual(mode, rigid_q) <= tolerance
                        for mode in expected_raw),
                    f"{operator_id}: rigid Q does not span physical generators")
            complete = basis_columns(null_rows, operator_id, "complete_kernel", column_count)
            nonrigid_basis = basis_columns(null_rows, operator_id, "nonrigid", column_count)
            basis_kinds = {row["basis_kind"] for row in null_rows if row["operator_id"] == operator_id}
            require(basis_kinds <= {"complete_kernel", "nonrigid"},
                    f"{operator_id}: packet null basis kind")
            derived_rigid_in_kernel = all(
                decimal_norm(decimal_matvec(matrix, mode))
                <= tolerance * max(matrix_norm * decimal_norm(mode), MIN_NORMAL)
                and decimal_norm(decimal_matvec(reference_matrix, mode))
                <= tolerance * max(reference_matrix_norm * decimal_norm(mode), MIN_NORMAL)
                for mode in rigid_q
            )
            rigid_contained = all(
                subspace_projection_residual(mode, complete) <= tolerance
                for mode in rigid_q
            ) if complete else not rigid_q
            rigid_contract = derived_rigid_in_kernel and rigid_contained
            derived_nonrigid = (
                independent_nullity - independent_rigid_rank
                if rigid_contract else None
            )
            derived_kernel_equals = bool(
                rigid_contract and derived_nonrigid == 0
            )

        complete_q = orthonormalize_columns(complete, Decimal(16) * tolerance)
        basis_complete = len(complete) == independent_nullity and len(complete_q) == independent_nullity
        require(boolean(summary["basis_complete"], f"{operator_id} basis complete") == basis_complete,
                f"{operator_id}: independently derived basis completeness")
        require(basis_complete, f"{operator_id}: incomplete accepted null basis")
        if status["candidate"] != "A":
            derived_kernel_equals = (
                derived_kernel_equals and basis_complete
            )
        require(orthonormality_residual(complete) <= tolerance,
                f"{operator_id}: complete null basis is not unit/orthonormal")
        if status["candidate"] != "A":
            if derived_nonrigid is None:
                require(nonrigid is None and not nonrigid_basis,
                        f"{operator_id}: noncontained rigid span has quotient claim")
            else:
                nonrigid_q = orthonormalize_columns(
                    nonrigid_basis, Decimal(16) * tolerance
                )
                require(len(nonrigid_basis) == derived_nonrigid
                        and len(nonrigid_q) == derived_nonrigid,
                        f"{operator_id}: independent nonrigid basis dimension")
                require(orthonormality_residual(nonrigid_basis) <= tolerance,
                        f"{operator_id}: nonrigid basis is not unit/orthonormal")
                quotient_q = orthonormalize_columns(
                    [*rigid_q, *nonrigid_basis], Decimal(16) * tolerance
                )
                require(len(quotient_q) == independent_nullity
                        and all(subspace_projection_residual(mode, quotient_q)
                                <= tolerance for mode in complete),
                        f"{operator_id}: quotient basis does not span complete kernel")

        def normalized_product(columns: Sequence[Sequence[Decimal]]) -> Decimal:
            if not columns:
                return Decimal(0)
            image = [decimal_matvec(matrix, column) for column in columns]
            numerator = decimal_norm(value for column in image for value in column)
            denominator = decimal_matrix_norm(matrix) * decimal_norm(
                value for column in columns for value in column
            )
            return numerator / max(denominator, MIN_NORMAL)

        aggregate_rigid = normalized_product(rigid_q)
        aggregate_null = normalized_product(complete)
        aggregate_nonrigid: Decimal | None = (
            aggregate_null if status["candidate"] == "A"
            else None if derived_nonrigid is None
            else normalized_product(nonrigid_basis)
        )
        if rigid_q and nonrigid_basis:
            cross_norm = decimal_norm(
                decimal_dot(rigid_mode, nonrigid_mode)
                for rigid_mode in rigid_q for nonrigid_mode in nonrigid_basis
            )
            aggregate_orthogonality = cross_norm / max(
                decimal_norm(value for mode in rigid_q for value in mode)
                * decimal_norm(value for mode in nonrigid_basis for value in mode),
                MIN_NORMAL,
            )
        else:
            aggregate_orthogonality = Decimal(0)
        aggregate_values = {
            "normalized_rigid_residual": aggregate_rigid,
            "normalized_null_residual": aggregate_null,
            "normalized_nonrigid_residual": aggregate_nonrigid,
            "rigid_orthogonality_residual": aggregate_orthogonality,
        }
        aggregate_comparison_budget = Decimal(256) * Decimal(
            max(row_count, column_count)
        ) * EPS64
        for field, expected in aggregate_values.items():
            emitted = binary64(
                summary[field], f"{operator_id} {field}", optional=expected is None
            )
            if expected is None:
                require(emitted is None, f"{operator_id}: {field} must be NA")
            else:
                require(emitted is not None
                        and abs(emitted - expected) <= aggregate_comparison_budget,
                        f"{operator_id}: independently rebuilt {field}")
        require(rigid_rank == independent_rigid_rank and nonrigid == derived_nonrigid,
                f"{operator_id}: producer rigid/nonrigid counts differ from independent quotient")
        require(boolean(summary["rigid_in_kernel"], f"{operator_id} rigid kernel")
                == derived_rigid_in_kernel,
                f"{operator_id}: rigid-in-kernel flag")
        require(boolean(summary["kernel_equals_rigid_subspace"], f"{operator_id} kernel equality")
                == derived_kernel_equals,
                f"{operator_id}: kernel equality flag")
        expected_generic_pass = (
            status["candidate"] != "A"
            and boolean(status["generic_solid_gate"], f"{operator_id} generic")
            and not ambiguous and basis_complete and derived_rigid_in_kernel
            and derived_kernel_equals
        )
        require(boolean(summary["generic_observability_pass"], f"{operator_id} generic pass")
                == expected_generic_pass,
                f"{operator_id}: generic observability flag")

        basis_sets = (("sampling_null", complete),) if status["candidate"] == "A" else (
            ("complete_kernel", complete), ("nonrigid", nonrigid_basis)
        )
        metric_matrix = matrices[operator_id] if status["candidate"] == "A" else matrix
        metric_matrix_norm = decimal_matrix_norm(metric_matrix)
        all_metric_pass = True
        for basis_kind, basis in basis_sets:
            for mode_index, mode in enumerate(basis):
                key = (operator_id, basis_kind, mode_index)
                expected_metric_keys.add(key)
                metric = metric_lookup.get(key)
                require(metric is not None, f"{operator_id}/{basis_kind}/{mode_index}: missing metric")
                image_norm = decimal_norm(decimal_matvec(metric_matrix, mode))
                denominator = max(metric_matrix_norm * decimal_norm(mode), MIN_NORMAL)
                normalized = image_norm / denominator
                projection = decimal_norm(decimal_dot(q_mode, mode) for q_mode in rigid_q) \
                    if rigid_q else Decimal(0)
                orthogonality = projection if basis_kind == "nonrigid" else Decimal(0)
                for field, expected in (
                    ("operator_image_l2", image_norm),
                    ("operator_denominator", denominator),
                    ("normalized_operator_residual", normalized),
                    ("rigid_projection_l2", projection),
                    ("rigid_orthogonality_residual", orthogonality),
                    ("roundoff_bound", tolerance),
                ):
                    emitted = binary64(metric[field], f"{operator_id}/{basis_kind}/{mode_index}/{field}")
                    assert emitted is not None
                    require(abs(emitted - expected) <= aggregate_comparison_budget,
                            f"{operator_id}/{basis_kind}/{mode_index}: {field}")
                expected_pass = normalized <= tolerance and (
                    basis_kind != "nonrigid" or orthogonality <= tolerance
                )
                all_metric_pass = all_metric_pass and expected_pass
                require(boolean(metric["pass"], f"{operator_id}/{basis_kind}/{mode_index} pass")
                        == expected_pass and not boolean(
                            metric["promotion_eligible"], f"{operator_id}/{basis_kind}/{mode_index} promotion"
                        ), f"{operator_id}/{basis_kind}/{mode_index}: metric gate")
        residual_contract_pass = (
            aggregate_rigid <= tolerance
            and aggregate_null <= tolerance
            and aggregate_nonrigid is not None
            and aggregate_nonrigid <= tolerance
            and aggregate_orthogonality <= tolerance
        )
        reference_basis_pass = all(
            decimal_norm(decimal_matvec(reference_matrix, mode))
            <= tolerance * max(reference_matrix_norm * decimal_norm(mode), MIN_NORMAL)
            for mode in [*rigid_q, *complete, *nonrigid_basis]
        )
        summaries[operator_id] = {
            "status": status_name,
            "rank": rank,
            "nullity": independent_nullity,
            "rigid_rank": rigid_rank,
            "nonrigid_nullity": derived_nonrigid,
            "ambiguous": ambiguous,
            "basis_complete": basis_complete,
            "kernel_equals_rigid": derived_kernel_equals,
            "generic_pass": expected_generic_pass,
            "contract_pass": (
                not ambiguous and basis_complete and derived_rigid_in_kernel
                and rigid_contract and reference_rank_agreement
                and reference_basis_pass and residual_contract_pass
                and all_metric_pass
            ),
            "snapshot_residual": max(
                value for value in aggregate_values.values() if value is not None
            ),
            "reference_rank_match": reference_rank_agreement,
            "independent_basis_agreement": True,
        }
    require(set(rank_by_operator) <= set(status_by_id), "rank rows for unknown operator")
    require(set(metric_lookup) == expected_metric_keys, "orphan or missing nullspace metrics")
    require({row["operator_id"] for row in rigid_rows} <= set(status_by_id),
            "rigid basis for unknown operator")
    require({row["operator_id"] for row in null_rows} <= set(status_by_id),
            "null basis for unknown operator")
    return summaries


AFFINE_FIELDS: dict[str, tuple[list[list[Decimal]], list[Decimal]]] = {
    "translation": (
        [[Decimal(0), Decimal(0), Decimal(0)] for _ in range(3)],
        [Decimal(2) / 10, Decimal(-3) / 10, Decimal(5) / 10],
    ),
    "infinitesimal_rotation": (
        [
            [Decimal(0), Decimal(-4) / 10, Decimal(-2) / 10],
            [Decimal(4) / 10, Decimal(0), Decimal(-3) / 10],
            [Decimal(2) / 10, Decimal(3) / 10, Decimal(0)],
        ],
        [Decimal(0), Decimal(0), Decimal(0)],
    ),
    "isotropic_expansion": (
        [
            [Decimal(1) / 5, Decimal(0), Decimal(0)],
            [Decimal(0), Decimal(1) / 5, Decimal(0)],
            [Decimal(0), Decimal(0), Decimal(1) / 5],
        ],
        [Decimal(0), Decimal(0), Decimal(0)],
    ),
    "pure_shear": (
        [
            [Decimal(0), Decimal(3) / 10, Decimal(0)],
            [Decimal(3) / 10, Decimal(0), Decimal(0)],
            [Decimal(0), Decimal(0), Decimal(0)],
        ],
        [Decimal(0), Decimal(0), Decimal(0)],
    ),
    "general_affine": (
        [
            [Decimal(1) / 5, Decimal(-1) / 10, Decimal(3) / 20],
            [Decimal(1) / 4, Decimal(-3) / 20, Decimal(1) / 10],
            [Decimal(-1) / 5, Decimal(1) / 8, Decimal(1) / 20],
        ],
        [Decimal(-1) / 10, Decimal(2) / 10, Decimal(1) / 10],
    ),
}


def affine_velocity(
    matrix: Sequence[Sequence[Decimal]], intercept: Sequence[Decimal], point: Sequence[Decimal]
) -> list[Decimal]:
    return [decimal_dot(row, point) + intercept[index] for index, row in enumerate(matrix)]


def affine_target(
    candidate: str,
    matrix: Sequence[Sequence[Decimal]],
    positions: Mapping[int, tuple[Decimal, Decimal, Decimal]],
    relations: Sequence[Mapping[str, str]],
) -> list[Decimal]:
    packet_ids = sorted(positions)
    square_root_two = Decimal(2).sqrt()
    if candidate == "B":
        local = [
            matrix[0][0], matrix[1][1], matrix[2][2],
            (matrix[0][1] + matrix[1][0]) / square_root_two,
            (matrix[0][2] + matrix[2][0]) / square_root_two,
            (matrix[1][2] + matrix[2][1]) / square_root_two,
        ]
        return local * len(packet_ids)
    bonds = bond_rows_decimal(positions, packet_ids, relations)
    velocities = [
        component
        for packet_id in packet_ids
        for component in affine_velocity(matrix, [Decimal(0)] * 3, positions[packet_id])
    ]
    target = decimal_matvec(bonds, velocities)
    if candidate == "D":
        trace = matrix[0][0] + matrix[1][1] + matrix[2][2]
        for relation in relations:
            if relation["relation_kind"] != "oriented_volume" or relation["selection_status"] != "retained":
                continue
            sites = tuple(
                int(relation[field]) for field in ("center_id", "first_id", "second_id", "third_id")
            )
            target.append(trace * volume6_decimal(positions, sites))
    return target


def transformed_point_envelope(
    point: Sequence[Decimal],
    rotation: Sequence[Sequence[Decimal]],
    translation: Sequence[Decimal],
    scale: Decimal,
) -> list[Decimal]:
    """Registered left-to-right absolute construction envelope for Q/s/t."""

    result: list[Decimal] = []
    for axis in range(3):
        linear = abs(rotation[axis][0] * point[0]) + abs(rotation[axis][1] * point[1])
        linear += abs(rotation[axis][2] * point[2])
        result.append(abs(scale) * linear + abs(translation[axis]))
    return result


def determinant_envelope(
    first: Sequence[Decimal], second: Sequence[Decimal], third: Sequence[Decimal]
) -> Decimal:
    first_term = first[0] * (second[1] * third[2] + second[2] * third[1])
    second_term = first[1] * (second[0] * third[2] + second[2] * third[0])
    third_term = first[2] * (second[0] * third[1] + second[1] * third[0])
    return (first_term + second_term) + third_term


def finite_operand_scale(
    relation: Mapping[str, str],
    positions: Mapping[int, tuple[Decimal, Decimal, Decimal]],
    rotation: Sequence[Sequence[Decimal]],
    translation: Sequence[Decimal],
    scale: Decimal,
    measured: Decimal,
    target: Decimal,
) -> Decimal:
    """Dimensioned cancellation-aware scale frozen for the finite controls."""

    if relation["relation_kind"] == "bond":
        center, site = int(relation["first_id"]), int(relation["second_id"])
        reference = [abs(positions[site][axis]) + abs(positions[center][axis])
                     for axis in range(3)]
        center_envelope = transformed_point_envelope(
            positions[center], rotation, translation, scale
        )
        site_envelope = transformed_point_envelope(
            positions[site], rotation, translation, scale
        )
        transformed = [site_envelope[axis] + center_envelope[axis] for axis in range(3)]
        value = abs(scale) * ((reference[0] + reference[1]) + reference[2])
        value = value + ((transformed[0] + transformed[1]) + transformed[2])
        value = value + abs(measured)
        value = value + abs(target)
        return max(MIN_NORMAL, value)

    center = int(relation["center_id"])
    sites = [int(relation[field]) for field in ("first_id", "second_id", "third_id")]
    center_envelope = transformed_point_envelope(
        positions[center], rotation, translation, scale
    )
    reference_vectors = [
        [abs(positions[site][axis]) + abs(positions[center][axis]) for axis in range(3)]
        for site in sites
    ]
    transformed_vectors: list[list[Decimal]] = []
    for site in sites:
        site_envelope = transformed_point_envelope(
            positions[site], rotation, translation, scale
        )
        transformed_vectors.append([
            site_envelope[axis] + center_envelope[axis] for axis in range(3)
        ])
    scale_cube = (abs(scale) * abs(scale)) * abs(scale)
    value = scale_cube * determinant_envelope(*reference_vectors)
    value = value + determinant_envelope(*transformed_vectors)
    value = value + abs(measured)
    value = value + abs(target)
    return max(MIN_NORMAL, value)


def validate_affine_objectivity(
    rows: Sequence[dict[str, str]],
    status_by_id: Mapping[str, Mapping[str, str]],
    matrices: Mapping[str, list[list[Decimal]]],
    positions: Mapping[str, Mapping[int, tuple[Decimal, Decimal, Decimal]]],
    relations: Sequence[dict[str, str]],
    configurations: Mapping[str, Mapping[str, str]],
) -> dict[str, Decimal]:
    by_operator: dict[str, list[dict[str, str]]] = defaultdict(list)
    relations_by_configuration: dict[str, list[dict[str, str]]] = defaultdict(list)
    allowed_test_kinds = {
        "linear_operator_aggregate", "full_gradient_reproduction",
        "finite_bond_length", "finite_oriented_volume",
    }
    for row in rows:
        by_operator[row["operator_id"]].append(row)
        identifier(row["test_id"], f"{row['operator_id']} affine test ID")
        require(row["test_kind"] in allowed_test_kinds,
                f"{row['operator_id']}/{row['test_id']}: unknown test kind")
        binary64(row["measured_value"], f"{row['operator_id']}/{row['test_id']} measured")
        binary64(row["target_value"], f"{row['operator_id']}/{row['test_id']} target")
        normalized = binary64(
            row["normalized_error"], f"{row['operator_id']}/{row['test_id']} error"
        )
        bound = binary64(
            row["roundoff_bound"], f"{row['operator_id']}/{row['test_id']} bound"
        )
        absolute_error = binary64(
            row["absolute_error"], f"{row['operator_id']}/{row['test_id']} absolute error"
        )
        scale = binary64(
            row["normalization_scale"], f"{row['operator_id']}/{row['test_id']} scale"
        )
        assert normalized is not None and bound is not None
        assert absolute_error is not None and scale is not None
        require(normalized >= 0 and bound >= 0 and absolute_error >= 0 and scale >= 0,
                f"{row['operator_id']}/{row['test_id']}: negative diagnostic")
        if row["test_kind"] in {"finite_bond_length", "finite_oriented_volume"}:
            operations = integer(
                row["operation_count"], f"{row['operator_id']}/{row['test_id']} operations",
                minimum=1,
            )
            require(operations in {72, 134},
                    f"{row['operator_id']}/{row['test_id']}: finite operation count")
            gamma = gamma_n(operations)
            expected_bound = Decimal(256) * gamma * scale + Decimal(256) * MIN_NORMAL
            require_forward_close(
                bound, expected_bound, physical_scale=expected_bound,
                operation_count=4,
                where=f"{row['operator_id']}/{row['test_id']}: finite bound formula",
            )
            expected_normalized = absolute_error / max(scale, MIN_NORMAL)
            normalized_budget = (
                forward_error_budget(scale, operations) / max(scale, MIN_NORMAL)
                + forward_error_budget(
                    abs(expected_normalized), 2, safety_factor=8
                )
            )
            require(abs(normalized - expected_normalized) <= normalized_budget,
                    f"{row['operator_id']}/{row['test_id']}: finite normalization")
            require(not boolean(row["pass"], f"{row['operator_id']}/{row['test_id']} pass")
                    or absolute_error <= bound,
                    f"{row['operator_id']}/{row['test_id']}: finite pass exceeds bound")
        else:
            integer(row["operation_count"], f"{row['operator_id']}/{row['test_id']} operations",
                    minimum=0)
            require(not boolean(row["pass"], f"{row['operator_id']}/{row['test_id']} pass")
                    or normalized <= bound,
                    f"{row['operator_id']}/{row['test_id']}: pass exceeds bound")
    for relation in relations:
        relations_by_configuration[relation["configuration_id"]].append(relation)
    maxima: dict[str, Decimal] = {}
    for operator_id, status in status_by_id.items():
        if (
            status["candidate"] not in {"B", "C", "D"}
            or status["build_status"] != "built"
        ):
            continue
        require(operator_id in matrices, f"{operator_id}: affine decision operator not exported")
        matrix = matrices[operator_id]
        configuration_id = status["configuration_id"]
        packet_positions = positions[configuration_id]
        packet_ids = sorted(packet_positions)
        aggregate_rows = [
            row for row in by_operator[operator_id]
            if row["test_kind"] == "linear_operator_aggregate"
        ]
        retained_relations = [
            row for row in relations_by_configuration[configuration_id]
            if row["selection_status"] == "retained"
        ]
        bond_count = sum(
            row["relation_kind"] == "bond" for row in retained_relations
        )
        if status["candidate"] == "D":
            aggregate_specs = {
                (field, "BOND_ALL"): (
                    f"affine:{field}:bond_aggregate", "m_per_s",
                    tuple(range(bond_count)),
                )
                for field in AFFINE_FIELDS
            }
            if bond_count < len(matrix):
                aggregate_specs.update({
                    (field, "VOLUME_ALL"): (
                        f"affine:{field}:volume_aggregate", "m3_per_s",
                        tuple(range(bond_count, len(matrix))),
                    )
                    for field in AFFINE_FIELDS
                })
        else:
            aggregate_specs = {
                (field, "ALL"): (
                    f"affine:{field}:aggregate",
                    "per_s" if status["candidate"] == "B" else "m_per_s",
                    tuple(range(len(matrix))),
                )
                for field in AFFINE_FIELDS
            }
        aggregate_lookup = {
            (row["field"], row["component"]): row for row in aggregate_rows
        }
        require(len(aggregate_lookup) == len(aggregate_rows)
                and set(aggregate_lookup) == set(aggregate_specs),
                f"{operator_id}: affine aggregate homogeneous-block inventory")
        expected_test_ids = {spec[0] for spec in aggregate_specs.values()}
        for field, (gradient, intercept) in AFFINE_FIELDS.items():
            velocity = [
                component
                for packet_id in packet_ids
                for component in affine_velocity(gradient, intercept, packet_positions[packet_id])
            ]
            measured = decimal_matvec(matrix, velocity)
            target = affine_target(
                status["candidate"], gradient, packet_positions,
                relations_by_configuration[configuration_id],
            )
            require(len(measured) == len(target), f"{operator_id}/{field}: affine target length")
            field_specs = [
                (component, aggregate_specs[(field, component)])
                for candidate_field, component in aggregate_specs
                if candidate_field == field
            ]
            for component, (test_id, expected_units, indices) in field_specs:
                block_matrix = [matrix[index] for index in indices]
                block_measured = [measured[index] for index in indices]
                block_target = [target[index] for index in indices]
                error = decimal_norm(vector_subtract(block_measured, block_target))
                measured_norm = decimal_norm(block_measured)
                target_norm = decimal_norm(block_target)
                denominator = max(
                    decimal_matrix_norm(block_matrix) * decimal_norm(velocity)
                    + target_norm,
                    MIN_NORMAL,
                )
                normalized = error / denominator
                bound = Decimal(4096) * Decimal(max(
                    len(block_matrix), len(block_matrix[0]) if block_matrix else 0
                )) * EPS64
                row = aggregate_lookup[(field, component)]
                require(row["test_id"] == test_id,
                        f"{operator_id}/{field}/{component}: test ID")
                require(row["packet_id"] == "NA" and row["relation_id"] == "NA",
                        f"{operator_id}/{field}/{component}: aggregate optional IDs")
                require(row["units"] == expected_units,
                        f"{operator_id}/{field}/{component}: aggregate units")
                require(integer(
                    row["operation_count"],
                    f"{operator_id}/{field}/{component} operations",
                ) == 0, f"{operator_id}/{field}/{component}: aggregate operation count")
                emitted_values = {
                    "measured_value": measured_norm,
                    "target_value": target_norm,
                    "absolute_error": error,
                    "normalization_scale": denominator,
                    "normalized_error": normalized,
                    "roundoff_bound": bound,
                }
                aggregate_operations = 16 * max(
                    len(block_matrix), len(block_matrix[0]) if block_matrix else 0
                )
                physical_budget = forward_error_budget(
                    denominator, aggregate_operations
                )
                for key, expected in emitted_values.items():
                    actual = binary64(
                        row[key], f"{operator_id}/{field}/{component}/{key}"
                    )
                    assert actual is not None
                    if key == "normalized_error":
                        allowed = physical_budget / max(denominator, MIN_NORMAL)
                    elif key == "roundoff_bound":
                        allowed = forward_error_budget(expected, 4, safety_factor=8)
                    else:
                        allowed = physical_budget
                    require(abs(actual - expected) <= allowed,
                            f"{operator_id}/{field}/{component}: {key} mismatch")
                require(boolean(row["pass"], f"{operator_id}/{field}/{component} pass")
                        == (normalized <= bound),
                        f"{operator_id}/{field}/{component}: affine pass")
                maxima[operator_id] = max(
                    maxima.get(operator_id, Decimal(0)), normalized
                )

        operator_rows = by_operator[operator_id]
        if status["candidate"] == "B":
            support_rows = [row for row in operator_rows
                            if row["test_kind"] == "full_gradient_reproduction"]
            expected_keys = {
                (field, packet_id, f"{tensor_row}{tensor_column}")
                for field in AFFINE_FIELDS for packet_id in packet_ids
                for tensor_row in range(3) for tensor_column in range(3)
            }
            actual_keys = {(row["field"], int(row["packet_id"]), row["component"])
                           for row in support_rows}
            require(actual_keys == expected_keys and len(actual_keys) == len(support_rows),
                    f"{operator_id}: full-gradient affine coverage")
            expected_test_ids.update(
                f"affine:{field}:full_gradient:{packet_id}:{tensor_row}{tensor_column}"
                for field, packet_id, component in expected_keys
                for tensor_row, tensor_column in ((int(component[0]), int(component[1])),)
            )
            config_support = binary64(
                configurations[configuration_id]["support_radius_m"],
                f"{configuration_id}: full-gradient support",
            )
            assert config_support is not None
            _candidate, reconstructed_moments = reconstruct_corrected_gradient(
                packet_positions, config_support
            )
            require(all("coefficient" in item for item in reconstructed_moments.values()),
                    f"{operator_id}: full-gradient coefficient reconstruction unavailable")
            for row in support_rows:
                field = row["field"]
                packet_id = int(row["packet_id"])
                tensor_row, tensor_column = map(int, row["component"])
                gradient, intercept = AFFINE_FIELDS[field]
                velocities = {
                    source_id: affine_velocity(gradient, intercept, packet_positions[source_id])
                    for source_id in packet_ids
                }
                coefficients = reconstructed_moments[packet_id]["coefficient"]
                measured_value = dsum(
                    velocities[source_id][tensor_row] * coefficients[source_id][tensor_column]
                    for source_id in packet_ids if source_id in coefficients
                )
                target_value = gradient[tensor_row][tensor_column]
                absolute = abs(measured_value - target_value)
                scale = max(Decimal(1), abs(measured_value), abs(target_value))
                normalized_value = absolute / scale
                bound = Decimal(4096) * Decimal(max(len(matrix), len(matrix[0]))) * EPS64
                require(row["test_id"] ==
                        f"affine:{field}:full_gradient:{packet_id}:{tensor_row}{tensor_column}"
                        and row["relation_id"] == "NA" and row["units"] == "per_s"
                        and int(row["operation_count"]) == 0,
                        f"{operator_id}: full-gradient row semantics")
                full_gradient_operations = 12 * len(packet_ids)
                physical_budget = forward_error_budget(scale, full_gradient_operations)
                for key, expected in (
                    ("measured_value", measured_value), ("target_value", target_value),
                    ("absolute_error", absolute), ("normalization_scale", scale),
                    ("normalized_error", normalized_value), ("roundoff_bound", bound),
                ):
                    emitted = binary64(row[key], f"{operator_id}/{row['test_id']}/{key}")
                    assert emitted is not None
                    if key == "normalized_error":
                        allowed = physical_budget / max(scale, MIN_NORMAL)
                    elif key == "roundoff_bound":
                        allowed = forward_error_budget(expected, 4, safety_factor=8)
                    else:
                        allowed = physical_budget
                    require(abs(emitted - expected) <= allowed,
                            f"{operator_id}/{row['test_id']}: {key}")
                require(boolean(row["pass"], f"{operator_id}/{row['test_id']} pass")
                        == (normalized_value <= bound),
                        f"{operator_id}/{row['test_id']}: full-gradient pass")
        else:
            require(not any(row["test_kind"] == "full_gradient_reproduction"
                            for row in operator_rows),
                    f"{operator_id}: non-B full-gradient rows")

        if status["candidate"] in {"C", "D"}:
            retained = [row for row in relations_by_configuration[configuration_id]
                        if row["selection_status"] == "retained"
                        and (row["relation_kind"] == "bond" or status["candidate"] == "D")]
            transform_specs = {
                "proper_quaternion_rotation": (ROTATION_Q, (Q(0), Q(0), Q(0)), Q(1)),
                "signed_axis_rotation": (((Q(1), Q(0), Q(0)), (Q(0), Q(-1), Q(0)),
                                           (Q(0), Q(0), Q(-1))), (Q(0), Q(0), Q(0)), Q(1)),
                "translation": (((Q(1), Q(0), Q(0)), (Q(0), Q(1), Q(0)),
                                 (Q(0), Q(0), Q(1))), TRANSLATION_Q, Q(1)),
                "scale_half": (((Q(1), Q(0), Q(0)), (Q(0), Q(1), Q(0)),
                                (Q(0), Q(0), Q(1))), (Q(0), Q(0), Q(0)), Q(1, 2)),
                "scale_double": (((Q(1), Q(0), Q(0)), (Q(0), Q(1), Q(0)),
                                  (Q(0), Q(0), Q(1))), (Q(0), Q(0), Q(0)), Q(2)),
            }
            finite_rows = [row for row in operator_rows
                           if row["test_kind"] in {"finite_bond_length", "finite_oriented_volume"}]
            expected_finite = {(name, relation["relation_id"])
                               for name in transform_specs for relation in retained}
            actual_finite = {(row["field"], row["relation_id"]) for row in finite_rows}
            require(actual_finite == expected_finite and len(actual_finite) == len(finite_rows),
                    f"{operator_id}: finite-objectivity coverage")
            expected_test_ids.update(
                f"finite:{field}:{relation_id}"
                for field, relation_id in expected_finite
            )
            relation_lookup = {row["relation_id"]: row for row in retained}
            for row in finite_rows:
                transform, translation, scale_q = transform_specs[row["field"]]
                scale_d = Decimal(scale_q.numerator) / Decimal(scale_q.denominator)
                translation_d = [Decimal(value.numerator) / Decimal(value.denominator)
                                 for value in translation]
                rotation_d = [[Decimal(value.numerator) / Decimal(value.denominator)
                               for value in transform_row] for transform_row in transform]
                transformed = {
                    packet_id: tuple(scale_d * decimal_dot(rotation_d[axis], point)
                                     + translation_d[axis] for axis in range(3))
                    for packet_id, point in packet_positions.items()
                }
                relation = relation_lookup[row["relation_id"]]
                if relation["relation_kind"] == "bond":
                    first, second = int(relation["first_id"]), int(relation["second_id"])
                    reference = decimal_norm(vector_subtract(packet_positions[second], packet_positions[first]))
                    measured_value = decimal_norm(vector_subtract(transformed[second], transformed[first]))
                    target_value = scale_d * reference
                    kind, component, units, operations = "finite_bond_length", "length", "m", 72
                else:
                    sites = tuple(int(relation[field]) for field in
                                  ("center_id", "first_id", "second_id", "third_id"))
                    reference = volume6_decimal(packet_positions, sites)
                    measured_value = volume6_decimal(transformed, sites)
                    target_value = scale_d ** 3 * reference
                    kind, component, units, operations = "finite_oriented_volume", "volume", "m3", 134
                absolute = abs(measured_value - target_value)
                operand_scale = finite_operand_scale(
                    relation, packet_positions, rotation_d, translation_d, scale_d,
                    measured_value, target_value,
                )
                normalized_value = absolute / operand_scale
                gamma = gamma_n(operations)
                bound = Decimal(256) * gamma * operand_scale + Decimal(256) * MIN_NORMAL
                require(row["test_id"] == f"finite:{row['field']}:{row['relation_id']}"
                        and row["test_kind"] == kind and row["packet_id"] == "NA"
                        and row["component"] == component and row["units"] == units
                        and int(row["operation_count"]) == operations,
                        f"{operator_id}/{row['test_id']}: finite row semantics")
                physical_budget = forward_error_budget(operand_scale, operations)
                for key, expected in (
                    ("measured_value", measured_value), ("target_value", target_value),
                    ("absolute_error", absolute), ("normalization_scale", operand_scale),
                    ("normalized_error", normalized_value), ("roundoff_bound", bound),
                ):
                    emitted = binary64(row[key], f"{operator_id}/{row['test_id']}/{key}")
                    assert emitted is not None
                    if key == "normalized_error":
                        allowed = physical_budget / max(operand_scale, MIN_NORMAL)
                    elif key == "roundoff_bound":
                        allowed = forward_error_budget(expected, 4, safety_factor=8)
                    else:
                        allowed = physical_budget
                    require(abs(emitted - expected) <= allowed,
                            f"{operator_id}/{row['test_id']}: finite {key}")
                require(boolean(row["pass"], f"{operator_id}/{row['test_id']} pass")
                        == (absolute <= bound),
                        f"{operator_id}/{row['test_id']}: finite pass")
        else:
            require(not any(row["test_kind"].startswith("finite_") for row in operator_rows),
                    f"{operator_id}: nonrelational finite rows")
        actual_test_ids = {row["test_id"] for row in operator_rows}
        require(actual_test_ids == expected_test_ids
                and len(actual_test_ids) == len(operator_rows),
                f"{operator_id}: affine/objectivity row inventory")
    expected_operators = {operator_id for operator_id, status in status_by_id.items()
                          if status["candidate"] in {"B", "C", "D"}
                          and status["build_status"] == "built"}
    require(set(by_operator) == expected_operators, "affine/objectivity operator coverage/orphan rows")
    return maxima


def expected_invariance_inventory(
    status_by_id: Mapping[str, Mapping[str, str]],
    configurations: Mapping[str, Mapping[str, str]],
) -> dict[str, tuple[str, str, str, Decimal, str]]:
    """Derive every required comparison from attempted operators, including failures."""

    expected: dict[str, tuple[str, str, str, Decimal, str]] = {}
    packet_operator_ids = {
        operator_id for operator_id, status in status_by_id.items()
        if status["candidate"] in {"B", "C", "D"}
    }
    for operator_id in packet_operator_ids:
        if status_by_id[operator_id]["build_status"] != "built":
            continue
        expected[f"permutation.{operator_id}"] = (
            operator_id, operator_id, "packet_permutation", Decimal(1), "NA"
        )
    for config_id in configurations:
        operator_id = f"{config_id}.C"
        require(operator_id in packet_operator_ids,
                f"{config_id}: lookup-phase C status unavailable")
        expected[f"lookup_phase.{config_id}"] = (
            operator_id, operator_id, "lookup_phase", Decimal(1),
            "p000_to_p037_011_029",
        )
    for config_id, configuration in configurations.items():
        if configuration["variant"] == "original":
            continue
        for candidate in ("B", "C", "D"):
            transformed = f"{config_id}.{candidate}"
            base = f"{configuration['base_configuration_id']}.{candidate}"
            require(transformed in packet_operator_ids and base in packet_operator_ids,
                    f"{config_id}/{candidate}: metamorphic attempted-operator inventory")
            scale = binary64(configuration["geometry_scale"],
                             f"{config_id} invariance scale")
            assert scale is not None
            expected[f"metamorphic.{config_id}.{candidate}"] = (
                base, transformed, configuration["transform"], scale, "NA"
            )
    return expected


def validate_invariance(
    rows: Sequence[dict[str, str]],
    status_by_id: Mapping[str, Mapping[str, str]],
    configurations: Mapping[str, Mapping[str, str]],
    topology: Mapping[str, Mapping[str, Any]],
    ranks: Mapping[str, Mapping[str, Any]],
    matrices: Mapping[str, Sequence[Sequence[Decimal]]],
    permutation_controls: Mapping[str, bool],
) -> None:
    expected = expected_invariance_inventory(status_by_id, configurations)
    require({row["comparison_id"] for row in rows} == set(expected)
            and len(rows) == len(expected), "invariance coverage differs from frozen matrix")
    comparison_ids: set[str] = set()
    spectra: dict[str, tuple[list[Decimal], Decimal]] = {}
    for row in rows:
        comparison_id = row["comparison_id"]
        identifier(comparison_id, "invariance comparison ID")
        require(comparison_id not in comparison_ids, f"duplicate invariance comparison {comparison_id}")
        comparison_ids.add(comparison_id)
        require(row["base_operator_id"] in status_by_id and row["transformed_operator_id"] in status_by_id,
                f"{comparison_id}: unknown operator")
        base_id, transformed_id, kind, expected_scale, lookup_phase = expected[comparison_id]
        require(row["base_operator_id"] == base_id
                and row["transformed_operator_id"] == transformed_id
                and row["transform_kind"] == kind and row["lookup_phase"] == lookup_phase,
                f"{comparison_id}: invariance linkage/provenance")
        require(row["transform_kind"] in {
            "identity", "translation", "rational_quaternion_rotation",
            "rational_quaternion_rotation_translation", "scale_half_rotation",
            "scale_double_rotation", "packet_permutation", "lookup_phase",
        }, f"{comparison_id}: transform kind")
        scale = binary64(row["scale"], f"{comparison_id} scale")
        assert scale is not None
        require(scale > 0 and close_decimal(scale, expected_scale, factor=Decimal("2e-15")),
                f"{comparison_id}: scale")
        base_status, transformed_status = status_by_id[base_id], status_by_id[transformed_id]
        require(row["base_build_status"] == base_status["build_status"]
                and row["transformed_build_status"] == transformed_status["build_status"],
                f"{comparison_id}: build-status linkage")
        status_fields = (
            "build_status", "failure_stage", "failure_reason",
            "failure_witness_row", "failure_witness_column",
            "failure_witness_value", "failure_witness_ieee754_bits",
            "failure_witness_class",
        )
        expected_build_match = all(
            base_status[field] == transformed_status[field] for field in status_fields
        )
        require(boolean(row["build_status_match"], f"{comparison_id} build parity")
                == expected_build_match,
                f"{comparison_id}: build/witness parity")
        if kind in {"packet_permutation", "lookup_phase"}:
            expected_topology_match = True
            expected_relation_match = True
        else:
            transformed_config = transformed_status["configuration_id"]
            expected_topology_match = bool(topology[transformed_config]["base_topology_match"])
            expected_relation_match = bool(
                topology[transformed_config]["base_relation_ids_match"]
            )
        require(boolean(row["topology_match"], f"{comparison_id} topology")
                == expected_topology_match,
                f"{comparison_id}: independently derived topology match")
        require(boolean(row["relation_ids_match"], f"{comparison_id} relation IDs")
                == expected_relation_match,
                f"{comparison_id}: independently derived relation-ID match")

        base_rank = ranks.get(base_id)
        transformed_rank = ranks.get(transformed_id)
        base_resolved = (
            base_rank is not None and base_rank["status"] == "analyzed"
            and not base_rank["ambiguous"] and base_rank["basis_complete"]
        )
        transformed_resolved = (
            transformed_rank is not None and transformed_rank["status"] == "analyzed"
            and not transformed_rank["ambiguous"] and transformed_rank["basis_complete"]
        )
        dimensions_match = (
            int(base_status["row_count"]) == int(transformed_status["row_count"])
            and int(base_status["column_count"]) == int(transformed_status["column_count"])
        )
        ranks_equal = bool(
            base_resolved and transformed_resolved
            and base_rank["rank"] == transformed_rank["rank"]
        )
        nullities_equal = bool(
            base_resolved and transformed_resolved
            and base_rank["nullity"] == transformed_rank["nullity"]
        )
        spectrum_resolved = True
        spectrum_uncertainty = Decimal(0)
        if base_id != transformed_id and ranks_equal and nullities_equal:
            if base_id not in spectra:
                spectra[base_id] = singular_values_reference(
                    normalized_rows(matrices[base_id])
                )
            if transformed_id not in spectra:
                spectra[transformed_id] = singular_values_reference(
                    normalized_rows(matrices[transformed_id])
                )
            first_values, first_error = spectra[base_id]
            second_values, second_error = spectra[transformed_id]
            resolved_rank = base_rank["rank"]
            spectrum_resolved = (
                len(first_values) == len(second_values)
                and 0 <= resolved_rank <= len(first_values)
                and (
                    resolved_rank == 0
                    or (
                        first_values[resolved_rank - 1] > Decimal(64) * first_error
                        and second_values[resolved_rank - 1] > Decimal(64) * second_error
                    )
                )
            )
            if spectrum_resolved and resolved_rank:
                spectrum_uncertainty = max(
                    (
                        (first_error + second_error)
                        / max(first, second, Decimal(1))
                    )
                    for first, second in zip(
                        first_values[:resolved_rank],
                        second_values[:resolved_rank], strict=True,
                    )
                )
        expected_metrics_available = bool(
            base_status["build_status"] == "built"
            and transformed_status["build_status"] == "built"
            and dimensions_match and ranks_equal and nullities_equal
            and spectrum_resolved
        )
        require(boolean(row["rank_match"], f"{comparison_id} rank match") == ranks_equal,
                f"{comparison_id}: independently derived rank match")
        require(boolean(row["nullity_match"], f"{comparison_id} nullity match")
                == nullities_equal,
                f"{comparison_id}: independently derived nullity match")
        require(boolean(row["metrics_available"], f"{comparison_id} metrics available")
                == expected_metrics_available,
                f"{comparison_id}: metric availability")

        residual = binary64(
            row["normalized_residual_delta"], f"{comparison_id} residual delta",
            optional=not expected_metrics_available,
        )
        singular = binary64(
            row["max_scaled_singular_value_delta"],
            f"{comparison_id} singular delta", optional=not expected_metrics_available,
        )
        tolerance = binary64(
            row["tolerance"], f"{comparison_id} tolerance",
            optional=not expected_metrics_available,
        )
        if not expected_metrics_available:
            require(residual is None and singular is None and tolerance is None,
                    f"{comparison_id}: unavailable metrics must be NA")
            canonical = boolean(row["canonical_bytes_match"],
                                f"{comparison_id} canonical bytes")
            require(not canonical, f"{comparison_id}: unavailable canonical-byte claim")
            expected_pass = (
                base_status["build_status"] != "built"
                and transformed_status["build_status"] != "built"
                and expected_build_match and expected_topology_match
                and expected_relation_match
            )
            require(boolean(row["pass"], f"{comparison_id} pass") == expected_pass,
                    f"{comparison_id}: unavailable-status invariance decision")
            continue

        assert residual is not None and singular is not None and tolerance is not None
        expected_tolerance = Decimal(16384) * Decimal(max(
            int(base_status["row_count"]), int(base_status["column_count"]),
            int(transformed_status["row_count"]), int(transformed_status["column_count"]),
        )) * EPS64
        require_forward_close(
            tolerance, expected_tolerance, physical_scale=expected_tolerance,
            operation_count=4, safety_factor=8,
            where=f"{comparison_id}: invariance tolerance formula",
        )
        expected_residual = abs(
            base_rank["snapshot_residual"]
            - transformed_rank["snapshot_residual"]
        )
        metric_budget = Decimal(256) * Decimal(max(
            int(base_status["row_count"]), int(base_status["column_count"]),
            int(transformed_status["row_count"]), int(transformed_status["column_count"]),
        )) * EPS64
        require(abs(residual - expected_residual) <= metric_budget,
                f"{comparison_id}: independently rebuilt residual delta")
        if base_id == transformed_id:
            expected_singular = Decimal(0)
        else:
            first_values, _first_error = spectra[base_id]
            second_values, _second_error = spectra[transformed_id]
            require(len(first_values) == len(second_values),
                    f"{comparison_id}: independent singular-spectrum dimension")
            resolved_rank = base_rank["rank"]
            require(0 <= resolved_rank <= len(first_values),
                    f"{comparison_id}: resolved singular rank out of range")
            expected_singular = max((
                abs(first - second) / max(first, second, Decimal(1))
                for first, second in zip(
                    first_values[:resolved_rank], second_values[:resolved_rank], strict=True
                )
            ), default=Decimal(0))
        reporting_budget = Decimal(2048) * Decimal(max(
            int(base_status["row_count"]), int(base_status["column_count"]),
            int(transformed_status["row_count"]), int(transformed_status["column_count"]),
        )) * EPS64
        spectrum_budget = reporting_budget + spectrum_uncertainty
        require(abs(singular - expected_singular) <= spectrum_budget,
                f"{comparison_id}: independently rebuilt scaled singular-value delta")
        canonical = boolean(row["canonical_bytes_match"], f"{comparison_id} canonical bytes")
        if row["transform_kind"] == "packet_permutation":
            require(comparison_id in permutation_controls,
                    f"{comparison_id}: missing independently parsed permutation artifact")
            require(canonical == permutation_controls[comparison_id],
                    f"{comparison_id}: permutation equality differs from raw artifact")
            canonical_condition = permutation_controls[comparison_id] \
                and expected_residual == 0 and expected_singular == 0
        else:
            require(not canonical, f"{comparison_id}: non-permutation canonical-bytes claim")
            canonical_condition = True
        independently_passes = (
            expected_topology_match and expected_relation_match
            and expected_build_match and ranks_equal and nullities_equal
            and
            expected_residual + metric_budget <= expected_tolerance
            and expected_singular + spectrum_budget <= expected_tolerance
            and canonical_condition
        )
        require(boolean(row["pass"], f"{comparison_id} pass") == independently_passes,
                f"{comparison_id}: pass differs from independent invariance decision")


def derive_invariance_aggregate(
    rows: Sequence[Mapping[str, str]],
    status_by_id: Mapping[str, Mapping[str, str]],
) -> bool:
    """Reduce validated comparison rows without hiding mandatory unavailability."""

    return bool(rows) and all(
        boolean(row["pass"], f"{row['comparison_id']} pass")
        and (
            boolean(row["metrics_available"], f"{row['comparison_id']} metrics")
            or not any(
                boolean(status_by_id[operator_id]["decision_driving"],
                        f"{operator_id} decision driving")
                for operator_id in {
                    row["base_operator_id"], row["transformed_operator_id"]
                }
            )
        )
        for row in rows
    )


def validate_grid_gauge(
    rows: Sequence[dict[str, str]],
    status_by_id: Mapping[str, Mapping[str, str]],
    controls: Mapping[str, Mapping[str, Any]],
    null_rows: Sequence[dict[str, str]],
    ranks: Mapping[str, Mapping[str, Any]],
) -> bool:
    by_operator: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_operator[row["operator_id"]].append(row)
    expected_controls = {
        sampling_id for sampling_id, control in controls.items()
        if control["available"] and candidate_a_rank_supports_gauge(
            ranks.get(sampling_id)
        )
    }
    require(set(by_operator) == expected_controls,
            "grid-gauge/A-control inventory mismatch")
    control_results: list[bool] = []
    for sampling_id, control in controls.items():
        derivative_id = control["derivative_id"]
        if not control["available"]:
            require(sampling_id not in ranks,
                    f"{sampling_id}: failed A control unexpectedly ranked")
            control_results.append(False)
            continue
        if not candidate_a_rank_supports_gauge(ranks.get(sampling_id)):
            require(sampling_id in ranks,
                    f"{sampling_id}: built A control lacks rank outcome")
            control_results.append(False)
            continue
        column_count = len(control["sampling"][0])
        modes = basis_columns(null_rows, sampling_id, "sampling_null", column_count)
        gauge_rows = by_operator[sampling_id]
        require(len(gauge_rows) == len(modes), f"{sampling_id}: gauge row/mode count")
        sampling_matrix = control["sampling"]
        derivative_matrix = control["derivative"]
        sampling_norm = decimal_matrix_norm(sampling_matrix)
        rank_tolerance = Decimal(4096) * Decimal(max(
            len(sampling_matrix), len(sampling_matrix[0])
        )) * EPS64
        kernel_q = orthonormalize_columns(modes, Decimal(16) * rank_tolerance)
        require(len(kernel_q) == ranks[sampling_id]["nullity"],
                f"{sampling_id}: independent gauge kernel basis dimension")
        restricted_sampling = [
            [decimal_dot(matrix_row, mode) for mode in kernel_q]
            for matrix_row in sampling_matrix
        ]
        restricted_sampling_residual = decimal_matrix_norm(restricted_sampling) / max(
            sampling_norm, MIN_NORMAL
        )
        derivative_restriction_norm = restricted_operator_norm(
            derivative_matrix, kernel_q
        )
        operations = 2 * len(derivative_matrix[0])
        gamma = Decimal(operations) * EPS64 / (
            Decimal(1) - Decimal(operations) * EPS64
        )
        invariant_roundoff_bound = (
            Decimal(128) * gamma * decimal_matrix_norm(derivative_matrix)
        )
        invariant_accepted = restricted_sampling_residual <= rank_tolerance
        invariant_visible = derivative_restriction_norm > max(
            Decimal("1e-10"), Decimal("1e4") * invariant_roundoff_bound
        )
        every_mode_passed = True
        for mode_index, (row, mode) in enumerate(zip(gauge_rows, modes, strict=True)):
            require(row["sampling_operator_id"] == sampling_id
                    and row["derivative_operator_id"] == derivative_id
                    and int(row["mode_index"]) == mode_index,
                    f"{sampling_id}/{mode_index}: gauge linkage")
            component = AXES[mode_index % 3]
            require(row["representative_component"] == component,
                    f"{sampling_id}/{mode_index}: representative component")
            axis = mode_index % 3
            require(all(mode[dof] == 0 for dof in range(len(mode)) if dof % 3 != axis),
                    f"{sampling_id}/{mode_index}: mode is not a scalar component lift")
            scalar_mode = [mode[3 * node + axis] for node in range(control["node_count"])]
            sample_image = decimal_matvec(sampling_matrix, mode)
            sample_denominator = max(sampling_norm * decimal_norm(mode), MIN_NORMAL)
            sampling_residual = decimal_norm(sample_image) / sample_denominator
            derivative_image = decimal_matvec(derivative_matrix, mode)
            derivative_max = max((abs(value) for value in derivative_image), default=Decimal(0))
            derivative_rms = decimal_norm(derivative_image) / Decimal(len(derivative_image)).sqrt()
            roundoff = MIN_NORMAL
            for stencil in control["gradient_stencils"]:
                absolute_sum = dsum(
                    abs(scalar_mode[node]) * decimal_norm(gradient)
                    for node, gradient in stencil.items()
                )
                operations = 3 * len(stencil)
                gamma = Decimal(operations) * EPS64 / (Decimal(1) - Decimal(operations) * EPS64)
                roundoff = max(roundoff, Decimal(128) * gamma * absolute_sum)
            ratio = derivative_max / roundoff
            expected = {
                "sampling_residual_normalized": sampling_residual,
                "derivative_max_per_s": derivative_max,
                "derivative_rms_per_s": derivative_rms,
                "derivative_roundoff_bound_per_s": roundoff,
                "visibility_ratio": ratio,
            }
            for field, value in expected.items():
                emitted = binary64(row[field], f"{sampling_id}/{mode_index}/{field}")
                assert emitted is not None
                comparison_budget = (
                    Decimal(64)
                    * Decimal(max(len(sampling_matrix), len(sampling_matrix[0]),
                                  len(derivative_matrix)))
                    * EPS64
                    * max(Decimal(1), abs(value))
                )
                require(abs(emitted - value) <= comparison_budget,
                        f"{sampling_id}/{mode_index}: independently rebuilt {field}")
            visible = derivative_max > max(Decimal("1e-10"), Decimal("1e4") * roundoff)
            accepted = sampling_residual <= rank_tolerance
            passed = accepted and visible
            every_mode_passed = every_mode_passed and passed
            require(boolean(row["gradient_visible"], f"{sampling_id}/{mode_index} visible") == visible
                    and boolean(row["accepted"], f"{sampling_id}/{mode_index} accepted") == accepted
                    and boolean(row["pass"], f"{sampling_id}/{mode_index} pass") == passed,
                    f"{sampling_id}/{mode_index}: independently derived gauge classification")
            require(not boolean(row["promotion_eligible"], f"{sampling_id}/{mode_index} promotion"),
                    f"{sampling_id}/{mode_index}: promotion")
        control_results.append(
            invariant_accepted and invariant_visible and every_mode_passed
        )
    return bool(control_results) and all(control_results)


def validate_configuration_rows(rows: Sequence[dict[str, str]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    allowed_transforms = {
        "identity", "translation", "rational_quaternion_rotation",
        "rational_quaternion_rotation_translation", "scale_half_rotation",
        "scale_double_rotation",
    }
    for row in rows:
        configuration_id = row["configuration_id"]
        identifier(configuration_id, "configuration ID")
        require(configuration_id not in result, f"duplicate configuration {configuration_id}")
        result[configuration_id] = row
        identifier(row["base_configuration_id"], f"{configuration_id} base ID")
        for field in ("family", "variant", "profile", "lookup_phase"):
            identifier(row[field], f"{configuration_id} {field}")
        require(row["transform"] in allowed_transforms, f"{configuration_id}: transform")
        for field in ("nominal_spacing_m", "support_radius_m", "geometry_scale"):
            value = binary64(row[field], f"{configuration_id} {field}")
            assert value is not None
            require(value > 0, f"{configuration_id}: {field} must be positive")
        for field in (
            "packet_payload_sha256", "neighbor_payload_sha256", "relation_payload_sha256",
            "input_checkpoint_sha256_before", "input_checkpoint_sha256_after",
        ):
            sha256(row[field], f"{configuration_id} {field}")
        boolean(row["diagnostics_read_only_exact"], f"{configuration_id} read-only")
        for field in ("generic_solid_gate", "intentionally_flexible", "decision_driving"):
            boolean(row[field], f"{configuration_id} {field}")
        expected_flexible = frozen_intentionally_flexible(configuration_id, row["family"])
        require(boolean(row["intentionally_flexible"], f"{configuration_id} flexible")
                == expected_flexible,
                f"{configuration_id}: intentionally-flexible flag differs from frozen family")
        require(boolean(row["decision_driving"], f"{configuration_id} decision"),
                f"{configuration_id}: registered configuration cannot hide decision rows")
    return result


def validate_full_configuration_matrix(rows: Mapping[str, Mapping[str, str]]) -> None:
    base_specs: dict[str, tuple[str, str, int]] = {}

    def register_profiles(family: str, profiles: Sequence[str], packet_count: int) -> None:
        for profile in profiles:
            configuration_id = f"base.{family}.{profile}.original"
            base_specs[configuration_id] = (family, profile, packet_count)

    register_profiles("sc3", ("r105", "r150", "r180"), 27)
    register_profiles("bcc35", ("r105", "r150", "r180"), 35)
    register_profiles("jitter27", ("r105", "r150", "r180"), 27)
    register_profiles("free_face", ("r150", "r180"), 48)
    register_profiles("edge_truncated", ("r150", "r180"), 36)
    register_profiles("corner_truncated", ("r150", "r180"), 27)
    register_profiles("sheet", ("r105", "r150"), 25)
    register_profiles("filament", ("r105", "r205"), 8)
    register_profiles("sc3_deletion", ("delete10", "delete25", "delete40"), 27)
    exact_specs = {
        "exact.noncoplanar_underconnected": ("noncoplanar_underconnected", "k4_minus_edge", 4),
        "exact.tetrahedron_k4": ("tetrahedron_k4", "exact", 4),
        "exact.tetrahedron_k4_minus_edge": ("tetrahedron_k4_minus_edge", "exact", 4),
        "exact.octahedron_graph": ("octahedron_graph", "exact", 6),
        "exact.cube_edge_graph": ("cube_edge_graph", "exact", 8),
        "exact.planar_square_plus_diagonal": ("planar_square_plus_diagonal", "exact", 4),
        "exact.planar_square_plus_diagonal_and_volume": (
            "planar_square_plus_diagonal_and_volume", "exact", 4,
        ),
    }
    base_specs.update(exact_specs)
    metamorphic_bases = (
        "base.sc3.r180.original",
        "base.bcc35.r180.original",
        "base.jitter27.r180.original",
        "base.corner_truncated.r180.original",
        "base.sheet.r150.original",
        "base.filament.r205.original",
    )
    variants = {
        "translation": ("translation", Decimal(1)),
        "rotation": ("rational_quaternion_rotation", Decimal(1)),
        "rotation_translation": ("rational_quaternion_rotation_translation", Decimal(1)),
        "scale_half_rotation": ("scale_half_rotation", Decimal("0.5")),
        "scale_double_rotation": ("scale_double_rotation", Decimal(2)),
    }
    expected_ids = set(base_specs)
    for base_id in metamorphic_bases:
        expected_ids.update(f"{base_id}.{variant}" for variant in variants)
    require(set(rows) == expected_ids and len(rows) == 59,
            "full configuration matrix ID set/count mismatch")
    for configuration_id, (family, profile, packet_count) in base_specs.items():
        row = rows[configuration_id]
        require(row["family"] == family and row["profile"] == profile,
                f"{configuration_id}: frozen family/profile mismatch")
        require(row["variant"] == "original" and row["transform"] == "identity",
                f"{configuration_id}: frozen original transform mismatch")
        require(row["base_configuration_id"] == configuration_id,
                f"{configuration_id}: original base ID mismatch")
        require(int(row["packet_count"]) == packet_count,
                f"{configuration_id}: frozen packet count mismatch")
    for base_id in metamorphic_bases:
        base = rows[base_id]
        for variant, (transform, scale) in variants.items():
            row = rows[f"{base_id}.{variant}"]
            require(row["base_configuration_id"] == base_id,
                    f"{base_id}.{variant}: base ID mismatch")
            require(row["family"] == base["family"] and row["profile"] == base["profile"],
                    f"{base_id}.{variant}: family/profile changed")
            require(row["variant"] == variant and row["transform"] == transform,
                    f"{base_id}.{variant}: transform metadata mismatch")
            emitted_scale = binary64(row["geometry_scale"], f"{base_id}.{variant} scale")
            assert emitted_scale is not None
            require(close_decimal(emitted_scale, scale, factor=Decimal("1e-16")),
                    f"{base_id}.{variant}: geometry scale mismatch")


FROZEN_JITTER = (
    (-7, 2, 5), (4, -1, -6), (1, 7, -3), (-2, -5, 6), (6, 3, 0),
    (-4, 1, 7), (3, -7, 2), (0, 5, -4), (7, -2, 1), (-5, 6, -1),
    (2, 0, 4), (-1, -3, -7), (5, 4, 3), (-6, -1, 2), (1, -4, 6),
    (-3, 7, -5), (4, 2, -2), (-7, -6, 5), (2, 3, 7), (-4, 5, 0),
    (6, -7, -1), (-1, 1, -4), (3, -2, 6), (-5, 4, -7), (7, 0, 3),
    (0, -5, 1), (5, 6, -2),
)
ROTATION_Q = (
    (Q(1, 9), Q(8, 9), Q(4, 9)),
    (Q(8, 9), Q(1, 9), Q(-4, 9)),
    (Q(-4, 9), Q(4, 9), Q(-7, 9)),
)
TRANSLATION_Q = (Q(13, 100), Q(-7, 100), Q(21, 100))


def frozen_intentionally_flexible(configuration_id: str, family: str) -> bool:
    """Return the preregistered physical-topology classification.

    This value is derived from the frozen configuration family/ID and never
    from a producer-supplied decision flag.  Metamorphic variants inherit the
    family of their registered base configuration.
    """

    return family in {"sheet", "filament"} or configuration_id.split(".", 2)[:2] == [
        "exact", "noncoplanar_underconnected"
    ] or configuration_id in {
        "exact.tetrahedron_k4_minus_edge",
        "exact.cube_edge_graph",
        "exact.planar_square_plus_diagonal",
        "exact.planar_square_plus_diagonal_and_volume",
    }


def q_matvec(matrix: Sequence[Sequence[Q]], vector: Sequence[Q]) -> tuple[Q, Q, Q]:
    return tuple(qsum(matrix[row][axis] * vector[axis] for axis in range(3))
                 for row in range(3))  # type: ignore[return-value]


def rectangular_q(nx: int, ny: int, nz: int, spacing: Q = Q(1, 4)) -> list[tuple[Q, Q, Q]]:
    return [
        (spacing * x, spacing * y, spacing * z)
        for z in range(nz) for y in range(ny) for x in range(nx)
    ]


def frozen_geometry() -> dict[str, dict[str, Any]]:
    a = Q(1, 4)
    bases: dict[str, dict[str, Any]] = {}

    def add(family: str, profiles: Sequence[tuple[str, Q]], points: list[tuple[Q, Q, Q]],
            jitter: list[tuple[Q, Q, Q]] | None = None) -> None:
        offsets = jitter or [(Q(0), Q(0), Q(0)) for _ in points]
        for profile, ratio in profiles:
            config_id = f"base.{family}.{profile}.original"
            bases[config_id] = {
                "positions": points,
                "jitter": offsets,
                "spacing": a,
                "support": a * ratio,
                "scale": Q(1),
            }

    add("sc3", (("r105", Q(21, 20)), ("r150", Q(3, 2)), ("r180", Q(9, 5))),
        rectangular_q(3, 3, 3))
    bcc = rectangular_q(3, 3, 3)
    bcc.extend((a * (Q(x) + Q(1, 2)), a * (Q(y) + Q(1, 2)),
                a * (Q(z) + Q(1, 2)))
               for z in range(2) for y in range(2) for x in range(2))
    add("bcc35", (("r105", Q(21, 20)), ("r150", Q(3, 2)), ("r180", Q(9, 5))), bcc)
    jitter = [tuple(a * Q(value, 100) for value in values) for values in FROZEN_JITTER]
    jittered = [tuple(base[axis] + offset[axis] for axis in range(3))
                for base, offset in zip(rectangular_q(3, 3, 3), jitter, strict=True)]
    add("jitter27", (("r105", Q(21, 20)), ("r150", Q(3, 2)), ("r180", Q(9, 5))),
        jittered, jitter)
    add("free_face", (("r150", Q(3, 2)), ("r180", Q(9, 5))), rectangular_q(4, 4, 3))
    add("edge_truncated", (("r150", Q(3, 2)), ("r180", Q(9, 5))), rectangular_q(4, 3, 3))
    add("corner_truncated", (("r150", Q(3, 2)), ("r180", Q(9, 5))), rectangular_q(3, 3, 3))
    add("sheet", (("r105", Q(21, 20)), ("r150", Q(3, 2))), rectangular_q(5, 5, 1))
    add("filament", (("r105", Q(21, 20)), ("r205", Q(41, 20))), rectangular_q(8, 1, 1))
    for percent in (10, 25, 40):
        bases[f"base.sc3_deletion.delete{percent}.original"] = {
            **bases["base.sc3.r180.original"]
        }

    exact: dict[str, list[tuple[Q, Q, Q]]] = {
        "exact.noncoplanar_underconnected": [(Q(0), Q(0), Q(0)), (a, Q(0), Q(0)),
            (Q(0), a, Q(0)), (Q(0), Q(0), a)],
        "exact.tetrahedron_k4": [(Q(0), Q(0), Q(0)), (Q(1), Q(0), Q(0)),
            (Q(0), Q(1), Q(0)), (Q(0), Q(0), Q(1))],
        "exact.tetrahedron_k4_minus_edge": [(Q(0), Q(0), Q(0)), (Q(1), Q(0), Q(0)),
            (Q(0), Q(1), Q(0)), (Q(0), Q(0), Q(1))],
        "exact.octahedron_graph": [(Q(1), Q(0), Q(0)), (Q(-1), Q(0), Q(0)),
            (Q(0), Q(1), Q(0)), (Q(0), Q(-1), Q(0)), (Q(0), Q(0), Q(1)),
            (Q(0), Q(0), Q(-1))],
        "exact.cube_edge_graph": [(Q(x), Q(y), Q(z)) for z in range(2)
            for y in range(2) for x in range(2)],
        "exact.planar_square_plus_diagonal": [(Q(0), Q(0), Q(0)), (Q(1), Q(0), Q(0)),
            (Q(1), Q(1), Q(0)), (Q(0), Q(1), Q(0))],
        "exact.planar_square_plus_diagonal_and_volume": [(Q(0), Q(0), Q(0)),
            (Q(1), Q(0), Q(0)), (Q(1), Q(1), Q(0)), (Q(0), Q(1), Q(0))],
    }
    for config_id, points in exact.items():
        bases[config_id] = {
            "positions": points,
            "jitter": [(Q(0), Q(0), Q(0)) for _ in points],
            "spacing": a,
            "support": Q(2),
            "scale": Q(1),
        }

    variants = {
        "translation": (Q(1), False, True),
        "rotation": (Q(1), True, False),
        "rotation_translation": (Q(1), True, True),
        "scale_half_rotation": (Q(1, 2), True, False),
        "scale_double_rotation": (Q(2), True, False),
    }
    for base_id in A_REPRESENTATIVES:
        base = bases[base_id]
        for variant, (scale, rotate, translate) in variants.items():
            points = []
            offsets = []
            for point, offset in zip(base["positions"], base["jitter"], strict=True):
                transformed = q_matvec(ROTATION_Q, point) if rotate else point
                transformed_offset = q_matvec(ROTATION_Q, offset) if rotate else offset
                points.append(tuple(scale * value + (TRANSLATION_Q[axis] if translate else Q(0))
                                    for axis, value in enumerate(transformed)))
                offsets.append(tuple(scale * value for value in transformed_offset))
            bases[f"{base_id}.{variant}"] = {
                "positions": points,
                "jitter": offsets,
                "spacing": base["spacing"] * scale,
                "support": base["support"] * scale,
                "scale": scale,
            }
    return bases


def rational_binary64_text(value: Q) -> str:
    result = float(value)
    if result == 0.0:
        result = 0.0
    return result.hex()


def validate_frozen_geometry(
    configurations: Mapping[str, Mapping[str, str]],
    packet_rows: Mapping[str, list[dict[str, str]]],
) -> None:
    expected = frozen_geometry()
    require(set(configurations) <= set(expected), "configuration outside frozen geometry matrix")
    for config_id, config in configurations.items():
        spec = expected[config_id]
        require(config["lookup_phase"] == "p000", f"{config_id}: configuration lookup phase")
        for field, target in (("nominal_spacing_m", spec["spacing"]),
                              ("support_radius_m", spec["support"]),
                              ("geometry_scale", spec["scale"])):
            fraction64(config[field], f"{config_id}/{field}")
            require(config[field] == rational_binary64_text(target),
                    f"{config_id}: frozen {field} differs from correctly rounded rational")
        rows = packet_rows[config_id]
        require(len(rows) == len(spec["positions"]), f"{config_id}: frozen packet count")
        for index, (row, position, jitter) in enumerate(zip(
            rows, spec["positions"], spec["jitter"], strict=True
        )):
            require(int(row["packet_id"]) == index + 1, f"{config_id}: frozen packet IDs")
            require(int(row["mass_quanta"]) == 4096, f"{config_id}/{index + 1}: frozen mass")
            for axis, field in enumerate(("x_m", "y_m", "z_m")):
                fraction64(row[field], f"{config_id}/{field}")
                require(row[field] == rational_binary64_text(position[axis]),
                        f"{config_id}/{index + 1}: frozen {field} not verbatim")
            for axis, field in enumerate(("jitter_dx_m", "jitter_dy_m", "jitter_dz_m")):
                fraction64(row[field], f"{config_id}/{field}")
                require(row[field] == rational_binary64_text(jitter[axis]),
                        f"{config_id}/{index + 1}: frozen {field} not verbatim")
            for field in ("vx_m_per_s", "vy_m_per_s", "vz_m_per_s"):
                require(row[field] == "0x0.0p+0", f"{config_id}/{index + 1}: nonzero frozen velocity")


def validate_checkpoints(
    rows: Sequence[dict[str, str]],
    configurations: Mapping[str, Mapping[str, str]],
    packet_rows: Mapping[str, list[dict[str, str]]],
    topology: Mapping[str, Mapping[str, Any]],
) -> tuple[bool, bool]:
    kind_order = {
        "authoritative_before": 0,
        "round_trip_reserialized": 1,
        "after_diagnostics": 2,
    }
    grouped: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        config_id = row["configuration_id"]
        require(config_id in configurations, f"checkpoint: unknown configuration {config_id}")
        kind = row["checkpoint_kind"]
        require(kind in kind_order, f"{config_id}: unknown checkpoint kind")
        require(kind not in grouped[config_id], f"{config_id}: duplicate checkpoint kind {kind}")
        grouped[config_id][kind] = row
    require(set(grouped) == set(configurations), "checkpoint/configuration inventory mismatch")
    require(all(set(group) == set(kind_order) for group in grouped.values()),
            "checkpoint kind inventory mismatch")

    def read_u64(payload: bytes, offset: int, where: str) -> tuple[int, int]:
        require(offset + 8 <= len(payload), f"{where}: truncated u64")
        return struct.unpack_from("<Q", payload, offset)[0], offset + 8

    def read_f64(payload: bytes, offset: int, where: str) -> tuple[float, int]:
        bits, offset = read_u64(payload, offset, where)
        value = struct.unpack("<d", struct.pack("<Q", bits))[0]
        require(math.isfinite(value), f"{where}: nonfinite checkpoint binary64")
        require(not (value == 0.0 and bits >> 63), f"{where}: checkpoint negative zero")
        return value, offset

    def parse_row(
        row: Mapping[str, str], config_id: str, *, bind_authoritative: bool
    ) -> tuple[bytes, str]:
        require(row["encoding"] == "lowercase_hex", f"{config_id}: checkpoint encoding")
        payload_hex = row["payload_hex"]
        require(re.fullmatch(r"(?:[0-9a-f]{2})+", payload_hex) is not None,
                f"{config_id}: noncanonical checkpoint hex")
        payload = bytes.fromhex(payload_hex)
        require(unsigned(row["byte_count"], f"{config_id} checkpoint bytes") == len(payload),
                f"{config_id}: checkpoint byte count")
        digest = hashlib.sha256(payload).hexdigest()
        require(sha256(row["payload_sha256"], f"{config_id} checkpoint digest") == digest,
                f"{config_id}: checkpoint payload digest")
        config = configurations[config_id]
        require(payload[:8] == b"MLSMOBS1", f"{config_id}: checkpoint magic")
        require(len(payload) >= 20, f"{config_id}: checkpoint truncated header")
        version = struct.unpack_from("<I", payload, 8)[0]
        require(version == 1, f"{config_id}: checkpoint version")
        offset = 12
        support, offset = read_f64(payload, offset, f"{config_id}/support")
        require(support > 0.0, f"{config_id}: checkpoint support must be positive")
        if bind_authoritative:
            require(support.hex() == config["support_radius_m"],
                    f"{config_id}: checkpoint support mismatch")
        count, offset = read_u64(payload, offset, f"{config_id}/packet_count")
        require(count <= 10_000, f"{config_id}: checkpoint packet count cap")
        if bind_authoritative:
            require(count == len(packet_rows[config_id]), f"{config_id}: checkpoint packet count")
        rebuilt = bytearray(b"MLSMOBS1" + struct.pack("<I", 1) + struct.pack("<d", support))
        rebuilt.extend(struct.pack("<Q", count))
        observed_packet_ids: list[int] = []
        for index in range(count):
            packet_id, offset = read_u64(payload, offset, f"{config_id}/packet/{index}/id")
            mass_bits, offset = read_u64(payload, offset, f"{config_id}/packet/{index}/mass")
            mass = struct.unpack("<q", struct.pack("<Q", mass_bits))[0]
            values: list[float] = []
            for field in ("x", "y", "z", "vx", "vy", "vz"):
                value, offset = read_f64(payload, offset, f"{config_id}/packet/{index}/{field}")
                values.append(value)
            require(packet_id > 0 and mass > 0, f"{config_id}: invalid checkpoint packet")
            observed_packet_ids.append(packet_id)
            if bind_authoritative:
                expected = packet_rows[config_id][index]
                require(packet_id == int(expected["packet_id"])
                        and mass == int(expected["mass_quanta"]),
                        f"{config_id}: checkpoint packet identity/mass mismatch")
                for value, field in zip(values, (
                    "x_m", "y_m", "z_m", "vx_m_per_s", "vy_m_per_s", "vz_m_per_s"
                ), strict=True):
                    require(value.hex() == expected[field],
                            f"{config_id}/{packet_id}: checkpoint {field} mismatch")
            rebuilt.extend(struct.pack("<Qq", packet_id, mass))
            rebuilt.extend(struct.pack("<6d", *values))
        require(observed_packet_ids == sorted(set(observed_packet_ids)),
                f"{config_id}: checkpoint packet order/uniqueness")
        packet_id_set = set(observed_packet_ids)
        bond_count, offset = read_u64(payload, offset, f"{config_id}/bond_count")
        maximum_bonds = count * (count - 1) // 2 if count >= 2 else 0
        require(bond_count <= min(1_000_000, maximum_bonds),
                f"{config_id}: checkpoint bond count exceeds packet-derived cap")
        bonds: list[tuple[int, int]] = []
        rebuilt.extend(struct.pack("<Q", bond_count))
        for index in range(bond_count):
            first, offset = read_u64(payload, offset, f"{config_id}/bond/{index}/first")
            second, offset = read_u64(payload, offset, f"{config_id}/bond/{index}/second")
            bonds.append((first, second))
            rebuilt.extend(struct.pack("<QQ", first, second))
        require(bonds == sorted(set(bonds)) and all(first < second for first, second in bonds),
                f"{config_id}: checkpoint bond order/uniqueness")
        require(all(first in packet_id_set and second in packet_id_set
                    for first, second in bonds),
                f"{config_id}: checkpoint bond has dangling endpoint")
        if bind_authoritative:
            require(bonds == topology[config_id]["retained_edges"],
                    f"{config_id}: checkpoint retained-bond mismatch")
        volume_count, offset = read_u64(payload, offset, f"{config_id}/volume_count")
        maximum_volumes = (
            count * math.comb(count - 1, 3) if count >= 4 else 0
        )
        require(volume_count <= min(1_000_000, maximum_volumes),
                f"{config_id}: checkpoint volume count exceeds packet-derived cap")
        volumes: list[tuple[int, int, int, int]] = []
        rebuilt.extend(struct.pack("<Q", volume_count))
        for index in range(volume_count):
            sites: list[int] = []
            for site in range(4):
                value, offset = read_u64(payload, offset, f"{config_id}/volume/{index}/{site}")
                sites.append(value)
            volumes.append(tuple(sites))  # type: ignore[arg-type]
            rebuilt.extend(struct.pack("<QQQQ", *sites))
        require(volumes == sorted(set(volumes)),
                f"{config_id}: checkpoint volume order/uniqueness")
        require(all(
            center in packet_id_set
            and all(site in packet_id_set for site in others)
            and center not in others
            and list(others) == sorted(set(others))
            for center, *others in volumes
        ), f"{config_id}: checkpoint volume has dangling/noncanonical sites")
        if bind_authoritative:
            require(volumes == topology[config_id]["volumes"],
                    f"{config_id}: checkpoint volume mismatch")
        require(offset == len(payload), f"{config_id}: checkpoint trailing bytes")
        require(bytes(rebuilt) == payload, f"{config_id}: checkpoint reserialization mismatch")
        return payload, digest

    round_trip_all = True
    diagnostics_all = True
    for config_id in sorted(configurations):
        group = grouped[config_id]
        before, before_hash = parse_row(
            group["authoritative_before"], config_id, bind_authoritative=True
        )
        round_trip, _round_hash = parse_row(
            group["round_trip_reserialized"], config_id, bind_authoritative=False
        )
        after, after_hash = parse_row(
            group["after_diagnostics"], config_id, bind_authoritative=False
        )
        config = configurations[config_id]
        require(config["input_checkpoint_sha256_before"] == before_hash,
                f"{config_id}: before checkpoint hash binding")
        require(config["input_checkpoint_sha256_after"] == after_hash,
                f"{config_id}: after checkpoint hash binding")
        round_trip_equal = before == round_trip
        diagnostics_equal = before == after
        require(boolean(config["diagnostics_read_only_exact"], f"{config_id} read-only")
                == diagnostics_equal,
                f"{config_id}: diagnostics read-only flag mismatch")
        round_trip_all = round_trip_all and round_trip_equal
        diagnostics_all = diagnostics_all and diagnostics_equal
    return round_trip_all, diagnostics_all


def validate_operator_status_metadata(
    status_by_id: Mapping[str, Mapping[str, str]],
    topology: Mapping[str, Mapping[str, Any]],
) -> None:
    observable_by_candidate = {
        "A": {"frozen_quadratic_sampling", "frozen_quadratic_symmetric_gradient", "frozen_quadratic_gauge"},
        "B": {"corrected_local_symmetric_gradient"},
        "C": {"central_bond_length_rate"},
        "D": {"enriched_bond_and_volume"},
    }
    configuration_ids = set(topology)
    expected_ids = {f"{configuration_id}.{candidate}"
                    for configuration_id in configuration_ids for candidate in ("B", "C", "D")}
    expected_ids.update(
        f"{configuration_id}.A.{phase}.{suffix}"
        for configuration_id in A_REPRESENTATIVES if configuration_id in configuration_ids
        for phase in LOOKUP_PHASES for suffix in ("S", "D")
    )
    require(set(status_by_id) == expected_ids, "operator inventory differs from frozen A/B/C/D matrix")
    role_by_candidate = {
        "B": "corrected_local_gradient",
        "C": "central_relation_graph",
        "D": "objective_volume_enrichment",
    }
    for operator_id, status in status_by_id.items():
        candidate = status["candidate"]
        require(status["observable_kind"] in observable_by_candidate[candidate],
                f"{operator_id}: observable kind")
        identifier(status["operator_role"], f"{operator_id} operator role")
        if candidate in role_by_candidate:
            require(operator_id == f"{status['configuration_id']}.{candidate}",
                    f"{operator_id}: packet operator ID")
            require(status["operator_role"] == role_by_candidate[candidate],
                    f"{operator_id}: operator role")
        relation_count = unsigned(status["relation_count"], f"{operator_id} relation count")
        configuration_topology = topology[status["configuration_id"]]
        expected_relations = 0
        if candidate == "C":
            expected_relations = len(configuration_topology["retained_edges"])
        elif candidate == "D":
            expected_relations = len(configuration_topology["retained_edges"]) + len(
                configuration_topology["volumes"]
            )
        require(relation_count == expected_relations, f"{operator_id}: relation count mismatch")
        if candidate == "C":
            require(status["build_status"] in {"built", "numerical_failure"},
                    f"{operator_id}: C attempted-build status")
        if candidate == "D":
            require(status["build_status"] in {
                "built", "numerical_failure", "not_triggered",
            }, f"{operator_id}: D build status")
        rank_applicable = boolean(status["rank_applicable"], f"{operator_id} rank applicable")
        decision_driving = boolean(status["decision_driving"], f"{operator_id} decision")
        raw_exported = boolean(status["raw_exported"], f"{operator_id} raw")
        if status["build_status"] != "built":
            require(not rank_applicable, f"{operator_id}: failed build marked rank-applicable")
        if candidate == "A":
            expected_decision = True
        elif candidate == "B":
            expected_decision = bool(
                topology[status["configuration_id"]]["generic_solid_gate"]
            )
        else:
            expected_decision = candidate == "C" or (
                bool(topology[status["configuration_id"]]["generic_solid_gate"])
                and status["build_status"] != "not_triggered"
            )
        require(decision_driving == expected_decision,
                f"{operator_id}: attempted operator decision inventory")
        expected_rank_applicable = expected_operator_rank_applicable(
            operator_id, status_by_id
        )
        require(rank_applicable == expected_rank_applicable,
                f"{operator_id}: rank-applicable status inventory")
        if status["build_status"] == "built":
            require(raw_exported, f"{operator_id}: built operator is not exported")
        b_eligible = boolean(status["b_rank_eligible"], f"{operator_id} B eligible")
        require((candidate == "B" and b_eligible == (status["build_status"] == "built"))
                or (candidate != "B" and not b_eligible),
                f"{operator_id}: B eligibility flag")
        first_invalid = status["first_invalid_row"]
        if boolean(status["row_normalization_complete"], f"{operator_id} normalization"):
            require(first_invalid == "NA", f"{operator_id}: completed normalization has invalid row")
        elif status["failure_stage"] == "row_normalization":
            unsigned(first_invalid, f"{operator_id} first invalid row")
        else:
            require(first_invalid == "NA", f"{operator_id}: non-normalization invalid row")


def rank_claim_is_resolved(rank: Mapping[str, Any] | None) -> bool:
    nonrigid_nullity = None if rank is None else rank.get("nonrigid_nullity")
    return (
        rank is not None
        and rank["status"] == "analyzed"
        and not rank["ambiguous"]
        and rank["basis_complete"]
        and rank.get("contract_pass", False)
        # Scientific reducers consume this quotient.  A completed-looking rank
        # row with an unavailable quotient is therefore unresolved, even if a
        # producer flag accidentally claims that the surrounding contract
        # passed.  ``type(...) is int`` deliberately excludes booleans.
        and type(nonrigid_nullity) is int
        and nonrigid_nullity >= 0
    )


def candidate_a_rank_supports_gauge(rank: Mapping[str, Any] | None) -> bool:
    """Whether the closed A rank wire permits null/gauge diagnostics."""

    return bool(
        rank is not None
        and rank["status"] == "analyzed"
        and not rank["ambiguous"]
        and rank["basis_complete"]
    )


def derive_decisive_rank_gate(
    status_by_id: Mapping[str, Mapping[str, str]],
    ranks: Mapping[str, Mapping[str, Any]],
) -> tuple[bool, bool]:
    """Return (decisive-rank contract, independent-basis agreement).

    A decision-driving attempted operator that did not build is an explicit
    implementation stop even though it correctly has no rank rows.  A built
    rank-applicable operator must have a resolved accepted rank contract.
    This common reducer makes partial Candidate-A pairs and B/C/D build/rank
    failures follow the same fail-closed rule.
    """

    independent_basis_agreement = all(
        rank.get("independent_basis_agreement", True) for rank in ranks.values()
    )
    decisive = [
        (operator_id, status)
        for operator_id, status in status_by_id.items()
        if boolean(status["decision_driving"], f"{operator_id} decision driving")
    ]
    return independent_basis_agreement and all(
        status["build_status"] == "built"
        and (
            not boolean(status["rank_applicable"], f"{operator_id} rank applicable")
            or rank_claim_is_resolved(ranks.get(operator_id))
        )
        for operator_id, status in decisive
    ), independent_basis_agreement


def derive_global_d_trigger(
    status_by_id: Mapping[str, Mapping[str, str]],
    ranks: Mapping[str, Mapping[str, Any]],
    generic_configurations: set[str],
) -> bool:
    """Derive D's global trigger only from independently accepted C ranks."""
    generic_c = [
        (operator_id, status)
        for operator_id, status in status_by_id.items()
        if status["candidate"] == "C"
        and status["configuration_id"] in generic_configurations
        and not status["configuration_id"].startswith("exact.")
    ]
    if not generic_c:
        return False
    every_contract_is_accepted = all(
        status["build_status"] == "built"
        and boolean(status["row_normalization_complete"], f"{operator_id} normalization")
        and boolean(status["raw_exported"], f"{operator_id} raw export")
        and rank_claim_is_resolved(ranks.get(operator_id))
        for operator_id, status in generic_c
    )
    return every_contract_is_accepted and any(
        ranks[operator_id]["nonrigid_nullity"] > 0
        for operator_id, _status in generic_c
    )


def validate_global_d_inventory(
    status_by_id: Mapping[str, Mapping[str, str]],
    ranks: Mapping[str, Mapping[str, Any]],
    topology: Mapping[str, Mapping[str, Any]],
    generic_configurations: set[str],
) -> bool:
    """Bind the all-or-none D sweep to the independent generic-C trigger.

    The registered enriched exact control is intentionally outside this global
    trigger.  Every other configuration either has no selected volume and no
    built D operator, or (after one resolved generic C failure) receives the
    complete frozen selector result.  This prevents producer-supplied volume
    rows from defining their own trigger.
    """
    triggered = derive_global_d_trigger(status_by_id, ranks, generic_configurations)
    for configuration_id, facts in topology.items():
        if configuration_id.startswith("exact."):
            continue
        expected_volumes = facts["frozen_enrichment"] if triggered else []
        require(
            facts["volumes"] == expected_volumes,
            f"{configuration_id}: global D selector inventory mismatch",
        )
        operator_id = f"{configuration_id}.D"
        require(operator_id in status_by_id, f"{configuration_id}: missing D status")
        observed_build = status_by_id[operator_id]["build_status"]
        if expected_volumes:
            require(observed_build in {"built", "numerical_failure"},
                    f"{configuration_id}: triggered D was not attempted")
        else:
            require(observed_build == "not_triggered",
                    f"{configuration_id}: unexpected untriggered D attempt")
    return triggered


def derive_decision(
    summary: Mapping[str, Any],
    status_by_id: Mapping[str, Mapping[str, str]],
    ranks: Mapping[str, Mapping[str, Any]],
    negative_control: bool,
    generic_configurations: set[str],
) -> tuple[dict[str, str], str]:
    def is_generic(status: Mapping[str, str]) -> bool:
        # The reducer consumes only the independently rebuilt topology screen,
        # never producer configuration/operator booleans.
        return status["configuration_id"] in generic_configurations

    decisive_operators = [
        operator_id for operator_id, status in status_by_id.items()
        if boolean(status["decision_driving"], f"{operator_id} decision")
    ]
    rank_inconclusive = any(
        boolean(status_by_id[operator_id]["rank_applicable"], f"{operator_id} rank applicable")
        and not rank_claim_is_resolved(ranks.get(operator_id))
        for operator_id in decisive_operators
    )
    decisive_contract_ready = all(
        status_by_id[operator_id]["build_status"] == "built"
        and (
            not boolean(
                status_by_id[operator_id]["rank_applicable"],
                f"{operator_id} rank applicable",
            )
            or rank_claim_is_resolved(ranks.get(operator_id))
        )
        for operator_id in decisive_operators
    )
    required_flags = (
        "checkpoint_round_trip_all_pass",
        "diagnostics_read_only_all_exact",
        "neighbor_lookup_all_agree",
        "affine_objectivity_all_pass",
        "finite_objectivity_all_pass",
        "invariance_all_pass",
        "decisive_rank_rows_all_unambiguous",
        "raw_decision_rows_all_exported",
        "independent_reference_all_pass",
    )
    implementation_failure = (
        summary["mode"] != "full"
        or not negative_control
        or rank_inconclusive
        or not decisive_contract_ready
        or any(summary[key] is not True for key in required_flags)
        or summary["nondeterminism_detected"] is True
    )
    b_eligible = [
        operator_id for operator_id, status in status_by_id.items()
        if status["candidate"] == "B"
        and is_generic(status)
        and boolean(status["b_rank_eligible"], f"{operator_id} B eligible")
        and boolean(status["decision_driving"], f"{operator_id} decision")
    ]
    c_generic = [
        operator_id for operator_id, status in status_by_id.items()
        if status["candidate"] == "C"
        and is_generic(status)
        and boolean(status["decision_driving"], f"{operator_id} decision")
    ]
    b_science_ready = bool(b_eligible) and all(
        status_by_id[operator_id]["build_status"] == "built"
        and boolean(
            status_by_id[operator_id]["rank_applicable"],
            f"{operator_id} rank applicable",
        )
        and rank_claim_is_resolved(ranks.get(operator_id))
        for operator_id in b_eligible
    )
    c_science_ready = bool(c_generic) and all(
        status_by_id[operator_id]["build_status"] == "built"
        and boolean(
            status_by_id[operator_id]["rank_applicable"],
            f"{operator_id} rank applicable",
        )
        and rank_claim_is_resolved(ranks.get(operator_id))
        for operator_id in c_generic
    )
    implementation_failure = (
        implementation_failure or not b_science_ready or not c_science_ready
    )
    if implementation_failure:
        findings = {
            "A": "negative_control_reproduced" if negative_control else "negative_control_failed",
            "B": "inconclusive",
            "C": "inconclusive",
            "D": "inconclusive",
        }
        return findings, "stop_inconclusive_or_implementation_failure"

    # Every scientific B/C quotient is now an independently accepted
    # non-negative integer.  D inventory still has its own availability gate,
    # so defer the actual scientific reductions until that gate also passes.
    global_d_trigger = derive_global_d_trigger(
        status_by_id, ranks, generic_configurations
    )
    generic_d = {
        operator_id for operator_id, status in status_by_id.items()
        if status["candidate"] == "D" and is_generic(status)
        and not status["configuration_id"].startswith("exact.")
    }
    triggered_d = {
        operator_id for operator_id, status in status_by_id.items()
        if status["candidate"] == "D" and status["build_status"] == "built"
        and is_generic(status) and not status["configuration_id"].startswith("exact.")
    }
    expected_triggered_d = generic_d if global_d_trigger else set()
    triggered_d_incomplete = any(
        not rank_claim_is_resolved(ranks.get(operator_id))
        for operator_id in triggered_d
    )
    implementation_failure = (
        triggered_d != expected_triggered_d
        or triggered_d_incomplete
    )
    if implementation_failure:
        findings = {
            "A": "negative_control_reproduced" if negative_control else "negative_control_failed",
            "B": "inconclusive",
            "C": "inconclusive",
            "D": "inconclusive",
        }
        return findings, "stop_inconclusive_or_implementation_failure"
    # All B/C and any triggered D ranks are now resolved.  Only below this line
    # may scientific quotient fields be consumed.
    b_nonrigid = any(
        ranks[operator_id]["nonrigid_nullity"] > 0
        for operator_id in b_eligible
    )
    c_classification_inconsistent = any(
        ranks[operator_id]["nonrigid_nullity"] == 0
        and not ranks[operator_id].get("generic_pass", False)
        for operator_id in c_generic
    )
    triggered_d_classification_inconsistent = any(
        ranks[operator_id]["nonrigid_nullity"] == 0
        and not ranks[operator_id].get("generic_pass", False)
        for operator_id in triggered_d
    )
    if c_classification_inconsistent or triggered_d_classification_inconsistent:
        return {
            "A": "negative_control_reproduced",
            "B": "inconclusive",
            "C": "inconclusive",
            "D": "inconclusive",
        }, "stop_inconclusive_or_implementation_failure"
    b_finding = (
        "reject_averaged_single_gradient_packet_kinematics"
        if b_nonrigid else "no_resolved_eligible_nonrigid_mode"
    )
    if not global_d_trigger:
        findings = {
            "A": "negative_control_reproduced",
            "B": b_finding,
            "C": "retain_central_relational_representation_for_research",
            "D": "not_triggered",
        }
        return findings, "retain_central_relational_representation_for_research"
    d_nonrigid = [
        operator_id for operator_id in sorted(triggered_d)
        if ranks[operator_id]["nonrigid_nullity"] > 0
    ]
    if not d_nonrigid:
        return {
            "A": "negative_control_reproduced", "B": b_finding,
            "C": "generic_nonrigid_mode_triggers_d",
            "D": "retain_volume_enriched_relational_representation_for_research",
        }, "retain_volume_enriched_relational_representation_for_research"
    return {
        "A": "negative_control_reproduced", "B": b_finding,
        "C": "generic_nonrigid_mode_triggers_d",
        "D": "stop_reconsider_packet_abstraction",
    }, "stop_reconsider_packet_abstraction"


def compare_bundles(first: Path, second: Path) -> list[dict[str, str]]:
    first_files = sorted(path.name for path in first.iterdir())
    second_files = sorted(path.name for path in second.iterdir())
    require(first_files == second_files, "compared bundle inventory differs")
    mismatches: list[dict[str, str]] = []
    for name in first_files:
        require((first / name).is_file() and (second / name).is_file(),
                f"compared entry {name} is not regular")
        first_digest = hashlib.sha256((first / name).read_bytes()).hexdigest()
        second_digest = hashlib.sha256((second / name).read_bytes()).hexdigest()
        if first_digest != second_digest:
            mismatches.append({
                "path": name,
                "first_sha256": first_digest,
                "second_sha256": second_digest,
            })
    return mismatches


def validate_snapshot_bundle(bundle: Path, *, allow_smoke: bool) -> Mapping[str, Any]:
    require(bundle.is_dir(), f"bundle is not a directory: {bundle}")
    verify_manifest(bundle)
    tables = {name: read_csv(bundle / name, fields) for name, fields in CSV_SCHEMAS.items()}
    validate_canonical_integer_cells(tables)
    require_table_order(tables)
    summary = read_json(bundle / "summary.json")
    validate_summary(summary, tables)
    require(summary["mode"] == "full" or allow_smoke, "smoke bundle requires --allow-smoke")
    configurations_by_id = validate_configuration_rows(tables["configurations.csv"])
    if summary["mode"] == "full":
        validate_full_configuration_matrix(configurations_by_id)
    packet_rows, positions_d, positions_q = validate_packet_tables(
        tables["configurations.csv"], tables["packets.csv"]
    )
    validate_frozen_geometry(configurations_by_id, packet_rows)
    neighbors, neighbor_lookup_all_agree = validate_neighbors(
        tables["configurations.csv"], tables["neighbor_pairs.csv"], positions_d
    )
    topology = validate_relations(
        tables["configurations.csv"], tables["relations.csv"], positions_d, positions_q
    )
    generic_configurations = {
        configuration_id for configuration_id, facts in topology.items()
        if facts["generic_solid_gate"]
    }
    checkpoint_all_pass, diagnostics_read_only_all = validate_checkpoints(
        tables["checkpoints.csv"], configurations_by_id, packet_rows, topology
    )
    for configuration_id, phases in neighbors.items():
        retained = set(topology[configuration_id]["retained_edges"])
        physical_rows = [
            row for row in tables["relations.csv"]
            if row["configuration_id"] == configuration_id
            and row["relation_kind"] == "bond"
            and row["selection_source"] == "physical_radius"
        ]
        deletion_rows = [
            row for row in tables["relations.csv"]
            if row["configuration_id"] == configuration_id
            and row["relation_kind"] == "bond"
            and row["selection_source"].startswith("sha256_deletion_")
        ]
        if physical_rows and not deletion_rows:
            require(retained == next(iter(phases.values())),
                    f"{configuration_id}: radius relation set differs from physical support")
        if deletion_rows:
            configuration = configurations_by_id[configuration_id]
            match = re.fullmatch(r"delete(10|25|40)", configuration["profile"])
            require(match is not None, f"{configuration_id}: deletion graph profile")
            percent = int(match.group(1))
            all_bond_rows = [
                row for row in tables["relations.csv"]
                if row["configuration_id"] == configuration_id
                and row["relation_kind"] == "bond"
            ]
            all_edges = {(int(row["first_id"]), int(row["second_id"])) for row in all_bond_rows}
            require(all_edges == next(iter(phases.values())),
                    f"{configuration_id}: deletion universe differs from physical support")
            ordering = sorted(
                (
                    hashlib.sha256(
                        f"{SEED}|{configuration_id}|{low}|{high}".encode("utf-8")
                    ).hexdigest(),
                    (low, high),
                )
                for low, high in all_edges
            )
            remove_count = len(all_edges) * percent // 100
            expected_deleted = {edge for _digest, edge in ordering[:remove_count]}
            require(set(topology[configuration_id]["deleted_edges"]) == expected_deleted,
                    f"{configuration_id}: SHA-256 deletion set mismatch")
            for row in deletion_rows:
                require(row["selection_source"] == f"sha256_deletion_{percent}"
                        and row["selection_status"] == "deleted",
                        f"{configuration_id}: deletion provenance mismatch")
    status_by_id, matrices, _moments, reference_matrices = validate_operator_tables(
        tables["configurations.csv"], generic_configurations, packet_rows, positions_d,
        tables["relations.csv"], tables["operator_status.csv"],
        tables["operator_entries.csv"], tables["moment_diagnostics.csv"],
        tables["grid_nodes.csv"],
    )
    validate_operator_status_metadata(status_by_id, topology)
    failure_fixture_target = validate_failure_fixture_contract(summary, status_by_id)
    controls = validate_candidate_a_inputs(
        tables["grid_nodes.csv"], configurations_by_id, positions_d,
        status_by_id, tables["operator_entries.csv"], matrices,
        injected_zero_fixture_target=failure_fixture_target,
    )
    for sampling_id, control in controls.items():
        reference_matrices[sampling_id] = control["sampling"]
        reference_matrices[control["derivative_id"]] = control["derivative"]
    validate_b_moment_eligibility(
        configurations_by_id, positions_d, status_by_id,
        tables["moment_diagnostics.csv"],
    )
    exact_claims, exact_reference_rows_pass = validate_exact_references(
        tables["exact_reference.csv"], status_by_id, positions_q,
        tables["relations.csv"], full=summary["mode"] == "full",
    )
    permutation_controls = validate_permutation_controls(
        tables["permutation_controls.csv"], tables["permutation_entries.csv"],
        status_by_id, packet_rows, tables["relations.csv"],
        tables["operator_entries.csv"], matrices,
    )
    ranks = validate_rank_and_bases(
        status_by_id, matrices, reference_matrices, positions_d, tables["rank_status.csv"],
        tables["rigid_basis.csv"], tables["nullspace_modes.csv"],
        tables["nullspace_metrics.csv"],
    )
    validate_global_d_inventory(
        status_by_id, ranks, topology, generic_configurations
    )
    exact_numerical_agreement = exact_reference_rows_pass
    exact_numerical_agreement = exact_numerical_agreement and all(
        rank.get("reference_rank_match", False) for rank in ranks.values()
    )
    for operator_id, (exact_rank, exact_nullity, exact_nonrigid) in exact_claims.items():
        numerical = ranks.get(operator_id)
        exact_numerical_agreement = exact_numerical_agreement and bool(
            numerical is not None
            and rank_claim_is_resolved(numerical)
            and (
                numerical["rank"], numerical["nullity"],
                numerical["nonrigid_nullity"],
            ) == (exact_rank, exact_nullity, exact_nonrigid)
        )
    validate_affine_objectivity(
        tables["affine_objectivity.csv"], status_by_id, matrices, positions_d,
        tables["relations.csv"], configurations_by_id,
    )
    validate_invariance(
        tables["invariance.csv"], status_by_id, configurations_by_id, topology,
        ranks, matrices,
        permutation_controls,
    )
    negative_control = validate_grid_gauge(
        tables["grid_gauge.csv"], status_by_id, controls,
        tables["nullspace_modes.csv"], ranks,
    )
    all_affine_pass = bool(tables["affine_objectivity.csv"]) and all(
        boolean(row["pass"], f"{row['operator_id']}/{row['test_id']} pass")
        for row in tables["affine_objectivity.csv"]
        if row["test_kind"] in {
            "linear_operator_aggregate", "full_gradient_reproduction"
        }
    )
    finite_rows = [
        row for row in tables["affine_objectivity.csv"]
        if row["test_kind"] in {"finite_bond_length", "finite_oriented_volume"}
    ]
    all_finite_pass = bool(finite_rows) and all(
        boolean(row["pass"], f"{row['operator_id']}/{row['test_id']} finite pass")
        for row in finite_rows
    )
    all_invariance_pass = derive_invariance_aggregate(
        tables["invariance.csv"], status_by_id
    )
    decision_statuses = [
        (operator_id, status)
        for operator_id, status in status_by_id.items()
        if boolean(status["decision_driving"], f"{operator_id} decision driving")
    ]
    actual_raw_decision_rows = all(
        boolean(status["raw_exported"], f"{operator_id} raw exported")
        for operator_id, status in decision_statuses
    )
    actual_decisive_rank, independent_basis_agreement = derive_decisive_rank_gate(
        status_by_id, ranks
    )
    derived_gates = {
        "affine_objectivity_all_pass": all_affine_pass,
        "checkpoint_round_trip_all_pass": checkpoint_all_pass,
        "decisive_rank_rows_all_unambiguous": actual_decisive_rank,
        "deterministic_repeatability": not summary["nondeterminism_detected"],
        "diagnostics_read_only_all_exact": diagnostics_read_only_all,
        "finite_objectivity_all_pass": all_finite_pass,
        "independent_basis_agreement": independent_basis_agreement,
        "independent_reference_all_pass": exact_numerical_agreement,
        "invariance_all_pass": all_invariance_pass,
        "negative_control_reproduced": negative_control,
        "neighbor_lookup_all_agree": neighbor_lookup_all_agree,
        "raw_decision_rows_all_exported": actual_raw_decision_rows,
    }
    decision_inputs = dict(summary)
    for key in SUMMARY_CONTRACT_KEYS:
        decision_inputs[key] = derived_gates[key]
    decision_inputs["nondeterminism_detected"] = not derived_gates[
        "deterministic_repeatability"
    ]
    preliminary_findings, preliminary_decision = derive_decision(
        decision_inputs, status_by_id, ranks, negative_control, generic_configurations
    )
    claim_mismatches = [
        key for key in SUMMARY_CONTRACT_KEYS
        if summary[key] != derived_gates[key]
    ]
    if not independent_basis_agreement:
        claim_mismatches.append("independent_basis_agreement")
    if summary["candidate_findings"] != preliminary_findings:
        claim_mismatches.append("candidate_findings")
    if summary["decision"] != preliminary_decision:
        claim_mismatches.append("decision")
    derived_gates["producer_claims_consistent"] = not claim_mismatches
    if claim_mismatches:
        derived_findings = {
            "A": "negative_control_reproduced"
            if negative_control else "negative_control_failed",
            "B": "inconclusive",
            "C": "inconclusive",
            "D": "inconclusive",
        }
        derived_decision = "stop_inconclusive_or_implementation_failure"
    else:
        derived_findings, derived_decision = preliminary_findings, preliminary_decision
    require(summary["promotion"] is False, "bundle attempts promotion")
    result = dict(summary)
    result["_validator_derived_gates"] = derived_gates
    result["_validator_claim_mismatches"] = sorted(set(claim_mismatches))
    result["_validator_candidate_findings"] = derived_findings
    result["_validator_decision"] = derived_decision
    return result


def validate_bundle(bundle: Path, *, allow_smoke: bool) -> Mapping[str, Any]:
    with tempfile.TemporaryDirectory(prefix="mls-mechanical-validator-snapshot-") as temporary:
        snapshot = Path(temporary) / "bundle"
        signature = capture_bundle_snapshot(bundle, snapshot)
        summary = validate_snapshot_bundle(snapshot, allow_smoke=allow_smoke)
        require_live_bundle_unchanged(bundle, signature)
        return summary


def canonical_compact_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def build_validator_findings(
    outcomes: Sequence[Mapping[str, Any]],
    manifest_pre_hashes: Sequence[str],
    mismatches: Sequence[Mapping[str, str]],
    validator_sha256: str,
) -> dict[str, Any]:
    require(len(outcomes) in {1, 2}, "findings bundle cardinality")
    require(len(outcomes) == len(manifest_pre_hashes), "findings pre-hash cardinality")
    require(SHA256_RE.fullmatch(validator_sha256) is not None,
            "validator findings SHA-256")
    require(all(SHA256_RE.fullmatch(value) is not None
                for value in manifest_pre_hashes), "findings manifest pre-hash")
    require(not mismatches or len(outcomes) == 2,
            "single-bundle findings cannot contain comparison mismatches")
    mismatch_paths: list[str] = []
    allowed_mismatch_paths = {*REQUIRED_FILES, "manifest.json"}
    for mismatch in mismatches:
        require(set(mismatch) == {"path", "first_sha256", "second_sha256"},
                "findings mismatch schema")
        path = mismatch["path"]
        require(path in allowed_mismatch_paths, "findings mismatch path")
        require(SHA256_RE.fullmatch(mismatch["first_sha256"]) is not None
                and SHA256_RE.fullmatch(mismatch["second_sha256"]) is not None,
                "findings mismatch digest")
        require(mismatch["first_sha256"] != mismatch["second_sha256"],
                "findings mismatch has equal digests")
        mismatch_paths.append(path)
    require(mismatch_paths == sorted(set(mismatch_paths)),
            "findings mismatch inventory must be unique and sorted")
    first = outcomes[0]
    require(SOURCE_SHA_RE.fullmatch(first["source_sha"]) is not None,
            "findings source SHA")
    require(all(outcome["source_sha"] == first["source_sha"] for outcome in outcomes),
            "comparison source SHA")
    require(all(outcome["mode"] == first["mode"] for outcome in outcomes),
            "comparison bundle mode")
    comparison_status = "single" if len(outcomes) == 1 else (
        "nondeterministic" if mismatches else "byte_identical"
    )
    if comparison_status == "byte_identical":
        require(not any(outcome["nondeterminism_detected"] for outcome in outcomes),
                "byte-identical comparison claims nondeterminism")

    claim_mismatches: list[str] = []
    labels = ("first",) if len(outcomes) == 1 else ("first", "second")
    for label, outcome in zip(labels, outcomes, strict=True):
        claim_mismatches.extend(
            f"{label}.{key}" for key in outcome["_validator_claim_mismatches"]
        )
    if mismatches and not all(
        outcome["nondeterminism_detected"] for outcome in outcomes
    ):
        claim_mismatches.append("comparison.nondeterminism_detected")

    gate_names = {
        key for outcome in outcomes
        for key in outcome["_validator_derived_gates"]
    }
    require(all(set(outcome["_validator_derived_gates"]) == gate_names
                for outcome in outcomes), "derived gate inventory differs between bundles")
    derived_gates = {
        key: all(outcome["_validator_derived_gates"][key] for outcome in outcomes)
        for key in sorted(gate_names)
    }
    derived_gates["deterministic_repeatability"] = bool(
        derived_gates["deterministic_repeatability"] and not mismatches
    )
    derived_gates["producer_claims_consistent"] = not claim_mismatches

    requires_stop = bool(
        mismatches or claim_mismatches
        or any(outcome["_validator_decision"]
               == "stop_inconclusive_or_implementation_failure"
               for outcome in outcomes)
    )
    if requires_stop:
        candidate_findings = {
            "A": "negative_control_reproduced"
            if derived_gates["negative_control_reproduced"]
            else "negative_control_failed",
            "B": "inconclusive",
            "C": "inconclusive",
            "D": "inconclusive",
        }
        decision = "stop_inconclusive_or_implementation_failure"
    else:
        candidate_findings = dict(first["_validator_candidate_findings"])
        decision = first["_validator_decision"]
        require(all(outcome["_validator_candidate_findings"] == candidate_findings
                    and outcome["_validator_decision"] == decision
                    for outcome in outcomes),
                "comparison derived decision differs without byte mismatch")

    producer_summaries = [
        {key: value for key, value in outcome.items() if not key.startswith("_validator_")}
        for outcome in outcomes
    ]
    producer_claims_sha256 = hashlib.sha256(
        canonical_compact_json(producer_summaries)
    ).hexdigest()
    result: dict[str, Any] = {
        "schema": VALIDATOR_FINDINGS_SCHEMA,
        "validator_sha256": validator_sha256,
        "source_sha": first["source_sha"],
        "mode": first["mode"],
        "first_manifest_pre_hash": manifest_pre_hashes[0],
        "second_manifest_pre_hash": manifest_pre_hashes[1]
        if len(manifest_pre_hashes) == 2 else None,
        "comparison_status": comparison_status,
        "mismatches": list(mismatches),
        "bundle_structural_valid": [True] * len(outcomes),
        "producer_claims_sha256": producer_claims_sha256,
        "derived_gates": derived_gates,
        "claim_mismatches": sorted(set(claim_mismatches)),
        "candidate_findings": candidate_findings,
        "decision": decision,
        "promotion": False,
    }
    result["result_sha256_before_hash_field"] = hashlib.sha256(
        canonical_compact_json(result)
    ).hexdigest()
    return result


def validator_findings_bytes(findings: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(findings, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def write_validator_findings(path: Path, findings: Mapping[str, Any]) -> str:
    payload = validator_findings_bytes(findings)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(payload)
    except OSError as error:
        fail(f"cannot write validator findings: {error}")
    return hashlib.sha256(payload).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--allow-smoke", action="store_true")
    parser.add_argument("--findings-output", type=Path)
    parser.add_argument("--validator-sha256")
    args = parser.parse_args(argv)
    try:
        with tempfile.TemporaryDirectory(
            prefix="mls-mechanical-validator-snapshots-"
        ) as temporary:
            snapshot_root = Path(temporary)
            first_snapshot = snapshot_root / "first"
            first_signature = capture_bundle_snapshot(args.bundle, first_snapshot)
            summary = validate_snapshot_bundle(
                first_snapshot, allow_smoke=args.allow_smoke
            )
            manifest_pre_hash = read_json(first_snapshot / "manifest.json")[
                "pre_hash_sha256"
            ]
            outcomes = [summary]
            manifest_pre_hashes = [manifest_pre_hash]
            mismatches: list[dict[str, str]] = []
            if args.compare is not None:
                second_snapshot = snapshot_root / "second"
                second_signature = capture_bundle_snapshot(
                    args.compare, second_snapshot
                )
                comparison = validate_snapshot_bundle(
                    second_snapshot, allow_smoke=args.allow_smoke
                )
                outcomes.append(comparison)
                manifest_pre_hashes.append(
                    read_json(second_snapshot / "manifest.json")["pre_hash_sha256"]
                )
                mismatches = compare_bundles(first_snapshot, second_snapshot)
                require_live_bundle_unchanged(args.compare, second_signature)
            require_live_bundle_unchanged(args.bundle, first_signature)
            if args.validator_sha256 is not None:
                validator_digest = sha256(
                    args.validator_sha256, "validator --validator-sha256"
                )
            else:
                validator_path = Path(__file__)
                require(validator_path.is_file(),
                        "stdin validator requires --validator-sha256")
                validator_digest = hashlib.sha256(validator_path.read_bytes()).hexdigest()
            findings = build_validator_findings(
                outcomes, manifest_pre_hashes, mismatches, validator_digest
            )
            findings_digest = hashlib.sha256(
                validator_findings_bytes(findings)
            ).hexdigest()
            if args.findings_output is not None:
                written_digest = write_validator_findings(
                    args.findings_output, findings
                )
                require(written_digest == findings_digest,
                        "validator findings write digest mismatch")
    except (InvalidBundle, OSError, UnicodeError, ValueError, ArithmeticError) as error:
        sys.stderr.buffer.write(
            f"MECHANICAL OBSERVABILITY BUNDLE INVALID: {error}\n".encode("utf-8")
        )
        return 1
    valid_line = (
        "MECHANICAL OBSERVABILITY BUNDLE VALID: "
        f"configurations={len(summary['registered_configuration_ids'])} "
        f"operators={len(summary['registered_operator_ids'])} "
        f"source_sha={summary['source_sha']} "
        f"manifest_pre_hash={manifest_pre_hash} "
        f"decision={findings['decision']} promotion=false"
    )
    sys.stdout.buffer.write(
        f"{valid_line}\nfindings_sha256={findings_digest}\n".encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
