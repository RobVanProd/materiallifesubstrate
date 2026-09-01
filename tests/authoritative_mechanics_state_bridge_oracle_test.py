#!/usr/bin/env python3
"""Determinism and fail-closed mutations for the mechanics bridge oracle."""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable


def invoke(oracle: Path, raw: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(oracle), "--raw", str(raw), "--output", str(output)],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        env={**dict(__import__("os").environ), "PYTHONDONTWRITEBYTECODE": "1"},
    )


def mutate_csv(path: Path, mutation: Callable[[list[dict[str, str]]], None]) -> None:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or ())
        values = list(reader)
    mutation(values)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def first(field: str, value: str) -> Callable[[list[dict[str, str]]], None]:
    def mutate(values: list[dict[str, str]]) -> None:
        values[0][field] = value
    return mutate


def relation_path(values: list[dict[str, str]]) -> None:
    values[0]["geometry_path"] = "frozen_binary64"


def noncentral(values: list[dict[str, str]]) -> None:
    for row in values:
        if row["path"] == "fixed_point_refinement" and row["refinement"] == "16":
            row["impulse_z_raw"] = "1"
            return
    raise AssertionError("noncentral target absent")


def unequal(values: list[dict[str, str]]) -> None:
    values[0]["opposite_x_raw"] = str(int(values[0]["opposite_x_raw"]) + 1)


def hidden_remainder(values: list[dict[str, str]]) -> None:
    for row in values:
        if row["path"] == "explicit_remainder" and row["subdivisions"] == "16":
            row["checkpoint_remainder_bits"] = "0"
            return
    raise AssertionError("remainder target absent")


def altered_checkpoint_hash(values: list[dict[str, str]]) -> None:
    for row in values:
        if row["path"] == "explicit_remainder":
            row["checkpoint_hash"] = str(int(row["checkpoint_hash"]) ^ 1)
            return


def relabel_subdivision(values: list[dict[str, str]]) -> None:
    for row in values:
        if row["path"] == "direct_nearest" and row["subdivisions"] == "16":
            row["applied_multiple"] = "2"
            return


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument(
        "--oracle",
        type=Path,
        default=root / "reference" / "authoritative_mechanics_state_bridge_oracle.py",
    )
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="mls-mechanics-bridge-oracle-") as temporary:
        directory = Path(temporary)
        raw = directory / "raw"
        shutil.copytree(arguments.raw, raw)
        first_output = directory / "positive-a.json"
        second_output = directory / "positive-b.json"
        first_run = invoke(arguments.oracle, raw, first_output)
        second_run = invoke(arguments.oracle, raw, second_output)
        if first_run.returncode != 0 or second_run.returncode != 0:
            raise AssertionError(
                f"positive oracle failed\n{first_run.stdout}\n{first_run.stderr}\n"
                f"{second_run.stdout}\n{second_run.stderr}"
            )
        if first_output.read_bytes() != second_output.read_bytes() or (
            first_output.with_suffix(".csv").read_bytes()
            != second_output.with_suffix(".csv").read_bytes()
        ):
            raise AssertionError("positive oracle output differs")

        mutations: tuple[tuple[str, str, Callable[[list[dict[str, str]]], None]], ...] = (
            ("altered-Lq", "units.csv", first("Lq", "1/999999999")),
            ("nonunit-velocity-scale", "units.csv", first("velocity_scale_numerator", "3")),
            ("changed-mass", "packets_bits.csv", first("base_mass_raw", "2")),
            ("changed-reference-coordinate", "packets_bits.csv", first("base_x_raw", "1")),
            ("changed-H", "h_bits.csv", first("h_bits", "0")),
            ("Path-A-masquerading-as-B", "relations_bits.csv", relation_path),
            ("noncentral-component-rounding", "evaluations.csv", noncentral),
            ("unequal-impulses", "evaluations.csv", unequal),
            ("hidden-remainder", "evaluations.csv", hidden_remainder),
            ("checkpoint-hash-omission", "evaluations.csv", altered_checkpoint_hash),
            ("subdivision-relabel", "evaluations.csv", relabel_subdivision),
            ("kinetic-floor-order", "evaluations.csv", first("kinetic_raw", "1")),
        )
        for label, name, mutation in mutations:
            target = raw / name
            original = target.read_bytes()
            mutate_csv(target, mutation)
            completed = invoke(arguments.oracle, raw, directory / f"mutation-{label}.json")
            target.write_bytes(original)
            if completed.returncode == 0:
                raise AssertionError(f"oracle accepted mutation: {label}")
    print(
        "authoritative mechanics state bridge oracle regression: PASS "
        f"(2 deterministic positives, {len(mutations)} mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
