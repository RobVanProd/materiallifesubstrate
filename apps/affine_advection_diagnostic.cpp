#include "mls/affine_advection_lab.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <locale>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
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

using mls::experimental::GridIndex;
using mls::experimental::Matrix3d;
using mls::experimental::TransferCandidate;
using mls::experimental::TransferConfig;
using mls::experimental::TransferCycle;
using mls::experimental::TransferGrid;
using mls::experimental::TransferParticle;
using mls::experimental::TransferTotals;
using mls::experimental::Vec3d;
using mls::experimental::affine_advection::AffineField;
using mls::experimental::affine_advection::MovingApicParticle;
using mls::experimental::affine_advection::MovingApicStep;
using mls::experimental::affine_advection::Path;

constexpr std::uint64_t seed = 260828;
constexpr std::int64_t time_quantum_seconds_numerator = 1;
constexpr std::int64_t time_quantum_seconds_denominator = 80;
constexpr std::int64_t horizon_quanta = 8;
constexpr double kg_per_mass_quantum = 0.125;
constexpr double core_spacing_m = 0.5;

constexpr double mass_tolerance = 2.0e-13;
constexpr double linear_tolerance = 2.0e-12;
constexpr double angular_tolerance = 2.0e-11;
constexpr double one_remap_affine_tolerance = 5.0e-11;
constexpr double horizon_tolerance = 2.0e-9;
constexpr double roundoff_floor = 5.0e-14;

enum class FieldKind : std::uint8_t {
    translation,
    rigid_rotation,
    general_affine,
};

enum class LayoutKind : std::uint8_t {
    regular_2x2x2,
    unequal_mass_asymmetric,
    seeded_jittered_27,
};

struct Orientation final {
    Matrix3d matrix{};
    std::string label{};
};

struct LayoutMass final {
    LayoutKind layout{};
    std::int64_t mass_ratio{1};
};

struct Options final {
    bool smoke{false};
    std::filesystem::path output{"evidence/affine-advection-diagnostic"};
};

struct Family final {
    FieldKind field{};
    std::size_t phase_index{0};
    std::size_t orientation_index{0};
    LayoutKind layout{};
    std::int64_t mass_ratio{1};

    [[nodiscard]] auto operator<=>(const Family&) const noexcept = default;
};

struct DiagnosticRow final {
    Family family{};
    Path path{};
    std::int64_t schedule_index{0};
    std::int64_t step_or_remap_count{0};
    std::int64_t dt_quanta{0};
    double dt_seconds{0.0};
    double spacing_m{0.0};
    bool physical_time_applicable{false};
    std::int64_t elapsed_quanta{0};
    bool exact_mass_ok{false};
    bool exact_clock_ok{false};
    std::optional<double> static_velocity_error{};
    std::optional<double> static_affine_error{};
    std::optional<double> static_grid_error{};
    std::optional<double> affine_gradient_error{};
    std::optional<double> affine_intercept_error{};
    std::optional<double> affine_dispersion_error{};
    std::optional<double> stale_gradient_witness_error{};
    std::optional<double> trajectory_position_error{};
    std::optional<double> material_velocity_error{};
    std::optional<double> linear_momentum_error{};
    std::optional<double> center_orbital_error{};
    std::optional<double> center_kinetic_error{};
    double max_p2g_mass_error{0.0};
    double max_p2g_linear_error{0.0};
    double max_p2g_augmented_angular_error{0.0};
    double max_g2p_linear_error{0.0};
    double max_g2p_augmented_angular_error{0.0};
    double max_abs_p2g_center_energy_residual_j{0.0};
    double max_abs_p2g_augmented_energy_residual_j{0.0};
    double terminal_affine_auxiliary_energy_j{0.0};
    double terminal_augmented_representation_energy_j{0.0};
};

struct RunResult final {
    std::vector<TransferParticle> particles{};
    AffineField analytic_field{};
    std::int64_t elapsed_quanta{0};
    std::int64_t exact_mass_initial{0};
    std::int64_t exact_mass_terminal{0};
    double max_static_velocity_error{0.0};
    double max_static_affine_error{0.0};
    double max_static_grid_error{0.0};
    double max_p2g_mass_error{0.0};
    double max_p2g_linear_error{0.0};
    double max_p2g_augmented_angular_error{0.0};
    double max_g2p_linear_error{0.0};
    double max_g2p_augmented_angular_error{0.0};
    double max_abs_p2g_center_energy_residual_j{0.0};
    double max_abs_p2g_augmented_energy_residual_j{0.0};
};

struct SanityRow final {
    FieldKind field{};
    std::size_t phase_index{0};
    std::size_t orientation_index{0};
    std::int64_t dt_quanta{0};
    std::int64_t steps{0};
    bool exact_mass_ok{false};
    bool exact_clock_ok{false};
    double position_error{0.0};
    double velocity_error{0.0};
    double B_error{0.0};
    double center_energy_error{0.0};
    bool pass{false};
};

class Csv final {
public:
    explicit Csv(const std::filesystem::path& path) : stream_(path, std::ios::binary) {
        stream_.exceptions(std::ios::badbit | std::ios::failbit);
        stream_.imbue(std::locale::classic());
    }

    void write(std::string_view text) { stream_.write(text.data(), static_cast<std::streamsize>(text.size())); }

    void row(const std::vector<std::string>& fields) {
        for (std::size_t index = 0; index < fields.size(); ++index) {
            if (index != 0U) {
                stream_ << ',';
            }
            stream_ << fields[index];
        }
        stream_ << '\n';
        ++rows_;
    }

    [[nodiscard]] std::uint64_t rows() const noexcept { return rows_; }

private:
    std::ofstream stream_;
    std::uint64_t rows_{0};
};

[[nodiscard]] std::string format_double(double value) {
    if (!std::isfinite(value)) {
        throw std::runtime_error("non-finite affine-advection result");
    }
    std::ostringstream text;
    text.imbue(std::locale::classic());
    text << std::scientific << std::setprecision(std::numeric_limits<double>::max_digits10)
         << value;
    return text.str();
}

[[nodiscard]] std::string format_optional(const std::optional<double>& value) {
    return value.has_value() ? format_double(*value) : "NA";
}

template <typename Value>
[[nodiscard]] std::string to_text(Value value) {
    return std::to_string(value);
}

[[nodiscard]] std::string to_text(bool value) { return value ? "true" : "false"; }

[[nodiscard]] Matrix3d matrix_subtract(const Matrix3d& lhs, const Matrix3d& rhs) noexcept {
    Matrix3d result{};
    for (std::size_t row = 0; row < 3; ++row) {
        for (std::size_t column = 0; column < 3; ++column) {
            result.value[row][column] = lhs.value[row][column] - rhs.value[row][column];
        }
    }
    return result;
}

[[nodiscard]] Matrix3d matrix_add(const Matrix3d& lhs, const Matrix3d& rhs) noexcept {
    return lhs + rhs;
}

[[nodiscard]] double relative_scalar(double lhs, double rhs) noexcept {
    return std::abs(lhs - rhs) / std::max({1.0, std::abs(lhs), std::abs(rhs)});
}

[[nodiscard]] double relative_vector(Vec3d lhs, Vec3d rhs) noexcept {
    return mls::experimental::norm(lhs - rhs) /
        std::max({1.0, mls::experimental::norm(lhs), mls::experimental::norm(rhs)});
}

[[nodiscard]] double relative_matrix(const Matrix3d& lhs, const Matrix3d& rhs) noexcept {
    return mls::experimental::frobenius_norm(matrix_subtract(lhs, rhs)) /
        std::max({1.0,
                  mls::experimental::frobenius_norm(lhs),
                  mls::experimental::frobenius_norm(rhs)});
}

[[nodiscard]] std::string_view field_name(FieldKind field) noexcept {
    switch (field) {
    case FieldKind::translation:
        return "translation";
    case FieldKind::rigid_rotation:
        return "rigid_rotation";
    case FieldKind::general_affine:
        return "general_affine";
    }
    return "unknown";
}

[[nodiscard]] std::string_view layout_name(LayoutKind layout) noexcept {
    switch (layout) {
    case LayoutKind::regular_2x2x2:
        return "regular_2x2x2";
    case LayoutKind::unequal_mass_asymmetric:
        return "unequal_mass_asymmetric";
    case LayoutKind::seeded_jittered_27:
        return "seeded_jittered_27";
    }
    return "unknown";
}

[[nodiscard]] Matrix3d rotation_gradient(Vec3d omega_per_s) noexcept {
    Matrix3d result{};
    result.value = {{{0.0, -omega_per_s.z, omega_per_s.y},
                     {omega_per_s.z, 0.0, -omega_per_s.x},
                     {-omega_per_s.y, omega_per_s.x, 0.0}}};
    return result;
}

[[nodiscard]] std::array<FieldKind, 3> fields() noexcept {
    return {FieldKind::translation, FieldKind::rigid_rotation, FieldKind::general_affine};
}

[[nodiscard]] std::array<Vec3d, 2> phases() noexcept {
    return {Vec3d{0.0, 0.0, 0.0}, Vec3d{0.49, 0.01, 0.83}};
}

[[nodiscard]] std::array<Orientation, 3> orientations() {
    Matrix3d identity = Matrix3d::identity();
    Matrix3d cyclic{};
    cyclic.value = {{{0.0, 1.0, 0.0}, {0.0, 0.0, 1.0}, {1.0, 0.0, 0.0}}};
    Matrix3d reversal{};
    reversal.value = {{{0.0, 0.0, 1.0}, {0.0, 1.0, 0.0}, {-1.0, 0.0, 0.0}}};
    return {{{identity, "p012_sppp"}, {cyclic, "p120_sppp"}, {reversal, "p210_sppm"}}};
}

[[nodiscard]] std::array<LayoutMass, 3> layout_mass_pairs() noexcept {
    return {{{LayoutKind::regular_2x2x2, 1},
             {LayoutKind::unequal_mass_asymmetric, 17},
             {LayoutKind::seeded_jittered_27, 1}}};
}

[[nodiscard]] std::array<std::int64_t, 4> dt_quanta_values() noexcept {
    return {8, 4, 2, 1};
}

[[nodiscard]] std::array<Path, 5> paths() noexcept {
    return {Path::analytic_ballistic,
            Path::frozen_static_apic,
            Path::sealed_static_apic_ballistic,
            Path::analytic_convected_affine_control,
            Path::jst2017_moving_apic};
}

[[nodiscard]] double seconds_from_quanta(std::int64_t quanta) noexcept {
    return static_cast<double>(quanta * time_quantum_seconds_numerator) /
        static_cast<double>(time_quantum_seconds_denominator);
}

[[nodiscard]] AffineField base_global_field(FieldKind kind) {
    Matrix3d gradient{};
    Vec3d centered_translation{};
    const Vec3d center{0.31, -0.27, 0.19};
    switch (kind) {
    case FieldKind::translation:
        centered_translation = {0.70, -0.45, 0.20};
        break;
    case FieldKind::rigid_rotation:
        gradient = rotation_gradient({0.45, -0.35, 0.55});
        break;
    case FieldKind::general_affine:
        gradient.value = {{{0.20, -0.70, 0.30},
                           {0.55, -0.10, 0.25},
                           {-0.35, 0.40, 0.15}}};
        centered_translation = {0.90, -0.40, 0.70};
        break;
    }
    return {gradient, centered_translation - mls::experimental::multiply(gradient, center)};
}

[[nodiscard]] AffineField oriented_field(FieldKind kind, const Orientation& orientation) {
    const auto source = base_global_field(kind);
    return {
        mls::experimental::multiply(
            mls::experimental::multiply(orientation.matrix, source.gradient_per_s),
            mls::experimental::transpose(orientation.matrix)),
        mls::experimental::multiply(orientation.matrix, source.offset_m_per_s),
    };
}

class SplitMix64 final {
public:
    explicit SplitMix64(std::uint64_t initial) : state_(initial) {}
    [[nodiscard]] std::uint64_t next() noexcept {
        state_ += 0x9e3779b97f4a7c15ULL;
        auto value = state_;
        value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
        value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
        return value ^ (value >> 31U);
    }
    [[nodiscard]] double symmetric_unit() noexcept {
        constexpr double scale = 1.0 / 9007199254740992.0;
        return 2.0 * (static_cast<double>(next() >> 11U) * scale) - 1.0;
    }
private:
    std::uint64_t state_;
};

struct BaseLayout final {
    std::vector<Vec3d> offsets{};
    std::vector<std::int64_t> masses{};
};

[[nodiscard]] BaseLayout base_layout(LayoutKind layout) {
    BaseLayout result{};
    switch (layout) {
    case LayoutKind::regular_2x2x2:
        for (const auto x : {-0.36, 0.36}) {
            for (const auto y : {-0.36, 0.36}) {
                for (const auto z : {-0.36, 0.36}) {
                    result.offsets.push_back({x, y, z});
                    result.masses.push_back(1);
                }
            }
        }
        break;
    case LayoutKind::unequal_mass_asymmetric:
        result.offsets = {
            {-0.51, -0.22, 0.17}, {0.44, -0.31, -0.28}, {-0.13, 0.56, -0.19},
            {0.28, 0.16, 0.49},   {-0.47, 0.33, 0.41},  {0.09, -0.54, 0.36},
            {0.53, 0.45, 0.08},   {-0.24, -0.11, -0.52}, {0.17, 0.04, -0.07}};
        result.masses = {1, 2, 3, 5, 8, 13, 17, 11, 7};
        break;
    case LayoutKind::seeded_jittered_27: {
        SplitMix64 generator(seed);
        for (const auto x : {-0.42, 0.0, 0.42}) {
            for (const auto y : {-0.42, 0.0, 0.42}) {
                for (const auto z : {-0.42, 0.0, 0.42}) {
                    result.offsets.push_back({
                        x + 0.055 * generator.symmetric_unit(),
                        y + 0.055 * generator.symmetric_unit(),
                        z + 0.055 * generator.symmetric_unit()});
                    result.masses.push_back(1);
                }
            }
        }
        break;
    }
    }
    return result;
}

[[nodiscard]] std::vector<TransferParticle> make_particles(
    const Family& family, const Orientation& orientation, const AffineField& field) {
    const auto base = base_layout(family.layout);
    const Vec3d center{0.31, -0.27, 0.19};
    std::vector<TransferParticle> result;
    result.reserve(base.offsets.size());
    for (std::size_t index = 0; index < base.offsets.size(); ++index) {
        const auto position = mls::experimental::multiply(
            orientation.matrix, center + base.offsets[index]);
        const auto ratio = index % 2U == 0U ? std::int64_t{1} : family.mass_ratio;
        result.push_back({
            static_cast<std::uint64_t>(index + 1U),
            base.masses[index] * ratio,
            position,
            mls::experimental::affine_advection::velocity_at(field, position),
            field.gradient_per_s});
    }
    return result;
}

[[nodiscard]] double particle_vector_rms_error(
    const std::vector<TransferParticle>& actual,
    const std::vector<TransferParticle>& reference,
    bool position) {
    if (actual.size() != reference.size()) {
        throw std::logic_error("particle vector comparison size mismatch");
    }
    long double weighted_error = 0.0L;
    long double weighted_reference = 0.0L;
    long double total_mass = 0.0L;
    for (std::size_t index = 0; index < actual.size(); ++index) {
        const auto lhs = position ? actual[index].position_m : actual[index].velocity_m_per_s;
        const auto rhs = position ? reference[index].position_m : reference[index].velocity_m_per_s;
        const auto difference = lhs - rhs;
        const auto mass = static_cast<long double>(reference[index].mass_quanta);
        weighted_error += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        weighted_reference += mass * static_cast<long double>(mls::experimental::dot(rhs, rhs));
        total_mass += mass;
    }
    const auto error = std::sqrt(static_cast<double>(weighted_error / total_mass));
    const auto scale = std::sqrt(static_cast<double>(weighted_reference / total_mass));
    return error / std::max(1.0, scale);
}

[[nodiscard]] double particle_affine_change(
    const std::vector<TransferParticle>& actual,
    const std::vector<TransferParticle>& reference) {
    long double weighted_error = 0.0L;
    long double weighted_reference = 0.0L;
    long double total_mass = 0.0L;
    for (std::size_t index = 0; index < actual.size(); ++index) {
        const auto difference = matrix_subtract(
            actual[index].affine_velocity_per_s, reference[index].affine_velocity_per_s);
        const auto error = mls::experimental::frobenius_norm(difference);
        const auto ref = mls::experimental::frobenius_norm(
            reference[index].affine_velocity_per_s);
        const auto mass = static_cast<long double>(reference[index].mass_quanta);
        weighted_error += mass * static_cast<long double>(error * error);
        weighted_reference += mass * static_cast<long double>(ref * ref);
        total_mass += mass;
    }
    return std::sqrt(static_cast<double>(weighted_error / total_mass)) /
        std::max(1.0, std::sqrt(static_cast<double>(weighted_reference / total_mass)));
}

[[nodiscard]] double affine_gradient_error(
    const std::vector<TransferParticle>& particles, const Matrix3d& reference) {
    long double weighted_error = 0.0L;
    long double total_mass = 0.0L;
    for (const auto& particle : particles) {
        const auto error = mls::experimental::frobenius_norm(
            matrix_subtract(particle.affine_velocity_per_s, reference));
        const auto mass = static_cast<long double>(particle.mass_quanta);
        weighted_error += mass * static_cast<long double>(error * error);
        total_mass += mass;
    }
    return std::sqrt(static_cast<double>(weighted_error / total_mass)) /
        std::max(1.0, mls::experimental::frobenius_norm(reference));
}

[[nodiscard]] Vec3d recovered_intercept(const TransferParticle& particle) noexcept {
    return particle.velocity_m_per_s -
        mls::experimental::multiply(particle.affine_velocity_per_s, particle.position_m);
}

[[nodiscard]] double affine_intercept_error(
    const std::vector<TransferParticle>& particles, Vec3d reference) {
    long double weighted_error = 0.0L;
    long double total_mass = 0.0L;
    for (const auto& particle : particles) {
        const auto difference = recovered_intercept(particle) - reference;
        const auto mass = static_cast<long double>(particle.mass_quanta);
        weighted_error += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        total_mass += mass;
    }
    return std::sqrt(static_cast<double>(weighted_error / total_mass)) /
        std::max(1.0, mls::experimental::norm(reference));
}

[[nodiscard]] double affine_dispersion(const std::vector<TransferParticle>& particles) {
    Matrix3d mean_gradient{};
    Vec3d mean_intercept{};
    long double total_mass = 0.0L;
    for (const auto& particle : particles) {
        const auto mass = static_cast<double>(particle.mass_quanta);
        mean_gradient = matrix_add(mean_gradient, mass * particle.affine_velocity_per_s);
        mean_intercept += mass * recovered_intercept(particle);
        total_mass += static_cast<long double>(particle.mass_quanta);
    }
    const auto inverse_mass = 1.0 / static_cast<double>(total_mass);
    mean_gradient = inverse_mass * mean_gradient;
    mean_intercept = inverse_mass * mean_intercept;
    long double gradient_variance = 0.0L;
    long double intercept_variance = 0.0L;
    for (const auto& particle : particles) {
        const auto mass = static_cast<long double>(particle.mass_quanta);
        const auto gradient_delta = mls::experimental::frobenius_norm(
            matrix_subtract(particle.affine_velocity_per_s, mean_gradient));
        const auto intercept_delta = recovered_intercept(particle) - mean_intercept;
        gradient_variance += mass * static_cast<long double>(gradient_delta * gradient_delta);
        intercept_variance += mass * static_cast<long double>(
            mls::experimental::dot(intercept_delta, intercept_delta));
    }
    return std::max(
        std::sqrt(static_cast<double>(gradient_variance / total_mass)),
        std::sqrt(static_cast<double>(intercept_variance / total_mass)));
}

[[nodiscard]] double grid_reconstruction_error(
    const TransferGrid& grid, const AffineField& field) {
    long double weighted_error = 0.0L;
    long double weighted_reference = 0.0L;
    long double total_mass = 0.0L;
    for (const auto& [index, node] : grid.nodes) {
        const Vec3d position{
            grid.config.grid_origin_m.x + static_cast<double>(index.x) * grid.config.grid_spacing_m,
            grid.config.grid_origin_m.y + static_cast<double>(index.y) * grid.config.grid_spacing_m,
            grid.config.grid_origin_m.z + static_cast<double>(index.z) * grid.config.grid_spacing_m};
        const auto reference = mls::experimental::affine_advection::velocity_at(field, position);
        const auto difference = node.velocity_m_per_s - reference;
        const auto mass = static_cast<long double>(node.mass_kg);
        weighted_error += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        weighted_reference += mass * static_cast<long double>(mls::experimental::dot(reference, reference));
        total_mass += mass;
    }
    return std::sqrt(static_cast<double>(weighted_error / total_mass)) /
        std::max(1.0, std::sqrt(static_cast<double>(weighted_reference / total_mass)));
}

[[nodiscard]] double moving_grid_reconstruction_error(
    const MovingApicStep& step, const AffineField& field) {
    long double weighted_error = 0.0L;
    long double weighted_reference = 0.0L;
    long double total_mass = 0.0L;
    for (const auto& [index, node] : step.grid) {
        static_cast<void>(index);
        const auto reference = mls::experimental::affine_advection::velocity_at(
            field, node.old_position_m);
        const auto difference = node.old_velocity_m_per_s - reference;
        const auto mass = static_cast<long double>(node.mass_kg);
        weighted_error += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        weighted_reference += mass * static_cast<long double>(mls::experimental::dot(reference, reference));
        total_mass += mass;
    }
    return std::sqrt(static_cast<double>(weighted_error / total_mass)) /
        std::max(1.0, std::sqrt(static_cast<double>(weighted_reference / total_mass)));
}

void update_existing_transfer_diagnostics(
    RunResult& result,
    const std::vector<TransferParticle>& before,
    const TransferCycle& cycle,
    const AffineField& reference_field,
    bool include_static_representation) {
    if (include_static_representation) {
        result.max_static_velocity_error = particle_vector_rms_error(
            cycle.particles, before, false);
        result.max_static_affine_error = particle_affine_change(cycle.particles, before);
        result.max_static_grid_error = grid_reconstruction_error(cycle.grid, reference_field);
    }
    result.max_p2g_mass_error = std::max(
        result.max_p2g_mass_error,
        relative_scalar(cycle.particle_before.mass_kg, cycle.grid_after_p2g.mass_kg));
    result.max_p2g_linear_error = std::max(
        result.max_p2g_linear_error,
        relative_vector(cycle.particle_before.linear_momentum_kg_m_per_s,
                        cycle.grid_after_p2g.linear_momentum_kg_m_per_s));
    result.max_p2g_augmented_angular_error = std::max(
        result.max_p2g_augmented_angular_error,
        relative_vector(cycle.particle_before.augmented_angular_kg_m2_per_s,
                        cycle.grid_after_p2g.center_orbital_kg_m2_per_s));
    result.max_g2p_linear_error = std::max(
        result.max_g2p_linear_error,
        relative_vector(cycle.particle_before.linear_momentum_kg_m_per_s,
                        cycle.particle_after.linear_momentum_kg_m_per_s));
    result.max_g2p_augmented_angular_error = std::max(
        result.max_g2p_augmented_angular_error,
        relative_vector(cycle.particle_before.augmented_angular_kg_m2_per_s,
                        cycle.particle_after.augmented_angular_kg_m2_per_s));
    result.max_abs_p2g_center_energy_residual_j = std::max(
        result.max_abs_p2g_center_energy_residual_j,
        std::abs(cycle.grid_after_p2g.center_kinetic_j -
                 cycle.particle_before.center_kinetic_j));
    result.max_abs_p2g_augmented_energy_residual_j = std::max(
        result.max_abs_p2g_augmented_energy_residual_j,
        std::abs(cycle.p2g_numerical_energy_residual_j));
}

void update_moving_transfer_diagnostics(
    RunResult& result,
    const MovingApicStep& step,
    const std::vector<TransferParticle>& static_before,
    const std::vector<TransferParticle>& static_after,
    const AffineField& reference_field) {
    result.max_static_velocity_error = std::max(
        result.max_static_velocity_error,
        particle_vector_rms_error(static_after, static_before, false));
    result.max_static_affine_error = std::max(
        result.max_static_affine_error, particle_affine_change(static_after, static_before));
    result.max_static_grid_error = std::max(
        result.max_static_grid_error, moving_grid_reconstruction_error(step, reference_field));
}

void update_moving_step_invariants(RunResult& result, const MovingApicStep& step) {
    result.max_p2g_mass_error = std::max(
        result.max_p2g_mass_error,
        relative_scalar(step.particle_before.mass_kg, step.grid_after_p2g.mass_kg));
    result.max_p2g_linear_error = std::max(
        result.max_p2g_linear_error,
        relative_vector(step.particle_before.linear_momentum_kg_m_per_s,
                        step.grid_after_p2g.linear_momentum_kg_m_per_s));
    result.max_p2g_augmented_angular_error = std::max(
        result.max_p2g_augmented_angular_error,
        relative_vector(step.particle_before.augmented_angular_kg_m2_per_s,
                        step.grid_after_p2g.center_orbital_kg_m2_per_s));
    result.max_g2p_linear_error = std::max(
        result.max_g2p_linear_error,
        relative_vector(step.grid_after_no_force_evolution.linear_momentum_kg_m_per_s,
                        step.particle_after.linear_momentum_kg_m_per_s));
    result.max_g2p_augmented_angular_error = std::max(
        result.max_g2p_augmented_angular_error,
        relative_vector(step.grid_after_no_force_evolution.center_orbital_kg_m2_per_s,
                        step.particle_after.augmented_angular_kg_m2_per_s));
    result.max_abs_p2g_center_energy_residual_j = std::max(
        result.max_abs_p2g_center_energy_residual_j,
        std::abs(step.p2g_center_energy_residual_j));
    result.max_abs_p2g_augmented_energy_residual_j = std::max(
        result.max_abs_p2g_augmented_energy_residual_j,
        std::abs(step.p2g_augmented_representation_energy_residual_j));
}

[[nodiscard]] RunResult run_path(
    Path path,
    const std::vector<TransferParticle>& initial,
    const TransferConfig& config,
    const AffineField& initial_field,
    std::int64_t count,
    std::int64_t dt_quanta) {
    if (count <= 0) {
        throw std::invalid_argument("path schedule count must be positive");
    }
    RunResult result{};
    result.particles = initial;
    result.analytic_field = initial_field;
    result.exact_mass_initial = mls::experimental::exact_particle_mass_quanta(initial);
    const auto timestep_s = seconds_from_quanta(dt_quanta);

    if (path == Path::jst2017_moving_apic) {
        std::vector<MovingApicParticle> moving;
        moving.reserve(initial.size());
        for (const auto& particle : initial) {
            moving.push_back(
                mls::experimental::affine_advection::initialize_moving_apic_particle(
                    particle, config));
        }
        for (std::int64_t step_index = 0; step_index < count; ++step_index) {
            if (step_index == 0) {
                const auto static_before =
                    mls::experimental::affine_advection::as_transfer_particles(moving, config);
                const auto static_step =
                    mls::experimental::affine_advection::jst2017_moving_apic_no_force_step(
                        moving, config, 0.0);
                const auto static_after =
                    mls::experimental::affine_advection::as_transfer_particles(
                        static_step.particles, config);
                update_moving_transfer_diagnostics(
                    result, static_step, static_before, static_after, result.analytic_field);
            }

            const auto moving_step =
                mls::experimental::affine_advection::jst2017_moving_apic_no_force_step(
                    moving, config, timestep_s);
            update_moving_step_invariants(result, moving_step);
            moving = moving_step.particles;
            result.analytic_field =
                mls::experimental::affine_advection::convected_affine_field(
                    result.analytic_field, timestep_s);
            result.elapsed_quanta += dt_quanta;
        }
        result.particles =
            mls::experimental::affine_advection::as_transfer_particles(moving, config);
        result.exact_mass_terminal =
            mls::experimental::exact_particle_mass_quanta(result.particles);
        return result;
    }

    for (std::int64_t step_index = 0; step_index < count; ++step_index) {
        switch (path) {
        case Path::analytic_ballistic:
            result.particles = mls::experimental::affine_advection::ballistic_step(
                result.particles, timestep_s);
            result.analytic_field =
                mls::experimental::affine_advection::convected_affine_field(
                    result.analytic_field, timestep_s);
            for (auto& particle : result.particles) {
                particle.affine_velocity_per_s = result.analytic_field.gradient_per_s;
            }
            result.elapsed_quanta += dt_quanta;
            break;
        case Path::frozen_static_apic: {
            const auto cycle = mls::experimental::transfer_cycle(
                result.particles, config, TransferCandidate::apic);
            update_existing_transfer_diagnostics(
                result,
                result.particles,
                cycle,
                result.analytic_field,
                step_index == 0);
            result.particles = cycle.particles;
            break;
        }
        case Path::sealed_static_apic_ballistic: {
            const auto diagnostic_cycle = mls::experimental::transfer_cycle(
                result.particles, config, TransferCandidate::apic);
            update_existing_transfer_diagnostics(
                result,
                result.particles,
                diagnostic_cycle,
                result.analytic_field,
                step_index == 0);
            // The state transition itself calls the accepted sealed composition.
            result.particles =
                mls::experimental::affine_advection::sealed_static_apic_ballistic_step(
                    result.particles, config, timestep_s);
            result.analytic_field =
                mls::experimental::affine_advection::convected_affine_field(
                    result.analytic_field, timestep_s);
            result.elapsed_quanta += dt_quanta;
            break;
        }
        case Path::analytic_convected_affine_control: {
            const auto diagnostic_cycle = mls::experimental::transfer_cycle(
                result.particles, config, TransferCandidate::apic);
            update_existing_transfer_diagnostics(
                result,
                result.particles,
                diagnostic_cycle,
                result.analytic_field,
                step_index == 0);
            auto control =
                mls::experimental::affine_advection::analytic_convected_control_step(
                    result.particles,
                    config,
                    result.analytic_field,
                    timestep_s);
            result.particles = std::move(control.particles);
            result.analytic_field = control.field;
            result.elapsed_quanta += dt_quanta;
            break;
        }
        case Path::jst2017_moving_apic:
            throw std::logic_error("moving APIC path reached static dispatch");
        }
    }
    result.exact_mass_terminal =
        mls::experimental::exact_particle_mass_quanta(result.particles);
    if (path == Path::frozen_static_apic) {
        result.max_static_velocity_error =
            particle_vector_rms_error(result.particles, initial, false);
        result.max_static_affine_error = particle_affine_change(result.particles, initial);
    }
    return result;
}

[[nodiscard]] std::vector<TransferParticle> ballistic_reference(
    const std::vector<TransferParticle>& initial, double horizon_s) {
    auto result = initial;
    for (auto& particle : result) {
        particle.position_m += horizon_s * particle.velocity_m_per_s;
    }
    return result;
}

[[nodiscard]] Matrix3d mean_affine(const std::vector<TransferParticle>& particles) {
    Matrix3d result{};
    long double total_mass = 0.0L;
    for (const auto& particle : particles) {
        const auto mass = static_cast<double>(particle.mass_quanta);
        result = matrix_add(result, mass * particle.affine_velocity_per_s);
        total_mass += static_cast<long double>(particle.mass_quanta);
    }
    return (1.0 / static_cast<double>(total_mass)) * result;
}

[[nodiscard]] DiagnosticRow make_row(
    const Family& family,
    Path path,
    std::int64_t schedule_index,
    std::int64_t count,
    std::int64_t dt_quanta,
    double spacing_m,
    const std::vector<TransferParticle>& initial,
    const AffineField& initial_field,
    const RunResult& run) {
    const auto physical = path != Path::frozen_static_apic;
    const auto horizon_s = physical ? seconds_from_quanta(horizon_quanta) : 0.0;
    const auto reference_particles = physical ? ballistic_reference(initial, horizon_s) : initial;
    const auto reference_field = physical
        ? mls::experimental::affine_advection::convected_affine_field(
              initial_field, seconds_from_quanta(horizon_quanta))
        : initial_field;
    const auto phase = phases()[family.phase_index];
    const TransferConfig totals_config{
        spacing_m, phase * spacing_m, kg_per_mass_quantum};
    const auto initial_totals =
        mls::experimental::particle_totals(initial, totals_config);
    const auto terminal_totals =
        mls::experimental::particle_totals(run.particles, totals_config);

    DiagnosticRow row{};
    row.family = family;
    row.path = path;
    row.schedule_index = schedule_index;
    row.step_or_remap_count = count;
    row.dt_quanta = physical ? dt_quanta : 0;
    row.dt_seconds = physical ? seconds_from_quanta(dt_quanta) : 0.0;
    row.spacing_m = spacing_m;
    row.physical_time_applicable = physical;
    row.elapsed_quanta = run.elapsed_quanta;
    row.exact_mass_ok = run.exact_mass_initial == run.exact_mass_terminal;
    row.exact_clock_ok = physical ? run.elapsed_quanta == horizon_quanta
                                  : run.elapsed_quanta == 0;
    if (path != Path::analytic_ballistic) {
        row.static_velocity_error = run.max_static_velocity_error;
        row.static_affine_error = run.max_static_affine_error;
        row.static_grid_error = run.max_static_grid_error;
    }
    if (path != Path::frozen_static_apic) {
        row.affine_gradient_error =
            affine_gradient_error(run.particles, reference_field.gradient_per_s);
        row.affine_intercept_error =
            affine_intercept_error(run.particles, reference_field.offset_m_per_s);
        row.affine_dispersion_error = affine_dispersion(run.particles);
        row.trajectory_position_error =
            particle_vector_rms_error(run.particles, reference_particles, true);
        row.material_velocity_error =
            particle_vector_rms_error(run.particles, reference_particles, false);
        row.linear_momentum_error = relative_vector(
            initial_totals.linear_momentum_kg_m_per_s,
            terminal_totals.linear_momentum_kg_m_per_s);
        row.center_orbital_error = relative_vector(
            initial_totals.center_orbital_kg_m2_per_s,
            terminal_totals.center_orbital_kg_m2_per_s);
        row.center_kinetic_error = relative_scalar(
            initial_totals.center_kinetic_j, terminal_totals.center_kinetic_j);
    }
    if (path == Path::sealed_static_apic_ballistic && count == 1) {
        const auto exact_stale_defect = matrix_subtract(
            initial_field.gradient_per_s, reference_field.gradient_per_s);
        const auto observed_defect = matrix_subtract(
            mean_affine(run.particles), reference_field.gradient_per_s);
        row.stale_gradient_witness_error = relative_matrix(
            observed_defect, exact_stale_defect);
    }
    row.max_p2g_mass_error = run.max_p2g_mass_error;
    row.max_p2g_linear_error = run.max_p2g_linear_error;
    row.max_p2g_augmented_angular_error = run.max_p2g_augmented_angular_error;
    row.max_g2p_linear_error = run.max_g2p_linear_error;
    row.max_g2p_augmented_angular_error = run.max_g2p_augmented_angular_error;
    row.max_abs_p2g_center_energy_residual_j = run.max_abs_p2g_center_energy_residual_j;
    row.max_abs_p2g_augmented_energy_residual_j =
        run.max_abs_p2g_augmented_energy_residual_j;
    row.terminal_affine_auxiliary_energy_j = terminal_totals.affine_auxiliary_kinetic_j;
    row.terminal_augmented_representation_energy_j = terminal_totals.augmented_kinetic_j;
    return row;
}

[[nodiscard]] std::vector<SanityRow> run_single_particle_sanity(
    bool smoke, Csv& csv) {
    csv.write(
        "mode,seed,field,phase_index,orientation_index,orientation,dt_quanta,dt_seconds,"
        "steps,exact_mass_ok,exact_clock_ok,position_error,velocity_error,B_error,"
        "center_physical_kinetic_error,pass\n");
    std::vector<SanityRow> rows;
    const auto all_fields = fields();
    const auto all_phases = phases();
    const auto all_orientations = orientations();
    const auto all_dt = dt_quanta_values();
    const auto field_count = smoke ? std::size_t{1} : all_fields.size();
    const auto phase_count = smoke ? std::size_t{1} : all_phases.size();
    const auto orientation_count = smoke ? std::size_t{1} : all_orientations.size();
    for (std::size_t field_index = 0; field_index < field_count; ++field_index) {
        for (std::size_t phase_index = 0; phase_index < phase_count; ++phase_index) {
            for (std::size_t orientation_index = 0;
                 orientation_index < orientation_count;
                 ++orientation_index) {
                const auto& orientation = all_orientations[orientation_index];
                const auto field = oriented_field(all_fields[field_index], orientation);
                const auto position = mls::experimental::multiply(
                    orientation.matrix, Vec3d{0.483, -0.557, 0.609});
                const TransferConfig config{
                    core_spacing_m,
                    all_phases[phase_index] * core_spacing_m,
                    kg_per_mass_quantum};
                TransferParticle source{
                    1,
                    13,
                    position,
                    mls::experimental::affine_advection::velocity_at(field, position),
                    field.gradient_per_s};
                for (const auto dt_quanta : all_dt) {
                    const auto steps = horizon_quanta / dt_quanta;
                    auto particle =
                        mls::experimental::affine_advection::initialize_moving_apic_particle(
                            source, config);
                    const auto initial = particle;
                    std::int64_t elapsed = 0;
                    bool exact_mass_ok = true;
                    for (std::int64_t step_index = 0; step_index < steps; ++step_index) {
                        const auto step =
                            mls::experimental::affine_advection::jst2017_moving_apic_no_force_step(
                                std::array{particle}, config, seconds_from_quanta(dt_quanta));
                        exact_mass_ok = exact_mass_ok &&
                            step.exact_mass_quanta_before == step.exact_mass_quanta_after;
                        particle = step.particles.front();
                        elapsed += dt_quanta;
                    }
                    const auto expected_position =
                        initial.position_m + seconds_from_quanta(horizon_quanta) *
                            initial.velocity_m_per_s;
                    const auto position_error = relative_vector(particle.position_m, expected_position);
                    const auto velocity_error = relative_vector(
                        particle.velocity_m_per_s, initial.velocity_m_per_s);
                    const auto B_error = relative_matrix(particle.B_m2_per_s, initial.B_m2_per_s);
                    const auto initial_energy = 0.5 * static_cast<double>(source.mass_quanta) *
                        kg_per_mass_quantum *
                        mls::experimental::dot(source.velocity_m_per_s, source.velocity_m_per_s);
                    const auto terminal_energy = 0.5 * static_cast<double>(source.mass_quanta) *
                        kg_per_mass_quantum *
                        mls::experimental::dot(
                            particle.velocity_m_per_s, particle.velocity_m_per_s);
                    const auto energy_error = relative_scalar(initial_energy, terminal_energy);
                    const auto exact_clock_ok = elapsed == horizon_quanta;
                    const auto pass = exact_mass_ok && exact_clock_ok &&
                        position_error <= horizon_tolerance &&
                        velocity_error <= horizon_tolerance && B_error <= horizon_tolerance &&
                        energy_error <= horizon_tolerance;
                    SanityRow row{
                        all_fields[field_index],
                        phase_index,
                        orientation_index,
                        dt_quanta,
                        steps,
                        exact_mass_ok,
                        exact_clock_ok,
                        position_error,
                        velocity_error,
                        B_error,
                        energy_error,
                        pass};
                    rows.push_back(row);
                    csv.row({
                        smoke ? "smoke" : "full",
                        to_text(seed),
                        std::string(field_name(row.field)),
                        to_text(row.phase_index),
                        to_text(row.orientation_index),
                        orientation.label,
                        to_text(row.dt_quanta),
                        format_double(seconds_from_quanta(row.dt_quanta)),
                        to_text(row.steps),
                        to_text(row.exact_mass_ok),
                        to_text(row.exact_clock_ok),
                        format_double(row.position_error),
                        format_double(row.velocity_error),
                        format_double(row.B_error),
                        format_double(row.center_energy_error),
                        to_text(row.pass)});
                }
            }
        }
    }
    return rows;
}

void write_diagnostic_header(Csv& csv) {
    csv.write(
        "mode,seed,scope,path,field,phase_index,orientation_index,orientation,layout,"
        "mass_ratio,schedule_index,step_or_remap_count,grid_spacing_m,dt_quanta,dt_seconds,"
        "physical_time_applicable,elapsed_quanta,exact_mass_ok,exact_clock_ok,"
        "static_representation_applicable,static_velocity_error,static_affine_error,"
        "static_grid_error,affine_advection_applicable,affine_gradient_error,"
        "affine_intercept_error,affine_dispersion_error,stale_witness_applicable,"
        "stale_gradient_witness_error,trajectory_applicable,trajectory_position_error,"
        "material_velocity_error,linear_momentum_error,center_orbital_error,"
        "center_physical_kinetic_error,max_p2g_mass_error,max_p2g_linear_error,"
        "max_p2g_paper_augmented_angular_error,max_g2p_linear_error,"
        "max_g2p_paper_augmented_angular_error,max_abs_p2g_center_energy_residual_j,"
        "max_abs_p2g_augmented_representation_energy_residual_j,"
        "terminal_affine_auxiliary_energy_diagnostic_j,"
        "terminal_augmented_representation_energy_diagnostic_j\n");
}

void write_diagnostic_row(
    Csv& csv,
    bool smoke,
    std::string_view scope,
    const DiagnosticRow& row,
    const Orientation& orientation) {
    csv.row({
        smoke ? "smoke" : "full",
        to_text(seed),
        std::string(scope),
        std::string(mls::experimental::affine_advection::path_name(row.path)),
        std::string(field_name(row.family.field)),
        to_text(row.family.phase_index),
        to_text(row.family.orientation_index),
        orientation.label,
        std::string(layout_name(row.family.layout)),
        to_text(row.family.mass_ratio),
        to_text(row.schedule_index),
        to_text(row.step_or_remap_count),
        format_double(row.spacing_m),
        to_text(row.dt_quanta),
        format_double(row.dt_seconds),
        to_text(row.physical_time_applicable),
        to_text(row.elapsed_quanta),
        to_text(row.exact_mass_ok),
        to_text(row.exact_clock_ok),
        to_text(row.static_velocity_error.has_value()),
        format_optional(row.static_velocity_error),
        format_optional(row.static_affine_error),
        format_optional(row.static_grid_error),
        to_text(row.affine_gradient_error.has_value()),
        format_optional(row.affine_gradient_error),
        format_optional(row.affine_intercept_error),
        format_optional(row.affine_dispersion_error),
        to_text(row.stale_gradient_witness_error.has_value()),
        format_optional(row.stale_gradient_witness_error),
        to_text(row.trajectory_position_error.has_value()),
        format_optional(row.trajectory_position_error),
        format_optional(row.material_velocity_error),
        format_optional(row.linear_momentum_error),
        format_optional(row.center_orbital_error),
        format_optional(row.center_kinetic_error),
        format_double(row.max_p2g_mass_error),
        format_double(row.max_p2g_linear_error),
        format_double(row.max_p2g_augmented_angular_error),
        format_double(row.max_g2p_linear_error),
        format_double(row.max_g2p_augmented_angular_error),
        format_double(row.max_abs_p2g_center_energy_residual_j),
        format_double(row.max_abs_p2g_augmented_energy_residual_j),
        format_double(row.terminal_affine_auxiliary_energy_j),
        format_double(row.terminal_augmented_representation_energy_j)});
}

[[nodiscard]] std::vector<DiagnosticRow> run_core_sweep(bool smoke, Csv& csv) {
    write_diagnostic_header(csv);
    std::vector<DiagnosticRow> rows;
    const auto all_fields = fields();
    const auto all_phases = phases();
    const auto all_orientations = orientations();
    const auto all_layouts = layout_mass_pairs();
    const auto field_count = smoke ? std::size_t{1} : all_fields.size();
    const auto phase_count = smoke ? std::size_t{1} : all_phases.size();
    const auto orientation_count = smoke ? std::size_t{1} : all_orientations.size();
    const auto layout_count = smoke ? std::size_t{1} : all_layouts.size();
    for (std::size_t field_index = 0; field_index < field_count; ++field_index) {
        for (std::size_t phase_index = 0; phase_index < phase_count; ++phase_index) {
            for (std::size_t orientation_index = 0;
                 orientation_index < orientation_count;
                 ++orientation_index) {
                const auto& orientation = all_orientations[orientation_index];
                const auto field = oriented_field(all_fields[field_index], orientation);
                for (std::size_t layout_index = 0; layout_index < layout_count; ++layout_index) {
                    const auto layout_mass = all_layouts[layout_index];
                    const Family family{
                        all_fields[field_index],
                        phase_index,
                        orientation_index,
                        layout_mass.layout,
                        layout_mass.mass_ratio};
                    const auto initial = make_particles(family, orientation, field);
                    const TransferConfig config{
                        core_spacing_m,
                        all_phases[phase_index] * core_spacing_m,
                        kg_per_mass_quantum};
                    for (const auto path : paths()) {
                        const auto dt_values = dt_quanta_values();
                        for (std::size_t schedule_index = 0;
                             schedule_index < dt_values.size();
                             ++schedule_index) {
                            const auto dt_quanta = dt_values[schedule_index];
                            const auto count = horizon_quanta / dt_quanta;
                            const auto result = run_path(
                                path, initial, config, field, count, dt_quanta);
                            const auto row = make_row(
                                family,
                                path,
                                static_cast<std::int64_t>(schedule_index),
                                count,
                                dt_quanta,
                                core_spacing_m,
                                initial,
                                field,
                                result);
                            rows.push_back(row);
                            write_diagnostic_row(csv, smoke, "core", row, orientation);
                        }
                    }
                }
            }
        }
    }
    return rows;
}

[[nodiscard]] std::vector<DiagnosticRow> run_coupled_sweep(bool smoke, Csv& csv) {
    write_diagnostic_header(csv);
    if (smoke) {
        return {};
    }
    const auto all_phases = phases();
    const auto all_orientations = orientations();
    const auto& orientation = all_orientations[2];
    const Family family{
        FieldKind::general_affine,
        1,
        2,
        LayoutKind::unequal_mass_asymmetric,
        17};
    const auto field = oriented_field(family.field, orientation);
    const auto initial = make_particles(family, orientation, field);
    const std::array<double, 4> spacings{1.0, 0.5, 0.25, 0.125};
    const auto dt_values = dt_quanta_values();
    std::vector<DiagnosticRow> rows;
    for (const auto path : {Path::sealed_static_apic_ballistic,
                            Path::analytic_convected_affine_control,
                            Path::jst2017_moving_apic}) {
        for (std::size_t level = 0; level < spacings.size(); ++level) {
            const auto spacing = spacings[level];
            const auto dt_quanta = dt_values[level];
            const auto count = horizon_quanta / dt_quanta;
            const TransferConfig config{
                spacing,
                all_phases[family.phase_index] * spacing,
                kg_per_mass_quantum};
            const auto result = run_path(path, initial, config, field, count, dt_quanta);
            const auto row = make_row(
                family,
                path,
                static_cast<std::int64_t>(level),
                count,
                dt_quanta,
                spacing,
                initial,
                field,
                result);
            rows.push_back(row);
            write_diagnostic_row(csv, false, "coupled_h_dt", row, orientation);
        }
    }
    return rows;
}

struct ConvergenceEvaluation final {
    bool all_below{false};
    bool ratio_rule{false};
    bool finest_increase_failure{false};
    bool pass{false};
};

[[nodiscard]] ConvergenceEvaluation convergence(
    const std::array<double, 4>& errors, double hard_tolerance) noexcept {
    ConvergenceEvaluation result{};
    result.all_below = std::ranges::all_of(errors, [hard_tolerance](double value) {
        return std::isfinite(value) && value <= hard_tolerance;
    });
    result.finest_increase_failure =
        errors[3] > roundoff_floor &&
        (errors[3] > errors[2] || errors[3] > errors[1] || errors[3] > errors[0]);
    result.ratio_rule = !result.finest_increase_failure &&
        errors[1] <= 0.70 * errors[0] && errors[2] <= 0.70 * errors[1] &&
        errors[3] <= 0.70 * errors[2] && errors[3] <= 0.125 * errors[0];
    result.pass = result.all_below || result.ratio_rule;
    return result;
}

using MetricAccessor = std::optional<double> DiagnosticRow::*;

struct MetricSpec final {
    std::string_view name{};
    MetricAccessor member{};
    double tolerance{horizon_tolerance};
};

[[nodiscard]] std::vector<MetricSpec> metric_specs(Path path, FieldKind field) {
    const auto static_tolerance = field == FieldKind::translation
        ? 2.0e-12
        : one_remap_affine_tolerance;
    if (path == Path::analytic_ballistic) {
        return {
            {"trajectory_position", &DiagnosticRow::trajectory_position_error, horizon_tolerance},
            {"material_velocity", &DiagnosticRow::material_velocity_error, horizon_tolerance},
            {"linear_momentum", &DiagnosticRow::linear_momentum_error, horizon_tolerance},
            {"center_orbital", &DiagnosticRow::center_orbital_error, horizon_tolerance},
            {"center_physical_kinetic", &DiagnosticRow::center_kinetic_error, horizon_tolerance}};
    }
    if (path == Path::frozen_static_apic) {
        return {
            {"static_velocity", &DiagnosticRow::static_velocity_error, static_tolerance},
            {"static_affine", &DiagnosticRow::static_affine_error, static_tolerance},
            {"static_grid", &DiagnosticRow::static_grid_error, static_tolerance}};
    }
    return {
        {"static_velocity", &DiagnosticRow::static_velocity_error, static_tolerance},
        {"static_affine", &DiagnosticRow::static_affine_error, static_tolerance},
        {"static_grid", &DiagnosticRow::static_grid_error, static_tolerance},
        {"affine_gradient", &DiagnosticRow::affine_gradient_error, horizon_tolerance},
        {"affine_intercept", &DiagnosticRow::affine_intercept_error, horizon_tolerance},
        {"affine_dispersion", &DiagnosticRow::affine_dispersion_error, horizon_tolerance},
        {"trajectory_position", &DiagnosticRow::trajectory_position_error, horizon_tolerance},
        {"material_velocity", &DiagnosticRow::material_velocity_error, horizon_tolerance},
        {"linear_momentum", &DiagnosticRow::linear_momentum_error, horizon_tolerance},
        {"center_orbital", &DiagnosticRow::center_orbital_error, horizon_tolerance},
        {"center_physical_kinetic", &DiagnosticRow::center_kinetic_error, horizon_tolerance}};
}

[[nodiscard]] std::uint64_t write_convergence_rows(
    Csv& csv,
    bool smoke,
    std::string_view scope,
    const std::vector<DiagnosticRow>& rows) {
    using GroupKey = std::pair<Family, Path>;
    std::map<GroupKey, std::array<const DiagnosticRow*, 4>> groups;
    for (const auto& row : rows) {
        auto& group = groups[{row.family, row.path}];
        if (row.schedule_index < 0 || row.schedule_index >= 4) {
            throw std::logic_error("invalid convergence schedule index");
        }
        group[static_cast<std::size_t>(row.schedule_index)] = &row;
    }
    std::uint64_t written = 0;
    const auto all_orientations = orientations();
    for (const auto& [key, group] : groups) {
        if (!std::ranges::all_of(group, [](const DiagnosticRow* row) { return row != nullptr; })) {
            throw std::runtime_error("incomplete affine convergence family");
        }
        for (const auto& metric : metric_specs(key.second, key.first.field)) {
            std::array<double, 4> values{};
            for (std::size_t level = 0; level < values.size(); ++level) {
                const auto& optional = group[level]->*(metric.member);
                if (!optional.has_value()) {
                    throw std::runtime_error("missing applicable convergence metric");
                }
                values[level] = *optional;
            }
            const auto evaluation = convergence(values, metric.tolerance);
            csv.row({
                smoke ? "smoke" : "full",
                to_text(seed),
                std::string(scope),
                std::string(mls::experimental::affine_advection::path_name(key.second)),
                std::string(field_name(key.first.field)),
                to_text(key.first.phase_index),
                to_text(key.first.orientation_index),
                all_orientations[key.first.orientation_index].label,
                std::string(layout_name(key.first.layout)),
                to_text(key.first.mass_ratio),
                std::string(metric.name),
                format_double(metric.tolerance),
                format_double(values[0]),
                format_double(values[1]),
                format_double(values[2]),
                format_double(values[3]),
                to_text(evaluation.all_below),
                to_text(evaluation.ratio_rule),
                to_text(evaluation.finest_increase_failure),
                to_text(evaluation.pass)});
            ++written;
        }
    }
    return written;
}

void write_convergence_header(Csv& csv) {
    csv.write(
        "mode,seed,scope,path,field,phase_index,orientation_index,orientation,layout,"
        "mass_ratio,metric,hard_tolerance,error_level_0,error_level_1,error_level_2,"
        "error_level_3,all_below,ratio_rule,finest_increase_failure,pass\n");
}

[[nodiscard]] std::map<Family, std::array<const DiagnosticRow*, 4>> path_groups(
    const std::vector<DiagnosticRow>& rows, Path path) {
    std::map<Family, std::array<const DiagnosticRow*, 4>> result;
    for (const auto& row : rows) {
        if (row.path != path) {
            continue;
        }
        result[row.family][static_cast<std::size_t>(row.schedule_index)] = &row;
    }
    for (const auto& [family, group] : result) {
        static_cast<void>(family);
        if (!std::ranges::all_of(group, [](const DiagnosticRow* row) { return row != nullptr; })) {
            throw std::runtime_error("incomplete path decision family");
        }
    }
    return result;
}

[[nodiscard]] bool primary_row_below(const DiagnosticRow& row, double tolerance) {
    return row.trajectory_position_error.value_or(std::numeric_limits<double>::infinity()) <=
            tolerance &&
        row.material_velocity_error.value_or(std::numeric_limits<double>::infinity()) <=
            tolerance &&
        row.affine_gradient_error.value_or(std::numeric_limits<double>::infinity()) <=
            tolerance &&
        row.affine_intercept_error.value_or(std::numeric_limits<double>::infinity()) <=
            tolerance &&
        row.affine_dispersion_error.value_or(std::numeric_limits<double>::infinity()) <=
            tolerance;
}

struct CausalSummary final {
    std::uint64_t translation_families{0};
    std::uint64_t translation_passes{0};
    std::uint64_t rotation_families{0};
    std::uint64_t rotation_defect_positive{0};
    std::uint64_t affine_families{0};
    std::uint64_t affine_defect_positive{0};
    std::uint64_t d_families{0};
    std::uint64_t d_removal_passes{0};
    bool c_reproduces{false};
    bool d_removes{false};
    std::string numerical_result{"not evaluated"};
};

[[nodiscard]] CausalSummary causal_summary(const std::vector<DiagnosticRow>& rows) {
    const auto c_groups = path_groups(rows, Path::sealed_static_apic_ballistic);
    const auto d_groups = path_groups(rows, Path::analytic_convected_affine_control);
    CausalSummary result{};
    for (const auto& [family, group] : c_groups) {
        if (family.field == FieldKind::translation) {
            ++result.translation_families;
            const auto pass = std::ranges::all_of(group, [](const DiagnosticRow* row) {
                return primary_row_below(*row, horizon_tolerance);
            });
            if (pass) {
                ++result.translation_passes;
            }
            continue;
        }
        auto& families = family.field == FieldKind::rigid_rotation
            ? result.rotation_families
            : result.affine_families;
        auto& positives = family.field == FieldKind::rigid_rotation
            ? result.rotation_defect_positive
            : result.affine_defect_positive;
        ++families;
        const auto coarse_position = group[0]->trajectory_position_error.value();
        const auto coarse_velocity = group[0]->material_velocity_error.value();
        const auto finest_velocity = group[3]->material_velocity_error.value();
        const std::array<double, 4> velocity_errors{
            group[0]->material_velocity_error.value(),
            group[1]->material_velocity_error.value(),
            group[2]->material_velocity_error.value(),
            group[3]->material_velocity_error.value()};
        const auto finer_resolved = std::ranges::any_of(
            velocity_errors.begin() + 1,
            velocity_errors.end(),
            [](double value) { return value > horizon_tolerance; });
        const auto witness_pass = group[0]->stale_gradient_witness_error.has_value() &&
            group[0]->stale_gradient_witness_error.value() <= one_remap_affine_tolerance;
        const auto velocity_convergence = convergence(velocity_errors, horizon_tolerance);
        const auto defect_positive = coarse_position <= horizon_tolerance &&
            coarse_velocity <= horizon_tolerance && witness_pass && finer_resolved &&
            finest_velocity >= 10.0 * std::max(roundoff_floor, coarse_velocity) &&
            !velocity_convergence.pass;
        if (defect_positive) {
            ++positives;
        }
    }
    result.c_reproduces =
        result.translation_families > 0U &&
        result.translation_passes == result.translation_families &&
        result.rotation_defect_positive + 1U >= result.rotation_families &&
        result.affine_defect_positive + 1U >= result.affine_families;

    for (const auto& [family, d_group] : d_groups) {
        ++result.d_families;
        const auto found_c = c_groups.find(family);
        if (found_c == c_groups.end()) {
            throw std::runtime_error("Path D family lacks Path C control");
        }
        const auto& c_group = found_c->second;
        bool pass = std::ranges::all_of(d_group, [](const DiagnosticRow* row) {
            return primary_row_below(*row, horizon_tolerance);
        });
        const auto c_finest = c_group[3]->material_velocity_error.value();
        const auto d_finest = d_group[3]->material_velocity_error.value();
        if (c_finest > horizon_tolerance) {
            pass = pass && d_finest <= 0.1 * c_finest;
        }
        if (pass) {
            ++result.d_removal_passes;
        }
    }
    result.d_removes =
        result.d_families > 0U && result.d_removal_passes == result.d_families;
    result.numerical_result = result.c_reproduces && result.d_removes
        ? "causally_supported_pending_external_gates"
        : "hypothesis_rejected_by_preregistered_numerical_rule";
    return result;
}

[[nodiscard]] std::uint64_t convergence_failures(
    const std::vector<DiagnosticRow>& rows, Path path) {
    const auto groups = path_groups(rows, path);
    std::uint64_t failures = 0;
    for (const auto& [family, group] : groups) {
        for (const auto& metric : metric_specs(path, family.field)) {
            std::array<double, 4> values{};
            for (std::size_t level = 0; level < values.size(); ++level) {
                const auto& optional = group[level]->*(metric.member);
                if (!optional.has_value()) {
                    ++failures;
                    continue;
                }
                values[level] = *optional;
            }
            if (!convergence(values, metric.tolerance).pass) {
                ++failures;
            }
        }
    }
    return failures;
}

struct ESummary final {
    std::uint64_t sanity_rows{0};
    std::uint64_t sanity_failures{0};
    std::uint64_t exact_failures{0};
    std::uint64_t transfer_contract_failures{0};
    std::uint64_t static_failures{0};
    std::uint64_t core_convergence_failures{0};
    std::uint64_t coupled_convergence_failures{0};
    bool passes{false};
};

[[nodiscard]] ESummary e_summary(
    const std::vector<SanityRow>& sanity,
    const std::vector<DiagnosticRow>& core,
    const std::vector<DiagnosticRow>& coupled) {
    ESummary result{};
    result.sanity_rows = static_cast<std::uint64_t>(sanity.size());
    result.sanity_failures = static_cast<std::uint64_t>(std::ranges::count_if(
        sanity, [](const SanityRow& row) { return !row.pass; }));
    for (const auto& row : core) {
        if (row.path != Path::jst2017_moving_apic) {
            continue;
        }
        if (!row.exact_mass_ok || !row.exact_clock_ok) {
            ++result.exact_failures;
        }
        if (row.max_p2g_mass_error > mass_tolerance ||
            row.max_p2g_linear_error > linear_tolerance ||
            row.max_p2g_augmented_angular_error > angular_tolerance ||
            row.max_g2p_linear_error > linear_tolerance ||
            row.max_g2p_augmented_angular_error > angular_tolerance) {
            ++result.transfer_contract_failures;
        }
        const auto static_tolerance = row.family.field == FieldKind::translation
            ? 2.0e-12
            : one_remap_affine_tolerance;
        if (row.static_velocity_error.value() > static_tolerance ||
            row.static_affine_error.value() > static_tolerance ||
            row.static_grid_error.value() > static_tolerance) {
            ++result.static_failures;
        }
    }
    result.core_convergence_failures =
        convergence_failures(core, Path::jst2017_moving_apic);
    result.coupled_convergence_failures = coupled.empty()
        ? 0U
        : convergence_failures(coupled, Path::jst2017_moving_apic);
    result.passes = result.sanity_failures == 0U && result.exact_failures == 0U &&
        result.transfer_contract_failures == 0U && result.static_failures == 0U &&
        result.core_convergence_failures == 0U &&
        result.coupled_convergence_failures == 0U;
    return result;
}

void write_summary(
    const std::filesystem::path& path,
    bool smoke,
    std::uint64_t sanity_rows,
    std::uint64_t core_rows,
    std::uint64_t coupled_rows,
    std::uint64_t convergence_rows,
    bool sanity_gate_pass,
    const std::optional<CausalSummary>& causal,
    const std::optional<ESummary>& paper) {
    const auto expected_sanity = smoke ? std::uint64_t{4} : std::uint64_t{72};
    const auto expected_core = smoke ? std::uint64_t{20} : std::uint64_t{1080};
    const auto expected_coupled = smoke ? std::uint64_t{0} : std::uint64_t{12};
    const auto expected_convergence = smoke ? std::uint64_t{41} : std::uint64_t{2247};
    const auto complete = sanity_rows == expected_sanity && core_rows == expected_core &&
        coupled_rows == expected_coupled && convergence_rows == expected_convergence;
    std::ofstream output(path, std::ios::binary);
    output.exceptions(std::ios::badbit | std::ios::failbit);
    output.imbue(std::locale::classic());
    output << "{\n"
           << "  \"schema\": \"mls-affine-advection-diagnostic-v1\",\n"
           << "  \"mode\": \"" << (smoke ? "smoke" : "full") << "\",\n"
           << "  \"selection_or_promotion_evidence\": false,\n"
           << "  \"source_sha_at_configure\": \"" << MLS_CONFIGURED_SOURCE_SHA << "\",\n"
           << "  \"source_branch_at_configure\": \"" << MLS_CONFIGURED_SOURCE_BRANCH << "\",\n"
           << "  \"source_dirty_at_configure\": \"" << MLS_CONFIGURED_SOURCE_DIRTY << "\",\n"
           << "  \"compiler_id\": \"" << MLS_CONFIGURED_COMPILER_ID << "\",\n"
           << "  \"compiler_version\": \"" << MLS_CONFIGURED_COMPILER_VERSION << "\",\n"
           << "  \"seed\": " << seed << ",\n"
           << "  \"time_quantum_seconds\": \"1/80\",\n"
           << "  \"fixed_horizon_seconds\": \"1/10\",\n"
           << "  \"single_particle_gate_pass\": "
           << (sanity_gate_pass ? "true" : "false") << ",\n"
           << "  \"counts_complete\": " << (complete ? "true" : "false") << ",\n"
           << "  \"counts\": {\n"
           << "    \"single_particle_sanity\": {\"expected\": " << expected_sanity
           << ", \"actual\": " << sanity_rows << "},\n"
           << "    \"core_sweep\": {\"expected\": " << expected_core
           << ", \"actual\": " << core_rows << "},\n"
           << "    \"coupled_refinement\": {\"expected\": " << expected_coupled
           << ", \"actual\": " << coupled_rows << "},\n"
           << "    \"convergence\": {\"expected\": " << expected_convergence
           << ", \"actual\": " << convergence_rows << "}\n"
           << "  },\n"
           << "  \"energy_policy\": \"center particle kinetic energy is physical; affine and augmented quantities are diagnostics only\",\n"
           << "  \"path_d_promotion_eligible\": false,\n"
           << "  \"path_e_promotion_eligible\": false,\n";
    if (causal.has_value()) {
        output << "  \"causal_diagnosis\": {\n"
               << "    \"path_c_translation_families\": " << causal->translation_families << ",\n"
               << "    \"path_c_translation_passes\": " << causal->translation_passes << ",\n"
               << "    \"path_c_rotation_families\": " << causal->rotation_families << ",\n"
               << "    \"path_c_rotation_defect_positive\": "
               << causal->rotation_defect_positive << ",\n"
               << "    \"path_c_affine_families\": " << causal->affine_families << ",\n"
               << "    \"path_c_affine_defect_positive\": "
               << causal->affine_defect_positive << ",\n"
               << "    \"path_c_reproduces\": " << (causal->c_reproduces ? "true" : "false") << ",\n"
               << "    \"path_d_families\": " << causal->d_families << ",\n"
               << "    \"path_d_removal_passes\": " << causal->d_removal_passes << ",\n"
               << "    \"path_d_removes\": " << (causal->d_removes ? "true" : "false") << ",\n"
               << "    \"numerical_result\": \"" << causal->numerical_result << "\"\n"
               << "  },\n";
    } else {
        output << "  \"causal_diagnosis\": null,\n";
    }
    if (paper.has_value()) {
        output << "  \"path_e_literature_and_mls_gate\": {\n"
               << "    \"single_particle_rows\": " << paper->sanity_rows << ",\n"
               << "    \"single_particle_failures\": " << paper->sanity_failures << ",\n"
               << "    \"exact_failures\": " << paper->exact_failures << ",\n"
               << "    \"paper_transfer_contract_failures\": "
               << paper->transfer_contract_failures << ",\n"
               << "    \"static_representation_failures\": " << paper->static_failures << ",\n"
               << "    \"core_convergence_failures\": "
               << paper->core_convergence_failures << ",\n"
               << "    \"coupled_convergence_failures\": "
               << paper->coupled_convergence_failures << ",\n"
               << "    \"passes\": " << (paper->passes ? "true" : "false") << "\n"
               << "  },\n";
    } else {
        output << "  \"path_e_literature_and_mls_gate\": null,\n";
    }
    output << "  \"overall_recommendation\": \"no promotion; stop for head-agent review\",\n"
           << "  \"external_gates_required\": [\"clean source\", \"byte-identical rerun\", \"independent verifier\", \"C++\", \"Python exact oracle\", \"Lean/axioms\", \"CI\"],\n"
           << "  \"excluded\": [\"stress\", \"forces\", \"gravity\", \"elasticity\", \"contact\", \"fracture\", \"diffusion\", \"reaction kinetics\", \"organisms\", \"rendering\", \"GPU work\"]\n"
           << "}\n";
}

[[nodiscard]] Options parse_options(int argc, char** argv) {
    Options options{};
    for (int index = 1; index < argc; ++index) {
        const std::string_view argument{argv[index]};
        if (argument == "--smoke") {
            options.smoke = true;
        } else if (argument == "--output") {
            if (index + 1 >= argc) {
                throw std::invalid_argument("--output requires a directory");
            }
            options.output = argv[++index];
        } else if (argument == "--help") {
            std::cout << "Usage: mls_affine_advection_diagnostic [--smoke] [--output DIRECTORY]\n";
            std::exit(EXIT_SUCCESS);
        } else {
            throw std::invalid_argument("unknown argument: " + std::string(argument));
        }
    }
    if (options.output.empty()) {
        throw std::invalid_argument("output directory must not be empty");
    }
    return options;
}

int run(const Options& options) {
    std::filesystem::create_directories(options.output);
    Csv sanity_csv(options.output / "single_particle_sanity.csv");
    const auto sanity = run_single_particle_sanity(options.smoke, sanity_csv);
    const auto sanity_gate_pass =
        std::ranges::all_of(sanity, [](const SanityRow& row) { return row.pass; });
    if (!sanity_gate_pass) {
        write_summary(
            options.output / "summary.json",
            options.smoke,
            sanity_csv.rows(),
            0,
            0,
            0,
            false,
            std::nullopt,
            std::nullopt);
        std::cerr << "mls_affine_advection_diagnostic: single-particle gate failed; multiparticle sweep refused\n";
        return EXIT_FAILURE;
    }

    Csv core_csv(options.output / "core_sweep.csv");
    const auto core = run_core_sweep(options.smoke, core_csv);
    Csv coupled_csv(options.output / "coupled_refinement.csv");
    const auto coupled = run_coupled_sweep(options.smoke, coupled_csv);
    Csv convergence_csv(options.output / "convergence.csv");
    write_convergence_header(convergence_csv);
    auto convergence_rows = write_convergence_rows(
        convergence_csv, options.smoke, "core", core);
    convergence_rows += write_convergence_rows(
        convergence_csv, options.smoke, "coupled_h_dt", coupled);

    const auto expected_sanity = options.smoke ? std::uint64_t{4} : std::uint64_t{72};
    const auto expected_core = options.smoke ? std::uint64_t{20} : std::uint64_t{1080};
    const auto expected_coupled = options.smoke ? std::uint64_t{0} : std::uint64_t{12};
    const auto expected_convergence = options.smoke ? std::uint64_t{41} : std::uint64_t{2247};
    if (sanity_csv.rows() != expected_sanity || core_csv.rows() != expected_core ||
        coupled_csv.rows() != expected_coupled || convergence_rows != expected_convergence) {
        throw std::runtime_error("diagnostic Cartesian-product row counts are incomplete");
    }
    const auto causal = options.smoke
        ? std::optional<CausalSummary>{}
        : std::optional<CausalSummary>{causal_summary(core)};
    const auto paper = options.smoke
        ? std::optional<ESummary>{}
        : std::optional<ESummary>{e_summary(sanity, core, coupled)};
    write_summary(
        options.output / "summary.json",
        options.smoke,
        sanity_csv.rows(),
        core_csv.rows(),
        coupled_csv.rows(),
        convergence_rows,
        sanity_gate_pass,
        causal,
        paper);
    std::cout << "Affine Advection " << (options.smoke ? "smoke" : "full")
              << " diagnostic evidence written to " << options.output.string() << '\n';
    return EXIT_SUCCESS;
}

} // namespace

int main(int argc, char** argv) {
    try {
        return run(parse_options(argc, argv));
    } catch (const std::exception& error) {
        std::cerr << "mls_affine_advection_diagnostic: " << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
