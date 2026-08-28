#!/usr/bin/env python3
"""Positive and mutation regressions for the affine-advection bundle validator."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Sequence


def run_validator(validator: Path, bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(validator),
            "--bundle",
            str(bundle),
            "--smoke-provisional",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def mutate_csv(path: Path, mutation: Callable[[list[dict[str, str]]], None]) -> None:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = list(reader.fieldnames or ())
        rows = list(reader)
    mutation(rows)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def expect_rejection(
    validator: Path,
    source_bundle: Path,
    root: Path,
    name: str,
    mutation: Callable[[Path], None],
) -> None:
    target = root / name
    shutil.copytree(source_bundle, target)
    mutation(target)
    result = run_validator(validator, target)
    if result.returncode == 0:
        raise AssertionError(f"validator accepted mutation {name}\n{result.stdout}")
    if "AFFINE ADVECTION BUNDLE INVALID" not in result.stderr:
        raise AssertionError(
            f"mutation {name} failed without the validator rejection marker\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--validator", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_args(argv)
    source = arguments.bundle.resolve()
    validator = arguments.validator.resolve()
    positive = run_validator(validator, source)
    if positive.returncode != 0:
        raise AssertionError(
            f"unmodified smoke fixture did not validate\n"
            f"stdout:\n{positive.stdout}\nstderr:\n{positive.stderr}"
        )

    with tempfile.TemporaryDirectory(prefix="mls-affine-validator-") as temporary:
        root = Path(temporary)

        def wrong_applicability(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                rows[0]["static_representation_applicable"] = "true"
                # The corresponding values deliberately remain NA.
            mutate_csv(bundle / "core_sweep.csv", change)

        def delete_row(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                rows.pop()
            mutate_csv(bundle / "core_sweep.csv", change)

        def tamper_summary_decision(bundle: Path) -> None:
            path = bundle / "summary.json"
            summary = json.loads(path.read_text(encoding="utf-8"))
            summary["overall_recommendation"] = "promote Path E"
            path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

        def tamper_convergence_flag(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                rows[0]["pass"] = "false" if rows[0]["pass"] == "true" else "true"
            mutate_csv(bundle / "convergence.csv", change)

        expect_rejection(validator, source, root, "wrong-applicability-na", wrong_applicability)
        expect_rejection(validator, source, root, "deleted-row", delete_row)
        expect_rejection(validator, source, root, "summary-decision", tamper_summary_decision)
        expect_rejection(validator, source, root, "convergence-flag", tamper_convergence_flag)

    print("Affine-advection bundle validator regression: PASS (1 positive, 4 mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
