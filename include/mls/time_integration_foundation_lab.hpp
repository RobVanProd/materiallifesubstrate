#pragma once

#include "mls/authoritative_drift_state_bridge_lab.hpp"
#include "mls/relation_geometry_resolution_lab.hpp"

#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>
#include <string_view>
#include <vector>

namespace mls::experimental::time_integration_foundation {

namespace drift = authoritative_drift_state_bridge;
namespace force = conservative_force_consistency;
namespace geometry = relation_geometry_resolution;
namespace mechanics = authoritative_mechanics_state_bridge;
namespace observation = mechanical_observability;

inline constexpr std::uint32_t selected_refinement = 128U;
inline constexpr int safe_domain_exponent = -24;
inline constexpr std::uint32_t checkpoint_version = 1U;

enum class IntegratorPath : std::uint8_t {
    symplectic_euler_control,
    quantized_kick_drift_kick,
};

[[nodiscard]] std::string_view path_name(IntegratorPath path) noexcept;

enum class StepStatus : std::uint8_t {
    accepted,
    initial_domain_failure,
    force_domain_failure,
    chord_domain_failure,
    invariant_failure,
    arithmetic_failure,
};

[[nodiscard]] std::string_view status_name(StepStatus status) noexcept;

enum class StageKind : std::uint8_t {
    initial,
    first_kick,
    drift,
    second_kick,
    committed,
    rejected,
};

[[nodiscard]] std::string_view stage_name(StageKind stage) noexcept;

struct DynamicPacket final {
    std::uint64_t id{0};
    Position3 position{};
    Momentum3 momentum{};
    Mass mass{};

    [[nodiscard]] constexpr auto operator<=>(
        const DynamicPacket&) const noexcept = default;
};

struct PhaseState final {
    Time physical_time{};
    std::vector<DynamicPacket> packets{};

    [[nodiscard]] constexpr bool operator==(
        const PhaseState&) const noexcept = default;
};

struct DynamicModel final {
    // Exact R=128 reference state. Momentum is ignored while constructing the
    // frozen accepted constitutive operator.
    std::vector<DynamicPacket> reference_packets{};
    force::FrozenForceOperator frozen_force{};
};

// Constructs the accepted unit-weight local collective model with K/G=2.
// This is experimental model setup, not a constitutive rebuild during a step.
[[nodiscard]] DynamicModel build_registered_model(
    std::span<const DynamicPacket> reference_packets,
    std::span<const observation::BondRelation> relations);

struct ExactInvariants final {
    Momentum3 total_momentum{};
    AngularMomentum3 orbital_angular_momentum{};

    [[nodiscard]] constexpr bool operator==(
        const ExactInvariants&) const noexcept = default;
};

[[nodiscard]] ExactInvariants evaluate_exact_invariants(
    std::span<const DynamicPacket> packets);

struct StageRecord final {
    StageKind stage{StageKind::initial};
    ExactInvariants invariants{};
    std::uint64_t state_hash{0};

    [[nodiscard]] constexpr bool operator==(
        const StageRecord&) const noexcept = default;
};

struct EnergyDiagnostic final {
    double exact_integer_state_kinetic_j{0.0};
    Energy floored_integer_kinetic{};
    double accepted_potential_j{0.0};
    double mechanical_energy_j{0.0};
    bool evaluated{false};
};

[[nodiscard]] EnergyDiagnostic evaluate_energy(
    const DynamicModel& model,
    const PhaseState& state);

struct StepInput final {
    IntegratorPath path{IntegratorPath::quantized_kick_drift_kick};
    PhaseState state{};
    // Signed and nonzero. Registered KDK values are even raw counts so h/2 is
    // an exact authoritative duration.
    Time timestep{};
};

struct StepResult final {
    IntegratorPath path{IntegratorPath::quantized_kick_drift_kick};
    StepStatus status{StepStatus::arithmetic_failure};
    PhaseState prior_state{};
    // Equals prior_state for every rejected step.
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

// Applies one signed-time experimental step. All work occurs on a copy and a
// failure returns the prior state byte-for-byte. It never mutates World.
[[nodiscard]] StepResult evaluate_step(
    const DynamicModel& model,
    const StepInput& input);

struct TrajectoryResult final {
    IntegratorPath path{IntegratorPath::quantized_kick_drift_kick};
    StepStatus status{StepStatus::arithmetic_failure};
    PhaseState initial_state{};
    PhaseState final_state{};
    std::uint64_t requested_steps{0};
    std::uint64_t completed_steps{0};
    std::vector<std::uint64_t> event_hashes{};
    std::vector<double> mechanical_energy_j{};
    bool exact_momentum_preserved{false};
    bool exact_orbital_angular_momentum_preserved{false};
};

[[nodiscard]] TrajectoryResult evaluate_trajectory(
    const DynamicModel& model,
    IntegratorPath path,
    const PhaseState& initial_state,
    Time timestep,
    std::uint64_t step_count);

// Canonical little-endian experimental checkpoint. It contains no model,
// force cache, geometry cache, remainder, or energy ledger.
[[nodiscard]] std::vector<std::uint8_t> encode_phase_checkpoint(
    const PhaseState& state);
[[nodiscard]] PhaseState decode_phase_checkpoint(
    std::span<const std::uint8_t> bytes);
[[nodiscard]] std::uint64_t hash_phase_state(const PhaseState& state);

} // namespace mls::experimental::time_integration_foundation
