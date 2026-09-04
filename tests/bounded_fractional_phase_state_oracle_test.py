#!/usr/bin/env python3
"""Deterministic positives and semantic mutations for the bounded oracle.

The final oracle replay is intentionally large.  This regression exercises two
independent deterministic one-step positives, then routes each mutation to the
smallest production verifier that owns its contract.  No mutation is accepted
merely because a file digest changed.
"""

from __future__ import annotations

import argparse
import copy
import csv
import importlib.util
import io
import os
import random
import shutil
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Callable


Detector = Callable[[Path, Path], None]
Mutation = Callable[[Path, Path], None]


class _RecordingCsvLines:
    """Expose logical CSV input while retaining each record's source text."""

    def __init__(self, stream) -> None:
        self.stream = stream
        self.consumed: list[str] = []

    def __iter__(self):
        return self

    def __next__(self) -> str:
        line = self.stream.readline()
        if line == "":
            raise StopIteration
        self.consumed.append(line)
        return line

    def take(self) -> str:
        result = "".join(self.consumed)
        self.consumed.clear()
        return result


def _copy_exact_prefix(source, destination, length: int) -> None:
    remaining = length
    while remaining:
        block = source.read(min(remaining, 8 * 1024 * 1024))
        if not block:
            raise RuntimeError("mutation source ended inside the target prefix")
        destination.write(block)
        remaining -= len(block)


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
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.mutation-",
        suffix=".tmp",
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    changed = False
    try:
        # The mutation overlays are symlinks to immutable source evidence.  Read
        # through the link and atomically replace only that link after a target
        # is found.  Once the first matching logical RFC 4180 record has been
        # parsed, preserve the complete untouched prefix and suffix byte for
        # byte.  This avoids parsing and reserializing the remaining 1.4 GB
        # force audit without weakening the mutation to a truncated fixture.
        target_start = 0
        target_end = 0
        replacement = b""
        with path.open(newline="", encoding="utf-8") as source:
            lines = _RecordingCsvLines(source)
            reader = csv.reader(lines)
            fields = next(reader, None)
            byte_offset = len(lines.take().encode("utf-8"))
            if fields is not None:
                for values in reader:
                    original = lines.take()
                    record_start = byte_offset
                    byte_offset += len(original.encode("utf-8"))
                    if len(values) != len(fields):
                        raise RuntimeError(f"mutation row width differs: {filename}")
                    row = dict(zip(fields, values, strict=True))
                    if predicate(row):
                        if column not in row:
                            raise RuntimeError(
                                f"mutation column absent: {filename}/{column}"
                            )
                        row[column] = value(row[column]) if callable(value) else value
                        encoded = io.StringIO(newline="")
                        csv.DictWriter(
                            encoded, fieldnames=fields, lineterminator="\n"
                        ).writerow(row)
                        target_start = record_start
                        target_end = byte_offset
                        replacement = encoded.getvalue().encode("utf-8")
                        changed = True
                        break
        if not changed:
            raise RuntimeError(f"mutation target absent: {filename}/{column}")
        with (
            path.open("rb") as source,
            temporary.open("wb") as destination,
        ):
            _copy_exact_prefix(source, destination, target_start)
            destination.write(replacement)
            source.seek(target_end)
            shutil.copyfileobj(source, destination, length=8 * 1024 * 1024)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def streaming_edit_cell_positive() -> None:
    """Exercise byte equivalence, symlink isolation, and atomic failure."""
    with tempfile.TemporaryDirectory(prefix="mls-streaming-csv-positive-") as directory:
        root = Path(directory)
        source = root / "source.csv"
        mutation = root / "mutation"
        absent = root / "absent"
        golden = root / "golden.csv"
        mutation.mkdir()
        absent.mkdir()
        rows = [
            {"key": "first", "value": "comma,value", "detail": "unchanged"},
            {
                "key": "second",
                "value": "quoted \"value\"\ncontinued",
                "detail": "target",
            },
            {"key": "third", "value": "3", "detail": "tail\nrecord"},
        ]
        with source.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=("key", "value", "detail"), lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
        original = source.read_bytes()
        (mutation / "sample.csv").symlink_to(source)
        (absent / "sample.csv").symlink_to(source)

        # This is the former whole-file implementation retained locally as a
        # golden byte oracle for the optimized record splice.
        with (
            source.open(newline="", encoding="utf-8") as input_stream,
            golden.open("w", newline="", encoding="utf-8") as output_stream,
        ):
            reader = csv.DictReader(input_stream)
            fields = list(reader.fieldnames or [])
            writer = csv.DictWriter(
                output_stream, fieldnames=fields, lineterminator="\n"
            )
            writer.writeheader()
            changed = False
            for row in reader:
                if not changed and row["key"] == "second":
                    row["value"] = f"{row['value']}-changed"
                    changed = True
                writer.writerow(row)
        if not changed:
            raise RuntimeError("golden streaming mutation target absent")

        edit_cell(
            mutation, "sample.csv", lambda row: row["key"] == "second",
            "value", lambda current: f"{current}-changed",
        )
        if source.read_bytes() != original:
            raise RuntimeError("streaming mutation changed its symlink source")
        if (mutation / "sample.csv").is_symlink():
            raise RuntimeError("streaming mutation did not replace its overlay link")
        if (mutation / "sample.csv").read_bytes() != golden.read_bytes():
            raise RuntimeError("streaming mutation differs from whole-file golden bytes")

        before_failed_mutation = (mutation / "sample.csv").read_bytes()
        try:
            edit_cell(
                mutation, "sample.csv", lambda row: row["key"] == "absent",
                "value", "unreachable",
            )
        except RuntimeError as error:
            if "mutation target absent" not in str(error):
                raise
        else:
            raise RuntimeError("missing streaming mutation target was accepted")
        if (mutation / "sample.csv").read_bytes() != before_failed_mutation:
            raise RuntimeError("failed streaming mutation replaced its input")
        if list(mutation.glob(".sample.csv.mutation-*.tmp")):
            raise RuntimeError("streaming mutation left a temporary file")

        try:
            edit_cell(
                absent, "sample.csv", lambda row: row["key"] == "absent",
                "value", "unreachable",
            )
        except RuntimeError as error:
            if "mutation target absent" not in str(error):
                raise
        else:
            raise RuntimeError("missing symlink-overlay mutation target was accepted")
        if not (absent / "sample.csv").is_symlink():
            raise RuntimeError("failed mutation replaced its symlink overlay")
        if source.read_bytes() != original:
            raise RuntimeError("failed mutation changed its symlink source")
        if list(absent.glob(".sample.csv.mutation-*.tmp")):
            raise RuntimeError("failed symlink mutation left a temporary file")


def perturb_compact_dyadic(value: str):
    return oracle.canonical_dyadic_text(
        oracle.parse_dyadic_text(value) + oracle.Fraction(1, 2**1000)
    )


def flip_sha256(value: str) -> str:
    if len(value) != 64:
        raise RuntimeError("mutation target is not SHA-256 text")
    return ("0" if value[0] != "0" else "1") + value[1:]


def rewrite_csv(root: Path, filename: str, content: list[dict[str, str]]) -> None:
    path = root / filename
    with path.open(newline="", encoding="utf-8") as stream:
        fields = list(csv.DictReader(stream).fieldnames or [])
    if path.is_symlink():
        path.unlink()
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(content)


def duplicate_small_table_key(
    root: Path, filename: str, key_fields: tuple[str, ...],
) -> None:
    content = oracle.rows(root / filename)
    if len(content) < 2:
        raise RuntimeError(f"{filename} row inventory is too small")
    for field in key_fields:
        content[1][field] = content[0][field]
    rewrite_csv(root, filename, content)


def reorder_small_table(root: Path, filename: str) -> None:
    content = oracle.rows(root / filename)
    if len(content) < 2:
        raise RuntimeError(f"{filename} row inventory is too small")
    content[0], content[1] = content[1], content[0]
    rewrite_csv(root, filename, content)


def delete_small_table_row(root: Path, filename: str) -> None:
    content = oracle.rows(root / filename)
    if not content:
        raise RuntimeError(f"{filename} row inventory is empty")
    del content[0]
    rewrite_csv(root, filename, content)


def reorder_comparator_rows(root: Path) -> None:
    content = oracle.rows(root / "rational_comparator.csv")
    if len(content) < 2:
        raise RuntimeError("rational comparator row inventory is too small")
    content[0], content[1] = content[1], content[0]
    rewrite_csv(root, "rational_comparator.csv", content)


def representation_scope_rows(root: Path, scope: str) -> tuple[list[dict[str, str]], list[int]]:
    content = oracle.rows(root / "representation_error.csv")
    indices = [index for index, row in enumerate(content) if row["scope"] == scope]
    if not indices:
        raise RuntimeError(f"representation scope absent: {scope}")
    return content, indices


def positional_index(indices: list[int], position: str) -> int:
    if position == "first":
        return indices[0]
    if position == "middle":
        return indices[len(indices) // 2]
    if position == "last":
        return indices[-1]
    raise RuntimeError(f"unknown row position {position!r}")


def delete_representation_row(root: Path, scope: str, position: str) -> None:
    content, indices = representation_scope_rows(root, scope)
    del content[positional_index(indices, position)]
    rewrite_csv(root, "representation_error.csv", content)


def duplicate_representation_row(root: Path, scope: str, position: str) -> None:
    content, indices = representation_scope_rows(root, scope)
    index = positional_index(indices, position)
    content.insert(index + 1, dict(content[index]))
    rewrite_csv(root, "representation_error.csv", content)


def reorder_representation_rows(root: Path, scope: str, position: str) -> None:
    content, indices = representation_scope_rows(root, scope)
    index = positional_index(indices, position)
    neighbor = index + 1 if index < indices[-1] else index - 1
    content[index], content[neighbor] = content[neighbor], content[index]
    rewrite_csv(root, "representation_error.csv", content)


def mutate_representation_identity(root: Path, scope: str, position: str) -> None:
    content, indices = representation_scope_rows(root, scope)
    index = positional_index(indices, position)
    content[index]["sample"] = str(int(content[index]["sample"]) + 1)
    rewrite_csv(root, "representation_error.csv", content)


def transplant_representation_commitment(root: Path) -> None:
    content, indices = representation_scope_rows(root, "short")
    target = next(
        index for index in indices
        if content[index]["scenario_id"] == "k4_breathing"
        and content[index]["path"] == oracle.CONTROL
        and content[index]["precision"] == "64"
        and content[index]["level"] == "0"
        and content[index]["sample"] == "1"
    )
    donor = next(
        index for index in indices
        if content[index]["scenario_id"] == "k4_breathing"
        and content[index]["path"] == oracle.CONTROL
        and content[index]["precision"] == "64"
        and content[index]["level"] == "0"
        if content[index]["exact_errors_sha256"] != content[target]["exact_errors_sha256"]
    )
    content[target]["exact_errors_sha256"] = content[donor]["exact_errors_sha256"]
    rewrite_csv(root, "representation_error.csv", content)


def alter_representation_display(root: Path) -> None:
    content, indices = representation_scope_rows(root, "short")
    target = next(
        index for index in indices
        if content[index]["scenario_id"] == "k4_breathing"
        and content[index]["path"] == oracle.CONTROL
        and content[index]["precision"] == "64"
        and content[index]["level"] == "0"
        and content[index]["sample"] == "1"
    )
    field = "position_raw_error_display"
    content[target][field] = (
        "0x8000000000000000@-999" if content[target][field] == "0" else "0"
    )
    rewrite_csv(root, "representation_error.csv", content)


def display_fraction(value: str):
    if value == "0":
        return oracle.Fraction()
    sign = -1 if value.startswith("-") else 1
    unsigned = value[1:] if sign < 0 else value
    significand, separator, exponent = unsigned.partition("@")
    if separator != "@" or not significand.startswith("0x"):
        raise RuntimeError("invalid bounded representation display")
    return sign * oracle.Fraction(int(significand[2:], 16)) * oracle.power_of_two(int(exponent))


def replace_with_display_rounded_commitment(root: Path) -> None:
    content, indices = representation_scope_rows(root, "short")
    for index in indices:
        row = content[index]
        if not (
            row["scenario_id"] == "k4_breathing"
            and row["path"] == oracle.CONTROL
            and row["precision"] == "64"
            and row["level"] == "0"
        ):
            continue
        approximate = tuple(
            display_fraction(row[f"{metric}_display"])
            for metric in oracle.REPRESENTATION_ERROR_METRICS
        )
        candidate = oracle.representation_error_commitment(row, *approximate)
        if candidate != row["exact_errors_sha256"]:
            row["exact_errors_sha256"] = candidate
            rewrite_csv(root, "representation_error.csv", content)
            return
    raise RuntimeError("no lossy representation display found")


def forge_zero_high_precision_representation_error(root: Path) -> None:
    """Forge a self-consistent zero-error receipt at B256 to fake scaling."""
    predicate = lambda row: (
        row["scope"] == "short"
        and row["scenario_id"] == "k4_breathing"
        and row["path"] == oracle.CONTROL
        and row["precision"] == "256"
        and row["level"] == "0"
        and row["sample"] == "1"
    )
    target = next(
        (row for row in oracle.iter_rows(root / "representation_error.csv")
         if predicate(row)),
        None,
    )
    if target is None:
        raise RuntimeError("high-precision representation mutation target absent")
    if all(target[f"{metric}_display"] == "0"
           for metric in oracle.REPRESENTATION_ERROR_METRICS):
        raise RuntimeError("high-precision representation target is already exact")
    false_commitment = oracle.representation_error_commitment(
        target, oracle.Fraction(), oracle.Fraction(), oracle.Fraction()
    )
    edit_cell(
        root, "representation_error.csv", predicate,
        "exact_errors_sha256", false_commitment,
    )
    for metric in oracle.REPRESENTATION_ERROR_METRICS:
        edit_cell(
            root, "representation_error.csv", predicate,
            f"{metric}_display", "0",
        )


def component_wire(sign: int, precision: int, exponent: int, significand: int) -> str:
    return (
        bytes((sign,))
        + precision.to_bytes(2, "little")
        + exponent.to_bytes(2, "little", signed=True)
        + significand.to_bytes(precision // 8, "big")
    ).hex()


def mutate_underflow_range_wire_state(root: Path) -> None:
    """Create a fully spelled out, normalized component below frozen emin."""
    predicate = lambda row: (
        row["precision"] == "64"
        and row["scenario_id"] == "domain_crossing"
        and row["packet_id"] == "1"
    )
    target = next(
        (row for row in oracle.iter_rows(root / "initial_states.csv")
         if predicate(row)),
        None,
    )
    if target is None:
        raise RuntimeError("underflow wire-state mutation target absent")
    precision = int(target["precision"])
    sign = int(target["xx_sign"])
    significand = int(target["xx_significand_hex"], 16)
    if not 2 ** (precision - 1) <= significand < 2**precision:
        raise RuntimeError("underflow mutation target is not normalized")
    exponent = oracle.MIN_EXPONENT - 1
    exact = oracle.Fraction(significand) * oracle.power_of_two(
        exponent - (precision - 1)
    )
    if sign:
        exact = -exact
    for column, value in (
        ("xx_E", str(exponent)),
        ("xx_wire_hex", component_wire(sign, precision, exponent, significand)),
        ("xx_exact_num", str(exact.numerator)),
        ("xx_exact_den", str(exact.denominator)),
    ):
        edit_cell(root, "initial_states.csv", predicate, column, value)


def mutate_noncanonical_significand_wire_state(root: Path) -> None:
    """Encode the same dyadic value with an unnormalized significand."""
    predicate = lambda row: (
        row["precision"] == "64"
        and row["scenario_id"] == "domain_crossing"
        and row["packet_id"] == "1"
    )
    target = next(
        (row for row in oracle.iter_rows(root / "initial_states.csv")
         if predicate(row)),
        None,
    )
    if target is None:
        raise RuntimeError("noncanonical wire-state mutation target absent")
    precision = int(target["precision"])
    sign = int(target["xx_sign"])
    exponent = int(target["xx_E"])
    significand = int(target["xx_significand_hex"], 16)
    if significand == 0 or significand % 2:
        raise RuntimeError("noncanonical significand target is not exactly shiftable")
    exponent += 1
    significand //= 2
    for column, value in (
        ("xx_E", str(exponent)),
        ("xx_significand_hex", format(significand, f"0{precision // 4}x")),
        ("xx_wire_hex", component_wire(sign, precision, exponent, significand)),
    ):
        edit_cell(root, "initial_states.csv", predicate, column, value)


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


def expected_representation_row(
    identity: dict[str, object], position_raw_error, momentum_raw_error, energy_error,
) -> dict[str, str]:
    result = {field: str(identity[field]) for field in oracle.REPRESENTATION_ERROR_IDENTITY_FIELDS}
    result["exact_errors_sha256"] = oracle.representation_error_commitment(
        identity, position_raw_error, momentum_raw_error, energy_error
    )
    for metric, exact in zip(
        oracle.REPRESENTATION_ERROR_METRICS,
        (position_raw_error, momentum_raw_error, energy_error),
    ):
        result[f"{metric}_display"] = oracle.bounded_fraction_display(exact)
    return result


def representation_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row[field] for field in oracle.REPRESENTATION_ERROR_IDENTITY_FIELDS[:7])


def verify_cached_representation_rows(
    raw: Path, expected: dict[tuple[str, ...], dict[str, str]],
) -> None:
    selected = {
        representation_key(row): row
        for row in oracle.iter_rows(raw / "representation_error.csv")
        if representation_key(row) in expected
    }
    oracle.require(set(selected) == set(expected),
                   "cached representation row inventory differs")
    for key, expected_row in expected.items():
        oracle.require(selected[key] == expected_row,
                       "cached independently replayed representation row differs")


def first_short_representation(
    raw: Path, parent_raw: Path, context: dict[str, object], precision: int = 64,
) -> dict[tuple[str, ...], dict[str, str]]:
    level = 0
    scenario = "k4_breathing"
    path = oracle.CONTROL
    model = context["models"]["k4"]
    bounded_initial = context["state_report"]["initial"][
        (precision, scenario, "initial", 0)
    ]
    parent_initial = oracle.grouped(
        oracle.rows(parent_raw / "initial_states.csv"), ("scenario_id",)
    )
    exact_initial = oracle.rational_from_parent_rows(parent_initial[(scenario,)])
    bounded = oracle.run_trajectory(
        model, bounded_initial, oracle.TIMESTEPS_RAW[level],
        oracle.STEP_COUNTS[level], path,
    )[0].samples
    exact = oracle.run_rational_trajectory(
        model, exact_initial, oracle.TIMESTEPS_RAW[level],
        oracle.STEP_COUNTS[level], path,
    )
    evidence = [
        row for row in oracle.iter_rows(raw / "representation_error.csv")
        if row["scenario_id"] == scenario and row["scope"] == "short"
        and row["path"] == path and row["precision"] == str(precision)
        and row["level"] == str(level)
    ]
    oracle.require(len(evidence) == len(bounded) == len(exact),
                   "first short representation inventory differs")
    expected_rows: dict[tuple[str, ...], dict[str, str]] = {}
    for sample, (row, candidate, control) in enumerate(zip(evidence, bounded, exact)):
        x_raw = oracle.bounded_rational_error(candidate, control)
        p_raw = oracle.bounded_rational_error(candidate, control, True)
        energy_error = (
            oracle.mechanical_energy(model, candidate)[2]
            - oracle.rational_energy(model, control)
        )
        identity = {
            "scenario_id": scenario,
            "scope": "short",
            "path": path,
            "precision": precision,
            "level": level,
            "dt_raw": oracle.TIMESTEPS_RAW[level],
            "sample": sample,
            "candidate_state_hash": oracle.phase_hash(candidate),
            "control_state_hash": oracle.rational_hash(control),
        }
        oracle.verify_representation_error_row(
            row, identity, x_raw, p_raw, energy_error
        )
        expected = expected_representation_row(identity, x_raw, p_raw, energy_error)
        expected_rows[representation_key(expected)] = expected
    return expected_rows


def display_alias_positive() -> None:
    identity = {
        "scenario_id": "display_alias_positive",
        "scope": "short",
        "path": oracle.KDK,
        "precision": 64,
        "level": 0,
        "dt_raw": oracle.TIMESTEPS_RAW[0],
        "sample": 0,
        "candidate_state_hash": "1" * 64,
        "control_state_hash": "2" * 64,
    }
    first = oracle.Fraction(1) + oracle.Fraction(1, 2**100)
    second = oracle.Fraction(1) + oracle.Fraction(1, 2**101)
    oracle.require(first != second, "display-alias values unexpectedly equal")
    oracle.require(
        oracle.bounded_fraction_display(first) == oracle.bounded_fraction_display(second),
        "display-alias positive did not alias at 64 display bits",
    )
    oracle.require(
        oracle.representation_error_commitment(identity, first, first, first)
        != oracle.representation_error_commitment(identity, second, first, first),
        "exact commitments failed to distinguish display aliases",
    )


def preregistered_scaling_semantics_positive() -> None:
    # Sections 7-8 require unit-roundoff scaling only until an envelope first
    # enters budget.  A later below-budget pair is not a structural failure
    # merely because it misses the unconditional B192/B256 diagnostic.
    budget = oracle.Fraction(1)
    below_budget = {
        64: oracle.Fraction(1, 2),
        96: oracle.Fraction(1, 3),
        128: oracle.Fraction(1, 4),
        192: oracle.Fraction(1, 5),
        256: oracle.Fraction(1, 6),
    }
    oracle.require(
        oracle.scaling_until_budget(below_budget, budget),
        "post-budget scaling semantics rejected a bounded envelope",
    )
    oracle.require(
        not oracle.unit_roundoff_pair_scales(
            below_budget[192], below_budget[256], 64
        ),
        "post-budget control unexpectedly obeyed unconditional pair scaling",
    )
    pre_budget_plateau = {
        64: oracle.Fraction(1),
        96: oracle.Fraction(1, 2),
        128: oracle.Fraction(1, 4),
        192: oracle.Fraction(1, 8),
        256: oracle.Fraction(1, 16),
    }
    oracle.require(
        not oracle.scaling_until_budget(pre_budget_plateau, oracle.Fraction(1, 1000)),
        "pre-budget precision plateau was accepted",
    )
    zero_reappears = dict(below_budget)
    zero_reappears[64] = oracle.Fraction()
    oracle.require(
        not oracle.scaling_until_budget(zero_reappears, budget),
        "exact-zero closure was not enforced",
    )
    qualitative, attained = oracle.timestep_contraction_profile(
        [oracle.Fraction(10), oracle.Fraction(5), oracle.Fraction(5),
         oracle.Fraction(5), oracle.Fraction(5)],
        oracle.Fraction(6),
    )
    oracle.require(
        qualitative and attained,
        "post-floor timestep plateau was rejected",
    )
    qualitative, attained = oracle.timestep_contraction_profile(
        [oracle.Fraction(10)] * len(oracle.LEVELS), oracle.Fraction(1),
    )
    oracle.require(
        not qualitative and not attained,
        "pre-floor timestep plateau was accepted",
    )

    anchor_good = {
        "position_maximum": {
            64: oracle.Fraction(1),
            96: oracle.Fraction(1, 2),
            128: oracle.Fraction(1, 4),
            192: oracle.Fraction(1, 2**10),
            256: oracle.Fraction(1, 2**75),
        }
    }
    anchor_budget = {"position_maximum": oracle.Fraction(1)}
    below_checks, pair_checks, qualified = oracle.qualify_exact_prefix_anchor(
        anchor_good, anchor_budget, True
    )
    oracle.require(all(below_checks.values()) and all(pair_checks.values()) and qualified,
                   "valid exact-prefix anchor failed")
    good_contract = (True, all(below_checks.values()), all(pair_checks.values()))

    anchor_bad_pair = {"position_maximum": dict(anchor_good["position_maximum"])}
    anchor_bad_pair["position_maximum"][256] = oracle.Fraction(1, 32)
    below_checks, pair_checks, qualified = oracle.qualify_exact_prefix_anchor(
        anchor_bad_pair, anchor_budget, True
    )
    oracle.require(all(below_checks.values()) and not all(pair_checks.values())
                   and not qualified, "bad anchor pair was accepted")
    bad_pair_contract = (True, all(below_checks.values()), all(pair_checks.values()))
    _below, _pair, not_applicable = oracle.qualify_exact_prefix_anchor(
        anchor_bad_pair, anchor_budget, False
    )
    oracle.require(not_applicable, "comparator-complete prefix required an anchor")

    anchor_bad_budget = {"position_maximum": dict(anchor_good["position_maximum"])}
    anchor_bad_budget["position_maximum"][192] = oracle.Fraction(2**62)
    anchor_bad_budget["position_maximum"][256] = oracle.Fraction(1, 8)
    below_checks, pair_checks, qualified = oracle.qualify_exact_prefix_anchor(
        anchor_bad_budget, anchor_budget, True
    )
    oracle.require(not all(below_checks.values()) and all(pair_checks.values())
                   and not qualified, "over-budget anchor was accepted")
    bad_budget_contract = (True, all(below_checks.values()), all(pair_checks.values()))

    budget_pass, scaling_pass, aggregate_pass = (
        oracle.aggregate_required_anchor_contracts(
            [good_contract, bad_pair_contract, (False, False, False)]
        )
    )
    oracle.require(budget_pass and not scaling_pass and not aggregate_pass,
                   "one scenario masked another scenario's failed anchor")
    decision, selected = oracle.scientific_disposition(
        oracle.PARENT_DECISION, True, scaling_pass, None
    )
    oracle.require(
        decision == "bounded_phase_state_restores_dynamics_but_structure_residuals_unresolved"
        and selected is None,
        "anchor-scaling failure routed to the wrong disposition",
    )
    budget_pass, scaling_pass, aggregate_pass = (
        oracle.aggregate_required_anchor_contracts(
            [good_contract, bad_budget_contract, (False, False, False)]
        )
    )
    oracle.require(not budget_pass and scaling_pass and not aggregate_pass,
                   "budget-only anchor failure was misclassified")
    decision, selected = oracle.scientific_disposition(
        oracle.PARENT_DECISION, True, scaling_pass, None
    )
    oracle.require(
        decision == "bounded_phase_state_converges_but_required_precision_unresolved"
        and selected is None,
        "anchor-budget failure routed to the wrong disposition",
    )

    all_pass = {precision: True for precision in oracle.PRECISIONS}
    scenario_controls = {
        precision: {scenario: True for scenario in oracle.SCENARIOS}
        for precision in oracle.PRECISIONS
    }
    scenario_controls[64][oracle.SCENARIOS[0]] = False
    control_by_precision = oracle.aggregate_precision_scenario_gate(
        scenario_controls
    )
    eligibility = oracle.combine_precision_eligibility(
        (all_pass, control_by_precision), (True,),
    )
    oracle.require(
        not eligibility[64]
        and all(eligibility[precision] for precision in oracle.PRECISIONS[1:]),
        "low-precision control failure leaked into higher-precision eligibility",
    )
    shared_failure = oracle.combine_precision_eligibility(
        (all_pass, control_by_precision), (False,),
    )
    oracle.require(
        not any(shared_failure.values()),
        "shared precision gate did not disqualify every precision",
    )

    decision_cases = (
        (
            "wrong_parent", True, True, 96,
            "stop_inconclusive_or_wrong_parent", None,
        ),
        (
            oracle.PARENT_DECISION, False, True, 96,
            "reject_bounded_binary_fractional_phase_state", None,
        ),
        (
            oracle.PARENT_DECISION, True, False, 96,
            "bounded_phase_state_restores_dynamics_but_structure_residuals_unresolved",
            None,
        ),
        (
            oracle.PARENT_DECISION, True, True, 96,
            "retain_bounded_variable_exponent_phase_state_for_research", 96,
        ),
    )
    for parent, dynamics, structure, candidate, expected_decision, expected_precision \
            in decision_cases:
        decision, selected = oracle.scientific_disposition(
            parent, dynamics, structure, candidate
        )
        oracle.require(
            decision == expected_decision and selected == expected_precision,
            "scientific decision branch differs",
        )

    completed = {
        "decision": oracle.FINAL_DECISION,
        "selected_precision": oracle.FINAL_SELECTED_PRECISION,
        "highest_precision_dynamics_pass": True,
        "structure_residuals_resolved": False,
        "precision_eligibility": {
            str(precision): False for precision in oracle.PRECISIONS
        },
    }
    oracle.require_final_outcome(completed)
    final_outcome_mutations = (
        ("decision", "bounded_phase_state_converges_but_required_precision_unresolved"),
        ("selected_precision", 96),
        ("highest_precision_dynamics_pass", False),
        ("structure_residuals_resolved", True),
    )
    for field, value in final_outcome_mutations:
        altered = copy.deepcopy(completed)
        altered[field] = value
        try:
            oracle.require_final_outcome(altered)
        except oracle.OracleError:
            pass
        else:
            raise RuntimeError(f"completed outcome accepted changed {field}")
    altered = copy.deepcopy(completed)
    altered["precision_eligibility"]["256"] = True
    try:
        oracle.require_final_outcome(altered)
    except oracle.OracleError:
        pass
    else:
        raise RuntimeError("completed outcome accepted an eligible precision")


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


def transplant_coarser_temporal_endpoint(root: Path) -> None:
    """Replace the finest endpoint by the coarser result without breaking wire form."""
    content = oracle.rows(root / "endpoints.csv")
    common = lambda row: (
        row["precision"] == "256"
        and row["scenario_id"] == "k4_internal"
        and row["path"] == oracle.KDK
    )
    targets = [row for row in content if common(row) and row["level"] == "4"]
    donors = {
        row["packet_id"]: row
        for row in content if common(row) and row["level"] == "3"
    }
    if not targets or set(donors) != {row["packet_id"] for row in targets}:
        raise RuntimeError("temporal endpoint transplant inventory differs")
    component_fields = [
        f"{prefix}_{suffix}"
        for prefix in oracle.COMPONENT_PREFIXES
        for suffix in ("sign", "E", "significand_hex", "wire_hex", "exact_num", "exact_den")
    ]
    for target in targets:
        donor = donors[target["packet_id"]]
        target["state_hash"] = donor["state_hash"]
        for field in component_fields:
            target[field] = donor[field]
    rewrite_csv(root, "endpoints.csv", content)


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


def analytic_phase_certificate_semantics(
    raw: Path, context: dict[str, object], parent_raw: Path,
) -> None:
    """Exercise paired phase certificates and their fail-closed prerequisites."""
    precision = 96
    level = 0
    steps = oracle.STEP_COUNTS[level]
    interval = oracle.TIMESTEPS_RAW[level]
    initial = context["state_report"]["initial"]
    model = context["models"]["k4"]
    baseline, baseline_stages, baseline_forces = oracle.run_trajectory(
        model, initial[(precision, "k4_internal", "initial", 0)],
        interval, steps, oracle.KDK, True,
    )
    boosted, boosted_stages, boosted_forces = oracle.run_trajectory(
        model, initial[(precision, "k4_boosted", "initial", 0)],
        interval, steps, oracle.KDK, True,
    )
    frame = oracle.paired_frame_bound_certificate(
        baseline, baseline_stages, baseline_forces,
        boosted, boosted_stages, boosted_forces, interval,
    )
    oracle.require(bool(frame["passed"]), "valid paired frame certificate failed")

    compact_baseline_forces = oracle.compact_long_force_trace(baseline_forces)
    compact_boosted_forces = oracle.compact_long_force_trace(boosted_forces)
    oracle.require(
        all(
            tuple(audit) == oracle.LONG_FORCE_CERTIFICATE_FIELDS
            for _step, _stage, audit in (
                compact_baseline_forces + compact_boosted_forces
            )
        ),
        "long force certificate compaction retained the wrong fields",
    )
    compact_frame = oracle.paired_frame_bound_certificate(
        baseline, baseline_stages, compact_baseline_forces,
        boosted, boosted_stages, compact_boosted_forces, interval,
    )
    oracle.require(
        compact_frame == frame,
        "compact/full paired frame certificates differ",
    )

    missing_source = copy.deepcopy(baseline_forces[:1])
    del missing_source[0][2][oracle.LONG_FORCE_CERTIFICATE_FIELDS[-1]]
    try:
        oracle.compact_long_force_trace(missing_source)
    except oracle.OracleError:
        pass
    else:
        raise RuntimeError("long force compaction accepted a missing causal field")

    backward, backward_stages, backward_forces = oracle.run_trajectory(
        model, baseline.final, -interval, steps, oracle.KDK, True,
    )
    reversal = oracle.paired_reversal_bound_certificate(
        baseline, baseline_stages, baseline_forces,
        backward, backward_stages, backward_forces, interval,
    )
    oracle.require(bool(reversal["passed"]), "valid paired reversal certificate failed")

    # The full verifier must reuse the already verified short and auxiliary
    # traces for checkpoint/event comparison.  Exercise that path with a
    # sentinel that rejects any accidental fourth trajectory replay.
    half = steps // 2
    checkpoint = context["state_report"]["checkpoint"][
        (precision, "k4_internal", oracle.KDK, level)
    ]
    first, first_stages, first_forces = oracle.run_trajectory(
        model, baseline.initial, interval, half, oracle.KDK, True,
    )
    resumed, resumed_stages, resumed_forces = oracle.run_trajectory(
        model, checkpoint, interval, half, oracle.KDK, True,
    )
    first_id = f"checkpoint:first:B{precision}:L{level}"
    resumed_id = f"checkpoint:resumed:B{precision}:L{level}"
    auxiliary = {
        first_id: (
            first, first_stages, first_forces,
        ),
        resumed_id: (
            resumed, resumed_stages, resumed_forces,
        ),
    }
    operation_rows = {
        row["trajectory_id"]: row for row in oracle.rows(raw / "operation_counts.csv")
    }
    checkpoint_row = next(
        row for row in oracle.rows(raw / "checkpoint.csv")
        if row["precision"] == str(precision) and row["level"] == str(level)
    )
    run_trajectory = oracle.run_trajectory

    def unexpected_replay(*_arguments, **_keywords):
        raise RuntimeError("cached checkpoint path replayed a trajectory")

    oracle.run_trajectory = unexpected_replay
    try:
        oracle.verify_checkpoint_row(
            checkpoint_row, precision, level, model, baseline.initial, checkpoint,
            baseline, operation_rows, (baseline_stages, baseline_forces), auxiliary,
        )

        def require_corrupt_cache_rejected(
            name: str, cached_whole, cached_auxiliary,
        ) -> None:
            try:
                oracle.verify_checkpoint_row(
                    checkpoint_row, precision, level, model,
                    baseline.initial, checkpoint, cached_whole, operation_rows,
                    (baseline_stages, baseline_forces), cached_auxiliary,
                )
            except oracle.OracleError:
                return
            raise RuntimeError(f"corrupt checkpoint cache was accepted: {name}")

        corrupted = copy.deepcopy(auxiliary)
        corrupted[first_id][0].initial.time_raw += 1
        require_corrupt_cache_rejected("first initial", baseline, corrupted)

        corrupted = copy.deepcopy(auxiliary)
        corrupted[first_id][0].final.packets[0].x[0] += oracle.Fraction(1)
        require_corrupt_cache_rejected("first final", baseline, corrupted)

        corrupted = copy.deepcopy(auxiliary)
        corrupted[resumed_id][0].initial.packets[0].p[0] += oracle.Fraction(1)
        require_corrupt_cache_rejected("resumed initial", baseline, corrupted)

        corrupted = copy.deepcopy(auxiliary)
        corrupted[resumed_id][0].final.packets[0].x[0] += oracle.Fraction(1)
        require_corrupt_cache_rejected("resumed final", baseline, corrupted)

        # Preserve endpoint associations while corrupting the cached terminal
        # time, so this negative reaches the explicit time-chain check rather
        # than relying on a phase-state mismatch.
        wrong_time_whole = copy.deepcopy(baseline)
        wrong_time_auxiliary = copy.deepcopy(auxiliary)
        wrong_time_whole.final.time_raw += 1
        wrong_time_auxiliary[resumed_id][0].final.time_raw += 1
        require_corrupt_cache_rejected(
            "whole/resumed final time", wrong_time_whole, wrong_time_auxiliary,
        )
    finally:
        oracle.run_trajectory = run_trajectory

    parent_initial = oracle.grouped(
        oracle.rows(parent_raw / "initial_states.csv"), ("scenario_id",)
    )
    exact_initial = oracle.rational_from_parent_rows(parent_initial[("k4_internal",)])
    exact_samples, exact_traces, _exact_evaluations = (
        oracle.run_rational_trajectory_with_traces(
            model, exact_initial, interval, 1, oracle.KDK,
        )
    )
    bounded_stage_map = oracle.indexed_stage_trace(baseline_stages)
    bounded_force_map = oracle.grouped_force_trace(baseline_forces)
    x_radius, p_radius = oracle.zero_phase_radii(baseline.initial)
    initial_contained, _x_error, _p_error = oracle.bounded_rational_state_containment(
        baseline.initial, exact_samples[0], x_radius, p_radius,
    )
    oracle.require(initial_contained, "B96/Q initial state certificate failed")
    exact_stages, exact_forces = exact_traces[0]
    x_radius, p_radius, step_passed, paired = (
        oracle.advance_bounded_rational_step_bound(
            bounded_stage_map, bounded_force_map, 1, exact_samples[0],
            exact_stages, exact_forces, interval, oracle.KDK,
            x_radius, p_radius,
        )
    )
    oracle.require(step_passed and paired == 2 * len(model.relations),
                   "B96/Q one-step phase recurrence failed")
    compact_bounded_force_map = oracle.grouped_force_trace(
        compact_baseline_forces
    )
    compact_recurrence = oracle.advance_bounded_rational_step_bound(
        bounded_stage_map, compact_bounded_force_map, 1, exact_samples[0],
        exact_stages, exact_forces, interval, oracle.KDK,
        *oracle.zero_phase_radii(baseline.initial),
    )
    oracle.require(
        compact_recurrence == (x_radius, p_radius, step_passed, paired),
        "compact/full bounded-rational recurrence certificates differ",
    )
    bounded_energy = oracle.mechanical_energy(model, baseline.samples[1])[2]
    exact_energy = oracle.rational_energy(model, exact_samples[1])
    energy_radius = oracle.kinetic_difference_radius_bound(
        baseline.samples[1], exact_samples[1], p_radius,
    )
    bounded_potential = oracle.mechanical_energy(model, baseline.samples[1])[1]
    exact_potential = oracle.rational_force_and_energy(model, exact_samples[1])[1]
    oracle.require(
        bounded_potential == exact_potential
        and abs(bounded_energy - exact_energy) <= energy_radius,
        "B96/Q one-step representation-energy certificate failed",
    )

    scalar_mutation = copy.deepcopy(boosted_forces)
    scalar_mutation[0][2]["conjugate_bits"] = (
        int(scalar_mutation[0][2]["conjugate_bits"]) + 1
    )
    oracle.require(
        not oracle.paired_frame_bound_certificate(
            baseline, baseline_stages, baseline_forces,
            boosted, boosted_stages, scalar_mutation, interval,
        )["passed"],
        "paired frame certificate accepted a force-scalar mismatch",
    )

    omitted_sources = copy.deepcopy(boosted_forces)
    zero = (oracle.Fraction(), oracle.Fraction(), oracle.Fraction())
    for _step, _stage, audit in omitted_sources:
        for name in (
            "relative_subtraction_bounds", "impulse_component_bounds",
            "first_endpoint_bounds", "second_endpoint_bounds",
        ):
            audit[name] = zero
    oracle.require(
        not oracle.paired_frame_bound_certificate(
            baseline, baseline_stages, baseline_forces,
            boosted, boosted_stages, omitted_sources, interval,
        )["passed"],
        "paired frame certificate accepted omitted local half-ULP sources",
    )

    time_mutation = copy.deepcopy(backward_stages)
    time_mutation[-1][2].time_raw += 1
    oracle.require(
        not oracle.paired_reversal_bound_certificate(
            baseline, baseline_stages, baseline_forces,
            backward, time_mutation, backward_forces, interval,
        )["passed"],
        "paired reversal certificate accepted an incorrect recovered time",
    )

    rotated, rotated_stages, rotated_forces = oracle.run_trajectory(
        context["models"]["k4_rotated"],
        initial[(precision, "k4_rotated", "initial", 0)],
        interval, steps, oracle.KDK, True,
    )
    del rotated
    rotation = oracle.exact_discrete_equivariance_certificate(
        baseline_stages, baseline_forces, rotated_stages, rotated_forces, True,
    )
    oracle.require(bool(rotation["passed"]),
                   "valid signed-lattice-rotation certificate failed")
    primitive_mutation = copy.deepcopy(rotated_forces)
    impulse = primitive_mutation[0][2]["rounded_impulse"]
    primitive_mutation[0][2]["rounded_impulse"] = (
        impulse[0] + oracle.Fraction(1, 2**96), impulse[1], impulse[2]
    )
    oracle.require(
        not oracle.exact_discrete_equivariance_certificate(
            baseline_stages, baseline_forces,
            rotated_stages, primitive_mutation, True,
        )["passed"],
        "rotation certificate accepted a changed force primitive",
    )

    permuted_initial = initial[(precision, "k4_internal", "initial", 0)].clone()
    permuted_initial.packets.reverse()
    _permuted, permuted_stages, permuted_forces = oracle.run_trajectory(
        model, permuted_initial, interval, steps, oracle.KDK, True,
    )
    permutation = oracle.exact_discrete_equivariance_certificate(
        baseline_stages, baseline_forces,
        permuted_stages, permuted_forces, False,
    )
    oracle.require(bool(permutation["passed"]),
                   "valid packet-permutation certificate failed")

    exact_radius = oracle.Fraction(2**300 + 1, 3)
    inward = oracle.inward_certificate_witness(exact_radius)
    oracle.require(
        oracle.Fraction() < inward <= exact_radius,
        "inward recurrence witness is not a lower witness",
    )
    residuals = [oracle.Fraction(), oracle.Fraction(1)]
    bounds = [oracle.Fraction(), oracle.Fraction()]
    oracle.require(
        abs(oracle.least_squares_slope(residuals, oracle.Fraction(1)))
        > oracle.least_squares_absolute_bound(bounds, oracle.Fraction(1)),
        "undersized least-squares energy envelope was accepted",
    )


def optimization_equivalence_semantics(
    context: dict[str, object], parent_raw: Path,
) -> None:
    """Keep verifier caches exact and hot comparisons threshold-neutral."""
    def legacy_relation_is_safe(
        offset: tuple[oracle.Fraction, ...],
        reference: tuple[oracle.Fraction, ...],
    ) -> bool:
        reference_squared = oracle.dot(reference, reference)
        return (
            reference_squared > 0
            and oracle.dot(offset, offset)
                >= oracle.SAFE_SQUARED_RATIO * reference_squared
        )

    def legacy_chord_is_safe(
        initial: tuple[oracle.Fraction, ...],
        final: tuple[oracle.Fraction, ...],
        reference: tuple[oracle.Fraction, ...],
    ) -> bool:
        delta = oracle.vector_sub(final, initial)
        dd = oracle.dot(delta, delta)
        aa = oracle.dot(initial, initial)
        ad = oracle.dot(initial, delta)
        reference_squared = oracle.dot(reference, reference)
        oracle.require(reference_squared > 0, "zero reference relation")
        threshold = oracle.SAFE_SQUARED_RATIO * reference_squared
        if dd == 0 or ad >= 0:
            return aa >= threshold
        if ad <= -dd:
            return oracle.dot(final, final) >= threshold
        return aa * dd - ad * ad >= threshold * dd

    boundary_reference = (
        oracle.Fraction(2**24), oracle.Fraction(), oracle.Fraction(),
    )
    boundary = (oracle.Fraction(1), oracle.Fraction(), oracle.Fraction())
    below = (
        oracle.Fraction(2**80 - 1, 2**80),
        oracle.Fraction(), oracle.Fraction(),
    )
    crossing_first = (
        oracle.Fraction(-2), oracle.Fraction(), oracle.Fraction(),
    )
    crossing_last = (
        oracle.Fraction(2), oracle.Fraction(), oracle.Fraction(),
    )
    oracle.require(
        oracle._relation_component_safety_witness(
            boundary,
            oracle.SAFE_SQUARED_RATIO
            * oracle.dot(boundary_reference, boundary_reference),
        )
        and oracle.relation_is_safe(boundary, boundary_reference)
        and not oracle.relation_is_safe(below, boundary_reference)
        and not oracle._chord_component_safety_witness(
            crossing_first, crossing_last,
            oracle.SAFE_SQUARED_RATIO
            * oracle.dot(boundary_reference, boundary_reference),
        )
        and oracle._chord_component_safety_witness(
            boundary, (oracle.Fraction(2),) + boundary[1:],
            oracle.SAFE_SQUARED_RATIO
            * oracle.dot(boundary_reference, boundary_reference),
        )
        and oracle.chord_is_safe(
            boundary, (oracle.Fraction(2),) + boundary[1:],
            boundary_reference,
        )
        and not oracle.chord_is_safe(
            crossing_first, crossing_last, boundary_reference,
        ),
        "exact component witness changed a boundary or crossing chord",
    )

    generator = random.Random(0x4D4C535F51444F4D)
    for _case in range(512):
        def random_fraction() -> oracle.Fraction:
            numerator = generator.randint(-(2**96), 2**96)
            denominator = generator.randint(1, 2**48)
            return oracle.Fraction(numerator, denominator)

        reference = tuple(random_fraction() for _axis in range(3))
        if reference == (oracle.Fraction(),) * 3:
            reference = (oracle.Fraction(1),) + reference[1:]
        initial = tuple(random_fraction() for _axis in range(3))
        final = tuple(random_fraction() for _axis in range(3))
        oracle.require(
            oracle.relation_is_safe(initial, reference)
                == legacy_relation_is_safe(initial, reference)
            and oracle.chord_is_safe(initial, final, reference)
                == legacy_chord_is_safe(initial, final, reference),
            "exact component safety witness differs from the full predicate",
        )

    fractions = (
        (oracle.Fraction(-7, 18), oracle.Fraction(5, 42)),
        (
            oracle.Fraction(2**4096 + 3, 3 * 2**2048),
            oracle.Fraction(-(2**4095 - 7), 5 * 2**2047),
        ),
        (
            oracle.Fraction(1, 2**8192),
            oracle.Fraction(-1, 3 * 2**4096),
        ),
    )
    expected_maximum = max(abs(first - second) for first, second in fractions)
    maximum_pair = (0, 1)
    for first, second in fractions:
        pair = oracle._fraction_difference_pair(first, second)
        if oracle._fraction_pair_greater(pair, maximum_pair):
            maximum_pair = pair
        exact = abs(first - second)
        oracle.require(
            oracle.fraction_difference_within(first, second, exact)
            and not oracle.fraction_difference_within(
                first, second,
                exact - oracle.Fraction(1, exact.denominator * 2),
            ),
            "cross-product difference containment changed an exact boundary",
        )
    oracle.require(
        oracle.Fraction(*maximum_pair) == expected_maximum,
        "cross-product maximum differs from canonical Fraction arithmetic",
    )

    parent_initial = oracle.grouped(
        oracle.rows(parent_raw / "initial_states.csv"), ("scenario_id",)
    )
    exact_initial = oracle.rational_from_parent_rows(parent_initial[("k4_internal",)])
    encoded = oracle.encode_rational_state(exact_initial)
    bit_lengths: list[int] = []
    for packet in sorted(exact_initial.packets, key=lambda value: value.identifier):
        for value in packet.x + packet.p:
            _coarse, residual = oracle.split_rational_component(value)
            bit_lengths.extend((
                abs(residual.numerator).bit_length(),
                residual.denominator.bit_length(),
            ))
    ordered = sorted(bit_lengths)
    center = len(ordered) // 2
    legacy_median = (
        oracle.Fraction(ordered[center])
        if len(ordered) % 2
        else oracle.Fraction(ordered[center - 1] + ordered[center], 2)
    )
    metrics = oracle.rational_state_metrics(exact_initial)
    oracle.require(
        metrics.maximum_component_bits == max(bit_lengths)
        and metrics.median_component_bits == legacy_median
        and metrics.checkpoint_bytes == len(encoded)
        and metrics.sha256 == oracle.hashlib.sha256(encoded).hexdigest(),
        "single-pass rational state metrics differ",
    )

    model = context["models"]["k4"]
    interval = oracle.TIMESTEPS_RAW[0]
    for path in (oracle.CONTROL, oracle.KDK):
        samples, traces, evaluations = oracle.run_rational_trajectory_with_traces(
            model, exact_initial, interval, 2, path,
        )
        direct = oracle.run_rational_trajectory(
            model, exact_initial, interval, 2, path,
        )
        oracle.require(
            [oracle.encode_rational_state(state) for state in samples]
            == [oracle.encode_rational_state(state) for state in direct],
            "cached exact-force trajectory differs from direct replay",
        )
        oracle.require(
            all(
                trace[0]["committed"] == samples[index + 1]
                for index, trace in enumerate(traces)
            ),
            "cached exact-force trace chain differs",
        )
        for state, cached in zip(samples, evaluations):
            oracle.require(
                cached == oracle.rational_force_and_energy(model, state),
                "cached exact force/potential evaluation differs",
            )

    bounded = context["state_report"]["initial"][
        (96, "k4_internal", "initial", 0)
    ]
    x_radii, p_radii = oracle.zero_phase_radii(bounded)
    bounded_packets = sorted(bounded.packets, key=lambda value: value.identifier)
    exact_packets = sorted(exact_initial.packets, key=lambda value: value.identifier)
    legacy_contained = all(
        abs(bounded_packet.x[axis] - exact_packet.x[axis])
            <= x_radii[bounded_packet.identifier][axis]
        and abs(bounded_packet.p[axis] - exact_packet.p[axis])
            <= p_radii[bounded_packet.identifier][axis]
        for bounded_packet, exact_packet in zip(bounded_packets, exact_packets)
        for axis in range(3)
    )
    oracle.require(
        oracle.bounded_rational_state_is_contained(
            bounded, exact_initial, x_radii, p_radii,
        ) == legacy_contained
        and oracle.bounded_rational_error(bounded, exact_initial)
            == max(
                abs(left - right)
                for bounded_packet, exact_packet in zip(
                    bounded_packets, exact_packets
                )
                for left, right in zip(bounded_packet.x, exact_packet.x)
            ),
        "optimized bounded/rational state comparison differs",
    )
    wrong_time = exact_initial.clone()
    wrong_time.time_raw += 1
    oracle.require(
        not oracle.bounded_rational_state_is_contained(
            bounded, wrong_time, x_radii, p_radii,
        ),
        "optimized bounded/rational containment ignored time",
    )


def first_comparator_receipt(
    raw: Path, parent_raw: Path, context: dict[str, object],
) -> dict[tuple[str, ...], dict[str, str]]:
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
    selected_steps = {0, requested // 2, requested}
    exact_samples = {}
    for step in range(requested + 1):
        if step in selected_steps:
            exact_samples[step] = state.clone()
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
    oracle.require(set(exact_samples) == selected_steps,
                   "selected long exact-comparator samples differ")
    precision = 64
    bounded_initial = context["state_report"]["initial"][
        (precision, scenario, "initial", 0)
    ]
    bounded_samples = oracle.run_trajectory(
        context["models"]["k4"], bounded_initial, oracle.TIMESTEPS_RAW[level],
        requested, oracle.KDK,
    )[0].samples
    evidence = {
        int(item["sample"]): item
        for item in oracle.iter_rows(raw / "representation_error.csv")
        if item["scenario_id"] == scenario
        and item["scope"] == "long_exact_prefix"
        and item["path"] == oracle.KDK
        and item["precision"] == str(precision)
        and item["level"] == str(level)
        and int(item["sample"]) in selected_steps
    }
    oracle.require(set(evidence) == selected_steps,
                   "selected long representation inventory differs")
    expected_rows: dict[tuple[str, ...], dict[str, str]] = {}
    for sample in sorted(selected_steps):
        candidate = bounded_samples[sample]
        exact = exact_samples[sample]
        x_raw = oracle.bounded_rational_error(candidate, exact)
        p_raw = oracle.bounded_rational_error(candidate, exact, True)
        energy_error = (
            oracle.mechanical_energy(context["models"]["k4"], candidate)[2]
            - oracle.rational_energy(context["models"]["k4"], exact)
        )
        identity = {
            "scenario_id": scenario,
            "scope": "long_exact_prefix",
            "path": oracle.KDK,
            "precision": precision,
            "level": level,
            "dt_raw": oracle.TIMESTEPS_RAW[level],
            "sample": sample,
            "candidate_state_hash": oracle.phase_hash(candidate),
            "control_state_hash": oracle.rational_hash(exact),
        }
        oracle.verify_representation_error_row(
            evidence[sample], identity, x_raw, p_raw, energy_error
        )
        expected = expected_representation_row(identity, x_raw, p_raw, energy_error)
        expected_rows[representation_key(expected)] = expected
    return expected_rows


def detect_state(raw: Path, parent_raw: Path) -> None:
    oracle.verify_state_tables(raw, parent_raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--parent-raw", type=Path, required=True)
    arguments = parser.parse_args()
    global oracle
    oracle = load_oracle(Path(__file__).resolve().parents[1])

    print("[bounded-phase mutations] baseline-positives:start", flush=True)
    streaming_edit_cell_positive()
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
    analytic_phase_certificate_semantics(arguments.raw, context, arguments.parent_raw)
    optimization_equivalence_semantics(context, arguments.parent_raw)
    long_representation_expectations = first_comparator_receipt(
        arguments.raw, arguments.parent_raw, context
    )
    oracle.verify_representation_error_inventory(arguments.raw)
    short_representation_expectations = first_short_representation(
        arguments.raw, arguments.parent_raw, context
    )
    high_precision_representation_expectations = first_short_representation(
        arguments.raw, arguments.parent_raw, context, 256
    )
    selected_representation_expectations = {
        **short_representation_expectations,
        **high_precision_representation_expectations,
        **long_representation_expectations,
    }
    display_alias_positive()
    preregistered_scaling_semantics_positive()
    oracle.verify_state_size(arguments.raw, context["state_report"])
    print("[bounded-phase mutations] baseline-positives:complete", flush=True)

    schema = lambda raw, _parent: oracle.verify_schema_metadata_profiles(raw, True)
    parent_check = lambda raw, parent_raw: oracle.verify_parent_hashes(raw, parent_raw)
    positive = lambda raw, parent_raw: oracle.verify_positive_control_rows(raw, parent_raw)
    state = lambda raw, parent_raw: detect_state(raw, parent_raw)
    short = lambda raw, _parent: first_short_replay(raw, context)
    long_audit = lambda raw, _parent: first_long_audit(raw, context)
    auxiliary_audit = lambda raw, _parent: first_auxiliary_audit(raw, context)
    representation = lambda raw, parent: first_short_representation(raw, parent, context)
    representation_inventory = (
        lambda raw, _parent: oracle.verify_representation_error_inventory(raw)
    )
    cached_representation = (
        lambda raw, _parent: verify_cached_representation_rows(
            raw, selected_representation_expectations
        )
    )
    reversal = lambda raw, _parent: first_reversal(raw, context)
    covariance = lambda raw, _parent: covariance_scaling(raw, context)
    domain = lambda raw, _parent: first_domain(raw, context)
    size = lambda raw, _parent: oracle.verify_state_size(raw, context["state_report"])
    long_energy = lambda raw, _parent: first_long_energy(raw, context)
    checkpoint = lambda raw, _parent: first_checkpoint(raw, context)
    comparator = lambda raw, parent: first_comparator_receipt(raw, parent, context)
    composition_inventory = (
        lambda raw, _parent: oracle.verify_reversal_checkpoint_domain_inventory(raw)
    )

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
        ("raw_schema_discriminator", lambda r, _p: edit_cell(
            r, "metadata.csv", lambda row: row["key"] == "schema",
            "value", "mls.bounded-fractional-phase-state.raw.v1"), schema),
        ("observer_event_discriminator", lambda r, _p: edit_cell(
            r, "metadata.csv", lambda row: row["key"] == "observer_event_encoding",
            "value", "length_framed_utf8_fields_then_sha256_v1"), schema),
        ("observer_stream_discriminator", lambda r, _p: edit_cell(
            r, "metadata.csv", lambda row: row["key"] == "observer_stream_encoding",
            "value", "step_framed_ordered_event_sha256_v1"), schema),
        ("representation_commitment_discriminator", lambda r, _p: edit_cell(
            r, "metadata.csv",
            lambda row: row["key"] == "representation_error_commitment_encoding",
            "value", "identified_exact_fraction_triplet_sha256_v1"), schema),
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
        ("underflow_range_wire_state",
         lambda r, _p: mutate_underflow_range_wire_state(r), state),
        ("nonnormalized_significand_wire_state",
         lambda r, _p: mutate_noncanonical_significand_wire_state(r), state),
        ("unreduced_state_exact_value", lambda r, _p: (
            edit_cell(r, "initial_states.csv", lambda row: True, "xx_exact_num",
                      lambda value: str(int(value) * 2)),
            edit_cell(r, "initial_states.csv", lambda row: True, "xx_exact_den",
                      lambda value: str(int(value) * 2))), state),
        ("false_temporal_endpoint", lambda r, _p: mutate_canonical_endpoint(r, context),
         lambda r, _p: endpoint_replay(r, context)),
        ("false_temporal_order_endpoint_transplant",
         lambda r, _p: transplant_coarser_temporal_endpoint(r),
         lambda r, _p: endpoint_replay(r, context)),
        ("absolute_position_conversion_masquerade", lambda r, _p: edit_cell(
            r, "force_audit.csv", first_force, "causal_offset_raw_hash", "0" * 64), short),
        ("false_force_length", lambda r, _p: edit_cell(
            r, "force_audit.csv", first_force, "length_bits", lambda value: str(int(value) + 1)), short),
        ("false_force_residual", lambda r, _p: edit_cell(
            r, "force_audit.csv", first_force,
            "pair_momentum_residual_raw_x_dyadic", perturb_compact_dyadic), short),
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
            r, "invariants.csv", first_invariant,
            "momentum_raw_x_dyadic", perturb_compact_dyadic), short),
        ("omitted_long_invariant_observer", lambda r, _p: edit_cell(
            r, "invariants.csv", first_long, "angular_raw_x_dyadic", ""), long_audit),
        ("false_transformed_absolute_angular", lambda r, _p: edit_cell(
            r, "invariants.csv", first_auxiliary, "angular_raw_x_dyadic", "0x1@0"),
         auxiliary_audit),
        ("false_transformed_centrality", lambda r, _p: edit_cell(
            r, "force_audit.csv", first_auxiliary,
            "stored_impulse_centrality_residual_raw_x_dyadic", perturb_compact_dyadic),
         auxiliary_audit),
        ("representation_digest_flip", lambda r, _p: edit_cell(
            r, "representation_error.csv", lambda row: row["scenario_id"] == "k4_breathing"
            and row["path"] == oracle.CONTROL and row["precision"] == "64"
            and row["level"] == "0" and row["scope"] == "short" and row["sample"] == "1",
            "exact_errors_sha256", flip_sha256), representation),
        ("representation_digest_transplant",
         lambda r, _p: transplant_representation_commitment(r), representation),
        ("representation_display_only",
         lambda r, _p: alter_representation_display(r), representation),
        ("representation_rounded_commitment",
         lambda r, _p: replace_with_display_rounded_commitment(r), representation),
        ("false_precision_scaling_evidence",
         lambda r, _p: forge_zero_high_precision_representation_error(r),
         cached_representation),
        ("representation_candidate_hash", lambda r, _p: edit_cell(
            r, "representation_error.csv", lambda row: row["scenario_id"] == "k4_breathing"
            and row["path"] == oracle.CONTROL and row["precision"] == "64"
            and row["level"] == "0" and row["scope"] == "short" and row["sample"] == "1",
            "candidate_state_hash", "3" * 64), representation),
        ("representation_control_hash", lambda r, _p: edit_cell(
            r, "representation_error.csv", lambda row: row["scenario_id"] == "k4_breathing"
            and row["path"] == oracle.CONTROL and row["precision"] == "64"
            and row["level"] == "0" and row["scope"] == "short" and row["sample"] == "1",
            "control_state_hash", "4" * 64), representation),
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
        ("reordered_exact_comparator_receipts",
         lambda r, _p: reorder_comparator_rows(r), representation_inventory),
        ("duplicate_reversibility_key", lambda r, _p: duplicate_small_table_key(
            r, "reversibility.csv", ("precision", "scenario_id", "level")),
         composition_inventory),
        ("missing_reversibility_row",
         lambda r, _p: delete_small_table_row(r, "reversibility.csv"),
         composition_inventory),
        ("reordered_reversibility_rows",
         lambda r, _p: reorder_small_table(r, "reversibility.csv"),
         composition_inventory),
        ("duplicate_checkpoint_key", lambda r, _p: duplicate_small_table_key(
            r, "checkpoint.csv", ("precision", "level")), composition_inventory),
        ("missing_checkpoint_row",
         lambda r, _p: delete_small_table_row(r, "checkpoint.csv"),
         composition_inventory),
        ("reordered_checkpoint_rows",
         lambda r, _p: reorder_small_table(r, "checkpoint.csv"),
         composition_inventory),
        ("duplicate_domain_key", lambda r, _p: duplicate_small_table_key(
            r, "domain.csv", ("precision", "level")), composition_inventory),
        ("missing_domain_row",
         lambda r, _p: delete_small_table_row(r, "domain.csv"),
         composition_inventory),
        ("reordered_domain_rows",
         lambda r, _p: reorder_small_table(r, "domain.csv"),
         composition_inventory),
        ("hidden_state_column", lambda r, _p: add_hidden_column(r), schema),
    ]

    for scope in ("short", "long_exact_prefix"):
        label = "short" if scope == "short" else "long"
        for position in ("first", "middle", "last"):
            cases.append((
                f"representation_delete_{label}_{position}",
                lambda r, _p, s=scope, q=position: delete_representation_row(r, s, q),
                representation_inventory,
            ))
        cases.extend((
            (
                f"representation_duplicate_{label}",
                lambda r, _p, s=scope: duplicate_representation_row(r, s, "middle"),
                representation_inventory,
            ),
            (
                f"representation_reorder_{label}",
                lambda r, _p, s=scope: reorder_representation_rows(r, s, "middle"),
                representation_inventory,
            ),
            (
                f"representation_identity_{label}",
                lambda r, _p, s=scope: mutate_representation_identity(r, s, "middle"),
                representation_inventory,
            ),
        ))

    for label, scope, scenario, path, samples in (
        ("short", "short", "k4_breathing", oracle.CONTROL, (0, 8, 16)),
        ("long", "long_exact_prefix", "k4_internal", oracle.KDK, (0, 128, 256)),
    ):
        for position, sample in zip(("first", "middle", "last"), samples):
            cases.append((
                f"representation_digest_{label}_{position}",
                lambda r, _p, s=scope, c=scenario, q=path, n=sample: edit_cell(
                    r, "representation_error.csv",
                    lambda row: row["scope"] == s and row["scenario_id"] == c
                    and row["path"] == q and row["precision"] == "64"
                    and row["level"] == "0" and row["sample"] == str(n),
                    "exact_errors_sha256", flip_sha256,
                ),
                cached_representation,
            ))

    detected = 0
    failures = (
        OSError, ValueError, ArithmeticError, IndexError, KeyError, StopIteration,
        oracle.OracleError, oracle.parent.OracleError, oracle.foundation.OracleError,
    )
    with tempfile.TemporaryDirectory(prefix="mls-bounded-phase-mutations-") as directory:
        root = Path(directory)
        for index, (name, mutation, detector) in enumerate(cases):
            print(
                f"[bounded-phase mutation {index + 1}/{len(cases)}] {name}",
                flush=True,
            )
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
        "PASS (2 deterministic replay positives, 1 display-alias positive, "
        f"paired analytic-certificate positives/negatives, {detected} mutations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
