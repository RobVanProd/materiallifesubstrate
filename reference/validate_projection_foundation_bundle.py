#!/usr/bin/env python3
"""Independent validator for an MLS Projection Foundation evidence bundle.

The producer is C++; this validator deliberately shares no implementation
code with it.  It reconstructs the frozen 330-row matrix, derived-table keys,
registered decisions, failure rows, checkpoint evidence, and manifest hashes.
Passing validates bundle consistency only.  It is not a mechanics result and
cannot promote a transfer candidate.  In particular, it does not recompute
floating trajectories from checkpoints; it checks the registered matrix and
cross-table decisions.  The exact-rational oracle is a separate implementation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SEED = 260828
SUMMARY_SCHEMA = "mls.projection-foundation.summary.v2"
MANIFEST_SCHEMA = "mls.projection-foundation.manifest.v1"
ORACLE_SHA256 = "7f3119d609bf022fa31bfc5bf01a6c15189aaede7e35f9cfad13f4c275fae4bc"
PARENT_SHA = "aa084440fcd859b4f3416b21623cc3ac0c5b3e16"
PARENT_TAG = "moving-apic-limit-lab-evidence-v1"

CANDIDATES = ("lumped_PIC", "full_consistent", "FMPM_1", "FMPM_2", "FMPM_3", "FMPM_4")
FMPM = CANDIDATES[2:]
FIELDS = ("translation", "rigid_rotation", "general_affine", "smooth_non_affine")
AFFINE_FIELDS = FIELDS[:3]
PHASES = ("p000", "p049_001_083")
ORIENTATIONS = ("p012_sppp", "p210_sppm")
METRICS = ("material_velocity", "trajectory", "linear_momentum", "orbital_angular")
DISTANCE_METRICS = ("grid_distance_full", "particle_distance_full")
SOLVED = {"solved", "empty"}
STATUSES = SOLVED | {
    "structurally_rank_deficient", "numerically_rank_deficient",
    "ill_conditioned", "breakdown", "iteration_limit", "residual_failed",
    "numerical_overflow",
}

REQUIRED_FILES = (
    "checkpoint.csv", "convergence.csv", "exact_angular_control.csv",
    "hard_gates.csv", "main_raw.csv", "order_to_full.csv",
    "orientation_sensitivity.csv", "phase_sensitivity.csv", "ppc_raw.csv",
    "solver_failures.csv", "summary.json",
)

RAW_FIELDS = tuple((
    "mode,seed,scope,candidate,field,phase,orientation,level,domain_min_m,domain_max_m,"
    "density_kg_per_m3,registered_total_mass_kg,cfl_u_ref_dt_over_h,h_m,dt_s,dt_quanta,steps,"
    "cells_per_axis,nominal_domain_grid_cell_count,particles_per_axis,particle_count,particles_per_cell,particle_spacing_m,"
    "mass_quanta_per_particle,kg_per_mass_quantum,expected_mass_quanta,exact_mass_before,"
    "exact_mass_after,expected_elapsed_quanta,observed_elapsed_quanta,exact_mass_ok,"
    "exact_clock_ok,status,full_reference_status,full_reference_available,"
    "candidate_solve_residual_applicable,full_reference_solve_residual_applicable,"
    "particle_count_diag,"
    "active_node_count,shape_entry_count,matrix_nonzero_count,node_order_digest,"
    "structural_rank_upper_bound,numerical_rank_estimate,numerical_rank_method,"
    "numerical_rank_is_estimated,rank_certified,condition_estimated,"
    "smallest_spectral_or_pivot_value,"
    "largest_spectral_or_pivot_value,raw_condition_estimate,"
    "preconditioned_condition_estimate,matrix_symmetry_relative_residual,"
    "row_sum_relative_residual,partition_unity_max_residual,"
    "linear_reproduction_max_residual_m,grid_mass_relative_error,"
    "max_projection_residual,full_reference_max_projection_residual,"
    "fmpm_residual_identity_applicable,fmpm_residual_identity,material_velocity_error,"
    "trajectory_error,linear_momentum_error,orbital_angular_error,"
    "center_kinetic_relative_change,consistent_grid_quadratic_energy_applicable,"
    "consistent_grid_quadratic_energy_j,numerical_projection_energy_residual_applicable,"
    "max_abs_numerical_projection_energy_residual_j,"
    "particle_reconstruction_error,affine_grid_representation_error,"
    "grid_distance_full,particle_distance_full,pic_identity_error,id_error_count,"
    "nonfinite_count,candidate_termination_reason,full_reference_termination_reason,"
    "checkpoint_roundtrip_ok,checkpoint_replay_ok,"
    "initial_checkpoint_sha256,terminal_checkpoint_sha256"
).split(","))
SENSITIVITY_FIELDS = tuple((
    "mode,seed,kind,candidate,field,fixed_axis,level,metric,value,hard_floor,"
    "finest_ceiling,applicable"
).split(","))
CONVERGENCE_FIELDS = tuple((
    "mode,seed,scope,candidate,field,phase,orientation,metric,error_level_0,"
    "error_level_1,error_level_2,hard_floor,finest_ceiling,contraction_01,"
    "contraction_12,endpoint_contraction,pass,reason"
).split(","))
ORDER_FIELDS = tuple((
    "mode,seed,scope,field,phase,orientation,level,metric,k1,k2,k3,k4,"
    "applicable,successor_nonincrease,k4_half_k1,pass,reason"
).split(","))
GATE_FIELDS = tuple((
    "mode,seed,scope,candidate,field,phase,orientation,level,gate,applicable,"
    "value,tolerance,pass"
).split(","))
SOLVER_FIELDS = tuple((
    "mode,seed,scope,candidate,field,phase,orientation,level,status,"
    "full_reference_status,candidate_failed,full_reference_failed,particle_count,"
    "active_node_count,structural_rank_upper_bound,numerical_rank_estimate,"
    "rank_method,rank_is_estimated,rank_certified,condition_estimated,"
    "raw_condition_estimate,preconditioned_condition_estimate,"
    "candidate_residual_applicable,candidate_max_normalized_residual,"
    "full_reference_residual_applicable,full_reference_max_normalized_residual,"
    "candidate_termination_reason,full_reference_termination_reason"
).split(","))
CHECKPOINT_FIELDS = tuple((
    "mode,seed,scope,candidate,field,phase,orientation,level,roundtrip_exact,"
    "replay_exact,initial_sha256,terminal_sha256,pass"
).split(","))
EXACT_FIELDS = tuple((
    "mode,seed,candidate,condition_one_exact,angular_delta_exact,"
    "linear_momentum_exact,oracle_result_sha256,role"
).split(","))

GATES = (
    "exact_mass", "exact_clock", "identity_integrity", "nonfinite_physical_output",
    "partition_unity", "linear_reproduction", "matrix_symmetry", "row_sum_identity",
    "grid_mass", "linear_momentum", "full_solve_residual", "full_raw_condition",
    "full_preconditioned_condition", "full_affine_particle_reconstruction",
    "full_affine_grid_representation", "full_affine_orbital",
    "fmpm_residual_identity", "fmpm1_pic_identity",
    "checkpoint_roundtrip_replay", "represented_affine_energy_diagnostic",
)

INT_RE = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")


class InvalidBundle(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidBundle(message)


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
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
        raise InvalidBundle(f"cannot read CSV {path.name}: {error}") from error
    for number, row in enumerate(rows, 2):
        require(None not in row, f"{path.name}:{number}: excess columns")
        require(all(value is not None for value in row.values()), f"{path.name}:{number}: missing column")
    return rows


def integer(value: str, where: str) -> int:
    require(INT_RE.fullmatch(value) is not None, f"{where}: noncanonical integer {value!r}")
    return int(value)


def boolean(value: str, where: str) -> bool:
    require(value in {"true", "false"}, f"{where}: expected true/false, got {value!r}")
    return value == "true"


def number(value: str, where: str, *, optional: bool = False, finite: bool = True) -> float | None:
    if value == "NA":
        require(optional, f"{where}: unexpected NA")
        return None
    try:
        result = float(value)
    except ValueError as error:
        raise InvalidBundle(f"{where}: invalid number {value!r}") from error
    require(not finite or math.isfinite(result), f"{where}: nonfinite number")
    return result


def same_number(actual: str, expected: float | None, where: str) -> None:
    observed = number(actual, where, optional=True)
    if expected is None:
        require(observed is None, f"{where}: expected NA")
    else:
        require(observed is not None and observed == expected, f"{where}: {observed!r} != {expected!r}")


def key(row: Mapping[str, str]) -> tuple[str, str, str, str, str, int]:
    return (row["scope"], row["candidate"], row["field"], row["phase"],
            row["orientation"], integer(row["level"], "level"))


def expected_raw(mode: str) -> dict[tuple[str, str, str, str, str, int], dict[str, float | int]]:
    main_levels = (
        dict(level=0, h_m=0.5, dt_s=1.0 / 40.0, dt_quanta=4, steps=1,
             cells_per_axis=2, particles_per_axis=4, particles_per_cell=8,
             particle_spacing_m=0.25, mass_quanta_per_particle=64),
        dict(level=1, h_m=0.25, dt_s=1.0 / 80.0, dt_quanta=2, steps=2,
             cells_per_axis=4, particles_per_axis=8, particles_per_cell=8,
             particle_spacing_m=0.125, mass_quanta_per_particle=8),
        dict(level=2, h_m=0.125, dt_s=1.0 / 160.0, dt_quanta=1, steps=4,
             cells_per_axis=8, particles_per_axis=16, particles_per_cell=8,
             particle_spacing_m=0.0625, mass_quanta_per_particle=1),
    )
    result: dict[tuple[str, str, str, str, str, int], dict[str, float | int]] = {}
    if mode == "smoke":
        for candidate in CANDIDATES:
            cfg = dict(main_levels[0])
            result[("main", candidate, "general_affine", "p000", "p012_sppp", 0)] = cfg
        return result
    for field in FIELDS:
        for candidate in CANDIDATES:
            for phase in PHASES:
                for orientation in ORIENTATIONS:
                    for cfg0 in main_levels:
                        cfg = dict(cfg0)
                        result[("main", candidate, field, phase, orientation, int(cfg["level"]))] = cfg
    ppc_levels = (
        (0, 1, 4, 0.25, 64), (1, 8, 8, 0.125, 8), (2, 64, 16, 0.0625, 1),
    )
    for field in ("general_affine", "smooth_non_affine"):
        for candidate in CANDIDATES:
            for level, ppc, axis, spacing, mass in ppc_levels:
                result[("ppc", candidate, field, "p049_001_083", "p210_sppm", level)] = {
                    "level": level, "h_m": 0.25, "dt_s": 1.0 / 80.0,
                    "dt_quanta": 2, "steps": 2, "cells_per_axis": 4,
                    "particles_per_axis": axis, "particles_per_cell": ppc,
                    "particle_spacing_m": spacing, "mass_quanta_per_particle": mass,
                }
    return result


def index_unique(rows: Iterable[dict[str, str]], name: str) -> dict[tuple[str, str, str, str, str, int], dict[str, str]]:
    result: dict[tuple[str, str, str, str, str, int], dict[str, str]] = {}
    for row in rows:
        row_key = key(row)
        require(row_key not in result, f"{name}: duplicate row key {row_key}")
        result[row_key] = row
    return result


def validate_raw(rows: list[dict[str, str]], scope: str, mode: str,
                 expected: Mapping[tuple[str, str, str, str, str, int], Mapping[str, float | int]]) -> dict[tuple[str, str, str, str, str, int], dict[str, str]]:
    indexed = index_unique(rows, f"{scope}_raw")
    expected_scope = {k: v for k, v in expected.items() if k[0] == scope}
    require(set(indexed) == set(expected_scope), f"{scope}_raw: configuration matrix mismatch")
    for row_key, row in indexed.items():
        where = f"{scope}_raw:{row_key}"
        cfg = expected_scope[row_key]
        require(row["mode"] == mode, f"{where}: mode mismatch")
        require(integer(row["seed"], where) == SEED, f"{where}: seed mismatch")
        require(row["candidate"] in CANDIDATES and row["field"] in FIELDS, f"{where}: enum mismatch")
        for name in ("level", "dt_quanta", "steps", "cells_per_axis", "particles_per_axis",
                     "particles_per_cell", "mass_quanta_per_particle"):
            require(integer(row[name], where) == cfg[name], f"{where}: {name} drift")
        for name in ("h_m", "dt_s", "particle_spacing_m"):
            require(number(row[name], where) == cfg[name], f"{where}: {name} drift")
        domain_min = number(row["domain_min_m"], where)
        domain_max = number(row["domain_max_m"], where)
        density = number(row["density_kg_per_m3"], where)
        registered_mass = number(row["registered_total_mass_kg"], where)
        observed_cfl = number(row["cfl_u_ref_dt_over_h"], where)
        require(domain_min == -0.5, f"{where}: domain minimum")
        require(domain_max == 0.5, f"{where}: domain maximum")
        require(density == 1.0, f"{where}: density")
        require(registered_mass == 1.0, f"{where}: registered total mass")
        require(observed_cfl == 0.125, f"{where}: CFL-like ratio")
        assert domain_min is not None and domain_max is not None
        assert density is not None and registered_mass is not None
        assert observed_cfl is not None
        extent = domain_max - domain_min
        axis = int(cfg["particles_per_axis"])
        cells = int(cfg["cells_per_axis"])
        particle_count = axis ** 3
        nominal_grid_cell_count = integer(row["nominal_domain_grid_cell_count"], where)
        require(nominal_grid_cell_count == cells ** 3,
                f"{where}: nominal grid-cell count relation")
        require(cells * float(cfg["h_m"]) == extent,
                f"{where}: grid extent relation")
        require(axis * float(cfg["particle_spacing_m"]) == extent,
                f"{where}: particle extent relation")
        require(axis % cells == 0 and (axis // cells) ** 3 == int(cfg["particles_per_cell"]),
                f"{where}: particles-per-cell relation")
        require(observed_cfl == 2.5 * float(cfg["dt_s"]) / float(cfg["h_m"]),
                f"{where}: CFL reconstruction relation")
        require(integer(row["particle_count"], where) == particle_count, f"{where}: particle count")
        kg_per_quantum = number(row["kg_per_mass_quantum"], where)
        require(kg_per_quantum == 1.0 / 4096.0, f"{where}: mass quantum")
        require(integer(row["expected_mass_quanta"], where) == 4096, f"{where}: expected mass")
        assert kg_per_quantum is not None
        require(registered_mass == extent ** 3 * density,
                f"{where}: density/domain mass relation")
        require(registered_mass == 4096 * kg_per_quantum,
                f"{where}: exact-quantum total-mass relation")
        require(registered_mass == particle_count * int(cfg["mass_quanta_per_particle"]) *
                kg_per_quantum, f"{where}: particle mass relation")
        before = integer(row["exact_mass_before"], where)
        after = integer(row["exact_mass_after"], where)
        mass_ok = before == 4096 and after == 4096
        require(boolean(row["exact_mass_ok"], where) == mass_ok, f"{where}: exact mass flag")
        require(integer(row["expected_elapsed_quanta"], where) == 4, f"{where}: horizon")
        observed_clock = integer(row["observed_elapsed_quanta"], where)
        require(boolean(row["exact_clock_ok"], where) == (observed_clock == 4), f"{where}: clock flag")
        require(row["status"] in STATUSES and row["full_reference_status"] in STATUSES,
                f"{where}: status enum")
        require(boolean(row["full_reference_available"], where) ==
                (row["full_reference_status"] in SOLVED), f"{where}: full-reference flag")
        require(integer(row["particle_count_diag"], where) == particle_count, f"{where}: diagnostic particle count")
        for name in ("active_node_count", "shape_entry_count", "matrix_nonzero_count",
                     "node_order_digest", "structural_rank_upper_bound", "numerical_rank_estimate",
                     "id_error_count", "nonfinite_count"):
            require(integer(row[name], where) >= 0, f"{where}: negative {name}")
        optional_numbers = {
            "max_projection_residual", "full_reference_max_projection_residual",
            "fmpm_residual_identity", "consistent_grid_quadratic_energy_j",
            "max_abs_numerical_projection_energy_residual_j",
            "affine_grid_representation_error", "grid_distance_full",
            "particle_distance_full", "pic_identity_error",
            "material_velocity_error", "trajectory_error", "linear_momentum_error",
            "orbital_angular_error", "center_kinetic_relative_change",
        }
        numeric_diagnostics = (
            "smallest_spectral_or_pivot_value", "largest_spectral_or_pivot_value",
            "raw_condition_estimate", "preconditioned_condition_estimate",
            "matrix_symmetry_relative_residual", "row_sum_relative_residual",
            "partition_unity_max_residual", "linear_reproduction_max_residual_m",
            "grid_mass_relative_error", "max_projection_residual",
            "full_reference_max_projection_residual", "fmpm_residual_identity",
            "material_velocity_error", "trajectory_error", "linear_momentum_error",
            "orbital_angular_error", "center_kinetic_relative_change",
            "consistent_grid_quadratic_energy_j",
            "max_abs_numerical_projection_energy_residual_j",
            "particle_reconstruction_error", "affine_grid_representation_error",
            "grid_distance_full", "particle_distance_full", "pic_identity_error",
        )
        for name in numeric_diagnostics:
            number(row[name], f"{where}:{name}", optional=name in optional_numbers, finite=True)
        boolean_diagnostics = (
            "checkpoint_roundtrip_ok", "checkpoint_replay_ok",
            "numerical_rank_is_estimated", "rank_certified", "condition_estimated",
            "candidate_solve_residual_applicable",
            "full_reference_solve_residual_applicable",
            "fmpm_residual_identity_applicable",
            "consistent_grid_quadratic_energy_applicable",
            "numerical_projection_energy_residual_applicable",
        )
        for name in boolean_diagnostics:
            boolean(row[name], f"{where}:{name}")
        applicability_pairs = (
            ("candidate_solve_residual_applicable", "max_projection_residual"),
            ("full_reference_solve_residual_applicable", "full_reference_max_projection_residual"),
            ("fmpm_residual_identity_applicable", "fmpm_residual_identity"),
            ("consistent_grid_quadratic_energy_applicable", "consistent_grid_quadratic_energy_j"),
            ("numerical_projection_energy_residual_applicable", "max_abs_numerical_projection_energy_residual_j"),
        )
        for flag, value in applicability_pairs:
            require(boolean(row[flag], where) == (row[value] != "NA"),
                    f"{where}: {flag}/{value} applicability mismatch")
        identity_clean = integer(row["id_error_count"], where) == 0
        for name in ("material_velocity_error", "trajectory_error", "linear_momentum_error",
                     "orbital_angular_error", "center_kinetic_relative_change"):
            require((row[name] != "NA") == identity_clean,
                    f"{where}: {name} must be NA exactly when identity is invalid")
        require(row["candidate_termination_reason"] != "" and
                row["full_reference_termination_reason"] != "", f"{where}: missing termination trace")
        require(SHA_RE.fullmatch(row["initial_checkpoint_sha256"]) is not None, f"{where}: initial SHA")
        require(SHA_RE.fullmatch(row["terminal_checkpoint_sha256"]) is not None, f"{where}: terminal SHA")
        require(row["numerical_rank_method"] != "", f"{where}: rank-method traceability")
        if boolean(row["rank_certified"], where):
            require(not boolean(row["numerical_rank_is_estimated"], where),
                    f"{where}: certified rank cannot be labeled estimated")
    return indexed


def validate_exact(rows: list[dict[str, str]], mode: str) -> None:
    angular = {
        "lumped_PIC": "-921401/1895040", "full_consistent": "0/1",
        "FMPM_1": "-921401/1895040", "FMPM_2": "-91802668277/359117660160",
        "FMPM_3": "-9282539024459489/68054233070960640",
        "FMPM_4": "-953607378962630674973/12896549383879325122560",
    }
    require(len(rows) == 6, "exact control: expected six rows")
    seen: set[str] = set()
    for row in rows:
        candidate = row["candidate"]
        require(candidate in CANDIDATES and candidate not in seen, "exact control: candidate set")
        seen.add(candidate)
        require(row["mode"] == mode and integer(row["seed"], "exact seed") == SEED, "exact control provenance")
        require(row["condition_one_exact"] == "2514/343", "exact condition fingerprint")
        require(row["angular_delta_exact"] == angular[candidate], "exact angular fingerprint")
        require(row["linear_momentum_exact"] == "true", "exact linear result")
        require(row["oracle_result_sha256"] == ORACLE_SHA256, "exact oracle SHA")
        role = ("exact_full_recovery" if candidate == "full_consistent" else
                "negative_control_identity" if candidate in {"lumped_PIC", "FMPM_1"} else
                "finite_order_fingerprint")
        require(row["role"] == role, "exact role mismatch")


def sensitivity_keys(kind: str) -> set[tuple[str, str, str, int, str]]:
    result: set[tuple[str, str, str, int, str]] = set()
    if kind == "phase":
        for candidate in CANDIDATES:
            for field in FIELDS:
                for fixed in ORIENTATIONS:
                    for level in range(3):
                        metrics = ("material_velocity", "trajectory") + (
                            DISTANCE_METRICS if candidate in FMPM else ())
                        for metric in metrics:
                            result.add((candidate, field, fixed, level, metric))
    else:
        for candidate in CANDIDATES:
            for field in FIELDS:
                for fixed in PHASES:
                    for level in range(3):
                        metrics = ("material_velocity", "trajectory") + (
                            DISTANCE_METRICS if candidate in FMPM else ())
                        for metric in metrics:
                            result.add((candidate, field, fixed, level, metric))
    return result


def validate_sensitivity(rows: list[dict[str, str]], kind: str, mode: str,
                         raw: Mapping[tuple[str, str, str, str, str, int], dict[str, str]]) -> dict[tuple[str, str, str, int, str], dict[str, str]]:
    if mode == "smoke":
        require(not rows, f"{kind} sensitivity must be empty in smoke")
        return {}
    indexed: dict[tuple[str, str, str, int, str], dict[str, str]] = {}
    for row in rows:
        where = f"{kind} sensitivity"
        require(row["mode"] == mode and integer(row["seed"], where) == SEED and row["kind"] == kind,
                f"{where}: provenance")
        k = (row["candidate"], row["field"], row["fixed_axis"],
             integer(row["level"], where), row["metric"])
        require(k not in indexed, f"{where}: duplicate {k}")
        indexed[k] = row
        candidate, field, fixed, level, _ = k
        if kind == "phase":
            lhs = raw[("main", candidate, field, "p000", fixed, level)]
            rhs = raw[("main", candidate, field, "p049_001_083", fixed, level)]
        else:
            lhs = raw[("main", candidate, field, fixed, "p012_sppp", level)]
            rhs = raw[("main", candidate, field, fixed, "p210_sppm", level)]
        applicable = (lhs["status"] in SOLVED and rhs["status"] in SOLVED and
                      integer(lhs["id_error_count"], where) == 0 and
                      integer(rhs["id_error_count"], where) == 0)
        expected_distance_value: float | None = None
        if row["metric"] in DISTANCE_METRICS:
            column = row["metric"]
            lhs_value = number(lhs[column], where, optional=True)
            rhs_value = number(rhs[column], where, optional=True)
            applicable = applicable and lhs_value is not None and rhs_value is not None
            if applicable:
                expected_distance_value = abs(float(lhs_value) - float(rhs_value))
        require(boolean(row["applicable"], where) == applicable, f"{where}: applicability")
        require((row["value"] != "NA") == applicable, f"{where}: explicit NA")
        require(number(row["hard_floor"], where) == 5.0e-10, f"{where}: floor")
        require(number(row["finest_ceiling"], where) == 5.0e-3, f"{where}: ceiling")
        observed_value = number(row["value"], where, optional=True)
        if row["metric"] in DISTANCE_METRICS:
            require(observed_value == expected_distance_value,
                    f"{where}: distance sensitivity source mismatch")
    require(set(indexed) == sensitivity_keys(kind), f"{kind} sensitivity: family matrix mismatch")
    return indexed


def tolerances(field: str, metric: str) -> tuple[float, float]:
    if metric == "material_velocity":
        return (2.0e-8, 2.0e-2) if field == "smooth_non_affine" else (5.0e-10, 5.0e-8)
    if metric == "trajectory":
        return (2.0e-8, 2.0e-3) if field == "smooth_non_affine" else (5.0e-10, 5.0e-8)
    if metric == "linear_momentum":
        return 2.0e-11, 2.0e-9
    if metric == "orbital_angular":
        return 5.0e-10, 5.0e-5
    if metric in DISTANCE_METRICS:
        return 5.0e-10, 2.0e-2
    raise InvalidBundle(f"unknown metric {metric}")


def convergence_decision(values: Sequence[float | None], floor: float, ceiling: float) -> tuple[bool, str]:
    if any(value is None or not math.isfinite(value) or value < 0.0 for value in values):
        return False, "missing_failed_or_nonfinite_level"
    e0, e1, e2 = (float(value) for value in values)
    if e0 <= floor and e1 <= floor and e2 <= floor:
        return True, "all_below_hard_floor"
    passed = (e1 <= 0.80 * e0 + 5.0e-14 and e2 <= 0.80 * e1 + 5.0e-14 and
              e2 <= 0.40 * e0 + 5.0e-14 and e2 <= ceiling)
    return passed, "contraction_and_finest_ceiling" if passed else "convergence_rule_failed"


def ratio(next_value: float | None, previous: float | None) -> float | None:
    if next_value is None or previous is None:
        return None
    if previous == 0.0:
        return 0.0 if next_value == 0.0 else None
    return next_value / previous


def raw_metric(row: Mapping[str, str], metric: str) -> float | None:
    if row["status"] not in SOLVED:
        return None
    column = {"material_velocity": "material_velocity_error", "trajectory": "trajectory_error",
              "linear_momentum": "linear_momentum_error", "orbital_angular": "orbital_angular_error",
              "grid_distance_full": "grid_distance_full", "particle_distance_full": "particle_distance_full"}[metric]
    return number(row[column], f"raw metric {metric}", optional=True)


def expected_convergence(mode: str,
                         raw: Mapping[tuple[str, str, str, str, str, int], dict[str, str]],
                         phase: Mapping[tuple[str, str, str, int, str], dict[str, str]],
                         orientation: Mapping[tuple[str, str, str, int, str], dict[str, str]]) -> dict[tuple[str, str, str, str, str, str], tuple[list[float | None], float, float]]:
    result: dict[tuple[str, str, str, str, str, str], tuple[list[float | None], float, float]] = {}
    if mode == "smoke":
        return result
    for candidate in CANDIDATES:
        for field in FIELDS:
            for ph in PHASES:
                for orient in ORIENTATIONS:
                    for metric in METRICS + (DISTANCE_METRICS if candidate in FMPM else ()):
                        values = [raw_metric(raw[("main", candidate, field, ph, orient, level)], metric)
                                  for level in range(3)]
                        result[("main", candidate, field, ph, orient, metric)] = (*[values], *tolerances(field, metric))
    for candidate in CANDIDATES:
        for field in ("general_affine", "smooth_non_affine"):
            for metric in METRICS + (DISTANCE_METRICS if candidate in FMPM else ()):
                values = [raw_metric(raw[("ppc", candidate, field, "p049_001_083", "p210_sppm", level)], metric)
                          for level in range(3)]
                result[("ppc", candidate, field, "p049_001_083", "p210_sppm", metric)] = (*[values], *tolerances(field, metric))
    for (candidate, field, fixed, _level, metric) in phase:
        k = ("phase", candidate, field, "phase_pair", fixed, metric)
        if k not in result:
            values = [number(phase[(candidate, field, fixed, level, metric)]["value"], "phase value", optional=True)
                      for level in range(3)]
            result[k] = (values, 5.0e-10, 5.0e-3)
    for (candidate, field, fixed, _level, metric) in orientation:
        k = ("orientation", candidate, field, fixed, "orientation_pair", metric)
        if k not in result:
            values = [number(orientation[(candidate, field, fixed, level, metric)]["value"], "orientation value", optional=True)
                      for level in range(3)]
            result[k] = (values, 5.0e-10, 5.0e-3)
    return result


def validate_convergence(rows: list[dict[str, str]], mode: str,
                         expected: Mapping[tuple[str, str, str, str, str, str], tuple[list[float | None], float, float]]) -> dict[tuple[str, str, str, str, str, str], dict[str, str]]:
    indexed: dict[tuple[str, str, str, str, str, str], dict[str, str]] = {}
    for row in rows:
        where = "convergence"
        require(row["mode"] == mode and integer(row["seed"], where) == SEED, "convergence provenance")
        k = (row["scope"], row["candidate"], row["field"], row["phase"], row["orientation"], row["metric"])
        require(k not in indexed, f"convergence duplicate {k}")
        indexed[k] = row
    require(set(indexed) == set(expected), "convergence family matrix mismatch")
    for k, (values, floor, ceiling) in expected.items():
        row = indexed[k]
        observed_values = [number(row[f"error_level_{level}"], f"convergence {k}", optional=True)
                           for level in range(3)]
        require(observed_values == values, f"convergence {k}: source values mismatch")
        require(number(row["hard_floor"], f"convergence {k}") == floor, f"convergence {k}: floor")
        require(number(row["finest_ceiling"], f"convergence {k}") == ceiling, f"convergence {k}: ceiling")
        expected_ratios = (ratio(values[1], values[0]), ratio(values[2], values[1]), ratio(values[2], values[0]))
        for column, expected_ratio in zip(("contraction_01", "contraction_12", "endpoint_contraction"), expected_ratios):
            observed = number(row[column], f"convergence {k}:{column}", optional=True)
            require(observed == expected_ratio, f"convergence {k}: ratio mismatch")
        passed, reason = convergence_decision(values, floor, ceiling)
        require(boolean(row["pass"], f"convergence {k}") == passed and row["reason"] == reason,
                f"convergence {k}: decision mismatch")
    return indexed


def expected_orders(mode: str) -> set[tuple[str, str, str, str, int, str]]:
    if mode == "smoke":
        return {("main", "general_affine", "p000", "p012_sppp", 0, metric) for metric in DISTANCE_METRICS}
    result = {("main", field, phase, orientation, level, metric)
              for field in FIELDS for phase in PHASES for orientation in ORIENTATIONS
              for level in range(3) for metric in DISTANCE_METRICS}
    result |= {("ppc", field, "p049_001_083", "p210_sppm", level, metric)
               for field in ("general_affine", "smooth_non_affine")
               for level in range(3) for metric in DISTANCE_METRICS}
    return result


def validate_orders(rows: list[dict[str, str]], mode: str,
                    raw: Mapping[tuple[str, str, str, str, str, int], dict[str, str]]) -> dict[tuple[str, str, str, str, int, str], dict[str, str]]:
    indexed: dict[tuple[str, str, str, str, int, str], dict[str, str]] = {}
    for row in rows:
        where = "order"
        require(row["mode"] == mode and integer(row["seed"], where) == SEED, "order provenance")
        k = (row["scope"], row["field"], row["phase"], row["orientation"], integer(row["level"], where), row["metric"])
        require(k not in indexed, f"order duplicate {k}")
        indexed[k] = row
    require(set(indexed) == expected_orders(mode), "order family matrix mismatch")
    for k, row in indexed.items():
        scope, field, phase, orientation, level, metric = k
        values = [raw_metric(raw[(scope, candidate, field, phase, orientation, level)], metric) for candidate in FMPM]
        observed = [number(row[f"k{order}"], f"order {k}", optional=True) for order in range(1, 5)]
        require(observed == values, f"order {k}: source values mismatch")
        applicable = all(value is not None and math.isfinite(value) and value >= 0.0 for value in values)
        successor = applicable and all(float(values[i]) <= float(values[i - 1]) + 5.0e-13 for i in range(1, 4))
        half = applicable and float(values[3]) <= 0.50 * float(values[0]) + 5.0e-13
        all_small = applicable and all(float(value) <= 5.0e-10 for value in values)
        passed = applicable and (all_small or (successor and half))
        reason = ("full_reference_or_order_unavailable" if not applicable else
                  "all_orders_below_floor" if all_small else
                  "monotone_and_half_at_k4" if passed else "order_rule_failed")
        require(boolean(row["applicable"], f"order {k}") == applicable, f"order {k}: applicability")
        require(boolean(row["successor_nonincrease"], f"order {k}") == successor, f"order {k}: monotonicity")
        require(boolean(row["k4_half_k1"], f"order {k}") == half, f"order {k}: half rule")
        require(boolean(row["pass"], f"order {k}") == passed and row["reason"] == reason,
                f"order {k}: decision")
    return indexed


def gate_expectation(raw: Mapping[str, str], gate: str) -> tuple[bool, float | None, float | None, bool]:
    candidate, field, status = raw["candidate"], raw["field"], raw["status"]
    is_full, is_fmpm, is_fmpm1 = candidate == "full_consistent", candidate in FMPM, candidate == "FMPM_1"
    full_solved, affine = is_full and status in SOLVED, field in AFFINE_FIELDS
    def observed(column: str) -> float | None:
        return number(raw[column], f"gate source {gate}", optional=True)

    def within(value: float | None, tolerance: float) -> bool:
        return value is not None and math.isfinite(value) and value <= tolerance

    simple = {
        "exact_mass": (0.0 if boolean(raw["exact_mass_ok"], "raw") else 1.0, 0.0,
                       boolean(raw["exact_mass_ok"], "raw")),
        "exact_clock": (0.0 if boolean(raw["exact_clock_ok"], "raw") else 1.0, 0.0,
                        boolean(raw["exact_clock_ok"], "raw")),
        "identity_integrity": (float(integer(raw["id_error_count"], "raw")), 0.0,
                               integer(raw["id_error_count"], "raw") == 0),
        "nonfinite_physical_output": (float(integer(raw["nonfinite_count"], "raw")), 0.0,
                                      integer(raw["nonfinite_count"], "raw") == 0),
        "partition_unity": (observed("partition_unity_max_residual"), 5.0e-14,
                            within(observed("partition_unity_max_residual"), 5.0e-14)),
        "linear_reproduction": (observed("linear_reproduction_max_residual_m"), 5.0e-13,
                                within(observed("linear_reproduction_max_residual_m"), 5.0e-13)),
        "matrix_symmetry": (observed("matrix_symmetry_relative_residual"), 5.0e-15,
                            within(observed("matrix_symmetry_relative_residual"), 5.0e-15)),
        "row_sum_identity": (observed("row_sum_relative_residual"), 5.0e-13,
                             within(observed("row_sum_relative_residual"), 5.0e-13)),
        "grid_mass": (observed("grid_mass_relative_error"), 2.0e-13,
                      within(observed("grid_mass_relative_error"), 2.0e-13)),
        "linear_momentum": (observed("linear_momentum_error"), 2.0e-11,
                            within(observed("linear_momentum_error"), 2.0e-11)),
    }
    if gate in simple:
        value, tolerance, passed = simple[gate]
        return True, value, tolerance, bool(passed)
    if gate == "full_solve_residual":
        value = observed("max_projection_residual") if is_full else None
        passed = bool(full_solved and value is not None and value <= 5.0e-12)
        return is_full, value, 5.0e-12 if is_full else None, passed if is_full else True
    if gate in {"full_raw_condition", "full_preconditioned_condition"}:
        column, tolerance = (("raw_condition_estimate", 1.0e10) if gate == "full_raw_condition"
                             else ("preconditioned_condition_estimate", 1.0e8))
        value = observed(column) if is_full else None
        passed = bool(full_solved and value is not None and value <= tolerance)
        return is_full, value, tolerance if is_full else None, passed if is_full else True
    if gate in {"full_affine_particle_reconstruction", "full_affine_grid_representation",
                "full_affine_orbital",
                "represented_affine_energy_diagnostic"}:
        column, tolerance = {
            "full_affine_particle_reconstruction": ("particle_reconstruction_error", 5.0e-10),
            "full_affine_grid_representation": ("affine_grid_representation_error", 5.0e-10),
            "full_affine_orbital": ("orbital_angular_error", 5.0e-10),
            "represented_affine_energy_diagnostic": ("center_kinetic_relative_change", 5.0e-9),
        }[gate]
        applicable = is_full and affine
        identity_required = gate != "full_affine_grid_representation"
        identity_clean = integer(raw["id_error_count"], "gate") == 0
        value = observed(column) if (
            full_solved and affine and (identity_clean or not identity_required)) else None
        passed = bool(full_solved and value is not None and value <= tolerance)
        return applicable, value, tolerance if applicable else None, passed if applicable else True
    if gate == "fmpm_residual_identity":
        value = observed("fmpm_residual_identity") if is_fmpm else None
        passed = bool(value is not None and value <= 5.0e-11)
        return is_fmpm, value, 5.0e-11 if is_fmpm else None, passed if is_fmpm else True
    if gate == "fmpm1_pic_identity":
        value = observed("pic_identity_error") if is_fmpm1 else None
        passed = bool(value is not None and value <= 5.0e-13)
        return is_fmpm1, value, 5.0e-13 if is_fmpm1 else None, passed if is_fmpm1 else True
    if gate == "checkpoint_roundtrip_replay":
        passed = boolean(raw["checkpoint_roundtrip_ok"], "raw") and boolean(raw["checkpoint_replay_ok"], "raw")
        return True, 0.0 if passed else 1.0, 0.0, passed
    raise InvalidBundle(f"unknown hard gate {gate}")


def validate_gates(rows: list[dict[str, str]], mode: str,
                   raw: Mapping[tuple[str, str, str, str, str, int], dict[str, str]]) -> dict[tuple[tuple[str, str, str, str, str, int], str], dict[str, str]]:
    indexed: dict[tuple[tuple[str, str, str, str, str, int], str], dict[str, str]] = {}
    for row in rows:
        require(row["mode"] == mode and integer(row["seed"], "gate") == SEED, "gate provenance")
        k = (key(row), row["gate"])
        require(k not in indexed, f"gate duplicate {k}")
        indexed[k] = row
    expected = {(raw_key, gate) for raw_key in raw for gate in GATES}
    require(set(indexed) == expected, "hard-gate matrix mismatch")
    for (raw_key, gate), row in indexed.items():
        applicable, value, tolerance, passed = gate_expectation(raw[raw_key], gate)
        where = f"gate {raw_key}:{gate}"
        require(boolean(row["applicable"], where) == applicable, f"{where}: applicability")
        same_number(row["value"], value, where)
        same_number(row["tolerance"], tolerance, where)
        require(boolean(row["pass"], where) == passed, f"{where}: pass mismatch")
    return indexed


def validate_solver(rows: list[dict[str, str]], mode: str,
                    raw: Mapping[tuple[str, str, str, str, str, int], dict[str, str]]) -> None:
    indexed = index_unique(rows, "solver")
    require(set(indexed) == set(raw), "solver table matrix mismatch")
    copies = {
        "status": "status", "full_reference_status": "full_reference_status",
        "particle_count": "particle_count_diag", "active_node_count": "active_node_count",
        "structural_rank_upper_bound": "structural_rank_upper_bound",
        "numerical_rank_estimate": "numerical_rank_estimate", "rank_method": "numerical_rank_method",
        "rank_is_estimated": "numerical_rank_is_estimated", "raw_condition_estimate": "raw_condition_estimate",
        "rank_certified": "rank_certified", "condition_estimated": "condition_estimated",
        "preconditioned_condition_estimate": "preconditioned_condition_estimate",
        "candidate_residual_applicable": "candidate_solve_residual_applicable",
        "candidate_max_normalized_residual": "max_projection_residual",
        "full_reference_residual_applicable": "full_reference_solve_residual_applicable",
        "full_reference_max_normalized_residual": "full_reference_max_projection_residual",
        "candidate_termination_reason": "candidate_termination_reason",
        "full_reference_termination_reason": "full_reference_termination_reason",
    }
    for k, row in indexed.items():
        source = raw[k]
        require(row["mode"] == mode and integer(row["seed"], "solver") == SEED, "solver provenance")
        for target, origin in copies.items():
            require(row[target] == source[origin], f"solver {k}: {target} mismatch")
        require(boolean(row["candidate_failed"], "solver") == (source["status"] not in SOLVED), f"solver {k}: candidate failure")
        require(boolean(row["full_reference_failed"], "solver") == (source["full_reference_status"] not in SOLVED), f"solver {k}: reference failure")
        require(row["candidate_termination_reason"] != "" and
                row["full_reference_termination_reason"] != "",
                f"solver {k}: missing termination reason")


def validate_checkpoints(rows: list[dict[str, str]], mode: str,
                         raw: Mapping[tuple[str, str, str, str, str, int], dict[str, str]]) -> None:
    indexed = index_unique(rows, "checkpoint")
    require(set(indexed) == set(raw), "checkpoint matrix mismatch")
    for k, row in indexed.items():
        source = raw[k]
        require(row["mode"] == mode and integer(row["seed"], "checkpoint") == SEED, "checkpoint provenance")
        require(row["roundtrip_exact"] == source["checkpoint_roundtrip_ok"] and
                row["replay_exact"] == source["checkpoint_replay_ok"] and
                row["initial_sha256"] == source["initial_checkpoint_sha256"] and
                row["terminal_sha256"] == source["terminal_checkpoint_sha256"],
                f"checkpoint {k}: source mismatch")
        expected_pass = boolean(row["roundtrip_exact"], "checkpoint") and boolean(row["replay_exact"], "checkpoint")
        require(boolean(row["pass"], "checkpoint") == expected_pass, f"checkpoint {k}: pass")


def validate_manifest(bundle: Path) -> None:
    manifest = read_json(bundle / "manifest.json")
    require(set(manifest) == {"algorithm", "files", "pre_hash_sha256", "schema"}, "manifest keys")
    require(manifest["algorithm"] == "SHA-256" and manifest["schema"] == MANIFEST_SCHEMA, "manifest identity")
    files = manifest["files"]
    require(isinstance(files, dict) and set(files) == set(REQUIRED_FILES), "manifest file set")
    for name in REQUIRED_FILES:
        path = bundle / name
        require(path.is_file(), f"missing bundle file {name}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        require(files[name] == digest, f"manifest hash mismatch: {name}")
    payload = {"algorithm": "SHA-256", "files": dict(sorted(files.items())), "schema": MANIFEST_SCHEMA}
    canonical = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    # C++ indentation matches json.dumps except it intentionally omits the final newline.
    require(hashlib.sha256(canonical).hexdigest() == manifest["pre_hash_sha256"], "manifest pre-hash mismatch")


def expected_counts(mode: str) -> dict[str, int]:
    return ({"checkpoint": 6, "convergence": 0, "exact_control": 6, "hard_gates": 120,
             "main_raw": 6, "order_to_full": 2, "orientation_sensitivity": 0,
             "phase_sensitivity": 0, "ppc_raw": 0, "primary_total": 12,
             "solver_failures": 6} if mode == "smoke" else
            {"checkpoint": 324, "convergence": 896, "exact_control": 6, "hard_gates": 6480,
             "main_raw": 288, "order_to_full": 108, "orientation_sensitivity": 480,
             "phase_sensitivity": 480, "ppc_raw": 36, "primary_total": 330,
             "solver_failures": 324})


def bounded_decision(mode: str, raw: Mapping[tuple[str, str, str, str, str, int], dict[str, str]],
                     convergence: Mapping[tuple[str, str, str, str, str, str], dict[str, str]],
                     orders: Mapping[tuple[str, str, str, str, int, str], dict[str, str]],
                     gates: Mapping[tuple[tuple[str, str, str, str, str, int], str], dict[str, str]]) -> str:
    if mode == "smoke":
        return "smoke_provisional_no_scientific_decision"
    if any(k[1] == "full_consistent" and row["status"] not in SOLVED for k, row in raw.items()):
        return "isolate_rank_condition_or_particle_quadrature_and_stop"
    if any(k[0] == "main" and k[1] == "full_consistent" and not boolean(row["pass"], "decision") for k, row in convergence.items()):
        return "stop_reconsider_particle_grid_architecture"
    if any(not boolean(row["applicable"], "decision") for row in orders.values()):
        return "isolate_rank_condition_or_particle_quadrature_and_stop"
    if any(not boolean(row["pass"], "decision") for row in orders.values()):
        return "retain_full_reference_only_reject_tested_FMPM_approximation"
    if (not any(k[1] == "FMPM_4" and not boolean(row["pass"], "decision") for k, row in convergence.items()) and
            not any(k[0][1] == "FMPM_4" and boolean(row["applicable"], "decision") and
                    not boolean(row["pass"], "decision") for k, row in gates.items())):
        return "retain_FMPM_as_mechanics_foundation_research_candidate_only"
    return "retain_full_reference_only_reject_FMPM_for_MLS_gates"


def validate_summary(summary: Mapping[str, Any], mode: str, counts: Mapping[str, int],
                     raw: Mapping[tuple[str, str, str, str, str, int], dict[str, str]],
                     convergence: Mapping[tuple[str, str, str, str, str, str], dict[str, str]],
                     orders: Mapping[tuple[str, str, str, str, int, str], dict[str, str]],
                     gates: Mapping[tuple[tuple[str, str, str, str, str, int], str], dict[str, str]]) -> None:
    require(summary.get("schema") == SUMMARY_SCHEMA and summary.get("mode") == mode and summary.get("seed") == SEED,
            "summary identity")
    require(summary.get("accepted_parent_sha") == PARENT_SHA and summary.get("accepted_parent_tag") == PARENT_TAG,
            "summary parent evidence")
    require(summary.get("exact_oracle_result_sha256") == ORACLE_SHA256, "summary oracle SHA")
    require(summary.get("no_constitutive_mechanics_authorized") is True, "summary scope guard")
    require(summary.get("sweep_complete") is True, "summary incomplete sweep")
    require(summary.get("counts") == dict(counts), "summary counts mismatch")
    require(summary.get("candidate_failures") == sum(row["status"] not in SOLVED for row in raw.values()), "summary candidate failures")
    require(summary.get("full_reference_failures") == sum(row["full_reference_status"] not in SOLVED for row in raw.values()), "summary reference failures")
    require(summary.get("structural_rank_failures") == sum(row["status"] == "structurally_rank_deficient" for row in raw.values()), "summary rank failures")
    require(summary.get("checkpoint_failures") == sum(not (boolean(row["checkpoint_roundtrip_ok"], "summary") and boolean(row["checkpoint_replay_ok"], "summary")) for row in raw.values()), "summary checkpoint failures")
    require(summary.get("convergence_failures") == sum(not boolean(row["pass"], "summary") for row in convergence.values()), "summary convergence failures")
    require(summary.get("order_failures") == sum(boolean(row["applicable"], "summary") and not boolean(row["pass"], "summary") for row in orders.values()), "summary order failures")
    require(summary.get("order_unavailable") == sum(not boolean(row["applicable"], "summary") for row in orders.values()), "summary unavailable orders")
    require(summary.get("hard_gate_failures") == sum(boolean(row["applicable"], "summary") and not boolean(row["pass"], "summary") for row in gates.values()), "summary gate failures")
    require(summary.get("bounded_decision") == bounded_decision(mode, raw, convergence, orders, gates), "summary bounded decision")
    require(summary.get("tool_language") == "C++20" and
            isinstance(summary.get("compiler_id"), str) and summary.get("compiler_id") not in {"", "unknown"} and
            isinstance(summary.get("compiler_version"), str) and summary.get("compiler_version") not in {"", "unknown"},
            "summary tool provenance")
    require(summary.get("time_quantum_s") == 1.0 / 160.0 and summary.get("u_ref_m_per_s") == 2.5 and
            summary.get("domain_min_m") == -0.5 and summary.get("domain_max_m") == 0.5 and
            summary.get("density_kg_per_m3") == 1.0 and
            summary.get("registered_total_mass_kg") == 1.0 and
            summary.get("registered_cfl_u_ref_dt_over_h") == 0.125,
            "summary physical scales")
    require(isinstance(summary.get("source_sha"), str) and isinstance(summary.get("source_branch"), str) and
            isinstance(summary.get("source_dirty"), bool), "summary source provenance")
    if mode == "full":
        require(re.fullmatch(r"[0-9a-f]{40}", str(summary.get("source_sha"))) is not None,
                "full summary requires an exact 40-hex source SHA")
        require(summary.get("source_branch") == "projection-foundation-lab",
                "full summary branch mismatch")
        require(summary.get("source_dirty") is False,
                "full summary must be built from a clean source tree")


def validate_bundle(bundle: Path, smoke_provisional: bool) -> str:
    require(bundle.is_dir(), f"bundle directory does not exist: {bundle}")
    validate_manifest(bundle)
    summary = read_json(bundle / "summary.json")
    mode = summary.get("mode")
    require(mode in {"smoke", "full"}, "unknown bundle mode")
    if mode == "smoke":
        require(smoke_provisional, "smoke bundle requires --smoke-provisional")
    main_rows = read_csv(bundle / "main_raw.csv", RAW_FIELDS)
    ppc_rows = read_csv(bundle / "ppc_raw.csv", RAW_FIELDS)
    exact_rows = read_csv(bundle / "exact_angular_control.csv", EXACT_FIELDS)
    phase_rows = read_csv(bundle / "phase_sensitivity.csv", SENSITIVITY_FIELDS)
    orientation_rows = read_csv(bundle / "orientation_sensitivity.csv", SENSITIVITY_FIELDS)
    convergence_rows = read_csv(bundle / "convergence.csv", CONVERGENCE_FIELDS)
    order_rows = read_csv(bundle / "order_to_full.csv", ORDER_FIELDS)
    gate_rows = read_csv(bundle / "hard_gates.csv", GATE_FIELDS)
    solver_rows = read_csv(bundle / "solver_failures.csv", SOLVER_FIELDS)
    checkpoint_rows = read_csv(bundle / "checkpoint.csv", CHECKPOINT_FIELDS)
    expected = expected_raw(mode)
    main = validate_raw(main_rows, "main", mode, expected)
    ppc = validate_raw(ppc_rows, "ppc", mode, expected)
    raw = dict(main)
    raw.update(ppc)
    validate_exact(exact_rows, mode)
    phase = validate_sensitivity(phase_rows, "phase", mode, raw)
    orientation = validate_sensitivity(orientation_rows, "orientation", mode, raw)
    convergence_expected = expected_convergence(mode, raw, phase, orientation)
    convergence = validate_convergence(convergence_rows, mode, convergence_expected)
    orders = validate_orders(order_rows, mode, raw)
    gates = validate_gates(gate_rows, mode, raw)
    validate_solver(solver_rows, mode, raw)
    validate_checkpoints(checkpoint_rows, mode, raw)
    counts = expected_counts(mode)
    observed_counts = {
        "checkpoint": len(checkpoint_rows), "convergence": len(convergence_rows),
        "exact_control": len(exact_rows), "hard_gates": len(gate_rows),
        "main_raw": len(main_rows), "order_to_full": len(order_rows),
        "orientation_sensitivity": len(orientation_rows), "phase_sensitivity": len(phase_rows),
        "ppc_raw": len(ppc_rows), "primary_total": len(main_rows) + len(ppc_rows) + len(exact_rows),
        "solver_failures": len(solver_rows),
    }
    require(observed_counts == counts, "independent row counts mismatch")
    validate_summary(summary, mode, counts, raw, convergence, orders, gates)
    return mode


def compare_bundles(first: Path, second: Path) -> None:
    for name in (*REQUIRED_FILES, "manifest.json"):
        require((first / name).read_bytes() == (second / name).read_bytes(),
                f"deterministic comparison differs: {name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--smoke-provisional", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        mode = validate_bundle(args.bundle, args.smoke_provisional)
        if args.compare is not None:
            compare_mode = validate_bundle(args.compare, args.smoke_provisional)
            require(compare_mode == mode, "comparison mode mismatch")
            compare_bundles(args.bundle, args.compare)
    except (InvalidBundle, OSError) as error:
        print(f"PROJECTION FOUNDATION BUNDLE INVALID: {error}", file=sys.stderr)
        return 1
    label = "SMOKE PROVISIONAL" if mode == "smoke" else "VALID"
    print(f"PROJECTION FOUNDATION BUNDLE {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
