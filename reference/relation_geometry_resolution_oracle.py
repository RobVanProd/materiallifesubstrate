#!/usr/bin/env python3
"""Independent bit-pattern oracle for the Relation Geometry Resolution Lab.

The input authority is the uint64 encoding of each binary64 value.  Decimal
renderings from the C++ producer are never parsed.  Path A and Path B are
reimplemented with Python binary64 operations; the physical oracle uses 120
decimal digits and independently assembles energy, force, and the complete
radial Hessian.  Nothing in this file is eligible mechanics or persistent
state, and it performs no time integration.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import struct
from dataclasses import dataclass
from decimal import Decimal as D
from decimal import localcontext
from pathlib import Path
from typing import Iterable, Mapping, Sequence


SCHEMA = "mls.relation-geometry-resolution.oracle.v1"
# The ordinary-scale adjacency probe changes a zero coordinate by as little as
# 2^-1074 beside unit coordinates.  About 324 decimal digits are required even
# to distinguish that exact binary64 value before the square root; 420 leaves
# a wide guard band for the downstream force and tangent arithmetic.
DIGITS = 420
FORCE_PARENT_HASHES = {
    "configurations.csv": "4183860d6dd2253b2d8dc72594b3d6c9d08c2e69fc877c31c03a0e98584571ce",
    "reference_packets.csv": "b63a251b1c2eb396eee6074f542bb815b94370882261574b5d9939acd9fe857b",
    "relations.csv": "c23f5e0d3d20373f38b8a42dba647e83015231551513230970a7dae9c56a9356",
    "operators.csv": "a2dbf33fca81d48c4666c0208598bc35ec1a7ba5375697945748d34b04405644",
    "h_matrix.csv": "641c7785a6fa86ee5d1da48ddb871036ca89f628134687a8bd3c7e82db5e3c87",
    "manifest.json": "b00633d6ca69ee8f67d8e878de6c1bbf817274e2941bc1d44240c7ad57fd10df",
}
PATH_A = "frozen_binary64"
PATH_B = "cancellation_resistant_binary64"
PATH_C = "transient_double_double"
RAW_FIELDS = {
    "reference_packets_bits.csv": (
        "configuration_id", "packet_index", "packet_id", "mass_quanta",
        "x_bits", "y_bits", "z_bits",
    ),
    "relations_bits.csv": (
        "configuration_id", "relation_index", "first_id", "second_id",
        "reference_length_bits", "weight_bits",
    ),
    "operators_bits.csv": (
        "operator_id", "configuration_id", "a_bits", "b_bits",
        "relation_count", "packet_count",
    ),
    "h_bits.csv": (
        "operator_id", "row_relation_index", "column_relation_index",
        "parent_bits", "frozen_bits",
    ),
    "evaluations.csv": (
        "evaluation_id", "operator_id", "path", "probe", "parameter",
        "ratio_bits", "status", "failed_relation_index", "energy_bits",
        "condition_resolved", "condition_bits", "largest_singular_bits",
        "smallest_nonzero_singular_bits", "ulp_force_sensitivity_bits",
        "adjacent_length_changed",
    ),
    "current_packets_bits.csv": (
        "evaluation_id", "packet_index", "packet_id", "x_bits", "y_bits", "z_bits",
    ),
    "geometry_bits.csv": (
        "evaluation_id", "relation_index", "first_id", "second_id", "status",
        "coordinate_coincident", "length_order", "current_offset_x_bits",
        "current_offset_y_bits", "current_offset_z_bits", "current_offset_low_x_bits",
        "current_offset_low_y_bits", "current_offset_low_z_bits", "current_length_bits",
        "current_length_low_bits", "extension_bits", "extension_low_bits",
        "direction_x_bits", "direction_y_bits", "direction_z_bits",
        "direction_low_x_bits", "direction_low_y_bits", "direction_low_z_bits",
        "squared_difference_bits", "squared_difference_low_bits", "conjugate_bits",
    ),
    "packet_forces_bits.csv": (
        "evaluation_id", "packet_index", "packet_id", "force_x_bits",
        "force_y_bits", "force_z_bits",
    ),
    "tangents_bits.csv": (
        "evaluation_id", "row_dof", "column_dof", "material_bits",
        "geometric_bits", "total_bits", "force_jacobian_bits",
    ),
}

VecD = tuple[D, D, D]
VecF = tuple[float, float, float]
MatrixD = list[list[D]]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def csv_fieldnames(path: Path) -> tuple[str, ...]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.reader(stream)
        return tuple(next(reader))


def fbits(value: float) -> int:
    return struct.unpack(">Q", struct.pack(">d", value))[0]


def bitsf(value: str | int) -> float:
    return struct.unpack(">d", struct.pack(">Q", int(value)))[0]


def bitsd(value: str | int) -> D:
    return D.from_float(bitsf(value))


def ordered_bits(value: float) -> int:
    raw = fbits(value)
    return (~raw & ((1 << 64) - 1)) if raw >> 63 else raw | (1 << 63)


def ulp_error(actual: float, expected: float) -> int:
    if math.isnan(actual) or math.isnan(expected):
        return (1 << 64) - 1
    return abs(ordered_bits(actual) - ordered_bits(expected))


def dsum(values: Iterable[D]) -> D:
    return sum(values, D(0))


def dsub(first: VecD, second: VecD) -> VecD:
    return tuple(first[i] - second[i] for i in range(3))  # type: ignore[return-value]


def ddot(first: Sequence[D], second: Sequence[D]) -> D:
    return dsum(a * b for a, b in zip(first, second, strict=True))


def dnorm(value: Sequence[D]) -> D:
    return ddot(value, value).sqrt()


def dscale(scale: D, value: VecD) -> VecD:
    return tuple(scale * component for component in value)  # type: ignore[return-value]


def dadd(first: VecD, second: VecD) -> VecD:
    return tuple(first[i] + second[i] for i in range(3))  # type: ignore[return-value]


def fsub(first: VecF, second: VecF) -> VecF:
    return tuple(first[i] - second[i] for i in range(3))  # type: ignore[return-value]


def stable_norm(value: VecF) -> float:
    scale = max(abs(value[0]), abs(value[1]), abs(value[2]))
    if scale == 0.0:
        return 0.0
    x = value[0] / scale
    y = value[1] / scale
    z = value[2] / scale
    return scale * math.sqrt((x * x + y * y) + z * z)


@dataclass(frozen=True)
class DD:
    hi: float = 0.0
    lo: float = 0.0


def quick_two_sum(larger: float, smaller: float) -> DD:
    total = larger + smaller
    return DD(total, smaller - (total - larger))


def two_sum(first: float, second: float) -> DD:
    total = first + second
    virtual_second = total - first
    error = (first - (total - virtual_second)) + (second - virtual_second)
    return DD(total, error)


def two_difference(first: float, second: float) -> DD:
    difference = first - second
    virtual_second = first - difference
    error = (first - (difference + virtual_second)) + (virtual_second - second)
    return DD(difference, error)


def ddadd(first: DD, second: DD) -> DD:
    total = first.hi + second.hi
    virtual_second = total - first.hi
    error = (first.hi - (total - virtual_second)) + (second.hi - virtual_second)
    error += first.lo + second.lo
    return quick_two_sum(total, error)


def ddneg(value: DD) -> DD:
    return DD(-value.hi, -value.lo)


def ddsub(first: DD, second: DD) -> DD:
    return ddadd(first, ddneg(second))


def ddmul(first: DD, second: DD) -> DD:
    product = first.hi * second.hi
    error = math.fma(first.hi, second.hi, -product)
    error += first.hi * second.lo + first.lo * second.hi
    error += first.lo * second.lo
    return quick_two_sum(product, error)


def dddiv(numerator: DD, denominator: DD) -> DD:
    quotient = DD(numerator.hi / denominator.hi, 0.0)
    for _ in range(2):
        residual = ddsub(numerator, ddmul(denominator, quotient))
        quotient = ddadd(quotient, DD(residual.hi / denominator.hi, 0.0))
    return quick_two_sum(quotient.hi, quotient.lo)


def squared_difference(
    reference_first: VecF,
    reference_second: VecF,
    current_first: VecF,
    current_second: VecF,
) -> DD:
    result = DD()
    for axis in range(3):
        displacement_difference = ddsub(
            two_difference(current_second[axis], reference_second[axis]),
            two_difference(current_first[axis], reference_first[axis]),
        )
        offset_sum = ddsub(
            two_sum(current_second[axis], reference_second[axis]),
            two_sum(current_first[axis], reference_first[axis]),
        )
        result = ddadd(result, ddmul(displacement_difference, offset_sum))
    return quick_two_sum(result.hi, result.lo)


@dataclass(frozen=True)
class BinaryGeometry:
    length: float
    extension: float
    extension_low: float
    direction: VecF
    order: str


def independent_path_a(
    frozen_l0: float, current_first: VecF, current_second: VecF
) -> BinaryGeometry:
    offset = fsub(current_second, current_first)
    length = stable_norm(offset)
    extension = length - frozen_l0
    direction = tuple(component / length for component in offset)
    order = "longer" if extension > 0 else "shorter" if extension < 0 else "equal"
    return BinaryGeometry(length, extension, 0.0, direction, order)  # type: ignore[arg-type]


def independent_path_b(
    frozen_l0: float,
    reference_first: VecF,
    reference_second: VecF,
    current_first: VecF,
    current_second: VecF,
) -> BinaryGeometry:
    offset = fsub(current_second, current_first)
    length = stable_norm(offset)
    numerator = squared_difference(
        reference_first, reference_second, current_first, current_second
    )
    extension = dddiv(numerator, DD(length + frozen_l0, 0.0))
    direction = tuple(component / length for component in offset)
    order = (
        "longer"
        if numerator.hi > 0 or (numerator.hi == 0 and numerator.lo > 0)
        else "shorter"
        if numerator.hi < 0 or (numerator.hi == 0 and numerator.lo < 0)
        else "equal"
    )
    return BinaryGeometry(length, extension.hi, extension.lo, direction, order)  # type: ignore[arg-type]


@dataclass(frozen=True)
class Model:
    operator_id: str
    configuration_id: str
    packet_ids: tuple[int, ...]
    reference: Mapping[int, VecD]
    reference_float: Mapping[int, VecF]
    relations: tuple[tuple[int, int], ...]
    frozen_lengths: tuple[D, ...]
    frozen_lengths_float: tuple[float, ...]
    h: tuple[tuple[D, ...], ...]


def load_models(raw: Path) -> dict[str, Model]:
    reference_by_configuration: dict[str, dict[int, VecD]] = {}
    reference_float_by_configuration: dict[str, dict[int, VecF]] = {}
    for row in rows(raw / "reference_packets_bits.csv"):
        configuration = row["configuration_id"]
        packet_id = int(row["packet_id"])
        reference_by_configuration.setdefault(configuration, {})[packet_id] = (
            bitsd(row["x_bits"]),
            bitsd(row["y_bits"]),
            bitsd(row["z_bits"]),
        )
        reference_float_by_configuration.setdefault(configuration, {})[packet_id] = (
            bitsf(row["x_bits"]),
            bitsf(row["y_bits"]),
            bitsf(row["z_bits"]),
        )
    relation_by_configuration: dict[str, list[tuple[int, int]]] = {}
    length_by_configuration: dict[str, list[D]] = {}
    length_float_by_configuration: dict[str, list[float]] = {}
    for row in rows(raw / "relations_bits.csv"):
        configuration = row["configuration_id"]
        relation_by_configuration.setdefault(configuration, []).append(
            (int(row["first_id"]), int(row["second_id"]))
        )
        length_by_configuration.setdefault(configuration, []).append(
            bitsd(row["reference_length_bits"])
        )
        length_float_by_configuration.setdefault(configuration, []).append(
            bitsf(row["reference_length_bits"])
        )
    h_rows = rows(raw / "h_bits.csv")
    models: dict[str, Model] = {}
    for operator in rows(raw / "operators_bits.csv"):
        operator_id = operator["operator_id"]
        configuration = operator["configuration_id"]
        count = int(operator["relation_count"])
        h = [[D(0) for _ in range(count)] for _ in range(count)]
        seen = 0
        for row in h_rows:
            if row["operator_id"] != operator_id:
                continue
            h[int(row["row_relation_index"])][int(row["column_relation_index"])] = bitsd(
                row["frozen_bits"]
            )
            seen += 1
        if seen != count * count:
            raise ValueError(f"incomplete H for {operator_id}")
        reference = reference_by_configuration[configuration]
        models[operator_id] = Model(
            operator_id,
            configuration,
            tuple(sorted(reference)),
            reference,
            reference_float_by_configuration[configuration],
            tuple(relation_by_configuration[configuration]),
            tuple(length_by_configuration[configuration]),
            tuple(length_float_by_configuration[configuration]),
            tuple(tuple(value for value in row) for row in h),
        )
    return models


def validate_raw_mirror(raw: Path, force_bundle: Path) -> None:
    selected_configurations = {"exact.tetrahedron_k4", "exact.octahedron_graph"}
    selected_operators = {
        row["operator_id"]
        for row in rows(force_bundle / "operators.csv")
        if row["configuration_id"] in selected_configurations
    }
    source_packets = {
        (row["configuration_id"], row["packet_id"]): (
            fbits(float.fromhex(row["x_m"])),
            fbits(float.fromhex(row["y_m"])),
            fbits(float.fromhex(row["z_m"])),
            row["mass_quanta"],
        )
        for row in rows(force_bundle / "reference_packets.csv")
        if row["configuration_id"] in selected_configurations
    }
    raw_packets = {
        (row["configuration_id"], row["packet_id"]): (
            int(row["x_bits"]), int(row["y_bits"]), int(row["z_bits"]),
            row["mass_quanta"],
        )
        for row in rows(raw / "reference_packets_bits.csv")
    }
    if raw_packets != source_packets:
        raise ValueError("raw reference coordinate bits differ from sealed force parent")
    source_relations = {
        (row["configuration_id"], row["relation_index"]): (
            row["first_id"], row["second_id"],
            fbits(float.fromhex(row["reference_length_m"])),
            fbits(float.fromhex(row["weight"])),
        )
        for row in rows(force_bundle / "relations.csv")
        if row["configuration_id"] in selected_configurations
    }
    raw_relations = {
        (row["configuration_id"], row["relation_index"]): (
            row["first_id"], row["second_id"],
            int(row["reference_length_bits"]), int(row["weight_bits"]),
        )
        for row in rows(raw / "relations_bits.csv")
    }
    if raw_relations != source_relations:
        raise ValueError("raw relation coordinates differ from sealed force parent")
    source_operators = {
        row["operator_id"]: (
            row["configuration_id"], fbits(float.fromhex(row["a_j_per_m2"])),
            fbits(float.fromhex(row["b_j_per_m2"])),
        )
        for row in rows(force_bundle / "operators.csv")
        if row["operator_id"] in selected_operators
    }
    raw_operators = {
        row["operator_id"]: (
            row["configuration_id"], int(row["a_bits"]), int(row["b_bits"]),
        )
        for row in rows(raw / "operators_bits.csv")
    }
    if raw_operators != source_operators:
        raise ValueError("raw operator policy differs from sealed force parent")
    source_h = {
        (row["operator_id"], row["row_relation_index"], row["column_relation_index"]): (
            fbits(float.fromhex(row["parent_value_j_per_m2"])),
            fbits(float.fromhex(row["frozen_value_j_per_m2"])),
        )
        for row in rows(force_bundle / "h_matrix.csv")
        if row["operator_id"] in selected_operators
    }
    raw_h = {
        (row["operator_id"], row["row_relation_index"], row["column_relation_index"]): (
            int(row["parent_bits"]), int(row["frozen_bits"]),
        )
        for row in rows(raw / "h_bits.csv")
    }
    if raw_h != source_h:
        raise ValueError("raw H bits differ from sealed force parent")


@dataclass(frozen=True)
class OracleEvaluation:
    lengths: tuple[D, ...]
    extensions: tuple[D, ...]
    directions: tuple[VecD, ...]
    conjugates: tuple[D, ...]
    energy: D
    forces: Mapping[int, VecD]
    material: MatrixD
    geometric: MatrixD
    total: MatrixD


def zeros(rows_count: int, columns_count: int) -> MatrixD:
    return [[D(0) for _ in range(columns_count)] for _ in range(rows_count)]


def evaluate_oracle(model: Model, current: Mapping[int, VecD]) -> OracleEvaluation:
    lengths: list[D] = []
    reference_exact_lengths: list[D] = []
    extensions: list[D] = []
    directions: list[VecD] = []
    for first, second in model.relations:
        reference_offset = dsub(model.reference[second], model.reference[first])
        offset = dsub(current[second], current[first])
        reference_length = dnorm(reference_offset)
        length = dnorm(offset)
        if length == 0:
            raise ZeroDivisionError("coincident relation")
        reference_exact_lengths.append(reference_length)
        lengths.append(length)
        extensions.append(length - reference_length)
        directions.append(dscale(D(1) / length, offset))
    conjugates = [
        dsum(model.h[row][column] * extensions[column] for column in range(len(extensions)))
        for row in range(len(extensions))
    ]
    energy = D("0.5") * dsum(
        extensions[index] * conjugates[index] for index in range(len(extensions))
    )
    forces: dict[int, VecD] = {packet_id: (D(0), D(0), D(0)) for packet_id in model.packet_ids}
    dofs = 3 * len(model.packet_ids)
    id_index = {packet_id: index for index, packet_id in enumerate(model.packet_ids)}
    rigidity = zeros(len(model.relations), dofs)
    for relation_index, (first, second) in enumerate(model.relations):
        relation_force = dscale(conjugates[relation_index], directions[relation_index])
        forces[first] = dadd(forces[first], relation_force)
        forces[second] = dadd(forces[second], dscale(D(-1), relation_force))
        for axis in range(3):
            rigidity[relation_index][3 * id_index[first] + axis] = -directions[relation_index][axis]
            rigidity[relation_index][3 * id_index[second] + axis] = directions[relation_index][axis]
    h_times_r = zeros(len(model.relations), dofs)
    for row in range(len(model.relations)):
        for column in range(dofs):
            h_times_r[row][column] = dsum(
                model.h[row][inner] * rigidity[inner][column]
                for inner in range(len(model.relations))
            )
    material = zeros(dofs, dofs)
    for row in range(dofs):
        for column in range(dofs):
            material[row][column] = dsum(
                rigidity[relation][row] * h_times_r[relation][column]
                for relation in range(len(model.relations))
            )
    geometric = zeros(dofs, dofs)
    for relation_index, (first, second) in enumerate(model.relations):
        direction = directions[relation_index]
        scale = conjugates[relation_index] / lengths[relation_index]
        first_index = id_index[first]
        second_index = id_index[second]
        for axis in range(3):
            for component_axis in range(3):
                projector = (D(1) if axis == component_axis else D(0)) - direction[axis] * direction[component_axis]
                contribution = scale * projector
                geometric[3 * first_index + axis][3 * first_index + component_axis] += contribution
                geometric[3 * second_index + axis][3 * second_index + component_axis] += contribution
                geometric[3 * first_index + axis][3 * second_index + component_axis] -= contribution
                geometric[3 * second_index + axis][3 * first_index + component_axis] -= contribution
    total = [
        [material[row][column] + geometric[row][column] for column in range(dofs)]
        for row in range(dofs)
    ]
    return OracleEvaluation(
        tuple(lengths), tuple(extensions), tuple(directions), tuple(conjugates),
        energy, forces, material, geometric, total
    )


def frobenius(matrix: Sequence[Sequence[D]]) -> D:
    return dsum(value * value for row in matrix for value in row).sqrt()


def max_abs_matrix(matrix: Sequence[Sequence[D]]) -> D:
    return max((abs(value) for row in matrix for value in row), default=D(0))


def maximum_matrix_error(
    actual: Mapping[tuple[int, int], tuple[float, float, float, float]],
    oracle: OracleEvaluation,
) -> tuple[D, D, D, D]:
    errors = [D(0), D(0), D(0), D(0)]
    for (row, column), values in actual.items():
        expected = (
            oracle.material[row][column],
            oracle.geometric[row][column],
            oracle.total[row][column],
            -oracle.total[row][column],
        )
        for index in range(4):
            errors[index] = max(errors[index], abs(D.from_float(values[index]) - expected[index]))
    return tuple(errors)  # type: ignore[return-value]


def spectrum(total: MatrixD, nonrigid_rank: int) -> tuple[D, D, D]:
    matrix = [list(row) for row in total]
    dimension = len(matrix)
    scale = max_abs_matrix(matrix)
    tolerance = scale * (D(10) ** -(DIGITS - 60))
    converged = dimension < 2
    for _sweep in range(1024):
        rotated = False
        for first in range(dimension):
            for second in range(first + 1, dimension):
                correlation = matrix[first][second]
                if abs(correlation) <= tolerance:
                    continue
                first_value = matrix[first][first]
                second_value = matrix[second][second]
                zeta = (second_value - first_value) / (D(2) * correlation)
                tangent = (
                    D(1)
                    if zeta == 0
                    else (D(1) if zeta > 0 else D(-1))
                    / (abs(zeta) + (D(1) + zeta * zeta).sqrt())
                )
                cosine = D(1) / (D(1) + tangent * tangent).sqrt()
                sine = tangent * cosine
                for index in range(dimension):
                    if index in (first, second):
                        continue
                    old_first = matrix[index][first]
                    old_second = matrix[index][second]
                    new_first = cosine * old_first - sine * old_second
                    new_second = sine * old_first + cosine * old_second
                    matrix[index][first] = new_first
                    matrix[first][index] = new_first
                    matrix[index][second] = new_second
                    matrix[second][index] = new_second
                matrix[first][first] = (
                    cosine * cosine * first_value
                    - D(2) * cosine * sine * correlation
                    + sine * sine * second_value
                )
                matrix[second][second] = (
                    sine * sine * first_value
                    + D(2) * cosine * sine * correlation
                    + cosine * cosine * second_value
                )
                matrix[first][second] = D(0)
                matrix[second][first] = D(0)
                rotated = True
        if not rotated:
            converged = True
            break
    if not converged:
        raise ArithmeticError("420-digit symmetric Jacobi eigensolver did not converge")
    singular = sorted((abs(matrix[index][index]) for index in range(dimension)), reverse=True)
    largest = singular[0]
    smallest = singular[nonrigid_rank - 1]
    condition = largest / smallest if smallest != 0 else D("Infinity")
    return smallest, largest, condition


def directional_gradient_residual(
    model: Model, current: Mapping[int, VecD], oracle: OracleEvaluation
) -> D:
    first, second = model.relations[0]
    direction = oracle.directions[0]
    characteristic = max(dnorm(dsub(model.reference[b], model.reference[a])) for a, b in model.relations)
    step = characteristic * D("1e-50")
    plus = dict(current)
    minus = dict(current)
    plus[second] = dadd(current[second], dscale(step, direction))
    minus[second] = dadd(current[second], dscale(-step, direction))
    plus_energy = evaluate_energy_only(model, plus)
    minus_energy = evaluate_energy_only(model, minus)
    numeric = (plus_energy - minus_energy) / (D(2) * step)
    analytic = -ddot(oracle.forces[second], direction)
    return abs(numeric - analytic)


def evaluate_energy_only(model: Model, current: Mapping[int, VecD]) -> D:
    extensions = []
    for first, second in model.relations:
        length = dnorm(dsub(current[second], current[first]))
        reference_length = dnorm(dsub(model.reference[second], model.reference[first]))
        extensions.append(length - reference_length)
    conjugates = [
        dsum(model.h[row][column] * extensions[column] for column in range(len(extensions)))
        for row in range(len(extensions))
    ]
    return D("0.5") * dsum(
        extensions[index] * conjugates[index] for index in range(len(extensions))
    )


def dtext(value: D) -> str:
    if not value.is_finite():
        return str(value)
    return "0" if value == 0 else format(value.normalize(), "E")


def sign_order(value: D) -> str:
    return "longer" if value > 0 else "shorter" if value < 0 else "equal"


def run(raw: Path, force_bundle: Path, output: Path) -> dict[str, object]:
    for name, expected_fields in RAW_FIELDS.items():
        if csv_fieldnames(raw / name) != expected_fields:
            raise ValueError(f"raw schema mismatch: {name}")
    for name, expected in FORCE_PARENT_HASHES.items():
        actual = sha256(force_bundle / name)
        if actual != expected:
            raise ValueError(f"immutable force parent hash mismatch: {name}")
    validate_raw_mirror(raw, force_bundle)
    models = load_models(raw)
    evaluation_rows = rows(raw / "evaluations.csv")
    current_rows = rows(raw / "current_packets_bits.csv")
    geometry_rows = rows(raw / "geometry_bits.csv")
    packet_force_rows = rows(raw / "packet_forces_bits.csv")
    tangent_rows = rows(raw / "tangents_bits.csv")
    current_by_evaluation: dict[str, dict[int, VecD]] = {}
    current_float_by_evaluation: dict[str, dict[int, VecF]] = {}
    for row in current_rows:
        evaluation_id = row["evaluation_id"]
        packet_id = int(row["packet_id"])
        current_by_evaluation.setdefault(evaluation_id, {})[packet_id] = (
            bitsd(row["x_bits"]), bitsd(row["y_bits"]), bitsd(row["z_bits"])
        )
        current_float_by_evaluation.setdefault(evaluation_id, {})[packet_id] = (
            bitsf(row["x_bits"]), bitsf(row["y_bits"]), bitsf(row["z_bits"])
        )
    geometry_by_evaluation: dict[str, list[dict[str, str]]] = {}
    for row in geometry_rows:
        geometry_by_evaluation.setdefault(row["evaluation_id"], []).append(row)
    force_by_evaluation: dict[str, dict[int, VecF]] = {}
    for row in packet_force_rows:
        force_by_evaluation.setdefault(row["evaluation_id"], {})[int(row["packet_id"])] = (
            bitsf(row["force_x_bits"]), bitsf(row["force_y_bits"]), bitsf(row["force_z_bits"])
        )
    tangent_by_evaluation: dict[str, dict[tuple[int, int], tuple[float, float, float, float]]] = {}
    for row in tangent_rows:
        tangent_by_evaluation.setdefault(row["evaluation_id"], {})[
            (int(row["row_dof"]), int(row["column_dof"]))
        ] = (
            bitsf(row["material_bits"]), bitsf(row["geometric_bits"]),
            bitsf(row["total_bits"]), bitsf(row["force_jacobian_bits"]),
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    details_path = output.with_suffix(".csv")
    fieldnames = [
        "evaluation_id", "operator_id", "path", "probe", "parameter",
        "oracle_status", "path_a_exact_match", "path_b_exact_match",
        "maximum_length_ulp", "maximum_extension_ulp", "maximum_direction_ulp",
        "order_pass", "nonzero_pass", "energy_abs_error", "force_max_abs_error",
        "material_max_abs_error", "geometric_max_abs_error", "total_max_abs_error",
        "force_jacobian_max_abs_error", "oracle_material_norm", "oracle_geometric_norm",
        "oracle_total_norm", "oracle_smallest_nonrigid_singular",
        "oracle_largest_singular", "oracle_condition", "gradient_residual",
        "condition_classification_pass", "one_ulp_pass", "forward_identity_pass",
        "row_pass",
    ]
    detail_rows: list[dict[str, str]] = []
    counts = {
        "evaluations": 0,
        "coincident": 0,
        "path_a_exact_failures": 0,
        "path_b_exact_failures": 0,
        "selectable_failures": {PATH_B: 0, PATH_C: 0},
        "adjacency_failures": {PATH_A: 0, PATH_B: 0, PATH_C: 0},
    }
    collapse_pass: dict[str, dict[int, bool]] = {PATH_B: {}, PATH_C: {}}
    oracle_collapse: dict[str, dict[int, tuple[D, D]]] = {}
    oracle_cache: dict[tuple[str, tuple[D, ...]], OracleEvaluation] = {}
    spectrum_cache: dict[tuple[str, tuple[D, ...]], tuple[D, D, D]] = {}
    gradient_cache: dict[tuple[str, tuple[D, ...]], D] = {}
    with localcontext() as context:
        context.prec = DIGITS
        for evaluation in evaluation_rows:
            counts["evaluations"] += 1
            evaluation_id = evaluation["evaluation_id"]
            model = models[evaluation["operator_id"]]
            path = evaluation["path"]
            if evaluation["status"] == "coincident_relation":
                counts["coincident"] += 1
                clean = (
                    evaluation_id not in geometry_by_evaluation
                    and evaluation_id not in force_by_evaluation
                    and evaluation_id not in tangent_by_evaluation
                )
                detail_rows.append({
                    **{name: "not_emitted" for name in fieldnames},
                    "evaluation_id": evaluation_id,
                    "operator_id": model.operator_id,
                    "path": path,
                    "probe": evaluation["probe"],
                    "parameter": evaluation["parameter"],
                    "oracle_status": "coincident_relation",
                    "row_pass": str(clean).lower(),
                })
                continue
            current = current_by_evaluation[evaluation_id]
            current_float = current_float_by_evaluation[evaluation_id]
            cache_key = (
                model.operator_id,
                tuple(
                    component
                    for packet_id in model.packet_ids
                    for component in current[packet_id]
                ),
            )
            if cache_key not in oracle_cache:
                oracle_cache[cache_key] = evaluate_oracle(model, current)
            oracle = oracle_cache[cache_key]
            geometry_actual = sorted(
                geometry_by_evaluation[evaluation_id], key=lambda row: int(row["relation_index"])
            )
            if len(geometry_actual) != len(model.relations):
                raise ValueError(f"geometry inventory mismatch: {evaluation_id}")
            maximum_length_ulp = 0
            maximum_extension_ulp = 0
            maximum_direction_ulp = 0
            order_pass = True
            nonzero_pass = True
            exact_a = True
            exact_b = True
            for index, row in enumerate(geometry_actual):
                expected_length = float(oracle.lengths[index])
                expected_extension = float(oracle.extensions[index])
                actual_length = bitsf(row["current_length_bits"])
                actual_extension = bitsf(row["extension_bits"])
                maximum_length_ulp = max(maximum_length_ulp, ulp_error(actual_length, expected_length))
                maximum_extension_ulp = max(maximum_extension_ulp, ulp_error(actual_extension, expected_extension))
                expected_order = sign_order(oracle.extensions[index])
                order_pass = order_pass and row["length_order"] == expected_order
                if expected_extension != 0.0:
                    nonzero_pass = nonzero_pass and actual_extension != 0.0
                for axis, name in enumerate(("x", "y", "z")):
                    actual_direction = bitsf(row[f"direction_{name}_bits"])
                    expected_direction = float(oracle.directions[index][axis])
                    maximum_direction_ulp = max(
                        maximum_direction_ulp, ulp_error(actual_direction, expected_direction)
                    )
                first, second = model.relations[index]
                if path == PATH_A:
                    independent = independent_path_a(
                        model.frozen_lengths_float[index], current_float[first], current_float[second]
                    )
                    exact_a = exact_a and (
                        fbits(independent.length) == int(row["current_length_bits"])
                        and fbits(independent.extension) == int(row["extension_bits"])
                        and independent.order == row["length_order"]
                        and all(
                            fbits(independent.direction[axis]) == int(row[f"direction_{name}_bits"])
                            for axis, name in enumerate(("x", "y", "z"))
                        )
                    )
                elif path == PATH_B:
                    independent = independent_path_b(
                        model.frozen_lengths_float[index], model.reference_float[first],
                        model.reference_float[second], current_float[first], current_float[second]
                    )
                    exact_b = exact_b and (
                        fbits(independent.length) == int(row["current_length_bits"])
                        and fbits(independent.extension) == int(row["extension_bits"])
                        and fbits(independent.extension_low) == int(row["extension_low_bits"])
                        and independent.order == row["length_order"]
                        and all(
                            fbits(independent.direction[axis]) == int(row[f"direction_{name}_bits"])
                            for axis, name in enumerate(("x", "y", "z"))
                        )
                    )
            if path == PATH_A and not exact_a:
                counts["path_a_exact_failures"] += 1
            if path == PATH_B and not exact_b:
                counts["path_b_exact_failures"] += 1
            energy_error = abs(bitsd(evaluation["energy_bits"]) - oracle.energy)
            maximum_force_error = D(0)
            for packet_id, expected in oracle.forces.items():
                actual = force_by_evaluation[evaluation_id][packet_id]
                for axis in range(3):
                    maximum_force_error = max(
                        maximum_force_error, abs(D.from_float(actual[axis]) - expected[axis])
                    )
            matrix_errors = maximum_matrix_error(tangent_by_evaluation[evaluation_id], oracle)
            if cache_key not in spectrum_cache:
                spectrum_cache[cache_key] = spectrum(
                    oracle.total, 3 * len(model.packet_ids) - 6
                )
            smallest, largest, condition = spectrum_cache[cache_key]
            if cache_key not in gradient_cache:
                gradient_cache[cache_key] = directional_gradient_residual(
                    model, current, oracle
                )
            gradient_residual = gradient_cache[cache_key]
            direction_pass = maximum_direction_ulp <= 8 or all(
                abs(D.from_float(bitsf(row[f"direction_{name}_bits"])) - oracle.directions[index][axis])
                <= D(64) * D.from_float(math.ulp(1.0)) * max(abs(oracle.directions[index][axis]), D(1))
                for index, row in enumerate(geometry_actual)
                for axis, name in enumerate(("x", "y", "z"))
            )
            geometry_pass = (
                maximum_length_ulp <= 4
                and maximum_extension_ulp <= 4
                and direction_pass
                and order_pass
                and nonzero_pass
            )
            exact_path_pass = exact_a if path == PATH_A else exact_b if path == PATH_B else True
            epsilon = D(2) ** -52
            minimum_normal = D(2) ** -1022
            dimension = 3 * len(model.packet_ids)
            energy_tolerance = D(65536 * dimension) * epsilon * max(
                abs(oracle.energy), minimum_normal
            )
            force_scale = max(
                (abs(value) for vector in oracle.forces.values() for value in vector),
                default=minimum_normal,
            )
            force_tolerance = D(65536 * dimension) * epsilon * max(
                force_scale, minimum_normal
            )
            tangent_scales = (
                max_abs_matrix(oracle.material), max_abs_matrix(oracle.geometric),
                max_abs_matrix(oracle.total), max_abs_matrix(oracle.total),
            )
            tangent_pass = all(
                matrix_errors[index]
                <= D(262144 * dimension) * epsilon * max(tangent_scales[index], minimum_normal)
                for index in range(4)
            )
            forward_scale = max(abs(oracle.energy), minimum_normal)
            gradient_pass = gradient_residual <= max(
                D("1e-50"), D("1e-40") * forward_scale
            )
            forward_identity_pass = (
                energy_error <= energy_tolerance
                and maximum_force_error <= force_tolerance
                and tangent_pass
                and gradient_pass
            )
            condition_pass = evaluation["condition_resolved"] == "true"
            one_ulp_pass = evaluation["adjacent_length_changed"] == "true"
            row_pass = (
                geometry_pass
                and exact_path_pass
                and forward_identity_pass
                and condition_pass
                and one_ulp_pass
            )
            if path in (PATH_B, PATH_C) and not row_pass:
                counts["selectable_failures"][path] += 1
            if evaluation["probe"] == "adjacency" and not row_pass:
                counts["adjacency_failures"][path] += 1
            if evaluation["probe"] == "collapse" and path in (PATH_B, PATH_C):
                exponent = int(evaluation["parameter"])
                collapse_pass[path][exponent] = collapse_pass[path].get(exponent, True) and row_pass
            if evaluation["probe"] == "collapse" and path == PATH_B:
                oracle_collapse.setdefault(model.operator_id, {})[
                    int(evaluation["parameter"])
                ] = (frobenius(oracle.geometric), condition)
            detail_rows.append({
                "evaluation_id": evaluation_id,
                "operator_id": model.operator_id,
                "path": path,
                "probe": evaluation["probe"],
                "parameter": evaluation["parameter"],
                "oracle_status": "evaluated",
                "path_a_exact_match": str(exact_a).lower() if path == PATH_A else "not_applicable",
                "path_b_exact_match": str(exact_b).lower() if path == PATH_B else "not_applicable",
                "maximum_length_ulp": str(maximum_length_ulp),
                "maximum_extension_ulp": str(maximum_extension_ulp),
                "maximum_direction_ulp": str(maximum_direction_ulp),
                "order_pass": str(order_pass).lower(),
                "nonzero_pass": str(nonzero_pass).lower(),
                "energy_abs_error": dtext(energy_error),
                "force_max_abs_error": dtext(maximum_force_error),
                "material_max_abs_error": dtext(matrix_errors[0]),
                "geometric_max_abs_error": dtext(matrix_errors[1]),
                "total_max_abs_error": dtext(matrix_errors[2]),
                "force_jacobian_max_abs_error": dtext(matrix_errors[3]),
                "oracle_material_norm": dtext(frobenius(oracle.material)),
                "oracle_geometric_norm": dtext(frobenius(oracle.geometric)),
                "oracle_total_norm": dtext(frobenius(oracle.total)),
                "oracle_smallest_nonrigid_singular": dtext(smallest),
                "oracle_largest_singular": dtext(largest),
                "oracle_condition": dtext(condition),
                "gradient_residual": dtext(gradient_residual),
                "condition_classification_pass": str(condition_pass).lower(),
                "one_ulp_pass": str(one_ulp_pass).lower(),
                "forward_identity_pass": str(forward_identity_pass).lower(),
                "row_pass": str(row_pass).lower(),
            })
    with details_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(detail_rows)
    def safe_domain(values: Mapping[int, bool]) -> dict[str, object]:
        ordered = [0, -4, -8, -12, -16, -20, -24, -28, -32, -36, -40, -44, -48]
        first_failure: int | None = None
        last_pass: int | None = None
        for exponent in ordered:
            if not values.get(exponent, False):
                first_failure = exponent
                break
            last_pass = exponent
        if first_failure == 0 or last_pass is None:
            return {"established": False, "rho_min": None, "first_failure_exponent": first_failure}
        if first_failure is None:
            rho_exponent = -44
        else:
            rho_exponent = last_pass + 4
        return {
            "established": True,
            "rho_min": f"2^{rho_exponent}",
            "rho_min_exponent": rho_exponent,
            "last_contiguous_pass_exponent": last_pass,
            "first_failure_exponent": first_failure,
            "lower_reopened_passes_ignored": [
                exponent for exponent in ordered
                if first_failure is not None and exponent < first_failure and values.get(exponent, False)
            ],
        }

    intrinsic = True
    intrinsic_rows: dict[str, bool] = {}
    for operator_id, values in oracle_collapse.items():
        exponents = [-8, -12, -16, -20, -24, -28, -32, -36, -40, -44, -48]
        grows = all(
            values[exponents[index + 1]][0] > values[exponents[index]][0]
            and values[exponents[index + 1]][1] > values[exponents[index]][1]
            for index in range(len(exponents) - 1)
        )
        intrinsic_rows[operator_id] = grows
        intrinsic = intrinsic and grows
    safe_domains = {path: safe_domain(values) for path, values in collapse_pass.items()}
    selected_path = (
        PATH_B
        if counts["adjacency_failures"][PATH_B] == 0
        and safe_domains[PATH_B]["established"]
        else PATH_C
        if counts["adjacency_failures"][PATH_C] == 0
        and safe_domains[PATH_C]["established"]
        else None
    )
    summary: dict[str, object] = {
        "schema": SCHEMA,
        "digits": DIGITS,
        "input_authority": "uint64_binary64_bit_patterns",
        "force_parent_hashes": FORCE_PARENT_HASHES,
        "counts": counts,
        "collapse_pass_by_exponent": {
            path: {str(exponent): passed for exponent, passed in sorted(values.items(), reverse=True)}
            for path, values in collapse_pass.items()
        },
        "safe_domains": safe_domains,
        "intrinsic_growth_by_operator": intrinsic_rows,
        "intrinsic_collapse_domain_boundary_confirmed": intrinsic,
        "selected_geometry_path": selected_path,
        "selection_rule": "prefer_path_B_when_B_and_C_both_pass",
        "decision": (
            "retain_relation_geometry_with_explicit_safe_domain_for_research"
            if selected_path is not None
            else "reject_current_relation_geometry_arithmetic"
        ),
        "details_csv": details_path.name,
        "details_sha256": sha256(details_path),
        "promotion": "NO_PROMOTION",
    }
    expected_adjacency = {PATH_A: 18, PATH_B: 0, PATH_C: 0}
    if (
        counts["evaluations"] != 306
        or counts["coincident"] != 18
        or counts["path_a_exact_failures"] != 0
        or counts["path_b_exact_failures"] != 0
        or counts["adjacency_failures"] != expected_adjacency
        or not intrinsic
        or selected_path != PATH_B
        or summary["decision"]
        != "retain_relation_geometry_with_explicit_safe_domain_for_research"
        or any(
            safe_domains[path].get("rho_min_exponent") != -24
            for path in (PATH_B, PATH_C)
        )
    ):
        raise ValueError("registered scientific disposition or inventory mismatch")
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--force-bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    summary = run(arguments.raw, arguments.force_bundle, arguments.output)
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("RELATION GEOMETRY HIGH-PRECISION ORACLE COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
