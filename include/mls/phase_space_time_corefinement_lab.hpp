#pragma once

#include "mls/time_integration_foundation_lab.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>
#include <string>
#include <vector>

namespace mls::experimental::phase_space_time_corefinement {

namespace mechanics = authoritative_mechanics_state_bridge;
namespace observation = mechanical_observability;
namespace time_foundation = time_integration_foundation;

inline constexpr std::uint32_t maximum_level = 4U;

struct UnitProfile final {
    std::uint32_t level{0};
    mechanics::PositiveRational length_quantum_m{};
    mechanics::PositiveRational mass_quantum_kg{};
    mechanics::PositiveRational time_quantum_s{};
    mechanics::PositiveRational momentum_quantum_kg_m_per_s{};
    mechanics::PositiveRational energy_quantum_j{};
    mechanics::PositiveRational force_quantum_n{};

    [[nodiscard]] constexpr auto operator<=>(
        const UnitProfile&) const noexcept = default;
};

// Constructs the preregistered exact unit family. All derived units are
// checked from Lq, Mq, and Tq; inconsistent profiles are rejected.
[[nodiscard]] UnitProfile unit_profile(std::uint32_t level);
void validate_unit_profile(const UnitProfile& profile);

// Read-only exact diagnostic integer. It is not authoritative state and is
// never serialized into a phase checkpoint. Three magnitude limbs cover a
// sum of all registered signed-64-bit position-momentum products.
struct SignedMagnitude192 final {
    bool negative{false};
    std::array<std::uint64_t, 3> magnitude{};

    [[nodiscard]] constexpr auto operator<=>(
        const SignedMagnitude192&) const noexcept = default;
};

struct WideAngularMomentum3 final {
    SignedMagnitude192 x{};
    SignedMagnitude192 y{};
    SignedMagnitude192 z{};

    [[nodiscard]] constexpr auto operator<=>(
        const WideAngularMomentum3&) const noexcept = default;
};

[[nodiscard]] std::string hexadecimal(const SignedMagnitude192& value);

using DynamicPacket = time_foundation::DynamicPacket;
using PhaseState = time_foundation::PhaseState;
using IntegratorPath = time_foundation::IntegratorPath;
using StepStatus = time_foundation::StepStatus;
using StageKind = time_foundation::StageKind;
using EnergyDiagnostic = time_foundation::EnergyDiagnostic;

struct ExactInvariants final {
    Momentum3 total_momentum{};
    WideAngularMomentum3 orbital_angular_momentum{};

    [[nodiscard]] constexpr auto operator<=>(
        const ExactInvariants&) const noexcept = default;
};

[[nodiscard]] ExactInvariants evaluate_exact_invariants(
    std::span<const DynamicPacket> packets);

struct PrimitiveMomentumDiagnostic final {
    std::uint64_t packet_id{0};
    Momentum3 momentum{};
    Scalar direction_gcd{0};
    std::array<Scalar, 3> primitive_direction{};

    [[nodiscard]] constexpr auto operator<=>(
        const PrimitiveMomentumDiagnostic&) const noexcept = default;
};

struct PrimitiveRelationDiagnostic final {
    std::size_t relation_index{0};
    observation::BondRelation relation{};
    Position3 relative_position{};
    Scalar direction_gcd{0};
    std::array<Scalar, 3> primitive_direction{};
    std::uint64_t target_multiple_bits{0};
    Scalar applied_multiple{0};
};

[[nodiscard]] PrimitiveMomentumDiagnostic primitive_momentum_diagnostic(
    const DynamicPacket& packet);

// Exposes the accepted stateless primitive-directional drift for bridge
// contract probes. The result is a raw displacement, not persistent state.
[[nodiscard]] Position3 evaluate_directional_drift(
    const DynamicPacket& packet,
    Time timestep);

struct DynamicModel final {
    std::uint32_t level{0};
    UnitProfile units{};
    std::vector<DynamicPacket> reference_packets{};
    conservative_force_consistency::FrozenForceOperator frozen_force{};
};

// Builds H exactly once from the accepted level-zero physical reference, then
// maps only the authoritative reference integers to the requested profile.
[[nodiscard]] DynamicModel build_registered_model(
    std::span<const DynamicPacket> level_zero_reference_packets,
    std::span<const observation::BondRelation> relations,
    std::uint32_t level);

// Maps an exact level-zero phase state to the same SI state at a registered
// co-refinement level. Signed-64-bit overflow is fail-closed.
[[nodiscard]] PhaseState map_level_zero_state(
    const PhaseState& level_zero_state,
    std::uint32_t level);

struct StageRecord final {
    StageKind stage{StageKind::initial};
    ExactInvariants invariants{};
    std::uint64_t state_hash{0};
    std::vector<PrimitiveMomentumDiagnostic> primitive_momenta{};
    std::vector<PrimitiveRelationDiagnostic> primitive_relations{};
};

struct StepInput final {
    IntegratorPath path{IntegratorPath::quantized_kick_drift_kick};
    PhaseState state{};
    Time timestep{};
};

struct StepResult final {
    IntegratorPath path{IntegratorPath::quantized_kick_drift_kick};
    StepStatus status{StepStatus::arithmetic_failure};
    PhaseState prior_state{};
    PhaseState next_state{};
    std::size_t failed_relation_index{
        std::numeric_limits<std::size_t>::max()};
    observation::BondRelation failed_relation{};
    std::vector<StageRecord> stages{};
    EnergyDiagnostic energy_before{};
    EnergyDiagnostic energy_after{};
    bool state_unchanged_on_rejection{false};
    bool exact_momentum_preserved{false};
    bool exact_orbital_angular_momentum_preserved{false};
};

[[nodiscard]] EnergyDiagnostic evaluate_energy(
    const DynamicModel& model,
    const PhaseState& state);

[[nodiscard]] StepResult evaluate_step(
    const DynamicModel& model,
    const StepInput& input);

struct TrajectoryPrimitiveRecord final {
    std::uint64_t step_index{0};
    StageKind stage{StageKind::initial};
    PrimitiveMomentumDiagnostic diagnostic{};
};

struct TrajectoryRelationRecord final {
    std::uint64_t step_index{0};
    StageKind stage{StageKind::initial};
    PrimitiveRelationDiagnostic diagnostic{};
};

struct TrajectoryResult final {
    IntegratorPath path{IntegratorPath::quantized_kick_drift_kick};
    StepStatus status{StepStatus::arithmetic_failure};
    PhaseState initial_state{};
    PhaseState final_state{};
    std::uint64_t requested_steps{0};
    std::uint64_t completed_steps{0};
    std::vector<std::uint64_t> event_hashes{};
    std::vector<double> mechanical_energy_j{};
    std::vector<TrajectoryPrimitiveRecord> primitive_records{};
    std::vector<TrajectoryRelationRecord> relation_records{};
    bool exact_momentum_preserved{false};
    bool exact_orbital_angular_momentum_preserved{false};
};

[[nodiscard]] TrajectoryResult evaluate_trajectory(
    const DynamicModel& model,
    IntegratorPath path,
    const PhaseState& initial_state,
    Time timestep,
    std::uint64_t step_count);

} // namespace mls::experimental::phase_space_time_corefinement
