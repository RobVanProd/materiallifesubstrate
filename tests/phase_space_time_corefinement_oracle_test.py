#!/usr/bin/env python3
"""Determinism and semantic-mutation regression for the co-refinement oracle."""

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
    path = reference / "phase_space_time_corefinement_oracle.py"
    specification = importlib.util.spec_from_file_location("corefinement_oracle", path)
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load co-refinement oracle")
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
    lines[0] += ",position_remainder_raw"
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

    units = oracle.verify_units(arguments.raw)
    models = oracle.load_models(arguments.raw, units)
    initial = oracle.load_initial_physical(arguments.raw, units)
    precomputed = oracle.foundation.oracle_states(models, initial)
    baseline = oracle.verify(arguments.raw, arguments.parent_raw, precomputed)
    repeated = oracle.verify(arguments.raw, arguments.parent_raw, precomputed)
    if baseline != repeated:
        raise RuntimeError("two oracle positives differ")
    if baseline["decision"] != "reject_order_matched_space_time_corefinement":
        raise RuntimeError("baseline decision differs")
    baseline_signature = scientific_signature(baseline)

    mutations: list[tuple[str, Mutation]] = [
        (
            "wrong_parent_payload",
            lambda _raw, parent: edit_cell(
                parent, "units.csv", lambda row: True, "Lq", "1/127000000000"
            ),
        ),
        (
            "altered_length_exponent",
            lambda raw, _parent: edit_cell(
                raw, "units.csv", lambda row: row["level"] == "2", "Lq", "1/1"
            ),
        ),
        (
            "altered_mass_quantum",
            lambda raw, _parent: edit_cell(
                raw, "units.csv", lambda row: row["level"] == "1", "Mq", "1/524287"
            ),
        ),
        (
            "altered_time_exponent",
            lambda raw, _parent: edit_cell(
                raw, "units.csv", lambda row: row["level"] == "3", "Tq", "1/1"
            ),
        ),
        (
            "inconsistent_momentum_quantum",
            lambda raw, _parent: edit_cell(
                raw, "units.csv", lambda row: row["level"] == "4", "Pq", "1/1"
            ),
        ),
        (
            "inconsistent_energy_quantum",
            lambda raw, _parent: edit_cell(
                raw, "units.csv", lambda row: row["level"] == "2", "Eq", "1/1"
            ),
        ),
        (
            "inconsistent_force_quantum",
            lambda raw, _parent: edit_cell(
                raw, "units.csv", lambda row: row["level"] == "1", "Fq", "1/1"
            ),
        ),
        (
            "altered_raw_timestep",
            lambda raw, _parent: edit_cell(
                raw, "units.csv", lambda row: row["level"] == "4", "dt_raw", "1"
            ),
        ),
        (
            "hidden_refinement_increase",
            lambda raw, _parent: edit_cell(
                raw,
                "metadata.csv",
                lambda row: row["key"] == "base_representation",
                "value",
                "R=256",
            ),
        ),
        (
            "hidden_integer_width_increase",
            lambda raw, _parent: edit_cell(
                raw,
                "metadata.csv",
                lambda row: row["key"] == "authoritative_integer_width",
                "value",
                "signed128",
            ),
        ),
        (
            "hidden_remainder_metadata",
            lambda raw, _parent: edit_cell(
                raw,
                "metadata.csv",
                lambda row: row["key"] == "position_remainder_present",
                "value",
                "true",
            ),
        ),
        ("hidden_remainder_column", lambda raw, _parent: add_hidden_column(raw)),
        (
            "adaptive_profile",
            lambda raw, _parent: edit_cell(
                raw,
                "metadata.csv",
                lambda row: row["key"] == "adaptive_profile_present",
                "value",
                "true",
            ),
        ),
        (
            "overflow_relabelled",
            lambda raw, _parent: edit_cell(
                raw,
                "mapping.csv",
                lambda row: row["scenario_id"] == "k4_translated"
                and row["level"] == "4",
                "status",
                "mapped",
            ),
        ),
        (
            "parent_fingerprint_false",
            lambda raw, _parent: edit_cell(
                raw, "parent_fingerprint.csv", lambda row: True, "passed", "false"
            ),
        ),
        (
            "changed_force_operator",
            lambda raw, _parent: edit_cell(
                raw,
                "force_operator.csv",
                lambda row: row["model_id"] == "k4"
                and row["row"] == "0"
                and row["column"] == "0",
                "h_bits",
                float_bits(0.75),
            ),
        ),
        (
            "wrong_relation_orientation",
            lambda raw, _parent: edit_cell(
                raw,
                "relations.csv",
                lambda row: row["model_id"] == "k4" and row["relation_index"] == "0",
                "first_id",
                "2",
            ),
        ),
        (
            "changed_reference_geometry",
            lambda raw, _parent: edit_cell(
                raw,
                "reference_packets.csv",
                lambda row: row["model_id"] == "k4"
                and row["level"] == "0"
                and row["packet_id"] == "2",
                "x_raw",
                lambda value: str(int(value) + 1),
            ),
        ),
        (
            "changed_initial_state",
            lambda raw, _parent: edit_cell(
                raw,
                "initial_states.csv",
                lambda row: row["scenario_id"] == "k4_internal"
                and row["level"] == "0"
                and row["packet_id"] == "1",
                "px_raw",
                lambda value: str(int(value) + 1),
            ),
        ),
        (
            "wrong_momentum_gcd",
            lambda raw, _parent: edit_cell(
                raw,
                "primitive_diagnostics.csv",
                lambda row: int(row["g"]) > 0,
                "g",
                lambda value: str(int(value) + 1),
            ),
        ),
        (
            "wrong_momentum_primitive",
            lambda raw, _parent: edit_cell(
                raw,
                "primitive_diagnostics.csv",
                lambda row: int(row["g"]) > 0,
                "ux",
                lambda value: str(int(value) + 1),
            ),
        ),
        (
            "wrong_minimum_drift",
            lambda raw, _parent: edit_cell(
                raw,
                "primitive_diagnostics.csv",
                lambda row: int(row["g"]) > 0,
                "minimum_drift_m_bits",
                lambda value: str(int(value) + 1),
            ),
        ),
        (
            "wrong_relation_gcd",
            lambda raw, _parent: edit_cell(
                raw,
                "relation_primitive_diagnostics.csv",
                lambda row: True,
                "g",
                lambda value: str(int(value) + 1),
            ),
        ),
        (
            "wrong_relation_applied_multiple",
            lambda raw, _parent: edit_cell(
                raw,
                "relation_primitive_diagnostics.csv",
                lambda row: True,
                "applied_multiple",
                lambda value: str(int(value) + 1),
            ),
        ),
        (
            "wrong_minimum_impulse",
            lambda raw, _parent: edit_cell(
                raw,
                "relation_primitive_diagnostics.csv",
                lambda row: True,
                "minimum_impulse_bits",
                lambda value: str(int(value) + 1),
            ),
        ),
        (
            "false_order_endpoint",
            lambda raw, _parent: edit_cell(
                raw,
                "endpoints.csv",
                lambda row: row["scenario_id"] == "k4_internal"
                and row["path"] == "quantized_kick_drift_kick"
                and row["level"] == "4"
                and row["packet_id"] == "1",
                "x_raw",
                lambda value: str(int(value) + 1_000_000),
            ),
        ),
        (
            "false_boost_convergence",
            lambda raw, _parent: edit_cell(
                raw,
                "covariance.csv",
                lambda row: row["kind"] == "galilean_boost" and row["level"] == "4",
                "position_discrepancy_raw",
                "1000000",
            ),
        ),
        (
            "false_reversibility",
            lambda raw, _parent: edit_cell(
                raw, "reversibility.csv", lambda row: True, "bit_identical", "false"
            ),
        ),
        (
            "non_atomic_domain_rejection",
            lambda raw, _parent: edit_cell(
                raw, "domain.csv", lambda row: True, "state_unchanged", "false"
            ),
        ),
        (
            "checkpoint_divergence",
            lambda raw, _parent: edit_cell(
                raw,
                "checkpoint.csv",
                lambda row: True,
                "event_suffix_identical",
                "false",
            ),
        ),
        (
            "changed_energy_trace",
            lambda raw, _parent: edit_cell(
                raw,
                "long_energy.csv",
                lambda row: row["level"] == "4" and row["sample"] == "1",
                "mechanical_energy_bits",
                float_bits(123.0),
            ),
        ),
        (
            "bridge_force_failure_relabelled",
            lambda raw, _parent: edit_cell(
                raw, "bridge_contracts.csv", lambda row: True, "path_b_force", "false"
            ),
        ),
        (
            "false_invariant_declaration",
            lambda raw, _parent: edit_cell(
                raw, "endpoints.csv", lambda row: True, "momentum_preserved", "false"
            ),
        ),
    ]

    detected = 0
    with tempfile.TemporaryDirectory(prefix="mls-corefinement-mutations-") as directory:
        temporary = Path(directory)
        for index, (name, mutation) in enumerate(mutations):
            candidate = temporary / f"{index:02d}-{name}" / "raw"
            parent = temporary / f"{index:02d}-{name}" / "parent"
            shutil.copytree(arguments.raw, candidate)
            shutil.copytree(arguments.parent_raw, parent)
            mutation(candidate, parent)
            try:
                result = oracle.verify(candidate, parent, precomputed)
                changed = scientific_signature(result) != baseline_signature
            except (
                OSError,
                ValueError,
                ArithmeticError,
                IndexError,
                KeyError,
                oracle.OracleError,
                oracle.foundation.OracleError,
            ):
                changed = True
            if not changed:
                raise RuntimeError(f"mutation was not detected: {name}")
            detected += 1
            shutil.rmtree(candidate.parent)

    print(
        "PHASE SPACE TIME COREFINEMENT ORACLE MUTATIONS: "
        f"PASS (2 deterministic positives, {detected} mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
