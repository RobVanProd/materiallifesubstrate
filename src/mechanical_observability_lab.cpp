#include "mls/mechanical_observability_lab.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <limits>
#include <map>
#include <numeric>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>

namespace mls::experimental::mechanical_observability {
namespace {

[[nodiscard]] bool finite(Vec3d value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) &&
        std::isfinite(value.z);
}

[[nodiscard]] bool finite(const Matrix3d& value) noexcept {
    return std::ranges::all_of(value.value, [](const auto& row) {
        return std::ranges::all_of(row, [](double entry) {
            return std::isfinite(entry);
        });
    });
}

[[nodiscard]] double component(Vec3d value, std::size_t index) noexcept {
    if (index == 0U) {
        return value.x;
    }
    if (index == 1U) {
        return value.y;
    }
    return value.z;
}

[[nodiscard]] double stable_vector_norm(Vec3d value) noexcept {
    const auto scale = std::max({std::abs(value.x), std::abs(value.y),
                                 std::abs(value.z)});
    if (scale == 0.0) {
        return 0.0;
    }
    if (!std::isfinite(scale)) {
        return std::numeric_limits<double>::infinity();
    }
    const auto x = value.x / scale;
    const auto y = value.y / scale;
    const auto z = value.z / scale;
    return scale * std::sqrt(x * x + y * y + z * z);
}

[[nodiscard]] double stable_l2(std::span<const double> values) noexcept {
    double scale = 0.0;
    long double scaled_squared = 0.0L;
    for (const auto value : values) {
        const auto magnitude = std::abs(value);
        if (!std::isfinite(magnitude)) {
            return std::numeric_limits<double>::infinity();
        }
        if (magnitude == 0.0) {
            continue;
        }
        if (scale < magnitude) {
            const auto ratio = scale / magnitude;
            scaled_squared = 1.0L + scaled_squared * ratio * ratio;
            scale = magnitude;
        } else {
            const auto ratio = magnitude / scale;
            scaled_squared += static_cast<long double>(ratio) * ratio;
        }
    }
    return scale == 0.0
        ? 0.0
        : scale * std::sqrt(static_cast<double>(scaled_squared));
}

[[nodiscard]] double matrix_frobenius(const DenseMatrix& matrix) noexcept {
    return stable_l2(matrix.entries());
}

[[nodiscard]] std::vector<MechanicalPacket> canonical_packets(
    std::span<const MechanicalPacket> packets) {
    std::vector<MechanicalPacket> result(packets.begin(), packets.end());
    for (const auto& packet : result) {
        if (packet.id == 0U || packet.mass_quanta <= 0 ||
            !finite(packet.position_m) ||
            !finite(packet.velocity_m_per_s)) {
            throw std::invalid_argument(
                "packet IDs/masses must be positive and state finite");
        }
    }
    std::ranges::sort(result, {}, &MechanicalPacket::id);
    for (std::size_t index = 1; index < result.size(); ++index) {
        if (result[index - 1U].id == result[index].id) {
            throw std::invalid_argument("packet IDs must be unique");
        }
    }
    return result;
}

[[nodiscard]] std::map<std::uint64_t, std::size_t> packet_lookup(
    std::span<const MechanicalPacket> packets) {
    std::map<std::uint64_t, std::size_t> result;
    for (std::size_t index = 0; index < packets.size(); ++index) {
        result.emplace(packets[index].id, index);
    }
    return result;
}

[[nodiscard]] std::vector<std::uint64_t> packet_ids(
    std::span<const MechanicalPacket> packets) {
    std::vector<std::uint64_t> result;
    result.reserve(packets.size());
    for (const auto& packet : packets) {
        result.push_back(packet.id);
    }
    return result;
}

[[nodiscard]] std::size_t checked_product(
    std::size_t value, std::size_t multiplier,
    std::string_view description) {
    if (multiplier != 0U &&
        value > std::numeric_limits<std::size_t>::max() / multiplier) {
        throw std::length_error(std::string(description) + " dimension overflow");
    }
    return value * multiplier;
}

[[nodiscard]] std::size_t checked_sum(
    std::size_t first, std::size_t second,
    std::string_view description) {
    if (first > std::numeric_limits<std::size_t>::max() - second) {
        throw std::length_error(std::string(description) + " dimension overflow");
    }
    return first + second;
}

[[nodiscard]] bool inside_support(
    Vec3d offset_m, double support_radius_m, double& squared_ratio) noexcept {
    const auto scale = std::max({std::abs(offset_m.x), std::abs(offset_m.y),
                                 std::abs(offset_m.z), support_radius_m});
    if (!(scale > 0.0) || !std::isfinite(scale)) {
        return false;
    }
    const auto x = offset_m.x / scale;
    const auto y = offset_m.y / scale;
    const auto z = offset_m.z / scale;
    const auto radius = support_radius_m / scale;
    const auto distance_squared = x * x + y * y + z * z;
    const auto radius_squared = radius * radius;
    if (!std::isfinite(distance_squared) || !std::isfinite(radius_squared) ||
        !(distance_squared > 0.0) || !(distance_squared < radius_squared)) {
        return false;
    }
    squared_ratio = distance_squared / radius_squared;
    return std::isfinite(squared_ratio) && squared_ratio >= 0.0 &&
        squared_ratio < 1.0;
}

[[nodiscard]] Matrix3d scaled_matrix(
    const Matrix3d& matrix, double scalar) noexcept {
    Matrix3d result{};
    for (std::size_t row = 0; row < 3U; ++row) {
        for (std::size_t column = 0; column < 3U; ++column) {
            result.value[row][column] = matrix.value[row][column] * scalar;
        }
    }
    return result;
}

void add_scaled_outer(
    Matrix3d& matrix, double scale, Vec3d lhs, Vec3d rhs) noexcept {
    for (std::size_t row = 0; row < 3U; ++row) {
        for (std::size_t column = 0; column < 3U; ++column) {
            matrix.value[row][column] +=
                scale * component(lhs, row) * component(rhs, column);
        }
    }
}

[[nodiscard]] std::array<double, 3> symmetric_eigenvalues(
    const Matrix3d& matrix) noexcept {
    auto work = matrix.value;
    for (std::size_t sweep = 0; sweep < 32U; ++sweep) {
        std::size_t p = 0U;
        std::size_t q = 1U;
        auto largest = std::abs(work[p][q]);
        for (const auto& [candidate_p, candidate_q] :
             {std::pair{0U, 2U}, std::pair{1U, 2U}}) {
            const auto magnitude = std::abs(work[candidate_p][candidate_q]);
            if (magnitude > largest) {
                largest = magnitude;
                p = candidate_p;
                q = candidate_q;
            }
        }
        const auto diagonal_scale = std::max(
            {std::abs(work[0][0]), std::abs(work[1][1]),
             std::abs(work[2][2]), std::numeric_limits<double>::min()});
        if (largest <= 16.0 * std::numeric_limits<double>::epsilon() *
                           diagonal_scale) {
            break;
        }
        const auto angle = 0.5 * std::atan2(
            2.0 * work[p][q], work[q][q] - work[p][p]);
        const auto cosine = std::cos(angle);
        const auto sine = std::sin(angle);
        const auto app = work[p][p];
        const auto aqq = work[q][q];
        const auto apq = work[p][q];
        work[p][p] = cosine * cosine * app - 2.0 * sine * cosine * apq +
            sine * sine * aqq;
        work[q][q] = sine * sine * app + 2.0 * sine * cosine * apq +
            cosine * cosine * aqq;
        work[p][q] = 0.0;
        work[q][p] = 0.0;
        for (std::size_t index = 0; index < 3U; ++index) {
            if (index == p || index == q) {
                continue;
            }
            const auto aip = work[index][p];
            const auto aiq = work[index][q];
            work[index][p] = cosine * aip - sine * aiq;
            work[p][index] = work[index][p];
            work[index][q] = sine * aip + cosine * aiq;
            work[q][index] = work[index][q];
        }
    }
    std::array result{work[0][0], work[1][1], work[2][2]};
    std::ranges::sort(result);
    return result;
}

[[nodiscard]] bool inverse_symmetric_positive(
    const Matrix3d& matrix, Matrix3d& inverse) noexcept {
    double scale = 0.0;
    for (const auto& row : matrix.value) {
        for (const auto entry : row) {
            scale = std::max(scale, std::abs(entry));
        }
    }
    if (!(scale > 0.0) || !std::isfinite(scale)) {
        return false;
    }
    const auto a = scaled_matrix(matrix, 1.0 / scale).value;
    const auto determinant =
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) -
        a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) +
        a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]);
    if (!(determinant > 0.0) || !std::isfinite(determinant)) {
        return false;
    }
    inverse.value[0][0] = a[1][1] * a[2][2] - a[1][2] * a[2][1];
    inverse.value[0][1] = a[0][2] * a[2][1] - a[0][1] * a[2][2];
    inverse.value[0][2] = a[0][1] * a[1][2] - a[0][2] * a[1][1];
    inverse.value[1][0] = a[1][2] * a[2][0] - a[1][0] * a[2][2];
    inverse.value[1][1] = a[0][0] * a[2][2] - a[0][2] * a[2][0];
    inverse.value[1][2] = a[0][2] * a[1][0] - a[0][0] * a[1][2];
    inverse.value[2][0] = a[1][0] * a[2][1] - a[1][1] * a[2][0];
    inverse.value[2][1] = a[0][1] * a[2][0] - a[0][0] * a[2][1];
    inverse.value[2][2] = a[0][0] * a[1][1] - a[0][1] * a[1][0];
    inverse = scaled_matrix(inverse, 1.0 / (determinant * scale));
    return finite(inverse);
}

[[nodiscard]] double matrix3_frobenius(const Matrix3d& matrix) noexcept {
    std::array<double, 9> entries{};
    std::size_t index = 0U;
    for (const auto& row : matrix.value) {
        for (const auto value : row) {
            entries[index++] = value;
        }
    }
    return stable_l2(entries);
}

[[nodiscard]] double inverse_product_residual(
    const Matrix3d& matrix, const Matrix3d& inverse) noexcept {
    Matrix3d residual{};
    for (std::size_t row = 0U; row < 3U; ++row) {
        for (std::size_t column = 0U; column < 3U; ++column) {
            long double value = 0.0L;
            for (std::size_t inner = 0U; inner < 3U; ++inner) {
                value += static_cast<long double>(matrix.value[row][inner]) *
                    inverse.value[inner][column];
            }
            if (row == column) {
                value -= 1.0L;
            }
            residual.value[row][column] = static_cast<double>(value);
        }
    }
    const auto numerator = matrix3_frobenius(residual);
    const auto denominator = std::max(
        1.0, matrix3_frobenius(matrix) * matrix3_frobenius(inverse));
    if (!std::isfinite(numerator) || !std::isfinite(denominator) ||
        !(denominator > 0.0)) {
        return std::numeric_limits<double>::infinity();
    }
    return numerator / denominator;
}

[[nodiscard]] double long_double_triple(Vec3d a, Vec3d b, Vec3d c) {
    const auto value =
        static_cast<long double>(a.x) *
            (static_cast<long double>(b.y) * c.z -
             static_cast<long double>(b.z) * c.y) -
        static_cast<long double>(a.y) *
            (static_cast<long double>(b.x) * c.z -
             static_cast<long double>(b.z) * c.x) +
        static_cast<long double>(a.z) *
            (static_cast<long double>(b.x) * c.y -
             static_cast<long double>(b.y) * c.x);
    const auto converted = static_cast<double>(value);
    if (!std::isfinite(converted)) {
        throw std::overflow_error("oriented-volume arithmetic overflow");
    }
    return converted;
}

[[nodiscard]] Vec3d checked_cross(Vec3d lhs, Vec3d rhs) {
    const std::array<long double, 3> value{
        static_cast<long double>(lhs.y) * rhs.z -
            static_cast<long double>(lhs.z) * rhs.y,
        static_cast<long double>(lhs.z) * rhs.x -
            static_cast<long double>(lhs.x) * rhs.z,
        static_cast<long double>(lhs.x) * rhs.y -
            static_cast<long double>(lhs.y) * rhs.x,
    };
    const Vec3d result{static_cast<double>(value[0]),
                       static_cast<double>(value[1]),
                       static_cast<double>(value[2])};
    if (!finite(result)) {
        throw std::overflow_error("relation derivative overflow");
    }
    return result;
}

[[nodiscard]] DenseMatrix multiply_dense(
    const DenseMatrix& lhs, const DenseMatrix& rhs) {
    if (lhs.column_count() != rhs.row_count()) {
        throw std::invalid_argument("dense matrix dimensions do not compose");
    }
    DenseMatrix result(lhs.row_count(), rhs.column_count());
    for (std::size_t row = 0; row < lhs.row_count(); ++row) {
        for (std::size_t column = 0; column < rhs.column_count(); ++column) {
            long double sum = 0.0L;
            for (std::size_t inner = 0; inner < lhs.column_count(); ++inner) {
                sum += static_cast<long double>(lhs(row, inner)) *
                    rhs(inner, column);
            }
            result(row, column) = static_cast<double>(sum);
        }
    }
    return result;
}

[[nodiscard]] DenseMatrix orthonormalize_columns(
    const DenseMatrix& matrix,
    double relative_threshold,
    double absolute_threshold = 0.0) {
    DenseMatrix temporary(matrix.row_count(), matrix.column_count());
    std::size_t accepted = 0U;
    for (std::size_t source = 0; source < matrix.column_count(); ++source) {
        std::vector<double> column(matrix.row_count());
        for (std::size_t row = 0; row < matrix.row_count(); ++row) {
            column[row] = matrix(row, source);
        }
        const auto original_norm = stable_l2(column);
        if (!(original_norm > 0.0) || !std::isfinite(original_norm)) {
            continue;
        }
        for (std::size_t pass = 0; pass < 2U; ++pass) {
            for (std::size_t basis = 0; basis < accepted; ++basis) {
                long double projection = 0.0L;
                for (std::size_t row = 0; row < matrix.row_count(); ++row) {
                    projection += static_cast<long double>(
                        temporary(row, basis)) * column[row];
                }
                for (std::size_t row = 0; row < matrix.row_count(); ++row) {
                    column[row] -= static_cast<double>(projection) *
                        temporary(row, basis);
                }
            }
        }
        const auto residual_norm = stable_l2(column);
        if (!(residual_norm > std::max(
                  relative_threshold * original_norm, absolute_threshold)) ||
            !std::isfinite(residual_norm)) {
            continue;
        }
        for (std::size_t row = 0; row < matrix.row_count(); ++row) {
            temporary(row, accepted) = column[row] / residual_norm;
        }
        ++accepted;
    }
    DenseMatrix result(matrix.row_count(), accepted);
    for (std::size_t row = 0; row < matrix.row_count(); ++row) {
        for (std::size_t column = 0; column < accepted; ++column) {
            result(row, column) = temporary(row, column);
        }
    }
    return result;
}

struct PivotedQr final {
    bool ok{false};
    std::size_t rows{0};
    std::size_t columns{0};
    std::vector<double> factor{};
    std::vector<std::size_t> permutation{};
    std::vector<double> diagonals{};
};

[[nodiscard]] PivotedQr complete_householder_cpqr(const DenseMatrix& matrix) {
    PivotedQr result{};
    result.rows = matrix.row_count();
    result.columns = matrix.column_count();
    result.factor.assign(matrix.entries().begin(), matrix.entries().end());
    result.permutation.resize(result.columns);
    std::iota(
        result.permutation.begin(), result.permutation.end(), std::size_t{0});
    const auto steps = std::min(result.rows, result.columns);
    result.diagonals.reserve(steps);
    for (std::size_t step = 0; step < steps; ++step) {
        auto selected = step;
        long double selected_squared = -1.0L;
        for (std::size_t column = step; column < result.columns; ++column) {
            long double squared = 0.0L;
            for (std::size_t row = step; row < result.rows; ++row) {
                const auto value = result.factor[row * result.columns + column];
                squared += static_cast<long double>(value) * value;
            }
            if (squared > selected_squared) {
                selected_squared = squared;
                selected = column;
            }
        }
        const auto selected_norm = std::sqrt(
            static_cast<double>(std::max(0.0L, selected_squared)));
        if (!std::isfinite(selected_norm)) {
            return result;
        }
        if (!(selected_norm > 0.0)) {
            // Preserve every structural-zero step in the deterministic trace.
            // All remaining trailing norms are zero, but retaining each step
            // makes the pivot evidence complete rather than silently short.
            result.diagonals.push_back(0.0);
            continue;
        }
        if (selected != step) {
            for (std::size_t row = 0; row < result.rows; ++row) {
                std::swap(
                    result.factor[row * result.columns + step],
                    result.factor[row * result.columns + selected]);
            }
            std::swap(result.permutation[step], result.permutation[selected]);
        }
        long double norm_squared = 0.0L;
        for (std::size_t row = step; row < result.rows; ++row) {
            const auto value = result.factor[row * result.columns + step];
            norm_squared += static_cast<long double>(value) * value;
        }
        const auto column_norm = std::sqrt(static_cast<double>(norm_squared));
        if (!std::isfinite(column_norm)) {
            return result;
        }
        if (!(column_norm > 0.0)) {
            result.diagonals.push_back(0.0);
            continue;
        }
        const auto first = result.factor[step * result.columns + step];
        const auto alpha = first >= 0.0 ? -column_norm : column_norm;
        std::vector<double> reflector(result.rows - step);
        for (std::size_t row = step; row < result.rows; ++row) {
            reflector[row - step] =
                result.factor[row * result.columns + step];
        }
        reflector.front() -= alpha;
        long double reflector_squared = 0.0L;
        for (const auto value : reflector) {
            reflector_squared += static_cast<long double>(value) * value;
        }
        if (!(reflector_squared > 0.0L)) {
            return result;
        }
        for (std::size_t column = step; column < result.columns; ++column) {
            long double product = 0.0L;
            for (std::size_t row = step; row < result.rows; ++row) {
                product += static_cast<long double>(reflector[row - step]) *
                    result.factor[row * result.columns + column];
            }
            const auto scale = static_cast<double>(
                2.0L * product / reflector_squared);
            for (std::size_t row = step; row < result.rows; ++row) {
                result.factor[row * result.columns + column] -=
                    scale * reflector[row - step];
            }
        }
        result.factor[step * result.columns + step] = alpha;
        for (std::size_t row = step + 1U; row < result.rows; ++row) {
            result.factor[row * result.columns + step] = 0.0;
        }
        result.diagonals.push_back(std::abs(alpha));
    }
    result.ok = result.diagonals.size() == steps &&
        std::ranges::all_of(result.factor, [](double value) {
            return std::isfinite(value);
        });
    return result;
}

[[nodiscard]] std::vector<double> qr_null_vector(
    const PivotedQr& qr, std::size_t rank, std::size_t free_offset) {
    const auto free_column = rank + free_offset;
    std::vector<double> permuted(qr.columns, 0.0);
    permuted[free_column] = 1.0;
    for (std::size_t reverse = rank; reverse > 0U; --reverse) {
        const auto row = reverse - 1U;
        long double rhs = 0.0L;
        for (std::size_t column = row + 1U; column < qr.columns; ++column) {
            rhs += static_cast<long double>(
                qr.factor[row * qr.columns + column]) * permuted[column];
        }
        const auto diagonal = qr.factor[row * qr.columns + row];
        if (diagonal == 0.0 || !std::isfinite(diagonal)) {
            throw std::runtime_error("accepted QR pivot is invalid");
        }
        permuted[row] = -static_cast<double>(rhs) / diagonal;
    }
    std::vector<double> result(qr.columns, 0.0);
    for (std::size_t column = 0; column < qr.columns; ++column) {
        result[qr.permutation[column]] = permuted[column];
    }
    return result;
}

[[nodiscard]] double normalized_product_residual(
    const DenseMatrix& lhs, const DenseMatrix& rhs) {
    if (lhs.column_count() != rhs.row_count()) {
        throw std::invalid_argument("residual matrices do not compose");
    }
    if (rhs.column_count() == 0U) {
        return 0.0;
    }
    const auto product = multiply_dense(lhs, rhs);
    const auto denominator = matrix_frobenius(lhs) * matrix_frobenius(rhs);
    const auto numerator = matrix_frobenius(product);
    if (denominator == 0.0) {
        return numerator == 0.0
            ? 0.0
            : std::numeric_limits<double>::infinity();
    }
    return numerator / denominator;
}

[[nodiscard]] double normalized_cross_orthogonality(
    const DenseMatrix& lhs_columns, const DenseMatrix& rhs_columns) {
    if (lhs_columns.row_count() != rhs_columns.row_count()) {
        throw std::invalid_argument("orthogonality matrices disagree");
    }
    if (lhs_columns.column_count() == 0U ||
        rhs_columns.column_count() == 0U) {
        return 0.0;
    }
    DenseMatrix product(lhs_columns.column_count(), rhs_columns.column_count());
    for (std::size_t left = 0; left < lhs_columns.column_count(); ++left) {
        for (std::size_t right = 0; right < rhs_columns.column_count(); ++right) {
            long double value = 0.0L;
            for (std::size_t row = 0; row < lhs_columns.row_count(); ++row) {
                value += static_cast<long double>(lhs_columns(row, left)) *
                    rhs_columns(row, right);
            }
            product(left, right) = static_cast<double>(value);
        }
    }
    return matrix_frobenius(product) /
        (matrix_frobenius(lhs_columns) * matrix_frobenius(rhs_columns));
}

[[nodiscard]] std::vector<MechanicalPacket> packets_in_operator_order(
    const LinearizedOperator& linearized,
    std::span<const MechanicalPacket> packets) {
    const auto canonical = canonical_packets(packets);
    if (packet_ids(canonical) != linearized.packet_ids ||
        linearized.matrix.column_count() !=
            checked_product(canonical.size(), 3U, "packet velocity")) {
        throw std::invalid_argument("operator and packet identity sets disagree");
    }
    return canonical;
}

[[nodiscard]] std::vector<BondRelation> validate_bonds(
    const std::map<std::uint64_t, std::size_t>& lookup,
    std::span<const BondRelation> relations) {
    std::vector<BondRelation> result(relations.begin(), relations.end());
    for (const auto& relation : result) {
        if (relation.first_id == 0U ||
            !(relation.first_id < relation.second_id) ||
            !lookup.contains(relation.first_id) ||
            !lookup.contains(relation.second_id)) {
            throw std::invalid_argument("bond relation is noncanonical or unresolved");
        }
    }
    if (!std::ranges::is_sorted(result, {}, [](const BondRelation& relation) {
            return std::pair{relation.first_id, relation.second_id};
        })) {
        throw std::invalid_argument("bond relations must be sorted canonically");
    }
    for (std::size_t index = 1; index < result.size(); ++index) {
        if (result[index - 1U] == result[index]) {
            throw std::invalid_argument("duplicate bond relation");
        }
    }
    return result;
}

[[nodiscard]] std::vector<VolumeRelation> validate_volumes(
    const std::map<std::uint64_t, std::size_t>& lookup,
    std::span<const VolumeRelation> relations) {
    std::vector<VolumeRelation> result(relations.begin(), relations.end());
    for (const auto& relation : result) {
        const auto& other = relation.other_ids;
        if (relation.center_id == 0U || other[0] == 0U ||
            !(other[0] < other[1] && other[1] < other[2]) ||
            std::ranges::find(other, relation.center_id) != other.end() ||
            !lookup.contains(relation.center_id) ||
            !std::ranges::all_of(other, [&](std::uint64_t value) {
                return lookup.contains(value);
            })) {
            throw std::invalid_argument(
                "volume relation is noncanonical or unresolved");
        }
    }
    if (!std::ranges::is_sorted(result, {}, [](const VolumeRelation& relation) {
            return std::tuple{
                relation.center_id, relation.other_ids[0],
                relation.other_ids[1], relation.other_ids[2]};
        })) {
        throw std::invalid_argument("volume relations must be sorted canonically");
    }
    for (std::size_t index = 1; index < result.size(); ++index) {
        if (result[index - 1U] == result[index]) {
            throw std::invalid_argument("duplicate volume relation");
        }
    }
    return result;
}

[[nodiscard]] double determinant(const Matrix3d& matrix) noexcept {
    const auto& a = matrix.value;
    return a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) -
        a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) +
        a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]);
}

constexpr std::array<std::uint8_t, 8> checkpoint_magic{
    'M', 'L', 'S', 'M', 'O', 'B', 'S', '1'};

void append_u32(std::vector<std::uint8_t>& bytes, std::uint32_t value) {
    for (std::size_t shift = 0; shift < 32U; shift += 8U) {
        bytes.push_back(static_cast<std::uint8_t>(value >> shift));
    }
}

void append_u64(std::vector<std::uint8_t>& bytes, std::uint64_t value) {
    for (std::size_t shift = 0; shift < 64U; shift += 8U) {
        bytes.push_back(static_cast<std::uint8_t>(value >> shift));
    }
}

void append_double(std::vector<std::uint8_t>& bytes, double value) {
    if (!std::isfinite(value)) {
        throw std::invalid_argument("checkpoint binary64 value must be finite");
    }
    if (value == 0.0) {
        value = 0.0; // canonicalize negative zero
    }
    append_u64(bytes, std::bit_cast<std::uint64_t>(value));
}

class CheckpointReader final {
public:
    explicit CheckpointReader(std::span<const std::uint8_t> bytes)
        : bytes_(bytes) {}

    [[nodiscard]] std::uint32_t u32() {
        const auto value = u64_width(4U);
        return static_cast<std::uint32_t>(value);
    }

    [[nodiscard]] std::uint64_t u64() { return u64_width(8U); }

    [[nodiscard]] double binary64() {
        const auto value = std::bit_cast<double>(u64());
        if (!std::isfinite(value) || (value == 0.0 && std::signbit(value))) {
            throw std::invalid_argument(
                "checkpoint binary64 is nonfinite or noncanonical");
        }
        return value;
    }

    void expect_magic() {
        require(checkpoint_magic.size());
        for (const auto expected : checkpoint_magic) {
            if (bytes_[offset_++] != expected) {
                throw std::invalid_argument("checkpoint magic mismatch");
            }
        }
    }

    [[nodiscard]] bool finished() const noexcept {
        return offset_ == bytes_.size();
    }

private:
    [[nodiscard]] std::uint64_t u64_width(std::size_t width) {
        require(width);
        std::uint64_t result = 0U;
        for (std::size_t index = 0; index < width; ++index) {
            result |= static_cast<std::uint64_t>(bytes_[offset_++]) <<
                (8U * index);
        }
        return result;
    }

    void require(std::size_t count) const {
        if (count > bytes_.size() - std::min(offset_, bytes_.size())) {
            throw std::invalid_argument("checkpoint is truncated");
        }
    }

    std::span<const std::uint8_t> bytes_{};
    std::size_t offset_{0};
};

[[nodiscard]] std::size_t checked_count(std::uint64_t count) {
    if (count > static_cast<std::uint64_t>(
                    std::numeric_limits<std::size_t>::max())) {
        throw std::length_error("checkpoint count exceeds address space");
    }
    return static_cast<std::size_t>(count);
}

} // namespace

DenseMatrix::DenseMatrix(
    const std::size_t row_count, const std::size_t column_count)
    : row_count_(row_count), column_count_(column_count) {
    if (column_count_ != 0U &&
        row_count_ > std::numeric_limits<std::size_t>::max() / column_count_) {
        throw std::length_error("dense matrix dimension overflow");
    }
    entries_.assign(row_count_ * column_count_, 0.0);
}

double DenseMatrix::operator()(
    const std::size_t row, const std::size_t column) const {
    if (row >= row_count_ || column >= column_count_) {
        throw std::out_of_range("dense matrix index out of range");
    }
    return entries_[row * column_count_ + column];
}

double& DenseMatrix::operator()(
    const std::size_t row, const std::size_t column) {
    if (row >= row_count_ || column >= column_count_) {
        throw std::out_of_range("dense matrix index out of range");
    }
    return entries_[row * column_count_ + column];
}

std::vector<std::uint8_t> serialize_mechanical_observability_state(
    const MechanicalObservabilityState& state) {
    if (!(state.support_radius_m > 0.0) ||
        !std::isfinite(state.support_radius_m)) {
        throw std::invalid_argument("checkpoint support radius must be positive");
    }
    const auto packets = canonical_packets(state.packets);
    const auto lookup = packet_lookup(packets);
    const auto bonds = validate_bonds(lookup, state.bonds);
    const auto volumes = validate_volumes(lookup, state.volumes);
    validate_selected_oriented_volume_relations(packets, bonds, volumes);
    // These calls additionally reject coincident bond endpoints and a volume
    // tuple whose complete linearized observable is zero.
    static_cast<void>(build_bond_rigidity_operator(packets, bonds));
    static_cast<void>(build_oriented_volume_operator(packets, volumes));

    std::vector<std::uint8_t> result;
    result.insert(result.end(), checkpoint_magic.begin(), checkpoint_magic.end());
    append_u32(result, mechanical_observability_checkpoint_version);
    append_double(result, state.support_radius_m);
    append_u64(result, static_cast<std::uint64_t>(packets.size()));
    for (const auto& packet : packets) {
        append_u64(result, packet.id);
        append_u64(result, std::bit_cast<std::uint64_t>(packet.mass_quanta));
        append_double(result, packet.position_m.x);
        append_double(result, packet.position_m.y);
        append_double(result, packet.position_m.z);
        append_double(result, packet.velocity_m_per_s.x);
        append_double(result, packet.velocity_m_per_s.y);
        append_double(result, packet.velocity_m_per_s.z);
    }
    append_u64(result, static_cast<std::uint64_t>(bonds.size()));
    for (const auto& bond : bonds) {
        append_u64(result, bond.first_id);
        append_u64(result, bond.second_id);
    }
    append_u64(result, static_cast<std::uint64_t>(volumes.size()));
    for (const auto& volume : volumes) {
        append_u64(result, volume.center_id);
        for (const auto other : volume.other_ids) {
            append_u64(result, other);
        }
    }
    return result;
}

MechanicalObservabilityState deserialize_mechanical_observability_state(
    std::span<const std::uint8_t> checkpoint) {
    CheckpointReader reader(checkpoint);
    reader.expect_magic();
    if (reader.u32() != mechanical_observability_checkpoint_version) {
        throw std::invalid_argument("unsupported observability checkpoint version");
    }
    MechanicalObservabilityState result{};
    result.support_radius_m = reader.binary64();
    const auto packet_count = checked_count(reader.u64());
    if (packet_count > checkpoint.size() / 64U) {
        throw std::invalid_argument("checkpoint packet count is impossible");
    }
    result.packets.reserve(packet_count);
    for (std::size_t index = 0; index < packet_count; ++index) {
        MechanicalPacket packet{};
        packet.id = reader.u64();
        packet.mass_quanta = std::bit_cast<std::int64_t>(reader.u64());
        packet.position_m = {
            reader.binary64(), reader.binary64(), reader.binary64()};
        packet.velocity_m_per_s = {
            reader.binary64(), reader.binary64(), reader.binary64()};
        result.packets.push_back(packet);
    }
    const auto bond_count = checked_count(reader.u64());
    if (bond_count > checkpoint.size() / 16U) {
        throw std::invalid_argument("checkpoint bond count is impossible");
    }
    result.bonds.reserve(bond_count);
    for (std::size_t index = 0; index < bond_count; ++index) {
        result.bonds.push_back({reader.u64(), reader.u64()});
    }
    const auto volume_count = checked_count(reader.u64());
    if (volume_count > checkpoint.size() / 32U) {
        throw std::invalid_argument("checkpoint volume count is impossible");
    }
    result.volumes.reserve(volume_count);
    for (std::size_t index = 0; index < volume_count; ++index) {
        VolumeRelation relation{};
        relation.center_id = reader.u64();
        for (auto& other : relation.other_ids) {
            other = reader.u64();
        }
        result.volumes.push_back(relation);
    }
    if (!reader.finished()) {
        throw std::invalid_argument("checkpoint has trailing bytes");
    }
    // Re-encoding is both the full state validation and the canonical byte
    // check. An alternate packet/relation order or negative-zero spelling is
    // rejected rather than becoming a second checkpoint for the same state.
    if (serialize_mechanical_observability_state(result) !=
        std::vector<std::uint8_t>(checkpoint.begin(), checkpoint.end())) {
        throw std::invalid_argument("checkpoint is not canonically encoded");
    }
    return result;
}

std::string_view observable_name(const ObservableKind kind) noexcept {
    switch (kind) {
    case ObservableKind::corrected_local_symmetric_gradient:
        return "corrected_local_symmetric_gradient";
    case ObservableKind::central_bond_length_rate:
        return "central_bond_length_rate";
    case ObservableKind::oriented_volume_rate:
        return "oriented_volume_rate";
    case ObservableKind::enriched_bond_and_volume:
        return "enriched_bond_and_volume";
    }
    return "unknown";
}

std::string_view status_name(const OperatorBuildStatus status) noexcept {
    switch (status) {
    case OperatorBuildStatus::built:
        return "built";
    case OperatorBuildStatus::empty:
        return "empty";
    case OperatorBuildStatus::singular_local_moment:
        return "singular_local_moment";
    case OperatorBuildStatus::ill_conditioned_local_moment:
        return "ill_conditioned_local_moment";
    case OperatorBuildStatus::numerical_failure:
        return "numerical_failure";
    }
    return "unknown";
}

CorrectedGradientOperator build_corrected_local_gradient(
    std::span<const MechanicalPacket> packets,
    const CorrectedGradientPolicy& policy) {
    if (!(policy.support_radius_m > 0.0) ||
        !std::isfinite(policy.support_radius_m) ||
        !(policy.condition_number_max >= 1.0) ||
        !std::isfinite(policy.condition_number_max)) {
        throw std::invalid_argument("invalid corrected-gradient policy");
    }
    const auto canonical = canonical_packets(packets);
    CorrectedGradientOperator result{};
    result.symmetric_gradient.kind =
        ObservableKind::corrected_local_symmetric_gradient;
    result.symmetric_gradient.packet_ids = packet_ids(canonical);
    if (canonical.empty()) {
        result.status = OperatorBuildStatus::empty;
        return result;
    }
    const auto count = canonical.size();
    const auto velocity_dofs = checked_product(count, 3U, "packet velocity");
    const auto symmetric_rows = checked_product(count, 6U, "symmetric gradient");
    const auto full_rows = checked_product(count, 9U, "full gradient");
    result.symmetric_gradient.matrix = DenseMatrix(symmetric_rows, velocity_dofs);
    result.full_gradient = DenseMatrix(full_rows, velocity_dofs);
    result.local_moments.reserve(count);
    auto aggregate_status = OperatorBuildStatus::built;

    struct Neighbor final {
        std::size_t index{0};
        Vec3d offset_m{};
        double weight{0.0};
    };
    for (std::size_t particle = 0; particle < count; ++particle) {
        std::vector<Neighbor> neighbors;
        Matrix3d moment{};
        bool coordinate_subtraction_failed = false;
        for (std::size_t candidate = 0; candidate < count; ++candidate) {
            if (candidate == particle) {
                continue;
            }
            const auto offset = canonical[candidate].position_m -
                canonical[particle].position_m;
            if (!finite(offset)) {
                coordinate_subtraction_failed = true;
                aggregate_status = OperatorBuildStatus::numerical_failure;
                continue;
            }
            double squared_ratio = 0.0;
            if (!inside_support(offset, policy.support_radius_m, squared_ratio)) {
                continue;
            }
            const auto complement = 1.0 - squared_ratio;
            const auto weight = complement * complement;
            if (!(weight > 0.0) || !std::isfinite(weight)) {
                aggregate_status = OperatorBuildStatus::numerical_failure;
                continue;
            }
            neighbors.push_back({candidate, offset, weight});
            add_scaled_outer(moment, weight, offset, offset);
        }

        LocalMomentDiagnostic diagnostic{};
        diagnostic.packet_id = canonical[particle].id;
        diagnostic.neighbor_count = neighbors.size();
        diagnostic.moment_m2 = moment;
        diagnostic.status = OperatorBuildStatus::built;
        Matrix3d inverse{};
        if (coordinate_subtraction_failed || !finite(moment)) {
            diagnostic.status = OperatorBuildStatus::numerical_failure;
        } else {
            const auto eigenvalues = symmetric_eigenvalues(moment);
            diagnostic.smallest_eigenvalue_m2 = eigenvalues[0];
            diagnostic.largest_eigenvalue_m2 = eigenvalues[2];
            const auto singular_floor = 64.0 *
                std::numeric_limits<double>::epsilon() *
                std::max(eigenvalues[2], std::numeric_limits<double>::min());
            if (!(eigenvalues[2] > 0.0) ||
                !(eigenvalues[0] > singular_floor)) {
                diagnostic.status = OperatorBuildStatus::singular_local_moment;
                diagnostic.condition_number =
                    std::numeric_limits<double>::infinity();
            } else {
                diagnostic.condition_number = eigenvalues[2] / eigenvalues[0];
                if (!std::isfinite(diagnostic.condition_number)) {
                    diagnostic.status = OperatorBuildStatus::numerical_failure;
                } else if (diagnostic.condition_number >
                           policy.condition_number_max) {
                    diagnostic.status =
                        OperatorBuildStatus::ill_conditioned_local_moment;
                } else if (!inverse_symmetric_positive(moment, inverse)) {
                    diagnostic.status =
                        OperatorBuildStatus::singular_local_moment;
                } else {
                    diagnostic.inverse_residual_normalized =
                        inverse_product_residual(moment, inverse);
                    diagnostic.inverse_accepted =
                        std::isfinite(diagnostic.inverse_residual_normalized) &&
                        diagnostic.inverse_residual_normalized <=
                            diagnostic.inverse_residual_tolerance;
                    if (!diagnostic.inverse_accepted) {
                        diagnostic.status =
                            OperatorBuildStatus::numerical_failure;
                    }
                }
            }
        }
        if (diagnostic.status != OperatorBuildStatus::built &&
            aggregate_status == OperatorBuildStatus::built) {
            aggregate_status = diagnostic.status;
        }
        result.local_moments.push_back(diagnostic);
        if (diagnostic.status != OperatorBuildStatus::built) {
            continue;
        }

        for (const auto& neighbor : neighbors) {
            std::array<double, 3> coefficient{};
            for (std::size_t gradient_column = 0; gradient_column < 3U;
                 ++gradient_column) {
                long double value = 0.0L;
                for (std::size_t inner = 0; inner < 3U; ++inner) {
                    value += static_cast<long double>(
                        component(neighbor.offset_m, inner)) *
                        inverse.value[inner][gradient_column];
                }
                coefficient[gradient_column] =
                    neighbor.weight * static_cast<double>(value);
            }
            for (std::size_t velocity_component = 0; velocity_component < 3U;
                 ++velocity_component) {
                for (std::size_t derivative = 0; derivative < 3U; ++derivative) {
                    const auto row = 9U * particle +
                        3U * velocity_component + derivative;
                    const auto neighbor_column =
                        3U * neighbor.index + velocity_component;
                    const auto center_column =
                        3U * particle + velocity_component;
                    result.full_gradient(row, neighbor_column) +=
                        coefficient[derivative];
                    result.full_gradient(row, center_column) -=
                        coefficient[derivative];
                }
            }
        }

        const auto copy_diagonal = [&](std::size_t output, std::size_t axis) {
            const auto full_row = 9U * particle + 3U * axis + axis;
            for (std::size_t column = 0; column < velocity_dofs; ++column) {
                result.symmetric_gradient.matrix(6U * particle + output, column) =
                    result.full_gradient(full_row, column);
            }
        };
        copy_diagonal(0U, 0U);
        copy_diagonal(1U, 1U);
        copy_diagonal(2U, 2U);
        constexpr double inverse_sqrt_two = 0.707106781186547524400844362104849;
        for (const auto& [output, first, second] :
             {std::tuple{3U, 0U, 1U}, std::tuple{4U, 0U, 2U},
              std::tuple{5U, 1U, 2U}}) {
            const auto first_row = 9U * particle + 3U * first + second;
            const auto second_row = 9U * particle + 3U * second + first;
            for (std::size_t column = 0; column < velocity_dofs; ++column) {
                result.symmetric_gradient.matrix(6U * particle + output, column) =
                    inverse_sqrt_two *
                    (result.full_gradient(first_row, column) +
                     result.full_gradient(second_row, column));
            }
        }
    }
    result.status = aggregate_status;
    if (result.status != OperatorBuildStatus::built) {
        // A partial operator is not an admissible candidate. Per-packet moment
        // evidence remains available, but no zero-filled row may be mistaken
        // for an observable.
        result.symmetric_gradient.matrix = DenseMatrix{};
        result.full_gradient = DenseMatrix{};
    }
    return result;
}

BondOperator build_bond_rigidity_operator(
    std::span<const MechanicalPacket> packets,
    std::span<const BondRelation> relations) {
    const auto canonical = canonical_packets(packets);
    const auto lookup = packet_lookup(canonical);
    BondOperator result{};
    result.linearized.kind = ObservableKind::central_bond_length_rate;
    result.linearized.packet_ids = packet_ids(canonical);
    result.relations = validate_bonds(lookup, relations);
    result.linearized.matrix =
        DenseMatrix(result.relations.size(),
            checked_product(canonical.size(), 3U, "bond operator"));
    result.lengths_m.reserve(result.relations.size());
    for (std::size_t row = 0; row < result.relations.size(); ++row) {
        const auto& relation = result.relations[row];
        const auto first = lookup.at(relation.first_id);
        const auto second = lookup.at(relation.second_id);
        const auto offset = canonical[second].position_m -
            canonical[first].position_m;
        if (!finite(offset)) {
            throw std::overflow_error("bond coordinate subtraction overflow");
        }
        const auto length = stable_vector_norm(offset);
        if (!(length > 0.0) || !std::isfinite(length)) {
            throw std::invalid_argument("bond endpoints must be distinct and finite");
        }
        result.lengths_m.push_back(length);
        const auto direction = offset / length;
        for (std::size_t component_index = 0; component_index < 3U;
             ++component_index) {
            const auto coefficient = component(direction, component_index);
            result.linearized.matrix(row, 3U * first + component_index) =
                -coefficient;
            result.linearized.matrix(row, 3U * second + component_index) =
                coefficient;
        }
    }
    return result;
}

VolumeOperator build_oriented_volume_operator(
    std::span<const MechanicalPacket> packets,
    std::span<const VolumeRelation> relations) {
    const auto canonical = canonical_packets(packets);
    const auto lookup = packet_lookup(canonical);
    VolumeOperator result{};
    result.linearized.kind = ObservableKind::oriented_volume_rate;
    result.linearized.packet_ids = packet_ids(canonical);
    result.relations = validate_volumes(lookup, relations);
    result.linearized.matrix =
        DenseMatrix(result.relations.size(),
            checked_product(canonical.size(), 3U, "volume operator"));
    result.oriented_volumes_m3.reserve(result.relations.size());
    for (std::size_t row = 0; row < result.relations.size(); ++row) {
        const auto& relation = result.relations[row];
        const auto i = lookup.at(relation.center_id);
        const auto j = lookup.at(relation.other_ids[0]);
        const auto k = lookup.at(relation.other_ids[1]);
        const auto l = lookup.at(relation.other_ids[2]);
        const auto a = canonical[j].position_m - canonical[i].position_m;
        const auto b = canonical[k].position_m - canonical[i].position_m;
        const auto c = canonical[l].position_m - canonical[i].position_m;
        if (!finite(a) || !finite(b) || !finite(c)) {
            throw std::overflow_error("volume coordinate subtraction overflow");
        }
        result.oriented_volumes_m3.push_back(long_double_triple(a, b, c));
        const auto coefficient_j = checked_cross(b, c);
        const auto coefficient_k = checked_cross(c, a);
        const auto coefficient_l = checked_cross(a, b);
        const auto coefficient_i =
            -(coefficient_j + coefficient_k + coefficient_l);
        if (!(stable_vector_norm(coefficient_i) > 0.0 ||
              stable_vector_norm(coefficient_j) > 0.0 ||
              stable_vector_norm(coefficient_k) > 0.0 ||
              stable_vector_norm(coefficient_l) > 0.0)) {
            throw std::invalid_argument(
                "volume relation has a zero linearized observable");
        }
        for (const auto& [index, coefficient] :
             {std::pair{i, coefficient_i}, std::pair{j, coefficient_j},
              std::pair{k, coefficient_k}, std::pair{l, coefficient_l}}) {
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                result.linearized.matrix(row, 3U * index + axis) =
                    component(coefficient, axis);
            }
        }
    }
    return result;
}

std::vector<VolumeRelation> select_oriented_volume_relations(
    std::span<const MechanicalPacket> packets,
    std::span<const BondRelation> bonds) {
    const auto canonical = canonical_packets(packets);
    const auto bond_operator = build_bond_rigidity_operator(canonical, bonds);
    const auto lookup = packet_lookup(canonical);
    std::map<std::uint64_t, std::vector<std::uint64_t>> neighbors;
    for (const auto& packet : canonical) {
        neighbors.emplace(packet.id, std::vector<std::uint64_t>{});
    }
    for (const auto& bond : bond_operator.relations) {
        neighbors.at(bond.first_id).push_back(bond.second_id);
        neighbors.at(bond.second_id).push_back(bond.first_id);
    }
    std::vector<VolumeRelation> result;
    for (auto& [center, incident] : neighbors) {
        std::ranges::sort(incident);
        if (incident.size() < 3U) {
            continue;
        }
        std::optional<VolumeRelation> selected;
        long double maximum_score = 0.0L;
        const auto center_position = canonical[lookup.at(center)].position_m;
        for (std::size_t first = 0U; first + 2U < incident.size(); ++first) {
            for (std::size_t second = first + 1U;
                 second + 1U < incident.size(); ++second) {
                for (std::size_t third = second + 1U;
                     third < incident.size(); ++third) {
                    const VolumeRelation candidate{
                        center,
                        {incident[first], incident[second], incident[third]}};
                    const auto a = canonical[lookup.at(candidate.other_ids[0])]
                                       .position_m - center_position;
                    const auto b = canonical[lookup.at(candidate.other_ids[1])]
                                       .position_m - center_position;
                    const auto c = canonical[lookup.at(candidate.other_ids[2])]
                                       .position_m - center_position;
                    if (!finite(a) || !finite(b) || !finite(c)) {
                        throw std::overflow_error(
                            "volume selection coordinate subtraction overflow");
                    }
                    const std::array cross_products{
                        checked_cross(b, c), checked_cross(c, a),
                        checked_cross(a, b)};
                    long double score = 0.0L;
                    for (const auto value : cross_products) {
                        score += static_cast<long double>(value.x) * value.x +
                            static_cast<long double>(value.y) * value.y +
                            static_cast<long double>(value.z) * value.z;
                    }
                    if (!std::isfinite(score)) {
                        throw std::overflow_error(
                            "volume selection score overflow");
                    }
                    if (score > maximum_score ||
                        (score == maximum_score && selected.has_value() &&
                         candidate.other_ids < selected->other_ids)) {
                        maximum_score = score;
                        selected = candidate;
                    }
                }
            }
        }
        if (selected.has_value() && maximum_score > 0.0L) {
            result.push_back(*selected);
        }
    }
    return result;
}

void validate_selected_oriented_volume_relations(
    std::span<const MechanicalPacket> packets,
    std::span<const BondRelation> bonds,
    std::span<const VolumeRelation> volumes) {
    const auto canonical = canonical_packets(packets);
    const auto lookup = packet_lookup(canonical);
    static_cast<void>(validate_bonds(lookup, bonds));
    const auto supplied = validate_volumes(lookup, volumes);
    if (supplied.empty()) {
        return;
    }
    const auto expected = select_oriented_volume_relations(canonical, bonds);
    std::map<std::uint64_t, VolumeRelation> selected_by_center;
    for (const auto& relation : expected) {
        selected_by_center.emplace(relation.center_id, relation);
    }
    std::set<std::uint64_t> supplied_centers;
    for (const auto& relation : supplied) {
        const auto selected = selected_by_center.find(relation.center_id);
        if (!supplied_centers.insert(relation.center_id).second ||
            selected == selected_by_center.end() ||
            selected->second != relation) {
            throw std::invalid_argument(
                "volume relation is not the unique deterministic selection for its center");
        }
    }
}

LinearizedOperator combine_relational_operators(
    const BondOperator& bonds, const VolumeOperator& volumes) {
    if (bonds.linearized.packet_ids != volumes.linearized.packet_ids ||
        bonds.linearized.matrix.column_count() !=
            volumes.linearized.matrix.column_count()) {
        throw std::invalid_argument("relational operators use different packets");
    }
    LinearizedOperator result{};
    result.kind = ObservableKind::enriched_bond_and_volume;
    result.packet_ids = bonds.linearized.packet_ids;
    result.matrix = DenseMatrix(
        checked_sum(bonds.linearized.matrix.row_count(),
            volumes.linearized.matrix.row_count(), "relational row"),
        bonds.linearized.matrix.column_count());
    for (std::size_t row = 0; row < bonds.linearized.matrix.row_count(); ++row) {
        for (std::size_t column = 0;
             column < result.matrix.column_count(); ++column) {
            result.matrix(row, column) = bonds.linearized.matrix(row, column);
        }
    }
    for (std::size_t row = 0; row < volumes.linearized.matrix.row_count(); ++row) {
        for (std::size_t column = 0;
             column < result.matrix.column_count(); ++column) {
            result.matrix(bonds.linearized.matrix.row_count() + row, column) =
                volumes.linearized.matrix(row, column);
        }
    }
    return result;
}

std::vector<double> apply_operator(
    const LinearizedOperator& linearized,
    std::span<const MechanicalPacket> packets) {
    const auto canonical = packets_in_operator_order(linearized, packets);
    std::vector<double> result(linearized.matrix.row_count(), 0.0);
    for (std::size_t row = 0; row < linearized.matrix.row_count(); ++row) {
        long double value = 0.0L;
        for (std::size_t packet = 0; packet < canonical.size(); ++packet) {
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                value += static_cast<long double>(
                    linearized.matrix(row, 3U * packet + axis)) *
                    component(canonical[packet].velocity_m_per_s, axis);
            }
        }
        result[row] = static_cast<double>(value);
        if (!std::isfinite(result[row])) {
            throw std::overflow_error("operator application overflow");
        }
    }
    return result;
}

std::vector<Matrix3d> evaluate_full_local_gradients(
    const CorrectedGradientOperator& corrected,
    std::span<const MechanicalPacket> packets) {
    if (corrected.status != OperatorBuildStatus::built) {
        throw std::invalid_argument("corrected gradient is unavailable");
    }
    LinearizedOperator full{
        corrected.full_gradient,
        corrected.symmetric_gradient.packet_ids,
        ObservableKind::corrected_local_symmetric_gradient};
    const auto values = apply_operator(full, packets);
    std::vector<Matrix3d> result(corrected.symmetric_gradient.packet_ids.size());
    for (std::size_t packet = 0; packet < result.size(); ++packet) {
        for (std::size_t row = 0; row < 3U; ++row) {
            for (std::size_t column = 0; column < 3U; ++column) {
                result[packet].value[row][column] =
                    values[9U * packet + 3U * row + column];
            }
        }
    }
    return result;
}

RowNormalization normalize_operator_rows(const DenseMatrix& matrix) {
    RowNormalization result{};
    result.normalized = DenseMatrix(matrix.row_count(), matrix.column_count());
    result.row_norms.reserve(matrix.row_count());
    result.complete = true;
    result.first_invalid_row = matrix.row_count();
    for (std::size_t row = 0; row < matrix.row_count(); ++row) {
        std::vector<double> values(matrix.column_count());
        for (std::size_t column = 0; column < matrix.column_count(); ++column) {
            values[column] = matrix(row, column);
        }
        const auto norm_value = stable_l2(values);
        result.row_norms.push_back(norm_value);
        if (!(norm_value > 0.0) || !std::isfinite(norm_value)) {
            result.complete = false;
            if (result.first_invalid_row == matrix.row_count()) {
                result.first_invalid_row = row;
            }
            continue;
        }
        for (std::size_t column = 0; column < matrix.column_count(); ++column) {
            result.normalized(row, column) = matrix(row, column) / norm_value;
        }
    }
    // A genuinely empty observation set has no row to drop or normalize.
    if (matrix.row_count() == 0U) {
        result.complete = true;
    }
    return result;
}

std::string_view status_name(const RankStatus status) noexcept {
    switch (status) {
    case RankStatus::analyzed:
        return "analyzed";
    case RankStatus::empty:
        return "empty";
    case RankStatus::size_limit:
        return "size_limit";
    case RankStatus::invalid_rows:
        return "invalid_rows";
    case RankStatus::ambiguous:
        return "ambiguous";
    case RankStatus::numerical_failure:
        return "numerical_failure";
    }
    return "unknown";
}

RankDiagnostics diagnose_rank_and_nullspace(
    const DenseMatrix& matrix, const RankPolicy& policy) {
    if (policy.maximum_rows == 0U || policy.maximum_columns == 0U ||
        !(policy.roundoff_safety_factor > 0.0) ||
        !std::isfinite(policy.roundoff_safety_factor) ||
        !(policy.ambiguity_factor > 1.0) ||
        !std::isfinite(policy.ambiguity_factor) ||
        !(policy.residual_safety_factor > 0.0) ||
        !std::isfinite(policy.residual_safety_factor)) {
        throw std::invalid_argument("invalid rank policy");
    }
    RankDiagnostics result{};
    result.row_count = matrix.row_count();
    result.column_count = matrix.column_count();
    if (matrix.column_count() == 0U) {
        result.status = RankStatus::empty;
        result.basis_complete = true;
        return result;
    }
    if (matrix.row_count() > policy.maximum_rows ||
        matrix.column_count() > policy.maximum_columns) {
        result.status = RankStatus::size_limit;
        return result;
    }
    if (!std::ranges::all_of(matrix.entries(), [](double value) {
            return std::isfinite(value);
        })) {
        result.status = RankStatus::invalid_rows;
        return result;
    }
    if (matrix.row_count() == 0U) {
        result.status = RankStatus::analyzed;
        result.rank = 0U;
        result.nullity = matrix.column_count();
        result.nullspace_basis = DenseMatrix(result.nullity, result.nullity);
        for (std::size_t index = 0; index < result.nullity; ++index) {
            result.nullspace_basis(index, index) = 1.0;
        }
        result.basis_complete = true;
        return result;
    }
    const auto qr = complete_householder_cpqr(matrix);
    if (!qr.ok || qr.diagonals.empty()) {
        result.status = RankStatus::numerical_failure;
        return result;
    }
    result.diagonal_magnitudes = qr.diagonals;
    result.column_permutation = qr.permutation;
    result.threshold = policy.roundoff_safety_factor *
        static_cast<double>(std::max(matrix.row_count(), matrix.column_count())) *
        std::numeric_limits<double>::epsilon() *
        std::max(qr.diagonals.front(), std::numeric_limits<double>::min());
    result.ambiguity_lower = result.threshold / policy.ambiguity_factor;
    result.ambiguity_upper = result.threshold * policy.ambiguity_factor;
    for (const auto diagonal : qr.diagonals) {
        if (diagonal > result.threshold) {
            ++result.rank;
            result.accepted_pivot_magnitudes.push_back(diagonal);
        }
    }
    result.nullity = matrix.column_count() - result.rank;
    auto ambiguous = false;
    for (const auto diagonal : qr.diagonals) {
        ambiguous = ambiguous ||
            (diagonal >= result.ambiguity_lower &&
             diagonal <= result.ambiguity_upper);
    }
    DenseMatrix raw_basis(matrix.column_count(), result.nullity);
    try {
        for (std::size_t free = 0; free < result.nullity; ++free) {
            const auto vector = qr_null_vector(qr, result.rank, free);
            for (std::size_t row = 0; row < vector.size(); ++row) {
                raw_basis(row, free) = vector[row];
            }
        }
    } catch (const std::runtime_error&) {
        result.status = RankStatus::numerical_failure;
        return result;
    }
    const auto orthogonal_threshold = 128.0 *
        static_cast<double>(std::max(matrix.row_count(), matrix.column_count())) *
        std::numeric_limits<double>::epsilon();
    result.nullspace_basis =
        orthonormalize_columns(raw_basis, orthogonal_threshold);
    result.basis_complete =
        result.nullspace_basis.column_count() == result.nullity;
    result.normalized_null_residual = result.basis_complete
        ? normalized_product_residual(matrix, result.nullspace_basis)
        : std::numeric_limits<double>::infinity();
    const auto residual_tolerance = policy.residual_safety_factor *
        static_cast<double>(std::max(
            matrix.row_count(), matrix.column_count())) *
        std::numeric_limits<double>::epsilon();
    if (!result.basis_complete ||
        !std::isfinite(result.normalized_null_residual) ||
        result.normalized_null_residual > residual_tolerance) {
        result.status = RankStatus::numerical_failure;
    } else {
        result.status = ambiguous ? RankStatus::ambiguous : RankStatus::analyzed;
    }
    return result;
}

RigidMotionSubspace build_rigid_motion_subspace(
    std::span<const MechanicalPacket> packets) {
    const auto canonical = canonical_packets(packets);
    RigidMotionSubspace result{};
    result.packet_ids = packet_ids(canonical);
    const auto velocity_dofs =
        checked_product(canonical.size(), 3U, "rigid generator");
    result.generators = DenseMatrix(velocity_dofs, 6U);
    if (canonical.empty()) {
        return result;
    }
    Vec3d centroid{};
    for (const auto& packet : canonical) {
        centroid += packet.position_m;
    }
    centroid = centroid / static_cast<double>(canonical.size());
    const std::array<Vec3d, 3> axes{
        Vec3d{1.0, 0.0, 0.0}, Vec3d{0.0, 1.0, 0.0},
        Vec3d{0.0, 0.0, 1.0}};
    for (std::size_t packet = 0; packet < canonical.size(); ++packet) {
        const auto offset = canonical[packet].position_m - centroid;
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            result.generators(3U * packet + axis, axis) = 1.0;
            const auto rotational_velocity = cross(axes[axis], offset);
            for (std::size_t component_index = 0; component_index < 3U;
                 ++component_index) {
                result.generators(
                    3U * packet + component_index, 3U + axis) =
                    component(rotational_velocity, component_index);
            }
        }
    }
    const auto threshold = 256.0 * static_cast<double>(
        std::max<std::size_t>(velocity_dofs, 6U)) *
        std::numeric_limits<double>::epsilon();
    result.orthonormal_basis =
        orthonormalize_columns(result.generators, threshold);
    result.rank = result.orthonormal_basis.column_count();
    return result;
}

ObservabilityDiagnostics diagnose_mechanical_observability(
    const LinearizedOperator& linearized,
    std::span<const MechanicalPacket> packets,
    const RankPolicy& policy) {
    const auto canonical = packets_in_operator_order(linearized, packets);
    ObservabilityDiagnostics result{};
    result.rigid = build_rigid_motion_subspace(canonical);
    const auto normalized = normalize_operator_rows(linearized.matrix);
    if (!normalized.complete) {
        result.status = RankStatus::invalid_rows;
        result.operator_rank.status = RankStatus::invalid_rows;
        return result;
    }
    result.operator_rank =
        diagnose_rank_and_nullspace(normalized.normalized, policy);
    result.status = result.operator_rank.status;
    if (result.status != RankStatus::analyzed &&
        result.status != RankStatus::ambiguous) {
        return result;
    }
    result.normalized_rigid_residual = normalized_product_residual(
        normalized.normalized, result.rigid.orthonormal_basis);
    const auto tolerance = policy.residual_safety_factor *
        static_cast<double>(std::max(
            normalized.normalized.row_count(),
            normalized.normalized.column_count())) *
        std::numeric_limits<double>::epsilon();
    result.rigid_subspace_in_kernel =
        result.normalized_rigid_residual <= tolerance;
    if (result.rigid_subspace_in_kernel &&
        result.operator_rank.nullity >= result.rigid.rank) {
        result.nonrigid_nullity =
            result.operator_rank.nullity - result.rigid.rank;
    }

    const auto& kernel = result.operator_rank.nullspace_basis;
    DenseMatrix projected(kernel.row_count(), kernel.column_count());
    for (std::size_t column = 0; column < kernel.column_count(); ++column) {
        for (std::size_t row = 0; row < kernel.row_count(); ++row) {
            projected(row, column) = kernel(row, column);
        }
        for (std::size_t rigid_column = 0;
             rigid_column < result.rigid.orthonormal_basis.column_count();
             ++rigid_column) {
            long double coefficient = 0.0L;
            for (std::size_t row = 0; row < kernel.row_count(); ++row) {
                coefficient += static_cast<long double>(
                    result.rigid.orthonormal_basis(row, rigid_column)) *
                    projected(row, column);
            }
            for (std::size_t row = 0; row < kernel.row_count(); ++row) {
                projected(row, column) -= static_cast<double>(coefficient) *
                    result.rigid.orthonormal_basis(row, rigid_column);
            }
        }
    }
    result.nonrigid_nullspace_basis =
        orthonormalize_columns(projected, tolerance, tolerance);
    result.normalized_nonrigid_residual = normalized_product_residual(
        normalized.normalized, result.nonrigid_nullspace_basis);
    result.rigid_orthogonality_residual = normalized_cross_orthogonality(
        result.rigid.orthonormal_basis, result.nonrigid_nullspace_basis);
    if (result.rigid_subspace_in_kernel &&
        result.nonrigid_nullspace_basis.column_count() !=
            result.nonrigid_nullity) {
        result.status = RankStatus::numerical_failure;
    }
    if (!std::isfinite(result.operator_rank.normalized_null_residual) ||
        result.operator_rank.normalized_null_residual > tolerance ||
        !std::isfinite(result.normalized_nonrigid_residual) ||
        result.normalized_nonrigid_residual > tolerance ||
        !std::isfinite(result.rigid_orthogonality_residual) ||
        result.rigid_orthogonality_residual > tolerance) {
        result.status = RankStatus::numerical_failure;
    }
    result.kernel_equals_rigid_subspace =
        result.status == RankStatus::analyzed && result.rigid.rank == 6U &&
        result.rigid_subspace_in_kernel &&
        result.operator_rank.nullity == 6U &&
        result.nonrigid_nullspace_basis.column_count() == 0U;
    return result;
}

std::vector<MechanicalPacket> with_affine_velocity(
    std::span<const MechanicalPacket> packets,
    const Matrix3d& gradient_per_s,
    Vec3d intercept_m_per_s) {
    if (!finite(gradient_per_s) || !finite(intercept_m_per_s)) {
        throw std::invalid_argument("affine field must be finite");
    }
    auto result = canonical_packets(packets);
    for (auto& packet : result) {
        packet.velocity_m_per_s =
            multiply(gradient_per_s, packet.position_m) + intercept_m_per_s;
        if (!finite(packet.velocity_m_per_s)) {
            throw std::overflow_error("affine velocity overflow");
        }
    }
    return result;
}

std::vector<double> expected_affine_bond_rates_m_per_s(
    std::span<const MechanicalPacket> packets,
    std::span<const BondRelation> relations,
    const Matrix3d& gradient_per_s) {
    const auto canonical = canonical_packets(packets);
    const auto lookup = packet_lookup(canonical);
    const auto checked = validate_bonds(lookup, relations);
    if (!finite(gradient_per_s)) {
        throw std::invalid_argument("affine gradient must be finite");
    }
    std::vector<double> result;
    result.reserve(checked.size());
    for (const auto& relation : checked) {
        const auto offset = canonical[lookup.at(relation.second_id)].position_m -
            canonical[lookup.at(relation.first_id)].position_m;
        const auto length = stable_vector_norm(offset);
        if (!(length > 0.0) || !std::isfinite(length)) {
            throw std::invalid_argument("bond endpoints coincide");
        }
        const auto rate = dot(offset / length, multiply(gradient_per_s, offset));
        if (!std::isfinite(rate)) {
            throw std::overflow_error("affine bond-rate overflow");
        }
        result.push_back(rate);
    }
    return result;
}

std::vector<double> expected_affine_volume_rates_m3_per_s(
    std::span<const MechanicalPacket> packets,
    std::span<const VolumeRelation> relations,
    const Matrix3d& gradient_per_s) {
    const auto volume_operator =
        build_oriented_volume_operator(packets, relations);
    if (!finite(gradient_per_s)) {
        throw std::invalid_argument("affine gradient must be finite");
    }
    const auto trace = gradient_per_s.value[0][0] +
        gradient_per_s.value[1][1] + gradient_per_s.value[2][2];
    std::vector<double> result;
    result.reserve(volume_operator.oriented_volumes_m3.size());
    for (const auto volume : volume_operator.oriented_volumes_m3) {
        const auto rate = trace * volume;
        if (!std::isfinite(rate)) {
            throw std::overflow_error("affine volume-rate overflow");
        }
        result.push_back(rate);
    }
    return result;
}

bool is_proper_rotation(const Matrix3d& matrix, const double tolerance) noexcept {
    if (!finite(matrix) || !(tolerance >= 0.0) || !std::isfinite(tolerance)) {
        return false;
    }
    const auto gram = multiply(transpose(matrix), matrix);
    double maximum_error = 0.0;
    for (std::size_t row = 0; row < 3U; ++row) {
        for (std::size_t column = 0; column < 3U; ++column) {
            maximum_error = std::max(
                maximum_error,
                std::abs(gram.value[row][column] -
                         (row == column ? 1.0 : 0.0)));
        }
    }
    return maximum_error <= tolerance &&
        std::abs(determinant(matrix) - 1.0) <= tolerance;
}

std::vector<MechanicalPacket> similarity_transform_packets(
    std::span<const MechanicalPacket> packets,
    const Matrix3d& proper_rotation,
    Vec3d translation_m,
    const double scale) {
    if (!is_proper_rotation(proper_rotation) || !finite(translation_m) ||
        !(scale > 0.0) || !std::isfinite(scale)) {
        throw std::invalid_argument("invalid proper similarity transform");
    }
    auto result = canonical_packets(packets);
    for (auto& packet : result) {
        packet.position_m =
            scale * multiply(proper_rotation, packet.position_m) + translation_m;
        packet.velocity_m_per_s =
            scale * multiply(proper_rotation, packet.velocity_m_per_s);
        if (!finite(packet.position_m) || !finite(packet.velocity_m_per_s)) {
            throw std::overflow_error("similarity transform overflow");
        }
    }
    return result;
}

FiniteRelationComparison compare_finite_relations(
    std::span<const MechanicalPacket> reference,
    std::span<const MechanicalPacket> transformed,
    std::span<const BondRelation> bonds,
    std::span<const VolumeRelation> volumes) {
    const auto reference_bonds = build_bond_rigidity_operator(reference, bonds);
    const auto transformed_bonds = build_bond_rigidity_operator(transformed, bonds);
    const auto reference_volumes =
        build_oriented_volume_operator(reference, volumes);
    const auto transformed_volumes =
        build_oriented_volume_operator(transformed, volumes);
    if (reference_bonds.linearized.packet_ids !=
            transformed_bonds.linearized.packet_ids ||
        reference_volumes.linearized.packet_ids !=
            transformed_volumes.linearized.packet_ids) {
        throw std::invalid_argument("finite relation packet sets disagree");
    }
    FiniteRelationComparison result{};
    for (std::size_t index = 0; index < reference_bonds.lengths_m.size(); ++index) {
        const auto left = reference_bonds.lengths_m[index];
        const auto right = transformed_bonds.lengths_m[index];
        const auto error = std::abs(left - right);
        const auto denominator = std::max(
            {std::abs(left), std::abs(right),
             std::numeric_limits<double>::min()});
        result.maximum_bond_absolute_error_m =
            std::max(result.maximum_bond_absolute_error_m, error);
        result.maximum_bond_relative_error =
            std::max(result.maximum_bond_relative_error, error / denominator);
    }
    for (std::size_t index = 0;
         index < reference_volumes.oriented_volumes_m3.size(); ++index) {
        const auto left = reference_volumes.oriented_volumes_m3[index];
        const auto right = transformed_volumes.oriented_volumes_m3[index];
        const auto error = std::abs(left - right);
        const auto denominator = std::max(
            {std::abs(left), std::abs(right),
             std::numeric_limits<double>::min()});
        result.maximum_volume_absolute_error_m3 =
            std::max(result.maximum_volume_absolute_error_m3, error);
        result.maximum_volume_relative_error =
            std::max(result.maximum_volume_relative_error, error / denominator);
    }
    result.finite =
        std::isfinite(result.maximum_bond_absolute_error_m) &&
        std::isfinite(result.maximum_bond_relative_error) &&
        std::isfinite(result.maximum_volume_absolute_error_m3) &&
        std::isfinite(result.maximum_volume_relative_error);
    return result;
}

} // namespace mls::experimental::mechanical_observability
