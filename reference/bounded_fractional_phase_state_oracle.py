#!/usr/bin/env python3
"""Independent verifier for Bounded Fractional Phase-State Lab evidence.

The candidate uses MPFR, but this verifier deliberately does not.  Every
stored value is decoded as a :class:`fractions.Fraction`, every registered
rounded primitive is recomputed with integer arithmetic, and every residual
observer operates on the exact dyadic meaning of the wire records.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import struct
import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, getcontext
from fractions import Fraction
from pathlib import Path
from typing import Iterable, Sequence

import explicit_fractional_phase_state_oracle as parent
import time_integration_foundation_oracle as foundation


if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)

getcontext().prec = 110

PARENT_SHA = "6f25d7428fde7420c1f4cbe1e3565c11a28e817c"
PARENT_TAG = "explicit-fractional-phase-state-lab-evidence-v1"
PARENT_TAG_OBJECT = "a0feca21f7676e0b6f1443c483bd62448d68c65b"
PARENT_ARCHIVE_SHA256 = (
    "77aad47e1842b4fe29760594ee247f609b5d1e88ae7e6b370d86c0bdbb6c71de"
)
PARENT_ARCHIVE_SIZE = 31_142_852
PARENT_DECISION = (
    "fractional_phase_state_restores_dynamics_but_bounded_representation_unresolved"
)
FINAL_DECISION = (
    "bounded_phase_state_restores_dynamics_but_structure_residuals_unresolved"
)
FINAL_SELECTED_PRECISION = None
BRANCH = "bounded-fractional-phase-state-lab"
CAUSAL_STATE_SHAPE = (
    "State(precision,time_raw,packets);"
    "Packet(identifier,mass_raw,x[3],p[3]);slots_only_v1"
)
KDK = "bounded_binary_kick_drift_kick"
CONTROL = "bounded_binary_symplectic_euler_control"
Q_KDK = "fractional_kick_drift_kick"
Q_CONTROL = "fractional_symplectic_euler_control"
PRECISIONS = (64, 96, 128, 192, 256)
LEVELS = tuple(range(5))
TIMESTEPS_RAW = (62_500_000, 31_250_000, 15_625_000, 7_812_500, 3_906_250)
STEP_COUNTS = (16, 32, 64, 128, 256)
SCENARIOS = ("k4_breathing", "k4_internal", "octahedron_deformation")

LQ = Fraction(1, 128_000_000_000)
MQ = Fraction(1, 524_288)
TQ = Fraction(1, 1_000_000_000)
PQ = Fraction(1, 67_108_864)
EQ = Fraction(1, 8_589_934_592)
FQ = Fraction(1_953_125, 131_072)
SAFE_SQUARED_RATIO = Fraction(1, 2**48)
Q_BUDGET = Fraction(1, 2**20)
POSITION_BUDGET = LQ * Q_BUDGET
MOMENTUM_BUDGET = PQ * Q_BUDGET
ANGULAR_BUDGET = LQ * PQ * Q_BUDGET
ENERGY_BUDGET = EQ * Q_BUDGET
ENERGY_SLOPE_BUDGET = ENERGY_BUDGET / 16
MOMENTUM_SLOPE_BUDGET = MOMENTUM_BUDGET / 16
ANGULAR_SLOPE_BUDGET = ANGULAR_BUDGET / 16
MIN_EXPONENT = -16_382
MAX_EXPONENT = 16_383
DOMAIN_SCRATCH_PADDING_BITS = 64
EXACT_MAX_COMPONENT_BITS = 262_144
EXACT_MEDIAN_COMPONENT_BITS = 131_072
EXACT_MAX_CHECKPOINT_BYTES = 8_388_608

STATE_MAGIC = b"MLS-BOUNDED-BINARY-PHASE-v1\x00"
OBSERVER_EVENT_MAGIC = b"MLS-BOUNDED-OBSERVER-EVENT-v2\x00"
OBSERVER_STREAM_MAGIC = b"MLS-BOUNDED-OBSERVER-STREAM-v2\x00"
REPRESENTATION_ERROR_COMMITMENT_MAGIC = (
    b"MLS-BOUNDED-REPRESENTATION-ERROR-v2\x00"
)
REPRESENTATION_ERROR_DISPLAY_BITS = 64
REPRESENTATION_ERROR_DISPLAY_MAX_BYTES = 32
ROUNDING_AUDIT_MAGIC = b"MLS-BOUNDED-ROUNDING-AUDIT-v1\x00"
ROUNDING_AUDIT_MERGE_MAGIC = b"MLS-BOUNDED-ROUNDING-AUDIT-MERGE-v1\x00"
SHA1 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
SIGNED_DECIMAL = re.compile(r"0|-?[1-9][0-9]*")
UNSIGNED_DECIMAL = re.compile(r"0|[1-9][0-9]*")

PARENT_HASHES = {
    "checkpoint.csv": "e0045d1f915193d1b29cda6b49fb013df6513806f3e6e9858f330a1a3420c815",
    "checkpoint_states.csv": "4abc339e92a31aef4fd19df1bc4a88ad96c139cba2af9b05af89cc2219e0d36b",
    "covariance.csv": "fde6891c9217c2a42c81d3113803f48227f4f79004dd5199ab64b10177f1ad95",
    "domain.csv": "2a039b7a9a83b8af5fcc9cc63008f08568d5e074eb4d3ad9b9f541927285e942",
    "endpoints.csv": "19b01d10b510b10a69f491f02b9bd5914175d412b2477c8b124c15091ff0fdd3",
    "energies.csv": "0898cf9f64c1b3abe253169997225ca79083344bca261ee2717fdce1bc7650d2",
    "force_audit.csv": "ac3d12575aad9ff0e010fd8413c48e14731131029271275f5e54eccdfc7b5b6f",
    "force_operator.csv": "d5d9a19ea6f8a5cdd25810f2e6a1e35ed039e45463d56a3f208c8b9151698ed7",
    "initial_states.csv": "d9864ce96b8d80a70c5494311b74ee392feaefdcae1c70c875f5192713ccdf8a",
    "invariants.csv": "d26b29686368ef89c771004bc0f6a20dea8f6aaa76d5b6ee385ef0971967c8ce",
    "long_energy.csv": "d139d159dd710fc342b288794ec43d0f208b35a719995c6a7d1dc41d24dc0599",
    "metadata.csv": "4ac5b9f03e5a402b54e8ff1b3848005229055095ea2dbf2191ef80141a9eb7d0",
    "obstruction.csv": "28162b08bc11a03214b5f2ba723be61b6925be4e89cb7c9555ea57841417e843",
    "parent_fingerprint.csv": "1515a999155f1b5988190417c632005e038c6543845aebde600dc99dceff9eaa",
    "recovery_states.csv": "419cf8dfa1ad790de719dc616f601ccef96fa99a2a724155e8f808ec1626c9eb",
    "reference_packets.csv": "907cc08a3f6a8db48143e35d0ee247dccf687cc42ba617f28ff213219312994f",
    "relations.csv": "5b50a04399f9868a9fdc0fe3e263e162aa3a4d52b0be03b11a6cb17a689bece0",
    "reversibility.csv": "079f98712a0ac4443b7b376b408013fe601fbb6fbf7bd6c57d03a2b9378e40d6",
    "state_complexity.csv": "5ab4512b49c0081ec3557e75b67c3bdffcd39ebc5b6887c0b79db87982faf7b1",
    "units.csv": "0c2e6c9e38ac0007be7d7be45463271fb66da6569208e7d371183c2520a32f9b",
}

FILES = (
    "metadata.csv", "precisions.csv", "units.csv", "parent_fingerprint.csv",
    "positive_control.csv", "reference_packets.csv", "relations.csv",
    "force_operator.csv", "initial_states.csv", "endpoints.csv",
    "long_endpoints.csv", "checkpoint_states.csv", "recovery_states.csv",
    "representation_error.csv", "energies.csv", "long_energy.csv",
    "invariants.csv", "force_audit.csv", "reversibility.csv", "covariance.csv",
    "checkpoint.csv", "domain.csv", "state_size.csv", "operation_counts.csv",
    "rational_comparator.csv",
)


def _state_fields() -> tuple[str, ...]:
    base = (
        "precision", "scenario_id", "model_id", "scope", "path", "level", "dt_raw",
        "steps", "status", "completed_steps", "time_raw", "state_hash", "packet_id",
        "mass_raw",
    )
    return base + tuple(
        f"{prefix}_{suffix}"
        for prefix in ("xx", "xy", "xz", "px", "py", "pz")
        for suffix in ("sign", "E", "significand_hex", "wire_hex", "exact_num", "exact_den")
    )


def _raw_vector_fields(prefixes: Sequence[str]) -> tuple[str, ...]:
    return tuple(
        field
        for prefix in prefixes
        for field in (f"{prefix}_raw_{axis}_dyadic" for axis in "xyz")
    )


STATE_FIELDS = _state_fields()
INVARIANT_FIELDS = (
    "trajectory_id", "precision", "level", "step", "stage", "state_hash",
) + _raw_vector_fields(("momentum", "angular"))
FORCE_FIELDS = (
    "trajectory_id", "precision", "level", "step", "stage", "relation_index",
    "first_id", "second_id", "length_bits", "conjugate_bits", "causal_offset_raw_hash",
    "exact_stored_offset_raw_hash", "ideal_impulse_raw_hash",
    "first_actual_impulse_raw_hash", "second_actual_impulse_raw_hash",
) + _raw_vector_fields((
    "pair_momentum_residual", "stored_impulse_centrality_residual",
    "first_actual_centrality_residual", "second_actual_centrality_residual",
    "relation_angular_residual",
))
REPRESENTATION_ERROR_IDENTITY_FIELDS = (
    "scenario_id", "scope", "path", "precision", "level", "dt_raw", "sample",
    "candidate_state_hash", "control_state_hash",
)
REPRESENTATION_ERROR_METRICS = (
    "position_raw_error", "momentum_raw_error", "energy_error",
)
REPRESENTATION_ERROR_FIELDS = (
    *REPRESENTATION_ERROR_IDENTITY_FIELDS,
    "exact_errors_sha256",
    *(f"{metric}_display" for metric in REPRESENTATION_ERROR_METRICS),
)
ENERGY_EVENT_FIELDS = (
    "trajectory_id", "precision", "level", "step", "state_hash",
    "potential_binary64_bits", "kinetic_num", "kinetic_den", "kinetic_hash",
    "potential_num", "potential_den", "potential_hash", "mechanical_num",
    "mechanical_den", "mechanical_hash",
)

SCHEMAS: dict[str, tuple[str, ...]] = {
    "metadata.csv": ("key", "value"),
    "precisions.csv": (
        "precision", "unit_roundoff", "leading_exponent_min", "leading_exponent_max",
        "component_bytes", "phase_bytes_per_packet", "complete_packet_bytes",
        "domain_scratch_bit_limit", "lq_sign", "lq_E", "lq_significand_hex",
        "lq_wire_hex", "lq_exact_num", "lq_exact_den", "lq_conversion_inexact",
        "lq_rounding_audit_sha256", "rounding",
    ),
    "units.csv": (
        "Lq", "Mq", "Tq", "Pq", "Eq", "Fq", "position_budget",
        "momentum_budget", "angular_centrality_budget", "energy_budget",
        "energy_slope_budget",
    ),
    "parent_fingerprint.csv": ("file", "sha256", "expected_sha256", "passed"),
    "positive_control.csv": ("check", "passed", "detail"),
    "reference_packets.csv": ("model_id", "level", "packet_id", "x_raw", "y_raw", "z_raw", "mass_raw"),
    "relations.csv": ("model_id", "relation_index", "first_id", "second_id", "rest_length_bits"),
    "force_operator.csv": ("model_id", "row", "column", "h_bits"),
    "initial_states.csv": STATE_FIELDS,
    "endpoints.csv": STATE_FIELDS,
    "long_endpoints.csv": STATE_FIELDS,
    "checkpoint_states.csv": STATE_FIELDS,
    "recovery_states.csv": STATE_FIELDS,
    "representation_error.csv": REPRESENTATION_ERROR_FIELDS,
    "energies.csv": (
        "scenario_id", "scope", "path", "precision", "level", "dt_raw", "sample",
        "potential_binary64_bits", "kinetic_num", "kinetic_den", "kinetic_hash",
        "potential_num", "potential_den", "potential_hash", "mechanical_num",
        "mechanical_den", "mechanical_hash",
    ),
    "long_energy.csv": (
        "scenario_id", "scope", "path", "precision", "level", "dt_raw", "sample",
        "potential_binary64_bits", "kinetic_num", "kinetic_den", "kinetic_hash",
        "potential_num", "potential_den", "potential_hash", "mechanical_num",
        "mechanical_den", "mechanical_hash",
    ),
    "invariants.csv": INVARIANT_FIELDS,
    "force_audit.csv": FORCE_FIELDS,
    "reversibility.csv": (
        "scenario_id", "precision", "level", "dt_raw", "steps", "forward_status",
        "backward_status", "initial_hash", "recovered_hash", "complete_state_identical",
        "position_raw_error_num", "position_raw_error_den", "position_physical_error_num",
        "position_physical_error_den", "momentum_raw_error_num", "momentum_raw_error_den",
        "momentum_physical_error_num", "momentum_physical_error_den",
    ),
    "covariance.csv": (
        "kind", "scope", "precision", "level", "dt_raw", "sample", "baseline_hash",
        "transformed_hash", "bit_identical", "relative_position_raw_num",
        "relative_position_raw_den", "relative_position_physical_num",
        "relative_position_physical_den", "relative_momentum_raw_num",
        "relative_momentum_raw_den", "relative_momentum_physical_num",
        "relative_momentum_physical_den",
    ),
    "checkpoint.csv": (
        "scenario_id", "precision", "level", "dt_raw", "steps", "checkpoint_step",
        "checkpoint_hash", "checkpoint_bytes", "decoded_hash", "whole_final_hash",
        "resumed_final_hash", "whole_suffix_event_count", "resumed_event_count",
        "whole_suffix_event_sha256", "resumed_event_sha256", "event_suffix_identical",
        "canonical_round_trip",
    ),
    "domain.csv": (
        "scenario_id", "precision", "level", "status", "prior_hash", "returned_hash",
        "time_unchanged", "state_unchanged", "event_rows_emitted", "energy_ledger_present",
        "observer_events_emitted", "prior_energy_observation_sha256",
        "returned_energy_observation_sha256", "energy_observation_unchanged",
        "offending_relation_index", "chord_minimum_case", "comparison_lhs_num",
        "comparison_lhs_den", "comparison_rhs_num", "comparison_rhs_den",
        "domain_scratch_observed_bits", "domain_scratch_limit_bits",
    ),
    "state_size.csv": (
        "trajectory_id", "precision", "level", "step", "label", "packet_count",
        "component_bytes", "phase_bytes_per_packet", "complete_packet_bytes", "state_bytes",
        "state_hash", "causal_cache_bytes", "causal_history_bytes",
    ),
    "operation_counts.csv": (
        "trajectory_id", "precision", "level", "path", "packet_count", "relation_count",
        "completed_steps", "per_step_expected", "expected_categories", "observed_categories",
        "inexact_categories", "inexact_total", "exact_total", "rounding_audit_records",
        "rounding_audit_sha256", "categories_passed", "total_expected", "total_observed",
        "passed",
    ),
    "rational_comparator.csv": (
        "scenario_id", "scope", "path", "level", "dt_raw", "requested_steps",
        "completed_steps", "comparison_samples", "status", "first_crossing_step",
        "last_within_ceiling_step", "last_comparator_sample",
        "first_comparator_free_sample", "last_comparator_time_raw",
        "last_comparator_state_hash", "maximum_component_bits",
        "maximum_state_median_bits_num", "maximum_state_median_bits_den",
        "maximum_checkpoint_bytes", "crossing_component_bits",
        "crossing_state_median_bits_num", "crossing_state_median_bits_den",
        "crossing_checkpoint_bytes", "maximum_component_bits_limit",
        "median_component_bits_limit", "maximum_checkpoint_bytes_limit",
        "crossing_state_included",
    ),
}


class OracleError(RuntimeError):
    """Evidence violates a frozen verifier contract."""


class ExponentRangeError(OracleError):
    """An exact nonzero result cannot be represented in the frozen range."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OracleError(message)


def progress(stage: str) -> None:
    """Emit deterministic, non-scientific liveness markers for long replays."""
    print(f"[bounded-phase oracle] {stage}", flush=True)


def boolean(value: str) -> bool:
    require(value in {"true", "false"}, f"invalid boolean {value!r}")
    return value == "true"


def decimal_integer(value: str, *, unsigned: bool = False) -> int:
    pattern = UNSIGNED_DECIMAL if unsigned else SIGNED_DECIMAL
    require(pattern.fullmatch(value) is not None, f"noncanonical decimal integer {value!r}")
    return int(value)


def ratio(value: str) -> Fraction:
    numerator, separator, denominator = value.partition("/")
    require(separator == "/", f"invalid rational {value!r}")
    raw_numerator = decimal_integer(numerator)
    raw_denominator = decimal_integer(denominator, unsigned=True)
    require(raw_denominator > 0, "nonpositive rational denominator")
    parsed = Fraction(raw_numerator, raw_denominator)
    require(parsed.numerator == raw_numerator and parsed.denominator == raw_denominator,
            "rational is not reduced")
    return parsed


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def iter_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        yield from csv.DictReader(stream)


def metadata(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows(path):
        require(row["key"] not in result, "duplicate metadata key")
        result[row["key"]] = row["value"]
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def grouped(values: Iterable[dict[str, str]], fields: Sequence[str]) -> dict[tuple[str, ...], list[dict[str, str]]]:
    result: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in values:
        result[tuple(row[field] for field in fields)].append(row)
    return dict(result)


def representation_identity_key(row: dict[str, str]) -> tuple[str, ...]:
    for field in ("precision", "level", "dt_raw", "sample"):
        decimal_integer(row[field], unsigned=True)
    return tuple(row[field] for field in REPRESENTATION_ERROR_IDENTITY_FIELDS[:7])


def verify_representation_error_inventory(raw: Path) -> dict[str, int]:
    """Require the producer's complete, unique, global row sequence."""
    evidence = rows(raw / "representation_error.csv")
    comparator_evidence = rows(raw / "rational_comparator.csv")
    actual_comparators = [
        (row["scenario_id"], row["level"]) for row in comparator_evidence
    ]
    expected_comparator_sequence = [
        (scenario, str(level))
        for level in LEVELS for scenario in ("k4_internal", "k4_boosted")
    ]
    require(actual_comparators == expected_comparator_sequence,
            "representation comparator global order differs")
    comparator_rows = {
        (row["scenario_id"], row["level"]): row for row in comparator_evidence
    }
    require(len(comparator_rows) == len(comparator_evidence),
            "duplicate rational-comparator identity")
    require(set(comparator_rows) == set(expected_comparator_sequence),
            "representation comparator inventory differs")

    expected: list[tuple[str, ...]] = []
    for level in LEVELS:
        # The producer completes all short comparisons for one timestep level,
        # then appends that level's exact-rational long prefixes before moving
        # to the next level.  Bind that actual causal materialization order.
        for scenario in SCENARIOS:
            for path in (CONTROL, KDK):
                for precision in PRECISIONS:
                    for sample in range(STEP_COUNTS[level] + 1):
                        expected.append((
                            scenario, "short", path, str(precision), str(level),
                            str(TIMESTEPS_RAW[level]), str(sample),
                        ))
        for precision in PRECISIONS:
            for scenario in ("k4_internal", "k4_boosted"):
                completed = decimal_integer(
                    comparator_rows[(scenario, str(level))]["completed_steps"],
                    unsigned=True,
                )
                require(completed <= 16 * STEP_COUNTS[level],
                        "representation comparator prefix exceeds requested horizon")
                for sample in range(completed + 1):
                    expected.append((
                        scenario, "long_exact_prefix", KDK, str(precision), str(level),
                        str(TIMESTEPS_RAW[level]), str(sample),
                    ))

    actual = [representation_identity_key(row) for row in evidence]
    require(actual == expected,
            "representation-error global order/key inventory differs")
    require(len(set(actual)) == len(actual),
            "duplicate representation-error identity")
    for row in evidence:
        require(SHA256.fullmatch(row["candidate_state_hash"]) is not None,
                "representation candidate state hash is malformed")
        require(SHA256.fullmatch(row["control_state_hash"]) is not None,
                "representation control state hash is malformed")
        require(SHA256.fullmatch(row["exact_errors_sha256"]) is not None,
                "representation exact-error commitment is malformed")
        for metric in REPRESENTATION_ERROR_METRICS:
            display = row[f"{metric}_display"]
            require(display and len(display.encode("ascii")) <= REPRESENTATION_ERROR_DISPLAY_MAX_BYTES,
                    f"representation {metric} display is absent or oversized")
    short_count = sum(row["scope"] == "short" for row in evidence)
    return {"rows": len(evidence), "short_rows": short_count,
            "long_rows": len(evidence) - short_count}


def float_from_bits(value: str | int) -> float:
    return struct.unpack(">d", struct.pack(">Q", int(value)))[0]


def exact_float_bits(value: str | int) -> Fraction:
    decoded = float_from_bits(value)
    require(math.isfinite(decoded), "nonfinite binary64 evidence")
    return Fraction(*decoded.as_integer_ratio())


def power_of_two(exponent: int) -> Fraction:
    return Fraction(2**exponent) if exponent >= 0 else Fraction(1, 2 ** (-exponent))


def leading_exponent(value: Fraction) -> int:
    """Return floor(log2(abs(value))) using integer comparisons only."""
    require(value != 0, "zero has no leading exponent")
    magnitude = abs(value)
    exponent = magnitude.numerator.bit_length() - magnitude.denominator.bit_length()
    if magnitude < power_of_two(exponent):
        exponent -= 1
    require(power_of_two(exponent) <= magnitude < power_of_two(exponent + 1),
            "leading exponent derivation failed")
    return exponent


def nearest_even_integer(value: Fraction) -> int:
    """Round a nonnegative rational to nearest integer, ties to even."""
    require(value >= 0, "nearest-even helper received a negative value")
    quotient, remainder = divmod(value.numerator, value.denominator)
    comparison = 2 * remainder - value.denominator
    return quotient + int(comparison > 0 or (comparison == 0 and quotient % 2 == 1))


@dataclass(frozen=True)
class Dyadic:
    sign: int
    precision: int
    exponent: int
    significand: int

    def validate(self) -> None:
        require(self.sign in (0, 1), "dyadic sign differs")
        require(self.precision in PRECISIONS, "dyadic precision differs")
        require(self.precision % 8 == 0, "dyadic precision is not byte aligned")
        if self.significand == 0:
            require(self.sign == 0 and self.exponent == 0,
                    "zero is not canonical positive zero")
            return
        require(MIN_EXPONENT <= self.exponent <= MAX_EXPONENT,
                "dyadic leading exponent outside frozen range")
        require(2 ** (self.precision - 1) <= self.significand < 2**self.precision,
                "dyadic significand is not normalized to declared precision")

    def fraction(self) -> Fraction:
        self.validate()
        if self.significand == 0:
            return Fraction()
        value = Fraction(self.significand) * power_of_two(
            self.exponent - (self.precision - 1)
        )
        return -value if self.sign else value

    def encode(self) -> bytes:
        self.validate()
        return (
            bytes((self.sign,))
            + self.precision.to_bytes(2, "little")
            + self.exponent.to_bytes(2, "little", signed=True)
            + self.significand.to_bytes(self.precision // 8, "big")
        )

    @classmethod
    def from_row(cls, row: dict[str, str], prefix: str) -> "Dyadic":
        text = row[f"{prefix}_significand_hex"]
        precision = decimal_integer(row["precision"], unsigned=True)
        require(
            len(text) == precision // 4
            and text == text.lower()
            and re.fullmatch(r"[0-9a-f]+", text) is not None,
            "noncanonical textual significand",
        )
        try:
            significand = int(text, 16)
        except ValueError as error:
            raise OracleError("invalid dyadic significand") from error
        result = cls(
            decimal_integer(row[f"{prefix}_sign"], unsigned=True),
            precision,
            decimal_integer(row[f"{prefix}_E"]),
            significand,
        )
        result.validate()
        wire_text = row[f"{prefix}_wire_hex"]
        require(
            len(wire_text) == 2 * (5 + precision // 8)
            and wire_text == wire_text.lower()
            and re.fullmatch(r"[0-9a-f]+", wire_text) is not None,
            "noncanonical component wire text",
        )
        require(result.encode().hex() == wire_text, "component wire differs")
        exact_numerator = decimal_integer(row[f"{prefix}_exact_num"])
        exact_denominator = decimal_integer(row[f"{prefix}_exact_den"], unsigned=True)
        require(exact_denominator > 0, "component exact denominator is not positive")
        exact = Fraction(exact_numerator, exact_denominator)
        require(
            exact.numerator == exact_numerator and exact.denominator == exact_denominator,
            "component exact rational is not reduced",
        )
        require(result.fraction() == exact, "component exact value differs from wire")
        return result


def round_dyadic(value: Fraction, precision: int) -> Dyadic:
    """Correctly round an exact rational to the frozen binary profile."""
    require(precision in PRECISIONS, "unregistered rounding precision")
    if value == 0:
        return Dyadic(0, precision, 0, 0)
    exponent = leading_exponent(value)
    if exponent < MIN_EXPONENT or exponent > MAX_EXPONENT:
        raise ExponentRangeError("exact result is outside frozen exponent range")
    scaled = abs(value) / power_of_two(exponent - (precision - 1))
    significand = nearest_even_integer(scaled)
    if significand == 2**precision:
        significand //= 2
        exponent += 1
    if exponent < MIN_EXPONENT or exponent > MAX_EXPONENT:
        raise ExponentRangeError("rounded result is outside frozen exponent range")
    result = Dyadic(int(value < 0), precision, exponent, significand)
    result.validate()
    return result


def half_ulp(value: Fraction, precision: int) -> Fraction:
    require(value != 0, "zero result has no normal half-ULP")
    return power_of_two(leading_exponent(value) - precision)


def rounded_fraction(value: Fraction, precision: int) -> Fraction:
    return round_dyadic(value, precision).fraction()


def vector_add(first: Sequence[Fraction], second: Sequence[Fraction]) -> tuple[Fraction, Fraction, Fraction]:
    return tuple(first[index] + second[index] for index in range(3))  # type: ignore[return-value]


def vector_sub(first: Sequence[Fraction], second: Sequence[Fraction]) -> tuple[Fraction, Fraction, Fraction]:
    return tuple(first[index] - second[index] for index in range(3))  # type: ignore[return-value]


def vector_scale(factor: Fraction, value: Sequence[Fraction]) -> tuple[Fraction, Fraction, Fraction]:
    return tuple(factor * value[index] for index in range(3))  # type: ignore[return-value]


def dot(first: Sequence[Fraction], second: Sequence[Fraction]) -> Fraction:
    return sum((first[index] * second[index] for index in range(3)), Fraction())


def cross(first: Sequence[Fraction], second: Sequence[Fraction]) -> tuple[Fraction, Fraction, Fraction]:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def infinity_norm(value: Sequence[Fraction]) -> Fraction:
    return max((abs(component) for component in value), default=Fraction())


def component_round_bound(exact: Fraction, precision: int) -> Fraction:
    return Fraction() if exact == 0 else half_ulp(exact, precision)


def cross_absolute_bound(
    first: Sequence[Fraction], second_bounds: Sequence[Fraction],
) -> tuple[Fraction, Fraction, Fraction]:
    return (
        abs(first[1]) * second_bounds[2] + abs(first[2]) * second_bounds[1],
        abs(first[2]) * second_bounds[0] + abs(first[0]) * second_bounds[2],
        abs(first[0]) * second_bounds[1] + abs(first[1]) * second_bounds[0],
    )


def decimal_value(value: Fraction) -> Decimal:
    return Decimal(value.numerator) / Decimal(value.denominator)


def contains_window(values: Sequence[float], low: float, high: float, count: int) -> bool:
    return any(
        all(low <= value <= high for value in values[start:start + count])
        for start in range(len(values) - count + 1)
    )


def verify_parent_hashes(raw: Path, parent_raw: Path) -> dict[str, object]:
    fingerprint_rows = rows(raw / "parent_fingerprint.csv")
    indexed = {row["file"]: row for row in fingerprint_rows}
    require(len(indexed) == len(fingerprint_rows), "duplicate parent fingerprint row")
    require(set(indexed) == set(PARENT_HASHES), "parent fingerprint inventory differs")
    for filename, expected in PARENT_HASHES.items():
        observed = sha256(parent_raw / filename)
        row = indexed[filename]
        require(
            observed == expected
            and row["sha256"] == expected
            and row["expected_sha256"] == expected
            and boolean(row["passed"]),
            f"stop_inconclusive_or_wrong_parent: {filename}",
        )
    parent_meta = metadata(parent_raw / "metadata.csv")
    require(parent_meta.get("source_sha") == PARENT_SHA, "parent source SHA differs")
    require(parent_meta.get("branch") == "explicit-fractional-phase-state-lab",
            "parent branch differs")
    for filename in ("reference_packets.csv", "relations.csv", "force_operator.csv"):
        require(sha256(raw / filename) == PARENT_HASHES[filename],
                f"frozen parent physics differs: {filename}")
    return {"files": len(PARENT_HASHES), "source_sha": PARENT_SHA}


def verify_schema_metadata_profiles(raw: Path, allow_dirty: bool) -> dict[str, str]:
    require(set(FILES) == set(SCHEMAS), "oracle schema inventory differs")
    actual_files = {path.name for path in raw.iterdir() if path.is_file()}
    require(actual_files == set(FILES), "raw file inventory differs")
    for filename, expected in SCHEMAS.items():
        path = raw / filename
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.reader(stream)
            header = tuple(next(reader))
        require(header == expected, f"{filename}: schema differs")

    meta = metadata(raw / "metadata.csv")
    expected_metadata = {
        "schema": "mls.bounded-fractional-phase-state.raw.v2",
        "accepted_parent_sha": PARENT_SHA,
        "accepted_parent_tag": PARENT_TAG,
        "accepted_parent_tag_object": PARENT_TAG_OBJECT,
        "accepted_parent_archive_sha256": PARENT_ARCHIVE_SHA256,
        "accepted_parent_archive_size": str(PARENT_ARCHIVE_SIZE),
        "branch": BRANCH,
        "candidate": "fixed_precision_variable_exponent_binary_phase_state",
        "gmpy2_version": "2.3.1",
        "mpfr_version": "MPFR 4.2.2",
        "rounding": "round_to_nearest_ties_to_even",
        "leading_exponent_range": "[-16382,16383]",
        "mpfr_context_emin": "-16381",
        "mpfr_context_emax": "16384",
        "subnormalization": "false",
        "adaptive_precision": "false",
        "hidden_residual_or_history": "false",
        "causal_state_shape": CAUSAL_STATE_SHAPE,
        "causal_state_shape_sha256": hashlib.sha256(
            CAUSAL_STATE_SHAPE.encode("utf-8")
        ).hexdigest(),
        "causal_state_slots_only": "true",
        "force_geometry": "cancellation_resistant_binary64",
        "safe_domain": "2^-24",
        "domain_scratch_bit_limit_formula": (
            "4*(B+(leading_exponent_max-leading_exponent_min))+64"
        ),
        "observer_event_encoding": "length_framed_utf8_fields_then_sha256_v2",
        "observer_stream_encoding": "step_framed_ordered_event_sha256_v2",
        "representation_error_commitment_encoding": (
            "identified_exact_fraction_triplet_sha256_v2"
        ),
        "representation_error_display": (
            "nonauthoritative_rn_even_binary64_significand_max_32_bytes"
        ),
        "exact_comparator_maximum_component_bits": "262144",
        "exact_comparator_median_component_bits": "131072",
        "exact_comparator_maximum_checkpoint_bytes": "8388608",
        "promotion": "NO_PROMOTION",
    }
    require(
        set(meta) == set(expected_metadata) | {
            "source_sha", "configured_source_branch", "source_dirty",
        },
        "metadata key inventory differs",
    )
    for key, value in expected_metadata.items():
        require(meta.get(key) == value, f"metadata {key} differs")
    require(SHA1.fullmatch(meta.get("source_sha", "")) is not None, "source SHA malformed")
    require(meta.get("configured_source_branch") in {BRANCH, "HEAD"},
            "configured source branch differs")
    require(allow_dirty or meta.get("source_dirty") == "false",
            "source materialization is dirty")

    profiles = rows(raw / "precisions.csv")
    require([int(row["precision"]) for row in profiles] == list(PRECISIONS),
            "precision inventory or order differs")
    for row, precision in zip(profiles, PRECISIONS):
        require(ratio(row["unit_roundoff"]) == Fraction(1, 2**precision),
                f"B={precision}: unit roundoff differs")
        require(int(row["leading_exponent_min"]) == MIN_EXPONENT
                and int(row["leading_exponent_max"]) == MAX_EXPONENT,
                f"B={precision}: exponent profile differs")
        require(int(row["component_bytes"]) == 5 + precision // 8,
                f"B={precision}: component size differs")
        require(int(row["phase_bytes_per_packet"]) == 6 * (5 + precision // 8),
                f"B={precision}: phase size differs")
        require(int(row["complete_packet_bytes"]) == 16 + 6 * (5 + precision // 8),
                f"B={precision}: packet size differs")
        require(int(row["domain_scratch_bit_limit"]) == domain_scratch_bit_limit(precision),
                f"B={precision}: domain scratch cap differs")
        lq = Dyadic.from_row(row, "lq")
        expected_lq = round_dyadic(LQ, precision)
        require(lq == expected_lq, f"B={precision}: rounded Lq profile differs")
        lq_audit = RoundingAudit()
        rounded_lq = audited_rn(LQ, precision, "profile_Lq", lq_audit)
        require(
            rounded_lq == lq.fraction()
            and boolean(row["lq_conversion_inexact"]) == (rounded_lq != LQ)
            and row["lq_rounding_audit_sha256"] == lq_audit.sha256()
            and lq_audit.total == 1,
            f"B={precision}: Lq conversion audit differs",
        )
        require(row["rounding"] == "round_to_nearest_ties_to_even",
                f"B={precision}: rounding differs")

    units = rows(raw / "units.csv")
    require(len(units) == 1, "unit row count differs")
    unit = units[0]
    for name, expected in (
        ("Lq", LQ), ("Mq", MQ), ("Tq", TQ), ("Pq", PQ), ("Eq", EQ), ("Fq", FQ),
        ("position_budget", POSITION_BUDGET), ("momentum_budget", MOMENTUM_BUDGET),
        ("angular_centrality_budget", ANGULAR_BUDGET), ("energy_budget", ENERGY_BUDGET),
        ("energy_slope_budget", ENERGY_SLOPE_BUDGET),
    ):
        require(ratio(unit[name]) == expected, f"unit/budget {name} differs")
    require(PQ == MQ * LQ / TQ and EQ == PQ * PQ / MQ and FQ * TQ == PQ,
            "coherent unit identities fail")
    return meta


def verify_positive_control_rows(raw: Path, parent_raw: Path) -> dict[str, object]:
    evidence = rows(raw / "positive_control.csv")
    require(evidence and all(boolean(row["passed"]) for row in evidence),
            "declared positive control failed")
    indexed = {row["check"]: row for row in evidence}
    require(len(indexed) == len(evidence), "duplicate positive-control check")
    base = {
        "exact_momentum_and_angular", "exact_relation_centrality",
        "exact_signed_time_recovery", "exact_registered_covariance",
        "atomic_domain_rejection", "complexity_crossing_fingerprint",
    }
    expected_hashes = {
        (row["scenario_id"], row["path"], int(row["level"])): row["state_hash"]
        for row in rows(parent_raw / "endpoints.csv")
    }
    endpoint_checks = {
        f"endpoint:{scenario}:{path}:L{level}"
        for scenario, path, level in expected_hashes
    }
    require(set(indexed) == base | endpoint_checks,
            "positive-control inventory differs")
    require(all(indexed[name]["detail"] == "sealed_raw" for name in base),
            "positive-control sealed detail differs")
    for (scenario, path, level), expected_hash in expected_hashes.items():
        check = indexed[f"endpoint:{scenario}:{path}:L{level}"]
        require(check["detail"] == expected_hash,
                "positive-control endpoint hash differs")
    return {"rows": len(evidence), "all_declared_passed": True}


def load_smooth_problem(
    parent_raw: Path,
) -> tuple[
    dict[str, foundation.Model],
    dict[str, tuple[str, list[list[Decimal]], list[list[Decimal]]]],
]:
    """Reconstruct the inherited smooth problem without candidate helpers."""
    reference = grouped(rows(parent_raw / "reference_packets.csv"), ("model_id", "level"))
    relation_rows = grouped(rows(parent_raw / "relations.csv"), ("model_id",))
    operator_rows = grouped(rows(parent_raw / "force_operator.csv"), ("model_id",))
    model_ids = {key[0] for key in relation_rows}
    require(model_ids == {"k4", "k4_translated", "k4_rotated", "octahedron", "pair"},
            "parent model inventory differs")
    models: dict[str, foundation.Model] = {}
    for model_id in sorted(model_ids):
        packets = sorted(reference[(model_id, "0")], key=lambda row: int(row["packet_id"]))
        identifiers = [int(row["packet_id"]) for row in packets]
        positions = [
            [decimal_value(Fraction(int(row[f"{axis}_raw"])) * LQ) for axis in "xyz"]
            for row in packets
        ]
        masses = [decimal_value(Fraction(int(row["mass_raw"])) * MQ) for row in packets]
        relations = sorted(
            relation_rows[(model_id,)], key=lambda row: int(row["relation_index"])
        )
        edges = [(int(row["first_id"]), int(row["second_id"])) for row in relations]
        h = [[Decimal() for _ in edges] for _ in edges]
        for row in operator_rows[(model_id,)]:
            h[int(row["row"])][int(row["column"])] = decimal_value(
                exact_float_bits(row["h_bits"])
            )
        model = foundation.Model(identifiers, masses, positions, edges, h)
        expected_h = foundation.expected_local_collective_h(model)
        require(
            all(
                abs(h[i][j] - expected_h[i][j]) <= Decimal("5e-15")
                for i in range(len(edges)) for j in range(len(edges))
            ),
            f"{model_id}: inherited force operator differs",
        )
        models[model_id] = model

    initial_grouped = grouped(rows(parent_raw / "initial_states.csv"), ("scenario_id",))
    initial: dict[str, tuple[str, list[list[Decimal]], list[list[Decimal]]]] = {}
    for scenario in SCENARIOS:
        packet_rows = sorted(initial_grouped[(scenario,)], key=lambda row: int(row["packet_id"]))
        require(packet_rows, f"{scenario}: parent initial state missing")
        initial[scenario] = (
            packet_rows[0]["model_id"],
            [
                [decimal_value(parent.component(row, "x", axis) * LQ) for axis in "xyz"]
                for row in packet_rows
            ],
            [
                [decimal_value(parent.component(row, "p", axis) * PQ) for axis in "xyz"]
                for row in packet_rows
            ],
        )
    return models, initial


def rk4_sampled(
    model: foundation.Model, initial: list[Decimal], steps: int,
    sample_count: int = 256,
) -> list[list[Decimal]]:
    """Independent fixed-step RK4 trace on the registered one-second horizon."""
    require(steps % sample_count == 0, "smooth RK4 grid does not contain sample grid")
    stride = steps // sample_count
    h = Decimal(1) / steps
    half = h / 2
    sixth = h / 6
    state = list(initial)
    samples = [list(state)]
    for step in range(1, steps + 1):
        k1 = foundation.derivative(model, state)
        k2 = foundation.derivative(
            model, [state[index] + half * k1[index] for index in range(len(state))]
        )
        k3 = foundation.derivative(
            model, [state[index] + half * k2[index] for index in range(len(state))]
        )
        k4 = foundation.derivative(
            model, [state[index] + h * k3[index] for index in range(len(state))]
        )
        state = [
            state[index]
            + sixth * (k1[index] + 2 * k2[index] + 2 * k3[index] + k4[index])
            for index in range(len(state))
        ]
        if step % stride == 0:
            samples.append(list(state))
    require(len(samples) == sample_count + 1, "smooth RK4 sample inventory differs")
    return samples


def extrapolated_rk4_sampled(
    model: foundation.Model, initial: list[Decimal], base: int = 256,
    levels: int = 6,
) -> tuple[list[list[Decimal]], list[list[Decimal]]]:
    require(levels >= 2, "sampled Richardson table is too shallow")
    tables: list[list[list[list[Decimal]]]] = []
    for level in range(levels):
        tables.append([rk4_sampled(model, initial, base * 2**level)])
        for column in range(1, level + 1):
            exponent = 4 + column - 1
            denominator = Decimal(2) ** exponent - 1
            previous = tables[level][column - 1]
            coarser = tables[level - 1][column - 1]
            tables[level].append([
                [
                    previous[sample][index]
                    + (previous[sample][index] - coarser[sample][index]) / denominator
                    for index in range(len(previous[sample]))
                ]
                for sample in range(len(previous))
            ])
    return tables[-2][-1], tables[-1][-1]


def smooth_oracle_with_samples(
    models: dict[str, foundation.Model],
    initial_states: dict[str, tuple[str, list[list[Decimal]], list[list[Decimal]]]],
) -> tuple[
    dict[str, list[Decimal]], dict[str, Decimal], dict[str, list[list[Decimal]]]
]:
    endpoints: dict[str, list[Decimal]] = {}
    refinements: dict[str, Decimal] = {}
    traces: dict[str, list[list[Decimal]]] = {}
    for scenario in SCENARIOS:
        model_id, position, momentum = initial_states[scenario]
        model = models[model_id]
        initial = [value for vector in position for value in vector]
        initial.extend(value for vector in momentum for value in vector)
        coarse_trace, trace = extrapolated_rk4_sampled(model, initial)
        accepted_endpoint = foundation.extrapolated_rk4(model, initial, 256, 6)
        require(trace[-1] == accepted_endpoint,
                f"{scenario}: sampled smooth endpoint differs from accepted oracle")
        difference = max(
            foundation.state_norm_difference(coarse, fine, len(model.packet_ids))
            for coarse, fine in zip(coarse_trace, trace)
        )
        require(difference <= Decimal(2) ** -70,
                f"{scenario}: sampled smooth-oracle refinement failed")
        endpoints[scenario] = trace[-1]
        refinements[scenario] = difference
        traces[scenario] = trace
    return endpoints, refinements, traces


def verify_positive_parent(
    parent_raw: Path,
    smooth_data: tuple[dict[str, list[Decimal]], dict[str, Decimal]],
) -> dict[str, object]:
    parent.verify_schema_and_metadata(parent_raw, True)
    endpoints, endpoint_invariants = parent.verify_states(parent_raw)
    smooth, _refinements = smooth_data
    convergence, kdk_pass, control_pass = parent.convergence_report(endpoints, smooth)
    accounting, accounting_pass, frame_pass = parent.verify_accounting(parent_raw)
    complexity, complexity_exceeded = parent.complexity_report(parent_raw)
    energy = parent.energy_report(parent_raw)
    obstruction = parent.verify_obstruction(parent_raw)
    crossings = {
        int(key.rsplit("L", 1)[1]): value["first_crossing_step"]
        for key, value in complexity["trajectories"].items()
        if key.startswith("long:k4_internal:L")
    }
    require(crossings == {0: None, 1: 405, 2: 403, 3: 400, 4: 398},
            "parent rational complexity fingerprint differs")
    require(
        endpoint_invariants and kdk_pass and control_pass and accounting_pass and frame_pass
        and complexity_exceeded and energy["short_energy_contracts"] is True,
        "stop_inconclusive_or_wrong_parent: exact-rational positive control differs",
    )
    require(
        accounting == {
            "invariant_stage_rows": 10446,
            "exact_stage_invariants": True,
            "force_relation_rows": 35712,
            "exact_central_kicks": True,
            "reversibility_rows": 15,
            "complete_state_reversible": True,
            "checkpoint_rows": 5,
            "checkpoint_exact": True,
            "domain_rows": 5,
            "domain_atomic": True,
            "covariance_rows": 20,
            "translation_rotation_permutation_exact": True,
        },
        "parent exact accounting fingerprint differs",
    )
    return {
        "decision": PARENT_DECISION,
        "candidate_second_order": all(
            convergence[scenario]["candidate_second_order_window"] for scenario in SCENARIOS
        ),
        "control_first_order": all(
            convergence[scenario]["control_distinguishable"] for scenario in SCENARIOS
        ),
        "exact_momentum_angular_centrality_reversal_frame": True,
        "short_energy_second_order": True,
        "complexity_crossings": crossings,
        "obstruction": obstruction,
    }


COMPONENT_PREFIXES = ("xx", "xy", "xz", "px", "py", "pz")


def encode_state_rows(state_rows: Sequence[dict[str, str]]) -> bytes:
    require(bool(state_rows), "empty canonical state")
    precisions = {decimal_integer(row["precision"], unsigned=True) for row in state_rows}
    times = {decimal_integer(row["time_raw"]) for row in state_rows}
    hashes = {row["state_hash"] for row in state_rows}
    require(len(precisions) == len(times) == len(hashes) == 1,
            "state rows disagree on profile, time, or hash")
    precision = next(iter(precisions))
    require(precision in PRECISIONS, "state precision differs")
    packets = sorted(
        state_rows, key=lambda row: decimal_integer(row["packet_id"], unsigned=True)
    )
    identifiers = [decimal_integer(row["packet_id"], unsigned=True) for row in packets]
    require(len(set(identifiers)) == len(identifiers), "duplicate packet ID")
    output = bytearray(STATE_MAGIC)
    output.extend((1).to_bytes(2, "little"))
    output.extend(precision.to_bytes(2, "little"))
    output.extend(MIN_EXPONENT.to_bytes(2, "little", signed=True))
    output.extend(MAX_EXPONENT.to_bytes(2, "little", signed=True))
    output.extend(next(iter(times)).to_bytes(8, "little", signed=True))
    output.extend(len(packets).to_bytes(8, "little"))
    for identifier, row in zip(identifiers, packets):
        mass = decimal_integer(row["mass_raw"])
        require(0 < identifier < 2**64 and -(2**63) <= mass < 2**63 and mass > 0,
                "packet identity or mass outside wire domain")
        output.extend(identifier.to_bytes(8, "little"))
        output.extend(mass.to_bytes(8, "little", signed=True))
        for prefix in COMPONENT_PREFIXES:
            output.extend(Dyadic.from_row(row, prefix).encode())
    component_bytes = 5 + precision // 8
    expected = len(STATE_MAGIC) + 24 + len(packets) * (16 + 6 * component_bytes)
    require(len(output) == expected, "canonical state byte size differs")
    actual_hash = hashlib.sha256(output).hexdigest()
    require(actual_hash == next(iter(hashes)), "independent canonical state hash differs")
    return bytes(output)


def state_hash_rows(state_rows: Sequence[dict[str, str]]) -> str:
    return hashlib.sha256(encode_state_rows(state_rows)).hexdigest()


def state_values(state_rows: Sequence[dict[str, str]]) -> dict[int, tuple[list[Fraction], list[Fraction]]]:
    result: dict[int, tuple[list[Fraction], list[Fraction]]] = {}
    for row in state_rows:
        identifier = int(row["packet_id"])
        require(identifier not in result, "duplicate packet in decoded state")
        position = [Dyadic.from_row(row, f"x{axis}").fraction() for axis in "xyz"]
        momentum = [Dyadic.from_row(row, f"p{axis}").fraction() for axis in "xyz"]
        result[identifier] = (position, momentum)
    return result


def exact_invariants(
    state_rows: Sequence[dict[str, str]],
) -> tuple[tuple[Fraction, Fraction, Fraction], tuple[Fraction, Fraction, Fraction]]:
    momentum = [Fraction(), Fraction(), Fraction()]
    angular = [Fraction(), Fraction(), Fraction()]
    for position, packet_momentum in state_values(state_rows).values():
        for axis in range(3):
            momentum[axis] += packet_momentum[axis]
        orbital = cross(position, packet_momentum)
        for axis in range(3):
            angular[axis] += orbital[axis]
    return tuple(momentum), tuple(angular)  # type: ignore[return-value]


def physical_state_decimal(state_rows: Sequence[dict[str, str]]) -> list[Decimal]:
    packets = state_values(sorted(state_rows, key=lambda row: int(row["packet_id"])))
    result = [
        decimal_value(component * LQ)
        for identifier in sorted(packets)
        for component in packets[identifier][0]
    ]
    result.extend(
        decimal_value(component * PQ)
        for identifier in sorted(packets)
        for component in packets[identifier][1]
    )
    return result


def raw_component_error(
    first: Sequence[dict[str, str]], second: Sequence[dict[str, str]], momentum: bool,
) -> Fraction:
    left = state_values(first)
    right = state_values(second)
    require(set(left) == set(right), "state comparator packet IDs differ")
    index = 1 if momentum else 0
    return max(
        (
            abs(left[identifier][index][axis] - right[identifier][index][axis])
            for identifier in left for axis in range(3)
        ),
        default=Fraction(),
    )


def encode_unsigned(value: int) -> bytes:
    require(value >= 0, "negative unsigned canonical integer")
    magnitude = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return len(magnitude).to_bytes(8, "little") + magnitude


def encode_signed(value: int) -> bytes:
    return (b"\x01" if value < 0 else b"\x00") + encode_unsigned(abs(value))


def encode_fraction(value: Fraction) -> bytes:
    return encode_signed(value.numerator) + encode_unsigned(value.denominator)


def _length_frame(value: bytes) -> bytes:
    return struct.pack("<Q", len(value)) + value


def _fraction_floor_log2(value: Fraction) -> int:
    require(value > 0, "binary display logarithm requires positive input")
    numerator = value.numerator
    denominator = value.denominator
    exponent = numerator.bit_length() - denominator.bit_length()
    if exponent >= 0:
        if numerator < denominator << exponent:
            exponent -= 1
    elif numerator << -exponent < denominator:
        exponent -= 1
    return exponent


def _round_nonnegative_ratio_ties_even(numerator: int, denominator: int) -> int:
    require(numerator >= 0 and denominator > 0, "invalid binary display ratio")
    quotient, remainder = divmod(numerator, denominator)
    doubled = 2 * remainder
    if doubled > denominator or (doubled == denominator and quotient % 2 == 1):
        quotient += 1
    return quotient


def bounded_fraction_display(value: Fraction) -> str:
    """Independently derive the bounded nonauthoritative RN-even display."""
    if value == 0:
        return "0"
    magnitude = abs(value)
    display_exponent = (
        _fraction_floor_log2(magnitude) - (REPRESENTATION_ERROR_DISPLAY_BITS - 1)
    )
    numerator = magnitude.numerator
    denominator = magnitude.denominator
    if display_exponent >= 0:
        denominator <<= display_exponent
    else:
        numerator <<= -display_exponent
    significand = _round_nonnegative_ratio_ties_even(numerator, denominator)
    if significand == 1 << REPRESENTATION_ERROR_DISPLAY_BITS:
        significand >>= 1
        display_exponent += 1
    require(
        1 << (REPRESENTATION_ERROR_DISPLAY_BITS - 1)
        <= significand < 1 << REPRESENTATION_ERROR_DISPLAY_BITS,
        "binary display normalization failed",
    )
    result = f"{'-' if value < 0 else ''}0x{significand:016x}@{display_exponent:+d}"
    require(
        len(result.encode("ascii")) <= REPRESENTATION_ERROR_DISPLAY_MAX_BYTES,
        "representation error display bound exceeded",
    )
    return result


def representation_error_commitment(
    identity: dict[str, object] | dict[str, str], position_raw_error: Fraction,
    momentum_raw_error: Fraction, energy_error: Fraction,
) -> str:
    """Commit fixed identity and exact errors with an independent encoder."""
    require(position_raw_error >= 0 and momentum_raw_error >= 0,
            "state-error maxima must be nonnegative")
    result = bytearray(REPRESENTATION_ERROR_COMMITMENT_MAGIC)
    result.extend(struct.pack("<Q", len(REPRESENTATION_ERROR_IDENTITY_FIELDS)))
    for field_name in REPRESENTATION_ERROR_IDENTITY_FIELDS:
        require(field_name in identity, f"representation identity omits {field_name}")
        result.extend(_length_frame(field_name.encode("utf-8")))
        result.extend(_length_frame(str(identity[field_name]).encode("utf-8")))
    values = (position_raw_error, momentum_raw_error, energy_error)
    result.extend(struct.pack("<Q", len(REPRESENTATION_ERROR_METRICS)))
    for metric, exact in zip(REPRESENTATION_ERROR_METRICS, values):
        result.extend(_length_frame(metric.encode("utf-8")))
        result.extend(_length_frame(encode_fraction(exact)))
    return hashlib.sha256(result).hexdigest()


def verify_representation_error_row(
    row: dict[str, str], identity: dict[str, object],
    position_raw_error: Fraction, momentum_raw_error: Fraction,
    energy_error: Fraction,
) -> None:
    """Bind a row to its independently replayed exact comparator quantities."""
    for field_name in REPRESENTATION_ERROR_IDENTITY_FIELDS:
        require(row[field_name] == str(identity[field_name]),
                f"representation identity {field_name} differs")
    exact_values = (position_raw_error, momentum_raw_error, energy_error)
    expected_commitment = representation_error_commitment(
        identity, *exact_values
    )
    require(SHA256.fullmatch(row["exact_errors_sha256"]) is not None,
            "representation exact-error commitment is malformed")
    require(row["exact_errors_sha256"] == expected_commitment,
            "representation exact-error commitment differs")
    for metric, exact in zip(REPRESENTATION_ERROR_METRICS, exact_values):
        require(row[f"{metric}_display"] == bounded_fraction_display(exact),
                f"representation {metric} display differs")


def fraction_hash(value: Fraction) -> str:
    return hashlib.sha256(encode_fraction(value)).hexdigest()


def vector_hash(value: Sequence[Fraction]) -> str:
    require(len(value) == 3, "vector hash requires exactly xyz components")
    return hashlib.sha256(b"".join(encode_fraction(item) for item in value)).hexdigest()


@dataclass
class PacketState:
    identifier: int
    mass_raw: int
    x: list[Fraction]
    p: list[Fraction]

    def clone(self) -> "PacketState":
        return PacketState(self.identifier, self.mass_raw, list(self.x), list(self.p))


@dataclass
class PhaseState:
    precision: int
    time_raw: int
    packets: list[PacketState]

    def clone(self) -> "PhaseState":
        return PhaseState(self.precision, self.time_raw, [packet.clone() for packet in self.packets])


@dataclass(frozen=True)
class Relation:
    index: int
    first_id: int
    second_id: int
    rest_length: float


@dataclass
class Model:
    identifier: str
    reference: dict[int, list[Fraction]]
    masses_raw: dict[int, int]
    relations: list[Relation]
    h: list[list[float]]


@dataclass(frozen=True)
class EvaluatedRelation:
    relation: Relation
    offset: tuple[Fraction, Fraction, Fraction]
    length: float
    conjugate: float
    extension: float


@dataclass
class Trajectory:
    status: str
    initial: PhaseState
    final: PhaseState
    completed_steps: int
    samples: list[PhaseState]
    events: list[str]
    operation_count: int
    operation_categories: dict[str, int]
    inexact_categories: dict[str, int]
    inexact_count: int
    rounding_audit_sha256: str


@dataclass
class RationalState:
    time_raw: int
    packets: list[PacketState]

    def clone(self) -> "RationalState":
        return RationalState(self.time_raw, [packet.clone() for packet in self.packets])


@dataclass(frozen=True)
class RationalStateMetrics:
    maximum_component_bits: int
    median_component_bits: Fraction
    checkpoint_bytes: int
    exceeded: bool
    sha256: str


def encode_phase_state(state: PhaseState) -> bytes:
    require(state.precision in PRECISIONS, "phase-state precision differs")
    packets = sorted(state.packets, key=lambda packet: packet.identifier)
    require(len({packet.identifier for packet in packets}) == len(packets),
            "duplicate phase-state packet ID")
    output = bytearray(STATE_MAGIC)
    output.extend((1).to_bytes(2, "little"))
    output.extend(state.precision.to_bytes(2, "little"))
    output.extend(MIN_EXPONENT.to_bytes(2, "little", signed=True))
    output.extend(MAX_EXPONENT.to_bytes(2, "little", signed=True))
    output.extend(state.time_raw.to_bytes(8, "little", signed=True))
    output.extend(len(packets).to_bytes(8, "little"))
    for packet in packets:
        require(0 < packet.identifier < 2**64 and 0 < packet.mass_raw < 2**63,
                "phase-state packet identity differs")
        output.extend(packet.identifier.to_bytes(8, "little"))
        output.extend(packet.mass_raw.to_bytes(8, "little", signed=True))
        for value in packet.x + packet.p:
            rounded = round_dyadic(value, state.precision)
            require(rounded.fraction() == value, "phase-state value is not precision-B dyadic")
            output.extend(rounded.encode())
    return bytes(output)


def phase_hash(state: PhaseState) -> str:
    return hashlib.sha256(encode_phase_state(state)).hexdigest()


def split_rational_component(value: Fraction) -> tuple[int, Fraction]:
    shifted = value + Fraction(1, 2)
    coarse = shifted.numerator // shifted.denominator
    residual = value - coarse
    require(-(2**63) <= coarse < 2**63 and Fraction(-1, 2) <= residual < Fraction(1, 2),
            "rational control state is not canonically representable")
    return coarse, residual


def _encode_rational_state_with_bits(
    state: RationalState,
) -> tuple[bytes, list[int]]:
    output = bytearray(b"MLS-FRACTIONAL-PHASE-v1\x00")
    bit_lengths: list[int] = []
    output.extend(encode_signed(state.time_raw))
    packets = sorted(state.packets, key=lambda packet: packet.identifier)
    output.extend(len(packets).to_bytes(8, "little"))
    for packet in packets:
        output.extend(packet.identifier.to_bytes(8, "little"))
        output.extend(packet.mass_raw.to_bytes(8, "little", signed=True))
        for value in packet.x + packet.p:
            coarse, residual = split_rational_component(value)
            bit_lengths.extend((
                abs(residual.numerator).bit_length(),
                residual.denominator.bit_length(),
            ))
            output.extend(coarse.to_bytes(8, "little", signed=True))
            output.extend(encode_fraction(residual))
    return bytes(output), bit_lengths


def encode_rational_state(state: RationalState) -> bytes:
    return _encode_rational_state_with_bits(state)[0]


def rational_hash(state: RationalState) -> str:
    return hashlib.sha256(encode_rational_state(state)).hexdigest()


def rational_state_metrics(state: RationalState) -> RationalStateMetrics:
    """Measure all canonical exact-state commitments from one encoding pass."""
    encoded, bit_lengths = _encode_rational_state_with_bits(state)
    maximum = max(bit_lengths, default=0)
    ordered = sorted(bit_lengths)
    if not ordered:
        median = Fraction()
    elif len(ordered) % 2:
        median = Fraction(ordered[len(ordered) // 2])
    else:
        center = len(ordered) // 2
        median = Fraction(ordered[center - 1] + ordered[center], 2)
    checkpoint_bytes = len(encoded)
    exceeded = (
        maximum > EXACT_MAX_COMPONENT_BITS
        or median > EXACT_MEDIAN_COMPONENT_BITS
        or checkpoint_bytes > EXACT_MAX_CHECKPOINT_BYTES
    )
    return RationalStateMetrics(
        maximum,
        median,
        checkpoint_bytes,
        exceeded,
        hashlib.sha256(encoded).hexdigest(),
    )


def rational_complexity(state: RationalState) -> tuple[int, Fraction, int, bool]:
    """Independently measure the frozen exact-comparator complexity ceilings."""
    metrics = rational_state_metrics(state)
    return (
        metrics.maximum_component_bits,
        metrics.median_component_bits,
        metrics.checkpoint_bytes,
        metrics.exceeded,
    )


def phase_from_rows(state_rows_: Sequence[dict[str, str]]) -> PhaseState:
    encode_state_rows(state_rows_)
    precision = int(state_rows_[0]["precision"])
    packets: list[PacketState] = []
    for row in sorted(state_rows_, key=lambda item: int(item["packet_id"])):
        packets.append(PacketState(
            int(row["packet_id"]), int(row["mass_raw"]),
            [Dyadic.from_row(row, f"x{axis}").fraction() for axis in "xyz"],
            [Dyadic.from_row(row, f"p{axis}").fraction() for axis in "xyz"],
        ))
    result = PhaseState(precision, int(state_rows_[0]["time_raw"]), packets)
    require(encode_phase_state(result) == encode_state_rows(state_rows_),
            "decoded state does not reproduce canonical bytes")
    return result


def packet_lookup(state: PhaseState) -> dict[int, PacketState]:
    result = {packet.identifier: packet for packet in state.packets}
    require(len(result) == len(state.packets), "duplicate packet lookup ID")
    return result


def load_models(raw: Path) -> dict[str, Model]:
    reference = grouped(rows(raw / "reference_packets.csv"), ("model_id", "level"))
    relations = grouped(rows(raw / "relations.csv"), ("model_id",))
    operators = grouped(rows(raw / "force_operator.csv"), ("model_id",))
    model_ids = {key[0] for key in relations}
    result: dict[str, Model] = {}
    for model_id in sorted(model_ids):
        packet_rows = sorted(reference[(model_id, "0")], key=lambda row: int(row["packet_id"]))
        reference_map = {
            int(row["packet_id"]): [Fraction(int(row[f"{axis}_raw"])) for axis in "xyz"]
            for row in packet_rows
        }
        masses = {int(row["packet_id"]): int(row["mass_raw"]) for row in packet_rows}
        relation_values = [
            Relation(
                int(row["relation_index"]), int(row["first_id"]), int(row["second_id"]),
                float_from_bits(row["rest_length_bits"]),
            )
            for row in sorted(relations[(model_id,)], key=lambda row: int(row["relation_index"]))
        ]
        require([relation.index for relation in relation_values] == list(range(len(relation_values))),
                f"{model_id}: relation indices differ")
        h = [[0.0 for _ in relation_values] for _ in relation_values]
        for row in operators[(model_id,)]:
            h[int(row["row"])][int(row["column"])] = float_from_bits(row["h_bits"])
        result[model_id] = Model(model_id, reference_map, masses, relation_values, h)
    return result


def reference_offset(model: Model, relation: Relation) -> tuple[Fraction, Fraction, Fraction]:
    return vector_sub(model.reference[relation.second_id], model.reference[relation.first_id])


def exact_stored_relation_offset(
    state: PhaseState, relation: Relation,
) -> tuple[Fraction, Fraction, Fraction]:
    """Subtract authoritative stored dyadics exactly for domain certification."""
    packets = packet_lookup(state)
    return vector_sub(packets[relation.second_id].x, packets[relation.first_id].x)


stored_relation_offset = exact_stored_relation_offset


def domain_scratch_bit_limit(precision: int) -> int:
    require(precision in PRECISIONS, "unregistered domain scratch precision")
    return 4 * (precision + MAX_EXPONENT - MIN_EXPONENT) + DOMAIN_SCRATCH_PADDING_BITS


@dataclass
class DomainScratch:
    """Independent fail-closed ledger for exact-integer chord arithmetic."""

    precision: int
    observed_bits: int = 0

    @property
    def limit_bits(self) -> int:
        return domain_scratch_bit_limit(self.precision)

    @staticmethod
    def width(value: int) -> int:
        return abs(value).bit_length()

    def reserve(self, bits: int) -> None:
        require(bits >= 0, "negative domain scratch width")
        self.observed_bits = max(self.observed_bits, bits)
        require(bits <= self.limit_bits, "domain_scratch_bound_exceeded")

    def observe(self, value: int) -> int:
        self.reserve(self.width(value))
        return value

    def add(self, first: int, second: int) -> int:
        if first == 0:
            return self.observe(second)
        if second == 0:
            return self.observe(first)
        self.reserve(max(self.width(first), self.width(second)) + 1)
        return self.observe(first + second)

    def subtract(self, first: int, second: int) -> int:
        if second == 0:
            return self.observe(first)
        if first == 0:
            return self.observe(-second)
        self.reserve(max(self.width(first), self.width(second)) + 1)
        return self.observe(first - second)

    def multiply(self, first: int, second: int) -> int:
        if first == 0 or second == 0:
            return self.observe(0)
        self.reserve(self.width(first) + self.width(second))
        return self.observe(first * second)

    def shift_left(self, value: int, shift: int) -> int:
        require(shift >= 0, "negative domain scratch shift")
        if value == 0:
            return self.observe(0)
        self.reserve(self.width(value) + shift)
        return self.observe(value << shift)


@dataclass(frozen=True)
class DomainCertificate:
    safe: bool
    minimum_case: str
    lhs: Fraction
    rhs: Fraction
    scratch_observed_bits: int
    scratch_limit_bits: int


def dyadic_integer_term(value: Fraction) -> tuple[int, int]:
    require(value.denominator & (value.denominator - 1) == 0,
            "domain predicate received a nondyadic value")
    if value == 0:
        return 0, 0
    magnitude = abs(value.numerator)
    trailing = (magnitude & -magnitude).bit_length() - 1
    integer = magnitude >> trailing
    if value < 0:
        integer = -integer
    exponent = trailing - (value.denominator.bit_length() - 1)
    return integer, exponent


def aligned_dyadic_integers(
    values: Sequence[Fraction], scratch: DomainScratch,
) -> tuple[list[int], int]:
    terms = [dyadic_integer_term(value) for value in values]
    common_exponent = min((exponent for integer, exponent in terms if integer), default=0)
    result: list[int] = []
    for integer, exponent in terms:
        if integer == 0:
            result.append(scratch.observe(0))
        else:
            shift = exponent - common_exponent
            scratch.reserve(abs(integer).bit_length() + shift)
            result.append(scratch.observe(integer << shift))
    return result, common_exponent


def scratch_dot(
    first: Sequence[int], second: Sequence[int], scratch: DomainScratch,
) -> int:
    require(len(first) == len(second) == 3, "domain vector dimension differs")
    result = 0
    for left, right in zip(first, second):
        result = scratch.add(result, scratch.multiply(left, right))
    return result


def scaled_integer_fraction(value: int, exponent: int) -> Fraction:
    return Fraction(value) * power_of_two(exponent)


def _fraction_square_at_least(value: Fraction, threshold: Fraction) -> bool:
    """Compare ``value^2 >= threshold`` without constructing ``value^2``.

    Exact-Q comparator components can contain hundreds of thousands of bits.
    Cross multiplication preserves the exact rational predicate while avoiding
    a canonical ``Fraction`` square (and its otherwise unnecessary reduction).
    """
    require(threshold >= 0, "negative squared-magnitude threshold")
    return (
        value.numerator * value.numerator * threshold.denominator
        >= threshold.numerator * value.denominator * value.denominator
    )


def _relation_component_safety_witness(
    offset: Sequence[Fraction], threshold: Fraction,
) -> bool:
    """Prove a relation norm safe from one exact Cartesian component."""
    return any(_fraction_square_at_least(component, threshold) for component in offset)


def _chord_component_safety_witness(
    initial: Sequence[Fraction], final: Sequence[Fraction], threshold: Fraction,
) -> bool:
    """Prove a complete affine chord safe from one non-sign-changing component.

    If one component has the same sign at both endpoints, its magnitude along
    the entire straight chord is at least the smaller endpoint magnitude.
    This is only a sufficient witness; callers retain the full exact predicate
    as a fallback whenever no component supplies the proof.
    """
    for first, last in zip(initial, final):
        same_sign = (first >= 0 and last >= 0) or (first <= 0 and last <= 0)
        if same_sign and _fraction_square_at_least(
            min(abs(first), abs(last)), threshold
        ):
            return True
    return False


def bounded_chord_certificate(
    initial: Sequence[Fraction], final: Sequence[Fraction],
    reference: Sequence[Fraction], precision: int,
) -> DomainCertificate:
    require(len(initial) == len(final) == len(reference) == 3,
            "domain vector dimension differs")
    scratch = DomainScratch(precision)
    aligned, common_exponent = aligned_dyadic_integers(
        [*initial, *final, *reference], scratch
    )
    first, last, reference_integer = aligned[:3], aligned[3:6], aligned[6:]
    delta = [scratch.subtract(last[axis], first[axis]) for axis in range(3)]
    dd = scratch_dot(delta, delta, scratch)
    aa = scratch_dot(first, first, scratch)
    ad = scratch_dot(first, delta, scratch)
    reference_squared = scratch_dot(reference_integer, reference_integer, scratch)
    require(reference_squared > 0, "zero reference relation")
    if dd == 0 or ad >= 0:
        comparison_lhs = scratch.shift_left(aa, 48)
        comparison_rhs = scratch.observe(reference_squared)
        lhs = scaled_integer_fraction(aa, 2 * common_exponent)
        rhs = scaled_integer_fraction(reference_squared, 2 * common_exponent - 48)
        minimum_case = "initial"
    elif ad <= -dd:
        final_squared = scratch_dot(last, last, scratch)
        comparison_lhs = scratch.shift_left(final_squared, 48)
        comparison_rhs = scratch.observe(reference_squared)
        lhs = scaled_integer_fraction(final_squared, 2 * common_exponent)
        rhs = scaled_integer_fraction(reference_squared, 2 * common_exponent - 48)
        minimum_case = "final"
    else:
        area_squared = scratch.subtract(
            scratch.multiply(aa, dd), scratch.multiply(ad, ad)
        )
        comparison_lhs = scratch.shift_left(area_squared, 48)
        comparison_rhs = scratch.multiply(reference_squared, dd)
        lhs = scaled_integer_fraction(area_squared, 4 * common_exponent)
        rhs = scaled_integer_fraction(
            reference_squared * dd, 4 * common_exponent - 48
        )
        minimum_case = "interior"
    return DomainCertificate(
        comparison_lhs >= comparison_rhs,
        minimum_case,
        lhs,
        rhs,
        scratch.observed_bits,
        scratch.limit_bits,
    )


def relation_is_safe(
    offset: Sequence[Fraction], reference: Sequence[Fraction],
    precision: int | None = None,
) -> bool:
    if precision is not None:
        return bounded_chord_certificate(offset, offset, reference, precision).safe
    reference_squared = dot(reference, reference)
    if reference_squared <= 0:
        return False
    threshold = SAFE_SQUARED_RATIO * reference_squared
    if _relation_component_safety_witness(offset, threshold):
        return True
    return dot(offset, offset) >= threshold


def chord_is_safe(
    initial: Sequence[Fraction], final: Sequence[Fraction], reference: Sequence[Fraction],
    precision: int | None = None,
) -> bool:
    if precision is not None:
        return bounded_chord_certificate(initial, final, reference, precision).safe
    reference_squared = dot(reference, reference)
    require(reference_squared > 0, "zero reference relation")
    threshold = SAFE_SQUARED_RATIO * reference_squared
    if _chord_component_safety_witness(initial, final, threshold):
        return True
    delta = vector_sub(final, initial)
    dd = dot(delta, delta)
    aa = dot(initial, initial)
    ad = dot(initial, delta)
    if dd == 0 or ad >= 0:
        return aa >= threshold
    if ad <= -dd:
        endpoint = vector_add(initial, delta)
        return dot(endpoint, endpoint) >= threshold
    return aa * dd - ad * ad >= threshold * dd


def _quick_two_sum(larger: float, smaller: float) -> tuple[float, float]:
    total = larger + smaller
    return total, smaller - (total - larger)


def _two_sum(first: float, second: float) -> tuple[float, float]:
    total = first + second
    virtual_second = total - first
    return total, (first - (total - virtual_second)) + (second - virtual_second)


def _two_difference(first: float, second: float) -> tuple[float, float]:
    difference = first - second
    virtual_second = first - difference
    return difference, (first - (difference + virtual_second)) + (virtual_second - second)


def _dd_add(first: tuple[float, float], second: tuple[float, float]) -> tuple[float, float]:
    total = first[0] + second[0]
    virtual_second = total - first[0]
    error = (first[0] - (total - virtual_second)) + (second[0] - virtual_second)
    error += first[1] + second[1]
    return _quick_two_sum(total, error)


def _dd_sub(first: tuple[float, float], second: tuple[float, float]) -> tuple[float, float]:
    return _dd_add(first, (-second[0], -second[1]))


def _dd_mul(first: tuple[float, float], second: tuple[float, float]) -> tuple[float, float]:
    product = first[0] * second[0]
    error = math.fma(first[0], second[0], -product)
    error += first[0] * second[1] + first[1] * second[0] + first[1] * second[1]
    return _quick_two_sum(product, error)


def _dd_div(numerator: tuple[float, float], denominator: tuple[float, float]) -> tuple[float, float]:
    require(denominator[0] != 0.0, "Path-B division by zero")
    quotient = (numerator[0] / denominator[0], 0.0)
    for _ in range(2):
        residual = _dd_sub(numerator, _dd_mul(denominator, quotient))
        quotient = _dd_add(quotient, (residual[0] / denominator[0], 0.0))
    return _quick_two_sum(quotient[0], quotient[1])


def stable_norm(value: Sequence[float]) -> float:
    scale = max(abs(component) for component in value)
    if scale == 0.0:
        return 0.0
    normalized = [component / scale for component in value]
    squared = normalized[0] * normalized[0]
    squared += normalized[1] * normalized[1]
    squared += normalized[2] * normalized[2]
    return scale * math.sqrt(squared)


def path_b_geometry(
    current: Sequence[float], reference: Sequence[float], frozen_reference_length: float,
) -> tuple[float, float]:
    length = stable_norm(current)
    require(length > 0.0 and math.isfinite(length), "force_domain_failure")
    numerator = (0.0, 0.0)
    for axis in range(3):
        numerator = _dd_add(
            numerator,
            _dd_mul(_two_difference(current[axis], reference[axis]),
                    _two_sum(current[axis], reference[axis])),
        )
    denominator = length + frozen_reference_length
    require(denominator > 0.0 and math.isfinite(denominator), "invalid Path-B denominator")
    extension = _dd_div(numerator, (denominator, 0.0))[0]
    require(math.isfinite(extension), "nonfinite Path-B extension")
    return length, extension


def rn(value: Fraction, precision: int) -> Fraction:
    try:
        return round_dyadic(value, precision).fraction()
    except ExponentRangeError as error:
        raise OracleError("phase_range_failure") from error


@dataclass
class RoundingAudit:
    total: int = 0
    categories: dict[str, int] | None = None
    inexact_total: int = 0
    inexact_categories: dict[str, int] | None = None
    _digest: object | None = None

    def __post_init__(self) -> None:
        if self.categories is None:
            self.categories = {}
        if self.inexact_categories is None:
            self.inexact_categories = {}
        if self._digest is None:
            self._digest = hashlib.sha256(ROUNDING_AUDIT_MAGIC)

    def record(
        self, category: str, exact: Fraction, rounded: Fraction,
        error: Fraction, bound: Fraction,
    ) -> None:
        inexact = error != 0
        self.total += 1
        assert self.categories is not None and self.inexact_categories is not None
        self.categories[category] = self.categories.get(category, 0) + 1
        if inexact:
            self.inexact_total += 1
            self.inexact_categories[category] = (
                self.inexact_categories.get(category, 0) + 1
            )
        assert self._digest is not None and hasattr(self._digest, "update")
        self._digest.update(b"L")
        self._digest.update(struct.pack("<Q", self.total))
        for value in (
            category, ratio_text(exact), ratio_text(rounded), ratio_text(error),
            ratio_text(bound), str(inexact).lower(),
        ):
            self._digest.update(_observer_frame(value))

    def merge(self, child: "RoundingAudit") -> None:
        assert self.categories is not None and self.inexact_categories is not None
        assert child.categories is not None and child.inexact_categories is not None
        assert self._digest is not None and hasattr(self._digest, "update")
        self._digest.update(ROUNDING_AUDIT_MERGE_MAGIC)
        self._digest.update(struct.pack("<Q", child.total))
        self._digest.update(bytes.fromhex(child.sha256()))
        self.total += child.total
        self.inexact_total += child.inexact_total
        for name, value in child.categories.items():
            self.categories[name] = self.categories.get(name, 0) + value
        for name, value in child.inexact_categories.items():
            self.inexact_categories[name] = self.inexact_categories.get(name, 0) + value

    def sha256(self) -> str:
        assert self._digest is not None and hasattr(self._digest, "copy")
        return self._digest.copy().hexdigest()


def audited_rn(
    value: Fraction, precision: int, category: str, audit: RoundingAudit,
) -> Fraction:
    try:
        encoded = round_dyadic(value, precision)
    except ExponentRangeError as error:
        raise OracleError("phase_range_failure") from error
    rounded = encoded.fraction()
    error = rounded - value
    bound = Fraction() if value == 0 else power_of_two(encoded.exponent - precision)
    require(abs(error) <= bound, f"{category}: independent half-ULP bound exceeded")
    audit.record(category, value, rounded, error, bound)
    return rounded


def validate_phase_state(state: PhaseState) -> None:
    require(-(2**63) <= state.time_raw < 2**63, "phase-state time outside signed64")
    for packet in state.packets:
        for value in packet.x:
            require(abs(value) < 2**48, "raw position evidence bound exceeded")
            require(rn(value, state.precision) == value, "stored position is not canonical dyadic")
        for value in packet.p:
            require(abs(value) < 2**40, "raw momentum evidence bound exceeded")
            require(rn(value, state.precision) == value, "stored momentum is not canonical dyadic")
    encode_phase_state(state)


def force_and_energy(
    model: Model, state: PhaseState, audit: RoundingAudit | None = None,
) -> tuple[list[EvaluatedRelation], Fraction, int]:
    precision = state.precision
    lq_b = rn(LQ, precision)
    packets = packet_lookup(state)
    geometry: list[tuple[Relation, tuple[Fraction, Fraction, Fraction], float, float]] = []
    start_operations = audit.total if audit is not None else 0
    for relation in model.relations:
        offset = tuple(
            (
                audited_rn(
                    packets[relation.second_id].x[axis]
                    - packets[relation.first_id].x[axis],
                    precision, "relative_subtraction", audit,
                )
                if audit is not None else rn(
                    packets[relation.second_id].x[axis]
                    - packets[relation.first_id].x[axis], precision
                )
            )
            for axis in range(3)
        )
        reference = reference_offset(model, relation)
        stored_offset = exact_stored_relation_offset(state, relation)
        require(
            relation_is_safe(stored_offset, reference, precision),
            "force_domain_failure",
        )
        require(infinity_norm(offset) < 2**49, "raw relation evidence bound exceeded")
        current_si = [
            float(
                audited_rn(
                    component * lq_b, precision, "relative_unit_multiplication", audit
                )
                if audit is not None else rn(component * lq_b, precision)
            )
            for component in offset
        ]
        reference_si = [float(component * LQ) for component in reference]
        length, extension = path_b_geometry(current_si, reference_si, relation.rest_length)
        geometry.append((relation, offset, length, extension))

    conjugates: list[float] = []
    for row_index in range(len(model.relations)):
        value = 0.0
        for column in range(len(model.relations)):
            value += model.h[row_index][column] * geometry[column][3]
        require(math.isfinite(value), "nonfinite accepted force conjugate")
        conjugates.append(value)
    energy_twice = 0.0
    for index, entry in enumerate(geometry):
        energy_twice += entry[3] * conjugates[index]
    require(math.isfinite(energy_twice), "nonfinite accepted potential")
    evaluated = [
        EvaluatedRelation(entry[0], entry[1], entry[2], conjugates[index], entry[3])
        for index, entry in enumerate(geometry)
    ]
    operations = (audit.total - start_operations) if audit is not None else 0
    return evaluated, exact_float_bits(struct.unpack(">Q", struct.pack(">d", 0.5 * energy_twice))[0]), operations


def exact_state_invariants(
    state: PhaseState,
) -> tuple[tuple[Fraction, Fraction, Fraction], tuple[Fraction, Fraction, Fraction]]:
    momentum = [Fraction(), Fraction(), Fraction()]
    angular = [Fraction(), Fraction(), Fraction()]
    for packet in state.packets:
        for axis in range(3):
            momentum[axis] += packet.p[axis]
        value = cross(packet.x, packet.p)
        for axis in range(3):
            angular[axis] += value[axis]
    return tuple(momentum), tuple(angular)  # type: ignore[return-value]


def mechanical_energy(model: Model, state: PhaseState) -> tuple[Fraction, Fraction, Fraction]:
    kinetic = Fraction()
    for packet in state.packets:
        kinetic += dot(packet.p, packet.p) * PQ * PQ / (2 * packet.mass_raw * MQ)
    _relations, potential, _operations = force_and_energy(model, state)
    return kinetic, potential, kinetic + potential


def kick(
    model: Model, state: PhaseState, interval_raw: int,
    audit: RoundingAudit | None = None,
) -> tuple[PhaseState, int, list[dict[str, object]]]:
    precision = state.precision
    local_audit = audit if audit is not None else RoundingAudit()
    start_operations = local_audit.total
    result = state.clone()
    evaluated, _potential, _operations = force_and_energy(model, state, local_audit)
    frozen = packet_lookup(state)
    packets = packet_lookup(result)
    c_kick = audited_rn(
        Fraction(interval_raw) * TQ * LQ / PQ,
        precision, "kick_constant_conversion", local_audit,
    )
    audits: list[dict[str, object]] = []
    for relation_value in evaluated:
        coefficient = audited_rn(c_kick * exact_float_bits(
            struct.unpack(">Q", struct.pack(">d", relation_value.conjugate))[0]
        ), precision, "kick_scalar_multiplication", local_audit)
        alpha = audited_rn(coefficient / exact_float_bits(
            struct.unpack(">Q", struct.pack(">d", relation_value.length))[0]
        ), precision, "kick_length_division", local_audit)
        impulse = tuple(
            audited_rn(
                alpha * component, precision,
                "impulse_component_multiplication", local_audit,
            )
            for component in relation_value.offset
        )
        require(infinity_norm(impulse) < 2**40, "raw impulse evidence bound exceeded")
        relation = relation_value.relation
        first = packets[relation.first_id]
        second = packets[relation.second_id]
        first_before = list(first.p)
        second_before = list(second.p)
        first_exact = [first.p[axis] + impulse[axis] for axis in range(3)]
        second_exact = [second.p[axis] - impulse[axis] for axis in range(3)]
        first.p = [
            audited_rn(value, precision, "endpoint_momentum_accumulation", local_audit)
            for value in first_exact
        ]
        second.p = [
            audited_rn(value, precision, "endpoint_momentum_accumulation", local_audit)
            for value in second_exact
        ]
        first_delta = tuple(first.p[axis] - first_before[axis] for axis in range(3))
        second_delta = tuple(second.p[axis] - second_before[axis] for axis in range(3))
        offset = relation_value.offset
        pair = vector_add(first_delta, second_delta)
        stored_offset = vector_sub(
            frozen[relation.second_id].x, frozen[relation.first_id].x
        )
        stored_centrality = cross(stored_offset, impulse)
        first_centrality = cross(stored_offset, first_delta)
        second_centrality = cross(stored_offset, tuple(-value for value in second_delta))
        relation_angular = vector_add(
            cross(frozen[relation.first_id].x, first_delta),
            cross(frozen[relation.second_id].x, second_delta),
        )
        offset_bounds = [
            component_round_bound(stored_offset[axis], precision) for axis in range(3)
        ]
        impulse_bounds = [
            component_round_bound(alpha * offset[axis], precision) for axis in range(3)
        ]
        direction_error_bounds = [
            abs(alpha) * offset_bounds[axis] + impulse_bounds[axis] for axis in range(3)
        ]
        stored_centrality_bound = cross_absolute_bound(stored_offset, direction_error_bounds)
        first_endpoint_bounds = [component_round_bound(value, precision) for value in first_exact]
        second_endpoint_bounds = [component_round_bound(value, precision) for value in second_exact]
        first_centrality_bound = vector_add(
            stored_centrality_bound, cross_absolute_bound(stored_offset, first_endpoint_bounds)
        )
        second_centrality_bound = vector_add(
            stored_centrality_bound, cross_absolute_bound(stored_offset, second_endpoint_bounds)
        )
        pair_bound = tuple(
            (first_endpoint_bounds[axis] + second_endpoint_bounds[axis]) * PQ
            for axis in range(3)
        )
        angular_endpoint_bound = vector_add(
            cross_absolute_bound(frozen[relation.first_id].x, first_endpoint_bounds),
            cross_absolute_bound(frozen[relation.second_id].x, second_endpoint_bounds),
        )
        angular_bound = vector_scale(
            LQ * PQ, vector_add(stored_centrality_bound, angular_endpoint_bound)
        )
        audits.append({
            "relation": relation,
            # Verifier-only causal values.  These never enter the raw schema;
            # they let paired trajectory certificates propagate each local
            # RN-even source without replaying a third copy of the force map.
            "alpha": alpha,
            "causal_offset": offset,
            "rounded_impulse": impulse,
            "first_actual_impulse": first_delta,
            "second_actual_impulse": second_delta,
            "relative_subtraction_bounds": tuple(offset_bounds),
            "impulse_component_bounds": tuple(impulse_bounds),
            "first_endpoint_bounds": tuple(first_endpoint_bounds),
            "second_endpoint_bounds": tuple(second_endpoint_bounds),
            "length_bits": struct.unpack(">Q", struct.pack(">d", relation_value.length))[0],
            "conjugate_bits": struct.unpack(">Q", struct.pack(">d", relation_value.conjugate))[0],
            "causal_offset_raw_hash": vector_hash(offset),
            "exact_stored_offset_raw_hash": vector_hash(stored_offset),
            "ideal_impulse_raw_hash": vector_hash(impulse),
            "first_actual_impulse_raw_hash": vector_hash(first_delta),
            "second_actual_impulse_raw_hash": vector_hash(second_delta),
            "pair_momentum_residual": vector_scale(PQ, pair),
            "stored_impulse_centrality_residual": vector_scale(LQ * PQ, stored_centrality),
            "first_actual_centrality_residual": vector_scale(LQ * PQ, first_centrality),
            "second_actual_centrality_residual": vector_scale(LQ * PQ, second_centrality),
            "relation_angular_residual": vector_scale(LQ * PQ, relation_angular),
            "pair_momentum_bound": pair_bound,
            "stored_impulse_centrality_bound": vector_scale(LQ * PQ, stored_centrality_bound),
            "first_actual_centrality_bound": vector_scale(LQ * PQ, first_centrality_bound),
            "second_actual_centrality_bound": vector_scale(LQ * PQ, second_centrality_bound),
            "relation_angular_bound": angular_bound,
        })
    validate_phase_state(result)
    return result, local_audit.total - start_operations, audits


def drift(
    model: Model, state: PhaseState, interval_raw: int,
    audit: RoundingAudit | None = None,
) -> tuple[PhaseState, int, tuple[Fraction, Fraction, Fraction]]:
    precision = state.precision
    local_audit = audit if audit is not None else RoundingAudit()
    start_operations = local_audit.total
    result = state.clone()
    initial_offsets = [
        exact_stored_relation_offset(state, relation) for relation in model.relations
    ]
    operations = 0
    angular_bound_raw = [Fraction(), Fraction(), Fraction()]
    for packet in result.packets:
        coefficient = audited_rn(
            Fraction(interval_raw, packet.mass_raw), precision,
            "drift_constant_conversion", local_audit,
        )
        exact_displacement = [coefficient * packet.p[axis] for axis in range(3)]
        displacement = [
            audited_rn(value, precision, "drift_displacement_multiplication", local_audit)
            for value in exact_displacement
        ]
        exact_position = [packet.x[axis] + displacement[axis] for axis in range(3)]
        packet.x = [
            audited_rn(value, precision, "drift_position_accumulation", local_audit)
            for value in exact_position
        ]
        displacement_error_bound = [
            component_round_bound(exact_displacement[axis], precision)
            + component_round_bound(exact_position[axis], precision)
            for axis in range(3)
        ]
        packet_bound = cross_absolute_bound(packet.p, displacement_error_bound)
        angular_bound_raw = list(vector_add(angular_bound_raw, packet_bound))
    for relation, initial in zip(model.relations, initial_offsets):
        final = exact_stored_relation_offset(result, relation)
        require(chord_is_safe(initial, final, reference_offset(model, relation), precision),
                "chord_domain_failure")
    validate_phase_state(result)
    return (
        result, local_audit.total - start_operations,
        vector_scale(LQ * PQ, angular_bound_raw),
    )


def kick_increment_bounds(
    audits: Sequence[dict[str, object]],
) -> tuple[tuple[Fraction, Fraction, Fraction], tuple[Fraction, Fraction, Fraction]]:
    momentum = (Fraction(), Fraction(), Fraction())
    angular = (Fraction(), Fraction(), Fraction())
    for audit in audits:
        pair = audit["pair_momentum_bound"]
        relation = audit["relation_angular_bound"]
        assert isinstance(pair, tuple) and isinstance(relation, tuple)
        momentum = vector_add(momentum, pair)
        angular = vector_add(angular, relation)
    return momentum, angular


PhaseRadii = dict[int, list[Fraction]]
PhaseShift = dict[int, tuple[Fraction, Fraction, Fraction]]
StageTrace = list[tuple[
    int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
    tuple[Fraction, Fraction, Fraction],
]]
ForceTrace = list[tuple[int, str, dict[str, object]]]
AuditReplay = tuple[Trajectory, StageTrace, ForceTrace]

# Once a long-run force row has been independently checked, only these causal
# quantities are consumed by the later frame and bounded-vs-exact recurrence
# certificates. Keeping the raw hashes, residual vectors, and reported bounds
# for every relation would retain several gigabytes of already-verified data at
# the finest registered level.
LONG_FORCE_CERTIFICATE_FIELDS = (
    "relation",
    "alpha",
    "length_bits",
    "conjugate_bits",
    "relative_subtraction_bounds",
    "impulse_component_bounds",
    "first_endpoint_bounds",
    "second_endpoint_bounds",
)


def compact_long_force_trace(values: Sequence[
    tuple[int, str, dict[str, object]]
]) -> ForceTrace:
    """Retain exactly the causal fields needed after long-row verification."""
    result: ForceTrace = []
    for step, stage, audit in values:
        missing = [name for name in LONG_FORCE_CERTIFICATE_FIELDS if name not in audit]
        require(
            not missing,
            f"long force certificate field missing: {missing[0] if missing else ''}",
        )
        compact = {name: audit[name] for name in LONG_FORCE_CERTIFICATE_FIELDS}
        require(
            tuple(compact) == LONG_FORCE_CERTIFICATE_FIELDS,
            "long force certificate field inventory differs",
        )
        result.append((step, stage, compact))
    return result


def inward_certificate_witness(value: Fraction) -> Fraction:
    """Round a nonnegative monotone recurrence downward to a B256 dyadic.

    Every coefficient and source in the radius recurrence is nonnegative, so
    the rounded witness is no greater than the corresponding literal exact
    local-half-ULP recurrence.  It is deliberately *not* assumed to remain an
    upper bound by rounding alone: every generated stage is checked against the
    inward witness, re-establishing the induction hypothesis before the next
    primitive.  Thus a passing check proves residual <= witness <= exact
    recurrence while avoiding unbounded denominator growth.  B256 is the
    frozen maximum registered candidate precision, not a fitted constant.
    """
    require(value >= 0, "negative paired-certificate radius")
    if value == 0:
        return value
    precision = max(PRECISIONS)
    exponent = leading_exponent(value)
    quantum = power_of_two(exponent - (precision - 1))
    scaled = value / quantum
    significand = scaled.numerator // scaled.denominator
    require(2 ** (precision - 1) <= significand < 2**precision,
            "inward certificate significand is not normalized")
    return Fraction(significand) * quantum


def zero_phase_radii(state: PhaseState) -> tuple[PhaseRadii, PhaseRadii]:
    identifiers = {packet.identifier for packet in state.packets}
    require(len(identifiers) == len(state.packets), "duplicate paired-bound packet ID")
    return (
        {identifier: [Fraction(), Fraction(), Fraction()] for identifier in identifiers},
        {identifier: [Fraction(), Fraction(), Fraction()] for identifier in identifiers},
    )


def constant_phase_shift(
    left: PhaseState, right: PhaseState, momentum: bool,
) -> PhaseShift:
    """Recover an exact common affine shift from two registered initial states."""
    left_packets = packet_lookup(left)
    right_packets = packet_lookup(right)
    require(set(left_packets) == set(right_packets), "paired-bound packet IDs differ")
    name = "p" if momentum else "x"
    anchor = min(left_packets)
    shift = tuple(
        getattr(right_packets[anchor], name)[axis]
        - getattr(left_packets[anchor], name)[axis]
        for axis in range(3)
    )
    result: PhaseShift = {}
    for identifier in left_packets:
        candidate = tuple(
            getattr(right_packets[identifier], name)[axis]
            - getattr(left_packets[identifier], name)[axis]
            for axis in range(3)
        )
        require(candidate == shift, "registered frame shift is not common")
        result[identifier] = shift  # type: ignore[assignment]
    return result


def zero_phase_shift(state: PhaseState) -> PhaseShift:
    return {
        packet.identifier: (Fraction(), Fraction(), Fraction())
        for packet in state.packets
    }


def paired_state_containment(
    left: PhaseState, right: PhaseState,
    x_shift: PhaseShift, p_shift: PhaseShift,
    x_radii: PhaseRadii, p_radii: PhaseRadii,
) -> tuple[bool, Fraction, Fraction]:
    """Check every aligned phase component, not only the exported infinity norm."""
    left_packets = packet_lookup(left)
    right_packets = packet_lookup(right)
    require(
        set(left_packets) == set(right_packets)
        == set(x_shift) == set(p_shift) == set(x_radii) == set(p_radii),
        "paired-state certificate inventory differs",
    )
    contained = True
    x_maximum = Fraction()
    p_maximum = Fraction()
    for identifier in left_packets:
        for axis in range(3):
            x_error = abs(
                right_packets[identifier].x[axis]
                - left_packets[identifier].x[axis]
                - x_shift[identifier][axis]
            )
            p_error = abs(
                right_packets[identifier].p[axis]
                - left_packets[identifier].p[axis]
                - p_shift[identifier][axis]
            )
            x_maximum = max(x_maximum, x_error)
            p_maximum = max(p_maximum, p_error)
            contained = (
                contained
                and x_error <= x_radii[identifier][axis]
                and p_error <= p_radii[identifier][axis]
            )
    return contained, x_maximum, p_maximum


def relative_observer_radius(radii: PhaseRadii) -> Fraction:
    """Bound the packet-zero-relative observer used by covariance.csv."""
    anchor = min(radii)
    return max(
        (
            radii[identifier][axis] + radii[anchor][axis]
            for identifier in radii if identifier != anchor for axis in range(3)
        ),
        default=Fraction(),
    )


def grouped_force_trace(
    values: Sequence[tuple[int, str, dict[str, object]]],
) -> dict[tuple[int, str], list[dict[str, object]]]:
    result: dict[tuple[int, str], list[dict[str, object]]] = defaultdict(list)
    for step, stage, value in values:
        result[(step, stage)].append(value)
    return dict(result)


def indexed_stage_trace(
    values: Sequence[tuple[
        int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
        tuple[Fraction, Fraction, Fraction],
    ]],
) -> dict[tuple[int, str], PhaseState]:
    result: dict[tuple[int, str], PhaseState] = {}
    for step, stage, state, _momentum, _angular in values:
        key = (step, stage)
        require(key not in result, "duplicate paired-bound stage")
        result[key] = state
    return result


def propagate_paired_kick_bound(
    left_audits: Sequence[dict[str, object]],
    right_audits: Sequence[dict[str, object]],
    x_radii: PhaseRadii,
    p_radii: PhaseRadii,
    inverse: bool,
) -> tuple[PhaseRadii, bool, int]:
    """Propagate a same-time or signed-inverse frozen-force kick enclosure."""
    if len(left_audits) != len(right_audits):
        return p_radii, False, 0
    result = {identifier: list(value) for identifier, value in p_radii.items()}
    paired = 0
    scalar_sign = -1 if inverse else 1
    for left, right in zip(left_audits, right_audits):
        left_relation = left["relation"]
        right_relation = right["relation"]
        assert isinstance(left_relation, Relation) and isinstance(right_relation, Relation)
        if (
            left_relation != right_relation
            or left["length_bits"] != right["length_bits"]
            or left["conjugate_bits"] != right["conjugate_bits"]
        ):
            return p_radii, False, paired
        left_alpha = left["alpha"]
        right_alpha = right["alpha"]
        assert isinstance(left_alpha, Fraction) and isinstance(right_alpha, Fraction)
        if right_alpha != scalar_sign * left_alpha:
            return p_radii, False, paired
        left_offset = left["relative_subtraction_bounds"]
        right_offset = right["relative_subtraction_bounds"]
        left_impulse = left["impulse_component_bounds"]
        right_impulse = right["impulse_component_bounds"]
        left_first = left["first_endpoint_bounds"]
        right_first = right["first_endpoint_bounds"]
        left_second = left["second_endpoint_bounds"]
        right_second = right["second_endpoint_bounds"]
        assert all(
            isinstance(value, tuple)
            for value in (
                left_offset, right_offset, left_impulse, right_impulse,
                left_first, right_first, left_second, right_second,
            )
        )
        for axis in range(3):
            relation_radius = (
                x_radii[left_relation.first_id][axis]
                + x_radii[left_relation.second_id][axis]
                + left_offset[axis] + right_offset[axis]
            )
            impulse_radius = (
                abs(left_alpha) * relation_radius
                + left_impulse[axis] + right_impulse[axis]
            )
            result[left_relation.first_id][axis] = inward_certificate_witness(
                result[left_relation.first_id][axis]
                + impulse_radius + left_first[axis] + right_first[axis]
            )
            result[left_relation.second_id][axis] = inward_certificate_witness(
                result[left_relation.second_id][axis]
                + impulse_radius + left_second[axis] + right_second[axis]
            )
        paired += 1
    return result, True, paired


def propagate_paired_drift_bound(
    left_before: PhaseState, right_before: PhaseState,
    left_interval_raw: int, right_interval_raw: int,
    x_radii: PhaseRadii, p_radii: PhaseRadii,
    x_shift: PhaseShift, p_shift: PhaseShift,
    inverse: bool,
) -> tuple[PhaseRadii, PhaseShift, bool]:
    """Propagate the exact component recurrence through both RN drift primitives."""
    left_packets = packet_lookup(left_before)
    right_packets = packet_lookup(right_before)
    require(set(left_packets) == set(right_packets), "paired drift packet IDs differ")
    result = {identifier: list(value) for identifier, value in x_radii.items()}
    next_shift: PhaseShift = {}
    expected_sign = -1 if inverse else 1
    for identifier in left_packets:
        left_packet = left_packets[identifier]
        right_packet = right_packets[identifier]
        require(left_packet.mass_raw == right_packet.mass_raw,
                "paired drift mass differs")
        left_coefficient = rn(
            Fraction(left_interval_raw, left_packet.mass_raw), left_before.precision
        )
        right_coefficient = rn(
            Fraction(right_interval_raw, right_packet.mass_raw), right_before.precision
        )
        if right_coefficient != expected_sign * left_coefficient:
            return x_radii, x_shift, False
        if inverse:
            require(
                p_shift[identifier] == (Fraction(), Fraction(), Fraction()),
                "inverse paired drift has a nonzero momentum shift",
            )
            next_shift[identifier] = x_shift[identifier]
        else:
            next_shift[identifier] = tuple(
                x_shift[identifier][axis]
                + left_coefficient * p_shift[identifier][axis]
                for axis in range(3)
            )  # type: ignore[assignment]
        for axis in range(3):
            left_exact_displacement = left_coefficient * left_packet.p[axis]
            right_exact_displacement = right_coefficient * right_packet.p[axis]
            left_displacement = rn(left_exact_displacement, left_before.precision)
            right_displacement = rn(right_exact_displacement, right_before.precision)
            left_exact_position = left_packet.x[axis] + left_displacement
            right_exact_position = right_packet.x[axis] + right_displacement
            result[identifier][axis] = inward_certificate_witness(
                result[identifier][axis]
                + abs(left_coefficient) * p_radii[identifier][axis]
                + component_round_bound(left_exact_displacement, left_before.precision)
                + component_round_bound(right_exact_displacement, right_before.precision)
                + component_round_bound(left_exact_position, left_before.precision)
                + component_round_bound(right_exact_position, right_before.precision)
            )
    return result, next_shift, True


def paired_frame_bound_certificate(
    baseline: Trajectory,
    baseline_stages: Sequence[tuple[
        int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
        tuple[Fraction, Fraction, Fraction],
    ]],
    baseline_forces: Sequence[tuple[int, str, dict[str, object]]],
    transformed: Trajectory,
    transformed_stages: Sequence[tuple[
        int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
        tuple[Fraction, Fraction, Fraction],
    ]],
    transformed_forces: Sequence[tuple[int, str, dict[str, object]]],
    interval_raw: int,
) -> dict[str, object]:
    """Certify translation/boost covariance from paired causal RN sources."""
    require(
        baseline.completed_steps == transformed.completed_steps
        and baseline.initial.precision == transformed.initial.precision,
        "paired frame trajectory profile differs",
    )
    require(baseline.initial.time_raw == transformed.initial.time_raw,
            "paired frame initial time differs")
    x_radii, p_radii = zero_phase_radii(baseline.initial)
    x_shift = constant_phase_shift(baseline.initial, transformed.initial, False)
    p_shift = constant_phase_shift(baseline.initial, transformed.initial, True)
    left_stages = indexed_stage_trace(baseline_stages)
    right_stages = indexed_stage_trace(transformed_stages)
    left_forces = grouped_force_trace(baseline_forces)
    right_forces = grouped_force_trace(transformed_forces)
    contained, x_aligned, p_aligned = paired_state_containment(
        baseline.initial, transformed.initial, x_shift, p_shift, x_radii, p_radii
    )
    x_relative = relative_state_error(baseline.initial, transformed.initial)
    p_relative = relative_state_error(baseline.initial, transformed.initial, True)
    x_bound = relative_observer_radius(x_radii)
    p_bound = relative_observer_radius(p_radii)
    contained = contained and x_relative <= x_bound and p_relative <= p_bound
    scalar_bits_equal = True
    paired_relations = 0
    for step in range(1, baseline.completed_steps + 1):
        for stage in ("first_kick", "drift", "second_kick"):
            if stage == "first_kick":
                left_before = (
                    baseline.initial if step == 1 else left_stages[(step - 1, "committed")]
                )
                right_before = (
                    transformed.initial if step == 1 else right_stages[(step - 1, "committed")]
                )
            elif stage == "drift":
                left_before = left_stages[(step, "first_kick")]
                right_before = right_stages[(step, "first_kick")]
            else:
                left_before = left_stages[(step, "drift")]
                right_before = right_stages[(step, "drift")]
            if stage in {"first_kick", "second_kick"}:
                p_radii, matched, count = propagate_paired_kick_bound(
                    left_forces[(step, stage)], right_forces[(step, stage)],
                    x_radii, p_radii, False,
                )
                scalar_bits_equal = scalar_bits_equal and matched
                paired_relations += count
                if not matched:
                    contained = False
                    break
            else:
                x_radii, x_shift, matched = propagate_paired_drift_bound(
                    left_before, right_before, interval_raw, interval_raw,
                    x_radii, p_radii, x_shift, p_shift, False,
                )
                if not matched:
                    contained = False
                    break
                common = x_shift[min(x_shift)]
                require(all(value == common for value in x_shift.values()),
                        "frame drift does not have a common affine translation")
            left_after = left_stages[(step, stage)]
            right_after = right_stages[(step, stage)]
            contained = contained and (
                left_after.time_raw == left_before.time_raw
                and right_after.time_raw == right_before.time_raw
                and left_after.time_raw == right_after.time_raw
            )
            local, x_value, p_value = paired_state_containment(
                left_after, right_after, x_shift, p_shift, x_radii, p_radii
            )
            contained = contained and local
            x_aligned = max(x_aligned, x_value)
            p_aligned = max(p_aligned, p_value)
        if not scalar_bits_equal:
            break
        left_commit = left_stages[(step, "committed")]
        right_commit = right_stages[(step, "committed")]
        contained = contained and (
            left_commit.time_raw == right_commit.time_raw
            and left_commit.time_raw == left_before.time_raw + interval_raw
            and right_commit.time_raw == right_before.time_raw + interval_raw
        )
        local, x_value, p_value = paired_state_containment(
            left_commit, right_commit, x_shift, p_shift, x_radii, p_radii
        )
        contained = contained and local
        x_aligned = max(x_aligned, x_value)
        p_aligned = max(p_aligned, p_value)
        x_relative = max(x_relative, relative_state_error(left_commit, right_commit))
        p_relative = max(
            p_relative, relative_state_error(left_commit, right_commit, True)
        )
        x_bound = max(x_bound, relative_observer_radius(x_radii))
        p_bound = max(p_bound, relative_observer_radius(p_radii))
        contained = contained and x_relative <= x_bound and p_relative <= p_bound
    return {
        "passed": scalar_bits_equal and contained,
        "force_scalar_bits_equal": scalar_bits_equal,
        "paired_relation_evaluations": paired_relations,
        "maximum_aligned_position_residual_raw": ratio_text(x_aligned),
        "maximum_aligned_momentum_residual_raw": ratio_text(p_aligned),
        "maximum_relative_position_residual_raw": ratio_text(x_relative),
        "maximum_relative_momentum_residual_raw": ratio_text(p_relative),
        "inward_B256_local_half_ulp_position_witness_raw": ratio_text(x_bound),
        "inward_B256_local_half_ulp_momentum_witness_raw": ratio_text(p_bound),
    }


def paired_reversal_bound_certificate(
    forward: Trajectory,
    forward_stages: Sequence[tuple[
        int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
        tuple[Fraction, Fraction, Fraction],
    ]],
    forward_forces: Sequence[tuple[int, str, dict[str, object]]],
    backward: Trajectory,
    backward_stages: Sequence[tuple[
        int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
        tuple[Fraction, Fraction, Fraction],
    ]],
    backward_forces: Sequence[tuple[int, str, dict[str, object]]],
    interval_raw: int,
) -> dict[str, object]:
    """Certify signed-time recovery by pairing mirrored KDK primitives."""
    require(
        forward.completed_steps == backward.completed_steps
        and forward.final.precision == backward.initial.precision,
        "paired reversal trajectory profile differs",
    )
    require(forward.final.time_raw == backward.initial.time_raw,
            "paired reversal starting time differs")
    x_radii, p_radii = zero_phase_radii(forward.final)
    x_shift = zero_phase_shift(forward.final)
    p_shift = zero_phase_shift(forward.final)
    left_stages = indexed_stage_trace(forward_stages)
    right_stages = indexed_stage_trace(backward_stages)
    left_forces = grouped_force_trace(forward_forces)
    right_forces = grouped_force_trace(backward_forces)
    contained, x_maximum, p_maximum = paired_state_containment(
        forward.final, backward.initial, x_shift, p_shift, x_radii, p_radii
    )
    scalar_bits_equal = True
    paired_relations = 0
    steps = forward.completed_steps
    for reverse_step in range(1, steps + 1):
        forward_step = steps - reverse_step + 1
        forward_pre = (
            forward.initial if forward_step == 1
            else left_stages[(forward_step - 1, "committed")]
        )
        reverse_pre = (
            backward.initial if reverse_step == 1
            else right_stages[(reverse_step - 1, "committed")]
        )
        contained = contained and (
            reverse_pre.time_raw == forward_pre.time_raw + interval_raw
        )
        # Reverse first kick cancels the corresponding forward second kick.
        p_radii, matched, count = propagate_paired_kick_bound(
            left_forces[(forward_step, "second_kick")],
            right_forces[(reverse_step, "first_kick")],
            x_radii, p_radii, True,
        )
        scalar_bits_equal = scalar_bits_equal and matched
        paired_relations += count
        if not matched:
            contained = False
            break
        reverse_first = right_stages[(reverse_step, "first_kick")]
        forward_drift = left_stages[(forward_step, "drift")]
        contained = contained and (
            forward_drift.time_raw == forward_pre.time_raw
            and reverse_first.time_raw == reverse_pre.time_raw
        )
        local, x_value, p_value = paired_state_containment(
            forward_drift, reverse_first, x_shift, p_shift, x_radii, p_radii
        )
        contained = contained and local
        x_maximum = max(x_maximum, x_value)
        p_maximum = max(p_maximum, p_value)

        # The signed drift maps the forward post-drift state back toward its
        # pre-drift state; both local multiply/add RN errors enter the radius.
        forward_first = left_stages[(forward_step, "first_kick")]
        x_radii, x_shift, matched = propagate_paired_drift_bound(
            forward_first, reverse_first,
            interval_raw, -interval_raw,
            x_radii, p_radii, x_shift, p_shift, True,
        )
        scalar_bits_equal = scalar_bits_equal and matched
        if not matched:
            contained = False
            break
        reverse_drift = right_stages[(reverse_step, "drift")]
        contained = contained and (
            forward_first.time_raw == forward_pre.time_raw
            and reverse_drift.time_raw == reverse_pre.time_raw
        )
        local, x_value, p_value = paired_state_containment(
            forward_first, reverse_drift, x_shift, p_shift, x_radii, p_radii
        )
        contained = contained and local
        x_maximum = max(x_maximum, x_value)
        p_maximum = max(p_maximum, p_value)

        # Reverse second kick cancels the corresponding forward first kick.
        p_radii, matched, count = propagate_paired_kick_bound(
            left_forces[(forward_step, "first_kick")],
            right_forces[(reverse_step, "second_kick")],
            x_radii, p_radii, True,
        )
        scalar_bits_equal = scalar_bits_equal and matched
        paired_relations += count
        if not matched:
            contained = False
            break
        reverse_second = right_stages[(reverse_step, "second_kick")]
        contained = contained and (
            left_stages[(forward_step, "second_kick")].time_raw
            == forward_pre.time_raw
            and reverse_second.time_raw == reverse_pre.time_raw
        )
        local, x_value, p_value = paired_state_containment(
            forward_pre, reverse_second, x_shift, p_shift, x_radii, p_radii
        )
        contained = contained and local
        x_maximum = max(x_maximum, x_value)
        p_maximum = max(p_maximum, p_value)
        reverse_commit = right_stages[(reverse_step, "committed")]
        contained = contained and reverse_commit.time_raw == forward_pre.time_raw
        local, x_value, p_value = paired_state_containment(
            forward_pre, reverse_commit, x_shift, p_shift, x_radii, p_radii
        )
        contained = contained and local
        x_maximum = max(x_maximum, x_value)
        p_maximum = max(p_maximum, p_value)
    final_x = raw_phase_error(backward.final, forward.initial)
    final_p = raw_phase_error(backward.final, forward.initial, True)
    contained = contained and backward.final.time_raw == forward.initial.time_raw
    x_bound = max((max(value) for value in x_radii.values()), default=Fraction())
    p_bound = max((max(value) for value in p_radii.values()), default=Fraction())
    contained = contained and final_x <= x_bound and final_p <= p_bound
    return {
        "passed": scalar_bits_equal and contained,
        "force_scalar_bits_equal": scalar_bits_equal,
        "paired_relation_evaluations": paired_relations,
        "maximum_stage_position_residual_raw": ratio_text(x_maximum),
        "maximum_stage_momentum_residual_raw": ratio_text(p_maximum),
        "final_position_residual_raw": ratio_text(final_x),
        "final_momentum_residual_raw": ratio_text(final_p),
        "inward_B256_local_half_ulp_position_witness_raw": ratio_text(x_bound),
        "inward_B256_local_half_ulp_momentum_witness_raw": ratio_text(p_bound),
    }


def exact_discrete_equivariance_certificate(
    baseline_stages: Sequence[tuple[
        int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
        tuple[Fraction, Fraction, Fraction],
    ]],
    baseline_forces: Sequence[tuple[int, str, dict[str, object]]],
    transformed_stages: Sequence[tuple[
        int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
        tuple[Fraction, Fraction, Fraction],
    ]],
    transformed_forces: Sequence[tuple[int, str, dict[str, object]]],
    inverse_signed_axis_rotation: bool,
) -> dict[str, object]:
    """Verify exact primitive equivariance, independently of sampled residual rows."""

    def map_vector(value: Sequence[Fraction]) -> tuple[Fraction, Fraction, Fraction]:
        if inverse_signed_axis_rotation:
            return value[1], -value[0], value[2]
        return value[0], value[1], value[2]

    def map_bounds(value: Sequence[Fraction]) -> tuple[Fraction, Fraction, Fraction]:
        if inverse_signed_axis_rotation:
            return value[1], value[0], value[2]
        return value[0], value[1], value[2]

    left_stages = indexed_stage_trace(baseline_stages)
    right_stages = indexed_stage_trace(transformed_stages)
    passed = set(left_stages) == set(right_stages)
    compared_components = 0
    if passed:
        for key in left_stages:
            passed = passed and (
                left_stages[key].time_raw == right_stages[key].time_raw
            )
            left_packets = packet_lookup(left_stages[key])
            right_packets = packet_lookup(right_stages[key])
            if set(left_packets) != set(right_packets):
                passed = False
                break
            for identifier in left_packets:
                passed = passed and (
                    tuple(left_packets[identifier].x)
                    == map_vector(right_packets[identifier].x)
                    and tuple(left_packets[identifier].p)
                    == map_vector(right_packets[identifier].p)
                )
                compared_components += 6
    left_forces = grouped_force_trace(baseline_forces)
    right_forces = grouped_force_trace(transformed_forces)
    passed = passed and set(left_forces) == set(right_forces)
    paired_relations = 0
    if passed:
        for key in left_forces:
            left_values = left_forces[key]
            right_values = right_forces[key]
            if len(left_values) != len(right_values):
                passed = False
                break
            for left, right in zip(left_values, right_values):
                left_relation = left["relation"]
                right_relation = right["relation"]
                assert isinstance(left_relation, Relation)
                assert isinstance(right_relation, Relation)
                passed = passed and (
                    left_relation == right_relation
                    and left["length_bits"] == right["length_bits"]
                    and left["conjugate_bits"] == right["conjugate_bits"]
                    and left["alpha"] == right["alpha"]
                )
                for name in (
                    "causal_offset", "rounded_impulse",
                    "first_actual_impulse", "second_actual_impulse",
                ):
                    value = right[name]
                    expected = left[name]
                    assert isinstance(value, tuple) and isinstance(expected, tuple)
                    passed = passed and expected == map_vector(value)
                for name in (
                    "relative_subtraction_bounds", "impulse_component_bounds",
                    "first_endpoint_bounds", "second_endpoint_bounds",
                ):
                    value = right[name]
                    expected = left[name]
                    assert isinstance(value, tuple) and isinstance(expected, tuple)
                    passed = passed and expected == map_bounds(value)
                paired_relations += 1
    return {
        "passed": passed,
        "exact_state_stage_components_compared": compared_components,
        "exact_force_primitive_relations_compared": paired_relations,
        "mapping": (
            "inverse_signed_axis_rotation_[y,-x,z]"
            if inverse_signed_axis_rotation else "canonical_packet_id_identity"
        ),
        "inward_B256_local_half_ulp_position_witness_raw": "0/1",
        "inward_B256_local_half_ulp_momentum_witness_raw": "0/1",
    }


def _fraction_difference_pair(
    first: Fraction, second: Fraction,
) -> tuple[int, int]:
    """Return an exact, not-necessarily-reduced |first-second| numerator/denominator.

    The hot exact-comparator path only needs ordering or containment for most
    components.  Deferring canonical Fraction reduction until the winning
    maximum avoids repeating large gcd reductions without changing the exact
    rational value.
    """
    common = math.gcd(first.denominator, second.denominator)
    first_scale = second.denominator // common
    second_scale = first.denominator // common
    numerator = abs(
        first.numerator * first_scale - second.numerator * second_scale
    )
    denominator = first.denominator * first_scale
    return numerator, denominator


def _fraction_pair_greater(
    first: tuple[int, int], second: tuple[int, int],
) -> bool:
    return first[0] * second[1] > second[0] * first[1]


def fraction_difference_within(
    first: Fraction, second: Fraction, radius: Fraction,
) -> bool:
    """Compare |first-second| <= radius without reducing the difference."""
    require(radius >= 0, "negative bounded/rational certificate radius")
    numerator, denominator = _fraction_difference_pair(first, second)
    return numerator * radius.denominator <= radius.numerator * denominator


def bounded_rational_state_is_contained(
    bounded: PhaseState, exact: RationalState,
    x_radii: PhaseRadii, p_radii: PhaseRadii,
) -> bool:
    """Fast exact componentwise containment used by the recurrence hot path."""
    bounded_packets = packet_lookup(bounded)
    exact_packets = {packet.identifier: packet for packet in exact.packets}
    require(
        set(bounded_packets) == set(exact_packets) == set(x_radii) == set(p_radii),
        "bounded/rational certificate inventory differs",
    )
    if bounded.time_raw != exact.time_raw:
        return False
    return all(
        fraction_difference_within(
            bounded_packets[identifier].x[axis],
            exact_packets[identifier].x[axis],
            x_radii[identifier][axis],
        )
        and fraction_difference_within(
            bounded_packets[identifier].p[axis],
            exact_packets[identifier].p[axis],
            p_radii[identifier][axis],
        )
        for identifier in bounded_packets for axis in range(3)
    )


def bounded_rational_state_containment(
    bounded: PhaseState, exact: RationalState,
    x_radii: PhaseRadii, p_radii: PhaseRadii,
) -> tuple[bool, Fraction, Fraction]:
    bounded_packets = packet_lookup(bounded)
    exact_packets = {packet.identifier: packet for packet in exact.packets}
    require(
        set(bounded_packets) == set(exact_packets) == set(x_radii) == set(p_radii),
        "bounded/rational certificate inventory differs",
    )
    return (
        bounded_rational_state_is_contained(
            bounded, exact, x_radii, p_radii,
        ),
        bounded_rational_error(bounded, exact),
        bounded_rational_error(bounded, exact, True),
    )


def kinetic_difference_radius_bound(
    bounded: PhaseState, exact: RationalState, p_radii: PhaseRadii,
) -> Fraction:
    """Bound kinetic-energy error from independently propagated p radii."""
    bounded_packets = packet_lookup(bounded)
    exact_packets = {packet.identifier: packet for packet in exact.packets}
    require(set(bounded_packets) == set(exact_packets) == set(p_radii),
            "kinetic-radius certificate inventory differs")
    result = Fraction()
    for identifier, bounded_packet in bounded_packets.items():
        exact_packet = exact_packets[identifier]
        require(bounded_packet.mass_raw == exact_packet.mass_raw,
                "kinetic-radius certificate mass differs")
        factor = PQ * PQ / (2 * bounded_packet.mass_raw * MQ)
        for axis in range(3):
            result += (
                factor * p_radii[identifier][axis]
                * (abs(bounded_packet.p[axis]) + abs(exact_packet.p[axis]))
            )
    return result


def propagate_bounded_rational_kick_bound(
    bounded_audits: Sequence[dict[str, object]],
    exact_relations: Sequence[
        tuple[Relation, tuple[Fraction, Fraction, Fraction], float, float]
    ],
    interval_raw: int,
    x_radii: PhaseRadii,
    p_radii: PhaseRadii,
    precision: int,
) -> tuple[PhaseRadii, bool, int]:
    """Advance a one-sided B-vs-exact-Q kick radius from local B half-ULPs."""
    if len(bounded_audits) != len(exact_relations):
        return p_radii, False, 0
    result_radii = {identifier: list(value) for identifier, value in p_radii.items()}
    c_exact = Fraction(interval_raw) * TQ * LQ / PQ
    c_bounded = rn(c_exact, precision)
    c_radius = component_round_bound(c_exact, precision)
    matched = True
    paired = 0
    for audit, exact_relation in zip(bounded_audits, exact_relations):
        relation, exact_offset, exact_length, exact_conjugate = exact_relation
        audit_relation = audit["relation"]
        assert isinstance(audit_relation, Relation)
        length_bits = struct.unpack(">Q", struct.pack(">d", exact_length))[0]
        conjugate_bits = struct.unpack(">Q", struct.pack(">d", exact_conjugate))[0]
        if (
            audit_relation != relation
            or audit["length_bits"] != length_bits
            or audit["conjugate_bits"] != conjugate_bits
        ):
            return p_radii, False, paired
        length = exact_float_bits(length_bits)
        conjugate = exact_float_bits(conjugate_bits)
        bounded_coefficient_operand = c_bounded * conjugate
        bounded_coefficient = rn(bounded_coefficient_operand, precision)
        coefficient_radius = (
            abs(conjugate) * c_radius
            + component_round_bound(bounded_coefficient_operand, precision)
        )
        bounded_alpha_operand = bounded_coefficient / length
        bounded_alpha = rn(bounded_alpha_operand, precision)
        alpha_radius = (
            coefficient_radius / abs(length)
            + component_round_bound(bounded_alpha_operand, precision)
        )
        audit_alpha = audit["alpha"]
        assert isinstance(audit_alpha, Fraction)
        require(audit_alpha == bounded_alpha,
                "bounded/rational kick alpha reconstruction differs")
        offset_bounds = audit["relative_subtraction_bounds"]
        impulse_bounds = audit["impulse_component_bounds"]
        first_bounds = audit["first_endpoint_bounds"]
        second_bounds = audit["second_endpoint_bounds"]
        assert all(isinstance(value, tuple) for value in (
            offset_bounds, impulse_bounds, first_bounds, second_bounds
        ))
        for axis in range(3):
            offset_radius = (
                x_radii[relation.first_id][axis]
                + x_radii[relation.second_id][axis]
                + offset_bounds[axis]
            )
            impulse_radius = (
                abs(bounded_alpha) * offset_radius
                + abs(exact_offset[axis]) * alpha_radius
                + impulse_bounds[axis]
            )
            result_radii[relation.first_id][axis] = inward_certificate_witness(
                result_radii[relation.first_id][axis]
                + impulse_radius + first_bounds[axis]
            )
            result_radii[relation.second_id][axis] = inward_certificate_witness(
                result_radii[relation.second_id][axis]
                + impulse_radius + second_bounds[axis]
            )
        paired += 1
    return result_radii, matched, paired


def propagate_bounded_rational_drift_bound(
    bounded_before: PhaseState,
    exact_before: RationalState,
    interval_raw: int,
    x_radii: PhaseRadii,
    p_radii: PhaseRadii,
) -> PhaseRadii:
    """Advance a one-sided B-vs-exact-Q drift radius from local B half-ULPs."""
    precision = bounded_before.precision
    bounded_packets = packet_lookup(bounded_before)
    exact_packets = {packet.identifier: packet for packet in exact_before.packets}
    require(set(bounded_packets) == set(exact_packets),
            "bounded/rational drift packet IDs differ")
    result = {identifier: list(value) for identifier, value in x_radii.items()}
    for identifier, bounded_packet in bounded_packets.items():
        exact_packet = exact_packets[identifier]
        require(bounded_packet.mass_raw == exact_packet.mass_raw,
                "bounded/rational drift mass differs")
        exact_coefficient = Fraction(interval_raw, bounded_packet.mass_raw)
        bounded_coefficient = rn(exact_coefficient, precision)
        coefficient_radius = component_round_bound(exact_coefficient, precision)
        for axis in range(3):
            bounded_exact_displacement = bounded_coefficient * bounded_packet.p[axis]
            bounded_displacement = rn(bounded_exact_displacement, precision)
            bounded_exact_position = bounded_packet.x[axis] + bounded_displacement
            displacement_radius = (
                abs(bounded_coefficient) * p_radii[identifier][axis]
                + abs(exact_packet.p[axis]) * coefficient_radius
                + component_round_bound(bounded_exact_displacement, precision)
            )
            result[identifier][axis] = inward_certificate_witness(
                result[identifier][axis]
                + displacement_radius
                + component_round_bound(bounded_exact_position, precision)
            )
    return result


def advance_bounded_rational_step_bound(
    bounded_stages: dict[tuple[int, str], PhaseState],
    bounded_forces: dict[tuple[int, str], list[dict[str, object]]],
    step: int,
    exact_before: RationalState,
    exact_stages: dict[str, RationalState],
    exact_forces: dict[str, list[
        tuple[Relation, tuple[Fraction, Fraction, Fraction], float, float]
    ]],
    interval_raw: int,
    path: str,
    x_radii: PhaseRadii,
    p_radii: PhaseRadii,
) -> tuple[PhaseRadii, PhaseRadii, bool, int]:
    """Advance and check one complete bounded-vs-Q operation graph."""
    precision = bounded_stages[(step, "first_kick" if path == KDK else "full_kick")].precision
    matched = True
    paired = 0
    if path == KDK:
        p_radii, local, count = propagate_bounded_rational_kick_bound(
            bounded_forces[(step, "first_kick")], exact_forces["first_kick"],
            interval_raw // 2, x_radii, p_radii, precision,
        )
        matched = matched and local
        paired += count
        contained = bounded_rational_state_is_contained(
            bounded_stages[(step, "first_kick")], exact_stages["first_kick"],
            x_radii, p_radii
        )
        matched = matched and contained
        x_radii = propagate_bounded_rational_drift_bound(
            bounded_stages[(step, "first_kick")], exact_stages["first_kick"],
            interval_raw,
            x_radii, p_radii,
        )
        contained = bounded_rational_state_is_contained(
            bounded_stages[(step, "drift")], exact_stages["drift"], x_radii, p_radii
        )
        matched = matched and contained
        p_radii, local, count = propagate_bounded_rational_kick_bound(
            bounded_forces[(step, "second_kick")], exact_forces["second_kick"],
            interval_raw // 2, x_radii, p_radii, precision,
        )
        matched = matched and local
        paired += count
        contained = bounded_rational_state_is_contained(
            bounded_stages[(step, "second_kick")], exact_stages["second_kick"],
            x_radii, p_radii
        )
        matched = matched and contained
    elif path == CONTROL:
        p_radii, local, count = propagate_bounded_rational_kick_bound(
            bounded_forces[(step, "full_kick")], exact_forces["full_kick"],
            interval_raw, x_radii, p_radii, precision,
        )
        matched = matched and local
        paired += count
        contained = bounded_rational_state_is_contained(
            bounded_stages[(step, "full_kick")], exact_stages["full_kick"],
            x_radii, p_radii
        )
        matched = matched and contained
        x_radii = propagate_bounded_rational_drift_bound(
            bounded_stages[(step, "full_kick")], exact_stages["full_kick"],
            interval_raw,
            x_radii, p_radii,
        )
        contained = bounded_rational_state_is_contained(
            bounded_stages[(step, "drift")], exact_stages["drift"], x_radii, p_radii
        )
        matched = matched and contained
    else:
        raise OracleError("unknown bounded/rational certificate path")
    contained = bounded_rational_state_is_contained(
        bounded_stages[(step, "committed")], exact_stages["committed"],
        x_radii, p_radii
    )
    return x_radii, p_radii, matched and contained, paired


def one_step(
    model: Model, state: PhaseState, interval_raw: int, path: str,
    rounding_audit: RoundingAudit | None = None,
) -> tuple[
    str, PhaseState, int,
    list[tuple[
        str, PhaseState, tuple[Fraction, Fraction, Fraction],
        tuple[Fraction, Fraction, Fraction],
    ]],
    list[tuple[str, dict[str, object]]],
]:
    prior = state.clone()
    stages: list[
        tuple[
            str, PhaseState,
            tuple[Fraction, Fraction, Fraction],
            tuple[Fraction, Fraction, Fraction],
        ]
    ] = []
    force_events: list[tuple[str, dict[str, object]]] = []
    operations = 0
    local_audit = rounding_audit if rounding_audit is not None else RoundingAudit()
    try:
        if path == KDK:
            require(interval_raw % 2 == 0, "KDK half timestep is not an integer")
            work, count, audits = kick(model, prior, interval_raw // 2, local_audit)
            operations += count
            p_bound, l_bound = kick_increment_bounds(audits)
            stages.append(("first_kick", work.clone(), p_bound, l_bound))
            force_events.extend(("first_kick", audit) for audit in audits)
            work, count, l_bound = drift(model, work, interval_raw, local_audit)
            operations += count
            stages.append(("drift", work.clone(), (Fraction(),) * 3, l_bound))
            work, count, audits = kick(model, work, interval_raw // 2, local_audit)
            operations += count
            p_bound, l_bound = kick_increment_bounds(audits)
            stages.append(("second_kick", work.clone(), p_bound, l_bound))
            force_events.extend(("second_kick", audit) for audit in audits)
        elif path == CONTROL:
            work, count, audits = kick(model, prior, interval_raw, local_audit)
            operations += count
            p_bound, l_bound = kick_increment_bounds(audits)
            stages.append(("full_kick", work.clone(), p_bound, l_bound))
            force_events.extend(("full_kick", audit) for audit in audits)
            work, count, l_bound = drift(model, work, interval_raw, local_audit)
            operations += count
            stages.append(("drift", work.clone(), (Fraction(),) * 3, l_bound))
        else:
            raise OracleError("unknown bounded path")
        work.time_raw += interval_raw
        validate_phase_state(work)
        stages.append(("committed", work.clone(), (Fraction(),) * 3, (Fraction(),) * 3))
        require(operations == local_audit.total,
                "step rounding-audit operation count differs")
        return "accepted", work, operations, stages, force_events
    except OracleError as error:
        status = str(error).split(":", 1)[0]
        if status in {
            "force_domain_failure", "chord_domain_failure",
            "domain_scratch_bound_exceeded", "phase_range_failure",
        }:
            return status, prior, 0, [], []
        raise


def expected_operation_categories(
    model: Model, state: PhaseState, path: str,
) -> dict[str, int]:
    n = len(state.packets)
    m = len(model.relations)
    if path == KDK:
        kicks = 2
    elif path == CONTROL:
        kicks = 1
    else:
        raise OracleError("unknown path operation count")
    return {
        "drift_constant_conversion": n,
        "drift_displacement_multiplication": 3 * n,
        "drift_position_accumulation": 3 * n,
        "endpoint_momentum_accumulation": kicks * 6 * m,
        "impulse_component_multiplication": kicks * 3 * m,
        "kick_constant_conversion": kicks,
        "kick_length_division": kicks * m,
        "kick_scalar_multiplication": kicks * m,
        "relative_subtraction": kicks * 3 * m,
        "relative_unit_multiplication": kicks * 3 * m,
    }


def canonical_operation_categories(categories: dict[str, int]) -> str:
    require(all(value >= 0 for value in categories.values()),
            "negative operation category count")
    return ";".join(
        f"{name}={categories[name]}" for name in sorted(categories) if categories[name]
    )


def expected_operations(model: Model, state: PhaseState, path: str) -> int:
    return sum(expected_operation_categories(model, state, path).values())


def verify_operation_row(
    row: dict[str, str], trajectory_id: str, precision: int, level: int,
    path: str, model: Model, initial: PhaseState, completed_steps: int,
    trajectory: Trajectory,
) -> None:
    per_step_categories = expected_operation_categories(model, initial, path)
    total_categories = {
        name: count * completed_steps
        for name, count in per_step_categories.items() if count
    }
    expected_text = canonical_operation_categories(total_categories)
    observed_text = canonical_operation_categories(trajectory.operation_categories)
    inexact_text = canonical_operation_categories(trajectory.inexact_categories)
    require(
        row["trajectory_id"] == trajectory_id
        and int(row["precision"]) == precision
        and int(row["level"]) == level
        and row["path"] == path
        and int(row["packet_count"]) == len(initial.packets)
        and int(row["relation_count"]) == len(model.relations)
        and int(row["completed_steps"]) == completed_steps
        and int(row["per_step_expected"]) == sum(per_step_categories.values())
        and row["expected_categories"] == expected_text
        and row["observed_categories"] == observed_text == expected_text
        and row["inexact_categories"] == inexact_text
        and int(row["inexact_total"]) == trajectory.inexact_count
        and int(row["exact_total"])
            == trajectory.operation_count - trajectory.inexact_count
        and int(row["rounding_audit_records"]) == trajectory.operation_count
        and row["rounding_audit_sha256"] == trajectory.rounding_audit_sha256
        and boolean(row["categories_passed"])
        and int(row["total_expected"]) == sum(total_categories.values())
        and int(row["total_observed"]) == trajectory.operation_count
        and boolean(row["passed"]),
        f"{trajectory_id}: causal operation category/count contract differs",
    )


def run_trajectory(
    model: Model, initial: PhaseState, interval_raw: int, steps: int, path: str,
    collect_audit: bool = False,
    initial_momentum_bound: tuple[Fraction, Fraction, Fraction] | None = None,
    initial_angular_bound: tuple[Fraction, Fraction, Fraction] | None = None,
) -> tuple[
    Trajectory,
    list[tuple[
        int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
        tuple[Fraction, Fraction, Fraction],
    ]],
    list[tuple[int, str, dict[str, object]]],
]:
    state = initial.clone()
    samples = [state.clone()]
    events: list[str] = []
    zero_bound = (Fraction(), Fraction(), Fraction())
    starting_momentum_bound = initial_momentum_bound or zero_bound
    starting_angular_bound = initial_angular_bound or zero_bound
    stage_states: list[
        tuple[
            int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
            tuple[Fraction, Fraction, Fraction],
        ]
    ] = [(
        0, "initial", state.clone(),
        starting_momentum_bound, starting_angular_bound,
    )]
    force_events: list[tuple[int, str, dict[str, object]]] = []
    total_operations = 0
    trajectory_audit = RoundingAudit()
    accumulated_momentum_bound = starting_momentum_bound
    accumulated_angular_bound = starting_angular_bound
    status = "accepted"
    completed = 0
    for step in range(1, steps + 1):
        step_audit = RoundingAudit()
        status, candidate, operations, stages, audits = one_step(
            model, state, interval_raw, path, step_audit
        )
        if status != "accepted":
            break
        state = candidate
        completed = step
        samples.append(state.clone())
        events.append(phase_hash(state))
        total_operations += operations
        trajectory_audit.merge(step_audit)
        if collect_audit:
            for stage, value, momentum_increment, angular_increment in stages:
                accumulated_momentum_bound = vector_add(
                    accumulated_momentum_bound, momentum_increment
                )
                accumulated_angular_bound = vector_add(
                    accumulated_angular_bound, angular_increment
                )
                stage_states.append((
                    step, stage, value,
                    accumulated_momentum_bound, accumulated_angular_bound,
                ))
            force_events.extend((step, stage, audit) for stage, audit in audits)
    require(total_operations == expected_operations(model, initial, path) * completed,
            "independent causal operation count differs")
    require(total_operations == trajectory_audit.total,
            "independent rounding-audit record count differs")
    assert trajectory_audit.categories is not None
    assert trajectory_audit.inexact_categories is not None
    return (
        Trajectory(
            status, initial.clone(), state, completed, samples, events, total_operations,
            dict(trajectory_audit.categories), dict(trajectory_audit.inexact_categories),
            trajectory_audit.inexact_total, trajectory_audit.sha256(),
        ),
        stage_states,
        force_events,
    )


def rational_from_parent_rows(state_rows_: Sequence[dict[str, str]]) -> RationalState:
    packets = [
        PacketState(
            int(row["packet_id"]), int(row["mass_raw"]),
            [parent.component(row, "x", axis) for axis in "xyz"],
            [parent.component(row, "p", axis) for axis in "xyz"],
        )
        for row in sorted(state_rows_, key=lambda row: int(row["packet_id"]))
    ]
    return RationalState(int(state_rows_[0]["time_raw"]), packets)


def rational_offset(
    state: RationalState, relation: Relation,
) -> tuple[Fraction, Fraction, Fraction]:
    packets = {packet.identifier: packet for packet in state.packets}
    return vector_sub(packets[relation.second_id].x, packets[relation.first_id].x)


def rational_force_and_energy(
    model: Model, state: RationalState,
) -> tuple[list[tuple[Relation, tuple[Fraction, Fraction, Fraction], float, float]], Fraction]:
    geometry: list[tuple[Relation, tuple[Fraction, Fraction, Fraction], float, float]] = []
    for relation in model.relations:
        offset = rational_offset(state, relation)
        reference = reference_offset(model, relation)
        require(relation_is_safe(offset, reference), "rational force_domain_failure")
        current = [float(component * LQ) for component in offset]
        reference_si = [float(component * LQ) for component in reference]
        length, extension = path_b_geometry(current, reference_si, relation.rest_length)
        geometry.append((relation, offset, length, extension))
    conjugates: list[float] = []
    for row_index in range(len(model.relations)):
        value = 0.0
        for column in range(len(model.relations)):
            value += model.h[row_index][column] * geometry[column][3]
        conjugates.append(value)
    energy_twice = 0.0
    for index, entry in enumerate(geometry):
        energy_twice += entry[3] * conjugates[index]
    evaluated = [
        (entry[0], entry[1], entry[2], conjugates[index])
        for index, entry in enumerate(geometry)
    ]
    bits = struct.unpack(">Q", struct.pack(">d", 0.5 * energy_twice))[0]
    return evaluated, exact_float_bits(bits)


def rational_kick_from_evaluated(
    state: RationalState,
    interval_raw: int,
    evaluated: Sequence[
        tuple[Relation, tuple[Fraction, Fraction, Fraction], float, float]
    ],
) -> RationalState:
    result = state.clone()
    packets = {packet.identifier: packet for packet in result.packets}
    for relation, offset, length, conjugate in evaluated:
        coefficient = (
            Fraction(interval_raw) * TQ * exact_float_bits(
                struct.unpack(">Q", struct.pack(">d", conjugate))[0]
            ) / exact_float_bits(struct.unpack(">Q", struct.pack(">d", length))[0])
        )
        impulse = vector_scale(coefficient * LQ / PQ, offset)
        packets[relation.first_id].p = list(vector_add(packets[relation.first_id].p, impulse))
        packets[relation.second_id].p = list(vector_sub(packets[relation.second_id].p, impulse))
    return result


def rational_kick(model: Model, state: RationalState, interval_raw: int) -> RationalState:
    evaluated, _potential = rational_force_and_energy(model, state)
    return rational_kick_from_evaluated(state, interval_raw, evaluated)


def rational_drift(model: Model, state: RationalState, interval_raw: int) -> RationalState:
    result = state.clone()
    initial = [rational_offset(state, relation) for relation in model.relations]
    for packet in result.packets:
        packet.x = list(vector_add(
            packet.x, vector_scale(Fraction(interval_raw, packet.mass_raw), packet.p)
        ))
    for relation, before in zip(model.relations, initial):
        require(chord_is_safe(before, rational_offset(result, relation), reference_offset(model, relation)),
                "rational chord_domain_failure")
    return result


def rational_step(
    model: Model, state: RationalState, interval_raw: int, path: str,
) -> RationalState:
    if path == KDK:
        work = rational_kick(model, state, interval_raw // 2)
        work = rational_drift(model, work, interval_raw)
        work = rational_kick(model, work, interval_raw // 2)
    elif path == CONTROL:
        work = rational_kick(model, state, interval_raw)
        work = rational_drift(model, work, interval_raw)
    else:
        raise OracleError("unknown rational-control path")
    work.time_raw += interval_raw
    return work


def rational_step_trace(
    model: Model, state: RationalState, interval_raw: int, path: str,
    initial_evaluation: tuple[
        Sequence[
            tuple[Relation, tuple[Fraction, Fraction, Fraction], float, float]
        ],
        Fraction,
    ] | None = None,
) -> tuple[
    RationalState,
    dict[str, RationalState],
    dict[str, list[
        tuple[Relation, tuple[Fraction, Fraction, Fraction], float, float]
    ]],
    tuple[
        list[tuple[
            Relation, tuple[Fraction, Fraction, Fraction], float, float
        ]],
        Fraction,
    ],
]:
    """Advance Q and carry the terminal position's force evaluation forward."""
    stages: dict[str, RationalState] = {}
    forces: dict[str, list[
        tuple[Relation, tuple[Fraction, Fraction, Fraction], float, float]
    ]] = {}
    if initial_evaluation is None:
        current_force, _current_potential = rational_force_and_energy(model, state)
    else:
        force, _current_potential = initial_evaluation
        current_force = list(force)
    if path == KDK:
        first_force = current_force
        forces["first_kick"] = first_force
        work = rational_kick_from_evaluated(state, interval_raw // 2, first_force)
        stages["first_kick"] = work.clone()
        work = rational_drift(model, work, interval_raw)
        stages["drift"] = work.clone()
        second_force, second_potential = rational_force_and_energy(model, work)
        forces["second_kick"] = second_force
        work = rational_kick_from_evaluated(work, interval_raw // 2, second_force)
        stages["second_kick"] = work.clone()
        next_evaluation = (second_force, second_potential)
    elif path == CONTROL:
        full_force = current_force
        forces["full_kick"] = full_force
        work = rational_kick_from_evaluated(state, interval_raw, full_force)
        stages["full_kick"] = work.clone()
        work = rational_drift(model, work, interval_raw)
        stages["drift"] = work.clone()
        next_evaluation = rational_force_and_energy(model, work)
    else:
        raise OracleError("unknown rational-control path")
    work.time_raw += interval_raw
    stages["committed"] = work.clone()
    # Force and potential depend only on position.  Neither the final kick nor
    # the time counter changes position, so this exact evaluation is also the
    # next committed sample's evaluation.
    return work, stages, forces, next_evaluation


def run_rational_trajectory_with_traces(
    model: Model, initial: RationalState, interval_raw: int, steps: int, path: str,
) -> tuple[
    list[RationalState],
    list[tuple[
        dict[str, RationalState],
        dict[str, list[
            tuple[Relation, tuple[Fraction, Fraction, Fraction], float, float]
        ]],
    ]],
    list[tuple[
        list[tuple[
            Relation, tuple[Fraction, Fraction, Fraction], float, float
        ]],
        Fraction,
    ]],
]:
    state = initial.clone()
    samples = [state.clone()]
    traces: list[tuple[
        dict[str, RationalState],
        dict[str, list[
            tuple[Relation, tuple[Fraction, Fraction, Fraction], float, float]
        ]],
    ]] = []
    evaluation = rational_force_and_energy(model, state)
    evaluations = [evaluation]
    for _step in range(steps):
        state, stages, forces, evaluation = rational_step_trace(
            model, state, interval_raw, path, evaluation
        )
        samples.append(state.clone())
        traces.append((stages, forces))
        evaluations.append(evaluation)
    return samples, traces, evaluations


def run_rational_trajectory(
    model: Model, initial: RationalState, interval_raw: int, steps: int, path: str,
) -> list[RationalState]:
    state = initial.clone()
    samples = [state.clone()]
    for _ in range(steps):
        state = rational_step(model, state, interval_raw, path)
        samples.append(state.clone())
    return samples


def rational_energy(model: Model, state: RationalState) -> Fraction:
    kinetic = rational_kinetic_energy(state)
    _relations, potential = rational_force_and_energy(model, state)
    return kinetic + potential


def rational_kinetic_energy(state: RationalState) -> Fraction:
    kinetic = Fraction()
    for packet in state.packets:
        kinetic += dot(packet.p, packet.p) * PQ * PQ / (2 * packet.mass_raw * MQ)
    return kinetic


def bounded_kinetic_energy(state: PhaseState) -> Fraction:
    kinetic = Fraction()
    for packet in state.packets:
        kinetic += dot(packet.p, packet.p) * PQ * PQ / (2 * packet.mass_raw * MQ)
    return kinetic


def least_squares_absolute_bound(
    values: Sequence[Fraction], dt: Fraction,
) -> Fraction:
    """Bound a fitted slope from independent per-sample absolute radii."""
    require(bool(values), "least-squares bound requires samples")
    if len(values) == 1:
        return Fraction()
    times = [Fraction(index) * dt for index in range(len(values))]
    mean_time = sum(times, Fraction()) / len(times)
    denominator = sum(((value - mean_time) ** 2 for value in times), Fraction())
    require(denominator > 0, "least-squares bound has zero time variance")
    return sum(
        (abs(time - mean_time) * radius for time, radius in zip(times, values)),
        Fraction(),
    ) / denominator


def bounded_rational_error(
    bounded: PhaseState, control: RationalState, momentum: bool = False,
) -> Fraction:
    candidate = {packet.identifier: packet for packet in bounded.packets}
    exact = {packet.identifier: packet for packet in control.packets}
    require(set(candidate) == set(exact), "bounded/rational packet IDs differ")
    vector_name = "p" if momentum else "x"
    maximum = (0, 1)
    for identifier in candidate:
        first = getattr(candidate[identifier], vector_name)
        second = getattr(exact[identifier], vector_name)
        for left, right in zip(first, second):
            difference = _fraction_difference_pair(left, right)
            if _fraction_pair_greater(difference, maximum):
                maximum = difference
    return Fraction(*maximum)


def rational_physical_decimal(state: RationalState) -> list[Decimal]:
    packets = sorted(state.packets, key=lambda packet: packet.identifier)
    result = [decimal_value(value * LQ) for packet in packets for value in packet.x]
    result.extend(decimal_value(value * PQ) for packet in packets for value in packet.p)
    return result


STATE_ID_FIELDS = (
    "precision", "scenario_id", "model_id", "scope", "path", "level", "dt_raw",
    "steps", "status", "completed_steps", "time_raw", "state_hash",
)


def load_state_table(path: Path) -> dict[tuple[str, ...], tuple[PhaseState, list[dict[str, str]]]]:
    groups = grouped(rows(path), STATE_ID_FIELDS)
    result: dict[tuple[str, ...], tuple[PhaseState, list[dict[str, str]]]] = {}
    for key, state_rows_ in groups.items():
        state = phase_from_rows(state_rows_)
        require(phase_hash(state) == key[-1], f"{path.name}: reconstructed state hash differs")
        result[key] = (state, state_rows_)
    return result


def state_index(
    table: dict[tuple[str, ...], tuple[PhaseState, list[dict[str, str]]]],
) -> dict[tuple[int, str, str, int], PhaseState]:
    result: dict[tuple[int, str, str, int], PhaseState] = {}
    for key, (state, _rows) in table.items():
        precision, scenario, _model, _scope, path, level = key[:6]
        index = (int(precision), scenario, path, int(level))
        require(index not in result, "duplicate indexed phase state")
        result[index] = state
    return result


def verify_state_tables(raw: Path, parent_raw: Path) -> dict[str, object]:
    tables = {
        filename: load_state_table(raw / filename)
        for filename in (
            "initial_states.csv", "endpoints.csv", "long_endpoints.csv",
            "checkpoint_states.csv", "recovery_states.csv",
        )
    }
    initial = state_index(tables["initial_states.csv"])
    endpoint = state_index(tables["endpoints.csv"])
    long_endpoint = state_index(tables["long_endpoints.csv"])
    checkpoint = state_index(tables["checkpoint_states.csv"])
    recovery = state_index(tables["recovery_states.csv"])

    parent_initial = grouped(rows(parent_raw / "initial_states.csv"), ("scenario_id",))
    scenario_set = {key[0] for key in parent_initial}
    scenario_models = {
        scenario: group[0]["model_id"] for (scenario,), group in parent_initial.items()
    }
    expected_initial = {
        (precision, scenario, "initial", 0)
        for precision in PRECISIONS for scenario in scenario_set
    }
    require(set(initial) == expected_initial, "bounded initial-state inventory differs")
    for key in tables["initial_states.csv"]:
        precision, scenario, model, scope, path, level, dt_raw, steps, status, completed, time_raw = key[:11]
        require(
            int(precision) in PRECISIONS
            and scenario in scenario_set and model == scenario_models[scenario]
            and scope == "initial" and path == "initial"
            and int(level) == 0 and int(dt_raw) == 0 and int(steps) == 0
            and status == "initial" and int(completed) == 0 and int(time_raw) == 0,
            "bounded initial-state descriptor differs",
        )
    for precision in PRECISIONS:
        for scenario in scenario_set:
            candidate = initial[(precision, scenario, "initial", 0)]
            expected_rows = sorted(parent_initial[(scenario,)], key=lambda row: int(row["packet_id"]))
            expected = {
                int(row["packet_id"]): (
                    [parent.component(row, "x", axis) for axis in "xyz"],
                    [parent.component(row, "p", axis) for axis in "xyz"],
                    int(row["mass_raw"]),
                )
                for row in expected_rows
            }
            for packet in candidate.packets:
                require(packet.identifier in expected, "initial packet differs from parent")
                x, p, mass = expected[packet.identifier]
                require(packet.x == x and packet.p == p and packet.mass_raw == mass,
                        "bounded initial value differs from exact-rational parent")

    expected_endpoint = {
        (precision, scenario, path, level)
        for precision in PRECISIONS for scenario in SCENARIOS
        for path in (CONTROL, KDK) for level in LEVELS
    }
    require(set(endpoint) == expected_endpoint, "short endpoint inventory differs")
    for key in tables["endpoints.csv"]:
        precision, scenario, model, scope, path, level, dt_raw, steps, status, completed, time_raw = key[:11]
        index = int(level)
        require(
            int(precision) in PRECISIONS and scenario in SCENARIOS
            and model == scenario_models[scenario] and scope == "short"
            and path in {CONTROL, KDK} and index in LEVELS
            and int(dt_raw) == TIMESTEPS_RAW[index]
            and int(steps) == STEP_COUNTS[index] and status == "accepted"
            and int(completed) == STEP_COUNTS[index]
            and int(time_raw) == TIMESTEPS_RAW[index] * STEP_COUNTS[index],
            "short endpoint descriptor differs",
        )
    expected_long = {
        (precision, scenario, KDK, level)
        for precision in PRECISIONS for scenario in ("k4_internal", "k4_boosted")
        for level in LEVELS
    }
    require(set(long_endpoint) == expected_long, "long endpoint inventory differs")
    for key in tables["long_endpoints.csv"]:
        precision, scenario, model, scope, path, level, dt_raw, steps, status, completed, time_raw = key[:11]
        index = int(level)
        total_steps = 16 * STEP_COUNTS[index]
        require(
            int(precision) in PRECISIONS
            and scenario in {"k4_internal", "k4_boosted"}
            and model == "k4" and scope == "long" and path == KDK
            and index in LEVELS and int(dt_raw) == TIMESTEPS_RAW[index]
            and int(steps) == total_steps and status == "accepted"
            and int(completed) == total_steps
            and int(time_raw) == TIMESTEPS_RAW[index] * total_steps,
            "long endpoint descriptor differs",
        )
    expected_checkpoint = {
        (precision, "k4_internal", KDK, level)
        for precision in PRECISIONS for level in LEVELS
    }
    require(set(checkpoint) == expected_checkpoint, "checkpoint-state inventory differs")
    for key in tables["checkpoint_states.csv"]:
        precision, scenario, model, scope, path, level, dt_raw, steps, status, completed, time_raw = key[:11]
        index = int(level)
        half = STEP_COUNTS[index] // 2
        require(
            int(precision) in PRECISIONS and scenario == "k4_internal"
            and model == "k4" and scope == "checkpoint" and path == KDK
            and index in LEVELS and int(dt_raw) == TIMESTEPS_RAW[index]
            and int(steps) == STEP_COUNTS[index] and status == "accepted"
            and int(completed) == half and int(time_raw) == TIMESTEPS_RAW[index] * half,
            "checkpoint-state descriptor differs",
        )
    expected_recovery = {
        (precision, scenario, KDK, level)
        for precision in PRECISIONS for scenario in SCENARIOS for level in LEVELS
    }
    require(set(recovery) == expected_recovery, "recovery-state inventory differs")
    for key in tables["recovery_states.csv"]:
        precision, scenario, model, scope, path, level, dt_raw, steps, status, completed, time_raw = key[:11]
        index = int(level)
        require(
            int(precision) in PRECISIONS and scenario in SCENARIOS
            and model == scenario_models[scenario] and scope == "recovery" and path == KDK
            and index in LEVELS and int(dt_raw) == TIMESTEPS_RAW[index]
            and int(steps) == STEP_COUNTS[index] and status == "accepted"
            and int(completed) == STEP_COUNTS[index] and int(time_raw) == 0,
            "recovery-state descriptor differs",
        )

    for key in tables["endpoints.csv"]:
        require(key[8] == "accepted" and int(key[9]) == STEP_COUNTS[int(key[5])],
                "short endpoint status/count differs")
    for key in tables["long_endpoints.csv"]:
        require(key[8] == "accepted" and int(key[9]) == 16 * STEP_COUNTS[int(key[5])],
                "long endpoint status/count differs")
    for key in tables["recovery_states.csv"]:
        require(key[8] == "accepted" and int(key[9]) == STEP_COUNTS[int(key[5])],
                "recovery status/count differs")

    for key, state in endpoint.items():
        level = key[3]
        require(state.time_raw == TIMESTEPS_RAW[level] * STEP_COUNTS[level],
                "short endpoint time differs")
    for key, state in long_endpoint.items():
        level = key[3]
        require(state.time_raw == TIMESTEPS_RAW[level] * STEP_COUNTS[level] * 16,
                "long endpoint time differs")
    return {
        "tables": tables,
        "initial": initial,
        "endpoint": endpoint,
        "long_endpoint": long_endpoint,
        "checkpoint": checkpoint,
        "recovery": recovery,
        "state_count": sum(len(table) for table in tables.values()),
    }


def table_model_map(
    table: dict[tuple[str, ...], tuple[PhaseState, list[dict[str, str]]]],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in table:
        scenario, model = key[1], key[2]
        require(scenario not in result or result[scenario] == model,
                "scenario uses multiple models")
        result[scenario] = model
    return result


DYADIC_TEXT = re.compile(r"(-?)0x([0-9a-f]+)@(-?[0-9]+)")


def canonical_dyadic_text(value: Fraction) -> str:
    if value == 0:
        return "0"
    require(value.denominator & (value.denominator - 1) == 0,
            "nondyadic value cannot use compact dyadic encoding")
    magnitude = abs(value.numerator)
    trailing = (magnitude & -magnitude).bit_length() - 1
    odd = magnitude >> trailing
    exponent = trailing - (value.denominator.bit_length() - 1)
    return f"{'-' if value < 0 else ''}0x{odd:x}@{exponent}"


def parse_dyadic_text(text: str) -> Fraction:
    if text == "0":
        return Fraction()
    match = DYADIC_TEXT.fullmatch(text)
    require(match is not None, "invalid compact dyadic encoding")
    assert match is not None
    magnitude_text = match.group(2)
    require(not magnitude_text.startswith("0") and int(magnitude_text[-1], 16) % 2 == 1,
            "compact dyadic significand is not canonical odd hexadecimal")
    magnitude = int(magnitude_text, 16)
    exponent = int(match.group(3))
    value = Fraction(magnitude) * power_of_two(exponent)
    if match.group(1):
        value = -value
    require(canonical_dyadic_text(value) == text, "compact dyadic round trip differs")
    return value


def raw_vector_from_row(
    row: dict[str, str], prefix: str,
) -> tuple[Fraction, Fraction, Fraction]:
    """Decode the complete compact xyz vector; no derived value is trusted."""
    encoded = tuple(row[f"{prefix}_raw_{axis}_dyadic"] for axis in "xyz")
    require(all(encoded), f"{prefix}: compact raw xyz vector is incomplete")
    result = tuple(parse_dyadic_text(value) for value in encoded)
    return result  # type: ignore[return-value]


def verify_raw_vector_matches(
    row: dict[str, str], prefix: str, raw_expected: Sequence[Fraction],
    scale: Fraction,
) -> tuple[Fraction, Fraction, Fraction]:
    """Compare retained raw xyz, then independently derive physical/hash/max."""
    expected = tuple(raw_expected)
    require(len(expected) == 3, f"{prefix}: expected xyz inventory differs")
    actual_raw = raw_vector_from_row(row, prefix)
    require(actual_raw == expected, f"{prefix}: raw exact xyz vector differs")
    physical = tuple(component * scale for component in actual_raw)
    # These are intentionally recomputed rather than read from the compact row.
    derived_hash = vector_hash(physical)
    derived_raw_maximum = infinity_norm(actual_raw)
    derived_physical_maximum = infinity_norm(physical)
    require(SHA256.fullmatch(derived_hash) is not None,
            f"{prefix}: independently derived vector hash is malformed")
    require(derived_raw_maximum * abs(scale) == derived_physical_maximum,
            f"{prefix}: independently derived vector scaling differs")
    return physical  # type: ignore[return-value]


def scalar_from_columns(row: dict[str, str], prefix: str) -> Fraction:
    numerator = decimal_integer(row[f"{prefix}_num"])
    denominator = decimal_integer(row[f"{prefix}_den"], unsigned=True)
    require(denominator > 0, f"{prefix}: nonpositive denominator")
    value = Fraction(numerator, denominator)
    require(value.numerator == numerator and value.denominator == denominator,
            f"{prefix}: fraction is not reduced")
    hash_key = f"{prefix}_hash"
    if hash_key in row:
        require(row[hash_key] == fraction_hash(value), f"{prefix}: fraction hash differs")
    return value


def verify_energy_row(
    row: dict[str, str], expected: tuple[Fraction, Fraction, Fraction],
) -> None:
    kinetic, potential, mechanical = expected
    require(scalar_from_columns(row, "kinetic") == kinetic, "kinetic energy differs")
    require(scalar_from_columns(row, "potential") == potential, "potential energy differs")
    require(scalar_from_columns(row, "mechanical") == mechanical, "mechanical energy differs")
    require(exact_float_bits(row["potential_binary64_bits"]) == potential,
            "potential binary64 bits differ")


def verify_invariant_row(
    row: dict[str, str], state: PhaseState,
    baseline: tuple[Sequence[Fraction], Sequence[Fraction]], model: Model,
    accumulated_momentum_bound: Sequence[Fraction],
    accumulated_angular_bound: Sequence[Fraction],
) -> tuple[Fraction, Fraction]:
    momentum_raw, angular_raw = exact_state_invariants(state)
    momentum = vector_scale(PQ, momentum_raw)
    angular = vector_scale(LQ * PQ, angular_raw)
    delta_momentum = vector_sub(momentum, vector_scale(PQ, baseline[0]))
    delta_angular = vector_sub(angular, vector_scale(LQ * PQ, baseline[1]))
    require(row["state_hash"] == phase_hash(state), "invariant stage state hash differs")
    observed_momentum = verify_raw_vector_matches(
        row, "momentum", momentum_raw, PQ
    )
    observed_angular = verify_raw_vector_matches(
        row, "angular", angular_raw, LQ * PQ
    )
    # The compact schema deliberately stores absolute current invariants only.
    # Deltas, physical units, maxima, and hashes are all derived here.
    observed_delta_momentum = vector_sub(
        observed_momentum, vector_scale(PQ, baseline[0])
    )
    observed_delta_angular = vector_sub(
        observed_angular, vector_scale(LQ * PQ, baseline[1])
    )
    require(observed_delta_momentum == delta_momentum,
            "derived total-momentum delta differs")
    require(observed_delta_angular == delta_angular,
            "derived orbital-angular-momentum delta differs")
    vector_hash(observed_delta_momentum)
    vector_hash(observed_delta_angular)
    precision = state.precision
    step = int(row["step"])
    unit_roundoff = Fraction(1, 2**precision)
    momentum_bound = 4 * len(model.relations) * step * unit_roundoff * 2**40 * PQ
    angular_bound = (
        (16 * len(model.relations) + 4 * len(state.packets))
        * step * unit_roundoff * 2**88 * LQ * PQ
    )
    require(infinity_norm(delta_momentum) <= momentum_bound,
            "total momentum exceeds operation-count bound")
    require(infinity_norm(delta_angular) <= angular_bound,
            "orbital angular momentum exceeds operation-count bound")
    require(all(
        abs(delta_momentum[axis]) <= accumulated_momentum_bound[axis]
        for axis in range(3)
    ), "total momentum exceeds summed local half-ULP bounds")
    require(all(
        abs(delta_angular[axis]) <= accumulated_angular_bound[axis]
        for axis in range(3)
    ), "orbital angular momentum exceeds summed local half-ULP bounds")
    return infinity_norm(delta_momentum), infinity_norm(delta_angular)


def verify_force_row(row: dict[str, str], expected: dict[str, object]) -> dict[str, Fraction]:
    relation = expected["relation"]
    assert isinstance(relation, Relation)
    require(
        int(row["relation_index"]) == relation.index
        and int(row["first_id"]) == relation.first_id
        and int(row["second_id"]) == relation.second_id,
        "force relation identity/orientation differs",
    )
    require(int(row["length_bits"]) == expected["length_bits"], "force length bits differ")
    require(int(row["conjugate_bits"]) == expected["conjugate_bits"],
            "force conjugate bits differ")
    for key in (
        "causal_offset_raw_hash", "exact_stored_offset_raw_hash", "ideal_impulse_raw_hash",
        "first_actual_impulse_raw_hash", "second_actual_impulse_raw_hash",
    ):
        require(row[key] == expected[key], f"force {key} differs")
    residuals: dict[str, Fraction] = {}
    pairs = (
        ("pair_momentum_residual", "pair_momentum_bound"),
        ("stored_impulse_centrality_residual", "stored_impulse_centrality_bound"),
        ("first_actual_centrality_residual", "first_actual_centrality_bound"),
        ("second_actual_centrality_residual", "second_actual_centrality_bound"),
        ("relation_angular_residual", "relation_angular_bound"),
    )
    for prefix, bound_name in pairs:
        expected_vector = expected[prefix]
        bound = expected[bound_name]
        assert isinstance(expected_vector, tuple) and isinstance(bound, tuple)
        if prefix == "pair_momentum_residual":
            scale = PQ
        else:
            scale = LQ * PQ
        raw_expected = tuple(component / scale for component in expected_vector)
        actual = verify_raw_vector_matches(row, prefix, raw_expected, scale)
        require(all(abs(actual[index]) <= bound[index] for index in range(3)),
                f"{prefix}: residual exceeds independently summed half-ULP bound")
        residuals[prefix] = infinity_norm(actual)
    return residuals


def verify_audit_trajectory(
    invariant_iterator: Iterable[dict[str, str]],
    force_iterator: Iterable[dict[str, str]],
    operation_row: dict[str, str],
    trajectory_id: str,
    precision: int,
    level: int,
    model: Model,
    initial: PhaseState,
    interval_raw: int,
    steps: int,
    baseline: tuple[Sequence[Fraction], Sequence[Fraction]],
    step_offset: int = 0,
    initial_momentum_bound: tuple[Fraction, Fraction, Fraction] | None = None,
    initial_angular_bound: tuple[Fraction, Fraction, Fraction] | None = None,
) -> tuple[
    Trajectory,
    StageTrace,
    ForceTrace,
    tuple[Fraction, Fraction, Fraction],
    tuple[Fraction, Fraction, Fraction],
    int,
    int,
    dict[str, Fraction],
    dict[str, Fraction],
]:
    """Replay and consume one complete accepted invariant/force audit stream."""
    replay, stage_states, force_events = run_trajectory(
        model, initial, interval_raw, steps, KDK, True,
        initial_momentum_bound, initial_angular_bound,
    )
    require(
        replay.status == "accepted" and replay.completed_steps == steps,
        f"{trajectory_id}: auxiliary audit replay failed",
    )
    verify_operation_row(
        operation_row, trajectory_id, precision, level, KDK,
        model, initial, steps, replay,
    )
    invariant_rows = take_evidence_rows(
        invariant_iterator, len(stage_states), f"{trajectory_id}: invariant audit"
    )
    force_rows = take_evidence_rows(
        force_iterator, len(force_events), f"{trajectory_id}: force audit"
    )
    residual_maxima: dict[str, Fraction] = defaultdict(Fraction)
    bound_maxima: dict[str, Fraction] = defaultdict(Fraction)
    for row, (step, stage, state, momentum_bound, angular_bound) in zip(
        invariant_rows, stage_states
    ):
        absolute_step = step + step_offset
        require(
            row["trajectory_id"] == trajectory_id
            and int(row["precision"]) == precision
            and int(row["level"]) == level
            and int(row["step"]) == absolute_step
            and row["stage"] == stage,
            f"{trajectory_id}: invariant audit causal order differs",
        )
        p_error, l_error = verify_invariant_row(
            row, state, baseline, model, momentum_bound, angular_bound,
        )
        residual_maxima["momentum"] = max(residual_maxima["momentum"], p_error)
        residual_maxima["angular"] = max(residual_maxima["angular"], l_error)
        bound_maxima["accumulated_momentum"] = max(
            bound_maxima["accumulated_momentum"], infinity_norm(momentum_bound)
        )
        bound_maxima["accumulated_angular"] = max(
            bound_maxima["accumulated_angular"], infinity_norm(angular_bound)
        )
    for row, (step, stage, expected) in zip(force_rows, force_events):
        absolute_step = step + step_offset
        require(
            row["trajectory_id"] == trajectory_id
            and int(row["precision"]) == precision
            and int(row["level"]) == level
            and int(row["step"]) == absolute_step
            and row["stage"] == stage,
            f"{trajectory_id}: force audit causal order differs",
        )
        for name, value in verify_force_row(row, expected).items():
            residual_maxima[name] = max(residual_maxima[name], value)
        for name in (
            "pair_momentum_bound", "stored_impulse_centrality_bound",
            "first_actual_centrality_bound", "second_actual_centrality_bound",
            "relation_angular_bound",
        ):
            bound = expected[name]
            assert isinstance(bound, tuple)
            bound_maxima[name] = max(bound_maxima[name], infinity_norm(bound))
    final_momentum_bound = stage_states[-1][3]
    final_angular_bound = stage_states[-1][4]
    return (
        replay, stage_states, force_events,
        final_momentum_bound, final_angular_bound,
        len(invariant_rows), len(force_rows),
        dict(residual_maxima), dict(bound_maxima),
    )


def verify_auxiliary_audits(
    raw: Path,
    state_report: dict[str, object],
    models: dict[str, Model],
    trajectories: dict[tuple[int, str, str, int], Trajectory],
    operation_rows: dict[str, dict[str, str]],
) -> tuple[dict[str, object], dict[str, AuditReplay]]:
    """Independently replay all 225 non-primary, non-long accepted invocations."""
    initial = state_report["initial"]
    checkpoints = state_report["checkpoint"]
    assert isinstance(initial, dict) and isinstance(checkpoints, dict)
    auxiliary_prefixes = ("reverse:", "covariance:", "checkpoint:")
    invariant_iterator = iter(
        row for row in iter_rows(raw / "invariants.csv")
        if row["trajectory_id"].startswith(auxiliary_prefixes)
    )
    force_iterator = iter(
        row for row in iter_rows(raw / "force_audit.csv")
        if row["trajectory_id"].startswith(auxiliary_prefixes)
    )
    invocations = 0
    invariant_count = 0
    force_count = 0
    residual_maxima: dict[int, dict[str, Fraction]] = {
        precision: defaultdict(Fraction) for precision in PRECISIONS
    }
    bound_maxima: dict[int, dict[str, Fraction]] = {
        precision: defaultdict(Fraction) for precision in PRECISIONS
    }
    audit_replays: dict[str, AuditReplay] = {}

    def consume(
        trajectory_id: str,
        precision: int,
        level: int,
        model: Model,
        state: PhaseState,
        interval_raw: int,
        steps: int,
        baseline: tuple[Sequence[Fraction], Sequence[Fraction]],
        step_offset: int = 0,
        inherited_bounds: tuple[
            tuple[Fraction, Fraction, Fraction],
            tuple[Fraction, Fraction, Fraction],
        ] | None = None,
    ) -> tuple[
        Trajectory,
        tuple[Fraction, Fraction, Fraction],
        tuple[Fraction, Fraction, Fraction],
    ]:
        nonlocal invocations, invariant_count, force_count
        momentum_bound = inherited_bounds[0] if inherited_bounds else None
        angular_bound = inherited_bounds[1] if inherited_bounds else None
        result = verify_audit_trajectory(
            invariant_iterator, force_iterator, operation_rows[trajectory_id],
            trajectory_id, precision, level, model, state, interval_raw, steps,
            baseline, step_offset, momentum_bound, angular_bound,
        )
        (
            replay, stage_states, force_events,
            final_p_bound, final_l_bound,
            inv_rows, frc_rows, residuals, bounds,
        ) = result
        require(trajectory_id not in audit_replays,
                "duplicate auxiliary replay cache identity")
        audit_replays[trajectory_id] = (replay, stage_states, force_events)
        invocations += 1
        invariant_count += inv_rows
        force_count += frc_rows
        for name, value in residuals.items():
            residual_maxima[precision][name] = max(
                residual_maxima[precision][name], value
            )
        for name, value in bounds.items():
            bound_maxima[precision][name] = max(bound_maxima[precision][name], value)
        return replay, final_p_bound, final_l_bound

    scenario_models = {
        "k4_breathing": "k4", "k4_internal": "k4",
        "octahedron_deformation": "octahedron",
    }
    transformed_models = {
        "translation": ("k4_translated", "k4_translated"),
        "galilean_boost": ("k4_boosted", "k4"),
        "proper_lattice_rotation": ("k4_rotated", "k4_rotated"),
    }
    for level in LEVELS:
        dt_raw = TIMESTEPS_RAW[level]
        steps = STEP_COUNTS[level]
        for precision in PRECISIONS:
            for scenario in SCENARIOS:
                model = models[scenario_models[scenario]]
                state = trajectories[(precision, scenario, KDK, level)].final
                trajectory_id = f"reverse:{scenario}:B{precision}:L{level}"
                consume(
                    trajectory_id, precision, level, model, state,
                    -dt_raw, steps, exact_state_invariants(state),
                )
            for kind, (scenario, model_name) in transformed_models.items():
                state = initial[(precision, scenario, "initial", 0)]
                trajectory_id = f"covariance:{kind}:B{precision}:L{level}"
                consume(
                    trajectory_id, precision, level, models[model_name], state,
                    dt_raw, steps, exact_state_invariants(state),
                )
            permuted = initial[(precision, "k4_internal", "initial", 0)].clone()
            permuted.packets.reverse()
            trajectory_id = f"covariance:packet_permutation:B{precision}:L{level}"
            consume(
                trajectory_id, precision, level, models["k4"], permuted,
                dt_raw, steps, exact_state_invariants(permuted),
            )

            full_initial = initial[(precision, "k4_internal", "initial", 0)]
            full_baseline = exact_state_invariants(full_initial)
            half = steps // 2
            first_id = f"checkpoint:first:B{precision}:L{level}"
            first, first_p_bound, first_l_bound = consume(
                first_id, precision, level, models["k4"], full_initial,
                dt_raw, half, full_baseline,
            )
            checkpoint = checkpoints[(precision, "k4_internal", KDK, level)]
            require(
                encode_phase_state(first.final) == encode_phase_state(checkpoint),
                f"{first_id}: checkpoint state differs",
            )
            resumed_id = f"checkpoint:resumed:B{precision}:L{level}"
            consume(
                resumed_id, precision, level, models["k4"], checkpoint,
                dt_raw, half, full_baseline, half,
                (first_p_bound, first_l_bound),
            )

    try:
        next(invariant_iterator)
        raise OracleError("unexpected extra auxiliary invariant audit row")
    except StopIteration:
        pass
    try:
        next(force_iterator)
        raise OracleError("unexpected extra auxiliary force audit row")
    except StopIteration:
        pass
    require(invocations == 225, "auxiliary accepted audit invocation count differs")
    report = {
        "invocations": invocations,
        "invariant_rows": invariant_count,
        "force_rows": force_count,
        "maximum_residuals": {
            str(precision): {
                name: ratio_text(value) for name, value in sorted(values.items())
            }
            for precision, values in residual_maxima.items()
        },
        "independently_summed_half_ulp_bound_maxima": {
            str(precision): {
                name: ratio_text(value) for name, value in sorted(values.items())
            }
            for precision, values in bound_maxima.items()
        },
    }
    require(set(audit_replays) == {
        trajectory_id for trajectory_id in operation_rows
        if trajectory_id.startswith(auxiliary_prefixes)
    }, "auxiliary replay cache inventory differs")
    return report, audit_replays


def verify_short_replay(
    raw: Path,
    state_report: dict[str, object],
    models: dict[str, Model],
) -> tuple[
    dict[tuple[int, str, str, int], Trajectory],
    dict[tuple[int, str, str, int], tuple[
        list[tuple[
            int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
            tuple[Fraction, Fraction, Fraction],
        ]],
        list[tuple[int, str, dict[str, object]]],
    ]],
    dict[str, object],
]:
    initial = state_report["initial"]
    endpoints = state_report["endpoint"]
    tables = state_report["tables"]
    assert isinstance(initial, dict) and isinstance(endpoints, dict) and isinstance(tables, dict)
    initial_table = tables["initial_states.csv"]
    assert isinstance(initial_table, dict)
    scenario_models = table_model_map(initial_table)

    invariant_groups = grouped(
        (row for row in iter_rows(raw / "invariants.csv") if row["trajectory_id"].startswith("short:")),
        ("trajectory_id",),
    )
    force_groups = grouped(
        (row for row in iter_rows(raw / "force_audit.csv") if row["trajectory_id"].startswith("short:")),
        ("trajectory_id",),
    )
    energy_groups = grouped(rows(raw / "energies.csv"),
                            ("scenario_id", "path", "precision", "level"))
    operation_rows = {
        row["trajectory_id"]: row
        for row in rows(raw / "operation_counts.csv")
        if row["trajectory_id"].startswith("short:")
    }
    require(len(operation_rows) == 3 * 2 * 5 * 5, "short operation-count inventory differs")
    expected_short_trajectories = {
        f"short:{scenario}:{path}:B{precision}:L{level}"
        for scenario in SCENARIOS for path in (CONTROL, KDK)
        for precision in PRECISIONS for level in LEVELS
    }
    require(
        set(invariant_groups) == {(value,) for value in expected_short_trajectories}
        and set(force_groups) == {(value,) for value in expected_short_trajectories},
        "short invariant/force audit trajectory inventory differs",
    )

    trajectories: dict[tuple[int, str, str, int], Trajectory] = {}
    trajectory_traces: dict[tuple[int, str, str, int], tuple[
        list[tuple[
            int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
            tuple[Fraction, Fraction, Fraction],
        ]],
        list[tuple[int, str, dict[str, object]]],
    ]] = {}
    maximum_residuals: dict[int, dict[str, Fraction]] = {
        precision: defaultdict(Fraction) for precision in PRECISIONS
    }
    maximum_analytic_bounds: dict[int, dict[str, Fraction]] = {
        precision: defaultdict(Fraction) for precision in PRECISIONS
    }
    for level in LEVELS:
        for scenario in SCENARIOS:
            model = models[scenario_models[scenario]]
            for path in (CONTROL, KDK):
                for precision in PRECISIONS:
                    key = (precision, scenario, path, level)
                    initial_state = initial[(precision, scenario, "initial", 0)]
                    assert isinstance(initial_state, PhaseState)
                    trajectory_id = f"short:{scenario}:{path}:B{precision}:L{level}"
                    trajectory, stage_states, force_events = run_trajectory(
                        model, initial_state, TIMESTEPS_RAW[level], STEP_COUNTS[level], path, True
                    )
                    require(trajectory.status == "accepted"
                            and trajectory.completed_steps == STEP_COUNTS[level],
                            f"{trajectory_id}: independent short replay failed")
                    expected_endpoint = endpoints[key]
                    assert isinstance(expected_endpoint, PhaseState)
                    require(encode_phase_state(trajectory.final) == encode_phase_state(expected_endpoint),
                            f"{trajectory_id}: endpoint replay differs")
                    trajectories[key] = trajectory
                    trajectory_traces[key] = (stage_states, force_events)

                    baseline = exact_state_invariants(initial_state)
                    invariant_rows = invariant_groups.get((trajectory_id,), [])
                    require(len(invariant_rows) == len(stage_states),
                            f"{trajectory_id}: invariant stage inventory differs")
                    for row, (
                        step, stage, stage_state, momentum_bound, angular_bound,
                    ) in zip(invariant_rows, stage_states):
                        require(int(row["step"]) == step and row["stage"] == stage,
                                f"{trajectory_id}: invariant stage order differs")
                        p_error, l_error = verify_invariant_row(
                            row, stage_state, baseline, model,
                            momentum_bound, angular_bound,
                        )
                        maximum_residuals[precision]["momentum"] = max(
                            maximum_residuals[precision]["momentum"], p_error
                        )
                        maximum_residuals[precision]["angular"] = max(
                            maximum_residuals[precision]["angular"], l_error
                        )
                        maximum_analytic_bounds[precision]["accumulated_momentum"] = max(
                            maximum_analytic_bounds[precision]["accumulated_momentum"],
                            infinity_norm(momentum_bound),
                        )
                        maximum_analytic_bounds[precision]["accumulated_angular"] = max(
                            maximum_analytic_bounds[precision]["accumulated_angular"],
                            infinity_norm(angular_bound),
                        )

                    force_rows = force_groups.get((trajectory_id,), [])
                    require(len(force_rows) == len(force_events),
                            f"{trajectory_id}: force-audit inventory differs")
                    for row, (step, stage, expected) in zip(force_rows, force_events):
                        require(int(row["step"]) == step and row["stage"] == stage,
                                f"{trajectory_id}: force-audit order differs")
                        residuals = verify_force_row(row, expected)
                        for name, value in residuals.items():
                            maximum_residuals[precision][name] = max(
                                maximum_residuals[precision][name], value
                            )
                        for name in (
                            "pair_momentum_bound", "stored_impulse_centrality_bound",
                            "first_actual_centrality_bound",
                            "second_actual_centrality_bound", "relation_angular_bound",
                        ):
                            bound = expected[name]
                            assert isinstance(bound, tuple)
                            maximum_analytic_bounds[precision][name] = max(
                                maximum_analytic_bounds[precision][name],
                                infinity_norm(bound),
                            )

                    energy_rows = energy_groups.get(
                        (scenario, path, str(precision), str(level)), []
                    )
                    require(len(energy_rows) == len(trajectory.samples),
                            f"{trajectory_id}: energy sample inventory differs")
                    for sample, (row, state) in enumerate(zip(energy_rows, trajectory.samples)):
                        require(int(row["sample"]) == sample,
                                f"{trajectory_id}: energy sample order differs")
                        verify_energy_row(row, mechanical_energy(model, state))

                    operation = operation_rows[trajectory_id]
                    verify_operation_row(
                        operation, trajectory_id, precision, level, path, model,
                        initial_state, STEP_COUNTS[level], trajectory,
                    )

    return trajectories, trajectory_traces, {
        "trajectories": len(trajectories),
        "maximum_residuals": {
            str(precision): {
                name: f"{value.numerator}/{value.denominator}"
                for name, value in sorted(values.items())
            }
            for precision, values in maximum_residuals.items()
        },
        "independently_summed_half_ulp_bound_maxima": {
            str(precision): {
                name: ratio_text(value) for name, value in sorted(values.items())
            }
            for precision, values in maximum_analytic_bounds.items()
        },
        "causal_rounding_records_recomputed_and_digest_bound": True,
        "compact_xyz_hash_max_physical_and_delta_derivations": True,
    }


def verify_representation_and_temporal(
    raw: Path,
    parent_raw: Path,
    models: dict[str, Model],
    trajectories: dict[tuple[int, str, str, int], Trajectory],
    trajectory_traces: dict[tuple[int, str, str, int], tuple[
        list[tuple[
            int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
            tuple[Fraction, Fraction, Fraction],
        ]],
        list[tuple[int, str, dict[str, object]]],
    ]],
    smooth: dict[str, list[Decimal]],
    smooth_traces: dict[str, list[list[Decimal]]],
) -> tuple[
    dict[str, object], dict[int, bool], bool,
    dict[str, dict[int, Fraction]],
]:
    inventory_report = verify_representation_error_inventory(raw)
    parent_initial = grouped(rows(parent_raw / "initial_states.csv"), ("scenario_id",))
    parent_endpoints = {
        (row["scenario_id"], row["path"], int(row["level"])): row["state_hash"]
        for row in rows(parent_raw / "endpoints.csv")
    }
    representation_groups = grouped(
        (row for row in rows(raw / "representation_error.csv") if row["scope"] == "short"),
        ("scenario_id", "path", "precision", "level"),
    )
    expected_keys = {
        (scenario, path, str(precision), str(level))
        for scenario in SCENARIOS for path in (CONTROL, KDK)
        for precision in PRECISIONS for level in LEVELS
    }
    require(set(representation_groups) == expected_keys,
            "short representation-error inventory differs")

    envelope: dict[tuple[str, str, int, int], tuple[Fraction, Fraction, Decimal]] = {}
    exact_structure_envelopes = {
        name: {precision: Fraction() for precision in PRECISIONS}
        for name in (
            "representation_position", "representation_momentum",
            "representation_energy",
        )
    }
    rational_endpoint: dict[tuple[str, str, int], RationalState] = {}
    exact_truncation: dict[tuple[str, str, int], Decimal] = {}
    exact_truncation_samples: dict[tuple[str, str, int], list[Decimal]] = {}
    bounded_smooth_samples: dict[tuple[str, str, int, int], list[Decimal]] = {}
    short_energy_bound_pass = {precision: True for precision in PRECISIONS}
    short_energy_certificate: dict[int, dict[str, object]] = {
        precision: {
            "samples": 0,
            "potential_binary64_value_matches": 0,
            "force_scalar_pairs": 0,
            "force_scalar_bit_matches": 0,
            "paired_kick_relations": 0,
            "maximum_energy_residual": Fraction(),
            "maximum_componentwise_energy_bound": Fraction(),
        }
        for precision in PRECISIONS
    }
    model_names = {
        "k4_breathing": "k4", "k4_internal": "k4",
        "octahedron_deformation": "octahedron",
    }
    for level in LEVELS:
        for scenario in SCENARIOS:
            model = models[model_names[scenario]]
            rational_initial = rational_from_parent_rows(parent_initial[(scenario,)])
            for path, parent_path in ((CONTROL, Q_CONTROL), (KDK, Q_KDK)):
                (
                    rational_samples, rational_traces, rational_evaluations,
                ) = run_rational_trajectory_with_traces(
                    model, rational_initial, TIMESTEPS_RAW[level],
                    STEP_COUNTS[level], path,
                )
                rational_hashes = [rational_hash(state) for state in rational_samples]
                rational_decimals = [
                    rational_physical_decimal(state) for state in rational_samples
                ]
                require(
                    all(
                        trace[0]["committed"] == rational_samples[index + 1]
                        for index, trace in enumerate(rational_traces)
                    ),
                    "exact-rational short trace/sample chain differs",
                )
                rational_endpoint[(scenario, path, level)] = rational_samples[-1]
                require(
                    rational_hashes[-1]
                    == parent_endpoints[(scenario, parent_path, level)],
                    "exact-rational short positive-control endpoint differs",
                )
                stride = 2 ** (4 - level)
                registered_smooth = smooth_traces[scenario][::stride]
                require(len(registered_smooth) == len(rational_samples),
                        "smooth/exact-rational sample grids differ")
                truncation_trace = [
                    foundation.state_norm_difference(
                        exact_decimal, smooth_state, len(exact.packets),
                    )
                    for exact, exact_decimal, smooth_state in zip(
                        rational_samples, rational_decimals, registered_smooth
                    )
                ]
                exact_truncation_samples[(scenario, path, level)] = truncation_trace
                exact_truncation[(scenario, path, level)] = max(
                    truncation_trace, default=Decimal()
                )
                rational_energy_parts = [
                    (*evaluation, rational_kinetic_energy(state))
                    for state, evaluation in zip(
                        rational_samples, rational_evaluations
                    )
                ]
                for precision in PRECISIONS:
                    trajectory_key = (precision, scenario, path, level)
                    bounded_trajectory = trajectories[trajectory_key]
                    bounded_samples = bounded_trajectory.samples
                    bounded_stage_values, bounded_force_values = trajectory_traces[
                        trajectory_key
                    ]
                    bounded_stage_map = indexed_stage_trace(bounded_stage_values)
                    bounded_force_map = grouped_force_trace(bounded_force_values)
                    x_radii, p_radii = zero_phase_radii(bounded_trajectory.initial)
                    certified_exact = rational_samples[0]
                    initial_contained = bounded_rational_state_is_contained(
                        bounded_trajectory.initial, certified_exact,
                        x_radii, p_radii,
                    )
                    short_energy_bound_pass[precision] = (
                        short_energy_bound_pass[precision] and initial_contained
                    )
                    evidence = representation_groups[(scenario, path, str(precision), str(level))]
                    require(len(evidence) == len(bounded_samples) == len(rational_samples),
                            "short representation sample count differs")
                    maximum_x = Fraction()
                    maximum_p = Fraction()
                    maximum_state = Decimal()
                    smooth_error_trace: list[Decimal] = []
                    for sample, (
                        row, bounded, exact, exact_energy_parts,
                        exact_hash, exact_decimal,
                    ) in enumerate(
                        zip(
                            evidence, bounded_samples, rational_samples,
                            rational_energy_parts, rational_hashes,
                            rational_decimals,
                        )
                    ):
                        exact_relations, exact_potential, exact_kinetic = exact_energy_parts
                        exact_energy = exact_kinetic + exact_potential
                        require(certified_exact == exact,
                                "short bounded/rational certificate state differs")
                        identity: dict[str, object] = {
                            "scenario_id": scenario,
                            "scope": "short",
                            "path": path,
                            "precision": precision,
                            "level": level,
                            "dt_raw": TIMESTEPS_RAW[level],
                            "sample": sample,
                            "candidate_state_hash": phase_hash(bounded),
                            "control_state_hash": exact_hash,
                        }
                        x_raw = bounded_rational_error(bounded, exact)
                        p_raw = bounded_rational_error(bounded, exact, True)
                        x_physical = x_raw * LQ
                        p_physical = p_raw * PQ
                        bounded_decimal = physical_state_decimal_from_phase(bounded)
                        state_error = foundation.state_norm_difference(
                            bounded_decimal, exact_decimal, len(bounded.packets),
                        )
                        smooth_error_trace.append(foundation.state_norm_difference(
                            bounded_decimal,
                            registered_smooth[sample],
                            len(bounded.packets),
                        ))
                        bounded_relations, bounded_potential, _operations = force_and_energy(
                            model, bounded
                        )
                        bounded_energy = (
                            bounded_kinetic_energy(bounded) + bounded_potential
                        )
                        energy_error = bounded_energy - exact_energy
                        potential_match = bounded_potential == exact_potential
                        force_matches = sum(
                            1
                            for bounded_relation, exact_relation in zip(
                                bounded_relations, exact_relations
                            )
                            if (
                                bounded_relation.relation == exact_relation[0]
                                and struct.unpack(
                                    ">Q", struct.pack(">d", bounded_relation.length)
                                )[0] == struct.unpack(
                                    ">Q", struct.pack(">d", exact_relation[2])
                                )[0]
                                and struct.unpack(
                                    ">Q", struct.pack(">d", bounded_relation.conjugate)
                                )[0] == struct.unpack(
                                    ">Q", struct.pack(">d", exact_relation[3])
                                )[0]
                            )
                        )
                        force_match = (
                            len(bounded_relations) == len(exact_relations) == force_matches
                        )
                        energy_bound = kinetic_difference_radius_bound(
                            bounded, exact, p_radii
                        )
                        energy_contained = (
                            potential_match and abs(energy_error) <= energy_bound
                        )
                        certificate = short_energy_certificate[precision]
                        certificate["samples"] = int(certificate["samples"]) + 1
                        certificate["potential_binary64_value_matches"] = (
                            int(certificate["potential_binary64_value_matches"])
                            + int(potential_match)
                        )
                        certificate["force_scalar_pairs"] = (
                            int(certificate["force_scalar_pairs"]) + len(exact_relations)
                        )
                        certificate["force_scalar_bit_matches"] = (
                            int(certificate["force_scalar_bit_matches"]) + force_matches
                        )
                        certificate["maximum_energy_residual"] = max(
                            certificate["maximum_energy_residual"], abs(energy_error)
                        )
                        certificate["maximum_componentwise_energy_bound"] = max(
                            certificate["maximum_componentwise_energy_bound"], energy_bound
                        )
                        short_energy_bound_pass[precision] = (
                            short_energy_bound_pass[precision]
                            and force_match and energy_contained
                        )
                        verify_representation_error_row(
                            row, identity, x_raw, p_raw, energy_error,
                        )
                        exact_structure_envelopes["representation_position"][precision] = max(
                            exact_structure_envelopes["representation_position"][precision],
                            x_physical,
                        )
                        exact_structure_envelopes["representation_momentum"][precision] = max(
                            exact_structure_envelopes["representation_momentum"][precision],
                            p_physical,
                        )
                        exact_structure_envelopes["representation_energy"][precision] = max(
                            exact_structure_envelopes["representation_energy"][precision],
                            abs(energy_error),
                        )
                        maximum_x = max(maximum_x, x_physical)
                        maximum_p = max(maximum_p, p_physical)
                        maximum_state = max(maximum_state, state_error)
                        if sample < STEP_COUNTS[level]:
                            exact_stages, exact_forces = rational_traces[sample]
                            (
                                x_radii, p_radii,
                                recurrence_passed, paired_relations,
                            ) = advance_bounded_rational_step_bound(
                                bounded_stage_map, bounded_force_map,
                                sample + 1, certified_exact,
                                exact_stages, exact_forces, TIMESTEPS_RAW[level],
                                path, x_radii, p_radii,
                            )
                            certified_exact = exact_stages["committed"]
                            certificate["paired_kick_relations"] = (
                                int(certificate["paired_kick_relations"])
                                + paired_relations
                            )
                            short_energy_bound_pass[precision] = (
                                short_energy_bound_pass[precision]
                                and recurrence_passed
                            )
                    envelope[(scenario, path, level, precision)] = (
                        maximum_x, maximum_p, maximum_state
                    )
                    bounded_smooth_samples[(scenario, path, level, precision)] = (
                        smooth_error_trace
                    )

    precision_scaling = True
    component_budget_pass: dict[int, bool] = {precision: True for precision in PRECISIONS}
    for scenario in SCENARIOS:
        for path in (CONTROL, KDK):
            for level in LEVELS:
                values = [envelope[(scenario, path, level, precision)] for precision in PRECISIONS]
                for component_index, budget in ((0, POSITION_BUDGET), (1, MOMENTUM_BUDGET)):
                    reached_budget = False
                    prior = Fraction()
                    prior_precision = 0
                    for precision, value in zip(PRECISIONS, values):
                        current = value[component_index]
                        component_budget_pass[precision] = (
                            component_budget_pass[precision] and current <= budget
                        )
                        if prior_precision and not reached_budget and prior != 0:
                            precision_scaling = precision_scaling and current < prior
                            precision_scaling = precision_scaling and (
                                current <= 4 * Fraction(1, 2 ** (precision - prior_precision)) * prior
                            )
                        if prior_precision and prior == 0:
                            precision_scaling = precision_scaling and current == 0
                        reached_budget = reached_budget or current <= budget
                        if reached_budget:
                            precision_scaling = precision_scaling and current <= budget
                        prior, prior_precision = current, precision
                truncation = exact_truncation[(scenario, path, level)]
                reached_truncation = False
                prior_state = Decimal()
                prior_precision = 0
                for precision, value in zip(PRECISIONS, values):
                    current_state = value[2]
                    if prior_precision and not reached_truncation and prior_state != 0:
                        precision_scaling = precision_scaling and current_state < prior_state
                        precision_scaling = precision_scaling and (
                            current_state
                            <= Decimal(4) * (Decimal(2) ** (-(precision - prior_precision)))
                            * prior_state
                        )
                    if prior_precision and prior_state == 0:
                        precision_scaling = precision_scaling and current_state == 0
                    reached_truncation = (
                        reached_truncation or current_state <= truncation
                    )
                    if reached_truncation:
                        precision_scaling = (
                            precision_scaling
                            and current_state <= truncation
                        )
                    prior_state, prior_precision = current_state, precision

    convergence: dict[str, object] = {}
    temporal_pass: dict[int, bool] = {precision: True for precision in PRECISIONS}
    internal_velocity_temporal_pass: dict[int, bool] = {
        precision: False for precision in PRECISIONS
    }
    control_scenarios: dict[int, dict[str, bool]] = {
        precision: {} for precision in PRECISIONS
    }
    truncation_margin_pass: dict[int, bool] = {precision: True for precision in PRECISIONS}
    for precision in PRECISIONS:
        precision_report: dict[str, object] = {}
        for scenario in SCENARIOS:
            scenario_report: dict[str, object] = {}
            orders_by_path: dict[str, list[float]] = {}
            for path in (CONTROL, KDK):
                errors = [
                    foundation.state_norm_difference(
                        physical_state_decimal_from_phase(
                            trajectories[(precision, scenario, path, level)].final
                        ),
                        smooth[scenario],
                        len(trajectories[(precision, scenario, path, level)].final.packets),
                    )
                    for level in LEVELS
                ]
                require(all(error > 0 for error in errors), "zero smooth endpoint error")
                orders = [math.log2(float(errors[index] / errors[index + 1])) for index in range(4)]
                orders_by_path[path] = orders
                scenario_report[path] = {
                    "errors": [format(error, ".29E") for error in errors],
                    "orders": orders,
                }
                if path == KDK:
                    for level, error in enumerate(errors):
                        representation = envelope[(scenario, path, level, precision)][2]
                        rational_truncation = exact_truncation[(scenario, path, level)]
                        truncation_margin_pass[precision] = (
                            truncation_margin_pass[precision]
                            and representation <= Decimal("0.1") * rational_truncation
                        )
            kdk_window = contains_window(orders_by_path[KDK], 1.6, 2.4, 3)
            control_window = contains_window(orders_by_path[CONTROL], 0.6, 1.4, 2)
            separated = max(orders_by_path[KDK]) - max(orders_by_path[CONTROL]) >= 0.5
            scenario_report["candidate_second_order_window"] = kdk_window
            scenario_report["control_distinguishable"] = control_window and separated
            temporal_pass[precision] = temporal_pass[precision] and kdk_window
            if scenario == "k4_internal":
                internal_velocity_temporal_pass[precision] = kdk_window
            control_scenarios[precision][scenario] = control_window and separated
            precision_report[scenario] = scenario_report
        convergence[str(precision)] = precision_report

    control_pass = aggregate_precision_scenario_gate(control_scenarios)
    selectable_representation = {
        precision: (
            component_budget_pass[precision]
            and truncation_margin_pass[precision]
            and short_energy_bound_pass[precision]
        )
        for precision in PRECISIONS
    }
    return {
        "compact_exact_error_inventory": inventory_report,
        "exact_error_commitments_independently_reproduced": True,
        "bounded_displays_independently_reproduced": True,
        "precision_scaling": precision_scaling,
        "precision_scaling_cutoff": "R_state<=T_exact_Q_vs_smooth",
        "selection_margin": "R_state<=0.1*T_exact_Q_vs_smooth",
        "component_budget_pass": component_budget_pass,
        "truncation_margin_pass": truncation_margin_pass,
        "short_energy_componentwise_certificates": {
            str(precision): {
                name: ratio_text(value) if isinstance(value, Fraction) else value
                for name, value in certificate.items()
            } | {"passed": short_energy_bound_pass[precision]}
            for precision, certificate in short_energy_certificate.items()
        },
        "exact_rational_smooth_truncation": {
            f"{scenario}:{path}:L{level}": format(value, ".29E")
            for (scenario, path, level), value in exact_truncation.items()
        },
        "exact_rational_smooth_sample_errors": {
            f"{scenario}:{path}:L{level}": [
                format(value, ".29E") for value in values
            ]
            for (scenario, path, level), values in exact_truncation_samples.items()
        },
        "bounded_smooth_sample_errors": {
            f"{scenario}:{path}:L{level}:B{precision}": [
                format(value, ".29E") for value in values
            ]
            for (scenario, path, level, precision), values in bounded_smooth_samples.items()
        },
        "convergence": convergence,
        # Keep the aggregate for a concise experiment-wide diagnostic, but do
        # not use it to make a precision selectable.  The control is evaluated
        # independently at every registered arithmetic precision.
        "control_distinguishable": all(control_pass.values()),
        "control_distinguishable_by_precision": control_pass,
        "kdk_all_scenarios_second_order": temporal_pass,
        "kdk_internal_velocity_second_order": internal_velocity_temporal_pass,
        "maximum_representation_envelopes": {
            f"{scenario}:{path}:L{level}:B{precision}": {
                "position": ratio_text(values[0]),
                "momentum": ratio_text(values[1]),
                "state_norm": format(values[2], ".29E"),
            }
            for (scenario, path, level, precision), values in envelope.items()
        },
    }, {
        precision: temporal_pass[precision] and selectable_representation[precision]
        for precision in PRECISIONS
    }, internal_velocity_temporal_pass[256], exact_structure_envelopes


def physical_state_decimal_from_phase(state: PhaseState) -> list[Decimal]:
    packets = sorted(state.packets, key=lambda packet: packet.identifier)
    result = [decimal_value(value * LQ) for packet in packets for value in packet.x]
    result.extend(decimal_value(value * PQ) for packet in packets for value in packet.p)
    return result


def relative_state_error(first: PhaseState, second: PhaseState, momentum: bool = False) -> Fraction:
    left = sorted(first.packets, key=lambda packet: packet.identifier)
    right = sorted(second.packets, key=lambda packet: packet.identifier)
    require([packet.identifier for packet in left] == [packet.identifier for packet in right],
            "covariance packet IDs differ")
    maximum = Fraction()
    for index in range(1, len(left)):
        left_vector = left[index].p if momentum else left[index].x
        left_origin = left[0].p if momentum else left[0].x
        right_vector = right[index].p if momentum else right[index].x
        right_origin = right[0].p if momentum else right[0].x
        for axis in range(3):
            maximum = max(
                maximum,
                abs((left_vector[axis] - left_origin[axis])
                    - (right_vector[axis] - right_origin[axis])),
            )
    return maximum


def inverse_rotate(state: PhaseState) -> PhaseState:
    result = state.clone()
    for packet in result.packets:
        packet.x = [packet.x[1], -packet.x[0], packet.x[2]]
        packet.p = [packet.p[1], -packet.p[0], packet.p[2]]
    return result


def timestep_contraction_profile(
    values: Sequence[Fraction], floor: Fraction,
) -> tuple[bool, bool]:
    """Return qualitative h-contraction and separate floor attainment.

    Strict contraction without reaching the registered budget is convergent
    but not yet selectable.  Once an envelope is below the floor, finer levels
    may plateau but may not leave it.  Exact zero is closed under refinement.
    """
    require(len(values) == len(LEVELS) and floor > 0,
            "invalid timestep-contraction inventory")
    reached_floor = values[0] <= floor
    prior = values[0]
    for current in values[1:]:
        require(current >= 0, "negative timestep residual envelope")
        if prior == 0 and current != 0:
            return False, reached_floor
        if reached_floor:
            if current > floor:
                return False, reached_floor
        elif current >= prior:
            return False, reached_floor
        reached_floor = reached_floor or current <= floor
        prior = current
    return True, reached_floor


def timestep_contraction_until_floor(
    values: Sequence[Fraction], floor: Fraction,
) -> bool:
    """Compatibility predicate requiring both contraction and floor entry."""
    qualitative, attained = timestep_contraction_profile(values, floor)
    return qualitative and attained


def stage_event_signature(
    record: tuple[
        int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
        tuple[Fraction, Fraction, Fraction],
    ],
) -> tuple[str, str, str, str]:
    _step, stage, state, _momentum_bound, _angular_bound = record
    momentum, angular = exact_state_invariants(state)
    return stage, phase_hash(state), vector_hash(momentum), vector_hash(angular)


def force_event_signature(
    record: tuple[int, str, dict[str, object]],
) -> tuple[object, ...]:
    _step, stage, audit = record
    relation = audit["relation"]
    assert isinstance(relation, Relation)
    return (
        stage, relation.index, relation.first_id, relation.second_id,
        audit["length_bits"], audit["conjugate_bits"],
        audit["causal_offset_raw_hash"], audit["exact_stored_offset_raw_hash"],
        audit["ideal_impulse_raw_hash"], audit["first_actual_impulse_raw_hash"],
        audit["second_actual_impulse_raw_hash"],
        *(vector_hash(audit[name]) for name in (
            "pair_momentum_residual", "stored_impulse_centrality_residual",
            "first_actual_centrality_residual", "second_actual_centrality_residual",
            "relation_angular_residual",
        )),
    )


def _observer_frame(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<Q", len(encoded)) + encoded


def observer_event_bytes(kind: str, row: dict[str, object]) -> bytes:
    """Encode a complete observer event without using candidate helpers."""
    if kind == "invariant":
        fields = INVARIANT_FIELDS
    elif kind == "force_audit":
        fields = FORCE_FIELDS
    elif kind == "energy":
        fields = ENERGY_EVENT_FIELDS
    else:
        raise OracleError(f"unknown observer event kind {kind!r}")
    result = bytearray(OBSERVER_EVENT_MAGIC)
    result.extend(_observer_frame(kind))
    result.extend(struct.pack("<Q", len(fields)))
    for field in fields:
        result.extend(_observer_frame(field))
        result.extend(_observer_frame(str(row.get(field, ""))))
    return bytes(result)


def observer_event_digest(kind: str, row: dict[str, object]) -> str:
    return hashlib.sha256(observer_event_bytes(kind, row)).hexdigest()


def observer_stream_sha256(groups: Sequence[Sequence[str]]) -> str:
    result = hashlib.sha256()
    result.update(OBSERVER_STREAM_MAGIC)
    result.update(struct.pack("<Q", len(groups)))
    result.update(struct.pack("<Q", sum(len(group) for group in groups)))
    for group in groups:
        result.update(struct.pack("<Q", len(group)))
        for digest in group:
            require(SHA256.fullmatch(digest) is not None,
                    "observer event digest is not canonical SHA-256")
            result.update(bytes.fromhex(digest))
    return result.hexdigest()


def _observer_add_vector(
    row: dict[str, object], prefix: str, raw_value: Sequence[Fraction],
) -> None:
    require(len(raw_value) == 3, f"{prefix}: observer xyz inventory differs")
    for axis, component in zip("xyz", raw_value):
        row[f"{prefix}_raw_{axis}_dyadic"] = canonical_dyadic_text(component)


def observer_invariant_row(
    trajectory_id: str, precision: int, level: int, step: int, stage: str,
    state: PhaseState,
    baseline: tuple[Sequence[Fraction], Sequence[Fraction]],
) -> dict[str, object]:
    momentum, angular = exact_state_invariants(state)
    row: dict[str, object] = {
        "trajectory_id": trajectory_id,
        "precision": precision,
        "level": level,
        "step": step,
        "stage": stage,
        "state_hash": phase_hash(state),
    }
    del baseline
    _observer_add_vector(row, "momentum", momentum)
    _observer_add_vector(row, "angular", angular)
    return row


def observer_force_row(
    trajectory_id: str, precision: int, level: int, step: int, stage: str,
    audit: dict[str, object],
) -> dict[str, object]:
    relation = audit["relation"]
    assert isinstance(relation, Relation)
    row: dict[str, object] = {
        "trajectory_id": trajectory_id,
        "precision": precision,
        "level": level,
        "step": step,
        "stage": stage,
        "relation_index": relation.index,
        "first_id": relation.first_id,
        "second_id": relation.second_id,
        "length_bits": audit["length_bits"],
        "conjugate_bits": audit["conjugate_bits"],
        "causal_offset_raw_hash": audit["causal_offset_raw_hash"],
        "exact_stored_offset_raw_hash": audit["exact_stored_offset_raw_hash"],
        "ideal_impulse_raw_hash": audit["ideal_impulse_raw_hash"],
        "first_actual_impulse_raw_hash": audit["first_actual_impulse_raw_hash"],
        "second_actual_impulse_raw_hash": audit["second_actual_impulse_raw_hash"],
    }
    scales = {
        "pair_momentum_residual": PQ,
        "stored_impulse_centrality_residual": LQ * PQ,
        "first_actual_centrality_residual": LQ * PQ,
        "second_actual_centrality_residual": LQ * PQ,
        "relation_angular_residual": LQ * PQ,
    }
    for prefix, scale in scales.items():
        physical = audit[prefix]
        assert isinstance(physical, tuple)
        raw_value = tuple(component / scale for component in physical)
        _observer_add_vector(row, prefix, raw_value)
    return row


def observer_energy_row(
    trajectory_id: str, precision: int, level: int, step: int,
    model: Model, state: PhaseState,
) -> dict[str, object]:
    kinetic, potential, mechanical = mechanical_energy(model, state)
    potential_bits = struct.unpack(">Q", struct.pack(">d", float(potential)))[0]
    require(exact_float_bits(potential_bits) == potential,
            "energy observer potential is not an exact binary64 value")
    row: dict[str, object] = {
        "trajectory_id": trajectory_id,
        "precision": precision,
        "level": level,
        "step": step,
        "state_hash": phase_hash(state),
        "potential_binary64_bits": potential_bits,
    }
    for name, value in (
        ("kinetic", kinetic), ("potential", potential), ("mechanical", mechanical),
    ):
        row[f"{name}_num"] = value.numerator
        row[f"{name}_den"] = value.denominator
        row[f"{name}_hash"] = fraction_hash(value)
    return row


def observer_groups_from_replay(
    model: Model, trajectory_id: str, precision: int, level: int,
    trajectory: Trajectory,
    stage_records: Sequence[tuple[
        int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
        tuple[Fraction, Fraction, Fraction],
    ]],
    force_records: Sequence[tuple[int, str, dict[str, object]]],
    baseline: tuple[Sequence[Fraction], Sequence[Fraction]],
    step_offset: int = 0,
) -> list[list[str]]:
    """Reconstruct the complete canonical event stream from exact replay data."""
    stages: dict[tuple[int, str], PhaseState] = {
        (step, stage): state for step, stage, state, _p_bound, _l_bound in stage_records
        if step > 0
    }
    forces: dict[tuple[int, str], list[dict[str, object]]] = defaultdict(list)
    for step, stage, audit in force_records:
        forces[(step, stage)].append(audit)
    groups: list[list[str]] = []
    for local_step in range(1, trajectory.completed_steps + 1):
        absolute_step = step_offset + local_step
        group: list[str] = []
        stage_order = (
            ("first_kick", True), ("drift", False),
            ("second_kick", True), ("committed", False),
        )
        for stage, has_force in stage_order:
            if has_force:
                audits = forces[(local_step, stage)]
                require(len(audits) == len(model.relations),
                        "observer relation-event inventory differs")
                for audit in audits:
                    row = observer_force_row(
                        trajectory_id, precision, level, absolute_step, stage, audit
                    )
                    group.append(observer_event_digest("force_audit", row))
            require((local_step, stage) in stages,
                    "observer invariant stage inventory differs")
            invariant = observer_invariant_row(
                trajectory_id, precision, level, absolute_step, stage,
                stages[(local_step, stage)], baseline,
            )
            group.append(observer_event_digest("invariant", invariant))
        energy = observer_energy_row(
            trajectory_id, precision, level, absolute_step,
            model, trajectory.samples[local_step],
        )
        group.append(observer_event_digest("energy", energy))
        expected_count = 2 * len(model.relations) + 5
        require(len(group) == expected_count,
                "observer per-step causal event count differs")
        groups.append(group)
    require(len(groups) == trajectory.completed_steps,
            "observer step-group inventory differs")
    return groups


def verify_checkpoint_row(
    row: dict[str, str], precision: int, level: int, model: Model,
    initial_state: PhaseState, checkpoint_state: PhaseState,
    baseline_trajectory: Trajectory | None = None,
    operation_rows: dict[str, dict[str, str]] | None = None,
    baseline_trace: tuple[StageTrace, ForceTrace] | None = None,
    auxiliary_replays: dict[str, AuditReplay] | None = None,
) -> None:
    """Verify one checkpoint, including every independently framed suffix event."""
    steps = STEP_COUNTS[level]
    half = steps // 2
    dt_raw = TIMESTEPS_RAW[level]
    trajectory_id = f"short:k4_internal:{KDK}:B{precision}:L{level}"
    require((baseline_trajectory is None) == (baseline_trace is None),
            "checkpoint cached trajectory/trace pairing differs")
    if baseline_trajectory is None:
        whole, whole_stages, whole_forces = run_trajectory(
            model, initial_state, dt_raw, steps, KDK, True
        )
    else:
        whole = baseline_trajectory
        assert baseline_trace is not None
        whole_stages, whole_forces = baseline_trace
    require(whole.status == "accepted" and whole.completed_steps == steps,
            "checkpoint whole trajectory did not complete")
    require(
        encode_phase_state(whole.initial) == encode_phase_state(initial_state),
        "checkpoint whole replay initial state differs",
    )
    require(encode_phase_state(whole.samples[half]) == encode_phase_state(checkpoint_state),
            "interior checkpoint state differs")
    first_id = f"checkpoint:first:B{precision}:L{level}"
    resumed_id = f"checkpoint:resumed:B{precision}:L{level}"
    if auxiliary_replays is None:
        first, _first_stages, _first_forces = run_trajectory(
            model, initial_state, dt_raw, half, KDK
        )
        resumed, resumed_stages, resumed_forces = run_trajectory(
            model, checkpoint_state, dt_raw, half, KDK, True
        )
    else:
        require(first_id in auxiliary_replays and resumed_id in auxiliary_replays,
                "checkpoint auxiliary replay cache entry missing")
        first, _first_stages, _first_forces = auxiliary_replays[first_id]
        resumed, resumed_stages, resumed_forces = auxiliary_replays[resumed_id]
    require(first.status == "accepted" and first.completed_steps == half,
            "checkpoint first-half trajectory did not complete")
    require(resumed.status == "accepted" and resumed.completed_steps == half,
            "checkpoint resumed trajectory did not complete")
    require(
        encode_phase_state(first.initial) == encode_phase_state(initial_state)
        and encode_phase_state(first.final) == encode_phase_state(checkpoint_state)
        and encode_phase_state(resumed.initial) == encode_phase_state(checkpoint_state)
        and encode_phase_state(resumed.final) == encode_phase_state(whole.final),
        "checkpoint cached trajectory association differs",
    )
    initial_time = initial_state.time_raw
    checkpoint_time = initial_time + half * dt_raw
    final_time = initial_time + steps * dt_raw
    require(
        whole.initial.time_raw == initial_time
        and whole.samples[half].time_raw == checkpoint_time
        and whole.final.time_raw == final_time
        and checkpoint_state.time_raw == checkpoint_time
        and first.initial.time_raw == initial_time
        and first.final.time_raw == checkpoint_time
        and resumed.initial.time_raw == checkpoint_time
        and resumed.final.time_raw == final_time,
        "checkpoint cached trajectory time association differs",
    )
    if operation_rows is not None:
        verify_operation_row(
            operation_rows[first_id], first_id, precision, level, KDK,
            model, initial_state, half, first,
        )
        verify_operation_row(
            operation_rows[resumed_id], resumed_id, precision, level, KDK,
            model, checkpoint_state, half, resumed,
        )
    baseline = exact_state_invariants(initial_state)
    whole_groups = observer_groups_from_replay(
        model, trajectory_id, precision, level, whole, whole_stages, whole_forces, baseline
    )
    resumed_groups = observer_groups_from_replay(
        model, trajectory_id, precision, level, resumed, resumed_stages, resumed_forces,
        baseline, half,
    )
    suffix = whole_groups[half:]
    require(resumed_groups == suffix,
            "checkpoint complete observer-event suffix differs")
    suffix_count = sum(len(group) for group in suffix)
    resumed_count = sum(len(group) for group in resumed_groups)
    suffix_hash = observer_stream_sha256(suffix)
    resumed_hash = observer_stream_sha256(resumed_groups)
    checkpoint_bytes = encode_phase_state(checkpoint_state)
    require(
        row["scenario_id"] == "k4_internal"
        and int(row["precision"]) == precision
        and int(row["level"]) == level
        and int(row["dt_raw"]) == dt_raw
        and int(row["steps"]) == steps
        and int(row["checkpoint_step"]) == half
        and row["checkpoint_hash"] == hashlib.sha256(checkpoint_bytes).hexdigest()
        and int(row["checkpoint_bytes"]) == len(checkpoint_bytes)
        and row["decoded_hash"] == phase_hash(checkpoint_state)
        and row["whole_final_hash"] == phase_hash(whole.final)
        and row["resumed_final_hash"] == phase_hash(resumed.final)
        and int(row["whole_suffix_event_count"]) == suffix_count
        and int(row["resumed_event_count"]) == resumed_count
        and row["whole_suffix_event_sha256"] == suffix_hash
        and row["resumed_event_sha256"] == resumed_hash
        and boolean(row["event_suffix_identical"])
        and boolean(row["canonical_round_trip"]),
        "checkpoint/replay contract differs",
    )


def verify_reversal_checkpoint_domain_inventory(
    raw: Path,
) -> tuple[
    dict[tuple[int, str, int], dict[str, str]],
    dict[tuple[int, int], dict[str, str]],
    dict[tuple[int, int], dict[str, str]],
]:
    """Bind each small composition table to its exact canonical row stream."""
    reversal_evidence = rows(raw / "reversibility.csv")
    reversal_keys = [
        (int(row["precision"]), row["scenario_id"], int(row["level"]))
        for row in reversal_evidence
    ]
    expected_reversal = [
        (precision, scenario, level)
        for level in LEVELS for precision in PRECISIONS for scenario in SCENARIOS
    ]
    require(len(reversal_evidence) == len(expected_reversal),
            "reversibility row count differs")
    require(len(set(reversal_keys)) == len(reversal_keys),
            "duplicate reversibility key")
    require(reversal_keys == expected_reversal,
            "reversibility canonical producer order differs")

    expected_profile = [
        (precision, level) for level in LEVELS for precision in PRECISIONS
    ]
    checkpoint_evidence = rows(raw / "checkpoint.csv")
    checkpoint_keys = [
        (int(row["precision"]), int(row["level"]))
        for row in checkpoint_evidence
    ]
    require(len(checkpoint_evidence) == len(expected_profile),
            "checkpoint row count differs")
    require(len(set(checkpoint_keys)) == len(checkpoint_keys),
            "duplicate checkpoint key")
    require(checkpoint_keys == expected_profile,
            "checkpoint canonical producer order differs")

    domain_evidence = rows(raw / "domain.csv")
    domain_keys = [
        (int(row["precision"]), int(row["level"]))
        for row in domain_evidence
    ]
    require(len(domain_evidence) == len(expected_profile),
            "domain row count differs")
    require(len(set(domain_keys)) == len(domain_keys),
            "duplicate domain key")
    require(domain_keys == expected_profile,
            "domain canonical producer order differs")

    return (
        dict(zip(reversal_keys, reversal_evidence)),
        dict(zip(checkpoint_keys, checkpoint_evidence)),
        dict(zip(domain_keys, domain_evidence)),
    )


def verify_reversal_checkpoint_covariance_domain(
    raw: Path,
    state_report: dict[str, object],
    models: dict[str, Model],
    trajectories: dict[tuple[int, str, str, int], Trajectory],
    trajectory_traces: dict[tuple[int, str, str, int], tuple[
        list[tuple[
            int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
            tuple[Fraction, Fraction, Fraction],
        ]],
        list[tuple[int, str, dict[str, object]]],
    ]],
) -> tuple[dict[str, object], dict[int, bool]]:
    initial = state_report["initial"]
    checkpoint_states = state_report["checkpoint"]
    recovery_states = state_report["recovery"]
    assert isinstance(initial, dict) and isinstance(checkpoint_states, dict)
    assert isinstance(recovery_states, dict)
    reversal_rows, checkpoint_rows, domain_rows = (
        verify_reversal_checkpoint_domain_inventory(raw)
    )
    operation_evidence = rows(raw / "operation_counts.csv")
    operation_rows = {row["trajectory_id"]: row for row in operation_evidence}
    require(len(operation_rows) == len(operation_evidence),
            "duplicate operation-count trajectory")
    expected_operation_ids = {
        f"short:{scenario}:{path}:B{precision}:L{level}"
        for scenario in SCENARIOS for path in (CONTROL, KDK)
        for precision in PRECISIONS for level in LEVELS
    } | {
        f"reverse:{scenario}:B{precision}:L{level}"
        for scenario in SCENARIOS for precision in PRECISIONS for level in LEVELS
    } | {
        f"covariance:{kind}:B{precision}:L{level}"
        for kind in ("translation", "galilean_boost", "proper_lattice_rotation")
        for precision in PRECISIONS for level in LEVELS
    } | {
        f"covariance:packet_permutation:B{precision}:L{level}"
        for precision in PRECISIONS for level in LEVELS
    } | {
        f"checkpoint:{kind}:B{precision}:L{level}"
        for kind in ("first", "resumed")
        for precision in PRECISIONS for level in LEVELS
    } | {
        f"long:{scenario}:B{precision}:L{level}"
        for scenario in ("k4_internal", "k4_boosted")
        for precision in PRECISIONS for level in LEVELS
    }
    require(len(expected_operation_ids) == 425
            and set(operation_rows) == expected_operation_ids,
            "complete accepted operation-audit inventory differs")
    auxiliary_audits, auxiliary_replays = verify_auxiliary_audits(
        raw, state_report, models, trajectories, operation_rows
    )
    expected_reversal = {
        (precision, scenario, level)
        for precision in PRECISIONS for scenario in SCENARIOS for level in LEVELS
    }
    require(set(reversal_rows) == expected_reversal, "reversibility inventory differs")

    precision_pass = {precision: True for precision in PRECISIONS}
    recovery_max: dict[int, tuple[Fraction, Fraction]] = {}
    recovery_bound_pass = {precision: True for precision in PRECISIONS}
    recovery_bound_report: dict[str, object] = {}
    complete_checkpoint_event_streams = 0
    for precision, scenario, level in sorted(expected_reversal):
        initial_state = initial[(precision, scenario, "initial", 0)]
        forward = trajectories[(precision, scenario, KDK, level)]
        model = models["octahedron" if scenario == "octahedron_deformation" else "k4"]
        reverse_id = f"reverse:{scenario}:B{precision}:L{level}"
        require(reverse_id in auxiliary_replays,
                "signed-time auxiliary replay cache entry missing")
        backward, backward_stages, backward_forces = auxiliary_replays[reverse_id]
        verify_operation_row(
            operation_rows[reverse_id], reverse_id, precision, level, KDK, model,
            forward.final, STEP_COUNTS[level], backward,
        )
        expected_recovery = recovery_states[(precision, scenario, KDK, level)]
        require(encode_phase_state(backward.final) == encode_phase_state(expected_recovery),
                "signed-time recovery replay differs")
        row = reversal_rows[(precision, scenario, level)]
        x_raw = raw_phase_error(backward.final, initial_state)
        p_raw = raw_phase_error(backward.final, initial_state, True)
        require(
            row["forward_status"] == row["backward_status"] == "accepted"
            and row["initial_hash"] == phase_hash(initial_state)
            and row["recovered_hash"] == phase_hash(backward.final)
            and boolean(row["complete_state_identical"]) == (
                encode_phase_state(backward.final) == encode_phase_state(initial_state)
            ),
            "signed-time recovery declaration differs",
        )
        for prefix, expected in (
            ("position_raw_error", x_raw), ("position_physical_error", x_raw * LQ),
            ("momentum_raw_error", p_raw), ("momentum_physical_error", p_raw * PQ),
        ):
            require(scalar_from_columns(row, prefix) == expected,
                    f"reversibility {prefix} differs")
        old = recovery_max.get(precision, (Fraction(), Fraction()))
        recovery_max[precision] = (max(old[0], x_raw * LQ), max(old[1], p_raw * PQ))
        forward_stages, forward_forces = trajectory_traces[
            (precision, scenario, KDK, level)
        ]
        certificate = paired_reversal_bound_certificate(
            forward, forward_stages, forward_forces,
            backward, backward_stages, backward_forces,
            TIMESTEPS_RAW[level],
        )
        recovery_bound_report[f"{scenario}:B{precision}:L{level}"] = certificate
        recovery_bound_pass[precision] = (
            recovery_bound_pass[precision] and bool(certificate["passed"])
        )

    for precision in PRECISIONS:
        for level in LEVELS:
            baseline = trajectories[(precision, "k4_internal", KDK, level)]
            half = STEP_COUNTS[level] // 2
            expected_checkpoint = checkpoint_states[(precision, "k4_internal", KDK, level)]
            row = checkpoint_rows[(precision, level)]
            verify_checkpoint_row(
                row, precision, level, models["k4"],
                initial[(precision, "k4_internal", "initial", 0)],
                expected_checkpoint, baseline, operation_rows,
                trajectory_traces[(precision, "k4_internal", KDK, level)],
                auxiliary_replays,
            )
            complete_checkpoint_event_streams += 1

            crossing = initial[(precision, "domain_crossing", "initial", 0)]
            first_kick, _operations, _audit = kick(models["pair"], crossing,
                                                   500_000_000)
            proposed = first_kick.clone()
            for packet in proposed.packets:
                coefficient = rn(Fraction(1_000_000_000, packet.mass_raw), precision)
                displacement = [rn(coefficient * packet.p[axis], precision) for axis in range(3)]
                packet.x = [rn(packet.x[axis] + displacement[axis], precision) for axis in range(3)]
            failures: list[tuple[Relation, DomainCertificate]] = []
            for relation in models["pair"].relations:
                before = exact_stored_relation_offset(first_kick, relation)
                after = exact_stored_relation_offset(proposed, relation)
                certificate = bounded_chord_certificate(
                    before, after, reference_offset(models["pair"], relation), precision
                )
                if not certificate.safe:
                    failures.append((relation, certificate))
            require(len(failures) == 1, "domain crossing certificate count differs")
            relation, certificate = failures[0]
            row = domain_rows[(precision, level)]
            domain_trajectory = f"domain:B{precision}:L{level}"
            energy_row = observer_energy_row(
                domain_trajectory, precision, level, 0, models["pair"], crossing
            )
            energy_digest = observer_event_digest("energy", energy_row)
            require(
                row["scenario_id"] == "domain_crossing"
                and row["status"] == "chord_domain_failure"
                and row["prior_hash"] == row["returned_hash"] == phase_hash(crossing)
                and boolean(row["time_unchanged"]) and boolean(row["state_unchanged"])
                and int(row["event_rows_emitted"]) == 0
                and not boolean(row["energy_ledger_present"])
                and int(row["observer_events_emitted"]) == 0
                and row["prior_energy_observation_sha256"] == energy_digest
                and row["returned_energy_observation_sha256"] == energy_digest
                and boolean(row["energy_observation_unchanged"])
                and int(row["offending_relation_index"]) == relation.index
                and row["chord_minimum_case"] == certificate.minimum_case
                and scalar_from_columns(row, "comparison_lhs") == certificate.lhs
                and scalar_from_columns(row, "comparison_rhs") == certificate.rhs
                and int(row["domain_scratch_observed_bits"])
                    == certificate.scratch_observed_bits
                and int(row["domain_scratch_limit_bits"])
                    == certificate.scratch_limit_bits
                and certificate.scratch_observed_bits <= certificate.scratch_limit_bits
                and certificate.lhs < certificate.rhs,
                "domain rejection/certificate differs",
            )

    covariance_groups = grouped(
        (row for row in rows(raw / "covariance.csv") if row["scope"] == "short"),
        ("kind", "precision", "level"),
    )
    require(set(covariance_groups) == {
        (kind, str(precision), str(level))
        for kind in ("translation", "galilean_boost", "proper_lattice_rotation", "packet_permutation")
        for precision in PRECISIONS for level in LEVELS
    }, "short covariance inventory differs")
    covariance_max: dict[int, tuple[Fraction, Fraction]] = {}
    covariance_level: dict[tuple[str, int, int], tuple[Fraction, Fraction, Fraction, Fraction]] = {}
    frame_bound_pass = {precision: True for precision in PRECISIONS}
    frame_bound_report: dict[str, object] = {}
    rotation_classification: dict[tuple[int, int], str] = {}
    for precision in PRECISIONS:
        for level in LEVELS:
            baseline = trajectories[(precision, "k4_internal", KDK, level)]
            baseline_stages, baseline_forces = trajectory_traces[
                (precision, "k4_internal", KDK, level)
            ]
            transformed_runs: dict[str, tuple[
                Trajectory, list[PhaseState], PhaseState, Model,
                list[tuple[
                    int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
                    tuple[Fraction, Fraction, Fraction],
                ]],
                list[tuple[int, str, dict[str, object]]],
            ]] = {}
            for kind, scenario, model_name in (
                ("translation", "k4_translated", "k4_translated"),
                ("galilean_boost", "k4_boosted", "k4"),
                ("proper_lattice_rotation", "k4_rotated", "k4_rotated"),
            ):
                operation_id = f"covariance:{kind}:B{precision}:L{level}"
                require(operation_id in auxiliary_replays,
                        "covariance auxiliary replay cache entry missing")
                candidate, candidate_stages, candidate_forces = (
                    auxiliary_replays[operation_id]
                )
                transformed = [
                    inverse_rotate(state) if kind == "proper_lattice_rotation" else state
                    for state in candidate.samples
                ]
                transformed_runs[kind] = (
                    candidate, transformed,
                    initial[(precision, scenario, "initial", 0)], models[model_name],
                    candidate_stages, candidate_forces,
                )
                verify_operation_row(
                    operation_rows[operation_id], operation_id, precision, level, KDK,
                    models[model_name], initial[(precision, scenario, "initial", 0)],
                    STEP_COUNTS[level], candidate,
                )
            permuted = initial[(precision, "k4_internal", "initial", 0)].clone()
            permuted.packets.reverse()
            permutation_id = f"covariance:packet_permutation:B{precision}:L{level}"
            require(permutation_id in auxiliary_replays,
                    "permutation auxiliary replay cache entry missing")
            permutation, permutation_stages, permutation_forces = (
                auxiliary_replays[permutation_id]
            )
            verify_operation_row(
                operation_rows[permutation_id], permutation_id, precision, level, KDK,
                models["k4"], permuted, STEP_COUNTS[level], permutation,
            )
            transformed_runs["packet_permutation"] = (
                permutation, permutation.samples, permuted, models["k4"],
                permutation_stages, permutation_forces,
            )
            for kind, (
                candidate, transformed, _candidate_initial, _model,
                candidate_stages, candidate_forces,
            ) in transformed_runs.items():
                evidence = covariance_groups[(kind, str(precision), str(level))]
                require(len(evidence) == len(baseline.samples) == len(transformed),
                        "short covariance sample count differs")
                level_x = Fraction()
                level_p = Fraction()
                final_x = Fraction()
                final_p = Fraction()
                all_bit_identical = True
                for sample, (row, first, second) in enumerate(zip(evidence, baseline.samples, transformed)):
                    x_raw = relative_state_error(first, second)
                    p_raw = relative_state_error(first, second, True)
                    bit_identical = encode_phase_state(first) == encode_phase_state(second)
                    require(
                        int(row["sample"]) == sample
                        and row["baseline_hash"] == phase_hash(first)
                        and row["transformed_hash"] == phase_hash(second)
                        and boolean(row["bit_identical"]) == bit_identical,
                        "short covariance hashes/classification differ",
                    )
                    for prefix, expected in (
                        ("relative_position_raw", x_raw),
                        ("relative_position_physical", x_raw * LQ),
                        ("relative_momentum_raw", p_raw),
                        ("relative_momentum_physical", p_raw * PQ),
                    ):
                        require(scalar_from_columns(row, prefix) == expected,
                                f"short covariance {prefix} differs")
                    old = covariance_max.get(precision, (Fraction(), Fraction()))
                    covariance_max[precision] = (
                        max(old[0], x_raw * LQ), max(old[1], p_raw * PQ)
                    )
                    level_x = max(level_x, x_raw * LQ)
                    level_p = max(level_p, p_raw * PQ)
                    final_x = x_raw * LQ
                    final_p = p_raw * PQ
                    all_bit_identical = all_bit_identical and bit_identical
                covariance_level[(kind, precision, level)] = (
                    level_x, level_p, final_x, final_p
                )
                if kind == "proper_lattice_rotation":
                    if all_bit_identical:
                        classification = "bit_exact"
                    elif level_x == 0 and level_p == 0:
                        classification = "exact_dyadic"
                    elif level_x <= POSITION_BUDGET and level_p <= MOMENTUM_BUDGET:
                        classification = "precision_bounded"
                    else:
                        classification = "unresolved"
                    rotation_classification[(precision, level)] = classification
                if kind in {"translation", "galilean_boost"}:
                    certificate = paired_frame_bound_certificate(
                        baseline, baseline_stages, baseline_forces,
                        candidate, candidate_stages, candidate_forces,
                        TIMESTEPS_RAW[level],
                    )
                else:
                    certificate = exact_discrete_equivariance_certificate(
                        baseline_stages, baseline_forces,
                        candidate_stages, candidate_forces,
                        kind == "proper_lattice_rotation",
                    )
                    certificate["sampled_relative_residuals_exact_zero"] = (
                        level_x == 0 and level_p == 0
                    )
                    certificate["passed"] = (
                        bool(certificate["passed"])
                        and bool(certificate["sampled_relative_residuals_exact_zero"])
                    )
                frame_bound_report[f"short:{kind}:B{precision}:L{level}"] = certificate
                frame_bound_pass[precision] = (
                    frame_bound_pass[precision] and bool(certificate["passed"])
                )

    rotation_precision_scaling: dict[int, bool] = {}
    for level in LEVELS:
        rotation_x = {
            precision: covariance_level[("proper_lattice_rotation", precision, level)][0]
            for precision in PRECISIONS
        }
        rotation_p = {
            precision: covariance_level[("proper_lattice_rotation", precision, level)][1]
            for precision in PRECISIONS
        }
        rotation_precision_scaling[level] = (
            scaling_until_budget(rotation_x, POSITION_BUDGET)
            and scaling_until_budget(rotation_p, MOMENTUM_BUDGET)
        )
        if rotation_precision_scaling[level]:
            for precision in PRECISIONS:
                if rotation_classification[(precision, level)] == "unresolved":
                    rotation_classification[(precision, level)] = (
                        "precision_convergent_above_budget"
                    )

    boost_timestep: dict[int, dict[str, object]] = {}
    for precision in PRECISIONS:
        recovery = recovery_max[precision]
        covariance = covariance_max[precision]
        x_values = [
            covariance_level[("galilean_boost", precision, level)][0]
            for level in LEVELS
        ]
        p_values = [
            covariance_level[("galilean_boost", precision, level)][1]
            for level in LEVELS
        ]
        x_qualitative, x_attained = timestep_contraction_profile(
            x_values, POSITION_BUDGET
        )
        p_qualitative, p_attained = timestep_contraction_profile(
            p_values, MOMENTUM_BUDGET
        )
        boost_timestep[precision] = {
            "position_maxima": [ratio_text(value) for value in x_values],
            "momentum_maxima": [ratio_text(value) for value in p_values],
            "position_qualitative_contraction": x_qualitative,
            "position_floor_attained": x_attained,
            "position_contracts_until_floor": x_qualitative and x_attained,
            "momentum_qualitative_contraction": p_qualitative,
            "momentum_floor_attained": p_attained,
            "momentum_contracts_until_floor": p_qualitative and p_attained,
        }
        precision_pass[precision] = (
            recovery[0] <= POSITION_BUDGET and recovery[1] <= MOMENTUM_BUDGET
            and covariance[0] <= POSITION_BUDGET and covariance[1] <= MOMENTUM_BUDGET
            and recovery_bound_pass[precision]
            and frame_bound_pass[precision]
            and x_qualitative and x_attained and p_qualitative and p_attained
            and all(
                covariance_level[("proper_lattice_rotation", precision, level)][0]
                    <= POSITION_BUDGET
                and covariance_level[("proper_lattice_rotation", precision, level)][1]
                    <= MOMENTUM_BUDGET
                for level in LEVELS
            )
        )
    return {
        "recovery_max": {str(k): [ratio_text(v[0]), ratio_text(v[1])] for k, v in recovery_max.items()},
        "covariance_max": {str(k): [ratio_text(v[0]), ratio_text(v[1])] for k, v in covariance_max.items()},
        "signed_time_recovery_summed_local_half_ulp_certificates": recovery_bound_report,
        "signed_time_recovery_bound_pass": {
            str(precision): value for precision, value in recovery_bound_pass.items()
        },
        "short_frame_summed_local_half_ulp_certificates": frame_bound_report,
        "short_frame_bound_pass": {
            str(precision): value for precision, value in frame_bound_pass.items()
        },
        "checkpoint_rows": len(checkpoint_rows),
        "independent_complete_checkpoint_event_streams": complete_checkpoint_event_streams,
        "domain_rows": len(domain_rows),
        "complete_accepted_rounding_audit_rows": len(operation_rows),
        "complete_accepted_invariant_force_audit_invocations": (
            150 + int(auxiliary_audits["invocations"]) + 50
        ),
        "auxiliary_invariant_force_audits": auxiliary_audits,
        "rounding_audit_records_and_hashes_independently_reproduced": True,
        "boost_timestep_contraction": {
            str(precision): value for precision, value in boost_timestep.items()
        },
        "proper_lattice_rotation_classification": {
            f"B{precision}:L{level}": rotation_classification[(precision, level)]
            for precision in PRECISIONS for level in LEVELS
        },
        "proper_lattice_rotation_precision_scaling": {
            f"L{level}": rotation_precision_scaling[level] for level in LEVELS
        },
        "highest_precision_frame_contract": (
            boost_timestep[256]["position_qualitative_contraction"]
            and boost_timestep[256]["momentum_qualitative_contraction"]
            and all(rotation_precision_scaling.values())
        ),
    }, precision_pass


def raw_phase_error(first: PhaseState, second: PhaseState, momentum: bool = False) -> Fraction:
    left = packet_lookup(first)
    right = packet_lookup(second)
    require(set(left) == set(right), "phase error packet IDs differ")
    name = "p" if momentum else "x"
    return max(
        (
            abs(getattr(left[identifier], name)[axis] - getattr(right[identifier], name)[axis])
            for identifier in left for axis in range(3)
        ),
        default=Fraction(),
    )


def chord_certificate(
    initial: Sequence[Fraction], final: Sequence[Fraction], reference: Sequence[Fraction],
) -> tuple[bool, str, Fraction, Fraction]:
    delta = vector_sub(final, initial)
    dd = dot(delta, delta)
    aa = dot(initial, initial)
    ad = dot(initial, delta)
    reference_squared = dot(reference, reference)
    require(reference_squared > 0, "zero reference relation")
    if dd == 0 or ad >= 0:
        rhs = SAFE_SQUARED_RATIO * reference_squared
        return aa >= rhs, "initial", aa, rhs
    if ad <= -dd:
        endpoint = vector_add(initial, delta)
        lhs = dot(endpoint, endpoint)
        rhs = SAFE_SQUARED_RATIO * reference_squared
        return lhs >= rhs, "final", lhs, rhs
    lhs = aa * dd - ad * ad
    rhs = SAFE_SQUARED_RATIO * reference_squared * dd
    return lhs >= rhs, "interior", lhs, rhs


def ratio_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def least_squares_slope(values: Sequence[Fraction], dt: Fraction) -> Fraction:
    if len(values) < 2:
        return Fraction()
    x_mean = Fraction(len(values) - 1, 2)
    y_mean = sum(values, Fraction()) / len(values)
    numerator = sum(
        ((Fraction(index) - x_mean) * (value - y_mean) for index, value in enumerate(values)),
        Fraction(),
    )
    denominator = sum(
        ((Fraction(index) - x_mean) ** 2 for index in range(len(values))), Fraction()
    )
    return numerator / denominator / dt


def phase_trace_difference_statistics(
    candidate: Sequence[PhaseState], anchor: Sequence[PhaseState], start: int,
    scale: Fraction, momentum: bool, dt: Fraction,
) -> tuple[Fraction, Fraction, Fraction]:
    require(len(candidate) == len(anchor), "anchor phase-trace lengths differ")
    if start >= len(candidate):
        return Fraction(), Fraction(), Fraction()
    component_series: list[list[Fraction]] = []
    identifiers = sorted(packet_lookup(candidate[0]))
    for identifier in identifiers:
        for axis in range(3):
            values: list[Fraction] = []
            for candidate_state, anchor_state in zip(candidate[start:], anchor[start:]):
                left = packet_lookup(candidate_state)[identifier]
                right = packet_lookup(anchor_state)[identifier]
                left_vector = left.p if momentum else left.x
                right_vector = right.p if momentum else right.x
                values.append((left_vector[axis] - right_vector[axis]) * scale)
            component_series.append(values)
    maximum = max(
        (abs(value) for series in component_series for value in series),
        default=Fraction(),
    )
    final = max((abs(series[-1]) for series in component_series), default=Fraction())
    slope = max(
        (abs(least_squares_slope(series, dt)) for series in component_series),
        default=Fraction(),
    )
    return maximum, final, slope


def take_evidence_rows(
    iterator: Iterable[dict[str, str]], count: int, label: str,
) -> list[dict[str, str]]:
    source = iter(iterator)
    result: list[dict[str, str]] = []
    for _ in range(count):
        try:
            result.append(next(source))
        except StopIteration as error:
            raise OracleError(f"{label} evidence ended early") from error
    return result


def verify_long_replay(
    raw: Path,
    parent_raw: Path,
    state_report: dict[str, object],
    models: dict[str, Model],
) -> tuple[
    dict[str, object], dict[int, bool], bool,
    dict[str, dict[int, Fraction]],
]:
    initial = state_report["initial"]
    long_endpoints = state_report["long_endpoint"]
    assert isinstance(initial, dict) and isinstance(long_endpoints, dict)
    parent_initial = grouped(rows(parent_raw / "initial_states.csv"), ("scenario_id",))
    comparator_rows = {
        (row["scenario_id"], int(row["level"])): row
        for row in rows(raw / "rational_comparator.csv")
    }
    expected_comparators = {
        (scenario, level)
        for scenario in ("k4_internal", "k4_boosted") for level in LEVELS
    }
    require(set(comparator_rows) == expected_comparators,
            "exact-rational comparator receipt inventory differs")
    prefix_steps: dict[tuple[str, int], int] = {}
    for (scenario, level), row in comparator_rows.items():
        requested = 16 * STEP_COUNTS[level]
        completed = int(row["completed_steps"])
        require(
            row["scope"] == "long_exact_comparator"
            and row["path"] == KDK
            and int(row["dt_raw"]) == TIMESTEPS_RAW[level]
            and int(row["requested_steps"]) == requested
            and int(row["comparison_samples"]) == completed + 1
            and int(row["last_comparator_sample"]) == completed
            and int(row["first_comparator_free_sample"]) == completed + 1
            and int(row["maximum_component_bits_limit"]) == EXACT_MAX_COMPONENT_BITS
            and int(row["median_component_bits_limit"]) == EXACT_MEDIAN_COMPONENT_BITS
            and int(row["maximum_checkpoint_bytes_limit"]) == EXACT_MAX_CHECKPOINT_BYTES,
            f"{scenario}:L{level}: exact-comparator receipt contract differs",
        )
        prefix_steps[(scenario, level)] = completed
    require(
        {level: prefix_steps[("k4_internal", level)] for level in LEVELS}
        == {0: 256, 1: 405, 2: 403, 3: 400, 4: 398},
        "sealed internal exact-control crossing differs",
    )

    representation_iterator = iter(
        row for row in iter_rows(raw / "representation_error.csv")
        if row["scope"] == "long_exact_prefix"
    )
    energy_iterator = iter(iter_rows(raw / "long_energy.csv"))
    covariance_iterator = iter(
        row for row in iter_rows(raw / "covariance.csv") if row["scope"] == "long"
    )
    operation_rows = {
        row["trajectory_id"]: row
        for row in rows(raw / "operation_counts.csv")
        if row["trajectory_id"].startswith("long:")
    }
    require(len(operation_rows) == 2 * len(PRECISIONS) * len(LEVELS),
            "long operation inventory differs")

    invariant_iterator = iter(
        row for row in iter_rows(raw / "invariants.csv")
        if row["trajectory_id"].startswith("long:")
    )
    force_iterator = iter(
        row for row in iter_rows(raw / "force_audit.csv")
        if row["trajectory_id"].startswith("long:")
    )
    precision_pass = {precision: True for precision in PRECISIONS}
    report: dict[str, object] = {}
    momentum_series: dict[tuple[int, int, str], list[tuple[Fraction, Fraction, Fraction]]] = {}
    angular_series: dict[tuple[int, int, str], list[tuple[Fraction, Fraction, Fraction]]] = {}
    energy_error_series: dict[tuple[int, int], list[Fraction]] = {}
    mechanical_energy_series: dict[tuple[int, int], list[Fraction]] = {}
    prefix_state_series: dict[
        tuple[int, int, str], list[tuple[Fraction, Fraction, Decimal]]
    ] = defaultdict(list)
    boost_series: dict[tuple[int, int], list[tuple[Fraction, Fraction]]] = {}
    force_maxima: dict[int, dict[str, Fraction]] = {
        precision: defaultdict(Fraction) for precision in PRECISIONS
    }
    analytic_bound_maxima: dict[int, dict[str, Fraction]] = {
        precision: defaultdict(Fraction) for precision in PRECISIONS
    }
    slope_envelopes: dict[str, dict[int, Fraction]] = {
        name: {precision: Fraction() for precision in PRECISIONS}
        for name in ("momentum", "angular", "energy", "boost_position", "boost_momentum")
    }
    exact_structure_envelopes = {
        name: {precision: Fraction() for precision in PRECISIONS}
        for name in (
            "representation_position", "representation_momentum",
            "representation_energy",
        )
    }
    full_anchor_pass = {precision: True for precision in PRECISIONS}
    full_anchor_report: dict[str, object] = {}
    comparator_report: dict[str, object] = {}
    long_frame_bound_pass = {precision: True for precision in PRECISIONS}
    long_frame_bound_report: dict[str, object] = {}
    exact_prefix_energy_bound_pass = {precision: True for precision in PRECISIONS}
    exact_prefix_energy_profile_pass = {
        (precision, level, scenario): True
        for precision in PRECISIONS for level in LEVELS
        for scenario in ("k4_internal", "k4_boosted")
    }
    exact_prefix_energy_bounds: dict[
        tuple[int, int, str], list[Fraction]
    ] = defaultdict(list)
    exact_prefix_energy_residuals: dict[
        tuple[int, int, str], list[Fraction]
    ] = defaultdict(list)
    exact_prefix_energy_certificate: dict[int, dict[str, object]] = {
        precision: {
            "samples": 0,
            "potential_binary64_value_matches": 0,
            "force_scalar_pairs": 0,
            "force_scalar_bit_matches": 0,
            "paired_kick_relations": 0,
            "maximum_energy_residual": Fraction(),
            "maximum_componentwise_energy_bound": Fraction(),
            "maximum_slope_residual": Fraction(),
            "maximum_least_squares_slope_bound": Fraction(),
        }
        for precision in PRECISIONS
    }

    for level in LEVELS:
        progress(f"long-replay:L{level}:start")
        level_runs: dict[tuple[int, str], Trajectory] = {}
        level_traces: dict[tuple[int, str], tuple[
            list[tuple[
                int, str, PhaseState, tuple[Fraction, Fraction, Fraction],
                tuple[Fraction, Fraction, Fraction],
            ]],
            list[tuple[int, str, dict[str, object]]],
        ]] = {}
        level_representation: dict[tuple[int, str], list[dict[str, str]]] = {}
        total_steps = 16 * STEP_COUNTS[level]
        for precision in PRECISIONS:
            for scenario in ("k4_internal", "k4_boosted"):
                trajectory_id = f"long:{scenario}:B{precision}:L{level}"
                run, stage_states, force_events = run_trajectory(
                    models["k4"], initial[(precision, scenario, "initial", 0)],
                    TIMESTEPS_RAW[level], total_steps, KDK, True,
                )
                require(run.status == "accepted" and run.completed_steps == total_steps,
                        f"{trajectory_id}: long independent replay failed")
                expected_endpoint = long_endpoints[(precision, scenario, KDK, level)]
                require(encode_phase_state(run.final) == encode_phase_state(expected_endpoint),
                        f"{trajectory_id}: long endpoint differs")
                level_runs[(precision, scenario)] = run
                baseline = exact_state_invariants(run.initial)
                committed_p: list[tuple[Fraction, Fraction, Fraction]] = []
                committed_l: list[tuple[Fraction, Fraction, Fraction]] = []
                for step, stage, state, momentum_bound, angular_bound in stage_states:
                    try:
                        row = next(invariant_iterator)
                    except StopIteration as error:
                        raise OracleError("long invariant evidence ended early") from error
                    require(row["trajectory_id"] == trajectory_id
                            and int(row["step"]) == step and row["stage"] == stage,
                            "long invariant causal order differs")
                    p_error, l_error = verify_invariant_row(
                        row, state, baseline, models["k4"],
                        momentum_bound, angular_bound,
                    )
                    analytic_bound_maxima[precision]["accumulated_momentum"] = max(
                        analytic_bound_maxima[precision]["accumulated_momentum"],
                        infinity_norm(momentum_bound),
                    )
                    analytic_bound_maxima[precision]["accumulated_angular"] = max(
                        analytic_bound_maxima[precision]["accumulated_angular"],
                        infinity_norm(angular_bound),
                    )
                    if stage in {"initial", "committed"}:
                        p_raw, l_raw = exact_state_invariants(state)
                        committed_p.append(tuple(
                            (p_raw[axis] - baseline[0][axis]) * PQ for axis in range(3)
                        ))
                        committed_l.append(tuple(
                            (l_raw[axis] - baseline[1][axis]) * LQ * PQ for axis in range(3)
                        ))
                    precision_pass[precision] = precision_pass[precision] and (
                        p_error <= MOMENTUM_BUDGET and l_error <= ANGULAR_BUDGET
                    )
                for step, stage, expected in force_events:
                    try:
                        row = next(force_iterator)
                    except StopIteration as error:
                        raise OracleError("long force evidence ended early") from error
                    require(row["trajectory_id"] == trajectory_id
                            and int(row["step"]) == step and row["stage"] == stage,
                            "long force causal order differs")
                    residuals = verify_force_row(row, expected)
                    for name, value in residuals.items():
                        force_maxima[precision][name] = max(force_maxima[precision][name], value)
                    for name in (
                        "pair_momentum_bound", "stored_impulse_centrality_bound",
                        "first_actual_centrality_bound",
                        "second_actual_centrality_bound", "relation_angular_bound",
                    ):
                        bound = expected[name]
                        assert isinstance(bound, tuple)
                        analytic_bound_maxima[precision][name] = max(
                            analytic_bound_maxima[precision][name], infinity_norm(bound)
                        )
                momentum_series[(precision, level, scenario)] = committed_p
                angular_series[(precision, level, scenario)] = committed_l

                operation = operation_rows[trajectory_id]
                verify_operation_row(
                    operation, trajectory_id, precision, level, KDK, models["k4"],
                    run.initial, total_steps, run,
                )
                level_traces[(precision, scenario)] = (
                    stage_states, compact_long_force_trace(force_events)
                )

            internal = level_runs[(precision, "k4_internal")]
            boosted = level_runs[(precision, "k4_boosted")]
            internal_stages, internal_forces = level_traces[(precision, "k4_internal")]
            boosted_stages, boosted_forces = level_traces[(precision, "k4_boosted")]
            frame_certificate = paired_frame_bound_certificate(
                internal, internal_stages, internal_forces,
                boosted, boosted_stages, boosted_forces,
                TIMESTEPS_RAW[level],
            )
            long_frame_bound_report[f"long:galilean_boost:B{precision}:L{level}"] = (
                frame_certificate
            )
            long_frame_bound_pass[precision] = (
                long_frame_bound_pass[precision] and bool(frame_certificate["passed"])
            )
            covariance = take_evidence_rows(
                covariance_iterator, total_steps + 1, "long covariance"
            )
            require(len(covariance) == len(internal.samples) == len(boosted.samples),
                    "long covariance sample count differs")
            covariance_values: list[tuple[Fraction, Fraction]] = []
            for sample, (row, first, second) in enumerate(
                zip(covariance, internal.samples, boosted.samples)
            ):
                x_raw = relative_state_error(first, second)
                p_raw = relative_state_error(first, second, True)
                require(
                    row["kind"] == "galilean_boost" and int(row["sample"]) == sample
                    and row["baseline_hash"] == phase_hash(first)
                    and row["transformed_hash"] == phase_hash(second)
                    and boolean(row["bit_identical"]) == (
                        encode_phase_state(first) == encode_phase_state(second)
                    ),
                    "long boost hash/classification differs",
                )
                for prefix, expected in (
                    ("relative_position_raw", x_raw),
                    ("relative_position_physical", x_raw * LQ),
                    ("relative_momentum_raw", p_raw),
                    ("relative_momentum_physical", p_raw * PQ),
                ):
                    require(scalar_from_columns(row, prefix) == expected,
                            f"long covariance {prefix} differs")
                covariance_values.append((x_raw * LQ, p_raw * PQ))
            boost_series[(precision, level)] = covariance_values

            energy_evidence = take_evidence_rows(
                energy_iterator, total_steps + 1, "long energy"
            )
            require(len(energy_evidence) == len(internal.samples),
                    "long energy sample count differs")
            observed_mechanical: list[Fraction] = []
            for sample, (row, state) in enumerate(zip(energy_evidence, internal.samples)):
                require(row["scenario_id"] == "k4_internal"
                        and row["path"] == KDK and int(row["sample"]) == sample,
                        "long energy sample identity differs")
                measured_energy = mechanical_energy(models["k4"], state)
                verify_energy_row(row, measured_energy)
                observed_mechanical.append(measured_energy[2])
            mechanical_energy_series[(precision, level)] = observed_mechanical
            for scenario in ("k4_internal", "k4_boosted"):
                group_rows = take_evidence_rows(
                    representation_iterator, prefix_steps[(scenario, level)] + 1,
                    "long representation",
                )
                require(all(
                    row["scenario_id"] == scenario
                    and int(row["precision"]) == precision
                    and int(row["level"]) == level
                    and row["scope"] == "long_exact_prefix"
                    and row["path"] == KDK
                    for row in group_rows
                ), "long representation group order differs")
                level_representation[(precision, scenario)] = group_rows

        anchor_precision = 256
        anchor_internal = level_runs[(anchor_precision, "k4_internal")]
        anchor_boosted = level_runs[(anchor_precision, "k4_boosted")]
        comparator_free_starts = {
            scenario: prefix_steps[(scenario, level)] + 1
            for scenario in ("k4_internal", "k4_boosted")
        }
        dt_physical = Fraction(TIMESTEPS_RAW[level]) * TQ
        for precision in PRECISIONS:
            if precision == anchor_precision:
                full_anchor_report[f"B{precision}:L{level}"] = {
                    "comparator_free_samples": {
                        "k4_internal": max(
                            0, len(anchor_internal.samples)
                            - comparator_free_starts["k4_internal"]
                        ),
                        "k4_boosted": max(
                            0, len(anchor_boosted.samples)
                            - comparator_free_starts["k4_boosted"]
                        ),
                    },
                    "self_anchor": True,
                    "passed": True,
                }
                continue
            statistics: dict[str, tuple[Fraction, Fraction, Fraction]] = {}
            for scenario, anchor_run in (
                ("k4_internal", anchor_internal), ("k4_boosted", anchor_boosted)
            ):
                candidate_run = level_runs[(precision, scenario)]
                comparator_free_start = comparator_free_starts[scenario]
                statistics[f"{scenario}_position"] = phase_trace_difference_statistics(
                    candidate_run.samples, anchor_run.samples, comparator_free_start,
                    LQ, False, dt_physical,
                )
                statistics[f"{scenario}_momentum"] = phase_trace_difference_statistics(
                    candidate_run.samples, anchor_run.samples, comparator_free_start,
                    PQ, True, dt_physical,
                )
            candidate_energy = mechanical_energy_series[(precision, level)]
            anchor_energy = mechanical_energy_series[(anchor_precision, level)]
            comparator_free_start = comparator_free_starts["k4_internal"]
            energy_difference = [
                candidate_energy[index] - anchor_energy[index]
                for index in range(comparator_free_start, len(candidate_energy))
            ]
            energy_maximum = max(
                (abs(value) for value in energy_difference), default=Fraction()
            )
            energy_final = abs(energy_difference[-1]) if energy_difference else Fraction()
            energy_slope = (
                abs(least_squares_slope(energy_difference, dt_physical))
                if energy_difference else Fraction()
            )
            passed = all(
                maximum <= (MOMENTUM_BUDGET if name.endswith("momentum") else POSITION_BUDGET)
                and final <= (MOMENTUM_BUDGET if name.endswith("momentum") else POSITION_BUDGET)
                and slope <= (
                    MOMENTUM_SLOPE_BUDGET if name.endswith("momentum")
                    else POSITION_BUDGET / 16
                )
                for name, (maximum, final, slope) in statistics.items()
            ) and (
                energy_maximum <= ENERGY_BUDGET
                and energy_final <= ENERGY_BUDGET
                and energy_slope <= ENERGY_SLOPE_BUDGET
            )
            full_anchor_pass[precision] = full_anchor_pass[precision] and passed
            full_anchor_report[f"B{precision}:L{level}"] = {
                "comparator_free_samples": max(
                    0, len(candidate_energy) - comparator_free_start
                ),
                "state": {
                    name: {
                        "maximum": ratio_text(value[0]),
                        "final": ratio_text(value[1]),
                        "slope": ratio_text(value[2]),
                    }
                    for name, value in statistics.items()
                },
                "energy_maximum": ratio_text(energy_maximum),
                "energy_final": ratio_text(energy_final),
                "energy_slope": ratio_text(energy_slope),
                "passed": passed,
            }

        rational_states = {
            scenario: rational_from_parent_rows(parent_initial[(scenario,)])
            for scenario in ("k4_internal", "k4_boosted")
        }
        rational_evaluations = {
            scenario: rational_force_and_energy(models["k4"], state)
            for scenario, state in rational_states.items()
        }
        rational_metrics = {
            scenario: rational_state_metrics(state)
            for scenario, state in rational_states.items()
        }
        bounded_rational_radii: dict[
            tuple[int, str], tuple[PhaseRadii, PhaseRadii]
        ] = {}
        bounded_rational_stage_maps: dict[
            tuple[int, str], dict[tuple[int, str], PhaseState]
        ] = {}
        bounded_rational_force_maps: dict[
            tuple[int, str], dict[tuple[int, str], list[dict[str, object]]]
        ] = {}
        for precision in PRECISIONS:
            for scenario in ("k4_internal", "k4_boosted"):
                run = level_runs[(precision, scenario)]
                bounded_rational_radii[(precision, scenario)] = zero_phase_radii(
                    run.initial
                )
                stage_values, force_values = level_traces[(precision, scenario)]
                bounded_rational_stage_maps[(precision, scenario)] = (
                    indexed_stage_trace(stage_values)
                )
                bounded_rational_force_maps[(precision, scenario)] = (
                    grouped_force_trace(force_values)
                )
                x_radius, p_radius = bounded_rational_radii[(precision, scenario)]
                initial_contained = bounded_rational_state_is_contained(
                    run.initial, rational_states[scenario], x_radius, p_radius
                )
                exact_prefix_energy_bound_pass[precision] = (
                    exact_prefix_energy_bound_pass[precision] and initial_contained
                )
                exact_prefix_energy_profile_pass[(precision, level, scenario)] = (
                    exact_prefix_energy_profile_pass[(precision, level, scenario)]
                    and initial_contained
                )
        exact_energy_error: dict[int, list[Fraction]] = {
            precision: [] for precision in PRECISIONS
        }
        comparator_metrics: dict[str, dict[str, object]] = {}
        for scenario in rational_states:
            metrics = rational_metrics[scenario]
            require(not metrics.exceeded,
                    "exact-rational initial comparator exceeds ceiling")
            comparator_metrics[scenario] = {
                "maximum": metrics.maximum_component_bits,
                "median": metrics.median_component_bits,
                "checkpoint_bytes": metrics.checkpoint_bytes,
                "crossing": None,
            }
        maximum_prefix_step = max(
            prefix_steps[(scenario, level)] for scenario in rational_states
        )
        for sample in range(maximum_prefix_step + 1):
            for scenario in ("k4_internal", "k4_boosted"):
                completed = prefix_steps[(scenario, level)]
                if sample > completed:
                    continue
                exact = rational_states[scenario]
                state_metrics = rational_metrics[scenario]
                component_bits = state_metrics.maximum_component_bits
                median_bits = state_metrics.median_component_bits
                checkpoint_bytes = state_metrics.checkpoint_bytes
                exceeded = state_metrics.exceeded
                metrics = comparator_metrics[scenario]
                metrics["maximum"] = max(int(metrics["maximum"]), component_bits)
                metrics["median"] = max(metrics["median"], median_bits)
                metrics["checkpoint_bytes"] = max(
                    int(metrics["checkpoint_bytes"]), checkpoint_bytes
                )
                if exceeded:
                    require(sample == completed and completed <= 16 * STEP_COUNTS[level],
                            "exact comparator crossed before declared terminal sample")
                    metrics["crossing"] = (
                        component_bits, median_bits, checkpoint_bytes
                    )
                else:
                    require(sample < completed or completed == 16 * STEP_COUNTS[level],
                            "exact comparator failed to cross at declared terminal sample")
                exact_relations, exact_potential = rational_evaluations[scenario]
                exact_energy = rational_kinetic_energy(exact) + exact_potential
                exact_hash = state_metrics.sha256
                exact_decimal = rational_physical_decimal(exact)
                for precision in PRECISIONS:
                    bounded = level_runs[(precision, scenario)].samples[sample]
                    evidence = level_representation[(precision, scenario)]
                    row = evidence[sample]
                    x_raw = bounded_rational_error(bounded, exact)
                    p_raw = bounded_rational_error(bounded, exact, True)
                    state_norm = foundation.state_norm_difference(
                        physical_state_decimal_from_phase(bounded),
                        exact_decimal,
                        len(bounded.packets),
                    )
                    bounded_relations, bounded_potential, _operations = force_and_energy(
                        models["k4"], bounded
                    )
                    bounded_energy = (
                        bounded_kinetic_energy(bounded) + bounded_potential
                    )
                    potential_match = bounded_potential == exact_potential
                    force_matches = sum(
                        1
                        for bounded_relation, exact_relation in zip(
                            bounded_relations, exact_relations
                        )
                        if (
                            bounded_relation.relation == exact_relation[0]
                            and struct.unpack(
                                ">Q", struct.pack(">d", bounded_relation.length)
                            )[0] == struct.unpack(
                                ">Q", struct.pack(">d", exact_relation[2])
                            )[0]
                            and struct.unpack(
                                ">Q", struct.pack(">d", bounded_relation.conjugate)
                            )[0] == struct.unpack(
                                ">Q", struct.pack(">d", exact_relation[3])
                            )[0]
                        )
                    )
                    force_match = (
                        len(bounded_relations) == len(exact_relations) == force_matches
                    )
                    _x_radius, current_p_radius = bounded_rational_radii[
                        (precision, scenario)
                    ]
                    kinetic_bound = kinetic_difference_radius_bound(
                        bounded, exact, current_p_radius
                    )
                    energy_residual = abs(bounded_energy - exact_energy)
                    energy_bound = kinetic_bound if potential_match else Fraction()
                    energy_contained = potential_match and energy_residual <= energy_bound
                    certificate = exact_prefix_energy_certificate[precision]
                    certificate["samples"] = int(certificate["samples"]) + 1
                    certificate["potential_binary64_value_matches"] = (
                        int(certificate["potential_binary64_value_matches"])
                        + int(potential_match)
                    )
                    certificate["force_scalar_pairs"] = (
                        int(certificate["force_scalar_pairs"]) + len(exact_relations)
                    )
                    certificate["force_scalar_bit_matches"] = (
                        int(certificate["force_scalar_bit_matches"]) + force_matches
                    )
                    certificate["maximum_energy_residual"] = max(
                        certificate["maximum_energy_residual"], energy_residual
                    )
                    certificate["maximum_componentwise_energy_bound"] = max(
                        certificate["maximum_componentwise_energy_bound"], energy_bound
                    )
                    exact_prefix_energy_bounds[(precision, level, scenario)].append(
                        energy_bound
                    )
                    exact_prefix_energy_residuals[(precision, level, scenario)].append(
                        bounded_energy - exact_energy
                    )
                    exact_prefix_energy_bound_pass[precision] = (
                        exact_prefix_energy_bound_pass[precision]
                        and force_match and energy_contained
                    )
                    exact_prefix_energy_profile_pass[(precision, level, scenario)] = (
                        exact_prefix_energy_profile_pass[(precision, level, scenario)]
                        and force_match and energy_contained
                    )
                    identity: dict[str, object] = {
                        "scenario_id": scenario,
                        "scope": "long_exact_prefix",
                        "path": KDK,
                        "precision": precision,
                        "level": level,
                        "dt_raw": TIMESTEPS_RAW[level],
                        "sample": sample,
                        "candidate_state_hash": phase_hash(bounded),
                        "control_state_hash": exact_hash,
                    }
                    verify_representation_error_row(
                        row, identity, x_raw, p_raw,
                        bounded_energy - exact_energy,
                    )
                    exact_structure_envelopes["representation_position"][precision] = max(
                        exact_structure_envelopes["representation_position"][precision],
                        x_raw * LQ,
                    )
                    exact_structure_envelopes["representation_momentum"][precision] = max(
                        exact_structure_envelopes["representation_momentum"][precision],
                        p_raw * PQ,
                    )
                    exact_structure_envelopes["representation_energy"][precision] = max(
                        exact_structure_envelopes["representation_energy"][precision],
                        abs(bounded_energy - exact_energy),
                    )
                    if scenario == "k4_internal":
                        exact_energy_error[precision].append(bounded_energy - exact_energy)
                    prefix_state_series[(precision, level, scenario)].append(
                        (x_raw * LQ, p_raw * PQ, state_norm)
                    )
                if sample < completed:
                    (
                        next_exact, exact_stages, exact_forces, next_evaluation,
                    ) = rational_step_trace(
                        models["k4"], exact, TIMESTEPS_RAW[level], KDK,
                        (exact_relations, exact_potential),
                    )
                    for precision in PRECISIONS:
                        x_radius, p_radius = bounded_rational_radii[
                            (precision, scenario)
                        ]
                        (
                            x_radius, p_radius, recurrence_passed, paired_relations,
                        ) = advance_bounded_rational_step_bound(
                            bounded_rational_stage_maps[(precision, scenario)],
                            bounded_rational_force_maps[(precision, scenario)],
                            sample + 1, exact, exact_stages, exact_forces,
                            TIMESTEPS_RAW[level], KDK, x_radius, p_radius,
                        )
                        bounded_rational_radii[(precision, scenario)] = (
                            x_radius, p_radius
                        )
                        certificate = exact_prefix_energy_certificate[precision]
                        certificate["paired_kick_relations"] = (
                            int(certificate["paired_kick_relations"])
                            + paired_relations
                        )
                        exact_prefix_energy_bound_pass[precision] = (
                            exact_prefix_energy_bound_pass[precision]
                            and recurrence_passed
                        )
                        exact_prefix_energy_profile_pass[
                            (precision, level, scenario)
                        ] = (
                            exact_prefix_energy_profile_pass[
                                (precision, level, scenario)
                            ]
                            and recurrence_passed
                        )
                    rational_states[scenario] = next_exact
                    rational_evaluations[scenario] = next_evaluation
                    rational_metrics[scenario] = rational_state_metrics(next_exact)
        for scenario, exact in rational_states.items():
            completed = prefix_steps[(scenario, level)]
            requested = 16 * STEP_COUNTS[level]
            row = comparator_rows[(scenario, level)]
            metrics = comparator_metrics[scenario]
            crossing = metrics["crossing"]
            crossed = crossing is not None
            require(
                row["status"] == (
                    "complexity_budget_exceeded" if crossed else "accepted"
                )
                and row["first_crossing_step"] == (
                    str(completed) if crossed else ""
                )
                and int(row["last_within_ceiling_step"])
                    == (completed - 1 if crossed else completed)
                and int(row["last_comparator_time_raw"]) == exact.time_raw
                and row["last_comparator_state_hash"]
                    == rational_metrics[scenario].sha256
                and int(row["maximum_component_bits"]) == metrics["maximum"]
                and scalar_from_columns(row, "maximum_state_median_bits")
                    == metrics["median"]
                and int(row["maximum_checkpoint_bytes"])
                    == metrics["checkpoint_bytes"]
                and boolean(row["crossing_state_included"]) == crossed,
                f"{scenario}:L{level}: exact comparator receipt differs",
            )
            if crossed:
                assert isinstance(crossing, tuple)
                require(
                    int(row["crossing_component_bits"]) == crossing[0]
                    and scalar_from_columns(row, "crossing_state_median_bits")
                        == crossing[1]
                    and int(row["crossing_checkpoint_bytes"]) == crossing[2]
                    and completed <= requested,
                    f"{scenario}:L{level}: exact crossing receipt differs",
                )
            else:
                require(
                    completed == requested
                    and row["crossing_component_bits"] == ""
                    and row["crossing_state_median_bits_num"] == ""
                    and row["crossing_state_median_bits_den"] == ""
                    and row["crossing_checkpoint_bytes"] == "",
                    f"{scenario}:L{level}: accepted comparator receipt differs",
                )
            comparator_report[f"{scenario}:L{level}"] = {
                "status": row["status"],
                "completed_steps": completed,
                "last_state_hash": rational_metrics[scenario].sha256,
                "maximum_component_bits": metrics["maximum"],
                "maximum_state_median_bits": ratio_text(metrics["median"]),
                "maximum_checkpoint_bytes": metrics["checkpoint_bytes"],
                "crossing_state_included": crossed,
            }
        for precision in PRECISIONS:
            exact_prefix_dt = Fraction(TIMESTEPS_RAW[level]) * TQ
            for scenario in ("k4_internal", "k4_boosted"):
                energy_values = exact_prefix_energy_residuals[
                    (precision, level, scenario)
                ]
                energy_bounds = exact_prefix_energy_bounds[
                    (precision, level, scenario)
                ]
                require(len(energy_values) == len(energy_bounds) > 0,
                        "exact-prefix energy certificate inventory differs")
                slope_residual = abs(
                    least_squares_slope(energy_values, exact_prefix_dt)
                )
                slope_bound = least_squares_absolute_bound(
                    energy_bounds, exact_prefix_dt
                )
                certificate = exact_prefix_energy_certificate[precision]
                certificate["maximum_slope_residual"] = max(
                    certificate["maximum_slope_residual"], slope_residual
                )
                certificate["maximum_least_squares_slope_bound"] = max(
                    certificate["maximum_least_squares_slope_bound"], slope_bound
                )
                exact_prefix_energy_bound_pass[precision] = (
                    exact_prefix_energy_bound_pass[precision]
                    and slope_residual <= slope_bound
                )
                exact_prefix_energy_profile_pass[(precision, level, scenario)] = (
                    exact_prefix_energy_profile_pass[(precision, level, scenario)]
                    and slope_residual <= slope_bound
                )
            energy_error_series[(precision, level)] = exact_energy_error[precision]
            physical_energy = mechanical_energy_series[(precision, level)]
            physical_offsets = [value - physical_energy[0] for value in physical_energy]
            physical_slope = least_squares_slope(
                physical_offsets, Fraction(TIMESTEPS_RAW[level]) * TQ
            )
            prefix_energy = exact_energy_error[precision]
            prefix_energy_slope = least_squares_slope(
                prefix_energy, Fraction(TIMESTEPS_RAW[level]) * TQ
            )
            prefix_statistics: dict[str, object] = {}
            for scenario in ("k4_internal", "k4_boosted"):
                values = prefix_state_series[(precision, level, scenario)]
                prefix_statistics[scenario] = {
                    "position_maximum": ratio_text(max(value[0] for value in values)),
                    "position_final": ratio_text(values[-1][0]),
                    "momentum_maximum": ratio_text(max(value[1] for value in values)),
                    "momentum_final": ratio_text(values[-1][1]),
                    "state_norm_maximum": format(max(value[2] for value in values), ".29E"),
                    "state_norm_final": format(values[-1][2], ".29E"),
                }
            invariant_statistics: dict[str, object] = {}
            dt_value = Fraction(TIMESTEPS_RAW[level]) * TQ
            for scenario in ("k4_internal", "k4_boosted"):
                p_values = momentum_series[(precision, level, scenario)]
                l_values = angular_series[(precision, level, scenario)]
                invariant_statistics[scenario] = {
                    "momentum_maximum": ratio_text(max(
                        (infinity_norm(value) for value in p_values), default=Fraction()
                    )),
                    "momentum_final": [ratio_text(value) for value in p_values[-1]],
                    "momentum_slopes": [ratio_text(least_squares_slope(
                        [value[axis] for value in p_values], dt_value
                    )) for axis in range(3)],
                    "angular_maximum": ratio_text(max(
                        (infinity_norm(value) for value in l_values), default=Fraction()
                    )),
                    "angular_final": [ratio_text(value) for value in l_values[-1]],
                    "angular_slopes": [ratio_text(least_squares_slope(
                        [value[axis] for value in l_values], dt_value
                    )) for axis in range(3)],
                }
            boost_values = boost_series[(precision, level)]
            run_report = {
                "steps": total_steps,
                "endpoint_hash": phase_hash(level_runs[(precision, "k4_internal")].final),
                "boost_endpoint_hash": phase_hash(level_runs[(precision, "k4_boosted")].final),
                "maximum_energy_representation_error": ratio_text(max(
                    (abs(value) for value in prefix_energy), default=Fraction()
                )),
                "final_energy_representation_error": ratio_text(prefix_energy[-1]),
                "mean_energy_representation_error": ratio_text(
                    sum(prefix_energy, Fraction()) / len(prefix_energy)
                ),
                "energy_representation_least_squares_slope": ratio_text(
                    prefix_energy_slope
                ),
                "exact_prefix_state": prefix_statistics,
                "invariant_residuals": invariant_statistics,
                "boost_position_maximum": ratio_text(max(value[0] for value in boost_values)),
                "boost_position_final": ratio_text(boost_values[-1][0]),
                "boost_position_slope": ratio_text(least_squares_slope(
                    [value[0] for value in boost_values], dt_value
                )),
                "boost_momentum_maximum": ratio_text(max(value[1] for value in boost_values)),
                "boost_momentum_final": ratio_text(boost_values[-1][1]),
                "boost_momentum_slope": ratio_text(least_squares_slope(
                    [value[1] for value in boost_values], dt_value
                )),
                "maximum_physical_energy_excursion": ratio_text(max(
                    (abs(value) for value in physical_offsets), default=Fraction()
                )),
                "final_physical_energy_error": ratio_text(physical_offsets[-1]),
                "mean_physical_energy_offset": ratio_text(
                    sum(physical_offsets, Fraction()) / len(physical_offsets)
                ),
                "physical_energy_least_squares_slope": ratio_text(physical_slope),
            }
            report[f"B{precision}:L{level}"] = run_report
        progress(f"long-replay:L{level}:complete")

    try:
        next(representation_iterator)
        raise OracleError("unexpected extra long representation row")
    except StopIteration:
        pass
    try:
        next(energy_iterator)
        raise OracleError("unexpected extra long energy row")
    except StopIteration:
        pass
    try:
        next(covariance_iterator)
        raise OracleError("unexpected extra long covariance row")
    except StopIteration:
        pass
    try:
        next(invariant_iterator)
        raise OracleError("unexpected extra long invariant row")
    except StopIteration:
        pass
    try:
        next(force_iterator)
        raise OracleError("unexpected extra long force row")
    except StopIteration:
        pass

    for precision in PRECISIONS:
        for level in LEVELS:
            dt = Fraction(TIMESTEPS_RAW[level]) * TQ
            e_values = energy_error_series[(precision, level)]
            b_values = boost_series[(precision, level)]
            e_slope = least_squares_slope(e_values, dt)
            bx_slope = least_squares_slope([value[0] for value in b_values], dt)
            bp_slope = least_squares_slope([value[1] for value in b_values], dt)
            residual_contract = True
            for scenario in ("k4_internal", "k4_boosted"):
                p_values = momentum_series[(precision, level, scenario)]
                l_values = angular_series[(precision, level, scenario)]
                p_slopes = [least_squares_slope([value[axis] for value in p_values], dt)
                            for axis in range(3)]
                l_slopes = [least_squares_slope([value[axis] for value in l_values], dt)
                            for axis in range(3)]
                residual_contract = residual_contract and (
                    max((infinity_norm(value) for value in p_values), default=Fraction()) <= MOMENTUM_BUDGET
                    and max((infinity_norm(value) for value in l_values), default=Fraction()) <= ANGULAR_BUDGET
                    and max((abs(value) for value in p_slopes), default=Fraction()) <= MOMENTUM_SLOPE_BUDGET
                    and max((abs(value) for value in l_slopes), default=Fraction()) <= ANGULAR_SLOPE_BUDGET
                )
                slope_envelopes["momentum"][precision] = max(
                    slope_envelopes["momentum"][precision],
                    max((abs(value) for value in p_slopes), default=Fraction()),
                )
                slope_envelopes["angular"][precision] = max(
                    slope_envelopes["angular"][precision],
                    max((abs(value) for value in l_slopes), default=Fraction()),
                )
            slope_envelopes["energy"][precision] = max(
                slope_envelopes["energy"][precision], abs(e_slope)
            )
            slope_envelopes["boost_position"][precision] = max(
                slope_envelopes["boost_position"][precision], abs(bx_slope)
            )
            slope_envelopes["boost_momentum"][precision] = max(
                slope_envelopes["boost_momentum"][precision], abs(bp_slope)
            )
            precision_pass[precision] = precision_pass[precision] and residual_contract and (
                max((abs(value) for value in e_values), default=Fraction()) <= ENERGY_BUDGET
                and abs(e_slope) <= ENERGY_SLOPE_BUDGET
                and max((value[0] for value in b_values), default=Fraction()) <= POSITION_BUDGET
                and max((value[1] for value in b_values), default=Fraction()) <= MOMENTUM_BUDGET
                and abs(bx_slope) <= POSITION_BUDGET / 16
                and abs(bp_slope) <= MOMENTUM_BUDGET / 16
            )
    slope_budgets = {
        "momentum": MOMENTUM_SLOPE_BUDGET,
        "angular": ANGULAR_SLOPE_BUDGET,
        "energy": ENERGY_SLOPE_BUDGET,
        "boost_position": POSITION_BUDGET / 16,
        "boost_momentum": MOMENTUM_BUDGET / 16,
    }
    slope_scaling = {
        name: scaling_until_budget(values, slope_budgets[name])
        for name, values in slope_envelopes.items()
    }
    slope_anchor_budget_pass = all(
        slope_envelopes[name][256] <= slope_budgets[name] / 16
        for name in slope_envelopes
    )
    slope_anchor_unit_roundoff_scaling = all(
        unit_roundoff_pair_scales(
            slope_envelopes[name][192], slope_envelopes[name][256], 64
        )
        for name in slope_envelopes
    )
    exact_prefix_anchor_report: dict[str, object] = {}
    exact_prefix_anchor_pass: dict[int, bool] = {}
    anchor_contracts: list[tuple[bool, bool, bool]] = []
    analytic_anchor_contracts: list[bool] = []
    for level in LEVELS:
        scenario_report: dict[str, object] = {}
        level_contracts: list[tuple[bool, bool, bool]] = []
        level_analytic_contracts: list[bool] = []
        for scenario in ("k4_internal", "k4_boosted"):
            metric_envelopes = {
                name: {precision: Fraction() for precision in PRECISIONS}
                for name in (
                    "position_maximum", "position_final",
                    "momentum_maximum", "momentum_final",
                )
            }
            for precision in PRECISIONS:
                state_values = prefix_state_series[(precision, level, scenario)]
                metric_envelopes["position_maximum"][precision] = max(
                    value[0] for value in state_values
                )
                metric_envelopes["position_final"][precision] = state_values[-1][0]
                metric_envelopes["momentum_maximum"][precision] = max(
                    value[1] for value in state_values
                )
                metric_envelopes["momentum_final"][precision] = state_values[-1][1]
            metric_budgets = {
                "position_maximum": POSITION_BUDGET,
                "position_final": POSITION_BUDGET,
                "momentum_maximum": MOMENTUM_BUDGET,
                "momentum_final": MOMENTUM_BUDGET,
            }
            if scenario == "k4_internal":
                for name in ("energy_maximum", "energy_final", "energy_slope"):
                    metric_envelopes[name] = {
                        precision: Fraction() for precision in PRECISIONS
                    }
                dt = Fraction(TIMESTEPS_RAW[level]) * TQ
                for precision in PRECISIONS:
                    energy_values = energy_error_series[(precision, level)]
                    metric_envelopes["energy_maximum"][precision] = max(
                        (abs(value) for value in energy_values), default=Fraction()
                    )
                    metric_envelopes["energy_final"][precision] = abs(energy_values[-1])
                    metric_envelopes["energy_slope"][precision] = abs(
                        least_squares_slope(energy_values, dt)
                    )
                metric_budgets.update({
                    "energy_maximum": ENERGY_BUDGET,
                    "energy_final": ENERGY_BUDGET,
                    "energy_slope": ENERGY_SLOPE_BUDGET,
                })
            anchor_required = (
                prefix_steps[(scenario, level)] < 16 * STEP_COUNTS[level]
            )
            below_one_sixteenth, pair_scaling, scenario_qualified = (
                qualify_exact_prefix_anchor(
                    metric_envelopes, metric_budgets, anchor_required
                )
            )
            analytic_anchor_pass = exact_prefix_energy_profile_pass[
                (256, level, scenario)
            ]
            analytic_contract = not anchor_required or analytic_anchor_pass
            scenario_qualified = scenario_qualified and analytic_contract
            contract = (
                anchor_required,
                all(below_one_sixteenth.values()),
                all(pair_scaling.values()),
            )
            level_contracts.append(contract)
            anchor_contracts.append(contract)
            level_analytic_contracts.append(analytic_contract)
            analytic_anchor_contracts.append(analytic_contract)
            scenario_report[scenario] = {
                "anchor_required": anchor_required,
                "qualification": (
                    "passed" if anchor_required and scenario_qualified
                    else "failed" if anchor_required else "not_applicable"
                ),
                "metric_envelopes": {
                    name: {
                        str(precision): ratio_text(value)
                        for precision, value in values.items()
                    }
                    for name, values in metric_envelopes.items()
                },
                "physical_budgets": {
                    name: ratio_text(value) for name, value in metric_budgets.items()
                },
                "b256_below_one_sixteenth_budget": below_one_sixteenth,
                "b192_b256_unit_roundoff_scaling": pair_scaling,
                "b256_analytic_energy_certificate": analytic_anchor_pass,
                "qualified": scenario_qualified if anchor_required else None,
            }
        _level_budgets, _level_scaling, level_qualified = (
            aggregate_required_anchor_contracts(level_contracts)
        )
        level_qualified = level_qualified and all(level_analytic_contracts)
        exact_prefix_anchor_pass[level] = level_qualified
        exact_prefix_anchor_report[str(level)] = {
            "scenarios": scenario_report,
            "all_required_scenarios_qualified": level_qualified,
        }
    (
        all_required_anchor_budgets_pass,
        all_required_anchor_scaling_pass,
        all_required_anchors_qualified,
    ) = aggregate_required_anchor_contracts(anchor_contracts)
    all_required_anchors_qualified = (
        all_required_anchors_qualified and all(analytic_anchor_contracts)
    )
    boost_timestep_contraction: dict[str, object] = {}
    for precision in PRECISIONS:
        x_maxima = [
            max((value[0] for value in boost_series[(precision, level)]), default=Fraction())
            for level in LEVELS
        ]
        p_maxima = [
            max((value[1] for value in boost_series[(precision, level)]), default=Fraction())
            for level in LEVELS
        ]
        x_finals = [boost_series[(precision, level)][-1][0] for level in LEVELS]
        p_finals = [boost_series[(precision, level)][-1][1] for level in LEVELS]
        profiles = {
            "position_maximum": timestep_contraction_profile(x_maxima, POSITION_BUDGET),
            "position_final": timestep_contraction_profile(x_finals, POSITION_BUDGET),
            "momentum_maximum": timestep_contraction_profile(p_maxima, MOMENTUM_BUDGET),
            "momentum_final": timestep_contraction_profile(p_finals, MOMENTUM_BUDGET),
        }
        contracts = {
            name: qualitative and attained
            for name, (qualitative, attained) in profiles.items()
        }
        precision_pass[precision] = precision_pass[precision] and all(contracts.values())
        boost_timestep_contraction[str(precision)] = {
            "position_maxima": [ratio_text(value) for value in x_maxima],
            "position_finals": [ratio_text(value) for value in x_finals],
            "momentum_maxima": [ratio_text(value) for value in p_maxima],
            "momentum_finals": [ratio_text(value) for value in p_finals],
            **{
                f"{name}_qualitative_contraction": qualitative
                for name, (qualitative, _attained) in profiles.items()
            },
            **{
                f"{name}_floor_attained": attained
                for name, (_qualitative, attained) in profiles.items()
            },
            **contracts,
        }
    for precision in PRECISIONS:
        for level in LEVELS:
            anchor_row = full_anchor_report[f"B{precision}:L{level}"]
            assert isinstance(anchor_row, dict)
            comparison_passed = bool(anchor_row["passed"])
            anchor_row["comparison_passed"] = comparison_passed
            anchor_row["qualified_by_exact_prefix"] = exact_prefix_anchor_pass[level]
            anchor_row["passed"] = (
                comparison_passed and exact_prefix_anchor_pass[level]
            )
            full_anchor_pass[precision] = (
                full_anchor_pass[precision] and bool(anchor_row["passed"])
            )
        precision_pass[precision] = (
            precision_pass[precision]
            and full_anchor_pass[precision]
            and long_frame_bound_pass[precision]
            and exact_prefix_energy_bound_pass[precision]
        )
    return {
        "runs": report,
        "force_maxima": {
            str(precision): {name: ratio_text(value) for name, value in values.items()}
            for precision, values in force_maxima.items()
        },
        "independently_summed_half_ulp_bound_maxima": {
            str(precision): {
                name: ratio_text(value) for name, value in sorted(values.items())
            }
            for precision, values in analytic_bound_maxima.items()
        },
        "long_frame_summed_local_half_ulp_certificates": long_frame_bound_report,
        "long_frame_bound_pass": {
            str(precision): value for precision, value in long_frame_bound_pass.items()
        },
        "exact_prefix_energy_componentwise_certificates": {
            str(precision): {
                name: (
                    ratio_text(value) if isinstance(value, Fraction) else value
                )
                for name, value in certificate.items()
            } | {"passed": exact_prefix_energy_bound_pass[precision]}
            for precision, certificate in exact_prefix_energy_certificate.items()
        },
        "exact_prefix_energy_profile_pass": {
            f"B{precision}:L{level}:{scenario}": passed
            for (precision, level, scenario), passed
            in exact_prefix_energy_profile_pass.items()
        },
        "paired_bound_accumulator": {
            "eligibility_witness_rounding": (
                "greatest_B256_dyadic_not_above_each_monotone_exact_"
                "recurrence_update"
            ),
            "eligibility_implication": (
                "measured_residual<=inward_witness<=literal_exact_local_"
                "half_ulp_recurrence"
            ),
            "fitted_constants": False,
        },
        "slope_envelopes": {
            name: {str(precision): ratio_text(value) for precision, value in values.items()}
            for name, values in slope_envelopes.items()
        },
        "slope_unit_roundoff_scaling": slope_scaling,
        "b256_all_residual_slopes_below_one_sixteenth_budget_diagnostic": (
            slope_anchor_budget_pass
        ),
        "b192_b256_all_residual_slopes_unit_roundoff_diagnostic": (
            slope_anchor_unit_roundoff_scaling
        ),
        "long_exact_prefix_anchor": exact_prefix_anchor_report,
        "all_required_exact_prefix_below_one_sixteenth_budget": (
            all_required_anchor_budgets_pass
        ),
        "all_required_exact_prefix_unit_roundoff_scaling": (
            all_required_anchor_scaling_pass
        ),
        "all_required_full_tail_anchors_qualified": (
            all_required_anchors_qualified
        ),
        "comparator_free_b256_trace_agreement": full_anchor_report,
        "boost_timestep_contraction": boost_timestep_contraction,
        "exact_rational_comparator_receipts": comparator_report,
        "compact_xyz_hash_max_physical_and_delta_derivations": True,
    }, precision_pass, (
        all(slope_scaling.values())
        and all_required_anchor_scaling_pass
        and all(
            bool(boost_timestep_contraction["256"][f"{name}_qualitative_contraction"])
            for name in (
                "position_maximum", "position_final",
                "momentum_maximum", "momentum_final",
            )
        )
    ), exact_structure_envelopes


def scaling_until_budget(values: dict[int, Fraction], budget: Fraction) -> bool:
    require(set(values) == set(PRECISIONS), "precision envelope inventory differs")
    reached = False
    prior_precision: int | None = None
    prior = Fraction()
    for precision in PRECISIONS:
        value = values[precision]
        require(value >= 0, "negative residual envelope")
        if prior_precision is not None and prior == 0 and value != 0:
            return False
        if prior_precision is not None and not reached and prior != 0:
            if not (
                value < prior
                and value <= 4 * Fraction(1, 2 ** (precision - prior_precision)) * prior
            ):
                return False
        reached = reached or value <= budget
        if reached and value > budget:
            return False
        prior_precision, prior = precision, value
    return True


def unit_roundoff_pair_scales(lower: Fraction, higher: Fraction, bit_gap: int) -> bool:
    """Apply the frozen adjacent-precision rule, including exact-zero closure."""
    require(lower >= 0 and higher >= 0 and bit_gap > 0,
            "invalid precision-pair residual")
    if lower == 0:
        return higher == 0
    return higher < lower and higher <= 4 * Fraction(1, 2**bit_gap) * lower


def qualify_exact_prefix_anchor(
    metric_envelopes: dict[str, dict[int, Fraction]],
    metric_budgets: dict[str, Fraction],
    required: bool,
) -> tuple[dict[str, bool], dict[str, bool], bool]:
    require(set(metric_envelopes) == set(metric_budgets),
            "exact-prefix anchor metric inventory differs")
    require(all(set(values) == set(PRECISIONS) for values in metric_envelopes.values()),
            "exact-prefix anchor precision inventory differs")
    below_one_sixteenth = {
        name: values[256] <= metric_budgets[name] / 16
        for name, values in metric_envelopes.items()
    }
    pair_scaling = {
        name: unit_roundoff_pair_scales(values[192], values[256], 64)
        for name, values in metric_envelopes.items()
    }
    qualified = (
        not required
        or (all(below_one_sixteenth.values()) and all(pair_scaling.values()))
    )
    return below_one_sixteenth, pair_scaling, qualified


def aggregate_required_anchor_contracts(
    contracts: Sequence[tuple[bool, bool, bool]],
) -> tuple[bool, bool, bool]:
    require(bool(contracts), "exact-prefix anchor contract inventory is empty")
    budget_pass = all(not required or budget for required, budget, _scaling in contracts)
    scaling_pass = all(not required or scaling for required, _budget, scaling in contracts)
    return budget_pass, scaling_pass, budget_pass and scaling_pass


def structure_residual_report(
    raw: Path, state_report: dict[str, object],
    exact_representation: dict[str, dict[int, Fraction]],
) -> tuple[dict[str, object], dict[int, bool], bool]:
    quantities: dict[str, tuple[Fraction, dict[int, Fraction]]] = {
        "representation_position": (
            POSITION_BUDGET, {precision: Fraction() for precision in PRECISIONS}
        ),
        "representation_momentum": (
            MOMENTUM_BUDGET, {precision: Fraction() for precision in PRECISIONS}
        ),
        "momentum": (MOMENTUM_BUDGET, {precision: Fraction() for precision in PRECISIONS}),
        "angular": (ANGULAR_BUDGET, {precision: Fraction() for precision in PRECISIONS}),
        "pair_momentum": (MOMENTUM_BUDGET, {precision: Fraction() for precision in PRECISIONS}),
        "stored_centrality": (ANGULAR_BUDGET, {precision: Fraction() for precision in PRECISIONS}),
        "first_centrality": (ANGULAR_BUDGET, {precision: Fraction() for precision in PRECISIONS}),
        "second_centrality": (ANGULAR_BUDGET, {precision: Fraction() for precision in PRECISIONS}),
        "relation_angular": (ANGULAR_BUDGET, {precision: Fraction() for precision in PRECISIONS}),
        "reversal_position": (POSITION_BUDGET, {precision: Fraction() for precision in PRECISIONS}),
        "reversal_momentum": (MOMENTUM_BUDGET, {precision: Fraction() for precision in PRECISIONS}),
        "frame_position": (POSITION_BUDGET, {precision: Fraction() for precision in PRECISIONS}),
        "frame_momentum": (MOMENTUM_BUDGET, {precision: Fraction() for precision in PRECISIONS}),
        "representation_energy": (ENERGY_BUDGET, {precision: Fraction() for precision in PRECISIONS}),
    }

    def update(name: str, precision: int, value: Fraction) -> None:
        budget, envelope = quantities[name]
        del budget
        envelope[precision] = max(envelope[precision], abs(value))

    initial = state_report["initial"]
    endpoints = state_report["endpoint"]
    assert isinstance(initial, dict) and isinstance(endpoints, dict)

    def baseline_for(
        trajectory: str, precision: int, level: int,
    ) -> tuple[tuple[Fraction, Fraction, Fraction], tuple[Fraction, Fraction, Fraction]]:
        parts = trajectory.split(":")
        if parts[0] == "short":
            state = initial[(precision, parts[1], "initial", 0)]
        elif parts[0] == "reverse":
            state = endpoints[(precision, parts[1], KDK, level)]
        elif parts[0] == "covariance":
            scenario = {
                "translation": "k4_translated",
                "galilean_boost": "k4_boosted",
                "proper_lattice_rotation": "k4_rotated",
                "packet_permutation": "k4_internal",
            }[parts[1]]
            state = initial[(precision, scenario, "initial", 0)]
        elif parts[0] == "checkpoint":
            state = initial[(precision, "k4_internal", "initial", 0)]
        elif parts[0] == "long":
            state = initial[(precision, parts[1], "initial", 0)]
        else:
            raise OracleError(f"unknown invariant trajectory {trajectory!r}")
        assert isinstance(state, PhaseState)
        return exact_state_invariants(state)

    baseline_cache: dict[
        tuple[str, int, int],
        tuple[tuple[Fraction, Fraction, Fraction], tuple[Fraction, Fraction, Fraction]],
    ] = {}
    for row in iter_rows(raw / "invariants.csv"):
        precision = int(row["precision"])
        level = int(row["level"])
        trajectory = row["trajectory_id"]
        cache_key = (trajectory, precision, level)
        baseline = baseline_cache.setdefault(
            cache_key, baseline_for(trajectory, precision, level)
        )
        momentum = raw_vector_from_row(row, "momentum")
        angular = raw_vector_from_row(row, "angular")
        update("momentum", precision,
               infinity_norm(vector_sub(momentum, baseline[0])) * PQ)
        update("angular", precision,
               infinity_norm(vector_sub(angular, baseline[1])) * LQ * PQ)
    force_names = {
        "pair_momentum_residual": ("pair_momentum", PQ),
        "stored_impulse_centrality_residual": ("stored_centrality", LQ * PQ),
        "first_actual_centrality_residual": ("first_centrality", LQ * PQ),
        "second_actual_centrality_residual": ("second_centrality", LQ * PQ),
        "relation_angular_residual": ("relation_angular", LQ * PQ),
    }
    for row in iter_rows(raw / "force_audit.csv"):
        precision = int(row["precision"])
        for prefix, (name, scale) in force_names.items():
            update(name, precision, infinity_norm(raw_vector_from_row(row, prefix)) * scale)
    for row in rows(raw / "reversibility.csv"):
        precision = int(row["precision"])
        update("reversal_position", precision, scalar_from_columns(row, "position_physical_error"))
        update("reversal_momentum", precision, scalar_from_columns(row, "momentum_physical_error"))
    for row in iter_rows(raw / "covariance.csv"):
        precision = int(row["precision"])
        update("frame_position", precision, scalar_from_columns(row, "relative_position_physical"))
        update("frame_momentum", precision, scalar_from_columns(row, "relative_momentum_physical"))
    require(
        set(exact_representation)
        == {"representation_position", "representation_momentum", "representation_energy"},
        "recomputed representation envelope inventory differs",
    )
    for name, envelope in exact_representation.items():
        require(set(envelope) == set(PRECISIONS),
                f"{name}: recomputed precision inventory differs")
        for precision, value in envelope.items():
            update(name, precision, value)

    scaling = {
        name: scaling_until_budget(envelope, budget)
        for name, (budget, envelope) in quantities.items()
    }
    eligible = {
        precision: all(envelope[precision] <= budget for budget, envelope in quantities.values())
        for precision in PRECISIONS
    }
    pair_scaling_diagnostic = {
        name: unit_roundoff_pair_scales(envelope[192], envelope[256], 64)
        for name, (_budget, envelope) in quantities.items()
    }
    return {
        "envelopes": {
            name: {str(precision): ratio_text(value) for precision, value in envelope.items()}
            for name, (_budget, envelope) in quantities.items()
        },
        "scaling_until_budget": scaling,
        "absolute_budget_pass": {
            str(precision): value for precision, value in eligible.items()
        },
        "all_scaling_until_budget_passed": all(scaling.values()),
        "b192_b256_unconditional_pair_scaling_diagnostic": pair_scaling_diagnostic,
    }, eligible, all(scaling.values())


def verify_state_size(
    raw: Path, state_report: dict[str, object],
) -> tuple[dict[str, object], dict[int, bool]]:
    evidence = rows(raw / "state_size.csv")
    require(evidence, "state-size evidence missing")
    groups = grouped(evidence, ("trajectory_id",))
    initial = state_report["initial"]
    endpoint = state_report["endpoint"]
    long_endpoint = state_report["long_endpoint"]
    checkpoint_states = state_report["checkpoint"]
    assert isinstance(initial, dict) and isinstance(endpoint, dict)
    assert isinstance(long_endpoint, dict) and isinstance(checkpoint_states, dict)
    expected_trajectories = {
        f"short:{scenario}:{path}:B{precision}:L{level}"
        for scenario in SCENARIOS for path in (CONTROL, KDK)
        for precision in PRECISIONS for level in LEVELS
    } | {
        f"long:{scenario}:B{precision}:L{level}"
        for scenario in ("k4_internal", "k4_boosted")
        for precision in PRECISIONS for level in LEVELS
    } | {
        f"checkpoint:B{precision}:L{level}"
        for precision in PRECISIONS for level in LEVELS
    }
    require(set(key[0] for key in groups) == expected_trajectories,
            "state-size trajectory inventory differs")
    eligible = {precision: True for precision in PRECISIONS}
    by_precision: dict[int, set[int]] = {precision: set() for precision in PRECISIONS}
    for (trajectory,), group in groups.items():
        precisions = {int(row["precision"]) for row in group}
        packet_counts = {int(row["packet_count"]) for row in group}
        levels = {int(row["level"]) for row in group}
        require(len(precisions) == len(packet_counts) == len(levels) == 1,
                f"{trajectory}: state-size profile changes")
        precision = next(iter(precisions))
        packet_count = next(iter(packet_counts))
        component = 5 + precision // 8
        phase = 6 * component
        packet = 16 + phase
        state_bytes = len(STATE_MAGIC) + 24 + packet_count * packet
        hashes: set[str] = set()
        for row in group:
            require(
                int(row["component_bytes"]) == component
                and int(row["phase_bytes_per_packet"]) == phase
                and int(row["complete_packet_bytes"]) == packet
                and int(row["state_bytes"]) == state_bytes
                and int(row["causal_cache_bytes"]) == 0
                and int(row["causal_history_bytes"]) == 0
                and SHA256.fullmatch(row["state_hash"]) is not None,
                f"{trajectory}: fixed state-size contract differs",
            )
            hashes.add(row["state_hash"])
        by_precision[precision].add(state_bytes)
        labels = {row["label"] for row in group}
        level = int(group[0]["level"])
        if trajectory.startswith("short:"):
            _kind, scenario, path, _precision_text, _level_text = trajectory.split(":")
            require(_precision_text == f"B{precision}" and _level_text == f"L{level}",
                    f"{trajectory}: state-size trajectory/profile identity differs")
            expected_labels = {"initial", "step_1", "final"}
            expected_hashes = {
                "initial": phase_hash(initial[(precision, scenario, "initial", 0)]),
                "final": phase_hash(endpoint[(precision, scenario, path, level)]),
            }
            expected_steps = {"initial": 0, "step_1": 1, "final": STEP_COUNTS[level]}
        elif trajectory.startswith("long:"):
            _kind, scenario, _precision_text, _level_text = trajectory.split(":")
            require(_precision_text == f"B{precision}" and _level_text == f"L{level}",
                    f"{trajectory}: state-size trajectory/profile identity differs")
            expected_labels = {"initial", "step_1", "final"}
            if level > 0:
                expected_labels.add("step_400")
            expected_hashes = {
                "initial": phase_hash(initial[(precision, scenario, "initial", 0)]),
                "final": phase_hash(long_endpoint[(precision, scenario, KDK, level)]),
            }
            expected_steps = {
                "initial": 0, "step_1": 1,
                "final": 16 * STEP_COUNTS[level], "step_400": 400,
            }
        else:
            _kind, _precision_text, _level_text = trajectory.split(":")
            require(_precision_text == f"B{precision}" and _level_text == f"L{level}",
                    f"{trajectory}: state-size trajectory/profile identity differs")
            expected_labels = {"checkpoint"}
            expected_hashes = {
                "checkpoint": phase_hash(
                    checkpoint_states[(precision, "k4_internal", KDK, level)]
                )
            }
            expected_steps = {"checkpoint": STEP_COUNTS[level] // 2}
        require(labels == expected_labels and len(group) == len(expected_labels),
                f"{trajectory}: state-size lifecycle differs")
        for row in group:
            label = row["label"]
            require(int(row["step"]) == expected_steps[label],
                    f"{trajectory}: state-size lifecycle step differs")
            if label in expected_hashes:
                require(row["state_hash"] == expected_hashes[label],
                        f"{trajectory}: state-size anchor hash differs")
        eligible[precision] = eligible[precision] and len({int(row["state_bytes"]) for row in group}) == 1
    require(all(by_precision.values()), "state-size precision inventory differs")
    return {
        "rows": len(evidence),
        "trajectories": len(groups),
        "state_bytes_by_precision": {
            str(precision): sorted(values) for precision, values in by_precision.items()
        },
        "bounded_independent_of_step_count": all(eligible.values()),
        "causal_state_shape": CAUSAL_STATE_SHAPE,
        "source_sha_bound_slots_only_shape": True,
        "canonical_decode_encode_reproduced": True,
        "checkpoint_resume_complete_state_reproduced": True,
        "causal_cache_and_history_bytes": 0,
    }, eligible


def scientific_disposition(
    parent_decision: str,
    highest_precision_dynamics_pass: bool,
    structure_residuals_resolved: bool,
    selected_precision: int | None,
) -> tuple[str, int | None]:
    if parent_decision != PARENT_DECISION:
        return "stop_inconclusive_or_wrong_parent", None
    if not highest_precision_dynamics_pass:
        return "reject_bounded_binary_fractional_phase_state", None
    if not structure_residuals_resolved:
        return "bounded_phase_state_restores_dynamics_but_structure_residuals_unresolved", None
    if selected_precision is None:
        return "bounded_phase_state_converges_but_required_precision_unresolved", None
    return "retain_bounded_variable_exponent_phase_state_for_research", selected_precision


def require_final_outcome(result: dict[str, object]) -> None:
    """Pin the completed lab source to its accepted, reproducible outcome."""
    eligibility = result.get("precision_eligibility")
    require(
        result.get("decision") == FINAL_DECISION
        and result.get("selected_precision") is FINAL_SELECTED_PRECISION
        and result.get("highest_precision_dynamics_pass") is True
        and result.get("structure_residuals_resolved") is False
        and isinstance(eligibility, dict)
        and set(eligibility) == {str(precision) for precision in PRECISIONS}
        and all(value is False for value in eligibility.values()),
        "completed-lab outcome differs from the accepted bounded negative",
    )


def aggregate_precision_scenario_gate(
    scenario_gates: dict[int, dict[str, bool]],
) -> dict[int, bool]:
    """Require every registered scenario independently at each precision."""
    require(set(scenario_gates) == set(PRECISIONS),
            "precision scenario-gate profile differs")
    require(
        all(set(gates) == set(SCENARIOS) for gates in scenario_gates.values()),
        "precision scenario-gate inventory differs",
    )
    return {
        precision: all(scenario_gates[precision][scenario] for scenario in SCENARIOS)
        for precision in PRECISIONS
    }


def combine_precision_eligibility(
    precision_gates: Sequence[dict[int, bool]], shared_gates: Sequence[bool],
) -> dict[int, bool]:
    """Combine independent per-precision gates without cross-precision leakage."""
    require(bool(precision_gates), "precision eligibility gate inventory is empty")
    require(
        all(set(gate) == set(PRECISIONS) for gate in precision_gates),
        "precision eligibility gate profile differs",
    )
    shared = all(shared_gates)
    return {
        precision: shared and all(gate[precision] for gate in precision_gates)
        for precision in PRECISIONS
    }


def verify(
    raw: Path,
    parent_raw: Path,
    allow_dirty: bool = False,
    precomputed_smooth: tuple[
        dict[str, list[Decimal]], dict[str, Decimal], dict[str, list[list[Decimal]]]
    ] | None = None,
) -> dict[str, object]:
    progress("metadata-parent-controls:start")
    meta = verify_schema_metadata_profiles(raw, allow_dirty)
    parent_fingerprint = verify_parent_hashes(raw, parent_raw)
    declared_positive = verify_positive_control_rows(raw, parent_raw)
    progress("metadata-parent-controls:complete")
    progress("smooth-parent-oracle:start")
    if precomputed_smooth is None:
        smooth_models, smooth_initial = load_smooth_problem(parent_raw)
        smooth_data = smooth_oracle_with_samples(smooth_models, smooth_initial)
    else:
        smooth_data = precomputed_smooth
    positive = verify_positive_parent(parent_raw, (smooth_data[0], smooth_data[1]))
    positive["declared_rows"] = declared_positive
    progress("smooth-parent-oracle:complete")

    progress("state-tables-short-replay:start")
    models = load_models(raw)
    state_report = verify_state_tables(raw, parent_raw)
    trajectories, trajectory_traces, short_replay = verify_short_replay(
        raw, state_report, models
    )
    progress("state-tables-short-replay:complete")
    progress("representation-temporal:start")
    (
        representation, representation_temporal_pass,
        highest_precision_dynamics_pass, short_representation_envelopes,
    ) = (
        verify_representation_and_temporal(
            raw, parent_raw, models, trajectories, trajectory_traces,
            smooth_data[0], smooth_data[2]
        )
    )
    progress("representation-temporal:complete")
    progress("composition-contracts:start")
    composition, composition_pass = verify_reversal_checkpoint_covariance_domain(
        raw, state_report, models, trajectories, trajectory_traces
    )
    progress("composition-contracts:complete")
    # The short and auxiliary composition reports contain no replay objects.
    # Release their completed trajectories before materializing a long level.
    del trajectories, trajectory_traces
    progress("long-replay:start")
    long_run, long_pass, long_scaling, long_representation_envelopes = verify_long_replay(
        raw, parent_raw, state_report, models
    )
    progress("long-replay:complete")
    require(set(short_representation_envelopes) == set(long_representation_envelopes),
            "short/long recomputed representation envelope inventory differs")
    representation_envelopes = {
        name: {
            precision: max(
                short_representation_envelopes[name][precision],
                long_representation_envelopes[name][precision],
            )
            for precision in PRECISIONS
        }
        for name in short_representation_envelopes
    }
    progress("structure-residuals-state-size:start")
    residuals, residual_budget_pass, residual_scaling = structure_residual_report(
        raw, state_report, representation_envelopes
    )
    composition["structure_residuals"] = residuals
    state_size, size_pass = verify_state_size(raw, state_report)
    progress("structure-residuals-state-size:complete")

    anchor_qualification = bool(
        long_run["all_required_full_tail_anchors_qualified"]
    )

    control_by_precision = representation["control_distinguishable_by_precision"]
    assert isinstance(control_by_precision, dict)
    short_energy_certificates = representation[
        "short_energy_componentwise_certificates"
    ]
    recovery_certificate_pass = composition["signed_time_recovery_bound_pass"]
    short_frame_certificate_pass = composition["short_frame_bound_pass"]
    long_frame_certificate_pass = long_run["long_frame_bound_pass"]
    long_energy_certificates = long_run[
        "exact_prefix_energy_componentwise_certificates"
    ]
    assert all(isinstance(value, dict) for value in (
        short_energy_certificates, recovery_certificate_pass,
        short_frame_certificate_pass, long_frame_certificate_pass,
        long_energy_certificates,
    ))
    highest_precision_analytic_certificates_pass = (
        bool(short_energy_certificates["256"]["passed"])
        and bool(recovery_certificate_pass["256"])
        and bool(short_frame_certificate_pass["256"])
        and bool(long_frame_certificate_pass["256"])
        and bool(long_energy_certificates["256"]["passed"])
    )
    precision_eligibility = combine_precision_eligibility(
        (
            representation_temporal_pass,
            composition_pass,
            long_pass,
            residual_budget_pass,
            size_pass,
            control_by_precision,
        ),
        (bool(representation["precision_scaling"]), anchor_qualification),
    )
    all_qualitative_gates_converge = (
        residual_scaling and long_scaling
        and bool(composition["highest_precision_frame_contract"])
        and highest_precision_analytic_certificates_pass
        and bool(representation["precision_scaling"])
        and bool(control_by_precision[256])
        and bool(representation["kdk_all_scenarios_second_order"][256])
        and all(size_pass.values())
        and composition["checkpoint_rows"] == len(PRECISIONS) * len(LEVELS)
        and composition["domain_rows"] == len(PRECISIONS) * len(LEVELS)
    )
    structure_residuals_resolved = all_qualitative_gates_converge
    composition["all_qualitative_gates_converge"] = all_qualitative_gates_converge
    composition["highest_precision_analytic_certificates_pass"] = (
        highest_precision_analytic_certificates_pass
    )
    composition["all_required_full_tail_anchors_qualified"] = anchor_qualification
    selected = next(
        (precision for precision in PRECISIONS if precision_eligibility[precision]), None
    )
    decision, selected = scientific_disposition(
        str(positive["decision"]), highest_precision_dynamics_pass,
        structure_residuals_resolved, selected,
    )

    canonical_state_summary = {
        "state_groups": state_report["state_count"],
        "wire_version": 1,
        "registered_precisions": list(PRECISIONS),
        "canonical_hashes_independently_reproduced": True,
    }
    progress("disposition-summary:start")
    result = {
        "schema": "mls.bounded-fractional-phase-state.oracle.v1",
        "precision_decimal_digits": getcontext().prec,
        "source_sha": meta["source_sha"],
        "parent_fingerprint": parent_fingerprint,
        "positive_control": positive,
        "oracle_refinement_errors": {
            key: format(value, ".29E") for key, value in smooth_data[1].items()
        },
        "canonical_states": canonical_state_summary,
        "short_replay": short_replay,
        "representation_and_temporal": representation,
        "composition_contracts": composition,
        "long_run": long_run,
        "state_size": state_size,
        "precision_eligibility": {str(key): value for key, value in precision_eligibility.items()},
        "highest_precision_dynamics_pass": highest_precision_dynamics_pass,
        "structure_residuals_resolved": structure_residuals_resolved,
        "selected_precision": selected,
        "decision": decision,
        "promotion": "NO_PROMOTION",
        "raw_files": {filename: sha256(raw / filename) for filename in FILES},
    }
    progress("disposition-summary:complete")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--parent-raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    arguments = parser.parse_args()
    try:
        result = verify(arguments.raw, arguments.parent_raw, arguments.allow_dirty)
        require_final_outcome(result)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        progress("summary-write:complete")
        print(
            "BOUNDED FRACTIONAL PHASE STATE ORACLE: "
            f"PASS {result['decision']} selected={result['selected_precision']} NO_PROMOTION"
        )
        return 0
    except (OSError, ValueError, ArithmeticError, IndexError, KeyError, OracleError,
            parent.OracleError, foundation.OracleError) as error:
        print(f"BOUNDED FRACTIONAL PHASE STATE ORACLE: FAIL {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
