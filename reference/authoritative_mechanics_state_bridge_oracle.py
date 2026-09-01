#!/usr/bin/env python3
"""Independent exact-rational oracle for the mechanics state bridge lab."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import struct
from fractions import Fraction
from pathlib import Path
from typing import Any


PARENT_SHA = "2cc26e9a6e2aff8f40dec9787fe7e6e0e6b63f21"
PARENT_TAG = "relation-geometry-resolution-lab-evidence-v1"
PARENT_TAG_OBJECT = "ea423e350908b3446b754f7fb75457ca78313cde"
BRANCH = "authoritative-mechanics-state-bridge-lab"
DECISION = "retain_direct_quantized_mechanics_bridge_for_research"
EXPECTED_H_SHA256 = "463dd112cdab06916d500a9f55cc6442a465322ea38374a982fc4a9193815fa3"
REFINEMENTS = (1, 2, 4, 8, 16)
SUBDIVISIONS = (1, 2, 4, 8, 16)
PATHS = ("direct_nearest", "fixed_point_refinement", "explicit_remainder")


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bits_float(text: str) -> float:
    return struct.unpack("<d", struct.pack("<Q", int(text)))[0]


def bits_fraction(text: str) -> Fraction:
    return Fraction.from_float(bits_float(text))


def float_bits(value: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def rational(text: str) -> Fraction:
    numerator, denominator = text.split("/")
    return Fraction(int(numerator), int(denominator))


def nearest_even(value: Fraction) -> int:
    lower = value.numerator // value.denominator
    remainder = value - lower
    if remainder > Fraction(1, 2) or (
        remainder == Fraction(1, 2) and lower % 2 != 0
    ):
        return lower + 1
    return lower


def cross(lhs: tuple[int, int, int], rhs: tuple[int, int, int]) -> tuple[int, int, int]:
    return (
        lhs[1] * rhs[2] - lhs[2] * rhs[1],
        lhs[2] * rhs[0] - lhs[0] * rhs[2],
        lhs[0] * rhs[1] - lhs[1] * rhs[0],
    )


def primitive(offset: tuple[int, int, int]) -> tuple[int, int, int]:
    divisor = math.gcd(math.gcd(abs(offset[0]), abs(offset[1])), abs(offset[2]))
    if divisor == 0:
        raise ValueError("coincident authoritative relation")
    return tuple(value // divisor for value in offset)  # type: ignore[return-value]


def fnv_word(state: int, word: int) -> int:
    for index in range(8):
        state = ((state ^ ((word >> (8 * index)) & 0xFF)) * 1099511628211) & (
            (1 << 64) - 1
        )
    return state


def checkpoint_hash(first_id: int, second_id: int, remainder_bits: int) -> int:
    state = 1469598103934665603
    state = fnv_word(state, first_id)
    state = fnv_word(state, second_id)
    return fnv_word(state, remainder_bits)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def close_bits(actual: str, exact: Fraction, ulps: int = 8) -> None:
    expected = float_bits(float(exact))
    observed = int(actual)
    if expected >> 63 != observed >> 63:
        require(expected == observed, "binary64 sign differs")
    require(abs(expected - observed) <= ulps, "binary64 forward error exceeds gate")


def validate_units(raw: Path) -> dict[int, dict[str, Fraction]]:
    values = rows(raw / "units.csv")
    require(len(values) == 5, "unit refinement inventory differs")
    result: dict[int, dict[str, Fraction]] = {}
    for row in values:
        refinement = int(row["refinement"])
        require(refinement in REFINEMENTS and refinement not in result, "unit R differs")
        unit = {name: rational(row[name]) for name in ("Lq", "Mq", "Tq", "Pq", "Eq", "Fq")}
        require(unit["Lq"] == Fraction(1, 1_000_000_000 * refinement), "Lq differs")
        require(unit["Mq"] == Fraction(1, 4096 * refinement), "Mq differs")
        require(unit["Tq"] == Fraction(1, 1_000_000_000), "Tq differs")
        require(unit["Pq"] == unit["Mq"] * unit["Lq"] / unit["Tq"], "Pq identity")
        require(unit["Eq"] == unit["Mq"] * unit["Lq"] ** 2 / unit["Tq"] ** 2, "Eq identity")
        require(unit["Fq"] == unit["Mq"] * unit["Lq"] / unit["Tq"] ** 2, "Fq identity")
        require(row["physical_time_numerator"] == "1", "physical time numerator")
        require(row["physical_time_denominator"] == "1000000000", "physical time denominator")
        require(row["velocity_scale_numerator"] == "1", "velocity scale numerator")
        require(row["velocity_scale_denominator"] == "1", "velocity scale denominator")
        require(row["kinetic_scale_denominator"] == "1", "kinetic denominator")
        result[refinement] = unit
    require(tuple(result) == REFINEMENTS, "unit order differs")
    return result


def validate_metadata(raw: Path) -> dict[str, str]:
    values = rows(raw / "metadata.csv")
    metadata = {row["key"]: row["value"] for row in values}
    require(len(metadata) == len(values), "duplicate metadata key")
    expected = {
        "schema": "mls.authoritative-mechanics-state-bridge.raw.v1",
        "accepted_parent_sha": PARENT_SHA,
        "accepted_parent_tag": PARENT_TAG,
        "accepted_parent_tag_object": PARENT_TAG_OBJECT,
        "source_branch": BRANCH,
        "branch": BRANCH,
        "decision": DECISION,
        "selected_refinement": "16",
        "selected_geometry_path": "cancellation_resistant_binary64",
        "safe_domain": "2^-24",
        "promotion": "NO_PROMOTION",
    }
    for key, value in expected.items():
        require(metadata.get(key) == value, f"metadata differs: {key}")
    return metadata


def validate_packets(raw: Path, units: dict[int, dict[str, Fraction]]) -> dict[int, dict[str, Any]]:
    values = rows(raw / "packets_bits.csv")
    require(len(values) == 4, "packet inventory differs")
    packets: dict[int, dict[str, Any]] = {}
    for row in values:
        packet_id = int(row["packet_id"])
        require(packet_id not in packets and packet_id in range(1, 5), "packet ID differs")
        position = tuple(int(row[f"base_{axis}_raw"]) for axis in "xyz")
        momentum = tuple(int(row[f"base_p{axis}_raw"]) for axis in "xyz")
        mass = int(row["base_mass_raw"])
        require(mass == 1, "authoritative mass differs")
        require(row["nearest_roundtrip_exact"] == "true", "mapping roundtrip failed")
        for index, axis in enumerate("xyz"):
            # The C++ bridge performs the declared binary64 raw*quantum
            # operation.  Its 1e-9 length quantum is itself rounded, so the
            # result may be one ulp from the correctly rounded exact rational
            # while still recovering the raw coordinate exactly.
            close_bits(row[f"{axis}_bits"], position[index] * units[1]["Lq"], 2)
            close_bits(row[f"p{axis}_bits"], momentum[index] * units[1]["Pq"], 0)
        close_bits(row["mass_bits"], mass * units[1]["Mq"], 0)
        packets[packet_id] = {"position": position, "momentum": momentum, "mass": mass}
    require(tuple(packets) == (1, 2, 3, 4), "packet order differs")
    return packets


def validate_relations(raw: Path) -> dict[int, dict[str, Any]]:
    require(sha256(raw / "h_bits.csv") == EXPECTED_H_SHA256, "frozen H differs")
    h_rows = rows(raw / "h_bits.csv")
    require(len(h_rows) == 36, "H inventory differs")
    h = {(int(row["row_relation_index"]), int(row["column_relation_index"])): row["h_bits"] for row in h_rows}
    require(len(h) == 36, "duplicate H coordinate")
    for row in range(6):
        for column in range(6):
            require(h[(row, column)] == h[(column, row)], "H is not bit symmetric")

    values = rows(raw / "relations_bits.csv")
    require(len(values) == 6, "relation inventory differs")
    result: dict[int, dict[str, Any]] = {}
    for row in values:
        index = int(row["relation_index"])
        require(index not in result and index in range(6), "relation index differs")
        first_id, second_id = int(row["first_id"]), int(row["second_id"])
        require(first_id < second_id, "relation orientation differs")
        require(row["geometry_path"] == "cancellation_resistant_binary64", "Path B changed")
        require(row["geometry_status"] == "evaluated", "Path B unresolved")
        require((row["rho_num"], row["rho_den"]) == ("1001", "1000"), "safe-domain ratio differs")
        result[index] = {
            "first": first_id,
            "second": second_id,
            "force": tuple(bits_fraction(row[f"force_{axis}_bits"]) for axis in "xyz"),
        }
    require(tuple(result) == tuple(range(6)), "relation order differs")
    return result


def validate_evaluations(
    raw: Path,
    units: dict[int, dict[str, Fraction]],
    packets: dict[int, dict[str, Any]],
    relations: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, str]], dict[int, tuple[Fraction, Fraction, Fraction]]]:
    values = rows(raw / "evaluations.csv")
    require(len(values) == 6 * 5 * 5 * 3, "evaluation inventory differs")
    seen: set[tuple[int, str, int, int]] = set()
    errors: dict[int, list[Fraction]] = {refinement: [] for refinement in REFINEMENTS}
    applied_by_group: dict[tuple[int, int, int], list[tuple[Fraction, Fraction, Fraction]]] = {}
    remainder_totals: dict[tuple[int, int], set[tuple[int, int, int]]] = {}
    floor_bounds: dict[int, Fraction] = {refinement: Fraction(0) for refinement in REFINEMENTS}
    direct_totals: dict[int, set[tuple[int, int, int]]] = {}

    for row in values:
        relation_index = int(row["relation_index"])
        path = row["path"]
        refinement = int(row["refinement"])
        subdivisions = int(row["subdivisions"])
        key = (relation_index, path, refinement, subdivisions)
        require(key not in seen, "duplicate evaluation")
        seen.add(key)
        require(path in PATHS and refinement in REFINEMENTS and subdivisions in SUBDIVISIONS, "evaluation coordinate differs")
        relation = relations[relation_index]
        first_id, second_id = int(row["first_id"]), int(row["second_id"])
        require((first_id, second_id) == (relation["first"], relation["second"]), "evaluation endpoints differ")
        first, second = packets[first_id], packets[second_id]
        offset = tuple(second["position"][axis] - first["position"][axis] for axis in range(3))
        direction = primitive(offset)
        exported_direction = tuple(int(row[f"primitive_{axis}"]) for axis in "xyz")
        require(exported_direction == direction, "primitive direction differs")
        direction_squared = sum(value * value for value in direction)
        target = relation["force"]  # dt is exactly one SI second
        target_multiple = sum(target[axis] * direction[axis] for axis in range(3)) / (
            units[refinement]["Pq"] * direction_squared
        )
        close_bits(row["target_multiple_bits"], target_multiple, 4)

        if path == "explicit_remainder":
            remainder = Fraction(0)
            applied_multiple = 0
            for _ in range(subdivisions):
                available = target_multiple / subdivisions + remainder
                increment = nearest_even(available)
                applied_multiple += increment
                remainder = available - increment
        else:
            increment = nearest_even(target_multiple / subdivisions)
            applied_multiple = subdivisions * increment
            remainder = Fraction(0)
        require(int(row["applied_multiple"]) == applied_multiple, "nearest-even decision differs")
        impulse = tuple(applied_multiple * value for value in direction)
        opposite = tuple(-value for value in impulse)
        require(tuple(int(row[f"impulse_{axis}_raw"]) for axis in "xyz") == impulse, "impulse differs")
        require(tuple(int(row[f"opposite_{axis}_raw"]) for axis in "xyz") == opposite, "opposite impulse differs")
        require(tuple(impulse[axis] + opposite[axis] for axis in range(3)) == (0, 0, 0), "raw Delta P differs")
        require(cross(tuple(value * refinement for value in offset), impulse) == (0, 0, 0), "raw Delta L differs")
        require(row["linear_conserved"] == "true" and row["angular_conserved"] == "true", "conservation label differs")

        applied_si = tuple(value * units[refinement]["Pq"] for value in impulse)
        for axis, name in enumerate("xyz"):
            close_bits(row[f"target_{name}_bits"], target[axis], 0)
            close_bits(row[f"applied_{name}_bits"], applied_si[axis], 0)
            close_bits(row[f"discarded_{name}_bits"], target[axis] - applied_si[axis], 2)
            errors[refinement].append(abs(target[axis] - applied_si[axis]) / units[1]["Pq"])
        applied_by_group.setdefault((relation_index, refinement, 0), []).append(applied_si)
        if path == "direct_nearest" and refinement == 1:
            direct_totals.setdefault(relation_index, set()).add(impulse)
        if path == "explicit_remainder":
            remainder_totals.setdefault((relation_index, refinement), set()).add(impulse)
            require(row["checkpoint_first_id"] == str(first_id), "remainder checkpoint first ID")
            require(row["checkpoint_second_id"] == str(second_id), "remainder checkpoint second ID")
            remainder_bits = int(row["checkpoint_remainder_bits"])
            require(float_bits(bits_float(row["remainder_bits"])) == remainder_bits, "remainder checkpoint omitted")
            require(int(row["checkpoint_hash"]) == checkpoint_hash(first_id, second_id, remainder_bits), "remainder checkpoint hash differs")
            require(row["checkpoint_roundtrip"] == "true", "remainder checkpoint roundtrip failed")

        squared_raw = sum(value * value for value in impulse)
        first_mass_raw = first["mass"] * refinement
        second_mass_raw = second["mass"] * refinement
        kinetic_raw = (squared_raw // first_mass_raw) // 2 + (squared_raw // second_mass_raw) // 2
        require(int(row["kinetic_raw"]) == kinetic_raw, "kinetic floor order differs")
        exact_kinetic = sum(value * value for value in applied_si) * (
            Fraction(1, 2 * first["mass"] * refinement) / units[refinement]["Mq"]
            + Fraction(1, 2 * second["mass"] * refinement) / units[refinement]["Mq"]
        )
        quantized_kinetic = kinetic_raw * units[refinement]["Eq"]
        floor_residual = exact_kinetic - quantized_kinetic
        require(Fraction(0) <= floor_residual < 2 * units[refinement]["Eq"], "kinetic floor residual bound")
        floor_bounds[refinement] = max(floor_bounds[refinement], floor_residual)
        close_bits(row["exact_kinetic_bits"], exact_kinetic, 6)
        close_bits(row["quantized_kinetic_bits"], quantized_kinetic, 0)
        close_bits(row["floor_residual_bits"], floor_residual, 12)
        close_bits(row["work_bits"], exact_kinetic, 6)

    require(len(seen) == 450, "evaluation coverage differs")
    require(any(len(values) > 1 for values in direct_totals.values()), "Path A subdivision control unexpectedly invariant")
    require(all(len(values) == 1 for values in remainder_totals.values()), "explicit remainder is not subdivision invariant")
    require(all(floor_bounds[REFINEMENTS[index + 1]] <= 2 * units[REFINEMENTS[index + 1]]["Eq"] < 2 * units[REFINEMENTS[index]]["Eq"] for index in range(4)), "kinetic floor envelope does not converge")

    summary: dict[int, tuple[Fraction, Fraction, Fraction]] = {}
    for refinement in REFINEMENTS:
        fixed_rows = [row for row in values if row["path"] == "fixed_point_refinement" and int(row["refinement"]) == refinement]
        max_error = max(errors[refinement])
        spread = Fraction(0)
        for relation_index in range(6):
            relation_rows = [row for row in fixed_rows if int(row["relation_index"]) == relation_index]
            for axis in "xyz":
                applied = [bits_fraction(row[f"applied_{axis}_bits"]) for row in relation_rows]
                spread = max(spread, max(applied) - min(applied))
        summary[refinement] = (max_error, spread / units[1]["Pq"], floor_bounds[refinement])
    return values, summary


def validate_summary(raw: Path, summary: dict[int, tuple[Fraction, Fraction, Fraction]]) -> None:
    values = rows(raw / "candidate_summary.csv")
    require(len(values) == 5, "candidate summary inventory differs")
    prior_error: Fraction | None = None
    selected: list[int] = []
    for row in values:
        refinement = int(row["refinement"])
        max_error, spread, _ = summary[refinement]
        close_bits(row["maximum_error_base_quanta_bits"], max_error, 8)
        close_bits(row["subdivision_spread_base_quanta_bits"], spread, 8)
        passes = refinement > 1 and max_error < Fraction(1, 32) and spread < Fraction(1, 16)
        require(row["passes"] == str(passes).lower(), "candidate pass label differs")
        require(row["selected"] == str(refinement == 16).lower(), "candidate selection label differs")
        if row["selected"] == "true":
            selected.append(refinement)
        if prior_error is not None:
            require(max_error < prior_error, "impulse error envelope is not strictly shrinking")
        prior_error = max_error
    require(selected == [16], "smallest passing refinement is not R=16")


def canonical(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        raw = arguments.raw.resolve()
        metadata = validate_metadata(raw)
        units = validate_units(raw)
        packets = validate_packets(raw, units)
        relations = validate_relations(raw)
        evaluations, summary = validate_evaluations(raw, units, packets, relations)
        validate_summary(raw, summary)
        result = {
            "schema": "mls.authoritative-mechanics-state-bridge.oracle.v1",
            "accepted_parent_sha": PARENT_SHA,
            "source_sha": metadata["source_sha"],
            "decision": DECISION,
            "selected_refinement": 16,
            "selected_geometry_path": "cancellation_resistant_binary64",
            "unit_contract_consistent": True,
            "binary64_roundtrip_resolved": True,
            "evaluation_count": len(evaluations),
            "exact_linear_momentum_rows": len(evaluations),
            "exact_orbital_angular_momentum_rows": len(evaluations),
            "direct_base_subdivision_control": False,
            "stateless_refinement_converges": True,
            "explicit_remainder_controlled_but_not_selected": True,
            "kinetic_energy_floor_converges": True,
            "promotion": "NO_PROMOTION",
            "input_sha256": {
                path.name: sha256(path)
                for path in sorted(raw.glob("*.csv"))
            },
        }
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(canonical(result), encoding="utf-8")
        csv_output = arguments.output.with_suffix(".csv")
        with csv_output.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(("refinement", "max_error", "spread", "floor_residual"))
            for refinement in REFINEMENTS:
                writer.writerow((refinement, *(str(value) for value in summary[refinement])))
        print(
            "AUTHORITATIVE MECHANICS STATE BRIDGE ORACLE: PASS "
            "R=16 exact_conservation=450 kinetic_floor_converges=true NO_PROMOTION"
        )
        return 0
    except (OSError, ValueError, KeyError, ZeroDivisionError, OverflowError) as error:
        print(f"AUTHORITATIVE MECHANICS STATE BRIDGE ORACLE: FAIL: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
