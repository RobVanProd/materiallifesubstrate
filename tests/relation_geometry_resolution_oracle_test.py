#!/usr/bin/env python3
"""Independent-oracle determinism and fail-closed mutation regression."""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable


def invoke(
    oracle: Path, raw: Path, force_bundle: Path, output: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(oracle),
            "--raw",
            str(raw),
            "--force-bundle",
            str(force_bundle),
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
        env={**dict(__import__("os").environ), "PYTHONDONTWRITEBYTECODE": "1"},
    )


def mutate_csv(
    path: Path, mutation: Callable[[list[dict[str, str]]], None]
) -> None:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fieldnames = list(reader.fieldnames or ())
        values = list(reader)
    mutation(values)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def change_direct_subtraction(values: list[dict[str, str]]) -> None:
    lookup = {row["evaluation_id"]: row for row in values}
    changed = 0
    for row in values:
        if (
            ".adjacency." in row["evaluation_id"]
            and row["evaluation_id"].endswith("cancellation_resistant_binary64")
            and row["relation_index"] == "0"
        ):
            control_id = row["evaluation_id"].replace(
                "cancellation_resistant_binary64", "frozen_binary64"
            )
            control = lookup[control_id]
            for field in (
                "current_length_bits", "extension_bits", "extension_low_bits",
                "length_order", "squared_difference_bits",
                "squared_difference_low_bits",
            ):
                row[field] = control[field]
            changed += 1
    if changed != 18:
        raise AssertionError("direct-subtraction mutation inventory changed")


def change_first_bit(field: str) -> Callable[[list[dict[str, str]]], None]:
    def mutate(values: list[dict[str, str]]) -> None:
        values[0][field] = str(int(values[0][field]) ^ 1)

    return mutate


def change_epsilon_clamp(values: list[dict[str, str]]) -> None:
    for row in values:
        if (
            ".collapse.-48.cancellation_resistant_binary64" in row["evaluation_id"]
            and row["relation_index"] == "0"
        ):
            row["direction_x_bits"] = "0"
            return
    raise AssertionError("epsilon-clamp target absent")


def change_orientation(values: list[dict[str, str]]) -> None:
    values[0]["first_id"], values[0]["second_id"] = (
        values[0]["second_id"], values[0]["first_id"]
    )


def change_condition_labels(values: list[dict[str, str]]) -> None:
    changed = 0
    for row in values:
        if row["probe"] == "collapse" and row["parameter"] in {
            "-32", "-36", "-40"
        }:
            row["condition_resolved"] = "true"
            row["condition_bits"] = "4607182418800017408"
            row["largest_singular_bits"] = "4607182418800017408"
            row["smallest_nonzero_singular_bits"] = "4607182418800017408"
            changed += 1
    if changed != 54:
        raise AssertionError("condition-label mutation inventory changed")


def add_hidden_repulsion(values: list[dict[str, str]]) -> None:
    for row in values:
        if ".collapse.0.cancellation_resistant_binary64" in row["evaluation_id"]:
            row["force_x_bits"] = "4607182418800017408"
            return
    raise AssertionError("hidden-repulsion target absent")


def add_persistent_low_word(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[0] += ",persistent_position_low_bits"
    for index in range(1, len(lines)):
        lines[index] += ",0"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--oracle",
        type=Path,
        default=root / "reference" / "relation_geometry_resolution_oracle.py",
    )
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--force-bundle", type=Path, required=True)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="mls-relation-geometry-mutations-") as temporary:
        directory = Path(temporary)
        raw = directory / "raw"
        shutil.copytree(arguments.raw, raw)
        first_output = directory / "positive-a" / "result.json"
        second_output = directory / "positive-b" / "result.json"
        first = invoke(arguments.oracle, raw, arguments.force_bundle, first_output)
        second = invoke(arguments.oracle, raw, arguments.force_bundle, second_output)
        if first.returncode != 0 or second.returncode != 0:
            raise AssertionError(
                f"positive oracle failed\n{first.stdout}\n{first.stderr}\n"
                f"{second.stdout}\n{second.stderr}"
            )
        if (
            first_output.read_bytes() != second_output.read_bytes()
            or first_output.with_suffix(".csv").read_bytes()
            != second_output.with_suffix(".csv").read_bytes()
        ):
            raise AssertionError("oracle twin output differs")

        mutations: tuple[
            tuple[str, str, Callable[[list[dict[str, str]]], None]], ...
        ] = (
            ("direct-norm-subtraction", "geometry_bits.csv", change_direct_subtraction),
            ("altered-h", "h_bits.csv", change_first_bit("frozen_bits")),
            (
                "changed-reference-coordinate",
                "reference_packets_bits.csv",
                change_first_bit("x_bits"),
            ),
            ("epsilon-clamping", "geometry_bits.csv", change_epsilon_clamp),
            ("wrong-relation-orientation", "relations_bits.csv", change_orientation),
            (
                "hidden-repulsion",
                "packet_forces_bits.csv",
                add_hidden_repulsion,
            ),
            (
                "intrinsic-failure-relabeled-pass",
                "evaluations.csv",
                change_condition_labels,
            ),
        )
        for label, name, mutation in mutations:
            target = raw / name
            original = target.read_bytes()
            mutate_csv(target, mutation)
            completed = invoke(
                arguments.oracle, raw, arguments.force_bundle,
                directory / f"mutation-{label}.json",
            )
            target.write_bytes(original)
            if completed.returncode == 0:
                raise AssertionError(f"oracle accepted mutation: {label}")

        target = raw / "current_packets_bits.csv"
        original = target.read_bytes()
        add_persistent_low_word(target)
        completed = invoke(
            arguments.oracle, raw, arguments.force_bundle,
            directory / "mutation-persistent-double-double.json",
        )
        target.write_bytes(original)
        if completed.returncode == 0:
            raise AssertionError("oracle accepted persistent double-double state")

    print(
        "relation geometry oracle regression: PASS "
        f"(2 deterministic positives, {len(mutations) + 1} mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
