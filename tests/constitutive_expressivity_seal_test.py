#!/usr/bin/env python3
"""Adversarial mutation regression for the constitutive outer seal."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
from typing import Callable


def load_tool():
    path = pathlib.Path(__file__).resolve().parents[1] / "tools" / \
        "seal_constitutive_expressivity_evidence.py"
    spec = importlib.util.spec_from_file_location("constitutive_sealer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load constitutive evidence sealer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect_rejection(tool, operation: Callable[[], object], label: str) -> None:
    try:
        operation()
    except tool.SealError:
        return
    raise RuntimeError(f"seal accepted {label} mutation")


def receipt(tool, source_sha: str, output: str) -> dict:
    payload = output.encode("utf-8")
    return {
        "schema": tool.RECEIPT_SCHEMA,
        "label": "test",
        "source_sha": source_sha,
        "branch": tool.BRANCH,
        "cwd": "D:/MaterialLifeSubstrate",
        "command": ["test", "--exact"],
        "started_at_utc": "2026-08-30T00:00:00Z",
        "ended_at_utc": "2026-08-30T00:00:01Z",
        "exit_code": 0,
        "output_bytes": len(payload),
        "output_sha256": tool.sha256_bytes(payload),
        "output": output,
    }


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


def main() -> int:
    tool = load_tool()
    source_sha = "1" * 40
    mutations = 0

    # Exact source provenance is decision-bearing.
    with tempfile.TemporaryDirectory(prefix="mls-constitutive-bundle-") as temporary:
        bundle = pathlib.Path(temporary)
        summary = {
            "schema": "mls.constitutive-expressivity.summary.v1",
            "smoke": False,
            "decision": tool.DECISION,
            "no_promotion": True,
            "candidate_b_decision_inputs": 0,
            "candidate_d_decision_inputs": 0,
            "dense_global_rows": 0,
            "bulk_failures": 0,
            "graph_failures": 0,
            "metamorphic_failures": 0,
            "checkpoint_failures": 0,
            "prohibited_features": {
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
            },
        }
        provenance = {
            "source_sha": source_sha,
            "source_branch": tool.BRANCH,
            "expected_branch": tool.BRANCH,
            "source_dirty": False,
            "parent_sha": tool.PARENT_SHA,
            "exact_oracle_pre_hash": tool.ORACLE_PRE_HASH,
            "inherited_blobs": tool.INHERITED_BLOBS,
        }
        (bundle / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        (bundle / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
        tool.validate_bundle_claims(bundle, source_sha)
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
    with tempfile.TemporaryDirectory(prefix="mls-constitutive-twins-") as temporary:
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

    # Receipt output, exit status, source, and command are authenticated fields.
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
        "ci_run_id": "77",
        "ci_attempt": 1,
        "tag": tool.TAG,
        "decision": tool.DECISION,
        "promotion_permitted": False,
        "bundle_tree_sha256": "4" * 64,
    }
    with tempfile.TemporaryDirectory(prefix="mls-constitutive-seal-") as temporary:
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
        "constitutive expressivity outer-seal mutation regression: "
        f"PASS ({mutations} mutations: source/tag/CI/twin/receipt/manifest/inventory)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
