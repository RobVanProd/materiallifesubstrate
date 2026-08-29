#!/usr/bin/env python3
"""Mutation regression for the Projection Foundation outer evidence seal.

The test constructs a complete synthetic seal, checks deterministic create and
positive verify, then exercises raw integrity failures and semantic mutations
whose outer manifests have been independently refreshed.  It intentionally
does not use the sealer to refresh adversarial manifests.
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
OUTER_SCHEMA = "mls.projection-foundation.outer-evidence-seal.v1"
METADATA_SCHEMA = "mls.projection-foundation.outer-evidence-metadata.v1"
CI_SCHEMA = "mls.projection-foundation.ci-metadata.v1"
INNER_SCHEMA = "mls.projection-foundation.manifest.v1"
BRANCH = "projection-foundation-lab"
REPOSITORY = "https://github.com/RobVanProd/materiallifesubstrate"
SOURCE_SHA = "1234567890abcdef1234567890abcdef12345678"
RUN_URL = REPOSITORY + "/actions/runs/123456"

INNER_FILES = (
    "checkpoint.csv",
    "convergence.csv",
    "exact_angular_control.csv",
    "hard_gates.csv",
    "main_raw.csv",
    "order_to_full.csv",
    "orientation_sensitivity.csv",
    "phase_sensitivity.csv",
    "ppc_raw.csv",
    "solver_failures.csv",
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
    "lean-build.log",
    "lean-axiom-report.log",
    "source-scan.log",
    "git-provenance.log",
)
COMMANDS = (
    "full_bundle_a",
    "full_bundle_b",
    "bundle_compare_validator",
    "configure",
    "build",
    "ctest",
    "exact_oracle",
    "lean_build",
    "lean_axiom_report",
    "source_scan",
    "git_provenance",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def inner_payload(hashes: Mapping[str, str]) -> bytes:
    names = sorted(hashes)
    lines = ["{", '  "algorithm": "SHA-256",', '  "files": {']
    for index, name in enumerate(names):
        comma = "," if index + 1 != len(names) else ""
        lines.append(f"    {json.dumps(name)}: {json.dumps(hashes[name])}{comma}")
    lines.extend(("  },", f'  "schema": {json.dumps(INNER_SCHEMA)}', "}"))
    return "\n".join(lines).encode("utf-8")


def refresh_inner(bundle: Path) -> None:
    hashes = {name: sha256_bytes((bundle / name).read_bytes()) for name in INNER_FILES}
    write_json(
        bundle / "manifest.json",
        {
            "algorithm": "SHA-256",
            "files": hashes,
            "pre_hash_sha256": sha256_bytes(inner_payload(hashes)),
            "schema": INNER_SCHEMA,
        },
    )


def outer_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_file() and path.relative_to(root).as_posix() != OUTER_MANIFEST:
            raw = path.read_bytes()
            records.append(
                {
                    "path": path.relative_to(root).as_posix(),
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
        {**payload, "pre_hash_sha256": sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))},
    )


def make_fixture(root: Path) -> None:
    root.mkdir(parents=True)
    prototype = root / "bundles/full-a"
    prototype.mkdir(parents=True)
    for index, name in enumerate(INNER_FILES):
        (prototype / name).write_text(f"synthetic projection artifact {index}: {name}\n", encoding="utf-8")
    refresh_inner(prototype)
    shutil.copytree(prototype, root / "bundles/full-b")

    logs = root / "logs"
    logs.mkdir()
    for name in LOGS:
        (logs / name).write_text(f"synthetic captured output: {name}\n", encoding="utf-8")

    ci_block = {
        "jobs": [
            {
                "name": "linux-gcc",
                "status": "success",
                "url": RUN_URL + "/job/789",
            },
            {
                "name": "windows-msvc",
                "status": "success",
                "url": RUN_URL + "/job/790",
            },
        ],
        "run_url": RUN_URL,
        "status": "success",
    }
    write_json(
        root / "ci/metadata.json",
        {
            "branch": BRANCH,
            **ci_block,
            "schema": CI_SCHEMA,
            "source_sha": SOURCE_SHA,
        },
    )
    summaries = {
        name: {"status": "pass", "summary": f"synthetic {name} completed"}
        for name in COMMANDS
    }
    metadata = {
        "ci": ci_block,
        "commands": [
            {
                "argv": ["synthetic-tool", "--stage", name],
                "cwd": "D:/MaterialLifeSubstrate",
                "name": name,
            }
            for name in COMMANDS
        ],
        "local": {
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
            "tag": "projection-foundation-lab-evidence-v1",
        },
    }
    write_json(root / "metadata.json", metadata)


def run_tool(tool: Path, mode: str, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(tool), mode, "--seal-dir", str(root)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def require_valid(tool: Path, root: Path, mode: str = "verify") -> None:
    result = run_tool(tool, mode, root)
    if result.returncode != 0 or "OUTER SEAL VALID" not in result.stdout:
        raise AssertionError(f"expected {mode} success\nstdout={result.stdout}\nstderr={result.stderr}")


def require_invalid(tool: Path, root: Path, label: str) -> None:
    result = run_tool(tool, "verify", root)
    if result.returncode == 0 or "OUTER SEAL INVALID" not in result.stderr:
        raise AssertionError(f"{label}: expected verify rejection\nstdout={result.stdout}\nstderr={result.stderr}")


def cloned(source: Path, destination: Path) -> Path:
    target = destination / source.name
    shutil.copytree(source, target)
    return target


def load_tool_module(path: Path) -> Any:
    specification = importlib.util.spec_from_file_location("projection_outer_seal", path)
    if specification is None or specification.loader is None:
        raise AssertionError("could not import seal tool for collision-unit regression")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tool",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "tools/seal_projection_foundation_evidence.py",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    options = parse_arguments(arguments)
    tool = options.tool.resolve()
    if not tool.is_file():
        raise SystemExit(f"seal tool not found: {tool}")

    with tempfile.TemporaryDirectory(prefix="mls-projection-outer-seal-") as temporary:
        work = Path(temporary)
        baseline = work / "baseline"
        make_fixture(baseline)
        require_valid(tool, baseline, "create")
        first_manifest = (baseline / OUTER_MANIFEST).read_bytes()
        require_valid(tool, baseline, "create")
        if (baseline / OUTER_MANIFEST).read_bytes() != first_manifest:
            raise AssertionError("create is not byte-deterministic")
        require_valid(tool, baseline)

        mutation_count = 0

        def mutation(label: str, change: Callable[[Path], None], refresh: bool = False) -> None:
            nonlocal mutation_count
            target = cloned(baseline, work / f"mutation-{mutation_count:02d}-{label}")
            change(target)
            if refresh:
                refresh_outer(target)
            require_invalid(tool, target, label)
            mutation_count += 1

        mutation(
            "unrefreshed-byte",
            lambda root: (root / "logs/build.log").write_text("tampered\n", encoding="utf-8"),
        )
        mutation(
            "unrefreshed-extra",
            lambda root: (root / "unregistered-extra.txt").write_text("extra\n", encoding="utf-8"),
        )
        mutation(
            "refreshed-missing-required-log",
            lambda root: (root / "logs/ctest.log").unlink(),
            refresh=True,
        )

        def invalid_source_sha(root: Path) -> None:
            value = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
            value["source"]["sha"] = "deadbeef"
            write_json(root / "metadata.json", value)

        mutation("refreshed-invalid-source-sha", invalid_source_sha, refresh=True)

        def missing_command(root: Path) -> None:
            value = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
            value["commands"] = [row for row in value["commands"] if row["name"] != "source_scan"]
            write_json(root / "metadata.json", value)

        mutation("refreshed-missing-command", missing_command, refresh=True)

        def divergent_ci(root: Path) -> None:
            value = json.loads((root / "ci/metadata.json").read_text(encoding="utf-8"))
            value["status"] = "failure"
            write_json(root / "ci/metadata.json", value)

        mutation("refreshed-divergent-ci", divergent_ci, refresh=True)

        mutation(
            "refreshed-stale-inner-manifest",
            lambda root: (root / "bundles/full-a/main_raw.csv").write_text("changed but inner manifest stale\n", encoding="utf-8"),
            refresh=True,
        )

        def divergent_full_bundle(root: Path) -> None:
            path = root / "bundles/full-a/main_raw.csv"
            path.write_text("self-consistently changed only in run A\n", encoding="utf-8")
            refresh_inner(path.parent)

        mutation("refreshed-divergent-full-runs", divergent_full_bundle, refresh=True)

        def duplicate_outer_path(root: Path) -> None:
            value = json.loads((root / OUTER_MANIFEST).read_text(encoding="utf-8"))
            duplicate = dict(value["files"][0])
            duplicate["path"] = duplicate["path"].upper()
            value["files"].append(duplicate)
            value["files"].sort(key=lambda row: row["path"])
            payload = {key: item for key, item in value.items() if key != "pre_hash_sha256"}
            value["pre_hash_sha256"] = sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
            write_json(root / OUTER_MANIFEST, value)

        mutation("self-consistent-case-colliding-manifest", duplicate_outer_path)

        module = load_tool_module(tool)
        try:
            module.ensure_unique_portable_paths(("Logs/A.log", "logs/a.LOG"), "test")
        except module.SealError:
            pass
        else:
            raise AssertionError("portable case-collision helper accepted a collision")

        symlink_result = "not-supported"
        symlink_target = cloned(baseline, work / "symlink-case")
        try:
            os.symlink(symlink_target / "logs/build.log", symlink_target / "linked.log")
        except (OSError, NotImplementedError):
            pass
        else:
            require_invalid(tool, symlink_target, "symlink")
            mutation_count += 1
            symlink_result = "rejected"

    print(
        "projection foundation outer seal mutation regression PASS "
        f"(positive + deterministic create + {mutation_count} CLI mutations; "
        f"portable case collision rejected; symlink={symlink_result})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
