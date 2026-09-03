#!/usr/bin/env python3
"""Create or verify the Bounded Fractional Phase-State Lab outer seal."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "mls.bounded-fractional-phase-state.outer-seal.v1"
ORACLE_SCHEMA = "mls.bounded-fractional-phase-state.oracle.v1"
SOURCE_SCHEMA = "mls.bounded-fractional-phase-state.source.v1"
REPOSITORY = "RobVanProd/materiallifesubstrate"
PARENT_SHA = "6f25d7428fde7420c1f4cbe1e3565c11a28e817c"
PARENT_TAG = "explicit-fractional-phase-state-lab-evidence-v1"
PARENT_TAG_OBJECT = "a0feca21f7676e0b6f1443c483bd62448d68c65b"
PARENT_ARCHIVE_SHA256 = (
    "77aad47e1842b4fe29760594ee247f609b5d1e88ae7e6b370d86c0bdbb6c71de"
)
PARENT_ARCHIVE_BYTES = 31_142_852
PARENT_OUTER_PRE_HASH = (
    "169a963d4336b23a2f55a19ec182b95cb0c208b30c008a6fc40a644cc763330f"
)
PARENT_DECISION = (
    "fractional_phase_state_restores_dynamics_but_bounded_representation_unresolved"
)
BRANCH = "bounded-fractional-phase-state-lab"
TAG = "bounded-fractional-phase-state-lab-evidence-v1"
PRECISIONS = (64, 96, 128, 192, 256)
DECISIONS = {
    "stop_inconclusive_or_wrong_parent",
    "reject_bounded_binary_fractional_phase_state",
    "bounded_phase_state_restores_dynamics_but_structure_residuals_unresolved",
    "bounded_phase_state_converges_but_required_precision_unresolved",
    "retain_bounded_variable_exponent_phase_state_for_research",
}
RETAIN_DECISION = "retain_bounded_variable_exponent_phase_state_for_research"
SHA1 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
REQUIRED_GROUPS = {
    "raw-a",
    "raw-b",
    "oracle",
    "parent-explicit-fractional",
    "source",
    "receipts",
    "docs",
}


class SealError(RuntimeError):
    """A fail-closed outer-seal validation error."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _safe_relative(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    parts = Path(relative).parts
    if (
        not relative
        or relative.startswith("/")
        or "\\" in relative
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise SealError(f"unsafe evidence path: {relative!r}")
    return relative


def _walk_entries(root: Path) -> Iterable[tuple[str, Path]]:
    if root.is_symlink() or not root.is_dir():
        raise SealError("evidence bundle must be a real directory")
    folded: set[str] = set()
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in sorted((*directory_names, *file_names)):
            path = base / name
            relative = _safe_relative(path, root)
            folded_name = relative.casefold()
            if folded_name in folded:
                raise SealError(f"case-colliding evidence path: {relative}")
            folded.add(folded_name)
            if path.is_symlink():
                raise SealError(f"symlink forbidden in evidence: {relative}")
            if not path.is_dir() and not path.is_file():
                raise SealError(f"unsupported evidence object: {relative}")
            yield relative, path


def inventory(bundle: Path) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for relative, path in _walk_entries(bundle):
        if path.is_file() and relative != "outer-seal.json":
            result.append(
                {"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)}
            )
    result.sort(key=lambda item: str(item["path"]))
    if not result:
        raise SealError("cannot seal empty evidence")
    return result


def directory_inventory(directory: Path) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for relative, path in _walk_entries(directory):
        if path.is_file():
            result.append(
                {"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)}
            )
    result.sort(key=lambda item: str(item["path"]))
    return result


def manifest_hash(items: list[dict[str, object]]) -> str:
    return sha256_bytes(canonical(items))


def read_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SealError(f"{label} is unreadable") from error
    if not isinstance(value, dict):
        raise SealError(f"{label} must be a JSON object")
    return value


def validate_decision(decision: object, selected_precision: object) -> tuple[str, int | None]:
    if not isinstance(decision, str) or decision not in DECISIONS:
        raise SealError("oracle decision is not registered")
    if decision == RETAIN_DECISION:
        if type(selected_precision) is not int or selected_precision not in PRECISIONS:
            raise SealError("retained decision requires one registered selected precision")
    elif selected_precision is not None:
        raise SealError("non-retained decision requires null selected precision")
    return decision, selected_precision  # type: ignore[return-value]


def oracle_identity(bundle: Path, source_sha: str) -> tuple[str, int | None]:
    summary = read_object(bundle / "oracle" / "oracle-summary.json", "oracle summary")
    if (
        summary.get("schema") != ORACLE_SCHEMA
        or summary.get("source_sha") != source_sha
        or summary.get("precision_decimal_digits") != 110
        or summary.get("promotion") != "NO_PROMOTION"
    ):
        raise SealError("oracle identity or promotion boundary differs")
    return validate_decision(summary.get("decision"), summary.get("selected_precision"))


def source_tree_identity(bundle: Path, source_sha: str) -> str:
    identity = read_object(bundle / "source" / "source-identity.json", "source identity")
    if (
        identity.get("schema") != SOURCE_SCHEMA
        or identity.get("repository") != REPOSITORY
        or identity.get("branch") != BRANCH
        or identity.get("source_sha") != source_sha
        or not isinstance(identity.get("tree_sha"), str)
        or SHA1.fullmatch(str(identity["tree_sha"])) is None
    ):
        raise SealError("source identity differs")
    return str(identity["tree_sha"])


def validate_parent_identity(bundle: Path) -> None:
    seal = read_object(
        bundle / "parent-explicit-fractional" / "outer-seal.json",
        "nested parent outer seal",
    )
    if (
        seal.get("source_sha") != PARENT_SHA
        or seal.get("tag") != PARENT_TAG
        or seal.get("decision") != PARENT_DECISION
        or seal.get("outer_pre_hash") != PARENT_OUTER_PRE_HASH
        or seal.get("promotion") != "NO_PROMOTION"
    ):
        raise SealError("nested parent scientific identity differs")


def validate_groups(bundle: Path, outer_present: bool) -> None:
    names = {path.name for path in bundle.iterdir()}
    expected = REQUIRED_GROUPS | ({"outer-seal.json"} if outer_present else set())
    if names != expected:
        raise SealError("evidence top-level inventory differs")
    if not all((bundle / name).is_dir() and not (bundle / name).is_symlink() for name in REQUIRED_GROUPS):
        raise SealError("evidence payload group inventory differs")
    if outer_present and not (bundle / "outer-seal.json").is_file():
        raise SealError("outer seal is not a regular file")


def pre_hash(value: dict[str, object]) -> str:
    candidate = dict(value)
    candidate["outer_pre_hash"] = None
    return sha256_bytes(canonical(candidate))


def fixed_fields() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "repository": REPOSITORY,
        "accepted_parent_sha": PARENT_SHA,
        "accepted_parent_tag": PARENT_TAG,
        "accepted_parent_tag_object": PARENT_TAG_OBJECT,
        "accepted_parent_archive_sha256": PARENT_ARCHIVE_SHA256,
        "accepted_parent_archive_bytes": PARENT_ARCHIVE_BYTES,
        "accepted_parent_outer_pre_hash": PARENT_OUTER_PRE_HASH,
        "branch": BRANCH,
        "tag": TAG,
        "candidate": "fixed_precision_variable_exponent_binary_phase_state",
        "precision_inventory": list(PRECISIONS),
        "gmpy2_version": "2.3.1",
        "mpfr_version": "MPFR 4.2.2",
        "rounding": "round_to_nearest_ties_to_even",
        "registered_fused_operations": [],
        "leading_exponent_min": -16_382,
        "leading_exponent_max": 16_383,
        "mpfr_context_emin": -16_381,
        "mpfr_context_emax": 16_384,
        "subnormalization": False,
        "adaptive_precision": False,
        "hidden_residual_or_history": False,
        "safe_domain": "2^-24",
        "physical_budgets": {
            "position": "1/134217728000000000",
            "momentum": "1/70368744177664",
            "angular_centrality": "1/9007199254740992000000000",
            "energy": "1/9007199254740992",
            "momentum_slope": "1/1125899906842624",
            "angular_momentum_slope": "1/144115188075855872000000000",
            "energy_slope": "1/144115188075855872",
        },
        "promotion": "NO_PROMOTION",
        "promotion_permitted": False,
    }


def create(
    bundle: Path, source_sha: str, evidence_tag_object: str, ci_run_id: int
) -> dict[str, object]:
    if SHA1.fullmatch(source_sha) is None:
        raise SealError("source SHA must be an exact lowercase Git SHA-1")
    if type(ci_run_id) is not int or ci_run_id <= 0:
        raise SealError("CI run ID must be a positive integer")
    if SHA1.fullmatch(evidence_tag_object) is None or evidence_tag_object == source_sha:
        raise SealError("evidence tag object must identify an annotated tag")
    validate_groups(bundle, False)
    # Walk before reading identities so symlinks and path collisions fail first.
    payload = inventory(bundle)
    raw_a = directory_inventory(bundle / "raw-a")
    raw_b = directory_inventory(bundle / "raw-b")
    if raw_a != raw_b:
        raise SealError("raw twin inventories or bytes differ")
    decision, selected_precision = oracle_identity(bundle, source_sha)
    source_tree_sha = source_tree_identity(bundle, source_sha)
    validate_parent_identity(bundle)
    value: dict[str, object] = {
        **fixed_fields(),
        "source_sha": source_sha,
        "source_tree_sha": source_tree_sha,
        "evidence_tag_object": evidence_tag_object,
        "ci_run_id": ci_run_id,
        "decision": decision,
        "selected_precision": selected_precision,
        "raw_twin_manifest_sha256": manifest_hash(raw_a),
        "payload_manifest_sha256": manifest_hash(payload),
        "payload": payload,
        "outer_pre_hash": None,
    }
    value["outer_pre_hash"] = pre_hash(value)
    (bundle / "outer-seal.json").write_bytes(canonical(value))
    return value


def verify(bundle: Path) -> dict[str, object]:
    validate_groups(bundle, True)
    seal_path = bundle / "outer-seal.json"
    try:
        raw_seal = seal_path.read_bytes()
        value = json.loads(raw_seal.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SealError("outer seal is unreadable") from error
    expected_fields = {
        *fixed_fields(),
        "source_sha",
        "source_tree_sha",
        "evidence_tag_object",
        "ci_run_id",
        "decision",
        "selected_precision",
        "raw_twin_manifest_sha256",
        "payload_manifest_sha256",
        "payload",
        "outer_pre_hash",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise SealError("outer seal field inventory differs")
    if raw_seal != canonical(value):
        raise SealError("outer seal is not canonical JSON")
    for field, expected in fixed_fields().items():
        if value[field] != expected:
            raise SealError(f"outer seal fixed field differs: {field}")
    source_sha = value["source_sha"]
    if not isinstance(source_sha, str) or SHA1.fullmatch(source_sha) is None:
        raise SealError("outer seal source SHA malformed")
    if not isinstance(value["source_tree_sha"], str) or SHA1.fullmatch(value["source_tree_sha"]) is None:
        raise SealError("outer seal source tree SHA malformed")
    if (
        not isinstance(value["evidence_tag_object"], str)
        or SHA1.fullmatch(value["evidence_tag_object"]) is None
        or value["evidence_tag_object"] == source_sha
    ):
        raise SealError("outer seal evidence tag object malformed")
    if type(value["ci_run_id"]) is not int or value["ci_run_id"] <= 0:
        raise SealError("outer seal CI run ID malformed")
    decision, selected_precision = validate_decision(
        value["decision"], value["selected_precision"]
    )
    for field in ("raw_twin_manifest_sha256", "payload_manifest_sha256", "outer_pre_hash"):
        if not isinstance(value[field], str) or SHA256.fullmatch(value[field]) is None:
            raise SealError(f"outer seal hash malformed: {field}")
    if value["outer_pre_hash"] != pre_hash(value):
        raise SealError("outer pre-hash mismatch")
    payload = inventory(bundle)
    if value["payload"] != payload:
        raise SealError("outer payload inventory mismatch")
    if value["payload_manifest_sha256"] != manifest_hash(payload):
        raise SealError("outer payload manifest hash mismatch")
    payload_groups = {Path(str(item["path"])).parts[0] for item in payload}
    if payload_groups != REQUIRED_GROUPS:
        raise SealError("outer payload group inventory differs")
    raw_a = directory_inventory(bundle / "raw-a")
    raw_b = directory_inventory(bundle / "raw-b")
    if raw_a != raw_b:
        raise SealError("raw twin inventories or bytes differ")
    if value["raw_twin_manifest_sha256"] != manifest_hash(raw_a):
        raise SealError("raw twin manifest hash mismatch")
    oracle_decision, oracle_precision = oracle_identity(bundle, source_sha)
    if (decision, selected_precision) != (oracle_decision, oracle_precision):
        raise SealError("outer/oracle disposition differs")
    if value["source_tree_sha"] != source_tree_identity(bundle, source_sha):
        raise SealError("outer/source tree identity differs")
    validate_parent_identity(bundle)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--bundle", type=Path, required=True)
    create_parser.add_argument("--source-sha", required=True)
    create_parser.add_argument("--tag-object", required=True)
    create_parser.add_argument("--ci-run-id", type=int, required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--bundle", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        value = (
            create(
                arguments.bundle.resolve(),
                arguments.source_sha,
                arguments.tag_object,
                arguments.ci_run_id,
            )
            if arguments.command == "create"
            else verify(arguments.bundle.resolve())
        )
    except (OSError, SealError) as error:
        print(f"BOUNDED FRACTIONAL PHASE STATE OUTER SEAL INVALID: {error}")
        return 1
    print(json.dumps(value, indent=2, sort_keys=True))
    print(
        "BOUNDED FRACTIONAL PHASE STATE OUTER SEAL VALID: "
        f"{value['decision']} selected_precision={value['selected_precision']} NO_PROMOTION"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
