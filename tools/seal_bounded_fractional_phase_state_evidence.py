#!/usr/bin/env python3
"""Create or verify the Bounded Fractional Phase-State Lab outer seal."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
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
WORKFLOW = "Bounded Fractional Phase-State Lab"
PRECISIONS = (64, 96, 128, 192, 256)
DECISIONS = {
    "stop_inconclusive_or_wrong_parent",
    "reject_bounded_binary_fractional_phase_state",
    "bounded_phase_state_restores_dynamics_but_structure_residuals_unresolved",
    "bounded_phase_state_converges_but_required_precision_unresolved",
    "retain_bounded_variable_exponent_phase_state_for_research",
}
RETAIN_DECISION = "retain_bounded_variable_exponent_phase_state_for_research"
FINAL_DECISION = (
    "bounded_phase_state_restores_dynamics_but_structure_residuals_unresolved"
)
FINAL_SELECTED_PRECISION = None
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
REQUIRED_JOBS = frozenset(
    {
        "C++ / Linux GCC",
        "C++ / Linux Clang",
        "C++ / Windows MSVC",
        "Python exact oracle",
        "Pinned Lean build and axiom output",
    }
)
CI_SOURCE_FIELDS = frozenset(
    {
        "attempt",
        "conclusion",
        "databaseId",
        "event",
        "headBranch",
        "headSha",
        "jobs",
        "status",
        "workflowName",
    }
)
CI_JOB_FIELDS = frozenset(
    {
        "completedAt",
        "conclusion",
        "databaseId",
        "name",
        "startedAt",
        "status",
        "steps",
        "url",
    }
)
CI_STEP_FIELDS = frozenset(
    {"completedAt", "conclusion", "name", "number", "startedAt", "status"}
)
CI_SCHEMA = "mls.bounded-fractional-phase-state.ci.v1"
RAW_FILES = frozenset(
    {
        "metadata.csv",
        "precisions.csv",
        "units.csv",
        "parent_fingerprint.csv",
        "positive_control.csv",
        "reference_packets.csv",
        "relations.csv",
        "force_operator.csv",
        "initial_states.csv",
        "endpoints.csv",
        "long_endpoints.csv",
        "checkpoint_states.csv",
        "recovery_states.csv",
        "representation_error.csv",
        "energies.csv",
        "long_energy.csv",
        "invariants.csv",
        "force_audit.csv",
        "reversibility.csv",
        "covariance.csv",
        "checkpoint.csv",
        "domain.csv",
        "state_size.csv",
        "operation_counts.csv",
        "rational_comparator.csv",
    }
)
DOCUMENT_FILES = frozenset(
    {
        "bounded-fractional-phase-state-preregistration.md",
        "bounded-fractional-phase-state-lab-contract.md",
        "bounded-fractional-phase-state-evidence-schema.md",
        "bounded-fractional-phase-state-result.md",
    }
)
ORACLE_FILES = frozenset(
    {"oracle-summary.json", "oracle.log", "mutation-regression.log"}
)
RECEIPT_FILES = frozenset(
    {
        "algorithm-contracts.log",
        "build.log",
        "ci-run-source.json",
        "ci-run.json",
        "configure.log",
        "ctest.log",
        "failed-attempts.json",
        "lean-axioms.log",
        "lean-build.log",
        "lean-trust.log",
        "mls-validation.log",
        "raw-a.log",
        "raw-b.log",
        "raw-files-sha256.log",
        "raw-twin.log",
        "seal-mutation-regression.log",
        "source-archive.log",
        "tool-versions.log",
    }
)
FAILED_ATTEMPTS_SCHEMA = "mls.bounded-fractional-phase-state.failed-attempts.v1"
FAILED_ATTEMPTS = (
    (
        "oversized-v1-public-archive",
        "f891c248c414a5a705e60c13b865a722d24b305b",
    ),
    (
        "compact-v2-row-order-verifier",
        "be6f95a8dac47153616d398a079b30830d7213da",
    ),
    (
        "overstrict-anchor-interpretation-verifier",
        "be6f95a8dac47153616d398a079b30830d7213da",
    ),
    (
        "incomplete-compositional-bound-verifier-precheck",
        "be6f95a8dac47153616d398a079b30830d7213da",
    ),
    (
        "branch-ci-oracle-timeout-33830169828",
        "506ee4b692b38041479a5781823f3c637483e50c",
    ),
)
SOURCE_ROOT = Path(__file__).resolve().parents[1]


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


def git_stdout(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SealError("local evidence tag cannot be resolved")
    result = completed.stdout.strip()
    if not result or "\n" in result:
        raise SealError("local evidence tag query returned malformed output")
    return result


def git_blob(repository: Path, object_specification: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repository), "cat-file", "blob", object_specification],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise SealError("tagged source document blob cannot be read")
    return completed.stdout


def validate_local_annotated_tag(
    repository: Path, source_sha: str, evidence_tag_object: str,
) -> None:
    """Bind create-mode inputs to the exact named local annotated tag.

    This is deliberately a create-only preflight.  Verification remains an
    offline replay of the tag object and peeled source identity recorded in the
    immutable outer seal.
    """
    try:
        local_repository = repository.resolve(strict=True)
    except OSError as error:
        raise SealError("local source repository cannot be resolved") from error
    tag_reference = f"refs/tags/{TAG}"
    local_tag_object = git_stdout(
        local_repository, "rev-parse", "--verify", tag_reference
    )
    if local_tag_object != evidence_tag_object:
        raise SealError("local evidence tag object differs from create input")
    if git_stdout(local_repository, "cat-file", "-t", local_tag_object) != "tag":
        raise SealError("local evidence tag is not annotated")
    peeled_source = git_stdout(
        local_repository, "rev-parse", "--verify", f"{tag_reference}^{{commit}}"
    )
    if peeled_source != source_sha:
        raise SealError("local evidence tag does not peel to source SHA")


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
    decision = validate_decision(
        summary.get("decision"), summary.get("selected_precision")
    )
    if decision != (FINAL_DECISION, FINAL_SELECTED_PRECISION):
        raise SealError("oracle disposition differs from the completed lab outcome")
    eligibility = summary.get("precision_eligibility")
    if not (
        summary.get("highest_precision_dynamics_pass") is True
        and summary.get("structure_residuals_resolved") is False
        and isinstance(eligibility, dict)
        and set(eligibility) == {str(precision) for precision in PRECISIONS}
        and all(value is False for value in eligibility.values())
    ):
        raise SealError("oracle completed-lab outcome gates differ")
    return decision


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


def validate_flat_inventory(
    directory: Path, expected: frozenset[str], label: str
) -> None:
    entries = list(directory.iterdir())
    if any(path.is_symlink() or not path.is_file() for path in entries):
        raise SealError(f"{label} must contain only regular files")
    actual = {path.name for path in entries}
    if actual != expected:
        difference = sorted(actual ^ expected)
        raise SealError(f"{label} file inventory differs: {difference}")
    empty = sorted(path.name for path in entries if path.stat().st_size == 0)
    if empty:
        raise SealError(f"{label} files must be nonempty: {empty}")


def validate_failed_attempts(path: Path) -> None:
    value = read_object(path, "failed-attempt receipt")
    if set(value) != {"schema", "attempts"} or value["schema"] != FAILED_ATTEMPTS_SCHEMA:
        raise SealError("failed-attempt receipt schema differs")
    attempts = value["attempts"]
    if not isinstance(attempts, list) or len(attempts) != len(FAILED_ATTEMPTS):
        raise SealError("failed-attempt receipt inventory differs")
    fields = {
        "id",
        "source_sha",
        "stage",
        "outcome",
        "scientific_disposition",
        "preservation",
    }
    for item, (expected_id, expected_sha) in zip(attempts, FAILED_ATTEMPTS):
        if not isinstance(item, dict) or set(item) != fields:
            raise SealError("failed-attempt item schema differs")
        if item["id"] != expected_id or item["source_sha"] != expected_sha:
            raise SealError("failed-attempt identity or order differs")
        if item["scientific_disposition"] is not None:
            raise SealError("failed attempt has a scientific disposition")
        if any(
            not isinstance(item[field], str) or not item[field]
            for field in ("stage", "outcome", "preservation")
        ):
            raise SealError("failed-attempt descriptive field is empty")


def validate_ci_source(
    source: dict[str, object], source_sha: str, run_id: int, branch: str,
) -> list[dict[str, str]]:
    if set(source) != CI_SOURCE_FIELDS:
        raise SealError("CI source field inventory differs")
    if (
        type(source["attempt"]) is not int
        or source["attempt"] < 1
        or type(source["databaseId"]) is not int
        or source["databaseId"] != run_id
        or source["event"] != "push"
        or source["headBranch"] != branch
        or source["headSha"] != source_sha
        or source["status"] != "completed"
        or source["conclusion"] != "success"
        or source["workflowName"] != WORKFLOW
        or not isinstance(source["jobs"], list)
    ):
        raise SealError("CI source identity differs")
    observed: dict[str, str] = {}
    for job in source["jobs"]:
        if not isinstance(job, dict) or set(job) != CI_JOB_FIELDS:
            raise SealError("CI source job schema differs")
        name = job["name"]
        if (
            not isinstance(name, str)
            or not name
            or name in observed
            or type(job["databaseId"]) is not int
            or job["databaseId"] <= 0
            or job["status"] != "completed"
            or job["conclusion"] != "success"
            or not isinstance(job["startedAt"], str)
            or not job["startedAt"]
            or not isinstance(job["completedAt"], str)
            or not job["completedAt"]
            or not isinstance(job["url"], str)
            or not job["url"]
            or not isinstance(job["steps"], list)
            or not job["steps"]
        ):
            raise SealError("CI source job identity differs")
        step_numbers: set[int] = set()
        for step in job["steps"]:
            if not isinstance(step, dict) or set(step) != CI_STEP_FIELDS:
                raise SealError("CI source step schema differs")
            number = step["number"]
            if (
                type(number) is not int
                or number <= 0
                or number in step_numbers
                or not isinstance(step["name"], str)
                or not step["name"]
                or not isinstance(step["status"], str)
                or not step["status"]
                or not isinstance(step["conclusion"], str)
                or not step["conclusion"]
                or not isinstance(step["startedAt"], str)
                or not step["startedAt"]
                or not isinstance(step["completedAt"], str)
                or not step["completedAt"]
            ):
                raise SealError("CI source step identity differs")
            step_numbers.add(number)
        observed[name] = str(job["conclusion"])
    if set(observed) != REQUIRED_JOBS:
        raise SealError("CI source job inventory differs")
    return [
        {"name": name, "conclusion": observed[name]}
        for name in sorted(observed)
    ]


def validate_ci_receipts(bundle: Path, source_sha: str, run_id: int) -> None:
    source = read_object(bundle / "receipts" / "ci-run-source.json", "CI source")
    jobs = validate_ci_source(source, source_sha, run_id, BRANCH)
    expected: dict[str, object] = {
        "schema": CI_SCHEMA,
        "repository": REPOSITORY,
        "workflow": WORKFLOW,
        "run_id": run_id,
        "run_attempt": source["attempt"],
        "head_sha": source_sha,
        "head_branch": BRANCH,
        "event": "push",
        "conclusion": "success",
        "jobs": jobs,
    }
    normalized = read_object(bundle / "receipts" / "ci-run.json", "CI receipt")
    if normalized != expected:
        raise SealError("normalized CI receipt differs from exact source")


def validate_inner_payload_inventory(
    bundle: Path, source_sha: str, repository: Path | None = None,
) -> None:
    """Freeze every closed inner payload group except the inherited parent.

    Publication receipts that can only exist after the immutable seal (tag CI,
    release, public archive, and fresh download) deliberately do not belong to
    this inventory.
    """

    validate_flat_inventory(bundle / "raw-a", RAW_FILES, "raw-a")
    validate_flat_inventory(bundle / "raw-b", RAW_FILES, "raw-b")
    validate_flat_inventory(bundle / "docs", DOCUMENT_FILES, "document")
    validate_flat_inventory(bundle / "oracle", ORACLE_FILES, "oracle")
    validate_flat_inventory(bundle / "receipts", RECEIPT_FILES, "receipt")
    validate_failed_attempts(bundle / "receipts" / "failed-attempts.json")
    validate_flat_inventory(
        bundle / "source",
        frozenset(
            {
                "source-identity.json",
                f"materiallifesubstrate-{source_sha}.tar.gz",
            }
        ),
        "source",
    )
    if repository is not None:
        for name in DOCUMENT_FILES:
            bundled_document = bundle / "docs" / name
            tagged_bytes = git_blob(repository, f"{source_sha}:docs/{name}")
            if bundled_document.read_bytes() != tagged_bytes:
                raise SealError(
                    f"bundled document is not an exact tagged-source copy: {name}"
                )


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
    bundle: Path, source_sha: str, evidence_tag_object: str, ci_run_id: int,
    repository: Path = SOURCE_ROOT,
) -> dict[str, object]:
    if SHA1.fullmatch(source_sha) is None:
        raise SealError("source SHA must be an exact lowercase Git SHA-1")
    if type(ci_run_id) is not int or ci_run_id <= 0:
        raise SealError("CI run ID must be a positive integer")
    if SHA1.fullmatch(evidence_tag_object) is None:
        raise SealError("evidence tag object must be an exact lowercase Git SHA-1")
    validate_local_annotated_tag(repository, source_sha, evidence_tag_object)
    validate_groups(bundle, False)
    # Walk before reading identities so symlinks and path collisions fail first.
    payload = inventory(bundle)
    validate_inner_payload_inventory(bundle, source_sha, repository)
    validate_ci_receipts(bundle, source_sha, ci_run_id)
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
    validate_inner_payload_inventory(bundle, source_sha)
    validate_ci_receipts(bundle, source_sha, int(value["ci_run_id"]))
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
    create_parser.add_argument("--repo", type=Path, default=SOURCE_ROOT)
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
                arguments.repo,
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
