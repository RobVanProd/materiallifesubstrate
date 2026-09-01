#!/usr/bin/env python3
"""Outer-seal deterministic positive and fail-closed mutation regression."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def invoke(tool: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(tool), *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def fixture(root: Path) -> Path:
    bundle = root / "bundle"
    for name in (
        "raw-a", "raw-b", "oracle", "parent-force-producer", "source",
        "receipts", "docs",
    ):
        directory = bundle / name
        directory.mkdir(parents=True)
        (directory / "payload.txt").write_text(f"{name}\n", encoding="utf-8")
    return bundle


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tool",
        type=Path,
        default=root / "tools" / "seal_relation_geometry_resolution_evidence.py",
    )
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="mls-relation-geometry-seal-") as temporary:
        directory = Path(temporary)
        bundle = fixture(directory)
        created = invoke(
            arguments.tool,
            "create",
            "--bundle",
            str(bundle),
            "--source-sha",
            "0123456789abcdef0123456789abcdef01234567",
            "--ci-run-id",
            "1",
        )
        if created.returncode != 0:
            raise AssertionError(f"seal creation failed\n{created.stdout}\n{created.stderr}")
        first = invoke(arguments.tool, "verify", "--bundle", str(bundle))
        second = invoke(arguments.tool, "verify", "--bundle", str(bundle))
        if first.returncode != 0 or first.stdout != second.stdout:
            raise AssertionError("seal positive verification is not deterministic")
        seal_path = bundle / "outer-seal.json"
        original_seal = seal_path.read_bytes()
        payload = bundle / "raw-a" / "payload.txt"
        original_payload = payload.read_bytes()
        payload.write_bytes(original_payload + b"mutation")
        if invoke(arguments.tool, "verify", "--bundle", str(bundle)).returncode == 0:
            raise AssertionError("seal accepted a payload mutation")
        payload.write_bytes(original_payload)
        value = json.loads(original_seal)
        value["rho_min_exponent"] = -28
        seal_path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if invoke(arguments.tool, "verify", "--bundle", str(bundle)).returncode == 0:
            raise AssertionError("seal accepted a scientific-field mutation")
        seal_path.write_bytes(original_seal)
        (bundle / "extra.txt").write_text("extra\n", encoding="utf-8")
        if invoke(arguments.tool, "verify", "--bundle", str(bundle)).returncode == 0:
            raise AssertionError("seal accepted an extra payload")
    print("relation geometry outer-seal regression: PASS (2 positives, 3 mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
