#include "test_harness.hpp"

#include "mls/projection_foundation_lab.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <concepts>
#include <cstdint>
#include <limits>
#include <iostream>
#include <span>
#include <stdexcept>
#include <type_traits>
#include <utility>
#include <vector>

namespace {

namespace projection = mls::experimental::projection_foundation;
using mls::PhysicalTimeScale;
using mls::experimental::Matrix3d;
using mls::experimental::TransferConfig;
using mls::experimental::Vec3d;
using projection::CenterParticle;
using projection::ProjectionCandidate;
using projection::ProjectionLabState;
using projection::ProjectionStatus;

template <typename Type>
concept HasAffineState = requires(Type value) { value.affine_velocity_per_s; };

template <typename Type>
concept HasPolynomialState = requires(Type value) { value.polynomial_mode; };

template <typename Type>
concept HasNumericalEnergyLedger = requires(Type value) { value.numerical_energy_ledger; };

static_assert(!HasAffineState<CenterParticle>);
static_assert(!HasPolynomialState<CenterParticle>);
static_assert(!HasNumericalEnergyLedger<CenterParticle>);
static_assert(std::same_as<decltype(CenterParticle::id), std::uint64_t>);
static_assert(std::same_as<decltype(CenterParticle::mass_quanta), std::int64_t>);
static_assert(std::same_as<decltype(CenterParticle::position_m), Vec3d>);
static_assert(std::same_as<decltype(CenterParticle::velocity_m_per_s), Vec3d>);
static_assert(!std::default_initializable<projection::ProjectionSystem>);
static_assert(std::same_as<
    decltype(std::declval<const projection::ProjectionSystem&>().active_nodes()),
    const std::vector<mls::experimental::GridIndex>&>);
static_assert(std::same_as<
    decltype(std::declval<const projection::ProjectionSystem&>().consistent_mass_rows()),
    const std::vector<std::map<std::size_t, double>>&>);

[[nodiscard]] bool close(double actual, double expected, double tolerance = 2.0e-11) {
    return std::abs(actual - expected) <=
        tolerance * std::max({1.0, std::abs(actual), std::abs(expected)});
}

[[nodiscard]] bool close(Vec3d actual, Vec3d expected, double tolerance = 2.0e-11) {
    return close(actual.x, expected.x, tolerance) &&
        close(actual.y, expected.y, tolerance) &&
        close(actual.z, expected.z, tolerance);
}

[[nodiscard]] Vec3d affine_velocity(const Matrix3d& matrix, Vec3d offset, Vec3d x) {
    return mls::experimental::multiply(matrix, x) + offset;
}

[[nodiscard]] std::vector<CenterParticle> lattice(
    const Matrix3d& matrix, Vec3d offset, bool non_affine = false) {
    std::vector<CenterParticle> result;
    std::uint64_t id = 1;
    for (std::size_t ix = 0; ix < 4U; ++ix) {
        for (std::size_t iy = 0; iy < 4U; ++iy) {
            for (std::size_t iz = 0; iz < 4U; ++iz) {
                const Vec3d position{
                    -0.375 + 0.25 * static_cast<double>(ix),
                    -0.375 + 0.25 * static_cast<double>(iy),
                    -0.375 + 0.25 * static_cast<double>(iz),
                };
                auto velocity = affine_velocity(matrix, offset, position);
                if (non_affine) {
                    velocity.x += 0.17 * std::sin(2.3 * position.y) *
                        std::cos(1.7 * position.z);
                    velocity.y += 0.13 * std::sin(1.9 * position.z) *
                        std::cos(2.1 * position.x);
                    velocity.z += 0.11 * std::sin(1.5 * position.x) *
                        std::cos(2.7 * position.y);
                }
                result.push_back({id++, 2, position, velocity});
            }
        }
    }
    return result;
}

[[nodiscard]] Matrix3d general_affine_matrix() {
    Matrix3d result{};
    result.value = {{{0.15, 0.40, 0.35},
                     {0.25, -0.10, -0.55},
                     {-0.30, 0.70, 0.20}}};
    return result;
}

[[nodiscard]] Vec3d linear_momentum(
    std::span<const CenterParticle> particles, const TransferConfig& config) {
    Vec3d result{};
    for (const auto& particle : particles) {
        result += static_cast<double>(particle.mass_quanta) *
            config.kg_per_mass_quantum * particle.velocity_m_per_s;
    }
    return result;
}

[[nodiscard]] Vec3d orbital_angular(
    std::span<const CenterParticle> particles, const TransferConfig& config) {
    Vec3d result{};
    for (const auto& particle : particles) {
        const auto momentum = static_cast<double>(particle.mass_quanta) *
            config.kg_per_mass_quantum * particle.velocity_m_per_s;
        result += mls::experimental::cross(particle.position_m, momentum);
    }
    return result;
}

[[nodiscard]] std::vector<Vec3d> dense_solve(
    const projection::ProjectionSystem& system) {
    const auto count = system.active_nodes().size();
    std::vector<double> matrix(count * count, 0.0);
    for (std::size_t row = 0; row < count; ++row) {
        for (const auto& [column, coefficient] : system.consistent_mass_rows()[row]) {
            matrix[row * count + column] = coefficient;
        }
    }
    std::array<std::vector<double>, 3> rhs;
    for (auto& component : rhs) {
        component.resize(count);
    }
    for (std::size_t index = 0; index < count; ++index) {
        rhs[0][index] = system.consistent_rhs_kg_m_per_s()[index].x;
        rhs[1][index] = system.consistent_rhs_kg_m_per_s()[index].y;
        rhs[2][index] = system.consistent_rhs_kg_m_per_s()[index].z;
    }
    for (std::size_t pivot = 0; pivot < count; ++pivot) {
        auto selected = pivot;
        for (std::size_t row = pivot + 1U; row < count; ++row) {
            if (std::abs(matrix[row * count + pivot]) >
                std::abs(matrix[selected * count + pivot])) {
                selected = row;
            }
        }
        if (selected != pivot) {
            for (std::size_t column = pivot; column < count; ++column) {
                std::swap(
                    matrix[pivot * count + column],
                    matrix[selected * count + column]);
            }
            for (auto& component : rhs) {
                std::swap(component[pivot], component[selected]);
            }
        }
        MLS_REQUIRE(std::abs(matrix[pivot * count + pivot]) > 1.0e-15);
        for (std::size_t row = pivot + 1U; row < count; ++row) {
            const auto factor = matrix[row * count + pivot] /
                matrix[pivot * count + pivot];
            for (std::size_t column = pivot; column < count; ++column) {
                matrix[row * count + column] -=
                    factor * matrix[pivot * count + column];
            }
            for (auto& component : rhs) {
                component[row] -= factor * component[pivot];
            }
        }
    }
    std::vector<Vec3d> result(count);
    for (std::size_t component = 0; component < 3U; ++component) {
        for (std::size_t reverse = count; reverse > 0U; --reverse) {
            const auto row = reverse - 1U;
            auto value = rhs[component][row];
            for (std::size_t column = row + 1U; column < count; ++column) {
                const auto known = component == 0U ? result[column].x
                    : component == 1U ? result[column].y : result[column].z;
                value -= matrix[row * count + column] * known;
            }
            value /= matrix[row * count + row];
            if (component == 0U) {
                result[row].x = value;
            } else if (component == 1U) {
                result[row].y = value;
            } else {
                result[row].z = value;
            }
        }
    }
    return result;
}

[[nodiscard]] double raw_cholesky_pivot_spread(
    const projection::ProjectionSystem& system) {
    const auto count = system.active_nodes().size();
    std::vector<double> factor(count * count, 0.0);
    for (std::size_t row = 0; row < count; ++row) {
        for (const auto& [column, coefficient] : system.consistent_mass_rows()[row]) {
            factor[row * count + column] = coefficient;
        }
    }
    auto smallest = std::numeric_limits<double>::infinity();
    auto largest = 0.0;
    for (std::size_t row = 0; row < count; ++row) {
        for (std::size_t column = 0; column <= row; ++column) {
            long double value = factor[row * count + column];
            for (std::size_t inner = 0; inner < column; ++inner) {
                value -= static_cast<long double>(factor[row * count + inner]) *
                    static_cast<long double>(factor[column * count + inner]);
            }
            if (row == column) {
                const auto pivot = static_cast<double>(value);
                MLS_REQUIRE(pivot > 0.0);
                smallest = std::min(smallest, pivot);
                largest = std::max(largest, pivot);
                factor[row * count + column] = std::sqrt(pivot);
            } else {
                factor[row * count + column] =
                    static_cast<double>(value) / factor[column * count + column];
            }
        }
    }
    return largest / smallest;
}

[[nodiscard]] std::array<double, 3> independently_computed_residuals(
    const projection::ProjectionSystem& system,
    std::span<const Vec3d> grid_velocity) {
    std::array<long double, 3> squared{};
    for (std::size_t row = 0; row < system.active_nodes().size(); ++row) {
        Vec3d applied{};
        for (const auto& [column, coefficient] : system.consistent_mass_rows()[row]) {
            applied += coefficient * grid_velocity[column];
        }
        const auto residual = applied - system.consistent_rhs_kg_m_per_s()[row];
        squared[0] += static_cast<long double>(residual.x) * residual.x;
        squared[1] += static_cast<long double>(residual.y) * residual.y;
        squared[2] += static_cast<long double>(residual.z) * residual.z;
    }
    return {
        std::sqrt(static_cast<double>(squared[0])),
        std::sqrt(static_cast<double>(squared[1])),
        std::sqrt(static_cast<double>(squared[2])),
    };
}

[[nodiscard]] std::uint64_t fnv1a(std::span<const std::uint8_t> bytes) noexcept {
    auto hash = UINT64_C(14695981039346656037);
    for (const auto byte : bytes) {
        hash = (hash ^ byte) * UINT64_C(1099511628211);
    }
    return hash;
}

template <typename Integer>
void write_little(std::vector<std::uint8_t>& bytes, std::size_t offset, Integer value) {
    using Unsigned = std::make_unsigned_t<Integer>;
    auto bits = static_cast<Unsigned>(value);
    MLS_REQUIRE(offset + sizeof(Unsigned) <= bytes.size());
    for (std::size_t index = 0; index < sizeof(Unsigned); ++index) {
        bytes[offset + index] = static_cast<std::uint8_t>(bits & Unsigned{0xff});
        bits >>= 8U;
    }
}

void refresh_checksum(std::vector<std::uint8_t>& bytes) {
    MLS_REQUIRE(bytes.size() >= sizeof(std::uint64_t));
    const auto payload_size = bytes.size() - sizeof(std::uint64_t);
    write_little(bytes, payload_size, fnv1a(std::span(bytes).first(payload_size)));
}

[[nodiscard]] bool checkpoint_rejected(const std::vector<std::uint8_t>& bytes) {
    try {
        static_cast<void>(projection::deserialize_projection_checkpoint(bytes));
    } catch (const std::invalid_argument&) {
        return true;
    }
    return false;
}

[[nodiscard]] ProjectionLabState checkpoint_state() {
    auto particles = lattice(Matrix3d::zero(), {0.45, -0.3, 0.2});
    std::ranges::reverse(particles);
    return {
        {1.0, {0.13, -0.07, 0.21}, 0.01},
        PhysicalTimeScale{1, 160},
        7,
        std::move(particles),
    };
}

} // namespace

MLS_TEST("projection foundation center state has no hidden persistent modes") {
    const CenterParticle particle{7, 3, {1.0, 2.0, 3.0}, {4.0, 5.0, 6.0}};
    MLS_REQUIRE_EQ(particle.id, UINT64_C(7));
    MLS_REQUIRE_EQ(particle.mass_quanta, INT64_C(3));
}

MLS_TEST("projection assembly is canonical under input permutation") {
    const TransferConfig config{1.0, {}, 0.01};
    auto particles = lattice(general_affine_matrix(), {0.888, -0.645, -0.592});
    const auto forward = projection::build_projection_system(particles, config);
    std::ranges::reverse(particles);
    const auto reverse = projection::build_projection_system(particles, config);
    MLS_REQUIRE_EQ(forward.particles(), reverse.particles());
    MLS_REQUIRE_EQ(forward.active_nodes(), reverse.active_nodes());
    MLS_REQUIRE_EQ(forward.particle_stencils(), reverse.particle_stencils());
    MLS_REQUIRE_EQ(forward.lumped_mass_kg(), reverse.lumped_mass_kg());
    MLS_REQUIRE_EQ(forward.consistent_mass_rows(), reverse.consistent_mass_rows());
    MLS_REQUIRE_EQ(
        forward.consistent_rhs_kg_m_per_s(), reverse.consistent_rhs_kg_m_per_s());
    MLS_REQUIRE_EQ(
        forward.assembly_diagnostics().node_order_digest,
        reverse.assembly_diagnostics().node_order_digest);
    MLS_REQUIRE(forward.assembly_diagnostics().partition_unity_max_residual <= 5.0e-14);
    MLS_REQUIRE(
        forward.assembly_diagnostics().linear_reproduction_max_residual_m <= 5.0e-13);
    MLS_REQUIRE(
        forward.assembly_diagnostics().matrix_symmetry_relative_residual <= 5.0e-15);
    MLS_REQUIRE(forward.assembly_diagnostics().row_sum_relative_residual <= 5.0e-13);
}

MLS_TEST("projection PIC and FMPM1 are identical and translation is reproduced") {
    const TransferConfig config{1.0, {}, 0.01};
    const auto particles = lattice(Matrix3d::zero(), {0.45, -0.30, 0.20});
    const auto system = projection::build_projection_system(particles, config);
    const auto pic = projection::project_centers(system, ProjectionCandidate::lumped_pic);
    const auto fmpm = projection::project_centers(system, ProjectionCandidate::fmpm_1);
    MLS_REQUIRE_EQ(pic.status, ProjectionStatus::solved);
    MLS_REQUIRE_EQ(fmpm.status, ProjectionStatus::solved);
    MLS_REQUIRE_EQ(pic.grid_velocity_m_per_s, fmpm.grid_velocity_m_per_s);
    MLS_REQUIRE_EQ(pic.particles, fmpm.particles);
    MLS_REQUIRE(fmpm.fmpm_residual_identity_normalized <= 5.0e-14);
    for (const auto& particle : pic.particles) {
        MLS_REQUIRE(close(particle.velocity_m_per_s, {0.45, -0.30, 0.20}, 1.0e-14));
    }
}

MLS_TEST("projection full mass recovers affine field and agrees with dense comparator") {
    const TransferConfig config{1.0, {}, 0.01};
    const auto matrix = general_affine_matrix();
    const Vec3d offset{0.888, -0.645, -0.592};
    const auto particles = lattice(matrix, offset);
    const auto system = projection::build_projection_system(particles, config);
    MLS_REQUIRE(system.active_nodes().size() <= particles.size());
    const auto full = projection::project_centers(system, ProjectionCandidate::full_consistent);
    std::cout << "[EVIDENCE] projection_unit_full_status="
              << projection::status_name(full.status)
              << " nodes=" << system.active_nodes().size()
              << " rank=" << full.diagnostics.numerical_rank_estimate
              << " raw_condition=" << full.diagnostics.raw_condition_estimate
              << " preconditioned_condition="
              << full.diagnostics.preconditioned_condition_estimate << '\n';
    MLS_REQUIRE_EQ(full.status, ProjectionStatus::solved);
    MLS_REQUIRE_EQ(full.diagnostics.numerical_rank_estimate, system.active_nodes().size());
    MLS_REQUIRE(full.diagnostics.rank_certified);
    MLS_REQUIRE(full.diagnostics.condition_estimated);
    MLS_REQUIRE(full.diagnostics.raw_condition_estimate <= 1.0e10);
    for (const auto residual : full.diagnostics.normalized_solve_residual) {
        MLS_REQUIRE(residual <= 5.0e-12);
    }
    for (const auto& particle : full.particles) {
        MLS_REQUIRE(close(
            particle.velocity_m_per_s,
            affine_velocity(matrix, offset, particle.position_m),
            5.0e-10));
    }
    const auto dense = dense_solve(system);
    MLS_REQUIRE_EQ(dense.size(), full.grid_velocity_m_per_s.size());
    for (std::size_t index = 0; index < dense.size(); ++index) {
        MLS_REQUIRE(close(dense[index], full.grid_velocity_m_per_s[index], 3.0e-10));
    }

    // This SPD Gram matrix is an adversarial counterexample to treating the
    // spread of Cholesky pivots as the spectral condition number. The true
    // symmetric-eigen diagnostic is over two orders of magnitude larger.
    const auto pivot_spread = raw_cholesky_pivot_spread(system);
    MLS_REQUIRE(full.diagnostics.raw_condition_estimate > 50.0 * pivot_spread);
    projection::ProjectionSolvePolicy adversarial_gate{};
    adversarial_gate.raw_condition_max = 2.0 * pivot_spread;
    adversarial_gate.preconditioned_condition_max = 1.0e12;
    const auto rejected = projection::project_centers(
        system, ProjectionCandidate::full_consistent, adversarial_gate);
    MLS_REQUIRE_EQ(rejected.status, ProjectionStatus::ill_conditioned);
}

MLS_TEST("projection full static cycle preserves center linear and orbital moments") {
    const TransferConfig config{1.0, {}, 0.01};
    const auto particles = lattice(
        general_affine_matrix(), {0.888, -0.645, -0.592}, true);
    const auto full = projection::project_centers(
        particles, config, ProjectionCandidate::full_consistent);
    MLS_REQUIRE_EQ(full.status, ProjectionStatus::solved);
    MLS_REQUIRE(close(
        linear_momentum(full.particles, config),
        linear_momentum(particles, config),
        2.0e-10));
    MLS_REQUIRE(close(
        orbital_angular(full.particles, config),
        orbital_angular(particles, config),
        3.0e-10));
}

MLS_TEST("projection smooth nonaffine field is not falsely claimed exact") {
    const TransferConfig config{1.0, {}, 0.01};
    const auto particles = lattice(
        general_affine_matrix(), {0.888, -0.645, -0.592}, true);
    const auto full = projection::project_centers(
        particles, config, ProjectionCandidate::full_consistent);
    MLS_REQUIRE_EQ(full.status, ProjectionStatus::solved);
    double maximum_error = 0.0;
    for (std::size_t index = 0; index < particles.size(); ++index) {
        maximum_error = std::max(
            maximum_error,
            mls::experimental::norm(
                full.particles[index].velocity_m_per_s - particles[index].velocity_m_per_s));
    }
    MLS_REQUIRE(maximum_error > 1.0e-5);
    MLS_REQUIRE(full.numerical_projection_energy_residual_j < 0.0);
}

MLS_TEST("projection FMPM recurrence satisfies residual identity at every frozen order") {
    const TransferConfig config{1.0, {0.13, -0.07, 0.21}, 0.01};
    const auto particles = lattice(
        general_affine_matrix(), {0.888, -0.645, -0.592}, true);
    const auto system = projection::build_projection_system(particles, config);
    const std::array candidates{
        ProjectionCandidate::fmpm_1,
        ProjectionCandidate::fmpm_2,
        ProjectionCandidate::fmpm_3,
        ProjectionCandidate::fmpm_4,
    };
    std::array<double, 4> fingerprint{};
    std::array<double, 4> angular_change{};
    std::array<double, 4> energy_change{};
    const auto momentum_before = linear_momentum(particles, config);
    const auto angular_before = orbital_angular(particles, config);
    for (std::size_t index = 0; index < candidates.size(); ++index) {
        const auto result = projection::project_centers(system, candidates[index]);
        MLS_REQUIRE_EQ(result.status, ProjectionStatus::solved);
        MLS_REQUIRE(result.fmpm_residual_identity_applicable);
        MLS_REQUIRE(result.fmpm_residual_identity_normalized <= 5.0e-14);
        const auto independently_computed = independently_computed_residuals(
            system, result.grid_velocity_m_per_s);
        for (std::size_t component = 0; component < 3U; ++component) {
            MLS_REQUIRE(result.diagnostics.solve_residual_applicable[component]);
            MLS_REQUIRE(close(
                result.diagnostics.absolute_solve_residual[component],
                independently_computed[component],
                2.0e-14));
        }
        MLS_REQUIRE(close(
            linear_momentum(result.particles, config), momentum_before, 2.0e-12));
        angular_change[index] = mls::experimental::norm(
            orbital_angular(result.particles, config) - angular_before);
        fingerprint[index] = result.grid_velocity_m_per_s.front().x;
        energy_change[index] = result.numerical_projection_energy_residual_j;
    }
    std::cout << "[EVIDENCE] projection_fmpm_fingerprint="
              << std::bit_cast<std::uint64_t>(fingerprint[0]) << ','
              << std::bit_cast<std::uint64_t>(fingerprint[1]) << ','
              << std::bit_cast<std::uint64_t>(fingerprint[2]) << ','
              << std::bit_cast<std::uint64_t>(fingerprint[3]) << '\n';
    // A fixed recurrence witness: successive orders are distinct for this
    // non-affine state and therefore cannot all collapse to PIC accidentally.
    MLS_REQUIRE(std::abs(fingerprint[1] - fingerprint[0]) > 1.0e-6);
    MLS_REQUIRE(std::abs(fingerprint[2] - fingerprint[1]) > 1.0e-6);
    MLS_REQUIRE(std::abs(fingerprint[3] - fingerprint[2]) > 1.0e-6);
    // Finite FMPM has no generic orbital-angular theorem. This witness keeps
    // that expected residual visible instead of post-correcting it away.
    MLS_REQUIRE(angular_change[0] > 1.0e-8);
    // Do not manufacture a positive roundoff witness: with positive weights,
    // H=D^-1/2 M D^-1/2 has spectrum in [0,1] and finite FMPM applies
    // 1-(1-lambda)^k in [0,1]. The exact center map is nonexpansive.
    MLS_REQUIRE(energy_change[0] < 0.0);

    const auto fmpm_one = projection::project_centers(
        system, ProjectionCandidate::fmpm_1);
    long double q_dot_v = 0.0L;
    long double v_dot_m_v = 0.0L;
    const auto mass_velocity = projection::apply_consistent_mass(
        system, fmpm_one.grid_velocity_m_per_s);
    for (std::size_t node = 0; node < system.active_nodes().size(); ++node) {
        q_dot_v += mls::experimental::dot(
            system.consistent_rhs_kg_m_per_s()[node],
            fmpm_one.grid_velocity_m_per_s[node]);
        v_dot_m_v += mls::experimental::dot(
            mass_velocity[node], fmpm_one.grid_velocity_m_per_s[node]);
    }
    MLS_REQUIRE(fmpm_one.consistent_grid_quadratic_energy_applicable);
    MLS_REQUIRE(close(
        fmpm_one.consistent_grid_quadratic_energy_j,
        0.5 * static_cast<double>(q_dot_v),
        2.0e-14));
    MLS_REQUIRE(std::abs(static_cast<double>(q_dot_v - v_dot_m_v)) > 1.0e-8);
}

MLS_TEST("projection production assembly and FMPM recurrence match rational cross-wire") {
    // Independent Fraction arithmetic for this two-particle stencil gives the
    // constants below. Expected values do not call the production M/q/D path.
    const TransferConfig config{1.0, {}, 1.0};
    const std::vector<CenterParticle> particles{
        {2, 1, {0.5, 0.0, 0.0}, {-2.0, 0.0, 0.0}},
        {1, 1, {0.0, 0.0, 0.0}, {1.0, 0.0, 0.0}},
    };
    const auto system = projection::build_projection_system(particles, config);
    MLS_REQUIRE_EQ(system.active_nodes().size(), std::size_t{27});
    MLS_REQUIRE_EQ(system.active_nodes().front(), (mls::experimental::GridIndex{-1, -1, -1}));
    MLS_REQUIRE_EQ(system.active_nodes()[13], (mls::experimental::GridIndex{0, 0, 0}));
    MLS_REQUIRE_EQ(system.active_nodes().back(), (mls::experimental::GridIndex{1, 1, 1}));

    MLS_REQUIRE_EQ(system.lumped_mass_kg().front(), 1.0 / 512.0);
    MLS_REQUIRE_EQ(system.lumped_mass_kg()[13], 45.0 / 64.0);
    MLS_REQUIRE_EQ(system.lumped_mass_kg().back(), 5.0 / 512.0);
    MLS_REQUIRE_EQ(system.consistent_rhs_kg_m_per_s().front().x, 1.0 / 512.0);
    MLS_REQUIRE_EQ(system.consistent_rhs_kg_m_per_s()[13].x, -9.0 / 64.0);
    MLS_REQUIRE_EQ(system.consistent_rhs_kg_m_per_s().back().x, -7.0 / 512.0);
    MLS_REQUIRE_EQ(system.consistent_mass_rows().front().at(0), 1.0 / 262144.0);
    MLS_REQUIRE_EQ(system.consistent_mass_rows().front().at(13), 27.0 / 32768.0);
    MLS_REQUIRE_EQ(system.consistent_mass_rows()[13].at(13), 1053.0 / 4096.0);

    const std::array candidates{
        ProjectionCandidate::fmpm_1,
        ProjectionCandidate::fmpm_2,
        ProjectionCandidate::fmpm_3,
        ProjectionCandidate::fmpm_4,
    };
    const std::array expected_first{1.0, 11.0 / 5.0, 79.0 / 25.0, 491.0 / 125.0};
    const std::array expected_center{-1.0 / 5.0, 1.0 / 25.0, 29.0 / 125.0, 241.0 / 625.0};
    const std::array expected_last{-7.0 / 5.0, -53.0 / 25.0, -337.0 / 125.0,
                                   -1973.0 / 625.0};
    for (std::size_t order = 0; order < candidates.size(); ++order) {
        const auto result = projection::project_centers(system, candidates[order]);
        MLS_REQUIRE_EQ(result.status, ProjectionStatus::solved);
        MLS_REQUIRE(close(
            result.grid_velocity_m_per_s.front().x, expected_first[order], 2.0e-14));
        MLS_REQUIRE(close(
            result.grid_velocity_m_per_s[13].x, expected_center[order], 2.0e-14));
        MLS_REQUIRE(close(
            result.grid_velocity_m_per_s.back().x, expected_last[order], 2.0e-14));
    }
}

MLS_TEST("projection singular systems and solver limits fail closed") {
    const TransferConfig config{1.0, {}, 0.01};
    const std::vector<CenterParticle> one{{1, 1, {0.1, 0.2, 0.3}, {1.0, 2.0, 3.0}}};
    const auto structural = projection::project_centers(
        one, config, ProjectionCandidate::full_consistent);
    MLS_REQUIRE_EQ(structural.status, ProjectionStatus::structurally_rank_deficient);
    MLS_REQUIRE_EQ(structural.particles, one);
    MLS_REQUIRE(structural.grid_velocity_m_per_s.empty());
    MLS_REQUIRE_EQ(structural.diagnostics.exact_mass_quanta_before, INT64_C(1));
    MLS_REQUIRE_EQ(structural.diagnostics.exact_mass_quanta_after, INT64_C(1));
    for (std::size_t component = 0; component < 3U; ++component) {
        MLS_REQUIRE(!structural.diagnostics.solve_residual_applicable[component]);
        MLS_REQUIRE(std::isnan(structural.diagnostics.absolute_solve_residual[component]));
        MLS_REQUIRE(std::isnan(structural.diagnostics.normalized_solve_residual[component]));
    }

    std::vector<CenterParticle> coincident;
    for (std::uint64_t id = 1; id <= 27U; ++id) {
        coincident.push_back({id, 1, {0.1, 0.2, 0.3}, {1.0, 2.0, 3.0}});
    }
    const auto numerical = projection::project_centers(
        coincident, config, ProjectionCandidate::full_consistent);
    MLS_REQUIRE_EQ(numerical.status, ProjectionStatus::numerically_rank_deficient);
    MLS_REQUIRE_EQ(numerical.particles, coincident);
    MLS_REQUIRE_EQ(
        numerical.diagnostics.exact_mass_quanta_after,
        numerical.diagnostics.exact_mass_quanta_before);

    const auto regular = lattice(
        general_affine_matrix(), {0.888, -0.645, -0.592}, true);
    projection::ProjectionSolvePolicy limited{};
    limited.iteration_limit_override = 1;
    limited.normalized_residual_max = 1.0e-15;
    const auto stopped = projection::project_centers(
        regular, config, ProjectionCandidate::full_consistent, limited);
    MLS_REQUIRE_EQ(stopped.status, ProjectionStatus::iteration_limit);
    MLS_REQUIRE_EQ(stopped.particles, regular);
    MLS_REQUIRE(stopped.diagnostics.solve_residual_applicable[0]);
    MLS_REQUIRE(!stopped.diagnostics.solve_residual_applicable[1]);

    projection::ProjectionSolvePolicy condition_gate{};
    condition_gate.raw_condition_max = 1.000001;
    condition_gate.preconditioned_condition_max = 1.000001;
    const auto ill = projection::project_centers(
        regular, config, ProjectionCandidate::full_consistent, condition_gate);
    MLS_REQUIRE_EQ(ill.status, ProjectionStatus::ill_conditioned);
    MLS_REQUIRE_EQ(ill.particles, regular);

    projection::ProjectionSolvePolicy estimated{};
    estimated.dense_diagnostic_max_nodes = 1;
    estimated.lanczos_max_steps = 16;
    estimated.raw_condition_max = 1.0e20;
    estimated.preconditioned_condition_max = 1.0e20;
    const auto large_path = projection::project_centers(
        regular, config, ProjectionCandidate::full_consistent, estimated);
    MLS_REQUIRE_EQ(large_path.status, ProjectionStatus::solved);
    MLS_REQUIRE(!large_path.diagnostics.rank_certified);
    MLS_REQUIRE(large_path.diagnostics.numerical_rank_is_estimated);
    MLS_REQUIRE_EQ(large_path.diagnostics.numerical_rank_estimate, std::size_t{0});
    MLS_REQUIRE(large_path.diagnostics.condition_estimated);

    projection::ProjectionSolvePolicy unresolved{};
    unresolved.dense_jacobi_max_sweeps = 1;
    const auto unresolved_result = projection::project_centers(
        regular, config, ProjectionCandidate::full_consistent, unresolved);
    MLS_REQUIRE_EQ(unresolved_result.status, ProjectionStatus::breakdown);
    MLS_REQUIRE(!unresolved_result.diagnostics.solve_residual_applicable[0]);
}

MLS_TEST("projection rejects invalid zero duplicate overflow and nonfinite inputs") {
    const TransferConfig config{1.0, {}, 1.0};
    const auto empty_system = projection::build_projection_system({}, config);
    const auto empty = projection::project_centers(
        empty_system, ProjectionCandidate::full_consistent);
    MLS_REQUIRE_EQ(empty.status, ProjectionStatus::empty);
    MLS_REQUIRE(empty.particles.empty());

    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        projection::build_projection_system(
            std::array{CenterParticle{1, 0, {}, {}}}, config));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        projection::build_projection_system(
            std::array{
                CenterParticle{1, 1, {}, {}},
                CenterParticle{1, 2, {0.1, 0.2, 0.3}, {}},
            },
            config));
    MLS_REQUIRE_THROWS(
        std::overflow_error,
        projection::build_projection_system(
            std::array{
                CenterParticle{1, std::numeric_limits<std::int64_t>::max(), {}, {}},
                CenterParticle{2, 1, {0.1, 0.2, 0.3}, {}},
            },
            config));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        projection::build_projection_system(
            std::array{CenterParticle{
                1,
                1,
                {std::numeric_limits<double>::quiet_NaN(), 0.0, 0.0},
                {}}},
            config));
    MLS_REQUIRE_THROWS(
        std::overflow_error,
        projection::build_projection_system(
            std::array{CenterParticle{1, 1, {20'000.0, 0.0, 0.0}, {}}},
            config));
    MLS_REQUIRE_THROWS(
        std::overflow_error,
        projection::build_projection_system(
            std::array{CenterParticle{
                1, std::numeric_limits<std::int64_t>::max(), {}, {}}},
            TransferConfig{1.0, {}, std::numeric_limits<double>::max()}));

    const auto huge_speed = 2.0 * std::sqrt(std::numeric_limits<double>::max());
    const std::vector<CenterParticle> finite_but_overflowing{
        {2, 1, {0.1, 0.2, 0.3}, {huge_speed, 0.0, 0.0}},
        {1, 1, {-0.1, -0.2, -0.3}, {-huge_speed, 0.0, 0.0}},
    };
    const auto overflow = projection::project_centers(
        finite_but_overflowing,
        config,
        ProjectionCandidate::lumped_pic);
    MLS_REQUIRE_EQ(overflow.status, ProjectionStatus::numerical_overflow);
    MLS_REQUIRE_EQ(overflow.particles, finite_but_overflowing);
    MLS_REQUIRE_EQ(overflow.diagnostics.exact_mass_quanta_before, INT64_C(2));
    MLS_REQUIRE_EQ(overflow.diagnostics.exact_mass_quanta_after, INT64_C(2));
}

MLS_TEST("projection failed steps preserve unsorted center state byte-for-byte") {
    ProjectionLabState state{
        {1.0, {}, 1.0},
        PhysicalTimeScale{1, 40},
        3,
        {
            {9, 1, {0.1, 0.2, 0.3}, {1.0, 0.0, 0.0}},
            {2, 1, {-0.1, -0.2, -0.3}, {-1.0, 0.0, 0.0}},
        },
    };
    const auto before = state;
    const auto failed = projection::trapezoid_projection_step(
        state, ProjectionCandidate::full_consistent, 1, 1.0 / 40.0);
    MLS_REQUIRE_EQ(failed.projection.status, ProjectionStatus::structurally_rank_deficient);
    MLS_REQUIRE_EQ(failed.state, before);
    MLS_REQUIRE_EQ(failed.projection.particles, before.particles);
}

MLS_TEST("projection trapezoid step uses exact clock and has no numerical energy ledger") {
    auto state = checkpoint_state();
    state.elapsed_time_quanta = 0;
    const auto before = projection::serialize_projection_checkpoint(state);
    const auto step = projection::trapezoid_projection_step(
        state, ProjectionCandidate::lumped_pic, 4, 1.0 / 40.0);
    MLS_REQUIRE_EQ(step.projection.status, ProjectionStatus::solved);
    MLS_REQUIRE_EQ(step.state.elapsed_time_quanta, UINT64_C(4));
    MLS_REQUIRE(step.projection.numerical_projection_energy_residual_applicable);
    MLS_REQUIRE(std::abs(step.projection.numerical_projection_energy_residual_j) <= 1.0e-12);
    for (std::size_t index = 0; index < state.particles.size(); ++index) {
        const auto expected = state.particles[index].position_m +
            (1.0 / 40.0) * state.particles[index].velocity_m_per_s;
        const auto found = std::ranges::find(
            step.state.particles, state.particles[index].id, &CenterParticle::id);
        MLS_REQUIRE(found != step.state.particles.end());
        MLS_REQUIRE(close(found->position_m, expected, 2.0e-14));
    }
    MLS_REQUIRE(before == projection::serialize_projection_checkpoint(state));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        projection::trapezoid_projection_step(
            state, ProjectionCandidate::lumped_pic, 4, 0.026));
    state.elapsed_time_quanta = std::numeric_limits<std::uint64_t>::max() - 1U;
    const auto clock_overflow = projection::trapezoid_projection_step(
        state, ProjectionCandidate::lumped_pic, 4, 1.0 / 40.0);
    MLS_REQUIRE_EQ(clock_overflow.projection.status, ProjectionStatus::numerical_overflow);
    MLS_REQUIRE_EQ(clock_overflow.state, state);
}

MLS_TEST("projection checkpoint is canonical corruptible and excludes solver state") {
    const auto unsorted = checkpoint_state();
    const auto bytes = projection::serialize_projection_checkpoint(unsorted);
    const auto restored = projection::deserialize_projection_checkpoint(bytes);
    MLS_REQUIRE(std::ranges::is_sorted(restored.particles, {}, &CenterParticle::id));
    MLS_REQUIRE_EQ(projection::serialize_projection_checkpoint(restored), bytes);

    auto corrupt = bytes;
    corrupt[20] ^= 0x40U;
    MLS_REQUIRE(checkpoint_rejected(corrupt));
    auto truncated = bytes;
    truncated.pop_back();
    MLS_REQUIRE(checkpoint_rejected(truncated));
    auto version = bytes;
    write_little(
        version,
        std::size_t{8},
        projection::projection_checkpoint_format_version + 1U);
    refresh_checksum(version);
    MLS_REQUIRE(checkpoint_rejected(version));
    auto time_scale = bytes;
    write_little(time_scale, std::size_t{52}, UINT64_C(0));
    refresh_checksum(time_scale);
    MLS_REQUIRE(checkpoint_rejected(time_scale));

    constexpr std::size_t first_particle = 84;
    constexpr std::size_t particle_record_size = 64;
    auto noncanonical = bytes;
    for (std::size_t index = 0; index < particle_record_size; ++index) {
        std::swap(
            noncanonical[first_particle + index],
            noncanonical[first_particle + particle_record_size + index]);
    }
    refresh_checksum(noncanonical);
    MLS_REQUIRE(checkpoint_rejected(noncanonical));

    auto duplicate = bytes;
    for (std::size_t index = 0; index < sizeof(std::uint64_t); ++index) {
        duplicate[first_particle + particle_record_size + index] =
            duplicate[first_particle + index];
    }
    refresh_checksum(duplicate);
    MLS_REQUIRE(checkpoint_rejected(duplicate));

    auto nonfinite = bytes;
    write_little(
        nonfinite,
        first_particle + 2U * sizeof(std::uint64_t),
        UINT64_C(0x7ff8000000000000));
    refresh_checksum(nonfinite);
    MLS_REQUIRE(checkpoint_rejected(nonfinite));

    auto trailing = bytes;
    trailing.resize(trailing.size() - sizeof(std::uint64_t));
    trailing.push_back(0U);
    const auto trailing_hash = fnv1a(trailing);
    const auto old_size = trailing.size();
    trailing.resize(old_size + sizeof(std::uint64_t));
    write_little(trailing, old_size, trailing_hash);
    MLS_REQUIRE(checkpoint_rejected(trailing));
}

MLS_TEST("projection checkpoint restart reproduces continued center evolution exactly") {
    auto original = checkpoint_state();
    original.elapsed_time_quanta = 0;
    const auto first = projection::trapezoid_projection_step(
        original, ProjectionCandidate::fmpm_2, 2, 1.0 / 80.0);
    const auto restart_bytes = projection::serialize_projection_checkpoint(first.state);
    const auto restored = projection::deserialize_projection_checkpoint(restart_bytes);
    const auto continued_original = projection::trapezoid_projection_step(
        first.state, ProjectionCandidate::fmpm_2, 2, 1.0 / 80.0);
    const auto continued_restored = projection::trapezoid_projection_step(
        restored, ProjectionCandidate::fmpm_2, 2, 1.0 / 80.0);
    MLS_REQUIRE_EQ(
        projection::serialize_projection_checkpoint(continued_original.state),
        projection::serialize_projection_checkpoint(continued_restored.state));
}
