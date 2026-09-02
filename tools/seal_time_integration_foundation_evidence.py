#!/usr/bin/env python3
"""Create or verify the Time Integration Foundation outer seal."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "mls.time-integration-foundation.outer-seal.v1"
PARENT_SHA = "ffefb2ea9ee0f032946af4ed23acd12883f20cfe"
PARENT_TAG = "authoritative-drift-state-bridge-lab-evidence-v1"
PARENT_TAG_OBJECT = "5a6237a9dcbe676aa4c89c10d5f9f94e935507e6"
BRANCH = "time-integration-foundation-lab"
DECISION = "temporal_convergence_blocked_by_authoritative_quantization"
TAG = "time-integration-foundation-lab-evidence-v1"
SHA1 = re.compile(r"[0-9a-f]{40}")
REQUIRED_GROUPS = {
    "raw-a", "raw-b", "oracle", "parent-drift-bridge",
    "source", "receipts", "docs",
}


class SealError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def inventory(bundle: Path) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for path in sorted(bundle.rglob("*")):
        if path.is_symlink():
            raise SealError(f"symlink forbidden in evidence: {path}")
        if not path.is_file() or path.name == "outer-seal.json":
            continue
        relative = path.relative_to(bundle).as_posix()
        if relative.startswith("/") or ".." in Path(relative).parts:
            raise SealError("unsafe evidence path")
        result.append(
            {"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)}
        )
    if not result:
        raise SealError("cannot seal empty evidence")
    return result


def pre_hash(value: dict[str, object]) -> str:
    candidate = dict(value)
    candidate["outer_pre_hash"] = None
    return hashlib.sha256(canonical(candidate)).hexdigest()


def create(bundle: Path, source_sha: str, ci_run_id: int) -> dict[str, object]:
    if not SHA1.fullmatch(source_sha):
        raise SealError("source SHA must be an exact lowercase Git SHA-1")
    if (bundle / "outer-seal.json").exists():
        raise SealError("outer seal already exists")
    groups = {path.name for path in bundle.iterdir()}
    if groups != REQUIRED_GROUPS or not all(
        (bundle / name).is_dir() for name in REQUIRED_GROUPS
    ):
        raise SealError("evidence payload group inventory differs")
    value: dict[str, object] = {
        "schema": SCHEMA,
        "accepted_parent_sha": PARENT_SHA,
        "accepted_parent_tag": PARENT_TAG,
        "accepted_parent_tag_object": PARENT_TAG_OBJECT,
        "branch": BRANCH,
        "source_sha": source_sha,
        "tag": TAG,
        "ci_run_id": ci_run_id,
        "decision": DECISION,
        "candidate": "quantized_kick_drift_kick",
        "negative_control": "symplectic_euler_control",
        "selected_refinement": 128,
        "position_remainder_present": False,
        "safe_domain": "2^-24",
        "promotion": "NO_PROMOTION",
        "promotion_permitted": False,
        "payload": inventory(bundle),
        "outer_pre_hash": None,
    }
    value["outer_pre_hash"] = pre_hash(value)
    (bundle / "outer-seal.json").write_bytes(canonical(value))
    return value


def verify(bundle: Path) -> dict[str, object]:
    try:
        value = json.loads((bundle / "outer-seal.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SealError("outer seal is unreadable") from error
    expected_fields = {
        "schema", "accepted_parent_sha", "accepted_parent_tag",
        "accepted_parent_tag_object", "branch", "source_sha", "tag",
        "ci_run_id", "decision", "candidate", "negative_control",
        "selected_refinement", "position_remainder_present", "safe_domain",
        "promotion", "promotion_permitted", "payload", "outer_pre_hash",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise SealError("outer seal field inventory differs")
    fixed: dict[str, object] = {
        "schema": SCHEMA,
        "accepted_parent_sha": PARENT_SHA,
        "accepted_parent_tag": PARENT_TAG,
        "accepted_parent_tag_object": PARENT_TAG_OBJECT,
        "branch": BRANCH,
        "tag": TAG,
        "decision": DECISION,
        "candidate": "quantized_kick_drift_kick",
        "negative_control": "symplectic_euler_control",
        "selected_refinement": 128,
        "position_remainder_present": False,
        "safe_domain": "2^-24",
        "promotion": "NO_PROMOTION",
        "promotion_permitted": False,
    }
    for field, expected in fixed.items():
        if value[field] != expected:
            raise SealError(f"outer seal fixed field differs: {field}")
    if not isinstance(value["source_sha"], str) or not SHA1.fullmatch(value["source_sha"]):
        raise SealError("outer seal source SHA malformed")
    if not isinstance(value["ci_run_id"], int) or value["ci_run_id"] <= 0:
        raise SealError("outer seal CI run ID malformed")
    if value["outer_pre_hash"] != pre_hash(value):
        raise SealError("outer pre-hash mismatch")
    if value["payload"] != inventory(bundle):
        raise SealError("outer payload inventory mismatch")
    payload_groups = {Path(item["path"]).parts[0] for item in value["payload"]}
    if payload_groups != REQUIRED_GROUPS:
        raise SealError("outer payload group inventory differs")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--bundle", type=Path, required=True)
    create_parser.add_argument("--source-sha", required=True)
    create_parser.add_argument("--ci-run-id", type=int, required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--bundle", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        value = (
            create(arguments.bundle, arguments.source_sha, arguments.ci_run_id)
            if arguments.command == "create"
            else verify(arguments.bundle)
        )
    except SealError as error:
        print(f"TIME INTEGRATION FOUNDATION OUTER SEAL INVALID: {error}")
        return 1
    print(json.dumps(value, indent=2, sort_keys=True))
    print(
        "TIME INTEGRATION FOUNDATION OUTER SEAL VALID: "
        "temporal_convergence_blocked_by_authoritative_quantization NO_PROMOTION"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
