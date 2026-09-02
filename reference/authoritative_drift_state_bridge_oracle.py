#!/usr/bin/env python3
"""Independent exact-rational oracle for the Authoritative Drift State Bridge."""

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
from fractions import Fraction
from pathlib import Path


PARENT_SHA = "d8fca8b0bf59a92382048bfb1389126552ac92f3"
PARENT_TAG = "authoritative-mechanics-state-bridge-lab-evidence-v1"
PARENT_TAG_OBJECT = "0a920fbb080525123d29dbea0a81b3bee3b9eec6"
BRANCH = "authoritative-drift-state-bridge-lab"
DECISION = "retain_refined_stateless_mechanics_representation_for_research"
REFINEMENTS = (1, 2, 4, 8, 16, 32, 64, 128)
HORIZONS = (32, 96, 160)
SUBDIVISIONS = (1, 2, 4, 8, 16, 32)
FILES = (
    "metadata.csv",
    "units.csv",
    "parent_fingerprint.csv",
    "inventory.csv",
    "evaluations.csv",
    "equal_velocity.csv",
    "center_of_mass.csv",
    "impulse_regression.csv",
    "domain_chords.csv",
    "overflow_controls.csv",
    "rounding_controls.csv",
    "candidate_summary.csv",
)
SHA1 = re.compile(r"[0-9a-f]{40}")
MAX_I64 = 2**63 - 1


class OracleError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OracleError(message)


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def metadata(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows(path):
        require(set(row) == {"key", "value"}, "metadata schema differs")
        require(row["key"] not in result, "duplicate metadata key")
        result[row["key"]] = row["value"]
    return result


def boolean(value: str) -> bool:
    require(value in {"true", "false"}, f"invalid boolean {value!r}")
    return value == "true"


def parse_ratio(value: str) -> Fraction:
    numerator, separator, denominator = value.partition("/")
    require(separator == "/", f"invalid rational {value!r}")
    result = Fraction(int(numerator), int(denominator))
    require(result > 0, "unit rational must be positive")
    return result


def float_from_bits(value: str) -> float:
    integer = int(value)
    require(0 <= integer < 2**64, "binary64 bits outside uint64")
    return struct.unpack(">d", struct.pack(">Q", integer))[0]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def nearest_even(value: Fraction) -> int:
    denominator = value.denominator
    floor_value = value.numerator // denominator
    remainder = value.numerator - floor_value * denominator
    doubled = 2 * remainder
    if doubled < denominator:
        return floor_value
    if doubled > denominator:
        return floor_value + 1
    return floor_value if floor_value % 2 == 0 else floor_value + 1


def nearest_even_double(value: float) -> int:
    require(math.isfinite(value), "nonfinite binary64 rounding input")
    lower = math.floor(value)
    fraction = value - lower
    if fraction > 0.5 or (fraction == 0.5 and lower % 2 != 0):
        return lower + 1
    return lower


def gcd3(vector: tuple[int, int, int]) -> int:
    return math.gcd(math.gcd(abs(vector[0]), abs(vector[1])), abs(vector[2]))


def cross(first: tuple[int, int, int], second: tuple[int, int, int]) -> tuple[int, int, int]:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def kinetic(momentum: tuple[int, int, int], mass: int) -> int:
    return sum(value * value for value in momentum) // mass // 1 // 2


def exact_max(values: list[Fraction]) -> Fraction:
    return max(values, default=Fraction(0))


def fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def verify_units(raw: Path) -> None:
    unit_rows = rows(raw / "units.csv")
    require(len(unit_rows) == len(REFINEMENTS), "unit row count differs")
    for row, refinement in zip(unit_rows, REFINEMENTS, strict=True):
        require(int(row["refinement"]) == refinement, "unit refinement order differs")
        length = Fraction(1, 1_000_000_000 * refinement)
        mass = Fraction(1, 4_096 * refinement)
        time = Fraction(1, 1_000_000_000)
        momentum = mass * length / time
        energy = mass * length * length / (time * time)
        force = energy / length
        require(parse_ratio(row["Lq"]) == length, "Lq differs")
        require(parse_ratio(row["Mq"]) == mass, "Mq differs")
        require(parse_ratio(row["Tq"]) == time, "Tq differs")
        require(parse_ratio(row["Pq"]) == momentum, "Pq differs")
        require(parse_ratio(row["Eq"]) == energy, "Eq differs")
        require(parse_ratio(row["Fq"]) == force, "Fq differs")
        require(row["velocity_scale_numerator"] == "1", "velocity numerator differs")
        require(row["velocity_scale_denominator"] == "1", "velocity denominator differs")
        require(row["kinetic_scale_denominator"] == "1", "kinetic scale differs")


def verify_fingerprint(raw: Path) -> None:
    fingerprint = {row["case"]: row for row in rows(raw / "parent_fingerprint.csv")}
    require(set(fingerprint) == {"exact_integer", "fractional"}, "fingerprint cases differ")
    require(
        fingerprint["exact_integer"]["expected"] == "pass"
        and boolean(fingerprint["exact_integer"]["result"])
        and boolean(fingerprint["exact_integer"]["transactional"]),
        "exact parent fingerprint differs",
    )
    require(
        fingerprint["fractional"]["expected"] == "reject"
        and boolean(fingerprint["fractional"]["result"])
        and boolean(fingerprint["fractional"]["transactional"]),
        "fractional parent fingerprint differs",
    )


def verify_rounding_and_overflow(raw: Path) -> None:
    controls = rows(raw / "rounding_controls.csv")
    require(len(controls) == 8, "rounding control count differs")
    for row in controls:
        value = Fraction(int(row["numerator"]), int(row["denominator"]))
        require(int(row["nearest_even"]) == nearest_even(value), "nearest-even control differs")
    overflow = {row["case"]: row for row in rows(raw / "overflow_controls.csv")}
    require(set(overflow) == {"largest_safe_product", "adjacent_overflow"}, "overflow controls differ")
    safe = overflow["largest_safe_product"]
    product = int(safe["multiplicand"]) * int(safe["multiplier"])
    require(abs(product) <= MAX_I64, "safe product is not safe")
    require(boolean(safe["accepted"]), "safe product rejected")
    require(
        int(safe["result"]) == nearest_even(Fraction(product, int(safe["denominator"]))),
        "safe product result differs",
    )
    rejected = overflow["adjacent_overflow"]
    product = int(rejected["multiplicand"]) * int(rejected["multiplier"])
    require(abs(product) > MAX_I64, "overflow witness does not overflow")
    require(not boolean(rejected["accepted"]) and rejected["result"] == "rejected", "overflow not rejected")


def verify_chords(raw: Path) -> None:
    chord_rows = rows(raw / "domain_chords.csv")
    require(len(chord_rows) == 3, "chord count differs")
    classifications: dict[int, bool] = {}
    for row in chord_rows:
        identifier = int(row["id"])
        initial = tuple(int(row[f"initial_{axis}"]) for axis in "xyz")
        final = tuple(int(row[f"final_{axis}"]) for axis in "xyz")
        rest = int(row["rest_length"])
        require(rest > 0, "nonpositive chord rest length")
        delta = tuple(final[index] - initial[index] for index in range(3))
        a = sum(value * value for value in delta)
        b = sum(initial[index] * delta[index] for index in range(3))
        parameter = Fraction(0)
        if a > 0:
            parameter = min(Fraction(1), max(Fraction(0), Fraction(-b, a)))
        minimum = tuple(Fraction(initial[index]) + parameter * delta[index] for index in range(3))
        minimum_squared = sum(value * value for value in minimum)
        admissible = minimum_squared * 2**48 >= rest * rest
        interior = Fraction(0) < parameter < Fraction(1)
        require(boolean(row["interior_minimum"]) == interior, "chord minimum classification differs")
        require(boolean(row["admissible"]) == admissible, "chord safe-domain classification differs")
        classifications[identifier] = admissible
    require(classifications == {1: True, 2: False, 3: False}, "registered chord fingerprint differs")


def verify(raw: Path) -> dict[str, object]:
    for filename in FILES:
        require((raw / filename).is_file(), f"missing raw file {filename}")
    meta = metadata(raw / "metadata.csv")
    expected_meta = {
        "schema": "mls.authoritative-drift-state-bridge.raw.v1",
        "accepted_parent_sha": PARENT_SHA,
        "accepted_parent_tag": PARENT_TAG,
        "accepted_parent_tag_object": PARENT_TAG_OBJECT,
        "branch": BRANCH,
        "decision": DECISION,
        "selected_refinement": "128",
        "selected_path": "primitive_directional",
        "explicit_remainder_evaluated": "false",
        "safe_domain": "2^-24",
        "cartesian_negative_control": "reject_cartesian_drift_quantization",
        "promotion": "NO_PROMOTION",
    }
    for key, value in expected_meta.items():
        require(meta.get(key) == value, f"metadata differs: {key}")
    require(meta.get("source_dirty") == "false", "source materialization is dirty")
    require(SHA1.fullmatch(meta.get("source_sha", "")) is not None, "source SHA malformed")
    verify_units(raw)
    verify_fingerprint(raw)
    verify_rounding_and_overflow(raw)
    verify_chords(raw)

    inventory_rows = rows(raw / "inventory.csv")
    require(len(inventory_rows) == 7, "inventory count differs")
    packets: dict[int, dict[str, object]] = {}
    for row in inventory_rows:
        identifier = int(row["packet_id"])
        require(identifier not in packets, "duplicate inventory packet")
        packets[identifier] = {
            "position": tuple(int(row[f"base_{axis}"]) for axis in "xyz"),
            "momentum": tuple(int(row[f"base_p{axis}"]) for axis in "xyz"),
            "mass": int(row["base_mass"]),
            "role": row["role"],
        }
    require(set(packets) == set(range(1, 8)), "packet IDs differ")
    require(
        packets[6]["momentum"] == (2, -3, 1)
        and packets[6]["mass"] == 5
        and packets[7]["momentum"] == (6, -9, 3)
        and packets[7]["mass"] == 15,
        "equal-velocity inventory differs",
    )

    evaluation_rows = rows(raw / "evaluations.csv")
    require(len(evaluation_rows) == 7 * 2 * 8 * 3 * 6, "evaluation row count differs")
    seen: set[tuple[int, str, int, int, int]] = set()
    directional: dict[tuple[int, int, int, int], dict[str, object]] = {}
    cartesian_torque = 0
    directional_exact = 0
    for row in evaluation_rows:
        identifier = int(row["packet_id"])
        path = row["path"]
        refinement = int(row["refinement"])
        horizon = int(row["horizon"])
        subdivision = int(row["subdivisions"])
        key = (identifier, path, refinement, horizon, subdivision)
        require(key not in seen, "duplicate evaluation row")
        seen.add(key)
        require(path in {"cartesian_nearest", "primitive_directional"}, "unknown drift path")
        require(refinement in REFINEMENTS and horizon in HORIZONS and subdivision in SUBDIVISIONS, "unregistered evaluation coordinate")
        require(horizon % subdivision == 0, "nonintegral substep")
        packet = packets[identifier]
        base_position = packet["position"]
        base_momentum = packet["momentum"]
        base_mass = int(packet["mass"])
        assert isinstance(base_position, tuple) and isinstance(base_momentum, tuple)
        refined_position = tuple(value * refinement for value in base_position)
        refined_momentum = tuple(value * refinement * refinement for value in base_momentum)
        refined_mass = base_mass * refinement
        substep = horizon // subdivision
        divisor = gcd3(refined_momentum)
        primitive = (0, 0, 0) if divisor == 0 else tuple(value // divisor for value in refined_momentum)
        if path == "cartesian_nearest":
            displacement = tuple(
                subdivision * nearest_even(Fraction(value * substep, refined_mass))
                for value in refined_momentum
            )
        elif divisor == 0:
            displacement = (0, 0, 0)
        else:
            multiple = subdivision * nearest_even(Fraction(divisor * substep, refined_mass))
            displacement = tuple(multiple * value for value in primitive)
        target = tuple(value * horizon for value in refined_momentum)
        error = tuple(displacement[index] * refined_mass - target[index] for index in range(3))
        delta_l = cross(displacement, refined_momentum)
        require(tuple(int(row[f"refined_{axis}"]) for axis in "xyz") == refined_position, "refined position differs")
        require(tuple(int(row[f"refined_p{axis}"]) for axis in "xyz") == refined_momentum, "refined momentum differs")
        require(int(row["refined_mass"]) == refined_mass, "refined mass differs")
        require(int(row["substep"]) == substep, "substep differs")
        require(int(row["gcd"]) == divisor, "momentum gcd differs")
        require(tuple(int(row[f"primitive_{axis}"]) for axis in "xyz") == primitive, "primitive direction differs")
        require(tuple(int(row[f"applied_d{axis}"]) for axis in "xyz") == displacement, "applied displacement differs")
        require(tuple(int(row[f"target_{axis}_num"]) for axis in "xyz") == target, "target numerator differs")
        require(int(row["target_den"]) == refined_mass, "target denominator differs")
        require(tuple(int(row[f"error_{axis}_num"]) for axis in "xyz") == error, "error numerator differs")
        require(tuple(int(row[f"delta_L_{axis}"]) for axis in "xyz") == delta_l, "orbital delta differs")
        before = kinetic(refined_momentum, refined_mass)
        require(int(row["kinetic_before"]) == before and int(row["kinetic_after"]) == before, "kinetic energy changed")
        require(boolean(row["momentum_unchanged"]), "momentum changed")
        require(boolean(row["kinetic_unchanged"]), "kinetic flag differs")
        angular = delta_l == (0, 0, 0)
        require(boolean(row["angular_unchanged"]) == angular, "angular flag differs")
        margin = min(MAX_I64 - abs(value) for value in target)
        require(int(row["product_margin"]) == margin, "product margin differs")
        lq = float(Fraction(1, 1_000_000_000 * refinement))
        exact_float = tuple(float(value) / float(refined_mass) * lq for value in target)
        applied_float = tuple(float(value) * lq for value in displacement)
        error_float = tuple(applied_float[index] - exact_float[index] for index in range(3))
        for index, axis in enumerate("xyz"):
            require(float_from_bits(row[f"exact_{axis}_bits"]) == exact_float[index], "exact SI rendering differs")
            require(float_from_bits(row[f"applied_{axis}_bits"]) == applied_float[index], "applied SI rendering differs")
            require(float_from_bits(row[f"error_{axis}_bits"]) == error_float[index], "error SI rendering differs")
        vector_rendered = float_from_bits(row["vector_error_bits"])
        vector_expected = math.sqrt(sum(value * value for value in error_float))
        require(
            math.isfinite(vector_rendered)
            and math.isclose(vector_rendered, vector_expected, rel_tol=1e-14, abs_tol=1e-25),
            "vector error rendering differs",
        )
        if path == "cartesian_nearest" and not angular:
            cartesian_torque += 1
        if path == "primitive_directional":
            require(angular, "directional drift generated torque")
            directional_exact += 1
            directional[(identifier, refinement, horizon, subdivision)] = {
                "displacement": displacement,
                "error": tuple(Fraction(value, refined_mass * refinement) for value in error),
                "base_applied": tuple(Fraction(value, refinement) for value in displacement),
            }
    require(cartesian_torque > 0, "Cartesian negative control lacks torque")
    require(directional_exact == 7 * 8 * 3 * 6, "directional exact row count differs")

    equal_rows = rows(raw / "equal_velocity.csv")
    require(len(equal_rows) == 8 * 3 * 6, "equal-velocity row count differs")
    for row in equal_rows:
        refinement = int(row["refinement"])
        horizon = int(row["horizon"])
        subdivision = int(row["subdivisions"])
        first = directional[(6, refinement, horizon, subdivision)]["displacement"]
        second = directional[(7, refinement, horizon, subdivision)]["displacement"]
        require(tuple(int(row[f"first_d{axis}"]) for axis in "xyz") == first, "equal-velocity first displacement differs")
        require(tuple(int(row[f"second_d{axis}"]) for axis in "xyz") == second, "equal-velocity second displacement differs")
        require(boolean(row["equal"]) and first == second, "equal velocities drift differently")

    com_rows = rows(raw / "center_of_mass.csv")
    require(len(com_rows) == 8 * 3 * 6, "COM row count differs")
    com_error: dict[tuple[int, int, int], tuple[Fraction, Fraction, Fraction]] = {}
    for row in com_rows:
        refinement = int(row["refinement"])
        horizon = int(row["horizon"])
        subdivision = int(row["subdivisions"])
        total_mass = sum(int(packets[index]["mass"]) for index in (2, 3, 4, 5))
        exact = [Fraction(0), Fraction(0), Fraction(0)]
        applied = [Fraction(0), Fraction(0), Fraction(0)]
        for identifier in (2, 3, 4, 5):
            packet = packets[identifier]
            mass = int(packet["mass"])
            momentum = packet["momentum"]
            assert isinstance(momentum, tuple)
            displacement = directional[(identifier, refinement, horizon, subdivision)]["base_applied"]
            for axis in range(3):
                exact[axis] += mass * Fraction(momentum[axis] * horizon, mass)
                applied[axis] += mass * displacement[axis]
        exact_tuple = tuple(value / total_mass for value in exact)
        applied_tuple = tuple(value / total_mass for value in applied)
        error_tuple = tuple(applied_tuple[index] - exact_tuple[index] for index in range(3))
        com_error[(refinement, horizon, subdivision)] = error_tuple
        for index, axis in enumerate("xyz"):
            require(abs(float_from_bits(row[f"exact_{axis}_bits"]) - float(exact_tuple[index])) < 1e-12, "COM exact rendering differs")
            require(abs(float_from_bits(row[f"applied_{axis}_bits"]) - float(applied_tuple[index])) < 1e-12, "COM applied rendering differs")
            require(abs(float_from_bits(row[f"error_{axis}_bits"]) - float(error_tuple[index])) < 1e-12, "COM error rendering differs")

    impulse_rows = rows(raw / "impulse_regression.csv")
    require(len(impulse_rows) == 6 * 4 * 5, "impulse regression row count differs")
    impulse_applied: dict[tuple[int, int], list[tuple[int, tuple[int, int, int], float]]] = defaultdict(list)
    for row in impulse_rows:
        relation = int(row["relation_index"])
        refinement = int(row["refinement"])
        subdivision = int(row["subdivisions"])
        target = float_from_bits(row["target_multiple_bits"])
        primitive = tuple(int(row[f"primitive_{axis}"]) for axis in "xyz")
        applied = int(row["applied_multiple"])
        expected = subdivision * nearest_even_double(target / float(subdivision))
        require(applied == expected, "inherited impulse rounding differs")
        require(boolean(row["linear_conserved"]) and boolean(row["angular_conserved"]), "inherited impulse conservation differs")
        residual = float_from_bits(row["kinetic_floor_residual_bits"])
        eq = float(Fraction(1, 4_096 * refinement**3))
        require(residual >= -1e-18 and residual < 2.0 * eq, "inherited kinetic floor differs")
        impulse_applied[(relation, refinement)].append((applied, primitive, target))

    impulse_pass: dict[int, bool] = {refinement: True for refinement in (16, 32, 64, 128)}
    for (relation, refinement), values in impulse_applied.items():
        del relation
        errors: list[float] = []
        components: list[tuple[float, float, float]] = []
        for applied, primitive, target in values:
            for axis in range(3):
                errors.append(abs(primitive[axis] * (target - applied)) / refinement**2)
            components.append(tuple(primitive[axis] * applied / refinement**2 for axis in range(3)))
        spread = max(
            abs(first[axis] - second[axis])
            for first in components for second in components for axis in range(3)
        )
        impulse_pass[refinement] = impulse_pass[refinement] and max(errors) < 1 / 32 and spread < 1 / 16
    require(all(impulse_pass.values()), "finer inherited impulse bridge failed")

    exact_summary: dict[int, dict[str, object]] = {}
    for refinement in REFINEMENTS:
        errors = [
            directional[(identifier, refinement, horizon, subdivision)]["error"]
            for identifier in packets for horizon in HORIZONS for subdivision in SUBDIVISIONS
        ]
        max_component = exact_max([abs(value) for vector in errors for value in vector])
        max_vector_squared = exact_max([sum(value * value for value in vector) for vector in errors])
        max_component_spread = Fraction(0)
        max_vector_spread_squared = Fraction(0)
        for identifier in packets:
            for horizon in HORIZONS:
                values = [
                    directional[(identifier, refinement, horizon, subdivision)]["base_applied"]
                    for subdivision in SUBDIVISIONS
                ]
                for first in values:
                    for second in values:
                        difference = tuple(first[index] - second[index] for index in range(3))
                        max_component_spread = max(max_component_spread, *(abs(value) for value in difference))
                        max_vector_spread_squared = max(max_vector_spread_squared, sum(value * value for value in difference))
        com_values = [value for key, value in com_error.items() if key[0] == refinement]
        max_com_component = exact_max([abs(value) for vector in com_values for value in vector])
        max_com_vector_squared = exact_max([sum(value * value for value in vector) for vector in com_values])
        passes = (
            refinement >= 16
            and impulse_pass.get(refinement, False)
            and max_component <= 1
            and max_vector_squared <= Fraction(9, 4)
            and max_component_spread <= 1
            and max_vector_spread_squared <= Fraction(9, 4)
            and max_com_component <= 1
            and max_com_vector_squared <= Fraction(9, 4)
        )
        exact_summary[refinement] = {
            "maximum_component_error": max_component,
            "maximum_vector_error_squared": max_vector_squared,
            "maximum_component_spread": max_component_spread,
            "maximum_vector_spread_squared": max_vector_spread_squared,
            "maximum_com_component_error": max_com_component,
            "maximum_com_vector_error_squared": max_com_vector_squared,
            "passes": passes,
        }
    selected = next((refinement for refinement in REFINEMENTS if exact_summary[refinement]["passes"]), 0)
    require(selected == 128, "exact selection does not resolve to R=128")

    summary_rows = rows(raw / "candidate_summary.csv")
    require(len(summary_rows) == len(REFINEMENTS), "candidate summary row count differs")
    for row, refinement in zip(summary_rows, REFINEMENTS, strict=True):
        require(int(row["refinement"]) == refinement, "summary refinement order differs")
        exact = exact_summary[refinement]
        require(boolean(row["passes"]) == exact["passes"], "summary pass differs")
        require(boolean(row["selected"]) == (refinement == selected), "summary selection differs")
        require(boolean(row["exact_gates"]) and boolean(row["equal_velocity"]), "summary exact gate differs")
        require(boolean(row["inherited_impulse"]) == impulse_pass.get(refinement, False), "summary impulse gate differs")
        numeric_checks = (
            ("maximum_component_error_bits", float(exact["maximum_component_error"])),
            ("maximum_vector_error_bits", math.sqrt(float(exact["maximum_vector_error_squared"]))),
            ("maximum_component_spread_bits", float(exact["maximum_component_spread"])),
            ("maximum_vector_spread_bits", math.sqrt(float(exact["maximum_vector_spread_squared"]))),
            ("maximum_com_component_error_bits", float(exact["maximum_com_component_error"])),
            ("maximum_com_vector_error_bits", math.sqrt(float(exact["maximum_com_vector_error_squared"]))),
        )
        for field, expected in numeric_checks:
            require(abs(float_from_bits(row[field]) - expected) < 1e-12, f"summary numeric differs: {field}")

    input_hashes = {filename: sha256(raw / filename) for filename in FILES}
    return {
        "schema": "mls.authoritative-drift-state-bridge.oracle.v1",
        "accepted_parent_sha": PARENT_SHA,
        "source_sha": meta["source_sha"],
        "decision": DECISION,
        "selected_refinement": selected,
        "selected_path": "primitive_directional",
        "evaluation_count": len(evaluation_rows),
        "cartesian_torque_rows": cartesian_torque,
        "directional_exact_rows": directional_exact,
        "parent_fingerprint_reproduced": True,
        "equal_velocity_consistent": True,
        "inherited_impulse_and_kinetic_gates": True,
        "safe_domain_chords_classified": True,
        "overflow_fail_closed": True,
        "explicit_remainder_evaluated": False,
        "input_sha256": input_hashes,
        "exact_refinement_summary": {
            str(refinement): {
                "maximum_component_error": fraction_text(exact_summary[refinement]["maximum_component_error"]),
                "maximum_vector_error_squared": fraction_text(exact_summary[refinement]["maximum_vector_error_squared"]),
                "maximum_component_spread": fraction_text(exact_summary[refinement]["maximum_component_spread"]),
                "maximum_vector_spread_squared": fraction_text(exact_summary[refinement]["maximum_vector_spread_squared"]),
                "maximum_com_component_error": fraction_text(exact_summary[refinement]["maximum_com_component_error"]),
                "maximum_com_vector_error_squared": fraction_text(exact_summary[refinement]["maximum_com_vector_error_squared"]),
                "passes": exact_summary[refinement]["passes"],
            }
            for refinement in REFINEMENTS
        },
        "promotion": "NO_PROMOTION",
    }


def write_summary(summary: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    csv_path = output.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            ["refinement", "maximum_component_error", "maximum_vector_error_squared",
             "maximum_component_spread", "maximum_vector_spread_squared",
             "maximum_com_component_error", "maximum_com_vector_error_squared", "passes"]
        )
        exact = summary["exact_refinement_summary"]
        assert isinstance(exact, dict)
        for refinement in REFINEMENTS:
            row = exact[str(refinement)]
            assert isinstance(row, dict)
            writer.writerow(
                [refinement, row["maximum_component_error"],
                 row["maximum_vector_error_squared"], row["maximum_component_spread"],
                 row["maximum_vector_spread_squared"], row["maximum_com_component_error"],
                 row["maximum_com_vector_error_squared"],
                 "true" if row["passes"] else "false"]
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        summary = verify(arguments.raw.resolve())
        write_summary(summary, arguments.output.resolve())
    except (OSError, ValueError, KeyError, OracleError, csv.Error) as error:
        print(f"AUTHORITATIVE DRIFT STATE BRIDGE ORACLE: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "AUTHORITATIVE DRIFT STATE BRIDGE ORACLE: PASS "
        f"R={summary['selected_refinement']} rows={summary['evaluation_count']} "
        "NO_PROMOTION"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
