#!/usr/bin/env python3
"""Mutation regression for the exactness/nullspace outer evidence seal.

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
OUTER_SCHEMA = "mls.projection-exactness-nullspace.outer-evidence-seal.v1"
METADATA_SCHEMA = (
    "mls.projection-exactness-nullspace.outer-evidence-metadata.v1"
)
CI_SCHEMA = (
    "mls.projection-exactness-nullspace.independent-ci-metadata.v1"
)
INNER_SCHEMA = "mls.projection-exactness-nullspace.manifest.v1"
SUMMARY_SCHEMA = "mls.projection-exactness-nullspace.summary.v1"
BRANCH = "projection-exactness-nullspace-lab"
PARENT_SHA = "beac8861314e9a2c18e59fd65c426cfdbf75882c"
REPOSITORY = "https://github.com/RobVanProd/materiallifesubstrate"
SOURCE_SHA = "1234567890abcdef1234567890abcdef12345678"
RUN_URL = REPOSITORY + "/actions/runs/123456"
VALIDATOR_MARKER = "PROJECTION EXACTNESS NULLSPACE BUNDLE VALID:"

INNER_FILES = (
    "systems.csv",
    "particles.csv",
    "nodes.csv",
    "stencils.csv",
    "matrix.csv",
    "rhs.csv",
    "witness.csv",
    "solve_diagnostics.csv",
    "high_precision.csv",
    "nullspace_modes.csv",
    "nullspace_metrics.csv",
    "summary.json",
)
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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
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
            f"synthetic exactness/nullspace artifact {index}: {name}\n",
            encoding="utf-8",
        )
    write_json(
        bundle / "summary.json",
        {
            "branch": BRANCH,
            "mode": "full",
            "parent_sha": PARENT_SHA,
            "producer": "cpp_projection_exactness_nullspace_lab",
            "promotion": False,
            "schema": SUMMARY_SCHEMA,
            "seed": 260828,
            "source_sha": SOURCE_SHA,
        },
    )
    refresh_inner(bundle)


def make_provenance(root: Path) -> None:
    logs = root / "logs"
    logs.mkdir(parents=True)
    for name in LOGS:
        text = f"synthetic captured output: {name}\n"
        if name == "full-bundle-validator.log":
            text += (
                VALIDATOR_MARKER
                + " systems=76 exported=14 accepted_modes=1 "
                "visible_modes=1 decision="
                "stop_center_state_gradient_nullspace_blocker\n"
            )
        (logs / name).write_text(text, encoding="utf-8")

    jobs = [
        {
            "id": "linux_gcc",
            "name": "C++ / Linux GCC",
            "status": "queued",
            "url": RUN_URL + "/job/701",
        },
        {
            "id": "linux_clang",
            "name": "C++ / Linux Clang",
            "status": "queued",
            "url": RUN_URL + "/job/702",
        },
        {
            "id": "windows_msvc",
            "name": "C++ / Windows MSVC",
            "status": "queued",
            "url": RUN_URL + "/job/703",
        },
        {
            "id": "python_oracle",
            "name": "Python exact oracle",
            "status": "queued",
            "url": RUN_URL + "/job/704",
        },
        {
            "id": "lean",
            "name": "Pinned Lean build and axiom output",
            "status": "queued",
            "url": RUN_URL + "/job/705",
        },
    ]
    write_json(
        root / "ci/metadata.json",
        {
            "branch": BRANCH,
            "execution_context": "independent_ci",
            "jobs": jobs,
            "repository_url": REPOSITORY,
            "run_url": RUN_URL,
            "schema": CI_SCHEMA,
            "source_sha": SOURCE_SHA,
            "status": "queued",
        },
    )

    commands: list[dict[str, Any]] = []
    for name in RESULT_EVIDENCE:
        if name == "bundle_compare_validator":
            argv = [
                sys.executable,
                "reference/validate_projection_exactness_nullspace_bundle.py",
                "--bundle",
                "evidence/run-a",
                "--compare",
                "evidence/run-b",
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
            "independent_ci": {
                "execution_context": "independent_ci",
                "metadata_path": "ci/metadata.json",
            },
            "local": {
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
            "source": {
                "branch": BRANCH,
                "repository_url": REPOSITORY,
                "sha": SOURCE_SHA,
                "tag": "projection-exactness-nullspace-evidence-v1",
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
    payload = {
        "algorithm": "SHA-256",
        "files": records,
        "metadata_path": "metadata.json",
        "schema": OUTER_SCHEMA,
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
    tool: Path,
    bundle_a: Path,
    bundle_b: Path,
    provenance: Path,
    seal_dir: Path,
) -> subprocess.CompletedProcess[str]:
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
    tool: Path, seal_dir: Path
) -> subprocess.CompletedProcess[str]:
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
    tool: Path,
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


def require_verify_valid(tool: Path, seal_dir: Path) -> None:
    result = run_verify(tool, seal_dir)
    if result.returncode != 0 or "OUTER SEAL VALID" not in result.stdout:
        raise AssertionError(
            "expected verify success\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )


def require_invalid(tool: Path, seal_dir: Path, label: str) -> None:
    result = run_verify(tool, seal_dir)
    if result.returncode == 0 or "OUTER SEAL INVALID" not in result.stderr:
        raise AssertionError(
            f"{label}: expected verify rejection\n"
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
        "projection_exactness_nullspace_outer_seal", path
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
            / "tools/seal_projection_exactness_nullspace_evidence.py"
        ),
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    options = parse_arguments(arguments)
    tool = options.tool.resolve()
    if not tool.is_file():
        raise SystemExit(f"seal tool not found: {tool}")

    with tempfile.TemporaryDirectory(
        prefix="mls-exactness-nullspace-outer-seal-"
    ) as temporary:
        work = Path(temporary)
        source_a = work / "source-run-a"
        source_b = work / "source-run-b"
        provenance = work / "source-provenance"
        make_bundle(source_a)
        shutil.copytree(source_a, source_b)
        make_provenance(provenance)

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
        if copied_ci["status"] != "queued":
            raise AssertionError(
                "create inferred independent CI success from local PASS data"
            )

        mutation_count = 0

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
                    "execution_context", "local"
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
                    "source_sha", "0" * 40
                ),
            ),
            refresh=True,
        )
        mutation(
            "refreshed-stale-inner-manifest",
            lambda root: (
                root / "bundles/full-a/systems.csv"
            ).write_text("changed with stale inner manifest\n", encoding="utf-8"),
            refresh=True,
        )

        def divergent_full_bundle(root: Path) -> None:
            path = root / "bundles/full-a/systems.csv"
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

        module = load_tool_module(tool)
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

    print(
        "projection exactness/nullspace outer seal mutation regression PASS "
        "(immutable-input copy + deterministic create + positive verify + "
        f"{mutation_count} CLI mutations; portable path ambiguity rejected; "
        f"symlink={symlink_result})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
