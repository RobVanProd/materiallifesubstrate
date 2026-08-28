#pragma once

#include "mls/quantity.hpp"

#include <compare>
#include <cstdint>

namespace mls {

// Tick is the deterministic ballistic-step sequence counter. Other world
// transitions may share a Tick; it is deliberately not a physical-time
// quantity and carries no unit conversion.
using Tick = std::uint64_t;

// Exact scale for the Time fixed-point quantity. One raw Time quantum denotes
// seconds_per_time_quantum_numerator / seconds_per_time_quantum_denominator
// SI seconds. The ratio is stored rather than converted through floating point.
struct PhysicalTimeScale final {
    std::uint64_t seconds_per_time_quantum_numerator{1};
    std::uint64_t seconds_per_time_quantum_denominator{1'000'000'000};

    [[nodiscard]] constexpr auto operator<=>(const PhysicalTimeScale&) const noexcept = default;
};

// Explicit raw-unit bridge for ballistic reference integration:
//
//   displacement_length_quanta =
//       momentum_quanta * timestep_time_quanta * numerator
//       / (mass_quanta * denominator)
//
// The default 1/1 bridge and a one-quantum timestep reproduce the accepted
// MLS-0 p/m displacement. It is an explicit unit convention, not Tick-as-time.
struct MomentumMassToVelocityScale final {
    Scalar length_quanta_numerator{1};
    Scalar length_quanta_denominator{1};

    [[nodiscard]] constexpr auto operator<=>(
        const MomentumMassToVelocityScale&) const noexcept = default;
};

// Throws std::invalid_argument when a time configuration cannot define a
// positive physical step and unit scale.
void validate_time_configuration(
    Time physical_timestep,
    const PhysicalTimeScale& physical_time_scale,
    const MomentumMassToVelocityScale& momentum_mass_to_velocity_scale);

} // namespace mls
