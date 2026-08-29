#!/usr/bin/env python3
"""Positive and re-manifested mutation tests for the nullspace validator."""

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


MANIFEST_SCHEMA = "mls.projection-exactness-nullspace.manifest.v1"
CSV_FILES = (
    "systems.csv", "particles.csv", "nodes.csv", "stencils.csv", "matrix.csv",
    "rhs.csv", "witness.csv", "solve_diagnostics.csv", "high_precision.csv",
    "nullspace_modes.csv", "nullspace_metrics.csv",
)
FILES = (*CSV_FILES, "summary.json")
RAW_FILES = ("particles.csv", "nodes.csv", "stencils.csv", "matrix.csv", "rhs.csv")
INVALID = "PROJECTION EXACTNESS NULLSPACE BUNDLE INVALID"


def manifest_payload(hashes: dict[str, str]) -> bytes:
    lines = ["{", '  "algorithm": "SHA-256",', '  "files": {']
    names = sorted(hashes)
    for index, name in enumerate(names):
        comma = "," if index + 1 < len(names) else ""
        lines.append(f"    {json.dumps(name)}: {json.dumps(hashes[name])}{comma}")
    lines.extend(("  },", f'  "schema": {json.dumps(MANIFEST_SCHEMA)}', "}"))
    return "\n".join(lines).encode()


def refresh_manifest(bundle: Path) -> None:
    hashes = {name: hashlib.sha256((bundle / name).read_bytes()).hexdigest() for name in FILES}
    value = {
        "algorithm": "SHA-256", "files": hashes, "schema": MANIFEST_SCHEMA,
        "pre_hash_sha256": hashlib.sha256(manifest_payload(hashes)).hexdigest(),
    }
    (bundle / "manifest.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or ()), list(reader)


def write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def mutate_row(bundle: Path, name: str, change: Callable[[dict[str, str]], None]) -> None:
    fields, rows = read_rows(bundle / name)
    if not rows:
        raise AssertionError(f"empty mutation table {name}")
    change(rows[0])
    write_rows(bundle / name, fields, rows)


def refresh_assembly_digest(bundle: Path, system_id: str) -> None:
    digest = hashlib.sha256()
    digest.update(b"MLS-PROJECTION-EXACTNESS-ASSEMBLY-v1\n")
    for name in RAW_FILES:
        fields, rows = read_rows(bundle / name)
        for row in rows:
            if row["system_id"] != system_id:
                continue
            digest.update(name.encode("ascii"))
            for field in fields:
                digest.update(b"\0")
                digest.update(row[field].encode())
            digest.update(b"\n")
    fields, rows = read_rows(bundle / "systems.csv")
    for row in rows:
        if row["system_id"] == system_id:
            row["assembly_payload_sha256"] = digest.hexdigest()
    write_rows(bundle / "systems.csv", fields, rows)


def run_validator(validator: Path, bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(validator), "--bundle", str(bundle), "--oracle-fixture"],
        check=False, capture_output=True, text=True, encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--oracle", type=Path, default=root / "reference/projection_exactness_nullspace_oracle.py")
    parser.add_argument("--validator", type=Path, default=root / "reference/validate_projection_exactness_nullspace_bundle.py")
    args = parser.parse_args(argv)
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="mls-nullspace-validator-") as temporary:
        base = Path(temporary) / "base"
        subprocess.run([sys.executable, str(args.oracle), "--write-fixture", str(base)], check=True, capture_output=True, text=True)
        positive = run_validator(args.validator, base)
        if positive.returncode != 0:
            raise AssertionError(f"positive fixture rejected\n{positive.stdout}\n{positive.stderr}")

        def reject(name: str, mutation: Callable[[Path], None], *, refresh: bool = True) -> None:
            nonlocal mutations
            target = Path(temporary) / name
            shutil.copytree(base, target)
            mutation(target)
            if refresh:
                refresh_manifest(target)
            result = run_validator(args.validator, target)
            if result.returncode == 0 or INVALID not in result.stderr:
                raise AssertionError(f"mutation {name} accepted\n{result.stdout}\n{result.stderr}")
            mutations += 1

        def matrix_semantic(bundle: Path) -> None:
            fields, rows = read_rows(bundle / "matrix.csv")
            rows[0]["value_kg"] = (float.fromhex(rows[0]["value_kg"]) * 1.25).hex()
            sid = rows[0]["system_id"]
            write_rows(bundle / "matrix.csv", fields, rows)
            refresh_assembly_digest(bundle, sid)

        reject("matrix-semantic", matrix_semantic)
        reject("rhs-semantic", lambda b: mutate_row(b, "rhs.csv", lambda r: r.__setitem__("value_kg_m_per_s", (float.fromhex(r["value_kg_m_per_s"]) + 0.25).hex())))
        reject("witness-pass", lambda b: mutate_row(b, "witness.csv", lambda r: r.__setitem__("pass", "false")))
        reject("solve-forward", lambda b: mutate_row(b, "solve_diagnostics.csv", lambda r: r.__setitem__("normalized_forward_error", "1e0")))
        reject("hp-promotion", lambda b: mutate_row(b, "high_precision.csv", lambda r: r.__setitem__("promotion_eligible", "true")))
        reject("null-mode", lambda b: mutate_row(b, "nullspace_modes.csv", lambda r: r.__setitem__("z_value_m_per_s", "0x1.8p+0")))
        reject("null-visible", lambda b: mutate_row(b, "nullspace_metrics.csv", lambda r: r.__setitem__("gradient_visible", "false")))

        def summary_decision(bundle: Path) -> None:
            value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
            value["decision"] = "stop_inconclusive_rank_or_solver_diagnosis"
            (bundle / "summary.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        reject("summary-decision", summary_decision)
        reject("checkpoint-hash", lambda b: mutate_row(b, "systems.csv", lambda r: r.__setitem__("input_checkpoint_sha256_after", "0" * 64)))

        def corrupt_manifest(bundle: Path) -> None:
            value = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
            value["pre_hash_sha256"] = "0" * 64
            (bundle / "manifest.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        reject("manifest-corrupt", corrupt_manifest, refresh=False)

    print(f"Projection exactness/nullspace validator regression: PASS (1 positive, {mutations} mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
