#!/usr/bin/env python3
"""Independent exact oracle for the MLS mechanical-observability lab.

This file deliberately shares no implementation with the C++ diagnostics.  It
uses only :class:`fractions.Fraction`, explicit matrix assembly, and an exact
RREF implementation.  Its scope is deliberately small: registered rational
frameworks, objective relational rows, and corrected local-gradient controls.
It is an algebraic cross-check, not evidence for a floating-point mechanics
solver and not a constitutive model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction as Q
from pathlib import Path
from typing import Iterable, Sequence


SEED = 260828
SCHEMA = "mls.mechanical-observability.exact-oracle.v1"
IMPLEMENTATION = "independent Python standard-library Fraction matrix/RREF oracle"

Vec3 = tuple[Q, Q, Q]
Matrix = list[list[Q]]


class SingularMatrixError(ValueError):
    """Raised when an exact inverse does not exist."""


def qsum(values: Iterable[Q]) -> Q:
    return sum(values, Q(0))


def qtext(value: Q) -> str:
    return f"{value.numerator}/{value.denominator}"


def vector_text(vector: Sequence[Q]) -> list[str]:
    return [qtext(value) for value in vector]


def matrix_text(matrix: Sequence[Sequence[Q]]) -> list[list[str]]:
    return [vector_text(row) for row in matrix]


def add(first: Vec3, second: Vec3) -> Vec3:
    return tuple(first[index] + second[index] for index in range(3))  # type: ignore[return-value]


def subtract(first: Vec3, second: Vec3) -> Vec3:
    return tuple(first[index] - second[index] for index in range(3))  # type: ignore[return-value]


def scale(factor: Q, vector: Vec3) -> Vec3:
    return tuple(factor * value for value in vector)  # type: ignore[return-value]


def dot(first: Sequence[Q], second: Sequence[Q]) -> Q:
    if len(first) != len(second):
        raise ValueError("dot-product size mismatch")
    return qsum(a * b for a, b in zip(first, second, strict=True))


def cross(first: Vec3, second: Vec3) -> Vec3:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def squared_norm(vector: Vec3) -> Q:
    return dot(vector, vector)


def transpose(matrix: Sequence[Sequence[Q]]) -> Matrix:
    if not matrix:
        return []
    width = len(matrix[0])
    if any(len(row) != width for row in matrix):
        raise ValueError("ragged matrix")
    return [list(column) for column in zip(*matrix, strict=True)]


def matmul(first: Sequence[Sequence[Q]], second: Sequence[Sequence[Q]]) -> Matrix:
    if not first or not second:
        return []
    second_t = transpose(second)
    if len(first[0]) != len(second):
        raise ValueError("matrix-product size mismatch")
    return [[dot(row, column) for column in second_t] for row in first]


def matvec(matrix: Sequence[Sequence[Q]], vector: Sequence[Q]) -> list[Q]:
    return [dot(row, vector) for row in matrix]


def rref(matrix: Sequence[Sequence[Q]]) -> tuple[Matrix, list[int]]:
    """Return an exact reduced row echelon form and its pivot columns."""
    work = [list(row) for row in matrix]
    if not work:
        return [], []
    width = len(work[0])
    if any(len(row) != width for row in work):
        raise ValueError("ragged matrix")
    pivots: list[int] = []
    pivot_row = 0
    for column in range(width):
        selected = next(
            (row for row in range(pivot_row, len(work)) if work[row][column] != 0),
            None,
        )
        if selected is None:
            continue
        work[pivot_row], work[selected] = work[selected], work[pivot_row]
        divisor = work[pivot_row][column]
        work[pivot_row] = [value / divisor for value in work[pivot_row]]
        for row in range(len(work)):
            if row == pivot_row or work[row][column] == 0:
                continue
            multiplier = work[row][column]
            work[row] = [
                work[row][entry] - multiplier * work[pivot_row][entry]
                for entry in range(width)
            ]
        pivots.append(column)
        pivot_row += 1
        if pivot_row == len(work):
            break
    return work, pivots


def matrix_rank(matrix: Sequence[Sequence[Q]], *, width_if_empty: int = 0) -> int:
    if not matrix:
        if width_if_empty < 0:
            raise ValueError("negative empty-matrix width")
        return 0
    return len(rref(matrix)[1])


def nullspace(matrix: Sequence[Sequence[Q]], width: int | None = None) -> list[list[Q]]:
    if matrix:
        inferred_width = len(matrix[0])
        if width is not None and width != inferred_width:
            raise ValueError("explicit nullspace width mismatch")
        width = inferred_width
    elif width is None:
        raise ValueError("empty matrix requires explicit nullspace width")
    reduced, pivots = rref(matrix)
    pivot_rows = {column: row for row, column in enumerate(pivots)}
    free_columns = [column for column in range(width) if column not in pivot_rows]
    basis: list[list[Q]] = []
    for free in free_columns:
        vector = [Q(0) for _ in range(width)]
        vector[free] = Q(1)
        for pivot, row in pivot_rows.items():
            vector[pivot] = -reduced[row][free]
        assert matvec(matrix, vector) == [Q(0)] * len(matrix)
        basis.append(vector)
    return basis


def columns_to_matrix(columns: Sequence[Sequence[Q]], row_count: int) -> Matrix:
    if not columns:
        return [[] for _ in range(row_count)]
    if any(len(column) != row_count for column in columns):
        raise ValueError("column height mismatch")
    return [
        [columns[column][row] for column in range(len(columns))]
        for row in range(row_count)
    ]


def inverse(matrix: Sequence[Sequence[Q]]) -> Matrix:
    size = len(matrix)
    if size == 0 or any(len(row) != size for row in matrix):
        raise SingularMatrixError("inverse requires a nonempty square matrix")
    augmented = [
        list(row) + [Q(1) if row_index == column else Q(0) for column in range(size)]
        for row_index, row in enumerate(matrix)
    ]
    reduced, pivots = rref(augmented)
    if pivots[:size] != list(range(size)):
        raise SingularMatrixError("matrix is singular")
    left = [row[:size] for row in reduced]
    identity = [[Q(1) if row == column else Q(0) for column in range(size)] for row in range(size)]
    if left != identity:
        raise SingularMatrixError("matrix has no exact inverse")
    return [row[size:] for row in reduced]


def determinant3(matrix: Sequence[Sequence[Q]]) -> Q:
    if len(matrix) != 3 or any(len(row) != 3 for row in matrix):
        raise ValueError("determinant3 requires a 3x3 matrix")
    return (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def matrix_vector3(matrix: Sequence[Sequence[Q]], vector: Vec3) -> Vec3:
    values = matvec(matrix, vector)
    if len(values) != 3:
        raise ValueError("3D transform must have three rows")
    return tuple(values)  # type: ignore[return-value]


def points(values: Sequence[Sequence[int | Q]]) -> list[Vec3]:
    return [tuple(Q(entry) for entry in point) for point in values]  # type: ignore[list-item]


def central_squared_length_rows(
    configuration: Sequence[Vec3], edges: Sequence[tuple[int, int]]
) -> Matrix:
    """Derivative rows of |x_i-x_j|^2, with no material law attached."""
    width = 3 * len(configuration)
    rows: Matrix = []
    for first, second in edges:
        if first == second or not (0 <= first < len(configuration) and 0 <= second < len(configuration)):
            raise ValueError("invalid central relation")
        displacement = subtract(configuration[first], configuration[second])
        row = [Q(0)] * width
        for axis in range(3):
            row[3 * first + axis] = 2 * displacement[axis]
            row[3 * second + axis] = -2 * displacement[axis]
        rows.append(row)
    return rows


def oriented_volume6(configuration: Sequence[Vec3], sites: tuple[int, int, int, int]) -> Q:
    origin, first, second, third = (configuration[index] for index in sites)
    a = subtract(first, origin)
    b = subtract(second, origin)
    c = subtract(third, origin)
    return dot(a, cross(b, c))


def oriented_volume6_derivative_row(
    configuration: Sequence[Vec3], sites: tuple[int, int, int, int]
) -> list[Q]:
    """Derivative of det(x1-x0,x2-x0,x3-x0), an objective signed relation."""
    origin_index, first_index, second_index, third_index = sites
    origin, first, second, third = (configuration[index] for index in sites)
    a = subtract(first, origin)
    b = subtract(second, origin)
    c = subtract(third, origin)
    gradients = {
        first_index: cross(b, c),
        second_index: cross(c, a),
        third_index: cross(a, b),
    }
    gradients[origin_index] = scale(
        Q(-1), add(add(gradients[first_index], gradients[second_index]), gradients[third_index])
    )
    row = [Q(0)] * (3 * len(configuration))
    for site, gradient in gradients.items():
        for axis in range(3):
            row[3 * site + axis] = gradient[axis]
    return row


def rigid_generators(configuration: Sequence[Vec3]) -> list[list[Q]]:
    """Three translations followed by rotations omega cross x about each axis."""
    generators: list[list[Q]] = []
    axes = ((Q(1), Q(0), Q(0)), (Q(0), Q(1), Q(0)), (Q(0), Q(0), Q(1)))
    for axis in axes:
        generators.append([axis[component] for _point in configuration for component in range(3)])
    for omega in axes:
        generators.append([component for point in configuration for component in cross(omega, point)])
    return generators


def relation_rows(
    configuration: Sequence[Vec3],
    edges: Sequence[tuple[int, int]],
    volumes: Sequence[tuple[int, int, int, int]],
) -> Matrix:
    return central_squared_length_rows(configuration, edges) + [
        oriented_volume6_derivative_row(configuration, sites) for sites in volumes
    ]


def rigidity_case(
    name: str,
    configuration: Sequence[Vec3],
    edges: Sequence[tuple[int, int]],
    expected_rank: int,
    expected_nullity: int,
    volumes: Sequence[tuple[int, int, int, int]] = (),
) -> dict:
    rows = relation_rows(configuration, edges, volumes)
    width = 3 * len(configuration)
    rank = matrix_rank(rows, width_if_empty=width)
    kernel = nullspace(rows, width)
    rigid = rigid_generators(configuration)
    rigid_rank = matrix_rank(columns_to_matrix(rigid, width))
    rigid_residuals = [matvec(rows, generator) for generator in rigid]
    rigid_in_kernel = all(all(value == 0 for value in residual) for residual in rigid_residuals)
    kernel_rank = matrix_rank(columns_to_matrix(kernel, width))
    combined_rank = matrix_rank(columns_to_matrix([*rigid, *kernel], width))
    nonrigid_dimension = combined_rank - rigid_rank
    kernel_equals_rigid = (
        rigid_in_kernel
        and rank == expected_rank
        and len(kernel) == expected_nullity
        and kernel_rank == len(kernel)
        and rigid_rank == len(kernel)
        and combined_rank == rigid_rank
    )
    if rank != expected_rank or len(kernel) != expected_nullity:
        raise AssertionError(
            f"{name}: rank/nullity {(rank, len(kernel))} != {(expected_rank, expected_nullity)}"
        )
    if not rigid_in_kernel or rigid_rank != 6 or kernel_rank != len(kernel):
        raise AssertionError(f"{name}: rigid/kernel exactness failure")
    if nonrigid_dimension != expected_nullity - 6:
        raise AssertionError(f"{name}: non-rigid nullspace partition failure")
    return {
        "name": name,
        "point_count": len(configuration),
        "points": [vector_text(point) for point in configuration],
        "edge_count": len(edges),
        "edges": [list(edge) for edge in edges],
        "objective_volume_relations": [list(sites) for sites in volumes],
        "relation_row_count": len(rows),
        "degrees_of_freedom": width,
        "rank": rank,
        "nullity": len(kernel),
        "kernel_basis_rank": kernel_rank,
        "rigid_generator_rank": rigid_rank,
        "rigid_generators_in_kernel": rigid_in_kernel,
        "combined_kernel_rigid_span_rank": combined_rank,
        "nonrigid_nullity": nonrigid_dimension,
        "kernel_equals_rigid_span": kernel_equals_rigid,
    }


def affine_value(matrix: Sequence[Sequence[Q]], intercept: Vec3, point: Vec3) -> Vec3:
    return add(matrix_vector3(matrix, point), intercept)


def corrected_wls(
    center: Vec3,
    neighbors: Sequence[Vec3],
    center_velocity: Vec3,
    neighbor_velocities: Sequence[Vec3],
    support_radius: Q,
) -> tuple[Matrix, Matrix, Matrix]:
    """Compute G=(sum w dv tensor r) M^-1 with w=(1-r^2/H^2)^2."""
    if len(neighbors) != len(neighbor_velocities):
        raise ValueError("neighbor/velocity count mismatch")
    if support_radius <= 0:
        raise ValueError("support radius must be positive")
    moment = [[Q(0) for _ in range(3)] for _ in range(3)]
    numerator = [[Q(0) for _ in range(3)] for _ in range(3)]
    for neighbor, velocity in zip(neighbors, neighbor_velocities, strict=True):
        offset = subtract(neighbor, center)
        radius_squared = squared_norm(offset)
        if radius_squared >= support_radius * support_radius:
            raise ValueError("registered WLS neighbor lies outside open support")
        weight = (Q(1) - radius_squared / (support_radius * support_radius)) ** 2
        velocity_delta = subtract(velocity, center_velocity)
        for row in range(3):
            for column in range(3):
                moment[row][column] += weight * offset[row] * offset[column]
                numerator[row][column] += weight * velocity_delta[row] * offset[column]
    return moment, numerator, matmul(numerator, inverse(moment))


def corrected_wls_controls() -> dict:
    center: Vec3 = (Q(1, 5), Q(-2, 7), Q(3, 8))
    offsets: list[Vec3] = [
        (Q(1), Q(0), Q(0)),
        (Q(0), Q(1), Q(0)),
        (Q(0), Q(0), Q(1)),
        (Q(-1), Q(-1, 2), Q(0)),
        (Q(0), Q(-1), Q(-1, 2)),
        (Q(-1, 2), Q(0), Q(-1)),
    ]
    neighbors = [add(center, offset) for offset in offsets]
    support_radius = Q(2)
    fields: dict[str, tuple[Matrix, Vec3]] = {
        "uniform_translation": (
            [[Q(0), Q(0), Q(0)] for _ in range(3)],
            (Q(2, 3), Q(-3, 5), Q(5, 7)),
        ),
        "infinitesimal_rigid_rotation": (
            [[Q(0), Q(-2), Q(3)], [Q(2), Q(0), Q(-1)], [Q(-3), Q(1), Q(0)]],
            (Q(1, 9), Q(-1, 11), Q(1, 13)),
        ),
        "isotropic_expansion": (
            [[Q(3, 7), Q(0), Q(0)], [Q(0), Q(3, 7), Q(0)], [Q(0), Q(0), Q(3, 7)]],
            (Q(-1, 3), Q(1, 4), Q(2, 9)),
        ),
        "pure_shear": (
            [[Q(0), Q(1, 3), Q(0)], [Q(1, 3), Q(0), Q(0)], [Q(0), Q(0), Q(0)]],
            (Q(2, 5), Q(1, 6), Q(-1, 8)),
        ),
        "general_affine": (
            [
                [Q(1, 5), Q(-2, 7), Q(3, 11)],
                [Q(4, 9), Q(-1, 6), Q(2, 13)],
                [Q(-3, 8), Q(5, 12), Q(7, 10)],
            ],
            (Q(5, 17), Q(-4, 19), Q(3, 23)),
        ),
    }
    recovered: dict[str, dict] = {}
    reference_moment: Matrix | None = None
    for name, (gradient, intercept) in fields.items():
        center_velocity = affine_value(gradient, intercept, center)
        neighbor_velocities = [affine_value(gradient, intercept, point) for point in neighbors]
        moment, numerator, estimate = corrected_wls(
            center, neighbors, center_velocity, neighbor_velocities, support_radius
        )
        if estimate != gradient:
            raise AssertionError(f"corrected WLS failed exact {name} reproduction")
        if reference_moment is None:
            reference_moment = moment
        elif moment != reference_moment:
            raise AssertionError("WLS moment changed with velocity field")
        recovered[name] = {
            "claimed_gradient": matrix_text(gradient),
            "recovered_gradient": matrix_text(estimate),
            "exact": True,
            "numerator": matrix_text(numerator),
        }
    assert reference_moment is not None
    moment_rank = matrix_rank(reference_moment)
    if moment_rank != 3:
        raise AssertionError("registered WLS moment is not full rank")

    translation: Vec3 = (Q(7, 13), Q(-5, 11), Q(2, 9))
    scale_factor = Q(5, 3)
    general_matrix, general_intercept = fields["general_affine"]
    translated_center = add(center, translation)
    translated_neighbors = [add(point, translation) for point in neighbors]
    translated_center_velocity = affine_value(general_matrix, general_intercept, translated_center)
    translated_neighbor_velocities = [
        affine_value(general_matrix, general_intercept, point) for point in translated_neighbors
    ]
    translated_moment, _numerator, translated_estimate = corrected_wls(
        translated_center,
        translated_neighbors,
        translated_center_velocity,
        translated_neighbor_velocities,
        support_radius,
    )
    if translated_moment != reference_moment or translated_estimate != general_matrix:
        raise AssertionError("corrected WLS translation relation failed")

    scaled_center = scale(scale_factor, center)
    scaled_neighbors = [scale(scale_factor, point) for point in neighbors]
    scaled_center_velocity = affine_value(general_matrix, general_intercept, scaled_center)
    scaled_neighbor_velocities = [
        affine_value(general_matrix, general_intercept, point) for point in scaled_neighbors
    ]
    scaled_moment, _numerator, scaled_estimate = corrected_wls(
        scaled_center,
        scaled_neighbors,
        scaled_center_velocity,
        scaled_neighbor_velocities,
        scale_factor * support_radius,
    )
    expected_scaled_moment = [
        [scale_factor * scale_factor * value for value in row] for row in reference_moment
    ]
    if scaled_moment != expected_scaled_moment or scaled_estimate != general_matrix:
        raise AssertionError("corrected WLS scale relation failed")

    singular_offsets: list[Vec3] = [
        (Q(-1), Q(0), Q(0)),
        (Q(1, 2), Q(0), Q(0)),
        (Q(3, 2), Q(0), Q(0)),
    ]
    singular_neighbors = [add(center, offset) for offset in singular_offsets]
    singular_velocities = [
        affine_value(general_matrix, general_intercept, point) for point in singular_neighbors
    ]
    singular_center_velocity = affine_value(general_matrix, general_intercept, center)
    singular_moment = [[Q(0) for _ in range(3)] for _ in range(3)]
    for neighbor in singular_neighbors:
        offset = subtract(neighbor, center)
        weight = (Q(1) - squared_norm(offset) / (support_radius * support_radius)) ** 2
        for row in range(3):
            for column in range(3):
                singular_moment[row][column] += weight * offset[row] * offset[column]
    rejected = False
    try:
        corrected_wls(
            center,
            singular_neighbors,
            singular_center_velocity,
            singular_velocities,
            support_radius,
        )
    except SingularMatrixError:
        rejected = True
    if matrix_rank(singular_moment) != 1 or not rejected:
        raise AssertionError("singular corrected-WLS control was not preserved")

    return {
        "equation": "G=(sum_q w_pq (v_q-v_p) tensor r_pq) M^-1",
        "moment_equation": "M=sum_q w_pq r_pq tensor r_pq",
        "weight_equation": "w=(1-r_squared/H_squared)^2",
        "center": vector_text(center),
        "neighbor_offsets": [vector_text(offset) for offset in offsets],
        "support_radius": qtext(support_radius),
        "moment": matrix_text(reference_moment),
        "moment_rank": moment_rank,
        "moment_determinant": qtext(determinant3(reference_moment)),
        "affine_field_controls": recovered,
        "affine_reproduction_count": len(recovered),
        "translation_relation_exact": True,
        "scale_factor": qtext(scale_factor),
        "moment_scale_power_two_exact": True,
        "scaled_gradient_unchanged": True,
        "singular_control": {
            "neighbor_offsets": [vector_text(offset) for offset in singular_offsets],
            "moment": matrix_text(singular_moment),
            "moment_rank": matrix_rank(singular_moment),
            "inverse_rejected": rejected,
            "regularization_used": False,
        },
    }


def transformed_points(
    configuration: Sequence[Vec3], rotation: Sequence[Sequence[Q]], translation: Vec3
) -> list[Vec3]:
    return [add(matrix_vector3(rotation, point), translation) for point in configuration]


def pullback_row(row: Sequence[Q], rotation: Sequence[Sequence[Q]]) -> list[Q]:
    rotation_t = transpose(rotation)
    result: list[Q] = []
    for site in range(len(row) // 3):
        block: Vec3 = tuple(row[3 * site : 3 * site + 3])  # type: ignore[assignment]
        result.extend(matrix_vector3(rotation_t, block))
    return result


def objectivity_controls(cases: Sequence[dict], case_inputs: dict[str, tuple]) -> dict:
    rotation: Matrix = [
        [Q(1, 9), Q(8, 9), Q(4, 9)],
        [Q(8, 9), Q(1, 9), Q(-4, 9)],
        [Q(-4, 9), Q(4, 9), Q(-7, 9)],
    ]
    identity = [[Q(1) if row == column else Q(0) for column in range(3)] for row in range(3)]
    if matmul(transpose(rotation), rotation) != identity or determinant3(rotation) != 1:
        raise AssertionError("registered rational transform is not a proper rotation")
    translation: Vec3 = (Q(7, 5), Q(-11, 7), Q(13, 9))
    scale_factor = Q(5, 3)
    length_checks = 0
    volume_checks = 0
    translation_row_checks = 0
    rotation_pullback_checks = 0
    scale_row_checks = 0
    registered_names = {case["name"] for case in cases}
    if registered_names != set(case_inputs):
        raise AssertionError("objectivity inputs do not match registered cases")
    for name, (configuration, edges, volumes) in case_inputs.items():
        transformed = transformed_points(configuration, rotation, translation)
        translated = [add(point, translation) for point in configuration]
        scaled = [scale(scale_factor, point) for point in configuration]
        original_rows = relation_rows(configuration, edges, volumes)
        transformed_rows = relation_rows(transformed, edges, volumes)
        translated_rows = relation_rows(translated, edges, volumes)
        scaled_rows = relation_rows(scaled, edges, volumes)
        if translated_rows != original_rows:
            raise AssertionError(f"{name}: derivative rows changed under translation")
        translation_row_checks += len(original_rows)
        for original, transformed_row in zip(original_rows, transformed_rows, strict=True):
            if pullback_row(transformed_row, rotation) != original:
                raise AssertionError(f"{name}: derivative-row rotational objectivity failed")
            rotation_pullback_checks += 1
        for index, original in enumerate(original_rows):
            exponent = 1 if index < len(edges) else 2
            expected = [scale_factor**exponent * value for value in original]
            if scaled_rows[index] != expected:
                raise AssertionError(f"{name}: derivative-row scale relation failed")
            scale_row_checks += 1
        for first, second in edges:
            original_squared = squared_norm(subtract(configuration[first], configuration[second]))
            transformed_squared = squared_norm(subtract(transformed[first], transformed[second]))
            scaled_squared = squared_norm(subtract(scaled[first], scaled[second]))
            if transformed_squared != original_squared or scaled_squared != scale_factor**2 * original_squared:
                raise AssertionError(f"{name}: finite bond objectivity/scale failure")
            length_checks += 1
        for sites in volumes:
            original_volume = oriented_volume6(configuration, sites)
            transformed_volume = oriented_volume6(transformed, sites)
            scaled_volume = oriented_volume6(scaled, sites)
            if transformed_volume != original_volume or scaled_volume != scale_factor**3 * original_volume:
                raise AssertionError(f"{name}: finite volume objectivity/scale failure")
            volume_checks += 1

    tetrahedron = case_inputs["tetrahedron_k4"][0]
    tetra_sites = (0, 1, 2, 3)
    tetra_transformed = transformed_points(tetrahedron, rotation, translation)
    tetra_scaled = [scale(scale_factor, point) for point in tetrahedron]
    tetra_volume = oriented_volume6(tetrahedron, tetra_sites)
    if tetra_volume == 0:
        raise AssertionError("finite volume control must be nonzero")
    if oriented_volume6(tetra_transformed, tetra_sites) != tetra_volume:
        raise AssertionError("nonzero finite volume changed under proper rigid motion")
    if oriented_volume6(tetra_scaled, tetra_sites) != scale_factor**3 * tetra_volume:
        raise AssertionError("nonzero finite volume scale relation failed")
    volume_checks += 1
    return {
        "proper_rotation": matrix_text(rotation),
        "proper_rotation_orthogonal": True,
        "proper_rotation_determinant": qtext(determinant3(rotation)),
        "translation": vector_text(translation),
        "scale_factor": qtext(scale_factor),
        "finite_squared_length_objectivity_and_scale_checks": length_checks,
        "finite_oriented_volume_objectivity_and_scale_checks": volume_checks,
        "derivative_translation_invariance_checks": translation_row_checks,
        "derivative_rotation_pullback_checks": rotation_pullback_checks,
        "derivative_scale_covariance_checks": scale_row_checks,
        "all_exact": True,
    }


def result_without_hash() -> dict:
    tetrahedron = points(((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)))
    tetrahedron_edges = [(first, second) for first in range(4) for second in range(first + 1, 4)]
    tetrahedron_minus_edge = tetrahedron_edges[:-1]

    octahedron = points(((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))
    octahedron_edges = [
        (first, second)
        for first in range(6)
        for second in range(first + 1, 6)
        if octahedron[first] != scale(Q(-1), octahedron[second])
    ]

    cube = points(tuple((x, y, z) for z in (0, 1) for y in (0, 1) for x in (0, 1)))
    cube_edges = [
        (first, second)
        for first in range(8)
        for second in range(first + 1, 8)
        if qsum(abs(cube[first][axis] - cube[second][axis]) for axis in range(3)) == 1
    ]

    square = points(((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)))
    square_edges = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2)]
    square_volume = [(0, 1, 2, 3)]

    registrations = [
        ("tetrahedron_k4", tetrahedron, tetrahedron_edges, (), 6, 6),
        ("tetrahedron_k4_minus_edge", tetrahedron, tetrahedron_minus_edge, (), 5, 7),
        ("octahedron_graph", octahedron, octahedron_edges, (), 12, 6),
        ("cube_edge_graph", cube, cube_edges, (), 12, 12),
        ("planar_square_plus_diagonal", square, square_edges, (), 5, 7),
        (
            "planar_square_plus_diagonal_and_volume",
            square,
            square_edges,
            square_volume,
            6,
            6,
        ),
    ]
    cases = [
        rigidity_case(name, configuration, edges, rank, nullity, volumes)
        for name, configuration, edges, volumes, rank, nullity in registrations
    ]
    case_inputs = {
        name: (configuration, edges, volumes)
        for name, configuration, edges, volumes, _rank, _nullity in registrations
    }
    square_plain = next(case for case in cases if case["name"] == "planar_square_plus_diagonal")
    square_enriched = next(
        case for case in cases if case["name"] == "planar_square_plus_diagonal_and_volume"
    )
    if square_plain["nonrigid_nullity"] != 1 or not square_enriched["kernel_equals_rigid_span"]:
        raise AssertionError("registered triple-volume enrichment identity is false")
    expected = {
        "tetrahedron_k4": (6, 6, 0),
        "tetrahedron_k4_minus_edge": (5, 7, 1),
        "octahedron_graph": (12, 6, 0),
        "cube_edge_graph": (12, 12, 6),
        "planar_square_plus_diagonal": (5, 7, 1),
        "planar_square_plus_diagonal_and_volume": (6, 6, 0),
    }
    for case in cases:
        actual = (case["rank"], case["nullity"], case["nonrigid_nullity"])
        if actual != expected[case["name"]]:
            raise AssertionError(f"unexpected registered exact claim for {case['name']}")
    return {
        "schema": SCHEMA,
        "seed": SEED,
        "implementation": IMPLEMENTATION,
        "scope": "small exact algebra controls; independent of C++ and promotion-ineligible",
        "arithmetic": "fractions.Fraction only",
        "central_relation": "derivative of squared packet distance; no force or constitutive law",
        "rigid_motion_definition": "three translations plus omega cross x for three rotation axes",
        "rigidity_cases": cases,
        "registered_rank_claims": {
            name: {"rank": values[0], "nullity": values[1], "nonrigid_nullity": values[2]}
            for name, values in expected.items()
        },
        "triple_volume_enrichment": {
            "relation": "det(x1-x0,x2-x0,x3-x0)",
            "planar_derivative_row": vector_text(
                oriented_volume6_derivative_row(square, square_volume[0])
            ),
            "rank_before": square_plain["rank"],
            "rank_after": square_enriched["rank"],
            "nullity_before": square_plain["nullity"],
            "nullity_after": square_enriched["nullity"],
            "expected_identity_confirmed": True,
        },
        "objectivity_controls": objectivity_controls(cases, case_inputs),
        "corrected_wls_controls": corrected_wls_controls(),
        "regularization_used": False,
        "constitutive_law_present": False,
        "promotion_eligible": False,
    }


def render_result(result: dict) -> str:
    return json.dumps(result, indent=2, sort_keys=True)


def run() -> dict:
    result = result_without_hash()
    payload = render_result(result)
    result["result_sha256_before_hash_field"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return result


def verify(path: Path, actual: dict) -> None:
    try:
        expected = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"MECHANICAL OBSERVABILITY ORACLE INVALID: {error}") from error
    if not isinstance(expected, dict):
        raise SystemExit("MECHANICAL OBSERVABILITY ORACLE INVALID: canonical root is not an object")
    expected_payload = dict(expected)
    claimed_hash = expected_payload.pop("result_sha256_before_hash_field", None)
    computed_hash = hashlib.sha256(render_result(expected_payload).encode("utf-8")).hexdigest()
    if claimed_hash != computed_hash:
        raise SystemExit("MECHANICAL OBSERVABILITY ORACLE INVALID: canonical pre-hash mismatch")
    if expected != actual:
        raise SystemExit("MECHANICAL OBSERVABILITY ORACLE MISMATCH: canonical result differs")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    result = run()
    if args.verify is not None:
        verify(args.verify, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
