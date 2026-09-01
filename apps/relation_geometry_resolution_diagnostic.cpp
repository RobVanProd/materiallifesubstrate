#include "mls/relation_geometry_resolution_lab.hpp"

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
#include <ranges>
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
#ifndef MLS_CONFIGURED_BUILD_TYPE
#define MLS_CONFIGURED_BUILD_TYPE "unknown"
#endif

namespace {

namespace geometry = mls::experimental::relation_geometry_resolution;
namespace force = mls::experimental::conservative_force_consistency;
namespace constitutive = mls::experimental::constitutive_expressivity;
namespace observation = mls::experimental::mechanical_observability;
using mls::experimental::Vec3d;
using observation::BondRelation;
using observation::MechanicalPacket;

static_assert(sizeof(double) == sizeof(std::uint64_t));
static_assert(std::numeric_limits<double>::is_iec559);

constexpr std::string_view accepted_source_sha =
    "7ee2555521b2c3a86ece87fad961500e413244c5";
constexpr std::string_view accepted_evidence_tag =
    "conservative-force-consistency-lab-evidence-v1";
constexpr std::string_view accepted_archive_sha256 =
    "fe6f34cad1e2794ec50ce9df6f2f88ea4f0aca07322f64f78bf003aa4ceb2ca4";
constexpr std::array<std::string_view, 2> selected_configurations{
    "exact.tetrahedron_k4", "exact.octahedron_graph"};
constexpr std::array<int, 13> collapse_exponents{
    0, -4, -8, -12, -16, -20, -24, -28, -32, -36, -40, -44, -48};
constexpr std::array<int, 6> adjacency_ulps{-4, -2, -1, 1, 2, 4};
constexpr std::array<geometry::GeometryPath, 3> paths{
    geometry::GeometryPath::frozen_binary64,
    geometry::GeometryPath::cancellation_resistant_binary64,
    geometry::GeometryPath::transient_double_double};

using Row = std::vector<std::string>;

[[nodiscard]] std::string read_text(const std::filesystem::path& path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        throw std::runtime_error("cannot read input: " + path.string());
    }
    return {std::istreambuf_iterator<char>(stream),
            std::istreambuf_iterator<char>()};
}

void write_text(const std::filesystem::path& path, std::string_view text) {
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    if (!stream) {
        throw std::runtime_error("cannot write output: " + path.string());
    }
    stream.write(text.data(), static_cast<std::streamsize>(text.size()));
    if (!stream) {
        throw std::runtime_error("failed writing output: " + path.string());
    }
}

[[nodiscard]] std::vector<Row> parse_csv(std::string_view input) {
    std::vector<Row> rows;
    Row row;
    std::string field;
    bool quoted = false;
    for (std::size_t index = 0; index < input.size(); ++index) {
        const auto character = input[index];
        if (quoted) {
            if (character == '"' && index + 1U < input.size() &&
                input[index + 1U] == '"') {
                field.push_back('"');
                ++index;
            } else if (character == '"') {
                quoted = false;
            } else {
                field.push_back(character);
            }
        } else if (character == '"') {
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

[[nodiscard]] std::map<std::string, std::size_t> header_map(
    const Row& header) {
    std::map<std::string, std::size_t> result;
    for (std::size_t index = 0; index < header.size(); ++index) {
        result.emplace(header[index], index);
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

[[nodiscard]] double parse_double(std::string_view value) {
    std::string storage(value);
    char* end = nullptr;
    const auto result = std::strtod(storage.c_str(), &end);
    if (end == storage.c_str() || *end != '\0' || !std::isfinite(result)) {
        throw std::runtime_error("invalid binary64 field");
    }
    return result;
}

[[nodiscard]] std::string csv_escape(std::string_view value) {
    if (value.find_first_of(",\"\r\n") == std::string_view::npos) {
        return std::string(value);
    }
    std::string result{"\""};
    for (const auto character : value) {
        if (character == '"') {
            result.push_back('"');
        }
        result.push_back(character);
    }
    result.push_back('"');
    return result;
}

class Csv final {
public:
    explicit Csv(std::string header)
        : header_(std::move(header)),
          width_(static_cast<std::size_t>(
              std::ranges::count(header_, ',')) + 1U) {}

    void row(Row values) {
        if (values.size() != width_) {
            throw std::logic_error("CSV row width mismatch");
        }
        rows_.push_back(std::move(values));
    }

    [[nodiscard]] std::string contents() const {
        std::string result = header_ + '\n';
        for (const auto& row : rows_) {
            for (std::size_t index = 0; index < row.size(); ++index) {
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
    std::size_t width_{0U};
    std::vector<Row> rows_{};
};

[[nodiscard]] std::string bits(double value) {
    return std::to_string(std::bit_cast<std::uint64_t>(value));
}

[[nodiscard]] std::string text(bool value) { return value ? "true" : "false"; }

[[nodiscard]] bool selected_configuration(std::string_view id) {
    return std::ranges::find(selected_configurations, id) !=
        selected_configurations.end();
}

struct Graph final {
    std::string id{};
    std::vector<MechanicalPacket> reference{};
    std::vector<BondRelation> relations{};
    std::vector<double> reference_lengths{};
};

struct Operator final {
    std::string id{};
    std::string configuration_id{};
    double a{0.0};
    double b{0.0};
    force::FrozenForceOperator frozen{};
};

struct Input final {
    std::map<std::string, Graph> graphs{};
    std::vector<Operator> operators{};
};

[[nodiscard]] std::vector<constitutive::WeightedRelation> weighted(
    std::span<const BondRelation> relations) {
    std::vector<constitutive::WeightedRelation> result;
    result.reserve(relations.size());
    for (const auto relation : relations) {
        result.push_back({relation, 1.0});
    }
    return result;
}

[[nodiscard]] Input load_input(const std::filesystem::path& directory) {
    auto packet_rows = parse_csv(read_text(directory / "reference_packets.csv"));
    auto relation_rows = parse_csv(read_text(directory / "relations.csv"));
    auto operator_rows = parse_csv(read_text(directory / "operators.csv"));
    auto h_rows = parse_csv(read_text(directory / "h_matrix.csv"));
    if (packet_rows.empty() || relation_rows.empty() || operator_rows.empty() ||
        h_rows.empty()) {
        throw std::runtime_error("force parent tables are empty");
    }
    const auto ph = header_map(packet_rows.front());
    const auto rh = header_map(relation_rows.front());
    const auto oh = header_map(operator_rows.front());
    const auto hh = header_map(h_rows.front());
    Input result{};
    for (const auto id : selected_configurations) {
        result.graphs.emplace(std::string(id), Graph{std::string(id)});
    }
    for (std::size_t row = 1U; row < packet_rows.size(); ++row) {
        const auto& values = packet_rows[row];
        const auto id = values.at(ph.at("configuration_id"));
        if (!selected_configuration(id)) {
            continue;
        }
        auto& graph = result.graphs.at(id);
        const auto index = parse_integer<std::size_t>(
            values.at(ph.at("packet_index")));
        if (index != graph.reference.size()) {
            throw std::runtime_error("noncanonical reference packet order");
        }
        graph.reference.push_back({
            parse_integer<std::uint64_t>(values.at(ph.at("packet_id"))),
            parse_integer<std::int64_t>(values.at(ph.at("mass_quanta"))),
            {parse_double(values.at(ph.at("x_m"))),
             parse_double(values.at(ph.at("y_m"))),
             parse_double(values.at(ph.at("z_m")))},
            {}});
    }
    for (std::size_t row = 1U; row < relation_rows.size(); ++row) {
        const auto& values = relation_rows[row];
        const auto id = values.at(rh.at("configuration_id"));
        if (!selected_configuration(id)) {
            continue;
        }
        auto& graph = result.graphs.at(id);
        const auto index = parse_integer<std::size_t>(
            values.at(rh.at("relation_index")));
        if (index != graph.relations.size()) {
            throw std::runtime_error("noncanonical relation order");
        }
        graph.relations.push_back({
            parse_integer<std::uint64_t>(values.at(rh.at("first_id"))),
            parse_integer<std::uint64_t>(values.at(rh.at("second_id")))});
        graph.reference_lengths.push_back(
            parse_double(values.at(rh.at("reference_length_m"))));
        if (parse_double(values.at(rh.at("weight"))) != 1.0) {
            throw std::runtime_error("selected relation weight changed");
        }
    }
    for (std::size_t row = 1U; row < operator_rows.size(); ++row) {
        const auto& values = operator_rows[row];
        const auto configuration = values.at(oh.at("configuration_id"));
        if (!selected_configuration(configuration)) {
            continue;
        }
        const auto a = parse_double(values.at(oh.at("a_j_per_m2")));
        const auto b = parse_double(values.at(oh.at("b_j_per_m2")));
        auto& graph = result.graphs.at(configuration);
        const auto parent = constitutive::build_local_collective_energy(
            graph.reference, weighted(graph.relations),
            {.dilatational_coefficient_j_per_m2 = a,
             .deviatoric_coefficient_j_per_m2 = b});
        auto frozen = force::freeze_symmetric_force_operator(parent);
        if (frozen.force_operator.relations != graph.relations ||
            frozen.force_operator.reference_lengths_m !=
                graph.reference_lengths) {
            throw std::runtime_error("rebuilt operator differs from sealed coordinates");
        }
        result.operators.push_back(
            {values.at(oh.at("operator_id")), configuration, a, b,
             std::move(frozen)});
    }
    for (auto& selected : result.operators) {
        const auto count = selected.frozen.force_operator.relations.size();
        std::size_t seen = 0U;
        for (std::size_t row = 1U; row < h_rows.size(); ++row) {
            const auto& values = h_rows[row];
            if (values.at(hh.at("operator_id")) != selected.id) {
                continue;
            }
            const auto r = parse_integer<std::size_t>(
                values.at(hh.at("row_relation_index")));
            const auto c = parse_integer<std::size_t>(
                values.at(hh.at("column_relation_index")));
            if (r >= count || c >= count ||
                selected.frozen.parent_operator.h_j_per_m2(r, c) !=
                    parse_double(values.at(hh.at("parent_value_j_per_m2"))) ||
                selected.frozen.force_operator.h_j_per_m2(r, c) !=
                    parse_double(values.at(hh.at("frozen_value_j_per_m2")))) {
                throw std::runtime_error("rebuilt H differs from sealed H bits");
            }
            ++seen;
        }
        if (seen != count * count) {
            throw std::runtime_error("sealed H inventory is incomplete");
        }
    }
    if (result.operators.size() != 6U) {
        throw std::runtime_error("selected operator inventory is incomplete");
    }
    return result;
}

[[nodiscard]] std::map<std::uint64_t, std::size_t> packet_lookup(
    std::span<const MechanicalPacket> packets) {
    std::map<std::uint64_t, std::size_t> result;
    for (std::size_t index = 0; index < packets.size(); ++index) {
        result.emplace(packets[index].id, index);
    }
    return result;
}

[[nodiscard]] double shift_ulps(double value, int ulps) {
    const auto target = ulps > 0 ? std::numeric_limits<double>::infinity()
                                 : -std::numeric_limits<double>::infinity();
    for (int step = 0; step < std::abs(ulps); ++step) {
        value = std::nextafter(value, target);
    }
    return value;
}

[[nodiscard]] std::size_t registered_axis(Vec3d offset) {
    const std::array components{offset.x, offset.y, offset.z};
    return static_cast<std::size_t>(
        std::ranges::max_element(
            components, {}, [](double value) { return std::abs(value); }) -
        components.begin());
}

[[nodiscard]] double& component(Vec3d& value, std::size_t axis) {
    if (axis == 0U) {
        return value.x;
    }
    if (axis == 1U) {
        return value.y;
    }
    return value.z;
}

struct Spectrum final {
    bool converged{false};
    std::vector<double> singular_values{};
};

[[nodiscard]] Spectrum binary64_singular_values(
    const observation::DenseMatrix& matrix) {
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
            throw std::invalid_argument("condition matrix must be finite");
        }
        maximum_entry = std::max(maximum_entry, std::abs(value));
    }
    if (maximum_entry == 0.0) {
        return {true, std::vector<double>(dimension, 0.0)};
    }
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
                const auto threshold = correlation_factor *
                    std::numeric_limits<double>::epsilon() *
                    std::sqrt(first_norm_squared) *
                    std::sqrt(second_norm_squared);
                if (std::abs(correlation) <= threshold) {
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
        singular_values.push_back(maximum_entry * std::sqrt(squared_norm));
    }
    std::ranges::sort(singular_values, std::greater<>{});
    return {true, std::move(singular_values)};
}

struct Condition final {
    bool resolved{false};
    double estimate{0.0};
    double largest{0.0};
    double smallest_nonzero{0.0};
};

[[nodiscard]] Condition condition(
    const observation::DenseMatrix& matrix) {
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
    if (!(smallest_nonzero > 0.0)) {
        return {};
    }
    return {true, spectrum.singular_values.front() / smallest_nonzero,
            spectrum.singular_values.front(), smallest_nonzero};
}

[[nodiscard]] double force_sensitivity(
    std::span<const force::PacketForce> first,
    std::span<const force::PacketForce> second) {
    if (first.size() != second.size()) {
        throw std::logic_error("force sensitivity inventory mismatch");
    }
    double scale = 0.0;
    for (std::size_t index = 0; index < first.size(); ++index) {
        const auto difference = first[index].force_n - second[index].force_n;
        scale = std::max(
            {scale, std::abs(difference.x), std::abs(difference.y),
             std::abs(difference.z)});
    }
    if (scale == 0.0) {
        return 0.0;
    }
    double sum = 0.0;
    for (std::size_t index = 0; index < first.size(); ++index) {
        const auto difference = first[index].force_n - second[index].force_n;
        for (const auto value :
             std::array{difference.x, difference.y, difference.z}) {
            const auto normalized = value / scale;
            sum += normalized * normalized;
        }
    }
    return scale * std::sqrt(sum);
}

struct Tables final {
    Csv reference_packets{
        "configuration_id,packet_index,packet_id,mass_quanta,x_bits,y_bits,z_bits"};
    Csv relations{
        "configuration_id,relation_index,first_id,second_id,reference_length_bits,weight_bits"};
    Csv operators{
        "operator_id,configuration_id,a_bits,b_bits,relation_count,packet_count"};
    Csv h{
        "operator_id,row_relation_index,column_relation_index,parent_bits,frozen_bits"};
    Csv evaluations{
        "evaluation_id,operator_id,path,probe,parameter,ratio_bits,status,failed_relation_index,energy_bits,condition_resolved,condition_bits,largest_singular_bits,smallest_nonzero_singular_bits,ulp_force_sensitivity_bits,adjacent_length_changed"};
    Csv current_packets{
        "evaluation_id,packet_index,packet_id,x_bits,y_bits,z_bits"};
    Csv geometry{
        "evaluation_id,relation_index,first_id,second_id,status,coordinate_coincident,length_order,current_offset_x_bits,current_offset_y_bits,current_offset_z_bits,current_offset_low_x_bits,current_offset_low_y_bits,current_offset_low_z_bits,current_length_bits,current_length_low_bits,extension_bits,extension_low_bits,direction_x_bits,direction_y_bits,direction_z_bits,direction_low_x_bits,direction_low_y_bits,direction_low_z_bits,squared_difference_bits,squared_difference_low_bits,conjugate_bits"};
    Csv packet_forces{
        "evaluation_id,packet_index,packet_id,force_x_bits,force_y_bits,force_z_bits"};
    Csv tangents{
        "evaluation_id,row_dof,column_dof,material_bits,geometric_bits,total_bits,force_jacobian_bits"};
};

void emit_static_tables(Tables& tables, const Input& input) {
    for (const auto& [id, graph] : input.graphs) {
        for (std::size_t index = 0; index < graph.reference.size(); ++index) {
            const auto& packet = graph.reference[index];
            tables.reference_packets.row(
                {id, std::to_string(index), std::to_string(packet.id),
                 std::to_string(packet.mass_quanta), bits(packet.position_m.x),
                 bits(packet.position_m.y), bits(packet.position_m.z)});
        }
        for (std::size_t index = 0; index < graph.relations.size(); ++index) {
            const auto relation = graph.relations[index];
            tables.relations.row(
                {id, std::to_string(index), std::to_string(relation.first_id),
                 std::to_string(relation.second_id),
                 bits(graph.reference_lengths[index]), bits(1.0)});
        }
    }
    for (const auto& selected : input.operators) {
        const auto& frozen = selected.frozen;
        tables.operators.row(
            {selected.id, selected.configuration_id, bits(selected.a),
             bits(selected.b),
             std::to_string(frozen.force_operator.relations.size()),
             std::to_string(input.graphs.at(selected.configuration_id)
                                .reference.size())});
        const auto count = frozen.force_operator.relations.size();
        for (std::size_t row = 0; row < count; ++row) {
            for (std::size_t column = 0; column < count; ++column) {
                tables.h.row(
                    {selected.id, std::to_string(row), std::to_string(column),
                     bits(frozen.parent_operator.h_j_per_m2(row, column)),
                     bits(frozen.force_operator.h_j_per_m2(row, column))});
            }
        }
    }
}

[[nodiscard]] std::string resolved_status(
    geometry::ResolvedForceStatus status) {
    switch (status) {
    case geometry::ResolvedForceStatus::evaluated:
        return "evaluated";
    case geometry::ResolvedForceStatus::coincident_relation:
        return "coincident_relation";
    case geometry::ResolvedForceStatus::unresolved_noncoincident:
        return "unresolved_noncoincident";
    }
    return "unknown";
}

void emit_evaluation(
    Tables& tables, const Operator& selected, const Graph& graph,
    std::string id, std::string probe, int parameter, double ratio,
    std::span<const MechanicalPacket> current,
    geometry::GeometryPath path) {
    const auto evaluated = geometry::evaluate_resolved_spatial_force(
        selected.frozen, graph.reference, current, path);
    const auto tangent = geometry::evaluate_resolved_spatial_tangent(
        selected.frozen, graph.reference, current, path);
    if (evaluated.status != tangent.status) {
        throw std::runtime_error("force/tangent status disagreement");
    }
    std::string condition_resolved = "not_emitted";
    std::string condition_bits = "not_emitted";
    std::string largest_bits = "not_emitted";
    std::string smallest_bits = "not_emitted";
    std::string sensitivity_bits = "not_emitted";
    std::string adjacent_changed = "not_emitted";
    if (evaluated.status == geometry::ResolvedForceStatus::evaluated) {
        const auto diagnostic = condition(
            tangent.total_energy_hessian_n_per_m);
        condition_resolved = text(diagnostic.resolved);
        if (diagnostic.resolved) {
            condition_bits = bits(diagnostic.estimate);
            largest_bits = bits(diagnostic.largest);
            smallest_bits = bits(diagnostic.smallest_nonzero);
        }
        const auto relation = graph.relations.front();
        const auto lookup = packet_lookup(current);
        const auto first = lookup.at(relation.first_id);
        const auto second = lookup.at(relation.second_id);
        const auto reference_offset = graph.reference[second].position_m -
            graph.reference[first].position_m;
        const auto axis = registered_axis(reference_offset);
        const std::array components{
            reference_offset.x, reference_offset.y, reference_offset.z};
        auto adjacent = std::vector<MechanicalPacket>(
            current.begin(), current.end());
        auto& coordinate = component(adjacent[second].position_m, axis);
        coordinate = std::nextafter(
            coordinate,
            components[axis] >= 0.0
                ? std::numeric_limits<double>::infinity()
                : -std::numeric_limits<double>::infinity());
        const auto adjacent_force = geometry::evaluate_resolved_spatial_force(
            selected.frozen, graph.reference, adjacent, path);
        if (adjacent_force.status != geometry::ResolvedForceStatus::evaluated) {
            throw std::runtime_error("adjacent force unexpectedly unresolved");
        }
        sensitivity_bits = bits(force_sensitivity(
            evaluated.packet_forces, adjacent_force.packet_forces));
        adjacent_changed = text(
            evaluated.relation_coordinates.front().geometry.current_length_m !=
            adjacent_force.relation_coordinates.front().geometry.current_length_m ||
            evaluated.relation_coordinates.front().geometry.extension_m !=
            adjacent_force.relation_coordinates.front().geometry.extension_m ||
            evaluated.relation_coordinates.front().geometry.extension_low_m !=
            adjacent_force.relation_coordinates.front().geometry.extension_low_m ||
            evaluated.relation_coordinates.front().geometry
                    .squared_distance_difference_m2 !=
                adjacent_force.relation_coordinates.front().geometry
                    .squared_distance_difference_m2 ||
            evaluated.relation_coordinates.front().geometry
                    .squared_distance_difference_low_m2 !=
                adjacent_force.relation_coordinates.front().geometry
                    .squared_distance_difference_low_m2 ||
            evaluated.relation_coordinates.front().geometry.exact_length_order !=
            adjacent_force.relation_coordinates.front().geometry.exact_length_order);
    }
    tables.evaluations.row(
        {id, selected.id, std::string(geometry::path_name(path)), probe,
         std::to_string(parameter), bits(ratio),
         resolved_status(evaluated.status),
         evaluated.failed_relation_index == std::numeric_limits<std::size_t>::max()
             ? "none"
             : std::to_string(evaluated.failed_relation_index),
         bits(evaluated.energy_j), condition_resolved, condition_bits,
         largest_bits, smallest_bits, sensitivity_bits, adjacent_changed});
    for (std::size_t index = 0; index < current.size(); ++index) {
        const auto& packet = current[index];
        tables.current_packets.row(
            {id, std::to_string(index), std::to_string(packet.id),
             bits(packet.position_m.x), bits(packet.position_m.y),
             bits(packet.position_m.z)});
    }
    for (const auto& coordinate : evaluated.relation_coordinates) {
        const auto& value = coordinate.geometry;
        tables.geometry.row(
            {id, std::to_string(coordinate.relation_index),
             std::to_string(coordinate.relation.first_id),
             std::to_string(coordinate.relation.second_id),
             std::string(geometry::status_name(value.status)),
             text(value.coordinate_coincident),
             std::string(geometry::order_name(value.exact_length_order)),
             bits(value.current_offset_m.x), bits(value.current_offset_m.y),
             bits(value.current_offset_m.z),
             bits(value.current_offset_low_m.x),
             bits(value.current_offset_low_m.y),
             bits(value.current_offset_low_m.z), bits(value.current_length_m),
             bits(value.current_length_low_m), bits(value.extension_m),
             bits(value.extension_low_m),
             bits(value.direction_first_to_second.x),
             bits(value.direction_first_to_second.y),
             bits(value.direction_first_to_second.z),
             bits(value.direction_low.x), bits(value.direction_low.y),
             bits(value.direction_low.z),
             bits(value.squared_distance_difference_m2),
             bits(value.squared_distance_difference_low_m2),
             bits(coordinate.conjugate_force_n)});
    }
    for (std::size_t index = 0; index < evaluated.packet_forces.size();
         ++index) {
        const auto& packet = evaluated.packet_forces[index];
        tables.packet_forces.row(
            {id, std::to_string(index), std::to_string(packet.packet_id),
             bits(packet.force_n.x), bits(packet.force_n.y),
             bits(packet.force_n.z)});
    }
    if (tangent.status == geometry::ResolvedForceStatus::evaluated) {
        const auto rows = tangent.total_energy_hessian_n_per_m.row_count();
        const auto columns =
            tangent.total_energy_hessian_n_per_m.column_count();
        for (std::size_t row = 0; row < rows; ++row) {
            for (std::size_t column = 0; column < columns; ++column) {
                tables.tangents.row(
                    {id, std::to_string(row), std::to_string(column),
                     bits(tangent.material_energy_hessian_n_per_m(row, column)),
                     bits(tangent.geometric_energy_hessian_n_per_m(row, column)),
                     bits(tangent.total_energy_hessian_n_per_m(row, column)),
                     bits(tangent.force_jacobian_n_per_m(row, column))});
            }
        }
    }
}

void emit_dynamic_tables(Tables& tables, const Input& input) {
    for (const auto& selected : input.operators) {
        const auto& graph = input.graphs.at(selected.configuration_id);
        const auto relation = graph.relations.front();
        const auto lookup = packet_lookup(graph.reference);
        const auto first = lookup.at(relation.first_id);
        const auto second = lookup.at(relation.second_id);
        const auto offset = graph.reference[second].position_m -
            graph.reference[first].position_m;
        if (graph.id == "exact.octahedron_graph") {
            const auto axis = registered_axis(offset);
            for (const auto ulps : adjacency_ulps) {
                auto current = graph.reference;
                auto& coordinate = component(current[second].position_m, axis);
                coordinate = shift_ulps(coordinate, ulps);
                for (const auto path : paths) {
                    const auto id = selected.id + ".adjacency." +
                        std::to_string(ulps) + "." +
                        std::string(geometry::path_name(path));
                    emit_evaluation(
                        tables, selected, graph, id, "adjacency", ulps, 1.0,
                        current, path);
                }
            }
        }
        for (const auto exponent : collapse_exponents) {
            const auto ratio = std::ldexp(1.0, exponent);
            auto current = graph.reference;
            current[second].position_m =
                current[first].position_m + ratio * offset;
            for (const auto path : paths) {
                const auto id = selected.id + ".collapse." +
                    std::to_string(exponent) + "." +
                    std::string(geometry::path_name(path));
                emit_evaluation(
                    tables, selected, graph, id, "collapse", exponent, ratio,
                    current, path);
            }
        }
        auto coincident = graph.reference;
        coincident[second].position_m = coincident[first].position_m;
        for (const auto path : paths) {
            const auto id = selected.id + ".coincident." +
                std::string(geometry::path_name(path));
            emit_evaluation(
                tables, selected, graph, id, "coincident", 0, 0.0,
                coincident, path);
        }
    }
}

struct Arguments final {
    std::filesystem::path force_bundle{};
    std::filesystem::path output{};
};

[[nodiscard]] Arguments arguments(int argc, char** argv) {
    Arguments result{};
    for (int index = 1; index < argc; ++index) {
        const std::string_view argument = argv[index];
        if (argument == "--force-bundle" && index + 1 < argc) {
            result.force_bundle = argv[++index];
        } else if (argument == "--output" && index + 1 < argc) {
            result.output = argv[++index];
        } else {
            throw std::invalid_argument("unrecognized or incomplete argument");
        }
    }
    if (result.force_bundle.empty() || result.output.empty()) {
        throw std::invalid_argument("--force-bundle and --output are required");
    }
    return result;
}

} // namespace

int main(int argc, char** argv) {
    try {
        std::locale::global(std::locale::classic());
        const auto options = arguments(argc, argv);
        const auto input = load_input(options.force_bundle);
        Tables tables{};
        emit_static_tables(tables, input);
        emit_dynamic_tables(tables, input);
        std::filesystem::create_directories(options.output);
        write_text(options.output / "reference_packets_bits.csv",
                   tables.reference_packets.contents());
        write_text(options.output / "relations_bits.csv",
                   tables.relations.contents());
        write_text(options.output / "operators_bits.csv",
                   tables.operators.contents());
        write_text(options.output / "h_bits.csv", tables.h.contents());
        write_text(options.output / "evaluations.csv",
                   tables.evaluations.contents());
        write_text(options.output / "current_packets_bits.csv",
                   tables.current_packets.contents());
        write_text(options.output / "geometry_bits.csv",
                   tables.geometry.contents());
        write_text(options.output / "packet_forces_bits.csv",
                   tables.packet_forces.contents());
        write_text(options.output / "tangents_bits.csv",
                   tables.tangents.contents());
        std::ostringstream provenance;
        provenance << "{\n"
                   << "  \"schema\": \"mls.relation-geometry-resolution.raw.v1\",\n"
                   << "  \"accepted_source_sha\": \"" << accepted_source_sha
                   << "\",\n"
                   << "  \"accepted_evidence_tag\": \"" << accepted_evidence_tag
                   << "\",\n"
                   << "  \"accepted_archive_sha256\": \""
                   << accepted_archive_sha256 << "\",\n"
                   << "  \"build_source_sha\": \"" << MLS_CONFIGURED_SOURCE_SHA
                   << "\",\n"
                   << "  \"build_branch\": \"" << MLS_CONFIGURED_SOURCE_BRANCH
                   << "\",\n"
                   << "  \"build_dirty\": " << MLS_CONFIGURED_SOURCE_DIRTY
                   << ",\n"
                   << "  \"compiler_id\": \"" << MLS_CONFIGURED_COMPILER_ID
                   << "\",\n"
                   << "  \"compiler_version\": \""
                   << MLS_CONFIGURED_COMPILER_VERSION << "\",\n"
                   << "  \"build_type\": \"" << MLS_CONFIGURED_BUILD_TYPE
                   << "\",\n"
                   << "  \"promotion\": \"NO_PROMOTION\"\n"
                   << "}\n";
        write_text(options.output / "provenance.json", provenance.str());
        std::cout << "RELATION GEOMETRY RAW BUNDLE COMPLETE\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "relation geometry diagnostic failed: " << error.what()
                  << '\n';
        return 1;
    }
}
