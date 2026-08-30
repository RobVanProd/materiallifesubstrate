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
    bundle_a = root / "bundle-a"
    bundle_b = root / "bundle-b"
    commands = {
        "configure.json": [
            "cmake", "-S", str(repo), "-B", str(build),
            "-DMLS_WARNINGS_AS_ERRORS=ON",
            "-DMLS_RUN_EXTENDED_EXACT_TESTS=ON",
        ],
        "build.json": ["cmake", "--build", str(build)],
        "ctest.json": [
            "ctest", "--test-dir", str(build), "--output-on-failure"
        ],
        "producer-a.json": [
            str(build / "mls_constitutive_expressivity_diagnostic.exe"),
            "--output", str(bundle_a),
        ],
        "producer-b.json": [
            str(build / "mls_constitutive_expressivity_diagnostic.exe"),
            "--output", str(bundle_b),
        ],
        "twin-compare.json": [
            "python", "reference/validate_constitutive_expressivity_bundle.py",
            "--bundle", str(bundle_a), "--compare", str(bundle_b),
        ],
        "validator.json": [
            "python", "reference/validate_constitutive_expressivity_bundle.py",
            "--bundle", str(bundle_b), "--compare", str(bundle_a),
        ],
        "validator-regression.json": [
            "python", "tests/constitutive_expressivity_bundle_validator_test.py",
        ],
        "exact-oracle.json": [
            "python", "reference/constitutive_expressivity_oracle.py",
            "--verify", "tests/constitutive_expressivity_oracle.canonical.json",
        ],
        "exact-oracle-regression.json": [
            "python", "tests/constitutive_expressivity_oracle_test.py",
        ],
        "lean-build.json": ["lake", "--wfail", "build"],
        "lean-axioms.json": ["lake", "env", "lean", "MLSFormal/AxiomReport.lean"],
        "formal-trust.json": [
            "python", "tools/formal_trust_scan.py", "--formal-root", "formal",
        ],
        "compiler-versions.json": ["cmake", "--version"],
        "parent-subset.json": [
            "python", "tools/derive_constitutive_parent_subset.py",
            "--parent-bundle", str(root / "accepted-parent"), "--verify",
        ],
    }
    outputs = {
        "configure.json": "Build files have been written\n",
        "build.json": "mls_constitutive_expressivity_diagnostic\n",
        "ctest.json": "100% tests passed, 0 tests failed\n",
        "producer-a.json": tool.DECISION + " NO PROMOTION\n",
        "producer-b.json": tool.DECISION + " NO PROMOTION\n",
        "twin-compare.json": "PASS\n",
        "validator.json": "CONSTITUTIVE EXPRESSIVITY BUNDLE VALID\n",
        "validator-regression.json": "PASS\n",
        "exact-oracle.json": tool.ORACLE_PRE_HASH + "\n",
        "exact-oracle-regression.json": "PASS\n",
        "lean-build.json": "Build completed successfully\n",
        "lean-axioms.json": "relationalStiffness_kernel_eq_relationKernel\n",
        "formal-trust.json": "PASS: no sorry, admit, sorryAx\n",
        "compiler-versions.json": "source_sha=" + source_sha + " version\n",
        "parent-subset.json": (
            "configurations.csv 45d162381ec723dd9ce744f2cc23c4d21435a52b7c7e60a182073ee19a08d60e\n"
            "packets.csv 843c9cb22c0b55e07c207135125a8334b0dd170a0f708aa1fb50f34d4c5d7363\n"
            "relations.csv 0b2e21dcbf26454af316bec9323627aa1488ebc7aa1f14c006bfb41a231e0e6f\n"
            "constitutive parent subset: PASS\n"
        ),
    }
    return {
        name: receipt(
            tool, source_sha, outputs[name], label=pathlib.Path(name).stem,
            command=command, cwd=str(repo),
        )
        for name, command in commands.items()
    }


def write_receipt_directory(path: pathlib.Path, receipts: dict[str, dict]) -> None:
    path.mkdir()
    for name, value in receipts.items():
        (path / name).write_text(json.dumps(value), encoding="utf-8")
    (path / "ci-run.json").write_text("{}", encoding="utf-8")


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
        for name in ("configurations.csv", "packets.csv", "relations.csv"):
            (bundle / name).write_text(f"synthetic {name}\n", encoding="utf-8")
        selected_subset = {
            "mode": "accepted_parent_subset",
            **{
                name: tool.sha256(bundle / name)
                for name in ("configurations.csv", "packets.csv", "relations.csv")
            },
        }
        frozen_selected_subset = tool.SELECTED_SUBSET_SHA256
        tool.SELECTED_SUBSET_SHA256 = selected_subset
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
            "selected_subset_sha256": selected_subset,
        }
        (bundle / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        (bundle / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
        tool.validate_bundle_claims(bundle, source_sha)
        provenance["selected_subset_sha256"] = {
            **selected_subset,
            "packets.csv": "0" * 64,
        }
        (bundle / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
        expect_rejection(
            tool, lambda: tool.validate_bundle_claims(bundle, source_sha),
            "selected parent subset",
        )
        mutations += 1
        provenance["selected_subset_sha256"] = selected_subset
        provenance["source_sha"] = "2" * 40
        (bundle / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
        expect_rejection(
            tool, lambda: tool.validate_bundle_claims(bundle, source_sha),
            "bundle source SHA",
        )
        tool.SELECTED_SUBSET_SHA256 = frozen_selected_subset
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

    # Receipt argv is parsed token-by-token and the exact build/bundle path
    # relationships are integrity-bound.  Markers cannot substitute for those
    # relationships, and the receipts do not authenticate OS execution.
    if "authenticated command receipts" in (tool.__doc__ or "").lower():
        raise RuntimeError("seal still overclaims authenticated execution")
    with tempfile.TemporaryDirectory(prefix="mls-constitutive-receipts-") as temporary:
        root = pathlib.Path(temporary)
        source = valid_receipts(tool, source_sha, root)

        def evaluate(changed: dict[str, dict]) -> dict:
            logs = root / ("logs-" + str(evaluate.counter))
            evaluate.counter += 1
            write_receipt_directory(logs, changed)
            return tool.require_receipts(
                logs, source_sha,
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
            ("producer bundle-a output", argv_mutation(
                "producer-a.json", "--output", str(root / "other-a"))),
            ("validator bundle path", argv_mutation(
                "validator.json", "--bundle", str(root / "other-a"))),
            ("twin comparator path", argv_mutation(
                "twin-compare.json", "--compare", str(root / "other-b"))),
            ("accepted parent bundle path", argv_mutation(
                "parent-subset.json", "--parent-bundle",
                str(root / "wrong-parent"))),
        ):
            expect_rejection(tool, lambda changed=changed: evaluate(changed), label)
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
        "ci_run_id": "77",
        "ci_attempt": 1,
        "tag": tool.TAG,
        "decision": tool.DECISION,
        "promotion_permitted": False,
        "bundle_tree_sha256": "4" * 64,
        "receipt_path_bindings": {
            "schema": tool.RECEIPT_BINDINGS_SCHEMA,
            "semantics":
                "integrity-bound-command-receipts-not-execution-authentication",
        },
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
