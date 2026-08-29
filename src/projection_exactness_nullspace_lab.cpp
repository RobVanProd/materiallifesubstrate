#include "mls/projection_exactness_nullspace_lab.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <utility>

namespace mls::experimental::projection_exactness_nullspace {
namespace {

[[nodiscard]] double component(Vec3d value, std::size_t index) noexcept {
    if (index == 0U) {
        return value.x;
    }
    if (index == 1U) {
        return value.y;
    }
    return value.z;
}

void set_component(Vec3d& value, std::size_t index, double scalar) noexcept {
    if (index == 0U) {
        value.x = scalar;
    } else if (index == 1U) {
        value.y = scalar;
    } else {
        value.z = scalar;
    }
}

[[nodiscard]] bool finite(Vec3d value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) &&
        std::isfinite(value.z);
}

[[nodiscard]] double gamma_n(std::size_t operations) noexcept {
    const auto product = static_cast<double>(operations) *
        std::numeric_limits<double>::epsilon();
    if (!(product < 0.5)) {
        return std::numeric_limits<double>::infinity();
    }
    return product / (1.0 - product);
}

[[nodiscard]] double l2_norm(std::span<const double> values) noexcept {
    long double sum = 0.0L;
    for (const auto value : values) {
        sum += static_cast<long double>(value) * value;
    }
    return std::sqrt(static_cast<double>(sum));
}

[[nodiscard]] double vec_l2_norm(std::span<const Vec3d> values) noexcept {
    long double sum = 0.0L;
    for (const auto value : values) {
        sum += static_cast<long double>(value.x) * value.x;
        sum += static_cast<long double>(value.y) * value.y;
        sum += static_cast<long double>(value.z) * value.z;
    }
    return std::sqrt(static_cast<double>(sum));
}

[[nodiscard]] double vec_max_norm(std::span<const Vec3d> values) noexcept {
    double result = 0.0;
    for (const auto value : values) {
        result = std::max(result, std::abs(value.x));
        result = std::max(result, std::abs(value.y));
        result = std::max(result, std::abs(value.z));
    }
    return result;
}

[[nodiscard]] ErrorNorms normwise_equation_error_norms(
    const projection::ProjectionSystem& system,
    std::span<const Vec3d> grid_velocity,
    std::span<const Vec3d> residual,
    std::span<const double> roundoff_scales = {}) {
    ErrorNorms result{};
    result.absolute_l2 = vec_l2_norm(residual);
    result.absolute_max = vec_max_norm(residual);
    long double denominator_squared = 0.0L;
    for (std::size_t row = 0; row < system.active_nodes().size(); ++row) {
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            long double denominator = std::abs(component(
                system.consistent_rhs_kg_m_per_s()[row], axis));
            for (const auto& [column, coefficient] :
                 system.consistent_mass_rows()[row]) {
                denominator += std::abs(static_cast<long double>(coefficient) *
                    component(grid_velocity[column], axis));
            }
            denominator_squared += denominator * denominator;
        }
    }
    result.reference_l2 = std::sqrt(static_cast<double>(denominator_squared));
    result.relative_l2 = result.reference_l2 > 0.0
        ? result.absolute_l2 / result.reference_l2
        : result.absolute_l2;
    result.roundoff_scale_l2 = roundoff_scales.empty()
        ? 0.0
        : l2_norm(roundoff_scales);
    return result;
}

[[nodiscard]] ErrorNorms grid_mass_weighted_error_norms(
    const projection::ProjectionSystem& system,
    std::span<const Vec3d> error,
    std::span<const Vec3d> reference) {
    if (error.size() != system.lumped_mass_kg().size() ||
        reference.size() != error.size()) {
        throw std::invalid_argument("grid weighted diagnostic dimensions differ");
    }
    ErrorNorms result{};
    long double error_squared = 0.0L;
    long double reference_squared = 0.0L;
    long double total_mass = 0.0L;
    for (std::size_t node = 0; node < error.size(); ++node) {
        const auto mass = system.lumped_mass_kg()[node];
        error_squared += static_cast<long double>(mass) * dot(error[node], error[node]);
        reference_squared += static_cast<long double>(mass) *
            dot(reference[node], reference[node]);
        total_mass += static_cast<long double>(mass);
    }
    result.absolute_l2 = std::sqrt(static_cast<double>(error_squared));
    result.absolute_max = vec_max_norm(error);
    result.reference_l2 = std::sqrt(static_cast<double>(
        std::max(reference_squared, total_mass)));
    result.relative_l2 = result.reference_l2 > 0.0
        ? result.absolute_l2 / result.reference_l2
        : result.absolute_l2;
    return result;
}

[[nodiscard]] ErrorNorms particle_mass_weighted_error_norms(
    const projection::ProjectionSystem& system,
    std::span<const Vec3d> error,
    std::span<const Vec3d> reference,
    std::span<const double> roundoff_scales = {}) {
    if (error.size() != system.particle_mass_kg().size() ||
        reference.size() != error.size()) {
        throw std::invalid_argument("particle weighted diagnostic dimensions differ");
    }
    ErrorNorms result{};
    long double error_squared = 0.0L;
    long double reference_squared = 0.0L;
    long double roundoff_squared = 0.0L;
    long double total_mass = 0.0L;
    for (std::size_t particle = 0; particle < error.size(); ++particle) {
        const auto mass = system.particle_mass_kg()[particle];
        error_squared += static_cast<long double>(mass) *
            dot(error[particle], error[particle]);
        reference_squared += static_cast<long double>(mass) *
            dot(reference[particle], reference[particle]);
        total_mass += static_cast<long double>(mass);
        if (!roundoff_scales.empty()) {
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                const auto scale = roundoff_scales[3U * particle + axis];
                roundoff_squared += static_cast<long double>(mass) * scale * scale;
            }
        }
    }
    result.absolute_l2 = std::sqrt(static_cast<double>(error_squared));
    result.absolute_max = vec_max_norm(error);
    result.reference_l2 = std::sqrt(static_cast<double>(
        std::max(reference_squared, total_mass)));
    result.relative_l2 = result.reference_l2 > 0.0
        ? result.absolute_l2 / result.reference_l2
        : result.absolute_l2;
    result.roundoff_scale_l2 = std::sqrt(static_cast<double>(roundoff_squared));
    return result;
}

[[nodiscard]] std::vector<Vec3d> subtract_vectors(
    std::span<const Vec3d> lhs, std::span<const Vec3d> rhs) {
    if (lhs.size() != rhs.size()) {
        throw std::invalid_argument("diagnostic vector dimensions differ");
    }
    std::vector<Vec3d> result(lhs.size());
    for (std::size_t index = 0; index < lhs.size(); ++index) {
        result[index] = lhs[index] - rhs[index];
    }
    return result;
}

[[nodiscard]] std::vector<Vec3d> particle_velocities(
    const projection::ProjectionSystem& system) {
    std::vector<Vec3d> result;
    result.reserve(system.particles().size());
    for (const auto& particle : system.particles()) {
        result.push_back(particle.velocity_m_per_s);
    }
    return result;
}

[[nodiscard]] std::vector<Vec3d> reconstructed_velocities(
    const projection::ProjectionSystem& system,
    std::span<const Vec3d> grid_velocity) {
    const auto reconstructed = projection::reconstruct_centers(system, grid_velocity);
    std::vector<Vec3d> result;
    result.reserve(reconstructed.size());
    for (const auto& particle : reconstructed) {
        result.push_back(particle.velocity_m_per_s);
    }
    return result;
}

[[nodiscard]] std::vector<Vec3d> equation_residual(
    const projection::ProjectionSystem& system,
    std::span<const Vec3d> grid_velocity,
    std::vector<Vec3d>* applied_out = nullptr) {
    auto applied = projection::apply_consistent_mass(system, grid_velocity);
    auto residual = subtract_vectors(applied, system.consistent_rhs_kg_m_per_s());
    if (applied_out != nullptr) {
        *applied_out = std::move(applied);
    }
    return residual;
}

[[nodiscard]] ErrorNorms unavailable_error_norms() noexcept {
    const auto nan = std::numeric_limits<double>::quiet_NaN();
    return {nan, nan, nan, nan, nan};
}

// Portable FMA double-double arithmetic. The non-overlapping hi/lo pair has
// approximately 106 significand bits on IEEE-754 binary64 implementations.
// It is deliberately local to this diagnostic and is not an MLS state type.
struct DoubleDouble final {
    double hi{0.0};
    double lo{0.0};

    DoubleDouble() = default;
    explicit DoubleDouble(double value) : hi(value) {}
    DoubleDouble(double high, double low) : hi(high), lo(low) {}
};

[[nodiscard]] DoubleDouble normalized(double high, double low) noexcept {
    const auto sum = high + low;
    const auto error = low - (sum - high);
    return {sum, error};
}

[[nodiscard]] DoubleDouble operator+(
    DoubleDouble lhs, DoubleDouble rhs) noexcept {
    const auto sum = lhs.hi + rhs.hi;
    const auto virtual_rhs = sum - lhs.hi;
    const auto error = (lhs.hi - (sum - virtual_rhs)) +
        (rhs.hi - virtual_rhs) + lhs.lo + rhs.lo;
    return normalized(sum, error);
}

[[nodiscard]] DoubleDouble operator-(DoubleDouble value) noexcept {
    return {-value.hi, -value.lo};
}

[[nodiscard]] DoubleDouble operator-(
    DoubleDouble lhs, DoubleDouble rhs) noexcept {
    return lhs + (-rhs);
}

[[nodiscard]] DoubleDouble operator*(
    DoubleDouble lhs, DoubleDouble rhs) noexcept {
    const auto product = lhs.hi * rhs.hi;
    const auto error = std::fma(lhs.hi, rhs.hi, -product) +
        lhs.hi * rhs.lo + lhs.lo * rhs.hi + lhs.lo * rhs.lo;
    return normalized(product, error);
}

[[nodiscard]] DoubleDouble operator/(
    DoubleDouble numerator, DoubleDouble denominator) noexcept {
    const auto first = numerator.hi / denominator.hi;
    auto remainder = numerator - denominator * DoubleDouble(first);
    const auto second = remainder.hi / denominator.hi;
    remainder = remainder - denominator * DoubleDouble(second);
    const auto third = remainder.hi / denominator.hi;
    return DoubleDouble(first) + DoubleDouble(second) + DoubleDouble(third);
}

DoubleDouble& operator+=(DoubleDouble& lhs, DoubleDouble rhs) noexcept {
    lhs = lhs + rhs;
    return lhs;
}

DoubleDouble& operator-=(DoubleDouble& lhs, DoubleDouble rhs) noexcept {
    lhs = lhs - rhs;
    return lhs;
}

[[nodiscard]] DoubleDouble absolute(DoubleDouble value) noexcept {
    if (value.hi < 0.0 || (value.hi == 0.0 && value.lo < 0.0)) {
        return -value;
    }
    return value;
}

[[nodiscard]] bool greater(DoubleDouble lhs, DoubleDouble rhs) noexcept {
    return lhs.hi > rhs.hi || (lhs.hi == rhs.hi && lhs.lo > rhs.lo);
}

[[nodiscard]] bool less_equal(DoubleDouble lhs, DoubleDouble rhs) noexcept {
    return !greater(lhs, rhs);
}

[[nodiscard]] bool finite(DoubleDouble value) noexcept {
    return std::isfinite(value.hi) && std::isfinite(value.lo);
}

[[nodiscard]] double approximate(DoubleDouble value) noexcept {
    return value.hi + value.lo;
}

[[nodiscard]] ExtendedScalar extended(DoubleDouble value) noexcept {
    return {value.hi, value.lo};
}

class BigUnsigned final {
public:
    BigUnsigned() = default;
    explicit BigUnsigned(std::uint64_t value) {
        while (value != 0U) {
            limbs_.push_back(static_cast<std::uint32_t>(value % base));
            value /= base;
        }
    }

    [[nodiscard]] bool zero() const noexcept { return limbs_.empty(); }

    void multiply_small(std::uint32_t factor) {
        if (factor == 0U || zero()) {
            limbs_.clear();
            return;
        }
        std::uint64_t carry = 0U;
        for (auto& limb : limbs_) {
            const auto product = static_cast<std::uint64_t>(limb) * factor + carry;
            limb = static_cast<std::uint32_t>(product % base);
            carry = product / base;
        }
        while (carry != 0U) {
            limbs_.push_back(static_cast<std::uint32_t>(carry % base));
            carry /= base;
        }
    }

    void multiply_power(std::uint32_t factor, int exponent) {
        for (int index = 0; index < exponent; ++index) {
            multiply_small(factor);
        }
    }

    [[nodiscard]] int compare(const BigUnsigned& other) const noexcept {
        if (limbs_.size() != other.limbs_.size()) {
            return limbs_.size() < other.limbs_.size() ? -1 : 1;
        }
        for (std::size_t reverse = limbs_.size(); reverse > 0U; --reverse) {
            const auto index = reverse - 1U;
            if (limbs_[index] != other.limbs_[index]) {
                return limbs_[index] < other.limbs_[index] ? -1 : 1;
            }
        }
        return 0;
    }

    void add(const BigUnsigned& other) {
        const auto count = std::max(limbs_.size(), other.limbs_.size());
        limbs_.resize(count, 0U);
        std::uint64_t carry = 0U;
        for (std::size_t index = 0; index < count; ++index) {
            const auto rhs = index < other.limbs_.size() ? other.limbs_[index] : 0U;
            const auto sum = static_cast<std::uint64_t>(limbs_[index]) + rhs + carry;
            limbs_[index] = static_cast<std::uint32_t>(sum % base);
            carry = sum / base;
        }
        if (carry != 0U) {
            limbs_.push_back(static_cast<std::uint32_t>(carry));
        }
    }

    // Requires *this >= other.
    void subtract(const BigUnsigned& other) {
        std::int64_t borrow = 0;
        for (std::size_t index = 0; index < limbs_.size(); ++index) {
            const auto rhs = index < other.limbs_.size()
                ? static_cast<std::int64_t>(other.limbs_[index])
                : 0;
            auto difference = static_cast<std::int64_t>(limbs_[index]) - rhs - borrow;
            if (difference < 0) {
                difference += static_cast<std::int64_t>(base);
                borrow = 1;
            } else {
                borrow = 0;
            }
            limbs_[index] = static_cast<std::uint32_t>(difference);
        }
        while (!limbs_.empty() && limbs_.back() == 0U) {
            limbs_.pop_back();
        }
    }

    [[nodiscard]] std::string decimal_digits() const {
        if (zero()) {
            return "0";
        }
        auto result = std::to_string(limbs_.back());
        for (std::size_t reverse = limbs_.size() - 1U; reverse > 0U; --reverse) {
            auto chunk = std::to_string(limbs_[reverse - 1U]);
            result.append(9U - chunk.size(), '0');
            result += chunk;
        }
        return result;
    }

private:
    static constexpr std::uint64_t base = UINT64_C(1000000000);
    std::vector<std::uint32_t> limbs_{};
};

struct BinaryTerm final {
    bool negative{false};
    std::uint64_t mantissa{0U};
    int exponent_two{0};
};

[[nodiscard]] BinaryTerm decompose_binary64(double value) noexcept {
    const auto bits = std::bit_cast<std::uint64_t>(value);
    const auto exponent_bits = static_cast<unsigned>((bits >> 52U) & UINT64_C(0x7ff));
    const auto fraction = bits & UINT64_C(0x000fffffffffffff);
    BinaryTerm result{};
    result.negative = (bits >> 63U) != 0U;
    if (exponent_bits == 0U) {
        result.mantissa = fraction;
        result.exponent_two = -1074;
    } else if (exponent_bits != 0x7ffU) {
        result.mantissa = fraction | UINT64_C(0x0010000000000000);
        result.exponent_two = static_cast<int>(exponent_bits) - 1023 - 52;
    }
    return result;
}

struct ExactBinarySum final {
    bool negative{false};
    BigUnsigned magnitude{};
    int exponent_two{0};
};

[[nodiscard]] ExactBinarySum exact_binary_sum(double lhs, double rhs) {
    const auto left = decompose_binary64(lhs);
    const auto right = decompose_binary64(rhs);
    if (left.mantissa == 0U && right.mantissa == 0U) {
        return {};
    }
    const auto common_exponent = left.mantissa == 0U ? right.exponent_two
        : right.mantissa == 0U ? left.exponent_two
        : std::min(left.exponent_two, right.exponent_two);
    auto left_magnitude = BigUnsigned(left.mantissa);
    auto right_magnitude = BigUnsigned(right.mantissa);
    if (left.mantissa != 0U) {
        left_magnitude.multiply_power(2U, left.exponent_two - common_exponent);
    }
    if (right.mantissa != 0U) {
        right_magnitude.multiply_power(2U, right.exponent_two - common_exponent);
    }
    ExactBinarySum result{};
    result.exponent_two = common_exponent;
    if (left.mantissa == 0U) {
        result.negative = right.negative;
        result.magnitude = std::move(right_magnitude);
    } else if (right.mantissa == 0U) {
        result.negative = left.negative;
        result.magnitude = std::move(left_magnitude);
    } else if (left.negative == right.negative) {
        result.negative = left.negative;
        left_magnitude.add(right_magnitude);
        result.magnitude = std::move(left_magnitude);
    } else {
        const auto ordering = left_magnitude.compare(right_magnitude);
        if (ordering >= 0) {
            left_magnitude.subtract(right_magnitude);
            result.negative = left.negative;
            result.magnitude = std::move(left_magnitude);
        } else {
            right_magnitude.subtract(left_magnitude);
            result.negative = right.negative;
            result.magnitude = std::move(right_magnitude);
        }
    }
    if (result.magnitude.zero()) {
        result.negative = false;
    }
    return result;
}

[[nodiscard]] DoubleDouble dd_sqrt(DoubleDouble value) noexcept {
    if (value.hi == 0.0 && value.lo == 0.0) {
        return {};
    }
    auto estimate = DoubleDouble(std::sqrt(std::max(0.0, value.hi)));
    // Two Newton refinements are enough to fill the double-double mantissa.
    estimate = DoubleDouble(0.5) * (estimate + value / estimate);
    estimate = DoubleDouble(0.5) * (estimate + value / estimate);
    return estimate;
}

struct DdErrorAccumulator final {
    DoubleDouble squared{};
    DoubleDouble maximum{};
    DoubleDouble reference_squared{};
    DoubleDouble weight_sum{};

    void add(
        DoubleDouble error,
        DoubleDouble reference,
        DoubleDouble weight = DoubleDouble(1.0)) noexcept {
        const auto magnitude = absolute(error);
        if (greater(magnitude, maximum)) {
            maximum = magnitude;
        }
        squared += weight * error * error;
        reference_squared += weight * reference * reference;
        weight_sum += weight;
    }
};

[[nodiscard]] ErrorNorms finish(
    const DdErrorAccumulator& accumulator,
    bool apply_unit_reference_floor = false) noexcept {
    ErrorNorms result{};
    result.absolute_l2 = approximate(dd_sqrt(accumulator.squared));
    result.absolute_max = approximate(accumulator.maximum);
    const auto reference_squared = apply_unit_reference_floor &&
            greater(accumulator.weight_sum, accumulator.reference_squared)
        ? accumulator.weight_sum
        : accumulator.reference_squared;
    result.reference_l2 = approximate(dd_sqrt(reference_squared));
    result.relative_l2 = result.reference_l2 > 0.0
        ? result.absolute_l2 / result.reference_l2
        : result.absolute_l2;
    return result;
}

struct AxisBasis final {
    double weight{0.0};
    double derivative_m_inv{0.0};
};

[[nodiscard]] AxisBasis quadratic_axis_basis(
    double particle_coordinate_m,
    double node_coordinate_m,
    double spacing_m) noexcept {
    const auto relative = (particle_coordinate_m - node_coordinate_m) / spacing_m;
    const auto magnitude = std::abs(relative);
    if (magnitude < 0.5) {
        return {
            0.75 - relative * relative,
            -2.0 * relative / spacing_m,
        };
    }
    if (magnitude < 1.5) {
        const auto distance = 1.5 - magnitude;
        const auto sign = std::copysign(1.0, relative);
        return {
            0.5 * distance * distance,
            -distance * sign / spacing_m,
        };
    }
    return {};
}

struct BasisGradient final {
    double reconstructed_weight{0.0};
    Vec3d gradient_m_inv{};
};

[[nodiscard]] BasisGradient basis_gradient(
    Vec3d particle_m, Vec3d node_m, double spacing_m) noexcept {
    const auto x = quadratic_axis_basis(particle_m.x, node_m.x, spacing_m);
    const auto y = quadratic_axis_basis(particle_m.y, node_m.y, spacing_m);
    const auto z = quadratic_axis_basis(particle_m.z, node_m.z, spacing_m);
    return {
        x.weight * y.weight * z.weight,
        {
            x.derivative_m_inv * y.weight * z.weight,
            x.weight * y.derivative_m_inv * z.weight,
            x.weight * y.weight * z.derivative_m_inv,
        },
    };
}

[[nodiscard]] double matrix_frobenius_norm(
    const projection::ProjectionSystem& system) noexcept {
    long double squared = 0.0L;
    for (const auto& row : system.consistent_mass_rows()) {
        for (const auto& [column, coefficient] : row) {
            static_cast<void>(column);
            squared += static_cast<long double>(coefficient) * coefficient;
        }
    }
    return std::sqrt(static_cast<double>(squared));
}

struct PivotedQr final {
    bool ok{false};
    std::size_t rows{0};
    std::size_t columns{0};
    std::size_t rank{0};
    std::vector<double> factor{};
    std::vector<std::size_t> permutation{};
    double largest_diagonal{0.0};
    double smallest_accepted_diagonal{0.0};
    double frobenius_norm{0.0};
    double rank_threshold{0.0};
};

[[nodiscard]] PivotedQr householder_column_pivoted_qr(
    std::vector<double> matrix,
    std::size_t rows,
    std::size_t columns,
    double rank_roundoff_safety_factor) {
    PivotedQr result{};
    result.rows = rows;
    result.columns = columns;
    result.factor = std::move(matrix);
    result.permutation.resize(columns);
    std::iota(result.permutation.begin(), result.permutation.end(), std::size_t{0});

    long double frobenius_squared = 0.0L;
    for (const auto value : result.factor) {
        frobenius_squared += static_cast<long double>(value) * value;
    }
    result.frobenius_norm = std::sqrt(static_cast<double>(frobenius_squared));
    if (!std::isfinite(result.frobenius_norm)) {
        return result;
    }
    if (rows == 0U || columns == 0U) {
        result.ok = true;
        return result;
    }

    double largest_initial_column_norm = 0.0;
    for (std::size_t column = 0; column < columns; ++column) {
        long double squared = 0.0L;
        for (std::size_t row = 0; row < rows; ++row) {
            const auto value = result.factor[row * columns + column];
            squared += static_cast<long double>(value) * value;
        }
        largest_initial_column_norm = std::max(
            largest_initial_column_norm, std::sqrt(static_cast<double>(squared)));
    }
    const auto threshold = rank_roundoff_safety_factor *
        static_cast<double>(std::max(rows, columns)) *
        std::numeric_limits<double>::epsilon() *
        std::max(largest_initial_column_norm,
                 std::numeric_limits<double>::min());
    result.rank_threshold = threshold;
    const auto steps = std::min(rows, columns);
    result.smallest_accepted_diagonal = std::numeric_limits<double>::infinity();

    for (std::size_t step = 0; step < steps; ++step) {
        auto selected = step;
        long double selected_squared = -1.0L;
        for (std::size_t column = step; column < columns; ++column) {
            long double squared = 0.0L;
            for (std::size_t row = step; row < rows; ++row) {
                const auto value = result.factor[row * columns + column];
                squared += static_cast<long double>(value) * value;
            }
            if (squared > selected_squared) {
                selected_squared = squared;
                selected = column;
            }
        }
        const auto selected_norm = std::sqrt(
            static_cast<double>(std::max(0.0L, selected_squared)));
        if (!(selected_norm > threshold)) {
            break;
        }
        if (selected != step) {
            for (std::size_t row = 0; row < rows; ++row) {
                std::swap(
                    result.factor[row * columns + step],
                    result.factor[row * columns + selected]);
            }
            std::swap(result.permutation[step], result.permutation[selected]);
        }

        long double norm_squared = 0.0L;
        for (std::size_t row = step; row < rows; ++row) {
            const auto value = result.factor[row * columns + step];
            norm_squared += static_cast<long double>(value) * value;
        }
        const auto norm = std::sqrt(static_cast<double>(norm_squared));
        if (!(norm > threshold) || !std::isfinite(norm)) {
            break;
        }
        const auto first = result.factor[step * columns + step];
        const auto alpha = first >= 0.0 ? -norm : norm;
        std::vector<double> reflector(rows - step);
        for (std::size_t row = step; row < rows; ++row) {
            reflector[row - step] = result.factor[row * columns + step];
        }
        reflector.front() -= alpha;
        long double reflector_squared = 0.0L;
        for (const auto value : reflector) {
            reflector_squared += static_cast<long double>(value) * value;
        }
        if (!(reflector_squared > 0.0L)) {
            return result;
        }
        for (std::size_t column = step; column < columns; ++column) {
            long double dot_product = 0.0L;
            for (std::size_t row = step; row < rows; ++row) {
                dot_product += static_cast<long double>(reflector[row - step]) *
                    result.factor[row * columns + column];
            }
            const auto scale = static_cast<double>(2.0L * dot_product /
                                                   reflector_squared);
            for (std::size_t row = step; row < rows; ++row) {
                result.factor[row * columns + column] -=
                    scale * reflector[row - step];
            }
        }
        result.factor[step * columns + step] = alpha;
        for (std::size_t row = step + 1U; row < rows; ++row) {
            result.factor[row * columns + step] = 0.0;
        }
        const auto diagonal = std::abs(alpha);
        result.largest_diagonal = std::max(result.largest_diagonal, diagonal);
        result.smallest_accepted_diagonal = std::min(
            result.smallest_accepted_diagonal, diagonal);
        ++result.rank;
    }
    if (result.rank == 0U) {
        result.smallest_accepted_diagonal = 0.0;
    }
    result.ok = std::ranges::all_of(result.factor, [](double value) {
        return std::isfinite(value);
    });
    return result;
}

[[nodiscard]] std::vector<double> qr_null_vector(
    const PivotedQr& qr, std::size_t free_offset) {
    const auto free_column = qr.rank + free_offset;
    std::vector<double> permuted(qr.columns, 0.0);
    permuted[free_column] = 1.0;
    for (std::size_t reverse = qr.rank; reverse > 0U; --reverse) {
        const auto row = reverse - 1U;
        long double rhs = 0.0L;
        for (std::size_t column = row + 1U; column < qr.columns; ++column) {
            rhs += static_cast<long double>(
                qr.factor[row * qr.columns + column]) * permuted[column];
        }
        permuted[row] = -static_cast<double>(rhs) /
            qr.factor[row * qr.columns + row];
    }
    std::vector<double> result(qr.columns, 0.0);
    for (std::size_t current = 0; current < qr.columns; ++current) {
        result[qr.permutation[current]] = permuted[current];
    }
    const auto maximum = std::ranges::max(
        result, {}, [](double value) { return std::abs(value); });
    const auto magnitude = std::abs(maximum);
    if (!(magnitude > 0.0) || !std::isfinite(magnitude)) {
        throw std::runtime_error("rank-revealing QR produced an invalid null vector");
    }
    for (auto& value : result) {
        value /= magnitude;
    }
    return result;
}

[[nodiscard]] double scalar_mass_image_l2(
    const projection::ProjectionSystem& system,
    std::span<const double> mode) {
    long double squared = 0.0L;
    for (const auto& row : system.consistent_mass_rows()) {
        long double value = 0.0L;
        for (const auto& [column, coefficient] : row) {
            value += static_cast<long double>(coefficient) * mode[column];
        }
        squared += value * value;
    }
    return std::sqrt(static_cast<double>(squared));
}

[[nodiscard]] std::pair<double, double> scalar_center_image_norms(
    const projection::ProjectionSystem& system,
    std::span<const double> mode) {
    long double squared = 0.0L;
    double maximum = 0.0;
    for (const auto& stencil : system.particle_stencils()) {
        long double value = 0.0L;
        for (const auto& entry : stencil) {
            value += static_cast<long double>(entry.weight) * mode[entry.node_index];
        }
        squared += value * value;
        maximum = std::max(maximum, std::abs(static_cast<double>(value)));
    }
    return {std::sqrt(static_cast<double>(squared)), maximum};
}

} // namespace

Vec3d evaluate(const AffineVelocityField& field, Vec3d position_m) noexcept {
    return multiply(field.gradient_per_s, position_m) + field.intercept_m_per_s;
}

BasisWeightGradient evaluate_quadratic_bspline_basis(
    Vec3d particle_position_m,
    Vec3d node_position_m,
    double grid_spacing_m) {
    if (!finite(particle_position_m) || !finite(node_position_m) ||
        !(grid_spacing_m > 0.0) || !std::isfinite(grid_spacing_m)) {
        throw std::invalid_argument("invalid quadratic basis diagnostic input");
    }
    const auto found = basis_gradient(
        particle_position_m, node_position_m, grid_spacing_m);
    return {found.reconstructed_weight, found.gradient_m_inv};
}

std::string canonical_decimal(ExtendedScalar value, std::size_t significant_digits) {
    if (significant_digits == 0U || significant_digits > 1'000U) {
        throw std::invalid_argument("canonical decimal digit count is out of range");
    }
    if (std::isnan(value.hi) || std::isnan(value.lo)) {
        return "nan";
    }
    if (std::isinf(value.hi) || std::isinf(value.lo)) {
        const auto sum = value.hi + value.lo;
        if (std::isnan(sum)) {
            return "nan";
        }
        return std::signbit(sum) ? "-inf" : "+inf";
    }
    auto exact = exact_binary_sum(value.hi, value.lo);
    if (exact.magnitude.zero()) {
        std::string zero = "0";
        if (significant_digits > 1U) {
            zero += '.';
            zero.append(significant_digits - 1U, '0');
        }
        return zero + "e+0";
    }

    std::size_t decimal_scale = 0U;
    if (exact.exponent_two >= 0) {
        exact.magnitude.multiply_power(2U, exact.exponent_two);
    } else {
        const auto scale = -exact.exponent_two;
        exact.magnitude.multiply_power(5U, scale);
        decimal_scale = static_cast<std::size_t>(scale);
    }
    auto digits = exact.magnitude.decimal_digits();
    auto exponent_ten = static_cast<long long>(digits.size()) -
        static_cast<long long>(decimal_scale) - 1LL;

    if (digits.size() > significant_digits) {
        const auto round_up = digits[significant_digits] >= '5';
        digits.resize(significant_digits);
        if (round_up) {
            auto carry = true;
            for (std::size_t reverse = digits.size(); reverse > 0U && carry; --reverse) {
                auto& digit = digits[reverse - 1U];
                if (digit == '9') {
                    digit = '0';
                } else {
                    ++digit;
                    carry = false;
                }
            }
            if (carry) {
                digits.insert(digits.begin(), '1');
                digits.resize(significant_digits);
                ++exponent_ten;
            }
        }
    } else if (digits.size() < significant_digits) {
        digits.append(significant_digits - digits.size(), '0');
    }

    std::string result;
    if (exact.negative) {
        result.push_back('-');
    }
    result.push_back(digits.front());
    if (significant_digits > 1U) {
        result.push_back('.');
        result.append(digits.begin() + 1, digits.end());
    }
    result.push_back('e');
    result.push_back(exponent_ten < 0 ? '-' : '+');
    const auto magnitude = exponent_ten < 0 ? -exponent_ten : exponent_ten;
    result += std::to_string(magnitude);
    return result;
}

AnalyticAffineWitness evaluate_analytic_affine_witness(
    const projection::ProjectionSystem& system,
    const AffineVelocityField& field) {
    AnalyticAffineWitness result{};
    const auto node_count = system.active_nodes().size();
    result.analytic_grid_velocity_m_per_s.reserve(node_count);
    for (const auto position : system.active_node_positions_m()) {
        const auto velocity = evaluate(field, position);
        if (!finite(velocity)) {
            throw std::overflow_error("affine witness grid value is non-finite");
        }
        result.analytic_grid_velocity_m_per_s.push_back(velocity);
    }

    const auto equation = equation_residual(
        system,
        result.analytic_grid_velocity_m_per_s,
        &result.mass_times_analytic_grid_kg_m_per_s);
    std::vector<double> equation_roundoff;
    equation_roundoff.reserve(3U * node_count);
    std::vector<std::size_t> rhs_contributions(node_count, 0U);
    for (const auto& stencil : system.particle_stencils()) {
        result.maximum_particle_stencil_size = std::max(
            result.maximum_particle_stencil_size, stencil.size());
        for (const auto& entry : stencil) {
            ++rhs_contributions[entry.node_index];
        }
    }
    for (std::size_t row = 0; row < node_count; ++row) {
        result.maximum_matrix_row_nonzeros = std::max(
            result.maximum_matrix_row_nonzeros,
            system.consistent_mass_rows()[row].size());
        result.maximum_rhs_particle_contributions_per_row = std::max(
            result.maximum_rhs_particle_contributions_per_row,
            rhs_contributions[row]);
        const auto operation_count = system.consistent_mass_rows()[row].size() +
            rhs_contributions[row] + 8U;
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            long double absolute_sum = std::abs(component(
                system.consistent_rhs_kg_m_per_s()[row], axis));
            for (const auto& [column, coefficient] :
                 system.consistent_mass_rows()[row]) {
                absolute_sum += std::abs(static_cast<long double>(coefficient) *
                    component(result.analytic_grid_velocity_m_per_s[column], axis));
            }
            equation_roundoff.push_back(
                gamma_n(operation_count) * static_cast<double>(absolute_sum));
        }
    }
    result.assembled_equation = normwise_equation_error_norms(
        system,
        result.analytic_grid_velocity_m_per_s,
        equation,
        equation_roundoff);

    result.reconstructed_particle_velocity_m_per_s = reconstructed_velocities(
        system, result.analytic_grid_velocity_m_per_s);
    const auto expected_particles = particle_velocities(system);
    const auto particle_error = subtract_vectors(
        result.reconstructed_particle_velocity_m_per_s, expected_particles);
    std::vector<double> particle_roundoff;
    particle_roundoff.reserve(3U * system.particles().size());
    for (std::size_t particle = 0; particle < system.particles().size(); ++particle) {
        const auto& stencil = system.particle_stencils()[particle];
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            long double absolute_sum = std::abs(
                component(expected_particles[particle], axis));
            for (const auto& entry : stencil) {
                absolute_sum += std::abs(static_cast<long double>(entry.weight) *
                    component(result.analytic_grid_velocity_m_per_s[entry.node_index], axis));
            }
            particle_roundoff.push_back(
                gamma_n(stencil.size() + 12U) * static_cast<double>(absolute_sum));
        }
    }
    result.particle_reconstruction = particle_mass_weighted_error_norms(
        system, particle_error, expected_particles, particle_roundoff);

    long double partition_scale_squared = 0.0L;
    long double linear_scale_squared = 0.0L;
    long double derivative_scale_squared = 0.0L;
    for (std::size_t particle = 0; particle < system.particles().size(); ++particle) {
        long double partition = 0.0L;
        Vec3d reproduced{};
        Vec3d derivative_partition{};
        long double partition_abs = 0.0L;
        std::array<long double, 3> linear_abs{};
        std::array<long double, 3> derivative_abs{};
        for (const auto& entry : system.particle_stencils()[particle]) {
            partition += entry.weight;
            partition_abs += std::abs(entry.weight);
            const auto node = system.active_node_positions_m()[entry.node_index];
            reproduced += entry.weight * node;
            const auto gradient = basis_gradient(
                system.particles()[particle].position_m,
                node,
                system.config().grid_spacing_m);
            derivative_partition += gradient.gradient_m_inv;
            derivative_abs[0] += std::abs(gradient.gradient_m_inv.x);
            derivative_abs[1] += std::abs(gradient.gradient_m_inv.y);
            derivative_abs[2] += std::abs(gradient.gradient_m_inv.z);
            linear_abs[0] += std::abs(static_cast<long double>(entry.weight) * node.x);
            linear_abs[1] += std::abs(static_cast<long double>(entry.weight) * node.y);
            linear_abs[2] += std::abs(static_cast<long double>(entry.weight) * node.z);
        }
        result.partition_unity_max_residual = std::max(
            result.partition_unity_max_residual,
            std::abs(static_cast<double>(partition - 1.0L)));
        const auto linear_error = reproduced - system.particles()[particle].position_m;
        result.linear_reproduction_max_residual_m = std::max(
            result.linear_reproduction_max_residual_m,
            vec_max_norm(std::span(&linear_error, std::size_t{1})));
        result.derivative_partition_max_residual_m_inv = std::max(
            result.derivative_partition_max_residual_m_inv,
            vec_max_norm(std::span(&derivative_partition, std::size_t{1})));
        const auto partition_bound = gamma_n(
            system.particle_stencils()[particle].size() + 2U) *
            static_cast<double>(partition_abs + 1.0L);
        partition_scale_squared += static_cast<long double>(partition_bound) *
            partition_bound;
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            const auto bound = gamma_n(
                system.particle_stencils()[particle].size() + 6U) *
                static_cast<double>(linear_abs[axis] +
                    std::abs(component(system.particles()[particle].position_m, axis)));
            linear_scale_squared += static_cast<long double>(bound) * bound;
            const auto derivative_bound = gamma_n(
                8U * system.particle_stencils()[particle].size() + 8U) *
                static_cast<double>(derivative_abs[axis]);
            derivative_scale_squared +=
                static_cast<long double>(derivative_bound) * derivative_bound;
        }
    }
    result.partition_unity_roundoff_scale =
        std::sqrt(static_cast<double>(partition_scale_squared));
    result.linear_reproduction_roundoff_scale_m =
        std::sqrt(static_cast<double>(linear_scale_squared));
    result.derivative_partition_roundoff_scale_m_inv =
        std::sqrt(static_cast<double>(derivative_scale_squared));
    result.assembled_equation_normalization =
        "||M g-q||_2 / || |M||g|+|q| ||_2";
    result.reconstruction_normalization =
        "sqrt(sum_p m_p |Sg_p-V_p|^2) / max(sqrt(sum_p m_p |V_p|^2),sqrt(sum_p m_p)*(1 m/s))";
    result.roundoff_model =
        "binary64 Higham gamma_n=sum-operation-count*epsilon/(1-n*epsilon); "
        "scales include actual absolute summands and are diagnostic, not acceptance tolerances";
    return result;
}

FullSolveDiagnostics diagnose_affine_full_solve(
    const projection::ProjectionSystem& system,
    const projection::ProjectionResult& result,
    const AffineVelocityField& field) {
    FullSolveDiagnostics diagnostics{};
    diagnostics.solver_status = result.status;
    diagnostics.raw_condition_value = result.diagnostics.raw_condition_estimate;
    diagnostics.preconditioned_condition_value =
        result.diagnostics.preconditioned_condition_estimate;
    diagnostics.condition_is_certified = false;
    diagnostics.condition_is_ritz_or_floating_estimate =
        result.diagnostics.condition_estimated;
    diagnostics.condition_method = result.diagnostics.numerical_rank_method;
    diagnostics.backward_error_normalization =
        "||M v_hat-q||_2 / (||M||_F ||v_hat||_2+||q||_2)";
    diagnostics.grid_forward_error_normalization =
        "sqrt(sum_i D_i |v_hat_i-g_i|^2) / max(sqrt(sum_i D_i |g_i|^2),sqrt(sum_i D_i)*(1 m/s))";
    diagnostics.reconstruction_error_normalization =
        "sqrt(sum_p m_p |S v_hat_p-V_p|^2) / max(sqrt(sum_p m_p |V_p|^2),sqrt(sum_p m_p)*(1 m/s))";
    diagnostics.grid_solution_available =
        result.grid_velocity_m_per_s.size() == system.active_nodes().size();
    diagnostics.component_absolute_backward_error.fill(
        std::numeric_limits<double>::quiet_NaN());
    diagnostics.component_normalized_backward_error.fill(
        std::numeric_limits<double>::quiet_NaN());
    diagnostics.raw_condition_times_residual.fill(
        std::numeric_limits<double>::quiet_NaN());
    diagnostics.preconditioned_condition_times_residual.fill(
        std::numeric_limits<double>::quiet_NaN());
    if (!diagnostics.grid_solution_available) {
        diagnostics.backward_error = unavailable_error_norms();
        diagnostics.grid_forward_error = unavailable_error_norms();
        diagnostics.particle_reconstruction_error = unavailable_error_norms();
        return diagnostics;
    }

    const auto residual = equation_residual(
        system, result.grid_velocity_m_per_s);
    diagnostics.backward_error.absolute_l2 = vec_l2_norm(residual);
    diagnostics.backward_error.absolute_max = vec_max_norm(residual);
    const auto matrix_frobenius = matrix_frobenius_norm(system);
    const auto grid_l2 = vec_l2_norm(result.grid_velocity_m_per_s);
    const auto rhs_l2 = vec_l2_norm(system.consistent_rhs_kg_m_per_s());
    diagnostics.backward_error.reference_l2 =
        matrix_frobenius * grid_l2 + rhs_l2;
    diagnostics.backward_error.relative_l2 =
        diagnostics.backward_error.reference_l2 > 0.0
        ? diagnostics.backward_error.absolute_l2 /
            diagnostics.backward_error.reference_l2
        : diagnostics.backward_error.absolute_l2;
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        long double residual_squared = 0.0L;
        long double solution_squared = 0.0L;
        long double rhs_squared = 0.0L;
        for (std::size_t row = 0; row < residual.size(); ++row) {
            const auto residual_value = component(residual[row], axis);
            const auto rhs_value = component(
                system.consistent_rhs_kg_m_per_s()[row], axis);
            residual_squared += static_cast<long double>(residual_value) * residual_value;
            rhs_squared += static_cast<long double>(rhs_value) * rhs_value;
            const auto solution_value = component(
                result.grid_velocity_m_per_s[row], axis);
            solution_squared +=
                static_cast<long double>(solution_value) * solution_value;
        }
        const auto absolute = std::sqrt(static_cast<double>(residual_squared));
        const auto scale = matrix_frobenius *
                std::sqrt(static_cast<double>(solution_squared)) +
            std::sqrt(static_cast<double>(rhs_squared));
        const auto normalized = scale > 0.0 ? absolute / scale : absolute;
        diagnostics.component_absolute_backward_error[axis] = absolute;
        diagnostics.component_normalized_backward_error[axis] = normalized;
        diagnostics.raw_condition_times_residual[axis] =
            diagnostics.raw_condition_value * normalized;
        diagnostics.preconditioned_condition_times_residual[axis] =
            diagnostics.preconditioned_condition_value * normalized;
    }

    std::vector<Vec3d> analytic_grid;
    analytic_grid.reserve(system.active_nodes().size());
    for (const auto position : system.active_node_positions_m()) {
        analytic_grid.push_back(evaluate(field, position));
    }
    const auto grid_error = subtract_vectors(
        result.grid_velocity_m_per_s, analytic_grid);
    diagnostics.grid_forward_error = grid_mass_weighted_error_norms(
        system, grid_error, analytic_grid);

    const auto reconstructed = reconstructed_velocities(
        system, result.grid_velocity_m_per_s);
    const auto expected = particle_velocities(system);
    diagnostics.particle_reconstruction_error = particle_mass_weighted_error_norms(
        system, subtract_vectors(reconstructed, expected), expected);
    return diagnostics;
}

projection::ProjectionResult run_legacy_pcg_control(
    const projection::ProjectionSystem& system,
    const projection::ProjectionSolvePolicy& policy) {
    return projection::project_centers(
        system, projection::ProjectionCandidate::full_consistent, policy);
}

std::string_view status_name(HighPrecisionStatus status) noexcept {
    switch (status) {
    case HighPrecisionStatus::solved:
        return "solved";
    case HighPrecisionStatus::empty:
        return "empty";
    case HighPrecisionStatus::size_limit:
        return "size_limit";
    case HighPrecisionStatus::rank_deficient:
        return "rank_deficient";
    case HighPrecisionStatus::numerical_failure:
        return "numerical_failure";
    }
    return "unknown";
}

HighPrecisionSolveResult solve_affine_high_precision(
    const projection::ProjectionSystem& system,
    const AffineVelocityField& field,
    const HighPrecisionSolvePolicy& policy) {
    if (policy.maximum_nodes == 0U ||
        !(policy.rank_roundoff_safety_factor > 0.0) ||
        !std::isfinite(policy.rank_roundoff_safety_factor)) {
        throw std::invalid_argument("invalid high-precision solve policy");
    }
    HighPrecisionSolveResult result{};
    result.node_count = system.active_nodes().size();
    result.arithmetic_method =
        "portable IEEE-754 FMA double-double, non-overlapping hi/lo, approximately 106 significand bits";
    result.factorization_method =
        "deterministic dense complete-pivot Gaussian elimination; numerical rank threshold=2^12*n*2^-104*max|M_ij| by frozen default; no shift, regularization, node drop, or basis change";
    result.backward_error_normalization =
        "||M v_hp-q||_2 / (||M||_F ||v_hp||_2+||q||_2), evaluated in double-double";
    result.grid_forward_error_normalization =
        "sqrt(sum_i D_i |v_hp_i-g_i|^2) / max(sqrt(sum_i D_i |g_i|^2),sqrt(sum_i D_i)*(1 m/s)), evaluated in double-double";
    result.reconstruction_error_normalization =
        "sqrt(sum_p m_p |S v_hp_p-V_p|^2) / max(sqrt(sum_p m_p |V_p|^2),sqrt(sum_p m_p)*(1 m/s)), evaluated in double-double";
    if (result.node_count == 0U) {
        result.status = HighPrecisionStatus::empty;
        return result;
    }
    if (result.node_count > policy.maximum_nodes) {
        result.status = HighPrecisionStatus::size_limit;
        return result;
    }

    const auto count = result.node_count;
    std::vector<DoubleDouble> matrix(count * count);
    DoubleDouble largest_matrix_entry{};
    for (std::size_t row = 0; row < count; ++row) {
        for (const auto& [column, coefficient] :
             system.consistent_mass_rows()[row]) {
            matrix[row * count + column] = DoubleDouble(coefficient);
            const auto magnitude = absolute(DoubleDouble(coefficient));
            if (greater(magnitude, largest_matrix_entry)) {
                largest_matrix_entry = magnitude;
            }
        }
    }
    std::array<std::vector<DoubleDouble>, 3> rhs;
    for (auto& values : rhs) {
        values.resize(count);
    }
    for (std::size_t row = 0; row < count; ++row) {
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            rhs[axis][row] = DoubleDouble(component(
                system.consistent_rhs_kg_m_per_s()[row], axis));
        }
    }
    result.column_permutation.resize(count);
    result.row_permutation.resize(count);
    std::iota(
        result.column_permutation.begin(),
        result.column_permutation.end(),
        std::size_t{0});
    std::iota(
        result.row_permutation.begin(),
        result.row_permutation.end(),
        std::size_t{0});
    const auto threshold = DoubleDouble(policy.rank_roundoff_safety_factor) *
        DoubleDouble(static_cast<double>(count)) *
        DoubleDouble(std::ldexp(1.0, -104)) * largest_matrix_entry;
    result.numerical_rank_threshold = extended(threshold);
    DoubleDouble largest_pivot{};
    DoubleDouble smallest_pivot{
        std::numeric_limits<double>::infinity(), 0.0};

    for (std::size_t step = 0; step < count; ++step) {
        auto pivot_row = step;
        auto pivot_column = step;
        DoubleDouble pivot_magnitude{};
        for (std::size_t row = step; row < count; ++row) {
            for (std::size_t column = step; column < count; ++column) {
                const auto magnitude = absolute(matrix[row * count + column]);
                if (greater(magnitude, pivot_magnitude)) {
                    pivot_magnitude = magnitude;
                    pivot_row = row;
                    pivot_column = column;
                }
            }
        }
        if (!finite(pivot_magnitude)) {
            result.status = HighPrecisionStatus::numerical_failure;
            return result;
        }
        if (less_equal(pivot_magnitude, threshold)) {
            result.status = HighPrecisionStatus::rank_deficient;
            result.threshold_rank = step;
            result.largest_absolute_pivot = extended(largest_pivot);
            result.smallest_accepted_absolute_pivot = step == 0U
                ? ExtendedScalar{}
                : extended(smallest_pivot);
            result.pivot_ratio_estimate = step == 0U
                ? std::numeric_limits<double>::infinity()
                : approximate(largest_pivot / smallest_pivot);
            return result;
        }
        if (pivot_row != step) {
            for (std::size_t column = 0; column < count; ++column) {
                std::swap(
                    matrix[step * count + column],
                    matrix[pivot_row * count + column]);
            }
            for (auto& values : rhs) {
                std::swap(values[step], values[pivot_row]);
            }
            std::swap(
                result.row_permutation[step], result.row_permutation[pivot_row]);
        }
        if (pivot_column != step) {
            for (std::size_t row = 0; row < count; ++row) {
                std::swap(
                    matrix[row * count + step],
                    matrix[row * count + pivot_column]);
            }
            std::swap(
                result.column_permutation[step],
                result.column_permutation[pivot_column]);
        }
        if (greater(pivot_magnitude, largest_pivot)) {
            largest_pivot = pivot_magnitude;
        }
        if (greater(smallest_pivot, pivot_magnitude)) {
            smallest_pivot = pivot_magnitude;
        }
        ++result.threshold_rank;
        const auto pivot = matrix[step * count + step];
        for (std::size_t row = step + 1U; row < count; ++row) {
            const auto factor = matrix[row * count + step] / pivot;
            matrix[row * count + step] = DoubleDouble{};
            for (std::size_t column = step + 1U; column < count; ++column) {
                matrix[row * count + column] -=
                    factor * matrix[step * count + column];
            }
            for (auto& values : rhs) {
                values[row] -= factor * values[step];
            }
        }
    }

    std::array<std::vector<DoubleDouble>, 3> solution;
    for (auto& values : solution) {
        values.resize(count);
    }
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        std::vector<DoubleDouble> permuted(count);
        for (std::size_t reverse = count; reverse > 0U; --reverse) {
            const auto row = reverse - 1U;
            auto value = rhs[axis][row];
            for (std::size_t column = row + 1U; column < count; ++column) {
                value -= matrix[row * count + column] * permuted[column];
            }
            permuted[row] = value / matrix[row * count + row];
            if (!finite(permuted[row])) {
                result.status = HighPrecisionStatus::numerical_failure;
                return result;
            }
        }
        for (std::size_t current = 0; current < count; ++current) {
            solution[axis][result.column_permutation[current]] = permuted[current];
        }
    }

    result.grid_velocity_m_per_s.resize(count);
    result.grid_velocity_extended.resize(count);
    for (std::size_t node = 0; node < count; ++node) {
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            result.grid_velocity_extended[node][axis] =
                extended(solution[axis][node]);
            set_component(
                result.grid_velocity_m_per_s[node],
                axis,
                approximate(solution[axis][node]));
        }
    }

    DdErrorAccumulator backward{};
    DdErrorAccumulator forward{};
    DdErrorAccumulator reconstruction{};
    for (std::size_t row = 0; row < count; ++row) {
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            DoubleDouble applied{};
            for (const auto& [column, coefficient] :
                 system.consistent_mass_rows()[row]) {
                applied += DoubleDouble(coefficient) * solution[axis][column];
            }
            const auto expected_rhs = DoubleDouble(component(
                system.consistent_rhs_kg_m_per_s()[row], axis));
            backward.add(applied - expected_rhs, DoubleDouble{});
            const auto expected_grid = DoubleDouble(component(
                evaluate(field, system.active_node_positions_m()[row]), axis));
            forward.add(
                solution[axis][row] - expected_grid,
                expected_grid,
                DoubleDouble(system.lumped_mass_kg()[row]));
        }
    }
    for (std::size_t particle = 0; particle < system.particles().size(); ++particle) {
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            DoubleDouble reconstructed{};
            for (const auto& entry : system.particle_stencils()[particle]) {
                reconstructed += DoubleDouble(entry.weight) *
                    solution[axis][entry.node_index];
            }
            const auto expected = DoubleDouble(component(
                system.particles()[particle].velocity_m_per_s, axis));
            reconstruction.add(
                reconstructed - expected,
                expected,
                DoubleDouble(system.particle_mass_kg()[particle]));
        }
    }
    result.backward_error = finish(backward);
    DoubleDouble matrix_squared{};
    for (const auto& row : system.consistent_mass_rows()) {
        for (const auto& [column, coefficient] : row) {
            static_cast<void>(column);
            const auto value = DoubleDouble(coefficient);
            matrix_squared += value * value;
        }
    }
    DoubleDouble solution_squared{};
    DoubleDouble rhs_squared{};
    for (std::size_t row = 0; row < count; ++row) {
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            solution_squared += solution[axis][row] * solution[axis][row];
            const auto rhs_value = DoubleDouble(component(
                system.consistent_rhs_kg_m_per_s()[row], axis));
            rhs_squared += rhs_value * rhs_value;
        }
    }
    result.backward_error.reference_l2 = approximate(
        dd_sqrt(matrix_squared) * dd_sqrt(solution_squared) +
        dd_sqrt(rhs_squared));
    result.backward_error.relative_l2 = result.backward_error.reference_l2 > 0.0
        ? result.backward_error.absolute_l2 / result.backward_error.reference_l2
        : result.backward_error.absolute_l2;
    result.grid_forward_error = finish(forward, true);
    result.particle_reconstruction_error = finish(reconstruction, true);
    result.backward_error_max_extended = extended(backward.maximum);
    result.grid_forward_error_max_extended = extended(forward.maximum);
    result.particle_reconstruction_error_max_extended =
        extended(reconstruction.maximum);
    result.largest_absolute_pivot = extended(largest_pivot);
    result.smallest_accepted_absolute_pivot = extended(smallest_pivot);
    result.pivot_ratio_estimate = approximate(largest_pivot / smallest_pivot);
    result.status = HighPrecisionStatus::solved;
    return result;
}

std::string_view status_name(NullspaceStatus status) noexcept {
    switch (status) {
    case NullspaceStatus::analyzed:
        return "analyzed";
    case NullspaceStatus::empty:
        return "empty";
    case NullspaceStatus::size_limit:
        return "size_limit";
    case NullspaceStatus::numerical_failure:
        return "numerical_failure";
    }
    return "unknown";
}

NullspaceDiagnostics diagnose_gram_nullspace(
    const projection::ProjectionSystem& system,
    std::span<const Vec3d> representative_grid_velocity_m_per_s,
    const NullspacePolicy& policy) {
    if (policy.maximum_particles == 0U || policy.maximum_nodes == 0U ||
        !(policy.rank_roundoff_safety_factor > 0.0) ||
        !std::isfinite(policy.rank_roundoff_safety_factor) ||
        !finite(policy.perturbation_amplitude_m_per_s)) {
        throw std::invalid_argument("invalid nullspace diagnostic policy");
    }
    NullspaceDiagnostics result{};
    result.particle_count = system.particles().size();
    result.node_count = system.active_nodes().size();
    result.rank_method =
        "deterministic binary64 Householder column-pivoted QR of sqrt(W)S; numerical threshold=128*max(P,N)*epsilon*first pivot by frozen default; not certification";
    if (result.node_count == 0U || result.particle_count == 0U) {
        result.status = NullspaceStatus::empty;
        return result;
    }
    if (result.particle_count > policy.maximum_particles ||
        result.node_count > policy.maximum_nodes) {
        result.status = NullspaceStatus::size_limit;
        return result;
    }
    if (representative_grid_velocity_m_per_s.size() != result.node_count) {
        throw std::invalid_argument(
            "nullspace representative grid has the wrong dimension");
    }

    std::vector<double> weighted_sampling(
        result.particle_count * result.node_count, 0.0);
    long double sampling_squared = 0.0L;
    for (std::size_t particle = 0; particle < result.particle_count; ++particle) {
        const auto mass_scale = std::sqrt(system.particle_mass_kg()[particle]);
        for (const auto& entry : system.particle_stencils()[particle]) {
            weighted_sampling[particle * result.node_count + entry.node_index] =
                mass_scale * entry.weight;
            sampling_squared += static_cast<long double>(entry.weight) * entry.weight;
            const auto node = system.active_node_positions_m()[entry.node_index];
            const auto gradient = basis_gradient(
                system.particles()[particle].position_m,
                node,
                system.config().grid_spacing_m);
            result.gradient_weight_reconstruction_max_residual = std::max(
                result.gradient_weight_reconstruction_max_residual,
                std::abs(gradient.reconstructed_weight - entry.weight));
        }
    }
    result.sampling_frobenius_norm =
        std::sqrt(static_cast<double>(sampling_squared));
    const auto qr = householder_column_pivoted_qr(
        std::move(weighted_sampling),
        result.particle_count,
        result.node_count,
        policy.rank_roundoff_safety_factor);
    if (!qr.ok) {
        result.status = NullspaceStatus::numerical_failure;
        return result;
    }
    result.threshold_rank = qr.rank;
    result.nullity = result.node_count - qr.rank;
    result.largest_qr_diagonal = qr.largest_diagonal;
    result.smallest_accepted_qr_diagonal = qr.smallest_accepted_diagonal;
    result.weighted_sampling_frobenius_norm = qr.frobenius_norm;
    result.numerical_rank_threshold = qr.rank_threshold;
    result.column_permutation = qr.permutation;
    const auto representative_residual = equation_residual(
        system, representative_grid_velocity_m_per_s);
    result.representative_equation_residual_l2_kg_m_per_s =
        vec_l2_norm(representative_residual);

    const auto representative_particles = reconstructed_velocities(
        system, representative_grid_velocity_m_per_s);
    const auto matrix_norm = matrix_frobenius_norm(system);
    result.modes.reserve(result.nullity);
    for (std::size_t mode_index = 0; mode_index < result.nullity; ++mode_index) {
        NullspaceModeDiagnostics mode{};
        mode.mode_index = mode_index;
        mode.nodal_mode = qr_null_vector(qr, mode_index);
        mode.nodal_l2_norm = l2_norm(mode.nodal_mode);
        mode.mass_image_l2_kg = scalar_mass_image_l2(system, mode.nodal_mode);
        mode.mass_image_relative = matrix_norm > 0.0
            ? mode.mass_image_l2_kg / (matrix_norm * mode.nodal_l2_norm)
            : mode.mass_image_l2_kg;
        const auto center_norms = scalar_center_image_norms(
            system, mode.nodal_mode);
        mode.particle_center_image_l2 = center_norms.first;
        mode.particle_center_image_max = center_norms.second;
        const auto center_scale = result.sampling_frobenius_norm *
            mode.nodal_l2_norm;
        mode.particle_center_image_relative = center_scale > 0.0
            ? mode.particle_center_image_l2 / center_scale
            : mode.particle_center_image_l2;

        mode.particle_gradient_m_inv.resize(result.particle_count);
        long double gradient_squared = 0.0L;
        long double gradient_bound_squared = 0.0L;
        for (std::size_t particle = 0; particle < result.particle_count; ++particle) {
            Vec3d accumulated{};
            long double absolute_norm_sum = 0.0L;
            for (const auto& entry : system.particle_stencils()[particle]) {
                const auto node = system.active_node_positions_m()[entry.node_index];
                const auto gradient = basis_gradient(
                    system.particles()[particle].position_m,
                    node,
                    system.config().grid_spacing_m);
                accumulated += mode.nodal_mode[entry.node_index] * gradient.gradient_m_inv;
                absolute_norm_sum += std::abs(static_cast<long double>(
                    mode.nodal_mode[entry.node_index])) *
                    static_cast<long double>(norm(gradient.gradient_m_inv));
            }
            mode.particle_gradient_m_inv[particle] = accumulated;
            const auto magnitude = norm(accumulated);
            gradient_squared += static_cast<long double>(magnitude) * magnitude;
            mode.particle_gradient_max_m_inv = std::max(
                mode.particle_gradient_max_m_inv, magnitude);
            const auto bound = 128.0 * gamma_n(
                3U * system.particle_stencils()[particle].size()) *
                static_cast<double>(absolute_norm_sum);
            gradient_bound_squared += static_cast<long double>(bound) * bound;
            mode.particle_gradient_roundoff_bound_max_m_inv = std::max(
                mode.particle_gradient_roundoff_bound_max_m_inv, bound);
        }
        mode.particle_gradient_l2_m_inv =
            std::sqrt(static_cast<double>(gradient_squared));
        mode.particle_gradient_roundoff_bound_l2_m_inv =
            std::sqrt(static_cast<double>(gradient_bound_squared));

        std::vector<Vec3d> perturbed(result.node_count);
        long double grid_difference_squared = 0.0L;
        for (std::size_t node = 0; node < result.node_count; ++node) {
            const auto difference = mode.nodal_mode[node] *
                policy.perturbation_amplitude_m_per_s;
            perturbed[node] = representative_grid_velocity_m_per_s[node] + difference;
            grid_difference_squared += static_cast<long double>(dot(difference, difference));
        }
        mode.perturbed_grid_difference_l2_m_per_s =
            std::sqrt(static_cast<double>(grid_difference_squared));
        const auto perturbed_residual = equation_residual(system, perturbed);
        mode.perturbed_equation_residual_l2_kg_m_per_s =
            vec_l2_norm(perturbed_residual);
        mode.equation_residual_change_l2_kg_m_per_s = vec_l2_norm(
            subtract_vectors(perturbed_residual, representative_residual));
        const auto perturbed_particles = reconstructed_velocities(system, perturbed);
        const auto particle_difference = subtract_vectors(
            perturbed_particles, representative_particles);
        mode.perturbed_particle_difference_l2_m_per_s =
            vec_l2_norm(particle_difference);
        mode.perturbed_particle_difference_max_m_per_s =
            vec_max_norm(particle_difference);
        result.modes.push_back(std::move(mode));
    }
    result.status = NullspaceStatus::analyzed;
    return result;
}

} // namespace mls::experimental::projection_exactness_nullspace
