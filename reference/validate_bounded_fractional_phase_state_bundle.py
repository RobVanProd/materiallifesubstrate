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
SHA1 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
REQUIRED_JOBS = {
    "C++ / Linux GCC",
    "C++ / Linux Clang",
    "C++ / Windows MSVC",
    "Python exact oracle",
    "Pinned Lean build and axiom output",
}
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


def invoke(
    command: list[str], cwd: Path, timeout: int = 14_400
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


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
        "schema": "mls.bounded-fractional-phase-state.raw.v1",
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
        "force_geometry": "cancellation_resistant_binary64",
        "safe_domain": "2^-24",
        "promotion": "NO_PROMOTION",
    }
    for key, value in expected.items():
        require(metadata.get(key) == value, f"raw metadata differs: {key}")
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
    head = invoke(["git", "rev-parse", "HEAD"], source, timeout=30)
    tree = invoke(["git", "rev-parse", "HEAD^{tree}"], source, timeout=30)
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
            timeout=300,
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


def validate_ci_receipt(bundle: Path, source_sha: str, run_id: int) -> None:
    receipt = read_json(bundle / "receipts" / "ci-run.json")
    expected_fields = {
        "schema",
        "repository",
        "workflow",
        "run_id",
        "run_attempt",
        "head_sha",
        "head_branch",
        "event",
        "conclusion",
        "jobs",
    }
    require(set(receipt) == expected_fields, "CI receipt field inventory differs")
    require(
        receipt["schema"] == "mls.bounded-fractional-phase-state.ci.v1"
        and receipt["repository"] == REPOSITORY
        and receipt["workflow"] == WORKFLOW
        and receipt["run_id"] == run_id
        and type(receipt["run_attempt"]) is int
        and receipt["run_attempt"] >= 1
        and receipt["head_sha"] == source_sha
        and receipt["head_branch"] == BRANCH
        and receipt["event"] == "push"
        and receipt["conclusion"] == "success"
        and isinstance(receipt["jobs"], list),
        "CI receipt identity differs",
    )
    jobs: dict[str, str] = {}
    for item in receipt["jobs"]:
        require(isinstance(item, dict) and set(item) == {"name", "conclusion"}, "CI job schema differs")
        name = item["name"]
        conclusion = item["conclusion"]
        require(isinstance(name, str) and isinstance(conclusion, str) and name not in jobs, "CI job identity differs")
        jobs[name] = conclusion
    require(set(jobs) == REQUIRED_JOBS, "required CI job inventory differs")
    require(all(value == "success" for value in jobs.values()), "required CI job did not succeed")


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
    bundle: Path, source_sha: str, evidence_tag_object: str, source: Path
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
        timeout=120,
    )
    require_success(remote, "public tag lookup")
    tag_object, peeled = parse_remote_tag(remote.stdout)
    require(peeled == source_sha, "public evidence tag/source mismatch")
    require(tag_object == evidence_tag_object, "public evidence tag object mismatch")

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
        timeout=120,
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
    viewed = invoke(
        [
            "gh",
            "run",
            "view",
            str(tag_run_id),
            "--repo",
            REPOSITORY,
            "--json",
            "databaseId,event,headBranch,headSha,status,conclusion,workflowName,jobs",
        ],
        source,
        timeout=120,
    )
    require_success(viewed, "immutable-tag CI inspection")
    run = json.loads(viewed.stdout)
    require(
        isinstance(run, dict)
        and run.get("databaseId") == tag_run_id
        and run.get("event") == "push"
        and run.get("headBranch") == TAG
        and run.get("headSha") == source_sha
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and run.get("workflowName") == WORKFLOW,
        "immutable-tag CI identity differs",
    )
    jobs = run.get("jobs")
    require(isinstance(jobs, list), "immutable-tag CI jobs malformed")
    tag_jobs = {
        item.get("name"): item.get("conclusion")
        for item in jobs
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    require(set(tag_jobs) == REQUIRED_JOBS, "immutable-tag CI job inventory differs")
    require(all(value == "success" for value in tag_jobs.values()), "immutable-tag CI job failed")

    release_result = invoke(
        ["gh", "api", f"repos/{REPOSITORY}/releases/tags/{TAG}"],
        source,
        timeout=120,
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
    assets = [asset for asset in release["assets"] if isinstance(asset, dict) and asset.get("name") == ASSET_NAME]
    require(len(assets) == 1, "public evidence asset inventory differs")
    asset = assets[0]
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
                timeout=1800,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
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
        )
        require_success(verified, "fresh public outer seal")
    return {
        "tag_object": tag_object,
        "tag_ci_run_id": tag_run_id,
        "archive_bytes": asset["size"],
        "archive_sha256": archive_sha256,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run-mutations", action="store_true")
    parser.add_argument(
        "--fresh-online",
        action="store_true",
        help="also resolve the annotated tag, successful tag CI, and freshly download the public release asset",
    )
    arguments = parser.parse_args()
    bundle = arguments.bundle.resolve()
    source = arguments.source.resolve()
    try:
        seal = validate_bundle(bundle, source, arguments.run_mutations)
        online: dict[str, object] | None = None
        if arguments.fresh_online:
            online = fresh_online_validation(
                bundle,
                str(seal["source_sha"]),
                str(seal["evidence_tag_object"]),
                source,
            )
        suffix = ""
        if online is not None:
            suffix = (
                f" tag_object={online['tag_object']} tag_ci_run={online['tag_ci_run_id']}"
                f" archive_bytes={online['archive_bytes']} archive_sha256={online['archive_sha256']}"
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
