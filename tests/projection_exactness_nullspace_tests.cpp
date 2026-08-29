#include "test_harness.hpp"

#include "mls/projection_exactness_nullspace_lab.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

namespace {

namespace diagnostic = mls::experimental::projection_exactness_nullspace;
namespace projection = mls::experimental::projection_foundation;
using diagnostic::AffineVelocityField;
using mls::experimental::Matrix3d;
using mls::experimental::TransferConfig;
using mls::experimental::Vec3d;
using projection::CenterParticle;

[[nodiscard]] Matrix3d affine_matrix() {
    Matrix3d result{};
    result.value = {{{0.15, 0.40, 0.35},
                     {0.25, -0.10, -0.55},
                     {-0.30, 0.70, 0.20}}};
    return result;
}

[[nodiscard]] std::vector<CenterParticle> affine_lattice(
    const AffineVelocityField& field) {
    std::vector<CenterParticle> result;
    std::uint64_t id = 1U;
    for (std::size_t ix = 0; ix < 4U; ++ix) {
        for (std::size_t iy = 0; iy < 4U; ++iy) {
            for (std::size_t iz = 0; iz < 4U; ++iz) {
                const Vec3d position{
                    -0.375 + 0.25 * static_cast<double>(ix),
                    -0.375 + 0.25 * static_cast<double>(iy),
                    -0.375 + 0.25 * static_cast<double>(iz),
                };
                result.push_back({
                    id++, 2, position, diagnostic::evaluate(field, position)});
            }
        }
    }
    return result;
}

} // namespace

MLS_TEST("projection exactness analytic witness bypasses every solver") {
    const AffineVelocityField field{affine_matrix(), {0.888, -0.645, -0.592}};
    const auto particles = affine_lattice(field);
    const auto system = projection::build_projection_system(
        particles, TransferConfig{1.0, {0.13, -0.07, 0.21}, 0.01});
    const auto witness = diagnostic::evaluate_analytic_affine_witness(system, field);

    MLS_REQUIRE_EQ(
        witness.analytic_grid_velocity_m_per_s.size(),
        system.active_nodes().size());
    MLS_REQUIRE(witness.assembled_equation.relative_l2 < 2.0e-15);
    MLS_REQUIRE(witness.particle_reconstruction.relative_l2 < 2.0e-15);
    MLS_REQUIRE(witness.partition_unity_max_residual < 1.0e-14);
    MLS_REQUIRE(witness.linear_reproduction_max_residual_m < 1.0e-14);
    MLS_REQUIRE(witness.derivative_partition_max_residual_m_inv < 2.0e-14);
    MLS_REQUIRE(witness.maximum_matrix_row_nonzeros > 0U);
    MLS_REQUIRE(witness.maximum_particle_stencil_size <= 27U);
    MLS_REQUIRE(witness.maximum_rhs_particle_contributions_per_row > 0U);
}

MLS_TEST("projection exactness high precision retains auditable hi lo solution") {
    const AffineVelocityField field{affine_matrix(), {0.888, -0.645, -0.592}};
    const auto particles = affine_lattice(field);
    const auto system = projection::build_projection_system(
        particles, TransferConfig{1.0, {}, 0.01});
    const auto high_precision = diagnostic::solve_affine_high_precision(system, field);

    MLS_REQUIRE_EQ(
        high_precision.status, diagnostic::HighPrecisionStatus::solved);
    MLS_REQUIRE_EQ(high_precision.threshold_rank, system.active_nodes().size());
    MLS_REQUIRE_EQ(
        high_precision.grid_velocity_extended.size(), system.active_nodes().size());
    MLS_REQUIRE_EQ(
        high_precision.row_permutation.size(), system.active_nodes().size());
    MLS_REQUIRE_EQ(
        high_precision.column_permutation.size(), system.active_nodes().size());
    MLS_REQUIRE(!high_precision.regularization_applied);
    std::cout << "[EVIDENCE] hp_backward="
              << high_precision.backward_error.relative_l2
              << " hp_grid_forward="
              << high_precision.grid_forward_error.relative_l2
              << " hp_particle_forward="
              << high_precision.particle_reconstruction_error.relative_l2 << '\n';
    MLS_REQUIRE(high_precision.backward_error.relative_l2 < 1.0e-25);
    // M and q are the exact binary64 assembly, so assembly roundoff amplified
    // through its condition number can move the nodal solution away from g.
    // The particle reconstruction is the physically relevant comparison.
    MLS_REQUIRE(high_precision.grid_forward_error.relative_l2 < 1.0e-10);
    MLS_REQUIRE(high_precision.particle_reconstruction_error.relative_l2 < 1.0e-12);

    MLS_REQUIRE_EQ(
        diagnostic::canonical_decimal({1.0, 0.0}, 35),
        std::string{"1.0000000000000000000000000000000000e+0"});
    MLS_REQUIRE_EQ(
        diagnostic::canonical_decimal({1.0, std::ldexp(1.0, -54)}, 35),
        std::string{"1.0000000000000000555111512312578270e+0"});
}

MLS_TEST("projection Gram QR exhibits center invisible gradient visible modes") {
    const AffineVelocityField field{affine_matrix(), {0.888, -0.645, -0.592}};
    const Vec3d position{0.1, 0.2, 0.3};
    const std::vector<CenterParticle> particles{
        {1, 2, position, diagnostic::evaluate(field, position)},
    };
    const auto system = projection::build_projection_system(
        particles, TransferConfig{1.0, {}, 0.01});
    const auto witness = diagnostic::evaluate_analytic_affine_witness(system, field);
    const auto nullspace = diagnostic::diagnose_gram_nullspace(
        system, witness.analytic_grid_velocity_m_per_s);

    MLS_REQUIRE_EQ(nullspace.status, diagnostic::NullspaceStatus::analyzed);
    MLS_REQUIRE_EQ(nullspace.threshold_rank, std::size_t{1});
    MLS_REQUIRE_EQ(nullspace.nullity, system.active_nodes().size() - 1U);
    MLS_REQUIRE_EQ(nullspace.modes.size(), nullspace.nullity);
    MLS_REQUIRE(nullspace.gradient_weight_reconstruction_max_residual < 2.0e-16);
    auto gradient_visible = false;
    for (const auto& mode : nullspace.modes) {
        MLS_REQUIRE(std::abs(
            *std::ranges::max_element(
                mode.nodal_mode,
                {},
                [](double value) { return std::abs(value); })) <= 1.0 + 1.0e-14);
        MLS_REQUIRE(mode.mass_image_relative < 2.0e-14);
        MLS_REQUIRE(mode.particle_center_image_relative < 2.0e-14);
        MLS_REQUIRE(mode.perturbed_particle_difference_max_m_per_s < 2.0e-14);
        gradient_visible = gradient_visible ||
            mode.particle_gradient_max_m_inv >
                1.0e4 * mode.particle_gradient_roundoff_bound_max_m_inv;
    }
    MLS_REQUIRE(gradient_visible);
}
