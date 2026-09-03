#!/usr/bin/env python3
"""Focused executable contracts for the bounded MPFR phase-state candidate."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "tools"))

import run_bounded_fractional_phase_state_lab as lab  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def value(profile: lab.Profile, rational: lab.Fraction) -> lab.mpfr:
    with profile.activate() as context:
        return lab.rounded_fraction(context, profile.precision, rational, "test_conversion")


def zero_vector(profile: lab.Profile) -> list[lab.mpfr]:
    return [value(profile, lab.Fraction()) for _ in range(3)]


def main() -> int:
    require(lab.gmpy2.version() == "2.3.1", "gmpy2 version differs")
    require(lab.gmpy2.mpfr_version() == "MPFR 4.2.2", "MPFR version differs")
    require(lab.PRECISIONS == (64, 96, 128, 192, 256), "precision inventory differs")
    require(
        len(lab.accepted_trajectory_ids()) == 425,
        "accepted invariant/force/operation trajectory inventory differs",
    )

    # Hashes bind the exact inherited binary preimage, including the empty
    # magnitude encoding of zero and the fixed x/y/z vector cardinality.
    fraction = lab.Fraction(-3, 10)
    expected_fraction_preimage = (
        b"\x01" + (1).to_bytes(8, "little") + b"\x03"
        + (1).to_bytes(8, "little") + b"\x0a"
    )
    require(
        lab.fraction_hash(fraction)
        == hashlib.sha256(expected_fraction_preimage).hexdigest(),
        "exact fraction hash preimage differs",
    )
    vector = (lab.Fraction(), fraction, lab.Fraction(7, 8))
    expected_vector_preimage = (
        b"\x00" + (0).to_bytes(8, "little")
        + (1).to_bytes(8, "little") + b"\x01"
        + expected_fraction_preimage
        + b"\x00" + (1).to_bytes(8, "little") + b"\x07"
        + (1).to_bytes(8, "little") + b"\x08"
    )
    require(
        lab.vector_hash(vector)
        == hashlib.sha256(expected_vector_preimage).hexdigest(),
        "exact x/y/z vector hash preimage differs",
    )
    try:
        lab.vector_hash(vector[:2])
    except lab.LabError:
        pass
    else:
        raise AssertionError("non-three-component evidence vector was hashable")

    for precision, expected_packet_bytes in {
        64: 94, 96: 118, 128: 142, 192: 190, 256: 238,
    }.items():
        profile = lab.Profile(precision)
        require(profile.packet_bytes == expected_packet_bytes, "packet byte profile differs")
        require(profile.lq_conversion_inexact,
                "frozen Lq conversion was not recorded as inexact")
        require(len(profile.lq_rounding_audit_sha256) == 64,
                "frozen Lq conversion audit digest width differs")
        packet = lab.Packet(
            7, 524288,
            [value(profile, lab.Fraction(3, 2)), value(profile, lab.Fraction(-1, 3)),
             value(profile, lab.Fraction())],
            [value(profile, lab.Fraction(2**39 + 1)), value(profile, lab.Fraction(-5, 7)),
             value(profile, lab.Fraction())],
        )
        state = lab.State(precision, 19, [packet])
        lab.validate_causal_state_shape()
        try:
            state.hidden_history = 1  # type: ignore[attr-defined]
        except AttributeError:
            pass
        else:
            raise AssertionError("causal state accepted an unregistered side field")
        encoded = lab.encode_state(state)
        decoded = lab.decode_state(encoded)
        require(lab.encode_state(decoded) == encoded, "canonical state did not round trip")
        require(len(encoded) == len(lab.MAGIC) + 24 + expected_packet_bytes,
                "fixed state header or packet size differs")
        require(lab.state_hash(state) == hashlib.sha256(encoded).hexdigest(),
                "state hash is not canonical-byte hash")
        zero = lab.encode_component(value(profile, lab.Fraction()), precision)
        require(zero[0] == 0 and int.from_bytes(zero[3:5], "little", signed=True) == 0 and
                not any(zero[5:]), "zero encoding is not unique")
        malformed = bytearray(zero)
        malformed[0] = 1
        try:
            lab.decode_component(bytes(malformed), precision, profile)
        except lab.LabError:
            pass
        else:
            raise AssertionError("negative encoded zero was accepted")

    expected_scratch_limits = {
        64: 131380, 96: 131508, 128: 131636, 192: 131892, 256: 132148,
    }
    require({precision: lab.domain_scratch_bit_limit(precision)
             for precision in lab.PRECISIONS} == expected_scratch_limits,
            "mechanical domain scratch-cap formula differs")
    boundary = lab.bounded_chord_certificate(
        [lab.Fraction(1), lab.Fraction(), lab.Fraction()],
        [lab.Fraction(1), lab.Fraction(), lab.Fraction()],
        [lab.Fraction(2**24), lab.Fraction(), lab.Fraction()], 64)
    require(boundary.safe and boundary.minimum_case == "initial" and
            boundary.lhs == boundary.rhs == 1,
            "safe-domain equality boundary was not accepted exactly")
    require(boundary.scratch_observed_bits <= boundary.scratch_limit_bits,
            "bounded domain certificate exceeded its scratch cap")
    try:
        lab.bounded_chord_certificate(
            [lab.Fraction(2**expected_scratch_limits[64]), lab.Fraction(), lab.Fraction()],
            [lab.Fraction(2**expected_scratch_limits[64]), lab.Fraction(), lab.Fraction()],
            [lab.Fraction(1), lab.Fraction(), lab.Fraction()], 64)
    except lab.LabError as error:
        require(str(error) == "domain_scratch_bound_exceeded",
                "domain scratch overflow classification differs")
    else:
        raise AssertionError("domain scratch cap did not fail closed")

    exact_safe = lab.exact_lab.State(0, [lab.exact_lab.Packet(
        1, 1,
        [lab.Fraction(1, 2 ** (lab.EXACT_MAX_COMPONENT_BITS - 1)),
         lab.Fraction(), lab.Fraction()],
        [lab.Fraction(), lab.Fraction(), lab.Fraction()],
    )])
    exact_unsafe = lab.exact_lab.State(0, [lab.exact_lab.Packet(
        1, 1,
        [lab.Fraction(1, 2 ** lab.EXACT_MAX_COMPONENT_BITS),
         lab.Fraction(), lab.Fraction()],
        [lab.Fraction(), lab.Fraction(), lab.Fraction()],
    )])
    require(not lab.exact_shadow_complexity(exact_safe)[3],
            "exact comparator rejected its inclusive bit ceiling")
    require(lab.exact_shadow_complexity(exact_unsafe)[3],
            "exact comparator did not stop beyond its bit ceiling")

    profile = lab.Profile(64)
    with profile.activate() as context:
        rounding_count = lab.OperationCounter()
        lab.rounded_fraction(context, 64, lab.Fraction(1), "exact_test", rounding_count)
        lab.rounded_fraction(context, 64, lab.Fraction(1, 3), "inexact_test", rounding_count)
        require(rounding_count.total == 2 and rounding_count.inexact_total == 1 and
                rounding_count.inexact_categories == {"inexact_test": 1},
                "candidate MPFR inexact accounting differs")
        require(rounding_count.audit_sha256() != lab.OperationCounter().audit_sha256(),
                "rounding audit did not bind primitive results")
        tie_down = lab.rounded_fraction(
            context, 64, lab.Fraction(1) + lab.Fraction(1, 2**64), "tie_down")
        tie_up = lab.rounded_fraction(
            context, 64, lab.Fraction(1) + lab.Fraction(3, 2**64), "tie_up")
        require(lab.exact_dyadic(tie_down) == 1, "nearest-even lower tie differs")
        require(lab.exact_dyadic(tie_up) == lab.Fraction(1) + lab.Fraction(1, 2**62),
                "nearest-even upper tie differs")
        minimum = lab.rounded_fraction(
            context, 64, lab.Fraction(1, 2**16382), "minimum_exponent")
        maximum = lab.rounded_fraction(
            context, 64, lab.Fraction(2**16383), "maximum_exponent")
        require(lab.component_parts(minimum, 64)[1] == lab.LEADING_EXPONENT_MIN,
                "minimum leading exponent differs")
        require(lab.component_parts(maximum, 64)[1] == lab.LEADING_EXPONENT_MAX,
                "maximum leading exponent differs")
        for bad, label in ((lab.Fraction(1, 2**16383), "underflow"),
                           (lab.Fraction(2**16384), "overflow")):
            try:
                lab.rounded_fraction(context, 64, bad, label)
            except lab.LabError as error:
                require(str(error).startswith("phase_range_failure"),
                        "range failure classification differs")
            else:
                raise AssertionError(f"{label} did not fail closed")

    # Relative subtraction occurs before binary64 conversion.  The absolute
    # physical coordinates alias in binary64 while the bounded relation does not.
    common = lab.Fraction(2**47)
    delta = lab.Fraction(1, 2**15)
    first = lab.Packet(1, 524288, [value(profile, common), *zero_vector(profile)[1:]],
                       zero_vector(profile))
    second = lab.Packet(2, 524288, [value(profile, common + delta), *zero_vector(profile)[1:]],
                        zero_vector(profile))
    translated = lab.State(64, 0, [first, second])
    with profile.activate() as context:
        relative = lab.relation_offset(
            translated, lab.exact_lab.Relation(0, 1, 2, float(delta * lab.LQ)), context)
        relative_si = lab.rounded_mul(context, 64, relative[0], profile.lq,
                                      "relative_unit_multiplication")
    require(lab.exact_dyadic(relative[0]) == delta, "bounded relative subtraction lost delta")
    require(float(value(profile, common) * profile.lq) ==
            float(value(profile, common + delta) * profile.lq),
            "absolute-position binary64 negative control did not alias")
    require(float(relative_si) != 0.0, "already-relative binary64 conversion lost delta")

    relation = lab.exact_lab.Relation(0, 1, 2, 1.0)
    model = lab.exact_lab.Model(
        "pair",
        {1: [lab.Fraction(), lab.Fraction(), lab.Fraction()],
         2: [lab.Fraction(128_000_000_000), lab.Fraction(), lab.Fraction()]},
        {1: 524288, 2: 524288},
        [relation],
        [[1.0]],
    )
    dynamic = lab.State(64, 0, [
        lab.Packet(1, 524288, zero_vector(profile), zero_vector(profile)),
        lab.Packet(2, 524288,
                   [value(profile, lab.Fraction(129_000_000_000)),
                    value(profile, lab.Fraction(1_000_000_000)),
                    value(profile, lab.Fraction())],
                   zero_vector(profile)),
    ])
    force_rows: list[dict[str, object]] = []
    count = lab.OperationCounter()
    kicked = lab.kick(model, dynamic, 31_250_000, profile,
                      force_rows=force_rows, counter=count)
    require(count.total == 18, "one-relation kick operation count differs")
    require(force_rows and force_rows[0]["stored_impulse_centrality_residual_hash"] and
            force_rows[0]["first_actual_centrality_residual_hash"] and
            force_rows[0]["second_actual_centrality_residual_hash"],
            "exact-dyadic centrality observation missing")
    require(lab.state_hash(kicked) != lab.state_hash(dynamic), "bounded kick vanished")
    long_force_rows: list[dict[str, object]] = []
    lab.kick(model, dynamic, 31_250_000, profile, trajectory="long:test",
             force_rows=long_force_rows)
    for prefix in lab.VECTOR_PREFIXES_FORCE:
        require(all(f"{prefix}_raw_{axis}_dyadic" in long_force_rows[0] for axis in "xyz"),
                f"long force row omitted signed raw {prefix} components")
        require(f"{prefix}_x_num" not in long_force_rows[0],
                f"long force row unexpectedly expanded physical {prefix} components")

    drift_count = lab.OperationCounter()
    drifted = lab.drift(model, kicked, 62_500_000, profile, drift_count)
    require(drift_count.total == 14, "two-packet drift operation count differs")
    require(all(
        lab.encode_component(before, 64) == lab.encode_component(after, 64)
        for old_packet, new_packet in zip(lab.canonical_packets(kicked), lab.canonical_packets(drifted))
        for before, after in zip(old_packet.p, new_packet.p)
    ), "drift changed stored momentum")

    step_count = lab.OperationCounter()
    status, stepped = lab.one_step(
        model, dynamic, 62_500_000, lab.KDK, profile, counter=step_count)
    require(status == "accepted", "bounded KDK smoke step failed")
    require(stepped.time_raw == 62_500_000, "bounded KDK did not advance raw time")
    expected_categories = lab.expected_operation_categories(model, dynamic, lab.KDK)
    require(step_count.categories == expected_categories and
            step_count.total == sum(expected_categories.values()) == 50,
            "KDK causal operation category breakdown differs")
    require(lab.canonical_operation_categories(step_count.categories) ==
            lab.canonical_operation_categories(expected_categories),
            "canonical operation category spelling differs")
    count_row = lab.operation_count_row(
        "test", 64, 0, lab.KDK, model,
        lab.RunResult("accepted", dynamic, stepped, 1, 1, [dynamic, stepped], [], [], step_count))
    require(count_row["expected_categories"] == count_row["observed_categories"] and
            count_row["categories_passed"] == "true" and count_row["passed"] == "true",
            "operation-count evidence row omitted or rejected the category breakdown")
    require(count_row["inexact_total"] + count_row["exact_total"] ==
            count_row["total_observed"] == count_row["rounding_audit_records"] and
            len(str(count_row["rounding_audit_sha256"])) == 64,
            "operation-count row omitted inexact or rounding-audit accounting")

    # Checkpoint replay covers the complete causal observer stream.  Each
    # one-relation KDK step has two force-audit events, four stage-invariant
    # events, and one post-commit energy event, in causal order. The resumed invocation uses the original
    # invariant baseline and absolute step labels, so every framed field agrees.
    observer_trajectory = "short:test:bounded_binary_kick_drift_kick:B64:L0"
    original_invariants = lab.exact_state_invariants(dynamic)
    whole = lab.run_trajectory(
        model, dynamic, 62_500_000, 2, lab.KDK, profile,
        observer_trajectory, 0, collect_observer_events=True,
        initial_invariants=original_invariants)
    first_invariants: list[dict[str, object]] = []
    first_forces: list[dict[str, object]] = []
    first_trajectory = "checkpoint:first:B64:L0"
    first = lab.run_trajectory(
        model, dynamic, 62_500_000, 1, lab.KDK, profile,
        first_trajectory, 0, first_invariants, first_forces)
    resumed_invariants: list[dict[str, object]] = []
    resumed_forces: list[dict[str, object]] = []
    resumed_trajectory = "checkpoint:resumed:B64:L0"
    resumed = lab.run_trajectory(
        model, lab.decode_state(lab.encode_state(first.final)), 62_500_000, 1,
        lab.KDK, profile, resumed_trajectory, 0,
        resumed_invariants, resumed_forces,
        collect_observer_events=True, step_offset=1,
        initial_invariants=original_invariants,
        observer_trajectory=observer_trajectory)
    require(len(whole.events) == 2 and all(len(events) == 7 for events in whole.events),
            "complete KDK observer-event inventory differs")
    require(resumed.events == whole.events[1:],
            "resumed complete observer-event suffix differs")
    require(lab.observer_event_count(resumed.events) == 7 and
            lab.observer_stream_sha256(resumed.events) ==
            lab.observer_stream_sha256(whole.events[1:]),
            "checkpoint observer-event count or digest differs")
    require(
        len(first_invariants) == len(resumed_invariants) == 5
        and len(first_forces) == len(resumed_forces) == 2
        and {str(row["trajectory_id"]) for row in first_invariants + first_forces}
            == {first_trajectory}
        and {str(row["trajectory_id"]) for row in resumed_invariants + resumed_forces}
            == {resumed_trajectory},
        "checkpoint halves lack uniquely identified invariant/force audit rows",
    )
    require(
        int(first_invariants[0]["step"]) == 0
        and int(resumed_invariants[0]["step"]) == 1
        and resumed.events == whole.events[1:],
        "checkpoint audit IDs leaked into the canonical observer suffix",
    )

    # The complete crossing chord must reject with no state or event mutation.
    crossing_model = lab.exact_lab.Model(
        "crossing",
        {1: [lab.Fraction(-128_000_000_000), lab.Fraction(), lab.Fraction()],
         2: [lab.Fraction(128_000_000_000), lab.Fraction(), lab.Fraction()]},
        {1: 524288, 2: 524288},
        [lab.exact_lab.Relation(0, 1, 2, 2.0)],
        [[0.0]],
    )
    crossing = lab.State(64, 0, [
        lab.Packet(1, 524288,
                   [value(profile, lab.Fraction(-128_000_000_000)),
                    value(profile, lab.Fraction()), value(profile, lab.Fraction())],
                   [value(profile, lab.Fraction(134_217_728)),
                    value(profile, lab.Fraction()), value(profile, lab.Fraction())]),
        lab.Packet(2, 524288,
                   [value(profile, lab.Fraction(128_000_000_000)),
                    value(profile, lab.Fraction()), value(profile, lab.Fraction())],
                   [value(profile, lab.Fraction(-134_217_728)),
                    value(profile, lab.Fraction()), value(profile, lab.Fraction())]),
    ])
    before = lab.encode_state(crossing)
    invariant_rows: list[dict[str, object]] = []
    central_rows: list[dict[str, object]] = []
    rejected_events: list[str] = []
    failure_details: list[dict[str, object]] = []
    prior_energy = lab.observed_energy(crossing_model, crossing, profile)
    prior_energy_digest = lab.observer_event_digest(
        "energy", lab.energy_observer_row(
            "domain:test", 64, 0, 0, crossing, prior_energy))
    status, returned = lab.one_step(
        crossing_model, crossing, 1_000_000_000, lab.KDK, profile,
        invariant_rows=invariant_rows, force_rows=central_rows,
        failure_details=failure_details, observer_events=rejected_events)
    require(status == "chord_domain_failure", "crossing chord did not fail closed")
    require(lab.encode_state(returned) == before and lab.encode_state(crossing) == before,
            "domain rejection was not atomic")
    require(not invariant_rows and not central_rows and not rejected_events,
            "rejected step leaked observer/event rows")
    returned_energy = lab.observed_energy(crossing_model, returned, profile)
    returned_energy_digest = lab.observer_event_digest(
        "energy", lab.energy_observer_row(
            "domain:test", 64, 0, 0, returned, returned_energy))
    require(returned_energy == prior_energy and returned_energy_digest == prior_energy_digest,
            "domain rejection changed the mechanical-energy observation")
    require(len(failure_details) == 1 and
            failure_details[0]["domain_scratch_observed_bits"] <=
            failure_details[0]["domain_scratch_limit_bits"] == expected_scratch_limits[64],
            "domain rejection did not export its bounded scratch observation")

    free_model = lab.exact_lab.Model("free", {}, {1: 1}, [], [])
    free = lab.State(64, 0, [lab.Packet(
        1, 1, zero_vector(profile),
        [value(profile, lab.Fraction(1, 3)), value(profile, lab.Fraction(-2, 5)),
         value(profile, lab.Fraction(7, 11))],
    )])
    initial_bytes = len(lab.encode_state(free))
    current = free
    for _ in range(400):
        current = lab.drift(free_model, current, 1, profile)
    require(len(lab.encode_state(current)) == initial_bytes,
            "causal state size grew with operation count")

    print("bounded fractional phase-state algorithm contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
