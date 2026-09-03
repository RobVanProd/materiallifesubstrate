#!/usr/bin/env python3
"""Materialize raw evidence for the Bounded Fractional Phase-State Lab.

The causal packet phase state is finite, fixed-precision ``gmpy2.mpfr``.  All
causal primitives use the preregistered MPFR 4.2.2 round-to-nearest/ties-even
operation graph.  Exact ``mpq`` arithmetic is used only to serialize stored
dyadics, audit residuals, compare the ineligible exact-rational control, and
certify the force-domain chord.

This program writes raw tables only.  It does not select a disposition, seal
evidence, or modify authoritative World mechanics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator

try:
    import gmpy2
    from gmpy2 import mpfr
    from gmpy2 import mpq as Fraction
except ImportError as error:
    raise SystemExit(
        "gmpy2 2.3.1 (MPFR 4.2.2) is required for bounded phase-state evidence"
    ) from error

if gmpy2.version() != "2.3.1":
    raise SystemExit(f"gmpy2 2.3.1 is required; found {gmpy2.version()}")
if gmpy2.mpfr_version() != "MPFR 4.2.2":
    raise SystemExit(f"MPFR 4.2.2 is required; found {gmpy2.mpfr_version()}")

import run_explicit_fractional_phase_state_lab as exact_lab


if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)


PARENT_SHA = "6f25d7428fde7420c1f4cbe1e3565c11a28e817c"
PARENT_TAG = "explicit-fractional-phase-state-lab-evidence-v1"
PARENT_TAG_OBJECT = "a0feca21f7676e0b6f1443c483bd62448d68c65b"
PARENT_ARCHIVE_SHA256 = (
    "77aad47e1842b4fe29760594ee247f609b5d1e88ae7e6b370d86c0bdbb6c71de"
)
PARENT_ARCHIVE_SIZE = 31_142_852
BRANCH = "bounded-fractional-phase-state-lab"

PRECISIONS = (64, 96, 128, 192, 256)
LEADING_EXPONENT_MIN = -16_382
LEADING_EXPONENT_MAX = 16_383
MPFR_EMIN = -16_381
MPFR_EMAX = 16_384
ROUNDING_NAME = "round_to_nearest_ties_to_even"

KDK = "bounded_binary_kick_drift_kick"
CONTROL = "bounded_binary_symplectic_euler_control"
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
DOMAIN_SCRATCH_PADDING_BITS = 64
SIGNED64_MIN = -(2**63)
SIGNED64_MAX = 2**63 - 1
RAW_X_LIMIT = Fraction(2**48)
RAW_P_LIMIT = Fraction(2**40)
RAW_R_LIMIT = Fraction(2**49)
RAW_J_LIMIT = Fraction(2**40)
EXACT_MAX_COMPONENT_BITS = 262_144
EXACT_MEDIAN_COMPONENT_BITS = 131_072
EXACT_MAX_CHECKPOINT_BYTES = 8_388_608

POSITION_BUDGET = LQ / 2**20
MOMENTUM_BUDGET = PQ / 2**20
ANGULAR_BUDGET = LQ * PQ / 2**20
ENERGY_BUDGET = EQ / 2**20
ENERGY_SLOPE_BUDGET = ENERGY_BUDGET / 16

MAGIC = b"MLS-BOUNDED-BINARY-PHASE-v1\x00"
WIRE_VERSION = 1
OBSERVER_EVENT_MAGIC = b"MLS-BOUNDED-OBSERVER-EVENT-v1\x00"
OBSERVER_STREAM_MAGIC = b"MLS-BOUNDED-OBSERVER-STREAM-v1\x00"
ROUNDING_AUDIT_MAGIC = b"MLS-BOUNDED-ROUNDING-AUDIT-v1\x00"
ROUNDING_AUDIT_MERGE_MAGIC = b"MLS-BOUNDED-ROUNDING-AUDIT-MERGE-v1\x00"
CAUSAL_STATE_SHAPE = (
    "State(precision,time_raw,packets);"
    "Packet(identifier,mass_raw,x[3],p[3]);slots_only_v1"
)

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


class LabError(RuntimeError):
    """Deterministic experiment failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LabError(message)


def ratio_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def exact_float(value: float) -> Fraction:
    require(math.isfinite(value), "nonfinite binary64 cannot enter bounded state")
    return Fraction(*value.as_integer_ratio())


def float_bits(value: float) -> int:
    return struct.unpack(">Q", struct.pack(">d", value))[0]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_rows(path: Path, fields: tuple[str, ...], rows: Iterable[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: str(row.get(key, "")) for key in fields})


class CsvSink:
    """Deterministic append-only CSV sink for high-cardinality causal audits."""

    def __init__(self, path: Path, fields: tuple[str, ...]):
        self.fields = fields
        self.stream = path.open("w", encoding="utf-8", newline="")
        self.writer = csv.DictWriter(self.stream, fieldnames=fields, lineterminator="\n")
        self.writer.writeheader()

    def append(self, row: dict[str, object]) -> None:
        self.writer.writerow({key: str(row.get(key, "")) for key in self.fields})

    def extend(self, rows: Iterable[dict[str, object]]) -> None:
        for row in rows:
            self.append(row)

    def close(self) -> None:
        self.stream.close()


def make_context(precision: int) -> gmpy2.context:
    require(precision in PRECISIONS, "unregistered bounded precision")
    return gmpy2.context(
        precision=precision,
        round=gmpy2.RoundToNearest,
        emin=MPFR_EMIN,
        emax=MPFR_EMAX,
        subnormalize=False,
        trap_underflow=True,
        trap_overflow=True,
        trap_invalid=True,
        trap_erange=True,
        trap_divzero=True,
        trap_inexact=False,
    )


def check_context(context: gmpy2.context, precision: int) -> None:
    require(context.precision == precision, "ambient MPFR precision entered candidate")
    require(context.round == gmpy2.RoundToNearest, "MPFR rounding mode differs")
    require(context.emin == MPFR_EMIN and context.emax == MPFR_EMAX,
            "MPFR exponent range differs")
    require(not context.subnormalize, "MPFR subnormalization enabled")


@dataclass
class OperationCounter:
    total: int = 0
    categories: dict[str, int] = field(default_factory=dict)
    inexact_total: int = 0
    inexact_categories: dict[str, int] = field(default_factory=dict)
    _audit: object = field(
        default_factory=lambda: hashlib.sha256(ROUNDING_AUDIT_MAGIC), repr=False
    )

    def count(
        self, category: str, inexact: bool, exact: Fraction, rounded: Fraction,
        error: Fraction, half_ulp_bound: Fraction,
    ) -> None:
        self.total += 1
        self.categories[category] = self.categories.get(category, 0) + 1
        if inexact:
            self.inexact_total += 1
            self.inexact_categories[category] = self.inexact_categories.get(category, 0) + 1
        audit = self._audit
        assert hasattr(audit, "update")
        audit.update(b"L")
        audit.update(struct.pack("<Q", self.total))
        for value in (
            category, ratio_text(exact), ratio_text(rounded), ratio_text(error),
            ratio_text(half_ulp_bound), str(inexact).lower(),
        ):
            encoded = value.encode("utf-8")
            audit.update(struct.pack("<Q", len(encoded)))
            audit.update(encoded)

    def merge(self, other: "OperationCounter") -> None:
        audit = self._audit
        assert hasattr(audit, "update")
        audit.update(ROUNDING_AUDIT_MERGE_MAGIC)
        audit.update(struct.pack("<Q", other.total))
        audit.update(bytes.fromhex(other.audit_sha256()))
        self.total += other.total
        self.inexact_total += other.inexact_total
        for key, value in other.categories.items():
            self.categories[key] = self.categories.get(key, 0) + value
        for key, value in other.inexact_categories.items():
            self.inexact_categories[key] = self.inexact_categories.get(key, 0) + value

    def audit_sha256(self) -> str:
        audit = self._audit
        assert hasattr(audit, "copy")
        return audit.copy().hexdigest()


def canonical_operation_categories(categories: dict[str, int]) -> str:
    """Locale-independent spelling of a complete nonzero operation breakdown."""
    require(all(value >= 0 for value in categories.values()),
            "negative causal operation count")
    return ";".join(
        f"{key}={categories[key]}" for key in sorted(categories) if categories[key]
    )


def _checked(
    context: gmpy2.context,
    precision: int,
    category: str,
    operation: Callable[[], mpfr],
    counter: OperationCounter | None = None,
    exact_result: Fraction | None = None,
) -> mpfr:
    check_context(context, precision)
    context.clear_flags()
    try:
        value = operation()
    except (ArithmeticError, ValueError) as error:
        raise LabError(f"phase_range_failure:{category}:{type(error).__name__}") from error
    # Capture inexact before any diagnostic conversion can touch the context.
    inexact = bool(context.inexact)
    require(gmpy2.is_finite(value), f"phase_range_failure:{category}:nonfinite")
    require(not (context.underflow or context.overflow or context.invalid or
                 context.erange or context.divzero),
            f"phase_range_failure:{category}:MPFR_flag")
    require(value.precision == precision, f"mixed precision result in {category}")
    if gmpy2.is_zero(value):
        # Canonicalization is representational, not a hidden numerical state.
        value = gmpy2.mpfr(0, precision=precision)
        exponent = 0
    else:
        exponent = int(gmpy2.get_exp(value)) - 1
        require(LEADING_EXPONENT_MIN <= exponent <= LEADING_EXPONENT_MAX,
                f"phase_range_failure:{category}:leading_exponent")
    if exact_result is not None:
        rounded = exact_dyadic(value)
        error = rounded - exact_result
        half_ulp_bound = (
            Fraction() if exact_result == 0
            else (Fraction(2**(exponent - precision)) if exponent >= precision
                  else Fraction(1, 2**(precision - exponent)))
        )
        require(inexact == (error != 0), f"{category}: MPFR inexact flag differs")
        require(abs(error) <= half_ulp_bound, f"{category}: half-ULP bound exceeded")
        if counter is not None:
            counter.count(
                category, inexact, exact_result, rounded, error, half_ulp_bound
            )
    else:
        require(counter is None, f"{category}: counted primitive lacks exact audit")
    return value


def rounded_fraction(
    context: gmpy2.context,
    precision: int,
    value: Fraction | int,
    category: str,
    counter: OperationCounter | None = None,
) -> mpfr:
    rational = value if isinstance(value, Fraction) else Fraction(value)
    return _checked(
        context, precision, category, lambda: gmpy2.mpfr(rational), counter, rational
    )


def rounded_add(context: gmpy2.context, precision: int, first: mpfr, second: mpfr,
                category: str, counter: OperationCounter | None = None) -> mpfr:
    exact = exact_dyadic(first) + exact_dyadic(second)
    return _checked(context, precision, category, lambda: first + second, counter, exact)


def rounded_sub(context: gmpy2.context, precision: int, first: mpfr, second: mpfr,
                category: str, counter: OperationCounter | None = None) -> mpfr:
    exact = exact_dyadic(first) - exact_dyadic(second)
    return _checked(context, precision, category, lambda: first - second, counter, exact)


def rounded_mul(context: gmpy2.context, precision: int, first: mpfr, second: mpfr,
                category: str, counter: OperationCounter | None = None) -> mpfr:
    exact = exact_dyadic(first) * exact_dyadic(second)
    return _checked(context, precision, category, lambda: first * second, counter, exact)


def rounded_div(context: gmpy2.context, precision: int, first: mpfr, second: mpfr,
                category: str, counter: OperationCounter | None = None) -> mpfr:
    divisor = exact_dyadic(second)
    require(divisor != 0, f"phase_range_failure:{category}:zero_divisor")
    exact = exact_dyadic(first) / divisor
    return _checked(context, precision, category, lambda: first / second, counter, exact)


def exact_dyadic(value: mpfr) -> Fraction:
    require(gmpy2.is_finite(value), "observer received nonfinite MPFR value")
    numerator, denominator = value.as_integer_ratio()
    return Fraction(numerator, denominator)


def canonical_dyadic_text(value: Fraction) -> str:
    """Canonical compact ``[-]0xODD@EXP2`` spelling of an exact dyadic."""
    if value == 0:
        return "0"
    numerator = int(value.numerator)
    denominator = int(value.denominator)
    require(denominator > 0 and denominator & (denominator - 1) == 0,
            "canonical dyadic formatter received nondyadic value")
    sign = "-" if numerator < 0 else ""
    magnitude = abs(numerator)
    trailing = (magnitude & -magnitude).bit_length() - 1
    odd = magnitude >> trailing
    exponent = trailing - (denominator.bit_length() - 1)
    return f"{sign}0x{odd:x}@{exponent}"


class Profile:
    def __init__(self, precision: int):
        self.precision = precision
        self.template = make_context(precision)
        lq_counter = OperationCounter()
        with gmpy2.context(self.template) as context:
            self.lq = rounded_fraction(
                context, precision, LQ, "profile_Lq", lq_counter
            )
        require(lq_counter.total == 1, "profile Lq conversion count differs")
        self.lq_conversion_inexact = lq_counter.inexact_total == 1
        self.lq_rounding_audit_sha256 = lq_counter.audit_sha256()

    def activate(self) -> gmpy2.context:
        return gmpy2.context(self.template)

    @property
    def component_bytes(self) -> int:
        return 5 + self.precision // 8

    @property
    def phase_bytes_per_packet(self) -> int:
        return 6 * self.component_bytes

    @property
    def packet_bytes(self) -> int:
        return 16 + self.phase_bytes_per_packet


_PROFILE_CACHE: dict[int, Profile] = {}


def profile_for(precision: int) -> Profile:
    profile = _PROFILE_CACHE.get(precision)
    if profile is None:
        profile = Profile(precision)
        _PROFILE_CACHE[precision] = profile
    return profile


@dataclass(slots=True)
class Packet:
    identifier: int
    mass_raw: int
    x: list[mpfr]
    p: list[mpfr]

    def clone(self) -> "Packet":
        return Packet(self.identifier, self.mass_raw, list(self.x), list(self.p))


@dataclass(slots=True)
class State:
    precision: int
    time_raw: int
    packets: list[Packet]

    def clone(self) -> "State":
        return State(self.precision, self.time_raw, [packet.clone() for packet in self.packets])


@dataclass
class ForceRelation:
    relation: exact_lab.Relation
    offset: list[mpfr]
    length: float
    conjugate: float
    extension: float


@dataclass
class RunResult:
    status: str
    initial: State
    final: State
    requested_steps: int
    completed_steps: int
    samples: list[State]
    energies: list[tuple[Fraction, Fraction, Fraction, int]]
    # One ordered list of canonical observer-event digests per committed step.
    # Keeping the step boundary makes an interior checkpoint suffix explicit.
    events: list[list[str]]
    operations: OperationCounter


@dataclass
class ExactShadowResult:
    samples: list[exact_lab.State]
    status: str
    requested_steps: int
    completed_steps: int
    first_crossing_step: int | None
    last_within_ceiling_step: int
    maximum_component_bits: int
    maximum_state_median_bits: Fraction
    maximum_checkpoint_bytes: int
    crossing_component_bits: int | None
    crossing_state_median_bits: Fraction | None
    crossing_checkpoint_bytes: int | None


def canonical_packets(state: State) -> list[Packet]:
    require(type(state) is State, "causal state type differs from frozen shape")
    packets = sorted((packet.clone() for packet in state.packets), key=lambda row: row.identifier)
    require(all(type(packet) is Packet for packet in packets),
            "causal packet type differs from frozen shape")
    require(len({packet.identifier for packet in packets}) == len(packets),
            "duplicate packet ID")
    require(all(packet.identifier > 0 and packet.mass_raw > 0 for packet in packets),
            "invalid packet identity or mass")
    return packets


def validate_causal_state_shape() -> None:
    require(State.__slots__ == ("precision", "time_raw", "packets"),
            "causal State slots differ")
    require(Packet.__slots__ == ("identifier", "mass_raw", "x", "p"),
            "causal Packet slots differ")


def _scaled_integer(value: Fraction, shift: int) -> int:
    scaled = value * (Fraction(2**shift) if shift >= 0 else Fraction(1, 2**(-shift)))
    require(scaled.denominator == 1, "MPFR value is not a precision-B dyadic")
    return int(scaled.numerator)


def component_parts(value: mpfr, precision: int) -> tuple[int, int, int]:
    require(value.precision == precision and gmpy2.is_finite(value),
            "component precision or finiteness differs")
    if gmpy2.is_zero(value):
        require(not gmpy2.is_signed(value), "negative zero is noncanonical")
        return 0, 0, 0
    rational = exact_dyadic(value)
    sign = 1 if rational < 0 else 0
    magnitude = abs(rational)
    denominator_exponent = int(magnitude.denominator).bit_length() - 1
    require(2**denominator_exponent == magnitude.denominator,
            "MPFR denominator is not a power of two")
    exponent = int(magnitude.numerator).bit_length() - 1 - denominator_exponent
    require(LEADING_EXPONENT_MIN <= exponent <= LEADING_EXPONENT_MAX,
            "component leading exponent outside profile")
    significand = _scaled_integer(magnitude, precision - 1 - exponent)
    require(2**(precision - 1) <= significand < 2**precision,
            "component significand is not full-width normalized")
    return sign, exponent, significand


def encode_component(value: mpfr, precision: int) -> bytes:
    sign, exponent, significand = component_parts(value, precision)
    return (
        bytes((sign,))
        + precision.to_bytes(2, "little")
        + exponent.to_bytes(2, "little", signed=True)
        + significand.to_bytes(precision // 8, "big")
    )


def decode_component(data: bytes, precision: int, profile: Profile) -> mpfr:
    require(len(data) == profile.component_bytes, "component byte width differs")
    sign = data[0]
    stored_precision = int.from_bytes(data[1:3], "little")
    exponent = int.from_bytes(data[3:5], "little", signed=True)
    significand = int.from_bytes(data[5:], "big")
    require(sign in (0, 1) and stored_precision == precision,
            "component sign or precision differs")
    if significand == 0:
        require(sign == 0 and exponent == 0, "noncanonical zero encoding")
        with profile.activate() as context:
            return rounded_fraction(context, precision, Fraction(), "decode_zero")
    require(2**(precision - 1) <= significand < 2**precision,
            "nonnormalized component significand")
    require(LEADING_EXPONENT_MIN <= exponent <= LEADING_EXPONENT_MAX,
            "encoded component exponent outside profile")
    value = Fraction(significand)
    shift = exponent - (precision - 1)
    value = value * (Fraction(2**shift) if shift >= 0 else Fraction(1, 2**(-shift)))
    if sign:
        value = -value
    with profile.activate() as context:
        result = rounded_fraction(context, precision, value, "decode_component")
    require(exact_dyadic(result) == value, "canonical component did not decode exactly")
    require(encode_component(result, precision) == data, "component round trip differs")
    return result


def encode_state(state: State) -> bytes:
    profile = profile_for(state.precision)
    validate_state(state)
    output = bytearray(MAGIC)
    output.extend(WIRE_VERSION.to_bytes(2, "little"))
    output.extend(state.precision.to_bytes(2, "little"))
    output.extend(LEADING_EXPONENT_MIN.to_bytes(2, "little", signed=True))
    output.extend(LEADING_EXPONENT_MAX.to_bytes(2, "little", signed=True))
    output.extend(state.time_raw.to_bytes(8, "little", signed=True))
    packets = canonical_packets(state)
    output.extend(len(packets).to_bytes(8, "little"))
    for packet in packets:
        output.extend(packet.identifier.to_bytes(8, "little"))
        output.extend(packet.mass_raw.to_bytes(8, "little", signed=True))
        for vector in (packet.x, packet.p):
            for value in vector:
                output.extend(encode_component(value, state.precision))
    expected = len(MAGIC) + 24 + len(packets) * profile.packet_bytes
    require(len(output) == expected, "canonical state byte construction differs")
    return bytes(output)


def decode_state(data: bytes) -> State:
    require(data.startswith(MAGIC), "checkpoint magic differs")
    cursor = len(MAGIC)
    require(len(data) >= cursor + 24, "truncated checkpoint profile")
    version = int.from_bytes(data[cursor:cursor + 2], "little"); cursor += 2
    precision = int.from_bytes(data[cursor:cursor + 2], "little"); cursor += 2
    exponent_min = int.from_bytes(data[cursor:cursor + 2], "little", signed=True); cursor += 2
    exponent_max = int.from_bytes(data[cursor:cursor + 2], "little", signed=True); cursor += 2
    require((version, exponent_min, exponent_max) ==
            (WIRE_VERSION, LEADING_EXPONENT_MIN, LEADING_EXPONENT_MAX),
            "checkpoint profile differs")
    profile = Profile(precision)
    time_raw = int.from_bytes(data[cursor:cursor + 8], "little", signed=True); cursor += 8
    count = int.from_bytes(data[cursor:cursor + 8], "little"); cursor += 8
    packets: list[Packet] = []
    for _ in range(count):
        require(cursor + 16 <= len(data), "truncated packet record")
        identifier = int.from_bytes(data[cursor:cursor + 8], "little"); cursor += 8
        mass_raw = int.from_bytes(data[cursor:cursor + 8], "little", signed=True); cursor += 8
        vectors: list[list[mpfr]] = []
        for _kind in range(2):
            vector: list[mpfr] = []
            for _axis in range(3):
                end = cursor + profile.component_bytes
                require(end <= len(data), "truncated component record")
                vector.append(decode_component(data[cursor:end], precision, profile))
                cursor = end
            vectors.append(vector)
        packets.append(Packet(identifier, mass_raw, vectors[0], vectors[1]))
    require(cursor == len(data), "checkpoint trailing bytes")
    result = State(precision, time_raw, packets)
    require(encode_state(result) == data, "checkpoint canonical round trip differs")
    return result


def state_hash(state: State) -> str:
    return hashlib.sha256(encode_state(state)).hexdigest()


def fraction_hash(value: Fraction) -> str:
    return exact_lab.fraction_hash(value)


def vector_hash(value: Iterable[Fraction]) -> str:
    components = tuple(value)
    require(len(components) == 3, "evidence vector hash dimension differs")
    return exact_lab.rational_vector_hash(components)


def packet_lookup(state: State) -> dict[int, Packet]:
    return {packet.identifier: packet for packet in state.packets}


def relation_offset(
    state: State,
    relation: exact_lab.Relation,
    context: gmpy2.context,
    counter: OperationCounter | None = None,
) -> list[mpfr]:
    lookup = packet_lookup(state)
    return [
        rounded_sub(context, state.precision,
                    lookup[relation.second_id].x[axis], lookup[relation.first_id].x[axis],
                    "relative_subtraction", counter)
        for axis in range(3)
    ]


def exact_reference_offset(model: exact_lab.Model, relation: exact_lab.Relation) -> list[Fraction]:
    return exact_lab.reference_offset(model, relation)


def exact_stored_relation_offset(state: State, relation: exact_lab.Relation) -> list[Fraction]:
    """Subtract exact dyadic stored endpoints for domain certification only."""
    lookup = packet_lookup(state)
    return [
        exact_dyadic(lookup[relation.second_id].x[axis])
        - exact_dyadic(lookup[relation.first_id].x[axis])
        for axis in range(3)
    ]


def vector_add(first: list[Fraction], second: list[Fraction]) -> list[Fraction]:
    return [first[axis] + second[axis] for axis in range(3)]


def vector_sub(first: list[Fraction], second: list[Fraction]) -> list[Fraction]:
    return [first[axis] - second[axis] for axis in range(3)]


def vector_scale(scale: Fraction, value: list[Fraction]) -> list[Fraction]:
    return [scale * component for component in value]


def dot(first: list[Fraction], second: list[Fraction]) -> Fraction:
    return sum((first[axis] * second[axis] for axis in range(3)), Fraction())


def cross(first: list[Fraction], second: list[Fraction]) -> list[Fraction]:
    return [
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    ]


def domain_scratch_bit_limit(precision: int) -> int:
    """Universal scratch cap for the registered exact-dyadic chord predicate.

    A stored component aligned to the smallest registered quantum needs at most
    ``B + (Emax-Emin)`` bits.  Two endpoint differences add two carry bits;
    the quartic interior predicate and its ``2^-48`` comparison then fit under
    four times that base width plus the frozen 64-bit safety allowance.
    """
    require(precision in PRECISIONS, "unregistered domain scratch precision")
    return 4 * (precision + LEADING_EXPONENT_MAX - LEADING_EXPONENT_MIN) \
        + DOMAIN_SCRATCH_PADDING_BITS


class DomainScratch:
    """Fail-closed integer scratch ledger for exact dyadic domain predicates."""

    def __init__(self, precision: int):
        self.limit_bits = domain_scratch_bit_limit(precision)
        self.observed_bits = 0

    @staticmethod
    def _width(value: int) -> int:
        return abs(value).bit_length()

    def reserve(self, bits: int) -> None:
        require(bits >= 0, "negative domain scratch width")
        self.observed_bits = max(self.observed_bits, bits)
        require(bits <= self.limit_bits, "domain_scratch_bound_exceeded")

    def observe(self, value: int) -> int:
        self.reserve(self._width(value))
        return value

    def add(self, first: int, second: int) -> int:
        if first == 0:
            return self.observe(second)
        if second == 0:
            return self.observe(first)
        self.reserve(max(self._width(first), self._width(second)) + 1)
        return self.observe(first + second)

    def subtract(self, first: int, second: int) -> int:
        if second == 0:
            return self.observe(first)
        if first == 0:
            return self.observe(-second)
        self.reserve(max(self._width(first), self._width(second)) + 1)
        return self.observe(first - second)

    def multiply(self, first: int, second: int) -> int:
        if first == 0 or second == 0:
            return self.observe(0)
        self.reserve(self._width(first) + self._width(second))
        return self.observe(first * second)

    def shift_left(self, value: int, shift: int) -> int:
        require(shift >= 0, "negative domain scratch left shift")
        if value == 0:
            return self.observe(0)
        self.reserve(self._width(value) + shift)
        return self.observe(value << shift)


@dataclass(frozen=True)
class DomainCertificate:
    safe: bool
    minimum_case: str
    lhs: Fraction
    rhs: Fraction
    scratch_observed_bits: int
    scratch_limit_bits: int


def _dyadic_term(value: Fraction) -> tuple[int, int]:
    """Return signed odd integer and base-two exponent for an exact dyadic."""
    numerator = int(value.numerator)
    denominator = int(value.denominator)
    require(denominator > 0 and denominator & (denominator - 1) == 0,
            "domain predicate received nondyadic value")
    if numerator == 0:
        return 0, 0
    magnitude = abs(numerator)
    trailing = (magnitude & -magnitude).bit_length() - 1
    odd = magnitude >> trailing
    if numerator < 0:
        odd = -odd
    return odd, trailing - (denominator.bit_length() - 1)


def _aligned_dyadic_integers(
    values: Iterable[Fraction], scratch: DomainScratch
) -> tuple[list[int], int]:
    terms = [_dyadic_term(value) for value in values]
    exponents = [exponent for integer, exponent in terms if integer]
    common_exponent = min(exponents, default=0)
    result: list[int] = []
    for integer, exponent in terms:
        if integer == 0:
            result.append(scratch.observe(0))
            continue
        shift = exponent - common_exponent
        scratch.reserve(abs(integer).bit_length() + shift)
        result.append(scratch.observe(integer << shift))
    return result, common_exponent


def _integer_dot(first: list[int], second: list[int], scratch: DomainScratch) -> int:
    require(len(first) == len(second) == 3, "domain vector dimension differs")
    result = 0
    for first_component, second_component in zip(first, second):
        result = scratch.add(
            result, scratch.multiply(first_component, second_component))
    return result


def _fraction_from_scaled_integer(value: int, exponent: int) -> Fraction:
    if exponent >= 0:
        return Fraction(value * 2**exponent)
    return Fraction(value, 2**(-exponent))


def bounded_chord_certificate(
    initial: list[Fraction], final: list[Fraction], reference: list[Fraction],
    precision: int,
) -> DomainCertificate:
    """Certify the exact stored chord using only cap-checked integer arithmetic."""
    require(len(initial) == len(final) == len(reference) == 3,
            "domain vector dimension differs")
    scratch = DomainScratch(precision)
    aligned, common_exponent = _aligned_dyadic_integers(
        [*initial, *final, *reference], scratch)
    first = aligned[0:3]
    last = aligned[3:6]
    reference_integer = aligned[6:9]
    delta = [scratch.subtract(last[axis], first[axis]) for axis in range(3)]
    dd = _integer_dot(delta, delta, scratch)
    aa = _integer_dot(first, first, scratch)
    ad = _integer_dot(first, delta, scratch)
    reference_squared = _integer_dot(reference_integer, reference_integer, scratch)
    require(reference_squared > 0, "zero reference relation")

    if dd == 0 or ad >= 0:
        comparison_lhs = scratch.shift_left(aa, 48)
        comparison_rhs = scratch.observe(reference_squared)
        lhs = _fraction_from_scaled_integer(aa, 2 * common_exponent)
        rhs = _fraction_from_scaled_integer(reference_squared, 2 * common_exponent - 48)
        minimum_case = "initial"
    elif ad <= -dd:
        final_squared = _integer_dot(last, last, scratch)
        comparison_lhs = scratch.shift_left(final_squared, 48)
        comparison_rhs = scratch.observe(reference_squared)
        lhs = _fraction_from_scaled_integer(final_squared, 2 * common_exponent)
        rhs = _fraction_from_scaled_integer(reference_squared, 2 * common_exponent - 48)
        minimum_case = "final"
    else:
        area_squared = scratch.subtract(
            scratch.multiply(aa, dd), scratch.multiply(ad, ad))
        comparison_lhs = scratch.shift_left(area_squared, 48)
        comparison_rhs = scratch.multiply(reference_squared, dd)
        lhs = _fraction_from_scaled_integer(area_squared, 4 * common_exponent)
        rhs = _fraction_from_scaled_integer(comparison_rhs, 4 * common_exponent - 48)
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
    offset: list[Fraction], reference: list[Fraction], precision: int | None = None
) -> bool:
    if precision is not None:
        return bounded_chord_certificate(offset, offset, reference, precision).safe
    reference_squared = dot(reference, reference)
    return reference_squared > 0 and dot(offset, offset) >= SAFE_SQUARED_RATIO * reference_squared


def chord_is_safe(initial: list[Fraction], final: list[Fraction],
                  reference: list[Fraction], precision: int | None = None) -> bool:
    if precision is not None:
        return bounded_chord_certificate(initial, final, reference, precision).safe
    return chord_certificate(initial, final, reference)[0]


def chord_certificate(initial: list[Fraction], final: list[Fraction],
                      reference: list[Fraction]) -> tuple[bool, str, Fraction, Fraction]:
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
        lhs = dot(vector_add(initial, delta), vector_add(initial, delta))
        rhs = SAFE_SQUARED_RATIO * reference_squared
        return lhs >= rhs, "final", lhs, rhs
    lhs = aa * dd - ad * ad
    rhs = SAFE_SQUARED_RATIO * reference_squared * dd
    return lhs >= rhs, "interior", lhs, rhs


def _path_b_from_si(current: list[float], reference: list[float],
                    frozen_reference_length: float) -> tuple[float, float]:
    length = exact_lab.stable_norm(current)
    require(length > 0.0 and math.isfinite(length), "force_domain_failure")
    numerator = (0.0, 0.0)
    for axis in range(3):
        difference = exact_lab._two_difference(current[axis], reference[axis])
        total = exact_lab._two_sum(current[axis], reference[axis])
        numerator = exact_lab._dd_add(numerator, exact_lab._dd_mul(difference, total))
    denominator = length + frozen_reference_length
    require(denominator > 0.0 and math.isfinite(denominator), "invalid Path-B denominator")
    extension = exact_lab._dd_div(numerator, (denominator, 0.0))[0]
    require(math.isfinite(extension), "nonfinite Path-B extension")
    return length, extension


def force_and_energy(
    model: exact_lab.Model,
    state: State,
    profile: Profile,
    counter: OperationCounter | None = None,
) -> tuple[list[ForceRelation], float]:
    geometry: list[tuple[exact_lab.Relation, list[mpfr], float, float]] = []
    with profile.activate() as context:
        for relation in model.relations:
            raw = relation_offset(state, relation, context, counter)
            raw_exact = [exact_dyadic(value) for value in raw]
            reference_raw = exact_reference_offset(model, relation)
            require(relation_is_safe(
                exact_stored_relation_offset(state, relation), reference_raw,
                state.precision),
                "force_domain_failure")
            require(max(abs(value) for value in raw_exact) < RAW_R_LIMIT,
                    "raw_relation_evidence_bound_exceeded")
            current_si: list[float] = []
            for value in raw:
                si = rounded_mul(context, state.precision, value, profile.lq,
                                 "relative_unit_multiplication", counter)
                as_float = float(si)
                require(math.isfinite(as_float), "binary64 relative conversion failed")
                current_si.append(as_float)
            reference_si = [float(value * LQ) for value in reference_raw]
            length, extension = _path_b_from_si(
                current_si, reference_si, relation.rest_length)
            geometry.append((relation, raw, length, extension))
    conjugates: list[float] = []
    for row in range(len(model.relations)):
        value = 0.0
        for column in range(len(model.relations)):
            value += model.h[row][column] * geometry[column][3]
        require(math.isfinite(value), "nonfinite force conjugate")
        conjugates.append(value)
    energy_twice = 0.0
    for index, entry in enumerate(geometry):
        energy_twice += entry[3] * conjugates[index]
    require(math.isfinite(energy_twice), "nonfinite accepted potential")
    return [
        ForceRelation(entry[0], entry[1], entry[2], conjugates[index], entry[3])
        for index, entry in enumerate(geometry)
    ], 0.5 * energy_twice


def exact_state_invariants(state: State) -> tuple[list[Fraction], list[Fraction]]:
    momentum = [Fraction(), Fraction(), Fraction()]
    angular = [Fraction(), Fraction(), Fraction()]
    for packet in state.packets:
        x = [exact_dyadic(value) for value in packet.x]
        p = [exact_dyadic(value) for value in packet.p]
        momentum = vector_add(momentum, p)
        angular = vector_add(angular, cross(x, p))
    return momentum, angular


def kinetic_energy(state: State) -> Fraction:
    result = Fraction()
    for packet in state.packets:
        p = [exact_dyadic(value) for value in packet.p]
        result += dot(p, p) * PQ * PQ / (2 * packet.mass_raw * MQ)
    return result


def observed_energy(
    model: exact_lab.Model, state: State, profile: Profile
) -> tuple[Fraction, Fraction, Fraction, int]:
    _relations, potential_float = force_and_energy(model, state, profile)
    kinetic = kinetic_energy(state)
    potential = exact_float(potential_float)
    return kinetic, potential, kinetic + potential, float_bits(potential_float)


def validate_state(state: State) -> None:
    require(state.precision in PRECISIONS, "state precision is unregistered")
    require(SIGNED64_MIN <= state.time_raw <= SIGNED64_MAX, "state time overflow")
    require(len(canonical_packets(state)) == len(state.packets), "packet order validation failed")
    for packet in state.packets:
        require(len(packet.x) == len(packet.p) == 3, "phase vector shape differs")
        require(SIGNED64_MIN <= packet.mass_raw <= SIGNED64_MAX and packet.mass_raw > 0,
                "packet mass invalid")
        for value in packet.x:
            component_parts(value, state.precision)
            require(abs(exact_dyadic(value)) < RAW_X_LIMIT, "raw_position_evidence_bound_exceeded")
        for value in packet.p:
            component_parts(value, state.precision)
            require(abs(exact_dyadic(value)) < RAW_P_LIMIT, "raw_momentum_evidence_bound_exceeded")


def _add_vector_fields(row: dict[str, object], prefix: str,
                       value: list[Fraction], scale: Fraction = Fraction(1),
                       include_components: bool = True,
                       include_raw_components: bool = True) -> None:
    physical = vector_scale(scale, value)
    row[f"{prefix}_hash"] = vector_hash(physical)
    raw_maximum = max((abs(item) for item in value), default=Fraction())
    row[f"{prefix}_raw_max_dyadic"] = canonical_dyadic_text(raw_maximum)
    if include_raw_components:
        for axis, component in zip("xyz", value):
            row[f"{prefix}_raw_{axis}_dyadic"] = canonical_dyadic_text(component)
    if include_components:
        maximum = max((abs(item) for item in physical), default=Fraction())
        row[f"{prefix}_max_num"] = maximum.numerator
        row[f"{prefix}_max_den"] = maximum.denominator
        for axis, component in zip("xyz", physical):
            row[f"{prefix}_{axis}_num"] = component.numerator
            row[f"{prefix}_{axis}_den"] = component.denominator


def record_invariant(
    rows: list[dict[str, object]], trajectory: str, precision: int, level: int,
    step: int, stage: str, state: State,
    initial: tuple[list[Fraction], list[Fraction]],
    observer_events: list[str] | None = None,
) -> None:
    current = exact_state_invariants(state)
    row: dict[str, object] = {
        "trajectory_id": trajectory,
        "precision": precision,
        "level": level,
        "step": step,
        "stage": stage,
        "state_hash": state_hash(state),
    }
    compact = trajectory.startswith("long:")
    _add_vector_fields(row, "momentum", current[0], PQ,
                       include_components=not compact,
                       include_raw_components=not compact)
    _add_vector_fields(row, "angular", current[1], LQ * PQ,
                       include_components=not compact,
                       include_raw_components=not compact)
    _add_vector_fields(row, "delta_momentum", vector_sub(current[0], initial[0]), PQ,
                       include_components=not compact, include_raw_components=True)
    _add_vector_fields(row, "delta_angular", vector_sub(current[1], initial[1]), LQ * PQ,
                       include_components=not compact, include_raw_components=True)
    rows.append(row)
    if observer_events is not None:
        observer_events.append(observer_event_digest("invariant", row))


def _actual_packet_delta(before: list[mpfr], after: list[mpfr]) -> list[Fraction]:
    return [exact_dyadic(after[axis]) - exact_dyadic(before[axis]) for axis in range(3)]


def kick(
    model: exact_lab.Model,
    state: State,
    interval_raw: int,
    profile: Profile,
    trajectory: str = "algorithm",
    level: int = 0,
    step: int = 0,
    stage: str = "kick",
    force_rows: list[dict[str, object]] | None = None,
    counter: OperationCounter | None = None,
    observer_events: list[str] | None = None,
) -> State:
    result = state.clone()
    evaluated, _potential = force_and_energy(model, state, profile, counter)
    lookup = packet_lookup(result)
    frozen_lookup = packet_lookup(state)
    with profile.activate() as context:
        c_kick = rounded_fraction(
            context, state.precision, Fraction(interval_raw) * TQ * LQ / PQ,
            "kick_constant_conversion", counter)
        for relation_value in evaluated:
            conjugate = rounded_fraction(
                context, state.precision, exact_float(relation_value.conjugate),
                "binary64_conjugate_exact_conversion")
            length = rounded_fraction(
                context, state.precision, exact_float(relation_value.length),
                "binary64_length_exact_conversion")
            coefficient = rounded_mul(context, state.precision, c_kick, conjugate,
                                      "kick_scalar_multiplication", counter)
            alpha = rounded_div(context, state.precision, coefficient, length,
                                "kick_length_division", counter)
            impulse = [
                rounded_mul(context, state.precision, alpha, component,
                            "impulse_component_multiplication", counter)
                for component in relation_value.offset
            ]
            impulse_exact = [exact_dyadic(value) for value in impulse]
            require(max(abs(value) for value in impulse_exact) < RAW_J_LIMIT,
                    "raw_impulse_evidence_bound_exceeded")
            relation = relation_value.relation
            first = lookup[relation.first_id]
            second = lookup[relation.second_id]
            first_before = list(first.p)
            second_before = list(second.p)
            first.p = [
                rounded_add(context, state.precision, first.p[axis], impulse[axis],
                            "endpoint_momentum_accumulation", counter)
                for axis in range(3)
            ]
            second.p = [
                rounded_sub(context, state.precision, second.p[axis], impulse[axis],
                            "endpoint_momentum_accumulation", counter)
                for axis in range(3)
            ]
            if force_rows is not None or observer_events is not None:
                first_delta = _actual_packet_delta(first_before, first.p)
                second_delta = _actual_packet_delta(second_before, second.p)
                offset = [exact_dyadic(value) for value in relation_value.offset]
                first_x = [exact_dyadic(value) for value in frozen_lookup[relation.first_id].x]
                second_x = [exact_dyadic(value) for value in frozen_lookup[relation.second_id].x]
                pair_momentum = vector_add(first_delta, second_delta)
                stored_offset = vector_sub(second_x, first_x)
                stored_centrality = cross(stored_offset, impulse_exact)
                first_centrality = cross(stored_offset, first_delta)
                second_centrality = cross(
                    stored_offset, [-component for component in second_delta])
                relation_angular = vector_add(cross(first_x, first_delta),
                                              cross(second_x, second_delta))
                row: dict[str, object] = {
                    "trajectory_id": trajectory,
                    "precision": state.precision,
                    "level": level,
                    "step": step,
                    "stage": stage,
                    "relation_index": relation.index,
                    "first_id": relation.first_id,
                    "second_id": relation.second_id,
                    "length_bits": float_bits(relation_value.length),
                    "conjugate_bits": float_bits(relation_value.conjugate),
                    "causal_offset_raw_hash": vector_hash(offset),
                    "exact_stored_offset_raw_hash": vector_hash(stored_offset),
                    "ideal_impulse_raw_hash": vector_hash(impulse_exact),
                    "first_actual_impulse_raw_hash": vector_hash(first_delta),
                    "second_actual_impulse_raw_hash": vector_hash(second_delta),
                }
                full_components = not trajectory.startswith("long:")
                _add_vector_fields(row, "pair_momentum_residual", pair_momentum, PQ,
                                   full_components, True)
                _add_vector_fields(row, "stored_impulse_centrality_residual",
                                   stored_centrality, LQ * PQ, full_components, True)
                _add_vector_fields(row, "first_actual_centrality_residual",
                                   first_centrality, LQ * PQ, full_components, True)
                _add_vector_fields(row, "second_actual_centrality_residual",
                                   second_centrality, LQ * PQ, full_components, True)
                _add_vector_fields(row, "relation_angular_residual", relation_angular,
                                   LQ * PQ, full_components, True)
                if force_rows is not None:
                    force_rows.append(row)
                if observer_events is not None:
                    observer_events.append(observer_event_digest("force_audit", row))
    validate_state(result)
    return result


def drift(
    model: exact_lab.Model,
    state: State,
    interval_raw: int,
    profile: Profile,
    counter: OperationCounter | None = None,
    domain_failures: list[dict[str, object]] | None = None,
) -> State:
    result = state.clone()
    with profile.activate() as context:
        initial_offsets = [
            exact_stored_relation_offset(state, relation) for relation in model.relations
        ]
        for packet in result.packets:
            c_drift = rounded_fraction(
                context, state.precision, Fraction(interval_raw, packet.mass_raw),
                "drift_constant_conversion", counter)
            displacement = [
                rounded_mul(context, state.precision, c_drift, packet.p[axis],
                            "drift_displacement_multiplication", counter)
                for axis in range(3)
            ]
            packet.x = [
                rounded_add(context, state.precision, packet.x[axis], displacement[axis],
                            "drift_position_accumulation", counter)
                for axis in range(3)
            ]
        for relation, initial in zip(model.relations, initial_offsets):
            final = exact_stored_relation_offset(result, relation)
            certificate = bounded_chord_certificate(
                initial, final, exact_reference_offset(model, relation), state.precision)
            if not certificate.safe:
                if domain_failures is not None:
                    domain_failures.append({
                        "offending_relation_index": relation.index,
                        "chord_minimum_case": certificate.minimum_case,
                        "comparison_lhs_num": certificate.lhs.numerator,
                        "comparison_lhs_den": certificate.lhs.denominator,
                        "comparison_rhs_num": certificate.rhs.numerator,
                        "comparison_rhs_den": certificate.rhs.denominator,
                        "domain_scratch_observed_bits": certificate.scratch_observed_bits,
                        "domain_scratch_limit_bits": certificate.scratch_limit_bits,
                    })
                raise LabError("chord_domain_failure")
    validate_state(result)
    return result


def one_step(
    model: exact_lab.Model,
    state: State,
    interval_raw: int,
    path: str,
    profile: Profile,
    trajectory: str = "algorithm",
    level: int = 0,
    step: int = 1,
    invariant_rows: list[dict[str, object]] | None = None,
    force_rows: list[dict[str, object]] | None = None,
    initial_invariants: tuple[list[Fraction], list[Fraction]] | None = None,
    counter: OperationCounter | None = None,
    failure_details: list[dict[str, object]] | None = None,
    observer_events: list[str] | None = None,
) -> tuple[str, State]:
    prior = state.clone()
    local_invariants: list[dict[str, object]] = []
    local_forces: list[dict[str, object]] = []
    local_counter = OperationCounter()
    local_failures: list[dict[str, object]] = []
    local_events: list[str] = []
    event_target = local_events if observer_events is not None else None
    baseline = initial_invariants if initial_invariants is not None else exact_state_invariants(prior)
    try:
        if path == KDK:
            require(interval_raw % 2 == 0, "bounded KDK half-step is not integral time")
            work = kick(model, prior, interval_raw // 2, profile, trajectory, level, step,
                        "first_kick", local_forces if force_rows is not None else None,
                        local_counter, event_target)
            if invariant_rows is not None or event_target is not None:
                record_invariant(local_invariants, trajectory, state.precision, level, step,
                                 "first_kick", work, baseline, event_target)
            work = drift(model, work, interval_raw, profile, local_counter, local_failures)
            if invariant_rows is not None or event_target is not None:
                record_invariant(local_invariants, trajectory, state.precision, level, step,
                                 "drift", work, baseline, event_target)
            work = kick(model, work, interval_raw // 2, profile, trajectory, level, step,
                        "second_kick", local_forces if force_rows is not None else None,
                        local_counter, event_target)
            if invariant_rows is not None or event_target is not None:
                record_invariant(local_invariants, trajectory, state.precision, level, step,
                                 "second_kick", work, baseline, event_target)
        elif path == CONTROL:
            work = kick(model, prior, interval_raw, profile, trajectory, level, step,
                        "full_kick", local_forces if force_rows is not None else None,
                        local_counter, event_target)
            if invariant_rows is not None or event_target is not None:
                record_invariant(local_invariants, trajectory, state.precision, level, step,
                                 "full_kick", work, baseline, event_target)
            work = drift(model, work, interval_raw, profile, local_counter, local_failures)
            if invariant_rows is not None or event_target is not None:
                record_invariant(local_invariants, trajectory, state.precision, level, step,
                                 "drift", work, baseline, event_target)
        else:
            raise LabError("unknown bounded integrator path")
        work.time_raw += interval_raw
        validate_state(work)
        if invariant_rows is not None or event_target is not None:
            record_invariant(local_invariants, trajectory, state.precision, level, step,
                             "committed", work, baseline, event_target)
        if invariant_rows is not None:
            invariant_rows.extend(local_invariants)
        if force_rows is not None:
            force_rows.extend(local_forces)
        if counter is not None:
            counter.merge(local_counter)
        if observer_events is not None:
            observer_events.extend(local_events)
        return "accepted", work
    except LabError as error:
        status = str(error).split(":", 1)[0]
        fail_closed = status in {
            "force_domain_failure", "chord_domain_failure", "domain_scratch_bound_exceeded",
            "phase_range_failure",
        }
        if fail_closed:
            require(encode_state(prior) == encode_state(state),
                    "atomic rejection mutated prior state")
            if failure_details is not None:
                failure_details.extend(local_failures)
            return status, prior
        raise


def expected_operation_categories(
    model: exact_lab.Model, state: State, path: str
) -> dict[str, int]:
    relations = len(model.relations)
    packets = len(state.packets)
    if path == KDK:
        kicks = 2
    elif path == CONTROL:
        kicks = 1
    else:
        raise LabError("unknown path for operation count")
    return {
        "drift_constant_conversion": packets,
        "drift_displacement_multiplication": 3 * packets,
        "drift_position_accumulation": 3 * packets,
        "endpoint_momentum_accumulation": kicks * 6 * relations,
        "impulse_component_multiplication": kicks * 3 * relations,
        "kick_constant_conversion": kicks,
        "kick_length_division": kicks * relations,
        "kick_scalar_multiplication": kicks * relations,
        "relative_subtraction": kicks * 3 * relations,
        "relative_unit_multiplication": kicks * 3 * relations,
    }


def expected_operations(model: exact_lab.Model, state: State, path: str) -> int:
    return sum(expected_operation_categories(model, state, path).values())


def operation_count_row(
    trajectory: str, precision: int, level: int, path: str,
    model: exact_lab.Model, result: RunResult,
) -> dict[str, object]:
    per_step = expected_operation_categories(model, result.initial, path)
    expected = {
        category: count * result.completed_steps
        for category, count in per_step.items()
        if count
    }
    observed = {category: count for category, count in result.operations.categories.items() if count}
    categories_passed = observed == expected
    total_expected = sum(expected.values())
    total_passed = result.operations.total == total_expected
    return {
        "trajectory_id": trajectory,
        "precision": precision,
        "level": level,
        "path": path,
        "packet_count": len(result.initial.packets),
        "relation_count": len(model.relations),
        "completed_steps": result.completed_steps,
        "per_step_expected": sum(per_step.values()),
        "expected_categories": canonical_operation_categories(expected),
        "observed_categories": canonical_operation_categories(observed),
        "inexact_categories": canonical_operation_categories(result.operations.inexact_categories),
        "inexact_total": result.operations.inexact_total,
        "exact_total": result.operations.total - result.operations.inexact_total,
        "rounding_audit_records": result.operations.total,
        "rounding_audit_sha256": result.operations.audit_sha256(),
        "categories_passed": str(categories_passed).lower(),
        "total_expected": total_expected,
        "total_observed": result.operations.total,
        "passed": str(total_passed and categories_passed).lower(),
    }


def _size_row(trajectory: str, level: int, step: int, label: str,
              state: State, profile: Profile) -> dict[str, object]:
    return {
        "trajectory_id": trajectory,
        "precision": state.precision,
        "level": level,
        "step": step,
        "label": label,
        "packet_count": len(state.packets),
        "component_bytes": profile.component_bytes,
        "phase_bytes_per_packet": profile.phase_bytes_per_packet,
        "complete_packet_bytes": profile.packet_bytes,
        "state_bytes": len(encode_state(state)),
        "state_hash": state_hash(state),
        "causal_cache_bytes": 0,
        "causal_history_bytes": 0,
    }


def run_trajectory(
    model: exact_lab.Model,
    initial: State,
    interval_raw: int,
    steps: int,
    path: str,
    profile: Profile,
    trajectory: str,
    level: int,
    invariant_rows: list[dict[str, object]] | None = None,
    force_rows: list[dict[str, object]] | None = None,
    size_rows: list[dict[str, object]] | None = None,
    collect_observer_events: bool = False,
    step_offset: int = 0,
    initial_invariants: tuple[list[Fraction], list[Fraction]] | None = None,
) -> RunResult:
    state = initial.clone()
    baseline = (initial_invariants if initial_invariants is not None
                else exact_state_invariants(state))
    energies = [observed_energy(model, state, profile)]
    samples = [state.clone()]
    events: list[list[str]] = []
    operations = OperationCounter()
    if invariant_rows is not None:
        record_invariant(invariant_rows, trajectory, state.precision, level, 0,
                         "initial", state, baseline)
    if size_rows is not None:
        size_rows.append(_size_row(trajectory, level, 0, "initial", state, profile))
    completed = 0
    status = "accepted"
    for local_step in range(1, steps + 1):
        step = step_offset + local_step
        step_events: list[str] = []
        status, candidate = one_step(
            model, state, interval_raw, path, profile, trajectory, level, step,
            invariant_rows, force_rows, baseline, operations,
            observer_events=step_events if collect_observer_events else None)
        if status != "accepted":
            break
        state = candidate
        completed = local_step
        samples.append(state.clone())
        energy = observed_energy(model, state, profile)
        energies.append(energy)
        if collect_observer_events:
            step_events.append(observer_event_digest(
                "energy", energy_observer_row(
                    trajectory, state.precision, level, step, state, energy)))
            events.append(step_events)
        if size_rows is not None and local_step in {1, 400, steps}:
            label = ("step_1" if local_step == 1
                     else ("step_400" if local_step == 400 else "final"))
            size_rows.append(_size_row(trajectory, level, step, label, state, profile))
    expected = expected_operations(model, initial, path) * completed
    require(operations.total == expected,
            f"causal operation count differs: {operations.total} != {expected}")
    expected_categories = {
        category: count * completed
        for category, count in expected_operation_categories(model, initial, path).items()
        if count * completed
    }
    observed_categories = {
        category: count for category, count in operations.categories.items() if count
    }
    require(observed_categories == expected_categories,
            "causal operation category breakdown differs")
    return RunResult(status, initial.clone(), state, steps, completed, samples,
                     energies, events, operations)


def _parent_value(row: dict[str, str], name: str) -> Fraction:
    return Fraction(int(row[f"{name}_coarse"])) + Fraction(
        int(row[f"{name}_num"]), int(row[f"{name}_den"])
    )


def load_exact_states(parent_raw: Path) -> tuple[dict[str, str], dict[str, exact_lab.State]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in read_rows(parent_raw / "initial_states.csv"):
        grouped.setdefault(row["scenario_id"], []).append(row)
    models: dict[str, str] = {}
    states: dict[str, exact_lab.State] = {}
    for scenario, rows in grouped.items():
        rows.sort(key=lambda row: int(row["packet_id"]))
        models[scenario] = rows[0]["model_id"]
        states[scenario] = exact_lab.State(0, [exact_lab.Packet(
            int(row["packet_id"]), int(row["mass_raw"]),
            [_parent_value(row, f"x{axis}") for axis in "xyz"],
            [_parent_value(row, f"p{axis}") for axis in "xyz"],
        ) for row in rows])
    required = set(SCENARIOS) | {
        "k4_translated", "k4_boosted", "k4_rotated", "domain_crossing"
    }
    require(required.issubset(states), "sealed parent scenario inventory differs")
    return models, states


def bounded_state(source: exact_lab.State, profile: Profile) -> State:
    packets: list[Packet] = []
    with profile.activate() as context:
        for packet in source.packets:
            packets.append(Packet(
                packet.identifier,
                packet.mass_raw,
                [rounded_fraction(context, profile.precision, value,
                                  "initial_state_conversion") for value in packet.x],
                [rounded_fraction(context, profile.precision, value,
                                  "initial_state_conversion") for value in packet.p],
            ))
    result = State(profile.precision, source.time_raw, packets)
    validate_state(result)
    for bounded_packet, exact_packet in zip(
        canonical_packets(result), sorted(source.packets, key=lambda row: row.identifier)
    ):
        require(all(
            exact_dyadic(candidate) == expected
            for candidate, expected in zip(
                bounded_packet.x + bounded_packet.p, exact_packet.x + exact_packet.p)
        ), "sealed initial state is not exactly representable at registered precision")
    return result


def run_exact_shadow(model: exact_lab.Model, initial: exact_lab.State,
                     interval_raw: int, steps: int, path: str) -> list[exact_lab.State]:
    exact_path = exact_lab.KDK if path == KDK else exact_lab.CONTROL
    state = initial.clone()
    baseline = exact_lab.exact_invariants(state)
    samples = [state.clone()]
    for step in range(1, steps + 1):
        status, state = exact_lab.one_step(
            model, state, interval_raw, exact_path, "bounded-positive-control", 0,
            step, None, None, baseline)
        require(status == "accepted", "exact-rational positive control trajectory failed")
        samples.append(state.clone())
    return samples


def exact_shadow_complexity(state: exact_lab.State) -> tuple[int, Fraction, int, bool]:
    """Measure the sealed exact-rational residual-state ceilings exactly."""
    bit_lengths: list[int] = []
    for packet in sorted(state.packets, key=lambda row: row.identifier):
        for value in (*packet.x, *packet.p):
            _coarse, residual = exact_lab.split_raw(value)
            bit_lengths.extend((
                abs(int(residual.numerator)).bit_length(),
                int(residual.denominator).bit_length(),
            ))
    maximum = max(bit_lengths, default=0)
    ordered = sorted(bit_lengths)
    if not ordered:
        median = Fraction()
    elif len(ordered) % 2:
        median = Fraction(ordered[len(ordered) // 2])
    else:
        midpoint = len(ordered) // 2
        median = Fraction(ordered[midpoint - 1] + ordered[midpoint], 2)
    checkpoint_bytes = len(exact_lab.encode_state(state))
    exceeded = (
        maximum > EXACT_MAX_COMPONENT_BITS
        or median > EXACT_MEDIAN_COMPONENT_BITS
        or checkpoint_bytes > EXACT_MAX_CHECKPOINT_BYTES
    )
    return maximum, median, checkpoint_bytes, exceeded


def run_exact_shadow_with_ceiling(
    model: exact_lab.Model, initial: exact_lab.State,
    interval_raw: int, steps: int, path: str,
) -> ExactShadowResult:
    """Advance through and include the first exact-state complexity crossing."""
    exact_path = exact_lab.KDK if path == KDK else exact_lab.CONTROL
    state = initial.clone()
    baseline = exact_lab.exact_invariants(state)
    samples = [state.clone()]
    maximum, maximum_median, maximum_bytes, exceeded = exact_shadow_complexity(state)
    require(not exceeded, "exact-rational initial state exceeds frozen complexity ceiling")
    first_crossing: int | None = None
    crossing_values: tuple[int, Fraction, int] | None = None
    completed = 0
    for step in range(1, steps + 1):
        status, state = exact_lab.one_step(
            model, state, interval_raw, exact_path, "bounded-positive-control", 0,
            step, None, None, baseline)
        require(status == "accepted", "exact-rational positive control trajectory failed")
        completed = step
        samples.append(state.clone())
        component_bits, median_bits, checkpoint_bytes, exceeded = exact_shadow_complexity(state)
        maximum = max(maximum, component_bits)
        maximum_median = max(maximum_median, median_bits)
        maximum_bytes = max(maximum_bytes, checkpoint_bytes)
        if exceeded:
            first_crossing = step
            crossing_values = (component_bits, median_bits, checkpoint_bytes)
            break
    return ExactShadowResult(
        samples=samples,
        status="complexity_budget_exceeded" if first_crossing is not None else "accepted",
        requested_steps=steps,
        completed_steps=completed,
        first_crossing_step=first_crossing,
        last_within_ceiling_step=(first_crossing - 1 if first_crossing is not None else completed),
        maximum_component_bits=maximum,
        maximum_state_median_bits=maximum_median,
        maximum_checkpoint_bytes=maximum_bytes,
        crossing_component_bits=(crossing_values[0] if crossing_values else None),
        crossing_state_median_bits=(crossing_values[1] if crossing_values else None),
        crossing_checkpoint_bytes=(crossing_values[2] if crossing_values else None),
    )


def exact_shadow_receipt(
    scenario: str, level: int, dt_raw: int, result: ExactShadowResult,
) -> dict[str, object]:
    crossing = result.first_crossing_step
    row: dict[str, object] = {
        "scenario_id": scenario,
        "scope": "long_exact_comparator",
        "path": KDK,
        "level": level,
        "dt_raw": dt_raw,
        "requested_steps": result.requested_steps,
        "completed_steps": result.completed_steps,
        "comparison_samples": len(result.samples),
        "status": result.status,
        "first_crossing_step": "" if crossing is None else crossing,
        "last_within_ceiling_step": result.last_within_ceiling_step,
        "last_comparator_sample": result.completed_steps,
        "first_comparator_free_sample": result.completed_steps + 1,
        "last_comparator_time_raw": result.samples[-1].time_raw,
        "last_comparator_state_hash": exact_lab.state_hash(result.samples[-1]),
        "maximum_component_bits": result.maximum_component_bits,
        "maximum_state_median_bits_num": result.maximum_state_median_bits.numerator,
        "maximum_state_median_bits_den": result.maximum_state_median_bits.denominator,
        "maximum_checkpoint_bytes": result.maximum_checkpoint_bytes,
        "crossing_component_bits": (
            "" if result.crossing_component_bits is None else result.crossing_component_bits),
        "crossing_state_median_bits_num": (
            "" if result.crossing_state_median_bits is None
            else result.crossing_state_median_bits.numerator),
        "crossing_state_median_bits_den": (
            "" if result.crossing_state_median_bits is None
            else result.crossing_state_median_bits.denominator),
        "crossing_checkpoint_bytes": (
            "" if result.crossing_checkpoint_bytes is None
            else result.crossing_checkpoint_bytes),
        "maximum_component_bits_limit": EXACT_MAX_COMPONENT_BITS,
        "median_component_bits_limit": EXACT_MEDIAN_COMPONENT_BITS,
        "maximum_checkpoint_bytes_limit": EXACT_MAX_CHECKPOINT_BYTES,
        "crossing_state_included": str(crossing is not None).lower(),
    }
    return row


def exact_observed_energy(model: exact_lab.Model, state: exact_lab.State) -> Fraction:
    _relations, potential = exact_lab.force_and_energy(model, state)
    return exact_lab.kinetic_energy_exact(state) + exact_float(potential)


def max_state_error(candidate: State, control: exact_lab.State,
                    momentum: bool = False) -> Fraction:
    first = canonical_packets(candidate)
    second = sorted(control.packets, key=lambda row: row.identifier)
    require([row.identifier for row in first] == [row.identifier for row in second],
            "candidate/control packet IDs differ")
    maximum = Fraction()
    for bounded_packet, exact_packet in zip(first, second):
        bounded_vector = bounded_packet.p if momentum else bounded_packet.x
        exact_vector = exact_packet.p if momentum else exact_packet.x
        for bounded_value, exact_value in zip(bounded_vector, exact_vector):
            maximum = max(maximum, abs(exact_dyadic(bounded_value) - exact_value))
    return maximum


def relative_state_error(first: State, second: State, momentum: bool = False) -> Fraction:
    first_packets = canonical_packets(first)
    second_packets = canonical_packets(second)
    require([row.identifier for row in first_packets] == [row.identifier for row in second_packets],
            "covariance packet IDs differ")
    maximum = Fraction()
    for index in range(1, len(first_packets)):
        first_vector = first_packets[index].p if momentum else first_packets[index].x
        first_origin = first_packets[0].p if momentum else first_packets[0].x
        second_vector = second_packets[index].p if momentum else second_packets[index].x
        second_origin = second_packets[0].p if momentum else second_packets[0].x
        for axis in range(3):
            first_relative = exact_dyadic(first_vector[axis]) - exact_dyadic(first_origin[axis])
            second_relative = exact_dyadic(second_vector[axis]) - exact_dyadic(second_origin[axis])
            maximum = max(maximum, abs(first_relative - second_relative))
    return maximum


def inverse_rotate_state(state: State) -> State:
    result = state.clone()
    profile = profile_for(state.precision)
    with profile.activate() as context:
        for packet in result.packets:
            old_x = list(packet.x)
            old_p = list(packet.p)
            packet.x = [old_x[1], _checked(context, state.precision, "exact_negation",
                                           lambda value=old_x[0]: -value), old_x[2]]
            packet.p = [old_p[1], _checked(context, state.precision, "exact_negation",
                                           lambda value=old_p[0]: -value), old_p[2]]
    return result


def component_row(row: dict[str, object], name: str, value: mpfr, precision: int) -> None:
    sign, exponent, significand = component_parts(value, precision)
    exact = exact_dyadic(value)
    row[f"{name}_sign"] = sign
    row[f"{name}_E"] = exponent
    row[f"{name}_significand_hex"] = f"{significand:0{precision // 4}x}"
    row[f"{name}_wire_hex"] = encode_component(value, precision).hex()
    row[f"{name}_exact_num"] = exact.numerator
    row[f"{name}_exact_den"] = exact.denominator


def full_state_row(prefix: dict[str, object], packet: Packet, precision: int) -> dict[str, object]:
    row = dict(prefix)
    row.update({"packet_id": packet.identifier, "mass_raw": packet.mass_raw})
    for name, vector in (("x", packet.x), ("p", packet.p)):
        for axis, value in zip("xyz", vector):
            component_row(row, f"{name}{axis}", value, precision)
    return row


STATE_BASE_FIELDS = (
    "precision", "scenario_id", "model_id", "scope", "path", "level", "dt_raw",
    "steps", "status", "completed_steps", "time_raw", "state_hash", "packet_id", "mass_raw",
)
COMPONENT_FIELD_SUFFIXES = (
    "sign", "E", "significand_hex", "wire_hex", "exact_num", "exact_den",
)
STATE_FIELDS = STATE_BASE_FIELDS + tuple(
    f"{name}_{suffix}"
    for name in ("xx", "xy", "xz", "px", "py", "pz")
    for suffix in COMPONENT_FIELD_SUFFIXES
)


VECTOR_PREFIXES_INVARIANT = ("momentum", "angular", "delta_momentum", "delta_angular")
VECTOR_PREFIXES_FORCE = (
    "pair_momentum_residual", "stored_impulse_centrality_residual",
    "first_actual_centrality_residual", "second_actual_centrality_residual",
    "relation_angular_residual",
)


def vector_fields(prefixes: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        field_name
        for prefix in prefixes
        for field_name in (
            f"{prefix}_hash", f"{prefix}_raw_max_dyadic",
            *(f"{prefix}_raw_{axis}_dyadic" for axis in "xyz"),
            f"{prefix}_max_num", f"{prefix}_max_den",
            *(f"{prefix}_{axis}_{part}" for axis in "xyz" for part in ("num", "den")),
        )
    )


INVARIANT_FIELDS = (
    "trajectory_id", "precision", "level", "step", "stage", "state_hash",
    *vector_fields(VECTOR_PREFIXES_INVARIANT),
)
FORCE_FIELDS = (
    "trajectory_id", "precision", "level", "step", "stage", "relation_index",
    "first_id", "second_id", "length_bits", "conjugate_bits",
    "causal_offset_raw_hash", "exact_stored_offset_raw_hash", "ideal_impulse_raw_hash",
    "first_actual_impulse_raw_hash", "second_actual_impulse_raw_hash",
    *vector_fields(VECTOR_PREFIXES_FORCE),
)
ENERGY_EVENT_FIELDS = (
    "trajectory_id", "precision", "level", "step", "state_hash",
    "potential_binary64_bits", "kinetic_num", "kinetic_den", "kinetic_hash",
    "potential_num", "potential_den", "potential_hash",
    "mechanical_num", "mechanical_den", "mechanical_hash",
)


def _observer_frame(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<Q", len(encoded)) + encoded


def observer_event_bytes(kind: str, row: dict[str, object]) -> bytes:
    """Return one canonical, invocation-identifying observer-event record."""
    if kind == "invariant":
        fields = INVARIANT_FIELDS
    elif kind == "force_audit":
        fields = FORCE_FIELDS
    elif kind == "energy":
        fields = ENERGY_EVENT_FIELDS
    else:
        raise LabError("unknown observer event kind")
    result = bytearray(OBSERVER_EVENT_MAGIC)
    result.extend(_observer_frame(kind))
    result.extend(struct.pack("<Q", len(fields)))
    for field_name in fields:
        result.extend(_observer_frame(field_name))
        result.extend(_observer_frame(str(row.get(field_name, ""))))
    return bytes(result)


def observer_event_digest(kind: str, row: dict[str, object]) -> str:
    return hashlib.sha256(observer_event_bytes(kind, row)).hexdigest()


def energy_observer_row(
    trajectory: str, precision: int, level: int, step: int, state: State,
    value: tuple[Fraction, Fraction, Fraction, int],
) -> dict[str, object]:
    kinetic, potential, mechanical, potential_bits = value
    row: dict[str, object] = {
        "trajectory_id": trajectory,
        "precision": precision,
        "level": level,
        "step": step,
        "state_hash": state_hash(state),
        "potential_binary64_bits": potential_bits,
    }
    for name, observed in (
        ("kinetic", kinetic), ("potential", potential), ("mechanical", mechanical)
    ):
        _ratio_columns(row, name, observed)
        row[f"{name}_hash"] = fraction_hash(observed)
    return row


def observer_event_count(events: Iterable[Iterable[str]]) -> int:
    return sum(len(step_events) for step_events in events)


def observer_stream_sha256(events: Iterable[Iterable[str]]) -> str:
    step_groups = [list(step_events) for step_events in events]
    digest = hashlib.sha256()
    digest.update(OBSERVER_STREAM_MAGIC)
    digest.update(struct.pack("<Q", len(step_groups)))
    digest.update(struct.pack("<Q", observer_event_count(step_groups)))
    for step_events in step_groups:
        digest.update(struct.pack("<Q", len(step_events)))
        for event in step_events:
            require(len(event) == 64, "observer event digest width differs")
            try:
                digest.update(bytes.fromhex(event))
            except ValueError as error:
                raise LabError("observer event digest is not hexadecimal") from error
    return digest.hexdigest()


def state_rows(prefix: dict[str, object], state: State) -> Iterator[dict[str, object]]:
    for packet in canonical_packets(state):
        yield full_state_row(prefix, packet, state.precision)


def verify_parent(parent_raw: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    fingerprint: list[dict[str, object]] = []
    for filename, expected in sorted(PARENT_HASHES.items()):
        path = parent_raw / filename
        require(path.is_file(), f"stop_inconclusive_or_wrong_parent:{filename}:missing")
        actual = sha256_file(path)
        fingerprint.append({"file": filename, "sha256": actual,
                            "expected_sha256": expected,
                            "passed": str(actual == expected).lower()})
        require(actual == expected, f"stop_inconclusive_or_wrong_parent:{filename}:hash")

    controls: list[dict[str, object]] = []
    checks = {
        "exact_momentum_and_angular": all(
            row["momentum_equal_initial"] == "true" and row["angular_equal_initial"] == "true"
            for row in read_rows(parent_raw / "invariants.csv")
        ),
        "exact_relation_centrality": all(
            row["central_cross_zero"] == "true"
            for row in read_rows(parent_raw / "force_audit.csv")
        ),
        "exact_signed_time_recovery": all(
            row["complete_state_identical"] == "true"
            for row in read_rows(parent_raw / "reversibility.csv")
        ),
        "exact_registered_covariance": all(
            int(row["position_discrepancy_num"]) == 0 and
            int(row["momentum_discrepancy_num"]) == 0
            for row in read_rows(parent_raw / "covariance.csv")
        ),
        "atomic_domain_rejection": all(
            row["status"] == "chord_domain_failure" and
            row["time_unchanged"] == "true" and row["state_unchanged"] == "true"
            for row in read_rows(parent_raw / "domain.csv")
        ),
    }
    long_statuses = {
        int(row["level"]): row["status"]
        for row in read_rows(parent_raw / "long_energy.csv")
    }
    checks["complexity_crossing_fingerprint"] = (
        long_statuses.get(0) == "accepted" and
        all(long_statuses.get(level) == "complexity_budget_exceeded" for level in range(1, 5))
    )
    for name, passed in checks.items():
        controls.append({"check": name, "passed": str(passed).lower(), "detail": "sealed_raw"})
        require(passed, f"stop_inconclusive_or_wrong_parent:{name}")
    return fingerprint, controls


def endpoint_parent_hashes(parent_raw: Path) -> dict[tuple[str, str, int], str]:
    result: dict[tuple[str, str, int], str] = {}
    for row in read_rows(parent_raw / "endpoints.csv"):
        result[(row["scenario_id"], row["path"], int(row["level"]))] = row["state_hash"]
    return result


def parent_long_prefix_steps(parent_raw: Path) -> dict[int, int]:
    counts: dict[int, int] = {}
    for row in read_rows(parent_raw / "long_energy.csv"):
        level = int(row["level"])
        counts[level] = max(counts.get(level, 0), int(row["sample"]))
    return counts


def git_identity(source: Path) -> tuple[str, str, bool]:
    def run(*arguments: str) -> str:
        return subprocess.check_output(["git", *arguments], cwd=source, text=True).strip()
    return (run("rev-parse", "HEAD"), run("rev-parse", "--abbrev-ref", "HEAD"),
            bool(run("status", "--porcelain")))


def _ratio_columns(row: dict[str, object], prefix: str, value: Fraction) -> None:
    row[f"{prefix}_num"] = value.numerator
    row[f"{prefix}_den"] = value.denominator


def append_representation_rows(
    rows: list[dict[str, object]], scenario: str, scope: str, path: str,
    precision: int, level: int, dt_raw: int,
    candidate: list[State], control: list[exact_lab.State], model: exact_lab.Model,
) -> None:
    for sample, (bounded, exact) in enumerate(zip(candidate, control)):
        x_raw = max_state_error(bounded, exact)
        p_raw = max_state_error(bounded, exact, True)
        bounded_energy = observed_energy(model, bounded, profile_for(precision))[2]
        control_energy = exact_observed_energy(model, exact)
        row: dict[str, object] = {
            "scenario_id": scenario, "scope": scope, "path": path,
            "precision": precision, "level": level, "dt_raw": dt_raw,
            "sample": sample, "candidate_state_hash": state_hash(bounded),
            "control_state_hash": exact_lab.state_hash(exact),
        }
        _ratio_columns(row, "position_raw_error", x_raw)
        _ratio_columns(row, "position_physical_error", x_raw * LQ)
        _ratio_columns(row, "momentum_raw_error", p_raw)
        _ratio_columns(row, "momentum_physical_error", p_raw * PQ)
        _ratio_columns(row, "energy_error", bounded_energy - control_energy)
        rows.append(row)


def append_energy_rows(rows: list[dict[str, object]], scenario: str, scope: str,
                       path: str, precision: int, level: int, dt_raw: int,
                       values: list[tuple[Fraction, Fraction, Fraction, int]]) -> None:
    for sample, (kinetic, potential, total, potential_bits) in enumerate(values):
        row: dict[str, object] = {
            "scenario_id": scenario, "scope": scope, "path": path,
            "precision": precision, "level": level, "dt_raw": dt_raw, "sample": sample,
            "potential_binary64_bits": potential_bits,
        }
        for name, value in (("kinetic", kinetic), ("potential", potential), ("mechanical", total)):
            _ratio_columns(row, name, value)
            row[f"{name}_hash"] = fraction_hash(value)
        rows.append(row)


def append_covariance_rows(rows: list[dict[str, object]], kind: str, scope: str,
                           precision: int, level: int, dt_raw: int,
                           baseline: list[State], transformed: list[State]) -> None:
    for sample, (first, second) in enumerate(zip(baseline, transformed)):
        x_raw = relative_state_error(first, second)
        p_raw = relative_state_error(first, second, True)
        row: dict[str, object] = {
            "kind": kind, "scope": scope, "precision": precision, "level": level,
            "dt_raw": dt_raw, "sample": sample,
            "baseline_hash": state_hash(first), "transformed_hash": state_hash(second),
            "bit_identical": str(encode_state(first) == encode_state(second)).lower(),
        }
        _ratio_columns(row, "relative_position_raw", x_raw)
        _ratio_columns(row, "relative_position_physical", x_raw * LQ)
        _ratio_columns(row, "relative_momentum_raw", p_raw)
        _ratio_columns(row, "relative_momentum_physical", p_raw * PQ)
        rows.append(row)


def _state_prefix(scenario: str, model_id: str, scope: str, path: str,
                  level: int, dt_raw: int, steps: int, result: RunResult) -> dict[str, object]:
    return {
        "precision": result.final.precision, "scenario_id": scenario, "model_id": model_id,
        "scope": scope, "path": path, "level": level, "dt_raw": dt_raw, "steps": steps,
        "status": result.status, "completed_steps": result.completed_steps,
        "time_raw": result.final.time_raw, "state_hash": state_hash(result.final),
    }


def materialize(parent_raw: Path, output: Path, source: Path) -> None:
    validate_causal_state_shape()
    fingerprint_rows, positive_rows = verify_parent(parent_raw)
    models = exact_lab.load_models(parent_raw)
    scenario_models, exact_states = load_exact_states(parent_raw)
    parent_endpoints = endpoint_parent_hashes(parent_raw)
    long_prefix = parent_long_prefix_steps(parent_raw)
    source_sha, source_branch, source_dirty = git_identity(source)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    initial_rows: list[dict[str, object]] = []
    endpoint_rows: list[dict[str, object]] = []
    long_endpoint_rows: list[dict[str, object]] = []
    checkpoint_state_rows: list[dict[str, object]] = []
    recovery_state_rows: list[dict[str, object]] = []
    representation_rows: list[dict[str, object]] = []
    energy_rows: list[dict[str, object]] = []
    long_energy_rows: list[dict[str, object]] = []
    invariant_rows = CsvSink(output / "invariants.csv", INVARIANT_FIELDS)
    force_rows = CsvSink(output / "force_audit.csv", FORCE_FIELDS)
    reversibility_rows: list[dict[str, object]] = []
    covariance_rows: list[dict[str, object]] = []
    checkpoint_rows: list[dict[str, object]] = []
    domain_rows: list[dict[str, object]] = []
    size_rows: list[dict[str, object]] = []
    operation_rows: list[dict[str, object]] = []
    rational_comparator_rows: list[dict[str, object]] = []

    profiles = {precision: profile_for(precision) for precision in PRECISIONS}
    for precision, profile in profiles.items():
        for scenario in sorted(exact_states):
            initial = bounded_state(exact_states[scenario], profile)
            prefix = {
                "precision": precision, "scenario_id": scenario,
                "model_id": scenario_models[scenario], "scope": "initial", "path": "initial",
                "level": 0, "dt_raw": 0, "steps": 0, "status": "initial",
                "completed_steps": 0, "time_raw": initial.time_raw,
                "state_hash": state_hash(initial),
            }
            initial_rows.extend(state_rows(prefix, initial))

    primary: dict[tuple[int, int, str, str], RunResult] = {}
    for level, (dt_raw, steps) in enumerate(zip(TIMESTEPS_RAW, STEP_COUNTS)):
        print(f"bounded phase level {level}: dt_raw={dt_raw} steps={steps}", flush=True)
        for scenario in SCENARIOS:
            model = models[scenario_models[scenario]]
            for path in (CONTROL, KDK):
                shadow = run_exact_shadow(model, exact_states[scenario], dt_raw, steps, path)
                parent_path = exact_lab.KDK if path == KDK else exact_lab.CONTROL
                expected_hash = parent_endpoints[(scenario, parent_path, level)]
                actual_hash = exact_lab.state_hash(shadow[-1])
                passed = actual_hash == expected_hash
                positive_rows.append({
                    "check": f"endpoint:{scenario}:{parent_path}:L{level}",
                    "passed": str(passed).lower(), "detail": actual_hash,
                })
                require(passed, "stop_inconclusive_or_wrong_parent:exact endpoint")
                for precision, profile in profiles.items():
                    trajectory = f"short:{scenario}:{path}:B{precision}:L{level}"
                    result = run_trajectory(
                        model, bounded_state(exact_states[scenario], profile), dt_raw, steps,
                        path, profile, trajectory, level, invariant_rows, force_rows, size_rows,
                        collect_observer_events=(scenario == "k4_internal" and path == KDK))
                    primary[(precision, level, scenario, path)] = result
                    prefix = _state_prefix(scenario, model.identifier, "short", path,
                                           level, dt_raw, steps, result)
                    endpoint_rows.extend(state_rows(prefix, result.final))
                    append_energy_rows(energy_rows, scenario, "short", path, precision,
                                       level, dt_raw, result.energies)
                    append_representation_rows(representation_rows, scenario, "short", path,
                                               precision, level, dt_raw, result.samples, shadow, model)
                    operation_rows.append(operation_count_row(
                        trajectory, precision, level, path, model, result))

        for precision, profile in profiles.items():
            for scenario in SCENARIOS:
                model = models[scenario_models[scenario]]
                forward = primary[(precision, level, scenario, KDK)]
                backward = run_trajectory(
                    model, forward.final, -dt_raw, steps, KDK, profile,
                    f"reverse:{scenario}:B{precision}:L{level}", level)
                operation_rows.append(operation_count_row(
                    f"reverse:{scenario}:B{precision}:L{level}", precision, level,
                    KDK, model, backward))
                x_error = max_state_error(backward.final, exact_states[scenario])
                p_error = max_state_error(backward.final, exact_states[scenario], True)
                row: dict[str, object] = {
                    "scenario_id": scenario, "precision": precision, "level": level,
                    "dt_raw": dt_raw, "steps": steps, "forward_status": forward.status,
                    "backward_status": backward.status,
                    "initial_hash": state_hash(bounded_state(exact_states[scenario], profile)),
                    "recovered_hash": state_hash(backward.final),
                    "complete_state_identical": str(
                        encode_state(backward.final) ==
                        encode_state(bounded_state(exact_states[scenario], profile))).lower(),
                }
                _ratio_columns(row, "position_raw_error", x_error)
                _ratio_columns(row, "position_physical_error", x_error * LQ)
                _ratio_columns(row, "momentum_raw_error", p_error)
                _ratio_columns(row, "momentum_physical_error", p_error * PQ)
                reversibility_rows.append(row)
                prefix = _state_prefix(scenario, model.identifier, "recovery", KDK,
                                       level, dt_raw, steps, backward)
                recovery_state_rows.extend(state_rows(prefix, backward.final))

            baseline = primary[(precision, level, "k4_internal", KDK)]
            for kind, scenario, transform in (
                ("translation", "k4_translated", lambda value: value),
                ("galilean_boost", "k4_boosted", lambda value: value),
                ("proper_lattice_rotation", "k4_rotated", inverse_rotate_state),
            ):
                candidate = run_trajectory(
                    models[scenario_models[scenario]], bounded_state(exact_states[scenario], profile),
                    dt_raw, steps, KDK, profile,
                    f"covariance:{kind}:B{precision}:L{level}", level)
                operation_rows.append(operation_count_row(
                    f"covariance:{kind}:B{precision}:L{level}", precision, level,
                    KDK, models[scenario_models[scenario]], candidate))
                transformed = [transform(value) for value in candidate.samples]
                append_covariance_rows(covariance_rows, kind, "short", precision, level,
                                       dt_raw, baseline.samples, transformed)
            permuted = bounded_state(exact_states["k4_internal"], profile)
            permuted.packets.reverse()
            permutation = run_trajectory(
                models["k4"], permuted, dt_raw, steps, KDK, profile,
                f"covariance:packet_permutation:B{precision}:L{level}", level)
            operation_rows.append(operation_count_row(
                f"covariance:packet_permutation:B{precision}:L{level}",
                precision, level, KDK, models["k4"], permutation))
            append_covariance_rows(covariance_rows, "packet_permutation", "short",
                                   precision, level, dt_raw, baseline.samples,
                                   permutation.samples)

            half = steps // 2
            first = run_trajectory(
                models["k4"], bounded_state(exact_states["k4_internal"], profile),
                dt_raw, half, KDK, profile,
                f"checkpoint:first:B{precision}:L{level}", level)
            operation_rows.append(operation_count_row(
                f"checkpoint:first:B{precision}:L{level}", precision, level,
                KDK, models["k4"], first))
            encoded = encode_state(first.final)
            decoded = decode_state(encoded)
            second = run_trajectory(
                models["k4"], decoded, dt_raw, half, KDK, profile,
                f"short:k4_internal:{KDK}:B{precision}:L{level}", level,
                collect_observer_events=True, step_offset=half,
                initial_invariants=exact_state_invariants(
                    bounded_state(exact_states["k4_internal"], profile)))
            operation_rows.append(operation_count_row(
                f"checkpoint:resumed:B{precision}:L{level}", precision, level,
                KDK, models["k4"], second))
            suffix = baseline.events[half:]
            suffix_count = observer_event_count(suffix)
            resumed_count = observer_event_count(second.events)
            suffix_sha256 = observer_stream_sha256(suffix)
            resumed_sha256 = observer_stream_sha256(second.events)
            event_suffix_identical = second.events == suffix
            require(event_suffix_identical and resumed_count == suffix_count
                    and resumed_sha256 == suffix_sha256,
                    "checkpoint complete observer-event suffix differs")
            checkpoint_rows.append({
                "scenario_id": "k4_internal", "precision": precision, "level": level,
                "dt_raw": dt_raw, "steps": steps, "checkpoint_step": half,
                "checkpoint_hash": hashlib.sha256(encoded).hexdigest(),
                "checkpoint_bytes": len(encoded), "decoded_hash": state_hash(decoded),
                "whole_final_hash": state_hash(baseline.final),
                "resumed_final_hash": state_hash(second.final),
                "whole_suffix_event_count": suffix_count,
                "resumed_event_count": resumed_count,
                "whole_suffix_event_sha256": suffix_sha256,
                "resumed_event_sha256": resumed_sha256,
                "event_suffix_identical": str(event_suffix_identical).lower(),
                "canonical_round_trip": str(encode_state(decoded) == encoded).lower(),
            })
            size_rows.append(_size_row(
                f"checkpoint:B{precision}:L{level}", level, half, "checkpoint", decoded, profile))
            checkpoint_prefix = {
                "precision": precision, "scenario_id": "k4_internal", "model_id": "k4",
                "scope": "checkpoint", "path": KDK, "level": level, "dt_raw": dt_raw,
                "steps": steps, "status": first.status, "completed_steps": first.completed_steps,
                "time_raw": decoded.time_raw, "state_hash": state_hash(decoded),
            }
            checkpoint_state_rows.extend(state_rows(checkpoint_prefix, decoded))

            crossing = bounded_state(exact_states["domain_crossing"], profile)
            rejected_invariant_rows: list[dict[str, object]] = []
            rejected_force_rows: list[dict[str, object]] = []
            rejected_observer_events: list[str] = []
            domain_trajectory = f"domain:B{precision}:L{level}"
            prior_energy = observed_energy(models["pair"], crossing, profile)
            prior_energy_digest = observer_event_digest(
                "energy", energy_observer_row(
                    domain_trajectory, precision, level, 0, crossing, prior_energy))
            status, rejected = one_step(
                models["pair"], crossing, 1_000_000_000, KDK, profile,
                domain_trajectory, level, 1,
                invariant_rows=rejected_invariant_rows,
                force_rows=rejected_force_rows,
                failure_details=(failure_details := []),
                observer_events=rejected_observer_events)
            require(len(failure_details) == 1, "domain failure detail count differs")
            returned_energy = observed_energy(models["pair"], rejected, profile)
            returned_energy_digest = observer_event_digest(
                "energy", energy_observer_row(
                    domain_trajectory, precision, level, 0, rejected, returned_energy))
            domain_rows.append({
                "scenario_id": "domain_crossing", "precision": precision, "level": level,
                "status": status, "prior_hash": state_hash(crossing),
                "returned_hash": state_hash(rejected),
                "time_unchanged": str(rejected.time_raw == crossing.time_raw).lower(),
                "state_unchanged": str(encode_state(rejected) == encode_state(crossing)).lower(),
                "event_rows_emitted": len(rejected_invariant_rows) + len(rejected_force_rows),
                "energy_ledger_present": "false",
                "observer_events_emitted": len(rejected_observer_events),
                "prior_energy_observation_sha256": prior_energy_digest,
                "returned_energy_observation_sha256": returned_energy_digest,
                "energy_observation_unchanged": str(
                    returned_energy == prior_energy
                    and returned_energy_digest == prior_energy_digest).lower(),
                **failure_details[0],
            })

        total_steps = steps * 16
        exact_long_result = run_exact_shadow_with_ceiling(
            models["k4"], exact_states["k4_internal"], dt_raw, total_steps, KDK)
        expected_internal_status = (
            "accepted" if long_prefix[level] == total_steps
            else "complexity_budget_exceeded")
        require(
            exact_long_result.completed_steps == long_prefix[level]
            and exact_long_result.status == expected_internal_status,
            "stop_inconclusive_or_wrong_parent: sealed exact complexity crossing differs",
        )
        exact_boost_result = run_exact_shadow_with_ceiling(
            models["k4"], exact_states["k4_boosted"], dt_raw, total_steps, KDK)
        rational_comparator_rows.extend((
            exact_shadow_receipt("k4_internal", level, dt_raw, exact_long_result),
            exact_shadow_receipt("k4_boosted", level, dt_raw, exact_boost_result),
        ))
        exact_long = exact_long_result.samples
        exact_boost = exact_boost_result.samples
        for precision, profile in profiles.items():
            long_result = run_trajectory(
                models["k4"], bounded_state(exact_states["k4_internal"], profile),
                dt_raw, total_steps, KDK, profile,
                f"long:k4_internal:B{precision}:L{level}", level,
                invariant_rows, force_rows, size_rows)
            long_boosted = run_trajectory(
                models["k4"], bounded_state(exact_states["k4_boosted"], profile),
                dt_raw, total_steps, KDK, profile,
                f"long:k4_boosted:B{precision}:L{level}", level,
                invariant_rows, force_rows, size_rows)
            prefix = _state_prefix("k4_internal", "k4", "long", KDK,
                                   level, dt_raw, total_steps, long_result)
            long_endpoint_rows.extend(state_rows(prefix, long_result.final))
            boost_prefix = _state_prefix("k4_boosted", "k4", "long", KDK,
                                         level, dt_raw, total_steps, long_boosted)
            long_endpoint_rows.extend(state_rows(boost_prefix, long_boosted.final))
            append_energy_rows(long_energy_rows, "k4_internal", "long", KDK,
                               precision, level, dt_raw, long_result.energies)
            append_representation_rows(
                representation_rows, "k4_internal", "long_exact_prefix", KDK,
                precision, level, dt_raw,
                long_result.samples[:len(exact_long)], exact_long, models["k4"])
            append_representation_rows(
                representation_rows, "k4_boosted", "long_exact_prefix", KDK,
                precision, level, dt_raw,
                long_boosted.samples[:len(exact_boost)], exact_boost, models["k4"])
            append_covariance_rows(covariance_rows, "galilean_boost", "long",
                                   precision, level, dt_raw,
                                   long_result.samples, long_boosted.samples)
            for candidate in (long_result, long_boosted):
                trajectory = (
                    f"long:{'k4_internal' if candidate is long_result else 'k4_boosted'}:"
                    f"B{precision}:L{level}"
                )
                operation_rows.append(operation_count_row(
                    trajectory, precision, level, KDK, models["k4"], candidate))
        print(f"bounded phase level {level}: complete", flush=True)

    metadata_rows = [
        {"key": "schema", "value": "mls.bounded-fractional-phase-state.raw.v1"},
        {"key": "accepted_parent_sha", "value": PARENT_SHA},
        {"key": "accepted_parent_tag", "value": PARENT_TAG},
        {"key": "accepted_parent_tag_object", "value": PARENT_TAG_OBJECT},
        {"key": "accepted_parent_archive_sha256", "value": PARENT_ARCHIVE_SHA256},
        {"key": "accepted_parent_archive_size", "value": PARENT_ARCHIVE_SIZE},
        {"key": "source_sha", "value": source_sha},
        {"key": "configured_source_branch", "value": source_branch},
        {"key": "source_dirty", "value": str(source_dirty).lower()},
        {"key": "branch", "value": BRANCH},
        {"key": "candidate", "value": "fixed_precision_variable_exponent_binary_phase_state"},
        {"key": "gmpy2_version", "value": gmpy2.version()},
        {"key": "mpfr_version", "value": gmpy2.mpfr_version()},
        {"key": "rounding", "value": ROUNDING_NAME},
        {"key": "leading_exponent_range", "value": "[-16382,16383]"},
        {"key": "mpfr_context_emin", "value": MPFR_EMIN},
        {"key": "mpfr_context_emax", "value": MPFR_EMAX},
        {"key": "subnormalization", "value": "false"},
        {"key": "adaptive_precision", "value": "false"},
        {"key": "hidden_residual_or_history", "value": "false"},
        {"key": "causal_state_shape", "value": CAUSAL_STATE_SHAPE},
        {"key": "causal_state_shape_sha256",
         "value": hashlib.sha256(CAUSAL_STATE_SHAPE.encode("utf-8")).hexdigest()},
        {"key": "causal_state_slots_only", "value": "true"},
        {"key": "force_geometry", "value": "cancellation_resistant_binary64"},
        {"key": "safe_domain", "value": "2^-24"},
        {"key": "exact_comparator_maximum_component_bits",
         "value": EXACT_MAX_COMPONENT_BITS},
        {"key": "exact_comparator_median_component_bits",
         "value": EXACT_MEDIAN_COMPONENT_BITS},
        {"key": "exact_comparator_maximum_checkpoint_bytes",
         "value": EXACT_MAX_CHECKPOINT_BYTES},
        {"key": "domain_scratch_bit_limit_formula",
         "value": "4*(B+(leading_exponent_max-leading_exponent_min))+64"},
        {"key": "observer_event_encoding",
         "value": "length_framed_utf8_fields_then_sha256_v1"},
        {"key": "observer_stream_encoding",
         "value": "step_framed_ordered_event_sha256_v1"},
        {"key": "promotion", "value": "NO_PROMOTION"},
    ]
    precision_rows: list[dict[str, object]] = []
    for precision in PRECISIONS:
        profile = profiles[precision]
        row: dict[str, object] = {
            "precision": precision,
            "unit_roundoff": ratio_text(Fraction(1, 2**precision)),
            "leading_exponent_min": LEADING_EXPONENT_MIN,
            "leading_exponent_max": LEADING_EXPONENT_MAX,
            "component_bytes": profile.component_bytes,
            "phase_bytes_per_packet": profile.phase_bytes_per_packet,
            "complete_packet_bytes": profile.packet_bytes,
            "domain_scratch_bit_limit": domain_scratch_bit_limit(precision),
        }
        component_row(row, "lq", profile.lq, precision)
        row["lq_conversion_inexact"] = str(profile.lq_conversion_inexact).lower()
        row["lq_rounding_audit_sha256"] = profile.lq_rounding_audit_sha256
        row["rounding"] = ROUNDING_NAME
        precision_rows.append(row)
    unit_rows = [{
        "Lq": ratio_text(LQ), "Mq": ratio_text(MQ), "Tq": ratio_text(TQ),
        "Pq": ratio_text(PQ), "Eq": ratio_text(EQ), "Fq": ratio_text(FQ),
        "position_budget": ratio_text(POSITION_BUDGET),
        "momentum_budget": ratio_text(MOMENTUM_BUDGET),
        "angular_centrality_budget": ratio_text(ANGULAR_BUDGET),
        "energy_budget": ratio_text(ENERGY_BUDGET),
        "energy_slope_budget": ratio_text(ENERGY_SLOPE_BUDGET),
    }]

    write_rows(output / "metadata.csv", ("key", "value"), metadata_rows)
    write_rows(output / "precisions.csv", tuple(precision_rows[0]), precision_rows)
    write_rows(output / "units.csv", tuple(unit_rows[0]), unit_rows)
    write_rows(output / "parent_fingerprint.csv",
               ("file", "sha256", "expected_sha256", "passed"), fingerprint_rows)
    write_rows(output / "positive_control.csv", ("check", "passed", "detail"), positive_rows)
    for filename in ("reference_packets.csv", "relations.csv", "force_operator.csv"):
        shutil.copyfile(parent_raw / filename, output / filename)
    write_rows(output / "initial_states.csv", STATE_FIELDS, initial_rows)
    write_rows(output / "endpoints.csv", STATE_FIELDS, endpoint_rows)
    write_rows(output / "long_endpoints.csv", STATE_FIELDS, long_endpoint_rows)
    write_rows(output / "checkpoint_states.csv", STATE_FIELDS, checkpoint_state_rows)
    write_rows(output / "recovery_states.csv", STATE_FIELDS, recovery_state_rows)
    write_rows(output / "representation_error.csv", (
        "scenario_id", "scope", "path", "precision", "level", "dt_raw", "sample",
        "candidate_state_hash", "control_state_hash",
        "position_raw_error_num", "position_raw_error_den",
        "position_physical_error_num", "position_physical_error_den",
        "momentum_raw_error_num", "momentum_raw_error_den",
        "momentum_physical_error_num", "momentum_physical_error_den",
        "energy_error_num", "energy_error_den",
    ), representation_rows)
    energy_fields = (
        "scenario_id", "scope", "path", "precision", "level", "dt_raw", "sample",
        "potential_binary64_bits", "kinetic_num", "kinetic_den", "kinetic_hash",
        "potential_num", "potential_den", "potential_hash",
        "mechanical_num", "mechanical_den", "mechanical_hash",
    )
    write_rows(output / "energies.csv", energy_fields, energy_rows)
    write_rows(output / "long_energy.csv", energy_fields, long_energy_rows)
    invariant_rows.close()
    force_rows.close()
    write_rows(output / "reversibility.csv", (
        "scenario_id", "precision", "level", "dt_raw", "steps", "forward_status",
        "backward_status", "initial_hash", "recovered_hash", "complete_state_identical",
        "position_raw_error_num", "position_raw_error_den",
        "position_physical_error_num", "position_physical_error_den",
        "momentum_raw_error_num", "momentum_raw_error_den",
        "momentum_physical_error_num", "momentum_physical_error_den",
    ), reversibility_rows)
    write_rows(output / "covariance.csv", (
        "kind", "scope", "precision", "level", "dt_raw", "sample",
        "baseline_hash", "transformed_hash", "bit_identical",
        "relative_position_raw_num", "relative_position_raw_den",
        "relative_position_physical_num", "relative_position_physical_den",
        "relative_momentum_raw_num", "relative_momentum_raw_den",
        "relative_momentum_physical_num", "relative_momentum_physical_den",
    ), covariance_rows)
    write_rows(output / "checkpoint.csv", (
        "scenario_id", "precision", "level", "dt_raw", "steps", "checkpoint_step",
        "checkpoint_hash", "checkpoint_bytes", "decoded_hash", "whole_final_hash",
        "resumed_final_hash", "whole_suffix_event_count", "resumed_event_count",
        "whole_suffix_event_sha256", "resumed_event_sha256",
        "event_suffix_identical", "canonical_round_trip",
    ), checkpoint_rows)
    write_rows(output / "domain.csv", (
        "scenario_id", "precision", "level", "status", "prior_hash", "returned_hash",
        "time_unchanged", "state_unchanged", "event_rows_emitted", "energy_ledger_present",
        "observer_events_emitted", "prior_energy_observation_sha256",
        "returned_energy_observation_sha256", "energy_observation_unchanged",
        "offending_relation_index", "chord_minimum_case",
        "comparison_lhs_num", "comparison_lhs_den",
        "comparison_rhs_num", "comparison_rhs_den",
        "domain_scratch_observed_bits", "domain_scratch_limit_bits",
    ), domain_rows)
    write_rows(output / "state_size.csv", (
        "trajectory_id", "precision", "level", "step", "label", "packet_count",
        "component_bytes", "phase_bytes_per_packet", "complete_packet_bytes",
        "state_bytes", "state_hash", "causal_cache_bytes", "causal_history_bytes",
    ), size_rows)
    write_rows(output / "operation_counts.csv", (
        "trajectory_id", "precision", "level", "path", "packet_count", "relation_count",
        "completed_steps", "per_step_expected", "expected_categories", "observed_categories",
        "inexact_categories", "inexact_total", "exact_total", "rounding_audit_records",
        "rounding_audit_sha256", "categories_passed", "total_expected", "total_observed", "passed",
    ), operation_rows)
    write_rows(output / "rational_comparator.csv", (
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
    ), rational_comparator_rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    try:
        materialize(arguments.parent_raw, arguments.output, arguments.source)
        print("BOUNDED FRACTIONAL PHASE STATE RAW COMPLETE: UNDISPOSITIONED NO_PROMOTION")
        return 0
    except (OSError, ValueError, ArithmeticError, LabError) as error:
        print(f"BOUNDED FRACTIONAL PHASE STATE FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
