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
from collections import defaultdict
from decimal import Decimal, getcontext, localcontext
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
GRADIENT_ABSOLUTE_FLOOR = Decimal("1e-10")
GRADIENT_BOUND_MULTIPLIER = Decimal("1e4")
DECIMAL_PRECISION = 100
getcontext().prec = DECIMAL_PRECISION

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
    "normalized_mg_minus_q,mgq_roundoff_bound,mgq_pass,sg_minus_v_l2_m_per_s,"
    "sgv_denominator_m_per_s_sqrt_kg,normalized_sg_minus_v,sgv_roundoff_bound,"
    "sgv_pass,partition_max_residual,partition_roundoff_bound,partition_pass,"
    "linear_reproduction_max_residual_m,linear_reproduction_roundoff_bound_m,"
    "linear_reproduction_pass,gradient_partition_max_residual_per_m,"
    "gradient_partition_roundoff_bound_per_m,gradient_partition_pass,pass"
    .split(",")
)
SOLVE_FIELDS = tuple(
    "system_id,component,status,solver,iterations,"
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
NULLSPACE_MODE_FIELDS = tuple(
    "system_id,mode_index,node_index,z_value_m_per_s,method,singular_value_kg,"
    "representative_value_m_per_s,shifted_value_m_per_s".split(",")
)
NULLSPACE_METRIC_FIELDS = tuple(
    "system_id,mode_index,rank,rank_method,rank_is_certified,"
    "mz_l2_kg_m_per_s,mz_denominator_kg_m_per_s,mz_normalized,"
    "sz_l2_m_per_s,sz_denominator_m_per_s,sz_normalized,"
    "gradient_max_per_s,gradient_rms_per_s,gradient_roundoff_bound_per_s,"
    "visibility_ratio,gradient_visible,alpha_m_per_s,representative_component,"
    "representative_kind,base_residual_normalized,shifted_residual_normalized,"
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
    "nullspace_modes.csv": NULLSPACE_MODE_FIELDS,
    "nullspace_metrics.csv": NULLSPACE_METRIC_FIELDS,
}
REQUIRED_FILES = (*CSV_SCHEMAS, "summary.json")
CONDITION_KINDS = {
    "dense_numerical_estimate", "ritz_lanczos_estimate",
    "high_precision_inverse_norm_estimate", "high_precision_pivot_ratio_estimate",
    "unavailable",
}
STATUS_VALUES = {
    "solved", "empty", "structurally_rank_deficient",
    "numerically_rank_deficient", "ill_conditioned", "breakdown",
    "iteration_limit", "residual_failed", "numerical_failure", "size_limit",
}
SHA64_RE = re.compile(r"[0-9a-f]{64}\Z")
SHA40_RE = re.compile(r"[0-9a-f]{40}\Z")
INT_RE = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")
HEX_RE = re.compile(r"-?0x[0-9a-f]+(?:\.[0-9a-f]+)?p[+-][0-9]+\Z")
DEC_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?\Z")


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


def read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
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


def close_reported(actual: Decimal, expected: Decimal, where: str, *, factor: Decimal = Decimal("5e-11")) -> None:
    scale = max(abs(expected), Decimal("1e-90"))
    require(abs(actual - expected) <= factor * scale + Decimal("1e-90"),
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
    manifest = read_json(bundle / "manifest.json")
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
    actual_files = {path.name for path in bundle.iterdir() if path.is_file()}
    require(actual_files == {*REQUIRED_FILES, "manifest.json"}, "unexpected/missing bundle file")


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


def validate_registered_matrix(systems: Sequence[dict[str, str]], oracle_fixture: bool) -> None:
    if oracle_fixture:
        require(len(systems) == 2, "oracle fixture must contain two systems")
        require(sum(boolean(row["high_precision_applicable"], "hp applicable") for row in systems) == 1,
                "oracle fixture HP selection mismatch")
        require(sum(boolean(row["nullspace_applicable"], "null applicable") for row in systems) == 1,
                "oracle fixture null selection mismatch")
        require(all(boolean(row["assembly_exported"], "assembly exported") for row in systems),
                "oracle fixture must export both systems")
        return
    require(len(systems) == 76, f"expected 76 systems, found {len(systems)}")
    classes = defaultdict(list)
    for row in systems:
        classes[row["case_class"]].append(row)
    require({name: len(rows) for name, rows in classes.items()} == {
        "main": 72, "full_rank_micro": 2, "singular_ppc1": 2,
    }, "76-system case-class matrix mismatch")
    expected_main = {
        (field, time, phase, orientation, level)
        for field in ("translation", "rigid_rotation", "general_affine")
        for time in (0, 4)
        for phase in ("p000", "p049_001_083")
        for orientation in ("p012_sppp", "p210_sppm")
        for level in range(3)
    }
    actual_main = {
        (row["field"], integer(row["time_quanta"], "main time"), row["phase"], row["orientation"], integer(row["level"], "main level"))
        for row in classes["main"]
    }
    require(actual_main == expected_main, "main Cartesian matrix mismatch")
    micro = {(row["phase"], row["orientation"]) for row in classes["full_rank_micro"]}
    require(micro == {("p000", "p012_sppp"), ("p049_001_083", "p210_sppm")}, "micro controls mismatch")
    singular = {row["orientation"] for row in classes["singular_ppc1"]}
    require(singular == {"p012_sppp", "p210_sppm"}, "singular controls mismatch")
    hp = [row for row in systems if boolean(row["high_precision_applicable"], "HP selection")]
    null = [row for row in systems if boolean(row["nullspace_applicable"], "null selection")]
    exported = [row for row in systems if boolean(row["assembly_exported"], "assembly selection")]
    require(len(hp) == 4, "high-precision selection must contain four systems")
    require(len(null) == 10, "nullspace selection must contain ten systems")
    require(len(exported) == 14, "assembly export union must contain fourteen systems")
    require({row["system_id"] for row in exported} == {row["system_id"] for row in hp + null},
            "assembly export is not HP4 union null10")
    require(sum(row["case_class"] == "full_rank_micro" for row in hp) == 2, "both micro controls must be HP selected")
    hp_main = [row for row in hp if row["case_class"] == "main"]
    require({(row["field"], row["time_quanta"], row["level"], row["phase"], row["orientation"]) for row in hp_main} == {
        ("general_affine", "0", "1", "p000", "p012_sppp"),
        ("general_affine", "0", "1", "p049_001_083", "p210_sppm"),
    }, "prior-failure HP selection mismatch")


def validate_system_metadata(systems: Sequence[dict[str, str]], tables: Mapping[str, list[dict[str, str]]], oracle_fixture: bool) -> None:
    seen: set[str] = set()
    raw_names = ("particles.csv", "nodes.csv", "stencils.csv", "matrix.csv", "rhs.csv")
    for row in systems:
        sid = row["system_id"]
        require(sid and sid not in seen, f"duplicate/empty system_id {sid!r}")
        seen.add(sid)
        time_quanta = integer(row["time_quanta"], f"{sid} time_quanta", minimum=0)
        numerator = integer(row["time_quantum_numerator_s"], f"{sid} time numerator", minimum=1)
        denominator = integer(row["time_quantum_denominator_s"], f"{sid} time denominator", minimum=1)
        time_s = binary64(row["time_s"], f"{sid} time_s")
        require(time_s == Decimal.from_float(float(time_quanta * numerator / denominator)), f"{sid}: physical time mismatch")
        for field in ("h_m", "dx_p_m", "kg_per_mass_quantum"):
            require((binary64(row[field], f"{sid} {field}") or Decimal(0)) > 0, f"{sid}: {field} must be positive")
        particle_count = integer(row["particle_count"], f"{sid} particle_count", minimum=1)
        node_count = integer(row["node_count"], f"{sid} node_count", minimum=1)
        integer(row["matrix_nnz"], f"{sid} matrix nnz", minimum=1)
        require(integer(row["rank_upper_bound"], f"{sid} rank upper", minimum=1) == min(particle_count, node_count),
                f"{sid}: rank upper bound mismatch")
        require(integer(row["max_stencil_size"], f"{sid} max stencil", minimum=1) <= node_count, f"{sid}: bad max stencil")
        integer(row["max_particle_contributions_per_node"], f"{sid} max contributions", minimum=1)
        integer(row["max_matrix_row_nnz"], f"{sid} max row nnz", minimum=1)
        require(integer(row["exact_mass_quanta"], f"{sid} mass quanta", minimum=1) == (particle_count if oracle_fixture else 4096),
                f"{sid}: exact mass registration mismatch")
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
    positions = [[binary64(row[field], f"{sid} particle position") or Decimal(0) for field in ("x_m", "y_m", "z_m")] for row in particles]
    particle_velocity = [[binary64(row[field], f"{sid} particle velocity") or Decimal(0) for field in ("vx_m_per_s", "vy_m_per_s", "vz_m_per_s")] for row in particles]
    node_positions = [[binary64(row[field], f"{sid} node position") or Decimal(0) for field in ("x_m", "y_m", "z_m")] for row in nodes]
    analytic = [[binary64(nodes[node][field], f"{sid} analytic g") or Decimal(0) for node in range(n_count)] for field in ("analytic_gx_m_per_s", "analytic_gy_m_per_s", "analytic_gz_m_per_s")]
    A = [[binary64(system[f"a{row}{column}_per_s"], f"{sid} A") or Decimal(0) for column in range(3)] for row in range(3)]
    b = [binary64(system[f"b{component}_m_per_s"], f"{sid} b") or Decimal(0) for component in range(3)]
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
    for component in range(3):
        row = witness_index[(sid, str(component))]
        mg = [sum((M_export.get((i, j), Decimal(0)) * analytic[component][j] for j in range(n_count)), Decimal(0)) for i in range(n_count)]
        mg_residual = l2(mg[i] - rhs_export[(component, i)] for i in range(n_count))
        mg_denominator = l2(sum((abs(M_export.get((i, j), Decimal(0))) * abs(analytic[component][j]) for j in range(n_count)), Decimal(0)) for i in range(n_count)) + l2(rhs_export[(component, i)] for i in range(n_count))
        require(mg_denominator > 0, f"{sid}: zero Mg-q denominator")
        mg_normalized = mg_residual / mg_denominator
        reconstructed = [sum((S[p][node] * analytic[component][node] for node in range(n_count)), Decimal(0)) for p in range(p_count)]
        sg_residual = sum((masses[p] * (reconstructed[p] - particle_velocity[p][component]) ** 2 for p in range(p_count)), Decimal(0)).sqrt()
        sg_denominator = max(sum((masses[p] * particle_velocity[p][component] ** 2 for p in range(p_count)), Decimal(0)).sqrt(), sum(masses, Decimal(0)).sqrt())
        sg_normalized = sg_residual / sg_denominator
        for name, expected in (
            ("mg_minus_q_l2_kg_m_per_s", mg_residual), ("mgq_denominator_kg_m_per_s", mg_denominator),
            ("normalized_mg_minus_q", mg_normalized), ("sg_minus_v_l2_m_per_s", sg_residual),
            ("sgv_denominator_m_per_s_sqrt_kg", sg_denominator), ("normalized_sg_minus_v", sg_normalized),
            ("partition_max_residual", partition), ("linear_reproduction_max_residual_m", linear),
            ("gradient_partition_max_residual_per_m", derivative_partition),
        ):
            close_reported(numeric(row[name], f"{sid} witness {name}") or Decimal(0), expected, f"{sid} witness {name}")
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
            solution = [binary64(nodes[node][("pcg_vhat_x_m_per_s", "pcg_vhat_y_m_per_s", "pcg_vhat_z_m_per_s")[component]], f"{sid} pcg solution") or Decimal(0) for node in range(n_count)]
            validate_solve_metrics(sid, component, solve, solution, analytic[component], particle_velocity, masses, S, M_export, rhs_export, lumped)
        else:
            require(solve["status"] != "solved", f"{sid}: solved PCG lacks solution")
    return {"witness_all": witness_all, "matrix_frobenius": matrix_frobenius, "S": S, "gradients": gradients,
            "masses": masses, "M": M_export, "rhs": rhs_export, "analytic": analytic, "particles": particle_velocity,
            "nodes": nodes, "lumped": lumped}


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
        close_reported(numeric(row[field], f"{sid} solve {field}") or Decimal(0), metrics[name], f"{sid} solve {field}")
    if not high_precision:
        require(row["raw_condition_kind"] in CONDITION_KINDS and row["preconditioned_condition_kind"] in CONDITION_KINDS,
                f"{sid}: invalid condition provenance")
        raw = numeric(row["raw_condition_value"], f"{sid} raw condition", optional=True)
        budget = numeric(row["condition_times_normalized_residual"], f"{sid} condition residual", optional=True)
        if raw is None:
            require(row["raw_condition_kind"] == "unavailable" and budget is None, f"{sid}: unavailable condition contract")
        else:
            require(raw >= 1 and budget is not None, f"{sid}: bad condition estimate")
            close_reported(budget, raw * metrics["normalized_backward"], f"{sid} condition*eta")
        integer(row["iterations"], f"{sid} iterations", minimum=0)
    require(row["status"] in STATUS_VALUES, f"{sid}: invalid solve status")
    return metrics


def validate_high_precision(
    system: Mapping[str, str], data: Mapping[str, Any], hp_index: Mapping[tuple[str, ...], dict[str, str]],
) -> tuple[bool, bool]:
    sid = system["system_id"]
    selected = boolean(system["high_precision_applicable"], f"{sid} HP selected")
    rows = [hp_index.get((sid, str(component))) for component in range(3)]
    if not selected:
        require(all(row is None for row in rows), f"{sid}: unselected high precision rows")
        return False, False
    require(all(row is not None for row in rows), f"{sid}: missing high precision component")
    nodes = data["nodes"]
    available = all(boolean(node["hp_available"], f"{sid} HP available") for node in nodes)
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
        require(integer(row["precision_bits"], f"{sid} HP bits", minimum=100) >= 100, f"{sid}: HP precision not substantially above binary64")
        integer(row["decimal_digits"], f"{sid} HP digits", minimum=30)
        require(row["regularization"] == "none" and not boolean(row["node_dropping"], f"{sid} node drop") and not boolean(row["basis_altered"], f"{sid} basis altered"), f"{sid}: HP modified system")
        require(not boolean(row["promotion_eligible"], f"{sid} HP promotion"), f"{sid}: HP diagnostic marked promotion eligible")
        require(not boolean(row["rank_is_certified"], f"{sid} HP rank certified"), f"{sid}: numerical HP rank mislabeled certified")
        require(row["condition_kind"] in CONDITION_KINDS, f"{sid}: invalid HP condition provenance")
        if row["status"] != "solved":
            require(not available, f"{sid}: failed HP solve exported solution")
            all_pass = False
            continue
        require(available, f"{sid}: solved HP lacks values")
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
    require(set(modes_by_index) == {int(key[1]) for key in metric_index}, f"{sid}: mode/metric key mismatch")
    n_count, p_count = len(data["nodes"]), len(data["S"])
    accepted = visible = 0
    ambiguous = False
    for mode_index, rows in modes_by_index.items():
        require([integer(row["node_index"], f"{sid} mode node") for row in rows] == list(range(n_count)), f"{sid}: incomplete mode vector")
        metric = metric_index[(sid, str(mode_index))]
        require(metric["phase"] == system["phase"] and metric["orientation"] == system["orientation"], f"{sid}: null phase/orientation mismatch")
        require(not boolean(metric["promotion_eligible"], f"{sid} null promotion"), f"{sid}: null diagnostic marked promotion eligible")
        if oracle_fixture:
            require(metric["rank_method"] == "exact_sampling_rref", f"{sid}: oracle rank method mismatch")
        else:
            require(not boolean(metric["rank_is_certified"], f"{sid} rank certified"), f"{sid}: numerical QR rank mislabeled certified")
        z = [binary64(row["z_value_m_per_s"], f"{sid} z") or Decimal(0) for row in rows]
        require(abs(max(abs(value) for value in z) - 1) <= Decimal("1e-14"), f"{sid}: null mode not unit amplitude")
        component = integer(metric["representative_component"], f"{sid} representative component")
        require(0 <= component < 3, f"{sid}: bad representative component")
        alpha = binary64(metric["alpha_m_per_s"], f"{sid} alpha") or Decimal(0)
        representative = [binary64(row["representative_value_m_per_s"], f"{sid} representative") or Decimal(0) for row in rows]
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
            "reconstruction_delta_normalized": recon_delta,
        }
        for field, value in expected.items():
            close_reported(numeric(metric[field], f"{sid} null {field}") or Decimal(0), value, f"{sid} null {field}")
        reported_ratio = numeric(metric["visibility_ratio"], f"{sid} visibility ratio", optional=True)
        if gradient_bound == 0:
            require(metric["visibility_ratio"] == "inf", f"{sid}: zero-bound visibility must be inf")
        else:
            require(reported_ratio is not None, f"{sid}: missing visibility ratio")
            close_reported(reported_ratio, visibility_ratio, f"{sid} visibility ratio")
        require(boolean(metric["gradient_visible"], f"{sid} gradient visible") == gradient_visible, f"{sid}: gradient decision mismatch")
        mode_pass = mz_normalized <= null_limit and sz_normalized <= null_limit and shifted_metrics["normalized_backward"] <= null_limit and recon_delta <= null_limit
        require(boolean(metric["pass"], f"{sid} null pass") == mode_pass, f"{sid}: null acceptance mismatch")
        if metric["representative_kind"] == "diagnostic_pseudoinverse":
            require(not boolean(metric["promotion_eligible"], f"{sid} pseudoinverse promotion"), f"{sid}: pseudoinverse promotion leak")
        if mode_pass:
            accepted += 1
            visible += int(gradient_visible)
        else:
            ambiguous = True
    return accepted, visible, ambiguous


def validate_bundle(bundle: Path, oracle_fixture: bool) -> dict[str, Any]:
    validate_manifest(bundle)
    tables = {name: read_csv(bundle / name, fields) for name, fields in CSV_SCHEMAS.items()}
    summary = read_json(bundle / "summary.json")
    require(summary.get("schema") == SUMMARY_SCHEMA and summary.get("seed") == SEED, "summary schema/seed mismatch")
    require(summary.get("branch") == "projection-exactness-nullspace-lab", "summary branch mismatch")
    if oracle_fixture:
        require(summary.get("mode") == "oracle_fixture" and summary.get("producer") == "python_independent_fixture", "not an oracle fixture")
    else:
        require(summary.get("mode") == "full" and summary.get("producer") == "cpp_projection_exactness_nullspace_lab", "not final C++ evidence")
        require(isinstance(summary.get("source_sha"), str) and SHA40_RE.fullmatch(str(summary["source_sha"])) is not None, "bad source SHA")
        require(summary.get("parent_sha") == SOURCE_PARENT_SHA, "accepted parent SHA mismatch")
    row_counts = summary.get("row_counts")
    require(isinstance(row_counts, dict) and row_counts == {name: len(rows) for name, rows in tables.items()}, "summary row counts mismatch")
    systems = tables["systems.csv"]
    validate_registered_matrix(systems, oracle_fixture)
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
    exported_data: dict[str, dict[str, Any]] = {}
    witness_all = True
    for system in systems:
        if boolean(system["assembly_exported"], "assembly exported"):
            data = validate_exported_system(system, tables, witness_index, solve_index, hp_index)
            exported_data[system["system_id"]] = data
            witness_all &= data["witness_all"]
        else:
            for component in range(3):
                row = witness_index[(system["system_id"], str(component))]
                witness_all &= boolean(row["pass"], f"{system['system_id']} witness pass")
                require(solve_index[(system["system_id"], str(component))]["status"] in STATUS_VALUES, "invalid nonexported solve status")
                require((system["system_id"], str(component)) not in hp_index, "nonexported system cannot be HP selected")
    hp_all = True
    contradiction = False
    pcg_miss = False
    for system in systems:
        sid = system["system_id"]
        if boolean(system["high_precision_applicable"], f"{sid} HP"):
            require(sid in exported_data, f"{sid}: HP system lacks export")
            passed, contradicted = validate_high_precision(system, exported_data[sid], hp_index)
            hp_all &= passed
            contradiction |= contradicted
            for component in range(3):
                solve = solve_index[(sid, str(component))]
                forward = numeric(solve["normalized_forward_error"], f"{sid} PCG forward", optional=True)
                recon = numeric(solve["normalized_reconstruction_error"], f"{sid} PCG recon", optional=True)
                pcg_miss |= (forward is not None and forward > FORWARD_LIMIT) or (recon is not None and recon > FORWARD_LIMIT)
        else:
            require(not any(key[0] == sid for key in hp_index), f"{sid}: unexpected HP rows")
    mode_by_system: dict[str, list[dict[str, str]]] = defaultdict(list)
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
            accepted, visible, ambiguous = validate_nullspace(system, exported_data[sid], mode_by_system[sid], metric_by_system[sid], oracle_fixture)
            accepted_modes += accepted
            visible_modes += visible
            null_ambiguous |= ambiguous or accepted == 0
        else:
            require(not mode_by_system[sid] and not metric_by_system[sid], f"{sid}: unexpected null rows")
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
    require(summary.get("pcg_miss_observed") == pcg_miss, "summary PCG miss mismatch")
    require(summary.get("singular_center_invariant") == (accepted_modes > 0 and not null_ambiguous), "summary null invariance mismatch")
    require(summary.get("singular_gradient_visible") == (visible_modes > 0), "summary gradient visibility mismatch")
    require(summary.get("diagnostic_pseudoinverse_promotion_eligible") is False, "pseudoinverse promotion gate mismatch")
    require(summary.get("decision") == decision, f"bounded decision mismatch: {summary.get('decision')} != {decision}")
    require(summary.get("promotion") is False, "projection method was promoted")
    return {"systems": len(systems), "exported": len(exported_data), "accepted_modes": accepted_modes,
            "visible_modes": visible_modes, "decision": decision}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--oracle-fixture", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = validate_bundle(args.bundle.resolve(), args.oracle_fixture)
        if args.compare:
            other = validate_bundle(args.compare.resolve(), args.oracle_fixture)
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
