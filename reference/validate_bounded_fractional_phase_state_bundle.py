#!/usr/bin/env python3
"""Fresh verifier for sealed Bounded Fractional Phase-State Lab evidence."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


BRANCH = "bounded-fractional-phase-state-lab"
TAG = "bounded-fractional-phase-state-lab-evidence-v1"
REPOSITORY = "RobVanProd/materiallifesubstrate"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
WORKFLOW = "Bounded Fractional Phase-State Lab"
WORKFLOW_FILE = "bounded-fractional-phase-state-lab.yml"
RELEASE_NAME = "Bounded Fractional Phase-State Lab evidence v1"
ASSET_NAME = "bounded-fractional-phase-state-evidence-v1.tar.gz"
ARCHIVE_ROOT = "bounded-fractional-phase-state-evidence-v1"
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
# Canonical path/byte/SHA-256 inventory of the complete downloaded accepted
# parent directory, including its own outer seal and nested-parent outer seal.
PARENT_BUNDLE_TREE_SHA256 = (
    "cb97734e81e202b24bf39d126483fcb346cd18bbf976c05e0299b53024674404"
)
PARENT_BUNDLE_FILES = 165
PARENT_BUNDLE_BYTES = 124_976_741
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
REQUIRED_JOBS = {
    "C++ / Linux GCC",
    "C++ / Linux Clang",
    "C++ / Windows MSVC",
    "Python exact oracle",
    "Pinned Lean build and axiom output",
}
# Explicit subprocess budgets keep fresh verification diagnosable and below the
# six-hour GitHub-hosted job ceiling.  The exact oracle is intentionally given
# most of that budget; mutations and seal checks have independent bounds.
GIT_OBJECT_TIMEOUT_SECONDS = 30
SHORT_COMMAND_TIMEOUT_SECONDS = 120
SOURCE_ARCHIVE_TIMEOUT_SECONDS = 300
SEAL_VERIFY_TIMEOUT_SECONDS = 600
ORACLE_REPLAY_TIMEOUT_SECONDS = 16_200
SEMANTIC_MUTATION_TIMEOUT_SECONDS = 1_800
SEAL_MUTATION_TIMEOUT_SECONDS = 600
PUBLIC_DOWNLOAD_TIMEOUT_SECONDS = 1_800
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
TAG_CI_SCHEMA = "mls.bounded-fractional-phase-state.tag-ci.v1"
RELEASE_SOURCE_SCHEMA = "mls.bounded-fractional-phase-state.release-source.v1"
FRESH_PUBLIC_SCHEMA = "mls.bounded-fractional-phase-state.fresh-public-validation.v1"
PUBLICATION_RECEIPT_FILES = frozenset(
    {
        "tag-ci-run-source.json",
        "tag-ci-run.json",
        "release-source.json",
        "public-archive-sha256.log",
        "fresh-public-validation.log",
    }
)
RELEASE_SOURCE_FIELDS = frozenset(
    {"schema", "repository", "tag_name", "name", "draft", "prerelease", "assets"}
)
RELEASE_ASSET_FIELDS = frozenset({"id", "name", "size", "state", "digest"})
FRESH_PUBLIC_FIELDS = frozenset(
    {
        "schema",
        "repository",
        "source_sha",
        "tag",
        "tag_object",
        "tag_ci_run_id",
        "tag_ci_run_attempt",
        "release_name",
        "asset_id",
        "asset_name",
        "archive_bytes",
        "archive_sha256",
        "outer_pre_hash",
        "decision",
        "selected_precision",
        "promotion",
        "fresh_download",
        "fresh_archive_digest",
        "fresh_bundle_identity",
        "fresh_outer_seal",
        "fresh_full_validation",
    }
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
    (
        "branch-ci-oracle-timeout-33830169828",
        "506ee4b692b38041479a5781823f3c637483e50c",
    ),
)
ORACLE_FIELDS = {
    "schema",
    "precision_decimal_digits",
    "source_sha",
    "parent_fingerprint",
    "positive_control",
    "oracle_refinement_errors",
    "canonical_states",
    "short_replay",
    "representation_and_temporal",
    "composition_contracts",
    "long_run",
    "state_size",
    "precision_eligibility",
    "highest_precision_dynamics_pass",
    "structure_residuals_resolved",
    "selected_precision",
    "decision",
    "promotion",
    "raw_files",
}
MAX_PUBLIC_EXPANDED_BYTES = 20 * 1024 * 1024 * 1024


def raw_vector_fields(prefixes: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        field
        for prefix in prefixes
        for field in (f"{prefix}_raw_{axis}_dyadic" for axis in "xyz")
    )


INVARIANT_FIELDS = (
    "trajectory_id", "precision", "level", "step", "stage", "state_hash",
    *raw_vector_fields(("momentum", "angular")),
)
FORCE_FIELDS = (
    "trajectory_id", "precision", "level", "step", "stage", "relation_index",
    "first_id", "second_id", "length_bits", "conjugate_bits",
    "causal_offset_raw_hash", "exact_stored_offset_raw_hash",
    "ideal_impulse_raw_hash", "first_actual_impulse_raw_hash",
    "second_actual_impulse_raw_hash",
    *raw_vector_fields((
        "pair_momentum_residual", "stored_impulse_centrality_residual",
        "first_actual_centrality_residual", "second_actual_centrality_residual",
        "relation_angular_residual",
    )),
)
REPRESENTATION_ERROR_FIELDS = (
    "scenario_id", "scope", "path", "precision", "level", "dt_raw", "sample",
    "candidate_state_hash", "control_state_hash", "exact_errors_sha256",
    "position_raw_error_display", "momentum_raw_error_display", "energy_error_display",
)


def invoke(
    command: list[str], cwd: Path, *, timeout_seconds: int, label: str,
    stream_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    require(timeout_seconds > 0, f"{label} timeout must be positive")
    print(
        f"[bounded-phase validator] START {label} "
        f"(timeout={timeout_seconds}s)",
        flush=True,
    )
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=not stream_output,
            text=True,
            timeout=timeout_seconds,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"{label} timed out after {timeout_seconds} seconds"
        ) from error
    print(
        f"[bounded-phase validator] COMPLETE {label} "
        f"(returncode={completed.returncode})",
        flush=True,
    )
    return completed


def read_git_blob(repository: Path, object_specification: str) -> bytes:
    label = f"tagged source document: {object_specification}"
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository), "cat-file", "blob", object_specification],
            cwd=repository,
            check=False,
            capture_output=True,
            timeout=GIT_OBJECT_TIMEOUT_SECONDS,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"{label} timed out after {GIT_OBJECT_TIMEOUT_SECONDS} seconds"
        ) from error
    require_success(completed, label)
    return completed.stdout


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def require_success(completed: subprocess.CompletedProcess[Any], label: str) -> None:
    if completed.returncode != 0:
        stdout = completed.stdout
        stderr = completed.stderr
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"{label} failed\nstdout:\n{stdout}\nstderr:\n{stderr}")


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def read_key_value_log(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        require(line and "=" in line, f"malformed key/value receipt line: {path.name}")
        key, value = line.split("=", 1)
        require(key and value and key not in result, f"malformed key/value receipt: {path.name}")
        result[key] = value
    require(result, f"empty key/value receipt: {path.name}")
    return result


def read_metadata(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames == ["key", "value"], "raw metadata schema differs")
        for row in reader:
            require(set(row) == {"key", "value"}, "raw metadata row differs")
            require(row["key"] not in result, "duplicate raw metadata key")
            result[row["key"]] = row["value"]
    return result


def csv_header(path: Path) -> tuple[str, ...]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.reader(stream)
        try:
            return tuple(next(reader))
        except StopIteration as error:
            raise RuntimeError(f"empty raw CSV: {path.name}") from error


def tree_inventory(root: Path) -> list[dict[str, object]]:
    require(root.is_dir() and not root.is_symlink(), f"real directory required: {root}")
    entries: list[dict[str, object]] = []
    folded: set[str] = set()
    for directory, directory_names, file_names in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in sorted((*directory_names, *file_names)):
            path = base / name
            relative = path.relative_to(root).as_posix()
            require(
                relative and not relative.startswith("/") and "\\" not in relative,
                f"unsafe evidence path: {relative!r}",
            )
            require(
                all(part not in {"", ".", ".."} for part in Path(relative).parts),
                f"unsafe evidence path: {relative!r}",
            )
            require(relative.casefold() not in folded, f"case-colliding path: {relative}")
            folded.add(relative.casefold())
            require(not path.is_symlink(), f"symlink forbidden: {relative}")
            require(path.is_dir() or path.is_file(), f"unsupported object: {relative}")
            if path.is_file():
                entries.append(
                    {
                        "path": relative,
                        "bytes": path.stat().st_size,
                        "sha256": sha256(path),
                    }
                )
    entries.sort(key=lambda item: str(item["path"]))
    return entries


def tree_hash(entries: list[dict[str, object]]) -> str:
    return hashlib.sha256(canonical(entries)).hexdigest()


def compare_directories(first: Path, second: Path, label: str) -> None:
    require(tree_inventory(first) == tree_inventory(second), f"{label} differs")


def require_flat_inventory(
    directory: Path, expected: frozenset[str], label: str
) -> None:
    entries = list(directory.iterdir())
    require(
        all(path.is_file() and not path.is_symlink() for path in entries),
        f"{label} must contain only regular files",
    )
    actual = {path.name for path in entries}
    require(
        actual == expected,
        f"{label} file inventory differs: {sorted(actual ^ expected)}",
    )
    empty = sorted(path.name for path in entries if path.stat().st_size == 0)
    require(not empty, f"{label} files must be nonempty: {empty}")


def validate_failed_attempts(path: Path) -> None:
    value = read_json(path)
    require(
        set(value) == {"schema", "attempts"}
        and value["schema"] == FAILED_ATTEMPTS_SCHEMA,
        "failed-attempt receipt schema differs",
    )
    attempts = value["attempts"]
    require(
        isinstance(attempts, list) and len(attempts) == len(FAILED_ATTEMPTS),
        "failed-attempt receipt inventory differs",
    )
    fields = {
        "id",
        "source_sha",
        "stage",
        "outcome",
        "scientific_disposition",
        "preservation",
    }
    for item, (expected_id, expected_sha) in zip(attempts, FAILED_ATTEMPTS):
        require(isinstance(item, dict) and set(item) == fields,
                "failed-attempt item schema differs")
        require(
            item["id"] == expected_id and item["source_sha"] == expected_sha,
            "failed-attempt identity or order differs",
        )
        require(item["scientific_disposition"] is None,
                "failed attempt has a scientific disposition")
        require(
            all(
                isinstance(item[field], str) and bool(item[field])
                for field in ("stage", "outcome", "preservation")
            ),
            "failed-attempt descriptive field is empty",
        )


def validate_inner_payload_inventory(
    bundle: Path, source: Path, source_sha: str
) -> None:
    """Validate the complete closed pre-publication payload inventory.

    Tag-CI, release, public-archive, and fresh-download receipts necessarily
    postdate the seal and therefore remain external to this closed inventory.
    """

    require_flat_inventory(bundle / "raw-a", RAW_FILES, "raw-a")
    require_flat_inventory(bundle / "raw-b", RAW_FILES, "raw-b")
    require_flat_inventory(bundle / "docs", DOCUMENT_FILES, "document")
    require_flat_inventory(bundle / "oracle", ORACLE_FILES, "oracle")
    require_flat_inventory(bundle / "receipts", RECEIPT_FILES, "receipt")
    validate_failed_attempts(bundle / "receipts" / "failed-attempts.json")
    require_flat_inventory(
        bundle / "source",
        frozenset(
            {
                "source-identity.json",
                f"materiallifesubstrate-{source_sha}.tar.gz",
            }
        ),
        "source",
    )
    for name in DOCUMENT_FILES:
        bundled_document = bundle / "docs" / name
        require(
            bundled_document.read_bytes()
            == read_git_blob(source, f"{source_sha}:docs/{name}"),
            f"bundled document is not an exact source copy: {name}",
        )


def validate_decision(decision: object, selected: object) -> tuple[str, int | None]:
    require(isinstance(decision, str) and decision in DECISIONS, "decision is unregistered")
    if decision == RETAIN_DECISION:
        require(type(selected) is int and selected in PRECISIONS, "retained precision differs")
    else:
        require(selected is None, "non-retained decision has a selected precision")
    return decision, selected  # type: ignore[return-value]


def validate_raw_identity(bundle: Path, source_sha: str) -> None:
    compare_directories(bundle / "raw-a", bundle / "raw-b", "raw twins")
    metadata = read_metadata(bundle / "raw-a" / "metadata.csv")
    expected = {
        "schema": "mls.bounded-fractional-phase-state.raw.v2",
        "accepted_parent_sha": PARENT_SHA,
        "accepted_parent_tag": PARENT_TAG,
        "accepted_parent_tag_object": PARENT_TAG_OBJECT,
        "accepted_parent_archive_sha256": PARENT_ARCHIVE_SHA256,
        "accepted_parent_archive_size": str(PARENT_ARCHIVE_BYTES),
        "source_sha": source_sha,
        "configured_source_branch": BRANCH,
        "source_dirty": "false",
        "branch": BRANCH,
        "candidate": "fixed_precision_variable_exponent_binary_phase_state",
        "gmpy2_version": "2.3.1",
        "mpfr_version": "MPFR 4.2.2",
        "rounding": "round_to_nearest_ties_to_even",
        "leading_exponent_range": "[-16382,16383]",
        "mpfr_context_emin": "-16381",
        "mpfr_context_emax": "16384",
        "subnormalization": "false",
        "adaptive_precision": "false",
        "hidden_residual_or_history": "false",
        "causal_state_shape": (
            "State(precision,time_raw,packets);"
            "Packet(identifier,mass_raw,x[3],p[3]);slots_only_v1"
        ),
        "causal_state_shape_sha256": hashlib.sha256(
            (
                "State(precision,time_raw,packets);"
                "Packet(identifier,mass_raw,x[3],p[3]);slots_only_v1"
            ).encode("utf-8")
        ).hexdigest(),
        "causal_state_slots_only": "true",
        "force_geometry": "cancellation_resistant_binary64",
        "safe_domain": "2^-24",
        "exact_comparator_maximum_component_bits": "262144",
        "exact_comparator_median_component_bits": "131072",
        "exact_comparator_maximum_checkpoint_bytes": "8388608",
        "domain_scratch_bit_limit_formula": (
            "4*(B+(leading_exponent_max-leading_exponent_min))+64"
        ),
        "observer_event_encoding": "length_framed_utf8_fields_then_sha256_v2",
        "observer_stream_encoding": "step_framed_ordered_event_sha256_v2",
        "representation_error_commitment_encoding": (
            "identified_exact_fraction_triplet_sha256_v2"
        ),
        "representation_error_display": (
            "nonauthoritative_rn_even_binary64_significand_max_32_bytes"
        ),
        "promotion": "NO_PROMOTION",
    }
    require(set(metadata) == set(expected), "raw metadata key inventory differs")
    for key, value in expected.items():
        require(metadata.get(key) == value, f"raw metadata differs: {key}")
    for raw_name in ("raw-a", "raw-b"):
        raw = bundle / raw_name
        for filename, fields in (
            ("invariants.csv", INVARIANT_FIELDS),
            ("force_audit.csv", FORCE_FIELDS),
            ("representation_error.csv", REPRESENTATION_ERROR_FIELDS),
        ):
            require(csv_header(raw / filename) == fields,
                    f"{raw_name}/{filename}: compact-v2 header differs")
    with (bundle / "raw-a" / "precisions.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    require([int(row["precision"]) for row in rows] == list(PRECISIONS), "precision inventory differs")
    require(
        [int(row["complete_packet_bytes"]) for row in rows] == [94, 118, 142, 190, 238],
        "fixed packet sizes differ",
    )


def validate_source_identity(bundle: Path, source: Path, seal: dict[str, object]) -> None:
    identity = read_json(bundle / "source" / "source-identity.json")
    expected_fields = {
        "schema",
        "repository",
        "branch",
        "source_sha",
        "tree_sha",
        "archive",
        "archive_bytes",
        "archive_sha256",
    }
    require(set(identity) == expected_fields, "source identity field inventory differs")
    source_sha = seal["source_sha"]
    source_tree_sha = seal["source_tree_sha"]
    archive_name = f"materiallifesubstrate-{source_sha}.tar.gz"
    require(
        identity["schema"] == "mls.bounded-fractional-phase-state.source.v1"
        and identity["repository"] == REPOSITORY
        and identity["branch"] == BRANCH
        and identity["source_sha"] == source_sha
        and identity["tree_sha"] == source_tree_sha
        and identity["archive"] == archive_name
        and type(identity["archive_bytes"]) is int
        and identity["archive_bytes"] > 0
        and isinstance(identity["archive_sha256"], str)
        and SHA256.fullmatch(identity["archive_sha256"]) is not None,
        "source identity differs",
    )
    archive = bundle / "source" / archive_name
    require(
        archive.is_file()
        and archive.stat().st_size == identity["archive_bytes"]
        and sha256(archive) == identity["archive_sha256"],
        "source archive identity differs",
    )
    head = invoke(
        ["git", "rev-parse", "HEAD"], source,
        timeout_seconds=GIT_OBJECT_TIMEOUT_SECONDS,
        label="source Git HEAD",
    )
    tree = invoke(
        ["git", "rev-parse", "HEAD^{tree}"], source,
        timeout_seconds=GIT_OBJECT_TIMEOUT_SECONDS,
        label="source Git tree",
    )
    require_success(head, "source Git HEAD")
    require_success(tree, "source Git tree")
    require(head.stdout.strip() == source_sha, "verifier source HEAD differs")
    require(tree.stdout.strip() == source_tree_sha, "verifier source tree differs")
    with tempfile.TemporaryDirectory(prefix="mls-bounded-source-") as temporary:
        expected_tar = Path(temporary) / "expected.tar"
        stored_tar = Path(temporary) / "stored.tar"
        archived = invoke(
            [
                "git",
                "archive",
                "--format=tar",
                f"--prefix=materiallifesubstrate-{source_sha}/",
                "-o",
                str(expected_tar),
                source_sha,
            ],
            source,
            timeout_seconds=SOURCE_ARCHIVE_TIMEOUT_SECONDS,
            label="fresh source tree archive",
        )
        require_success(archived, "fresh source tree archive")
        expected_bytes = expected_tar.stat().st_size
        written = 0
        with gzip.open(archive, "rb") as input_stream, stored_tar.open("xb") as output_stream:
            while True:
                block = input_stream.read(1024 * 1024)
                if not block:
                    break
                written += len(block)
                require(written <= expected_bytes, "source archive expands beyond sealed Git tree")
                output_stream.write(block)
        require(
            written == expected_bytes
            and sha256(expected_tar) == sha256(stored_tar),
            "source archive does not materialize the sealed Git tree",
        )


def validate_ci_source(
    source: dict[str, object], source_sha: str, run_id: int, branch: str,
) -> list[dict[str, str]]:
    require(set(source) == CI_SOURCE_FIELDS, "CI source field inventory differs")
    require(
        type(source["attempt"]) is int
        and source["attempt"] >= 1
        and type(source["databaseId"]) is int
        and source["databaseId"] == run_id
        and source["event"] == "push"
        and source["headBranch"] == branch
        and source["headSha"] == source_sha
        and source["status"] == "completed"
        and source["conclusion"] == "success"
        and source["workflowName"] == WORKFLOW
        and isinstance(source["jobs"], list),
        "CI source identity differs",
    )
    observed: dict[str, str] = {}
    for job in source["jobs"]:
        require(
            isinstance(job, dict) and set(job) == CI_JOB_FIELDS,
            "CI source job schema differs",
        )
        name = job["name"]
        require(
            isinstance(name, str)
            and bool(name)
            and name not in observed
            and type(job["databaseId"]) is int
            and job["databaseId"] > 0
            and job["status"] == "completed"
            and job["conclusion"] == "success"
            and isinstance(job["startedAt"], str)
            and bool(job["startedAt"])
            and isinstance(job["completedAt"], str)
            and bool(job["completedAt"])
            and isinstance(job["url"], str)
            and bool(job["url"])
            and isinstance(job["steps"], list)
            and bool(job["steps"]),
            "CI source job identity differs",
        )
        step_numbers: set[int] = set()
        for step in job["steps"]:
            require(
                isinstance(step, dict) and set(step) == CI_STEP_FIELDS,
                "CI source step schema differs",
            )
            number = step["number"]
            require(
                type(number) is int
                and number > 0
                and number not in step_numbers
                and isinstance(step["name"], str)
                and bool(step["name"])
                and isinstance(step["status"], str)
                and bool(step["status"])
                and isinstance(step["conclusion"], str)
                and bool(step["conclusion"])
                and isinstance(step["startedAt"], str)
                and bool(step["startedAt"])
                and isinstance(step["completedAt"], str)
                and bool(step["completedAt"]),
                "CI source step identity differs",
            )
            step_numbers.add(number)
        observed[name] = str(job["conclusion"])
    require(set(observed) == REQUIRED_JOBS, "CI source job inventory differs")
    return [
        {"name": name, "conclusion": observed[name]}
        for name in sorted(observed)
    ]


def validate_ci_receipt(bundle: Path, source_sha: str, run_id: int) -> None:
    source = read_json(bundle / "receipts" / "ci-run-source.json")
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
    require(
        read_json(bundle / "receipts" / "ci-run.json") == expected,
        "normalized CI receipt differs from exact source",
    )


def validate_public_branch_ci(
    public_source: dict[str, object], bundle: Path, source_sha: str, run_id: int
) -> None:
    validate_ci_source(public_source, source_sha, run_id, BRANCH)
    require(
        public_source == read_json(bundle / "receipts" / "ci-run-source.json"),
        "public branch CI differs from sealed exact source receipt",
    )


def validate_publication_receipts(
    directory: Path, bundle: Path, seal: dict[str, object]
) -> dict[str, object]:
    publication = directory.resolve(strict=True)
    bundle_root = bundle.resolve(strict=True)
    require(
        not publication.is_relative_to(bundle_root),
        "publication receipts must remain outside the sealed payload",
    )
    require_flat_inventory(
        publication, PUBLICATION_RECEIPT_FILES, "external publication receipt"
    )
    source_sha = seal["source_sha"]
    tag_object = seal["evidence_tag_object"]
    require(
        isinstance(source_sha, str)
        and SHA1.fullmatch(source_sha) is not None
        and isinstance(tag_object, str)
        and SHA1.fullmatch(tag_object) is not None,
        "sealed publication identity malformed",
    )

    tag_source = read_json(publication / "tag-ci-run-source.json")
    tag_run_id = tag_source.get("databaseId")
    require(type(tag_run_id) is int and tag_run_id > 0, "tag CI run ID malformed")
    tag_jobs = validate_ci_source(tag_source, source_sha, tag_run_id, TAG)
    expected_tag_ci: dict[str, object] = {
        "schema": TAG_CI_SCHEMA,
        "repository": REPOSITORY,
        "workflow": WORKFLOW,
        "run_id": tag_run_id,
        "run_attempt": tag_source["attempt"],
        "head_sha": source_sha,
        "head_branch": TAG,
        "event": "push",
        "conclusion": "success",
        "jobs": tag_jobs,
        "tag": TAG,
        "tag_object": tag_object,
    }
    require(
        read_json(publication / "tag-ci-run.json") == expected_tag_ci,
        "normalized tag CI receipt differs from exact source",
    )

    release = read_json(publication / "release-source.json")
    require(set(release) == RELEASE_SOURCE_FIELDS, "release source field inventory differs")
    assets = release.get("assets")
    require(
        release["schema"] == RELEASE_SOURCE_SCHEMA
        and release["repository"] == REPOSITORY
        and release["tag_name"] == TAG
        and release["name"] == RELEASE_NAME
        and release["draft"] is False
        and release["prerelease"] is False
        and isinstance(assets, list)
        and len(assets) == 1,
        "release source identity differs",
    )
    asset = assets[0]
    require(
        isinstance(asset, dict) and set(asset) == RELEASE_ASSET_FIELDS,
        "release asset field inventory differs",
    )
    digest = asset["digest"]
    require(
        type(asset["id"]) is int
        and asset["id"] > 0
        and asset["name"] == ASSET_NAME
        and type(asset["size"]) is int
        and asset["size"] > 0
        and asset["state"] == "uploaded"
        and isinstance(digest, str)
        and digest.startswith("sha256:")
        and SHA256.fullmatch(digest.removeprefix("sha256:")) is not None,
        "release asset identity differs",
    )
    archive_sha256 = digest.removeprefix("sha256:")
    expected_digest_log = f"{archive_sha256}  {ASSET_NAME}\n".encode("utf-8")
    require(
        (publication / "public-archive-sha256.log").read_bytes()
        == expected_digest_log,
        "public archive digest receipt differs",
    )

    fresh = read_key_value_log(publication / "fresh-public-validation.log")
    selected_precision = seal["selected_precision"]
    expected_fresh = {
        "schema": FRESH_PUBLIC_SCHEMA,
        "repository": REPOSITORY,
        "source_sha": source_sha,
        "tag": TAG,
        "tag_object": tag_object,
        "tag_ci_run_id": str(tag_run_id),
        "tag_ci_run_attempt": str(tag_source["attempt"]),
        "release_name": RELEASE_NAME,
        "asset_id": str(asset["id"]),
        "asset_name": ASSET_NAME,
        "archive_bytes": str(asset["size"]),
        "archive_sha256": archive_sha256,
        "outer_pre_hash": str(seal["outer_pre_hash"]),
        "decision": str(seal["decision"]),
        "selected_precision": (
            "null" if selected_precision is None else str(selected_precision)
        ),
        "promotion": "NO_PROMOTION",
        "fresh_download": "PASS",
        "fresh_archive_digest": "PASS",
        "fresh_bundle_identity": "PASS",
        "fresh_outer_seal": "PASS",
        "fresh_full_validation": "PASS",
    }
    require(set(fresh) == FRESH_PUBLIC_FIELDS, "fresh-public field inventory differs")
    require(fresh == expected_fresh, "fresh-public receipt identity differs")
    return {
        "tag_ci_run_id": tag_run_id,
        "tag_ci_run_attempt": tag_source["attempt"],
        "tag_ci_source": tag_source,
        "archive_bytes": asset["size"],
        "archive_sha256": archive_sha256,
        "asset_id": asset["id"],
    }


def validate_online_publication_match(
    online: dict[str, object], publication: dict[str, object]
) -> None:
    for key in (
        "tag_ci_run_id",
        "tag_ci_run_attempt",
        "asset_id",
        "archive_bytes",
        "archive_sha256",
    ):
        require(
            online[key] == publication[key],
            f"online/publication receipt mismatch: {key}",
        )
    require(
        online["tag_ci_source"] == publication["tag_ci_source"],
        "live tag CI differs from external exact source receipt",
    )


def validate_parent(bundle: Path, source: Path) -> None:
    parent = bundle / "parent-explicit-fractional"
    completed = invoke(
        [
            sys.executable,
            str(source / "tools" / "seal_explicit_fractional_phase_state_evidence.py"),
            "verify",
            "--bundle",
            str(parent),
        ],
        source,
        timeout_seconds=SEAL_VERIFY_TIMEOUT_SECONDS,
        label="nested parent outer seal",
    )
    require_success(completed, "nested parent outer seal")
    seal = read_json(parent / "outer-seal.json")
    require(
        seal.get("source_sha") == PARENT_SHA
        and seal.get("tag") == PARENT_TAG
        and seal.get("decision") == PARENT_DECISION
        and seal.get("outer_pre_hash") == PARENT_OUTER_PRE_HASH
        and seal.get("promotion") == "NO_PROMOTION",
        "nested parent scientific identity differs",
    )
    inventory = tree_inventory(parent)
    require(len(inventory) == PARENT_BUNDLE_FILES, "nested parent file count differs")
    require(sum(int(item["bytes"]) for item in inventory) == PARENT_BUNDLE_BYTES, "nested parent byte count differs")
    require(tree_hash(inventory) == PARENT_BUNDLE_TREE_SHA256, "nested parent complete tree differs")


def validate_summary(summary: dict[str, object], seal: dict[str, object]) -> None:
    require(set(summary) == ORACLE_FIELDS, "oracle summary field inventory differs")
    require(
        summary["schema"] == "mls.bounded-fractional-phase-state.oracle.v1"
        and summary["precision_decimal_digits"] == 110
        and summary["source_sha"] == seal["source_sha"]
        and summary["promotion"] == "NO_PROMOTION",
        "oracle summary identity differs",
    )
    decision, selected = validate_decision(summary["decision"], summary["selected_precision"])
    require(
        decision == seal["decision"] and selected == seal["selected_precision"],
        "oracle/outer disposition differs",
    )
    highest = summary["highest_precision_dynamics_pass"]
    structure = summary["structure_residuals_resolved"]
    eligibility = summary["precision_eligibility"]
    require(
        isinstance(eligibility, dict)
        and set(eligibility) == {str(precision) for precision in PRECISIONS}
        and all(type(value) is bool for value in eligibility.values()),
        "oracle precision eligibility profile malformed",
    )
    composition = summary["composition_contracts"]
    long_run = summary["long_run"]
    require(
        isinstance(composition, dict)
        and composition.get("all_qualitative_gates_converge") is structure,
        "oracle structure aggregate differs",
    )
    require(
        isinstance(long_run, dict)
        and type(long_run.get("all_required_full_tail_anchors_qualified")) is bool
        and composition.get("all_required_full_tail_anchors_qualified")
        is long_run["all_required_full_tail_anchors_qualified"],
        "oracle full-tail anchor aggregate differs",
    )
    if decision != "stop_inconclusive_or_wrong_parent":
        require(type(highest) is bool and type(structure) is bool, "oracle disposition gates malformed")
    if decision == "reject_bounded_binary_fractional_phase_state":
        require(highest is False, "rejection contradicts highest-precision dynamics gate")
    elif decision == "bounded_phase_state_restores_dynamics_but_structure_residuals_unresolved":
        require(highest is True and structure is False, "structure disposition gates differ")
    elif decision in {
        "bounded_phase_state_converges_but_required_precision_unresolved",
        RETAIN_DECISION,
    }:
        require(highest is True and structure is True, "converged disposition gates differ")
    if decision == RETAIN_DECISION:
        eligible = [
            precision for precision in PRECISIONS if eligibility[str(precision)]
        ]
        require(bool(eligible) and selected == eligible[0], "retained precision is not the smallest eligible precision")
    elif decision != "stop_inconclusive_or_wrong_parent":
        require(not any(eligibility.values()), "negative disposition has an eligible precision")
    require(
        (decision, selected) == (FINAL_DECISION, FINAL_SELECTED_PRECISION),
        "oracle disposition differs from the completed lab outcome",
    )


def validate_bundle(bundle: Path, source: Path, run_mutations: bool) -> dict[str, object]:
    seal_result = invoke(
        [
            sys.executable,
            str(source / "tools" / "seal_bounded_fractional_phase_state_evidence.py"),
            "verify",
            "--bundle",
            str(bundle),
        ],
        source,
        timeout_seconds=SEAL_VERIFY_TIMEOUT_SECONDS,
        label="outer seal",
    )
    require_success(seal_result, "outer seal")
    seal = read_json(bundle / "outer-seal.json")
    source_sha = seal.get("source_sha")
    run_id = seal.get("ci_run_id")
    require(isinstance(source_sha, str) and SHA1.fullmatch(source_sha) is not None, "outer source SHA malformed")
    require(type(run_id) is int and run_id > 0, "outer CI run ID malformed")
    validate_decision(seal.get("decision"), seal.get("selected_precision"))
    validate_raw_identity(bundle, source_sha)
    validate_source_identity(bundle, source, seal)
    validate_inner_payload_inventory(bundle, source, source_sha)
    validate_ci_receipt(bundle, source_sha, run_id)
    validate_parent(bundle, source)
    with tempfile.TemporaryDirectory(prefix="mls-bounded-phase-verify-") as temporary:
        output = Path(temporary) / "oracle-summary.json"
        oracle = invoke(
            [
                sys.executable,
                str(source / "reference" / "bounded_fractional_phase_state_oracle.py"),
                "--raw",
                str(bundle / "raw-a"),
                "--parent-raw",
                str(bundle / "parent-explicit-fractional" / "raw-a"),
                "--output",
                str(output),
            ],
            source,
            timeout_seconds=ORACLE_REPLAY_TIMEOUT_SECONDS,
            label="independent exact-dyadic and 110-digit oracle",
            stream_output=True,
        )
        require_success(oracle, "independent exact-dyadic and 110-digit oracle")
        require(
            output.read_bytes() == (bundle / "oracle" / "oracle-summary.json").read_bytes(),
            "fresh oracle JSON differs",
        )
        validate_summary(read_json(output), seal)
    if run_mutations:
        semantic = invoke(
            [
                sys.executable,
                str(source / "tests" / "bounded_fractional_phase_state_oracle_test.py"),
                "--raw",
                str(bundle / "raw-a"),
                "--parent-raw",
                str(bundle / "parent-explicit-fractional" / "raw-a"),
            ],
            source,
            timeout_seconds=SEMANTIC_MUTATION_TIMEOUT_SECONDS,
            label="semantic mutation regression",
            stream_output=True,
        )
        require_success(semantic, "semantic mutation regression")
        outer = invoke(
            [
                sys.executable,
                str(source / "tests" / "bounded_fractional_phase_state_seal_test.py"),
                "--tool",
                str(source / "tools" / "seal_bounded_fractional_phase_state_evidence.py"),
            ],
            source,
            timeout_seconds=SEAL_MUTATION_TIMEOUT_SECONDS,
            label="outer-seal mutation regression",
            stream_output=True,
        )
        require_success(outer, "outer-seal mutation regression")
    return seal


def parse_remote_tag(output: str) -> tuple[str, str]:
    direct: str | None = None
    peeled: str | None = None
    for line in output.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        if fields[1] == f"refs/tags/{TAG}":
            direct = fields[0]
        elif fields[1] == f"refs/tags/{TAG}^{{}}":
            peeled = fields[0]
    require(direct is not None and SHA1.fullmatch(direct) is not None, "public annotated tag object missing")
    require(peeled is not None and SHA1.fullmatch(peeled) is not None, "public annotated tag peel missing")
    require(direct != peeled, "public evidence tag is not annotated")
    return direct, peeled


def fetch_public_ci_run(
    run_id: int,
    source_sha: str,
    branch: str,
    source: Path,
    label: str,
) -> dict[str, object]:
    completed = invoke(
        [
            "gh",
            "run",
            "view",
            str(run_id),
            "--repo",
            REPOSITORY,
            "--json",
            "attempt,conclusion,databaseId,event,headBranch,headSha,jobs,status,workflowName",
        ],
        source,
        timeout_seconds=SHORT_COMMAND_TIMEOUT_SECONDS,
        label=label,
    )
    require_success(completed, label)
    value = json.loads(completed.stdout)
    require(isinstance(value, dict), f"{label} result malformed")
    validate_ci_source(value, source_sha, run_id, branch)
    return value


def safe_extract_public_archive(archive_path: Path, destination: Path) -> Path:
    seen: set[str] = set()
    folded: set[str] = set()
    expanded = 0
    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = archive.getmembers()
        require(members, "public archive is empty")
        for member in members:
            name = member.name.rstrip("/")
            pure = PurePosixPath(name)
            require(
                name
                and not pure.is_absolute()
                and "\\" not in name
                and all(part not in {"", ".", ".."} for part in pure.parts),
                f"unsafe public archive path: {member.name!r}",
            )
            require(name not in seen, f"duplicate public archive path: {name}")
            require(name.casefold() not in folded, f"case-colliding public archive path: {name}")
            seen.add(name)
            folded.add(name.casefold())
            require(pure.parts[0] == ARCHIVE_ROOT, "public archive root differs")
            require(member.isdir() or member.isreg(), f"unsupported public archive object: {name}")
            require(member.size >= 0, f"negative public archive size: {name}")
            expanded += member.size
            require(expanded <= MAX_PUBLIC_EXPANDED_BYTES, "public archive expansion limit exceeded")
        for member in members:
            name = member.name.rstrip("/")
            target = destination.joinpath(*PurePosixPath(name).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=False)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            require(source is not None, f"cannot read public archive member: {name}")
            written = 0
            with target.open("xb") as output:
                while True:
                    block = source.read(1024 * 1024)
                    if not block:
                        break
                    output.write(block)
                    written += len(block)
            require(written == member.size, f"public archive member size differs: {name}")
    root = destination / ARCHIVE_ROOT
    require(root.is_dir(), "public archive evidence root missing")
    require({path.name for path in destination.iterdir()} == {ARCHIVE_ROOT}, "public archive has extra roots")
    return root


def fresh_online_validation(
    bundle: Path,
    source_sha: str,
    evidence_tag_object: str,
    branch_run_id: int,
    source: Path,
) -> dict[str, object]:
    remote = invoke(
        [
            "git",
            "ls-remote",
            f"{REPOSITORY_URL}.git",
            f"refs/tags/{TAG}",
            f"refs/tags/{TAG}^{{}}",
        ],
        source,
        timeout_seconds=SHORT_COMMAND_TIMEOUT_SECONDS,
        label="public tag lookup",
    )
    require_success(remote, "public tag lookup")
    tag_object, peeled = parse_remote_tag(remote.stdout)
    require(peeled == source_sha, "public evidence tag/source mismatch")
    require(tag_object == evidence_tag_object, "public evidence tag object mismatch")

    branch_run = fetch_public_ci_run(
        branch_run_id,
        source_sha,
        BRANCH,
        source,
        "sealed branch CI inspection",
    )
    validate_public_branch_ci(branch_run, bundle, source_sha, branch_run_id)

    listed = invoke(
        [
            "gh",
            "run",
            "list",
            "--repo",
            REPOSITORY,
            "--workflow",
            WORKFLOW_FILE,
            "--branch",
            TAG,
            "--event",
            "push",
            "--limit",
            "20",
            "--json",
            "databaseId,event,headBranch,headSha,status,conclusion,workflowName",
        ],
        source,
        timeout_seconds=SHORT_COMMAND_TIMEOUT_SECONDS,
        label="immutable-tag CI lookup",
    )
    require_success(listed, "immutable-tag CI lookup")
    runs = json.loads(listed.stdout)
    require(isinstance(runs, list), "immutable-tag CI result malformed")
    matching = [
        run
        for run in runs
        if isinstance(run, dict)
        and run.get("event") == "push"
        and run.get("headBranch") == TAG
        and run.get("headSha") == source_sha
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and run.get("workflowName") == WORKFLOW
        and type(run.get("databaseId")) is int
    ]
    require(matching, "successful immutable-tag CI run missing")
    tag_run_id = max(int(run["databaseId"]) for run in matching)
    tag_run = fetch_public_ci_run(
        tag_run_id,
        source_sha,
        TAG,
        source,
        "immutable-tag CI inspection",
    )

    release_result = invoke(
        ["gh", "api", f"repos/{REPOSITORY}/releases/tags/{TAG}"],
        source,
        timeout_seconds=SHORT_COMMAND_TIMEOUT_SECONDS,
        label="public release lookup",
    )
    require_success(release_result, "public release lookup")
    release = json.loads(release_result.stdout)
    require(
        isinstance(release, dict)
        and release.get("tag_name") == TAG
        and release.get("name") == RELEASE_NAME
        and release.get("draft") is False
        and release.get("prerelease") is False
        and isinstance(release.get("assets"), list),
        "public release identity differs",
    )
    require(len(release["assets"]) == 1, "public release must contain exactly one asset")
    asset = release["assets"][0]
    require(
        isinstance(asset, dict) and asset.get("name") == ASSET_NAME,
        "public evidence asset inventory differs",
    )
    digest = asset.get("digest")
    require(
        type(asset.get("id")) is int
        and type(asset.get("size")) is int
        and asset["size"] > 0
        and asset.get("state") == "uploaded"
        and isinstance(digest, str)
        and digest.startswith("sha256:")
        and SHA256.fullmatch(digest.removeprefix("sha256:")) is not None,
        "public evidence asset metadata differs",
    )
    with tempfile.TemporaryDirectory(prefix="mls-bounded-phase-public-") as temporary:
        temporary_root = Path(temporary)
        archive_path = temporary_root / ASSET_NAME
        with archive_path.open("xb") as output_stream:
            try:
                download = subprocess.run(
                    [
                        "gh",
                        "api",
                        "--method",
                        "GET",
                        "-H",
                        "Accept: application/octet-stream",
                        f"repos/{REPOSITORY}/releases/assets/{asset['id']}",
                    ],
                    cwd=source,
                    check=False,
                    stdout=output_stream,
                    stderr=subprocess.PIPE,
                    timeout=PUBLIC_DOWNLOAD_TIMEOUT_SECONDS,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
            except subprocess.TimeoutExpired as error:
                raise RuntimeError(
                    "fresh public evidence download timed out after "
                    f"{PUBLIC_DOWNLOAD_TIMEOUT_SECONDS} seconds"
                ) from error
        if download.returncode != 0:
            raise RuntimeError(
                "fresh public evidence download failed\nstderr:\n"
                + download.stderr.decode("utf-8", errors="replace")
            )
        archive_sha256 = sha256(archive_path)
        require(archive_path.stat().st_size == asset["size"], "fresh public archive size differs")
        require(archive_sha256 == digest.removeprefix("sha256:"), "fresh public archive digest differs")
        extract_root = temporary_root / "extracted"
        extract_root.mkdir()
        downloaded = safe_extract_public_archive(archive_path, extract_root)
        compare_directories(bundle, downloaded, "fresh public downloaded evidence")
        verified = invoke(
            [
                sys.executable,
                str(source / "tools" / "seal_bounded_fractional_phase_state_evidence.py"),
                "verify",
                "--bundle",
                str(downloaded),
            ],
            source,
            timeout_seconds=SEAL_VERIFY_TIMEOUT_SECONDS,
            label="fresh public outer seal",
        )
        require_success(verified, "fresh public outer seal")
    return {
        "tag_object": tag_object,
        "branch_ci_run_id": branch_run_id,
        "tag_ci_run_id": tag_run_id,
        "tag_ci_run_attempt": tag_run["attempt"],
        "tag_ci_source": tag_run,
        "asset_id": asset["id"],
        "archive_bytes": asset["size"],
        "archive_sha256": archive_sha256,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run-mutations", action="store_true")
    parser.add_argument(
        "--publication-receipts",
        type=Path,
        help="also validate the exact five-file local post-seal receipt directory",
    )
    parser.add_argument(
        "--fresh-online",
        action="store_true",
        help="also authenticate branch/tag CI, resolve the annotated tag, and freshly download the sole public release asset",
    )
    arguments = parser.parse_args()
    bundle = arguments.bundle.resolve()
    source = arguments.source.resolve()
    try:
        seal = validate_bundle(bundle, source, arguments.run_mutations)
        publication: dict[str, object] | None = None
        if arguments.publication_receipts is not None:
            publication = validate_publication_receipts(
                arguments.publication_receipts, bundle, seal
            )
        online: dict[str, object] | None = None
        if arguments.fresh_online:
            online = fresh_online_validation(
                bundle,
                str(seal["source_sha"]),
                str(seal["evidence_tag_object"]),
                int(seal["ci_run_id"]),
                source,
            )
        if online is not None and publication is not None:
            validate_online_publication_match(online, publication)
        suffix = ""
        if online is not None:
            suffix = (
                f" tag_object={online['tag_object']} branch_ci_run={online['branch_ci_run_id']}"
                f" tag_ci_run={online['tag_ci_run_id']}"
                f" archive_bytes={online['archive_bytes']} archive_sha256={online['archive_sha256']}"
            )
        elif publication is not None:
            suffix = (
                f" publication_tag_ci_run={publication['tag_ci_run_id']}"
                f" archive_bytes={publication['archive_bytes']}"
                f" archive_sha256={publication['archive_sha256']}"
            )
        print(
            "BOUNDED FRACTIONAL PHASE STATE EVIDENCE VALID: "
            f"source={seal['source_sha']} files={len(seal['payload'])} "
            f"prehash={seal['outer_pre_hash']} decision={seal['decision']} "
            f"selected_precision={seal['selected_precision']} NO_PROMOTION{suffix}"
        )
        return 0
    except (
        OSError,
        EOFError,
        ValueError,
        RuntimeError,
        csv.Error,
        json.JSONDecodeError,
        tarfile.TarError,
        subprocess.TimeoutExpired,
    ) as error:
        print(f"BOUNDED FRACTIONAL PHASE STATE EVIDENCE INVALID: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
