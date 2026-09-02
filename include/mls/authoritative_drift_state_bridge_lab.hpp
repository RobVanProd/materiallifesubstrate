#pragma once

#include "mls/authoritative_mechanics_state_bridge_lab.hpp"

#include <array>
#include <cstdint>

namespace mls::experimental::authoritative_drift_state_bridge {

enum class DriftPath : std::uint8_t {
    cartesian_nearest,
    primitive_directional,
};

[[nodiscard]] const char* path_name(DriftPath path) noexcept;

struct DriftPacket final {
    std::uint64_t id{0};
    // Exact R=1 state.  Evaluation maps the same SI state into the requested
    // coherent mechanics refinement before applying a displacement.
    Position3 base_position{};
    Momentum3 base_momentum{};
    Mass base_mass{};

    [[nodiscard]] constexpr auto operator<=>(const DriftPacket&) const noexcept = default;
};

struct DriftInput final {
    DriftPacket packet{};
    Time horizon{};
    std::uint32_t subdivisions{1};
    DriftPath path{DriftPath::primitive_directional};
};

struct DriftEvaluation final {
    DriftPath path{DriftPath::primitive_directional};
    std::uint32_t refinement{1};
    std::uint32_t subdivisions{1};
    Time substep{};
    Position3 refined_position{};
    Momentum3 refined_momentum{};
    Mass refined_mass{};
    Scalar direction_gcd{0};
    Position3 primitive_direction{};
    Position3 applied_displacement{};
    Position3 final_position{};
    // Exact target displacement in refined length quanta is
    // target_numerator[axis] / target_denominator.
    std::array<Scalar, 3> target_numerator{};
    Scalar target_denominator{1};
    // Exact applied-minus-target numerator over target_denominator.
    std::array<Scalar, 3> error_numerator{};
    Vec3d exact_displacement_m{};
    Vec3d applied_displacement_m{};
    Vec3d component_error_m{};
    double vector_error_m{0.0};
    AngularMomentum3 orbital_angular_momentum_delta{};
    Momentum3 momentum_after{};
    Energy kinetic_energy_before{};
    Energy kinetic_energy_after{};
    std::uint64_t checked_product_margin{0};
    bool exact_momentum_unchanged{false};
    bool exact_kinetic_energy_unchanged{false};
    bool exact_orbital_angular_momentum{false};
};

// Deterministic signed-rational nearest-even rounding.  The denominator must
// be positive.  No binary floating-point value participates in the decision.
[[nodiscard]] Scalar nearest_even_rational(Scalar numerator, Scalar denominator);

// Checked product followed by the same nearest-even rational decision.  This
// seam exists for registered near-overflow controls; wrap is never accepted.
[[nodiscard]] Scalar nearest_even_product_ratio(
    Scalar multiplicand, Scalar multiplier, Scalar denominator);

// Read-only drift evaluation.  It does not mutate World, clock, packet state,
// momentum, mass, or any energy channel.
[[nodiscard]] DriftEvaluation evaluate_drift(
    const DriftInput& input,
    const authoritative_mechanics_state_bridge::MechanicsUnitContract& contract);

struct RelationChordInput final {
    std::uint64_t id{0};
    Position3 initial_relative{};
    Position3 final_relative{};
    Length rest_length{};
};

struct RelationChordEvaluation final {
    std::uint64_t id{0};
    bool interior_minimum{false};
    bool admissible_force_domain{false};
};

// Classifies the straight relative-position chord against r/l0 >= 2^-24.
// It never clips or modifies either endpoint.
[[nodiscard]] RelationChordEvaluation evaluate_relation_chord(
    const RelationChordInput& input);

} // namespace mls::experimental::authoritative_drift_state_bridge
