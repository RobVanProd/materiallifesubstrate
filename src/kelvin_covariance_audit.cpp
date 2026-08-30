#include "mls/kelvin_covariance_audit.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace mls::experimental::kelvin_covariance_audit {
namespace {

using observation::DenseMatrix;

[[nodiscard]] bool finite(const Vec3d value) {
    return std::isfinite(value.x) && std::isfinite(value.y) &&
        std::isfinite(value.z);
}

[[nodiscard]] double stable_l2(const std::span<const double> values) {
    double scale = 0.0;
    long double sum = 0.0L;
    for (const double value : values) {
        const double magnitude = std::abs(value);
        if (!std::isfinite(magnitude)) {
            return std::numeric_limits<double>::infinity();
        }
        if (magnitude == 0.0) {
            continue;
        }
        if (magnitude > scale) {
            const double ratio = scale / magnitude;
            sum = 1.0L + sum * static_cast<long double>(ratio) * ratio;
            scale = magnitude;
        } else {
            const double ratio = magnitude / scale;
            sum += static_cast<long double>(ratio) * ratio;
        }
    }
    return scale == 0.0 ? 0.0 :
        scale * std::sqrt(static_cast<double>(sum));
}

[[nodiscard]] double frobenius(const DenseMatrix& matrix) {
    return stable_l2(matrix.entries());
}

[[nodiscard]] DenseMatrix multiply_dense(
    const DenseMatrix& lhs, const DenseMatrix& rhs) {
    if (lhs.column_count() != rhs.row_count()) {
        throw std::invalid_argument("dense matrix dimension mismatch");
    }
    DenseMatrix result(lhs.row_count(), rhs.column_count());
    for (std::size_t row = 0; row < lhs.row_count(); ++row) {
        for (std::size_t column = 0; column < rhs.column_count(); ++column) {
            long double value = 0.0L;
            for (std::size_t inner = 0; inner < lhs.column_count(); ++inner) {
                value += static_cast<long double>(lhs(row, inner)) *
                    rhs(inner, column);
            }
            result(row, column) = static_cast<double>(value);
        }
    }
    return result;
}

[[nodiscard]] DenseMatrix transpose_dense(const DenseMatrix& matrix) {
    DenseMatrix result(matrix.column_count(), matrix.row_count());
    for (std::size_t row = 0; row < matrix.row_count(); ++row) {
        for (std::size_t column = 0; column < matrix.column_count(); ++column) {
            result(column, row) = matrix(row, column);
        }
    }
    return result;
}

[[nodiscard]] DenseMatrix block_diagonal(
    const DenseMatrix& block, const std::size_t count) {
    DenseMatrix result(block.row_count() * count, block.column_count() * count);
    for (std::size_t index = 0; index < count; ++index) {
        for (std::size_t row = 0; row < block.row_count(); ++row) {
            for (std::size_t column = 0; column < block.column_count(); ++column) {
                result(index * block.row_count() + row,
                    index * block.column_count() + column) = block(row, column);
            }
        }
    }
    return result;
}

[[nodiscard]] DenseMatrix input_rotation(const Matrix3d& rotation) {
    DenseMatrix result(3U, 3U);
    for (std::size_t row = 0; row < 3U; ++row) {
        for (std::size_t column = 0; column < 3U; ++column) {
            result(row, column) = rotation.value[row][column];
        }
    }
    return result;
}

[[nodiscard]] std::array<double, 6> kelvin_components(
    const Matrix3d& symmetric) {
    constexpr double sqrt_two = 1.414213562373095048801688724209698;
    return {symmetric.value[0][0], symmetric.value[1][1],
        symmetric.value[2][2], sqrt_two * symmetric.value[0][1],
        sqrt_two * symmetric.value[0][2],
        sqrt_two * symmetric.value[1][2]};
}

[[nodiscard]] Matrix3d kelvin_basis(const std::size_t column) {
    Matrix3d result{};
    if (column < 3U) {
        result.value[column][column] = 1.0;
        return result;
    }
    constexpr double inverse_sqrt_two =
        0.707106781186547524400844362104849;
    const std::array<std::array<std::size_t, 2>, 3> pairs{{
        {{0U, 1U}}, {{0U, 2U}}, {{1U, 2U}}}};
    const auto pair = pairs[column - 3U];
    result.value[pair[0]][pair[1]] = inverse_sqrt_two;
    result.value[pair[1]][pair[0]] = inverse_sqrt_two;
    return result;
}

[[nodiscard]] Matrix3d conjugate(
    const Matrix3d& rotation, const Matrix3d& tensor) {
    return multiply(multiply(rotation, tensor), transpose(rotation));
}

[[nodiscard]] double determinant(const Matrix3d& matrix) {
    return matrix.value[0][0] *
            (matrix.value[1][1] * matrix.value[2][2] -
             matrix.value[1][2] * matrix.value[2][1]) -
        matrix.value[0][1] *
            (matrix.value[1][0] * matrix.value[2][2] -
             matrix.value[1][2] * matrix.value[2][0]) +
        matrix.value[0][2] *
            (matrix.value[1][0] * matrix.value[2][1] -
             matrix.value[1][1] * matrix.value[2][0]);
}

[[nodiscard]] double orthogonality_residual(const DenseMatrix& matrix) {
    if (matrix.row_count() != matrix.column_count()) {
        return std::numeric_limits<double>::infinity();
    }
    const auto product = multiply_dense(transpose_dense(matrix), matrix);
    DenseMatrix identity(product.row_count(), product.column_count());
    for (std::size_t index = 0; index < product.row_count(); ++index) {
        identity(index, index) = 1.0;
    }
    return normalized_frobenius_difference(product, identity);
}

} // namespace

DenseMatrix kelvin_rotation(const Matrix3d& proper_rotation) {
    if (!observation::is_proper_rotation(proper_rotation, 1.0e-10)) {
        throw std::invalid_argument("Kelvin map requires a proper rotation");
    }
    DenseMatrix result(6U, 6U);
    for (std::size_t column = 0; column < 6U; ++column) {
        const auto transformed = conjugate(
            proper_rotation, kelvin_basis(column));
        const auto values = kelvin_components(transformed);
        for (std::size_t row = 0; row < 6U; ++row) {
            result(row, column) = values[row];
        }
    }
    return result;
}

std::vector<observation::MechanicalPacket> transform_packet_geometry(
    const std::span<const observation::MechanicalPacket> packets,
    const Matrix3d& proper_rotation, const Vec3d translation_m,
    const double scale) {
    if (!(scale > 0.0) || !std::isfinite(scale) || !finite(translation_m) ||
        !observation::is_proper_rotation(proper_rotation, 1.0e-10)) {
        throw std::invalid_argument("invalid packet similarity transform");
    }
    std::vector<observation::MechanicalPacket> result(
        packets.begin(), packets.end());
    for (auto& packet : result) {
        packet.position_m = scale * multiply(
            proper_rotation, packet.position_m) + translation_m;
        packet.velocity_m_per_s = multiply(
            proper_rotation, packet.velocity_m_per_s);
        if (!finite(packet.position_m) || !finite(packet.velocity_m_per_s)) {
            throw std::overflow_error("packet similarity transform overflow");
        }
    }
    return result;
}

DenseMatrix expected_transformed_operator(
    const DenseMatrix& base, const Matrix3d& proper_rotation,
    const double scale) {
    if (!(scale > 0.0) || !std::isfinite(scale) ||
        base.row_count() % 6U != 0U || base.column_count() % 3U != 0U ||
        base.row_count() / 6U != base.column_count() / 3U) {
        throw std::invalid_argument("invalid Kelvin operator dimensions/scale");
    }
    const std::size_t packet_count = base.row_count() / 6U;
    const auto output = block_diagonal(
        kelvin_rotation(proper_rotation), packet_count);
    const auto input = block_diagonal(
        input_rotation(proper_rotation), packet_count);
    auto result = multiply_dense(
        multiply_dense(output, base), transpose_dense(input));
    for (std::size_t row = 0; row < result.row_count(); ++row) {
        for (std::size_t column = 0; column < result.column_count(); ++column) {
            result(row, column) /= scale;
        }
    }
    return result;
}

BlockNormalization normalize_kelvin_blocks(const DenseMatrix& matrix) {
    if (matrix.row_count() % 6U != 0U) {
        throw std::invalid_argument("Kelvin block normalization requires 6N rows");
    }
    BlockNormalization result{};
    result.normalized = DenseMatrix(matrix.row_count(), matrix.column_count());
    const auto block_count = matrix.row_count() / 6U;
    result.first_invalid_block = block_count;
    result.complete = true;
    result.block_norms.reserve(block_count);
    for (std::size_t block = 0; block < block_count; ++block) {
        std::vector<double> entries;
        entries.reserve(6U * matrix.column_count());
        for (std::size_t local = 0; local < 6U; ++local) {
            for (std::size_t column = 0; column < matrix.column_count(); ++column) {
                entries.push_back(matrix(6U * block + local, column));
            }
        }
        const double norm = stable_l2(entries);
        result.block_norms.push_back(norm);
        if (!(norm > 0.0) || !std::isfinite(norm)) {
            result.complete = false;
            if (result.first_invalid_block == block_count) {
                result.first_invalid_block = block;
            }
            continue;
        }
        for (std::size_t local = 0; local < 6U; ++local) {
            for (std::size_t column = 0; column < matrix.column_count(); ++column) {
                result.normalized(6U * block + local, column) =
                    matrix(6U * block + local, column) / norm;
            }
        }
    }
    return result;
}

double normalized_frobenius_difference(
    const DenseMatrix& actual, const DenseMatrix& reference) {
    if (actual.row_count() != reference.row_count() ||
        actual.column_count() != reference.column_count()) {
        return std::numeric_limits<double>::infinity();
    }
    std::vector<double> difference;
    difference.reserve(actual.entries().size());
    for (std::size_t row = 0; row < actual.row_count(); ++row) {
        for (std::size_t column = 0; column < actual.column_count(); ++column) {
            difference.push_back(actual(row, column) - reference(row, column));
        }
    }
    return stable_l2(difference) /
        std::max(frobenius(reference), std::numeric_limits<double>::min());
}

std::vector<double> singular_values(const DenseMatrix& matrix) {
    const std::size_t rows = matrix.row_count();
    const std::size_t columns = matrix.column_count();
    const bool transpose_input = rows < columns;
    const std::size_t working_rows = transpose_input ? columns : rows;
    const std::size_t dimension = transpose_input ? rows : columns;
    if (dimension == 0U) {
        return {};
    }
    double maximum_entry = 0.0;
    for (const double value : matrix.entries()) {
        if (!std::isfinite(value)) {
            throw std::invalid_argument(
                "singular-spectrum diagnostic requires finite entries");
        }
        maximum_entry = std::max(maximum_entry, std::abs(value));
    }
    if (maximum_entry == 0.0) {
        return std::vector<double>(dimension, 0.0);
    }
    std::vector<long double> work(working_rows * dimension, 0.0L);
    for (std::size_t row = 0; row < working_rows; ++row) {
        for (std::size_t column = 0; column < dimension; ++column) {
            work[row * dimension + column] = static_cast<long double>(
                (transpose_input ? matrix(column, row) : matrix(row, column)) /
                maximum_entry);
        }
    }

    // A deterministic one-sided Jacobi SVD acts on the matrix directly.
    // Forming A^T A first squares the condition number and promotes binary64
    // roundoff in an exact null tail from O(epsilon) to O(sqrt(epsilon)) when
    // its eigenvalues are square-rooted.  That platform-dependent artifact is
    // large enough to masquerade as a covariance failure on implementations
    // where long double has the same precision as double (notably MSVC).
    constexpr std::size_t maximum_sweeps = 256U;
    constexpr long double correlation_factor = 32.0L;
    bool converged = dimension < 2U;
    for (std::size_t sweep = 0; sweep < maximum_sweeps; ++sweep) {
        bool rotated = false;
        for (std::size_t p = 0; p < dimension; ++p) {
            for (std::size_t q = p + 1U; q < dimension; ++q) {
                long double alpha = 0.0L;
                long double beta = 0.0L;
                long double gamma = 0.0L;
                for (std::size_t row = 0; row < working_rows; ++row) {
                    const long double lhs = work[row * dimension + p];
                    const long double rhs = work[row * dimension + q];
                    alpha += lhs * lhs;
                    beta += rhs * rhs;
                    gamma += lhs * rhs;
                }
                if (alpha == 0.0L || beta == 0.0L) {
                    continue;
                }
                const long double threshold = correlation_factor *
                    std::numeric_limits<long double>::epsilon() *
                    std::sqrt(alpha) * std::sqrt(beta);
                if (std::abs(gamma) <= threshold) {
                    continue;
                }
                const long double zeta = (beta - alpha) / (2.0L * gamma);
                const long double tangent = zeta == 0.0L ? 1.0L :
                    std::copysign(1.0L, zeta) /
                        (std::abs(zeta) + std::hypot(1.0L, zeta));
                const long double cosine =
                    1.0L / std::sqrt(1.0L + tangent * tangent);
                const long double sine = cosine * tangent;
                for (std::size_t row = 0; row < working_rows; ++row) {
                    const auto index_p = row * dimension + p;
                    const auto index_q = row * dimension + q;
                    const long double lhs = work[index_p];
                    const long double rhs = work[index_q];
                    work[index_p] = cosine * lhs - sine * rhs;
                    work[index_q] = sine * lhs + cosine * rhs;
                }
                rotated = true;
            }
        }
        if (!rotated) {
            converged = true;
            break;
        }
    }
    if (!converged) {
        throw std::runtime_error(
            "one-sided Jacobi singular-spectrum diagnostic did not converge");
    }

    std::vector<double> result;
    result.reserve(dimension);
    for (std::size_t column = 0; column < dimension; ++column) {
        long double squared_norm = 0.0L;
        for (std::size_t row = 0; row < working_rows; ++row) {
            const long double value = work[row * dimension + column];
            squared_norm += value * value;
        }
        result.push_back(maximum_entry *
            static_cast<double>(std::sqrt(squared_norm)));
    }
    std::ranges::sort(result, std::greater<>{});
    return result;
}

double normalized_spectrum_difference(
    const std::span<const double> actual,
    const std::span<const double> reference, const double actual_scale) {
    if (actual.size() != reference.size() || !std::isfinite(actual_scale)) {
        return std::numeric_limits<double>::infinity();
    }
    const double reference_max = reference.empty() ? 0.0 :
        *std::ranges::max_element(reference);
    const double denominator = std::max(
        reference_max, std::numeric_limits<double>::min());
    double maximum = 0.0;
    for (std::size_t index = 0; index < actual.size(); ++index) {
        maximum = std::max(maximum,
            std::abs(actual_scale * actual[index] - reference[index]) /
                denominator);
    }
    return maximum;
}

OrthogonalityDiagnostics diagnose_orthogonality(
    const Matrix3d& proper_rotation, const DenseMatrix& kelvin) {
    const auto q = input_rotation(proper_rotation);
    return {orthogonality_residual(q),
        std::abs(determinant(proper_rotation) - 1.0),
        orthogonality_residual(kelvin)};
}

RowNormalizationCounterexample kelvin_row_normalization_counterexample(
    const Matrix3d& proper_rotation) {
    const auto kelvin = kelvin_rotation(proper_rotation);
    DenseMatrix base(6U, 6U);
    for (std::size_t index = 0; index < 6U; ++index) {
        base(index, index) = static_cast<double>(index + 1U);
    }
    const auto transformed = multiply_dense(kelvin, base);
    const auto expected = multiply_dense(kelvin, base);
    const auto base_spectrum = singular_values(base);
    const auto transformed_spectrum = singular_values(transformed);
    const auto base_rows = observation::normalize_operator_rows(base);
    const auto transformed_rows =
        observation::normalize_operator_rows(transformed);
    RowNormalizationCounterexample result{};
    result.raw_spectrum_delta = normalized_spectrum_difference(
        transformed_spectrum, base_spectrum);
    result.raw_transform_residual = normalized_frobenius_difference(
        transformed, expected);
    result.row_normalizations_complete =
        base_rows.complete && transformed_rows.complete;
    if (result.row_normalizations_complete) {
        result.row_normalized_spectrum_delta =
            normalized_spectrum_difference(
                singular_values(transformed_rows.normalized),
                singular_values(base_rows.normalized));
    } else {
        result.row_normalized_spectrum_delta =
            std::numeric_limits<double>::infinity();
    }
    return result;
}

} // namespace mls::experimental::kelvin_covariance_audit
