#!/usr/bin/env python3
"""Mutation regression for the mechanical observability outer evidence seal.

The regression constructs two complete synthetic producer bundles and a
separate provenance tree, checks that create leaves all inputs untouched,
checks deterministic copy/sealing and positive verify, then applies raw and
self-consistently re-manifested adversarial mutations.  Adversarial outer
manifests are refreshed by this test, never by the sealer under test.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


OUTER_MANIFEST = "outer-manifest.json"
OUTER_SCHEMA = "mls.mechanical-observability.outer-evidence-seal.v3"
METADATA_SCHEMA = (
    "mls.mechanical-observability.outer-evidence-metadata.v3"
)
CI_SCHEMA = (
    "mls.mechanical-observability.captured-external-ci-metadata.v1"
)
INNER_SCHEMA = "mls.mechanical-observability.manifest.v1"
SUMMARY_SCHEMA = "mls.mechanical-observability.summary.v1"
BRANCH = "mechanical-observability-lab"
PARENT_SHA = "2e175396ff30faea8a4d96d5a0336ab9ba042f12"
REPOSITORY = "https://github.com/RobVanProd/materiallifesubstrate"
SOURCE_SHA = "1234567890abcdef1234567890abcdef12345678"
RUN_URL = REPOSITORY + "/actions/runs/123456"
VALIDATOR_MARKER = "MECHANICAL OBSERVABILITY BUNDLE VALID:"
VALIDATOR_FINDINGS_SCHEMA = (
    "mls.mechanical-observability.validator-findings.v1"
)
VALIDATOR_FINDINGS_PATH = (
    "results/mechanical-observability-findings.json"
)
VALIDATOR_LOG_PATH = "logs/full-bundle-validator.log"
STOP_DECISION = "stop_inconclusive_or_implementation_failure"

INNER_FILES = (
    "configurations.csv",
    "packets.csv",
    "neighbor_pairs.csv",
    "relations.csv",
    "operator_status.csv",
    "operator_entries.csv",
    "moment_diagnostics.csv",
    "affine_objectivity.csv",
    "invariance.csv",
    "rigid_basis.csv",
    "rank_status.csv",
    "nullspace_modes.csv",
    "nullspace_metrics.csv",
    "grid_gauge.csv",
    "exact_reference.csv",
    "grid_nodes.csv",
    "checkpoints.csv",
    "permutation_controls.csv",
    "permutation_entries.csv",
    "summary.json",
)
CLAIM_SCOPE = "integrity_and_independent_local_semantic_validation_only"
UNAUTHENTICATED = "not_authenticated_by_offline_seal"
LOGS = (
    "full-bundle-a.log",
    "full-bundle-b.log",
    "full-bundle-compare.log",
    "full-bundle-validator.log",
    "configure.log",
    "build.log",
    "ctest.log",
    "exact-oracle.log",
    "validator-mutation.log",
    "lean-build.log",
    "lean-axiom-report.log",
    "source-scan.log",
    "git-provenance.log",
)
RESULT_EVIDENCE = {
    "full_bundle_a": ["logs/full-bundle-a.log"],
    "full_bundle_b": ["logs/full-bundle-b.log"],
    "bundle_compare_validator": [
        "logs/full-bundle-compare.log",
        "logs/full-bundle-validator.log",
        VALIDATOR_FINDINGS_PATH,
    ],
    "configure": ["logs/configure.log"],
    "build": ["logs/build.log"],
    "ctest": ["logs/ctest.log"],
    "exact_oracle": ["logs/exact-oracle.log"],
    "validator_mutation": ["logs/validator-mutation.log"],
    "lean_build": ["logs/lean-build.log"],
    "lean_axiom_report": ["logs/lean-axiom-report.log"],
    "source_scan": ["logs/source-scan.log"],
    "git_provenance": ["logs/git-provenance.log"],
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: Any, *, pretty: bool) -> bytes:
    if pretty:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def flat_bundle_hashes(bundle: Path) -> dict[str, str]:
    return {
        path.name: sha256_bytes(path.read_bytes())
        for path in sorted(bundle.iterdir(), key=lambda item: item.name)
        if path.is_file()
    }


def make_validator_findings(
    first: Path, second: Path, validator_sha256: str
) -> bytes:
    first_hashes = flat_bundle_hashes(first)
    second_hashes = flat_bundle_hashes(second)
    if set(first_hashes) != set(second_hashes):
        raise AssertionError("synthetic bundle inventories differ")
    mismatches = [
        {
            "path": path,
            "first_sha256": first_hashes[path],
            "second_sha256": second_hashes[path],
        }
        for path in sorted(first_hashes)
        if first_hashes[path] != second_hashes[path]
    ]
    summaries = [
        json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
        for bundle in (first, second)
    ]
    claim_mismatches: list[str] = []
    if mismatches and not all(
        summary["nondeterminism_detected"] for summary in summaries
    ):
        claim_mismatches.append("comparison.nondeterminism_detected")
    if not mismatches:
        for label, summary in zip(("first", "second"), summaries):
            if summary["nondeterminism_detected"]:
                claim_mismatches.append(f"{label}.nondeterminism_detected")
    claim_mismatches.sort()
    negative = bool(mismatches or claim_mismatches)
    gates = {
        "affine_objectivity_all_pass": True,
        "checkpoint_round_trip_all_pass": True,
        "decisive_rank_rows_all_unambiguous": True,
        "deterministic_repeatability": not mismatches,
        "diagnostics_read_only_all_exact": True,
        "finite_objectivity_all_pass": True,
        "independent_reference_all_pass": True,
        "invariance_all_pass": True,
        "negative_control_reproduced": True,
        "neighbor_lookup_all_agree": True,
        "producer_claims_consistent": not claim_mismatches,
        "raw_decision_rows_all_exported": True,
    }
    if negative:
        candidate_findings = {
            "A": "negative_control_reproduced",
            "B": "inconclusive",
            "C": "inconclusive",
            "D": "inconclusive",
        }
        decision = STOP_DECISION
    else:
        candidate_findings = {
            "A": "negative_control_reproduced",
            "B": "no_resolved_eligible_nonrigid_mode",
            "C": "retain_central_relational_representation_for_research",
            "D": "not_triggered",
        }
        decision = "retain_central_relational_representation_for_research"
    manifests = [
        json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        for bundle in (first, second)
    ]
    result: dict[str, Any] = {
        "bundle_structural_valid": [True, True],
        "candidate_findings": candidate_findings,
        "claim_mismatches": claim_mismatches,
        "comparison_status": (
            "nondeterministic" if mismatches else "byte_identical"
        ),
        "decision": decision,
        "derived_gates": gates,
        "first_manifest_pre_hash": manifests[0]["pre_hash_sha256"],
        "mismatches": mismatches,
        "mode": "full",
        "producer_claims_sha256": sha256_bytes(
            canonical_json_bytes(summaries, pretty=False)
        ),
        "promotion": False,
        "schema": VALIDATOR_FINDINGS_SCHEMA,
        "second_manifest_pre_hash": manifests[1]["pre_hash_sha256"],
        "source_sha": summaries[0]["source_sha"],
        "validator_sha256": validator_sha256,
    }
    result["result_sha256_before_hash_field"] = sha256_bytes(
        canonical_json_bytes(result, pretty=False)
    )
    return canonical_json_bytes(result, pretty=True)


def validator_stdout(findings_bytes: bytes, source_sha: str) -> bytes:
    findings = json.loads(findings_bytes.decode("utf-8"))
    return (
        VALIDATOR_MARKER
        + f" source_sha={source_sha} decision={findings['decision']} "
        + "promotion=false\n"
        + f"findings_sha256={sha256_bytes(findings_bytes)}\n"
    ).encode("utf-8")


def validator_binding(findings_bytes: bytes, log_bytes: bytes) -> dict[str, Any]:
    findings = json.loads(findings_bytes.decode("utf-8"))
    negative = bool(
        findings["comparison_status"] == "nondeterministic"
        or findings["claim_mismatches"]
    )
    return {
        "binding_kind": "fresh_pinned_validator_replay",
        "comparison_status": findings["comparison_status"],
        "decision": findings["decision"],
        "evidence_route": (
            "preserved_negative" if negative else "deterministic_success"
        ),
        "findings_path": VALIDATOR_FINDINGS_PATH,
        "findings_sha256": sha256_bytes(findings_bytes),
        "promotion": False,
        "result_sha256_before_hash_field": findings[
            "result_sha256_before_hash_field"
        ],
        "validator_log_path": VALIDATOR_LOG_PATH,
        "validator_log_sha256": sha256_bytes(log_bytes),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
    )


def inner_payload(hashes: Mapping[str, str]) -> bytes:
    names = sorted(hashes)
    lines = ["{", '  "algorithm": "SHA-256",', '  "files": {']
    for index, name in enumerate(names):
        comma = "," if index + 1 != len(names) else ""
        lines.append(
            f"    {json.dumps(name)}: {json.dumps(hashes[name])}{comma}"
        )
    lines.extend(("  },", f'  "schema": {json.dumps(INNER_SCHEMA)}', "}"))
    return "\n".join(lines).encode("utf-8")


def refresh_inner(bundle: Path) -> None:
    hashes = {
        name: sha256_bytes((bundle / name).read_bytes())
        for name in INNER_FILES
    }
    write_json(
        bundle / "manifest.json",
        {
            "algorithm": "SHA-256",
            "files": hashes,
            "pre_hash_sha256": sha256_bytes(inner_payload(hashes)),
            "schema": INNER_SCHEMA,
        },
    )


def make_bundle(bundle: Path) -> None:
    bundle.mkdir(parents=True)
    for index, name in enumerate(INNER_FILES):
        if name == "summary.json":
            continue
        (bundle / name).write_text(
            f"synthetic mechanical observability artifact {index}: {name}\n",
            encoding="utf-8",
        )
    write_json(
        bundle / "summary.json",
        {
            "branch": BRANCH,
            "dirty": False,
            "mode": "full",
            "nondeterminism_detected": False,
            "parent_sha": PARENT_SHA,
            "producer": "cpp_mechanical_observability_lab",
            "promotion": False,
            "schema": SUMMARY_SCHEMA,
            "seed": 260828,
            "source_sha": SOURCE_SHA,
        },
    )
    refresh_inner(bundle)


def make_provenance(
    root: Path,
    bundle: Path,
    second_bundle: Path,
    validator_sha256: str,
) -> None:
    findings_bytes = make_validator_findings(
        bundle, second_bundle, validator_sha256
    )
    log_bytes = validator_stdout(findings_bytes, SOURCE_SHA)
    findings_path = root / VALIDATOR_FINDINGS_PATH
    findings_path.parent.mkdir(parents=True)
    findings_path.write_bytes(findings_bytes)
    logs = root / "logs"
    logs.mkdir(parents=True)
    for name in LOGS:
        if name == "full-bundle-validator.log":
            (logs / name).write_bytes(log_bytes)
        else:
            (logs / name).write_bytes(
                f"synthetic captured output: {name}\n".encode("utf-8")
            )

    jobs = [
        {
            "id": "linux_gcc",
            "database_id": 701,
            "name": "C++ / Linux GCC",
            "conclusion": "success",
            "url": RUN_URL + "/job/701",
        },
        {
            "id": "linux_clang",
            "database_id": 702,
            "name": "C++ / Linux Clang",
            "conclusion": "success",
            "url": RUN_URL + "/job/702",
        },
        {
            "id": "windows_msvc",
            "database_id": 703,
            "name": "C++ / Windows MSVC",
            "conclusion": "success",
            "url": RUN_URL + "/job/703",
        },
        {
            "id": "python_oracle",
            "database_id": 704,
            "name": "Python exact oracle",
            "conclusion": "success",
            "url": RUN_URL + "/job/704",
        },
        {
            "id": "lean",
            "database_id": 705,
            "name": "Pinned Lean build and axiom output",
            "conclusion": "success",
            "url": RUN_URL + "/job/705",
        },
    ]
    write_json(
        root / "ci/metadata.json",
        {
            "authentication_status": UNAUTHENTICATED,
            "claim_kind": "captured_external_github_actions_metadata",
            "head_branch": BRANCH,
            "head_sha": SOURCE_SHA,
            "jobs": jobs,
            "repository_url": REPOSITORY,
            "run_id": 123456,
            "run_url": RUN_URL,
            "schema": CI_SCHEMA,
            "conclusion": "success",
        },
    )

    commands: list[dict[str, Any]] = []
    for name in RESULT_EVIDENCE:
        if name == "bundle_compare_validator":
            argv = [
                sys.executable,
                "reference/validate_mechanical_observability_bundle.py",
                "--bundle",
                "evidence/run-a",
                "--compare",
                "evidence/run-b",
                "--findings-output",
                VALIDATOR_FINDINGS_PATH,
                "--validator-sha256",
                validator_sha256,
            ]
        else:
            argv = ["synthetic-tool", "--stage", name]
        commands.append(
            {
                "argv": argv,
                "cwd": "D:/MaterialLifeSubstrate",
                "name": name,
            }
        )
    summaries = {
        name: {
            "evidence_paths": evidence,
            "exit_code": 0,
            "status": "pass",
            "summary": f"synthetic local {name} completed",
        }
        for name, evidence in RESULT_EVIDENCE.items()
    }
    write_json(
        root / "metadata.json",
        {
            "commands": commands,
            "captured_external_ci": {
                "authentication_status": UNAUTHENTICATED,
                "claim_kind": "captured_external_ci_metadata",
                "metadata_path": "ci/metadata.json",
            },
            "local": {
                "authentication_status": UNAUTHENTICATED,
                "claim_kind": "captured_local_execution_metadata",
                "execution_context": "local",
                "result_summaries": summaries,
                "tool_versions": {
                    "cmake": "cmake version 4.1.1",
                    "ctest": "ctest version 4.1.1",
                    "cxx": "g++ 15.2.0",
                    "git": "git version 2.51.0.windows.1",
                    "lake": "Lake version 5.0.0",
                    "lean": "Lean 4.24.0",
                    "python": "Python 3.13.14",
                },
            },
            "schema": METADATA_SCHEMA,
            "seal_claim_scope": CLAIM_SCOPE,
            "validator_findings": validator_binding(
                findings_bytes, log_bytes
            ),
            "source": {
                "authentication_status": UNAUTHENTICATED,
                "branch": BRANCH,
                "claim_kind": "captured_external_git_metadata",
                "repository_url": REPOSITORY,
                "sha": SOURCE_SHA,
                "tag": "mechanical-observability-evidence-v1",
                "tag_target_sha": SOURCE_SHA,
            },
        },
    )


def tree_snapshot(root: Path) -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    for path in sorted(
        root.rglob("*"),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        if path.is_file():
            raw = path.read_bytes()
            result[path.relative_to(root).as_posix()] = (
                len(raw),
                sha256_bytes(raw),
            )
    return result


def outer_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(
        root.rglob("*"),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        relative = path.relative_to(root).as_posix()
        if path.is_file() and relative != OUTER_MANIFEST:
            raw = path.read_bytes()
            records.append(
                {
                    "path": relative,
                    "sha256": sha256_bytes(raw),
                    "size": len(raw),
                }
            )
    return records


def refresh_outer(root: Path) -> None:
    records = outer_records(root)
    current = json.loads((root / OUTER_MANIFEST).read_text(encoding="utf-8"))
    payload = {
        "algorithm": "SHA-256",
        "claim_scope": CLAIM_SCOPE,
        "files": records,
        "metadata_path": "metadata.json",
        "pinned_validator_sha256": current["pinned_validator_sha256"],
        "schema": OUTER_SCHEMA,
        "validator_findings": current["validator_findings"],
    }
    write_json(
        root / OUTER_MANIFEST,
        {
            **payload,
            "pre_hash_sha256": sha256_bytes(
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ),
        },
    )


def run_create(
    tool: Any,
    bundle_a: Path,
    bundle_b: Path,
    provenance: Path,
    seal_dir: Path,
) -> subprocess.CompletedProcess[str]:
    if not isinstance(tool, Path):
        try:
            manifest = tool.create_seal(bundle_a, bundle_b, provenance, seal_dir)
            return subprocess.CompletedProcess(
                [], 0,
                f"OUTER SEAL VALID: pre_hash_sha256={manifest['pre_hash_sha256']}\n", ""
            )
        except tool.SealError as error:
            return subprocess.CompletedProcess([], 1, "", f"OUTER SEAL INVALID: {error}\n")
    return subprocess.run(
        [
            sys.executable,
            str(tool),
            "create",
            "--bundle-a",
            str(bundle_a),
            "--bundle-b",
            str(bundle_b),
            "--provenance-dir",
            str(provenance),
            "--seal-dir",
            str(seal_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def run_verify(
    tool: Any, seal_dir: Path
) -> subprocess.CompletedProcess[str]:
    if not isinstance(tool, Path):
        try:
            manifest = tool.verify_seal(seal_dir)
            return subprocess.CompletedProcess(
                [], 0,
                f"OUTER SEAL VALID: pre_hash_sha256={manifest['pre_hash_sha256']}\n", ""
            )
        except tool.SealError as error:
            return subprocess.CompletedProcess([], 1, "", f"OUTER SEAL INVALID: {error}\n")
    return subprocess.run(
        [
            sys.executable,
            str(tool),
            "verify",
            "--seal-dir",
            str(seal_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def require_create_valid(
    tool: Any,
    bundle_a: Path,
    bundle_b: Path,
    provenance: Path,
    seal_dir: Path,
) -> None:
    result = run_create(tool, bundle_a, bundle_b, provenance, seal_dir)
    if result.returncode != 0 or "OUTER SEAL VALID" not in result.stdout:
        raise AssertionError(
            "expected create success\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )


def require_create_invalid(
    tool: Any,
    bundle_a: Path,
    bundle_b: Path,
    provenance: Path,
    seal_dir: Path,
    label: str,
) -> None:
    result = run_create(tool, bundle_a, bundle_b, provenance, seal_dir)
    if result.returncode == 0 or "OUTER SEAL INVALID" not in result.stderr:
        raise AssertionError(
            f"{label}: expected create rejection\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )


def require_verify_valid(tool: Any, seal_dir: Path) -> None:
    result = run_verify(tool, seal_dir)
    if result.returncode != 0 or "OUTER SEAL VALID" not in result.stdout:
        raise AssertionError(
            "expected verify success\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )


def require_invalid(tool: Any, seal_dir: Path, label: str) -> None:
    result = run_verify(tool, seal_dir)
    if result.returncode == 0 or "OUTER SEAL INVALID" not in result.stderr:
        raise AssertionError(
            f"{label}: expected verify rejection\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )


def require_invalid_contains(
    tool: Any, seal_dir: Path, label: str, marker: str
) -> None:
    result = run_verify(tool, seal_dir)
    if (
        result.returncode == 0
        or "OUTER SEAL INVALID" not in result.stderr
        or marker not in result.stderr
    ):
        raise AssertionError(
            f"{label}: expected verify rejection containing {marker!r}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )


def mutate_json(
    root: Path,
    relative: str,
    change: Callable[[dict[str, Any]], None],
) -> None:
    path = root / relative
    value = json.loads(path.read_text(encoding="utf-8"))
    change(value)
    write_json(path, value)


def load_tool_module(path: Path) -> Any:
    specification = importlib.util.spec_from_file_location(
        "mechanical_observability_outer_seal", path
    )
    if specification is None or specification.loader is None:
        raise AssertionError("could not import seal tool for helper regressions")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def parse_arguments(
    arguments: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tool",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "tools/seal_mechanical_observability_evidence.py"
        ),
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    options = parse_arguments(arguments)
    tool_path = options.tool.resolve()
    if not tool_path.is_file():
        raise SystemExit(f"seal tool not found: {tool_path}")
    module = load_tool_module(tool_path)

    with tempfile.TemporaryDirectory(
        prefix="mls-mechanical-observability-outer-seal-"
    ) as temporary:
        work = Path(temporary)
        source_a = work / "source-run-a"
        source_b = work / "source-run-b"
        provenance = work / "source-provenance"
        make_bundle(source_a)
        shutil.copytree(source_a, source_b)
        make_provenance(
            provenance,
            source_a,
            source_b,
            module.PINNED_VALIDATOR_SHA256,
        )

        # The real pinned validator must reject this intentionally synthetic
        # (manifest-valid but semantically malformed) fixture.  Positive seal
        # flow below replaces only the expensive semantic runner with a strict
        # test double; all integrity/metadata logic remains the production code.
        source_records = [
            module.scan_regular_files(source_a),
            module.scan_regular_files(source_b),
        ]
        source_identities = [
            module.validate_inner_bundle(
                source_a, source_records[0], "synthetic source A"
            ),
            module.validate_inner_bundle(
                source_b, source_records[1], "synthetic source B"
            ),
        ]
        try:
            module._run_pinned_validator(
                source_a,
                source_b,
                source_identities,
                source_records,
            )
        except module.SealError:
            pass
        else:
            raise AssertionError("real pinned validator accepted malformed fixture")

        # Exercise the production isolation path with controlled exact bytes.
        # The repository-side source is replaced after it has been snapshotted,
        # and hostile Python environment entries are present in the caller.
        # Only the private byte-for-byte script under ``-I -S`` may execute.
        fake_project = work / "fake-validator-project"
        fake_tools = fake_project / "tools"
        fake_reference = fake_project / "reference"
        fake_tools.mkdir(parents=True)
        fake_reference.mkdir(parents=True)
        fake_tool_path = fake_tools / "seal.py"
        fake_tool_path.write_text("# path anchor only\n", encoding="utf-8")
        fake_validator_path = (
            fake_reference / "validate_mechanical_observability_bundle.py"
        )
        fake_findings_bytes = b"{}\n"
        fake_findings_sha256 = sha256_bytes(fake_findings_bytes)
        fake_stdout_bytes = (
            VALIDATOR_MARKER
            + " isolated\nfindings_sha256="
            + fake_findings_sha256
            + "\n"
        ).encode("utf-8")
        fake_validator_bytes = (
            "import os, pathlib, sys\n"
            "if 'PYTHONPATH' in os.environ or "
            "'MLS_SEAL_PATH_INJECTION' in os.environ:\n"
            "    raise SystemExit(73)\n"
            "if __file__ == '<stdin>':\n"
            "    output = pathlib.Path("
            "sys.argv[sys.argv.index('--findings-output') + 1])\n"
            "    output.write_bytes(" + repr(fake_findings_bytes) + ")\n"
            "    sys.stdout.buffer.write(" + repr(fake_stdout_bytes) + ")\n"
            "else:\n"
            "    raise SystemExit(74)\n"
        ).encode("utf-8")
        fake_validator_path.write_bytes(fake_validator_bytes)
        original_module_file = module.__file__
        original_pin = module.PINNED_VALIDATOR_SHA256
        original_subprocess_run = module.subprocess.run
        original_findings_validator = module.validate_validator_findings
        old_pythonpath = os.environ.get("PYTHONPATH")
        old_injection = os.environ.get("MLS_SEAL_PATH_INJECTION")
        os.environ["PYTHONPATH"] = str(work / "hostile-python-path")
        os.environ["MLS_SEAL_PATH_INJECTION"] = "must-not-propagate"

        def replace_source_after_snapshot(*args: Any, **kwargs: Any) -> Any:
            fake_validator_path.write_bytes(
                b"raise SystemExit('repository path won the race')\n"
            )
            try:
                return original_subprocess_run(*args, **kwargs)
            finally:
                fake_validator_path.write_bytes(fake_validator_bytes)

        try:
            module.__file__ = str(fake_tool_path)
            module.PINNED_VALIDATOR_SHA256 = sha256_bytes(
                fake_validator_bytes
            )
            module.subprocess.run = replace_source_after_snapshot

            def accept_fake_findings(
                raw: bytes,
                identities: Sequence[Mapping[str, Any]],
                records: Sequence[Sequence[Mapping[str, Any]]],
            ) -> dict[str, Any]:
                del identities, records
                if raw != fake_findings_bytes:
                    raise module.SealError("fake findings bytes changed")
                return {
                    "comparison_status": "byte_identical",
                    "decision": STOP_DECISION,
                    "evidence_route": "deterministic_success",
                    "findings": {},
                    "findings_sha256": fake_findings_sha256,
                    "promotion": False,
                    "result_sha256_before_hash_field": "0" * 64,
                    "source_sha": SOURCE_SHA,
                }

            module.validate_validator_findings = accept_fake_findings
            isolated_output = module._run_pinned_validator(
                source_a,
                source_b,
                source_identities,
                source_records,
            )
            if VALIDATOR_MARKER.encode("utf-8") \
                    not in isolated_output["stdout_bytes"]:
                raise AssertionError("isolated fake validator did not execute")
        finally:
            module.__file__ = original_module_file
            module.PINNED_VALIDATOR_SHA256 = original_pin
            module.subprocess.run = original_subprocess_run
            module.validate_validator_findings = original_findings_validator
            if old_pythonpath is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = old_pythonpath
            if old_injection is None:
                os.environ.pop("MLS_SEAL_PATH_INJECTION", None)
            else:
                os.environ["MLS_SEAL_PATH_INJECTION"] = old_injection

        expected_semantic_digest = sha256_bytes(
            (source_a / "configurations.csv").read_bytes()
        )
        semantic_calls = 0

        def strict_test_validator(
            first: Path,
            second_path: Path,
            identities: Sequence[Mapping[str, Any]],
            records: Sequence[Sequence[Mapping[str, Any]]],
        ) -> dict[str, Any]:
            nonlocal semantic_calls
            semantic_calls += 1
            for bundle in (first, second_path):
                if sha256_bytes((bundle / "configurations.csv").read_bytes()) \
                        != expected_semantic_digest:
                    raise module.SealError("test semantic validator rejected malformed bundle")
            findings_bytes = make_validator_findings(
                first, second_path, module.PINNED_VALIDATOR_SHA256
            )
            outcome = module.validate_validator_findings(
                findings_bytes, identities, records
            )
            stdout_bytes = validator_stdout(findings_bytes, SOURCE_SHA)
            outcome.update(
                {
                    "findings_bytes": findings_bytes,
                    "stdout_bytes": stdout_bytes,
                    "validator_log_sha256": sha256_bytes(stdout_bytes),
                }
            )
            return outcome

        module._run_pinned_validator = strict_test_validator
        tool = module

        input_before = {
            "a": tree_snapshot(source_a),
            "b": tree_snapshot(source_b),
            "provenance": tree_snapshot(provenance),
        }
        baseline = work / "sealed-a"
        second = work / "sealed-b"
        require_create_valid(
            tool, source_a, source_b, provenance, baseline
        )
        require_create_valid(
            tool, source_a, source_b, provenance, second
        )
        input_after = {
            "a": tree_snapshot(source_a),
            "b": tree_snapshot(source_b),
            "provenance": tree_snapshot(provenance),
        }
        if input_after != input_before:
            raise AssertionError("create altered one or more input trees")
        if tree_snapshot(baseline) != tree_snapshot(second):
            raise AssertionError("independent create outputs are not byte-identical")
        require_verify_valid(tool, baseline)

        copied_ci = json.loads(
            (baseline / "ci/metadata.json").read_text(encoding="utf-8")
        )
        if copied_ci["conclusion"] != "success":
            raise AssertionError(
                "create altered the captured independent CI success status"
            )

        # The only accepted differing-run route is explicit preserved negative
        # evidence.  Both synthetic bundles retain their self-consistent inner
        # manifests; the independent comparator inventories the changed data
        # artifact and manifest, forces STOP/no-promotion, and the seal binds
        # that exact result.
        divergent_a = work / "divergent-source-a"
        divergent_b = work / "divergent-source-b"
        divergent_provenance = work / "divergent-provenance"
        shutil.copytree(source_a, divergent_a)
        shutil.copytree(source_b, divergent_b)
        (divergent_b / "operator_entries.csv").write_bytes(
            (divergent_b / "operator_entries.csv").read_bytes()
            + b"synthetic independently valid divergent row\n"
        )
        refresh_inner(divergent_b)
        make_provenance(
            divergent_provenance,
            divergent_a,
            divergent_b,
            module.PINNED_VALIDATOR_SHA256,
        )
        divergent_seal = work / "sealed-preserved-negative"
        require_create_valid(
            tool,
            divergent_a,
            divergent_b,
            divergent_provenance,
            divergent_seal,
        )
        require_verify_valid(tool, divergent_seal)
        divergent_manifest = json.loads(
            (divergent_seal / OUTER_MANIFEST).read_text(encoding="utf-8")
        )
        divergent_findings = json.loads(
            (divergent_seal / VALIDATOR_FINDINGS_PATH).read_text(
                encoding="utf-8"
            )
        )
        if (
            divergent_manifest["validator_findings"]["evidence_route"]
            != "preserved_negative"
            or divergent_findings["comparison_status"]
            != "nondeterministic"
            or divergent_findings["decision"] != STOP_DECISION
            or divergent_findings["promotion"] is not False
            or not divergent_findings["mismatches"]
        ):
            raise AssertionError(
                "differing-run seal did not preserve the frozen negative route"
            )

        # Byte-identical bundles cannot be relabeled as divergent merely by
        # toggling producer summaries.  Even a self-consistent captured STOP
        # result remains invalid for this contradictory route.
        claimed_divergent_a = work / "claimed-divergent-source-a"
        claimed_divergent_b = work / "claimed-divergent-source-b"
        claimed_divergent_provenance = work / "claimed-divergent-provenance"
        shutil.copytree(source_a, claimed_divergent_a)
        shutil.copytree(source_b, claimed_divergent_b)
        for bundle in (claimed_divergent_a, claimed_divergent_b):
            summary = json.loads(
                (bundle / "summary.json").read_text(encoding="utf-8")
            )
            summary["nondeterminism_detected"] = True
            write_json(bundle / "summary.json", summary)
            refresh_inner(bundle)
        make_provenance(
            claimed_divergent_provenance,
            claimed_divergent_a,
            claimed_divergent_b,
            module.PINNED_VALIDATOR_SHA256,
        )
        require_create_invalid(
            tool,
            claimed_divergent_a,
            claimed_divergent_b,
            claimed_divergent_provenance,
            work / "must-not-seal-identical-divergence-claim",
            "identical-but-claimed-divergent",
        )

        # A byte difference does not waive semantic validation.  This
        # self-manifested malformed synthetic bundle is rejected by the strict
        # independent test validator rather than being sealed as nondeterminism.
        malformed_divergent_a = work / "malformed-divergent-source-a"
        malformed_divergent_b = work / "malformed-divergent-source-b"
        malformed_divergent_provenance = work / "malformed-divergent-provenance"
        shutil.copytree(source_a, malformed_divergent_a)
        shutil.copytree(source_b, malformed_divergent_b)
        (malformed_divergent_b / "configurations.csv").write_bytes(
            b"self-manifested but semantically malformed divergent bytes\n"
        )
        refresh_inner(malformed_divergent_b)
        make_provenance(
            malformed_divergent_provenance,
            malformed_divergent_a,
            malformed_divergent_b,
            module.PINNED_VALIDATOR_SHA256,
        )
        require_create_invalid(
            tool,
            malformed_divergent_a,
            malformed_divergent_b,
            malformed_divergent_provenance,
            work / "must-not-seal-malformed-divergence",
            "malformed-divergent-bundle",
        )

        mutation_count = 0

        # Make a contradictory nondeterminism result internally self-consistent
        # at every captured layer (findings self-hash, stdout digest, metadata,
        # outer binding and outer pre-hash).  Fresh pinned replay must still
        # reject it byte-for-byte because the actual differing bundles require
        # the frozen STOP decision.
        contradictory_target = work / (
            f"mutation-{mutation_count:02d}-contradictory-result"
        )
        shutil.copytree(divergent_seal, contradictory_target)
        contradictory_path = contradictory_target / VALIDATOR_FINDINGS_PATH
        contradictory = json.loads(
            contradictory_path.read_text(encoding="utf-8")
        )
        contradictory["decision"] = (
            "retain_central_relational_representation_for_research"
        )
        pre_hash_payload = {
            key: value
            for key, value in contradictory.items()
            if key != "result_sha256_before_hash_field"
        }
        contradictory["result_sha256_before_hash_field"] = sha256_bytes(
            canonical_json_bytes(pre_hash_payload, pretty=False)
        )
        contradictory_bytes = canonical_json_bytes(
            contradictory, pretty=True
        )
        contradictory_path.write_bytes(contradictory_bytes)
        contradictory_log = validator_stdout(
            contradictory_bytes, SOURCE_SHA
        )
        (contradictory_target / VALIDATOR_LOG_PATH).write_bytes(
            contradictory_log
        )
        contradictory_binding = validator_binding(
            contradictory_bytes, contradictory_log
        )
        contradictory_metadata = json.loads(
            (contradictory_target / "metadata.json").read_text(
                encoding="utf-8"
            )
        )
        contradictory_metadata["validator_findings"] = (
            contradictory_binding
        )
        write_json(
            contradictory_target / "metadata.json",
            contradictory_metadata,
        )
        contradictory_outer = json.loads(
            (contradictory_target / OUTER_MANIFEST).read_text(
                encoding="utf-8"
            )
        )
        contradictory_outer["validator_findings"] = (
            contradictory_binding
        )
        write_json(
            contradictory_target / OUTER_MANIFEST,
            contradictory_outer,
        )
        refresh_outer(contradictory_target)
        require_invalid(
            tool, contradictory_target, "contradictory-validator-result"
        )
        mutation_count += 1

        def mutation(
            label: str,
            change: Callable[[Path], None],
            *,
            refresh: bool = False,
        ) -> None:
            nonlocal mutation_count
            target = work / f"mutation-{mutation_count:02d}-{label}"
            shutil.copytree(baseline, target)
            change(target)
            if refresh:
                refresh_outer(target)
            require_invalid(tool, target, label)
            mutation_count += 1

        mutation(
            "unrefreshed-byte",
            lambda root: (root / "logs/build.log").write_text(
                "tampered\n", encoding="utf-8"
            ),
        )
        mutation(
            "unrefreshed-extra",
            lambda root: (root / "unregistered-extra.txt").write_text(
                "extra\n", encoding="utf-8"
            ),
        )
        mutation(
            "empty-directory-addition",
            lambda root: (root / "empty-extra").mkdir(),
        )
        mutation(
            "refreshed-missing-required-log",
            lambda root: (root / "logs/ctest.log").unlink(),
            refresh=True,
        )

        def invalid_source_sha(root: Path) -> None:
            mutate_json(
                root,
                "metadata.json",
                lambda value: value["source"].__setitem__(
                    "sha", "deadbeef"
                ),
            )

        mutation(
            "refreshed-invalid-source-sha",
            invalid_source_sha,
            refresh=True,
        )

        def missing_command(root: Path) -> None:
            def change(value: dict[str, Any]) -> None:
                value["commands"] = [
                    row
                    for row in value["commands"]
                    if row["name"] != "source_scan"
                ]

            mutate_json(root, "metadata.json", change)

        mutation(
            "refreshed-missing-command", missing_command, refresh=True
        )

        def validator_without_compare(root: Path) -> None:
            def change(value: dict[str, Any]) -> None:
                row = next(
                    item
                    for item in value["commands"]
                    if item["name"] == "bundle_compare_validator"
                )
                index = row["argv"].index("--compare")
                del row["argv"][index : index + 2]

            mutate_json(root, "metadata.json", change)

        mutation(
            "refreshed-validator-command",
            validator_without_compare,
            refresh=True,
        )

        def failed_validator_result(root: Path) -> None:
            def change(value: dict[str, Any]) -> None:
                result = value["local"]["result_summaries"][
                    "bundle_compare_validator"
                ]
                result["status"] = "fail"
                result["exit_code"] = 1

            mutate_json(root, "metadata.json", change)

        mutation(
            "refreshed-validator-not-pass",
            failed_validator_result,
            refresh=True,
        )

        def failed_build_result(root: Path) -> None:
            def change(value: dict[str, Any]) -> None:
                result = value["local"]["result_summaries"]["build"]
                result["status"] = "fail"
                result["exit_code"] = 1

            mutate_json(root, "metadata.json", change)

        mutation(
            "refreshed-build-not-pass",
            failed_build_result,
            refresh=True,
        )
        mutation(
            "refreshed-validator-marker",
            lambda root: (
                root / "logs/full-bundle-validator.log"
            ).write_text("exit code 0 without validator output\n", encoding="utf-8"),
            refresh=True,
        )

        def missing_ctest_location(root: Path) -> None:
            mutate_json(
                root,
                "metadata.json",
                lambda value: value["local"]["result_summaries"][
                    "ctest"
                ].__setitem__(
                    "evidence_paths", ["logs/build.log"]
                ),
            )

        mutation(
            "refreshed-ctest-location",
            missing_ctest_location,
            refresh=True,
        )
        mutation(
            "refreshed-local-context",
            lambda root: mutate_json(
                root,
                "metadata.json",
                lambda value: value["local"].__setitem__(
                    "execution_context", "independent_ci"
                ),
            ),
            refresh=True,
        )
        mutation(
            "refreshed-ci-context",
            lambda root: mutate_json(
                root,
                "ci/metadata.json",
                lambda value: value.__setitem__(
                    "claim_kind", "independent_ci"
                ),
            ),
            refresh=True,
        )
        mutation(
            "refreshed-ci-source-sha",
            lambda root: mutate_json(
                root,
                "ci/metadata.json",
                lambda value: value.__setitem__(
                    "head_sha", "0" * 40
                ),
            ),
            refresh=True,
        )
        mutation(
            "refreshed-ci-run-failure",
            lambda root: mutate_json(
                root,
                "ci/metadata.json",
                lambda value: value.__setitem__("conclusion", "failure"),
            ),
            refresh=True,
        )

        def failed_ci_job(root: Path) -> None:
            def change(value: dict[str, Any]) -> None:
                value["jobs"][0]["conclusion"] = "failure"

            mutate_json(root, "ci/metadata.json", change)

        mutation(
            "refreshed-ci-job-failure",
            failed_ci_job,
            refresh=True,
        )
        mutation(
            "refreshed-stale-inner-manifest",
            lambda root: (
                root / "bundles/full-a/configurations.csv"
            ).write_text("changed with stale inner manifest\n", encoding="utf-8"),
            refresh=True,
        )

        def divergent_full_bundle(root: Path) -> None:
            path = root / "bundles/full-a/configurations.csv"
            path.write_text(
                "self-consistently changed only in run A\n",
                encoding="utf-8",
            )
            refresh_inner(path.parent)

        mutation(
            "refreshed-divergent-full-runs",
            divergent_full_bundle,
            refresh=True,
        )

        def malformed_both(root: Path) -> None:
            for relative in ("bundles/full-a", "bundles/full-b"):
                bundle = root / relative
                (bundle / "configurations.csv").write_text(
                    "self-consistent but semantically malformed\n", encoding="utf-8"
                )
                refresh_inner(bundle)

        mutation(
            "refreshed-byte-identical-semantic-malformation",
            malformed_both,
            refresh=True,
        )

        # Mutate both byte-identical bundles so this penetrates the equality
        # gate and exercises the clean-source requirement itself.
        def dirty_both(root: Path) -> None:
            for relative in ("bundles/full-a", "bundles/full-b"):
                bundle = root / relative
                value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
                value["dirty"] = True
                write_json(bundle / "summary.json", value)
                refresh_inner(bundle)

        mutation("refreshed-dirty-full-bundles", dirty_both, refresh=True)

        def nondeterministic_both(root: Path) -> None:
            for relative in ("bundles/full-a", "bundles/full-b"):
                bundle = root / relative
                value = json.loads((bundle / "summary.json").read_text(encoding="utf-8"))
                value["nondeterminism_detected"] = True
                write_json(bundle / "summary.json", value)
                refresh_inner(bundle)

        mutation(
            "refreshed-nondeterministic-full-bundles",
            nondeterministic_both,
            refresh=True,
        )

        def extra_inner_schema_member(root: Path) -> None:
            mutate_json(
                root,
                "bundles/full-a/manifest.json",
                lambda value: value.__setitem__("ambiguous", True),
            )

        mutation(
            "refreshed-extra-inner-member",
            extra_inner_schema_member,
            refresh=True,
        )

        def duplicate_metadata_member(root: Path) -> None:
            path = root / "metadata.json"
            raw = path.read_text(encoding="utf-8")
            path.write_text(
                raw.replace(
                    "{\n",
                    "{\n"
                    f'  "schema": "{METADATA_SCHEMA}",\n',
                    1,
                ),
                encoding="utf-8",
            )

        mutation(
            "refreshed-duplicate-json-member",
            duplicate_metadata_member,
            refresh=True,
        )

        mutation(
            "refreshed-negative-zero-json",
            lambda root: (
                root / "ci/metadata.json"
            ).write_bytes(
                (root / "ci/metadata.json")
                .read_bytes()
                .replace(b'"run_id": 123456', b'"run_id": -0')
            ),
            refresh=True,
        )

        def compact_metadata(root: Path) -> None:
            path = root / "metadata.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            path.write_bytes(
                json.dumps(
                    value, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            )

        mutation(
            "refreshed-noncanonical-compact-metadata",
            compact_metadata,
            refresh=True,
        )

        mutation(
            "refreshed-noncanonical-crlf-inner-manifest",
            lambda root: (
                root / "bundles/full-a/manifest.json"
            ).write_bytes(
                (root / "bundles/full-a/manifest.json")
                .read_bytes()
                .replace(b"\n", b"\r\n")
            ),
            refresh=True,
        )

        def noncanonical_outer(
            label: str, encode: Callable[[dict[str, Any]], bytes]
        ) -> None:
            nonlocal mutation_count
            target = work / f"mutation-{mutation_count:02d}-{label}"
            shutil.copytree(baseline, target)
            path = target / OUTER_MANIFEST
            value = json.loads(path.read_text(encoding="utf-8"))
            path.write_bytes(encode(value))
            require_invalid(tool, target, label)
            mutation_count += 1

        noncanonical_outer(
            "compact-outer-json",
            lambda value: json.dumps(
                value, sort_keys=True, separators=(",", ":")
            ).encode("utf-8"),
        )
        noncanonical_outer(
            "crlf-outer-json",
            lambda value: (
                json.dumps(value, indent=2, sort_keys=True) + "\n"
            ).replace("\n", "\r\n").encode("utf-8"),
        )
        noncanonical_outer(
            "trailing-outer-json",
            lambda value: (
                json.dumps(value, indent=2, sort_keys=True) + "\n \n"
            ).encode("utf-8"),
        )
        noncanonical_outer(
            "member-order-outer-json",
            lambda value: (
                json.dumps(
                    dict(reversed(tuple(value.items()))),
                    indent=2,
                    sort_keys=False,
                )
                + "\n"
            ).encode("utf-8"),
        )

        def duplicate_outer_member(value: dict[str, Any]) -> bytes:
            canonical = (
                json.dumps(value, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            return canonical.replace(
                b"{\n",
                b'{\n  "algorithm": "SHA-256",\n',
                1,
            )

        noncanonical_outer(
            "duplicate-member-outer-json", duplicate_outer_member
        )

        def wrong_outer_schema(root: Path) -> None:
            value = json.loads(
                (root / OUTER_MANIFEST).read_text(encoding="utf-8")
            )
            value["schema"] = OUTER_SCHEMA + ".other"
            payload = {
                key: item
                for key, item in value.items()
                if key != "pre_hash_sha256"
            }
            value["pre_hash_sha256"] = sha256_bytes(
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            )
            write_json(root / OUTER_MANIFEST, value)

        mutation("self-consistent-outer-schema", wrong_outer_schema)

        def duplicate_outer_path(root: Path) -> None:
            value = json.loads(
                (root / OUTER_MANIFEST).read_text(encoding="utf-8")
            )
            duplicate = dict(value["files"][0])
            duplicate["path"] = duplicate["path"].upper()
            value["files"].append(duplicate)
            value["files"].sort(key=lambda row: row["path"])
            payload = {
                key: item
                for key, item in value.items()
                if key != "pre_hash_sha256"
            }
            value["pre_hash_sha256"] = sha256_bytes(
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            )
            write_json(root / OUTER_MANIFEST, value)

        mutation(
            "self-consistent-case-colliding-manifest",
            duplicate_outer_path,
        )

        def traversal_outer_path(root: Path) -> None:
            value = json.loads(
                (root / OUTER_MANIFEST).read_text(encoding="utf-8")
            )
            value["files"][0]["path"] = "../outside"
            value["files"].sort(key=lambda row: row["path"])
            payload = {
                key: item
                for key, item in value.items()
                if key != "pre_hash_sha256"
            }
            value["pre_hash_sha256"] = sha256_bytes(
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            )
            write_json(root / OUTER_MANIFEST, value)

        mutation("self-consistent-traversal-path", traversal_outer_path)

        # A transient A->B->A change in the live seal cannot affect semantic
        # validation because the validator receives only a private digest-
        # checked snapshot.  Start and end bytes are intentionally identical;
        # this is a containment test, not a claim that an unobservable transient
        # write can be detected after restoration.
        aba_target = work / "race-a-b-a-contained"
        shutil.copytree(baseline, aba_target)
        ordinary_validator = module._run_pinned_validator
        live_configuration = (
            aba_target / "bundles/full-a/configurations.csv"
        )
        live_configuration_a = live_configuration.read_bytes()

        def aba_validator(
            first: Path,
            second_path: Path,
            identities: Sequence[Mapping[str, Any]],
            records: Sequence[Sequence[Mapping[str, Any]]],
        ) -> dict[str, Any]:
            if first.resolve().is_relative_to(aba_target.resolve()):
                raise AssertionError("validator received the live seal tree")
            live_configuration.write_bytes(b"transient B bytes\n")
            try:
                if first.joinpath("configurations.csv").read_bytes() \
                        != live_configuration_a:
                    raise AssertionError("private snapshot followed live A->B write")
            finally:
                live_configuration.write_bytes(live_configuration_a)
            return ordinary_validator(
                first, second_path, identities, records
            )

        module._run_pinned_validator = aba_validator
        try:
            require_verify_valid(tool, aba_target)
        finally:
            module._run_pinned_validator = ordinary_validator

        # The root manifest is parsed from one bounded read.  A temporary live
        # manifest substitution during evidence copying must not become the
        # semantic manifest and must not alter a restored valid seal.
        manifest_aba_target = work / "race-manifest-a-b-a-contained"
        shutil.copytree(baseline, manifest_aba_target)
        ordinary_copy_records = module._copy_records
        live_manifest = manifest_aba_target / OUTER_MANIFEST
        live_manifest_a = live_manifest.read_bytes()

        def manifest_aba_copy(
            source_root: Path,
            destination_root: Path,
            records: Sequence[Mapping[str, Any]],
        ) -> None:
            if source_root.resolve() == manifest_aba_target.resolve():
                live_manifest.write_bytes(b'{"transient":"B"}\n')
                try:
                    ordinary_copy_records(source_root, destination_root, records)
                finally:
                    live_manifest.write_bytes(live_manifest_a)
            else:
                ordinary_copy_records(source_root, destination_root, records)

        module._copy_records = manifest_aba_copy
        try:
            require_verify_valid(tool, manifest_aba_target)
        finally:
            module._copy_records = ordinary_copy_records

        # A content substitution during the immutable-snapshot copy itself is
        # not benign: the copied digest differs from the manifest and must fail
        # even if the live pathname is restored to A before final rescan.
        copy_race_target = work / "race-copy-b-then-a-rejected"
        shutil.copytree(baseline, copy_race_target)
        copy_race_file = copy_race_target / "bundles/full-a/configurations.csv"
        copy_race_a = copy_race_file.read_bytes()
        ordinary_copy_records = module._copy_records

        def content_race_copy(
            source_root: Path,
            destination_root: Path,
            records: Sequence[Mapping[str, Any]],
        ) -> None:
            if source_root.resolve() == copy_race_target.resolve():
                copy_race_file.write_bytes(b"transient copied B bytes\n")
                try:
                    ordinary_copy_records(source_root, destination_root, records)
                finally:
                    copy_race_file.write_bytes(copy_race_a)
            else:
                ordinary_copy_records(source_root, destination_root, records)

        module._copy_records = content_race_copy
        try:
            require_invalid(tool, copy_race_target, "copy-content-race")
        finally:
            module._copy_records = ordinary_copy_records
        mutation_count += 1

        # Simulate a concurrent writer that changes a sealed artifact only
        # after the semantic validator has completed.  The verifier's final
        # rescan must close this TOCTOU window.
        race_target = work / f"mutation-{mutation_count:02d}-during-validator"
        shutil.copytree(baseline, race_target)
        ordinary_validator = module._run_pinned_validator

        def mutating_validator(
            first: Path,
            second_path: Path,
            identities: Sequence[Mapping[str, Any]],
            records: Sequence[Sequence[Mapping[str, Any]]],
        ) -> dict[str, Any]:
            output = ordinary_validator(
                first, second_path, identities, records
            )
            (first / "configurations.csv").write_bytes(
                (first / "configurations.csv").read_bytes() + b"concurrent mutation\n"
            )
            return output

        module._run_pinned_validator = mutating_validator
        try:
            require_invalid(tool, race_target, "mutation-during-validator")
        finally:
            module._run_pinned_validator = ordinary_validator
        mutation_count += 1

        try:
            module.ensure_unique_portable_paths(
                ("Logs/A.log", "logs/a.LOG"), "test"
            )
        except module.SealError:
            pass
        else:
            raise AssertionError(
                "portable case-collision helper accepted a collision"
            )
        try:
            module.ensure_unique_portable_paths(("logs/con",), "test")
        except module.SealError:
            pass
        else:
            raise AssertionError(
                "portable path helper accepted a reserved component"
            )

        def expect_seal_error(
            label: str, operation: Callable[[], Any], marker: str | None = None
        ) -> None:
            try:
                operation()
            except module.SealError as error:
                if marker is not None and marker not in str(error):
                    raise AssertionError(
                        f"{label}: expected {marker!r}, got {error!r}"
                    ) from error
            else:
                raise AssertionError(f"{label}: expected SealError")

        unsafe_paths = {
            "absolute": "/absolute/path",
            "windows-absolute": "C:/absolute/path",
            "backslash": "logs\\injected.log",
            "parent": "../outside",
            "deep": "/".join("a" for _ in range(module.MAX_PATH_DEPTH + 1)),
            "long-component": "a" * (module.MAX_COMPONENT_UTF8_BYTES + 1),
            "long-path": "/".join(
                "a" * (module.MAX_PATH_UTF8_BYTES // module.MAX_PATH_DEPTH)
                for _ in range(module.MAX_PATH_DEPTH)
            ),
            "non-utf8-surrogate": "logs/\ud800.log",
        }
        for label, unsafe in unsafe_paths.items():
            expect_seal_error(
                f"unsafe-path-{label}",
                lambda unsafe=unsafe: module.ensure_unique_portable_paths(
                    (unsafe,), "resource regression"
                ),
            )

        expect_seal_error(
            "negative-zero-json",
            lambda: module.read_json_bytes(b'{"value":-0}\n', "negative-zero"),
            "negative-zero",
        )
        expect_seal_error(
            "floating-json",
            lambda: module.read_json_bytes(b'{"value":1e0}\n', "float"),
            "floating JSON number",
        )

        scan_cases = work / "resource-scan-cases"
        scan_cases.mkdir()
        too_many = scan_cases / "too-many-files"
        too_many.mkdir()
        for index in range(module.MAX_REGULAR_FILES + 1):
            (too_many / f"f{index:03d}").write_bytes(b"x")
        expect_seal_error(
            "regular-file-count-cap",
            lambda: module.scan_regular_files(too_many),
            "count cap",
        )

        too_many_directories = scan_cases / "too-many-directories"
        too_many_directories.mkdir()
        for index in range(module.MAX_DIRECTORIES):
            child = too_many_directories / f"d{index:03d}"
            child.mkdir()
            (child / "value").write_bytes(b"x")
        expect_seal_error(
            "directory-count-cap",
            lambda: module.scan_regular_files(too_many_directories),
            "directory-count cap",
        )

        too_deep = scan_cases / "too-deep"
        deep_cursor = too_deep
        for _ in range(module.MAX_PATH_DEPTH + 1):
            deep_cursor /= "d"
        deep_cursor.mkdir(parents=True)
        (deep_cursor / "value").write_bytes(b"x")
        expect_seal_error(
            "filesystem-depth-cap",
            lambda: module.scan_regular_files(too_deep),
            "depth cap",
        )

        long_component_root = scan_cases / "long-component"
        long_component_root.mkdir()
        original_component_cap = module.MAX_COMPONENT_UTF8_BYTES
        module.MAX_COMPONENT_UTF8_BYTES = 16
        try:
            (long_component_root / ("x" * 17)).write_bytes(b"x")
            expect_seal_error(
                "filesystem-component-cap",
                lambda: module.scan_regular_files(long_component_root),
                "component exceeds",
            )
        finally:
            module.MAX_COMPONENT_UTF8_BYTES = original_component_cap

        oversized = scan_cases / "oversized"
        oversized.write_bytes(b"0123456789")
        expect_seal_error(
            "per-file-byte-cap",
            lambda: module._hash_regular_file(oversized, 9),
            "byte cap",
        )

        total_cap_root = scan_cases / "total-cap"
        total_cap_root.mkdir()
        (total_cap_root / "a").write_bytes(b"12345678")
        (total_cap_root / "b").write_bytes(b"12345678")
        original_total_cap = module.MAX_SEAL_BYTES
        module.MAX_SEAL_BYTES = 15
        try:
            expect_seal_error(
                "total-byte-cap",
                lambda: module.scan_regular_files(total_cap_root),
                "total byte cap",
            )
        finally:
            module.MAX_SEAL_BYTES = original_total_cap

        too_many_manifest_records = [
            {
                "path": f"f{index:03d}",
                "sha256": "0" * 64,
                "size": 0,
            }
            for index in range(module.MAX_REGULAR_FILES + 1)
        ]
        expect_seal_error(
            "manifest-record-count-cap",
            lambda: module._validate_manifest_records(
                too_many_manifest_records
            ),
            "file-count cap",
        )

        symlink_result = "not-supported"
        symlink_target = work / "symlink-case"
        shutil.copytree(baseline, symlink_target)
        try:
            os.symlink(
                symlink_target / "logs/build.log",
                symlink_target / "linked.log",
            )
        except (OSError, NotImplementedError):
            pass
        else:
            require_invalid(tool, symlink_target, "symlink")
            mutation_count += 1
            symlink_result = "rejected"

        if semantic_calls < 3:
            raise AssertionError("production seal flow did not invoke semantic validation")

    print(
        "mechanical observability outer seal mutation regression PASS "
        "(immutable-input copy + deterministic create + positive verify + "
        f"{mutation_count} verification mutations; real malformed bundle rejected; "
        "2 A->B->A races contained by immutable snapshot/single-read manifest; "
        "pinned bytes isolated from source-path and Python environment injection; "
        "portable path ambiguity rejected; "
        f"symlink={symlink_result})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
