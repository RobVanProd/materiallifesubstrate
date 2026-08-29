#!/usr/bin/env python3
"""Create and verify the immutable Kelvin Covariance Audit outer seal."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Iterable

SCHEMA = "mls-kelvin-covariance-outer-seal-v1"
BRANCH = "kelvin-covariance-audit"
REQUIRED_LOGS = {
    "configure.log",
    "build.log",
    "ctest.log",
    "oracle.log",
    "oracle-regression.log",
    "lean-build.log",
    "lean-axioms.log",
    "formal-trust.log",
    "validator.log",
    "compiler-versions.txt",
    "ci-run.json",
}
SOURCE_FILES = {
    ".github/workflows/baseline-replication.yml",
    "CMakeLists.txt",
    "tests/CMakeLists.txt",
    "apps/kelvin_covariance_diagnostic.cpp",
    "include/mls/kelvin_covariance_audit.hpp",
    "src/kelvin_covariance_audit.cpp",
    "reference/kelvin_covariance_oracle.py",
    "reference/validate_kelvin_covariance_bundle.py",
    "tests/kelvin_covariance_audit_tests.cpp",
    "tests/kelvin_covariance_oracle.canonical.json",
    "tests/kelvin_covariance_oracle_test.py",
    "tests/kelvin_covariance_bundle_validator_test.py",
    "formal/MLSFormal/KelvinCovariance.lean",
    "formal/MLSFormal/AxiomReport.lean",
    "formal/lakefile.toml",
    "formal/lake-manifest.json",
    "formal/lean-toolchain",
    "docs/kelvin-covariance-audit-contract.md",
    "docs/kelvin-covariance-source-audit.md",
    "docs/kelvin-covariance-audit-results.md",
    "tools/formal_trust_scan.py",
    "tools/seal_kelvin_covariance_evidence.py",
}


class SealError(RuntimeError):
    pass


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def files_under(root: pathlib.Path, *, omit_manifest: bool = False) -> list[pathlib.Path]:
    return sorted(
        path for path in root.rglob("*") if path.is_file() and
        not (omit_manifest and path.relative_to(root).as_posix() == "outer-seal.json"))


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
        sort_keys=True, separators=(",", ":")).encode("utf-8")
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
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return payload


def verify_manifest_only(root: pathlib.Path) -> dict:
    manifest_path = root / "outer-seal.json"
    if not manifest_path.is_file():
        raise SealError("missing outer-seal.json")
    try:
        observed = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SealError(f"invalid outer manifest: {error}") from error
    if observed.get("schema") != SCHEMA:
        raise SealError("outer schema mismatch")
    provenance = observed.get("provenance")
    if not isinstance(provenance, dict):
        raise SealError("outer provenance missing")
    expected = manifest_payload(root, provenance)
    if observed != expected:
        raise SealError("outer manifest/hash/inventory mismatch")
    return observed


def run_validator(validator: pathlib.Path, first: pathlib.Path,
                  second: pathlib.Path | None = None) -> None:
    command = [sys.executable, str(validator), "--bundle", str(first)]
    if second is not None:
        command += ["--compare", str(second)]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise SealError(
            "bundle validator failed:\n" + completed.stdout + completed.stderr)


def read_json(path: pathlib.Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SealError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise SealError(f"{path} must contain a JSON object")
    return value


def require_log_markers(logs: pathlib.Path) -> None:
    markers = {
        "configure.log": "Build files have been written",
        "build.log": "mls_kelvin_covariance_diagnostic",
        "ctest.log": "100% tests passed",
        "oracle.log": "result_sha256_before_hash_field",
        "oracle-regression.log": "kelvin covariance exact-oracle regression: PASS",
        "lean-build.log": "Build completed successfully",
        "lean-axioms.log": "scalarRowNormalization_destroys_raw_spectrum_covariance",
        "formal-trust.log": "PASS: no sorry, admit, sorryAx",
        "validator.log": "KELVIN COVARIANCE BUNDLE VALID",
        "compiler-versions.txt": "source_sha=",
        "ci-run.json": '"conclusion":"success"',
    }
    observed = {path.name for path in logs.iterdir() if path.is_file()}
    if observed != REQUIRED_LOGS:
        raise SealError(f"log inventory mismatch: {sorted(observed ^ REQUIRED_LOGS)}")
    for filename, marker in markers.items():
        text = (logs / filename).read_text(encoding="utf-8", errors="strict")
        if marker not in text.replace(" ", "") if filename == "ci-run.json" else marker not in text:
            raise SealError(f"required marker absent from {filename}")


def copy_tree_exact(source: pathlib.Path, destination: pathlib.Path) -> None:
    if not source.is_dir():
        raise SealError(f"source directory missing: {source}")
    shutil.copytree(source, destination)


def copy_source_snapshot(repo: pathlib.Path, destination: pathlib.Path) -> None:
    for relative in sorted(SOURCE_FILES):
        source = repo / relative
        if not source.is_file():
            raise SealError(f"required source file missing: {relative}")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def create(args: argparse.Namespace) -> dict:
    seal_dir: pathlib.Path = args.seal_dir.resolve()
    if seal_dir.exists() and (not seal_dir.is_dir() or any(seal_dir.iterdir())):
        raise SealError("seal directory must be absent or empty")
    seal_dir.mkdir(parents=True, exist_ok=True)
    repo = args.repo.resolve()
    validator = repo / "reference" / "validate_kelvin_covariance_bundle.py"
    run_validator(validator, args.bundle_a.resolve(), args.bundle_b.resolve())
    first_summary = read_json(args.bundle_a / "summary.json")
    second_summary = read_json(args.bundle_b / "summary.json")
    if first_summary != second_summary:
        raise SealError("twin summaries differ")
    if first_summary.get("source_sha") != args.source_sha:
        raise SealError("bundle source SHA mismatch")
    if first_summary.get("source_branch") != BRANCH:
        raise SealError("bundle branch mismatch")
    if first_summary.get("source_dirty_at_configure") is not False:
        raise SealError("bundle was configured from a dirty source")
    if first_summary.get("decision") != "SUPPORTED_DIAGNOSTIC_COORDINATE_DEFECT":
        raise SealError("bundle decision is not the preregistered supported result")

    ci = read_json(args.logs / "ci-run.json")
    if ci.get("headSha") != args.source_sha or ci.get("conclusion") != "success":
        raise SealError("CI evidence does not certify the source SHA")
    if str(ci.get("databaseId")) != str(args.ci_run_id):
        raise SealError("CI run ID mismatch")
    require_log_markers(args.logs)

    copy_tree_exact(args.bundle_a.resolve(), seal_dir / "bundles" / "full-a")
    copy_tree_exact(args.bundle_b.resolve(), seal_dir / "bundles" / "full-b")
    copy_tree_exact(args.logs.resolve(), seal_dir / "logs")
    copy_source_snapshot(repo, seal_dir / "source")
    provenance = {
        "repository_url": args.repository_url,
        "branch": BRANCH,
        "source_sha": args.source_sha,
        "ci_run_id": str(args.ci_run_id),
        "tag": args.tag,
        "decision": "SUPPORTED_DIAGNOSTIC_COORDINATE_DEFECT",
        "promotion_permitted": False,
    }
    (seal_dir / "provenance.json").write_text(
        json.dumps(provenance, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return write_manifest(seal_dir, provenance)


def verify(seal_dir: pathlib.Path) -> dict:
    root = seal_dir.resolve()
    manifest = verify_manifest_only(root)
    provenance = read_json(root / "provenance.json")
    if manifest.get("provenance") != provenance:
        raise SealError("manifest/provenance mismatch")
    if provenance.get("branch") != BRANCH or provenance.get("promotion_permitted") is not False:
        raise SealError("invalid claim boundary")
    require_log_markers(root / "logs")
    ci = read_json(root / "logs" / "ci-run.json")
    if ci.get("headSha") != provenance.get("source_sha") or \
            ci.get("conclusion") != "success" or \
            str(ci.get("databaseId")) != provenance.get("ci_run_id"):
        raise SealError("sealed CI provenance mismatch")
    validator = root / "source" / "reference" / "validate_kelvin_covariance_bundle.py"
    run_validator(validator, root / "bundles" / "full-a",
                  root / "bundles" / "full-b")
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    subcommands = result.add_subparsers(dest="command", required=True)
    create_parser = subcommands.add_parser("create")
    create_parser.add_argument("--seal-dir", type=pathlib.Path, required=True)
    create_parser.add_argument("--repo", type=pathlib.Path, required=True)
    create_parser.add_argument("--bundle-a", type=pathlib.Path, required=True)
    create_parser.add_argument("--bundle-b", type=pathlib.Path, required=True)
    create_parser.add_argument("--logs", type=pathlib.Path, required=True)
    create_parser.add_argument("--source-sha", required=True)
    create_parser.add_argument("--ci-run-id", required=True)
    create_parser.add_argument("--repository-url", required=True)
    create_parser.add_argument("--tag", default="kelvin-covariance-audit-evidence-v1")
    verify_parser = subcommands.add_parser("verify")
    verify_parser.add_argument("--seal-dir", type=pathlib.Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        manifest = create(args) if args.command == "create" else verify(args.seal_dir)
        print(f"KELVIN COVARIANCE OUTER SEAL VALID: {manifest['file_count']} files; "
              f"pre_hash={manifest['pre_hash_sha256']}")
        return 0
    except (OSError, SealError, subprocess.SubprocessError) as error:
        print(f"KELVIN COVARIANCE OUTER SEAL INVALID: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
