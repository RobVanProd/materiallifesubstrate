#!/usr/bin/env python3
"""Outer-seal positives and fail-closed mutations for bounded phase evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


SOURCE_SHA = "0123456789abcdef0123456789abcdef01234567"
TREE_SHA = "89abcdef0123456789abcdef0123456789abcdef"
TAG_OBJECT = "fedcba9876543210fedcba9876543210fedcba98"
TAG = "bounded-fractional-phase-state-lab-evidence-v1"
BRANCH = "bounded-fractional-phase-state-lab"
WORKFLOW = "Bounded Fractional Phase-State Lab"
REPOSITORY = "RobVanProd/materiallifesubstrate"
LOCAL_REPOSITORY: Path | None = None
PARENT_SHA = "6f25d7428fde7420c1f4cbe1e3565c11a28e817c"
PARENT_TAG = "explicit-fractional-phase-state-lab-evidence-v1"
PARENT_PREHASH = "169a963d4336b23a2f55a19ec182b95cb0c208b30c008a6fc40a644cc763330f"
PARENT_DECISION = (
    "fractional_phase_state_restores_dynamics_but_bounded_representation_unresolved"
)
DECISION = "bounded_phase_state_restores_dynamics_but_structure_residuals_unresolved"
REQUIRED_JOBS = frozenset(
    {
        "C++ / Linux GCC",
        "C++ / Linux Clang",
        "C++ / Windows MSVC",
        "Python exact oracle",
        "Pinned Lean build and axiom output",
    }
)
GROUPS = (
    "raw-a",
    "raw-b",
    "oracle",
    "parent-explicit-fractional",
    "source",
    "receipts",
    "docs",
)
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
)


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def ci_source(branch: str = BRANCH, run_id: int = 1) -> dict[str, object]:
    return {
        "attempt": 1,
        "conclusion": "success",
        "databaseId": run_id,
        "event": "push",
        "headBranch": branch,
        "headSha": SOURCE_SHA,
        "jobs": [
            {
                "completedAt": "2026-01-01T00:01:00Z",
                "conclusion": "success",
                "databaseId": index,
                "name": name,
                "startedAt": "2026-01-01T00:00:00Z",
                "status": "completed",
                "steps": [
                    {
                        "completedAt": "2026-01-01T00:01:00Z",
                        "conclusion": "success",
                        "name": "Synthetic gate",
                        "number": 1,
                        "startedAt": "2026-01-01T00:00:00Z",
                        "status": "completed",
                    }
                ],
                "url": f"https://example.invalid/jobs/{index}",
            }
            for index, name in enumerate(sorted(REQUIRED_JOBS), start=1)
        ],
        "status": "completed",
        "workflowName": WORKFLOW,
    }


def normalized_ci(
    source: dict[str, object],
    *,
    branch: str = BRANCH,
    schema: str = "mls.bounded-fractional-phase-state.ci.v1",
) -> dict[str, object]:
    jobs = source["jobs"]
    if not isinstance(jobs, list):
        raise AssertionError("synthetic CI jobs malformed")
    return {
        "schema": schema,
        "repository": REPOSITORY,
        "workflow": WORKFLOW,
        "run_id": source["databaseId"],
        "run_attempt": source["attempt"],
        "head_sha": source["headSha"],
        "head_branch": branch,
        "event": source["event"],
        "conclusion": source["conclusion"],
        "jobs": [
            {"name": job["name"], "conclusion": job["conclusion"]}
            for job in sorted(jobs, key=lambda item: str(item["name"]))
            if isinstance(job, dict)
        ],
    }


def publication_fixture(
    root: Path, seal: dict[str, object], name: str = "publication-receipts"
) -> Path:
    publication = root / name
    publication.mkdir()
    tag_source = ci_source(TAG, 2)
    (publication / "tag-ci-run-source.json").write_bytes(canonical(tag_source))
    tag_ci = normalized_ci(
        tag_source,
        branch=TAG,
        schema="mls.bounded-fractional-phase-state.tag-ci.v1",
    )
    tag_ci["tag"] = TAG
    tag_ci["tag_object"] = seal["evidence_tag_object"]
    (publication / "tag-ci-run.json").write_bytes(canonical(tag_ci))
    archive_sha256 = "a" * 64
    release = {
        "schema": "mls.bounded-fractional-phase-state.release-source.v1",
        "repository": REPOSITORY,
        "tag_name": TAG,
        "name": "Bounded Fractional Phase-State Lab evidence v1",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "id": 3,
                "name": "bounded-fractional-phase-state-evidence-v1.tar.gz",
                "size": 12345,
                "state": "uploaded",
                "digest": f"sha256:{archive_sha256}",
            }
        ],
    }
    (publication / "release-source.json").write_bytes(canonical(release))
    (publication / "public-archive-sha256.log").write_text(
        f"{archive_sha256}  bounded-fractional-phase-state-evidence-v1.tar.gz\n",
        encoding="utf-8",
    )
    fresh = {
        "schema": "mls.bounded-fractional-phase-state.fresh-public-validation.v1",
        "repository": REPOSITORY,
        "source_sha": seal["source_sha"],
        "tag": TAG,
        "tag_object": seal["evidence_tag_object"],
        "tag_ci_run_id": "2",
        "tag_ci_run_attempt": "1",
        "release_name": release["name"],
        "asset_id": "3",
        "asset_name": release["assets"][0]["name"],
        "archive_bytes": "12345",
        "archive_sha256": archive_sha256,
        "outer_pre_hash": seal["outer_pre_hash"],
        "decision": seal["decision"],
        "selected_precision": (
            "null"
            if seal["selected_precision"] is None
            else str(seal["selected_precision"])
        ),
        "promotion": "NO_PROMOTION",
        "fresh_download": "PASS",
        "fresh_archive_digest": "PASS",
        "fresh_bundle_identity": "PASS",
        "fresh_outer_seal": "PASS",
        "fresh_full_validation": "PASS",
    }
    (publication / "fresh-public-validation.log").write_text(
        "".join(f"{key}={fresh[key]}\n" for key in sorted(fresh)),
        encoding="utf-8",
    )
    return publication


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


def git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "MLS Seal Regression",
            "GIT_AUTHOR_EMAIL": "seal-regression@example.invalid",
            "GIT_COMMITTER_NAME": "MLS Seal Regression",
            "GIT_COMMITTER_EMAIL": "seal-regression@example.invalid",
        },
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git fixture command failed: {' '.join(arguments)}\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    return completed.stdout.strip()


def annotated_tag_repository(root: Path) -> tuple[Path, str, str, str]:
    repository = root / "tag-repository"
    repository.mkdir()
    git(repository, "init", "--quiet")
    (repository / "docs").mkdir()
    source_root = Path(__file__).resolve().parents[1]
    for document in DOCUMENT_FILES:
        (repository / "docs" / document).write_bytes(
            (source_root / "docs" / document).read_bytes()
        )
    (repository / "source.txt").write_text("sealed source\n", encoding="utf-8")
    git(repository, "add", "docs", "source.txt")
    git(repository, "commit", "--quiet", "-m", "sealed source")
    source_sha = git(repository, "rev-parse", "HEAD")
    tree_sha = git(repository, "rev-parse", "HEAD^{tree}")
    git(repository, "tag", "-a", TAG, "-m", "synthetic evidence tag", source_sha)
    tag_object = git(repository, "rev-parse", f"refs/tags/{TAG}")
    return repository, source_sha, tree_sha, tag_object


def restore_annotated_tag(repository: Path, source_sha: str) -> str:
    git(
        repository, "tag", "-f", "-a", TAG,
        "-m", "synthetic evidence tag", source_sha,
    )
    return git(repository, "rev-parse", f"refs/tags/{TAG}")


def fixture(root: Path, name: str = "bundle") -> Path:
    bundle = root / name
    for group in GROUPS:
        (bundle / group).mkdir(parents=True)
    twin = b"key,value\nschema,synthetic\n"
    for raw_name in ("raw-a", "raw-b"):
        for filename in RAW_FILES:
            (bundle / raw_name / filename).write_bytes(
                twin if filename == "metadata.csv" else b"synthetic\n"
            )
    (bundle / "oracle" / "oracle-summary.json").write_bytes(
        canonical(
            {
                "schema": "mls.bounded-fractional-phase-state.oracle.v1",
                "precision_decimal_digits": 110,
                "source_sha": SOURCE_SHA,
                "decision": DECISION,
                "selected_precision": None,
                "highest_precision_dynamics_pass": True,
                "structure_residuals_resolved": False,
                "precision_eligibility": {
                    str(precision): False
                    for precision in (64, 96, 128, 192, 256)
                },
                "promotion": "NO_PROMOTION",
            }
        )
    )
    (bundle / "oracle" / "oracle.log").write_text("oracle receipt\n", encoding="utf-8")
    (bundle / "oracle" / "mutation-regression.log").write_text(
        "mutation receipt\n", encoding="utf-8"
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
    for receipt in RECEIPT_FILES:
        (bundle / "receipts" / receipt).write_text(
            f"synthetic receipt: {receipt}\n", encoding="utf-8"
        )
    branch_ci = ci_source()
    (bundle / "receipts" / "ci-run-source.json").write_bytes(canonical(branch_ci))
    (bundle / "receipts" / "ci-run.json").write_bytes(
        canonical(normalized_ci(branch_ci))
    )
    (bundle / "receipts" / "failed-attempts.json").write_bytes(
        canonical(
            {
                "schema": FAILED_ATTEMPTS_SCHEMA,
                "attempts": [
                    {
                        "id": identifier,
                        "source_sha": source_sha,
                        "stage": "synthetic_stage",
                        "outcome": "synthetic_failure",
                        "scientific_disposition": None,
                        "preservation": "receipt_only",
                    }
                    for identifier, source_sha in FAILED_ATTEMPTS
                ],
            }
        )
    )
    source_root = Path(__file__).resolve().parents[1]
    for document in DOCUMENT_FILES:
        (bundle / "docs" / document).write_bytes(
            (source_root / "docs" / document).read_bytes()
        )
    return bundle


def create(
    tool: Path, bundle: Path, tag_object: str | None = None,
) -> subprocess.CompletedProcess[str]:
    if LOCAL_REPOSITORY is None:
        raise RuntimeError("local tag repository fixture is not initialized")
    return invoke(
        tool,
        "create",
        "--bundle",
        str(bundle),
        "--source-sha",
        SOURCE_SHA,
        "--tag-object",
        TAG_OBJECT if tag_object is None else tag_object,
        "--ci-run-id",
        "1",
        "--repo",
        str(LOCAL_REPOSITORY),
    )


def must_reject(label: str, operation: Callable[[], subprocess.CompletedProcess[str]]) -> None:
    completed = operation()
    if completed.returncode == 0:
        raise AssertionError(f"seal accepted mutation: {label}\n{completed.stdout}")


def must_reject_inventory(
    label: str,
    validator: Callable[[Path, Path, str], None],
    bundle: Path,
) -> None:
    if LOCAL_REPOSITORY is None:
        raise RuntimeError("local tag repository fixture is not initialized")
    try:
        validator(bundle, LOCAL_REPOSITORY, SOURCE_SHA)
    except (OSError, RuntimeError, json.JSONDecodeError):
        return
    raise AssertionError(f"full validator accepted inventory mutation: {label}")


def must_reject_validation(label: str, operation: Callable[[], None]) -> None:
    try:
        operation()
    except (OSError, RuntimeError, json.JSONDecodeError):
        return
    raise AssertionError(f"full validator accepted mutation: {label}")


def must_reject_publication(
    label: str,
    validator: Callable[[Path, Path, dict[str, object]], dict[str, object]],
    publication: Path,
    bundle: Path,
    seal: dict[str, object],
) -> None:
    try:
        validator(publication, bundle, seal)
    except (OSError, RuntimeError, json.JSONDecodeError):
        return
    raise AssertionError(f"publication validator accepted mutation: {label}")


def rewrite_seal(bundle: Path, mutate: Callable[[dict[str, object]], None]) -> None:
    path = bundle / "outer-seal.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    mutate(value)
    value["outer_pre_hash"] = pre_hash(value)
    path.write_bytes(canonical(value))


def main() -> int:
    global LOCAL_REPOSITORY, SOURCE_SHA, TREE_SHA, TAG_OBJECT
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tool",
        type=Path,
        default=root / "tools" / "seal_bounded_fractional_phase_state_evidence.py",
    )
    parser.add_argument(
        "--validator",
        type=Path,
        default=root / "reference" / "validate_bounded_fractional_phase_state_bundle.py",
    )
    arguments = parser.parse_args()
    validator_namespace = runpy.run_path(str(arguments.validator))
    validate_inner_inventory = validator_namespace["validate_inner_payload_inventory"]
    validate_ci_receipt = validator_namespace["validate_ci_receipt"]
    validate_summary = validator_namespace["validate_summary"]
    validate_public_branch_ci = validator_namespace["validate_public_branch_ci"]
    validate_publication = validator_namespace["validate_publication_receipts"]
    validate_online_publication_match = validator_namespace[
        "validate_online_publication_match"
    ]
    fetch_public_ci_run = validator_namespace["fetch_public_ci_run"]
    with tempfile.TemporaryDirectory(prefix="mls-bounded-phase-seal-") as temporary:
        temporary_root = Path(temporary)
        (
            LOCAL_REPOSITORY,
            SOURCE_SHA,
            TREE_SHA,
            TAG_OBJECT,
        ) = annotated_tag_repository(temporary_root)
        public_ci_source = ci_source()
        function_globals = fetch_public_ci_run.__globals__
        original_invoke = function_globals["invoke"]

        def synthetic_invoke(
            command: list[str], cwd: Path, *, timeout_seconds: int,
            label: str, stream_output: bool = False,
        ) -> subprocess.CompletedProcess[str]:
            del cwd, timeout_seconds, label, stream_output
            if command[-1] != (
                "attempt,conclusion,databaseId,event,headBranch,headSha,"
                "jobs,status,workflowName"
            ):
                raise AssertionError("public CI query field set differs")
            return subprocess.CompletedProcess(
                command, 0, canonical(public_ci_source).decode("utf-8"), ""
            )

        function_globals["invoke"] = synthetic_invoke
        try:
            observed_public_ci = fetch_public_ci_run(
                1, SOURCE_SHA, BRANCH, LOCAL_REPOSITORY, "synthetic public CI"
            )
            if observed_public_ci != public_ci_source:
                raise AssertionError("synthetic public CI source changed")
            public_ci_source["headSha"] = "f" * 40
            must_reject_validation(
                "public branch CI source mismatch",
                lambda: fetch_public_ci_run(
                    1,
                    SOURCE_SHA,
                    BRANCH,
                    LOCAL_REPOSITORY,
                    "synthetic public CI",
                ),
            )
        finally:
            function_globals["invoke"] = original_invoke
        bundle = fixture(temporary_root, "positive")
        summary = {field: None for field in validator_namespace["ORACLE_FIELDS"]}
        summary.update(
            {
                "schema": "mls.bounded-fractional-phase-state.oracle.v1",
                "precision_decimal_digits": 110,
                "source_sha": SOURCE_SHA,
                "decision": DECISION,
                "selected_precision": None,
                "promotion": "NO_PROMOTION",
                "highest_precision_dynamics_pass": True,
                "structure_residuals_resolved": False,
                "precision_eligibility": {
                    str(precision): False for precision in (64, 96, 128, 192, 256)
                },
                "composition_contracts": {
                    "all_qualitative_gates_converge": False,
                    "all_required_full_tail_anchors_qualified": False,
                },
                "long_run": {
                    "all_required_full_tail_anchors_qualified": False,
                },
            }
        )
        summary_seal = {
            "source_sha": SOURCE_SHA,
            "decision": DECISION,
            "selected_precision": None,
        }
        validate_summary(summary, summary_seal)
        summary_mutations = []
        malformed_eligibility = copy.deepcopy(summary)
        malformed_eligibility["precision_eligibility"].pop("256")
        summary_mutations.append(("summary eligibility inventory", malformed_eligibility))
        eligible_negative = copy.deepcopy(summary)
        eligible_negative["precision_eligibility"]["256"] = True
        summary_mutations.append(("summary eligible negative", eligible_negative))
        structure_mismatch = copy.deepcopy(summary)
        structure_mismatch["composition_contracts"][
            "all_qualitative_gates_converge"
        ] = True
        summary_mutations.append(("summary structure aggregate", structure_mismatch))
        anchor_mismatch = copy.deepcopy(summary)
        anchor_mismatch["long_run"][
            "all_required_full_tail_anchors_qualified"
        ] = True
        summary_mutations.append(("summary anchor aggregate", anchor_mismatch))
        non_smallest = copy.deepcopy(summary)
        non_smallest.update(
            {
                "decision": "retain_bounded_variable_exponent_phase_state_for_research",
                "selected_precision": 128,
                "structure_residuals_resolved": True,
            }
        )
        non_smallest["composition_contracts"][
            "all_qualitative_gates_converge"
        ] = True
        non_smallest["precision_eligibility"]["96"] = True
        non_smallest["precision_eligibility"]["128"] = True
        non_smallest_seal = {
            "source_sha": SOURCE_SHA,
            "decision": non_smallest["decision"],
            "selected_precision": non_smallest["selected_precision"],
        }
        must_reject_validation(
            "summary retained non-smallest precision",
            lambda: validate_summary(non_smallest, non_smallest_seal),
        )
        for label, altered in summary_mutations:
            must_reject_validation(
                label, lambda value=altered: validate_summary(value, summary_seal)
            )
        validate_inner_inventory(bundle, LOCAL_REPOSITORY, SOURCE_SHA)
        validate_ci_receipt(bundle, SOURCE_SHA, 1)
        validate_public_branch_ci(ci_source(), bundle, SOURCE_SHA, 1)
        altered_public_source = ci_source()
        altered_public_source["jobs"][0]["url"] = "https://example.invalid/changed"
        must_reject_validation(
            "public branch CI exact source mismatch",
            lambda: validate_public_branch_ci(
                altered_public_source, bundle, SOURCE_SHA, 1
            ),
        )
        created = create(arguments.tool, bundle)
        if created.returncode != 0:
            raise AssertionError(f"seal create failed\n{created.stdout}\n{created.stderr}")
        seal = json.loads((bundle / "outer-seal.json").read_text(encoding="utf-8"))
        publication = publication_fixture(temporary_root, seal)
        publication_identity = validate_publication(publication, bundle, seal)
        online_identity = dict(publication_identity)
        validate_online_publication_match(online_identity, publication_identity)
        altered_online_identity = dict(online_identity)
        altered_tag_source = json.loads(
            json.dumps(altered_online_identity["tag_ci_source"])
        )
        altered_tag_source["jobs"][0]["completedAt"] = "2026-01-01T00:02:00Z"
        altered_online_identity["tag_ci_source"] = altered_tag_source
        must_reject_validation(
            "live/external exact tag CI source mismatch",
            lambda: validate_online_publication_match(
                altered_online_identity, publication_identity
            ),
        )
        first = invoke(arguments.tool, "verify", "--bundle", str(bundle))
        second = invoke(arguments.tool, "verify", "--bundle", str(bundle))
        if first.returncode != 0 or first.stdout != second.stdout:
            raise AssertionError("seal positive verification differs")
        unavailable_repository = temporary_root / "tag-repository-unavailable"
        LOCAL_REPOSITORY.rename(unavailable_repository)
        offline = invoke(arguments.tool, "verify", "--bundle", str(bundle))
        unavailable_repository.rename(LOCAL_REPOSITORY)
        if offline.returncode != 0 or offline.stdout != first.stdout:
            raise AssertionError("offline seal verification depends on local Git state")
        must_reject("second create", lambda: create(arguments.tool, bundle))

        dirty_tagged_source = fixture(temporary_root, "dirty-tagged-source")
        dirty_document = LOCAL_REPOSITORY / "docs" / min(DOCUMENT_FILES)
        clean_document = dirty_document.read_bytes()
        dirty_document.write_bytes(clean_document + b"dirty worktree mutation\n")
        dirty_created = create(arguments.tool, dirty_tagged_source)
        if dirty_created.returncode != 0:
            raise AssertionError(
                "tagged-source document check depended on dirty checkout\n"
                f"{dirty_created.stdout}\n{dirty_created.stderr}"
            )
        validate_inner_inventory(dirty_tagged_source, LOCAL_REPOSITORY, SOURCE_SHA)
        dirty_bundle = fixture(temporary_root, "dirty-document-bundle")
        (dirty_bundle / "docs" / min(DOCUMENT_FILES)).write_bytes(
            dirty_document.read_bytes()
        )
        must_reject(
            "dirty checkout document differs from tagged blob",
            lambda: create(arguments.tool, dirty_bundle),
        )
        must_reject_inventory(
            "dirty checkout document differs from tagged blob",
            validate_inner_inventory,
            dirty_bundle,
        )
        dirty_document.write_bytes(clean_document)

        missing_tag = fixture(temporary_root, "missing-tag")
        git(LOCAL_REPOSITORY, "tag", "-d", TAG)
        must_reject("missing named evidence tag", lambda: create(arguments.tool, missing_tag))
        TAG_OBJECT = restore_annotated_tag(LOCAL_REPOSITORY, SOURCE_SHA)

        lightweight_tag = fixture(temporary_root, "lightweight-tag")
        git(LOCAL_REPOSITORY, "tag", "-d", TAG)
        git(LOCAL_REPOSITORY, "tag", TAG, SOURCE_SHA)
        must_reject(
            "lightweight evidence tag",
            lambda: create(arguments.tool, lightweight_tag, SOURCE_SHA),
        )
        TAG_OBJECT = restore_annotated_tag(LOCAL_REPOSITORY, SOURCE_SHA)

        wrong_target = fixture(temporary_root, "wrong-tag-target")
        (LOCAL_REPOSITORY / "second.txt").write_text("second commit\n", encoding="utf-8")
        git(LOCAL_REPOSITORY, "add", "second.txt")
        git(LOCAL_REPOSITORY, "commit", "--quiet", "-m", "wrong tag target")
        wrong_sha = git(LOCAL_REPOSITORY, "rev-parse", "HEAD")
        git(LOCAL_REPOSITORY, "tag", "-f", "-a", TAG, "-m", "wrong target", wrong_sha)
        wrong_tag_object = git(LOCAL_REPOSITORY, "rev-parse", f"refs/tags/{TAG}")
        must_reject(
            "annotated tag peels to wrong source",
            lambda: create(arguments.tool, wrong_target, wrong_tag_object),
        )
        TAG_OBJECT = restore_annotated_tag(LOCAL_REPOSITORY, SOURCE_SHA)

        mismatched_tag_object = fixture(temporary_root, "mismatched-tag-object")
        must_reject(
            "supplied tag object differs from named local tag",
            lambda: create(arguments.tool, mismatched_tag_object, "f" * 40),
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

        alternate_outcome = fixture(temporary_root, "alternate-valid-outcome")
        summary_path = alternate_outcome / "oracle" / "oracle-summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["decision"] = (
            "bounded_phase_state_converges_but_required_precision_unresolved"
        )
        summary_path.write_bytes(canonical(summary))
        must_reject(
            "alternate registered outcome",
            lambda: create(arguments.tool, alternate_outcome),
        )

        inconsistent_outcome = fixture(temporary_root, "inconsistent-outcome-gates")
        summary_path = inconsistent_outcome / "oracle" / "oracle-summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["precision_eligibility"]["256"] = True
        summary_path.write_bytes(canonical(summary))
        must_reject(
            "inconsistent completed outcome gates",
            lambda: create(arguments.tool, inconsistent_outcome),
        )

        twins = fixture(temporary_root, "twin-mismatch")
        (twins / "raw-b" / "metadata.csv").write_text("different\n", encoding="utf-8")
        must_reject("raw twin mismatch", lambda: create(arguments.tool, twins))

        missing_raw = fixture(temporary_root, "missing-raw")
        (missing_raw / "raw-a" / min(RAW_FILES)).unlink()
        must_reject("missing raw file", lambda: create(arguments.tool, missing_raw))
        must_reject_inventory(
            "missing raw file", validate_inner_inventory, missing_raw
        )

        extra_raw = fixture(temporary_root, "extra-raw")
        (extra_raw / "raw-a" / "unexpected.csv").write_text(
            "unexpected\n", encoding="utf-8"
        )
        must_reject("extra raw file", lambda: create(arguments.tool, extra_raw))
        must_reject_inventory("extra raw file", validate_inner_inventory, extra_raw)

        empty_raw = fixture(temporary_root, "empty-raw")
        (empty_raw / "raw-a" / min(RAW_FILES)).write_bytes(b"")
        must_reject("empty raw file", lambda: create(arguments.tool, empty_raw))
        must_reject_inventory("empty raw file", validate_inner_inventory, empty_raw)

        nested_raw = fixture(temporary_root, "nested-raw")
        (nested_raw / "raw-a" / "nested").mkdir()
        (nested_raw / "raw-a" / "nested" / "unexpected.csv").write_text(
            "unexpected\n", encoding="utf-8"
        )
        must_reject("nested raw file", lambda: create(arguments.tool, nested_raw))
        must_reject_inventory("nested raw file", validate_inner_inventory, nested_raw)

        empty_raw_directory = fixture(temporary_root, "empty-raw-directory")
        (empty_raw_directory / "raw-a" / "empty").mkdir()
        must_reject(
            "empty nested raw directory",
            lambda: create(arguments.tool, empty_raw_directory),
        )
        must_reject_inventory(
            "empty nested raw directory",
            validate_inner_inventory,
            empty_raw_directory,
        )

        extra = fixture(temporary_root, "extra")
        (extra / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
        must_reject("extra top-level payload", lambda: create(arguments.tool, extra))

        missing_document = fixture(temporary_root, "missing-document")
        (missing_document / "docs" / min(DOCUMENT_FILES)).unlink()
        must_reject("missing document", lambda: create(arguments.tool, missing_document))

        extra_document = fixture(temporary_root, "extra-document")
        (extra_document / "docs" / "unexpected.md").write_text(
            "unexpected\n", encoding="utf-8"
        )
        must_reject("extra document", lambda: create(arguments.tool, extra_document))

        altered_document = fixture(temporary_root, "altered-document")
        document_path = altered_document / "docs" / min(DOCUMENT_FILES)
        document_path.write_bytes(document_path.read_bytes() + b"mutation\n")
        must_reject("non-source document", lambda: create(arguments.tool, altered_document))

        missing_oracle = fixture(temporary_root, "missing-oracle")
        (missing_oracle / "oracle" / "oracle.log").unlink()
        must_reject("missing oracle file", lambda: create(arguments.tool, missing_oracle))

        extra_oracle = fixture(temporary_root, "extra-oracle")
        (extra_oracle / "oracle" / "unexpected.log").write_text(
            "unexpected\n", encoding="utf-8"
        )
        must_reject("extra oracle file", lambda: create(arguments.tool, extra_oracle))

        missing_source = fixture(temporary_root, "missing-source")
        (missing_source / "source" / f"materiallifesubstrate-{SOURCE_SHA}.tar.gz").unlink()
        must_reject("missing source file", lambda: create(arguments.tool, missing_source))

        extra_source = fixture(temporary_root, "extra-source")
        (extra_source / "source" / "unexpected.txt").write_text(
            "unexpected\n", encoding="utf-8"
        )
        must_reject("extra source file", lambda: create(arguments.tool, extra_source))

        missing_receipt = fixture(temporary_root, "missing-receipt")
        (missing_receipt / "receipts" / min(RECEIPT_FILES)).unlink()
        must_reject("missing receipt", lambda: create(arguments.tool, missing_receipt))

        extra_receipt = fixture(temporary_root, "extra-receipt")
        (extra_receipt / "receipts" / "unexpected.log").write_text(
            "unexpected\n", encoding="utf-8"
        )
        must_reject("extra receipt", lambda: create(arguments.tool, extra_receipt))

        empty_receipt = fixture(temporary_root, "empty-receipt")
        (empty_receipt / "receipts" / min(RECEIPT_FILES)).write_bytes(b"")
        must_reject("empty receipt", lambda: create(arguments.tool, empty_receipt))

        ci_source_missing_field = fixture(temporary_root, "ci-source-missing-field")
        ci_path = ci_source_missing_field / "receipts" / "ci-run-source.json"
        ci = json.loads(ci_path.read_text(encoding="utf-8"))
        del ci["workflowName"]
        ci_path.write_bytes(canonical(ci))
        must_reject(
            "CI source missing field",
            lambda: create(arguments.tool, ci_source_missing_field),
        )
        must_reject_validation(
            "CI source missing field",
            lambda: validate_ci_receipt(ci_source_missing_field, SOURCE_SHA, 1),
        )

        ci_source_extra_job_field = fixture(
            temporary_root, "ci-source-extra-job-field"
        )
        ci_path = ci_source_extra_job_field / "receipts" / "ci-run-source.json"
        ci = json.loads(ci_path.read_text(encoding="utf-8"))
        ci["jobs"][0]["unexpected"] = "value"
        ci_path.write_bytes(canonical(ci))
        must_reject(
            "CI source extra job field",
            lambda: create(arguments.tool, ci_source_extra_job_field),
        )
        must_reject_validation(
            "CI source extra job field",
            lambda: validate_ci_receipt(ci_source_extra_job_field, SOURCE_SHA, 1),
        )

        ci_source_wrong_sha = fixture(temporary_root, "ci-source-wrong-sha")
        ci_path = ci_source_wrong_sha / "receipts" / "ci-run-source.json"
        ci = json.loads(ci_path.read_text(encoding="utf-8"))
        ci["headSha"] = "f" * 40
        ci_path.write_bytes(canonical(ci))
        must_reject(
            "CI source wrong SHA", lambda: create(arguments.tool, ci_source_wrong_sha)
        )
        must_reject_validation(
            "CI source wrong SHA",
            lambda: validate_ci_receipt(ci_source_wrong_sha, SOURCE_SHA, 1),
        )

        ci_source_missing_job = fixture(temporary_root, "ci-source-missing-job")
        ci_path = ci_source_missing_job / "receipts" / "ci-run-source.json"
        ci = json.loads(ci_path.read_text(encoding="utf-8"))
        ci["jobs"].pop()
        ci_path.write_bytes(canonical(ci))
        must_reject(
            "CI source missing job",
            lambda: create(arguments.tool, ci_source_missing_job),
        )
        must_reject_validation(
            "CI source missing job",
            lambda: validate_ci_receipt(ci_source_missing_job, SOURCE_SHA, 1),
        )

        ci_normalized_mismatch = fixture(temporary_root, "ci-normalized-mismatch")
        ci_path = ci_normalized_mismatch / "receipts" / "ci-run.json"
        ci = json.loads(ci_path.read_text(encoding="utf-8"))
        ci["run_attempt"] = 2
        ci_path.write_bytes(canonical(ci))
        must_reject(
            "normalized CI differs from source",
            lambda: create(arguments.tool, ci_normalized_mismatch),
        )
        must_reject_validation(
            "normalized CI differs from source",
            lambda: validate_ci_receipt(ci_normalized_mismatch, SOURCE_SHA, 1),
        )

        malformed_attempts = fixture(temporary_root, "malformed-attempts")
        (malformed_attempts / "receipts" / "failed-attempts.json").write_text(
            "{", encoding="utf-8"
        )
        must_reject(
            "malformed failed-attempt receipt",
            lambda: create(arguments.tool, malformed_attempts),
        )

        missing_attempt = fixture(temporary_root, "missing-attempt")
        attempts_path = missing_attempt / "receipts" / "failed-attempts.json"
        attempts = json.loads(attempts_path.read_text(encoding="utf-8"))
        attempts["attempts"].pop()
        attempts_path.write_bytes(canonical(attempts))
        must_reject(
            "missing failed-attempt inventory",
            lambda: create(arguments.tool, missing_attempt),
        )

        reordered_attempts = fixture(temporary_root, "reordered-attempts")
        attempts_path = reordered_attempts / "receipts" / "failed-attempts.json"
        attempts = json.loads(attempts_path.read_text(encoding="utf-8"))
        attempts["attempts"][0], attempts["attempts"][1] = (
            attempts["attempts"][1],
            attempts["attempts"][0],
        )
        attempts_path.write_bytes(canonical(attempts))
        must_reject(
            "reordered failed-attempt inventory",
            lambda: create(arguments.tool, reordered_attempts),
        )

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

        missing_publication_file = publication_fixture(
            temporary_root, seal, "publication-missing-file"
        )
        (missing_publication_file / "public-archive-sha256.log").unlink()
        must_reject_publication(
            "missing external receipt",
            validate_publication,
            missing_publication_file,
            bundle,
            seal,
        )

        extra_publication_file = publication_fixture(
            temporary_root, seal, "publication-extra-file"
        )
        (extra_publication_file / "unexpected.log").write_text(
            "unexpected\n", encoding="utf-8"
        )
        must_reject_publication(
            "extra external receipt",
            validate_publication,
            extra_publication_file,
            bundle,
            seal,
        )

        wrong_tag_object = publication_fixture(
            temporary_root, seal, "publication-wrong-tag-object"
        )
        receipt_path = wrong_tag_object / "tag-ci-run.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["tag_object"] = "f" * 40
        receipt_path.write_bytes(canonical(receipt))
        must_reject_publication(
            "wrong publication tag object",
            validate_publication,
            wrong_tag_object,
            bundle,
            seal,
        )

        tag_source_mismatch = publication_fixture(
            temporary_root, seal, "publication-tag-source-mismatch"
        )
        receipt_path = tag_source_mismatch / "tag-ci-run-source.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["headSha"] = "f" * 40
        receipt_path.write_bytes(canonical(receipt))
        must_reject_publication(
            "wrong publication tag source",
            validate_publication,
            tag_source_mismatch,
            bundle,
            seal,
        )

        extra_release_asset = publication_fixture(
            temporary_root, seal, "publication-extra-release-asset"
        )
        receipt_path = extra_release_asset / "release-source.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["assets"].append(dict(receipt["assets"][0]))
        receipt_path.write_bytes(canonical(receipt))
        must_reject_publication(
            "extra release asset",
            validate_publication,
            extra_release_asset,
            bundle,
            seal,
        )

        archive_digest_mismatch = publication_fixture(
            temporary_root, seal, "publication-archive-digest-mismatch"
        )
        (archive_digest_mismatch / "public-archive-sha256.log").write_text(
            f"{'b' * 64}  bounded-fractional-phase-state-evidence-v1.tar.gz\n",
            encoding="utf-8",
        )
        must_reject_publication(
            "public archive digest mismatch",
            validate_publication,
            archive_digest_mismatch,
            bundle,
            seal,
        )

        false_fresh_pass = publication_fixture(
            temporary_root, seal, "publication-false-fresh-pass"
        )
        receipt_path = false_fresh_pass / "fresh-public-validation.log"
        receipt_path.write_text(
            receipt_path.read_text(encoding="utf-8").replace(
                "fresh_full_validation=PASS", "fresh_full_validation=FAIL"
            ),
            encoding="utf-8",
        )
        must_reject_publication(
            "false fresh validation pass",
            validate_publication,
            false_fresh_pass,
            bundle,
            seal,
        )

        inside_bundle = fixture(temporary_root, "publication-inside-bundle")
        inside_publication = publication_fixture(inside_bundle, seal)
        must_reject_publication(
            "publication directory inside sealed payload",
            validate_publication,
            inside_publication,
            inside_bundle,
            seal,
        )

    print(
        "bounded fractional phase-state outer-seal regression: "
        "PASS (6 deterministic positives, 43 seal, 5 summary, 3 online-CI, "
        "and 8 publication mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
