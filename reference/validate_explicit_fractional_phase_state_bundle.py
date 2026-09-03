#!/usr/bin/env python3
"""Fresh validator for sealed Explicit Fractional Phase-State evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


BRANCH = "explicit-fractional-phase-state-lab"
REPOSITORY = "RobVanProd/materiallifesubstrate"
WORKFLOW = "Explicit Fractional Phase-State Lab"
DECISION = (
    "fractional_phase_state_restores_dynamics_but_bounded_representation_unresolved"
)
PARENT_SHA = "6dfaf29821ded7e1349358c671b52e73f345c26a"
SHA1 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
REQUIRED_JOBS = {
    "C++ / Linux GCC",
    "C++ / Linux Clang",
    "C++ / Windows MSVC",
    "Python exact rational experiment and oracle",
    "Pinned Lean build and axiom output",
}


def invoke(
    command: list[str], cwd: Path, timeout: int = 7200
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def require_success(completed: subprocess.CompletedProcess[str], label: str) -> None:
    if completed.returncode != 0:
        raise RuntimeError(
            f"{label} failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


def compare_directories(first: Path, second: Path) -> None:
    first_files = {
        path.relative_to(first).as_posix(): path
        for path in first.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second).as_posix(): path
        for path in second.rglob("*")
        if path.is_file()
    }
    if set(first_files) != set(second_files):
        raise RuntimeError("raw twin inventories differ")
    for name, first_path in first_files.items():
        if first_path.read_bytes() != second_files[name].read_bytes():
            raise RuntimeError(f"raw twin differs: {name}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def read_metadata(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if set(row) != {"key", "value"} or row["key"] in result:
                raise RuntimeError("raw metadata schema differs")
            result[row["key"]] = row["value"]
    return result


def validate_source_identity(bundle: Path, source_sha: str) -> None:
    identity = read_json(bundle / "source" / "source-identity.json")
    expected_fields = {
        "schema",
        "repository",
        "branch",
        "source_sha",
        "tree_sha",
        "archive",
        "archive_bytes",
        "archive_sha256",
    }
    if set(identity) != expected_fields:
        raise RuntimeError("source identity field inventory differs")
    if (
        identity["schema"] != "mls.explicit-fractional-phase-state.source.v1"
        or identity["repository"] != REPOSITORY
        or identity["branch"] != BRANCH
        or identity["source_sha"] != source_sha
        or not isinstance(identity["tree_sha"], str)
        or SHA1.fullmatch(identity["tree_sha"]) is None
        or not isinstance(identity["archive"], str)
        or Path(identity["archive"]).name != identity["archive"]
        or not isinstance(identity["archive_bytes"], int)
        or not isinstance(identity["archive_sha256"], str)
        or SHA256.fullmatch(identity["archive_sha256"]) is None
    ):
        raise RuntimeError("source identity differs")
    archive = bundle / "source" / str(identity["archive"])
    if (
        not archive.is_file()
        or archive.stat().st_size != identity["archive_bytes"]
        or sha256(archive) != identity["archive_sha256"]
    ):
        raise RuntimeError("source archive identity differs")


def validate_ci_receipt(bundle: Path, source_sha: str, run_id: int) -> None:
    receipt = read_json(bundle / "receipts" / "ci-run.json")
    expected_fields = {
        "schema",
        "repository",
        "workflow",
        "run_id",
        "run_attempt",
        "head_sha",
        "head_branch",
        "event",
        "conclusion",
        "jobs",
    }
    if set(receipt) != expected_fields:
        raise RuntimeError("CI receipt field inventory differs")
    if (
        receipt["schema"] != "mls.explicit-fractional-phase-state.ci.v1"
        or receipt["repository"] != REPOSITORY
        or receipt["workflow"] != WORKFLOW
        or receipt["run_id"] != run_id
        or not isinstance(receipt["run_attempt"], int)
        or receipt["run_attempt"] < 1
        or receipt["head_sha"] != source_sha
        or receipt["head_branch"] != BRANCH
        or receipt["event"] != "push"
        or receipt["conclusion"] != "success"
        or not isinstance(receipt["jobs"], list)
    ):
        raise RuntimeError("CI receipt identity differs")
    jobs: dict[str, str] = {}
    for job in receipt["jobs"]:
        if not isinstance(job, dict) or set(job) != {"name", "conclusion"}:
            raise RuntimeError("CI job receipt schema differs")
        name = job["name"]
        conclusion = job["conclusion"]
        if not isinstance(name, str) or not isinstance(conclusion, str) or name in jobs:
            raise RuntimeError("CI job receipt identity differs")
        jobs[name] = conclusion
    if set(jobs) != REQUIRED_JOBS or any(value != "success" for value in jobs.values()):
        raise RuntimeError("required CI job did not succeed")


def validate_parent(bundle: Path, source: Path) -> None:
    parent_bundle = bundle / "parent-corefinement"
    completed = invoke(
        [
            sys.executable,
            str(source / "tools" / "seal_phase_space_time_corefinement_evidence.py"),
            "verify",
            "--bundle",
            str(parent_bundle),
        ],
        source,
    )
    require_success(completed, "nested parent outer seal")
    parent_seal = read_json(parent_bundle / "outer-seal.json")
    if (
        parent_seal.get("source_sha") != PARENT_SHA
        or parent_seal.get("decision") != "reject_order_matched_space_time_corefinement"
        or parent_seal.get("promotion") != "NO_PROMOTION"
    ):
        raise RuntimeError("nested parent scientific identity differs")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run-mutations", action="store_true")
    arguments = parser.parse_args()
    bundle = arguments.bundle.resolve()
    source = arguments.source.resolve()
    try:
        seal = invoke(
            [
                sys.executable,
                str(source / "tools" / "seal_explicit_fractional_phase_state_evidence.py"),
                "verify",
                "--bundle",
                str(bundle),
            ],
            source,
        )
        require_success(seal, "outer seal")
        seal_value = read_json(bundle / "outer-seal.json")
        source_sha = seal_value.get("source_sha")
        run_id = seal_value.get("ci_run_id")
        if (
            not isinstance(source_sha, str)
            or SHA1.fullmatch(source_sha) is None
            or not isinstance(run_id, int)
        ):
            raise RuntimeError("outer source or CI identity malformed")
        compare_directories(bundle / "raw-a", bundle / "raw-b")
        raw_metadata = read_metadata(bundle / "raw-a" / "metadata.csv")
        if (
            raw_metadata.get("source_sha") != source_sha
            or raw_metadata.get("source_dirty") != "false"
            or raw_metadata.get("configured_source_branch") != BRANCH
        ):
            raise RuntimeError("raw/source identity differs")
        validate_source_identity(bundle, source_sha)
        validate_ci_receipt(bundle, source_sha, run_id)
        validate_parent(bundle, source)
        with tempfile.TemporaryDirectory(prefix="mls-fractional-verify-") as temporary:
            output = Path(temporary) / "oracle-summary.json"
            oracle = invoke(
                [
                    sys.executable,
                    str(source / "reference" / "explicit_fractional_phase_state_oracle.py"),
                    "--raw",
                    str(bundle / "raw-a"),
                    "--parent-raw",
                    str(bundle / "parent-corefinement" / "raw-a"),
                    "--output",
                    str(output),
                ],
                source,
            )
            require_success(oracle, "110-digit trajectory oracle")
            if output.read_bytes() != (bundle / "oracle" / "oracle-summary.json").read_bytes():
                raise RuntimeError("fresh oracle JSON differs")
            summary = read_json(output)
            convergence = summary.get("convergence")
            accounting = summary.get("accounting")
            complexity = summary.get("state_complexity")
            energy = summary.get("energy")
            if (
                summary.get("decision") != DECISION
                or summary.get("precision_decimal_digits") != 110
                or summary.get("promotion") != "NO_PROMOTION"
                or not isinstance(convergence, dict)
                or any(
                    not isinstance(convergence.get(scenario), dict)
                    or convergence[scenario].get("candidate_second_order_window") is not True
                    or convergence[scenario].get("control_distinguishable") is not True
                    for scenario in ("k4_breathing", "k4_internal", "octahedron_deformation")
                )
                or not isinstance(accounting, dict)
                or any(
                    accounting.get(field) is not True
                    for field in (
                        "exact_stage_invariants",
                        "exact_central_kicks",
                        "complete_state_reversible",
                        "checkpoint_exact",
                        "domain_atomic",
                        "translation_rotation_permutation_exact",
                    )
                )
                or not isinstance(complexity, dict)
                or complexity.get("any_ceiling_exceeded") is not True
                or not isinstance(energy, dict)
                or energy.get("short_energy_contracts") is not True
                or energy.get("long_run_complete") is not False
                or energy.get("long_energy_contracts") != "blocked_by_complexity_ceiling"
            ):
                raise RuntimeError("fresh scientific disposition differs")
        if arguments.run_mutations:
            mutations = invoke(
                [
                    sys.executable,
                    str(source / "tests" / "explicit_fractional_phase_state_oracle_test.py"),
                    "--raw",
                    str(bundle / "raw-a"),
                    "--parent-raw",
                    str(bundle / "parent-corefinement" / "raw-a"),
                ],
                source,
            )
            require_success(mutations, "oracle mutation regression")
        print(
            "EXPLICIT FRACTIONAL PHASE STATE EVIDENCE VALID: "
            f"source={source_sha} files={len(seal_value['payload'])} "
            f"prehash={seal_value['outer_pre_hash']} {DECISION} NO_PROMOTION"
        )
        return 0
    except (
        OSError,
        ValueError,
        RuntimeError,
        json.JSONDecodeError,
        subprocess.TimeoutExpired,
    ) as error:
        print(f"EXPLICIT FRACTIONAL PHASE STATE EVIDENCE INVALID: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
