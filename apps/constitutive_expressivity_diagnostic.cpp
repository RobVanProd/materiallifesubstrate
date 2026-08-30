#include "mls/constitutive_expressivity_lab.hpp"

#include "mls/kelvin_covariance_audit.hpp"
#include "mls/relational_observability_confirmation.hpp"

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

namespace constitutive =
    mls::experimental::constitutive_expressivity;
namespace confirmation =
    mls::experimental::relational_observability_confirmation;
namespace kelvin = mls::experimental::kelvin_covariance_audit;
namespace observation = mls::experimental::mechanical_observability;
using mls::experimental::Matrix3d;
using mls::experimental::Vec3d;
using observation::BondRelation;
using observation::DenseMatrix;
using observation::MechanicalPacket;

constexpr std::uint64_t seed = 260828U;
constexpr std::string_view parent_sha =
    "101296f936f8473effb316b1f9ae4040b5768349";
constexpr std::string_view branch = "constitutive-expressivity-lab";
constexpr std::string_view summary_schema =
    "mls.constitutive-expressivity.summary.v1";
constexpr std::string_view manifest_schema =
    "mls.constitutive-expressivity.manifest.v1";
constexpr std::string_view accepted_configurations_hash =
    "cbae18e3b2c356e2898d1410f37fb90692d889f28438cfb5524753c87f1db2b7";
constexpr std::string_view accepted_packets_hash =
    "dfd22994678333125b90f658d5b228c09f45e4564f52e02d6f38a3b2f3c924f7";
constexpr std::string_view accepted_relations_hash =
    "14afdb0ac5822294a5d5437b3e622dffdc9f886dda395d0bfef5ae9b13c73093";

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

[[nodiscard]] std::vector<std::string> split_header(
    std::string_view header) {
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

[[nodiscard]] std::string bool_text(bool value) {
    return value ? "true" : "false";
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

[[nodiscard]] std::string read_binary_text(
    const std::filesystem::path& path) {
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

void write_bytes(const std::filesystem::path& path,
                 std::span<const std::uint8_t> value) {
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    if (!stream) {
        throw std::runtime_error("cannot write binary output: " + path.string());
    }
    stream.write(reinterpret_cast<const char*>(value.data()),
                 static_cast<std::streamsize>(value.size()));
    if (!stream) {
        throw std::runtime_error("failed writing binary output: " + path.string());
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
    if (quoted) {
        throw std::runtime_error("unterminated quoted CSV field");
    }
    if (!field.empty() || !row.empty()) {
        row.push_back(std::move(field));
        rows.push_back(std::move(row));
    }
    return rows;
}

[[nodiscard]] std::map<std::string, std::size_t> header_map(
    const Row& header) {
    std::map<std::string, std::size_t> result;
    for (std::size_t index = 0U; index < header.size(); ++index) {
        if (!result.emplace(header[index], index).second) {
            throw std::runtime_error("duplicate CSV header");
        }
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

[[nodiscard]] std::uint64_t parse_u64(std::string_view value) {
    std::uint64_t result = 0U;
    const auto parsed = std::from_chars(
        value.data(), value.data() + value.size(), result);
    if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size()) {
        throw std::runtime_error("invalid uint64 field");
    }
    return result;
}

[[nodiscard]] std::int64_t parse_i64(std::string_view value) {
    std::int64_t result = 0;
    const auto parsed = std::from_chars(
        value.data(), value.data() + value.size(), result);
    if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size()) {
        throw std::runtime_error("invalid int64 field");
    }
    return result;
}

struct GraphConfiguration final {
    std::string id{};
    std::vector<MechanicalPacket> packets{};
    std::vector<BondRelation> relations{};
    bool intentionally_floppy{false};
};

[[nodiscard]] bool selected_id(std::string_view id) {
    return std::ranges::find(registered_configuration_ids, id) !=
        registered_configuration_ids.end();
}

[[nodiscard]] std::vector<GraphConfiguration> smoke_graphs() {
    const std::vector<MechanicalPacket> packets{
        {1, 1, {0.0, 0.0, 0.0}, {}},
        {2, 1, {1.0, 0.0, 0.0}, {}},
        {3, 1, {0.0, 1.0, 0.0}, {}},
        {4, 1, {0.0, 0.0, 1.0}, {}},
    };
    const std::vector<BondRelation> k4{
        {1, 2}, {1, 3}, {1, 4}, {2, 3}, {2, 4}, {3, 4}};
    auto missing = k4;
    missing.pop_back();
    return {
        {"exact.tetrahedron_k4", packets, k4, false},
        {"exact.tetrahedron_k4_minus_edge", packets, missing, true},
    };
}

struct FixtureInput final {
    std::vector<GraphConfiguration> configurations{};
    std::map<std::string, std::string> hashes{};
};

[[nodiscard]] FixtureInput load_fixture_bundle(
    const std::filesystem::path& directory) {
    const auto configurations_text =
        read_binary_text(directory / "configurations.csv");
    const auto packets_text = read_binary_text(directory / "packets.csv");
    const auto relations_text = read_binary_text(directory / "relations.csv");
    FixtureInput result{};
    result.hashes = {
        {"configurations.csv", sha256(configurations_text)},
        {"packets.csv", sha256(packets_text)},
        {"relations.csv", sha256(relations_text)},
    };
    if (result.hashes.at("configurations.csv") != accepted_configurations_hash ||
        result.hashes.at("packets.csv") != accepted_packets_hash ||
        result.hashes.at("relations.csv") != accepted_relations_hash) {
        throw std::runtime_error("accepted fixture hash mismatch");
    }
    auto configuration_rows = parse_csv(configurations_text);
    auto packet_rows = parse_csv(packets_text);
    auto relation_rows = parse_csv(relations_text);
    if (configuration_rows.empty() || packet_rows.empty() ||
        relation_rows.empty()) {
        throw std::runtime_error("fixture bundle table is empty");
    }
    const auto ch = header_map(configuration_rows.front());
    const auto ph = header_map(packet_rows.front());
    const auto rh = header_map(relation_rows.front());
    std::map<std::string, std::size_t> lookup;
    for (std::size_t row = 1U; row < configuration_rows.size(); ++row) {
        const auto& values = configuration_rows[row];
        const auto& id = values.at(ch.at("configuration_id"));
        if (!selected_id(id)) {
            continue;
        }
        GraphConfiguration configuration{};
        configuration.id = id;
        configuration.intentionally_floppy =
            id == "exact.tetrahedron_k4_minus_edge";
        lookup.emplace(id, result.configurations.size());
        result.configurations.push_back(std::move(configuration));
    }
    if (result.configurations.size() != registered_configuration_ids.size()) {
        throw std::runtime_error("registered fixture configuration missing");
    }
    for (std::size_t row = 1U; row < packet_rows.size(); ++row) {
        const auto& values = packet_rows[row];
        const auto found = lookup.find(values.at(ph.at("configuration_id")));
        if (found == lookup.end()) {
            continue;
        }
        result.configurations[found->second].packets.push_back({
            parse_u64(values.at(ph.at("packet_id"))),
            parse_i64(values.at(ph.at("mass_quanta"))),
            {parse_double(values.at(ph.at("x_m"))),
             parse_double(values.at(ph.at("y_m"))),
             parse_double(values.at(ph.at("z_m")))},
            {parse_double(values.at(ph.at("vx_m_per_s"))),
             parse_double(values.at(ph.at("vy_m_per_s"))),
             parse_double(values.at(ph.at("vz_m_per_s")))},
        });
    }
    for (std::size_t row = 1U; row < relation_rows.size(); ++row) {
        const auto& values = relation_rows[row];
        const auto found = lookup.find(values.at(rh.at("configuration_id")));
        if (found == lookup.end() ||
            values.at(rh.at("selection_status")) != "retained") {
            continue;
        }
        result.configurations[found->second].relations.push_back({
            parse_u64(values.at(rh.at("first_id"))),
            parse_u64(values.at(rh.at("second_id"))),
        });
    }
    std::ranges::sort(result.configurations, {}, &GraphConfiguration::id);
    for (auto& configuration : result.configurations) {
        std::ranges::sort(configuration.packets, {}, &MechanicalPacket::id);
        std::ranges::sort(configuration.relations, [](const auto& lhs,
                                                       const auto& rhs) {
            return std::pair{lhs.first_id, lhs.second_id} <
                std::pair{rhs.first_id, rhs.second_id};
        });
        static_cast<void>(observation::build_bond_rigidity_operator(
            configuration.packets, configuration.relations));
    }
    return result;
}

struct Cubature final {
    std::string id{};
    std::vector<MechanicalPacket> packets{};
    std::vector<constitutive::WeightedRelation> relations{};
    double moment_m2{0.0};
    double second_moment{0.0};
    double fourth_coefficient{0.0};
    double collective_a_multiplier{0.0};
    double collective_b_multiplier{0.0};
};

[[nodiscard]] Cubature seven_line_cubature() {
    const auto d = 1.0 / std::sqrt(3.0);
    return {
        "axes_body_diagonals_7",
        {{1, 1, {0.0, 0.0, 0.0}, {}},
         {2, 1, {1.0, 0.0, 0.0}, {}},
         {3, 1, {0.0, 1.0, 0.0}, {}},
         {4, 1, {0.0, 0.0, 1.0}, {}},
         {5, 1, {d, d, d}, {}},
         {6, 1, {d, -d, -d}, {}},
         {7, 1, {-d, d, -d}, {}},
         {8, 1, {-d, -d, d}, {}}},
        {{{1, 2}, 8.0}, {{1, 3}, 8.0}, {{1, 4}, 8.0},
         {{1, 5}, 9.0}, {{1, 6}, 9.0}, {{1, 7}, 9.0},
         {{1, 8}, 9.0}},
        60.0,
        20.0,
        4.0,
        3.0 / 20.0,
        1.0 / 4.0,
    };
}

[[nodiscard]] Cubature nine_line_cubature() {
    const auto d = 1.0 / std::sqrt(2.0);
    return {
        "axes_face_diagonals_9",
        {{1, 1, {0.0, 0.0, 0.0}, {}},
         {2, 1, {1.0, 0.0, 0.0}, {}},
         {3, 1, {0.0, 1.0, 0.0}, {}},
         {4, 1, {0.0, 0.0, 1.0}, {}},
         {5, 1, {d, d, 0.0}, {}},
         {6, 1, {d, -d, 0.0}, {}},
         {7, 1, {d, 0.0, d}, {}},
         {8, 1, {d, 0.0, -d}, {}},
         {9, 1, {0.0, d, d}, {}},
         {10, 1, {0.0, d, -d}, {}}},
        {{{1, 2}, 1.0}, {{1, 3}, 1.0}, {{1, 4}, 1.0},
         {{1, 5}, 2.0}, {{1, 6}, 2.0}, {{1, 7}, 2.0},
         {{1, 8}, 2.0}, {{1, 9}, 2.0}, {{1, 10}, 2.0}},
        15.0,
        5.0,
        1.0,
        3.0 / 5.0,
        1.0,
    };
}

[[nodiscard]] std::vector<BondRelation> plain_relations(
    std::span<const constitutive::WeightedRelation> weighted) {
    std::vector<BondRelation> result;
    result.reserve(weighted.size());
    for (const auto& entry : weighted) {
        result.push_back(entry.relation);
    }
    return result;
}

[[nodiscard]] std::vector<constitutive::PacketDisplacement>
affine_displacements(std::span<const MechanicalPacket> packets,
                     const Matrix3d& strain) {
    std::vector<constitutive::PacketDisplacement> result;
    result.reserve(packets.size());
    for (const auto& packet : packets) {
        result.push_back(
            {packet.id, mls::experimental::multiply(strain, packet.position_m)});
    }
    return result;
}

[[nodiscard]] Matrix3d add(Matrix3d lhs, const Matrix3d& rhs) {
    for (std::size_t row = 0U; row < 3U; ++row) {
        for (std::size_t column = 0U; column < 3U; ++column) {
            lhs.value[row][column] += rhs.value[row][column];
        }
    }
    return lhs;
}

[[nodiscard]] std::vector<Matrix3d> kelvin_basis() {
    const auto d = 1.0 / std::sqrt(2.0);
    std::vector<Matrix3d> result(6U);
    result[0].value[0][0] = 1.0;
    result[1].value[1][1] = 1.0;
    result[2].value[2][2] = 1.0;
    result[3].value[0][1] = d;
    result[3].value[1][0] = d;
    result[4].value[0][2] = d;
    result[4].value[2][0] = d;
    result[5].value[1][2] = d;
    result[5].value[2][1] = d;
    return result;
}

[[nodiscard]] std::vector<Matrix3d> mixed_strains() {
    std::vector<Matrix3d> result(3U);
    result[0].value = {{{1.0 / 5.0, 1.0 / 7.0, -1.0 / 11.0},
                        {1.0 / 7.0, -2.0 / 5.0, 1.0 / 13.0},
                        {-1.0 / 11.0, 1.0 / 13.0, 1.0 / 3.0}}};
    result[1].value = {{{-1.0 / 4.0, 1.0 / 9.0, 1.0 / 10.0},
                        {1.0 / 9.0, 1.0 / 6.0, -1.0 / 8.0},
                        {1.0 / 10.0, -1.0 / 8.0, 1.0 / 12.0}}};
    result[2].value = {{{2.0 / 7.0, -1.0 / 6.0, 1.0 / 5.0},
                        {-1.0 / 6.0, 1.0 / 9.0, 1.0 / 14.0},
                        {1.0 / 5.0, 1.0 / 14.0, -3.0 / 11.0}}};
    return result;
}

[[nodiscard]] double trace(const Matrix3d& value) noexcept {
    return value.value[0][0] + value.value[1][1] + value.value[2][2];
}

[[nodiscard]] double deviatoric_squared(const Matrix3d& value) noexcept {
    const auto mean = trace(value) / 3.0;
    double result = 0.0;
    for (std::size_t row = 0U; row < 3U; ++row) {
        for (std::size_t column = 0U; column < 3U; ++column) {
            auto entry = value.value[row][column];
            if (row == column) {
                entry -= mean;
            }
            result += entry * entry;
        }
    }
    return result;
}

[[nodiscard]] double expected_isotropic_energy(
    const Matrix3d& strain, double bulk, double shear) noexcept {
    return 0.5 * bulk * trace(strain) * trace(strain) +
        shear * deviatoric_squared(strain);
}

[[nodiscard]] double center_energy(
    const Cubature& cubature,
    const constitutive::RelationEnergyOperator& energy_operator,
    const Matrix3d& strain) {
    const auto relations = plain_relations(cubature.relations);
    const auto extensions = constitutive::evaluate_linearized_relation_extensions(
        cubature.packets,
        affine_displacements(cubature.packets, strain), relations);
    const auto evaluated = constitutive::evaluate_energy(
        energy_operator, extensions);
    const auto found = std::ranges::find(
        evaluated.local, std::uint64_t{1},
        &constitutive::LocalEnergyValue::packet_id);
    if (!evaluated.finite || found == evaluated.local.end()) {
        throw std::runtime_error("central collective energy unavailable");
    }
    return found->total_j;
}

[[nodiscard]] double total_energy(
    const Cubature& cubature,
    const constitutive::RelationEnergyOperator& energy_operator,
    const Matrix3d& strain) {
    const auto relations = plain_relations(cubature.relations);
    const auto extensions = constitutive::evaluate_linearized_relation_extensions(
        cubature.packets,
        affine_displacements(cubature.packets, strain), relations);
    const auto evaluated = constitutive::evaluate_energy(
        energy_operator, extensions);
    if (!evaluated.finite) {
        throw std::runtime_error("pair energy unavailable");
    }
    return evaluated.total_j;
}

[[nodiscard]] double tolerance(std::size_t packets, std::size_t relations,
                               double factor, double scale = 1.0) noexcept {
    const auto dimension = std::max(
        {std::size_t{6}, 3U * packets, relations});
    return factor * static_cast<double>(dimension) *
        std::numeric_limits<double>::epsilon() * std::max(1.0, scale);
}

struct Tables final {
    Csv configurations{
        "configuration_id,parent_source_id,role,packet_count,relation_count"};
    Csv packets{
        "configuration_id,packet_index,packet_id,mass_quanta,x_m,y_m,z_m"};
    Csv relations{
        "configuration_id,relation_index,first_id,second_id,reference_length_m"};
    Csv bulk{
        "control_id,cubature,family,target_k_over_g,a_j_per_m2,b_j_per_m2,"
        "weighted_moment_m2,second_moment,fourth_moment_coefficient,"
        "measured_bulk,measured_shear,measured_k_over_g,measured_poisson,"
        "cross_coupling,tangent_symmetry_residual,minimum_registered_energy,"
        "positive,pass"};
    Csv tangent{
        "control_id,row,column,actual,expected,residual,tolerance,pass"};
    Csv strain{
        "control_id,strain_id,actual_energy,expected_energy,residual,tolerance,pass"};
    Csv graph{
        "configuration_id,family,target_k_over_g,packet_count,relation_count,"
        "r_rank,r_nullity,r_nonrigid_nullity,lr_rank,lr_nullity,"
        "lr_nonrigid_nullity,lr_threshold,rank_ambiguous,h_symmetry_residual,"
        "k_symmetry_residual,h_lambda_min_certified_lower,"
        "h_lambda_max_certified_upper,h_positive_certified,h_nnz,h_density,"
        "nonlocal_off_diagonal_count,max_graph_hop,max_euclidean_coupling_m,"
        "rigid_energy_residual,null_energy_residual,min_resolved_lr_sigma,"
        "kernel_equal,pass"};
    Csv spectra{
        "configuration_id,family,target_k_over_g,singular_index,"
        "singular_value,threshold,classification"};
    Csv metamorphic{
        "configuration_id,family,probe,baseline_energy,probe_energy,"
        "expected_ratio,actual_ratio,residual,tolerance,pass"};
    Csv checkpoints{
        "configuration_id,byte_count,sha256_before,sha256_roundtrip,"
        "roundtrip_exact,diagnostics_read_only,pass"};
};

void emit_selected_inputs(std::span<const GraphConfiguration> configurations,
                          Tables& tables) {
    for (const auto& configuration : configurations) {
        tables.configurations.row({
            configuration.id,
            configuration.id,
            configuration.intentionally_floppy ? "intentionally_floppy"
                                                : "eligible_generic",
            std::to_string(configuration.packets.size()),
            std::to_string(configuration.relations.size()),
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
            });
        }
        const auto rigidity = observation::build_bond_rigidity_operator(
            configuration.packets, configuration.relations);
        for (std::size_t index = 0U; index < rigidity.relations.size(); ++index) {
            tables.relations.row({
                configuration.id,
                std::to_string(index),
                std::to_string(rigidity.relations[index].first_id),
                std::to_string(rigidity.relations[index].second_id),
                hex64(rigidity.lengths_m[index]),
            });
        }
    }
}

struct RunCounts final {
    std::size_t bulk_rows{0U};
    std::size_t bulk_failures{0U};
    std::size_t graph_rows{0U};
    std::size_t graph_failures{0U};
    std::size_t metamorphic_rows{0U};
    std::size_t metamorphic_failures{0U};
    std::size_t checkpoint_rows{0U};
    std::size_t checkpoint_failures{0U};
};

[[nodiscard]] std::array<std::array<double, 6>, 6> tangent_matrix(
    const std::function<double(const Matrix3d&)>& energy) {
    const auto basis = kelvin_basis();
    std::array<std::array<double, 6>, 6> result{};
    for (std::size_t index = 0U; index < 6U; ++index) {
        result[index][index] = 2.0 * energy(basis[index]);
    }
    for (std::size_t row = 0U; row < 6U; ++row) {
        for (std::size_t column = row + 1U; column < 6U; ++column) {
            result[row][column] = energy(add(basis[row], basis[column])) -
                0.5 * result[row][row] - 0.5 * result[column][column];
            result[column][row] = result[row][column];
        }
    }
    return result;
}

[[nodiscard]] double volumetric_deviatoric_cross(
    const std::array<std::array<double, 6>, 6>& tangent) {
    const auto inv_sqrt_three = 1.0 / std::sqrt(3.0);
    const auto inv_sqrt_two = 1.0 / std::sqrt(2.0);
    const auto inv_sqrt_six = 1.0 / std::sqrt(6.0);
    const std::array<double, 6> volumetric{
        inv_sqrt_three, inv_sqrt_three, inv_sqrt_three, 0.0, 0.0, 0.0};
    const std::array<std::array<double, 6>, 5> deviatoric{{
        {inv_sqrt_two, -inv_sqrt_two, 0.0, 0.0, 0.0, 0.0},
        {inv_sqrt_six, inv_sqrt_six, -2.0 * inv_sqrt_six, 0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0, 1.0, 0.0, 0.0},
        {0.0, 0.0, 0.0, 0.0, 1.0, 0.0},
        {0.0, 0.0, 0.0, 0.0, 0.0, 1.0},
    }};
    double result = 0.0;
    for (const auto& direction : deviatoric) {
        long double value = 0.0L;
        for (std::size_t row = 0U; row < 6U; ++row) {
            for (std::size_t column = 0U; column < 6U; ++column) {
                value += static_cast<long double>(volumetric[row]) *
                    tangent[row][column] * direction[column];
            }
        }
        result = std::max(result, std::abs(static_cast<double>(value)));
    }
    return result;
}

[[nodiscard]] Matrix3d axis_angle_rotation();

[[nodiscard]] Matrix3d rotate_strain(
    const Matrix3d& rotation, const Matrix3d& strain) {
    return mls::experimental::multiply(
        mls::experimental::multiply(rotation, strain),
        mls::experimental::transpose(rotation));
}

[[nodiscard]] Cubature rotate_cubature(
    const Cubature& cubature, const Matrix3d& rotation) {
    auto result = cubature;
    result.id += ".rotated";
    for (auto& packet : result.packets) {
        packet.position_m =
            mls::experimental::multiply(rotation, packet.position_m);
    }
    return result;
}

void emit_bulk_controls(Tables& tables, RunCounts& counts) {
    const std::array cubatures{seven_line_cubature(), nine_line_cubature()};
    const std::array ratios{1.0 / 3.0, 1.0, 2.0, 10.0};
    for (const auto& cubature : cubatures) {
        std::vector<constitutive::PairRelationCoefficient> pair_coefficients;
        for (const auto& entry : cubature.relations) {
            pair_coefficients.push_back({entry.relation, entry.weight});
        }
        const auto pair = constitutive::build_pair_separable_energy(
            cubature.packets, pair_coefficients);
        const auto pair_energy = [&](const Matrix3d& strain) {
            return total_energy(cubature, pair, strain);
        };
        const auto pair_tangent = tangent_matrix(pair_energy);
        const auto pair_shear = 0.5 * pair_tangent[3][3];
        const auto pair_bulk = std::accumulate(
            pair_tangent[0].begin(), pair_tangent[0].begin() + 3U, 0.0) /
            3.0;
        const auto pair_ratio = pair_bulk / pair_shear;
        auto pair_symmetry = 0.0;
        bool pair_tangent_pass = true;
        const auto pair_id = cubature.id + ".pair";
        for (std::size_t row = 0U; row < 6U; ++row) {
            for (std::size_t column = 0U; column < 6U; ++column) {
                const auto trace_row = row < 3U ? 1.0 : 0.0;
                const auto trace_column = column < 3U ? 1.0 : 0.0;
                const auto expected = pair_bulk * trace_row * trace_column +
                    2.0 * pair_shear *
                        ((row == column ? 1.0 : 0.0) -
                         trace_row * trace_column / 3.0);
                const auto residual =
                    std::abs(pair_tangent[row][column] - expected);
                const auto gate = tolerance(
                    cubature.packets.size(), cubature.relations.size(),
                    65536.0,
                    std::max(std::abs(expected),
                             std::abs(pair_tangent[row][column])));
                pair_symmetry = std::max(
                    pair_symmetry,
                    std::abs(pair_tangent[row][column] -
                             pair_tangent[column][row]));
                pair_tangent_pass = pair_tangent_pass && residual <= gate;
                tables.tangent.row({
                    pair_id,
                    std::to_string(row),
                    std::to_string(column),
                    hex64(pair_tangent[row][column]),
                    hex64(expected),
                    hex64(residual),
                    hex64(gate),
                    bool_text(residual <= gate),
                });
            }
        }
        auto pair_minimum_energy = std::numeric_limits<double>::infinity();
        std::vector<std::pair<std::string, Matrix3d>> pair_strains;
        std::size_t pair_index = 0U;
        for (const auto& strain : kelvin_basis()) {
            pair_strains.emplace_back(
                "kelvin_" + std::to_string(pair_index++), strain);
        }
        pair_index = 0U;
        for (const auto& strain : mixed_strains()) {
            pair_strains.emplace_back(
                "mixed_" + std::to_string(pair_index++), strain);
        }
        const auto rotation = axis_angle_rotation();
        const auto rotated_cubature = rotate_cubature(cubature, rotation);
        const auto rotated_pair = constitutive::build_pair_separable_energy(
            rotated_cubature.packets, pair_coefficients);
        for (const auto& [strain_id, strain] : pair_strains) {
            const auto actual = pair_energy(strain);
            const auto expected =
                expected_isotropic_energy(strain, pair_bulk, pair_shear);
            const auto residual = std::abs(actual - expected);
            const auto gate = tolerance(
                cubature.packets.size(), cubature.relations.size(), 65536.0,
                std::max(actual, expected));
            pair_minimum_energy = std::min(pair_minimum_energy, actual);
            pair_tangent_pass = pair_tangent_pass && residual <= gate;
            tables.strain.row({pair_id, strain_id, hex64(actual), hex64(expected),
                               hex64(residual), hex64(gate),
                               bool_text(residual <= gate)});
            const auto rotated_energy = total_energy(
                rotated_cubature, rotated_pair,
                rotate_strain(rotation, strain));
            const auto rotation_residual = std::abs(rotated_energy - actual);
            const auto rotation_gate = tolerance(
                cubature.packets.size(), cubature.relations.size(), 32768.0,
                std::max(actual, rotated_energy));
            pair_tangent_pass =
                pair_tangent_pass && rotation_residual <= rotation_gate;
            tables.strain.row({
                pair_id, "rotated_" + strain_id, hex64(rotated_energy),
                hex64(actual), hex64(rotation_residual), hex64(rotation_gate),
                bool_text(rotation_residual <= rotation_gate)});
        }
        const auto pair_tolerance = tolerance(
            cubature.packets.size(), cubature.relations.size(), 131072.0,
            pair_ratio);
        const auto pair_pass = pair_tangent_pass &&
            std::abs(pair_ratio - 5.0 / 3.0) <= pair_tolerance &&
            pair_minimum_energy > 0.0;
        tables.bulk.row({
            pair_id,
            cubature.id,
            "pair_separable",
            hex64(5.0 / 3.0),
            hex64(0.0),
            hex64(0.0),
            hex64(cubature.moment_m2),
            hex64(cubature.second_moment),
            hex64(cubature.fourth_coefficient),
            hex64(pair_bulk),
            hex64(pair_shear),
            hex64(pair_ratio),
            hex64((3.0 * pair_bulk - 2.0 * pair_shear) /
                  (2.0 * (3.0 * pair_bulk + pair_shear))),
            hex64(volumetric_deviatoric_cross(pair_tangent)),
            hex64(pair_symmetry),
            hex64(pair_minimum_energy),
            bool_text(pair_bulk > 0.0 && pair_shear > 0.0),
            bool_text(pair_pass),
        });
        ++counts.bulk_rows;
        counts.bulk_failures += pair_pass ? 0U : 1U;

        for (const auto ratio : ratios) {
            constexpr auto shear = 1.0;
            const auto bulk = ratio * shear;
            const auto coefficient_a =
                cubature.collective_a_multiplier * bulk;
            const auto coefficient_b =
                cubature.collective_b_multiplier * shear;
            const auto collective = constitutive::build_local_collective_energy(
                cubature.packets, cubature.relations,
                {.dilatational_coefficient_j_per_m2 = coefficient_a,
                 .deviatoric_coefficient_j_per_m2 = coefficient_b});
            const auto energy = [&](const Matrix3d& strain) {
                return center_energy(cubature, collective, strain);
            };
            const auto tangent = tangent_matrix(energy);
            const auto measured_shear = 0.5 * tangent[3][3];
            const auto measured_bulk = std::accumulate(
                tangent[0].begin(), tangent[0].begin() + 3U, 0.0) / 3.0;
            const auto measured_ratio = measured_bulk / measured_shear;
            const auto control_id = cubature.id + ".collective." + hex64(ratio);
            auto tangent_symmetry = 0.0;
            bool tangent_pass = true;
            for (std::size_t row = 0U; row < 6U; ++row) {
                for (std::size_t column = 0U; column < 6U; ++column) {
                    const auto trace_row = row < 3U ? 1.0 : 0.0;
                    const auto trace_column = column < 3U ? 1.0 : 0.0;
                    const auto expected = bulk * trace_row * trace_column +
                        2.0 * shear *
                            ((row == column ? 1.0 : 0.0) -
                             trace_row * trace_column / 3.0);
                    const auto residual = std::abs(tangent[row][column] - expected);
                    const auto gate = tolerance(
                        cubature.packets.size(), cubature.relations.size(),
                        65536.0, std::max(std::abs(expected),
                                         std::abs(tangent[row][column])));
                    tangent_symmetry = std::max(
                        tangent_symmetry,
                        std::abs(tangent[row][column] - tangent[column][row]));
                    tangent_pass = tangent_pass && residual <= gate;
                    tables.tangent.row({
                        control_id,
                        std::to_string(row),
                        std::to_string(column),
                        hex64(tangent[row][column]),
                        hex64(expected),
                        hex64(residual),
                        hex64(gate),
                        bool_text(residual <= gate),
                    });
                }
            }
            auto minimum_energy = std::numeric_limits<double>::infinity();
            const auto basis = kelvin_basis();
            std::size_t strain_index = 0U;
            for (const auto& strain : basis) {
                const auto actual = energy(strain);
                const auto expected = expected_isotropic_energy(strain, bulk, shear);
                const auto residual = std::abs(actual - expected);
                const auto gate = tolerance(
                    cubature.packets.size(), cubature.relations.size(), 65536.0,
                    std::max(actual, expected));
                minimum_energy = std::min(minimum_energy, actual);
                tangent_pass = tangent_pass && residual <= gate;
                tables.strain.row({
                    control_id,
                    "kelvin_" + std::to_string(strain_index++),
                    hex64(actual), hex64(expected), hex64(residual), hex64(gate),
                    bool_text(residual <= gate),
                });
            }
            strain_index = 0U;
            for (const auto& strain : mixed_strains()) {
                const auto actual = energy(strain);
                const auto expected = expected_isotropic_energy(strain, bulk, shear);
                const auto residual = std::abs(actual - expected);
                const auto gate = tolerance(
                    cubature.packets.size(), cubature.relations.size(), 65536.0,
                    std::max(actual, expected));
                minimum_energy = std::min(minimum_energy, actual);
                tangent_pass = tangent_pass && residual <= gate;
                tables.strain.row({
                    control_id,
                    "mixed_" + std::to_string(strain_index++),
                    hex64(actual), hex64(expected), hex64(residual), hex64(gate),
                    bool_text(residual <= gate),
                });
            }
            const auto rotated = rotate_cubature(cubature, rotation);
            const auto rotated_collective =
                constitutive::build_local_collective_energy(
                    rotated.packets, rotated.relations,
                    {.dilatational_coefficient_j_per_m2 = coefficient_a,
                     .deviatoric_coefficient_j_per_m2 = coefficient_b});
            strain_index = 0U;
            std::vector<std::pair<std::string, Matrix3d>> rotation_strains;
            for (const auto& strain : basis) {
                rotation_strains.emplace_back(
                    "kelvin_" + std::to_string(strain_index++), strain);
            }
            strain_index = 0U;
            for (const auto& strain : mixed_strains()) {
                rotation_strains.emplace_back(
                    "mixed_" + std::to_string(strain_index++), strain);
            }
            for (const auto& [strain_id, strain] : rotation_strains) {
                const auto baseline = energy(strain);
                const auto rotated_energy = center_energy(
                    rotated, rotated_collective,
                    rotate_strain(rotation, strain));
                const auto residual = std::abs(rotated_energy - baseline);
                const auto gate = tolerance(
                    cubature.packets.size(), cubature.relations.size(),
                    32768.0, std::max(rotated_energy, baseline));
                tangent_pass = tangent_pass && residual <= gate;
                tables.strain.row({
                    control_id, "rotated_" + strain_id,
                    hex64(rotated_energy), hex64(baseline), hex64(residual),
                    hex64(gate), bool_text(residual <= gate),
                });
            }
            const auto ratio_gate = tolerance(
                cubature.packets.size(), cubature.relations.size(),
                131072.0, std::max(ratio, measured_ratio));
            const auto pass = tangent_pass &&
                std::abs(measured_ratio - ratio) <= ratio_gate &&
                minimum_energy > 0.0 &&
                collective.nonlocal_off_diagonal_count == 0U;
            tables.bulk.row({
                control_id,
                cubature.id,
                "local_incident_collective",
                hex64(ratio),
                hex64(coefficient_a),
                hex64(coefficient_b),
                hex64(cubature.moment_m2),
                hex64(cubature.second_moment),
                hex64(cubature.fourth_coefficient),
                hex64(measured_bulk),
                hex64(measured_shear),
                hex64(measured_ratio),
                hex64((3.0 * measured_bulk - 2.0 * measured_shear) /
                      (2.0 * (3.0 * measured_bulk + measured_shear))),
                hex64(volumetric_deviatoric_cross(tangent)),
                hex64(tangent_symmetry),
                hex64(minimum_energy),
                bool_text(minimum_energy > 0.0),
                bool_text(pass),
            });
            ++counts.bulk_rows;
            counts.bulk_failures += pass ? 0U : 1U;
        }
    }
}

[[nodiscard]] std::vector<constitutive::WeightedRelation> unit_weighted(
    std::span<const BondRelation> relations) {
    std::vector<constitutive::WeightedRelation> result;
    result.reserve(relations.size());
    for (const auto relation : relations) {
        result.push_back({relation, 1.0});
    }
    return result;
}

[[nodiscard]] std::vector<constitutive::PairRelationCoefficient> unit_pair(
    std::span<const BondRelation> relations) {
    std::vector<constitutive::PairRelationCoefficient> result;
    result.reserve(relations.size());
    for (const auto relation : relations) {
        result.push_back({relation, 1.0});
    }
    return result;
}

[[nodiscard]] std::size_t matrix_nnz(const DenseMatrix& matrix) {
    return static_cast<std::size_t>(std::ranges::count_if(
        matrix.entries(), [](double value) { return value != 0.0; }));
}

[[nodiscard]] double distance(Vec3d first, Vec3d second) {
    return mls::experimental::norm(second - first);
}

[[nodiscard]] double maximum_euclidean_coupling(
    const GraphConfiguration& configuration,
    const constitutive::RelationEnergyOperator& model) {
    std::map<std::uint64_t, Vec3d> positions;
    for (const auto& packet : configuration.packets) {
        positions.emplace(packet.id, packet.position_m);
    }
    double result = 0.0;
    for (std::size_t first = 0U; first < model.relations.size(); ++first) {
        for (std::size_t second = first;
             second < model.relations.size(); ++second) {
            if (model.h_j_per_m2(first, second) == 0.0) {
                continue;
            }
            const auto a = model.relations[first];
            const auto b = model.relations[second];
            for (const auto first_id : {a.first_id, a.second_id}) {
                for (const auto second_id : {b.first_id, b.second_id}) {
                    result = std::max(
                        result,
                        distance(positions.at(first_id), positions.at(second_id)));
                }
            }
        }
    }
    return result;
}

[[nodiscard]] double maximum_factor_basis_energy(
    const DenseMatrix& factor, const DenseMatrix& basis) {
    double result = 0.0;
    for (std::size_t column = 0U; column < basis.column_count(); ++column) {
        long double twice_energy = 0.0L;
        for (std::size_t row = 0U; row < factor.row_count(); ++row) {
            long double value = 0.0L;
            for (std::size_t coordinate = 0U;
                 coordinate < factor.column_count(); ++coordinate) {
                value += static_cast<long double>(factor(row, coordinate)) *
                    basis(coordinate, column);
            }
            twice_energy += value * value;
        }
        result = std::max(result, 0.5 * static_cast<double>(twice_energy));
    }
    return result;
}

struct RankResult final {
    std::size_t rank{0U};
    std::size_t nullity{0U};
    double threshold{0.0};
    double minimum_nonzero{0.0};
    bool ambiguous{false};
    std::vector<double> singular_values{};
};

[[nodiscard]] RankResult direct_rank(
    const DenseMatrix& matrix, std::size_t dimension_scale) {
    RankResult result{};
    result.singular_values = kelvin::singular_values(matrix);
    const auto sigma_max = result.singular_values.empty()
        ? 0.0
        : result.singular_values.front();
    result.threshold = 512.0 * static_cast<double>(dimension_scale) *
        std::numeric_limits<double>::epsilon() *
        std::max(sigma_max, std::numeric_limits<double>::min());
    result.minimum_nonzero = std::numeric_limits<double>::infinity();
    for (const auto value : result.singular_values) {
        if (value > 8.0 * result.threshold) {
            ++result.rank;
            result.minimum_nonzero = std::min(result.minimum_nonzero, value);
        } else if (value >= result.threshold / 8.0) {
            result.ambiguous = true;
        }
    }
    result.nullity = matrix.column_count() - result.rank;
    if (!std::isfinite(result.minimum_nonzero)) {
        result.minimum_nonzero = 0.0;
    }
    return result;
}

void emit_graph_controls(std::span<const GraphConfiguration> configurations,
                         Tables& tables, RunCounts& counts) {
    const std::array ratios{1.0 / 3.0, 1.0, 2.0, 10.0};
    for (const auto& configuration : configurations) {
        const auto rigidity = observation::build_bond_rigidity_operator(
            configuration.packets, configuration.relations);
        const auto r_diagnostic = confirmation::analyze_raw_central_rigidity(
            configuration.packets, configuration.relations);
        struct ModelCase final {
            std::string family{};
            double ratio{0.0};
            double coefficient_a{1.0};
            double coefficient_b{1.0};
            constitutive::RelationEnergyOperator model{};
        };
        std::vector<ModelCase> models;
        models.push_back({
            "pair_separable", 5.0 / 3.0, 1.0, 1.0,
            constitutive::build_pair_separable_energy(
                configuration.packets, unit_pair(configuration.relations))});
        for (const auto ratio : ratios) {
            const auto a = 3.0 * ratio / 20.0;
            constexpr auto b = 1.0 / 4.0;
            models.push_back({
                "local_incident_collective", ratio, a, b,
                constitutive::build_local_collective_energy(
                    configuration.packets, unit_weighted(configuration.relations),
                    {.dilatational_coefficient_j_per_m2 = a,
                     .deviatoric_coefficient_j_per_m2 = b})});
        }
        for (const auto& entry : models) {
            const auto lr = constitutive::assemble_energy_factor_times_rigidity(
                rigidity, entry.model);
            const auto dimension = std::max(
                {std::size_t{6}, 3U * configuration.packets.size(),
                 configuration.relations.size()});
            const auto lr_rank = direct_rank(lr.matrix, dimension);
            const auto packet_hessian = constitutive::assemble_packet_energy_hessian(
                rigidity, entry.model);
            const auto h_symmetry = constitutive::maximum_symmetry_residual(
                entry.model.h_j_per_m2);
            const auto k_symmetry = constitutive::maximum_symmetry_residual(
                packet_hessian);
            const auto h_lower = entry.family == "pair_separable"
                ? 1.0
                : 2.0 * std::min(entry.coefficient_a, entry.coefficient_b);
            const auto h_upper = entry.family == "pair_separable"
                ? 1.0
                : 2.0 * std::max(entry.coefficient_a, entry.coefficient_b);
            const auto rigid_energy = maximum_factor_basis_energy(
                lr.matrix, r_diagnostic.rigid.orthonormal_basis);
            const auto null_energy = maximum_factor_basis_energy(
                lr.matrix, r_diagnostic.cpqr.nullspace_basis);
            const auto r_nonrigid = r_diagnostic.nonrigid_nullity;
            const auto lr_nonrigid = lr_rank.nullity >=
                    r_diagnostic.realized_rigid_rank
                ? lr_rank.nullity - r_diagnostic.realized_rigid_rank
                : std::numeric_limits<std::size_t>::max();
            const auto symmetry_gate = tolerance(
                configuration.packets.size(), configuration.relations.size(),
                32768.0);
            const auto energy_gate = tolerance(
                configuration.packets.size(), configuration.relations.size(),
                65536.0, std::max(1.0, h_upper));
            const auto nnz = matrix_nnz(entry.model.h_j_per_m2);
            const auto matrix_entries = configuration.relations.size() *
                configuration.relations.size();
            const auto density = matrix_entries == 0U
                ? 0.0
                : static_cast<double>(nnz) /
                    static_cast<double>(matrix_entries);
            const auto kernel_equal = !lr_rank.ambiguous &&
                lr_rank.rank == r_diagnostic.svd_rank &&
                lr_rank.nullity == r_diagnostic.nullity &&
                lr_nonrigid == r_nonrigid;
            const auto pass =
                r_diagnostic.status == observation::RankStatus::analyzed &&
                r_diagnostic.direct_svd_unambiguous && !lr_rank.ambiguous &&
                kernel_equal && h_symmetry <= symmetry_gate &&
                k_symmetry <= symmetry_gate && h_lower > 0.0 &&
                entry.model.nonlocal_off_diagonal_count == 0U &&
                rigid_energy <= energy_gate && null_energy <= energy_gate &&
                (configuration.intentionally_floppy
                     ? lr_nonrigid == 1U
                     : lr_nonrigid == 0U);
            tables.graph.row({
                configuration.id,
                entry.family,
                hex64(entry.ratio),
                std::to_string(configuration.packets.size()),
                std::to_string(configuration.relations.size()),
                std::to_string(r_diagnostic.svd_rank),
                std::to_string(r_diagnostic.nullity),
                std::to_string(r_nonrigid),
                std::to_string(lr_rank.rank),
                std::to_string(lr_rank.nullity),
                std::to_string(lr_nonrigid),
                hex64(lr_rank.threshold),
                bool_text(lr_rank.ambiguous),
                hex64(h_symmetry),
                hex64(k_symmetry),
                hex64(h_lower),
                hex64(h_upper),
                bool_text(h_lower > 0.0),
                std::to_string(nnz),
                hex64(density),
                std::to_string(entry.model.nonlocal_off_diagonal_count),
                entry.family == "pair_separable" ? "0" : "1",
                hex64(maximum_euclidean_coupling(configuration, entry.model)),
                hex64(rigid_energy),
                hex64(null_energy),
                hex64(lr_rank.minimum_nonzero),
                bool_text(kernel_equal),
                bool_text(pass),
            });
            for (std::size_t index = 0U;
                 index < lr_rank.singular_values.size(); ++index) {
                const auto value = lr_rank.singular_values[index];
                const auto classification = value > 8.0 * lr_rank.threshold
                    ? "accepted_nonzero"
                    : (value < lr_rank.threshold / 8.0 ? "resolved_zero"
                                                       : "ambiguous");
                tables.spectra.row({
                    configuration.id,
                    entry.family,
                    hex64(entry.ratio),
                    std::to_string(index),
                    hex64(value),
                    hex64(lr_rank.threshold),
                    classification,
                });
            }
            ++counts.graph_rows;
            counts.graph_failures += pass ? 0U : 1U;
        }
    }
}

[[nodiscard]] Matrix3d finite_deformation() {
    Matrix3d result{};
    result.value = {{{21.0 / 20.0, 1.0 / 20.0, -1.0 / 40.0},
                     {0.0, 19.0 / 20.0, 1.0 / 25.0},
                     {1.0 / 50.0, 0.0, 11.0 / 10.0}}};
    return result;
}

[[nodiscard]] Matrix3d axis_angle_rotation() {
    const Vec3d axis_raw{1.0, 2.0, 3.0};
    const auto axis = axis_raw / mls::experimental::norm(axis_raw);
    constexpr auto angle = 0.731;
    const auto c = std::cos(angle);
    const auto s = std::sin(angle);
    const auto one_minus_c = 1.0 - c;
    Matrix3d result{};
    result.value = {{{
        c + axis.x * axis.x * one_minus_c,
        axis.x * axis.y * one_minus_c - axis.z * s,
        axis.x * axis.z * one_minus_c + axis.y * s}, {
        axis.y * axis.x * one_minus_c + axis.z * s,
        c + axis.y * axis.y * one_minus_c,
        axis.y * axis.z * one_minus_c - axis.x * s}, {
        axis.z * axis.x * one_minus_c - axis.y * s,
        axis.z * axis.y * one_minus_c + axis.x * s,
        c + axis.z * axis.z * one_minus_c}}};
    return result;
}

[[nodiscard]] std::vector<MechanicalPacket> transform_packets(
    std::span<const MechanicalPacket> packets, const Matrix3d& map,
    Vec3d translation) {
    std::vector<MechanicalPacket> result(packets.begin(), packets.end());
    for (auto& packet : result) {
        packet.position_m =
            mls::experimental::multiply(map, packet.position_m) + translation;
    }
    return result;
}

[[nodiscard]] std::vector<std::uint64_t> ordered_ids(
    std::span<const MechanicalPacket> packets) {
    std::vector<std::uint64_t> result;
    for (const auto& packet : packets) {
        result.push_back(packet.id);
    }
    std::ranges::sort(result);
    return result;
}

[[nodiscard]] std::map<std::uint64_t, std::uint64_t> id_mapping(
    std::span<const MechanicalPacket> packets, std::string_view kind) {
    const auto ids = ordered_ids(packets);
    auto targets = ids;
    if (kind == "id_reverse") {
        std::ranges::reverse(targets);
    } else if (kind == "id_cycle") {
        std::ranges::rotate(targets, targets.begin() + 1);
    } else if (kind == "id_sha256") {
        std::ranges::sort(targets, [](auto lhs, auto rhs) {
            return sha256(std::to_string(seed) + "|" + std::to_string(lhs)) <
                sha256(std::to_string(seed) + "|" + std::to_string(rhs));
        });
        if (targets == ids && targets.size() > 1U) {
            std::ranges::rotate(targets, targets.begin() + 1);
        }
    } else {
        throw std::invalid_argument("unknown ID mapping");
    }
    std::map<std::uint64_t, std::uint64_t> result;
    for (std::size_t index = 0U; index < ids.size(); ++index) {
        result.emplace(ids[index], targets[index]);
    }
    return result;
}

void rename(std::vector<MechanicalPacket>& packets,
            std::vector<BondRelation>& relations,
            const std::map<std::uint64_t, std::uint64_t>& mapping) {
    for (auto& packet : packets) {
        packet.id = mapping.at(packet.id);
    }
    for (auto& relation : relations) {
        relation.first_id = mapping.at(relation.first_id);
        relation.second_id = mapping.at(relation.second_id);
    }
}

[[nodiscard]] constitutive::RelationEnergyOperator build_model(
    std::string_view family, std::span<const MechanicalPacket> packets,
    std::span<const BondRelation> relations) {
    if (family == "pair_separable") {
        return constitutive::build_pair_separable_energy(
            packets, unit_pair(relations));
    }
    return constitutive::build_local_collective_energy(
        packets, unit_weighted(relations),
        {.dilatational_coefficient_j_per_m2 = 3.0 / 10.0,
         .deviatoric_coefficient_j_per_m2 = 1.0 / 4.0});
}

[[nodiscard]] double finite_energy(
    std::string_view family,
    std::span<const MechanicalPacket> reference,
    std::span<const MechanicalPacket> current,
    std::span<const BondRelation> relations) {
    const auto model = build_model(family, reference, relations);
    const auto evaluated = constitutive::evaluate_finite_energy(
        model, reference, current);
    if (!evaluated.finite) {
        throw std::runtime_error("finite energy evaluation failed");
    }
    return evaluated.total_j;
}

class SplitMix64 final {
public:
    explicit SplitMix64(std::uint64_t value) noexcept : state_(value) {}
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

template <typename Value>
void deterministic_shuffle(std::vector<Value>& values, std::uint64_t salt) {
    SplitMix64 random(seed ^ salt);
    for (std::size_t index = values.size(); index > 1U; --index) {
        const auto selected = static_cast<std::size_t>(
            random.next() % static_cast<std::uint64_t>(index));
        std::swap(values[index - 1U], values[selected]);
    }
}

void emit_metamorphic_controls(
    std::span<const GraphConfiguration> configurations,
    Tables& tables, RunCounts& counts) {
    const auto deformation = finite_deformation();
    const auto rotation = axis_angle_rotation();
    const Vec3d translation{7.0 / 13.0, -5.0 / 11.0, 3.0 / 17.0};
    const std::array<std::string_view, 2> families{
        "pair_separable", "local_incident_collective"};
    for (const auto& configuration : configurations) {
        const auto current = transform_packets(
            configuration.packets, deformation, {});
        for (const auto family : families) {
            const auto baseline = finite_energy(
                family, configuration.packets, current,
                configuration.relations);
            struct Probe final {
                std::string id{};
                std::vector<MechanicalPacket> reference{};
                std::vector<MechanicalPacket> current{};
                std::vector<BondRelation> relations{};
                double expected_ratio{1.0};
            };
            std::vector<Probe> probes;
            probes.push_back({"translation",
                transform_packets(configuration.packets, Matrix3d::identity(),
                                  translation),
                transform_packets(current, Matrix3d::identity(), translation),
                configuration.relations, 1.0});
            probes.push_back({"rotation",
                transform_packets(configuration.packets, rotation, {}),
                transform_packets(current, rotation, {}),
                configuration.relations, 1.0});
            probes.push_back({"rotation_translation",
                transform_packets(configuration.packets, rotation, translation),
                transform_packets(current, rotation, translation),
                configuration.relations, 1.0});
            for (const auto scale : {0.5, 2.0}) {
                Matrix3d scale_map = Matrix3d::identity();
                for (std::size_t axis = 0U; axis < 3U; ++axis) {
                    scale_map.value[axis][axis] = scale;
                }
                probes.push_back({"scale_" + hex64(scale),
                    transform_packets(configuration.packets, scale_map, {}),
                    transform_packets(current, scale_map, {}),
                    configuration.relations, scale * scale});
            }
            {
                auto reference = configuration.packets;
                auto transformed = current;
                std::ranges::reverse(reference);
                std::ranges::reverse(transformed);
                probes.push_back({"packet_reverse", std::move(reference),
                                  std::move(transformed),
                                  configuration.relations, 1.0});
            }
            {
                auto reference = configuration.packets;
                auto transformed = current;
                deterministic_shuffle(reference, 1U);
                deterministic_shuffle(transformed, 1U);
                probes.push_back({"packet_splitmix", std::move(reference),
                                  std::move(transformed),
                                  configuration.relations, 1.0});
            }
            {
                auto relations = configuration.relations;
                std::ranges::reverse(relations);
                probes.push_back({"relation_reverse", configuration.packets,
                                  current, std::move(relations), 1.0});
            }
            {
                auto relations = configuration.relations;
                deterministic_shuffle(relations, 2U);
                probes.push_back({"relation_splitmix", configuration.packets,
                                  current, std::move(relations), 1.0});
            }
            {
                auto relations = configuration.relations;
                for (std::size_t index = 0U; index < relations.size();
                     index += 2U) {
                    std::swap(relations[index].first_id,
                              relations[index].second_id);
                }
                probes.push_back({"relation_endpoint_reverse",
                                  configuration.packets, current,
                                  std::move(relations), 1.0});
            }
            for (const auto kind : {"id_reverse", "id_cycle", "id_sha256"}) {
                auto reference = configuration.packets;
                auto transformed = current;
                auto relations = configuration.relations;
                const auto mapping = id_mapping(reference, kind);
                rename(reference, relations, mapping);
                auto ignored_relations = configuration.relations;
                rename(transformed, ignored_relations, mapping);
                probes.push_back({kind, std::move(reference),
                                  std::move(transformed), std::move(relations),
                                  1.0});
            }
            for (const auto& probe : probes) {
                const auto actual_energy = finite_energy(
                    family, probe.reference, probe.current, probe.relations);
                const auto actual_ratio = baseline == 0.0
                    ? (actual_energy == 0.0 ? probe.expected_ratio : 0.0)
                    : actual_energy / baseline;
                const auto residual =
                    std::abs(actual_ratio - probe.expected_ratio);
                const auto gate = tolerance(
                    configuration.packets.size(), configuration.relations.size(),
                    32768.0,
                    std::max(std::abs(actual_ratio), probe.expected_ratio));
                const auto pass = residual <= gate;
                tables.metamorphic.row({
                    configuration.id,
                    std::string(family),
                    probe.id,
                    hex64(baseline),
                    hex64(actual_energy),
                    hex64(probe.expected_ratio),
                    hex64(actual_ratio),
                    hex64(residual),
                    hex64(gate),
                    bool_text(pass),
                });
                ++counts.metamorphic_rows;
                counts.metamorphic_failures += pass ? 0U : 1U;
            }
        }
    }
}

[[nodiscard]] std::string hash_bytes(
    std::span<const std::uint8_t> bytes) {
    return sha256(std::string_view(
        reinterpret_cast<const char*>(bytes.data()), bytes.size()));
}

void emit_checkpoints(
    std::span<const GraphConfiguration> configurations,
    Tables& tables, RunCounts& counts,
    std::map<std::string, std::vector<std::uint8_t>>& checkpoint_payloads) {
    for (const auto& configuration : configurations) {
        observation::MechanicalObservabilityState state{};
        state.packets = configuration.packets;
        state.bonds = configuration.relations;
        const auto rigidity = observation::build_bond_rigidity_operator(
            state.packets, state.bonds);
        state.support_radius_m = *std::ranges::max_element(rigidity.lengths_m);
        const auto bytes =
            observation::serialize_mechanical_observability_state(state);
        const auto before = hash_bytes(bytes);
        const auto restored = observation::deserialize_mechanical_observability_state(
            bytes);
        const auto roundtrip =
            observation::serialize_mechanical_observability_state(restored);
        const auto after = hash_bytes(roundtrip);
        const auto exact = bytes == roundtrip && state == restored;
        // Read-only diagnostics are run after serialization; their result may
        // not alter the authoritative input checkpoint.
        static_cast<void>(confirmation::analyze_raw_central_rigidity(
            state.packets, state.bonds));
        const auto after_diagnostic =
            observation::serialize_mechanical_observability_state(state);
        const auto read_only = after_diagnostic == bytes;
        const auto pass = exact && read_only && before == after;
        checkpoint_payloads.emplace(
            "checkpoints/" + configuration.id + ".bin", bytes);
        tables.checkpoints.row({
            configuration.id,
            std::to_string(bytes.size()),
            before,
            after,
            bool_text(exact),
            bool_text(read_only),
            bool_text(pass),
        });
        ++counts.checkpoint_rows;
        counts.checkpoint_failures += pass ? 0U : 1U;
    }
}

[[nodiscard]] std::string summary_json(
    const RunCounts& counts, bool smoke, std::string_view decision) {
    std::ostringstream output;
    output << "{\n"
           << "  \"schema\": \"" << summary_schema << "\",\n"
           << "  \"seed\": " << seed << ",\n"
           << "  \"smoke\": " << bool_text(smoke) << ",\n"
           << "  \"decision\": \"" << decision << "\",\n"
           << "  \"no_promotion\": true,\n"
           << "  \"candidate_b_decision_inputs\": 0,\n"
           << "  \"candidate_d_decision_inputs\": 0,\n"
           << "  \"dense_global_rows\": 0,\n"
           << "  \"bulk_rows\": " << counts.bulk_rows << ",\n"
           << "  \"bulk_failures\": " << counts.bulk_failures << ",\n"
           << "  \"graph_rows\": " << counts.graph_rows << ",\n"
           << "  \"graph_failures\": " << counts.graph_failures << ",\n"
           << "  \"metamorphic_rows\": " << counts.metamorphic_rows << ",\n"
           << "  \"metamorphic_failures\": "
           << counts.metamorphic_failures << ",\n"
           << "  \"checkpoint_rows\": " << counts.checkpoint_rows << ",\n"
           << "  \"checkpoint_failures\": "
           << counts.checkpoint_failures << ",\n"
           << "  \"prohibited_features\": {\n"
           << "    \"motion_integration\": false,\n"
           << "    \"runtime_force_application\": false,\n"
           << "    \"stress\": false,\n"
           << "    \"contact\": false,\n"
           << "    \"damage_or_fracture\": false,\n"
           << "    \"gravity\": false,\n"
           << "    \"chemistry\": false,\n"
           << "    \"organisms\": false,\n"
           << "    \"rendering\": false,\n"
           << "    \"gpu\": false\n"
           << "  }\n"
           << "}\n";
    return output.str();
}

[[nodiscard]] std::string provenance_json(
    bool smoke, const std::map<std::string, std::string>& fixture_hashes) {
    const auto hash_or = [&](std::string_view name) {
        const auto found = fixture_hashes.find(std::string(name));
        return found == fixture_hashes.end() ? std::string("builtin_smoke")
                                             : found->second;
    };
    std::ostringstream output;
    output << "{\n"
           << "  \"parent_sha\": \"" << parent_sha << "\",\n"
           << "  \"exact_oracle_pre_hash\": "
              "\"463fd3f58c5ab5693207ed1a127300434bd76f6d03074f7217fd50e5511ad3d2\",\n"
           << "  \"source_sha\": \"" << MLS_CONFIGURED_SOURCE_SHA << "\",\n"
           << "  \"source_branch\": \"" << MLS_CONFIGURED_SOURCE_BRANCH
           << "\",\n"
           << "  \"expected_branch\": \"" << branch << "\",\n"
           << "  \"source_dirty\": " << MLS_CONFIGURED_SOURCE_DIRTY << ",\n"
           << "  \"compiler_id\": \"" << MLS_CONFIGURED_COMPILER_ID << "\",\n"
           << "  \"compiler_version\": \"" << MLS_CONFIGURED_COMPILER_VERSION
           << "\",\n"
           << "  \"smoke\": " << bool_text(smoke) << ",\n"
           << "  \"inherited_blobs\": {\n"
           << "    \"include/mls/mechanical_observability_lab.hpp\": "
              "\"e5007f63ff4984dd5e6fbbb027a26f319cc02e5c\",\n"
           << "    \"src/mechanical_observability_lab.cpp\": "
              "\"9ed0ab945a4178286c59aad9e8f9fd9eb1ac8c87\",\n"
           << "    \"src/kelvin_covariance_audit.cpp\": "
              "\"bcdad1a3edaf9fbf4528438f720261141333b394\"\n"
           << "  },\n"
           << "  \"fixture_sha256\": {\n"
           << "    \"configurations.csv\": \""
           << hash_or("configurations.csv") << "\",\n"
           << "    \"packets.csv\": \"" << hash_or("packets.csv")
           << "\",\n"
           << "    \"relations.csv\": \"" << hash_or("relations.csv")
           << "\"\n"
           << "  }\n"
           << "}\n";
    return output.str();
}

[[nodiscard]] std::string manifest_json(
    const std::map<std::string, std::string>& hashes) {
    std::ostringstream preimage;
    for (const auto& [name, digest] : hashes) {
        preimage << name << '\0' << digest << '\n';
    }
    std::ostringstream output;
    output << "{\n  \"schema\": \"" << manifest_schema << "\",\n"
           << "  \"file_sha256\": {\n";
    std::size_t index = 0U;
    for (const auto& [name, digest] : hashes) {
        output << "    \"" << name << "\": \"" << digest << "\""
               << (++index == hashes.size() ? "\n" : ",\n");
    }
    output << "  },\n  \"pre_hash_sha256\": \""
           << sha256(preimage.str()) << "\"\n}\n";
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
        std::cout << "Constitutive Expressivity schema audit: PASS\n";
        return 0;
    }
    FixtureInput input{};
    if (arguments.smoke) {
        input.configurations = smoke_graphs();
    } else {
        input = load_fixture_bundle(arguments.fixture_bundle);
    }
    Tables tables{};
    RunCounts counts{};
    emit_selected_inputs(input.configurations, tables);
    emit_bulk_controls(tables, counts);
    emit_graph_controls(input.configurations, tables, counts);
    emit_metamorphic_controls(input.configurations, tables, counts);
    std::map<std::string, std::vector<std::uint8_t>> checkpoint_payloads;
    emit_checkpoints(
        input.configurations, tables, counts, checkpoint_payloads);
    const auto all_green = counts.bulk_failures == 0U &&
        counts.graph_failures == 0U && counts.metamorphic_failures == 0U &&
        counts.checkpoint_failures == 0U;
    const std::string decision = all_green
        ? "retain_local_collective_relational_energy_for_research"
        : "stop_inconclusive_or_implementation_failure";

    std::filesystem::create_directories(arguments.output);
    std::map<std::string, std::string> payloads{
        {"configurations.csv", tables.configurations.contents()},
        {"packets.csv", tables.packets.contents()},
        {"relations.csv", tables.relations.contents()},
        {"bulk_expressivity.csv", tables.bulk.contents()},
        {"tangent.csv", tables.tangent.contents()},
        {"strain_energy.csv", tables.strain.contents()},
        {"graph_energy.csv", tables.graph.contents()},
        {"spectra.csv", tables.spectra.contents()},
        {"metamorphic.csv", tables.metamorphic.contents()},
        {"checkpoints.csv", tables.checkpoints.contents()},
        {"summary.json", summary_json(counts, arguments.smoke, decision)},
        {"provenance.json", provenance_json(arguments.smoke, input.hashes)},
    };
    std::map<std::string, std::string> hashes;
    for (const auto& [name, contents] : payloads) {
        write_text(arguments.output / name, contents);
        hashes.emplace(name, sha256(contents));
    }
    std::filesystem::create_directories(arguments.output / "checkpoints");
    for (const auto& [name, bytes] : checkpoint_payloads) {
        write_bytes(arguments.output / name, bytes);
        hashes.emplace(name, hash_bytes(bytes));
    }
    const auto manifest = manifest_json(hashes);
    write_text(arguments.output / "manifest.json", manifest);
    std::cout << "Constitutive Expressivity evidence written: "
              << arguments.output.string() << '\n'
              << "decision=" << decision << " NO_PROMOTION\n";
    return 0;
}

} // namespace

int main(int argc, char** argv) {
    try {
        return run(parse_arguments(argc, argv));
    } catch (const std::exception& error) {
        std::cerr << "Constitutive Expressivity diagnostic failed: "
                  << error.what() << '\n';
        return 1;
    }
}
