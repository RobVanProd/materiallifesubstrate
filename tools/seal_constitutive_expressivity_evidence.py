#!/usr/bin/env python3
"""Create or verify the Constitutive Expressivity Lab outer evidence seal.

The numerical bundle has its own closed manifest and independent validator.
This outer seal binds two byte-identical full bundles to the complete committed
source tree, authenticated command receipts, one successful public CI attempt,
and an immutable public tag.  It never promotes mechanics or dynamics.
"""
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
import tempfile
from typing import Any, Iterable


SCHEMA = "mls-constitutive-expressivity-outer-seal-v1"
RECEIPT_SCHEMA = "mls-constitutive-expressivity-command-receipt-v1"
BRANCH = "constitutive-expressivity-lab"
PARENT_SHA = "101296f936f8473effb316b1f9ae4040b5768349"
TAG = "constitutive-expressivity-lab-evidence-v1"
DECISION = "retain_local_collective_relational_energy_for_research"
ORACLE_PRE_HASH = "463fd3f58c5ab5693207ed1a127300434bd76f6d03074f7217fd50e5511ad3d2"
WORKFLOW_NAME = "MLS-0 baseline replication"
SHA1_RE = re.compile(r"[0-9a-f]{40}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")

INHERITED_BLOBS = {
    "include/mls/mechanical_observability_lab.hpp":
        "e5007f63ff4984dd5e6fbbb027a26f319cc02e5c",
    "src/mechanical_observability_lab.cpp":
        "9ed0ab945a4178286c59aad9e8f9fd9eb1ac8c87",
    "src/kelvin_covariance_audit.cpp":
        "bcdad1a3edaf9fbf4528438f720261141333b394",
}
REQUIRED_SOURCE_FILES = {
    ".github/workflows/baseline-replication.yml",
    "CMakeLists.txt",
    "tests/CMakeLists.txt",
    "apps/constitutive_expressivity_diagnostic.cpp",
    "include/mls/constitutive_expressivity_lab.hpp",
    "include/mls/mechanical_observability_lab.hpp",
    "src/constitutive_expressivity_lab.cpp",
    "src/mechanical_observability_lab.cpp",
    "src/kelvin_covariance_audit.cpp",
    "tests/constitutive_expressivity_tests.cpp",
    "tests/constitutive_expressivity_oracle_test.py",
    "tests/constitutive_expressivity_bundle_validator_test.py",
    "tests/constitutive_expressivity_seal_test.py",
    "reference/constitutive_expressivity_oracle.py",
    "reference/validate_constitutive_expressivity_bundle.py",
    "formal/MLSFormal/ConstitutiveExpressivity.lean",
    "formal/MLSFormal/AxiomReport.lean",
    "formal/lakefile.toml",
    "formal/lake-manifest.json",
    "formal/lean-toolchain",
    "docs/constitutive-expressivity-preregistration.md",
    "docs/constitutive-expressivity-evidence-schema.md",
    "docs/constitutive-expressivity-source-audit.md",
    "tools/formal_trust_scan.py",
    "tools/seal_constitutive_expressivity_evidence.py",
}
REQUIRED_CI_JOBS = {
    "C++ / Linux GCC",
    "C++ / Linux Clang",
    "C++ / Windows MSVC",
    "Python exact oracle",
    "Pinned Lean build and axiom output",
}
REQUIRED_RECEIPTS = {
    "configure.json",
    "build.json",
    "ctest.json",
    "producer-a.json",
    "producer-b.json",
    "twin-compare.json",
    "validator.json",
    "validator-regression.json",
    "exact-oracle.json",
    "exact-oracle-regression.json",
    "lean-build.json",
    "lean-axioms.json",
    "formal-trust.json",
    "compiler-versions.json",
}
RECEIPT_FIELDS = {
    "schema", "label", "source_sha", "branch", "cwd", "command",
    "started_at_utc", "ended_at_utc", "exit_code", "output_bytes",
    "output_sha256", "output",
}
PROVENANCE_FIELDS = {
    "repository_url", "branch", "source_sha", "source_tree_sha",
    "accepted_parent_sha", "inherited_blobs", "ci_run_id", "ci_attempt",
    "tag", "decision", "promotion_permitted", "bundle_tree_sha256",
}


class SealError(RuntimeError):
    """Fail-closed seal verification error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SealError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_object_id(kind: str, payload: bytes) -> str:
    header = f"{kind} {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def read_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SealError(f"invalid JSON {path}: {error}") from error
    require(isinstance(value, dict), f"{path} must be a JSON object")
    return value


def run(command: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise SealError(f"{' '.join(command)} failed: {detail}")
    return completed


def git_text(repo: pathlib.Path, *args: str) -> str:
    return run(["git", *args], repo).stdout.decode("utf-8").rstrip("\r\n")


def github_slug(repository_url: str) -> str:
    match = re.fullmatch(
        r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?",
        repository_url,
    )
    require(match is not None, "repository URL must be a public GitHub HTTPS URL")
    return f"{match.group(1)}/{match.group(2)}"


def files_under(root: pathlib.Path, *, omit_outer: bool = False) -> list[pathlib.Path]:
    return sorted(
        path for path in root.rglob("*") if path.is_file()
        and not (omit_outer and path.relative_to(root).as_posix() == "outer-seal.json")
    )


def canonical_tree(root: pathlib.Path) -> dict[str, dict[str, Any]]:
    require(root.is_dir(), f"directory missing: {root}")
    return {
        path.relative_to(root).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in files_under(root)
    }


def tree_digest(tree: dict[str, dict[str, Any]]) -> str:
    return sha256_bytes(json.dumps(
        tree, sort_keys=True, separators=(",", ":")
    ).encode("utf-8"))


def require_twins(first: pathlib.Path, second: pathlib.Path) -> dict[str, dict[str, Any]]:
    require(first.resolve() != second.resolve(), "twin paths must be distinct")
    first_tree = canonical_tree(first)
    second_tree = canonical_tree(second)
    require(first_tree == second_tree, "twin bundle inventories or bytes differ")
    return first_tree


def run_validator(validator: pathlib.Path, first: pathlib.Path,
                  second: pathlib.Path | None = None) -> str:
    command = [sys.executable, str(validator), "--bundle", str(first)]
    if second is not None:
        command += ["--compare", str(second)]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise SealError("independent bundle validator failed:\n" +
                        completed.stdout + completed.stderr)
    return completed.stdout


def validate_bundle_claims(bundle: pathlib.Path, source_sha: str) -> dict[str, Any]:
    summary = read_json(bundle / "summary.json")
    provenance = read_json(bundle / "provenance.json")
    require(summary.get("schema") == "mls.constitutive-expressivity.summary.v1",
            "bundle summary schema mismatch")
    require(summary.get("smoke") is False, "outer seal requires a full bundle")
    require(summary.get("decision") == DECISION, "bundle decision mismatch")
    require(summary.get("no_promotion") is True, "bundle must state NO PROMOTION")
    require(summary.get("candidate_b_decision_inputs") == 0,
            "Candidate B entered the decision")
    require(summary.get("candidate_d_decision_inputs") == 0,
            "Candidate D entered the decision")
    require(summary.get("dense_global_rows") == 0,
            "dense global H entered selectable evidence")
    require(all(summary.get(name) == 0 for name in (
        "bulk_failures", "graph_failures", "metamorphic_failures",
        "checkpoint_failures")), "bundle contains failed gates")
    expected_prohibited = {
        "motion_integration": False,
        "runtime_force_application": False,
        "stress": False,
        "contact": False,
        "damage_or_fracture": False,
        "gravity": False,
        "chemistry": False,
        "organisms": False,
        "rendering": False,
        "gpu": False,
    }
    require(summary.get("prohibited_features") == expected_prohibited,
            "prohibited-scope boundary mismatch")
    require(provenance.get("source_sha") == source_sha,
            "bundle source SHA mismatch")
    require(provenance.get("source_branch") == BRANCH and
            provenance.get("expected_branch") == BRANCH,
            "bundle branch mismatch")
    require(provenance.get("source_dirty") is False,
            "bundle was produced from a dirty source")
    require(provenance.get("parent_sha") == PARENT_SHA,
            "bundle accepted-parent mismatch")
    require(provenance.get("exact_oracle_pre_hash") == ORACLE_PRE_HASH,
            "bundle exact-oracle mismatch")
    require(provenance.get("inherited_blobs") == INHERITED_BLOBS,
            "bundle inherited blob identities mismatch")
    return summary


def parse_ls_tree(repo: pathlib.Path, source_sha: str) -> dict[str, dict[str, str]]:
    payload = run(
        ["git", "ls-tree", "-r", "-z", "--full-tree", source_sha], repo
    ).stdout
    result: dict[str, dict[str, str]] = {}
    for record in payload.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, object_id = metadata.decode("ascii").split()
        path = raw_path.decode("utf-8", errors="surrogateescape")
        require(kind == "blob", f"unsupported source tree entry: {path} ({kind})")
        require(path not in result, f"duplicate source path: {path}")
        result[path] = {"mode": mode, "blob": object_id}
    return result


def reconstructed_git_tree_id(entries: dict[str, dict[str, str]]) -> str:
    """Reconstruct the Git tree object recursively from a flat ls-tree map."""
    root: dict[str, Any] = {}
    for relative, metadata in entries.items():
        parts = relative.split("/")
        require(parts and all(parts), f"invalid Git path: {relative}")
        node = root
        for component in parts[:-1]:
            child = node.setdefault(component, {})
            require(isinstance(child, dict) and "mode" not in child,
                    f"source path/tree collision: {relative}")
            node = child
        require(parts[-1] not in node, f"duplicate Git path: {relative}")
        node[parts[-1]] = metadata

    def encode_tree(node: dict[str, Any]) -> str:
        rows: list[tuple[bytes, bytes]] = []
        for name, value in node.items():
            raw_name = name.encode("utf-8", errors="surrogateescape")
            if isinstance(value, dict) and "mode" not in value:
                object_id = encode_tree(value)
                mode = "40000"
                sort_key = raw_name + b"/"
            else:
                require(isinstance(value, dict) and
                        set(value) == {"mode", "blob"},
                        f"invalid Git entry metadata: {name}")
                object_id = value["blob"]
                mode = value["mode"]
                require(mode in {"100644", "100755", "120000"},
                        f"unsupported Git blob mode: {mode}")
                require(SHA1_RE.fullmatch(object_id) is not None,
                        f"invalid Git blob ID: {name}")
                sort_key = raw_name
            row = mode.encode("ascii") + b" " + raw_name + b"\0" + \
                bytes.fromhex(object_id)
            rows.append((sort_key, row))
        payload = b"".join(row for _key, row in sorted(rows, key=lambda item: item[0]))
        return git_object_id("tree", payload)

    return encode_tree(root)


def validate_repo_source(repo: pathlib.Path, source_sha: str) -> tuple[str, dict[str, dict[str, str]]]:
    require(SHA1_RE.fullmatch(source_sha) is not None, "invalid source SHA")
    require(git_text(repo, "rev-parse", "HEAD") == source_sha,
            "repository HEAD/source SHA mismatch")
    require(git_text(repo, "branch", "--show-current") == BRANCH,
            "source branch mismatch")
    require(git_text(repo, "status", "--porcelain=v1", "--untracked-files=all") == "",
            "repository is dirty")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", PARENT_SHA, source_sha],
        cwd=repo, check=False,
    )
    require(ancestor.returncode == 0, "accepted parent is not an ancestor")
    tree_sha = git_text(repo, "rev-parse", f"{source_sha}^{{tree}}")
    entries = parse_ls_tree(repo, source_sha)
    require(reconstructed_git_tree_id(entries) == tree_sha,
            "complete source inventory does not reconstruct the Git tree")
    require(REQUIRED_SOURCE_FILES <= set(entries),
            f"required source files missing: {sorted(REQUIRED_SOURCE_FILES - set(entries))}")
    for path, expected_blob in INHERITED_BLOBS.items():
        require(entries.get(path, {}).get("blob") == expected_blob,
                f"frozen inherited blob mismatch: {path}")
    return tree_sha, entries


def copy_source_snapshot(repo: pathlib.Path, destination: pathlib.Path,
                         source_sha: str, tree_sha: str,
                         entries: dict[str, dict[str, str]]) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for relative, metadata in sorted(entries.items()):
        payload = run(["git", "cat-file", "blob", metadata["blob"]], repo).stdout
        require(git_object_id("blob", payload) == metadata["blob"],
                f"Git returned wrong blob bytes: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    commit = run(["git", "cat-file", "commit", source_sha], repo).stdout
    require(git_object_id("commit", commit) == source_sha,
            "source commit object reconstruction failed")
    (destination / ".seal-source-tree.json").write_text(json.dumps({
        "schema": "mls-complete-git-source-snapshot-v1",
        "source_sha": source_sha,
        "tree_sha": tree_sha,
        "entries": entries,
        "commit_object_hex": commit.hex(),
    }, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def verify_source_snapshot(snapshot: pathlib.Path, provenance: dict[str, Any]) -> None:
    metadata = read_json(snapshot / ".seal-source-tree.json")
    require(set(metadata) == {
        "schema", "source_sha", "tree_sha", "entries", "commit_object_hex"
    }, "source snapshot metadata fields mismatch")
    require(metadata["schema"] == "mls-complete-git-source-snapshot-v1",
            "source snapshot schema mismatch")
    require(metadata["source_sha"] == provenance["source_sha"] and
            metadata["tree_sha"] == provenance["source_tree_sha"],
            "source snapshot identity mismatch")
    entries = metadata["entries"]
    require(isinstance(entries, dict), "source entries missing")
    actual = {
        path.relative_to(snapshot).as_posix() for path in files_under(snapshot)
        if path.name != ".seal-source-tree.json"
    }
    require(actual == set(entries), "source snapshot inventory mismatch")
    require(REQUIRED_SOURCE_FILES <= actual, "snapshot lacks required sources")
    for relative, item in entries.items():
        require(set(item) == {"mode", "blob"}, f"source metadata fields: {relative}")
        payload = (snapshot / relative).read_bytes()
        require(git_object_id("blob", payload) == item["blob"],
                f"source snapshot blob mismatch: {relative}")
    require(reconstructed_git_tree_id(entries) == provenance["source_tree_sha"],
            "sealed file inventory does not reconstruct the committed Git tree")
    for relative, expected in INHERITED_BLOBS.items():
        require(entries.get(relative, {}).get("blob") == expected,
                f"sealed inherited blob mismatch: {relative}")
    try:
        commit = bytes.fromhex(metadata["commit_object_hex"])
    except (TypeError, ValueError) as error:
        raise SealError("invalid source commit bytes") from error
    require(git_object_id("commit", commit) == provenance["source_sha"],
            "sealed source commit mismatch")
    first_line = commit.splitlines()[0].decode("ascii", errors="strict")
    require(first_line == f"tree {provenance['source_tree_sha']}",
            "source commit/tree binding mismatch")


def validate_receipt(receipt: dict[str, Any], source_sha: str,
                     filename: str) -> str:
    require(set(receipt) == RECEIPT_FIELDS, f"receipt fields mismatch: {filename}")
    require(receipt["schema"] == RECEIPT_SCHEMA, f"receipt schema: {filename}")
    require(receipt["source_sha"] == source_sha and receipt["branch"] == BRANCH,
            f"receipt source binding: {filename}")
    require(type(receipt["exit_code"]) is int and receipt["exit_code"] == 0,
            f"receipt command failed: {filename}")
    require(isinstance(receipt["command"], list) and receipt["command"] and
            all(isinstance(value, str) and value for value in receipt["command"]),
            f"receipt command invalid: {filename}")
    require(isinstance(receipt["output"], str), f"receipt output invalid: {filename}")
    payload = receipt["output"].encode("utf-8")
    require(receipt["output_bytes"] == len(payload) and
            receipt["output_sha256"] == sha256_bytes(payload),
            f"receipt output authentication failed: {filename}")
    require(isinstance(receipt["cwd"], str) and receipt["cwd"],
            f"receipt cwd missing: {filename}")
    require(isinstance(receipt["started_at_utc"], str) and
            isinstance(receipt["ended_at_utc"], str),
            f"receipt timestamps missing: {filename}")
    return receipt["output"]


def require_receipts(logs: pathlib.Path, source_sha: str) -> None:
    actual = {path.name for path in logs.iterdir() if path.is_file()}
    require(actual == REQUIRED_RECEIPTS | {"ci-run.json"},
            f"receipt inventory mismatch: {sorted(actual ^ (REQUIRED_RECEIPTS | {'ci-run.json'}))}")
    receipts = {name: read_json(logs / name) for name in REQUIRED_RECEIPTS}
    outputs = {
        name: validate_receipt(receipt, source_sha, name)
        for name, receipt in receipts.items()
    }
    commands = {name: receipts[name]["command"] for name in receipts}

    def has(name: str, *tokens: str) -> None:
        joined = " ".join(commands[name]).lower()
        require(all(token.lower() in joined for token in tokens),
                f"receipt command mismatch: {name}")

    has("configure.json", "cmake", "-s", "-b")
    has("build.json", "cmake", "--build")
    has("ctest.json", "ctest", "--test-dir")
    has("producer-a.json", "mls_constitutive_expressivity_diagnostic", "--output")
    has("producer-b.json", "mls_constitutive_expressivity_diagnostic", "--output")
    has("twin-compare.json", "--compare")
    has("validator.json", "validate_constitutive_expressivity_bundle.py",
        "--bundle", "--compare")
    has("validator-regression.json",
        "constitutive_expressivity_bundle_validator_test.py")
    has("exact-oracle.json", "constitutive_expressivity_oracle.py", "--verify")
    has("exact-oracle-regression.json", "constitutive_expressivity_oracle_test.py")
    has("lean-build.json", "lake", "--wfail", "build")
    has("lean-axioms.json", "lake", "env", "lean", "axiomreport.lean")
    has("formal-trust.json", "formal_trust_scan.py", "--formal-root")
    has("compiler-versions.json", "version")
    require(commands["producer-a.json"] != commands["producer-b.json"],
            "twin producers did not use distinct output commands")
    require("MLS_WARNINGS_AS_ERRORS=ON" in " ".join(commands["configure.json"]),
            "configure did not enable warnings as errors")
    require("MLS_RUN_EXTENDED_EXACT_TESTS=ON" in " ".join(commands["configure.json"]),
            "configure omitted extended exact tests")
    ctest_command = commands["ctest.json"]
    require("--output-on-failure" in ctest_command,
            "CTest receipt omitted output-on-failure")
    require(not any(flag in ctest_command for flag in ("-R", "-E", "-I", "-L", "-LE")),
            "CTest receipt used a selected subset")
    markers = {
        "configure.json": "Build files have been written",
        "build.json": "mls_constitutive_expressivity_diagnostic",
        "ctest.json": "100% tests passed",
        "producer-a.json": DECISION,
        "producer-b.json": DECISION,
        "twin-compare.json": "PASS",
        "validator.json": "CONSTITUTIVE EXPRESSIVITY BUNDLE VALID",
        "validator-regression.json": "PASS",
        "exact-oracle.json": ORACLE_PRE_HASH,
        "exact-oracle-regression.json": "PASS",
        "lean-build.json": "Build completed successfully",
        "lean-axioms.json": "relationalStiffness_kernel_eq_relationKernel",
        "formal-trust.json": "PASS: no sorry, admit, sorryAx",
        "compiler-versions.json": "source_sha=",
    }
    for name, marker in markers.items():
        require(marker in outputs[name], f"receipt marker absent: {name}")
    all_output = "\n".join(outputs.values()).lower()
    require("0 tests failed" in outputs["ctest.json"].lower(),
            "CTest did not report zero failures")
    require("no promotion" in outputs["producer-a.json"].lower() and
            "no promotion" in outputs["producer-b.json"].lower(),
            "producer receipts omit NO PROMOTION")
    require(not any(token in all_output for token in (
        "sorryax found", "declaration uses 'sorry'", "custom axiom found",
        "tests failed, 0 tests passed")), "receipt output contains a trust failure")


def validate_ci(ci: dict[str, Any], source_sha: str, run_id: str,
                attempt: int) -> None:
    require(str(ci.get("databaseId")) == str(run_id), "CI run ID mismatch")
    require(type(ci.get("attempt")) is int and ci["attempt"] == attempt,
            "CI attempt mismatch")
    require(ci.get("headSha") == source_sha, "CI source SHA mismatch")
    require(ci.get("headBranch") == BRANCH, "CI branch mismatch")
    require(ci.get("workflowName") == WORKFLOW_NAME or ci.get("name") == WORKFLOW_NAME,
            "CI workflow mismatch")
    require(ci.get("status") == "completed" and ci.get("conclusion") == "success",
            "CI was not successful")
    jobs = ci.get("jobs")
    require(isinstance(jobs, list), "CI jobs missing")
    observed: dict[str, str] = {}
    for job in jobs:
        require(isinstance(job, dict), "CI job malformed")
        name = job.get("name")
        if name in REQUIRED_CI_JOBS:
            require(name not in observed, f"duplicate CI job: {name}")
            observed[name] = job.get("conclusion")
    require(set(observed) == REQUIRED_CI_JOBS, "required CI job matrix incomplete")
    require(all(value == "success" for value in observed.values()),
            "required CI job failed")


def fetch_ci_run(repository_url: str, run_id: str, attempt: int) -> dict[str, Any]:
    slug = github_slug(repository_url)
    command = [
        "gh", "run", "view", str(run_id), "--repo", slug,
        "--attempt", str(attempt), "--json",
        "attempt,conclusion,databaseId,headBranch,headSha,jobs,name,status,workflowName,url",
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise SealError("cannot fetch public CI run: " + completed.stderr.strip())
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise SealError("public CI returned invalid JSON") from error
    require(isinstance(value, dict), "public CI result is not an object")
    return value


def parse_remote_refs(output: str, tag: str) -> tuple[str | None, str | None]:
    direct: str | None = None
    peeled: str | None = None
    for line in output.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        if fields[1] == f"refs/tags/{tag}":
            direct = fields[0]
        elif fields[1] == f"refs/tags/{tag}^{{}}":
            peeled = fields[0]
    return direct, peeled


def validate_publication(repository_url: str, tag: str, source_sha: str,
                         *, require_branch: bool) -> None:
    require(tag == TAG, "unexpected evidence tag")
    remote = repository_url[:-4] if repository_url.endswith(".git") else repository_url
    command = [
        "git", "ls-remote", remote + ".git", f"refs/tags/{tag}",
        f"refs/tags/{tag}^{{}}",
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise SealError("cannot resolve public evidence tag")
    direct, peeled = parse_remote_refs(completed.stdout, tag)
    require(direct is not None, "public evidence tag missing")
    require((peeled or direct) == source_sha, "public evidence tag/source mismatch")
    if require_branch:
        branch = subprocess.run(
            ["git", "ls-remote", remote + ".git", f"refs/heads/{BRANCH}"],
            text=True, capture_output=True, check=False,
        )
        require(branch.returncode == 0, "cannot resolve public branch")
        fields = branch.stdout.split()
        require(len(fields) == 2 and fields[0] == source_sha,
                "public branch does not equal source SHA")


def copy_tree_exact(source: pathlib.Path, destination: pathlib.Path) -> None:
    require(source.is_dir(), f"source directory missing: {source}")
    shutil.copytree(source, destination)


def manifest_payload(root: pathlib.Path, provenance: dict[str, Any]) -> dict[str, Any]:
    files = {
        path.relative_to(root).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in files_under(root, omit_outer=True)
    }
    preimage = json.dumps({
        "schema": SCHEMA, "provenance": provenance, "files": files,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "schema": SCHEMA,
        "provenance": provenance,
        "file_count": len(files),
        "files": files,
        "pre_hash_sha256": sha256_bytes(preimage),
    }


def write_manifest(root: pathlib.Path, provenance: dict[str, Any]) -> dict[str, Any]:
    payload = manifest_payload(root, provenance)
    (root / "outer-seal.json").write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def verify_manifest_only(root: pathlib.Path) -> dict[str, Any]:
    observed = read_json(root / "outer-seal.json")
    require(observed.get("schema") == SCHEMA, "outer schema mismatch")
    provenance = observed.get("provenance")
    require(isinstance(provenance, dict), "outer provenance missing")
    expected = manifest_payload(root, provenance)
    require(observed == expected, "outer manifest/hash/archive inventory mismatch")
    return observed


def verify(seal_dir: pathlib.Path, expected_pre_hash: str | None = None,
           *, public: bool = True) -> dict[str, Any]:
    root = seal_dir.resolve()
    manifest = verify_manifest_only(root)
    if expected_pre_hash is not None:
        require(SHA256_RE.fullmatch(expected_pre_hash) is not None and
                manifest["pre_hash_sha256"] == expected_pre_hash,
                "external pre-hash pin mismatch")
    provenance = read_json(root / "provenance.json")
    require(set(provenance) == PROVENANCE_FIELDS, "provenance fields mismatch")
    require(manifest["provenance"] == provenance, "manifest/provenance mismatch")
    require(provenance["branch"] == BRANCH and
            provenance["accepted_parent_sha"] == PARENT_SHA,
            "sealed source lineage mismatch")
    require(provenance["inherited_blobs"] == INHERITED_BLOBS,
            "sealed inherited blobs mismatch")
    require(provenance["decision"] == DECISION and
            provenance["promotion_permitted"] is False,
            "sealed claim boundary mismatch")
    require(provenance["tag"] == TAG, "sealed evidence tag mismatch")
    first = root / "bundles" / "full-a"
    second = root / "bundles" / "full-b"
    twins = require_twins(first, second)
    require(tree_digest(twins) == provenance["bundle_tree_sha256"],
            "bundle tree provenance mismatch")
    validate_bundle_claims(first, provenance["source_sha"])
    validate_bundle_claims(second, provenance["source_sha"])
    validator = root / "source" / "reference" / \
        "validate_constitutive_expressivity_bundle.py"
    run_validator(validator, first, second)
    require_receipts(root / "logs", provenance["source_sha"])
    ci = read_json(root / "logs" / "ci-run.json")
    validate_ci(ci, provenance["source_sha"], provenance["ci_run_id"],
                provenance["ci_attempt"])
    verify_source_snapshot(root / "source", provenance)
    if public:
        remote_ci = fetch_ci_run(
            provenance["repository_url"], provenance["ci_run_id"],
            provenance["ci_attempt"],
        )
        validate_ci(remote_ci, provenance["source_sha"],
                    provenance["ci_run_id"], provenance["ci_attempt"])
        require(remote_ci == ci, "sealed/public CI attempt mismatch")
        validate_publication(provenance["repository_url"], provenance["tag"],
                             provenance["source_sha"], require_branch=False)
    return manifest


def create(args: argparse.Namespace) -> dict[str, Any]:
    repo = args.repo.resolve()
    source_sha = args.source_sha
    tree_sha, entries = validate_repo_source(repo, source_sha)
    first = args.bundle_a.resolve()
    second = args.bundle_b.resolve()
    twins = require_twins(first, second)
    validator = repo / "reference" / "validate_constitutive_expressivity_bundle.py"
    run_validator(validator, first, second)
    validate_bundle_claims(first, source_sha)
    validate_bundle_claims(second, source_sha)
    require_receipts(args.logs.resolve(), source_sha)
    ci = read_json(args.logs.resolve() / "ci-run.json")
    validate_ci(ci, source_sha, args.ci_run_id, args.ci_attempt)
    public_ci = fetch_ci_run(args.repository_url, args.ci_run_id, args.ci_attempt)
    validate_ci(public_ci, source_sha, args.ci_run_id, args.ci_attempt)
    require(public_ci == ci, "local/public CI attempt JSON mismatch")
    validate_publication(args.repository_url, args.tag, source_sha,
                         require_branch=True)
    provenance = {
        "repository_url": args.repository_url,
        "branch": BRANCH,
        "source_sha": source_sha,
        "source_tree_sha": tree_sha,
        "accepted_parent_sha": PARENT_SHA,
        "inherited_blobs": INHERITED_BLOBS,
        "ci_run_id": str(args.ci_run_id),
        "ci_attempt": args.ci_attempt,
        "tag": args.tag,
        "decision": DECISION,
        "promotion_permitted": False,
        "bundle_tree_sha256": tree_digest(twins),
    }
    destination = args.seal_dir.resolve()
    require(not destination.exists(), "seal destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = pathlib.Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.staging-", dir=destination.parent
    ))
    try:
        copy_tree_exact(first, staging / "bundles" / "full-a")
        copy_tree_exact(second, staging / "bundles" / "full-b")
        copy_tree_exact(args.logs.resolve(), staging / "logs")
        copy_source_snapshot(repo, staging / "source", source_sha, tree_sha, entries)
        (staging / "provenance.json").write_text(
            json.dumps(provenance, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest = write_manifest(staging, provenance)
        verify(staging, manifest["pre_hash_sha256"], public=True)
        os.replace(staging, destination)
        return manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    subcommands = result.add_subparsers(dest="command", required=True)
    create_parser = subcommands.add_parser("create")
    create_parser.add_argument("--repo", type=pathlib.Path, required=True)
    create_parser.add_argument("--bundle-a", type=pathlib.Path, required=True)
    create_parser.add_argument("--bundle-b", type=pathlib.Path, required=True)
    create_parser.add_argument("--logs", type=pathlib.Path, required=True)
    create_parser.add_argument("--seal-dir", type=pathlib.Path, required=True)
    create_parser.add_argument("--source-sha", required=True)
    create_parser.add_argument("--ci-run-id", required=True)
    create_parser.add_argument("--ci-attempt", type=int, default=1)
    create_parser.add_argument("--repository-url", required=True)
    create_parser.add_argument("--tag", default=TAG)
    verify_parser = subcommands.add_parser("verify")
    verify_parser.add_argument("--seal-dir", type=pathlib.Path, required=True)
    verify_parser.add_argument("--expected-pre-hash")
    verify_parser.add_argument("--offline", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "create":
            manifest = create(args)
        else:
            manifest = verify(args.seal_dir, args.expected_pre_hash,
                              public=not args.offline)
        print(
            "CONSTITUTIVE EXPRESSIVITY OUTER SEAL VALID: "
            f"{manifest['file_count']} files; "
            f"pre_hash={manifest['pre_hash_sha256']}; NO_PROMOTION"
        )
        return 0
    except (OSError, SealError, subprocess.SubprocessError) as error:
        print(f"CONSTITUTIVE EXPRESSIVITY OUTER SEAL INVALID: {error}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
