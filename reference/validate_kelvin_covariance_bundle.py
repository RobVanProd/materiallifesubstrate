#!/usr/bin/env python3
"""Independent structural validator for Kelvin Covariance Audit evidence."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import pathlib
import struct
import sys
from dataclasses import dataclass

EXPECTED_CONFIGS = {
    "cube8": (8, 2.0),
    "bcc9": (9, 2.0),
    "jitter27": (27, 2.2),
    "surface18": (18, 3.1),
}
EXPECTED_TRANSFORMS = {
    "translation": 1.0,
    "rotation": 1.0,
    "rotation_translation": 1.0,
    "scale_half_rotation_translation": 0.5,
    "scale_double_rotation_translation": 2.0,
    "packet_permutation": 1.0,
}
ORACLE_SHA = "58fa03bef4451bc5411ce8ee2c59f17e8f1fa6e056f2909147a0e15ef81d9ff6"
REQUIRED_FILES = {
    "summary.json",
    "tolerances.json",
    "counterexample.json",
    "covariance.csv",
    *(f"checkpoints/{name}.bin" for name in EXPECTED_CONFIGS),
}
EPSILON64 = 2.0 ** -52


class ValidationError(RuntimeError):
    pass


@dataclass
class Audit:
    checks: int = 0

    def require(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            raise ValidationError(message)


def read_json(path: pathlib.Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"cannot read {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise ValidationError(f"{path.name} root must be an object")
    return value


def finite_hex(value: str, field: str) -> float:
    try:
        parsed = float.fromhex(value)
    except (TypeError, ValueError) as error:
        raise ValidationError(f"invalid hexadecimal float {field}") from error
    if not math.isfinite(parsed):
        raise ValidationError(f"nonfinite value {field}")
    return parsed


def bool_field(value: str, field: str) -> bool:
    if value not in {"true", "false"}:
        raise ValidationError(f"invalid boolean {field}")
    return value == "true"


def canonical_tree(root: pathlib.Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix()
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def parse_checkpoint(path: pathlib.Path, expected_count: int,
                     expected_support: float, audit: Audit) -> None:
    data = path.read_bytes()
    offset = 0

    def take(fmt: str):
        nonlocal offset
        size = struct.calcsize(fmt)
        audit.require(offset + size <= len(data), f"{path.name} truncated")
        value = struct.unpack_from(fmt, data, offset)
        offset += size
        return value[0] if len(value) == 1 else value

    audit.require(data[:8] == b"MLSMOBS1", f"{path.name} magic")
    offset = 8
    audit.require(take("<I") == 1, f"{path.name} version")
    support = take("<d")
    audit.require(math.isfinite(support) and support == expected_support,
                  f"{path.name} support")
    packet_count = take("<Q")
    audit.require(packet_count == expected_count, f"{path.name} packet count")
    previous_id = 0
    for _ in range(packet_count):
        packet_id = take("<Q")
        mass = take("<q")
        state = take("<6d")
        audit.require(packet_id > previous_id, f"{path.name} canonical IDs")
        audit.require(mass == 1, f"{path.name} mass")
        audit.require(all(math.isfinite(x) for x in state),
                      f"{path.name} finite packet")
        audit.require(state[3:] == (0.0, 0.0, 0.0),
                      f"{path.name} zero diagnostic velocity")
        previous_id = packet_id
    audit.require(take("<Q") == 0, f"{path.name} bonds absent")
    audit.require(take("<Q") == 0, f"{path.name} volumes absent")
    audit.require(offset == len(data), f"{path.name} trailing bytes")


def validate_bundle(
    root: pathlib.Path, allow_dirty: bool, expected_source_branch: str
) -> tuple[int, dict]:
    audit = Audit()
    audit.require(root.is_dir(), "bundle directory missing")
    tree = canonical_tree(root)
    audit.require(set(tree) == REQUIRED_FILES,
                  f"file inventory mismatch: {sorted(set(tree) ^ REQUIRED_FILES)}")
    summary = read_json(root / "summary.json")
    tolerances = read_json(root / "tolerances.json")
    counter = read_json(root / "counterexample.json")

    audit.require(summary.get("schema_version") == 1, "schema version")
    audit.require(summary.get("producer") == "cpp_kelvin_covariance_audit",
                  "producer")
    audit.require(summary.get("source_branch") == expected_source_branch,
                  "source branch")
    source_sha = summary.get("source_sha")
    audit.require(isinstance(source_sha, str) and len(source_sha) == 40 and
                  all(c in "0123456789abcdef" for c in source_sha), "source SHA")
    audit.require(allow_dirty or summary.get("source_dirty_at_configure") is False,
                  "source was dirty at configure time")
    audit.require(summary.get("seed") == 260829, "seed")
    audit.require(summary.get("exact_oracle_result_sha256") == ORACLE_SHA,
                  "exact oracle SHA")
    audit.require(summary.get("candidate_promotion_permitted") is False,
                  "promotion must be forbidden")
    audit.require(summary.get("configuration_count") == 4, "configuration count")
    audit.require(summary.get("transform_count") == 6, "transform count")
    audit.require(summary.get("comparison_count") == 24, "comparison count")

    audit.require(finite_hex(tolerances.get("epsilon64"), "epsilon") == EPSILON64,
                  "epsilon")
    expected_factors = {
        "q_factor": 8192,
        "kelvin_factor": 16384,
        "raw_operator_factor": 32768,
        "raw_spectrum_factor": 65536,
        "block_scalar_factor": 65536,
        "counterexample_required_multiple": 1000,
    }
    for key, value in expected_factors.items():
        audit.require(tolerances.get(key) == value, f"tolerance {key}")

    with (root / "covariance.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    audit.require(len(rows) == 24, "covariance row count")
    audit.require(len({(r["configuration"], r["transform"]) for r in rows}) == 24,
                  "duplicate comparison rows")
    expected_pairs = {(c, t) for c in EXPECTED_CONFIGS for t in EXPECTED_TRANSFORMS}
    audit.require({(r["configuration"], r["transform"]) for r in rows} ==
                  expected_pairs, "comparison matrix")

    raw_failures = unavailable = block_failures = legacy_differences = 0
    for row in rows:
        config = row["configuration"]
        transform = row["transform"]
        count, support = EXPECTED_CONFIGS[config]
        scale = EXPECTED_TRANSFORMS[transform]
        audit.require(int(row["packets"]) == count, f"{config}/{transform} packets")
        audit.require(finite_hex(row["support_base_m"], "support") == support,
                      f"{config}/{transform} base support")
        audit.require(finite_hex(row["scale"], "scale") == scale,
                      f"{config}/{transform} scale")
        audit.require(finite_hex(row["support_transformed_m"], "support transformed") ==
                      scale * support, f"{config}/{transform} transformed support")
        audit.require(row["base_status"] == "built" and
                      row["transformed_status"] == "built",
                      f"{config}/{transform} build status")
        dimension = 6 * count
        expected_tolerances = {
            "orthogonality_tolerance": 8192 * dimension * EPSILON64,
            "kelvin_tolerance": 16384 * dimension * EPSILON64,
            "operator_tolerance": 32768 * dimension * EPSILON64,
            "spectrum_tolerance": 65536 * dimension * EPSILON64,
            "block_tolerance": 65536 * dimension * EPSILON64,
        }
        for key, expected in expected_tolerances.items():
            audit.require(finite_hex(row[key], key) == expected,
                          f"{config}/{transform} {key}")
        values = {key: finite_hex(row[key], key) for key in (
            "q_orthogonality_residual", "determinant_residual",
            "kelvin_orthogonality_residual", "raw_operator_residual",
            "raw_scaled_spectrum_delta", "block_scalar_operator_residual",
            "legacy_scalar_row_spectrum_delta")}
        available = bool_field(row["raw_available"], "raw_available")
        raw_pass = (available and
            values["q_orthogonality_residual"] <= expected_tolerances["orthogonality_tolerance"] and
            values["determinant_residual"] <= expected_tolerances["orthogonality_tolerance"] and
            values["kelvin_orthogonality_residual"] <= expected_tolerances["kelvin_tolerance"] and
            values["raw_operator_residual"] <= expected_tolerances["operator_tolerance"] and
            values["raw_scaled_spectrum_delta"] <= expected_tolerances["spectrum_tolerance"])
        block_pass = available and values["block_scalar_operator_residual"] <= \
            expected_tolerances["block_tolerance"]
        audit.require(bool_field(row["raw_pass"], "raw_pass") == raw_pass,
                      f"{config}/{transform} raw flag")
        audit.require(bool_field(row["block_pass"], "block_pass") == block_pass,
                      f"{config}/{transform} block flag")
        audit.require(bool_field(row["pass"], "pass") == (raw_pass and block_pass),
                      f"{config}/{transform} aggregate flag")
        unavailable += int(not available)
        raw_failures += int(available and not raw_pass)
        block_failures += int(available and not block_pass)
        if transform not in {"translation", "packet_permutation"} and \
                values["legacy_scalar_row_spectrum_delta"] > \
                expected_tolerances["spectrum_tolerance"]:
            legacy_differences += 1

    counter_tolerance = 65536 * 6 * EPSILON64
    audit.require(counter.get("construction") ==
                  "actual_3d_kelvin_rotation_of_diagonal_raw_operator",
                  "counterexample construction")
    raw_transform = finite_hex(counter.get("raw_transform_residual"), "counter raw transform")
    raw_spectrum = finite_hex(counter.get("raw_spectrum_delta"), "counter raw spectrum")
    normalized_spectrum = finite_hex(
        counter.get("scalar_row_normalized_spectrum_delta"), "counter normalized")
    audit.require(finite_hex(counter.get("binary64_tolerance"), "counter tolerance") ==
                  counter_tolerance, "counter tolerance")
    counter_pass = (counter.get("row_normalizations_complete") is True and
                    raw_transform <= counter_tolerance and
                    raw_spectrum <= counter_tolerance and
                    normalized_spectrum > 1000 * counter_tolerance)
    audit.require(counter.get("pass") is counter_pass, "counter pass flag")
    decision = ("RAW_OPERATOR_COVARIANCE_FAILURE" if raw_failures else
                "SUPPORTED_DIAGNOSTIC_COORDINATE_DEFECT" if
                unavailable == 0 and block_failures == 0 and counter_pass else
                "INCONCLUSIVE")
    audit.require(summary.get("raw_failures") == raw_failures, "raw failures")
    audit.require(summary.get("unavailable_comparisons") == unavailable,
                  "unavailable count")
    audit.require(summary.get("block_scalar_failures") == block_failures,
                  "block failures")
    audit.require(summary.get("legacy_rotation_spectrum_differences") ==
                  legacy_differences, "legacy difference count")
    audit.require(summary.get("counterexample_pass") is counter_pass,
                  "counter summary")
    audit.require(summary.get("decision") == decision, "decision")

    for name, (count, support) in EXPECTED_CONFIGS.items():
        parse_checkpoint(root / "checkpoints" / f"{name}.bin",
                         count, support, audit)
    return audit.checks, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=pathlib.Path, required=True)
    parser.add_argument("--compare", type=pathlib.Path)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument(
        "--expected-source-branch", default="kelvin-covariance-audit",
        help=("exact branch recorded by the input; the default preserves the "
              "sealed Kelvin-audit contract"),
    )
    args = parser.parse_args()
    try:
        checks, summary = validate_bundle(
            args.bundle, args.allow_dirty, args.expected_source_branch
        )
        if args.compare is not None:
            other_checks, other_summary = validate_bundle(
                args.compare, args.allow_dirty, args.expected_source_branch
            )
            checks += other_checks
            if canonical_tree(args.bundle) != canonical_tree(args.compare):
                raise ValidationError("twin bundles are not byte-for-byte identical")
            if summary != other_summary:
                raise ValidationError("twin summaries differ")
        print(f"KELVIN COVARIANCE BUNDLE VALID: {checks} checks; "
              f"decision={summary['decision']}")
        return 0
    except (OSError, ValidationError, KeyError, ValueError) as error:
        print(f"KELVIN COVARIANCE BUNDLE INVALID: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
