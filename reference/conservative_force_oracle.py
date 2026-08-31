#!/usr/bin/env python3
"""Independent high-precision oracle for Conservative Force Consistency.

This file deliberately does not import, execute, or bind the C++ force
evaluator.  It reconstructs a frozen relation-space energy from reference and
current packet coordinates, differentiates it analytically, and checks the
finite conservative identities with Decimal arithmetic well beyond binary64.

The oracle is not a dynamics implementation.  It contains no time integrator,
force installation, damping, contact, fracture, gravity, or thermal ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal as D
from decimal import localcontext
from pathlib import Path
from random import Random
from typing import Iterable, Mapping, Sequence


SCHEMA = "mls.conservative-force-consistency.high-precision-oracle.v1"
SEED = 260828
DIGITS = 100
IMPLEMENTATION = (
    "independent Python standard-library Decimal analytic energy/gradient/"
    "Hessian plus high-precision energy directional differences; no C++ "
    "force result is accepted as a premise"
)

Vec3 = tuple[D, D, D]
Edge = tuple[int, int]
Matrix = list[list[D]]


class CoincidentRelationError(ValueError):
    """The length-coordinate derivative has no direction at coincidence."""


def d(value: str | int | D) -> D:
    return value if isinstance(value, D) else D(value)


def dtext(value: D) -> str:
    if not value.is_finite():
        return str(value)
    if value == 0:
        return "0"
    return format(value.normalize(), "E")


def dsum(values: Iterable[D]) -> D:
    return sum(values, D(0))


def vadd(first: Vec3, second: Vec3) -> Vec3:
    return tuple(first[i] + second[i] for i in range(3))  # type: ignore[return-value]


def vsub(first: Vec3, second: Vec3) -> Vec3:
    return tuple(first[i] - second[i] for i in range(3))  # type: ignore[return-value]


def vscale(scale: D, value: Vec3) -> Vec3:
    return tuple(scale * value[i] for i in range(3))  # type: ignore[return-value]


def dot(first: Sequence[D], second: Sequence[D]) -> D:
    return dsum(a * b for a, b in zip(first, second, strict=True))


def cross(first: Vec3, second: Vec3) -> Vec3:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def norm(value: Sequence[D]) -> D:
    return dot(value, value).sqrt()


def normalize(value: Vec3) -> Vec3:
    magnitude = norm(value)
    if magnitude == 0:
        raise ValueError("cannot normalize zero vector")
    return vscale(D(1) / magnitude, value)


def zeros(rows: int, columns: int) -> Matrix:
    return [[D(0) for _column in range(columns)] for _row in range(rows)]


def transpose(matrix: Sequence[Sequence[D]]) -> Matrix:
    return [list(column) for column in zip(*matrix, strict=True)] if matrix else []


def matvec(matrix: Sequence[Sequence[D]], vector: Sequence[D]) -> list[D]:
    return [dot(row, vector) for row in matrix]


def matmul(first: Sequence[Sequence[D]], second: Sequence[Sequence[D]]) -> Matrix:
    columns = transpose(second)
    return [[dot(row, column) for column in columns] for row in first]


def flatten(points: Mapping[int, Vec3], ids: Sequence[int]) -> list[D]:
    return [points[packet_id][axis] for packet_id in ids for axis in range(3)]


def unflatten(vector: Sequence[D], ids: Sequence[int]) -> dict[int, Vec3]:
    if len(vector) != 3 * len(ids):
        raise ValueError("packet vector size mismatch")
    return {
        packet_id: (vector[3 * index], vector[3 * index + 1], vector[3 * index + 2])
        for index, packet_id in enumerate(ids)
    }


def max_abs(values: Iterable[D]) -> D:
    return max((abs(value) for value in values), default=D(0))


def frobenius(matrix: Sequence[Sequence[D]]) -> D:
    return dsum(value * value for row in matrix for value in row).sqrt()


def canonical_edge(edge: Edge) -> Edge:
    if edge[0] <= 0 or edge[1] <= 0 or edge[0] == edge[1]:
        raise ValueError("relations require distinct positive packet IDs")
    return edge if edge[0] < edge[1] else (edge[1], edge[0])


@dataclass(frozen=True)
class RelationModel:
    packet_ids: tuple[int, ...]
    reference: Mapping[int, Vec3]
    relations: tuple[Edge, ...]
    reference_lengths: tuple[D, ...]
    h: tuple[tuple[D, ...], ...]
    reference_length_tolerance: D = D(0)

    def __post_init__(self) -> None:
        if tuple(sorted(self.packet_ids)) != self.packet_ids:
            raise ValueError("packet IDs must be canonical")
        if set(self.reference) != set(self.packet_ids):
            raise ValueError("reference packet IDs disagree")
        if any(canonical_edge(edge) != edge for edge in self.relations) or len(
            set(self.relations)
        ) != len(self.relations):
            raise ValueError("relations must be unique oriented-canonical coordinates")
        relation_count = len(self.relations)
        if len(self.reference_lengths) != relation_count:
            raise ValueError("reference length count mismatch")
        if len(self.h) != relation_count or any(
            len(row) != relation_count for row in self.h
        ):
            raise ValueError("H must be a complete square matrix")
        for index, edge in enumerate(self.relations):
            if edge[0] not in self.reference or edge[1] not in self.reference:
                raise ValueError("relation endpoint absent")
            actual = norm(vsub(self.reference[edge[1]], self.reference[edge[0]]))
            if actual <= 0 or abs(actual - self.reference_lengths[index]) > self.reference_length_tolerance:
                raise ValueError("frozen reference length mismatch")
        if any(self.h[i][j] != self.h[j][i] for i in range(relation_count) for j in range(relation_count)):
            raise ValueError("H must be symmetric")


@dataclass(frozen=True)
class Evaluation:
    energy: D
    extensions: tuple[D, ...]
    conjugates: tuple[D, ...]
    directions: tuple[Vec3, ...]
    lengths: tuple[D, ...]
    forces: Mapping[int, Vec3]


def reference_lengths(reference: Mapping[int, Vec3], relations: Sequence[Edge]) -> tuple[D, ...]:
    result: list[D] = []
    for first, second in relations:
        length = norm(vsub(reference[second], reference[first]))
        if length <= 0:
            raise CoincidentRelationError("reference relation is coincident")
        result.append(length)
    return tuple(result)


def build_local_collective_h(
    reference: Mapping[int, Vec3],
    relations: Sequence[Edge],
    weights: Sequence[D],
    a_coefficient: D,
    b_coefficient: D,
) -> Matrix:
    """Independently assemble the accepted incident-star H.

    Each packet contribution is
      B W + (A-B) (W l)(W l)^T / (l^T W l)
    on its incident relation coordinates.  No current geometry participates.
    """

    if a_coefficient <= 0 or b_coefficient <= 0:
        raise ValueError("collective coefficients must be positive")
    canonical = tuple(map(canonical_edge, relations))
    if tuple(sorted(canonical)) != canonical or len(set(canonical)) != len(canonical):
        raise ValueError("relations must be canonical and unique")
    if len(weights) != len(canonical) or any(weight <= 0 for weight in weights):
        raise ValueError("one positive frozen weight is required per relation")
    lengths = reference_lengths(reference, canonical)
    result = zeros(len(canonical), len(canonical))
    for packet_id in sorted(reference):
        incident = [
            index for index, edge in enumerate(canonical) if packet_id in edge
        ]
        if not incident:
            continue
        moment = dsum(weights[index] * lengths[index] ** 2 for index in incident)
        if moment <= 0:
            raise ValueError("positive incident weighted moment required")
        for row in incident:
            wl_row = weights[row] * lengths[row]
            for column in incident:
                wl_column = weights[column] * lengths[column]
                result[row][column] += (
                    (b_coefficient * weights[row] if row == column else D(0))
                    + (a_coefficient - b_coefficient)
                    * wl_row
                    * wl_column
                    / moment
                )
    return result


def make_model(
    reference: Mapping[int, Vec3], relations: Sequence[Edge], h: Sequence[Sequence[D]]
) -> RelationModel:
    canonical = tuple(map(canonical_edge, relations))
    return RelationModel(
        tuple(sorted(reference)),
        dict(reference),
        canonical,
        reference_lengths(reference, canonical),
        tuple(tuple(value for value in row) for row in h),
    )


def evaluate(model: RelationModel, current: Mapping[int, Vec3]) -> Evaluation:
    if set(current) != set(model.packet_ids):
        raise ValueError("current packet IDs disagree")
    lengths: list[D] = []
    directions: list[Vec3] = []
    extensions: list[D] = []
    for index, (first, second) in enumerate(model.relations):
        offset = vsub(current[second], current[first])
        length = norm(offset)
        if length == 0:
            raise CoincidentRelationError(
                f"relation {first}-{second} is outside |x_j-x_i|>0"
            )
        lengths.append(length)
        directions.append(vscale(D(1) / length, offset))
        extensions.append(length - model.reference_lengths[index])
    conjugates = matvec(model.h, extensions)
    energy = dot(extensions, conjugates) / 2
    forces = {packet_id: (D(0), D(0), D(0)) for packet_id in model.packet_ids}
    for index, (first, second) in enumerate(model.relations):
        relation_force = vscale(conjugates[index], directions[index])
        forces[first] = vadd(forces[first], relation_force)
        forces[second] = vsub(forces[second], relation_force)
    return Evaluation(
        energy,
        tuple(extensions),
        tuple(conjugates),
        tuple(directions),
        tuple(lengths),
        forces,
    )


def rigidity(model: RelationModel, current: Mapping[int, Vec3]) -> Matrix:
    evaluation = evaluate(model, current)
    lookup = {packet_id: index for index, packet_id in enumerate(model.packet_ids)}
    result = zeros(len(model.relations), 3 * len(model.packet_ids))
    for row, ((first, second), direction) in enumerate(
        zip(model.relations, evaluation.directions, strict=True)
    ):
        for axis in range(3):
            result[row][3 * lookup[first] + axis] = -direction[axis]
            result[row][3 * lookup[second] + axis] = direction[axis]
    return result


def tangent_decomposition(
    model: RelationModel, current: Mapping[int, Vec3]
) -> tuple[Matrix, Matrix, Matrix]:
    """Return material, geometric, and full energy Hessians."""

    evaluation = evaluate(model, current)
    r_matrix = rigidity(model, current)
    material = matmul(transpose(r_matrix), matmul(model.h, r_matrix))
    size = 3 * len(model.packet_ids)
    geometric = zeros(size, size)
    lookup = {packet_id: index for index, packet_id in enumerate(model.packet_ids)}
    identity = [[D(1) if i == j else D(0) for j in range(3)] for i in range(3)]
    for relation_index, (first, second) in enumerate(model.relations):
        direction = evaluation.directions[relation_index]
        scale = evaluation.conjugates[relation_index] / evaluation.lengths[relation_index]
        block = [
            [scale * (identity[i][j] - direction[i] * direction[j]) for j in range(3)]
            for i in range(3)
        ]
        first_index = lookup[first]
        second_index = lookup[second]
        for axis in range(3):
            for component in range(3):
                value = block[axis][component]
                geometric[3 * first_index + axis][3 * first_index + component] += value
                geometric[3 * second_index + axis][3 * second_index + component] += value
                geometric[3 * first_index + axis][3 * second_index + component] -= value
                geometric[3 * second_index + axis][3 * first_index + component] -= value
    total = [
        [material[row][column] + geometric[row][column] for column in range(size)]
        for row in range(size)
    ]
    return material, geometric, total


def force_vector(model: RelationModel, current: Mapping[int, Vec3]) -> list[D]:
    evaluation = evaluate(model, current)
    return flatten(evaluation.forces, model.packet_ids)


def shifted(
    points: Mapping[int, Vec3], ids: Sequence[int], direction: Sequence[D], step: D
) -> dict[int, Vec3]:
    base = flatten(points, ids)
    return unflatten(
        [value + step * delta for value, delta in zip(base, direction, strict=True)], ids
    )


def directional_derivative(
    model: RelationModel,
    current: Mapping[int, Vec3],
    direction: Sequence[D],
    step: D,
) -> D:
    plus = evaluate(model, shifted(current, model.packet_ids, direction, step)).energy
    minus = evaluate(model, shifted(current, model.packet_ids, direction, -step)).energy
    return (plus - minus) / (2 * step)


def extrapolate_polynomial_at_zero(abscissas: Sequence[D], values: Sequence[D]) -> D:
    """Evaluate the unique interpolation polynomial at zero.

    The force lab registers four centred estimates as a degree-three
    polynomial in t=h^2.  This direct Lagrange form is deterministic and is
    used only with high-precision Decimal values.
    """

    if len(abscissas) != len(values) or not abscissas:
        raise ValueError("extrapolation data mismatch")
    if len(set(abscissas)) != len(abscissas):
        raise ValueError("extrapolation abscissas must be distinct")
    result = D(0)
    for index, (x_value, y_value) in enumerate(zip(abscissas, values, strict=True)):
        weight = D(1)
        for other, x_other in enumerate(abscissas):
            if other != index:
                weight *= -x_other / (x_value - x_other)
        result += weight * y_value
    return result


def registered_raw_convergence(errors: Sequence[D], floor: D) -> bool:
    """Require every registered refinement transition until the error floor."""

    if len(errors) != 4:
        raise ValueError("registered raw convergence requires four levels")
    at_floor = errors[0] <= floor
    for index in range(3):
        if at_floor:
            if errors[index + 1] > floor:
                return False
            continue
        if errors[index + 1] <= floor:
            at_floor = True
            continue
        if errors[index + 1] >= errors[index]:
            return False
    return True


def extrapolated_directional_derivative(
    model: RelationModel,
    current: Mapping[int, Vec3],
    direction: Sequence[D],
    steps: Sequence[D],
) -> tuple[list[D], D]:
    raw = [directional_derivative(model, current, direction, step) for step in steps]
    return raw, extrapolate_polynomial_at_zero([step * step for step in steps], raw)


def numerical_force_jacobian(
    model: RelationModel, current: Mapping[int, Vec3], step: D
) -> Matrix:
    size = 3 * len(model.packet_ids)
    result = zeros(size, size)
    for column in range(size):
        direction = [D(0)] * size
        direction[column] = D(1)
        plus = force_vector(
            model, shifted(current, model.packet_ids, direction, step)
        )
        minus = force_vector(
            model, shifted(current, model.packet_ids, direction, -step)
        )
        for row in range(size):
            result[row][column] = (plus[row] - minus[row]) / (2 * step)
    return result


def extrapolated_force_jacobian(
    model: RelationModel, current: Mapping[int, Vec3], steps: Sequence[D]
) -> tuple[list[Matrix], Matrix]:
    raw = [numerical_force_jacobian(model, current, step) for step in steps]
    size = 3 * len(model.packet_ids)
    abscissas = [step * step for step in steps]
    result = zeros(size, size)
    for row in range(size):
        for column in range(size):
            result[row][column] = extrapolate_polynomial_at_zero(
                abscissas, [matrix[row][column] for matrix in raw]
            )
    return raw, result


def total_force(forces: Mapping[int, Vec3]) -> Vec3:
    return tuple(dsum(value[axis] for value in forces.values()) for axis in range(3))  # type: ignore[return-value]


def total_torque(
    points: Mapping[int, Vec3], forces: Mapping[int, Vec3], origin: Vec3
) -> Vec3:
    result = (D(0), D(0), D(0))
    for packet_id in sorted(points):
        result = vadd(result, cross(vsub(points[packet_id], origin), forces[packet_id]))
    return result


def power_control(
    model: RelationModel, current: Mapping[int, Vec3], velocity: Mapping[int, Vec3]
) -> tuple[D, D]:
    evaluation = evaluate(model, current)
    r_matrix = rigidity(model, current)
    velocity_vector = flatten(velocity, model.packet_ids)
    extension_rate = matvec(r_matrix, velocity_vector)
    energy_rate = dot(evaluation.conjugates, extension_rate)
    force_power = dot(force_vector(model, current), velocity_vector)
    return energy_rate, force_power


def transform_points(
    points: Mapping[int, Vec3], rotation: Sequence[Sequence[D]], translation: Vec3
) -> dict[int, Vec3]:
    return {
        packet_id: tuple(
            dot(rotation[row], point) + translation[row] for row in range(3)
        )  # type: ignore[misc]
        for packet_id, point in points.items()
    }


def transform_vectors(
    vectors: Mapping[int, Vec3], rotation: Sequence[Sequence[D]], scale: D = D(1)
) -> dict[int, Vec3]:
    return {
        packet_id: tuple(scale * dot(rotation[row], vector) for row in range(3))  # type: ignore[misc]
        for packet_id, vector in vectors.items()
    }


def permuted_model(model: RelationModel, order: Sequence[int], reverse_edges: bool) -> RelationModel:
    relations = [model.relations[index] for index in order]
    if reverse_edges:
        relations = [(second, first) for first, second in relations]
    permutation_h = [[model.h[row][column] for column in order] for row in order]
    # make_model canonicalizes only endpoint orientation, not row order; evaluate
    # is order-covariant, so construct the dataclass directly for this probe.
    canonical_relations = tuple(canonical_edge(edge) for edge in relations)
    lengths = tuple(model.reference_lengths[index] for index in order)
    return RelationModel(
        model.packet_ids,
        model.reference,
        canonical_relations,
        lengths,
        tuple(tuple(value for value in row) for row in permutation_h),
    )


def renamed_model(model: RelationModel, mapping: Mapping[int, int]) -> RelationModel:
    reference = {mapping[packet_id]: point for packet_id, point in model.reference.items()}
    raw_edges = [(mapping[first], mapping[second]) for first, second in model.relations]
    indexed = sorted(
        ((canonical_edge(edge), index) for index, edge in enumerate(raw_edges)),
        key=lambda item: item[0],
    )
    relations = tuple(edge for edge, _index in indexed)
    order = [index for _edge, index in indexed]
    h = [[model.h[row][column] for column in order] for row in order]
    return make_model(reference, relations, h)


def build_control_model(bulk_over_shear: D) -> RelationModel:
    reference: dict[int, Vec3] = {
        11: (D("0"), D("0"), D("0")),
        23: (D("1"), D("0"), D("0")),
        37: (D("0"), D("1"), D("0")),
        53: (D("0"), D("0"), D("1")),
    }
    relations = ((11, 23), (11, 37), (11, 53), (23, 37), (23, 53), (37, 53))
    weights = [D(1)] * len(relations)
    h = build_local_collective_h(
        reference,
        relations,
        weights,
        D(3) * bulk_over_shear / D(20),
        D(1) / D(4),
    )
    return make_model(reference, relations, h)


def deformed_points(reference: Mapping[int, Vec3]) -> dict[int, Vec3]:
    deformation = (
        (D("1.07"), D("0.08"), D("-0.03")),
        (D("0.02"), D("0.91"), D("0.05")),
        (D("0.04"), D("-0.01"), D("1.12")),
    )
    translation = (D("0.31"), D("-0.27"), D("0.19"))
    return transform_points(reference, deformation, translation)


def normalized_random_directions(size: int, count: int) -> list[list[D]]:
    random = Random(SEED)
    result: list[list[D]] = []
    for _ in range(count):
        raw = [D(random.randint(-31, 31)) for _entry in range(size)]
        magnitude = norm(raw)
        if magnitude == 0:
            raise AssertionError("registered random direction was zero")
        result.append([value / magnitude for value in raw])
    return result


def oracle_controls() -> dict:
    with localcontext() as context:
        context.prec = DIGITS
        ratios = (D(1) / D(3), D(2), D(10))
        ratio_results: list[dict] = []
        absolute_tolerance = D("1e-75")
        derivative_relative_tolerance = D("1e-45")
        derivative_absolute_tolerance = D("1e-55")
        tangent_relative_tolerance = D("1e-40")
        tangent_absolute_tolerance = D("1e-50")
        for ratio in ratios:
            model = build_control_model(ratio)
            current = deformed_points(model.reference)
            evaluation = evaluate(model, current)

            # Analytic -gradient plus high-precision energy derivatives.
            force = force_vector(model, current)
            gradient = [-value for value in force]
            directions: list[tuple[str, list[D]]] = []
            directions.extend(
                (f"random_{index}", value)
                for index, value in enumerate(
                    normalized_random_directions(len(force), 6)
                )
            )
            for axis in range(3):
                translation = [
                    D(1) if component % 3 == axis else D(0)
                    for component in range(len(force))
                ]
                translation_norm = norm(translation)
                directions.append(
                    (
                        f"translation_{axis}",
                        [value / translation_norm for value in translation],
                    )
                )
            centroid = tuple(
                dsum(current[packet_id][axis] for packet_id in model.packet_ids)
                / D(len(model.packet_ids))
                for axis in range(3)
            )
            for axis in range(3):
                omega = tuple(D(1) if component == axis else D(0) for component in range(3))
                rotation_map = {
                    packet_id: cross(omega, vsub(current[packet_id], centroid))
                    for packet_id in model.packet_ids
                }
                rotation = flatten(rotation_map, model.packet_ids)
                rotation_norm = norm(rotation)
                directions.append(
                    (
                        f"infinitesimal_rotation_{axis}",
                        [value / rotation_norm for value in rotation],
                    )
                )
            derivative_rows = []
            characteristic_length = max(model.reference_lengths)
            step_ratios = (D("1e-8"), D("1e-12"), D("1e-16"), D("1e-20"))
            derivative_steps = [characteristic_length * value for value in step_ratios]
            for label, direction in directions:
                analytic = dot(gradient, direction)
                raw, extrapolated = extrapolated_directional_derivative(
                    model, current, direction, derivative_steps
                )
                raw_residuals = [abs(value - analytic) for value in raw]
                residual = abs(extrapolated - analytic)
                allowed = max(
                    derivative_absolute_tolerance,
                    derivative_relative_tolerance * abs(analytic),
                )
                if not registered_raw_convergence(raw_residuals, allowed):
                    raise AssertionError(f"raw derivative convergence failed: {label}")
                if residual > allowed:
                    raise AssertionError(f"high-precision derivative failed: {label}")
                if (label.startswith("translation") or label.startswith("infinitesimal_rotation")) and abs(analytic) > derivative_absolute_tolerance:
                    raise AssertionError(f"rigid direction performed work: {label}")
                derivative_rows.append(
                    {
                        "direction": label,
                        "analytic_dU": dtext(analytic),
                        "raw": [
                            {
                                "h_over_L": dtext(step_ratio),
                                "centered_dU": dtext(value),
                                "absolute_residual": dtext(error),
                            }
                            for step_ratio, value, error in zip(
                                step_ratios, raw, raw_residuals, strict=True
                            )
                        ],
                        "extrapolated_dU": dtext(extrapolated),
                        "absolute_residual": dtext(residual),
                    }
                )

            # Continuous balance and power identities.
            force_sum = total_force(evaluation.forces)
            torque_origin = total_torque(
                current, evaluation.forces, (D(0), D(0), D(0))
            )
            torque_shifted = total_torque(
                current, evaluation.forces, (D("1.7"), D("-2.3"), D("0.6"))
            )
            velocity_values = normalized_random_directions(len(force), 1)[0]
            velocity = unflatten(velocity_values, model.packet_ids)
            energy_rate, force_power = power_control(model, current, velocity)
            if (
                max_abs(force_sum) > absolute_tolerance
                or max_abs(torque_origin) > absolute_tolerance
                or max_abs(torque_shifted) > absolute_tolerance
                or abs(energy_rate + force_power) > absolute_tolerance
            ):
                raise AssertionError("continuous conservation identity failed")

            # Objective/covariant finite transforms and s^2/s dimension laws.
            rotation_matrix = (
                (D("0.6"), D("-0.8"), D(0)),
                (D("0.8"), D("0.6"), D(0)),
                (D(0), D(0), D(1)),
            )
            translation = (D("0.7"), D("-0.4"), D("0.9"))
            rotated_reference = transform_points(model.reference, rotation_matrix, translation)
            rotated_current = transform_points(current, rotation_matrix, translation)
            rotated = RelationModel(
                model.packet_ids,
                rotated_reference,
                model.relations,
                model.reference_lengths,
                model.h,
            )
            rotated_evaluation = evaluate(rotated, rotated_current)
            expected_rotated_force = transform_vectors(evaluation.forces, rotation_matrix)
            rotation_force_error = max_abs(
                rotated_evaluation.forces[packet_id][axis]
                - expected_rotated_force[packet_id][axis]
                for packet_id in model.packet_ids
                for axis in range(3)
            )
            if (
                abs(rotated_evaluation.energy - evaluation.energy) > absolute_tolerance
                or rotation_force_error > absolute_tolerance
            ):
                raise AssertionError("objective force covariance failed")
            scale_rows = []
            for scale in (D("0.5"), D(2), D(7)):
                scaled_reference = {
                    packet_id: vscale(scale, point)
                    for packet_id, point in model.reference.items()
                }
                scaled_current = {
                    packet_id: vscale(scale, point)
                    for packet_id, point in current.items()
                }
                # Recompute transformed reference lengths independently.  At
                # finite Decimal precision sqrt(s^2 r^2) and s*sqrt(r^2) can
                # differ in the last retained digit; this is arithmetic, not
                # permission to rebuild H from current geometry.
                scaled = make_model(
                    scaled_reference,
                    model.relations,
                    model.h,
                )
                scaled_evaluation = evaluate(scaled, scaled_current)
                energy_residual = abs(
                    scaled_evaluation.energy - scale * scale * evaluation.energy
                )
                force_residual = max_abs(
                    scaled_evaluation.forces[packet_id][axis]
                    - scale * evaluation.forces[packet_id][axis]
                    for packet_id in model.packet_ids
                    for axis in range(3)
                )
                if max(energy_residual, force_residual) > absolute_tolerance:
                    raise AssertionError("finite dimension law failed")
                scale_rows.append(
                    {
                        "scale": dtext(scale),
                        "energy_ratio": dtext(scaled_evaluation.energy / evaluation.energy),
                        "force_scale_residual": dtext(force_residual),
                    }
                )

            # Relation order/orientation and packet-ID labels are not physics.
            relation_order = list(reversed(range(len(model.relations))))
            permuted = permuted_model(model, relation_order, True)
            permuted_eval = evaluate(permuted, current)
            relation_force_error = max_abs(
                permuted_eval.forces[packet_id][axis] - evaluation.forces[packet_id][axis]
                for packet_id in model.packet_ids
                for axis in range(3)
            )
            mapping = {11: 109, 23: 71, 37: 211, 53: 17}
            renamed = renamed_model(model, mapping)
            renamed_current = {mapping[packet_id]: point for packet_id, point in current.items()}
            renamed_eval = evaluate(renamed, renamed_current)
            rename_force_error = max_abs(
                renamed_eval.forces[mapping[packet_id]][axis]
                - evaluation.forces[packet_id][axis]
                for packet_id in model.packet_ids
                for axis in range(3)
            )
            if (
                abs(permuted_eval.energy - evaluation.energy) > absolute_tolerance
                or abs(renamed_eval.energy - evaluation.energy) > absolute_tolerance
                or max(relation_force_error, rename_force_error) > absolute_tolerance
            ):
                raise AssertionError("metamorphic label/order gate failed")

            # Full finite Hessian: material plus geometric; force Jacobian is
            # its negative and must be symmetric because U is scalar.
            material, geometric, energy_hessian = tangent_decomposition(model, current)
            raw_force_jacobians, force_jacobian = extrapolated_force_jacobian(
                model, current, derivative_steps
            )
            tangent_error = max_abs(
                force_jacobian[row][column] + energy_hessian[row][column]
                for row in range(len(force))
                for column in range(len(force))
            )
            force_jacobian_symmetry = max_abs(
                force_jacobian[row][column] - force_jacobian[column][row]
                for row in range(len(force))
                for column in range(len(force))
            )
            decomposition_error = max_abs(
                energy_hessian[row][column]
                - material[row][column]
                - geometric[row][column]
                for row in range(len(force))
                for column in range(len(force))
            )
            tangent_scale = max(D("1e-90"), frobenius(energy_hessian))
            tangent_allowed = max(
                tangent_absolute_tolerance,
                tangent_relative_tolerance * tangent_scale,
            )
            raw_tangent_errors = [
                max_abs(
                    matrix[row][column] + energy_hessian[row][column]
                    for row in range(len(force))
                    for column in range(len(force))
                )
                for matrix in raw_force_jacobians
            ]
            if not registered_raw_convergence(
                raw_tangent_errors, tangent_allowed
            ):
                raise AssertionError("raw finite-tangent convergence failed")
            if max(tangent_error, force_jacobian_symmetry, decomposition_error) > tangent_allowed:
                raise AssertionError("finite conservative tangent failed")

            # Reference tangent limit and explicit zero force at e=0.
            reference_eval = evaluate(model, model.reference)
            if reference_eval.energy != 0 or max_abs(force_vector(model, model.reference)) != 0:
                raise AssertionError("reference state is not zero energy/force")
            reference_r = rigidity(model, model.reference)
            reference_k = matmul(transpose(reference_r), matmul(model.h, reference_r))
            # The standalone exact control uses six deterministic directions;
            # bundle validation applies the registered semantic affine labels.
            reference_directions = normalized_random_directions(len(force), 6)
            epsilon_ratios = tuple(D(2) ** -power for power in (6, 9, 12, 15, 18, 21))
            reference_limit_rows = []
            for direction_index, displacement in enumerate(reference_directions):
                expected_linear = [-value for value in matvec(reference_k, displacement)]
                epsilon_rows = []
                errors: list[D] = []
                for epsilon_ratio in epsilon_ratios:
                    epsilon = characteristic_length * epsilon_ratio
                    perturbed = shifted(model.reference, model.packet_ids, displacement, epsilon)
                    quotient = [value / epsilon for value in force_vector(model, perturbed)]
                    error = max_abs(
                        actual - expected
                        for actual, expected in zip(quotient, expected_linear, strict=True)
                    ) / max(
                        D("1e-90"),
                        max_abs(expected_linear),
                        max_abs(value for matrix_row in model.h for value in matrix_row),
                    )
                    errors.append(error)
                    epsilon_rows.append(
                        {
                            "epsilon_over_L": dtext(epsilon_ratio),
                            "scale_normalized_infinity_error": dtext(error),
                        }
                    )
                decreases = [errors[i + 1] < errors[i] for i in range(5)]
                if max(
                    sum(1 for value in decreases[start : start + 3] if value)
                    for start in range(3)
                ) != 3:
                    raise AssertionError("reference tangent lacks three consecutive decreases")
                orders = [
                    (errors[i] / errors[i + 1]).ln() / D(8).ln()
                    for i in range(5)
                    if errors[i + 1] != 0 and errors[i] != 0
                ]
                sorted_orders = sorted(orders)
                median_order = sorted_orders[len(sorted_orders) // 2]
                if not D("0.75") <= median_order <= D("1.25") or min(errors) > D("2e-5"):
                    raise AssertionError("reference tangent registered convergence gate failed")
                reference_limit_rows.append(
                    {
                        "direction_index": direction_index,
                        "rows": epsilon_rows,
                        "median_observed_order": dtext(median_order),
                        "minimum_relative_error": dtext(min(errors)),
                    }
                )

            ratio_results.append(
                {
                    "K_over_G": dtext(ratio),
                    "energy_j": dtext(evaluation.energy),
                    "directional_derivatives": derivative_rows,
                    "maximum_total_force_n": dtext(max_abs(force_sum)),
                    "maximum_total_torque_origin_nm": dtext(max_abs(torque_origin)),
                    "maximum_total_torque_shifted_nm": dtext(max_abs(torque_shifted)),
                    "power_residual_w": dtext(abs(energy_rate + force_power)),
                    "objective_energy_residual_j": dtext(
                        abs(rotated_evaluation.energy - evaluation.energy)
                    ),
                    "objective_force_residual_n": dtext(rotation_force_error),
                    "scale_controls": scale_rows,
                    "relation_permutation_endpoint_reversal_force_residual_n": dtext(
                        relation_force_error
                    ),
                    "packet_id_bijection_force_residual_n": dtext(rename_force_error),
                    "material_hessian_norm_n_per_m": dtext(frobenius(material)),
                    "geometric_hessian_norm_n_per_m": dtext(frobenius(geometric)),
                    "finite_hessian_decomposition_residual_n_per_m": dtext(
                        decomposition_error
                    ),
                    "force_jacobian_gradient_residual_n_per_m": dtext(tangent_error),
                    "force_jacobian_symmetry_residual_n_per_m": dtext(
                        force_jacobian_symmetry
                    ),
                    "raw_force_jacobian_residuals_n_per_m": [
                        dtext(value) for value in raw_tangent_errors
                    ],
                    "reference_tangent_limit": reference_limit_rows,
                }
            )

        # A deliberately isolated positive-length approach to the nonsmooth
        # boundary.  It demonstrates finite force but a geometric tangent that
        # grows like 1/r.  Exact coincidence must raise, never choose a direction.
        collapse_reference = {1: (D(0), D(0), D(0)), 2: (D(1), D(0), D(0))}
        collapse_model = make_model(collapse_reference, ((1, 2),), ((D(2),),))
        collapse_rows = []
        for exponent in (0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48):
            ratio = D(2) ** -exponent
            current = {1: (D(0), D(0), D(0)), 2: (ratio, D(0), D(0))}
            evaluation = evaluate(collapse_model, current)
            material, geometric, total = tangent_decomposition(collapse_model, current)
            force_norm = norm(force_vector(collapse_model, current))
            collapse_rows.append(
                {
                    "length_ratio": dtext(ratio),
                    "force_norm_n": dtext(force_norm),
                    "material_tangent_norm_n_per_m": dtext(frobenius(material)),
                    "geometric_tangent_norm_n_per_m": dtext(frobenius(geometric)),
                    "total_tangent_norm_n_per_m": dtext(frobenius(total)),
                    "domain_status": "valid_noncoincident",
                    "registered_domain_row": exponent <= 32,
                }
            )
        exact_coincidence_failed_closed = False
        try:
            evaluate(
                collapse_model,
                {1: (D(0), D(0), D(0)), 2: (D(0), D(0), D(0))},
            )
        except CoincidentRelationError:
            exact_coincidence_failed_closed = True
        if not exact_coincidence_failed_closed:
            raise AssertionError("exact coincidence did not fail closed")

        return {
            "schema": SCHEMA,
            "seed": SEED,
            "decimal_digits": DIGITS,
            "implementation": IMPLEMENTATION,
            "scope": "read-only finite energy/force consistency; no dynamics",
            "domain_contract": "every current relation length must satisfy |x_j-x_i|>0",
            "frozen_energy": "U=1/2 e^T H e; H/reference lengths/topology fixed from reference data",
            "analytic_force": "g=H e; f_i+=g_a n_a; f_j-=g_a n_a=-gradient(U)",
            "finite_tangent": (
                "energy Hessian=R^T H R + sum_a g_a/r_a B_a^T(I-n_a n_a^T)B_a; "
                "force Jacobian is its negative"
            ),
            "registered_tolerances": {
                "exact_identity_absolute": dtext(absolute_tolerance),
                "directional_derivative_relative": dtext(derivative_relative_tolerance),
                "directional_derivative_absolute": dtext(derivative_absolute_tolerance),
                "finite_tangent_relative": dtext(tangent_relative_tolerance),
                "finite_tangent_absolute": dtext(tangent_absolute_tolerance),
            },
            "collective_policy_controls": ratio_results,
            "coincident_relation_approach": {
                "rows": collapse_rows,
                "exact_coincidence_failed_closed": exact_coincidence_failed_closed,
                "epsilon_normalization_or_hidden_repulsion_used": False,
            },
            "all_registered_noncoincident_controls_passed": True,
            "force_installed_in_authoritative_world": False,
            "time_integration_present": False,
            "numerical_residual_converted_to_physical_energy": False,
            "candidate_promotion_permitted": False,
            "result_boundary": "NO PROMOTION to dynamics",
        }


def render_without_hash(value: Mapping[str, object]) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def run() -> dict:
    result = oracle_controls()
    result["result_sha256_before_hash_field"] = hashlib.sha256(
        render_without_hash(result).encode("utf-8")
    ).hexdigest()
    return result


def verify(path: Path, actual: dict) -> None:
    try:
        expected = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit(f"CONSERVATIVE FORCE ORACLE INVALID: {error}") from error
    if not isinstance(expected, dict):
        raise SystemExit("CONSERVATIVE FORCE ORACLE INVALID: canonical root is not an object")
    payload = dict(expected)
    claimed = payload.pop("result_sha256_before_hash_field", None)
    computed = hashlib.sha256(render_without_hash(payload).encode("utf-8")).hexdigest()
    if claimed != computed:
        raise SystemExit("CONSERVATIVE FORCE ORACLE INVALID: canonical pre-hash mismatch")
    if expected != actual:
        raise SystemExit("CONSERVATIVE FORCE ORACLE MISMATCH: canonical result differs")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        result = run()
        if args.verify is not None:
            verify(args.verify, result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ArithmeticError, AssertionError, ValueError) as error:
        print(f"CONSERVATIVE FORCE ORACLE INVALID: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
