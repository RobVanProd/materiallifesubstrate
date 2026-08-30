#!/usr/bin/env python3
"""Create or verify the Constitutive Expressivity Lab outer evidence seal.

The numerical bundle has its own closed manifest and independent validator.
This outer seal binds two byte-identical full bundles to the complete committed
source tree, integrity-bound command receipts, one successful public CI
attempt, and an immutable public tag.  A receipt preserves argv, output, and
their relationships; it does not authenticate operating-system execution.
The seal never promotes mechanics or dynamics.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import ntpath
import os
import pathlib
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterable


SCHEMA = "mls-constitutive-expressivity-outer-seal-v1"
RECEIPT_SCHEMA = "mls-constitutive-expressivity-command-receipt-v1"
RECEIPT_BINDINGS_SCHEMA = \
    "mls-constitutive-expressivity-receipt-path-bindings-v1"
BRANCH = "constitutive-expressivity-lab"
PARENT_SHA = "101296f936f8473effb316b1f9ae4040b5768349"
TAG = "constitutive-expressivity-lab-evidence-v1"
DECISION = "retain_local_collective_relational_energy_for_research"
NO_PROMOTION = "NO_PROMOTION"
ORACLE_PRE_HASH = "010d1452010d534445e63b2acfb83374a92b1958e6a62afbf240a8f3121e36bf"
SELECTED_SUBSET_SHA256 = {
    "mode": "accepted_parent_subset",
    "configurations.csv": "45d162381ec723dd9ce744f2cc23c4d21435a52b7c7e60a182073ee19a08d60e",
    "packets.csv": "843c9cb22c0b55e07c207135125a8334b0dd170a0f708aa1fb50f34d4c5d7363",
    "relations.csv": "0b2e21dcbf26454af316bec9323627aa1488ebc7aa1f14c006bfb41a231e0e6f",
}
WORKFLOW_NAME = "MLS-0 baseline replication"
CI_FIELDS = {
    "attempt", "conclusion", "databaseId", "headBranch", "headSha", "jobs",
    "name", "status", "workflowName", "url",
}
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
    "tests/constitutive_expressivity_oracle.canonical.json",
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
    "docs/constitutive-expressivity-lab-contract.md",
    "docs/constitutive-expressivity-evidence-schema.md",
    "docs/constitutive-expressivity-source-audit.md",
    "tools/formal_trust_scan.py",
    "tools/derive_constitutive_parent_subset.py",
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
    "parent-subset.json",
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
    "receipt_path_bindings",
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
    require(summary.get("pair_control_rows") == 2 and
            summary.get("pair_control_failures") == 0,
            "pair-separable control failed or inventory changed")
    require(summary.get("collective_bulk_rows") == 8 and
            summary.get("collective_bulk_failures") == 0,
            "collective bulk inventory failed or changed")
    require(isinstance(summary.get("basis_vector_rows"), int) and
            summary.get("basis_vector_rows") > 0,
            "basis-vector evidence missing")
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
    require(provenance.get("selected_subset_sha256") == SELECTED_SUBSET_SHA256,
            "bundle selected accepted-parent subset mismatch")
    for name in ("configurations.csv", "packets.csv", "relations.csv"):
        require(sha256(bundle / name) == SELECTED_SUBSET_SHA256[name],
                f"bundle selected subset payload mismatch: {name}")
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
    require(receipt["label"] == pathlib.Path(filename).stem,
            f"receipt label/filename mismatch: {filename}")
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
            f"receipt output integrity mismatch: {filename}")
    require(isinstance(receipt["cwd"], str) and receipt["cwd"],
            f"receipt cwd missing: {filename}")
    require(isinstance(receipt["started_at_utc"], str) and
            isinstance(receipt["ended_at_utc"], str),
            f"receipt timestamps missing: {filename}")
    return receipt["output"]


def portable_basename(value: str) -> str:
    """Return an argv token's basename without trusting host path semantics."""
    return value.replace("\\", "/").rsplit("/", 1)[-1].lower()


def executable_is(command: list[str], expected: str) -> bool:
    observed = portable_basename(command[0])
    wanted = expected.lower()
    return observed == wanted or observed == wanted + ".exe"


def require_script(command: list[str], expected: str, filename: str) -> None:
    require(any(portable_basename(token) == expected.lower() for token in command),
            f"receipt script mismatch: {filename}")


def exact_option(command: list[str], flag: str, filename: str) -> str:
    """Read one exact two-token option; joined strings never satisfy a flag."""
    positions = [index for index, token in enumerate(command) if token == flag]
    require(len(positions) == 1, f"receipt must contain one {flag}: {filename}")
    index = positions[0]
    require(index + 1 < len(command) and command[index + 1] and
            not command[index + 1].startswith("-"),
            f"receipt {flag} value missing: {filename}")
    return command[index + 1]


def require_exact_flag(command: list[str], flag: str, filename: str) -> None:
    require(sum(token == flag for token in command) == 1,
            f"receipt must contain one exact {flag}: {filename}")


def canonical_recorded_path(value: str, cwd: str) -> str:
    """Lexically resolve a receipt path on Windows or POSIX, even offline.

    This deliberately does not touch the filesystem.  The create path compares
    the result with resolved live inputs; offline verification only checks the
    path relationships preserved in the receipts and provenance.
    """
    windows = bool(re.match(r"^(?:[A-Za-z]:[\\/]|\\\\)", value)) or \
        bool(re.match(r"^(?:[A-Za-z]:[\\/]|\\\\)", cwd))
    if windows:
        candidate = value if ntpath.isabs(value) else ntpath.join(cwd, value)
        return "windows:" + ntpath.normcase(ntpath.normpath(candidate))
    candidate = value if posixpath.isabs(value) else posixpath.join(cwd, value)
    return "posix:" + posixpath.normpath(candidate)


def command_path(receipt: dict[str, Any], flag: str, filename: str) -> str:
    raw = exact_option(receipt["command"], flag, filename)
    return canonical_recorded_path(raw, receipt["cwd"])


def receipt_path_bindings(
    receipts: dict[str, dict[str, Any]],
    *,
    expected_repo: pathlib.Path | None = None,
    expected_bundle_a: pathlib.Path | None = None,
    expected_bundle_b: pathlib.Path | None = None,
    expected_parent_bundle: pathlib.Path | None = None,
) -> dict[str, Any]:
    """Validate exact argv relationships and return their sealed path binding.

    Expected live paths are resolved once by ``create`` before they reach this
    function.  Do not resolve them again here: on Windows, a second filesystem
    resolution can expand a short name or traverse a runner alias on only one
    side of an otherwise identical lexical receipt binding.
    """
    commands = {name: value["command"] for name, value in receipts.items()}

    require(executable_is(commands["configure.json"], "cmake"),
            "configure receipt executable mismatch")
    require(executable_is(commands["build.json"], "cmake"),
            "build receipt executable mismatch")
    require(executable_is(commands["ctest.json"], "ctest"),
            "CTest receipt executable mismatch")
    require(portable_basename(commands["producer-a.json"][0]) in {
                "mls_constitutive_expressivity_diagnostic",
                "mls_constitutive_expressivity_diagnostic.exe",
            }, "producer-a receipt executable mismatch")
    require(portable_basename(commands["producer-b.json"][0]) in {
                "mls_constitutive_expressivity_diagnostic",
                "mls_constitutive_expressivity_diagnostic.exe",
            }, "producer-b receipt executable mismatch")

    configure_source = command_path(
        receipts["configure.json"], "-S", "configure.json")
    configure_build = command_path(
        receipts["configure.json"], "-B", "configure.json")
    require(exact_option(commands["build.json"], "--build", "build.json"),
            "build directory missing")
    build_dir = command_path(receipts["build.json"], "--build", "build.json")
    ctest_dir = command_path(receipts["ctest.json"], "--test-dir", "ctest.json")
    require(configure_build == build_dir == ctest_dir,
            "configure/build/CTest directories are not the same resolved path")

    producer_a = command_path(
        receipts["producer-a.json"], "--output", "producer-a.json")
    producer_b = command_path(
        receipts["producer-b.json"], "--output", "producer-b.json")
    require(producer_a != producer_b,
            "twin producers must use distinct resolved output directories")

    pair = {producer_a, producer_b}
    twin_bundle = command_path(
        receipts["twin-compare.json"], "--bundle", "twin-compare.json")
    twin_compare = command_path(
        receipts["twin-compare.json"], "--compare", "twin-compare.json")
    validator_bundle = command_path(
        receipts["validator.json"], "--bundle", "validator.json")
    validator_compare = command_path(
        receipts["validator.json"], "--compare", "validator.json")
    require({twin_bundle, twin_compare} == pair and twin_bundle != twin_compare,
            "twin comparator paths do not equal the producer bundle paths")
    require({validator_bundle, validator_compare} == pair and
            validator_bundle != validator_compare,
            "validator paths do not equal the producer bundle paths")
    parent_bundle = command_path(
        receipts["parent-subset.json"], "--parent-bundle",
        "parent-subset.json")

    if expected_repo is not None:
        expected = canonical_recorded_path(str(expected_repo),
                                           str(expected_repo))
        require(configure_source == expected,
                "configured source directory does not equal the sealed repository")
    if expected_bundle_a is not None:
        expected = canonical_recorded_path(str(expected_bundle_a),
                                           str(expected_bundle_a.parent))
        require(producer_a == expected,
                "producer-a output does not equal --bundle-a")
    if expected_bundle_b is not None:
        expected = canonical_recorded_path(str(expected_bundle_b),
                                           str(expected_bundle_b.parent))
        require(producer_b == expected,
                "producer-b output does not equal --bundle-b")
    if expected_parent_bundle is not None:
        expected = canonical_recorded_path(
            str(expected_parent_bundle),
            str(expected_parent_bundle.parent),
        )
        require(parent_bundle == expected,
                "parent subset input does not equal --parent-bundle")

    return {
        "schema": RECEIPT_BINDINGS_SCHEMA,
        "semantics": "integrity-bound-command-receipts-not-execution-authentication",
        "configure_source_dir": configure_source,
        "build_dir": configure_build,
        "bundle_a": producer_a,
        "bundle_b": producer_b,
        "twin_compare_order": [twin_bundle, twin_compare],
        "validator_order": [validator_bundle, validator_compare],
        "accepted_parent_bundle": parent_bundle,
    }


def record_command(args: argparse.Namespace) -> int:
    """Execute one command and atomically preserve its exact structured receipt."""
    repo = args.repo.resolve()
    source_sha = args.source_sha
    require(SHA1_RE.fullmatch(source_sha) is not None, "invalid receipt source SHA")
    require(git_text(repo, "rev-parse", "HEAD") == source_sha,
            "receipt repository HEAD/source mismatch")
    require(git_text(repo, "branch", "--show-current") == BRANCH,
            "receipt repository branch mismatch")
    require(git_text(repo, "status", "--porcelain=v1", "--untracked-files=all") == "",
            "receipt repository is dirty")
    command = list(args.command)
    if command and command[0] == "--":
        command.pop(0)
    require(command, "receipt command is empty")
    destination = args.receipt.resolve()
    require(destination.name == f"{args.label}.json",
            "receipt filename must equal <label>.json")
    require(not destination.exists(), "receipt already exists; preserve prior evidence")
    cwd = args.cwd.resolve() if args.cwd is not None else repo
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    completed = subprocess.run(
        command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", check=False,
    )
    ended = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    output = completed.stdout
    payload = output.encode("utf-8")
    value = {
        "schema": RECEIPT_SCHEMA,
        "label": args.label,
        "source_sha": source_sha,
        "branch": BRANCH,
        "cwd": str(cwd),
        "command": command,
        "started_at_utc": started,
        "ended_at_utc": ended,
        "exit_code": completed.returncode,
        "output_bytes": len(payload),
        "output_sha256": sha256_bytes(payload),
        "output": output,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    require(not temporary.exists(), "temporary receipt path already exists")
    temporary.write_text(
        json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, destination)
    replay_console_output(output)
    return completed.returncode


def replay_console_output(output: str, stream: Any = None) -> None:
    """Replay captured UTF-8 output without making console encoding evidentiary.

    The receipt above is written from ``output`` itself.  Console replay is only
    a convenience and must not turn an otherwise valid recorded command into a
    failure when a Windows console uses a restrictive encoding such as cp1252.
    Unrepresentable characters are therefore emitted as deterministic Python
    backslash escapes on that console; the receipt retains the original text.
    """
    destination = sys.stdout if stream is None else stream
    encoding = getattr(destination, "encoding", None) or "utf-8"
    try:
        printable = output.encode(encoding, errors="backslashreplace").decode(encoding)
    except (LookupError, UnicodeError):
        printable = output.encode("ascii", errors="backslashreplace").decode("ascii")
    try:
        destination.write(printable)
    except UnicodeEncodeError:
        # A wrapper may advertise an encoding different from the encoder used
        # by its underlying sink.  ASCII backslash escapes remain replayable.
        destination.write(
            output.encode("ascii", errors="backslashreplace").decode("ascii")
        )


def require_receipts(
    logs: pathlib.Path,
    source_sha: str,
    *,
    expected_repo: pathlib.Path | None = None,
    expected_bundle_a: pathlib.Path | None = None,
    expected_bundle_b: pathlib.Path | None = None,
    expected_parent_bundle: pathlib.Path | None = None,
) -> dict[str, Any]:
    actual = {path.name for path in logs.iterdir() if path.is_file()}
    require(actual == REQUIRED_RECEIPTS | {"ci-run.json"},
            f"receipt inventory mismatch: {sorted(actual ^ (REQUIRED_RECEIPTS | {'ci-run.json'}))}")
    receipts = {name: read_json(logs / name) for name in REQUIRED_RECEIPTS}
    outputs = {
        name: validate_receipt(receipt, source_sha, name)
        for name, receipt in receipts.items()
    }
    commands = {name: receipts[name]["command"] for name in receipts}
    bindings = receipt_path_bindings(
        receipts,
        expected_repo=expected_repo,
        expected_bundle_a=expected_bundle_a,
        expected_bundle_b=expected_bundle_b,
        expected_parent_bundle=expected_parent_bundle,
    )

    require_script(commands["twin-compare.json"],
                   "validate_constitutive_expressivity_bundle.py",
                   "twin-compare.json")
    require_script(commands["validator.json"],
                   "validate_constitutive_expressivity_bundle.py",
                   "validator.json")
    require_script(commands["validator-regression.json"],
                   "constitutive_expressivity_bundle_validator_test.py",
                   "validator-regression.json")
    require_script(commands["exact-oracle.json"],
                   "constitutive_expressivity_oracle.py", "exact-oracle.json")
    require(exact_option(commands["exact-oracle.json"], "--verify",
                         "exact-oracle.json"),
            "exact oracle verification target missing")
    require_script(commands["exact-oracle-regression.json"],
                   "constitutive_expressivity_oracle_test.py",
                   "exact-oracle-regression.json")
    require(executable_is(commands["lean-build.json"], "lake") and
            commands["lean-build.json"][1:] == ["--wfail", "build"],
            "Lean build receipt argv mismatch")
    require(executable_is(commands["lean-axioms.json"], "lake") and
            commands["lean-axioms.json"][1:3] == ["env", "lean"] and
            portable_basename(commands["lean-axioms.json"][-1]) ==
            "axiomreport.lean",
            "Lean axiom receipt argv mismatch")
    require_script(commands["formal-trust.json"], "formal_trust_scan.py",
                   "formal-trust.json")
    exact_option(commands["formal-trust.json"], "--formal-root",
                 "formal-trust.json")
    require(any(token in {"--version", "-version", "/?"}
                for token in commands["compiler-versions.json"]) or
            any("version" in token.lower()
                for token in commands["compiler-versions.json"]),
            "compiler version receipt argv mismatch")
    require_script(commands["parent-subset.json"],
                   "derive_constitutive_parent_subset.py",
                   "parent-subset.json")
    exact_option(commands["parent-subset.json"], "--parent-bundle",
                 "parent-subset.json")
    require_exact_flag(commands["parent-subset.json"], "--verify",
                       "parent-subset.json")
    require("-DMLS_WARNINGS_AS_ERRORS=ON" in commands["configure.json"],
            "configure did not enable warnings as errors")
    require("-DMLS_RUN_EXTENDED_EXACT_TESTS=ON" in commands["configure.json"],
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
        "parent-subset.json": "constitutive parent subset: PASS",
    }
    for name, marker in markers.items():
        require(marker in outputs[name], f"receipt marker absent: {name}")
    for digest in (
        "45d162381ec723dd9ce744f2cc23c4d21435a52b7c7e60a182073ee19a08d60e",
        "843c9cb22c0b55e07c207135125a8334b0dd170a0f708aa1fb50f34d4c5d7363",
        "0b2e21dcbf26454af316bec9323627aa1488ebc7aa1f14c006bfb41a231e0e6f",
    ):
        require(digest in outputs["parent-subset.json"],
                "parent subset receipt omits a frozen selected hash")
    all_output = "\n".join(outputs.values()).lower()
    require("0 tests failed" in outputs["ctest.json"].lower(),
            "CTest did not report zero failures")
    explicit_no_promotion = re.compile(
        rf"(?<![A-Za-z0-9_]){re.escape(NO_PROMOTION)}(?![A-Za-z0-9_])"
    )
    require(explicit_no_promotion.search(outputs["producer-a.json"]) is not None and
            explicit_no_promotion.search(outputs["producer-b.json"]) is not None,
            f"producer receipts omit exact {NO_PROMOTION} token")
    require(not any(token in all_output for token in (
        "sorryax found", "declaration uses 'sorry'", "custom axiom found",
        "tests failed, 0 tests passed")), "receipt output contains a trust failure")
    return bindings


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
    require(set(value) == CI_FIELDS, "public CI result field inventory mismatch")
    return value


def write_ci_capture(destination: pathlib.Path, ci: dict[str, Any],
                     source_sha: str, run_id: str, attempt: int) -> None:
    """Validate and atomically create one integrity-bound public CI record."""
    require(destination.name == "ci-run.json",
            "CI capture destination must be named ci-run.json")
    require(SHA1_RE.fullmatch(source_sha) is not None,
            "invalid CI capture source SHA")
    require(type(attempt) is int and attempt > 0, "invalid CI capture attempt")
    require(set(ci) == CI_FIELDS, "CI capture field inventory mismatch")
    validate_ci(ci, source_sha, run_id, attempt)
    destination.parent.mkdir(parents=True, exist_ok=True)
    require(not destination.exists(), "CI capture already exists; preserve it")
    temporary = destination.with_name(destination.name + ".tmp")
    require(not temporary.exists(), "temporary CI capture path already exists")
    payload = (json.dumps(ci, sort_keys=True, indent=2) + "\n").encode("utf-8")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Hard-link publication is fail-if-exists on all supported hosts.  A
        # rename would overwrite on POSIX and would weaken the no-overwrite gate.
        os.link(temporary, destination)
        temporary.unlink()
    except FileExistsError as error:
        temporary.unlink(missing_ok=True)
        raise SealError("CI capture destination appeared during publication") from error
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def capture_ci(args: argparse.Namespace) -> int:
    ci = fetch_ci_run(args.repository_url, args.run_id, args.attempt)
    destination = args.destination.resolve()
    write_ci_capture(destination, ci, args.source_sha, args.run_id, args.attempt)
    print(
        "CONSTITUTIVE EXPRESSIVITY CI CAPTURED: "
        f"run={args.run_id}; attempt={args.attempt}; "
        f"source_sha={args.source_sha}; path={destination}"
    )
    return 0


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
    receipt_bindings = require_receipts(root / "logs", provenance["source_sha"])
    require(receipt_bindings == provenance["receipt_path_bindings"],
            "sealed receipt path relationships mismatch")
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
    receipt_bindings = require_receipts(
        args.logs.resolve(), source_sha,
        expected_repo=repo,
        expected_bundle_a=first,
        expected_bundle_b=second,
        expected_parent_bundle=args.parent_bundle.resolve(),
    )
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
        "receipt_path_bindings": receipt_bindings,
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
    subcommands = result.add_subparsers(dest="operation", required=True)
    create_parser = subcommands.add_parser("create")
    create_parser.add_argument("--repo", type=pathlib.Path, required=True)
    create_parser.add_argument("--bundle-a", type=pathlib.Path, required=True)
    create_parser.add_argument("--bundle-b", type=pathlib.Path, required=True)
    create_parser.add_argument("--parent-bundle", type=pathlib.Path, required=True)
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
    record_parser = subcommands.add_parser("record")
    record_parser.add_argument("--repo", type=pathlib.Path, required=True)
    record_parser.add_argument("--cwd", type=pathlib.Path)
    record_parser.add_argument("--source-sha", required=True)
    record_parser.add_argument("--label", required=True)
    record_parser.add_argument("--receipt", type=pathlib.Path, required=True)
    record_parser.add_argument("command", nargs=argparse.REMAINDER)
    capture_parser = subcommands.add_parser("capture-ci")
    capture_parser.add_argument("--repository-url", required=True)
    capture_parser.add_argument("--run-id", required=True)
    capture_parser.add_argument("--attempt", type=int, default=1)
    capture_parser.add_argument("--source-sha", required=True)
    capture_parser.add_argument("--destination", type=pathlib.Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.operation == "record":
            return record_command(args)
        if args.operation == "capture-ci":
            return capture_ci(args)
        if args.operation == "create":
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
