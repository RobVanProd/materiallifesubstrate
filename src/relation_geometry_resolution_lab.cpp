#include "mls/relation_geometry_resolution_lab.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace mls::experimental::relation_geometry_resolution {
namespace {

static_assert(sizeof(double) == 8U);
static_assert(std::numeric_limits<double>::digits == 53);
static_assert(std::numeric_limits<double>::is_iec559);

struct DoubleDouble final {
    double hi{0.0};
    double lo{0.0};
};

[[nodiscard]] bool finite(Vec3d value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) &&
        std::isfinite(value.z);
}

[[nodiscard]] DoubleDouble quick_two_sum(double larger, double smaller) noexcept {
    const auto sum = larger + smaller;
    return {sum, smaller - (sum - larger)};
}

[[nodiscard]] DoubleDouble two_sum(double lhs, double rhs) noexcept {
    const auto sum = lhs + rhs;
    const auto rhs_virtual = sum - lhs;
    const auto error = (lhs - (sum - rhs_virtual)) + (rhs - rhs_virtual);
    return {sum, error};
}

[[nodiscard]] DoubleDouble two_difference(double lhs, double rhs) noexcept {
    const auto difference = lhs - rhs;
    const auto rhs_virtual = lhs - difference;
    const auto error = (lhs - (difference + rhs_virtual)) +
        (rhs_virtual - rhs);
    return {difference, error};
}

[[nodiscard]] DoubleDouble normalize(DoubleDouble value) noexcept {
    return quick_two_sum(value.hi, value.lo);
}

[[nodiscard]] DoubleDouble add(
    DoubleDouble lhs, DoubleDouble rhs) noexcept {
    const auto sum = lhs.hi + rhs.hi;
    const auto virtual_rhs = sum - lhs.hi;
    auto error = (lhs.hi - (sum - virtual_rhs)) +
        (rhs.hi - virtual_rhs);
    error += lhs.lo + rhs.lo;
    return quick_two_sum(sum, error);
}

[[nodiscard]] DoubleDouble negate(DoubleDouble value) noexcept {
    return {-value.hi, -value.lo};
}

[[nodiscard]] DoubleDouble subtract(
    DoubleDouble lhs, DoubleDouble rhs) noexcept {
    return add(lhs, negate(rhs));
}

[[nodiscard]] DoubleDouble multiply(
    DoubleDouble lhs, DoubleDouble rhs) noexcept {
    const auto product = lhs.hi * rhs.hi;
    auto error = std::fma(lhs.hi, rhs.hi, -product);
    error += lhs.hi * rhs.lo + lhs.lo * rhs.hi;
    error += lhs.lo * rhs.lo;
    return quick_two_sum(product, error);
}

[[nodiscard]] DoubleDouble divide(
    DoubleDouble numerator, DoubleDouble denominator) {
    if (denominator.hi == 0.0) {
        throw std::domain_error("double-double division by zero");
    }
    const auto first = numerator.hi / denominator.hi;
    auto quotient = DoubleDouble{first, 0.0};
    for (std::size_t iteration = 0; iteration < 2U; ++iteration) {
        const auto residual = subtract(
            numerator, multiply(denominator, quotient));
        const auto correction = residual.hi / denominator.hi;
        quotient = add(quotient, {correction, 0.0});
    }
    return normalize(quotient);
}

[[nodiscard]] DoubleDouble square_root(DoubleDouble value) {
    if (value.hi < 0.0 || (value.hi == 0.0 && value.lo < 0.0)) {
        throw std::domain_error("double-double square root of negative value");
    }
    if (value.hi == 0.0 && value.lo == 0.0) {
        return {};
    }
    auto root = DoubleDouble{std::sqrt(value.hi), 0.0};
    for (std::size_t iteration = 0; iteration < 2U; ++iteration) {
        const auto residual = subtract(value, multiply(root, root));
        const auto denominator = add(root, root);
        root = add(root, divide(residual, denominator));
    }
    return normalize(root);
}

[[nodiscard]] LengthOrder order(DoubleDouble value) noexcept {
    if (value.hi < 0.0 || (value.hi == 0.0 && value.lo < 0.0)) {
        return LengthOrder::shorter;
    }
    if (value.hi > 0.0 || value.lo > 0.0) {
        return LengthOrder::longer;
    }
    return LengthOrder::equal;
}

[[nodiscard]] LengthOrder order(double value) noexcept {
    if (value < 0.0) {
        return LengthOrder::shorter;
    }
    if (value > 0.0) {
        return LengthOrder::longer;
    }
    return LengthOrder::equal;
}

[[nodiscard]] double stable_norm(Vec3d value) noexcept {
    const auto scale =
        std::max({std::abs(value.x), std::abs(value.y), std::abs(value.z)});
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

[[nodiscard]] bool same_coordinates(Vec3d lhs, Vec3d rhs) noexcept {
    return lhs.x == rhs.x && lhs.y == rhs.y && lhs.z == rhs.z;
}

[[nodiscard]] DoubleDouble exact_offset(double second, double first) noexcept {
    return two_difference(second, first);
}

[[nodiscard]] std::array<DoubleDouble, 3> exact_offset(
    Vec3d second, Vec3d first) noexcept {
    return {exact_offset(second.x, first.x), exact_offset(second.y, first.y),
            exact_offset(second.z, first.z)};
}

[[nodiscard]] DoubleDouble squared_norm(
    const std::array<DoubleDouble, 3>& offset) noexcept {
    DoubleDouble result{};
    for (const auto component : offset) {
        result = add(result, multiply(component, component));
    }
    return normalize(result);
}

[[nodiscard]] DoubleDouble cancellation_resistant_squared_difference(
    const RelationGeometryInput& input) noexcept {
    const std::array current_first{input.current_first_m.x,
                                   input.current_first_m.y,
                                   input.current_first_m.z};
    const std::array current_second{input.current_second_m.x,
                                    input.current_second_m.y,
                                    input.current_second_m.z};
    const std::array reference_first{input.reference_first_m.x,
                                     input.reference_first_m.y,
                                     input.reference_first_m.z};
    const std::array reference_second{input.reference_second_m.x,
                                      input.reference_second_m.y,
                                      input.reference_second_m.z};
    DoubleDouble result{};
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        // (cs-cf)^2-(rs-rf)^2
        // = ((cs-rs)-(cf-rf))*((cs+rs)-(cf+rf)).
        // The first factor preserves semantic endpoint perturbations before a
        // rounded relation subtraction can erase them.  Every addition,
        // subtraction, product residual, and accumulation order is explicit.
        const auto displacement_difference = subtract(
            two_difference(current_second[axis], reference_second[axis]),
            two_difference(current_first[axis], reference_first[axis]));
        const auto offset_sum = subtract(
            two_sum(current_second[axis], reference_second[axis]),
            two_sum(current_first[axis], reference_first[axis]));
        result = add(
            result, multiply(displacement_difference, offset_sum));
    }
    return normalize(result);
}

void validate_input(const RelationGeometryInput& input) {
    if (!finite(input.reference_first_m) ||
        !finite(input.reference_second_m) ||
        !finite(input.current_first_m) ||
        !finite(input.current_second_m) ||
        !(input.frozen_reference_length_m > 0.0) ||
        !std::isfinite(input.frozen_reference_length_m)) {
        throw std::invalid_argument(
            "relation geometry requires finite endpoints and positive l0");
    }
    if (same_coordinates(input.reference_first_m, input.reference_second_m)) {
        throw std::invalid_argument(
            "relation geometry reference endpoints must be noncoincident");
    }
}

[[nodiscard]] Vec3d high_words(
    const std::array<DoubleDouble, 3>& value) noexcept {
    return {value[0].hi, value[1].hi, value[2].hi};
}

[[nodiscard]] Vec3d low_words(
    const std::array<DoubleDouble, 3>& value) noexcept {
    return {value[0].lo, value[1].lo, value[2].lo};
}

} // namespace

std::string_view path_name(GeometryPath path) noexcept {
    switch (path) {
    case GeometryPath::frozen_binary64:
        return "frozen_binary64";
    case GeometryPath::cancellation_resistant_binary64:
        return "cancellation_resistant_binary64";
    case GeometryPath::transient_double_double:
        return "transient_double_double";
    }
    return "unknown";
}

std::string_view status_name(GeometryStatus status) noexcept {
    switch (status) {
    case GeometryStatus::evaluated:
        return "evaluated";
    case GeometryStatus::coincident_relation:
        return "coincident_relation";
    case GeometryStatus::unresolved_noncoincident:
        return "unresolved_noncoincident";
    }
    return "unknown";
}

std::string_view order_name(LengthOrder value) noexcept {
    switch (value) {
    case LengthOrder::shorter:
        return "shorter";
    case LengthOrder::equal:
        return "equal";
    case LengthOrder::longer:
        return "longer";
    }
    return "unknown";
}

RelationGeometryEvaluation evaluate_relation_geometry(
    const RelationGeometryInput& input, GeometryPath path) {
    validate_input(input);
    RelationGeometryEvaluation result{};
    result.path = path;
    result.coordinate_coincident =
        same_coordinates(input.current_first_m, input.current_second_m);

    if (path == GeometryPath::transient_double_double) {
        const auto reference_offset = exact_offset(
            input.reference_second_m, input.reference_first_m);
        const auto current_offset = exact_offset(
            input.current_second_m, input.current_first_m);
        result.reference_offset_m = high_words(reference_offset);
        result.reference_offset_low_m = low_words(reference_offset);
        result.current_offset_m = high_words(current_offset);
        result.current_offset_low_m = low_words(current_offset);
        const auto reference_squared = squared_norm(reference_offset);
        const auto current_squared = squared_norm(current_offset);
        // Direct subtraction of two double-double squared norms still has
        // only about 106 bits of relative precision.  It cannot retain a
        // subnormal endpoint perturbation beside an O(1) reference norm.
        // Preserve the exact algebraic coordinate with the independently
        // factored endpoint-bit numerator, then divide by the DD norm sum.
        const auto squared_difference =
            cancellation_resistant_squared_difference(input);
        result.squared_distance_difference_m2 = squared_difference.hi;
        result.squared_distance_difference_low_m2 = squared_difference.lo;
        if (result.coordinate_coincident) {
            result.status = GeometryStatus::coincident_relation;
            return result;
        }
        const auto reference_length = square_root(reference_squared);
        const auto current_length = square_root(current_squared);
        if (current_length.hi == 0.0) {
            result.status = GeometryStatus::unresolved_noncoincident;
            return result;
        }
        const auto extension = divide(
            squared_difference, add(current_length, reference_length));
        result.current_length_m = current_length.hi;
        result.current_length_low_m = current_length.lo;
        result.extension_m = extension.hi;
        result.extension_low_m = extension.lo;
        result.exact_length_order = order(extension);
        std::array<DoubleDouble, 3> direction{};
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            direction[axis] = divide(current_offset[axis], current_length);
        }
        result.direction_first_to_second = high_words(direction);
        result.direction_low = low_words(direction);
        if (!finite(result.direction_first_to_second)) {
            throw std::overflow_error(
                "transient relation direction is nonfinite");
        }
        result.status = GeometryStatus::evaluated;
        return result;
    }

    result.reference_offset_m =
        input.reference_second_m - input.reference_first_m;
    result.current_offset_m = input.current_second_m - input.current_first_m;
    if (!finite(result.reference_offset_m) || !finite(result.current_offset_m)) {
        throw std::overflow_error("binary64 relation offset overflow");
    }
    const auto current_length = stable_norm(result.current_offset_m);
    if (result.coordinate_coincident) {
        result.status = GeometryStatus::coincident_relation;
        return result;
    }
    if (current_length == 0.0) {
        result.status = GeometryStatus::unresolved_noncoincident;
        return result;
    }
    if (!std::isfinite(current_length)) {
        throw std::overflow_error("binary64 relation length overflow");
    }
    result.current_length_m = current_length;
    result.direction_first_to_second = {
        result.current_offset_m.x / current_length,
        result.current_offset_m.y / current_length,
        result.current_offset_m.z / current_length};
    if (!finite(result.direction_first_to_second)) {
        throw std::overflow_error("binary64 relation direction overflow");
    }

    if (path == GeometryPath::frozen_binary64) {
        result.extension_m =
            current_length - input.frozen_reference_length_m;
        result.exact_length_order = order(result.extension_m);
        result.squared_distance_difference_m2 =
            current_length * current_length -
            input.frozen_reference_length_m *
                input.frozen_reference_length_m;
    } else {
        const auto numerator =
            cancellation_resistant_squared_difference(input);
        const auto denominator =
            current_length + input.frozen_reference_length_m;
        if (!(denominator > 0.0) || !std::isfinite(denominator)) {
            throw std::overflow_error(
                "rationalized extension denominator is invalid");
        }
        const auto extension = divide(numerator, {denominator, 0.0});
        result.extension_m = extension.hi;
        result.extension_low_m = extension.lo;
        result.squared_distance_difference_m2 = numerator.hi;
        result.squared_distance_difference_low_m2 = numerator.lo;
        result.exact_length_order = order(numerator);
    }
    if (!std::isfinite(result.extension_m) ||
        !std::isfinite(result.squared_distance_difference_m2)) {
        throw std::overflow_error("relation extension evaluation overflow");
    }
    result.status = GeometryStatus::evaluated;
    return result;
}

} // namespace mls::experimental::relation_geometry_resolution
