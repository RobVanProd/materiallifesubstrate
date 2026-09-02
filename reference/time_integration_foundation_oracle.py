#!/usr/bin/env python3
"""Independent high-precision oracle for the Time Integration Foundation Lab."""

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
from decimal import Decimal, getcontext
from fractions import Fraction
from pathlib import Path


PARENT_SHA = "ffefb2ea9ee0f032946af4ed23acd12883f20cfe"
PARENT_TAG = "authoritative-drift-state-bridge-lab-evidence-v1"
PARENT_TAG_OBJECT = "5a6237a9dcbe676aa4c89c10d5f9f94e935507e6"
BRANCH = "time-integration-foundation-lab"
SHA1 = re.compile(r"[0-9a-f]{40}")
KDK = "quantized_kick_drift_kick"
CONTROL = "symplectic_euler_control"
TIMESTEPS = (62_500_000, 31_250_000, 15_625_000, 7_812_500, 3_906_250)
STEP_COUNTS = (16, 32, 64, 128, 256)
CONVERGENCE_SCENARIOS = (
    "k4_breathing",
    "k4_internal",
    "octahedron_deformation",
)
FILES = (
    "metadata.csv",
    "units.csv",
    "parent_fingerprint.csv",
    "rounding_controls.csv",
    "reference_packets.csv",
    "relations.csv",
    "force_operator.csv",
    "initial_states.csv",
    "endpoints.csv",
    "energies.csv",
    "reversibility.csv",
    "covariance.csv",
    "checkpoint.csv",
    "domain.csv",
    "long_energy.csv",
)
SCHEMAS = {
    "metadata.csv": "key,value",
    "units.csv": "refinement,Lq,Mq,Tq,Pq,Eq,Fq",
    "parent_fingerprint.csv": "case,passed",
    "rounding_controls.csv": "numerator,denominator,nearest_even",
    "reference_packets.csv": "model_id,packet_id,x_raw,y_raw,z_raw,mass_raw",
    "relations.csv": "model_id,relation_index,first_id,second_id,rest_length_bits",
    "force_operator.csv": "model_id,row,column,h_bits",
    "initial_states.csv": (
        "scenario_id,model_id,convergence,packet_id,x_raw,y_raw,z_raw,"
        "px_raw,py_raw,pz_raw,mass_raw"
    ),
    "endpoints.csv": (
        "scenario_id,path,level,dt_raw,steps,status,completed_steps,packet_id,"
        "time_raw,x_raw,y_raw,z_raw,px_raw,py_raw,pz_raw,momentum_preserved,"
        "angular_preserved"
    ),
    "energies.csv": "scenario_id,path,level,sample,dt_raw,mechanical_energy_bits",
    "reversibility.csv": (
        "scenario_id,level,dt_raw,steps,forward_status,backward_status,"
        "initial_hash,recovered_hash,bit_identical"
    ),
    "covariance.csv": (
        "kind,level,dt_raw,position_discrepancy_raw,momentum_discrepancy_raw,exact"
    ),
    "checkpoint.csv": (
        "scenario_id,dt_raw,steps,checkpoint_step,checkpoint_hash,decoded_hash,"
        "whole_final_hash,resumed_final_hash,event_suffix_identical"
    ),
    "domain.csv": (
        "scenario_id,status,failed_relation_index,first_id,second_id,time_unchanged,"
        "momentum_unchanged,state_unchanged,energy_before_bits,energy_after_evaluated"
    ),
    "long_energy.csv": "scenario_id,dt_raw,sample,mechanical_energy_bits",
}

getcontext().prec = 110


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
    return Fraction(int(numerator), int(denominator))


def mp_fraction(value: Fraction) -> Decimal:
    return Decimal(value.numerator) / Decimal(value.denominator)


def float_from_bits(value: str) -> float:
    integer = int(value)
    require(0 <= integer < 2**64, "binary64 bits outside uint64")
    return struct.unpack(">d", struct.pack(">Q", integer))[0]


def mp_from_bits(value: str) -> Decimal:
    numerator, denominator = float_from_bits(value).as_integer_ratio()
    return Decimal(numerator) / Decimal(denominator)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def group(rows_: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows_:
        result[row[key]].append(row)
    return dict(result)


def verify_schemas(raw: Path) -> None:
    require(set(SCHEMAS) == set(FILES), "schema inventory differs")
    for filename, expected in SCHEMAS.items():
        with (raw / filename).open(encoding="utf-8", newline="") as stream:
            actual = stream.readline().rstrip("\r\n")
        require(actual == expected, f"{filename}: raw schema differs")


def verify_metadata(raw: Path) -> tuple[Fraction, Fraction, Fraction]:
    meta = metadata(raw / "metadata.csv")
    expected = {
        "schema": "mls.time-integration-foundation.raw.v1",
        "accepted_parent_sha": PARENT_SHA,
        "accepted_parent_tag": PARENT_TAG,
        "accepted_parent_tag_object": PARENT_TAG_OBJECT,
        "branch": BRANCH,
        "selected_refinement": "128",
        "candidate": KDK,
        "negative_control": CONTROL,
        "safe_domain": "2^-24",
        "position_remainder_present": "false",
        "energy_discrepancy_stored": "false",
        "promotion": "NO_PROMOTION",
    }
    for key, value in expected.items():
        require(meta.get(key) == value, f"metadata {key} differs")
    require(meta.get("source_dirty") == "false", "source materialization is dirty")
    require(SHA1.fullmatch(meta.get("source_sha", "")) is not None, "source SHA malformed")
    require(
        meta.get("configured_source_branch") == BRANCH,
        "configured source branch differs",
    )
    unit_rows = rows(raw / "units.csv")
    require(len(unit_rows) == 1 and unit_rows[0]["refinement"] == "128", "unit row differs")
    unit = unit_rows[0]
    length = Fraction(1, 128_000_000_000)
    mass = Fraction(1, 524_288)
    time = Fraction(1, 1_000_000_000)
    momentum = Fraction(1, 67_108_864)
    energy = Fraction(1, 8_589_934_592)
    force = Fraction(1_953_125, 131_072)
    require(parse_ratio(unit["Lq"]) == length, "Lq differs")
    require(parse_ratio(unit["Mq"]) == mass, "Mq differs")
    require(parse_ratio(unit["Tq"]) == time, "Tq differs")
    require(parse_ratio(unit["Pq"]) == momentum, "Pq differs")
    require(parse_ratio(unit["Eq"]) == energy, "Eq differs")
    require(parse_ratio(unit["Fq"]) == force, "Fq differs")
    fingerprints = rows(raw / "parent_fingerprint.csv")
    require(len(fingerprints) == 5, "parent fingerprint count differs")
    require(all(boolean(row["passed"]) for row in fingerprints), "parent fingerprint failed")
    require(
        {row["case"] for row in fingerprints}
        == {
            "accepted_R128_impulse",
            "accepted_R128_drift",
            "cartesian_torque_control",
            "safe_chord",
            "crossing_chord",
        },
        "parent fingerprint inventory differs",
    )
    controls = rows(raw / "rounding_controls.csv")
    require(len(controls) == 8, "rounding control count differs")
    for row in controls:
        value = Fraction(int(row["numerator"]), int(row["denominator"]))
        floor_value = value.numerator // value.denominator
        remainder = value.numerator - floor_value * value.denominator
        if 2 * remainder < value.denominator:
            expected_round = floor_value
        elif 2 * remainder > value.denominator:
            expected_round = floor_value + 1
        else:
            expected_round = floor_value if floor_value % 2 == 0 else floor_value + 1
        require(int(row["nearest_even"]) == expected_round, "nearest-even control differs")
    return length, mass, momentum


class Model:
    def __init__(
        self,
        packet_ids: list[int],
        masses: list[Decimal],
        reference: list[list[Decimal]],
        relations: list[tuple[int, int]],
        h: list[list[Decimal]],
    ) -> None:
        self.packet_ids = packet_ids
        self.masses = masses
        self.reference = reference
        self.relations = relations
        self.h = h
        self.index = {identifier: index for index, identifier in enumerate(packet_ids)}
        self.reference_lengths = [
            (
                sum(
                    ((reference[self.index[second]][axis] -
                      reference[self.index[first]][axis]) ** 2
                     for axis in range(3)),
                    Decimal(0),
                )
            ).sqrt()
            for first, second in relations
        ]

    def force_and_energy(self, position: list[list[Decimal]]) -> tuple[list[list[Decimal]], Decimal]:
        directions: list[list[Decimal]] = []
        extensions: list[Decimal] = []
        for relation_index, (first, second) in enumerate(self.relations):
            offset = [
                position[self.index[second]][axis] - position[self.index[first]][axis]
                for axis in range(3)
            ]
            length = sum((value * value for value in offset), Decimal(0)).sqrt()
            require(length > 0, "oracle trajectory reached exact coincidence")
            directions.append([value / length for value in offset])
            extensions.append(length - self.reference_lengths[relation_index])
        conjugate = [
            sum(self.h[row][column] * extensions[column] for column in range(len(extensions)))
            for row in range(len(extensions))
        ]
        force = [[Decimal(0), Decimal(0), Decimal(0)] for _ in self.packet_ids]
        for relation_index, (first, second) in enumerate(self.relations):
            for axis in range(3):
                value = conjugate[relation_index] * directions[relation_index][axis]
                force[self.index[first]][axis] += value
                force[self.index[second]][axis] -= value
        energy = sum(
            (extensions[index] * conjugate[index]
             for index in range(len(extensions))),
            Decimal(0),
        ) / 2
        return force, energy


def verify_registered_models(raw: Path) -> None:
    grouped = group(rows(raw / "reference_packets.csv"), "model_id")
    require(
        set(grouped) == {"k4", "k4_translated", "k4_rotated", "octahedron", "pair"},
        "registered model IDs differ",
    )
    metre = 128_000_000_000
    kilogram = 524_288
    k4 = {
        1: (0, 0, 0),
        2: (metre, 0, 0),
        3: (0, metre, 0),
        4: (0, 0, metre),
    }
    shift = (17 * metre, -11 * metre, 7 * metre)
    expected: dict[str, dict[int, tuple[int, int, int]]] = {
        "k4": k4,
        "k4_translated": {
            identifier: tuple(value[axis] + shift[axis] for axis in range(3))
            for identifier, value in k4.items()
        },
        "k4_rotated": {
            identifier: (-value[1], value[0], value[2])
            for identifier, value in k4.items()
        },
        "octahedron": {
            1: (metre, 0, 0),
            2: (-metre, 0, 0),
            3: (0, metre, 0),
            4: (0, -metre, 0),
            5: (0, 0, metre),
            6: (0, 0, -metre),
        },
        "pair": {1: (-metre, 0, 0), 2: (metre, 0, 0)},
    }
    for model_id, model_rows in grouped.items():
        actual: dict[int, tuple[int, int, int]] = {}
        for row in model_rows:
            identifier = int(row["packet_id"])
            require(identifier not in actual, f"{model_id}: duplicate reference packet")
            require(int(row["mass_raw"]) == kilogram, f"{model_id}: reference mass differs")
            actual[identifier] = tuple(int(row[f"{axis}_raw"]) for axis in "xyz")
        require(actual == expected[model_id], f"{model_id}: reference coordinates differ")

    relation_groups = group(rows(raw / "relations.csv"), "model_id")
    k4_edges = {(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4)}
    octa_edges = {
        (first, second)
        for first in range(1, 7)
        for second in range(first + 1, 7)
        if (first, second) not in {(1, 2), (3, 4), (5, 6)}
    }
    expected_edges = {
        "k4": k4_edges,
        "k4_translated": k4_edges,
        "k4_rotated": k4_edges,
        "octahedron": octa_edges,
        "pair": {(1, 2)},
    }
    for model_id, relation_rows in relation_groups.items():
        actual = {(int(row["first_id"]), int(row["second_id"])) for row in relation_rows}
        require(actual == expected_edges[model_id], f"{model_id}: relation topology differs")


def expected_local_collective_h(model: Model) -> list[list[Decimal]]:
    count = len(model.relations)
    result = [[Decimal(0) for _ in range(count)] for _ in range(count)]
    a_coefficient = Decimal(3) / 10
    b_coefficient = Decimal(1) / 4
    for packet_id in model.packet_ids:
        incident = [
            index
            for index, relation in enumerate(model.relations)
            if packet_id in relation
        ]
        moment = sum(
            (model.reference_lengths[index] ** 2 for index in incident),
            Decimal(0),
        )
        require(moment > 0, "oracle local moment is not positive")
        for row in incident:
            for column in incident:
                result[row][column] += (
                    a_coefficient
                    * model.reference_lengths[row]
                    * model.reference_lengths[column]
                    / moment
                )
        for residual in incident:
            projection = [Decimal(0) for _ in range(count)]
            for row in incident:
                projection[row] = (
                    (Decimal(1) if row == residual else Decimal(0))
                    - model.reference_lengths[residual]
                    * model.reference_lengths[row]
                    / moment
                )
            for row in incident:
                for column in incident:
                    result[row][column] += (
                        b_coefficient * projection[row] * projection[column]
                    )
    return result


def load_models(raw: Path, lq: Fraction, mq: Fraction) -> dict[str, Model]:
    verify_registered_models(raw)
    packet_rows = group(rows(raw / "reference_packets.csv"), "model_id")
    relation_rows = group(rows(raw / "relations.csv"), "model_id")
    operator_rows = group(rows(raw / "force_operator.csv"), "model_id")
    require(set(packet_rows) == set(relation_rows) == set(operator_rows), "model inventories differ")
    result: dict[str, Model] = {}
    for model_id in sorted(packet_rows):
        packets = sorted(packet_rows[model_id], key=lambda row: int(row["packet_id"]))
        packet_ids = [int(row["packet_id"]) for row in packets]
        reference = [
            [mp_fraction(int(row[f"{axis}_raw"]) * lq) for axis in "xyz"]
            for row in packets
        ]
        masses = [mp_fraction(int(row["mass_raw"]) * mq) for row in packets]
        relations_raw = sorted(
            relation_rows[model_id], key=lambda row: int(row["relation_index"])
        )
        require(
            [int(row["relation_index"]) for row in relations_raw]
            == list(range(len(relations_raw))),
            f"{model_id}: relation order differs",
        )
        relations = [(int(row["first_id"]), int(row["second_id"])) for row in relations_raw]
        count = len(relations)
        h = [[Decimal(0) for _ in range(count)] for _ in range(count)]
        seen: set[tuple[int, int]] = set()
        for row in operator_rows[model_id]:
            index = (int(row["row"]), int(row["column"]))
            require(index not in seen, f"{model_id}: duplicate H entry")
            seen.add(index)
            h[index[0]][index[1]] = mp_from_bits(row["h_bits"])
        require(len(seen) == count * count, f"{model_id}: incomplete H")
        require(
            all(h[i][j] == h[j][i] for i in range(count) for j in range(count)),
            f"{model_id}: H is not symmetric",
        )
        for index, row in enumerate(relations_raw):
            exported = mp_from_bits(row["rest_length_bits"])
            reconstructed = (
                sum(
                    ((
                        reference[packet_ids.index(relations[index][1])][axis]
                        - reference[packet_ids.index(relations[index][0])][axis]
                    )
                    ** 2
                     for axis in range(3)),
                    Decimal(0),
                )
            ).sqrt()
            require(
                abs(exported - reconstructed) <= Decimal(2) ** -51 * max(Decimal(1), reconstructed),
                f"{model_id}: frozen reference length differs",
            )
        model = Model(packet_ids, masses, reference, relations, h)
        expected_h = expected_local_collective_h(model)
        require(
            all(
                abs(h[row][column] - expected_h[row][column]) <= Decimal("5e-15")
                for row in range(count)
                for column in range(count)
            ),
            f"{model_id}: frozen H differs from the registered collective law",
        )
        result[model_id] = model
    return result


def load_initial_states(
    raw: Path, lq: Fraction, pq: Fraction
) -> tuple[dict[str, tuple[str, list[list[Decimal]], list[list[Decimal]]]], set[str]]:
    grouped = group(rows(raw / "initial_states.csv"), "scenario_id")
    result: dict[str, tuple[str, list[list[Decimal]], list[list[Decimal]]]] = {}
    convergence: set[str] = set()
    for scenario, scenario_rows in grouped.items():
        values = sorted(scenario_rows, key=lambda row: int(row["packet_id"]))
        model_ids = {row["model_id"] for row in values}
        flags = {boolean(row["convergence"]) for row in values}
        require(len(model_ids) == 1 and len(flags) == 1, f"{scenario}: initial metadata differs")
        if True in flags:
            convergence.add(scenario)
        position = [
            [mp_fraction(int(row[f"{axis}_raw"]) * lq) for axis in "xyz"]
            for row in values
        ]
        momentum = [
            [mp_fraction(int(row[f"p{axis}_raw"]) * pq) for axis in "xyz"]
            for row in values
        ]
        result[scenario] = (next(iter(model_ids)), position, momentum)
    require(convergence == set(CONVERGENCE_SCENARIOS), "convergence scenario inventory differs")
    return result, convergence


def derivative(model: Model, state: list[Decimal]) -> list[Decimal]:
    count = len(model.packet_ids)
    position = [[state[3 * i + axis] for axis in range(3)] for i in range(count)]
    momentum_offset = 3 * count
    momentum = [
        [state[momentum_offset + 3 * i + axis] for axis in range(3)]
        for i in range(count)
    ]
    force, _ = model.force_and_energy(position)
    result: list[Decimal] = []
    for index in range(count):
        result.extend(momentum[index][axis] / model.masses[index] for axis in range(3))
    for value in force:
        result.extend(value)
    return result


def rk4(model: Model, initial: list[Decimal], steps: int) -> list[Decimal]:
    h = Decimal(1) / steps
    half = h / 2
    sixth = h / 6
    state = list(initial)
    for _ in range(steps):
        k1 = derivative(model, state)
        k2 = derivative(model, [state[i] + half * k1[i] for i in range(len(state))])
        k3 = derivative(model, [state[i] + half * k2[i] for i in range(len(state))])
        k4 = derivative(model, [state[i] + h * k3[i] for i in range(len(state))])
        state = [
            state[i] + sixth * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i])
            for i in range(len(state))
        ]
    return state


def extrapolated_rk4(model: Model, initial: list[Decimal], base: int, levels: int) -> list[Decimal]:
    table: list[list[list[Decimal]]] = []
    for level in range(levels):
        table.append([rk4(model, initial, base * 2**level)])
        for column in range(1, level + 1):
            exponent = 4 + column - 1
            denominator = Decimal(2) ** exponent - 1
            previous = table[level][column - 1]
            coarser = table[level - 1][column - 1]
            table[level].append(
                [
                    previous[index] + (previous[index] - coarser[index]) / denominator
                    for index in range(len(previous))
                ]
            )
    return table[-1][-1]


def state_norm_difference(first: list[Decimal], second: list[Decimal], count: int) -> Decimal:
    return (
        sum(((first[i] - second[i]) ** 2 for i in range(len(first))), Decimal(0))
        / count
    ).sqrt()


def oracle_states(
    models: dict[str, Model],
    initial_states: dict[str, tuple[str, list[list[Decimal]], list[list[Decimal]]]],
) -> tuple[dict[str, list[Decimal]], dict[str, Decimal]]:
    results: dict[str, list[Decimal]] = {}
    refinements: dict[str, Decimal] = {}
    for scenario in CONVERGENCE_SCENARIOS:
        model_id, position, momentum = initial_states[scenario]
        model = models[model_id]
        initial = [value for vector in position for value in vector]
        initial.extend(value for vector in momentum for value in vector)
        first = extrapolated_rk4(model, initial, 128, 6)
        second = extrapolated_rk4(model, initial, 256, 6)
        difference = state_norm_difference(first, second, len(model.packet_ids))
        require(difference <= Decimal(2) ** -70, f"{scenario}: oracle refinement gate failed: {difference}")
        results[scenario] = second
        refinements[scenario] = difference
    return results, refinements


def load_endpoint_states(
    raw: Path, lq: Fraction, pq: Fraction
) -> dict[tuple[str, str, int], list[Decimal]]:
    grouped: dict[tuple[str, str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows(raw / "endpoints.csv"):
        key = (row["scenario_id"], row["path"], int(row["level"]))
        grouped[key].append(row)
    result: dict[tuple[str, str, int], list[Decimal]] = {}
    for key, endpoint_rows in grouped.items():
        level = key[2]
        require(int(endpoint_rows[0]["dt_raw"]) == TIMESTEPS[level], "endpoint timestep differs")
        require(int(endpoint_rows[0]["steps"]) == STEP_COUNTS[level], "endpoint step count differs")
        require(all(row["status"] == "accepted" for row in endpoint_rows), f"{key}: trajectory failed")
        require(
            all(int(row["completed_steps"]) == STEP_COUNTS[level] for row in endpoint_rows),
            f"{key}: incomplete trajectory",
        )
        require(
            all(boolean(row["momentum_preserved"]) and boolean(row["angular_preserved"]) for row in endpoint_rows),
            f"{key}: exact invariant failure",
        )
        values = sorted(endpoint_rows, key=lambda row: int(row["packet_id"]))
        state = [mp_fraction(int(row[f"{axis}_raw"]) * lq) for row in values for axis in "xyz"]
        state.extend(mp_fraction(int(row[f"p{axis}_raw"]) * pq) for row in values for axis in "xyz")
        result[key] = state
    expected = {
        (scenario, path, level)
        for scenario in CONVERGENCE_SCENARIOS
        for path in (CONTROL, KDK)
        for level in range(5)
    }
    require(set(result) == expected, "endpoint trajectory inventory differs")
    return result


def exact_invariants_from_rows(
    state_rows: list[dict[str, str]], momentum_prefix: str = "p"
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    total_p = [0, 0, 0]
    total_l = [0, 0, 0]
    for row in state_rows:
        x = tuple(int(row[f"{axis}_raw"]) for axis in "xyz")
        p = tuple(int(row[f"{momentum_prefix}{axis}_raw"]) for axis in "xyz")
        for axis in range(3):
            total_p[axis] += p[axis]
        total_l[0] += x[1] * p[2] - x[2] * p[1]
        total_l[1] += x[2] * p[0] - x[0] * p[2]
        total_l[2] += x[0] * p[1] - x[1] * p[0]
    return tuple(total_p), tuple(total_l)


def verify_endpoint_invariants(raw: Path) -> bool:
    initial = group(rows(raw / "initial_states.csv"), "scenario_id")
    endpoints: dict[tuple[str, str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows(raw / "endpoints.csv"):
        endpoints[(row["scenario_id"], row["path"], int(row["level"]))].append(row)
    result = True
    for key, state_rows in endpoints.items():
        scenario = key[0]
        expected = exact_invariants_from_rows(initial[scenario])
        actual = exact_invariants_from_rows(state_rows)
        declared = all(
            boolean(row["momentum_preserved"]) and boolean(row["angular_preserved"])
            for row in state_rows
        )
        result = result and actual == expected and declared == (actual == expected)
    return result


def contains_successive_window(orders: list[float], low: float, high: float, count: int) -> bool:
    return any(
        all(low <= value <= high for value in orders[start : start + count])
        for start in range(len(orders) - count + 1)
    )


def verify_convergence(
    endpoints: dict[tuple[str, str, int], list[Decimal]],
    oracle: dict[str, list[Decimal]],
) -> tuple[dict[str, object], bool]:
    report: dict[str, object] = {}
    passed = True
    floor = Decimal(64) * max(
        Decimal(1) / 128_000_000_000,
        Decimal(1) / 67_108_864,
    )
    for scenario in CONVERGENCE_SCENARIOS:
        scenario_report: dict[str, object] = {}
        path_orders: dict[str, list[float]] = {}
        for path in (CONTROL, KDK):
            errors = [
                state_norm_difference(endpoints[(scenario, path, level)], oracle[scenario],
                                      len(endpoints[(scenario, path, level)]) // 6)
                for level in range(5)
            ]
            orders = [math.log2(float(errors[i] / errors[i + 1])) for i in range(4)]
            path_orders[path] = orders
            systematic_worsening = all(
                errors[index + 1] > Decimal("1.05") * errors[index]
                for index in range(2, 4)
            ) and errors[2] <= floor
            scenario_report[path] = {
                "errors": [format(value, ".29E") for value in errors],
                "orders": orders,
                "systematic_worsening": systematic_worsening,
            }
        kdk_window = contains_successive_window(path_orders[KDK], 1.6, 2.4, 3)
        control_window = contains_successive_window(path_orders[CONTROL], 0.6, 1.4, 2)
        order_separation = max(path_orders[KDK], default=-math.inf) - max(
            path_orders[CONTROL], default=math.inf
        ) >= 0.5
        scenario_pass = kdk_window and control_window and order_separation
        scenario_report["passes"] = scenario_pass
        passed = passed and scenario_pass
        report[scenario] = scenario_report
    return report, passed


def verify_energy(raw: Path) -> tuple[dict[str, object], bool]:
    grouped: dict[tuple[str, str, int], list[float]] = defaultdict(list)
    for row in rows(raw / "energies.csv"):
        key = (row["scenario_id"], row["path"], int(row["level"]))
        grouped[key].append(float_from_bits(row["mechanical_energy_bits"]))
    report: dict[str, object] = {}
    passed = True
    for scenario in CONVERGENCE_SCENARIOS:
        envelopes: dict[str, list[float]] = {}
        for path in (CONTROL, KDK):
            values = []
            for level in range(5):
                energy = grouped[(scenario, path, level)]
                require(len(energy) == STEP_COUNTS[level] + 1, f"{scenario}/{path}: energy samples differ")
                values.append(max(abs(value - energy[0]) for value in energy))
            envelopes[path] = values
        kdk_orders = [math.log2(envelopes[KDK][i] / envelopes[KDK][i + 1]) for i in range(4)]
        control_orders = [math.log2(envelopes[CONTROL][i] / envelopes[CONTROL][i + 1]) for i in range(4)]
        kdk_pass = contains_successive_window(kdk_orders, 1.5, 2.5, 3)
        control_pass = contains_successive_window(control_orders, 0.5, 1.5, 2)
        scenario_pass = kdk_pass and control_pass
        report[scenario] = {
            "candidate_envelopes": envelopes[KDK],
            "candidate_orders": kdk_orders,
            "control_envelopes": envelopes[CONTROL],
            "control_orders": control_orders,
            "passes": scenario_pass,
        }
        passed = passed and scenario_pass

    long_values = [float_from_bits(row["mechanical_energy_bits"]) for row in rows(raw / "long_energy.csv")]
    require(len(long_values) == 1025, "long-run energy sample count differs")
    error = [value - long_values[0] for value in long_values]
    mean = sum(error) / len(error)
    x_mean = (len(error) - 1) / 2
    slope = sum((index - x_mean) * (value - mean) for index, value in enumerate(error)) / sum(
        (index - x_mean) ** 2 for index in range(len(error))
    )
    quarters = [error[(len(error) - 1) * index // 4] for index in range(1, 5)]
    secular = (
        all(value > 0 for value in quarters)
        or all(value < 0 for value in quarters)
    ) and all(abs(quarters[index]) > abs(quarters[index - 1]) for index in range(1, 4))
    report["long_run"] = {
        "maximum_excursion": max(abs(value) for value in error),
        "mean_offset": mean,
        "final_error": error[-1],
        "least_squares_slope_per_sample": slope,
        "secular": secular,
    }
    return report, passed


def verify_exact_gates(raw: Path) -> tuple[dict[str, object], bool, bool, bool]:
    reversibility = rows(raw / "reversibility.csv")
    require(len(reversibility) == 30, "reversibility row count differs")
    reversible = all(
        row["forward_status"] == "accepted"
        and row["backward_status"] == "accepted"
        and row["initial_hash"] == row["recovered_hash"]
        and boolean(row["bit_identical"])
        for row in reversibility
    )
    covariance = group(rows(raw / "covariance.csv"), "kind")
    require(set(covariance) == {"translation", "galilean_boost", "proper_lattice_rotation"},
            "covariance inventory differs")
    translation = all(
        int(row["position_discrepancy_raw"]) == 0
        and int(row["momentum_discrepancy_raw"]) == 0
        and boolean(row["exact"])
        for row in covariance["translation"]
    )
    rotation = all(
        int(row["position_discrepancy_raw"]) == 0
        and int(row["momentum_discrepancy_raw"]) == 0
        and boolean(row["exact"])
        for row in covariance["proper_lattice_rotation"]
    )
    boost_rows = sorted(covariance["galilean_boost"], key=lambda row: int(row["level"]))
    require(len(boost_rows) == 5, "boost level count differs")
    floor_reached = False
    boost_pass = True
    previous = None
    boost_values: list[tuple[int, int]] = []
    for row in boost_rows:
        position = int(row["position_discrepancy_raw"])
        momentum = int(row["momentum_discrepancy_raw"])
        boost_values.append((position, momentum))
        combined = max(position, momentum)
        if floor_reached:
            boost_pass = boost_pass and combined <= 128
        elif combined <= 64:
            floor_reached = True
        elif previous is not None:
            boost_pass = boost_pass and combined < previous
        previous = combined
    checkpoint_rows = rows(raw / "checkpoint.csv")
    require(len(checkpoint_rows) == 1, "checkpoint row count differs")
    checkpoint = checkpoint_rows[0]
    checkpoint_pass = (
        checkpoint["checkpoint_hash"] == checkpoint["decoded_hash"]
        and checkpoint["whole_final_hash"] == checkpoint["resumed_final_hash"]
        and boolean(checkpoint["event_suffix_identical"])
    )
    domain_rows = rows(raw / "domain.csv")
    require(len(domain_rows) == 1, "domain row count differs")
    domain = domain_rows[0]
    domain_pass = (
        domain["status"] == "chord_domain_failure"
        and domain["first_id"] == "1"
        and domain["second_id"] == "2"
        and boolean(domain["time_unchanged"])
        and boolean(domain["momentum_unchanged"])
        and boolean(domain["state_unchanged"])
        and not boolean(domain["energy_after_evaluated"])
    )
    report = {
        "reversibility_rows": len(reversibility),
        "reversible": reversible,
        "translation_exact": translation,
        "proper_lattice_rotation_exact": rotation,
        "boost_discrepancies_raw": boost_values,
        "boost_pass": boost_pass,
        "checkpoint_pass": checkpoint_pass,
        "domain_atomic": domain_pass,
    }
    composition_pass = all(
        boolean(row["momentum_preserved"]) and boolean(row["angular_preserved"])
        for row in rows(raw / "endpoints.csv")
    )
    return report, composition_pass and checkpoint_pass and translation and rotation, reversible, boost_pass and domain_pass


def verify(
    raw: Path,
    precomputed_oracle: tuple[dict[str, list[Decimal]], dict[str, Decimal]] | None = None,
) -> dict[str, object]:
    for filename in FILES:
        require((raw / filename).is_file(), f"missing raw file {filename}")
    verify_schemas(raw)
    lq, mq, pq = verify_metadata(raw)
    models = load_models(raw, lq, mq)
    initial_states, _ = load_initial_states(raw, lq, pq)
    if precomputed_oracle is None:
        oracle, refinements = oracle_states(models, initial_states)
    else:
        oracle, refinements = precomputed_oracle
    endpoints = load_endpoint_states(raw, lq, pq)
    convergence, convergence_pass = verify_convergence(endpoints, oracle)
    energy, energy_pass = verify_energy(raw)
    exact, composition_pass, reversible, frame_and_domain = verify_exact_gates(raw)
    endpoint_invariants = verify_endpoint_invariants(raw)
    exact["endpoint_invariants_independently_recomputed"] = endpoint_invariants
    composition_pass = composition_pass and endpoint_invariants

    domain_atomic = bool(exact["domain_atomic"])
    boost_pass = bool(exact["boost_pass"])
    if not composition_pass:
        decision = "reject_quantized_time_composition"
    elif not reversible:
        decision = "reject_quantized_verlet_reversibility"
    elif not convergence_pass or not energy_pass:
        decision = "temporal_convergence_blocked_by_authoritative_quantization"
    elif not boost_pass:
        decision = "reject_quantized_dynamics_frame_covariance"
    elif not domain_atomic or not frame_and_domain:
        decision = "reject_time_domain_safety"
    else:
        decision = "retain_quantized_stormer_verlet_dynamics_candidate_for_research"

    return {
        "schema": "mls.time-integration-foundation.oracle.v1",
        "precision_decimal_digits": getcontext().prec,
        "oracle_method": "independent high-precision RK4 Richardson extrapolation",
        "oracle_refinement_errors": {
            key: format(value, ".29E") for key, value in refinements.items()
        },
        "convergence": convergence,
        "energy": energy,
        "exact_gates": exact,
        "decision": decision,
        "promotion": "NO_PROMOTION",
        "raw_files": {filename: sha256(raw / filename) for filename in FILES},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        result = verify(arguments.raw)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"TIME INTEGRATION FOUNDATION ORACLE: PASS {result['decision']} NO_PROMOTION")
        return 0
    except (OSError, ValueError, ArithmeticError, OracleError) as error:
        print(f"TIME INTEGRATION FOUNDATION ORACLE: FAIL {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
