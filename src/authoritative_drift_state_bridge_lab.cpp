#include "mls/authoritative_drift_state_bridge_lab.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <numeric>
#include <stdexcept>

namespace mls::experimental::authoritative_drift_state_bridge {
namespace {

namespace mechanics = authoritative_mechanics_state_bridge;

[[nodiscard]] bool valid_subdivisions(std::uint32_t value) noexcept {
    return value == 1U || value == 2U || value == 4U || value == 8U ||
        value == 16U || value == 32U;
}

[[nodiscard]] Scalar checked_scale(Scalar value, Scalar factor) {
    return detail::checked_multiply(value, factor);
}

[[nodiscard]] Scalar absolute_for_gcd(Scalar value) {
    if (value == std::numeric_limits<Scalar>::min()) {
        throw std::overflow_error("drift momentum magnitude overflow");
    }
    return value < 0 ? static_cast<Scalar>(-value) : value;
}

[[nodiscard]] Scalar component(const Momentum3& value, std::size_t axis) noexcept {
    if (axis == 0U) {
        return value.x.raw();
    }
    return axis == 1U ? value.y.raw() : value.z.raw();
}

[[nodiscard]] Position3 position_from(const std::array<Scalar, 3>& value) noexcept {
    return {
        Length::from_raw(value[0]),
        Length::from_raw(value[1]),
        Length::from_raw(value[2]),
    };
}

[[nodiscard]] Position3 scaled_position(const Position3& value, Scalar factor) {
    return {
        Length::from_raw(checked_scale(value.x.raw(), factor)),
        Length::from_raw(checked_scale(value.y.raw(), factor)),
        Length::from_raw(checked_scale(value.z.raw(), factor)),
    };
}

[[nodiscard]] Momentum3 scaled_momentum(const Momentum3& value, Scalar factor) {
    return {
        Momentum::from_raw(checked_scale(value.x.raw(), factor)),
        Momentum::from_raw(checked_scale(value.y.raw(), factor)),
        Momentum::from_raw(checked_scale(value.z.raw(), factor)),
    };
}

[[nodiscard]] std::uint64_t magnitude(Scalar value) {
    if (value == std::numeric_limits<Scalar>::min()) {
        return std::uint64_t{1} << 63U;
    }
    return static_cast<std::uint64_t>(value < 0 ? -value : value);
}

[[nodiscard]] std::uint64_t product_margin(Scalar value) noexcept {
    return static_cast<std::uint64_t>(std::numeric_limits<Scalar>::max()) -
        magnitude(value);
}

[[nodiscard]] double rational_value(
    mechanics::PositiveRational value) noexcept {
    return static_cast<double>(value.numerator) /
        static_cast<double>(value.denominator);
}

[[nodiscard]] long double square(long double value) noexcept {
    return value * value;
}

} // namespace

const char* path_name(DriftPath path) noexcept {
    switch (path) {
    case DriftPath::cartesian_nearest:
        return "cartesian_nearest";
    case DriftPath::primitive_directional:
        return "primitive_directional";
    }
    return "unknown";
}

Scalar nearest_even_rational(Scalar numerator, Scalar denominator) {
    if (denominator <= 0 || numerator == std::numeric_limits<Scalar>::min()) {
        throw std::invalid_argument("nearest-even rational requires bounded numerator and positive denominator");
    }
    const auto quotient = static_cast<Scalar>(numerator / denominator);
    const auto remainder = static_cast<Scalar>(numerator % denominator);
    const auto remainder_magnitude = absolute_for_gcd(remainder);
    const auto half = static_cast<Scalar>(denominator / 2);
    const auto above_half = remainder_magnitude > half;
    const auto exact_half = denominator % 2 == 0 && remainder_magnitude == half;
    if (!above_half && !(exact_half && quotient % 2 != 0)) {
        return quotient;
    }
    return detail::checked_add(quotient, numerator < 0 ? -1 : 1);
}

Scalar nearest_even_product_ratio(
    Scalar multiplicand, Scalar multiplier, Scalar denominator) {
    return nearest_even_rational(
        detail::checked_multiply(multiplicand, multiplier), denominator);
}

DriftEvaluation evaluate_drift(
    const DriftInput& input,
    const mechanics::MechanicsUnitContract& contract) {
    mechanics::validate_mechanics_unit_contract(contract);
    if (input.packet.id == 0U || input.packet.base_mass.raw() <= 0 ||
        input.horizon.raw() <= 0 || !valid_subdivisions(input.subdivisions) ||
        input.horizon.raw() % static_cast<Scalar>(input.subdivisions) != 0) {
        throw std::invalid_argument("invalid authoritative drift input");
    }

    const auto refinement = static_cast<Scalar>(contract.refinement);
    const auto refinement_squared = detail::checked_multiply(refinement, refinement);
    const auto refined_position = scaled_position(
        input.packet.base_position, refinement);
    const auto refined_momentum = scaled_momentum(
        input.packet.base_momentum, refinement_squared);
    const auto refined_mass = Mass::from_raw(
        checked_scale(input.packet.base_mass.raw(), refinement));
    const auto substep = Time::from_raw(
        input.horizon.raw() / static_cast<Scalar>(input.subdivisions));

    auto divisor = std::gcd(
        absolute_for_gcd(refined_momentum.x.raw()),
        absolute_for_gcd(refined_momentum.y.raw()));
    divisor = std::gcd(divisor, absolute_for_gcd(refined_momentum.z.raw()));
    std::array<Scalar, 3> direction{};
    if (divisor != 0) {
        for (std::size_t axis = 0; axis < direction.size(); ++axis) {
            direction[axis] = component(refined_momentum, axis) / divisor;
        }
    }

    std::array<Scalar, 3> displacement{};
    if (input.path == DriftPath::cartesian_nearest) {
        for (std::size_t axis = 0; axis < displacement.size(); ++axis) {
            const auto per_step = nearest_even_product_ratio(
                component(refined_momentum, axis), substep.raw(),
                refined_mass.raw());
            displacement[axis] = detail::checked_multiply(
                per_step, static_cast<Scalar>(input.subdivisions));
        }
    } else if (divisor != 0) {
        const auto per_step = nearest_even_product_ratio(
            divisor, substep.raw(), refined_mass.raw());
        const auto total = detail::checked_multiply(
            per_step, static_cast<Scalar>(input.subdivisions));
        for (std::size_t axis = 0; axis < displacement.size(); ++axis) {
            displacement[axis] = detail::checked_multiply(total, direction[axis]);
        }
    }

    DriftEvaluation result{};
    result.path = input.path;
    result.refinement = contract.refinement;
    result.subdivisions = input.subdivisions;
    result.substep = substep;
    result.refined_position = refined_position;
    result.refined_momentum = refined_momentum;
    result.refined_mass = refined_mass;
    result.direction_gcd = divisor;
    result.primitive_direction = position_from(direction);
    result.applied_displacement = position_from(displacement);
    result.final_position = refined_position + result.applied_displacement;
    result.target_denominator = refined_mass.raw();

    auto minimum_margin = std::numeric_limits<std::uint64_t>::max();
    const auto lq = rational_value(contract.length_quantum_m);
    long double squared_error = 0.0L;
    for (std::size_t axis = 0; axis < displacement.size(); ++axis) {
        result.target_numerator[axis] = detail::checked_multiply(
            component(refined_momentum, axis), input.horizon.raw());
        result.error_numerator[axis] = detail::checked_subtract(
            detail::checked_multiply(displacement[axis], refined_mass.raw()),
            result.target_numerator[axis]);
        minimum_margin = std::min(
            minimum_margin, product_margin(result.target_numerator[axis]));
        const auto exact = static_cast<double>(result.target_numerator[axis]) /
            static_cast<double>(result.target_denominator) * lq;
        const auto applied = static_cast<double>(displacement[axis]) * lq;
        const auto error = applied - exact;
        if (axis == 0U) {
            result.exact_displacement_m.x = exact;
            result.applied_displacement_m.x = applied;
            result.component_error_m.x = error;
        } else if (axis == 1U) {
            result.exact_displacement_m.y = exact;
            result.applied_displacement_m.y = applied;
            result.component_error_m.y = error;
        } else {
            result.exact_displacement_m.z = exact;
            result.applied_displacement_m.z = applied;
            result.component_error_m.z = error;
        }
        squared_error += static_cast<long double>(error) *
            static_cast<long double>(error);
    }
    result.vector_error_m = static_cast<double>(std::sqrt(squared_error));
    result.checked_product_margin = minimum_margin;
    result.orbital_angular_momentum_delta = cross(
        result.applied_displacement, refined_momentum);
    result.momentum_after = refined_momentum;
    result.kinetic_energy_before = kinetic_energy_of(
        refined_mass, refined_momentum, contract.kinetic_energy_scale_denominator);
    result.kinetic_energy_after = kinetic_energy_of(
        refined_mass, result.momentum_after, contract.kinetic_energy_scale_denominator);
    result.exact_momentum_unchanged = result.momentum_after == refined_momentum;
    result.exact_kinetic_energy_unchanged =
        result.kinetic_energy_after == result.kinetic_energy_before;
    result.exact_orbital_angular_momentum =
        result.orbital_angular_momentum_delta == AngularMomentum3{};
    return result;
}

RelationChordEvaluation evaluate_relation_chord(
    const RelationChordInput& input) {
    if (input.id == 0U || input.rest_length.raw() <= 0) {
        throw std::invalid_argument("invalid relation chord input");
    }
    const std::array<long double, 3> initial{
        static_cast<long double>(input.initial_relative.x.raw()),
        static_cast<long double>(input.initial_relative.y.raw()),
        static_cast<long double>(input.initial_relative.z.raw())};
    const std::array<long double, 3> delta{
        static_cast<long double>(detail::checked_subtract(
            input.final_relative.x.raw(), input.initial_relative.x.raw())),
        static_cast<long double>(detail::checked_subtract(
            input.final_relative.y.raw(), input.initial_relative.y.raw())),
        static_cast<long double>(detail::checked_subtract(
            input.final_relative.z.raw(), input.initial_relative.z.raw()))};
    long double a = 0.0L;
    long double b = 0.0L;
    for (std::size_t axis = 0; axis < initial.size(); ++axis) {
        a += square(delta[axis]);
        b += initial[axis] * delta[axis];
    }
    long double parameter = 0.0L;
    if (a > 0.0L) {
        parameter = std::clamp(-b / a, 0.0L, 1.0L);
    }
    long double minimum_squared = 0.0L;
    for (std::size_t axis = 0; axis < initial.size(); ++axis) {
        minimum_squared += square(initial[axis] + parameter * delta[axis]);
    }
    const auto rest = static_cast<long double>(input.rest_length.raw());
    const auto ratio_squared = minimum_squared / (rest * rest);
    const auto threshold_squared = std::ldexp(1.0L, -48);
    return {
        input.id,
        parameter > 0.0L && parameter < 1.0L,
        ratio_squared >= threshold_squared,
    };
}

} // namespace mls::experimental::authoritative_drift_state_bridge
