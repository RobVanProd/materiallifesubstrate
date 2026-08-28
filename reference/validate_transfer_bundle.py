#!/usr/bin/env python3
"""Independent structural and decision audit for a Time + Transfer bundle.

This validator consumes only the sealed ``summary.json`` and raw CSV files. It
does not import the C++ implementation, call the bakeoff executable, or accept
the application's summary decisions on trust.  The constants and decision
rules below are the version-1 protocol sealed in
``docs/time-transfer-preregistration.md``.

Passing this audit means that the bundle is complete and internally consistent.
It does not make a transfer candidate physically valid and does not validate
continuum mechanics.
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
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


SCHEMA = "mls-time-transfer-bakeoff-v2"
SEED = 260828
FNV1A64_OFFSET = 14695981039346656037
FNV1A64_PRIME = 1099511628211
UINT64_MASK = (1 << 64) - 1

# Frozen protocol-v1 scales and tolerances. Numerical residuals are diagnostics,
# never entries in a physical energy ledger.
KG_PER_MASS_QUANTUM = 0.125
SECONDS_PER_TIME_QUANTUM = 1.0 / 40.0
MASS_TOLERANCE = 2.0e-13
LINEAR_MOMENTUM_TOLERANCE = 2.0e-12
ANGULAR_MOMENTUM_TOLERANCE = 2.0e-11
TRANSLATION_RECONSTRUCTION_TOLERANCE = 2.0e-12
APIC_AFFINE_RECONSTRUCTION_TOLERANCE = 5.0e-11
REPEATED_CLAIM_TOLERANCE = 2.0e-9
ROUNDOFF_FLOOR = 5.0e-14

CANDIDATES = ("PIC", "APIC")
FIELDS = ("translation", "rigid_rotation", "general_affine")
LAYOUTS = ("regular_2x2x2", "unequal_mass_asymmetric", "seeded_jittered_27")
MASS_RATIOS = (1, 17)
SPACINGS = (1.0, 0.5, 0.25)
DT_QUANTA = (4, 2, 1)
PHASES = (
    (0.00, 0.00, 0.00),
    (0.13, 0.37, 0.71),
    (0.49, 0.01, 0.83),
    (0.91, 0.59, 0.23),
)


def proper_orientation_labels() -> tuple[str, ...]:
    labels: list[str] = []
    for permutation in itertools.permutations((0, 1, 2)):
        inversions = sum(
            permutation[left] > permutation[right]
            for left in range(3)
            for right in range(left + 1, 3)
        )
        parity = 1 if inversions % 2 == 0 else -1
        for signs in itertools.product((-1, 1), repeat=3):
            if parity * signs[0] * signs[1] * signs[2] != 1:
                continue
            suffix = "".join("p" if sign > 0 else "m" for sign in signs)
            labels.append(f"p{permutation[0]}{permutation[1]}{permutation[2]}_s{suffix}")
    if len(labels) != 24 or len(set(labels)) != 24:
        raise AssertionError("independent proper-orientation label construction failed")
    return tuple(labels)


ORIENTATION_LABELS = proper_orientation_labels()

REQUIRED_CSVS = (
    "transfer_sweep.csv",
    "h_convergence.csv",
    "ballistic_regrid_sweep.csv",
    "time_convergence.csv",
    "flip_identity_diagnostic.csv",
)
DETERMINISTIC_FILES = (*REQUIRED_CSVS, "summary.json")
EXTERNAL_GATES_SCHEMA = "mls-time-transfer-external-gates-v1"
REQUIRED_LOCAL_GATES = ("cpp", "python", "lean", "checkpoint", "deterministic_rerun")
REQUIRED_CI_JOBS = (
    "C++ / Linux GCC",
    "C++ / Linux Clang",
    "C++ / Windows MSVC",
    "Python exact oracle",
    "Pinned Lean build and axiom output",
)

TRANSFER_HEADER = """mode,seed,candidate,field,phase_index,phase_x,phase_y,phase_z,orientation_index,orientation,layout,grid_spacing_m,mass_ratio,kg_per_mass_quantum,dt_quanta,dt_seconds,pure_remap_timestep_independent,cycles,particle_count,exact_mass_initial_quanta,exact_mass_terminal_quanta,exact_mass_ok,max_p2g_mass_relative,max_p2g_linear_relative,max_p2g_center_orbital_relative,max_p2g_declared_angular_relative,max_roundtrip_mass_relative,max_roundtrip_linear_relative,max_roundtrip_center_orbital_relative,max_roundtrip_declared_angular_relative,cumulative_linear_relative,cumulative_center_orbital_relative,cumulative_declared_angular_relative,center_orbital_diagnostic_pass,grid_reconstruction_relative,particle_reconstruction_relative,affine_reconstruction_applicable,affine_reconstruction_relative,final_p2g_candidate_represented_energy_residual_j,final_p2g_candidate_represented_energy_relative,final_roundtrip_candidate_represented_energy_residual_j,final_roundtrip_candidate_represented_energy_relative,max_abs_p2g_candidate_represented_energy_relative,max_abs_roundtrip_candidate_represented_energy_relative,cumulative_candidate_represented_energy_residual_j,cumulative_candidate_represented_energy_relative,final_p2g_center_energy_residual_j,final_p2g_center_energy_relative,final_roundtrip_center_energy_residual_j,final_roundtrip_center_energy_relative,max_abs_p2g_center_energy_relative,max_abs_roundtrip_center_energy_relative,cumulative_center_energy_residual_j,cumulative_center_energy_relative,claimed_contract_pass,initial_mass_kg,initial_linear_x,initial_linear_y,initial_linear_z,initial_center_orbital_x,initial_center_orbital_y,initial_center_orbital_z,initial_affine_auxiliary_angular_x,initial_affine_auxiliary_angular_y,initial_affine_auxiliary_angular_z,initial_augmented_angular_x,initial_augmented_angular_y,initial_augmented_angular_z,initial_center_kinetic_j,initial_affine_auxiliary_kinetic_j,initial_augmented_kinetic_j,grid_mass_kg,grid_linear_x,grid_linear_y,grid_linear_z,grid_center_orbital_x,grid_center_orbital_y,grid_center_orbital_z,grid_affine_auxiliary_angular_x,grid_affine_auxiliary_angular_y,grid_affine_auxiliary_angular_z,grid_augmented_angular_x,grid_augmented_angular_y,grid_augmented_angular_z,grid_center_kinetic_j,grid_affine_auxiliary_kinetic_j,grid_augmented_kinetic_j,terminal_mass_kg,terminal_linear_x,terminal_linear_y,terminal_linear_z,terminal_center_orbital_x,terminal_center_orbital_y,terminal_center_orbital_z,terminal_affine_auxiliary_angular_x,terminal_affine_auxiliary_angular_y,terminal_affine_auxiliary_angular_z,terminal_augmented_angular_x,terminal_augmented_angular_y,terminal_augmented_angular_z,terminal_center_kinetic_j,terminal_affine_auxiliary_kinetic_j,terminal_augmented_kinetic_j""".split(",")

H_CONVERGENCE_HEADER = """mode,seed,candidate,field,phase_index,phase_x,phase_y,phase_z,orientation_index,orientation,layout,mass_ratio,cycles,dt_quanta,dt_seconds,metric,error_h_1,error_h_half,error_h_quarter,finest_increase_failure,all_below_threshold,ratio_rule_pass,medium_over_coarse,fine_over_medium,fine_over_coarse,convergence_pass""".split(",")

BALLISTIC_HEADER = """mode,seed,experiment,candidate,field,phase_index,phase_x,phase_y,phase_z,orientation_index,orientation,layout,grid_spacing_m,mass_ratio,kg_per_mass_quantum,time_quantum_seconds_num,time_quantum_seconds_den,dt_quanta,dt_seconds,fixed_horizon_quanta,fixed_horizon_seconds,step_count,elapsed_quanta,position_error_relative,velocity_error_relative,physical_time_error_relative,exact_mass_ok,max_p2g_mass_relative,max_p2g_linear_relative,max_p2g_center_orbital_relative,max_p2g_declared_angular_relative,max_roundtrip_mass_relative,max_roundtrip_linear_relative,max_roundtrip_center_orbital_relative,max_roundtrip_declared_angular_relative,cumulative_linear_relative,cumulative_center_orbital_relative,cumulative_declared_angular_relative,center_orbital_diagnostic_pass,declared_transfer_contract_pass,max_abs_p2g_candidate_represented_energy_relative,max_abs_roundtrip_candidate_represented_energy_relative,cumulative_candidate_represented_numerical_energy_residual_j,cumulative_candidate_represented_numerical_energy_relative,cumulative_center_kinetic_numerical_energy_residual_j,cumulative_center_kinetic_numerical_energy_relative,initial_center_kinetic_j,initial_affine_auxiliary_kinetic_j,initial_augmented_kinetic_j,terminal_center_kinetic_j,terminal_affine_auxiliary_kinetic_j,terminal_augmented_kinetic_j""".split(",")

TIME_CONVERGENCE_HEADER = """mode,seed,experiment,candidate,field,phase_index,phase_x,phase_y,phase_z,orientation_index,orientation,layout,grid_spacing_m,mass_ratio,metric,error_dt,error_dt_half,error_dt_quarter,finest_increase_failure,all_below_threshold,ratio_rule_pass,half_over_dt,quarter_over_half,quarter_over_dt,convergence_pass""".split(",")

FLIP_HEADER = """mode,seed,candidate,eligibility,omitted_redundant_axes,field,phase_index,phase_x,phase_y,phase_z,orientation_index,orientation,layout,grid_spacing_m,mass_ratio,kg_per_mass_quantum,particle_count,exact_mass_ok,p2g_mass_relative,p2g_linear_relative,p2g_center_orbital_relative,identity_velocity_relative,p2g_center_kinetic_numerical_energy_residual_j,p2g_center_kinetic_numerical_energy_relative""".split(",")


@dataclass(frozen=True)
class CsvSchema:
    header: Sequence[str]
    strings: frozenset[str]
    booleans: frozenset[str]
    integers: frozenset[str]


COMMON_STRINGS = frozenset({"mode", "candidate", "field", "orientation", "layout"})
COMMON_INTEGERS = frozenset({"seed", "phase_index", "orientation_index", "mass_ratio"})

CSV_SCHEMAS = {
    "transfer_sweep.csv": CsvSchema(
        TRANSFER_HEADER,
        COMMON_STRINGS,
        frozenset(
            {
                "pure_remap_timestep_independent",
                "exact_mass_ok",
                "center_orbital_diagnostic_pass",
                "affine_reconstruction_applicable",
                "claimed_contract_pass",
            }
        ),
        COMMON_INTEGERS
        | frozenset(
            {
                "dt_quanta",
                "cycles",
                "particle_count",
                "exact_mass_initial_quanta",
                "exact_mass_terminal_quanta",
            }
        ),
    ),
    "h_convergence.csv": CsvSchema(
        H_CONVERGENCE_HEADER,
        COMMON_STRINGS | frozenset({"metric"}),
        frozenset(
            {
                "finest_increase_failure",
                "all_below_threshold",
                "ratio_rule_pass",
                "convergence_pass",
            }
        ),
        COMMON_INTEGERS | frozenset({"cycles", "dt_quanta"}),
    ),
    "ballistic_regrid_sweep.csv": CsvSchema(
        BALLISTIC_HEADER,
        COMMON_STRINGS | frozenset({"experiment"}),
        frozenset(
            {
                "exact_mass_ok",
                "center_orbital_diagnostic_pass",
                "declared_transfer_contract_pass",
            }
        ),
        COMMON_INTEGERS
        | frozenset(
            {
                "time_quantum_seconds_num",
                "time_quantum_seconds_den",
                "dt_quanta",
                "fixed_horizon_quanta",
                "step_count",
                "elapsed_quanta",
            }
        ),
    ),
    "time_convergence.csv": CsvSchema(
        TIME_CONVERGENCE_HEADER,
        COMMON_STRINGS | frozenset({"experiment", "metric"}),
        frozenset(
            {
                "finest_increase_failure",
                "all_below_threshold",
                "ratio_rule_pass",
                "convergence_pass",
            }
        ),
        COMMON_INTEGERS,
    ),
    "flip_identity_diagnostic.csv": CsvSchema(
        FLIP_HEADER,
        COMMON_STRINGS | frozenset({"eligibility", "omitted_redundant_axes"}),
        frozenset({"exact_mass_ok"}),
        COMMON_INTEGERS | frozenset({"particle_count"}),
    ),
}

H_METRICS = (
    "particle_velocity_reconstruction",
    "grid_velocity_reconstruction",
    "absolute_candidate_represented_numerical_energy_residual",
    "absolute_center_kinetic_numerical_energy_residual",
    "affine_matrix_reconstruction",
)
TIME_METRICS = (
    "fixed_horizon_position_error",
    "fixed_horizon_velocity_error",
    "exact_physical_time_error",
    "absolute_candidate_represented_numerical_energy_residual",
    "absolute_center_kinetic_numerical_energy_residual",
)

SUMMARY_INTEGER_FIELDS = (
    "transfer_rows",
    "claimed_contract_failures",
    "exact_mass_failures",
    "center_orbital_diagnostic_failures",
    "h_groups",
    "h_particle_reconstruction_failures",
    "h_grid_reconstruction_failures",
    "h_energy_failures",
    "h_affine_reconstruction_failures",
    "h_center_energy_diagnostic_failures",
    "time_groups",
    "time_position_failures",
    "time_velocity_failures",
    "time_clock_failures",
    "time_energy_failures",
    "time_center_energy_diagnostic_failures",
    "time_contract_failures",
    "time_exact_mass_failures",
)
SUMMARY_FLOAT_FIELDS = (
    "worst_affine_reconstruction",
    "worst_claimed_angular",
    "worst_numerical_energy_residual",
    "worst_64_cycle_drift",
)
ELIGIBILITY_FAILURE_FIELDS = (
    "claimed_contract_failures",
    "exact_mass_failures",
    "h_particle_reconstruction_failures",
    "h_grid_reconstruction_failures",
    "h_affine_reconstruction_failures",
    "h_energy_failures",
    "time_position_failures",
    "time_velocity_failures",
    "time_clock_failures",
    "time_energy_failures",
    "time_contract_failures",
    "time_exact_mass_failures",
)


class BundleError(RuntimeError):
    """Raised when a bundle cannot be parsed far enough to audit safely."""


@dataclass
class CandidateStats:
    transfer_rows: int = 0
    claimed_contract_failures: int = 0
    exact_mass_failures: int = 0
    center_orbital_diagnostic_failures: int = 0
    h_groups: int = 0
    h_particle_reconstruction_failures: int = 0
    h_grid_reconstruction_failures: int = 0
    h_energy_failures: int = 0
    h_affine_reconstruction_failures: int = 0
    h_center_energy_diagnostic_failures: int = 0
    time_groups: int = 0
    time_position_failures: int = 0
    time_velocity_failures: int = 0
    time_clock_failures: int = 0
    time_energy_failures: int = 0
    time_center_energy_diagnostic_failures: int = 0
    time_contract_failures: int = 0
    time_exact_mass_failures: int = 0
    worst_affine_reconstruction: float = 0.0
    worst_claimed_angular: float = 0.0
    worst_numerical_energy_residual: float = 0.0
    worst_64_cycle_drift: float = 0.0


@dataclass
class Audit:
    bundle: Path
    summary: Mapping[str, Any]
    mode: str
    phase_count: int
    orientation_count: int
    errors: list[str] = field(default_factory=list)
    row_counts: Counter[str] = field(default_factory=Counter)
    candidate_stats: dict[str, CandidateStats] = field(
        default_factory=lambda: {name: CandidateStats() for name in CANDIDATES}
    )
    orientation_by_index: dict[int, str] = field(default_factory=dict)
    orientation_index_by_label: dict[str, int] = field(default_factory=dict)
    observed_phase_indices: set[int] = field(default_factory=set)
    observed_orientation_indices: set[int] = field(default_factory=set)
    sha256: dict[str, str] = field(default_factory=dict)
    known_failed_runs: Any = None

    def check(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)

    def check_float(self, actual: float, expected: float, message: str) -> None:
        # All emitted values use max_digits10. This allowance is only for the
        # independent recomputation's last rounding bit, not a scientific tolerance.
        allowance = max(5.0e-16, 8.0e-15 * max(abs(actual), abs(expected)))
        self.check(abs(actual - expected) <= allowance, f"{message}: {actual!r} != {expected!r}")


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value}")


def strict_json_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_summary(path: Path) -> Mapping[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(
                stream,
                parse_constant=reject_json_constant,
                object_pairs_hook=strict_json_object,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise BundleError(f"cannot parse {path}: {error}") from error
    if not isinstance(value, dict):
        raise BundleError("summary.json root must be an object")
    require_finite_json(value, "summary.json")
    return value


def require_finite_json(value: Any, location: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise BundleError(f"{location}: NaN or infinity is forbidden")
    if isinstance(value, dict):
        for key, child in value.items():
            require_finite_json(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            require_finite_json(child, f"{location}[{index}]")


def fnv1a64(path: Path) -> str:
    value = FNV1A64_OFFSET
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                for byte in chunk:
                    value ^= byte
                    value = (value * FNV1A64_PRIME) & UINT64_MASK
    except OSError as error:
        raise BundleError(f"cannot hash {path}: {error}") from error
    return f"{value:016x}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise BundleError(f"cannot hash {path}: {error}") from error
    return digest.hexdigest()


def parse_bool(text: str, location: str) -> bool:
    # The v1 writer uses stream-formatted 0/1 for generic rows and one literal
    # ``true`` in the hand-written pure-remap column.
    if text in {"1", "true"}:
        return True
    if text in {"0", "false"}:
        return False
    raise BundleError(f"{location}: expected a v1 boolean, got {text!r}")


def parse_row(
    schema: CsvSchema, raw: Sequence[str], filename: str, line_number: int
) -> dict[str, Any]:
    if len(raw) != len(schema.header):
        raise BundleError(
            f"{filename}:{line_number}: expected {len(schema.header)} columns, got {len(raw)}"
        )
    row: dict[str, Any] = {}
    for name, text in zip(schema.header, raw, strict=True):
        location = f"{filename}:{line_number}:{name}"
        if name in schema.strings:
            if not text:
                raise BundleError(f"{location}: empty string is not canonical")
            row[name] = text
        elif name in schema.booleans:
            row[name] = parse_bool(text, location)
        elif name in schema.integers:
            if not re.fullmatch(r"-?(0|[1-9][0-9]*)", text):
                raise BundleError(f"{location}: invalid canonical integer {text!r}")
            row[name] = int(text)
        else:
            try:
                number = float(text)
            except ValueError as error:
                raise BundleError(f"{location}: invalid floating value {text!r}") from error
            if not math.isfinite(number):
                raise BundleError(f"{location}: NaN or infinity is forbidden")
            row[name] = number
    return row


def csv_rows(path: Path, schema: CsvSchema) -> Iterator[tuple[int, dict[str, Any]]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream)
            try:
                header = next(reader)
            except StopIteration as error:
                raise BundleError(f"{path.name}: empty CSV") from error
            if header != list(schema.header):
                raise BundleError(
                    f"{path.name}: schema/header mismatch\n"
                    f"  expected: {','.join(schema.header)}\n"
                    f"  actual:   {','.join(header)}"
                )
            for line_number, raw in enumerate(reader, start=2):
                if not raw or (len(raw) == 1 and raw[0] == ""):
                    raise BundleError(f"{path.name}:{line_number}: blank row")
                yield line_number, parse_row(schema, raw, path.name, line_number)
    except (OSError, UnicodeError, csv.Error) as error:
        raise BundleError(f"cannot parse {path}: {error}") from error


def canonical_choice(value: float, choices: Sequence[float], location: str) -> float:
    for choice in choices:
        if math.isclose(value, choice, rel_tol=0.0, abs_tol=2.0e-15):
            return choice
    raise BundleError(f"{location}: {value!r} is outside the frozen axis {tuple(choices)!r}")


def expected_cycles(mode: str) -> tuple[int, ...]:
    return (1, 4) if mode == "smoke" else (1, 4, 16, 64)


def validate_common_axes(audit: Audit, row: Mapping[str, Any], filename: str, line: int) -> None:
    where = f"{filename}:{line}"
    audit.check(row["mode"] == audit.mode, f"{where}: row mode differs from summary mode")
    audit.check(row["seed"] == SEED, f"{where}: seed differs from frozen seed")
    audit.check(row["field"] in FIELDS, f"{where}: unknown field {row['field']!r}")
    audit.check(row["layout"] in LAYOUTS, f"{where}: unknown layout {row['layout']!r}")
    audit.check(row["mass_ratio"] in MASS_RATIOS, f"{where}: unknown mass ratio")

    phase_index = row["phase_index"]
    audit.check(0 <= phase_index < audit.phase_count, f"{where}: phase index out of range")
    if 0 <= phase_index < len(PHASES):
        actual_phase = (row["phase_x"], row["phase_y"], row["phase_z"])
        for axis, (actual, expected) in enumerate(zip(actual_phase, PHASES[phase_index], strict=True)):
            audit.check_float(actual, expected, f"{where}: phase {phase_index} axis {axis}")
        audit.observed_phase_indices.add(phase_index)

    orientation_index = row["orientation_index"]
    label = row["orientation"]
    audit.check(
        0 <= orientation_index < audit.orientation_count,
        f"{where}: orientation index out of range",
    )
    if 0 <= orientation_index < audit.orientation_count:
        audit.check(
            label == ORIENTATION_LABELS[orientation_index],
            f"{where}: orientation label is not the preregistered proper signed-axis rotation",
        )
        prior_label = audit.orientation_by_index.setdefault(orientation_index, label)
        audit.check(prior_label == label, f"{where}: orientation index changed label")
        prior_index = audit.orientation_index_by_label.setdefault(label, orientation_index)
        audit.check(prior_index == orientation_index, f"{where}: orientation label changed index")
        audit.observed_orientation_indices.add(orientation_index)


def reconstruction_claimed(candidate: str, field_name: str) -> bool:
    return field_name == "translation" or candidate == "APIC"


def reconstruction_tolerance(candidate: str, field_name: str, cycles: int) -> float:
    if cycles == 64 and reconstruction_claimed(candidate, field_name):
        return REPEATED_CLAIM_TOLERANCE
    if field_name == "translation":
        return TRANSLATION_RECONSTRUCTION_TOLERANCE
    return APIC_AFFINE_RECONSTRUCTION_TOLERANCE


@dataclass(frozen=True)
class Convergence:
    finest_increase_failure: bool
    all_below_threshold: bool
    ratio_rule_pass: bool
    medium_over_coarse: float
    fine_over_medium: float
    fine_over_coarse: float
    passed: bool


def convergence(errors: Sequence[float], hard_tolerance: float | None) -> Convergence:
    if len(errors) != 3 or any(not math.isfinite(value) or value < 0.0 for value in errors):
        raise BundleError("convergence inputs must be three finite nonnegative values")
    finest_increase = (
        errors[2] > ROUNDOFF_FLOOR
        and errors[2] > errors[0]
        and errors[2] > errors[1]
    )
    threshold = ROUNDOFF_FLOOR if hard_tolerance is None else hard_tolerance
    # A resolved finest-level increase blocks only the ratio branch. Three
    # values already inside an applicable hard tolerance remain a hard pass.
    all_below = all(value <= threshold for value in errors)
    clamped = tuple(max(value, ROUNDOFF_FLOOR) for value in errors)
    medium_over_coarse = clamped[1] / clamped[0]
    fine_over_medium = clamped[2] / clamped[1]
    fine_over_coarse = clamped[2] / clamped[0]
    ratio_pass = (
        medium_over_coarse <= 0.70
        and fine_over_medium <= 0.70
        and fine_over_coarse <= 0.25
        and not finest_increase
    )
    return Convergence(
        finest_increase,
        all_below,
        ratio_pass,
        medium_over_coarse,
        fine_over_medium,
        fine_over_coarse,
        all_below or ratio_pass,
    )


def check_convergence_row(
    audit: Audit,
    row: Mapping[str, Any],
    filename: str,
    line: int,
    errors: Sequence[float],
    hard_tolerance: float | None,
    ratio_columns: Sequence[str],
) -> Convergence:
    result = convergence(errors, hard_tolerance)
    where = f"{filename}:{line}"
    expected_flags = {
        "finest_increase_failure": result.finest_increase_failure,
        "all_below_threshold": result.all_below_threshold,
        "ratio_rule_pass": result.ratio_rule_pass,
        "convergence_pass": result.passed,
    }
    for name, expected in expected_flags.items():
        audit.check(row[name] is expected, f"{where}: incorrect {name}")
    for name, expected in zip(
        ratio_columns,
        (result.medium_over_coarse, result.fine_over_medium, result.fine_over_coarse),
        strict=True,
    ):
        audit.check_float(row[name], expected, f"{where}: incorrect {name}")
    if row["finest_increase_failure"] and not row["all_below_threshold"]:
        audit.check(
            not row["convergence_pass"],
            f"{where}: resolved finest-grid increase must block the ratio branch",
        )
    return result


def process_transfer(audit: Audit) -> None:
    filename = "transfer_sweep.csv"
    seen: set[tuple[Any, ...]] = set()
    cycles_axis = expected_cycles(audit.mode)
    for line, row in csv_rows(audit.bundle / filename, CSV_SCHEMAS[filename]):
        audit.row_counts[filename] += 1
        validate_common_axes(audit, row, filename, line)
        where = f"{filename}:{line}"
        candidate = row["candidate"]
        audit.check(candidate in CANDIDATES, f"{where}: unknown candidate {candidate!r}")
        if candidate not in audit.candidate_stats:
            continue
        stats = audit.candidate_stats[candidate]
        stats.transfer_rows += 1
        spacing = canonical_choice(row["grid_spacing_m"], SPACINGS, where)
        audit.check(row["dt_quanta"] in DT_QUANTA, f"{where}: invalid dt")
        audit.check(row["cycles"] in cycles_axis, f"{where}: invalid cycle count")
        audit.check(row["pure_remap_timestep_independent"], f"{where}: pure remap flag is false")
        audit.check_float(row["kg_per_mass_quantum"], KG_PER_MASS_QUANTUM, f"{where}: mass scale")
        audit.check_float(
            row["dt_seconds"], row["dt_quanta"] * SECONDS_PER_TIME_QUANTUM, f"{where}: dt"
        )
        key = (
            candidate,
            row["field"],
            row["phase_index"],
            row["orientation_index"],
            row["layout"],
            spacing,
            row["mass_ratio"],
            row["cycles"],
            row["dt_quanta"],
        )
        audit.check(key not in seen, f"{where}: duplicate transfer sweep key")
        seen.add(key)

        expected_mass_flag = row["exact_mass_initial_quanta"] == row["exact_mass_terminal_quanta"]
        audit.check(row["exact_mass_ok"] is expected_mass_flag, f"{where}: incorrect exact-mass flag")
        if not row["exact_mass_ok"]:
            stats.exact_mass_failures += 1

        cumulative_tolerance = (
            REPEATED_CLAIM_TOLERANCE
            if row["cycles"] == 64
            else ANGULAR_MOMENTUM_TOLERANCE
        )
        center_diagnostic_pass = (
            row["max_p2g_center_orbital_relative"] <= ANGULAR_MOMENTUM_TOLERANCE
            and row["max_roundtrip_center_orbital_relative"] <= ANGULAR_MOMENTUM_TOLERANCE
            and row["cumulative_center_orbital_relative"] <= cumulative_tolerance
        )
        audit.check(
            row["center_orbital_diagnostic_pass"] is center_diagnostic_pass,
            f"{where}: center-only physical orbital gate is incorrect",
        )
        if not row["center_orbital_diagnostic_pass"]:
            stats.center_orbital_diagnostic_failures += 1

        claimed_pass = (
            row["exact_mass_ok"]
            and row["max_p2g_mass_relative"] <= MASS_TOLERANCE
            and row["max_roundtrip_mass_relative"] <= MASS_TOLERANCE
            and row["max_p2g_linear_relative"] <= LINEAR_MOMENTUM_TOLERANCE
            and row["max_roundtrip_linear_relative"] <= LINEAR_MOMENTUM_TOLERANCE
            and row["max_p2g_declared_angular_relative"]
            <= ANGULAR_MOMENTUM_TOLERANCE
        )
        claimed_pass = claimed_pass and (
            row["max_roundtrip_declared_angular_relative"]
            <= ANGULAR_MOMENTUM_TOLERANCE
            and row["cumulative_linear_relative"] <= cumulative_tolerance
            and row["cumulative_declared_angular_relative"] <= cumulative_tolerance
        )
        if reconstruction_claimed(candidate, row["field"]):
            claimed_pass = claimed_pass and (
                row["particle_reconstruction_relative"]
                <= reconstruction_tolerance(candidate, row["field"], row["cycles"])
            )
        if candidate == "APIC":
            claimed_pass = claimed_pass and (
                row["affine_reconstruction_relative"]
                <= reconstruction_tolerance(candidate, row["field"], row["cycles"])
            )
        audit.check(row["claimed_contract_pass"] is claimed_pass, f"{where}: claimed contract flag")
        if not row["claimed_contract_pass"]:
            stats.claimed_contract_failures += 1

        audit.check(
            row["affine_reconstruction_applicable"] is (candidate == "APIC"),
            f"{where}: affine applicability does not match candidate",
        )
        if row["field"] == "general_affine":
            stats.worst_affine_reconstruction = max(
                stats.worst_affine_reconstruction,
                row["particle_reconstruction_relative"],
                row["affine_reconstruction_relative"] if candidate == "APIC" else 0.0,
            )
        stats.worst_claimed_angular = max(
            stats.worst_claimed_angular,
            row["max_p2g_declared_angular_relative"],
            row["max_roundtrip_declared_angular_relative"],
            row["cumulative_declared_angular_relative"],
        )
        stats.worst_numerical_energy_residual = max(
            stats.worst_numerical_energy_residual,
            row["max_abs_p2g_candidate_represented_energy_relative"],
            row["max_abs_roundtrip_candidate_represented_energy_relative"],
            row["cumulative_candidate_represented_energy_relative"],
        )
        if row["cycles"] == 64:
            stats.worst_64_cycle_drift = max(
                stats.worst_64_cycle_drift,
                row["particle_reconstruction_relative"]
                if reconstruction_claimed(candidate, row["field"])
                else 0.0,
                row["affine_reconstruction_relative"] if candidate == "APIC" else 0.0,
                row["cumulative_linear_relative"],
                row["cumulative_declared_angular_relative"],
            )


def process_h_convergence(audit: Audit) -> None:
    filename = "h_convergence.csv"
    seen: set[tuple[Any, ...]] = set()
    cycles_axis = expected_cycles(audit.mode)
    failure_field = {
        "particle_velocity_reconstruction": "h_particle_reconstruction_failures",
        "grid_velocity_reconstruction": "h_grid_reconstruction_failures",
        "affine_matrix_reconstruction": "h_affine_reconstruction_failures",
        "absolute_candidate_represented_numerical_energy_residual": "h_energy_failures",
        "absolute_center_kinetic_numerical_energy_residual": "h_center_energy_diagnostic_failures",
    }
    for line, row in csv_rows(audit.bundle / filename, CSV_SCHEMAS[filename]):
        audit.row_counts[filename] += 1
        validate_common_axes(audit, row, filename, line)
        where = f"{filename}:{line}"
        candidate = row["candidate"]
        if candidate not in audit.candidate_stats:
            audit.check(False, f"{where}: unknown candidate {candidate!r}")
            continue
        audit.check(row["metric"] in H_METRICS, f"{where}: unknown h metric")
        audit.check(
            row["metric"] != "affine_matrix_reconstruction" or candidate == "APIC",
            f"{where}: PIC must not emit an APIC affine-matrix metric",
        )
        audit.check(row["cycles"] in cycles_axis, f"{where}: invalid cycle count")
        audit.check(row["dt_quanta"] in DT_QUANTA, f"{where}: invalid dt")
        audit.check_float(
            row["dt_seconds"], row["dt_quanta"] * SECONDS_PER_TIME_QUANTUM, f"{where}: dt"
        )
        key = (
            candidate,
            row["field"],
            row["phase_index"],
            row["orientation_index"],
            row["layout"],
            row["mass_ratio"],
            row["cycles"],
            row["dt_quanta"],
            row["metric"],
        )
        audit.check(key not in seen, f"{where}: duplicate h-convergence key")
        seen.add(key)
        hard_tolerance: float | None = None
        if row["metric"] in {
            "particle_velocity_reconstruction",
            "grid_velocity_reconstruction",
        } and reconstruction_claimed(candidate, row["field"]):
            hard_tolerance = reconstruction_tolerance(
                candidate, row["field"], row["cycles"]
            )
        elif row["metric"] == "affine_matrix_reconstruction" and candidate == "APIC":
            hard_tolerance = reconstruction_tolerance(
                candidate, row["field"], row["cycles"]
            )
        result = check_convergence_row(
            audit,
            row,
            filename,
            line,
            (row["error_h_1"], row["error_h_half"], row["error_h_quarter"]),
            hard_tolerance,
            ("medium_over_coarse", "fine_over_medium", "fine_over_coarse"),
        )
        stats = audit.candidate_stats[candidate]
        if row["metric"] == "particle_velocity_reconstruction":
            stats.h_groups += 1
        if not result.passed and row["metric"] in failure_field:
            setattr(stats, failure_field[row["metric"]], getattr(stats, failure_field[row["metric"]]) + 1)


def process_ballistic(audit: Audit) -> None:
    filename = "ballistic_regrid_sweep.csv"
    seen: set[tuple[Any, ...]] = set()
    experiment = "force_free_ballistic_transfer_frequency_sensitivity"
    for line, row in csv_rows(audit.bundle / filename, CSV_SCHEMAS[filename]):
        audit.row_counts[filename] += 1
        validate_common_axes(audit, row, filename, line)
        where = f"{filename}:{line}"
        candidate = row["candidate"]
        if candidate not in audit.candidate_stats:
            audit.check(False, f"{where}: unknown candidate {candidate!r}")
            continue
        spacing = canonical_choice(row["grid_spacing_m"], SPACINGS, where)
        audit.check(row["experiment"] == experiment, f"{where}: wrong experiment label")
        audit.check(row["dt_quanta"] in DT_QUANTA, f"{where}: invalid dt")
        audit.check(row["time_quantum_seconds_num"] == 1, f"{where}: time numerator")
        audit.check(row["time_quantum_seconds_den"] == 40, f"{where}: time denominator")
        audit.check(row["fixed_horizon_quanta"] == 4, f"{where}: horizon quanta")
        audit.check(row["step_count"] == 4 // row["dt_quanta"], f"{where}: step count")
        audit.check(row["elapsed_quanta"] == 4, f"{where}: elapsed physical time")
        audit.check_float(row["kg_per_mass_quantum"], KG_PER_MASS_QUANTUM, f"{where}: mass scale")
        audit.check_float(
            row["dt_seconds"], row["dt_quanta"] * SECONDS_PER_TIME_QUANTUM, f"{where}: dt"
        )
        audit.check_float(row["fixed_horizon_seconds"], 0.1, f"{where}: horizon")
        key = (
            candidate,
            row["field"],
            row["phase_index"],
            row["orientation_index"],
            row["layout"],
            spacing,
            row["mass_ratio"],
            row["dt_quanta"],
        )
        audit.check(key not in seen, f"{where}: duplicate ballistic key")
        seen.add(key)

        stats = audit.candidate_stats[candidate]
        if not row["exact_mass_ok"]:
            stats.time_exact_mass_failures += 1
        center_diagnostic_pass = (
            row["max_p2g_center_orbital_relative"] <= ANGULAR_MOMENTUM_TOLERANCE
            and row["max_roundtrip_center_orbital_relative"] <= ANGULAR_MOMENTUM_TOLERANCE
            and row["cumulative_center_orbital_relative"] <= ANGULAR_MOMENTUM_TOLERANCE
        )
        audit.check(
            row["center_orbital_diagnostic_pass"] is center_diagnostic_pass,
            f"{where}: center-only orbital diagnostic is incorrect",
        )
        if not row["center_orbital_diagnostic_pass"]:
            stats.center_orbital_diagnostic_failures += 1

        claimed_pass = (
            row["exact_mass_ok"]
            and row["max_p2g_mass_relative"] <= MASS_TOLERANCE
            and row["max_roundtrip_mass_relative"] <= MASS_TOLERANCE
            and row["max_p2g_linear_relative"] <= LINEAR_MOMENTUM_TOLERANCE
            and row["max_roundtrip_linear_relative"] <= LINEAR_MOMENTUM_TOLERANCE
            and row["max_p2g_declared_angular_relative"]
            <= ANGULAR_MOMENTUM_TOLERANCE
            and row["max_roundtrip_declared_angular_relative"]
            <= ANGULAR_MOMENTUM_TOLERANCE
            and row["cumulative_linear_relative"] <= ANGULAR_MOMENTUM_TOLERANCE
            and row["cumulative_declared_angular_relative"]
            <= ANGULAR_MOMENTUM_TOLERANCE
        )
        audit.check(
            row["declared_transfer_contract_pass"] is claimed_pass,
            f"{where}: declared transfer-contract flag",
        )
        if not row["declared_transfer_contract_pass"]:
            stats.time_contract_failures += 1
        stats.worst_claimed_angular = max(
            stats.worst_claimed_angular,
            row["max_p2g_declared_angular_relative"],
            row["max_roundtrip_declared_angular_relative"],
            row["cumulative_declared_angular_relative"],
        )
        stats.worst_numerical_energy_residual = max(
            stats.worst_numerical_energy_residual,
            row["max_abs_p2g_candidate_represented_energy_relative"],
            row["max_abs_roundtrip_candidate_represented_energy_relative"],
            row["cumulative_candidate_represented_numerical_energy_relative"],
        )


def process_time_convergence(audit: Audit) -> None:
    filename = "time_convergence.csv"
    seen: set[tuple[Any, ...]] = set()
    experiment = "force_free_ballistic_transfer_frequency_sensitivity"
    failure_field = {
        "fixed_horizon_position_error": "time_position_failures",
        "fixed_horizon_velocity_error": "time_velocity_failures",
        "exact_physical_time_error": "time_clock_failures",
        "absolute_candidate_represented_numerical_energy_residual": "time_energy_failures",
        "absolute_center_kinetic_numerical_energy_residual": "time_center_energy_diagnostic_failures",
    }
    for line, row in csv_rows(audit.bundle / filename, CSV_SCHEMAS[filename]):
        audit.row_counts[filename] += 1
        validate_common_axes(audit, row, filename, line)
        where = f"{filename}:{line}"
        candidate = row["candidate"]
        if candidate not in audit.candidate_stats:
            audit.check(False, f"{where}: unknown candidate {candidate!r}")
            continue
        spacing = canonical_choice(row["grid_spacing_m"], SPACINGS, where)
        audit.check(row["experiment"] == experiment, f"{where}: wrong experiment label")
        audit.check(row["metric"] in TIME_METRICS, f"{where}: unknown time metric")
        key = (
            candidate,
            row["field"],
            row["phase_index"],
            row["orientation_index"],
            row["layout"],
            spacing,
            row["mass_ratio"],
            row["metric"],
        )
        audit.check(key not in seen, f"{where}: duplicate time-convergence key")
        seen.add(key)
        result = check_convergence_row(
            audit,
            row,
            filename,
            line,
            (row["error_dt"], row["error_dt_half"], row["error_dt_quarter"]),
            ROUNDOFF_FLOOR if row["metric"] == "exact_physical_time_error" else None,
            ("half_over_dt", "quarter_over_half", "quarter_over_dt"),
        )
        stats = audit.candidate_stats[candidate]
        if row["metric"] == "fixed_horizon_position_error":
            stats.time_groups += 1
        if not result.passed and row["metric"] in failure_field:
            attribute = failure_field[row["metric"]]
            setattr(stats, attribute, getattr(stats, attribute) + 1)


def process_flip(audit: Audit) -> None:
    filename = "flip_identity_diagnostic.csv"
    seen: set[tuple[Any, ...]] = set()
    omission = "cycles_and_dt_omitted_identity_is_mathematically_redundant_without_grid_update"
    for line, row in csv_rows(audit.bundle / filename, CSV_SCHEMAS[filename]):
        audit.row_counts[filename] += 1
        validate_common_axes(audit, row, filename, line)
        where = f"{filename}:{line}"
        spacing = canonical_choice(row["grid_spacing_m"], SPACINGS, where)
        audit.check(row["candidate"] == "FLIP diagnostic", f"{where}: wrong FLIP label")
        audit.check(row["eligibility"] == "ineligible", f"{where}: FLIP must be ineligible")
        audit.check(row["omitted_redundant_axes"] == omission, f"{where}: FLIP omission label")
        audit.check_float(row["kg_per_mass_quantum"], KG_PER_MASS_QUANTUM, f"{where}: mass scale")
        key = (
            row["field"],
            row["phase_index"],
            row["orientation_index"],
            row["layout"],
            spacing,
            row["mass_ratio"],
        )
        audit.check(key not in seen, f"{where}: duplicate FLIP key")
        seen.add(key)
        # Unlike a losing candidate metric, failure of this zero-grid-delta
        # identity means the diagnostic itself was not the preregistered FLIP case.
        audit.check(row["exact_mass_ok"], f"{where}: FLIP diagnostic lost exact mass")
        audit.check(
            row["identity_velocity_relative"] <= ROUNDOFF_FLOOR,
            f"{where}: zero-update FLIP is not identity",
        )
        audit.check(row["p2g_mass_relative"] <= MASS_TOLERANCE, f"{where}: FLIP P2G mass")
        audit.check(
            row["p2g_linear_relative"] <= LINEAR_MOMENTUM_TOLERANCE,
            f"{where}: FLIP P2G linear momentum",
        )
        audit.check(
            row["p2g_center_orbital_relative"] <= ANGULAR_MOMENTUM_TOLERANCE,
            f"{where}: FLIP P2G point-orbital momentum",
        )


def expected_row_counts(audit: Audit) -> dict[str, int]:
    p = audit.phase_count
    o = audit.orientation_count
    c = len(expected_cycles(audit.mode))
    return {
        "transfer_sweep.csv": 2 * 3 * p * o * 3 * 2 * 3 * c * 3,
        # Four metrics per PIC group; those four plus affine-matrix
        # reconstruction per APIC group.
        "h_convergence.csv": 9 * 3 * p * o * 3 * 2 * c * 3,
        "ballistic_regrid_sweep.csv": 2 * 3 * p * o * 3 * 2 * 3 * 3,
        "time_convergence.csv": 2 * 3 * p * o * 3 * 2 * 3 * 5,
        "flip_identity_diagnostic.csv": 3 * p * o * 3 * 2 * 3,
    }


def expected_group_counts(audit: Audit) -> dict[str, int]:
    p = audit.phase_count
    o = audit.orientation_count
    c = len(expected_cycles(audit.mode))
    return {
        "h_convergence_groups": 2 * 3 * p * o * 3 * 2 * c * 3,
        "time_convergence_groups": 2 * 3 * p * o * 3 * 2 * 3,
    }


def candidate_is_eligible(stats: CandidateStats) -> bool:
    # Center-only APIC orbital and energy series are explicitly diagnostic and
    # cannot disqualify APIC's declared center-plus-affine representation.
    return all(getattr(stats, name) == 0 for name in ELIGIBILITY_FAILURE_FIELDS)


def expected_recommendation(audit: Audit) -> str:
    if audit.mode == "smoke":
        return "not evaluated: smoke output is nonselection evidence"
    expected_rows = expected_row_counts(audit)
    expected_groups = expected_group_counts(audit)
    complete = all(audit.row_counts[name] == count for name, count in expected_rows.items())
    complete = complete and (
        sum(stats.h_groups for stats in audit.candidate_stats.values())
        == expected_groups["h_convergence_groups"]
        and sum(stats.time_groups for stats in audit.candidate_stats.values())
        == expected_groups["time_convergence_groups"]
    )
    pic_eligible = complete and candidate_is_eligible(audit.candidate_stats["PIC"])
    apic_eligible = complete and candidate_is_eligible(audit.candidate_stats["APIC"])
    if not pic_eligible and not apic_eligible:
        return "no provisional numerical promotion"
    if pic_eligible and not apic_eligible:
        return "PIC"
    if apic_eligible and not pic_eligible:
        return "APIC"
    pic = audit.candidate_stats["PIC"]
    apic = audit.candidate_stats["APIC"]
    pic_key = (
        pic.worst_affine_reconstruction,
        pic.worst_claimed_angular,
        pic.worst_numerical_energy_residual,
        pic.worst_64_cycle_drift,
    )
    apic_key = (
        apic.worst_affine_reconstruction,
        apic.worst_claimed_angular,
        apic.worst_numerical_energy_residual,
        apic.worst_64_cycle_drift,
    )
    return "APIC" if apic_key < pic_key else "PIC"


def validate_summary_policy(audit: Audit) -> None:
    summary = audit.summary
    required = {
        "schema",
        "mode",
        "selection_evidence",
        "external_gates_required",
        "seed",
        "source_sha_at_configure",
        "source_branch_at_configure",
        "source_dirty_at_configure",
        "compiler_id",
        "compiler_version",
        "time_scale",
        "mass_scale",
        "physical_energy_ledger_modified",
        "energy_differences_are_numerical_residuals_only",
        "time_experiment_interpretation",
        "excluded_physics",
        "executed_axis_counts",
        "frozen_full_axis_counts",
        "smoke_omissions",
        "evidence_counts_complete",
        "evidence_counts",
        "flip_diagnostic",
        "declared_angular_contract",
        "energy_convergence_all_below_rule",
        "candidates",
        "provisional_numerical_recommendation",
        "overall_recommendation",
        "csv_fnv1a64_diagnostic_only",
    }
    audit.check(required <= set(summary), f"summary.json missing keys {sorted(required - set(summary))}")
    audit.check(summary.get("schema") == SCHEMA, "wrong bundle schema")
    audit.check(summary.get("seed") == SEED, "wrong summary seed")
    audit.check(summary.get("selection_evidence") is False, "numerical harness issued selection evidence")
    audit.check(
        summary.get("external_gates_required")
        == [
            "runtime source provenance",
            "deterministic rerun",
            "checkpoint/replay",
            "C++",
            "Python",
            "Lean",
            "CI",
            "independent bundle verification",
        ],
        "summary external-gate declaration is incomplete",
    )
    audit.check(summary.get("physical_energy_ledger_modified") is False, "physical energy ledger was modified")
    audit.check(
        summary.get("energy_differences_are_numerical_residuals_only") is True,
        "energy differences are not isolated as numerical residuals",
    )
    audit.check(
        summary.get("frozen_full_axis_counts")
        == {"phases": 4, "proper_signed_axis_orientations": 24},
        "wrong frozen full axis counts",
    )
    expected_smoke_omissions = (
        "phases 1-3, orientations 2-23, cycles 16 and 64; smoke is not selection evidence"
        if audit.mode == "smoke"
        else None
    )
    audit.check(summary.get("smoke_omissions") == expected_smoke_omissions, "wrong smoke omissions")
    audit.check(
        summary.get("time_scale")
        == {
            "seconds_per_quantum_numerator": 1,
            "seconds_per_quantum_denominator": 40,
            "base_dt_quanta": 4,
            "fixed_horizon_quanta": 4,
        },
        "wrong time scale",
    )
    mass_scale = summary.get("mass_scale")
    audit.check(isinstance(mass_scale, dict), "mass_scale must be an object")
    if isinstance(mass_scale, dict):
        value = mass_scale.get("kilograms_per_exact_mass_quantum")
        audit.check(isinstance(value, (int, float)) and math.isfinite(value), "bad mass scale")
        if isinstance(value, (int, float)) and math.isfinite(value):
            audit.check_float(float(value), KG_PER_MASS_QUANTUM, "summary mass scale")
    audit.check(
        summary.get("flip_diagnostic")
        == {
            "selection_eligible": False,
            "omitted_redundant_axes": "cycles and dt; identity without grid update",
        },
        "FLIP summary must remain explicitly ineligible",
    )
    audit.check(
        summary.get("time_experiment_interpretation")
        == "force-free ballistic transfer-frequency sensitivity; not general temporal accuracy",
        "time experiment is mislabeled",
    )
    audit.check(
        summary.get("excluded_physics")
        == [
            "forces",
            "stress",
            "elasticity",
            "plasticity",
            "contact",
            "gravity",
            "fracture",
            "diffusion",
            "reaction kinetics",
            "organisms",
            "rendering",
            "GPU optimization",
        ],
        "excluded-physics declaration changed",
    )
    audit.check(
        summary.get("energy_convergence_all_below_rule")
        == "no energy hard tolerance was preregistered; only the 5e-14 roundoff floor or ratio branch is used",
        "energy convergence rule is mislabeled",
    )
    audit.check(
        "PIC uses center orbital angular momentum"
        in str(summary.get("declared_angular_contract", ""))
        and "APIC uses center plus affine angular momentum"
        in str(summary.get("declared_angular_contract", ""))
        and "diagnostic only" in str(summary.get("declared_angular_contract", "")),
        "summary does not preserve the declared candidate angular boundary",
    )
    candidates = summary.get("candidates")
    audit.check(
        isinstance(candidates, dict) and set(candidates) == set(CANDIDATES),
        "summary candidate set must be exactly PIC and APIC (FLIP is diagnostic)",
    )
    sha = summary.get("source_sha_at_configure")
    audit.check(
        isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha) is not None,
        "source_sha_at_configure is not a full lowercase Git SHA",
    )
    for key in ("source_branch_at_configure", "source_dirty_at_configure", "compiler_id", "compiler_version"):
        audit.check(isinstance(summary.get(key), str) and bool(summary.get(key)), f"missing {key}")
    audit.check(
        summary.get("overall_recommendation")
        == "not issued by numerical harness; external gates required",
        "numerical harness improperly issued an overall recommendation",
    )


def validate_hashes(audit: Audit) -> None:
    hashes = audit.summary.get("csv_fnv1a64_diagnostic_only")
    if not isinstance(hashes, dict):
        raise BundleError("summary csv_fnv1a64_diagnostic_only must be an object")
    audit.check(set(hashes) == set(REQUIRED_CSVS), "CSV hash manifest has missing or extra names")
    for filename in REQUIRED_CSVS:
        expected = hashes.get(filename)
        audit.check(
            isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{16}", expected) is not None,
            f"{filename}: malformed FNV-1a hash",
        )
        actual = fnv1a64(audit.bundle / filename)
        audit.check(actual == expected, f"{filename}: FNV-1a mismatch {actual} != {expected}")
    for filename in DETERMINISTIC_FILES:
        audit.sha256[filename] = sha256_file(audit.bundle / filename)


def load_json_object(path: Path, label: str) -> Mapping[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(
                stream,
                parse_constant=reject_json_constant,
                object_pairs_hook=strict_json_object,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise BundleError(f"cannot parse {label}: {error}") from error
    if not isinstance(value, dict):
        raise BundleError(f"{label} root must be an object")
    require_finite_json(value, label)
    return value


def resolve_evidence_file(audit: Audit, relative_name: Any, label: str) -> Path | None:
    if not isinstance(relative_name, str) or not relative_name:
        audit.check(False, f"{label}: file name must be a nonempty relative string")
        return None
    candidate = (audit.bundle / relative_name).resolve()
    try:
        candidate.relative_to(audit.bundle.resolve())
    except ValueError:
        audit.check(False, f"{label}: referenced file escapes the bundle")
        return None
    audit.check(candidate.is_file(), f"{label}: referenced file does not exist: {relative_name}")
    return candidate if candidate.is_file() else None


def validate_referenced_digest(
    audit: Audit, owner: Mapping[str, Any], file_key: str, hash_key: str, label: str
) -> None:
    path = resolve_evidence_file(audit, owner.get(file_key), label)
    expected = owner.get(hash_key)
    audit.check(
        isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected) is not None,
        f"{label}: malformed SHA-256",
    )
    if path is not None and isinstance(expected, str):
        audit.check(sha256_file(path) == expected, f"{label}: SHA-256 mismatch")


def git_command(repository: Path, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as error:
        raise BundleError(f"cannot execute Git provenance check: {error}") from error


def validate_runtime_git(audit: Audit, source_sha: Any) -> None:
    repository = Path(__file__).resolve().parents[1]
    head = git_command(repository, ("rev-parse", "HEAD"))
    branch = git_command(repository, ("branch", "--show-current"))
    tracked = git_command(repository, ("status", "--porcelain", "--untracked-files=no"))
    audit.check(head.returncode == 0, f"runtime Git HEAD query failed: {head.stderr.strip()}")
    audit.check(branch.returncode == 0, f"runtime Git branch query failed: {branch.stderr.strip()}")
    audit.check(tracked.returncode == 0, f"runtime Git cleanliness query failed: {tracked.stderr.strip()}")
    if head.returncode == 0:
        audit.check(head.stdout.strip() == source_sha, "runtime Git HEAD differs from sealed source SHA")
    if branch.returncode == 0:
        audit.check(branch.stdout.strip() == "time-transfer-lab", "runtime Git branch is not time-transfer-lab")
    if tracked.returncode == 0:
        audit.check(not tracked.stdout.strip(), "runtime tracked source tree is not clean")


def validate_external_gates(audit: Audit) -> None:
    audit.check(audit.mode == "full", "external selection gates require a full bundle")
    path = audit.bundle / "external_gates.json"
    if not path.is_file():
        audit.check(False, "missing required external_gates.json")
        return
    gates = load_json_object(path, "external_gates.json")
    audit.check(gates.get("schema") == EXTERNAL_GATES_SCHEMA, "wrong external-gates schema")
    source_sha = gates.get("source_sha")
    audit.check(
        isinstance(source_sha, str) and re.fullmatch(r"[0-9a-f]{40}", source_sha) is not None,
        "external source_sha is not a full lowercase Git SHA",
    )
    audit.check(
        source_sha == audit.summary.get("source_sha_at_configure"),
        "external source SHA differs from configure-time source SHA",
    )
    audit.check(gates.get("source_branch") == "time-transfer-lab", "external source branch")
    audit.check(gates.get("tracked_source_clean") is True, "external tracked-source gate is not green")
    audit.check(
        audit.summary.get("source_branch_at_configure") == "time-transfer-lab",
        "configure-time source branch is not time-transfer-lab",
    )
    audit.check(
        audit.summary.get("source_dirty_at_configure") == "false",
        "configure-time source was not clean",
    )
    if isinstance(source_sha, str):
        validate_runtime_git(audit, source_sha)

    local = gates.get("local")
    if not isinstance(local, dict):
        audit.check(False, "external local gates must be an object")
        local = {}
    audit.check(set(local) == set(REQUIRED_LOCAL_GATES), "external local gate set is incomplete or has extras")
    for gate_name in REQUIRED_LOCAL_GATES:
        gate = local.get(gate_name)
        label = f"local.{gate_name}"
        if not isinstance(gate, dict):
            audit.check(False, f"{label} must be an object")
            continue
        audit.check(gate.get("passed") is True, f"{label} did not pass")
        audit.check(
            isinstance(gate.get("command"), str) and bool(gate.get("command")),
            f"{label} has no exact command",
        )
        validate_referenced_digest(audit, gate, "log_file", "log_sha256", label)

    checkpoint = local.get("checkpoint", {})
    if isinstance(checkpoint, dict):
        audit.check(
            checkpoint.get("checkpoint_format_version") == 2,
            "checkpoint format version is not v2",
        )
        audit.check(
            checkpoint.get("physics_abi_version") == 1,
            "checkpoint physics ABI version is not v1",
        )
        audit.check(checkpoint.get("roundtrip_exact") is True, "checkpoint roundtrip is not exact")
        audit.check(
            checkpoint.get("continued_replay_exact") is True,
            "checkpoint continued replay is not exact",
        )
        audit.check(checkpoint.get("canonical_fixture_bytes") == 483, "checkpoint fixture byte count")
        audit.check(
            checkpoint.get("canonical_fixture_checksum_fnv1a64") == "6948438975031162627",
            "checkpoint canonical fixture checksum",
        )

    lean = local.get("lean", {})
    if isinstance(lean, dict):
        audit.check(lean.get("source_gate_passed") is True, "Lean source gate did not pass")
        theorem_count = lean.get("exported_theorem_count")
        audit.check(
            isinstance(theorem_count, int)
            and not isinstance(theorem_count, bool)
            and theorem_count > 0,
            "Lean exported theorem count must be positive",
        )
        audit.check(lean.get("project_defined_axioms") == [], "project-defined Lean axioms exist")
        audit.check(
            lean.get("sorry_admit_sorryAx_count") == 0,
            "Lean sorry/admit/sorryAx count is nonzero",
        )

    rerun = local.get("deterministic_rerun", {})
    if isinstance(rerun, dict):
        audit.check(
            rerun.get("all_csv_bytes_identical") is True,
            "deterministic rerun did not reproduce identical CSV bytes",
        )
        run_a = rerun.get("run_a_sha256")
        run_b = rerun.get("run_b_sha256")
        if not isinstance(run_a, dict) or not isinstance(run_b, dict):
            audit.check(False, "deterministic rerun SHA-256 maps must be objects")
        else:
            audit.check(set(run_a) == set(DETERMINISTIC_FILES), "run-A digest map has wrong files")
            audit.check(set(run_b) == set(DETERMINISTIC_FILES), "run-B digest map has wrong files")
            for filename in DETERMINISTIC_FILES:
                first = run_a.get(filename)
                second = run_b.get(filename)
                for label, value in (("run A", first), ("run B", second)):
                    audit.check(
                        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
                        f"{filename}: malformed {label} SHA-256",
                    )
                audit.check(first == second, f"{filename}: deterministic rerun digests differ")
                audit.check(
                    first == audit.sha256.get(filename),
                    f"{filename}: deterministic digest differs from sealed readback",
                )

    ci = gates.get("ci")
    if not isinstance(ci, dict):
        audit.check(False, "external CI gate must be an object")
        ci = {}
    run_id = ci.get("run_id")
    audit.check(
        isinstance(run_id, int) and not isinstance(run_id, bool) and run_id > 0,
        "CI run_id must be a positive integer",
    )
    audit.check(isinstance(ci.get("run_url"), str) and bool(ci.get("run_url")), "CI run URL missing")
    audit.check(ci.get("head_sha") == source_sha, "CI head SHA differs from source SHA")
    audit.check(ci.get("conclusion") == "success", "CI conclusion is not success")
    jobs = ci.get("jobs")
    audit.check(
        isinstance(jobs, dict) and set(jobs) == set(REQUIRED_CI_JOBS),
        "CI required-job map is incomplete or has extras",
    )
    if isinstance(jobs, dict):
        for job in REQUIRED_CI_JOBS:
            audit.check(jobs.get(job) == "success", f"CI job is not green: {job}")
    validate_referenced_digest(audit, ci, "evidence_file", "evidence_sha256", "ci")
    audit.known_failed_runs = gates.get("known_failed_runs")
    if audit.known_failed_runs is not None:
        audit.check(
            isinstance(audit.known_failed_runs, (list, dict)),
            "known_failed_runs is report-only but must be a list or object",
        )


def validate_aggregates(audit: Audit) -> None:
    expected_counts = expected_row_counts(audit)
    for filename, expected in expected_counts.items():
        audit.check(
            audit.row_counts[filename] == expected,
            f"{filename}: row count {audit.row_counts[filename]} != expected {expected}",
        )
    audit.check(
        audit.observed_phase_indices == set(range(audit.phase_count)),
        "executed phase index coverage is incomplete",
    )
    audit.check(
        audit.observed_orientation_indices == set(range(audit.orientation_count)),
        "executed orientation index coverage is incomplete",
    )
    audit.check(
        len(audit.orientation_by_index) == audit.orientation_count
        and len(audit.orientation_index_by_label) == audit.orientation_count,
        "orientation labels are not one-to-one with executed indices",
    )

    expected_groups = expected_group_counts(audit)
    actual_groups = {
        "h_convergence_groups": sum(
            stats.h_groups for stats in audit.candidate_stats.values()
        ),
        "time_convergence_groups": sum(
            stats.time_groups for stats in audit.candidate_stats.values()
        ),
    }
    evidence_counts = audit.summary.get("evidence_counts")
    expected_count_keys = {
        "transfer_sweep.csv",
        "h_convergence_groups",
        "h_convergence.csv",
        "ballistic_regrid_sweep.csv",
        "time_convergence_groups",
        "time_convergence.csv",
        "flip_identity_diagnostic.csv",
    }
    if not isinstance(evidence_counts, dict):
        audit.check(False, "summary evidence_counts must be an object")
        evidence_counts = {}
    audit.check(set(evidence_counts) == expected_count_keys, "summary evidence-count keys are wrong")
    for name, expected in expected_counts.items():
        entry = evidence_counts.get(name)
        audit.check(isinstance(entry, dict), f"summary evidence count {name} is malformed")
        if isinstance(entry, dict):
            audit.check(entry.get("expected_rows") == expected, f"{name}: wrong summary expected_rows")
            audit.check(
                entry.get("actual_rows") == audit.row_counts[name],
                f"{name}: wrong summary actual_rows",
            )
    for name, expected in expected_groups.items():
        entry = evidence_counts.get(name)
        audit.check(isinstance(entry, dict), f"summary evidence count {name} is malformed")
        if isinstance(entry, dict):
            audit.check(entry.get("expected") == expected, f"{name}: wrong summary expected groups")
            audit.check(entry.get("actual") == actual_groups[name], f"{name}: wrong summary actual groups")
    independently_complete = all(
        audit.row_counts[name] == expected for name, expected in expected_counts.items()
    ) and all(actual_groups[name] == expected for name, expected in expected_groups.items())
    audit.check(
        audit.summary.get("evidence_counts_complete") is independently_complete,
        "summary evidence_counts_complete differs from independent dimensions",
    )

    candidate_summary = audit.summary.get("candidates", {})
    if not isinstance(candidate_summary, dict):
        raise BundleError("summary candidates must be an object")
    for candidate in CANDIDATES:
        reported = candidate_summary.get(candidate)
        if not isinstance(reported, dict):
            audit.check(False, f"summary candidate {candidate} is missing or malformed")
            continue
        computed = audit.candidate_stats[candidate]
        for name in SUMMARY_INTEGER_FIELDS:
            audit.check(
                reported.get(name) == getattr(computed, name),
                f"summary {candidate}.{name}: {reported.get(name)!r} != {getattr(computed, name)!r}",
            )
        for name in SUMMARY_FLOAT_FIELDS:
            value = reported.get(name)
            audit.check(
                isinstance(value, (int, float)) and math.isfinite(value),
                f"summary {candidate}.{name} is not finite",
            )
            if isinstance(value, (int, float)) and math.isfinite(value):
                audit.check_float(float(value), getattr(computed, name), f"summary {candidate}.{name}")
        audit.check(
            reported.get("selection_eligible") is False,
            f"summary {candidate}.selection_eligible must remain false",
        )
        expected_eligible = (
            audit.mode == "full" and independently_complete and candidate_is_eligible(computed)
        )
        audit.check(
            reported.get("provisional_numerical_eligible") is expected_eligible,
            f"summary {candidate}.provisional_numerical_eligible is inconsistent",
        )

    recommendation = expected_recommendation(audit)
    audit.check(
        audit.summary.get("provisional_numerical_recommendation") == recommendation,
        "provisional numerical recommendation differs from independent computation: "
        f"{audit.summary.get('provisional_numerical_recommendation')!r} != {recommendation!r}",
    )


def build_audit(bundle: Path) -> Audit:
    if not bundle.is_dir():
        raise BundleError(f"bundle directory does not exist: {bundle}")
    summary_path = bundle / "summary.json"
    if not summary_path.is_file():
        raise BundleError(f"missing required file: {summary_path}")
    for filename in REQUIRED_CSVS:
        if not (bundle / filename).is_file():
            raise BundleError(f"missing required file: {bundle / filename}")
    summary = load_summary(summary_path)
    mode = summary.get("mode")
    if mode not in {"smoke", "full"}:
        raise BundleError(f"summary mode must be smoke or full, got {mode!r}")
    executed = summary.get("executed_axis_counts")
    if not isinstance(executed, dict):
        raise BundleError("executed_axis_counts must be an object")
    phase_count = executed.get("phases")
    orientation_count = executed.get("proper_signed_axis_orientations")
    expected_axes = (1, 2) if mode == "smoke" else (4, 24)
    if (phase_count, orientation_count) != expected_axes:
        raise BundleError(
            f"{mode} executed axes {(phase_count, orientation_count)!r} != {expected_axes!r}"
        )
    return Audit(bundle, summary, mode, int(phase_count), int(orientation_count))


def validate_bundle(bundle: Path, *, smoke_provisional: bool = False) -> Audit:
    audit = build_audit(bundle)
    if smoke_provisional and audit.mode != "smoke":
        raise BundleError("--smoke-provisional may only validate smoke bundles")
    validate_summary_policy(audit)
    validate_hashes(audit)
    process_transfer(audit)
    process_h_convergence(audit)
    process_ballistic(audit)
    process_time_convergence(audit)
    process_flip(audit)
    validate_aggregates(audit)
    if not smoke_provisional:
        validate_external_gates(audit)
    return audit


def files_identical(first: Path, second: Path) -> bool:
    try:
        if first.stat().st_size != second.stat().st_size:
            return False
        with first.open("rb") as left, second.open("rb") as right:
            while True:
                left_chunk = left.read(1024 * 1024)
                right_chunk = right.read(1024 * 1024)
                if left_chunk != right_chunk:
                    return False
                if not left_chunk:
                    return True
    except OSError as error:
        raise BundleError(f"cannot compare deterministic bundles: {error}") from error


def compare_bundles(first: Audit, second: Audit) -> None:
    first.check(first.mode == second.mode, "comparison bundle mode differs")
    for filename in DETERMINISTIC_FILES:
        first_hash = first.sha256.get(filename)
        second_hash = second.sha256.get(filename)
        first.check(first_hash == second_hash, f"{filename}: comparison SHA-256 differs")
        first.check(
            files_identical(first.bundle / filename, second.bundle / filename),
            f"{filename}: comparison bytes differ",
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="independently validate a Time + Transfer evidence bundle"
    )
    parser.add_argument("--bundle", type=Path, required=True, help="directory containing summary.json and CSV evidence")
    parser.add_argument(
        "--compare",
        type=Path,
        help="validate a second bundle and require its five CSVs and summary to be byte-identical",
    )
    parser.add_argument(
        "--smoke-provisional",
        action="store_true",
        help="validate smoke structure and decisions without requiring external_gates.json",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        audit = validate_bundle(
            arguments.bundle.resolve(), smoke_provisional=arguments.smoke_provisional
        )
        comparison = None
        if arguments.compare is not None:
            comparison = validate_bundle(
                arguments.compare.resolve(), smoke_provisional=arguments.smoke_provisional
            )
            compare_bundles(audit, comparison)
    except BundleError as error:
        print(f"TRANSFER BUNDLE INVALID: {error}", file=sys.stderr)
        return 1
    combined_errors = list(audit.errors)
    if comparison is not None:
        combined_errors.extend(f"comparison: {message}" for message in comparison.errors)
    if combined_errors:
        print(
            f"TRANSFER BUNDLE INVALID: {len(combined_errors)} independent audit mismatch(es)",
            file=sys.stderr,
        )
        for message in combined_errors[:100]:
            print(f"  - {message}", file=sys.stderr)
        if len(combined_errors) > 100:
            print(f"  - ... {len(combined_errors) - 100} more", file=sys.stderr)
        return 1
    counts = ", ".join(f"{name}={audit.row_counts[name]}" for name in REQUIRED_CSVS)
    overall = (
        "not issued: smoke provisional validation"
        if arguments.smoke_provisional
        else expected_recommendation(audit).replace("provisional numerical ", "")
    )
    digest_lines = "\n".join(
        f"sha256[{name}]={audit.sha256[name]}" for name in DETERMINISTIC_FILES
    )
    known_failures = (
        "none reported"
        if audit.known_failed_runs is None
        else f"reported ({len(audit.known_failed_runs)})"
    )
    print(
        "TRANSFER BUNDLE VALID\n"
        f"schema={SCHEMA} mode={audit.mode} seed={SEED}\n"
        f"rows: {counts}\n"
        "provisional_numerical_recommendation="
        f"{audit.summary['provisional_numerical_recommendation']}\n"
        f"overall_recommendation={overall}\n"
        f"byte_identical_comparison={'yes' if comparison is not None else 'not requested'}\n"
        f"known_failed_runs={known_failures}\n"
        f"{digest_lines}\n"
        "scope=evidence consistency only; no continuum-mechanics validation"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
