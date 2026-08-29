#pragma once

#include "mls/projection_foundation_lab.hpp"

#include <array>
#include <cstddef>
#include <limits>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace mls::experimental::projection_exactness_nullspace {

namespace projection = projection_foundation;

// A prescribed Eulerian affine velocity field. This is diagnostic input, not
// persistent packet state.
struct AffineVelocityField final {
    Matrix3d gradient_per_s{};
    Vec3d intercept_m_per_s{};
};

[[nodiscard]] Vec3d evaluate(
    const AffineVelocityField& field, Vec3d position_m) noexcept;

struct BasisWeightGradient final {
    double weight{0.0};
    Vec3d gradient_m_inv{};
};

// Independent analytic derivative of the exact tensor-product quadratic
// B-spline used by quadratic_bspline_samples. The producer exports this next
// to every selected stencil entry for external recomputation.
[[nodiscard]] BasisWeightGradient evaluate_quadratic_bspline_basis(
    Vec3d particle_position_m,
    Vec3d node_position_m,
    double grid_spacing_m);

struct ErrorNorms final {
    double absolute_l2{0.0};
    double absolute_max{0.0};
    double reference_l2{0.0};
    double relative_l2{0.0};
    // A diagnostic Higham-style gamma_n scale computed from the actual sums.
    // It is not itself a pass threshold; the preregistered experiment chooses
    // the multiplier before inspecting its final sweep.
    double roundoff_scale_l2{0.0};
};

struct AnalyticAffineWitness final {
    std::vector<Vec3d> analytic_grid_velocity_m_per_s{};
    std::vector<Vec3d> mass_times_analytic_grid_kg_m_per_s{};
    std::vector<Vec3d> reconstructed_particle_velocity_m_per_s{};
    ErrorNorms assembled_equation{};       // ||M g - q||
    ErrorNorms particle_reconstruction{};  // ||S g - V||
    double partition_unity_max_residual{0.0};
    double partition_unity_roundoff_scale{0.0};
    double linear_reproduction_max_residual_m{0.0};
    double linear_reproduction_roundoff_scale_m{0.0};
    double derivative_partition_max_residual_m_inv{0.0};
    double derivative_partition_roundoff_scale_m_inv{0.0};
    std::size_t maximum_matrix_row_nonzeros{0};
    std::size_t maximum_particle_stencil_size{0};
    std::size_t maximum_rhs_particle_contributions_per_row{0};
    std::string assembled_equation_normalization{};
    std::string reconstruction_normalization{};
    std::string roundoff_model{};
};

// Constructs g_i=A*x_i+b and evaluates the finite assembled identities before
// any linear solver participates.
[[nodiscard]] AnalyticAffineWitness evaluate_analytic_affine_witness(
    const projection::ProjectionSystem& system,
    const AffineVelocityField& field);

struct FullSolveDiagnostics final {
    projection::ProjectionStatus solver_status{projection::ProjectionStatus::empty};
    bool grid_solution_available{false};
    ErrorNorms backward_error{};             // ||M v_hat-q||
    ErrorNorms grid_forward_error{};          // ||v_hat-g||
    ErrorNorms particle_reconstruction_error{}; // ||S v_hat-V||
    std::array<double, 3> component_absolute_backward_error{};
    std::array<double, 3> component_normalized_backward_error{};
    std::array<double, 3> raw_condition_times_residual{};
    std::array<double, 3> preconditioned_condition_times_residual{};
    double raw_condition_value{std::numeric_limits<double>::quiet_NaN()};
    double preconditioned_condition_value{
        std::numeric_limits<double>::quiet_NaN()};
    bool condition_is_certified{false};
    bool condition_is_ritz_or_floating_estimate{false};
    std::string condition_method{};
    std::string backward_error_normalization{};
    std::string grid_forward_error_normalization{};
    std::string reconstruction_error_normalization{};
};

// Recomputes backward and forward errors independently of the legacy solver's
// acceptance decision. The supplied result may come from the unchanged PCG
// control or from another diagnostic solver.
[[nodiscard]] FullSolveDiagnostics diagnose_affine_full_solve(
    const projection::ProjectionSystem& system,
    const projection::ProjectionResult& result,
    const AffineVelocityField& field);

// Calls the sealed full-consistent PCG path without altering its policy or
// implementation. This wrapper exists solely to make the control explicit.
[[nodiscard]] projection::ProjectionResult run_legacy_pcg_control(
    const projection::ProjectionSystem& system,
    const projection::ProjectionSolvePolicy& policy = {});

// Public hi/lo form used to retain approximately 106 significant binary bits
// in evidence without exposing the arithmetic implementation as production
// state.
struct ExtendedScalar final {
    double hi{0.0};
    double lo{0.0};

    [[nodiscard]] double binary64_approximation() const noexcept { return hi + lo; }
};

// Exact conversion of the represented hi+lo sum followed by round-to-nearest,
// ties away from zero at the requested decimal digit. The scientific notation
// is locale-independent and always contains exactly significant_digits.
[[nodiscard]] std::string canonical_decimal(
    ExtendedScalar value, std::size_t significant_digits = 35);

enum class HighPrecisionStatus : std::uint8_t {
    solved,
    empty,
    size_limit,
    rank_deficient,
    numerical_failure,
};

[[nodiscard]] std::string_view status_name(HighPrecisionStatus status) noexcept;

struct HighPrecisionSolvePolicy final {
    std::size_t maximum_nodes{400};
    // threshold = factor * n * 2^-104 * max_ij |M_ij|. This detects a
    // numerical rank at the roundoff scale; it is not regularization.
    double rank_roundoff_safety_factor{4096.0};
};

struct HighPrecisionSolveResult final {
    HighPrecisionStatus status{HighPrecisionStatus::empty};
    std::size_t node_count{0};
    std::size_t threshold_rank{0};
    std::size_t significand_bits{106};
    bool rank_is_threshold_diagnostic{true};
    bool regularization_applied{false};
    std::string arithmetic_method{};
    std::string factorization_method{};
    ExtendedScalar numerical_rank_threshold{};
    std::vector<std::size_t> row_permutation{};
    std::vector<std::size_t> column_permutation{};
    // Entry k is the accepted absolute pivot after row/column k of the final
    // permutations was fixed. Its size is exactly threshold_rank.
    std::vector<ExtendedScalar> accepted_absolute_pivots{};
    ExtendedScalar largest_absolute_pivot{};
    ExtendedScalar smallest_accepted_absolute_pivot{};
    double pivot_ratio_estimate{std::numeric_limits<double>::infinity()};
    std::vector<Vec3d> grid_velocity_m_per_s{};
    std::vector<std::array<ExtendedScalar, 3>> grid_velocity_extended{};
    ErrorNorms backward_error{};
    ErrorNorms grid_forward_error{};
    ErrorNorms particle_reconstruction_error{};
    ExtendedScalar backward_error_max_extended{};
    ExtendedScalar grid_forward_error_max_extended{};
    ExtendedScalar particle_reconstruction_error_max_extended{};
    std::string backward_error_normalization{};
    std::string grid_forward_error_normalization{};
    std::string reconstruction_error_normalization{};
};

// Promotes the already assembled binary64 M and q into an independent
// FMA-based double-double dense complete-pivot solve. It never shifts,
// regularizes, drops nodes, or changes the basis.
[[nodiscard]] HighPrecisionSolveResult solve_affine_high_precision(
    const projection::ProjectionSystem& system,
    const AffineVelocityField& field,
    const HighPrecisionSolvePolicy& policy = {});

struct NullspacePolicy final {
    std::size_t maximum_particles{512};
    std::size_t maximum_nodes{256};
    // threshold = factor * max(P,N) * epsilon_binary64 * first_QR_pivot.
    double rank_roundoff_safety_factor{128.0};
    // A null mode z is perturbed as v'_i=v_i+z_i*amplitude. This has no
    // authoritative meaning and is used only to test solution equivalence.
    Vec3d perturbation_amplitude_m_per_s{1.0, 0.0, 0.0};
};

struct NullspaceModeDiagnostics final {
    std::size_t mode_index{0};
    std::vector<double> nodal_mode{};
    double nodal_l2_norm{0.0};
    double mass_image_l2_kg{0.0};             // ||M z||
    double mass_image_relative{0.0};
    double particle_center_image_l2{0.0};     // ||S z||
    double particle_center_image_max{0.0};
    double particle_center_image_relative{0.0};
    std::vector<Vec3d> particle_gradient_m_inv{}; // sum_i z_i grad N_i(x_p)
    double particle_gradient_l2_m_inv{0.0};
    double particle_gradient_max_m_inv{0.0};
    double particle_gradient_roundoff_bound_l2_m_inv{0.0};
    double particle_gradient_roundoff_bound_max_m_inv{0.0};
    double perturbed_grid_difference_l2_m_per_s{0.0};
    double perturbed_equation_residual_l2_kg_m_per_s{0.0};
    double equation_residual_change_l2_kg_m_per_s{0.0};
    double perturbed_particle_difference_l2_m_per_s{0.0};
    double perturbed_particle_difference_max_m_per_s{0.0};
};

enum class NullspaceStatus : std::uint8_t {
    analyzed,
    empty,
    size_limit,
    numerical_failure,
};

[[nodiscard]] std::string_view status_name(NullspaceStatus status) noexcept;

struct NullspaceDiagnostics final {
    NullspaceStatus status{NullspaceStatus::empty};
    std::size_t particle_count{0};
    std::size_t node_count{0};
    std::size_t threshold_rank{0};
    std::size_t nullity{0};
    bool rank_is_certified{false};
    std::string rank_method{};
    double largest_qr_diagonal{0.0};
    double smallest_accepted_qr_diagonal{0.0};
    double weighted_sampling_frobenius_norm{0.0};
    double sampling_frobenius_norm{0.0};
    double numerical_rank_threshold{0.0};
    double gradient_weight_reconstruction_max_residual{0.0};
    std::vector<std::size_t> column_permutation{};
    double representative_equation_residual_l2_kg_m_per_s{0.0};
    std::vector<NullspaceModeDiagnostics> modes{};
};

// Householder column-pivoted QR is applied to sqrt(W)S, independently of the
// production M solver. representative_grid_velocity must be a known solution
// (the analytic affine witness is valid even when M is singular).
[[nodiscard]] NullspaceDiagnostics diagnose_gram_nullspace(
    const projection::ProjectionSystem& system,
    std::span<const Vec3d> representative_grid_velocity_m_per_s,
    const NullspacePolicy& policy = {});

} // namespace mls::experimental::projection_exactness_nullspace
