#include "mls/mechanical_observability_lab.hpp"
#include "mls/projection_exactness_nullspace_lab.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <locale>
#include <map>
#include <numeric>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

#ifndef MLS_CONFIGURED_SOURCE_SHA
#define MLS_CONFIGURED_SOURCE_SHA "0000000000000000000000000000000000000000"
#endif
#ifndef MLS_CONFIGURED_SOURCE_DIRTY
#define MLS_CONFIGURED_SOURCE_DIRTY "true"
#endif

namespace {

namespace mo = mls::experimental::mechanical_observability;
namespace pen = mls::experimental::projection_exactness_nullspace;
namespace pf = mls::experimental::projection_foundation;
using mls::experimental::GridIndex;
using mls::experimental::Matrix3d;
using mls::experimental::TransferConfig;
using mls::experimental::Vec3d;

using Row = std::vector<std::string>;

constexpr std::uint64_t seed = 260828U;
constexpr double nominal_spacing_m = 0.25;
constexpr double kg_per_mass_quantum = 1.0 / 4096.0;
constexpr std::int64_t packet_mass_quanta = 4096;
constexpr double epsilon64 = std::numeric_limits<double>::epsilon();
constexpr double minimum_normal64 = std::numeric_limits<double>::min();
constexpr std::string_view summary_schema =
    "mls.mechanical-observability.summary.v2";
constexpr std::string_view manifest_schema =
    "mls.mechanical-observability.manifest.v1";
constexpr std::string_view accepted_parent_sha =
    "2e175396ff30faea8a4d96d5a0336ab9ba042f12";
constexpr std::string_view frozen_branch = "mechanical-observability-lab";

enum class RunMode {
    full,
    smoke,
    failure_fixture,
};

enum class CandidateAFailureFixture {
    none,
    sampling,
    derivative,
};

[[nodiscard]] constexpr std::string_view run_mode_name(
    RunMode mode) noexcept {
    switch (mode) {
    case RunMode::full:
        return "full";
    case RunMode::smoke:
        return "smoke";
    case RunMode::failure_fixture:
        return "failure_fixture";
    }
    return "invalid";
}

[[nodiscard]] constexpr bool valid_option_shape(
    bool smoke, bool failure_fixture, bool schema, bool logic,
    bool output) noexcept {
    const int action_count = static_cast<int>(schema) +
        static_cast<int>(logic) + static_cast<int>(output);
    return action_count == 1 &&
        !(smoke && failure_fixture) &&
        !((smoke || failure_fixture) && !output);
}

constexpr std::string_view configurations_header =
    "configuration_id,base_configuration_id,family,variant,profile,transform,"
    "lookup_phase,packet_count,nominal_spacing_m,support_radius_m,geometry_scale,"
    "affine_span_rank,connected,edge_count,edge_lower_bound,"
    "min_incident_direction_rank,rigid_generator_rank,generic_solid_gate,"
    "intentionally_flexible,decision_driving,packet_payload_sha256,"
    "neighbor_payload_sha256,relation_payload_sha256,"
    "input_checkpoint_sha256_before,input_checkpoint_sha256_after,"
    "diagnostics_read_only_exact";
constexpr std::string_view packets_header =
    "configuration_id,packet_index,packet_id,mass_quanta,x_m,y_m,z_m,"
    "vx_m_per_s,vy_m_per_s,vz_m_per_s,jitter_dx_m,jitter_dy_m,jitter_dz_m";
constexpr std::string_view neighbor_pairs_header =
    "configuration_id,lookup_phase,low_packet_id,high_packet_id,"
    "distance_squared_m2,support_radius_squared_m2,brute_force_eligible,"
    "lookup_eligible,agreement,weight";
constexpr std::string_view grid_nodes_header =
    "sampling_operator_id,derivative_operator_id,configuration_id,"
    "lookup_phase,node_index,node_id,grid_i,grid_j,grid_k,x_m,y_m,z_m";
constexpr std::string_view checkpoints_header =
    "configuration_id,checkpoint_kind,encoding,byte_count,payload_sha256,"
    "payload_hex";
constexpr std::string_view permutation_controls_header =
    "control_id,operator_id,configuration_id,permutation_kind,"
    "permutation_seed,packet_order,relation_order,row_count,column_count,"
    "entry_count,raw_payload_sha256,raw_dense_payload_sha256,"
    "canonical_payload_sha256,baseline_payload_sha256,"
    "canonical_bytes_match,promotion_eligible";
constexpr std::string_view permutation_entries_header =
    "control_id,operator_id,row_index,column_index,domain_kind,domain_id,"
    "velocity_component,row_kind,row_owner_id,row_component,value,units";
constexpr std::string_view relations_header =
    "configuration_id,relation_index,relation_id,relation_kind,center_id,"
    "first_id,second_id,third_id,selection_status,selection_source,"
    "reference_value,reference_units,selection_score_m4";
constexpr std::string_view operator_status_header =
    "operator_id,configuration_id,candidate,operator_role,observable_kind,"
    "build_status,packet_count,relation_count,row_count,column_count,"
    "raw_exported,operator_payload_sha256,row_normalization_complete,"
    "first_invalid_row,rank_applicable,b_rank_eligible,generic_solid_gate,"
    "decision_driving,promotion_eligible,failure_stage,failure_reason,"
    "failure_witness_row,failure_witness_column,failure_witness_value,"
    "failure_witness_ieee754_bits,failure_witness_class";
constexpr std::string_view operator_entries_header =
    "operator_id,row_index,column_index,domain_kind,domain_id,"
    "velocity_component,row_kind,row_owner_id,row_component,value,units";
constexpr std::string_view moment_diagnostics_header =
    "operator_id,packet_id,neighbor_count,m00_m2,m01_m2,m02_m2,m10_m2,"
    "m11_m2,m12_m2,m20_m2,m21_m2,m22_m2,symmetry_residual,"
    "smallest_eigenvalue_m2,largest_eigenvalue_m2,condition_number,"
    "condition_kind,inverse_residual_normalized,inverse_residual_tolerance,"
    "status,inverse_emitted";
constexpr std::string_view affine_objectivity_header =
    "operator_id,test_id,test_kind,field,packet_id,relation_id,component,"
    "measured_value,target_value,absolute_error,normalization_scale,"
    "normalized_error,operation_count,roundoff_bound,pass,units";
constexpr std::string_view invariance_header =
    "comparison_id,base_operator_id,transformed_operator_id,transform_kind,"
    "scale,lookup_phase,topology_match,relation_ids_match,rank_match,"
    "nullity_match,base_build_status,transformed_build_status,"
    "build_status_match,metrics_available,normalized_residual_delta,"
    "max_scaled_singular_value_delta,tolerance,canonical_bytes_match,pass";
constexpr std::string_view rigid_basis_header =
    "operator_id,basis_kind,mode_index,dof_index,domain_kind,domain_id,"
    "velocity_component,value";
constexpr std::string_view rank_status_header =
    "operator_id,record_kind,pivot_step,permuted_column_index,"
    "diagonal_magnitude,accepted_pivot,status,row_count,column_count,rank,"
    "nullity,rigid_rank,nonrigid_nullity,threshold,ambiguity_lower,"
    "ambiguity_upper,rank_ambiguous,rank_method,rank_is_certified,"
    "basis_complete,rigid_in_kernel,kernel_equals_rigid_subspace,"
    "normalized_rigid_residual,normalized_null_residual,"
    "normalized_nonrigid_residual,rigid_orthogonality_residual,"
    "residual_tolerance,generic_observability_pass,promotion_eligible,"
    "failure_stage,failure_reason";
constexpr std::string_view nullspace_modes_header =
    "operator_id,basis_kind,mode_index,dof_index,domain_kind,domain_id,"
    "velocity_component,value";
constexpr std::string_view nullspace_metrics_header =
    "operator_id,basis_kind,mode_index,operator_image_l2,operator_denominator,"
    "normalized_operator_residual,rigid_projection_l2,"
    "rigid_orthogonality_residual,roundoff_bound,pass,promotion_eligible";
constexpr std::string_view grid_gauge_header =
    "operator_id,sampling_operator_id,derivative_operator_id,mode_index,"
    "representative_component,sampling_residual_normalized,"
    "derivative_max_per_s,derivative_rms_per_s,"
    "derivative_roundoff_bound_per_s,visibility_ratio,gradient_visible,"
    "accepted,pass,promotion_eligible";
constexpr std::string_view exact_reference_header =
    "reference_id,configuration_id,candidate,operator_id,arithmetic,"
    "precision_digits,row_count,column_count,rank,nullity,rigid_rank,"
    "nonrigid_nullity,rigid_in_kernel,kernel_equals_rigid_span,source,pass,"
    "promotion_eligible";

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

[[nodiscard]] std::string csv_escape(std::string_view value) {
    if (value.find_first_of(",\"\r\n") == std::string_view::npos) {
        return std::string(value);
    }
    std::string result{"\""};
    for (const char character : value) {
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
    explicit Csv(std::string_view header)
        : header_(header), fields_(split_header(header)) {}

    void row(Row values) {
        if (values.size() != fields_.size()) {
            throw std::logic_error(
                "CSV row width differs from frozen header width");
        }
        rows_.push_back(std::move(values));
    }

    template <class Compare>
    void sort_rows(Compare compare) {
        std::stable_sort(rows_.begin(), rows_.end(), std::move(compare));
    }

    [[nodiscard]] const std::vector<std::string>& fields() const noexcept {
        return fields_;
    }
    [[nodiscard]] const std::vector<Row>& rows() const noexcept { return rows_; }
    [[nodiscard]] std::size_t size() const noexcept { return rows_.size(); }

    [[nodiscard]] std::string contents() const {
        std::string result{header_};
        result.push_back('\n');
        for (const auto& values : rows_) {
            for (std::size_t index = 0U; index < values.size(); ++index) {
                if (index != 0U) {
                    result.push_back(',');
                }
                result += csv_escape(values[index]);
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

[[nodiscard]] std::string bool_text(bool value) {
    return value ? "true" : "false";
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
    for (std::size_t offset = 0U; offset < bytes.size(); offset += 64U) {
        std::array<std::uint32_t, 64> words{};
        for (std::size_t index = 0U; index < 16U; ++index) {
            const auto base = offset + 4U * index;
            words[index] = (static_cast<std::uint32_t>(bytes[base]) << 24U) |
                (static_cast<std::uint32_t>(bytes[base + 1U]) << 16U) |
                (static_cast<std::uint32_t>(bytes[base + 2U]) << 8U) |
                static_cast<std::uint32_t>(bytes[base + 3U]);
        }
        for (std::size_t index = 16U; index < 64U; ++index) {
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
        for (std::size_t index = 0U; index < 64U; ++index) {
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
    std::span<const std::uint8_t> bytes) {
    return sha256(std::string_view(
        reinterpret_cast<const char*>(bytes.data()), bytes.size()));
}

[[nodiscard]] std::string lowercase_hex(
    std::span<const std::uint8_t> bytes) {
    constexpr std::string_view digits = "0123456789abcdef";
    std::string result;
    result.reserve(bytes.size() * 2U);
    for (const std::uint8_t byte : bytes) {
        result.push_back(digits[byte >> 4U]);
        result.push_back(digits[byte & 0x0fU]);
    }
    return result;
}

[[nodiscard]] std::string hex64(double value) {
    if (!std::isfinite(value)) {
        throw std::overflow_error("nonfinite binary64 evidence value");
    }
    if (value == 0.0) {
        return "0x0.0p+0";
    }
    const auto bits = std::bit_cast<std::uint64_t>(value);
    const bool negative = (bits >> 63U) != 0U;
    const auto exponent_bits = static_cast<unsigned>((bits >> 52U) & 0x7ffU);
    const auto fraction = bits & UINT64_C(0x000fffffffffffff);
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

[[nodiscard]] std::string json_escape(std::string_view value) {
    std::string result;
    for (const char character : value) {
        switch (character) {
        case '\\': result += "\\\\"; break;
        case '\"': result += "\\\""; break;
        case '\n': result += "\\n"; break;
        case '\r': result += "\\r"; break;
        case '\t': result += "\\t"; break;
        default: result.push_back(character); break;
        }
    }
    return result;
}

void write_text(const std::filesystem::path& path, std::string_view contents) {
    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    if (!output) {
        throw std::runtime_error("cannot open output file: " + path.string());
    }
    output.write(contents.data(), static_cast<std::streamsize>(contents.size()));
    if (!output) {
        throw std::runtime_error("cannot write output file: " + path.string());
    }
}

[[nodiscard]] double stable_norm(std::span<const double> values) {
    double scale = 0.0;
    double sum = 1.0;
    for (const double value : values) {
        const double magnitude = std::abs(value);
        if (magnitude == 0.0) {
            continue;
        }
        if (scale < magnitude) {
            const double ratio = scale / magnitude;
            sum = 1.0 + sum * ratio * ratio;
            scale = magnitude;
        } else {
            const double ratio = magnitude / scale;
            sum += ratio * ratio;
        }
    }
    return scale == 0.0 ? 0.0 : scale * std::sqrt(sum);
}

[[nodiscard]] double matrix_frobenius(const mo::DenseMatrix& matrix) {
    return stable_norm(matrix.entries());
}

[[nodiscard]] std::vector<double> matrix_vector(
    const mo::DenseMatrix& matrix, std::span<const double> vector) {
    if (vector.size() != matrix.column_count()) {
        throw std::invalid_argument("matrix-vector size mismatch");
    }
    std::vector<double> result(matrix.row_count(), 0.0);
    for (std::size_t row = 0U; row < matrix.row_count(); ++row) {
        double value = 0.0;
        for (std::size_t column = 0U; column < matrix.column_count(); ++column) {
            value = std::fma(matrix(row, column), vector[column], value);
        }
        result[row] = value;
    }
    return result;
}

[[nodiscard]] std::vector<double> matrix_column(
    const mo::DenseMatrix& matrix, std::size_t column) {
    std::vector<double> result(matrix.row_count(), 0.0);
    for (std::size_t row = 0U; row < matrix.row_count(); ++row) {
        result[row] = matrix(row, column);
    }
    return result;
}

[[nodiscard]] double safe_squared_distance(Vec3d first, Vec3d second) {
    const Vec3d difference{first.x - second.x, first.y - second.y,
        first.z - second.z};
    const double scale = std::max(
        {std::abs(difference.x), std::abs(difference.y),
         std::abs(difference.z)});
    if (scale == 0.0) {
        return 0.0;
    }
    if (!std::isfinite(scale) ||
        scale > std::sqrt(std::numeric_limits<double>::max() / 3.0)) {
        throw std::overflow_error("squared distance is not representable");
    }
    const double x = difference.x / scale;
    const double y = difference.y / scale;
    const double z = difference.z / scale;
    return scale * scale * (x * x + y * y + z * z);
}

struct RelationRecord final {
    std::string id{};
    bool retained{true};
    std::string source{};
    mo::BondRelation bond{};
};

struct Rational final {
    std::int64_t numerator{0};
    std::int64_t denominator{1};

    Rational() = default;
    Rational(std::int64_t numerator_value, std::int64_t denominator_value = 1)
        : numerator(numerator_value), denominator(denominator_value) {
        if (denominator == 0) {
            throw std::invalid_argument("zero rational denominator");
        }
        if (denominator < 0) {
            numerator = -numerator;
            denominator = -denominator;
        }
        const auto divisor = std::gcd(
            static_cast<std::uint64_t>(numerator < 0 ? -numerator : numerator),
            static_cast<std::uint64_t>(denominator));
        numerator /= static_cast<std::int64_t>(divisor);
        denominator /= static_cast<std::int64_t>(divisor);
    }

    [[nodiscard]] double binary64() const {
        return static_cast<double>(numerator) /
            static_cast<double>(denominator);
    }
};

[[nodiscard]] Rational operator+(Rational lhs, Rational rhs) {
    return {lhs.numerator * rhs.denominator +
        rhs.numerator * lhs.denominator,
        lhs.denominator * rhs.denominator};
}

[[nodiscard]] Rational operator*(Rational lhs, Rational rhs) {
    return {lhs.numerator * rhs.numerator,
        lhs.denominator * rhs.denominator};
}

struct RationalVec3 final {
    std::array<Rational, 3> value{};
};

[[nodiscard]] RationalVec3 operator+(const RationalVec3& lhs,
                                     const RationalVec3& rhs) {
    RationalVec3 result{};
    for (std::size_t axis = 0U; axis < 3U; ++axis) {
        result.value[axis] = lhs.value[axis] + rhs.value[axis];
    }
    return result;
}

[[nodiscard]] RationalVec3 operator*(Rational scale,
                                     const RationalVec3& vector) {
    RationalVec3 result{};
    for (std::size_t axis = 0U; axis < 3U; ++axis) {
        result.value[axis] = scale * vector.value[axis];
    }
    return result;
}

[[nodiscard]] RationalVec3 exact_rotate(const RationalVec3& vector) {
    constexpr std::array<std::array<std::int64_t, 3>, 3> numerator{{
        {{1, 8, 4}}, {{8, 1, -4}}, {{-4, 4, -7}}}};
    RationalVec3 result{};
    for (std::size_t row = 0U; row < 3U; ++row) {
        Rational sum{};
        for (std::size_t column = 0U; column < 3U; ++column) {
            sum = sum + Rational(numerator[row][column], 9) *
                vector.value[column];
        }
        result.value[row] = sum;
    }
    return result;
}

[[nodiscard]] Vec3d binary64(const RationalVec3& value) {
    return {value.value[0].binary64(), value.value[1].binary64(),
        value.value[2].binary64()};
}

[[nodiscard]] RationalVec3 rational_vec(Rational x, Rational y, Rational z) {
    return {{{x, y, z}}};
}

struct Configuration final {
    std::string id{};
    std::string base_id{};
    std::string family{};
    std::string variant{"original"};
    std::string profile{};
    std::string transform{"identity"};
    double spacing_m{nominal_spacing_m};
    double support_radius_m{nominal_spacing_m};
    double geometry_scale{1.0};
    std::vector<mo::MechanicalPacket> packets{};
    std::vector<Vec3d> jitter_offsets_m{};
    std::vector<RelationRecord> edges{};
    std::vector<mo::VolumeRelation> volumes{};
    bool intentionally_flexible{false};
    bool decision_driving{true};
    bool exact_control{false};
    bool candidate_a_representative{false};
};

[[nodiscard]] std::vector<mo::MechanicalPacket> rectangular_lattice(
    int nx, int ny, int nz, double spacing_m) {
    std::vector<mo::MechanicalPacket> result;
    std::uint64_t id = 1U;
    for (int z = 0; z < nz; ++z) {
        for (int y = 0; y < ny; ++y) {
            for (int x = 0; x < nx; ++x) {
                result.push_back(mo::MechanicalPacket{
                    id++, packet_mass_quanta,
                    {spacing_m * static_cast<double>(x),
                     spacing_m * static_cast<double>(y),
                     spacing_m * static_cast<double>(z)},
                    {}});
            }
        }
    }
    return result;
}

[[nodiscard]] std::vector<mo::MechanicalPacket> bcc_lattice(double spacing_m) {
    auto result = rectangular_lattice(3, 3, 3, spacing_m);
    std::uint64_t id = static_cast<std::uint64_t>(result.size()) + 1U;
    for (int z = 0; z < 2; ++z) {
        for (int y = 0; y < 2; ++y) {
            for (int x = 0; x < 2; ++x) {
                result.push_back(mo::MechanicalPacket{
                    id++, packet_mass_quanta,
                    {spacing_m * (static_cast<double>(x) + 0.5),
                     spacing_m * (static_cast<double>(y) + 0.5),
                     spacing_m * (static_cast<double>(z) + 0.5)},
                    {}});
            }
        }
    }
    return result;
}

constexpr std::array<std::array<int, 3>, 27> frozen_jitter_numerators{{
    {{-7, 2, 5}}, {{4, -1, -6}}, {{1, 7, -3}},
    {{-2, -5, 6}}, {{6, 3, 0}}, {{-4, 1, 7}},
    {{3, -7, 2}}, {{0, 5, -4}}, {{7, -2, 1}},
    {{-5, 6, -1}}, {{2, 0, 4}}, {{-1, -3, -7}},
    {{5, 4, 3}}, {{-6, -1, 2}}, {{1, -4, 6}},
    {{-3, 7, -5}}, {{4, 2, -2}}, {{-7, -6, 5}},
    {{2, 3, 7}}, {{-4, 5, 0}}, {{6, -7, -1}},
    {{-1, 1, -4}}, {{3, -2, 6}}, {{-5, 4, -7}},
    {{7, 0, 3}}, {{0, -5, 1}}, {{5, 6, -2}}
}};

[[nodiscard]] Configuration make_base_configuration(
    std::string family, std::string profile, double support_ratio,
    std::vector<mo::MechanicalPacket> packets, bool flexible = false) {
    Configuration result{};
    result.family = std::move(family);
    result.profile = std::move(profile);
    result.id = "base." + result.family + "." + result.profile + ".original";
    result.base_id = result.id;
    result.support_radius_m = support_ratio * nominal_spacing_m;
    result.packets = std::move(packets);
    result.jitter_offsets_m.resize(result.packets.size());
    result.intentionally_flexible = flexible;
    return result;
}

[[nodiscard]] std::vector<mo::BondRelation> radius_edges(
    std::span<const mo::MechanicalPacket> packets, double radius_m) {
    if (!(radius_m > 0.0) || !std::isfinite(radius_m)) {
        throw std::invalid_argument("relation radius must be positive and finite");
    }
    const double radius_squared = radius_m * radius_m;
    if (!std::isfinite(radius_squared)) {
        throw std::overflow_error("relation radius squared overflow");
    }
    std::vector<mo::BondRelation> result;
    for (std::size_t first = 0U; first < packets.size(); ++first) {
        for (std::size_t second = first + 1U; second < packets.size(); ++second) {
            const double distance_squared = safe_squared_distance(
                packets[first].position_m, packets[second].position_m);
            if (distance_squared > 0.0 && distance_squared < radius_squared) {
                result.push_back({packets[first].id, packets[second].id});
            }
        }
    }
    std::sort(result.begin(), result.end(), [](const auto& lhs, const auto& rhs) {
        return std::tie(lhs.first_id, lhs.second_id) <
            std::tie(rhs.first_id, rhs.second_id);
    });
    return result;
}

[[nodiscard]] std::vector<RelationRecord> retained_records(
    std::span<const mo::BondRelation> bonds, std::string_view source) {
    std::vector<RelationRecord> result;
    result.reserve(bonds.size());
    for (const auto& bond : bonds) {
        result.push_back(RelationRecord{
            "bond." + std::to_string(bond.first_id) + "." +
                std::to_string(bond.second_id),
            true, std::string(source), bond});
    }
    return result;
}

[[nodiscard]] Matrix3d rational_quaternion_rotation() {
    Matrix3d result{};
    result.value = {{{1.0 / 9.0, 8.0 / 9.0, 4.0 / 9.0},
                     {8.0 / 9.0, 1.0 / 9.0, -4.0 / 9.0},
                     {-4.0 / 9.0, 4.0 / 9.0, -7.0 / 9.0}}};
    return result;
}

[[nodiscard]] Matrix3d signed_axis_rotation() {
    Matrix3d result{};
    result.value = {{{1.0, 0.0, 0.0}, {0.0, -1.0, 0.0},
                     {0.0, 0.0, -1.0}}};
    return result;
}

[[nodiscard]] Configuration transformed_configuration(
    const Configuration& base, std::string variant, std::string transform,
    double scale, bool translate) {
    Configuration result = base;
    result.variant = std::move(variant);
    result.transform = std::move(transform);
    result.id = base.base_id + "." + result.variant;
    result.geometry_scale = scale;
    result.spacing_m = base.spacing_m * scale;
    result.support_radius_m = base.support_radius_m * scale;
    const Vec3d translation = translate ? Vec3d{0.13, -0.07, 0.21} : Vec3d{};
    result.packets = mo::similarity_transform_packets(
        base.packets, rational_quaternion_rotation(), translation, scale);
    result.jitter_offsets_m.clear();
    result.jitter_offsets_m.reserve(base.jitter_offsets_m.size());
    for (const Vec3d jitter : base.jitter_offsets_m) {
        result.jitter_offsets_m.push_back(
            scale * mls::experimental::multiply(
                rational_quaternion_rotation(), jitter));
    }
    result.volumes.clear();
    result.candidate_a_representative = false;
    return result;
}

[[nodiscard]] Configuration translated_configuration(const Configuration& base) {
    Configuration result = base;
    result.variant = "translation";
    result.transform = "translation";
    result.id = base.base_id + ".translation";
    result.packets = base.packets;
    for (auto& packet : result.packets) {
        packet.position_m += Vec3d{0.13, -0.07, 0.21};
    }
    result.volumes.clear();
    result.candidate_a_representative = false;
    return result;
}

void add_radius_relations(Configuration& configuration) {
    configuration.edges = retained_records(
        radius_edges(configuration.packets, configuration.support_radius_m),
        "physical_radius");
}

[[nodiscard]] Configuration exact_configuration(
    std::string name, std::vector<Vec3d> positions,
    std::vector<std::pair<std::uint64_t, std::uint64_t>> edges,
    bool flexible) {
    Configuration result{};
    result.id = "exact." + name;
    result.base_id = result.id;
    result.family = name;
    result.profile = "exact";
    result.support_radius_m = 2.0;
    result.intentionally_flexible = flexible;
    result.exact_control = true;
    result.packets.reserve(positions.size());
    result.jitter_offsets_m.resize(positions.size());
    for (std::size_t index = 0U; index < positions.size(); ++index) {
        result.packets.push_back({
            static_cast<std::uint64_t>(index) + 1U, packet_mass_quanta,
            positions[index], {}});
    }
    for (const auto& [first, second] : edges) {
        const mo::BondRelation bond{std::min(first, second), std::max(first, second)};
        result.edges.push_back({
            "bond." + std::to_string(bond.first_id) + "." +
                std::to_string(bond.second_id),
            true, "exact_control", bond});
    }
    std::sort(result.edges.begin(), result.edges.end(), [](const auto& lhs, const auto& rhs) {
        return std::tie(lhs.bond.first_id, lhs.bond.second_id) <
            std::tie(rhs.bond.first_id, rhs.bond.second_id);
    });
    return result;
}

[[nodiscard]] std::vector<Configuration> base_configurations() {
    std::vector<Configuration> result;
    const auto add_profiles = [&](std::string_view family,
                                  std::vector<mo::MechanicalPacket> packets,
                                  std::initializer_list<std::pair<std::string_view, double>> profiles,
                                  bool flexible = false) {
        for (const auto& [profile, ratio] : profiles) {
            result.push_back(make_base_configuration(
                std::string(family), std::string(profile), ratio, packets,
                flexible));
        }
    };
    add_profiles("sc3", rectangular_lattice(3, 3, 3, nominal_spacing_m),
        {{"r105", 21.0 / 20.0}, {"r150", 3.0 / 2.0}, {"r180", 9.0 / 5.0}});
    add_profiles("bcc35", bcc_lattice(nominal_spacing_m),
        {{"r105", 21.0 / 20.0}, {"r150", 3.0 / 2.0}, {"r180", 9.0 / 5.0}});

    auto jittered = rectangular_lattice(3, 3, 3, nominal_spacing_m);
    for (std::size_t index = 0U; index < jittered.size(); ++index) {
        const auto& values = frozen_jitter_numerators[index];
        const Vec3d jitter{
            nominal_spacing_m * static_cast<double>(values[0]) / 100.0,
            nominal_spacing_m * static_cast<double>(values[1]) / 100.0,
            nominal_spacing_m * static_cast<double>(values[2]) / 100.0};
        jittered[index].position_m += jitter;
    }
    const auto jitter_begin = result.size();
    add_profiles("jitter27", jittered,
        {{"r105", 21.0 / 20.0}, {"r150", 3.0 / 2.0}, {"r180", 9.0 / 5.0}});
    for (std::size_t config = jitter_begin; config < result.size(); ++config) {
        for (std::size_t index = 0U; index < jittered.size(); ++index) {
            const auto& values = frozen_jitter_numerators[index];
            result[config].jitter_offsets_m[index] = {
                nominal_spacing_m * static_cast<double>(values[0]) / 100.0,
                nominal_spacing_m * static_cast<double>(values[1]) / 100.0,
                nominal_spacing_m * static_cast<double>(values[2]) / 100.0};
        }
    }
    add_profiles("free_face", rectangular_lattice(4, 4, 3, nominal_spacing_m),
        {{"r150", 3.0 / 2.0}, {"r180", 9.0 / 5.0}});
    add_profiles("edge_truncated", rectangular_lattice(4, 3, 3, nominal_spacing_m),
        {{"r150", 3.0 / 2.0}, {"r180", 9.0 / 5.0}});
    add_profiles("corner_truncated", rectangular_lattice(3, 3, 3, nominal_spacing_m),
        {{"r150", 3.0 / 2.0}, {"r180", 9.0 / 5.0}});
    add_profiles("sheet", rectangular_lattice(5, 5, 1, nominal_spacing_m),
        {{"r105", 21.0 / 20.0}, {"r150", 3.0 / 2.0}}, true);
    add_profiles("filament", rectangular_lattice(8, 1, 1, nominal_spacing_m),
        {{"r105", 21.0 / 20.0}, {"r205", 41.0 / 20.0}}, true);

    for (auto& configuration : result) {
        add_radius_relations(configuration);
    }

    auto underconnected = exact_configuration(
        "noncoplanar_underconnected",
        {{0.0, 0.0, 0.0}, {0.25, 0.0, 0.0}, {0.0, 0.25, 0.0},
         {0.0, 0.0, 0.25}},
        {{1U, 2U}, {1U, 3U}, {1U, 4U}, {2U, 3U}, {2U, 4U}}, true);
    underconnected.profile = "k4_minus_edge";
    result.push_back(std::move(underconnected));

    const auto sc_high = std::find_if(result.begin(), result.end(), [](const auto& value) {
        return value.family == "sc3" && value.profile == "r180";
    });
    if (sc_high == result.end()) {
        throw std::logic_error("missing SC high-radius base");
    }
    for (const int percent : {10, 25, 40}) {
        Configuration deleted = *sc_high;
        deleted.family = "sc3_deletion";
        deleted.profile = "delete" + std::to_string(percent);
        deleted.id = "base." + deleted.family + "." + deleted.profile + ".original";
        deleted.base_id = deleted.id;
        std::vector<std::pair<std::string, std::size_t>> ordering;
        for (std::size_t index = 0U; index < deleted.edges.size(); ++index) {
            const auto& bond = deleted.edges[index].bond;
            const std::string preimage = std::to_string(seed) + "|" + deleted.id + "|" +
                std::to_string(bond.first_id) + "|" + std::to_string(bond.second_id);
            ordering.emplace_back(sha256(preimage), index);
        }
        std::sort(ordering.begin(), ordering.end());
        const std::size_t remove_count =
            deleted.edges.size() * static_cast<std::size_t>(percent) / 100U;
        std::set<std::size_t> removed;
        for (std::size_t index = 0U; index < remove_count; ++index) {
            removed.insert(ordering[index].second);
        }
        for (std::size_t index = 0U; index < deleted.edges.size(); ++index) {
            if (removed.contains(index)) {
                deleted.edges[index].retained = false;
                deleted.edges[index].source = "sha256_deletion_" + std::to_string(percent);
            }
        }
        result.push_back(std::move(deleted));
    }

    const std::vector<Vec3d> tetra{{0.0, 0.0, 0.0}, {1.0, 0.0, 0.0},
        {0.0, 1.0, 0.0}, {0.0, 0.0, 1.0}};
    const std::vector<std::pair<std::uint64_t, std::uint64_t>> k4{
        {1U, 2U}, {1U, 3U}, {1U, 4U}, {2U, 3U}, {2U, 4U}, {3U, 4U}};
    result.push_back(exact_configuration("tetrahedron_k4", tetra, k4, false));
    auto k4_minus = k4;
    k4_minus.pop_back();
    result.push_back(exact_configuration(
        "tetrahedron_k4_minus_edge", tetra, k4_minus, true));

    const std::vector<Vec3d> octa{{1.0, 0.0, 0.0}, {-1.0, 0.0, 0.0},
        {0.0, 1.0, 0.0}, {0.0, -1.0, 0.0}, {0.0, 0.0, 1.0},
        {0.0, 0.0, -1.0}};
    std::vector<std::pair<std::uint64_t, std::uint64_t>> octa_edges;
    for (std::uint64_t first = 1U; first <= 6U; ++first) {
        for (std::uint64_t second = first + 1U; second <= 6U; ++second) {
            const Vec3d sum = octa[first - 1U] + octa[second - 1U];
            if (safe_squared_distance(sum, {}) != 0.0) {
                octa_edges.emplace_back(first, second);
            }
        }
    }
    result.push_back(exact_configuration(
        "octahedron_graph", octa, octa_edges, false));

    std::vector<Vec3d> cube;
    for (int z = 0; z < 2; ++z) {
        for (int y = 0; y < 2; ++y) {
            for (int x = 0; x < 2; ++x) {
                cube.push_back({static_cast<double>(x), static_cast<double>(y),
                    static_cast<double>(z)});
            }
        }
    }
    std::vector<std::pair<std::uint64_t, std::uint64_t>> cube_edges;
    for (std::size_t first = 0U; first < cube.size(); ++first) {
        for (std::size_t second = first + 1U; second < cube.size(); ++second) {
            const Vec3d d = cube[first] - cube[second];
            if (std::abs(d.x) + std::abs(d.y) + std::abs(d.z) == 1.0) {
                cube_edges.emplace_back(first + 1U, second + 1U);
            }
        }
    }
    result.push_back(exact_configuration(
        "cube_edge_graph", cube, cube_edges, true));

    const std::vector<Vec3d> square{{0.0, 0.0, 0.0}, {1.0, 0.0, 0.0},
        {1.0, 1.0, 0.0}, {0.0, 1.0, 0.0}};
    const std::vector<std::pair<std::uint64_t, std::uint64_t>> square_edges{
        {1U, 2U}, {2U, 3U}, {3U, 4U}, {1U, 4U}, {1U, 3U}};
    result.push_back(exact_configuration(
        "planar_square_plus_diagonal", square, square_edges, true));
    auto square_enriched = exact_configuration(
        "planar_square_plus_diagonal_and_volume", square, square_edges, true);
    square_enriched.volumes.push_back({1U, {2U, 3U, 4U}});
    result.push_back(std::move(square_enriched));

    if (result.size() != 29U) {
        throw std::logic_error("frozen base configuration count is not 29");
    }
    return result;
}

[[nodiscard]] bool is_metamorphic_representative(const Configuration& value) {
    return (value.family == "sc3" && value.profile == "r180") ||
        (value.family == "bcc35" && value.profile == "r180") ||
        (value.family == "jitter27" && value.profile == "r180") ||
        (value.family == "corner_truncated" && value.profile == "r180") ||
        (value.family == "sheet" && value.profile == "r150") ||
        (value.family == "filament" && value.profile == "r205");
}

[[nodiscard]] std::vector<RationalVec3> rational_rectangular_lattice(
    int nx, int ny, int nz) {
    std::vector<RationalVec3> result;
    for (int z = 0; z < nz; ++z) {
        for (int y = 0; y < ny; ++y) {
            for (int x = 0; x < nx; ++x) {
                result.push_back({{{Rational(x, 4), Rational(y, 4),
                    Rational(z, 4)}}});
            }
        }
    }
    return result;
}

[[nodiscard]] std::vector<RationalVec3> rational_base_positions(
    const Configuration& configuration) {
    if (configuration.family == "sc3" ||
        configuration.family == "corner_truncated" ||
        configuration.family == "sc3_deletion") {
        return rational_rectangular_lattice(3, 3, 3);
    }
    if (configuration.family == "free_face") {
        return rational_rectangular_lattice(4, 4, 3);
    }
    if (configuration.family == "edge_truncated") {
        return rational_rectangular_lattice(4, 3, 3);
    }
    if (configuration.family == "sheet") {
        return rational_rectangular_lattice(5, 5, 1);
    }
    if (configuration.family == "filament") {
        return rational_rectangular_lattice(8, 1, 1);
    }
    if (configuration.family == "bcc35") {
        auto result = rational_rectangular_lattice(3, 3, 3);
        for (int z = 0; z < 2; ++z) {
            for (int y = 0; y < 2; ++y) {
                for (int x = 0; x < 2; ++x) {
                    result.push_back({{{Rational(2 * x + 1, 8),
                        Rational(2 * y + 1, 8),
                        Rational(2 * z + 1, 8)}}});
                }
            }
        }
        return result;
    }
    if (configuration.family == "jitter27") {
        auto result = rational_rectangular_lattice(3, 3, 3);
        for (std::size_t index = 0U; index < result.size(); ++index) {
            for (std::size_t axis = 0U; axis < 3U; ++axis) {
                result[index].value[axis] = result[index].value[axis] +
                    Rational(frozen_jitter_numerators[index][axis], 400);
            }
        }
        return result;
    }
    if (configuration.family == "noncoplanar_underconnected") {
        return {rational_vec(0, 0, 0), rational_vec({1, 4}, 0, 0),
            rational_vec(0, {1, 4}, 0), rational_vec(0, 0, {1, 4})};
    }
    if (configuration.family == "tetrahedron_k4" ||
        configuration.family == "tetrahedron_k4_minus_edge") {
        return {rational_vec(0, 0, 0), rational_vec(1, 0, 0),
            rational_vec(0, 1, 0), rational_vec(0, 0, 1)};
    }
    if (configuration.family == "octahedron_graph") {
        return {rational_vec(1, 0, 0), rational_vec(-1, 0, 0),
            rational_vec(0, 1, 0), rational_vec(0, -1, 0),
            rational_vec(0, 0, 1), rational_vec(0, 0, -1)};
    }
    if (configuration.family == "cube_edge_graph") {
        std::vector<RationalVec3> result;
        for (int z = 0; z < 2; ++z) {
            for (int y = 0; y < 2; ++y) {
                for (int x = 0; x < 2; ++x) {
                    result.push_back(rational_vec(x, y, z));
                }
            }
        }
        return result;
    }
    if (configuration.family == "planar_square_plus_diagonal" ||
        configuration.family == "planar_square_plus_diagonal_and_volume") {
        return {rational_vec(0, 0, 0), rational_vec(1, 0, 0),
            rational_vec(1, 1, 0), rational_vec(0, 1, 0)};
    }
    throw std::logic_error("missing rational base geometry for " +
        configuration.family);
}

[[nodiscard]] Rational support_ratio(std::string_view profile) {
    if (profile == "r105") {
        return {21, 20};
    }
    if (profile == "r150") {
        return {3, 2};
    }
    if (profile == "r180" || profile == "delete10" ||
        profile == "delete25" || profile == "delete40") {
        return {9, 5};
    }
    if (profile == "r205") {
        return {41, 20};
    }
    if (profile == "exact" || profile == "k4_minus_edge") {
        return {8, 1};
    }
    throw std::logic_error("missing rational support profile");
}

void apply_rational_geometry(Configuration& configuration) {
    auto points = rational_base_positions(configuration);
    std::vector<RationalVec3> jitter(points.size());
    if (configuration.family == "jitter27") {
        for (std::size_t index = 0U; index < jitter.size(); ++index) {
            for (std::size_t axis = 0U; axis < 3U; ++axis) {
                jitter[index].value[axis] =
                    Rational(frozen_jitter_numerators[index][axis], 400);
            }
        }
    }
    Rational scale{1};
    bool rotate = false;
    bool translate = false;
    if (configuration.variant == "translation") {
        translate = true;
    } else if (configuration.variant == "rotation") {
        rotate = true;
    } else if (configuration.variant == "rotation_translation") {
        rotate = true;
        translate = true;
    } else if (configuration.variant == "scale_half_rotation") {
        scale = {1, 2};
        rotate = true;
    } else if (configuration.variant == "scale_double_rotation") {
        scale = {2, 1};
        rotate = true;
    } else if (configuration.variant != "original") {
        throw std::logic_error("unknown frozen geometry variant");
    }
    const RationalVec3 translation{{{Rational(13, 100),
        Rational(-7, 100), Rational(21, 100)}}};
    for (std::size_t index = 0U; index < points.size(); ++index) {
        if (rotate) {
            points[index] = exact_rotate(points[index]);
            jitter[index] = exact_rotate(jitter[index]);
        }
        points[index] = scale * points[index];
        jitter[index] = scale * jitter[index];
        if (translate) {
            points[index] = points[index] + translation;
        }
    }
    if (points.size() != configuration.packets.size()) {
        throw std::logic_error("rational geometry packet-count mismatch");
    }
    for (std::size_t index = 0U; index < points.size(); ++index) {
        configuration.packets[index].position_m = binary64(points[index]);
        configuration.packets[index].velocity_m_per_s = {};
        configuration.jitter_offsets_m[index] = binary64(jitter[index]);
    }
    const Rational spacing = scale * Rational(1, 4);
    const Rational support = configuration.exact_control
        ? Rational(2) : scale * support_ratio(configuration.profile) *
            Rational(1, 4);
    configuration.spacing_m = spacing.binary64();
    configuration.support_radius_m = support.binary64();
    configuration.geometry_scale = scale.binary64();

    if (!configuration.exact_control) {
        configuration.edges = retained_records(radius_edges(
            configuration.packets, configuration.support_radius_m),
            "physical_radius");
        if (configuration.family == "sc3_deletion") {
            const int percent = std::stoi(configuration.profile.substr(6));
            std::vector<std::pair<std::string, std::size_t>> ordering;
            for (std::size_t index = 0U; index < configuration.edges.size(); ++index) {
                const auto& bond = configuration.edges[index].bond;
                const std::string preimage = std::to_string(seed) + "|" +
                    configuration.id + "|" + std::to_string(bond.first_id) +
                    "|" + std::to_string(bond.second_id);
                ordering.emplace_back(sha256(preimage), index);
            }
            std::sort(ordering.begin(), ordering.end());
            const std::size_t remove_count = ordering.size() *
                static_cast<std::size_t>(percent) / 100U;
            for (std::size_t index = 0U; index < remove_count; ++index) {
                auto& removed = configuration.edges[ordering[index].second];
                removed.retained = false;
                removed.source = "sha256_deletion_" + std::to_string(percent);
            }
        }
    }
}

[[nodiscard]] std::vector<Configuration> full_configurations() {
    auto result = base_configurations();
    std::vector<Configuration> variants;
    for (auto& base : result) {
        if (!is_metamorphic_representative(base)) {
            continue;
        }
        base.candidate_a_representative = true;
        variants.push_back(translated_configuration(base));
        variants.push_back(transformed_configuration(
            base, "rotation", "rational_quaternion_rotation", 1.0, false));
        variants.push_back(transformed_configuration(
            base, "rotation_translation", "rational_quaternion_rotation_translation",
            1.0, true));
        variants.push_back(transformed_configuration(
            base, "scale_half_rotation", "scale_half_rotation", 0.5, false));
        variants.push_back(transformed_configuration(
            base, "scale_double_rotation", "scale_double_rotation", 2.0, false));
    }
    result.insert(result.end(), variants.begin(), variants.end());
    for (auto& configuration : result) {
        apply_rational_geometry(configuration);
    }
    std::sort(result.begin(), result.end(), [](const auto& lhs, const auto& rhs) {
        return lhs.id < rhs.id;
    });
    if (result.size() != 59U) {
        throw std::logic_error("frozen full configuration count is not 59");
    }
    return result;
}

[[nodiscard]] std::vector<Configuration> configurations(bool smoke) {
    auto result = full_configurations();
    if (!smoke) {
        return result;
    }
    const std::set<std::string> selected{
        "base.filament.r205.original",
        "base.filament.r205.original.translation",
        "exact.planar_square_plus_diagonal_and_volume"};
    std::erase_if(result, [&](const auto& value) {
        return !selected.contains(value.id);
    });
    if (result.size() != selected.size()) {
        throw std::logic_error("smoke configuration selection is incomplete");
    }
    return result;
}

class SignedBigInteger final {
public:
    SignedBigInteger() = default;

    [[nodiscard]] static SignedBigInteger from_unsigned(
        std::uint64_t value) {
        SignedBigInteger result;
        if (value == 0U) {
            return result;
        }
        result.sign_ = 1;
        result.limbs_.push_back(static_cast<std::uint32_t>(value));
        const auto high = static_cast<std::uint32_t>(value >> 32U);
        if (high != 0U) {
            result.limbs_.push_back(high);
        }
        return result;
    }

    [[nodiscard]] bool is_zero() const noexcept { return sign_ == 0; }

    [[nodiscard]] SignedBigInteger negated() const {
        auto result = *this;
        result.sign_ = -result.sign_;
        return result;
    }

    [[nodiscard]] SignedBigInteger shifted_left(unsigned count) const {
        if (is_zero() || count == 0U) {
            return *this;
        }
        const std::size_t word_shift = count / 32U;
        const unsigned bit_shift = count % 32U;
        SignedBigInteger result;
        result.sign_ = sign_;
        result.limbs_.assign(word_shift + limbs_.size() + 1U, 0U);
        std::uint64_t carry = 0U;
        for (std::size_t index = 0U; index < limbs_.size(); ++index) {
            const std::uint64_t current =
                (static_cast<std::uint64_t>(limbs_[index]) << bit_shift) |
                carry;
            result.limbs_[word_shift + index] =
                static_cast<std::uint32_t>(current);
            carry = current >> 32U;
        }
        result.limbs_[word_shift + limbs_.size()] =
            static_cast<std::uint32_t>(carry);
        result.normalize();
        return result;
    }

    [[nodiscard]] friend SignedBigInteger operator+(
        const SignedBigInteger& first, const SignedBigInteger& second) {
        if (first.is_zero()) {
            return second;
        }
        if (second.is_zero()) {
            return first;
        }
        if (first.sign_ == second.sign_) {
            auto result = add_magnitudes(first, second);
            result.sign_ = first.sign_;
            return result;
        }
        const int comparison = compare_magnitudes(first, second);
        if (comparison == 0) {
            return {};
        }
        auto result = comparison > 0
            ? subtract_magnitudes(first, second)
            : subtract_magnitudes(second, first);
        result.sign_ = comparison > 0 ? first.sign_ : second.sign_;
        return result;
    }

    [[nodiscard]] friend SignedBigInteger operator*(
        const SignedBigInteger& first, const SignedBigInteger& second) {
        if (first.is_zero() || second.is_zero()) {
            return {};
        }
        SignedBigInteger result;
        result.sign_ = first.sign_ * second.sign_;
        result.limbs_.assign(
            first.limbs_.size() + second.limbs_.size(), 0U);
        for (std::size_t first_index = 0U;
             first_index < first.limbs_.size(); ++first_index) {
            std::uint64_t carry = 0U;
            for (std::size_t second_index = 0U;
                 second_index < second.limbs_.size(); ++second_index) {
                const std::size_t output = first_index + second_index;
                const std::uint64_t current =
                    static_cast<std::uint64_t>(result.limbs_[output]) +
                    static_cast<std::uint64_t>(first.limbs_[first_index]) *
                        second.limbs_[second_index] + carry;
                result.limbs_[output] =
                    static_cast<std::uint32_t>(current);
                carry = current >> 32U;
            }
            result.limbs_[first_index + second.limbs_.size()] =
                static_cast<std::uint32_t>(carry);
        }
        result.normalize();
        return result;
    }

private:
    [[nodiscard]] static int compare_magnitudes(
        const SignedBigInteger& first, const SignedBigInteger& second) {
        if (first.limbs_.size() != second.limbs_.size()) {
            return first.limbs_.size() < second.limbs_.size() ? -1 : 1;
        }
        for (std::size_t index = first.limbs_.size(); index-- > 0U;) {
            if (first.limbs_[index] != second.limbs_[index]) {
                return first.limbs_[index] < second.limbs_[index] ? -1 : 1;
            }
        }
        return 0;
    }

    [[nodiscard]] static SignedBigInteger add_magnitudes(
        const SignedBigInteger& first, const SignedBigInteger& second) {
        SignedBigInteger result;
        const std::size_t count =
            std::max(first.limbs_.size(), second.limbs_.size());
        result.limbs_.assign(count + 1U, 0U);
        std::uint64_t carry = 0U;
        for (std::size_t index = 0U; index < count; ++index) {
            const std::uint64_t value = carry +
                (index < first.limbs_.size() ? first.limbs_[index] : 0U) +
                (index < second.limbs_.size() ? second.limbs_[index] : 0U);
            result.limbs_[index] = static_cast<std::uint32_t>(value);
            carry = value >> 32U;
        }
        result.limbs_[count] = static_cast<std::uint32_t>(carry);
        result.normalize();
        return result;
    }

    [[nodiscard]] static SignedBigInteger subtract_magnitudes(
        const SignedBigInteger& larger, const SignedBigInteger& smaller) {
        SignedBigInteger result;
        result.limbs_.assign(larger.limbs_.size(), 0U);
        std::uint64_t borrow = 0U;
        for (std::size_t index = 0U; index < larger.limbs_.size(); ++index) {
            const std::uint64_t lhs = larger.limbs_[index];
            const std::uint64_t rhs = borrow +
                (index < smaller.limbs_.size() ? smaller.limbs_[index] : 0U);
            result.limbs_[index] = static_cast<std::uint32_t>(lhs - rhs);
            borrow = lhs < rhs ? 1U : 0U;
        }
        result.normalize();
        return result;
    }

    void normalize() {
        while (!limbs_.empty() && limbs_.back() == 0U) {
            limbs_.pop_back();
        }
        if (limbs_.empty()) {
            sign_ = 0;
        }
    }

    int sign_{0};
    std::vector<std::uint32_t> limbs_{};
};

struct ExactDyadic final {
    SignedBigInteger numerator{};
    int exponent2{0};
};

[[nodiscard]] ExactDyadic exact_binary64(double value) {
    if (!std::isfinite(value)) {
        throw std::invalid_argument("exact dyadic input must be finite");
    }
    const auto bits = std::bit_cast<std::uint64_t>(value);
    const bool negative = (bits >> 63U) != 0U;
    const unsigned exponent_bits =
        static_cast<unsigned>((bits >> 52U) & 0x7ffU);
    const std::uint64_t fraction =
        bits & UINT64_C(0x000fffffffffffff);
    if (exponent_bits == 0U && fraction == 0U) {
        return {};
    }
    auto numerator = SignedBigInteger::from_unsigned(exponent_bits == 0U
        ? fraction : UINT64_C(0x0010000000000000) | fraction);
    if (negative) {
        numerator = numerator.negated();
    }
    return {std::move(numerator), exponent_bits == 0U
        ? -1074 : static_cast<int>(exponent_bits) - 1023 - 52};
}

[[nodiscard]] ExactDyadic exact_add(
    const ExactDyadic& first, const ExactDyadic& second) {
    const int exponent = std::min(first.exponent2, second.exponent2);
    return {first.numerator.shifted_left(static_cast<unsigned>(
                first.exponent2 - exponent)) +
            second.numerator.shifted_left(static_cast<unsigned>(
                second.exponent2 - exponent)),
        exponent};
}

[[nodiscard]] ExactDyadic exact_negate(const ExactDyadic& value) {
    return {value.numerator.negated(), value.exponent2};
}

[[nodiscard]] ExactDyadic exact_subtract(
    const ExactDyadic& first, const ExactDyadic& second) {
    return exact_add(first, exact_negate(second));
}

[[nodiscard]] ExactDyadic exact_multiply(
    const ExactDyadic& first, const ExactDyadic& second) {
    return {first.numerator * second.numerator,
        first.exponent2 + second.exponent2};
}

using ExactVector3 = std::array<ExactDyadic, 3>;

[[nodiscard]] bool exact_zero(const ExactVector3& value) {
    return std::ranges::all_of(value, [](const auto& component_value) {
        return component_value.numerator.is_zero();
    });
}

[[nodiscard]] ExactVector3 exact_cross(
    const ExactVector3& first, const ExactVector3& second) {
    return {
        exact_subtract(exact_multiply(first[1], second[2]),
            exact_multiply(first[2], second[1])),
        exact_subtract(exact_multiply(first[2], second[0]),
            exact_multiply(first[0], second[2])),
        exact_subtract(exact_multiply(first[0], second[1]),
            exact_multiply(first[1], second[0]))};
}

[[nodiscard]] ExactDyadic exact_dot(
    const ExactVector3& first, const ExactVector3& second) {
    return exact_add(exact_add(exact_multiply(first[0], second[0]),
        exact_multiply(first[1], second[1])),
        exact_multiply(first[2], second[2]));
}

[[nodiscard]] ExactVector3 exact_difference(Vec3d first, Vec3d second) {
    return {exact_subtract(exact_binary64(first.x), exact_binary64(second.x)),
        exact_subtract(exact_binary64(first.y), exact_binary64(second.y)),
        exact_subtract(exact_binary64(first.z), exact_binary64(second.z))};
}

[[nodiscard]] std::size_t exact_vector_rank(
    std::span<const ExactVector3> vectors) {
    std::optional<ExactVector3> first{};
    std::optional<ExactVector3> second{};
    for (const auto& vector : vectors) {
        if (exact_zero(vector)) {
            continue;
        }
        if (!first.has_value()) {
            first = vector;
            continue;
        }
        if (!second.has_value()) {
            if (!exact_zero(exact_cross(*first, vector))) {
                second = vector;
            }
            continue;
        }
        if (!exact_dot(*first, exact_cross(*second, vector)).numerator.is_zero()) {
            return 3U;
        }
    }
    return second.has_value() ? 2U : (first.has_value() ? 1U : 0U);
}

[[nodiscard]] std::size_t affine_span_rank(
    std::span<const mo::MechanicalPacket> packets) {
    if (packets.size() < 2U) {
        return 0U;
    }
    std::vector<ExactVector3> differences;
    differences.reserve(packets.size() - 1U);
    for (std::size_t index = 1U; index < packets.size(); ++index) {
        differences.push_back(exact_difference(
            packets[index].position_m, packets[0].position_m));
    }
    return exact_vector_rank(differences);
}

[[nodiscard]] std::map<std::uint64_t, Vec3d> packet_positions(
    std::span<const mo::MechanicalPacket> packets) {
    std::map<std::uint64_t, Vec3d> result;
    for (const auto& packet : packets) {
        if (!result.emplace(packet.id, packet.position_m).second) {
            throw std::invalid_argument("duplicate packet ID");
        }
    }
    return result;
}

[[nodiscard]] std::vector<mo::BondRelation> retained_bonds(
    const Configuration& configuration) {
    std::vector<mo::BondRelation> result;
    for (const auto& relation : configuration.edges) {
        if (relation.retained) {
            result.push_back(relation.bond);
        }
    }
    return result;
}

[[nodiscard]] std::map<std::uint64_t, std::set<std::uint64_t>> adjacency(
    const Configuration& configuration) {
    std::map<std::uint64_t, std::set<std::uint64_t>> result;
    for (const auto& packet : configuration.packets) {
        result.emplace(packet.id, std::set<std::uint64_t>{});
    }
    for (const auto& relation : configuration.edges) {
        if (!relation.retained) {
            continue;
        }
        result.at(relation.bond.first_id).insert(relation.bond.second_id);
        result.at(relation.bond.second_id).insert(relation.bond.first_id);
    }
    return result;
}

[[nodiscard]] bool graph_connected(const Configuration& configuration) {
    if (configuration.packets.empty()) {
        return false;
    }
    const auto graph = adjacency(configuration);
    std::set<std::uint64_t> reached;
    std::vector<std::uint64_t> pending{configuration.packets.front().id};
    reached.insert(pending.front());
    while (!pending.empty()) {
        const auto current = pending.back();
        pending.pop_back();
        for (const auto neighbor : graph.at(current)) {
            if (reached.insert(neighbor).second) {
                pending.push_back(neighbor);
            }
        }
    }
    return reached.size() == configuration.packets.size();
}

[[nodiscard]] std::size_t minimum_incident_direction_rank(
    const Configuration& configuration) {
    const auto positions = packet_positions(configuration.packets);
    const auto graph = adjacency(configuration);
    std::size_t minimum = 3U;
    for (const auto& [center, neighbors] : graph) {
        std::vector<ExactVector3> directions;
        directions.reserve(neighbors.size());
        for (const auto neighbor : neighbors) {
            directions.push_back(exact_difference(
                positions.at(neighbor), positions.at(center)));
        }
        minimum = std::min(minimum, exact_vector_rank(directions));
    }
    return graph.empty() ? 0U : minimum;
}

struct TopologyFacts final {
    std::size_t affine_rank{0U};
    bool connected{false};
    std::size_t edge_count{0U};
    std::size_t edge_lower_bound{0U};
    std::size_t minimum_direction_rank{0U};
    std::size_t rigid_rank{0U};
    bool generic_solid_gate{false};
};

[[nodiscard]] TopologyFacts topology_facts(const Configuration& configuration) {
    TopologyFacts result{};
    result.affine_rank = affine_span_rank(configuration.packets);
    result.connected = graph_connected(configuration);
    result.edge_count = retained_bonds(configuration).size();
    result.edge_lower_bound = configuration.packets.size() < 2U
        ? 0U
        : 3U * configuration.packets.size() - 6U;
    result.minimum_direction_rank =
        minimum_incident_direction_rank(configuration);
    result.rigid_rank = configuration.packets.empty() ? 0U :
        (result.affine_rank == 0U ? 3U :
            (result.affine_rank == 1U ? 5U : 6U));
    result.generic_solid_gate = result.affine_rank == 3U &&
        result.connected && result.edge_count >= result.edge_lower_bound &&
        result.minimum_direction_rank == 3U && result.rigid_rank == 6U &&
        !configuration.intentionally_flexible;
    return result;
}

[[nodiscard]] double volume_score(
    const std::map<std::uint64_t, Vec3d>& positions,
    const mo::VolumeRelation& relation) {
    const Vec3d a = positions.at(relation.other_ids[0]) -
        positions.at(relation.center_id);
    const Vec3d b = positions.at(relation.other_ids[1]) -
        positions.at(relation.center_id);
    const Vec3d c = positions.at(relation.other_ids[2]) -
        positions.at(relation.center_id);
    const Vec3d bc = mls::experimental::cross(b, c);
    const Vec3d ca = mls::experimental::cross(c, a);
    const Vec3d ab = mls::experimental::cross(a, b);
    return mls::experimental::dot(bc, bc) +
        mls::experimental::dot(ca, ca) +
        mls::experimental::dot(ab, ab);
}

[[nodiscard]] std::vector<mo::VolumeRelation> select_volume_relations(
    const Configuration& configuration) {
    return mo::select_oriented_volume_relations(
        configuration.packets, retained_bonds(configuration));
}

void assign_volume_relations(std::vector<Configuration>& configurations_value) {
    std::map<std::string, std::vector<mo::VolumeRelation>> base_relations;
    for (const auto& configuration : configurations_value) {
        if (configuration.variant != "original" || configuration.exact_control) {
            continue;
        }
        base_relations.emplace(
            configuration.base_id, select_volume_relations(configuration));
    }
    for (auto& configuration : configurations_value) {
        if (configuration.exact_control) {
            continue;
        }
        configuration.volumes = base_relations.at(configuration.base_id);
    }
}

struct LookupPhase final {
    std::string id{};
    Vec3d fraction{};
};

const std::array<LookupPhase, 2> lookup_phases{{
    {"p000", {0.0, 0.0, 0.0}},
    {"p037_011_029", {0.37, 0.11, 0.29}}
}};

[[nodiscard]] GridIndex lookup_cell(
    Vec3d position_m, Vec3d origin_m, double cell_spacing_m) {
    const auto coordinate = [&](double position, double origin) {
        const double value = std::floor((position - origin) / cell_spacing_m);
        if (!std::isfinite(value) ||
            value < static_cast<double>(std::numeric_limits<std::int64_t>::min()) ||
            value > static_cast<double>(std::numeric_limits<std::int64_t>::max())) {
            throw std::overflow_error("lookup-grid index overflow");
        }
        return static_cast<std::int64_t>(value);
    };
    return {coordinate(position_m.x, origin_m.x),
        coordinate(position_m.y, origin_m.y),
        coordinate(position_m.z, origin_m.z)};
}

[[nodiscard]] std::set<std::pair<std::uint64_t, std::uint64_t>>
lookup_candidate_pairs(
    std::span<const mo::MechanicalPacket> packets,
    double cell_spacing_m, const LookupPhase& phase) {
    const Vec3d origin{phase.fraction.x * cell_spacing_m,
        phase.fraction.y * cell_spacing_m,
        phase.fraction.z * cell_spacing_m};
    std::map<GridIndex, std::vector<std::uint64_t>> cells;
    for (const auto& packet : packets) {
        cells[lookup_cell(packet.position_m, origin, cell_spacing_m)].push_back(packet.id);
    }
    for (auto& [cell, ids] : cells) {
        static_cast<void>(cell);
        std::sort(ids.begin(), ids.end());
    }
    std::set<std::pair<std::uint64_t, std::uint64_t>> result;
    for (const auto& [cell, ids] : cells) {
        for (int dz = -1; dz <= 1; ++dz) {
            for (int dy = -1; dy <= 1; ++dy) {
                for (int dx = -1; dx <= 1; ++dx) {
                    const GridIndex neighbor{
                        cell.x + static_cast<std::int64_t>(dx),
                        cell.y + static_cast<std::int64_t>(dy),
                        cell.z + static_cast<std::int64_t>(dz)};
                    const auto found = cells.find(neighbor);
                    if (found == cells.end()) {
                        continue;
                    }
                    for (const auto first : ids) {
                        for (const auto second : found->second) {
                            if (first != second) {
                                result.emplace(
                                    std::min(first, second), std::max(first, second));
                            }
                        }
                    }
                }
            }
        }
    }
    return result;
}

struct NeighborAuditRow final {
    std::string configuration_id{};
    std::string phase{};
    std::uint64_t low_id{0U};
    std::uint64_t high_id{0U};
    double distance_squared_m2{0.0};
    double radius_squared_m2{0.0};
    bool brute_eligible{false};
    bool lookup_eligible{false};
    bool agreement{false};
    std::optional<double> weight{};
};

[[nodiscard]] std::vector<NeighborAuditRow> neighbor_audit(
    const Configuration& configuration) {
    std::vector<NeighborAuditRow> result;
    const double radius_squared =
        configuration.support_radius_m * configuration.support_radius_m;
    const auto positions = packet_positions(configuration.packets);
    for (const auto& phase : lookup_phases) {
        const auto candidates = lookup_candidate_pairs(
            configuration.packets, configuration.support_radius_m, phase);
        for (std::size_t first = 0U; first < configuration.packets.size(); ++first) {
            for (std::size_t second = first + 1U;
                 second < configuration.packets.size(); ++second) {
                const auto low = configuration.packets[first].id;
                const auto high = configuration.packets[second].id;
                const double distance_squared = safe_squared_distance(
                    positions.at(low), positions.at(high));
                const bool brute = distance_squared > 0.0 &&
                    distance_squared < radius_squared;
                const bool lookup = candidates.contains({low, high}) && brute;
                NeighborAuditRow row{configuration.id, phase.id, low, high,
                    distance_squared, radius_squared, brute, lookup,
                    brute == lookup, std::nullopt};
                if (brute) {
                    const double ratio = distance_squared / radius_squared;
                    row.weight = (1.0 - ratio) * (1.0 - ratio);
                }
                result.push_back(row);
            }
        }
    }
    return result;
}

struct AffineField final {
    std::string name{};
    Matrix3d gradient_per_s{};
    Vec3d intercept_m_per_s{};
};

[[nodiscard]] std::vector<AffineField> affine_fields() {
    Matrix3d rotation{};
    const Vec3d omega{0.3, -0.2, 0.4};
    rotation.value = {{{0.0, -omega.z, omega.y},
                       {omega.z, 0.0, -omega.x},
                       {-omega.y, omega.x, 0.0}}};
    Matrix3d expansion{};
    expansion.value = {{{0.2, 0.0, 0.0},
                        {0.0, 0.2, 0.0},
                        {0.0, 0.0, 0.2}}};
    Matrix3d shear{};
    shear.value = {{{0.0, 0.3, 0.0},
                    {0.3, 0.0, 0.0},
                    {0.0, 0.0, 0.0}}};
    Matrix3d general{};
    general.value = {{{0.2, -0.1, 0.15},
                      {0.25, -0.15, 0.1},
                      {-0.2, 0.125, 0.05}}};
    return {
        {"general_affine", general, {-0.1, 0.2, 0.1}},
        {"infinitesimal_rotation", rotation, {}},
        {"isotropic_expansion", expansion, {}},
        {"pure_shear", shear, {}},
        {"translation", Matrix3d::zero(), {0.2, -0.3, 0.5}},
    };
}

struct BundleTables final {
    Csv configurations{configurations_header};
    Csv packets{packets_header};
    Csv neighbors{neighbor_pairs_header};
    Csv grid_nodes{grid_nodes_header};
    Csv checkpoints{checkpoints_header};
    Csv permutation_controls{permutation_controls_header};
    Csv permutation_entries{permutation_entries_header};
    Csv relations{relations_header};
    Csv operator_status{operator_status_header};
    Csv operator_entries{operator_entries_header};
    Csv moments{moment_diagnostics_header};
    Csv affine{affine_objectivity_header};
    Csv invariance{invariance_header};
    Csv rigid_basis{rigid_basis_header};
    Csv rank_status{rank_status_header};
    Csv nullspace_modes{nullspace_modes_header};
    Csv nullspace_metrics{nullspace_metrics_header};
    Csv grid_gauge{grid_gauge_header};
    Csv exact_reference{exact_reference_header};
};

[[nodiscard]] std::string grouped_payload_digest(
    std::string_view prefix, const Csv& schema,
    const std::vector<Row>& rows) {
    std::string payload(prefix);
    payload.push_back('\n');
    for (const auto& row : rows) {
        if (row.size() != schema.fields().size()) {
            throw std::logic_error("grouped digest row width mismatch");
        }
        for (const auto& field : row) {
            payload.push_back('\0');
            payload += field;
        }
        payload.push_back('\n');
    }
    return sha256(payload);
}

[[nodiscard]] std::string axis_name(std::size_t axis) {
    return axis == 0U ? "x" : (axis == 1U ? "y" : "z");
}

[[nodiscard]] double residual_tolerance(
    std::size_t rows, std::size_t columns,
    double factor = 4096.0) {
    return factor * static_cast<double>(std::max(rows, columns)) * epsilon64;
}

[[nodiscard]] std::vector<double> packet_velocity_vector(
    std::span<const mo::MechanicalPacket> packets) {
    std::vector<mo::MechanicalPacket> canonical(packets.begin(), packets.end());
    std::sort(canonical.begin(), canonical.end(), [](const auto& lhs, const auto& rhs) {
        return lhs.id < rhs.id;
    });
    std::vector<double> result;
    result.reserve(3U * canonical.size());
    for (const auto& packet : canonical) {
        result.push_back(packet.velocity_m_per_s.x);
        result.push_back(packet.velocity_m_per_s.y);
        result.push_back(packet.velocity_m_per_s.z);
    }
    return result;
}

[[nodiscard]] std::vector<double> symmetric_affine_target(
    const Matrix3d& gradient, std::size_t packet_count) {
    constexpr double sqrt_two = 1.414213562373095048801688724209698;
    const std::array<double, 6> components{
        gradient.value[0][0], gradient.value[1][1], gradient.value[2][2],
        (gradient.value[0][1] + gradient.value[1][0]) / sqrt_two,
        (gradient.value[0][2] + gradient.value[2][0]) / sqrt_two,
        (gradient.value[1][2] + gradient.value[2][1]) / sqrt_two};
    std::vector<double> result;
    result.reserve(6U * packet_count);
    for (std::size_t packet = 0U; packet < packet_count; ++packet) {
        result.insert(result.end(), components.begin(), components.end());
    }
    return result;
}

[[nodiscard]] double matrix3_symmetry_residual(const Matrix3d& matrix) {
    std::array<double, 9> difference{};
    std::array<double, 9> entries{};
    std::size_t index = 0U;
    for (std::size_t row = 0U; row < 3U; ++row) {
        for (std::size_t column = 0U; column < 3U; ++column) {
            entries[index] = matrix.value[row][column];
            difference[index] = matrix.value[row][column] -
                matrix.value[column][row];
            ++index;
        }
    }
    return stable_norm(difference) /
        std::max(stable_norm(entries), minimum_normal64);
}

struct OperatorFailureWitness final {
    std::string stage{"NA"};
    std::string reason{"NA"};
    std::string row{"NA"};
    std::string column{"NA"};
    std::string value{"NA"};
    std::string ieee754_bits{"NA"};
    std::string value_class{"NA"};
};

struct OperatorSnapshot final {
    std::string id{};
    std::string configuration_id{};
    std::string candidate{};
    mo::LinearizedOperator linearized{};
    mo::RowNormalization normalization{};
    mo::ObservabilityDiagnostics diagnostics{};
    std::string build_status{"empty"};
    OperatorFailureWitness failure{};
    bool built{false};
    bool raw_exported{false};
    bool b_rank_eligible{false};
    bool generic_solid_gate{false};
    bool decision_driving{false};
    std::vector<std::string> relation_ids{};
};

[[nodiscard]] std::string ieee754_bits_hex(double value) {
    std::ostringstream output;
    output.imbue(std::locale::classic());
    output << std::hex << std::nouppercase << std::setfill('0')
           << std::setw(16) << std::bit_cast<std::uint64_t>(value);
    return output.str();
}

[[nodiscard]] std::string nonfinite_class(double value) {
    if (std::isinf(value)) {
        return std::signbit(value) ? "negative_infinity" : "positive_infinity";
    }
    if (!std::isnan(value)) {
        throw std::invalid_argument("nonfinite class requested for finite value");
    }
    const auto bits = std::bit_cast<std::uint64_t>(value);
    constexpr std::uint64_t quiet_bit = UINT64_C(1) << 51U;
    return (bits & quiet_bit) != 0U ? "quiet_nan" : "signaling_nan";
}

[[nodiscard]] OperatorFailureWitness normalization_failure_witness(
    const mo::RowNormalization& normalization) {
    if (normalization.complete ||
        normalization.first_invalid_row >= normalization.row_norms.size()) {
        throw std::invalid_argument(
            "normalization failure lacks an invalid row witness");
    }
    const double norm_value =
        normalization.row_norms[normalization.first_invalid_row];
    OperatorFailureWitness result{};
    result.stage = "row_normalization";
    result.row = std::to_string(normalization.first_invalid_row);
    result.column = "NA";
    if (norm_value == 0.0) {
        result.reason = "zero_row_norm";
        result.value = "0x0.0p+0";
        result.ieee754_bits = "0000000000000000";
        result.value_class = "finite_zero";
        return result;
    }
    if (!std::isfinite(norm_value)) {
        result.reason = "nonfinite_row_norm";
        result.value = "NA";
        result.ieee754_bits = ieee754_bits_hex(norm_value);
        result.value_class = nonfinite_class(norm_value);
        return result;
    }
    throw std::logic_error(
        "row normalization rejected a finite positive row norm");
}

[[nodiscard]] std::optional<std::tuple<std::size_t, std::size_t, double>>
first_nonfinite_entry(const mo::DenseMatrix& matrix) {
    for (std::size_t row = 0U; row < matrix.row_count(); ++row) {
        for (std::size_t column = 0U; column < matrix.column_count(); ++column) {
            const double value = matrix(row, column);
            if (!std::isfinite(value)) {
                return std::tuple{row, column, value};
            }
        }
    }
    return std::nullopt;
}

[[nodiscard]] std::vector<std::string> bond_relation_ids(
    const Configuration& configuration) {
    std::vector<std::string> result;
    for (const auto& relation : configuration.edges) {
        if (relation.retained) {
            result.push_back(relation.id);
        }
    }
    return result;
}

[[nodiscard]] std::vector<std::string> volume_relation_ids(
    const Configuration& configuration) {
    std::vector<std::string> result;
    for (const auto& relation : configuration.volumes) {
        result.push_back("volume." + std::to_string(relation.center_id) + "." +
            std::to_string(relation.other_ids[0]) + "." +
            std::to_string(relation.other_ids[1]) + "." +
            std::to_string(relation.other_ids[2]));
    }
    return result;
}

[[nodiscard]] Row operator_entry_row(
    std::string_view operator_id, std::size_t row_index,
    std::size_t column_index, std::string domain_kind,
    std::string domain_id, std::string velocity_component,
    std::string row_kind, std::string row_owner_id,
    std::string row_component, double value, std::string units) {
    return {std::string(operator_id), std::to_string(row_index),
        std::to_string(column_index), std::move(domain_kind),
        std::move(domain_id), std::move(velocity_component),
        std::move(row_kind), std::move(row_owner_id),
        std::move(row_component), hex64(value), std::move(units)};
}

[[nodiscard]] std::vector<Row> packet_operator_entries(
    std::string_view operator_id, std::string_view candidate,
    const mo::LinearizedOperator& linearized,
    std::span<const std::string> relation_ids,
    std::size_t bond_row_count = 0U) {
    std::vector<Row> result;
    constexpr std::array<std::string_view, 6> symmetric_components{
        "xx", "yy", "zz", "xy", "xz", "yz"};
    for (std::size_t row = 0U; row < linearized.matrix.row_count(); ++row) {
        std::string row_kind;
        std::string owner;
        std::string row_component;
        std::string units;
        if (candidate == "B") {
            row_kind = "symmetric_gradient";
            owner = std::to_string(linearized.packet_ids[row / 6U]);
            row_component = std::string(symmetric_components[row % 6U]);
            units = "per_m";
        } else if (candidate == "C") {
            row_kind = "bond_length_rate";
            if (row >= relation_ids.size()) {
                throw std::out_of_range("candidate C relation-row lookup");
            }
            owner = relation_ids[row];
            row_component = "length";
            units = "one";
        } else {
            const bool bond = row < bond_row_count;
            row_kind = bond ? "bond_length_rate" : "oriented_volume_rate";
            if (row >= relation_ids.size()) {
                throw std::out_of_range("candidate D relation-row lookup");
            }
            owner = relation_ids[row];
            row_component = bond ? "length" : "volume";
            units = bond ? "one" : "m2";
        }
        for (std::size_t column = 0U;
             column < linearized.matrix.column_count(); ++column) {
            const double value = linearized.matrix(row, column);
            if (value == 0.0) {
                continue;
            }
            result.push_back(operator_entry_row(
                operator_id, row, column, "packet",
                std::to_string(linearized.packet_ids[column / 3U]),
                axis_name(column % 3U), row_kind, owner, row_component,
                value, units));
        }
    }
    return result;
}

void append_rows(Csv& table, const std::vector<Row>& rows) {
    for (const auto& row : rows) {
        table.row(row);
    }
}

[[nodiscard]] double normalized_image_residual(
    const mo::DenseMatrix& matrix, std::span<const double> vector,
    double& image_norm, double& denominator) {
    const auto image = matrix_vector(matrix, vector);
    image_norm = stable_norm(image);
    denominator = matrix_frobenius(matrix) * stable_norm(vector);
    return denominator == 0.0
        ? (image_norm == 0.0 ? 0.0 : std::numeric_limits<double>::infinity())
        : image_norm / denominator;
}

[[nodiscard]] double rigid_projection_norm(
    const mo::DenseMatrix& rigid_basis, std::span<const double> vector) {
    std::vector<double> coefficients(rigid_basis.column_count(), 0.0);
    for (std::size_t column = 0U; column < rigid_basis.column_count(); ++column) {
        long double value = 0.0L;
        for (std::size_t row = 0U; row < rigid_basis.row_count(); ++row) {
            value += static_cast<long double>(rigid_basis(row, column)) *
                vector[row];
        }
        coefficients[column] = static_cast<double>(value);
    }
    return stable_norm(coefficients);
}

void emit_basis(
    Csv& table, std::string_view operator_id, std::string_view kind,
    const mo::DenseMatrix& basis, std::span<const std::uint64_t> packet_ids) {
    for (std::size_t mode = 0U; mode < basis.column_count(); ++mode) {
        for (std::size_t dof = 0U; dof < basis.row_count(); ++dof) {
            table.row({std::string(operator_id), std::string(kind),
                std::to_string(mode), std::to_string(dof), "packet",
                std::to_string(packet_ids[dof / 3U]), axis_name(dof % 3U),
                hex64(basis(dof, mode))});
        }
    }
}

struct RankEvidenceDisposition final {
    std::string status{};
    std::string failure_stage{"NA"};
    std::string failure_reason{"NA"};
    bool basis_failure{false};
};

[[nodiscard]] bool finite_matrix(const mo::DenseMatrix& matrix) {
    return std::ranges::all_of(
        matrix.entries(), [](double value) { return std::isfinite(value); });
}

[[nodiscard]] RankEvidenceDisposition rank_evidence_disposition(
    const mo::ObservabilityDiagnostics& diagnostics) {
    const bool core_nonfinite =
        !finite_matrix(diagnostics.operator_rank.nullspace_basis) ||
        !finite_matrix(diagnostics.rigid.orthonormal_basis) ||
        !std::isfinite(diagnostics.operator_rank.normalized_null_residual) ||
        !std::isfinite(diagnostics.normalized_rigid_residual);
    const bool quotient_nonfinite = diagnostics.rigid_subspace_in_kernel &&
        (!finite_matrix(diagnostics.nonrigid_nullspace_basis) ||
         !std::isfinite(diagnostics.normalized_nonrigid_residual) ||
         !std::isfinite(diagnostics.rigid_orthogonality_residual));
    const bool nonfinite = core_nonfinite || quotient_nonfinite;
    if (diagnostics.status == mo::RankStatus::ambiguous) {
        return {"ambiguous", "rank_estimation",
            "ambiguity_band_overlap", true};
    }
    if (diagnostics.status == mo::RankStatus::analyzed && !nonfinite &&
        diagnostics.operator_rank.basis_complete &&
        (!diagnostics.rigid_subspace_in_kernel ||
         diagnostics.nonrigid_nullspace_basis.column_count() ==
            diagnostics.nonrigid_nullity)) {
        return {"analyzed", "NA", "NA", false};
    }
    RankEvidenceDisposition result{"numerical_failure",
        "basis_construction", "nonrigid_quotient_failure", true};
    if (nonfinite) {
        result.failure_reason = "nonfinite_basis";
    } else if (!diagnostics.operator_rank.basis_complete) {
        result.failure_reason = "incomplete_kernel";
    } else if (!diagnostics.rigid_subspace_in_kernel) {
        result.failure_reason = "rigid_span_failure";
    }
    if (diagnostics.status != mo::RankStatus::analyzed &&
        diagnostics.status != mo::RankStatus::numerical_failure) {
        throw std::logic_error(
            "rank failure has no closed evidence disposition");
    }
    return result;
}

[[nodiscard]] bool resolved_packet_rank_contract(
    const mo::LinearizedOperator& linearized,
    const mo::RowNormalization& normalization,
    const mo::ObservabilityDiagnostics& diagnostics) {
    if (!normalization.complete ||
        diagnostics.status != mo::RankStatus::analyzed) {
        return false;
    }
    const auto disposition = rank_evidence_disposition(diagnostics);
    const double tolerance = residual_tolerance(
        linearized.matrix.row_count(), linearized.matrix.column_count());
    if (disposition.status != "analyzed" || disposition.basis_failure ||
        !diagnostics.operator_rank.basis_complete ||
        !diagnostics.rigid_subspace_in_kernel ||
        diagnostics.nonrigid_nullspace_basis.column_count() !=
            diagnostics.nonrigid_nullity ||
        !std::isfinite(diagnostics.normalized_rigid_residual) ||
        diagnostics.normalized_rigid_residual > tolerance ||
        !std::isfinite(diagnostics.operator_rank.normalized_null_residual) ||
        diagnostics.operator_rank.normalized_null_residual > tolerance ||
        !std::isfinite(diagnostics.normalized_nonrigid_residual) ||
        diagnostics.normalized_nonrigid_residual > tolerance ||
        !std::isfinite(diagnostics.rigid_orthogonality_residual) ||
        diagnostics.rigid_orthogonality_residual > tolerance) {
        return false;
    }
    const auto modes_pass = [&](const mo::DenseMatrix& basis,
                                bool require_rigid_orthogonality) {
        for (std::size_t mode = 0U; mode < basis.column_count(); ++mode) {
            const auto vector = matrix_column(basis, mode);
            double image_norm = 0.0;
            double denominator = 0.0;
            const double normalized = normalized_image_residual(
                normalization.normalized, vector, image_norm, denominator);
            const double projection = require_rigid_orthogonality
                ? rigid_projection_norm(
                    diagnostics.rigid.orthonormal_basis, vector)
                : 0.0;
            if (!std::isfinite(normalized) || normalized > tolerance ||
                !std::isfinite(projection) ||
                (require_rigid_orthogonality && projection > tolerance)) {
                return false;
            }
        }
        return true;
    };
    return modes_pass(
               diagnostics.operator_rank.nullspace_basis, false) &&
        modes_pass(diagnostics.nonrigid_nullspace_basis, true);
}

[[nodiscard]] bool decisive_rank_contract_pass(
    const OperatorSnapshot& snapshot) {
    const bool required = snapshot.candidate == "C" ||
        snapshot.decision_driving;
    if (!required) {
        return true;
    }
    return snapshot.built && resolved_packet_rank_contract(
        snapshot.linearized, snapshot.normalization, snapshot.diagnostics);
}

void emit_rank_evidence(
    BundleTables& tables, const OperatorSnapshot& snapshot) {
    const auto& diagnostics = snapshot.diagnostics;
    const auto& rank = diagnostics.operator_rank;
    const double tolerance = residual_tolerance(
        snapshot.linearized.matrix.row_count(),
        snapshot.linearized.matrix.column_count());
    const auto disposition = rank_evidence_disposition(diagnostics);
    const bool ambiguous = disposition.status == "ambiguous";
    const bool generic_pass = snapshot.generic_solid_gate &&
        disposition.status == "analyzed" &&
        diagnostics.kernel_equals_rigid_subspace;
    const auto common = [&](std::string record_kind, std::string pivot_step,
                            std::string permuted_column,
                            std::string diagonal, std::string accepted) {
        return Row{snapshot.id, std::move(record_kind), std::move(pivot_step),
            std::move(permuted_column), std::move(diagonal),
            std::move(accepted), disposition.status,
            std::to_string(rank.row_count), std::to_string(rank.column_count),
            std::to_string(rank.rank), std::to_string(rank.nullity),
            std::to_string(diagnostics.rigid.rank),
            !disposition.basis_failure && diagnostics.rigid_subspace_in_kernel
                ? std::to_string(diagnostics.nonrigid_nullity) : "NA",
            hex64(rank.threshold),
            hex64(rank.ambiguity_lower), hex64(rank.ambiguity_upper),
            bool_text(ambiguous),
            "binary64_householder_qrcp_threshold_estimate",
            bool_text(rank.rank_is_certified && !disposition.basis_failure),
            bool_text(rank.basis_complete && !disposition.basis_failure),
            disposition.basis_failure ? "NA" :
                bool_text(diagnostics.rigid_subspace_in_kernel),
            disposition.basis_failure ? "NA" :
                bool_text(diagnostics.kernel_equals_rigid_subspace),
            disposition.basis_failure ? "NA" :
                hex64(diagnostics.normalized_rigid_residual),
            disposition.basis_failure ? "NA" :
                hex64(rank.normalized_null_residual),
            disposition.basis_failure ||
                    !diagnostics.rigid_subspace_in_kernel ? "NA" :
                hex64(diagnostics.normalized_nonrigid_residual),
            disposition.basis_failure ||
                    !diagnostics.rigid_subspace_in_kernel ? "NA" :
                hex64(diagnostics.rigid_orthogonality_residual),
            hex64(tolerance), disposition.basis_failure ? "NA" :
                bool_text(generic_pass), "false", disposition.failure_stage,
            disposition.failure_reason};
    };
    tables.rank_status.row(common("summary", "NA", "NA", "NA", "NA"));
    for (std::size_t step = 0U; step < rank.column_permutation.size(); ++step) {
        const double diagonal = step < rank.diagonal_magnitudes.size()
            ? rank.diagonal_magnitudes[step] : 0.0;
        tables.rank_status.row(common(
            "pivot", std::to_string(step),
            std::to_string(rank.column_permutation.at(step)),
            hex64(diagonal), bool_text(diagonal > rank.threshold)));
    }

    emit_basis(tables.rigid_basis, snapshot.id, "raw_generator",
        diagnostics.rigid.generators, snapshot.linearized.packet_ids);
    if (disposition.basis_failure) {
        return;
    }
    emit_basis(tables.rigid_basis, snapshot.id, "orthonormal",
        diagnostics.rigid.orthonormal_basis, snapshot.linearized.packet_ids);
    emit_basis(tables.nullspace_modes, snapshot.id, "complete_kernel",
        rank.nullspace_basis, snapshot.linearized.packet_ids);
    if (diagnostics.rigid_subspace_in_kernel) {
        emit_basis(tables.nullspace_modes, snapshot.id, "nonrigid",
            diagnostics.nonrigid_nullspace_basis,
            snapshot.linearized.packet_ids);
    }

    const auto emit_metrics = [&](std::string_view kind,
                                  const mo::DenseMatrix& basis) {
        for (std::size_t mode = 0U; mode < basis.column_count(); ++mode) {
            const auto vector = matrix_column(basis, mode);
            double image_norm = 0.0;
            double denominator = 0.0;
            const double normalized = normalized_image_residual(
                snapshot.normalization.normalized, vector, image_norm,
                denominator);
            const double projection = rigid_projection_norm(
                diagnostics.rigid.orthonormal_basis, vector);
            const double orthogonality = kind == "nonrigid" ? projection : 0.0;
            const bool pass = std::isfinite(normalized) &&
                normalized <= tolerance && std::isfinite(orthogonality) &&
                (kind != "nonrigid" || orthogonality <= tolerance);
            tables.nullspace_metrics.row({snapshot.id, std::string(kind),
                std::to_string(mode), hex64(image_norm), hex64(denominator),
                hex64(normalized), hex64(projection), hex64(orthogonality),
                hex64(tolerance), bool_text(pass), "false"});
        }
    };
    emit_metrics("complete_kernel", rank.nullspace_basis);
    if (diagnostics.rigid_subspace_in_kernel) {
        emit_metrics("nonrigid", diagnostics.nonrigid_nullspace_basis);
    }
}

void emit_moment_evidence(
    BundleTables& tables, std::string_view operator_id,
    const mo::CorrectedGradientOperator& corrected) {
    for (const auto& diagnostic : corrected.local_moments) {
        Row row{std::string(operator_id), std::to_string(diagnostic.packet_id),
            std::to_string(diagnostic.neighbor_count)};
        for (std::size_t matrix_row = 0U; matrix_row < 3U; ++matrix_row) {
            for (std::size_t matrix_column = 0U; matrix_column < 3U;
                 ++matrix_column) {
                row.push_back(hex64(
                    diagnostic.moment_m2.value[matrix_row][matrix_column]));
            }
        }
        row.push_back(hex64(matrix3_symmetry_residual(diagnostic.moment_m2)));
        row.push_back(hex64(diagnostic.smallest_eigenvalue_m2));
        row.push_back(hex64(diagnostic.largest_eigenvalue_m2));
        row.push_back(std::isfinite(diagnostic.condition_number)
            ? hex64(diagnostic.condition_number) : "NA");
        row.push_back("dense_symmetric_eigen_estimate");
        row.push_back(std::isfinite(diagnostic.inverse_residual_normalized)
            ? hex64(diagnostic.inverse_residual_normalized) : "NA");
        row.push_back(hex64(diagnostic.inverse_residual_tolerance));
        row.push_back(std::string(mo::status_name(diagnostic.status)));
        row.push_back(bool_text(diagnostic.inverse_accepted));
        tables.moments.row(std::move(row));
    }
}

[[nodiscard]] OperatorFailureWitness local_moment_failure_witness(
    std::string_view build_status,
    const mo::CorrectedGradientOperator& corrected) {
    for (const auto& diagnostic : corrected.local_moments) {
        if (mo::status_name(diagnostic.status) == build_status) {
            return {"local_moment", std::string(build_status),
                std::to_string(diagnostic.packet_id), "NA", "NA", "NA",
                "moment_diagnostics"};
        }
    }
    throw std::logic_error(
        "B aggregate failure lacks matching local-moment witness");
}

[[nodiscard]] std::vector<double> expected_affine_target(
    std::string_view candidate, const Configuration& configuration,
    const Matrix3d& gradient) {
    if (candidate == "B") {
        return symmetric_affine_target(gradient, configuration.packets.size());
    }
    const auto bonds = retained_bonds(configuration);
    auto result = mo::expected_affine_bond_rates_m_per_s(
        configuration.packets, bonds, gradient);
    if (candidate == "D") {
        const auto volumes = mo::expected_affine_volume_rates_m3_per_s(
            configuration.packets, configuration.volumes, gradient);
        result.insert(result.end(), volumes.begin(), volumes.end());
    }
    return result;
}

struct AffineAggregate final {
    double measured_norm{0.0};
    double target_norm{0.0};
    double absolute_error{0.0};
    double normalization{0.0};
    double normalized_error{0.0};
    double bound{0.0};
    bool pass{false};
};

[[nodiscard]] AffineAggregate affine_aggregate_block(
    const mo::DenseMatrix& matrix, std::span<const double> measured,
    std::span<const double> target, std::span<const double> velocity,
    std::size_t first_row, std::size_t row_count) {
    if (measured.size() != matrix.row_count() ||
        target.size() != matrix.row_count() ||
        velocity.size() != matrix.column_count() ||
        first_row > matrix.row_count() ||
        row_count > matrix.row_count() - first_row || row_count == 0U) {
        throw std::invalid_argument("invalid affine aggregate row block");
    }
    const auto measured_block = measured.subspan(first_row, row_count);
    const auto target_block = target.subspan(first_row, row_count);
    std::vector<double> difference(row_count, 0.0);
    std::vector<double> matrix_entries;
    matrix_entries.reserve(row_count * matrix.column_count());
    for (std::size_t row = 0U; row < row_count; ++row) {
        difference[row] = measured_block[row] - target_block[row];
        for (std::size_t column = 0U; column < matrix.column_count(); ++column) {
            matrix_entries.push_back(matrix(first_row + row, column));
        }
    }
    AffineAggregate result{};
    result.measured_norm = stable_norm(measured_block);
    result.target_norm = stable_norm(target_block);
    result.absolute_error = stable_norm(difference);
    result.normalization = std::max(
        stable_norm(matrix_entries) * stable_norm(velocity) +
            result.target_norm,
        minimum_normal64);
    result.normalized_error = result.absolute_error / result.normalization;
    result.bound = residual_tolerance(row_count, matrix.column_count());
    result.pass = std::isfinite(result.normalized_error) &&
        result.normalized_error <= result.bound;
    return result;
}

[[nodiscard]] bool emit_affine_evidence(
    BundleTables& tables, const OperatorSnapshot& snapshot,
    const Configuration& configuration,
    const mo::CorrectedGradientOperator* corrected) {
    bool all_pass = true;
    for (const auto& field : affine_fields()) {
        const auto packets = mo::with_affine_velocity(
            configuration.packets, field.gradient_per_s,
            field.intercept_m_per_s);
        const auto measured = mo::apply_operator(snapshot.linearized, packets);
        const auto target = expected_affine_target(
            snapshot.candidate, configuration, field.gradient_per_s);
        const auto velocity = packet_velocity_vector(packets);
        const double bound = residual_tolerance(
            snapshot.linearized.matrix.row_count(),
            snapshot.linearized.matrix.column_count());
        const auto emit_aggregate = [&](std::size_t first_row,
                                        std::size_t row_count,
                                        std::string id_suffix,
                                        std::string component,
                                        std::string units) {
            const auto aggregate = affine_aggregate_block(
                snapshot.linearized.matrix, measured, target, velocity,
                first_row, row_count);
            all_pass = all_pass && aggregate.pass;
            tables.affine.row({snapshot.id,
                "affine:" + field.name + ":" + id_suffix,
                "linear_operator_aggregate", field.name, "NA", "NA",
                std::move(component), hex64(aggregate.measured_norm),
                hex64(aggregate.target_norm), hex64(aggregate.absolute_error),
                hex64(aggregate.normalization),
                hex64(aggregate.normalized_error), "0",
                hex64(aggregate.bound), bool_text(aggregate.pass),
                std::move(units)});
        };
        if (snapshot.candidate == "D") {
            const std::size_t bond_rows = retained_bonds(configuration).size();
            const std::size_t volume_rows = configuration.volumes.size();
            if (bond_rows > 0U) {
                emit_aggregate(0U, bond_rows, "bond_aggregate", "BOND_ALL",
                    "m_per_s");
            }
            if (volume_rows > 0U) {
                emit_aggregate(bond_rows, volume_rows, "volume_aggregate",
                    "VOLUME_ALL", "m3_per_s");
            }
            if (bond_rows + volume_rows !=
                snapshot.linearized.matrix.row_count()) {
                throw std::logic_error(
                    "D affine row blocks do not cover the operator");
            }
        } else {
            emit_aggregate(0U, snapshot.linearized.matrix.row_count(),
                "aggregate", "ALL",
                snapshot.candidate == "B" ? "per_s" : "m_per_s");
        }

        if (snapshot.candidate == "B" && corrected != nullptr) {
            const auto gradients =
                mo::evaluate_full_local_gradients(*corrected, packets);
            for (std::size_t packet = 0U; packet < gradients.size(); ++packet) {
                for (std::size_t row = 0U; row < 3U; ++row) {
                    for (std::size_t column = 0U; column < 3U; ++column) {
                        const double actual = gradients[packet].value[row][column];
                        const double expected = field.gradient_per_s.value[row][column];
                        const double error = std::abs(actual - expected);
                        const double scale = std::max(
                            {1.0, std::abs(actual), std::abs(expected)});
                        const double relative = error / scale;
                        const bool detail_pass = std::isfinite(relative) &&
                            relative <= bound;
                        all_pass = all_pass && detail_pass;
                        tables.affine.row({snapshot.id,
                            "affine:" + field.name + ":full_gradient:" +
                                std::to_string(configuration.packets[packet].id) +
                                ":" + std::to_string(row) + std::to_string(column),
                            "full_gradient_reproduction", field.name,
                            std::to_string(configuration.packets[packet].id),
                            "NA", std::to_string(row) + std::to_string(column),
                            hex64(actual), hex64(expected), hex64(error),
                            hex64(scale), hex64(relative), "0", hex64(bound),
                            bool_text(detail_pass), "per_s"});
                    }
                }
            }
        }
    }
    return all_pass;
}

[[nodiscard]] double oriented_volume(
    const std::map<std::uint64_t, Vec3d>& positions,
    const mo::VolumeRelation& relation) {
    const Vec3d a = positions.at(relation.other_ids[0]) -
        positions.at(relation.center_id);
    const Vec3d b = positions.at(relation.other_ids[1]) -
        positions.at(relation.center_id);
    const Vec3d c = positions.at(relation.other_ids[2]) -
        positions.at(relation.center_id);
    return mls::experimental::dot(a, mls::experimental::cross(b, c));
}

constexpr std::size_t finite_bond_operation_count = 72U;
constexpr std::size_t finite_volume_operation_count = 134U;

[[nodiscard]] Vec3d transform_coordinate_operand_scale(
    Vec3d point, const Matrix3d& rotation, Vec3d translation,
    double scale) {
    const double scale_magnitude = std::abs(scale);
    const std::array<double, 3> coordinates{point.x, point.y, point.z};
    const std::array<double, 3> translations{
        translation.x, translation.y, translation.z};
    std::array<double, 3> result{};
    for (std::size_t axis = 0U; axis < 3U; ++axis) {
        const double inner =
            (std::abs(rotation.value[axis][0] * coordinates[0]) +
             std::abs(rotation.value[axis][1] * coordinates[1])) +
            std::abs(rotation.value[axis][2] * coordinates[2]);
        result[axis] = scale_magnitude * inner +
            std::abs(translations[axis]);
        if (!std::isfinite(result[axis])) {
            throw std::overflow_error(
                "finite-objectivity coordinate operand scale overflow");
        }
    }
    return {result[0], result[1], result[2]};
}

[[nodiscard]] Vec3d coordinate_cancellation_scale(
    Vec3d first, Vec3d second) {
    const Vec3d result{std::abs(first.x) + std::abs(second.x),
        std::abs(first.y) + std::abs(second.y),
        std::abs(first.z) + std::abs(second.z)};
    if (!std::isfinite(result.x) || !std::isfinite(result.y) ||
        !std::isfinite(result.z)) {
        throw std::overflow_error(
            "finite-objectivity cancellation scale overflow");
    }
    return result;
}

[[nodiscard]] double component_sum(Vec3d value) {
    const double result = (value.x + value.y) + value.z;
    if (!std::isfinite(result) || result < 0.0) {
        throw std::overflow_error(
            "finite-objectivity component scale overflow");
    }
    return result;
}

[[nodiscard]] double determinant_operand_envelope(
    Vec3d a, Vec3d b, Vec3d c) {
    const double first = a.x * (b.y * c.z + b.z * c.y);
    const double second = a.y * (b.x * c.z + b.z * c.x);
    const double third = a.z * (b.x * c.y + b.y * c.x);
    const double result = (first + second) + third;
    if (!std::isfinite(result) || result < 0.0) {
        throw std::overflow_error(
            "finite-objectivity determinant scale overflow");
    }
    return result;
}

[[nodiscard]] double finite_bond_operand_scale(
    const std::map<std::uint64_t, Vec3d>& reference_positions,
    const mo::BondRelation& bond, const Matrix3d& rotation,
    Vec3d translation, double scale, double measured, double target) {
    const Vec3d first = reference_positions.at(bond.first_id);
    const Vec3d second = reference_positions.at(bond.second_id);
    const Vec3d reference = coordinate_cancellation_scale(first, second);
    const Vec3d transformed =
        transform_coordinate_operand_scale(first, rotation, translation, scale) +
        transform_coordinate_operand_scale(second, rotation, translation, scale);
    double result = std::abs(scale) * component_sum(reference);
    result += component_sum(transformed);
    result += std::abs(measured);
    result += std::abs(target);
    if (!std::isfinite(result)) {
        throw std::overflow_error(
            "finite-objectivity bond operand scale overflow");
    }
    return std::max(result, minimum_normal64);
}

[[nodiscard]] double finite_volume_operand_scale(
    const std::map<std::uint64_t, Vec3d>& reference_positions,
    const mo::VolumeRelation& relation, const Matrix3d& rotation,
    Vec3d translation, double scale, double measured, double target) {
    const Vec3d center = reference_positions.at(relation.center_id);
    std::array<Vec3d, 3> reference{};
    std::array<Vec3d, 3> transformed{};
    const Vec3d center_transform = transform_coordinate_operand_scale(
        center, rotation, translation, scale);
    for (std::size_t index = 0U; index < relation.other_ids.size(); ++index) {
        const Vec3d site = reference_positions.at(relation.other_ids[index]);
        reference[index] = coordinate_cancellation_scale(site, center);
        transformed[index] = transform_coordinate_operand_scale(
            site, rotation, translation, scale) + center_transform;
    }
    const double scale_magnitude = std::abs(scale);
    double result = ((scale_magnitude * scale_magnitude) * scale_magnitude) *
        determinant_operand_envelope(
            reference[0], reference[1], reference[2]);
    result += determinant_operand_envelope(
        transformed[0], transformed[1], transformed[2]);
    result += std::abs(measured);
    result += std::abs(target);
    if (!std::isfinite(result)) {
        throw std::overflow_error(
            "finite-objectivity volume operand scale overflow");
    }
    return std::max(result, minimum_normal64);
}

[[nodiscard]] double gamma_n(std::size_t operations) {
    const double product = static_cast<double>(operations) * epsilon64;
    if (!(product < 1.0)) {
        throw std::overflow_error("finite-objectivity operation count invalid");
    }
    return product / (1.0 - product);
}

[[nodiscard]] bool emit_finite_evidence(
    BundleTables& tables, const OperatorSnapshot& snapshot,
    const Configuration& configuration) {
    struct Transform final {
        std::string name{};
        Matrix3d rotation{};
        Vec3d translation{};
        double scale{1.0};
        bool scale_covariance{false};
    };
    const std::array transforms{
        Transform{"proper_quaternion_rotation", rational_quaternion_rotation(), {}, 1.0, false},
        Transform{"signed_axis_rotation", signed_axis_rotation(), {}, 1.0, false},
        Transform{"translation", Matrix3d::identity(), {0.13, -0.07, 0.21}, 1.0, false},
        Transform{"scale_half", Matrix3d::identity(), {}, 0.5, true},
        Transform{"scale_double", Matrix3d::identity(), {}, 2.0, true},
    };
    const auto bonds = retained_bonds(configuration);
    const auto bond_ids = bond_relation_ids(configuration);
    const auto volume_ids = volume_relation_ids(configuration);
    const auto reference_positions = packet_positions(configuration.packets);
    bool all_pass = true;
    for (const auto& transform : transforms) {
        const auto transformed_packets = mo::similarity_transform_packets(
            configuration.packets, transform.rotation,
            transform.translation, transform.scale);
        const auto transformed_positions = packet_positions(transformed_packets);
        for (std::size_t index = 0U; index < bonds.size(); ++index) {
            const auto& bond = bonds[index];
            const double reference = std::sqrt(safe_squared_distance(
                reference_positions.at(bond.first_id),
                reference_positions.at(bond.second_id)));
            const double measured = std::sqrt(safe_squared_distance(
                transformed_positions.at(bond.first_id),
                transformed_positions.at(bond.second_id)));
            const double target = transform.scale * reference;
            const double error = std::abs(measured - target);
            constexpr std::size_t operation_count =
                finite_bond_operation_count;
            const double magnitude_scale = finite_bond_operand_scale(
                reference_positions, bond, transform.rotation,
                transform.translation, transform.scale, measured, target);
            const double bound = 256.0 * gamma_n(operation_count) *
                    magnitude_scale + 256.0 * minimum_normal64;
            const double normalized = error / magnitude_scale;
            const bool pass = std::isfinite(error) && error <= bound;
            all_pass = all_pass && pass;
            tables.affine.row({snapshot.id,
                "finite:" + transform.name + ":" + bond_ids[index],
                "finite_bond_length",
                transform.name, "NA", bond_ids[index], "length",
                hex64(measured), hex64(target), hex64(error),
                hex64(magnitude_scale), hex64(normalized),
                std::to_string(operation_count), hex64(bound),
                bool_text(pass), "m"});
        }
        if (snapshot.candidate != "D") {
            continue;
        }
        for (std::size_t index = 0U;
             index < configuration.volumes.size(); ++index) {
            const auto& relation = configuration.volumes[index];
            const double reference = oriented_volume(
                reference_positions, relation);
            const double measured = oriented_volume(
                transformed_positions, relation);
            const double target = transform.scale * transform.scale *
                transform.scale * reference;
            const double error = std::abs(measured - target);
            constexpr std::size_t operation_count =
                finite_volume_operation_count;
            const double magnitude_scale = finite_volume_operand_scale(
                reference_positions, relation, transform.rotation,
                transform.translation, transform.scale, measured, target);
            const double bound = 256.0 * gamma_n(operation_count) *
                    magnitude_scale + 256.0 * minimum_normal64;
            const double normalized = error / magnitude_scale;
            const bool pass = std::isfinite(error) && error <= bound;
            all_pass = all_pass && pass;
            tables.affine.row({snapshot.id,
                "finite:" + transform.name + ":" + volume_ids[index],
                "finite_oriented_volume",
                transform.name, "NA", volume_ids[index], "volume",
                hex64(measured), hex64(target), hex64(error),
                hex64(magnitude_scale), hex64(normalized),
                std::to_string(operation_count), hex64(bound),
                bool_text(pass), "m3"});
        }
    }
    return all_pass;
}

struct EmissionState final {
    bool affine_all_pass{true};
    bool finite_all_pass{true};
    bool raw_decision_all_exported{true};
    bool decisive_ranks_unambiguous{true};
    std::map<std::string, OperatorSnapshot> snapshots{};
    std::map<std::string, bool> permutation_matches{};
};

[[nodiscard]] OperatorSnapshot emit_packet_operator(
    BundleTables& tables, EmissionState& emission,
    const Configuration& configuration, const TopologyFacts& facts,
    std::string candidate, std::string role, std::string build_status,
    mo::LinearizedOperator linearized,
    std::vector<std::string> relation_ids, std::size_t bond_row_count,
    const mo::CorrectedGradientOperator* corrected = nullptr) {
    OperatorSnapshot snapshot{};
    snapshot.id = configuration.id + "." + candidate;
    snapshot.configuration_id = configuration.id;
    snapshot.candidate = candidate;
    snapshot.linearized = std::move(linearized);
    snapshot.generic_solid_gate = facts.generic_solid_gate;
    snapshot.relation_ids = std::move(relation_ids);
    snapshot.build_status = build_status;
    const bool attempted = build_status != "not_triggered";
    snapshot.decision_driving = attempted &&
        (candidate == "C" ||
         ((candidate == "B" || candidate == "D") &&
          facts.generic_solid_gate));
    const bool constructed = build_status == "built" &&
        snapshot.linearized.matrix.row_count() > 0U &&
        snapshot.linearized.matrix.column_count() > 0U;
    std::vector<Row> entries;
    if (constructed) {
        const auto nonfinite = first_nonfinite_entry(
            snapshot.linearized.matrix);
        if (nonfinite.has_value()) {
            if (candidate == "B") {
                throw std::logic_error(
                    "B constructed a nonfinite operator without a moment failure");
            }
            const auto [row, column, value] = *nonfinite;
            snapshot.build_status = "numerical_failure";
            snapshot.failure = {"operator_construction",
                "nonfinite_operator_cell", std::to_string(row),
                std::to_string(column), "NA", ieee754_bits_hex(value),
                nonfinite_class(value)};
        } else {
            snapshot.raw_exported = true;
        }
    }
    if (snapshot.raw_exported) {
        entries = packet_operator_entries(snapshot.id, candidate,
            snapshot.linearized, snapshot.relation_ids, bond_row_count);
        append_rows(tables.operator_entries, entries);
        snapshot.normalization =
            mo::normalize_operator_rows(snapshot.linearized.matrix);
        if (!snapshot.normalization.complete) {
            if (candidate == "B") {
                throw std::logic_error(
                    "B row normalization failed after accepted local moments");
            }
            snapshot.build_status = "numerical_failure";
            snapshot.failure =
                normalization_failure_witness(snapshot.normalization);
        } else {
            snapshot.built = true;
        }
    }
    if (!constructed) {
        if (candidate == "B" && corrected != nullptr &&
            (build_status == "singular_local_moment" ||
             build_status == "ill_conditioned_local_moment" ||
             build_status == "numerical_failure")) {
            snapshot.failure =
                local_moment_failure_witness(build_status, *corrected);
        } else if (candidate == "D" && build_status == "not_triggered") {
            snapshot.failure = {"not_attempted", "global_d_not_triggered",
                "NA", "NA", "NA", "NA", "none"};
            snapshot.decision_driving = false;
        } else {
            throw std::logic_error(
                "registered operator has unsupported construction status");
        }
    }
    snapshot.b_rank_eligible = candidate == "B" && snapshot.built;
    if (snapshot.built) {
        snapshot.diagnostics = mo::diagnose_mechanical_observability(
            snapshot.linearized, configuration.packets);
        emit_rank_evidence(tables, snapshot);
        const bool affine_pass = emit_affine_evidence(
            tables, snapshot, configuration, corrected);
        if (candidate == "C" || snapshot.decision_driving) {
            emission.affine_all_pass =
                affine_pass && emission.affine_all_pass;
        }
        if (candidate == "C" || candidate == "D") {
            const bool finite_pass = emit_finite_evidence(
                tables, snapshot, configuration);
            if (candidate == "C" || snapshot.decision_driving) {
                emission.finite_all_pass =
                    finite_pass && emission.finite_all_pass;
            }
        }
    }
    emission.decisive_ranks_unambiguous =
        decisive_rank_contract_pass(snapshot) &&
        emission.decisive_ranks_unambiguous;
    if (candidate == "B" && corrected != nullptr) {
        emit_moment_evidence(tables, snapshot.id, *corrected);
    }
    if (snapshot.decision_driving && !snapshot.raw_exported) {
        emission.raw_decision_all_exported = false;
    }
    const std::string digest = snapshot.raw_exported
        ? grouped_payload_digest(
            "MLS-MECHANICAL-OBSERVABILITY-OPERATOR-v1",
            tables.operator_entries, entries)
        : "NA";
    const std::string observable = candidate == "B"
        ? "corrected_local_symmetric_gradient"
        : (candidate == "C" ? "central_bond_length_rate" :
            (snapshot.built
                ? std::string(mo::observable_name(snapshot.linearized.kind))
                : "enriched_bond_and_volume"));
    const bool normalization_complete = snapshot.raw_exported &&
        snapshot.normalization.complete;
    tables.operator_status.row({snapshot.id, configuration.id, candidate,
        role, observable,
        snapshot.build_status, std::to_string(configuration.packets.size()),
        std::to_string(snapshot.relation_ids.size()),
        std::to_string(snapshot.linearized.matrix.row_count()),
        std::to_string(snapshot.linearized.matrix.column_count()),
        bool_text(snapshot.raw_exported), digest,
        bool_text(normalization_complete),
        normalization_complete ? "NA" :
            (snapshot.failure.stage == "row_normalization"
                ? snapshot.failure.row : "NA"),
        bool_text(snapshot.built),
        bool_text(snapshot.b_rank_eligible),
        bool_text(facts.generic_solid_gate),
        bool_text(snapshot.decision_driving), "false",
        snapshot.failure.stage, snapshot.failure.reason,
        snapshot.failure.row, snapshot.failure.column,
        snapshot.failure.value, snapshot.failure.ieee754_bits,
        snapshot.failure.value_class});
    emission.snapshots.emplace(snapshot.id, snapshot);
    return snapshot;
}

struct ConfigurationInputEvidence final {
    TopologyFacts facts{};
    std::string packet_digest{};
    std::string neighbor_digest{};
    std::string relation_digest{};
    std::vector<std::uint8_t> checkpoint_before{};
    std::vector<std::uint8_t> checkpoint_round_trip_reserialized{};
    bool checkpoint_round_trip{false};
    bool neighbor_agreement{false};
};

void emit_checkpoint_row(Csv& table, std::string_view configuration_id,
                         std::string_view checkpoint_kind,
                         std::span<const std::uint8_t> checkpoint) {
    table.row({std::string(configuration_id), std::string(checkpoint_kind),
        "lowercase_hex", std::to_string(checkpoint.size()),
        checkpoint_hash(checkpoint), lowercase_hex(checkpoint)});
}

[[nodiscard]] bool checkpoint_bytes_equal(
    std::span<const std::uint8_t> first,
    std::span<const std::uint8_t> second) {
    return first.size() == second.size() &&
        std::equal(first.begin(), first.end(), second.begin());
}

[[nodiscard]] std::string relation_id(const mo::VolumeRelation& relation) {
    return "volume." + std::to_string(relation.center_id) + "." +
        std::to_string(relation.other_ids[0]) + "." +
        std::to_string(relation.other_ids[1]) + "." +
        std::to_string(relation.other_ids[2]);
}

[[nodiscard]] ConfigurationInputEvidence emit_configuration_inputs(
    BundleTables& tables, const Configuration& configuration) {
    ConfigurationInputEvidence result{};
    result.facts = topology_facts(configuration);
    std::vector<Row> packet_rows;
    packet_rows.reserve(configuration.packets.size());
    for (std::size_t index = 0U; index < configuration.packets.size(); ++index) {
        const auto& packet = configuration.packets[index];
        const Vec3d jitter = configuration.jitter_offsets_m[index];
        packet_rows.push_back({configuration.id, std::to_string(index),
            std::to_string(packet.id), std::to_string(packet.mass_quanta),
            hex64(packet.position_m.x), hex64(packet.position_m.y),
            hex64(packet.position_m.z), hex64(packet.velocity_m_per_s.x),
            hex64(packet.velocity_m_per_s.y), hex64(packet.velocity_m_per_s.z),
            hex64(jitter.x), hex64(jitter.y), hex64(jitter.z)});
    }
    append_rows(tables.packets, packet_rows);
    result.packet_digest = grouped_payload_digest(
        "MLS-MECHANICAL-OBSERVABILITY-PACKETS-v1", tables.packets,
        packet_rows);

    std::vector<Row> neighbor_rows;
    const auto audit = neighbor_audit(configuration);
    result.neighbor_agreement = std::ranges::all_of(
        audit, [](const auto& row) { return row.agreement; });
    neighbor_rows.reserve(audit.size());
    for (const auto& row : audit) {
        neighbor_rows.push_back({row.configuration_id, row.phase,
            std::to_string(row.low_id), std::to_string(row.high_id),
            hex64(row.distance_squared_m2), hex64(row.radius_squared_m2),
            bool_text(row.brute_eligible), bool_text(row.lookup_eligible),
            bool_text(row.agreement),
            row.weight.has_value() ? hex64(*row.weight) : "NA"});
    }
    append_rows(tables.neighbors, neighbor_rows);
    result.neighbor_digest = grouped_payload_digest(
        "MLS-MECHANICAL-OBSERVABILITY-NEIGHBORS-v1", tables.neighbors,
        neighbor_rows);

    std::vector<Row> relation_rows;
    relation_rows.reserve(configuration.edges.size() +
        configuration.volumes.size());
    const auto positions = packet_positions(configuration.packets);
    std::size_t relation_index = 0U;
    for (const auto& record : configuration.edges) {
        const double length = std::sqrt(safe_squared_distance(
            positions.at(record.bond.first_id),
            positions.at(record.bond.second_id)));
        relation_rows.push_back({configuration.id,
            std::to_string(relation_index++), record.id, "bond", "NA",
            std::to_string(record.bond.first_id),
            std::to_string(record.bond.second_id), "NA",
            record.retained ? "retained" : "deleted", record.source,
            hex64(length), "m", "NA"});
    }
    for (const auto& relation : configuration.volumes) {
        relation_rows.push_back({configuration.id,
            std::to_string(relation_index++), relation_id(relation),
            "oriented_volume", std::to_string(relation.center_id),
            std::to_string(relation.other_ids[0]),
            std::to_string(relation.other_ids[1]),
            std::to_string(relation.other_ids[2]), "retained",
            configuration.exact_control ? "exact_control" :
                "volume_enrichment",
            hex64(oriented_volume(positions, relation)), "m3",
            hex64(volume_score(positions, relation))});
    }
    append_rows(tables.relations, relation_rows);
    result.relation_digest = grouped_payload_digest(
        "MLS-MECHANICAL-OBSERVABILITY-RELATIONS-v1", tables.relations,
        relation_rows);

    mo::MechanicalObservabilityState state{};
    state.support_radius_m = configuration.support_radius_m;
    state.packets = configuration.packets;
    state.bonds = retained_bonds(configuration);
    state.volumes = configuration.volumes;
    result.checkpoint_before =
        mo::serialize_mechanical_observability_state(state);
    const auto decoded = mo::deserialize_mechanical_observability_state(
        result.checkpoint_before);
    result.checkpoint_round_trip_reserialized =
        mo::serialize_mechanical_observability_state(decoded);
    result.checkpoint_round_trip = checkpoint_bytes_equal(
        result.checkpoint_before,
        result.checkpoint_round_trip_reserialized);
    emit_checkpoint_row(tables.checkpoints, configuration.id,
        "authoritative_before", result.checkpoint_before);
    emit_checkpoint_row(tables.checkpoints, configuration.id,
        "round_trip_reserialized",
        result.checkpoint_round_trip_reserialized);
    return result;
}

void emit_configuration_row(
    BundleTables& tables, const Configuration& configuration,
    const ConfigurationInputEvidence& evidence,
    std::span<const std::uint8_t> checkpoint_after) {
    const bool read_only = checkpoint_bytes_equal(
        evidence.checkpoint_before, checkpoint_after);
    emit_checkpoint_row(tables.checkpoints, configuration.id,
        "after_diagnostics", checkpoint_after);
    tables.configurations.row({configuration.id, configuration.base_id,
        configuration.family, configuration.variant, configuration.profile,
        configuration.transform, "p000",
        std::to_string(configuration.packets.size()),
        hex64(configuration.spacing_m), hex64(configuration.support_radius_m),
        hex64(configuration.geometry_scale),
        std::to_string(evidence.facts.affine_rank),
        bool_text(evidence.facts.connected),
        std::to_string(evidence.facts.edge_count),
        std::to_string(evidence.facts.edge_lower_bound),
        std::to_string(evidence.facts.minimum_direction_rank),
        std::to_string(evidence.facts.rigid_rank),
        bool_text(evidence.facts.generic_solid_gate),
        bool_text(configuration.intentionally_flexible),
        bool_text(configuration.decision_driving), evidence.packet_digest,
        evidence.neighbor_digest, evidence.relation_digest,
        checkpoint_hash(evidence.checkpoint_before),
        checkpoint_hash(checkpoint_after), bool_text(read_only)});
}

[[nodiscard]] std::vector<pf::CenterParticle> center_particles(
    const Configuration& configuration) {
    std::vector<pf::CenterParticle> result;
    result.reserve(configuration.packets.size());
    for (const auto& packet : configuration.packets) {
        result.push_back({packet.id, packet.mass_quanta, packet.position_m,
            packet.velocity_m_per_s});
    }
    return result;
}

struct CandidateAOperators final {
    CandidateAOperators(std::string sampling_id_value,
                        std::string derivative_id_value,
                        pf::ProjectionSystem system_value,
                        std::size_t particle_count,
                        std::size_t node_count)
        : sampling_id(std::move(sampling_id_value)),
          derivative_id(std::move(derivative_id_value)),
          system(std::move(system_value)),
          scalar_sampling(particle_count, node_count),
          sampling(3U * particle_count, 3U * node_count),
          derivative(6U * particle_count, 3U * node_count) {}

    std::string sampling_id{};
    std::string derivative_id{};
    pf::ProjectionSystem system;
    mo::DenseMatrix scalar_sampling{};
    mo::DenseMatrix sampling{};
    mo::DenseMatrix derivative{};
};

[[nodiscard]] CandidateAOperators build_candidate_a(
    const Configuration& configuration, const LookupPhase& phase) {
    const std::string sampling_id =
        configuration.id + ".A." + phase.id + ".S";
    const std::string derivative_id =
        configuration.id + ".A." + phase.id + ".D";
    const double h = configuration.spacing_m;
    const TransferConfig transfer{h,
        {phase.fraction.x * h, phase.fraction.y * h, phase.fraction.z * h},
        kg_per_mass_quantum};
    auto system = pf::build_projection_system(
        center_particles(configuration), transfer);
    const std::size_t particle_count = configuration.packets.size();
    const std::size_t node_count = system.active_nodes().size();
    CandidateAOperators result{sampling_id, derivative_id,
        std::move(system), particle_count, node_count};
    constexpr double half = 0.5;
    for (std::size_t particle = 0U; particle < particle_count; ++particle) {
        for (const auto& entry : result.system.particle_stencils()[particle]) {
            const std::size_t node = entry.node_index;
            result.scalar_sampling(particle, node) = entry.weight;
            for (std::size_t axis = 0U; axis < 3U; ++axis) {
                result.sampling(3U * particle + axis, 3U * node + axis) =
                    entry.weight;
            }
            const auto basis = pen::evaluate_quadratic_bspline_basis(
                result.system.particles()[particle].position_m,
                result.system.active_node_positions_m()[node], h);
            const std::array<double, 3> gradient{
                basis.gradient_m_inv.x, basis.gradient_m_inv.y,
                basis.gradient_m_inv.z};
            result.derivative(6U * particle + 0U, 3U * node + 0U) = gradient[0];
            result.derivative(6U * particle + 1U, 3U * node + 1U) = gradient[1];
            result.derivative(6U * particle + 2U, 3U * node + 2U) = gradient[2];
            result.derivative(6U * particle + 3U, 3U * node + 0U) = half * gradient[1];
            result.derivative(6U * particle + 3U, 3U * node + 1U) = half * gradient[0];
            result.derivative(6U * particle + 4U, 3U * node + 0U) = half * gradient[2];
            result.derivative(6U * particle + 4U, 3U * node + 2U) = half * gradient[0];
            result.derivative(6U * particle + 5U, 3U * node + 1U) = half * gradient[2];
            result.derivative(6U * particle + 5U, 3U * node + 2U) = half * gradient[1];
        }
    }
    return result;
}

[[nodiscard]] std::vector<Row> candidate_a_entries(
    std::string_view operator_id, const Configuration& configuration,
    const pf::ProjectionSystem& system, const mo::DenseMatrix& matrix,
    bool sampling) {
    constexpr std::array<std::string_view, 6> symmetric{
        "xx", "yy", "zz", "xy", "xz", "yz"};
    std::vector<Row> rows;
    const std::size_t block = sampling ? 3U : 6U;
    for (std::size_t row = 0U; row < matrix.row_count(); ++row) {
        const std::size_t packet_index = row / block;
        const std::string row_component = sampling
            ? axis_name(row % 3U) : std::string(symmetric[row % 6U]);
        for (std::size_t column = 0U; column < matrix.column_count(); ++column) {
            const double value = matrix(row, column);
            if (value == 0.0) {
                continue;
            }
            const std::size_t node = column / 3U;
            rows.push_back(operator_entry_row(operator_id, row, column,
                "grid_node", std::to_string(node + 1U),
                axis_name(column % 3U),
                sampling ? "packet_velocity_sample" :
                    "packet_symmetric_gradient",
                std::to_string(configuration.packets[packet_index].id),
                row_component, value, sampling ? "dimensionless" : "per_m"));
        }
    }
    (void)system;
    return rows;
}

[[nodiscard]] double basis_residual(
    const mo::DenseMatrix& matrix, const mo::DenseMatrix& basis) {
    if (basis.column_count() == 0U) {
        return 0.0;
    }
    long double image_squared = 0.0L;
    long double basis_squared = 0.0L;
    for (const double value : basis.entries()) {
        basis_squared += static_cast<long double>(value) * value;
    }
    for (std::size_t mode = 0U; mode < basis.column_count(); ++mode) {
        const auto image = matrix_vector(matrix, matrix_column(basis, mode));
        for (const double value : image) {
            image_squared += static_cast<long double>(value) * value;
        }
    }
    const double denominator = matrix_frobenius(matrix) *
        std::sqrt(static_cast<double>(basis_squared));
    return denominator == 0.0 ? 0.0 :
        std::sqrt(static_cast<double>(image_squared)) / denominator;
}

[[nodiscard]] double scalar_gradient_bound(
    const CandidateAOperators& operators, std::span<const double> mode) {
    double maximum = minimum_normal64;
    for (std::size_t particle = 0U;
         particle < operators.system.particles().size(); ++particle) {
        long double absolute_sum = 0.0L;
        const auto& stencil = operators.system.particle_stencils()[particle];
        for (const auto& entry : stencil) {
            const auto basis = pen::evaluate_quadratic_bspline_basis(
                operators.system.particles()[particle].position_m,
                operators.system.active_node_positions_m()[entry.node_index],
                operators.system.config().grid_spacing_m);
            absolute_sum += std::abs(static_cast<long double>(mode[entry.node_index])) *
                static_cast<long double>(mls::experimental::norm(
                    basis.gradient_m_inv));
        }
        const double bound = 128.0 * gamma_n(3U * stencil.size()) *
            static_cast<double>(absolute_sum);
        maximum = std::max(maximum, bound);
    }
    return maximum;
}

struct CandidateAResult final {
    bool negative_control_reproduced{false};
    bool ranks_unambiguous{true};
    bool raw_decision_exported{true};
    std::vector<std::string> operator_ids{};
};

struct CandidateAGaugeContract final {
    bool has_mode{false};
    bool all_modes_pass{true};

    void observe(bool sampling_accepted, bool derivative_visible) noexcept {
        has_mode = true;
        all_modes_pass = all_modes_pass && sampling_accepted &&
            derivative_visible;
    }

    [[nodiscard]] bool pass() const noexcept {
        return has_mode && all_modes_pass;
    }
};

struct CandidateAPreparedOperator final {
    std::vector<Row> entries{};
    mo::RowNormalization normalization{};
    OperatorFailureWitness failure{};
    std::string build_status{"built"};
    bool raw_exported{false};
    bool built{false};
};

struct CandidateAPairBuildDisposition final {
    bool pair_complete{false};
    bool sampling_rank_applicable{false};
    bool derivative_rank_applicable{false};
    bool rank_and_gauge_evidence_allowed{false};
};

[[nodiscard]] constexpr CandidateAPairBuildDisposition
candidate_a_pair_build_disposition(
    bool sampling_built, bool derivative_built) noexcept {
    const bool complete = sampling_built && derivative_built;
    return {complete, complete, false, complete};
}

struct CandidateARankWireDisposition final {
    std::string_view status{"analyzed"};
    std::string_view failure_stage{"NA"};
    std::string_view failure_reason{"NA"};
    bool suppress_basis_evidence{false};
};

[[nodiscard]] constexpr CandidateARankWireDisposition
candidate_a_rank_wire_disposition(
    bool basis_failure, bool basis_nonfinite, bool ambiguous) noexcept {
    if (basis_failure) {
        return {"numerical_failure", "basis_construction",
            basis_nonfinite ? "nonfinite_basis" : "incomplete_kernel",
            true};
    }
    if (ambiguous) {
        return {"ambiguous", "rank_estimation",
            "ambiguity_band_overlap", true};
    }
    return {};
}

[[nodiscard]] CandidateAPreparedOperator prepare_candidate_a_operator(
    BundleTables& tables, std::string_view operator_id,
    const Configuration& configuration, const pf::ProjectionSystem& system,
    const mo::DenseMatrix& matrix, bool sampling) {
    CandidateAPreparedOperator prepared{};
    const auto nonfinite = first_nonfinite_entry(matrix);
    if (nonfinite.has_value()) {
        const auto [row, column, value] = *nonfinite;
        prepared.build_status = "numerical_failure";
        prepared.failure = {"operator_construction",
            "nonfinite_operator_cell", std::to_string(row),
            std::to_string(column), "NA", ieee754_bits_hex(value),
            nonfinite_class(value)};
        return prepared;
    }
    prepared.raw_exported = true;
    prepared.entries = candidate_a_entries(
        operator_id, configuration, system, matrix, sampling);
    append_rows(tables.operator_entries, prepared.entries);
    prepared.normalization = mo::normalize_operator_rows(matrix);
    if (!prepared.normalization.complete) {
        prepared.build_status = "numerical_failure";
        prepared.failure =
            normalization_failure_witness(prepared.normalization);
        return prepared;
    }
    prepared.built = true;
    return prepared;
}

void emit_candidate_a_status(
    BundleTables& tables, std::string_view id,
    const Configuration& configuration, std::string_view role,
    std::string_view observable, const mo::DenseMatrix& matrix,
    const CandidateAPreparedOperator& prepared, bool rank_applicable) {
    if (rank_applicable && !prepared.built) {
        throw std::logic_error(
            "candidate A rank cannot apply to an unbuilt operator");
    }
    tables.operator_status.row({std::string(id), configuration.id, "A",
        std::string(role), std::string(observable), prepared.build_status,
        std::to_string(configuration.packets.size()), "0",
        std::to_string(matrix.row_count()),
        std::to_string(matrix.column_count()),
        bool_text(prepared.raw_exported),
        prepared.raw_exported ? grouped_payload_digest(
            "MLS-MECHANICAL-OBSERVABILITY-OPERATOR-v1",
            tables.operator_entries, prepared.entries) : "NA",
        bool_text(prepared.normalization.complete),
        prepared.failure.stage == "row_normalization"
            ? prepared.failure.row : "NA",
        bool_text(rank_applicable), "false", "false", "true", "false",
        prepared.failure.stage, prepared.failure.reason,
        prepared.failure.row, prepared.failure.column,
        prepared.failure.value, prepared.failure.ieee754_bits,
        prepared.failure.value_class});
}

[[nodiscard]] CandidateAResult emit_candidate_a_pair(
    BundleTables& tables, const Configuration& configuration,
    const LookupPhase& phase,
    CandidateAFailureFixture failure_fixture =
        CandidateAFailureFixture::none) {
    CandidateAResult result{};
    auto operators = build_candidate_a(configuration, phase);
    result.operator_ids = {operators.sampling_id, operators.derivative_id};
    std::optional<mo::DenseMatrix> failed_sampling;
    std::optional<mo::DenseMatrix> failed_derivative;
    if (failure_fixture == CandidateAFailureFixture::sampling) {
        failed_sampling.emplace(operators.sampling.row_count(),
            operators.sampling.column_count());
    } else if (failure_fixture == CandidateAFailureFixture::derivative) {
        failed_derivative.emplace(operators.derivative.row_count(),
            operators.derivative.column_count());
    }
    const auto& sampling_matrix = failed_sampling.has_value()
        ? *failed_sampling : operators.sampling;
    const auto& derivative_matrix = failed_derivative.has_value()
        ? *failed_derivative : operators.derivative;
    const std::size_t node_count = operators.system.active_nodes().size();
    for (std::size_t node = 0U; node < node_count; ++node) {
        const auto index = operators.system.active_nodes()[node];
        const auto position = operators.system.active_node_positions_m()[node];
        tables.grid_nodes.row({operators.sampling_id, operators.derivative_id,
            configuration.id, phase.id, std::to_string(node),
            std::to_string(node + 1U), std::to_string(index.x),
            std::to_string(index.y), std::to_string(index.z),
            hex64(position.x), hex64(position.y), hex64(position.z)});
    }
    const auto sampling_prepared = prepare_candidate_a_operator(
        tables, operators.sampling_id, configuration, operators.system,
        sampling_matrix, true);
    const auto derivative_prepared = prepare_candidate_a_operator(
        tables, operators.derivative_id, configuration, operators.system,
        derivative_matrix, false);
    const auto pair = candidate_a_pair_build_disposition(
        sampling_prepared.built, derivative_prepared.built);
    emit_candidate_a_status(tables, operators.sampling_id,
        configuration, "negative_control_sampling",
        "frozen_quadratic_sampling", sampling_matrix,
        sampling_prepared, pair.sampling_rank_applicable);
    emit_candidate_a_status(tables, operators.derivative_id,
        configuration, "negative_control_derivative",
        "frozen_quadratic_symmetric_gradient", derivative_matrix,
        derivative_prepared, pair.derivative_rank_applicable);
    if (!pair.rank_and_gauge_evidence_allowed) {
        result.ranks_unambiguous = false;
        result.raw_decision_exported =
            sampling_prepared.raw_exported &&
            derivative_prepared.raw_exported;
        return result;
    }
    const auto& sampling_normalization = sampling_prepared.normalization;
    const auto full_rank = mo::diagnose_rank_and_nullspace(
        sampling_normalization.normalized);
    const auto scalar_normalization =
        mo::normalize_operator_rows(operators.scalar_sampling);
    const auto scalar_rank = mo::diagnose_rank_and_nullspace(
        scalar_normalization.normalized);
    const bool rank_compatible = full_rank.rank == 3U * scalar_rank.rank &&
        full_rank.nullity == 3U * scalar_rank.nullity &&
        full_rank.basis_complete && scalar_rank.basis_complete;
    const std::size_t vector_nullity = 3U * scalar_rank.nullity;
    mo::DenseMatrix lifted(3U * node_count, vector_nullity);
    for (std::size_t scalar_mode = 0U;
         scalar_mode < scalar_rank.nullity; ++scalar_mode) {
        for (std::size_t axis = 0U; axis < 3U; ++axis) {
            const std::size_t vector_mode = 3U * scalar_mode + axis;
            for (std::size_t node = 0U; node < node_count; ++node) {
                lifted(3U * node + axis, vector_mode) =
                    scalar_rank.nullspace_basis(node, scalar_mode);
            }
        }
    }
    const double null_residual = basis_residual(operators.sampling, lifted);
    const double rank_tolerance = residual_tolerance(
        operators.sampling.row_count(), operators.sampling.column_count());
    const bool rank_ambiguous =
        full_rank.status == mo::RankStatus::ambiguous ||
        scalar_rank.status == mo::RankStatus::ambiguous;
    const bool rank_basis_nonfinite =
        !finite_matrix(full_rank.nullspace_basis) ||
        !finite_matrix(scalar_rank.nullspace_basis) ||
        !std::isfinite(full_rank.normalized_null_residual) ||
        !std::isfinite(scalar_rank.normalized_null_residual) ||
        !std::isfinite(null_residual);
    const bool rank_basis_failure = !rank_compatible ||
        full_rank.status == mo::RankStatus::numerical_failure ||
        scalar_rank.status == mo::RankStatus::numerical_failure ||
        rank_basis_nonfinite;
    const auto rank_disposition = candidate_a_rank_wire_disposition(
        rank_basis_failure, rank_basis_nonfinite, rank_ambiguous);
    const bool rank_evidence_suppressed =
        rank_disposition.suppress_basis_evidence;
    const std::string rank_status(rank_disposition.status);
    const std::string rank_failure_stage(rank_disposition.failure_stage);
    const std::string rank_failure_reason(rank_disposition.failure_reason);
    const auto rank_row = [&](std::string kind, std::string pivot_step,
                              std::string permuted_column,
                              std::string diagonal, std::string accepted) {
        return Row{operators.sampling_id, std::move(kind),
            std::move(pivot_step), std::move(permuted_column),
            std::move(diagonal), std::move(accepted), rank_status,
            std::to_string(operators.sampling.row_count()),
            std::to_string(operators.sampling.column_count()),
            std::to_string(full_rank.rank), std::to_string(full_rank.nullity),
            "0", rank_evidence_suppressed ? "NA" :
                std::to_string(full_rank.nullity), hex64(full_rank.threshold),
            hex64(full_rank.ambiguity_lower), hex64(full_rank.ambiguity_upper),
            bool_text(rank_ambiguous),
            "binary64_householder_qrcp_threshold_estimate", "false",
            bool_text(rank_compatible && !rank_evidence_suppressed),
            rank_evidence_suppressed ? "NA" : "true",
            rank_evidence_suppressed ? "NA" :
                bool_text(full_rank.nullity == 0U),
            rank_evidence_suppressed ? "NA" : "0x0.0p+0",
            rank_evidence_suppressed ? "NA" : hex64(null_residual),
            rank_evidence_suppressed ? "NA" : hex64(null_residual),
            rank_evidence_suppressed ? "NA" : "0x0.0p+0",
            hex64(rank_tolerance), rank_evidence_suppressed ? "NA" : "false",
            "false", rank_failure_stage, rank_failure_reason};
    };
    tables.rank_status.row(rank_row("summary", "NA", "NA", "NA", "NA"));
    for (std::size_t step = 0U; step < full_rank.column_permutation.size(); ++step) {
        const double diagonal = step < full_rank.diagonal_magnitudes.size()
            ? full_rank.diagonal_magnitudes[step] : 0.0;
        tables.rank_status.row(rank_row("pivot", std::to_string(step),
            std::to_string(full_rank.column_permutation[step]),
            hex64(diagonal), bool_text(diagonal > full_rank.threshold)));
    }
    if (rank_evidence_suppressed) {
        result.ranks_unambiguous = false;
        return result;
    }
    CandidateAGaugeContract gauge_contract{};
    for (std::size_t mode = 0U; mode < vector_nullity; ++mode) {
        const auto vector = matrix_column(lifted, mode);
        const auto image = matrix_vector(operators.sampling, vector);
        const double image_norm = stable_norm(image);
        const double denominator = std::max(
            matrix_frobenius(operators.sampling) * stable_norm(vector),
            minimum_normal64);
        const double normalized = image_norm / denominator;
        const bool accepted = std::isfinite(normalized) &&
            normalized <= rank_tolerance;
        for (std::size_t dof = 0U; dof < vector.size(); ++dof) {
            tables.nullspace_modes.row({operators.sampling_id,
                "sampling_null", std::to_string(mode), std::to_string(dof),
                "grid_node", std::to_string(dof / 3U + 1U),
                axis_name(dof % 3U), hex64(vector[dof])});
        }
        tables.nullspace_metrics.row({operators.sampling_id, "sampling_null",
            std::to_string(mode), hex64(image_norm), hex64(denominator),
            hex64(normalized), "0x0.0p+0", "0x0.0p+0",
            hex64(rank_tolerance), bool_text(accepted), "false"});
        const auto derivative_image = matrix_vector(operators.derivative, vector);
        double derivative_max = 0.0;
        for (const double value : derivative_image) {
            derivative_max = std::max(derivative_max, std::abs(value));
        }
        const double derivative_rms = derivative_image.empty() ? 0.0 :
            stable_norm(derivative_image) /
                std::sqrt(static_cast<double>(derivative_image.size()));
        const std::size_t scalar_mode = mode / 3U;
        const double bound = scalar_gradient_bound(operators,
            matrix_column(scalar_rank.nullspace_basis, scalar_mode));
        const double ratio = derivative_max / bound;
        const bool visible = derivative_max > std::max(1.0e-10, 1.0e4 * bound);
        const bool pass = accepted && visible;
        gauge_contract.observe(accepted, visible);
        tables.grid_gauge.row({operators.sampling_id, operators.sampling_id,
            operators.derivative_id, std::to_string(mode),
            axis_name(mode % 3U), hex64(normalized), hex64(derivative_max),
            hex64(derivative_rms), hex64(bound), hex64(ratio),
            bool_text(visible), bool_text(accepted), bool_text(pass), "false"});
    }
    const bool aggregate_null_residual_pass =
        std::isfinite(null_residual) && null_residual <= rank_tolerance;
    const bool complete_rank_contract = !rank_ambiguous && rank_compatible &&
        full_rank.status == mo::RankStatus::analyzed &&
        scalar_rank.status == mo::RankStatus::analyzed &&
        aggregate_null_residual_pass && gauge_contract.pass();
    result.negative_control_reproduced = complete_rank_contract;
    result.ranks_unambiguous = complete_rank_contract;
    return result;
}

[[nodiscard]] bool accepted_resolved_c_contract(
    const mo::LinearizedOperator& linearized,
    const mo::ObservabilityDiagnostics& diagnostics) {
    const auto normalization =
        mo::normalize_operator_rows(linearized.matrix);
    return resolved_packet_rank_contract(
        linearized, normalization, diagnostics);
}

struct GlobalDTriggerAssessment final {
    bool has_generic_c{false};
    bool all_generic_c_contracts_accepted{true};
    bool any_resolved_nonrigid_c{false};

    [[nodiscard]] bool trigger() const noexcept {
        return has_generic_c && all_generic_c_contracts_accepted &&
            any_resolved_nonrigid_c;
    }
};

struct CTriggerObservation final {
    bool accepted{false};
    std::size_t nonrigid_nullity{0U};
};

[[nodiscard]] GlobalDTriggerAssessment reduce_global_d_trigger(
    std::span<const CTriggerObservation> observations) {
    GlobalDTriggerAssessment result{};
    result.has_generic_c = !observations.empty();
    for (const auto& observation : observations) {
        result.all_generic_c_contracts_accepted =
            result.all_generic_c_contracts_accepted && observation.accepted;
        result.any_resolved_nonrigid_c = result.any_resolved_nonrigid_c ||
            (observation.accepted && observation.nonrigid_nullity > 0U);
    }
    return result;
}

[[nodiscard]] GlobalDTriggerAssessment assess_global_d_trigger(
    std::span<const Configuration> configurations_value) {
    std::vector<CTriggerObservation> observations;
    for (const auto& configuration : configurations_value) {
        const auto facts = topology_facts(configuration);
        if (configuration.exact_control || !facts.generic_solid_gate) {
            continue;
        }
        const auto bonds = mo::build_bond_rigidity_operator(
            configuration.packets, retained_bonds(configuration));
        const auto diagnostics = mo::diagnose_mechanical_observability(
            bonds.linearized, configuration.packets);
        const bool accepted =
            accepted_resolved_c_contract(bonds.linearized, diagnostics);
        observations.push_back({accepted, diagnostics.nonrigid_nullity});
    }
    return reduce_global_d_trigger(observations);
}

[[nodiscard]] std::vector<std::uint64_t> frozen_packet_permutation(
    const Configuration& configuration) {
    std::vector<std::pair<std::string, std::uint64_t>> ordered;
    ordered.reserve(configuration.packets.size());
    for (const auto& packet : configuration.packets) {
        const std::string preimage = std::to_string(seed) +
            "|packet_permutation|" + configuration.id + "|" +
            std::to_string(packet.id);
        ordered.emplace_back(sha256(preimage), packet.id);
    }
    std::sort(ordered.begin(), ordered.end());
    std::vector<std::uint64_t> result;
    result.reserve(ordered.size());
    for (const auto& [digest, packet_id] : ordered) {
        (void)digest;
        result.push_back(packet_id);
    }
    std::vector<std::uint64_t> canonical;
    canonical.reserve(configuration.packets.size());
    for (const auto& packet : configuration.packets) {
        canonical.push_back(packet.id);
    }
    std::sort(canonical.begin(), canonical.end());
    if (result == canonical && result.size() > 1U) {
        std::rotate(result.begin(), result.begin() + 1, result.end());
    }
    if (result == canonical && result.size() > 1U) {
        throw std::logic_error("packet permutation remained identity");
    }
    return result;
}

[[nodiscard]] std::vector<mo::MechanicalPacket> permuted_packets(
    const Configuration& configuration,
    std::span<const std::uint64_t> packet_order) {
    std::map<std::uint64_t, mo::MechanicalPacket> by_id;
    for (const auto& packet : configuration.packets) {
        by_id.emplace(packet.id, packet);
    }
    std::vector<mo::MechanicalPacket> result;
    result.reserve(packet_order.size());
    for (const auto packet_id : packet_order) {
        result.push_back(by_id.at(packet_id));
    }
    return result;
}

[[nodiscard]] std::vector<std::string> frozen_relation_permutation(
    const Configuration& configuration, std::string_view candidate,
    std::span<const std::string> relation_ids) {
    if (candidate == "B") {
        if (!relation_ids.empty()) {
            throw std::logic_error(
                "candidate B permutation unexpectedly has relations");
        }
        return {};
    }
    if (candidate != "C" && candidate != "D") {
        throw std::invalid_argument("unsupported relation permutation candidate");
    }
    std::vector<std::pair<std::string, std::string>> ordered;
    ordered.reserve(relation_ids.size());
    std::set<std::string> unique;
    for (const auto& relation_id_value : relation_ids) {
        if (!unique.insert(relation_id_value).second) {
            throw std::invalid_argument(
                "relation permutation contains duplicate semantic ID");
        }
        const std::string preimage = std::to_string(seed) +
            "|relation_permutation|" + configuration.id + "|" +
            std::string(candidate) + "|" + relation_id_value;
        ordered.emplace_back(sha256(preimage), relation_id_value);
    }
    std::sort(ordered.begin(), ordered.end());
    std::vector<std::string> result;
    result.reserve(ordered.size());
    for (const auto& [digest, relation_id_value] : ordered) {
        (void)digest;
        result.push_back(relation_id_value);
    }
    const std::vector<std::string> canonical(
        relation_ids.begin(), relation_ids.end());
    if (result == canonical && result.size() > 1U) {
        std::rotate(result.begin(), result.begin() + 1, result.end());
    }
    if (result == canonical && result.size() > 1U) {
        throw std::logic_error("relation permutation remained identity");
    }
    return result;
}

void append_little_u64(std::string& output, std::uint64_t value) {
    for (unsigned shift = 0U; shift < 64U; shift += 8U) {
        output.push_back(static_cast<char>((value >> shift) & 0xffU));
    }
}

[[nodiscard]] std::string canonical_operator_hash(
    const mo::DenseMatrix& matrix) {
    std::string payload{
        "MLS-MECHANICAL-OBSERVABILITY-CANONICAL-OPERATOR-v1\n"};
    append_little_u64(payload,
        static_cast<std::uint64_t>(matrix.row_count()));
    append_little_u64(payload,
        static_cast<std::uint64_t>(matrix.column_count()));
    for (const double value : matrix.entries()) {
        if (!std::isfinite(value)) {
            throw std::overflow_error(
                "canonical operator contains nonfinite entry");
        }
        append_little_u64(payload, std::bit_cast<std::uint64_t>(
            value == 0.0 ? 0.0 : value));
    }
    return sha256(payload);
}

[[nodiscard]] std::string raw_permuted_operator_hash(
    const mo::DenseMatrix& matrix) {
    std::string payload{
        "MLS-MECHANICAL-OBSERVABILITY-RAW-PERMUTED-OPERATOR-v2\n"};
    append_little_u64(payload,
        static_cast<std::uint64_t>(matrix.row_count()));
    append_little_u64(payload,
        static_cast<std::uint64_t>(matrix.column_count()));
    for (const double value : matrix.entries()) {
        if (!std::isfinite(value)) {
            throw std::overflow_error(
                "raw permuted operator contains nonfinite entry");
        }
        append_little_u64(payload, std::bit_cast<std::uint64_t>(
            value == 0.0 ? 0.0 : value));
    }
    return sha256(payload);
}

[[nodiscard]] std::string joined_packet_order(
    std::span<const std::uint64_t> packet_order) {
    std::string result;
    for (std::size_t index = 0U; index < packet_order.size(); ++index) {
        if (index != 0U) {
            result.push_back(':');
        }
        result += std::to_string(packet_order[index]);
    }
    return result;
}

[[nodiscard]] std::string joined_relation_order(
    std::span<const std::string> relation_order) {
    if (relation_order.empty()) {
        return "NA";
    }
    std::string result;
    for (std::size_t index = 0U; index < relation_order.size(); ++index) {
        if (index != 0U) {
            result.push_back(':');
        }
        result += relation_order[index];
    }
    return result;
}

[[nodiscard]] std::map<std::uint64_t, std::size_t> packet_block_indices(
    std::span<const std::uint64_t> packet_ids) {
    std::map<std::uint64_t, std::size_t> result;
    for (std::size_t index = 0U; index < packet_ids.size(); ++index) {
        if (!result.emplace(packet_ids[index], index).second) {
            throw std::invalid_argument("operator has duplicate packet ID");
        }
    }
    return result;
}

[[nodiscard]] std::map<std::string, std::size_t> relation_row_indices(
    std::span<const std::string> relation_ids) {
    std::map<std::string, std::size_t> result;
    for (std::size_t index = 0U; index < relation_ids.size(); ++index) {
        if (!result.emplace(relation_ids[index], index).second) {
            throw std::invalid_argument("operator has duplicate relation ID");
        }
    }
    return result;
}

[[nodiscard]] mo::DenseMatrix raw_permuted_operator(
    const mo::LinearizedOperator& canonical, std::string_view candidate,
    std::span<const std::uint64_t> packet_order,
    std::span<const std::string> canonical_relation_ids,
    std::span<const std::string> relation_order) {
    if (packet_order.size() != canonical.packet_ids.size() ||
        canonical.matrix.column_count() != 3U * packet_order.size()) {
        throw std::invalid_argument(
            "raw permutation packet dimensions do not match operator");
    }
    const auto canonical_packets = packet_block_indices(canonical.packet_ids);
    const auto canonical_relations = relation_row_indices(canonical_relation_ids);
    const bool packet_rows = candidate == "B";
    const std::size_t expected_rows = packet_rows
        ? 6U * packet_order.size() : relation_order.size();
    if (canonical.matrix.row_count() != expected_rows ||
        (packet_rows && (!canonical_relation_ids.empty() ||
                         !relation_order.empty())) ||
        (!packet_rows && canonical_relation_ids.size() != relation_order.size())) {
        throw std::invalid_argument(
            "raw permutation row dimensions do not match operator");
    }
    mo::DenseMatrix raw(expected_rows, canonical.matrix.column_count());
    for (std::size_t raw_row = 0U; raw_row < expected_rows; ++raw_row) {
        const std::size_t canonical_row = packet_rows
            ? 6U * canonical_packets.at(packet_order[raw_row / 6U]) +
                raw_row % 6U
            : canonical_relations.at(relation_order[raw_row]);
        for (std::size_t raw_column = 0U;
             raw_column < raw.column_count(); ++raw_column) {
            const std::size_t canonical_column =
                3U * canonical_packets.at(packet_order[raw_column / 3U]) +
                raw_column % 3U;
            raw(raw_row, raw_column) =
                canonical.matrix(canonical_row, canonical_column);
        }
    }
    return raw;
}

[[nodiscard]] mo::DenseMatrix canonicalize_raw_permuted_operator(
    const mo::DenseMatrix& raw, const mo::LinearizedOperator& canonical_layout,
    std::string_view candidate,
    std::span<const std::uint64_t> packet_order,
    std::span<const std::string> canonical_relation_ids,
    std::span<const std::string> relation_order) {
    if (raw.row_count() != canonical_layout.matrix.row_count() ||
        raw.column_count() != canonical_layout.matrix.column_count()) {
        throw std::invalid_argument(
            "raw operator dimensions differ from canonical layout");
    }
    const auto canonical_packets =
        packet_block_indices(canonical_layout.packet_ids);
    const auto canonical_relations = relation_row_indices(canonical_relation_ids);
    const bool packet_rows = candidate == "B";
    mo::DenseMatrix result(raw.row_count(), raw.column_count());
    for (std::size_t raw_row = 0U; raw_row < raw.row_count(); ++raw_row) {
        const std::size_t canonical_row = packet_rows
            ? 6U * canonical_packets.at(packet_order[raw_row / 6U]) +
                raw_row % 6U
            : canonical_relations.at(relation_order[raw_row]);
        for (std::size_t raw_column = 0U;
             raw_column < raw.column_count(); ++raw_column) {
            const std::size_t canonical_column =
                3U * canonical_packets.at(packet_order[raw_column / 3U]) +
                raw_column % 3U;
            result(canonical_row, canonical_column) = raw(raw_row, raw_column);
        }
    }
    return result;
}

[[nodiscard]] std::vector<Row> raw_permutation_entries(
    std::string_view control_id, std::string_view operator_id,
    std::string_view candidate, const mo::DenseMatrix& raw,
    std::span<const std::uint64_t> packet_order,
    std::span<const std::string> relation_order) {
    constexpr std::array<std::string_view, 6> symmetric_components{
        "xx", "yy", "zz", "xy", "xz", "yz"};
    std::vector<Row> result;
    for (std::size_t row = 0U; row < raw.row_count(); ++row) {
        std::string row_kind;
        std::string owner;
        std::string row_component;
        std::string units;
        if (candidate == "B") {
            row_kind = "symmetric_gradient";
            owner = std::to_string(packet_order[row / 6U]);
            row_component = std::string(symmetric_components[row % 6U]);
            units = "per_m";
        } else {
            if (row >= relation_order.size()) {
                throw std::out_of_range(
                    "raw relation row exceeds semantic relation order");
            }
            owner = relation_order[row];
            const bool volume = owner.starts_with("volume.");
            if (candidate == "C" && volume) {
                throw std::logic_error(
                    "candidate C raw row references a volume relation");
            }
            row_kind = volume
                ? "oriented_volume_rate" : "bond_length_rate";
            row_component = volume ? "volume" : "length";
            units = volume ? "m2" : "one";
        }
        for (std::size_t column = 0U;
             column < raw.column_count(); ++column) {
            const double value = raw(row, column);
            if (value == 0.0) {
                continue;
            }
            Row entry = operator_entry_row(operator_id, row, column,
                "packet", std::to_string(packet_order[column / 3U]),
                axis_name(column % 3U), row_kind, owner, row_component,
                value, units);
            entry.insert(entry.begin(), std::string(control_id));
            result.push_back(std::move(entry));
        }
    }
    return result;
}

void emit_permutation_control(
    BundleTables& tables, EmissionState& emission,
    const Configuration& configuration,
    const OperatorSnapshot& baseline, std::size_t bond_row_count) {
    (void)bond_row_count;
    if (!baseline.built ||
        (baseline.candidate != "B" && baseline.candidate != "C" &&
         baseline.candidate != "D")) {
        return;
    }
    const auto packet_order = frozen_packet_permutation(configuration);
    const auto permuted = permuted_packets(configuration, packet_order);
    mo::LinearizedOperator alternate{};
    if (baseline.candidate == "B") {
        const auto corrected = mo::build_corrected_local_gradient(permuted,
            mo::CorrectedGradientPolicy{
                configuration.support_radius_m, 1.0e10});
        if (corrected.status != mo::OperatorBuildStatus::built) {
            throw std::logic_error(
                "permuted B build differs from baseline status");
        }
        alternate = corrected.symmetric_gradient;
    } else {
        const auto bonds = retained_bonds(configuration);
        const auto bond_operator = mo::build_bond_rigidity_operator(
            permuted, bonds);
        if (baseline.candidate == "C") {
            alternate = bond_operator.linearized;
        } else {
            const auto volume_operator = mo::build_oriented_volume_operator(
                permuted, configuration.volumes);
            alternate = mo::combine_relational_operators(
                bond_operator, volume_operator);
        }
    }
    if (alternate.packet_ids != baseline.linearized.packet_ids ||
        alternate.matrix.row_count() != baseline.linearized.matrix.row_count() ||
        alternate.matrix.column_count() !=
            baseline.linearized.matrix.column_count()) {
        throw std::logic_error(
            "permuted operator semantic dimensions differ from baseline");
    }
    const auto relation_order = frozen_relation_permutation(
        configuration, baseline.candidate, baseline.relation_ids);
    const auto raw = raw_permuted_operator(alternate, baseline.candidate,
        packet_order, baseline.relation_ids, relation_order);
    const auto recanonicalized = canonicalize_raw_permuted_operator(
        raw, alternate, baseline.candidate, packet_order,
        baseline.relation_ids, relation_order);
    const std::string control_id = "permutation." + baseline.id;
    const auto evidence_entries = raw_permutation_entries(
        control_id, baseline.id, baseline.candidate, raw,
        packet_order, relation_order);
    append_rows(tables.permutation_entries, evidence_entries);
    const std::string alternate_hash =
        canonical_operator_hash(recanonicalized);
    const std::string baseline_hash = canonical_operator_hash(
        baseline.linearized.matrix);
    const bool canonical_match = alternate_hash == baseline_hash;
    if (!emission.permutation_matches.emplace(
            baseline.id, canonical_match).second) {
        throw std::logic_error("duplicate permutation control operator ID");
    }
    tables.permutation_controls.row({control_id, baseline.id,
        configuration.id, "sha256_packet_relation_permutation_v2",
        std::to_string(seed), joined_packet_order(packet_order),
        joined_relation_order(relation_order),
        std::to_string(raw.row_count()),
        std::to_string(raw.column_count()),
        std::to_string(evidence_entries.size()),
        grouped_payload_digest(
            "MLS-MECHANICAL-OBSERVABILITY-PERMUTATION-OPERATOR-v2",
            tables.permutation_entries, evidence_entries),
        raw_permuted_operator_hash(raw), alternate_hash, baseline_hash,
        bool_text(canonical_match), "false"});
}

void emit_bcd_operators(BundleTables& tables, EmissionState& emission,
                        const Configuration& configuration) {
    const auto facts = topology_facts(configuration);
    const auto bonds = retained_bonds(configuration);

    const auto corrected = mo::build_corrected_local_gradient(
        configuration.packets,
        mo::CorrectedGradientPolicy{configuration.support_radius_m, 1.0e10});
    const std::string corrected_status(mo::status_name(corrected.status));
    const auto b_snapshot = emit_packet_operator(
        tables, emission, configuration, facts, "B",
        "corrected_local_gradient", corrected_status,
        corrected.symmetric_gradient, {}, 0U, &corrected);
    emit_permutation_control(
        tables, emission, configuration, b_snapshot, 0U);

    const auto bond_operator = mo::build_bond_rigidity_operator(
        configuration.packets, bonds);
    const auto c_snapshot = emit_packet_operator(
        tables, emission, configuration, facts, "C",
        "central_relation_graph", bonds.empty() ? "empty" : "built",
        bond_operator.linearized, bond_relation_ids(configuration),
        bonds.size());
    emit_permutation_control(
        tables, emission, configuration, c_snapshot, bonds.size());

    if (configuration.volumes.empty()) {
        mo::LinearizedOperator empty{};
        empty.kind = mo::ObservableKind::enriched_bond_and_volume;
        (void)emit_packet_operator(tables, emission, configuration, facts, "D",
            "objective_volume_enrichment", "not_triggered", std::move(empty),
            bond_relation_ids(configuration), bonds.size());
        return;
    }
    mo::validate_selected_oriented_volume_relations(
        configuration.packets, bonds, configuration.volumes);
    const auto volume_operator = mo::build_oriented_volume_operator(
        configuration.packets, configuration.volumes);
    auto combined = mo::combine_relational_operators(
        bond_operator, volume_operator);
    auto relation_ids = bond_relation_ids(configuration);
    const auto volume_ids = volume_relation_ids(configuration);
    relation_ids.insert(relation_ids.end(), volume_ids.begin(), volume_ids.end());
    const auto d_snapshot = emit_packet_operator(
        tables, emission, configuration, facts, "D",
        "objective_volume_enrichment", "built", std::move(combined),
        std::move(relation_ids), bonds.size());
    emit_permutation_control(
        tables, emission, configuration, d_snapshot, bonds.size());
}

void emit_exact_references(BundleTables& tables,
                           std::span<const Configuration> configurations_value) {
    struct Claim final {
        std::string_view reference{};
        std::string_view configuration{};
        std::string_view candidate{};
        std::size_t rank{0U};
        std::size_t nullity{0U};
        std::size_t nonrigid{0U};
    };
    constexpr std::array claims{
        Claim{"cube_edge_graph", "exact.cube_edge_graph", "C", 12U, 12U, 6U},
        Claim{"octahedron_graph", "exact.octahedron_graph", "C", 12U, 6U, 0U},
        Claim{"planar_square_plus_diagonal", "exact.planar_square_plus_diagonal", "C", 5U, 7U, 1U},
        Claim{"planar_square_plus_diagonal_and_volume", "exact.planar_square_plus_diagonal_and_volume", "D", 6U, 6U, 0U},
        Claim{"tetrahedron_k4", "exact.tetrahedron_k4", "C", 6U, 6U, 0U},
        Claim{"tetrahedron_k4_minus_edge", "exact.tetrahedron_k4_minus_edge", "C", 5U, 7U, 1U},
    };
    const std::set<std::string> available = [&] {
        std::set<std::string> result;
        for (const auto& configuration : configurations_value) {
            result.insert(configuration.id);
        }
        return result;
    }();
    for (const auto& claim : claims) {
        if (!available.contains(std::string(claim.configuration))) {
            continue;
        }
        const auto found = std::find_if(configurations_value.begin(),
            configurations_value.end(), [&](const auto& value) {
                return value.id == claim.configuration;
            });
        if (found == configurations_value.end()) {
            throw std::logic_error("exact configuration lookup failed");
        }
        const std::size_t rows = retained_bonds(*found).size() +
            (claim.candidate == "D" ? found->volumes.size() : 0U);
        const std::size_t columns = 3U * found->packets.size();
        const std::size_t rigid_rank = claim.nullity - claim.nonrigid;
        tables.exact_reference.row({std::string(claim.reference),
            std::string(claim.configuration), std::string(claim.candidate),
            std::string(claim.configuration) + "." +
                std::string(claim.candidate),
            "Fraction_RREF", "0", std::to_string(rows),
            std::to_string(columns), std::to_string(claim.rank),
            std::to_string(claim.nullity), std::to_string(rigid_rank),
            std::to_string(claim.nonrigid), "true",
            bool_text(claim.nonrigid == 0U), "independent_fraction_rref",
            "true", "false"});
    }
}

[[nodiscard]] std::vector<double> singular_values(
    const mo::DenseMatrix& matrix) {
    const std::size_t rows = matrix.row_count();
    const std::size_t columns = matrix.column_count();
    const bool column_gram = columns <= rows;
    const std::size_t dimension = column_gram ? columns : rows;
    std::vector<long double> gram(dimension * dimension, 0.0L);
    for (std::size_t first = 0U; first < dimension; ++first) {
        for (std::size_t second = first; second < dimension; ++second) {
            long double value = 0.0L;
            const std::size_t sum_count = column_gram ? rows : columns;
            for (std::size_t entry = 0U; entry < sum_count; ++entry) {
                const double lhs = column_gram ? matrix(entry, first) :
                    matrix(first, entry);
                const double rhs = column_gram ? matrix(entry, second) :
                    matrix(second, entry);
                value += static_cast<long double>(lhs) * rhs;
            }
            gram[first * dimension + second] = value;
            gram[second * dimension + first] = value;
        }
    }
    for (std::size_t sweep = 0U; sweep < 128U; ++sweep) {
        long double maximum_off_diagonal = 0.0L;
        long double maximum_diagonal = 0.0L;
        for (std::size_t row = 0U; row < dimension; ++row) {
            maximum_diagonal = std::max(maximum_diagonal,
                std::abs(gram[row * dimension + row]));
            for (std::size_t column = row + 1U; column < dimension; ++column) {
                maximum_off_diagonal = std::max(maximum_off_diagonal,
                    std::abs(gram[row * dimension + column]));
            }
        }
        if (maximum_off_diagonal <= 16.0L *
                std::numeric_limits<long double>::epsilon() *
                std::max(maximum_diagonal,
                    std::numeric_limits<long double>::min())) {
            break;
        }
        for (std::size_t p = 0U; p < dimension; ++p) {
            for (std::size_t q = p + 1U; q < dimension; ++q) {
                const long double apq = gram[p * dimension + q];
                if (apq == 0.0L) {
                    continue;
                }
                const long double app = gram[p * dimension + p];
                const long double aqq = gram[q * dimension + q];
                const long double angle = 0.5L * std::atan2(
                    2.0L * apq, aqq - app);
                const long double cosine = std::cos(angle);
                const long double sine = std::sin(angle);
                for (std::size_t index = 0U; index < dimension; ++index) {
                    if (index == p || index == q) {
                        continue;
                    }
                    const long double aip = gram[index * dimension + p];
                    const long double aiq = gram[index * dimension + q];
                    const long double updated_p = cosine * aip - sine * aiq;
                    const long double updated_q = sine * aip + cosine * aiq;
                    gram[index * dimension + p] = updated_p;
                    gram[p * dimension + index] = updated_p;
                    gram[index * dimension + q] = updated_q;
                    gram[q * dimension + index] = updated_q;
                }
                gram[p * dimension + p] = cosine * cosine * app -
                    2.0L * sine * cosine * apq + sine * sine * aqq;
                gram[q * dimension + q] = sine * sine * app +
                    2.0L * sine * cosine * apq + cosine * cosine * aqq;
                gram[p * dimension + q] = 0.0L;
                gram[q * dimension + p] = 0.0L;
            }
        }
    }
    std::vector<double> result;
    result.reserve(dimension);
    for (std::size_t index = 0U; index < dimension; ++index) {
        result.push_back(std::sqrt(std::max(
            0.0, static_cast<double>(gram[index * dimension + index]))));
    }
    std::sort(result.begin(), result.end(), std::greater<>{});
    return result;
}

[[nodiscard]] double snapshot_residual(const OperatorSnapshot& snapshot) {
    if (!snapshot.built) {
        return 0.0;
    }
    return std::max({snapshot.diagnostics.normalized_rigid_residual,
        snapshot.diagnostics.operator_rank.normalized_null_residual,
        snapshot.diagnostics.normalized_nonrigid_residual,
        snapshot.diagnostics.rigid_orthogonality_residual});
}

[[nodiscard]] double scaled_singular_delta(
    const OperatorSnapshot& first, const OperatorSnapshot& second,
    std::size_t common_rank) {
    const auto first_values = singular_values(first.normalization.normalized);
    const auto second_values = singular_values(second.normalization.normalized);
    if (first_values.size() != second_values.size() ||
        common_rank > first_values.size()) {
        return std::numeric_limits<double>::infinity();
    }
    double result = 0.0;
    for (std::size_t index = 0U; index < common_rank; ++index) {
        result = std::max(result,
            std::abs(first_values[index] - second_values[index]) /
                std::max({first_values[index], second_values[index], 1.0}));
    }
    return result;
}

[[nodiscard]] bool build_status_parity(
    const OperatorSnapshot& first, const OperatorSnapshot& second) {
    return first.build_status == second.build_status &&
        first.failure.stage == second.failure.stage &&
        first.failure.reason == second.failure.reason &&
        first.failure.row == second.failure.row &&
        first.failure.column == second.failure.column &&
        first.failure.value == second.failure.value &&
        first.failure.ieee754_bits == second.failure.ieee754_bits &&
        first.failure.value_class == second.failure.value_class;
}

[[nodiscard]] bool emit_invariance_evidence(
    BundleTables& tables, const EmissionState& emission,
    std::span<const Configuration> configurations_value) {
    bool all_pass = true;
    const auto emit = [&](std::string comparison_id,
                          const OperatorSnapshot& base,
                          const OperatorSnapshot& transformed,
                          std::string transform_kind, double scale,
                          std::string lookup_phase, bool canonical_bytes_match,
                          bool calculate_singular) {
        const bool topology_match = base.linearized.packet_ids ==
            transformed.linearized.packet_ids;
        const bool relation_match = base.relation_ids == transformed.relation_ids;
        const bool build_status_match = build_status_parity(base, transformed);
        const bool base_rank_unambiguous =
            base.built && rank_evidence_disposition(base.diagnostics).status ==
                "analyzed";
        const bool transformed_rank_unambiguous =
            transformed.built &&
            rank_evidence_disposition(transformed.diagnostics).status ==
                "analyzed";
        const bool dimensions_match =
            base.linearized.matrix.row_count() ==
                transformed.linearized.matrix.row_count() &&
            base.linearized.matrix.column_count() ==
                transformed.linearized.matrix.column_count();
        const bool metrics_available = base_rank_unambiguous &&
            transformed_rank_unambiguous && dimensions_match;
        const bool rank_match = metrics_available &&
            base.diagnostics.operator_rank.rank ==
                transformed.diagnostics.operator_rank.rank;
        const bool nullity_match = metrics_available &&
            base.diagnostics.operator_rank.nullity ==
                transformed.diagnostics.operator_rank.nullity;
        const double residual_delta = metrics_available
            ? std::abs(snapshot_residual(base) -
                snapshot_residual(transformed)) : 0.0;
        const double singular_delta = metrics_available &&
                calculate_singular && rank_match && nullity_match
            ? scaled_singular_delta(base, transformed,
                base.diagnostics.operator_rank.rank) : 0.0;
        const double tolerance = 16384.0 * static_cast<double>(std::max({
            base.linearized.matrix.row_count(),
            base.linearized.matrix.column_count(),
            transformed.linearized.matrix.row_count(),
            transformed.linearized.matrix.column_count()})) * epsilon64;
        const bool metric_pass = metrics_available && topology_match &&
            relation_match && rank_match && nullity_match &&
            residual_delta <= tolerance && singular_delta <= tolerance &&
            (transform_kind != "packet_permutation" || canonical_bytes_match);
        const bool status_parity_pass = !base.built && !transformed.built &&
            topology_match && relation_match && build_status_match;
        const bool pass = metric_pass || status_parity_pass;
        const bool mandatory_unavailable = !metrics_available &&
            (base.decision_driving || transformed.decision_driving);
        all_pass = all_pass && pass && !mandatory_unavailable;
        tables.invariance.row({std::move(comparison_id), base.id,
            transformed.id, std::move(transform_kind), hex64(scale),
            std::move(lookup_phase), bool_text(topology_match),
            bool_text(relation_match), bool_text(rank_match),
            bool_text(nullity_match), base.build_status,
            transformed.build_status, bool_text(build_status_match),
            bool_text(metrics_available),
            metrics_available ? hex64(residual_delta) : "NA",
            metrics_available ? hex64(singular_delta) : "NA",
            metrics_available ? hex64(tolerance) : "NA",
            bool_text(metrics_available && canonical_bytes_match),
            bool_text(pass)});
    };

    for (const auto& [id, snapshot] : emission.snapshots) {
        if (!snapshot.built) {
            continue;
        }
        const auto permutation = emission.permutation_matches.find(id);
        const bool canonical_match =
            permutation != emission.permutation_matches.end() &&
            permutation->second;
        emit("permutation." + id, snapshot, snapshot, "packet_permutation",
            1.0, "NA", canonical_match, false);
    }
    for (const auto& configuration : configurations_value) {
        const auto found = emission.snapshots.find(configuration.id + ".C");
        if (found != emission.snapshots.end()) {
            emit("lookup_phase." + configuration.id, found->second,
                found->second, "lookup_phase", 1.0,
                "p000_to_p037_011_029", false, false);
        }
        if (configuration.variant == "original") {
            continue;
        }
        for (const std::string candidate : {"B", "C", "D"}) {
            const auto base = emission.snapshots.find(
                configuration.base_id + "." + candidate);
            const auto transformed = emission.snapshots.find(
                configuration.id + "." + candidate);
            if (base == emission.snapshots.end() ||
                transformed == emission.snapshots.end()) {
                throw std::logic_error(
                    "metamorphic comparison lacks attempted operator status");
            }
            emit("metamorphic." + configuration.id + "." + candidate,
                base->second, transformed->second, configuration.transform,
                configuration.geometry_scale, "NA", false, true);
        }
    }
    return all_pass && !tables.invariance.rows().empty();
}

[[nodiscard]] long long numeric_key(std::string_view value) {
    if (value == "NA") {
        return -1;
    }
    std::size_t consumed = 0U;
    const long long result = std::stoll(std::string(value), &consumed, 10);
    if (consumed != value.size()) {
        throw std::invalid_argument("noncanonical numerical sort key");
    }
    return result;
}

[[nodiscard]] int checkpoint_kind_order(std::string_view kind) {
    if (kind == "authoritative_before") {
        return 0;
    }
    if (kind == "round_trip_reserialized") {
        return 1;
    }
    if (kind == "after_diagnostics") {
        return 2;
    }
    throw std::invalid_argument("checkpoint row has unknown closed kind");
}

void sort_tables(BundleTables& tables) {
    const auto lex = [](std::size_t first) {
        return [=](const Row& lhs, const Row& rhs) {
            return lhs[first] < rhs[first];
        };
    };
    tables.configurations.sort_rows(lex(0U));
    tables.packets.sort_rows([](const Row& lhs, const Row& rhs) {
        return std::tuple(lhs[0], numeric_key(lhs[1])) <
            std::tuple(rhs[0], numeric_key(rhs[1]));
    });
    tables.neighbors.sort_rows([](const Row& lhs, const Row& rhs) {
        return std::tuple(lhs[0], lhs[1], numeric_key(lhs[2]), numeric_key(lhs[3])) <
            std::tuple(rhs[0], rhs[1], numeric_key(rhs[2]), numeric_key(rhs[3]));
    });
    tables.grid_nodes.sort_rows([](const Row& lhs, const Row& rhs) {
        return std::tuple(lhs[0], numeric_key(lhs[4])) <
            std::tuple(rhs[0], numeric_key(rhs[4]));
    });
    tables.checkpoints.sort_rows([](const Row& lhs, const Row& rhs) {
        return std::tuple(lhs[0], checkpoint_kind_order(lhs[1])) <
            std::tuple(rhs[0], checkpoint_kind_order(rhs[1]));
    });
    tables.permutation_controls.sort_rows(lex(0U));
    tables.permutation_entries.sort_rows([](const Row& lhs, const Row& rhs) {
        return std::tuple(lhs[0], numeric_key(lhs[2]), numeric_key(lhs[3])) <
            std::tuple(rhs[0], numeric_key(rhs[2]), numeric_key(rhs[3]));
    });
    tables.relations.sort_rows([](const Row& lhs, const Row& rhs) {
        return std::tuple(lhs[0], numeric_key(lhs[1])) <
            std::tuple(rhs[0], numeric_key(rhs[1]));
    });
    tables.operator_status.sort_rows(lex(0U));
    tables.operator_entries.sort_rows([](const Row& lhs, const Row& rhs) {
        return std::tuple(lhs[0], numeric_key(lhs[1]), numeric_key(lhs[2])) <
            std::tuple(rhs[0], numeric_key(rhs[1]), numeric_key(rhs[2]));
    });
    tables.moments.sort_rows([](const Row& lhs, const Row& rhs) {
        return std::tuple(lhs[0], numeric_key(lhs[1])) <
            std::tuple(rhs[0], numeric_key(rhs[1]));
    });
    tables.affine.sort_rows([](const Row& lhs, const Row& rhs) {
        return std::tie(lhs[0], lhs[1]) < std::tie(rhs[0], rhs[1]);
    });
    tables.invariance.sort_rows(lex(0U));
    const auto basis_sort = [](const Row& lhs, const Row& rhs) {
        return std::tuple(lhs[0], lhs[1], numeric_key(lhs[2]), numeric_key(lhs[3])) <
            std::tuple(rhs[0], rhs[1], numeric_key(rhs[2]), numeric_key(rhs[3]));
    };
    tables.rigid_basis.sort_rows(basis_sort);
    tables.rank_status.sort_rows([](const Row& lhs, const Row& rhs) {
        const int lhs_kind = lhs[1] == "summary" ? 0 : 1;
        const int rhs_kind = rhs[1] == "summary" ? 0 : 1;
        return std::tuple(lhs[0], lhs_kind, numeric_key(lhs[2])) <
            std::tuple(rhs[0], rhs_kind, numeric_key(rhs[2]));
    });
    tables.nullspace_modes.sort_rows(basis_sort);
    tables.nullspace_metrics.sort_rows([](const Row& lhs, const Row& rhs) {
        return std::tuple(lhs[0], lhs[1], numeric_key(lhs[2])) <
            std::tuple(rhs[0], rhs[1], numeric_key(rhs[2]));
    });
    tables.grid_gauge.sort_rows([](const Row& lhs, const Row& rhs) {
        return std::tuple(lhs[0], numeric_key(lhs[3])) <
            std::tuple(rhs[0], numeric_key(rhs[3]));
    });
    tables.exact_reference.sort_rows(lex(0U));
}

struct NamedTable final {
    std::string_view name{};
    const Csv* table{nullptr};
};

[[nodiscard]] std::array<NamedTable, 19> named_tables(
    const BundleTables& tables) {
    return {{{"affine_objectivity.csv", &tables.affine},
        {"checkpoints.csv", &tables.checkpoints},
        {"configurations.csv", &tables.configurations},
        {"exact_reference.csv", &tables.exact_reference},
        {"grid_gauge.csv", &tables.grid_gauge},
        {"grid_nodes.csv", &tables.grid_nodes},
        {"invariance.csv", &tables.invariance},
        {"moment_diagnostics.csv", &tables.moments},
        {"neighbor_pairs.csv", &tables.neighbors},
        {"nullspace_metrics.csv", &tables.nullspace_metrics},
        {"nullspace_modes.csv", &tables.nullspace_modes},
        {"operator_entries.csv", &tables.operator_entries},
        {"operator_status.csv", &tables.operator_status},
        {"packets.csv", &tables.packets},
        {"permutation_controls.csv", &tables.permutation_controls},
        {"permutation_entries.csv", &tables.permutation_entries},
        {"rank_status.csv", &tables.rank_status},
        {"relations.csv", &tables.relations},
        {"rigid_basis.csv", &tables.rigid_basis}}};
}

[[nodiscard]] std::string json_string_array(
    const std::vector<std::string>& values, std::size_t indentation) {
    std::string result{"["};
    if (!values.empty()) {
        result.push_back('\n');
        for (std::size_t index = 0U; index < values.size(); ++index) {
            result.append(indentation + 2U, ' ');
            result += '"' + json_escape(values[index]) + '"';
            result += index + 1U == values.size() ? "\n" : ",\n";
        }
        result.append(indentation, ' ');
    }
    result.push_back(']');
    return result;
}

struct SummaryInputs final {
    RunMode mode{RunMode::full};
    bool checkpoint_all{true};
    bool read_only_all{true};
    bool neighbor_all{true};
    bool negative_control{false};
    bool affine_all{true};
    bool finite_all{true};
    bool invariance_all{true};
    bool ranks_all{true};
    bool raw_all{true};
    bool exact_all{true};
};

struct BScientificReduction final {
    bool present{false};
    bool nonrigid{false};
};

[[nodiscard]] BScientificReduction reduce_scientific_b(
    const std::map<std::string, OperatorSnapshot>& snapshots) {
    BScientificReduction result{};
    for (const auto& [id, snapshot] : snapshots) {
        (void)id;
        // Flexible and lower-dimensional controls remain fully exported, but
        // they cannot reject a generic-solid representation. These predicates
        // mirror built, b_rank_eligible, generic_solid_gate, and
        // decision_driving in operator_status.csv.
        const bool eligible = snapshot.candidate == "B" && snapshot.built &&
            snapshot.b_rank_eligible && snapshot.generic_solid_gate &&
            snapshot.decision_driving;
        if (!eligible) {
            continue;
        }
        result.present = true;
        result.nonrigid = result.nonrigid ||
            snapshot.diagnostics.nonrigid_nullity > 0U;
    }
    return result;
}

[[nodiscard]] std::string make_summary(
    const BundleTables& tables, const EmissionState& emission,
    const SummaryInputs& inputs) {
    std::vector<std::string> configuration_ids;
    for (const auto& row : tables.configurations.rows()) {
        configuration_ids.push_back(row[0]);
    }
    std::vector<std::string> operator_ids;
    for (const auto& row : tables.operator_status.rows()) {
        operator_ids.push_back(row[0]);
    }
    std::string a_finding = inputs.negative_control
        ? "negative_control_reproduced" : "negative_control_failed";
    std::string b_finding = "inconclusive";
    std::string c_finding = "inconclusive";
    std::string d_finding = "inconclusive";
    std::string decision = "stop_inconclusive_or_implementation_failure";
    const bool gates_pass = inputs.negative_control && inputs.checkpoint_all &&
        inputs.read_only_all && inputs.neighbor_all && inputs.affine_all &&
        inputs.finite_all && inputs.invariance_all && inputs.ranks_all &&
        inputs.raw_all && inputs.exact_all;
    if (inputs.mode == RunMode::full && gates_pass) {
        const auto b_reduction = reduce_scientific_b(emission.snapshots);
        bool c_present = false;
        std::set<std::string> c_generic_configurations;
        std::set<std::string> c_nonrigid_configurations;
        std::map<std::string, const OperatorSnapshot*> d_by_configuration;
        for (const auto& [id, snapshot] : emission.snapshots) {
            (void)id;
            if (!snapshot.built) {
                continue;
            }
            if (snapshot.candidate == "C" &&
                       snapshot.generic_solid_gate) {
                c_present = true;
                c_generic_configurations.insert(snapshot.configuration_id);
                if (snapshot.diagnostics.nonrigid_nullity > 0U) {
                    c_nonrigid_configurations.insert(snapshot.configuration_id);
                }
            } else if (snapshot.candidate == "D") {
                d_by_configuration.emplace(snapshot.configuration_id, &snapshot);
            }
        }
        if (b_reduction.present && c_present) {
            b_finding = b_reduction.nonrigid
                ? "reject_averaged_single_gradient_packet_kinematics"
                : "no_resolved_eligible_nonrigid_mode";
            if (c_nonrigid_configurations.empty()) {
                c_finding =
                    "retain_central_relational_representation_for_research";
                d_finding = "not_triggered";
                decision =
                    "retain_central_relational_representation_for_research";
            } else {
                bool all_d_present = true;
                bool any_d_nonrigid = false;
                for (const auto& configuration_id :
                     c_generic_configurations) {
                    const auto found = d_by_configuration.find(configuration_id);
                    all_d_present = all_d_present &&
                        found != d_by_configuration.end();
                    if (found != d_by_configuration.end()) {
                        any_d_nonrigid = any_d_nonrigid ||
                            found->second->diagnostics.nonrigid_nullity > 0U;
                    }
                }
                if (all_d_present) {
                    c_finding = "generic_nonrigid_mode_triggers_d";
                    d_finding = any_d_nonrigid
                        ? "stop_reconsider_packet_abstraction"
                        : "retain_volume_enriched_relational_representation_for_research";
                    decision = any_d_nonrigid
                        ? "stop_reconsider_packet_abstraction"
                        : "retain_volume_enriched_relational_representation_for_research";
                }
            }
        }
    }
    std::ostringstream output;
    output.imbue(std::locale::classic());
    output << "{\n"
           << "  \"schema\": \"" << summary_schema << "\",\n"
           << "  \"mode\": \"" << run_mode_name(inputs.mode) << "\",\n"
           << "  \"provisional\": "
           << bool_text(inputs.mode != RunMode::full) << ",\n"
           << "  \"sweep_complete\": "
           << bool_text(inputs.mode == RunMode::full) << ",\n"
           << "  \"producer\": \"cpp_mechanical_observability_lab\",\n"
           << "  \"seed\": " << seed << ",\n"
           << "  \"source_sha\": \"" << MLS_CONFIGURED_SOURCE_SHA << "\",\n"
           << "  \"parent_sha\": \"" << accepted_parent_sha << "\",\n"
           << "  \"branch\": \"" << frozen_branch << "\",\n"
           << "  \"dirty\": " << MLS_CONFIGURED_SOURCE_DIRTY << ",\n"
           << "  \"registered_configuration_ids\": "
           << json_string_array(configuration_ids, 2U) << ",\n"
           << "  \"registered_operator_ids\": "
           << json_string_array(operator_ids, 2U) << ",\n"
           << "  \"checkpoint_round_trip_all_pass\": " << bool_text(inputs.checkpoint_all) << ",\n"
           << "  \"diagnostics_read_only_all_exact\": " << bool_text(inputs.read_only_all) << ",\n"
           << "  \"neighbor_lookup_all_agree\": " << bool_text(inputs.neighbor_all) << ",\n"
           << "  \"negative_control_reproduced\": " << bool_text(inputs.negative_control) << ",\n"
           << "  \"affine_objectivity_all_pass\": " << bool_text(inputs.affine_all) << ",\n"
           << "  \"finite_objectivity_all_pass\": " << bool_text(inputs.finite_all) << ",\n"
           << "  \"invariance_all_pass\": " << bool_text(inputs.invariance_all) << ",\n"
           << "  \"decisive_rank_rows_all_unambiguous\": " << bool_text(inputs.ranks_all) << ",\n"
           << "  \"raw_decision_rows_all_exported\": " << bool_text(inputs.raw_all) << ",\n"
           << "  \"independent_reference_all_pass\": " << bool_text(inputs.exact_all) << ",\n"
           << "  \"nondeterminism_detected\": false,\n"
           << "  \"candidate_findings\": {\n"
           << "    \"A\": \"" << a_finding << "\",\n"
           << "    \"B\": \"" << b_finding << "\",\n"
           << "    \"C\": \"" << c_finding << "\",\n"
           << "    \"D\": \"" << d_finding << "\"\n"
           << "  },\n"
           << "  \"decision\": \"" << decision << "\",\n"
           << "  \"promotion\": false,\n"
           << "  \"row_counts\": {\n";
    const auto tables_value = named_tables(tables);
    for (std::size_t index = 0U; index < tables_value.size(); ++index) {
        output << "    \"" << tables_value[index].name << "\": "
               << tables_value[index].table->size()
               << (index + 1U == tables_value.size() ? "\n" : ",\n");
    }
    output << "  },\n"
           << "  \"tolerances\": {\n"
           << "    \"moment_condition_number_max\": \"1e10\",\n"
           << "    \"moment_inverse_residual_formula\": \"4096*3*epsilon64\",\n"
           << "    \"rank_threshold_formula\": \"512*max(m,n)*epsilon64*max(d0,minnormal)\",\n"
           << "    \"rank_ambiguity_factor\": \"8\",\n"
           << "    \"rank_residual_formula\": \"4096*max(m,n)*epsilon64\",\n"
           << "    \"affine_normalized_formula\": \"4096*max(m,n)*epsilon64\",\n"
           << "    \"finite_roundoff_formula\": \"256*gamma(operation_count)*operand_scale+256*minnormal\",\n"
           << "    \"invariance_formula\": \"16384*max(m,n)*epsilon64\",\n"
           << "    \"grid_gauge_absolute_floor_per_s\": \"1e-10\",\n"
           << "    \"grid_gauge_roundoff_multiplier\": \"1e4\"\n"
           << "  }\n"
           << "}\n";
    return output.str();
}

[[nodiscard]] std::string manifest_payload(
    const std::map<std::string, std::string>& hashes) {
    std::ostringstream output;
    output << "{\n  \"algorithm\": \"SHA-256\",\n  \"files\": {\n";
    std::size_t index = 0U;
    for (const auto& [name, digest] : hashes) {
        output << "    \"" << name << "\": \"" << digest << "\""
               << (++index == hashes.size() ? "\n" : ",\n");
    }
    output << "  },\n  \"schema\": \"" << manifest_schema << "\"\n}";
    return output.str();
}

void write_bundle(const std::filesystem::path& output_directory,
                  const BundleTables& tables, std::string_view summary) {
    const std::set<std::string> expected = [&] {
        std::set<std::string> result{"summary.json", "manifest.json"};
        for (const auto& named : named_tables(tables)) {
            result.insert(std::string(named.name));
        }
        return result;
    }();
    if (std::filesystem::exists(output_directory)) {
        for (const auto& entry :
             std::filesystem::directory_iterator(output_directory)) {
            if (!entry.is_regular_file() ||
                !expected.contains(entry.path().filename().string())) {
                throw std::runtime_error(
                    "output directory contains an unexpected entry: " +
                    entry.path().string());
            }
        }
    }
    std::filesystem::create_directories(output_directory);
    std::map<std::string, std::string> hashes;
    for (const auto& named : named_tables(tables)) {
        const std::string contents = named.table->contents();
        write_text(output_directory / named.name, contents);
        hashes.emplace(std::string(named.name), sha256(contents));
    }
    write_text(output_directory / "summary.json", summary);
    hashes.emplace("summary.json", sha256(summary));
    const std::string preimage = manifest_payload(hashes);
    const std::string prehash = sha256(preimage);
    std::ostringstream manifest;
    manifest << "{\n  \"algorithm\": \"SHA-256\",\n  \"files\": {\n";
    std::size_t index = 0U;
    for (const auto& [name, digest] : hashes) {
        manifest << "    \"" << name << "\": \"" << digest << "\""
                 << (++index == hashes.size() ? "\n" : ",\n");
    }
    manifest << "  },\n  \"pre_hash_sha256\": \"" << prehash
             << "\",\n  \"schema\": \"" << manifest_schema << "\"\n}\n";
    write_text(output_directory / "manifest.json", manifest.str());
}

void schema_audit() {
    const auto full = full_configurations();
    if (full.size() != 59U ||
        std::count_if(full.begin(), full.end(), [](const auto& value) {
            return value.variant == "original";
        }) != 29 ||
        std::count_if(full.begin(), full.end(), [](const auto& value) {
            return value.candidate_a_representative;
        }) != 6) {
        throw std::logic_error("frozen configuration matrix audit failed");
    }
    BundleTables tables{};
    const auto inventory = named_tables(tables);
    if (inventory.size() != 19U) {
        throw std::logic_error("frozen CSV inventory is not 19 tables");
    }
    if (checkpoint_kind_order("authoritative_before") != 0 ||
        checkpoint_kind_order("round_trip_reserialized") != 1 ||
        checkpoint_kind_order("after_diagnostics") != 2) {
        throw std::logic_error("closed checkpoint kind order changed");
    }
    for (const auto& named : inventory) {
        if (named.table == nullptr || named.table->fields().empty()) {
            throw std::logic_error("frozen CSV schema is empty");
        }
    }
    const auto source_root =
        std::filesystem::path(__FILE__).parent_path().parent_path();
    const auto schema_path =
        source_root / "docs" / "mechanical-observability-evidence-schema.md";
    std::ifstream schema_stream(schema_path, std::ios::binary);
    if (!schema_stream) {
        throw std::runtime_error(
            "schema audit cannot open frozen wire documentation");
    }
    const std::string schema_document{
        std::istreambuf_iterator<char>(schema_stream),
        std::istreambuf_iterator<char>()};
    for (const auto& named : inventory) {
        std::string documented_header;
        for (std::size_t index = 0U;
             index < named.table->fields().size(); ++index) {
            if (index != 0U) {
                documented_header.push_back(',');
            }
            documented_header += named.table->fields()[index];
        }
        if (schema_document.find(documented_header) == std::string::npos) {
            throw std::logic_error(
                "wire documentation header drift: " +
                std::string(named.name));
        }
    }
    constexpr std::string_view summary_v2_key_prefix =
        "schema,mode,provisional,sweep_complete,producer,seed,source_sha,"
        "parent_sha,branch,dirty,";
    if (schema_document.find(summary_schema) == std::string::npos ||
        schema_document.find(summary_v2_key_prefix) == std::string::npos ||
        schema_document.find(
            "--a-pair-failure-fixture {sampling,derivative} --output DIR") ==
            std::string::npos) {
        throw std::logic_error(
            "summary v2 or failure-fixture wire documentation drift");
    }
    for (const auto& configuration : full) {
        const auto order = frozen_packet_permutation(configuration);
        std::vector<std::uint64_t> canonical;
        for (const auto& packet : configuration.packets) {
            canonical.push_back(packet.id);
        }
        std::sort(canonical.begin(), canonical.end());
        if (order.size() != canonical.size() ||
            (order.size() > 1U && order == canonical)) {
            throw std::logic_error(
                "frozen packet permutation schema audit failed");
        }
        const auto c_relation_ids = bond_relation_ids(configuration);
        const auto relation_order = frozen_relation_permutation(
            configuration, "C", c_relation_ids);
        if (relation_order.size() != c_relation_ids.size() ||
            (relation_order.size() > 1U &&
             relation_order == c_relation_ids)) {
            throw std::logic_error(
                "frozen relation permutation schema audit failed");
        }
    }
    BundleTables unexported_tables{};
    EmissionState unexported_emission{};
    mo::LinearizedOperator empty{};
    (void)emit_packet_operator(unexported_tables, unexported_emission,
        full.front(), topology_facts(full.front()), "D",
        "objective_volume_enrichment", "not_triggered", std::move(empty),
        {}, 0U);
    if (unexported_tables.operator_status.size() != 1U ||
        unexported_tables.operator_entries.size() != 0U ||
        unexported_tables.operator_status.rows().front()[10] != "false" ||
        unexported_tables.operator_status.rows().front()[11] != "NA") {
        throw std::logic_error(
            "unexported operator must use NA digest and no stray entries");
    }
    std::cout << "Mechanical Observability schema audit: PASS\n";
}

void logic_audit() {
    static_assert(finite_bond_operation_count == 72U);
    static_assert(finite_volume_operation_count == 134U);
    struct OptionShapeCase final {
        bool smoke{false};
        bool failure_fixture{false};
        bool schema{false};
        bool logic{false};
        bool output{false};
        bool expected{false};
    };
    constexpr std::array option_shape_cases{
        OptionShapeCase{false, false, false, false, true, true},
        OptionShapeCase{true, false, false, false, true, true},
        OptionShapeCase{false, true, false, false, true, true},
        OptionShapeCase{false, false, true, false, false, true},
        OptionShapeCase{false, false, false, true, false, true},
        OptionShapeCase{true, true, false, false, true, false},
        OptionShapeCase{false, true, true, false, false, false},
        OptionShapeCase{false, true, false, true, false, false},
        OptionShapeCase{false, true, false, false, false, false},
        OptionShapeCase{false, false, true, false, true, false},
        OptionShapeCase{false, false, false, false, false, false},
    };
    for (const auto& test : option_shape_cases) {
        if (valid_option_shape(test.smoke, test.failure_fixture,
                test.schema, test.logic, test.output) != test.expected) {
            throw std::logic_error(
                "logic audit diagnostic CLI state-machine mismatch");
        }
    }
    auto bases = base_configurations();
    const auto square = std::find_if(bases.begin(), bases.end(), [](const auto& value) {
        return value.id ==
            "exact.planar_square_plus_diagonal_and_volume";
    });
    if (square == bases.end()) {
        throw std::logic_error("logic audit missing exact enriched square");
    }
    const auto bonds = mo::build_bond_rigidity_operator(
        square->packets, retained_bonds(*square));
    const auto c = mo::diagnose_mechanical_observability(
        bonds.linearized, square->packets);
    const auto volumes = mo::build_oriented_volume_operator(
        square->packets, square->volumes);
    const auto d_linearized = mo::combine_relational_operators(bonds, volumes);
    const auto d = mo::diagnose_mechanical_observability(
        d_linearized, square->packets);
    if (c.status != mo::RankStatus::analyzed || c.nonrigid_nullity != 1U ||
        d.status != mo::RankStatus::analyzed || d.nonrigid_nullity != 0U) {
        throw std::logic_error("logic audit exact rank decision failed");
    }
    if (!accepted_resolved_c_contract(bonds.linearized, c)) {
        throw std::logic_error(
            "logic audit accepted C contract was rejected");
    }
    auto incomplete_c = c;
    incomplete_c.operator_rank.basis_complete = false;
    if (accepted_resolved_c_contract(bonds.linearized, incomplete_c)) {
        throw std::logic_error(
            "logic audit incomplete C basis triggered enrichment");
    }
    auto failed_residual_c = c;
    failed_residual_c.normalized_nonrigid_residual =
        2.0 * residual_tolerance(bonds.linearized.matrix.row_count(),
            bonds.linearized.matrix.column_count());
    if (accepted_resolved_c_contract(
            bonds.linearized, failed_residual_c)) {
        throw std::logic_error(
            "logic audit failed C residual triggered enrichment");
    }
    auto failed_orthogonality_c = c;
    failed_orthogonality_c.rigid_orthogonality_residual =
        2.0 * residual_tolerance(bonds.linearized.matrix.row_count(),
            bonds.linearized.matrix.column_count());
    if (accepted_resolved_c_contract(
            bonds.linearized, failed_orthogonality_c)) {
        throw std::logic_error(
            "logic audit failed C orthogonality triggered enrichment");
    }
    auto failed_mode_c = c;
    if (failed_mode_c.operator_rank.nullspace_basis.column_count() == 0U) {
        throw std::logic_error(
            "logic audit C control lacks a complete-kernel mode");
    }
    failed_mode_c.operator_rank.nullspace_basis(0U, 0U) += 1.0;
    if (accepted_resolved_c_contract(bonds.linearized, failed_mode_c)) {
        throw std::logic_error(
            "logic audit failed C per-mode residual triggered enrichment");
    }
    struct DecisiveRankCase final {
        std::string_view candidate{};
        std::string_view state{};
        bool decision_driving{true};
        bool expected{false};
    };
    constexpr std::array decisive_rank_cases{
        DecisiveRankCase{"B", "resolved", true, true},
        DecisiveRankCase{"B", "ambiguous", true, false},
        DecisiveRankCase{"B", "numerical_failure", true, false},
        DecisiveRankCase{"B", "unbuilt", true, false},
        DecisiveRankCase{"C", "resolved", true, true},
        DecisiveRankCase{"C", "ambiguous", true, false},
        DecisiveRankCase{"C", "numerical_failure", true, false},
        DecisiveRankCase{"C", "unbuilt", true, false},
        DecisiveRankCase{"D", "resolved", true, true},
        DecisiveRankCase{"D", "ambiguous", true, false},
        DecisiveRankCase{"D", "numerical_failure", true, false},
        DecisiveRankCase{"D", "unbuilt", true, false},
        DecisiveRankCase{"B", "unbuilt", false, true},
        DecisiveRankCase{"D", "unbuilt", false, true},
    };
    for (const auto& test : decisive_rank_cases) {
        OperatorSnapshot snapshot{};
        snapshot.candidate = std::string(test.candidate);
        snapshot.decision_driving = test.decision_driving;
        snapshot.linearized = bonds.linearized;
        snapshot.normalization = mo::normalize_operator_rows(
            snapshot.linearized.matrix);
        snapshot.diagnostics = c;
        snapshot.built = test.state != "unbuilt";
        if (test.state == "ambiguous") {
            snapshot.diagnostics.status = mo::RankStatus::ambiguous;
        } else if (test.state == "numerical_failure") {
            snapshot.diagnostics.status =
                mo::RankStatus::numerical_failure;
            snapshot.diagnostics.operator_rank.basis_complete = false;
        }
        if (decisive_rank_contract_pass(snapshot) != test.expected) {
            throw std::logic_error(
                "logic audit decisive rank state-machine mismatch for " +
                std::string(test.candidate) + "/" +
                std::string(test.state));
        }
    }
    struct CandidateAPairCase final {
        bool sampling_built{false};
        bool derivative_built{false};
        bool expected_complete{false};
    };
    constexpr std::array candidate_a_pair_cases{
        CandidateAPairCase{true, true, true},
        CandidateAPairCase{true, false, false},
        CandidateAPairCase{false, true, false},
        CandidateAPairCase{false, false, false},
    };
    for (const auto& test : candidate_a_pair_cases) {
        const auto disposition = candidate_a_pair_build_disposition(
            test.sampling_built, test.derivative_built);
        if (disposition.pair_complete != test.expected_complete ||
            disposition.sampling_rank_applicable !=
                test.expected_complete ||
            disposition.derivative_rank_applicable ||
            disposition.rank_and_gauge_evidence_allowed !=
                test.expected_complete) {
            throw std::logic_error(
                "logic audit Candidate-A pair state-machine mismatch");
        }
    }
    struct CandidateARankCase final {
        bool basis_failure{false};
        bool basis_nonfinite{false};
        bool ambiguous{false};
        std::string_view status{};
        std::string_view stage{};
        std::string_view reason{};
    };
    constexpr std::array candidate_a_rank_cases{
        CandidateARankCase{false, false, false,
            "analyzed", "NA", "NA"},
        CandidateARankCase{false, false, true,
            "ambiguous", "rank_estimation", "ambiguity_band_overlap"},
        CandidateARankCase{true, false, false,
            "numerical_failure", "basis_construction", "incomplete_kernel"},
        CandidateARankCase{true, true, false,
            "numerical_failure", "basis_construction", "nonfinite_basis"},
    };
    for (const auto& test : candidate_a_rank_cases) {
        const auto disposition = candidate_a_rank_wire_disposition(
            test.basis_failure, test.basis_nonfinite, test.ambiguous);
        if (disposition.status != test.status ||
            disposition.failure_stage != test.stage ||
            disposition.failure_reason != test.reason ||
            disposition.suppress_basis_evidence !=
                (test.basis_failure || test.ambiguous)) {
            throw std::logic_error(
                "logic audit Candidate-A rank wire state mismatch");
        }
    }
    CandidateAGaugeContract valid_a_contract{};
    valid_a_contract.observe(true, true);
    if (!valid_a_contract.pass()) {
        throw std::logic_error(
            "logic audit valid A gauge contract was rejected");
    }
    CandidateAGaugeContract failed_a_contract{};
    failed_a_contract.observe(true, true);
    failed_a_contract.observe(true, false);
    if (failed_a_contract.pass()) {
        throw std::logic_error(
            "logic audit one passing A mode hid a failed mode");
    }
    const std::array<CTriggerObservation, 1> accepted_nonrigid{{
        {true, 1U}}};
    if (!reduce_global_d_trigger(accepted_nonrigid).trigger()) {
        throw std::logic_error(
            "logic audit accepted nonrigid C did not trigger enrichment");
    }
    const std::array<CTriggerObservation, 2> mixed_c_contracts{{
        {true, 1U}, {false, 0U}}};
    if (reduce_global_d_trigger(mixed_c_contracts).trigger()) {
        throw std::logic_error(
            "logic audit invalid C failed to block global enrichment");
    }
    auto d_relation_ids = bond_relation_ids(*square);
    const auto exact_volume_ids = volume_relation_ids(*square);
    d_relation_ids.insert(d_relation_ids.end(), exact_volume_ids.begin(),
        exact_volume_ids.end());
    const auto packet_order = frozen_packet_permutation(*square);
    const auto relation_order = frozen_relation_permutation(
        *square, "D", d_relation_ids);
    std::vector<std::uint64_t> canonical_packet_order;
    for (const auto& packet : square->packets) {
        canonical_packet_order.push_back(packet.id);
    }
    std::sort(canonical_packet_order.begin(), canonical_packet_order.end());
    if (packet_order.size() > 1U && packet_order == canonical_packet_order) {
        throw std::logic_error(
            "logic audit packet permutation is not order-sensitive");
    }
    if (relation_order.size() > 1U && relation_order == d_relation_ids) {
        throw std::logic_error(
            "logic audit relation permutation is not order-sensitive");
    }
    const auto raw_d = raw_permuted_operator(d_linearized, "D",
        packet_order, d_relation_ids, relation_order);
    const auto recovered_d = canonicalize_raw_permuted_operator(raw_d,
        d_linearized, "D", packet_order, d_relation_ids, relation_order);
    if (recovered_d != d_linearized.matrix ||
        canonical_operator_hash(recovered_d) !=
            canonical_operator_hash(d_linearized.matrix)) {
        throw std::logic_error(
            "logic audit raw permutation did not canonicalize exactly");
    }
    if (raw_d == d_linearized.matrix) {
        throw std::logic_error(
            "logic audit raw permutation layout remained canonical");
    }
    const auto copied_baseline = canonicalize_raw_permuted_operator(
        d_linearized.matrix, d_linearized, "D", packet_order,
        d_relation_ids, relation_order);
    if (copied_baseline == d_linearized.matrix) {
        throw std::logic_error(
            "logic audit canonical baseline is copyable as raw evidence");
    }
    OperatorSnapshot permutation_snapshot{};
    permutation_snapshot.id = square->id + ".D";
    permutation_snapshot.configuration_id = square->id;
    permutation_snapshot.candidate = "D";
    permutation_snapshot.linearized = d_linearized;
    permutation_snapshot.normalization =
        mo::normalize_operator_rows(d_linearized.matrix);
    permutation_snapshot.diagnostics = d;
    permutation_snapshot.built = true;
    permutation_snapshot.decision_driving = true;
    permutation_snapshot.relation_ids = d_relation_ids;
    EmissionState permutation_failure{};
    permutation_failure.snapshots.emplace(
        permutation_snapshot.id, permutation_snapshot);
    permutation_failure.permutation_matches.emplace(
        permutation_snapshot.id, false);
    BundleTables permutation_failure_tables{};
    const std::array<Configuration, 1> permutation_configurations{*square};
    if (emit_invariance_evidence(permutation_failure_tables,
        permutation_failure, permutation_configurations) ||
        permutation_failure_tables.invariance.size() != 1U ||
        permutation_failure_tables.invariance.rows().front()[17] != "false" ||
        permutation_failure_tables.invariance.rows().front()[18] != "false") {
        throw std::logic_error(
            "logic audit permutation mismatch was not preserved as failure");
    }
    std::map<std::string, OperatorSnapshot> b_reducer_fixture;
    OperatorSnapshot flexible_b{};
    flexible_b.id = "flexible.B";
    flexible_b.candidate = "B";
    flexible_b.built = true;
    flexible_b.b_rank_eligible = true;
    flexible_b.decision_driving = true;
    flexible_b.generic_solid_gate = false;
    flexible_b.diagnostics.nonrigid_nullity = 1U;
    b_reducer_fixture.emplace(flexible_b.id, flexible_b);
    const auto flexible_only = reduce_scientific_b(b_reducer_fixture);
    if (flexible_only.present || flexible_only.nonrigid) {
        throw std::logic_error(
            "logic audit flexible B control drove scientific rejection");
    }
    b_reducer_fixture.begin()->second.generic_solid_gate = true;
    const auto eligible = reduce_scientific_b(b_reducer_fixture);
    if (!eligible.present || !eligible.nonrigid) {
        throw std::logic_error(
            "logic audit eligible generic B row was not reduced");
    }
    const auto filament = std::find_if(
        bases.begin(), bases.end(), [](const auto& configuration) {
            return configuration.id == "base.filament.r205.original";
        });
    if (filament == bases.end()) {
        throw std::logic_error("logic audit missing filament B control");
    }
    const auto filament_corrected = mo::build_corrected_local_gradient(
        filament->packets,
        mo::CorrectedGradientPolicy{filament->support_radius_m, 1.0e10});
    if (filament_corrected.status !=
        mo::OperatorBuildStatus::singular_local_moment) {
        throw std::logic_error(
            "logic audit filament did not reproduce singular B control");
    }
    const auto filament_facts = topology_facts(*filament);
    BundleTables flexible_b_tables{};
    EmissionState flexible_b_emission{};
    const auto flexible_b_snapshot = emit_packet_operator(
        flexible_b_tables, flexible_b_emission, *filament, filament_facts,
        "B", "corrected_local_gradient",
        std::string(mo::status_name(filament_corrected.status)),
        filament_corrected.symmetric_gradient, {}, 0U, &filament_corrected);
    if (filament_facts.generic_solid_gate ||
        flexible_b_snapshot.decision_driving ||
        !flexible_b_emission.decisive_ranks_unambiguous) {
        throw std::logic_error(
            "logic audit flexible singular B control drove global failure");
    }
    auto synthetic_generic_facts = filament_facts;
    synthetic_generic_facts.generic_solid_gate = true;
    BundleTables generic_b_tables{};
    EmissionState generic_b_emission{};
    const auto generic_b_snapshot = emit_packet_operator(
        generic_b_tables, generic_b_emission, *filament,
        synthetic_generic_facts, "B", "corrected_local_gradient",
        std::string(mo::status_name(filament_corrected.status)),
        filament_corrected.symmetric_gradient, {}, 0U, &filament_corrected);
    if (!generic_b_snapshot.decision_driving ||
        generic_b_emission.decisive_ranks_unambiguous ||
        generic_b_emission.raw_decision_all_exported) {
        throw std::logic_error(
            "logic audit generic singular B failure did not close gates");
    }
    OperatorSnapshot failed_first{};
    failed_first.build_status = "singular_local_moment";
    failed_first.failure = {"local_moment", "singular_local_moment", "1",
        "NA", "NA", "NA", "moment_diagnostics"};
    OperatorSnapshot failed_second = failed_first;
    if (!build_status_parity(failed_first, failed_second)) {
        throw std::logic_error(
            "logic audit matched failure status parity was rejected");
    }
    failed_second.failure.value_class = "finite_zero";
    if (build_status_parity(failed_first, failed_second)) {
        throw std::logic_error(
            "logic audit mismatched failure witness class passed parity");
    }
    OperatorSnapshot unavailable_c{};
    unavailable_c.id = filament->id + ".C";
    unavailable_c.configuration_id = filament->id;
    unavailable_c.candidate = "C";
    unavailable_c.build_status = "numerical_failure";
    unavailable_c.decision_driving = true;
    unavailable_c.failure = {"row_normalization", "zero_row_norm", "0",
        "NA", "0x0.0p+0", "0000000000000000", "finite_zero"};
    for (const auto& packet : filament->packets) {
        unavailable_c.linearized.packet_ids.push_back(packet.id);
    }
    std::sort(unavailable_c.linearized.packet_ids.begin(),
        unavailable_c.linearized.packet_ids.end());
    EmissionState unavailable_c_emission{};
    unavailable_c_emission.snapshots.emplace(
        unavailable_c.id, unavailable_c);
    BundleTables unavailable_c_tables{};
    const std::array<Configuration, 1> unavailable_c_configurations{
        *filament};
    if (emit_invariance_evidence(unavailable_c_tables,
            unavailable_c_emission, unavailable_c_configurations) ||
        unavailable_c_tables.invariance.size() != 1U ||
        unavailable_c_tables.invariance.rows().front()[0] !=
            "lookup_phase." + filament->id ||
        unavailable_c_tables.invariance.rows().front()[13] != "false" ||
        unavailable_c_tables.invariance.rows().front()[18] != "true") {
        throw std::logic_error(
            "logic audit unavailable C lookup parity did not force stop");
    }
    mo::DenseMatrix zero_row(1U, 3U);
    const auto zero_normalization = mo::normalize_operator_rows(zero_row);
    const auto zero_witness =
        normalization_failure_witness(zero_normalization);
    if (zero_witness.reason != "zero_row_norm" ||
        zero_witness.value != "0x0.0p+0" ||
        zero_witness.ieee754_bits != "0000000000000000" ||
        zero_witness.value_class != "finite_zero") {
        throw std::logic_error(
            "logic audit zero-row normalization witness mismatch");
    }
    const LookupPhase zero_a_phase{"p000", {}};
    const auto zero_a_operators = build_candidate_a(*filament, zero_a_phase);
    mo::DenseMatrix zero_a_matrix(
        zero_a_operators.sampling.row_count(),
        zero_a_operators.sampling.column_count());
    BundleTables zero_a_tables{};
    const auto zero_a = prepare_candidate_a_operator(zero_a_tables,
        "logic.zero.A.S", *filament, zero_a_operators.system,
        zero_a_matrix, true);
    if (zero_a.built || !zero_a.raw_exported ||
        zero_a.build_status != "numerical_failure" ||
        zero_a.failure.reason != "zero_row_norm" ||
        zero_a.failure.row != "0") {
        throw std::logic_error(
            "logic audit A normalization failure was not preserved");
    }
    mo::DenseMatrix zero_a_derivative(
        zero_a_operators.derivative.row_count(),
        zero_a_operators.derivative.column_count());
    BundleTables sampling_only_tables{};
    const auto sampling_only_sampling = prepare_candidate_a_operator(
        sampling_only_tables, "logic.sampling_only.A.S", *filament,
        zero_a_operators.system, zero_a_operators.sampling, true);
    const auto sampling_only_derivative = prepare_candidate_a_operator(
        sampling_only_tables, "logic.sampling_only.A.D", *filament,
        zero_a_operators.system, zero_a_derivative, false);
    const auto sampling_only_pair = candidate_a_pair_build_disposition(
        sampling_only_sampling.built, sampling_only_derivative.built);
    emit_candidate_a_status(sampling_only_tables,
        "logic.sampling_only.A.S", *filament,
        "negative_control_sampling", "frozen_quadratic_sampling",
        zero_a_operators.sampling, sampling_only_sampling,
        sampling_only_pair.sampling_rank_applicable);
    emit_candidate_a_status(sampling_only_tables,
        "logic.sampling_only.A.D", *filament,
        "negative_control_derivative",
        "frozen_quadratic_symmetric_gradient",
        zero_a_derivative, sampling_only_derivative,
        sampling_only_pair.derivative_rank_applicable);
    if (sampling_only_pair.pair_complete ||
        sampling_only_tables.operator_status.size() != 2U ||
        sampling_only_tables.operator_status.rows()[0][5] != "built" ||
        sampling_only_tables.operator_status.rows()[0][14] != "false" ||
        sampling_only_tables.operator_status.rows()[1][5] !=
            "numerical_failure" ||
        sampling_only_tables.operator_status.rows()[1][10] != "true" ||
        sampling_only_tables.operator_status.rows()[1][14] != "false" ||
        sampling_only_tables.operator_status.rows()[1][19] !=
            "row_normalization" ||
        sampling_only_tables.operator_status.rows()[1][20] !=
            "zero_row_norm" ||
        sampling_only_tables.operator_entries.size() == 0U ||
        sampling_only_tables.rank_status.size() != 0U ||
        sampling_only_tables.grid_gauge.size() != 0U) {
        throw std::logic_error(
            "logic audit S-built/D-failed A pair exposed rank or gauge");
    }
    BundleTables derivative_only_tables{};
    const auto derivative_only_sampling = prepare_candidate_a_operator(
        derivative_only_tables, "logic.derivative_only.A.S", *filament,
        zero_a_operators.system, zero_a_matrix, true);
    const auto derivative_only_derivative = prepare_candidate_a_operator(
        derivative_only_tables, "logic.derivative_only.A.D", *filament,
        zero_a_operators.system, zero_a_operators.derivative, false);
    const auto derivative_only_pair = candidate_a_pair_build_disposition(
        derivative_only_sampling.built, derivative_only_derivative.built);
    emit_candidate_a_status(derivative_only_tables,
        "logic.derivative_only.A.S", *filament,
        "negative_control_sampling", "frozen_quadratic_sampling",
        zero_a_matrix, derivative_only_sampling,
        derivative_only_pair.sampling_rank_applicable);
    emit_candidate_a_status(derivative_only_tables,
        "logic.derivative_only.A.D", *filament,
        "negative_control_derivative",
        "frozen_quadratic_symmetric_gradient",
        zero_a_operators.derivative, derivative_only_derivative,
        derivative_only_pair.derivative_rank_applicable);
    if (derivative_only_pair.pair_complete ||
        derivative_only_tables.operator_status.size() != 2U ||
        derivative_only_tables.operator_status.rows()[0][5] !=
            "numerical_failure" ||
        derivative_only_tables.operator_status.rows()[0][10] != "true" ||
        derivative_only_tables.operator_status.rows()[0][14] != "false" ||
        derivative_only_tables.operator_status.rows()[0][19] !=
            "row_normalization" ||
        derivative_only_tables.operator_status.rows()[0][20] !=
            "zero_row_norm" ||
        derivative_only_tables.operator_status.rows()[1][5] != "built" ||
        derivative_only_tables.operator_status.rows()[1][14] != "false" ||
        derivative_only_tables.operator_entries.size() == 0U ||
        derivative_only_tables.rank_status.size() != 0U ||
        derivative_only_tables.grid_gauge.size() != 0U) {
        throw std::logic_error(
            "logic audit D-built/S-failed A pair exposed rank or gauge");
    }
    mo::LinearizedOperator zero_relational{};
    zero_relational.kind = mo::ObservableKind::central_bond_length_rate;
    for (const auto& packet : square->packets) {
        zero_relational.packet_ids.push_back(packet.id);
    }
    std::sort(zero_relational.packet_ids.begin(),
        zero_relational.packet_ids.end());
    zero_relational.matrix = mo::DenseMatrix(
        1U, 3U * zero_relational.packet_ids.size());
    auto generic_zero_facts = topology_facts(*square);
    generic_zero_facts.generic_solid_gate = true;
    BundleTables zero_c_tables{};
    EmissionState zero_c_emission{};
    const auto zero_c = emit_packet_operator(zero_c_tables, zero_c_emission,
        *square, generic_zero_facts, "C", "central_relation_graph", "built",
        zero_relational, {"bond.1.2"}, 1U);
    if (zero_c.built || !zero_c.raw_exported ||
        zero_c.build_status != "numerical_failure" ||
        zero_c.failure.reason != "zero_row_norm" ||
        zero_c_emission.decisive_ranks_unambiguous ||
        zero_c_tables.rank_status.size() != 0U) {
        throw std::logic_error(
            "logic audit C normalization failure was not preserved as stop");
    }
    zero_relational.kind = mo::ObservableKind::enriched_bond_and_volume;
    BundleTables zero_d_tables{};
    EmissionState zero_d_emission{};
    const auto zero_d = emit_packet_operator(zero_d_tables, zero_d_emission,
        *square, generic_zero_facts, "D", "objective_volume_enrichment",
        "built", zero_relational, {"volume.1.2.3.4"}, 0U);
    if (zero_d.built || !zero_d.raw_exported ||
        zero_d.build_status != "numerical_failure" ||
        zero_d.failure.reason != "zero_row_norm" ||
        zero_d_emission.decisive_ranks_unambiguous ||
        zero_d_tables.rank_status.size() != 0U) {
        throw std::logic_error(
            "logic audit D normalization failure was not preserved as stop");
    }
    mo::DenseMatrix dilution_matrix(101U, 3U);
    std::vector<double> dilution_measured(101U, 1.0);
    std::vector<double> dilution_target(101U, 1.0);
    dilution_measured.back() = 0.0;
    const std::array<double, 3> zero_velocity{};
    const auto bond_aggregate = affine_aggregate_block(dilution_matrix,
        dilution_measured, dilution_target, zero_velocity, 0U, 100U);
    const auto volume_aggregate = affine_aggregate_block(dilution_matrix,
        dilution_measured, dilution_target, zero_velocity, 100U, 1U);
    if (!bond_aggregate.pass || volume_aggregate.pass ||
        volume_aggregate.normalized_error != 1.0) {
        throw std::logic_error(
            "logic audit D volume failure was diluted by good bond rows");
    }
    OperatorSnapshot reference{};
    reference.normalization.normalized = mo::DenseMatrix(2U, 2U);
    reference.normalization.normalized(0U, 0U) = 2.0;
    OperatorSnapshot null_tail_perturbed{};
    null_tail_perturbed.normalization.normalized = mo::DenseMatrix(2U, 2U);
    null_tail_perturbed.normalization.normalized(0U, 0U) = 2.0;
    null_tail_perturbed.normalization.normalized(1U, 1U) = 1.0e-8;
    if (scaled_singular_delta(reference, null_tail_perturbed, 1U) != 0.0) {
        throw std::logic_error(
            "logic audit rank-aware spectrum retained numerical null tail");
    }
    null_tail_perturbed.normalization.normalized(0U, 0U) = 3.0;
    const double resolved_delta =
        scaled_singular_delta(reference, null_tail_perturbed, 1U);
    if (std::abs(resolved_delta - 1.0 / 3.0) > 8.0 * epsilon64) {
        throw std::logic_error(
            "logic audit rank-aware spectrum discarded resolved value");
    }
    mo::DenseMatrix ambiguity_fixture(2U, 2U);
    ambiguity_fixture(0U, 0U) = 1.0;
    ambiguity_fixture(1U, 1U) = 512.0 * 2.0 * epsilon64;
    const auto ambiguity_rank =
        mo::diagnose_rank_and_nullspace(ambiguity_fixture);
    if (ambiguity_rank.status != mo::RankStatus::ambiguous) {
        throw std::logic_error(
            "logic audit failed to construct registered ambiguity fixture");
    }
    mo::ObservabilityDiagnostics ambiguity_diagnostics{};
    ambiguity_diagnostics.status = mo::RankStatus::ambiguous;
    ambiguity_diagnostics.operator_rank = ambiguity_rank;
    const auto ambiguity_disposition =
        rank_evidence_disposition(ambiguity_diagnostics);
    if (ambiguity_disposition.status != "ambiguous" ||
        ambiguity_disposition.failure_stage != "rank_estimation" ||
        ambiguity_disposition.failure_reason != "ambiguity_band_overlap" ||
        !ambiguity_disposition.basis_failure) {
        throw std::logic_error(
            "logic audit ambiguity evidence was not quarantined");
    }
    auto volume_inventory = full_configurations();
    std::map<std::string, std::vector<mo::VolumeRelation>>
        expected_volume_relations;
    for (const auto& configuration : volume_inventory) {
        if (configuration.variant == "original" &&
            !configuration.exact_control) {
            expected_volume_relations.emplace(configuration.base_id,
                select_volume_relations(configuration));
        }
    }
    assign_volume_relations(volume_inventory);
    for (const auto& configuration : volume_inventory) {
        if (configuration.exact_control) {
            continue;
        }
        const auto& expected =
            expected_volume_relations.at(configuration.base_id);
        if (configuration.volumes != expected) {
            throw std::logic_error(
                "logic audit D inventory escaped generic-solid gate: " +
                configuration.id);
        }
    }
    const std::map<std::uint64_t, Vec3d> unit_bond_positions{
        {1U, {}}, {2U, {1.0, 0.0, 0.0}}};
    const mo::BondRelation unit_bond{1U, 2U};
    const double unit_bond_scale = finite_bond_operand_scale(
        unit_bond_positions, unit_bond, Matrix3d::identity(), {}, 1.0,
        1.0, 1.0);
    const std::map<std::uint64_t, Vec3d> unit_tetrahedron_positions{
        {1U, {}}, {2U, {1.0, 0.0, 0.0}}, {3U, {0.0, 1.0, 0.0}},
        {4U, {0.0, 0.0, 1.0}}};
    const mo::VolumeRelation unit_volume{1U, {2U, 3U, 4U}};
    const double unit_volume_scale = finite_volume_operand_scale(
        unit_tetrahedron_positions, unit_volume, Matrix3d::identity(), {},
        1.0, 1.0, 1.0);
    if (unit_bond_scale != 4.0 || unit_volume_scale != 4.0) {
        throw std::logic_error(
            "logic audit finite operand-scale formula mismatch");
    }
    const std::vector<mo::MechanicalPacket> cancellation_packets{
        {1U, packet_mass_quanta, {}, {}},
        {2U, packet_mass_quanta, {1.0, 0.0, 0.0}, {}}};
    const Vec3d large_translation{0x1p54, 0.0, 0.0};
    const auto cancellation_transformed =
        mo::similarity_transform_packets(cancellation_packets,
            Matrix3d::identity(), large_translation, 1.0);
    const auto cancellation_reference_positions =
        packet_positions(cancellation_packets);
    const auto cancellation_transformed_positions =
        packet_positions(cancellation_transformed);
    const double cancellation_reference = std::sqrt(safe_squared_distance(
        cancellation_reference_positions.at(1U),
        cancellation_reference_positions.at(2U)));
    const double cancellation_measured = std::sqrt(safe_squared_distance(
        cancellation_transformed_positions.at(1U),
        cancellation_transformed_positions.at(2U)));
    const double cancellation_target = cancellation_reference;
    const double cancellation_error =
        std::abs(cancellation_measured - cancellation_target);
    const double cancellation_scale = finite_bond_operand_scale(
        cancellation_reference_positions, unit_bond, Matrix3d::identity(),
        large_translation, 1.0, cancellation_measured, cancellation_target);
    const double cancellation_bound = 256.0 *
            gamma_n(finite_bond_operation_count) * cancellation_scale +
        256.0 * minimum_normal64;
    const double result_only_bound = 256.0 *
            gamma_n(finite_bond_operation_count) *
            std::max({std::abs(cancellation_measured),
                std::abs(cancellation_target), minimum_normal64}) +
        256.0 * minimum_normal64;
    if (cancellation_measured != 0.0 || cancellation_error != 1.0 ||
        cancellation_scale != 0x1p55 ||
        !(cancellation_error <= cancellation_bound) ||
        !(cancellation_error > result_only_bound)) {
        throw std::logic_error(
            "logic audit large-translation cancellation scale failed");
    }
    const std::array<std::uint8_t, 2> checkpoint_a{1U, 2U};
    const std::array<std::uint8_t, 2> checkpoint_b{1U, 3U};
    if (!checkpoint_bytes_equal(checkpoint_a, checkpoint_a) ||
        checkpoint_bytes_equal(checkpoint_a, checkpoint_b)) {
        throw std::logic_error(
            "logic audit checkpoint mismatch was not preserved");
    }
    SummaryInputs checkpoint_failure_inputs{};
    checkpoint_failure_inputs.negative_control = true;
    checkpoint_failure_inputs.checkpoint_all = false;
    BundleTables checkpoint_failure_tables{};
    EmissionState checkpoint_failure_emission{};
    const std::string checkpoint_failure_summary = make_summary(
        checkpoint_failure_tables, checkpoint_failure_emission,
        checkpoint_failure_inputs);
    if (checkpoint_failure_summary.find(
            "\"checkpoint_round_trip_all_pass\": false") ==
            std::string::npos ||
        checkpoint_failure_summary.find(
            "\"decision\": \"stop_inconclusive_or_implementation_failure\"") ==
            std::string::npos) {
        throw std::logic_error(
            "logic audit checkpoint mismatch did not force stop");
    }
    SummaryInputs a_contract_failure_inputs{};
    a_contract_failure_inputs.negative_control = false;
    const std::string a_contract_failure_summary = make_summary(
        checkpoint_failure_tables, checkpoint_failure_emission,
        a_contract_failure_inputs);
    if (a_contract_failure_summary.find(
            "\"negative_control_reproduced\": false") ==
            std::string::npos ||
        a_contract_failure_summary.find(
            "\"decision\": \"stop_inconclusive_or_implementation_failure\"") ==
            std::string::npos) {
        throw std::logic_error(
            "logic audit A mode-contract failure did not force stop");
    }
    SummaryInputs rank_contract_failure_inputs{};
    rank_contract_failure_inputs.negative_control = true;
    rank_contract_failure_inputs.ranks_all = false;
    const std::string rank_contract_failure_summary = make_summary(
        checkpoint_failure_tables, checkpoint_failure_emission,
        rank_contract_failure_inputs);
    if (rank_contract_failure_summary.find(
            "\"decisive_rank_rows_all_unambiguous\": false") ==
            std::string::npos ||
        rank_contract_failure_summary.find(
            "\"decision\": \"stop_inconclusive_or_implementation_failure\"") ==
            std::string::npos) {
        throw std::logic_error(
            "logic audit C rank-contract failure did not force stop");
    }
    std::cout << "Mechanical Observability logic audit: PASS\n";
}

void run_producer(
    RunMode mode, CandidateAFailureFixture failure_fixture,
    const std::filesystem::path& output_directory) {
    const bool fixture_mode = mode == RunMode::failure_fixture;
    if (fixture_mode !=
        (failure_fixture != CandidateAFailureFixture::none)) {
        throw std::invalid_argument(
            "failure-fixture mode requires exactly one A half");
    }
    const bool reduced_inventory = mode != RunMode::full;
    auto configurations_value = configurations(reduced_inventory);
    const auto d_trigger = assess_global_d_trigger(configurations_value);
    if (d_trigger.trigger()) {
        assign_volume_relations(configurations_value);
    }

    BundleTables tables{};
    EmissionState emission{};
    SummaryInputs summary{};
    summary.mode = mode;
    bool candidate_a_seen = false;
    bool candidate_a_all_pass = true;
    std::size_t failure_fixture_count = 0U;
    for (const auto& configuration : configurations_value) {
        const auto input = emit_configuration_inputs(tables, configuration);
        summary.checkpoint_all = summary.checkpoint_all &&
            input.checkpoint_round_trip;
        summary.neighbor_all = summary.neighbor_all && input.neighbor_agreement;
        emit_bcd_operators(tables, emission, configuration);
        if (configuration.candidate_a_representative &&
            configuration.variant == "original") {
            for (const auto& phase : lookup_phases) {
                const bool fixture_target = fixture_mode &&
                    configuration.id ==
                        "base.filament.r205.original" &&
                    phase.id == "p000";
                const auto pair_failure = fixture_target
                    ? failure_fixture : CandidateAFailureFixture::none;
                const auto a = emit_candidate_a_pair(
                    tables, configuration, phase, pair_failure);
                failure_fixture_count += fixture_target ? 1U : 0U;
                candidate_a_seen = true;
                candidate_a_all_pass = candidate_a_all_pass &&
                    a.negative_control_reproduced;
                emission.decisive_ranks_unambiguous =
                    emission.decisive_ranks_unambiguous &&
                    a.ranks_unambiguous;
                emission.raw_decision_all_exported =
                    emission.raw_decision_all_exported &&
                    a.raw_decision_exported;
            }
        }
        mo::MechanicalObservabilityState state{};
        state.support_radius_m = configuration.support_radius_m;
        state.packets = configuration.packets;
        state.bonds = retained_bonds(configuration);
        state.volumes = configuration.volumes;
        const auto after = mo::serialize_mechanical_observability_state(state);
        const bool read_only = checkpoint_bytes_equal(
            after, input.checkpoint_before);
        summary.read_only_all = summary.read_only_all && read_only;
        emit_configuration_row(tables, configuration, input, after);
    }
    if (fixture_mode && failure_fixture_count != 1U) {
        throw std::logic_error(
            "A pair failure fixture target count is not exactly one");
    }
    summary.negative_control = candidate_a_seen && candidate_a_all_pass;
    emit_exact_references(tables, configurations_value);
    summary.invariance_all = emit_invariance_evidence(
        tables, emission, configurations_value);
    summary.affine_all = emission.affine_all_pass;
    summary.finite_all = emission.finite_all_pass;
    summary.raw_all = emission.raw_decision_all_exported;
    summary.exact_all = !tables.exact_reference.rows().empty() &&
        std::ranges::all_of(tables.exact_reference.rows(),
            [](const Row& row) { return row[15] == "true"; });
    summary.ranks_all = emission.decisive_ranks_unambiguous &&
        summary.exact_all;
    sort_tables(tables);
    const std::string summary_text = make_summary(tables, emission, summary);
    write_bundle(output_directory, tables, summary_text);
    if (mode == RunMode::failure_fixture) {
        std::cout << "Mechanical Observability provisional A-pair failure "
                     "fixture written: "
                  << output_directory.string() << '\n';
    } else if (mode == RunMode::smoke) {
        std::cout << "Mechanical Observability provisional smoke evidence written: "
                  << output_directory.string() << '\n';
    } else {
        std::cout << "Mechanical Observability evidence written: "
                  << output_directory.string() << '\n';
    }
}

struct Options final {
    bool smoke{false};
    bool schema{false};
    bool logic{false};
    CandidateAFailureFixture failure_fixture{
        CandidateAFailureFixture::none};
    std::optional<std::filesystem::path> output{};
};

[[nodiscard]] Options parse_options(int argc, char** argv) {
    Options result{};
    for (int index = 1; index < argc; ++index) {
        const std::string_view argument(argv[index]);
        if (argument == "--smoke") {
            result.smoke = true;
        } else if (argument == "--a-pair-failure-fixture") {
            if (++index >= argc || result.failure_fixture !=
                    CandidateAFailureFixture::none) {
                throw std::invalid_argument(
                    "--a-pair-failure-fixture requires one unique half");
            }
            const std::string_view half(argv[index]);
            if (half == "sampling") {
                result.failure_fixture =
                    CandidateAFailureFixture::sampling;
            } else if (half == "derivative") {
                result.failure_fixture =
                    CandidateAFailureFixture::derivative;
            } else {
                throw std::invalid_argument(
                    "A-pair failure fixture half must be sampling or derivative");
            }
        } else if (argument == "--schema-audit") {
            result.schema = true;
        } else if (argument == "--logic-audit") {
            result.logic = true;
        } else if (argument == "--output") {
            if (++index >= argc || result.output.has_value()) {
                throw std::invalid_argument("--output requires one unique path");
            }
            result.output = std::filesystem::path(argv[index]);
        } else {
            throw std::invalid_argument("unknown option: " + std::string(argument));
        }
    }
    if (!valid_option_shape(result.smoke,
            result.failure_fixture != CandidateAFailureFixture::none,
            result.schema, result.logic, result.output.has_value())) {
        throw std::invalid_argument(
            "usage: mls_mechanical_observability_diagnostic "
            "[--smoke --output DIR | --a-pair-failure-fixture "
            "{sampling,derivative} --output DIR | --output DIR | "
            "--schema-audit | --logic-audit]");
    }
    return result;
}

} // namespace

int main(int argc, char** argv) {
    try {
        const auto options = parse_options(argc, argv);
        if (options.schema) {
            schema_audit();
        } else if (options.logic) {
            logic_audit();
        } else {
            const RunMode mode = options.failure_fixture !=
                    CandidateAFailureFixture::none
                ? RunMode::failure_fixture
                : (options.smoke ? RunMode::smoke : RunMode::full);
            run_producer(mode, options.failure_fixture, *options.output);
        }
        return EXIT_SUCCESS;
    } catch (const std::exception& error) {
        std::cerr << "Mechanical Observability diagnostic failed: "
                  << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
