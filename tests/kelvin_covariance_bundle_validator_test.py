#!/usr/bin/env python3
"""Mutation regression for the Kelvin evidence validator."""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile


def run(
    validator: pathlib.Path,
    bundle: pathlib.Path,
    expected_source_branch: str,
    expect_success: bool,
) -> None:
    completed = subprocess.run(
        [
            sys.executable, str(validator), "--bundle", str(bundle),
            "--allow-dirty", "--expected-source-branch", expected_source_branch,
        ],
        text=True, capture_output=True, check=False)
    if (completed.returncode == 0) != expect_success:
        raise RuntimeError(
            f"unexpected validator outcome {completed.returncode}:\n"
            f"{completed.stdout}\n{completed.stderr}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validator", type=pathlib.Path, required=True)
    parser.add_argument("--bundle", type=pathlib.Path, required=True)
    parser.add_argument(
        "--expected-source-branch", default="kelvin-covariance-audit"
    )
    args = parser.parse_args()
    run(args.validator, args.bundle, args.expected_source_branch, True)
    with tempfile.TemporaryDirectory(prefix="mls-kelvin-validator-") as temp:
        root = pathlib.Path(temp)
        mutations = []
        for name in ("decision", "raw", "checkpoint", "inventory", "oracle"):
            target = root / name
            shutil.copytree(args.bundle, target)
            mutations.append((name, target))

        summary_path = mutations[0][1] / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["decision"] = "INCONCLUSIVE"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

        csv_path = mutations[1][1] / "covariance.csv"
        with csv_path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
            fields = stream.seek(0) or list(rows[0])
        rows[0]["raw_operator_residual"] = "0x1p+0"
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

        checkpoint = mutations[2][1] / "checkpoints" / "cube8.bin"
        payload = bytearray(checkpoint.read_bytes())
        payload[-1] ^= 1
        checkpoint.write_bytes(payload)

        (mutations[3][1] / "unexpected.txt").write_text("x", encoding="utf-8")

        summary_path = mutations[4][1] / "summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["exact_oracle_result_sha256"] = "0" * 64
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

        for name, target in mutations:
            try:
                run(args.validator, target, args.expected_source_branch, False)
            except RuntimeError as error:
                raise RuntimeError(f"mutation {name}: {error}") from error
    print("kelvin covariance bundle validator regression: PASS (5 mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
