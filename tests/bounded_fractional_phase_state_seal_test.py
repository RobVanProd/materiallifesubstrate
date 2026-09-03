#!/usr/bin/env python3
"""Outer-seal positives and fail-closed mutations for bounded phase evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


SOURCE_SHA = "0123456789abcdef0123456789abcdef01234567"
TREE_SHA = "89abcdef0123456789abcdef0123456789abcdef"
TAG_OBJECT = "fedcba9876543210fedcba9876543210fedcba98"
PARENT_SHA = "6f25d7428fde7420c1f4cbe1e3565c11a28e817c"
PARENT_TAG = "explicit-fractional-phase-state-lab-evidence-v1"
PARENT_PREHASH = "169a963d4336b23a2f55a19ec182b95cb0c208b30c008a6fc40a644cc763330f"
PARENT_DECISION = (
    "fractional_phase_state_restores_dynamics_but_bounded_representation_unresolved"
)
DECISION = "bounded_phase_state_converges_but_required_precision_unresolved"
GROUPS = (
    "raw-a",
    "raw-b",
    "oracle",
    "parent-explicit-fractional",
    "source",
    "receipts",
    "docs",
)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def pre_hash(value: dict[str, object]) -> str:
    candidate = dict(value)
    candidate["outer_pre_hash"] = None
    return hashlib.sha256(canonical(candidate)).hexdigest()


def invoke(tool: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(tool), *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def fixture(root: Path, name: str = "bundle") -> Path:
    bundle = root / name
    for group in GROUPS:
        (bundle / group).mkdir(parents=True)
    twin = b"key,value\nschema,synthetic\n"
    (bundle / "raw-a" / "metadata.csv").write_bytes(twin)
    (bundle / "raw-b" / "metadata.csv").write_bytes(twin)
    (bundle / "oracle" / "oracle-summary.json").write_bytes(
        canonical(
            {
                "schema": "mls.bounded-fractional-phase-state.oracle.v1",
                "precision_decimal_digits": 110,
                "source_sha": SOURCE_SHA,
                "decision": DECISION,
                "selected_precision": None,
                "promotion": "NO_PROMOTION",
            }
        )
    )
    (bundle / "parent-explicit-fractional" / "outer-seal.json").write_bytes(
        canonical(
            {
                "source_sha": PARENT_SHA,
                "tag": PARENT_TAG,
                "decision": PARENT_DECISION,
                "outer_pre_hash": PARENT_PREHASH,
                "promotion": "NO_PROMOTION",
            }
        )
    )
    archive = bundle / "source" / f"materiallifesubstrate-{SOURCE_SHA}.tar.gz"
    archive.write_bytes(b"synthetic source archive\n")
    (bundle / "source" / "source-identity.json").write_bytes(
        canonical(
            {
                "schema": "mls.bounded-fractional-phase-state.source.v1",
                "repository": "RobVanProd/materiallifesubstrate",
                "branch": "bounded-fractional-phase-state-lab",
                "source_sha": SOURCE_SHA,
                "tree_sha": TREE_SHA,
                "archive": archive.name,
                "archive_bytes": archive.stat().st_size,
                "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            }
        )
    )
    (bundle / "receipts" / "synthetic.txt").write_text("receipt\n", encoding="utf-8")
    (bundle / "docs" / "synthetic.md").write_text("# Synthetic\n", encoding="utf-8")
    return bundle


def create(
    tool: Path, bundle: Path, tag_object: str = TAG_OBJECT
) -> subprocess.CompletedProcess[str]:
    return invoke(
        tool,
        "create",
        "--bundle",
        str(bundle),
        "--source-sha",
        SOURCE_SHA,
        "--tag-object",
        tag_object,
        "--ci-run-id",
        "1",
    )


def must_reject(label: str, operation: Callable[[], subprocess.CompletedProcess[str]]) -> None:
    completed = operation()
    if completed.returncode == 0:
        raise AssertionError(f"seal accepted mutation: {label}\n{completed.stdout}")


def rewrite_seal(bundle: Path, mutate: Callable[[dict[str, object]], None]) -> None:
    path = bundle / "outer-seal.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    mutate(value)
    value["outer_pre_hash"] = pre_hash(value)
    path.write_bytes(canonical(value))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tool",
        type=Path,
        default=root / "tools" / "seal_bounded_fractional_phase_state_evidence.py",
    )
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="mls-bounded-phase-seal-") as temporary:
        temporary_root = Path(temporary)
        bundle = fixture(temporary_root, "positive")
        created = create(arguments.tool, bundle)
        if created.returncode != 0:
            raise AssertionError(f"seal create failed\n{created.stdout}\n{created.stderr}")
        first = invoke(arguments.tool, "verify", "--bundle", str(bundle))
        second = invoke(arguments.tool, "verify", "--bundle", str(bundle))
        if first.returncode != 0 or first.stdout != second.stdout:
            raise AssertionError("seal positive verification differs")
        must_reject("second create", lambda: create(arguments.tool, bundle))

        lightweight_tag = fixture(temporary_root, "lightweight-tag")
        must_reject(
            "lightweight evidence tag",
            lambda: create(arguments.tool, lightweight_tag, SOURCE_SHA),
        )

        payload = bundle / "raw-a" / "metadata.csv"
        original = payload.read_bytes()
        payload.write_bytes(original + b"mutation")
        must_reject(
            "payload bytes", lambda: invoke(arguments.tool, "verify", "--bundle", str(bundle))
        )
        payload.write_bytes(original)

        source_archive = bundle / "source" / f"materiallifesubstrate-{SOURCE_SHA}.tar.gz"
        original_source_archive = source_archive.read_bytes()
        source_archive.write_bytes(original_source_archive + b"mutation")
        must_reject(
            "source archive bytes",
            lambda: invoke(arguments.tool, "verify", "--bundle", str(bundle)),
        )
        source_archive.write_bytes(original_source_archive)

        parent_payload = bundle / "parent-explicit-fractional" / "outer-seal.json"
        original_parent_payload = parent_payload.read_bytes()
        parent_payload.write_bytes(original_parent_payload + b"mutation")
        must_reject(
            "nested parent payload",
            lambda: invoke(arguments.tool, "verify", "--bundle", str(bundle)),
        )
        parent_payload.write_bytes(original_parent_payload)

        rewrite_seal(bundle, lambda value: value.__setitem__("decision", "reject_bounded_binary_fractional_phase_state"))
        must_reject(
            "outer/oracle decision", lambda: invoke(arguments.tool, "verify", "--bundle", str(bundle))
        )

        noncanonical = fixture(temporary_root, "noncanonical")
        if create(arguments.tool, noncanonical).returncode != 0:
            raise AssertionError("noncanonical fixture did not seal")
        seal_path = noncanonical / "outer-seal.json"
        seal_path.write_bytes(seal_path.read_bytes() + b"\n")
        must_reject(
            "noncanonical seal JSON",
            lambda: invoke(arguments.tool, "verify", "--bundle", str(noncanonical)),
        )

        bad_selection = fixture(temporary_root, "bad-selection")
        summary_path = bad_selection / "oracle" / "oracle-summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["decision"] = "retain_bounded_variable_exponent_phase_state_for_research"
        summary["selected_precision"] = None
        summary_path.write_bytes(canonical(summary))
        must_reject("retain without precision", lambda: create(arguments.tool, bad_selection))

        unexpected_selection = fixture(temporary_root, "unexpected-selection")
        summary_path = unexpected_selection / "oracle" / "oracle-summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["selected_precision"] = 128
        summary_path.write_bytes(canonical(summary))
        must_reject(
            "non-retain with precision", lambda: create(arguments.tool, unexpected_selection)
        )

        twins = fixture(temporary_root, "twin-mismatch")
        (twins / "raw-b" / "metadata.csv").write_text("different\n", encoding="utf-8")
        must_reject("raw twin mismatch", lambda: create(arguments.tool, twins))

        extra = fixture(temporary_root, "extra")
        (extra / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
        must_reject("extra top-level payload", lambda: create(arguments.tool, extra))

        collision = fixture(temporary_root, "case-collision")
        (collision / "docs" / "Case.txt").write_text("first\n", encoding="utf-8")
        (collision / "docs" / "case.txt").write_text("second\n", encoding="utf-8")
        must_reject("case collision", lambda: create(arguments.tool, collision))

        symlink = fixture(temporary_root, "symlink")
        try:
            (symlink / "docs" / "link").symlink_to("synthetic.md")
        except (OSError, NotImplementedError):
            pass
        else:
            must_reject("symlink", lambda: create(arguments.tool, symlink))

        source_mismatch = fixture(temporary_root, "source-mismatch")
        summary_path = source_mismatch / "oracle" / "oracle-summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["source_sha"] = "f" * 40
        summary_path.write_bytes(canonical(summary))
        must_reject("oracle/source mismatch", lambda: create(arguments.tool, source_mismatch))

    print(
        "bounded fractional phase-state outer-seal regression: "
        "PASS (2 deterministic positives, 14 fail-closed mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
