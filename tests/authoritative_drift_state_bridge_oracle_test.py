#!/usr/bin/env python3
"""Positive and mutation regression for the independent drift oracle."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable


Mutator = Callable[[Path], None]


def rewrite(path: Path, change: Callable[[list[dict[str, str]]], None]) -> None:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames
        assert fieldnames is not None
        rows = list(reader)
    change(rows)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def first_row(filename: str, predicate: Callable[[dict[str, str]], bool], field: str, value: str) -> Mutator:
    def mutate(raw: Path) -> None:
        def change(rows: list[dict[str, str]]) -> None:
            row = next(item for item in rows if predicate(item))
            row[field] = value

        rewrite(raw / filename, change)

    return mutate


def metadata_value(key: str, value: str) -> Mutator:
    return first_row("metadata.csv", lambda row: row["key"] == key, "value", value)


def run_oracle(source: Path, raw: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(source / "reference" / "authoritative_drift_state_bridge_oracle.py"),
         "--raw", str(raw), "--output", str(output)],
        cwd=source,
        check=False,
        capture_output=True,
        text=True,
        timeout=1200,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    arguments = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    raw = arguments.raw.resolve()

    mutations: list[tuple[str, Mutator]] = [
        (
            "Cartesian displacement disguised as directional",
            first_row(
                "evaluations.csv",
                lambda row: row["path"] == "primitive_directional" and row["packet_id"] == "3"
                and row["refinement"] == "128" and row["horizon"] == "32"
                and row["subdivisions"] == "32",
                "applied_dx",
                "1",
            ),
        ),
        (
            "wrong gcd",
            first_row("evaluations.csv", lambda row: row["gcd"] != "0", "gcd", "1"),
        ),
        (
            "half away instead of nearest even",
            first_row(
                "rounding_controls.csv",
                lambda row: row["numerator"] == "1" and row["denominator"] == "2",
                "nearest_even",
                "1",
            ),
        ),
        (
            "changed mass",
            first_row("inventory.csv", lambda row: row["packet_id"] == "3", "base_mass", "42"),
        ),
        (
            "changed momentum",
            first_row("inventory.csv", lambda row: row["packet_id"] == "4", "base_px", "15"),
        ),
        (
            "changed unit scale",
            first_row("units.csv", lambda row: row["refinement"] == "128", "Lq", "1/1"),
        ),
        (
            "hidden kinetic mutation",
            first_row("evaluations.csv", lambda row: row["kinetic_before"] != "0", "kinetic_after", "0"),
        ),
        (
            "omitted Cartesian torque",
            first_row(
                "evaluations.csv",
                lambda row: row["path"] == "cartesian_nearest" and row["delta_L_x"] != "0",
                "delta_L_x",
                "0",
            ),
        ),
        (
            "false equal velocity result",
            first_row("equal_velocity.csv", lambda row: row["equal"] == "true", "equal", "false"),
        ),
        (
            "overflow relabeled accepted",
            first_row("overflow_controls.csv", lambda row: row["case"] == "adjacent_overflow", "accepted", "true"),
        ),
        (
            "crossing relabeled admissible",
            first_row("domain_chords.csv", lambda row: row["id"] == "2", "admissible", "true"),
        ),
        (
            "coarser false selection",
            first_row("candidate_summary.csv", lambda row: row["refinement"] == "64", "passes", "true"),
        ),
        (
            "changed inherited impulse",
            first_row("impulse_regression.csv", lambda row: True, "applied_multiple", "0"),
        ),
        (
            "wrong accepted parent",
            metadata_value("accepted_parent_sha", "0" * 40),
        ),
    ]

    with tempfile.TemporaryDirectory(prefix="mls-drift-oracle-test-") as temporary:
        root = Path(temporary)
        first = run_oracle(source, raw, root / "positive-a.json")
        second = run_oracle(source, raw, root / "positive-b.json")
        if first.returncode != 0 or second.returncode != 0:
            print(first.stdout + first.stderr + second.stdout + second.stderr, file=sys.stderr)
            return 1
        if (root / "positive-a.json").read_bytes() != (root / "positive-b.json").read_bytes():
            print("drift oracle positive outputs differ", file=sys.stderr)
            return 1
        if (root / "positive-a.csv").read_bytes() != (root / "positive-b.csv").read_bytes():
            print("drift oracle positive CSV outputs differ", file=sys.stderr)
            return 1

        for index, (name, mutate) in enumerate(mutations):
            candidate = root / f"mutation-{index}"
            shutil.copytree(raw, candidate)
            mutate(candidate)
            completed = run_oracle(source, candidate, root / f"mutation-{index}.json")
            if completed.returncode == 0:
                print(f"mutation unexpectedly passed: {name}", file=sys.stderr)
                return 1

    print(
        "authoritative drift state bridge oracle regression: PASS "
        f"(2 deterministic positives, {len(mutations)} mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
