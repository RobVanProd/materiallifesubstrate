#include "test_harness.hpp"

#include "mls/phase_space_time_corefinement_lab.hpp"

#include <array>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace {

namespace corefine = mls::experimental::phase_space_time_corefinement;
namespace observation = mls::experimental::mechanical_observability;
namespace parent = mls::experimental::time_integration_foundation;

using mls::Length;
using mls::Mass;
using mls::Momentum;
using mls::Time;
using parent::DynamicPacket;
using parent::PhaseState;

constexpr mls::Scalar metre = 128'000'000'000LL;
constexpr mls::Scalar kilogram = 524'288;

[[nodiscard]] DynamicPacket packet(
    std::uint64_t id,
    mls::Scalar x,
    mls::Scalar y,
    mls::Scalar z,
    mls::Scalar px = 0,
    mls::Scalar py = 0,
    mls::Scalar pz = 0) {
    return {
        id,
        {Length::from_raw(x), Length::from_raw(y), Length::from_raw(z)},
        {Momentum::from_raw(px), Momentum::from_raw(py), Momentum::from_raw(pz)},
        Mass::from_raw(kilogram),
    };
}

[[nodiscard]] std::vector<DynamicPacket> reference() {
    return {
        packet(1, 0, 0, 0),
        packet(2, metre, 0, 0),
        packet(3, 0, metre, 0),
        packet(4, 0, 0, metre),
    };
}

[[nodiscard]] std::vector<observation::BondRelation> relations() {
    return {{1, 2}, {1, 3}, {1, 4}, {2, 3}, {2, 4}, {3, 4}};
}

[[nodiscard]] PhaseState moving_state() {
    constexpr mls::Scalar low = -32'000'000;
    constexpr mls::Scalar high = 128'096'000'000LL;
    return {
        {},
        {
            packet(1, low, low, low, 65'536, -32'768, 16'384),
            packet(2, high, low, low, -49'152, 24'576, -8'192),
            packet(3, low, high, low, -8'192, 16'384, -24'576),
            packet(4, low, low, high, -8'192, -8'192, 16'384),
        },
    };
}

} // namespace

MLS_TEST("corefinement unit family is exact and mechanically derived") {
    constexpr std::array<std::uint64_t, 5> length_denominators{
        UINT64_C(128000000000), UINT64_C(8192000000000),
        UINT64_C(524288000000000), UINT64_C(33554432000000000),
        UINT64_C(2147483648000000000)};
    constexpr std::array<std::uint64_t, 5> time_denominators{
        UINT64_C(1000000000), UINT64_C(8000000000),
        UINT64_C(64000000000), UINT64_C(512000000000),
        UINT64_C(4096000000000)};
    for (std::uint32_t level = 0; level <= corefine::maximum_level; ++level) {
        const auto profile = corefine::unit_profile(level);
        corefine::validate_unit_profile(profile);
        MLS_REQUIRE_EQ(profile.level, level);
        MLS_REQUIRE_EQ(profile.length_quantum_m.numerator, 1U);
        MLS_REQUIRE_EQ(
            profile.length_quantum_m.denominator,
            length_denominators[level]);
        MLS_REQUIRE_EQ(profile.mass_quantum_kg.numerator, 1U);
        MLS_REQUIRE_EQ(profile.mass_quantum_kg.denominator, 524'288U);
        MLS_REQUIRE_EQ(profile.time_quantum_s.numerator, 1U);
        MLS_REQUIRE_EQ(
            profile.time_quantum_s.denominator,
            time_denominators[level]);
        MLS_REQUIRE_EQ(
            profile.force_quantum_n,
            (mls::experimental::authoritative_mechanics_state_bridge::
                 PositiveRational{1'953'125U, 131'072U}));
    }
}

MLS_TEST("corefinement level zero is exactly the sealed KDK map") {
    const auto base_reference = reference();
    const auto edges = relations();
    const auto base_model = parent::build_registered_model(base_reference, edges);
    const auto candidate_model = corefine::build_registered_model(
        base_reference, edges, 0);
    const auto initial = moving_state();
    const auto base = parent::evaluate_step(
        base_model,
        {parent::IntegratorPath::quantized_kick_drift_kick,
         initial,
         Time::from_raw(62'500'000)});
    const auto candidate = corefine::evaluate_step(
        candidate_model,
        {parent::IntegratorPath::quantized_kick_drift_kick,
         initial,
         Time::from_raw(62'500'000)});
    MLS_REQUIRE_EQ(candidate.status, base.status);
    MLS_REQUIRE_EQ(candidate.next_state, base.next_state);
    MLS_REQUIRE_EQ(
        candidate.energy_after.mechanical_energy_j,
        base.energy_after.mechanical_energy_j);
    MLS_REQUIRE(candidate.exact_momentum_preserved);
    MLS_REQUIRE(candidate.exact_orbital_angular_momentum_preserved);
}

MLS_TEST("wide orbital invariant diagnostic exceeds signed 64 bit without state widening") {
    const auto large = mls::Scalar{1} << 60U;
    const std::array packets{
        packet(1, large, 0, 0, 0, large, 0),
    };
    const auto invariant = corefine::evaluate_exact_invariants(packets);
    MLS_REQUIRE_EQ(invariant.total_momentum.y.raw(), large);
    MLS_REQUIRE_EQ(
        corefine::hexadecimal(invariant.orbital_angular_momentum.z),
        "0x1000000000000000000000000000000");
}

MLS_TEST("corefinement extracts the exact primitive momentum lattice") {
    const auto value = packet(7, 0, 0, 0, -84, 126, 210);
    const auto diagnostic = corefine::primitive_momentum_diagnostic(value);
    MLS_REQUIRE_EQ(diagnostic.direction_gcd, 42);
    MLS_REQUIRE_EQ(diagnostic.primitive_direction[0], -2);
    MLS_REQUIRE_EQ(diagnostic.primitive_direction[1], 3);
    MLS_REQUIRE_EQ(diagnostic.primitive_direction[2], 5);
}

MLS_TEST("corefined KDK retains exact registered signed-time recovery") {
    const auto base_reference = reference();
    const auto model = corefine::build_registered_model(
        base_reference, relations(), 1);
    const auto initial = corefine::map_level_zero_state(moving_state(), 1);
    const auto forward = corefine::evaluate_trajectory(
        model,
        parent::IntegratorPath::quantized_kick_drift_kick,
        initial,
        Time::from_raw(250'000'000),
        4);
    MLS_REQUIRE_EQ(forward.status, parent::StepStatus::accepted);
    const auto backward = corefine::evaluate_trajectory(
        model,
        parent::IntegratorPath::quantized_kick_drift_kick,
        forward.final_state,
        Time::from_raw(-250'000'000),
        4);
    MLS_REQUIRE_EQ(backward.status, parent::StepStatus::accepted);
    MLS_REQUIRE_EQ(backward.final_state, initial);
    MLS_REQUIRE(forward.exact_momentum_preserved);
    MLS_REQUIRE(forward.exact_orbital_angular_momentum_preserved);
}

MLS_TEST("corefinement mapping rejects signed 64 bit state overflow") {
    auto state = moving_state();
    state.packets[0].position.x = Length::from_raw(17 * metre);
    bool rejected = false;
    try {
        static_cast<void>(corefine::map_level_zero_state(state, 4));
    } catch (const std::overflow_error&) {
        rejected = true;
    }
    MLS_REQUIRE(rejected);
}

MLS_TEST("corefinement rejects independently altered derived units") {
    auto profile = corefine::unit_profile(2);
    ++profile.momentum_quantum_kg_m_per_s.denominator;
    bool rejected = false;
    try {
        corefine::validate_unit_profile(profile);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    MLS_REQUIRE(rejected);
}
