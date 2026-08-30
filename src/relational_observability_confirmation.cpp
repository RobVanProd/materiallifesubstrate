#include "mls/relational_observability_confirmation.hpp"

#include "mls/kelvin_covariance_audit.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <limits>
#include <map>
#include <numeric>
#include <stdexcept>
#include <vector>

namespace mls::experimental::relational_observability_confirmation {
namespace {

using observation::BondRelation;
using observation::DenseMatrix;
using observation::MechanicalPacket;

[[nodiscard]] double stable_l2(std::span<const double> values) {
    double scale = 0.0;
    double sum = 1.0;
    bool nonzero = false;
    for (const double value : values) {
        const double magnitude = std::abs(value);
        if (!std::isfinite(magnitude)) {
            return std::numeric_limits<double>::infinity();
        }
        if (magnitude == 0.0) {
            continue;
        }
        nonzero = true;
        if (scale < magnitude) {
            const double ratio = scale / magnitude;
            sum = 1.0 + sum * ratio * ratio;
            scale = magnitude;
        } else {
            const double ratio = magnitude / scale;
            sum += ratio * ratio;
        }
    }
    return nonzero ? scale * std::sqrt(sum) : 0.0;
}

[[nodiscard]] double frobenius_norm(const DenseMatrix& matrix) {
    return stable_l2(matrix.entries());
}

[[nodiscard]] std::vector<double> matrix_column(
    const DenseMatrix& matrix, const std::size_t column) {
    std::vector<double> result(matrix.row_count(), 0.0);
    for (std::size_t row = 0; row < matrix.row_count(); ++row) {
        result[row] = matrix(row, column);
    }
    return result;
}

[[nodiscard]] double normalized_matrix_vector_residual(
    const DenseMatrix& matrix, std::span<const double> vector) {
    if (matrix.column_count() != vector.size()) {
        return std::numeric_limits<double>::infinity();
    }
    std::vector<double> product(matrix.row_count(), 0.0);
    for (std::size_t row = 0; row < matrix.row_count(); ++row) {
        long double sum = 0.0L;
        for (std::size_t column = 0; column < matrix.column_count(); ++column) {
            sum += static_cast<long double>(matrix(row, column)) *
                static_cast<long double>(vector[column]);
        }
        product[row] = static_cast<double>(sum);
    }
    return stable_l2(product) /
        std::max(frobenius_norm(matrix) * stable_l2(vector),
                 std::numeric_limits<double>::min());
}

[[nodiscard]] double normalized_matrix_matrix_residual(
    const DenseMatrix& matrix, const DenseMatrix& vectors) {
    if (matrix.column_count() != vectors.row_count()) {
        return std::numeric_limits<double>::infinity();
    }
    std::vector<double> product;
    product.reserve(matrix.row_count() * vectors.column_count());
    for (std::size_t row = 0; row < matrix.row_count(); ++row) {
        for (std::size_t column = 0; column < vectors.column_count(); ++column) {
            long double sum = 0.0L;
            for (std::size_t inner = 0; inner < matrix.column_count(); ++inner) {
                sum += static_cast<long double>(matrix(row, inner)) *
                    static_cast<long double>(vectors(inner, column));
            }
            product.push_back(static_cast<double>(sum));
        }
    }
    return stable_l2(product) /
        std::max(frobenius_norm(matrix) * frobenius_norm(vectors),
                 std::numeric_limits<double>::min());
}

[[nodiscard]] double projection_norm(
    std::span<const double> vector, const DenseMatrix& orthonormal_basis) {
    if (vector.size() != orthonormal_basis.row_count()) {
        return std::numeric_limits<double>::infinity();
    }
    std::vector<double> coefficients(orthonormal_basis.column_count(), 0.0);
    for (std::size_t column = 0; column < orthonormal_basis.column_count();
         ++column) {
        long double value = 0.0L;
        for (std::size_t row = 0; row < vector.size(); ++row) {
            value += static_cast<long double>(vector[row]) *
                static_cast<long double>(orthonormal_basis(row, column));
        }
        coefficients[column] = static_cast<double>(value);
    }
    return stable_l2(coefficients) /
        std::max(stable_l2(vector), std::numeric_limits<double>::min());
}

[[nodiscard]] DenseMatrix orthonormalize_columns(
    const DenseMatrix& input, const double threshold) {
    std::vector<std::vector<double>> accepted;
    for (std::size_t column = 0U; column < input.column_count(); ++column) {
        auto candidate = matrix_column(input, column);
        for (int pass = 0; pass < 2; ++pass) {
            for (const auto& basis : accepted) {
                long double coefficient = 0.0L;
                for (std::size_t row = 0U; row < candidate.size(); ++row) {
                    coefficient += static_cast<long double>(candidate[row]) *
                        static_cast<long double>(basis[row]);
                }
                for (std::size_t row = 0U; row < candidate.size(); ++row) {
                    candidate[row] -= static_cast<double>(coefficient) * basis[row];
                }
            }
        }
        const double norm = stable_l2(candidate);
        if (norm <= threshold || !std::isfinite(norm)) {
            continue;
        }
        for (double& value : candidate) {
            value /= norm;
        }
        // Deterministic sign convention.
        const auto leading = std::ranges::find_if(candidate, [&](const double value) {
            return std::abs(value) > threshold;
        });
        if (leading != candidate.end() && *leading < 0.0) {
            for (double& value : candidate) {
                value = -value;
            }
        }
        accepted.push_back(std::move(candidate));
    }
    DenseMatrix result(input.row_count(), accepted.size());
    for (std::size_t column = 0U; column < accepted.size(); ++column) {
        for (std::size_t row = 0U; row < input.row_count(); ++row) {
            result(row, column) = accepted[column][row];
        }
    }
    return result;
}

[[nodiscard]] double normalized_cross_orthogonality(
    const DenseMatrix& first, const DenseMatrix& second) {
    if (first.row_count() != second.row_count()) {
        return std::numeric_limits<double>::infinity();
    }
    if (first.column_count() == 0U || second.column_count() == 0U) {
        return 0.0;
    }
    std::vector<double> products;
    products.reserve(first.column_count() * second.column_count());
    for (std::size_t left = 0U; left < first.column_count(); ++left) {
        for (std::size_t right = 0U; right < second.column_count(); ++right) {
            long double sum = 0.0L;
            for (std::size_t row = 0U; row < first.row_count(); ++row) {
                sum += static_cast<long double>(first(row, left)) *
                    static_cast<long double>(second(row, right));
            }
            products.push_back(static_cast<double>(sum));
        }
    }
    return stable_l2(products) /
        std::sqrt(static_cast<double>(
            first.column_count() * second.column_count()));
}

[[nodiscard]] std::uint32_t modular_power(
    std::uint32_t base, std::uint64_t exponent, const std::uint32_t prime) {
    std::uint64_t result = 1U;
    std::uint64_t factor = base;
    while (exponent != 0U) {
        if ((exponent & 1U) != 0U) {
            result = (result * factor) % prime;
        }
        factor = (factor * factor) % prime;
        exponent >>= 1U;
    }
    return static_cast<std::uint32_t>(result);
}

[[nodiscard]] std::uint32_t modular_inverse(
    const std::uint32_t value, const std::uint32_t prime) {
    if (value == 0U) {
        throw std::invalid_argument("zero has no modular inverse");
    }
    return modular_power(value, static_cast<std::uint64_t>(prime) - 2U, prime);
}

[[nodiscard]] std::uint32_t dyadic_double_mod(
    const double value, const std::uint32_t prime) {
    if (!std::isfinite(value)) {
        throw std::invalid_argument("exact modular rank requires finite coordinates");
    }
    if (value == 0.0) {
        return 0U;
    }
    const std::uint64_t bits = std::bit_cast<std::uint64_t>(value);
    const bool negative = (bits >> 63U) != 0U;
    const auto exponent_bits = static_cast<unsigned>((bits >> 52U) & 0x7ffU);
    const std::uint64_t fraction = bits & UINT64_C(0x000fffffffffffff);
    const std::uint64_t significand = exponent_bits == 0U
        ? fraction
        : (UINT64_C(1) << 52U) | fraction;
    const int exponent = exponent_bits == 0U
        ? -1074
        : static_cast<int>(exponent_bits) - 1023 - 52;
    std::uint64_t residue = significand % prime;
    if (exponent >= 0) {
        residue = (residue * modular_power(
            2U, static_cast<std::uint64_t>(exponent), prime)) % prime;
    } else {
        residue = (residue * modular_power(
            modular_inverse(2U, prime),
            static_cast<std::uint64_t>(-exponent), prime)) % prime;
    }
    if (negative && residue != 0U) {
        residue = prime - residue;
    }
    return static_cast<std::uint32_t>(residue);
}

[[nodiscard]] std::uint32_t modular_subtract(
    const std::uint32_t left, const std::uint32_t right,
    const std::uint32_t prime) noexcept {
    return left >= right ? left - right : prime - (right - left);
}

[[nodiscard]] std::size_t modular_rank(
    std::vector<std::uint32_t> matrix, const std::size_t rows,
    const std::size_t columns, const std::uint32_t prime) {
    std::size_t rank = 0U;
    for (std::size_t column = 0U; column < columns && rank < rows; ++column) {
        std::size_t pivot = rank;
        while (pivot < rows && matrix[pivot * columns + column] == 0U) {
            ++pivot;
        }
        if (pivot == rows) {
            continue;
        }
        if (pivot != rank) {
            for (std::size_t entry = column; entry < columns; ++entry) {
                std::swap(matrix[rank * columns + entry],
                          matrix[pivot * columns + entry]);
            }
        }
        const std::uint32_t inverse = modular_inverse(
            matrix[rank * columns + column], prime);
        for (std::size_t entry = column; entry < columns; ++entry) {
            matrix[rank * columns + entry] = static_cast<std::uint32_t>(
                (static_cast<std::uint64_t>(
                    matrix[rank * columns + entry]) * inverse) % prime);
        }
        for (std::size_t row = rank + 1U; row < rows; ++row) {
            const std::uint32_t factor = matrix[row * columns + column];
            if (factor == 0U) {
                continue;
            }
            for (std::size_t entry = column; entry < columns; ++entry) {
                const std::uint32_t product = static_cast<std::uint32_t>(
                    (static_cast<std::uint64_t>(factor) *
                     matrix[rank * columns + entry]) % prime);
                matrix[row * columns + entry] = modular_subtract(
                    matrix[row * columns + entry], product, prime);
            }
        }
        ++rank;
    }
    return rank;
}

[[nodiscard]] std::vector<MechanicalPacket> canonical_packets(
    std::span<const MechanicalPacket> packets) {
    std::vector<MechanicalPacket> result(packets.begin(), packets.end());
    std::ranges::sort(result, {}, &MechanicalPacket::id);
    if (std::adjacent_find(result.begin(), result.end(), [](const auto& lhs,
                                                            const auto& rhs) {
            return lhs.id == rhs.id;
        }) != result.end()) {
        throw std::invalid_argument("duplicate packet ID");
    }
    return result;
}

} // namespace

std::string_view classification_name(
    const SingularClassification classification) noexcept {
    switch (classification) {
    case SingularClassification::accepted_nonzero:
        return "accepted_nonzero";
    case SingularClassification::ambiguous:
        return "ambiguous";
    case SingularClassification::resolved_zero:
        return "resolved_zero";
    }
    return "unknown";
}

ModularRankDiagnostic three_prime_modular_rigidity_rank(
    const std::span<const MechanicalPacket> packets,
    const std::span<const BondRelation> relations) {
    // The inherited builder performs the authoritative topology and geometry
    // validation before an exact rank is reported.
    static_cast<void>(observation::build_bond_rigidity_operator(
        packets, relations));
    const auto canonical = canonical_packets(packets);
    std::map<std::uint64_t, std::size_t> index_by_id;
    for (std::size_t index = 0U; index < canonical.size(); ++index) {
        index_by_id.emplace(canonical[index].id, index);
    }
    constexpr std::array<std::uint32_t, 3> primes{
        998244353U, 1000000007U, 1000000009U};
    ModularRankDiagnostic result{};
    result.primes.assign(primes.begin(), primes.end());
    const std::size_t columns = 3U * canonical.size();
    for (const std::uint32_t prime : primes) {
        std::vector<std::uint32_t> matrix(relations.size() * columns, 0U);
        for (std::size_t row = 0U; row < relations.size(); ++row) {
            const auto first_index = index_by_id.at(relations[row].first_id);
            const auto second_index = index_by_id.at(relations[row].second_id);
            const auto& first = canonical[first_index].position_m;
            const auto& second = canonical[second_index].position_m;
            const std::array<double, 3> first_values{first.x, first.y, first.z};
            const std::array<double, 3> second_values{second.x, second.y, second.z};
            for (std::size_t axis = 0U; axis < 3U; ++axis) {
                const std::uint32_t difference = modular_subtract(
                    dyadic_double_mod(second_values[axis], prime),
                    dyadic_double_mod(first_values[axis], prime), prime);
                matrix[row * columns + 3U * second_index + axis] = difference;
                matrix[row * columns + 3U * first_index + axis] =
                    difference == 0U ? 0U : prime - difference;
            }
        }
        result.ranks.push_back(modular_rank(
            std::move(matrix), relations.size(), columns, prime));
    }
    result.unanimous = !result.ranks.empty() &&
        std::ranges::all_of(result.ranks, [&](const std::size_t value) {
            return value == result.ranks.front();
        });
    result.rank = result.unanimous ? result.ranks.front() : 0U;
    return result;
}

RawObservabilityDiagnostic analyze_raw_central_rigidity(
    const std::span<const MechanicalPacket> packets,
    const std::span<const BondRelation> relations,
    const RawSpectrumPolicy& policy) {
    if (!(policy.rank_roundoff_factor > 0.0) ||
        !(policy.ambiguity_factor > 1.0) ||
        !(policy.residual_factor > 0.0) ||
        !(policy.row_norm_factor > 0.0) ||
        !std::isfinite(policy.rank_roundoff_factor) ||
        !std::isfinite(policy.ambiguity_factor) ||
        !std::isfinite(policy.residual_factor) ||
        !std::isfinite(policy.row_norm_factor)) {
        throw std::invalid_argument("invalid raw observability policy");
    }
    const auto bonds = observation::build_bond_rigidity_operator(
        packets, relations);
    const DenseMatrix& matrix = bonds.linearized.matrix;
    RawObservabilityDiagnostic result{};
    result.row_count = matrix.row_count();
    result.column_count = matrix.column_count();
    result.dimension_scale = std::max<std::size_t>(
        6U, std::max(result.row_count, result.column_count));
    const double epsilon = std::numeric_limits<double>::epsilon();
    result.residual_tolerance = policy.residual_factor *
        static_cast<double>(result.dimension_scale) * epsilon;
    // The wire value is relative because its neighboring field is a relative
    // error.  This is algebraically the preregistered absolute gate
    // 64*eps*sqrt(2).
    result.row_norm_tolerance = policy.row_norm_factor * epsilon;

    const double expected_row_norm = std::sqrt(2.0);
    result.row_norms.reserve(result.row_count);
    for (std::size_t row = 0U; row < result.row_count; ++row) {
        std::vector<double> entries(result.column_count, 0.0);
        for (std::size_t column = 0U; column < result.column_count; ++column) {
            entries[column] = matrix(row, column);
        }
        const double norm = stable_l2(entries);
        result.row_norms.push_back(norm);
        result.maximum_row_norm_relative_error = std::max(
            result.maximum_row_norm_relative_error,
            std::abs(norm - expected_row_norm) / expected_row_norm);
    }
    result.row_norms_pass = std::ranges::all_of(
        result.row_norms, [&](const double value) {
            return std::isfinite(value) &&
                std::abs(value - expected_row_norm) / expected_row_norm <=
                    result.row_norm_tolerance;
        });

    observation::RankPolicy rank_policy{};
    rank_policy.roundoff_safety_factor = policy.rank_roundoff_factor;
    rank_policy.ambiguity_factor = policy.ambiguity_factor;
    rank_policy.residual_safety_factor = policy.residual_factor;
    result.cpqr = observation::diagnose_rank_and_nullspace(matrix, rank_policy);
    result.cpqr_rank = result.cpqr.rank;
    result.cpqr_threshold = result.cpqr.threshold;
    result.normalized_null_residual = result.cpqr.normalized_null_residual;

    const auto direct = kelvin_covariance_audit::singular_values(matrix);
    result.sigma_max = direct.empty() ? 0.0 : direct.front();
    result.svd_threshold = policy.rank_roundoff_factor *
        static_cast<double>(result.dimension_scale) * epsilon *
        std::max(result.sigma_max, std::numeric_limits<double>::min());
    result.direct_svd_unambiguous = true;
    result.spectrum.reserve(result.column_count);
    double maximum_resolved_zero = 0.0;
    for (std::size_t index = 0U; index < direct.size(); ++index) {
        SingularClassification classification = SingularClassification::ambiguous;
        if (direct[index] > policy.ambiguity_factor * result.svd_threshold) {
            classification = SingularClassification::accepted_nonzero;
            ++result.svd_rank;
            result.sigma_min_nonzero = direct[index];
        } else if (direct[index] <
                   result.svd_threshold / policy.ambiguity_factor) {
            classification = SingularClassification::resolved_zero;
            maximum_resolved_zero = std::max(maximum_resolved_zero, direct[index]);
        } else {
            result.direct_svd_unambiguous = false;
        }
        result.spectrum.push_back({index, direct[index], classification});
    }
    for (std::size_t index = direct.size(); index < result.column_count; ++index) {
        result.spectrum.push_back(
            {index, 0.0, SingularClassification::resolved_zero});
    }
    if (result.sigma_max > 0.0) {
        result.mu = result.sigma_min_nonzero / result.sigma_max;
    }
    result.nonzero_threshold_separation = result.sigma_min_nonzero > 0.0
        ? result.sigma_min_nonzero /
              (policy.ambiguity_factor * result.svd_threshold)
        : 0.0;
    result.null_threshold_separation = maximum_resolved_zero == 0.0
        ? std::numeric_limits<double>::infinity()
        : (result.svd_threshold / policy.ambiguity_factor) /
              maximum_resolved_zero;

    result.modular_rank = three_prime_modular_rigidity_rank(packets, relations);
    result.modular_rank_value = result.modular_rank.rank;
    result.rank_paths_agree = result.modular_rank.unanimous &&
        result.cpqr_rank == result.svd_rank &&
        result.cpqr_rank == result.modular_rank_value;
    result.nullity = result.column_count - result.modular_rank_value;

    result.rigid = observation::build_rigid_motion_subspace(packets);
    result.realized_rigid_rank = result.rigid.rank;
    result.normalized_rigid_residual = normalized_matrix_matrix_residual(
        matrix, result.rigid.orthonormal_basis);
    result.rigid_subspace_in_kernel =
        result.normalized_rigid_residual <= result.residual_tolerance;
    if (result.rigid_subspace_in_kernel &&
        result.nullity >= result.realized_rigid_rank) {
        result.nonrigid_nullity =
            result.nullity - result.realized_rigid_rank;
    }
    result.kernel_equals_rigid_subspace = result.rigid_subspace_in_kernel &&
        result.nonrigid_nullity == 0U;

    DenseMatrix projected_kernel(
        result.cpqr.nullspace_basis.row_count(),
        result.cpqr.nullspace_basis.column_count());
    for (std::size_t column = 0U;
         column < result.cpqr.nullspace_basis.column_count(); ++column) {
        auto projected = matrix_column(result.cpqr.nullspace_basis, column);
        for (std::size_t rigid_column = 0U;
             rigid_column < result.rigid.orthonormal_basis.column_count();
             ++rigid_column) {
            long double coefficient = 0.0L;
            for (std::size_t row = 0U; row < projected.size(); ++row) {
                coefficient += static_cast<long double>(
                    result.rigid.orthonormal_basis(row, rigid_column)) *
                    static_cast<long double>(projected[row]);
            }
            for (std::size_t row = 0U; row < projected.size(); ++row) {
                projected[row] -= static_cast<double>(coefficient) *
                    result.rigid.orthonormal_basis(row, rigid_column);
            }
        }
        for (std::size_t row = 0U; row < projected.size(); ++row) {
            projected_kernel(row, column) = projected[row];
        }
    }
    result.nonrigid_nullspace_basis = orthonormalize_columns(
        projected_kernel, result.residual_tolerance);
    result.nonrigid_basis_complete =
        result.nonrigid_nullspace_basis.column_count() ==
        result.nonrigid_nullity;
    result.normalized_nonrigid_residual = normalized_matrix_matrix_residual(
        matrix, result.nonrigid_nullspace_basis);
    result.rigid_orthogonality_residual = normalized_cross_orthogonality(
        result.rigid.orthonormal_basis,
        result.nonrigid_nullspace_basis);

    result.all_null_modes_accepted = result.cpqr.basis_complete;
    for (std::size_t mode = 0U;
         mode < result.cpqr.nullspace_basis.column_count(); ++mode) {
        const auto vector = matrix_column(result.cpqr.nullspace_basis, mode);
        const double residual = normalized_matrix_vector_residual(matrix, vector);
        const double rigid_projection = projection_norm(
            vector, result.rigid.orthonormal_basis);
        const double orthogonal = std::sqrt(std::max(
            0.0, 1.0 - rigid_projection * rigid_projection));
        const bool accepted = std::isfinite(residual) &&
            residual <= result.residual_tolerance;
        result.all_null_modes_accepted =
            result.all_null_modes_accepted && accepted;
        result.null_modes.push_back(
            {mode, residual, rigid_projection, orthogonal, accepted});
    }

    const bool cpqr_usable = result.cpqr.status == observation::RankStatus::analyzed;
    if (!result.row_norms_pass || !result.modular_rank.unanimous ||
        !result.rank_paths_agree || !result.rigid_subspace_in_kernel ||
        !result.all_null_modes_accepted || !result.nonrigid_basis_complete ||
        result.normalized_nonrigid_residual > result.residual_tolerance ||
        result.rigid_orthogonality_residual > result.residual_tolerance) {
        result.status = observation::RankStatus::numerical_failure;
    } else if (!result.direct_svd_unambiguous ||
               result.cpqr.status == observation::RankStatus::ambiguous) {
        result.status = observation::RankStatus::ambiguous;
    } else if (!cpqr_usable) {
        result.status = result.cpqr.status;
    } else {
        result.status = observation::RankStatus::analyzed;
    }
    return result;
}

double normalized_spectrum_difference(
    const std::span<const SingularEntry> actual,
    const std::span<const SingularEntry> reference) {
    if (actual.size() != reference.size()) {
        return std::numeric_limits<double>::infinity();
    }
    double denominator = std::numeric_limits<double>::min();
    for (const auto& entry : reference) {
        denominator = std::max(denominator, entry.value);
    }
    double difference = 0.0;
    for (std::size_t index = 0U; index < actual.size(); ++index) {
        difference = std::max(
            difference, std::abs(actual[index].value - reference[index].value) /
                            denominator);
    }
    return difference;
}

} // namespace mls::experimental::relational_observability_confirmation
