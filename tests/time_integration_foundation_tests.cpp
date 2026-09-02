#include "test_harness.hpp"

#include "mls/time_integration_foundation_lab.hpp"

#include <array>
#include <cstdint>
#include <vector>

namespace {

namespace time_lab = mls::experimental::time_integration_foundation;
namespace drift = mls::experimental::authoritative_drift_state_bridge;
namespace mechanics = mls::experimental::authoritative_mechanics_state_bridge;
namespace observation = mls::experimental::mechanical_observability;
using mls::Length;
using mls::Mass;
using mls::Momentum;
using mls::Time;
using time_lab::DynamicPacket;
using time_lab::PhaseState;

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

[[nodiscard]] std::vector<DynamicPacket> k4_reference() {
    return {
        packet(1, 0, 0, 0),
        packet(2, metre, 0, 0),
        packet(3, 0, metre, 0),
        packet(4, 0, 0, metre),
    };
}

[[nodiscard]] std::vector<observation::BondRelation> k4_relations() {
    return {{1, 2}, {1, 3}, {1, 4}, {2, 3}, {2, 4}, {3, 4}};
}

[[nodiscard]] PhaseState breathing_state(bool moving = false) {
    constexpr mls::Scalar low = -32'000'000;
    constexpr mls::Scalar high = 128'096'000'000LL;
    auto packets = std::vector<DynamicPacket>{
        packet(1, low, low, low),
        packet(2, high, low, low),
        packet(3, low, high, low),
        packet(4, low, low, high),
    };
    if (moving) {
        packets[0].momentum = {
            Momentum::from_raw(65'536), Momentum::from_raw(-32'768),
            Momentum::from_raw(16'384)};
        packets[1].momentum = {
            Momentum::from_raw(-49'152), Momentum::from_raw(24'576),
            Momentum::from_raw(-8'192)};
        packets[2].momentum = {
            Momentum::from_raw(-8'192), Momentum::from_raw(16'384),
            Momentum::from_raw(-24'576)};
        packets[3].momentum = {
            Momentum::from_raw(-8'192), Momentum::from_raw(-8'192),
            Momentum::from_raw(16'384)};
    }
    return {{}, std::move(packets)};
}

[[nodiscard]] PhaseState translated(PhaseState state, mls::Position3 shift) {
    for (auto& value : state.packets) {
        value.position += shift;
    }
    return state;
}

[[nodiscard]] mls::Position3 relative(
    const PhaseState& state, std::size_t index) {
    return state.packets[index].position - state.packets[0].position;
}

} // namespace

MLS_TEST("time integration foundation reproduces accepted parent bridge fingerprints") {
    const auto units = mechanics::mechanics_unit_contract(128);
    const mechanics::AuthoritativePacket first{
        1, {}, {}, Mass::from_raw(1)};
    const mechanics::AuthoritativePacket second{
        2, {Length::from_raw(1'001'000'000), {}, {}}, {}, Mass::from_raw(1)};
    const auto impulse = mechanics::evaluate_central_impulse(
        {first, second, {0.0006, 0.0, 0.0}, Time::from_raw(1'000'000'000),
         16, mechanics::QuantizationPath::fixed_point_refinement},
        units);
    MLS_REQUIRE(impulse.exact_linear_momentum);
    MLS_REQUIRE(impulse.exact_orbital_angular_momentum);

    const drift::DriftPacket drift_packet{
        3,
        {Length::from_raw(9), Length::from_raw(-6), Length::from_raw(3)},
        {Momentum::from_raw(-3), Momentum::from_raw(5),
         Momentum::from_raw(-7)},
        Mass::from_raw(41)};
    const auto accepted_drift = drift::evaluate_drift(
        {drift_packet, Time::from_raw(32), 32,
         drift::DriftPath::primitive_directional},
        units);
    MLS_REQUIRE(accepted_drift.exact_momentum_unchanged);
    MLS_REQUIRE(accepted_drift.exact_orbital_angular_momentum);
    const auto cartesian = drift::evaluate_drift(
        {drift_packet, Time::from_raw(32), 32,
         drift::DriftPath::cartesian_nearest},
        mechanics::mechanics_unit_contract(16));
    MLS_REQUIRE(!cartesian.exact_orbital_angular_momentum);

    MLS_REQUIRE(drift::evaluate_relation_chord(
        {1, {Length::from_raw(1'000'000), {}, {}},
         {Length::from_raw(1'000'000), Length::from_raw(10), {}},
         Length::from_raw(1'000'000)}).admissible_force_domain);
    MLS_REQUIRE(!drift::evaluate_relation_chord(
        {2, {Length::from_raw(1'000'000), {}, {}},
         {Length::from_raw(-1'000'000), {}, {}},
         Length::from_raw(1'000'000)}).admissible_force_domain);
}

MLS_TEST("quantized KDK preserves exact invariants at every stage") {
    const auto reference = k4_reference();
    const auto model = time_lab::build_registered_model(reference, k4_relations());
    const auto initial = breathing_state(true);
    const auto step = time_lab::evaluate_step(
        model,
        {time_lab::IntegratorPath::quantized_kick_drift_kick,
         initial, Time::from_raw(62'500'000)});
    MLS_REQUIRE_EQ(step.status, time_lab::StepStatus::accepted);
    MLS_REQUIRE(step.exact_momentum_preserved);
    MLS_REQUIRE(step.exact_orbital_angular_momentum_preserved);
    MLS_REQUIRE_EQ(step.stages.size(), 5U);
    for (const auto& stage : step.stages) {
        MLS_REQUIRE_EQ(stage.invariants, step.stages.front().invariants);
    }
    MLS_REQUIRE(step.energy_before.evaluated);
    MLS_REQUIRE(step.energy_after.evaluated);
}

MLS_TEST("quantized KDK signed-time composition is bit reversible") {
    const auto reference = k4_reference();
    const auto model = time_lab::build_registered_model(reference, k4_relations());
    const auto initial = breathing_state(true);
    const auto forward = time_lab::evaluate_trajectory(
        model, time_lab::IntegratorPath::quantized_kick_drift_kick,
        initial, Time::from_raw(31'250'000), 8);
    MLS_REQUIRE_EQ(forward.status, time_lab::StepStatus::accepted);
    const auto backward = time_lab::evaluate_trajectory(
        model, time_lab::IntegratorPath::quantized_kick_drift_kick,
        forward.final_state, Time::from_raw(-31'250'000), 8);
    MLS_REQUIRE_EQ(backward.status, time_lab::StepStatus::accepted);
    MLS_REQUIRE_EQ(backward.final_state, initial);
}

MLS_TEST("time-map translation leaves exact relative trajectory unchanged") {
    const auto reference = k4_reference();
    const auto relations = k4_relations();
    const auto model = time_lab::build_registered_model(reference, relations);
    const auto initial = breathing_state(true);
    const auto base = time_lab::evaluate_trajectory(
        model, time_lab::IntegratorPath::quantized_kick_drift_kick,
        initial, Time::from_raw(31'250'000), 4);

    const mls::Position3 shift{
        Length::from_raw(17 * metre), Length::from_raw(-11 * metre),
        Length::from_raw(7 * metre)};
    const auto translated_reference = translated({{}, reference}, shift).packets;
    const auto translated_model = time_lab::build_registered_model(
        translated_reference, relations);
    const auto shifted = time_lab::evaluate_trajectory(
        translated_model, time_lab::IntegratorPath::quantized_kick_drift_kick,
        translated(initial, shift), Time::from_raw(31'250'000), 4);
    MLS_REQUIRE_EQ(base.status, time_lab::StepStatus::accepted);
    MLS_REQUIRE_EQ(shifted.status, time_lab::StepStatus::accepted);
    for (std::size_t index = 1; index < base.final_state.packets.size(); ++index) {
        MLS_REQUIRE_EQ(
            relative(base.final_state, index),
            relative(shifted.final_state, index));
        MLS_REQUIRE_EQ(
            base.final_state.packets[index].momentum -
                base.final_state.packets[0].momentum,
            shifted.final_state.packets[index].momentum -
                shifted.final_state.packets[0].momentum);
    }
}

MLS_TEST("crossing drift rejects the entire time step atomically") {
    const auto reference = std::vector<DynamicPacket>{
        packet(1, -metre, 0, 0), packet(2, metre, 0, 0)};
    const auto model = time_lab::build_registered_model(
        reference, std::array{observation::BondRelation{1, 2}});
    auto initial = PhaseState{{}, reference};
    constexpr mls::Scalar two_metres_per_second_raw = 134'217'728;
    initial.packets[0].momentum.x = Momentum::from_raw(
        two_metres_per_second_raw);
    initial.packets[1].momentum.x = Momentum::from_raw(
        -two_metres_per_second_raw);
    const auto before = time_lab::encode_phase_checkpoint(initial);
    const auto result = time_lab::evaluate_step(
        model,
        {time_lab::IntegratorPath::quantized_kick_drift_kick,
         initial, Time::from_raw(1'000'000'000)});
    MLS_REQUIRE_EQ(result.status, time_lab::StepStatus::chord_domain_failure);
    MLS_REQUIRE_EQ(result.failed_relation.first_id, 1U);
    MLS_REQUIRE_EQ(result.failed_relation.second_id, 2U);
    MLS_REQUIRE(result.state_unchanged_on_rejection);
    MLS_REQUIRE_EQ(time_lab::encode_phase_checkpoint(result.next_state), before);
    MLS_REQUIRE_EQ(result.next_state.physical_time, Time{});
}

MLS_TEST("time-map checkpoint resume reproduces final state and events") {
    const auto reference = k4_reference();
    const auto model = time_lab::build_registered_model(reference, k4_relations());
    const auto initial = breathing_state(true);
    const auto whole = time_lab::evaluate_trajectory(
        model, time_lab::IntegratorPath::quantized_kick_drift_kick,
        initial, Time::from_raw(15'625'000), 16);
    const auto first = time_lab::evaluate_trajectory(
        model, time_lab::IntegratorPath::quantized_kick_drift_kick,
        initial, Time::from_raw(15'625'000), 8);
    const auto encoded = time_lab::encode_phase_checkpoint(first.final_state);
    const auto resumed_state = time_lab::decode_phase_checkpoint(encoded);
    const auto second = time_lab::evaluate_trajectory(
        model, time_lab::IntegratorPath::quantized_kick_drift_kick,
        resumed_state, Time::from_raw(15'625'000), 8);
    MLS_REQUIRE_EQ(whole.status, time_lab::StepStatus::accepted);
    MLS_REQUIRE_EQ(second.status, time_lab::StepStatus::accepted);
    MLS_REQUIRE_EQ(second.final_state, whole.final_state);
    for (std::size_t index = 0; index < second.event_hashes.size(); ++index) {
        MLS_REQUIRE_EQ(second.event_hashes[index], whole.event_hashes[index + 8U]);
    }
}
