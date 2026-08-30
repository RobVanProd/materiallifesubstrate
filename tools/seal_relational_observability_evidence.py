#!/usr/bin/env python3
"""Create or verify the immutable Relational Observability outer seal."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys


SCHEMA = "mls-relational-observability-outer-seal-v1"
BRANCH = "relational-observability-confirmation"
ALLOWED_VERDICTS = {
    "stop_inconclusive_or_implementation_failure",
    "reject_central_relational_representation",
    "retain_only_as_mathematically_rigid_numerically_unsafe",
    "retain_central_relational_representation_for_research",
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
SOURCE_FILES = {
    ".github/workflows/baseline-replication.yml",
    "CMakeLists.txt",
    "tests/CMakeLists.txt",
    "apps/relational_observability_diagnostic.cpp",
    "include/mls/relational_observability_confirmation.hpp",
    "src/relational_observability_confirmation.cpp",
    "reference/validate_relational_observability_bundle.py",
    "tests/relational_observability_confirmation_tests.cpp",
    "tests/relational_observability_bundle_validator_test.py",
    "formal/MLSFormal/RelationalObservability.lean",
    "formal/MLSFormal/AxiomReport.lean",
    "formal/lakefile.toml",
    "formal/lake-manifest.json",
    "formal/lean-toolchain",
    "docs/relational-observability-confirmation-contract.md",
    "docs/relational-observability-confirmation-preregistration.md",
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
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise SealError(
            "bundle validator failed:\n" + completed.stdout + completed.stderr
        )


def require_log_markers(logs: pathlib.Path) -> None:
    markers = {
        "configure.log": "Build files have been written",
        "build.log": "mls_relational_observability_diagnostic",
        "ctest.log": "100% tests passed",
        "producer-a.log": "Relational Observability evidence written",
        "producer-b.log": "Relational Observability evidence written",
        "twin-compare.log": "byte comparison: PASS",
        "validator.log": "RELATIONAL OBSERVABILITY BUNDLE VALID",
        "validator-regression.log": "relational observability bundle validator regression: PASS",
        "lean-build.log": "Build completed successfully",
        "lean-axioms.log": "mechanicallyObservable_vertex_relabel_iff",
        "formal-trust.log": "PASS: no sorry, admit, sorryAx",
        "compiler-versions.txt": "source_sha=",
        "ci-run.json": '"conclusion":"success"',
    }
    observed = {path.name for path in logs.iterdir() if path.is_file()}
    if observed != REQUIRED_LOGS:
        raise SealError(f"log inventory mismatch: {sorted(observed ^ REQUIRED_LOGS)}")
    for filename, marker in markers.items():
        text = (logs / filename).read_text(encoding="utf-8", errors="strict")
        candidate = text.replace(" ", "") if filename == "ci-run.json" else text
        if marker not in candidate:
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


def validate_summary(summary: dict, source_sha: str) -> str:
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


def create(args: argparse.Namespace) -> dict:
    seal_dir = args.seal_dir.resolve()
    if seal_dir.exists() and (not seal_dir.is_dir() or any(seal_dir.iterdir())):
        raise SealError("seal directory must be absent or empty")
    seal_dir.mkdir(parents=True, exist_ok=True)
    repo = args.repo.resolve()
    validator = repo / "reference" / "validate_relational_observability_bundle.py"
    run_validator(validator, args.bundle_a.resolve(), args.bundle_b.resolve())
    first_summary = read_json(args.bundle_a / "summary.json")
    second_summary = read_json(args.bundle_b / "summary.json")
    if first_summary != second_summary:
        raise SealError("twin summaries differ")
    verdict = validate_summary(first_summary, args.source_sha)

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
        "verdict": verdict,
        "promotion_permitted": False,
    }
    (seal_dir / "provenance.json").write_text(
        json.dumps(provenance, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return write_manifest(seal_dir, provenance)


def verify(seal_dir: pathlib.Path) -> dict:
    root = seal_dir.resolve()
    manifest = verify_manifest_only(root)
    provenance = read_json(root / "provenance.json")
    if manifest.get("provenance") != provenance:
        raise SealError("manifest/provenance mismatch")
    if provenance.get("branch") != BRANCH:
        raise SealError("sealed branch mismatch")
    if provenance.get("promotion_permitted") is not False:
        raise SealError("invalid promotion claim")
    if provenance.get("verdict") not in ALLOWED_VERDICTS:
        raise SealError("invalid sealed verdict")
    require_log_markers(root / "logs")
    ci = read_json(root / "logs" / "ci-run.json")
    if (
        ci.get("headSha") != provenance.get("source_sha")
        or ci.get("conclusion") != "success"
        or str(ci.get("databaseId")) != provenance.get("ci_run_id")
    ):
        raise SealError("sealed CI provenance mismatch")
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "create":
            payload = create(args)
            print(json.dumps(payload, sort_keys=True, indent=2))
        else:
            payload = verify(args.seal_dir)
            print(json.dumps(payload, sort_keys=True, indent=2))
    except SealError as error:
        print(f"relational observability seal rejected: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

