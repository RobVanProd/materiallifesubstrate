#pragma once

#include "mls/transfer_lab.hpp"

#include <cstdint>
#include <map>
#include <span>
#include <string_view>
#include <vector>

namespace mls::experimental::affine_advection {

// This namespace is a force-free diagnostic laboratory. None of its state or
// transitions are part of the authoritative MLS World ABI.
enum class Path : std::uint8_t {
    analytic_ballistic,
    frozen_static_apic,
    sealed_static_apic_ballistic,
    analytic_convected_affine_control,
    jst2017_moving_apic,
};

[[nodiscard]] std::string_view path_name(Path path) noexcept;

// Global Eulerian affine velocity field v(x) = A x + b.
struct AffineField final {
    Matrix3d gradient_per_s{};
    Vec3d offset_m_per_s{};

    [[nodiscard]] constexpr bool operator==(const AffineField&) const noexcept = default;
};

[[nodiscard]] Vec3d velocity_at(const AffineField& field, Vec3d position_m) noexcept;

// Force-free material advection over one explicit Euler step. The returned
// Eulerian representation is A' = A(I+dt A)^-1 and b'=(I+dt A)^-1 b.
// Throws when I+dt A is singular or numerically unresolved.
[[nodiscard]] AffineField convected_affine_field(
    const AffineField& field, double timestep_s);

// Exact algebraic defect of reusing the old affine field for a second step of
// size h after one ballistic step: h^2 A(Ax+b) in position and
// h A(Ax+b) in the stale Eulerian velocity sample.
[[nodiscard]] Vec3d stale_gradient_position_defect(
    const AffineField& field, Vec3d initial_position_m, double half_step_s) noexcept;
[[nodiscard]] Vec3d stale_gradient_velocity_defect(
    const AffineField& field, Vec3d initial_position_m, double half_step_s) noexcept;

// Advance positions ballistically while preserving every material particle's
// velocity. The APIC auxiliary is deliberately untouched.
[[nodiscard]] std::vector<TransferParticle> ballistic_step(
    std::span<const TransferParticle> particles, double timestep_s);

// Path C: exactly compose the sealed static APIC round trip with the ballistic
// position update. This calls the accepted Time + Transfer implementation and
// does not claim to be the full moving-particle APIC algorithm.
[[nodiscard]] std::vector<TransferParticle> sealed_static_apic_ballistic_step(
    std::span<const TransferParticle> particles,
    const TransferConfig& config,
    double timestep_s);

// Path D: diagnostic-only Path C plus the analytically convected global affine
// matrix. It is not a production candidate and cannot be promoted.
struct ConvectedControlStep final {
    std::vector<TransferParticle> particles{};
    AffineField field{};
};

[[nodiscard]] ConvectedControlStep analytic_convected_control_step(
    std::span<const TransferParticle> particles,
    const TransferConfig& config,
    const AffineField& field,
    double timestep_s);

// Jiang--Schroeder--Teran (JCP 2017) moving APIC state. B has units m^2/s and
// C=B D^-1 has units 1/s. Keeping B explicit prevents the static C remap from
// being silently presented as the paper's moving-state algorithm.
struct MovingApicParticle final {
    std::uint64_t id{0};
    std::int64_t mass_quanta{0};
    Vec3d position_m{};
    Vec3d velocity_m_per_s{};
    Matrix3d B_m2_per_s{};

    [[nodiscard]] constexpr bool operator==(const MovingApicParticle&) const noexcept = default;
};

struct MovingApicGridNode final {
    Vec3d old_position_m{};
    Vec3d conceptual_new_position_m{};
    double mass_kg{0.0};
    Vec3d momentum_kg_m_per_s{};
    Vec3d old_velocity_m_per_s{};
    Vec3d new_velocity_m_per_s{};
};

struct MovingApicStep final {
    std::vector<MovingApicParticle> particles{};
    std::map<GridIndex, MovingApicGridNode> grid{};
    std::int64_t exact_mass_quanta_before{0};
    std::int64_t exact_mass_quanta_after{0};
    TransferTotals particle_before{};
    TransferTotals grid_after_p2g{};
    TransferTotals grid_after_no_force_evolution{};
    TransferTotals particle_after{};
    // Approximation diagnostics only; never physical ledger channels.
    double p2g_center_energy_residual_j{0.0};
    double step_center_energy_residual_j{0.0};
    double p2g_augmented_representation_energy_residual_j{0.0};
    double step_augmented_representation_energy_residual_j{0.0};
};

[[nodiscard]] Matrix3d particle_moment_matrix(
    Vec3d particle_position_m, const TransferConfig& config);

[[nodiscard]] MovingApicParticle initialize_moving_apic_particle(
    const TransferParticle& particle, const TransferConfig& config);

[[nodiscard]] Matrix3d moving_apic_affine_matrix(
    const MovingApicParticle& particle, const TransferConfig& config);

[[nodiscard]] TransferParticle as_transfer_particle(
    const MovingApicParticle& particle, const TransferConfig& config);

[[nodiscard]] std::vector<TransferParticle> as_transfer_particles(
    std::span<const MovingApicParticle> particles, const TransferConfig& config);

// Literature-faithful force-free moving path using JST 2017 Eqs. (24)--(26),
// (30), and (37)--(39). Old weights w^n are used throughout the step. The
// fixed Cartesian grid remains storage; conceptual new grid positions only
// enter the time-aware G2P update.
[[nodiscard]] MovingApicStep jst2017_moving_apic_no_force_step(
    std::span<const MovingApicParticle> particles,
    const TransferConfig& config,
    double timestep_s);

} // namespace mls::experimental::affine_advection
