#!/usr/bin/env python3
"""Determinism and semantic-mutation regression for the fractional oracle."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import struct
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Callable


Mutation = Callable[[Path, Path], None]


def load_oracle(repository: Path) -> ModuleType:
    reference = repository / "reference"
    sys.path.insert(0, str(reference))
    path = reference / "explicit_fractional_phase_state_oracle.py"
    specification = importlib.util.spec_from_file_location("fractional_phase_oracle", path)
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load fractional phase-state oracle")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def edit_cell(
    root: Path,
    filename: str,
    predicate: Callable[[dict[str, str]], bool],
    column: str,
    value: Callable[[str], str] | str,
) -> None:
    path = root / filename
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fieldnames = list(reader.fieldnames or [])
        content = list(reader)
    changed = False
    for row in content:
        if not changed and predicate(row):
            row[column] = value(row[column]) if callable(value) else value
            changed = True
    if not changed:
        raise RuntimeError(f"mutation target absent: {filename}/{column}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(content)


def add_hidden_column(root: Path) -> None:
    path = root / "initial_states.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[0] += ",relation_remainder"
    lines[1:] = [line + ",0" for line in lines[1:]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def float_bits(value: float) -> str:
    return str(struct.unpack(">Q", struct.pack(">d", value))[0])


def scientific_signature(result: dict[str, object]) -> str:
    selected = {
        key: value
        for key, value in result.items()
        if key not in {"raw_files", "source_sha"}
    }
    return json.dumps(selected, sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--parent-raw", type=Path, required=True)
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    oracle = load_oracle(repository)

    parent_units = oracle.parent.verify_units(arguments.parent_raw)
    models = oracle.parent.load_models(arguments.parent_raw, parent_units)
    initial = oracle.parent.load_initial_physical(arguments.parent_raw, parent_units)
    precomputed = oracle.foundation.oracle_states(models, initial)
    baseline = oracle.verify(arguments.raw, arguments.parent_raw, True, precomputed)
    repeated = oracle.verify(arguments.raw, arguments.parent_raw, True, precomputed)
    if baseline != repeated:
        raise RuntimeError("two oracle positives differ")
    if baseline["decision"] != (
        "fractional_phase_state_restores_dynamics_but_bounded_representation_unresolved"
    ):
        raise RuntimeError("baseline decision differs")
    baseline_signature = scientific_signature(baseline)

    mutations: list[tuple[str, Mutation]] = [
        ("wrong_parent_payload", lambda _raw, parent: edit_cell(
            parent, "units.csv", lambda row: row["level"] == "0", "Lq", "1/127000000000")),
        ("wrong_parent_sha", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "accepted_parent_sha", "value", "0" * 40)),
        ("wrong_parent_tag", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "accepted_parent_tag", "value", "wrong")),
        ("wrong_parent_tag_object", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "accepted_parent_tag_object", "value", "0" * 40)),
        ("wrong_parent_archive", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "accepted_parent_archive_sha256", "value", "0" * 64)),
        ("wrong_branch", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "branch", "value", "main")),
        ("wrong_candidate", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "candidate", "value", "fixed_subgrid")),
        ("wrong_backend", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "rational_arithmetic_backend", "value", "binary64")),
        ("wrong_geometry", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "force_geometry", "value", "direct_norm_subtraction")),
        ("wrong_safe_domain", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "safe_domain", "value", "0")),
        ("hidden_width", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "coarse_integer_width", "value", "unbounded")),
        ("fixed_denominator", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "fractional_denominator", "value", "2^128")),
        ("hidden_relation_remainder", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "relation_remainder_present", "value", "true")),
        ("hidden_energy_store", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "energy_discrepancy_stored", "value", "true")),
        ("changed_maximum_budget", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "maximum_component_bits", "value", "999999")),
        ("changed_median_budget", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "median_component_bits", "value", "999999")),
        ("changed_checkpoint_budget", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "maximum_checkpoint_bytes", "value", "999999")),
        ("promotion_relabelled", lambda raw, _parent: edit_cell(
            raw, "metadata.csv", lambda row: row["key"] == "promotion", "value", "PROMOTED")),
        ("changed_length_quantum", lambda raw, _parent: edit_cell(
            raw, "units.csv", lambda row: True, "Lq", "1/127000000000")),
        ("changed_canonical_interval", lambda raw, _parent: edit_cell(
            raw, "units.csv", lambda row: True, "canonical_interval", "[0,1)")),
        ("adaptive_units", lambda raw, _parent: edit_cell(
            raw, "units.csv", lambda row: True, "fixed_across_levels", "false")),
        ("parent_fingerprint_false", lambda raw, _parent: edit_cell(
            raw, "parent_fingerprint.csv", lambda row: True, "passed", "false")),
        ("changed_reference_geometry", lambda raw, _parent: edit_cell(
            raw, "reference_packets.csv", lambda row: row["model_id"] == "k4" and row["packet_id"] == "2",
            "x_raw", lambda value: str(int(value) + 1))),
        ("wrong_relation_orientation", lambda raw, _parent: edit_cell(
            raw, "relations.csv", lambda row: row["model_id"] == "k4" and row["relation_index"] == "0",
            "first_id", "2")),
        ("changed_force_operator", lambda raw, _parent: edit_cell(
            raw, "force_operator.csv", lambda row: row["model_id"] == "k4" and row["row"] == "0" and row["column"] == "0",
            "h_bits", float_bits(0.75))),
        ("unreduced_initial_fraction", lambda raw, _parent: (
            edit_cell(raw, "initial_states.csv", lambda row: row["scenario_id"] == "k4_internal", "xx_num", "2"),
            edit_cell(raw, "initial_states.csv", lambda row: row["scenario_id"] == "k4_internal", "xx_den", "4"))),
        ("false_endpoint", lambda raw, _parent: edit_cell(
            raw, "endpoints.csv", lambda row: row["scenario_id"] == "k4_internal" and row["path"] == oracle.KDK and row["level"] == "4",
            "xx_coarse", lambda value: str(int(value) + 1))),
        ("false_state_hash", lambda raw, _parent: edit_cell(
            raw, "endpoints.csv", lambda row: True, "state_hash", "0" * 64)),
        ("false_invariant_value", lambda raw, _parent: edit_cell(
            raw, "invariants.csv", lambda row: True, "p_x_num", lambda value: str(int(value) + 1))),
        ("false_invariant_declaration", lambda raw, _parent: edit_cell(
            raw, "invariants.csv", lambda row: True, "momentum_equal_initial", "false")),
        ("noncentral_kick", lambda raw, _parent: edit_cell(
            raw, "force_audit.csv", lambda row: True, "central_cross_zero", "false")),
        ("false_reversibility", lambda raw, _parent: edit_cell(
            raw, "reversibility.csv", lambda row: True, "complete_state_identical", "false")),
        ("changed_recovery_state", lambda raw, _parent: edit_cell(
            raw, "recovery_states.csv", lambda row: True, "px_coarse", lambda value: str(int(value) + 1))),
        ("changed_checkpoint_state", lambda raw, _parent: edit_cell(
            raw, "checkpoint_states.csv", lambda row: True, "xx_coarse", lambda value: str(int(value) + 1))),
        ("checkpoint_divergence", lambda raw, _parent: edit_cell(
            raw, "checkpoint.csv", lambda row: True, "event_suffix_identical", "false")),
        ("non_atomic_domain_rejection", lambda raw, _parent: edit_cell(
            raw, "domain.csv", lambda row: True, "state_unchanged", "false")),
        ("false_frame_covariance", lambda raw, _parent: edit_cell(
            raw, "covariance.csv", lambda row: row["kind"] == "galilean_boost", "position_discrepancy_num", "1")),
        ("changed_energy_trace", lambda raw, _parent: edit_cell(
            raw, "long_energy.csv", lambda row: row["level"] == "4" and row["sample"] == "1",
            "mechanical_energy_bits", float_bits(123.0))),
        ("false_complexity", lambda raw, _parent: edit_cell(
            raw, "state_complexity.csv", lambda row: row["trajectory_id"] == "long:k4_internal:L4" and row["step"] == "398",
            "numerator_bits", "300000")),
        ("false_obstruction_product", lambda raw, _parent: edit_cell(
            raw, "obstruction.csv", lambda row: True, "product", "1/1")),
        ("hidden_state_column", lambda raw, _parent: add_hidden_column(raw)),
    ]

    detected = 0
    with tempfile.TemporaryDirectory(prefix="mls-fractional-mutations-") as directory:
        temporary = Path(directory)
        for index, (name, mutation) in enumerate(mutations):
            candidate = temporary / f"{index:02d}-{name}" / "raw"
            parent_raw = temporary / f"{index:02d}-{name}" / "parent"
            shutil.copytree(arguments.raw, candidate)
            shutil.copytree(arguments.parent_raw, parent_raw)
            mutation(candidate, parent_raw)
            try:
                result = oracle.verify(candidate, parent_raw, True, precomputed)
                changed = scientific_signature(result) != baseline_signature
            except (
                OSError,
                ValueError,
                ArithmeticError,
                IndexError,
                KeyError,
                OverflowError,
                oracle.OracleError,
                oracle.parent.OracleError,
                oracle.foundation.OracleError,
            ):
                changed = True
            if not changed:
                raise RuntimeError(f"mutation was not detected: {name}")
            detected += 1
            shutil.rmtree(candidate.parent)

    print(
        "EXPLICIT FRACTIONAL PHASE STATE ORACLE MUTATIONS: "
        f"PASS (2 deterministic positives, {detected} mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
