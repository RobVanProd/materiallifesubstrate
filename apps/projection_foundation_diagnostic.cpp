#include "mls/projection_foundation_lab.hpp"

#include <algorithm>
#include <atomic>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <locale>
#include <map>
#include <mutex>
#include <numbers>
#include <optional>
#include <ranges>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <tuple>
#include <utility>
#include <vector>

#ifndef MLS_CONFIGURED_SOURCE_SHA
#define MLS_CONFIGURED_SOURCE_SHA "unknown"
#endif
#ifndef MLS_CONFIGURED_SOURCE_BRANCH
#define MLS_CONFIGURED_SOURCE_BRANCH "unknown"
#endif
#ifndef MLS_CONFIGURED_SOURCE_DIRTY
#define MLS_CONFIGURED_SOURCE_DIRTY "true"
#endif
#ifndef MLS_CONFIGURED_COMPILER_ID
#define MLS_CONFIGURED_COMPILER_ID "unknown"
#endif
#ifndef MLS_CONFIGURED_COMPILER_VERSION
#define MLS_CONFIGURED_COMPILER_VERSION "unknown"
#endif

namespace {

namespace pf = mls::experimental::projection_foundation;
using mls::PhysicalTimeScale;
using mls::experimental::Matrix3d;
using mls::experimental::TransferConfig;
using mls::experimental::Vec3d;

constexpr std::uint64_t seed = 260828;
constexpr double domain_min_m = -0.5;
constexpr double domain_max_m = 0.5;
constexpr double density_kg_per_m3 = 1.0;
constexpr double kg_per_mass_quantum = 1.0 / 4096.0;
constexpr std::int64_t expected_mass_quanta = 4096;
constexpr std::uint64_t horizon_quanta = 4;
constexpr double time_quantum_s = 1.0 / 160.0;
constexpr double horizon_s = 1.0 / 40.0;
constexpr double u_ref_m_per_s = 2.5;
constexpr double cfl = 0.125;

constexpr double partition_tolerance = 5.0e-14;
constexpr double linear_reproduction_tolerance = 5.0e-13;
constexpr double symmetry_tolerance = 5.0e-15;
constexpr double row_sum_tolerance = 5.0e-13;
constexpr double grid_mass_tolerance = 2.0e-13;
constexpr double linear_tolerance = 2.0e-11;
constexpr double solve_tolerance = 5.0e-12;
constexpr double raw_condition_tolerance = 1.0e10;
constexpr double preconditioned_condition_tolerance = 1.0e8;
constexpr double affine_reconstruction_tolerance = 5.0e-10;
constexpr double affine_orbital_tolerance = 5.0e-10;
constexpr double fmpm_residual_tolerance = 5.0e-11;
constexpr double pic_identity_tolerance = 5.0e-13;
constexpr double affine_energy_diagnostic_tolerance = 5.0e-9;
constexpr double roundoff_guard = 5.0e-14;

constexpr std::string_view schema = "mls.projection-foundation.summary.v1";
constexpr std::string_view manifest_schema = "mls.projection-foundation.manifest.v1";
constexpr std::string_view exact_oracle_result_sha =
    "7f3119d609bf022fa31bfc5bf01a6c15189aaede7e35f9cfad13f4c275fae4bc";
constexpr std::string_view accepted_parent_sha =
    "aa084440fcd859b4f3416b21623cc3ac0c5b3e16";
constexpr std::string_view accepted_parent_tag = "moving-apic-limit-lab-evidence-v1";

enum class FieldKind : std::uint8_t {
    translation,
    rigid_rotation,
    general_affine,
    smooth_non_affine,
};

struct Options final {
    bool smoke{false};
    bool schema_audit{false};
    std::size_t jobs{1};
    std::filesystem::path output{"evidence/projection-foundation"};
};

struct Orientation final {
    std::string name{};
    Matrix3d matrix{};
};

struct Phase final {
    std::string name{};
    Vec3d fraction{};
};

struct FieldSpec final {
    FieldKind kind{FieldKind::translation};
    Matrix3d gradient_per_s{};
    Vec3d offset_m_per_s{};
};

struct Configuration final {
    std::string scope{};
    FieldKind field{FieldKind::translation};
    pf::ProjectionCandidate candidate{pf::ProjectionCandidate::lumped_pic};
    Phase phase{};
    Orientation orientation{};
    int level{0};
    double h_m{0.0};
    double dt_s{0.0};
    std::uint64_t dt_quanta{0};
    std::uint64_t steps{0};
    int cells_per_axis{0};
    int particles_per_axis{0};
    int particles_per_cell{0};
    double particle_spacing_m{0.0};
    std::int64_t mass_quanta_per_particle{0};
};

struct Totals final {
    double mass_kg{0.0};
    Vec3d linear{};
    Vec3d orbital{};
    double kinetic_j{0.0};
};

struct Trace final {
    pf::ProjectionLabState terminal{};
    pf::ProjectionStatus status{pf::ProjectionStatus::empty};
    pf::ProjectionStatus full_reference_status{pf::ProjectionStatus::empty};
    pf::ProjectionDiagnostics candidate_diagnostics{};
    pf::ProjectionDiagnostics full_reference_diagnostics{};
    bool full_reference_available{true};
    std::optional<double> grid_distance_full{};
    std::optional<double> particle_distance_full{};
    std::optional<double> affine_grid_representation_error{};
    std::optional<double> pic_identity_error{};
    double particle_reconstruction_error{0.0};
    std::optional<double> max_projection_residual{};
    std::optional<double> full_reference_max_projection_residual{};
    std::optional<double> max_fmpm_residual_identity{};
    std::optional<double> terminal_consistent_grid_energy_j{};
    std::optional<double> max_abs_numerical_projection_energy_residual_j{};
    std::uint64_t id_error_count{0};
    std::uint64_t nonfinite_count{0};
};

struct RawRow final {
    Configuration config{};
    Trace trace{};
    std::int64_t exact_mass_before{0};
    std::int64_t exact_mass_after{0};
    bool exact_mass_ok{false};
    bool exact_clock_ok{false};
    std::optional<double> material_velocity_error{};
    std::optional<double> trajectory_error{};
    std::optional<double> linear_momentum_error{};
    std::optional<double> orbital_angular_error{};
    std::optional<double> center_kinetic_relative_change{};
    bool checkpoint_roundtrip_ok{false};
    bool checkpoint_replay_ok{false};
    std::string initial_checkpoint_sha256{};
    std::string terminal_checkpoint_sha256{};
    std::vector<pf::CenterParticle> terminal_particles{};
};

struct SensitivityRow final {
    std::string kind{};
    std::string candidate{};
    std::string field{};
    std::string fixed_axis{};
    int level{0};
    std::string metric{};
    std::optional<double> value{};
    double hard_floor{0.0};
    double finest_ceiling{0.0};
    bool applicable{false};
};

struct ConvergenceRow final {
    std::string scope{};
    std::string candidate{};
    std::string field{};
    std::string phase{};
    std::string orientation{};
    std::string metric{};
    std::array<std::optional<double>, 3> errors{};
    double hard_floor{0.0};
    double finest_ceiling{0.0};
    bool pass{false};
    std::string reason{};
};

struct OrderRow final {
    std::string scope{};
    std::string field{};
    std::string phase{};
    std::string orientation{};
    int level{0};
    std::string metric{};
    std::array<std::optional<double>, 4> values{};
    bool applicable{false};
    bool pass{false};
    std::string reason{};
};

struct GateRow final {
    std::string scope{};
    std::string candidate{};
    std::string field{};
    std::string phase{};
    std::string orientation{};
    int level{0};
    std::string gate{};
    bool applicable{false};
    std::optional<double> value{};
    std::optional<double> tolerance{};
    bool pass{false};
};

[[nodiscard]] bool finite(Vec3d value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) && std::isfinite(value.z);
}

[[nodiscard]] Matrix3d matrix_inverse(const Matrix3d& matrix) {
    const auto& a = matrix.value;
    const auto determinant =
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) -
        a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) +
        a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]);
    const auto scale = std::max(1.0, mls::experimental::frobenius_norm(matrix));
    if (!std::isfinite(determinant) ||
        std::abs(determinant) <= 64.0 * std::numeric_limits<double>::epsilon() *
                scale * scale * scale) {
        throw std::domain_error("singular affine reference map");
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

[[nodiscard]] std::string_view field_name(FieldKind field) noexcept {
    switch (field) {
    case FieldKind::translation:
        return "translation";
    case FieldKind::rigid_rotation:
        return "rigid_rotation";
    case FieldKind::general_affine:
        return "general_affine";
    case FieldKind::smooth_non_affine:
        return "smooth_non_affine";
    }
    return "unknown";
}

[[nodiscard]] bool affine(FieldKind field) noexcept {
    return field != FieldKind::smooth_non_affine;
}

[[nodiscard]] std::array<FieldKind, 4> fields() noexcept {
    return {FieldKind::translation, FieldKind::rigid_rotation,
            FieldKind::general_affine, FieldKind::smooth_non_affine};
}

[[nodiscard]] std::array<pf::ProjectionCandidate, 6> candidates() noexcept {
    return {pf::ProjectionCandidate::lumped_pic,
            pf::ProjectionCandidate::full_consistent,
            pf::ProjectionCandidate::fmpm_1,
            pf::ProjectionCandidate::fmpm_2,
            pf::ProjectionCandidate::fmpm_3,
            pf::ProjectionCandidate::fmpm_4};
}

[[nodiscard]] bool fmpm(pf::ProjectionCandidate candidate) noexcept {
    return candidate == pf::ProjectionCandidate::fmpm_1 ||
        candidate == pf::ProjectionCandidate::fmpm_2 ||
        candidate == pf::ProjectionCandidate::fmpm_3 ||
        candidate == pf::ProjectionCandidate::fmpm_4;
}

[[nodiscard]] FieldSpec field_spec(FieldKind field) {
    FieldSpec result{};
    result.kind = field;
    switch (field) {
    case FieldKind::translation:
        result.offset_m_per_s = {9.0 / 20.0, -3.0 / 10.0, 1.0 / 5.0};
        break;
    case FieldKind::rigid_rotation: {
        const Vec3d omega{3.0 / 10.0, -1.0 / 5.0, 2.0 / 5.0};
        result.gradient_per_s.value =
            {{{0.0, -omega.z, omega.y},
              {omega.z, 0.0, -omega.x},
              {-omega.y, omega.x, 0.0}}};
        result.offset_m_per_s = {3.0 / 20.0, -1.0 / 10.0, 1.0 / 20.0};
        break;
    }
    case FieldKind::general_affine:
        result.gradient_per_s.value =
            {{{3.0 / 20.0, 2.0 / 5.0, 7.0 / 20.0},
              {1.0 / 4.0, -1.0 / 10.0, -11.0 / 20.0},
              {-3.0 / 10.0, 7.0 / 10.0, 1.0 / 5.0}}};
        result.offset_m_per_s = {111.0 / 125.0, -129.0 / 200.0, -74.0 / 125.0};
        break;
    case FieldKind::smooth_non_affine:
        break;
    }
    return result;
}

[[nodiscard]] Vec3d velocity_at(const FieldSpec& field, Vec3d position_m) noexcept {
    if (field.kind != FieldKind::smooth_non_affine) {
        return mls::experimental::multiply(field.gradient_per_s, position_m) +
            field.offset_m_per_s;
    }
    const auto pi = std::numbers::pi_v<double>;
    return {
        1.0 / 5.0 + 7.0 / 20.0 * std::sin(pi * position_m.y) *
            std::cos(pi * position_m.z),
        -3.0 / 20.0 + 3.0 / 10.0 * std::sin(pi * position_m.z) *
            std::cos(pi * position_m.x),
        1.0 / 10.0 + 1.0 / 4.0 * std::sin(pi * position_m.x) *
            std::cos(pi * position_m.y),
    };
}

[[nodiscard]] std::array<Phase, 2> phases() {
    return {Phase{"p000", {}}, Phase{"p049_001_083", {0.49, 0.01, 0.83}}};
}

[[nodiscard]] std::array<Orientation, 2> orientations() {
    return {
        Orientation{"p012_sppp", Matrix3d::identity()},
        Orientation{"p210_sppm",
                    Matrix3d{{{{0.0, 0.0, 1.0},
                               {0.0, 1.0, 0.0},
                               {-1.0, 0.0, 0.0}}}}},
    };
}

[[nodiscard]] Vec3d unorient(const Orientation& orientation, Vec3d value) noexcept {
    return mls::experimental::multiply(
        mls::experimental::transpose(orientation.matrix), value);
}

[[nodiscard]] FieldSpec oriented_field(FieldKind field, const Orientation& orientation) {
    auto source = field_spec(field);
    if (!affine(field)) {
        return source;
    }
    source.gradient_per_s = mls::experimental::multiply(
        mls::experimental::multiply(orientation.matrix, source.gradient_per_s),
        mls::experimental::transpose(orientation.matrix));
    source.offset_m_per_s =
        mls::experimental::multiply(orientation.matrix, source.offset_m_per_s);
    return source;
}

[[nodiscard]] FieldSpec convected_affine_field(const FieldSpec& initial, double time_s) {
    const auto inverse_map = matrix_inverse(
        Matrix3d::identity() + time_s * initial.gradient_per_s);
    auto result = initial;
    result.gradient_per_s =
        mls::experimental::multiply(initial.gradient_per_s, inverse_map);
    result.offset_m_per_s =
        mls::experimental::multiply(inverse_map, initial.offset_m_per_s);
    return result;
}

[[nodiscard]] double symmetric_relative(double lhs, double rhs) noexcept {
    return std::abs(lhs - rhs) / std::max({1.0, std::abs(lhs), std::abs(rhs)});
}

[[nodiscard]] double symmetric_relative(Vec3d lhs, Vec3d rhs) noexcept {
    return mls::experimental::norm(lhs - rhs) /
        std::max({1.0, mls::experimental::norm(lhs), mls::experimental::norm(rhs)});
}

[[nodiscard]] Totals totals(std::span<const pf::CenterParticle> particles) {
    Totals result{};
    for (const auto& particle : particles) {
        const auto mass = static_cast<double>(particle.mass_quanta) * kg_per_mass_quantum;
        const auto momentum = mass * particle.velocity_m_per_s;
        result.mass_kg += mass;
        result.linear += momentum;
        result.orbital += mls::experimental::cross(particle.position_m, momentum);
        result.kinetic_j += 0.5 * mass *
            mls::experimental::dot(particle.velocity_m_per_s,
                                   particle.velocity_m_per_s);
    }
    return result;
}

[[nodiscard]] std::int64_t exact_mass(std::span<const pf::CenterParticle> particles) {
    std::int64_t result = 0;
    for (const auto& particle : particles) {
        if (particle.mass_quanta <= 0 ||
            particle.mass_quanta > std::numeric_limits<std::int64_t>::max() - result) {
            throw std::overflow_error("projection evidence exact mass overflow");
        }
        result += particle.mass_quanta;
    }
    return result;
}

[[nodiscard]] std::uint64_t identity_error_count(
    std::span<const pf::CenterParticle> expected,
    std::span<const pf::CenterParticle> observed) {
    std::uint64_t errors = 0;
    std::map<std::uint64_t, std::int64_t> balance;
    for (const auto& particle : expected) {
        ++balance[particle.id];
    }
    for (const auto& particle : observed) {
        --balance[particle.id];
    }
    for (const auto& [id, count] : balance) {
        static_cast<void>(id);
        const auto magnitude = count < 0 ? -count : count;
        const auto increment = static_cast<std::uint64_t>(magnitude);
        if (increment > std::numeric_limits<std::uint64_t>::max() - errors) {
            return std::numeric_limits<std::uint64_t>::max();
        }
        errors += increment;
    }
    return errors;
}

[[nodiscard]] std::optional<double> particle_vector_rms(
    std::span<const pf::CenterParticle> actual,
    std::span<const pf::CenterParticle> initial,
    bool position,
    double elapsed_s) {
    if (actual.size() != initial.size()) {
        return std::nullopt;
    }
    long double error = 0.0L;
    long double reference = 0.0L;
    long double mass_sum = 0.0L;
    for (std::size_t index = 0; index < actual.size(); ++index) {
        if (actual[index].id != initial[index].id) {
            return std::nullopt;
        }
        const auto expected = position
            ? initial[index].position_m + elapsed_s * initial[index].velocity_m_per_s
            : initial[index].velocity_m_per_s;
        const auto observed = position ? actual[index].position_m
                                       : actual[index].velocity_m_per_s;
        const auto difference = observed - expected;
        const auto mass = static_cast<long double>(initial[index].mass_quanta) *
            static_cast<long double>(kg_per_mass_quantum);
        error += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        reference += mass * static_cast<long double>(mls::experimental::dot(expected, expected));
        mass_sum += mass;
    }
    if (!(mass_sum > 0.0L)) {
        return std::nullopt;
    }
    const auto numerator = std::sqrt(static_cast<double>(error / mass_sum));
    const auto denominator = std::max(
        1.0, std::sqrt(static_cast<double>(reference / mass_sum)));
    return numerator / denominator;
}

[[nodiscard]] double state_difference(
    std::span<const pf::CenterParticle> lhs,
    std::span<const pf::CenterParticle> rhs,
    bool position,
    const Orientation* unorient_lhs = nullptr,
    const Orientation* unorient_rhs = nullptr) {
    if (lhs.size() != rhs.size()) {
        throw std::logic_error("state comparison size mismatch");
    }
    long double numerator = 0.0L;
    long double denominator = 0.0L;
    long double mass_sum = 0.0L;
    for (std::size_t index = 0; index < lhs.size(); ++index) {
        if (lhs[index].id != rhs[index].id ||
            lhs[index].mass_quanta != rhs[index].mass_quanta) {
            throw std::logic_error("state comparison identity mismatch");
        }
        auto left = position ? lhs[index].position_m : lhs[index].velocity_m_per_s;
        auto right = position ? rhs[index].position_m : rhs[index].velocity_m_per_s;
        if (unorient_lhs != nullptr) {
            left = unorient(*unorient_lhs, left);
        }
        if (unorient_rhs != nullptr) {
            right = unorient(*unorient_rhs, right);
        }
        const auto difference = left - right;
        const auto mass = static_cast<long double>(lhs[index].mass_quanta) *
            static_cast<long double>(kg_per_mass_quantum);
        numerator += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        denominator += mass * static_cast<long double>(mls::experimental::dot(right, right));
        mass_sum += mass;
    }
    const auto error = std::sqrt(static_cast<double>(numerator / mass_sum));
    const auto scale = std::max(1.0, std::sqrt(static_cast<double>(denominator / mass_sum)));
    return error / scale;
}

[[nodiscard]] double grid_distance(
    const pf::ProjectionSystem& system,
    std::span<const Vec3d> actual,
    std::span<const Vec3d> reference) {
    if (actual.size() != reference.size() ||
        actual.size() != system.lumped_mass_kg().size()) {
        throw std::logic_error("grid distance size mismatch");
    }
    long double numerator = 0.0L;
    long double denominator = 0.0L;
    for (std::size_t index = 0; index < actual.size(); ++index) {
        const auto difference = actual[index] - reference[index];
        const auto mass = static_cast<long double>(system.lumped_mass_kg()[index]);
        numerator += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        denominator += mass * static_cast<long double>(
            mls::experimental::dot(reference[index], reference[index]));
    }
    return std::sqrt(static_cast<double>(numerator)) /
        std::max(1.0, std::sqrt(static_cast<double>(denominator)));
}

[[nodiscard]] double reconstructed_distance(
    std::span<const pf::CenterParticle> actual,
    std::span<const pf::CenterParticle> reference) {
    if (actual.size() != reference.size()) {
        throw std::logic_error("reconstructed distance size mismatch");
    }
    long double numerator = 0.0L;
    long double denominator = 0.0L;
    for (std::size_t index = 0; index < actual.size(); ++index) {
        const auto difference =
            actual[index].velocity_m_per_s - reference[index].velocity_m_per_s;
        const auto mass = static_cast<long double>(actual[index].mass_quanta) *
            static_cast<long double>(kg_per_mass_quantum);
        numerator += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        denominator += mass * static_cast<long double>(mls::experimental::dot(
            reference[index].velocity_m_per_s, reference[index].velocity_m_per_s));
    }
    return std::sqrt(static_cast<double>(numerator)) /
        std::max(1.0, std::sqrt(static_cast<double>(denominator)));
}

[[nodiscard]] double affine_grid_error(
    const pf::ProjectionSystem& system,
    std::span<const Vec3d> actual,
    const FieldSpec& field) {
    if (actual.size() != system.active_node_positions_m().size()) {
        throw std::logic_error("affine grid error size mismatch");
    }
    long double numerator = 0.0L;
    long double denominator = 0.0L;
    for (std::size_t index = 0; index < actual.size(); ++index) {
        const auto expected = velocity_at(field, system.active_node_positions_m()[index]);
        const auto difference = actual[index] - expected;
        const auto mass = static_cast<long double>(system.lumped_mass_kg()[index]);
        numerator += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        denominator += mass * static_cast<long double>(mls::experimental::dot(expected, expected));
    }
    return std::sqrt(static_cast<double>(numerator)) /
        std::max(1.0, std::sqrt(static_cast<double>(denominator)));
}

[[nodiscard]] std::vector<Configuration> configurations(bool smoke) {
    std::vector<Configuration> result;
    const std::array main_levels{
        std::tuple{0, 0.5, 1.0 / 40.0, UINT64_C(4), UINT64_C(1), 2, 4, 8,
                   1.0 / 4.0, INT64_C(64)},
        std::tuple{1, 0.25, 1.0 / 80.0, UINT64_C(2), UINT64_C(2), 4, 8, 8,
                   1.0 / 8.0, INT64_C(8)},
        std::tuple{2, 0.125, 1.0 / 160.0, UINT64_C(1), UINT64_C(4), 8, 16, 8,
                   1.0 / 16.0, INT64_C(1)},
    };
    if (smoke) {
        const auto [level, h, dt, dt_quanta, steps, cells, particles_axis, ppc,
                    spacing, mass] = main_levels.front();
        for (const auto candidate : candidates()) {
            result.push_back({
                "main", FieldKind::general_affine, candidate, phases().front(),
                orientations().front(), level, h, dt, dt_quanta, steps, cells,
                particles_axis, ppc, spacing, mass});
        }
        return result;
    }

    for (const auto field : fields()) {
        for (const auto candidate : candidates()) {
            for (const auto& phase : phases()) {
                for (const auto& orientation : orientations()) {
                    for (const auto& [level, h, dt, dt_quanta, steps, cells,
                                      particles_axis, ppc, spacing, mass] : main_levels) {
                        result.push_back({
                            "main", field, candidate, phase, orientation, level, h, dt,
                            dt_quanta, steps, cells, particles_axis, ppc, spacing, mass});
                    }
                }
            }
        }
    }

    const std::array ppc_levels{
        std::tuple{0, 1, 4, 1.0 / 4.0, INT64_C(64)},
        std::tuple{1, 8, 8, 1.0 / 8.0, INT64_C(8)},
        std::tuple{2, 64, 16, 1.0 / 16.0, INT64_C(1)},
    };
    for (const auto field : {FieldKind::general_affine, FieldKind::smooth_non_affine}) {
        for (const auto candidate : candidates()) {
            for (const auto& [level, ppc, particles_axis, spacing, mass] : ppc_levels) {
                result.push_back({
                    "ppc", field, candidate, phases()[1], orientations()[1], level,
                    0.25, 1.0 / 80.0, 2, 2, 4, particles_axis, ppc, spacing, mass});
            }
        }
    }
    return result;
}

[[nodiscard]] TransferConfig transfer_config(const Configuration& config) {
    const auto base_origin = config.h_m * config.phase.fraction;
    return {
        config.h_m,
        mls::experimental::multiply(config.orientation.matrix, base_origin),
        kg_per_mass_quantum,
    };
}

[[nodiscard]] pf::ProjectionLabState initial_state(const Configuration& config) {
    pf::ProjectionLabState state{};
    state.config = transfer_config(config);
    state.physical_time_scale = PhysicalTimeScale{1, 160};
    state.elapsed_time_quanta = 0;
    const auto source_field = field_spec(config.field);
    const auto count = static_cast<std::size_t>(config.particles_per_axis);
    state.particles.reserve(count * count * count);
    std::uint64_t id = 1;
    for (int ix = 0; ix < config.particles_per_axis; ++ix) {
        for (int iy = 0; iy < config.particles_per_axis; ++iy) {
            for (int iz = 0; iz < config.particles_per_axis; ++iz) {
                const Vec3d base_position{
                    domain_min_m + (static_cast<double>(ix) + 0.5) *
                        config.particle_spacing_m,
                    domain_min_m + (static_cast<double>(iy) + 0.5) *
                        config.particle_spacing_m,
                    domain_min_m + (static_cast<double>(iz) + 0.5) *
                        config.particle_spacing_m,
                };
                state.particles.push_back({
                    id++, config.mass_quanta_per_particle,
                    mls::experimental::multiply(config.orientation.matrix, base_position),
                    mls::experimental::multiply(
                        config.orientation.matrix,
                        velocity_at(source_field, base_position)),
                });
            }
        }
    }
    if (exact_mass(state.particles) != expected_mass_quanta) {
        throw std::logic_error("configuration does not contain exactly one kilogram");
    }
    return state;
}

void merge_diagnostics(pf::ProjectionDiagnostics& target,
                       const pf::ProjectionDiagnostics& source) {
    target.particle_count = std::max(target.particle_count, source.particle_count);
    target.active_node_count = std::max(target.active_node_count, source.active_node_count);
    target.shape_entry_count = std::max(target.shape_entry_count, source.shape_entry_count);
    target.matrix_nonzero_count =
        std::max(target.matrix_nonzero_count, source.matrix_nonzero_count);
    // Every rebuild of an identical active set must report the same canonical
    // ordering digest.  Keep the latest observation rather than folding it:
    // XOR would erase an even number of identical observations.
    if (source.node_order_digest != 0U) {
        target.node_order_digest = source.node_order_digest;
    }
    target.exact_mass_quanta_before = source.exact_mass_quanta_before;
    target.exact_mass_quanta_after = source.exact_mass_quanta_after;
    target.structural_rank_upper_bound = source.structural_rank_upper_bound;
    target.numerical_rank_estimate = source.numerical_rank_estimate;
    target.numerical_rank_method = source.numerical_rank_method;
    target.numerical_rank_is_estimated = source.numerical_rank_is_estimated;
    target.rank_certified = source.rank_certified;
    target.condition_estimated = source.condition_estimated;
    if (target.smallest_spectral_or_pivot_value == 0.0 ||
        (source.smallest_spectral_or_pivot_value > 0.0 &&
         source.smallest_spectral_or_pivot_value < target.smallest_spectral_or_pivot_value)) {
        target.smallest_spectral_or_pivot_value = source.smallest_spectral_or_pivot_value;
    }
    target.largest_spectral_or_pivot_value = std::max(
        target.largest_spectral_or_pivot_value, source.largest_spectral_or_pivot_value);
    target.raw_condition_estimate =
        std::max(target.raw_condition_estimate, source.raw_condition_estimate);
    target.preconditioned_condition_estimate = std::max(
        target.preconditioned_condition_estimate, source.preconditioned_condition_estimate);
    target.matrix_symmetry_relative_residual = std::max(
        target.matrix_symmetry_relative_residual,
        source.matrix_symmetry_relative_residual);
    target.row_sum_relative_residual =
        std::max(target.row_sum_relative_residual, source.row_sum_relative_residual);
    target.partition_unity_max_residual = std::max(
        target.partition_unity_max_residual, source.partition_unity_max_residual);
    target.linear_reproduction_max_residual_m = std::max(
        target.linear_reproduction_max_residual_m,
        source.linear_reproduction_max_residual_m);
    target.grid_mass_relative_error =
        std::max(target.grid_mass_relative_error, source.grid_mass_relative_error);
    for (std::size_t component = 0; component < 3; ++component) {
        if (source.solve_residual_applicable[component]) {
            const auto previously_applicable =
                target.solve_residual_applicable[component];
            target.solve_residual_applicable[component] = true;
            const auto preserve_max = [](double current, double observed,
                                         bool has_current) {
                if (!has_current) {
                    return observed;
                }
                if (!std::isfinite(current)) {
                    return current;
                }
                if (!std::isfinite(observed)) {
                    return observed;
                }
                return std::max(current, observed);
            };
            target.absolute_solve_residual[component] = preserve_max(
                target.absolute_solve_residual[component],
                source.absolute_solve_residual[component], previously_applicable);
            target.normalized_solve_residual[component] = preserve_max(
                target.normalized_solve_residual[component],
                source.normalized_solve_residual[component], previously_applicable);
        }
        target.component_iterations[component] = std::max(
            target.component_iterations[component], source.component_iterations[component]);
    }
    target.termination_reason = source.termination_reason;
}

void observe_optional_max(std::optional<double>& target, double observed) {
    if (target.has_value() && !std::isfinite(*target)) {
        return;
    }
    if (!std::isfinite(observed)) {
        target = observed;
        return;
    }
    if (!target.has_value()) {
        target = observed;
        return;
    }
    target = std::max(*target, observed);
}

void observe_solve_residual(
    std::optional<double>& target, const pf::ProjectionDiagnostics& diagnostics) {
    for (std::size_t component = 0; component < 3; ++component) {
        if (diagnostics.solve_residual_applicable[component]) {
            observe_optional_max(target, diagnostics.normalized_solve_residual[component]);
        }
    }
}

[[nodiscard]] bool solved(pf::ProjectionStatus status) noexcept {
    return status == pf::ProjectionStatus::solved || status == pf::ProjectionStatus::empty;
}

[[nodiscard]] std::optional<double> projection_particle_error(
    std::span<const pf::CenterParticle> projected,
    std::span<const pf::CenterParticle> material_reference) {
    if (projected.size() != material_reference.size()) {
        return std::nullopt;
    }
    long double error = 0.0L;
    long double reference = 0.0L;
    long double total_mass = 0.0L;
    for (std::size_t index = 0; index < projected.size(); ++index) {
        if (projected[index].id != material_reference[index].id ||
            projected[index].mass_quanta != material_reference[index].mass_quanta) {
            return std::nullopt;
        }
        const auto difference = projected[index].velocity_m_per_s -
            material_reference[index].velocity_m_per_s;
        const auto mass = static_cast<long double>(projected[index].mass_quanta) *
            static_cast<long double>(kg_per_mass_quantum);
        error += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        reference += mass * static_cast<long double>(mls::experimental::dot(
            material_reference[index].velocity_m_per_s,
            material_reference[index].velocity_m_per_s));
        total_mass += mass;
    }
    if (!(total_mass > 0.0L)) {
        return std::nullopt;
    }
    return std::sqrt(static_cast<double>(error / total_mass)) /
        std::max(1.0, std::sqrt(static_cast<double>(reference / total_mass)));
}

[[nodiscard]] Trace run_trace(
    const Configuration& config, const pf::ProjectionLabState& initial) {
    Trace trace{};
    trace.terminal = initial;
    trace.status = pf::ProjectionStatus::solved;
    trace.full_reference_status = pf::ProjectionStatus::solved;
    std::optional<double> max_grid_distance{};
    std::optional<double> max_particle_distance{};
    std::optional<double> max_affine_grid{};
    std::optional<double> max_pic_identity{};

    for (std::uint64_t step_index = 0; step_index < config.steps; ++step_index) {
        const auto system = pf::build_projection_system(
            trace.terminal.particles, trace.terminal.config);
        const auto full = pf::project_centers(
            system, pf::ProjectionCandidate::full_consistent);
        if (trace.full_reference_available) {
            trace.full_reference_status = full.status;
            merge_diagnostics(trace.full_reference_diagnostics, full.diagnostics);
            observe_solve_residual(
                trace.full_reference_max_projection_residual, full.diagnostics);
            if (!solved(full.status)) {
                trace.full_reference_available = false;
            }
        }

        const auto step = pf::trapezoid_projection_step(
            trace.terminal, config.candidate, config.dt_quanta, config.dt_s);
        trace.status = step.projection.status;
        merge_diagnostics(trace.candidate_diagnostics, step.projection.diagnostics);
        observe_solve_residual(
            trace.max_projection_residual, step.projection.diagnostics);
        if (step.projection.fmpm_residual_identity_applicable) {
            observe_optional_max(
                trace.max_fmpm_residual_identity,
                step.projection.fmpm_residual_identity_normalized);
        }
        trace.terminal_consistent_grid_energy_j =
            step.projection.consistent_grid_quadratic_energy_applicable
            ? std::optional<double>{step.projection.consistent_grid_quadratic_energy_j}
            : std::nullopt;
        if (step.projection.numerical_projection_energy_residual_applicable) {
            observe_optional_max(
                trace.max_abs_numerical_projection_energy_residual_j,
                std::abs(step.projection.numerical_projection_energy_residual_j));
        }

        if (solved(step.projection.status)) {
            const auto reconstruction = projection_particle_error(
                step.projection.particles, initial.particles);
            if (reconstruction.has_value()) {
                trace.particle_reconstruction_error = std::max(
                    trace.particle_reconstruction_error, *reconstruction);
            }
        }
        if (solved(full.status) && solved(step.projection.status)) {
            const auto grid_error = grid_distance(
                system, step.projection.grid_velocity_m_per_s,
                full.grid_velocity_m_per_s);
            const auto particle_error = reconstructed_distance(
                step.projection.particles, full.particles);
            max_grid_distance = std::max(max_grid_distance.value_or(0.0), grid_error);
            max_particle_distance =
                std::max(max_particle_distance.value_or(0.0), particle_error);
        }

        if (affine(config.field) && solved(step.projection.status)) {
            const auto elapsed_s = static_cast<double>(trace.terminal.elapsed_time_quanta) *
                time_quantum_s;
            const auto convected = convected_affine_field(
                oriented_field(config.field, config.orientation), elapsed_s);
            const auto error = affine_grid_error(
                system, step.projection.grid_velocity_m_per_s, convected);
            max_affine_grid = std::max(max_affine_grid.value_or(0.0), error);
        }

        if (config.candidate == pf::ProjectionCandidate::fmpm_1) {
            const auto pic = pf::project_centers(
                system, pf::ProjectionCandidate::lumped_pic);
            if (solved(pic.status) && solved(step.projection.status)) {
                const auto error = std::max(
                    grid_distance(system, step.projection.grid_velocity_m_per_s,
                                  pic.grid_velocity_m_per_s),
                    reconstructed_distance(step.projection.particles, pic.particles));
                max_pic_identity = std::max(max_pic_identity.value_or(0.0), error);
            }
        }

        trace.terminal = step.state;
        if (!solved(step.projection.status)) {
            break;
        }
    }
    trace.grid_distance_full =
        trace.full_reference_available ? max_grid_distance : std::nullopt;
    trace.particle_distance_full =
        trace.full_reference_available ? max_particle_distance : std::nullopt;
    trace.affine_grid_representation_error = max_affine_grid;
    trace.pic_identity_error = max_pic_identity;

    trace.id_error_count = identity_error_count(
        initial.particles, trace.terminal.particles);
    for (const auto& particle : trace.terminal.particles) {
        if (!finite(particle.position_m) || !finite(particle.velocity_m_per_s)) {
            ++trace.nonfinite_count;
        }
    }
    return trace;
}

[[nodiscard]] constexpr std::uint32_t rotate_right(
    std::uint32_t value, unsigned count) noexcept {
    return (value >> count) | (value << (32U - count));
}

[[nodiscard]] std::string sha256(std::string_view input) {
    constexpr std::array<std::uint32_t, 64> constants{
        0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U,
        0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
        0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U,
        0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
        0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
        0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
        0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U,
        0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
        0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U,
        0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
        0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U,
        0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
        0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U,
        0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
        0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
        0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U};
    std::vector<std::uint8_t> bytes(input.begin(), input.end());
    const auto bit_length = static_cast<std::uint64_t>(bytes.size()) * 8U;
    bytes.push_back(0x80U);
    while ((bytes.size() % 64U) != 56U) {
        bytes.push_back(0U);
    }
    for (int shift = 56; shift >= 0; shift -= 8) {
        bytes.push_back(static_cast<std::uint8_t>(bit_length >> shift));
    }
    std::array<std::uint32_t, 8> hash{
        0x6a09e667U, 0xbb67ae85U, 0x3c6ef372U, 0xa54ff53aU,
        0x510e527fU, 0x9b05688cU, 0x1f83d9abU, 0x5be0cd19U};
    for (std::size_t offset = 0; offset < bytes.size(); offset += 64U) {
        std::array<std::uint32_t, 64> words{};
        for (std::size_t index = 0; index < 16U; ++index) {
            const auto base = offset + 4U * index;
            words[index] = (static_cast<std::uint32_t>(bytes[base]) << 24U) |
                (static_cast<std::uint32_t>(bytes[base + 1U]) << 16U) |
                (static_cast<std::uint32_t>(bytes[base + 2U]) << 8U) |
                static_cast<std::uint32_t>(bytes[base + 3U]);
        }
        for (std::size_t index = 16; index < 64U; ++index) {
            const auto s0 = rotate_right(words[index - 15U], 7U) ^
                rotate_right(words[index - 15U], 18U) ^ (words[index - 15U] >> 3U);
            const auto s1 = rotate_right(words[index - 2U], 17U) ^
                rotate_right(words[index - 2U], 19U) ^ (words[index - 2U] >> 10U);
            words[index] = words[index - 16U] + s0 + words[index - 7U] + s1;
        }
        auto [a, b, c, d, e, f, g, h] = hash;
        for (std::size_t index = 0; index < 64U; ++index) {
            const auto s1 = rotate_right(e, 6U) ^ rotate_right(e, 11U) ^
                rotate_right(e, 25U);
            const auto choose = (e & f) ^ ((~e) & g);
            const auto temporary1 = h + s1 + choose + constants[index] + words[index];
            const auto s0 = rotate_right(a, 2U) ^ rotate_right(a, 13U) ^
                rotate_right(a, 22U);
            const auto majority = (a & b) ^ (a & c) ^ (b & c);
            const auto temporary2 = s0 + majority;
            h = g;
            g = f;
            f = e;
            e = d + temporary1;
            d = c;
            c = b;
            b = a;
            a = temporary1 + temporary2;
        }
        hash[0] += a;
        hash[1] += b;
        hash[2] += c;
        hash[3] += d;
        hash[4] += e;
        hash[5] += f;
        hash[6] += g;
        hash[7] += h;
    }
    std::ostringstream output;
    output.imbue(std::locale::classic());
    output << std::hex << std::setfill('0');
    for (const auto word : hash) {
        output << std::setw(8) << word;
    }
    return output.str();
}

[[nodiscard]] std::string checkpoint_hash(std::span<const std::uint8_t> bytes) {
    return sha256(std::string_view(
        reinterpret_cast<const char*>(bytes.data()), bytes.size()));
}

[[nodiscard]] RawRow run_configuration(const Configuration& config) {
    RawRow row{};
    row.config = config;
    const auto initial = initial_state(config);
    row.exact_mass_before = exact_mass(initial.particles);
    const auto initial_checkpoint = pf::serialize_projection_checkpoint(initial);
    const auto restored = pf::deserialize_projection_checkpoint(initial_checkpoint);
    row.checkpoint_roundtrip_ok =
        pf::serialize_projection_checkpoint(restored) == initial_checkpoint;
    row.initial_checkpoint_sha256 = checkpoint_hash(initial_checkpoint);

    row.trace = run_trace(config, initial);
    const auto replay = run_trace(config, restored);
    const auto terminal_checkpoint =
        pf::serialize_projection_checkpoint(row.trace.terminal);
    const auto replay_checkpoint = pf::serialize_projection_checkpoint(replay.terminal);
    row.checkpoint_replay_ok = terminal_checkpoint == replay_checkpoint;
    row.terminal_checkpoint_sha256 = checkpoint_hash(terminal_checkpoint);
    row.exact_mass_after = exact_mass(row.trace.terminal.particles);
    row.exact_mass_ok = row.exact_mass_before == expected_mass_quanta &&
        row.exact_mass_after == expected_mass_quanta;
    row.exact_clock_ok =
        row.trace.terminal.elapsed_time_quanta == horizon_quanta;
    if (row.trace.id_error_count == 0U) {
        row.material_velocity_error = particle_vector_rms(
            row.trace.terminal.particles, initial.particles, false, horizon_s);
        row.trajectory_error = particle_vector_rms(
            row.trace.terminal.particles, initial.particles, true, horizon_s);
        const auto before = totals(initial.particles);
        const auto after = totals(row.trace.terminal.particles);
        row.linear_momentum_error = symmetric_relative(after.linear, before.linear);
        row.orbital_angular_error = symmetric_relative(after.orbital, before.orbital);
        row.center_kinetic_relative_change =
            symmetric_relative(after.kinetic_j, before.kinetic_j);
    }
    row.terminal_particles = row.trace.terminal.particles;
    return row;
}

[[nodiscard]] std::string format_double(double value) {
    if (std::isnan(value)) {
        return "NAN";
    }
    if (value == std::numeric_limits<double>::infinity()) {
        return "INF";
    }
    if (value == -std::numeric_limits<double>::infinity()) {
        return "-INF";
    }
    if (value == 0.0) {
        value = 0.0;
    }
    std::ostringstream output;
    output.imbue(std::locale::classic());
    output << std::setprecision(std::numeric_limits<double>::max_digits10)
           << std::scientific << value;
    return output.str();
}

[[nodiscard]] std::string format_optional(const std::optional<double>& value) {
    return value.has_value() ? format_double(*value) : "NA";
}

[[nodiscard]] std::string bool_text(bool value) {
    return value ? "true" : "false";
}

[[nodiscard]] std::string csv_escape(std::string_view value) {
    if (value.find_first_of(",\"\r\n") == std::string_view::npos) {
        return std::string(value);
    }
    std::string result{"\""};
    for (const auto character : value) {
        if (character == '\"') {
            result.push_back('\"');
        }
        result.push_back(character);
    }
    result.push_back('\"');
    return result;
}

class Csv final {
public:
    explicit Csv(std::string_view header) {
        contents_.append(header);
        contents_.push_back('\n');
    }

    void row(std::initializer_list<std::string> values) {
        bool first = true;
        for (const auto& value : values) {
            if (!first) {
                contents_.push_back(',');
            }
            first = false;
            contents_.append(csv_escape(value));
        }
        contents_.push_back('\n');
        ++rows_;
    }

    void write(const std::filesystem::path& path) const {
        std::ofstream stream(path, std::ios::binary | std::ios::trunc);
        if (!stream) {
            throw std::runtime_error("cannot create evidence file: " + path.string());
        }
        stream.write(contents_.data(), static_cast<std::streamsize>(contents_.size()));
        if (!stream) {
            throw std::runtime_error("cannot write evidence file: " + path.string());
        }
    }

    [[nodiscard]] std::size_t rows() const noexcept { return rows_; }
    [[nodiscard]] const std::string& contents() const noexcept { return contents_; }

private:
    std::string contents_{};
    std::size_t rows_{0};
};

[[nodiscard]] const RawRow& find_raw(
    const std::vector<RawRow>& rows,
    std::string_view scope,
    pf::ProjectionCandidate candidate,
    FieldKind field,
    std::string_view phase,
    std::string_view orientation,
    int level) {
    const auto found = std::ranges::find_if(rows, [&](const RawRow& row) {
        return row.config.scope == scope && row.config.candidate == candidate &&
            row.config.field == field && row.config.phase.name == phase &&
            row.config.orientation.name == orientation && row.config.level == level;
    });
    if (found == rows.end()) {
        throw std::logic_error("missing raw evidence row");
    }
    return *found;
}

constexpr std::string_view raw_header =
    "mode,seed,scope,candidate,field,phase,orientation,level,h_m,dt_s,dt_quanta,steps,"
    "cells_per_axis,particles_per_axis,particle_count,particles_per_cell,particle_spacing_m,"
    "mass_quanta_per_particle,kg_per_mass_quantum,expected_mass_quanta,exact_mass_before,"
    "exact_mass_after,expected_elapsed_quanta,observed_elapsed_quanta,exact_mass_ok,"
    "exact_clock_ok,status,full_reference_status,full_reference_available,"
    "candidate_solve_residual_applicable,full_reference_solve_residual_applicable,"
    "particle_count_diag,"
    "active_node_count,shape_entry_count,matrix_nonzero_count,node_order_digest,"
    "structural_rank_upper_bound,numerical_rank_estimate,numerical_rank_method,"
    "numerical_rank_is_estimated,rank_certified,condition_estimated,"
    "smallest_spectral_or_pivot_value,"
    "largest_spectral_or_pivot_value,raw_condition_estimate,"
    "preconditioned_condition_estimate,matrix_symmetry_relative_residual,"
    "row_sum_relative_residual,partition_unity_max_residual,"
    "linear_reproduction_max_residual_m,grid_mass_relative_error,"
    "max_projection_residual,full_reference_max_projection_residual,"
    "fmpm_residual_identity_applicable,fmpm_residual_identity,material_velocity_error,"
    "trajectory_error,linear_momentum_error,orbital_angular_error,"
    "center_kinetic_relative_change,consistent_grid_quadratic_energy_applicable,"
    "consistent_grid_quadratic_energy_j,numerical_projection_energy_residual_applicable,"
    "max_abs_numerical_projection_energy_residual_j,"
    "particle_reconstruction_error,affine_grid_representation_error,"
    "grid_distance_full,particle_distance_full,pic_identity_error,id_error_count,"
    "nonfinite_count,candidate_termination_reason,full_reference_termination_reason,"
    "checkpoint_roundtrip_ok,checkpoint_replay_ok,"
    "initial_checkpoint_sha256,terminal_checkpoint_sha256";

void write_raw_row(Csv& csv, const RawRow& row, bool smoke) {
    const auto& config = row.config;
    const auto& trace = row.trace;
    const auto& diagnostics = trace.full_reference_diagnostics;
    csv.row({
        smoke ? "smoke" : "full",
        std::to_string(seed),
        config.scope,
        std::string(pf::candidate_name(config.candidate)),
        std::string(field_name(config.field)),
        config.phase.name,
        config.orientation.name,
        std::to_string(config.level),
        format_double(config.h_m),
        format_double(config.dt_s),
        std::to_string(config.dt_quanta),
        std::to_string(config.steps),
        std::to_string(config.cells_per_axis),
        std::to_string(config.particles_per_axis),
        std::to_string(config.particles_per_axis * config.particles_per_axis *
                       config.particles_per_axis),
        std::to_string(config.particles_per_cell),
        format_double(config.particle_spacing_m),
        std::to_string(config.mass_quanta_per_particle),
        format_double(kg_per_mass_quantum),
        std::to_string(expected_mass_quanta),
        std::to_string(row.exact_mass_before),
        std::to_string(row.exact_mass_after),
        std::to_string(horizon_quanta),
        std::to_string(trace.terminal.elapsed_time_quanta),
        bool_text(row.exact_mass_ok),
        bool_text(row.exact_clock_ok),
        std::string(pf::status_name(trace.status)),
        std::string(pf::status_name(trace.full_reference_status)),
        bool_text(trace.full_reference_available),
        bool_text(trace.max_projection_residual.has_value()),
        bool_text(trace.full_reference_max_projection_residual.has_value()),
        std::to_string(diagnostics.particle_count),
        std::to_string(diagnostics.active_node_count),
        std::to_string(diagnostics.shape_entry_count),
        std::to_string(diagnostics.matrix_nonzero_count),
        std::to_string(diagnostics.node_order_digest),
        std::to_string(diagnostics.structural_rank_upper_bound),
        std::to_string(diagnostics.numerical_rank_estimate),
        diagnostics.numerical_rank_method,
        bool_text(diagnostics.numerical_rank_is_estimated),
        bool_text(diagnostics.rank_certified),
        bool_text(diagnostics.condition_estimated),
        format_double(diagnostics.smallest_spectral_or_pivot_value),
        format_double(diagnostics.largest_spectral_or_pivot_value),
        format_double(diagnostics.raw_condition_estimate),
        format_double(diagnostics.preconditioned_condition_estimate),
        format_double(diagnostics.matrix_symmetry_relative_residual),
        format_double(diagnostics.row_sum_relative_residual),
        format_double(diagnostics.partition_unity_max_residual),
        format_double(diagnostics.linear_reproduction_max_residual_m),
        format_double(diagnostics.grid_mass_relative_error),
        format_optional(trace.max_projection_residual),
        format_optional(trace.full_reference_max_projection_residual),
        bool_text(trace.max_fmpm_residual_identity.has_value()),
        format_optional(trace.max_fmpm_residual_identity),
        format_optional(row.material_velocity_error),
        format_optional(row.trajectory_error),
        format_optional(row.linear_momentum_error),
        format_optional(row.orbital_angular_error),
        format_optional(row.center_kinetic_relative_change),
        bool_text(trace.terminal_consistent_grid_energy_j.has_value()),
        format_optional(trace.terminal_consistent_grid_energy_j),
        bool_text(trace.max_abs_numerical_projection_energy_residual_j.has_value()),
        format_optional(trace.max_abs_numerical_projection_energy_residual_j),
        format_double(trace.particle_reconstruction_error),
        format_optional(trace.affine_grid_representation_error),
        format_optional(trace.grid_distance_full),
        format_optional(trace.particle_distance_full),
        format_optional(trace.pic_identity_error),
        std::to_string(trace.id_error_count),
        std::to_string(trace.nonfinite_count),
        trace.candidate_diagnostics.termination_reason,
        trace.full_reference_diagnostics.termination_reason,
        bool_text(row.checkpoint_roundtrip_ok),
        bool_text(row.checkpoint_replay_ok),
        row.initial_checkpoint_sha256,
        row.terminal_checkpoint_sha256,
    });
}

[[nodiscard]] std::optional<double> raw_metric(
    const RawRow& row, std::string_view metric);

[[nodiscard]] std::vector<SensitivityRow> phase_sensitivity(
    const std::vector<RawRow>& rows, bool smoke) {
    std::vector<SensitivityRow> result;
    if (smoke) {
        return result;
    }
    for (const auto candidate : candidates()) {
        for (const auto field : fields()) {
            for (const auto& orientation : orientations()) {
                for (int level = 0; level < 3; ++level) {
                    const auto& first = find_raw(
                        rows, "main", candidate, field, "p000", orientation.name, level);
                    const auto& second = find_raw(
                        rows, "main", candidate, field, "p049_001_083",
                        orientation.name, level);
                    const auto applicable = solved(first.trace.status) &&
                        solved(second.trace.status) && first.trace.id_error_count == 0U &&
                        second.trace.id_error_count == 0U;
                    for (const auto position : {false, true}) {
                        result.push_back({
                            "phase", std::string(pf::candidate_name(candidate)),
                            std::string(field_name(field)), orientation.name, level,
                            position ? "trajectory" : "material_velocity",
                            applicable ? std::optional<double>{state_difference(
                                first.terminal_particles, second.terminal_particles,
                                position)} : std::nullopt,
                            5.0e-10, 5.0e-3, applicable});
                    }
                    if (fmpm(candidate)) {
                        for (const auto metric : {
                                 std::string_view{"grid_distance_full"},
                                 std::string_view{"particle_distance_full"}}) {
                            const auto first_value = raw_metric(first, metric);
                            const auto second_value = raw_metric(second, metric);
                            const auto distance_applicable = applicable &&
                                first_value.has_value() && second_value.has_value();
                            result.push_back({
                                "phase", std::string(pf::candidate_name(candidate)),
                                std::string(field_name(field)), orientation.name, level,
                                std::string(metric),
                                distance_applicable
                                    ? std::optional<double>{std::abs(
                                          *first_value - *second_value)}
                                    : std::nullopt,
                                5.0e-10, 5.0e-3, distance_applicable});
                        }
                    }
                }
            }
        }
    }
    return result;
}

[[nodiscard]] std::vector<SensitivityRow> orientation_sensitivity(
    const std::vector<RawRow>& rows, bool smoke) {
    std::vector<SensitivityRow> result;
    if (smoke) {
        return result;
    }
    const auto orientation_values = orientations();
    for (const auto candidate : candidates()) {
        for (const auto field : fields()) {
            for (const auto& phase : phases()) {
                for (int level = 0; level < 3; ++level) {
                    const auto& first = find_raw(
                        rows, "main", candidate, field, phase.name,
                        orientation_values[0].name, level);
                    const auto& second = find_raw(
                        rows, "main", candidate, field, phase.name,
                        orientation_values[1].name, level);
                    const auto applicable = solved(first.trace.status) &&
                        solved(second.trace.status) && first.trace.id_error_count == 0U &&
                        second.trace.id_error_count == 0U;
                    for (const auto position : {false, true}) {
                        result.push_back({
                            "orientation", std::string(pf::candidate_name(candidate)),
                            std::string(field_name(field)), phase.name, level,
                            position ? "trajectory" : "material_velocity",
                            applicable ? std::optional<double>{state_difference(
                                first.terminal_particles, second.terminal_particles, position,
                                &orientation_values[0], &orientation_values[1])} : std::nullopt,
                            5.0e-10, 5.0e-3, applicable});
                    }
                    if (fmpm(candidate)) {
                        for (const auto metric : {
                                 std::string_view{"grid_distance_full"},
                                 std::string_view{"particle_distance_full"}}) {
                            const auto first_value = raw_metric(first, metric);
                            const auto second_value = raw_metric(second, metric);
                            const auto distance_applicable = applicable &&
                                first_value.has_value() && second_value.has_value();
                            result.push_back({
                                "orientation",
                                std::string(pf::candidate_name(candidate)),
                                std::string(field_name(field)), phase.name, level,
                                std::string(metric),
                                distance_applicable
                                    ? std::optional<double>{std::abs(
                                          *first_value - *second_value)}
                                    : std::nullopt,
                                5.0e-10, 5.0e-3, distance_applicable});
                        }
                    }
                }
            }
        }
    }
    return result;
}

constexpr std::string_view sensitivity_header =
    "mode,seed,kind,candidate,field,fixed_axis,level,metric,value,hard_floor,"
    "finest_ceiling,applicable";

void write_sensitivity_row(Csv& csv, const SensitivityRow& row, bool smoke) {
    csv.row({
        smoke ? "smoke" : "full", std::to_string(seed), row.kind, row.candidate,
        row.field, row.fixed_axis, std::to_string(row.level), row.metric,
        format_optional(row.value), format_double(row.hard_floor),
        format_double(row.finest_ceiling), bool_text(row.applicable),
    });
}

[[nodiscard]] std::pair<double, double> metric_tolerances(
    FieldKind field, std::string_view metric) {
    if (metric == "material_velocity") {
        return field == FieldKind::smooth_non_affine
            ? std::pair{2.0e-8, 2.0e-2}
            : std::pair{5.0e-10, 5.0e-8};
    }
    if (metric == "trajectory") {
        return field == FieldKind::smooth_non_affine
            ? std::pair{2.0e-8, 2.0e-3}
            : std::pair{5.0e-10, 5.0e-8};
    }
    if (metric == "linear_momentum") {
        return {2.0e-11, 2.0e-9};
    }
    if (metric == "orbital_angular") {
        return {5.0e-10, 5.0e-5};
    }
    if (metric == "grid_distance_full" || metric == "particle_distance_full") {
        return {5.0e-10, 2.0e-2};
    }
    throw std::logic_error("unknown convergence metric");
}

[[nodiscard]] std::optional<double> raw_metric(
    const RawRow& row, std::string_view metric) {
    if (!solved(row.trace.status)) {
        return std::nullopt;
    }
    if (metric == "material_velocity") {
        return row.material_velocity_error;
    }
    if (metric == "trajectory") {
        return row.trajectory_error;
    }
    if (metric == "linear_momentum") {
        return row.linear_momentum_error;
    }
    if (metric == "orbital_angular") {
        return row.orbital_angular_error;
    }
    if (metric == "grid_distance_full") {
        return row.trace.grid_distance_full;
    }
    if (metric == "particle_distance_full") {
        return row.trace.particle_distance_full;
    }
    throw std::logic_error("unknown raw metric");
}

void decide_convergence(ConvergenceRow& row) {
    if (std::ranges::any_of(row.errors, [](const auto& value) {
            return !value.has_value() || !std::isfinite(*value) || *value < 0.0;
        })) {
        row.pass = false;
        row.reason = "missing_failed_or_nonfinite_level";
        return;
    }
    const auto e0 = *row.errors[0];
    const auto e1 = *row.errors[1];
    const auto e2 = *row.errors[2];
    if (e0 <= row.hard_floor && e1 <= row.hard_floor && e2 <= row.hard_floor) {
        row.pass = true;
        row.reason = "all_below_hard_floor";
        return;
    }
    const auto contraction =
        e1 <= 0.80 * e0 + roundoff_guard &&
        e2 <= 0.80 * e1 + roundoff_guard &&
        e2 <= 0.40 * e0 + roundoff_guard && e2 <= row.finest_ceiling;
    row.pass = contraction;
    row.reason = contraction ? "contraction_and_finest_ceiling"
                             : "convergence_rule_failed";
}

[[nodiscard]] std::vector<ConvergenceRow> convergence_rows(
    const std::vector<RawRow>& rows,
    const std::vector<SensitivityRow>& phase_rows,
    const std::vector<SensitivityRow>& orientation_rows,
    bool smoke) {
    std::vector<ConvergenceRow> result;
    if (smoke) {
        return result;
    }
    constexpr std::array<std::string_view, 4> base_metrics{
        "material_velocity", "trajectory", "linear_momentum", "orbital_angular"};
    constexpr std::array<std::string_view, 2> distance_metrics{
        "grid_distance_full", "particle_distance_full"};

    for (const auto candidate : candidates()) {
        for (const auto field : fields()) {
            for (const auto& phase : phases()) {
                for (const auto& orientation : orientations()) {
                    for (const auto metric : base_metrics) {
                        const auto [floor, ceiling] = metric_tolerances(field, metric);
                        ConvergenceRow row{
                            "main", std::string(pf::candidate_name(candidate)),
                            std::string(field_name(field)), phase.name, orientation.name,
                            std::string(metric), {}, floor, ceiling, false, {}};
                        for (int level = 0; level < 3; ++level) {
                            row.errors[static_cast<std::size_t>(level)] = raw_metric(
                                find_raw(rows, "main", candidate, field, phase.name,
                                         orientation.name, level), metric);
                        }
                        decide_convergence(row);
                        result.push_back(std::move(row));
                    }
                    if (fmpm(candidate)) {
                        for (const auto metric : distance_metrics) {
                            const auto [floor, ceiling] = metric_tolerances(field, metric);
                            ConvergenceRow row{
                                "main", std::string(pf::candidate_name(candidate)),
                                std::string(field_name(field)), phase.name,
                                orientation.name, std::string(metric), {}, floor, ceiling,
                                false, {}};
                            for (int level = 0; level < 3; ++level) {
                                row.errors[static_cast<std::size_t>(level)] = raw_metric(
                                    find_raw(rows, "main", candidate, field, phase.name,
                                             orientation.name, level), metric);
                            }
                            decide_convergence(row);
                            result.push_back(std::move(row));
                        }
                    }
                }
            }
        }
    }

    for (const auto candidate : candidates()) {
        for (const auto field : {FieldKind::general_affine, FieldKind::smooth_non_affine}) {
            for (const auto metric : base_metrics) {
                const auto [floor, ceiling] = metric_tolerances(field, metric);
                ConvergenceRow row{
                    "ppc", std::string(pf::candidate_name(candidate)),
                    std::string(field_name(field)), "p049_001_083", "p210_sppm",
                    std::string(metric), {}, floor, ceiling, false, {}};
                for (int level = 0; level < 3; ++level) {
                    row.errors[static_cast<std::size_t>(level)] = raw_metric(
                        find_raw(rows, "ppc", candidate, field, "p049_001_083",
                                 "p210_sppm", level), metric);
                }
                decide_convergence(row);
                result.push_back(std::move(row));
            }
            if (fmpm(candidate)) {
                for (const auto metric : distance_metrics) {
                    const auto [floor, ceiling] = metric_tolerances(field, metric);
                    ConvergenceRow row{
                        "ppc", std::string(pf::candidate_name(candidate)),
                        std::string(field_name(field)), "p049_001_083", "p210_sppm",
                        std::string(metric), {}, floor, ceiling, false, {}};
                    for (int level = 0; level < 3; ++level) {
                        row.errors[static_cast<std::size_t>(level)] = raw_metric(
                            find_raw(rows, "ppc", candidate, field, "p049_001_083",
                                     "p210_sppm", level), metric);
                    }
                    decide_convergence(row);
                    result.push_back(std::move(row));
                }
            }
        }
    }

    const auto add_sensitivity = [&](const std::vector<SensitivityRow>& source) {
        std::map<std::tuple<std::string, std::string, std::string, std::string>,
                 std::array<std::optional<double>, 3>> groups;
        for (const auto& row : source) {
            groups[{row.candidate, row.field, row.fixed_axis, row.metric}]
                  [static_cast<std::size_t>(row.level)] = row.value;
        }
        for (const auto& [key, errors] : groups) {
            const auto& [candidate, field, fixed_axis, metric] = key;
            ConvergenceRow row{
                source.empty() ? "unknown_sensitivity" : source.front().kind,
                candidate, field,
                source.empty() || source.front().kind != "orientation" ? "phase_pair"
                                                                       : fixed_axis,
                source.empty() || source.front().kind != "phase" ? "orientation_pair"
                                                                  : fixed_axis,
                metric, errors, 5.0e-10, 5.0e-3, false, {}};
            decide_convergence(row);
            result.push_back(std::move(row));
        }
    };
    add_sensitivity(phase_rows);
    add_sensitivity(orientation_rows);
    return result;
}

constexpr std::string_view convergence_header =
    "mode,seed,scope,candidate,field,phase,orientation,metric,error_level_0,"
    "error_level_1,error_level_2,hard_floor,finest_ceiling,contraction_01,"
    "contraction_12,endpoint_contraction,pass,reason";

void write_convergence_row(Csv& csv, const ConvergenceRow& row, bool smoke) {
    const auto ratio = [](const std::optional<double>& next,
                          const std::optional<double>& previous) -> std::optional<double> {
        if (!next.has_value() || !previous.has_value()) {
            return std::nullopt;
        }
        if (*previous == 0.0) {
            return *next == 0.0 ? std::optional<double>{0.0} : std::nullopt;
        }
        return *next / *previous;
    };
    csv.row({
        smoke ? "smoke" : "full", std::to_string(seed), row.scope, row.candidate,
        row.field, row.phase, row.orientation, row.metric,
        format_optional(row.errors[0]), format_optional(row.errors[1]),
        format_optional(row.errors[2]), format_double(row.hard_floor),
        format_double(row.finest_ceiling),
        format_optional(ratio(row.errors[1], row.errors[0])),
        format_optional(ratio(row.errors[2], row.errors[1])),
        format_optional(ratio(row.errors[2], row.errors[0])), bool_text(row.pass),
        row.reason,
    });
}

[[nodiscard]] std::vector<OrderRow> order_rows(
    const std::vector<RawRow>& rows, bool smoke) {
    std::vector<OrderRow> result;
    const auto make_for = [&](std::string_view scope, FieldKind field,
                              std::string_view phase, std::string_view orientation,
                              int level) {
        for (const auto metric : {std::string_view{"grid_distance_full"},
                                  std::string_view{"particle_distance_full"}}) {
            OrderRow row{
                std::string(scope), std::string(field_name(field)), std::string(phase),
                std::string(orientation), level, std::string(metric), {}, false, false, {}};
            for (int order = 0; order < 4; ++order) {
                const auto candidate = static_cast<pf::ProjectionCandidate>(
                    static_cast<int>(pf::ProjectionCandidate::fmpm_1) + order);
                const auto& raw = find_raw(
                    rows, scope, candidate, field, phase, orientation, level);
                row.values[static_cast<std::size_t>(order)] = raw_metric(raw, metric);
            }
            row.applicable = std::ranges::all_of(row.values, [](const auto& value) {
                return value.has_value() && std::isfinite(*value) && *value >= 0.0;
            });
            if (!row.applicable) {
                row.pass = false;
                row.reason = "full_reference_or_order_unavailable";
            } else {
                const auto all_small = std::ranges::all_of(row.values, [](const auto& value) {
                    return *value <= 5.0e-10;
                });
                auto monotone = true;
                for (std::size_t index = 1; index < row.values.size(); ++index) {
                    monotone = monotone &&
                        *row.values[index] <= *row.values[index - 1U] + 5.0e-13;
                }
                const auto half = *row.values[3] <= 0.50 * *row.values[0] + 5.0e-13;
                row.pass = all_small || (monotone && half);
                row.reason = all_small ? "all_orders_below_floor"
                    : row.pass ? "monotone_and_half_at_k4" : "order_rule_failed";
            }
            result.push_back(std::move(row));
        }
    };

    if (smoke) {
        make_for("main", FieldKind::general_affine, "p000", "p012_sppp", 0);
        return result;
    }
    for (const auto field : fields()) {
        for (const auto& phase : phases()) {
            for (const auto& orientation : orientations()) {
                for (int level = 0; level < 3; ++level) {
                    make_for("main", field, phase.name, orientation.name, level);
                }
            }
        }
    }
    for (const auto field : {FieldKind::general_affine, FieldKind::smooth_non_affine}) {
        for (int level = 0; level < 3; ++level) {
            make_for("ppc", field, "p049_001_083", "p210_sppm", level);
        }
    }
    return result;
}

constexpr std::string_view order_header =
    "mode,seed,scope,field,phase,orientation,level,metric,k1,k2,k3,k4,"
    "applicable,successor_nonincrease,k4_half_k1,pass,reason";

void write_order_row(Csv& csv, const OrderRow& row, bool smoke) {
    auto successor = row.applicable;
    if (row.applicable) {
        for (std::size_t index = 1; index < row.values.size(); ++index) {
            successor = successor &&
                *row.values[index] <= *row.values[index - 1U] + 5.0e-13;
        }
    }
    const auto half = row.applicable &&
        *row.values[3] <= 0.50 * *row.values[0] + 5.0e-13;
    csv.row({
        smoke ? "smoke" : "full", std::to_string(seed), row.scope, row.field,
        row.phase, row.orientation, std::to_string(row.level), row.metric,
        format_optional(row.values[0]), format_optional(row.values[1]),
        format_optional(row.values[2]), format_optional(row.values[3]),
        bool_text(row.applicable), bool_text(successor), bool_text(half),
        bool_text(row.pass), row.reason,
    });
}

void add_gate(std::vector<GateRow>& result,
              const RawRow& row,
              std::string gate,
              bool applicable,
              std::optional<double> value,
              std::optional<double> tolerance,
              bool pass) {
    result.push_back({
        row.config.scope, std::string(pf::candidate_name(row.config.candidate)),
        std::string(field_name(row.config.field)), row.config.phase.name,
        row.config.orientation.name, row.config.level, std::move(gate), applicable,
        value, tolerance, applicable ? pass : true});
}

[[nodiscard]] std::vector<GateRow> hard_gates(const std::vector<RawRow>& rows) {
    std::vector<GateRow> result;
    result.reserve(rows.size() * 20U);
    for (const auto& row : rows) {
        const auto& diagnostics = row.trace.full_reference_diagnostics;
        const auto is_full =
            row.config.candidate == pf::ProjectionCandidate::full_consistent;
        const auto is_affine = affine(row.config.field);
        const auto is_fmpm = fmpm(row.config.candidate);
        const auto is_fmpm1 =
            row.config.candidate == pf::ProjectionCandidate::fmpm_1;
        const auto full_solved = is_full && solved(row.trace.status);
        add_gate(result, row, "exact_mass", true,
                 row.exact_mass_ok ? 0.0 : 1.0, 0.0, row.exact_mass_ok);
        add_gate(result, row, "exact_clock", true,
                 row.exact_clock_ok ? 0.0 : 1.0, 0.0, row.exact_clock_ok);
        add_gate(result, row, "identity_integrity", true,
                 static_cast<double>(row.trace.id_error_count), 0.0,
                 row.trace.id_error_count == 0);
        add_gate(result, row, "nonfinite_physical_output", true,
                 static_cast<double>(row.trace.nonfinite_count), 0.0,
                 row.trace.nonfinite_count == 0);
        add_gate(result, row, "partition_unity", true,
                 diagnostics.partition_unity_max_residual, partition_tolerance,
                 std::isfinite(diagnostics.partition_unity_max_residual) &&
                     diagnostics.partition_unity_max_residual <= partition_tolerance);
        add_gate(result, row, "linear_reproduction", true,
                 diagnostics.linear_reproduction_max_residual_m,
                 linear_reproduction_tolerance,
                 std::isfinite(diagnostics.linear_reproduction_max_residual_m) &&
                     diagnostics.linear_reproduction_max_residual_m <=
                         linear_reproduction_tolerance);
        add_gate(result, row, "matrix_symmetry", true,
                 diagnostics.matrix_symmetry_relative_residual, symmetry_tolerance,
                 std::isfinite(diagnostics.matrix_symmetry_relative_residual) &&
                     diagnostics.matrix_symmetry_relative_residual <= symmetry_tolerance);
        add_gate(result, row, "row_sum_identity", true,
                 diagnostics.row_sum_relative_residual, row_sum_tolerance,
                 std::isfinite(diagnostics.row_sum_relative_residual) &&
                     diagnostics.row_sum_relative_residual <= row_sum_tolerance);
        add_gate(result, row, "grid_mass", true,
                 diagnostics.grid_mass_relative_error, grid_mass_tolerance,
                 std::isfinite(diagnostics.grid_mass_relative_error) &&
                     diagnostics.grid_mass_relative_error <= grid_mass_tolerance);
        add_gate(result, row, "linear_momentum", true,
                 row.linear_momentum_error, linear_tolerance,
                 row.linear_momentum_error.has_value() &&
                     std::isfinite(*row.linear_momentum_error) &&
                     *row.linear_momentum_error <= linear_tolerance);
        add_gate(result, row, "full_solve_residual", is_full,
                 is_full ? row.trace.max_projection_residual : std::nullopt,
                 is_full ? std::optional<double>{solve_tolerance} : std::nullopt,
                 full_solved && row.trace.max_projection_residual.has_value() &&
                     std::isfinite(*row.trace.max_projection_residual) &&
                     *row.trace.max_projection_residual <= solve_tolerance);
        add_gate(result, row, "full_raw_condition", is_full,
                 is_full ? std::optional<double>{diagnostics.raw_condition_estimate}
                         : std::nullopt,
                 is_full ? std::optional<double>{raw_condition_tolerance} : std::nullopt,
                 full_solved && std::isfinite(diagnostics.raw_condition_estimate) &&
                     diagnostics.raw_condition_estimate <= raw_condition_tolerance);
        add_gate(result, row, "full_preconditioned_condition", is_full,
                 is_full ? std::optional<double>{diagnostics.preconditioned_condition_estimate}
                         : std::nullopt,
                 is_full ? std::optional<double>{preconditioned_condition_tolerance}
                         : std::nullopt,
                 full_solved &&
                     std::isfinite(diagnostics.preconditioned_condition_estimate) &&
                     diagnostics.preconditioned_condition_estimate <=
                         preconditioned_condition_tolerance);
        add_gate(result, row, "full_affine_particle_reconstruction",
                 is_full && is_affine,
                 full_solved && is_affine && row.trace.id_error_count == 0U
                     ? std::optional<double>{row.trace.particle_reconstruction_error}
                     : std::nullopt,
                 is_full && is_affine
                     ? std::optional<double>{affine_reconstruction_tolerance}
                     : std::nullopt,
                 full_solved && row.trace.id_error_count == 0U &&
                     row.trace.particle_reconstruction_error <=
                     affine_reconstruction_tolerance);
        add_gate(result, row, "full_affine_grid_representation",
                 is_full && is_affine,
                 full_solved && is_affine
                     ? row.trace.affine_grid_representation_error
                     : std::nullopt,
                 is_full && is_affine
                     ? std::optional<double>{affine_reconstruction_tolerance}
                     : std::nullopt,
                 full_solved &&
                     row.trace.affine_grid_representation_error.has_value() &&
                     std::isfinite(*row.trace.affine_grid_representation_error) &&
                     *row.trace.affine_grid_representation_error <=
                         affine_reconstruction_tolerance);
        add_gate(result, row, "full_affine_orbital", is_full && is_affine,
                 full_solved && is_affine ? row.orbital_angular_error : std::nullopt,
                 is_full && is_affine
                     ? std::optional<double>{affine_orbital_tolerance}
                     : std::nullopt,
                 full_solved && row.orbital_angular_error.has_value() &&
                     std::isfinite(*row.orbital_angular_error) &&
                     *row.orbital_angular_error <= affine_orbital_tolerance);
        add_gate(result, row, "fmpm_residual_identity", is_fmpm,
                 is_fmpm ? row.trace.max_fmpm_residual_identity : std::nullopt,
                 is_fmpm ? std::optional<double>{fmpm_residual_tolerance}
                          : std::nullopt,
                 row.trace.max_fmpm_residual_identity.has_value() &&
                     std::isfinite(*row.trace.max_fmpm_residual_identity) &&
                     *row.trace.max_fmpm_residual_identity <= fmpm_residual_tolerance);
        add_gate(result, row, "fmpm1_pic_identity", is_fmpm1,
                 is_fmpm1 ? row.trace.pic_identity_error : std::nullopt,
                 is_fmpm1 ? std::optional<double>{pic_identity_tolerance}
                           : std::nullopt,
                 row.trace.pic_identity_error.has_value() &&
                     *row.trace.pic_identity_error <= pic_identity_tolerance);
        add_gate(result, row, "checkpoint_roundtrip_replay", true,
                 row.checkpoint_roundtrip_ok && row.checkpoint_replay_ok ? 0.0 : 1.0,
                 0.0, row.checkpoint_roundtrip_ok && row.checkpoint_replay_ok);
        add_gate(result, row, "represented_affine_energy_diagnostic",
                 is_full && is_affine,
                 full_solved && is_affine
                     ? row.center_kinetic_relative_change : std::nullopt,
                 is_full && is_affine
                     ? std::optional<double>{affine_energy_diagnostic_tolerance}
                     : std::nullopt,
                 full_solved && row.center_kinetic_relative_change.has_value() &&
                     std::isfinite(*row.center_kinetic_relative_change) &&
                     *row.center_kinetic_relative_change <=
                         affine_energy_diagnostic_tolerance);
    }
    return result;
}

constexpr std::string_view gate_header =
    "mode,seed,scope,candidate,field,phase,orientation,level,gate,applicable,"
    "value,tolerance,pass";

void write_gate_row(Csv& csv, const GateRow& row, bool smoke) {
    csv.row({
        smoke ? "smoke" : "full", std::to_string(seed), row.scope, row.candidate,
        row.field, row.phase, row.orientation, std::to_string(row.level), row.gate,
        bool_text(row.applicable), format_optional(row.value),
        format_optional(row.tolerance), bool_text(row.pass),
    });
}

constexpr std::string_view solver_header =
    "mode,seed,scope,candidate,field,phase,orientation,level,status,"
    "full_reference_status,candidate_failed,full_reference_failed,particle_count,"
    "active_node_count,structural_rank_upper_bound,numerical_rank_estimate,"
    "rank_method,rank_is_estimated,rank_certified,condition_estimated,"
    "raw_condition_estimate,preconditioned_condition_estimate,"
    "candidate_residual_applicable,candidate_max_normalized_residual,"
    "full_reference_residual_applicable,full_reference_max_normalized_residual,"
    "candidate_termination_reason,full_reference_termination_reason";

void write_solver_row(Csv& csv, const RawRow& row, bool smoke) {
    const auto& diagnostics = row.trace.full_reference_diagnostics;
    csv.row({
        smoke ? "smoke" : "full", std::to_string(seed), row.config.scope,
        std::string(pf::candidate_name(row.config.candidate)),
        std::string(field_name(row.config.field)), row.config.phase.name,
        row.config.orientation.name, std::to_string(row.config.level),
        std::string(pf::status_name(row.trace.status)),
        std::string(pf::status_name(row.trace.full_reference_status)),
        bool_text(!solved(row.trace.status)),
        bool_text(!solved(row.trace.full_reference_status)),
        std::to_string(diagnostics.particle_count),
        std::to_string(diagnostics.active_node_count),
        std::to_string(diagnostics.structural_rank_upper_bound),
        std::to_string(diagnostics.numerical_rank_estimate),
        diagnostics.numerical_rank_method,
        bool_text(diagnostics.numerical_rank_is_estimated),
        bool_text(diagnostics.rank_certified),
        bool_text(diagnostics.condition_estimated),
        format_double(diagnostics.raw_condition_estimate),
        format_double(diagnostics.preconditioned_condition_estimate),
        bool_text(row.trace.max_projection_residual.has_value()),
        format_optional(row.trace.max_projection_residual),
        bool_text(row.trace.full_reference_max_projection_residual.has_value()),
        format_optional(row.trace.full_reference_max_projection_residual),
        row.trace.candidate_diagnostics.termination_reason,
        row.trace.full_reference_diagnostics.termination_reason,
    });
}

constexpr std::string_view checkpoint_header =
    "mode,seed,scope,candidate,field,phase,orientation,level,roundtrip_exact,"
    "replay_exact,initial_sha256,terminal_sha256,pass";

void write_checkpoint_row(Csv& csv, const RawRow& row, bool smoke) {
    csv.row({
        smoke ? "smoke" : "full", std::to_string(seed), row.config.scope,
        std::string(pf::candidate_name(row.config.candidate)),
        std::string(field_name(row.config.field)), row.config.phase.name,
        row.config.orientation.name, std::to_string(row.config.level),
        bool_text(row.checkpoint_roundtrip_ok), bool_text(row.checkpoint_replay_ok),
        row.initial_checkpoint_sha256, row.terminal_checkpoint_sha256,
        bool_text(row.checkpoint_roundtrip_ok && row.checkpoint_replay_ok),
    });
}

constexpr std::string_view exact_header =
    "mode,seed,candidate,condition_one_exact,angular_delta_exact,"
    "linear_momentum_exact,oracle_result_sha256,role";

void write_exact_rows(Csv& csv, bool smoke) {
    const std::map<pf::ProjectionCandidate, std::string> angular{
        {pf::ProjectionCandidate::lumped_pic, "-921401/1895040"},
        {pf::ProjectionCandidate::full_consistent, "0/1"},
        {pf::ProjectionCandidate::fmpm_1, "-921401/1895040"},
        {pf::ProjectionCandidate::fmpm_2, "-91802668277/359117660160"},
        {pf::ProjectionCandidate::fmpm_3,
         "-9282539024459489/68054233070960640"},
        {pf::ProjectionCandidate::fmpm_4,
         "-953607378962630674973/12896549383879325122560"},
    };
    for (const auto candidate : candidates()) {
        const auto role = candidate == pf::ProjectionCandidate::full_consistent
            ? "exact_full_recovery"
            : candidate == pf::ProjectionCandidate::lumped_pic ||
                    candidate == pf::ProjectionCandidate::fmpm_1
                ? "negative_control_identity"
                : "finite_order_fingerprint";
        csv.row({
            smoke ? "smoke" : "full", std::to_string(seed),
            std::string(pf::candidate_name(candidate)), "2514/343",
            angular.at(candidate), "true", std::string(exact_oracle_result_sha), role,
        });
    }
}

[[nodiscard]] std::string decision(
    const std::vector<RawRow>& rows,
    const std::vector<ConvergenceRow>& convergence,
    const std::vector<OrderRow>& orders,
    const std::vector<GateRow>& gates,
    bool smoke) {
    if (smoke) {
        return "smoke_provisional_no_scientific_decision";
    }
    const auto full_unsolved = std::ranges::any_of(rows, [](const RawRow& row) {
        return row.config.candidate == pf::ProjectionCandidate::full_consistent &&
            !solved(row.trace.status);
    });
    // A missing full projection is not evidence that an accurately solved
    // projection failed the physical requirement.  The preregistration sends
    // rank/condition/quadrature-correlated failures to isolation first.
    if (full_unsolved) {
        return "isolate_rank_condition_or_particle_quadrature_and_stop";
    }
    const auto full_main_convergence_failure = std::ranges::any_of(
        convergence, [](const ConvergenceRow& row) {
            return row.scope == "main" && row.candidate == "full_consistent" &&
                !row.pass;
        });
    if (full_main_convergence_failure) {
        return "stop_reconsider_particle_grid_architecture";
    }
    const auto order_unavailable = std::ranges::any_of(orders, [](const OrderRow& row) {
        return !row.applicable;
    });
    if (order_unavailable) {
        return "isolate_rank_condition_or_particle_quadrature_and_stop";
    }
    const auto order_failure = std::ranges::any_of(orders, [](const OrderRow& row) {
        return !row.pass;
    });
    if (order_failure) {
        return "retain_full_reference_only_reject_tested_FMPM_approximation";
    }
    const auto fmpm4_convergence_failure = std::ranges::any_of(
        convergence, [](const ConvergenceRow& row) {
            return row.candidate == "FMPM_4" && !row.pass;
        });
    const auto fmpm4_hard_failure = std::ranges::any_of(gates, [](const GateRow& row) {
        return row.candidate == "FMPM_4" && row.applicable && !row.pass;
    });
    if (!fmpm4_convergence_failure && !fmpm4_hard_failure) {
        return "retain_FMPM_as_mechanics_foundation_research_candidate_only";
    }
    return "retain_full_reference_only_reject_FMPM_for_MLS_gates";
}

[[nodiscard]] std::string json_escape(std::string_view value) {
    std::ostringstream output;
    for (const auto character : value) {
        switch (character) {
        case '\\':
            output << "\\\\";
            break;
        case '\"':
            output << "\\\"";
            break;
        case '\n':
            output << "\\n";
            break;
        case '\r':
            output << "\\r";
            break;
        case '\t':
            output << "\\t";
            break;
        default:
            output << character;
            break;
        }
    }
    return output.str();
}

void write_text(const std::filesystem::path& path, std::string_view contents) {
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    if (!stream) {
        throw std::runtime_error("cannot create evidence file: " + path.string());
    }
    stream.write(contents.data(), static_cast<std::streamsize>(contents.size()));
    if (!stream) {
        throw std::runtime_error("cannot write evidence file: " + path.string());
    }
}

[[nodiscard]] std::string read_text(const std::filesystem::path& path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        throw std::runtime_error("cannot read evidence file: " + path.string());
    }
    std::ostringstream output;
    output << stream.rdbuf();
    if (!stream.good() && !stream.eof()) {
        throw std::runtime_error("cannot finish reading evidence file: " + path.string());
    }
    return output.str();
}

struct Counts final {
    std::size_t main_raw{0};
    std::size_t ppc_raw{0};
    std::size_t exact_control{0};
    std::size_t primary_total{0};
    std::size_t convergence{0};
    std::size_t order_to_full{0};
    std::size_t phase_sensitivity{0};
    std::size_t orientation_sensitivity{0};
    std::size_t hard_gates{0};
    std::size_t solver_failures{0};
    std::size_t checkpoint{0};
};

[[nodiscard]] std::string summary_json(
    bool smoke,
    const Counts& counts,
    std::string_view bounded_decision,
    const std::vector<RawRow>& rows,
    const std::vector<ConvergenceRow>& convergence,
    const std::vector<OrderRow>& orders,
    const std::vector<GateRow>& gates) {
    const auto candidate_failures = std::ranges::count_if(rows, [](const RawRow& row) {
        return !solved(row.trace.status);
    });
    const auto full_reference_failures = std::ranges::count_if(rows, [](const RawRow& row) {
        return !solved(row.trace.full_reference_status);
    });
    const auto convergence_failures = std::ranges::count_if(
        convergence, [](const ConvergenceRow& row) { return !row.pass; });
    const auto order_failures = std::ranges::count_if(
        orders, [](const OrderRow& row) { return row.applicable && !row.pass; });
    const auto order_unavailable = std::ranges::count_if(
        orders, [](const OrderRow& row) { return !row.applicable; });
    const auto applicable_gate_failures = std::ranges::count_if(
        gates, [](const GateRow& row) { return row.applicable && !row.pass; });
    const auto checkpoint_failures = std::ranges::count_if(rows, [](const RawRow& row) {
        return !row.checkpoint_roundtrip_ok || !row.checkpoint_replay_ok;
    });
    const auto structural_failures = std::ranges::count_if(rows, [](const RawRow& row) {
        return row.trace.status == pf::ProjectionStatus::structurally_rank_deficient;
    });

    std::ostringstream output;
    output.imbue(std::locale::classic());
    output << "{\n"
           << "  \"accepted_parent_sha\": \"" << accepted_parent_sha << "\",\n"
           << "  \"accepted_parent_tag\": \"" << accepted_parent_tag << "\",\n"
           << "  \"architecture_rule\": \"causally active numerical auxiliaries must be derivable or accounted physical state\",\n"
           << "  \"bounded_decision\": \"" << json_escape(bounded_decision) << "\",\n"
           << "  \"candidate_failures\": " << candidate_failures << ",\n"
           << "  \"checkpoint_failures\": " << checkpoint_failures << ",\n"
           << "  \"compiler_id\": \"" << json_escape(MLS_CONFIGURED_COMPILER_ID) << "\",\n"
           << "  \"compiler_version\": \"" << json_escape(MLS_CONFIGURED_COMPILER_VERSION) << "\",\n"
           << "  \"convergence_failures\": " << convergence_failures << ",\n"
           << "  \"counts\": {\n"
           << "    \"checkpoint\": " << counts.checkpoint << ",\n"
           << "    \"convergence\": " << counts.convergence << ",\n"
           << "    \"exact_control\": " << counts.exact_control << ",\n"
           << "    \"hard_gates\": " << counts.hard_gates << ",\n"
           << "    \"main_raw\": " << counts.main_raw << ",\n"
           << "    \"order_to_full\": " << counts.order_to_full << ",\n"
           << "    \"orientation_sensitivity\": " << counts.orientation_sensitivity << ",\n"
           << "    \"phase_sensitivity\": " << counts.phase_sensitivity << ",\n"
           << "    \"ppc_raw\": " << counts.ppc_raw << ",\n"
           << "    \"primary_total\": " << counts.primary_total << ",\n"
           << "    \"solver_failures\": " << counts.solver_failures << "\n"
           << "  },\n"
           << "  \"exact_oracle_result_sha256\": \"" << exact_oracle_result_sha << "\",\n"
           << "  \"full_reference_failures\": " << full_reference_failures << ",\n"
           << "  \"hard_gate_failures\": " << applicable_gate_failures << ",\n"
           << "  \"mode\": \"" << (smoke ? "smoke" : "full") << "\",\n"
           << "  \"no_constitutive_mechanics_authorized\": true,\n"
           << "  \"order_failures\": " << order_failures << ",\n"
           << "  \"order_unavailable\": " << order_unavailable << ",\n"
           << "  \"schema\": \"" << schema << "\",\n"
           << "  \"seed\": " << seed << ",\n"
           << "  \"source_branch\": \"" << json_escape(MLS_CONFIGURED_SOURCE_BRANCH) << "\",\n"
           << "  \"source_dirty\": " << MLS_CONFIGURED_SOURCE_DIRTY << ",\n"
           << "  \"source_sha\": \"" << json_escape(MLS_CONFIGURED_SOURCE_SHA) << "\",\n"
           << "  \"structural_rank_failures\": " << structural_failures << ",\n"
           << "  \"sweep_complete\": "
           << bool_text(smoke ? counts.main_raw == 6U
                              : counts.primary_total == 330U) << ",\n"
           << "  \"time_quantum_s\": " << format_double(time_quantum_s) << ",\n"
           << "  \"tool_language\": \"C++20\",\n"
           << "  \"u_ref_m_per_s\": " << format_double(u_ref_m_per_s) << "\n"
           << "}\n";
    return output.str();
}

void write_manifest(const std::filesystem::path& output_directory,
                    const std::vector<std::string>& filenames) {
    std::map<std::string, std::string> hashes;
    for (const auto& filename : filenames) {
        hashes.emplace(filename, sha256(read_text(output_directory / filename)));
    }
    std::ostringstream payload;
    payload << "{\n"
            << "  \"algorithm\": \"SHA-256\",\n"
            << "  \"files\": {\n";
    std::size_t index = 0;
    for (const auto& [filename, hash] : hashes) {
        payload << "    \"" << json_escape(filename) << "\": \"" << hash << "\""
                << (++index == hashes.size() ? "\n" : ",\n");
    }
    payload << "  },\n"
            << "  \"schema\": \"" << manifest_schema << "\"\n"
            << "}";
    const auto pre_hash = sha256(payload.str());
    std::ostringstream final;
    final << "{\n"
          << "  \"algorithm\": \"SHA-256\",\n"
          << "  \"files\": {\n";
    index = 0;
    for (const auto& [filename, hash] : hashes) {
        final << "    \"" << json_escape(filename) << "\": \"" << hash << "\""
              << (++index == hashes.size() ? "\n" : ",\n");
    }
    final << "  },\n"
          << "  \"pre_hash_sha256\": \"" << pre_hash << "\",\n"
          << "  \"schema\": \"" << manifest_schema << "\"\n"
          << "}\n";
    write_text(output_directory / "manifest.json", final.str());
}

[[nodiscard]] Options parse_options(int argc, char** argv) {
    Options result{};
    for (int index = 1; index < argc; ++index) {
        const std::string_view argument{argv[index]};
        if (argument == "--smoke") {
            result.smoke = true;
        } else if (argument == "--schema-audit") {
            result.schema_audit = true;
        } else if (argument == "--output") {
            if (index + 1 >= argc) {
                throw std::invalid_argument("--output requires a directory");
            }
            result.output = argv[++index];
        } else if (argument == "--jobs") {
            if (index + 1 >= argc) {
                throw std::invalid_argument("--jobs requires a positive integer");
            }
            const std::string value{argv[++index]};
            std::size_t parsed = 0;
            const auto jobs = std::stoull(value, &parsed, 10);
            if (parsed != value.size() || jobs == 0U || jobs > 64U) {
                throw std::invalid_argument("--jobs must be in [1,64]");
            }
            result.jobs = static_cast<std::size_t>(jobs);
        } else if (argument == "--help") {
            std::cout << "Usage: mls_projection_foundation_diagnostic "
                         "[--smoke | --schema-audit] [--jobs N] "
                         "[--output DIRECTORY]\n";
            std::exit(EXIT_SUCCESS);
        } else {
            throw std::invalid_argument("unknown argument: " + std::string(argument));
        }
    }
    return result;
}

[[nodiscard]] int run_schema_audit() {
    std::vector<RawRow> rows;
    const auto configs = configurations(false);
    rows.reserve(configs.size());
    for (const auto& config : configs) {
        RawRow row{};
        row.config = config;
        row.trace.status = pf::ProjectionStatus::solved;
        row.trace.full_reference_status = pf::ProjectionStatus::solved;
        row.trace.full_reference_available = true;
        row.trace.grid_distance_full = 0.0;
        row.trace.particle_distance_full = 0.0;
        row.trace.affine_grid_representation_error = 0.0;
        row.trace.pic_identity_error = 0.0;
        row.trace.max_projection_residual = 0.0;
        row.trace.max_fmpm_residual_identity = 0.0;
        row.trace.terminal.particles = {{1U, expected_mass_quanta, {}, {}}};
        row.terminal_particles = row.trace.terminal.particles;
        row.material_velocity_error = 0.0;
        row.trajectory_error = 0.0;
        row.linear_momentum_error = 0.0;
        row.orbital_angular_error = 0.0;
        row.center_kinetic_relative_change = 0.0;
        row.exact_mass_ok = true;
        row.exact_clock_ok = true;
        row.checkpoint_roundtrip_ok = true;
        row.checkpoint_replay_ok = true;
        rows.push_back(std::move(row));
    }
    const auto phase_rows = phase_sensitivity(rows, false);
    const auto orientation_rows = orientation_sensitivity(rows, false);
    const auto convergence = convergence_rows(
        rows, phase_rows, orientation_rows, false);
    const auto orders = order_rows(rows, false);
    const auto gates = hard_gates(rows);
    const auto require_count = [](std::size_t observed, std::size_t expected,
                                  std::string_view table) {
        if (observed != expected) {
            throw std::runtime_error(
                "schema audit count mismatch for " + std::string(table) + ": " +
                std::to_string(observed) + " != " + std::to_string(expected));
        }
    };
    require_count(rows.size(), 324U, "raw");
    require_count(phase_rows.size(), 480U, "phase sensitivity");
    require_count(orientation_rows.size(), 480U, "orientation sensitivity");
    const auto convergence_scope_count = [&](std::string_view scope) {
        return static_cast<std::size_t>(std::ranges::count_if(
            convergence, [&](const ConvergenceRow& row) { return row.scope == scope; }));
    };
    const auto main_distance_count = static_cast<std::size_t>(std::ranges::count_if(
        convergence, [](const ConvergenceRow& row) {
            return row.scope == "main" &&
                (row.metric == "grid_distance_full" ||
                 row.metric == "particle_distance_full");
        }));
    require_count(main_distance_count, 128U, "main distance convergence");
    require_count(convergence_scope_count("main"), 512U, "main convergence");
    require_count(convergence_scope_count("ppc"), 64U, "ppc convergence");
    require_count(convergence_scope_count("phase"), 160U, "phase convergence");
    require_count(
        convergence_scope_count("orientation"), 160U, "orientation convergence");
    require_count(convergence.size(), 896U, "convergence");
    require_count(orders.size(), 108U, "order");
    require_count(gates.size(), 6480U, "hard gates");

    std::set<std::string> convergence_keys;
    std::size_t phase_distance_families = 0;
    std::size_t orientation_distance_families = 0;
    for (const auto& row : convergence) {
        const auto key = row.scope + "\x1f" + row.candidate + "\x1f" + row.field +
            "\x1f" + row.phase + "\x1f" + row.orientation + "\x1f" + row.metric;
        if (!convergence_keys.insert(key).second) {
            throw std::runtime_error("schema audit duplicate convergence key");
        }
        if (row.metric == "grid_distance_full" ||
            row.metric == "particle_distance_full") {
            phase_distance_families += row.scope == "phase" ? 1U : 0U;
            orientation_distance_families += row.scope == "orientation" ? 1U : 0U;
        }
    }
    require_count(phase_distance_families, 64U, "phase distance convergence");
    require_count(
        orientation_distance_families, 64U, "orientation distance convergence");

    const std::vector<pf::CenterParticle> identity_reference{
        {1U, 1, {}, {}}, {2U, 1, {}, {}}};
    const std::vector<pf::CenterParticle> identity_missing{{1U, 1, {}, {}}};
    const std::vector<pf::CenterParticle> identity_replaced{
        {1U, 1, {}, {}}, {3U, 1, {}, {}}};
    const std::vector<pf::CenterParticle> identity_duplicate{
        {1U, 1, {}, {}}, {1U, 1, {}, {}}};
    const std::vector<pf::CenterParticle> identity_extra{
        {1U, 1, {}, {}}, {2U, 1, {}, {}}, {3U, 1, {}, {}}};
    if (identity_error_count(identity_reference, identity_reference) != 0U ||
        identity_error_count(identity_reference, identity_missing) != 1U ||
        identity_error_count(identity_reference, identity_replaced) != 2U ||
        identity_error_count(identity_reference, identity_duplicate) != 2U ||
        identity_error_count(identity_reference, identity_extra) != 1U) {
        throw std::runtime_error("schema audit identity accounting regression");
    }
    std::cout << "Projection Foundation full schema audit: PASS "
                 "(324 raw, 896 convergence, 480+480 sensitivity, "
                 "6480 gates; identity controls)\n";
    return EXIT_SUCCESS;
}

[[nodiscard]] int run(const Options& options) {
    if (options.schema_audit) {
        return run_schema_audit();
    }
    std::filesystem::create_directories(options.output);
    const auto configs = configurations(options.smoke);
    std::vector<std::optional<RawRow>> slots(configs.size());
    std::atomic<std::size_t> next_index{0};
    std::atomic<std::size_t> completed{0};
    std::atomic<bool> stop{false};
    std::mutex report_mutex{};
    std::exception_ptr worker_failure{};
    const auto worker = [&] {
        while (!stop.load(std::memory_order_relaxed)) {
            const auto index = next_index.fetch_add(1U, std::memory_order_relaxed);
            if (index >= configs.size()) {
                return;
            }
            try {
                slots[index] = run_configuration(configs[index]);
            } catch (...) {
                std::scoped_lock lock{report_mutex};
                if (worker_failure == nullptr) {
                    worker_failure = std::current_exception();
                }
                stop.store(true, std::memory_order_relaxed);
                return;
            }
            const auto count = completed.fetch_add(1U, std::memory_order_relaxed) + 1U;
            if (!options.smoke && count % 24U == 0U) {
                std::scoped_lock lock{report_mutex};
                std::cout << "projection-foundation progress " << count << '/'
                          << configs.size() << '\n';
            }
        }
    };
    std::vector<std::thread> workers;
    workers.reserve(options.jobs);
    for (std::size_t index = 0; index < options.jobs; ++index) {
        workers.emplace_back(worker);
    }
    for (auto& thread : workers) {
        thread.join();
    }
    if (worker_failure != nullptr) {
        std::rethrow_exception(worker_failure);
    }
    std::vector<RawRow> raw_rows;
    raw_rows.reserve(configs.size());
    for (auto& slot : slots) {
        if (!slot.has_value()) {
            throw std::runtime_error("projection worker did not produce a registered row");
        }
        raw_rows.push_back(std::move(*slot));
    }

    const auto phase_rows = phase_sensitivity(raw_rows, options.smoke);
    const auto orientation_rows = orientation_sensitivity(raw_rows, options.smoke);
    const auto convergence = convergence_rows(
        raw_rows, phase_rows, orientation_rows, options.smoke);
    const auto orders = order_rows(raw_rows, options.smoke);
    const auto gates = hard_gates(raw_rows);

    Csv main_csv(raw_header);
    Csv ppc_csv(raw_header);
    Csv exact_csv(exact_header);
    Csv convergence_csv(convergence_header);
    Csv order_csv(order_header);
    Csv phase_csv(sensitivity_header);
    Csv orientation_csv(sensitivity_header);
    Csv gate_csv(gate_header);
    Csv solver_csv(solver_header);
    Csv checkpoint_csv(checkpoint_header);
    for (const auto& row : raw_rows) {
        write_raw_row(row.config.scope == "main" ? main_csv : ppc_csv, row, options.smoke);
        write_solver_row(solver_csv, row, options.smoke);
        write_checkpoint_row(checkpoint_csv, row, options.smoke);
    }
    write_exact_rows(exact_csv, options.smoke);
    for (const auto& row : convergence) {
        write_convergence_row(convergence_csv, row, options.smoke);
    }
    for (const auto& row : orders) {
        write_order_row(order_csv, row, options.smoke);
    }
    for (const auto& row : phase_rows) {
        write_sensitivity_row(phase_csv, row, options.smoke);
    }
    for (const auto& row : orientation_rows) {
        write_sensitivity_row(orientation_csv, row, options.smoke);
    }
    for (const auto& row : gates) {
        write_gate_row(gate_csv, row, options.smoke);
    }

    const Counts actual{
        main_csv.rows(), ppc_csv.rows(), exact_csv.rows(),
        main_csv.rows() + ppc_csv.rows() + exact_csv.rows(),
        convergence_csv.rows(), order_csv.rows(), phase_csv.rows(),
        orientation_csv.rows(), gate_csv.rows(), solver_csv.rows(),
        checkpoint_csv.rows()};
    const Counts expected = options.smoke
        ? Counts{6, 0, 6, 12, 0, 2, 0, 0, 120, 6, 6}
        : Counts{288, 36, 6, 330, 896, 108, 480, 480, 6480, 324, 324};
    if (actual.main_raw != expected.main_raw || actual.ppc_raw != expected.ppc_raw ||
        actual.exact_control != expected.exact_control ||
        actual.primary_total != expected.primary_total ||
        actual.convergence != expected.convergence ||
        actual.order_to_full != expected.order_to_full ||
        actual.phase_sensitivity != expected.phase_sensitivity ||
        actual.orientation_sensitivity != expected.orientation_sensitivity ||
        actual.hard_gates != expected.hard_gates ||
        actual.solver_failures != expected.solver_failures ||
        actual.checkpoint != expected.checkpoint) {
        throw std::runtime_error("projection evidence row counts differ from frozen schema");
    }

    main_csv.write(options.output / "main_raw.csv");
    ppc_csv.write(options.output / "ppc_raw.csv");
    exact_csv.write(options.output / "exact_angular_control.csv");
    convergence_csv.write(options.output / "convergence.csv");
    order_csv.write(options.output / "order_to_full.csv");
    phase_csv.write(options.output / "phase_sensitivity.csv");
    orientation_csv.write(options.output / "orientation_sensitivity.csv");
    gate_csv.write(options.output / "hard_gates.csv");
    solver_csv.write(options.output / "solver_failures.csv");
    checkpoint_csv.write(options.output / "checkpoint.csv");
    const auto bounded_decision = decision(raw_rows, convergence, orders, gates, options.smoke);
    write_text(options.output / "summary.json",
               summary_json(options.smoke, actual, bounded_decision, raw_rows,
                            convergence, orders, gates));
    const std::vector<std::string> manifest_files{
        "checkpoint.csv", "convergence.csv", "exact_angular_control.csv",
        "hard_gates.csv", "main_raw.csv", "order_to_full.csv",
        "orientation_sensitivity.csv", "phase_sensitivity.csv", "ppc_raw.csv",
        "solver_failures.csv", "summary.json"};
    write_manifest(options.output, manifest_files);
    std::cout << "Projection Foundation " << (options.smoke ? "smoke" : "full")
              << " evidence written to " << options.output.string() << '\n';
    return EXIT_SUCCESS;
}

} // namespace

int main(int argc, char** argv) {
    try {
        return run(parse_options(argc, argv));
    } catch (const std::exception& error) {
        std::cerr << "mls_projection_foundation_diagnostic: " << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
