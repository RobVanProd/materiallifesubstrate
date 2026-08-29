#!/usr/bin/env python3
"""Create or verify the outer Projection Foundation Lab evidence seal.

The inner numerical bundles have their own producer manifests.  This tool is
the deliberately small, standard-library-only outer boundary: it validates
the projection-specific provenance record, validates both inner manifests,
requires two byte-identical full runs, and hashes every regular file below the
seal root except ``outer-manifest.json`` itself.

The seal is an integrity record, not a signature.  Possession of the source
tree is sufficient to create a new seal, so provenance still depends on the
public Git commit/tag and the independently hosted CI run named by metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, NoReturn, Sequence


OUTER_MANIFEST = "outer-manifest.json"
OUTER_SCHEMA = "mls.projection-foundation.outer-evidence-seal.v1"
METADATA_SCHEMA = "mls.projection-foundation.outer-evidence-metadata.v1"
CI_SCHEMA = "mls.projection-foundation.ci-metadata.v1"
INNER_SCHEMA = "mls.projection-foundation.manifest.v1"
BRANCH = "projection-foundation-lab"
PUBLIC_REPOSITORY = "https://github.com/RobVanProd/materiallifesubstrate"

FULL_BUNDLES = ("bundles/full-a", "bundles/full-b")
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

REQUIRED_LOGS = (
    "logs/full-bundle-a.log",
    "logs/full-bundle-b.log",
    "logs/full-bundle-compare.log",
    "logs/full-bundle-validator.log",
    "logs/configure.log",
    "logs/build.log",
    "logs/ctest.log",
    "logs/exact-oracle.log",
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
        "lean_build",
        "lean_axiom_report",
        "source_scan",
        "git_provenance",
    }
)
REQUIRED_TOOL_VERSIONS = frozenset(
    {"python", "cmake", "ctest", "cxx", "git", "lean", "lake"}
)
REQUIRED_RESULT_SUMMARIES = REQUIRED_COMMANDS
RESULT_STATUSES = frozenset({"pass", "fail", "not_run", "inconclusive"})

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
NAME_RE = re.compile(r"[a-z][a-z0-9_]*\Z")
STATUS_RE = re.compile(r"[a-z][a-z0-9_-]*\Z")
TAG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}\Z")


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
        return json.loads(text, object_pairs_hook=_strict_object)
    except (json.JSONDecodeError, SealError) as error:
        fail(f"invalid JSON in {path}: {error}")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _portable_key(relative: str) -> str:
    return unicodedata.normalize("NFC", relative).casefold()


def _validate_component(name: str, context: str) -> None:
    require(name not in {"", ".", ".."}, f"unsafe empty/dot path component: {context}")
    require("\\" not in name, f"backslash is not portable in path: {context}")
    require(
        all(ord(character) >= 0x20 and character != "\x7f" for character in name),
        f"control character in path: {context}",
    )


def ensure_unique_portable_paths(paths: Iterable[str], context: str) -> None:
    """Reject exact, Unicode-normalized, or case-folded path collisions."""

    seen: dict[str, str] = {}
    for relative in paths:
        require(isinstance(relative, str) and relative != "", f"invalid path in {context}")
        require(not relative.startswith("/"), f"absolute path in {context}: {relative!r}")
        components = relative.split("/")
        for component in components:
            _validate_component(component, relative)
        require(".." not in components, f"parent traversal in {context}: {relative!r}")
        key = _portable_key(relative)
        previous = seen.get(key)
        require(
            previous is None,
            f"duplicate/case-colliding path in {context}: {previous!r} and {relative!r}",
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


def scan_regular_files(root: Path) -> list[dict[str, Any]]:
    """Return every regular file below *root*, except the root outer manifest."""

    require(root.exists(), f"seal directory does not exist: {root}")
    require(not root.is_symlink() and not _is_junction(root), "seal root is a link/junction")
    require(root.is_dir(), f"seal root is not a directory: {root}")

    discovered: list[tuple[str, Path]] = []

    def visit(directory: Path, prefix: tuple[str, ...]) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as error:
            fail(f"cannot scan {directory}: {error}")

        sibling_names: dict[str, str] = {}
        for entry in entries:
            _validate_component(entry.name, "/".join((*prefix, entry.name)))
            sibling_key = _portable_key(entry.name)
            previous = sibling_names.get(sibling_key)
            require(
                previous is None,
                f"case-colliding sibling entries: {previous!r} and {entry.name!r} in {directory}",
            )
            sibling_names[sibling_key] = entry.name

            path = Path(entry.path)
            relative_parts = (*prefix, entry.name)
            relative = "/".join(relative_parts)
            require(
                not entry.is_symlink() and not _is_junction(path),
                f"links/junctions are forbidden in a seal: {relative}",
            )
            if entry.is_dir(follow_symlinks=False):
                visit(path, relative_parts)
            elif entry.is_file(follow_symlinks=False):
                if not prefix and _portable_key(entry.name) == _portable_key(OUTER_MANIFEST):
                    require(
                        entry.name == OUTER_MANIFEST,
                        f"outer manifest has a case-colliding spelling: {entry.name!r}",
                    )
                    continue
                discovered.append((relative, path))
            else:
                fail(f"special filesystem entry is forbidden in a seal: {relative}")

    visit(root, ())
    ensure_unique_portable_paths((relative for relative, _ in discovered), "seal tree")

    records: list[dict[str, Any]] = []
    for relative, path in sorted(discovered, key=lambda pair: pair[0]):
        size, digest = _hash_regular_file(path)
        records.append({"path": relative, "sha256": digest, "size": size})
    return records


def _record_map(records: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {str(record["path"]): record for record in records}


def _require_exact_keys(value: Mapping[str, Any], keys: set[str], context: str) -> None:
    actual = set(value)
    require(actual == keys, f"{context} keys differ: expected {sorted(keys)}, got {sorted(actual)}")


def _require_nonempty_string(value: Any, context: str) -> str:
    require(isinstance(value, str) and value.strip() == value and value != "", f"{context} must be a nonempty trimmed string")
    require("\x00" not in value, f"{context} contains NUL")
    return value


def _validate_jobs(value: Any, run_url: str, context: str) -> list[dict[str, str]]:
    require(isinstance(value, list) and value, f"{context} must be a nonempty list")
    jobs: list[dict[str, str]] = []
    names: list[str] = []
    for index, item in enumerate(value):
        require(isinstance(item, dict), f"{context}[{index}] must be an object")
        _require_exact_keys(item, {"name", "status", "url"}, f"{context}[{index}]")
        name = _require_nonempty_string(item["name"], f"{context}[{index}].name")
        status_value = _require_nonempty_string(item["status"], f"{context}[{index}].status")
        require(STATUS_RE.fullmatch(status_value) is not None, f"invalid CI status: {status_value!r}")
        url = _require_nonempty_string(item["url"], f"{context}[{index}].url")
        require(url.startswith(run_url + "/job/"), f"CI job URL is outside the declared run: {url}")
        names.append(name)
        jobs.append({"name": name, "status": status_value, "url": url})
    ensure_unique_portable_paths(names, context)
    return jobs


def _validate_ci_block(value: Any, context: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{context} must be an object")
    _require_exact_keys(value, {"jobs", "run_url", "status"}, context)
    run_url = _require_nonempty_string(value["run_url"], f"{context}.run_url")
    run_prefix = PUBLIC_REPOSITORY + "/actions/runs/"
    require(run_url.startswith(run_prefix), f"{context}.run_url is not in the public repository")
    require(run_url[len(run_prefix):].isdigit(), f"{context}.run_url must end in a numeric run id")
    status_value = _require_nonempty_string(value["status"], f"{context}.status")
    require(STATUS_RE.fullmatch(status_value) is not None, f"invalid CI run status: {status_value!r}")
    jobs = _validate_jobs(value["jobs"], run_url, f"{context}.jobs")
    return {"jobs": jobs, "run_url": run_url, "status": status_value}


def validate_metadata(root: Path) -> dict[str, Any]:
    metadata = read_json(root / "metadata.json")
    require(isinstance(metadata, dict), "metadata.json must contain an object")
    _require_exact_keys(metadata, {"schema", "source", "commands", "local", "ci"}, "metadata")
    require(metadata["schema"] == METADATA_SCHEMA, "metadata schema mismatch")

    source = metadata["source"]
    require(isinstance(source, dict), "metadata.source must be an object")
    _require_exact_keys(source, {"sha", "branch", "tag", "repository_url"}, "metadata.source")
    require(isinstance(source["sha"], str) and SOURCE_SHA_RE.fullmatch(source["sha"]) is not None, "source SHA must be exactly 40 lowercase hexadecimal characters")
    require(source["branch"] == BRANCH, f"source branch must be {BRANCH!r}")
    tag = _require_nonempty_string(source["tag"], "metadata.source.tag")
    require(TAG_RE.fullmatch(tag) is not None and ".." not in tag and "@{" not in tag, "invalid Git tag spelling")
    require(source["repository_url"] == PUBLIC_REPOSITORY, "public repository URL mismatch")

    commands = metadata["commands"]
    require(isinstance(commands, list) and commands, "metadata.commands must be a nonempty list")
    command_names: list[str] = []
    for index, command in enumerate(commands):
        require(isinstance(command, dict), f"metadata.commands[{index}] must be an object")
        _require_exact_keys(command, {"name", "cwd", "argv"}, f"metadata.commands[{index}]")
        name = _require_nonempty_string(command["name"], f"metadata.commands[{index}].name")
        require(NAME_RE.fullmatch(name) is not None, f"invalid command name: {name!r}")
        _require_nonempty_string(command["cwd"], f"metadata.commands[{index}].cwd")
        argv = command["argv"]
        require(isinstance(argv, list) and argv, f"metadata.commands[{index}].argv must be nonempty")
        for argument_index, argument in enumerate(argv):
            _require_nonempty_string(argument, f"metadata.commands[{index}].argv[{argument_index}]")
        command_names.append(name)
    ensure_unique_portable_paths(command_names, "metadata.commands names")
    missing_commands = REQUIRED_COMMANDS - set(command_names)
    require(not missing_commands, f"metadata.commands is missing: {sorted(missing_commands)}")

    local = metadata["local"]
    require(isinstance(local, dict), "metadata.local must be an object")
    _require_exact_keys(local, {"tool_versions", "result_summaries"}, "metadata.local")
    versions = local["tool_versions"]
    require(isinstance(versions, dict), "metadata.local.tool_versions must be an object")
    for name, version in versions.items():
        require(isinstance(name, str) and NAME_RE.fullmatch(name) is not None, f"invalid tool-version key: {name!r}")
        _require_nonempty_string(version, f"metadata.local.tool_versions.{name}")
    missing_versions = REQUIRED_TOOL_VERSIONS - set(versions)
    require(not missing_versions, f"tool versions are missing: {sorted(missing_versions)}")

    summaries = local["result_summaries"]
    require(isinstance(summaries, dict), "metadata.local.result_summaries must be an object")
    for name, summary in summaries.items():
        require(isinstance(name, str) and NAME_RE.fullmatch(name) is not None, f"invalid result-summary key: {name!r}")
        require(isinstance(summary, dict), f"result summary {name!r} must be an object")
        _require_exact_keys(summary, {"status", "summary"}, f"result summary {name!r}")
        require(summary["status"] in RESULT_STATUSES, f"invalid local result status for {name!r}")
        _require_nonempty_string(summary["summary"], f"result summary {name!r}.summary")
    missing_summaries = REQUIRED_RESULT_SUMMARIES - set(summaries)
    require(not missing_summaries, f"result summaries are missing: {sorted(missing_summaries)}")

    ci = _validate_ci_block(metadata["ci"], "metadata.ci")
    ci_metadata = read_json(root / "ci/metadata.json")
    require(isinstance(ci_metadata, dict), "ci/metadata.json must contain an object")
    _require_exact_keys(ci_metadata, {"schema", "source_sha", "branch", "run_url", "status", "jobs"}, "ci metadata")
    require(ci_metadata["schema"] == CI_SCHEMA, "CI metadata schema mismatch")
    require(ci_metadata["source_sha"] == source["sha"], "CI source SHA differs from metadata source SHA")
    require(ci_metadata["branch"] == BRANCH, "CI branch mismatch")
    ci_file_block = _validate_ci_block(
        {"run_url": ci_metadata["run_url"], "status": ci_metadata["status"], "jobs": ci_metadata["jobs"]},
        "ci metadata",
    )
    require(ci_file_block == ci, "CI metadata file differs from metadata.json CI block")
    return metadata


def _inner_manifest_payload(hashes: Mapping[str, str]) -> bytes:
    names = sorted(hashes)
    lines = ["{", '  "algorithm": "SHA-256",', '  "files": {']
    for index, name in enumerate(names):
        comma = "," if index + 1 != len(names) else ""
        lines.append(f"    {json.dumps(name)}: {json.dumps(hashes[name])}{comma}")
    lines.extend(("  },", f'  "schema": {json.dumps(INNER_SCHEMA)}', "}"))
    return "\n".join(lines).encode("utf-8")


def validate_inner_bundles(root: Path, records: Sequence[Mapping[str, Any]]) -> None:
    record_by_path = _record_map(records)
    bundle_digests: list[dict[str, tuple[int, str]]] = []
    expected_inner_names = set(INNER_FILES) | {"manifest.json"}

    for bundle_relative in FULL_BUNDLES:
        prefix = bundle_relative + "/"
        actual_names = {
            path[len(prefix):]
            for path in record_by_path
            if path.startswith(prefix)
        }
        require(actual_names == expected_inner_names, f"{bundle_relative} file set differs from the registered full bundle")
        require(all("/" not in name for name in actual_names), f"{bundle_relative} contains nested files")

        manifest = read_json(root / bundle_relative / "manifest.json")
        require(isinstance(manifest, dict), f"{bundle_relative}/manifest.json must be an object")
        _require_exact_keys(manifest, {"algorithm", "files", "pre_hash_sha256", "schema"}, f"{bundle_relative} manifest")
        require(manifest["algorithm"] == "SHA-256" and manifest["schema"] == INNER_SCHEMA, f"{bundle_relative} manifest identity mismatch")
        hashes = manifest["files"]
        require(isinstance(hashes, dict) and set(hashes) == set(INNER_FILES), f"{bundle_relative} inner manifest file set mismatch")
        calculated: dict[str, str] = {}
        for name in INNER_FILES:
            digest = str(record_by_path[prefix + name]["sha256"])
            require(isinstance(hashes[name], str) and SHA256_RE.fullmatch(hashes[name]) is not None, f"{bundle_relative} invalid digest for {name}")
            require(hashes[name] == digest, f"{bundle_relative} inner digest mismatch for {name}")
            calculated[name] = digest
        pre_hash = sha256_bytes(_inner_manifest_payload(calculated))
        require(manifest["pre_hash_sha256"] == pre_hash, f"{bundle_relative} inner manifest pre-hash mismatch")
        bundle_digests.append(
            {
                name: (
                    int(record_by_path[prefix + name]["size"]),
                    str(record_by_path[prefix + name]["sha256"]),
                )
                for name in expected_inner_names
            }
        )

    require(bundle_digests[0] == bundle_digests[1], "full-a and full-b are not byte-identical")


def validate_required_artifacts(root: Path, records: Sequence[Mapping[str, Any]]) -> None:
    record_by_path = _record_map(records)
    required = {"metadata.json", "ci/metadata.json", *REQUIRED_LOGS}
    for bundle in FULL_BUNDLES:
        required.update(f"{bundle}/{name}" for name in (*INNER_FILES, "manifest.json"))
    missing = sorted(required - set(record_by_path))
    require(not missing, f"required evidence artifacts are missing: {missing}")
    empty = sorted(path for path in required if int(record_by_path[path]["size"]) == 0)
    require(not empty, f"required evidence artifacts are empty: {empty}")
    validate_inner_bundles(root, records)
    validate_metadata(root)


def _validate_manifest_records(value: Any) -> list[dict[str, Any]]:
    require(isinstance(value, list), "outer manifest files must be a list")
    records: list[dict[str, Any]] = []
    paths: list[str] = []
    for index, record in enumerate(value):
        require(isinstance(record, dict), f"outer manifest files[{index}] must be an object")
        _require_exact_keys(record, {"path", "size", "sha256"}, f"outer manifest files[{index}]")
        path = record["path"]
        require(isinstance(path, str), f"outer manifest files[{index}].path must be a string")
        require(_portable_key(path) != _portable_key(OUTER_MANIFEST), "outer manifest cannot hash itself")
        size = record["size"]
        require(isinstance(size, int) and not isinstance(size, bool) and size >= 0, f"invalid size for {path!r}")
        digest = record["sha256"]
        require(isinstance(digest, str) and SHA256_RE.fullmatch(digest) is not None, f"invalid digest for {path!r}")
        paths.append(path)
        records.append({"path": path, "sha256": digest, "size": size})
    ensure_unique_portable_paths(paths, "outer manifest")
    require(paths == sorted(paths), "outer manifest file records are not sorted by path")
    return records


def manifest_payload(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "algorithm": "SHA-256",
        "files": list(records),
        "metadata_path": "metadata.json",
        "schema": OUTER_SCHEMA,
    }


def build_manifest(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    payload = manifest_payload(records)
    return {**payload, "pre_hash_sha256": sha256_bytes(_canonical_json(payload))}


def write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    encoded = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
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


def create_seal(root: Path) -> dict[str, Any]:
    records = scan_regular_files(root)
    validate_required_artifacts(root, records)
    manifest = build_manifest(records)
    write_manifest(root / OUTER_MANIFEST, manifest)
    # Re-read through the verification path so create cannot emit a seal that
    # verify rejects due to serialization or a concurrent file mutation.
    return verify_seal(root)


def verify_seal(root: Path) -> dict[str, Any]:
    manifest_path = root / OUTER_MANIFEST
    require(manifest_path.exists(), f"outer manifest is missing: {manifest_path}")
    require(not manifest_path.is_symlink() and not _is_junction(manifest_path), "outer manifest is a link/junction")
    manifest = read_json(manifest_path)
    require(isinstance(manifest, dict), "outer manifest must contain an object")
    _require_exact_keys(manifest, {"algorithm", "files", "metadata_path", "pre_hash_sha256", "schema"}, "outer manifest")
    require(manifest["algorithm"] == "SHA-256", "outer manifest algorithm mismatch")
    require(manifest["schema"] == OUTER_SCHEMA, "outer manifest schema mismatch")
    require(manifest["metadata_path"] == "metadata.json", "outer manifest metadata path mismatch")
    records = _validate_manifest_records(manifest["files"])
    pre_hash = manifest["pre_hash_sha256"]
    require(isinstance(pre_hash, str) and SHA256_RE.fullmatch(pre_hash) is not None, "outer manifest pre-hash is invalid")
    require(pre_hash == sha256_bytes(_canonical_json(manifest_payload(records))), "outer manifest pre-hash mismatch")

    actual_records = scan_regular_files(root)
    require(actual_records == records, "outer manifest differs from the complete regular-file scan (missing, extra, size, or digest mismatch)")
    validate_required_artifacts(root, actual_records)
    return manifest


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("create", "verify"))
    parser.add_argument("--seal-dir", type=Path, required=True)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    options = parse_arguments(arguments)
    root = options.seal_dir.absolute()
    try:
        manifest = create_seal(root) if options.mode == "create" else verify_seal(root)
    except SealError as error:
        print(f"PROJECTION FOUNDATION OUTER SEAL INVALID: {error}", file=sys.stderr)
        return 1
    print(
        "PROJECTION FOUNDATION OUTER SEAL VALID "
        f"mode={options.mode} files={len(manifest['files'])} "
        f"pre_hash_sha256={manifest['pre_hash_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
