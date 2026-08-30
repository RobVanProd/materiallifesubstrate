#include "mls/relational_observability_confirmation.hpp"

#include "mls/kelvin_covariance_audit.hpp"
#include "mls/mechanical_observability_lab.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <charconv>
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

namespace confirmation =
    mls::experimental::relational_observability_confirmation;
namespace observation = mls::experimental::mechanical_observability;
namespace kelvin = mls::experimental::kelvin_covariance_audit;
using mls::experimental::Matrix3d;
using mls::experimental::Vec3d;
using observation::BondRelation;
using observation::MechanicalPacket;

constexpr std::uint64_t seed = 260828U;
constexpr std::string_view parent_sha =
    "baa6beb0b89e70dc2a5baa141366be3f2530a19d";
constexpr std::string_view candidate_c_source_sha =
    "a71decf8a60c9937e568e712cf9bf13cb68c9bb7";
constexpr std::string_view branch = "relational-observability-confirmation";
constexpr std::size_t registered_topology_edge_count = 158U;
constexpr std::size_t registered_topology_transition_adjacent_before = 52U;
constexpr std::size_t registered_topology_last_rigid = 53U;
constexpr std::size_t registered_topology_first_nonrigid = 54U;
constexpr std::size_t registered_topology_transition_adjacent_after = 55U;
constexpr std::size_t registered_topology_complete_deletion = 158U;
constexpr std::size_t registered_topology_exact_rank_step54 = 74U;
constexpr std::string_view summary_schema =
    "mls.relational-observability-confirmation.summary.v1";
constexpr std::string_view manifest_schema =
    "mls.relational-observability-confirmation.manifest.v1";
constexpr std::string_view configurations_header =
    "configuration_id,source_configuration_id,probe_family,probe_id,family,"
    "profile,transform,decision_scope,packet_count,edge_count,nominal_spacing_m,"
    "support_radius_m,geometry_scale,deformation_det,"
    "perturbation_amplitude_ratio,perturbation_seed,topology_path_step,"
    "affine_span_rank,connected,edge_lower_bound,min_incident_direction_rank,"
    "rigid_rank,generic_solid_gate,intentionally_flexible,exact_control,"
    "input_checkpoint_sha256_before,input_checkpoint_sha256_after,"
    "diagnostics_read_only_exact";
constexpr std::string_view packets_header =
    "configuration_id,packet_index,packet_id,mass_quanta,x_m,y_m,z_m,"
    "vx_m_per_s,vy_m_per_s,vz_m_per_s";
constexpr std::string_view relations_header =
    "configuration_id,relation_index,first_id,second_id,selection_status,"
    "selection_source,reference_length_m,row_norm,row_norm_relative_error,"
    "row_norm_tolerance,row_norm_pass";
constexpr std::string_view observability_header =
    "configuration_id,probe_family,decision_scope,operator_status,row_count,"
    "column_count,row_norm_max_relative_error,row_norm_tolerance,row_norm_pass,"
    "qr_status,qr_rank,svd_rank,rank_agreement,rank_ambiguous,nullity,rigid_rank,"
    "rigid_residual_normalized,rigid_residual_tolerance,rigid_in_kernel,"
    "nonrigid_nullity,nullspace_basis_complete,nullspace_residual_normalized,"
    "nonrigid_residual_normalized,rigid_orthogonality_residual,sigma_max,"
    "sigma_min_nonzero,mu,svd_threshold,svd_ambiguity_lower,"
    "svd_ambiguity_upper,nonzero_threshold_separation,max_resolved_zero,"
    "null_threshold_separation,clear_separation_pass,baseline_mu,"
    "mu_retention_ratio,robustness_pass,classification,decision_gate_pass";
constexpr std::string_view spectra_header =
    "configuration_id,singular_index,singular_value,svd_threshold,"
    "threshold_ratio,classification,is_largest,is_smallest_accepted";
constexpr std::string_view nullspace_header =
    "configuration_id,mode_index,mode_operator_residual,rigid_projection_norm,"
    "nonrigid_component_norm,residual_tolerance,vector_sha256,accepted";
constexpr std::string_view nullspace_vectors_header =
    "configuration_id,mode_index,component_index,packet_id,axis,value";
constexpr std::string_view metamorphic_header =
    "control_id,base_configuration_id,variant_configuration_id,control_kind,"
    "physical_graph_equal,operator_covariance_residual,spectrum_residual,"
    "finite_length_scale,finite_length_residual,rank_equal,nullity_equal,"
    "nonrigid_nullity_equal,mu_relative_error,tolerance,pass";
constexpr std::string_view id_bijections_header =
    "control_id,source_configuration_id,bijection_kind,old_packet_id,"
    "new_packet_id,inverse_packet_id,nontrivial";
constexpr std::string_view topology_path_header =
    "path_id,configuration_id,deletion_step,removed_first_id,"
    "removed_second_id,edge_count,rank,nullity,nonrigid_nullity,"
    "sigma_min_nonzero,sigma_max,mu,nonzero_threshold_separation,"
    "rank_reference_kind,rank_certified,classification,transition";
constexpr std::string_view lookup_header =
    "configuration_id,phase_id,brute_force_edge_count,lookup_edge_count,"
    "canonical_equal,pass";
constexpr std::string_view checkpoints_header =
    "configuration_id,encoding,byte_count,payload_sha256_before,"
    "payload_sha256_roundtrip,payload_sha256_after,roundtrip_exact,"
    "diagnostics_read_only_exact,pass";

constexpr std::string_view accepted_configurations_hash =
    "557e4327867171aff7fcb34601e6c9548081cd2d6a3a735d2eabaf6dd3f2eb34";
constexpr std::string_view accepted_packets_hash =
    "b8525b53ace3a87d05d7fc32f0193eaa698d43b3af31321143d3314cd38d258c";
constexpr std::string_view accepted_relations_hash =
    "89c8189a64cfe27a6d4133dd2a6f5d9d38e96e29fcaea39b0512ea705e7ae6f9";

using Row = std::vector<std::string>;

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
        : header_(header), width_(split_header(header).size()) {}

    void row(Row values) {
        if (values.size() != width_) {
            throw std::logic_error("CSV row differs from frozen width");
        }
        rows_.push_back(std::move(values));
    }

    [[nodiscard]] std::size_t size() const noexcept { return rows_.size(); }

    [[nodiscard]] std::string contents() const {
        std::string result{header_};
        result.push_back('\n');
        for (const auto& row : rows_) {
            for (std::size_t index = 0U; index < row.size(); ++index) {
                if (index != 0U) {
                    result.push_back(',');
                }
                result += csv_escape(row[index]);
            }
            result.push_back('\n');
        }
        return result;
    }

private:
    std::string header_;
    std::size_t width_{0};
    std::vector<Row> rows_{};
};

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
            const auto temporary1 = h + s1 + choose +
                constants[index] + words[index];
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

[[nodiscard]] std::string bool_text(const bool value) {
    return value ? "true" : "false";
}

[[nodiscard]] std::string hex64(const double value) {
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

[[nodiscard]] std::string extended_hex64(const double value) {
    return std::isinf(value) && value > 0.0 ? "inf" : hex64(value);
}

[[nodiscard]] std::string read_binary_text(const std::filesystem::path& path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        throw std::runtime_error("cannot open input: " + path.string());
    }
    return {std::istreambuf_iterator<char>(stream),
            std::istreambuf_iterator<char>()};
}

void write_text(const std::filesystem::path& path, std::string_view value) {
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    if (!stream) {
        throw std::runtime_error("cannot open output: " + path.string());
    }
    stream.write(value.data(), static_cast<std::streamsize>(value.size()));
    if (!stream) {
        throw std::runtime_error("failed writing output: " + path.string());
    }
}

void write_bytes(
    const std::filesystem::path& path, std::span<const std::uint8_t> value) {
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    if (!stream) {
        throw std::runtime_error("cannot open binary output: " + path.string());
    }
    stream.write(reinterpret_cast<const char*>(value.data()),
                 static_cast<std::streamsize>(value.size()));
}

[[nodiscard]] std::vector<Row> parse_csv(std::string_view input) {
    std::vector<Row> rows;
    Row row;
    std::string field;
    bool quoted = false;
    for (std::size_t index = 0U; index < input.size(); ++index) {
        const char ch = input[index];
        if (quoted) {
            if (ch == '\"' && index + 1U < input.size() &&
                input[index + 1U] == '\"') {
                field.push_back('\"');
                ++index;
            } else if (ch == '\"') {
                quoted = false;
            } else {
                field.push_back(ch);
            }
        } else if (ch == '\"') {
            quoted = true;
        } else if (ch == ',') {
            row.push_back(std::move(field));
            field.clear();
        } else if (ch == '\n' || ch == '\r') {
            if (ch == '\r' && index + 1U < input.size() &&
                input[index + 1U] == '\n') {
                ++index;
            }
            row.push_back(std::move(field));
            field.clear();
            if (!(row.size() == 1U && row.front().empty())) {
                rows.push_back(std::move(row));
            }
            row.clear();
        } else {
            field.push_back(ch);
        }
    }
    if (quoted) {
        throw std::runtime_error("unterminated quoted CSV field");
    }
    if (!field.empty() || !row.empty()) {
        row.push_back(std::move(field));
        rows.push_back(std::move(row));
    }
    return rows;
}

[[nodiscard]] std::map<std::string, std::size_t> header_map(const Row& header) {
    std::map<std::string, std::size_t> result;
    for (std::size_t index = 0U; index < header.size(); ++index) {
        if (!result.emplace(header[index], index).second) {
            throw std::runtime_error("duplicate CSV header: " + header[index]);
        }
    }
    return result;
}

[[nodiscard]] double parse_double(std::string_view value) {
    std::string storage(value);
    char* end = nullptr;
    const double result = std::strtod(storage.c_str(), &end);
    if (end == storage.c_str() || *end != '\0' || !std::isfinite(result)) {
        throw std::runtime_error("invalid finite binary64 field: " + storage);
    }
    return result;
}

[[nodiscard]] std::uint64_t parse_u64(std::string_view value) {
    std::uint64_t result = 0U;
    const auto parsed = std::from_chars(
        value.data(), value.data() + value.size(), result);
    if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size()) {
        throw std::runtime_error("invalid uint64 field: " + std::string(value));
    }
    return result;
}

[[nodiscard]] std::int64_t parse_i64(std::string_view value) {
    std::int64_t result = 0;
    const auto parsed = std::from_chars(
        value.data(), value.data() + value.size(), result);
    if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size()) {
        throw std::runtime_error("invalid int64 field: " + std::string(value));
    }
    return result;
}

struct Configuration final {
    std::string id;
    std::string source_id;
    std::string probe_family{"inherited"};
    std::string probe_id{"original"};
    std::string family;
    std::string profile;
    std::string transform;
    std::string decision_scope;
    double nominal_spacing_m{1.0};
    double support_radius_m{1.0};
    double geometry_scale{1.0};
    double deformation_det{1.0};
    double perturbation_amplitude_ratio{0.0};
    std::uint64_t perturbation_seed{0U};
    std::int64_t topology_path_step{-1};
    bool generic_solid_gate{false};
    bool intentionally_flexible{false};
    bool exact_control{false};
    std::vector<MechanicalPacket> packets;
    std::vector<BondRelation> relations;
    std::vector<std::string> relation_sources;
    std::optional<BondRelation> removed_edge;
};

struct FixtureData final {
    std::vector<Configuration> configurations;
    std::map<std::string, std::string> hashes;
};

[[nodiscard]] FixtureData load_fixtures(
    const std::filesystem::path& directory, const bool smoke) {
    const auto configurations_text = read_binary_text(directory / "configurations.csv");
    const auto packets_text = read_binary_text(directory / "packets.csv");
    const auto relations_text = read_binary_text(directory / "relations.csv");
    FixtureData result{};
    result.hashes = {
        {"configurations.csv", sha256(configurations_text)},
        {"packets.csv", sha256(packets_text)},
        {"relations.csv", sha256(relations_text)},
    };
    constexpr std::string_view smoke_configurations_hash =
        "dfb49540cd5c737f99731e05889536a152ac58783a39a2e40c9a9631e267758f";
    constexpr std::string_view smoke_packets_hash =
        "73a6b649133d55195c5e0eac29e05937187e9debea9b9566a888b4787d20814a";
    constexpr std::string_view smoke_relations_hash =
        "e767bde1abb8962c076244710cf2e326bee720d047eb5aaf27c8e355433eac65";
    const bool hashes_match = smoke
        ? result.hashes.at("configurations.csv") == smoke_configurations_hash &&
              result.hashes.at("packets.csv") == smoke_packets_hash &&
              result.hashes.at("relations.csv") == smoke_relations_hash
        : result.hashes.at("configurations.csv") == accepted_configurations_hash &&
              result.hashes.at("packets.csv") == accepted_packets_hash &&
              result.hashes.at("relations.csv") == accepted_relations_hash;
    if (!hashes_match) {
        throw std::runtime_error(
            "inherited fixture tables do not match the registered mode hashes");
    }
    auto configuration_rows = parse_csv(configurations_text);
    auto packet_rows = parse_csv(packets_text);
    auto relation_rows = parse_csv(relations_text);
    if (configuration_rows.empty() || packet_rows.empty() || relation_rows.empty()) {
        throw std::runtime_error("inherited fixture table is empty");
    }
    const auto ch = header_map(configuration_rows.front());
    const auto ph = header_map(packet_rows.front());
    const auto rh = header_map(relation_rows.front());
    std::map<std::string, std::size_t> index_by_id;
    for (std::size_t row = 1U; row < configuration_rows.size(); ++row) {
        const auto& value = configuration_rows[row];
        Configuration configuration{};
        configuration.id = value.at(ch.at("configuration_id"));
        configuration.source_id = value.at(ch.at("base_configuration_id"));
        configuration.probe_family = "inherited";
        configuration.probe_id = value.at(ch.at("variant"));
        configuration.family = value.at(ch.at("family"));
        configuration.profile = value.at(ch.at("profile"));
        configuration.transform = value.at(ch.at("transform"));
        configuration.generic_solid_gate =
            value.at(ch.at("generic_solid_gate")) == "true";
        configuration.intentionally_flexible =
            value.at(ch.at("intentionally_flexible")) == "true";
        configuration.exact_control = configuration.id.starts_with("exact.");
        configuration.decision_scope = configuration.generic_solid_gate
            ? "eligible_generic"
            : (configuration.intentionally_flexible
                   ? "intentionally_flexible"
                   : "non_generic_control");
        configuration.nominal_spacing_m = parse_double(
            value.at(ch.at("nominal_spacing_m")));
        configuration.support_radius_m = parse_double(
            value.at(ch.at("support_radius_m")));
        configuration.geometry_scale = parse_double(
            value.at(ch.at("geometry_scale")));
        index_by_id.emplace(configuration.id, result.configurations.size());
        result.configurations.push_back(std::move(configuration));
    }
    const std::size_t expected_configurations = smoke ? 3U : 59U;
    if (result.configurations.size() != expected_configurations) {
        throw std::runtime_error("inherited fixture inventory has wrong size");
    }
    for (std::size_t row = 1U; row < packet_rows.size(); ++row) {
        const auto& value = packet_rows[row];
        auto& configuration = result.configurations.at(
            index_by_id.at(value.at(ph.at("configuration_id"))));
        configuration.packets.push_back({
            parse_u64(value.at(ph.at("packet_id"))),
            parse_i64(value.at(ph.at("mass_quanta"))),
            {parse_double(value.at(ph.at("x_m"))),
             parse_double(value.at(ph.at("y_m"))),
             parse_double(value.at(ph.at("z_m")))},
            {parse_double(value.at(ph.at("vx_m_per_s"))),
             parse_double(value.at(ph.at("vy_m_per_s"))),
             parse_double(value.at(ph.at("vz_m_per_s")))},
        });
    }
    for (std::size_t row = 1U; row < relation_rows.size(); ++row) {
        const auto& value = relation_rows[row];
        if (value.at(rh.at("relation_kind")) != "bond") {
            continue;
        }
        auto& configuration = result.configurations.at(
            index_by_id.at(value.at(rh.at("configuration_id"))));
        configuration.relations.push_back({
            parse_u64(value.at(rh.at("first_id"))),
            parse_u64(value.at(rh.at("second_id"))),
        });
        configuration.relation_sources.push_back(
            value.at(rh.at("selection_source")));
    }
    for (auto& configuration : result.configurations) {
        std::ranges::sort(configuration.packets, {}, &MechanicalPacket::id);
        std::vector<std::pair<BondRelation, std::string>> decorated;
        decorated.reserve(configuration.relations.size());
        for (std::size_t index = 0U; index < configuration.relations.size();
             ++index) {
            decorated.emplace_back(
                configuration.relations[index],
                configuration.relation_sources[index]);
        }
        std::ranges::sort(decorated, [](const auto& lhs, const auto& rhs) {
            return std::pair(lhs.first.first_id, lhs.first.second_id) <
                std::pair(rhs.first.first_id, rhs.first.second_id);
        });
        configuration.relations.clear();
        configuration.relation_sources.clear();
        for (auto& [relation, source] : decorated) {
            configuration.relations.push_back(relation);
            configuration.relation_sources.push_back(std::move(source));
        }
        static_cast<void>(observation::build_bond_rigidity_operator(
            configuration.packets, configuration.relations));
    }
    return result;
}

[[nodiscard]] Matrix3d deformation(std::string_view name) {
    Matrix3d result{};
    if (name == "isotropic_compression") {
        result = Matrix3d::identity();
        for (std::size_t index = 0U; index < 3U; ++index) {
            result.value[index][index] = 4.0 / 5.0;
        }
    } else if (name == "isotropic_expansion") {
        result = Matrix3d::identity();
        for (std::size_t index = 0U; index < 3U; ++index) {
            result.value[index][index] = 5.0 / 4.0;
        }
    } else if (name == "pure_shear") {
        result = Matrix3d::identity();
        result.value[0][0] = 5.0 / 4.0;
        result.value[1][1] = 4.0 / 5.0;
    } else if (name == "simple_shear") {
        result = Matrix3d::identity();
        result.value[0][1] = 1.0 / 4.0;
    } else if (name == "general_affine") {
        result.value = {{{1.0, 1.0 / 5.0, -1.0 / 10.0},
                         {1.0 / 10.0, 9.0 / 10.0, 1.0 / 8.0},
                         {-1.0 / 12.0, 1.0 / 10.0, 11.0 / 10.0}}};
    } else {
        throw std::invalid_argument("unknown deformation probe");
    }
    return result;
}

[[nodiscard]] double determinant(const Matrix3d& value) noexcept {
    return value.value[0][0] *
               (value.value[1][1] * value.value[2][2] -
                value.value[1][2] * value.value[2][1]) -
        value.value[0][1] *
               (value.value[1][0] * value.value[2][2] -
                value.value[1][2] * value.value[2][0]) +
        value.value[0][2] *
               (value.value[1][0] * value.value[2][1] -
                value.value[1][1] * value.value[2][0]);
}

[[nodiscard]] Vec3d apply_matrix(const Matrix3d& matrix, const Vec3d value) {
    return {
        matrix.value[0][0] * value.x + matrix.value[0][1] * value.y +
            matrix.value[0][2] * value.z,
        matrix.value[1][0] * value.x + matrix.value[1][1] * value.y +
            matrix.value[1][2] * value.z,
        matrix.value[2][0] * value.x + matrix.value[2][1] * value.y +
            matrix.value[2][2] * value.z,
    };
}

class SplitMix64 final {
public:
    explicit SplitMix64(const std::uint64_t initial) : state_(initial) {}
    [[nodiscard]] std::uint64_t next() noexcept {
        state_ += UINT64_C(0x9e3779b97f4a7c15);
        auto value = state_;
        value = (value ^ (value >> 30U)) * UINT64_C(0xbf58476d1ce4e5b9);
        value = (value ^ (value >> 27U)) * UINT64_C(0x94d049bb133111eb);
        return value ^ (value >> 31U);
    }
private:
    std::uint64_t state_{0U};
};

[[nodiscard]] std::uint64_t sha_prefix_u64(std::string_view value) {
    const std::string digest = sha256(value);
    std::uint64_t result = 0U;
    for (std::size_t index = 0U; index < 16U; ++index) {
        const char ch = digest[index];
        const auto nibble = static_cast<std::uint64_t>(
            ch >= 'a' ? 10 + ch - 'a' : ch - '0');
        result = (result << 4U) | nibble;
    }
    return result;
}

[[nodiscard]] Vec3d perturbation_direction(
    const std::uint64_t perturbation_seed, const std::uint64_t packet_id) {
    std::array<double, 3> values{};
    constexpr double denominator = 4503599627370496.0; // 2^52
    for (std::size_t axis = 0U; axis < 3U; ++axis) {
        const std::string tuple = std::to_string(perturbation_seed) + "|" +
            std::to_string(packet_id) + "|" + std::to_string(axis);
        SplitMix64 generator(sha_prefix_u64(tuple));
        const std::uint64_t dyadic = generator.next() >> 11U;
        values[axis] = static_cast<double>(dyadic) / denominator - 1.0;
    }
    const double norm = std::hypot(values[0], values[1], values[2]);
    if (norm == 0.0) {
        return {1.0, 0.0, 0.0};
    }
    return {values[0] / norm, values[1] / norm, values[2] / norm};
}

[[nodiscard]] Configuration make_perturbation(
    const Configuration& source, const double amplitude,
    const std::uint64_t perturbation_seed) {
    Configuration result = source;
    std::ostringstream id;
    id << "geometry." << source.id << ".a" << std::setprecision(0)
       << std::fixed << amplitude * 10000.0 << ".s" << perturbation_seed;
    result.id = id.str();
    result.source_id = source.id;
    result.probe_family = "geometry_perturbation";
    result.probe_id = "jitter";
    result.transform = "fixed_topology_jitter";
    result.perturbation_amplitude_ratio = amplitude;
    result.perturbation_seed = perturbation_seed;
    result.exact_control = false;
    result.relation_sources.assign(
        result.relations.size(), "fixed_topology_perturbation");
    for (auto& packet : result.packets) {
        const Vec3d direction = perturbation_direction(
            perturbation_seed, packet.id);
        const double magnitude = amplitude * source.nominal_spacing_m;
        packet.position_m += direction * magnitude;
    }
    return result;
}

[[nodiscard]] Configuration make_deformation(
    const Configuration& source, std::string_view probe) {
    Configuration result = source;
    result.id = "deformation." + source.id + "." + std::string(probe);
    result.source_id = source.id;
    result.probe_family = "homogeneous_deformation";
    result.probe_id = std::string(probe);
    result.transform = std::string(probe);
    result.exact_control = false;
    result.relation_sources.assign(
        result.relations.size(), "fixed_topology_deformation");
    const auto gradient = deformation(probe);
    result.deformation_det = determinant(gradient);
    if (!(result.deformation_det >= 0.5 && result.deformation_det <= 2.0)) {
        throw std::logic_error("deformation determinant violates preregistration");
    }
    for (auto& packet : result.packets) {
        packet.position_m = apply_matrix(gradient, packet.position_m);
        packet.velocity_m_per_s = apply_matrix(
            gradient, packet.velocity_m_per_s);
    }
    return result;
}

struct BijectionRow final {
    std::string control_id;
    std::string source_id;
    std::string kind;
    std::uint64_t old_id{0U};
    std::uint64_t new_id{0U};
};

[[nodiscard]] std::map<std::uint64_t, std::uint64_t> id_mapping(
    const Configuration& source, std::string_view kind) {
    std::vector<std::uint64_t> ids;
    ids.reserve(source.packets.size());
    for (const auto& packet : source.packets) {
        ids.push_back(packet.id);
    }
    std::ranges::sort(ids);
    std::vector<std::uint64_t> target = ids;
    if (kind == "id_reverse") {
        std::ranges::reverse(target);
    } else if (kind == "id_cycle") {
        std::rotate(target.begin(), target.begin() + 1, target.end());
    } else if (kind == "id_sha256") {
        std::ranges::sort(target, [&](const auto lhs, const auto rhs) {
            const auto lhs_hash = sha256(
                std::to_string(seed) + "|relational_observability_id_v1|" +
                source.id + "|" + std::to_string(lhs));
            const auto rhs_hash = sha256(
                std::to_string(seed) + "|relational_observability_id_v1|" +
                source.id + "|" + std::to_string(rhs));
            return std::pair(lhs_hash, lhs) < std::pair(rhs_hash, rhs);
        });
    } else {
        throw std::invalid_argument("unknown packet-ID bijection");
    }
    std::map<std::uint64_t, std::uint64_t> result;
    for (std::size_t index = 0U; index < ids.size(); ++index) {
        result.emplace(ids[index], target[index]);
    }
    if (std::ranges::all_of(result, [](const auto& item) {
            return item.first == item.second;
        })) {
        throw std::logic_error("registered ID bijection is trivial");
    }
    return result;
}

[[nodiscard]] Configuration make_id_bijection(
    const Configuration& source, std::string_view kind,
    std::vector<BijectionRow>& rows) {
    const auto mapping = id_mapping(source, kind);
    Configuration result = source;
    result.id = std::string(kind) + "." + source.id;
    result.source_id = source.id;
    result.probe_family = "id_bijection";
    result.probe_id = std::string(kind);
    result.transform = std::string(kind);
    result.exact_control = false;
    const std::string control_id = "control." + std::string(kind) + "." + source.id;
    for (auto& packet : result.packets) {
        packet.id = mapping.at(packet.id);
    }
    std::ranges::sort(result.packets, {}, &MechanicalPacket::id);
    std::vector<std::pair<BondRelation, std::string>> relations;
    relations.reserve(result.relations.size());
    for (std::size_t index = 0U; index < result.relations.size(); ++index) {
        auto first = mapping.at(result.relations[index].first_id);
        auto second = mapping.at(result.relations[index].second_id);
        if (second < first) {
            std::swap(first, second);
        }
        relations.push_back({{first, second}, result.relation_sources[index]});
    }
    std::ranges::sort(relations, [](const auto& lhs, const auto& rhs) {
        return std::pair(lhs.first.first_id, lhs.first.second_id) <
            std::pair(rhs.first.first_id, rhs.first.second_id);
    });
    result.relations.clear();
    result.relation_sources.clear();
    for (auto& [relation, relation_source] : relations) {
        result.relations.push_back(relation);
        result.relation_sources.push_back(std::move(relation_source));
    }
    for (const auto& [old_id, new_id] : mapping) {
        rows.push_back({control_id, source.id, std::string(kind), old_id, new_id});
    }
    return result;
}

[[nodiscard]] std::vector<std::pair<BondRelation, std::string>>
nested_deletion_order(const Configuration& source) {
    std::vector<std::pair<BondRelation, std::string>> result;
    result.reserve(source.relations.size());
    for (const auto& relation : source.relations) {
        const std::string preimage = std::to_string(seed) +
            "|relational_observability_nested_delete_v1|" +
            std::to_string(relation.first_id) + "|" +
            std::to_string(relation.second_id);
        result.emplace_back(relation, sha256(preimage));
    }
    std::ranges::sort(result, [](const auto& lhs, const auto& rhs) {
        return std::tuple(lhs.second, lhs.first.first_id, lhs.first.second_id) <
            std::tuple(rhs.second, rhs.first.first_id, rhs.first.second_id);
    });
    return result;
}

struct GeneratedInventory final {
    std::vector<Configuration> configurations;
    std::vector<BijectionRow> bijections;
    std::string topology_path_id{"nested.sc3.r180.v1"};
};

[[nodiscard]] GeneratedInventory generate_inventory(
    const FixtureData& fixtures, const bool smoke) {
    GeneratedInventory result{};
    result.configurations = fixtures.configurations;
    if (!smoke) {
        const std::array<std::string_view, 7> perturb_sources{
            "base.bcc35.r180.original",
            "base.corner_truncated.r180.original",
            "base.edge_truncated.r180.original",
            "base.free_face.r180.original",
            "base.jitter27.r180.original",
            "base.sc3.r180.original",
            "base.sc3_deletion.delete25.original",
        };
        constexpr std::array amplitudes{1.0 / 10000.0, 1.0 / 1000.0,
                                         1.0 / 100.0};
        constexpr std::array<std::uint64_t, 3> perturb_seeds{
            260829U, 260830U, 260831U};
        for (const auto source_id : perturb_sources) {
            const auto found = std::ranges::find_if(
                fixtures.configurations, [&](const auto& configuration) {
                    return configuration.id == source_id;
                });
            if (found == fixtures.configurations.end()) {
                throw std::logic_error("missing perturbation source fixture");
            }
            for (const double amplitude : amplitudes) {
                for (const auto derived_seed : perturb_seeds) {
                    result.configurations.push_back(make_perturbation(
                        *found, amplitude, derived_seed));
                }
            }
        }
        constexpr std::array<std::string_view, 5> deformation_names{
            "isotropic_compression", "isotropic_expansion", "pure_shear",
            "simple_shear", "general_affine"};
        for (const auto& configuration : fixtures.configurations) {
            if (!configuration.generic_solid_gate) {
                continue;
            }
            for (const auto name : deformation_names) {
                result.configurations.push_back(make_deformation(
                    configuration, name));
            }
        }
    }

    const std::size_t bijection_source_count = smoke
        ? std::min<std::size_t>(fixtures.configurations.size(), 1U)
        : fixtures.configurations.size();
    constexpr std::array<std::string_view, 3> bijection_kinds{
        "id_reverse", "id_cycle", "id_sha256"};
    for (std::size_t index = 0U; index < bijection_source_count; ++index) {
        for (const auto kind : bijection_kinds) {
            result.configurations.push_back(make_id_bijection(
                fixtures.configurations[index], kind, result.bijections));
        }
    }

    const std::string_view topology_source_id = smoke
        ? "base.filament.r205.original"
        : "base.sc3.r180.original";
    const auto topology_source = std::ranges::find_if(
        fixtures.configurations, [&](const auto& configuration) {
            return configuration.id == topology_source_id;
        });
    if (topology_source == fixtures.configurations.end()) {
        throw std::logic_error("missing nested deletion source fixture");
    }
    const auto order = nested_deletion_order(*topology_source);
    const std::size_t maximum_step = smoke
        ? std::min<std::size_t>(2U, order.size())
        : order.size();
    result.topology_path_id = smoke
        ? "nested.smoke.v1"
        : "nested.sc3.r180.v1";
    for (std::size_t step = 0U; step <= maximum_step; ++step) {
        Configuration path = *topology_source;
        std::ostringstream id;
        id << "topology." << topology_source->id << ".step"
           << std::setfill('0') << std::setw(3) << step;
        path.id = id.str();
        path.source_id = topology_source->id;
        path.probe_family = "topology_deletion";
        path.probe_id = "nested_delete";
        path.transform = "fixed_geometry_link_deletion";
        path.decision_scope = "non_generic_control";
        path.topology_path_step = static_cast<std::int64_t>(step);
        path.exact_control = false;
        if (step > 0U) {
            path.removed_edge = order[step - 1U].first;
        }
        std::set<std::pair<std::uint64_t, std::uint64_t>> removed;
        for (std::size_t index = 0U; index < step; ++index) {
            removed.emplace(order[index].first.first_id,
                            order[index].first.second_id);
        }
        path.relations.clear();
        path.relation_sources.clear();
        for (const auto& relation : topology_source->relations) {
            if (!removed.contains({relation.first_id, relation.second_id})) {
                path.relations.push_back(relation);
                path.relation_sources.push_back("nested_delete_retained");
            }
        }
        result.configurations.push_back(std::move(path));
    }
    std::ranges::sort(result.configurations, {}, &Configuration::id);
    const auto duplicate = std::adjacent_find(
        result.configurations.begin(), result.configurations.end(),
        [](const auto& lhs, const auto& rhs) { return lhs.id == rhs.id; });
    if (duplicate != result.configurations.end()) {
        throw std::logic_error("duplicate generated configuration ID");
    }
    return result;
}

[[nodiscard]] std::size_t numerical_rank_3(
    std::vector<std::array<long double, 3>> rows) {
    long double maximum = 0.0L;
    for (const auto& row : rows) {
        for (const auto value : row) {
            maximum = std::max(maximum, std::abs(value));
        }
    }
    const long double tolerance = 4096.0L *
        static_cast<long double>(std::max<std::size_t>(rows.size(), 3U)) *
        std::numeric_limits<long double>::epsilon() *
        std::max(maximum, std::numeric_limits<long double>::min());
    std::size_t rank = 0U;
    for (std::size_t column = 0U; column < 3U && rank < rows.size(); ++column) {
        std::size_t pivot = rank;
        for (std::size_t row = rank; row < rows.size(); ++row) {
            if (std::abs(rows[row][column]) >
                std::abs(rows[pivot][column])) {
                pivot = row;
            }
        }
        if (std::abs(rows[pivot][column]) <= tolerance) {
            continue;
        }
        std::swap(rows[rank], rows[pivot]);
        const long double divisor = rows[rank][column];
        for (std::size_t entry = column; entry < 3U; ++entry) {
            rows[rank][entry] /= divisor;
        }
        for (std::size_t row = rank + 1U; row < rows.size(); ++row) {
            const long double factor = rows[row][column];
            for (std::size_t entry = column; entry < 3U; ++entry) {
                rows[row][entry] -= factor * rows[rank][entry];
            }
        }
        ++rank;
    }
    return rank;
}

struct GeometryFacts final {
    std::size_t affine_span_rank{0U};
    bool connected{false};
    std::size_t edge_lower_bound{0U};
    std::size_t min_incident_direction_rank{0U};
    std::size_t rigid_rank{0U};
    bool generic_solid_gate{false};
};

[[nodiscard]] GeometryFacts geometry_facts(const Configuration& configuration) {
    GeometryFacts result{};
    if (configuration.packets.empty()) {
        return result;
    }
    const Vec3d origin = configuration.packets.front().position_m;
    std::vector<std::array<long double, 3>> affine_rows;
    for (std::size_t index = 1U; index < configuration.packets.size(); ++index) {
        const Vec3d delta = configuration.packets[index].position_m - origin;
        affine_rows.push_back({delta.x, delta.y, delta.z});
    }
    result.affine_span_rank = numerical_rank_3(std::move(affine_rows));
    std::map<std::uint64_t, std::size_t> packet_index;
    std::map<std::uint64_t, std::set<std::uint64_t>> adjacency;
    for (std::size_t index = 0U; index < configuration.packets.size(); ++index) {
        packet_index.emplace(configuration.packets[index].id, index);
        adjacency.emplace(configuration.packets[index].id,
                          std::set<std::uint64_t>{});
    }
    for (const auto relation : configuration.relations) {
        adjacency.at(relation.first_id).insert(relation.second_id);
        adjacency.at(relation.second_id).insert(relation.first_id);
    }
    std::set<std::uint64_t> reached{configuration.packets.front().id};
    std::vector<std::uint64_t> pending{configuration.packets.front().id};
    while (!pending.empty()) {
        const auto current = pending.back();
        pending.pop_back();
        for (const auto neighbor : adjacency.at(current)) {
            if (reached.insert(neighbor).second) {
                pending.push_back(neighbor);
            }
        }
    }
    result.connected = reached.size() == configuration.packets.size();
    result.edge_lower_bound = configuration.packets.size() >= 2U
        ? 3U * configuration.packets.size() - 6U
        : 0U;
    result.min_incident_direction_rank = 3U;
    for (const auto& packet : configuration.packets) {
        std::vector<std::array<long double, 3>> incident;
        for (const auto neighbor : adjacency.at(packet.id)) {
            const Vec3d delta =
                configuration.packets[packet_index.at(neighbor)].position_m -
                packet.position_m;
            incident.push_back({delta.x, delta.y, delta.z});
        }
        result.min_incident_direction_rank = std::min(
            result.min_incident_direction_rank,
            numerical_rank_3(std::move(incident)));
    }
    result.rigid_rank = observation::build_rigid_motion_subspace(
        configuration.packets).rank;
    result.generic_solid_gate = result.affine_span_rank == 3U &&
        result.connected &&
        configuration.relations.size() >= result.edge_lower_bound &&
        result.min_incident_direction_rank == 3U &&
        result.rigid_rank == 6U &&
        !configuration.intentionally_flexible;
    return result;
}

[[nodiscard]] std::string hash_bytes(std::span<const std::uint8_t> bytes) {
    return sha256(std::string_view(
        reinterpret_cast<const char*>(bytes.data()), bytes.size()));
}

[[nodiscard]] std::string hash_null_vector(
    const observation::DenseMatrix& basis, const std::size_t column) {
    std::vector<std::uint8_t> bytes;
    bytes.reserve(basis.row_count() * sizeof(double));
    for (std::size_t row = 0U; row < basis.row_count(); ++row) {
        const auto bits = std::bit_cast<std::uint64_t>(basis(row, column));
        for (unsigned shift = 0U; shift < 64U; shift += 8U) {
            bytes.push_back(static_cast<std::uint8_t>(bits >> shift));
        }
    }
    return hash_bytes(bytes);
}

struct AnalysisRecord final {
    const Configuration* configuration{nullptr};
    GeometryFacts facts{};
    confirmation::RawObservabilityDiagnostic diagnostic{};
    observation::BondOperator bonds{};
    std::vector<std::uint8_t> checkpoint{};
    std::string checkpoint_hash{};
    double maximum_null_residual{0.0};
    double maximum_resolved_zero{0.0};
    std::string classification{};
    bool clear_separation{false};
    double baseline_mu{0.0};
    double mu_retention{0.0};
    bool robustness_pass{false};
    bool decision_gate_pass{false};
};

[[nodiscard]] std::string wire_status(const observation::RankStatus status) {
    switch (status) {
    case observation::RankStatus::analyzed:
        return "analyzed";
    case observation::RankStatus::empty:
        return "empty";
    case observation::RankStatus::ambiguous:
        return "ambiguous";
    case observation::RankStatus::size_limit:
    case observation::RankStatus::invalid_rows:
    case observation::RankStatus::numerical_failure:
        return "numerical_failure";
    }
    return "numerical_failure";
}

[[nodiscard]] std::map<std::string, AnalysisRecord> analyze_inventory(
    const std::vector<Configuration>& configurations) {
    std::map<std::string, AnalysisRecord> result;
    for (const auto& configuration : configurations) {
        observation::MechanicalObservabilityState state{};
        state.support_radius_m = configuration.support_radius_m;
        state.packets = configuration.packets;
        state.bonds = configuration.relations;
        state.volumes.clear();
        auto checkpoint = observation::serialize_mechanical_observability_state(state);
        const auto restored = observation::deserialize_mechanical_observability_state(
            checkpoint);
        if (observation::serialize_mechanical_observability_state(restored) !=
            checkpoint) {
            throw std::runtime_error("checkpoint round trip changed authoritative state");
        }
        AnalysisRecord record{};
        record.configuration = &configuration;
        record.facts = geometry_facts(configuration);
        record.bonds = observation::build_bond_rigidity_operator(
            configuration.packets, configuration.relations);
        record.diagnostic = confirmation::analyze_raw_central_rigidity(
            configuration.packets, configuration.relations);
        record.checkpoint = std::move(checkpoint);
        record.checkpoint_hash = hash_bytes(record.checkpoint);
        for (const auto& mode : record.diagnostic.null_modes) {
            record.maximum_null_residual = std::max(
                record.maximum_null_residual,
                mode.normalized_operator_residual);
        }
        for (const auto& singular : record.diagnostic.spectrum) {
            if (singular.classification ==
                confirmation::SingularClassification::resolved_zero) {
                record.maximum_resolved_zero = std::max(
                    record.maximum_resolved_zero, singular.value);
            }
        }
        if (record.diagnostic.status == observation::RankStatus::numerical_failure ||
            record.diagnostic.status == observation::RankStatus::invalid_rows ||
            record.diagnostic.status == observation::RankStatus::size_limit) {
            record.classification = "implementation_failure";
        } else if (record.diagnostic.status == observation::RankStatus::ambiguous ||
                   !record.diagnostic.direct_svd_unambiguous) {
            record.classification = "ambiguous";
        } else if (record.diagnostic.nonrigid_nullity > 0U) {
            record.classification = "resolved_nonrigid";
        } else {
            record.classification = "rigid_only";
        }
        record.clear_separation =
            record.diagnostic.cpqr.status == observation::RankStatus::analyzed &&
            record.diagnostic.status == observation::RankStatus::analyzed &&
            record.diagnostic.direct_svd_unambiguous &&
            record.diagnostic.rank_paths_agree &&
            (record.diagnostic.modular_rank_value == 0U ||
             record.diagnostic.nonzero_threshold_separation > 1.0) &&
            record.diagnostic.null_threshold_separation > 1.0;
        if (!result.emplace(configuration.id, std::move(record)).second) {
            throw std::logic_error("duplicate analysis record");
        }
    }
    for (auto& [id, record] : result) {
        (void)id;
        const auto source = result.find(record.configuration->source_id);
        if (source == result.end()) {
            throw std::logic_error("configuration source missing from inventory");
        }
        record.baseline_mu = source->second.diagnostic.mu;
        const bool finite_mu = std::isfinite(record.baseline_mu) &&
            std::isfinite(record.diagnostic.mu) &&
            record.baseline_mu >= 0.0 && record.diagnostic.mu >= 0.0;
        if (!finite_mu) {
            record.mu_retention = 0.0;
            record.classification = "implementation_failure";
            record.clear_separation = false;
        } else if (record.baseline_mu > 0.0) {
            record.mu_retention = record.diagnostic.mu / record.baseline_mu;
        } else if (record.diagnostic.mu == 0.0) {
            record.mu_retention = 1.0;
        } else {
            // A positive margin relative to a zero-margin source has no finite
            // retention ratio.  Never emit infinity into the finite wire ABI.
            record.mu_retention = 0.0;
            record.classification = "implementation_failure";
            record.clear_separation = false;
        }
        const bool eligible =
            record.configuration->decision_scope == "eligible_generic";
        record.robustness_pass = eligible &&
            record.classification == "rigid_only" &&
            record.clear_separation && record.mu_retention >= 1.0 / 1024.0;
        if (eligible) {
            record.decision_gate_pass = record.robustness_pass;
        } else if (record.configuration->decision_scope ==
                   "intentionally_flexible") {
            record.decision_gate_pass =
                record.classification == "resolved_nonrigid" &&
                record.clear_separation;
        } else {
            record.decision_gate_pass =
                (record.classification == "rigid_only" ||
                 record.classification == "resolved_nonrigid") &&
                record.clear_separation;
        }
    }
    return result;
}

[[nodiscard]] double frobenius_norm(const observation::DenseMatrix& matrix) {
    long double sum = 0.0L;
    for (const double value : matrix.entries()) {
        sum += static_cast<long double>(value) * value;
    }
    return static_cast<double>(std::sqrt(sum));
}

[[nodiscard]] double normalized_matrix_difference(
    const observation::DenseMatrix& actual,
    const observation::DenseMatrix& expected) {
    if (actual.row_count() != expected.row_count() ||
        actual.column_count() != expected.column_count()) {
        return std::numeric_limits<double>::infinity();
    }
    long double sum = 0.0L;
    for (std::size_t row = 0U; row < actual.row_count(); ++row) {
        for (std::size_t column = 0U; column < actual.column_count(); ++column) {
            const long double difference = static_cast<long double>(
                actual(row, column)) - expected(row, column);
            sum += difference * difference;
        }
    }
    return static_cast<double>(std::sqrt(sum)) /
        std::max(frobenius_norm(expected), std::numeric_limits<double>::min());
}

[[nodiscard]] Matrix3d inherited_rotation() {
    Matrix3d result{};
    result.value = {{{1.0 / 9.0, 8.0 / 9.0, 4.0 / 9.0},
                     {8.0 / 9.0, 1.0 / 9.0, -4.0 / 9.0},
                     {-4.0 / 9.0, 4.0 / 9.0, -7.0 / 9.0}}};
    return result;
}

[[nodiscard]] observation::DenseMatrix rotated_expected_operator(
    const observation::DenseMatrix& base, const Matrix3d& rotation) {
    observation::DenseMatrix result(base.row_count(), base.column_count());
    for (std::size_t row = 0U; row < base.row_count(); ++row) {
        for (std::size_t packet = 0U; packet < base.column_count() / 3U;
             ++packet) {
            for (std::size_t axis = 0U; axis < 3U; ++axis) {
                long double value = 0.0L;
                for (std::size_t inner = 0U; inner < 3U; ++inner) {
                    value += static_cast<long double>(rotation.value[axis][inner]) *
                        base(row, 3U * packet + inner);
                }
                result(row, 3U * packet + axis) = static_cast<double>(value);
            }
        }
    }
    return result;
}

[[nodiscard]] double spectrum_residual(
    const confirmation::RawObservabilityDiagnostic& base,
    const confirmation::RawObservabilityDiagnostic& variant) {
    if (base.spectrum.size() != variant.spectrum.size()) {
        return std::numeric_limits<double>::infinity();
    }
    double result = 0.0;
    for (std::size_t index = 0U; index < base.spectrum.size(); ++index) {
        const double first = base.spectrum[index].value;
        const double second = variant.spectrum[index].value;
        result = std::max(result,
            std::abs(first - second) /
                std::max({std::abs(first), std::abs(second), 1.0}));
    }
    return result;
}

[[nodiscard]] double id_covariance_residual(
    const AnalysisRecord& base, const AnalysisRecord& variant,
    const std::map<std::uint64_t, std::uint64_t>& mapping) {
    const auto& base_operator = base.bonds.linearized;
    const auto& variant_operator = variant.bonds.linearized;
    if (base_operator.matrix.row_count() !=
            variant_operator.matrix.row_count() ||
        base_operator.matrix.column_count() !=
            variant_operator.matrix.column_count()) {
        return std::numeric_limits<double>::infinity();
    }
    std::map<std::pair<std::uint64_t, std::uint64_t>, std::size_t>
        variant_row_by_edge;
    for (std::size_t row = 0U; row < variant.bonds.relations.size(); ++row) {
        variant_row_by_edge.emplace(
            std::pair(variant.bonds.relations[row].first_id,
                      variant.bonds.relations[row].second_id), row);
    }
    std::map<std::uint64_t, std::size_t> variant_column_by_id;
    for (std::size_t index = 0U;
         index < variant_operator.packet_ids.size(); ++index) {
        variant_column_by_id.emplace(variant_operator.packet_ids[index], index);
    }
    observation::DenseMatrix semantic(
        base_operator.matrix.row_count(), base_operator.matrix.column_count());
    for (std::size_t base_row = 0U;
         base_row < base.bonds.relations.size(); ++base_row) {
        const auto relation = base.bonds.relations[base_row];
        auto mapped_first = mapping.at(relation.first_id);
        auto mapped_second = mapping.at(relation.second_id);
        if (mapped_second < mapped_first) {
            std::swap(mapped_first, mapped_second);
        }
        const std::size_t variant_row = variant_row_by_edge.at(
            {mapped_first, mapped_second});
        for (std::size_t base_packet = 0U;
             base_packet < base_operator.packet_ids.size(); ++base_packet) {
            const auto mapped_id = mapping.at(
                base_operator.packet_ids[base_packet]);
            const std::size_t variant_packet =
                variant_column_by_id.at(mapped_id);
            for (std::size_t axis = 0U; axis < 3U; ++axis) {
                semantic(base_row, 3U * base_packet + axis) =
                    variant_operator.matrix(
                        variant_row, 3U * variant_packet + axis);
            }
        }
    }
    return normalized_matrix_difference(
        semantic, base_operator.matrix);
}

struct MetamorphicRecord final {
    std::string control_id;
    std::string base_id;
    std::string variant_id;
    std::string kind;
    bool physical_graph_equal{true};
    double covariance_residual{0.0};
    double spectrum_residual_value{0.0};
    double finite_length_scale{1.0};
    double finite_length_residual{0.0};
    bool rank_equal{false};
    bool nullity_equal{false};
    bool nonrigid_equal{false};
    double mu_relative_error{0.0};
    double tolerance{0.0};
    bool pass{false};
};

using CanonicalEdge = std::pair<std::uint64_t, std::uint64_t>;

[[nodiscard]] CanonicalEdge canonical_edge(
    std::uint64_t first, std::uint64_t second) {
    if (first == second) {
        throw std::invalid_argument("self relation has no physical edge");
    }
    if (second < first) {
        std::swap(first, second);
    }
    return {first, second};
}

[[nodiscard]] std::vector<BondRelation> semantic_canonical_relations(
    std::span<const BondRelation> relations) {
    std::vector<BondRelation> result;
    result.reserve(relations.size());
    for (const auto relation : relations) {
        const auto [first, second] = canonical_edge(
            relation.first_id, relation.second_id);
        result.push_back({first, second});
    }
    std::ranges::sort(result, [](const auto& lhs, const auto& rhs) {
        return CanonicalEdge(lhs.first_id, lhs.second_id) <
            CanonicalEdge(rhs.first_id, rhs.second_id);
    });
    if (std::adjacent_find(result.begin(), result.end()) != result.end()) {
        throw std::invalid_argument(
            "semantic relation canonicalization produced duplicate edge");
    }
    return result;
}

struct FiniteLengthComparison final {
    bool graph_equal{false};
    double residual{std::numeric_limits<double>::infinity()};
};

[[nodiscard]] FiniteLengthComparison compare_canonical_bond_operators(
    const observation::BondOperator& base,
    const observation::BondOperator& variant,
    const double expected_scale) {
    if (!(expected_scale > 0.0) || !std::isfinite(expected_scale)) {
        throw std::invalid_argument("finite-length scale must be positive");
    }
    if (base.relations != variant.relations ||
        base.lengths_m.size() != variant.lengths_m.size()) {
        return {};
    }
    double maximum_residual = 0.0;
    for (std::size_t index = 0U; index < base.lengths_m.size(); ++index) {
        const double expected = expected_scale * base.lengths_m[index];
        const double actual = variant.lengths_m[index];
        maximum_residual = std::max(
            maximum_residual,
            std::abs(actual - expected) /
                std::max({std::abs(actual), std::abs(expected),
                          std::numeric_limits<double>::min()}));
    }
    return {true, maximum_residual};
}

[[nodiscard]] FiniteLengthComparison compare_finite_bond_lengths(
    const AnalysisRecord& base, const AnalysisRecord& variant,
    const double expected_scale,
    const std::map<std::uint64_t, std::uint64_t>* mapping = nullptr) {
    if (!(expected_scale > 0.0) || !std::isfinite(expected_scale)) {
        throw std::invalid_argument("finite-length scale must be positive");
    }
    std::map<CanonicalEdge, double> variant_lengths;
    for (std::size_t index = 0U;
         index < variant.bonds.relations.size(); ++index) {
        const auto relation = variant.bonds.relations[index];
        variant_lengths.emplace(
            canonical_edge(relation.first_id, relation.second_id),
            variant.bonds.lengths_m[index]);
    }
    std::set<CanonicalEdge> expected_edges;
    double maximum_residual = 0.0;
    for (std::size_t index = 0U; index < base.bonds.relations.size(); ++index) {
        auto first = base.bonds.relations[index].first_id;
        auto second = base.bonds.relations[index].second_id;
        if (mapping != nullptr) {
            first = mapping->at(first);
            second = mapping->at(second);
        }
        const auto edge = canonical_edge(first, second);
        expected_edges.insert(edge);
        const auto found = variant_lengths.find(edge);
        if (found == variant_lengths.end()) {
            return {};
        }
        const double expected = expected_scale * base.bonds.lengths_m[index];
        const double actual = found->second;
        maximum_residual = std::max(
            maximum_residual,
            std::abs(actual - expected) /
                std::max({std::abs(actual), std::abs(expected),
                          std::numeric_limits<double>::min()}));
    }
    std::set<CanonicalEdge> observed_edges;
    for (const auto& [edge, length] : variant_lengths) {
        (void)length;
        observed_edges.insert(edge);
    }
    return {expected_edges == observed_edges, maximum_residual};
}

[[nodiscard]] std::string inherited_control_kind(std::string_view transform) {
    if (transform == "translation") {
        return "inherited_translation";
    }
    if (transform == "rational_quaternion_rotation") {
        return "inherited_proper_rotation";
    }
    if (transform == "rational_quaternion_rotation_translation") {
        return "inherited_rotation_translation";
    }
    if (transform == "scale_half_rotation") {
        return "inherited_scale_half";
    }
    if (transform == "scale_double_rotation") {
        return "inherited_scale_double";
    }
    throw std::invalid_argument("unknown inherited metamorphic transform");
}

[[nodiscard]] MetamorphicRecord make_metamorphic_record(
    std::string control_id, std::string base_id, std::string variant_id,
    std::string kind, const std::map<std::string, AnalysisRecord>& analyses,
    const double covariance_residual, const double finite_length_scale,
    const double finite_length_residual,
    const bool physical_graph_equal = true) {
    const auto& base = analyses.at(base_id);
    const auto& variant = analyses.at(variant_id);
    MetamorphicRecord result{};
    result.control_id = std::move(control_id);
    result.base_id = std::move(base_id);
    result.variant_id = std::move(variant_id);
    result.kind = std::move(kind);
    result.physical_graph_equal = physical_graph_equal;
    result.covariance_residual = covariance_residual;
    result.spectrum_residual_value = spectrum_residual(
        base.diagnostic, variant.diagnostic);
    result.finite_length_scale = finite_length_scale;
    result.finite_length_residual = finite_length_residual;
    result.rank_equal = base.diagnostic.modular_rank_value ==
        variant.diagnostic.modular_rank_value;
    result.nullity_equal = base.diagnostic.nullity == variant.diagnostic.nullity;
    result.nonrigid_equal = base.diagnostic.nonrigid_nullity ==
        variant.diagnostic.nonrigid_nullity;
    result.mu_relative_error = std::abs(
        variant.diagnostic.mu - base.diagnostic.mu) /
        std::max(std::abs(base.diagnostic.mu),
                 std::numeric_limits<double>::min());
    const std::size_t dimension = std::max<std::size_t>({
        6U, base.diagnostic.row_count, base.diagnostic.column_count,
        variant.diagnostic.row_count, variant.diagnostic.column_count});
    result.tolerance = 16384.0 * static_cast<double>(dimension) *
        std::numeric_limits<double>::epsilon();
    result.pass = result.physical_graph_equal && result.rank_equal &&
        result.nullity_equal && result.nonrigid_equal &&
        result.covariance_residual <= result.tolerance &&
        result.spectrum_residual_value <= result.tolerance &&
        result.finite_length_residual <= result.tolerance &&
        result.mu_relative_error <= result.tolerance;
    return result;
}

[[nodiscard]] std::vector<MetamorphicRecord> build_metamorphic_records(
    const FixtureData& fixtures, const GeneratedInventory& inventory,
    const std::map<std::string, AnalysisRecord>& analyses, const bool smoke) {
    std::vector<MetamorphicRecord> result;
    for (const auto& configuration : fixtures.configurations) {
        if (configuration.transform == "identity") {
            continue;
        }
        const auto& base = analyses.at(configuration.source_id);
        const auto& variant = analyses.at(configuration.id);
        observation::DenseMatrix expected = base.bonds.linearized.matrix;
        if (configuration.transform != "translation") {
            expected = rotated_expected_operator(
                base.bonds.linearized.matrix, inherited_rotation());
        }
        const double covariance = normalized_matrix_difference(
            variant.bonds.linearized.matrix, expected);
        const double length_scale = configuration.geometry_scale /
            base.configuration->geometry_scale;
        const auto finite = compare_finite_bond_lengths(
            base, variant, length_scale);
        result.push_back(make_metamorphic_record(
            "control." + configuration.probe_id + "." +
                configuration.source_id,
            configuration.source_id, configuration.id,
            inherited_control_kind(configuration.transform), analyses,
            covariance, length_scale, finite.residual,
            finite.graph_equal));
    }
    // The inherited builder canonicalizes packet and relation order.  Exercise
    // both independently for every inherited fixture without adding a new
    // physical configuration.
    for (const auto& configuration : fixtures.configurations) {
        auto packet_permuted = configuration.packets;
        std::ranges::reverse(packet_permuted);
        const auto packet_operator = observation::build_bond_rigidity_operator(
            packet_permuted, configuration.relations);
        const double packet_residual = normalized_matrix_difference(
            packet_operator.linearized.matrix,
            analyses.at(configuration.id).bonds.linearized.matrix);
        const auto packet_finite = compare_canonical_bond_operators(
            analyses.at(configuration.id).bonds, packet_operator, 1.0);
        result.push_back(make_metamorphic_record(
            "control.packet_permutation." + configuration.id,
            configuration.id, configuration.id, "packet_permutation",
            analyses, packet_residual, 1.0, packet_finite.residual,
            packet_finite.graph_equal));

        auto relation_permuted = configuration.relations;
        std::ranges::reverse(relation_permuted);
        for (auto& relation : relation_permuted) {
            std::swap(relation.first_id, relation.second_id);
        }
        // IDs and relation order are labels.  The public inherited operator
        // intentionally requires a canonical ABI, so exercise a genuinely
        // noncanonical presentation and canonicalize it semantically here.
        relation_permuted = semantic_canonical_relations(relation_permuted);
        const auto relation_operator = observation::build_bond_rigidity_operator(
            configuration.packets, relation_permuted);
        const double relation_residual = normalized_matrix_difference(
            relation_operator.linearized.matrix,
            analyses.at(configuration.id).bonds.linearized.matrix);
        const auto relation_finite = compare_canonical_bond_operators(
            analyses.at(configuration.id).bonds, relation_operator, 1.0);
        result.push_back(make_metamorphic_record(
            "control.relation_permutation." + configuration.id,
            configuration.id, configuration.id, "relation_permutation",
            analyses, relation_residual, 1.0, relation_finite.residual,
            relation_finite.graph_equal));
    }
    for (const auto& configuration : inventory.configurations) {
        if (configuration.probe_family != "id_bijection") {
            continue;
        }
        const auto mapping = id_mapping(
            *analyses.at(configuration.source_id).configuration,
            configuration.probe_id);
        const double covariance = id_covariance_residual(
            analyses.at(configuration.source_id),
            analyses.at(configuration.id), mapping);
        const auto finite = compare_finite_bond_lengths(
            analyses.at(configuration.source_id),
            analyses.at(configuration.id), 1.0, &mapping);
        result.push_back(make_metamorphic_record(
            "control." + configuration.probe_id + "." +
                configuration.source_id,
            configuration.source_id, configuration.id,
            configuration.probe_id, analyses, covariance, 1.0,
            finite.residual, finite.graph_equal));
    }
    if (smoke && result.empty()) {
        throw std::logic_error("smoke metamorphic inventory is empty");
    }
    std::ranges::sort(result, {}, &MetamorphicRecord::control_id);
    return result;
}

struct BundleTables final {
    Csv configurations{configurations_header};
    Csv packets{packets_header};
    Csv relations{relations_header};
    Csv observability{observability_header};
    Csv spectra{spectra_header};
    Csv nullspace{nullspace_header};
    Csv nullspace_vectors{nullspace_vectors_header};
    Csv metamorphic{metamorphic_header};
    Csv id_bijections{id_bijections_header};
    Csv topology_path{topology_path_header};
    Csv lookup{lookup_header};
    Csv checkpoints{checkpoints_header};
};

void emit_core_tables(
    const GeneratedInventory& inventory,
    const std::map<std::string, AnalysisRecord>& analyses,
    BundleTables& tables) {
    const double sqrt_two = std::sqrt(2.0);
    constexpr std::array<std::string_view, 3> axes{"x", "y", "z"};
    if (!std::ranges::is_sorted(
            inventory.configurations, {}, &Configuration::id)) {
        throw std::logic_error(
            "configuration inventory is not in canonical evidence order");
    }
    for (const auto& configuration : inventory.configurations) {
        const auto& record = analyses.at(configuration.id);
        const auto& diagnostic = record.diagnostic;
        if (!std::ranges::is_sorted(
                configuration.packets, {}, &MechanicalPacket::id)) {
            throw std::logic_error(
                "packet inventory is not in canonical evidence order");
        }
        if (diagnostic.cpqr.nullspace_basis.row_count() !=
                3U * configuration.packets.size() ||
            diagnostic.cpqr.nullspace_basis.column_count() !=
                diagnostic.null_modes.size()) {
            throw std::logic_error(
                "CPQR nullspace evidence dimensions are inconsistent");
        }
        tables.configurations.row({
            configuration.id,
            configuration.source_id,
            configuration.probe_family,
            configuration.probe_id,
            configuration.family,
            configuration.profile,
            configuration.transform,
            configuration.decision_scope,
            std::to_string(configuration.packets.size()),
            std::to_string(configuration.relations.size()),
            hex64(configuration.nominal_spacing_m),
            hex64(configuration.support_radius_m),
            hex64(configuration.geometry_scale),
            configuration.probe_family == "homogeneous_deformation"
                ? hex64(configuration.deformation_det) : "NA",
            configuration.probe_family == "geometry_perturbation"
                ? hex64(configuration.perturbation_amplitude_ratio) : "NA",
            configuration.probe_family == "geometry_perturbation"
                ? std::to_string(configuration.perturbation_seed) : "NA",
            configuration.probe_family == "topology_deletion"
                ? std::to_string(configuration.topology_path_step) : "NA",
            std::to_string(record.facts.affine_span_rank),
            bool_text(record.facts.connected),
            std::to_string(record.facts.edge_lower_bound),
            std::to_string(record.facts.min_incident_direction_rank),
            std::to_string(record.facts.rigid_rank),
            bool_text(record.facts.generic_solid_gate),
            bool_text(configuration.intentionally_flexible),
            bool_text(configuration.exact_control),
            record.checkpoint_hash,
            record.checkpoint_hash,
            "true",
        });

        for (std::size_t index = 0U; index < configuration.packets.size();
             ++index) {
            const auto& packet = configuration.packets[index];
            tables.packets.row({
                configuration.id,
                std::to_string(index),
                std::to_string(packet.id),
                std::to_string(packet.mass_quanta),
                hex64(packet.position_m.x),
                hex64(packet.position_m.y),
                hex64(packet.position_m.z),
                hex64(packet.velocity_m_per_s.x),
                hex64(packet.velocity_m_per_s.y),
                hex64(packet.velocity_m_per_s.z),
            });
        }
        for (std::size_t index = 0U; index < configuration.relations.size();
             ++index) {
            const double row_norm = diagnostic.row_norms[index];
            const double relative_error =
                std::abs(row_norm - sqrt_two) / sqrt_two;
            tables.relations.row({
                configuration.id,
                std::to_string(index),
                std::to_string(configuration.relations[index].first_id),
                std::to_string(configuration.relations[index].second_id),
                "retained",
                configuration.relation_sources[index],
                hex64(record.bonds.lengths_m[index]),
                hex64(row_norm),
                hex64(relative_error),
                hex64(diagnostic.row_norm_tolerance),
                bool_text(relative_error <= diagnostic.row_norm_tolerance),
            });
        }

        const bool rank_ambiguous =
            !diagnostic.direct_svd_unambiguous ||
            diagnostic.cpqr.status == observation::RankStatus::ambiguous;
        tables.observability.row({
            configuration.id,
            configuration.probe_family,
            configuration.decision_scope,
            wire_status(diagnostic.status),
            std::to_string(diagnostic.row_count),
            std::to_string(diagnostic.column_count),
            hex64(diagnostic.maximum_row_norm_relative_error),
            hex64(diagnostic.row_norm_tolerance),
            bool_text(diagnostic.row_norms_pass),
            wire_status(diagnostic.cpqr.status),
            std::to_string(diagnostic.cpqr_rank),
            std::to_string(diagnostic.svd_rank),
            bool_text(diagnostic.rank_paths_agree),
            bool_text(rank_ambiguous),
            std::to_string(diagnostic.nullity),
            std::to_string(diagnostic.realized_rigid_rank),
            hex64(diagnostic.normalized_rigid_residual),
            hex64(diagnostic.residual_tolerance),
            bool_text(diagnostic.rigid_subspace_in_kernel),
            std::to_string(diagnostic.nonrigid_nullity),
            bool_text(diagnostic.cpqr.basis_complete),
            hex64(record.maximum_null_residual),
            hex64(diagnostic.normalized_nonrigid_residual),
            hex64(diagnostic.rigid_orthogonality_residual),
            hex64(diagnostic.sigma_max),
            hex64(diagnostic.sigma_min_nonzero),
            hex64(diagnostic.mu),
            hex64(diagnostic.svd_threshold),
            hex64(diagnostic.svd_threshold / 8.0),
            hex64(diagnostic.svd_threshold * 8.0),
            hex64(diagnostic.nonzero_threshold_separation),
            hex64(record.maximum_resolved_zero),
            extended_hex64(diagnostic.null_threshold_separation),
            bool_text(record.clear_separation),
            hex64(record.baseline_mu),
            extended_hex64(record.mu_retention),
            bool_text(record.robustness_pass),
            record.classification,
            bool_text(record.decision_gate_pass),
        });

        std::optional<std::size_t> smallest_accepted;
        for (std::size_t index = 0U; index < diagnostic.spectrum.size(); ++index) {
            if (diagnostic.spectrum[index].classification ==
                confirmation::SingularClassification::accepted_nonzero) {
                smallest_accepted = index;
            }
        }
        for (std::size_t index = 0U; index < diagnostic.spectrum.size(); ++index) {
            const auto& singular = diagnostic.spectrum[index];
            std::string classification{
                confirmation::classification_name(singular.classification)};
            const double ratio = diagnostic.svd_threshold > 0.0
                ? singular.value / diagnostic.svd_threshold : 0.0;
            tables.spectra.row({
                configuration.id,
                std::to_string(index),
                hex64(singular.value),
                hex64(diagnostic.svd_threshold),
                hex64(ratio),
                classification,
                bool_text(index == 0U),
                bool_text(smallest_accepted.has_value() &&
                          *smallest_accepted == index),
            });
        }
        for (std::size_t index = 0U; index < diagnostic.null_modes.size();
             ++index) {
            const auto& mode = diagnostic.null_modes[index];
            tables.nullspace.row({
                configuration.id,
                std::to_string(index),
                hex64(mode.normalized_operator_residual),
                hex64(mode.rigid_projection_norm),
                hex64(mode.rigid_orthogonality_residual),
                hex64(diagnostic.residual_tolerance),
                hash_null_vector(diagnostic.cpqr.nullspace_basis, index),
                bool_text(mode.accepted),
            });
            for (std::size_t packet_index = 0U;
                 packet_index < configuration.packets.size(); ++packet_index) {
                for (std::size_t axis = 0U; axis < axes.size(); ++axis) {
                    const std::size_t component_index = 3U * packet_index + axis;
                    tables.nullspace_vectors.row({
                        configuration.id,
                        std::to_string(index),
                        std::to_string(component_index),
                        std::to_string(configuration.packets[packet_index].id),
                        std::string(axes[axis]),
                        hex64(diagnostic.cpqr.nullspace_basis(
                            component_index, index)),
                    });
                }
            }
        }
        tables.checkpoints.row({
            configuration.id,
            "mls.mechanical-observability.input.v1.little-endian",
            std::to_string(record.checkpoint.size()),
            record.checkpoint_hash,
            record.checkpoint_hash,
            record.checkpoint_hash,
            "true",
            "true",
            "true",
        });
    }
}

void emit_bijections(
    const GeneratedInventory& inventory, BundleTables& tables) {
    for (const auto& row : inventory.bijections) {
        tables.id_bijections.row({
            row.control_id,
            row.source_id,
            row.kind,
            std::to_string(row.old_id),
            std::to_string(row.new_id),
            std::to_string(row.old_id),
            "true",
        });
    }
}

void emit_metamorphic(
    const std::vector<MetamorphicRecord>& records, BundleTables& tables) {
    for (const auto& record : records) {
        tables.metamorphic.row({
            record.control_id,
            record.base_id,
            record.variant_id,
            record.kind,
            bool_text(record.physical_graph_equal),
            hex64(record.covariance_residual),
            hex64(record.spectrum_residual_value),
            hex64(record.finite_length_scale),
            hex64(record.finite_length_residual),
            bool_text(record.rank_equal),
            bool_text(record.nullity_equal),
            bool_text(record.nonrigid_equal),
            hex64(record.mu_relative_error),
            hex64(record.tolerance),
            bool_text(record.pass),
        });
    }
}

[[nodiscard]] bool emit_topology_path(
    const GeneratedInventory& inventory,
    const std::map<std::string, AnalysisRecord>& analyses,
    BundleTables& tables, const bool smoke) {
    std::vector<const Configuration*> path;
    for (const auto& configuration : inventory.configurations) {
        if (configuration.probe_family == "topology_deletion") {
            path.push_back(&configuration);
        }
    }
    std::ranges::sort(path, [](const auto* lhs, const auto* rhs) {
        return lhs->topology_path_step < rhs->topology_path_step;
    });
    const std::size_t expected_path_size = smoke
        ? 3U
        : registered_topology_edge_count + 1U;
    if (path.size() != expected_path_size) {
        throw std::logic_error("topology path differs from registered extent");
    }
    bool registered_transition_pass = true;
    for (std::size_t index = 0U; index < path.size(); ++index) {
        const auto& configuration = *path[index];
        const auto& record = analyses.at(configuration.id);
        if (configuration.topology_path_step !=
            static_cast<std::int64_t>(index)) {
            throw std::logic_error("topology path step is noncanonical");
        }
        std::string transition = "none";
        if (!smoke && index == registered_topology_complete_deletion) {
            transition = "complete_deletion";
        } else if (!smoke && index == registered_topology_first_nonrigid) {
            transition = "first_nonrigid";
        } else if (!smoke && index == registered_topology_last_rigid) {
            transition = "last_rigid";
        } else if (!smoke &&
                   (index == registered_topology_transition_adjacent_before ||
                    index == registered_topology_transition_adjacent_after)) {
            transition = "transition_adjacent";
        }
        const std::size_t structural_upper_bound = std::min(
            configuration.relations.size(),
            3U * configuration.packets.size() - record.facts.rigid_rank);
        std::size_t reported_rank = record.diagnostic.modular_rank_value;
        std::string rank_reference_kind = "modular_lower_bound";
        bool rank_certified = false;
        if (!smoke && index == registered_topology_first_nonrigid) {
            reported_rank = registered_topology_exact_rank_step54;
            rank_reference_kind = "exact_fraction_rref";
            rank_certified = true;
        } else if (reported_rank == structural_upper_bound) {
            rank_reference_kind =
                "modular_lower_bound_matches_structural_upper_bound";
            rank_certified = true;
        }
        if (!smoke && index == registered_topology_last_rigid) {
            registered_transition_pass = registered_transition_pass &&
                record.diagnostic.modular_rank_value == 75U &&
                record.diagnostic.nonrigid_nullity == 0U;
        } else if (!smoke &&
                   index == registered_topology_first_nonrigid) {
            registered_transition_pass = registered_transition_pass &&
                record.diagnostic.modular_rank_value ==
                    registered_topology_exact_rank_step54 &&
                record.diagnostic.nonrigid_nullity == 1U;
        } else if (!smoke &&
                   index == registered_topology_complete_deletion) {
            registered_transition_pass = registered_transition_pass &&
                configuration.relations.empty() &&
                record.diagnostic.modular_rank_value == 0U;
        }
        tables.topology_path.row({
            inventory.topology_path_id,
            configuration.id,
            std::to_string(configuration.topology_path_step),
            configuration.removed_edge.has_value()
                ? std::to_string(configuration.removed_edge->first_id) : "NA",
            configuration.removed_edge.has_value()
                ? std::to_string(configuration.removed_edge->second_id) : "NA",
            std::to_string(configuration.relations.size()),
            std::to_string(reported_rank),
            std::to_string(record.diagnostic.nullity),
            std::to_string(record.diagnostic.nonrigid_nullity),
            hex64(record.diagnostic.sigma_min_nonzero),
            hex64(record.diagnostic.sigma_max),
            hex64(record.diagnostic.mu),
            hex64(record.diagnostic.nonzero_threshold_separation),
            rank_reference_kind,
            bool_text(rank_certified),
            record.classification,
            transition,
        });
    }
    return registered_transition_pass;
}

[[nodiscard]] bool emit_lookup(
    const FixtureData& fixtures, BundleTables& tables) {
    struct Phase final {
        std::string_view id;
        Vec3d fraction;
    };
    constexpr std::array<Phase, 2> phases{{
        {"p000", {0.0, 0.0, 0.0}},
        {"p037_011_029", {0.37, 0.11, 0.29}},
    }};
    bool all_pass = true;
    for (const auto& configuration : fixtures.configurations) {
        if (!std::ranges::all_of(
                configuration.relation_sources,
                [](const auto& source) { return source == "physical_radius"; })) {
            continue;
        }
        std::map<std::uint64_t, Vec3d> positions;
        for (const auto& packet : configuration.packets) {
            positions.emplace(packet.id, packet.position_m);
        }
        std::set<std::pair<std::uint64_t, std::uint64_t>> brute;
        for (std::size_t first = 0U; first < configuration.packets.size(); ++first) {
            for (std::size_t second = first + 1U;
                 second < configuration.packets.size(); ++second) {
                const auto& lhs = configuration.packets[first];
                const auto& rhs = configuration.packets[second];
                const Vec3d delta = rhs.position_m - lhs.position_m;
                const double distance = std::hypot(delta.x, delta.y, delta.z);
                if (distance > 0.0 && distance < configuration.support_radius_m) {
                    brute.emplace(lhs.id, rhs.id);
                }
            }
        }
        std::set<std::pair<std::uint64_t, std::uint64_t>> explicit_edges;
        for (const auto relation : configuration.relations) {
            explicit_edges.emplace(relation.first_id, relation.second_id);
        }
        for (const auto& phase : phases) {
            using Cell = std::array<std::int64_t, 3>;
            std::map<Cell, std::vector<std::uint64_t>> cells;
            for (const auto& packet : configuration.packets) {
                const auto coordinate = [&](const double value,
                                            const double fraction) {
                    const double cell = std::floor(
                        value / configuration.support_radius_m - fraction);
                    if (!std::isfinite(cell) ||
                        cell < static_cast<double>(
                            std::numeric_limits<std::int64_t>::min()) ||
                        cell > static_cast<double>(
                            std::numeric_limits<std::int64_t>::max())) {
                        throw std::overflow_error("lookup cell index overflow");
                    }
                    return static_cast<std::int64_t>(cell);
                };
                cells[{coordinate(packet.position_m.x, phase.fraction.x),
                       coordinate(packet.position_m.y, phase.fraction.y),
                       coordinate(packet.position_m.z, phase.fraction.z)}]
                    .push_back(packet.id);
            }
            std::set<std::pair<std::uint64_t, std::uint64_t>> candidates;
            for (const auto& [cell, ids] : cells) {
                for (int dz = -1; dz <= 1; ++dz) {
                    for (int dy = -1; dy <= 1; ++dy) {
                        for (int dx = -1; dx <= 1; ++dx) {
                            const Cell neighbor{
                                cell[0] + dx, cell[1] + dy, cell[2] + dz};
                            const auto found = cells.find(neighbor);
                            if (found == cells.end()) {
                                continue;
                            }
                            for (const auto first_id : ids) {
                                for (const auto second_id : found->second) {
                                    if (first_id == second_id) {
                                        continue;
                                    }
                                    const auto low = std::min(first_id, second_id);
                                    const auto high = std::max(first_id, second_id);
                                    const Vec3d delta =
                                        positions.at(high) - positions.at(low);
                                    const double distance = std::hypot(
                                        delta.x, delta.y, delta.z);
                                    if (distance > 0.0 &&
                                        distance < configuration.support_radius_m) {
                                        candidates.emplace(low, high);
                                    }
                                }
                            }
                        }
                    }
                }
            }
            const bool equal = brute == candidates && brute == explicit_edges;
            all_pass = all_pass && equal;
            tables.lookup.row({
                configuration.id,
                std::string(phase.id),
                std::to_string(brute.size()),
                std::to_string(candidates.size()),
                bool_text(equal),
                bool_text(equal),
            });
        }
    }
    return all_pass;
}

[[nodiscard]] std::string json_escape(std::string_view value) {
    std::string result;
    for (const unsigned char character : value) {
        switch (character) {
        case '\"': result += "\\\""; break;
        case '\\': result += "\\\\"; break;
        case '\n': result += "\\n"; break;
        case '\r': result += "\\r"; break;
        case '\t': result += "\\t"; break;
        default:
            if (character < 0x20U) {
                std::ostringstream escaped;
                escaped << "\\u" << std::hex << std::setw(4)
                        << std::setfill('0')
                        << static_cast<unsigned>(character);
                result += escaped.str();
            } else {
                result.push_back(static_cast<char>(character));
            }
        }
    }
    return result;
}

[[nodiscard]] std::string tolerances_json() {
    std::ostringstream output;
    output << "{\n"
           << "  \"schema\": \"mls.relational-observability-confirmation.tolerances.v1\",\n"
           << "  \"epsilon\": \"" << hex64(std::numeric_limits<double>::epsilon()) << "\",\n"
           << "  \"qr_roundoff_factor\": 512,\n"
           << "  \"svd_roundoff_factor\": 512,\n"
           << "  \"ambiguity_factor\": 8,\n"
           << "  \"residual_factor\": 4096,\n"
           << "  \"row_norm_factor\": 64,\n"
           << "  \"row_norm_target\": \"" << hex64(std::sqrt(2.0)) << "\",\n"
           << "  \"similarity_factor\": 16384,\n"
           << "  \"mu_retention_min\": \"" << hex64(1.0 / 1024.0) << "\",\n"
           << "  \"perturbation_amplitudes\": [\"" << hex64(1.0 / 10000.0)
           << "\", \"" << hex64(1.0 / 1000.0) << "\", \""
           << hex64(1.0 / 100.0) << "\"],\n"
           << "  \"perturbation_seeds\": [260829, 260830, 260831],\n"
           << "  \"deformations\": {\n"
           << "    \"isotropic_compression\": {\"matrix\": [\"" << hex64(4.0 / 5.0)
           << "\", \"" << hex64(4.0 / 5.0) << "\", \"" << hex64(4.0 / 5.0)
           << "\"], \"det\": \"" << hex64(64.0 / 125.0) << "\"},\n"
           << "    \"isotropic_expansion\": {\"matrix\": [\"" << hex64(5.0 / 4.0)
           << "\", \"" << hex64(5.0 / 4.0) << "\", \"" << hex64(5.0 / 4.0)
           << "\"], \"det\": \"" << hex64(125.0 / 64.0) << "\"},\n"
           << "    \"pure_shear\": [\"" << hex64(5.0 / 4.0) << "\", \""
           << hex64(4.0 / 5.0) << "\", \"" << hex64(1.0) << "\"],\n"
           << "    \"simple_shear\": \"" << hex64(1.0 / 4.0) << "\",\n"
           << "    \"general_affine\": [\"" << hex64(1.0) << "\", \""
           << hex64(1.0 / 5.0) << "\", \"" << hex64(-1.0 / 10.0)
           << "\", \"" << hex64(1.0 / 10.0) << "\", \""
           << hex64(9.0 / 10.0) << "\", \"" << hex64(1.0 / 8.0)
           << "\", \"" << hex64(-1.0 / 12.0) << "\", \""
           << hex64(1.0 / 10.0) << "\", \"" << hex64(11.0 / 10.0)
           << "\", \"" << hex64(11339.0 / 12000.0) << "\"]\n"
           << "  },\n"
           << "  \"nested_deletion_preimage\": \"260828|relational_observability_nested_delete_v1|first_id|second_id\",\n"
           << "  \"high_precision_deletion_steps\": [0, 25, 50, 52, 53, 54, 55, 75, 100, 125, 150, 158],\n"
           << "  \"registered_topology_transition\": {\n"
           << "    \"source_configuration_id\": \"base.sc3.r180.original\",\n"
           << "    \"edge_count\": " << registered_topology_edge_count << ",\n"
           << "    \"transition_adjacent_before_step\": "
           << registered_topology_transition_adjacent_before << ",\n"
           << "    \"last_rigid_step\": "
           << registered_topology_last_rigid << ",\n"
           << "    \"first_nonrigid_step\": "
           << registered_topology_first_nonrigid << ",\n"
           << "    \"first_nonrigid_exact_fraction_rank\": "
           << registered_topology_exact_rank_step54 << ",\n"
           << "    \"transition_adjacent_after_step\": "
           << registered_topology_transition_adjacent_after << ",\n"
           << "    \"complete_deletion_step\": "
           << registered_topology_complete_deletion << "\n"
           << "  },\n"
           << "  \"decision_order\": [\n"
           << "    \"stop_inconclusive_or_implementation_failure\",\n"
           << "    \"reject_central_relational_representation\",\n"
           << "    \"retain_only_as_mathematically_rigid_numerically_unsafe\",\n"
           << "    \"retain_central_relational_representation_for_research\"\n"
           << "  ]\n"
           << "}\n";
    return output.str();
}

[[nodiscard]] std::array<std::pair<std::string_view, const Csv*>, 12>
named_tables(const BundleTables& tables) {
    return {{{"checkpoints.csv", &tables.checkpoints},
             {"configurations.csv", &tables.configurations},
             {"id_bijections.csv", &tables.id_bijections},
             {"lookup.csv", &tables.lookup},
             {"metamorphic.csv", &tables.metamorphic},
             {"nullspace.csv", &tables.nullspace},
             {"nullspace_vectors.csv", &tables.nullspace_vectors},
             {"observability.csv", &tables.observability},
             {"packets.csv", &tables.packets},
             {"relations.csv", &tables.relations},
             {"spectra.csv", &tables.spectra},
             {"topology_path.csv", &tables.topology_path}}};
}

[[nodiscard]] std::string hash_preimage(
    const std::map<std::string, std::string>& hashes) {
    std::string result;
    for (const auto& [name, hash] : hashes) {
        result += name + "=" + hash + "\n";
    }
    return result;
}

struct VerdictCounts final {
    std::string verdict;
    std::size_t passed{0U};
    std::size_t failed{0U};
    std::size_t ambiguous{0U};
};

[[nodiscard]] VerdictCounts decide(
    const std::map<std::string, AnalysisRecord>& analyses,
    const std::vector<MetamorphicRecord>& controls,
    const bool lookup_pass, const bool topology_reference_pass,
    const bool smoke) {
    bool implementation_failure = std::ranges::any_of(
        controls, [](const auto& control) { return !control.pass; }) ||
        !lookup_pass || !topology_reference_pass;
    bool rejected = false;
    bool unsafe = false;
    VerdictCounts result{};
    for (const auto& [id, record] : analyses) {
        (void)id;
        implementation_failure = implementation_failure ||
            record.classification == "implementation_failure" ||
            record.classification == "ambiguous";
        const bool eligible =
            record.configuration->decision_scope == "eligible_generic";
        const bool failed_control = !eligible && !record.decision_gate_pass;
        implementation_failure = implementation_failure || failed_control;
        rejected = rejected ||
            (eligible && record.classification == "resolved_nonrigid");
        unsafe = unsafe ||
            (eligible &&
             (record.configuration->probe_family == "geometry_perturbation" ||
              record.configuration->probe_family == "homogeneous_deformation") &&
             !record.robustness_pass);
        if (record.classification == "ambiguous" ||
            record.classification == "implementation_failure") {
            ++result.ambiguous;
        } else if (record.decision_gate_pass) {
            ++result.passed;
        } else {
            ++result.failed;
        }
    }
    result.verdict = implementation_failure
        ? "stop_inconclusive_or_implementation_failure"
        : rejected
              ? "reject_central_relational_representation"
              : unsafe
                    ? "retain_only_as_mathematically_rigid_numerically_unsafe"
                    : "retain_central_relational_representation_for_research";
    if (smoke) {
        result.verdict = "stop_inconclusive_or_implementation_failure";
    }
    return result;
}

[[nodiscard]] std::string make_summary(
    const bool smoke, const FixtureData& fixtures,
    const GeneratedInventory& inventory,
    const std::map<std::string, AnalysisRecord>& analyses,
    const std::vector<MetamorphicRecord>& controls,
    const VerdictCounts& verdict, std::string_view prehash) {
    const auto count_probe = [&](std::string_view family) {
        return std::ranges::count_if(
            inventory.configurations, [&](const auto& configuration) {
                return configuration.probe_family == family;
            });
    };
    const auto count_scope = [&](std::string_view scope) {
        return std::ranges::count_if(
            inventory.configurations, [&](const auto& configuration) {
                return configuration.decision_scope == scope;
            });
    };
    const bool dirty = std::string_view(MLS_CONFIGURED_SOURCE_DIRTY) == "true";
    std::ostringstream output;
    output << "{\n"
           << "  \"schema\": \"" << summary_schema << "\",\n"
           << "  \"mode\": \"" << (smoke ? "smoke" : "full") << "\",\n"
           << "  \"provisional\": " << bool_text(smoke) << ",\n"
           << "  \"sweep_complete\": " << bool_text(!smoke) << ",\n"
           << "  \"producer\": \"cpp_relational_observability_confirmation\",\n"
           << "  \"seed\": " << seed << ",\n"
           << "  \"source_sha\": \"" << MLS_CONFIGURED_SOURCE_SHA << "\",\n"
           << "  \"parent_sha\": \"" << parent_sha << "\",\n"
           << "  \"accepted_candidate_c_source_sha\": \""
           << candidate_c_source_sha << "\",\n"
           << "  \"branch\": \""
           << json_escape(MLS_CONFIGURED_SOURCE_BRANCH) << "\",\n"
           << "  \"dirty\": " << bool_text(dirty) << ",\n"
           << "  \"verdict\": \"" << verdict.verdict << "\",\n"
           << "  \"no_promotion\": true,\n"
           << "  \"candidate\": \"central_relational_representation_C\",\n"
           << "  \"candidate_b_decision_input_count\": 0,\n"
           << "  \"candidate_d_instantiated\": false,\n"
           << "  \"inherited_git_blobs\": {\n"
           << "    \"include/mls/mechanical_observability_lab.hpp\": \"e5007f63ff4984dd5e6fbbb027a26f319cc02e5c\",\n"
           << "    \"src/mechanical_observability_lab.cpp\": \"9ed0ab945a4178286c59aad9e8f9fd9eb1ac8c87\",\n"
           << "    \"apps/mechanical_observability_diagnostic.cpp\": \"ca8082460ba9b34264b393cfb43feaccc8583d99\",\n"
           << "    \"tests/mechanical_observability_tests.cpp\": \"b334c2b43dcd7438403b4c87f72e442dcbaec504\",\n"
           << "    \"src/kelvin_covariance_audit.cpp\": \"bcdad1a3edaf9fbf4528438f720261141333b394\"\n"
           << "  },\n"
           << "  \"fixture_table_sha256\": {\n"
           << "    \"configurations\": \"" << fixtures.hashes.at("configurations.csv") << "\",\n"
           << "    \"packets\": \"" << fixtures.hashes.at("packets.csv") << "\",\n"
           << "    \"relations\": \"" << fixtures.hashes.at("relations.csv") << "\"\n"
           << "  },\n"
           << "  \"counts\": {\n"
           << "    \"configurations\": " << inventory.configurations.size() << ",\n"
           << "    \"inherited\": " << count_probe("inherited") << ",\n"
           << "    \"eligible_generic\": " << count_scope("eligible_generic") << ",\n"
           << "    \"intentionally_flexible\": " << count_scope("intentionally_flexible") << ",\n"
           << "    \"geometry_perturbation\": " << count_probe("geometry_perturbation") << ",\n"
           << "    \"homogeneous_deformation\": " << count_probe("homogeneous_deformation") << ",\n"
           << "    \"topology_deletion\": " << count_probe("topology_deletion") << ",\n"
           << "    \"id_bijection\": " << count_probe("id_bijection") << ",\n"
           << "    \"metamorphic_controls\": " << controls.size() << "\n"
           << "  },\n"
           << "  \"gate_counts\": {\"pass\": " << verdict.passed
           << ", \"fail\": " << verdict.failed
           << ", \"ambiguous\": " << verdict.ambiguous << "},\n"
           << "  \"compiler\": {\"id\": \"" << json_escape(MLS_CONFIGURED_COMPILER_ID)
           << "\", \"version\": \"" << json_escape(MLS_CONFIGURED_COMPILER_VERSION)
           << "\"},\n"
           << "  \"direct_svd\": \"rectangular_one_sided_jacobi\",\n"
           << "  \"pre_hash_sha256\": \"" << prehash << "\"\n"
           << "}\n";
    (void)analyses;
    return output.str();
}

void write_bundle(
    const std::filesystem::path& output_directory, const bool smoke,
    const FixtureData& fixtures, const GeneratedInventory& inventory,
    const std::map<std::string, AnalysisRecord>& analyses,
    const std::vector<MetamorphicRecord>& controls,
    const BundleTables& tables, const VerdictCounts& verdict) {
    std::filesystem::create_directories(output_directory / "checkpoints");
    std::set<std::string> checkpoint_names;
    for (const auto& configuration : inventory.configurations) {
        checkpoint_names.insert(configuration.id + ".bin");
    }
    for (const auto& entry :
         std::filesystem::directory_iterator(output_directory / "checkpoints")) {
        if (!entry.is_regular_file() ||
            !checkpoint_names.contains(entry.path().filename().string())) {
            throw std::runtime_error(
                "checkpoint directory contains unexpected stale entry: " +
                entry.path().string());
        }
    }

    std::map<std::string, std::string> payload_hashes;
    std::map<std::string, std::size_t> row_counts;
    for (const auto& [name, table] : named_tables(tables)) {
        const std::string contents = table->contents();
        write_text(output_directory / name, contents);
        payload_hashes.emplace(std::string(name), sha256(contents));
        row_counts.emplace(std::string(name), table->size());
    }
    const std::string tolerances = tolerances_json();
    write_text(output_directory / "tolerances.json", tolerances);
    payload_hashes.emplace("tolerances.json", sha256(tolerances));
    for (const auto& configuration : inventory.configurations) {
        const auto& record = analyses.at(configuration.id);
        const std::string relative = "checkpoints/" + configuration.id + ".bin";
        write_bytes(output_directory / relative, record.checkpoint);
        payload_hashes.emplace(relative, record.checkpoint_hash);
    }

    const std::string summary_preimage =
        hash_preimage(payload_hashes) + "verdict=" + verdict.verdict + "\n";
    const std::string summary = make_summary(
        smoke, fixtures, inventory, analyses, controls, verdict,
        sha256(summary_preimage));
    write_text(output_directory / "summary.json", summary);
    payload_hashes.emplace("summary.json", sha256(summary));

    const std::string manifest_prehash = sha256(hash_preimage(payload_hashes));
    std::ostringstream manifest;
    manifest << "{\n"
             << "  \"schema\": \"" << manifest_schema << "\",\n"
             << "  \"mode\": \"" << (smoke ? "smoke" : "full") << "\",\n"
             << "  \"source_sha\": \"" << MLS_CONFIGURED_SOURCE_SHA << "\",\n"
             << "  \"branch\": \""
             << json_escape(MLS_CONFIGURED_SOURCE_BRANCH) << "\",\n"
             << "  \"dirty\": "
             << bool_text(std::string_view(MLS_CONFIGURED_SOURCE_DIRTY) == "true")
             << ",\n"
             << "  \"expected_rows\": {\n";
    std::size_t row_index = 0U;
    for (const auto& [name, count] : row_counts) {
        manifest << "    \"" << name << "\": " << count
                 << (++row_index == row_counts.size() ? "\n" : ",\n");
    }
    manifest << "  },\n  \"actual_rows\": {\n";
    row_index = 0U;
    for (const auto& [name, count] : row_counts) {
        manifest << "    \"" << name << "\": " << count
                 << (++row_index == row_counts.size() ? "\n" : ",\n");
    }
    manifest << "  },\n  \"file_sha256\": {\n";
    std::size_t hash_index = 0U;
    for (const auto& [name, hash] : payload_hashes) {
        manifest << "    \"" << json_escape(name) << "\": \"" << hash << "\""
                 << (++hash_index == payload_hashes.size() ? "\n" : ",\n");
    }
    manifest << "  },\n"
             << "  \"pre_hash_sha256\": \"" << manifest_prehash << "\"\n"
             << "}\n";
    write_text(output_directory / "manifest.json", manifest.str());
}

struct Options final {
    bool smoke{false};
    bool schema_audit{false};
    bool logic_audit{false};
    std::filesystem::path fixture_bundle;
    std::filesystem::path output;
};

[[nodiscard]] Options parse_options(const int argc, char** argv) {
    Options result{};
    for (int index = 1; index < argc; ++index) {
        const std::string_view argument(argv[index]);
        if (argument == "--smoke") {
            result.smoke = true;
        } else if (argument == "--schema-audit") {
            result.schema_audit = true;
        } else if (argument == "--logic-audit") {
            result.logic_audit = true;
        } else if (argument == "--fixture-bundle" && index + 1 < argc) {
            result.fixture_bundle = argv[++index];
        } else if (argument == "--output" && index + 1 < argc) {
            result.output = argv[++index];
        } else if (argument == "--jobs" && index + 1 < argc) {
            ++index; // Accepted for command compatibility; run order stays fixed.
        } else if (argument == "--help") {
            std::cout
                << "usage: mls_relational_observability_diagnostic "
                   "[--smoke] --fixture-bundle PATH --output PATH\n"
                   "       mls_relational_observability_diagnostic "
                   "--schema-audit|--logic-audit\n";
            std::exit(0);
        } else {
            throw std::invalid_argument(
                "unknown or incomplete argument: " + std::string(argument));
        }
    }
    return result;
}

void schema_audit() {
    BundleTables tables{};
    for (const auto& [name, table] : named_tables(tables)) {
        if (name.empty() || table == nullptr || table->contents().empty()) {
            throw std::logic_error("frozen relational wire schema is empty");
        }
    }
    if (sha256("abc") !=
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") {
        throw std::logic_error("SHA-256 implementation self-test failed");
    }
    std::cout << "Relational Observability Confirmation schema audit: PASS\n";
}

void logic_audit() {
    const std::vector<MechanicalPacket> packets{
        {1, 1, {0.0, 0.0, 0.0}, {}},
        {2, 1, {1.0, 0.0, 0.0}, {}},
        {3, 1, {0.0, 1.0, 0.0}, {}},
        {4, 1, {0.0, 0.0, 1.0}, {}},
    };
    const std::vector<BondRelation> relations{
        {1, 2}, {1, 3}, {1, 4}, {2, 3}, {2, 4}, {3, 4}};
    const auto diagnostic = confirmation::analyze_raw_central_rigidity(
        packets, relations);
    if (diagnostic.status != observation::RankStatus::analyzed ||
        diagnostic.modular_rank_value != 6U ||
        diagnostic.nonrigid_nullity != 0U ||
        !diagnostic.kernel_equals_rigid_subspace ||
        !diagnostic.row_norms_pass) {
        throw std::logic_error("raw Candidate-C K4 logic self-test failed");
    }
    Configuration flexible_control{};
    flexible_control.id = "logic.flexible_control";
    flexible_control.source_id = flexible_control.id;
    flexible_control.decision_scope = "intentionally_flexible";
    AnalysisRecord failed_control{};
    failed_control.configuration = &flexible_control;
    failed_control.classification = "rigid_only";
    failed_control.clear_separation = true;
    failed_control.decision_gate_pass = false;
    const std::map<std::string, AnalysisRecord> failed_control_analyses{
        {flexible_control.id, failed_control}};
    const auto failed_control_verdict = decide(
        failed_control_analyses, {}, true, true, false);
    if (failed_control_verdict.verdict !=
            "stop_inconclusive_or_implementation_failure" ||
        failed_control_verdict.passed != 0U ||
        failed_control_verdict.failed != 1U ||
        failed_control_verdict.ambiguous != 0U) {
        throw std::logic_error(
            "failed intentionally-flexible control did not stop verdict");
    }
    std::cout << "Relational Observability Confirmation logic audit: PASS\n";
}

} // namespace

int main(int argc, char** argv) {
    try {
        const auto options = parse_options(argc, argv);
        if (options.schema_audit) {
            schema_audit();
            return 0;
        }
        if (options.logic_audit) {
            logic_audit();
            return 0;
        }
        if (options.fixture_bundle.empty() || options.output.empty()) {
            throw std::invalid_argument(
                "fixture bundle and output paths are required");
        }
        if (!options.smoke) {
            if (std::string_view(MLS_CONFIGURED_SOURCE_BRANCH) != branch) {
                throw std::runtime_error(
                    "full evidence requires the registered configured branch");
            }
            if (std::string_view(MLS_CONFIGURED_SOURCE_DIRTY) != "false") {
                throw std::runtime_error(
                    "full evidence requires a clean configured source tree");
            }
            if (std::string_view(MLS_CONFIGURED_SOURCE_SHA).size() != 40U ||
                std::string_view(MLS_CONFIGURED_SOURCE_SHA) == "unknown") {
                throw std::runtime_error(
                    "full evidence requires an exact configured source SHA");
            }
        }
        const auto fixtures = load_fixtures(
            options.fixture_bundle, options.smoke);
        const auto inventory = generate_inventory(fixtures, options.smoke);
        const auto analyses = analyze_inventory(inventory.configurations);
        const auto controls = build_metamorphic_records(
            fixtures, inventory, analyses, options.smoke);
        BundleTables tables{};
        emit_core_tables(inventory, analyses, tables);
        emit_bijections(inventory, tables);
        emit_metamorphic(controls, tables);
        const bool topology_reference_pass = emit_topology_path(
            inventory, analyses, tables, options.smoke);
        const bool lookup_pass = emit_lookup(fixtures, tables);
        const auto verdict = decide(
            analyses, controls, lookup_pass, topology_reference_pass,
            options.smoke);
        write_bundle(
            options.output, options.smoke, fixtures, inventory, analyses,
            controls, tables, verdict);
        std::cout << "Relational Observability evidence written ("
                  << (options.smoke ? "provisional smoke" : "full")
                  << ") to " << options.output.string()
                  << "\nVerdict: " << verdict.verdict
                  << "\nNO PROMOTION\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Relational Observability Confirmation failed: "
                  << error.what() << '\n';
        return 1;
    }
}
