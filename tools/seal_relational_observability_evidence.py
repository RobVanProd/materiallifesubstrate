#!/usr/bin/env python3
"""Create or verify the immutable Relational Observability outer seal."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys


SCHEMA = "mls-relational-observability-outer-seal-v1"
BRANCH = "relational-observability-confirmation"
WORKFLOW_NAME = "MLS-0 baseline replication"
CI_JSON_FIELDS = {
    "attempt",
    "conclusion",
    "createdAt",
    "databaseId",
    "displayTitle",
    "event",
    "headBranch",
    "headSha",
    "jobs",
    "name",
    "number",
    "startedAt",
    "status",
    "updatedAt",
    "url",
    "workflowDatabaseId",
    "workflowName",
}
REQUIRED_CI_JOBS = {
    "C++ / Linux GCC",
    "C++ / Linux Clang",
    "C++ / Windows MSVC",
    "Python exact oracle",
    "Pinned Lean build and axiom output",
}
SUMMARY_FIELDS = {
    "schema",
    "mode",
    "provisional",
    "sweep_complete",
    "producer",
    "seed",
    "source_sha",
    "parent_sha",
    "accepted_candidate_c_source_sha",
    "branch",
    "dirty",
    "verdict",
    "no_promotion",
    "candidate",
    "candidate_b_decision_input_count",
    "candidate_d_instantiated",
    "inherited_git_blobs",
    "fixture_table_sha256",
    "counts",
    "gate_counts",
    "compiler",
    "direct_svd",
    "pre_hash_sha256",
}
PROVENANCE_FIELDS = {
    "repository_url",
    "branch",
    "source_sha",
    "source_tree_sha",
    "source_git_tree",
    "ci_run_id",
    "tag",
    "verdict",
    "promotion_permitted",
}
ALLOWED_VERDICTS = {
    "stop_inconclusive_or_implementation_failure",
    "reject_central_relational_representation",
    "retain_only_as_mathematically_rigid_numerically_unsafe",
    "retain_central_relational_representation_for_research",
}
INHERITED_GIT_BLOBS = {
    "include/mls/mechanical_observability_lab.hpp":
        "e5007f63ff4984dd5e6fbbb027a26f319cc02e5c",
    "src/mechanical_observability_lab.cpp":
        "9ed0ab945a4178286c59aad9e8f9fd9eb1ac8c87",
    "apps/mechanical_observability_diagnostic.cpp":
        "ca8082460ba9b34264b393cfb43feaccc8583d99",
    "tests/mechanical_observability_tests.cpp":
        "b334c2b43dcd7438403b4c87f72e442dcbaec504",
    "src/kelvin_covariance_audit.cpp":
        "bcdad1a3edaf9fbf4528438f720261141333b394",
}
REQUIRED_LOGS = {
    "build.log",
    "ci-run.json",
    "compiler-versions.txt",
    "configure.log",
    "ctest.log",
    "formal-trust.log",
    "lean-axioms.log",
    "lean-build.log",
    "producer-a.log",
    "producer-b.log",
    "twin-compare.log",
    "validator-regression.log",
    "validator.log",
}
REQUIRED_SOURCE_FILES = {
    ".github/workflows/baseline-replication.yml",
    "CMakeLists.txt",
    "tests/CMakeLists.txt",
    "apps/relational_observability_diagnostic.cpp",
    "apps/mechanical_observability_diagnostic.cpp",
    "include/mls/mechanical_observability_lab.hpp",
    "include/mls/relational_observability_confirmation.hpp",
    "src/kelvin_covariance_audit.cpp",
    "src/mechanical_observability_lab.cpp",
    "src/relational_observability_confirmation.cpp",
    "reference/validate_relational_observability_bundle.py",
    "tests/relational_observability_confirmation_tests.cpp",
    "tests/relational_observability_bundle_validator_test.py",
    "tests/relational_observability_seal_test.py",
    "tests/mechanical_observability_tests.cpp",
    "tests/fixtures/relational_observability_smoke/configurations.csv",
    "tests/fixtures/relational_observability_smoke/packets.csv",
    "tests/fixtures/relational_observability_smoke/relations.csv",
    "formal/MLSFormal/RelationalObservability.lean",
    "formal/MLSFormal/AxiomReport.lean",
    "formal/lakefile.toml",
    "formal/lake-manifest.json",
    "formal/lean-toolchain",
    "docs/relational-observability-confirmation-contract.md",
    "docs/relational-observability-confirmation-preregistration.md",
    "docs/relational-observability-evidence-schema.md",
    "docs/relational-observability-failed-evidence-2026-08-29.md",
    "docs/relational-observability-source-audit.md",
    "tools/formal_trust_scan.py",
    "tools/seal_relational_observability_evidence.py",
}


class SealError(RuntimeError):
    """A fail-closed evidence-seal error."""


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_id(path: pathlib.Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def git_stdout(repo: pathlib.Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise SealError(
            f"git {' '.join(arguments)} failed: {completed.stderr.strip()}"
        )
    return completed.stdout.rstrip("\r\n")


def github_slug(repository_url: str) -> str:
    match = re.fullmatch(
        r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?",
        repository_url,
    )
    if match is None:
        raise SealError("repository URL must be a canonical GitHub HTTPS URL")
    return f"{match.group(1)}/{match.group(2)}"


def normalized_github_url(value: str) -> str:
    return f"https://github.com/{github_slug(value)}"


def ls_remote(repository_url: str, *patterns: str) -> dict[str, str]:
    completed = subprocess.run(
        ["git", "ls-remote", repository_url, *patterns],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise SealError("cannot verify public remote refs: " + completed.stderr.strip())
    result: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 2:
            raise SealError("malformed public remote ref response")
        result[fields[1]] = fields[0]
    return result


def validate_publication(
    repository_url: str, tag: str, source_sha: str,
    repo: pathlib.Path | None = None,
) -> None:
    slug = github_slug(repository_url)
    if re.fullmatch(r"[A-Za-z0-9._-]+", tag) is None:
        raise SealError("evidence tag is not a safe Git ref name")
    if repo is not None:
        origin = git_stdout(repo, "remote", "get-url", "origin")
        if normalized_github_url(origin) != normalized_github_url(repository_url):
            raise SealError("repository URL does not match Git origin")
    refs = ls_remote(
        repository_url,
        f"refs/heads/{BRANCH}",
        f"refs/tags/{tag}",
        f"refs/tags/{tag}^{{}}",
    )
    if refs.get(f"refs/heads/{BRANCH}") != source_sha:
        raise SealError("public branch does not point to source SHA")
    tag_sha = refs.get(f"refs/tags/{tag}^{{}}", refs.get(f"refs/tags/{tag}"))
    if tag_sha != source_sha:
        raise SealError("public evidence tag does not resolve to source SHA")
    completed = subprocess.run(
        ["gh", "repo", "view", slug, "--json", "url,isPrivate"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise SealError("cannot verify public GitHub repository")
    try:
        metadata = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SealError("invalid GitHub repository metadata") from error
    if metadata != {"isPrivate": False, "url": normalized_github_url(repository_url)}:
        raise SealError("repository is private or URL metadata differs")


def fetch_ci_run(repository_url: str, run_id: str) -> dict:
    completed = subprocess.run(
        [
            "gh", "run", "view", str(run_id),
            "--repo", github_slug(repository_url),
            "--json", ",".join(sorted(CI_JSON_FIELDS)),
        ],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise SealError("cannot verify GitHub Actions run: " + completed.stderr.strip())
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SealError("invalid GitHub Actions metadata") from error
    if not isinstance(value, dict):
        raise SealError("GitHub Actions metadata is not an object")
    return value


def validate_repo_source(
    repo: pathlib.Path, source_sha: str
) -> dict[str, dict[str, str]]:
    if git_stdout(repo, "rev-parse", "HEAD") != source_sha:
        raise SealError("repository HEAD does not equal the evidence source SHA")
    if git_stdout(repo, "branch", "--show-current") != BRANCH:
        raise SealError("repository is not on the registered evidence branch")
    if git_stdout(
        repo, "status", "--porcelain=v1", "--untracked-files=all"
    ):
        raise SealError("repository source tree is dirty at seal creation")

    completed = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--full-tree", source_sha],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise SealError(
            "cannot enumerate source commit tree: "
            + completed.stderr.decode("utf-8", errors="replace").strip()
        )
    result: dict[str, dict[str, str]] = {}
    for raw_entry in completed.stdout.split(b"\0"):
        if not raw_entry:
            continue
        if b"\t" not in raw_entry:
            raise SealError("malformed Git tree entry")
        raw_metadata, raw_path = raw_entry.split(b"\t", 1)
        fields = raw_metadata.decode("ascii").split()
        relative = raw_path.decode("utf-8")
        if len(fields) != 3 or fields[1] != "blob":
            raise SealError(f"unsupported non-blob source entry: {relative}")
        expected_blob = fields[2]
        source = repo / relative
        if not source.is_file():
            raise SealError(f"required source file missing: {relative}")
        observed_blob = git_stdout(
            repo, "hash-object", f"--path={relative}", "--", relative
        )
        if observed_blob != expected_blob:
            raise SealError(f"working build input differs from commit: {relative}")
        result[relative] = {"mode": fields[0], "blob": expected_blob}
    if not REQUIRED_SOURCE_FILES.issubset(result):
        missing = sorted(REQUIRED_SOURCE_FILES - set(result))
        raise SealError(f"required evidence sources are absent from commit: {missing}")
    for relative, expected_blob in INHERITED_GIT_BLOBS.items():
        if result.get(relative, {}).get("blob") != expected_blob:
            raise SealError(f"inherited source commit blob mismatch: {relative}")
    return result


def verify_source_snapshot(root: pathlib.Path, expected: object) -> None:
    if not isinstance(expected, dict) or not REQUIRED_SOURCE_FILES.issubset(expected):
        raise SealError("sealed source Git-blob inventory is incomplete")
    actual_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    if actual_files != set(expected):
        raise SealError("sealed source snapshot file inventory mismatch")
    for relative, entry in sorted(expected.items()):
        if (
            not isinstance(entry, dict)
            or set(entry) != {"mode", "blob"}
            or entry.get("mode") not in {"100644", "100755", "120000"}
            or not isinstance(entry.get("blob"), str)
            or len(entry["blob"]) != 40
        ):
            raise SealError(f"invalid sealed Git blob for source file: {relative}")
        path = root / relative
        if not path.is_file() or git_blob_id(path) != entry["blob"]:
            raise SealError(f"sealed source snapshot mismatch: {relative}")


def git_object_id(kind: str, payload: bytes) -> str:
    header = f"{kind} {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def reconstructed_git_tree_id(entries: object) -> str:
    if not isinstance(entries, dict) or not entries:
        raise SealError("source Git tree inventory is empty")
    root: dict[str, object] = {}
    for relative, metadata in entries.items():
        if not isinstance(relative, str) or not isinstance(metadata, dict):
            raise SealError("malformed source Git tree entry")
        path = pathlib.PurePosixPath(relative)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise SealError(f"unsafe source Git tree path: {relative}")
        mode = metadata.get("mode")
        blob = metadata.get("blob")
        if mode not in {"100644", "100755", "120000"} or not isinstance(
            blob, str
        ) or len(blob) != 40:
            raise SealError(f"malformed source Git tree metadata: {relative}")
        node = root
        for part in path.parts[:-1]:
            existing = node.setdefault(part, {})
            if not isinstance(existing, dict):
                raise SealError(f"source tree path collision: {relative}")
            node = existing
        leaf = path.parts[-1]
        if leaf in node:
            raise SealError(f"duplicate source tree path: {relative}")
        node[leaf] = (mode, blob)

    def hash_node(node: dict[str, object]) -> str:
        encoded_entries: list[tuple[bytes, bytes]] = []
        for name, value in node.items():
            raw_name = name.encode("utf-8")
            if b"\0" in raw_name or b"/" in raw_name:
                raise SealError(f"invalid Git tree name: {name}")
            if isinstance(value, dict):
                mode = "40000"
                object_id = hash_node(value)
                sort_key = raw_name + b"/"
            else:
                mode, object_id = value
                sort_key = raw_name
            wire = (
                mode.encode("ascii")
                + b" "
                + raw_name
                + b"\0"
                + bytes.fromhex(object_id)
            )
            encoded_entries.append((sort_key, wire))
        payload = b"".join(
            wire for _key, wire in sorted(encoded_entries, key=lambda item: item[0])
        )
        return git_object_id("tree", payload)

    return hash_node(root)


def committed_object(repo: pathlib.Path, kind: str, object_id: str) -> bytes:
    completed = subprocess.run(
        ["git", "cat-file", kind, object_id],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise SealError(f"cannot read committed {kind} object {object_id}")
    return completed.stdout


def commit_tree_id(commit_payload: bytes) -> str:
    first_line = commit_payload.splitlines()[0] if commit_payload else b""
    if not first_line.startswith(b"tree ") or len(first_line) != 45:
        raise SealError("source commit has no canonical SHA-1 tree header")
    try:
        return first_line[5:].decode("ascii")
    except UnicodeDecodeError as error:
        raise SealError("source commit tree ID is not ASCII") from error


def verify_inherited_git_blobs(root: pathlib.Path) -> None:
    for relative, expected in INHERITED_GIT_BLOBS.items():
        path = root / relative
        if not path.is_file():
            raise SealError(f"inherited source file missing: {relative}")
        observed = git_blob_id(path)
        if observed != expected:
            raise SealError(
                f"inherited source blob mismatch: {relative}: {observed}"
            )


def files_under(root: pathlib.Path, *, omit_manifest: bool = False) -> list[pathlib.Path]:
    return sorted(
        path for path in root.rglob("*") if path.is_file()
        and not (
            omit_manifest
            and path.relative_to(root).as_posix() == "outer-seal.json"
        )
    )


def manifest_payload(root: pathlib.Path, provenance: dict) -> dict:
    files = {
        path.relative_to(root).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in files_under(root, omit_manifest=True)
    }
    preimage = json.dumps(
        {"schema": SCHEMA, "provenance": provenance, "files": files},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "schema": SCHEMA,
        "provenance": provenance,
        "file_count": len(files),
        "files": files,
        "pre_hash_sha256": hashlib.sha256(preimage).hexdigest(),
    }


def write_manifest(root: pathlib.Path, provenance: dict) -> dict:
    payload = manifest_payload(root, provenance)
    (root / "outer-seal.json").write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def read_json(path: pathlib.Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SealError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise SealError(f"{path} must contain a JSON object")
    return value


def verify_manifest_only(root: pathlib.Path) -> dict:
    path = root / "outer-seal.json"
    if not path.is_file():
        raise SealError("missing outer-seal.json")
    observed = read_json(path)
    if observed.get("schema") != SCHEMA:
        raise SealError("outer schema mismatch")
    provenance = observed.get("provenance")
    if not isinstance(provenance, dict):
        raise SealError("outer provenance missing")
    expected = manifest_payload(root, provenance)
    if observed != expected:
        raise SealError("outer manifest/hash/inventory mismatch")
    return observed


def run_validator(
    validator: pathlib.Path, first: pathlib.Path, second: pathlib.Path | None = None
) -> None:
    command = [sys.executable, str(validator), "--bundle", str(first)]
    if second is not None:
        command += ["--compare", str(second)]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if completed.returncode != 0:
        raise SealError(
            "bundle validator failed:\n" + completed.stdout + completed.stderr
        )


def require_log_evidence(
    logs: pathlib.Path, source_sha: str, verdict: str
) -> None:
    observed = {path.name for path in logs.iterdir() if path.is_file()}
    if observed != REQUIRED_LOGS:
        raise SealError(f"log inventory mismatch: {sorted(observed ^ REQUIRED_LOGS)}")
    texts = {
        filename: (logs / filename).read_text(encoding="utf-8", errors="strict")
        for filename in REQUIRED_LOGS
        if filename != "ci-run.json"
    }
    if any(not value or "\0" in value for value in texts.values()):
        raise SealError("execution log is empty or contains NUL")

    configure = texts["configure.log"]
    if not all(
        marker in configure
        for marker in ("Configuring done", "Generating done", "Build files have been written")
    ) or "CMake Error" in configure:
        raise SealError("configure log does not show a clean completion")

    build = texts["build.log"]
    if "mls_relational_observability_diagnostic" not in build or re.search(
        r"(?im)^(?:FAILED:|ninja: (?:error|build stopped)|.*\berror:)", build
    ):
        raise SealError("build log does not show a clean diagnostic build")

    ctest = texts["ctest.log"]
    if re.search(
        r"100% tests passed, 0 tests failed out of [1-9][0-9]*", ctest
    ) is None or any(
        marker in ctest
        for marker in ("The following tests FAILED", "Errors while running CTest")
    ):
        raise SealError("CTest log does not show a complete zero-failure run")

    producer_a = texts["producer-a.log"]
    producer_b = texts["producer-b.log"]
    for label, producer in (("full-a", producer_a), ("full-b", producer_b)):
        if not all(
            marker in producer
            for marker in (
                "Relational Observability evidence written (full)",
                f"Verdict: {verdict}",
                "NO PROMOTION",
                label,
            )
        ) or "failed" in producer.lower():
            raise SealError(f"producer log is not a successful distinct {label} run")
    if producer_a == producer_b:
        raise SealError("twin producer logs are identical")

    twin = texts["twin-compare.log"]
    if "byte comparison: PASS" not in twin or "FAIL" in twin:
        raise SealError("twin comparison did not pass")

    validator = texts["validator.log"]
    if not all(
        marker in validator
        for marker in (
            "RELATIONAL OBSERVABILITY BUNDLE VALID:",
            f"decision={verdict}",
            "byte comparison: PASS",
        )
    ) or "INVALID" in validator:
        raise SealError("independent validator log is not a valid twin result")

    regression = texts["validator-regression.log"]
    if (
        "PASS (18 mutations; direct raw-matrix SVD regression)" not in regression
        or "FAIL" in regression
    ):
        raise SealError("validator mutation regression is incomplete")

    lean_build = texts["lean-build.log"]
    if "Build completed successfully" not in lean_build or re.search(
        r"(?im)^(?:error:|.*declaration uses 'sorry')", lean_build
    ):
        raise SealError("Lean build log does not show kernel success")
    lean_axioms = texts["lean-axioms.log"]
    if not all(
        theorem in lean_axioms
        for theorem in (
            "mechanicallyObservable_vertex_relabel_iff",
            "relationSquaredLength_similarity",
            "relabeledRationalTetraK4_mechanicallyObservable",
        )
    ) or "sorryAx" in lean_axioms:
        raise SealError("Lean theorem/axiom report is incomplete or untrusted")
    formal_trust = texts["formal-trust.log"]
    if (
        "PASS: no sorry, admit, sorryAx, project-defined axiom declaration, or unreported theorem"
        not in formal_trust
        or "FAIL" in formal_trust
    ):
        raise SealError("formal source trust scan did not pass")

    versions = texts["compiler-versions.txt"]
    if not all(
        marker in versions
        for marker in (
            f"source_sha={source_sha}",
            f"source_branch={BRANCH}",
            "cmake version",
            "Python ",
            "Lean ",
        )
    ) or re.search(
        r"(?m)^source_status_begin\r?\nsource_status_end$", versions
    ) is None:
        raise SealError("tool/source version receipt is incomplete or dirty")


def copy_tree_exact(source: pathlib.Path, destination: pathlib.Path) -> None:
    if not source.is_dir():
        raise SealError(f"source directory missing: {source}")
    shutil.copytree(source, destination)


def copy_source_snapshot(
    repo: pathlib.Path,
    destination: pathlib.Path,
    source_git_tree: dict[str, dict[str, str]],
) -> None:
    for relative in sorted(source_git_tree):
        relative_path = pathlib.PurePosixPath(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise SealError(f"unsafe committed source path: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            ["git", "cat-file", "blob", source_git_tree[relative]["blob"]],
            cwd=repo,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            raise SealError(f"cannot read committed source blob: {relative}")
        target.write_bytes(completed.stdout)
        if git_blob_id(target) != source_git_tree[relative]["blob"]:
            raise SealError(f"copied source blob mismatch: {relative}")
    verify_inherited_git_blobs(destination)


def validate_summary(summary: dict, source_sha: str) -> str:
    if set(summary) != SUMMARY_FIELDS:
        raise SealError("bundle summary field inventory mismatch")
    if summary.get("schema") != "mls.relational-observability-confirmation.summary.v1":
        raise SealError("bundle summary schema mismatch")
    if summary.get("source_sha") != source_sha:
        raise SealError("bundle source SHA mismatch")
    if summary.get("branch") != BRANCH or summary.get("dirty") is not False:
        raise SealError("bundle is not a clean confirmation-branch build")
    if summary.get("mode") != "full" or summary.get("provisional") is not False:
        raise SealError("only complete nonprovisional full evidence is sealable")
    if summary.get("sweep_complete") is not True:
        raise SealError("full sweep is incomplete")
    if summary.get("no_promotion") is not True:
        raise SealError("claim boundary is missing")
    if summary.get("candidate_b_decision_input_count") != 0:
        raise SealError("Candidate B leaked into the decision")
    if summary.get("candidate_d_instantiated") is not False:
        raise SealError("Candidate D was instantiated in this bounded run")
    verdict = summary.get("verdict")
    if verdict not in ALLOWED_VERDICTS:
        raise SealError("bundle verdict is not in the preregistered vocabulary")
    return str(verdict)


def validate_ci(
    ci: dict,
    source_sha: str,
    run_id: str,
    repository_url: str | None = None,
) -> None:
    if set(ci) != CI_JSON_FIELDS:
        raise SealError("CI metadata field inventory mismatch")
    if (
        ci.get("headSha") != source_sha
        or ci.get("headBranch") != BRANCH
        or ci.get("conclusion") != "success"
        or ci.get("status") != "completed"
        or ci.get("workflowName") != WORKFLOW_NAME
        or ci.get("event") not in {"push", "workflow_dispatch"}
        or str(ci.get("databaseId")) != str(run_id)
        or not isinstance(ci.get("attempt"), int)
        or ci["attempt"] < 1
    ):
        raise SealError("CI evidence does not certify the registered branch and SHA")
    jobs = ci.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise SealError("CI job inventory is absent")
    job_names: set[str] = set()
    for job in jobs:
        if not isinstance(job, dict):
            raise SealError("CI job metadata is malformed")
        name = job.get("name")
        if not isinstance(name, str) or name in job_names:
            raise SealError("CI job name is absent or duplicated")
        job_names.add(name)
        if job.get("status") != "completed" or job.get("conclusion") != "success":
            raise SealError(f"CI job did not succeed: {name}")
    if not REQUIRED_CI_JOBS.issubset(job_names):
        raise SealError("required compiler/Python/Lean CI matrix is incomplete")
    if repository_url is not None:
        remote = fetch_ci_run(repository_url, run_id)
        if ci != remote:
            raise SealError("stored CI metadata differs from GitHub Actions API")


def validate_twin_paths(first: pathlib.Path, second: pathlib.Path) -> None:
    if first == second:
        raise SealError("twin evidence paths must be distinct")
    try:
        if first.exists() and second.exists() and os.path.samefile(first, second):
            raise SealError("twin evidence paths alias the same directory")
    except OSError as error:
        raise SealError("cannot establish twin evidence path independence") from error


def create(args: argparse.Namespace) -> dict:
    seal_dir = args.seal_dir.resolve()
    if seal_dir.exists() and (not seal_dir.is_dir() or any(seal_dir.iterdir())):
        raise SealError("seal directory must be absent or empty")
    seal_dir.mkdir(parents=True, exist_ok=True)
    repo = args.repo.resolve()
    bundle_a = args.bundle_a.resolve()
    bundle_b = args.bundle_b.resolve()
    validate_twin_paths(bundle_a, bundle_b)
    source_git_tree = validate_repo_source(repo, args.source_sha)
    validate_publication(
        args.repository_url, args.tag, args.source_sha, repo=repo
    )
    source_commit = committed_object(repo, "commit", args.source_sha)
    if git_object_id("commit", source_commit) != args.source_sha:
        raise SealError("source commit object does not match source SHA")
    source_tree_sha = reconstructed_git_tree_id(source_git_tree)
    if commit_tree_id(source_commit) != source_tree_sha:
        raise SealError("committed source inventory does not match commit tree")
    validator = repo / "reference" / "validate_relational_observability_bundle.py"
    run_validator(validator, bundle_a, bundle_b)
    first_summary = read_json(bundle_a / "summary.json")
    second_summary = read_json(bundle_b / "summary.json")
    if first_summary != second_summary:
        raise SealError("twin summaries differ")
    verdict = validate_summary(first_summary, args.source_sha)

    ci = read_json(args.logs / "ci-run.json")
    validate_ci(
        ci, args.source_sha, str(args.ci_run_id), args.repository_url
    )
    require_log_evidence(args.logs, args.source_sha, verdict)

    copy_tree_exact(bundle_a, seal_dir / "bundles" / "full-a")
    copy_tree_exact(bundle_b, seal_dir / "bundles" / "full-b")
    copy_tree_exact(args.logs.resolve(), seal_dir / "logs")
    copy_source_snapshot(repo, seal_dir / "source", source_git_tree)
    (seal_dir / "source-commit.bin").write_bytes(source_commit)
    provenance = {
        "repository_url": args.repository_url,
        "branch": BRANCH,
        "source_sha": args.source_sha,
        "ci_run_id": str(args.ci_run_id),
        "tag": args.tag,
        "verdict": verdict,
        "promotion_permitted": False,
        "source_git_tree": source_git_tree,
        "source_tree_sha": source_tree_sha,
    }
    (seal_dir / "provenance.json").write_text(
        json.dumps(provenance, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return write_manifest(seal_dir, provenance)


def verify(
    seal_dir: pathlib.Path, expected_pre_hash: str | None = None
) -> dict:
    root = seal_dir.resolve()
    manifest = verify_manifest_only(root)
    if (
        expected_pre_hash is not None
        and manifest.get("pre_hash_sha256") != expected_pre_hash
    ):
        raise SealError("outer seal does not match the externally pinned pre-hash")
    provenance = read_json(root / "provenance.json")
    if set(provenance) != PROVENANCE_FIELDS:
        raise SealError("sealed provenance field inventory mismatch")
    verify_inherited_git_blobs(root / "source")
    verify_source_snapshot(root / "source", provenance.get("source_git_tree"))
    source_commit = (root / "source-commit.bin").read_bytes()
    if git_object_id("commit", source_commit) != provenance.get("source_sha"):
        raise SealError("sealed source commit object mismatch")
    reconstructed_tree = reconstructed_git_tree_id(
        provenance.get("source_git_tree")
    )
    if (
        reconstructed_tree != provenance.get("source_tree_sha")
        or commit_tree_id(source_commit) != reconstructed_tree
    ):
        raise SealError("sealed source tree is not bound to source commit")
    if manifest.get("provenance") != provenance:
        raise SealError("manifest/provenance mismatch")
    if provenance.get("branch") != BRANCH:
        raise SealError("sealed branch mismatch")
    if provenance.get("promotion_permitted") is not False:
        raise SealError("invalid promotion claim")
    if provenance.get("verdict") not in ALLOWED_VERDICTS:
        raise SealError("invalid sealed verdict")
    validate_publication(
        str(provenance.get("repository_url")),
        str(provenance.get("tag")),
        str(provenance.get("source_sha")),
    )
    require_log_evidence(
        root / "logs",
        str(provenance.get("source_sha")),
        str(provenance.get("verdict")),
    )
    ci = read_json(root / "logs" / "ci-run.json")
    validate_ci(
        ci,
        str(provenance.get("source_sha")),
        str(provenance.get("ci_run_id")),
        str(provenance.get("repository_url")),
    )
    validator = (
        root / "source" / "reference" / "validate_relational_observability_bundle.py"
    )
    run_validator(
        validator, root / "bundles" / "full-a", root / "bundles" / "full-b"
    )
    for bundle in ("full-a", "full-b"):
        summary = read_json(root / "bundles" / bundle / "summary.json")
        verdict = validate_summary(summary, str(provenance.get("source_sha")))
        if verdict != provenance.get("verdict"):
            raise SealError("sealed verdict mismatch")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--repo", type=pathlib.Path, required=True)
    create_parser.add_argument("--bundle-a", type=pathlib.Path, required=True)
    create_parser.add_argument("--bundle-b", type=pathlib.Path, required=True)
    create_parser.add_argument("--logs", type=pathlib.Path, required=True)
    create_parser.add_argument("--seal-dir", type=pathlib.Path, required=True)
    create_parser.add_argument("--source-sha", required=True)
    create_parser.add_argument("--ci-run-id", required=True)
    create_parser.add_argument("--repository-url", required=True)
    create_parser.add_argument("--tag", required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--seal-dir", type=pathlib.Path, required=True)
    verify_parser.add_argument("--expected-pre-hash")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "create":
            payload = create(args)
            print(json.dumps(payload, sort_keys=True, indent=2))
        else:
            payload = verify(args.seal_dir, args.expected_pre_hash)
            print(json.dumps(payload, sort_keys=True, indent=2))
    except SealError as error:
        print(f"relational observability seal rejected: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
