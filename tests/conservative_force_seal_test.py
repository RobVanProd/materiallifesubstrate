#!/usr/bin/env python3
"""Adversarial mutation regression for the conservative-force outer seal."""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import pathlib
import tempfile
from types import SimpleNamespace
from typing import Callable
import zipfile


TEST_DECISION = "retain_conservative_relational_force_for_research"


def load_tool(path: pathlib.Path | None = None):
    if path is None:
        path = pathlib.Path(__file__).resolve().parents[1] / "tools" / \
            "seal_conservative_force_consistency_evidence.py"
    path = path.resolve(strict=True)
    spec = importlib.util.spec_from_file_location("conservative_force_sealer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load conservative-force evidence sealer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect_rejection(tool, operation: Callable[[], object], label: str) -> None:
    try:
        operation()
    except tool.SealError:
        return
    raise RuntimeError(f"seal accepted {label} mutation")


def receipt(tool, source_sha: str, output: str, *, label: str = "test",
            command: list[str] | None = None,
            cwd: str = "D:/MaterialLifeSubstrate") -> dict:
    payload = output.encode("utf-8")
    return {
        "schema": tool.RECEIPT_SCHEMA,
        "label": label,
        "source_sha": source_sha,
        "branch": tool.BRANCH,
        "cwd": cwd,
        "command": command or ["test", "--exact"],
        "started_at_utc": "2026-08-30T00:00:00Z",
        "ended_at_utc": "2026-08-30T00:00:01Z",
        "exit_code": 0,
        "output_bytes": len(payload),
        "output_sha256": tool.sha256_bytes(payload),
        "output": output,
    }


def valid_receipts(tool, source_sha: str, root: pathlib.Path) -> dict[str, dict]:
    repo = root / "repo"
    build = root / "build"
    raw_a = root / "raw-a"
    raw_b = root / "raw-b"
    bundle_a = root / "bundle-a"
    bundle_b = root / "bundle-b"
    commands = {
        "configure.json": [
            "cmake", "-S", str(repo), "-B", str(build),
            "-DCMAKE_CXX_COMPILER=" + str(root / "cxx"),
            "-DMLS_WARNINGS_AS_ERRORS=ON",
            "-DMLS_RUN_EXTENDED_EXACT_TESTS=ON",
        ],
        "build.json": ["cmake", "--build", str(build)],
        "ctest.json": [
            "ctest", "--test-dir", str(build), "--output-on-failure"
        ],
        "raw-producer-a.json": [
            str(build / "mls_conservative_force_consistency_diagnostic.exe"),
            "--fixture-bundle", str(root / "accepted-parent"),
            "--output", str(raw_a),
        ],
        "raw-producer-b.json": [
            str(build / "mls_conservative_force_consistency_diagnostic.exe"),
            "--fixture-bundle", str(root / "accepted-parent"),
            "--output", str(raw_b),
        ],
        "materialize-a.json": [
            "python", "reference/validate_conservative_force_bundle.py",
            "materialize", "--producer", str(raw_a), "--output", str(bundle_a),
        ],
        "materialize-b.json": [
            "python", "reference/validate_conservative_force_bundle.py",
            "materialize", "--producer", str(raw_b), "--output", str(bundle_b),
        ],
        "twin-compare.json": [
            "python", "reference/validate_conservative_force_bundle.py",
            "validate", "--bundle", str(bundle_a), "--compare", str(bundle_b),
        ],
        "validator.json": [
            "python", "reference/validate_conservative_force_bundle.py",
            "validate", "--bundle", str(bundle_b), "--compare", str(bundle_a),
        ],
        "validator-regression.json": [
            "python", "tests/conservative_force_bundle_validator_test.py",
            "--validator", "reference/validate_conservative_force_bundle.py",
            "--producer", str(raw_a),
            "--producer-compare", str(raw_b),
        ],
        "exact-oracle.json": [
            "python", "reference/conservative_force_oracle.py",
            "--verify", "tests/conservative_force_oracle.canonical.json",
        ],
        "exact-oracle-regression.json": [
            "python", "tests/conservative_force_oracle_test.py",
            "--oracle", "reference/conservative_force_oracle.py",
            "--canonical", "tests/conservative_force_oracle.canonical.json",
        ],
        "lean-build.json": [str(root / "lake"), "--wfail", "build"],
        "lean-axioms.json": [
            str(root / "lake"), "env", "lean", "MLSFormal/AxiomReport.lean"
        ],
        "formal-trust.json": [
            "python", "tools/formal_trust_scan.py", "--formal-root", "formal",
        ],
        "compiler-versions.json": [
            "python", "tools/conservative_force_tool_versions.py",
            "--repo", str(repo), "--source-sha", source_sha,
            "--branch", tool.BRANCH, "--cxx", str(root / "cxx"),
            "--lake", str(root / "lake"),
        ],
        "parent-evidence.json": [
            "python", "tools/verify_force_parent_evidence.py",
            "--parent-bundle", str(root / "accepted-parent"), "--verify",
        ],
    }
    outputs = {
        "configure.json": "Build files have been written\n",
        "build.json": "mls_conservative_force_consistency_diagnostic\n",
        "ctest.json": "100% tests passed, 0 tests failed out of 78\n",
        "raw-producer-a.json": (
            "CONSERVATIVE FORCE RAW BUNDLE COMPLETE\n"
            "stage=pending_independent_stage\n" + tool.NO_PROMOTION + "\n"),
        "raw-producer-b.json": (
            "CONSERVATIVE FORCE RAW BUNDLE COMPLETE\n"
            "stage=pending_independent_stage\n" + tool.NO_PROMOTION + "\n"),
        "materialize-a.json": (
            "CONSERVATIVE FORCE BUNDLE MATERIALIZED decision=" + TEST_DECISION +
            "\n" + tool.NO_PROMOTION + "\n"),
        "materialize-b.json": (
            "CONSERVATIVE FORCE BUNDLE MATERIALIZED decision=" + TEST_DECISION +
            "\n" + tool.NO_PROMOTION + "\n"),
        "twin-compare.json": (
            "CONSERVATIVE FORCE BUNDLE VALID " + TEST_DECISION +
            " " + tool.NO_PROMOTION + "\n"),
        "validator.json": (
            "CONSERVATIVE FORCE BUNDLE VALID " + TEST_DECISION +
            " " + tool.NO_PROMOTION + "\n"),
        "validator-regression.json": "PASS\n",
        "exact-oracle.json": (
            '"schema": "mls.conservative-force-consistency.'
            'high-precision-oracle.v1"\n"result_boundary": '
            '"NO PROMOTION to dynamics"\n'),
        "exact-oracle-regression.json": "PASS\n",
        "lean-build.json": "Build completed successfully\n",
        "lean-axioms.json": (
            "linearizedRelationalForce_power_identity\n"
            "finiteCentralRelationForces_total_torque_zero\n"),
        "formal-trust.json": "PASS: no sorry, admit, sorryAx\n",
        "compiler-versions.json": (
            "source_sha=" + source_sha + "\n"
            "source_branch=" + tool.BRANCH + "\n"
            "source_status_begin\nsource_status_end\n"
            "seed=260828\n"
            "binary64_contract="
            "iec559_size8_digits53_explicit_order_fp_contract_off_v1\n"
            "lean_toolchain=leanprover/lean4:v4.33.0-rc1\n"
            "lake_manifest_sha256=" + "a" * 64 + "\n"
            "mathlib_commit=" + "b" * 40 + "\n" +
            "".join(
                name + "_command=" +
                (str(root / name) if name in {"cxx", "lake"}
                 else "/tools/" + name) + "\n" +
                name + "_cwd=/work\n" +
                name + "_version_begin\n" + name + " 1.0\n" +
                name + "_version_end\n"
                for name in (
                    "git", "cmake", "ctest", "ninja", "cxx", "python",
                    "elan", "lean", "lake")
            )),
        "parent-evidence.json": (
            "force parent evidence: PASS\nsource_sha=" + tool.PARENT_SHA +
            "\nmanifest_pre_hash=" + tool.PARENT_EVIDENCE_PRE_HASH + "\n" +
            "\n".join(name + "=" + digest
                       for name, digest in tool.PARENT_TABLE_SHA256.items()) + "\n"),
    }
    result = {
        name: receipt(
            tool, source_sha, outputs[name], label=pathlib.Path(name).stem,
            command=command, cwd=str(repo),
        )
        for name, command in commands.items()
    }
    result["lean-build.json"]["cwd"] = str(repo / "formal")
    result["lean-axioms.json"]["cwd"] = str(repo / "formal")
    return result


def valid_ci(tool, source_sha: str) -> dict:
    return {
        "attempt": 1,
        "conclusion": "success",
        "databaseId": 77,
        "headBranch": tool.BRANCH,
        "headSha": source_sha,
        "jobs": [
            {"name": name, "conclusion": "success"}
            for name in sorted(tool.REQUIRED_CI_JOBS)
        ],
        "name": tool.WORKFLOW_NAME,
        "status": "completed",
        "workflowName": tool.WORKFLOW_NAME,
        "url": "https://example.invalid/run/77",
    }


def zip_payload(files: dict[str, str]) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in sorted(files.items()):
            archive.writestr(name, value)
    return payload.getvalue()


def valid_artifact_downloads(tool, source_sha: str, run_id: str = "77",
                             attempt: int = 1) -> list[tuple[dict, bytes]]:
    names = tool.expected_ci_artifact_names(run_id, attempt)
    contents = {
        "cpp-Linux GCC": {
            "tool-versions.txt": (
                f"source_sha={source_sha}\nsource_status_begin\n"
                "source_status_end\ng++ 15\n"),
            "configure.txt": "Build files have been written\n",
            "build.txt": "build complete\n",
            "ctest.txt": "100% tests passed, 0 tests failed out of 78\n",
        },
        "cpp-Linux Clang": {
            "tool-versions.txt": (
                f"source_sha={source_sha}\nsource_status_begin\n"
                "source_status_end\nclang 21\n"),
            "configure.txt": "Build files have been written\n",
            "build.txt": "build complete\n",
            "ctest.txt": "100% tests passed, 0 tests failed out of 78\n",
        },
        "cpp-Windows MSVC": {
            "tool-versions.txt": (
                f"source_sha={source_sha}\nsource_status_begin\n"
                "source_status_end\nMSVC 19\n"),
            "configure.txt": "Build files have been written\n",
            "build.txt": "build complete\n",
            # Current CTest/MSVC emits this standard success form without the
            # redundant `0 tests failed` clause.
            "ctest.txt": "100% tests passed out of 78\n",
        },
        "exact-oracle": {
            "python-version.txt": f"source_sha={source_sha}\nPython 3.13\n",
            "conservative-force-oracle.txt":
                "mls.conservative-force-consistency.high-precision-oracle.v1\n",
            "conservative-force-oracle-regression.txt": "PASS\n",
            "conservative-force-validator-compile.txt": "compile PASS\n",
            "conservative-force-seal.txt": "PASS\n",
        },
        "lean": {
            "lean-tool-versions.txt": f"source_sha={source_sha}\nLean 4.33\n",
            "lean-build.txt": "Build completed successfully\n",
            "lean-axioms.txt":
                "finiteCentralRelationForces_total_torque_zero\n",
            "lean-source-scan.txt": "PASS: no sorry, admit, sorryAx\n",
            "mathlib-commit.txt": "c" * 40 + "\n",
        },
    }
    return [
        ({
            "id": index + 100,
            "name": names[prefix],
            "expired": False,
            "workflow_run": {"id": int(run_id), "head_sha": source_sha},
        }, zip_payload(contents[prefix]))
        for index, prefix in enumerate(sorted(contents))
    ]


def write_receipt_directory(tool, path: pathlib.Path,
                            receipts: dict[str, dict], source_sha: str) -> None:
    path.mkdir()
    for name, value in receipts.items():
        (path / name).write_text(json.dumps(value), encoding="utf-8")
    tool.write_ci_capture_with_artifacts(
        path / "ci-run.json", valid_ci(tool, source_sha), source_sha, "77", 1,
        valid_artifact_downloads(tool, source_sha))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", type=pathlib.Path)
    args = parser.parse_args()
    tool = load_tool(args.tool)
    source_sha = "1" * 40
    mutations = 0

    # The version producer itself refuses a mismatched SHA/branch and a dirty
    # tree; the sealer checks the corresponding receipt markers independently.
    version_path = pathlib.Path(__file__).resolve().parents[1] / "tools" / \
        "conservative_force_tool_versions.py"
    version_spec = importlib.util.spec_from_file_location(
        "conservative_force_tool_versions_test", version_path)
    if version_spec is None or version_spec.loader is None:
        raise RuntimeError("cannot load conservative-force version producer")
    version_tool = importlib.util.module_from_spec(version_spec)
    version_spec.loader.exec_module(version_tool)
    with tempfile.TemporaryDirectory(prefix="mls-force-versions-") as temporary:
        root = pathlib.Path(temporary)
        repo = root / "repo"
        formal = repo / "formal"
        mathlib = formal / ".lake" / "packages" / "mathlib"
        mathlib.mkdir(parents=True)
        (formal / "lean-toolchain").write_text(
            "leanprover/lean4:v4.33.0-rc1\n", encoding="utf-8")
        (formal / "lake-manifest.json").write_text("{}\n", encoding="utf-8")
        bin_dir = root / "bin"
        bin_dir.mkdir()
        for name in ("lake", "lean", "elan", "cxx", "tool"):
            (bin_dir / name).write_text("fixture\n", encoding="utf-8")
        observed_status = ""

        def fake_version_run(command, cwd):
            nonlocal observed_status
            if command[:3] == ["git", "status", "--porcelain=v1"]:
                return observed_status
            if command == ["git", "rev-parse", "HEAD"]:
                return "d" * 40 if cwd == mathlib else source_sha
            if command == ["git", "branch", "--show-current"]:
                return tool.BRANCH
            return "fixture tool version 1.0"

        original_version_run = version_tool.run
        original_executable = version_tool.executable
        original_parse_args = version_tool.parse_args
        try:
            version_tool.run = fake_version_run
            version_tool.executable = lambda value: (
                bin_dir / value if value in {"lake", "cxx"} else bin_dir / "tool")
            values = SimpleNamespace(
                repo=repo, source_sha=source_sha, branch=tool.BRANCH,
                cxx="cxx", lake="lake")
            version_tool.parse_args = lambda: values
            with contextlib.redirect_stdout(io.StringIO()) as captured:
                if version_tool.main() != 0:
                    raise RuntimeError("valid tool-version fixture failed")
            if "source_status_begin\nsource_status_end" not in captured.getvalue():
                raise RuntimeError("tool-version fixture omitted clean-source markers")
            for label, mutate, restore in (
                ("tool-version live SHA", lambda: setattr(values, "source_sha", "2" * 40),
                 lambda: setattr(values, "source_sha", source_sha)),
                ("tool-version live branch", lambda: setattr(values, "branch", "main"),
                 lambda: setattr(values, "branch", tool.BRANCH)),
                ("tool-version dirty source", lambda: None, lambda: None),
            ):
                mutate()
                if label == "tool-version dirty source":
                    observed_status = " M source.cpp"
                try:
                    version_tool.main()
                except RuntimeError:
                    mutations += 1
                else:
                    raise RuntimeError(f"version producer accepted {label}")
                finally:
                    observed_status = ""
                    restore()
        finally:
            version_tool.run = original_version_run
            version_tool.executable = original_executable
            version_tool.parse_args = original_parse_args

    # Exact source provenance is decision-bearing.
    with tempfile.TemporaryDirectory(prefix="mls-conservative-force-bundle-") as temporary:
        bundle = pathlib.Path(temporary)
        summary = {
            "schema": "mls.conservative-force-consistency.summary.v1",
            "full": True,
            "decision": TEST_DECISION,
            "no_promotion": tool.NO_PROMOTION,
            "promotion_permitted": False,
        }
        provenance = {
            "source_sha": source_sha,
            "source_branch": tool.BRANCH,
            "dirty": False,
            "accepted_parent_sha": tool.PARENT_SHA,
            "preregistration_commit": tool.PREREGISTRATION_SHA,
            "inherited_blobs": tool.INHERITED_BLOBS,
        }
        (bundle / "producer").mkdir()
        (bundle / "producer" / "raw_provenance.json").write_text(
            json.dumps({
                "source_sha": source_sha,
                "source_branch": tool.BRANCH,
                "accepted_parent_sha": tool.PARENT_SHA,
                "preregistration_commit": tool.PREREGISTRATION_SHA,
                "dirty": False,
                "full": True,
                "inherited_blobs": tool.INHERITED_BLOBS,
            }),
            encoding="utf-8")
        (bundle / "producer" / "raw_summary.json").write_text(json.dumps({
            "full": True,
            "stage_status": "pending_independent_stage",
            "final_decision_emitted": False,
            "no_promotion": tool.NO_PROMOTION,
            "promotion_permitted": False,
        }), encoding="utf-8")
        (bundle / "producer" / "compression.csv").write_text(
            "evaluation_id,binary64_gradient_error_n\n", encoding="utf-8")
        (bundle / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        (bundle / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
        tool.validate_bundle_claims(bundle, source_sha)
        for allowed in sorted(tool.ALLOWED_DECISIONS):
            summary["decision"] = allowed
            (bundle / "summary.json").write_text(
                json.dumps(summary), encoding="utf-8")
            if tool.validate_bundle_claims(bundle, source_sha)["decision"] != allowed:
                raise RuntimeError("allowed decision was not bound exactly")
        summary["decision"] = "forged_positive_decision"
        (bundle / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        expect_rejection(
            tool, lambda: tool.validate_bundle_claims(bundle, source_sha),
            "unregistered decision",
        )
        mutations += 1
        summary["decision"] = TEST_DECISION
        (bundle / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        summary["no_promotion"] = "NO PROMOTION"
        (bundle / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        expect_rejection(
            tool, lambda: tool.validate_bundle_claims(bundle, source_sha),
            "bundle promotion boundary",
        )
        mutations += 1
        summary["no_promotion"] = tool.NO_PROMOTION
        (bundle / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        compression = bundle / "producer" / "compression.csv"
        compression.write_text(
            "evaluation_id,independent_gradient_error_n\n", encoding="utf-8")
        expect_rejection(
            tool, lambda: tool.validate_bundle_claims(bundle, source_sha),
            "overstated compression gradient provenance",
        )
        mutations += 1
        compression.unlink()
        (bundle / "compression.csv").write_text(
            "evaluation_id,binary64_gradient_error_n\n", encoding="utf-8")
        expect_rejection(
            tool, lambda: tool.validate_bundle_claims(bundle, source_sha),
            "root-level compression decoy",
        )
        mutations += 1
        (bundle / "compression.csv").unlink()
        compression.write_text(
            "evaluation_id,binary64_gradient_error_n\n", encoding="utf-8")
        raw = bundle / "producer" / "raw_provenance.json"
        raw_value = json.loads(raw.read_text(encoding="utf-8"))
        raw_value["preregistration_commit"] = "0" * 40
        raw.write_text(json.dumps(raw_value), encoding="utf-8")
        expect_rejection(
            tool, lambda: tool.validate_bundle_claims(bundle, source_sha),
            "raw producer preregistration checkpoint",
        )
        mutations += 1
        raw_value["preregistration_commit"] = tool.PREREGISTRATION_SHA
        raw.write_text(json.dumps(raw_value), encoding="utf-8")
        provenance["inherited_blobs"] = {
            **tool.INHERITED_BLOBS,
            next(iter(tool.INHERITED_BLOBS)): "0" * 40,
        }
        (bundle / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
        expect_rejection(
            tool, lambda: tool.validate_bundle_claims(bundle, source_sha),
            "inherited constitutive blob",
        )
        mutations += 1
        provenance["inherited_blobs"] = tool.INHERITED_BLOBS
        provenance["source_branch"] = "main"
        (bundle / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
        expect_rejection(
            tool, lambda: tool.validate_bundle_claims(bundle, source_sha),
            "bundle source branch",
        )
        mutations += 1
        provenance["source_branch"] = tool.BRANCH
        provenance["source_sha"] = "2" * 40
        (bundle / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
        expect_rejection(
            tool, lambda: tool.validate_bundle_claims(bundle, source_sha),
            "bundle source SHA",
        )
        mutations += 1

    # Public CI identity, matrix, and conclusion are not inferred from markers.
    ci = valid_ci(tool, source_sha)
    tool.validate_ci(ci, source_sha, "77", 1)
    for label, mutate in (
        ("CI source", lambda value: value.update(headSha="2" * 40)),
        ("CI branch", lambda value: value.update(headBranch="main")),
        ("CI conclusion", lambda value: value.update(conclusion="failure")),
        ("CI attempt", lambda value: value.update(attempt=2)),
        ("CI matrix", lambda value: value["jobs"].pop()),
    ):
        changed = json.loads(json.dumps(ci))
        mutate(changed)
        expect_rejection(
            tool, lambda changed=changed: tool.validate_ci(
                changed, source_sha, "77", 1
            ), label,
        )
        mutations += 1

    # CI capture validates the exact public object before atomically creating
    # ci-run.json and refuses both invalid records and overwrite attempts.
    with tempfile.TemporaryDirectory(prefix="mls-conservative-force-ci-") as temporary:
        root = pathlib.Path(temporary)
        destination = root / "logs" / "ci-run.json"
        tool.write_ci_capture(destination, ci, source_sha, "77", 1)
        if json.loads(destination.read_text(encoding="utf-8")) != ci:
            raise RuntimeError("CI capture bytes did not preserve the validated object")
        expect_rejection(
            tool,
            lambda: tool.write_ci_capture(destination, ci, source_sha, "77", 1),
            "CI capture overwrite",
        )
        mutations += 1

        wrong_source = root / "wrong-source" / "ci-run.json"
        expect_rejection(
            tool,
            lambda: tool.write_ci_capture(
                wrong_source, ci, "2" * 40, "77", 1
            ),
            "CI capture source",
        )
        if wrong_source.exists():
            raise RuntimeError("invalid CI source created evidence")
        mutations += 1

        incomplete = json.loads(json.dumps(ci))
        incomplete["jobs"].pop()
        wrong_matrix = root / "wrong-matrix" / "ci-run.json"
        expect_rejection(
            tool,
            lambda: tool.write_ci_capture(
                wrong_matrix, incomplete, source_sha, "77", 1
            ),
            "CI capture matrix",
        )
        if wrong_matrix.exists():
            raise RuntimeError("invalid CI matrix created evidence")
        mutations += 1

        expect_rejection(
            tool,
            lambda: tool.write_ci_capture(
                root / "wrong-name.json", ci, source_sha, "77", 1
            ),
            "CI capture filename",
        )
        mutations += 1

        complete = root / "complete" / "ci-run.json"
        downloads = valid_artifact_downloads(tool, source_sha)
        tool.write_ci_capture_with_artifacts(
            complete, ci, source_sha, "77", 1, downloads)
        digest = tool.validate_ci_artifact_capture(
            complete.parent, source_sha, "77", 1)
        if len(digest) != 64:
            raise RuntimeError("CI artifact capture digest is malformed")
        expect_rejection(
            tool,
            lambda: tool.write_ci_capture_with_artifacts(
                complete, ci, source_sha, "77", 1, downloads),
            "complete CI capture overwrite",
        )
        mutations += 1

        missing = downloads[:-1]
        expect_rejection(
            tool,
            lambda: tool.write_ci_capture_with_artifacts(
                root / "missing-artifact" / "ci-run.json", ci, source_sha,
                "77", 1, missing),
            "CI artifact inventory",
        )
        mutations += 1

        cpp_index = next(
            index for index, (metadata, _) in enumerate(downloads)
            if metadata["name"].startswith("cpp-Windows MSVC-")
        )
        for label, replacement in (
            (
                "standard CTest failure summary",
                "99% tests passed, 1 test failed out of 78\n",
            ),
            (
                "wrong CTest total",
                "100% tests passed out of 999\n",
            ),
            (
                "mixed CTest success/failure summaries",
                "100% tests passed out of 78\n"
                "99% tests passed, 1 test failed out of 78\n",
            ),
            (
                "mismatched standalone CTest zero-failure summary",
                "100% tests passed out of 78\n"
                "0 tests failed out of 77\n",
            ),
            (
                "prefixed CTest failure decoy",
                "100% tests passed out of 78\n"
                "NOTE: 1 test failed out of 78\n",
            ),
            (
                "suffixed CTest failure decoy",
                "100% tests passed out of 78\n"
                "1 test failed out of 78 (decoy)\n",
            ),
            (
                "noncanonical leading-zero CTest summary",
                "0100% tests passed, 00 tests failed out of 078\n",
            ),
            (
                "CTest failed-tests marker",
                "100% tests passed out of 78\n"
                "The following tests FAILED:\n",
            ),
            (
                "CTest star-failed marker",
                "100% tests passed out of 78\n"
                "***Failed\n",
            ),
            (
                "CTest inline star-failed marker",
                " 1/78 Test #1: failure .....***Failed 0.01 sec\n"
                "100% tests passed out of 78\n",
            ),
            (
                "whitespace-obfuscated CTest failure decoy",
                "100% tests passed out of 78\n"
                "1 test  failed\t out  of 78\n",
            ),
            (
                "CTest inline timeout marker",
                " 1/78 Test #1: timeout .....***Timeout 1.00 sec\n"
                "100% tests passed out of 78\n",
            ),
            (
                "CTest inline skipped marker",
                " 1/78 Test #1: skipped .....***Skipped 0.01 sec\n"
                "100% tests passed out of 78\n",
            ),
        ):
            changed = list(downloads)
            metadata, payload = changed[cpp_index]
            files = tool.safe_zip_files(payload, metadata["name"])
            files["ctest.txt"] = replacement.encode("utf-8")
            changed[cpp_index] = (
                metadata,
                zip_payload({
                    name: value.decode("utf-8") for name, value in files.items()
                }),
            )
            expect_rejection(
                tool,
                lambda changed=changed, label=label:
                    tool.write_ci_capture_with_artifacts(
                        root / label.replace(" ", "-") / "ci-run.json", ci,
                        source_sha, "77", 1, changed),
                label,
            )
            mutations += 1

        # A locally self-consistent fabricated capture is not sealable unless
        # its stable IDs/names and expanded file hashes match a fresh live set.
        fabricated_downloads = list(downloads)
        fabricated_metadata, fabricated_zip = fabricated_downloads[0]
        fabricated_files = tool.safe_zip_files(
            fabricated_zip, fabricated_metadata["name"])
        fabricated_files["configure.txt"] += b"fabricated-but-well-formed\n"
        fabricated_downloads[0] = (
            fabricated_metadata,
            zip_payload({
                name: value.decode("utf-8")
                for name, value in fabricated_files.items()
            }),
        )
        fabricated_destination = root / "fabricated" / "ci-run.json"
        tool.write_ci_capture_with_artifacts(
            fabricated_destination, ci, source_sha, "77", 1,
            fabricated_downloads)
        tool.validate_ci_artifact_capture(
            fabricated_destination.parent, source_sha, "77", 1)
        expect_rejection(
            tool,
            lambda: tool.authenticate_ci_artifact_capture(
                fabricated_destination.parent, source_sha, "77", 1,
                downloads),
            "fabricated captured CI artifact content",
        )
        mutations += 1

        wrong_live_id = list(downloads)
        metadata, payload = wrong_live_id[0]
        changed_metadata = dict(metadata)
        changed_metadata["id"] = metadata["id"] + 10_000
        wrong_live_id[0] = (changed_metadata, payload)
        expect_rejection(
            tool,
            lambda: tool.authenticate_ci_artifact_capture(
                complete.parent, source_sha, "77", 1, wrong_live_id),
            "fresh CI artifact stable ID",
        )
        mutations += 1

        # ZIP containers are transport, not stable identity: recompressing the
        # same expanded files must still authenticate.
        recompressed = list(downloads)
        metadata, original_zip = recompressed[0]
        same_files = tool.safe_zip_files(original_zip, metadata["name"])
        alternate = io.BytesIO()
        with zipfile.ZipFile(alternate, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, value in reversed(sorted(same_files.items())):
                archive.writestr(name, value)
        recompressed[0] = (metadata, alternate.getvalue())
        if alternate.getvalue() == original_zip:
            raise RuntimeError("recompressed CI fixture did not change ZIP bytes")
        expected_stable = tool.ci_artifact_stable_sha256(
            json.loads((complete.parent / "ci-artifacts.json").read_text(
                encoding="utf-8")))
        observed_stable = tool.authenticate_ci_artifact_capture(
            complete.parent, source_sha, "77", 1, recompressed)
        if observed_stable != expected_stable:
            raise RuntimeError("stable CI artifact authentication changed")

        expect_rejection(
            tool,
            lambda: tool.bounded_zip_expanded_total(
                0, tool.MAX_CI_ARTIFACT_MEMBER_BYTES + 1,
                "oversized", "member.log"),
            "oversized CI artifact member declaration",
        )
        mutations += 1
        expect_rejection(
            tool,
            lambda: tool.bounded_zip_expanded_total(
                tool.MAX_CI_ARTIFACT_EXPANDED_BYTES - 1, 2,
                "oversized-total", "member.log"),
            "oversized CI artifact total declaration",
        )
        mutations += 1

        archive_path = complete.parent / "ci-artifacts" / \
            "artifact-00" / "archive.zip"
        archive_path.write_bytes(archive_path.read_bytes() + b"mutation")
        expect_rejection(
            tool,
            lambda: tool.validate_ci_artifact_capture(
                complete.parent, source_sha, "77", 1),
            "CI artifact archive bytes",
        )
        mutations += 1

        expect_rejection(
            tool,
            lambda: tool.safe_zip_files(
                zip_payload({"../escape.txt": "forged"}), "traversal"),
            "CI artifact path traversal",
        )
        mutations += 1

        wrong_artifact_source = valid_artifact_downloads(tool, source_sha)
        metadata, payload = wrong_artifact_source[0]
        bad_files = tool.safe_zip_files(payload, metadata["name"])
        bad_files["tool-versions.txt"] = bad_files["tool-versions.txt"].replace(
            source_sha.encode("ascii"), ("2" * 40).encode("ascii"))
        wrong_artifact_source[0] = (metadata, zip_payload({
            name: value.decode("utf-8") for name, value in bad_files.items()
        }))
        expect_rejection(
            tool,
            lambda: tool.write_ci_capture_with_artifacts(
                root / "wrong-artifact-source" / "ci-run.json", ci,
                source_sha, "77", 1, wrong_artifact_source),
            "CI artifact embedded source",
        )
        mutations += 1

    # Receipt argv is parsed token-by-token and the exact build/bundle path
    # relationships are integrity-bound.  Markers cannot substitute for those
    # relationships, and the receipts do not authenticate OS execution.
    if "authenticated command receipts" in (tool.__doc__ or "").lower():
        raise RuntimeError("seal still overclaims authenticated execution")
    with tempfile.TemporaryDirectory(prefix="mls-conservative-force-receipts-") as temporary:
        root = pathlib.Path(temporary)
        source = valid_receipts(tool, source_sha, root)

        def evaluate(changed: dict[str, dict]) -> dict:
            logs = root / ("logs-" + str(evaluate.counter))
            evaluate.counter += 1
            write_receipt_directory(tool, logs, changed, source_sha)
            return tool.require_receipts(
                logs, source_sha, expected_decision=TEST_DECISION,
                expected_repo=root / "repo",
                expected_bundle_a=root / "bundle-a",
                expected_bundle_b=root / "bundle-b",
                expected_parent_bundle=root / "accepted-parent",
            )

        evaluate.counter = 0
        bindings = evaluate(source)
        if bindings["semantics"] != (
                "integrity-bound-command-receipts-not-execution-authentication"):
            raise RuntimeError("receipt semantics overclaim execution authentication")

        # ``create`` resolves every live expected path exactly once before
        # receipt validation.  A second resolve here used to expand Windows
        # short names / runner aliases on only the expected side.  Model that
        # spelling change explicitly and require the lexical binding to remain
        # exact without consulting the filesystem again.
        class ResolutionChangingPath(type(pathlib.Path())):
            resolve_calls = 0

            def resolve(self, *args, **kwargs):
                type(self).resolve_calls += 1
                return type(self)(str(self) + "-different-resolved-spelling")

        lexical_root = ResolutionChangingPath(root)
        lexical_bindings = tool.receipt_path_bindings(
            source,
            expected_repo=lexical_root / "repo",
            expected_bundle_a=lexical_root / "bundle-a",
            expected_bundle_b=lexical_root / "bundle-b",
            expected_parent_bundle=lexical_root / "accepted-parent",
        )
        if ResolutionChangingPath.resolve_calls != 0:
            raise RuntimeError("receipt validation re-resolved a live path")
        receipt_only_bindings = dict(bindings)
        artifact_digest = receipt_only_bindings.pop(
            "ci_artifact_capture_sha256", None)
        stable_artifact_digest = receipt_only_bindings.pop(
            "ci_artifact_stable_content_sha256", None)
        if not isinstance(artifact_digest, str) or len(artifact_digest) != 64:
            raise RuntimeError("receipt validation omitted CI artifact commitment")
        if (not isinstance(stable_artifact_digest, str) or
                len(stable_artifact_digest) != 64):
            raise RuntimeError(
                "receipt validation omitted stable CI artifact commitment")
        if lexical_bindings != receipt_only_bindings:
            raise RuntimeError("lexically identical receipt bindings changed")
        expect_rejection(
            tool,
            lambda: tool.receipt_path_bindings(
                source,
                expected_repo=lexical_root / "different-repo",
                expected_bundle_a=lexical_root / "bundle-a",
                expected_bundle_b=lexical_root / "bundle-b",
                expected_parent_bundle=lexical_root / "accepted-parent",
            ),
            "lexically different live repository",
        )
        mutations += 1

        forged_bindings = json.loads(json.dumps(bindings))
        forged_bindings["semantics"] = "authenticated-operating-system-execution"
        expect_rejection(
            tool,
            lambda: tool.require(forged_bindings == bindings,
                                 "sealed receipt path relationships mismatch"),
            "receipt terminology",
        )
        mutations += 1

        def argv_mutation(filename: str, token: str, replacement: str) -> dict[str, dict]:
            changed = json.loads(json.dumps(source))
            command = changed[filename]["command"]
            command[command.index(token) + 1] = replacement
            return changed

        for label, changed in (
            ("configure/build directory", argv_mutation(
                "build.json", "--build", str(root / "other-build"))),
            ("raw producer-a output", argv_mutation(
                "raw-producer-a.json", "--output", str(root / "other-raw-a"))),
            ("materializer-a raw input", argv_mutation(
                "materialize-a.json", "--producer", str(root / "other-raw-a"))),
            ("materializer-a final output", argv_mutation(
                "materialize-a.json", "--output", str(root / "other-a"))),
            ("validator bundle path", argv_mutation(
                "validator.json", "--bundle", str(root / "other-a"))),
            ("twin comparator path", argv_mutation(
                "twin-compare.json", "--compare", str(root / "other-b"))),
            ("accepted parent bundle path", argv_mutation(
                "parent-evidence.json", "--parent-bundle",
                str(root / "wrong-parent"))),
        ):
            expect_rejection(tool, lambda changed=changed: evaluate(changed), label)
            mutations += 1

        exact_path_mutations = []
        changed = json.loads(json.dumps(source))
        changed["materialize-a.json"]["command"][1] = str(
            root / "decoy" / "validate_conservative_force_bundle.py")
        exact_path_mutations.append(("materializer script path", changed))
        changed = json.loads(json.dumps(source))
        changed["raw-producer-a.json"]["command"][0] = str(
            root / "other-build" /
            "mls_conservative_force_consistency_diagnostic.exe")
        exact_path_mutations.append(("raw producer executable path", changed))
        changed = json.loads(json.dumps(source))
        changed["lean-build.json"]["cwd"] = str(root / "repo")
        exact_path_mutations.append(("Lean project cwd", changed))
        changed = json.loads(json.dumps(source))
        changed["formal-trust.json"]["command"][-1] = str(root / "other-formal")
        exact_path_mutations.append(("formal trust root", changed))
        changed = json.loads(json.dumps(source))
        command = changed["exact-oracle.json"]["command"]
        command[command.index("--verify") + 1] = str(
            root / "decoy" / "conservative_force_oracle.canonical.json")
        exact_path_mutations.append(("oracle canonical path", changed))
        changed = json.loads(json.dumps(source))
        command = changed["validator-regression.json"]["command"]
        command[command.index("--producer") + 1] = str(root / "decoy-raw")
        exact_path_mutations.append(("validator regression producer path", changed))
        changed = json.loads(json.dumps(source))
        changed["compiler-versions.json"]["command"][1] = str(
            root / "decoy" / "conservative_force_tool_versions.py")
        exact_path_mutations.append(("tool-version script path", changed))
        changed = json.loads(json.dumps(source))
        command = changed["configure.json"]["command"]
        compiler_index = next(
            index for index, token in enumerate(command)
            if token.startswith("-DCMAKE_CXX_COMPILER="))
        command[compiler_index] = (
            "-DCMAKE_CXX_COMPILER=" + str(root / "decoy-cxx"))
        exact_path_mutations.append(("configured/versioned CXX mismatch", changed))
        for label, changed in exact_path_mutations:
            expect_rejection(tool, lambda changed=changed: evaluate(changed), label)
            mutations += 1

        for filename, old, new in (
            ("materialize-a.json", "materialize", "validate"),
            ("validator.json", "validate", "materialize"),
        ):
            changed = json.loads(json.dumps(source))
            command = changed[filename]["command"]
            command[command.index(old)] = new
            expect_rejection(
                tool, lambda changed=changed: evaluate(changed),
                filename + " subcommand",
            )
            mutations += 1

        changed = json.loads(json.dumps(source))
        changed["configure.json"]["command"].append(
            "text-containing--test-dir-and--bundle-is-not-an-option"
        )
        # An irrelevant substring is harmless because the required exact argv
        # remains present; removing the exact token must fail.
        evaluate(changed)
        changed["ctest.json"]["command"].remove("--test-dir")
        expect_rejection(tool, lambda: evaluate(changed), "substring-only option")
        mutations += 1

        # The raw producer's explicit publication boundary is the exact,
        # case-sensitive NO_PROMOTION token.  Keep receipt integrity internally
        # consistent so these mutations exercise the semantic gate itself.
        for label, marker in (
            ("missing producer NO_PROMOTION marker", ""),
            ("altered producer NO_PROMOTION marker", "NOT_PROMOTED"),
        ):
            changed = json.loads(json.dumps(source))
            output = (
                "CONSERVATIVE FORCE RAW BUNDLE COMPLETE\n"
                "stage=pending_independent_stage\n" +
                (marker + "\n" if marker else ""))
            changed["raw-producer-a.json"]["output"] = output
            payload = output.encode("utf-8")
            changed["raw-producer-a.json"]["output_bytes"] = len(payload)
            changed["raw-producer-a.json"]["output_sha256"] = tool.sha256_bytes(payload)
            expect_rejection(tool, lambda changed=changed: evaluate(changed), label)
            mutations += 1

        def replace_output(changed: dict[str, dict], filename: str,
                           output: str) -> None:
            payload = output.encode("utf-8")
            changed[filename]["output"] = output
            changed[filename]["output_bytes"] = len(payload)
            changed[filename]["output_sha256"] = tool.sha256_bytes(payload)

        version_output = source["compiler-versions.json"]["output"]
        for label, replacement in (
            ("dirty tool-version source",
             version_output.replace(
                 "source_status_begin\nsource_status_end",
                 "source_status_begin\n M source.cpp\nsource_status_end")),
            ("tool-version arithmetic contract",
             version_output.replace(
                 "iec559_size8_digits53_explicit_order_fp_contract_off_v1",
                 "unspecified-floating-point")),
            ("tool-version source branch",
             version_output.replace("source_branch=" + tool.BRANCH,
                                    "source_branch=main")),
            ("missing compiler version block",
             version_output.replace("cxx_version_end\n", "")),
            ("compiler version executable path",
             version_output.replace(
                 "cxx_command=" + str(root / "cxx"),
                 "cxx_command=" + str(root / "other-cxx"))),
        ):
            changed = json.loads(json.dumps(source))
            replace_output(changed, "compiler-versions.json", replacement)
            expect_rejection(
                tool, lambda changed=changed: evaluate(changed), label)
            mutations += 1

        changed = json.loads(json.dumps(source))
        other_decision = "reject_force_implementation"
        replace_output(
            changed, "materialize-a.json",
            "CONSERVATIVE FORCE BUNDLE MATERIALIZED decision=" +
            other_decision + "\n" + tool.NO_PROMOTION + "\n")
        expect_rejection(tool, lambda: evaluate(changed),
                         "producer decision differs from bound summary")
        mutations += 1

        for filename, output in (
            ("validator.json",
             "CONSERVATIVE FORCE BUNDLE VALID " + TEST_DECISION + "\n"),
            ("twin-compare.json",
             "CONSERVATIVE FORCE BUNDLE VALID reject_force_conservation " +
             tool.NO_PROMOTION + "\n"),
        ):
            changed = json.loads(json.dumps(source))
            replace_output(changed, filename, output)
            expect_rejection(tool, lambda changed=changed: evaluate(changed),
                             filename + " semantic marker")
            mutations += 1

    # The command receipt must retain exact UTF-8 even when stdout cannot
    # represent Lean's informational symbol.  Exercise record_command itself,
    # not just the console helper, using an encoding-strict platform-neutral
    # stream and deterministic process/git substitutes.
    class RestrictiveStdout:
        encoding = "cp1252"

        def __init__(self) -> None:
            self.value = ""

        def write(self, value: str) -> int:
            value.encode(self.encoding, errors="strict")
            self.value += value
            return len(value)

    with tempfile.TemporaryDirectory(prefix="mls-conservative-force-record-") as temporary:
        root = pathlib.Path(temporary)
        repo = root / "repo"
        repo.mkdir()
        destination = root / "unicode-replay.json"
        original_git_text = tool.git_text
        original_run = tool.subprocess.run
        original_stdout = tool.sys.stdout
        restrictive = RestrictiveStdout()
        captured = "Lean \u2139: declaration uses only permitted axioms\n"

        def fake_git_text(_repo, *arguments):
            if arguments == ("rev-parse", "HEAD"):
                return source_sha
            if arguments == ("branch", "--show-current"):
                return tool.BRANCH
            if arguments == ("status", "--porcelain=v1", "--untracked-files=all"):
                return ""
            raise RuntimeError(f"unexpected git fixture command: {arguments}")

        try:
            tool.git_text = fake_git_text
            tool.subprocess.run = lambda *args, **kwargs: SimpleNamespace(
                stdout=captured, returncode=0
            )
            tool.sys.stdout = restrictive
            return_code = tool.record_command(SimpleNamespace(
                repo=repo,
                source_sha=source_sha,
                command=["synthetic-lean"],
                receipt=destination,
                label="unicode-replay",
                cwd=repo,
            ))
        finally:
            tool.sys.stdout = original_stdout
            tool.subprocess.run = original_run
            tool.git_text = original_git_text

        if return_code != 0:
            raise RuntimeError("restrictive stdout changed the recorded exit code")
        recorded = json.loads(destination.read_text(encoding="utf-8"))
        if recorded["output"] != captured:
            raise RuntimeError("restrictive stdout changed UTF-8 receipt output")
        if recorded["output_sha256"] != tool.sha256_bytes(captured.encode("utf-8")):
            raise RuntimeError("restrictive stdout changed receipt output digest")
        if "\\u2139" not in restrictive.value or "\u2139" in restrictive.value:
            raise RuntimeError("restrictive stdout replay was not safely escaped")

    # Independent validation is not accepted from exit status alone. Its
    # validate subcommand, decision, and NO_PROMOTION marker are all bound.
    original_run = tool.subprocess.run
    observed_commands: list[list[str]] = []
    valid_validator_output = (
        "CONSERVATIVE FORCE BUNDLE VALID: 10 checks; decision=" +
        TEST_DECISION + "\n" + tool.NO_PROMOTION + "\n")
    current_validator_output = valid_validator_output

    def fake_validator_run(command, **_kwargs):
        observed_commands.append(command)
        return SimpleNamespace(
            returncode=0, stdout=current_validator_output, stderr="")

    try:
        tool.subprocess.run = fake_validator_run
        tool.run_validator(pathlib.Path("validator.py"), pathlib.Path("a"),
                           pathlib.Path("b"), expected_decision=TEST_DECISION)
        if observed_commands[-1][2] != "validate":
            raise RuntimeError("sealer omitted validator validate subcommand")
        for label, replacement in (
            ("validator decision output",
             valid_validator_output.replace(
                 TEST_DECISION, "reject_force_conservation")),
            ("validator promotion output",
             valid_validator_output.replace(tool.NO_PROMOTION, "NOT_PROMOTED")),
            ("validator success marker",
             valid_validator_output.replace(
                 "CONSERVATIVE FORCE BUNDLE VALID", "VALID")),
        ):
            current_validator_output = replacement
            expect_rejection(
                tool,
                lambda: tool.run_validator(
                    pathlib.Path("validator.py"), pathlib.Path("a"),
                    pathlib.Path("b"), expected_decision=TEST_DECISION),
                label,
            )
            mutations += 1
    finally:
        tool.subprocess.run = original_run

    # Annotated and lightweight tag resolution must both land on the source.
    direct, peeled = tool.parse_remote_refs(
        f"{'a' * 40}\trefs/tags/{tool.TAG}\n"
        f"{source_sha}\trefs/tags/{tool.TAG}^{{}}\n",
        tool.TAG,
    )
    if (peeled or direct) != source_sha:
        raise RuntimeError("valid annotated tag fixture did not resolve")
    direct, peeled = tool.parse_remote_refs(
        f"{'a' * 40}\trefs/tags/{tool.TAG}\n", tool.TAG
    )
    expect_rejection(
        tool,
        lambda: tool.require((peeled or direct) == source_sha,
                             "public evidence tag/source mismatch"),
        "public tag target",
    )
    mutations += 1

    # Twin bundles must be distinct directories with identical closed bytes.
    with tempfile.TemporaryDirectory(prefix="mls-conservative-force-twins-") as temporary:
        root = pathlib.Path(temporary)
        first, second = root / "a", root / "b"
        first.mkdir()
        second.mkdir()
        (first / "payload.bin").write_bytes(b"same")
        (second / "payload.bin").write_bytes(b"same")
        tool.require_twins(first, second)
        (second / "payload.bin").write_bytes(b"changed")
        expect_rejection(tool, lambda: tool.require_twins(first, second),
                         "twin payload")
        mutations += 1

    # Final publication is atomic and fail-if-exists, including the race
    # window after an earlier existence check.
    with tempfile.TemporaryDirectory(
            prefix="mls-conservative-force-publish-") as temporary:
        root = pathlib.Path(temporary)
        staging = root / "staging"
        destination = root / "sealed"
        staging.mkdir()
        (staging / "payload.bin").write_bytes(b"first")
        tool.publish_directory_no_replace(staging, destination)
        if (destination / "payload.bin").read_bytes() != b"first":
            raise RuntimeError("atomic directory publication changed bytes")
        second_staging = root / "second-staging"
        second_staging.mkdir()
        (second_staging / "payload.bin").write_bytes(b"replacement")
        expect_rejection(
            tool,
            lambda: tool.publish_directory_no_replace(
                second_staging, destination),
            "seal destination overwrite",
        )
        if (destination / "payload.bin").read_bytes() != b"first":
            raise RuntimeError("failed publication replaced sealed evidence")
        mutations += 1

    # Receipt output, exit status, source, and command are integrity-bound fields.
    valid_receipt = receipt(tool, source_sha, "PASS\n")
    tool.validate_receipt(valid_receipt, source_sha, "test.json")
    for label, mutate in (
        ("receipt output", lambda value: value.update(output="forged\n")),
        ("receipt exit", lambda value: value.update(exit_code=1)),
        ("receipt source", lambda value: value.update(source_sha="2" * 40)),
        ("receipt command", lambda value: value.update(command=[])),
    ):
        changed = json.loads(json.dumps(valid_receipt))
        mutate(changed)
        expect_rejection(
            tool,
            lambda changed=changed: tool.validate_receipt(
                changed, source_sha, "test.json"
            ),
            label,
        )
        mutations += 1

    # The outer pre-hash closes contents and archive inventory; provenance is
    # included in its preimage, so source/tag/decision edits also fail.
    provenance = {
        "repository_url": "https://github.com/example/repo",
        "branch": tool.BRANCH,
        "source_sha": source_sha,
        "source_tree_sha": "3" * 40,
        "accepted_parent_sha": tool.PARENT_SHA,
        "inherited_blobs": tool.INHERITED_BLOBS,
        "preregistration_commit": tool.PREREGISTRATION_SHA,
        "preregistered_blobs": tool.PREREGISTERED_BLOBS,
        "ci_run_id": "77",
        "ci_attempt": 1,
        "tag": tool.TAG,
        "decision": TEST_DECISION,
        "promotion_permitted": False,
        "bundle_tree_sha256": "4" * 64,
        "receipt_path_bindings": {
            "schema": tool.RECEIPT_BINDINGS_SCHEMA,
            "semantics":
                "integrity-bound-command-receipts-not-execution-authentication",
        },
    }
    tool.validate_outer_provenance(provenance)
    for label, field, value in (
        ("outer branch", "branch", "main"),
        ("outer source", "source_sha", "not-a-source"),
        ("outer tag", "tag", "forged-tag"),
        ("outer decision", "decision", "forged_decision"),
        ("outer preregistration", "preregistration_commit", "0" * 40),
    ):
        changed = json.loads(json.dumps(provenance))
        changed[field] = value
        expect_rejection(tool, lambda changed=changed:
                         tool.validate_outer_provenance(changed), label)
        mutations += 1
    with tempfile.TemporaryDirectory(prefix="mls-conservative-force-seal-") as temporary:
        root = pathlib.Path(temporary)
        (root / "payload").mkdir()
        payload = root / "payload" / "a.bin"
        payload.write_bytes(b"canonical")
        tool.write_manifest(root, provenance)
        tool.verify_manifest_only(root)

        payload.write_bytes(b"mutated")
        expect_rejection(tool, lambda: tool.verify_manifest_only(root),
                         "manifest payload")
        mutations += 1
        payload.write_bytes(b"canonical")
        tool.write_manifest(root, provenance)

        (root / "undeclared.bin").write_bytes(b"extra")
        expect_rejection(tool, lambda: tool.verify_manifest_only(root),
                         "archive inventory")
        mutations += 1
        (root / "undeclared.bin").unlink()
        tool.write_manifest(root, provenance)

        manifest_path = root / "outer-seal.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["pre_hash_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        expect_rejection(tool, lambda: tool.verify_manifest_only(root),
                         "outer pre-hash")
        mutations += 1

        tool.write_manifest(root, provenance)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["provenance"]["tag"] = "forged-tag"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        expect_rejection(tool, lambda: tool.verify_manifest_only(root),
                         "manifest tag provenance")
        mutations += 1

    print(
        "conservative force consistency outer-seal mutation regression: "
        f"PASS ({mutations} mutations: source/tag/CI/twin/receipt/manifest/inventory)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
