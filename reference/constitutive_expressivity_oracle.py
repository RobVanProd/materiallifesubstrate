#!/usr/bin/env python3
"""Independent exact oracle for the Constitutive Expressivity Lab.

This program intentionally shares no implementation with the C++ energy
evaluator.  It reconstructs the preregistered seven-direction cubature,
derives pair and collective Kelvin tangents from extension energies, checks
finite-length objectivity with rational arithmetic, and performs selected
exact graph/kernel checks over Q(sqrt(2)).  It is an energy-only oracle: no
force, stress, or time integration appears here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction as Q
from math import isqrt
from pathlib import Path
from typing import Callable, Iterable, Sequence


SCHEMA = "mls.constitutive-expressivity.exact-oracle.v1"
SEED = 260828
IMPLEMENTATION = (
    "independent Python standard-library Fraction and Q(sqrt(2)) algebra; "
    "no C++ result is accepted as a premise"
)


def qtext(value: Q) -> str:
    return f"{value.numerator}/{value.denominator}"


def qsum(values: Iterable[Q]) -> Q:
    return sum(values, Q(0))


@dataclass(frozen=True)
class QSqrt2:
    """Exact a+b*sqrt(2), sufficient for the selected graph controls."""

    rational: Q = Q(0)
    sqrt2: Q = Q(0)

    @staticmethod
    def coerce(value: QSqrt2 | Q | int) -> QSqrt2:
        if isinstance(value, QSqrt2):
            return value
        return QSqrt2(Q(value), Q(0))

    def __add__(self, other: QSqrt2 | Q | int) -> QSqrt2:
        rhs = self.coerce(other)
        return QSqrt2(self.rational + rhs.rational, self.sqrt2 + rhs.sqrt2)

    __radd__ = __add__

    def __neg__(self) -> QSqrt2:
        return QSqrt2(-self.rational, -self.sqrt2)

    def __sub__(self, other: QSqrt2 | Q | int) -> QSqrt2:
        return self + (-self.coerce(other))

    def __rsub__(self, other: QSqrt2 | Q | int) -> QSqrt2:
        return self.coerce(other) - self

    def __mul__(self, other: QSqrt2 | Q | int) -> QSqrt2:
        rhs = self.coerce(other)
        return QSqrt2(
            self.rational * rhs.rational + 2 * self.sqrt2 * rhs.sqrt2,
            self.rational * rhs.sqrt2 + self.sqrt2 * rhs.rational,
        )

    __rmul__ = __mul__

    def __truediv__(self, other: QSqrt2 | Q | int) -> QSqrt2:
        rhs = self.coerce(other)
        denominator = rhs.rational**2 - 2 * rhs.sqrt2**2
        if denominator == 0:
            raise ZeroDivisionError("division by zero in Q(sqrt(2))")
        return QSqrt2(
            (self.rational * rhs.rational - 2 * self.sqrt2 * rhs.sqrt2)
            / denominator,
            (self.sqrt2 * rhs.rational - self.rational * rhs.sqrt2)
            / denominator,
        )

    def __rtruediv__(self, other: QSqrt2 | Q | int) -> QSqrt2:
        return self.coerce(other) / self

    def __pow__(self, exponent: int) -> QSqrt2:
        if exponent < 0:
            return O / (self ** (-exponent))
        result = QSqrt2(Q(1))
        base = self
        remaining = exponent
        while remaining:
            if remaining & 1:
                result *= base
            base *= base
            remaining >>= 1
        return result

    def text(self) -> dict[str, str]:
        return {
            "rational": qtext(self.rational),
            "sqrt2_coefficient": qtext(self.sqrt2),
        }


Z = QSqrt2()
O = QSqrt2(Q(1))
S2 = QSqrt2(Q(0), Q(1))
QMatrix = list[list[Q]]
EMatrix = list[list[QSqrt2]]
QVec3 = tuple[Q, Q, Q]
Edge = tuple[int, int]


def esum(values: Iterable[QSqrt2]) -> QSqrt2:
    return sum(values, Z)


def canonical_edge(edge: Edge) -> Edge:
    first, second = edge
    if first == second:
        raise ValueError("self relation")
    return (first, second) if first < second else (second, first)


def transpose(matrix: Sequence[Sequence[QSqrt2]]) -> EMatrix:
    if not matrix:
        return []
    return [list(column) for column in zip(*matrix, strict=True)]


def matmul(
    first: Sequence[Sequence[QSqrt2]], second: Sequence[Sequence[QSqrt2]]
) -> EMatrix:
    if not first or not second:
        return []
    columns = transpose(second)
    if len(first[0]) != len(second):
        raise ValueError("matrix size mismatch")
    return [
        [esum(a * b for a, b in zip(row, column, strict=True)) for column in columns]
        for row in first
    ]


def matrix_rank(matrix: Sequence[Sequence[QSqrt2]]) -> int:
    work = [list(row) for row in matrix]
    if not work:
        return 0
    rows = len(work)
    columns = len(work[0])
    pivot_row = 0
    for column in range(columns):
        pivot = next(
            (row for row in range(pivot_row, rows) if work[row][column] != Z),
            None,
        )
        if pivot is None:
            continue
        work[pivot_row], work[pivot] = work[pivot], work[pivot_row]
        pivot_value = work[pivot_row][column]
        work[pivot_row] = [entry / pivot_value for entry in work[pivot_row]]
        for row in range(rows):
            if row == pivot_row or work[row][column] == Z:
                continue
            factor = work[row][column]
            work[row] = [
                lhs - factor * rhs
                for lhs, rhs in zip(work[row], work[pivot_row], strict=True)
            ]
        pivot_row += 1
        if pivot_row == rows:
            break
    return pivot_row


def identity(size: int) -> EMatrix:
    return [[O if row == column else Z for column in range(size)] for row in range(size)]


def zero_matrix(rows: int, columns: int) -> EMatrix:
    return [[Z for _column in range(columns)] for _row in range(rows)]


def exact_sqrt(value: Q) -> QSqrt2:
    if value <= 0:
        raise ValueError("positive square root required")

    def rational_sqrt(candidate: Q) -> Q | None:
        numerator = isqrt(candidate.numerator)
        denominator = isqrt(candidate.denominator)
        if numerator * numerator == candidate.numerator and denominator * denominator == candidate.denominator:
            return Q(numerator, denominator)
        return None

    rational = rational_sqrt(value)
    if rational is not None:
        return QSqrt2(rational)
    sqrt2_coefficient = rational_sqrt(value / 2)
    if sqrt2_coefficient is not None:
        return QSqrt2(Q(0), sqrt2_coefficient)
    raise ValueError(f"selected graph length leaves Q(sqrt(2)): {value}")


def determinant3(matrix: Sequence[Sequence[Q]]) -> Q:
    return (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def seven_directions() -> list[tuple[int, QMatrix]]:
    result: list[tuple[int, QMatrix]] = []
    for axis in range(3):
        outer = [[Q(0) for _column in range(3)] for _row in range(3)]
        outer[axis][axis] = Q(1)
        result.append((8, outer))
    for signs in ((1, 1, 1), (1, 1, -1), (1, -1, 1), (-1, 1, 1)):
        result.append(
            (9, [[Q(signs[row] * signs[column], 3) for column in range(3)] for row in range(3)])
        )
    return result


def face_diagonal_directions() -> list[tuple[int, QMatrix]]:
    """Three axes plus the six unoriented face-diagonal lines."""

    result: list[tuple[int, QMatrix]] = []
    for axis in range(3):
        outer = [[Q(0) for _column in range(3)] for _row in range(3)]
        outer[axis][axis] = Q(1)
        result.append((1, outer))
    for first, second in ((0, 1), (0, 2), (1, 2)):
        for sign in (1, -1):
            components = [0, 0, 0]
            components[first] = 1
            components[second] = sign
            result.append(
                (
                    2,
                    [
                        [Q(components[row] * components[column], 2) for column in range(3)]
                        for row in range(3)
                    ],
                )
            )
    return result


def cubature_moments(
    directions: Sequence[tuple[int, QMatrix]],
) -> tuple[QMatrix, list[list[list[list[Q]]]]]:
    second = [[Q(0) for _column in range(3)] for _row in range(3)]
    fourth = [
        [
            [[Q(0) for _l in range(3)] for _k in range(3)]
            for _j in range(3)
        ]
        for _i in range(3)
    ]
    for weight, outer in directions:
        for i in range(3):
            for j in range(3):
                second[i][j] += weight * outer[i][j]
                for k in range(3):
                    for l in range(3):
                        fourth[i][j][k][l] += weight * outer[i][j] * outer[k][l]
    return second, fourth


def delta(first: int, second: int) -> Q:
    return Q(1) if first == second else Q(0)


def add_strain(first: EMatrix, second: EMatrix) -> EMatrix:
    return [
        [lhs + rhs for lhs, rhs in zip(left_row, right_row, strict=True)]
        for left_row, right_row in zip(first, second, strict=True)
    ]


def kelvin_basis(index: int) -> EMatrix:
    result = zero_matrix(3, 3)
    if index < 3:
        result[index][index] = O
        return result
    row, column = ((1, 2), (0, 2), (0, 1))[index - 3]
    result[row][column] = S2 / 2
    result[column][row] = S2 / 2
    return result


def extension(outer: QMatrix, strain: EMatrix) -> QSqrt2:
    return esum(
        outer[row][column] * strain[row][column]
        for row in range(3)
        for column in range(3)
    )


def pair_energy(
    strain: EMatrix,
    directions: Sequence[tuple[int, QMatrix]] | None = None,
) -> QSqrt2:
    selected = seven_directions() if directions is None else directions
    return esum(
        Q(weight, 2) * extension(outer, strain) ** 2
        for weight, outer in selected
    )


def collective_energy(
    strain: EMatrix,
    bulk: Q,
    shear: Q = Q(1),
    *,
    directions: Sequence[tuple[int, QMatrix]] | None = None,
    a_coefficient: Q | None = None,
    b_coefficient: Q | None = None,
) -> QSqrt2:
    selected = seven_directions() if directions is None else directions
    moment, q_value, residual = collective_extension_moments(strain, selected)
    if a_coefficient is None:
        a_coefficient = 3 * bulk / 20
    if b_coefficient is None:
        b_coefficient = shear / 4
    return a_coefficient * q_value**2 / (2 * moment) + b_coefficient * residual / 2


def collective_extension_moments(
    strain: EMatrix, directions: Sequence[tuple[int, QMatrix]]
) -> tuple[Q, QSqrt2, QSqrt2]:
    extensions = [extension(outer, strain) for _weight, outer in directions]
    weights = [Q(weight) for weight, _outer in directions]
    moment = qsum(weights)  # all registered relation lengths are one
    q_value = esum(weight * value for weight, value in zip(weights, extensions, strict=True))
    dilation = q_value / moment
    residual = esum(
        weight * (value - dilation) ** 2
        for weight, value in zip(weights, extensions, strict=True)
    )
    return moment, q_value, residual


def derive_kelvin_tangent(energy: Callable[[EMatrix], QSqrt2]) -> EMatrix:
    basis = [kelvin_basis(index) for index in range(6)]
    basis_energy = [energy(direction) for direction in basis]
    return [
        [
            energy(add_strain(basis[row], basis[column]))
            - basis_energy[row]
            - basis_energy[column]
            for column in range(6)
        ]
        for row in range(6)
    ]


def expected_isotropic_tangent(bulk: Q, shear: Q) -> EMatrix:
    result = zero_matrix(6, 6)
    coupling = bulk - 2 * shear / 3
    for row in range(6):
        result[row][row] += 2 * shear
    for row in range(3):
        for column in range(3):
            result[row][column] += coupling
    return result


def strain_from_rational(matrix: Sequence[Sequence[Q]]) -> EMatrix:
    return [[QSqrt2(entry) for entry in row] for row in matrix]


MIXED_STRAINS: tuple[tuple[str, QMatrix], ...] = (
    (
        "M1",
        [
            [Q(1, 5), Q(1, 7), Q(-1, 11)],
            [Q(1, 7), Q(-2, 5), Q(1, 13)],
            [Q(-1, 11), Q(1, 13), Q(1, 3)],
        ],
    ),
    (
        "M2",
        [
            [Q(-1, 4), Q(1, 9), Q(1, 10)],
            [Q(1, 9), Q(1, 6), Q(-1, 8)],
            [Q(1, 10), Q(-1, 8), Q(1, 12)],
        ],
    ),
    (
        "M3",
        [
            [Q(2, 7), Q(-1, 6), Q(1, 5)],
            [Q(-1, 6), Q(1, 9), Q(1, 14)],
            [Q(1, 5), Q(1, 14), Q(-3, 11)],
        ],
    ),
)


def isotropic_energy(matrix: Sequence[Sequence[Q]], bulk: Q, shear: Q) -> Q:
    trace = qsum(matrix[index][index] for index in range(3))
    norm_squared = qsum(
        matrix[row][column] ** 2 for row in range(3) for column in range(3)
    )
    deviatoric_norm_squared = norm_squared - trace**2 / 3
    return bulk * trace**2 / 2 + shear * deviatoric_norm_squared


def require_rational(value: QSqrt2, label: str) -> Q:
    if value.sqrt2 != 0:
        raise AssertionError(f"{label} unexpectedly retained sqrt(2)")
    return value.rational


def qmatrix_text(matrix: Sequence[Sequence[Q]]) -> list[list[str]]:
    return [[qtext(entry) for entry in row] for row in matrix]


def ematrix_rational_text(matrix: Sequence[Sequence[QSqrt2]], label: str) -> list[list[str]]:
    return [
        [qtext(require_rational(entry, label)) for entry in row]
        for row in matrix
    ]


def squared_distance(first: QVec3, second: QVec3) -> Q:
    return qsum((second[axis] - first[axis]) ** 2 for axis in range(3))


def rational_distance(first: QVec3, second: QVec3) -> Q:
    root = exact_sqrt(squared_distance(first, second))
    if root.sqrt2 != 0:
        raise ValueError("finite rational control requires rational length")
    return root.rational


def finite_extensions(
    reference: dict[int, QVec3], current: dict[int, QVec3], edges: Sequence[Edge]
) -> dict[Edge, tuple[Q, Q]]:
    result: dict[Edge, tuple[Q, Q]] = {}
    for raw_edge in edges:
        edge = canonical_edge(raw_edge)
        reference_length = rational_distance(reference[edge[0]], reference[edge[1]])
        current_length = rational_distance(current[edge[0]], current[edge[1]])
        result[edge] = (reference_length, current_length - reference_length)
    return result


def finite_pair_energy(
    reference: dict[int, QVec3], current: dict[int, QVec3], edges: Sequence[Edge]
) -> Q:
    states = finite_extensions(reference, current, edges)
    return qsum(extension_value**2 for _length, extension_value in states.values())


def finite_collective_energy(
    reference: dict[int, QVec3],
    current: dict[int, QVec3],
    edges: Sequence[Edge],
    bulk: Q,
    shear: Q = Q(1),
) -> Q:
    states = finite_extensions(reference, current, edges)
    a_coefficient = 3 * bulk / 20
    b_coefficient = shear / 4
    result = Q(0)
    for packet_id in sorted(reference):
        incident = [state for edge, state in states.items() if packet_id in edge]
        if not incident:
            continue
        moment = qsum(length**2 for length, _extension in incident)
        q_value = qsum(length * extension_value for length, extension_value in incident)
        dilation = q_value / moment
        residual = qsum(
            (extension_value - dilation * length) ** 2
            for length, extension_value in incident
        )
        result += a_coefficient * q_value**2 / (2 * moment) + b_coefficient * residual / 2
    return result


def transform_points(
    points: dict[int, QVec3], matrix: Sequence[Sequence[Q]], translation: QVec3
) -> dict[int, QVec3]:
    return {
        packet_id: tuple(
            qsum(matrix[row][column] * point[column] for column in range(3))
            + translation[row]
            for row in range(3)
        )
        for packet_id, point in points.items()
    }


def scale_points(points: dict[int, QVec3], scale: Q) -> dict[int, QVec3]:
    return {
        packet_id: tuple(scale * component for component in point)
        for packet_id, point in points.items()
    }


def rename_graph(
    points: dict[int, QVec3], edges: Sequence[Edge], mapping: dict[int, int]
) -> tuple[dict[int, QVec3], list[Edge]]:
    return (
        {mapping[packet_id]: point for packet_id, point in points.items()},
        [(mapping[first], mapping[second]) for first, second in edges],
    )


def finite_objectivity_control() -> dict:
    reference: dict[int, QVec3] = {
        10: (Q(0), Q(0), Q(0)),
        20: (Q(1), Q(0), Q(0)),
        30: (Q(0), Q(1), Q(0)),
        40: (Q(0), Q(0), Q(1)),
    }
    current: dict[int, QVec3] = {
        10: (Q(0), Q(0), Q(0)),
        20: (Q(6, 5), Q(0), Q(0)),
        30: (Q(0), Q(4, 5), Q(0)),
        40: (Q(0), Q(0), Q(3, 2)),
    }
    edges = [(10, 20), (10, 30), (10, 40)]
    rotation = [
        [Q(3, 5), Q(-4, 5), Q(0)],
        [Q(4, 5), Q(3, 5), Q(0)],
        [Q(0), Q(0), Q(1)],
    ]
    translation = (Q(7, 13), Q(-5, 11), Q(3, 17))
    if determinant3(rotation) != 1:
        raise AssertionError("finite control rotation is not proper")
    base_pair = finite_pair_energy(reference, current, edges)
    base_collective = finite_collective_energy(reference, current, edges, Q(2))
    rotated_reference = transform_points(reference, rotation, translation)
    rotated_current = transform_points(current, rotation, translation)
    if finite_pair_energy(rotated_reference, rotated_current, edges) != base_pair:
        raise AssertionError("pair finite objectivity failed")
    if finite_collective_energy(rotated_reference, rotated_current, edges, Q(2)) != base_collective:
        raise AssertionError("collective finite objectivity failed")

    translated_reference = transform_points(
        reference,
        [[Q(1) if row == column else Q(0) for column in range(3)] for row in range(3)],
        translation,
    )
    translated_current = transform_points(
        current,
        [[Q(1) if row == column else Q(0) for column in range(3)] for row in range(3)],
        translation,
    )
    if finite_pair_energy(translated_reference, translated_current, edges) != base_pair:
        raise AssertionError("pair finite translation invariance failed")
    if finite_collective_energy(
        translated_reference, translated_current, edges, Q(2)
    ) != base_collective:
        raise AssertionError("collective finite translation invariance failed")

    reversed_reference = dict(reversed(list(reference.items())))
    reversed_current = dict(reversed(list(current.items())))
    if finite_pair_energy(reversed_reference, reversed_current, edges) != base_pair:
        raise AssertionError("pair packet-order invariance failed")
    if finite_collective_energy(
        reversed_reference, reversed_current, edges, Q(2)
    ) != base_collective:
        raise AssertionError("collective packet-order invariance failed")

    permutations = {
        "packet_reverse": list(reversed(edges)),
        "relation_reverse_orientation": [(second, first) for first, second in reversed(edges)],
        "relation_cycle": edges[1:] + edges[:1],
    }
    for label, permuted in permutations.items():
        if finite_pair_energy(reference, current, permuted) != base_pair:
            raise AssertionError(f"pair {label} invariance failed")
        if finite_collective_energy(reference, current, permuted, Q(2)) != base_collective:
            raise AssertionError(f"collective {label} invariance failed")

    renamings = {
        "reverse": {10: 40, 20: 30, 30: 20, 40: 10},
        "cycle": {10: 20, 20: 30, 30: 40, 40: 10},
        "nontrivial": {10: 991, 20: 17, 30: 503, 40: 42},
    }
    for label, mapping in renamings.items():
        renamed_reference, renamed_edges = rename_graph(reference, edges, mapping)
        renamed_current, _unused = rename_graph(current, edges, mapping)
        if finite_pair_energy(renamed_reference, renamed_current, renamed_edges) != base_pair:
            raise AssertionError(f"pair ID {label} invariance failed")
        if finite_collective_energy(
            renamed_reference, renamed_current, renamed_edges, Q(2)
        ) != base_collective:
            raise AssertionError(f"collective ID {label} invariance failed")

    scale_results = {}
    for scale in (Q(1, 2), Q(2)):
        pair = finite_pair_energy(scale_points(reference, scale), scale_points(current, scale), edges)
        collective = finite_collective_energy(
            scale_points(reference, scale), scale_points(current, scale), edges, Q(2)
        )
        if pair != scale**2 * base_pair or collective != scale**2 * base_collective:
            raise AssertionError("finite energy dimension law failed")
        scale_results[qtext(scale)] = {
            "pair_energy": qtext(pair),
            "collective_energy": qtext(collective),
            "energy_ratio": qtext(scale**2),
        }

    return {
        "arithmetic": "Fraction exact finite reference/current lengths",
        "proper_rotation_determinant": qtext(determinant3(rotation)),
        "base_pair_energy": qtext(base_pair),
        "base_collective_energy_K_over_G_2": qtext(base_collective),
        "translation_proper_rotation_invariant_exact": True,
        "packet_permutation_invariant_exact": True,
        "relation_permutations_and_orientations_invariant_exact": True,
        "packet_id_bijections_invariant_exact": True,
        "stable_ids_supply_no_orientation": True,
        "similarity_dimension_law": "E(sX,sx)=s^2 E(X,x)",
        "scale_controls": scale_results,
    }


def graph_rigidity(
    points: dict[int, QVec3], edges: Sequence[Edge]
) -> tuple[list[int], list[Edge], list[QSqrt2], EMatrix]:
    packet_ids = sorted(points)
    lookup = {packet_id: index for index, packet_id in enumerate(packet_ids)}
    canonical = sorted(canonical_edge(edge) for edge in edges)
    matrix = zero_matrix(len(canonical), 3 * len(packet_ids))
    lengths: list[QSqrt2] = []
    for row, edge in enumerate(canonical):
        offset = tuple(points[edge[1]][axis] - points[edge[0]][axis] for axis in range(3))
        length = exact_sqrt(qsum(component**2 for component in offset))
        lengths.append(length)
        for axis in range(3):
            direction = QSqrt2(offset[axis]) / length
            matrix[row][3 * lookup[edge[0]] + axis] = -direction
            matrix[row][3 * lookup[edge[1]] + axis] = direction
    return packet_ids, canonical, lengths, matrix


def local_collective_h(
    packet_ids: Sequence[int],
    edges: Sequence[Edge],
    lengths: Sequence[QSqrt2],
    bulk: Q,
    shear: Q = Q(1),
) -> EMatrix:
    relation_count = len(edges)
    result = zero_matrix(relation_count, relation_count)
    a_coefficient = 3 * bulk / 20
    b_coefficient = shear / 4
    for packet_id in packet_ids:
        incident = [index for index, edge in enumerate(edges) if packet_id in edge]
        moment = esum(lengths[index] ** 2 for index in incident)
        for row in incident:
            for column in incident:
                result[row][column] += (
                    b_coefficient * (O if row == column else Z)
                    + (a_coefficient - b_coefficient)
                    * lengths[row]
                    * lengths[column]
                    / moment
                )
    return result


def graph_controls() -> list[dict]:
    k4_points: dict[int, QVec3] = {
        1: (Q(0), Q(0), Q(0)),
        2: (Q(1), Q(0), Q(0)),
        3: (Q(0), Q(1), Q(0)),
        4: (Q(0), Q(0), Q(1)),
    }
    k4_edges = [(first, second) for first in k4_points for second in k4_points if first < second]
    octa_points: dict[int, QVec3] = {
        1: (Q(1), Q(0), Q(0)),
        2: (Q(-1), Q(0), Q(0)),
        3: (Q(0), Q(1), Q(0)),
        4: (Q(0), Q(-1), Q(0)),
        5: (Q(0), Q(0), Q(1)),
        6: (Q(0), Q(0), Q(-1)),
    }
    opposite = {canonical_edge(edge) for edge in ((1, 2), (3, 4), (5, 6))}
    octa_edges = [
        (first, second)
        for first in octa_points
        for second in octa_points
        if first < second and (first, second) not in opposite
    ]
    inventory = (
        ("exact.tetrahedron_k4", k4_points, k4_edges, 6, 0),
        ("exact.tetrahedron_k4_minus_edge", k4_points, k4_edges[:-1], 5, 1),
        ("exact.octahedron_graph", octa_points, octa_edges, 12, 0),
    )
    results = []
    for name, points, raw_edges, expected_rank, expected_nonrigid in inventory:
        packet_ids, edges, lengths, rigidity = graph_rigidity(points, raw_edges)
        rank_r = matrix_rank(rigidity)
        if rank_r != expected_rank:
            raise AssertionError(f"{name} exact rigidity rank changed")
        pair_k = matmul(transpose(rigidity), matmul(identity(len(edges)), rigidity))
        if matrix_rank(pair_k) != rank_r:
            raise AssertionError(f"{name} pair Gram changed rigidity kernel")
        target_results = []
        for bulk in (Q(1, 3), Q(1), Q(2), Q(10)):
            h_matrix = local_collective_h(packet_ids, edges, lengths, bulk)
            rank_h = matrix_rank(h_matrix)
            stiffness = matmul(transpose(rigidity), matmul(h_matrix, rigidity))
            rank_k = matrix_rank(stiffness)
            if rank_h != len(edges) or rank_k != rank_r:
                raise AssertionError(f"{name} collective exact kernel mismatch")
            nonlocal_entries = 0
            nonzero_entries = 0
            for row, row_edge in enumerate(edges):
                for column, column_edge in enumerate(edges):
                    if h_matrix[row][column] != Z:
                        nonzero_entries += 1
                        if not set(row_edge).intersection(column_edge):
                            nonlocal_entries += 1
            if nonlocal_entries:
                raise AssertionError(f"{name} local H contains nonlocal coupling")
            target_results.append(
                {
                    "K_over_G": qtext(bulk),
                    "rank_H": rank_h,
                    "rank_K": rank_k,
                    "nullity_K": 3 * len(packet_ids) - rank_k,
                    "H_nonzero_entries": nonzero_entries,
                    "H_nonlocal_entries": nonlocal_entries,
                    "strict_positive_on_relation_coordinates": True,
                }
            )
        results.append(
            {
                "configuration": name,
                "packet_count": len(packet_ids),
                "relation_count": len(edges),
                "rank_R": rank_r,
                "nullity_R": 3 * len(packet_ids) - rank_r,
                "realized_rigid_rank": 6,
                "non_rigid_nullity": expected_nonrigid,
                "pair_gram_rank_K": matrix_rank(pair_k),
                "collective_targets": target_results,
            }
        )
    return results


def tensor_nonzero_entries(fourth: list[list[list[list[Q]]]]) -> dict[str, str]:
    return {
        f"{i}{j}{k}{l}": qtext(fourth[i][j][k][l])
        for i in range(3)
        for j in range(3)
        for k in range(3)
        for l in range(3)
        if fourth[i][j][k][l] != 0
    }


def result_without_hash() -> dict:
    primary_directions = seven_directions()
    secondary_directions = face_diagonal_directions()
    second, fourth = cubature_moments(primary_directions)
    expected_second = [[Q(20) if row == column else Q(0) for column in range(3)] for row in range(3)]
    expected_fourth = [
        [
            [
                [
                    4
                    * (
                        delta(i, j) * delta(k, l)
                        + delta(i, k) * delta(j, l)
                        + delta(i, l) * delta(j, k)
                    )
                    for l in range(3)
                ]
                for k in range(3)
            ]
            for j in range(3)
        ]
        for i in range(3)
    ]
    if second != expected_second or fourth != expected_fourth:
        raise AssertionError("registered seven-direction moment identity failed")

    secondary_second, secondary_fourth = cubature_moments(secondary_directions)
    expected_secondary_second = [
        [Q(5) if row == column else Q(0) for column in range(3)]
        for row in range(3)
    ]
    expected_secondary_fourth = [
        [
            [
                [
                    delta(i, j) * delta(k, l)
                    + delta(i, k) * delta(j, l)
                    + delta(i, l) * delta(j, k)
                    for l in range(3)
                ]
                for k in range(3)
            ]
            for j in range(3)
        ]
        for i in range(3)
    ]
    if (
        secondary_second != expected_secondary_second
        or secondary_fourth != expected_secondary_fourth
    ):
        raise AssertionError("secondary face-diagonal moment identity failed")

    pair_tangent = derive_kelvin_tangent(pair_energy)
    pair_bulk = Q(20, 3)
    pair_shear = Q(4)
    if pair_tangent != expected_isotropic_tangent(pair_bulk, pair_shear):
        raise AssertionError("pair Cauchy tangent failed")
    volume_kelvin = [O, O, O, Z, Z, Z]
    deviatoric_kelvin = [O, -O, Z, Z, Z, Z]
    pair_cross = esum(
        volume_kelvin[row] * pair_tangent[row][column] * deviatoric_kelvin[column]
        for row in range(6)
        for column in range(6)
    )
    if pair_cross != Z:
        raise AssertionError("pair volumetric/deviatoric cross coupling is nonzero")
    pair_mixed = {}
    for name, matrix in MIXED_STRAINS:
        actual = require_rational(pair_energy(strain_from_rational(matrix)), name)
        expected = isotropic_energy(matrix, pair_bulk, pair_shear)
        if actual != expected:
            raise AssertionError(f"pair Cauchy mixed strain {name} failed")
        pair_mixed[name] = qtext(actual)

    collective_targets = []
    for bulk in (Q(1, 3), Q(1), Q(2), Q(10)):
        tangent = derive_kelvin_tangent(lambda strain, value=bulk: collective_energy(strain, value))
        expected = expected_isotropic_tangent(bulk, Q(1))
        if tangent != expected:
            raise AssertionError(f"collective tangent K/G={bulk} failed")
        basis_energies = [
            require_rational(collective_energy(kelvin_basis(index), bulk), "Kelvin energy")
            for index in range(6)
        ]
        mixed = {}
        for name, matrix in MIXED_STRAINS:
            actual = require_rational(collective_energy(strain_from_rational(matrix), bulk), name)
            expected_energy = isotropic_energy(matrix, bulk, Q(1))
            if actual != expected_energy:
                raise AssertionError(f"collective mixed strain {name} failed")
            mixed[name] = qtext(actual)
        volume = [O, O, O, Z, Z, Z]
        deviation = [O, -O, Z, Z, Z, Z]
        cross = esum(
            volume[row] * tangent[row][column] * deviation[column]
            for row in range(6)
            for column in range(6)
        )
        if cross != Z:
            raise AssertionError("volumetric/deviatoric cross coupling is nonzero")
        collective_targets.append(
            {
                "K_over_G": qtext(bulk),
                "A_equals_3K_over_20": qtext(3 * bulk / 20),
                "B_equals_G_over_4": qtext(Q(1, 4)),
                "recovered_bulk": qtext(bulk),
                "recovered_shear": qtext(Q(1)),
                "kelvin_tangent": ematrix_rational_text(tangent, "collective tangent"),
                "kelvin_basis_energies": [qtext(value) for value in basis_energies],
                "mixed_affine_strain_energies": mixed,
                "volumetric_deviatoric_cross_coupling": qtext(require_rational(cross, "cross")),
                "tangent_symmetric_exact": tangent == transpose(tangent),
                "positive_kelvin_eigenchannels": {
                    "volumetric_3K": qtext(3 * bulk),
                    "five_deviatoric_2G": qtext(Q(2)),
                },
                "positive_energy_exact": bulk > 0,
            }
        )

    identity_strain = [[O if row == column else Z for column in range(3)] for row in range(3)]
    deviatoric_probe = [[Z for _column in range(3)] for _row in range(3)]
    deviatoric_probe[0][0] = O
    deviatoric_probe[1][1] = -O
    primary_m, primary_q, primary_residual = collective_extension_moments(
        identity_strain, primary_directions
    )
    _primary_dev_m, primary_dev_q, primary_dev_residual = collective_extension_moments(
        deviatoric_probe, primary_directions
    )
    if (
        primary_m != 60
        or primary_q != QSqrt2(Q(60))
        or primary_residual != Z
        or primary_dev_q != Z
        or primary_dev_residual != QSqrt2(Q(16))
    ):
        raise AssertionError("primary collective moment controls failed")

    secondary_pair_bulk = Q(5, 3)
    secondary_pair_shear = Q(1)
    secondary_pair_tangent = derive_kelvin_tangent(
        lambda strain: pair_energy(strain, secondary_directions)
    )
    if secondary_pair_tangent != expected_isotropic_tangent(
        secondary_pair_bulk, secondary_pair_shear
    ):
        raise AssertionError("secondary pair Cauchy tangent failed")
    secondary_pair_cross = esum(
        volume_kelvin[row]
        * secondary_pair_tangent[row][column]
        * deviatoric_kelvin[column]
        for row in range(6)
        for column in range(6)
    )
    if secondary_pair_cross != Z:
        raise AssertionError("secondary pair volumetric/deviatoric coupling is nonzero")
    secondary_pair_mixed = {}
    for name, matrix in MIXED_STRAINS:
        actual = require_rational(
            pair_energy(strain_from_rational(matrix), secondary_directions),
            f"secondary pair {name}",
        )
        expected_energy = isotropic_energy(
            matrix, secondary_pair_bulk, secondary_pair_shear
        )
        if actual != expected_energy:
            raise AssertionError(f"secondary pair mixed strain {name} failed")
        secondary_pair_mixed[name] = qtext(actual)
    secondary_collective_targets = []
    for bulk in (Q(1, 3), Q(1), Q(2), Q(10)):
        tangent = derive_kelvin_tangent(
            lambda strain, value=bulk: collective_energy(
                strain,
                value,
                directions=secondary_directions,
                a_coefficient=3 * value / 5,
                b_coefficient=Q(1),
            )
        )
        if tangent != expected_isotropic_tangent(bulk, Q(1)):
            raise AssertionError(f"secondary collective tangent K/G={bulk} failed")
        basis_energies = [
            require_rational(
                collective_energy(
                    kelvin_basis(index),
                    bulk,
                    directions=secondary_directions,
                    a_coefficient=3 * bulk / 5,
                    b_coefficient=Q(1),
                ),
                "secondary Kelvin energy",
            )
            for index in range(6)
        ]
        mixed = {}
        for name, matrix in MIXED_STRAINS:
            actual = require_rational(
                collective_energy(
                    strain_from_rational(matrix),
                    bulk,
                    directions=secondary_directions,
                    a_coefficient=3 * bulk / 5,
                    b_coefficient=Q(1),
                ),
                f"secondary {name}",
            )
            expected_energy = isotropic_energy(matrix, bulk, Q(1))
            if actual != expected_energy:
                raise AssertionError(f"secondary collective mixed strain {name} failed")
            mixed[name] = qtext(actual)
        volume = [O, O, O, Z, Z, Z]
        deviation = [O, -O, Z, Z, Z, Z]
        cross = esum(
            volume[row] * tangent[row][column] * deviation[column]
            for row in range(6)
            for column in range(6)
        )
        if cross != Z:
            raise AssertionError("secondary volumetric/deviatoric coupling is nonzero")
        secondary_collective_targets.append(
            {
                "K_over_G": qtext(bulk),
                "A_equals_3K_over_5": qtext(3 * bulk / 5),
                "B_equals_G": qtext(Q(1)),
                "recovered_bulk": qtext(bulk),
                "recovered_shear": qtext(Q(1)),
                "kelvin_tangent": ematrix_rational_text(tangent, "secondary tangent"),
                "kelvin_basis_energies": [qtext(value) for value in basis_energies],
                "mixed_affine_strain_energies": mixed,
                "volumetric_deviatoric_cross_coupling": qtext(
                    require_rational(cross, "secondary cross")
                ),
                "tangent_symmetric_exact": tangent == transpose(tangent),
                "positive_kelvin_eigenchannels": {
                    "volumetric_3K": qtext(3 * bulk),
                    "five_deviatoric_2G": qtext(Q(2)),
                },
                "positive_energy_exact": bulk > 0,
            }
        )
    secondary_m, secondary_q, secondary_residual = collective_extension_moments(
        identity_strain, secondary_directions
    )
    _secondary_dev_m, secondary_dev_q, secondary_dev_residual = (
        collective_extension_moments(deviatoric_probe, secondary_directions)
    )
    if (
        secondary_m != 15
        or secondary_q != QSqrt2(Q(15))
        or secondary_residual != Z
        or secondary_dev_q != Z
        or secondary_dev_residual != QSqrt2(Q(4))
    ):
        raise AssertionError("secondary collective moment controls failed")

    graph_results = graph_controls()
    return {
        "schema": SCHEMA,
        "seed": SEED,
        "implementation": IMPLEMENTATION,
        "scope": "energy-only exact oracle; no force, stress, or dynamics",
        "seven_direction_cubature": {
            "direction_count": 7,
            "axis_weights": [8, 8, 8],
            "body_diagonal_line_weights": [9, 9, 9, 9],
            "total_weight_and_moment_m": qtext(Q(60)),
            "second_moment": qmatrix_text(second),
            "expected_second_moment": "20 delta_ij",
            "fourth_moment_nonzero_entries": tensor_nonzero_entries(fourth),
            "expected_fourth_moment": (
                "4(delta_ij delta_kl + delta_ik delta_jl + delta_il delta_jk)"
            ),
            "second_and_fourth_moments_exact": True,
        },
        "pair_separable_cauchy_control": {
            "lambda": qtext(Q(4)),
            "G": qtext(pair_shear),
            "K": qtext(pair_bulk),
            "K_over_G": qtext(Q(5, 3)),
            "poisson_ratio_3d": qtext(Q(1, 4)),
            "lambda_equals_G": True,
            "kelvin_tangent_derived_from_extensions": ematrix_rational_text(
                pair_tangent, "pair tangent"
            ),
            "tangent_symmetric_exact": pair_tangent == transpose(pair_tangent),
            "volumetric_deviatoric_cross_coupling": qtext(
                require_rational(pair_cross, "pair cross")
            ),
            "mixed_affine_strain_energies": pair_mixed,
            "registered_cauchy_restriction_reproduced": True,
            "negative_control_only": True,
        },
        "local_collective_bulk_shear_controls": {
            "derived_cubature_identities": {
                "m": qtext(Q(60)),
                "q_over_trace": qtext(Q(20)),
                "deviatoric_extension_norm_coefficient": qtext(Q(8)),
            },
            "coefficient_map": "A=3K/20, B=G/4",
            "targets": collective_targets,
            "independent_two_channel_control_exact": True,
        },
        "independent_face_diagonal_bulk_control": {
            "direction_count": 9,
            "axis_weights": [1, 1, 1],
            "face_diagonal_line_weights": [2, 2, 2, 2, 2, 2],
            "total_weight_and_moment_m": qtext(Q(15)),
            "second_moment": qmatrix_text(secondary_second),
            "expected_second_moment": "5 delta_ij",
            "fourth_moment_nonzero_entries": tensor_nonzero_entries(secondary_fourth),
            "expected_fourth_moment": (
                "delta_ij delta_kl + delta_ik delta_jl + delta_il delta_jk"
            ),
            "moments_exact": True,
            "pair_cauchy_control": {
                "lambda": qtext(Q(1)),
                "G": qtext(Q(1)),
                "K": qtext(secondary_pair_bulk),
                "K_over_G": qtext(Q(5, 3)),
                "poisson_ratio_3d": qtext(Q(1, 4)),
                "kelvin_tangent_derived_from_extensions": ematrix_rational_text(
                    secondary_pair_tangent, "secondary pair tangent"
                ),
                "tangent_symmetric_exact": (
                    secondary_pair_tangent == transpose(secondary_pair_tangent)
                ),
                "volumetric_deviatoric_cross_coupling": qtext(
                    require_rational(secondary_pair_cross, "secondary pair cross")
                ),
                "mixed_affine_strain_energies": secondary_pair_mixed,
                "registered_cauchy_restriction_reproduced": True,
            },
            "collective_identities": {
                "m": qtext(Q(15)),
                "q_over_trace": qtext(Q(5)),
                "deviatoric_extension_norm_coefficient": qtext(Q(2)),
                "coefficient_map": "A=3K/5, B=G",
            },
            "collective_targets": secondary_collective_targets,
            "independent_two_channel_control_exact": True,
        },
        "finite_length_objectivity_and_dimension": finite_objectivity_control(),
        "selected_exact_graph_H_kernel_controls": {
            "field": "Q(sqrt(2)) exact Gaussian elimination",
            "unit_direction_rigidity_rows": True,
            "H_locality": "off-diagonal coupling only for relations sharing a packet",
            "graphs": graph_results,
            "eligible_rigid_graphs_gain_no_nonrigid_zero_mode": True,
            "intentionally_floppy_graph_remains_floppy": True,
        },
        "global_dense_H_used": False,
        "persistent_kinematic_state_added": False,
        "numerical_regularization_used": False,
        "force_or_time_integration_present": False,
        "exact_oracle_controls_passed": True,
        "candidate_promotion_permitted": False,
        "result_boundary": "NO PROMOTION to mechanics or dynamics",
    }


def render_result(result: dict) -> str:
    return json.dumps(result, indent=2, sort_keys=True)


def run() -> dict:
    result = result_without_hash()
    result["result_sha256_before_hash_field"] = hashlib.sha256(
        render_result(result).encode("utf-8")
    ).hexdigest()
    return result


def verify(path: Path, actual: dict) -> None:
    try:
        expected = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"CONSTITUTIVE EXPRESSIVITY ORACLE INVALID: {error}") from error
    if not isinstance(expected, dict):
        raise SystemExit("CONSTITUTIVE EXPRESSIVITY ORACLE INVALID: canonical root is not an object")
    payload = dict(expected)
    claimed_hash = payload.pop("result_sha256_before_hash_field", None)
    computed_hash = hashlib.sha256(render_result(payload).encode("utf-8")).hexdigest()
    if claimed_hash != computed_hash:
        raise SystemExit("CONSTITUTIVE EXPRESSIVITY ORACLE INVALID: canonical pre-hash mismatch")
    if expected != actual:
        raise SystemExit("CONSTITUTIVE EXPRESSIVITY ORACLE MISMATCH: canonical result differs")


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
