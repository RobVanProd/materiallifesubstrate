#!/usr/bin/env python3
"""Create or verify the Mechanical Observability outer evidence seal.

Create copies two already-validated full bundles and a provenance tree into a
new seal directory.  It never writes to any input.  Byte-identical runs take
the deterministic route; differing runs can only be preserved as explicit
STOP/no-promotion negative evidence with a complete mismatch inventory.
Verify checks the complete regular-file inventory, both producer manifests,
runs the hash-pinned local semantic validator over both bundles, and binds
captured local/GitHub/Git metadata without authenticating those captures.

The seal is a canonical SHA-256 integrity record, not a signature.  Its only
execution claim is the validator run performed by this verifier.  Captured CI,
Git, tool, command, and log metadata remain explicitly unauthenticated until a
separate live service check is reported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, NoReturn, Sequence


OUTER_MANIFEST = "outer-manifest.json"
OUTER_SCHEMA = "mls.mechanical-observability.outer-evidence-seal.v3"
METADATA_SCHEMA = (
    "mls.mechanical-observability.outer-evidence-metadata.v3"
)
CI_SCHEMA = (
    "mls.mechanical-observability.captured-external-ci-metadata.v1"
)
INNER_SCHEMA = "mls.mechanical-observability.manifest.v1"
SUMMARY_SCHEMA = "mls.mechanical-observability.summary.v1"
BRANCH = "mechanical-observability-lab"
ACCEPTED_PARENT_SHA = "2e175396ff30faea8a4d96d5a0336ab9ba042f12"
PUBLIC_REPOSITORY = "https://github.com/RobVanProd/materiallifesubstrate"
SEED = 260828
MAX_SEAL_BYTES = 8 * 1024 * 1024 * 1024
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_LOG_BYTES = 256 * 1024 * 1024
MAX_DEFAULT_EVIDENCE_FILE_BYTES = 1024 * 1024 * 1024
MAX_NULLSPACE_FILE_BYTES = 1536 * 1024 * 1024
MAX_REGULAR_FILES = 128
MAX_DIRECTORIES = 24
MAX_PATH_DEPTH = 4
MAX_PATH_UTF8_BYTES = 512
MAX_COMPONENT_UTF8_BYTES = 192
MAX_VALIDATOR_BYTES = 4 * 1024 * 1024
MAX_VALIDATOR_OUTPUT_BYTES = 4 * 1024 * 1024

FULL_BUNDLES = ("bundles/full-a", "bundles/full-b")
INNER_FILES = (
    "configurations.csv",
    "packets.csv",
    "neighbor_pairs.csv",
    "relations.csv",
    "operator_status.csv",
    "operator_entries.csv",
    "moment_diagnostics.csv",
    "affine_objectivity.csv",
    "invariance.csv",
    "rigid_basis.csv",
    "rank_status.csv",
    "nullspace_modes.csv",
    "nullspace_metrics.csv",
    "grid_gauge.csv",
    "exact_reference.csv",
    "grid_nodes.csv",
    "checkpoints.csv",
    "permutation_controls.csv",
    "permutation_entries.csv",
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
            "results/mechanical-observability-findings.json",
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
VALIDATOR_BASENAME = "validate_mechanical_observability_bundle.py"
VALIDATOR_SUCCESS_MARKER = (
    "MECHANICAL OBSERVABILITY BUNDLE VALID:"
)
VALIDATOR_FINDINGS_SCHEMA = (
    "mls.mechanical-observability.validator-findings.v1"
)
VALIDATOR_FINDINGS_PATH = (
    "results/mechanical-observability-findings.json"
)
VALIDATOR_LOG_PATH = "logs/full-bundle-validator.log"
VALIDATOR_FINDINGS_KEYS = frozenset(
    {
        "schema",
        "validator_sha256",
        "source_sha",
        "mode",
        "first_manifest_pre_hash",
        "second_manifest_pre_hash",
        "comparison_status",
        "mismatches",
        "bundle_structural_valid",
        "producer_claims_sha256",
        "derived_gates",
        "claim_mismatches",
        "candidate_findings",
        "decision",
        "promotion",
        "result_sha256_before_hash_field",
    }
)
DERIVED_GATE_KEYS = frozenset(
    {
        "affine_objectivity_all_pass",
        "checkpoint_round_trip_all_pass",
        "decisive_rank_rows_all_unambiguous",
        "deterministic_repeatability",
        "diagnostics_read_only_all_exact",
        "finite_objectivity_all_pass",
        "independent_reference_all_pass",
        "invariance_all_pass",
        "negative_control_reproduced",
        "neighbor_lookup_all_agree",
        "producer_claims_consistent",
        "raw_decision_rows_all_exported",
    }
)
PRODUCER_CLAIM_KEYS = frozenset(
    {
        "checkpoint_round_trip_all_pass",
        "diagnostics_read_only_all_exact",
        "neighbor_lookup_all_agree",
        "negative_control_reproduced",
        "affine_objectivity_all_pass",
        "finite_objectivity_all_pass",
        "invariance_all_pass",
        "decisive_rank_rows_all_unambiguous",
        "raw_decision_rows_all_exported",
        "independent_reference_all_pass",
        "nondeterminism_detected",
        "candidate_findings",
        "decision",
    }
)
VALID_COMPARISON_STATUSES = frozenset(
    {"single", "byte_identical", "nondeterministic"}
)
STOP_DECISION = "stop_inconclusive_or_implementation_failure"
PINNED_VALIDATOR_SHA256 = "40dcbb6a5ee3bf96a22fcbc7f8068dcf36fdddeaae32676c70a3d15c110ca625"
OFFLINE_CLAIM_SCOPE = "integrity_and_independent_local_semantic_validation_only"
UNAUTHENTICATED_EXTERNAL = "not_authenticated_by_offline_seal"

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


def _parse_json_integer(value: str) -> int:
    require(value != "-0", "negative-zero JSON integer is not canonical")
    require(len(value) <= 20, "JSON integer exceeds frozen digit cap")
    return int(value)


def _reject_json_float(value: str) -> NoReturn:
    fail(f"floating JSON number is outside the frozen evidence schemas: {value}")


def read_json_bytes(raw: bytes, where: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        fail(f"{where} is not UTF-8: {error}")
    try:
        return json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_json_constant,
            parse_int=_parse_json_integer,
            parse_float=_reject_json_float,
        )
    except (json.JSONDecodeError, SealError, ValueError) as error:
        fail(f"invalid JSON in {where}: {error}")


def read_json(path: Path) -> Any:
    raw = _read_bounded_regular_bytes(path, MAX_JSON_BYTES)
    return read_json_bytes(raw, str(path))


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


def _canonical_json_document(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        fail(f"value cannot be represented as canonical JSON: {error}")
    return (text + "\n").encode("utf-8")


def require_canonical_json_document(
    raw: bytes, value: Any, where: str
) -> None:
    require(
        raw == _canonical_json_document(value),
        f"{where} is not in the frozen canonical JSON encoding",
    )


def read_canonical_json(path: Path) -> Any:
    raw = _read_bounded_regular_bytes(path, MAX_JSON_BYTES)
    value = read_json_bytes(raw, str(path))
    require_canonical_json_document(raw, value, str(path))
    return value


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
    try:
        encoded = name.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        fail(f"path component is not valid UTF-8: {context}: {error}")
    require(
        len(encoded) <= MAX_COMPONENT_UTF8_BYTES,
        f"path component exceeds frozen UTF-8 byte cap: {context}",
    )


def _validate_relative_path(relative: str, context: str) -> None:
    require(
        isinstance(relative, str) and relative != "",
        f"invalid path in {context}",
    )
    require(
        not relative.startswith("/"),
        f"absolute path in {context}: {relative!r}",
    )
    components = relative.split("/")
    require(
        len(components) <= MAX_PATH_DEPTH,
        f"path exceeds frozen depth cap: {relative!r}",
    )
    try:
        relative_utf8 = relative.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        fail(f"path is not valid UTF-8: {relative!r}: {error}")
    require(
        len(relative_utf8) <= MAX_PATH_UTF8_BYTES,
        f"path exceeds frozen UTF-8 byte cap: {relative!r}",
    )
    for component in components:
        _validate_component(component, relative)


def ensure_unique_portable_paths(paths: Iterable[str], context: str) -> None:
    """Reject unsafe, duplicate, normalized, or case-folded relative paths."""

    seen: dict[str, str] = {}
    for relative in paths:
        _validate_relative_path(relative, context)
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


def _identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def _open_regular_file(path: Path) -> tuple[Any, os.stat_result]:
    """Open one non-link regular file and bind the handle to its directory entry."""

    try:
        path_before = os.stat(path, follow_symlinks=False)
    except OSError as error:
        fail(f"cannot stat {path}: {error}")
    require(stat.S_ISREG(path_before.st_mode), f"not a regular file: {path}")
    require(
        not path.is_symlink() and not _is_junction(path),
        f"file is a link/junction: {path}",
    )
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        require(stat.S_ISREG(opened.st_mode), f"not a regular file: {path}")
        require(
            (path_before.st_dev, path_before.st_ino)
            == (opened.st_dev, opened.st_ino),
            f"file was replaced while opening: {path}",
        )
        stream = os.fdopen(descriptor, "rb")
        descriptor = None
        return stream, opened
    except OSError as error:
        fail(f"cannot securely open {path}: {error}")
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_bounded_regular_bytes(path: Path, max_bytes: int) -> bytes:
    require(max_bytes >= 0, "internal negative file byte cap")
    stream, before = _open_regular_file(path)
    chunks: list[bytes] = []
    observed = 0
    try:
        with stream:
            require(
                before.st_size <= max_bytes,
                f"file exceeds frozen byte cap {max_bytes}: {path}",
            )
            while chunk := stream.read(min(1024 * 1024, max_bytes + 1)):
                observed += len(chunk)
                require(
                    observed <= max_bytes,
                    f"file grew past frozen byte cap while reading: {path}",
                )
                chunks.append(chunk)
            after = os.fstat(stream.fileno())
    except OSError as error:
        fail(f"cannot read {path}: {error}")
    require(_identity(before) == _identity(after), f"file changed while reading: {path}")
    try:
        path_after = os.stat(path, follow_symlinks=False)
    except OSError as error:
        fail(f"file disappeared after reading {path}: {error}")
    require(
        _identity(after) == _identity(path_after),
        f"file was replaced while reading: {path}",
    )
    return b"".join(chunks)


def evidence_file_cap(relative: str) -> int:
    name = relative.rsplit("/", 1)[-1]
    if name == "nullspace_modes.csv":
        return MAX_NULLSPACE_FILE_BYTES
    if name.endswith(".log"):
        return MAX_LOG_BYTES
    if name.endswith(".json"):
        return MAX_JSON_BYTES
    return MAX_DEFAULT_EVIDENCE_FILE_BYTES


def _hash_regular_file(path: Path, max_bytes: int) -> tuple[int, str]:
    digest = hashlib.sha256()
    stream, before = _open_regular_file(path)
    try:
        with stream:
            require(before.st_size <= max_bytes,
                    f"file exceeds frozen byte cap {max_bytes}: {path}")
            observed = 0
            while chunk := stream.read(1024 * 1024):
                observed += len(chunk)
                require(observed <= max_bytes,
                        f"file grew past frozen byte cap while hashing: {path}")
                digest.update(chunk)
            after = os.fstat(stream.fileno())
    except OSError as error:
        fail(f"cannot hash {path}: {error}")
    require(
        _identity(before) == _identity(after),
        f"file changed while hashing: {path}",
    )
    try:
        path_after = os.stat(path, follow_symlinks=False)
    except OSError as error:
        fail(f"file disappeared after hashing {path}: {error}")
    require(
        _identity(after) == _identity(path_after),
        f"file was replaced while hashing: {path}",
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
    directory_count = 0
    entry_count = 0

    def visit(directory: Path, prefix: tuple[str, ...]) -> None:
        nonlocal directory_count, entry_count
        directory_count += 1
        require(
            directory_count <= MAX_DIRECTORIES,
            "evidence tree exceeds frozen directory-count cap",
        )
        try:
            entries: list[os.DirEntry[str]] = []
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    entry_count += 1
                    require(
                        entry_count <= MAX_REGULAR_FILES + MAX_DIRECTORIES,
                        "evidence tree exceeds frozen entry-count cap",
                    )
                    entries.append(entry)
            entries.sort(key=lambda entry: entry.name)
        except OSError as error:
            fail(f"cannot scan {directory}: {error}")
        require(
            not prefix or bool(entries),
            f"empty directories are forbidden: {'/'.join(prefix)}",
        )

        sibling_names: dict[str, str] = {}
        for entry in entries:
            relative_parts = (*prefix, entry.name)
            relative = "/".join(relative_parts)
            _validate_relative_path(relative, "evidence tree")
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
                require(
                    len(discovered) < MAX_REGULAR_FILES,
                    "evidence tree exceeds frozen regular-file-count cap",
                )
                discovered.append((relative, path))
            else:
                fail(f"special filesystem entry is forbidden in evidence: {relative}")

    visit(root, ())
    ensure_unique_portable_paths(
        (relative for relative, _ in discovered), "evidence tree"
    )

    records: list[dict[str, Any]] = []
    total_size = 0
    for relative, path in sorted(discovered, key=lambda pair: pair[0]):
        size, digest = _hash_regular_file(path, evidence_file_cap(relative))
        total_size += size
        require(total_size <= MAX_SEAL_BYTES,
                "evidence tree exceeds frozen total byte cap")
        records.append({"path": relative, "sha256": digest, "size": size})
    return records


def _record_map(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    return {str(record["path"]): record for record in records}


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
) -> dict[str, Any]:
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

    manifest = read_canonical_json(bundle / "manifest.json")
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
        and summary.get("producer") == "cpp_mechanical_observability_lab",
        f"{context} is not final C++ full evidence",
    )
    require(summary.get("dirty") is False, f"{context} was produced from a dirty source tree")
    require(
        isinstance(summary.get("nondeterminism_detected"), bool),
        f"{context} nondeterminism claim must be Boolean",
    )
    require(summary.get("promotion") is False, f"{context} claims promotion")
    return {
        "branch": BRANCH,
        "source_sha": source_sha,
        "manifest_pre_hash": expected_pre_hash,
        "nondeterminism_detected": summary["nondeterminism_detected"],
        "summary": summary,
    }


def _bundle_mismatches(
    first: Sequence[Mapping[str, Any]],
    second: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    first_map = _record_map(first)
    second_map = _record_map(second)
    require(
        set(first_map) == set(second_map),
        "full-bundle inventories differ",
    )
    return [
        {
            "path": path,
            "first_sha256": str(first_map[path]["sha256"]),
            "second_sha256": str(second_map[path]["sha256"]),
        }
        for path in sorted(first_map)
        if (
            int(first_map[path]["size"]),
            str(first_map[path]["sha256"]),
        )
        != (
            int(second_map[path]["size"]),
            str(second_map[path]["sha256"]),
        )
    ]


def _producer_claims_sha256(
    identities: Sequence[Mapping[str, Any]],
) -> str:
    return sha256_bytes(
        _canonical_json([identity["summary"] for identity in identities])
    )


def _validate_claim_mismatches(value: Any) -> list[str]:
    require(isinstance(value, list), "validator claim_mismatches must be a list")
    claims: list[str] = []
    for index, item in enumerate(value):
        require(
            isinstance(item, str),
            f"validator claim_mismatches[{index}] must be a string",
        )
        valid = item == "comparison.nondeterminism_detected"
        if not valid:
            match = re.fullmatch(r"(first|second)\.([a-z_]+)", item)
            valid = bool(match and match.group(2) in PRODUCER_CLAIM_KEYS)
        require(valid, f"unknown validator claim mismatch: {item!r}")
        claims.append(item)
    require(
        claims == sorted(set(claims)),
        "validator claim_mismatches are not sorted and unique",
    )
    return claims


def validate_validator_findings(
    raw: bytes,
    identities: Sequence[Mapping[str, Any]],
    bundle_records: Sequence[Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    require(len(identities) == 2, "outer seal requires exactly two bundle identities")
    require(len(bundle_records) == 2, "outer seal requires exactly two bundle inventories")
    findings = read_json_bytes(raw, VALIDATOR_FINDINGS_PATH)
    require_canonical_json_document(raw, findings, VALIDATOR_FINDINGS_PATH)
    require(isinstance(findings, dict), "validator findings must contain an object")
    _require_exact_keys(
        findings, set(VALIDATOR_FINDINGS_KEYS), "validator findings"
    )
    require(
        findings["schema"] == VALIDATOR_FINDINGS_SCHEMA,
        "validator findings schema mismatch",
    )
    require(
        findings["validator_sha256"] == PINNED_VALIDATOR_SHA256,
        "validator findings pin mismatch",
    )
    source_shas = {identity["source_sha"] for identity in identities}
    require(len(source_shas) == 1, "full-bundle source SHAs differ")
    source_sha = next(iter(source_shas))
    require(findings["source_sha"] == source_sha,
            "validator findings source SHA mismatch")
    require(findings["mode"] == "full", "validator findings mode mismatch")
    require(
        findings["first_manifest_pre_hash"]
        == identities[0]["manifest_pre_hash"],
        "validator findings first manifest pre-hash mismatch",
    )
    require(
        findings["second_manifest_pre_hash"]
        == identities[1]["manifest_pre_hash"],
        "validator findings second manifest pre-hash mismatch",
    )
    structural = findings["bundle_structural_valid"]
    require(
        structural == [True, True],
        "validator findings do not certify both bundle structures",
    )
    require(
        findings["producer_claims_sha256"]
        == _producer_claims_sha256(identities),
        "validator findings producer-claims digest mismatch",
    )

    expected_mismatches = _bundle_mismatches(
        bundle_records[0], bundle_records[1]
    )
    mismatches = findings["mismatches"]
    require(isinstance(mismatches, list), "validator mismatches must be a list")
    for index, mismatch in enumerate(mismatches):
        require(isinstance(mismatch, dict),
                f"validator mismatches[{index}] must be an object")
        _require_exact_keys(
            mismatch,
            {"path", "first_sha256", "second_sha256"},
            f"validator mismatches[{index}]",
        )
        require(isinstance(mismatch["path"], str),
                f"validator mismatches[{index}].path must be a string")
        for key in ("first_sha256", "second_sha256"):
            require(
                isinstance(mismatch[key], str)
                and SHA256_RE.fullmatch(mismatch[key]) is not None,
                f"validator mismatches[{index}].{key} is invalid",
            )
    require(
        mismatches == expected_mismatches,
        "validator mismatch inventory differs from independent seal replay",
    )

    expected_status = (
        "nondeterministic" if expected_mismatches else "byte_identical"
    )
    require(
        findings["comparison_status"] in VALID_COMPARISON_STATUSES
        and findings["comparison_status"] == expected_status,
        "validator comparison status mismatch",
    )
    gates = findings["derived_gates"]
    require(isinstance(gates, dict), "validator derived_gates must be an object")
    _require_exact_keys(gates, set(DERIVED_GATE_KEYS), "validator derived_gates")
    require(
        all(isinstance(gates[key], bool) for key in DERIVED_GATE_KEYS),
        "validator derived gates must all be Boolean",
    )
    require(
        gates["deterministic_repeatability"] is (not expected_mismatches),
        "validator deterministic-repeatability gate mismatch",
    )
    claim_mismatches = _validate_claim_mismatches(
        findings["claim_mismatches"]
    )
    require(
        gates["producer_claims_consistent"] is (not claim_mismatches),
        "validator producer-claims-consistent gate mismatch",
    )
    candidate_findings = findings["candidate_findings"]
    require(
        isinstance(candidate_findings, dict)
        and set(candidate_findings) == {"A", "B", "C", "D"},
        "validator candidate findings keys mismatch",
    )
    for candidate, value in candidate_findings.items():
        _require_nonempty_string(value, f"validator candidate finding {candidate}")
    decision = _require_nonempty_string(
        findings["decision"], "validator decision"
    )
    require(findings["promotion"] is False,
            "validator findings attempt promotion")
    result_hash = findings["result_sha256_before_hash_field"]
    require(
        isinstance(result_hash, str)
        and SHA256_RE.fullmatch(result_hash) is not None,
        "validator result pre-hash is invalid",
    )
    pre_hash_payload = {
        key: value for key, value in findings.items()
        if key != "result_sha256_before_hash_field"
    }
    require(
        result_hash == sha256_bytes(_canonical_json(pre_hash_payload)),
        "validator result pre-hash mismatch",
    )

    producer_claims_divergence = any(
        identity["nondeterminism_detected"] for identity in identities
    )
    require(
        not (not expected_mismatches and producer_claims_divergence),
        "byte-identical bundles claim divergent execution",
    )
    negative_route = bool(expected_mismatches or claim_mismatches)
    route = (
        "preserved_negative" if negative_route else "deterministic_success"
    )
    if negative_route:
        require(decision == STOP_DECISION,
                "negative evidence route does not force STOP")
        require(
            candidate_findings["A"]
            == (
                "negative_control_reproduced"
                if gates["negative_control_reproduced"]
                else "negative_control_failed"
            )
            and all(
                candidate_findings[candidate] == "inconclusive"
                for candidate in ("B", "C", "D")
            ),
            "negative evidence route findings are not quarantined",
        )
    else:
        require(
            all(
                identity["nondeterminism_detected"] is False
                for identity in identities
            ),
            "deterministic evidence route has a nondeterminism claim",
        )

    return {
        "comparison_status": expected_status,
        "decision": decision,
        "evidence_route": route,
        "findings": findings,
        "findings_sha256": sha256_bytes(raw),
        "promotion": False,
        "result_sha256_before_hash_field": result_hash,
        "source_sha": source_sha,
    }


def _run_pinned_validator(
    bundle_a: Path,
    bundle_b: Path,
    identities: Sequence[Mapping[str, Any]],
    bundle_records: Sequence[Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Run the repository-pinned semantic validator over both full bundles."""

    validator = Path(__file__).resolve().parents[1] / "reference" / VALIDATOR_BASENAME
    validator_bytes = _read_bounded_regular_bytes(
        validator, MAX_VALIDATOR_BYTES
    )
    digest = sha256_bytes(validator_bytes)
    require(digest == PINNED_VALIDATOR_SHA256,
            "local semantic validator differs from the sealer-pinned SHA-256")
    with tempfile.TemporaryDirectory(
        prefix="mls-mechanical-pinned-validator-"
    ) as temporary:
        isolated_root = Path(temporary)
        isolated_validator = isolated_root / VALIDATOR_BASENAME
        findings_output = isolated_root / "validator-findings.json"
        try:
            isolated_validator.write_bytes(validator_bytes)
            if os.name != "nt":
                isolated_validator.chmod(stat.S_IREAD)
        except OSError as error:
            fail(f"cannot materialize pinned local semantic validator: {error}")
        require(
            sha256_bytes(
                _read_bounded_regular_bytes(
                    isolated_validator, MAX_VALIDATOR_BYTES
                )
            )
            == PINNED_VALIDATOR_SHA256,
            "private semantic-validator snapshot differs from pinned bytes",
        )
        python = Path(sys.executable).resolve()
        require(
            python.is_file() and not python.is_symlink(),
            f"Python executable is unavailable or linked: {python}",
        )
        command = [
            str(python),
            "-I",
            "-S",
            "-B",
            "-X",
            "utf8",
            "-",
            "--bundle", str(bundle_a),
            "--compare", str(bundle_b),
            "--findings-output", str(findings_output),
            "--validator-sha256", PINNED_VALIDATOR_SHA256,
        ]
        environment = {
            name: os.environ[name]
            for name in ("SYSTEMROOT", "WINDIR")
            if name in os.environ
        }
        environment.update(
            {"TEMP": str(isolated_root), "TMP": str(isolated_root)}
        )
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                input=validator_bytes,
                timeout=3600,
                cwd=isolated_root,
                env=environment,
            )
        except (OSError, subprocess.SubprocessError) as error:
            fail(f"cannot execute pinned local semantic validator: {error}")
        require(
            sha256_bytes(
                _read_bounded_regular_bytes(
                    isolated_validator, MAX_VALIDATOR_BYTES
                )
            )
            == PINNED_VALIDATOR_SHA256,
            "private semantic-validator snapshot changed during execution",
        )
        findings_bytes = _read_bounded_regular_bytes(
            findings_output, MAX_JSON_BYTES
        )
    require(
        len(result.stdout) <= MAX_VALIDATOR_OUTPUT_BYTES
        and len(result.stderr) <= MAX_VALIDATOR_OUTPUT_BYTES,
        "pinned semantic validator output exceeds frozen byte cap",
    )
    require(
        b"\r" not in result.stdout and b"\r" not in result.stderr,
        "pinned semantic validator output is not canonical LF-only UTF-8",
    )
    try:
        stdout = result.stdout.decode("utf-8", errors="strict")
        stderr = result.stderr.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        fail(f"pinned semantic validator output is not UTF-8: {error}")
    require(result.returncode == 0 and stderr == "",
            "pinned local semantic validator rejected the sealed bundles")
    require(stdout.endswith("\n"),
            "pinned validator stdout lacks canonical final LF")
    lines = stdout.splitlines()
    require(
        len(lines) == 2 and lines[0].startswith(VALIDATOR_SUCCESS_MARKER),
        "pinned validator stdout does not have the frozen two-line form",
    )
    findings_sha256 = sha256_bytes(findings_bytes)
    require(
        lines[1] == f"findings_sha256={findings_sha256}",
        "pinned validator stdout findings digest mismatch",
    )
    outcome = validate_validator_findings(
        findings_bytes, identities, bundle_records
    )
    require(
        outcome["findings_sha256"] == findings_sha256,
        "internal validator findings digest mismatch",
    )
    outcome.update(
        {
            "findings_bytes": findings_bytes,
            "stdout_bytes": result.stdout,
            "validator_log_sha256": sha256_bytes(result.stdout),
        }
    )
    return outcome


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
    require(path in records, "captured external CI metadata is missing")
    require(int(records[path]["size"]) > 0, "captured external CI metadata is empty")
    ci = read_canonical_json(root / path)
    require(isinstance(ci, dict), "ci/metadata.json must contain an object")
    _require_exact_keys(
        ci,
        {
            "schema",
            "claim_kind",
            "authentication_status",
            "head_sha",
            "head_branch",
            "repository_url",
            "run_id",
            "run_url",
            "conclusion",
            "jobs",
        },
        "captured external CI metadata",
    )
    require(ci["schema"] == CI_SCHEMA, "captured external CI schema mismatch")
    require(
        ci["claim_kind"] == "captured_external_github_actions_metadata"
        and ci["authentication_status"] == UNAUTHENTICATED_EXTERNAL,
        "external CI metadata is not explicitly labeled captured/unauthenticated",
    )
    require(ci["head_sha"] == source_sha, "captured CI head SHA mismatch")
    require(ci["head_branch"] == BRANCH, "captured CI branch mismatch")
    require(
        ci["repository_url"] == PUBLIC_REPOSITORY,
        "independent CI repository URL mismatch",
    )
    run_url = _require_nonempty_string(ci["run_url"], "independent CI run_url")
    run_id = ci["run_id"]
    require(isinstance(run_id, int) and not isinstance(run_id, bool) and run_id > 0,
            "captured CI run_id must be a positive integer")
    run_prefix = PUBLIC_REPOSITORY + "/actions/runs/"
    require(
        run_url == run_prefix + str(run_id),
        "captured CI run URL is not bound to repository/run_id",
    )
    status_value = _require_nonempty_string(ci["conclusion"], "captured CI conclusion")
    require(status_value in CI_STATUSES, f"invalid independent CI status: {status_value!r}")
    require(
        status_value == "success",
        f"independent CI run is not successful: {status_value!r}",
    )

    jobs_value = ci["jobs"]
    require(
        isinstance(jobs_value, list) and jobs_value,
        "captured CI jobs must be a nonempty list",
    )
    jobs: dict[str, Mapping[str, Any]] = {}
    names: dict[str, str] = {}
    for index, item in enumerate(jobs_value):
        require(isinstance(item, dict), f"captured CI jobs[{index}] must be an object")
        _require_exact_keys(
            item, {"id", "database_id", "name", "conclusion", "url"},
            f"captured CI jobs[{index}]"
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
            item["conclusion"], f"captured CI jobs[{index}].conclusion"
        )
        require(job_status in CI_STATUSES, f"invalid CI job status: {job_status!r}")
        require(
            job_status == "success",
            f"independent CI job {job_id!r} is not successful: {job_status!r}",
        )
        url = _require_nonempty_string(
            item["url"], f"independent CI jobs[{index}].url"
        )
        database_id = item["database_id"]
        require(isinstance(database_id, int) and not isinstance(database_id, bool)
                and database_id > 0,
                f"captured CI job {job_id!r} database_id")
        require(
            url == run_url + "/job/" + str(database_id),
            f"CI job URL is outside the declared run: {url}",
        )
        jobs[job_id] = item
    missing_jobs = REQUIRED_CI_JOB_IDS - set(jobs)
    require(
        not missing_jobs,
        f"independent CI jobs are missing: {sorted(missing_jobs)}",
    )


def _validator_outcome_binding(
    validator_outcome: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "binding_kind": "fresh_pinned_validator_replay",
        "comparison_status": validator_outcome["comparison_status"],
        "decision": validator_outcome["decision"],
        "evidence_route": validator_outcome["evidence_route"],
        "findings_path": VALIDATOR_FINDINGS_PATH,
        "findings_sha256": validator_outcome["findings_sha256"],
        "promotion": False,
        "result_sha256_before_hash_field": validator_outcome[
            "result_sha256_before_hash_field"
        ],
        "validator_log_path": VALIDATOR_LOG_PATH,
        "validator_log_sha256": validator_outcome[
            "validator_log_sha256"
        ],
    }


def _validate_validator_binding(value: Any, context: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{context} must be an object")
    keys = {
        "binding_kind",
        "comparison_status",
        "decision",
        "evidence_route",
        "findings_path",
        "findings_sha256",
        "promotion",
        "result_sha256_before_hash_field",
        "validator_log_path",
        "validator_log_sha256",
    }
    _require_exact_keys(value, keys, context)
    require(
        value["binding_kind"] == "fresh_pinned_validator_replay",
        f"{context} binding kind mismatch",
    )
    require(
        value["comparison_status"] in {"byte_identical", "nondeterministic"},
        f"{context} comparison status mismatch",
    )
    require(
        value["evidence_route"]
        in {"deterministic_success", "preserved_negative"},
        f"{context} evidence route mismatch",
    )
    require(value["findings_path"] == VALIDATOR_FINDINGS_PATH,
            f"{context} findings path mismatch")
    require(value["validator_log_path"] == VALIDATOR_LOG_PATH,
            f"{context} validator log path mismatch")
    _require_nonempty_string(value["decision"], f"{context} decision")
    require(value["promotion"] is False, f"{context} attempts promotion")
    for key in (
        "findings_sha256",
        "result_sha256_before_hash_field",
        "validator_log_sha256",
    ):
        require(
            isinstance(value[key], str)
            and SHA256_RE.fullmatch(value[key]) is not None,
            f"{context}.{key} is not a SHA-256 digest",
        )
    return dict(value)


def validate_metadata(
    root: Path,
    records: Sequence[Mapping[str, Any]],
    bundle_identities: Sequence[Mapping[str, Any]],
    validator_outcome: Mapping[str, Any],
) -> dict[str, Any]:
    record_by_path = _record_map(records)
    metadata = read_canonical_json(root / "metadata.json")
    require(isinstance(metadata, dict), "metadata.json must contain an object")
    _require_exact_keys(
        metadata,
        {
            "schema",
            "seal_claim_scope",
            "source",
            "commands",
            "local",
            "captured_external_ci",
            "validator_findings",
        },
        "metadata",
    )
    require(metadata["schema"] == METADATA_SCHEMA, "metadata schema mismatch")
    require(metadata["seal_claim_scope"] == OFFLINE_CLAIM_SCOPE,
            "offline seal claim scope mismatch")

    source = metadata["source"]
    require(isinstance(source, dict), "metadata.source must be an object")
    _require_exact_keys(
        source,
        {
            "claim_kind", "authentication_status", "sha", "branch", "tag",
            "tag_target_sha", "repository_url",
        },
        "metadata.source",
    )
    require(source["claim_kind"] == "captured_external_git_metadata"
            and source["authentication_status"] == UNAUTHENTICATED_EXTERNAL,
            "Git metadata is not explicitly labeled captured/unauthenticated")
    source_sha = source["sha"]
    require(
        isinstance(source_sha, str)
        and SOURCE_SHA_RE.fullmatch(source_sha) is not None,
        "source SHA must be exactly 40 lowercase hexadecimal characters",
    )
    require(source["branch"] == BRANCH, f"source branch must be {BRANCH!r}")
    require(
        all(
            source_sha == identity["source_sha"]
            for identity in bundle_identities
        ),
        "metadata source SHA differs from full-bundle source SHA",
    )
    tag = _require_nonempty_string(source["tag"], "metadata.source.tag")
    require(
        TAG_RE.fullmatch(tag) is not None and ".." not in tag and "@{" not in tag,
        "invalid Git tag spelling",
    )
    require(source["tag_target_sha"] == source_sha,
            "captured Git tag target differs from source SHA")
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
        "--bundle" in validator_argv
        and "--compare" in validator_argv
        and "--findings-output" in validator_argv
        and "--validator-sha256" in validator_argv,
        "bundle_compare_validator must compare both bundles and emit pinned findings",
    )
    for flag in (
        "--bundle",
        "--compare",
        "--findings-output",
        "--validator-sha256",
    ):
        require(
            validator_argv.count(flag) == 1,
            f"captured validator command must contain exactly one {flag}",
        )
    pin_index = validator_argv.index("--validator-sha256")
    require(
        pin_index + 1 < len(validator_argv)
        and validator_argv[pin_index + 1] == PINNED_VALIDATOR_SHA256,
        "captured validator command pin differs from sealed validator",
    )
    findings_index = validator_argv.index("--findings-output")
    captured_findings_path = (
        validator_argv[findings_index + 1].replace("\\", "/")
        if findings_index + 1 < len(validator_argv)
        else ""
    )
    require(
        captured_findings_path == VALIDATOR_FINDINGS_PATH
        or captured_findings_path.endswith("/" + VALIDATOR_FINDINGS_PATH),
        "captured validator command findings path differs from sealed artifact",
    )

    local = metadata["local"]
    require(isinstance(local, dict), "metadata.local must be an object")
    _require_exact_keys(
        local,
        {"claim_kind", "authentication_status", "execution_context", "tool_versions", "result_summaries"},
        "metadata.local",
    )
    require(
        local["execution_context"] == "local"
        and local["claim_kind"] == "captured_local_execution_metadata"
        and local["authentication_status"] == UNAUTHENTICATED_EXTERNAL,
        "local results must be explicitly labeled captured/unauthenticated",
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
    findings_binding = metadata["validator_findings"]
    findings_binding = _validate_validator_binding(
        findings_binding, "metadata.validator_findings"
    )
    expected_binding = _validator_outcome_binding(validator_outcome)
    require(
        findings_binding == expected_binding,
        "metadata validator-findings binding differs from fresh replay",
    )
    require(
        str(record_by_path[VALIDATOR_FINDINGS_PATH]["sha256"])
        == validator_outcome["findings_sha256"]
        and str(record_by_path[VALIDATOR_LOG_PATH]["sha256"])
        == validator_outcome["validator_log_sha256"],
        "metadata validator-findings artifacts differ from bound digests",
    )

    independent_ci = metadata["captured_external_ci"]
    require(
        isinstance(independent_ci, dict),
        "metadata.captured_external_ci must be an object",
    )
    _require_exact_keys(
        independent_ci,
        {"claim_kind", "authentication_status", "metadata_path"},
        "metadata.captured_external_ci",
    )
    require(
        independent_ci["claim_kind"] == "captured_external_ci_metadata"
        and independent_ci["authentication_status"] == UNAUTHENTICATED_EXTERNAL,
        "external CI pointer is not labeled captured/unauthenticated",
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
    required = {
        "metadata.json",
        "ci/metadata.json",
        VALIDATOR_FINDINGS_PATH,
        *REQUIRED_LOGS,
    }
    _require_artifacts(records, required, "required provenance")


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
) -> dict[str, Any]:
    required = {
        "metadata.json",
        "ci/metadata.json",
        VALIDATOR_FINDINGS_PATH,
        *REQUIRED_LOGS,
    }
    for bundle in FULL_BUNDLES:
        required.update(f"{bundle}/{name}" for name in (*INNER_FILES, "manifest.json"))
    _require_artifacts(records, required, "required sealed evidence")

    identities: list[dict[str, Any]] = []
    bundle_records: list[list[dict[str, Any]]] = []
    for bundle in FULL_BUNDLES:
        local_records = _records_below(records, bundle)
        bundle_records.append(local_records)
        identities.append(
            validate_inner_bundle(root / bundle, local_records, bundle)
        )
    require(
        identities[0]["source_sha"] == identities[1]["source_sha"]
        and identities[0]["branch"] == identities[1]["branch"],
        "full-a and full-b source identities differ",
    )
    outcome = _run_pinned_validator(
        root / FULL_BUNDLES[0],
        root / FULL_BUNDLES[1],
        identities,
        bundle_records,
    )
    captured_findings = _read_bounded_regular_bytes(
        root / VALIDATOR_FINDINGS_PATH, MAX_JSON_BYTES
    )
    require(
        captured_findings == outcome["findings_bytes"],
        "captured validator findings differ byte-for-byte from fresh replay",
    )
    captured_log = _read_bounded_regular_bytes(
        root / VALIDATOR_LOG_PATH, MAX_LOG_BYTES
    )
    require(
        captured_log == outcome["stdout_bytes"],
        "captured validator log differs byte-for-byte from fresh replay",
    )
    validate_metadata(root, records, identities, outcome)
    return outcome


def _validate_manifest_records(value: Any) -> list[dict[str, Any]]:
    require(isinstance(value, list), "outer manifest files must be a list")
    require(
        len(value) <= MAX_REGULAR_FILES,
        "outer manifest exceeds frozen regular-file-count cap",
    )
    records: list[dict[str, Any]] = []
    paths: list[str] = []
    total_size = 0
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
        require(
            size <= evidence_file_cap(path),
            f"declared size exceeds frozen per-file cap for {path!r}",
        )
        total_size += size
        require(
            total_size <= MAX_SEAL_BYTES,
            "outer manifest exceeds frozen total byte cap",
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
    validator_findings: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "algorithm": "SHA-256",
        "claim_scope": OFFLINE_CLAIM_SCOPE,
        "files": list(records),
        "metadata_path": "metadata.json",
        "pinned_validator_sha256": PINNED_VALIDATOR_SHA256,
        "schema": OUTER_SCHEMA,
        "validator_findings": dict(validator_findings),
    }


def build_manifest(
    records: Sequence[Mapping[str, Any]],
    validator_outcome: Mapping[str, Any],
) -> dict[str, Any]:
    payload = manifest_payload(
        records, _validator_outcome_binding(validator_outcome)
    )
    return {
        **payload,
        "pre_hash_sha256": sha256_bytes(_canonical_json(payload)),
    }


def write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    encoded = _canonical_json_document(manifest)
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
    manifest_bytes_before = _read_bounded_regular_bytes(
        manifest_path, MAX_JSON_BYTES
    )
    manifest = read_json_bytes(manifest_bytes_before, str(manifest_path))
    require_canonical_json_document(
        manifest_bytes_before, manifest, str(manifest_path)
    )
    require(isinstance(manifest, dict), "outer manifest must contain an object")
    _require_exact_keys(
        manifest,
        {
            "algorithm",
            "claim_scope",
            "files",
            "metadata_path",
            "pinned_validator_sha256",
            "pre_hash_sha256",
            "schema",
            "validator_findings",
        },
        "outer manifest",
    )
    require(manifest["algorithm"] == "SHA-256", "outer manifest algorithm mismatch")
    require(manifest["schema"] == OUTER_SCHEMA, "outer manifest schema mismatch")
    require(manifest["claim_scope"] == OFFLINE_CLAIM_SCOPE,
            "outer manifest claim scope mismatch")
    require(manifest["pinned_validator_sha256"] == PINNED_VALIDATOR_SHA256,
            "outer manifest validator pin mismatch")
    require(
        manifest["metadata_path"] == "metadata.json",
        "outer manifest metadata path mismatch",
    )
    records = _validate_manifest_records(manifest["files"])
    claimed_validator_binding = _validate_validator_binding(
        manifest["validator_findings"], "outer manifest validator_findings"
    )
    pre_hash = manifest["pre_hash_sha256"]
    require(
        isinstance(pre_hash, str) and SHA256_RE.fullmatch(pre_hash) is not None,
        "outer manifest pre-hash is invalid",
    )
    require(
        pre_hash
        == sha256_bytes(
            _canonical_json(
                manifest_payload(records, claimed_validator_binding)
            )
        ),
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
    # Never semantically reopen the live tree.  Digest-copy every manifest-
    # bound byte into a private snapshot first; replace/restore races on the
    # live seal can then neither supply different semantic input nor evade the
    # final rescan.
    with tempfile.TemporaryDirectory(
        prefix="mls-mechanical-seal-verify-snapshot-"
    ) as temporary:
        snapshot = Path(temporary) / "seal"
        snapshot.mkdir(parents=True, exist_ok=False)
        _copy_records(root, snapshot, records)
        try:
            (snapshot / OUTER_MANIFEST).write_bytes(manifest_bytes_before)
        except OSError as error:
            fail(f"cannot materialize snapshotted outer manifest: {error}")
        snapshot_records = scan_regular_files(
            snapshot, exclude_root_outer_manifest=True
        )
        require(snapshot_records == records,
                "private seal snapshot differs from outer manifest")
        validator_outcome = validate_seal_artifacts(
            snapshot, snapshot_records
        )
        require(
            claimed_validator_binding
            == _validator_outcome_binding(validator_outcome),
            "outer manifest validator binding differs from fresh replay",
        )
        require(
            _read_bounded_regular_bytes(
                snapshot / OUTER_MANIFEST, MAX_JSON_BYTES
            )
            == manifest_bytes_before,
            "private outer-manifest snapshot changed during validation",
        )
        require(
            scan_regular_files(
                snapshot, exclude_root_outer_manifest=True
            )
            == records,
            "private seal snapshot changed during semantic validation",
        )

    # Semantic validation may run for many minutes.  Require both the live
    # manifest and complete file tree to remain byte-identical as well.
    require(not manifest_path.is_symlink() and not _is_junction(manifest_path),
            "outer manifest became a link/junction during validation")
    manifest_bytes_after = _read_bounded_regular_bytes(
        manifest_path, MAX_JSON_BYTES
    )
    require(manifest_bytes_after == manifest_bytes_before,
            "outer manifest changed during semantic validation")
    post_validation_records = scan_regular_files(
        root, exclude_root_outer_manifest=True
    )
    require(post_validation_records == records,
            "sealed evidence changed during semantic validation")
    return manifest


def _copy_regular_file(
    source: Path,
    destination: Path,
    expected_size: int,
    expected_digest: str,
) -> None:
    require(
        0 <= expected_size <= evidence_file_cap(destination.name),
        f"copy size exceeds frozen cap: {source}",
    )
    digest = hashlib.sha256()
    input_stream, before = _open_regular_file(source)
    observed = 0
    try:
        with input_stream:
            require(
                before.st_size == expected_size,
                f"copy source size differs from manifest: {source}",
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as output_stream:
                while chunk := input_stream.read(1024 * 1024):
                    observed += len(chunk)
                    require(
                        observed <= expected_size,
                        f"copy source grew beyond manifest size: {source}",
                    )
                    digest.update(chunk)
                    output_stream.write(chunk)
            after = os.fstat(input_stream.fileno())
    except OSError as error:
        fail(f"cannot copy {source} to {destination}: {error}")
    require(
        _identity(before) == _identity(after),
        f"copy source changed while being read: {source}",
    )
    try:
        source_after = os.stat(source, follow_symlinks=False)
    except OSError as error:
        fail(f"copy source disappeared after reading {source}: {error}")
    require(
        _identity(after) == _identity(source_after),
        f"copy source was replaced while being read: {source}",
    )
    require(
        observed == expected_size and digest.hexdigest() == expected_digest,
        f"copy source changed after validation: {source}",
    )


def _copy_records(
    source_root: Path,
    destination_root: Path,
    records: Sequence[Mapping[str, Any]],
) -> None:
    require(
        len(records) <= MAX_REGULAR_FILES,
        "copy inventory exceeds frozen regular-file-count cap",
    )
    ensure_unique_portable_paths(
        (str(record["path"]) for record in records), "copy inventory"
    )
    total_size = 0
    for record in records:
        relative = str(record["path"])
        expected_size = int(record["size"])
        require(
            expected_size <= evidence_file_cap(relative),
            f"copy inventory file exceeds frozen cap: {relative}",
        )
        total_size += expected_size
        require(
            total_size <= MAX_SEAL_BYTES,
            "copy inventory exceeds frozen total byte cap",
        )
        _copy_regular_file(
            source_root.joinpath(*relative.split("/")),
            destination_root.joinpath(*relative.split("/")),
            expected_size,
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
    require(
        identity_a["source_sha"] == identity_b["source_sha"]
        and identity_a["branch"] == identity_b["branch"],
        "source bundle identities differ",
    )
    provenance_records = scan_regular_files(source_provenance)
    validate_provenance_tree(source_provenance, provenance_records)

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
        validator_outcome = validate_seal_artifacts(staging, records)
        write_manifest(
            staging / OUTER_MANIFEST,
            build_manifest(records, validator_outcome),
        )
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
            "seal_mechanical_observability_evidence.py create "
            "--bundle-a evidence/run-a --bundle-b evidence/run-b "
            "--provenance-dir evidence/provenance "
            "--seal-dir evidence/sealed-final; "
            "verify example: python tools/"
            "seal_mechanical_observability_evidence.py verify "
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
            "MECHANICAL OBSERVABILITY OUTER SEAL INVALID: "
            f"{error}",
            file=sys.stderr,
        )
        return 1
    print(
        "MECHANICAL OBSERVABILITY OUTER SEAL VALID "
        f"mode={options.mode} files={len(manifest['files'])} "
        f"pre_hash_sha256={manifest['pre_hash_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
