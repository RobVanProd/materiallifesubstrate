#!/usr/bin/env python3
"""Positive and mutation regressions for the moving-APIC-limit validator."""
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


INVALID_MARKER = "MOVING APIC LIMIT BUNDLE INVALID"


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
        fields = list(reader.fieldnames or ())
        rows = list(reader)
    mutation(rows)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def expect_rejection(
    validator: Path,
    source: Path,
    root: Path,
    name: str,
    mutation: Callable[[Path], None],
) -> None:
    target = root / name
    shutil.copytree(source, target)
    mutation(target)
    result = run_validator(validator, target)
    if result.returncode == 0:
        raise AssertionError(f"validator accepted mutation {name}\n{result.stdout}")
    if INVALID_MARKER not in result.stderr:
        raise AssertionError(
            f"mutation {name} lacked rejection marker\n"
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
    summary = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    mode = summary.get("mode")
    if mode not in {"smoke", "full"}:
        raise AssertionError(f"fixture has invalid mode {mode!r}")
    positive = run_validator(validator, source)
    if positive.returncode != 0:
        raise AssertionError(
            "unmodified fixture did not validate\n"
            f"stdout:\n{positive.stdout}\nstderr:\n{positive.stderr}"
        )

    mutations = 0
    with tempfile.TemporaryDirectory(prefix="mls-moving-apic-limit-validator-") as temporary:
        root = Path(temporary)

        def deleted_row(bundle: Path) -> None:
            mutate_csv(bundle / "co_refinement.csv", lambda rows: rows.pop())

        def tamper_ppc(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                rows[0]["particles_per_cell"] = str(int(rows[0]["particles_per_cell"]) + 1)
            mutate_csv(bundle / "particles_per_cell.csv", change)

        def tamper_mass(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                rows[0]["terminal_mass_quanta"] = "32767"
            mutate_csv(bundle / "co_refinement.csv", change)

        def tamper_cfl(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                rows[0]["cfl"] = "0.126"
            mutate_csv(bundle / "co_refinement.csv", change)

        def tamper_hard_applicability(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                rows[0]["applicable"] = (
                    "false" if rows[0]["applicable"] == "true" else "true"
                )
            mutate_csv(bundle / "hard_gates.csv", change)

        def tamper_prerequisite_hash(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                target = next(
                    row for row in rows if row["gate"] == "sealed_control_csv_sha256"
                )
                target["expected"] = "0" * 64
            mutate_csv(bundle / "prerequisites.csv", change)

        def tamper_decision(bundle: Path) -> None:
            path = bundle / "summary.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["decision"] = "promote_APIC"
            path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        common_mutations = (
            ("deleted-row", deleted_row),
            ("tampered-ppc", tamper_ppc),
            ("tampered-mass", tamper_mass),
            ("tampered-cfl", tamper_cfl),
            ("hard-applicability", tamper_hard_applicability),
            ("prerequisite-hash", tamper_prerequisite_hash),
            ("decision", tamper_decision),
        )
        for name, mutation in common_mutations:
            expect_rejection(validator, source, root, name, mutation)
            mutations += 1

        if mode == "full":
            def tamper_convergence_flag(bundle: Path) -> None:
                def change(rows: list[dict[str, str]]) -> None:
                    rows[0]["pass"] = "false" if rows[0]["pass"] == "true" else "true"
                mutate_csv(bundle / "convergence.csv", change)

            def tamper_convergence_failure_count(bundle: Path) -> None:
                def change(rows: list[dict[str, str]]) -> None:
                    rows[0]["failure_count"] = (
                        "1" if rows[0]["failure_count"] == "0" else "0"
                    )
                mutate_csv(bundle / "convergence.csv", change)

            def tamper_convergence_worst(bundle: Path) -> None:
                def change(rows: list[dict[str, str]]) -> None:
                    rows[0]["worst_value"] = str(float(rows[0]["worst_value"]) + 1.0)
                    rows[0]["worst_configuration"] = "level_99"
                mutate_csv(bundle / "convergence.csv", change)

            def synthesize_sealed_absent_observation(bundle: Path) -> None:
                def change(rows: list[dict[str, str]]) -> None:
                    target = next(
                        row for row in rows
                        if row["scope"] == "fixed_particle_control"
                        and row["gate"] == "nonfinite_or_missing_count"
                    )
                    target.update({
                        "applicable": "true",
                        "expected_configurations": "4",
                        "evaluated_configurations": "4",
                        "failure_count": "0",
                        "worst_value": "0",
                        "tolerance": "0",
                        "worst_configuration": "level_0",
                        "pass": "true",
                    })
                mutate_csv(bundle / "hard_gates.csv", change)

            def tamper_sealed_byte(bundle: Path) -> None:
                path = bundle / "fixed_particle_control.csv"
                data = bytearray(path.read_bytes())
                if not data:
                    raise AssertionError("sealed fixture unexpectedly empty")
                data[-1] ^= 1
                path.write_bytes(data)

            for name, mutation in (
                ("convergence-flag", tamper_convergence_flag),
                ("convergence-failure-count", tamper_convergence_failure_count),
                ("convergence-worst", tamper_convergence_worst),
                ("sealed-absent-observation", synthesize_sealed_absent_observation),
                ("sealed-control-byte", tamper_sealed_byte),
            ):
                expect_rejection(validator, source, root, name, mutation)
                mutations += 1

    conditional = "full convergence+sealed-byte exercised" if mode == "full" else (
        "smoke provisional: convergence+sealed-byte deferred to required full-bundle run"
    )
    print(
        "Moving APIC limit bundle validator regression: PASS "
        f"(1 positive, {mutations} mutations; {conditional})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
