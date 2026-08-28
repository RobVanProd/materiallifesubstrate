#include "test_harness.hpp"

#include "mls/affine_advection_lab.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace {

using mls::experimental::Matrix3d;
using mls::experimental::TransferConfig;
using mls::experimental::TransferParticle;
using mls::experimental::Vec3d;
using mls::experimental::affine_advection::AffineField;
using mls::experimental::affine_advection::MovingApicParticle;

[[nodiscard]] bool close(double actual, double expected, double tolerance = 2.0e-12) {
    return std::abs(actual - expected) <=
        tolerance * std::max({1.0, std::abs(actual), std::abs(expected)});
}

[[nodiscard]] bool close(Vec3d actual, Vec3d expected, double tolerance = 2.0e-12) {
    return close(actual.x, expected.x, tolerance) &&
        close(actual.y, expected.y, tolerance) &&
        close(actual.z, expected.z, tolerance);
}

[[nodiscard]] bool close(
    const Matrix3d& actual, const Matrix3d& expected, double tolerance = 2.0e-12) {
    for (std::size_t row = 0; row < 3; ++row) {
        for (std::size_t column = 0; column < 3; ++column) {
            if (!close(actual.value[row][column], expected.value[row][column], tolerance)) {
                return false;
            }
        }
    }
    return true;
}

[[nodiscard]] AffineField general_field() {
    AffineField field{};
    field.gradient_per_s.value = {{{0.20, -0.70, 0.30},
                                   {0.55, -0.10, 0.25},
                                   {-0.35, 0.40, 0.15}}};
    field.offset_m_per_s = {0.90, -0.40, 0.70};
    return field;
}

[[nodiscard]] AffineField rotation_field() {
    AffineField field{};
    field.gradient_per_s.value = {{{0.0, -0.55, -0.35},
                                   {0.55, 0.0, -0.45},
                                   {0.35, 0.45, 0.0}}};
    field.offset_m_per_s = {0.13, -0.07, 0.09};
    return field;
}

[[nodiscard]] std::vector<TransferParticle> particles_for(const AffineField& field) {
    const std::array<Vec3d, 9> positions{{
        {-0.51, -0.22, 0.17}, {0.44, -0.31, -0.28}, {-0.13, 0.56, -0.19},
        {0.28, 0.16, 0.49},   {-0.47, 0.33, 0.41},  {0.09, -0.54, 0.36},
        {0.53, 0.45, 0.08},   {-0.24, -0.11, -0.52}, {0.17, 0.04, -0.07},
    }};
    const std::array<std::int64_t, 9> masses{{1, 2, 3, 5, 8, 13, 17, 11, 7}};
    std::vector<TransferParticle> result;
    for (std::size_t index = 0; index < positions.size(); ++index) {
        result.push_back({
            static_cast<std::uint64_t>(index + 1U),
            masses[index],
            positions[index],
            mls::experimental::affine_advection::velocity_at(field, positions[index]),
            field.gradient_per_s,
        });
    }
    return result;
}

[[nodiscard]] double max_velocity_error(
    const std::vector<TransferParticle>& actual,
    const std::vector<TransferParticle>& reference) {
    double result = 0.0;
    for (std::size_t index = 0; index < actual.size(); ++index) {
        result = std::max(
            result,
            mls::experimental::norm(
                actual[index].velocity_m_per_s - reference[index].velocity_m_per_s));
    }
    return result;
}

} // namespace

MLS_TEST("force-free affine convection preserves every material particle velocity") {
    const auto field = general_field();
    const auto timestep = 0.075;
    const auto next =
        mls::experimental::affine_advection::convected_affine_field(field, timestep);
    for (const auto position : std::array{
             Vec3d{-0.47, 0.23, 0.61},
             Vec3d{0.0, 0.0, 0.0},
             Vec3d{0.81, -0.32, -0.19}}) {
        const auto velocity =
            mls::experimental::affine_advection::velocity_at(field, position);
        const auto advected = position + timestep * velocity;
        MLS_REQUIRE(close(
            mls::experimental::affine_advection::velocity_at(next, advected), velocity));
    }
}

MLS_TEST("convected affine half steps equal one full analytic step") {
    const auto field = general_field();
    const auto half = 0.04;
    const auto full_field =
        mls::experimental::affine_advection::convected_affine_field(field, 2.0 * half);
    const auto half_field =
        mls::experimental::affine_advection::convected_affine_field(field, half);
    const auto two_half_field =
        mls::experimental::affine_advection::convected_affine_field(half_field, half);
    MLS_REQUIRE(close(full_field.gradient_per_s, two_half_field.gradient_per_s, 5.0e-12));
    MLS_REQUIRE(close(full_field.offset_m_per_s, two_half_field.offset_m_per_s, 5.0e-12));

    const Vec3d initial{-0.27, 0.41, 0.18};
    const auto material_velocity =
        mls::experimental::affine_advection::velocity_at(field, initial);
    const auto one_full = initial + (2.0 * half) * material_velocity;
    const auto after_half = initial + half * material_velocity;
    const auto second_velocity =
        mls::experimental::affine_advection::velocity_at(half_field, after_half);
    const auto two_half = after_half + half * second_velocity;
    MLS_REQUIRE(close(one_full, two_half, 5.0e-12));
}

MLS_TEST("stale affine gradient has the predeclared exact two-half-step defect") {
    const auto field = general_field();
    const Vec3d initial{0.31, -0.27, 0.19};
    const auto half = 0.05;
    const auto initial_velocity =
        mls::experimental::affine_advection::velocity_at(field, initial);
    const auto after_half = initial + half * initial_velocity;
    const auto stale_velocity =
        mls::experimental::affine_advection::velocity_at(field, after_half);
    const auto stale_terminal = after_half + half * stale_velocity;
    const auto ballistic_terminal = initial + (2.0 * half) * initial_velocity;
    MLS_REQUIRE(close(
        stale_terminal - ballistic_terminal,
        mls::experimental::affine_advection::stale_gradient_position_defect(
            field, initial, half),
        5.0e-12));
    MLS_REQUIRE(close(
        stale_velocity - initial_velocity,
        mls::experimental::affine_advection::stale_gradient_velocity_defect(
            field, initial, half),
        5.0e-12));
}

MLS_TEST("convected affine control updates Path C auxiliary without changing material velocity") {
    const auto field = rotation_field();
    const auto particles = particles_for(field);
    const TransferConfig config{0.5, {0.065, 0.185, 0.355}, 0.125};
    const auto timestep = 0.05;
    const auto stale = mls::experimental::affine_advection::sealed_static_apic_ballistic_step(
        particles, config, timestep);
    const auto control =
        mls::experimental::affine_advection::analytic_convected_control_step(
            particles, config, field, timestep);
    const auto expected_field =
        mls::experimental::affine_advection::convected_affine_field(field, timestep);
    MLS_REQUIRE_EQ(stale.size(), control.particles.size());
    for (std::size_t index = 0; index < stale.size(); ++index) {
        MLS_REQUIRE(close(stale[index].position_m, control.particles[index].position_m));
        MLS_REQUIRE(close(
            stale[index].velocity_m_per_s, control.particles[index].velocity_m_per_s));
        MLS_REQUIRE(close(
            control.particles[index].affine_velocity_per_s,
            expected_field.gradient_per_s,
            5.0e-12));
    }
    MLS_REQUIRE(close(control.field.gradient_per_s, expected_field.gradient_per_s));
}

MLS_TEST("JST 2017 moving APIC isolated particle is stable and non-dissipative") {
    const TransferConfig config{0.5, {0.065, 0.185, 0.355}, 0.25};
    TransferParticle source{
        7,
        13,
        {0.317, -0.289, 0.611},
        {0.83, -0.41, 0.29},
        general_field().gradient_per_s,
    };
    auto particle =
        mls::experimental::affine_advection::initialize_moving_apic_particle(source, config);
    const auto initial = particle;
    const auto timestep = 0.025;
    for (int step = 0; step < 32; ++step) {
        const auto result =
            mls::experimental::affine_advection::jst2017_moving_apic_no_force_step(
                std::array{particle}, config, timestep);
        MLS_REQUIRE_EQ(result.exact_mass_quanta_before, result.exact_mass_quanta_after);
        MLS_REQUIRE(close(result.step_center_energy_residual_j, 0.0, 5.0e-12));
        particle = result.particles.front();
    }
    MLS_REQUIRE(close(particle.velocity_m_per_s, initial.velocity_m_per_s, 2.0e-11));
    MLS_REQUIRE(close(particle.B_m2_per_s, initial.B_m2_per_s, 2.0e-10));
    MLS_REQUIRE(close(
        particle.position_m,
        initial.position_m + (32.0 * timestep) * initial.velocity_m_per_s,
        2.0e-11));
}

MLS_TEST("JST 2017 no-force path independently matches one sealed APIC composition") {
    const auto field = general_field();
    const auto particles = particles_for(field);
    const TransferConfig config{0.5, {0.245, 0.005, 0.415}, 0.125};
    const auto timestep = 0.05;
    std::vector<MovingApicParticle> moving;
    for (const auto& particle : particles) {
        moving.push_back(
            mls::experimental::affine_advection::initialize_moving_apic_particle(
                particle, config));
    }
    const auto paper =
        mls::experimental::affine_advection::jst2017_moving_apic_no_force_step(
            moving, config, timestep);
    const auto paper_particles =
        mls::experimental::affine_advection::as_transfer_particles(paper.particles, config);
    const auto sealed = mls::experimental::affine_advection::sealed_static_apic_ballistic_step(
        particles, config, timestep);
    MLS_REQUIRE_EQ(paper.exact_mass_quanta_before, paper.exact_mass_quanta_after);
    MLS_REQUIRE_EQ(paper_particles.size(), sealed.size());
    for (std::size_t index = 0; index < sealed.size(); ++index) {
        MLS_REQUIRE(close(paper_particles[index].position_m, sealed[index].position_m, 2.0e-11));
        MLS_REQUIRE(close(
            paper_particles[index].velocity_m_per_s,
            sealed[index].velocity_m_per_s,
            2.0e-11));
        MLS_REQUIRE(close(
            paper_particles[index].affine_velocity_per_s,
            sealed[index].affine_velocity_per_s,
            2.0e-10));
    }
}

MLS_TEST("convected affine control removes the nontranslation two-remap defect") {
    const auto field = general_field();
    const auto initial = particles_for(field);
    const TransferConfig config{0.5, {0.065, 0.185, 0.355}, 0.125};
    const auto timestep = 0.08;
    auto stale = initial;
    auto control = initial;
    auto control_field = field;
    for (int step = 0; step < 4; ++step) {
        stale = mls::experimental::affine_advection::sealed_static_apic_ballistic_step(
            stale, config, timestep);
        auto next = mls::experimental::affine_advection::analytic_convected_control_step(
            control, config, control_field, timestep);
        control = std::move(next.particles);
        control_field = next.field;
    }
    const auto stale_error = max_velocity_error(stale, initial);
    const auto control_error = max_velocity_error(control, initial);
    MLS_REQUIRE(stale_error > 1.0e-4);
    MLS_REQUIRE(control_error < 1.0e-10);
    MLS_REQUIRE(stale_error > 1.0e5 * std::max(control_error, 1.0e-15));
}

MLS_TEST("affine convection rejects singular maps and nonpositive timesteps") {
    auto singular = AffineField{};
    singular.gradient_per_s.value[0][0] = -2.0;
    MLS_REQUIRE_THROWS(
        std::domain_error,
        mls::experimental::affine_advection::convected_affine_field(singular, 0.5));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        mls::experimental::affine_advection::convected_affine_field(general_field(), 0.0));
}
