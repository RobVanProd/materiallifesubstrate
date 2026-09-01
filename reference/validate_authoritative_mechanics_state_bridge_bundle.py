#!/usr/bin/env python3
"""Fresh validator for sealed Authoritative Mechanics State Bridge evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def invoke(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=cwd, check=False, capture_output=True, text=True,
        timeout=1200,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def require_success(completed: subprocess.CompletedProcess[str], label: str) -> None:
    if completed.returncode != 0:
        raise RuntimeError(
            f"{label} failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


def compare_directories(first: Path, second: Path) -> None:
    first_files = {path.relative_to(first).as_posix(): path for path in first.rglob("*") if path.is_file()}
    second_files = {path.relative_to(second).as_posix(): path for path in second.rglob("*") if path.is_file()}
    if set(first_files) != set(second_files):
        raise RuntimeError("raw twin inventories differ")
    for name, first_path in first_files.items():
        if first_path.read_bytes() != second_files[name].read_bytes():
            raise RuntimeError(f"raw twin differs: {name}")


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
            [sys.executable, str(source / "tools" / "seal_authoritative_mechanics_state_bridge_evidence.py"),
             "verify", "--bundle", str(bundle)], source,
        )
        require_success(seal, "outer seal")
        compare_directories(bundle / "raw-a", bundle / "raw-b")
        with tempfile.TemporaryDirectory(prefix="mls-mechanics-bridge-verify-") as temporary:
            output = Path(temporary) / "oracle-summary.json"
            oracle = invoke(
                [sys.executable,
                 str(source / "reference" / "authoritative_mechanics_state_bridge_oracle.py"),
                 "--raw", str(bundle / "raw-a"), "--output", str(output)], source,
            )
            require_success(oracle, "exact-rational oracle")
            if output.read_bytes() != (bundle / "oracle" / "oracle-summary.json").read_bytes():
                raise RuntimeError("fresh oracle JSON differs")
            if output.with_suffix(".csv").read_bytes() != (bundle / "oracle" / "oracle-summary.csv").read_bytes():
                raise RuntimeError("fresh oracle CSV differs")
            summary = json.loads(output.read_text(encoding="utf-8"))
            if (
                summary.get("decision") != "retain_direct_quantized_mechanics_bridge_for_research"
                or summary.get("selected_refinement") != 16
                or summary.get("unit_contract_consistent") is not True
                or summary.get("kinetic_energy_floor_converges") is not True
                or summary.get("promotion") != "NO_PROMOTION"
            ):
                raise RuntimeError("fresh scientific disposition differs")
        if arguments.run_mutations:
            mutations = invoke(
                [sys.executable,
                 str(source / "tests" / "authoritative_mechanics_state_bridge_oracle_test.py"),
                 "--raw", str(bundle / "raw-a")], source,
            )
            require_success(mutations, "oracle mutation regression")
        seal_value = json.loads((bundle / "outer-seal.json").read_text(encoding="utf-8"))
        print(
            "AUTHORITATIVE MECHANICS STATE BRIDGE EVIDENCE VALID: "
            f"source={seal_value['source_sha']} files={len(seal_value['payload'])} "
            f"prehash={seal_value['outer_pre_hash']} R=16 NO_PROMOTION"
        )
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"AUTHORITATIVE MECHANICS STATE BRIDGE EVIDENCE INVALID: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
