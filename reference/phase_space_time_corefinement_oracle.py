#!/usr/bin/env python3
"""Independent oracle for the Phase-Space/Time Co-Refinement Lab."""

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

import time_integration_foundation_oracle as foundation


PARENT_SHA = "243d52938ef22f7bf37e4e37decbe209bec504cf"
PARENT_TAG = "time-integration-foundation-lab-evidence-v1"
PARENT_TAG_OBJECT = "855e89d86fa0192f7cd24a9743e545f588335c44"
PARENT_ARCHIVE_SHA256 = (
    "d2c8f6e468a5f81c60ba4300276b6b301e1f4ab966eb4198bc4e3a02bff55dbb"
)
BRANCH = "phase-space-time-corefinement-lab"
KDK = "quantized_kick_drift_kick"
CONTROL = "symplectic_euler_control"
LEVELS = tuple(range(5))
TIMESTEPS = (62_500_000, 250_000_000, 1_000_000_000, 4_000_000_000, 16_000_000_000)
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
    "mapping.csv",
    "reference_packets.csv",
    "relations.csv",
    "force_operator.csv",
    "initial_states.csv",
    "endpoints.csv",
    "energies.csv",
    "primitive_diagnostics.csv",
    "relation_primitive_diagnostics.csv",
    "reversibility.csv",
    "covariance.csv",
    "checkpoint.csv",
    "domain.csv",
    "bridge_contracts.csv",
    "long_energy.csv",
)
SCHEMAS = {
    "metadata.csv": "key,value",
    "units.csv": "level,Lq,Mq,Tq,Pq,Eq,Fq,dt_raw,steps,unit_contract_valid",
    "parent_fingerprint.csv": "case,observed,expected,passed",
    "mapping.csv": "scenario_id,model_id,level,status,detail",
    "reference_packets.csv": "model_id,level,packet_id,x_raw,y_raw,z_raw,mass_raw",
    "relations.csv": "model_id,relation_index,first_id,second_id,rest_length_bits",
    "force_operator.csv": "model_id,row,column,h_bits",
    "initial_states.csv": (
        "scenario_id,model_id,convergence,level,packet_id,x_raw,y_raw,z_raw,"
        "px_raw,py_raw,pz_raw,mass_raw"
    ),
    "endpoints.csv": (
        "scenario_id,path,level,dt_raw,steps,status,completed_steps,packet_id,"
        "time_raw,x_raw,y_raw,z_raw,px_raw,py_raw,pz_raw,momentum_preserved,"
        "angular_preserved"
    ),
    "energies.csv": "scenario_id,path,level,sample,dt_raw,mechanical_energy_bits",
    "primitive_diagnostics.csv": (
        "scenario_id,path,level,step,stage,packet_id,px_raw,py_raw,pz_raw,g,"
        "ux,uy,uz,primitive_norm_squared_ld,minimum_drift_m_bits"
    ),
    "relation_primitive_diagnostics.csv": (
        "scenario_id,path,level,step,stage,relation_index,first_id,second_id,"
        "rx_raw,ry_raw,rz_raw,g,ux,uy,uz,target_multiple_bits,applied_multiple,"
        "minimum_impulse_bits"
    ),
    "reversibility.csv": (
        "scenario_id,level,dt_raw,steps,forward_status,backward_status,"
        "initial_hash,recovered_hash,bit_identical"
    ),
    "covariance.csv": (
        "kind,level,dt_raw,position_discrepancy_raw,momentum_discrepancy_raw,status"
    ),
    "checkpoint.csv": (
        "scenario_id,level,dt_raw,steps,checkpoint_step,checkpoint_hash,decoded_hash,"
        "whole_final_hash,resumed_final_hash,event_suffix_identical"
    ),
    "domain.csv": (
        "scenario_id,level,status,failed_relation_index,first_id,second_id,"
        "time_unchanged,momentum_unchanged,state_unchanged,energy_after_evaluated"
    ),
    "bridge_contracts.csv": (
        "level,unit_contract,path_b_force,equal_velocity_drift,exact_momentum,"
        "exact_angular,reversible,overflow_fail_closed,kinetic_diagnostic"
    ),
    "long_energy.csv": "scenario_id,level,dt_raw,sample,mechanical_energy_bits",
}
PARENT_CONTENT_HASHES = {
    "checkpoint.csv": "643faf79e9376ffc3fa792cd589a6ed914aa8f259e4fc80bad490b8dc3870da5",
    "covariance.csv": "605d92921b3193d60a08ee710c47c924e60ed9295589b93824f665e856177327",
    "domain.csv": "8dcb84cfbb5285cb9fd447f0cf7e2695de5ab2225e71534d3e8a45dfdd8b6297",
    "endpoints.csv": "a04d60925b07c064a7b66626e370899b4c92eabb35b192d906a48ee05e642e7b",
    "energies.csv": "38d4911944d2f0938225b5b8b2371fa37cc5ca84eb86d7bbd4f9da6b44d8ea4d",
    "force_operator.csv": "d5d9a19ea6f8a5cdd25810f2e6a1e35ed039e45463d56a3f208c8b9151698ed7",
    "initial_states.csv": "1f1e7474f1f88c74c91cc1a89419daa08256dd4461a79faa5056b5f4b1b58162",
    "long_energy.csv": "525774ec0b37c61fe35b030744c1910811dcb55bfda876453c7ea4d45ce79e4d",
    "parent_fingerprint.csv": "8f4a1f99d131c2d4633b79cf4ff95d90819eefcd87ad93f09e357363cf3fd3d8",
    "reference_packets.csv": "cece5ec75feb212294ece4077cd7781c36e03815d6de528f64ca19a98964d8a3",
    "relations.csv": "5b50a04399f9868a9fdc0fe3e263e162aa3a4d52b0be03b11a6cb17a689bece0",
    "reversibility.csv": "e4f5c4545aa34e59cbbec46be3708b921c57bcd7f5de8e807f258e457dc6a932",
    "rounding_controls.csv": "055d0a2f62442b7bc7b50902644a6a29fff0273185bb22dd3f3fbbae7d2c0aa3",
    "units.csv": "52f4037f08919c20413b98418b6b79f6e87d0e361eff57ef6fb26ac6f94fe2d7",
}
SHA1 = re.compile(r"[0-9a-f]{40}")

getcontext().prec = 110


class OracleError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OracleError(message)


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def group(
    input_rows: list[dict[str, str]], keys: tuple[str, ...]
) -> dict[tuple[str, ...], list[dict[str, str]]]:
    result: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in input_rows:
        result[tuple(row[key] for key in keys)].append(row)
    return dict(result)


def metadata(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows(path):
        require(row["key"] not in result, "duplicate metadata key")
        result[row["key"]] = row["value"]
    return result


def boolean(value: str) -> bool:
    require(value in {"true", "false"}, f"invalid boolean {value!r}")
    return value == "true"


def ratio(value: str) -> Fraction:
    numerator, separator, denominator = value.partition("/")
    require(separator == "/", f"invalid rational {value!r}")
    return Fraction(int(numerator), int(denominator))


def mp(value: Fraction | int) -> Decimal:
    fraction = Fraction(value)
    return Decimal(fraction.numerator) / Decimal(fraction.denominator)


def float_from_bits(value: str) -> float:
    return struct.unpack(">d", struct.pack(">Q", int(value)))[0]


def mp_from_bits(value: str) -> Decimal:
    numerator, denominator = float_from_bits(value).as_integer_ratio()
    return Decimal(numerator) / Decimal(denominator)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_parent(parent_raw: Path) -> dict[str, object]:
    actual: dict[str, str] = {}
    for filename, expected in PARENT_CONTENT_HASHES.items():
        path = parent_raw / filename
        require(path.is_file(), f"parent fingerprint missing {filename}")
        actual[filename] = sha256(path)
        require(actual[filename] == expected, f"parent fingerprint differs: {filename}")
    return {
        "scientific_files": len(actual),
        "content_hashes": actual,
        "decision": "temporal_convergence_blocked_by_authoritative_quantization",
    }


def verify_level_zero_parent_seam(raw: Path, parent_raw: Path) -> dict[str, int]:
    comparisons = {
        "reference_packets.csv": (
            "model_id", "packet_id", "x_raw", "y_raw", "z_raw", "mass_raw"
        ),
        "initial_states.csv": (
            "scenario_id", "model_id", "convergence", "packet_id", "x_raw",
            "y_raw", "z_raw", "px_raw", "py_raw", "pz_raw", "mass_raw",
        ),
    }
    counts: dict[str, int] = {}
    for filename, fields in comparisons.items():
        candidate = [row for row in rows(raw / filename) if row["level"] == "0"]
        parent = rows(parent_raw / filename)
        candidate_projection = sorted(tuple(row[field] for field in fields) for row in candidate)
        parent_projection = sorted(tuple(row[field] for field in fields) for row in parent)
        require(
            candidate_projection == parent_projection,
            f"level-zero parent seam differs: {filename}",
        )
        counts[filename] = len(candidate_projection)
    return counts


def verify_schema_and_metadata(raw: Path) -> dict[str, str]:
    require(set(FILES) == set(SCHEMAS), "schema inventory differs")
    for filename, expected in SCHEMAS.items():
        path = raw / filename
        require(path.is_file(), f"missing raw file {filename}")
        with path.open(encoding="utf-8", newline="") as stream:
            actual = stream.readline().rstrip("\r\n")
        require(actual == expected, f"{filename}: schema differs")
    meta = metadata(raw / "metadata.csv")
    expected = {
        "schema": "mls.phase-space-time-corefinement.raw.v1",
        "accepted_parent_sha": PARENT_SHA,
        "accepted_parent_tag": PARENT_TAG,
        "accepted_parent_tag_object": PARENT_TAG_OBJECT,
        "accepted_parent_archive_sha256": PARENT_ARCHIVE_SHA256,
        "accepted_parent_archive_size": "7742347",
        "branch": BRANCH,
        "base_representation": "R=128",
        "candidate": "order_matched_space_time_corefinement",
        "negative_control": "fixed_R128_parent",
        "safe_domain": "2^-24",
        "authoritative_integer_width": "signed64",
        "diagnostic_invariant_width": "signed_magnitude_192",
        "position_remainder_present": "false",
        "impulse_remainder_present": "false",
        "adaptive_profile_present": "false",
        "energy_discrepancy_stored": "false",
        "promotion": "NO_PROMOTION",
    }
    for key, value in expected.items():
        require(meta.get(key) == value, f"metadata {key} differs")
    require(meta.get("source_dirty") == "false", "source materialization is dirty")
    require(SHA1.fullmatch(meta.get("source_sha", "")) is not None, "source SHA malformed")
    require(
        meta.get("configured_source_branch") in {BRANCH, "HEAD"},
        "configured source branch differs",
    )
    fingerprints = rows(raw / "parent_fingerprint.csv")
    require(len(fingerprints) == 6, "parent seam fingerprint count differs")
    require(all(boolean(row["passed"]) for row in fingerprints), "parent seam fingerprint failed")
    return meta


def expected_units(level: int) -> dict[str, Fraction | int]:
    time_factor = 2 ** (3 * level)
    length_factor = 2 ** (6 * level)
    return {
        "Lq": Fraction(1, 128_000_000_000 * length_factor),
        "Mq": Fraction(1, 524_288),
        "Tq": Fraction(1, 1_000_000_000 * time_factor),
        "Pq": Fraction(1, 67_108_864 * time_factor),
        "Eq": Fraction(1, 8_589_934_592 * length_factor),
        "Fq": Fraction(1_953_125, 131_072),
        "dt_raw": TIMESTEPS[level],
        "steps": STEP_COUNTS[level],
    }


def verify_units(raw: Path) -> dict[int, dict[str, Fraction | int]]:
    unit_rows = rows(raw / "units.csv")
    require(len(unit_rows) == 5, "unit level count differs")
    result: dict[int, dict[str, Fraction | int]] = {}
    for row in unit_rows:
        level = int(row["level"])
        require(level in LEVELS and level not in result, "unit level differs")
        expected = expected_units(level)
        actual = {key: ratio(row[key]) for key in ("Lq", "Mq", "Tq", "Pq", "Eq", "Fq")}
        for key, value in actual.items():
            require(value == expected[key], f"level {level}: {key} differs")
        require(int(row["dt_raw"]) == expected["dt_raw"], "raw timestep differs")
        require(int(row["steps"]) == expected["steps"], "step count differs")
        require(boolean(row["unit_contract_valid"]), "unit contract declared invalid")
        require(actual["Pq"] == actual["Mq"] * actual["Lq"] / actual["Tq"], "Pq identity fails")
        require(actual["Eq"] == actual["Pq"] ** 2 / actual["Mq"], "Eq identity fails")
        require(actual["Fq"] * actual["Tq"] == actual["Pq"], "Fq identity fails")
        result[level] = expected
    return result


def verify_mapping(raw: Path) -> dict[str, object]:
    mapping = rows(raw / "mapping.csv")
    require(len(mapping) == 35, "mapping inventory differs")
    overflow = [row for row in mapping if row["status"] == "signed64_overflow"]
    require(
        [(row["scenario_id"], int(row["level"])) for row in overflow]
        == [("k4_translated", 4)],
        "signed-width fingerprint differs",
    )
    require(
        all(row["status"] in {"mapped", "signed64_overflow"} for row in mapping),
        "unknown mapping status",
    )
    initial = group(rows(raw / "initial_states.csv"), ("scenario_id", "level"))
    for (scenario, level_text), packet_rows in initial.items():
        level = int(level_text)
        base = initial.get((scenario, "0"))
        require(base is not None, f"{scenario}: missing level-zero state")
        base_by_id = {row["packet_id"]: row for row in base}
        position_factor = 2 ** (6 * level)
        momentum_factor = 2 ** (3 * level)
        for row in packet_rows:
            original = base_by_id[row["packet_id"]]
            for axis in "xyz":
                require(
                    int(row[f"{axis}_raw"]) == int(original[f"{axis}_raw"]) * position_factor,
                    f"{scenario}/{level}: position mapping differs",
                )
                require(
                    int(row[f"p{axis}_raw"]) == int(original[f"p{axis}_raw"]) * momentum_factor,
                    f"{scenario}/{level}: momentum mapping differs",
                )
            require(row["mass_raw"] == original["mass_raw"], "mass mapping differs")
    return {
        "mapped_rows": sum(row["status"] == "mapped" for row in mapping),
        "signed64_overflow": [(row["scenario_id"], int(row["level"])) for row in overflow],
    }


def load_models(raw: Path, units: dict[int, dict[str, Fraction | int]]) -> dict[str, foundation.Model]:
    require(
        sha256(raw / "relations.csv") == PARENT_CONTENT_HASHES["relations.csv"],
        "accepted relation topology/orientation differs",
    )
    require(
        sha256(raw / "force_operator.csv")
        == PARENT_CONTENT_HASHES["force_operator.csv"],
        "accepted force operator differs",
    )
    reference = group(rows(raw / "reference_packets.csv"), ("model_id", "level"))
    relations = group(rows(raw / "relations.csv"), ("model_id",))
    operators = group(rows(raw / "force_operator.csv"), ("model_id",))
    model_ids = {key[0] for key in relations}
    require(model_ids == {"k4", "k4_translated", "k4_rotated", "octahedron", "pair"}, "model inventory differs")
    metre = 128_000_000_000
    kilogram = 524_288
    k4 = {
        1: (0, 0, 0),
        2: (metre, 0, 0),
        3: (0, metre, 0),
        4: (0, 0, metre),
    }
    shift = (17 * metre, -11 * metre, 7 * metre)
    expected_level_zero: dict[str, dict[int, tuple[int, int, int]]] = {
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
    result: dict[str, foundation.Model] = {}
    for model_id in sorted(model_ids):
        level_zero = sorted(reference[(model_id, "0")], key=lambda row: int(row["packet_id"]))
        packet_ids = [int(row["packet_id"]) for row in level_zero]
        actual_level_zero = {
            int(row["packet_id"]): tuple(int(row[f"{axis}_raw"]) for axis in "xyz")
            for row in level_zero
        }
        require(
            actual_level_zero == expected_level_zero[model_id],
            f"{model_id}: accepted reference coordinates differ",
        )
        require(
            all(int(row["mass_raw"]) == kilogram for row in level_zero),
            f"{model_id}: accepted reference masses differ",
        )
        lq0 = units[0]["Lq"]
        mq0 = units[0]["Mq"]
        assert isinstance(lq0, Fraction) and isinstance(mq0, Fraction)
        positions = [[mp(int(row[f"{axis}_raw"]) * lq0) for axis in "xyz"] for row in level_zero]
        masses = [mp(int(row["mass_raw"]) * mq0) for row in level_zero]
        relation_rows = sorted(relations[(model_id,)], key=lambda row: int(row["relation_index"]))
        edges = [(int(row["first_id"]), int(row["second_id"])) for row in relation_rows]
        count = len(edges)
        h = [[Decimal(0) for _ in range(count)] for _ in range(count)]
        for row in operators[(model_id,)]:
            h[int(row["row"])][int(row["column"])] = mp_from_bits(row["h_bits"])
        model = foundation.Model(packet_ids, masses, positions, edges, h)
        expected_h = foundation.expected_local_collective_h(model)
        require(
            all(abs(h[i][j] - expected_h[i][j]) <= Decimal("5e-15") for i in range(count) for j in range(count)),
            f"{model_id}: H differs",
        )
        result[model_id] = model
        for level in LEVELS:
            level_rows = reference.get((model_id, str(level)))
            if model_id == "k4_translated" and level == 4:
                require(level_rows is None, "overflowed reference was emitted")
                continue
            require(level_rows is not None, f"{model_id}/{level}: reference missing")
            by_id = {int(row["packet_id"]): row for row in level_rows}
            lq = units[level]["Lq"]
            assert isinstance(lq, Fraction)
            for index, identifier in enumerate(packet_ids):
                for axis_index, axis in enumerate("xyz"):
                    require(
                        mp(int(by_id[identifier][f"{axis}_raw"]) * lq) == positions[index][axis_index],
                        f"{model_id}/{level}: physical reference changed",
                    )
    return result


def load_initial_physical(
    raw: Path,
    units: dict[int, dict[str, Fraction | int]],
) -> dict[str, tuple[str, list[list[Decimal]], list[list[Decimal]]]]:
    grouped = group(rows(raw / "initial_states.csv"), ("scenario_id", "level"))
    result: dict[str, tuple[str, list[list[Decimal]], list[list[Decimal]]]] = {}
    for scenario in CONVERGENCE_SCENARIOS:
        packet_rows = sorted(grouped[(scenario, "0")], key=lambda row: int(row["packet_id"]))
        lq = units[0]["Lq"]
        pq = units[0]["Pq"]
        assert isinstance(lq, Fraction) and isinstance(pq, Fraction)
        result[scenario] = (
            packet_rows[0]["model_id"],
            [[mp(int(row[f"{axis}_raw"]) * lq) for axis in "xyz"] for row in packet_rows],
            [[mp(int(row[f"p{axis}_raw"]) * pq) for axis in "xyz"] for row in packet_rows],
        )
    return result


def exact_invariants(state_rows: list[dict[str, str]]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    total_p = [0, 0, 0]
    total_l = [0, 0, 0]
    for row in state_rows:
        x = [int(row[f"{axis}_raw"]) for axis in "xyz"]
        p = [int(row[f"p{axis}_raw"]) for axis in "xyz"]
        for axis in range(3):
            total_p[axis] += p[axis]
        total_l[0] += x[1] * p[2] - x[2] * p[1]
        total_l[1] += x[2] * p[0] - x[0] * p[2]
        total_l[2] += x[0] * p[1] - x[1] * p[0]
    return tuple(total_p), tuple(total_l)


def load_endpoints(
    raw: Path,
    units: dict[int, dict[str, Fraction | int]],
) -> tuple[dict[tuple[str, str, int], list[Decimal]], bool]:
    grouped = group(rows(raw / "endpoints.csv"), ("scenario_id", "path", "level"))
    initial = group(rows(raw / "initial_states.csv"), ("scenario_id", "level"))
    result: dict[tuple[str, str, int], list[Decimal]] = {}
    invariants_pass = True
    for scenario in CONVERGENCE_SCENARIOS:
        for path in (CONTROL, KDK):
            for level in LEVELS:
                key = (scenario, path, level)
                endpoint_rows = sorted(grouped[(scenario, path, str(level))], key=lambda row: int(row["packet_id"]))
                require(all(row["status"] == "accepted" for row in endpoint_rows), f"{key}: trajectory failed")
                require(all(int(row["completed_steps"]) == STEP_COUNTS[level] for row in endpoint_rows), f"{key}: incomplete")
                require(all(boolean(row["momentum_preserved"]) and boolean(row["angular_preserved"]) for row in endpoint_rows), f"{key}: declared invariant failed")
                invariants_pass = invariants_pass and exact_invariants(endpoint_rows) == exact_invariants(initial[(scenario, str(level))])
                lq = units[level]["Lq"]
                pq = units[level]["Pq"]
                assert isinstance(lq, Fraction) and isinstance(pq, Fraction)
                state = [mp(int(row[f"{axis}_raw"]) * lq) for row in endpoint_rows for axis in "xyz"]
                state.extend(mp(int(row[f"p{axis}_raw"]) * pq) for row in endpoint_rows for axis in "xyz")
                result[key] = state
    return result, invariants_pass


def contains_window(orders: list[float], low: float, high: float, count: int) -> bool:
    return any(
        all(low <= value <= high for value in orders[start : start + count])
        for start in range(len(orders) - count + 1)
    )


def convergence_report(
    endpoints: dict[tuple[str, str, int], list[Decimal]],
    oracle: dict[str, list[Decimal]],
) -> tuple[dict[str, object], bool, bool]:
    report: dict[str, object] = {}
    candidate_pass = True
    control_pass = True
    for scenario in CONVERGENCE_SCENARIOS:
        scenario_report: dict[str, object] = {}
        orders_by_path: dict[str, list[float]] = {}
        for path in (CONTROL, KDK):
            errors = [
                foundation.state_norm_difference(
                    endpoints[(scenario, path, level)], oracle[scenario],
                    len(endpoints[(scenario, path, level)]) // 6,
                )
                for level in LEVELS
            ]
            orders = [math.log2(float(errors[i] / errors[i + 1])) for i in range(4)]
            orders_by_path[path] = orders
            scenario_report[path] = {
                "errors": [format(value, ".29E") for value in errors],
                "orders": orders,
            }
        kdk_window = contains_window(orders_by_path[KDK], 1.6, 2.4, 3)
        first_order = contains_window(orders_by_path[CONTROL], 0.6, 1.4, 2)
        separated = max(orders_by_path[KDK]) - max(orders_by_path[CONTROL]) >= 0.5
        scenario_report["candidate_second_order_window"] = kdk_window
        scenario_report["control_first_order_window"] = first_order
        scenario_report["order_separated"] = separated
        report[scenario] = scenario_report
        candidate_pass = candidate_pass and kdk_window
        control_pass = control_pass and first_order and separated
    return report, candidate_pass, control_pass


def verify_primitive(raw: Path, units: dict[int, dict[str, Fraction | int]]) -> dict[str, object]:
    diagnostic_rows = rows(raw / "primitive_diagnostics.csv")
    require(diagnostic_rows, "primitive diagnostics empty")
    summaries: dict[tuple[str, int], dict[str, object]] = {}
    grouped = group(diagnostic_rows, ("scenario_id", "level"))
    for key, values in grouped.items():
        level = int(key[1])
        gcd_one = 0
        maximum_minimum = 0.0
        observed_stages: set[str] = set()
        for row in values:
            p = tuple(int(row[f"p{axis}_raw"]) for axis in "xyz")
            divisor = math.gcd(*(abs(value) for value in p))
            require(int(row["g"]) == divisor, "gcd diagnostic differs")
            u = tuple(int(row[axis]) for axis in ("ux", "uy", "uz"))
            expected_u = (0, 0, 0) if divisor == 0 else tuple(value // divisor for value in p)
            require(u == expected_u, "primitive direction differs")
            if divisor != 0:
                require(math.gcd(*(abs(value) for value in u)) == 1, "direction is not primitive")
            squared = sum(value * value for value in u)
            declared_squared = Decimal(row["primitive_norm_squared_ld"])
            require(abs(declared_squared - Decimal(squared)) <= Decimal("0.5"), "primitive norm diagnostic differs")
            lq = units[level]["Lq"]
            assert isinstance(lq, Fraction)
            expected_minimum = float(mp(lq) * Decimal(squared).sqrt())
            observed_minimum = float_from_bits(row["minimum_drift_m_bits"])
            require(observed_minimum == expected_minimum, "minimum drift diagnostic differs")
            maximum_minimum = max(maximum_minimum, observed_minimum)
            gcd_one += divisor == 1
            observed_stages.add(row["stage"])
        require({"first_kick", "drift"}.issubset(observed_stages), f"{key}: kick/drift diagnostics missing")
        summaries[(key[0], level)] = {
            "rows": len(values),
            "gcd_one_rows": gcd_one,
            "maximum_minimum_drift_m": maximum_minimum,
        }
    return {
        f"{scenario}/level-{level}": value
        for (scenario, level), value in sorted(summaries.items())
    }


def verify_relation_primitive(
    raw: Path,
    units: dict[int, dict[str, Fraction | int]],
) -> dict[str, object]:
    diagnostic_rows = rows(raw / "relation_primitive_diagnostics.csv")
    require(diagnostic_rows, "relation primitive diagnostics empty")
    summaries: dict[tuple[str, int], dict[str, object]] = {}
    grouped = group(diagnostic_rows, ("scenario_id", "level"))
    for key, values in grouped.items():
        level = int(key[1])
        gcd_one = 0
        applied_zero = 0
        resolved_target_but_zero = 0
        maximum_minimum = 0.0
        stages: set[str] = set()
        for row in values:
            relative = tuple(int(row[f"r{axis}_raw"]) for axis in "xyz")
            divisor = math.gcd(*(abs(value) for value in relative))
            require(divisor > 0 and int(row["g"]) == divisor, "relation gcd differs")
            primitive = tuple(int(row[axis]) for axis in ("ux", "uy", "uz"))
            require(primitive == tuple(value // divisor for value in relative), "relation primitive differs")
            require(math.gcd(*(abs(value) for value in primitive)) == 1, "relation direction not primitive")
            target = float_from_bits(row["target_multiple_bits"])
            require(math.isfinite(target), "relation target multiple is nonfinite")
            applied = int(row["applied_multiple"])
            expected_applied = round(target)
            require(applied == expected_applied, "relation nearest-even multiple differs")
            pq = units[level]["Pq"]
            assert isinstance(pq, Fraction)
            expected_minimum = float(
                mp(pq) * Decimal(sum(value * value for value in primitive)).sqrt()
            )
            observed_minimum = float_from_bits(row["minimum_impulse_bits"])
            require(observed_minimum == expected_minimum, "minimum impulse diagnostic differs")
            gcd_one += divisor == 1
            applied_zero += applied == 0
            resolved_target_but_zero += applied == 0 and target != 0.0
            maximum_minimum = max(maximum_minimum, observed_minimum)
            stages.add(row["stage"])
        require("first_kick" in stages, f"{key}: first-kick diagnostic missing")
        summaries[(key[0], level)] = {
            "rows": len(values),
            "gcd_one_rows": gcd_one,
            "applied_zero_rows": applied_zero,
            "nonzero_target_rounded_to_zero_rows": resolved_target_but_zero,
            "maximum_minimum_impulse_kg_m_per_s": maximum_minimum,
        }
    return {
        f"{scenario}/level-{level}": value
        for (scenario, level), value in sorted(summaries.items())
    }


def verify_exact_gates(raw: Path, units: dict[int, dict[str, Fraction | int]]) -> tuple[dict[str, object], bool, bool, bool]:
    bridge_rows = rows(raw / "bridge_contracts.csv")
    require(len(bridge_rows) == 5, "bridge level count differs")
    bridge_pass = all(
        all(boolean(row[key]) for key in (
            "unit_contract", "path_b_force", "equal_velocity_drift", "exact_momentum",
            "exact_angular", "reversible", "overflow_fail_closed", "kinetic_diagnostic",
        ))
        for row in bridge_rows
    )
    reversibility = rows(raw / "reversibility.csv")
    require(len(reversibility) == 30, "reversibility inventory differs")
    width_rows = [row for row in reversibility if row["forward_status"] == "mapping_overflow"]
    require([(row["scenario_id"], int(row["level"])) for row in width_rows] == [("k4_translated", 4)], "reversibility width fingerprint differs")
    reversible = all(
        row["forward_status"] == "accepted" and row["backward_status"] == "accepted"
        and row["initial_hash"] == row["recovered_hash"] and boolean(row["bit_identical"])
        for row in reversibility if row not in width_rows
    )
    checkpoints = rows(raw / "checkpoint.csv")
    checkpoint_pass = len(checkpoints) == 5 and all(
        row["checkpoint_hash"] == row["decoded_hash"]
        and row["whole_final_hash"] == row["resumed_final_hash"]
        and boolean(row["event_suffix_identical"])
        for row in checkpoints
    )
    domains = rows(raw / "domain.csv")
    domain_pass = len(domains) == 5 and all(
        row["status"] == "chord_domain_failure" and row["first_id"] == "1"
        and row["second_id"] == "2" and boolean(row["time_unchanged"])
        and boolean(row["momentum_unchanged"]) and boolean(row["state_unchanged"])
        and not boolean(row["energy_after_evaluated"])
        for row in domains
    )
    covariance = group(rows(raw / "covariance.csv"), ("kind",))
    require(set(key[0] for key in covariance) == {"translation", "galilean_boost", "proper_lattice_rotation"}, "covariance inventory differs")
    translation_rows = covariance[("translation",)]
    translation_pass = all(
        (int(row["level"]) == 4 and row["status"] == "mapping_overflow")
        or (row["status"] == "evaluated" and int(row["position_discrepancy_raw"]) == 0 and int(row["momentum_discrepancy_raw"]) == 0)
        for row in translation_rows
    )
    rotation_pass = all(
        row["status"] == "evaluated" and int(row["position_discrepancy_raw"]) == 0
        and int(row["momentum_discrepancy_raw"]) == 0
        for row in covariance[("proper_lattice_rotation",)]
    )
    boost_physical: list[float] = []
    for row in sorted(covariance[("galilean_boost",)], key=lambda value: int(value["level"])):
        level = int(row["level"])
        lq = units[level]["Lq"]
        pq = units[level]["Pq"]
        assert isinstance(lq, Fraction) and isinstance(pq, Fraction)
        boost_physical.append(max(
            float(int(row["position_discrepancy_raw"]) * lq),
            float(int(row["momentum_discrepancy_raw"]) * pq),
        ))
    boost_pass = all(value == 0.0 for value in boost_physical) or all(
        boost_physical[index + 1] < boost_physical[index]
        for index in range(len(boost_physical) - 1)
        if boost_physical[index] != 0.0
    )
    report = {
        "bridge_levels_pass": bridge_pass,
        "reversibility_rows": len(reversibility),
        "reversible_evaluated_rows": reversible,
        "width_omission": [(row["scenario_id"], int(row["level"])) for row in width_rows],
        "checkpoint_pass": checkpoint_pass,
        "domain_atomic": domain_pass,
        "translation_exact_before_width_limit": translation_pass,
        "rotation_exact": rotation_pass,
        "boost_discrepancy_physical": boost_physical,
        "boost_pass": boost_pass,
    }
    return report, bridge_pass and checkpoint_pass and domain_pass and translation_pass and rotation_pass, reversible, boost_pass


def energy_report(
    raw: Path,
    units: dict[int, dict[str, Fraction | int]],
) -> tuple[dict[str, object], bool]:
    grouped = group(rows(raw / "energies.csv"), ("scenario_id", "path", "level"))
    report: dict[str, object] = {}
    short_pass = True
    for scenario in CONVERGENCE_SCENARIOS:
        scenario_report: dict[str, object] = {}
        for path in (CONTROL, KDK):
            envelopes: list[float] = []
            for level in LEVELS:
                energy = [float_from_bits(row["mechanical_energy_bits"]) for row in grouped[(scenario, path, str(level))]]
                require(len(energy) == STEP_COUNTS[level] + 1, f"{scenario}/{path}/{level}: energy samples differ")
                envelopes.append(max(abs(value - energy[0]) for value in energy))
            orders = [math.log2(envelopes[i] / envelopes[i + 1]) for i in range(4)]
            scenario_report[path] = {"envelopes": envelopes, "orders": orders}
            if path == KDK:
                short_pass = short_pass and contains_window(orders, 1.5, 2.5, 3)
        report[scenario] = scenario_report
    long_grouped = group(rows(raw / "long_energy.csv"), ("level",))
    long_reports: list[dict[str, object]] = []
    for level in LEVELS:
        values = [float_from_bits(row["mechanical_energy_bits"]) for row in long_grouped[(str(level),)]]
        require(len(values) == STEP_COUNTS[level] * 16 + 1, f"long energy level {level} incomplete")
        error = [value - values[0] for value in values]
        mean = sum(error) / len(error)
        x_mean = (len(error) - 1) / 2
        slope = sum(
            (i - x_mean) * (value - mean) for i, value in enumerate(error)
        ) / sum((i - x_mean) ** 2 for i in range(len(error)))
        time_quantum = units[level]["Tq"]
        assert isinstance(time_quantum, Fraction)
        sample_seconds = float(TIMESTEPS[level] * time_quantum)
        long_reports.append({
            "level": level,
            "maximum_excursion": max(abs(value) for value in error),
            "final_error": error[-1],
            "mean_offset": mean,
            "least_squares_slope_per_sample": slope,
            "sample_seconds": sample_seconds,
            "least_squares_slope_per_second": slope / sample_seconds,
        })
    def contraction_orders(field: str) -> list[float]:
        magnitudes = [abs(float(entry[field])) for entry in long_reports]
        require(all(value > 0.0 for value in magnitudes), f"long energy {field} unresolved")
        return [math.log2(magnitudes[index] / magnitudes[index + 1]) for index in range(4)]

    maximum_orders = contraction_orders("maximum_excursion")
    final_orders = contraction_orders("final_error")
    physical_slope_orders = contraction_orders("least_squares_slope_per_second")
    # The per-sample slope shrinks automatically as the sampling interval is
    # halved.  The physical-time slope is the scientific quantity.  Require
    # all three registered diagnostics to enter the same three-halving,
    # second-order contraction window as the short KDK energy envelope.
    long_pass = all(
        contains_window(values, 1.5, 2.5, 3)
        for values in (maximum_orders, final_orders, physical_slope_orders)
    )
    report["long_run"] = long_reports
    report["long_run_contraction_orders"] = {
        "maximum_excursion": maximum_orders,
        "final_error": final_orders,
        "least_squares_slope_per_second": physical_slope_orders,
    }
    report["long_run_contracts"] = long_pass
    return report, short_pass and long_pass


def verify(
    raw: Path,
    parent_raw: Path,
    precomputed_oracle: tuple[
        dict[str, list[Decimal]], dict[str, Decimal]
    ] | None = None,
) -> dict[str, object]:
    parent_report = verify_parent(parent_raw)
    level_zero_seam = verify_level_zero_parent_seam(raw, parent_raw)
    meta = verify_schema_and_metadata(raw)
    units = verify_units(raw)
    mapping = verify_mapping(raw)
    models = load_models(raw, units)
    initial = load_initial_physical(raw, units)
    oracle, oracle_refinements = (
        foundation.oracle_states(models, initial)
        if precomputed_oracle is None
        else precomputed_oracle
    )
    endpoints, endpoint_invariants = load_endpoints(raw, units)
    convergence, convergence_pass, control_pass = convergence_report(endpoints, oracle)
    primitive = verify_primitive(raw, units)
    relation_primitive = verify_relation_primitive(raw, units)
    exact, exact_pass, reversible, frame_pass = verify_exact_gates(raw, units)
    energy, energy_pass = energy_report(raw, units)
    width_blocks_window = any(
        scenario in CONVERGENCE_SCENARIOS
        for scenario, _level in mapping["signed64_overflow"]
    )
    if parent_report["decision"] != "temporal_convergence_blocked_by_authoritative_quantization":
        decision = "stop_inconclusive_or_wrong_parent"
    elif width_blocks_window:
        decision = "corefinement_blocked_by_fixed_width_state"
    elif not endpoint_invariants or not exact_pass or not reversible:
        decision = "reject_corefined_quantized_composition"
    elif not convergence_pass or not control_pass:
        decision = "reject_order_matched_space_time_corefinement"
    elif not frame_pass:
        decision = "reject_corefined_phase_space_frame_covariance"
    elif not energy_pass:
        decision = "reject_corefined_long_run_energy_behavior"
    else:
        decision = "retain_order_matched_space_time_corefinement_for_research"
    return {
        "schema": "mls.phase-space-time-corefinement.oracle.v1",
        "precision_decimal_digits": getcontext().prec,
        "source_sha": meta["source_sha"],
        "parent_fingerprint": parent_report,
        "level_zero_parent_seam_rows": level_zero_seam,
        "unit_profiles": {str(level): {key: str(value) for key, value in units[level].items()} for level in LEVELS},
        "mapping": mapping,
        "oracle_refinement_errors": {key: format(value, ".29E") for key, value in oracle_refinements.items()},
        "convergence": convergence,
        "primitive_diagnostics": primitive,
        "relation_primitive_diagnostics": relation_primitive,
        "exact_gates": exact,
        "energy": energy,
        "endpoint_invariants_independently_recomputed": endpoint_invariants,
        "width_blocks_convergence_window": width_blocks_window,
        "decision": decision,
        "promotion": "NO_PROMOTION",
        "raw_files": {filename: sha256(raw / filename) for filename in FILES},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--parent-raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        result = verify(arguments.raw, arguments.parent_raw)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"PHASE SPACE TIME COREFINEMENT ORACLE: PASS {result['decision']} NO_PROMOTION")
        return 0
    except (OSError, ValueError, ArithmeticError, OracleError, foundation.OracleError) as error:
        print(f"PHASE SPACE TIME COREFINEMENT ORACLE: FAIL {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
