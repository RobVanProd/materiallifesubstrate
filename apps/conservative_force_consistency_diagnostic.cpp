#include "mls/conservative_force_consistency_lab.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <locale>
#include <map>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
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

namespace force =
    mls::experimental::conservative_force_consistency;
namespace constitutive = mls::experimental::constitutive_expressivity;
namespace observation = mls::experimental::mechanical_observability;
using mls::experimental::Matrix3d;
using mls::experimental::Vec3d;
using observation::BondRelation;
using observation::DenseMatrix;
using observation::MechanicalPacket;

static_assert(sizeof(double) == 8U);
static_assert(std::numeric_limits<double>::digits == 53);
static_assert(std::numeric_limits<double>::is_iec559);

constexpr std::uint64_t seed = 260828U;
constexpr std::string_view parent_sha =
    "2de8843faf76a75d16b3a3012897e719291c52cf";
constexpr std::string_view preregistration_commit =
    "d19cabc47849e0aab178915e90adcfc9df5a6fe1";
constexpr std::string_view parent_manifest_prehash =
    "18b1af6837f2c67204094498eedd2a8d8eabaf315ebae1d58c4b2073b778973f";
constexpr std::string_view selected_configurations_hash =
    "45d162381ec723dd9ce744f2cc23c4d21435a52b7c7e60a182073ee19a08d60e";
constexpr std::string_view selected_packets_hash =
    "843c9cb22c0b55e07c207135125a8334b0dd170a0f708aa1fb50f34d4c5d7363";
constexpr std::string_view selected_relations_hash =
    "0b2e21dcbf26454af316bec9323627aa1488ebc7aa1f14c006bfb41a231e0e6f";
constexpr std::string_view selected_graph_energy_hash =
    "c1173a8c167d3076a6e8afcb756e539020a8a12fb2e49bb11af3205f0613d874";
constexpr std::string_view selected_provenance_hash =
    "396e3273159d833ae59669e71ca5b5543e30d8c088c617aa102d5abf1508f414";
constexpr std::string_view summary_schema =
    "mls.conservative-force-consistency.raw-summary.v1";
constexpr std::string_view manifest_schema =
    "mls.conservative-force-consistency.raw-manifest.v1";

constexpr std::array<std::string_view, 8> registered_configuration_ids{
    "exact.tetrahedron_k4",
    "exact.octahedron_graph",
    "base.sc3.r180.original",
    "base.bcc35.r180.original",
    "base.jitter27.r180.original",
    "base.free_face.r180.original",
    "base.sc3_deletion.delete25.original",
    "exact.tetrahedron_k4_minus_edge",
};

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
    explicit Csv(std::string_view header)
        : header_(header), width_(split_header(header).size()) {}

    void row(Row values) {
        if (values.size() != width_) {
            throw std::logic_error("CSV row differs from registered width");
        }
        rows_.push_back(std::move(values));
    }

    [[nodiscard]] std::size_t size() const noexcept { return rows_.size(); }
    [[nodiscard]] std::string_view header() const noexcept { return header_; }

    [[nodiscard]] std::string contents() const {
        std::string result{header_};
        result.push_back('\n');
        for (const auto& values : rows_) {
            for (std::size_t index = 0; index < values.size(); ++index) {
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
    std::string header_;
    std::size_t width_{0U};
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

[[nodiscard]] std::string hex64(double value) {
    if (!std::isfinite(value)) {
        throw std::overflow_error("non-finite value cannot be emitted");
    }
    const auto bits = std::bit_cast<std::uint64_t>(value);
    const auto negative = (bits >> 63U) != 0U;
    const auto exponent_bits = static_cast<unsigned>((bits >> 52U) & 0x7ffU);
    const auto fraction = bits & UINT64_C(0x000fffffffffffff);
    if (exponent_bits == 0U && fraction == 0U) {
        // Evidence has one canonical representation of real zero. Sign-bit
        // artifacts from a negated zero are not physical data.
        return "0x0.0p+0";
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

[[nodiscard]] std::string bool_text(bool value) {
    return value ? "true" : "false";
}

[[nodiscard]] std::string_view evidence_status(
    force::ForceDomainStatus status) noexcept {
    return status == force::ForceDomainStatus::evaluated
        ? std::string_view{"valid_noncoincident"}
        : std::string_view{"coincident_relation"};
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
        throw std::runtime_error("cannot write output: " + path.string());
    }
    stream.write(value.data(), static_cast<std::streamsize>(value.size()));
    if (!stream) {
        throw std::runtime_error("failed writing output: " + path.string());
    }
}

[[nodiscard]] std::vector<Row> parse_csv(std::string_view input) {
    std::vector<Row> rows;
    Row row;
    std::string field;
    bool quoted = false;
    for (std::size_t index = 0U; index < input.size(); ++index) {
        const auto character = input[index];
        if (quoted) {
            if (character == '\"' && index + 1U < input.size() &&
                input[index + 1U] == '\"') {
                field.push_back('\"');
                ++index;
            } else if (character == '\"') {
                quoted = false;
            } else {
                field.push_back(character);
            }
        } else if (character == '\"') {
            quoted = true;
        } else if (character == ',') {
            row.push_back(std::move(field));
            field.clear();
        } else if (character == '\r' || character == '\n') {
            if (character == '\r' && index + 1U < input.size() &&
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
            field.push_back(character);
        }
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
        result.emplace(header[index], index);
    }
    return result;
}

[[nodiscard]] double parse_double(std::string_view value) {
    std::string storage(value);
    char* end = nullptr;
    const auto result = std::strtod(storage.c_str(), &end);
    if (end == storage.c_str() || *end != '\0' || !std::isfinite(result)) {
        throw std::runtime_error("invalid binary64 field");
    }
    return result;
}

template <typename Integer>
[[nodiscard]] Integer parse_integer(std::string_view value) {
    Integer result{};
    const auto parsed = std::from_chars(
        value.data(), value.data() + value.size(), result);
    if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size()) {
        throw std::runtime_error("invalid integer field");
    }
    return result;
}

struct GraphConfiguration final {
    std::string id{};
    std::string role{};
    std::vector<MechanicalPacket> packets{};
    std::vector<BondRelation> relations{};
    bool intentionally_floppy{false};
};

[[nodiscard]] bool selected_id(std::string_view id) {
    return std::ranges::find(registered_configuration_ids, id) !=
        registered_configuration_ids.end();
}

[[nodiscard]] std::string role_for(std::string_view id) {
    if (id == "exact.tetrahedron_k4" || id == "exact.octahedron_graph") {
        return "exact_rigid";
    }
    if (id == "base.sc3.r180.original") {
        return "regular_bulk";
    }
    if (id == "base.bcc35.r180.original") {
        return "bcc_like_bulk";
    }
    if (id == "base.jitter27.r180.original") {
        return "jittered_bulk";
    }
    if (id == "base.free_face.r180.original") {
        return "free_surface";
    }
    if (id == "base.sc3_deletion.delete25.original") {
        return "relation_deletion";
    }
    return "intentionally_floppy";
}

struct FixtureInput final {
    std::vector<GraphConfiguration> configurations{};
    std::map<std::string, std::string> hashes{};
};

[[nodiscard]] std::vector<GraphConfiguration> smoke_graphs() {
    const std::vector<MechanicalPacket> packets{
        {1, 1, {0.0, 0.0, 0.0}, {}},
        {2, 1, {1.0, 0.0, 0.0}, {}},
        {3, 1, {0.0, 1.0, 0.0}, {}},
        {4, 1, {0.0, 0.0, 1.0}, {}},
    };
    const std::vector<BondRelation> complete{
        {1, 2}, {1, 3}, {1, 4}, {2, 3}, {2, 4}, {3, 4}};
    auto missing = complete;
    missing.pop_back();
    return {
        {"exact.tetrahedron_k4", "exact_rigid", packets, complete, false},
        {"exact.tetrahedron_k4_minus_edge", "intentionally_floppy",
         packets, missing, true},
    };
}

[[nodiscard]] FixtureInput load_fixture_bundle(
    const std::filesystem::path& directory) {
    const auto configurations_text =
        read_binary_text(directory / "configurations.csv");
    const auto packets_text = read_binary_text(directory / "packets.csv");
    const auto relations_text = read_binary_text(directory / "relations.csv");
    const auto graph_energy_text =
        read_binary_text(directory / "graph_energy.csv");
    const auto provenance_text =
        read_binary_text(directory / "provenance.json");
    const auto manifest_text = read_binary_text(directory / "manifest.json");
    FixtureInput result{};
    result.hashes = {{"configurations.csv", sha256(configurations_text)},
                     {"packets.csv", sha256(packets_text)},
                     {"relations.csv", sha256(relations_text)},
                     {"graph_energy.csv", sha256(graph_energy_text)},
                     {"provenance.json", sha256(provenance_text)}};
    if (result.hashes.at("configurations.csv") !=
            selected_configurations_hash ||
        result.hashes.at("packets.csv") != selected_packets_hash ||
        result.hashes.at("relations.csv") != selected_relations_hash ||
        result.hashes.at("graph_energy.csv") != selected_graph_energy_hash ||
        result.hashes.at("provenance.json") != selected_provenance_hash ||
        manifest_text.find(std::string(parent_manifest_prehash)) ==
            std::string::npos) {
        throw std::runtime_error(
            "accepted constitutive parent bundle hash mismatch");
    }
    auto configuration_rows = parse_csv(configurations_text);
    auto packet_rows = parse_csv(packets_text);
    auto relation_rows = parse_csv(relations_text);
    const auto ch = header_map(configuration_rows.at(0));
    const auto ph = header_map(packet_rows.at(0));
    const auto rh = header_map(relation_rows.at(0));
    std::map<std::string, std::size_t> lookup;
    std::map<std::string, std::pair<std::size_t, std::size_t>> expected_sizes;
    for (std::size_t row = 1U; row < configuration_rows.size(); ++row) {
        const auto& id =
            configuration_rows[row].at(ch.at("configuration_id"));
        if (!selected_id(id)) {
            continue;
        }
        lookup.emplace(id, result.configurations.size());
        result.configurations.push_back(
            {id, role_for(id), {}, {},
             id == "exact.tetrahedron_k4_minus_edge"});
        expected_sizes.emplace(
            id,
            std::pair{
                parse_integer<std::size_t>(
                    configuration_rows[row].at(ch.at("packet_count"))),
                parse_integer<std::size_t>(
                    configuration_rows[row].at(ch.at("relation_count")))});
    }
    for (std::size_t row = 1U; row < packet_rows.size(); ++row) {
        const auto& values = packet_rows[row];
        const auto found = lookup.find(values.at(ph.at("configuration_id")));
        if (found == lookup.end()) {
            continue;
        }
        auto& configuration = result.configurations[found->second];
        const auto inherited_index = parse_integer<std::size_t>(
            values.at(ph.at("packet_index")));
        if (inherited_index != configuration.packets.size()) {
            throw std::runtime_error(
                "accepted parent packet coordinates are not canonical");
        }
        configuration.packets.push_back({
            parse_integer<std::uint64_t>(values.at(ph.at("packet_id"))),
            parse_integer<std::int64_t>(values.at(ph.at("mass_quanta"))),
            {parse_double(values.at(ph.at("x_m"))),
             parse_double(values.at(ph.at("y_m"))),
             parse_double(values.at(ph.at("z_m")))},
            {}});
    }
    for (std::size_t row = 1U; row < relation_rows.size(); ++row) {
        const auto& values = relation_rows[row];
        const auto found = lookup.find(values.at(rh.at("configuration_id")));
        if (found == lookup.end()) {
            continue;
        }
        auto& configuration = result.configurations[found->second];
        const auto inherited_index = parse_integer<std::size_t>(
            values.at(rh.at("relation_index")));
        if (inherited_index != configuration.relations.size()) {
            throw std::runtime_error(
                "accepted parent relation coordinates are not canonical");
        }
        configuration.relations.push_back({
            parse_integer<std::uint64_t>(values.at(rh.at("first_id"))),
            parse_integer<std::uint64_t>(values.at(rh.at("second_id")))});
    }
    if (result.configurations.size() != registered_configuration_ids.size()) {
        throw std::runtime_error("registered fixture configuration missing");
    }
    for (auto& configuration : result.configurations) {
        const auto expected = expected_sizes.at(configuration.id);
        if (configuration.packets.size() != expected.first ||
            configuration.relations.size() != expected.second) {
            throw std::runtime_error(
                "accepted parent coordinate inventory is incomplete");
        }
        static_cast<void>(observation::build_bond_rigidity_operator(
            configuration.packets, configuration.relations));
    }
    return result;
}

[[nodiscard]] std::vector<constitutive::WeightedRelation> weighted_relations(
    std::span<const BondRelation> relations) {
    std::vector<constitutive::WeightedRelation> result;
    result.reserve(relations.size());
    for (const auto relation : relations) {
        result.push_back({relation, 1.0});
    }
    return result;
}

[[nodiscard]] Vec3d centroid(std::span<const MechanicalPacket> packets) {
    Vec3d result{};
    for (const auto& packet : packets) {
        result += packet.position_m;
    }
    return result / static_cast<double>(packets.size());
}

[[nodiscard]] Matrix3d general_deformation() {
    Matrix3d result{};
    result.value = {{{21.0 / 20.0, 1.0 / 20.0, -1.0 / 40.0},
                     {0.0, 19.0 / 20.0, 1.0 / 25.0},
                     {1.0 / 50.0, 0.0, 11.0 / 10.0}}};
    return result;
}

[[nodiscard]] Matrix3d shear_deformation() {
    Matrix3d result = Matrix3d::identity();
    result.value[0][1] = 3.0 / 20.0;
    result.value[1][2] = 1.0 / 20.0;
    return result;
}

[[nodiscard]] Matrix3d compression_deformation() {
    Matrix3d result{};
    result.value[0][0] = 4.0 / 5.0;
    result.value[1][1] = 9.0 / 10.0;
    result.value[2][2] = 17.0 / 20.0;
    return result;
}

[[nodiscard]] std::vector<MechanicalPacket> deform_about_centroid(
    std::span<const MechanicalPacket> packets, const Matrix3d& deformation) {
    const auto center = centroid(packets);
    std::vector<MechanicalPacket> result(packets.begin(), packets.end());
    for (auto& packet : result) {
        packet.position_m = center + mls::experimental::multiply(
            deformation, packet.position_m - center);
    }
    return result;
}

[[nodiscard]] Matrix3d axis_angle(Vec3d axis, double angle) {
    axis = axis / mls::experimental::norm(axis);
    const auto c = std::cos(angle);
    const auto s = std::sin(angle);
    const auto one_minus_c = 1.0 - c;
    Matrix3d result{};
    result.value = {{{c + axis.x * axis.x * one_minus_c,
                      axis.x * axis.y * one_minus_c - axis.z * s,
                      axis.x * axis.z * one_minus_c + axis.y * s},
                     {axis.y * axis.x * one_minus_c + axis.z * s,
                      c + axis.y * axis.y * one_minus_c,
                      axis.y * axis.z * one_minus_c - axis.x * s},
                     {axis.z * axis.x * one_minus_c - axis.y * s,
                      axis.z * axis.y * one_minus_c + axis.x * s,
                      c + axis.z * axis.z * one_minus_c}}};
    return result;
}

[[nodiscard]] std::vector<MechanicalPacket> rigid_transform(
    std::span<const MechanicalPacket> packets, const Matrix3d& rotation,
    Vec3d translation, double scale = 1.0) {
    std::vector<MechanicalPacket> result(packets.begin(), packets.end());
    for (auto& packet : result) {
        packet.position_m = scale *
                mls::experimental::multiply(rotation, packet.position_m) +
            translation;
        packet.velocity_m_per_s = scale *
            mls::experimental::multiply(rotation, packet.velocity_m_per_s);
    }
    return result;
}

[[nodiscard]] std::uint64_t splitmix64(std::uint64_t& state) noexcept {
    state += UINT64_C(0x9e3779b97f4a7c15);
    auto value = state;
    value = (value ^ (value >> 30U)) * UINT64_C(0xbf58476d1ce4e5b9);
    value = (value ^ (value >> 27U)) * UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31U);
}

[[nodiscard]] double random_signed(std::uint64_t& state) noexcept {
    constexpr auto scale = 1.0 / 9007199254740992.0;
    return 2.0 * static_cast<double>(splitmix64(state) >> 11U) * scale - 1.0;
}

[[nodiscard]] std::vector<Vec3d> normalized_random_vectors(
    std::size_t count, std::uint64_t stream) {
    std::vector<Vec3d> result(count);
    double squared = 0.0;
    auto state = seed ^ stream;
    for (auto& value : result) {
        value = {random_signed(state), random_signed(state), random_signed(state)};
        squared += value.x * value.x + value.y * value.y + value.z * value.z;
    }
    const auto inverse = 1.0 / std::sqrt(squared);
    for (auto& value : result) {
        value = inverse * value;
    }
    return result;
}

[[nodiscard]] std::vector<Vec3d> normalized_rigid_velocity(
    std::span<const MechanicalPacket> packets, Vec3d translation,
    Vec3d rotation_axis) {
    const auto center = centroid(packets);
    std::vector<Vec3d> result;
    result.reserve(packets.size());
    double squared = 0.0;
    for (const auto& packet : packets) {
        const auto value = translation +
            mls::experimental::cross(
                rotation_axis, packet.position_m - center);
        result.push_back(value);
        squared += value.x * value.x + value.y * value.y + value.z * value.z;
    }
    const auto inverse = 1.0 / std::sqrt(squared);
    for (auto& value : result) {
        value = inverse * value;
    }
    return result;
}

[[nodiscard]] std::vector<Vec3d> affine_velocity(
    std::span<const MechanicalPacket> packets) {
    Matrix3d gradient{};
    gradient.value = {{{1.0 / 7.0, -1.0 / 11.0, 1.0 / 13.0},
                       {2.0 / 17.0, -1.0 / 19.0, 1.0 / 23.0},
                       {-1.0 / 29.0, 2.0 / 31.0, 1.0 / 37.0}}};
    std::vector<Vec3d> result;
    result.reserve(packets.size());
    for (const auto& packet : packets) {
        result.push_back(
            mls::experimental::multiply(gradient, packet.position_m) +
            Vec3d{1.0 / 5.0, -1.0 / 7.0, 1.0 / 11.0});
    }
    return result;
}

[[nodiscard]] std::vector<MechanicalPacket> with_velocities(
    std::span<const MechanicalPacket> packets,
    std::span<const Vec3d> velocities) {
    if (packets.size() != velocities.size()) {
        throw std::invalid_argument("velocity probe size mismatch");
    }
    std::vector<MechanicalPacket> result(packets.begin(), packets.end());
    for (std::size_t index = 0; index < result.size(); ++index) {
        result[index].velocity_m_per_s = velocities[index];
    }
    return result;
}

[[nodiscard]] double max_abs(const DenseMatrix& matrix) noexcept {
    double result = 0.0;
    for (const auto value : matrix.entries()) {
        result = std::max(result, std::abs(value));
    }
    return result;
}

[[nodiscard]] double frobenius_norm(const DenseMatrix& matrix) noexcept {
    double scale = 0.0;
    for (const auto value : matrix.entries()) {
        scale = std::max(scale, std::abs(value));
    }
    if (scale == 0.0) {
        return 0.0;
    }
    double sum = 0.0;
    for (const auto value : matrix.entries()) {
        const auto normalized = value / scale;
        sum += normalized * normalized;
    }
    return scale * std::sqrt(sum);
}

[[nodiscard]] double packet_force_l2_norm(
    std::span<const force::PacketForce> packet_forces) noexcept {
    double scale = 0.0;
    for (const auto& packet : packet_forces) {
        scale = std::max(
            {scale, std::abs(packet.force_n.x), std::abs(packet.force_n.y),
             std::abs(packet.force_n.z)});
    }
    if (scale == 0.0) {
        return 0.0;
    }
    double sum = 0.0;
    for (const auto& packet : packet_forces) {
        for (const auto value :
             std::array{packet.force_n.x, packet.force_n.y,
                        packet.force_n.z}) {
            const auto normalized = value / scale;
            sum += normalized * normalized;
        }
    }
    return scale * std::sqrt(sum);
}

[[nodiscard]] double vector_norm(Vec3d value) noexcept {
    return std::sqrt(mls::experimental::dot(value, value));
}

[[nodiscard]] double characteristic_length(
    const force::FrozenForceOperator& energy_operator) {
    return *std::ranges::max_element(
        energy_operator.force_operator.reference_lengths_m);
}

[[nodiscard]] std::string operator_id(
    std::string_view configuration, double ratio) {
    std::string suffix;
    if (ratio == 1.0 / 3.0) {
        suffix = "one_third";
    } else if (ratio == 2.0) {
        suffix = "two";
    } else {
        suffix = "ten";
    }
    return std::string(configuration) + ".collective." + suffix;
}

[[nodiscard]] std::string_view ratio_label(double ratio) {
    if (ratio == 1.0 / 3.0) {
        return "1/3";
    }
    if (ratio == 2.0) {
        return "2";
    }
    if (ratio == 10.0) {
        return "10";
    }
    throw std::invalid_argument("unregistered K/G ratio");
}

struct OperatorCase final {
    std::string id{};
    const GraphConfiguration* graph{nullptr};
    double target_ratio{0.0};
    double a{0.0};
    double b{0.25};
    force::FrozenForceOperator frozen{};
};

[[nodiscard]] OperatorCase build_operator(
    const GraphConfiguration& graph, double ratio) {
    const auto parent = constitutive::build_local_collective_energy(
        graph.packets, weighted_relations(graph.relations),
        {.dilatational_coefficient_j_per_m2 = 3.0 * ratio / 20.0,
         .deviatoric_coefficient_j_per_m2 = 0.25});
    if (parent.relations != graph.relations) {
        throw std::runtime_error(
            "constitutive rebuild changed inherited relation coordinates");
    }
    return {operator_id(graph.id, ratio), &graph, ratio,
            3.0 * ratio / 20.0, 0.25,
            force::freeze_symmetric_force_operator(parent)};
}

struct Tables final {
    Csv configurations{
        "configuration_id,parent_source_id,role,packet_count,relation_count"};
    Csv reference_packets{
        "configuration_id,packet_index,packet_id,semantic_packet_id,mass_quanta,x_m,y_m,z_m"};
    Csv relations{
        "configuration_id,relation_index,first_id,second_id,semantic_first_id,semantic_second_id,reference_length_m,weight"};
    Csv operators{
        "operator_id,configuration_id,family,target_k_over_g,a_j_per_m2,b_j_per_m2"};
    Csv h_matrix{
        "operator_id,row_relation_index,column_relation_index,parent_value_j_per_m2,frozen_value_j_per_m2,correction_j_per_m2"};
    Csv current_packets{
        "evaluation_id,packet_index,packet_id,semantic_packet_id,x_m,y_m,z_m,vx_m_per_s,vy_m_per_s,vz_m_per_s"};
    Csv force_evaluations{
        "evaluation_id,operator_id,probe,velocity_probe,status,energy_j,extension_power_w,negative_force_power_w,power_residual_w,total_force_x_n,total_force_y_n,total_force_z_n,total_torque_origin_x_nm,total_torque_origin_y_nm,total_torque_origin_z_nm,total_torque_shifted_x_nm,total_torque_shifted_y_nm,total_torque_shifted_z_nm,balance_scale_force_n,balance_scale_torque_nm,balance_scale_power_w,tolerance_force_n,tolerance_torque_nm,tolerance_power_w,pass"};
    Csv relation_forces{
        "evaluation_id,relation_index,first_id,second_id,reference_length_m,current_length_m,extension_m,conjugate_force_n,direction_x,direction_y,direction_z"};
    Csv packet_forces{
        "evaluation_id,packet_index,packet_id,semantic_packet_id,force_x_n,force_y_n,force_z_n"};
    Csv reference_tangent{
        "operator_id,evaluation_id,direction_id,direction_kind,epsilon_index,epsilon_over_l,epsilon_m,error_infinity_scaled,observed_order,minimum_relative_error,three_consecutive_decreases,median_order,pass"};
    Csv finite_tangent{
        "evaluation_id,row_dof,column_dof,row_semantic_packet_id,row_axis,column_semantic_packet_id,column_axis,step_index,h_over_l,material_n_per_m,geometric_n_per_m,total_energy_hessian_n_per_m,force_jacobian_n_per_m,raw_binary64_force_jacobian_n_per_m,raw_gradient_residual_n_per_m,decomposition_residual_n_per_m,symmetry_residual_n_per_m,tolerance_n_per_m,pass"};
    Csv metamorphic{
        "baseline_evaluation_id,probe_evaluation_id,probe,packet_coordinate_map,relation_coordinate_map,transformed_h_sha256,scale,expected_energy_ratio,actual_energy_ratio,energy_residual_j,force_covariance_residual_n,tangent_covariance_residual_n_per_m,relation_conjugate_residual_n,energy_tolerance_j,force_tolerance_n,tangent_tolerance_n_per_m,conjugate_tolerance_n,scaling_ratio_tolerance,pass"};
    Csv compression{
        "operator_id,evaluation_id,relation_index,length_ratio,registered_domain_row,status,minimum_length_m,force_norm_n,material_tangent_norm_n_per_m,geometric_tangent_norm_n_per_m,total_tangent_norm_n_per_m,condition_estimate,binary64_gradient_error_n,ulp_coordinate_sensitivity_n,adjacent_length_resolved,pass"};
};

struct EvaluationRecord final {
    std::string id{};
    std::string probe{};
    std::string velocity_probe{};
    const OperatorCase* operator_case{nullptr};
    std::vector<MechanicalPacket> current{};
    std::map<std::uint64_t, std::uint64_t> semantic_by_actual{};
    force::SpatialForceEvaluation force{};
};

struct Counts final {
    std::size_t force_evaluations{0U};
    std::size_t valid_evaluations{0U};
    std::size_t coincident_failures{0U};
    std::size_t raw_registered_failures{0U};
    bool exact_coincidence_failed_closed{true};
};

[[nodiscard]] std::map<std::uint64_t, std::uint64_t> identity_semantics(
    std::span<const MechanicalPacket> packets) {
    std::map<std::uint64_t, std::uint64_t> result;
    for (const auto& packet : packets) {
        result.emplace(packet.id, packet.id);
    }
    return result;
}

[[nodiscard]] std::size_t arithmetic_dimension(
    std::size_t packets, std::size_t relations) noexcept {
    return std::max({std::size_t{6}, 3U * packets, relations});
}

[[nodiscard]] double registered_tolerance(
    std::size_t packets, std::size_t relations, double factor,
    double scale) noexcept {
    return factor * static_cast<double>(arithmetic_dimension(packets, relations)) *
        std::numeric_limits<double>::epsilon() *
        std::max(scale, std::numeric_limits<double>::min());
}

[[nodiscard]] bool converges_until_binary64_floor(
    std::span<const double> errors, double floor) {
    if (errors.empty()) {
        return false;
    }
    auto at_floor = errors.front() <= floor;
    for (std::size_t index = 1U; index < errors.size(); ++index) {
        if (at_floor) {
            // Reaching the arithmetic floor does not license a later blow-up.
            if (errors[index] > floor) {
                return false;
            }
            continue;
        }
        if (errors[index] <= floor) {
            at_floor = true;
            continue;
        }
        if (errors[index] >= errors[index - 1U]) {
            return false;
        }
    }
    return true;
}

[[nodiscard]] std::string axis_name(std::size_t axis) {
    return std::array<std::string, 3>{"x", "y", "z"}.at(axis);
}

void emit_inputs(
    const std::vector<GraphConfiguration>& graphs,
    std::vector<OperatorCase>& operators, Tables& tables) {
    const std::array ratios{1.0 / 3.0, 2.0, 10.0};
    for (const auto& graph : graphs) {
        tables.configurations.row(
            {graph.id, graph.id, graph.role,
             std::to_string(graph.packets.size()),
             std::to_string(graph.relations.size())});
        for (std::size_t index = 0; index < graph.packets.size(); ++index) {
            const auto& packet = graph.packets[index];
            tables.reference_packets.row(
                {graph.id, std::to_string(index), std::to_string(packet.id),
                 std::to_string(packet.id), std::to_string(packet.mass_quanta),
                 hex64(packet.position_m.x), hex64(packet.position_m.y),
                 hex64(packet.position_m.z)});
        }
        const auto rigidity = observation::build_bond_rigidity_operator(
            graph.packets, graph.relations);
        for (std::size_t index = 0; index < graph.relations.size(); ++index) {
            const auto relation = graph.relations[index];
            tables.relations.row(
                {graph.id, std::to_string(index),
                 std::to_string(relation.first_id),
                 std::to_string(relation.second_id),
                 std::to_string(relation.first_id),
                 std::to_string(relation.second_id),
                 hex64(rigidity.lengths_m[index]), hex64(1.0)});
        }
        for (const auto ratio : ratios) {
            operators.push_back(build_operator(graph, ratio));
            const auto& entry = operators.back();
            tables.operators.row(
                {entry.id, graph.id, "local_incident_collective",
                 std::string(ratio_label(entry.target_ratio)), hex64(entry.a),
                 hex64(entry.b)});
            const auto count = entry.frozen.force_operator.relations.size();
            for (std::size_t row = 0; row < count; ++row) {
                for (std::size_t column = 0; column < count; ++column) {
                    const auto parent =
                        entry.frozen.parent_operator.h_j_per_m2(row, column);
                    const auto frozen =
                        entry.frozen.force_operator.h_j_per_m2(row, column);
                    tables.h_matrix.row(
                        {entry.id, std::to_string(row), std::to_string(column),
                         hex64(parent), hex64(frozen), hex64(frozen - parent)});
                }
            }
        }
    }
}

[[nodiscard]] EvaluationRecord emit_evaluation(
    Tables& tables, Counts& counts, const OperatorCase& operator_case,
    std::string id, std::string probe, std::string velocity_probe,
    std::vector<MechanicalPacket> current,
    std::map<std::uint64_t, std::uint64_t> semantic_by_actual,
    bool expected_coincident = false) {
    if (semantic_by_actual.size() != current.size()) {
        throw std::invalid_argument("semantic packet map is incomplete");
    }
    auto evaluated = force::evaluate_spatial_force(
        operator_case.frozen, current);
    // Evidence preserves the submitted packet order. The read-only evaluator
    // canonicalizes internally, but sorting here would erase the registered
    // packet-order metamorphic intervention.
    for (std::size_t index = 0; index < current.size(); ++index) {
        const auto& packet = current[index];
        tables.current_packets.row(
            {id, std::to_string(index), std::to_string(packet.id),
             std::to_string(semantic_by_actual.at(packet.id)),
             hex64(packet.position_m.x), hex64(packet.position_m.y),
             hex64(packet.position_m.z), hex64(packet.velocity_m_per_s.x),
             hex64(packet.velocity_m_per_s.y),
             hex64(packet.velocity_m_per_s.z)});
    }
    ++counts.force_evaluations;
    if (evaluated.status == force::ForceDomainStatus::coincident_relation) {
        ++counts.coincident_failures;
        const auto clean_failure = std::isnan(evaluated.energy_j) &&
            evaluated.relation_coordinates.empty() &&
            evaluated.packet_forces.empty() &&
            evaluated.current_rigidity.matrix.row_count() == 0U;
        const auto pass = expected_coincident && clean_failure;
        counts.exact_coincidence_failed_closed =
            counts.exact_coincidence_failed_closed && pass;
        if (!pass) {
            ++counts.raw_registered_failures;
        }
        tables.force_evaluations.row(
            {id, operator_case.id, probe, velocity_probe,
             std::string(evidence_status(evaluated.status)),
             "not_emitted", "not_emitted", "not_emitted", "not_emitted",
             "not_emitted", "not_emitted", "not_emitted", "not_emitted",
             "not_emitted", "not_emitted", "not_emitted", "not_emitted",
             "not_emitted", "not_emitted", "not_emitted", "not_emitted",
             "not_emitted", "not_emitted", "not_emitted", bool_text(pass)});
        return {std::move(id), std::move(probe), std::move(velocity_probe),
                &operator_case, std::move(current),
                std::move(semantic_by_actual), std::move(evaluated)};
    }
    ++counts.valid_evaluations;
    if (expected_coincident) {
        counts.exact_coincidence_failed_closed = false;
    }
    const auto second_origin =
        Vec3d{7.0 / 13.0, -5.0 / 11.0, 3.0 / 17.0};
    const auto identities = force::evaluate_continuous_identities(
        evaluated, current, second_origin);
    double force_scale = 0.0;
    double torque_origin_scale = 0.0;
    double torque_shifted_scale = 0.0;
    double relation_endpoint_power_scale = 0.0;
    double relation_rate_power_scale = 0.0;
    std::map<std::uint64_t, const MechanicalPacket*> packet_lookup;
    for (const auto& packet : current) {
        packet_lookup.emplace(packet.id, &packet);
    }
    for (const auto& packet_force : evaluated.packet_forces) {
        force_scale += std::abs(packet_force.force_n.x) +
            std::abs(packet_force.force_n.y) +
            std::abs(packet_force.force_n.z);
        const auto& packet = *packet_lookup.at(packet_force.packet_id);
        const auto torque = mls::experimental::cross(
            packet.position_m, packet_force.force_n);
        torque_origin_scale +=
            std::abs(torque.x) + std::abs(torque.y) + std::abs(torque.z);
        const auto shifted_torque = mls::experimental::cross(
            packet.position_m - second_origin, packet_force.force_n);
        torque_shifted_scale += std::abs(shifted_torque.x) +
            std::abs(shifted_torque.y) + std::abs(shifted_torque.z);
    }
    for (const auto& relation : evaluated.relation_coordinates) {
        const auto& first = *packet_lookup.at(relation.relation.first_id);
        const auto& second = *packet_lookup.at(relation.relation.second_id);
        const auto tail_force = relation.conjugate_force_n *
            relation.direction_first_to_second;
        relation_endpoint_power_scale +=
            std::abs(mls::experimental::dot(
                tail_force, first.velocity_m_per_s)) +
            std::abs(mls::experimental::dot(
                -1.0 * tail_force, second.velocity_m_per_s));
        const auto extension_rate = mls::experimental::dot(
            relation.direction_first_to_second,
            second.velocity_m_per_s - first.velocity_m_per_s);
        relation_rate_power_scale +=
            std::abs(relation.conjugate_force_n * extension_rate);
    }
    const auto torque_scale =
        std::max(torque_origin_scale, torque_shifted_scale);
    // The power identity compares two differently associated evaluations.
    // Bound its arithmetic using the elementary endpoint relation-work terms
    // that feed packet-force assembly as well as the relation-rate terms.
    // Using only already-assembled packet powers would erase the cancellation
    // scale responsible for their own rounding error.
    const auto power_scale =
        relation_endpoint_power_scale + relation_rate_power_scale;
    const auto tolerance_force = registered_tolerance(
        current.size(), evaluated.relation_coordinates.size(), 65536.0,
        force_scale);
    const auto tolerance_torque = registered_tolerance(
        current.size(), evaluated.relation_coordinates.size(), 65536.0,
        torque_scale);
    const auto tolerance_power = registered_tolerance(
        current.size(), evaluated.relation_coordinates.size(), 65536.0,
        power_scale);
    const auto pass = !expected_coincident &&
        vector_norm(identities.total_internal_force_n) <= tolerance_force &&
        vector_norm(identities.torque_about_origin_n_m) <= tolerance_torque &&
        vector_norm(identities.torque_about_second_origin_n_m) <=
            tolerance_torque &&
        std::abs(identities.power_identity_residual_w) <= tolerance_power;
    if (!pass) {
        ++counts.raw_registered_failures;
    }
    tables.force_evaluations.row(
        {id, operator_case.id, probe, velocity_probe,
         std::string(evidence_status(evaluated.status)),
         hex64(evaluated.energy_j), hex64(identities.relation_energy_rate_w),
         hex64(-identities.force_power_w),
         hex64(identities.power_identity_residual_w),
         hex64(identities.total_internal_force_n.x),
         hex64(identities.total_internal_force_n.y),
         hex64(identities.total_internal_force_n.z),
         hex64(identities.torque_about_origin_n_m.x),
         hex64(identities.torque_about_origin_n_m.y),
         hex64(identities.torque_about_origin_n_m.z),
         hex64(identities.torque_about_second_origin_n_m.x),
         hex64(identities.torque_about_second_origin_n_m.y),
         hex64(identities.torque_about_second_origin_n_m.z),
         hex64(force_scale), hex64(torque_scale), hex64(power_scale),
         hex64(tolerance_force), hex64(tolerance_torque),
         hex64(tolerance_power), bool_text(pass)});
    for (const auto& relation : evaluated.relation_coordinates) {
        tables.relation_forces.row(
            {id, std::to_string(relation.relation_index),
             std::to_string(relation.relation.first_id),
             std::to_string(relation.relation.second_id),
             hex64(relation.reference_length_m),
             hex64(relation.current_length_m), hex64(relation.extension_m),
             hex64(relation.conjugate_force_n),
             hex64(relation.direction_first_to_second.x),
             hex64(relation.direction_first_to_second.y),
             hex64(relation.direction_first_to_second.z)});
    }
    for (std::size_t index = 0; index < evaluated.packet_forces.size(); ++index) {
        const auto& packet = evaluated.packet_forces[index];
        tables.packet_forces.row(
            {id, std::to_string(index), std::to_string(packet.packet_id),
             std::to_string(semantic_by_actual.at(packet.packet_id)),
             hex64(packet.force_n.x), hex64(packet.force_n.y),
             hex64(packet.force_n.z)});
    }
    return {std::move(id), std::move(probe), std::move(velocity_probe),
            &operator_case, std::move(current),
            std::move(semantic_by_actual), std::move(evaluated)};
}

struct NamedVelocity final {
    std::string name{};
    std::vector<Vec3d> values{};
};

[[nodiscard]] std::vector<NamedVelocity> registered_velocity_probes(
    std::span<const MechanicalPacket> packets, std::uint64_t stream) {
    std::vector<NamedVelocity> result;
    const std::array axes{Vec3d{1.0, 0.0, 0.0}, Vec3d{0.0, 1.0, 0.0},
                          Vec3d{0.0, 0.0, 1.0}};
    for (std::size_t axis = 0; axis < axes.size(); ++axis) {
        result.push_back(
            {"translation_" + axis_name(axis),
             normalized_rigid_velocity(packets, axes[axis], {})});
    }
    for (std::size_t axis = 0; axis < axes.size(); ++axis) {
        result.push_back(
            {"rotation_" + axis_name(axis),
             normalized_rigid_velocity(packets, {}, axes[axis])});
    }
    result.push_back({"affine", affine_velocity(packets)});
    result.push_back(
        {"random_0", normalized_random_vectors(packets.size(), stream)});
    result.push_back(
        {"random_1", normalized_random_vectors(
                         packets.size(), stream ^ UINT64_C(0x51a7d3))});
    return result;
}

[[nodiscard]] std::map<std::string, EvaluationRecord> emit_base_evaluations(
    Tables& tables, Counts& counts, std::span<const OperatorCase> operators,
    bool smoke) {
    std::map<std::string, EvaluationRecord> records;
    for (std::size_t operator_index = 0; operator_index < operators.size();
         ++operator_index) {
        const auto& operator_case = operators[operator_index];
        const auto semantics = identity_semantics(operator_case.graph->packets);
        const std::vector<Vec3d> zero(operator_case.graph->packets.size());
        const auto reference_id = operator_case.id + ".reference.zero";
        records.emplace(
            reference_id,
            emit_evaluation(
                tables, counts, operator_case, reference_id, "reference",
                "zero", with_velocities(operator_case.graph->packets, zero),
                semantics));
        const std::array probes{
            std::pair{std::string_view{"F_general"}, general_deformation()},
            std::pair{std::string_view{"F_shear"}, shear_deformation()},
            std::pair{std::string_view{"F_compress"}, compression_deformation()},
        };
        for (std::size_t probe_index = 0; probe_index < probes.size();
             ++probe_index) {
            const auto deformed = deform_about_centroid(
                operator_case.graph->packets, probes[probe_index].second);
            auto velocities = registered_velocity_probes(
                deformed, static_cast<std::uint64_t>(operator_index * 17U +
                    probe_index));
            if (smoke) {
                velocities.resize(1U);
            }
            for (const auto& velocity : velocities) {
                const auto id = operator_case.id + "." +
                    std::string(probes[probe_index].first) + "." + velocity.name;
                records.emplace(
                    id,
                    emit_evaluation(
                        tables, counts, operator_case, id,
                        std::string(probes[probe_index].first), velocity.name,
                        with_velocities(deformed, velocity.values), semantics));
            }
        }
    }
    return records;
}

[[nodiscard]] std::vector<Vec3d> normalized_affine_direction(
    std::span<const MechanicalPacket> packets, const Matrix3d& map) {
    const auto center = centroid(packets);
    std::vector<Vec3d> result;
    result.reserve(packets.size());
    double squared = 0.0;
    for (const auto& packet : packets) {
        const auto value =
            mls::experimental::multiply(map, packet.position_m - center);
        result.push_back(value);
        squared += value.x * value.x + value.y * value.y + value.z * value.z;
    }
    const auto inverse = 1.0 / std::sqrt(squared);
    for (auto& value : result) {
        value = inverse * value;
    }
    return result;
}

[[nodiscard]] std::vector<MechanicalPacket> displaced(
    std::span<const MechanicalPacket> reference,
    std::span<const Vec3d> direction, double epsilon_m) {
    auto result = with_velocities(reference, direction);
    for (std::size_t index = 0; index < result.size(); ++index) {
        result[index].position_m += epsilon_m * direction[index];
    }
    return result;
}

[[nodiscard]] std::vector<double> flatten_forces(
    const force::SpatialForceEvaluation& evaluated) {
    std::vector<double> result;
    result.reserve(3U * evaluated.packet_forces.size());
    for (const auto& packet : evaluated.packet_forces) {
        result.push_back(packet.force_n.x);
        result.push_back(packet.force_n.y);
        result.push_back(packet.force_n.z);
    }
    return result;
}

[[nodiscard]] std::vector<double> flatten_vectors(
    std::span<const Vec3d> values) {
    std::vector<double> result;
    result.reserve(3U * values.size());
    for (const auto value : values) {
        result.push_back(value.x);
        result.push_back(value.y);
        result.push_back(value.z);
    }
    return result;
}

[[nodiscard]] std::vector<double> matrix_times(
    const DenseMatrix& matrix, std::span<const double> vector) {
    std::vector<double> result(matrix.row_count(), 0.0);
    for (std::size_t row = 0; row < matrix.row_count(); ++row) {
        double value = 0.0;
        for (std::size_t column = 0; column < matrix.column_count(); ++column) {
            value += matrix(row, column) * vector[column];
        }
        result[row] = value;
    }
    return result;
}

[[nodiscard]] double maximum_difference(
    std::span<const double> lhs, std::span<const double> rhs) {
    double result = 0.0;
    for (std::size_t index = 0; index < lhs.size(); ++index) {
        result = std::max(result, std::abs(lhs[index] - rhs[index]));
    }
    return result;
}

void emit_reference_tangent(
    Tables& tables, Counts& counts, std::span<const OperatorCase> operators,
    bool smoke) {
    const std::array exponents{-6, -9, -12, -15, -18, -21};
    for (std::size_t operator_index = 0; operator_index < operators.size();
         ++operator_index) {
        const auto& operator_case = operators[operator_index];
        const auto& reference = operator_case.graph->packets;
        std::vector<NamedVelocity> directions{
            {"random_0", normalized_random_vectors(reference.size(),
                                                     operator_index * 31U)},
            {"random_1", normalized_random_vectors(reference.size(),
                                                     operator_index * 31U + 1U)},
            {"random_2", normalized_random_vectors(reference.size(),
                                                     operator_index * 31U + 2U)},
        };
        directions.push_back(
            {"isotropic", normalized_affine_direction(
                              reference, Matrix3d::identity())});
        Matrix3d shear{};
        shear.value[0][1] = 0.5;
        shear.value[1][0] = 0.5;
        directions.push_back(
            {"pure_shear", normalized_affine_direction(reference, shear)});
        directions.push_back(
            {"general_affine", normalized_affine_direction(
                                   reference, general_deformation())});
        if (smoke) {
            directions.resize(1U);
        }
        const auto reference_tangent = force::evaluate_spatial_tangent(
            operator_case.frozen, reference);
        for (const auto& direction : directions) {
            const auto target = matrix_times(
                reference_tangent.force_jacobian_n_per_m,
                flatten_vectors(direction.values));
            double target_scale = 0.0;
            for (const auto value : target) {
                target_scale = std::max(target_scale, std::abs(value));
            }
            const auto length = characteristic_length(operator_case.frozen);
            std::vector<double> errors;
            std::vector<double> orders(exponents.size(), 0.0);
            std::vector<std::string> evaluation_ids;
            for (std::size_t epsilon_index = 0;
                 epsilon_index < exponents.size(); ++epsilon_index) {
                const auto ratio = std::ldexp(1.0, exponents[epsilon_index]);
                const auto epsilon = ratio * length;
                const auto id = operator_case.id + ".reference_tangent." +
                    direction.name + "." + std::to_string(epsilon_index);
                const auto record = emit_evaluation(
                    tables, counts, operator_case, id, "reference_tangent",
                    direction.name,
                    displaced(reference, direction.values, epsilon),
                    identity_semantics(reference));
                auto actual = flatten_forces(record.force);
                for (auto& value : actual) {
                    value /= epsilon;
                }
                errors.push_back(
                    maximum_difference(actual, target) /
                    std::max(target_scale,
                             operator_case.frozen.maximum_parent_h_magnitude_j_per_m2));
                evaluation_ids.push_back(id);
                if (epsilon_index != 0U && errors[epsilon_index] > 0.0 &&
                    errors[epsilon_index - 1U] > 0.0) {
                    orders[epsilon_index] = std::log(
                        errors[epsilon_index - 1U] / errors[epsilon_index]) /
                        std::log(8.0);
                }
            }
            std::vector<double> finite_orders;
            for (std::size_t index = 1U; index < 4U; ++index) {
                finite_orders.push_back(orders[index]);
            }
            std::ranges::sort(finite_orders);
            const auto median = finite_orders[finite_orders.size() / 2U];
            const auto decreases = errors[1] < errors[0] &&
                errors[2] < errors[1] && errors[3] < errors[2];
            const auto minimum = *std::ranges::min_element(errors);
            const auto floor = registered_tolerance(
                reference.size(),
                operator_case.frozen.force_operator.relations.size(),
                262144.0, 1.0);
            const auto convergence =
                converges_until_binary64_floor(errors, floor);
            const auto initially_at_floor = errors.front() <= floor;
            const auto pass = convergence &&
                (initially_at_floor ||
                 (decreases && median >= 0.75 && median <= 1.25)) &&
                minimum <= 2.0e-5;
            if (!pass) {
                counts.raw_registered_failures += exponents.size();
            }
            for (std::size_t index = 0; index < exponents.size(); ++index) {
                tables.reference_tangent.row(
                    {operator_case.id, evaluation_ids[index], direction.name,
                     direction.name, std::to_string(index),
                     hex64(std::ldexp(1.0, exponents[index])),
                     hex64(std::ldexp(1.0, exponents[index]) * length),
                     hex64(errors[index]), hex64(orders[index]),
                     hex64(minimum), bool_text(decreases), hex64(median),
                     bool_text(pass)});
            }
        }
    }
}

void emit_finite_tangent(
    Tables& tables, Counts& counts, std::span<const OperatorCase> operators,
    bool smoke) {
    const std::array steps{1.0e-8, 1.0e-12, 1.0e-16, 1.0e-20};
    for (const auto& operator_case : operators) {
        const auto selected = operator_case.graph->id ==
                "exact.tetrahedron_k4" ||
            operator_case.graph->id == "exact.octahedron_graph" ||
            operator_case.graph->id == "base.jitter27.r180.original";
        if (!selected && !smoke) {
            continue;
        }
        const std::array probes{
            std::pair{std::string_view{"general"}, general_deformation()},
            std::pair{std::string_view{"compress"}, compression_deformation()},
        };
        for (const auto& probe : probes) {
            auto current = deform_about_centroid(
                operator_case.graph->packets, probe.second);
            const auto zero = std::vector<Vec3d>(current.size());
            current = with_velocities(current, zero);
            const auto id = operator_case.id + ".finite_tangent." +
                std::string(probe.first);
            static_cast<void>(emit_evaluation(
                tables, counts, operator_case, id, std::string(probe.first),
                "zero", current, identity_semantics(current)));
            const auto tangent = force::evaluate_spatial_tangent(
                operator_case.frozen, current);
            const auto dof_count = 3U * current.size();
            const auto length = characteristic_length(operator_case.frozen);
            const auto analytic_scale = std::max(
                {max_abs(tangent.material_energy_hessian_n_per_m),
                 max_abs(tangent.geometric_energy_hessian_n_per_m),
                 max_abs(tangent.total_energy_hessian_n_per_m)});
            const auto tolerance = registered_tolerance(
                current.size(),
                operator_case.frozen.force_operator.relations.size(),
                262144.0, analytic_scale);
            for (std::size_t step_index = 0; step_index < steps.size();
                 ++step_index) {
                const auto h = steps[step_index] * length;
                for (std::size_t column = 0; column < dof_count; ++column) {
                    std::vector<Vec3d> direction(current.size());
                    const auto packet = column / 3U;
                    const auto axis = column % 3U;
                    if (axis == 0U) {
                        direction[packet].x = 1.0;
                    } else if (axis == 1U) {
                        direction[packet].y = 1.0;
                    } else {
                        direction[packet].z = 1.0;
                    }
                    const auto plus = flatten_forces(
                        force::evaluate_spatial_force(
                            operator_case.frozen,
                            displaced(current, direction, h)));
                    const auto minus = flatten_forces(
                        force::evaluate_spatial_force(
                            operator_case.frozen,
                            displaced(current, direction, -h)));
                    for (std::size_t row = 0; row < dof_count; ++row) {
                        const auto raw = (plus[row] - minus[row]) / (2.0 * h);
                        const auto material =
                            tangent.material_energy_hessian_n_per_m(row, column);
                        const auto geometric =
                            tangent.geometric_energy_hessian_n_per_m(row, column);
                        const auto total =
                            tangent.total_energy_hessian_n_per_m(row, column);
                        const auto jacobian =
                            tangent.force_jacobian_n_per_m(row, column);
                        const auto decomposition =
                            std::abs(total - material - geometric);
                        const auto symmetry = std::abs(
                            total - tangent.total_energy_hessian_n_per_m(
                                        column, row));
                        const auto pass = decomposition <= tolerance &&
                            symmetry <= tolerance;
                        if (!pass) {
                            ++counts.raw_registered_failures;
                        }
                        tables.finite_tangent.row(
                            {id, std::to_string(row), std::to_string(column),
                             std::to_string(current[row / 3U].id),
                             std::to_string(row % 3U),
                             std::to_string(current[column / 3U].id),
                             std::to_string(column % 3U),
                             std::to_string(step_index), hex64(steps[step_index]),
                             hex64(material), hex64(geometric), hex64(total),
                             hex64(jacobian), hex64(raw),
                             hex64(raw - jacobian), hex64(decomposition),
                             hex64(symmetry), hex64(tolerance), bool_text(pass)});
                    }
                }
            }
        }
    }
}

[[nodiscard]] force::FrozenForceOperator scaled_reference_operator(
    const force::FrozenForceOperator& source, double scale) {
    if (!std::isfinite(scale) || scale <= 0.0) {
        throw std::invalid_argument(
            "reference similarity scale must be finite and positive");
    }
    auto result = source;
    const auto apply = [scale](constitutive::RelationEnergyOperator& model) {
        for (auto& length : model.reference_lengths_m) {
            length *= scale;
        }
        model.locality_radius_m *= scale;
        for (auto& local : model.local_contributions) {
            local.weighted_length_moment_m2 *= scale * scale;
            local.maximum_incident_length_m *= scale;
        }
    };
    apply(result.parent_operator);
    apply(result.force_operator);
    const auto verify = [scale](
                            const constitutive::RelationEnergyOperator& before,
                            const constitutive::RelationEnergyOperator& after) {
        if (before.h_j_per_m2 != after.h_j_per_m2 ||
            before.factor_sqrt_j_per_m != after.factor_sqrt_j_per_m ||
            before.relations != after.relations ||
            before.reference_lengths_m.size() !=
                after.reference_lengths_m.size() ||
            before.local_contributions.size() !=
                after.local_contributions.size() ||
            after.locality_radius_m != before.locality_radius_m * scale) {
            throw std::logic_error(
                "similarity transform changed or omitted frozen reference data");
        }
        for (std::size_t index = 0;
             index < before.reference_lengths_m.size(); ++index) {
            if (after.reference_lengths_m[index] !=
                before.reference_lengths_m[index] * scale) {
                throw std::logic_error(
                    "similarity transform omitted a reference length");
            }
        }
        for (std::size_t index = 0;
             index < before.local_contributions.size(); ++index) {
            const auto& old_local = before.local_contributions[index];
            const auto& new_local = after.local_contributions[index];
            if (new_local.packet_id != old_local.packet_id ||
                new_local.incident_relation_count !=
                    old_local.incident_relation_count ||
                new_local.weighted_length_moment_m2 !=
                    old_local.weighted_length_moment_m2 * (scale * scale) ||
                new_local.maximum_incident_length_m !=
                    old_local.maximum_incident_length_m * scale ||
                new_local.dilatational_h_j_per_m2 !=
                    old_local.dilatational_h_j_per_m2 ||
                new_local.deviatoric_h_j_per_m2 !=
                    old_local.deviatoric_h_j_per_m2 ||
                new_local.dilatational_factor_sqrt_j_per_m !=
                    old_local.dilatational_factor_sqrt_j_per_m ||
                new_local.deviatoric_factor_sqrt_j_per_m !=
                    old_local.deviatoric_factor_sqrt_j_per_m) {
                throw std::logic_error(
                    "similarity transform changed or omitted local reference metadata");
            }
        }
    };
    verify(source.parent_operator, result.parent_operator);
    verify(source.force_operator, result.force_operator);
    return result;
}

void rename_operator_packets(
    force::FrozenForceOperator& frozen,
    const std::map<std::uint64_t, std::uint64_t>& renamed) {
    const auto apply = [&](constitutive::RelationEnergyOperator& model) {
        for (auto& relation : model.relations) {
            relation.first_id = renamed.at(relation.first_id);
            relation.second_id = renamed.at(relation.second_id);
        }
        for (auto& local : model.local_contributions) {
            local.packet_id = renamed.at(local.packet_id);
        }
    };
    apply(frozen.parent_operator);
    apply(frozen.force_operator);
}

[[nodiscard]] std::string identity_coordinate_map(std::size_t count) {
    std::string result;
    for (std::size_t index = 0; index < count; ++index) {
        if (index != 0U) {
            result.push_back(';');
        }
        result += std::to_string(index) + ":" + std::to_string(index);
    }
    return result;
}

[[nodiscard]] std::string permutation_coordinate_map(
    std::span<const std::size_t> new_to_old) {
    std::vector<std::size_t> old_to_new(new_to_old.size());
    for (std::size_t new_index = 0; new_index < new_to_old.size(); ++new_index) {
        old_to_new[new_to_old[new_index]] = new_index;
    }
    std::string result;
    for (std::size_t old = 0; old < old_to_new.size(); ++old) {
        if (old != 0U) {
            result.push_back(';');
        }
        result += std::to_string(old) + ":" + std::to_string(old_to_new[old]);
    }
    return result;
}

[[nodiscard]] std::string transformed_h_sha256(
    const force::FrozenForceOperator& frozen) {
    const auto& h = frozen.force_operator.h_j_per_m2;
    if (h.row_count() != h.column_count()) {
        throw std::invalid_argument(
            "metamorphic frozen H digest requires a square matrix");
    }
    // Closed preimage v1: schema line, decimal dimension line, then every
    // canonical binary64 value in row-major order, one per LF-terminated line.
    std::string preimage{
        "mls.conservative-force-consistency.metamorphic-h.v1\n"};
    preimage += "dimension=" + std::to_string(h.row_count()) + "\n";
    for (std::size_t row = 0; row < h.row_count(); ++row) {
        for (std::size_t column = 0; column < h.column_count(); ++column) {
            preimage += hex64(h(row, column));
            preimage.push_back('\n');
        }
    }
    return sha256(preimage);
}

[[nodiscard]] std::vector<std::size_t> deterministic_permutation(
    std::size_t count, std::uint64_t stream) {
    std::vector<std::size_t> result(count);
    std::iota(result.begin(), result.end(), std::size_t{0});
    auto state = seed ^ stream;
    for (std::size_t remaining = count; remaining > 1U; --remaining) {
        const auto selected = static_cast<std::size_t>(
            splitmix64(state) % static_cast<std::uint64_t>(remaining));
        std::swap(result[remaining - 1U], result[selected]);
    }
    return result;
}

[[nodiscard]] double semantic_force_residual(
    const force::SpatialForceEvaluation& baseline,
    const force::SpatialForceEvaluation& probe,
    const std::map<std::uint64_t, std::uint64_t>& probe_semantics,
    const Matrix3d& rotation, double scale) {
    std::map<std::uint64_t, Vec3d> expected;
    for (const auto& packet : baseline.packet_forces) {
        expected.emplace(
            packet.packet_id,
            scale * mls::experimental::multiply(rotation, packet.force_n));
    }
    double result = 0.0;
    for (const auto& packet : probe.packet_forces) {
        const auto difference = packet.force_n -
            expected.at(probe_semantics.at(packet.packet_id));
        result = std::max(result, vector_norm(difference));
    }
    return result;
}

[[nodiscard]] double semantic_conjugate_residual(
    const force::SpatialForceEvaluation& baseline,
    const force::SpatialForceEvaluation& probe,
    const std::map<std::uint64_t, std::uint64_t>& probe_semantics,
    double scale) {
    std::map<std::pair<std::uint64_t, std::uint64_t>, double> expected;
    for (const auto& relation : baseline.relation_coordinates) {
        const auto key = std::minmax(
            relation.relation.first_id, relation.relation.second_id);
        expected.emplace(
            std::pair{key.first, key.second},
            scale * relation.conjugate_force_n);
    }
    double result = 0.0;
    for (const auto& relation : probe.relation_coordinates) {
        const auto first = probe_semantics.at(relation.relation.first_id);
        const auto second = probe_semantics.at(relation.relation.second_id);
        const auto key = std::minmax(first, second);
        result = std::max(
            result,
            std::abs(relation.conjugate_force_n -
                     expected.at({key.first, key.second})));
    }
    return result;
}

[[nodiscard]] double tangent_covariance_residual(
    const force::SpatialTangentEvaluation& baseline,
    const force::SpatialTangentEvaluation& probe,
    const std::map<std::uint64_t, std::uint64_t>& probe_semantics,
    const Matrix3d& rotation) {
    std::map<std::uint64_t, std::size_t> baseline_index;
    std::map<std::uint64_t, std::size_t> probe_index;
    for (std::size_t index = 0; index < baseline.packet_ids.size(); ++index) {
        baseline_index.emplace(baseline.packet_ids[index], index);
    }
    for (std::size_t index = 0; index < probe.packet_ids.size(); ++index) {
        probe_index.emplace(probe_semantics.at(probe.packet_ids[index]), index);
    }
    double result = 0.0;
    for (const auto& [row_id, baseline_row] : baseline_index) {
        for (const auto& [column_id, baseline_column] : baseline_index) {
            double baseline_block[3][3]{};
            for (std::size_t row = 0; row < 3U; ++row) {
                for (std::size_t column = 0; column < 3U; ++column) {
                    baseline_block[row][column] =
                        baseline.total_energy_hessian_n_per_m(
                            3U * baseline_row + row,
                            3U * baseline_column + column);
                }
            }
            for (std::size_t row = 0; row < 3U; ++row) {
                for (std::size_t column = 0; column < 3U; ++column) {
                    double expected = 0.0;
                    for (std::size_t inner_row = 0; inner_row < 3U;
                         ++inner_row) {
                        for (std::size_t inner_column = 0; inner_column < 3U;
                             ++inner_column) {
                            expected += rotation.value[row][inner_row] *
                                baseline_block[inner_row][inner_column] *
                                rotation.value[column][inner_column];
                        }
                    }
                    const auto actual = probe.total_energy_hessian_n_per_m(
                        3U * probe_index.at(row_id) + row,
                        3U * probe_index.at(column_id) + column);
                    result = std::max(
                        result,
                        std::abs(actual - expected));
                }
            }
        }
    }
    return result;
}

void emit_metamorphic(
    Tables& tables, Counts& counts, std::span<const OperatorCase> operators,
    bool smoke) {
    const auto rotation = axis_angle({1.0, 2.0, 3.0}, 0.731);
    const auto translation = Vec3d{7.0 / 13.0, -5.0 / 11.0, 3.0 / 17.0};
    for (std::size_t operator_index = 0; operator_index < operators.size();
         ++operator_index) {
        const auto& operator_case = operators[operator_index];
        auto baseline_current = deform_about_centroid(
            operator_case.graph->packets, general_deformation());
        baseline_current = with_velocities(
            baseline_current, affine_velocity(baseline_current));
        const auto baseline_id = operator_case.id + ".metamorphic.baseline";
        const auto baseline = emit_evaluation(
            tables, counts, operator_case, baseline_id, "F_general",
            "affine", baseline_current,
            identity_semantics(baseline_current));
        const auto baseline_tangent = force::evaluate_spatial_tangent(
            operator_case.frozen, baseline_current);

        struct Probe final {
            std::string name{};
            Matrix3d rotation{Matrix3d::identity()};
            Vec3d translation{};
            double scale{1.0};
            std::vector<std::size_t> packet_permutation{};
            std::vector<std::size_t> relation_permutation{};
            std::map<std::uint64_t, std::uint64_t> renaming{};
            bool reverse_endpoints{false};
        };
        std::vector<Probe> probes{
            {"current_translation", Matrix3d::identity(), translation},
            {"common_rotation", rotation},
            {"common_rotation_translation", rotation, translation},
            {"similarity_half", Matrix3d::identity(), {}, 0.5},
            {"similarity_two", Matrix3d::identity(), {}, 2.0},
        };
        const auto packet_count = baseline_current.size();
        const auto relation_count =
            operator_case.frozen.force_operator.relations.size();
        auto packet_reverse = std::vector<std::size_t>(packet_count);
        std::iota(packet_reverse.begin(), packet_reverse.end(), 0U);
        std::ranges::reverse(packet_reverse);
        probes.push_back(
            {"packet_reverse", Matrix3d::identity(), {}, 1.0,
             packet_reverse});
        probes.push_back(
            {"packet_splitmix", Matrix3d::identity(), {}, 1.0,
             deterministic_permutation(packet_count, operator_index + 901U)});
        auto relation_reverse = std::vector<std::size_t>(relation_count);
        std::iota(relation_reverse.begin(), relation_reverse.end(), 0U);
        std::ranges::reverse(relation_reverse);
        probes.push_back(
            {"relation_reverse", Matrix3d::identity(), {}, 1.0, {},
             relation_reverse});
        probes.push_back(
            {"relation_splitmix", Matrix3d::identity(), {}, 1.0, {},
             deterministic_permutation(
                 relation_count, operator_index + 1901U)});
        const auto ids = [&] {
            std::vector<std::uint64_t> value;
            for (const auto& packet : baseline_current) {
                value.push_back(packet.id);
            }
            return value;
        }();
        const auto add_renaming = [&](std::string name,
                                      std::vector<std::uint64_t> targets) {
            Probe probe{name};
            for (std::size_t index = 0; index < ids.size(); ++index) {
                probe.renaming.emplace(ids[index], targets[index]);
            }
            probes.push_back(std::move(probe));
        };
        auto reversed_ids = ids;
        std::ranges::reverse(reversed_ids);
        add_renaming("id_reverse", reversed_ids);
        auto cyclic_ids = ids;
        std::ranges::rotate(cyclic_ids, cyclic_ids.begin() + 1);
        add_renaming("id_cyclic", cyclic_ids);
        auto hashed_ids = ids;
        std::ranges::sort(hashed_ids, [&](auto lhs, auto rhs) {
            return sha256(std::to_string(lhs) + "." +
                          std::to_string(seed)) <
                sha256(std::to_string(rhs) + "." + std::to_string(seed));
        });
        add_renaming("id_sha256", hashed_ids);
        Probe endpoints{"endpoint_reverse"};
        endpoints.reverse_endpoints = true;
        probes.push_back(std::move(endpoints));
        if (smoke) {
            probes.resize(3U);
        }

        for (const auto& probe : probes) {
            OperatorCase transformed_case = operator_case;
            auto current = rigid_transform(
                baseline_current, probe.rotation, probe.translation,
                probe.scale);
            auto semantics = identity_semantics(current);
            auto packet_map = identity_coordinate_map(current.size());
            auto relation_map = identity_coordinate_map(relation_count);
            if (probe.scale != 1.0) {
                transformed_case.frozen = scaled_reference_operator(
                    transformed_case.frozen, probe.scale);
            }
            if (!probe.relation_permutation.empty()) {
                transformed_case.frozen = force::permute_relation_coordinates(
                    transformed_case.frozen, probe.relation_permutation);
                relation_map = permutation_coordinate_map(
                    probe.relation_permutation);
            }
            if (probe.reverse_endpoints) {
                for (auto& relation :
                     transformed_case.frozen.parent_operator.relations) {
                    std::swap(relation.first_id, relation.second_id);
                }
                for (auto& relation :
                     transformed_case.frozen.force_operator.relations) {
                    std::swap(relation.first_id, relation.second_id);
                }
            }
            if (!probe.packet_permutation.empty()) {
                std::vector<MechanicalPacket> permuted;
                permuted.reserve(current.size());
                for (const auto source : probe.packet_permutation) {
                    permuted.push_back(current[source]);
                }
                current = std::move(permuted);
                packet_map = permutation_coordinate_map(
                    probe.packet_permutation);
            }
            if (!probe.renaming.empty()) {
                rename_operator_packets(transformed_case.frozen, probe.renaming);
                semantics.clear();
                for (auto& packet : current) {
                    const auto semantic = packet.id;
                    packet.id = probe.renaming.at(packet.id);
                    semantics.emplace(packet.id, semantic);
                }
                std::vector<std::uint64_t> new_canonical_ids;
                for (const auto& packet : current) {
                    new_canonical_ids.push_back(packet.id);
                }
                std::ranges::sort(new_canonical_ids);
                packet_map.clear();
                for (std::size_t old_index = 0; old_index < ids.size();
                     ++old_index) {
                    if (old_index != 0U) {
                        packet_map.push_back(';');
                    }
                    const auto new_id = probe.renaming.at(ids[old_index]);
                    const auto new_index = static_cast<std::size_t>(
                        std::ranges::find(new_canonical_ids, new_id) -
                        new_canonical_ids.begin());
                    packet_map += std::to_string(old_index) + ":" +
                        std::to_string(new_index);
                }
            }
            const auto probe_id = operator_case.id + ".metamorphic." + probe.name;
            const auto evaluated = emit_evaluation(
                tables, counts, transformed_case, probe_id, probe.name,
                "affine_transformed", current, semantics);
            const auto probe_tangent = force::evaluate_spatial_tangent(
                transformed_case.frozen, evaluated.current);
            const auto expected_ratio = probe.scale * probe.scale;
            const auto actual_ratio =
                evaluated.force.energy_j / baseline.force.energy_j;
            const auto energy_residual = std::abs(
                evaluated.force.energy_j -
                expected_ratio * baseline.force.energy_j);
            const auto force_residual = semantic_force_residual(
                baseline.force, evaluated.force, semantics, probe.rotation,
                probe.scale);
            const auto tangent_residual = tangent_covariance_residual(
                baseline_tangent, probe_tangent, semantics, probe.rotation);
            const auto conjugate_residual = semantic_conjugate_residual(
                baseline.force, evaluated.force, semantics, probe.scale);
            double baseline_force_scale = 0.0;
            for (const auto& packet : baseline.force.packet_forces) {
                baseline_force_scale = std::max(
                    baseline_force_scale,
                    probe.scale * vector_norm(packet.force_n));
            }
            double probe_force_scale = 0.0;
            for (const auto& packet : evaluated.force.packet_forces) {
                probe_force_scale = std::max(
                    probe_force_scale, vector_norm(packet.force_n));
            }
            double baseline_conjugate_scale = 0.0;
            for (const auto& relation : baseline.force.relation_coordinates) {
                baseline_conjugate_scale = std::max(
                    baseline_conjugate_scale,
                    probe.scale * std::abs(relation.conjugate_force_n));
            }
            double probe_conjugate_scale = 0.0;
            for (const auto& relation : evaluated.force.relation_coordinates) {
                probe_conjugate_scale = std::max(
                    probe_conjugate_scale,
                    std::abs(relation.conjugate_force_n));
            }
            const auto energy_tolerance = registered_tolerance(
                current.size(), relation_count, 65536.0,
                std::max(std::abs(evaluated.force.energy_j),
                         expected_ratio * std::abs(baseline.force.energy_j)));
            const auto force_tolerance = registered_tolerance(
                current.size(), relation_count, 65536.0,
                std::max(baseline_force_scale, probe_force_scale));
            const auto tangent_tolerance = registered_tolerance(
                current.size(), relation_count, 262144.0,
                std::max(
                    max_abs(baseline_tangent.total_energy_hessian_n_per_m),
                    max_abs(probe_tangent.total_energy_hessian_n_per_m)));
            const auto conjugate_tolerance = registered_tolerance(
                current.size(), relation_count, 65536.0,
                std::max(baseline_conjugate_scale, probe_conjugate_scale));
            const auto scaling_ratio_tolerance = registered_tolerance(
                current.size(), relation_count, 131072.0, 1.0);
            const auto pass = energy_residual <= energy_tolerance &&
                force_residual <= force_tolerance &&
                tangent_residual <= tangent_tolerance &&
                conjugate_residual <= conjugate_tolerance &&
                std::abs(actual_ratio - expected_ratio) <=
                    scaling_ratio_tolerance;
            if (!pass) {
                ++counts.raw_registered_failures;
            }
            tables.metamorphic.row(
                {baseline_id, probe_id, probe.name, packet_map, relation_map,
                 transformed_h_sha256(transformed_case.frozen),
                 hex64(probe.scale), hex64(expected_ratio),
                 hex64(actual_ratio), hex64(energy_residual),
                 hex64(force_residual), hex64(tangent_residual),
                 hex64(conjugate_residual), hex64(energy_tolerance),
                 hex64(force_tolerance), hex64(tangent_tolerance),
                 hex64(conjugate_tolerance), hex64(scaling_ratio_tolerance),
                 bool_text(pass)});
        }
    }
}

void emit_direction_source_evaluations(
    Tables& tables, Counts& counts, std::span<const OperatorCase> operators,
    bool smoke) {
    const std::array axes{Vec3d{1.0, 0.0, 0.0}, Vec3d{0.0, 1.0, 0.0},
                          Vec3d{0.0, 0.0, 1.0}};
    for (std::size_t operator_index = 0; operator_index < operators.size();
         ++operator_index) {
        const auto& operator_case = operators[operator_index];
        const auto selected = operator_case.graph->id ==
                "exact.tetrahedron_k4" ||
            operator_case.graph->id == "exact.octahedron_graph" ||
            operator_case.graph->id == "base.jitter27.r180.original";
        if (!selected && !smoke) {
            continue;
        }
        auto current = deform_about_centroid(
            operator_case.graph->packets, general_deformation());
        std::vector<NamedVelocity> directions;
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            directions.push_back(
                {"direction.translation_" + axis_name(axis),
                 normalized_rigid_velocity(current, axes[axis], {})});
        }
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            directions.push_back(
                {"direction.rotation_" + axis_name(axis),
                 normalized_rigid_velocity(current, {}, axes[axis])});
        }
        for (std::size_t random_index = 0; random_index < 6U; ++random_index) {
            // The operator ID fixes operator_index in canonical emitted order;
            // the direction suffix fixes random_index. The independent stage
            // reconstructs this SplitMix64 stream instead of trusting the
            // exported velocity columns.
            directions.push_back(
                {"direction.random_" + std::to_string(random_index),
                 normalized_random_vectors(
                     current.size(), operator_index * 101U + random_index)});
        }
        if (smoke) {
            directions.resize(1U);
        }
        for (const auto& direction : directions) {
            const auto id = operator_case.id + "." + direction.name;
            static_cast<void>(emit_evaluation(
                tables, counts, operator_case, id, "general", direction.name,
                with_velocities(current, direction.values),
                identity_semantics(current)));
        }
    }
}

struct ConditionDiagnostic final {
    bool resolved{false};
    double value{0.0};
};

struct Binary64SpectrumDiagnostic final {
    bool converged{false};
    std::vector<double> singular_values{};
};

[[nodiscard]] Binary64SpectrumDiagnostic binary64_singular_values(
    const DenseMatrix& matrix) {
    const auto rows = matrix.row_count();
    const auto columns = matrix.column_count();
    const bool transpose_input = rows < columns;
    const auto working_rows = transpose_input ? columns : rows;
    const auto dimension = transpose_input ? rows : columns;
    if (dimension == 0U) {
        return {true, {}};
    }

    double maximum_entry = 0.0;
    for (const auto value : matrix.entries()) {
        if (!std::isfinite(value)) {
            throw std::invalid_argument(
                "binary64 singular-spectrum diagnostic requires finite entries");
        }
        maximum_entry = std::max(maximum_entry, std::abs(value));
    }
    if (maximum_entry == 0.0) {
        return {true, std::vector<double>(dimension, 0.0)};
    }

    // This lab-local direct one-sided Jacobi SVD intentionally uses only the
    // registered binary64 type.  It does not form A^T A, symmetrize the input,
    // or call the inherited Kelvin diagnostic, whose native long-double work
    // representation is outside this lab's frozen arithmetic contract.
    std::vector<double> work(working_rows * dimension, 0.0);
    for (std::size_t row = 0; row < working_rows; ++row) {
        for (std::size_t column = 0; column < dimension; ++column) {
            work[row * dimension + column] =
                (transpose_input ? matrix(column, row) : matrix(row, column)) /
                maximum_entry;
        }
    }

    constexpr std::size_t maximum_sweeps = 256U;
    constexpr double correlation_factor = 32.0;
    bool converged = dimension < 2U;
    for (std::size_t sweep = 0; sweep < maximum_sweeps; ++sweep) {
        bool rotated = false;
        for (std::size_t first = 0; first < dimension; ++first) {
            for (std::size_t second = first + 1U; second < dimension;
                 ++second) {
                double first_norm_squared = 0.0;
                double second_norm_squared = 0.0;
                double correlation = 0.0;
                for (std::size_t row = 0; row < working_rows; ++row) {
                    const auto first_value = work[row * dimension + first];
                    const auto second_value = work[row * dimension + second];
                    first_norm_squared += first_value * first_value;
                    second_norm_squared += second_value * second_value;
                    correlation += first_value * second_value;
                }
                if (first_norm_squared == 0.0 ||
                    second_norm_squared == 0.0) {
                    continue;
                }
                const auto correlation_threshold = correlation_factor *
                    std::numeric_limits<double>::epsilon() *
                    std::sqrt(first_norm_squared) *
                    std::sqrt(second_norm_squared);
                if (std::abs(correlation) <= correlation_threshold) {
                    continue;
                }
                const auto zeta =
                    (second_norm_squared - first_norm_squared) /
                    (2.0 * correlation);
                const auto tangent = zeta == 0.0
                    ? 1.0
                    : std::copysign(1.0, zeta) /
                          (std::abs(zeta) + std::hypot(1.0, zeta));
                const auto cosine = 1.0 / std::sqrt(1.0 + tangent * tangent);
                const auto sine = cosine * tangent;
                for (std::size_t row = 0; row < working_rows; ++row) {
                    const auto first_index = row * dimension + first;
                    const auto second_index = row * dimension + second;
                    const auto first_value = work[first_index];
                    const auto second_value = work[second_index];
                    work[first_index] =
                        cosine * first_value - sine * second_value;
                    work[second_index] =
                        sine * first_value + cosine * second_value;
                }
                rotated = true;
            }
        }
        if (!rotated) {
            converged = true;
            break;
        }
    }
    if (!converged) {
        return {};
    }

    std::vector<double> singular_values;
    singular_values.reserve(dimension);
    for (std::size_t column = 0; column < dimension; ++column) {
        double squared_norm = 0.0;
        for (std::size_t row = 0; row < working_rows; ++row) {
            const auto value = work[row * dimension + column];
            squared_norm += value * value;
        }
        singular_values.push_back(
            maximum_entry * std::sqrt(squared_norm));
    }
    std::ranges::sort(singular_values, std::greater<>{});
    return {true, std::move(singular_values)};
}

[[nodiscard]] ConditionDiagnostic resolved_nonzero_condition(
    const DenseMatrix& matrix) {
    const auto spectrum = binary64_singular_values(matrix);
    if (!spectrum.converged || spectrum.singular_values.empty() ||
        !(spectrum.singular_values.front() > 0.0)) {
        return {};
    }
    const auto dimension = std::max(
        {std::size_t{6}, matrix.row_count(), matrix.column_count()});
    const auto threshold = 512.0 * static_cast<double>(dimension) *
        std::numeric_limits<double>::epsilon() *
        spectrum.singular_values.front();
    double smallest_nonzero = 0.0;
    for (const auto value : spectrum.singular_values) {
        if (value > 8.0 * threshold) {
            smallest_nonzero = value;
        } else if (value >= threshold / 8.0) {
            return {};
        }
    }
    return smallest_nonzero > 0.0
        ? ConditionDiagnostic{
              true, spectrum.singular_values.front() / smallest_nonzero}
        : ConditionDiagnostic{};
}

void audit_binary64_condition_diagnostic() {
    DenseMatrix diagonal(6U, 6U);
    diagonal(0U, 0U) = 1.0;
    diagonal(1U, 1U) = -0.25;
    const auto ordinary = resolved_nonzero_condition(diagonal);
    if (!ordinary.resolved || ordinary.value != 4.0) {
        throw std::runtime_error(
            "binary64 condition diagnostic signed-spectrum self-test failed");
    }

    const auto threshold = 512.0 * 6.0 *
        std::numeric_limits<double>::epsilon();
    DenseMatrix ambiguous(6U, 6U);
    ambiguous(0U, 0U) = 1.0;
    ambiguous(1U, 1U) = threshold;
    if (resolved_nonzero_condition(ambiguous).resolved) {
        throw std::runtime_error(
            "binary64 condition diagnostic ambiguity-band self-test failed");
    }

    DenseMatrix below_band(6U, 6U);
    below_band(0U, 0U) = 1.0;
    below_band(1U, 1U) = threshold / 16.0;
    const auto below = resolved_nonzero_condition(below_band);
    if (!below.resolved || below.value != 1.0) {
        throw std::runtime_error(
            "binary64 condition diagnostic null-tail self-test failed");
    }

    DenseMatrix above_band(6U, 6U);
    above_band(0U, 0U) = 1.0;
    above_band(1U, 1U) = 16.0 * threshold;
    const auto above = resolved_nonzero_condition(above_band);
    const auto expected_above = 1.0 / (16.0 * threshold);
    if (!above.resolved || above.value != expected_above) {
        throw std::runtime_error(
            "binary64 condition diagnostic resolved-tail self-test failed");
    }

    DenseMatrix coupled(3U, 3U);
    coupled(0U, 0U) = 2.0;
    coupled(0U, 1U) = 0.25;
    coupled(1U, 0U) = 0.25;
    coupled(1U, 1U) = 1.0;
    coupled(2U, 2U) = 0.5;
    const auto first = resolved_nonzero_condition(coupled);
    const auto second = resolved_nonzero_condition(coupled);
    if (!first.resolved || !second.resolved ||
        std::bit_cast<std::uint64_t>(first.value) !=
            std::bit_cast<std::uint64_t>(second.value)) {
        throw std::runtime_error(
            "binary64 condition diagnostic repeatability self-test failed");
    }
}

void emit_compression(
    Tables& tables, Counts& counts, std::span<const OperatorCase> operators,
    bool smoke) {
    const std::array exponents{0, -4, -8, -12, -16, -20, -24,
                               -28, -32, -36, -40, -44, -48};
    for (const auto& operator_case : operators) {
        const auto selected =
            operator_case.graph->id == "exact.tetrahedron_k4" ||
            operator_case.graph->id == "exact.octahedron_graph";
        if (!selected) {
            continue;
        }
        const auto relation =
            operator_case.frozen.force_operator.relations.front();
        std::map<std::uint64_t, std::size_t> lookup;
        for (std::size_t index = 0; index < operator_case.graph->packets.size();
             ++index) {
            lookup.emplace(operator_case.graph->packets[index].id, index);
        }
        const auto first = lookup.at(relation.first_id);
        const auto second = lookup.at(relation.second_id);
        const auto offset =
            operator_case.graph->packets[second].position_m -
            operator_case.graph->packets[first].position_m;
        const auto offset_scale = std::max(
            {std::abs(offset.x), std::abs(offset.y), std::abs(offset.z)});
        const Vec3d scaled_offset{
            offset.x / offset_scale, offset.y / offset_scale,
            offset.z / offset_scale};
        const auto length = offset_scale * std::sqrt(
            scaled_offset.x * scaled_offset.x +
            scaled_offset.y * scaled_offset.y +
            scaled_offset.z * scaled_offset.z);
        const Vec3d direction{
            offset.x / length, offset.y / length, offset.z / length};
        const auto limit = smoke ? std::size_t{3} : exponents.size();
        for (std::size_t ratio_index = 0; ratio_index < limit; ++ratio_index) {
            const auto ratio = std::ldexp(1.0, exponents[ratio_index]);
            auto current = operator_case.graph->packets;
            current[second].position_m = current[first].position_m +
                ratio * offset;
            const auto zero = std::vector<Vec3d>(current.size());
            current = with_velocities(current, zero);
            const auto id = operator_case.id + ".compression." +
                std::to_string(ratio_index);
            const auto evaluated = emit_evaluation(
                tables, counts, operator_case, id, "compression", "zero",
                current, identity_semantics(current));
            const auto tangent = force::evaluate_spatial_tangent(
                operator_case.frozen, current);
            const auto force_norm =
                packet_force_l2_norm(evaluated.force.packet_forces);
            const auto material_norm =
                frobenius_norm(tangent.material_energy_hessian_n_per_m);
            const auto geometric_norm =
                frobenius_norm(tangent.geometric_energy_hessian_n_per_m);
            const auto total_norm =
                frobenius_norm(tangent.total_energy_hessian_n_per_m);
            const auto condition = resolved_nonzero_condition(
                tangent.total_energy_hessian_n_per_m);

            const auto h = std::min(length * 1.0e-8, ratio * length * 0.25);
            auto plus = current;
            auto minus = current;
            plus[second].position_m += h * direction;
            minus[second].position_m += -h * direction;
            const auto plus_energy = force::evaluate_spatial_force(
                operator_case.frozen, plus).energy_j;
            const auto minus_energy = force::evaluate_spatial_force(
                operator_case.frozen, minus).energy_j;
            const auto numeric = (plus_energy - minus_energy) / (2.0 * h);
            const auto packet_force = evaluated.force.packet_forces[second].force_n;
            const auto analytic = -mls::experimental::dot(packet_force, direction);
            const auto gradient_error = std::abs(numeric - analytic);

            auto adjacent = current;
            const std::array components{direction.x, direction.y, direction.z};
            const auto axis = static_cast<std::size_t>(
                std::ranges::max_element(
                    components, {}, [](double value) { return std::abs(value); }) -
                components.begin());
            auto* coordinate = axis == 0U ? &adjacent[second].position_m.x
                : axis == 1U           ? &adjacent[second].position_m.y
                                        : &adjacent[second].position_m.z;
            *coordinate = std::nextafter(
                *coordinate,
                components[axis] >= 0.0
                    ? std::numeric_limits<double>::infinity()
                    : -std::numeric_limits<double>::infinity());
            const auto adjacent_force = force::evaluate_spatial_force(
                operator_case.frozen, adjacent);
            double sensitivity_squared = 0.0;
            for (std::size_t packet = 0;
                 packet < evaluated.force.packet_forces.size(); ++packet) {
                const auto difference =
                    adjacent_force.packet_forces[packet].force_n -
                    evaluated.force.packet_forces[packet].force_n;
                sensitivity_squared += difference.x * difference.x;
                sensitivity_squared += difference.y * difference.y;
                sensitivity_squared += difference.z * difference.z;
            }
            const auto sensitivity = std::sqrt(sensitivity_squared);
            const auto adjacent_resolved =
                adjacent_force.relation_coordinates.front().current_length_m !=
                evaluated.force.relation_coordinates.front().current_length_m;
            const auto registered = exponents[ratio_index] >= -32;
            const auto pass = evaluated.force.status ==
                    force::ForceDomainStatus::evaluated &&
                std::isfinite(force_norm) && std::isfinite(total_norm) &&
                (!registered || adjacent_resolved);
            if (!pass) {
                ++counts.raw_registered_failures;
            }
            tables.compression.row(
                {operator_case.id, id, "0", hex64(ratio),
                 bool_text(registered),
                 std::string(evidence_status(evaluated.force.status)),
                 hex64(ratio * length), hex64(force_norm),
                 hex64(material_norm), hex64(geometric_norm),
                 hex64(total_norm),
                 condition.resolved ? hex64(condition.value) : "unresolved",
                 hex64(gradient_error),
                 hex64(sensitivity), bool_text(adjacent_resolved),
                 bool_text(pass)});
        }
        auto coincident = operator_case.graph->packets;
        coincident[second].position_m = coincident[first].position_m;
        const auto zero = std::vector<Vec3d>(coincident.size());
        coincident = with_velocities(coincident, zero);
        const auto id = operator_case.id + ".compression.coincident";
        const auto failure = emit_evaluation(
            tables, counts, operator_case, id, "compression_coincident", "zero",
            coincident, identity_semantics(coincident), true);
        const auto clean = failure.force.status ==
                force::ForceDomainStatus::coincident_relation &&
            failure.force.packet_forces.empty() &&
            failure.force.relation_coordinates.empty();
        if (!clean) {
            ++counts.raw_registered_failures;
        }
        tables.compression.row(
            {operator_case.id, id, "0", hex64(0.0), "false",
             std::string(evidence_status(failure.force.status)), "not_emitted",
             "not_emitted", "not_emitted", "not_emitted", "not_emitted",
             "not_emitted", "not_emitted", "not_emitted", "false",
             bool_text(clean)});
    }
}

void emit_floppy_mechanism(
    Tables& tables, Counts& counts, std::span<const OperatorCase> operators,
    bool smoke) {
    if (smoke) {
        return;
    }
    const std::array exponents{-8, -12, -16, -20};
    for (const auto& operator_case : operators) {
        if (!operator_case.graph->intentionally_floppy) {
            continue;
        }
        const auto rigidity = observation::build_bond_rigidity_operator(
            operator_case.graph->packets, operator_case.graph->relations);
        const auto diagnostic = observation::diagnose_mechanical_observability(
            rigidity.linearized, operator_case.graph->packets);
        if (diagnostic.nonrigid_nullity != 1U) {
            throw std::runtime_error("registered floppy mechanism unavailable");
        }
        std::vector<Vec3d> direction(operator_case.graph->packets.size());
        for (std::size_t packet = 0; packet < direction.size(); ++packet) {
            direction[packet] = {
                diagnostic.nonrigid_nullspace_basis(3U * packet, 0U),
                diagnostic.nonrigid_nullspace_basis(3U * packet + 1U, 0U),
                diagnostic.nonrigid_nullspace_basis(3U * packet + 2U, 0U)};
        }
        const auto length = characteristic_length(operator_case.frozen);
        std::vector<double> errors;
        std::vector<double> orders(exponents.size(), 0.0);
        std::vector<std::string> ids;
        for (std::size_t index = 0; index < exponents.size(); ++index) {
            const auto epsilon = std::ldexp(1.0, exponents[index]) * length;
            const auto id = operator_case.id + ".floppy_mechanism." +
                std::to_string(index);
            const auto evaluated = emit_evaluation(
                tables, counts, operator_case, id, "floppy_mechanism",
                "floppy_mechanism", displaced(
                    operator_case.graph->packets, direction, epsilon),
                identity_semantics(operator_case.graph->packets));
            double maximum = 0.0;
            for (const auto& packet : evaluated.force.packet_forces) {
                // Section 4 preregisters the same componentwise infinity norm
                // used by the ordinary reference-tangent rows.
                maximum = std::max(
                    {maximum,
                     std::abs(packet.force_n.x) / epsilon,
                     std::abs(packet.force_n.y) / epsilon,
                     std::abs(packet.force_n.z) / epsilon});
            }
            errors.push_back(maximum /
                std::max(operator_case.frozen.maximum_parent_h_magnitude_j_per_m2,
                         std::numeric_limits<double>::min()));
            ids.push_back(id);
            if (index != 0U && errors[index] > 0.0 && errors[index - 1U] > 0.0) {
                orders[index] = std::log(
                    errors[index - 1U] / errors[index]) / std::log(16.0);
            }
        }
        const auto decreases = errors[1] < errors[0] && errors[2] < errors[1] &&
            errors[3] < errors[2];
        const auto minimum = *std::ranges::min_element(errors);
        std::array order_values{orders[1], orders[2], orders[3]};
        std::ranges::sort(order_values);
        const auto median = order_values[1];
        const auto floor = registered_tolerance(
            operator_case.graph->packets.size(),
            operator_case.frozen.force_operator.relations.size(),
            262144.0, 1.0);
        const auto convergence =
            converges_until_binary64_floor(errors, floor);
        const auto initially_at_floor = errors.front() <= floor;
        const auto pass = convergence &&
            (initially_at_floor ||
             (decreases && median >= 0.75 && median <= 1.25));
        if (!pass) {
            counts.raw_registered_failures += exponents.size();
        }
        for (std::size_t index = 0; index < exponents.size(); ++index) {
            tables.reference_tangent.row(
                {operator_case.id, ids[index], "floppy_mechanism",
                 "floppy_mechanism", std::to_string(index),
                 hex64(std::ldexp(1.0, exponents[index])),
                 hex64(std::ldexp(1.0, exponents[index]) * length),
                 hex64(errors[index]), hex64(orders[index]), hex64(minimum),
                 bool_text(decreases), hex64(median), bool_text(pass)});
        }
    }
}

[[nodiscard]] std::string raw_summary_json(
    const Counts& counts, const Tables& tables, std::size_t configurations,
    std::size_t operators, bool full) {
    std::ostringstream output;
    output << "{\n"
           << "  \"schema\": \"" << summary_schema << "\",\n"
           << "  \"seed\": " << seed << ",\n"
           << "  \"full\": " << bool_text(full) << ",\n"
           << "  \"stage_status\": \"pending_independent_stage\",\n"
           << "  \"final_decision_emitted\": false,\n"
           << "  \"no_promotion\": \"NO_PROMOTION\",\n"
           << "  \"promotion_permitted\": false,\n"
           << "  \"configuration_count\": " << configurations << ",\n"
           << "  \"operator_count\": " << operators << ",\n"
           << "  \"force_evaluation_count\": "
           << counts.force_evaluations << ",\n"
           << "  \"valid_evaluation_count\": "
           << counts.valid_evaluations << ",\n"
           << "  \"coincident_failure_count\": "
           << counts.coincident_failures << ",\n"
           << "  \"reference_tangent_row_count\": "
           << tables.reference_tangent.size() << ",\n"
           << "  \"finite_tangent_row_count\": "
           << tables.finite_tangent.size() << ",\n"
           << "  \"metamorphic_row_count\": "
           << tables.metamorphic.size() << ",\n"
           << "  \"compression_row_count\": "
           << tables.compression.size() << ",\n"
           << "  \"raw_registered_failures\": "
           << counts.raw_registered_failures << ",\n"
           << "  \"exact_coincidence_failed_closed\": "
           << bool_text(counts.exact_coincidence_failed_closed) << ",\n"
           << "  \"result_boundary\": \"NO_PROMOTION to dynamics\"\n"
           << "}\n";
    return output.str();
}

[[nodiscard]] std::string raw_provenance_json(
    const FixtureInput& input, bool full) {
    std::ostringstream output;
    output << "{\n"
           << "  \"schema\": \"mls.conservative-force-consistency.raw-provenance.v1\",\n"
           << "  \"source_sha\": \"" << MLS_CONFIGURED_SOURCE_SHA << "\",\n"
           << "  \"source_branch\": \"" << MLS_CONFIGURED_SOURCE_BRANCH << "\",\n"
           << "  \"accepted_parent_sha\": \"" << parent_sha << "\",\n"
           << "  \"parent_evidence_tag\": \"constitutive-expressivity-lab-evidence-v1\",\n"
           << "  \"preregistration_commit\": \""
           << preregistration_commit << "\",\n"
           << "  \"seed\": " << seed << ",\n"
           << "  \"full\": " << bool_text(full) << ",\n"
           << "  \"dirty\": " << MLS_CONFIGURED_SOURCE_DIRTY << ",\n"
           << "  \"compiler_id\": \"" << MLS_CONFIGURED_COMPILER_ID << "\",\n"
           << "  \"compiler_version\": \""
           << MLS_CONFIGURED_COMPILER_VERSION << "\",\n"
#ifdef MLS_CONFIGURED_BUILD_TYPE
           << "  \"build_type\": \"" << MLS_CONFIGURED_BUILD_TYPE << "\",\n"
#else
           << "  \"build_type\": \"unknown\",\n"
#endif
           << "  \"inherited_blobs\": {\n"
           << "    \"include/mls/constitutive_expressivity_lab.hpp\": \"ba5743419cd956d9bc77b979ea3ec803cd5c4547\",\n"
           << "    \"src/constitutive_expressivity_lab.cpp\": \"1186bc643b8677ca8d72dba4347e26d5d07e8031\",\n"
           << "    \"apps/constitutive_expressivity_diagnostic.cpp\": \"ed6fd9eb0704262ca041c30fe8e091e4923028a6\",\n"
           << "    \"docs/constitutive-expressivity-preregistration.md\": \"4afa56de497035338b1c9b9299740b2691f471c3\"\n"
           << "  },\n"
           << "  \"symmetric_freeze_contract\": \"binary64_pair_average_mirrored_v1\",\n"
           << "  \"binary64_contract\": \"iec559_size8_digits53_explicit_order_fp_contract_off_v1\",\n"
           << "  \"parent_outer_pre_hash\": \"5382848fab2c84b7fad4eb43647e368c492cd245d27c10f552c01edffdc0842c\",\n"
           << "  \"parent_archive_sha256\": \"1bc4dccee877cd4a3d4ee05df7d3aab00d4643b400186a6a5ef5447b6cbb1123\",\n"
           << "  \"parent_bundle_manifest_pre_hash\": \""
           << parent_manifest_prehash << "\",\n"
           << "  \"parent_table_sha256\": ";
    if (full) {
        output << "{\n"
               << "    \"configurations.csv\": \""
               << input.hashes.at("configurations.csv") << "\",\n"
               << "    \"packets.csv\": \""
               << input.hashes.at("packets.csv")
               << "\",\n"
               << "    \"relations.csv\": \""
               << input.hashes.at("relations.csv")
               << "\",\n"
               << "    \"graph_energy.csv\": \""
               << input.hashes.at("graph_energy.csv") << "\",\n"
               << "    \"provenance.json\": \""
               << input.hashes.at("provenance.json") << "\"\n"
               << "  }\n";
    } else {
        output << "\"builtin_smoke\"\n";
    }
    output
           << "}\n";
    return output.str();
}

[[nodiscard]] std::string manifest_json(
    const std::map<std::string, std::string>& hashes) {
    std::string preimage;
    for (const auto& [name, digest] : hashes) {
        preimage += name;
        preimage.push_back('\0');
        preimage += digest;
        preimage.push_back('\n');
    }
    std::ostringstream output;
    output << "{\n  \"schema\": \"" << manifest_schema << "\",\n"
           << "  \"file_sha256\": {\n";
    std::size_t index = 0U;
    for (const auto& [name, digest] : hashes) {
        output << "    \"" << name << "\": \"" << digest << "\""
               << (++index == hashes.size() ? "\n" : ",\n");
    }
    output << "  },\n  \"pre_hash_sha256\": \"" << sha256(preimage)
           << "\"\n}\n";
    return output.str();
}

struct Arguments final {
    bool smoke{false};
    bool schema_audit{false};
    std::filesystem::path fixture_bundle{};
    std::filesystem::path output{};
};

[[nodiscard]] Arguments parse_arguments(int argc, char** argv) {
    Arguments result{};
    for (int index = 1; index < argc; ++index) {
        const std::string_view argument(argv[index]);
        if (argument == "--smoke") {
            result.smoke = true;
        } else if (argument == "--schema-audit") {
            result.schema_audit = true;
        } else if (argument == "--fixture-bundle" && index + 1 < argc) {
            result.fixture_bundle = argv[++index];
        } else if (argument == "--output" && index + 1 < argc) {
            result.output = argv[++index];
        } else {
            throw std::invalid_argument("unknown or incomplete argument");
        }
    }
    if (!result.schema_audit && result.output.empty()) {
        throw std::invalid_argument("--output is required");
    }
    if (!result.schema_audit && !result.smoke && result.fixture_bundle.empty()) {
        throw std::invalid_argument("full run requires --fixture-bundle");
    }
    return result;
}

int run(const Arguments& arguments) {
    if (arguments.schema_audit) {
        if (sha256("abc") !=
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad") {
            throw std::runtime_error("SHA-256 self-test failed");
        }
        audit_binary64_condition_diagnostic();
        const Tables audit_tables{};
        const std::array expected_headers{
            std::pair{&audit_tables.configurations,
                      std::string_view{"configuration_id,parent_source_id,role,packet_count,relation_count"}},
            std::pair{&audit_tables.reference_packets,
                      std::string_view{"configuration_id,packet_index,packet_id,semantic_packet_id,mass_quanta,x_m,y_m,z_m"}},
            std::pair{&audit_tables.relations,
                      std::string_view{"configuration_id,relation_index,first_id,second_id,semantic_first_id,semantic_second_id,reference_length_m,weight"}},
            std::pair{&audit_tables.operators,
                      std::string_view{"operator_id,configuration_id,family,target_k_over_g,a_j_per_m2,b_j_per_m2"}},
            std::pair{&audit_tables.h_matrix,
                      std::string_view{"operator_id,row_relation_index,column_relation_index,parent_value_j_per_m2,frozen_value_j_per_m2,correction_j_per_m2"}},
            std::pair{&audit_tables.current_packets,
                      std::string_view{"evaluation_id,packet_index,packet_id,semantic_packet_id,x_m,y_m,z_m,vx_m_per_s,vy_m_per_s,vz_m_per_s"}},
            std::pair{&audit_tables.force_evaluations,
                      std::string_view{"evaluation_id,operator_id,probe,velocity_probe,status,energy_j,extension_power_w,negative_force_power_w,power_residual_w,total_force_x_n,total_force_y_n,total_force_z_n,total_torque_origin_x_nm,total_torque_origin_y_nm,total_torque_origin_z_nm,total_torque_shifted_x_nm,total_torque_shifted_y_nm,total_torque_shifted_z_nm,balance_scale_force_n,balance_scale_torque_nm,balance_scale_power_w,tolerance_force_n,tolerance_torque_nm,tolerance_power_w,pass"}},
            std::pair{&audit_tables.relation_forces,
                      std::string_view{"evaluation_id,relation_index,first_id,second_id,reference_length_m,current_length_m,extension_m,conjugate_force_n,direction_x,direction_y,direction_z"}},
            std::pair{&audit_tables.packet_forces,
                      std::string_view{"evaluation_id,packet_index,packet_id,semantic_packet_id,force_x_n,force_y_n,force_z_n"}},
            std::pair{&audit_tables.reference_tangent,
                      std::string_view{"operator_id,evaluation_id,direction_id,direction_kind,epsilon_index,epsilon_over_l,epsilon_m,error_infinity_scaled,observed_order,minimum_relative_error,three_consecutive_decreases,median_order,pass"}},
            std::pair{&audit_tables.finite_tangent,
                      std::string_view{"evaluation_id,row_dof,column_dof,row_semantic_packet_id,row_axis,column_semantic_packet_id,column_axis,step_index,h_over_l,material_n_per_m,geometric_n_per_m,total_energy_hessian_n_per_m,force_jacobian_n_per_m,raw_binary64_force_jacobian_n_per_m,raw_gradient_residual_n_per_m,decomposition_residual_n_per_m,symmetry_residual_n_per_m,tolerance_n_per_m,pass"}},
            std::pair{&audit_tables.metamorphic,
                      std::string_view{"baseline_evaluation_id,probe_evaluation_id,probe,packet_coordinate_map,relation_coordinate_map,transformed_h_sha256,scale,expected_energy_ratio,actual_energy_ratio,energy_residual_j,force_covariance_residual_n,tangent_covariance_residual_n_per_m,relation_conjugate_residual_n,energy_tolerance_j,force_tolerance_n,tangent_tolerance_n_per_m,conjugate_tolerance_n,scaling_ratio_tolerance,pass"}},
            std::pair{&audit_tables.compression,
                      std::string_view{"operator_id,evaluation_id,relation_index,length_ratio,registered_domain_row,status,minimum_length_m,force_norm_n,material_tangent_norm_n_per_m,geometric_tangent_norm_n_per_m,total_tangent_norm_n_per_m,condition_estimate,binary64_gradient_error_n,ulp_coordinate_sensitivity_n,adjacent_length_resolved,pass"}},
        };
        for (const auto& [table, expected] : expected_headers) {
            if (table->header() != expected) {
                throw std::runtime_error("raw CSV header audit failed");
            }
        }
        const auto manifest = manifest_json({{"probe", sha256("probe")}});
        if (manifest.find(std::string(manifest_schema)) == std::string::npos ||
            manifest.find("\"file_sha256\"") == std::string::npos ||
            manifest.find("\"files\"") != std::string::npos ||
            manifest.find(
                "837ee0391c401a1fde5e6f445e745a5f5cd4149a1574bdb87c4f2655ff608b62") ==
                std::string::npos) {
            throw std::runtime_error(
                "raw manifest field audit failed: " + manifest);
        }
        const auto smoke_graph = smoke_graphs().front();
        const auto smoke_operator = build_operator(smoke_graph, 2.0).frozen;
        const auto scaled_smoke = scaled_reference_operator(smoke_operator, 2.0);
        static_cast<void>(force::evaluate_spatial_force(
            scaled_smoke,
            rigid_transform(
                smoke_graph.packets, Matrix3d::identity(), {}, 2.0)));
        if (!arguments.fixture_bundle.empty()) {
            const auto accepted_parent =
                load_fixture_bundle(arguments.fixture_bundle);
            std::size_t rebuilt_operators = 0U;
            for (const auto& graph : accepted_parent.configurations) {
                for (const auto ratio :
                     std::array{1.0 / 3.0, 2.0, 10.0}) {
                    static_cast<void>(build_operator(graph, ratio));
                    ++rebuilt_operators;
                }
            }
            if (rebuilt_operators !=
                3U * registered_configuration_ids.size()) {
                throw std::runtime_error(
                    "accepted parent operator inventory audit failed");
            }
            std::cout << "Accepted constitutive parent fixture audit: PASS\n";
        }
        std::cout << "Conservative Force Consistency raw schema audit: PASS\n";
        return 0;
    }
    FixtureInput input{};
    if (arguments.smoke) {
        input.configurations = smoke_graphs();
    } else {
        input = load_fixture_bundle(arguments.fixture_bundle);
    }
    Tables tables{};
    Counts counts{};
    std::vector<OperatorCase> operators;
    operators.reserve(3U * input.configurations.size());
    emit_inputs(input.configurations, operators, tables);
    static_cast<void>(emit_base_evaluations(
        tables, counts, operators, arguments.smoke));
    emit_direction_source_evaluations(
        tables, counts, operators, arguments.smoke);
    emit_reference_tangent(tables, counts, operators, arguments.smoke);
    emit_floppy_mechanism(tables, counts, operators, arguments.smoke);
    emit_finite_tangent(tables, counts, operators, arguments.smoke);
    emit_metamorphic(tables, counts, operators, arguments.smoke);
    emit_compression(tables, counts, operators, arguments.smoke);

    std::map<std::string, std::string> payloads{
        {"configurations.csv", tables.configurations.contents()},
        {"reference_packets.csv", tables.reference_packets.contents()},
        {"relations.csv", tables.relations.contents()},
        {"operators.csv", tables.operators.contents()},
        {"h_matrix.csv", tables.h_matrix.contents()},
        {"current_packets.csv", tables.current_packets.contents()},
        {"force_evaluations.csv", tables.force_evaluations.contents()},
        {"relation_forces.csv", tables.relation_forces.contents()},
        {"packet_forces.csv", tables.packet_forces.contents()},
        {"reference_tangent.csv", tables.reference_tangent.contents()},
        {"finite_tangent.csv", tables.finite_tangent.contents()},
        {"metamorphic.csv", tables.metamorphic.contents()},
        {"compression.csv", tables.compression.contents()},
        {"raw_summary.json",
         raw_summary_json(
             counts, tables, input.configurations.size(), operators.size(),
             !arguments.smoke)},
        {"raw_provenance.json",
         raw_provenance_json(input, !arguments.smoke)},
    };
    auto write_root = arguments.output;
    bool owns_staging = false;
    if (!arguments.smoke) {
        if (std::filesystem::exists(arguments.output)) {
            throw std::runtime_error(
                "full raw output already exists; overwrite is forbidden");
        }
        write_root = arguments.output;
        write_root += ".staging-";
        write_root += std::string(MLS_CONFIGURED_SOURCE_SHA).substr(0U, 12U);
        if (std::filesystem::exists(write_root) ||
            !std::filesystem::create_directories(write_root)) {
            throw std::runtime_error(
                "cannot acquire a fresh owned raw staging directory");
        }
        owns_staging = true;
    } else {
        // Smoke outputs are explicitly test-only and rerunnable. Canonical full
        // evidence never enters this branch.
        std::filesystem::create_directories(write_root);
    }
    std::map<std::string, std::string> hashes;
    try {
        for (const auto& [name, contents] : payloads) {
            write_text(write_root / name, contents);
            hashes.emplace(name, sha256(contents));
        }
        write_text(write_root / "manifest.json", manifest_json(hashes));
        if (!arguments.smoke) {
            if (std::filesystem::exists(arguments.output)) {
                throw std::runtime_error(
                    "full raw output appeared before no-replace publication");
            }
            std::filesystem::rename(write_root, arguments.output);
            owns_staging = false;
        }
    } catch (...) {
        if (owns_staging && std::filesystem::exists(write_root)) {
            std::filesystem::remove_all(write_root);
        }
        throw;
    }
    std::cout << "CONSERVATIVE FORCE RAW BUNDLE COMPLETE\n"
              << "output=" << arguments.output.string() << '\n'
              << "stage=pending_independent_stage\n"
              << "NO_PROMOTION\n";
    return 0;
}

} // namespace

int main(int argc, char** argv) {
    try {
        return run(parse_arguments(argc, argv));
    } catch (const std::exception& error) {
        std::cerr << "Conservative Force Consistency diagnostic failed: "
                  << error.what() << '\n';
        return 1;
    }
}
