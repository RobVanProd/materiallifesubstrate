#!/usr/bin/env python3
"""Independent verifier and smooth oracle for fractional phase-state evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import struct
import sys
from collections import defaultdict
from decimal import Decimal, getcontext
from fractions import Fraction
from pathlib import Path

import phase_space_time_corefinement_oracle as parent
import time_integration_foundation_oracle as foundation


if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)

getcontext().prec = 110

PARENT_SHA = "6dfaf29821ded7e1349358c671b52e73f345c26a"
PARENT_TAG = "phase-space-time-corefinement-lab-evidence-v1"
PARENT_TAG_OBJECT = "b4df81ae41b9b341ae49f564e784976f8b731084"
PARENT_ARCHIVE_SHA256 = (
    "cf3427082fc66426c4074e615decbc5353ba0bc216a1b480f0c688e18f8f3c8d"
)
BRANCH = "explicit-fractional-phase-state-lab"
KDK = "fractional_kick_drift_kick"
CONTROL = "fractional_symplectic_euler_control"
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
MAX_COMPONENT_BITS = 262_144
MEDIAN_COMPONENT_BITS = 131_072
MAX_CHECKPOINT_BYTES = 8_388_608
SHA1 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")

FILES = (
    "metadata.csv", "units.csv", "parent_fingerprint.csv",
    "reference_packets.csv", "relations.csv", "force_operator.csv",
    "initial_states.csv", "endpoints.csv", "checkpoint_states.csv",
    "recovery_states.csv", "energies.csv", "invariants.csv",
    "force_audit.csv", "state_complexity.csv", "reversibility.csv",
    "covariance.csv", "checkpoint.csv", "domain.csv", "long_energy.csv",
    "obstruction.csv",
)

SCHEMAS = {
    "metadata.csv": "key,value",
    "units.csv": "Lq,Mq,Tq,Pq,Eq,Fq,canonical_interval,fixed_across_levels",
    "parent_fingerprint.csv": "file,sha256,expected_sha256,passed",
    "reference_packets.csv": "model_id,level,packet_id,x_raw,y_raw,z_raw,mass_raw",
    "relations.csv": "model_id,relation_index,first_id,second_id,rest_length_bits",
    "force_operator.csv": "model_id,row,column,h_bits",
    "initial_states.csv": (
        "scenario_id,model_id,path,level,dt_raw,steps,status,completed_steps,time_raw,"
        "state_hash,packet_id,mass_raw,xx_coarse,xx_num,xx_den,xy_coarse,xy_num,xy_den,"
        "xz_coarse,xz_num,xz_den,px_coarse,px_num,px_den,py_coarse,py_num,py_den,"
        "pz_coarse,pz_num,pz_den"
    ),
    "endpoints.csv": (
        "scenario_id,model_id,path,level,dt_raw,steps,status,completed_steps,time_raw,"
        "state_hash,packet_id,mass_raw,xx_coarse,xx_num,xx_den,xy_coarse,xy_num,xy_den,"
        "xz_coarse,xz_num,xz_den,px_coarse,px_num,px_den,py_coarse,py_num,py_den,"
        "pz_coarse,pz_num,pz_den"
    ),
    "checkpoint_states.csv": (
        "scenario_id,model_id,path,level,dt_raw,steps,status,completed_steps,time_raw,"
        "state_hash,packet_id,mass_raw,xx_coarse,xx_num,xx_den,xy_coarse,xy_num,xy_den,"
        "xz_coarse,xz_num,xz_den,px_coarse,px_num,px_den,py_coarse,py_num,py_den,"
        "pz_coarse,pz_num,pz_den"
    ),
    "recovery_states.csv": (
        "scenario_id,model_id,path,level,dt_raw,steps,status,completed_steps,time_raw,"
        "state_hash,packet_id,mass_raw,xx_coarse,xx_num,xx_den,xy_coarse,xy_num,xy_den,"
        "xz_coarse,xz_num,xz_den,px_coarse,px_num,px_den,py_coarse,py_num,py_den,"
        "pz_coarse,pz_num,pz_den"
    ),
    "energies.csv": "scenario_id,path,level,sample,dt_raw,mechanical_energy_bits",
    "invariants.csv": (
        "trajectory_id,level,step,stage,momentum_hash,angular_hash,"
        "momentum_equal_initial,angular_equal_initial,"
        "p_x_num,p_x_den,p_y_num,p_y_den,p_z_num,p_z_den,"
        "l_x_num,l_x_den,l_y_num,l_y_den,l_z_num,l_z_den"
    ),
    "force_audit.csv": (
        "trajectory_id,level,step,stage,relation_index,first_id,second_id,length_bits,"
        "conjugate_bits,coefficient_hash,coefficient_bits,impulse_hash,impulse_bits,"
        "central_cross_zero"
    ),
    "state_complexity.csv": (
        "trajectory_id,level,step,time_raw,packet_id,phase,axis,residual_hash,"
        "numerator_bits,denominator_bits,checkpoint_bytes"
    ),
    "reversibility.csv": (
        "scenario_id,level,dt_raw,steps,forward_status,backward_status,initial_hash,"
        "recovered_hash,complete_state_identical"
    ),
    "covariance.csv": (
        "kind,level,dt_raw,position_discrepancy_hash,position_discrepancy_num,"
        "position_discrepancy_den,momentum_discrepancy_hash,momentum_discrepancy_num,"
        "momentum_discrepancy_den,status"
    ),
    "checkpoint.csv": (
        "scenario_id,level,dt_raw,steps,checkpoint_step,checkpoint_hash,checkpoint_bytes,"
        "decoded_hash,whole_final_hash,resumed_final_hash,event_suffix_identical,"
        "canonical_round_trip"
    ),
    "domain.csv": (
        "scenario_id,level,status,prior_hash,returned_hash,time_unchanged,state_unchanged,"
        "energy_ledger_present"
    ),
    "long_energy.csv": "scenario_id,level,dt_raw,sample,status,mechanical_energy_bits",
    "obstruction.csv": (
        "relation_gcd,momentum_gcd,relation_squared,momentum_squared,"
        "minimum_impulse_squared,minimum_drift_squared,product,expected_product,"
        "unit_independent"
    ),
}


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
        require(row["key"] not in result, "duplicate metadata key")
        result[row["key"]] = row["value"]
    return result


def boolean(value: str) -> bool:
    require(value in {"true", "false"}, f"invalid boolean {value!r}")
    return value == "true"


def ratio(value: str) -> Fraction:
    numerator, separator, denominator = value.partition("/")
    require(separator == "/", f"invalid rational {value!r}")
    parsed = Fraction(int(numerator), int(denominator))
    require(parsed.denominator > 0, "nonpositive rational denominator")
    return parsed


def mp(value: Fraction | int) -> Decimal:
    fraction = Fraction(value)
    return Decimal(fraction.numerator) / Decimal(fraction.denominator)


def float_from_bits(value: str) -> float:
    return struct.unpack(">d", struct.pack(">Q", int(value)))[0]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def grouped(values: list[dict[str, str]], fields: tuple[str, ...]) -> dict[tuple[str, ...], list[dict[str, str]]]:
    result: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in values:
        result[tuple(row[field] for field in fields)].append(row)
    return dict(result)


def verify_schema_and_metadata(raw: Path, allow_dirty: bool) -> dict[str, str]:
    require(set(FILES) == set(SCHEMAS), "oracle schema inventory differs")
    for filename, expected in SCHEMAS.items():
        path = raw / filename
        require(path.is_file(), f"missing raw file {filename}")
        with path.open(encoding="utf-8", newline="") as stream:
            actual = stream.readline().rstrip("\r\n")
        require(actual == expected, f"{filename}: schema differs")
    meta = metadata(raw / "metadata.csv")
    expected = {
        "schema": "mls.explicit-fractional-phase-state.raw.v1",
        "accepted_parent_sha": PARENT_SHA,
        "accepted_parent_tag": PARENT_TAG,
        "accepted_parent_tag_object": PARENT_TAG_OBJECT,
        "accepted_parent_archive_sha256": PARENT_ARCHIVE_SHA256,
        "accepted_parent_archive_size": "4481719",
        "branch": BRANCH,
        "candidate": "exact_reduced_rational_packet_phase_state",
        "rational_arithmetic_backend": "gmpy2.mpq-2.3.1",
        "force_geometry": "cancellation_resistant_binary64",
        "safe_domain": "2^-24",
        "coarse_integer_width": "signed64",
        "fractional_denominator": "unbounded_exact_reduced",
        "relation_remainder_present": "false",
        "energy_discrepancy_stored": "false",
        "maximum_component_bits": str(MAX_COMPONENT_BITS),
        "median_component_bits": str(MEDIAN_COMPONENT_BITS),
        "maximum_checkpoint_bytes": str(MAX_CHECKPOINT_BYTES),
        "promotion": "NO_PROMOTION",
    }
    for key, value in expected.items():
        require(meta.get(key) == value, f"metadata {key} differs")
    require(SHA1.fullmatch(meta.get("source_sha", "")) is not None, "source SHA malformed")
    require(meta.get("configured_source_branch") in {BRANCH, "HEAD"}, "source branch differs")
    require(allow_dirty or meta.get("source_dirty") == "false", "source materialization is dirty")
    unit_rows = rows(raw / "units.csv")
    require(len(unit_rows) == 1, "unit row count differs")
    unit = unit_rows[0]
    for key, value in (("Lq", LQ), ("Mq", MQ), ("Tq", TQ), ("Pq", PQ), ("Eq", EQ), ("Fq", FQ)):
        require(ratio(unit[key]) == value, f"{key} differs")
    require(unit["canonical_interval"] == "[-1/2,1/2)" and boolean(unit["fixed_across_levels"]),
            "fractional unit/canonical contract differs")
    require(PQ == MQ * LQ / TQ and EQ == PQ * PQ / MQ and FQ * TQ == PQ,
            "coherent unit identity failed")
    return meta


def verify_parent(raw: Path, parent_raw: Path) -> dict[str, object]:
    fingerprints = rows(raw / "parent_fingerprint.csv")
    actual = {row["file"]: row for row in fingerprints}
    expected_hashes = {
        "bridge_contracts.csv": "93a5730fb67023b089366893dafe9f34be983e03abdf4ba5c6cb4fefd0a7366d",
        "checkpoint.csv": "1429269754b0e5583e518c75fa50866e65b6a161f350c23d7c93f09f39b99f04",
        "covariance.csv": "7f9eaa75cd4c2efcc475dc5fbc08de6f15ffa26b07a47d0f867784f7fab4c705",
        "domain.csv": "298741726b34711257526b5c4ca604a90924acacdc16c5830913eeb37bc06a8a",
        "endpoints.csv": "20712bdf438f55cc74638eb40a2539799d7b324349a9f3ae61acf68a53aaf972",
        "energies.csv": "55b6510995a99d60b578d33bade20f061676804cb80012b72a46e0ab2fa74772",
        "force_operator.csv": "d5d9a19ea6f8a5cdd25810f2e6a1e35ed039e45463d56a3f208c8b9151698ed7",
        "initial_states.csv": "c018a437ab10e8f6786fcfe8ff0be4bbad45dbc3a83118b8dfef46b275b4ad21",
        "long_energy.csv": "4251e29b09b922c76d487b9884fc5e560f73cf0a2eed083ffbc85fd3a6566099",
        "mapping.csv": "129668990414470cf33cdc234177896562acd34b800440a85e4867ca5a4d856f",
        "metadata.csv": "8b7a456878b2d8e3f75550cb8cb434f9e861c5e6f4249d46dda8045fca3d5cb0",
        "parent_fingerprint.csv": "9802cf098a77f21b2d30e9abc8c045cd2425efcf0e2d47f7bd2d31bbc2f73e4f",
        "primitive_diagnostics.csv": "7bc891be789f853566757009855317569a96e29b1ff99250bea7808b0470f858",
        "reference_packets.csv": "907cc08a3f6a8db48143e35d0ee247dccf687cc42ba617f28ff213219312994f",
        "relation_primitive_diagnostics.csv": "aed093b5e8329bb9e5d16de5619e546e37675fb2cfeb7b7097f9283b0bec4399",
        "relations.csv": "5b50a04399f9868a9fdc0fe3e263e162aa3a4d52b0be03b11a6cb17a689bece0",
        "reversibility.csv": "5dd215fbe8e6c9743dd072cf43791410ceacf6ab8ef2d1c3107fece759752c28",
        "units.csv": "5f7310161e356739c5bf0989b47c58fe35eb5d5241f7e3542da276f1d77c0e77",
    }
    require(len(fingerprints) == len(expected_hashes),
            "parent fingerprint file count differs")
    require(set(actual) == set(expected_hashes), "parent fingerprint inventory differs")
    for filename, expected in expected_hashes.items():
        observed = sha256(parent_raw / filename)
        row = actual[filename]
        require(observed == expected == row["sha256"] == row["expected_sha256"] and boolean(row["passed"]),
                f"stop_inconclusive_or_wrong_parent: {filename}")
    for filename in ("reference_packets.csv", "relations.csv", "force_operator.csv"):
        require(sha256(raw / filename) == expected_hashes[filename],
                f"frozen copied parent input differs: {filename}")
    parent_meta = metadata(parent_raw / "metadata.csv")
    require(parent_meta.get("source_sha") == PARENT_SHA, "parent source SHA differs")
    require(parent_meta.get("decision", "reject_order_matched_space_time_corefinement")
            == "reject_order_matched_space_time_corefinement", "parent decision differs")
    return {"files": len(expected_hashes), "decision": "reject_order_matched_space_time_corefinement"}


def component(row: dict[str, str], name: str, axis: str) -> Fraction:
    coarse = int(row[f"{name}{axis}_coarse"])
    numerator = int(row[f"{name}{axis}_num"])
    denominator = int(row[f"{name}{axis}_den"])
    require(denominator > 0, "state denominator is nonpositive")
    residual = Fraction(numerator, denominator)
    require(residual.numerator == numerator and residual.denominator == denominator,
            "state fraction is not reduced")
    require(Fraction(-1, 2) <= residual < Fraction(1, 2), "state residual is noncanonical")
    require(-(2**63) <= coarse < 2**63, "coarse state outside signed64")
    return Fraction(coarse) + residual


def encode_unsigned(value: int) -> bytes:
    require(value >= 0, "negative unsigned canonical integer")
    magnitude = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return len(magnitude).to_bytes(8, "little") + magnitude


def encode_signed(value: int) -> bytes:
    return (b"\x01" if value < 0 else b"\x00") + encode_unsigned(abs(value))


def encode_fraction(value: Fraction) -> bytes:
    return encode_signed(value.numerator) + encode_unsigned(value.denominator)


def encode_vector(value: tuple[Fraction, ...] | list[Fraction]) -> bytes:
    return b"".join(encode_fraction(component_) for component_ in value)


def vector_hash(value: tuple[Fraction, ...] | list[Fraction]) -> str:
    return hashlib.sha256(encode_vector(value)).hexdigest()


def encode_state_rows(state_rows: list[dict[str, str]]) -> bytes:
    require(bool(state_rows), "empty canonical state")
    times = {int(row["time_raw"]) for row in state_rows}
    require(len(times) == 1, "canonical state has mixed times")
    packets = sorted(state_rows, key=lambda row: int(row["packet_id"]))
    identifiers = [int(row["packet_id"]) for row in packets]
    require(len(set(identifiers)) == len(identifiers), "canonical state has duplicate packet IDs")
    output = bytearray(b"MLS-FRACTIONAL-PHASE-v1\x00")
    output.extend(encode_signed(next(iter(times))))
    output.extend(len(packets).to_bytes(8, "little"))
    for row, identifier in zip(packets, identifiers):
        mass = int(row["mass_raw"])
        require(identifier > 0 and mass > 0, "canonical state packet identity invalid")
        output.extend(identifier.to_bytes(8, "little"))
        output.extend(mass.to_bytes(8, "little", signed=True))
        for name in ("x", "p"):
            for axis in "xyz":
                value = component(row, name, axis)
                coarse = int(row[f"{name}{axis}_coarse"])
                residual = Fraction(
                    int(row[f"{name}{axis}_num"]),
                    int(row[f"{name}{axis}_den"]),
                )
                canonical_coarse = (value + Fraction(1, 2)).numerator // (
                    value + Fraction(1, 2)
                ).denominator
                require(coarse == canonical_coarse and value - coarse == residual,
                        "canonical state carry differs")
                output.extend(coarse.to_bytes(8, "little", signed=True))
                output.extend(encode_fraction(residual))
    return bytes(output)


def verify_state_hash(state_rows: list[dict[str, str]]) -> str:
    hashes = {row["state_hash"] for row in state_rows}
    require(len(hashes) == 1, "state rows disagree on state hash")
    actual = hashlib.sha256(encode_state_rows(state_rows)).hexdigest()
    require(actual == next(iter(hashes)), "independent canonical state hash differs")
    return actual


def exact_invariants(state_rows: list[dict[str, str]]) -> tuple[tuple[Fraction, ...], tuple[Fraction, ...]]:
    momentum = [Fraction(), Fraction(), Fraction()]
    angular = [Fraction(), Fraction(), Fraction()]
    for row in state_rows:
        position = [component(row, "x", axis) for axis in "xyz"]
        packet_momentum = [component(row, "p", axis) for axis in "xyz"]
        for axis in range(3):
            momentum[axis] += packet_momentum[axis]
        angular[0] += position[1] * packet_momentum[2] - position[2] * packet_momentum[1]
        angular[1] += position[2] * packet_momentum[0] - position[0] * packet_momentum[2]
        angular[2] += position[0] * packet_momentum[1] - position[1] * packet_momentum[0]
    return tuple(momentum), tuple(angular)


def verify_states(raw: Path) -> tuple[dict[tuple[str, str, int], list[Decimal]], bool]:
    initial = grouped(rows(raw / "initial_states.csv"), ("scenario_id",))
    for state_rows in initial.values():
        verify_state_hash(state_rows)
    endpoints_grouped = grouped(rows(raw / "endpoints.csv"), ("scenario_id", "path", "level"))
    expected_keys = {(scenario, path, str(level)) for scenario in SCENARIOS
                     for path in (CONTROL, KDK) for level in LEVELS}
    require(set(endpoints_grouped) == expected_keys, "endpoint inventory differs")
    result: dict[tuple[str, str, int], list[Decimal]] = {}
    invariants_pass = True
    for key, state_rows in endpoints_grouped.items():
        scenario, path, level_text = key
        level = int(level_text)
        require(len(state_rows) in {4, 6}, "endpoint packet count differs")
        require(all(row["status"] == "accepted" for row in state_rows), f"{key}: short trajectory failed")
        require(all(int(row["completed_steps"]) == STEP_COUNTS[level] for row in state_rows),
                f"{key}: short trajectory incomplete")
        require(all(int(row["dt_raw"]) == TIMESTEPS_RAW[level] for row in state_rows),
                f"{key}: timestep differs")
        state_rows.sort(key=lambda row: int(row["packet_id"]))
        verify_state_hash(state_rows)
        initial_rows = initial[(scenario,)]
        invariants_pass = invariants_pass and exact_invariants(state_rows) == exact_invariants(initial_rows)
        state = [mp(component(row, "x", axis) * LQ) for row in state_rows for axis in "xyz"]
        state.extend(mp(component(row, "p", axis) * PQ) for row in state_rows for axis in "xyz")
        result[(scenario, path, level)] = state
    require(invariants_pass, "endpoint exact rational invariant failed")
    return result, invariants_pass


def contains_window(values: list[float], low: float, high: float, count: int) -> bool:
    return any(all(low <= value <= high for value in values[start:start + count])
               for start in range(len(values) - count + 1))


def convergence_report(endpoints: dict[tuple[str, str, int], list[Decimal]],
                       smooth: dict[str, list[Decimal]]) -> tuple[dict[str, object], bool, bool]:
    report: dict[str, object] = {}
    kdk_pass = True
    controls_pass = True
    for scenario in SCENARIOS:
        scenario_report: dict[str, object] = {}
        path_orders: dict[str, list[float]] = {}
        for path in (CONTROL, KDK):
            count = len(endpoints[(scenario, path, 0)]) // 6
            errors = [foundation.state_norm_difference(endpoints[(scenario, path, level)], smooth[scenario], count)
                      for level in LEVELS]
            require(all(error > 0 for error in errors), f"{scenario}/{path}: zero endpoint error")
            orders = [math.log2(float(errors[index] / errors[index + 1])) for index in range(4)]
            path_orders[path] = orders
            scenario_report[path] = {
                "errors": [format(value, ".29E") for value in errors],
                "orders": orders,
            }
        candidate_window = contains_window(path_orders[KDK], 1.6, 2.4, 3)
        control_window = contains_window(path_orders[CONTROL], 0.6, 1.4, 2)
        separated = max(path_orders[KDK]) - max(path_orders[CONTROL]) >= 0.5
        scenario_report["candidate_second_order_window"] = candidate_window
        scenario_report["control_distinguishable"] = control_window and separated
        report[scenario] = scenario_report
        kdk_pass = kdk_pass and candidate_window
        controls_pass = controls_pass and control_window and separated
    return report, kdk_pass, controls_pass


def verify_accounting(raw: Path) -> tuple[dict[str, object], bool, bool]:
    initial = grouped(rows(raw / "initial_states.csv"), ("scenario_id",))
    initial_invariants = {
        scenario[0]: exact_invariants(state_rows)
        for scenario, state_rows in initial.items()
    }
    invariant_rows = rows(raw / "invariants.csv")
    invariant_pass = bool(invariant_rows)
    for row in invariant_rows:
        parts = row["trajectory_id"].split(":")
        require(len(parts) == 4 and parts[0] == "short" and parts[1] in SCENARIOS,
                "invariant trajectory identity differs")
        momentum = tuple(Fraction(int(row[f"p_{axis}_num"]), int(row[f"p_{axis}_den"]))
                         for axis in "xyz")
        angular = tuple(Fraction(int(row[f"l_{axis}_num"]), int(row[f"l_{axis}_den"]))
                        for axis in "xyz")
        expected_momentum, expected_angular = initial_invariants[parts[1]]
        invariant_pass = invariant_pass and (
            momentum == expected_momentum
            and angular == expected_angular
            and row["momentum_hash"] == vector_hash(momentum)
            and row["angular_hash"] == vector_hash(angular)
            and boolean(row["momentum_equal_initial"])
            and boolean(row["angular_equal_initial"])
        )
    force_rows = rows(raw / "force_audit.csv")
    central_pass = bool(force_rows) and all(
        boolean(row["central_cross_zero"]) and int(row["coefficient_bits"]) > 0
        and int(row["impulse_bits"]) > 0 and math.isfinite(float_from_bits(row["length_bits"]))
        and math.isfinite(float_from_bits(row["conjugate_bits"]))
        for row in force_rows
    )
    reversibility = rows(raw / "reversibility.csv")
    recovery_groups = grouped(rows(raw / "recovery_states.csv"), ("scenario_id", "level"))
    require(len(recovery_groups) == 15, "recovery state inventory differs")
    recovery_hashes: dict[tuple[str, str], str] = {}
    for key, state_rows in recovery_groups.items():
        require(encode_state_rows(state_rows) == encode_state_rows(initial[(key[0],)]),
                f"{key}: complete recovery state differs")
        recovery_hashes[key] = verify_state_hash(state_rows)
    reversible = len(reversibility) == 15 and all(
        row["forward_status"] == "accepted" and row["backward_status"] == "accepted"
        and row["initial_hash"] == verify_state_hash(initial[(row["scenario_id"],)])
        and row["recovered_hash"] == recovery_hashes[(row["scenario_id"], row["level"])]
        and row["initial_hash"] == row["recovered_hash"]
        and boolean(row["complete_state_identical"])
        for row in reversibility
    )
    checkpoints = rows(raw / "checkpoint.csv")
    checkpoint_groups = grouped(rows(raw / "checkpoint_states.csv"), ("scenario_id", "level"))
    require(len(checkpoint_groups) == 5, "checkpoint state inventory differs")
    checkpoint_values = {
        key: (verify_state_hash(state_rows), len(encode_state_rows(state_rows)))
        for key, state_rows in checkpoint_groups.items()
    }
    checkpoint_pass = len(checkpoints) == 5 and all(
        row["decoded_hash"] == row["checkpoint_hash"]
        == checkpoint_values[(row["scenario_id"], row["level"])][0]
        and int(row["checkpoint_bytes"])
        == checkpoint_values[(row["scenario_id"], row["level"])][1]
        and row["whole_final_hash"] == row["resumed_final_hash"]
        and boolean(row["event_suffix_identical"]) and boolean(row["canonical_round_trip"])
        for row in checkpoints
    )
    domains = rows(raw / "domain.csv")
    domain_pass = len(domains) == 5 and all(
        row["status"] == "chord_domain_failure" and row["prior_hash"] == row["returned_hash"]
        and boolean(row["time_unchanged"]) and boolean(row["state_unchanged"])
        and not boolean(row["energy_ledger_present"])
        for row in domains
    )
    covariance = rows(raw / "covariance.csv")
    kinds = {row["kind"] for row in covariance}
    require(kinds == {"translation", "galilean_boost", "proper_lattice_rotation", "packet_permutation"},
            "covariance inventory differs")
    frame_pass = len(covariance) == 20 and all(
        row["status"] == "accepted"
        and Fraction(int(row["position_discrepancy_num"]), int(row["position_discrepancy_den"])) == 0
        and Fraction(int(row["momentum_discrepancy_num"]), int(row["momentum_discrepancy_den"])) == 0
        for row in covariance
    )
    report = {
        "invariant_stage_rows": len(invariant_rows), "exact_stage_invariants": invariant_pass,
        "force_relation_rows": len(force_rows), "exact_central_kicks": central_pass,
        "reversibility_rows": len(reversibility), "complete_state_reversible": reversible,
        "checkpoint_rows": len(checkpoints), "checkpoint_exact": checkpoint_pass,
        "domain_rows": len(domains), "domain_atomic": domain_pass,
        "covariance_rows": len(covariance), "translation_rotation_permutation_exact": frame_pass,
    }
    return report, all((invariant_pass, central_pass, reversible, checkpoint_pass, domain_pass)), frame_pass


def complexity_report(raw: Path) -> tuple[dict[str, object], bool]:
    values = rows(raw / "state_complexity.csv")
    require(values, "state complexity evidence missing")
    per_trajectory: dict[str, dict[str, object]] = {}
    grouped_rows = grouped(values, ("trajectory_id",))
    any_exceeded = False
    for (trajectory,), trajectory_rows in sorted(grouped_rows.items()):
        bits = [int(row["numerator_bits"]) for row in trajectory_rows]
        bits.extend(int(row["denominator_bits"]) for row in trajectory_rows)
        maximum = max(bits)
        median = statistics.median(bits)
        checkpoint = max(int(row["checkpoint_bytes"]) for row in trajectory_rows)
        state_groups = grouped(trajectory_rows, ("step", "time_raw"))
        crossing_steps: list[int] = []
        maximum_state_median = 0.0
        for (step_text, _time_raw), state_rows in state_groups.items():
            state_bits = [int(row["numerator_bits"]) for row in state_rows]
            state_bits.extend(int(row["denominator_bits"]) for row in state_rows)
            state_maximum = max(state_bits)
            state_median = statistics.median(state_bits)
            maximum_state_median = max(maximum_state_median, state_median)
            state_checkpoint = max(int(row["checkpoint_bytes"]) for row in state_rows)
            if (state_maximum > MAX_COMPONENT_BITS
                    or state_median > MEDIAN_COMPONENT_BITS
                    or state_checkpoint > MAX_CHECKPOINT_BYTES):
                crossing_steps.append(int(step_text))
        exceeded = bool(crossing_steps)
        any_exceeded = any_exceeded or exceeded
        steps = sorted({int(row["step"]) for row in trajectory_rows})
        start_rows = [row for row in trajectory_rows if int(row["step"]) == steps[0]]
        end_rows = [row for row in trajectory_rows if int(row["step"]) == steps[-1]]
        start_max = max(max(int(row["numerator_bits"]), int(row["denominator_bits"])) for row in start_rows)
        end_max = max(max(int(row["numerator_bits"]), int(row["denominator_bits"])) for row in end_rows)
        per_trajectory[trajectory] = {
            "recorded_steps": len(steps), "last_step": steps[-1], "maximum_bits": maximum,
            "median_bits_over_trajectory": median,
            "maximum_state_median_bits": maximum_state_median,
            "maximum_checkpoint_bytes": checkpoint,
            "maximum_bit_growth": end_max - start_max, "ceiling_exceeded": exceeded,
            "first_crossing_step": min(crossing_steps) if crossing_steps else None,
        }
    return {
        "rows": len(values), "maximum_component_bits": max(
            max(int(row["numerator_bits"]), int(row["denominator_bits"])) for row in values),
        "maximum_checkpoint_bytes": max(int(row["checkpoint_bytes"]) for row in values),
        "any_ceiling_exceeded": any_exceeded, "trajectories": per_trajectory,
    }, any_exceeded


def energy_report(raw: Path) -> dict[str, object]:
    short = grouped(rows(raw / "energies.csv"), ("scenario_id", "path", "level"))
    short_report: dict[str, object] = {}
    short_contracts = True
    for scenario in SCENARIOS:
        scenario_report: dict[str, object] = {}
        for path in (CONTROL, KDK):
            envelopes: list[float] = []
            finals: list[float] = []
            for level in LEVELS:
                values = [float_from_bits(row["mechanical_energy_bits"])
                          for row in short[(scenario, path, str(level))]]
                require(len(values) == STEP_COUNTS[level] + 1, f"{scenario}/{path}/{level}: energy trace incomplete")
                errors = [value - values[0] for value in values]
                envelopes.append(max(abs(value) for value in errors))
                finals.append(errors[-1])
            orders = [math.log2(envelopes[index] / envelopes[index + 1]) for index in range(4)]
            scenario_report[path] = {"maximum_excursions": envelopes, "final_errors": finals, "orders": orders}
            if path == KDK:
                short_contracts = short_contracts and contains_window(orders, 1.6, 2.4, 3)
        short_report[scenario] = scenario_report
    long_groups = grouped(rows(raw / "long_energy.csv"), ("level",))
    long_report: list[dict[str, object]] = []
    for level in LEVELS:
        group_rows = long_groups[(str(level),)]
        values = [float_from_bits(row["mechanical_energy_bits"]) for row in group_rows]
        errors = [value - values[0] for value in values]
        mean = sum(errors) / len(errors)
        x_mean = (len(errors) - 1) / 2
        denominator = sum((index - x_mean) ** 2 for index in range(len(errors)))
        slope = 0.0 if denominator == 0 else sum(
            (index - x_mean) * (value - mean) for index, value in enumerate(errors)) / denominator
        long_report.append({
            "level": level, "status": group_rows[0]["status"], "samples": len(values),
            "maximum_excursion": max(abs(value) for value in errors), "final_error": errors[-1],
            "mean_offset": mean, "slope_per_second": slope / float(TIMESTEPS_RAW[level] * TQ),
        })
    long_complete = all(row["status"] == "accepted" for row in long_report)
    long_contracts = False
    if long_complete:
        excursions = [float(row["maximum_excursion"]) for row in long_report]
        final_errors = [abs(float(row["final_error"])) for row in long_report]
        slopes = [abs(float(row["slope_per_second"])) for row in long_report]
        long_contracts = (
            all(excursions[index + 1] < excursions[index] for index in range(4))
            and final_errors[-1] < final_errors[0]
            and slopes[-1] < slopes[0]
        )
    return {
        "short": short_report,
        "long": long_report,
        "short_energy_contracts": short_contracts,
        "long_run_complete": long_complete,
        "long_energy_contracts": long_contracts if long_complete else "blocked_by_complexity_ceiling",
    }


def verify_obstruction(raw: Path) -> dict[str, object]:
    evidence = rows(raw / "obstruction.csv")
    require(len(evidence) >= 3, "obstruction evidence missing")
    for row in evidence:
        gr = int(row["relation_gcd"])
        gp = int(row["momentum_gcd"])
        r2 = Fraction(int(row["relation_squared"]))
        p2 = Fraction(int(row["momentum_squared"]))
        impulse = ratio(row["minimum_impulse_squared"])
        drift = ratio(row["minimum_drift_squared"])
        expected = r2 * p2 / (gr * gr * gp * gp)
        require(impulse * drift == expected == ratio(row["product"]) == ratio(row["expected_product"])
                and boolean(row["unit_independent"]), "reciprocal obstruction identity failed")
    return {"rows": len(evidence), "unit_independent_squared_product": True}


def verify(raw: Path, parent_raw: Path, allow_dirty: bool = False,
           precomputed_oracle: tuple[dict[str, list[Decimal]], dict[str, Decimal]] | None = None) -> dict[str, object]:
    meta = verify_schema_and_metadata(raw, allow_dirty)
    parent_report = verify_parent(raw, parent_raw)
    parent_units = parent.verify_units(parent_raw)
    models = parent.load_models(parent_raw, parent_units)
    initial = parent.load_initial_physical(parent_raw, parent_units)
    smooth, refinements = foundation.oracle_states(models, initial) if precomputed_oracle is None else precomputed_oracle
    endpoints, endpoint_invariants = verify_states(raw)
    convergence, convergence_pass, control_pass = convergence_report(endpoints, smooth)
    accounting, accounting_pass, frame_pass = verify_accounting(raw)
    complexity, complexity_exceeded = complexity_report(raw)
    energy = energy_report(raw)
    obstruction = verify_obstruction(raw)

    if parent_report["decision"] != "reject_order_matched_space_time_corefinement":
        decision = "stop_inconclusive_or_wrong_parent"
    elif not endpoint_invariants or not accounting_pass:
        decision = "reject_fractional_phase_state_accounting"
    elif (not convergence_pass or not control_pass or not frame_pass
          or energy["short_energy_contracts"] is not True):
        decision = "reject_fractional_phase_state_as_quantization_cure"
    elif complexity_exceeded:
        decision = "fractional_phase_state_restores_dynamics_but_bounded_representation_unresolved"
    elif energy["long_energy_contracts"] is not True:
        decision = "reject_fractional_phase_state_as_quantization_cure"
    else:
        decision = "retain_explicit_fractional_phase_state_for_research"
    return {
        "schema": "mls.explicit-fractional-phase-state.oracle.v1",
        "precision_decimal_digits": getcontext().prec,
        "source_sha": meta["source_sha"],
        "parent_fingerprint": parent_report,
        "obstruction": obstruction,
        "oracle_refinement_errors": {key: format(value, ".29E") for key, value in refinements.items()},
        "convergence": convergence,
        "endpoint_invariants_independently_recomputed": endpoint_invariants,
        "accounting": accounting,
        "state_complexity": complexity,
        "energy": energy,
        "decision": decision,
        "promotion": "NO_PROMOTION",
        "raw_files": {filename: sha256(raw / filename) for filename in FILES},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--parent-raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    arguments = parser.parse_args()
    try:
        result = verify(arguments.raw, arguments.parent_raw, arguments.allow_dirty)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"EXPLICIT FRACTIONAL PHASE STATE ORACLE: PASS {result['decision']} NO_PROMOTION")
        return 0
    except (OSError, ValueError, ArithmeticError, OracleError,
            parent.OracleError, foundation.OracleError) as error:
        print(f"EXPLICIT FRACTIONAL PHASE STATE ORACLE: FAIL {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
