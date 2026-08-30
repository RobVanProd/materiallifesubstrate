#!/usr/bin/env python3
"""Mutation tests for the Relational Observability outer-seal boundary."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import tempfile


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


def main() -> int:
    tool = load_tool()
    with tempfile.TemporaryDirectory(prefix="mls-git-blob-") as temporary:
        blob = pathlib.Path(temporary) / "hello.txt"
        blob.write_bytes(b"hello\n")
        if tool.git_blob_id(blob) != "ce013625030ba8dba906f756967f9e9ca394464a":
            raise RuntimeError("Git-blob provenance self-test failed")
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
    with tempfile.TemporaryDirectory(prefix="mls-log-evidence-") as temporary:
        logs = pathlib.Path(temporary)
        verdict = "retain_central_relational_representation_for_research"
        contents = {
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
            "twin-compare.log": "byte comparison: PASS\n",
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
                "cmake version 4.0\nPython 3.13\nLean 4.0\n"
            ),
            "ci-run.json": json.dumps(valid_ci),
        }
        for filename, content in contents.items():
            (logs / filename).write_text(content, encoding="utf-8")
        tool.require_log_evidence(logs, "1" * 40, verdict)
        ctest_path = logs / "ctest.log"
        ctest_path.write_text(
            "ERROR: not 100% tests passed\n", encoding="utf-8"
        )
        try:
            tool.require_log_evidence(logs, "1" * 40, verdict)
        except tool.SealError:
            pass
        else:
            raise RuntimeError("log gate accepted a forged CTest marker")
        ctest_path.write_text(contents["ctest.log"], encoding="utf-8")
        trust_path = logs / "formal-trust.log"
        trust_path.write_text(
            "FAIL then " + contents["formal-trust.log"], encoding="utf-8"
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

    print("relational observability outer-seal mutation regression: PASS (8 mutations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
