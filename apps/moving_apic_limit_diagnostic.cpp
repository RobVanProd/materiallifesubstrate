#include "mls/moving_apic_limit_lab.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <functional>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <locale>
#include <map>
#include <optional>
#include <ranges>
#include <set>
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

using mls::experimental::Matrix3d;
using mls::experimental::TransferConfig;
using mls::experimental::TransferParticle;
using mls::experimental::TransferTotals;
using mls::experimental::Vec3d;
using mls::experimental::affine_advection::AffineField;
using mls::experimental::affine_advection::MovingApicParticle;
using mls::experimental::affine_advection::MovingApicStep;
using mls::experimental::moving_apic_limit::OracleBIntervention;

constexpr std::uint64_t seed = 260828;
constexpr std::int64_t time_quantum_denominator = 160;
constexpr std::int64_t horizon_quanta = 16;
constexpr double time_quantum_s = 1.0 / 160.0;
constexpr double horizon_s = 0.1;
constexpr double kg_per_mass_quantum = 1.0 / 4096.0;
constexpr std::int64_t expected_mass_quanta = 32768;
constexpr double density_kg_per_m3 = 1.0;
constexpr double domain_min_m = -1.0;
constexpr double domain_max_m = 1.0;
constexpr double u_ref_m_per_s = 2.5;
constexpr double cfl = 0.125;

constexpr double mass_tolerance = 2.0e-13;
constexpr double linear_tolerance = 2.0e-12;
constexpr double angular_tolerance = 2.0e-11;
constexpr double representation_tolerance = 5.0e-11;
constexpr double horizon_tolerance = 2.0e-9;
constexpr double roundoff_floor = 5.0e-14;

constexpr std::string_view path_e = "E_JST2017_moving_APIC";
constexpr std::string_view path_oracle = "E_oracleB";
constexpr std::string_view phase_zero = "p000";
constexpr std::string_view phase_hard = "p049_001_083";
constexpr std::string_view summary_schema = "mls.moving-apic-limit.summary.v1";
constexpr std::string_view sealed_csv_sha =
    "67cb234a0ebaf6dac2251412eb845f18c78806b2d92857608f537439d8de2ad1";
constexpr std::string_view sealed_header_sha =
    "174cc146ca76cd9859975e14540d01999d1b74fe8f717eb935b446346bed6330";
constexpr std::string_view sealed_source_sha =
    "bb4b8bafd4a830b08c1e7e751090e850dbea1d7a";
constexpr std::string_view sealed_tag = "affine-advection-lab-evidence-v1";

constexpr std::string_view sealed_header =
    "mode,seed,scope,path,field,phase_index,orientation_index,orientation,layout,mass_ratio,"
    "schedule_index,step_or_remap_count,grid_spacing_m,dt_quanta,dt_seconds,"
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
    "terminal_augmented_representation_energy_diagnostic_j\n";

constexpr std::string_view raw_header =
    "mode,seed,scope,path,phase,level,domain_min_m,domain_max_m,density_kg_per_m3,"
    "grid_phase_x,grid_phase_y,grid_phase_z,grid_spacing_m,timestep_s,time_quantum_s,"
    "timestep_quanta,steps,elapsed_quanta,horizon_s,u_ref_m_per_s,cfl,"
    "nominal_cells_per_axis,nominal_grid_cells,peak_allocated_nodes,particles_per_axis,"
    "particle_count,particles_per_cell,particle_spacing_m,kg_per_mass_quantum,"
    "mass_quanta_per_particle,initial_mass_quanta,terminal_mass_quanta,total_mass_kg,"
    "exact_mass_ok,exact_clock_ok,id_error_count,configuration_error_count,"
    "nonfinite_or_missing_count,static_velocity_error,static_affine_error,static_grid_error,"
    "affine_gradient_error,affine_intercept_error,affine_dispersion_error,"
    "trajectory_position_error,material_velocity_error,linear_momentum_error,"
    "center_orbital_error,center_physical_kinetic_error,max_p2g_mass_error,"
    "max_p2g_linear_error,max_g2p_linear_error,max_p2g_paper_augmented_angular_error,"
    "max_g2p_paper_augmented_angular_error,max_abs_p2g_center_energy_residual_j,"
    "max_abs_p2g_augmented_energy_residual_j,max_abs_step_center_energy_residual_j,"
    "max_abs_step_augmented_energy_residual_j,terminal_center_physical_kinetic_j,"
    "terminal_preoverride_affine_energy_j,terminal_preoverride_augmented_energy_j,"
    "terminal_postoverride_affine_energy_j,terminal_postoverride_augmented_energy_j,"
    "oracle_B_constraint_error,max_oracle_B_override_relative\n";

constexpr std::string_view phase_header =
    "mode,seed,path,level,grid_spacing_m,timestep_s,particle_count,reference_phase,"
    "comparison_phase,position_phase_error,velocity_phase_error,affine_phase_error,"
    "id_error_count,nonfinite_or_missing_count\n";

constexpr std::string_view causal_header =
    "mode,seed,path,phase,level,grid_spacing_m,timestep_s,particle_count,"
    "D_stationarity_error,B_identity_error,C_retention_error,discrepancy_witness_error,"
    "oracle_C_exact_applicable,oracle_C_exact_error,nonfinite_or_missing_count\n";

constexpr std::string_view convergence_header =
    "mode,seed,scope,path,phase,metric,level_ids,hard_tolerance,error_level_0,"
    "error_level_1,error_level_2,error_level_3,all_below,contraction_01,contraction_12,"
    "contraction_23,endpoint_contraction,finest_increase_failure,ratio_rule,pass,"
    "failure_reason\n";

constexpr std::string_view hard_header =
    "mode,seed,scope,path,phase,gate,applicable,expected_configurations,"
    "evaluated_configurations,failure_count,worst_value,tolerance,worst_configuration,pass\n";

constexpr std::string_view prerequisite_header =
    "mode,seed,gate,expected,observed,applicable,evaluated,pass,details\n";

enum class LimitPath : std::uint8_t { paper_e, oracle_b };

[[nodiscard]] constexpr std::string_view path_name(LimitPath path) noexcept {
    return path == LimitPath::paper_e ? path_e : path_oracle;
}

struct Options final {
    bool smoke{false};
    std::filesystem::path output{"evidence/moving-apic-limit-diagnostic"};
    std::optional<std::filesystem::path> sealed_control{};
};

struct Configuration final {
    std::string scope{};
    std::string phase{};
    int level{0};
    double h_m{0.0};
    double dt_s{0.0};
    std::int64_t dt_quanta{0};
    std::int64_t steps{0};
    int cells_per_axis{0};
    int particles_per_axis{0};
    int particles_per_cell{0};
    double particle_spacing_m{0.0};
    std::int64_t mass_quanta_per_particle{0};
    Vec3d phase_fraction{};
};

struct CausalRow final {
    LimitPath path{};
    Configuration config{};
    double D_stationarity_error{0.0};
    double B_identity_error{0.0};
    double C_retention_error{0.0};
    double discrepancy_witness_error{0.0};
    std::optional<double> oracle_C_exact_error{};
    std::uint64_t nonfinite_or_missing_count{0};
};

struct RawRow final {
    LimitPath path{};
    Configuration config{};
    std::size_t peak_allocated_nodes{0};
    std::size_t particle_count{0};
    std::int64_t initial_mass_quanta{0};
    std::int64_t terminal_mass_quanta{0};
    std::int64_t elapsed_quanta{0};
    bool exact_mass_ok{false};
    bool exact_clock_ok{false};
    std::uint64_t id_error_count{0};
    std::uint64_t configuration_error_count{0};
    std::uint64_t nonfinite_or_missing_count{0};
    std::array<double, 11> metrics{};
    double max_p2g_mass_error{0.0};
    double max_p2g_linear_error{0.0};
    double max_g2p_linear_error{0.0};
    double max_p2g_augmented_angular_error{0.0};
    double max_g2p_augmented_angular_error{0.0};
    double max_abs_p2g_center_energy_residual_j{0.0};
    double max_abs_p2g_augmented_energy_residual_j{0.0};
    double max_abs_step_center_energy_residual_j{0.0};
    double max_abs_step_augmented_energy_residual_j{0.0};
    double terminal_center_kinetic_j{0.0};
    double terminal_preoverride_affine_energy_j{0.0};
    double terminal_preoverride_augmented_energy_j{0.0};
    double terminal_postoverride_affine_energy_j{0.0};
    double terminal_postoverride_augmented_energy_j{0.0};
    std::optional<double> oracle_B_constraint_error{};
    std::optional<double> max_oracle_B_override_relative{};
    std::vector<TransferParticle> terminal_particles{};
};

struct PhaseRow final {
    LimitPath path{};
    int level{0};
    double h_m{0.0};
    double dt_s{0.0};
    std::size_t particle_count{0};
    double position_error{0.0};
    double velocity_error{0.0};
    double affine_error{0.0};
    std::uint64_t id_error_count{0};
    std::uint64_t nonfinite_or_missing_count{0};
};

struct ConvergenceRow final {
    std::string scope{};
    std::string path{};
    std::string phase{};
    std::string metric{};
    std::string level_ids{};
    double hard_tolerance{0.0};
    std::array<std::optional<double>, 4> errors{};
    bool all_below{false};
    std::array<std::optional<bool>, 3> contractions{};
    bool endpoint_contraction{false};
    bool finest_increase_failure{false};
    bool ratio_rule{false};
    bool pass{false};
    std::string failure_reason{};
};

struct GateRow final {
    std::string scope{};
    std::string path{};
    std::string phase{};
    std::string gate{};
    bool applicable{false};
    std::size_t expected_configurations{0};
    std::size_t evaluated_configurations{0};
    std::size_t failure_count{0};
    std::optional<double> worst_value{};
    std::optional<double> tolerance{};
    std::string worst_configuration{"NA"};
    bool pass{false};
};

class Csv final {
public:
    Csv(const std::filesystem::path& path, std::string_view header)
        : stream_(path, std::ios::binary) {
        stream_.exceptions(std::ios::badbit | std::ios::failbit);
        stream_.imbue(std::locale::classic());
        stream_.write(header.data(), static_cast<std::streamsize>(header.size()));
    }

    void row(const std::vector<std::string>& values) {
        for (std::size_t index = 0; index < values.size(); ++index) {
            if (index != 0U) {
                stream_ << ',';
            }
            stream_ << values[index];
        }
        stream_ << '\n';
        ++rows_;
    }

    [[nodiscard]] std::size_t rows() const noexcept { return rows_; }

private:
    std::ofstream stream_;
    std::size_t rows_{0};
};

[[nodiscard]] std::string format_double(double value) {
    if (!std::isfinite(value)) {
        return "NA";
    }
    std::ostringstream stream;
    stream.imbue(std::locale::classic());
    stream << std::scientific << std::setprecision(std::numeric_limits<double>::max_digits10)
           << value;
    return stream.str();
}

[[nodiscard]] std::string format_optional(const std::optional<double>& value) {
    return value.has_value() ? format_double(*value) : "NA";
}

[[nodiscard]] std::string format_optional_bool(const std::optional<bool>& value) {
    return value.has_value() ? (*value ? "true" : "false") : "NA";
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

[[nodiscard]] Matrix3d matrix_inverse(const Matrix3d& matrix) {
    const auto& a = matrix.value;
    const double c00 = a[1][1] * a[2][2] - a[1][2] * a[2][1];
    const double c01 = a[1][2] * a[2][0] - a[1][0] * a[2][2];
    const double c02 = a[1][0] * a[2][1] - a[1][1] * a[2][0];
    const double determinant = a[0][0] * c00 + a[0][1] * c01 + a[0][2] * c02;
    const auto scale = std::max(1.0, mls::experimental::frobenius_norm(matrix));
    if (!std::isfinite(determinant) || std::abs(determinant) <=
            128.0 * std::numeric_limits<double>::epsilon() * scale * scale * scale) {
        throw std::domain_error("singular or unresolved 3x3 matrix");
    }
    Matrix3d result{};
    result.value = {{{c00 / determinant,
                      (a[0][2] * a[2][1] - a[0][1] * a[2][2]) / determinant,
                      (a[0][1] * a[1][2] - a[0][2] * a[1][1]) / determinant},
                     {c01 / determinant,
                      (a[0][0] * a[2][2] - a[0][2] * a[2][0]) / determinant,
                      (a[0][2] * a[1][0] - a[0][0] * a[1][2]) / determinant},
                     {c02 / determinant,
                      (a[0][1] * a[2][0] - a[0][0] * a[2][1]) / determinant,
                      (a[0][0] * a[1][1] - a[0][1] * a[1][0]) / determinant}}};
    return result;
}

[[nodiscard]] AffineField initial_field() noexcept {
    Matrix3d gradient{};
    gradient.value = {{{3.0 / 20.0, 2.0 / 5.0, 7.0 / 20.0},
                       {1.0 / 4.0, -1.0 / 10.0, -11.0 / 20.0},
                       {-3.0 / 10.0, 7.0 / 10.0, 1.0 / 5.0}}};
    return {gradient, {111.0 / 125.0, -129.0 / 200.0, -74.0 / 125.0}};
}

[[nodiscard]] Vec3d phase_fraction(std::string_view phase) {
    if (phase == phase_zero) {
        return {0.0, 0.0, 0.0};
    }
    if (phase == phase_hard) {
        return {0.49, 0.01, 0.83};
    }
    throw std::invalid_argument("unknown grid phase");
}

[[nodiscard]] TransferConfig transfer_config(const Configuration& config) noexcept {
    return {config.h_m, config.h_m * config.phase_fraction, kg_per_mass_quantum};
}

[[nodiscard]] std::vector<Configuration> co_refinement_configurations(bool smoke) {
    std::vector<Configuration> result;
    const std::array<std::string_view, 2> phases{phase_zero, phase_hard};
    const int phase_begin = smoke ? 1 : 0;
    const int level_count = smoke ? 1 : 3;
    for (int phase_index = phase_begin; phase_index < 2; ++phase_index) {
        for (int level = 0; level < level_count; ++level) {
            const auto scale = std::int64_t{1} << level;
            Configuration config{};
            config.scope = "co_refinement";
            config.phase = phases[static_cast<std::size_t>(phase_index)];
            config.level = level;
            config.h_m = 0.5 / static_cast<double>(scale);
            config.dt_quanta = 4 / scale;
            config.dt_s = static_cast<double>(config.dt_quanta) * time_quantum_s;
            config.steps = static_cast<std::int64_t>(horizon_quanta / config.dt_quanta);
            config.cells_per_axis = 4 * static_cast<int>(scale);
            config.particles_per_axis = 8 * static_cast<int>(scale);
            config.particles_per_cell = 8;
            config.particle_spacing_m = 0.25 / static_cast<double>(scale);
            config.mass_quanta_per_particle = 64 / scale / scale / scale;
            config.phase_fraction = phase_fraction(config.phase);
            result.push_back(config);
        }
    }
    return result;
}

[[nodiscard]] std::vector<Configuration> particles_per_cell_configurations(bool smoke) {
    std::vector<Configuration> result;
    const int level_count = smoke ? 1 : 3;
    for (int level = 0; level < level_count; ++level) {
        const auto per_axis_cell = std::int64_t{1} << level;
        Configuration config{};
        config.scope = "particles_per_cell";
        config.phase = std::string(phase_hard);
        config.level = level;
        config.h_m = 0.25;
        config.dt_quanta = 2;
        config.dt_s = 1.0 / 80.0;
        config.steps = 8;
        config.cells_per_axis = 8;
        config.particles_per_axis = 8 * static_cast<int>(per_axis_cell);
        config.particles_per_cell = static_cast<int>(per_axis_cell * per_axis_cell * per_axis_cell);
        config.particle_spacing_m = 0.25 / static_cast<double>(per_axis_cell);
        config.mass_quanta_per_particle = 64 / per_axis_cell / per_axis_cell / per_axis_cell;
        config.phase_fraction = phase_fraction(config.phase);
        result.push_back(config);
    }
    return result;
}

[[nodiscard]] std::vector<TransferParticle> make_lattice_particles(
    const Configuration& config, const AffineField& field) {
    std::vector<TransferParticle> particles;
    const auto axis = static_cast<std::size_t>(config.particles_per_axis);
    particles.reserve(axis * axis * axis);
    std::uint64_t id = 1;
    for (int x = 0; x < config.particles_per_axis; ++x) {
        for (int y = 0; y < config.particles_per_axis; ++y) {
            for (int z = 0; z < config.particles_per_axis; ++z) {
                const Vec3d position{
                    domain_min_m + (static_cast<double>(x) + 0.5) * config.particle_spacing_m,
                    domain_min_m + (static_cast<double>(y) + 0.5) * config.particle_spacing_m,
                    domain_min_m + (static_cast<double>(z) + 0.5) * config.particle_spacing_m};
                particles.push_back({
                    id++,
                    config.mass_quanta_per_particle,
                    position,
                    mls::experimental::affine_advection::velocity_at(field, position),
                    field.gradient_per_s});
            }
        }
    }
    return particles;
}

[[nodiscard]] std::vector<MovingApicParticle> initialize_moving_particles(
    const std::vector<TransferParticle>& particles, const TransferConfig& config) {
    std::vector<MovingApicParticle> result;
    result.reserve(particles.size());
    for (const auto& particle : particles) {
        result.push_back(
            mls::experimental::affine_advection::initialize_moving_apic_particle(
                particle, config));
    }
    return result;
}

[[nodiscard]] std::vector<TransferParticle> ballistic_reference(
    const std::vector<TransferParticle>& initial) {
    auto reference = initial;
    for (auto& particle : reference) {
        particle.position_m += horizon_s * particle.velocity_m_per_s;
    }
    return reference;
}

[[nodiscard]] std::uint64_t id_errors(
    const std::vector<TransferParticle>& actual,
    const std::vector<TransferParticle>& reference) {
    std::uint64_t errors = actual.size() == reference.size() ? 0U : 1U;
    std::set<std::uint64_t> ids;
    const auto count = std::min(actual.size(), reference.size());
    for (std::size_t index = 0; index < actual.size(); ++index) {
        if (!ids.insert(actual[index].id).second) {
            ++errors;
        }
        if (index < count && actual[index].id != reference[index].id) {
            ++errors;
        }
    }
    return errors;
}

[[nodiscard]] double vector_rms_error(
    const std::vector<TransferParticle>& actual,
    const std::vector<TransferParticle>& reference,
    bool position) {
    if (actual.size() != reference.size() || actual.empty()) {
        return std::numeric_limits<double>::quiet_NaN();
    }
    long double error_sum = 0.0L;
    long double reference_sum = 0.0L;
    long double total_mass = 0.0L;
    for (std::size_t index = 0; index < actual.size(); ++index) {
        if (actual[index].id != reference[index].id) {
            return std::numeric_limits<double>::quiet_NaN();
        }
        const auto actual_value = position ? actual[index].position_m : actual[index].velocity_m_per_s;
        const auto reference_value = position ? reference[index].position_m : reference[index].velocity_m_per_s;
        const auto difference = actual_value - reference_value;
        const auto mass = static_cast<long double>(reference[index].mass_quanta);
        error_sum += mass * static_cast<long double>(mls::experimental::dot(difference, difference));
        reference_sum += mass * static_cast<long double>(
            mls::experimental::dot(reference_value, reference_value));
        total_mass += mass;
    }
    const auto error = std::sqrt(static_cast<double>(error_sum / total_mass));
    const auto scale = std::sqrt(static_cast<double>(reference_sum / total_mass));
    return error / std::max(1.0, scale);
}

[[nodiscard]] double matrix_rms_error(
    const std::vector<TransferParticle>& particles, const Matrix3d& reference) {
    if (particles.empty()) {
        return std::numeric_limits<double>::quiet_NaN();
    }
    long double error_sum = 0.0L;
    long double reference_sum = 0.0L;
    long double total_mass = 0.0L;
    const auto reference_norm = mls::experimental::frobenius_norm(reference);
    for (const auto& particle : particles) {
        const auto error = mls::experimental::frobenius_norm(
            matrix_subtract(particle.affine_velocity_per_s, reference));
        const auto mass = static_cast<long double>(particle.mass_quanta);
        error_sum += mass * static_cast<long double>(error * error);
        reference_sum += mass * static_cast<long double>(reference_norm * reference_norm);
        total_mass += mass;
    }
    return std::sqrt(static_cast<double>(error_sum / total_mass)) /
        std::max(1.0, std::sqrt(static_cast<double>(reference_sum / total_mass)));
}

struct AffineStatistics final {
    Matrix3d mean_gradient{};
    Vec3d mean_intercept{};
    double dispersion{0.0};
};

[[nodiscard]] AffineStatistics affine_statistics(
    const std::vector<TransferParticle>& particles, const AffineField& reference) {
    AffineStatistics result{};
    long double total_mass = 0.0L;
    for (const auto& particle : particles) {
        const auto mass = static_cast<double>(particle.mass_quanta);
        result.mean_gradient = result.mean_gradient + mass * particle.affine_velocity_per_s;
        result.mean_intercept += mass * (
            particle.velocity_m_per_s -
            mls::experimental::multiply(particle.affine_velocity_per_s, particle.position_m));
        total_mass += static_cast<long double>(particle.mass_quanta);
    }
    const auto inverse_mass = 1.0 / static_cast<double>(total_mass);
    result.mean_gradient = inverse_mass * result.mean_gradient;
    result.mean_intercept = inverse_mass * result.mean_intercept;

    long double gradient_variance = 0.0L;
    long double intercept_variance = 0.0L;
    for (const auto& particle : particles) {
        const auto mass = static_cast<long double>(particle.mass_quanta);
        const auto gradient_delta = mls::experimental::frobenius_norm(
            matrix_subtract(particle.affine_velocity_per_s, result.mean_gradient));
        const auto intercept = particle.velocity_m_per_s -
            mls::experimental::multiply(particle.affine_velocity_per_s, particle.position_m);
        const auto intercept_delta = intercept - result.mean_intercept;
        gradient_variance += mass * static_cast<long double>(gradient_delta * gradient_delta);
        intercept_variance += mass * static_cast<long double>(
            mls::experimental::dot(intercept_delta, intercept_delta));
    }
    const auto gradient_dispersion =
        std::sqrt(static_cast<double>(gradient_variance / total_mass)) /
        std::max(1.0, mls::experimental::frobenius_norm(reference.gradient_per_s));
    const auto intercept_dispersion =
        std::sqrt(static_cast<double>(intercept_variance / total_mass)) /
        std::max(1.0, mls::experimental::norm(reference.offset_m_per_s));
    result.dispersion = std::max(gradient_dispersion, intercept_dispersion);
    return result;
}

[[nodiscard]] double affine_phase_rms_error(
    const std::vector<TransferParticle>& actual,
    const std::vector<TransferParticle>& reference) {
    if (actual.size() != reference.size() || actual.empty()) {
        return std::numeric_limits<double>::quiet_NaN();
    }
    long double error_sum = 0.0L;
    long double reference_sum = 0.0L;
    long double total_mass = 0.0L;
    for (std::size_t index = 0; index < actual.size(); ++index) {
        if (actual[index].id != reference[index].id) {
            return std::numeric_limits<double>::quiet_NaN();
        }
        const auto error = mls::experimental::frobenius_norm(matrix_subtract(
            actual[index].affine_velocity_per_s, reference[index].affine_velocity_per_s));
        const auto reference_norm = mls::experimental::frobenius_norm(
            reference[index].affine_velocity_per_s);
        const auto mass = static_cast<long double>(reference[index].mass_quanta);
        error_sum += mass * static_cast<long double>(error * error);
        reference_sum += mass * static_cast<long double>(reference_norm * reference_norm);
        total_mass += mass;
    }
    return std::sqrt(static_cast<double>(error_sum / total_mass)) /
        std::max(1.0, std::sqrt(static_cast<double>(reference_sum / total_mass)));
}

[[nodiscard]] double moving_grid_reconstruction_error(
    const MovingApicStep& step, const AffineField& field) {
    long double error_sum = 0.0L;
    long double reference_sum = 0.0L;
    long double total_mass = 0.0L;
    for (const auto& [index, node] : step.grid) {
        static_cast<void>(index);
        const auto reference = mls::experimental::affine_advection::velocity_at(
            field, node.old_position_m);
        const auto difference = node.old_velocity_m_per_s - reference;
        const auto mass = static_cast<long double>(node.mass_kg);
        error_sum += mass * static_cast<long double>(
            mls::experimental::dot(difference, difference));
        reference_sum += mass * static_cast<long double>(
            mls::experimental::dot(reference, reference));
        total_mass += mass;
    }
    if (total_mass <= 0.0L) {
        return std::numeric_limits<double>::quiet_NaN();
    }
    return std::sqrt(static_cast<double>(error_sum / total_mass)) /
        std::max(1.0, std::sqrt(static_cast<double>(reference_sum / total_mass)));
}

[[nodiscard]] std::uint64_t count_nonfinite(std::span<const double> values) noexcept {
    return static_cast<std::uint64_t>(std::ranges::count_if(
        values, [](double value) { return !std::isfinite(value); }));
}

void accumulate_step_residuals(RawRow& row, const MovingApicStep& step) {
    row.max_p2g_mass_error = std::max(
        row.max_p2g_mass_error,
        relative_scalar(step.particle_before.mass_kg, step.grid_after_p2g.mass_kg));
    row.max_p2g_linear_error = std::max(
        row.max_p2g_linear_error,
        relative_vector(step.particle_before.linear_momentum_kg_m_per_s,
                        step.grid_after_p2g.linear_momentum_kg_m_per_s));
    row.max_g2p_linear_error = std::max(
        row.max_g2p_linear_error,
        relative_vector(step.grid_after_no_force_evolution.linear_momentum_kg_m_per_s,
                        step.particle_after.linear_momentum_kg_m_per_s));
    row.max_p2g_augmented_angular_error = std::max(
        row.max_p2g_augmented_angular_error,
        relative_vector(step.particle_before.augmented_angular_kg_m2_per_s,
                        step.grid_after_p2g.center_orbital_kg_m2_per_s));
    row.max_g2p_augmented_angular_error = std::max(
        row.max_g2p_augmented_angular_error,
        relative_vector(step.grid_after_no_force_evolution.center_orbital_kg_m2_per_s,
                        step.particle_after.augmented_angular_kg_m2_per_s));
    row.max_abs_p2g_center_energy_residual_j = std::max(
        row.max_abs_p2g_center_energy_residual_j,
        std::abs(step.p2g_center_energy_residual_j));
    row.max_abs_p2g_augmented_energy_residual_j = std::max(
        row.max_abs_p2g_augmented_energy_residual_j,
        std::abs(step.p2g_augmented_representation_energy_residual_j));
    row.max_abs_step_center_energy_residual_j = std::max(
        row.max_abs_step_center_energy_residual_j,
        std::abs(step.step_center_energy_residual_j));
    row.max_abs_step_augmented_energy_residual_j = std::max(
        row.max_abs_step_augmented_energy_residual_j,
        std::abs(step.step_augmented_representation_energy_residual_j));
    row.peak_allocated_nodes = std::max(row.peak_allocated_nodes, step.grid.size());
}

[[nodiscard]] CausalRow make_causal_row(
    LimitPath path,
    const Configuration& config,
    const std::vector<MovingApicParticle>& old_particles,
    const MovingApicStep& paper_step,
    const AffineField& old_field,
    const AffineField& exact_next_field,
    const std::optional<OracleBIntervention>& intervention) {
    CausalRow row{};
    row.path = path;
    row.config = config;
    const auto transfer = transfer_config(config);
    const auto identity = Matrix3d::identity();
    const auto inverse = matrix_inverse(
        identity + config.dt_s * old_field.gradient_per_s);
    const auto predicted_discrepancy = config.dt_s * mls::experimental::multiply(
        mls::experimental::multiply(old_field.gradient_per_s, old_field.gradient_per_s),
        inverse);

    if (old_particles.size() != paper_step.particles.size()) {
        row.nonfinite_or_missing_count = 5;
        row.D_stationarity_error = std::numeric_limits<double>::quiet_NaN();
        row.B_identity_error = std::numeric_limits<double>::quiet_NaN();
        row.C_retention_error = std::numeric_limits<double>::quiet_NaN();
        row.discrepancy_witness_error = std::numeric_limits<double>::quiet_NaN();
        if (path == LimitPath::oracle_b) {
            row.oracle_C_exact_error = std::numeric_limits<double>::quiet_NaN();
        }
        return row;
    }

    for (std::size_t index = 0; index < old_particles.size(); ++index) {
        const auto& old_particle = old_particles[index];
        const auto& paper_particle = paper_step.particles[index];
        const auto D_old = mls::experimental::affine_advection::particle_moment_matrix(
            old_particle.position_m, transfer);
        const auto D_next = mls::experimental::affine_advection::particle_moment_matrix(
            paper_particle.position_m, transfer);
        row.D_stationarity_error = std::max(
            row.D_stationarity_error, relative_matrix(D_next, D_old));
        const auto expected_B = mls::experimental::multiply(
            old_field.gradient_per_s, D_old);
        row.B_identity_error = std::max(
            row.B_identity_error,
            relative_matrix(paper_particle.B_m2_per_s, expected_B));
        const auto paper_C =
            mls::experimental::affine_advection::moving_apic_affine_matrix(
                paper_particle, transfer);
        row.C_retention_error = std::max(
            row.C_retention_error,
            relative_matrix(paper_C, old_field.gradient_per_s));
        const auto observed_discrepancy = matrix_subtract(
            paper_C, exact_next_field.gradient_per_s);
        row.discrepancy_witness_error = std::max(
            row.discrepancy_witness_error,
            relative_matrix(observed_discrepancy, predicted_discrepancy));
        if (path == LimitPath::oracle_b && intervention.has_value()) {
            const auto oracle_C =
                mls::experimental::affine_advection::moving_apic_affine_matrix(
                    intervention->particles[index], transfer);
            row.oracle_C_exact_error = std::max(
                row.oracle_C_exact_error.value_or(0.0),
                relative_matrix(oracle_C, exact_next_field.gradient_per_s));
        }
    }
    const std::array<double, 4> common{
        row.D_stationarity_error,
        row.B_identity_error,
        row.C_retention_error,
        row.discrepancy_witness_error};
    row.nonfinite_or_missing_count = count_nonfinite(common);
    if (path == LimitPath::oracle_b) {
        if (!row.oracle_C_exact_error.has_value() ||
            !std::isfinite(*row.oracle_C_exact_error)) {
            ++row.nonfinite_or_missing_count;
        }
    }
    return row;
}

[[nodiscard]] std::pair<RawRow, CausalRow> run_configuration(
    LimitPath path, const Configuration& config) {
    RawRow row{};
    row.path = path;
    row.config = config;
    const auto field0 = initial_field();
    const auto transfer = transfer_config(config);
    const auto initial = make_lattice_particles(config, field0);
    auto moving = initialize_moving_particles(initial, transfer);
    row.particle_count = initial.size();
    row.initial_mass_quanta = mls::experimental::exact_particle_mass_quanta(initial);

    // Separate dt=0 representation probe. It never advances the physical clock.
    const auto static_step =
        mls::experimental::affine_advection::jst2017_moving_apic_no_force_step(
            moving, transfer, 0.0);
    const auto static_particles =
        mls::experimental::affine_advection::as_transfer_particles(
            static_step.particles, transfer);
    row.metrics[0] = vector_rms_error(static_particles, initial, false);
    row.metrics[1] = matrix_rms_error(static_particles, field0.gradient_per_s);
    row.metrics[2] = moving_grid_reconstruction_error(static_step, field0);
    row.peak_allocated_nodes = static_step.grid.size();

    AffineField exact_field = field0;
    std::optional<CausalRow> causal{};
    std::optional<TransferTotals> last_preoverride_totals{};
    std::optional<TransferTotals> last_postoverride_totals{};
    double max_constraint = 0.0;
    double max_override = 0.0;
    for (std::int64_t step_index = 0; step_index < config.steps; ++step_index) {
        const auto old_moving = moving;
        // This is the accepted Path E call. E_oracleB invokes this exact function
        // exactly once before applying its diagnostic-only B intervention.
        const auto paper_step =
            mls::experimental::affine_advection::jst2017_moving_apic_no_force_step(
                moving, transfer, config.dt_s);
        accumulate_step_residuals(row, paper_step);
        const auto exact_next =
            mls::experimental::affine_advection::convected_affine_field(
                exact_field, config.dt_s);

        std::optional<OracleBIntervention> intervention{};
        if (path == LimitPath::oracle_b) {
            intervention =
                mls::experimental::moving_apic_limit::apply_oracle_B_after_G2P(
                    paper_step.particles, transfer, exact_next);
            max_constraint = std::max(
                max_constraint, intervention->max_relative_B_constraint_error);
            max_override = std::max(
                max_override, intervention->max_relative_B_override);
            moving = intervention->particles;
            last_preoverride_totals = intervention->pre_override_totals;
            last_postoverride_totals = intervention->post_override_totals;
        } else {
            moving = paper_step.particles;
            last_preoverride_totals = paper_step.particle_after;
            last_postoverride_totals = paper_step.particle_after;
        }
        if (step_index == 0) {
            causal = make_causal_row(
                path,
                config,
                old_moving,
                paper_step,
                exact_field,
                exact_next,
                intervention);
        }
        exact_field = exact_next;
        row.elapsed_quanta += config.dt_quanta;
    }

    row.terminal_particles =
        mls::experimental::affine_advection::as_transfer_particles(moving, transfer);
    row.terminal_mass_quanta =
        mls::experimental::exact_particle_mass_quanta(row.terminal_particles);
    row.exact_mass_ok = row.initial_mass_quanta == expected_mass_quanta &&
        row.terminal_mass_quanta == expected_mass_quanta;
    row.exact_clock_ok = row.elapsed_quanta == horizon_quanta;
    row.id_error_count = id_errors(row.terminal_particles, initial);
    row.configuration_error_count = 0;
    const auto nominal_particles = static_cast<std::size_t>(config.particles_per_axis) *
        static_cast<std::size_t>(config.particles_per_axis) *
        static_cast<std::size_t>(config.particles_per_axis);
    if (row.particle_count != nominal_particles ||
        config.mass_quanta_per_particle <= 0 ||
        row.initial_mass_quanta != expected_mass_quanta ||
        std::abs(u_ref_m_per_s * config.dt_s / config.h_m - cfl) > 8.0e-16 ||
        config.steps * config.dt_quanta != horizon_quanta) {
        ++row.configuration_error_count;
    }

    const auto reference_particles = ballistic_reference(initial);
    const auto statistics = affine_statistics(row.terminal_particles, exact_field);
    row.metrics[3] = relative_matrix(
        statistics.mean_gradient, exact_field.gradient_per_s);
    row.metrics[4] = relative_vector(
        statistics.mean_intercept, exact_field.offset_m_per_s);
    row.metrics[5] = statistics.dispersion;
    row.metrics[6] = vector_rms_error(row.terminal_particles, reference_particles, true);
    row.metrics[7] = vector_rms_error(row.terminal_particles, reference_particles, false);
    const auto initial_totals = mls::experimental::particle_totals(initial, transfer);
    const auto terminal_totals =
        mls::experimental::particle_totals(row.terminal_particles, transfer);
    row.metrics[8] = relative_vector(
        terminal_totals.linear_momentum_kg_m_per_s,
        initial_totals.linear_momentum_kg_m_per_s);
    row.metrics[9] = relative_vector(
        terminal_totals.center_orbital_kg_m2_per_s,
        initial_totals.center_orbital_kg_m2_per_s);
    row.metrics[10] = relative_scalar(
        terminal_totals.center_kinetic_j, initial_totals.center_kinetic_j);
    row.terminal_center_kinetic_j = terminal_totals.center_kinetic_j;
    if (last_preoverride_totals.has_value() && last_postoverride_totals.has_value()) {
        row.terminal_preoverride_affine_energy_j =
            last_preoverride_totals->affine_auxiliary_kinetic_j;
        row.terminal_preoverride_augmented_energy_j =
            last_preoverride_totals->augmented_kinetic_j;
        row.terminal_postoverride_affine_energy_j =
            last_postoverride_totals->affine_auxiliary_kinetic_j;
        row.terminal_postoverride_augmented_energy_j =
            last_postoverride_totals->augmented_kinetic_j;
    }
    if (path == LimitPath::oracle_b) {
        row.oracle_B_constraint_error = max_constraint;
        row.max_oracle_B_override_relative = max_override;
    }

    std::vector<double> finite_values(row.metrics.begin(), row.metrics.end());
    const std::array<double, 17> residual_values{
        row.max_p2g_mass_error,
        row.max_p2g_linear_error,
        row.max_g2p_linear_error,
        row.max_p2g_augmented_angular_error,
        row.max_g2p_augmented_angular_error,
        row.max_abs_p2g_center_energy_residual_j,
        row.max_abs_p2g_augmented_energy_residual_j,
        row.max_abs_step_center_energy_residual_j,
        row.max_abs_step_augmented_energy_residual_j,
        row.terminal_center_kinetic_j,
        row.terminal_preoverride_affine_energy_j,
        row.terminal_preoverride_augmented_energy_j,
        row.terminal_postoverride_affine_energy_j,
        row.terminal_postoverride_augmented_energy_j,
        config.h_m,
        config.dt_s,
        config.particle_spacing_m};
    finite_values.insert(finite_values.end(), residual_values.begin(), residual_values.end());
    row.nonfinite_or_missing_count = count_nonfinite(finite_values);
    if (path == LimitPath::oracle_b &&
        (!row.oracle_B_constraint_error.has_value() ||
         !std::isfinite(*row.oracle_B_constraint_error) ||
         !row.max_oracle_B_override_relative.has_value() ||
         !std::isfinite(*row.max_oracle_B_override_relative))) {
        ++row.nonfinite_or_missing_count;
    }
    if (!causal.has_value()) {
        throw std::logic_error("first-step causal row missing");
    }
    return {std::move(row), *causal};
}

[[nodiscard]] std::array<std::string_view, 11> metric_names() noexcept {
    return {"static_velocity",
            "static_affine",
            "static_grid",
            "affine_gradient",
            "affine_intercept",
            "affine_dispersion",
            "trajectory_position",
            "material_velocity",
            "linear_momentum",
            "center_orbital",
            "center_physical_kinetic"};
}

[[nodiscard]] double metric_tolerance(std::size_t metric_index) noexcept {
    return metric_index < 3U ? representation_tolerance : horizon_tolerance;
}

void write_raw_row(Csv& csv, const RawRow& row, bool smoke) {
    const auto& config = row.config;
    const auto cells = static_cast<std::int64_t>(config.cells_per_axis) *
        config.cells_per_axis * config.cells_per_axis;
    const auto ppc_axis = std::cbrt(static_cast<double>(config.particles_per_cell));
    static_cast<void>(ppc_axis);
    csv.row({
        smoke ? "smoke" : "full",
        to_text(seed),
        config.scope,
        std::string(path_name(row.path)),
        config.phase,
        to_text(config.level),
        format_double(domain_min_m),
        format_double(domain_max_m),
        format_double(density_kg_per_m3),
        format_double(config.phase_fraction.x),
        format_double(config.phase_fraction.y),
        format_double(config.phase_fraction.z),
        format_double(config.h_m),
        format_double(config.dt_s),
        format_double(time_quantum_s),
        to_text(config.dt_quanta),
        to_text(config.steps),
        to_text(row.elapsed_quanta),
        format_double(horizon_s),
        format_double(u_ref_m_per_s),
        format_double(u_ref_m_per_s * config.dt_s / config.h_m),
        to_text(config.cells_per_axis),
        to_text(cells),
        to_text(row.peak_allocated_nodes),
        to_text(config.particles_per_axis),
        to_text(row.particle_count),
        to_text(config.particles_per_cell),
        format_double(config.particle_spacing_m),
        format_double(kg_per_mass_quantum),
        to_text(config.mass_quanta_per_particle),
        to_text(row.initial_mass_quanta),
        to_text(row.terminal_mass_quanta),
        format_double(static_cast<double>(row.terminal_mass_quanta) * kg_per_mass_quantum),
        to_text(row.exact_mass_ok),
        to_text(row.exact_clock_ok),
        to_text(row.id_error_count),
        to_text(row.configuration_error_count),
        to_text(row.nonfinite_or_missing_count),
        format_double(row.metrics[0]),
        format_double(row.metrics[1]),
        format_double(row.metrics[2]),
        format_double(row.metrics[3]),
        format_double(row.metrics[4]),
        format_double(row.metrics[5]),
        format_double(row.metrics[6]),
        format_double(row.metrics[7]),
        format_double(row.metrics[8]),
        format_double(row.metrics[9]),
        format_double(row.metrics[10]),
        format_double(row.max_p2g_mass_error),
        format_double(row.max_p2g_linear_error),
        format_double(row.max_g2p_linear_error),
        format_double(row.max_p2g_augmented_angular_error),
        format_double(row.max_g2p_augmented_angular_error),
        format_double(row.max_abs_p2g_center_energy_residual_j),
        format_double(row.max_abs_p2g_augmented_energy_residual_j),
        format_double(row.max_abs_step_center_energy_residual_j),
        format_double(row.max_abs_step_augmented_energy_residual_j),
        format_double(row.terminal_center_kinetic_j),
        format_double(row.terminal_preoverride_affine_energy_j),
        format_double(row.terminal_preoverride_augmented_energy_j),
        format_double(row.terminal_postoverride_affine_energy_j),
        format_double(row.terminal_postoverride_augmented_energy_j),
        format_optional(row.oracle_B_constraint_error),
        format_optional(row.max_oracle_B_override_relative),
    });
}

void write_causal_row(Csv& csv, const CausalRow& row, bool smoke) {
    csv.row({
        smoke ? "smoke" : "full",
        to_text(seed),
        std::string(path_name(row.path)),
        row.config.phase,
        to_text(row.config.level),
        format_double(row.config.h_m),
        format_double(row.config.dt_s),
        to_text(static_cast<std::int64_t>(row.config.particles_per_axis) *
                row.config.particles_per_axis * row.config.particles_per_axis),
        format_double(row.D_stationarity_error),
        format_double(row.B_identity_error),
        format_double(row.C_retention_error),
        format_double(row.discrepancy_witness_error),
        to_text(row.oracle_C_exact_error.has_value()),
        format_optional(row.oracle_C_exact_error),
        to_text(row.nonfinite_or_missing_count),
    });
}

[[nodiscard]] std::vector<RawRow> run_scope(
    const std::vector<Configuration>& configurations,
    Csv& raw_csv,
    Csv* causal_csv,
    std::vector<CausalRow>& causal_rows,
    bool smoke) {
    std::vector<RawRow> rows;
    rows.reserve(configurations.size() * 2U);
    for (const auto& config : configurations) {
        for (const auto path : {LimitPath::paper_e, LimitPath::oracle_b}) {
            auto [raw, causal] = run_configuration(path, config);
            write_raw_row(raw_csv, raw, smoke);
            if (causal_csv != nullptr) {
                write_causal_row(*causal_csv, causal, smoke);
                causal_rows.push_back(causal);
            }
            rows.push_back(std::move(raw));
        }
    }
    return rows;
}

[[nodiscard]] std::vector<PhaseRow> make_phase_rows(
    const std::vector<RawRow>& co_rows) {
    std::vector<PhaseRow> result;
    for (const auto path : {LimitPath::paper_e, LimitPath::oracle_b}) {
        for (int level = 0; level < 3; ++level) {
            const RawRow* zero = nullptr;
            const RawRow* hard = nullptr;
            for (const auto& row : co_rows) {
                if (row.path == path && row.config.level == level) {
                    if (row.config.phase == phase_zero) {
                        zero = &row;
                    } else if (row.config.phase == phase_hard) {
                        hard = &row;
                    }
                }
            }
            if (zero == nullptr || hard == nullptr) {
                throw std::logic_error("phase pair is incomplete");
            }
            PhaseRow phase{};
            phase.path = path;
            phase.level = level;
            phase.h_m = zero->config.h_m;
            phase.dt_s = zero->config.dt_s;
            phase.particle_count = zero->particle_count;
            phase.position_error = vector_rms_error(
                hard->terminal_particles, zero->terminal_particles, true);
            phase.velocity_error = vector_rms_error(
                hard->terminal_particles, zero->terminal_particles, false);
            phase.affine_error = affine_phase_rms_error(
                hard->terminal_particles, zero->terminal_particles);
            phase.id_error_count = id_errors(
                hard->terminal_particles, zero->terminal_particles);
            const std::array<double, 3> values{
                phase.position_error, phase.velocity_error, phase.affine_error};
            phase.nonfinite_or_missing_count = count_nonfinite(values);
            result.push_back(phase);
        }
    }
    return result;
}

void write_phase_row(Csv& csv, const PhaseRow& row, bool smoke) {
    csv.row({
        smoke ? "smoke" : "full",
        to_text(seed),
        std::string(path_name(row.path)),
        to_text(row.level),
        format_double(row.h_m),
        format_double(row.dt_s),
        to_text(row.particle_count),
        std::string(phase_zero),
        std::string(phase_hard),
        format_double(row.position_error),
        format_double(row.velocity_error),
        format_double(row.affine_error),
        to_text(row.id_error_count),
        to_text(row.nonfinite_or_missing_count),
    });
}

[[nodiscard]] ConvergenceRow evaluate_convergence(
    std::string scope,
    std::string path,
    std::string phase,
    std::string metric,
    std::span<const double> errors,
    double tolerance) {
    ConvergenceRow row{};
    row.scope = std::move(scope);
    row.path = std::move(path);
    row.phase = std::move(phase);
    row.metric = std::move(metric);
    row.hard_tolerance = tolerance;
    row.level_ids = errors.size() == 4U ? "0|1|2|3" : "0|1|2";
    for (std::size_t index = 0; index < errors.size() && index < 4U; ++index) {
        row.errors[index] = errors[index];
    }
    if ((errors.size() != 3U && errors.size() != 4U) ||
        std::ranges::any_of(errors, [](double value) {
            return !std::isfinite(value) || value < 0.0;
        })) {
        row.failure_reason = "missing_or_nonfinite";
        return row;
    }
    row.all_below = std::ranges::all_of(
        errors, [tolerance](double value) { return value <= tolerance; });
    for (std::size_t index = 0; index + 1U < errors.size(); ++index) {
        row.contractions[index] = errors[index + 1U] <= 0.70 * errors[index];
    }
    const auto finest = errors.back();
    row.endpoint_contraction = errors.size() == 4U
        ? finest <= 0.125 * errors.front()
        : finest <= 0.25 * errors.front();
    row.finest_increase_failure = finest > roundoff_floor &&
        std::ranges::any_of(errors.first(errors.size() - 1U),
                            [finest](double predecessor) { return finest > predecessor; });
    row.ratio_rule = !row.finest_increase_failure && row.endpoint_contraction;
    for (std::size_t index = 0; index + 1U < errors.size(); ++index) {
        row.ratio_rule = row.ratio_rule && row.contractions[index].value_or(false);
    }
    row.pass = row.all_below || row.ratio_rule;
    if (row.all_below) {
        row.failure_reason = "pass_all_below";
    } else if (row.ratio_rule) {
        row.failure_reason = "pass_ratio";
    } else if (row.finest_increase_failure) {
        row.failure_reason = "finest_increase";
    } else if (!row.endpoint_contraction) {
        row.failure_reason = "endpoint_failed";
    } else {
        row.failure_reason = "contraction_failed";
    }
    return row;
}

void write_convergence_row(Csv& csv, const ConvergenceRow& row, bool smoke) {
    csv.row({
        smoke ? "smoke" : "full",
        to_text(seed),
        row.scope,
        row.path,
        row.phase,
        row.metric,
        row.level_ids,
        format_double(row.hard_tolerance),
        format_optional(row.errors[0]),
        format_optional(row.errors[1]),
        format_optional(row.errors[2]),
        format_optional(row.errors[3]),
        to_text(row.all_below),
        format_optional_bool(row.contractions[0]),
        format_optional_bool(row.contractions[1]),
        format_optional_bool(row.contractions[2]),
        to_text(row.endpoint_contraction),
        to_text(row.finest_increase_failure),
        to_text(row.ratio_rule),
        to_text(row.pass),
        row.failure_reason,
    });
}

[[nodiscard]] std::vector<ConvergenceRow> new_convergence_rows(
    const std::vector<RawRow>& co_rows,
    const std::vector<RawRow>& ppc_rows,
    const std::vector<PhaseRow>& phase_rows) {
    std::vector<ConvergenceRow> result;
    for (const auto path : {LimitPath::paper_e, LimitPath::oracle_b}) {
        for (const auto phase : {phase_zero, phase_hard}) {
            for (std::size_t metric = 0; metric < metric_names().size(); ++metric) {
                std::array<double, 3> errors{};
                for (int level = 0; level < 3; ++level) {
                    const auto found = std::ranges::find_if(co_rows, [&](const RawRow& row) {
                        return row.path == path && row.config.phase == phase &&
                            row.config.level == level;
                    });
                    if (found == co_rows.end()) {
                        throw std::logic_error("co-refinement convergence group incomplete");
                    }
                    errors[static_cast<std::size_t>(level)] = found->metrics[metric];
                }
                result.push_back(evaluate_convergence(
                    "co_refinement",
                    std::string(path_name(path)),
                    std::string(phase),
                    std::string(metric_names()[metric]),
                    errors,
                    metric_tolerance(metric)));
            }
        }
        for (std::size_t metric = 0; metric < metric_names().size(); ++metric) {
            std::array<double, 3> errors{};
            for (int level = 0; level < 3; ++level) {
                const auto found = std::ranges::find_if(ppc_rows, [&](const RawRow& row) {
                    return row.path == path && row.config.level == level;
                });
                if (found == ppc_rows.end()) {
                    throw std::logic_error("particles/cell convergence group incomplete");
                }
                errors[static_cast<std::size_t>(level)] = found->metrics[metric];
            }
            result.push_back(evaluate_convergence(
                "particles_per_cell",
                std::string(path_name(path)),
                "NA",
                std::string(metric_names()[metric]),
                errors,
                metric_tolerance(metric)));
        }
        const std::array<std::pair<std::string_view, double PhaseRow::*>, 3> phase_metrics{{
            {"phase_position", &PhaseRow::position_error},
            {"phase_velocity", &PhaseRow::velocity_error},
            {"phase_affine", &PhaseRow::affine_error},
        }};
        for (const auto& [name, member] : phase_metrics) {
            std::array<double, 3> errors{};
            for (int level = 0; level < 3; ++level) {
                const auto found = std::ranges::find_if(phase_rows, [&](const PhaseRow& row) {
                    return row.path == path && row.level == level;
                });
                if (found == phase_rows.end()) {
                    throw std::logic_error("phase convergence group incomplete");
                }
                errors[static_cast<std::size_t>(level)] = (*found).*member;
            }
            result.push_back(evaluate_convergence(
                "phase_sensitivity",
                std::string(path_name(path)),
                "p000_vs_p049_001_083",
                std::string(name),
                errors,
                horizon_tolerance));
        }
    }
    return result;
}

[[nodiscard]] std::vector<std::string> split_csv_line(std::string_view line) {
    std::vector<std::string> fields;
    std::size_t begin = 0;
    while (begin <= line.size()) {
        const auto comma = line.find(',', begin);
        if (comma == std::string_view::npos) {
            fields.emplace_back(line.substr(begin));
            break;
        }
        fields.emplace_back(line.substr(begin, comma - begin));
        begin = comma + 1U;
    }
    return fields;
}

struct SealedRow final {
    std::map<std::string, std::string> fields{};
};

struct SealedControl final {
    std::string bytes{};
    std::vector<SealedRow> rows{};
};

[[nodiscard]] SealedControl read_sealed_control(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    input.exceptions(std::ios::badbit);
    if (!input) {
        throw std::runtime_error("cannot open sealed fixed-particle control");
    }
    SealedControl result{};
    result.bytes.assign(
        std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
    if (!result.bytes.starts_with(sealed_header)) {
        throw std::runtime_error("sealed fixed-particle header mismatch");
    }
    const auto header_fields = split_csv_line(
        sealed_header.substr(0, sealed_header.size() - 1U));
    std::istringstream stream(result.bytes);
    stream.imbue(std::locale::classic());
    std::string line;
    std::getline(stream, line);
    while (std::getline(stream, line)) {
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        if (line.empty()) {
            continue;
        }
        const auto values = split_csv_line(line);
        if (values.size() != header_fields.size()) {
            throw std::runtime_error("sealed fixed-particle row width mismatch");
        }
        SealedRow row{};
        for (std::size_t index = 0; index < values.size(); ++index) {
            row.fields.emplace(header_fields[index], values[index]);
        }
        result.rows.push_back(std::move(row));
    }
    if (result.rows.size() != 12U) {
        throw std::runtime_error("sealed fixed-particle row count is not 12");
    }
    return result;
}

[[nodiscard]] double sealed_double(const SealedRow& row, std::string_view field) {
    const auto found = row.fields.find(std::string(field));
    if (found == row.fields.end() || found->second == "NA") {
        return std::numeric_limits<double>::quiet_NaN();
    }
    std::size_t parsed = 0;
    const auto value = std::stod(found->second, &parsed);
    if (parsed != found->second.size()) {
        throw std::runtime_error("malformed sealed numeric field");
    }
    return value;
}

[[nodiscard]] bool sealed_bool(const SealedRow& row, std::string_view field) {
    const auto found = row.fields.find(std::string(field));
    if (found == row.fields.end()) {
        throw std::runtime_error("missing sealed boolean field");
    }
    if (found->second == "true") {
        return true;
    }
    if (found->second == "false") {
        return false;
    }
    throw std::runtime_error("malformed sealed boolean field");
}

[[nodiscard]] std::vector<ConvergenceRow> sealed_convergence_rows(
    const SealedControl& sealed) {
    const std::array<std::pair<std::string_view, std::string_view>, 11> columns{{
        {"static_velocity", "static_velocity_error"},
        {"static_affine", "static_affine_error"},
        {"static_grid", "static_grid_error"},
        {"affine_gradient", "affine_gradient_error"},
        {"affine_intercept", "affine_intercept_error"},
        {"affine_dispersion", "affine_dispersion_error"},
        {"trajectory_position", "trajectory_position_error"},
        {"material_velocity", "material_velocity_error"},
        {"linear_momentum", "linear_momentum_error"},
        {"center_orbital", "center_orbital_error"},
        {"center_physical_kinetic", "center_physical_kinetic_error"},
    }};
    const std::array<std::string_view, 3> paths{
        "C_sealed_static_APIC_ballistic",
        "D_analytic_convected_affine_control",
        "E_JST2017_moving_APIC"};
    std::vector<ConvergenceRow> result;
    for (const auto path : paths) {
        for (std::size_t metric = 0; metric < columns.size(); ++metric) {
            std::array<double, 4> errors{};
            std::array<bool, 4> found{};
            for (const auto& row : sealed.rows) {
                if (row.fields.at("path") != path) {
                    continue;
                }
                const auto level = static_cast<std::size_t>(std::stoul(
                    row.fields.at("schedule_index")));
                if (level >= 4U) {
                    throw std::runtime_error("sealed schedule index out of range");
                }
                errors[level] = sealed_double(row, columns[metric].second);
                found[level] = true;
            }
            if (!std::ranges::all_of(found, [](bool value) { return value; })) {
                throw std::runtime_error("sealed convergence family incomplete");
            }
            result.push_back(evaluate_convergence(
                "fixed_particle_control",
                std::string(path),
                "NA",
                std::string(columns[metric].first),
                errors,
                metric_tolerance(metric)));
        }
    }
    return result;
}

[[nodiscard]] GateRow evaluate_gate(
    std::string scope,
    std::string path,
    std::string phase,
    std::string gate,
    bool applicable,
    std::size_t expected,
    std::span<const std::pair<int, double>> values,
    double tolerance) {
    GateRow row{};
    row.scope = std::move(scope);
    row.path = std::move(path);
    row.phase = std::move(phase);
    row.gate = std::move(gate);
    row.applicable = applicable;
    if (!applicable) {
        row.pass = true;
        return row;
    }
    row.expected_configurations = expected;
    row.evaluated_configurations = values.size();
    row.tolerance = tolerance;
    double worst = -1.0;
    int worst_level = -1;
    for (const auto& [level, value] : values) {
        if (!std::isfinite(value) || value > tolerance) {
            ++row.failure_count;
        }
        if (!std::isfinite(value) || value > worst) {
            worst = value;
            worst_level = level;
        }
    }
    row.worst_value = worst;
    row.worst_configuration = worst_level >= 0 ? "level_" + to_text(worst_level) : "NA";
    row.pass = row.evaluated_configurations == row.expected_configurations &&
        row.failure_count == 0U;
    return row;
}

using RawAccessor = std::function<double(const RawRow&)>;
using CausalAccessor = std::function<double(const CausalRow&)>;

[[nodiscard]] std::vector<GateRow> new_hard_gate_rows(
    const std::vector<RawRow>& co_rows,
    const std::vector<RawRow>& ppc_rows,
    const std::vector<CausalRow>& causal_rows,
    bool smoke) {
    struct GateSpec final {
        std::string_view name{};
        double tolerance{0.0};
        bool oracle_only{false};
        bool causal{false};
        bool oracle_causal_only{false};
        RawAccessor raw{};
        CausalAccessor control{};
    };
    const std::array<GateSpec, 17> specs{{
        {"exact_mass_ok", 0.0, false, false, false,
         [](const RawRow& row) { return row.exact_mass_ok ? 0.0 : 1.0; }, {}},
        {"exact_clock_ok", 0.0, false, false, false,
         [](const RawRow& row) { return row.exact_clock_ok ? 0.0 : 1.0; }, {}},
        {"max_p2g_mass_error", mass_tolerance, false, false, false,
         [](const RawRow& row) { return row.max_p2g_mass_error; }, {}},
        {"max_p2g_linear_error", linear_tolerance, false, false, false,
         [](const RawRow& row) { return row.max_p2g_linear_error; }, {}},
        {"max_g2p_linear_error", linear_tolerance, false, false, false,
         [](const RawRow& row) { return row.max_g2p_linear_error; }, {}},
        {"max_p2g_paper_augmented_angular_error", angular_tolerance, false, false, false,
         [](const RawRow& row) { return row.max_p2g_augmented_angular_error; }, {}},
        {"max_g2p_paper_augmented_angular_error", angular_tolerance, false, false, false,
         [](const RawRow& row) { return row.max_g2p_augmented_angular_error; }, {}},
        {"static_grid_error", representation_tolerance, false, false, false,
         [](const RawRow& row) { return row.metrics[2]; }, {}},
        {"oracle_B_constraint_error", representation_tolerance, true, false, false,
         [](const RawRow& row) {
             return row.oracle_B_constraint_error.value_or(
                 std::numeric_limits<double>::quiet_NaN());
         }, {}},
        {"nonfinite_or_missing_count", 0.0, false, false, false,
         [](const RawRow& row) {
             return static_cast<double>(row.nonfinite_or_missing_count);
         }, {}},
        {"configuration_error_count", 0.0, false, false, false,
         [](const RawRow& row) {
             return static_cast<double>(row.configuration_error_count);
         }, {}},
        {"id_error_count", 0.0, false, false, false,
         [](const RawRow& row) { return static_cast<double>(row.id_error_count); }, {}},
        {"first_step_D_stationarity_error", representation_tolerance, false, true, false,
         {}, [](const CausalRow& row) { return row.D_stationarity_error; }},
        {"first_step_B_identity_error", representation_tolerance, false, true, false,
         {}, [](const CausalRow& row) { return row.B_identity_error; }},
        {"first_step_C_retention_error", representation_tolerance, false, true, false,
         {}, [](const CausalRow& row) { return row.C_retention_error; }},
        {"first_step_discrepancy_witness_error", representation_tolerance, false, true, false,
         {}, [](const CausalRow& row) { return row.discrepancy_witness_error; }},
        {"oracle_first_step_C_exact_error", representation_tolerance, false, true, true,
         {}, [](const CausalRow& row) {
             return row.oracle_C_exact_error.value_or(
                 std::numeric_limits<double>::quiet_NaN());
         }},
    }};

    std::vector<GateRow> result;
    struct FamilySpec final {
        std::string scope{};
        LimitPath path{};
        std::string phase{};
        const std::vector<RawRow>* rows{};
    };
    std::vector<FamilySpec> families;
    if (smoke) {
        for (const auto path : {LimitPath::paper_e, LimitPath::oracle_b}) {
            families.push_back({"co_refinement", path, std::string(phase_hard), &co_rows});
            families.push_back({"particles_per_cell", path, "NA", &ppc_rows});
        }
    } else {
        for (const auto path : {LimitPath::paper_e, LimitPath::oracle_b}) {
            for (const auto phase : {phase_zero, phase_hard}) {
                families.push_back({"co_refinement", path, std::string(phase), &co_rows});
            }
            families.push_back({"particles_per_cell", path, "NA", &ppc_rows});
        }
    }
    for (const auto& family : families) {
        std::vector<const RawRow*> family_rows;
        for (const auto& row : *family.rows) {
            const auto phase_matches = family.scope == "particles_per_cell" ||
                row.config.phase == family.phase;
            if (row.path == family.path && phase_matches) {
                family_rows.push_back(&row);
            }
        }
        for (const auto& spec : specs) {
            const bool is_oracle = family.path == LimitPath::oracle_b;
            const bool applicable = (!spec.oracle_only || is_oracle) &&
                (!spec.causal || family.scope == "co_refinement") &&
                (!spec.oracle_causal_only || is_oracle);
            std::vector<std::pair<int, double>> values;
            if (applicable) {
                if (spec.causal) {
                    for (const auto& row : causal_rows) {
                        if (row.path == family.path && row.config.phase == family.phase) {
                            values.emplace_back(row.config.level, spec.control(row));
                        }
                    }
                } else {
                    for (const auto* row : family_rows) {
                        values.emplace_back(row->config.level, spec.raw(*row));
                    }
                }
            }
            result.push_back(evaluate_gate(
                family.scope,
                std::string(path_name(family.path)),
                family.phase,
                std::string(spec.name),
                applicable,
                family_rows.size(),
                values,
                spec.tolerance));
        }
    }
    return result;
}

[[nodiscard]] std::vector<GateRow> sealed_hard_gate_rows(const SealedControl& sealed) {
    struct Spec final {
        std::string_view name{};
        std::optional<std::string_view> column{};
        double tolerance{0.0};
        bool boolean{false};
    };
    const std::array<Spec, 12> applicable_specs{{
        {"exact_mass_ok", "exact_mass_ok", 0.0, true},
        {"exact_clock_ok", "exact_clock_ok", 0.0, true},
        {"max_p2g_mass_error", "max_p2g_mass_error", mass_tolerance, false},
        {"max_p2g_linear_error", "max_p2g_linear_error", linear_tolerance, false},
        {"max_g2p_linear_error", "max_g2p_linear_error", linear_tolerance, false},
        {"max_p2g_paper_augmented_angular_error",
         "max_p2g_paper_augmented_angular_error", angular_tolerance, false},
        {"max_g2p_paper_augmented_angular_error",
         "max_g2p_paper_augmented_angular_error", angular_tolerance, false},
        {"static_grid_error", "static_grid_error", representation_tolerance, false},
        {"nonfinite_or_missing_count", std::nullopt, 0.0, false},
        {"configuration_error_count", std::nullopt, 0.0, false},
        {"id_error_count", std::nullopt, 0.0, false},
        // Placeholder is replaced by the inapplicable vocabulary loop below.
        {"", std::nullopt, 0.0, false},
    }};
    const std::array<std::string_view, 17> vocabulary{
        "exact_mass_ok",
        "exact_clock_ok",
        "max_p2g_mass_error",
        "max_p2g_linear_error",
        "max_g2p_linear_error",
        "max_p2g_paper_augmented_angular_error",
        "max_g2p_paper_augmented_angular_error",
        "static_grid_error",
        "oracle_B_constraint_error",
        "nonfinite_or_missing_count",
        "configuration_error_count",
        "id_error_count",
        "first_step_D_stationarity_error",
        "first_step_B_identity_error",
        "first_step_C_retention_error",
        "first_step_discrepancy_witness_error",
        "oracle_first_step_C_exact_error"};
    const std::array<std::string_view, 3> paths{
        "C_sealed_static_APIC_ballistic",
        "D_analytic_convected_affine_control",
        "E_JST2017_moving_APIC"};
    std::vector<GateRow> result;
    for (const auto path : paths) {
        std::vector<const SealedRow*> rows;
        for (const auto& row : sealed.rows) {
            if (row.fields.at("path") == path) {
                rows.push_back(&row);
            }
        }
        for (const auto gate : vocabulary) {
            const auto spec = std::ranges::find_if(applicable_specs, [&](const Spec& value) {
                return !value.name.empty() && value.name == gate;
            });
            if (spec == applicable_specs.end()) {
                result.push_back(evaluate_gate(
                    "fixed_particle_control",
                    std::string(path),
                    "NA",
                    std::string(gate),
                    false,
                    0,
                    {},
                    0.0));
                continue;
            }
            std::vector<std::pair<int, double>> values;
            for (const auto* row : rows) {
                const auto level = static_cast<int>(std::stol(row->fields.at("schedule_index")));
                double value = 0.0;
                if (spec->column.has_value()) {
                    value = spec->boolean
                        ? (sealed_bool(*row, *spec->column) ? 0.0 : 1.0)
                        : sealed_double(*row, *spec->column);
                }
                values.emplace_back(level, value);
            }
            result.push_back(evaluate_gate(
                "fixed_particle_control",
                std::string(path),
                "NA",
                std::string(gate),
                true,
                4,
                values,
                spec->tolerance));
        }
    }
    return result;
}

void write_gate_row(Csv& csv, const GateRow& row, bool smoke) {
    csv.row({
        smoke ? "smoke" : "full",
        to_text(seed),
        row.scope,
        row.path,
        row.phase,
        row.gate,
        to_text(row.applicable),
        to_text(row.expected_configurations),
        to_text(row.evaluated_configurations),
        to_text(row.failure_count),
        format_optional(row.worst_value),
        format_optional(row.tolerance),
        row.worst_configuration,
        to_text(row.pass),
    });
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
            const auto s1 = rotate_right(e, 6U) ^ rotate_right(e, 11U) ^ rotate_right(e, 25U);
            const auto choose = (e & f) ^ ((~e) & g);
            const auto temporary1 = h + s1 + choose + constants[index] + words[index];
            const auto s0 = rotate_right(a, 2U) ^ rotate_right(a, 13U) ^ rotate_right(a, 22U);
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

struct PrerequisiteStatus final {
    std::string gate{};
    std::string expected{};
    std::string observed{};
    bool applicable{false};
    bool evaluated{false};
    bool pass{false};
    std::string details{};
};

[[nodiscard]] std::vector<PrerequisiteStatus> prerequisites(
    bool smoke, const std::optional<SealedControl>& sealed) {
    if (smoke) {
        return {
            {"accepted_source_sha", std::string(sealed_source_sha), "NA", false, false, false,
             "smoke_provisional"},
            {"immutable_release_tag", std::string(sealed_tag), "NA", false, false, false,
             "smoke_provisional"},
            {"sealed_control_csv_sha256", std::string(sealed_csv_sha), "NA", false, false, false,
             "smoke_provisional"},
            {"sealed_control_header_sha256", std::string(sealed_header_sha), "NA", false, false, false,
             "smoke_provisional"},
        };
    }
    if (!sealed.has_value()) {
        throw std::logic_error("full prerequisites require sealed control");
    }
    const auto csv_hash = sha256(sealed->bytes);
    const auto header_hash = sha256(sealed_header);
    return {
        {"accepted_source_sha", std::string(sealed_source_sha),
         "deferred_to_independent_validator", true, false, false,
         "requires ancestry and zero-diff check for the three sealed Path-E files"},
        {"immutable_release_tag", std::string(sealed_tag),
         "deferred_to_independent_validator", true, false, false,
         "requires remote immutable-tag verification"},
        {"sealed_control_csv_sha256", std::string(sealed_csv_sha), csv_hash,
         true, true, csv_hash == sealed_csv_sha, "computed before byte-for-byte copy"},
        {"sealed_control_header_sha256", std::string(sealed_header_sha), header_hash,
         true, true, header_hash == sealed_header_sha, "computed including LF terminator"},
    };
}

void write_prerequisite_row(Csv& csv, const PrerequisiteStatus& status, bool smoke) {
    csv.row({
        smoke ? "smoke" : "full",
        to_text(seed),
        status.gate,
        status.expected,
        status.observed,
        to_text(status.applicable),
        to_text(status.evaluated),
        to_text(status.pass),
        status.details,
    });
}

[[nodiscard]] bool convergence_pass(
    const std::vector<ConvergenceRow>& rows,
    std::string_view path,
    std::span<const std::string_view> scopes) {
    bool found = false;
    for (const auto& row : rows) {
        if (row.path != path ||
            std::ranges::find(scopes, std::string_view(row.scope)) == scopes.end()) {
            continue;
        }
        found = true;
        if (!row.pass) {
            return false;
        }
    }
    return found;
}

[[nodiscard]] bool hard_pass(
    const std::vector<GateRow>& rows,
    std::string_view path,
    std::span<const std::string_view> scopes) {
    bool found = false;
    for (const auto& row : rows) {
        if (row.path != path ||
            std::ranges::find(scopes, std::string_view(row.scope)) == scopes.end()) {
            continue;
        }
        found = true;
        if (!row.pass) {
            return false;
        }
    }
    return found;
}

struct MetricPartitions final {
    std::vector<std::string> e_fail_oracle_pass{};
    std::vector<std::string> e_fail_oracle_fail{};
    std::vector<std::string> e_pass_oracle_fail{};
    std::vector<std::string> both_pass{};
};

[[nodiscard]] MetricPartitions metric_partitions(
    const std::vector<ConvergenceRow>& rows) {
    std::map<std::tuple<std::string, std::string, std::string>, std::array<std::optional<bool>, 2>> pairs;
    for (const auto& row : rows) {
        if (row.path != path_e && row.path != path_oracle) {
            continue;
        }
        const auto key = std::tuple{row.scope, row.phase, row.metric};
        pairs[key][row.path == path_e ? 0U : 1U] = row.pass;
    }
    MetricPartitions result{};
    for (const auto& [key, values] : pairs) {
        if (!values[0].has_value() || !values[1].has_value()) {
            continue;
        }
        const auto label = std::get<0>(key) + "|" + std::get<1>(key) + "|" +
            std::get<2>(key);
        if (!*values[0] && *values[1]) {
            result.e_fail_oracle_pass.push_back(label);
        } else if (!*values[0] && !*values[1]) {
            result.e_fail_oracle_fail.push_back(label);
        } else if (*values[0] && !*values[1]) {
            result.e_pass_oracle_fail.push_back(label);
        } else {
            result.both_pass.push_back(label);
        }
    }
    return result;
}

[[nodiscard]] std::string json_escape(std::string_view value) {
    std::string result;
    for (const auto character : value) {
        switch (character) {
        case '"': result += "\\\""; break;
        case '\\': result += "\\\\"; break;
        case '\n': result += "\\n"; break;
        case '\r': result += "\\r"; break;
        case '\t': result += "\\t"; break;
        default: result += character; break;
        }
    }
    return result;
}

void write_json_array(std::ostream& output, const std::vector<std::string>& values) {
    output << '[';
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index != 0U) {
            output << ',';
        }
        output << '"' << json_escape(values[index]) << '"';
    }
    output << ']';
}

struct Counts final {
    std::size_t fixed_control{0};
    std::size_t co_refinement{0};
    std::size_t particles_per_cell{0};
    std::size_t phase_sensitivity{0};
    std::size_t causal_controls{0};
    std::size_t convergence{0};
    std::size_t hard_gates{0};
    std::size_t prerequisites{0};
};

[[nodiscard]] std::string computational_decision(
    bool e_core, bool e_density, bool oracle_core, bool oracle_density) {
    if (e_core && oracle_core) {
        return e_density
            ? "E remains viable for research under proper co-refinement; no promotion"
            : "E remains viable under proper co-refinement with unresolved quadrature-density behavior; no promotion";
    }
    if (e_core && !oracle_core) {
        return "E remains viable from proper co-refinement but E_oracleB is invalid for causal attribution; no promotion";
    }
    if (!e_core && !oracle_core) {
        return "reject standard JST moving APIC; both E and E_oracleB fail, remaining defect classified as projection/quadrature";
    }
    if (!e_density && oracle_density) {
        return "reject standard JST moving APIC; E fails while E_oracleB passes core and density, supporting affine-state mismatch";
    }
    if (!e_density && !oracle_density) {
        return "reject standard JST moving APIC; affine-state support coexists with remaining density projection/quadrature";
    }
    return "reject standard JST moving APIC; proper co-refinement and density sequences disagree";
}

void write_summary(
    const std::filesystem::path& path,
    bool smoke,
    const Counts& expected,
    const Counts& actual,
    const std::vector<ConvergenceRow>& convergence,
    const std::vector<GateRow>& gates,
    const std::vector<PrerequisiteStatus>& prerequisite_rows) {
    const std::array<std::string_view, 2> core_scopes{"co_refinement", "phase_sensitivity"};
    const std::array<std::string_view, 1> density_scopes{"particles_per_cell"};
    const auto e_core = !smoke && convergence_pass(convergence, path_e, core_scopes) &&
        hard_pass(gates, path_e, core_scopes);
    const auto oracle_core = !smoke && convergence_pass(convergence, path_oracle, core_scopes) &&
        hard_pass(gates, path_oracle, core_scopes);
    const auto e_density = !smoke && convergence_pass(convergence, path_e, density_scopes) &&
        hard_pass(gates, path_e, density_scopes);
    const auto oracle_density = !smoke && convergence_pass(convergence, path_oracle, density_scopes) &&
        hard_pass(gates, path_oracle, density_scopes);
    const auto prerequisites_complete = !smoke && std::ranges::all_of(
        prerequisite_rows, [](const PrerequisiteStatus& row) {
            return row.applicable && row.evaluated && row.pass;
        });
    const auto counts_complete =
        expected.fixed_control == actual.fixed_control &&
        expected.co_refinement == actual.co_refinement &&
        expected.particles_per_cell == actual.particles_per_cell &&
        expected.phase_sensitivity == actual.phase_sensitivity &&
        expected.causal_controls == actual.causal_controls &&
        expected.convergence == actual.convergence &&
        expected.hard_gates == actual.hard_gates &&
        expected.prerequisites == actual.prerequisites;
    const auto partitions = metric_partitions(convergence);
    const auto provisional = smoke
        ? std::string("smoke provisional; no verdict")
        : computational_decision(e_core, e_density, oracle_core, oracle_density);
    const auto decision = prerequisites_complete && counts_complete
        ? provisional
        : std::string("no viability or causal verdict: external prerequisites or completeness gate pending");

    std::ofstream output(path, std::ios::binary);
    output.exceptions(std::ios::badbit | std::ios::failbit);
    output.imbue(std::locale::classic());
    output << "{\n"
           << "  \"schema\": \"" << summary_schema << "\",\n"
           << "  \"mode\": \"" << (smoke ? "smoke" : "full") << "\",\n"
           << "  \"seed\": " << seed << ",\n"
           << "  \"source\": {\"sha\": \"" << MLS_CONFIGURED_SOURCE_SHA
           << "\", \"branch\": \"" << MLS_CONFIGURED_SOURCE_BRANCH
           << "\", \"dirty\": " << MLS_CONFIGURED_SOURCE_DIRTY << "},\n"
           << "  \"compiler\": {\"id\": \"" << MLS_CONFIGURED_COMPILER_ID
           << "\", \"version\": \"" << MLS_CONFIGURED_COMPILER_VERSION << "\"},\n"
           << "  \"units\": {\"time_quantum_s\": \"1/160\", \"mass_quantum_kg\": \"1/4096\", \"horizon_s\": \"1/10\"},\n"
           << "  \"counts_complete\": " << to_text(counts_complete) << ",\n"
           << "  \"counts\": {\n";
    const auto write_count = [&](std::string_view name, std::size_t wanted, std::size_t got, bool comma) {
        output << "    \"" << name << "\": {\"expected\": " << wanted
               << ", \"actual\": " << got << "}" << (comma ? "," : "") << "\n";
    };
    write_count("fixed_particle_control", expected.fixed_control, actual.fixed_control, true);
    write_count("co_refinement", expected.co_refinement, actual.co_refinement, true);
    write_count("particles_per_cell", expected.particles_per_cell, actual.particles_per_cell, true);
    write_count("phase_sensitivity", expected.phase_sensitivity, actual.phase_sensitivity, true);
    write_count("causal_controls", expected.causal_controls, actual.causal_controls, true);
    write_count("convergence", expected.convergence, actual.convergence, true);
    write_count("hard_gates", expected.hard_gates, actual.hard_gates, true);
    write_count("prerequisites", expected.prerequisites, actual.prerequisites, false);
    output << "  },\n"
           << "  \"prerequisites_complete\": " << to_text(prerequisites_complete) << ",\n"
           << "  \"decision_primitives\": {\n"
           << "    \"E\": {\"core_pass\": " << to_text(e_core)
           << ", \"density_pass\": " << to_text(e_density) << "},\n"
           << "    \"E_oracleB\": {\"core_pass\": " << to_text(oracle_core)
           << ", \"density_pass\": " << to_text(oracle_density) << "}\n"
           << "  },\n"
           << "  \"metric_partitions\": {\n";
    const auto write_partition = [&](std::string_view name, const std::vector<std::string>& values, bool comma) {
        output << "    \"" << name << "\": {\"count\": " << values.size() << ", \"groups\": ";
        write_json_array(output, values);
        output << "}" << (comma ? "," : "") << "\n";
    };
    write_partition("E_fail_oracle_pass", partitions.e_fail_oracle_pass, true);
    write_partition("E_fail_oracle_fail", partitions.e_fail_oracle_fail, true);
    write_partition("E_pass_oracle_fail", partitions.e_pass_oracle_fail, true);
    write_partition("both_pass", partitions.both_pass, false);
    output << "  },\n"
           << "  \"computational_decision\": \"" << json_escape(provisional) << "\",\n"
           << "  \"decision\": \"" << json_escape(decision) << "\",\n"
           << "  \"path_E_promotion_eligible\": false,\n"
           << "  \"path_E_oracleB_promotion_eligible\": false,\n"
           << "  \"energy_policy\": \"center particle kinetic energy is physical; affine and augmented quantities are diagnostics only\",\n"
           << "  \"overall_recommendation\": \"no promotion; stop for head-agent review\"\n"
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
        } else if (argument == "--sealed-control") {
            if (index + 1 >= argc) {
                throw std::invalid_argument("--sealed-control requires coupled_refinement.csv");
            }
            options.sealed_control = std::filesystem::path(argv[++index]);
        } else if (argument == "--help") {
            std::cout
                << "Usage: mls_moving_apic_limit_diagnostic [--smoke] [--output DIRECTORY] "
                   "[--sealed-control coupled_refinement.csv]\n";
            std::exit(EXIT_SUCCESS);
        } else {
            throw std::invalid_argument("unknown argument: " + std::string(argument));
        }
    }
    if (!options.smoke && !options.sealed_control.has_value()) {
        throw std::invalid_argument("full mode requires --sealed-control");
    }
    return options;
}

int run(const Options& options) {
    std::filesystem::create_directories(options.output);
    std::optional<SealedControl> sealed{};
    if (!options.smoke) {
        sealed = read_sealed_control(*options.sealed_control);
        std::ofstream copy(options.output / "fixed_particle_control.csv", std::ios::binary);
        copy.exceptions(std::ios::badbit | std::ios::failbit);
        copy.write(sealed->bytes.data(), static_cast<std::streamsize>(sealed->bytes.size()));
    }

    Csv co_csv(options.output / "co_refinement.csv", raw_header);
    Csv ppc_csv(options.output / "particles_per_cell.csv", raw_header);
    Csv phase_csv(options.output / "phase_sensitivity.csv", phase_header);
    Csv causal_csv(options.output / "causal_controls.csv", causal_header);
    Csv convergence_csv(options.output / "convergence.csv", convergence_header);
    Csv hard_csv(options.output / "hard_gates.csv", hard_header);
    Csv prerequisite_csv(options.output / "prerequisites.csv", prerequisite_header);

    std::vector<CausalRow> causal_rows;
    const auto co_rows = run_scope(
        co_refinement_configurations(options.smoke),
        co_csv,
        &causal_csv,
        causal_rows,
        options.smoke);
    const auto ppc_rows = run_scope(
        particles_per_cell_configurations(options.smoke),
        ppc_csv,
        nullptr,
        causal_rows,
        options.smoke);

    std::vector<PhaseRow> phase_rows;
    std::vector<ConvergenceRow> convergence_rows;
    if (!options.smoke) {
        phase_rows = make_phase_rows(co_rows);
        for (const auto& row : phase_rows) {
            write_phase_row(phase_csv, row, false);
        }
        auto sealed_convergence = sealed_convergence_rows(*sealed);
        auto current_convergence = new_convergence_rows(co_rows, ppc_rows, phase_rows);
        convergence_rows.reserve(sealed_convergence.size() + current_convergence.size());
        std::ranges::move(sealed_convergence, std::back_inserter(convergence_rows));
        std::ranges::move(current_convergence, std::back_inserter(convergence_rows));
    }
    for (const auto& row : convergence_rows) {
        write_convergence_row(convergence_csv, row, options.smoke);
    }

    auto gate_rows = new_hard_gate_rows(
        co_rows, ppc_rows, causal_rows, options.smoke);
    if (!options.smoke) {
        auto old_gates = sealed_hard_gate_rows(*sealed);
        // The preregistered family order is sealed C/D/E followed by the new
        // families; scientific pass/fail does not depend on this presentation.
        old_gates.insert(
            old_gates.end(),
            std::make_move_iterator(gate_rows.begin()),
            std::make_move_iterator(gate_rows.end()));
        gate_rows = std::move(old_gates);
    }
    for (const auto& row : gate_rows) {
        write_gate_row(hard_csv, row, options.smoke);
    }

    const auto prerequisite_rows = prerequisites(options.smoke, sealed);
    for (const auto& row : prerequisite_rows) {
        write_prerequisite_row(prerequisite_csv, row, options.smoke);
    }

    const Counts expected = options.smoke
        ? Counts{0, 2, 2, 0, 2, 0, 68, 4}
        : Counts{12, 12, 6, 6, 12, 105, 153, 4};
    const Counts actual{
        sealed.has_value() ? sealed->rows.size() : 0U,
        co_csv.rows(),
        ppc_csv.rows(),
        phase_csv.rows(),
        causal_csv.rows(),
        convergence_csv.rows(),
        hard_csv.rows(),
        prerequisite_csv.rows()};
    if (expected.fixed_control != actual.fixed_control ||
        expected.co_refinement != actual.co_refinement ||
        expected.particles_per_cell != actual.particles_per_cell ||
        expected.phase_sensitivity != actual.phase_sensitivity ||
        expected.causal_controls != actual.causal_controls ||
        expected.convergence != actual.convergence ||
        expected.hard_gates != actual.hard_gates ||
        expected.prerequisites != actual.prerequisites) {
        throw std::runtime_error("moving APIC limit evidence row counts are incomplete");
    }
    write_summary(
        options.output / "summary.json",
        options.smoke,
        expected,
        actual,
        convergence_rows,
        gate_rows,
        prerequisite_rows);
    std::cout << "Moving APIC Limit " << (options.smoke ? "smoke" : "full")
              << " evidence written to " << options.output.string() << '\n';
    return EXIT_SUCCESS;
}

} // namespace

int main(int argc, char** argv) {
    try {
        return run(parse_options(argc, argv));
    } catch (const std::exception& error) {
        std::cerr << "mls_moving_apic_limit_diagnostic: " << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
