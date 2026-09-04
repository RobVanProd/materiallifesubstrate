#!/usr/bin/env python3
"""Focused identity and fail-closed tests for long-oracle CI fragments."""

from __future__ import annotations

import copy
import csv
import sys
import tempfile
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "reference"))

import bounded_fractional_phase_state_oracle as oracle  # noqa: E402


SOURCE_SHA = "a" * 40
RAW_HASHES = {filename: "b" * 64 for filename in oracle.FILES}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def report(level: int) -> dict[str, object]:
    runs = {
        f"B{precision}:L{level}": {"level": level, "precision": precision}
        for precision in oracle.PRECISIONS
    }
    frames = {
        f"long:galilean_boost:B{precision}:L{level}": {"passed": True}
        for precision in oracle.PRECISIONS
    }
    profiles = {
        f"B{precision}:L{level}:{scenario}": True
        for precision in oracle.PRECISIONS
        for scenario in ("k4_internal", "k4_boosted")
    }
    comparators = {
        f"{scenario}:L{level}": {"status": "accepted"}
        for scenario in ("k4_internal", "k4_boosted")
    }
    precision_map = {
        str(precision): {"sample": f"{level}/1"}
        for precision in oracle.PRECISIONS
    }
    certificates = {
        str(precision): {
            **{name: level + 1 for name in oracle.LONG_CERTIFICATE_SUM_FIELDS},
            **{name: f"{level}/1" for name in oracle.LONG_CERTIFICATE_MAX_FIELDS},
            "passed": True,
        }
        for precision in oracle.PRECISIONS
    }
    slopes = {
        name: {str(precision): "0/1" for precision in oracle.PRECISIONS}
        for name in (
            "momentum", "angular", "energy", "boost_position", "boost_momentum",
        )
    }
    anchor_scenarios = {
        scenario: {
            "anchor_required": False,
            "b256_below_one_sixteenth_budget": {"sample": True},
            "b192_b256_unit_roundoff_scaling": {"sample": True},
            "b256_analytic_energy_certificate": True,
        }
        for scenario in ("k4_internal", "k4_boosted")
    }
    boosts = {
        str(precision): {
            "position_maxima": ["0/1"],
            "position_finals": ["0/1"],
            "momentum_maxima": ["0/1"],
            "momentum_finals": ["0/1"],
        }
        for precision in oracle.PRECISIONS
    }
    result = {field: {} for field in oracle.LONG_REPLAY_REPORT_FIELDS}
    result.update({
        "runs": runs,
        "force_maxima": copy.deepcopy(precision_map),
        "independently_summed_half_ulp_bound_maxima": copy.deepcopy(precision_map),
        "long_frame_summed_local_half_ulp_certificates": frames,
        "long_frame_bound_pass": {
            str(precision): True for precision in oracle.PRECISIONS
        },
        "exact_prefix_energy_componentwise_certificates": certificates,
        "exact_prefix_energy_profile_pass": profiles,
        "paired_bound_accumulator": {"fitted_constants": False},
        "slope_envelopes": slopes,
        "slope_unit_roundoff_scaling": {name: True for name in slopes},
        "b256_all_residual_slopes_below_one_sixteenth_budget_diagnostic": True,
        "b192_b256_all_residual_slopes_unit_roundoff_diagnostic": True,
        "long_exact_prefix_anchor": {
            str(level): {
                "scenarios": anchor_scenarios,
                "all_required_scenarios_qualified": True,
            }
        },
        "all_required_exact_prefix_below_one_sixteenth_budget": True,
        "all_required_exact_prefix_unit_roundoff_scaling": True,
        "all_required_full_tail_anchors_qualified": True,
        "comparator_free_b256_trace_agreement": copy.deepcopy(runs),
        "boost_timestep_contraction": boosts,
        "exact_rational_comparator_receipts": comparators,
        "compact_xyz_hash_max_physical_and_delta_derivations": True,
    })
    return result


def fragment(level: int) -> dict[str, object]:
    result: dict[str, object] = {
        "schema": oracle.LONG_REPLAY_FRAGMENT_SCHEMA,
        "source_sha": SOURCE_SHA,
        "parent_source_sha": oracle.PARENT_SHA,
        "level": level,
        "raw_files": RAW_HASHES,
        "long_run": report(level),
        "precision_pass": {
            str(precision): True for precision in oracle.PRECISIONS
        },
        "representation_envelopes": {
            name: {
                str(precision): "0/1" for precision in oracle.PRECISIONS
            }
            for name in (
                "representation_position", "representation_momentum",
                "representation_energy",
            )
        },
    }
    result["payload_sha256"] = oracle.canonical_json_sha256(
        oracle.long_replay_fragment_payload(result)
    )
    return result


def rejected(values: list[dict[str, object]], label: str) -> None:
    try:
        oracle.ordered_long_replay_fragments(values, SOURCE_SHA, RAW_HASHES)
    except oracle.OracleError:
        return
    raise AssertionError(f"{label} fragment mutation was accepted")


def write_order_fixture(root: Path, mutated: str | None = None) -> None:
    ordered_levels = list(oracle.LEVELS)
    reordered_levels = [0, 2, 1, 3, 4]
    specifications = {
        "long_energy.csv": ("scenario_id", "k4_internal"),
        "covariance.csv": ("scope", "long"),
        "invariants.csv": ("trajectory_id", "long:k4_internal:B256"),
        "force_audit.csv": ("trajectory_id", "long:k4_internal:B256"),
    }
    for filename, (selector, value) in specifications.items():
        levels = reordered_levels if filename == mutated else ordered_levels
        with (root / filename).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=(selector, "level"))
            writer.writeheader()
            writer.writerows(
                {selector: value, "level": str(level)} for level in levels
            )


def order_rejected(raw: Path, label: str) -> None:
    try:
        oracle.verify_long_replay_global_level_order(raw)
    except oracle.OracleError:
        return
    raise AssertionError(f"{label} global level-order mutation was accepted")


def main() -> int:
    fragments = [fragment(level) for level in reversed(oracle.LEVELS)]
    ordered = oracle.ordered_long_replay_fragments(
        fragments, SOURCE_SHA, RAW_HASHES
    )
    require(
        [item["level"] for item in ordered] == list(oracle.LEVELS),
        "fragment order was not canonicalized by registered level",
    )
    merged, precision_pass, long_scaling, envelopes = (
        oracle.merge_long_replay_fragments(fragments, SOURCE_SHA, RAW_HASHES)
    )
    require(set(merged) == oracle.LONG_REPLAY_REPORT_FIELDS,
            "merged report field inventory differs")
    require(len(merged["runs"]) == len(oracle.PRECISIONS) * len(oracle.LEVELS),
            "merged run inventory differs")
    require(merged["force_maxima"]["256"]["sample"] == "4/1",
            "fragment maxima were not reduced across levels")
    expected_count = sum(level + 1 for level in oracle.LEVELS)
    require(
        merged["exact_prefix_energy_componentwise_certificates"]["256"]["samples"]
        == expected_count,
        "fragment certificate counts were not summed across levels",
    )
    require(
        len(merged["boost_timestep_contraction"]["256"]["position_maxima"])
        == len(oracle.LEVELS)
        and all(precision_pass.values()) and long_scaling
        and all(value == 0 for values in envelopes.values() for value in values.values()),
        "fragment cross-level gates or envelopes differ",
    )

    missing = copy.deepcopy(fragments[:-1])
    rejected(missing, "missing-level")

    duplicate = copy.deepcopy(fragments)
    duplicate[-1]["level"] = duplicate[0]["level"]
    rejected(duplicate, "duplicate-level")

    wrong_source = copy.deepcopy(fragments)
    wrong_source[0]["source_sha"] = "c" * 40
    rejected(wrong_source, "source-identity")

    wrong_parent = copy.deepcopy(fragments)
    wrong_parent[0]["parent_source_sha"] = "d" * 40
    rejected(wrong_parent, "parent-identity")

    wrong_raw = copy.deepcopy(fragments)
    wrong_raw[0]["raw_files"][oracle.FILES[0]] = "e" * 64
    rejected(wrong_raw, "raw-identity")

    tampered = copy.deepcopy(fragments)
    tampered_run = tampered[0]["long_run"]["runs"]
    tampered_run[next(iter(tampered_run))]["precision"] = 1
    rejected(tampered, "payload-digest")

    extra_field = copy.deepcopy(fragments)
    extra_field[0]["unexpected"] = True
    rejected(extra_field, "field-inventory")

    with tempfile.TemporaryDirectory() as temporary:
        raw = Path(temporary)
        write_order_fixture(raw)
        counts = oracle.verify_long_replay_global_level_order(raw)
        require(
            counts == {
                "long_energy.csv": len(oracle.LEVELS),
                "covariance.csv": len(oracle.LEVELS),
                "invariants.csv": len(oracle.LEVELS),
                "force_audit.csv": len(oracle.LEVELS),
            },
            "valid global level-order fixture differs",
        )
        for filename in counts:
            write_order_fixture(raw, filename)
            order_rejected(raw, filename)

    print("bounded fractional phase-state oracle sharding contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
