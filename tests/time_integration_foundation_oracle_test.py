#!/usr/bin/env python3
"""Semantic mutation regression for the Time Integration Foundation oracle."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import struct
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Callable


def load_oracle(root: Path) -> ModuleType:
    path = root / "reference" / "time_integration_foundation_oracle.py"
    specification = importlib.util.spec_from_file_location("time_integration_oracle", path)
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load time integration oracle")
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
        rows = list(reader)
    changed = False
    for row in rows:
        if not changed and predicate(row):
            row[column] = value(row[column]) if callable(value) else value
            changed = True
    if not changed:
        raise RuntimeError(f"mutation target absent: {filename}/{column}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def add_hidden_column(root: Path) -> None:
    path = root / "initial_states.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[0] += ",position_remainder_raw"
    for index in range(1, len(lines)):
        lines[index] += ",0"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def float_bits(value: float) -> str:
    return str(struct.unpack(">Q", struct.pack(">d", value))[0])


def scientific_signature(result: dict[str, object]) -> str:
    return json.dumps(
        {
            "decision": result["decision"],
            "convergence": result["convergence"],
            "energy": result["energy"],
            "exact_gates": result["exact_gates"],
        },
        sort_keys=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    oracle = load_oracle(repository)

    lq, mq, pq = oracle.verify_metadata(arguments.raw)
    models = oracle.load_models(arguments.raw, lq, mq)
    initial, _ = oracle.load_initial_states(arguments.raw, lq, pq)
    precomputed = oracle.oracle_states(models, initial)
    baseline = oracle.verify(arguments.raw, precomputed)
    baseline_signature = scientific_signature(baseline)
    if baseline["decision"] != "temporal_convergence_blocked_by_authoritative_quantization":
        raise RuntimeError("baseline decision differs")

    mutations: list[tuple[str, Callable[[Path], None]]] = [
        (
            "wrong_parent",
            lambda root: edit_cell(
                root, "metadata.csv", lambda row: row["key"] == "accepted_parent_sha",
                "value", "0" * 40,
            ),
        ),
        (
            "wrong_refinement",
            lambda root: edit_cell(
                root, "metadata.csv", lambda row: row["key"] == "selected_refinement",
                "value", "64",
            ),
        ),
        (
            "changed_H",
            lambda root: edit_cell(
                root, "force_operator.csv",
                lambda row: row["model_id"] == "k4" and row["row"] == "0" and row["column"] == "0",
                "h_bits", float_bits(0.75),
            ),
        ),
        (
            "changed_reference",
            lambda root: edit_cell(
                root, "reference_packets.csv",
                lambda row: row["model_id"] == "k4" and row["packet_id"] == "2",
                "x_raw", lambda value: str(int(value) + 1),
            ),
        ),
        (
            "candidate_relabelled_as_control",
            lambda root: edit_cell(
                root, "endpoints.csv",
                lambda row: row["scenario_id"] == "k4_breathing"
                and row["path"] == "quantized_kick_drift_kick",
                "path", "symplectic_euler_control",
            ),
        ),
        (
            "unequal_kick",
            lambda root: edit_cell(
                root, "endpoints.csv",
                lambda row: row["scenario_id"] == "k4_breathing"
                and row["path"] == "quantized_kick_drift_kick"
                and row["level"] == "0" and row["packet_id"] == "1",
                "px_raw", lambda value: str(int(value) + 1),
            ),
        ),
        (
            "false_invariant",
            lambda root: edit_cell(
                root, "endpoints.csv", lambda row: True,
                "momentum_preserved", "false",
            ),
        ),
        (
            "omitted_chord_interior",
            lambda root: edit_cell(
                root, "domain.csv", lambda row: True,
                "status", "accepted",
            ),
        ),
        (
            "partial_commit",
            lambda root: edit_cell(
                root, "domain.csv", lambda row: True,
                "state_unchanged", "false",
            ),
        ),
        (
            "odd_timestep",
            lambda root: edit_cell(
                root, "endpoints.csv", lambda row: True,
                "dt_raw", lambda value: str(int(value) + 1),
            ),
        ),
        ("hidden_remainder", add_hidden_column),
        (
            "altered_nearest_even_tie",
            lambda root: edit_cell(
                root, "rounding_controls.csv",
                lambda row: row["numerator"] == "5" and row["denominator"] == "2",
                "nearest_even", "3",
            ),
        ),
        (
            "false_reversibility",
            lambda root: edit_cell(
                root, "reversibility.csv", lambda row: True,
                "bit_identical", "false",
            ),
        ),
        (
            "false_order_endpoint",
            lambda root: edit_cell(
                root, "endpoints.csv",
                lambda row: row["scenario_id"] == "k4_internal"
                and row["path"] == "quantized_kick_drift_kick"
                and row["level"] == "4" and row["packet_id"] == "1",
                "x_raw", lambda value: str(int(value) + 1_000_000),
            ),
        ),
        (
            "boost_relabel",
            lambda root: edit_cell(
                root, "covariance.csv",
                lambda row: row["kind"] == "galilean_boost",
                "kind", "translation",
            ),
        ),
        (
            "rotation_remap_error",
            lambda root: edit_cell(
                root, "covariance.csv",
                lambda row: row["kind"] == "proper_lattice_rotation",
                "position_discrepancy_raw", "1",
            ),
        ),
        (
            "checkpoint_omission",
            lambda root: edit_cell(
                root, "checkpoint.csv", lambda row: True,
                "event_suffix_identical", "false",
            ),
        ),
        (
            "stored_energy_discrepancy",
            lambda root: edit_cell(
                root, "metadata.csv", lambda row: row["key"] == "energy_discrepancy_stored",
                "value", "true",
            ),
        ),
        (
            "changed_energy_trace",
            lambda root: edit_cell(
                root, "energies.csv", lambda row: row["sample"] == "1",
                "mechanical_energy_bits", float_bits(123.0),
            ),
        ),
        (
            "parent_fingerprint_false",
            lambda root: edit_cell(
                root, "parent_fingerprint.csv", lambda row: True,
                "passed", "false",
            ),
        ),
    ]

    detected = 0
    with tempfile.TemporaryDirectory(prefix="mls-time-integration-mutations-") as directory:
        temporary = Path(directory)
        for name, mutation in mutations:
            mutated = temporary / name
            shutil.copytree(arguments.raw, mutated)
            mutation(mutated)
            try:
                result = oracle.verify(mutated, precomputed)
                changed = scientific_signature(result) != baseline_signature
            except (OSError, ValueError, ArithmeticError, IndexError, KeyError,
                    oracle.OracleError):
                changed = True
            if not changed:
                raise RuntimeError(f"mutation was not detected: {name}")
            detected += 1

    print(
        "TIME INTEGRATION FOUNDATION ORACLE MUTATIONS: "
        f"PASS (1 deterministic positive, {detected} mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
