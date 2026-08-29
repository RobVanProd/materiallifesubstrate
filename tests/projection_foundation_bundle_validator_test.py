#!/usr/bin/env python3
"""Positive and semantic-mutation regressions for the projection validator.

Every semantic mutation refreshes the bundle manifest.  A rejection therefore
demonstrates that the independent validator reconstructed the evidence rather
than merely detecting a stale file digest.  The final mutation deliberately
corrupts the manifest to exercise the integrity gate itself.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Sequence


INVALID_MARKER = "PROJECTION FOUNDATION BUNDLE INVALID"
MANIFEST_SCHEMA = "mls.projection-foundation.manifest.v1"
MANIFESTED_FILES = (
    "checkpoint.csv",
    "convergence.csv",
    "exact_angular_control.csv",
    "hard_gates.csv",
    "main_raw.csv",
    "order_to_full.csv",
    "orientation_sensitivity.csv",
    "phase_sensitivity.csv",
    "ppc_raw.csv",
    "solver_failures.csv",
    "summary.json",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def manifest_payload(hashes: dict[str, str]) -> bytes:
    """Reproduce the producer's pre-hash payload byte for byte."""
    names = sorted(hashes)
    lines = [
        "{",
        '  "algorithm": "SHA-256",',
        '  "files": {',
    ]
    for index, name in enumerate(names):
        comma = "," if index + 1 != len(names) else ""
        lines.append(f"    {json.dumps(name)}: {json.dumps(hashes[name])}{comma}")
    lines.extend(
        (
            "  },",
            f'  "schema": {json.dumps(MANIFEST_SCHEMA)}',
            "}",
        )
    )
    return "\n".join(lines).encode("utf-8")


def expected_manifest(bundle: Path) -> tuple[dict[str, str], str]:
    hashes = {
        name: sha256_bytes((bundle / name).read_bytes()) for name in MANIFESTED_FILES
    }
    return hashes, sha256_bytes(manifest_payload(hashes))


def refresh_manifest(bundle: Path) -> None:
    """Refresh integrity metadata after an intentional semantic mutation."""
    hashes, pre_hash = expected_manifest(bundle)
    value = {
        "algorithm": "SHA-256",
        "files": hashes,
        "pre_hash_sha256": pre_hash,
        "schema": MANIFEST_SCHEMA,
    }
    # The producer emits sorted file keys and this exact two-space layout.
    (bundle / "manifest.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def assert_manifest_current(bundle: Path) -> None:
    value = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    hashes, pre_hash = expected_manifest(bundle)
    if value.get("algorithm") != "SHA-256":
        raise AssertionError("fixture manifest has an unexpected algorithm")
    if value.get("schema") != MANIFEST_SCHEMA:
        raise AssertionError("fixture manifest has an unexpected schema")
    if value.get("files") != hashes:
        raise AssertionError("fixture manifest file hashes are stale")
    if value.get("pre_hash_sha256") != pre_hash:
        raise AssertionError("fixture manifest pre-hash is stale")


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
    if not fields:
        raise AssertionError(f"mutation fixture has no CSV header: {path}")
    mutation(rows)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def flip_bool(value: str) -> str:
    if value == "true":
        return "false"
    if value == "false":
        return "true"
    raise AssertionError(f"expected canonical boolean, got {value!r}")


def expect_rejection(
    validator: Path,
    source: Path,
    root: Path,
    name: str,
    mutation: Callable[[Path], None],
    *,
    refresh: bool = True,
) -> None:
    target = root / name
    shutil.copytree(source, target)
    mutation(target)
    if refresh:
        refresh_manifest(target)
        # Establish that semantic tests cannot pass merely through stale hashes.
        assert_manifest_current(target)
    result = run_validator(validator, target)
    if result.returncode == 0:
        raise AssertionError(
            f"validator accepted mutation {name}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    if INVALID_MARKER not in result.stderr:
        raise AssertionError(
            f"mutation {name} lacked the validator rejection marker\n"
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
    if not validator.is_file():
        raise AssertionError(f"validator does not exist: {validator}")

    summary = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    if summary.get("mode") != "smoke":
        raise AssertionError("this regression requires the registered smoke fixture")
    assert_manifest_current(source)
    positive = run_validator(validator, source)
    if positive.returncode != 0:
        raise AssertionError(
            "unmodified smoke fixture did not validate\n"
            f"stdout:\n{positive.stdout}\nstderr:\n{positive.stderr}"
        )

    mutations = 0
    with tempfile.TemporaryDirectory(prefix="mls-projection-validator-") as temporary:
        root = Path(temporary)

        def missing_registered_row(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                if not rows:
                    raise AssertionError("main_raw fixture unexpectedly empty")
                rows.pop()

            mutate_csv(bundle / "main_raw.csv", change)

        def duplicate_primary_key(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                if not rows:
                    raise AssertionError("main_raw fixture unexpectedly empty")
                rows.append(dict(rows[0]))

            mutate_csv(bundle / "main_raw.csv", change)

        def drift_registered_configuration(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                if not rows:
                    raise AssertionError("main_raw fixture unexpectedly empty")
                rows[0]["h_m"] = "5.00976562500000000e-01"

            mutate_csv(bundle / "main_raw.csv", change)

        def flip_hard_gate(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                if not rows:
                    raise AssertionError("hard_gates fixture unexpectedly empty")
                rows[0]["pass"] = flip_bool(rows[0]["pass"])

            mutate_csv(bundle / "hard_gates.csv", change)

        def break_identity_na_contract(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                if not rows:
                    raise AssertionError("main_raw fixture unexpectedly empty")
                rows[0]["id_error_count"] = "1"
                if rows[0]["material_velocity_error"] == "NA":
                    raise AssertionError("positive fixture unexpectedly has NA metric")

            mutate_csv(bundle / "main_raw.csv", change)

        def flip_order_decision(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                if not rows:
                    raise AssertionError("order_to_full fixture unexpectedly empty")
                rows[0]["pass"] = flip_bool(rows[0]["pass"])

            mutate_csv(bundle / "order_to_full.csv", change)

        def mismatch_solver_status(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                if not rows:
                    raise AssertionError("solver_failures fixture unexpectedly empty")
                rows[0]["status"] = (
                    "iteration_limit"
                    if rows[0]["status"] != "iteration_limit"
                    else "solved"
                )

            mutate_csv(bundle / "solver_failures.csv", change)

        def flip_checkpoint_decision(bundle: Path) -> None:
            def change(rows: list[dict[str, str]]) -> None:
                if not rows:
                    raise AssertionError("checkpoint fixture unexpectedly empty")
                rows[0]["pass"] = flip_bool(rows[0]["pass"])

            mutate_csv(bundle / "checkpoint.csv", change)

        def corrupt_manifest(bundle: Path) -> None:
            path = bundle / "manifest.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["pre_hash_sha256"] = "0" * 64
            path.write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

        for name, mutation in (
            ("missing-registered-row", missing_registered_row),
            ("duplicate-primary-key", duplicate_primary_key),
            ("registered-config-drift", drift_registered_configuration),
            ("hard-gate-flip", flip_hard_gate),
            ("identity-na-contract", break_identity_na_contract),
            ("order-decision-flip", flip_order_decision),
            ("solver-status-mismatch", mismatch_solver_status),
            ("checkpoint-decision-flip", flip_checkpoint_decision),
        ):
            expect_rejection(validator, source, root, name, mutation)
            mutations += 1

        expect_rejection(
            validator,
            source,
            root,
            "manifest-corruption",
            corrupt_manifest,
            refresh=False,
        )
        mutations += 1

    print(
        "Projection foundation bundle validator regression: PASS "
        f"(1 positive, {mutations} mutations; semantic mutations re-manifested)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
