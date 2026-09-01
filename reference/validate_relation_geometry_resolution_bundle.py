#!/usr/bin/env python3
"""Fresh validator for sealed Relation Geometry Resolution evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def invoke(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=1200,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def require_success(completed: subprocess.CompletedProcess[str], label: str) -> None:
    if completed.returncode != 0:
        raise RuntimeError(
            f"{label} failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


def compare_directories(first: Path, second: Path) -> None:
    first_files = {
        path.relative_to(first).as_posix(): path
        for path in first.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second).as_posix(): path
        for path in second.rglob("*")
        if path.is_file()
    }
    if set(first_files) != set(second_files):
        raise RuntimeError("raw twin inventories differ")
    for name, first_path in first_files.items():
        if first_path.read_bytes() != second_files[name].read_bytes():
            raise RuntimeError(f"raw twin file differs: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run-mutations", action="store_true")
    arguments = parser.parse_args()
    bundle = arguments.bundle.resolve()
    source = arguments.source.resolve()
    try:
        seal = invoke(
            [
                sys.executable,
                str(source / "tools" / "seal_relation_geometry_resolution_evidence.py"),
                "verify",
                "--bundle",
                str(bundle),
            ],
            source,
        )
        require_success(seal, "outer seal")
        compare_directories(bundle / "raw-a", bundle / "raw-b")
        with tempfile.TemporaryDirectory(prefix="mls-relation-geometry-verify-") as temporary:
            output = Path(temporary) / "oracle-summary.json"
            oracle = invoke(
                [
                    sys.executable,
                    str(source / "reference" / "relation_geometry_resolution_oracle.py"),
                    "--raw",
                    str(bundle / "raw-a"),
                    "--force-bundle",
                    str(bundle / "parent-force-producer"),
                    "--output",
                    str(output),
                ],
                source,
            )
            require_success(oracle, "420-digit oracle")
            canonical_json = bundle / "oracle" / "oracle-summary.json"
            canonical_csv = bundle / "oracle" / "oracle-summary.csv"
            if output.read_bytes() != canonical_json.read_bytes():
                raise RuntimeError("fresh oracle JSON differs from sealed result")
            if output.with_suffix(".csv").read_bytes() != canonical_csv.read_bytes():
                raise RuntimeError("fresh oracle CSV differs from sealed result")
            summary = json.loads(output.read_text(encoding="utf-8"))
            if (
                summary.get("decision")
                != "retain_relation_geometry_with_explicit_safe_domain_for_research"
                or summary.get("selected_geometry_path")
                != "cancellation_resistant_binary64"
                or summary.get("safe_domains", {})
                .get("cancellation_resistant_binary64", {})
                .get("rho_min_exponent")
                != -24
                or summary.get("intrinsic_collapse_domain_boundary_confirmed") is not True
                or summary.get("promotion") != "NO_PROMOTION"
            ):
                raise RuntimeError("fresh oracle scientific disposition differs")
        if arguments.run_mutations:
            mutations = invoke(
                [
                    sys.executable,
                    str(source / "tests" / "relation_geometry_resolution_oracle_test.py"),
                    "--raw",
                    str(bundle / "raw-a"),
                    "--force-bundle",
                    str(bundle / "parent-force-producer"),
                ],
                source,
            )
            require_success(mutations, "oracle mutation regression")
        seal_value = json.loads((bundle / "outer-seal.json").read_text(encoding="utf-8"))
        print(
            "RELATION GEOMETRY EVIDENCE VALID: "
            f"source={seal_value['source_sha']} "
            f"files={len(seal_value['payload'])} "
            f"prehash={seal_value['outer_pre_hash']} "
            "rho_min=2^-24 intrinsic_boundary=true NO_PROMOTION"
        )
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"RELATION GEOMETRY EVIDENCE INVALID: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
