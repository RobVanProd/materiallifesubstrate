#include "mls/time.hpp"

#include <stdexcept>

namespace mls {

void validate_time_configuration(
    Time physical_timestep,
    const PhysicalTimeScale& physical_time_scale,
    const MomentumMassToVelocityScale& momentum_mass_to_velocity_scale) {
    if (physical_timestep.raw() <= 0) {
        throw std::invalid_argument("physical timestep must be positive");
    }
    if (physical_time_scale.seconds_per_time_quantum_numerator == 0 ||
        physical_time_scale.seconds_per_time_quantum_denominator == 0) {
        throw std::invalid_argument("seconds per time quantum must be a positive rational");
    }
    if (momentum_mass_to_velocity_scale.length_quanta_numerator <= 0 ||
        momentum_mass_to_velocity_scale.length_quanta_denominator <= 0) {
        throw std::invalid_argument(
            "momentum/mass to velocity scale must be a positive rational");
    }
}

} // namespace mls
