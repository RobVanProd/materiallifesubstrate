#!/usr/bin/env python3
"""Create or verify the Projection Exactness + Nullspace outer evidence seal.

Create copies two already-validated, byte-identical full bundles and a
provenance tree into a new seal directory.  It never writes to any input.
Verify checks the complete regular-file inventory, both producer manifests,
the captured independent-validator PASS record, source provenance, local
evidence, and the separately identified independent-CI record.

The seal is a canonical SHA-256 integrity record, not a signature and not a
claim that local results establish an independent CI result.  CI status is
copied only from the dedicated independent-CI metadata file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, NoReturn, Sequence


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
ACCEPTED_PARENT_SHA = "beac8861314e9a2c18e59fd65c426cfdbf75882c"
PUBLIC_REPOSITORY = "https://github.com/RobVanProd/materiallifesubstrate"
SEED = 260828

FULL_BUNDLES = ("bundles/full-a", "bundles/full-b")
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
    "high_precision_pivots.csv",
    "nullspace_status.csv",
    "nullspace_modes.csv",
    "nullspace_metrics.csv",
    "summary.json",
)

REQUIRED_LOGS = (
    "logs/full-bundle-a.log",
    "logs/full-bundle-b.log",
    "logs/full-bundle-compare.log",
    "logs/full-bundle-validator.log",
    "logs/configure.log",
    "logs/build.log",
    "logs/ctest.log",
    "logs/exact-oracle.log",
    "logs/validator-mutation.log",
    "logs/lean-build.log",
    "logs/lean-axiom-report.log",
    "logs/source-scan.log",
    "logs/git-provenance.log",
)

REQUIRED_COMMANDS = frozenset(
    {
        "full_bundle_a",
        "full_bundle_b",
        "bundle_compare_validator",
        "configure",
        "build",
        "ctest",
        "exact_oracle",
        "validator_mutation",
        "lean_build",
        "lean_axiom_report",
        "source_scan",
        "git_provenance",
    }
)
REQUIRED_TOOL_VERSIONS = frozenset(
    {"python", "cmake", "ctest", "cxx", "git", "lean", "lake"}
)
REQUIRED_RESULT_EVIDENCE = {
    "full_bundle_a": frozenset({"logs/full-bundle-a.log"}),
    "full_bundle_b": frozenset({"logs/full-bundle-b.log"}),
    "bundle_compare_validator": frozenset(
        {
            "logs/full-bundle-compare.log",
            "logs/full-bundle-validator.log",
        }
    ),
    "configure": frozenset({"logs/configure.log"}),
    "build": frozenset({"logs/build.log"}),
    "ctest": frozenset({"logs/ctest.log"}),
    "exact_oracle": frozenset({"logs/exact-oracle.log"}),
    "validator_mutation": frozenset({"logs/validator-mutation.log"}),
    "lean_build": frozenset({"logs/lean-build.log"}),
    "lean_axiom_report": frozenset({"logs/lean-axiom-report.log"}),
    "source_scan": frozenset({"logs/source-scan.log"}),
    "git_provenance": frozenset({"logs/git-provenance.log"}),
}
REQUIRED_CI_JOB_IDS = frozenset(
    {
        "linux_gcc",
        "linux_clang",
        "windows_msvc",
        "python_oracle",
        "lean",
    }
)
RESULT_STATUSES = frozenset({"pass", "fail", "not_run", "inconclusive"})
CI_STATUSES = frozenset(
    {
        "success",
        "failure",
        "cancelled",
        "in_progress",
        "queued",
        "skipped",
        "neutral",
        "timed_out",
        "action_required",
        "stale",
        "not_run",
        "inconclusive",
    }
)
VALIDATOR_BASENAME = "validate_projection_exactness_nullspace_bundle.py"
VALIDATOR_SUCCESS_MARKER = (
    "PROJECTION EXACTNESS NULLSPACE BUNDLE VALID:"
)

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
NAME_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
TAG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}\Z")
WINDOWS_RESERVED_RE = re.compile(
    r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?\Z",
    re.IGNORECASE,
)


class SealError(RuntimeError):
    """A deterministic evidence-integrity or schema failure."""


def fail(message: str) -> NoReturn:
    raise SealError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            fail(f"duplicate JSON member: {key!r}")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> NoReturn:
    fail(f"nonstandard JSON number: {value}")


def read_json(path: Path) -> Any:
    try:
        raw = path.read_bytes()
    except OSError as error:
        fail(f"cannot read {path}: {error}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        fail(f"{path} is not UTF-8: {error}")
    try:
        return json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, SealError) as error:
        fail(f"invalid JSON in {path}: {error}")


def _canonical_json(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        fail(f"value cannot be represented as canonical JSON: {error}")
    return text.encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _portable_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _validate_component(name: str, context: str) -> None:
    require(name not in {"", ".", ".."}, f"unsafe empty/dot path component: {context}")
    require(
        unicodedata.normalize("NFC", name) == name,
        f"path is not Unicode NFC: {context}",
    )
    require("\\" not in name, f"backslash is not portable in path: {context}")
    require(
        not any(character in '<>:"|?*' for character in name),
        f"nonportable character in path: {context}",
    )
    require(
        not name.endswith((" ", ".")),
        f"trailing space/dot is not portable in path: {context}",
    )
    require(
        all(ord(character) >= 0x20 and character != "\x7f" for character in name),
        f"control character in path: {context}",
    )
    require(
        WINDOWS_RESERVED_RE.fullmatch(name) is None,
        f"reserved Windows path component: {context}",
    )


def ensure_unique_portable_paths(paths: Iterable[str], context: str) -> None:
    """Reject unsafe, duplicate, normalized, or case-folded relative paths."""

    seen: dict[str, str] = {}
    for relative in paths:
        require(
            isinstance(relative, str) and relative != "",
            f"invalid path in {context}",
        )
        require(
            not relative.startswith("/"),
            f"absolute path in {context}: {relative!r}",
        )
        components = relative.split("/")
        for component in components:
            _validate_component(component, relative)
        key = _portable_key(relative)
        previous = seen.get(key)
        require(
            previous is None,
            f"duplicate/case-colliding path in {context}: "
            f"{previous!r} and {relative!r}",
        )
        seen[key] = relative


def _is_junction(path: Path) -> bool:
    predicate = getattr(path, "is_junction", None)
    return bool(predicate()) if predicate is not None else False


def _hash_regular_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode), f"not a regular file: {path}")
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
            after = os.fstat(stream.fileno())
    except OSError as error:
        fail(f"cannot hash {path}: {error}")
    require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        f"file changed while hashing: {path}",
    )
    return before.st_size, digest.hexdigest()


def scan_regular_files(
    root: Path, *, exclude_root_outer_manifest: bool = False
) -> list[dict[str, Any]]:
    """Return every regular file below root and reject ambiguous tree entries."""

    require(root.exists(), f"directory does not exist: {root}")
    require(
        not root.is_symlink() and not _is_junction(root),
        f"tree root is a link/junction: {root}",
    )
    require(root.is_dir(), f"tree root is not a directory: {root}")

    discovered: list[tuple[str, Path]] = []

    def visit(directory: Path, prefix: tuple[str, ...]) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as error:
            fail(f"cannot scan {directory}: {error}")
        require(not prefix or bool(entries), f"empty directories are forbidden: {'/'.join(prefix)}")

        sibling_names: dict[str, str] = {}
        for entry in entries:
            relative_parts = (*prefix, entry.name)
            relative = "/".join(relative_parts)
            _validate_component(entry.name, relative)
            sibling_key = _portable_key(entry.name)
            previous = sibling_names.get(sibling_key)
            require(
                previous is None,
                f"case-colliding sibling entries: {previous!r} and "
                f"{entry.name!r} in {directory}",
            )
            sibling_names[sibling_key] = entry.name

            path = Path(entry.path)
            require(
                not entry.is_symlink() and not _is_junction(path),
                f"links/junctions are forbidden in evidence: {relative}",
            )
            if entry.is_dir(follow_symlinks=False):
                visit(path, relative_parts)
            elif entry.is_file(follow_symlinks=False):
                if (
                    exclude_root_outer_manifest
                    and not prefix
                    and sibling_key == _portable_key(OUTER_MANIFEST)
                ):
                    require(
                        entry.name == OUTER_MANIFEST,
                        "outer manifest has a case-colliding spelling: "
                        f"{entry.name!r}",
                    )
                    continue
                discovered.append((relative, path))
            else:
                fail(f"special filesystem entry is forbidden in evidence: {relative}")

    visit(root, ())
    ensure_unique_portable_paths(
        (relative for relative, _ in discovered), "evidence tree"
    )

    records: list[dict[str, Any]] = []
    for relative, path in sorted(discovered, key=lambda pair: pair[0]):
        size, digest = _hash_regular_file(path)
        records.append({"path": relative, "sha256": digest, "size": size})
    return records


def _record_map(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    return {str(record["path"]): record for record in records}


def _digest_map(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[int, str]]:
    return {
        str(record["path"]): (int(record["size"]), str(record["sha256"]))
        for record in records
    }


def _require_exact_keys(
    value: Mapping[str, Any], keys: set[str], context: str
) -> None:
    actual = set(value)
    require(
        actual == keys,
        f"{context} keys differ: expected {sorted(keys)}, got {sorted(actual)}",
    )


def _require_nonempty_string(value: Any, context: str) -> str:
    require(
        isinstance(value, str)
        and value.strip() == value
        and value != "",
        f"{context} must be a nonempty trimmed string",
    )
    require("\x00" not in value, f"{context} contains NUL")
    return value


def _inner_manifest_payload(hashes: Mapping[str, str]) -> bytes:
    names = sorted(hashes)
    lines = ["{", '  "algorithm": "SHA-256",', '  "files": {']
    for index, name in enumerate(names):
        comma = "," if index + 1 != len(names) else ""
        lines.append(
            f"    {json.dumps(name)}: {json.dumps(hashes[name])}{comma}"
        )
    lines.extend(("  },", f'  "schema": {json.dumps(INNER_SCHEMA)}', "}"))
    return "\n".join(lines).encode("utf-8")


def validate_inner_bundle(
    bundle: Path,
    records: Sequence[Mapping[str, Any]],
    context: str,
) -> dict[str, str]:
    record_by_path = _record_map(records)
    expected_names = set(INNER_FILES) | {"manifest.json"}
    require(
        set(record_by_path) == expected_names,
        f"{context} file set differs from the registered full bundle",
    )
    require(
        all("/" not in name for name in record_by_path),
        f"{context} contains nested entries",
    )

    manifest = read_json(bundle / "manifest.json")
    require(isinstance(manifest, dict), f"{context}/manifest.json must be an object")
    _require_exact_keys(
        manifest,
        {"algorithm", "files", "pre_hash_sha256", "schema"},
        f"{context} manifest",
    )
    require(
        manifest["algorithm"] == "SHA-256"
        and manifest["schema"] == INNER_SCHEMA,
        f"{context} manifest identity mismatch",
    )
    hashes = manifest["files"]
    require(
        isinstance(hashes, dict) and set(hashes) == set(INNER_FILES),
        f"{context} inner manifest file set mismatch",
    )
    calculated: dict[str, str] = {}
    for name in INNER_FILES:
        digest = str(record_by_path[name]["sha256"])
        require(
            isinstance(hashes[name], str)
            and SHA256_RE.fullmatch(hashes[name]) is not None,
            f"{context} invalid digest for {name}",
        )
        require(
            hashes[name] == digest,
            f"{context} inner digest mismatch for {name}",
        )
        calculated[name] = digest
    expected_pre_hash = sha256_bytes(_inner_manifest_payload(calculated))
    require(
        isinstance(manifest["pre_hash_sha256"], str)
        and SHA256_RE.fullmatch(manifest["pre_hash_sha256"]) is not None,
        f"{context} inner manifest pre-hash is invalid",
    )
    require(
        manifest["pre_hash_sha256"] == expected_pre_hash,
        f"{context} inner manifest pre-hash mismatch",
    )

    summary = read_json(bundle / "summary.json")
    require(isinstance(summary, dict), f"{context}/summary.json must be an object")
    require(summary.get("schema") == SUMMARY_SCHEMA, f"{context} summary schema mismatch")
    require(summary.get("seed") == SEED, f"{context} summary seed mismatch")
    require(summary.get("branch") == BRANCH, f"{context} summary branch mismatch")
    source_sha = summary.get("source_sha")
    require(
        isinstance(source_sha, str)
        and SOURCE_SHA_RE.fullmatch(source_sha) is not None,
        f"{context} summary source SHA is invalid",
    )
    require(
        summary.get("parent_sha") == ACCEPTED_PARENT_SHA,
        f"{context} accepted parent SHA mismatch",
    )
    require(
        summary.get("mode") == "full"
        and summary.get("producer") == "cpp_projection_exactness_nullspace_lab",
        f"{context} is not final C++ full evidence",
    )
    require(summary.get("promotion") is False, f"{context} claims promotion")
    return {"branch": BRANCH, "source_sha": source_sha}


def _validate_evidence_paths(
    value: Any,
    records: Mapping[str, Mapping[str, Any]],
    context: str,
) -> list[str]:
    require(isinstance(value, list) and value, f"{context} must be a nonempty list")
    paths: list[str] = []
    for index, item in enumerate(value):
        require(isinstance(item, str), f"{context}[{index}] must be a string")
        paths.append(item)
    ensure_unique_portable_paths(paths, context)
    for path in paths:
        require(path in records, f"{context} names missing evidence: {path}")
        require(int(records[path]["size"]) > 0, f"{context} names empty evidence: {path}")
    return paths


def _validate_ci_metadata(
    root: Path,
    records: Mapping[str, Mapping[str, Any]],
    source_sha: str,
) -> None:
    path = "ci/metadata.json"
    require(path in records, "independent CI metadata is missing")
    require(int(records[path]["size"]) > 0, "independent CI metadata is empty")
    ci = read_json(root / path)
    require(isinstance(ci, dict), "ci/metadata.json must contain an object")
    _require_exact_keys(
        ci,
        {
            "schema",
            "execution_context",
            "source_sha",
            "branch",
            "repository_url",
            "run_url",
            "status",
            "jobs",
        },
        "independent CI metadata",
    )
    require(ci["schema"] == CI_SCHEMA, "independent CI schema mismatch")
    require(
        ci["execution_context"] == "independent_ci",
        "CI evidence is not explicitly independent",
    )
    require(ci["source_sha"] == source_sha, "independent CI source SHA mismatch")
    require(ci["branch"] == BRANCH, "independent CI branch mismatch")
    require(
        ci["repository_url"] == PUBLIC_REPOSITORY,
        "independent CI repository URL mismatch",
    )
    run_url = _require_nonempty_string(ci["run_url"], "independent CI run_url")
    run_prefix = PUBLIC_REPOSITORY + "/actions/runs/"
    require(
        run_url.startswith(run_prefix),
        "independent CI run URL is outside the public repository",
    )
    require(
        run_url[len(run_prefix) :].isdigit(),
        "independent CI run URL must end in a numeric run id",
    )
    status_value = _require_nonempty_string(ci["status"], "independent CI status")
    require(status_value in CI_STATUSES, f"invalid independent CI status: {status_value!r}")
    require(
        status_value == "success",
        f"independent CI run is not successful: {status_value!r}",
    )

    jobs_value = ci["jobs"]
    require(
        isinstance(jobs_value, list) and jobs_value,
        "independent CI jobs must be a nonempty list",
    )
    jobs: dict[str, Mapping[str, Any]] = {}
    names: dict[str, str] = {}
    for index, item in enumerate(jobs_value):
        require(isinstance(item, dict), f"independent CI jobs[{index}] must be an object")
        _require_exact_keys(
            item, {"id", "name", "status", "url"}, f"independent CI jobs[{index}]"
        )
        job_id = _require_nonempty_string(item["id"], f"independent CI jobs[{index}].id")
        require(NAME_RE.fullmatch(job_id) is not None, f"invalid CI job id: {job_id!r}")
        require(job_id not in jobs, f"duplicate independent CI job id: {job_id!r}")
        name = _require_nonempty_string(
            item["name"], f"independent CI jobs[{index}].name"
        )
        name_key = _portable_key(name)
        require(
            name_key not in names,
            f"duplicate/case-colliding CI job names: {names.get(name_key)!r} and {name!r}",
        )
        names[name_key] = name
        job_status = _require_nonempty_string(
            item["status"], f"independent CI jobs[{index}].status"
        )
        require(job_status in CI_STATUSES, f"invalid CI job status: {job_status!r}")
        require(
            job_status == "success",
            f"independent CI job {job_id!r} is not successful: {job_status!r}",
        )
        url = _require_nonempty_string(
            item["url"], f"independent CI jobs[{index}].url"
        )
        require(
            url.startswith(run_url + "/job/")
            and url[len(run_url + "/job/") :].isdigit(),
            f"CI job URL is outside the declared run: {url}",
        )
        jobs[job_id] = item
    missing_jobs = REQUIRED_CI_JOB_IDS - set(jobs)
    require(
        not missing_jobs,
        f"independent CI jobs are missing: {sorted(missing_jobs)}",
    )


def _require_log_marker(root: Path, relative: str, marker: str) -> None:
    try:
        text = (root / relative).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        fail(f"cannot read captured text log {relative}: {error}")
    require(marker in text, f"{relative} lacks required captured marker: {marker}")


def validate_metadata(
    root: Path,
    records: Sequence[Mapping[str, Any]],
    bundle_identity: Mapping[str, str],
) -> dict[str, Any]:
    record_by_path = _record_map(records)
    metadata = read_json(root / "metadata.json")
    require(isinstance(metadata, dict), "metadata.json must contain an object")
    _require_exact_keys(
        metadata,
        {"schema", "source", "commands", "local", "independent_ci"},
        "metadata",
    )
    require(metadata["schema"] == METADATA_SCHEMA, "metadata schema mismatch")

    source = metadata["source"]
    require(isinstance(source, dict), "metadata.source must be an object")
    _require_exact_keys(
        source, {"sha", "branch", "tag", "repository_url"}, "metadata.source"
    )
    source_sha = source["sha"]
    require(
        isinstance(source_sha, str)
        and SOURCE_SHA_RE.fullmatch(source_sha) is not None,
        "source SHA must be exactly 40 lowercase hexadecimal characters",
    )
    require(source["branch"] == BRANCH, f"source branch must be {BRANCH!r}")
    require(
        source_sha == bundle_identity["source_sha"],
        "metadata source SHA differs from full-bundle source SHA",
    )
    tag = _require_nonempty_string(source["tag"], "metadata.source.tag")
    require(
        TAG_RE.fullmatch(tag) is not None and ".." not in tag and "@{" not in tag,
        "invalid Git tag spelling",
    )
    require(
        source["repository_url"] == PUBLIC_REPOSITORY,
        "public repository URL mismatch",
    )

    commands = metadata["commands"]
    require(
        isinstance(commands, list) and commands,
        "metadata.commands must be a nonempty list",
    )
    commands_by_name: dict[str, Mapping[str, Any]] = {}
    for index, command in enumerate(commands):
        require(isinstance(command, dict), f"metadata.commands[{index}] must be an object")
        _require_exact_keys(
            command, {"name", "cwd", "argv"}, f"metadata.commands[{index}]"
        )
        name = _require_nonempty_string(
            command["name"], f"metadata.commands[{index}].name"
        )
        require(NAME_RE.fullmatch(name) is not None, f"invalid command name: {name!r}")
        require(name not in commands_by_name, f"duplicate command name: {name!r}")
        _require_nonempty_string(command["cwd"], f"metadata.commands[{index}].cwd")
        argv = command["argv"]
        require(
            isinstance(argv, list) and argv,
            f"metadata.commands[{index}].argv must be nonempty",
        )
        for argument_index, argument in enumerate(argv):
            _require_nonempty_string(
                argument,
                f"metadata.commands[{index}].argv[{argument_index}]",
            )
        commands_by_name[name] = command
    missing_commands = REQUIRED_COMMANDS - set(commands_by_name)
    require(
        not missing_commands,
        f"metadata.commands is missing: {sorted(missing_commands)}",
    )
    validator_argv = commands_by_name["bundle_compare_validator"]["argv"]
    validator_basenames = {
        argument.replace("\\", "/").rsplit("/", 1)[-1]
        for argument in validator_argv
    }
    require(
        VALIDATOR_BASENAME in validator_basenames,
        "bundle_compare_validator does not name the independent validator",
    )
    require(
        "--bundle" in validator_argv and "--compare" in validator_argv,
        "bundle_compare_validator must validate and compare both full bundles",
    )

    local = metadata["local"]
    require(isinstance(local, dict), "metadata.local must be an object")
    _require_exact_keys(
        local,
        {"execution_context", "tool_versions", "result_summaries"},
        "metadata.local",
    )
    require(
        local["execution_context"] == "local",
        "local results must be explicitly labeled local",
    )
    versions = local["tool_versions"]
    require(isinstance(versions, dict), "metadata.local.tool_versions must be an object")
    for name, version in versions.items():
        require(
            isinstance(name, str) and NAME_RE.fullmatch(name) is not None,
            f"invalid tool-version key: {name!r}",
        )
        _require_nonempty_string(version, f"metadata.local.tool_versions.{name}")
    missing_versions = REQUIRED_TOOL_VERSIONS - set(versions)
    require(
        not missing_versions,
        f"local tool versions are missing: {sorted(missing_versions)}",
    )

    summaries = local["result_summaries"]
    require(
        isinstance(summaries, dict),
        "metadata.local.result_summaries must be an object",
    )
    for name, summary in summaries.items():
        require(
            isinstance(name, str) and NAME_RE.fullmatch(name) is not None,
            f"invalid result-summary key: {name!r}",
        )
        require(isinstance(summary, dict), f"result summary {name!r} must be an object")
        _require_exact_keys(
            summary,
            {"status", "exit_code", "summary", "evidence_paths"},
            f"result summary {name!r}",
        )
        status_value = summary["status"]
        require(
            status_value in RESULT_STATUSES,
            f"invalid local result status for {name!r}",
        )
        exit_code = summary["exit_code"]
        require(
            exit_code is None
            or (
                isinstance(exit_code, int)
                and not isinstance(exit_code, bool)
                and exit_code >= 0
            ),
            f"invalid local exit code for {name!r}",
        )
        require(
            status_value == "pass" and exit_code == 0,
            f"required local result {name!r} is not a zero-exit PASS",
        )
        _require_nonempty_string(summary["summary"], f"result summary {name!r}.summary")
        paths = _validate_evidence_paths(
            summary["evidence_paths"],
            record_by_path,
            f"result summary {name!r}.evidence_paths",
        )
        required_paths = REQUIRED_RESULT_EVIDENCE.get(name, frozenset())
        require(
            required_paths <= set(paths),
            f"result summary {name!r} lacks required evidence paths: "
            f"{sorted(required_paths - set(paths))}",
        )
    missing_summaries = REQUIRED_COMMANDS - set(summaries)
    require(
        not missing_summaries,
        f"local result summaries are missing: {sorted(missing_summaries)}",
    )
    require(
        set(summaries) == set(commands_by_name),
        "local command and result-summary names differ",
    )
    validator_result = summaries["bundle_compare_validator"]
    require(
        validator_result["status"] == "pass"
        and validator_result["exit_code"] == 0,
        "captured independent validator result is not a zero-exit PASS",
    )
    _require_log_marker(
        root, "logs/full-bundle-validator.log", VALIDATOR_SUCCESS_MARKER
    )

    independent_ci = metadata["independent_ci"]
    require(
        isinstance(independent_ci, dict),
        "metadata.independent_ci must be an object",
    )
    _require_exact_keys(
        independent_ci,
        {"execution_context", "metadata_path"},
        "metadata.independent_ci",
    )
    require(
        independent_ci["execution_context"] == "independent_ci",
        "independent CI pointer is not labeled independent_ci",
    )
    require(
        independent_ci["metadata_path"] == "ci/metadata.json",
        "independent CI metadata path mismatch",
    )
    _validate_ci_metadata(root, record_by_path, source_sha)
    return metadata


def _require_artifacts(
    records: Sequence[Mapping[str, Any]], required: set[str], context: str
) -> None:
    record_by_path = _record_map(records)
    missing = sorted(required - set(record_by_path))
    require(not missing, f"{context} artifacts are missing: {missing}")
    empty = sorted(
        path for path in required if int(record_by_path[path]["size"]) == 0
    )
    require(not empty, f"{context} artifacts are empty: {empty}")


def validate_provenance_tree(
    root: Path,
    records: Sequence[Mapping[str, Any]],
    bundle_identity: Mapping[str, str],
) -> None:
    for record in records:
        relative = str(record["path"])
        top = relative.split("/", 1)[0]
        require(
            _portable_key(top) != _portable_key("bundles"),
            "provenance tree cannot contain the reserved bundles directory",
        )
        require(
            _portable_key(relative) != _portable_key(OUTER_MANIFEST),
            "provenance tree cannot contain the reserved outer manifest",
        )
    required = {"metadata.json", "ci/metadata.json", *REQUIRED_LOGS}
    _require_artifacts(records, required, "required provenance")
    validate_metadata(root, records, bundle_identity)


def _records_below(
    records: Sequence[Mapping[str, Any]], prefix: str
) -> list[dict[str, Any]]:
    full_prefix = prefix + "/"
    return [
        {
            "path": str(record["path"])[len(full_prefix) :],
            "sha256": str(record["sha256"]),
            "size": int(record["size"]),
        }
        for record in records
        if str(record["path"]).startswith(full_prefix)
    ]


def validate_seal_artifacts(
    root: Path, records: Sequence[Mapping[str, Any]]
) -> None:
    required = {"metadata.json", "ci/metadata.json", *REQUIRED_LOGS}
    for bundle in FULL_BUNDLES:
        required.update(f"{bundle}/{name}" for name in (*INNER_FILES, "manifest.json"))
    _require_artifacts(records, required, "required sealed evidence")

    identities: list[dict[str, str]] = []
    bundle_digests: list[dict[str, tuple[int, str]]] = []
    for bundle in FULL_BUNDLES:
        local_records = _records_below(records, bundle)
        identities.append(
            validate_inner_bundle(root / bundle, local_records, bundle)
        )
        bundle_digests.append(_digest_map(local_records))
    require(
        identities[0] == identities[1],
        "full-a and full-b source identities differ",
    )
    require(
        bundle_digests[0] == bundle_digests[1],
        "full-a and full-b are not byte-identical",
    )
    validate_metadata(root, records, identities[0])


def _validate_manifest_records(value: Any) -> list[dict[str, Any]]:
    require(isinstance(value, list), "outer manifest files must be a list")
    records: list[dict[str, Any]] = []
    paths: list[str] = []
    for index, record in enumerate(value):
        require(
            isinstance(record, dict),
            f"outer manifest files[{index}] must be an object",
        )
        _require_exact_keys(
            record,
            {"path", "size", "sha256"},
            f"outer manifest files[{index}]",
        )
        path = record["path"]
        require(
            isinstance(path, str),
            f"outer manifest files[{index}].path must be a string",
        )
        require(
            _portable_key(path) != _portable_key(OUTER_MANIFEST),
            "outer manifest cannot hash itself",
        )
        size = record["size"]
        require(
            isinstance(size, int)
            and not isinstance(size, bool)
            and size >= 0,
            f"invalid size for {path!r}",
        )
        digest = record["sha256"]
        require(
            isinstance(digest, str)
            and SHA256_RE.fullmatch(digest) is not None,
            f"invalid digest for {path!r}",
        )
        paths.append(path)
        records.append({"path": path, "sha256": digest, "size": size})
    ensure_unique_portable_paths(paths, "outer manifest")
    require(
        paths == sorted(paths),
        "outer manifest file records are not sorted by path",
    )
    return records


def manifest_payload(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "algorithm": "SHA-256",
        "files": list(records),
        "metadata_path": "metadata.json",
        "schema": OUTER_SCHEMA,
    }


def build_manifest(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    payload = manifest_payload(records)
    return {
        **payload,
        "pre_hash_sha256": sha256_bytes(_canonical_json(payload)),
    }


def write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    encoded = (
        json.dumps(
            manifest,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, path)
    except OSError as error:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        fail(f"cannot write outer manifest: {error}")


def verify_seal(root: Path) -> dict[str, Any]:
    manifest_path = root / OUTER_MANIFEST
    require(manifest_path.exists(), f"outer manifest is missing: {manifest_path}")
    require(
        not manifest_path.is_symlink() and not _is_junction(manifest_path),
        "outer manifest is a link/junction",
    )
    manifest = read_json(manifest_path)
    require(isinstance(manifest, dict), "outer manifest must contain an object")
    _require_exact_keys(
        manifest,
        {
            "algorithm",
            "files",
            "metadata_path",
            "pre_hash_sha256",
            "schema",
        },
        "outer manifest",
    )
    require(manifest["algorithm"] == "SHA-256", "outer manifest algorithm mismatch")
    require(manifest["schema"] == OUTER_SCHEMA, "outer manifest schema mismatch")
    require(
        manifest["metadata_path"] == "metadata.json",
        "outer manifest metadata path mismatch",
    )
    records = _validate_manifest_records(manifest["files"])
    pre_hash = manifest["pre_hash_sha256"]
    require(
        isinstance(pre_hash, str) and SHA256_RE.fullmatch(pre_hash) is not None,
        "outer manifest pre-hash is invalid",
    )
    require(
        pre_hash == sha256_bytes(_canonical_json(manifest_payload(records))),
        "outer manifest pre-hash mismatch",
    )

    actual_records = scan_regular_files(
        root, exclude_root_outer_manifest=True
    )
    require(
        actual_records == records,
        "outer manifest differs from the complete regular-file scan "
        "(missing, extra, size, or digest mismatch)",
    )
    validate_seal_artifacts(root, actual_records)
    return manifest


def _copy_regular_file(
    source: Path,
    destination: Path,
    expected_size: int,
    expected_digest: str,
) -> None:
    digest = hashlib.sha256()
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as input_stream:
            before = os.fstat(input_stream.fileno())
            require(stat.S_ISREG(before.st_mode), f"copy source is not regular: {source}")
            with destination.open("xb") as output_stream:
                while chunk := input_stream.read(1024 * 1024):
                    digest.update(chunk)
                    output_stream.write(chunk)
            after = os.fstat(input_stream.fileno())
    except OSError as error:
        fail(f"cannot copy {source} to {destination}: {error}")
    require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        f"copy source changed while being read: {source}",
    )
    require(
        before.st_size == expected_size and digest.hexdigest() == expected_digest,
        f"copy source changed after validation: {source}",
    )


def _copy_records(
    source_root: Path,
    destination_root: Path,
    records: Sequence[Mapping[str, Any]],
) -> None:
    for record in records:
        relative = str(record["path"])
        _copy_regular_file(
            source_root.joinpath(*relative.split("/")),
            destination_root.joinpath(*relative.split("/")),
            int(record["size"]),
            str(record["sha256"]),
        )


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _paths_overlap(left: Path, right: Path) -> bool:
    try:
        common = Path(os.path.commonpath((str(left), str(right))))
    except ValueError:
        return False
    return common == left or common == right


def _resolve_source(path: Path, context: str) -> Path:
    require(
        not path.is_symlink() and not _is_junction(path),
        f"{context} is a link/junction: {path}",
    )
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        fail(f"cannot resolve {context}: {error}")
    require(
        resolved.is_dir()
        and not resolved.is_symlink()
        and not _is_junction(resolved),
        f"{context} is not a regular directory: {resolved}",
    )
    return resolved


def create_seal(
    bundle_a: Path,
    bundle_b: Path,
    provenance: Path,
    seal_dir: Path,
) -> dict[str, Any]:
    source_a = _resolve_source(bundle_a, "bundle A")
    source_b = _resolve_source(bundle_b, "bundle B")
    source_provenance = _resolve_source(provenance, "provenance directory")
    sources = (source_a, source_b, source_provenance)
    for index, left in enumerate(sources):
        for right in sources[index + 1 :]:
            require(
                not _paths_overlap(left, right),
                f"create inputs overlap: {left} and {right}",
            )

    try:
        parent = seal_dir.parent.resolve(strict=True)
    except OSError as error:
        fail(f"cannot resolve seal parent directory: {error}")
    _validate_component(seal_dir.name, str(seal_dir))
    target = parent / seal_dir.name
    require(not _lexists(target), f"new seal directory already exists: {target}")
    for source in sources:
        require(
            not _paths_overlap(source, target),
            f"seal destination overlaps create input: {source}",
        )

    records_a = scan_regular_files(source_a)
    records_b = scan_regular_files(source_b)
    identity_a = validate_inner_bundle(source_a, records_a, "source bundle A")
    identity_b = validate_inner_bundle(source_b, records_b, "source bundle B")
    require(identity_a == identity_b, "source bundle identities differ")
    require(
        _digest_map(records_a) == _digest_map(records_b),
        "source bundles are not byte-identical",
    )
    provenance_records = scan_regular_files(source_provenance)
    validate_provenance_tree(
        source_provenance, provenance_records, identity_a
    )

    try:
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{target.name}.staging-",
                dir=parent,
            )
        )
    except OSError as error:
        fail(f"cannot create seal staging directory: {error}")

    active_staging: Path | None = staging
    try:
        _copy_records(source_a, staging / FULL_BUNDLES[0], records_a)
        _copy_records(source_b, staging / FULL_BUNDLES[1], records_b)
        _copy_records(source_provenance, staging, provenance_records)

        require(
            scan_regular_files(source_a) == records_a,
            "bundle A changed during create",
        )
        require(
            scan_regular_files(source_b) == records_b,
            "bundle B changed during create",
        )
        require(
            scan_regular_files(source_provenance) == provenance_records,
            "provenance tree changed during create",
        )

        records = scan_regular_files(staging)
        validate_seal_artifacts(staging, records)
        write_manifest(staging / OUTER_MANIFEST, build_manifest(records))
        verify_seal(staging)
        try:
            os.rename(staging, target)
        except OSError as error:
            fail(f"cannot publish new seal directory: {error}")
        active_staging = None
        return verify_seal(target)
    finally:
        if active_staging is not None and _lexists(active_staging):
            try:
                shutil.rmtree(active_staging)
            except OSError:
                pass


def parse_arguments(
    arguments: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "create example: python tools/"
            "seal_projection_exactness_nullspace_evidence.py create "
            "--bundle-a evidence/run-a --bundle-b evidence/run-b "
            "--provenance-dir evidence/provenance "
            "--seal-dir evidence/sealed-final; "
            "verify example: python tools/"
            "seal_projection_exactness_nullspace_evidence.py verify "
            "--seal-dir evidence/sealed-final"
        ),
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)
    create = subparsers.add_parser(
        "create", help="copy validated inputs into a new sealed directory"
    )
    create.add_argument("--bundle-a", type=Path, required=True)
    create.add_argument("--bundle-b", type=Path, required=True)
    create.add_argument("--provenance-dir", type=Path, required=True)
    create.add_argument("--seal-dir", type=Path, required=True)
    verify = subparsers.add_parser("verify", help="verify an existing seal")
    verify.add_argument("--seal-dir", type=Path, required=True)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    options = parse_arguments(arguments)
    try:
        if options.mode == "create":
            manifest = create_seal(
                options.bundle_a,
                options.bundle_b,
                options.provenance_dir,
                options.seal_dir.absolute(),
            )
        else:
            manifest = verify_seal(options.seal_dir.absolute())
    except SealError as error:
        print(
            "PROJECTION EXACTNESS NULLSPACE OUTER SEAL INVALID: "
            f"{error}",
            file=sys.stderr,
        )
        return 1
    print(
        "PROJECTION EXACTNESS NULLSPACE OUTER SEAL VALID "
        f"mode={options.mode} files={len(manifest['files'])} "
        f"pre_hash_sha256={manifest['pre_hash_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
