#!/usr/bin/env python3
"""Adversarial mutation regression for the conservative-force outer seal."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile
from types import SimpleNamespace
from typing import Callable


TEST_DECISION = "retain_conservative_relational_force_for_research"


def load_tool():
    path = pathlib.Path(__file__).resolve().parents[1] / "tools" / \
        "seal_conservative_force_consistency_evidence.py"
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
        ],
        "exact-oracle.json": [
            "python", "reference/conservative_force_oracle.py",
            "--verify", "tests/conservative_force_oracle.canonical.json",
        ],
        "exact-oracle-regression.json": [
            "python", "tests/conservative_force_oracle_test.py",
        ],
        "lean-build.json": ["lake", "--wfail", "build"],
        "lean-axioms.json": ["lake", "env", "lean", "MLSFormal/AxiomReport.lean"],
        "formal-trust.json": [
            "python", "tools/formal_trust_scan.py", "--formal-root", "formal",
        ],
        "compiler-versions.json": ["cmake", "--version"],
        "parent-evidence.json": [
            "python", "tools/verify_force_parent_evidence.py",
            "--parent-bundle", str(root / "accepted-parent"), "--verify",
        ],
    }
    outputs = {
        "configure.json": "Build files have been written\n",
        "build.json": "mls_conservative_force_consistency_diagnostic\n",
        "ctest.json": "100% tests passed, 0 tests failed\n",
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
        "compiler-versions.json": "source_sha=" + source_sha + " version\n",
        "parent-evidence.json": (
            "force parent evidence: PASS\nsource_sha=" + tool.PARENT_SHA +
            "\nmanifest_pre_hash=" + tool.PARENT_EVIDENCE_PRE_HASH + "\n" +
            "\n".join(name + "=" + digest
                       for name, digest in tool.PARENT_TABLE_SHA256.items()) + "\n"),
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
            write_receipt_directory(logs, changed)
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
        if lexical_bindings != bindings:
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
