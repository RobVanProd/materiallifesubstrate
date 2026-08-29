#!/usr/bin/env python3
"""Independent exact/high-precision oracle for the Kelvin covariance audit.

This bounded oracle reconstructs one corrected local particle-gradient block
without importing or executing MLS C++ code.  Exact arithmetic is performed in
Q(sqrt(2)); Decimal arithmetic is used only to display independently computed
singular spectra.  No result in this file is a candidate-promotion decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from pathlib import Path
from typing import Iterable, Sequence


SCHEMA = "mls.kelvin-covariance.exact-oracle.v1"
SEED = 260828
DECIMAL_PRECISION = 100
IMPLEMENTATION = (
    "independent Python standard-library Fraction Q(sqrt(2)) algebra and "
    "100-digit Decimal Jacobi spectrum oracle"
)


@dataclass(frozen=True)
class QSqrt2:
    """An exact a + b*sqrt(2) element with rational a and b."""

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
        denominator = rhs.rational * rhs.rational - 2 * rhs.sqrt2 * rhs.sqrt2
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
            return ONE / (self ** (-exponent))
        result = ONE
        base = self
        remaining = exponent
        while remaining:
            if remaining & 1:
                result *= base
            base *= base
            remaining >>= 1
        return result

    def to_decimal(self) -> Decimal:
        return fraction_decimal(self.rational) + fraction_decimal(self.sqrt2) * Decimal(2).sqrt()


S2 = QSqrt2(Q(0), Q(1))
ZERO = QSqrt2()
ONE = QSqrt2(Q(1))

Vec3 = tuple[Q, Q, Q]
RationalMatrix = list[list[Q]]
ExactMatrix = list[list[QSqrt2]]


def fraction_text(value: Q) -> str:
    return f"{value.numerator}/{value.denominator}"


def exact_text(value: QSqrt2) -> dict[str, str]:
    return {
        "rational": fraction_text(value.rational),
        "sqrt2_coefficient": fraction_text(value.sqrt2),
    }


def fraction_decimal(value: Q) -> Decimal:
    return Decimal(value.numerator) / Decimal(value.denominator)


def decimal_text(value: Decimal, digits: int = 60) -> str:
    with localcontext() as context:
        context.prec = digits
        return format(+value, ".{}E".format(digits - 1))


def qsum(values: Iterable[Q]) -> Q:
    return sum(values, Q(0))


def esum(values: Iterable[QSqrt2]) -> QSqrt2:
    return sum(values, ZERO)


def qdot(first: Sequence[Q], second: Sequence[Q]) -> Q:
    if len(first) != len(second):
        raise ValueError("dot-product size mismatch")
    return qsum(a * b for a, b in zip(first, second, strict=True))


def edot(first: Sequence[QSqrt2], second: Sequence[QSqrt2]) -> QSqrt2:
    if len(first) != len(second):
        raise ValueError("dot-product size mismatch")
    return esum(a * b for a, b in zip(first, second, strict=True))


def qtranspose(matrix: Sequence[Sequence[Q]]) -> RationalMatrix:
    if not matrix:
        return []
    return [list(column) for column in zip(*matrix, strict=True)]


def etranspose(matrix: Sequence[Sequence[QSqrt2]]) -> ExactMatrix:
    if not matrix:
        return []
    return [list(column) for column in zip(*matrix, strict=True)]


def qmatmul(first: Sequence[Sequence[Q]], second: Sequence[Sequence[Q]]) -> RationalMatrix:
    if not first or not second:
        return []
    columns = qtranspose(second)
    if len(first[0]) != len(second):
        raise ValueError("matrix-product size mismatch")
    return [[qdot(row, column) for column in columns] for row in first]


def ematmul(first: Sequence[Sequence[QSqrt2]], second: Sequence[Sequence[QSqrt2]]) -> ExactMatrix:
    if not first or not second:
        return []
    columns = etranspose(second)
    if len(first[0]) != len(second):
        raise ValueError("matrix-product size mismatch")
    return [[edot(row, column) for column in columns] for row in first]


def escale(factor: QSqrt2 | Q | int, matrix: Sequence[Sequence[QSqrt2]]) -> ExactMatrix:
    scalar = QSqrt2.coerce(factor)
    return [[scalar * entry for entry in row] for row in matrix]


def qidentity(size: int) -> RationalMatrix:
    return [[Q(1) if row == column else Q(0) for column in range(size)] for row in range(size)]


def eidentity(size: int) -> ExactMatrix:
    return [[ONE if row == column else ZERO for column in range(size)] for row in range(size)]


def to_exact(matrix: Sequence[Sequence[Q]]) -> ExactMatrix:
    return [[QSqrt2(value) for value in row] for row in matrix]


def inverse3(matrix: Sequence[Sequence[Q]]) -> RationalMatrix:
    if len(matrix) != 3 or any(len(row) != 3 for row in matrix):
        raise ValueError("inverse3 requires a 3x3 matrix")
    work = [list(row) + qidentity(3)[row_index] for row_index, row in enumerate(matrix)]
    for column in range(3):
        pivot = next((row for row in range(column, 3) if work[row][column] != 0), None)
        if pivot is None:
            raise ValueError("singular local moment")
        work[column], work[pivot] = work[pivot], work[column]
        divisor = work[column][column]
        work[column] = [entry / divisor for entry in work[column]]
        for row in range(3):
            if row == column:
                continue
            multiplier = work[row][column]
            work[row] = [
                work[row][entry] - multiplier * work[column][entry]
                for entry in range(6)
            ]
    return [row[3:] for row in work]


def qmatvec3(matrix: Sequence[Sequence[Q]], vector: Vec3) -> Vec3:
    values = [qdot(row, vector) for row in matrix]
    if len(values) != 3:
        raise ValueError("expected 3D matrix")
    return tuple(values)  # type: ignore[return-value]


def add3(first: Vec3, second: Vec3) -> Vec3:
    return tuple(first[axis] + second[axis] for axis in range(3))  # type: ignore[return-value]


def sub3(first: Vec3, second: Vec3) -> Vec3:
    return tuple(first[axis] - second[axis] for axis in range(3))  # type: ignore[return-value]


def scale3(factor: Q, vector: Vec3) -> Vec3:
    return tuple(factor * entry for entry in vector)  # type: ignore[return-value]


def corrected_symmetric_gradient_block(
    positions: Sequence[Vec3], support_radius: Q
) -> ExactMatrix:
    """Build Candidate B's center block in its orthonormal Kelvin basis."""
    if len(positions) < 4 or support_radius <= 0:
        raise ValueError("insufficient positions or invalid support")
    center = positions[0]
    offsets = [sub3(point, center) for point in positions[1:]]
    weights: list[Q] = []
    radius_squared = support_radius * support_radius
    for offset in offsets:
        squared_distance = qdot(offset, offset)
        if not Q(0) < squared_distance < radius_squared:
            raise ValueError("registered neighbor outside open support")
        weights.append((Q(1) - squared_distance / radius_squared) ** 2)

    moment = [[Q(0) for _ in range(3)] for _ in range(3)]
    for weight, offset in zip(weights, offsets, strict=True):
        for row in range(3):
            for column in range(3):
                moment[row][column] += weight * offset[row] * offset[column]
    moment_inverse = inverse3(moment)
    coefficients = [
        tuple(
            weight * qsum(moment_inverse[axis][inner] * offset[inner] for inner in range(3))
            for axis in range(3)
        )
        for weight, offset in zip(weights, offsets, strict=True)
    ]

    width = 3 * len(positions)
    rows = [[ZERO for _ in range(width)] for _ in range(6)]
    inv_sqrt2 = S2 / 2
    for neighbor_index, coefficient in enumerate(coefficients, start=1):
        for axis in range(3):
            neighbor_column = 3 * neighbor_index + axis
            center_column = axis
            diagonal = QSqrt2(coefficient[axis])
            rows[axis][neighbor_column] += diagonal
            rows[axis][center_column] -= diagonal

        kelvin_pairs = ((0, 1), (0, 2), (1, 2))
        for output, (first, second) in enumerate(kelvin_pairs, start=3):
            first_coefficient = inv_sqrt2 * coefficient[second]
            second_coefficient = inv_sqrt2 * coefficient[first]
            rows[output][3 * neighbor_index + first] += first_coefficient
            rows[output][first] -= first_coefficient
            rows[output][3 * neighbor_index + second] += second_coefficient
            rows[output][second] -= second_coefficient
    return rows


def kelvin_basis() -> list[ExactMatrix]:
    basis: list[ExactMatrix] = []
    for axis in range(3):
        matrix = [[ZERO for _ in range(3)] for _ in range(3)]
        matrix[axis][axis] = ONE
        basis.append(matrix)
    inv_sqrt2 = S2 / 2
    for first, second in ((0, 1), (0, 2), (1, 2)):
        matrix = [[ZERO for _ in range(3)] for _ in range(3)]
        matrix[first][second] = inv_sqrt2
        matrix[second][first] = inv_sqrt2
        basis.append(matrix)
    return basis


def kelvin_coordinates(tensor: Sequence[Sequence[QSqrt2]]) -> list[QSqrt2]:
    return [
        tensor[0][0],
        tensor[1][1],
        tensor[2][2],
        S2 * tensor[0][1],
        S2 * tensor[0][2],
        S2 * tensor[1][2],
    ]


def kelvin_rotation(rotation: Sequence[Sequence[Q]]) -> ExactMatrix:
    q = to_exact(rotation)
    qt = etranspose(q)
    columns: list[list[QSqrt2]] = []
    for tensor in kelvin_basis():
        columns.append(kelvin_coordinates(ematmul(ematmul(q, tensor), qt)))
    return [list(row) for row in zip(*columns, strict=True)]


def block_rotation(rotation: Sequence[Sequence[Q]], block_count: int) -> ExactMatrix:
    width = 3 * block_count
    result = [[ZERO for _ in range(width)] for _ in range(width)]
    for block in range(block_count):
        for row in range(3):
            for column in range(3):
                result[3 * block + row][3 * block + column] = QSqrt2(rotation[row][column])
    return result


def gram(matrix: Sequence[Sequence[QSqrt2]]) -> ExactMatrix:
    return ematmul(matrix, etranspose(matrix))


def frobenius_squared(matrix: Sequence[Sequence[QSqrt2]]) -> QSqrt2:
    return esum(entry * entry for row in matrix for entry in row)


def trace_square(matrix: Sequence[Sequence[QSqrt2]]) -> QSqrt2:
    product = ematmul(matrix, matrix)
    return esum(product[index][index] for index in range(len(product)))


def row_normalized_trace_gram_squared(matrix: Sequence[Sequence[QSqrt2]]) -> QSqrt2:
    norms_squared = [edot(row, row) for row in matrix]
    if any(value == ZERO for value in norms_squared):
        raise ValueError("zero row cannot be normalized")
    return esum(
        edot(matrix[first], matrix[second]) ** 2
        / (norms_squared[first] * norms_squared[second])
        for first in range(len(matrix))
        for second in range(len(matrix))
    )


def decimal_matrix(matrix: Sequence[Sequence[QSqrt2]]) -> list[list[Decimal]]:
    return [[entry.to_decimal() for entry in row] for row in matrix]


def decimal_eigenvalues_symmetric(matrix: Sequence[Sequence[QSqrt2]]) -> list[Decimal]:
    """Deterministic high-precision Jacobi eigenvalues for a small Gram matrix."""
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        work = decimal_matrix(matrix)
        size = len(work)
        if size == 0 or any(len(row) != size for row in work):
            raise ValueError("Jacobi eigensolver requires a nonempty square matrix")
        tolerance = Decimal(10) ** Decimal(-88)
        for _iteration in range(20000):
            candidates = [
                (abs(work[row][column]), row, column)
                for row in range(size)
                for column in range(row + 1, size)
            ]
            magnitude, pivot, column = max(candidates)
            if magnitude <= tolerance:
                return sorted((+work[index][index] for index in range(size)), reverse=True)
            off_diagonal = work[pivot][column]
            tau = (work[column][column] - work[pivot][pivot]) / (2 * off_diagonal)
            sign = Decimal(1) if tau >= 0 else Decimal(-1)
            tangent = sign / (abs(tau) + (Decimal(1) + tau * tau).sqrt())
            cosine = Decimal(1) / (Decimal(1) + tangent * tangent).sqrt()
            sine = tangent * cosine
            app = work[pivot][pivot]
            aqq = work[column][column]
            apq = off_diagonal
            for index in range(size):
                if index in (pivot, column):
                    continue
                aip = work[index][pivot]
                aiq = work[index][column]
                work[index][pivot] = cosine * aip - sine * aiq
                work[pivot][index] = work[index][pivot]
                work[index][column] = sine * aip + cosine * aiq
                work[column][index] = work[index][column]
            work[pivot][pivot] = (
                cosine * cosine * app
                - 2 * sine * cosine * apq
                + sine * sine * aqq
            )
            work[column][column] = (
                sine * sine * app
                + 2 * sine * cosine * apq
                + cosine * cosine * aqq
            )
            work[pivot][column] = Decimal(0)
            work[column][pivot] = Decimal(0)
        raise RuntimeError("high-precision Jacobi eigensolver did not converge")


def decimal_row_normalized_gram(matrix: Sequence[Sequence[QSqrt2]]) -> list[list[Decimal]]:
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        converted = decimal_matrix(matrix)
        norms = [sum((entry * entry for entry in row), Decimal(0)).sqrt() for row in converted]
        return [
            [
                sum(
                    (converted[first][entry] * converted[second][entry] for entry in range(len(converted[0]))),
                    Decimal(0),
                )
                / (norms[first] * norms[second])
                for second in range(len(converted))
            ]
            for first in range(len(converted))
        ]


def decimal_eigenvalues_from_decimal(matrix: Sequence[Sequence[Decimal]]) -> list[Decimal]:
    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        work = [[+entry for entry in row] for row in matrix]
        size = len(work)
        tolerance = Decimal(10) ** Decimal(-88)
        for _iteration in range(20000):
            magnitude, pivot, column = max(
                (abs(work[row][col]), row, col)
                for row in range(size)
                for col in range(row + 1, size)
            )
            if magnitude <= tolerance:
                return sorted((+work[index][index] for index in range(size)), reverse=True)
            apq = work[pivot][column]
            tau = (work[column][column] - work[pivot][pivot]) / (2 * apq)
            sign = Decimal(1) if tau >= 0 else Decimal(-1)
            tangent = sign / (abs(tau) + (Decimal(1) + tau * tau).sqrt())
            cosine = Decimal(1) / (Decimal(1) + tangent * tangent).sqrt()
            sine = tangent * cosine
            app = work[pivot][pivot]
            aqq = work[column][column]
            for index in range(size):
                if index in (pivot, column):
                    continue
                aip = work[index][pivot]
                aiq = work[index][column]
                work[index][pivot] = cosine * aip - sine * aiq
                work[pivot][index] = work[index][pivot]
                work[index][column] = sine * aip + cosine * aiq
                work[column][index] = work[index][column]
            work[pivot][pivot] = cosine * cosine * app - 2 * sine * cosine * apq + sine * sine * aqq
            work[column][column] = sine * sine * app + 2 * sine * cosine * apq + cosine * cosine * aqq
            work[pivot][column] = Decimal(0)
            work[column][pivot] = Decimal(0)
        raise RuntimeError("high-precision Jacobi eigensolver did not converge")


def result_without_hash() -> dict:
    positions: list[Vec3] = [
        (Q(1, 5), Q(-2, 7), Q(3, 11)),
        (Q(6, 5), Q(-2, 7), Q(3, 11)),
        (Q(1, 5), Q(12, 7), Q(3, 11)),
        (Q(1, 5), Q(-2, 7), Q(36, 11)),
        (Q(-4, 5), Q(-11, 14), Q(3, 11)),
        (Q(1, 5), Q(-9, 7), Q(-2, 33)),
        (Q(-1, 20), Q(-2, 7), Q(-8, 11)),
    ]
    support_radius = Q(4)
    rotation: RationalMatrix = [
        [Q(3, 5), Q(-4, 5), Q(0)],
        [Q(4, 5), Q(3, 5), Q(0)],
        [Q(0), Q(0), Q(1)],
    ]
    scale_factor = Q(7, 3)
    translation: Vec3 = (Q(5, 13), Q(-7, 17), Q(11, 19))
    transformed_positions = [
        add3(scale3(scale_factor, qmatvec3(rotation, point)), translation)
        for point in positions
    ]
    rotated_positions = [
        add3(qmatvec3(rotation, point), translation) for point in positions
    ]

    raw = corrected_symmetric_gradient_block(positions, support_radius)
    rotated = corrected_symmetric_gradient_block(rotated_positions, support_radius)
    transformed = corrected_symmetric_gradient_block(
        transformed_positions, scale_factor * support_radius
    )
    input_transform = block_rotation(rotation, len(positions))
    output_transform = kelvin_rotation(rotation)
    expected_rotated = ematmul(
        ematmul(output_transform, raw), etranspose(input_transform)
    )
    if rotated != expected_rotated:
        raise AssertionError("exact rotation/translation corrected-gradient law failed")
    expected_transformed = escale(
        Q(1, 1) / scale_factor,
        expected_rotated,
    )
    if transformed != expected_transformed:
        raise AssertionError("exact corrected-gradient similarity law failed")
    if ematmul(input_transform, etranspose(input_transform)) != eidentity(3 * len(positions)):
        raise AssertionError("input rotation is not exactly orthogonal")
    if ematmul(output_transform, etranspose(output_transform)) != eidentity(6):
        raise AssertionError("Kelvin output transform is not exactly orthogonal")

    raw_gram = gram(raw)
    transformed_gram = gram(transformed)
    expected_transformed_gram = escale(
        Q(1, 1) / (scale_factor * scale_factor),
        ematmul(ematmul(output_transform, raw_gram), etranspose(output_transform)),
    )
    if transformed_gram != expected_transformed_gram:
        raise AssertionError("raw Gram similarity failed")

    raw_frobenius_squared = frobenius_squared(raw)
    transformed_frobenius_squared = frobenius_squared(transformed)
    if transformed_frobenius_squared != raw_frobenius_squared / (scale_factor * scale_factor):
        raise AssertionError("block scalar norm did not scale by 1/s")
    block_gram = escale(ONE / raw_frobenius_squared, raw_gram)
    transformed_block_gram = escale(ONE / transformed_frobenius_squared, transformed_gram)
    if transformed_block_gram != ematmul(
        ematmul(output_transform, block_gram), etranspose(output_transform)
    ):
        raise AssertionError("rotationally invariant block normalization broke covariance")

    # Use the pure rigid transform here so the counterexample has no scalar
    # factor at all: the raw matrices differ only by orthogonal left/right
    # transformations, while independently normalizing scalar Kelvin rows
    # destroys that relation.
    row_trace_square = row_normalized_trace_gram_squared(raw)
    transformed_row_trace_square = row_normalized_trace_gram_squared(rotated)
    counterexample_difference = transformed_row_trace_square - row_trace_square
    if counterexample_difference == ZERO:
        raise AssertionError("registered scalar-row normalization counterexample is degenerate")

    with localcontext() as context:
        context.prec = DECIMAL_PRECISION
        raw_eigenvalues = decimal_eigenvalues_symmetric(raw_gram)
        scaled_transformed_eigenvalues = [
            value * fraction_decimal(scale_factor * scale_factor)
            for value in decimal_eigenvalues_symmetric(transformed_gram)
        ]
        raw_spectrum_delta = max(
            abs(first - second)
            for first, second in zip(raw_eigenvalues, scaled_transformed_eigenvalues, strict=True)
        )
        row_eigenvalues = decimal_eigenvalues_from_decimal(decimal_row_normalized_gram(raw))
        transformed_row_eigenvalues = decimal_eigenvalues_from_decimal(
            decimal_row_normalized_gram(rotated)
        )
        row_spectrum_delta = max(
            abs(first - second)
            for first, second in zip(row_eigenvalues, transformed_row_eigenvalues, strict=True)
        )
        if raw_spectrum_delta > Decimal("1e-80"):
            raise AssertionError("high-precision raw spectrum covariance check failed")
        if row_spectrum_delta < Decimal("1e-20"):
            raise AssertionError("high-precision row-normalized spectra did not separate")

    return {
        "schema": SCHEMA,
        "seed": SEED,
        "implementation": IMPLEMENTATION,
        "scope": "bounded diagnostic-coordinate audit; independent of C++; promotion-ineligible",
        "arithmetic": "exact Fraction arithmetic in Q(sqrt(2)); 100-digit Decimal only for displayed spectra",
        "configuration": {
            "point_count": len(positions),
            "positions_m": [[fraction_text(entry) for entry in point] for point in positions],
            "support_radius_m": fraction_text(support_radius),
            "proper_rotation": [[fraction_text(entry) for entry in row] for row in rotation],
            "scale": fraction_text(scale_factor),
            "translation_m": [fraction_text(entry) for entry in translation],
        },
        "raw_covariance": {
            "law": "R(sQx+t) = (1/s) K(Q) R(x) T(Q)^T",
            "input_transform_orthogonal_exact": True,
            "kelvin_output_transform_orthogonal_exact": True,
            "pure_rotation_translation_pullback_exact": True,
            "operator_identity_exact": True,
            "gram_similarity_exact": True,
            "singular_values_scale_as_inverse_length": True,
            "high_precision_max_scaled_gram_eigenvalue_delta": decimal_text(raw_spectrum_delta),
            "base_gram_eigenvalues": [decimal_text(value) for value in raw_eigenvalues],
            "scale_squared_times_transformed_gram_eigenvalues": [
                decimal_text(value) for value in scaled_transformed_eigenvalues
            ],
        },
        "scalar_row_normalization_counterexample": {
            "normalization": "divide every scalar Kelvin output row by its own Euclidean norm",
            "base_trace_of_normalized_gram_squared": exact_text(row_trace_square),
            "transformed_trace_of_normalized_gram_squared": exact_text(
                transformed_row_trace_square
            ),
            "exact_nonzero_difference": exact_text(counterexample_difference),
            "spectral_consequence": (
                "trace((Rhat Rhat^T)^2) is the sum of fourth powers of singular values; "
                "the exact nonzero difference proves spectrum covariance is destroyed"
            ),
            "base_normalized_gram_eigenvalues": [
                decimal_text(value) for value in row_eigenvalues
            ],
            "transformed_normalized_gram_eigenvalues": [
                decimal_text(value) for value in transformed_row_eigenvalues
            ],
            "high_precision_max_eigenvalue_delta": decimal_text(row_spectrum_delta),
            "counterexample_confirmed": True,
        },
        "rotationally_invariant_block_scalar_diagnostic": {
            "normalization": "one Frobenius scalar for the complete six-row Kelvin block",
            "base_frobenius_norm_squared": exact_text(raw_frobenius_squared),
            "transformed_frobenius_norm_squared": exact_text(transformed_frobenius_squared),
            "inverse_scale_squared_relation_exact": True,
            "normalized_gram_similarity_exact": True,
            "diagnostic_only": True,
        },
        "regularization_used": False,
        "candidate_promotion_permitted": False,
        "constitutive_law_present": False,
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
        raise SystemExit(f"KELVIN COVARIANCE ORACLE INVALID: {error}") from error
    if not isinstance(expected, dict):
        raise SystemExit("KELVIN COVARIANCE ORACLE INVALID: canonical root is not an object")
    expected_payload = dict(expected)
    claimed_hash = expected_payload.pop("result_sha256_before_hash_field", None)
    computed_hash = hashlib.sha256(render_result(expected_payload).encode("utf-8")).hexdigest()
    if claimed_hash != computed_hash:
        raise SystemExit("KELVIN COVARIANCE ORACLE INVALID: canonical pre-hash mismatch")
    if expected != actual:
        raise SystemExit("KELVIN COVARIANCE ORACLE MISMATCH: canonical result differs")


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
