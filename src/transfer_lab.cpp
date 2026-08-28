#include "mls/transfer_lab.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <tuple>

namespace mls::experimental {
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

void validate_config(const TransferConfig& config) {
    if (!(config.grid_spacing_m > 0.0) || !std::isfinite(config.grid_spacing_m)) {
        throw std::invalid_argument("transfer grid spacing must be finite and positive");
    }
    if (!(config.kg_per_mass_quantum > 0.0) ||
        !std::isfinite(config.kg_per_mass_quantum)) {
        throw std::invalid_argument("mass quantum scale must be finite and positive");
    }
    if (!finite(config.grid_origin_m)) {
        throw std::invalid_argument("transfer grid origin must be finite");
    }
}

void validate_particles(std::span<const TransferParticle> particles) {
    std::vector<std::uint64_t> ids;
    ids.reserve(particles.size());
    for (const auto& particle : particles) {
        if (particle.mass_quanta <= 0) {
            throw std::invalid_argument("transfer particle mass must be positive");
        }
        if (!finite(particle.position_m) || !finite(particle.velocity_m_per_s) ||
            !finite(particle.affine_velocity_per_s)) {
            throw std::invalid_argument("transfer particle state must be finite");
        }
        ids.push_back(particle.id);
    }
    std::ranges::sort(ids);
    if (std::adjacent_find(ids.begin(), ids.end()) != ids.end()) {
        throw std::invalid_argument("transfer particle IDs must be unique");
    }
}

[[nodiscard]] std::vector<const TransferParticle*> canonical_particles(
    std::span<const TransferParticle> particles) {
    std::vector<const TransferParticle*> ordered;
    ordered.reserve(particles.size());
    for (const auto& particle : particles) {
        ordered.push_back(&particle);
    }
    std::ranges::sort(ordered, {}, [](const TransferParticle* particle) {
        return particle->id;
    });
    return ordered;
}

[[nodiscard]] double mass_kg(const TransferParticle& particle, const TransferConfig& config) {
    const auto result = static_cast<double>(particle.mass_quanta) * config.kg_per_mass_quantum;
    if (!std::isfinite(result)) {
        throw std::overflow_error("transfer particle mass conversion overflow");
    }
    return result;
}

[[nodiscard]] std::array<double, 3> axis_weights(double coordinate) {
    return {
        0.5 * std::pow(1.5 - coordinate, 2.0),
        0.75 - std::pow(coordinate - 1.0, 2.0),
        0.5 * std::pow(coordinate - 0.5, 2.0),
    };
}

[[nodiscard]] std::int64_t checked_floor_to_i64(double value) {
    if (!std::isfinite(value)) {
        throw std::invalid_argument("non-finite transfer grid coordinate");
    }
    const auto floored = std::floor(value);
    constexpr auto low = static_cast<double>(std::numeric_limits<std::int64_t>::min());
    constexpr auto high = static_cast<double>(std::numeric_limits<std::int64_t>::max());
    if (!(floored >= low && floored < high)) {
        throw std::overflow_error("transfer grid index overflow");
    }
    return static_cast<std::int64_t>(floored);
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

[[nodiscard]] double determinant(const Matrix3d& matrix) noexcept {
    const auto& a = matrix.value;
    return a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) -
        a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) +
        a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]);
}

[[nodiscard]] Matrix3d inverse(const Matrix3d& matrix) {
    const auto det = determinant(matrix);
    const auto scale = std::max(1.0, std::pow(frobenius_norm(matrix), 3.0));
    if (!std::isfinite(det) || std::abs(det) <= 64.0 * std::numeric_limits<double>::epsilon() * scale) {
        throw std::domain_error("singular transfer kernel moment matrix");
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
    return (1.0 / det) * result;
}

[[nodiscard]] double represented_particle_energy(
    const TransferTotals& totals, TransferCandidate candidate) noexcept {
    return candidate == TransferCandidate::apic ? totals.augmented_kinetic_j
                                                 : totals.center_kinetic_j;
}

} // namespace

Vec3d operator+(Vec3d lhs, Vec3d rhs) noexcept {
    return {lhs.x + rhs.x, lhs.y + rhs.y, lhs.z + rhs.z};
}

Vec3d operator-(Vec3d lhs, Vec3d rhs) noexcept {
    return {lhs.x - rhs.x, lhs.y - rhs.y, lhs.z - rhs.z};
}

Vec3d operator-(Vec3d value) noexcept {
    return {-value.x, -value.y, -value.z};
}

Vec3d operator*(double scalar, Vec3d value) noexcept {
    return {scalar * value.x, scalar * value.y, scalar * value.z};
}

Vec3d operator*(Vec3d value, double scalar) noexcept {
    return scalar * value;
}

Vec3d operator/(Vec3d value, double scalar) {
    if (scalar == 0.0) {
        throw std::domain_error("Vec3d division by zero");
    }
    return (1.0 / scalar) * value;
}

Vec3d& operator+=(Vec3d& lhs, Vec3d rhs) noexcept {
    lhs = lhs + rhs;
    return lhs;
}

double dot(Vec3d lhs, Vec3d rhs) noexcept {
    return lhs.x * rhs.x + lhs.y * rhs.y + lhs.z * rhs.z;
}

Vec3d cross(Vec3d lhs, Vec3d rhs) noexcept {
    return {
        lhs.y * rhs.z - lhs.z * rhs.y,
        lhs.z * rhs.x - lhs.x * rhs.z,
        lhs.x * rhs.y - lhs.y * rhs.x,
    };
}

double norm(Vec3d value) noexcept {
    return std::sqrt(dot(value, value));
}

Vec3d multiply(const Matrix3d& matrix, Vec3d vector) noexcept {
    return {
        matrix.value[0][0] * vector.x + matrix.value[0][1] * vector.y +
            matrix.value[0][2] * vector.z,
        matrix.value[1][0] * vector.x + matrix.value[1][1] * vector.y +
            matrix.value[1][2] * vector.z,
        matrix.value[2][0] * vector.x + matrix.value[2][1] * vector.y +
            matrix.value[2][2] * vector.z,
    };
}

Matrix3d multiply(const Matrix3d& lhs, const Matrix3d& rhs) noexcept {
    Matrix3d result{};
    for (std::size_t row = 0; row < 3; ++row) {
        for (std::size_t column = 0; column < 3; ++column) {
            for (std::size_t inner = 0; inner < 3; ++inner) {
                result.value[row][column] +=
                    lhs.value[row][inner] * rhs.value[inner][column];
            }
        }
    }
    return result;
}

Matrix3d transpose(const Matrix3d& matrix) noexcept {
    Matrix3d result{};
    for (std::size_t row = 0; row < 3; ++row) {
        for (std::size_t column = 0; column < 3; ++column) {
            result.value[row][column] = matrix.value[column][row];
        }
    }
    return result;
}

Matrix3d outer(Vec3d lhs, Vec3d rhs) noexcept {
    return add_scaled_outer({}, 1.0, lhs, rhs);
}

Matrix3d operator+(const Matrix3d& lhs, const Matrix3d& rhs) noexcept {
    Matrix3d result{};
    for (std::size_t row = 0; row < 3; ++row) {
        for (std::size_t column = 0; column < 3; ++column) {
            result.value[row][column] = lhs.value[row][column] + rhs.value[row][column];
        }
    }
    return result;
}

Matrix3d operator*(double scalar, const Matrix3d& matrix) noexcept {
    Matrix3d result{};
    for (std::size_t row = 0; row < 3; ++row) {
        for (std::size_t column = 0; column < 3; ++column) {
            result.value[row][column] = scalar * matrix.value[row][column];
        }
    }
    return result;
}

double frobenius_norm(const Matrix3d& matrix) noexcept {
    double squared = 0.0;
    for (const auto& row : matrix.value) {
        for (const auto entry : row) {
            squared += entry * entry;
        }
    }
    return std::sqrt(squared);
}

std::string_view candidate_name(TransferCandidate candidate) noexcept {
    switch (candidate) {
    case TransferCandidate::pic:
        return "PIC";
    case TransferCandidate::apic:
        return "APIC";
    case TransferCandidate::flip_diagnostic:
        return "FLIP diagnostic";
    }
    return "unknown";
}

std::vector<KernelSample> quadratic_bspline_samples(
    Vec3d particle_position_m, const TransferConfig& config) {
    validate_config(config);
    if (!finite(particle_position_m)) {
        throw std::invalid_argument("particle position must be finite");
    }
    const auto normalized = (particle_position_m - config.grid_origin_m) /
        config.grid_spacing_m;
    const GridIndex base{
        checked_floor_to_i64(normalized.x - 0.5),
        checked_floor_to_i64(normalized.y - 0.5),
        checked_floor_to_i64(normalized.z - 0.5),
    };
    constexpr auto maximum_base = std::numeric_limits<std::int64_t>::max() - 2;
    if (base.x > maximum_base || base.y > maximum_base || base.z > maximum_base) {
        throw std::overflow_error("transfer kernel stencil index overflow");
    }
    const Vec3d fractional{
        normalized.x - static_cast<double>(base.x),
        normalized.y - static_cast<double>(base.y),
        normalized.z - static_cast<double>(base.z),
    };
    const auto wx = axis_weights(fractional.x);
    const auto wy = axis_weights(fractional.y);
    const auto wz = axis_weights(fractional.z);

    std::vector<KernelSample> result;
    result.reserve(27);
    for (std::int64_t ix = 0; ix < 3; ++ix) {
        for (std::int64_t iy = 0; iy < 3; ++iy) {
            for (std::int64_t iz = 0; iz < 3; ++iz) {
                const GridIndex index{base.x + ix, base.y + iy, base.z + iz};
                const Vec3d node_position{
                    config.grid_origin_m.x +
                        static_cast<double>(index.x) * config.grid_spacing_m,
                    config.grid_origin_m.y +
                        static_cast<double>(index.y) * config.grid_spacing_m,
                    config.grid_origin_m.z +
                        static_cast<double>(index.z) * config.grid_spacing_m,
                };
                if (!finite(node_position)) {
                    throw std::overflow_error("transfer kernel node position overflow");
                }
                result.push_back(KernelSample{
                    index,
                    node_position,
                    node_position - particle_position_m,
                    wx[static_cast<std::size_t>(ix)] * wy[static_cast<std::size_t>(iy)] *
                        wz[static_cast<std::size_t>(iz)],
                });
            }
        }
    }
    return result;
}

TransferGrid particle_to_grid(
    std::span<const TransferParticle> particles,
    const TransferConfig& config,
    TransferCandidate candidate) {
    validate_config(config);
    validate_particles(particles);
    TransferGrid grid{config, {}};
    for (const auto* particle : canonical_particles(particles)) {
        const auto particle_mass_kg = mass_kg(*particle, config);
        for (const auto& sample : quadratic_bspline_samples(particle->position_m, config)) {
            if (sample.weight == 0.0) {
                continue;
            }
            auto& node = grid.nodes[sample.index];
            const auto weighted_mass = sample.weight * particle_mass_kg;
            const auto represented_velocity = candidate == TransferCandidate::apic
                ? particle->velocity_m_per_s +
                    multiply(particle->affine_velocity_per_s,
                             sample.node_offset_from_particle_m)
                : particle->velocity_m_per_s;
            node.mass_kg += weighted_mass;
            node.momentum_kg_m_per_s += weighted_mass * represented_velocity;
        }
    }
    for (auto& [index, node] : grid.nodes) {
        static_cast<void>(index);
        if (!(node.mass_kg > 0.0) || !std::isfinite(node.mass_kg)) {
            throw std::runtime_error("invalid non-positive transfer grid mass");
        }
        node.velocity_m_per_s = node.momentum_kg_m_per_s / node.mass_kg;
        node.velocity_before_update_m_per_s = node.velocity_m_per_s;
    }
    return grid;
}

std::vector<TransferParticle> grid_to_particles(
    std::span<const TransferParticle> particles_before,
    const TransferGrid& grid,
    TransferCandidate candidate) {
    validate_config(grid.config);
    validate_particles(particles_before);
    std::vector<TransferParticle> result;
    result.reserve(particles_before.size());
    for (const auto* before : canonical_particles(particles_before)) {
        auto after = *before;
        Vec3d interpolated{};
        Vec3d flip_delta{};
        Matrix3d velocity_offset_moment{};
        Matrix3d position_moment{};
        for (const auto& sample : quadratic_bspline_samples(before->position_m, grid.config)) {
            if (sample.weight == 0.0) {
                continue;
            }
            const auto found = grid.nodes.find(sample.index);
            if (found == grid.nodes.end()) {
                throw std::runtime_error("transfer grid is missing a kernel node");
            }
            const auto& node = found->second;
            interpolated += sample.weight * node.velocity_m_per_s;
            flip_delta += sample.weight *
                (node.velocity_m_per_s - node.velocity_before_update_m_per_s);
            velocity_offset_moment = add_scaled_outer(
                velocity_offset_moment,
                sample.weight,
                node.velocity_m_per_s,
                sample.node_offset_from_particle_m);
            position_moment = add_scaled_outer(
                position_moment,
                sample.weight,
                sample.node_offset_from_particle_m,
                sample.node_offset_from_particle_m);
        }

        switch (candidate) {
        case TransferCandidate::pic:
            after.velocity_m_per_s = interpolated;
            after.affine_velocity_per_s = Matrix3d::zero();
            break;
        case TransferCandidate::apic:
            after.velocity_m_per_s = interpolated;
            after.affine_velocity_per_s =
                multiply(velocity_offset_moment, inverse(position_moment));
            break;
        case TransferCandidate::flip_diagnostic:
            after.velocity_m_per_s = before->velocity_m_per_s + flip_delta;
            after.affine_velocity_per_s = Matrix3d::zero();
            break;
        }
        if (!finite(after.velocity_m_per_s) || !finite(after.affine_velocity_per_s)) {
            throw std::runtime_error("non-finite grid-to-particle result");
        }
        result.push_back(after);
    }
    return result;
}

void add_diagnostic_grid_velocity_delta(TransferGrid& grid, Vec3d delta_m_per_s) {
    if (!finite(delta_m_per_s)) {
        throw std::invalid_argument("diagnostic grid delta must be finite");
    }
    for (auto& [index, node] : grid.nodes) {
        static_cast<void>(index);
        node.velocity_m_per_s += delta_m_per_s;
        node.momentum_kg_m_per_s = node.mass_kg * node.velocity_m_per_s;
    }
}

TransferTotals particle_totals(
    std::span<const TransferParticle> particles, const TransferConfig& config) {
    validate_config(config);
    validate_particles(particles);
    TransferTotals totals{};
    for (const auto* particle : canonical_particles(particles)) {
        const auto particle_mass_kg = mass_kg(*particle, config);
        const auto momentum = particle_mass_kg * particle->velocity_m_per_s;
        totals.mass_kg += particle_mass_kg;
        totals.linear_momentum_kg_m_per_s += momentum;
        totals.center_orbital_kg_m2_per_s += cross(particle->position_m, momentum);
        totals.center_kinetic_j +=
            0.5 * particle_mass_kg * dot(particle->velocity_m_per_s,
                                         particle->velocity_m_per_s);
        for (const auto& sample : quadratic_bspline_samples(particle->position_m, config)) {
            const auto affine_velocity = multiply(
                particle->affine_velocity_per_s, sample.node_offset_from_particle_m);
            totals.affine_auxiliary_kg_m2_per_s += particle_mass_kg * sample.weight *
                cross(sample.node_offset_from_particle_m, affine_velocity);
            totals.affine_auxiliary_kinetic_j += 0.5 * particle_mass_kg * sample.weight *
                dot(affine_velocity, affine_velocity);
        }
    }
    totals.augmented_angular_kg_m2_per_s =
        totals.center_orbital_kg_m2_per_s + totals.affine_auxiliary_kg_m2_per_s;
    totals.augmented_kinetic_j =
        totals.center_kinetic_j + totals.affine_auxiliary_kinetic_j;
    return totals;
}

TransferTotals grid_totals(const TransferGrid& grid) {
    validate_config(grid.config);
    TransferTotals totals{};
    for (const auto& [index, node] : grid.nodes) {
        const Vec3d position{
            grid.config.grid_origin_m.x +
                static_cast<double>(index.x) * grid.config.grid_spacing_m,
            grid.config.grid_origin_m.y +
                static_cast<double>(index.y) * grid.config.grid_spacing_m,
            grid.config.grid_origin_m.z +
                static_cast<double>(index.z) * grid.config.grid_spacing_m,
        };
        totals.mass_kg += node.mass_kg;
        totals.linear_momentum_kg_m_per_s += node.momentum_kg_m_per_s;
        totals.center_orbital_kg_m2_per_s += cross(position, node.momentum_kg_m_per_s);
        totals.center_kinetic_j +=
            0.5 * node.mass_kg * dot(node.velocity_m_per_s, node.velocity_m_per_s);
    }
    totals.augmented_angular_kg_m2_per_s = totals.center_orbital_kg_m2_per_s;
    totals.augmented_kinetic_j = totals.center_kinetic_j;
    return totals;
}

std::int64_t exact_particle_mass_quanta(std::span<const TransferParticle> particles) {
    validate_particles(particles);
    std::int64_t total = 0;
    for (const auto* particle : canonical_particles(particles)) {
        if (particle->mass_quanta > std::numeric_limits<std::int64_t>::max() - total) {
            throw std::overflow_error("exact transfer particle mass overflow");
        }
        total += particle->mass_quanta;
    }
    return total;
}

TransferCycle transfer_cycle(
    std::span<const TransferParticle> particles,
    const TransferConfig& config,
    TransferCandidate candidate) {
    TransferCycle result{};
    result.particle_before = particle_totals(particles, config);
    result.exact_mass_quanta_before = exact_particle_mass_quanta(particles);
    result.grid = particle_to_grid(particles, config, candidate);
    result.grid_after_p2g = grid_totals(result.grid);
    result.particles = grid_to_particles(particles, result.grid, candidate);
    result.particle_after = particle_totals(result.particles, config);
    result.exact_mass_quanta_after = exact_particle_mass_quanta(result.particles);
    const auto before_energy = represented_particle_energy(result.particle_before, candidate);
    const auto after_energy = represented_particle_energy(result.particle_after, candidate);
    result.p2g_numerical_energy_residual_j =
        result.grid_after_p2g.center_kinetic_j - before_energy;
    result.roundtrip_numerical_energy_residual_j = after_energy - before_energy;
    return result;
}

} // namespace mls::experimental
