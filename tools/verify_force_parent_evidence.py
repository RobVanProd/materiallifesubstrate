#!/usr/bin/env python3
"""Verify the immutable Constitutive Expressivity input to the force lab.

This is deliberately narrower than the constitutive numerical validator.  It
checks the accepted closed bundle byte inventory, its exact public commitments,
the bounded configuration set, and the decision/scope needed by the force lab.
It never edits or regenerates parent evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_PRE_HASH = (
    "18b1af6837f2c67204094498eedd2a8d8eabaf315ebae1d58c4b2073b778973f"
)
EXPECTED_SOURCE_SHA = "2de8843faf76a75d16b3a3012897e719291c52cf"
EXPECTED_DECISION = "retain_local_collective_relational_energy_for_research"
EXPECTED_TABLES = {
    "configurations.csv":
        "45d162381ec723dd9ce744f2cc23c4d21435a52b7c7e60a182073ee19a08d60e",
    "packets.csv":
        "843c9cb22c0b55e07c207135125a8334b0dd170a0f708aa1fb50f34d4c5d7363",
    "relations.csv":
        "0b2e21dcbf26454af316bec9323627aa1488ebc7aa1f14c006bfb41a231e0e6f",
}
EXPECTED_FIXTURE_TABLES = {
    "configurations.csv":
        "cbae18e3b2c356e2898d1410f37fb90692d889f28438cfb5524753c87f1db2b7",
    "packets.csv":
        "dfd22994678333125b90f658d5b228c09f45e4564f52e02d6f38a3b2f3c924f7",
    "relations.csv":
        "14afdb0ac5822294a5d5437b3e622dffdc9f886dda395d0bfef5ae9b13c73093",
}
EXPECTED_CONFIGURATIONS = {
    "exact.tetrahedron_k4": "eligible_generic",
    "exact.octahedron_graph": "eligible_generic",
    "base.sc3.r180.original": "eligible_generic",
    "base.bcc35.r180.original": "eligible_generic",
    "base.jitter27.r180.original": "eligible_generic",
    "base.free_face.r180.original": "eligible_generic",
    "base.sc3_deletion.delete25.original": "eligible_generic",
    "exact.tetrahedron_k4_minus_edge": "intentionally_floppy",
}


class ParentEvidenceError(RuntimeError):
    """Fail-closed parent verification error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ParentEvidenceError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ParentEvidenceError(f"invalid JSON {path}: {error}") from error
    require(isinstance(value, dict), f"{path.name} is not an object")
    return value


def verify(root: Path) -> dict[str, str]:
    root = root.resolve()
    require(root.is_dir(), "parent bundle directory is missing")
    manifest = read_json(root / "manifest.json")
    require(
        manifest.get("schema") == "mls.constitutive-expressivity.manifest.v1",
        "parent manifest schema mismatch",
    )
    require(
        manifest.get("pre_hash_sha256") == EXPECTED_PRE_HASH,
        "parent manifest pre-hash mismatch",
    )
    files = manifest.get("file_sha256")
    require(isinstance(files, dict), "parent manifest file map missing")
    require(
        all(isinstance(name, str) and isinstance(value, str)
            for name, value in files.items()),
        "parent manifest file map malformed",
    )
    observed = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*") if path.is_file()
    }
    require(observed == set(files) | {"manifest.json"},
            "parent closed file inventory mismatch")
    for relative, expected in sorted(files.items()):
        require(sha256(root / relative) == expected,
                f"parent payload hash mismatch: {relative}")
    for relative, expected in EXPECTED_TABLES.items():
        require(files.get(relative) == expected,
                f"selected parent commitment mismatch: {relative}")

    provenance = read_json(root / "provenance.json")
    require(provenance.get("source_sha") == EXPECTED_SOURCE_SHA,
            "accepted parent source SHA mismatch")
    require(provenance.get("source_branch") == "constitutive-expressivity-lab",
            "accepted parent branch mismatch")
    require(provenance.get("source_dirty") is False,
            "accepted parent was produced from a dirty source")
    require(provenance.get("smoke") is False,
            "smoke parent cannot feed full force evidence")
    require(provenance.get("fixture_sha256") == EXPECTED_FIXTURE_TABLES,
            "complete upstream fixture commitment mismatch")
    expected_subset = {"mode": "accepted_parent_subset", **EXPECTED_TABLES}
    require(provenance.get("selected_subset_sha256") == expected_subset,
            "selected parent subset commitment mismatch")

    summary = read_json(root / "summary.json")
    require(summary.get("decision") == EXPECTED_DECISION,
            "accepted parent decision mismatch")
    require(summary.get("no_promotion") is True,
            "accepted parent promotion boundary missing")
    require(summary.get("smoke") is False,
            "accepted parent summary is smoke data")
    require(summary.get("graph_failures") == 0 and
            summary.get("metamorphic_failures") == 0 and
            summary.get("checkpoint_failures") == 0,
            "accepted parent contains failed registered rows")
    prohibited = summary.get("prohibited_features")
    require(isinstance(prohibited, dict) and prohibited and
            all(value is False for value in prohibited.values()),
            "accepted parent prohibited-feature boundary failed")

    with (root / "configurations.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        rows = list(csv.DictReader(stream))
    observed_configurations = {
        row["configuration_id"]: row["role"] for row in rows
    }
    require(len(rows) == len(observed_configurations),
            "duplicate accepted configuration ID")
    require(observed_configurations == EXPECTED_CONFIGURATIONS,
            "bounded accepted configuration inventory mismatch")
    return {
        "source_sha": EXPECTED_SOURCE_SHA,
        "manifest_pre_hash": EXPECTED_PRE_HASH,
        **EXPECTED_TABLES,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-bundle", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if not args.verify:
        parser.error("--verify is required; this tool never regenerates evidence")
    try:
        result = verify(args.parent_bundle)
    except (OSError, ParentEvidenceError) as error:
        print(f"force parent evidence: FAIL: {error}")
        return 1
    print("force parent evidence: PASS")
    for name, value in result.items():
        print(f"{name}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
