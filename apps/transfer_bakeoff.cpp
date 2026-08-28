#include "mls/transfer_lab.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <compare>
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
#include <vector>

#ifndef MLS_CONFIGURED_SOURCE_SHA
#define MLS_CONFIGURED_SOURCE_SHA "unknown"
#endif
#ifndef MLS_CONFIGURED_SOURCE_BRANCH
#define MLS_CONFIGURED_SOURCE_BRANCH "unknown"
#endif
#ifndef MLS_CONFIGURED_SOURCE_DIRTY
#define MLS_CONFIGURED_SOURCE_DIRTY "unknown"
#endif
#ifndef MLS_CONFIGURED_COMPILER_ID
#define MLS_CONFIGURED_COMPILER_ID "unknown"
#endif
#ifndef MLS_CONFIGURED_COMPILER_VERSION
#define MLS_CONFIGURED_COMPILER_VERSION "unknown"
#endif

namespace {

using mls::experimental::GridNode;
using mls::experimental::Matrix3d;
using mls::experimental::TransferCandidate;
using mls::experimental::TransferConfig;
using mls::experimental::TransferCycle;
using mls::experimental::TransferGrid;
using mls::experimental::TransferParticle;
using mls::experimental::TransferTotals;
using mls::experimental::Vec3d;

constexpr std::uint64_t seed = 260828;
constexpr std::int64_t time_quantum_seconds_numerator = 1;
constexpr std::int64_t time_quantum_seconds_denominator = 40;
constexpr std::int64_t fixed_horizon_time_quanta = 4;
constexpr double kg_per_mass_quantum = 0.125;
constexpr double mass_tolerance = 2.0e-13;
constexpr double linear_momentum_tolerance = 2.0e-12;
constexpr double angular_momentum_tolerance = 2.0e-11;
constexpr double translation_reconstruction_tolerance = 2.0e-12;
constexpr double apic_affine_reconstruction_tolerance = 5.0e-11;
constexpr double repeated_claim_tolerance = 2.0e-9;
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

struct Options final {
    bool smoke{false};
    std::filesystem::path output{"evidence/time-transfer-bakeoff"};
};

struct Orientation final {
    Matrix3d matrix{};
    std::string label{};
};

struct FieldSpec final {
    FieldKind kind{FieldKind::translation};
    Matrix3d gradient_per_s{};
    Vec3d center_m{};
    Vec3d translation_m_per_s{};
};

struct Observation final {
    TransferTotals initial{};
    TransferTotals grid{};
    TransferTotals terminal{};
    std::int64_t exact_mass_initial{0};
    std::int64_t exact_mass_terminal{0};
    bool exact_mass_ok{true};
    double max_p2g_mass_relative{0.0};
    double max_p2g_linear_relative{0.0};
    double max_p2g_center_orbital_relative{0.0};
    double max_p2g_angular_relative{0.0};
    double max_roundtrip_mass_relative{0.0};
    double max_roundtrip_linear_relative{0.0};
    double max_roundtrip_center_orbital_relative{0.0};
    double max_roundtrip_claimed_angular_relative{0.0};
    double cumulative_linear_relative{0.0};
    double cumulative_center_orbital_relative{0.0};
    double cumulative_declared_angular_relative{0.0};
    double max_abs_p2g_energy_relative{0.0};
    double max_abs_roundtrip_energy_relative{0.0};
    double max_abs_p2g_center_energy_relative{0.0};
    double max_abs_roundtrip_center_energy_relative{0.0};
    double final_p2g_energy_residual_j{0.0};
    double final_p2g_energy_relative{0.0};
    double final_roundtrip_energy_residual_j{0.0};
    double final_roundtrip_energy_relative{0.0};
    double final_p2g_center_energy_residual_j{0.0};
    double final_p2g_center_energy_relative{0.0};
    double final_roundtrip_center_energy_residual_j{0.0};
    double final_roundtrip_center_energy_relative{0.0};
    double cumulative_energy_residual_j{0.0};
    double cumulative_energy_relative{0.0};
    double cumulative_center_energy_residual_j{0.0};
    double cumulative_center_energy_relative{0.0};
    double grid_reconstruction_relative{0.0};
    double particle_reconstruction_relative{0.0};
    double affine_reconstruction_relative{0.0};
    bool affine_reconstruction_applicable{false};
    bool claimed_contract_pass{false};
    bool center_orbital_diagnostic_pass{false};
};

struct HGroupKey final {
    TransferCandidate candidate{};
    FieldKind field{};
    std::uint8_t phase_index{0};
    std::uint8_t orientation_index{0};
    LayoutKind layout{};
    std::int64_t mass_ratio{1};
    std::int64_t cycles{1};
    std::int64_t dt_quanta{4};

    [[nodiscard]] auto operator<=>(const HGroupKey&) const noexcept = default;
};

struct HGroup final {
    std::array<double, 3> particle_reconstruction{};
    std::array<double, 3> grid_reconstruction{};
    std::array<double, 3> candidate_augmented_energy{};
    std::array<double, 3> center_energy{};
    std::array<double, 3> affine_matrix_reconstruction{};
    std::array<bool, 3> present{};
};

struct TimeGroupKey final {
    TransferCandidate candidate{};
    FieldKind field{};
    std::uint8_t phase_index{0};
    std::uint8_t orientation_index{0};
    LayoutKind layout{};
    std::uint8_t spacing_index{0};
    std::int64_t mass_ratio{1};

    [[nodiscard]] auto operator<=>(const TimeGroupKey&) const noexcept = default;
};

struct TimeGroup final {
    std::array<double, 3> position{};
    std::array<double, 3> velocity{};
    std::array<double, 3> time{};
    std::array<double, 3> candidate_augmented_energy{};
    std::array<double, 3> center_energy{};
    std::array<bool, 3> present{};
};

struct ConvergenceResult final {
    bool pass{false};
    bool all_below_threshold{false};
    bool ratio_rule_pass{false};
    bool finest_increase_failure{false};
    double medium_over_coarse{0.0};
    double fine_over_medium{0.0};
    double fine_over_coarse{0.0};
};

struct CandidateSummary final {
    std::uint64_t transfer_rows{0};
    std::uint64_t claimed_contract_failures{0};
    std::uint64_t exact_mass_failures{0};
    std::uint64_t center_orbital_diagnostic_failures{0};
    std::uint64_t h_groups{0};
    std::uint64_t h_particle_reconstruction_failures{0};
    std::uint64_t h_grid_reconstruction_failures{0};
    std::uint64_t h_affine_reconstruction_failures{0};
    std::uint64_t h_energy_failures{0};
    std::uint64_t h_center_energy_diagnostic_failures{0};
    std::uint64_t time_groups{0};
    std::uint64_t time_position_failures{0};
    std::uint64_t time_velocity_failures{0};
    std::uint64_t time_clock_failures{0};
    std::uint64_t time_energy_failures{0};
    std::uint64_t time_center_energy_diagnostic_failures{0};
    std::uint64_t time_contract_failures{0};
    std::uint64_t time_exact_mass_failures{0};
    double worst_affine_reconstruction{0.0};
    double worst_claimed_angular{0.0};
    double worst_energy_residual{0.0};
    double worst_64_cycle_drift{0.0};
};

struct EvidenceCounts final {
    std::uint64_t expected_transfer_rows{0};
    std::uint64_t actual_transfer_rows{0};
    std::uint64_t expected_h_groups{0};
    std::uint64_t actual_h_groups{0};
    std::uint64_t expected_h_convergence_rows{0};
    std::uint64_t actual_h_convergence_rows{0};
    std::uint64_t expected_time_raw_rows{0};
    std::uint64_t actual_time_raw_rows{0};
    std::uint64_t expected_time_groups{0};
    std::uint64_t actual_time_groups{0};
    std::uint64_t expected_time_convergence_rows{0};
    std::uint64_t actual_time_convergence_rows{0};
    std::uint64_t expected_flip_rows{0};
    std::uint64_t actual_flip_rows{0};
    bool complete{false};
};

class HashedCsv final {
public:
    explicit HashedCsv(const std::filesystem::path& path) : stream_(path, std::ios::binary) {
        stream_.exceptions(std::ios::badbit | std::ios::failbit);
        stream_.imbue(std::locale::classic());
    }

    void write(std::string_view text) {
        if (closed_) {
            throw std::logic_error("cannot write a closed CSV");
        }
        stream_.write(text.data(), static_cast<std::streamsize>(text.size()));
        for (const auto character : text) {
            hash_ ^= static_cast<std::uint8_t>(character);
            hash_ *= 1099511628211ULL;
        }
    }

    void write_row(std::string_view text) {
        write(text);
        ++row_count_;
    }

    void close() {
        if (!closed_) {
            stream_.flush();
            stream_.close();
            closed_ = true;
        }
    }

    [[nodiscard]] std::uint64_t row_count() const noexcept { return row_count_; }

    [[nodiscard]] std::string hash_hex() const {
        std::ostringstream result;
        result << std::hex << std::setfill('0') << std::setw(16) << hash_;
        return result.str();
    }

private:
    std::ofstream stream_;
    std::uint64_t hash_{14695981039346656037ULL};
    std::uint64_t row_count_{0};
    bool closed_{false};
};

[[nodiscard]] std::string format_double(double value) {
    if (!std::isfinite(value)) {
        throw std::runtime_error("non-finite bakeoff result");
    }
    std::ostringstream text;
    text.imbue(std::locale::classic());
    text << std::scientific << std::setprecision(std::numeric_limits<double>::max_digits10)
         << value;
    return text.str();
}

template <typename Value>
void csv_value(std::ostringstream& row, const Value& value) {
    row << value;
}

void csv_value(std::ostringstream& row, double value) {
    row << format_double(value);
}

template <typename Value, typename... Rest>
void csv_row_impl(std::ostringstream& row, const Value& value, const Rest&... rest) {
    csv_value(row, value);
    ((row << ',', csv_value(row, rest)), ...);
    row << '\n';
}

template <typename... Values>
void write_csv_row(HashedCsv& csv, const Values&... values) {
    std::ostringstream row;
    row.imbue(std::locale::classic());
    csv_row_impl(row, values...);
    csv.write_row(row.str());
}

[[nodiscard]] Vec3d subtract(Vec3d lhs, Vec3d rhs) noexcept {
    return lhs - rhs;
}

[[nodiscard]] Matrix3d matrix_subtract(const Matrix3d& lhs, const Matrix3d& rhs) noexcept {
    Matrix3d result{};
    for (std::size_t row = 0; row < 3; ++row) {
        for (std::size_t column = 0; column < 3; ++column) {
            result.value[row][column] = lhs.value[row][column] - rhs.value[row][column];
        }
    }
    return result;
}

[[nodiscard]] double relative_scalar(double lhs, double rhs) noexcept {
    return std::abs(lhs - rhs) / std::max({1.0, std::abs(lhs), std::abs(rhs)});
}

[[nodiscard]] double relative_vector(Vec3d lhs, Vec3d rhs) noexcept {
    return mls::experimental::norm(subtract(lhs, rhs)) /
        std::max({1.0, mls::experimental::norm(lhs), mls::experimental::norm(rhs)});
}

[[nodiscard]] double represented_energy(
    const TransferTotals& totals, TransferCandidate candidate) noexcept {
    return candidate == TransferCandidate::apic ? totals.augmented_kinetic_j
                                                 : totals.center_kinetic_j;
}

[[nodiscard]] Vec3d claimed_particle_angular(
    const TransferTotals& totals, TransferCandidate candidate) noexcept {
    return candidate == TransferCandidate::apic ? totals.augmented_angular_kg_m2_per_s
                                                 : totals.center_orbital_kg_m2_per_s;
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

[[nodiscard]] int permutation_parity(const std::array<int, 3>& permutation) noexcept {
    int inversions = 0;
    for (std::size_t lhs = 0; lhs < permutation.size(); ++lhs) {
        for (std::size_t rhs = lhs + 1; rhs < permutation.size(); ++rhs) {
            if (permutation[lhs] > permutation[rhs]) {
                ++inversions;
            }
        }
    }
    return inversions % 2 == 0 ? 1 : -1;
}

[[nodiscard]] std::vector<Orientation> proper_signed_axis_orientations() {
    std::vector<Orientation> result;
    std::array<int, 3> permutation{0, 1, 2};
    do {
        const auto parity = permutation_parity(permutation);
        for (const auto sx : {-1, 1}) {
            for (const auto sy : {-1, 1}) {
                for (const auto sz : {-1, 1}) {
                    if (parity * sx * sy * sz != 1) {
                        continue;
                    }
                    const std::array<int, 3> signs{sx, sy, sz};
                    Matrix3d matrix{};
                    for (std::size_t row = 0; row < 3; ++row) {
                        matrix.value[row][static_cast<std::size_t>(permutation[row])] =
                            static_cast<double>(signs[row]);
                    }
                    std::ostringstream label;
                    label << 'p' << permutation[0] << permutation[1] << permutation[2]
                          << "_s" << (sx > 0 ? 'p' : 'm') << (sy > 0 ? 'p' : 'm')
                          << (sz > 0 ? 'p' : 'm');
                    result.push_back({matrix, label.str()});
                }
            }
        }
    } while (std::next_permutation(permutation.begin(), permutation.end()));
    if (result.size() != 24U) {
        throw std::logic_error("proper signed-axis orientation generator did not produce 24");
    }
    return result;
}

[[nodiscard]] Matrix3d rotation_gradient(Vec3d omega_per_s) noexcept {
    Matrix3d result{};
    result.value = {{{0.0, -omega_per_s.z, omega_per_s.y},
                     {omega_per_s.z, 0.0, -omega_per_s.x},
                     {-omega_per_s.y, omega_per_s.x, 0.0}}};
    return result;
}

[[nodiscard]] FieldSpec base_field(FieldKind kind) {
    FieldSpec field{};
    field.kind = kind;
    field.center_m = {0.31, -0.27, 0.19};
    switch (kind) {
    case FieldKind::translation:
        field.translation_m_per_s = {0.70, -0.45, 0.20};
        break;
    case FieldKind::rigid_rotation:
        field.gradient_per_s = rotation_gradient({0.45, -0.35, 0.55});
        break;
    case FieldKind::general_affine:
        field.gradient_per_s.value = {{{0.20, -0.70, 0.30},
                                       {0.55, -0.10, 0.25},
                                       {-0.35, 0.40, 0.15}}};
        field.translation_m_per_s = {0.90, -0.40, 0.70};
        break;
    }
    return field;
}

[[nodiscard]] FieldSpec orient_field(FieldKind kind, const Orientation& orientation) {
    const auto source = base_field(kind);
    return {
        kind,
        mls::experimental::multiply(
            mls::experimental::multiply(orientation.matrix, source.gradient_per_s),
            mls::experimental::transpose(orientation.matrix)),
        mls::experimental::multiply(orientation.matrix, source.center_m),
        mls::experimental::multiply(orientation.matrix, source.translation_m_per_s),
    };
}

[[nodiscard]] Vec3d field_velocity(const FieldSpec& field, Vec3d position_m) noexcept {
    return mls::experimental::multiply(
               field.gradient_per_s, position_m - field.center_m) +
        field.translation_m_per_s;
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
        const auto unit = static_cast<double>(next() >> 11U) * scale;
        return 2.0 * unit - 1.0;
    }

private:
    std::uint64_t state_;
};

struct BaseLayout final {
    std::vector<Vec3d> offsets{};
    std::vector<std::int64_t> mass_spectrum{};
};

[[nodiscard]] BaseLayout base_layout(LayoutKind layout) {
    BaseLayout result{};
    switch (layout) {
    case LayoutKind::regular_2x2x2:
        for (const auto x : {-0.36, 0.36}) {
            for (const auto y : {-0.36, 0.36}) {
                for (const auto z : {-0.36, 0.36}) {
                    result.offsets.push_back({x, y, z});
                    result.mass_spectrum.push_back(1);
                }
            }
        }
        break;
    case LayoutKind::unequal_mass_asymmetric:
        result.offsets = {
            {-0.51, -0.22, 0.17}, {0.44, -0.31, -0.28}, {-0.13, 0.56, -0.19},
            {0.28, 0.16, 0.49},   {-0.47, 0.33, 0.41},  {0.09, -0.54, 0.36},
            {0.53, 0.45, 0.08},   {-0.24, -0.11, -0.52}, {0.17, 0.04, -0.07},
        };
        result.mass_spectrum = {1, 2, 3, 5, 8, 13, 17, 11, 7};
        break;
    case LayoutKind::seeded_jittered_27: {
        SplitMix64 generator(seed);
        for (const auto x : {-0.42, 0.0, 0.42}) {
            for (const auto y : {-0.42, 0.0, 0.42}) {
                for (const auto z : {-0.42, 0.0, 0.42}) {
                    result.offsets.push_back({
                        x + 0.055 * generator.symmetric_unit(),
                        y + 0.055 * generator.symmetric_unit(),
                        z + 0.055 * generator.symmetric_unit(),
                    });
                    result.mass_spectrum.push_back(1);
                }
            }
        }
        break;
    }
    }
    return result;
}

[[nodiscard]] std::vector<TransferParticle> make_particles(
    LayoutKind layout,
    std::int64_t mass_ratio,
    const Orientation& orientation,
    const FieldSpec& field,
    TransferCandidate candidate) {
    const auto base = base_layout(layout);
    std::vector<TransferParticle> particles;
    particles.reserve(base.offsets.size());
    for (std::size_t index = 0; index < base.offsets.size(); ++index) {
        const auto oriented_offset =
            mls::experimental::multiply(orientation.matrix, base.offsets[index]);
        const auto position = field.center_m + oriented_offset;
        const auto ratio_factor = index % 2U == 0U ? std::int64_t{1} : mass_ratio;
        const auto mass = base.mass_spectrum[index] * ratio_factor;
        particles.push_back({
            static_cast<std::uint64_t>(index + 1U),
            mass,
            position,
            field_velocity(field, position),
            candidate == TransferCandidate::apic ? field.gradient_per_s : Matrix3d::zero(),
        });
    }
    return particles;
}

[[nodiscard]] double particle_velocity_reconstruction(
    const std::vector<TransferParticle>& particles, const FieldSpec& field) {
    long double weighted_error = 0.0L;
    long double weighted_reference = 0.0L;
    long double total_mass = 0.0L;
    for (const auto& particle : particles) {
        const auto reference = field_velocity(field, particle.position_m);
        const auto difference = particle.velocity_m_per_s - reference;
        const auto mass = static_cast<long double>(particle.mass_quanta);
        weighted_error += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        weighted_reference += mass * static_cast<long double>(mls::experimental::dot(reference, reference));
        total_mass += mass;
    }
    const auto error_rms = std::sqrt(static_cast<double>(weighted_error / total_mass));
    const auto reference_rms = std::sqrt(static_cast<double>(weighted_reference / total_mass));
    return error_rms / std::max(1.0, reference_rms);
}

[[nodiscard]] double particle_velocity_difference(
    const std::vector<TransferParticle>& particles,
    const std::vector<TransferParticle>& reference) {
    if (particles.size() != reference.size()) {
        throw std::logic_error("particle velocity comparison size mismatch");
    }
    long double weighted_error = 0.0L;
    long double weighted_reference = 0.0L;
    long double total_mass = 0.0L;
    for (std::size_t index = 0; index < particles.size(); ++index) {
        const auto difference =
            particles[index].velocity_m_per_s - reference[index].velocity_m_per_s;
        const auto mass = static_cast<long double>(reference[index].mass_quanta);
        weighted_error += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        weighted_reference += mass * static_cast<long double>(mls::experimental::dot(
            reference[index].velocity_m_per_s, reference[index].velocity_m_per_s));
        total_mass += mass;
    }
    const auto error_rms = std::sqrt(static_cast<double>(weighted_error / total_mass));
    const auto reference_rms = std::sqrt(static_cast<double>(weighted_reference / total_mass));
    return error_rms / std::max(1.0, reference_rms);
}

[[nodiscard]] double particle_position_difference(
    const std::vector<TransferParticle>& particles,
    const std::vector<TransferParticle>& initial,
    double horizon_seconds) {
    if (particles.size() != initial.size()) {
        throw std::logic_error("particle position comparison size mismatch");
    }
    long double weighted_error = 0.0L;
    long double weighted_reference = 0.0L;
    long double total_mass = 0.0L;
    for (std::size_t index = 0; index < particles.size(); ++index) {
        const auto expected = initial[index].position_m +
            horizon_seconds * initial[index].velocity_m_per_s;
        const auto difference = particles[index].position_m - expected;
        const auto mass = static_cast<long double>(initial[index].mass_quanta);
        weighted_error += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        weighted_reference += mass * static_cast<long double>(mls::experimental::dot(expected, expected));
        total_mass += mass;
    }
    const auto error_rms = std::sqrt(static_cast<double>(weighted_error / total_mass));
    const auto reference_rms = std::sqrt(static_cast<double>(weighted_reference / total_mass));
    return error_rms / std::max(1.0, reference_rms);
}

[[nodiscard]] double affine_reconstruction(
    const std::vector<TransferParticle>& particles, const Matrix3d& reference) {
    long double weighted_error = 0.0L;
    long double weighted_reference = 0.0L;
    long double total_mass = 0.0L;
    const auto reference_norm = mls::experimental::frobenius_norm(reference);
    for (const auto& particle : particles) {
        const auto difference = matrix_subtract(particle.affine_velocity_per_s, reference);
        const auto error_norm = mls::experimental::frobenius_norm(difference);
        const auto mass = static_cast<long double>(particle.mass_quanta);
        weighted_error += mass * static_cast<long double>(error_norm * error_norm);
        weighted_reference += mass * static_cast<long double>(reference_norm * reference_norm);
        total_mass += mass;
    }
    const auto error_rms = std::sqrt(static_cast<double>(weighted_error / total_mass));
    const auto reference_rms = std::sqrt(static_cast<double>(weighted_reference / total_mass));
    return error_rms / std::max(1.0, reference_rms);
}

[[nodiscard]] double grid_velocity_reconstruction(
    const TransferGrid& grid, const FieldSpec& field) {
    long double weighted_error = 0.0L;
    long double weighted_reference = 0.0L;
    long double total_mass = 0.0L;
    for (const auto& [index, node] : grid.nodes) {
        const Vec3d position{
            grid.config.grid_origin_m.x +
                static_cast<double>(index.x) * grid.config.grid_spacing_m,
            grid.config.grid_origin_m.y +
                static_cast<double>(index.y) * grid.config.grid_spacing_m,
            grid.config.grid_origin_m.z +
                static_cast<double>(index.z) * grid.config.grid_spacing_m,
        };
        const auto reference = field_velocity(field, position);
        const auto difference = node.velocity_m_per_s - reference;
        const auto mass = static_cast<long double>(node.mass_kg);
        weighted_error += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        weighted_reference += mass * static_cast<long double>(mls::experimental::dot(reference, reference));
        total_mass += mass;
    }
    const auto error_rms = std::sqrt(static_cast<double>(weighted_error / total_mass));
    const auto reference_rms = std::sqrt(static_cast<double>(weighted_reference / total_mass));
    return error_rms / std::max(1.0, reference_rms);
}

void update_observation_pass(
    Observation& observation,
    const TransferCycle& cycle,
    TransferCandidate candidate) {
    observation.grid = cycle.grid_after_p2g;
    observation.terminal = cycle.particle_after;
    observation.exact_mass_terminal = cycle.exact_mass_quanta_after;
    observation.exact_mass_ok = observation.exact_mass_ok &&
        cycle.exact_mass_quanta_before == cycle.exact_mass_quanta_after &&
        cycle.exact_mass_quanta_before == observation.exact_mass_initial;
    observation.max_p2g_mass_relative = std::max(
        observation.max_p2g_mass_relative,
        relative_scalar(cycle.particle_before.mass_kg, cycle.grid_after_p2g.mass_kg));
    observation.max_p2g_linear_relative = std::max(
        observation.max_p2g_linear_relative,
        relative_vector(cycle.particle_before.linear_momentum_kg_m_per_s,
                        cycle.grid_after_p2g.linear_momentum_kg_m_per_s));
    observation.max_p2g_center_orbital_relative = std::max(
        observation.max_p2g_center_orbital_relative,
        relative_vector(cycle.particle_before.center_orbital_kg_m2_per_s,
                        cycle.grid_after_p2g.center_orbital_kg_m2_per_s));
    observation.max_p2g_angular_relative = std::max(
        observation.max_p2g_angular_relative,
        relative_vector(claimed_particle_angular(cycle.particle_before, candidate),
                        cycle.grid_after_p2g.center_orbital_kg_m2_per_s));
    observation.max_roundtrip_mass_relative = std::max(
        observation.max_roundtrip_mass_relative,
        relative_scalar(cycle.particle_before.mass_kg, cycle.particle_after.mass_kg));
    observation.max_roundtrip_linear_relative = std::max(
        observation.max_roundtrip_linear_relative,
        relative_vector(cycle.particle_before.linear_momentum_kg_m_per_s,
                        cycle.particle_after.linear_momentum_kg_m_per_s));
    observation.max_roundtrip_center_orbital_relative = std::max(
        observation.max_roundtrip_center_orbital_relative,
        relative_vector(cycle.particle_before.center_orbital_kg_m2_per_s,
                        cycle.particle_after.center_orbital_kg_m2_per_s));
    observation.max_roundtrip_claimed_angular_relative = std::max(
        observation.max_roundtrip_claimed_angular_relative,
        relative_vector(claimed_particle_angular(cycle.particle_before, candidate),
                        claimed_particle_angular(cycle.particle_after, candidate)));
    const auto before_energy = represented_energy(cycle.particle_before, candidate);
    const auto grid_energy = cycle.grid_after_p2g.center_kinetic_j;
    const auto after_energy = represented_energy(cycle.particle_after, candidate);
    observation.final_p2g_energy_residual_j = cycle.p2g_numerical_energy_residual_j;
    observation.final_p2g_energy_relative = relative_scalar(grid_energy, before_energy);
    observation.final_roundtrip_energy_residual_j =
        cycle.roundtrip_numerical_energy_residual_j;
    observation.final_roundtrip_energy_relative = relative_scalar(after_energy, before_energy);
    observation.max_abs_p2g_energy_relative = std::max(
        observation.max_abs_p2g_energy_relative,
        observation.final_p2g_energy_relative);
    observation.max_abs_roundtrip_energy_relative = std::max(
        observation.max_abs_roundtrip_energy_relative,
        observation.final_roundtrip_energy_relative);
    observation.final_p2g_center_energy_residual_j =
        cycle.grid_after_p2g.center_kinetic_j - cycle.particle_before.center_kinetic_j;
    observation.final_p2g_center_energy_relative = relative_scalar(
        cycle.grid_after_p2g.center_kinetic_j,
        cycle.particle_before.center_kinetic_j);
    observation.final_roundtrip_center_energy_residual_j =
        cycle.particle_after.center_kinetic_j - cycle.particle_before.center_kinetic_j;
    observation.final_roundtrip_center_energy_relative = relative_scalar(
        cycle.particle_after.center_kinetic_j,
        cycle.particle_before.center_kinetic_j);
    observation.max_abs_p2g_center_energy_relative = std::max(
        observation.max_abs_p2g_center_energy_relative,
        observation.final_p2g_center_energy_relative);
    observation.max_abs_roundtrip_center_energy_relative = std::max(
        observation.max_abs_roundtrip_center_energy_relative,
        observation.final_roundtrip_center_energy_relative);
}

[[nodiscard]] bool reconstruction_claimed(
    TransferCandidate candidate, FieldKind field) noexcept {
    return field == FieldKind::translation || candidate == TransferCandidate::apic;
}

[[nodiscard]] double reconstruction_tolerance(
    TransferCandidate candidate, FieldKind field, std::int64_t cycles) noexcept {
    if (cycles == 64 && reconstruction_claimed(candidate, field)) {
        return repeated_claim_tolerance;
    }
    if (field == FieldKind::translation) {
        return translation_reconstruction_tolerance;
    }
    return apic_affine_reconstruction_tolerance;
}

[[nodiscard]] bool observation_contract_pass(
    const Observation& observation,
    TransferCandidate candidate,
    FieldKind field,
    std::int64_t cycles) noexcept {
    if (!observation.exact_mass_ok || observation.max_p2g_mass_relative > mass_tolerance ||
        observation.max_roundtrip_mass_relative > mass_tolerance ||
        observation.max_p2g_linear_relative > linear_momentum_tolerance ||
        observation.max_roundtrip_linear_relative > linear_momentum_tolerance ||
        observation.max_p2g_angular_relative > angular_momentum_tolerance) {
        return false;
    }
    const auto cumulative_linear_tolerance =
        cycles == 64 ? repeated_claim_tolerance : linear_momentum_tolerance;
    const auto cumulative_angular_tolerance =
        cycles == 64 ? repeated_claim_tolerance : angular_momentum_tolerance;
    if (observation.max_roundtrip_claimed_angular_relative > angular_momentum_tolerance ||
        observation.cumulative_linear_relative > cumulative_linear_tolerance ||
        observation.cumulative_declared_angular_relative > cumulative_angular_tolerance) {
        return false;
    }
    if (reconstruction_claimed(candidate, field) &&
        observation.particle_reconstruction_relative >
            reconstruction_tolerance(candidate, field, cycles)) {
        return false;
    }
    if (candidate == TransferCandidate::apic &&
        observation.affine_reconstruction_relative >
            reconstruction_tolerance(candidate, field, cycles)) {
        return false;
    }
    return true;
}

[[nodiscard]] Observation observe_transfer_cycles(
    std::vector<TransferParticle> particles,
    const TransferConfig& config,
    TransferCandidate candidate,
    const FieldSpec& field,
    std::int64_t cycles) {
    Observation observation{};
    observation.initial = mls::experimental::particle_totals(particles, config);
    observation.exact_mass_initial = mls::experimental::exact_particle_mass_quanta(particles);
    const auto initial_energy = represented_energy(observation.initial, candidate);
    TransferGrid last_grid{};
    for (std::int64_t cycle_index = 0; cycle_index < cycles; ++cycle_index) {
        auto cycle = mls::experimental::transfer_cycle(particles, config, candidate);
        update_observation_pass(observation, cycle, candidate);
        last_grid = std::move(cycle.grid);
        particles = std::move(cycle.particles);
    }
    observation.terminal = mls::experimental::particle_totals(particles, config);
    observation.exact_mass_terminal = mls::experimental::exact_particle_mass_quanta(particles);
    observation.grid_reconstruction_relative = grid_velocity_reconstruction(last_grid, field);
    observation.particle_reconstruction_relative =
        particle_velocity_reconstruction(particles, field);
    observation.affine_reconstruction_applicable = candidate == TransferCandidate::apic;
    if (observation.affine_reconstruction_applicable) {
        observation.affine_reconstruction_relative =
            affine_reconstruction(particles, field.gradient_per_s);
    }
    const auto terminal_energy = represented_energy(observation.terminal, candidate);
    observation.cumulative_energy_residual_j = terminal_energy - initial_energy;
    observation.cumulative_energy_relative = relative_scalar(terminal_energy, initial_energy);
    observation.cumulative_center_energy_residual_j =
        observation.terminal.center_kinetic_j - observation.initial.center_kinetic_j;
    observation.cumulative_center_energy_relative = relative_scalar(
        observation.terminal.center_kinetic_j, observation.initial.center_kinetic_j);
    observation.cumulative_linear_relative = relative_vector(
        observation.initial.linear_momentum_kg_m_per_s,
        observation.terminal.linear_momentum_kg_m_per_s);
    observation.cumulative_center_orbital_relative = relative_vector(
        observation.initial.center_orbital_kg_m2_per_s,
        observation.terminal.center_orbital_kg_m2_per_s);
    observation.cumulative_declared_angular_relative = relative_vector(
        claimed_particle_angular(observation.initial, candidate),
        claimed_particle_angular(observation.terminal, candidate));
    const auto cumulative_orbital_tolerance =
        cycles == 64 ? repeated_claim_tolerance : angular_momentum_tolerance;
    observation.center_orbital_diagnostic_pass =
        observation.max_p2g_center_orbital_relative <= angular_momentum_tolerance &&
        observation.max_roundtrip_center_orbital_relative <= angular_momentum_tolerance &&
        observation.cumulative_center_orbital_relative <= cumulative_orbital_tolerance;
    observation.claimed_contract_pass =
        observation_contract_pass(observation, candidate, field.kind, cycles);
    return observation;
}

[[nodiscard]] ConvergenceResult convergence(
    const std::array<double, 3>& errors, std::optional<double> hard_tolerance) noexcept {
    ConvergenceResult result{};
    if (!std::ranges::all_of(errors, [](double value) { return std::isfinite(value); })) {
        return result;
    }
    result.all_below_threshold = hard_tolerance.has_value()
        ? std::ranges::all_of(errors, [&](double value) { return value <= *hard_tolerance; })
        : std::ranges::all_of(errors, [](double value) { return value <= roundoff_floor; });
    result.finest_increase_failure = !result.all_below_threshold &&
        errors[2] > roundoff_floor && errors[2] > errors[0] && errors[2] > errors[1];
    const std::array clamped{
        std::max(errors[0], roundoff_floor),
        std::max(errors[1], roundoff_floor),
        std::max(errors[2], roundoff_floor),
    };
    result.medium_over_coarse = clamped[1] / clamped[0];
    result.fine_over_medium = clamped[2] / clamped[1];
    result.fine_over_coarse = clamped[2] / clamped[0];
    result.ratio_rule_pass = result.medium_over_coarse <= 0.70 &&
        result.fine_over_medium <= 0.70 && result.fine_over_coarse <= 0.25 &&
        !result.finest_increase_failure;
    result.pass = result.all_below_threshold || result.ratio_rule_pass;
    return result;
}

[[nodiscard]] double timestep_seconds(std::int64_t time_quanta) noexcept {
    return static_cast<double>(time_quanta * time_quantum_seconds_numerator) /
        static_cast<double>(time_quantum_seconds_denominator);
}

void write_totals(std::ostringstream& row, const TransferTotals& totals) {
    row << ',' << format_double(totals.mass_kg)
        << ',' << format_double(totals.linear_momentum_kg_m_per_s.x)
        << ',' << format_double(totals.linear_momentum_kg_m_per_s.y)
        << ',' << format_double(totals.linear_momentum_kg_m_per_s.z)
        << ',' << format_double(totals.center_orbital_kg_m2_per_s.x)
        << ',' << format_double(totals.center_orbital_kg_m2_per_s.y)
        << ',' << format_double(totals.center_orbital_kg_m2_per_s.z)
        << ',' << format_double(totals.affine_auxiliary_kg_m2_per_s.x)
        << ',' << format_double(totals.affine_auxiliary_kg_m2_per_s.y)
        << ',' << format_double(totals.affine_auxiliary_kg_m2_per_s.z)
        << ',' << format_double(totals.augmented_angular_kg_m2_per_s.x)
        << ',' << format_double(totals.augmented_angular_kg_m2_per_s.y)
        << ',' << format_double(totals.augmented_angular_kg_m2_per_s.z)
        << ',' << format_double(totals.center_kinetic_j)
        << ',' << format_double(totals.affine_auxiliary_kinetic_j)
        << ',' << format_double(totals.augmented_kinetic_j);
}

void write_transfer_header(HashedCsv& csv) {
    csv.write(
        "mode,seed,candidate,field,phase_index,phase_x,phase_y,phase_z,"
        "orientation_index,orientation,layout,grid_spacing_m,mass_ratio,"
        "kg_per_mass_quantum,dt_quanta,dt_seconds,pure_remap_timestep_independent,cycles,particle_count,"
        "exact_mass_initial_quanta,exact_mass_terminal_quanta,exact_mass_ok,"
        "max_p2g_mass_relative,max_p2g_linear_relative,max_p2g_center_orbital_relative,"
        "max_p2g_declared_angular_relative,"
        "max_roundtrip_mass_relative,max_roundtrip_linear_relative,"
        "max_roundtrip_center_orbital_relative,"
        "max_roundtrip_declared_angular_relative,cumulative_linear_relative,"
        "cumulative_center_orbital_relative,cumulative_declared_angular_relative,"
        "center_orbital_diagnostic_pass,"
        "grid_reconstruction_relative,"
        "particle_reconstruction_relative,affine_reconstruction_applicable,"
        "affine_reconstruction_relative,final_p2g_candidate_represented_energy_residual_j,"
        "final_p2g_candidate_represented_energy_relative,"
        "final_roundtrip_candidate_represented_energy_residual_j,"
        "final_roundtrip_candidate_represented_energy_relative,"
        "max_abs_p2g_candidate_represented_energy_relative,"
        "max_abs_roundtrip_candidate_represented_energy_relative,"
        "cumulative_candidate_represented_energy_residual_j,"
        "cumulative_candidate_represented_energy_relative,"
        "final_p2g_center_energy_residual_j,final_p2g_center_energy_relative,"
        "final_roundtrip_center_energy_residual_j,final_roundtrip_center_energy_relative,"
        "max_abs_p2g_center_energy_relative,max_abs_roundtrip_center_energy_relative,"
        "cumulative_center_energy_residual_j,cumulative_center_energy_relative,"
        "claimed_contract_pass,"
        "initial_mass_kg,initial_linear_x,initial_linear_y,initial_linear_z,"
        "initial_center_orbital_x,initial_center_orbital_y,initial_center_orbital_z,"
        "initial_affine_auxiliary_angular_x,initial_affine_auxiliary_angular_y,"
        "initial_affine_auxiliary_angular_z,initial_augmented_angular_x,"
        "initial_augmented_angular_y,initial_augmented_angular_z,initial_center_kinetic_j,"
        "initial_affine_auxiliary_kinetic_j,initial_augmented_kinetic_j,"
        "grid_mass_kg,grid_linear_x,grid_linear_y,grid_linear_z,grid_center_orbital_x,"
        "grid_center_orbital_y,grid_center_orbital_z,grid_affine_auxiliary_angular_x,"
        "grid_affine_auxiliary_angular_y,grid_affine_auxiliary_angular_z,"
        "grid_augmented_angular_x,grid_augmented_angular_y,grid_augmented_angular_z,"
        "grid_center_kinetic_j,grid_affine_auxiliary_kinetic_j,grid_augmented_kinetic_j,"
        "terminal_mass_kg,terminal_linear_x,terminal_linear_y,terminal_linear_z,"
        "terminal_center_orbital_x,terminal_center_orbital_y,terminal_center_orbital_z,"
        "terminal_affine_auxiliary_angular_x,terminal_affine_auxiliary_angular_y,"
        "terminal_affine_auxiliary_angular_z,terminal_augmented_angular_x,"
        "terminal_augmented_angular_y,terminal_augmented_angular_z,terminal_center_kinetic_j,"
        "terminal_affine_auxiliary_kinetic_j,terminal_augmented_kinetic_j\n");
}

void write_transfer_observation(
    HashedCsv& csv,
    bool smoke,
    TransferCandidate candidate,
    FieldKind field,
    std::size_t phase_index,
    Vec3d phase,
    std::size_t orientation_index,
    const Orientation& orientation,
    LayoutKind layout,
    double spacing,
    std::int64_t mass_ratio,
    std::int64_t dt_quanta,
    std::int64_t cycles,
    std::size_t particle_count,
    const Observation& observation) {
    std::ostringstream row;
    row.imbue(std::locale::classic());
    row << (smoke ? "smoke" : "full") << ',' << seed << ','
        << mls::experimental::candidate_name(candidate) << ',' << field_name(field) << ','
        << phase_index << ',' << format_double(phase.x) << ',' << format_double(phase.y)
        << ',' << format_double(phase.z) << ',' << orientation_index << ','
        << orientation.label << ',' << layout_name(layout) << ',' << format_double(spacing)
        << ',' << mass_ratio << ',' << format_double(kg_per_mass_quantum) << ','
        << dt_quanta << ','
        << format_double(timestep_seconds(dt_quanta)) << ",true," << cycles << ','
        << particle_count << ',' << observation.exact_mass_initial << ','
        << observation.exact_mass_terminal << ',' << observation.exact_mass_ok << ','
        << format_double(observation.max_p2g_mass_relative) << ','
        << format_double(observation.max_p2g_linear_relative) << ','
        << format_double(observation.max_p2g_center_orbital_relative) << ','
        << format_double(observation.max_p2g_angular_relative) << ','
        << format_double(observation.max_roundtrip_mass_relative) << ','
        << format_double(observation.max_roundtrip_linear_relative) << ','
        << format_double(observation.max_roundtrip_center_orbital_relative) << ','
        << format_double(observation.max_roundtrip_claimed_angular_relative) << ','
        << format_double(observation.cumulative_linear_relative) << ','
        << format_double(observation.cumulative_center_orbital_relative) << ','
        << format_double(observation.cumulative_declared_angular_relative) << ','
        << observation.center_orbital_diagnostic_pass << ','
        << format_double(observation.grid_reconstruction_relative) << ','
        << format_double(observation.particle_reconstruction_relative) << ','
        << observation.affine_reconstruction_applicable << ','
        << format_double(observation.affine_reconstruction_relative) << ','
        << format_double(observation.final_p2g_energy_residual_j) << ','
        << format_double(observation.final_p2g_energy_relative) << ','
        << format_double(observation.final_roundtrip_energy_residual_j) << ','
        << format_double(observation.final_roundtrip_energy_relative) << ','
        << format_double(observation.max_abs_p2g_energy_relative) << ','
        << format_double(observation.max_abs_roundtrip_energy_relative) << ','
        << format_double(observation.cumulative_energy_residual_j) << ','
        << format_double(observation.cumulative_energy_relative) << ','
        << format_double(observation.final_p2g_center_energy_residual_j) << ','
        << format_double(observation.final_p2g_center_energy_relative) << ','
        << format_double(observation.final_roundtrip_center_energy_residual_j) << ','
        << format_double(observation.final_roundtrip_center_energy_relative) << ','
        << format_double(observation.max_abs_p2g_center_energy_relative) << ','
        << format_double(observation.max_abs_roundtrip_center_energy_relative) << ','
        << format_double(observation.cumulative_center_energy_residual_j) << ','
        << format_double(observation.cumulative_center_energy_relative) << ','
        << observation.claimed_contract_pass;
    write_totals(row, observation.initial);
    write_totals(row, observation.grid);
    write_totals(row, observation.terminal);
    row << '\n';
    csv.write_row(row.str());
}

[[nodiscard]] std::vector<FieldKind> fields() {
    return {FieldKind::translation, FieldKind::rigid_rotation, FieldKind::general_affine};
}

[[nodiscard]] std::vector<Vec3d> phases(bool smoke) {
    std::vector<Vec3d> values{
        {0.00, 0.00, 0.00},
        {0.13, 0.37, 0.71},
        {0.49, 0.01, 0.83},
        {0.91, 0.59, 0.23},
    };
    if (smoke) {
        values.resize(1);
    }
    return values;
}

[[nodiscard]] std::vector<Orientation> orientations(bool smoke) {
    auto values = proper_signed_axis_orientations();
    if (smoke) {
        values.resize(2);
    }
    return values;
}

[[nodiscard]] std::vector<LayoutKind> layouts() {
    return {LayoutKind::regular_2x2x2,
            LayoutKind::unequal_mass_asymmetric,
            LayoutKind::seeded_jittered_27};
}

[[nodiscard]] std::array<double, 3> spacings() noexcept {
    return {1.0, 0.5, 0.25};
}

[[nodiscard]] std::vector<std::int64_t> cycle_counts(bool smoke) {
    return smoke ? std::vector<std::int64_t>{1, 4}
                 : std::vector<std::int64_t>{1, 4, 16, 64};
}

[[nodiscard]] std::array<std::int64_t, 3> timestep_quanta() noexcept {
    return {4, 2, 1};
}

[[nodiscard]] std::uint64_t checked_product(
    std::initializer_list<std::uint64_t> factors) {
    std::uint64_t result = 1;
    for (const auto factor : factors) {
        if (factor != 0U && result > std::numeric_limits<std::uint64_t>::max() / factor) {
            throw std::overflow_error("bakeoff expected row-count product overflow");
        }
        result *= factor;
    }
    return result;
}

[[nodiscard]] EvidenceCounts expected_counts(
    std::size_t phase_count,
    std::size_t orientation_count,
    std::size_t cycle_count) {
    constexpr std::uint64_t candidate_count = 2;
    constexpr std::uint64_t mass_ratio_count = 2;
    const auto common = checked_product({
        static_cast<std::uint64_t>(fields().size()),
        static_cast<std::uint64_t>(phase_count),
        static_cast<std::uint64_t>(orientation_count),
        static_cast<std::uint64_t>(layouts().size()),
        mass_ratio_count,
    });
    const auto per_candidate_h_groups = checked_product({
        common,
        static_cast<std::uint64_t>(cycle_count),
        static_cast<std::uint64_t>(timestep_quanta().size()),
    });
    const auto per_candidate_time_groups = checked_product({
        common,
        static_cast<std::uint64_t>(spacings().size()),
    });
    EvidenceCounts result{};
    result.expected_transfer_rows = checked_product({
        candidate_count,
        per_candidate_h_groups,
        static_cast<std::uint64_t>(spacings().size()),
    });
    result.expected_h_groups = candidate_count * per_candidate_h_groups;
    result.expected_h_convergence_rows =
        4U * per_candidate_h_groups + 5U * per_candidate_h_groups;
    result.expected_time_groups = candidate_count * per_candidate_time_groups;
    result.expected_time_raw_rows = checked_product({
        result.expected_time_groups,
        static_cast<std::uint64_t>(timestep_quanta().size()),
    });
    result.expected_time_convergence_rows = 5U * result.expected_time_groups;
    result.expected_flip_rows = checked_product({
        common,
        static_cast<std::uint64_t>(spacings().size()),
    });
    return result;
}

void update_candidate_summary(
    CandidateSummary& summary,
    const Observation& observation,
    TransferCandidate candidate,
    FieldKind field,
    std::int64_t cycles) {
    ++summary.transfer_rows;
    if (!observation.claimed_contract_pass) {
        ++summary.claimed_contract_failures;
    }
    if (!observation.exact_mass_ok) {
        ++summary.exact_mass_failures;
    }
    if (!observation.center_orbital_diagnostic_pass) {
        ++summary.center_orbital_diagnostic_failures;
    }
    summary.worst_claimed_angular = std::max(
        {summary.worst_claimed_angular,
         observation.max_p2g_angular_relative,
         observation.max_roundtrip_claimed_angular_relative,
         observation.cumulative_declared_angular_relative});
    summary.worst_energy_residual = std::max(
        {summary.worst_energy_residual,
         observation.max_abs_p2g_energy_relative,
         observation.max_abs_roundtrip_energy_relative,
         observation.cumulative_energy_relative});
    if (field == FieldKind::general_affine) {
        summary.worst_affine_reconstruction = std::max(
            {summary.worst_affine_reconstruction,
             observation.particle_reconstruction_relative,
             observation.affine_reconstruction_applicable
                 ? observation.affine_reconstruction_relative
                 : 0.0});
    }
    if (cycles == 64) {
        summary.worst_64_cycle_drift = std::max(
            {summary.worst_64_cycle_drift,
             reconstruction_claimed(candidate, field)
                 ? observation.particle_reconstruction_relative
                 : 0.0,
             observation.affine_reconstruction_applicable
                 ? observation.affine_reconstruction_relative
                 : 0.0,
             observation.cumulative_linear_relative,
             observation.cumulative_declared_angular_relative});
    }
}

void run_transfer_sweep(
    bool smoke,
    HashedCsv& raw_csv,
    std::map<HGroupKey, HGroup>& h_groups,
    std::map<TransferCandidate, CandidateSummary>& summaries) {
    write_transfer_header(raw_csv);
    const auto sweep_phases = phases(smoke);
    const auto sweep_orientations = orientations(smoke);
    const auto sweep_cycles = cycle_counts(smoke);
    for (const auto candidate : {TransferCandidate::pic, TransferCandidate::apic}) {
        for (const auto field_kind : fields()) {
            for (std::size_t phase_index = 0; phase_index < sweep_phases.size(); ++phase_index) {
                const auto phase = sweep_phases[phase_index];
                for (std::size_t orientation_index = 0;
                     orientation_index < sweep_orientations.size(); ++orientation_index) {
                    const auto& orientation = sweep_orientations[orientation_index];
                    const auto field = orient_field(field_kind, orientation);
                    for (const auto layout : layouts()) {
                        for (const auto mass_ratio : {std::int64_t{1}, std::int64_t{17}}) {
                            for (std::size_t spacing_index = 0;
                                 spacing_index < spacings().size(); ++spacing_index) {
                                const auto spacing = spacings()[spacing_index];
                                const TransferConfig config{
                                    spacing,
                                    {phase.x * spacing, phase.y * spacing, phase.z * spacing},
                                    kg_per_mass_quantum,
                                };
                                const auto particles = make_particles(
                                    layout, mass_ratio, orientation, field, candidate);
                                for (const auto cycles : sweep_cycles) {
                                    const auto observation = observe_transfer_cycles(
                                        particles, config, candidate, field, cycles);
                                    for (const auto dt_quanta : timestep_quanta()) {
                                        write_transfer_observation(
                                            raw_csv,
                                            smoke,
                                            candidate,
                                            field_kind,
                                            phase_index,
                                            phase,
                                            orientation_index,
                                            orientation,
                                            layout,
                                            spacing,
                                            mass_ratio,
                                            dt_quanta,
                                            cycles,
                                            particles.size(),
                                            observation);
                                        const HGroupKey key{
                                            candidate,
                                            field_kind,
                                            static_cast<std::uint8_t>(phase_index),
                                            static_cast<std::uint8_t>(orientation_index),
                                            layout,
                                            mass_ratio,
                                            cycles,
                                            dt_quanta,
                                        };
                                        auto& group = h_groups[key];
                                        group.particle_reconstruction[spacing_index] =
                                            observation.particle_reconstruction_relative;
                                        group.grid_reconstruction[spacing_index] =
                                            observation.grid_reconstruction_relative;
                                        group.candidate_augmented_energy[spacing_index] =
                                            observation.cumulative_energy_relative;
                                        group.center_energy[spacing_index] =
                                            observation.cumulative_center_energy_relative;
                                        group.affine_matrix_reconstruction[spacing_index] =
                                            observation.affine_reconstruction_relative;
                                        group.present[spacing_index] = true;
                                        update_candidate_summary(
                                            summaries[candidate],
                                            observation,
                                            candidate,
                                            field_kind,
                                            cycles);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

void write_h_convergence(
    bool smoke,
    HashedCsv& csv,
    const std::map<HGroupKey, HGroup>& groups,
    const std::vector<Vec3d>& sweep_phases,
    const std::vector<Orientation>& sweep_orientations,
    std::map<TransferCandidate, CandidateSummary>& summaries) {
    csv.write(
        "mode,seed,candidate,field,phase_index,phase_x,phase_y,phase_z,orientation_index,"
        "orientation,layout,mass_ratio,cycles,dt_quanta,dt_seconds,metric,"
        "error_h_1,error_h_half,error_h_quarter,finest_increase_failure,"
        "all_below_threshold,ratio_rule_pass,"
        "medium_over_coarse,fine_over_medium,fine_over_coarse,convergence_pass\n");
    for (const auto& [key, group] : groups) {
        if (!std::ranges::all_of(group.present, [](bool value) { return value; })) {
            throw std::runtime_error("missing h-convergence row");
        }
        const auto tolerance = reconstruction_claimed(key.candidate, key.field)
            ? std::optional<double>{
                  reconstruction_tolerance(key.candidate, key.field, key.cycles)}
            : std::nullopt;
        const auto particle_result = convergence(group.particle_reconstruction, tolerance);
        const auto grid_result = convergence(group.grid_reconstruction, tolerance);
        const auto candidate_energy_result =
            convergence(group.candidate_augmented_energy, std::nullopt);
        const auto center_energy_result = convergence(group.center_energy, std::nullopt);
        const auto affine_result = convergence(
            group.affine_matrix_reconstruction,
            key.candidate == TransferCandidate::apic
                ? std::optional<double>{reconstruction_tolerance(
                      key.candidate, key.field, key.cycles)}
                : std::nullopt);
        auto& summary = summaries[key.candidate];
        ++summary.h_groups;
        if (!particle_result.pass) {
            ++summary.h_particle_reconstruction_failures;
        }
        if (!grid_result.pass) {
            ++summary.h_grid_reconstruction_failures;
        }
        if (key.candidate == TransferCandidate::apic && !affine_result.pass) {
            ++summary.h_affine_reconstruction_failures;
        }
        if (!candidate_energy_result.pass) {
            ++summary.h_energy_failures;
        }
        if (!center_energy_result.pass) {
            ++summary.h_center_energy_diagnostic_failures;
        }
        const auto phase = sweep_phases[key.phase_index];
        const auto& orientation = sweep_orientations[key.orientation_index];
        const auto emit = [&](std::string_view metric,
                              const std::array<double, 3>& errors,
                              const ConvergenceResult& result) {
            write_csv_row(
                csv,
                smoke ? "smoke" : "full",
                seed,
                mls::experimental::candidate_name(key.candidate),
                field_name(key.field),
                static_cast<unsigned int>(key.phase_index),
                phase.x,
                phase.y,
                phase.z,
                static_cast<unsigned int>(key.orientation_index),
                orientation.label,
                layout_name(key.layout),
                key.mass_ratio,
                key.cycles,
                key.dt_quanta,
                timestep_seconds(key.dt_quanta),
                metric,
                errors[0],
                errors[1],
                errors[2],
                result.finest_increase_failure,
                result.all_below_threshold,
                result.ratio_rule_pass,
                result.medium_over_coarse,
                result.fine_over_medium,
                result.fine_over_coarse,
                result.pass);
        };
        emit("particle_velocity_reconstruction", group.particle_reconstruction, particle_result);
        emit("grid_velocity_reconstruction", group.grid_reconstruction, grid_result);
        emit(
            "absolute_candidate_represented_numerical_energy_residual",
            group.candidate_augmented_energy,
            candidate_energy_result);
        emit(
            "absolute_center_kinetic_numerical_energy_residual",
            group.center_energy,
            center_energy_result);
        if (key.candidate == TransferCandidate::apic) {
            emit(
                "affine_matrix_reconstruction",
                group.affine_matrix_reconstruction,
                affine_result);
        }
    }
}

struct TimeObservation final {
    Observation transfer{};
    std::int64_t dt_quanta{0};
    std::int64_t step_count{0};
    std::int64_t elapsed_quanta{0};
    double position_error_relative{0.0};
    double velocity_error_relative{0.0};
    double physical_time_error_relative{0.0};
};

[[nodiscard]] TimeObservation observe_ballistic_regrid(
    std::vector<TransferParticle> particles,
    const TransferConfig& config,
    TransferCandidate candidate,
    std::int64_t dt_quanta) {
    const auto initial_particles = particles;
    TimeObservation result{};
    result.dt_quanta = dt_quanta;
    result.step_count = fixed_horizon_time_quanta / dt_quanta;
    result.transfer.initial = mls::experimental::particle_totals(particles, config);
    result.transfer.exact_mass_initial =
        mls::experimental::exact_particle_mass_quanta(particles);
    const auto initial_energy = represented_energy(result.transfer.initial, candidate);
    for (std::int64_t step = 0; step < result.step_count; ++step) {
        auto cycle = mls::experimental::transfer_cycle(particles, config, candidate);
        update_observation_pass(result.transfer, cycle, candidate);
        particles = std::move(cycle.particles);
        const auto dt_seconds = timestep_seconds(dt_quanta);
        for (auto& particle : particles) {
            particle.position_m += dt_seconds * particle.velocity_m_per_s;
        }
        result.elapsed_quanta += dt_quanta;
    }
    result.transfer.terminal = mls::experimental::particle_totals(particles, config);
    result.transfer.exact_mass_terminal =
        mls::experimental::exact_particle_mass_quanta(particles);
    result.transfer.exact_mass_ok = result.transfer.exact_mass_ok &&
        result.transfer.exact_mass_initial == result.transfer.exact_mass_terminal;
    const auto terminal_energy = represented_energy(result.transfer.terminal, candidate);
    result.transfer.cumulative_energy_residual_j = terminal_energy - initial_energy;
    result.transfer.cumulative_energy_relative = relative_scalar(terminal_energy, initial_energy);
    result.transfer.cumulative_center_energy_residual_j =
        result.transfer.terminal.center_kinetic_j -
        result.transfer.initial.center_kinetic_j;
    result.transfer.cumulative_center_energy_relative = relative_scalar(
        result.transfer.terminal.center_kinetic_j,
        result.transfer.initial.center_kinetic_j);
    result.transfer.cumulative_linear_relative = relative_vector(
        result.transfer.initial.linear_momentum_kg_m_per_s,
        result.transfer.terminal.linear_momentum_kg_m_per_s);
    result.transfer.cumulative_center_orbital_relative = relative_vector(
        result.transfer.initial.center_orbital_kg_m2_per_s,
        result.transfer.terminal.center_orbital_kg_m2_per_s);
    result.transfer.cumulative_declared_angular_relative = relative_vector(
        claimed_particle_angular(result.transfer.initial, candidate),
        claimed_particle_angular(result.transfer.terminal, candidate));
    result.transfer.center_orbital_diagnostic_pass =
        result.transfer.max_p2g_center_orbital_relative <= angular_momentum_tolerance &&
        result.transfer.max_roundtrip_center_orbital_relative <=
            angular_momentum_tolerance &&
        result.transfer.cumulative_center_orbital_relative <= angular_momentum_tolerance;
    result.transfer.claimed_contract_pass = result.transfer.exact_mass_ok &&
        result.transfer.max_p2g_mass_relative <= mass_tolerance &&
        result.transfer.max_roundtrip_mass_relative <= mass_tolerance &&
        result.transfer.max_p2g_linear_relative <= linear_momentum_tolerance &&
        result.transfer.max_roundtrip_linear_relative <= linear_momentum_tolerance &&
        result.transfer.max_p2g_angular_relative <= angular_momentum_tolerance &&
        result.transfer.max_roundtrip_claimed_angular_relative <=
            angular_momentum_tolerance &&
        result.transfer.cumulative_linear_relative <= linear_momentum_tolerance &&
        result.transfer.cumulative_declared_angular_relative <= angular_momentum_tolerance;
    result.position_error_relative = particle_position_difference(
        particles,
        initial_particles,
        timestep_seconds(fixed_horizon_time_quanta));
    result.velocity_error_relative = particle_velocity_difference(particles, initial_particles);
    result.physical_time_error_relative = relative_scalar(
        timestep_seconds(result.elapsed_quanta),
        timestep_seconds(fixed_horizon_time_quanta));
    return result;
}

void write_time_header(HashedCsv& csv) {
    csv.write(
        "mode,seed,experiment,candidate,field,phase_index,phase_x,phase_y,phase_z,"
        "orientation_index,orientation,layout,grid_spacing_m,mass_ratio,kg_per_mass_quantum,"
        "time_quantum_seconds_num,"
        "time_quantum_seconds_den,dt_quanta,dt_seconds,fixed_horizon_quanta,"
        "fixed_horizon_seconds,step_count,elapsed_quanta,position_error_relative,"
        "velocity_error_relative,physical_time_error_relative,exact_mass_ok,"
        "max_p2g_mass_relative,max_p2g_linear_relative,max_p2g_center_orbital_relative,"
        "max_p2g_declared_angular_relative,"
        "max_roundtrip_mass_relative,max_roundtrip_linear_relative,"
        "max_roundtrip_center_orbital_relative,"
        "max_roundtrip_declared_angular_relative,cumulative_linear_relative,"
        "cumulative_center_orbital_relative,cumulative_declared_angular_relative,"
        "center_orbital_diagnostic_pass,declared_transfer_contract_pass,"
        "max_abs_p2g_candidate_represented_energy_relative,"
        "max_abs_roundtrip_candidate_represented_energy_relative,"
        "cumulative_candidate_represented_numerical_energy_residual_j,"
        "cumulative_candidate_represented_numerical_energy_relative,"
        "cumulative_center_kinetic_numerical_energy_residual_j,"
        "cumulative_center_kinetic_numerical_energy_relative,initial_center_kinetic_j,"
        "initial_affine_auxiliary_kinetic_j,initial_augmented_kinetic_j,"
        "terminal_center_kinetic_j,terminal_affine_auxiliary_kinetic_j,"
        "terminal_augmented_kinetic_j\n");
}

void run_time_sweep(
    bool smoke,
    HashedCsv& csv,
    std::map<TimeGroupKey, TimeGroup>& groups,
    const std::vector<Vec3d>& sweep_phases,
    const std::vector<Orientation>& sweep_orientations,
    std::map<TransferCandidate, CandidateSummary>& summaries) {
    write_time_header(csv);
    for (const auto candidate : {TransferCandidate::pic, TransferCandidate::apic}) {
        for (const auto field_kind : fields()) {
            for (std::size_t phase_index = 0; phase_index < sweep_phases.size(); ++phase_index) {
                const auto phase = sweep_phases[phase_index];
                for (std::size_t orientation_index = 0;
                     orientation_index < sweep_orientations.size(); ++orientation_index) {
                    const auto& orientation = sweep_orientations[orientation_index];
                    const auto field = orient_field(field_kind, orientation);
                    for (const auto layout : layouts()) {
                        for (const auto mass_ratio : {std::int64_t{1}, std::int64_t{17}}) {
                            for (std::size_t spacing_index = 0;
                                 spacing_index < spacings().size(); ++spacing_index) {
                                const auto spacing = spacings()[spacing_index];
                                const TransferConfig config{
                                    spacing,
                                    {phase.x * spacing, phase.y * spacing, phase.z * spacing},
                                    kg_per_mass_quantum,
                                };
                                for (std::size_t dt_index = 0;
                                     dt_index < timestep_quanta().size(); ++dt_index) {
                                    const auto dt_quanta = timestep_quanta()[dt_index];
                                    const auto particles = make_particles(
                                        layout, mass_ratio, orientation, field, candidate);
                                    const auto observation = observe_ballistic_regrid(
                                        particles, config, candidate, dt_quanta);
                                    write_csv_row(
                                        csv,
                                        smoke ? "smoke" : "full",
                                        seed,
                                        "force_free_ballistic_transfer_frequency_sensitivity",
                                        mls::experimental::candidate_name(candidate),
                                        field_name(field_kind),
                                        phase_index,
                                        phase.x,
                                        phase.y,
                                        phase.z,
                                        orientation_index,
                                        orientation.label,
                                        layout_name(layout),
                                        spacing,
                                        mass_ratio,
                                        kg_per_mass_quantum,
                                        time_quantum_seconds_numerator,
                                        time_quantum_seconds_denominator,
                                        dt_quanta,
                                        timestep_seconds(dt_quanta),
                                        fixed_horizon_time_quanta,
                                        timestep_seconds(fixed_horizon_time_quanta),
                                        observation.step_count,
                                        observation.elapsed_quanta,
                                        observation.position_error_relative,
                                        observation.velocity_error_relative,
                                        observation.physical_time_error_relative,
                                        observation.transfer.exact_mass_ok,
                                        observation.transfer.max_p2g_mass_relative,
                                        observation.transfer.max_p2g_linear_relative,
                                        observation.transfer.max_p2g_center_orbital_relative,
                                        observation.transfer.max_p2g_angular_relative,
                                        observation.transfer.max_roundtrip_mass_relative,
                                        observation.transfer.max_roundtrip_linear_relative,
                                        observation.transfer.max_roundtrip_center_orbital_relative,
                                        observation.transfer.max_roundtrip_claimed_angular_relative,
                                        observation.transfer.cumulative_linear_relative,
                                        observation.transfer.cumulative_center_orbital_relative,
                                        observation.transfer.cumulative_declared_angular_relative,
                                        observation.transfer.center_orbital_diagnostic_pass,
                                        observation.transfer.claimed_contract_pass,
                                        observation.transfer.max_abs_p2g_energy_relative,
                                        observation.transfer.max_abs_roundtrip_energy_relative,
                                        observation.transfer.cumulative_energy_residual_j,
                                        observation.transfer.cumulative_energy_relative,
                                        observation.transfer.cumulative_center_energy_residual_j,
                                        observation.transfer.cumulative_center_energy_relative,
                                        observation.transfer.initial.center_kinetic_j,
                                        observation.transfer.initial.affine_auxiliary_kinetic_j,
                                        observation.transfer.initial.augmented_kinetic_j,
                                        observation.transfer.terminal.center_kinetic_j,
                                        observation.transfer.terminal.affine_auxiliary_kinetic_j,
                                        observation.transfer.terminal.augmented_kinetic_j);
                                    const TimeGroupKey key{
                                        candidate,
                                        field_kind,
                                        static_cast<std::uint8_t>(phase_index),
                                        static_cast<std::uint8_t>(orientation_index),
                                        layout,
                                        static_cast<std::uint8_t>(spacing_index),
                                        mass_ratio,
                                    };
                                    auto& group = groups[key];
                                    group.position[dt_index] = observation.position_error_relative;
                                    group.velocity[dt_index] = observation.velocity_error_relative;
                                    group.time[dt_index] = observation.physical_time_error_relative;
                                    group.candidate_augmented_energy[dt_index] =
                                        observation.transfer.cumulative_energy_relative;
                                    group.center_energy[dt_index] =
                                        observation.transfer.cumulative_center_energy_relative;
                                    group.present[dt_index] = true;
                                    auto& summary = summaries[candidate];
                                    if (!observation.transfer.claimed_contract_pass) {
                                        ++summary.time_contract_failures;
                                    }
                                    if (!observation.transfer.exact_mass_ok) {
                                        ++summary.time_exact_mass_failures;
                                    }
                                    if (!observation.transfer.center_orbital_diagnostic_pass) {
                                        ++summary.center_orbital_diagnostic_failures;
                                    }
                                    summary.worst_claimed_angular = std::max(
                                        {summary.worst_claimed_angular,
                                         observation.transfer.max_p2g_angular_relative,
                                         observation.transfer.max_roundtrip_claimed_angular_relative,
                                         observation.transfer.cumulative_declared_angular_relative});
                                    summary.worst_energy_residual = std::max(
                                        {summary.worst_energy_residual,
                                         observation.transfer.max_abs_p2g_energy_relative,
                                         observation.transfer.max_abs_roundtrip_energy_relative,
                                         observation.transfer.cumulative_energy_relative});
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

void write_time_convergence(
    bool smoke,
    HashedCsv& csv,
    const std::map<TimeGroupKey, TimeGroup>& groups,
    const std::vector<Vec3d>& sweep_phases,
    const std::vector<Orientation>& sweep_orientations,
    std::map<TransferCandidate, CandidateSummary>& summaries) {
    csv.write(
        "mode,seed,experiment,candidate,field,phase_index,phase_x,phase_y,phase_z,"
        "orientation_index,orientation,layout,grid_spacing_m,mass_ratio,metric,"
        "error_dt,error_dt_half,error_dt_quarter,finest_increase_failure,"
        "all_below_threshold,ratio_rule_pass,"
        "half_over_dt,quarter_over_half,quarter_over_dt,convergence_pass\n");
    for (const auto& [key, group] : groups) {
        if (!std::ranges::all_of(group.present, [](bool value) { return value; })) {
            throw std::runtime_error("missing time-convergence row");
        }
        const auto position_result = convergence(group.position, std::nullopt);
        const auto velocity_result = convergence(group.velocity, std::nullopt);
        const auto time_result = convergence(group.time, roundoff_floor);
        const auto candidate_energy_result =
            convergence(group.candidate_augmented_energy, std::nullopt);
        const auto center_energy_result = convergence(group.center_energy, std::nullopt);
        auto& summary = summaries[key.candidate];
        ++summary.time_groups;
        if (!position_result.pass) {
            ++summary.time_position_failures;
        }
        if (!velocity_result.pass) {
            ++summary.time_velocity_failures;
        }
        if (!time_result.pass) {
            ++summary.time_clock_failures;
        }
        if (!candidate_energy_result.pass) {
            ++summary.time_energy_failures;
        }
        if (!center_energy_result.pass) {
            ++summary.time_center_energy_diagnostic_failures;
        }
        const auto phase = sweep_phases[key.phase_index];
        const auto& orientation = sweep_orientations[key.orientation_index];
        const auto emit = [&](std::string_view metric,
                              const std::array<double, 3>& errors,
                              const ConvergenceResult& result) {
            write_csv_row(
                csv,
                smoke ? "smoke" : "full",
                seed,
                "force_free_ballistic_transfer_frequency_sensitivity",
                mls::experimental::candidate_name(key.candidate),
                field_name(key.field),
                static_cast<unsigned int>(key.phase_index),
                phase.x,
                phase.y,
                phase.z,
                static_cast<unsigned int>(key.orientation_index),
                orientation.label,
                layout_name(key.layout),
                spacings()[key.spacing_index],
                key.mass_ratio,
                metric,
                errors[0],
                errors[1],
                errors[2],
                result.finest_increase_failure,
                result.all_below_threshold,
                result.ratio_rule_pass,
                result.medium_over_coarse,
                result.fine_over_medium,
                result.fine_over_coarse,
                result.pass);
        };
        emit("fixed_horizon_position_error", group.position, position_result);
        emit("fixed_horizon_velocity_error", group.velocity, velocity_result);
        emit("exact_physical_time_error", group.time, time_result);
        emit(
            "absolute_candidate_represented_numerical_energy_residual",
            group.candidate_augmented_energy,
            candidate_energy_result);
        emit(
            "absolute_center_kinetic_numerical_energy_residual",
            group.center_energy,
            center_energy_result);
    }
}

void run_flip_diagnostic(
    bool smoke,
    HashedCsv& csv,
    const std::vector<Vec3d>& sweep_phases,
    const std::vector<Orientation>& sweep_orientations) {
    csv.write(
        "mode,seed,candidate,eligibility,omitted_redundant_axes,field,phase_index,"
        "phase_x,phase_y,phase_z,orientation_index,orientation,layout,grid_spacing_m,"
        "mass_ratio,kg_per_mass_quantum,particle_count,exact_mass_ok,p2g_mass_relative,"
        "p2g_linear_relative,p2g_center_orbital_relative,identity_velocity_relative,"
        "p2g_center_kinetic_numerical_energy_residual_j,"
        "p2g_center_kinetic_numerical_energy_relative\n");
    for (const auto field_kind : fields()) {
        for (std::size_t phase_index = 0; phase_index < sweep_phases.size(); ++phase_index) {
            const auto phase = sweep_phases[phase_index];
            for (std::size_t orientation_index = 0;
                 orientation_index < sweep_orientations.size(); ++orientation_index) {
                const auto& orientation = sweep_orientations[orientation_index];
                const auto field = orient_field(field_kind, orientation);
                for (const auto layout : layouts()) {
                    for (const auto mass_ratio : {std::int64_t{1}, std::int64_t{17}}) {
                        for (const auto spacing : spacings()) {
                            const TransferConfig config{
                                spacing,
                                {phase.x * spacing, phase.y * spacing, phase.z * spacing},
                                kg_per_mass_quantum,
                            };
                            const auto particles = make_particles(
                                layout,
                                mass_ratio,
                                orientation,
                                field,
                                TransferCandidate::flip_diagnostic);
                            const auto cycle = mls::experimental::transfer_cycle(
                                particles, config, TransferCandidate::flip_diagnostic);
                            const auto identity_error =
                                particle_velocity_difference(cycle.particles, particles);
                            const auto energy_before = cycle.particle_before.center_kinetic_j;
                            write_csv_row(
                                csv,
                                smoke ? "smoke" : "full",
                                seed,
                                "FLIP diagnostic",
                                "ineligible",
                                "cycles_and_dt_omitted_identity_is_mathematically_redundant_without_grid_update",
                                field_name(field_kind),
                                phase_index,
                                phase.x,
                                phase.y,
                                phase.z,
                                orientation_index,
                                orientation.label,
                                layout_name(layout),
                                spacing,
                                mass_ratio,
                                kg_per_mass_quantum,
                                particles.size(),
                                cycle.exact_mass_quanta_before == cycle.exact_mass_quanta_after,
                                relative_scalar(
                                    cycle.particle_before.mass_kg,
                                    cycle.grid_after_p2g.mass_kg),
                                relative_vector(
                                    cycle.particle_before.linear_momentum_kg_m_per_s,
                                    cycle.grid_after_p2g.linear_momentum_kg_m_per_s),
                                relative_vector(
                                    cycle.particle_before.center_orbital_kg_m2_per_s,
                                    cycle.grid_after_p2g.center_orbital_kg_m2_per_s),
                                identity_error,
                                cycle.p2g_numerical_energy_residual_j,
                                relative_scalar(
                                    cycle.grid_after_p2g.center_kinetic_j, energy_before));
                        }
                    }
                }
            }
        }
    }
}

[[nodiscard]] bool candidate_numerically_eligible(
    const CandidateSummary& summary, bool evidence_complete) noexcept {
    return summary.claimed_contract_failures == 0U && summary.exact_mass_failures == 0U &&
        evidence_complete &&
        summary.h_particle_reconstruction_failures == 0U &&
        summary.h_grid_reconstruction_failures == 0U &&
        summary.h_affine_reconstruction_failures == 0U &&
        summary.h_energy_failures == 0U && summary.time_position_failures == 0U &&
        summary.time_velocity_failures == 0U && summary.time_clock_failures == 0U &&
        summary.time_energy_failures == 0U && summary.time_contract_failures == 0U &&
        summary.time_exact_mass_failures == 0U;
}

[[nodiscard]] TransferCandidate choose_candidate(
    const CandidateSummary& pic, const CandidateSummary& apic) noexcept {
    const auto pic_key = std::array{
        pic.worst_affine_reconstruction,
        pic.worst_claimed_angular,
        pic.worst_energy_residual,
        pic.worst_64_cycle_drift,
    };
    const auto apic_key = std::array{
        apic.worst_affine_reconstruction,
        apic.worst_claimed_angular,
        apic.worst_energy_residual,
        apic.worst_64_cycle_drift,
    };
    return std::lexicographical_compare(
               apic_key.begin(), apic_key.end(), pic_key.begin(), pic_key.end())
        ? TransferCandidate::apic
        : TransferCandidate::pic;
}

[[nodiscard]] std::string json_escape(std::string_view value) {
    std::string result;
    for (const auto character : value) {
        switch (character) {
        case '\\':
            result += "\\\\";
            break;
        case '"':
            result += "\\\"";
            break;
        case '\n':
            result += "\\n";
            break;
        case '\r':
            result += "\\r";
            break;
        case '\t':
            result += "\\t";
            break;
        default:
            result += character;
            break;
        }
    }
    return result;
}

void write_candidate_json(
    std::ostream& output,
    std::string_view name,
    const CandidateSummary& summary,
    bool smoke,
    bool evidence_complete,
    bool trailing_comma) {
    const auto numerically_eligible =
        !smoke && candidate_numerically_eligible(summary, evidence_complete);
    output << "    \"" << name << "\": {\n"
           << "      \"selection_eligible\": false,\n"
           << "      \"provisional_numerical_eligible\": "
           << (numerically_eligible ? "true" : "false") << ",\n"
           << "      \"transfer_rows\": " << summary.transfer_rows << ",\n"
           << "      \"claimed_contract_failures\": "
           << summary.claimed_contract_failures << ",\n"
           << "      \"exact_mass_failures\": " << summary.exact_mass_failures << ",\n"
           << "      \"center_orbital_diagnostic_failures\": "
           << summary.center_orbital_diagnostic_failures << ",\n"
           << "      \"h_groups\": " << summary.h_groups << ",\n"
           << "      \"h_particle_reconstruction_failures\": "
           << summary.h_particle_reconstruction_failures << ",\n"
           << "      \"h_grid_reconstruction_failures\": "
           << summary.h_grid_reconstruction_failures << ",\n"
           << "      \"h_affine_reconstruction_failures\": "
           << summary.h_affine_reconstruction_failures << ",\n"
           << "      \"h_energy_failures\": " << summary.h_energy_failures << ",\n"
           << "      \"h_center_energy_diagnostic_failures\": "
           << summary.h_center_energy_diagnostic_failures << ",\n"
           << "      \"time_groups\": " << summary.time_groups << ",\n"
           << "      \"time_position_failures\": "
           << summary.time_position_failures << ",\n"
           << "      \"time_velocity_failures\": "
           << summary.time_velocity_failures << ",\n"
           << "      \"time_clock_failures\": " << summary.time_clock_failures << ",\n"
           << "      \"time_energy_failures\": " << summary.time_energy_failures << ",\n"
           << "      \"time_center_energy_diagnostic_failures\": "
           << summary.time_center_energy_diagnostic_failures << ",\n"
           << "      \"time_contract_failures\": "
           << summary.time_contract_failures << ",\n"
           << "      \"time_exact_mass_failures\": "
           << summary.time_exact_mass_failures << ",\n"
           << "      \"worst_affine_reconstruction\": "
           << format_double(summary.worst_affine_reconstruction) << ",\n"
           << "      \"worst_claimed_angular\": "
           << format_double(summary.worst_claimed_angular) << ",\n"
           << "      \"worst_numerical_energy_residual\": "
           << format_double(summary.worst_energy_residual) << ",\n"
           << "      \"worst_64_cycle_drift\": "
           << format_double(summary.worst_64_cycle_drift) << "\n"
           << "    }" << (trailing_comma ? "," : "") << "\n";
}

void write_summary(
    const std::filesystem::path& path,
    bool smoke,
    const std::map<TransferCandidate, CandidateSummary>& summaries,
    const std::map<std::string, std::string>& hashes,
    const EvidenceCounts& counts,
    std::size_t phase_count,
    std::size_t orientation_count) {
    const auto& pic = summaries.at(TransferCandidate::pic);
    const auto& apic = summaries.at(TransferCandidate::apic);
    std::string recommendation = "no provisional numerical promotion";
    if (smoke) {
        recommendation = "not evaluated: smoke output is nonselection evidence";
    } else {
        const auto pic_eligible = candidate_numerically_eligible(pic, counts.complete);
        const auto apic_eligible = candidate_numerically_eligible(apic, counts.complete);
        if (pic_eligible && apic_eligible) {
            recommendation = std::string(mls::experimental::candidate_name(
                choose_candidate(pic, apic)));
        } else if (pic_eligible) {
            recommendation = "PIC";
        } else if (apic_eligible) {
            recommendation = "APIC";
        }
    }

    std::ofstream output(path, std::ios::binary);
    output.exceptions(std::ios::badbit | std::ios::failbit);
    output.imbue(std::locale::classic());
    output << "{\n"
           << "  \"schema\": \"mls-time-transfer-bakeoff-v2\",\n"
           << "  \"mode\": \"" << (smoke ? "smoke" : "full") << "\",\n"
           << "  \"selection_evidence\": false,\n"
           << "  \"external_gates_required\": [\"runtime source provenance\", "
              "\"deterministic rerun\", \"checkpoint/replay\", \"C++\", \"Python\", "
              "\"Lean\", \"CI\", \"independent bundle verification\"],\n"
           << "  \"seed\": " << seed << ",\n"
           << "  \"source_sha_at_configure\": \""
           << json_escape(MLS_CONFIGURED_SOURCE_SHA) << "\",\n"
           << "  \"source_branch_at_configure\": \""
           << json_escape(MLS_CONFIGURED_SOURCE_BRANCH) << "\",\n"
           << "  \"source_dirty_at_configure\": \""
           << json_escape(MLS_CONFIGURED_SOURCE_DIRTY) << "\",\n"
           << "  \"compiler_id\": \"" << json_escape(MLS_CONFIGURED_COMPILER_ID)
           << "\",\n"
           << "  \"compiler_version\": \""
           << json_escape(MLS_CONFIGURED_COMPILER_VERSION) << "\",\n"
           << "  \"time_scale\": {\"seconds_per_quantum_numerator\": "
           << time_quantum_seconds_numerator
           << ", \"seconds_per_quantum_denominator\": "
           << time_quantum_seconds_denominator
           << ", \"base_dt_quanta\": 4, \"fixed_horizon_quanta\": 4},\n"
           << "  \"mass_scale\": {\"kilograms_per_exact_mass_quantum\": "
           << format_double(kg_per_mass_quantum) << "},\n"
           << "  \"physical_energy_ledger_modified\": false,\n"
           << "  \"energy_differences_are_numerical_residuals_only\": true,\n"
           << "  \"time_experiment_interpretation\": "
              "\"force-free ballistic transfer-frequency sensitivity; not general temporal accuracy\",\n"
           << "  \"excluded_physics\": [\"forces\", \"stress\", \"elasticity\", "
              "\"plasticity\", \"contact\", \"gravity\", \"fracture\", \"diffusion\", "
              "\"reaction kinetics\", \"organisms\", \"rendering\", \"GPU optimization\"],\n"
           << "  \"executed_axis_counts\": {\"phases\": " << phase_count
           << ", \"proper_signed_axis_orientations\": " << orientation_count << "},\n"
           << "  \"frozen_full_axis_counts\": {\"phases\": 4, "
              "\"proper_signed_axis_orientations\": 24},\n"
           << "  \"smoke_omissions\": "
           << (smoke
                   ? "\"phases 1-3, orientations 2-23, cycles 16 and 64; smoke is not selection evidence\""
                   : "null")
            << ",\n"
           << "  \"evidence_counts_complete\": "
           << (counts.complete ? "true" : "false") << ",\n"
           << "  \"evidence_counts\": {\n"
           << "    \"transfer_sweep.csv\": {\"expected_rows\": "
           << counts.expected_transfer_rows << ", \"actual_rows\": "
           << counts.actual_transfer_rows << "},\n"
           << "    \"h_convergence_groups\": {\"expected\": "
           << counts.expected_h_groups << ", \"actual\": " << counts.actual_h_groups
           << "},\n"
           << "    \"h_convergence.csv\": {\"expected_rows\": "
           << counts.expected_h_convergence_rows << ", \"actual_rows\": "
           << counts.actual_h_convergence_rows << "},\n"
           << "    \"ballistic_regrid_sweep.csv\": {\"expected_rows\": "
           << counts.expected_time_raw_rows << ", \"actual_rows\": "
           << counts.actual_time_raw_rows << "},\n"
           << "    \"time_convergence_groups\": {\"expected\": "
           << counts.expected_time_groups << ", \"actual\": "
           << counts.actual_time_groups << "},\n"
           << "    \"time_convergence.csv\": {\"expected_rows\": "
           << counts.expected_time_convergence_rows << ", \"actual_rows\": "
           << counts.actual_time_convergence_rows << "},\n"
           << "    \"flip_identity_diagnostic.csv\": {\"expected_rows\": "
           << counts.expected_flip_rows << ", \"actual_rows\": "
           << counts.actual_flip_rows << "}\n"
           << "  },\n"
           << "  \"flip_diagnostic\": {\"selection_eligible\": false, "
              "\"omitted_redundant_axes\": \"cycles and dt; identity without grid update\"},\n"
           << "  \"declared_angular_contract\": "
              "\"PIC uses center orbital angular momentum; APIC uses center plus affine angular momentum; APIC center-only orbital momentum is diagnostic only\",\n"
           << "  \"energy_convergence_all_below_rule\": "
              "\"no energy hard tolerance was preregistered; only the 5e-14 roundoff floor or ratio branch is used\",\n"
           << "  \"candidates\": {\n";
    write_candidate_json(output, "PIC", pic, smoke, counts.complete, true);
    write_candidate_json(output, "APIC", apic, smoke, counts.complete, false);
    output << "  },\n"
           << "  \"provisional_numerical_recommendation\": \""
           << json_escape(recommendation) << "\",\n"
           << "  \"overall_recommendation\": "
              "\"not issued by numerical harness; external gates required\",\n"
           << "  \"csv_fnv1a64_diagnostic_only\": {\n";
    std::size_t index = 0;
    for (const auto& [name, hash] : hashes) {
        output << "    \"" << json_escape(name) << "\": \"" << hash << "\"";
        ++index;
        output << (index < hashes.size() ? "," : "") << "\n";
    }
    output << "  }\n}\n";
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
            ++index;
            options.output = argv[index];
        } else if (argument == "--help") {
            std::cout
                << "Usage: mls_transfer_bakeoff [--smoke] [--output DIRECTORY]\n"
                << "Without --smoke, executes the complete frozen preregistered sweep.\n";
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
    const auto sweep_phases = phases(options.smoke);
    const auto sweep_orientations = orientations(options.smoke);
    auto counts = expected_counts(
        sweep_phases.size(), sweep_orientations.size(), cycle_counts(options.smoke).size());
    if (!options.smoke &&
        (counts.expected_transfer_rows != 124416U ||
         counts.expected_h_convergence_rows != 186624U ||
         counts.expected_time_raw_rows != 31104U ||
         counts.expected_time_convergence_rows != 51840U ||
         counts.expected_flip_rows != 5184U)) {
        throw std::logic_error("computed full row counts disagree with sealed preregistration");
    }

    HashedCsv transfer_csv(options.output / "transfer_sweep.csv");
    HashedCsv h_csv(options.output / "h_convergence.csv");
    HashedCsv time_csv(options.output / "ballistic_regrid_sweep.csv");
    HashedCsv time_convergence_csv(options.output / "time_convergence.csv");
    HashedCsv flip_csv(options.output / "flip_identity_diagnostic.csv");
    std::map<HGroupKey, HGroup> h_groups;
    std::map<TimeGroupKey, TimeGroup> time_groups;
    std::map<TransferCandidate, CandidateSummary> summaries{
        {TransferCandidate::pic, {}},
        {TransferCandidate::apic, {}},
    };

    run_transfer_sweep(options.smoke, transfer_csv, h_groups, summaries);
    write_h_convergence(
        options.smoke,
        h_csv,
        h_groups,
        sweep_phases,
        sweep_orientations,
        summaries);
    run_time_sweep(
        options.smoke,
        time_csv,
        time_groups,
        sweep_phases,
        sweep_orientations,
        summaries);
    write_time_convergence(
        options.smoke,
        time_convergence_csv,
        time_groups,
        sweep_phases,
        sweep_orientations,
        summaries);
    run_flip_diagnostic(options.smoke, flip_csv, sweep_phases, sweep_orientations);

    counts.actual_transfer_rows = transfer_csv.row_count();
    counts.actual_h_groups = static_cast<std::uint64_t>(h_groups.size());
    counts.actual_h_convergence_rows = h_csv.row_count();
    counts.actual_time_raw_rows = time_csv.row_count();
    counts.actual_time_groups = static_cast<std::uint64_t>(time_groups.size());
    counts.actual_time_convergence_rows = time_convergence_csv.row_count();
    counts.actual_flip_rows = flip_csv.row_count();
    counts.complete = counts.actual_transfer_rows == counts.expected_transfer_rows &&
        counts.actual_h_groups == counts.expected_h_groups &&
        counts.actual_h_convergence_rows == counts.expected_h_convergence_rows &&
        counts.actual_time_raw_rows == counts.expected_time_raw_rows &&
        counts.actual_time_groups == counts.expected_time_groups &&
        counts.actual_time_convergence_rows == counts.expected_time_convergence_rows &&
        counts.actual_flip_rows == counts.expected_flip_rows;

    transfer_csv.close();
    h_csv.close();
    time_csv.close();
    time_convergence_csv.close();
    flip_csv.close();

    const std::map<std::string, std::string> hashes{
        {"ballistic_regrid_sweep.csv", time_csv.hash_hex()},
        {"flip_identity_diagnostic.csv", flip_csv.hash_hex()},
        {"h_convergence.csv", h_csv.hash_hex()},
        {"time_convergence.csv", time_convergence_csv.hash_hex()},
        {"transfer_sweep.csv", transfer_csv.hash_hex()},
    };
    write_summary(
        options.output / "summary.json",
        options.smoke,
        summaries,
        hashes,
        counts,
        sweep_phases.size(),
        sweep_orientations.size());
    std::cout << "Time + Transfer " << (options.smoke ? "smoke" : "full")
              << " evidence written to " << options.output.string() << '\n';
    if (!counts.complete) {
        std::cerr << "mls_transfer_bakeoff: evidence row/group counts are incomplete\n";
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}

} // namespace

int main(int argc, char** argv) {
    try {
        return run(parse_options(argc, argv));
    } catch (const std::exception& error) {
        std::cerr << "mls_transfer_bakeoff: " << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
