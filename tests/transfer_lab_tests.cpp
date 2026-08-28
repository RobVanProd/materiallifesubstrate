#include "test_harness.hpp"

#include "mls/transfer_lab.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>

namespace {

using mls::experimental::Matrix3d;
using mls::experimental::TransferCandidate;
using mls::experimental::TransferConfig;
using mls::experimental::TransferParticle;
using mls::experimental::Vec3d;

[[nodiscard]] bool close(double actual, double expected, double tolerance = 1.0e-12) {
    return std::abs(actual - expected) <=
        tolerance * std::max({1.0, std::abs(actual), std::abs(expected)});
}

[[nodiscard]] bool close(Vec3d actual, Vec3d expected, double tolerance = 1.0e-12) {
    return close(actual.x, expected.x, tolerance) &&
        close(actual.y, expected.y, tolerance) && close(actual.z, expected.z, tolerance);
}

[[nodiscard]] bool close(
    const Matrix3d& actual, const Matrix3d& expected, double tolerance = 1.0e-12) {
    for (std::size_t row = 0; row < 3; ++row) {
        for (std::size_t column = 0; column < 3; ++column) {
            if (!close(actual.value[row][column], expected.value[row][column], tolerance)) {
                return false;
            }
        }
    }
    return true;
}

[[nodiscard]] Matrix3d affine_matrix() {
    Matrix3d matrix{};
    matrix.value = {{{0.20, -0.70, 0.30},
                     {0.55, -0.10, 0.25},
                     {-0.35, 0.40, 0.15}}};
    return matrix;
}

[[nodiscard]] std::vector<TransferParticle> affine_particles() {
    const auto affine = affine_matrix();
    const Vec3d translation{0.9, -0.4, 0.7};
    std::vector<TransferParticle> particles;
    std::uint64_t id = 1;
    for (const auto x : {-0.31, 0.47}) {
        for (const auto y : {-0.19, 0.53}) {
            for (const auto z : {-0.41, 0.29}) {
                const Vec3d position{x, y, z};
                particles.push_back(TransferParticle{
                    id++,
                    static_cast<std::int64_t>(id % 3 + 1),
                    position,
                    mls::experimental::multiply(affine, position) + translation,
                    affine,
                });
            }
        }
    }
    return particles;
}

} // namespace

MLS_TEST("transfer kernel has partition unity first moment and fixed second moment") {
    for (const auto phase : std::array{
             Vec3d{0.0, 0.0, 0.0},
             Vec3d{0.13, 0.37, 0.71},
             Vec3d{0.49, 0.01, 0.83},
             Vec3d{0.91, 0.59, 0.23}}) {
        const TransferConfig config{0.5, phase * 0.5, 0.25};
        const Vec3d position{0.317, -0.289, 0.611};
        const auto samples = mls::experimental::quadratic_bspline_samples(position, config);
        MLS_REQUIRE_EQ(samples.size(), std::size_t{27});
        double weight_sum = 0.0;
        Vec3d first_moment{};
        Matrix3d second_moment{};
        for (const auto& sample : samples) {
            MLS_REQUIRE(sample.weight >= 0.0);
            weight_sum += sample.weight;
            first_moment += sample.weight * sample.node_offset_from_particle_m;
            second_moment = second_moment + sample.weight *
                mls::experimental::outer(
                    sample.node_offset_from_particle_m,
                    sample.node_offset_from_particle_m);
        }
        MLS_REQUIRE(close(weight_sum, 1.0));
        MLS_REQUIRE(close(first_moment, {}));
        const auto expected = 0.25 * config.grid_spacing_m * config.grid_spacing_m *
            Matrix3d::identity();
        MLS_REQUIRE(close(second_moment, expected));
    }
}

MLS_TEST("transfer rejects invalid state duplicate IDs and exact mass overflow") {
    const TransferParticle valid{1, 1, {}, {}, {}};
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        mls::experimental::particle_to_grid(
            std::array{valid}, TransferConfig{0.0, {}, 1.0}, TransferCandidate::pic));
    auto zero_mass = valid;
    zero_mass.mass_quanta = 0;
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        mls::experimental::particle_to_grid(
            std::array{zero_mass}, TransferConfig{}, TransferCandidate::pic));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        mls::experimental::particle_to_grid(
            std::array{valid, valid}, TransferConfig{}, TransferCandidate::pic));
    auto huge_position = valid;
    huge_position.position_m = {
        static_cast<double>(std::numeric_limits<std::int64_t>::max()), 0.0, 0.0};
    MLS_REQUIRE_THROWS(
        std::overflow_error,
        mls::experimental::quadratic_bspline_samples(huge_position.position_m, {}));
    const std::array overflowing_mass{
        TransferParticle{1, std::numeric_limits<std::int64_t>::max(), {}, {}, {}},
        TransferParticle{2, 1, {}, {}, {}},
    };
    MLS_REQUIRE_THROWS(
        std::overflow_error,
        mls::experimental::exact_particle_mass_quanta(overflowing_mass));
}

MLS_TEST("zero kernel weights do not create zero-mass grid nodes") {
    const std::array particle{
        TransferParticle{1, 1, {0.5, 0.5, 0.5}, {1.0, 2.0, 3.0}, {}},
    };
    const auto grid = mls::experimental::particle_to_grid(
        particle, TransferConfig{}, TransferCandidate::pic);
    MLS_REQUIRE_EQ(grid.nodes.size(), std::size_t{8});
    for (const auto& [index, node] : grid.nodes) {
        static_cast<void>(index);
        MLS_REQUIRE(node.mass_kg > 0.0);
    }
}

MLS_TEST("PIC and APIC reproduce constant translation and exact particle mass") {
    auto particles = affine_particles();
    const Vec3d velocity{1.25, -0.75, 0.5};
    for (auto& particle : particles) {
        particle.velocity_m_per_s = velocity;
        particle.affine_velocity_per_s = Matrix3d::zero();
    }
    const TransferConfig config{0.5, {0.07, 0.11, 0.19}, 0.125};
    for (const auto candidate : {TransferCandidate::pic, TransferCandidate::apic}) {
        const auto cycle = mls::experimental::transfer_cycle(particles, config, candidate);
        MLS_REQUIRE_EQ(cycle.exact_mass_quanta_before, cycle.exact_mass_quanta_after);
        MLS_REQUIRE(close(cycle.particle_before.mass_kg, cycle.grid_after_p2g.mass_kg));
        MLS_REQUIRE(close(
            cycle.particle_before.linear_momentum_kg_m_per_s,
            cycle.grid_after_p2g.linear_momentum_kg_m_per_s));
        for (const auto& particle : cycle.particles) {
            MLS_REQUIRE(close(particle.velocity_m_per_s, velocity));
        }
        MLS_REQUIRE(close(cycle.roundtrip_numerical_energy_residual_j, 0.0));
    }
}

MLS_TEST("APIC exactly reconstructs affine fields on a frozen complete stencil") {
    const auto particles = affine_particles();
    const TransferConfig config{0.5, {0.065, 0.185, 0.355}, 0.25};
    const auto cycle =
        mls::experimental::transfer_cycle(particles, config, TransferCandidate::apic);
    MLS_REQUIRE(close(
        cycle.particle_before.linear_momentum_kg_m_per_s,
        cycle.grid_after_p2g.linear_momentum_kg_m_per_s,
        2.0e-12));
    MLS_REQUIRE(close(
        cycle.particle_before.augmented_angular_kg_m2_per_s,
        cycle.grid_after_p2g.center_orbital_kg_m2_per_s,
        2.0e-11));
    MLS_REQUIRE(close(cycle.p2g_numerical_energy_residual_j, 0.0, 2.0e-11));
    for (std::size_t index = 0; index < particles.size(); ++index) {
        MLS_REQUIRE(close(
            cycle.particles[index].velocity_m_per_s,
            particles[index].velocity_m_per_s,
            5.0e-11));
        MLS_REQUIRE(close(
            cycle.particles[index].affine_velocity_per_s,
            particles[index].affine_velocity_per_s,
            5.0e-11));
    }
}

MLS_TEST("APIC affine auxiliary stays separate from point orbital accounting") {
    Matrix3d rotation{};
    rotation.value = {{{0.0, -2.0, 0.0}, {2.0, 0.0, 0.0}, {0.0, 0.0, 0.0}}};
    const std::array particle{
        TransferParticle{1, 3, {0.25, -0.125, 0.5}, {0.25, 0.5, 0.0}, rotation},
    };
    const TransferConfig config{1.0, {0.17, 0.31, 0.43}, 1.0};
    const auto cycle =
        mls::experimental::transfer_cycle(particle, config, TransferCandidate::apic);
    MLS_REQUIRE(!close(cycle.particle_before.affine_auxiliary_kg_m2_per_s, {}));
    MLS_REQUIRE(!close(
        cycle.particle_before.center_orbital_kg_m2_per_s,
        cycle.grid_after_p2g.center_orbital_kg_m2_per_s));
    MLS_REQUIRE(close(
        cycle.particle_before.augmented_angular_kg_m2_per_s,
        cycle.grid_after_p2g.center_orbital_kg_m2_per_s,
        2.0e-11));
}

MLS_TEST("PIC exposes repeated affine damping as a numerical residual") {
    auto particles = affine_particles();
    const TransferConfig config{0.5, {0.065, 0.185, 0.355}, 0.25};
    const auto initial = mls::experimental::particle_totals(particles, config);
    for (int cycle_index = 0; cycle_index < 4; ++cycle_index) {
        particles = mls::experimental::transfer_cycle(
                        particles, config, TransferCandidate::pic)
                        .particles;
    }
    const auto after = mls::experimental::particle_totals(particles, config);
    MLS_REQUIRE(after.center_kinetic_j < initial.center_kinetic_j);
    MLS_REQUIRE(!close(after.center_kinetic_j, initial.center_kinetic_j, 1.0e-10));
}

MLS_TEST("FLIP comparator is identity without update and follows explicit grid delta") {
    const auto particles = affine_particles();
    const TransferConfig config{0.5, {0.065, 0.185, 0.355}, 0.25};
    auto grid = mls::experimental::particle_to_grid(
        particles, config, TransferCandidate::flip_diagnostic);
    const auto identity = mls::experimental::grid_to_particles(
        particles, grid, TransferCandidate::flip_diagnostic);
    for (std::size_t index = 0; index < particles.size(); ++index) {
        MLS_REQUIRE_EQ(identity[index].velocity_m_per_s, particles[index].velocity_m_per_s);
    }
    const Vec3d diagnostic_delta{0.125, -0.25, 0.5};
    mls::experimental::add_diagnostic_grid_velocity_delta(grid, diagnostic_delta);
    const auto changed = mls::experimental::grid_to_particles(
        particles, grid, TransferCandidate::flip_diagnostic);
    for (std::size_t index = 0; index < particles.size(); ++index) {
        MLS_REQUIRE(close(
            changed[index].velocity_m_per_s,
            particles[index].velocity_m_per_s + diagnostic_delta));
    }
}

MLS_TEST("transfer reduction and output order are canonical by particle ID") {
    auto forward = affine_particles();
    auto reverse = forward;
    std::ranges::reverse(reverse);
    const TransferConfig config{0.5, {0.065, 0.185, 0.355}, 0.25};
    const auto first =
        mls::experimental::transfer_cycle(forward, config, TransferCandidate::apic);
    const auto second =
        mls::experimental::transfer_cycle(reverse, config, TransferCandidate::apic);
    MLS_REQUIRE_EQ(first.grid.nodes, second.grid.nodes);
    MLS_REQUIRE_EQ(first.particles, second.particles);
    MLS_REQUIRE(std::ranges::is_sorted(first.particles, {}, &TransferParticle::id));
}
