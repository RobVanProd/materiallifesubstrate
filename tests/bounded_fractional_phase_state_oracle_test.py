#!/usr/bin/env python3
"""Deterministic positives and semantic mutations for the bounded oracle.

The final oracle replay is intentionally large.  This regression exercises two
independent deterministic one-step positives, then routes each mutation to the
smallest production verifier that owns its contract.  No mutation is accepted
merely because a file digest changed.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Callable


Detector = Callable[[Path, Path], None]
Mutation = Callable[[Path, Path], None]


def load_oracle(repository: Path) -> ModuleType:
    reference = repository / "reference"
    sys.path.insert(0, str(reference))
    path = reference / "bounded_fractional_phase_state_oracle.py"
    specification = importlib.util.spec_from_file_location("bounded_phase_oracle", path)
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load bounded phase-state oracle")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def overlay(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    for path in source.iterdir():
        if path.is_file():
            os.symlink(path.resolve(), destination / path.name)


def edit_cell(
    root: Path, filename: str, predicate: Callable[[dict[str, str]], bool],
    column: str, value: str | Callable[[str], str],
) -> None:
    path = root / filename
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        content = list(reader)
    changed = False
    for row in content:
        if not changed and predicate(row):
            if column not in row:
                raise RuntimeError(f"mutation column absent: {filename}/{column}")
            row[column] = value(row[column]) if callable(value) else value
            changed = True
    if not changed:
        raise RuntimeError(f"mutation target absent: {filename}/{column}")
    if path.is_symlink():
        path.unlink()
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(content)


def add_hidden_column(root: Path) -> None:
    path = root / "initial_states.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[0] += ",discarded_bit_history"
    lines[1:] = [line + ",0" for line in lines[1:]]
    if path.is_symlink():
        path.unlink()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def trajectory_rows(path: Path, trajectory: str, limit: int | None = None) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen = False
    for row in oracle.iter_rows(path):
        if row["trajectory_id"] == trajectory:
            seen = True
            result.append(row)
            if limit is not None and len(result) == limit:
                break
        elif seen:
            break
    if not result:
        raise RuntimeError(f"trajectory rows absent: {trajectory}")
    return result


def baseline_context(raw: Path, parent_raw: Path) -> dict[str, object]:
    oracle.verify_schema_metadata_profiles(raw, True)
    oracle.verify_parent_hashes(raw, parent_raw)
    oracle.verify_positive_control_rows(raw, parent_raw)
    state_report = oracle.verify_state_tables(raw, parent_raw)
    models = oracle.load_models(raw)
    return {"state_report": state_report, "models": models}


def first_short_replay(raw: Path, context: dict[str, object]) -> str:
    state_report = context["state_report"]
    models = context["models"]
    initial = state_report["initial"]
    model = models["k4"]
    state = initial[(64, "k4_breathing", "initial", 0)]
    trajectory_id = f"short:k4_breathing:{oracle.CONTROL}:B64:L0"
    run, stages, forces = oracle.run_trajectory(
        model, state, oracle.TIMESTEPS_RAW[0], oracle.STEP_COUNTS[0],
        oracle.CONTROL, True,
    )
    invariant_rows = trajectory_rows(raw / "invariants.csv", trajectory_id)
    force_rows = trajectory_rows(raw / "force_audit.csv", trajectory_id)
    if len(invariant_rows) != len(stages) or len(force_rows) != len(forces):
        raise oracle.OracleError("first short audit inventory differs")
    baseline = oracle.exact_state_invariants(state)
    for row, record in zip(invariant_rows, stages):
        step, stage, stage_state, p_bound, l_bound = record
        oracle.require(int(row["step"]) == step and row["stage"] == stage,
                       "first short invariant order differs")
        oracle.verify_invariant_row(
            row, stage_state, baseline, model, p_bound, l_bound
        )
    for row, record in zip(force_rows, forces):
        step, stage, expected = record
        oracle.require(int(row["step"]) == step and row["stage"] == stage,
                       "first short force order differs")
        oracle.verify_force_row(row, expected)
    energy = [
        row for row in oracle.rows(raw / "energies.csv")
        if row["scenario_id"] == "k4_breathing" and row["path"] == oracle.CONTROL
        and row["precision"] == "64" and row["level"] == "0"
    ]
    oracle.require(len(energy) == len(run.samples), "first short energy inventory differs")
    for sample, (row, phase) in enumerate(zip(energy, run.samples)):
        oracle.require(int(row["sample"]) == sample, "first short energy order differs")
        oracle.verify_energy_row(row, oracle.mechanical_energy(model, phase))
    operation = next(
        row for row in oracle.rows(raw / "operation_counts.csv")
        if row["trajectory_id"] == trajectory_id
    )
    oracle.verify_operation_row(
        operation, trajectory_id, 64, 0, oracle.CONTROL, model, state,
        oracle.STEP_COUNTS[0], run,
    )
    return oracle.phase_hash(run.final)


def first_long_audit(raw: Path, context: dict[str, object]) -> None:
    state_report = context["state_report"]
    model = context["models"]["k4"]
    state = state_report["initial"][(64, "k4_internal", "initial", 0)]
    trajectory_id = "long:k4_internal:B64:L0"
    _run, stages, forces = oracle.run_trajectory(
        model, state, oracle.TIMESTEPS_RAW[0], 1, oracle.KDK, True
    )
    invariant_rows = trajectory_rows(
        raw / "invariants.csv", trajectory_id, len(stages)
    )
    force_rows = trajectory_rows(raw / "force_audit.csv", trajectory_id, len(forces))
    baseline = oracle.exact_state_invariants(state)
    for row, record in zip(invariant_rows, stages):
        _step, _stage, phase, p_bound, l_bound = record
        oracle.verify_invariant_row(row, phase, baseline, model, p_bound, l_bound)
    for row, (_step, _stage, expected) in zip(force_rows, forces):
        oracle.verify_force_row(row, expected)


def first_auxiliary_audit(raw: Path, context: dict[str, object]) -> None:
    """Replay a transformed invocation, including absolute P/L and centrality."""
    precision = 64
    level = 0
    trajectory_id = "covariance:proper_lattice_rotation:B64:L0"
    state = context["state_report"]["initial"][
        (precision, "k4_rotated", "initial", 0)
    ]
    model = context["models"]["k4_rotated"]
    run, stages, forces = oracle.run_trajectory(
        model, state, oracle.TIMESTEPS_RAW[level], oracle.STEP_COUNTS[level],
        oracle.KDK, True,
    )
    invariant_rows = trajectory_rows(raw / "invariants.csv", trajectory_id)
    force_rows = trajectory_rows(raw / "force_audit.csv", trajectory_id)
    oracle.require(
        len(invariant_rows) == len(stages) and len(force_rows) == len(forces),
        "first auxiliary audit inventory differs",
    )
    baseline = oracle.exact_state_invariants(state)
    for row, record in zip(invariant_rows, stages):
        step, stage, phase, p_bound, l_bound = record
        oracle.require(
            int(row["step"]) == step and row["stage"] == stage,
            "first auxiliary invariant order differs",
        )
        oracle.verify_invariant_row(
            row, phase, baseline, model, p_bound, l_bound
        )
    for row, record in zip(force_rows, forces):
        step, stage, expected = record
        oracle.require(
            int(row["step"]) == step and row["stage"] == stage,
            "first auxiliary force order differs",
        )
        oracle.verify_force_row(row, expected)
    operation = next(
        row for row in oracle.rows(raw / "operation_counts.csv")
        if row["trajectory_id"] == trajectory_id
    )
    oracle.verify_operation_row(
        operation, trajectory_id, precision, level, oracle.KDK, model, state,
        oracle.STEP_COUNTS[level], run,
    )


def representation_zero(raw: Path, context: dict[str, object]) -> None:
    row = next(
        row for row in oracle.iter_rows(raw / "representation_error.csv")
        if row["scenario_id"] == "k4_breathing" and row["scope"] == "short"
        and row["path"] == oracle.CONTROL and row["precision"] == "256"
        and row["level"] == "0" and row["sample"] == "0"
    )
    state = context["state_report"]["initial"][(256, "k4_breathing", "initial", 0)]
    oracle.require(row["candidate_state_hash"] == oracle.phase_hash(state),
                   "initial representation candidate hash differs")
    for prefix in (
        "position_raw_error", "position_physical_error", "momentum_raw_error",
        "momentum_physical_error", "energy_error",
    ):
        oracle.require(oracle.scalar_from_columns(row, prefix) == 0,
                       f"initial {prefix} is not zero")


def first_reversal(raw: Path, context: dict[str, object]) -> None:
    initial = context["state_report"]["initial"][(64, "k4_breathing", "initial", 0)]
    model = context["models"]["k4"]
    forward, _stages, _forces = oracle.run_trajectory(
        model, initial, oracle.TIMESTEPS_RAW[0], oracle.STEP_COUNTS[0],
        oracle.KDK,
    )
    backward, _stages, _forces = oracle.run_trajectory(
        model, forward.final, -oracle.TIMESTEPS_RAW[0], oracle.STEP_COUNTS[0],
        oracle.KDK,
    )
    row = next(
        row for row in oracle.rows(raw / "reversibility.csv")
        if row["scenario_id"] == "k4_breathing" and row["precision"] == "64"
        and row["level"] == "0"
    )
    x_error = oracle.raw_phase_error(backward.final, initial)
    p_error = oracle.raw_phase_error(backward.final, initial, True)
    oracle.require(
        row["initial_hash"] == oracle.phase_hash(initial)
        and row["recovered_hash"] == oracle.phase_hash(backward.final)
        and oracle.boolean(row["complete_state_identical"]) == (
            oracle.encode_phase_state(initial) == oracle.encode_phase_state(backward.final)
        ), "reversal state declaration differs",
    )
    for prefix, expected in (
        ("position_raw_error", x_error), ("position_physical_error", x_error * oracle.LQ),
        ("momentum_raw_error", p_error), ("momentum_physical_error", p_error * oracle.PQ),
    ):
        oracle.require(oracle.scalar_from_columns(row, prefix) == expected,
                       f"reversal {prefix} differs")


def covariance_scaling(raw: Path, _context: dict[str, object]) -> None:
    for row in oracle.iter_rows(raw / "covariance.csv"):
        x_raw = oracle.scalar_from_columns(row, "relative_position_raw")
        p_raw = oracle.scalar_from_columns(row, "relative_momentum_raw")
        oracle.require(
            oracle.scalar_from_columns(row, "relative_position_physical")
            == x_raw * oracle.LQ
            and oracle.scalar_from_columns(row, "relative_momentum_physical")
            == p_raw * oracle.PQ,
            "covariance raw/physical scaling differs",
        )


def first_domain(raw: Path, context: dict[str, object]) -> None:
    initial = context["state_report"]["initial"][(64, "domain_crossing", "initial", 0)]
    model = context["models"]["pair"]
    first_kick, _count, _audit = oracle.kick(model, initial, 500_000_000)
    proposed = first_kick.clone()
    for packet in proposed.packets:
        coefficient = oracle.rn(oracle.Fraction(1_000_000_000, packet.mass_raw), 64)
        displacement = [oracle.rn(coefficient * value, 64) for value in packet.p]
        packet.x = [oracle.rn(packet.x[i] + displacement[i], 64) for i in range(3)]
    relation = model.relations[0]
    certificate = oracle.bounded_chord_certificate(
        oracle.stored_relation_offset(first_kick, relation),
        oracle.stored_relation_offset(proposed, relation),
        oracle.reference_offset(model, relation), 64,
    )
    row = next(
        row for row in oracle.rows(raw / "domain.csv")
        if row["precision"] == "64" and row["level"] == "0"
    )
    energy = oracle.observer_energy_row(
        "domain:B64:L0", 64, 0, 0, model, initial
    )
    energy_digest = oracle.observer_event_digest("energy", energy)
    oracle.require(
        not certificate.safe and row["status"] == "chord_domain_failure"
        and row["prior_hash"] == row["returned_hash"] == oracle.phase_hash(initial)
        and oracle.boolean(row["time_unchanged"])
        and oracle.boolean(row["state_unchanged"])
        and int(row["event_rows_emitted"]) == 0
        and not oracle.boolean(row["energy_ledger_present"])
        and int(row["observer_events_emitted"]) == 0
        and row["prior_energy_observation_sha256"] == energy_digest
        and row["returned_energy_observation_sha256"] == energy_digest
        and oracle.boolean(row["energy_observation_unchanged"])
        and oracle.scalar_from_columns(row, "comparison_lhs") == certificate.lhs
        and oracle.scalar_from_columns(row, "comparison_rhs") == certificate.rhs
        and int(row["domain_scratch_observed_bits"]) == certificate.scratch_observed_bits
        and int(row["domain_scratch_limit_bits"]) == certificate.scratch_limit_bits,
        "domain atomic/certificate evidence differs",
    )


def first_long_energy(raw: Path, context: dict[str, object]) -> None:
    row = next(
        row for row in oracle.iter_rows(raw / "long_energy.csv")
        if row["precision"] == "64" and row["level"] == "0" and row["sample"] == "0"
    )
    state = context["state_report"]["initial"][(64, "k4_internal", "initial", 0)]
    oracle.verify_energy_row(row, oracle.mechanical_energy(context["models"]["k4"], state))


def first_checkpoint(raw: Path, context: dict[str, object]) -> None:
    precision = 64
    level = 0
    row = next(
        row for row in oracle.rows(raw / "checkpoint.csv")
        if row["precision"] == str(precision) and row["level"] == str(level)
    )
    state_report = context["state_report"]
    oracle.verify_checkpoint_row(
        row, precision, level, context["models"]["k4"],
        state_report["initial"][(precision, "k4_internal", "initial", 0)],
        state_report["checkpoint"][(precision, "k4_internal", oracle.KDK, level)],
    )


def endpoint_replay(raw: Path, context: dict[str, object]) -> None:
    precision = 256
    level = 4
    scenario = "k4_internal"
    selected = [
        row for row in oracle.rows(raw / "endpoints.csv")
        if row["precision"] == str(precision) and row["scenario_id"] == scenario
        and row["path"] == oracle.KDK and row["level"] == str(level)
    ]
    observed = oracle.phase_from_rows(selected)
    initial = context["state_report"]["initial"][(precision, scenario, "initial", 0)]
    replay, _stages, _forces = oracle.run_trajectory(
        context["models"]["k4"], initial, oracle.TIMESTEPS_RAW[level],
        oracle.STEP_COUNTS[level], oracle.KDK,
    )
    oracle.require(
        oracle.encode_phase_state(observed) == oracle.encode_phase_state(replay.final),
        "self-consistent endpoint is not the independent trajectory result",
    )


def mutate_canonical_endpoint(raw: Path, context: dict[str, object]) -> None:
    path = raw / "endpoints.csv"
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        content = list(reader)
    target = [
        row for row in content
        if row["precision"] == "256" and row["scenario_id"] == "k4_internal"
        and row["path"] == oracle.KDK and row["level"] == "4"
    ]
    if not target:
        raise RuntimeError("canonical endpoint mutation target absent")
    row = target[0]
    old = oracle.Dyadic.from_row(row, "px")
    step = 1 if old.significand + 1 < 2**old.precision else -1
    changed = oracle.Dyadic(old.sign, old.precision, old.exponent, old.significand + step)
    changed.validate()
    row["px_sign"] = str(changed.sign)
    row["px_E"] = str(changed.exponent)
    row["px_significand_hex"] = format(changed.significand, f"0{changed.precision // 4}x")
    row["px_wire_hex"] = changed.encode().hex()
    value = changed.fraction()
    row["px_exact_num"] = str(value.numerator)
    row["px_exact_den"] = str(value.denominator)
    original = context["state_report"]["endpoint"][(256, "k4_internal", oracle.KDK, 4)]
    mutated = original.clone()
    packet = next(packet for packet in mutated.packets if packet.identifier == int(row["packet_id"]))
    packet.p[0] = value
    new_hash = oracle.phase_hash(mutated)
    for item in target:
        item["state_hash"] = new_hash
    if path.is_symlink():
        path.unlink()
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(content)


def half_ulp_bound_negative(raw: Path, context: dict[str, object]) -> None:
    """A value-correct force row must still fail an undersized derived bound."""
    model = context["models"]["k4"]
    initial = context["state_report"]["initial"][(64, "k4_breathing", "initial", 0)]
    _run, _stages, force_records = oracle.run_trajectory(
        model, initial, oracle.TIMESTEPS_RAW[0], 1, oracle.CONTROL, True,
    )
    evidence = trajectory_rows(
        raw / "force_audit.csv",
        f"short:k4_breathing:{oracle.CONTROL}:B64:L0", len(force_records),
    )
    selected = next(
        index for index, (_step, _stage, audit) in enumerate(force_records)
        if any(
            oracle.infinity_norm(audit[name]) > 0
            for name in (
                "pair_momentum_residual", "stored_impulse_centrality_residual",
                "first_actual_centrality_residual", "second_actual_centrality_residual",
                "relation_angular_residual",
            )
        )
    )
    row = evidence[selected]
    expected = dict(force_records[selected][2])
    zero = (oracle.Fraction(), oracle.Fraction(), oracle.Fraction())
    expected["pair_momentum_bound"] = zero
    expected["stored_impulse_centrality_bound"] = zero
    expected["first_actual_centrality_bound"] = zero
    expected["second_actual_centrality_bound"] = zero
    expected["relation_angular_bound"] = zero
    try:
        oracle.verify_force_row(row, expected)
    except oracle.OracleError:
        return
    raise RuntimeError("independent half-ULP bound negative was not detected")


def first_comparator_receipt(raw: Path, parent_raw: Path, context: dict[str, object]) -> None:
    level = 0
    scenario = "k4_internal"
    row = next(
        row for row in oracle.rows(raw / "rational_comparator.csv")
        if row["scenario_id"] == scenario and row["level"] == str(level)
    )
    parent_initial = oracle.grouped(
        oracle.rows(parent_raw / "initial_states.csv"), ("scenario_id",)
    )
    state = oracle.rational_from_parent_rows(parent_initial[(scenario,)])
    requested = 16 * oracle.STEP_COUNTS[level]
    maximum = 0
    maximum_median = oracle.Fraction()
    maximum_bytes = 0
    crossing = None
    for step in range(requested + 1):
        component, median, checkpoint_bytes, exceeded = oracle.rational_complexity(state)
        maximum = max(maximum, component)
        maximum_median = max(maximum_median, median)
        maximum_bytes = max(maximum_bytes, checkpoint_bytes)
        if exceeded:
            crossing = (step, component, median, checkpoint_bytes)
            break
        if step < requested:
            state = oracle.rational_step(
                context["models"]["k4"], state, oracle.TIMESTEPS_RAW[level], oracle.KDK
            )
    completed = crossing[0] if crossing else requested
    oracle.require(
        int(row["completed_steps"]) == completed
        and int(row["comparison_samples"]) == completed + 1
        and row["last_comparator_state_hash"] == oracle.rational_hash(state)
        and int(row["maximum_component_bits"]) == maximum
        and oracle.scalar_from_columns(row, "maximum_state_median_bits") == maximum_median
        and int(row["maximum_checkpoint_bytes"]) == maximum_bytes,
        "first exact-rational comparator receipt differs",
    )


def detect_state(raw: Path, parent_raw: Path) -> None:
    oracle.verify_state_tables(raw, parent_raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--parent-raw", type=Path, required=True)
    arguments = parser.parse_args()
    global oracle
    oracle = load_oracle(Path(__file__).resolve().parents[1])

    context = baseline_context(arguments.raw, arguments.parent_raw)
    first = first_short_replay(arguments.raw, context)
    second = first_short_replay(arguments.raw, context)
    if first != second:
        raise RuntimeError("two independent deterministic positives differ")
    first_domain(arguments.raw, context)
    first_long_audit(arguments.raw, context)
    first_auxiliary_audit(arguments.raw, context)
    first_checkpoint(arguments.raw, context)
    half_ulp_bound_negative(arguments.raw, context)
    first_comparator_receipt(arguments.raw, arguments.parent_raw, context)
    oracle.verify_state_size(arguments.raw, context["state_report"])

    schema = lambda raw, _parent: oracle.verify_schema_metadata_profiles(raw, True)
    parent_check = lambda raw, parent_raw: oracle.verify_parent_hashes(raw, parent_raw)
    positive = lambda raw, parent_raw: oracle.verify_positive_control_rows(raw, parent_raw)
    state = lambda raw, parent_raw: detect_state(raw, parent_raw)
    short = lambda raw, _parent: first_short_replay(raw, context)
    long_audit = lambda raw, _parent: first_long_audit(raw, context)
    auxiliary_audit = lambda raw, _parent: first_auxiliary_audit(raw, context)
    representation = lambda raw, _parent: representation_zero(raw, context)
    reversal = lambda raw, _parent: first_reversal(raw, context)
    covariance = lambda raw, _parent: covariance_scaling(raw, context)
    domain = lambda raw, _parent: first_domain(raw, context)
    size = lambda raw, _parent: oracle.verify_state_size(raw, context["state_report"])
    long_energy = lambda raw, _parent: first_long_energy(raw, context)
    checkpoint = lambda raw, _parent: first_checkpoint(raw, context)
    comparator = lambda raw, parent: first_comparator_receipt(raw, parent, context)

    first_force = lambda row: row["trajectory_id"] == (
        f"short:k4_breathing:{oracle.CONTROL}:B64:L0"
    )
    first_invariant = lambda row: row["trajectory_id"] == (
        f"short:k4_breathing:{oracle.CONTROL}:B64:L0"
    )
    first_operation = lambda row: row["trajectory_id"] == (
        f"short:k4_breathing:{oracle.CONTROL}:B64:L0"
    )
    first_long = lambda row: row["trajectory_id"] == "long:k4_internal:B64:L0"
    first_auxiliary = lambda row: row["trajectory_id"] == (
        "covariance:proper_lattice_rotation:B64:L0"
    )

    cases: list[tuple[str, Mutation, Detector]] = [
        ("wrong_parent_payload", lambda _r, p: edit_cell(
            p, "units.csv", lambda row: True, "Lq", "1/127000000000"), parent_check),
        ("wrong_parent_sha", lambda r, _p: edit_cell(
            r, "metadata.csv", lambda row: row["key"] == "accepted_parent_sha",
            "value", "0" * 40), schema),
        ("parent_fingerprint_false", lambda r, _p: edit_cell(
            r, "parent_fingerprint.csv", lambda row: True, "passed", "false"), parent_check),
        ("positive_control_false", lambda r, _p: edit_cell(
            r, "positive_control.csv", lambda row: True, "passed", "false"), positive),
        ("precision_inventory", lambda r, _p: edit_cell(
            r, "precisions.csv", lambda row: row["precision"] == "64", "precision", "63"), schema),
        ("rounding_mode", lambda r, _p: edit_cell(
            r, "metadata.csv", lambda row: row["key"] == "rounding", "value", "toward_zero"), schema),
        ("exponent_range", lambda r, _p: edit_cell(
            r, "precisions.csv", lambda row: row["precision"] == "96",
            "leading_exponent_min", "-16381"), schema),
        ("domain_scratch_cap", lambda r, _p: edit_cell(
            r, "precisions.csv", lambda row: row["precision"] == "128",
            "domain_scratch_bit_limit", lambda value: str(int(value) + 1)), schema),
        ("rounded_lq_profile", lambda r, _p: edit_cell(
            r, "precisions.csv", lambda row: row["precision"] == "64",
            "lq_conversion_inexact", lambda value: "false" if value == "true" else "true"),
         schema),
        ("mpfr_backend_version", lambda r, _p: edit_cell(
            r, "metadata.csv", lambda row: row["key"] == "mpfr_version", "value", "MPFR 4.2.1"), schema),
        ("adaptive_precision", lambda r, _p: edit_cell(
            r, "metadata.csv", lambda row: row["key"] == "adaptive_precision", "value", "true"), schema),
        ("hidden_residual", lambda r, _p: edit_cell(
            r, "metadata.csv", lambda row: row["key"] == "hidden_residual_or_history", "value", "true"), schema),
        ("promotion_relabel", lambda r, _p: edit_cell(
            r, "metadata.csv", lambda row: row["key"] == "promotion", "value", "PROMOTED"), schema),
        ("changed_position_budget", lambda r, _p: edit_cell(
            r, "units.csv", lambda row: True, "position_budget", "1/1"), schema),
        ("changed_energy_slope_budget", lambda r, _p: edit_cell(
            r, "units.csv", lambda row: True, "energy_slope_budget", "1/1"), schema),
        ("changed_reference_geometry", lambda r, _p: edit_cell(
            r, "reference_packets.csv", lambda row: row["model_id"] == "k4",
            "x_raw", lambda value: str(int(value) + 1)), parent_check),
        ("wrong_relation_orientation", lambda r, _p: edit_cell(
            r, "relations.csv", lambda row: row["model_id"] == "k4" and row["relation_index"] == "0",
            "first_id", "2"), parent_check),
        ("changed_force_operator", lambda r, _p: edit_cell(
            r, "force_operator.csv", lambda row: row["model_id"] == "k4" and row["row"] == "0",
            "h_bits", lambda value: str(int(value) + 1)), parent_check),
        ("noncanonical_zero_sign", lambda r, _p: edit_cell(
            r, "initial_states.csv", lambda row: int(row["pz_significand_hex"], 16) == 0,
            "pz_sign", "1"), state),
        ("unreduced_state_exact_value", lambda r, _p: (
            edit_cell(r, "initial_states.csv", lambda row: True, "xx_exact_num",
                      lambda value: str(int(value) * 2)),
            edit_cell(r, "initial_states.csv", lambda row: True, "xx_exact_den",
                      lambda value: str(int(value) * 2))), state),
        ("false_temporal_endpoint", lambda r, _p: mutate_canonical_endpoint(r, context),
         lambda r, _p: endpoint_replay(r, context)),
        ("absolute_position_conversion_masquerade", lambda r, _p: edit_cell(
            r, "force_audit.csv", first_force, "causal_offset_raw_hash", "0" * 64), short),
        ("false_force_length", lambda r, _p: edit_cell(
            r, "force_audit.csv", first_force, "length_bits", lambda value: str(int(value) + 1)), short),
        ("false_force_residual", lambda r, _p: edit_cell(
            r, "force_audit.csv", first_force, "pair_momentum_residual_raw_x_dyadic", "0x1@0"), short),
        ("omitted_long_force_observer", lambda r, _p: edit_cell(
            r, "force_audit.csv", first_long, "relation_angular_residual_raw_x_dyadic", ""), long_audit),
        ("reordered_or_fused_operation", lambda r, _p: edit_cell(
            r, "operation_counts.csv", first_operation, "observed_categories",
            lambda value: value.replace("drift_constant_conversion", "fused_drift", 1)), short),
        ("false_operation_total", lambda r, _p: edit_cell(
            r, "operation_counts.csv", first_operation, "total_observed",
            lambda value: str(int(value) - 1)), short),
        ("false_inexact_count", lambda r, _p: edit_cell(
            r, "operation_counts.csv", first_operation, "inexact_total",
            lambda value: str(int(value) + 1)), short),
        ("false_rounding_audit", lambda r, _p: edit_cell(
            r, "operation_counts.csv", first_operation, "rounding_audit_sha256",
            "0" * 64), short),
        ("false_invariant_residual", lambda r, _p: edit_cell(
            r, "invariants.csv", first_invariant, "delta_momentum_raw_x_dyadic", "0x1@0"), short),
        ("omitted_long_invariant_observer", lambda r, _p: edit_cell(
            r, "invariants.csv", first_long, "delta_angular_raw_x_dyadic", ""), long_audit),
        ("false_transformed_absolute_angular", lambda r, _p: edit_cell(
            r, "invariants.csv", first_auxiliary, "angular_raw_x_dyadic", "0x1@0"),
         auxiliary_audit),
        ("false_transformed_centrality", lambda r, _p: edit_cell(
            r, "force_audit.csv", first_auxiliary,
            "stored_impulse_centrality_residual_raw_x_dyadic", "0x1@0"),
         auxiliary_audit),
        ("false_representation_error", lambda r, _p: edit_cell(
            r, "representation_error.csv", lambda row: row["scenario_id"] == "k4_breathing"
            and row["precision"] == "256" and row["scope"] == "short" and row["sample"] == "0",
            "position_raw_error_num", "1"), representation),
        ("false_energy_trace", lambda r, _p: edit_cell(
            r, "long_energy.csv", lambda row: row["precision"] == "64"
            and row["level"] == "0" and row["sample"] == "0",
            "mechanical_num", lambda value: str(int(value) + 1)), long_energy),
        ("false_reversal", lambda r, _p: edit_cell(
            r, "reversibility.csv", lambda row: row["scenario_id"] == "k4_breathing"
            and row["precision"] == "64" and row["level"] == "0",
            "complete_state_identical", lambda value: "false" if value == "true" else "true"), reversal),
        ("false_frame_error", lambda r, _p: edit_cell(
            r, "covariance.csv", lambda row: row["kind"] == "galilean_boost",
            "relative_position_physical_num", lambda value: str(int(value) + 1)), covariance),
        ("non_atomic_domain", lambda r, _p: edit_cell(
            r, "domain.csv", lambda row: row["precision"] == "64" and row["level"] == "0",
            "event_rows_emitted", "1"), domain),
        ("false_domain_scratch", lambda r, _p: edit_cell(
            r, "domain.csv", lambda row: row["precision"] == "64" and row["level"] == "0",
            "domain_scratch_observed_bits", lambda value: str(int(value) + 1)), domain),
        ("false_atomic_energy_observer", lambda r, _p: edit_cell(
            r, "domain.csv", lambda row: row["precision"] == "64" and row["level"] == "0",
            "returned_energy_observation_sha256", "0" * 64), domain),
        ("hidden_causal_cache", lambda r, _p: edit_cell(
            r, "state_size.csv", lambda row: True, "causal_cache_bytes", "1"), size),
        ("false_fixed_state_size", lambda r, _p: edit_cell(
            r, "state_size.csv", lambda row: True, "state_bytes",
            lambda value: str(int(value) + 1)), size),
        ("checkpoint_replay", lambda r, _p: edit_cell(
            r, "checkpoint.csv", lambda row: row["precision"] == "64" and row["level"] == "0",
            "event_suffix_identical", "false"),
         checkpoint),
        ("checkpoint_event_digest", lambda r, _p: edit_cell(
            r, "checkpoint.csv", lambda row: row["precision"] == "64" and row["level"] == "0",
            "whole_suffix_event_sha256", "0" * 64), checkpoint),
        ("false_exact_comparator_receipt", lambda r, _p: edit_cell(
            r, "rational_comparator.csv", lambda row: row["scenario_id"] == "k4_internal"
            and row["level"] == "0", "last_comparator_state_hash", "0" * 64), comparator),
        ("hidden_state_column", lambda r, _p: add_hidden_column(r), schema),
    ]

    detected = 0
    failures = (
        OSError, ValueError, ArithmeticError, IndexError, KeyError, StopIteration,
        oracle.OracleError, oracle.parent.OracleError, oracle.foundation.OracleError,
    )
    with tempfile.TemporaryDirectory(prefix="mls-bounded-phase-mutations-") as directory:
        root = Path(directory)
        for index, (name, mutation, detector) in enumerate(cases):
            candidate = root / f"{index:02d}-{name}" / "raw"
            parent_candidate = root / f"{index:02d}-{name}" / "parent"
            overlay(arguments.raw, candidate)
            overlay(arguments.parent_raw, parent_candidate)
            mutation(candidate, parent_candidate)
            try:
                detector(candidate, parent_candidate)
            except failures:
                detected += 1
            else:
                raise RuntimeError(f"semantic mutation was not detected: {name}")
            shutil.rmtree(candidate.parent)

    print(
        "BOUNDED FRACTIONAL PHASE STATE ORACLE MUTATIONS: "
        f"PASS (2 deterministic positives, 1 analytic-bound negative, {detected} mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
