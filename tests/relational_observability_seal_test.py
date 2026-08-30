#!/usr/bin/env python3
"""Mutation tests for the Relational Observability outer-seal boundary."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
from types import SimpleNamespace


def load_tool():
    path = pathlib.Path(__file__).resolve().parents[1] / \
        "tools" / "seal_relational_observability_evidence.py"
    spec = importlib.util.spec_from_file_location("relational_sealer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load sealer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect_rejection(tool, root: pathlib.Path) -> None:
    try:
        tool.verify_manifest_only(root)
    except tool.SealError:
        return
    raise RuntimeError("outer seal accepted a mutation")


def write_receipt(
    tool,
    path: pathlib.Path,
    label: str,
    source_sha: str,
    command: list[str],
    output: str,
    *,
    exit_code: int = 0,
) -> None:
    payload = {
        "schema": tool.COMMAND_RECEIPT_SCHEMA,
        "label": label,
        "source_sha": source_sha,
        "branch": "relational-observability-confirmation",
        "cwd": str(path.parent.resolve()),
        "command": command,
        "started_at_utc": "2026-08-29T00:00:00.000000Z",
        "ended_at_utc": "2026-08-29T00:00:01.000000Z",
        "exit_code": exit_code,
        "output_bytes": len(output.encode("utf-8")),
        "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        "output": output,
    }
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def populate_valid_logs(
    tool,
    logs: pathlib.Path,
    source_sha: str,
    verdict: str,
    ci: dict,
) -> None:
    logs.mkdir(parents=True, exist_ok=True)
    outputs = {
        "configure.log": (
            "-- Configuring done\n-- Generating done\n"
            "-- Build files have been written to: test\n"
        ),
        "build.log": (
            "[1/1] Linking CXX executable "
            "mls_relational_observability_diagnostic\n"
        ),
        "ctest.log": "100% tests passed, 0 tests failed out of 7\n",
        "producer-a.log": (
            "Relational Observability evidence written (full) to full-a\n"
            f"Verdict: {verdict}\nNO PROMOTION\n"
        ),
        "producer-b.log": (
            "Relational Observability evidence written (full) to full-b\n"
            f"Verdict: {verdict}\nNO PROMOTION\n"
        ),
        "twin-compare.log": "smoke byte comparison: PASS (1 files)\n",
        "validator.log": (
            "RELATIONAL OBSERVABILITY BUNDLE VALID: 1 checks; "
            f"decision={verdict}; byte comparison: PASS\n"
        ),
        "validator-regression.log": (
            "PASS (18 mutations; direct raw-matrix SVD regression)\n"
        ),
        "lean-build.log": "Build completed successfully\n",
        "lean-axioms.log": (
            "mechanicallyObservable_vertex_relabel_iff\n"
            "relationSquaredLength_similarity\n"
            "relabeledRationalTetraK4_mechanicallyObservable\n"
        ),
        "formal-trust.log": (
            "PASS: no sorry, admit, sorryAx, project-defined axiom "
            "declaration, or unreported theorem\n"
        ),
        "compiler-versions.txt": (
            f"source_sha={source_sha}\n"
            "source_branch=relational-observability-confirmation\n"
            "source_status_begin\nsource_status_end\n"
            "cxx_command=c++\ncxx_version_begin\nC++ compiler 1.0\n"
            "cxx_version_end\ncmake_version_begin\ncmake version 4.0\n"
            "cmake_version_end\npython_version_begin\nPython 3.13\n"
            "python_version_end\nlean_version_begin\nLean 4.0\n"
            "lean_version_end\nlake_version_begin\nLake version 5.0\n"
            "lake_version_end\n"
        ),
    }
    commands = {
        "configure.log": [
            "cmake", "-S", ".", "-B", "build",
            "-DMLS_WARNINGS_AS_ERRORS=ON",
            "-DMLS_RUN_EXTENDED_EXACT_TESTS=ON",
        ],
        "build.log": ["cmake", "--build", "build", "--parallel", "8"],
        "ctest.log": ["ctest", "--test-dir", "build", "--output-on-failure"],
        "producer-a.log": [
            "mls_relational_observability_diagnostic.exe",
            "--fixture-bundle", "fixture", "--output", "full-a",
        ],
        "producer-b.log": [
            "mls_relational_observability_diagnostic.exe",
            "--fixture-bundle", "fixture", "--output", "full-b",
        ],
        "twin-compare.log": [
            "python", "compare_evidence_directories.py",
            "--first", "full-a", "--second", "full-b",
        ],
        "validator.log": [
            "python", "validate_relational_observability_bundle.py",
            "--bundle", "full-a", "--compare", "full-b",
        ],
        "validator-regression.log": [
            "python", "relational_observability_bundle_validator_test.py",
            "--validator", "validate_relational_observability_bundle.py",
            "--bundle", "full-a",
        ],
        "lean-build.log": ["lake", "--wfail", "build"],
        "lean-axioms.log": [
            "lake", "env", "lean", "MLSFormal/AxiomReport.lean"
        ],
        "formal-trust.log": [
            "python", "formal_trust_scan.py", "--formal-root", "formal"
        ],
        "compiler-versions.txt": [
            "python", "relational_observability_tool_versions.py",
            "--repo", ".", "--cxx", "c++", "--lake", "lake",
        ],
    }
    for filename, output in outputs.items():
        write_receipt(
            tool,
            logs / filename,
            pathlib.Path(filename).stem,
            source_sha,
            commands[filename],
            output,
        )
    (logs / "ci-run.json").write_text(
        json.dumps(ci, sort_keys=True), encoding="utf-8"
    )


def main() -> int:
    tool = load_tool()
    if tool.portable_basename(r"C:\tools\python.exe") != "python.exe":
        raise RuntimeError("Windows command basename is not host-neutral")
    if not tool.portable_absolute(r"D:\MaterialLifeSubstrate"):
        raise RuntimeError("Windows receipt cwd is not host-neutral")
    if not tool.portable_absolute("/opt/mls"):
        raise RuntimeError("POSIX receipt cwd is not host-neutral")
    with tempfile.TemporaryDirectory(prefix="mls-git-blob-") as temporary:
        blob = pathlib.Path(temporary) / "hello.txt"
        blob.write_bytes(b"hello\n")
        if tool.git_blob_id(blob) != "ce013625030ba8dba906f756967f9e9ca394464a":
            raise RuntimeError("Git-blob provenance self-test failed")
    with tempfile.TemporaryDirectory(prefix="mls-command-receipt-") as temporary:
        root = pathlib.Path(temporary)
        receipt = root / "probe.log"
        runner = pathlib.Path(__file__).resolve().parents[1] / \
            "tools" / "run_relational_evidence_command.py"
        completed = subprocess.run(
            [
                sys.executable, str(runner), "--receipt", str(receipt),
                "--label", "probe", "--source-sha", "1" * 40,
                "--cwd", str(root), "--", sys.executable, "-c",
                "print('receipt runner probe')",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if completed.returncode != 0 or "receipt runner probe" not in completed.stdout:
            raise RuntimeError("command receipt runner self-test failed")
        command, output = tool.read_command_receipt(receipt, "probe", "1" * 40)
        if command[-1] != "print('receipt runner probe')" or output not in {
            "receipt runner probe\r\n", "receipt runner probe\n"
        }:
            raise RuntimeError("command receipt runner payload mismatch")
    valid_ci = {
        "attempt": 1,
        "createdAt": "2026-08-29T00:00:00Z",
        "headSha": "1" * 40,
        "headBranch": "relational-observability-confirmation",
        "conclusion": "success",
        "databaseId": 7,
        "displayTitle": "test",
        "event": "push",
        "jobs": [
            {"name": name, "status": "completed", "conclusion": "success"}
            for name in sorted(tool.REQUIRED_CI_JOBS)
        ],
        "name": "MLS-0 baseline replication",
        "number": 1,
        "startedAt": "2026-08-29T00:00:00Z",
        "status": "completed",
        "updatedAt": "2026-08-29T00:01:00Z",
        "url": "https://github.com/example/repo/actions/runs/7",
        "workflowDatabaseId": 1,
        "workflowName": "MLS-0 baseline replication",
    }
    tool.validate_ci(valid_ci, "1" * 40, "7")
    invalid_ci = dict(valid_ci)
    invalid_ci["headBranch"] = "main"
    try:
        tool.validate_ci(invalid_ci, "1" * 40, "7")
    except tool.SealError:
        pass
    else:
        raise RuntimeError("CI provenance accepted the wrong source branch")
    invalid_ci = dict(valid_ci)
    invalid_ci["attempt"] = True
    try:
        tool.validate_ci(invalid_ci, "1" * 40, "7")
    except tool.SealError:
        pass
    else:
        raise RuntimeError("CI provenance accepted boolean attempt as integer one")
    with tempfile.TemporaryDirectory(prefix="mls-log-evidence-") as temporary:
        logs = pathlib.Path(temporary)
        verdict = "retain_central_relational_representation_for_research"
        outputs = {
            "configure.log": (
                "-- Configuring done\n-- Generating done\n"
                "-- Build files have been written to: test\n"
            ),
            "build.log": "[1/1] Linking CXX executable mls_relational_observability_diagnostic\n",
            "ctest.log": "100% tests passed, 0 tests failed out of 7\n",
            "producer-a.log": (
                "Relational Observability evidence written (full) to full-a\n"
                f"Verdict: {verdict}\nNO PROMOTION\n"
            ),
            "producer-b.log": (
                "Relational Observability evidence written (full) to full-b\n"
                f"Verdict: {verdict}\nNO PROMOTION\n"
            ),
            "twin-compare.log": "smoke byte comparison: PASS (1 files)\n",
            "validator.log": (
                "RELATIONAL OBSERVABILITY BUNDLE VALID: 1 checks; "
                f"decision={verdict}; byte comparison: PASS\n"
            ),
            "validator-regression.log": (
                "PASS (18 mutations; direct raw-matrix SVD regression)\n"
            ),
            "lean-build.log": "Build completed successfully\n",
            "lean-axioms.log": (
                "mechanicallyObservable_vertex_relabel_iff\n"
                "relationSquaredLength_similarity\n"
                "relabeledRationalTetraK4_mechanicallyObservable\n"
            ),
            "formal-trust.log": (
                "PASS: no sorry, admit, sorryAx, project-defined axiom "
                "declaration, or unreported theorem\n"
            ),
            "compiler-versions.txt": (
                f"source_sha={'1' * 40}\n"
                "source_branch=relational-observability-confirmation\n"
                "source_status_begin\nsource_status_end\n"
                "cxx_command=c++\ncxx_version_begin\nC++ compiler 1.0\n"
                "cxx_version_end\ncmake_version_begin\ncmake version 4.0\n"
                "cmake_version_end\npython_version_begin\nPython 3.13\n"
                "python_version_end\nlean_version_begin\nLean 4.0\n"
                "lean_version_end\nlake_version_begin\nLake version 5.0\n"
                "lake_version_end\n"
            ),
        }
        commands = {
            "configure.log": [
                "cmake", "-S", ".", "-B", "build",
                "-DMLS_WARNINGS_AS_ERRORS=ON",
                "-DMLS_RUN_EXTENDED_EXACT_TESTS=ON",
            ],
            "build.log": ["cmake", "--build", "build", "--parallel", "8"],
            "ctest.log": [
                "ctest", "--test-dir", "build", "--output-on-failure"
            ],
            "producer-a.log": [
                "mls_relational_observability_diagnostic.exe",
                "--fixture-bundle", "fixture", "--output", "full-a",
            ],
            "producer-b.log": [
                "mls_relational_observability_diagnostic.exe",
                "--fixture-bundle", "fixture", "--output", "full-b",
            ],
            "twin-compare.log": [
                "python", "compare_evidence_directories.py",
                "--first", "full-a", "--second", "full-b",
            ],
            "validator.log": [
                "python", "validate_relational_observability_bundle.py",
                "--bundle", "full-a", "--compare", "full-b",
            ],
            "validator-regression.log": [
                "python", "relational_observability_bundle_validator_test.py",
                "--validator", "validate_relational_observability_bundle.py",
                "--bundle", "full-a",
            ],
            "lean-build.log": ["lake", "--wfail", "build"],
            "lean-axioms.log": [
                "lake", "env", "lean", "MLSFormal/AxiomReport.lean"
            ],
            "formal-trust.log": [
                "python", "formal_trust_scan.py", "--formal-root", "formal"
            ],
            "compiler-versions.txt": [
                "python", "relational_observability_tool_versions.py",
                "--repo", ".", "--cxx", "c++", "--lake", "lake",
            ],
        }
        for filename, output in outputs.items():
            write_receipt(
                tool, logs / filename, pathlib.Path(filename).stem,
                "1" * 40, commands[filename], output,
            )
        (logs / "ci-run.json").write_text(json.dumps(valid_ci), encoding="utf-8")
        tool.require_log_evidence(logs, "1" * 40, verdict)
        ctest_path = logs / "ctest.log"
        write_receipt(
            tool, ctest_path, "ctest", "1" * 40, commands["ctest.log"],
            "ERROR: not 100% tests passed\n",
        )
        try:
            tool.require_log_evidence(logs, "1" * 40, verdict)
        except tool.SealError:
            pass
        else:
            raise RuntimeError("log gate accepted a forged CTest marker")
        write_receipt(
            tool, ctest_path, "ctest", "1" * 40, commands["ctest.log"],
            outputs["ctest.log"],
        )
        receipt = json.loads(ctest_path.read_text(encoding="utf-8"))
        receipt["exit_code"] = 9
        ctest_path.write_text(json.dumps(receipt), encoding="utf-8")
        try:
            tool.require_log_evidence(logs, "1" * 40, verdict)
        except tool.SealError:
            pass
        else:
            raise RuntimeError("log gate accepted a nonzero command exit code")
        write_receipt(
            tool, ctest_path, "ctest", "1" * 40, commands["ctest.log"],
            outputs["ctest.log"],
        )
        selected_ctest = list(commands["ctest.log"]) + ["-I", "1,1"]
        write_receipt(
            tool, ctest_path, "ctest", "1" * 40, selected_ctest,
            outputs["ctest.log"],
        )
        try:
            tool.require_log_evidence(logs, "1" * 40, verdict)
        except tool.SealError:
            pass
        else:
            raise RuntimeError("log gate accepted a selected CTest subset")
        write_receipt(
            tool, ctest_path, "ctest", "1" * 40, commands["ctest.log"],
            outputs["ctest.log"],
        )
        trust_path = logs / "formal-trust.log"
        write_receipt(
            tool, trust_path, "formal-trust", "1" * 40,
            commands["formal-trust.log"],
            "FAIL then " + outputs["formal-trust.log"],
        )
        try:
            tool.require_log_evidence(logs, "1" * 40, verdict)
        except tool.SealError:
            pass
        else:
            raise RuntimeError("log gate accepted contradictory formal trust")
        try:
            tool.validate_twin_paths(logs, logs)
        except tool.SealError:
            pass
        else:
            raise RuntimeError("twin gate accepted one directory twice")
    with tempfile.TemporaryDirectory(prefix="mls-source-tree-") as temporary:
        root = pathlib.Path(temporary)
        repo = root / "repo"
        repo.mkdir()
        subprocess.run(
            ["git", "init", "-b", "relational-observability-confirmation"],
            cwd=repo,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            ["git", "config", "user.email", "seal-test@example.invalid"],
            cwd=repo,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "MLS seal test"],
            cwd=repo,
            check=True,
        )
        tracked = repo / "tracked.txt"
        tracked.write_text("committed\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "test source"],
            cwd=repo,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        source_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        previous_required = tool.REQUIRED_SOURCE_FILES
        previous_inherited = tool.INHERITED_GIT_BLOBS
        try:
            tool.REQUIRED_SOURCE_FILES = {"tracked.txt"}
            tool.INHERITED_GIT_BLOBS = {}
            blobs = tool.validate_repo_source(repo, source_sha)
            if set(blobs) != {"tracked.txt"}:
                raise RuntimeError("source-tree inventory is incomplete")
            expected_tree = subprocess.run(
                ["git", "rev-parse", "HEAD^{tree}"],
                cwd=repo,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout.strip()
            if tool.reconstructed_git_tree_id(blobs) != expected_tree:
                raise RuntimeError("source-tree reconstruction mismatch")
            commit_payload = tool.committed_object(repo, "commit", source_sha)
            if tool.git_object_id("commit", commit_payload) != source_sha:
                raise RuntimeError("source-commit reconstruction mismatch")
            if tool.commit_tree_id(commit_payload) != expected_tree:
                raise RuntimeError("source commit/tree binding mismatch")
            snapshot = root / "snapshot"
            tool.copy_source_snapshot(repo, snapshot, blobs)
            tool.verify_source_snapshot(snapshot, blobs)
            subprocess.run(
                ["git", "update-index", "--assume-unchanged", "tracked.txt"],
                cwd=repo,
                check=True,
            )
            tracked.write_text("post-config edit\n", encoding="utf-8")
            try:
                tool.validate_repo_source(repo, source_sha)
            except tool.SealError:
                pass
            else:
                raise RuntimeError("source seal accepted a dirty post-config edit")
        finally:
            tool.REQUIRED_SOURCE_FILES = previous_required
            tool.INHERITED_GIT_BLOBS = previous_inherited

    # Exercise the actual atomic create -> full verify boundary with remote and
    # numerical execution replaced only by deterministic test doubles.
    with tempfile.TemporaryDirectory(prefix="mls-seal-e2e-") as temporary:
        root = pathlib.Path(temporary)
        repo = root / "repo"
        repo.mkdir()
        subprocess.run(
            ["git", "init", "-b", "relational-observability-confirmation"],
            cwd=repo,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            ["git", "config", "user.email", "seal-test@example.invalid"],
            cwd=repo,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "MLS seal test"],
            cwd=repo,
            check=True,
        )
        (repo / "tracked.txt").write_text("committed\n", encoding="utf-8")
        (repo / "nested").mkdir()
        (repo / "nested" / "unlisted.txt").write_text(
            "complete tree sentinel\n", encoding="utf-8"
        )
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "test source"],
            cwd=repo,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        source_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        verdict = "retain_central_relational_representation_for_research"
        summary = {
            "schema": "mls.relational-observability-confirmation.summary.v1",
            "mode": "full",
            "provisional": False,
            "sweep_complete": True,
            "producer": "cpp_relational_observability_confirmation",
            "seed": 260828,
            "source_sha": source_sha,
            "parent_sha": "0" * 40,
            "accepted_candidate_c_source_sha": "0" * 40,
            "branch": "relational-observability-confirmation",
            "dirty": False,
            "verdict": verdict,
            "no_promotion": True,
            "candidate": "C",
            "candidate_b_decision_input_count": 0,
            "candidate_d_instantiated": False,
            "inherited_git_blobs": {},
            "fixture_table_sha256": {},
            "counts": {},
            "gate_counts": {},
            "compiler": {},
            "direct_svd": {},
            "pre_hash_sha256": "0" * 64,
        }
        bundle_a = root / "bundle-a"
        bundle_b = root / "bundle-b"
        for bundle in (bundle_a, bundle_b):
            bundle.mkdir()
            (bundle / "summary.json").write_text(
                json.dumps(summary, sort_keys=True), encoding="utf-8"
            )
        ci = dict(valid_ci)
        ci["headSha"] = source_sha
        logs = root / "logs"
        populate_valid_logs(tool, logs, source_sha, verdict, ci)
        seal_dir = root / "evidence-v1"
        previous_required = tool.REQUIRED_SOURCE_FILES
        previous_inherited = tool.INHERITED_GIT_BLOBS
        previous_publication = tool.validate_publication
        previous_fetch = tool.fetch_ci_run
        previous_validator = tool.run_validator
        publication_branch_requirements: list[bool] = []

        def fake_publication(
            _url, _tag, _sha, repo=None, *, require_branch=True
        ):
            publication_branch_requirements.append(require_branch)

        def fake_fetch(_url, run_id, attempt):
            if str(run_id) != "7" or attempt != 1:
                raise RuntimeError("CI attempt identity was not preserved")
            return ci

        def fake_validator(_validator, first, second=None):
            if second is not None:
                first_summary = (first / "summary.json").read_bytes()
                second_summary = (second / "summary.json").read_bytes()
                if first_summary != second_summary:
                    raise RuntimeError("test-double twin bundles differ")

        try:
            tool.REQUIRED_SOURCE_FILES = {"tracked.txt"}
            tool.INHERITED_GIT_BLOBS = {}
            tool.validate_publication = fake_publication
            tool.fetch_ci_run = fake_fetch
            tool.run_validator = fake_validator
            manifest = tool.create(
                SimpleNamespace(
                    repo=repo,
                    bundle_a=bundle_a,
                    bundle_b=bundle_b,
                    logs=logs,
                    seal_dir=seal_dir,
                    source_sha=source_sha,
                    ci_run_id="7",
                    repository_url="https://github.com/example/repo",
                    tag="relational-observability-confirmation-evidence-v1",
                )
            )
            if not seal_dir.is_dir() or any(
                path.name.startswith(".evidence-v1.staging-")
                for path in root.iterdir()
            ):
                raise RuntimeError("atomic seal publication failed")
            sealed_provenance = json.loads(
                (seal_dir / "provenance.json").read_text(encoding="utf-8")
            )
            if set(sealed_provenance["source_git_tree"]) != {
                "tracked.txt", "nested/unlisted.txt"
            }:
                raise RuntimeError("seal did not capture the complete Git tree")
            tool.verify(seal_dir, manifest["pre_hash_sha256"])
            if publication_branch_requirements != [True, False, False]:
                raise RuntimeError("create/verify branch durability contract changed")
            calls_before_wrong_pin = len(publication_branch_requirements)
            try:
                tool.verify(seal_dir, "f" * 64)
            except tool.SealError:
                pass
            else:
                raise RuntimeError("full verify accepted the wrong external pre-hash")
            if len(publication_branch_requirements) != calls_before_wrong_pin:
                raise RuntimeError("wrong pre-hash reached remote verification")
            sealed_provenance["promotion_permitted_alias"] = False
            (seal_dir / "provenance.json").write_text(
                json.dumps(sealed_provenance, sort_keys=True), encoding="utf-8"
            )
            replacement = tool.write_manifest(seal_dir, sealed_provenance)
            try:
                tool.verify(seal_dir, replacement["pre_hash_sha256"])
            except tool.SealError:
                pass
            else:
                raise RuntimeError("full verify accepted extra provenance fields")
        finally:
            tool.REQUIRED_SOURCE_FILES = previous_required
            tool.INHERITED_GIT_BLOBS = previous_inherited
            tool.validate_publication = previous_publication
            tool.fetch_ci_run = previous_fetch
            tool.run_validator = previous_validator
    provenance = {
        "repository_url": "https://example.invalid/repo",
        "branch": "relational-observability-confirmation",
        "source_sha": "1" * 40,
        "ci_run_id": "7",
        "tag": "relational-observability-confirmation-evidence-v1",
        "verdict": "retain_central_relational_representation_for_research",
        "promotion_permitted": False,
    }
    with tempfile.TemporaryDirectory(prefix="mls-relational-seal-") as temporary:
        root = pathlib.Path(temporary)
        (root / "payload").mkdir()
        payload = root / "payload" / "a.txt"
        payload.write_text("alpha\n", encoding="utf-8")
        (root / "payload" / "b.bin").write_bytes(b"\x00\x01\x02")
        tool.write_manifest(root, provenance)
        tool.verify_manifest_only(root)

        original = payload.read_bytes()
        payload.write_bytes(original + b"x")
        expect_rejection(tool, root)
        payload.write_bytes(original)
        tool.write_manifest(root, provenance)

        extra = root / "payload" / "extra"
        extra.write_text("x", encoding="utf-8")
        expect_rejection(tool, root)
        extra.unlink()
        tool.write_manifest(root, provenance)

        manifest_path = root / "outer-seal.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["pre_hash_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        expect_rejection(tool, root)

    print("relational observability outer-seal mutation regression: PASS (13 mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
