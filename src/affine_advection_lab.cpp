#include "mls/affine_advection_lab.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <tuple>

namespace mls::experimental::affine_advection {
namespace {

[[nodiscard]] bool finite(Vec3d value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) && std::isfinite(value.z);
}

[[nodiscard]] bool finite(const Matrix3d& matrix) noexcept {
    for (const auto& row : matrix.value) {
        for (const auto entry : row) {
            if (!std::isfinite(entry)) {
                return false;
            }
        }
    }
    return true;
}

[[nodiscard]] double determinant(const Matrix3d& matrix) noexcept {
    const auto& a = matrix.value;
    return a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) -
        a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) +
        a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]);
}

[[nodiscard]] Matrix3d inverse(const Matrix3d& matrix) {
    if (!finite(matrix)) {
        throw std::invalid_argument("cannot invert a non-finite affine matrix");
    }
    const auto det = determinant(matrix);
    const auto matrix_norm = frobenius_norm(matrix);
    const auto scale = std::max(1.0, matrix_norm * matrix_norm * matrix_norm);
    if (!std::isfinite(det) ||
        std::abs(det) <= 64.0 * std::numeric_limits<double>::epsilon() * scale) {
        throw std::domain_error("singular or unresolved affine map");
    }
    const auto& a = matrix.value;
    Matrix3d result{};
    result.value[0][0] = a[1][1] * a[2][2] - a[1][2] * a[2][1];
    result.value[0][1] = a[0][2] * a[2][1] - a[0][1] * a[2][2];
    result.value[0][2] = a[0][1] * a[1][2] - a[0][2] * a[1][1];
    result.value[1][0] = a[1][2] * a[2][0] - a[1][0] * a[2][2];
    result.value[1][1] = a[0][0] * a[2][2] - a[0][2] * a[2][0];
    result.value[1][2] = a[0][2] * a[1][0] - a[0][0] * a[1][2];
    result.value[2][0] = a[1][0] * a[2][1] - a[1][1] * a[2][0];
    result.value[2][1] = a[0][1] * a[2][0] - a[0][0] * a[2][1];
    result.value[2][2] = a[0][0] * a[1][1] - a[0][1] * a[1][0];
    result = (1.0 / det) * result;
    if (!finite(result)) {
        throw std::overflow_error("affine inverse overflow");
    }
    return result;
}

[[nodiscard]] Matrix3d add_scaled_outer(
    Matrix3d matrix, double scale, Vec3d lhs, Vec3d rhs) noexcept {
    const std::array<double, 3> left{lhs.x, lhs.y, lhs.z};
    const std::array<double, 3> right{rhs.x, rhs.y, rhs.z};
    for (std::size_t row = 0; row < 3; ++row) {
        for (std::size_t column = 0; column < 3; ++column) {
            matrix.value[row][column] += scale * left[row] * right[column];
        }
    }
    return matrix;
}

void validate_timestep(double timestep_s, bool allow_zero = false) {
    if (!std::isfinite(timestep_s) || (allow_zero ? timestep_s < 0.0 : timestep_s <= 0.0)) {
        throw std::invalid_argument("diagnostic timestep must be finite and positive");
    }
}

[[nodiscard]] double mass_kg(
    const MovingApicParticle& particle, const TransferConfig& config) {
    if (particle.mass_quanta <= 0) {
        throw std::invalid_argument("moving APIC particle mass must be positive");
    }
    const auto mass = static_cast<double>(particle.mass_quanta) * config.kg_per_mass_quantum;
    if (!(mass > 0.0) || !std::isfinite(mass)) {
        throw std::overflow_error("moving APIC particle mass conversion overflow");
    }
    return mass;
}

void validate_moving_particles(std::span<const MovingApicParticle> particles) {
    std::vector<std::uint64_t> ids;
    ids.reserve(particles.size());
    for (const auto& particle : particles) {
        if (particle.mass_quanta <= 0 || !finite(particle.position_m) ||
            !finite(particle.velocity_m_per_s) || !finite(particle.B_m2_per_s)) {
            throw std::invalid_argument("invalid moving APIC particle state");
        }
        ids.push_back(particle.id);
    }
    std::ranges::sort(ids);
    if (std::adjacent_find(ids.begin(), ids.end()) != ids.end()) {
        throw std::invalid_argument("moving APIC particle IDs must be unique");
    }
}

[[nodiscard]] std::vector<const MovingApicParticle*> canonical_particles(
    std::span<const MovingApicParticle> particles) {
    std::vector<const MovingApicParticle*> result;
    result.reserve(particles.size());
    for (const auto& particle : particles) {
        result.push_back(&particle);
    }
    std::ranges::sort(result, {}, [](const MovingApicParticle* particle) {
        return particle->id;
    });
    return result;
}

[[nodiscard]] TransferTotals moving_grid_totals(
    const std::map<GridIndex, MovingApicGridNode>& grid, bool conceptual_new_positions) {
    TransferTotals totals{};
    for (const auto& [index, node] : grid) {
        static_cast<void>(index);
        totals.mass_kg += node.mass_kg;
        totals.linear_momentum_kg_m_per_s += node.momentum_kg_m_per_s;
        const auto position = conceptual_new_positions ? node.conceptual_new_position_m
                                                      : node.old_position_m;
        totals.center_orbital_kg_m2_per_s += cross(position, node.momentum_kg_m_per_s);
        totals.center_kinetic_j += 0.5 * node.mass_kg *
            dot(node.new_velocity_m_per_s, node.new_velocity_m_per_s);
    }
    totals.augmented_angular_kg_m2_per_s = totals.center_orbital_kg_m2_per_s;
    totals.augmented_kinetic_j = totals.center_kinetic_j;
    return totals;
}

} // namespace

std::string_view path_name(Path path) noexcept {
    switch (path) {
    case Path::analytic_ballistic:
        return "A_analytic_ballistic";
    case Path::frozen_static_apic:
        return "B_frozen_static_APIC";
    case Path::sealed_static_apic_ballistic:
        return "C_sealed_static_APIC_ballistic";
    case Path::analytic_convected_affine_control:
        return "D_analytic_convected_affine_control";
    case Path::jst2017_moving_apic:
        return "E_JST2017_moving_APIC";
    }
    return "unknown";
}

Vec3d velocity_at(const AffineField& field, Vec3d position_m) noexcept {
    return multiply(field.gradient_per_s, position_m) + field.offset_m_per_s;
}

AffineField convected_affine_field(const AffineField& field, double timestep_s) {
    validate_timestep(timestep_s);
    if (!finite(field.gradient_per_s) || !finite(field.offset_m_per_s)) {
        throw std::invalid_argument("affine field must be finite");
    }
    const auto map = Matrix3d::identity() + timestep_s * field.gradient_per_s;
    const auto inverse_map = inverse(map);
    return {
        multiply(field.gradient_per_s, inverse_map),
        multiply(inverse_map, field.offset_m_per_s),
    };
}

Vec3d stale_gradient_position_defect(
    const AffineField& field, Vec3d initial_position_m, double half_step_s) noexcept {
    const auto acceleration_like = multiply(
        field.gradient_per_s, velocity_at(field, initial_position_m));
    return (half_step_s * half_step_s) * acceleration_like;
}

Vec3d stale_gradient_velocity_defect(
    const AffineField& field, Vec3d initial_position_m, double half_step_s) noexcept {
    return half_step_s * multiply(
        field.gradient_per_s, velocity_at(field, initial_position_m));
}

std::vector<TransferParticle> ballistic_step(
    std::span<const TransferParticle> particles, double timestep_s) {
    validate_timestep(timestep_s);
    std::vector<TransferParticle> result(particles.begin(), particles.end());
    for (auto& particle : result) {
        if (!finite(particle.position_m) || !finite(particle.velocity_m_per_s)) {
            throw std::invalid_argument("ballistic particle state must be finite");
        }
        particle.position_m += timestep_s * particle.velocity_m_per_s;
        if (!finite(particle.position_m)) {
            throw std::overflow_error("ballistic particle position overflow");
        }
    }
    return result;
}

std::vector<TransferParticle> sealed_static_apic_ballistic_step(
    std::span<const TransferParticle> particles,
    const TransferConfig& config,
    double timestep_s) {
    const auto cycle = transfer_cycle(particles, config, TransferCandidate::apic);
    return ballistic_step(cycle.particles, timestep_s);
}

ConvectedControlStep analytic_convected_control_step(
    std::span<const TransferParticle> particles,
    const TransferConfig& config,
    const AffineField& field,
    double timestep_s) {
    auto result_particles = sealed_static_apic_ballistic_step(particles, config, timestep_s);
    const auto result_field = convected_affine_field(field, timestep_s);
    for (auto& particle : result_particles) {
        particle.affine_velocity_per_s = result_field.gradient_per_s;
    }
    return {std::move(result_particles), result_field};
}

Matrix3d particle_moment_matrix(
    Vec3d particle_position_m, const TransferConfig& config) {
    Matrix3d result{};
    for (const auto& sample : quadratic_bspline_samples(particle_position_m, config)) {
        result = add_scaled_outer(
            result,
            sample.weight,
            sample.node_offset_from_particle_m,
            sample.node_offset_from_particle_m);
    }
    if (!finite(result)) {
        throw std::overflow_error("moving APIC moment matrix overflow");
    }
    return result;
}

MovingApicParticle initialize_moving_apic_particle(
    const TransferParticle& particle, const TransferConfig& config) {
    return {
        particle.id,
        particle.mass_quanta,
        particle.position_m,
        particle.velocity_m_per_s,
        multiply(
            particle.affine_velocity_per_s,
            particle_moment_matrix(particle.position_m, config)),
    };
}

Matrix3d moving_apic_affine_matrix(
    const MovingApicParticle& particle, const TransferConfig& config) {
    return multiply(
        particle.B_m2_per_s,
        inverse(particle_moment_matrix(particle.position_m, config)));
}

TransferParticle as_transfer_particle(
    const MovingApicParticle& particle, const TransferConfig& config) {
    return {
        particle.id,
        particle.mass_quanta,
        particle.position_m,
        particle.velocity_m_per_s,
        moving_apic_affine_matrix(particle, config),
    };
}

std::vector<TransferParticle> as_transfer_particles(
    std::span<const MovingApicParticle> particles, const TransferConfig& config) {
    validate_moving_particles(particles);
    std::vector<TransferParticle> result;
    result.reserve(particles.size());
    for (const auto* particle : canonical_particles(particles)) {
        result.push_back(as_transfer_particle(*particle, config));
    }
    return result;
}

MovingApicStep jst2017_moving_apic_no_force_step(
    std::span<const MovingApicParticle> particles,
    const TransferConfig& config,
    double timestep_s) {
    validate_timestep(timestep_s, true);
    validate_moving_particles(particles);
    MovingApicStep result{};
    const auto before_transfer_particles = as_transfer_particles(particles, config);
    result.exact_mass_quanta_before = exact_particle_mass_quanta(before_transfer_particles);
    result.particle_before = particle_totals(before_transfer_particles, config);

    // JST 2017 Eqs. (24)--(26): old-position weights, explicit D_p and B_p D_p^-1.
    for (const auto* particle : canonical_particles(particles)) {
        const auto particle_mass = mass_kg(*particle, config);
        const auto affine = moving_apic_affine_matrix(*particle, config);
        for (const auto& sample : quadratic_bspline_samples(particle->position_m, config)) {
            if (sample.weight == 0.0) {
                continue;
            }
            auto& node = result.grid[sample.index];
            node.old_position_m = sample.node_position_m;
            const auto weighted_mass = sample.weight * particle_mass;
            node.mass_kg += weighted_mass;
            node.momentum_kg_m_per_s += weighted_mass *
                (particle->velocity_m_per_s +
                 multiply(affine, sample.node_offset_from_particle_m));
        }
    }
    for (auto& [index, node] : result.grid) {
        static_cast<void>(index);
        if (!(node.mass_kg > 0.0) || !std::isfinite(node.mass_kg)) {
            throw std::runtime_error("invalid moving APIC grid mass");
        }
        node.old_velocity_m_per_s = node.momentum_kg_m_per_s / node.mass_kg;
        // Eq. (29), f=0: no-force grid velocity is unchanged.
        node.new_velocity_m_per_s = node.old_velocity_m_per_s;
        // Eq. (30), f=0: lambda cancels because old and new velocities agree.
        node.conceptual_new_position_m =
            node.old_position_m + timestep_s * node.new_velocity_m_per_s;
    }
    result.grid_after_p2g = moving_grid_totals(result.grid, false);
    result.grid_after_no_force_evolution = moving_grid_totals(result.grid, true);

    // JST 2017 Eqs. (37)--(39). All interpolation weights remain w_ip^n.
    result.particles.reserve(particles.size());
    for (const auto* before : canonical_particles(particles)) {
        MovingApicParticle after = *before;
        Vec3d new_velocity{};
        Vec3d new_position{};
        const auto samples = quadratic_bspline_samples(before->position_m, config);
        for (const auto& sample : samples) {
            if (sample.weight == 0.0) {
                continue;
            }
            const auto found = result.grid.find(sample.index);
            if (found == result.grid.end()) {
                throw std::runtime_error("moving APIC grid is missing an old-weight node");
            }
            new_velocity += sample.weight * found->second.new_velocity_m_per_s;
            new_position += sample.weight * found->second.conceptual_new_position_m;
        }
        after.velocity_m_per_s = new_velocity;
        after.position_m = new_position;
        Matrix3d new_B{};
        for (const auto& sample : samples) {
            if (sample.weight == 0.0) {
                continue;
            }
            const auto& node = result.grid.at(sample.index);
            const auto old_offset = sample.node_offset_from_particle_m;
            const auto new_offset = node.conceptual_new_position_m - after.position_m;
            new_B = add_scaled_outer(
                new_B,
                0.5 * sample.weight,
                node.new_velocity_m_per_s,
                old_offset + new_offset);
            new_B = add_scaled_outer(
                new_B,
                0.5 * sample.weight,
                old_offset - new_offset,
                node.new_velocity_m_per_s);
        }
        if (!finite(after.position_m) || !finite(after.velocity_m_per_s) || !finite(new_B)) {
            throw std::runtime_error("non-finite moving APIC G2P state");
        }
        after.B_m2_per_s = new_B;
        result.particles.push_back(after);
    }

    const auto after_transfer_particles = as_transfer_particles(result.particles, config);
    result.exact_mass_quanta_after = exact_particle_mass_quanta(after_transfer_particles);
    result.particle_after = particle_totals(after_transfer_particles, config);
    result.p2g_center_energy_residual_j =
        result.grid_after_p2g.center_kinetic_j - result.particle_before.center_kinetic_j;
    result.step_center_energy_residual_j =
        result.particle_after.center_kinetic_j - result.particle_before.center_kinetic_j;
    result.p2g_augmented_representation_energy_residual_j =
        result.grid_after_p2g.center_kinetic_j - result.particle_before.augmented_kinetic_j;
    result.step_augmented_representation_energy_residual_j =
        result.particle_after.augmented_kinetic_j -
        result.particle_before.augmented_kinetic_j;
    return result;
}

} // namespace mls::experimental::affine_advection
