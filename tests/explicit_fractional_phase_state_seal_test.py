#!/usr/bin/env python3
"""Outer-seal positive and mutation regression for fractional phase evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


GROUPS = (
    "raw-a",
    "raw-b",
    "oracle",
    "parent-corefinement",
    "source",
    "receipts",
    "docs",
)


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
    for name in GROUPS:
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
        default=root / "tools" / "seal_explicit_fractional_phase_state_evidence.py",
    )
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="mls-fractional-seal-") as temporary:
        bundle = fixture(Path(temporary))
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
            raise AssertionError(f"seal create failed\n{created.stdout}\n{created.stderr}")
        first = invoke(arguments.tool, "verify", "--bundle", str(bundle))
        second = invoke(arguments.tool, "verify", "--bundle", str(bundle))
        if first.returncode != 0 or first.stdout != second.stdout:
            raise AssertionError("seal positive verification differs")
        seal = bundle / "outer-seal.json"
        original_seal = seal.read_bytes()
        payload = bundle / "raw-a" / "payload.txt"
        original_payload = payload.read_bytes()
        payload.write_bytes(original_payload + b"mutation")
        if invoke(arguments.tool, "verify", "--bundle", str(bundle)).returncode == 0:
            raise AssertionError("seal accepted payload mutation")
        payload.write_bytes(original_payload)
        value = json.loads(original_seal)
        value["decision"] = "retain_explicit_fractional_phase_state_for_research"
        seal.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if invoke(arguments.tool, "verify", "--bundle", str(bundle)).returncode == 0:
            raise AssertionError("seal accepted scientific-field mutation")
        seal.write_bytes(original_seal)
        (bundle / "extra.txt").write_text("extra\n", encoding="utf-8")
        if invoke(arguments.tool, "verify", "--bundle", str(bundle)).returncode == 0:
            raise AssertionError("seal accepted extra payload")
    print("explicit fractional phase-state outer-seal regression: PASS (2 positives, 3 mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
