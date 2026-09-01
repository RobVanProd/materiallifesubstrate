#include "test_harness.hpp"

#include "mls/authoritative_mechanics_state_bridge_lab.hpp"

#include <array>
#include <cmath>
#include <stdexcept>

namespace {

namespace bridge =
    mls::experimental::authoritative_mechanics_state_bridge;
using mls::Energy;
using mls::Length;
using mls::Mass;
using mls::Momentum;
using mls::Time;
using mls::experimental::Vec3d;

[[nodiscard]] bridge::AuthoritativePacket packet(
    std::uint64_t id, mls::Scalar x, mls::Scalar y, mls::Scalar z,
    mls::Scalar mass = 1) {
    return {
        id,
        {Length::from_raw(x), Length::from_raw(y), Length::from_raw(z)},
        {},
        Mass::from_raw(mass),
    };
}

} // namespace

MLS_TEST("authoritative mechanics unit family is exactly coherent") {
    for (const auto refinement : std::array{1U, 2U, 4U, 8U, 16U}) {
        const auto units = bridge::mechanics_unit_contract(refinement);
        bridge::validate_mechanics_unit_contract(units);
        MLS_REQUIRE_EQ(units.refinement, refinement);
        MLS_REQUIRE_EQ(
            units.momentum_mass_to_velocity_scale,
            mls::MomentumMassToVelocityScale{});
        MLS_REQUIRE_EQ(units.kinetic_energy_scale_denominator, 1);
    }
}

MLS_TEST("authoritative mechanics rejects dimensionally inconsistent scales") {
    auto units = bridge::mechanics_unit_contract(1);
    units.momentum_mass_to_velocity_scale = {3, 2};
    MLS_REQUIRE_THROWS(
        std::invalid_argument, bridge::validate_mechanics_unit_contract(units));
    units = bridge::mechanics_unit_contract(1);
    units.kinetic_energy_scale_denominator = 2;
    MLS_REQUIRE_THROWS(
        std::invalid_argument, bridge::validate_mechanics_unit_contract(units));
}

MLS_TEST("authoritative packet SI mapping round trips registered raw values") {
    const auto units = bridge::mechanics_unit_contract(1);
    const bridge::AuthoritativePacket value{
        7,
        {Length::from_raw(1'001'000'000), Length::from_raw(-17), {}},
        {Momentum::from_raw(19), Momentum::from_raw(-23), {}},
        Mass::from_raw(3),
    };
    const auto mapped = bridge::map_packet_to_binary64_si(value, units);
    MLS_REQUIRE(mapped.nearest_roundtrip_exact);
    MLS_REQUIRE_EQ(mapped.id, value.id);
    MLS_REQUIRE(mapped.mass_kg > 0.0);
}

MLS_TEST("central impulse quantization conserves exact raw momentum and orbit") {
    const auto first = packet(1, 0, 0, 0);
    const auto second = packet(2, 1'001'000'000, 0, 0);
    for (const auto refinement : std::array{1U, 2U, 4U, 8U, 16U}) {
        const auto units = bridge::mechanics_unit_contract(refinement);
        for (const auto subdivisions : std::array{1U, 2U, 4U, 8U, 16U}) {
            const auto evaluated = bridge::evaluate_central_impulse(
                {first, second, {0.0006, 0.0, 0.0},
                 Time::from_raw(1'000'000'000), subdivisions,
                 bridge::QuantizationPath::fixed_point_refinement},
                units);
            MLS_REQUIRE(evaluated.exact_linear_momentum);
            MLS_REQUIRE(evaluated.exact_orbital_angular_momentum);
            MLS_REQUIRE_EQ(evaluated.impulse_to_second, -evaluated.impulse_to_first);
            MLS_REQUIRE(evaluated.kinetic_floor_residual_j >= -1.0e-18);
        }
    }
}

MLS_TEST("primitive central lattice prevents Cartesian rounding torque") {
    const auto units = bridge::mechanics_unit_contract(16);
    const auto evaluated = bridge::evaluate_central_impulse(
        {packet(1, 1'001'000'000, 0, 0),
         packet(2, 0, 1'001'000'000, 0),
         {-0.0006, 0.0006, 0.0}, Time::from_raw(1'000'000'000), 16,
         bridge::QuantizationPath::fixed_point_refinement},
        units);
    MLS_REQUIRE_EQ(evaluated.primitive_direction.x.raw(), -1);
    MLS_REQUIRE_EQ(evaluated.primitive_direction.y.raw(), 1);
    MLS_REQUIRE(evaluated.exact_orbital_angular_momentum);
}

MLS_TEST("explicit remainder is subdivision invariant and checkpointed") {
    const auto units = bridge::mechanics_unit_contract(1);
    const auto first = packet(1, 0, 0, 0);
    const auto second = packet(2, 1'001'000'000, 0, 0);
    mls::Scalar expected = 0;
    for (const auto subdivisions : std::array{1U, 2U, 4U, 8U, 16U}) {
        const auto evaluated = bridge::evaluate_central_impulse(
            {first, second, {0.0006, 0.0, 0.0},
             Time::from_raw(1'000'000'000), subdivisions,
             bridge::QuantizationPath::explicit_remainder},
            units);
        if (subdivisions == 1U) {
            expected = evaluated.applied_primitive_multiple;
        }
        MLS_REQUIRE_EQ(evaluated.applied_primitive_multiple, expected);
        MLS_REQUIRE(evaluated.remainder_checkpoint_roundtrip);
        MLS_REQUIRE(std::abs(evaluated.remainder_balance_error) < 2.0e-15);
    }
}

MLS_TEST("kinetic energy flooring remains a shrinking numerical residual") {
    double previous_bound = 1.0;
    for (const auto refinement : std::array{1U, 2U, 4U, 8U, 16U}) {
        const auto units = bridge::mechanics_unit_contract(refinement);
        const auto evaluated = bridge::evaluate_central_impulse(
            {packet(1, 0, 0, 0), packet(2, 1'001'000'000, 0, 0),
             {0.0006, 0.0, 0.0}, Time::from_raw(1'000'000'000), 1,
             bridge::QuantizationPath::fixed_point_refinement},
            units);
        const auto energy_quantum =
            static_cast<double>(units.energy_quantum_j.numerator) /
            static_cast<double>(units.energy_quantum_j.denominator);
        MLS_REQUIRE(evaluated.kinetic_floor_residual_j >= -1.0e-18);
        MLS_REQUIRE(evaluated.kinetic_floor_residual_j < 2.0 * energy_quantum);
        MLS_REQUIRE(2.0 * energy_quantum < previous_bound);
        previous_bound = 2.0 * energy_quantum;
        MLS_REQUIRE_EQ(
            evaluated.exact_impulse_work_j, evaluated.exact_kinetic_delta_j);
    }
}
