#pragma once

#include "mls/time.hpp"
#include "mls/transfer_lab.hpp"

#include <array>
#include <compare>
#include <cstddef>
#include <cstdint>
#include <map>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace mls::experimental::projection_foundation {

// This is the complete persistent particle state of this bounded experiment.
// In particular, it contains no affine/polynomial mode, spin, grid state, or
// numerical-energy reservoir.
struct CenterParticle final {
    std::uint64_t id{0};
    std::int64_t mass_quanta{0};
    Vec3d position_m{};
    Vec3d velocity_m_per_s{};

    [[nodiscard]] constexpr bool operator==(const CenterParticle&) const noexcept = default;
};

enum class ProjectionCandidate : std::uint8_t {
    lumped_pic,
    full_consistent,
    fmpm_1,
    fmpm_2,
    fmpm_3,
    fmpm_4,
};

[[nodiscard]] std::string_view candidate_name(ProjectionCandidate candidate) noexcept;

enum class ProjectionStatus : std::uint8_t {
    solved,
    empty,
    structurally_rank_deficient,
    numerically_rank_deficient,
    ill_conditioned,
    breakdown,
    iteration_limit,
    residual_failed,
};

[[nodiscard]] std::string_view status_name(ProjectionStatus status) noexcept;

struct ProjectionSolvePolicy final {
    double dense_relative_pivot_min{1.0e-12};
    double raw_condition_max{1.0e10};
    double preconditioned_condition_max{1.0e8};
    double normalized_residual_max{5.0e-12};
    std::size_t dense_diagnostic_max_nodes{128};
    std::size_t lanczos_max_steps{64};
    // Zero selects min(4*n, 10000), the frozen laboratory policy.
    std::size_t iteration_limit_override{0};
};

struct ProjectionDiagnostics final {
    std::size_t particle_count{0};
    std::size_t active_node_count{0};
    std::size_t shape_entry_count{0};
    std::size_t matrix_nonzero_count{0};
    std::uint64_t node_order_digest{0};
    std::int64_t exact_mass_quanta_before{0};
    std::int64_t exact_mass_quanta_after{0};
    std::size_t structural_rank_upper_bound{0};
    std::size_t numerical_rank_estimate{0};
    std::string numerical_rank_method{};
    bool numerical_rank_is_estimated{false};
    double smallest_spectral_or_pivot_value{0.0};
    double largest_spectral_or_pivot_value{0.0};
    double raw_condition_estimate{0.0};
    double preconditioned_condition_estimate{0.0};
    double matrix_symmetry_relative_residual{0.0};
    double row_sum_relative_residual{0.0};
    double partition_unity_max_residual{0.0};
    double linear_reproduction_max_residual_m{0.0};
    double grid_mass_relative_error{0.0};
    std::array<double, 3> absolute_solve_residual{};
    std::array<double, 3> normalized_solve_residual{};
    std::array<std::size_t, 3> component_iterations{};
    std::string termination_reason{};
};

struct ProjectionStencilEntry final {
    std::size_t node_index{0};
    double weight{0.0};

    [[nodiscard]] constexpr bool operator==(
        const ProjectionStencilEntry&) const noexcept = default;
};

// Deterministically rebuilt transient workspace. It is deliberately exposed
// for independent numerical inspection, but never checkpointed.
struct ProjectionSystem final {
    TransferConfig config{};
    std::vector<CenterParticle> particles{};
    std::vector<GridIndex> active_nodes{};
    std::vector<Vec3d> active_node_positions_m{};
    std::vector<std::vector<ProjectionStencilEntry>> particle_stencils{};
    std::vector<double> particle_mass_kg{};
    std::vector<double> lumped_mass_kg{};
    std::vector<std::map<std::size_t, double>> consistent_mass_rows{};
    std::vector<Vec3d> consistent_rhs_kg_m_per_s{};
    ProjectionDiagnostics assembly_diagnostics{};
};

[[nodiscard]] ProjectionSystem build_projection_system(
    std::span<const CenterParticle> particles,
    const TransferConfig& config);

[[nodiscard]] std::vector<Vec3d> apply_consistent_mass(
    const ProjectionSystem& system,
    std::span<const Vec3d> grid_values);

[[nodiscard]] std::vector<CenterParticle> reconstruct_centers(
    const ProjectionSystem& system,
    std::span<const Vec3d> grid_velocity_m_per_s);

struct ProjectionResult final {
    ProjectionCandidate candidate{ProjectionCandidate::lumped_pic};
    ProjectionStatus status{ProjectionStatus::empty};
    std::vector<Vec3d> grid_velocity_m_per_s{};
    std::vector<CenterParticle> particles{};
    ProjectionDiagnostics diagnostics{};
    // All energy quantities below are diagnostics. They are not ledger
    // channels and no transition converts them into physical energy.
    double center_kinetic_before_j{0.0};
    double center_kinetic_after_j{0.0};
    double consistent_grid_quadratic_energy_j{0.0};
    double numerical_projection_energy_residual_j{0.0};
    double fmpm_residual_identity_normalized{0.0};
};

[[nodiscard]] ProjectionResult project_centers(
    const ProjectionSystem& system,
    ProjectionCandidate candidate,
    const ProjectionSolvePolicy& policy = {});

[[nodiscard]] ProjectionResult project_centers(
    std::span<const CenterParticle> particles,
    const TransferConfig& config,
    ProjectionCandidate candidate,
    const ProjectionSolvePolicy& policy = {});

struct ProjectionLabState final {
    TransferConfig config{};
    PhysicalTimeScale physical_time_scale{};
    std::uint64_t elapsed_time_quanta{0};
    std::vector<CenterParticle> particles{};

    [[nodiscard]] constexpr bool operator==(const ProjectionLabState&) const noexcept = default;
};

struct ProjectionStep final {
    ProjectionResult projection{};
    ProjectionLabState state{};
};

// The binary64 timestep must agree with the exact quantum count and scale.
// A failed full projection does not move particles or advance the clock.
[[nodiscard]] ProjectionStep trapezoid_projection_step(
    const ProjectionLabState& state,
    ProjectionCandidate candidate,
    std::uint64_t timestep_quanta,
    double timestep_s,
    const ProjectionSolvePolicy& policy = {});

inline constexpr std::uint32_t projection_checkpoint_format_version = 1;

[[nodiscard]] std::vector<std::uint8_t> serialize_projection_checkpoint(
    const ProjectionLabState& state);

[[nodiscard]] ProjectionLabState deserialize_projection_checkpoint(
    std::span<const std::uint8_t> checkpoint);

} // namespace mls::experimental::projection_foundation
