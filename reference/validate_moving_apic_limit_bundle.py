#!/usr/bin/env python3
"""Independent validator for an MLS Moving APIC Limit Lab evidence bundle.

The validator reconstructs the preregistered configurations, convergence
decisions, hard-gate applicability, and bounded causal decision from the
published CSV files.  It deliberately does not import the C++ diagnostic or
its Python exact oracle.  Passing this program establishes evidence
consistency only; it does not validate mechanics or promote either path.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "mls.moving-apic-limit.summary.v1"
SEED = 260828
PATH_E = "E_JST2017_moving_APIC"
PATH_ORACLE = "E_oracleB"
PATH_C = "C_sealed_static_APIC_ballistic"
PATH_D = "D_analytic_convected_affine_control"
PHASE_ZERO = "p000"
PHASE_HARD = "p049_001_083"

SEALED_SOURCE_SHA = "bb4b8bafd4a830b08c1e7e751090e850dbea1d7a"
SEALED_TAG = "affine-advection-lab-evidence-v1"
SEALED_CSV_SHA256 = "67cb234a0ebaf6dac2251412eb845f18c78806b2d92857608f537439d8de2ad1"
SEALED_HEADER_SHA256 = "174cc146ca76cd9859975e14540d01999d1b74fe8f717eb935b446346bed6330"
SEALED_SOURCE_PATHS = (
    "include/mls/affine_advection_lab.hpp",
    "src/affine_advection_lab.cpp",
    "apps/affine_advection_diagnostic.cpp",
)

MASS_TOLERANCE = 2.0e-13
LINEAR_TOLERANCE = 2.0e-12
ANGULAR_TOLERANCE = 2.0e-11
STATIC_TOLERANCE = 5.0e-11
HORIZON_TOLERANCE = 2.0e-9
ROUND_OFF_FLOOR = 5.0e-14

RAW_FIELDS = (
    "mode", "seed", "scope", "path", "phase", "level", "domain_min_m",
    "domain_max_m", "density_kg_per_m3", "grid_phase_x", "grid_phase_y",
    "grid_phase_z", "grid_spacing_m", "timestep_s", "time_quantum_s",
    "timestep_quanta", "steps", "elapsed_quanta", "horizon_s",
    "u_ref_m_per_s", "cfl", "nominal_cells_per_axis",
    "nominal_grid_cells", "peak_allocated_nodes", "particles_per_axis",
    "particle_count", "particles_per_cell", "particle_spacing_m",
    "kg_per_mass_quantum", "mass_quanta_per_particle",
    "initial_mass_quanta", "terminal_mass_quanta", "total_mass_kg",
    "exact_mass_ok", "exact_clock_ok", "id_error_count",
    "configuration_error_count", "nonfinite_or_missing_count",
    "static_velocity_error", "static_affine_error", "static_grid_error",
    "affine_gradient_error", "affine_intercept_error",
    "affine_dispersion_error", "trajectory_position_error",
    "material_velocity_error", "linear_momentum_error",
    "center_orbital_error", "center_physical_kinetic_error",
    "max_p2g_mass_error", "max_p2g_linear_error", "max_g2p_linear_error",
    "max_p2g_paper_augmented_angular_error",
    "max_g2p_paper_augmented_angular_error",
    "max_abs_p2g_center_energy_residual_j",
    "max_abs_p2g_augmented_energy_residual_j",
    "max_abs_step_center_energy_residual_j",
    "max_abs_step_augmented_energy_residual_j",
    "terminal_center_physical_kinetic_j",
    "terminal_preoverride_affine_energy_j",
    "terminal_preoverride_augmented_energy_j",
    "terminal_postoverride_affine_energy_j",
    "terminal_postoverride_augmented_energy_j", "oracle_B_constraint_error",
    "max_oracle_B_override_relative",
)

PHASE_FIELDS = (
    "mode", "seed", "path", "level", "grid_spacing_m", "timestep_s",
    "particle_count", "reference_phase", "comparison_phase",
    "position_phase_error", "velocity_phase_error", "affine_phase_error",
    "id_error_count", "nonfinite_or_missing_count",
)

CAUSAL_FIELDS = (
    "mode", "seed", "path", "phase", "level", "grid_spacing_m",
    "timestep_s", "particle_count", "D_stationarity_error",
    "B_identity_error", "C_retention_error", "discrepancy_witness_error",
    "oracle_C_exact_applicable", "oracle_C_exact_error",
    "nonfinite_or_missing_count",
)

CONVERGENCE_FIELDS = (
    "mode", "seed", "scope", "path", "phase", "metric", "level_ids",
    "hard_tolerance", "error_level_0", "error_level_1", "error_level_2",
    "error_level_3", "all_below", "contraction_01", "contraction_12",
    "contraction_23", "endpoint_contraction", "finest_increase_failure",
    "ratio_rule", "pass", "failure_reason",
)

HARD_FIELDS = (
    "mode", "seed", "scope", "path", "phase", "gate", "applicable",
    "expected_configurations", "evaluated_configurations", "failure_count",
    "worst_value", "tolerance", "worst_configuration", "pass",
)

PREREQUISITE_FIELDS = (
    "mode", "seed", "gate", "expected", "observed", "applicable",
    "evaluated", "pass", "details",
)

OLD_RAW_FIELDS = (
    "mode", "seed", "scope", "path", "field", "phase_index",
    "orientation_index", "orientation", "layout", "mass_ratio",
    "schedule_index", "step_or_remap_count", "grid_spacing_m", "dt_quanta",
    "dt_seconds", "physical_time_applicable", "elapsed_quanta",
    "exact_mass_ok", "exact_clock_ok", "static_representation_applicable",
    "static_velocity_error", "static_affine_error", "static_grid_error",
    "affine_advection_applicable", "affine_gradient_error",
    "affine_intercept_error", "affine_dispersion_error",
    "stale_witness_applicable", "stale_gradient_witness_error",
    "trajectory_applicable", "trajectory_position_error",
    "material_velocity_error", "linear_momentum_error", "center_orbital_error",
    "center_physical_kinetic_error", "max_p2g_mass_error",
    "max_p2g_linear_error", "max_p2g_paper_augmented_angular_error",
    "max_g2p_linear_error", "max_g2p_paper_augmented_angular_error",
    "max_abs_p2g_center_energy_residual_j",
    "max_abs_p2g_augmented_representation_energy_residual_j",
    "terminal_affine_auxiliary_energy_diagnostic_j",
    "terminal_augmented_representation_energy_diagnostic_j",
)

METRIC_COLUMN = {
    "static_velocity": "static_velocity_error",
    "static_affine": "static_affine_error",
    "static_grid": "static_grid_error",
    "affine_gradient": "affine_gradient_error",
    "affine_intercept": "affine_intercept_error",
    "affine_dispersion": "affine_dispersion_error",
    "trajectory_position": "trajectory_position_error",
    "material_velocity": "material_velocity_error",
    "linear_momentum": "linear_momentum_error",
    "center_orbital": "center_orbital_error",
    "center_physical_kinetic": "center_physical_kinetic_error",
}
PHASE_METRIC_COLUMN = {
    "phase_position": "position_phase_error",
    "phase_velocity": "velocity_phase_error",
    "phase_affine": "affine_phase_error",
}
GATE_NAMES = (
    "exact_mass_ok", "exact_clock_ok", "max_p2g_mass_error",
    "max_p2g_linear_error", "max_g2p_linear_error",
    "max_p2g_paper_augmented_angular_error",
    "max_g2p_paper_augmented_angular_error", "static_grid_error",
    "oracle_B_constraint_error", "nonfinite_or_missing_count",
    "configuration_error_count", "id_error_count",
    "first_step_D_stationarity_error", "first_step_B_identity_error",
    "first_step_C_retention_error", "first_step_discrepancy_witness_error",
    "oracle_first_step_C_exact_error",
)
PREREQUISITE_VALUES = {
    "accepted_source_sha": SEALED_SOURCE_SHA,
    "immutable_release_tag": SEALED_TAG,
    "sealed_control_csv_sha256": SEALED_CSV_SHA256,
    "sealed_control_header_sha256": SEALED_HEADER_SHA256,
}
PREREQUISITE_DETAILS = {
    "accepted_source_sha":
        "requires ancestry and zero-diff check for the three sealed Path-E files",
    "immutable_release_tag": "requires remote immutable-tag verification",
    "sealed_control_csv_sha256": "computed before byte-for-byte copy",
    "sealed_control_header_sha256": "computed including LF terminator",
}

FULL_COUNTS = {
    "fixed_particle_control": 12,
    "co_refinement": 12,
    "particles_per_cell": 6,
    "phase_sensitivity": 6,
    "causal_controls": 12,
    "convergence": 105,
    "hard_gates": 153,
    "prerequisites": 4,
}
SMOKE_COUNTS = {
    "fixed_particle_control": 0,
    "co_refinement": 2,
    "particles_per_cell": 2,
    "phase_sensitivity": 0,
    "causal_controls": 2,
    "convergence": 0,
    "hard_gates": 68,
    "prerequisites": 4,
}
REQUIRED_FILES = (
    "co_refinement.csv", "particles_per_cell.csv", "phase_sensitivity.csv",
    "causal_controls.csv", "convergence.csv", "hard_gates.csv",
    "prerequisites.csv", "summary.json",
)


class BundleError(RuntimeError):
    """The evidence is structurally unusable and cannot be audited."""


def no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BundleError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_int(value: str, label: str) -> int:
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)", value) is None:
        raise BundleError(f"{label}: invalid canonical integer {value!r}")
    return int(value)


def parse_bool(value: str, label: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise BundleError(f"{label}: expected true/false, got {value!r}")


def parse_float(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as error:
        raise BundleError(f"{label}: invalid float {value!r}") from error
    if not math.isfinite(result):
        raise BundleError(f"{label}: non-finite float {value!r}")
    return result


def parse_optional_float(value: str, label: str) -> float | None:
    return None if value == "NA" else parse_float(value, label)


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=2.0e-14, abs_tol=2.0e-17)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_manifest(bundle: Path) -> dict[str, str]:
    return {
        path.relative_to(bundle).as_posix(): sha256_file(path)
        for path in sorted(bundle.rglob("*")) if path.is_file()
    }


def read_csv(path: Path, expected_header: Sequence[str]) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            actual = tuple(reader.fieldnames or ())
            if actual != tuple(expected_header):
                raise BundleError(
                    f"{path.name}: header differs from frozen schema\n"
                    f"expected={list(expected_header)!r}\nactual={list(actual)!r}"
                )
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        raise BundleError(f"cannot read {path}: {error}") from error
    for number, row in enumerate(rows, 2):
        if None in row or any(value is None for value in row.values()):
            raise BundleError(f"{path.name}:{number}: malformed field count")
    return rows


def load_summary(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_object
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BundleError(f"cannot parse summary.json: {error}") from error
    if not isinstance(loaded, dict):
        raise BundleError("summary.json must be an object")
    return loaded


@dataclass
class Audit:
    bundle: Path
    summary: dict[str, Any]
    mode: str
    smoke_provisional: bool
    errors: list[str] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)

    def check(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)

    def check_float(self, actual: float, expected: float, message: str) -> None:
        self.check(close(actual, expected), f"{message}: {actual:.17g} != {expected:.17g}")


@dataclass(frozen=True)
class Configuration:
    scope: str
    path: str
    phase: str
    level: int
    phase_xyz: tuple[float, float, float]
    h: float
    dt: float
    dt_quanta: int
    steps: int
    cells_axis: int
    cells: int
    particles_axis: int
    particles: int
    particles_per_cell: int
    spacing: float
    mass_quanta_particle: int


def full_configurations() -> tuple[Configuration, ...]:
    result: list[Configuration] = []
    co_levels = (
        (0, 0.5, 1.0 / 40.0, 4, 4, 4, 64, 8, 512, 8, 0.25, 64),
        (1, 0.25, 1.0 / 80.0, 2, 8, 8, 512, 16, 4096, 8, 0.125, 8),
        (2, 0.125, 1.0 / 160.0, 1, 16, 16, 4096, 32, 32768, 8, 0.0625, 1),
    )
    phases = ((PHASE_ZERO, (0.0, 0.0, 0.0)),
              (PHASE_HARD, (0.49, 0.01, 0.83)))
    for path in (PATH_E, PATH_ORACLE):
        for phase, xyz in phases:
            for (level, h, dt, dtq, steps, ca, cells, pa, particles,
                 ppc, spacing, mqp) in co_levels:
                result.append(Configuration(
                    "co_refinement", path, phase, level, xyz, h, dt, dtq,
                    steps, ca, cells, pa, particles, ppc, spacing, mqp,
                ))
    ppc_levels = (
        (0, 8, 512, 1, 0.25, 64),
        (1, 16, 4096, 8, 0.125, 8),
        (2, 32, 32768, 64, 0.0625, 1),
    )
    for path in (PATH_E, PATH_ORACLE):
        for level, pa, particles, ppc, spacing, mqp in ppc_levels:
            result.append(Configuration(
                "particles_per_cell", path, PHASE_HARD, level,
                (0.49, 0.01, 0.83), 0.25, 1.0 / 80.0, 2, 8, 8, 512,
                pa, particles,
                ppc, spacing, mqp,
            ))
    return tuple(result)


def smoke_configurations() -> tuple[Configuration, ...]:
    full = full_configurations()
    return tuple(config for config in full if config.phase == PHASE_HARD and config.level == 0)


def configuration_key(config: Configuration) -> tuple[str, str, str, int]:
    return config.scope, config.path, config.phase, config.level


def validate_analytic_contract(audit: Audit) -> None:
    # Frozen p210_sppm general-affine metadata, independently transcribed from
    # the preregistration.  The CSV contains error scalars rather than the
    # field itself, so this gate verifies the registered field's dimensional
    # assumptions and all inverse times used by the experiment.
    matrix = (
        (3.0 / 20.0, 2.0 / 5.0, 7.0 / 20.0),
        (1.0 / 4.0, -1.0 / 10.0, -11.0 / 20.0),
        (-3.0 / 10.0, 7.0 / 10.0, 1.0 / 5.0),
    )
    offset = (111.0 / 125.0, -129.0 / 200.0, -74.0 / 125.0)
    maximum_speed = 0.0
    for x in (-1.0, 1.0):
        for y in (-1.0, 1.0):
            for z in (-1.0, 1.0):
                position = (x, y, z)
                velocity = tuple(
                    sum(matrix[row][column] * position[column] for column in range(3))
                    + offset[row]
                    for row in range(3)
                )
                maximum_speed = max(maximum_speed, math.sqrt(sum(v * v for v in velocity)))
    u_ref = 2.5
    audit.check(maximum_speed < u_ref,
                f"registered U_ref={u_ref} does not bound corner speed {maximum_speed}")

    def determinant(value: tuple[tuple[float, float, float], ...]) -> float:
        return (
            value[0][0] * (value[1][1] * value[2][2] - value[1][2] * value[2][1])
            - value[0][1] * (value[1][0] * value[2][2] - value[1][2] * value[2][0])
            + value[0][2] * (value[1][0] * value[2][1] - value[1][1] * value[2][0])
        )

    for time in (1.0 / 160.0, 1.0 / 80.0, 1.0 / 40.0, 0.1):
        mapping = tuple(tuple(
            (1.0 if row == column else 0.0) + time * matrix[row][column]
            for column in range(3)
        ) for row in range(3))
        audit.check(abs(determinant(mapping)) > 1.0e-12,
                    f"registered affine map is singular at t={time}")


def common_row(audit: Audit, row: Mapping[str, str], label: str) -> None:
    audit.check(row["mode"] == audit.mode, f"{label}: wrong mode")
    audit.check(parse_int(row["seed"], f"{label}.seed") == SEED, f"{label}: wrong seed")


def validate_raw_rows(
    audit: Audit,
    rows_by_scope: Mapping[str, Sequence[Mapping[str, str]]],
) -> dict[tuple[str, str, str, int], Mapping[str, str]]:
    expected_configs = (
        full_configurations() if audit.mode == "full" else smoke_configurations()
    )
    expected = {configuration_key(config): config for config in expected_configs}
    observed: dict[tuple[str, str, str, int], Mapping[str, str]] = {}
    numeric_errors = tuple(METRIC_COLUMN.values()) + (
        "max_p2g_mass_error", "max_p2g_linear_error", "max_g2p_linear_error",
        "max_p2g_paper_augmented_angular_error",
        "max_g2p_paper_augmented_angular_error",
        "max_abs_p2g_center_energy_residual_j",
        "max_abs_p2g_augmented_energy_residual_j",
        "max_abs_step_center_energy_residual_j",
        "max_abs_step_augmented_energy_residual_j",
    )
    finite_diagnostics = (
        "terminal_center_physical_kinetic_j",
        "terminal_preoverride_affine_energy_j",
        "terminal_preoverride_augmented_energy_j",
        "terminal_postoverride_affine_energy_j",
        "terminal_postoverride_augmented_energy_j",
    )
    for scope, rows in rows_by_scope.items():
        for line, row in enumerate(rows, 2):
            label = f"{scope}.csv:{line}"
            common_row(audit, row, label)
            level = parse_int(row["level"], f"{label}.level")
            key = (row["scope"], row["path"], row["phase"], level)
            audit.check(row["scope"] == scope, f"{label}: scope/file mismatch")
            audit.check(key not in observed, f"{label}: duplicate configuration {key!r}")
            audit.check(key in expected, f"{label}: unregistered configuration {key!r}")
            if key in observed or key not in expected:
                continue
            observed[key] = row
            config = expected[key]
            audit.check_float(parse_float(row["domain_min_m"], label), -1.0,
                              f"{label}: domain minimum")
            audit.check_float(parse_float(row["domain_max_m"], label), 1.0,
                              f"{label}: domain maximum")
            audit.check_float(parse_float(row["density_kg_per_m3"], label), 1.0,
                              f"{label}: density")
            for axis, actual, wanted in zip(
                "xyz", (row["grid_phase_x"], row["grid_phase_y"], row["grid_phase_z"]),
                config.phase_xyz,
            ):
                audit.check_float(parse_float(actual, f"{label}.phase_{axis}"), wanted,
                                  f"{label}: phase {axis}")
            audit.check_float(parse_float(row["grid_spacing_m"], label), config.h,
                              f"{label}: h")
            audit.check_float(parse_float(row["timestep_s"], label), config.dt,
                              f"{label}: dt")
            audit.check_float(parse_float(row["time_quantum_s"], label), 1.0 / 160.0,
                              f"{label}: time quantum")
            int_expectations = {
                "timestep_quanta": config.dt_quanta,
                "steps": config.steps,
                "elapsed_quanta": 16,
                "nominal_cells_per_axis": config.cells_axis,
                "nominal_grid_cells": config.cells,
                "particles_per_axis": config.particles_axis,
                "particle_count": config.particles,
                "particles_per_cell": config.particles_per_cell,
                "mass_quanta_per_particle": config.mass_quanta_particle,
                "initial_mass_quanta": 32768,
                "terminal_mass_quanta": 32768,
                "id_error_count": 0,
                "configuration_error_count": 0,
                "nonfinite_or_missing_count": 0,
            }
            for name, wanted in int_expectations.items():
                actual = parse_int(row[name], f"{label}.{name}")
                audit.check(actual == wanted, f"{label}: {name}={actual} != {wanted}")
            peak = parse_int(row["peak_allocated_nodes"], f"{label}.peak_allocated_nodes")
            audit.check(peak > 0, f"{label}: peak allocated node count must be positive")
            float_expectations = {
                "horizon_s": 0.1,
                "u_ref_m_per_s": 2.5,
                "cfl": 0.125,
                "particle_spacing_m": config.spacing,
                "kg_per_mass_quantum": 1.0 / 4096.0,
                "total_mass_kg": 8.0,
            }
            for name, wanted in float_expectations.items():
                audit.check_float(parse_float(row[name], f"{label}.{name}"), wanted,
                                  f"{label}: {name}")
            audit.check(parse_bool(row["exact_mass_ok"], f"{label}.exact_mass_ok"),
                        f"{label}: exact mass gate failed")
            audit.check(parse_bool(row["exact_clock_ok"], f"{label}.exact_clock_ok"),
                        f"{label}: exact clock gate failed")
            for name in numeric_errors:
                value = parse_float(row[name], f"{label}.{name}")
                audit.check(value >= 0.0, f"{label}: {name} is negative")
            for name in finite_diagnostics:
                parse_float(row[name], f"{label}.{name}")
            oracle_constraint = parse_optional_float(
                row["oracle_B_constraint_error"], f"{label}.oracle_B_constraint_error"
            )
            override = parse_optional_float(
                row["max_oracle_B_override_relative"],
                f"{label}.max_oracle_B_override_relative",
            )
            if config.path == PATH_ORACLE:
                audit.check(oracle_constraint is not None,
                            f"{label}: oracle B constraint is missing")
                audit.check(override is not None, f"{label}: oracle override is missing")
                if oracle_constraint is not None:
                    audit.check(oracle_constraint >= 0.0,
                                f"{label}: oracle B constraint is negative")
                if override is not None:
                    audit.check(override >= 0.0, f"{label}: oracle override is negative")
            else:
                audit.check(oracle_constraint is None,
                            f"{label}: E has an oracle B constraint value")
                audit.check(override is None, f"{label}: E has an oracle override value")
    if set(observed) != set(expected):
        raise BundleError("raw configuration Cartesian product differs")
    return observed


def validate_phase_rows(
    audit: Audit, rows: Sequence[Mapping[str, str]]
) -> dict[tuple[str, int], Mapping[str, str]]:
    expected = (
        {(path, level) for path in (PATH_E, PATH_ORACLE) for level in range(3)}
        if audit.mode == "full" else set()
    )
    observed: dict[tuple[str, int], Mapping[str, str]] = {}
    h_dt_particles = {
        0: (0.5, 1.0 / 40.0, 512),
        1: (0.25, 1.0 / 80.0, 4096),
        2: (0.125, 1.0 / 160.0, 32768),
    }
    for line, row in enumerate(rows, 2):
        label = f"phase_sensitivity.csv:{line}"
        common_row(audit, row, label)
        level = parse_int(row["level"], f"{label}.level")
        key = (row["path"], level)
        audit.check(key not in observed, f"{label}: duplicate {key!r}")
        audit.check(key in expected, f"{label}: unregistered {key!r}")
        if key in observed or key not in expected:
            continue
        observed[key] = row
        h, dt, particles = h_dt_particles[level]
        audit.check_float(parse_float(row["grid_spacing_m"], label), h, f"{label}: h")
        audit.check_float(parse_float(row["timestep_s"], label), dt, f"{label}: dt")
        audit.check(parse_int(row["particle_count"], label) == particles,
                    f"{label}: wrong particle count")
        audit.check(row["reference_phase"] == PHASE_ZERO, f"{label}: wrong reference phase")
        audit.check(row["comparison_phase"] == PHASE_HARD, f"{label}: wrong comparison phase")
        for name in PHASE_METRIC_COLUMN.values():
            audit.check(parse_float(row[name], f"{label}.{name}") >= 0.0,
                        f"{label}: negative {name}")
        audit.check(parse_int(row["id_error_count"], label) == 0,
                    f"{label}: ID errors")
        audit.check(parse_int(row["nonfinite_or_missing_count"], label) == 0,
                    f"{label}: nonfinite/missing values")
    if set(observed) != expected:
        raise BundleError("phase-pair Cartesian product differs")
    return observed


def validate_causal_rows(
    audit: Audit, rows: Sequence[Mapping[str, str]]
) -> dict[tuple[str, str, int], Mapping[str, str]]:
    if audit.mode == "full":
        expected = {
            (path, phase, level)
            for path in (PATH_E, PATH_ORACLE)
            for phase in (PHASE_ZERO, PHASE_HARD)
            for level in range(3)
        }
    else:
        expected = {(PATH_E, PHASE_HARD, 0), (PATH_ORACLE, PHASE_HARD, 0)}
    configs = {
        (config.path, config.phase, config.level): config
        for config in (full_configurations() if audit.mode == "full" else smoke_configurations())
        if config.scope == "co_refinement"
    }
    observed: dict[tuple[str, str, int], Mapping[str, str]] = {}
    for line, row in enumerate(rows, 2):
        label = f"causal_controls.csv:{line}"
        common_row(audit, row, label)
        level = parse_int(row["level"], f"{label}.level")
        key = row["path"], row["phase"], level
        audit.check(key not in observed, f"{label}: duplicate {key!r}")
        audit.check(key in expected, f"{label}: unregistered {key!r}")
        if key in observed or key not in expected:
            continue
        observed[key] = row
        config = configs[key]
        audit.check_float(parse_float(row["grid_spacing_m"], label), config.h,
                          f"{label}: h")
        audit.check_float(parse_float(row["timestep_s"], label), config.dt,
                          f"{label}: dt")
        audit.check(parse_int(row["particle_count"], label) == config.particles,
                    f"{label}: particle count")
        for name in (
            "D_stationarity_error", "B_identity_error", "C_retention_error",
            "discrepancy_witness_error",
        ):
            audit.check(parse_float(row[name], f"{label}.{name}") >= 0.0,
                        f"{label}: negative {name}")
        applicable = parse_bool(row["oracle_C_exact_applicable"], label)
        oracle_error = parse_optional_float(row["oracle_C_exact_error"], label)
        audit.check(applicable == (row["path"] == PATH_ORACLE),
                    f"{label}: oracle C applicability mismatch")
        audit.check((oracle_error is not None) == applicable,
                    f"{label}: oracle C value/applicability mismatch")
        if oracle_error is not None:
            audit.check(oracle_error >= 0.0, f"{label}: negative oracle C error")
        audit.check(parse_int(row["nonfinite_or_missing_count"], label) == 0,
                    f"{label}: nonfinite/missing values")
    if set(observed) != expected:
        raise BundleError("causal-control Cartesian product differs")
    return observed


def validate_sealed_control(
    audit: Audit,
) -> tuple[list[dict[str, str]], str | None, str | None]:
    path = audit.bundle / "fixed_particle_control.csv"
    if audit.mode == "smoke":
        audit.check(not path.exists(), "smoke must not synthesize a sealed control")
        return [], None, None
    if not path.is_file():
        raise BundleError("full bundle is missing fixed_particle_control.csv")
    data = path.read_bytes()
    csv_hash = sha256_bytes(data)
    newline = data.find(b"\n")
    if newline < 0:
        raise BundleError("sealed control has no LF-terminated header")
    header_hash = sha256_bytes(data[:newline + 1])
    audit.check(csv_hash == SEALED_CSV_SHA256, "sealed control byte hash differs")
    audit.check(header_hash == SEALED_HEADER_SHA256, "sealed control header hash differs")
    rows = read_csv(path, OLD_RAW_FIELDS)
    audit.check(len(rows) == 12, f"sealed control has {len(rows)} rows, expected 12")
    expected = {
        (path_name, level)
        for path_name in (PATH_C, PATH_D, PATH_E) for level in range(4)
    }
    observed: set[tuple[str, int]] = set()
    for line, row in enumerate(rows, 2):
        label = f"fixed_particle_control.csv:{line}"
        audit.check(row["mode"] == "full", f"{label}: wrong sealed mode")
        audit.check(parse_int(row["seed"], label) == SEED, f"{label}: wrong seed")
        level = parse_int(row["schedule_index"], label)
        key = row["path"], level
        audit.check(key in expected, f"{label}: unregistered sealed row {key!r}")
        audit.check(key not in observed, f"{label}: duplicate sealed row {key!r}")
        observed.add(key)
        audit.check(row["scope"] == "coupled_h_dt", f"{label}: wrong sealed scope")
        audit.check(row["field"] == "general_affine", f"{label}: wrong field")
        audit.check(parse_int(row["phase_index"], label) == 1,
                    f"{label}: wrong phase")
        audit.check(parse_int(row["orientation_index"], label) == 2,
                    f"{label}: wrong orientation index")
        audit.check(row["orientation"] == "p210_sppm", f"{label}: wrong orientation")
        audit.check(row["layout"] == "unequal_mass_asymmetric", f"{label}: wrong layout")
        audit.check(parse_int(row["mass_ratio"], label) == 17,
                    f"{label}: wrong mass ratio")
    audit.check(observed == expected, "sealed control Cartesian product differs")
    return rows, csv_hash, header_hash


def validate_prerequisites(
    audit: Audit,
    rows: Sequence[Mapping[str, str]],
    sealed_csv_hash: str | None,
    sealed_header_hash: str | None,
) -> dict[str, Mapping[str, str]]:
    observed: dict[str, Mapping[str, str]] = {}
    for line, row in enumerate(rows, 2):
        label = f"prerequisites.csv:{line}"
        common_row(audit, row, label)
        gate = row["gate"]
        audit.check(gate in PREREQUISITE_VALUES, f"{label}: unknown gate {gate!r}")
        audit.check(gate not in observed, f"{label}: duplicate gate {gate!r}")
        if gate not in PREREQUISITE_VALUES or gate in observed:
            continue
        observed[gate] = row
        audit.check(row["expected"] == PREREQUISITE_VALUES[gate],
                    f"{label}: wrong expected value")
        applicable = parse_bool(row["applicable"], f"{label}.applicable")
        evaluated = parse_bool(row["evaluated"], f"{label}.evaluated")
        passed = parse_bool(row["pass"], f"{label}.pass")
        if audit.mode == "smoke":
            audit.check(not applicable and not evaluated and not passed,
                        f"{label}: smoke prerequisite must be deferred")
            audit.check(row["observed"] == "NA", f"{label}: smoke observed must be NA")
            audit.check(row["details"] == "smoke_provisional",
                        f"{label}: wrong smoke detail")
            continue
        audit.check(applicable, f"{label}: full prerequisite must apply")
        if gate == "sealed_control_csv_sha256":
            audit.check(evaluated and passed, f"{label}: CSV hash gate did not pass")
            audit.check(row["observed"] == sealed_csv_hash,
                        f"{label}: CSV observed hash mismatch")
        elif gate == "sealed_control_header_sha256":
            audit.check(evaluated and passed, f"{label}: header hash gate did not pass")
            audit.check(row["observed"] == sealed_header_hash,
                        f"{label}: header observed hash mismatch")
        else:
            audit.check(not evaluated and not passed,
                        f"{label}: source/tag must remain externally evaluated")
            audit.check(row["observed"] == "deferred_to_independent_validator",
                        f"{label}: wrong deferred marker")
        audit.check(row["details"] == PREREQUISITE_DETAILS[gate],
                    f"{label}: prerequisite detail mismatch")
    audit.check(set(observed) == set(PREREQUISITE_VALUES),
                "prerequisite gate vocabulary differs")
    return observed


def git_query(repository: Path, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments], check=False,
            capture_output=True, text=True, encoding="utf-8",
        )
    except OSError as error:
        raise BundleError(f"cannot execute Git: {error}") from error


def validate_sealed_source(audit: Audit, repository: Path, required: bool) -> bool:
    inside = git_query(repository, ("rev-parse", "--is-inside-work-tree"))
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        audit.check(not required, f"sealed-source repository unavailable: {repository}")
        return False
    tag = git_query(repository, ("rev-list", "-n", "1", SEALED_TAG))
    diff = git_query(repository, ("diff", "--quiet", SEALED_SOURCE_SHA, "--", *SEALED_SOURCE_PATHS))
    ancestor = git_query(repository, ("merge-base", "--is-ancestor", SEALED_SOURCE_SHA, "HEAD"))
    okay = (
        tag.returncode == 0 and tag.stdout.strip() == SEALED_SOURCE_SHA
        and diff.returncode == 0 and ancestor.returncode == 0
    )
    audit.check(not required or okay, "sealed Path E source/tag verification failed")
    return okay


def validate_provenance(
    audit: Audit,
    source_sha: str | None,
    source_branch: str | None,
    require_clean: bool,
) -> None:
    summary = audit.summary
    source = summary.get("source")
    if not isinstance(source, dict):
        audit.check(False, "summary source must be an object")
        return
    audit.check(set(source) == {"sha", "branch", "dirty"},
                "summary source has missing or extra keys")
    embedded_sha = source.get("sha")
    embedded_branch = source.get("branch")
    embedded_dirty = source.get("dirty")
    audit.check(
        isinstance(embedded_sha, str)
        and (embedded_sha == "unknown" or re.fullmatch(r"[0-9a-f]{40}", embedded_sha) is not None),
        "malformed configure-time source SHA",
    )
    audit.check(isinstance(embedded_branch, str) and bool(embedded_branch),
                "missing configure-time source branch")
    audit.check(isinstance(embedded_dirty, bool), "source.dirty must be a boolean")
    if source_sha is not None:
        audit.check(re.fullmatch(r"[0-9a-f]{40}", source_sha) is not None,
                    "--source-sha must be a full lowercase SHA")
        audit.check(embedded_sha == source_sha, "embedded source SHA differs from requirement")
    if source_branch is not None:
        audit.check(embedded_branch == source_branch,
                    "embedded source branch differs from requirement")
    if not require_clean:
        return
    audit.check(embedded_dirty is False, "configure-time source was dirty")
    repository = Path(__file__).resolve().parents[1]
    head = git_query(repository, ("rev-parse", "HEAD"))
    branch = git_query(repository, ("branch", "--show-current"))
    status = git_query(repository, ("status", "--porcelain"))
    audit.check(head.returncode == 0 and head.stdout.strip() == embedded_sha,
                "runtime HEAD differs from embedded source SHA")
    audit.check(branch.returncode == 0 and branch.stdout.strip() == embedded_branch,
                "runtime branch differs from embedded source branch")
    audit.check(status.returncode == 0 and not status.stdout.strip(),
                "runtime source tree is dirty")


@dataclass(frozen=True)
class ConvergenceResult:
    values: tuple[float, ...]
    tolerance: float
    all_below: bool
    contractions: tuple[bool, ...]
    endpoint: bool
    finest_increase: bool
    ratio_rule: bool
    passes: bool
    reason: str


def convergence(values: Sequence[float], tolerance: float) -> ConvergenceResult:
    if len(values) not in {3, 4} or any(value < 0.0 or not math.isfinite(value) for value in values):
        finite_values = tuple(value for value in values if math.isfinite(value))
        return ConvergenceResult(
            finite_values, tolerance, False, (), False, True, False, False,
            "missing_or_nonfinite",
        )
    values_tuple = tuple(values)
    all_below = all(value <= tolerance for value in values_tuple)
    contractions = tuple(
        values_tuple[index + 1] <= 0.70 * values_tuple[index]
        for index in range(len(values_tuple) - 1)
    )
    endpoint_factor = 0.25 if len(values_tuple) == 3 else 0.125
    endpoint = values_tuple[-1] <= endpoint_factor * values_tuple[0]
    finest_increase = values_tuple[-1] > ROUND_OFF_FLOOR and any(
        values_tuple[-1] > previous for previous in values_tuple[:-1]
    )
    ratio = not finest_increase and all(contractions) and endpoint
    passes = all_below or ratio
    if all_below:
        reason = "pass_all_below"
    elif ratio:
        reason = "pass_ratio"
    elif finest_increase:
        reason = "finest_increase"
    elif not endpoint:
        reason = "endpoint_failed"
    elif not all(contractions):
        reason = "contraction_failed"
    else:
        reason = "hard_and_ratio_failed"
    return ConvergenceResult(
        values_tuple, tolerance, all_below, contractions, endpoint,
        finest_increase, ratio, passes, reason,
    )


def metric_tolerance(metric: str) -> float:
    return STATIC_TOLERANCE if metric in {
        "static_velocity", "static_affine", "static_grid"
    } else HORIZON_TOLERANCE


def expected_convergence(
    sealed: Sequence[Mapping[str, str]],
    raw: Mapping[tuple[str, str, str, int], Mapping[str, str]],
    phases: Mapping[tuple[str, int], Mapping[str, str]],
) -> dict[tuple[str, str, str, str], ConvergenceResult]:
    expected: dict[tuple[str, str, str, str], ConvergenceResult] = {}
    if sealed:
        for path in (PATH_C, PATH_D, PATH_E):
            family = sorted(
                (row for row in sealed if row["path"] == path),
                key=lambda row: parse_int(row["schedule_index"], "sealed level"),
            )
            for metric, column in METRIC_COLUMN.items():
                values = tuple(parse_float(row[column], f"sealed.{path}.{metric}") for row in family)
                expected[("fixed_particle_control", path, "NA", metric)] = convergence(
                    values, metric_tolerance(metric)
                )
    for scope in ("co_refinement", "particles_per_cell"):
        phase_names = ((PHASE_ZERO, PHASE_HARD) if scope == "co_refinement" else ("NA",))
        for path in (PATH_E, PATH_ORACLE):
            for family_phase in phase_names:
                raw_phase = family_phase if scope == "co_refinement" else PHASE_HARD
                family = [raw[(scope, path, raw_phase, level)] for level in range(3)]
                for metric, column in METRIC_COLUMN.items():
                    values = tuple(parse_float(row[column], f"{scope}.{path}.{metric}") for row in family)
                    expected[(scope, path, family_phase, metric)] = convergence(
                        values, metric_tolerance(metric)
                    )
    if phases:
        for path in (PATH_E, PATH_ORACLE):
            family = [phases[(path, level)] for level in range(3)]
            for metric, column in PHASE_METRIC_COLUMN.items():
                values = tuple(parse_float(row[column], f"phase.{path}.{metric}") for row in family)
                expected[("phase_sensitivity", path, "p000_vs_p049_001_083", metric)] = convergence(
                    values, HORIZON_TOLERANCE
                )
    return expected


def validate_convergence_rows(
    audit: Audit,
    rows: Sequence[Mapping[str, str]],
    expected: Mapping[tuple[str, str, str, str], ConvergenceResult],
) -> dict[tuple[str, str, str, str], ConvergenceResult]:
    observed: set[tuple[str, str, str, str]] = set()
    for line, row in enumerate(rows, 2):
        label = f"convergence.csv:{line}"
        common_row(audit, row, label)
        key = row["scope"], row["path"], row["phase"], row["metric"]
        audit.check(key in expected, f"{label}: unregistered group {key!r}")
        audit.check(key not in observed, f"{label}: duplicate group {key!r}")
        if key not in expected or key in observed:
            continue
        observed.add(key)
        result = expected[key]
        audit.check(row["level_ids"] == ("0|1|2|3" if len(result.values) == 4 else "0|1|2"),
                    f"{label}: wrong level IDs")
        audit.check_float(parse_float(row["hard_tolerance"], label), result.tolerance,
                          f"{label}: hard tolerance")
        error_fields = ("error_level_0", "error_level_1", "error_level_2", "error_level_3")
        for index, name in enumerate(error_fields):
            if index < len(result.values):
                audit.check_float(parse_float(row[name], f"{label}.{name}"), result.values[index],
                                  f"{label}: {name}")
            else:
                audit.check(row[name] == "NA", f"{label}: {name} must be NA")
        audit.check(parse_bool(row["all_below"], label) == result.all_below,
                    f"{label}: all_below mismatch")
        contraction_fields = ("contraction_01", "contraction_12", "contraction_23")
        for index, name in enumerate(contraction_fields):
            if index < len(result.contractions):
                audit.check(parse_bool(row[name], f"{label}.{name}") == result.contractions[index],
                            f"{label}: {name} mismatch")
            else:
                audit.check(row[name] == "NA", f"{label}: {name} must be NA")
        audit.check(parse_bool(row["endpoint_contraction"], label) == result.endpoint,
                    f"{label}: endpoint mismatch")
        audit.check(parse_bool(row["finest_increase_failure"], label) == result.finest_increase,
                    f"{label}: finest-increase mismatch")
        audit.check(parse_bool(row["ratio_rule"], label) == result.ratio_rule,
                    f"{label}: ratio-rule mismatch")
        audit.check(parse_bool(row["pass"], label) == result.passes,
                    f"{label}: pass mismatch")
        audit.check(row["failure_reason"] == result.reason,
                    f"{label}: failure reason mismatch")
    audit.check(observed == set(expected), "convergence group set differs")
    return dict(expected)


@dataclass(frozen=True)
class HardResult:
    applicable: bool
    expected_configurations: int
    evaluated_configurations: int
    failure_count: int
    worst_value: float | None
    tolerance: float | None
    worst_configuration: str | None
    passes: bool


def hard_result(values: Sequence[tuple[int, float]], tolerance: float) -> HardResult:
    worst_level, worst_value = values[0]
    for level, value in values[1:]:
        if value > worst_value:
            worst_level, worst_value = level, value
    failures = sum(value > tolerance for _, value in values)
    return HardResult(
        True, len(values), len(values), failures, worst_value, tolerance,
        f"level_{worst_level}", failures == 0,
    )


def inapplicable_hard() -> HardResult:
    return HardResult(False, 0, 0, 0, None, None, None, True)


def expected_hard_results(
    audit: Audit,
    sealed: Sequence[Mapping[str, str]],
    raw: Mapping[tuple[str, str, str, int], Mapping[str, str]],
    causal: Mapping[tuple[str, str, int], Mapping[str, str]],
) -> dict[tuple[str, str, str, str], HardResult]:
    families: dict[tuple[str, str, str], list[tuple[int, Mapping[str, str], bool]]] = {}
    if sealed:
        for path in (PATH_C, PATH_D, PATH_E):
            families[("fixed_particle_control", path, "NA")] = [
                (parse_int(row["schedule_index"], "sealed level"), row, True)
                for row in sealed if row["path"] == path
            ]
    configs = full_configurations() if audit.mode == "full" else smoke_configurations()
    family_keys = sorted({
        (
            config.scope,
            config.path,
            config.phase if config.scope == "co_refinement" else "NA",
        )
        for config in configs
    })
    for scope, path, family_phase in family_keys:
        raw_phase = family_phase if scope == "co_refinement" else PHASE_HARD
        levels = sorted(
            config.level for config in configs
            if config.scope == scope and config.path == path
            and config.phase == raw_phase
        )
        families[(scope, path, family_phase)] = [
            (level, raw[(scope, path, raw_phase, level)], False) for level in levels
        ]

    output: dict[tuple[str, str, str, str], HardResult] = {}
    base_tolerances: dict[str, float] = {
        "exact_mass_ok": 0.0,
        "exact_clock_ok": 0.0,
        "max_p2g_mass_error": MASS_TOLERANCE,
        "max_p2g_linear_error": LINEAR_TOLERANCE,
        "max_g2p_linear_error": LINEAR_TOLERANCE,
        "max_p2g_paper_augmented_angular_error": ANGULAR_TOLERANCE,
        "max_g2p_paper_augmented_angular_error": ANGULAR_TOLERANCE,
        "static_grid_error": STATIC_TOLERANCE,
        "nonfinite_or_missing_count": 0.0,
        "configuration_error_count": 0.0,
        "id_error_count": 0.0,
    }
    causal_columns = {
        "first_step_D_stationarity_error": "D_stationarity_error",
        "first_step_B_identity_error": "B_identity_error",
        "first_step_C_retention_error": "C_retention_error",
        "first_step_discrepancy_witness_error": "discrepancy_witness_error",
        "oracle_first_step_C_exact_error": "oracle_C_exact_error",
    }
    for family, family_rows in families.items():
        scope, path, phase = family
        ordered = sorted(family_rows, key=lambda item: item[0])
        sealed_family = ordered[0][2]
        for gate in GATE_NAMES:
            key = scope, path, phase, gate
            if gate in base_tolerances:
                values: list[tuple[int, float]] = []
                for level, row, is_sealed in ordered:
                    if gate in {"exact_mass_ok", "exact_clock_ok"}:
                        value = 0.0 if parse_bool(row[gate], f"hard.{family}.{gate}") else 1.0
                    elif gate in {"nonfinite_or_missing_count", "configuration_error_count", "id_error_count"}:
                        value = (
                            0.0 if is_sealed
                            else float(parse_int(row[gate], f"hard.{family}.{gate}"))
                        )
                    else:
                        value = parse_float(row[gate], f"hard.{family}.{gate}")
                    values.append((level, value))
                output[key] = hard_result(values, base_tolerances[gate])
                continue
            if gate == "oracle_B_constraint_error":
                if path != PATH_ORACLE or sealed_family:
                    output[key] = inapplicable_hard()
                else:
                    values = [
                        (level, parse_float(row[gate], f"hard.{family}.{gate}"))
                        for level, row, _ in ordered
                    ]
                    output[key] = hard_result(values, STATIC_TOLERANCE)
                continue
            if gate in causal_columns:
                oracle_only = gate == "oracle_first_step_C_exact_error"
                if scope != "co_refinement" or (oracle_only and path != PATH_ORACLE):
                    output[key] = inapplicable_hard()
                    continue
                column = causal_columns[gate]
                values = []
                for level, _, _ in ordered:
                    control = causal[(path, phase, level)]
                    values.append((level, parse_float(control[column], f"hard.{family}.{gate}")))
                output[key] = hard_result(values, STATIC_TOLERANCE)
                continue
            raise AssertionError(f"unhandled hard gate {gate}")
    return output


def validate_hard_rows(
    audit: Audit,
    rows: Sequence[Mapping[str, str]],
    expected: Mapping[tuple[str, str, str, str], HardResult],
) -> dict[tuple[str, str, str, str], HardResult]:
    observed: set[tuple[str, str, str, str]] = set()
    for line, row in enumerate(rows, 2):
        label = f"hard_gates.csv:{line}"
        common_row(audit, row, label)
        key = row["scope"], row["path"], row["phase"], row["gate"]
        audit.check(key in expected, f"{label}: unregistered hard family {key!r}")
        audit.check(key not in observed, f"{label}: duplicate hard family {key!r}")
        if key not in expected or key in observed:
            continue
        observed.add(key)
        result = expected[key]
        audit.check(parse_bool(row["applicable"], label) == result.applicable,
                    f"{label}: applicability mismatch")
        audit.check(parse_int(row["expected_configurations"], label)
                    == result.expected_configurations,
                    f"{label}: expected configuration count mismatch")
        audit.check(parse_int(row["evaluated_configurations"], label)
                    == result.evaluated_configurations,
                    f"{label}: evaluated configuration count mismatch")
        audit.check(parse_int(row["failure_count"], label) == result.failure_count,
                    f"{label}: failure count mismatch")
        if result.worst_value is None:
            audit.check(row["worst_value"] == "NA", f"{label}: worst value must be NA")
            audit.check(row["tolerance"] == "NA", f"{label}: tolerance must be NA")
            audit.check(row["worst_configuration"] == "NA",
                        f"{label}: worst configuration must be NA")
        else:
            audit.check_float(parse_float(row["worst_value"], label), result.worst_value,
                              f"{label}: worst value")
            assert result.tolerance is not None
            audit.check_float(parse_float(row["tolerance"], label), result.tolerance,
                              f"{label}: tolerance")
            audit.check(row["worst_configuration"] == result.worst_configuration,
                        f"{label}: worst configuration mismatch")
        audit.check(parse_bool(row["pass"], label) == result.passes,
                    f"{label}: pass mismatch")
    audit.check(observed == set(expected), "hard-gate family set differs")
    return dict(expected)


def compute_path_gates(
    convergence_results: Mapping[tuple[str, str, str, str], ConvergenceResult],
    hard_results: Mapping[tuple[str, str, str, str], HardResult],
) -> dict[str, dict[str, bool]]:
    output: dict[str, dict[str, bool]] = {}
    for path in (PATH_E, PATH_ORACLE):
        core_convergence = [
            result for (scope, row_path, _, _), result in convergence_results.items()
            if row_path == path and scope in {"co_refinement", "phase_sensitivity"}
        ]
        density_convergence = [
            result for (scope, row_path, _, _), result in convergence_results.items()
            if row_path == path and scope == "particles_per_cell"
        ]
        core_hard = [
            result for (scope, row_path, _, _), result in hard_results.items()
            if row_path == path and scope == "co_refinement"
        ]
        density_hard = [
            result for (scope, row_path, _, _), result in hard_results.items()
            if row_path == path and scope == "particles_per_cell"
        ]
        output[path] = {
            "core_pass": bool(core_convergence and core_hard)
            and all(result.passes for result in core_convergence)
            and all(result.passes for result in core_hard),
            "density_pass": bool(density_convergence and density_hard)
            and all(result.passes for result in density_convergence)
            and all(result.passes for result in density_hard),
        }
    return output


def compute_metric_partitions(
    convergence_results: Mapping[tuple[str, str, str, str], ConvergenceResult],
) -> dict[str, list[str]]:
    partitions = {
        "E_fail_oracle_pass": [],
        "E_fail_oracle_fail": [],
        "E_pass_oracle_fail": [],
        "both_pass": [],
    }
    for scope in ("co_refinement", "particles_per_cell", "phase_sensitivity"):
        phases = sorted({
            phase for (row_scope, path, phase, _) in convergence_results
            if row_scope == scope and path == PATH_E
        })
        for phase in phases:
            metrics = sorted({
                metric for (row_scope, path, row_phase, metric) in convergence_results
                if row_scope == scope and path == PATH_E and row_phase == phase
            })
            for metric in metrics:
                e = convergence_results[(scope, PATH_E, phase, metric)].passes
                oracle = convergence_results[(scope, PATH_ORACLE, phase, metric)].passes
                token = f"{scope}|{phase}|{metric}"
                if not e and oracle:
                    partitions["E_fail_oracle_pass"].append(token)
                elif not e and not oracle:
                    partitions["E_fail_oracle_fail"].append(token)
                elif e and not oracle:
                    partitions["E_pass_oracle_fail"].append(token)
                else:
                    partitions["both_pass"].append(token)
    return partitions


def compute_decision(path_gates: Mapping[str, Mapping[str, bool]]) -> str:
    e_core = path_gates[PATH_E]["core_pass"]
    e_density = path_gates[PATH_E]["density_pass"]
    oracle_core = path_gates[PATH_ORACLE]["core_pass"]
    oracle_density = path_gates[PATH_ORACLE]["density_pass"]
    if e_core and oracle_core:
        if e_density:
            return "E remains viable for research under proper co-refinement; no promotion"
        return (
            "E remains viable under proper co-refinement with unresolved "
            "quadrature-density behavior; no promotion"
        )
    if e_core and not oracle_core:
        return (
            "E remains viable from proper co-refinement but E_oracleB is invalid "
            "for causal attribution; no promotion"
        )
    if not e_core and not oracle_core:
        return (
            "reject standard JST moving APIC; both E and E_oracleB fail, "
            "remaining defect classified as projection/quadrature"
        )
    if not e_density and oracle_density:
        return (
            "reject standard JST moving APIC; E fails while E_oracleB passes core "
            "and density, supporting affine-state mismatch"
        )
    if not e_density and not oracle_density:
        return (
            "reject standard JST moving APIC; affine-state support coexists with "
            "remaining density projection/quadrature"
        )
    return (
        "reject standard JST moving APIC; proper co-refinement and density "
        "sequences disagree"
    )


def validate_counts(
    audit: Audit,
    actual: Mapping[str, int],
) -> None:
    expected = FULL_COUNTS if audit.mode == "full" else SMOKE_COUNTS
    for name, wanted in expected.items():
        audit.check(actual.get(name) == wanted,
                    f"{name}: {actual.get(name)} rows != {wanted}")
    primary = actual["fixed_particle_control"] + actual["co_refinement"] + actual["particles_per_cell"]
    all_rows = primary + actual["phase_sensitivity"] + actual["causal_controls"]
    audit.check(primary == (30 if audit.mode == "full" else 4),
                "primary raw-row count differs")
    audit.check(all_rows == (48 if audit.mode == "full" else 6),
                "all raw/control-row count differs")
    counts = audit.summary.get("counts")
    audit.check(isinstance(counts, dict), "summary counts must be an object")
    if not isinstance(counts, dict):
        return
    audit.check(set(counts) == set(expected), "summary counts have missing or extra keys")
    for name, wanted in expected.items():
        entry = counts.get(name)
        audit.check(isinstance(entry, dict), f"summary counts.{name} must be an object")
        if isinstance(entry, dict):
            audit.check(entry.get("expected") == wanted,
                        f"summary counts.{name}.expected mismatch")
            audit.check(entry.get("actual") == actual[name],
                        f"summary counts.{name}.actual mismatch")
    audit.check(audit.summary.get("counts_complete") is True,
                "summary counts_complete must be true")


def files_identical(left: Path, right: Path) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as first, right.open("rb") as second:
        while True:
            one = first.read(1024 * 1024)
            two = second.read(1024 * 1024)
            if one != two:
                return False
            if not one:
                return True


def compare_bundles(first: Audit, second: Audit) -> None:
    first.check(first.mode == second.mode, "comparison mode differs")
    first_files = set(first.hashes)
    second_files = set(second.hashes)
    first.check(first_files == second_files, "comparison file sets differ")
    for relative in sorted(first_files & second_files):
        first.check(first.hashes[relative] == second.hashes[relative],
                    f"comparison hash differs: {relative}")
        first.check(files_identical(first.bundle / relative, second.bundle / relative),
                    f"comparison bytes differ: {relative}")


def validate_summary_policy(audit: Audit) -> None:
    summary = audit.summary
    expected_keys = {
        "schema", "mode", "seed", "source", "compiler", "units",
        "counts_complete", "counts", "prerequisites_complete",
        "decision_primitives", "metric_partitions", "computational_decision",
        "decision", "path_E_promotion_eligible",
        "path_E_oracleB_promotion_eligible", "energy_policy",
        "overall_recommendation",
    }
    audit.check(set(summary) == expected_keys, "summary has missing or extra keys")
    audit.check(summary.get("schema") == SCHEMA, "wrong summary schema")
    audit.check(summary.get("mode") == audit.mode, "summary mode mismatch")
    audit.check(summary.get("seed") == SEED, "wrong summary seed")
    audit.check(summary.get("path_E_promotion_eligible") is False,
                "Path E must remain promotion-ineligible")
    audit.check(summary.get("path_E_oracleB_promotion_eligible") is False,
                "E_oracleB must remain promotion-ineligible")
    units = summary.get("units")
    audit.check(units == {
        "time_quantum_s": "1/160",
        "mass_quantum_kg": "1/4096",
        "horizon_s": "1/10",
    }, "wrong summary units")
    compiler = summary.get("compiler")
    audit.check(isinstance(compiler, dict)
                and set(compiler) == {"id", "version"}
                and isinstance(compiler.get("id"), str) and bool(compiler.get("id"))
                and isinstance(compiler.get("version"), str) and bool(compiler.get("version")),
                "missing compiler provenance")
    audit.check(summary.get("energy_policy") ==
                "center particle kinetic energy is physical; affine and augmented quantities are diagnostics only",
                "wrong energy-separation policy")
    audit.check(summary.get("overall_recommendation") ==
                "no promotion; stop for head-agent review",
                "wrong mandatory stop recommendation")
    if audit.mode == "smoke":
        audit.check(audit.smoke_provisional, "smoke requires --smoke-provisional")
        audit.check(summary.get("computational_decision") == "smoke provisional; no verdict",
                    "smoke issued a computational verdict")
        audit.check(summary.get("decision") ==
                    "no viability or causal verdict: external prerequisites or completeness gate pending",
                    "smoke issued a final verdict")
        audit.check(summary.get("decision_primitives") == {
            "E": {"core_pass": False, "density_pass": False},
            "E_oracleB": {"core_pass": False, "density_pass": False},
        }, "smoke decision primitives must all be false")
        audit.check(summary.get("metric_partitions") == {
            "E_fail_oracle_pass": {"count": 0, "groups": []},
            "E_fail_oracle_fail": {"count": 0, "groups": []},
            "E_pass_oracle_fail": {"count": 0, "groups": []},
            "both_pass": {"count": 0, "groups": []},
        }, "smoke metric partitions must be empty")


def validate_summary_results(
    audit: Audit,
    path_gates: Mapping[str, Mapping[str, bool]],
    partitions: Mapping[str, Sequence[str]],
    decision: str,
    sealed_source_verified: bool,
) -> None:
    if audit.mode != "full":
        return
    summary = audit.summary
    reported_paths = summary.get("decision_primitives")
    audit.check(isinstance(reported_paths, dict),
                "summary decision_primitives must be an object")
    if isinstance(reported_paths, dict):
        for path, summary_name in ((PATH_E, "E"), (PATH_ORACLE, "E_oracleB")):
            values = path_gates[path]
            actual = reported_paths.get(summary_name)
            audit.check(isinstance(actual, dict),
                        f"summary decision_primitives.{summary_name} missing")
            if isinstance(actual, dict):
                for name, value in values.items():
                    audit.check(actual.get(name) == value,
                                f"summary decision_primitives.{summary_name}.{name} mismatch")
    reported_partitions = summary.get("metric_partitions")
    audit.check(isinstance(reported_partitions, dict),
                "summary metric_partitions must be an object")
    if isinstance(reported_partitions, dict):
        for name, values in partitions.items():
            entry = reported_partitions.get(name)
            if isinstance(entry, dict):
                audit.check(entry.get("count") == len(values),
                            f"summary partition {name} count mismatch")
                audit.check(entry.get("groups") == list(values),
                            f"summary partition {name} groups mismatch")
            else:
                audit.check(entry == list(values), f"summary partition {name} mismatch")
    audit.check(summary.get("computational_decision") == decision,
                "summary computational decision mismatch")
    audit.check(summary.get("decision") ==
                "no viability or causal verdict: external prerequisites or completeness gate pending",
                "producer must retain pending external-prerequisite verdict")
    prerequisite_complete = summary.get("prerequisites_complete")
    audit.check(prerequisite_complete is False,
                "producer prerequisites_complete must retain deferred source/tag gates")
    if sealed_source_verified:
        # This is the verifier's external result, intentionally not rewritten
        # into the producer-owned summary.
        pass


def build_audit(bundle: Path, smoke_provisional: bool) -> Audit:
    if not bundle.is_dir():
        raise BundleError(f"bundle directory does not exist: {bundle}")
    summary_path = bundle / "summary.json"
    if not summary_path.is_file():
        raise BundleError("bundle is missing summary.json")
    summary = load_summary(summary_path)
    mode = summary.get("mode")
    if mode not in {"full", "smoke"}:
        raise BundleError(f"summary mode must be full or smoke, got {mode!r}")
    missing = [name for name in REQUIRED_FILES if not (bundle / name).is_file()]
    if mode == "full" and not (bundle / "fixed_particle_control.csv").is_file():
        missing.append("fixed_particle_control.csv")
    if missing:
        raise BundleError(f"bundle is missing required files: {missing!r}")
    return Audit(bundle, summary, mode, smoke_provisional)


def validate_bundle(
    bundle: Path,
    *,
    smoke_provisional: bool,
    source_sha: str | None,
    source_branch: str | None,
    require_clean: bool,
    sealed_source_repository: Path | None,
    require_sealed_source: bool,
) -> Audit:
    audit = build_audit(bundle, smoke_provisional)
    audit.hashes = file_manifest(bundle)
    validate_summary_policy(audit)
    validate_analytic_contract(audit)
    sealed, sealed_csv_hash, sealed_header_hash = validate_sealed_control(audit)
    co_rows = read_csv(bundle / "co_refinement.csv", RAW_FIELDS)
    ppc_rows = read_csv(bundle / "particles_per_cell.csv", RAW_FIELDS)
    phase_rows = read_csv(bundle / "phase_sensitivity.csv", PHASE_FIELDS)
    causal_rows = read_csv(bundle / "causal_controls.csv", CAUSAL_FIELDS)
    convergence_rows = read_csv(bundle / "convergence.csv", CONVERGENCE_FIELDS)
    hard_rows = read_csv(bundle / "hard_gates.csv", HARD_FIELDS)
    prerequisite_rows = read_csv(bundle / "prerequisites.csv", PREREQUISITE_FIELDS)
    actual_counts = {
        "fixed_particle_control": len(sealed),
        "co_refinement": len(co_rows),
        "particles_per_cell": len(ppc_rows),
        "phase_sensitivity": len(phase_rows),
        "causal_controls": len(causal_rows),
        "convergence": len(convergence_rows),
        "hard_gates": len(hard_rows),
        "prerequisites": len(prerequisite_rows),
    }
    validate_counts(audit, actual_counts)
    raw = validate_raw_rows(audit, {
        "co_refinement": co_rows,
        "particles_per_cell": ppc_rows,
    })
    phase = validate_phase_rows(audit, phase_rows)
    causal = validate_causal_rows(audit, causal_rows)
    validate_prerequisites(
        audit, prerequisite_rows, sealed_csv_hash, sealed_header_hash
    )
    if audit.mode == "full":
        expected_convergence_rows = expected_convergence(sealed, raw, phase)
    else:
        expected_convergence_rows = {}
    convergence_results = validate_convergence_rows(
        audit, convergence_rows, expected_convergence_rows
    )
    hard_results = validate_hard_rows(
        audit, hard_rows, expected_hard_results(audit, sealed, raw, causal)
    )
    repository = sealed_source_repository or Path(__file__).resolve().parents[1]
    sealed_source_verified = (
        validate_sealed_source(audit, repository, require_sealed_source)
        if audit.mode == "full" else False
    )
    if audit.mode == "full":
        path_gates = compute_path_gates(convergence_results, hard_results)
        partitions = compute_metric_partitions(convergence_results)
        decision = compute_decision(path_gates)
        validate_summary_results(
            audit, path_gates, partitions, decision, sealed_source_verified
        )
    validate_provenance(audit, source_sha, source_branch, require_clean)
    return audit


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="independently validate an MLS Moving APIC Limit Lab bundle"
    )
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--compare", type=Path,
                        help="validate and require a byte-identical second bundle")
    parser.add_argument("--smoke-provisional", action="store_true",
                        help="accept smoke output as provisional and issue no verdict")
    parser.add_argument("--source-sha")
    parser.add_argument("--source-branch")
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument("--sealed-source-repository", type=Path,
                        help="Git repository used for accepted Path E source/tag verification")
    parser.add_argument("--require-sealed-source", action="store_true",
                        help="fail unless the accepted tag and three Path E files verify")
    return parser.parse_args(argv)


def print_manifest(label: str, hashes: Mapping[str, str]) -> None:
    print(f"sha256_manifest[{label}]=")
    print(json.dumps(dict(sorted(hashes.items())), sort_keys=True, indent=2))


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        audit = validate_bundle(
            arguments.bundle.resolve(),
            smoke_provisional=arguments.smoke_provisional,
            source_sha=arguments.source_sha,
            source_branch=arguments.source_branch,
            require_clean=arguments.require_clean,
            sealed_source_repository=(
                arguments.sealed_source_repository.resolve()
                if arguments.sealed_source_repository else None
            ),
            require_sealed_source=arguments.require_sealed_source,
        )
        comparison: Audit | None = None
        if arguments.compare is not None:
            comparison = validate_bundle(
                arguments.compare.resolve(),
                smoke_provisional=arguments.smoke_provisional,
                source_sha=arguments.source_sha,
                source_branch=arguments.source_branch,
                require_clean=arguments.require_clean,
                sealed_source_repository=(
                    arguments.sealed_source_repository.resolve()
                    if arguments.sealed_source_repository else None
                ),
                require_sealed_source=arguments.require_sealed_source,
            )
            compare_bundles(audit, comparison)
    except BundleError as error:
        print(f"MOVING APIC LIMIT BUNDLE INVALID: {error}", file=sys.stderr)
        return 1
    errors = list(audit.errors)
    if comparison is not None:
        errors.extend(f"comparison: {message}" for message in comparison.errors)
    if errors:
        print(f"MOVING APIC LIMIT BUNDLE INVALID: {len(errors)} mismatch(es)", file=sys.stderr)
        for message in errors[:250]:
            print(f"  - {message}", file=sys.stderr)
        if len(errors) > 250:
            print(f"  - ... {len(errors) - 250} more", file=sys.stderr)
        print_manifest("primary", audit.hashes)
        return 1
    status = "SMOKE PROVISIONAL" if audit.mode == "smoke" else "VALID"
    print(f"MOVING APIC LIMIT BUNDLE {status}")
    print(f"schema={SCHEMA} mode={audit.mode} seed={SEED}")
    print(f"byte_identical_comparison={'yes' if comparison else 'not requested'}")
    print_manifest("primary", audit.hashes)
    if comparison is not None:
        print_manifest("comparison", comparison.hashes)
    print("scope=evidence consistency only; no transfer promotion or mechanics validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
