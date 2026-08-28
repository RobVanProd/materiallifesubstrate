#include "test_harness.hpp"

#include "mls/moving_apic_limit_lab.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
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

[[nodiscard]] Matrix3d subtract(const Matrix3d& lhs, const Matrix3d& rhs) noexcept {
    Matrix3d result{};
    for (std::size_t row = 0; row < 3; ++row) {
        for (std::size_t column = 0; column < 3; ++column) {
            result.value[row][column] =
                lhs.value[row][column] - rhs.value[row][column];
        }
    }
    return result;
}

[[nodiscard]] Matrix3d inverse(const Matrix3d& matrix) {
    const auto& a = matrix.value;
    const auto determinant =
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) -
        a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) +
        a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]);
    if (determinant == 0.0) {
        throw std::domain_error("singular test matrix");
    }
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
    return (1.0 / determinant) * result;
}

[[nodiscard]] AffineField general_affine_field() {
    AffineField result{};
    result.gradient_per_s.value = {{{3.0 / 20.0, 2.0 / 5.0, 7.0 / 20.0},
                                    {1.0 / 4.0, -1.0 / 10.0, -11.0 / 20.0},
                                    {-3.0 / 10.0, 7.0 / 10.0, 1.0 / 5.0}}};
    result.offset_m_per_s = {111.0 / 125.0, -129.0 / 200.0, -74.0 / 125.0};
    return result;
}

[[nodiscard]] std::vector<MovingApicParticle> small_affine_lattice(
    const TransferConfig& config, const AffineField& field) {
    std::vector<MovingApicParticle> result;
    std::uint64_t id = 1;
    for (const auto x : {-0.375, 0.125}) {
        for (const auto y : {-0.225, 0.275}) {
            for (const auto z : {-0.325, 0.175}) {
                const Vec3d position{x, y, z};
                const TransferParticle source{
                    id,
                    static_cast<std::int64_t>(id + 2U),
                    position,
                    mls::experimental::affine_advection::velocity_at(field, position),
                    field.gradient_per_s,
                };
                result.push_back(
                    mls::experimental::affine_advection::initialize_moving_apic_particle(
                        source, config));
                ++id;
            }
        }
    }
    return result;
}

void require_same_material_state(
    const MovingApicParticle& actual, const MovingApicParticle& expected) {
    MLS_REQUIRE_EQ(actual.id, expected.id);
    MLS_REQUIRE_EQ(actual.mass_quanta, expected.mass_quanta);
    MLS_REQUIRE_EQ(actual.position_m, expected.position_m);
    MLS_REQUIRE_EQ(actual.velocity_m_per_s, expected.velocity_m_per_s);
}

} // namespace

MLS_TEST("oracle-B intervention changes only B and leaves the direct Path E result untouched") {
    const TransferConfig config{0.5, {0.245, 0.005, 0.415}, 0.125};
    const auto field = general_affine_field();
    const auto input = small_affine_lattice(config, field);
    const auto input_copy = input;
    constexpr double timestep_s = 0.025;
    const auto paper =
        mls::experimental::affine_advection::jst2017_moving_apic_no_force_step(
            input, config, timestep_s);
    MLS_REQUIRE_EQ(input, input_copy);
    const auto paper_copy = paper.particles;
    const auto exact_next =
        mls::experimental::affine_advection::convected_affine_field(
            field, timestep_s);
    const auto intervention =
        mls::experimental::moving_apic_limit::apply_oracle_B_after_G2P(
            paper.particles, config, exact_next);

    MLS_REQUIRE_EQ(paper.particles, paper_copy);
    MLS_REQUIRE_EQ(intervention.particles.size(), paper.particles.size());
    for (std::size_t index = 0; index < paper.particles.size(); ++index) {
        require_same_material_state(intervention.particles[index], paper.particles[index]);
        const auto D_next =
            mls::experimental::affine_advection::particle_moment_matrix(
                paper.particles[index].position_m, config);
        const auto expected_B =
            mls::experimental::multiply(exact_next.gradient_per_s, D_next);
        MLS_REQUIRE_EQ(intervention.particles[index].B_m2_per_s, expected_B);
    }
    MLS_REQUIRE(intervention.max_relative_B_override > 1.0e-8);
    MLS_REQUIRE_EQ(intervention.max_relative_B_constraint_error, 0.0);
}

MLS_TEST("oracle-B intervention preserves exact mass and all material-center totals") {
    const TransferConfig config{0.5, {0.245, 0.005, 0.415}, 0.125};
    const auto field = general_affine_field();
    const auto input = small_affine_lattice(config, field);
    constexpr double timestep_s = 0.025;
    const auto paper =
        mls::experimental::affine_advection::jst2017_moving_apic_no_force_step(
            input, config, timestep_s);
    const auto exact_next =
        mls::experimental::affine_advection::convected_affine_field(
            field, timestep_s);
    const auto intervention =
        mls::experimental::moving_apic_limit::apply_oracle_B_after_G2P(
            paper.particles, config, exact_next);

    MLS_REQUIRE_EQ(
        intervention.exact_mass_quanta_before,
        intervention.exact_mass_quanta_after);
    MLS_REQUIRE_EQ(intervention.exact_mass_quanta_before, paper.exact_mass_quanta_after);
    MLS_REQUIRE_EQ(
        intervention.pre_override_totals.mass_kg,
        intervention.post_override_totals.mass_kg);
    MLS_REQUIRE_EQ(
        intervention.pre_override_totals.linear_momentum_kg_m_per_s,
        intervention.post_override_totals.linear_momentum_kg_m_per_s);
    MLS_REQUIRE_EQ(
        intervention.pre_override_totals.center_orbital_kg_m2_per_s,
        intervention.post_override_totals.center_orbital_kg_m2_per_s);
    MLS_REQUIRE_EQ(
        intervention.pre_override_totals.center_kinetic_j,
        intervention.post_override_totals.center_kinetic_j);
}

MLS_TEST("moving APIC first affine step has the derived B C and discrepancy fingerprint") {
    const TransferConfig config{0.5, {0.245, 0.005, 0.415}, 0.125};
    const auto field = general_affine_field();
    const auto input = small_affine_lattice(config, field);
    constexpr double timestep_s = 0.025;
    const auto paper =
        mls::experimental::affine_advection::jst2017_moving_apic_no_force_step(
            input, config, timestep_s);
    const auto exact_next =
        mls::experimental::affine_advection::convected_affine_field(
            field, timestep_s);
    const auto affine_map =
        Matrix3d::identity() + timestep_s * field.gradient_per_s;
    const auto expected_discrepancy = timestep_s * mls::experimental::multiply(
        mls::experimental::multiply(
            field.gradient_per_s, field.gradient_per_s),
        inverse(affine_map));
    const auto intervention =
        mls::experimental::moving_apic_limit::apply_oracle_B_after_G2P(
            paper.particles, config, exact_next);

    MLS_REQUIRE_EQ(paper.particles.size(), input.size());
    for (std::size_t index = 0; index < input.size(); ++index) {
        const auto D_old =
            mls::experimental::affine_advection::particle_moment_matrix(
                input[index].position_m, config);
        const auto expected_paper_B =
            mls::experimental::multiply(field.gradient_per_s, D_old);
        MLS_REQUIRE(close(
            paper.particles[index].B_m2_per_s, expected_paper_B, 5.0e-11));

        const auto paper_C =
            mls::experimental::affine_advection::moving_apic_affine_matrix(
                paper.particles[index], config);
        MLS_REQUIRE(close(paper_C, field.gradient_per_s, 5.0e-11));
        MLS_REQUIRE(close(
            subtract(paper_C, exact_next.gradient_per_s),
            expected_discrepancy,
            5.0e-11));

        const auto oracle_C =
            mls::experimental::affine_advection::moving_apic_affine_matrix(
                intervention.particles[index], config);
        MLS_REQUIRE(close(oracle_C, exact_next.gradient_per_s, 5.0e-11));
    }
}

MLS_TEST("oracle-B intervention rejects nonfinite fields invalid configs and invalid paper state") {
    const TransferConfig config{0.5, {0.245, 0.005, 0.415}, 0.125};
    const auto field = general_affine_field();
    auto input = small_affine_lattice(config, field);

    auto invalid_field = field;
    invalid_field.gradient_per_s.value[1][2] =
        std::numeric_limits<double>::quiet_NaN();
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        mls::experimental::moving_apic_limit::apply_oracle_B_after_G2P(
            input, config, invalid_field));

    invalid_field = field;
    invalid_field.offset_m_per_s.x = std::numeric_limits<double>::infinity();
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        mls::experimental::moving_apic_limit::apply_oracle_B_after_G2P(
            input, config, invalid_field));

    const TransferConfig invalid_config{0.0, config.grid_origin_m, 0.125};
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        mls::experimental::moving_apic_limit::apply_oracle_B_after_G2P(
            input, invalid_config, field));

    input[1].id = input[0].id;
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        mls::experimental::moving_apic_limit::apply_oracle_B_after_G2P(
            input, config, field));
}
