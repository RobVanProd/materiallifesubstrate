#!/usr/bin/env python3
"""Independent validator for an MLS Affine Advection Lab evidence bundle.

The validator deliberately reconstructs the preregistered Cartesian products,
applicability rules, convergence evaluations, causal diagnosis, and Path E gate
from the CSV evidence.  It does not import or call the C++ implementation.

This validates evidence consistency only.  It does not validate continuum
mechanics or make any transfer path eligible for promotion.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA = "mls-affine-advection-diagnostic-v1"
SEED = 260828
TIME_QUANTUM_SECONDS = 1.0 / 80.0
HORIZON_QUANTA = 8

MASS_TOLERANCE = 2.0e-13
LINEAR_TOLERANCE = 2.0e-12
ANGULAR_TOLERANCE = 2.0e-11
TRANSLATION_STATIC_TOLERANCE = 2.0e-12
AFFINE_STATIC_TOLERANCE = 5.0e-11
HORIZON_TOLERANCE = 2.0e-9
ROUND_OFF_FLOOR = 5.0e-14

FIELDS = ("translation", "rigid_rotation", "general_affine")
ORIENTATIONS = (
    (0, "p012_sppp"),
    (1, "p120_sppp"),
    (2, "p210_sppm"),
)
LAYOUT_MASS = (
    ("regular_2x2x2", 1),
    ("unequal_mass_asymmetric", 17),
    ("seeded_jittered_27", 1),
)
DT_QUANTA = (8, 4, 2, 1)
PATH_A = "A_analytic_ballistic"
PATH_B = "B_frozen_static_APIC"
PATH_C = "C_sealed_static_APIC_ballistic"
PATH_D = "D_analytic_convected_affine_control"
PATH_E = "E_JST2017_moving_APIC"
PATHS = (PATH_A, PATH_B, PATH_C, PATH_D, PATH_E)

REQUIRED_FILES = (
    "single_particle_sanity.csv",
    "core_sweep.csv",
    "coupled_refinement.csv",
    "convergence.csv",
    "summary.json",
)

SANITY_FIELDS = (
    "mode", "seed", "field", "phase_index", "orientation_index", "orientation",
    "dt_quanta", "dt_seconds", "steps", "exact_mass_ok", "exact_clock_ok",
    "position_error", "velocity_error", "B_error",
    "center_physical_kinetic_error", "pass",
)

RAW_FIELDS = (
    "mode", "seed", "scope", "path", "field", "phase_index",
    "orientation_index", "orientation", "layout", "mass_ratio",
    "schedule_index", "step_or_remap_count", "grid_spacing_m", "dt_quanta",
    "dt_seconds", "physical_time_applicable", "elapsed_quanta", "exact_mass_ok",
    "exact_clock_ok", "static_representation_applicable", "static_velocity_error",
    "static_affine_error", "static_grid_error", "affine_advection_applicable",
    "affine_gradient_error", "affine_intercept_error", "affine_dispersion_error",
    "stale_witness_applicable", "stale_gradient_witness_error",
    "trajectory_applicable", "trajectory_position_error", "material_velocity_error",
    "linear_momentum_error", "center_orbital_error", "center_physical_kinetic_error",
    "max_p2g_mass_error", "max_p2g_linear_error",
    "max_p2g_paper_augmented_angular_error", "max_g2p_linear_error",
    "max_g2p_paper_augmented_angular_error",
    "max_abs_p2g_center_energy_residual_j",
    "max_abs_p2g_augmented_representation_energy_residual_j",
    "terminal_affine_auxiliary_energy_diagnostic_j",
    "terminal_augmented_representation_energy_diagnostic_j",
)

CONVERGENCE_FIELDS = (
    "mode", "seed", "scope", "path", "field", "phase_index",
    "orientation_index", "orientation", "layout", "mass_ratio", "metric",
    "hard_tolerance", "error_level_0", "error_level_1", "error_level_2",
    "error_level_3", "all_below", "ratio_rule", "finest_increase_failure", "pass",
)

STATIC_OPTIONALS = (
    "static_velocity_error", "static_affine_error", "static_grid_error",
)
AFFINE_OPTIONALS = (
    "affine_gradient_error", "affine_intercept_error", "affine_dispersion_error",
)
TRAJECTORY_OPTIONALS = (
    "trajectory_position_error", "material_velocity_error", "linear_momentum_error",
    "center_orbital_error", "center_physical_kinetic_error",
)
ALWAYS_NUMERIC_RAW = (
    "max_p2g_mass_error", "max_p2g_linear_error",
    "max_p2g_paper_augmented_angular_error", "max_g2p_linear_error",
    "max_g2p_paper_augmented_angular_error",
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

SUMMARY_KEYS = {
    "schema", "mode", "selection_or_promotion_evidence", "source_sha_at_configure",
    "source_branch_at_configure", "source_dirty_at_configure", "compiler_id",
    "compiler_version", "seed", "time_quantum_seconds", "fixed_horizon_seconds",
    "single_particle_gate_pass", "counts_complete", "counts", "energy_policy",
    "path_d_promotion_eligible", "path_e_promotion_eligible", "causal_diagnosis",
    "path_e_literature_and_mls_gate", "overall_recommendation",
    "external_gates_required", "excluded",
}


class BundleError(RuntimeError):
    """A bundle cannot be parsed or is structurally unusable."""


def no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BundleError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest(bundle: Path) -> dict[str, str]:
    return {
        path.relative_to(bundle).as_posix(): sha256_file(path)
        for path in sorted(bundle.rglob("*"))
        if path.is_file()
    }


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


def parse_optional(value: str, label: str) -> float | None:
    return None if value == "NA" else parse_float(value, label)


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=2.0e-15, abs_tol=2.0e-18)


def read_csv(path: Path, expected_header: Sequence[str]) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != tuple(expected_header):
                raise BundleError(
                    f"{path.name}: header differs from schema\n"
                    f"expected={list(expected_header)!r}\nactual={reader.fieldnames!r}"
                )
            rows = list(reader)
    except OSError as error:
        raise BundleError(f"cannot read {path}: {error}") from error
    for number, row in enumerate(rows, 2):
        if None in row:
            raise BundleError(f"{path.name}:{number}: extra CSV field(s)")
        if any(value is None for value in row.values()):
            raise BundleError(f"{path.name}:{number}: missing CSV field")
    return rows


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

    def check_float(self, actual: float, expected: float, label: str) -> None:
        self.check(close(actual, expected), f"{label}: {actual:.17g} != {expected:.17g}")


def load_summary(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicate_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BundleError(f"cannot parse summary.json: {error}") from error
    if not isinstance(loaded, dict):
        raise BundleError("summary.json must contain a JSON object")
    return loaded


def expected_counts(mode: str) -> dict[str, int]:
    if mode == "smoke":
        return {
            "single_particle_sanity": 4,
            "core_sweep": 20,
            "coupled_refinement": 0,
            "convergence": 41,
        }
    return {
        "single_particle_sanity": 72,
        "core_sweep": 1080,
        "coupled_refinement": 12,
        "convergence": 2247,
    }


def mode_axes(mode: str) -> tuple[tuple[str, ...], tuple[int, ...], tuple[tuple[int, str], ...], tuple[tuple[str, int], ...]]:
    if mode == "smoke":
        return ((FIELDS[0],), (0,), (ORIENTATIONS[0],), (LAYOUT_MASS[0],))
    return (FIELDS, (0, 1), ORIENTATIONS, LAYOUT_MASS)


def validate_summary_policy(audit: Audit) -> None:
    summary = audit.summary
    audit.check(set(summary) == SUMMARY_KEYS, "summary.json has missing or extra top-level keys")
    audit.check(summary.get("schema") == SCHEMA, "wrong summary schema")
    audit.check(summary.get("mode") == audit.mode, "summary mode mismatch")
    audit.check(summary.get("seed") == SEED, "wrong summary seed")
    audit.check(summary.get("selection_or_promotion_evidence") is False,
                "lab must not claim selection or promotion evidence")
    audit.check(summary.get("time_quantum_seconds") == "1/80", "wrong time quantum")
    audit.check(summary.get("fixed_horizon_seconds") == "1/10", "wrong fixed horizon")
    audit.check(summary.get("path_d_promotion_eligible") is False,
                "Path D must remain promotion-ineligible")
    audit.check(summary.get("path_e_promotion_eligible") is False,
                "Path E must remain promotion-ineligible")
    audit.check(summary.get("overall_recommendation") ==
                "no promotion; stop for head-agent review", "wrong stop recommendation")
    audit.check(summary.get("energy_policy") ==
                "center particle kinetic energy is physical; affine and augmented quantities are diagnostics only",
                "energy policy differs from preregistration")
    sha = summary.get("source_sha_at_configure")
    branch = summary.get("source_branch_at_configure")
    dirty = summary.get("source_dirty_at_configure")
    audit.check(isinstance(sha, str) and (sha == "unknown" or re.fullmatch(r"[0-9a-f]{40}", sha) is not None),
                "malformed configure-time source SHA")
    audit.check(isinstance(branch, str) and bool(branch), "missing configure-time source branch")
    audit.check(dirty in {"true", "false"}, "source_dirty_at_configure must be true/false string")
    audit.check(isinstance(summary.get("compiler_id"), str) and bool(summary.get("compiler_id")),
                "missing compiler ID")
    audit.check(isinstance(summary.get("compiler_version"), str) and bool(summary.get("compiler_version")),
                "missing compiler version")
    if audit.mode == "smoke":
        audit.check(audit.smoke_provisional, "smoke bundles require --smoke-provisional")
        audit.check(summary.get("causal_diagnosis") is None,
                    "smoke summary must not issue a causal diagnosis")
        audit.check(summary.get("path_e_literature_and_mls_gate") is None,
                    "smoke summary must not issue a Path E gate result")


def validate_counts_summary(audit: Audit, actual: Mapping[str, int]) -> None:
    expected = expected_counts(audit.mode)
    counts = audit.summary.get("counts")
    if not isinstance(counts, dict):
        audit.check(False, "summary counts must be an object")
        return
    audit.check(set(counts) == set(expected), "summary counts have missing or extra keys")
    for key, wanted in expected.items():
        entry = counts.get(key)
        audit.check(isinstance(entry, dict), f"summary counts.{key} must be an object")
        if isinstance(entry, dict):
            audit.check(set(entry) == {"expected", "actual"}, f"summary counts.{key} keys")
            audit.check(entry.get("expected") == wanted, f"summary counts.{key}.expected")
            audit.check(entry.get("actual") == actual[key], f"summary counts.{key}.actual")
        audit.check(actual[key] == wanted, f"{key}: {actual[key]} rows != expected {wanted}")
    complete = all(actual[key] == value for key, value in expected.items())
    audit.check(audit.summary.get("counts_complete") is complete,
                "summary counts_complete differs from independent counts")


def validate_common_row(audit: Audit, row: Mapping[str, str], label: str) -> None:
    audit.check(row["mode"] == audit.mode, f"{label}: wrong mode")
    audit.check(parse_int(row["seed"], f"{label}.seed") == SEED, f"{label}: wrong seed")


def validate_sanity(audit: Audit, rows: list[dict[str, str]]) -> None:
    fields, phases, orientations, _ = mode_axes(audit.mode)
    expected = set(itertools.product(fields, phases, orientations, DT_QUANTA))
    observed: set[tuple[str, int, tuple[int, str], int]] = set()
    all_pass = True
    for index, row in enumerate(rows, 2):
        label = f"single_particle_sanity.csv:{index}"
        validate_common_row(audit, row, label)
        field_name = row["field"]
        phase = parse_int(row["phase_index"], f"{label}.phase_index")
        orientation = (
            parse_int(row["orientation_index"], f"{label}.orientation_index"),
            row["orientation"],
        )
        dt = parse_int(row["dt_quanta"], f"{label}.dt_quanta")
        if dt not in DT_QUANTA:
            raise BundleError(f"{label}: unregistered timestep quanta {dt}")
        key = (field_name, phase, orientation, dt)
        audit.check(key not in observed, f"{label}: duplicate axis tuple {key!r}")
        observed.add(key)
        audit.check(key in expected, f"{label}: unregistered axis tuple {key!r}")
        audit.check(parse_int(row["steps"], f"{label}.steps") == HORIZON_QUANTA // dt,
                    f"{label}: wrong step count")
        audit.check_float(parse_float(row["dt_seconds"], f"{label}.dt_seconds"),
                          dt * TIME_QUANTUM_SECONDS, f"{label}.dt_seconds")
        exact_mass = parse_bool(row["exact_mass_ok"], f"{label}.exact_mass_ok")
        exact_clock = parse_bool(row["exact_clock_ok"], f"{label}.exact_clock_ok")
        errors = [
            parse_float(row[name], f"{label}.{name}")
            for name in ("position_error", "velocity_error", "B_error",
                         "center_physical_kinetic_error")
        ]
        audit.check(all(value >= 0.0 for value in errors), f"{label}: negative error")
        expected_pass = exact_mass and exact_clock and all(
            value <= HORIZON_TOLERANCE for value in errors
        )
        reported_pass = parse_bool(row["pass"], f"{label}.pass")
        audit.check(reported_pass is expected_pass, f"{label}: pass flag not recomputed result")
        audit.check(exact_mass, f"{label}: exact mass failed")
        audit.check(exact_clock, f"{label}: exact clock failed")
        all_pass = all_pass and expected_pass
    audit.check(observed == expected, "single-particle axes are incomplete or contain extras")
    audit.check(audit.summary.get("single_particle_gate_pass") is all_pass,
                "summary single-particle gate differs from CSV")
    audit.check(all_pass, "mandatory single-particle sanity gate failed")


def raw_family(row: Mapping[str, str], label: str) -> tuple[str, int, int, str, str, int]:
    return (
        row["field"],
        parse_int(row["phase_index"], f"{label}.phase_index"),
        parse_int(row["orientation_index"], f"{label}.orientation_index"),
        row["orientation"], row["layout"],
        parse_int(row["mass_ratio"], f"{label}.mass_ratio"),
    )


def expected_core_keys(mode: str) -> set[tuple[Any, ...]]:
    fields, phases, orientations, layouts = mode_axes(mode)
    return {
        (field_name, phase, orientation_index, orientation_label, layout, mass,
         path, schedule)
        for field_name, phase, (orientation_index, orientation_label), (layout, mass), path, schedule
        in itertools.product(fields, phases, orientations, layouts, PATHS, range(4))
    }


def expected_coupled_keys(mode: str) -> set[tuple[Any, ...]]:
    if mode == "smoke":
        return set()
    return {
        ("general_affine", 1, 2, "p210_sppm", "unequal_mass_asymmetric", 17,
         path, schedule)
        for path in (PATH_C, PATH_D, PATH_E)
        for schedule in range(4)
    }


def validate_optional_group(
    audit: Audit, row: Mapping[str, str], label: str, flag: str,
    names: Sequence[str], applicable: bool,
) -> None:
    actual_flag = parse_bool(row[flag], f"{label}.{flag}")
    audit.check(actual_flag is applicable, f"{label}: wrong {flag}")
    for name in names:
        value = parse_optional(row[name], f"{label}.{name}")
        audit.check((value is not None) is applicable,
                    f"{label}: {name} NA/applicability mismatch")
        if value is not None:
            audit.check(value >= 0.0, f"{label}: negative {name}")


def validate_raw_rows(
    audit: Audit, rows: list[dict[str, str]], scope: str,
) -> dict[tuple[Any, ...], dict[str, str]]:
    expected = expected_core_keys(audit.mode) if scope == "core" else expected_coupled_keys(audit.mode)
    observed: dict[tuple[Any, ...], dict[str, str]] = {}
    for index, row in enumerate(rows, 2):
        filename = "core_sweep.csv" if scope == "core" else "coupled_refinement.csv"
        label = f"{filename}:{index}"
        validate_common_row(audit, row, label)
        audit.check(row["scope"] == scope, f"{label}: wrong scope")
        family = raw_family(row, label)
        path = row["path"]
        schedule = parse_int(row["schedule_index"], f"{label}.schedule_index")
        if schedule not in range(4):
            raise BundleError(f"{label}: schedule index must be in [0,3], got {schedule}")
        key = (*family, path, schedule)
        audit.check(key not in observed, f"{label}: duplicate axis tuple {key!r}")
        observed[key] = row
        audit.check(key in expected, f"{label}: unregistered axis tuple {key!r}")

        dt = DT_QUANTA[schedule] if 0 <= schedule < 4 else -1
        count = HORIZON_QUANTA // dt if dt > 0 else -1
        physical = path != PATH_B
        audit.check(parse_int(row["step_or_remap_count"], f"{label}.step_or_remap_count") == count,
                    f"{label}: wrong step/remap count")
        expected_spacing = 0.5 if scope == "core" else (1.0, 0.5, 0.25, 0.125)[schedule]
        audit.check_float(parse_float(row["grid_spacing_m"], f"{label}.grid_spacing_m"),
                          expected_spacing, f"{label}.grid_spacing_m")
        actual_dt = parse_int(row["dt_quanta"], f"{label}.dt_quanta")
        actual_dt_seconds = parse_float(row["dt_seconds"], f"{label}.dt_seconds")
        audit.check(actual_dt == (dt if physical else 0), f"{label}: wrong dt quanta")
        audit.check_float(actual_dt_seconds, dt * TIME_QUANTUM_SECONDS if physical else 0.0,
                          f"{label}.dt_seconds")
        audit.check(parse_bool(row["physical_time_applicable"], f"{label}.physical_time_applicable") is physical,
                    f"{label}: wrong physical-time applicability")
        elapsed = parse_int(row["elapsed_quanta"], f"{label}.elapsed_quanta")
        audit.check(elapsed == (HORIZON_QUANTA if physical else 0), f"{label}: wrong exact clock")
        audit.check(parse_bool(row["exact_mass_ok"], f"{label}.exact_mass_ok"),
                    f"{label}: exact mass failure")
        audit.check(parse_bool(row["exact_clock_ok"], f"{label}.exact_clock_ok"),
                    f"{label}: exact clock flag failure")

        validate_optional_group(audit, row, label, "static_representation_applicable",
                                STATIC_OPTIONALS, path != PATH_A)
        validate_optional_group(audit, row, label, "affine_advection_applicable",
                                AFFINE_OPTIONALS, path != PATH_B)
        validate_optional_group(audit, row, label, "trajectory_applicable",
                                TRAJECTORY_OPTIONALS, path != PATH_B)
        stale = path == PATH_C and schedule == 0
        validate_optional_group(audit, row, label, "stale_witness_applicable",
                                ("stale_gradient_witness_error",), stale)
        for name in ALWAYS_NUMERIC_RAW:
            value = parse_float(row[name], f"{label}.{name}")
            audit.check(value >= 0.0, f"{label}: negative {name}")
    audit.check(set(observed) == expected, f"{scope}: Cartesian axes are incomplete or contain extras")
    return observed


def metric_specs(path: str, field_name: str) -> list[tuple[str, float]]:
    static = TRANSLATION_STATIC_TOLERANCE if field_name == "translation" else AFFINE_STATIC_TOLERANCE
    if path == PATH_A:
        names = ("trajectory_position", "material_velocity", "linear_momentum",
                 "center_orbital", "center_physical_kinetic")
        return [(name, HORIZON_TOLERANCE) for name in names]
    if path == PATH_B:
        return [(name, static) for name in ("static_velocity", "static_affine", "static_grid")]
    names = (
        "static_velocity", "static_affine", "static_grid", "affine_gradient",
        "affine_intercept", "affine_dispersion", "trajectory_position",
        "material_velocity", "linear_momentum", "center_orbital",
        "center_physical_kinetic",
    )
    return [(name, static if name.startswith("static_") else HORIZON_TOLERANCE) for name in names]


@dataclass(frozen=True)
class ConvergenceResult:
    all_below: bool
    ratio_rule: bool
    finest_increase_failure: bool
    passes: bool


def convergence(values: Sequence[float], tolerance: float) -> ConvergenceResult:
    if len(values) != 4 or any(not math.isfinite(value) for value in values):
        return ConvergenceResult(False, False, True, False)
    all_below = all(value <= tolerance for value in values)
    finest_increase = values[3] > ROUND_OFF_FLOOR and (
        values[3] > values[2] or values[3] > values[1] or values[3] > values[0]
    )
    ratio = (not finest_increase and values[1] <= 0.70 * values[0]
             and values[2] <= 0.70 * values[1]
             and values[3] <= 0.70 * values[2]
             and values[3] <= 0.125 * values[0])
    return ConvergenceResult(all_below, ratio, finest_increase, all_below or ratio)


def raw_groups(rows: Mapping[tuple[Any, ...], dict[str, str]]) -> dict[tuple[Any, ...], list[dict[str, str]]]:
    groups: dict[tuple[Any, ...], list[dict[str, str] | None]] = {}
    for key, row in rows.items():
        family_path = key[:-1]
        schedule = key[-1]
        groups.setdefault(family_path, [None, None, None, None])[schedule] = row
    result: dict[tuple[Any, ...], list[dict[str, str]]] = {}
    for key, group in groups.items():
        if any(row is None for row in group):
            raise BundleError(f"incomplete raw convergence group: {key!r}")
        result[key] = [row for row in group if row is not None]
    return result


def expected_convergence(
    core: Mapping[tuple[Any, ...], dict[str, str]],
    coupled: Mapping[tuple[Any, ...], dict[str, str]],
) -> dict[tuple[Any, ...], tuple[float, tuple[float, ...], ConvergenceResult]]:
    expected: dict[tuple[Any, ...], tuple[float, tuple[float, ...], ConvergenceResult]] = {}
    for scope, rows in (("core", core), ("coupled_h_dt", coupled)):
        for family_path, group in raw_groups(rows).items():
            field_name = family_path[0]
            path = family_path[-1]
            for metric, tolerance in metric_specs(path, field_name):
                column = METRIC_COLUMN[metric]
                values_optional = tuple(
                    parse_optional(row[column], f"{scope}.{family_path!r}.{column}")
                    for row in group
                )
                if any(value is None for value in values_optional):
                    raise BundleError(f"{scope}.{family_path!r}: applicable metric {metric} is NA")
                values = tuple(float(value) for value in values_optional if value is not None)
                expected[(*family_path, scope, metric)] = (
                    tolerance, values, convergence(values, tolerance)
                )
    return expected


def validate_convergence(
    audit: Audit,
    rows: list[dict[str, str]],
    expected: Mapping[tuple[Any, ...], tuple[float, tuple[float, ...], ConvergenceResult]],
) -> dict[tuple[Any, ...], ConvergenceResult]:
    observed: dict[tuple[Any, ...], ConvergenceResult] = {}
    for index, row in enumerate(rows, 2):
        label = f"convergence.csv:{index}"
        validate_common_row(audit, row, label)
        family = raw_family(row, label)
        key = (*family, row["path"], row["scope"], row["metric"])
        audit.check(key not in observed, f"{label}: duplicate convergence key {key!r}")
        wanted = expected.get(key)
        if wanted is None:
            audit.check(False, f"{label}: unregistered convergence key {key!r}")
            continue
        tolerance, values, result = wanted
        audit.check_float(parse_float(row["hard_tolerance"], f"{label}.hard_tolerance"),
                          tolerance, f"{label}.hard_tolerance")
        for level, value in enumerate(values):
            actual = parse_float(row[f"error_level_{level}"], f"{label}.error_level_{level}")
            audit.check_float(actual, value, f"{label}.error_level_{level}")
        for name, wanted_bool in (
            ("all_below", result.all_below),
            ("ratio_rule", result.ratio_rule),
            ("finest_increase_failure", result.finest_increase_failure),
            ("pass", result.passes),
        ):
            audit.check(parse_bool(row[name], f"{label}.{name}") is wanted_bool,
                        f"{label}: {name} differs from independent convergence rule")
        observed[key] = result
    audit.check(set(observed) == set(expected), "convergence rows are incomplete or contain extras")
    return observed


def primary_below(row: Mapping[str, str]) -> bool:
    return all(
        parse_optional(row[name], name) is not None
        and float(parse_optional(row[name], name)) <= HORIZON_TOLERANCE
        for name in (
            "trajectory_position_error", "material_velocity_error", "affine_gradient_error",
            "affine_intercept_error", "affine_dispersion_error",
        )
    )


def computed_causal(core: Mapping[tuple[Any, ...], dict[str, str]]) -> dict[str, Any]:
    groups = raw_groups(core)
    c_groups = {key[:-1]: rows for key, rows in groups.items() if key[-1] == PATH_C}
    d_groups = {key[:-1]: rows for key, rows in groups.items() if key[-1] == PATH_D}
    result: dict[str, Any] = {
        "path_c_translation_families": 0,
        "path_c_translation_passes": 0,
        "path_c_rotation_families": 0,
        "path_c_rotation_defect_positive": 0,
        "path_c_affine_families": 0,
        "path_c_affine_defect_positive": 0,
    }
    for family, rows in c_groups.items():
        field_name = family[0]
        if field_name == "translation":
            result["path_c_translation_families"] += 1
            if all(primary_below(row) for row in rows):
                result["path_c_translation_passes"] += 1
            continue
        family_key = ("path_c_rotation_families" if field_name == "rigid_rotation"
                      else "path_c_affine_families")
        positive_key = ("path_c_rotation_defect_positive" if field_name == "rigid_rotation"
                        else "path_c_affine_defect_positive")
        result[family_key] += 1
        position_0 = parse_float(rows[0]["trajectory_position_error"], "C.position_0")
        velocity = tuple(parse_float(row["material_velocity_error"], "C.velocity") for row in rows)
        witness = parse_optional(rows[0]["stale_gradient_witness_error"], "C.witness")
        velocity_rule = convergence(velocity, HORIZON_TOLERANCE)
        defect = (
            position_0 <= HORIZON_TOLERANCE
            and velocity[0] <= HORIZON_TOLERANCE
            and witness is not None and witness <= AFFINE_STATIC_TOLERANCE
            and any(value > HORIZON_TOLERANCE for value in velocity[1:])
            and velocity[3] >= 10.0 * max(ROUND_OFF_FLOOR, velocity[0])
            and not velocity_rule.passes
        )
        if defect:
            result[positive_key] += 1
    result["path_c_reproduces"] = (
        result["path_c_translation_families"] > 0
        and result["path_c_translation_passes"] == result["path_c_translation_families"]
        and result["path_c_rotation_defect_positive"] + 1 >= result["path_c_rotation_families"]
        and result["path_c_affine_defect_positive"] + 1 >= result["path_c_affine_families"]
    )

    result["path_d_families"] = len(d_groups)
    removal_passes = 0
    for family, rows in d_groups.items():
        c_rows = c_groups.get(family)
        if c_rows is None:
            raise BundleError(f"Path D family lacks Path C control: {family!r}")
        passed = all(primary_below(row) for row in rows)
        c_finest = parse_float(c_rows[3]["material_velocity_error"], "C.finest_velocity")
        d_finest = parse_float(rows[3]["material_velocity_error"], "D.finest_velocity")
        if c_finest > HORIZON_TOLERANCE:
            passed = passed and d_finest <= 0.1 * c_finest
        if passed:
            removal_passes += 1
    result["path_d_removal_passes"] = removal_passes
    result["path_d_removes"] = len(d_groups) > 0 and removal_passes == len(d_groups)
    result["numerical_result"] = (
        "causally_supported_pending_external_gates"
        if result["path_c_reproduces"] and result["path_d_removes"]
        else "hypothesis_rejected_by_preregistered_numerical_rule"
    )
    return result


def computed_path_e(
    sanity: Sequence[Mapping[str, str]],
    core: Mapping[tuple[Any, ...], dict[str, str]],
    coupled: Mapping[tuple[Any, ...], dict[str, str]],
    convergence_results: Mapping[tuple[Any, ...], ConvergenceResult],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "single_particle_rows": len(sanity),
        "single_particle_failures": sum(
            not parse_bool(row["pass"], "single-particle pass") for row in sanity
        ),
        "exact_failures": 0,
        "paper_transfer_contract_failures": 0,
        "static_representation_failures": 0,
        "core_convergence_failures": 0,
        "coupled_convergence_failures": 0,
    }
    for key, row in core.items():
        if key[-2] != PATH_E:
            continue
        if not parse_bool(row["exact_mass_ok"], "Path E exact mass") or not parse_bool(
            row["exact_clock_ok"], "Path E exact clock"
        ):
            result["exact_failures"] += 1
        if (
            parse_float(row["max_p2g_mass_error"], "Path E P2G mass") > MASS_TOLERANCE
            or parse_float(row["max_p2g_linear_error"], "Path E P2G linear") > LINEAR_TOLERANCE
            or parse_float(row["max_p2g_paper_augmented_angular_error"], "Path E P2G angular") > ANGULAR_TOLERANCE
            or parse_float(row["max_g2p_linear_error"], "Path E G2P linear") > LINEAR_TOLERANCE
            or parse_float(row["max_g2p_paper_augmented_angular_error"], "Path E G2P angular") > ANGULAR_TOLERANCE
        ):
            result["paper_transfer_contract_failures"] += 1
        static_tolerance = (TRANSLATION_STATIC_TOLERANCE if key[0] == "translation"
                            else AFFINE_STATIC_TOLERANCE)
        if any(parse_float(row[name], f"Path E {name}") > static_tolerance
               for name in STATIC_OPTIONALS):
            result["static_representation_failures"] += 1
    for key, evaluation in convergence_results.items():
        path = key[-3]
        scope = key[-2]
        if path == PATH_E and not evaluation.passes:
            target = ("core_convergence_failures" if scope == "core"
                      else "coupled_convergence_failures")
            result[target] += 1
    result["passes"] = all(
        result[name] == 0
        for name in (
            "single_particle_failures", "exact_failures", "paper_transfer_contract_failures",
            "static_representation_failures", "core_convergence_failures",
            "coupled_convergence_failures",
        )
    )
    return result


def compare_summary_object(audit: Audit, name: str, expected: Mapping[str, Any]) -> None:
    actual = audit.summary.get(name)
    audit.check(isinstance(actual, dict), f"summary {name} must be an object")
    if not isinstance(actual, dict):
        return
    audit.check(set(actual) == set(expected), f"summary {name} keys differ")
    for key, value in expected.items():
        audit.check(actual.get(key) == value,
                    f"summary {name}.{key}: {actual.get(key)!r} != {value!r}")


def git_query(repository: Path, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments], check=False,
            capture_output=True, text=True, encoding="utf-8",
        )
    except OSError as error:
        raise BundleError(f"cannot execute Git provenance query: {error}") from error


def validate_provenance(
    audit: Audit, source_sha: str | None, source_branch: str | None, require_clean: bool,
) -> None:
    summary_sha = audit.summary.get("source_sha_at_configure")
    summary_branch = audit.summary.get("source_branch_at_configure")
    if source_sha is not None:
        audit.check(re.fullmatch(r"[0-9a-f]{40}", source_sha) is not None,
                    "--source-sha must be a full lowercase Git SHA")
        audit.check(summary_sha == source_sha, "summary source SHA differs from --source-sha")
    if source_branch is not None:
        audit.check(summary_branch == source_branch,
                    "summary source branch differs from --source-branch")
    if not require_clean:
        return
    audit.check(audit.summary.get("source_dirty_at_configure") == "false",
                "configure-time source was dirty")
    repository = Path(__file__).resolve().parents[1]
    head = git_query(repository, ("rev-parse", "HEAD"))
    branch = git_query(repository, ("branch", "--show-current"))
    status = git_query(repository, ("status", "--porcelain"))
    audit.check(head.returncode == 0, f"runtime Git HEAD query failed: {head.stderr.strip()}")
    audit.check(branch.returncode == 0, f"runtime Git branch query failed: {branch.stderr.strip()}")
    audit.check(status.returncode == 0, f"runtime Git status query failed: {status.stderr.strip()}")
    if head.returncode == 0:
        audit.check(head.stdout.strip() == summary_sha, "runtime HEAD differs from summary source SHA")
    if branch.returncode == 0:
        audit.check(branch.stdout.strip() == summary_branch,
                    "runtime branch differs from summary source branch")
    if status.returncode == 0:
        audit.check(not status.stdout.strip(), "runtime tracked source tree is dirty")


def build_audit(bundle: Path, smoke_provisional: bool) -> Audit:
    if not bundle.is_dir():
        raise BundleError(f"bundle directory does not exist: {bundle}")
    missing = [name for name in REQUIRED_FILES if not (bundle / name).is_file()]
    if missing:
        raise BundleError(f"bundle is missing required files: {missing!r}")
    summary = load_summary(bundle / "summary.json")
    mode = summary.get("mode")
    if mode not in {"smoke", "full"}:
        raise BundleError(f"summary mode must be smoke or full, got {mode!r}")
    return Audit(bundle, summary, mode, smoke_provisional)


def validate_bundle(
    bundle: Path,
    *,
    smoke_provisional: bool,
    source_sha: str | None,
    source_branch: str | None,
    require_clean: bool,
) -> Audit:
    audit = build_audit(bundle, smoke_provisional)
    audit.hashes = manifest(bundle)
    validate_summary_policy(audit)
    sanity = read_csv(bundle / "single_particle_sanity.csv", SANITY_FIELDS)
    core_rows = read_csv(bundle / "core_sweep.csv", RAW_FIELDS)
    coupled_rows = read_csv(bundle / "coupled_refinement.csv", RAW_FIELDS)
    convergence_rows = read_csv(bundle / "convergence.csv", CONVERGENCE_FIELDS)
    validate_counts_summary(audit, {
        "single_particle_sanity": len(sanity),
        "core_sweep": len(core_rows),
        "coupled_refinement": len(coupled_rows),
        "convergence": len(convergence_rows),
    })
    validate_sanity(audit, sanity)
    core = validate_raw_rows(audit, core_rows, "core")
    coupled = validate_raw_rows(audit, coupled_rows, "coupled_h_dt")
    expected_conv = expected_convergence(core, coupled)
    convergence_results = validate_convergence(audit, convergence_rows, expected_conv)
    if audit.mode == "full":
        compare_summary_object(audit, "causal_diagnosis", computed_causal(core))
        compare_summary_object(
            audit, "path_e_literature_and_mls_gate",
            computed_path_e(sanity, core, coupled, convergence_results),
        )
    validate_provenance(audit, source_sha, source_branch, require_clean)
    return audit


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
    first.check(first.mode == second.mode, "comparison bundle mode differs")
    first_files = set(first.hashes)
    second_files = set(second.hashes)
    first.check(first_files == second_files, "comparison bundle file sets differ")
    for relative in sorted(first_files & second_files):
        first.check(first.hashes[relative] == second.hashes[relative],
                    f"comparison SHA-256 differs: {relative}")
        first.check(files_identical(first.bundle / relative, second.bundle / relative),
                    f"comparison bytes differ: {relative}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="independently validate an MLS Affine Advection Lab bundle"
    )
    parser.add_argument("--bundle", required=True, type=Path,
                        help="bundle containing summary.json and four CSV files")
    parser.add_argument("--compare", type=Path,
                        help="validate another bundle and require every file to be byte-identical")
    parser.add_argument("--smoke-provisional", action="store_true",
                        help="explicitly accept smoke mode as provisional, without a causal verdict")
    parser.add_argument("--source-sha",
                        help="require this full lowercase Git SHA in configure-time provenance")
    parser.add_argument("--source-branch",
                        help="require this configure-time source branch")
    parser.add_argument("--require-clean", action="store_true",
                        help="require clean embedded provenance and matching clean runtime Git state")
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
        )
        comparison: Audit | None = None
        if arguments.compare is not None:
            comparison = validate_bundle(
                arguments.compare.resolve(),
                smoke_provisional=arguments.smoke_provisional,
                source_sha=arguments.source_sha,
                source_branch=arguments.source_branch,
                require_clean=arguments.require_clean,
            )
            compare_bundles(audit, comparison)
    except BundleError as error:
        print(f"AFFINE ADVECTION BUNDLE INVALID: {error}", file=sys.stderr)
        return 1

    errors = list(audit.errors)
    if comparison is not None:
        errors.extend(f"comparison: {message}" for message in comparison.errors)
    if errors:
        print(f"AFFINE ADVECTION BUNDLE INVALID: {len(errors)} mismatch(es)", file=sys.stderr)
        for message in errors[:200]:
            print(f"  - {message}", file=sys.stderr)
        if len(errors) > 200:
            print(f"  - ... {len(errors) - 200} more", file=sys.stderr)
        print_manifest("primary", audit.hashes)
        return 1

    status = "SMOKE PROVISIONAL" if audit.mode == "smoke" else "VALID"
    print(f"AFFINE ADVECTION BUNDLE {status}")
    print(f"schema={SCHEMA} mode={audit.mode} seed={SEED}")
    if audit.mode == "full":
        diagnosis = audit.summary["causal_diagnosis"]["numerical_result"]
        path_e = audit.summary["path_e_literature_and_mls_gate"]["passes"]
        print(f"causal_numerical_result={diagnosis}")
        print(f"path_e_literature_and_mls_gate_pass={str(path_e).lower()}")
    else:
        print("causal_numerical_result=not issued: smoke provisional")
        print("path_e_literature_and_mls_gate_pass=not issued: smoke provisional")
    print(f"byte_identical_comparison={'yes' if comparison is not None else 'not requested'}")
    print_manifest("primary", audit.hashes)
    if comparison is not None:
        print_manifest("comparison", comparison.hashes)
    print("scope=evidence consistency only; no transfer promotion or mechanics validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
