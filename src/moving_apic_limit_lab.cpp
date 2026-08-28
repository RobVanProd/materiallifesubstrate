#include "mls/moving_apic_limit_lab.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace mls::experimental::moving_apic_limit {
namespace {

[[nodiscard]] bool finite(Vec3d value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) && std::isfinite(value.z);
}

[[nodiscard]] bool finite(const Matrix3d& matrix) noexcept {
    for (const auto& row : matrix.value) {
        for (const auto value : row) {
            if (!std::isfinite(value)) {
                return false;
            }
        }
    }
    return true;
}

[[nodiscard]] double stable_norm(const Matrix3d& matrix) noexcept {
    double result = 0.0;
    for (const auto& row : matrix.value) {
        for (const auto value : row) {
            result = std::hypot(result, value);
        }
    }
    return result;
}

[[nodiscard]] double stable_distance(
    const Matrix3d& lhs, const Matrix3d& rhs) noexcept {
    double result = 0.0;
    for (std::size_t row = 0; row < 3; ++row) {
        for (std::size_t column = 0; column < 3; ++column) {
            result = std::hypot(
                result, lhs.value[row][column] - rhs.value[row][column]);
        }
    }
    return result;
}

[[nodiscard]] double relative_matrix_distance(
    const Matrix3d& lhs, const Matrix3d& rhs) {
    const auto result = stable_distance(lhs, rhs) /
        std::max({1.0, stable_norm(lhs), stable_norm(rhs)});
    if (!std::isfinite(result)) {
        throw std::overflow_error("oracle-B matrix diagnostic overflow");
    }
    return result;
}

} // namespace

OracleBIntervention apply_oracle_B_after_G2P(
    std::span<const affine_advection::MovingApicParticle> paper_particles,
    const TransferConfig& config,
    const affine_advection::AffineField& exact_next_field) {
    if (!finite(exact_next_field.gradient_per_s) ||
        !finite(exact_next_field.offset_m_per_s)) {
        throw std::invalid_argument("oracle-B exact next affine field must be finite");
    }

    // These conversions validate the paper state and config using the same
    // experimental transfer contracts as Path E. They also canonicalize the
    // reductions by particle ID without changing the copied state order.
    const auto pre_override_particles =
        affine_advection::as_transfer_particles(paper_particles, config);

    OracleBIntervention result{};
    result.particles.assign(paper_particles.begin(), paper_particles.end());
    result.exact_mass_quanta_before = exact_particle_mass_quanta(pre_override_particles);
    result.pre_override_totals = particle_totals(pre_override_particles, config);

    for (auto& particle : result.particles) {
        const auto moment = affine_advection::particle_moment_matrix(
            particle.position_m, config);
        const auto target_B = multiply(exact_next_field.gradient_per_s, moment);
        if (!finite(target_B)) {
            throw std::overflow_error("oracle-B target matrix overflow");
        }
        result.max_relative_B_override = std::max(
            result.max_relative_B_override,
            relative_matrix_distance(particle.B_m2_per_s, target_B));
        particle.B_m2_per_s = target_B;
        result.max_relative_B_constraint_error = std::max(
            result.max_relative_B_constraint_error,
            relative_matrix_distance(particle.B_m2_per_s, target_B));
    }

    const auto post_override_particles =
        affine_advection::as_transfer_particles(result.particles, config);
    result.exact_mass_quanta_after = exact_particle_mass_quanta(post_override_particles);
    result.post_override_totals = particle_totals(post_override_particles, config);
    return result;
}

} // namespace mls::experimental::moving_apic_limit
