#include "mls/projection_exactness_nullspace_lab.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
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
#include <optional>
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

namespace pen = mls::experimental::projection_exactness_nullspace;
namespace pf = mls::experimental::projection_foundation;
using mls::PhysicalTimeScale;
using mls::experimental::Matrix3d;
using mls::experimental::TransferConfig;
using mls::experimental::Vec3d;

constexpr std::uint64_t seed = 260828;
constexpr double domain_min_m = -0.5;
constexpr double kg_per_mass_quantum = 1.0 / 4096.0;
constexpr std::int64_t expected_mass_quanta = 4096;
constexpr std::uint64_t time_quantum_numerator_s = 1;
constexpr std::uint64_t time_quantum_denominator_s = 160;
constexpr double time_quantum_s = 1.0 / 160.0;
constexpr double forward_gate = 5.0e-10;
constexpr double gradient_visibility_floor_per_s = 1.0e-10;
constexpr double gradient_visibility_bound_multiplier = 1.0e4;
constexpr double dd_safety_factor = 4096.0;
constexpr double null_safety_factor = 512.0;
constexpr std::string_view summary_schema =
    "mls.projection-exactness-nullspace.summary.v1";
constexpr std::string_view manifest_schema =
    "mls.projection-exactness-nullspace.manifest.v1";
constexpr std::string_view accepted_parent_sha =
    "beac8861314e9a2c18e59fd65c426cfdbf75882c";

constexpr std::string_view system_header =
    "system_id,case_class,field,phase,orientation,level,time_quanta,"
    "time_quantum_numerator_s,time_quantum_denominator_s,time_s,h_m,dx_p_m,"
    "kg_per_mass_quantum,exact_mass_quanta,grid_origin_x_m,grid_origin_y_m,"
    "grid_origin_z_m,particle_count,node_count,matrix_nnz,rank_upper_bound,"
    "max_stencil_size,max_particle_contributions_per_node,max_matrix_row_nnz,"
    "a00_per_s,a01_per_s,a02_per_s,a10_per_s,a11_per_s,a12_per_s,a20_per_s,"
    "a21_per_s,a22_per_s,b0_m_per_s,b1_m_per_s,b2_m_per_s,"
    "full_solve_applicable,high_precision_applicable,nullspace_applicable,"
    "assembly_exported,assembly_payload_sha256,"
    "input_checkpoint_sha256_before,input_checkpoint_sha256_after,"
    "diagnostics_read_only_exact";
constexpr std::string_view particle_header =
    "system_id,particle_index,particle_id,mass_kg,x_m,y_m,z_m,vx_m_per_s,"
    "vy_m_per_s,vz_m_per_s";
constexpr std::string_view node_header =
    "system_id,node_index,grid_i,grid_j,grid_k,x_m,y_m,z_m,"
    "analytic_gx_m_per_s,analytic_gy_m_per_s,analytic_gz_m_per_s,"
    "pcg_available,pcg_vhat_x_m_per_s,pcg_vhat_y_m_per_s,"
    "pcg_vhat_z_m_per_s,hp_available,hp_vhat_x_m_per_s,"
    "hp_vhat_y_m_per_s,hp_vhat_z_m_per_s";
constexpr std::string_view stencil_header =
    "system_id,particle_index,node_index,weight,grad_x_per_m,grad_y_per_m,"
    "grad_z_per_m";
constexpr std::string_view matrix_header =
    "system_id,row_node_index,column_node_index,value_kg";
constexpr std::string_view rhs_header =
    "system_id,node_index,component,value_kg_m_per_s";
constexpr std::string_view witness_header =
    "system_id,component,mg_minus_q_l2_kg_m_per_s,mgq_denominator_kg_m_per_s,"
    "normalized_mg_minus_q,mgq_roundoff_bound,mgq_pass,sg_minus_v_l2_m_per_s,"
    "sgv_denominator_m_per_s_sqrt_kg,normalized_sg_minus_v,"
    "sgv_roundoff_bound,sgv_pass,partition_max_residual,partition_roundoff_bound,"
    "partition_pass,linear_reproduction_max_residual_m,"
    "linear_reproduction_roundoff_bound_m,linear_reproduction_pass,"
    "gradient_partition_max_residual_per_m,"
    "gradient_partition_roundoff_bound_per_m,gradient_partition_pass,pass";
constexpr std::string_view solve_header =
    "system_id,component,status,solver,iterations,"
    "backward_residual_l2_kg_m_per_s,backward_denominator_kg_m_per_s,"
    "normalized_backward_residual,grid_forward_lumped_numerator_m_per_s_sqrt_kg,"
    "grid_forward_lumped_denominator_m_per_s_sqrt_kg,normalized_forward_error,"
    "reconstruction_mass_numerator_m_per_s_sqrt_kg,"
    "reconstruction_mass_denominator_m_per_s_sqrt_kg,"
    "normalized_reconstruction_error,raw_condition_value,raw_condition_kind,"
    "preconditioned_condition_value,preconditioned_condition_kind,"
    "condition_times_normalized_residual";
constexpr std::string_view high_precision_header =
    "system_id,component,status,method,precision_bits,decimal_digits,rank,"
    "rank_method,rank_is_certified,regularization,node_dropping,basis_altered,"
    "promotion_eligible,pivot_threshold_relative,smallest_pivot_abs_kg,"
    "largest_pivot_abs_kg,backward_residual_l2_kg_m_per_s,"
    "backward_denominator_kg_m_per_s,normalized_backward_residual,"
    "grid_forward_lumped_numerator_m_per_s_sqrt_kg,"
    "grid_forward_lumped_denominator_m_per_s_sqrt_kg,normalized_forward_error,"
    "reconstruction_mass_numerator_m_per_s_sqrt_kg,"
    "reconstruction_mass_denominator_m_per_s_sqrt_kg,"
    "normalized_reconstruction_error,condition_value,condition_kind";
constexpr std::string_view nullspace_mode_header =
    "system_id,mode_index,node_index,z_value_m_per_s,method,singular_value_kg,"
    "representative_value_m_per_s,shifted_value_m_per_s";
constexpr std::string_view nullspace_metric_header =
    "system_id,mode_index,rank,rank_method,rank_is_certified,"
    "mz_l2_kg_m_per_s,mz_denominator_kg_m_per_s,mz_normalized,"
    "sz_l2_m_per_s,sz_denominator_m_per_s,sz_normalized,"
    "gradient_max_per_s,gradient_rms_per_s,gradient_roundoff_bound_per_s,"
    "visibility_ratio,gradient_visible,alpha_dimensionless,representative_component,"
    "representative_kind,base_residual_normalized,shifted_residual_normalized,"
    "reconstruction_delta_normalized,phase,orientation,promotion_eligible,pass";

enum class FieldKind : std::uint8_t {
    translation,
    rigid_rotation,
    general_affine,
};

struct Orientation final {
    std::string name{};
    Matrix3d matrix{};
};

struct Phase final {
    std::string name{};
    Vec3d fraction{};
};

struct Configuration final {
    std::string system_id{};
    std::string case_class{};
    FieldKind field{FieldKind::translation};
    Phase phase{};
    Orientation orientation{};
    int level{0};
    std::uint64_t time_quanta{0};
    double h_m{0.0};
    double particle_spacing_m{0.0};
    int particles_per_axis{0};
    std::int64_t mass_quanta_per_particle{0};
    bool high_precision{false};
    bool nullspace{false};
    bool assembly_exported{false};
};

struct Options final {
    bool smoke{false};
    bool schema_audit{false};
    std::size_t jobs{1};
    std::filesystem::path output{
        "evidence/projection-exactness-nullspace"};
};

struct AxisMetrics final {
    double backward_l2{0.0};
    double backward_denominator{0.0};
    double backward_normalized{0.0};
    double forward_numerator{0.0};
    double forward_denominator{0.0};
    double forward_normalized{0.0};
    double reconstruction_numerator{0.0};
    double reconstruction_denominator{0.0};
    double reconstruction_normalized{0.0};
};

struct WitnessAxis final {
    double mg_l2{0.0};
    double mg_denominator{0.0};
    double mg_normalized{0.0};
    double sg_l2{0.0};
    double sg_denominator{0.0};
    double sg_normalized{0.0};
    bool mg_pass{false};
    bool sg_pass{false};
};

struct WitnessMetrics final {
    std::array<WitnessAxis, 3> axis{};
    double mg_bound{0.0};
    double sg_bound{0.0};
    double partition_residual{0.0};
    double partition_bound{0.0};
    double linear_residual_m{0.0};
    double linear_bound_m{0.0};
    double gradient_partition_residual_per_m{0.0};
    double gradient_partition_bound_per_m{0.0};
    bool partition_pass{false};
    bool linear_pass{false};
    bool gradient_partition_pass{false};
    bool pass{false};
    std::size_t max_stencil{0};
    std::size_t max_contributions{0};
    std::size_t max_matrix_row_nnz{0};
};

struct StageRow final {
    Configuration config{};
    pen::AffineVelocityField field{};
    WitnessMetrics witness{};
    Vec3d grid_origin_m{};
    std::size_t particle_count{0};
    std::size_t node_count{0};
    std::size_t matrix_nnz{0};
    std::size_t rank_upper_bound{0};
    std::string checkpoint_before{};
    std::string checkpoint_after{};
    bool checkpoint_read_only{false};
};

using Row = std::vector<std::string>;

struct ExportRows final {
    std::vector<Row> particles{};
    std::vector<Row> nodes{};
    std::vector<Row> stencils{};
    std::vector<Row> matrix{};
    std::vector<Row> rhs{};
    std::string digest{};
};

struct NumericRow final {
    std::array<Row, 3> solve_rows{};
    std::vector<Row> high_precision_rows{};
    std::vector<Row> nullspace_mode_rows{};
    std::vector<Row> nullspace_metric_rows{};
    ExportRows exported{};
    bool pcg_miss{false};
    bool hp_full_rank_all_pass{false};
    bool hp_contradiction{false};
    bool hp_ambiguous{false};
    bool null_ambiguous{false};
    bool accepted_null_mode{false};
    bool accepted_gradient_visible{false};
    bool all_constructed_null_modes_accepted{false};
};

[[nodiscard]] double component(Vec3d value, std::size_t axis) noexcept {
    if (axis == 0U) {
        return value.x;
    }
    if (axis == 1U) {
        return value.y;
    }
    return value.z;
}

[[nodiscard]] bool finite(Vec3d value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) &&
        std::isfinite(value.z);
}

[[nodiscard]] std::string bool_text(bool value) {
    return value ? "true" : "false";
}

[[nodiscard]] std::string field_name(FieldKind field) {
    switch (field) {
    case FieldKind::translation:
        return "translation";
    case FieldKind::rigid_rotation:
        return "rigid_rotation";
    case FieldKind::general_affine:
        return "general_affine";
    }
    throw std::logic_error("unknown field");
}

[[nodiscard]] std::array<Phase, 2> phases() {
    return {Phase{"p000", {}},
            Phase{"p049_001_083", {0.49, 0.01, 0.83}}};
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

[[nodiscard]] pen::AffineVelocityField base_field(FieldKind field) {
    pen::AffineVelocityField result{};
    switch (field) {
    case FieldKind::translation:
        result.intercept_m_per_s = {9.0 / 20.0, -3.0 / 10.0, 1.0 / 5.0};
        break;
    case FieldKind::rigid_rotation: {
        const Vec3d omega{3.0 / 10.0, -1.0 / 5.0, 2.0 / 5.0};
        result.gradient_per_s.value =
            {{{0.0, -omega.z, omega.y},
              {omega.z, 0.0, -omega.x},
              {-omega.y, omega.x, 0.0}}};
        result.intercept_m_per_s = {3.0 / 20.0, -1.0 / 10.0, 1.0 / 20.0};
        break;
    }
    case FieldKind::general_affine:
        result.gradient_per_s.value =
            {{{3.0 / 20.0, 2.0 / 5.0, 7.0 / 20.0},
              {1.0 / 4.0, -1.0 / 10.0, -11.0 / 20.0},
              {-3.0 / 10.0, 7.0 / 10.0, 1.0 / 5.0}}};
        result.intercept_m_per_s =
            {111.0 / 125.0, -129.0 / 200.0, -74.0 / 125.0};
        break;
    }
    return result;
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
        throw std::domain_error("singular analytic affine map");
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

[[nodiscard]] pen::AffineVelocityField oriented_initial_field(
    FieldKind field, const Orientation& orientation) {
    const auto source = base_field(field);
    pen::AffineVelocityField result{};
    result.gradient_per_s = mls::experimental::multiply(
        mls::experimental::multiply(orientation.matrix, source.gradient_per_s),
        mls::experimental::transpose(orientation.matrix));
    result.intercept_m_per_s =
        mls::experimental::multiply(orientation.matrix, source.intercept_m_per_s);
    return result;
}

[[nodiscard]] pen::AffineVelocityField convected_field(
    const pen::AffineVelocityField& initial, double time_s) {
    const auto inverse = matrix_inverse(
        Matrix3d::identity() + time_s * initial.gradient_per_s);
    return {
        mls::experimental::multiply(initial.gradient_per_s, inverse),
        mls::experimental::multiply(inverse, initial.intercept_m_per_s),
    };
}

[[nodiscard]] TransferConfig transfer_config(const Configuration& config) {
    const auto origin = config.h_m * config.phase.fraction;
    return {
        config.h_m,
        mls::experimental::multiply(config.orientation.matrix, origin),
        kg_per_mass_quantum,
    };
}

[[nodiscard]] pf::ProjectionLabState physical_state(
    const Configuration& config) {
    pf::ProjectionLabState result{};
    result.config = transfer_config(config);
    result.physical_time_scale = PhysicalTimeScale{
        time_quantum_numerator_s, time_quantum_denominator_s};
    result.elapsed_time_quanta = config.time_quanta;
    const auto source = base_field(config.field);
    const auto time_s = static_cast<double>(config.time_quanta) * time_quantum_s;
    const auto count = static_cast<std::size_t>(config.particles_per_axis);
    result.particles.reserve(count * count * count);
    std::uint64_t id = 1;
    std::int64_t mass_sum = 0;
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
                const auto base_velocity = pen::evaluate(source, base_position);
                const auto oriented_position = mls::experimental::multiply(
                    config.orientation.matrix, base_position);
                const auto oriented_velocity = mls::experimental::multiply(
                    config.orientation.matrix, base_velocity);
                const auto ballistic_position =
                    oriented_position + time_s * oriented_velocity;
                if (!finite(ballistic_position) || !finite(oriented_velocity)) {
                    throw std::overflow_error("non-finite analytic particle state");
                }
                result.particles.push_back({
                    id++, config.mass_quanta_per_particle,
                    ballistic_position, oriented_velocity});
                mass_sum += config.mass_quanta_per_particle;
            }
        }
    }
    if (mass_sum != expected_mass_quanta) {
        throw std::logic_error("registered system does not have 4096 mass quanta");
    }
    return result;
}

[[nodiscard]] std::vector<Configuration> full_configurations() {
    std::vector<Configuration> result;
    const std::array<FieldKind, 3> fields{
        FieldKind::translation, FieldKind::rigid_rotation,
        FieldKind::general_affine};
    const std::array<std::tuple<int, double, double, int, std::int64_t>, 3> levels{
        std::tuple{0, 0.5, 0.25, 4, INT64_C(64)},
        std::tuple{1, 0.25, 0.125, 8, INT64_C(8)},
        std::tuple{2, 0.125, 0.0625, 16, INT64_C(1)},
    };
    for (const auto field : fields) {
        for (const auto time : {UINT64_C(0), UINT64_C(4)}) {
            for (const auto& phase : phases()) {
                for (const auto& orientation : orientations()) {
                    for (const auto& [level, h, spacing, particle_axis, mass] :
                         levels) {
                        const auto id = "main_" + field_name(field) + "_t" +
                            std::to_string(time) + "_l" +
                            std::to_string(level) + "_" + phase.name + "_" +
                            orientation.name;
                        const auto hp = field == FieldKind::general_affine &&
                            time == 0U && level == 1 &&
                            ((phase.name == "p000" &&
                              orientation.name == "p012_sppp") ||
                             (phase.name == "p049_001_083" &&
                              orientation.name == "p210_sppm"));
                        const auto nullspace =
                            field == FieldKind::general_affine && level == 0;
                        result.push_back({
                            id, "main", field, phase, orientation, level, time,
                            h, spacing, particle_axis, mass, hp, nullspace,
                            hp || nullspace});
                    }
                }
            }
        }
    }
    const auto phase_values = phases();
    const auto orientation_values = orientations();
    result.push_back({
        "full_rank_micro_p000_p012_sppp", "full_rank_micro",
        FieldKind::general_affine, phase_values[0], orientation_values[0], 0,
        0, 0.5, 0.125, 8, INT64_C(8), true, false, true});
    result.push_back({
        "full_rank_micro_p049_001_083_p210_sppm", "full_rank_micro",
        FieldKind::general_affine, phase_values[1], orientation_values[1], 0,
        0, 0.5, 0.125, 8, INT64_C(8), true, false, true});
    for (const auto& orientation : orientation_values) {
        result.push_back({
            "singular_ppc1_p049_001_083_" + orientation.name,
            "singular_ppc1", FieldKind::general_affine, phase_values[1],
            orientation, 1, 0, 0.25, 0.25, 4, INT64_C(64), false, true,
            true});
    }
    return result;
}

[[nodiscard]] std::vector<Configuration> configurations(bool smoke) {
    const auto full = full_configurations();
    if (!smoke) {
        return full;
    }
    const std::array<std::string_view, 3> smoke_ids{
        "main_general_affine_t0_l1_p000_p012_sppp",
        "full_rank_micro_p000_p012_sppp",
        "singular_ppc1_p049_001_083_p012_sppp",
    };
    std::vector<Configuration> result;
    for (const auto id : smoke_ids) {
        const auto found = std::find_if(
            full.begin(), full.end(),
            [&](const Configuration& config) { return config.system_id == id; });
        if (found == full.end()) {
            throw std::logic_error("registered smoke system is missing");
        }
        result.push_back(*found);
    }
    return result;
}

[[nodiscard]] double gamma_n(std::size_t operations) {
    const auto product = static_cast<double>(operations) *
        std::numeric_limits<double>::epsilon();
    if (operations == 0U || !(product < 1.0)) {
        throw std::overflow_error("invalid gamma_n denominator");
    }
    return product / (1.0 - product);
}

struct Accurate final {
    double hi{0.0};
    double lo{0.0};
};

[[nodiscard]] Accurate accurate_normalized(double hi, double lo) noexcept {
    const auto sum = hi + lo;
    return {sum, lo - (sum - hi)};
}

[[nodiscard]] Accurate operator+(Accurate lhs, Accurate rhs) noexcept {
    const auto sum = lhs.hi + rhs.hi;
    const auto virtual_rhs = sum - lhs.hi;
    const auto error = (lhs.hi - (sum - virtual_rhs)) +
        (rhs.hi - virtual_rhs) + lhs.lo + rhs.lo;
    return accurate_normalized(sum, error);
}

[[nodiscard]] Accurate operator-(Accurate lhs, Accurate rhs) noexcept {
    return lhs + Accurate{-rhs.hi, -rhs.lo};
}

[[nodiscard]] Accurate operator*(Accurate lhs, Accurate rhs) noexcept {
    const auto product = lhs.hi * rhs.hi;
    const auto error = std::fma(lhs.hi, rhs.hi, -product) +
        lhs.hi * rhs.lo + lhs.lo * rhs.hi + lhs.lo * rhs.lo;
    return accurate_normalized(product, error);
}

Accurate& operator+=(Accurate& lhs, Accurate rhs) noexcept {
    lhs = lhs + rhs;
    return lhs;
}

[[nodiscard]] double accurate_value(Accurate value) noexcept {
    return value.hi + value.lo;
}

[[nodiscard]] Accurate accurate_absolute(Accurate value) noexcept {
    return value.hi < 0.0 || (value.hi == 0.0 && value.lo < 0.0)
        ? Accurate{-value.hi, -value.lo}
        : value;
}

[[nodiscard]] double accurate_norm3(
    Accurate x, Accurate y, Accurate z) noexcept {
    const auto squared = x * x + y * y + z * z;
    return std::sqrt(std::max(0.0, accurate_value(squared)));
}

[[nodiscard]] WitnessMetrics evaluate_witness(
    const pf::ProjectionSystem& system,
    const pen::AffineVelocityField& field) {
    WitnessMetrics result{};
    const auto witness = pen::evaluate_analytic_affine_witness(system, field);
    result.max_stencil = witness.maximum_particle_stencil_size;
    result.max_contributions =
        witness.maximum_rhs_particle_contributions_per_row;
    result.max_matrix_row_nnz = witness.maximum_matrix_row_nonzeros;
    if (result.max_stencil == 0U || result.max_contributions == 0U ||
        result.max_matrix_row_nnz == 0U) {
        throw std::logic_error("nonempty system reported a zero witness count");
    }
    result.mg_bound = 128.0 * gamma_n(std::max({
        result.max_matrix_row_nnz, result.max_contributions,
        2U * result.max_stencil}));
    result.sg_bound = 128.0 * gamma_n(result.max_stencil);
    result.partition_residual = 0.0;
    result.partition_bound = 32.0 * gamma_n(result.max_stencil);
    result.linear_residual_m = 0.0;
    double max_position_norm = 0.0;
    for (const auto& particle : system.particles()) {
        max_position_norm = std::max(
            max_position_norm, mls::experimental::norm(particle.position_m));
    }
    result.linear_bound_m = 64.0 * gamma_n(result.max_stencil) *
        std::max({1.0, system.config().grid_spacing_m, max_position_norm});
    result.gradient_partition_residual_per_m = 0.0;
    result.gradient_partition_bound_per_m =
        64.0 * gamma_n(3U * result.max_stencil) *
        std::max(1.0, 1.0 / system.config().grid_spacing_m);

    // The table contract uses particlewise Euclidean residuals. Recompute
    // these from the exact exported binary64 entries with twofold arithmetic;
    // the core aggregate intentionally stores a componentwise max instead.
    for (std::size_t particle = 0;
         particle < system.particles().size(); ++particle) {
        Accurate partition{};
        std::array<Accurate, 3> linear{};
        std::array<Accurate, 3> gradient_partition{};
        for (const auto& entry : system.particle_stencils()[particle]) {
            partition += Accurate{entry.weight, 0.0};
            const auto node =
                system.active_node_positions_m()[entry.node_index];
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                linear[axis] += Accurate{entry.weight, 0.0} *
                    Accurate{component(node, axis), 0.0};
            }
            const auto basis = pen::evaluate_quadratic_bspline_basis(
                system.particles()[particle].position_m, node,
                system.config().grid_spacing_m);
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                gradient_partition[axis] +=
                    Accurate{component(basis.gradient_m_inv, axis), 0.0};
            }
        }
        partition = partition - Accurate{1.0, 0.0};
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            linear[axis] = linear[axis] - Accurate{component(
                system.particles()[particle].position_m, axis), 0.0};
        }
        result.partition_residual = std::max(
            result.partition_residual, std::abs(accurate_value(partition)));
        result.linear_residual_m = std::max(
            result.linear_residual_m,
            accurate_norm3(linear[0], linear[1], linear[2]));
        result.gradient_partition_residual_per_m = std::max(
            result.gradient_partition_residual_per_m,
            accurate_norm3(
                gradient_partition[0], gradient_partition[1],
                gradient_partition[2]));
    }

    const auto& analytic = witness.analytic_grid_velocity_m_per_s;
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        Accurate mg_squared{};
        Accurate absolute_mg_squared{};
        Accurate q_squared{};
        for (std::size_t row = 0; row < system.active_nodes().size(); ++row) {
            const auto q = component(
                system.consistent_rhs_kg_m_per_s()[row], axis);
            Accurate exact_applied{};
            Accurate absolute_mg{};
            for (const auto& [column, coefficient] :
                 system.consistent_mass_rows()[row]) {
                const auto product = Accurate{coefficient, 0.0} *
                    Accurate{component(analytic[column], axis), 0.0};
                exact_applied += product;
                absolute_mg += accurate_absolute(product);
            }
            const auto residual = exact_applied - Accurate{q, 0.0};
            mg_squared += residual * residual;
            q_squared += Accurate{q, 0.0} * Accurate{q, 0.0};
            absolute_mg_squared += absolute_mg * absolute_mg;
        }
        auto& metric = result.axis[axis];
        metric.mg_l2 = std::sqrt(std::max(0.0, accurate_value(mg_squared)));
        metric.mg_denominator =
            std::sqrt(std::max(0.0, accurate_value(absolute_mg_squared))) +
            std::sqrt(std::max(0.0, accurate_value(q_squared)));
        if (!(metric.mg_denominator > 0.0)) {
            throw std::logic_error("zero analytic equation denominator");
        }
        metric.mg_normalized = metric.mg_l2 / metric.mg_denominator;

        Accurate sg_squared{};
        Accurate reference_squared{};
        Accurate mass_sum{};
        for (std::size_t particle = 0;
             particle < system.particles().size(); ++particle) {
            const auto mass = system.particle_mass_kg()[particle];
            const auto expected = component(
                system.particles()[particle].velocity_m_per_s, axis);
            Accurate exact_reconstructed{};
            for (const auto& entry : system.particle_stencils()[particle]) {
                exact_reconstructed += Accurate{entry.weight, 0.0} *
                    Accurate{component(
                        analytic[entry.node_index], axis), 0.0};
            }
            const auto residual =
                exact_reconstructed - Accurate{expected, 0.0};
            sg_squared += Accurate{mass, 0.0} * residual * residual;
            reference_squared += Accurate{mass, 0.0} *
                Accurate{expected, 0.0} * Accurate{expected, 0.0};
            mass_sum += Accurate{mass, 0.0};
        }
        metric.sg_l2 =
            std::sqrt(std::max(0.0, accurate_value(sg_squared)));
        metric.sg_denominator = std::max(
            std::sqrt(std::max(0.0, accurate_value(reference_squared))),
            std::sqrt(std::max(0.0, accurate_value(mass_sum))));
        if (!(metric.sg_denominator > 0.0)) {
            throw std::logic_error("zero analytic reconstruction denominator");
        }
        metric.sg_normalized = metric.sg_l2 / metric.sg_denominator;
        metric.mg_pass = std::isfinite(metric.mg_normalized) &&
            metric.mg_normalized <= result.mg_bound;
        metric.sg_pass = std::isfinite(metric.sg_normalized) &&
            metric.sg_normalized <= result.sg_bound;
    }
    result.partition_pass = std::isfinite(result.partition_residual) &&
        result.partition_residual <= result.partition_bound;
    result.linear_pass = std::isfinite(result.linear_residual_m) &&
        result.linear_residual_m <= result.linear_bound_m;
    result.gradient_partition_pass =
        std::isfinite(result.gradient_partition_residual_per_m) &&
        result.gradient_partition_residual_per_m <=
            result.gradient_partition_bound_per_m;
    result.pass = result.partition_pass && result.linear_pass &&
        result.gradient_partition_pass;
    for (const auto& metric : result.axis) {
        result.pass = result.pass && metric.mg_pass && metric.sg_pass;
    }
    return result;
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
                rotate_right(words[index - 15U], 18U) ^
                (words[index - 15U] >> 3U);
            const auto s1 = rotate_right(words[index - 2U], 17U) ^
                rotate_right(words[index - 2U], 19U) ^
                (words[index - 2U] >> 10U);
            words[index] = words[index - 16U] + s0 +
                words[index - 7U] + s1;
        }
        auto [a, b, c, d, e, f, g, h] = hash;
        for (std::size_t index = 0; index < 64U; ++index) {
            const auto s1 = rotate_right(e, 6U) ^ rotate_right(e, 11U) ^
                rotate_right(e, 25U);
            const auto choose = (e & f) ^ ((~e) & g);
            const auto temporary1 =
                h + s1 + choose + constants[index] + words[index];
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
    for (const auto value : hash) {
        output << std::setw(8) << value;
    }
    return output.str();
}

[[nodiscard]] std::string checkpoint_hash(
    std::span<const std::uint8_t> checkpoint) {
    return sha256(std::string_view(
        reinterpret_cast<const char*>(checkpoint.data()), checkpoint.size()));
}

// Equivalent to Python binary64.hex(): one canonical, lowercase C99 literal.
[[nodiscard]] std::string hex64(double value) {
    if (!std::isfinite(value)) {
        throw std::overflow_error("non-finite value cannot be emitted as binary64");
    }
    const auto bits = std::bit_cast<std::uint64_t>(value);
    const auto negative = (bits >> 63U) != 0U;
    const auto exponent_bits = static_cast<unsigned>((bits >> 52U) & 0x7ffU);
    const auto fraction = bits & UINT64_C(0x000fffffffffffff);
    if (exponent_bits == 0U && fraction == 0U) {
        return negative ? "-0x0.0p+0" : "0x0.0p+0";
    }
    std::ostringstream output;
    output.imbue(std::locale::classic());
    if (negative) {
        output << '-';
    }
    output << (exponent_bits == 0U ? "0x0." : "0x1.")
           << std::hex << std::nouppercase << std::setfill('0')
           << std::setw(13) << fraction << std::dec << 'p';
    const auto exponent = exponent_bits == 0U
        ? -1022
        : static_cast<int>(exponent_bits) - 1023;
    if (exponent >= 0) {
        output << '+';
    }
    output << exponent;
    return output.str();
}

[[nodiscard]] std::string decimal(
    pen::ExtendedScalar value, std::size_t digits = 35U) {
    if (!std::isfinite(value.hi) || !std::isfinite(value.lo)) {
        return "NA";
    }
    return pen::canonical_decimal(value, digits);
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

[[nodiscard]] std::vector<std::string> split_header(std::string_view header) {
    std::vector<std::string> result;
    std::size_t begin = 0U;
    while (begin <= header.size()) {
        const auto comma = header.find(',', begin);
        const auto end = comma == std::string_view::npos ? header.size() : comma;
        result.emplace_back(header.substr(begin, end - begin));
        if (comma == std::string_view::npos) {
            break;
        }
        begin = comma + 1U;
    }
    return result;
}

class Csv final {
public:
    explicit Csv(std::string_view header)
        : header_(header), fields_(split_header(header)) {}

    void row(Row values) {
        if (values.size() != fields_.size()) {
            throw std::logic_error(
                "CSV row width " + std::to_string(values.size()) +
                " differs from header width " +
                std::to_string(fields_.size()));
        }
        rows_.push_back(std::move(values));
    }

    void rows(std::vector<Row> values) {
        for (auto& value : values) {
            row(std::move(value));
        }
    }

    [[nodiscard]] const std::vector<std::string>& fields() const noexcept {
        return fields_;
    }

    [[nodiscard]] const std::vector<Row>& data() const noexcept { return rows_; }
    [[nodiscard]] std::size_t size() const noexcept { return rows_.size(); }

    [[nodiscard]] std::string contents() const {
        std::string result{header_};
        result.push_back('\n');
        for (const auto& row_values : rows_) {
            for (std::size_t index = 0; index < row_values.size(); ++index) {
                if (index != 0U) {
                    result.push_back(',');
                }
                result += csv_escape(row_values[index]);
            }
            result.push_back('\n');
        }
        return result;
    }

private:
    std::string header_{};
    std::vector<std::string> fields_{};
    std::vector<Row> rows_{};
};

void write_text(const std::filesystem::path& path, std::string_view value) {
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    if (!output) {
        throw std::runtime_error("cannot open output file: " + path.string());
    }
    output.write(value.data(), static_cast<std::streamsize>(value.size()));
    if (!output) {
        throw std::runtime_error("cannot write output file: " + path.string());
    }
}

[[nodiscard]] std::string read_text(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        throw std::runtime_error("cannot read output file: " + path.string());
    }
    std::ostringstream value;
    value << input.rdbuf();
    return value.str();
}

[[nodiscard]] std::string json_escape(std::string_view value) {
    std::string result;
    for (const auto character : value) {
        switch (character) {
        case '\\':
            result += "\\\\";
            break;
        case '\"':
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
            result.push_back(character);
            break;
        }
    }
    return result;
}

[[nodiscard]] std::vector<Vec3d> analytic_grid(
    const pf::ProjectionSystem& system,
    const pen::AffineVelocityField& field) {
    std::vector<Vec3d> result;
    result.reserve(system.active_nodes().size());
    for (const auto position : system.active_node_positions_m()) {
        result.push_back(pen::evaluate(field, position));
    }
    return result;
}

[[nodiscard]] std::array<AxisMetrics, 3> binary64_metrics(
    const pf::ProjectionSystem& system,
    std::span<const Vec3d> solution,
    std::span<const Vec3d> analytic) {
    if (solution.size() != system.active_nodes().size() ||
        analytic.size() != solution.size()) {
        throw std::invalid_argument("solution metric dimensions differ");
    }
    std::array<AxisMetrics, 3> result{};
    Accurate matrix_squared{};
    for (const auto& row : system.consistent_mass_rows()) {
        for (const auto& [column, coefficient] : row) {
            static_cast<void>(column);
            const auto value = Accurate{coefficient, 0.0};
            matrix_squared += value * value;
        }
    }
    const auto matrix_norm =
        std::sqrt(std::max(0.0, accurate_value(matrix_squared)));
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        Accurate residual_squared{};
        Accurate solution_squared{};
        Accurate rhs_squared{};
        Accurate forward_squared{};
        Accurate forward_reference_squared{};
        Accurate lumped_mass_sum{};
        for (std::size_t node = 0; node < solution.size(); ++node) {
            const auto q = component(
                system.consistent_rhs_kg_m_per_s()[node], axis);
            const auto vhat = component(solution[node], axis);
            const auto expected = component(analytic[node], axis);
            const auto mass = system.lumped_mass_kg()[node];
            Accurate applied{};
            for (const auto& [column, coefficient] :
                 system.consistent_mass_rows()[node]) {
                applied += Accurate{coefficient, 0.0} * Accurate{
                    component(solution[column], axis), 0.0};
            }
            const auto residual = applied - Accurate{q, 0.0};
            const auto difference =
                Accurate{vhat, 0.0} - Accurate{expected, 0.0};
            const auto mass_value = Accurate{mass, 0.0};
            residual_squared += residual * residual;
            solution_squared +=
                Accurate{vhat, 0.0} * Accurate{vhat, 0.0};
            rhs_squared += Accurate{q, 0.0} * Accurate{q, 0.0};
            forward_squared += mass_value * difference * difference;
            forward_reference_squared += mass_value *
                Accurate{expected, 0.0} * Accurate{expected, 0.0};
            lumped_mass_sum += mass_value;
        }
        auto& metric = result[axis];
        metric.backward_l2 =
            std::sqrt(std::max(0.0, accurate_value(residual_squared)));
        metric.backward_denominator = matrix_norm *
                std::sqrt(std::max(0.0, accurate_value(solution_squared))) +
            std::sqrt(std::max(0.0, accurate_value(rhs_squared)));
        if (!(metric.backward_denominator > 0.0)) {
            throw std::logic_error("zero solve backward denominator");
        }
        metric.backward_normalized =
            metric.backward_l2 / metric.backward_denominator;
        metric.forward_numerator =
            std::sqrt(std::max(0.0, accurate_value(forward_squared)));
        metric.forward_denominator = std::max(
            std::sqrt(std::max(
                0.0, accurate_value(forward_reference_squared))),
            std::sqrt(std::max(0.0, accurate_value(lumped_mass_sum))));
        metric.forward_normalized =
            metric.forward_numerator / metric.forward_denominator;

        Accurate reconstruction_squared{};
        Accurate particle_reference_squared{};
        Accurate particle_mass_sum{};
        for (std::size_t particle = 0;
             particle < system.particles().size(); ++particle) {
            const auto mass = system.particle_mass_kg()[particle];
            const auto expected = component(
                system.particles()[particle].velocity_m_per_s, axis);
            Accurate reconstructed{};
            for (const auto& entry : system.particle_stencils()[particle]) {
                reconstructed += Accurate{entry.weight, 0.0} * Accurate{
                    component(solution[entry.node_index], axis), 0.0};
            }
            const auto difference =
                reconstructed - Accurate{expected, 0.0};
            const auto mass_value = Accurate{mass, 0.0};
            reconstruction_squared +=
                mass_value * difference * difference;
            particle_reference_squared += mass_value *
                Accurate{expected, 0.0} * Accurate{expected, 0.0};
            particle_mass_sum += mass_value;
        }
        metric.reconstruction_numerator =
            std::sqrt(std::max(
                0.0, accurate_value(reconstruction_squared)));
        metric.reconstruction_denominator = std::max(
            std::sqrt(std::max(
                0.0, accurate_value(particle_reference_squared))),
            std::sqrt(std::max(
                0.0, accurate_value(particle_mass_sum))));
        metric.reconstruction_normalized =
            metric.reconstruction_numerator /
            metric.reconstruction_denominator;
    }
    return result;
}

struct DoubleDouble final {
    double hi{0.0};
    double lo{0.0};

    DoubleDouble() = default;
    explicit DoubleDouble(double value) : hi(value) {}
    DoubleDouble(double high, double low) : hi(high), lo(low) {}
    explicit DoubleDouble(pen::ExtendedScalar value)
        : hi(value.hi), lo(value.lo) {}
};

[[nodiscard]] DoubleDouble dd_normalized(double high, double low) noexcept {
    const auto sum = high + low;
    return {sum, low - (sum - high)};
}

[[nodiscard]] DoubleDouble operator+(
    DoubleDouble lhs, DoubleDouble rhs) noexcept {
    const auto sum = lhs.hi + rhs.hi;
    const auto virtual_rhs = sum - lhs.hi;
    const auto error = (lhs.hi - (sum - virtual_rhs)) +
        (rhs.hi - virtual_rhs) + lhs.lo + rhs.lo;
    return dd_normalized(sum, error);
}

[[nodiscard]] DoubleDouble operator-(DoubleDouble value) noexcept {
    return {-value.hi, -value.lo};
}

[[nodiscard]] DoubleDouble operator-(
    DoubleDouble lhs, DoubleDouble rhs) noexcept {
    return lhs + (-rhs);
}

[[nodiscard]] DoubleDouble operator*(
    DoubleDouble lhs, DoubleDouble rhs) noexcept {
    const auto product = lhs.hi * rhs.hi;
    const auto error = std::fma(lhs.hi, rhs.hi, -product) +
        lhs.hi * rhs.lo + lhs.lo * rhs.hi + lhs.lo * rhs.lo;
    return dd_normalized(product, error);
}

[[nodiscard]] DoubleDouble operator/(
    DoubleDouble numerator, DoubleDouble denominator) noexcept {
    const auto first = numerator.hi / denominator.hi;
    auto remainder = numerator - denominator * DoubleDouble(first);
    const auto second = remainder.hi / denominator.hi;
    remainder = remainder - denominator * DoubleDouble(second);
    const auto third = remainder.hi / denominator.hi;
    return DoubleDouble(first) + DoubleDouble(second) + DoubleDouble(third);
}

DoubleDouble& operator+=(DoubleDouble& lhs, DoubleDouble rhs) noexcept {
    lhs = lhs + rhs;
    return lhs;
}

[[nodiscard]] bool dd_greater(DoubleDouble lhs, DoubleDouble rhs) noexcept {
    return lhs.hi > rhs.hi || (lhs.hi == rhs.hi && lhs.lo > rhs.lo);
}

[[nodiscard]] DoubleDouble dd_sqrt(DoubleDouble value) noexcept {
    if (value.hi == 0.0 && value.lo == 0.0) {
        return {};
    }
    auto estimate = DoubleDouble(std::sqrt(std::max(0.0, value.hi)));
    estimate = DoubleDouble(0.5) * (estimate + value / estimate);
    estimate = DoubleDouble(0.5) * (estimate + value / estimate);
    return estimate;
}

[[nodiscard]] pen::ExtendedScalar extended(DoubleDouble value) noexcept {
    return {value.hi, value.lo};
}

struct DdAxisMetrics final {
    std::array<DoubleDouble, 9> values{};
};

[[nodiscard]] std::array<DdAxisMetrics, 3> high_precision_metrics(
    const pf::ProjectionSystem& system,
    const pen::HighPrecisionSolveResult& solution,
    const pen::AffineVelocityField& field) {
    const auto node_count = system.active_nodes().size();
    if (solution.grid_velocity_extended.size() != node_count) {
        throw std::invalid_argument("high-precision solution dimensions differ");
    }
    DoubleDouble matrix_squared{};
    for (const auto& row : system.consistent_mass_rows()) {
        for (const auto& [column, coefficient] : row) {
            static_cast<void>(column);
            const auto value = DoubleDouble(coefficient);
            matrix_squared += value * value;
        }
    }
    const auto matrix_norm = dd_sqrt(matrix_squared);
    std::array<DdAxisMetrics, 3> result{};
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        DoubleDouble residual_squared{};
        DoubleDouble solution_squared{};
        DoubleDouble rhs_squared{};
        DoubleDouble forward_squared{};
        DoubleDouble forward_reference_squared{};
        DoubleDouble lumped_mass_sum{};
        for (std::size_t row = 0; row < node_count; ++row) {
            DoubleDouble applied{};
            for (const auto& [column, coefficient] :
                 system.consistent_mass_rows()[row]) {
                applied += DoubleDouble(coefficient) *
                    DoubleDouble(solution.grid_velocity_extended[column][axis]);
            }
            const auto q = DoubleDouble(component(
                system.consistent_rhs_kg_m_per_s()[row], axis));
            const auto vhat =
                DoubleDouble(solution.grid_velocity_extended[row][axis]);
            const auto expected = DoubleDouble(component(
                pen::evaluate(field, system.active_node_positions_m()[row]),
                axis));
            const auto residual = applied - q;
            const auto difference = vhat - expected;
            const auto mass = DoubleDouble(system.lumped_mass_kg()[row]);
            residual_squared += residual * residual;
            solution_squared += vhat * vhat;
            rhs_squared += q * q;
            forward_squared += mass * difference * difference;
            forward_reference_squared += mass * expected * expected;
            lumped_mass_sum += mass;
        }
        DoubleDouble reconstruction_squared{};
        DoubleDouble particle_reference_squared{};
        DoubleDouble particle_mass_sum{};
        for (std::size_t particle = 0;
             particle < system.particles().size(); ++particle) {
            DoubleDouble reconstructed{};
            for (const auto& entry : system.particle_stencils()[particle]) {
                reconstructed += DoubleDouble(entry.weight) * DoubleDouble(
                    solution.grid_velocity_extended[entry.node_index][axis]);
            }
            const auto expected = DoubleDouble(component(
                system.particles()[particle].velocity_m_per_s, axis));
            const auto difference = reconstructed - expected;
            const auto mass = DoubleDouble(system.particle_mass_kg()[particle]);
            reconstruction_squared += mass * difference * difference;
            particle_reference_squared += mass * expected * expected;
            particle_mass_sum += mass;
        }
        const auto backward_l2 = dd_sqrt(residual_squared);
        const auto backward_denominator =
            matrix_norm * dd_sqrt(solution_squared) + dd_sqrt(rhs_squared);
        const auto forward_numerator = dd_sqrt(forward_squared);
        const auto forward_denominator = dd_sqrt(
            dd_greater(lumped_mass_sum, forward_reference_squared)
                ? lumped_mass_sum
                : forward_reference_squared);
        const auto reconstruction_numerator =
            dd_sqrt(reconstruction_squared);
        const auto reconstruction_denominator = dd_sqrt(
            dd_greater(particle_mass_sum, particle_reference_squared)
                ? particle_mass_sum
                : particle_reference_squared);
        result[axis].values = {
            backward_l2,
            backward_denominator,
            backward_l2 / backward_denominator,
            forward_numerator,
            forward_denominator,
            forward_numerator / forward_denominator,
            reconstruction_numerator,
            reconstruction_denominator,
            reconstruction_numerator / reconstruction_denominator,
        };
    }
    return result;
}

[[nodiscard]] double dd_value(DoubleDouble value) noexcept {
    return value.hi + value.lo;
}

[[nodiscard]] DoubleDouble dd_max(
    DoubleDouble lhs, DoubleDouble rhs) noexcept {
    return dd_greater(lhs, rhs) ? lhs : rhs;
}

[[nodiscard]] std::string hp_status_name(pen::HighPrecisionStatus status) {
    switch (status) {
    case pen::HighPrecisionStatus::solved:
        return "solved";
    case pen::HighPrecisionStatus::empty:
        return "empty";
    case pen::HighPrecisionStatus::size_limit:
        return "size_limit";
    case pen::HighPrecisionStatus::rank_deficient:
        return "numerically_rank_deficient";
    case pen::HighPrecisionStatus::numerical_failure:
        return "numerical_failure";
    }
    return "numerical_failure";
}

[[nodiscard]] Row witness_row(
    const StageRow& stage, std::size_t axis) {
    const auto& witness = stage.witness;
    const auto& metric = witness.axis[axis];
    const auto pass = metric.mg_pass && metric.sg_pass &&
        witness.partition_pass && witness.linear_pass &&
        witness.gradient_partition_pass;
    return {
        stage.config.system_id,
        std::to_string(axis),
        hex64(metric.mg_l2),
        hex64(metric.mg_denominator),
        hex64(metric.mg_normalized),
        hex64(witness.mg_bound),
        bool_text(metric.mg_pass),
        hex64(metric.sg_l2),
        hex64(metric.sg_denominator),
        hex64(metric.sg_normalized),
        hex64(witness.sg_bound),
        bool_text(metric.sg_pass),
        hex64(witness.partition_residual),
        hex64(witness.partition_bound),
        bool_text(witness.partition_pass),
        hex64(witness.linear_residual_m),
        hex64(witness.linear_bound_m),
        bool_text(witness.linear_pass),
        hex64(witness.gradient_partition_residual_per_m),
        hex64(witness.gradient_partition_bound_per_m),
        bool_text(witness.gradient_partition_pass),
        bool_text(pass),
    };
}

[[nodiscard]] StageRow build_stage(const Configuration& config) {
    StageRow result{};
    result.config = config;
    auto state = physical_state(config);
    const auto checkpoint_before = pf::serialize_projection_checkpoint(state);
    result.checkpoint_before = checkpoint_hash(checkpoint_before);
    const auto system = pf::build_projection_system(
        state.particles, state.config);
    const auto initial = oriented_initial_field(config.field, config.orientation);
    const auto time_s =
        static_cast<double>(config.time_quanta) * time_quantum_s;
    result.field = convected_field(initial, time_s);
    result.witness = evaluate_witness(system, result.field);
    result.grid_origin_m = state.config.grid_origin_m;
    result.particle_count = system.particles().size();
    result.node_count = system.active_nodes().size();
    result.matrix_nnz =
        system.assembly_diagnostics().matrix_nonzero_count;
    result.rank_upper_bound = std::min(
        result.particle_count, result.node_count);
    const auto checkpoint_after = pf::serialize_projection_checkpoint(state);
    result.checkpoint_after = checkpoint_hash(checkpoint_after);
    result.checkpoint_read_only = checkpoint_before == checkpoint_after &&
        result.checkpoint_before == result.checkpoint_after;
    if (!result.checkpoint_read_only) {
        throw std::logic_error("diagnostic stage mutated physical checkpoint");
    }
    return result;
}

template <typename Input, typename Output, typename Function>
[[nodiscard]] std::vector<Output> parallel_map(
    const std::vector<Input>& input, std::size_t requested_jobs,
    Function function) {
    std::vector<std::optional<Output>> slots(input.size());
    std::atomic<std::size_t> next{0U};
    std::atomic<bool> stop{false};
    std::exception_ptr failure{};
    std::mutex failure_mutex{};
    const auto worker = [&] {
        while (!stop.load(std::memory_order_relaxed)) {
            const auto index = next.fetch_add(1U, std::memory_order_relaxed);
            if (index >= input.size()) {
                return;
            }
            try {
                slots[index] = function(input[index]);
            } catch (...) {
                std::scoped_lock lock{failure_mutex};
                if (failure == nullptr) {
                    failure = std::current_exception();
                }
                stop.store(true, std::memory_order_relaxed);
                return;
            }
        }
    };
    const auto jobs = std::min<std::size_t>({
        requested_jobs, std::size_t{4},
        std::max<std::size_t>(std::size_t{1}, input.size())});
    std::vector<std::thread> workers;
    workers.reserve(jobs);
    for (std::size_t index = 0; index < jobs; ++index) {
        workers.emplace_back(worker);
    }
    for (auto& thread : workers) {
        thread.join();
    }
    if (failure != nullptr) {
        std::rethrow_exception(failure);
    }
    std::vector<Output> result;
    result.reserve(input.size());
    for (auto& slot : slots) {
        if (!slot.has_value()) {
            throw std::logic_error("parallel stage omitted a registered row");
        }
        result.push_back(std::move(*slot));
    }
    return result;
}

[[nodiscard]] Row unavailable_solve_row(
    std::string_view system_id, std::size_t axis,
    std::string_view status) {
    return {
        std::string(system_id), std::to_string(axis), std::string(status),
        "pcg_control", "0",
        "NA", "NA", "NA", "NA", "NA", "NA", "NA", "NA", "NA",
        "NA", "unavailable", "NA", "unavailable", "NA",
    };
}

[[nodiscard]] std::array<Row, 3> pcg_rows(
    const pf::ProjectionSystem& system,
    const pen::AffineVelocityField& field,
    const pf::ProjectionResult& projection) {
    std::array<Row, 3> rows{};
    const auto available = projection.grid_velocity_m_per_s.size() ==
        system.active_nodes().size();
    if (!available) {
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            rows[axis] = unavailable_solve_row(
                "", axis, pf::status_name(projection.status));
        }
        return rows;
    }
    const auto analytic = analytic_grid(system, field);
    const auto metrics = binary64_metrics(
        system, projection.grid_velocity_m_per_s, analytic);
    const auto estimated = projection.diagnostics.condition_estimated;
    const auto dense = system.active_nodes().size() <= 128U;
    const auto kind = estimated
        ? (dense ? "dense_numerical_estimate" : "ritz_lanczos_estimate")
        : "unavailable";
    const auto raw = projection.diagnostics.raw_condition_estimate;
    const auto preconditioned =
        projection.diagnostics.preconditioned_condition_estimate;
    const auto raw_available = estimated && std::isfinite(raw) && raw >= 1.0;
    const auto preconditioned_available = estimated &&
        std::isfinite(preconditioned) && preconditioned >= 1.0;
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        const auto& metric = metrics[axis];
        rows[axis] = {
            "",
            std::to_string(axis),
            std::string(pf::status_name(projection.status)),
            "pcg_control",
            std::to_string(projection.diagnostics.component_iterations[axis]),
            hex64(metric.backward_l2),
            hex64(metric.backward_denominator),
            hex64(metric.backward_normalized),
            hex64(metric.forward_numerator),
            hex64(metric.forward_denominator),
            hex64(metric.forward_normalized),
            hex64(metric.reconstruction_numerator),
            hex64(metric.reconstruction_denominator),
            hex64(metric.reconstruction_normalized),
            raw_available ? hex64(raw) : "NA",
            raw_available ? kind : "unavailable",
            preconditioned_available ? hex64(preconditioned) : "NA",
            preconditioned_available ? kind : "unavailable",
            raw_available
                ? hex64(raw * metric.backward_normalized)
                : "NA",
        };
    }
    return rows;
}

[[nodiscard]] std::vector<Row> hp_rows(
    const Configuration& config,
    const pf::ProjectionSystem& system,
    const pen::AffineVelocityField& field,
    const pen::HighPrecisionSolveResult& hp,
    bool* all_pass,
    bool* contradiction) {
    constexpr std::size_t decimal_digits = 40U;
    std::vector<Row> rows;
    rows.reserve(3U);
    const auto solved = hp.status == pen::HighPrecisionStatus::solved;
    std::array<DdAxisMetrics, 3> metrics{};
    if (solved) {
        metrics = high_precision_metrics(system, hp, field);
    }
    const auto relative_threshold = pen::ExtendedScalar{
        std::ldexp(dd_safety_factor * static_cast<double>(hp.node_count), -104),
        0.0};
    const auto hp_backward_gate =
        dd_safety_factor * static_cast<double>(hp.node_count) *
        std::ldexp(1.0, -104);
    auto every_component_pass = solved && hp.threshold_rank == hp.node_count;
    auto any_contradiction = false;
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        bool component_pass = false;
        if (solved) {
            const auto normalized_backward =
                dd_value(metrics[axis].values[2]);
            const auto normalized_forward =
                dd_value(metrics[axis].values[5]);
            const auto normalized_reconstruction =
                dd_value(metrics[axis].values[8]);
            component_pass = normalized_backward <= hp_backward_gate &&
                normalized_forward <= forward_gate &&
                normalized_reconstruction <= forward_gate;
            any_contradiction = any_contradiction ||
                (normalized_backward <= hp_backward_gate &&
                 (normalized_forward > forward_gate ||
                  normalized_reconstruction > forward_gate));
        }
        every_component_pass = every_component_pass && component_pass;
        Row row{
            config.system_id,
            std::to_string(axis),
            hp_status_name(hp.status),
            "fma_double_double_complete_pivot",
            std::to_string(hp.significand_bits),
            std::to_string(decimal_digits),
            std::to_string(hp.threshold_rank),
            "dense_complete_pivot_double_double_threshold",
            "false",
            "none",
            "false",
            "false",
            "false",
            decimal(relative_threshold, decimal_digits),
            decimal(hp.smallest_accepted_absolute_pivot, decimal_digits),
            decimal(hp.largest_absolute_pivot, decimal_digits),
        };
        if (solved) {
            for (const auto value : metrics[axis].values) {
                row.push_back(decimal(extended(value), decimal_digits));
            }
            row.push_back(decimal(
                pen::ExtendedScalar{hp.pivot_ratio_estimate, 0.0},
                decimal_digits));
            row.push_back("high_precision_pivot_ratio_estimate");
        } else {
            row.insert(row.end(), 9U, "NA");
            row.push_back("NA");
            row.push_back("unavailable");
        }
        rows.push_back(std::move(row));
    }
    *all_pass = every_component_pass;
    *contradiction = any_contradiction;
    return rows;
}

struct NullMetric final {
    double mz_l2{0.0};
    double mz_denominator{0.0};
    double mz_normalized{0.0};
    double sz_l2{0.0};
    double sz_denominator{0.0};
    double sz_normalized{0.0};
    double gradient_max{0.0};
    double gradient_rms{0.0};
    double gradient_bound{0.0};
    std::optional<double> visibility_ratio{};
    bool gradient_visible{false};
    double base_residual_normalized{0.0};
    double shifted_residual_normalized{0.0};
    double reconstruction_delta_normalized{0.0};
    bool pass{false};
};

[[nodiscard]] NullMetric null_metric(
    const pf::ProjectionSystem& system,
    std::span<const double> z,
    std::span<const double> representative,
    std::span<const double> shifted,
    std::size_t component_axis,
    std::size_t max_stencil) {
    const auto node_count = system.active_nodes().size();
    if (z.size() != node_count || representative.size() != node_count ||
        shifted.size() != node_count) {
        throw std::invalid_argument("null mode dimensions differ");
    }
    DoubleDouble matrix_squared{};
    DoubleDouble sampling_squared{};
    DoubleDouble z_squared{};
    DoubleDouble mz_squared{};
    DoubleDouble sz_squared{};
    DoubleDouble q_squared{};
    DoubleDouble base_squared{};
    DoubleDouble shifted_squared{};
    DoubleDouble base_residual_squared{};
    DoubleDouble shifted_residual_squared{};
    for (const auto value : z) {
        const auto item = DoubleDouble(value);
        z_squared += item * item;
    }
    for (std::size_t row = 0; row < node_count; ++row) {
        DoubleDouble mz{};
        DoubleDouble base_applied{};
        DoubleDouble shifted_applied{};
        for (const auto& [column, coefficient] :
             system.consistent_mass_rows()[row]) {
            const auto matrix_value = DoubleDouble(coefficient);
            matrix_squared += matrix_value * matrix_value;
            mz += matrix_value * DoubleDouble(z[column]);
            base_applied += matrix_value * DoubleDouble(representative[column]);
            shifted_applied += matrix_value * DoubleDouble(shifted[column]);
        }
        const auto q = DoubleDouble(component(
            system.consistent_rhs_kg_m_per_s()[row], component_axis));
        mz_squared += mz * mz;
        q_squared += q * q;
        const auto base_value = DoubleDouble(representative[row]);
        const auto shifted_value = DoubleDouble(shifted[row]);
        base_squared += base_value * base_value;
        shifted_squared += shifted_value * shifted_value;
        const auto base_residual = base_applied - q;
        const auto shifted_residual = shifted_applied - q;
        base_residual_squared += base_residual * base_residual;
        shifted_residual_squared += shifted_residual * shifted_residual;
    }
    DoubleDouble reconstruction_delta_squared{};
    DoubleDouble gradient_squared{};
    DoubleDouble gradient_max{};
    DoubleDouble gradient_bound_max{};
    for (std::size_t particle = 0;
         particle < system.particles().size(); ++particle) {
        DoubleDouble sz{};
        DoubleDouble base_reconstructed{};
        DoubleDouble shifted_reconstructed{};
        std::array<DoubleDouble, 3> gradient{};
        DoubleDouble gradient_absolute_sum{};
        for (const auto& entry : system.particle_stencils()[particle]) {
            const auto weight = DoubleDouble(entry.weight);
            sampling_squared += weight * weight;
            sz += weight * DoubleDouble(z[entry.node_index]);
            base_reconstructed +=
                weight * DoubleDouble(representative[entry.node_index]);
            shifted_reconstructed +=
                weight * DoubleDouble(shifted[entry.node_index]);
            const auto basis = pen::evaluate_quadratic_bspline_basis(
                system.particles()[particle].position_m,
                system.active_node_positions_m()[entry.node_index],
                system.config().grid_spacing_m);
            DoubleDouble gradient_norm_squared{};
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                const auto gradient_value =
                    DoubleDouble(component(basis.gradient_m_inv, axis));
                gradient[axis] += DoubleDouble(z[entry.node_index]) *
                    gradient_value;
                gradient_norm_squared += gradient_value * gradient_value;
            }
            gradient_absolute_sum += DoubleDouble(
                std::abs(z[entry.node_index])) *
                dd_sqrt(gradient_norm_squared);
        }
        sz_squared += sz * sz;
        const auto reconstruction_delta =
            shifted_reconstructed - base_reconstructed;
        reconstruction_delta_squared +=
            reconstruction_delta * reconstruction_delta;
        const auto norm_squared = gradient[0] * gradient[0] +
            gradient[1] * gradient[1] + gradient[2] * gradient[2];
        const auto gradient_norm = dd_sqrt(norm_squared);
        gradient_squared += gradient_norm * gradient_norm;
        gradient_max = dd_max(gradient_max, gradient_norm);
        const auto particle_bound = DoubleDouble(
            128.0 * gamma_n(3U * max_stencil)) * gradient_absolute_sum;
        gradient_bound_max = dd_max(gradient_bound_max, particle_bound);
    }
    const auto matrix_norm = dd_sqrt(matrix_squared);
    const auto sampling_norm = dd_sqrt(sampling_squared);
    const auto z_norm = dd_sqrt(z_squared);
    const auto min_normal =
        DoubleDouble(std::numeric_limits<double>::min());
    const auto mz_denominator = dd_max(matrix_norm * z_norm, min_normal);
    const auto sz_denominator = dd_max(sampling_norm * z_norm, min_normal);
    const auto base_denominator =
        matrix_norm * dd_sqrt(base_squared) + dd_sqrt(q_squared);
    const auto shifted_denominator =
        matrix_norm * dd_sqrt(shifted_squared) + dd_sqrt(q_squared);
    NullMetric result{};
    result.mz_l2 = dd_value(dd_sqrt(mz_squared));
    result.mz_denominator = dd_value(mz_denominator);
    result.mz_normalized = result.mz_l2 / result.mz_denominator;
    result.sz_l2 = dd_value(dd_sqrt(sz_squared));
    result.sz_denominator = dd_value(sz_denominator);
    result.sz_normalized = result.sz_l2 / result.sz_denominator;
    result.gradient_max = dd_value(gradient_max);
    result.gradient_rms = dd_value(dd_sqrt(
        gradient_squared /
        DoubleDouble(static_cast<double>(system.particles().size()))));
    result.gradient_bound = dd_value(gradient_bound_max);
    if (result.gradient_bound > 0.0) {
        result.visibility_ratio =
            result.gradient_max / result.gradient_bound;
    }
    result.gradient_visible = result.gradient_max > std::max(
        gradient_visibility_floor_per_s,
        gradient_visibility_bound_multiplier * result.gradient_bound);
    result.base_residual_normalized =
        dd_value(dd_sqrt(base_residual_squared) / base_denominator);
    result.shifted_residual_normalized =
        dd_value(dd_sqrt(shifted_residual_squared) / shifted_denominator);
    result.reconstruction_delta_normalized = dd_value(
        dd_sqrt(reconstruction_delta_squared) / sz_denominator);
    const auto limit = null_safety_factor *
        static_cast<double>(std::max(
            system.particles().size(), system.active_nodes().size())) *
        std::numeric_limits<double>::epsilon();
    result.pass = result.mz_normalized <= limit &&
        result.sz_normalized <= limit &&
        result.reconstruction_delta_normalized <= limit;
    return result;
}

[[nodiscard]] std::string assembly_digest(const ExportRows& rows) {
    std::string payload{"MLS-PROJECTION-EXACTNESS-ASSEMBLY-v1\n"};
    const auto append_table = [&](std::string_view name,
                                  const std::vector<Row>& table) {
        for (const auto& row : table) {
            payload.append(name);
            for (const auto& value : row) {
                payload.push_back('\0');
                payload.append(value);
            }
            payload.push_back('\n');
        }
    };
    append_table("particles.csv", rows.particles);
    append_table("nodes.csv", rows.nodes);
    append_table("stencils.csv", rows.stencils);
    append_table("matrix.csv", rows.matrix);
    append_table("rhs.csv", rows.rhs);
    return sha256(payload);
}

[[nodiscard]] ExportRows build_export(
    const Configuration& config,
    const pf::ProjectionSystem& system,
    const pen::AffineVelocityField& field,
    const pf::ProjectionResult* pcg,
    const pen::HighPrecisionSolveResult* hp) {
    constexpr std::size_t hp_decimal_digits = 40U;
    ExportRows result{};
    result.particles.reserve(system.particles().size());
    for (std::size_t particle = 0;
         particle < system.particles().size(); ++particle) {
        const auto& value = system.particles()[particle];
        result.particles.push_back({
            config.system_id,
            std::to_string(particle),
            std::to_string(value.id),
            hex64(system.particle_mass_kg()[particle]),
            hex64(value.position_m.x),
            hex64(value.position_m.y),
            hex64(value.position_m.z),
            hex64(value.velocity_m_per_s.x),
            hex64(value.velocity_m_per_s.y),
            hex64(value.velocity_m_per_s.z),
        });
    }
    const auto analytic = analytic_grid(system, field);
    const auto pcg_available = pcg != nullptr &&
        pcg->grid_velocity_m_per_s.size() == system.active_nodes().size();
    const auto hp_available = hp != nullptr &&
        hp->status == pen::HighPrecisionStatus::solved &&
        hp->grid_velocity_extended.size() == system.active_nodes().size();
    result.nodes.reserve(system.active_nodes().size());
    for (std::size_t node = 0; node < system.active_nodes().size(); ++node) {
        const auto& index = system.active_nodes()[node];
        const auto position = system.active_node_positions_m()[node];
        Row row{
            config.system_id,
            std::to_string(node),
            std::to_string(index.x),
            std::to_string(index.y),
            std::to_string(index.z),
            hex64(position.x),
            hex64(position.y),
            hex64(position.z),
            hex64(analytic[node].x),
            hex64(analytic[node].y),
            hex64(analytic[node].z),
            bool_text(pcg_available),
        };
        if (pcg_available) {
            row.push_back(hex64(pcg->grid_velocity_m_per_s[node].x));
            row.push_back(hex64(pcg->grid_velocity_m_per_s[node].y));
            row.push_back(hex64(pcg->grid_velocity_m_per_s[node].z));
        } else {
            row.insert(row.end(), 3U, "NA");
        }
        row.push_back(bool_text(hp_available));
        if (hp_available) {
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                row.push_back(decimal(
                    hp->grid_velocity_extended[node][axis], hp_decimal_digits));
            }
        } else {
            row.insert(row.end(), 3U, "NA");
        }
        result.nodes.push_back(std::move(row));
    }
    std::size_t stencil_count = 0U;
    for (const auto& stencil : system.particle_stencils()) {
        stencil_count += stencil.size();
    }
    result.stencils.reserve(stencil_count);
    for (std::size_t particle = 0;
         particle < system.particle_stencils().size(); ++particle) {
        for (const auto& entry : system.particle_stencils()[particle]) {
            const auto basis = pen::evaluate_quadratic_bspline_basis(
                system.particles()[particle].position_m,
                system.active_node_positions_m()[entry.node_index],
                system.config().grid_spacing_m);
            if (!(entry.weight > 0.0)) {
                throw std::logic_error("exported stencil contains nonpositive weight");
            }
            result.stencils.push_back({
                config.system_id,
                std::to_string(particle),
                std::to_string(entry.node_index),
                hex64(entry.weight),
                hex64(basis.gradient_m_inv.x),
                hex64(basis.gradient_m_inv.y),
                hex64(basis.gradient_m_inv.z),
            });
        }
    }
    result.matrix.reserve(
        system.assembly_diagnostics().matrix_nonzero_count);
    for (std::size_t row = 0;
         row < system.consistent_mass_rows().size(); ++row) {
        for (const auto& [column, value] :
             system.consistent_mass_rows()[row]) {
            if (value == 0.0) {
                throw std::logic_error("sparse matrix contains explicit zero");
            }
            result.matrix.push_back({
                config.system_id,
                std::to_string(row),
                std::to_string(column),
                hex64(value),
            });
        }
    }
    result.rhs.reserve(3U * system.active_nodes().size());
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        for (std::size_t node = 0;
             node < system.active_nodes().size(); ++node) {
            result.rhs.push_back({
                config.system_id,
                std::to_string(node),
                std::to_string(axis),
                hex64(component(
                    system.consistent_rhs_kg_m_per_s()[node], axis)),
            });
        }
    }
    result.digest = assembly_digest(result);
    return result;
}

[[nodiscard]] std::vector<Row> stopped_hp_rows(
    const Configuration& config, std::size_t node_count) {
    std::vector<Row> result;
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        result.push_back({
            config.system_id, std::to_string(axis), "numerical_failure",
            "fma_double_double_complete_pivot", "106", "40", "0",
            "dense_complete_pivot_double_double_threshold", "false", "none",
            "false", "false", "false",
            decimal({
                std::ldexp(dd_safety_factor * static_cast<double>(node_count),
                           -104),
                0.0}, 40U),
            "NA", "NA", "NA", "NA", "NA", "NA", "NA", "NA", "NA",
            "NA", "NA", "NA", "unavailable",
        });
    }
    return result;
}

[[nodiscard]] NumericRow run_numeric(
    const StageRow& stage, bool solvers_allowed) {
    NumericRow result{};
    const auto state = physical_state(stage.config);
    const auto checkpoint = pf::serialize_projection_checkpoint(state);
    if (checkpoint_hash(checkpoint) != stage.checkpoint_before) {
        throw std::logic_error("numeric rebuild changed authoritative checkpoint");
    }
    const auto system = pf::build_projection_system(
        state.particles, state.config);
    if (system.particles().size() != stage.particle_count ||
        system.active_nodes().size() != stage.node_count ||
        system.assembly_diagnostics().matrix_nonzero_count != stage.matrix_nnz) {
        throw std::logic_error("numeric rebuild changed assembly dimensions");
    }
    const auto rebuilt_witness = evaluate_witness(system, stage.field);
    if (rebuilt_witness.pass != stage.witness.pass ||
        rebuilt_witness.max_stencil != stage.witness.max_stencil ||
        rebuilt_witness.max_contributions != stage.witness.max_contributions ||
        rebuilt_witness.max_matrix_row_nnz !=
            stage.witness.max_matrix_row_nnz) {
        throw std::logic_error("numeric rebuild changed witness outcome");
    }

    std::optional<pf::ProjectionResult> pcg{};
    std::optional<pen::HighPrecisionSolveResult> hp{};
    if (solvers_allowed) {
        pcg = pen::run_legacy_pcg_control(system);
        result.solve_rows = pcg_rows(system, stage.field, *pcg);
        for (auto& row : result.solve_rows) {
            row[0] = stage.config.system_id;
        }
        if (stage.config.high_precision &&
            pcg->grid_velocity_m_per_s.size() == system.active_nodes().size()) {
            const auto metrics = binary64_metrics(
                system, pcg->grid_velocity_m_per_s,
                analytic_grid(system, stage.field));
            for (const auto& metric : metrics) {
                result.pcg_miss = result.pcg_miss ||
                    metric.forward_normalized > forward_gate ||
                    metric.reconstruction_normalized > forward_gate;
            }
        }
        if (stage.config.high_precision) {
            hp = pen::solve_affine_high_precision(system, stage.field);
            result.high_precision_rows = hp_rows(
                stage.config, system, stage.field, *hp,
                &result.hp_full_rank_all_pass, &result.hp_contradiction);
            result.hp_ambiguous =
                hp->status != pen::HighPrecisionStatus::solved ||
                hp->threshold_rank != hp->node_count;
        }
        if (stage.config.nullspace) {
            const auto representative_grid = analytic_grid(system, stage.field);
            const auto nullspace = pen::diagnose_gram_nullspace(
                system, representative_grid);
            result.null_ambiguous =
                nullspace.status != pen::NullspaceStatus::analyzed ||
                nullspace.modes.empty();
            result.all_constructed_null_modes_accepted =
                nullspace.status == pen::NullspaceStatus::analyzed &&
                !nullspace.modes.empty();
            if (nullspace.status == pen::NullspaceStatus::analyzed) {
                std::vector<double> representative(system.active_nodes().size());
                for (std::size_t node = 0; node < representative.size(); ++node) {
                    representative[node] = representative_grid[node].x;
                }
                for (const auto& mode : nullspace.modes) {
                    std::vector<double> shifted(representative.size());
                    for (std::size_t node = 0; node < shifted.size(); ++node) {
                        shifted[node] = representative[node] +
                            mode.nodal_mode[node];
                        result.nullspace_mode_rows.push_back({
                            stage.config.system_id,
                            std::to_string(mode.mode_index),
                            std::to_string(node),
                            hex64(mode.nodal_mode[node]),
                            "householder_cpqr_sqrt_w_s",
                            "NA",
                            hex64(representative[node]),
                            hex64(shifted[node]),
                        });
                    }
                    const auto metric = null_metric(
                        system, mode.nodal_mode, representative, shifted, 0U,
                        stage.witness.max_stencil);
                    result.nullspace_metric_rows.push_back({
                        stage.config.system_id,
                        std::to_string(mode.mode_index),
                        std::to_string(nullspace.threshold_rank),
                        "householder_cpqr_sqrt_w_s",
                        "false",
                        hex64(metric.mz_l2),
                        hex64(metric.mz_denominator),
                        hex64(metric.mz_normalized),
                        hex64(metric.sz_l2),
                        hex64(metric.sz_denominator),
                        hex64(metric.sz_normalized),
                        hex64(metric.gradient_max),
                        hex64(metric.gradient_rms),
                        hex64(metric.gradient_bound),
                        metric.visibility_ratio.has_value()
                            ? hex64(*metric.visibility_ratio)
                            : "inf",
                        bool_text(metric.gradient_visible),
                        hex64(1.0),
                        "0",
                        "analytic_affine",
                        hex64(metric.base_residual_normalized),
                        hex64(metric.shifted_residual_normalized),
                        hex64(metric.reconstruction_delta_normalized),
                        stage.config.phase.name,
                        stage.config.orientation.name,
                        "false",
                        bool_text(metric.pass),
                    });
                    result.accepted_null_mode =
                        result.accepted_null_mode || metric.pass;
                    result.accepted_gradient_visible =
                        result.accepted_gradient_visible ||
                        (metric.pass && metric.gradient_visible);
                    result.all_constructed_null_modes_accepted =
                        result.all_constructed_null_modes_accepted &&
                        metric.pass;
                    result.null_ambiguous =
                        result.null_ambiguous || !metric.pass;
                }
            }
        }
    } else {
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            result.solve_rows[axis] = unavailable_solve_row(
                stage.config.system_id, axis, "numerical_failure");
        }
        if (stage.config.high_precision) {
            result.high_precision_rows = stopped_hp_rows(
                stage.config, stage.node_count);
            result.hp_ambiguous = true;
        }
        if (stage.config.nullspace) {
            result.null_ambiguous = true;
        }
    }
    if (stage.config.assembly_exported) {
        result.exported = build_export(
            stage.config, system, stage.field,
            pcg.has_value() ? &*pcg : nullptr,
            hp.has_value() ? &*hp : nullptr);
    }
    return result;
}

[[nodiscard]] Row system_row(
    const StageRow& stage, const NumericRow& numeric) {
    Row row{
        stage.config.system_id,
        stage.config.case_class,
        field_name(stage.config.field),
        stage.config.phase.name,
        stage.config.orientation.name,
        std::to_string(stage.config.level),
        std::to_string(stage.config.time_quanta),
        std::to_string(time_quantum_numerator_s),
        std::to_string(time_quantum_denominator_s),
        hex64(static_cast<double>(stage.config.time_quanta) * time_quantum_s),
        hex64(stage.config.h_m),
        hex64(stage.config.particle_spacing_m),
        hex64(kg_per_mass_quantum),
        std::to_string(expected_mass_quanta),
        hex64(stage.grid_origin_m.x),
        hex64(stage.grid_origin_m.y),
        hex64(stage.grid_origin_m.z),
        std::to_string(stage.particle_count),
        std::to_string(stage.node_count),
        std::to_string(stage.matrix_nnz),
        std::to_string(stage.rank_upper_bound),
        std::to_string(stage.witness.max_stencil),
        std::to_string(stage.witness.max_contributions),
        std::to_string(stage.witness.max_matrix_row_nnz),
    };
    for (const auto& matrix_row : stage.field.gradient_per_s.value) {
        for (const auto value : matrix_row) {
            row.push_back(hex64(value));
        }
    }
    row.push_back(hex64(stage.field.intercept_m_per_s.x));
    row.push_back(hex64(stage.field.intercept_m_per_s.y));
    row.push_back(hex64(stage.field.intercept_m_per_s.z));
    row.push_back("true");
    row.push_back(bool_text(stage.config.high_precision));
    row.push_back(bool_text(stage.config.nullspace));
    row.push_back(bool_text(stage.config.assembly_exported));
    row.push_back(stage.config.assembly_exported ? numeric.exported.digest : "NA");
    row.push_back(stage.checkpoint_before);
    row.push_back(stage.checkpoint_after);
    row.push_back(bool_text(stage.checkpoint_read_only));
    return row;
}

struct SummaryState final {
    bool witness_all{false};
    bool hp_all{false};
    bool pcg_miss{false};
    bool contradiction{false};
    bool null_ambiguous{false};
    bool accepted_mode{false};
    bool visible_mode{false};
    std::string decision{};
};

[[nodiscard]] SummaryState summarize(
    std::span<const StageRow> stages,
    std::span<const NumericRow> numeric) {
    if (stages.size() != numeric.size()) {
        throw std::logic_error("summary stage dimensions differ");
    }
    SummaryState result{};
    result.witness_all = std::all_of(
        stages.begin(), stages.end(),
        [](const StageRow& stage) { return stage.witness.pass; });
    result.hp_all = true;
    for (std::size_t index = 0; index < stages.size(); ++index) {
        if (stages[index].config.high_precision) {
            result.hp_all = result.hp_all &&
                numeric[index].hp_full_rank_all_pass;
            result.contradiction = result.contradiction ||
                numeric[index].hp_contradiction;
        }
        if (stages[index].config.nullspace) {
            result.null_ambiguous = result.null_ambiguous ||
                numeric[index].null_ambiguous ||
                !numeric[index].accepted_null_mode;
            result.accepted_mode = result.accepted_mode ||
                numeric[index].accepted_null_mode;
            result.visible_mode = result.visible_mode ||
                numeric[index].accepted_gradient_visible;
        }
        result.pcg_miss = result.pcg_miss || numeric[index].pcg_miss;
    }
    if (!result.witness_all) {
        result.decision = "stop_assembly_or_basis_inconsistency";
    } else if (result.contradiction) {
        result.decision = "stop_contradiction_or_implementation_defect";
    } else if (result.visible_mode) {
        result.decision =
            "stop_center_state_gradient_nullspace_blocker";
    } else if (result.null_ambiguous || !result.hp_all) {
        result.decision = "stop_inconclusive_rank_or_solver_diagnosis";
    } else {
        result.decision =
            "stop_retain_quotient_or_gauge_for_future_lab";
    }
    return result;
}

[[nodiscard]] std::string summary_json(
    bool smoke,
    const std::vector<StageRow>& stages,
    const SummaryState& state,
    const std::map<std::string, std::size_t>& row_counts) {
    std::vector<std::string> findings;
    if (state.hp_all && state.pcg_miss) {
        findings.emplace_back(
            "prior_affine_failure_is_solver_or_conditioning");
    }
    if (state.contradiction) {
        findings.emplace_back(
            "high_precision_forward_contradiction_or_implementation_defect");
    }
    if (state.accepted_mode) {
        findings.emplace_back("center_invisible_numerical_null_modes");
    }
    if (state.visible_mode) {
        findings.emplace_back("center_invisible_gradient_visible_modes");
    }
    std::ostringstream output;
    output.imbue(std::locale::classic());
    output << "{\n"
           << "  \"analytic_witness_all_pass\": "
           << bool_text(state.witness_all) << ",\n"
           << "  \"authoritative_input_sha256\": {\n"
           << "    \"contract\": \"4cbd68a597c15a015ee545293608f7887c387df5c31c87b5fd42e49699348224\",\n"
           << "    \"independent_oracle_canonical_sha256\": \"3e8565277a5b0cfad5497950fe30f59f86616034e6e90535d7adaf1ec2029a42\",\n"
           << "    \"preregistration\": \"ce7771b75fdf6c076d6ef42cae57d497fc32ae8e0e73f0b5bf9dfa7162969d32\"\n"
           << "  },\n"
           << "  \"branch\": \"projection-exactness-nullspace-lab\",\n"
           << "  \"compiler_id\": \""
           << json_escape(MLS_CONFIGURED_COMPILER_ID) << "\",\n"
           << "  \"compiler_version\": \""
           << json_escape(MLS_CONFIGURED_COMPILER_VERSION) << "\",\n"
           << "  \"configured_source_branch\": \""
           << json_escape(MLS_CONFIGURED_SOURCE_BRANCH) << "\",\n"
           << "  \"decision\": \"" << json_escape(state.decision)
           << "\",\n"
           << "  \"diagnostic_pseudoinverse_promotion_eligible\": false,\n"
           << "  \"high_precision_all_pass\": "
           << bool_text(state.hp_all) << ",\n"
           << "  \"mode\": \"" << (smoke ? "smoke" : "full")
           << "\",\n"
           << "  \"parent_sha\": \"" << accepted_parent_sha << "\",\n"
           << "  \"pcg_miss_observed\": " << bool_text(state.pcg_miss)
           << ",\n"
           << "  \"producer\": \"cpp_projection_exactness_nullspace_lab\",\n"
           << "  \"promotion\": false,\n"
           << "  \"provisional\": " << bool_text(smoke) << ",\n"
           << "  \"registered_system_ids\": [\n";
    for (std::size_t index = 0; index < stages.size(); ++index) {
        output << "    \"" << json_escape(stages[index].config.system_id)
               << "\"" << (index + 1U == stages.size() ? "\n" : ",\n");
    }
    output << "  ],\n"
           << "  \"row_counts\": {\n";
    std::size_t count_index = 0U;
    for (const auto& [name, count] : row_counts) {
        output << "    \"" << json_escape(name) << "\": " << count
               << (++count_index == row_counts.size() ? "\n" : ",\n");
    }
    output << "  },\n"
           << "  \"schema\": \"" << summary_schema << "\",\n"
           << "  \"seed\": " << seed << ",\n"
           << "  \"singular_center_invariant\": "
           << bool_text(state.accepted_mode && !state.null_ambiguous) << ",\n"
           << "  \"singular_gradient_visible\": "
           << bool_text(state.visible_mode) << ",\n"
           << "  \"source_dirty\": " << MLS_CONFIGURED_SOURCE_DIRTY
           << ",\n"
           << "  \"source_sha\": \""
           << json_escape(MLS_CONFIGURED_SOURCE_SHA) << "\",\n"
           << "  \"supported_findings\": [";
    if (!findings.empty()) {
        output << '\n';
        for (std::size_t index = 0; index < findings.size(); ++index) {
            output << "    \"" << json_escape(findings[index]) << "\""
                   << (index + 1U == findings.size() ? "\n" : ",\n");
        }
        output << "  ";
    }
    output << "],\n"
           << "  \"sweep_complete\": "
           << bool_text(!smoke && stages.size() == 76U) << ",\n"
           << "  \"tolerances\": {\n"
           << "    \"gradient_absolute_floor_per_s\": \"1e-10\",\n"
           << "    \"gradient_visible_bound_multiplier\": \"1e4\",\n"
           << "    \"high_precision_normalized_backward_formula\": \"2^12*n*2^-104\",\n"
           << "    \"high_precision_normalized_forward\": \"5e-10\",\n"
           << "    \"high_precision_normalized_reconstruction\": \"5e-10\",\n"
           << "    \"null_normalized_formula\": \"512*max(P,N)*2^-52\"\n"
           << "  },\n"
           << "  \"tool_language\": \"C++20\"\n"
           << "}\n";
    return output.str();
}

void write_manifest(
    const std::filesystem::path& output_directory,
    const std::vector<std::string>& filenames) {
    std::map<std::string, std::string> hashes;
    for (const auto& filename : filenames) {
        hashes.emplace(
            filename, sha256(read_text(output_directory / filename)));
    }
    std::ostringstream preimage;
    preimage << "{\n"
             << "  \"algorithm\": \"SHA-256\",\n"
             << "  \"files\": {\n";
    std::size_t index = 0U;
    for (const auto& [filename, hash] : hashes) {
        preimage << "    \"" << json_escape(filename) << "\": \""
                 << hash << "\""
                 << (++index == hashes.size() ? "\n" : ",\n");
    }
    preimage << "  },\n"
             << "  \"schema\": \"" << manifest_schema << "\"\n"
             << "}";
    const auto pre_hash = sha256(preimage.str());
    std::ostringstream output;
    output << "{\n"
           << "  \"algorithm\": \"SHA-256\",\n"
           << "  \"files\": {\n";
    index = 0U;
    for (const auto& [filename, hash] : hashes) {
        output << "    \"" << json_escape(filename) << "\": \""
               << hash << "\""
               << (++index == hashes.size() ? "\n" : ",\n");
    }
    output << "  },\n"
           << "  \"pre_hash_sha256\": \"" << pre_hash << "\",\n"
           << "  \"schema\": \"" << manifest_schema << "\"\n"
           << "}\n";
    write_text(output_directory / "manifest.json", output.str());
}

[[nodiscard]] Options parse_options(int argc, char** argv) {
    Options result{};
    for (int index = 1; index < argc; ++index) {
        const std::string_view argument{argv[index]};
        if (argument == "--smoke") {
            result.smoke = true;
        } else if (argument == "--schema-audit") {
            result.schema_audit = true;
        } else if (argument == "--jobs") {
            if (index + 1 >= argc) {
                throw std::invalid_argument("--jobs requires a positive integer");
            }
            const std::string value{argv[++index]};
            std::size_t parsed = 0U;
            const auto jobs = std::stoull(value, &parsed, 10);
            if (parsed != value.size() || jobs == 0U || jobs > 64U) {
                throw std::invalid_argument("--jobs must be in [1,64]");
            }
            result.jobs = static_cast<std::size_t>(jobs);
        } else if (argument == "--output") {
            if (index + 1 >= argc) {
                throw std::invalid_argument("--output requires a directory");
            }
            result.output = argv[++index];
        } else if (argument == "--help") {
            std::cout
                << "Usage: mls_projection_exactness_nullspace_diagnostic "
                   "[--smoke] [--schema-audit] [--jobs N] "
                   "[--output DIRECTORY]\n";
            std::exit(EXIT_SUCCESS);
        } else {
            throw std::invalid_argument(
                "unknown argument: " + std::string(argument));
        }
    }
    return result;
}

[[nodiscard]] int run_schema_audit() {
    const auto configs = full_configurations();
    const auto count_if = [&](auto predicate) {
        return static_cast<std::size_t>(std::count_if(
            configs.begin(), configs.end(), predicate));
    };
    if (configs.size() != 76U ||
        count_if([](const Configuration& value) {
            return value.case_class == "main";
        }) != 72U ||
        count_if([](const Configuration& value) {
            return value.case_class == "full_rank_micro";
        }) != 2U ||
        count_if([](const Configuration& value) {
            return value.case_class == "singular_ppc1";
        }) != 2U ||
        count_if([](const Configuration& value) {
            return value.high_precision;
        }) != 4U ||
        count_if([](const Configuration& value) {
            return value.nullspace;
        }) != 10U ||
        count_if([](const Configuration& value) {
            return value.assembly_exported;
        }) != 14U) {
        throw std::logic_error("frozen 76/4/10/14 selection audit failed");
    }
    std::set<std::string> ids;
    for (const auto& config : configs) {
        if (!ids.insert(config.system_id).second) {
            throw std::logic_error("duplicate registered system ID");
        }
    }
    const std::array<std::string_view, 11> headers{
        system_header, particle_header, node_header, stencil_header,
        matrix_header, rhs_header, witness_header, solve_header,
        high_precision_header, nullspace_mode_header,
        nullspace_metric_header};
    const std::array<std::size_t, 11> widths{
        44U, 10U, 19U, 7U, 4U, 4U, 22U, 19U, 27U, 8U, 26U};
    for (std::size_t index = 0; index < headers.size(); ++index) {
        if (split_header(headers[index]).size() != widths[index]) {
            throw std::logic_error("CSV header width audit failed");
        }
    }
    std::cout << "Projection Exactness + Nullspace schema audit: PASS "
                 "(76 systems, HP4, null10, exported14; frozen CSV widths)\n";
    return EXIT_SUCCESS;
}

[[nodiscard]] int run(const Options& options) {
    if (options.schema_audit) {
        return run_schema_audit();
    }
    const auto configs = configurations(options.smoke);
    const auto stages = parallel_map<Configuration, StageRow>(
        configs, options.jobs,
        [](const Configuration& config) { return build_stage(config); });
    const auto witness_all = std::all_of(
        stages.begin(), stages.end(),
        [](const StageRow& stage) { return stage.witness.pass; });
    const auto numeric = parallel_map<StageRow, NumericRow>(
        stages, options.jobs,
        [&](const StageRow& stage) {
            return run_numeric(stage, witness_all);
        });

    Csv systems(system_header);
    Csv particles(particle_header);
    Csv nodes(node_header);
    Csv stencils(stencil_header);
    Csv matrix(matrix_header);
    Csv rhs(rhs_header);
    Csv witness(witness_header);
    Csv solve(solve_header);
    Csv high_precision(high_precision_header);
    Csv nullspace_modes(nullspace_mode_header);
    Csv nullspace_metrics(nullspace_metric_header);
    for (std::size_t index = 0; index < stages.size(); ++index) {
        systems.row(system_row(stages[index], numeric[index]));
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            witness.row(witness_row(stages[index], axis));
            solve.row(numeric[index].solve_rows[axis]);
        }
        high_precision.rows(numeric[index].high_precision_rows);
        nullspace_modes.rows(numeric[index].nullspace_mode_rows);
        nullspace_metrics.rows(numeric[index].nullspace_metric_rows);
        if (stages[index].config.assembly_exported) {
            particles.rows(numeric[index].exported.particles);
            nodes.rows(numeric[index].exported.nodes);
            stencils.rows(numeric[index].exported.stencils);
            matrix.rows(numeric[index].exported.matrix);
            rhs.rows(numeric[index].exported.rhs);
        }
    }

    if (witness.size() != 3U * stages.size() ||
        solve.size() != 3U * stages.size()) {
        throw std::logic_error("witness/solve component coverage is incomplete");
    }
    const auto hp_selection = static_cast<std::size_t>(std::count_if(
        stages.begin(), stages.end(),
        [](const StageRow& stage) { return stage.config.high_precision; }));
    if (high_precision.size() != 3U * hp_selection) {
        throw std::logic_error("high-precision component coverage is incomplete");
    }
    if (witness_all) {
        const auto null_selection = static_cast<std::size_t>(std::count_if(
            stages.begin(), stages.end(),
            [](const StageRow& stage) { return stage.config.nullspace; }));
        const auto diagnosed = static_cast<std::size_t>(std::count_if(
            numeric.begin(), numeric.end(),
            [](const NumericRow& row) {
                return !row.nullspace_metric_rows.empty();
            }));
        if (diagnosed != null_selection) {
            throw std::logic_error("selected nullspace diagnosis is incomplete");
        }
    }

    std::map<std::string, std::size_t> row_counts{
        {"high_precision.csv", high_precision.size()},
        {"matrix.csv", matrix.size()},
        {"nodes.csv", nodes.size()},
        {"nullspace_metrics.csv", nullspace_metrics.size()},
        {"nullspace_modes.csv", nullspace_modes.size()},
        {"particles.csv", particles.size()},
        {"rhs.csv", rhs.size()},
        {"solve_diagnostics.csv", solve.size()},
        {"stencils.csv", stencils.size()},
        {"systems.csv", systems.size()},
        {"witness.csv", witness.size()},
    };
    const auto summary_state = summarize(stages, numeric);
    std::filesystem::create_directories(options.output);
    const std::array<std::pair<std::string_view, const Csv*>, 11> tables{
        std::pair{"systems.csv", &systems},
        std::pair{"particles.csv", &particles},
        std::pair{"nodes.csv", &nodes},
        std::pair{"stencils.csv", &stencils},
        std::pair{"matrix.csv", &matrix},
        std::pair{"rhs.csv", &rhs},
        std::pair{"witness.csv", &witness},
        std::pair{"solve_diagnostics.csv", &solve},
        std::pair{"high_precision.csv", &high_precision},
        std::pair{"nullspace_modes.csv", &nullspace_modes},
        std::pair{"nullspace_metrics.csv", &nullspace_metrics},
    };
    std::vector<std::string> manifest_files;
    manifest_files.reserve(12U);
    for (const auto& [name, table] : tables) {
        write_text(options.output / name, table->contents());
        manifest_files.emplace_back(name);
    }
    write_text(
        options.output / "summary.json",
        summary_json(options.smoke, stages, summary_state, row_counts));
    manifest_files.emplace_back("summary.json");
    write_manifest(options.output, manifest_files);
    std::cout << "Projection Exactness + Nullspace "
              << (options.smoke ? "provisional smoke" : "full")
              << " evidence written to " << options.output.string()
              << " (decision=" << summary_state.decision << ")\n";
    return EXIT_SUCCESS;
}

} // namespace

int main(int argc, char** argv) {
    try {
        return run(parse_options(argc, argv));
    } catch (const std::exception& error) {
        std::cerr << "mls_projection_exactness_nullspace_diagnostic: "
                  << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
