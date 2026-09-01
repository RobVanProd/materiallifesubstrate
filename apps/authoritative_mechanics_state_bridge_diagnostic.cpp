#include "mls/authoritative_mechanics_state_bridge_lab.hpp"
#include "mls/constitutive_expressivity_lab.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <initializer_list>
#include <iostream>
#include <limits>
#include <map>
#include <span>
#include <sstream>
#include <stdexcept>
#include <string>
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

namespace bridge =
    mls::experimental::authoritative_mechanics_state_bridge;
namespace constitutive = mls::experimental::constitutive_expressivity;
namespace force = mls::experimental::conservative_force_consistency;
namespace geometry = mls::experimental::relation_geometry_resolution;
namespace observation = mls::experimental::mechanical_observability;
using mls::Length;
using mls::Mass;
using mls::Time;
using mls::experimental::Vec3d;

constexpr auto accepted_parent_sha =
    "2cc26e9a6e2aff8f40dec9787fe7e6e0e6b63f21";
constexpr auto accepted_parent_tag =
    "relation-geometry-resolution-lab-evidence-v1";
constexpr auto accepted_parent_tag_object =
    "ea423e350908b3446b754f7fb75457ca78313cde";
constexpr auto branch = "authoritative-mechanics-state-bridge-lab";
constexpr auto decision =
    "retain_direct_quantized_mechanics_bridge_for_research";

class Csv final {
public:
    explicit Csv(std::string header) : text_(std::move(header) + "\n") {}

    void row(std::initializer_list<std::string> values) {
        row(std::span<const std::string>(values.begin(), values.size()));
    }

    void row(std::span<const std::string> values) {
        for (std::size_t index = 0; index < values.size(); ++index) {
            if (index != 0U) {
                text_ += ',';
            }
            if (values[index].find_first_of(",\"\n") != std::string::npos) {
                text_ += '"';
                for (const auto character : values[index]) {
                    if (character == '"') {
                        text_ += '"';
                    }
                    text_ += character;
                }
                text_ += '"';
            } else {
                text_ += values[index];
            }
        }
        text_ += '\n';
    }

    void write(const std::filesystem::path& path) const {
        std::ofstream stream(path, std::ios::binary);
        if (!stream) {
            throw std::runtime_error("cannot write bridge evidence file");
        }
        stream << text_;
        if (!stream) {
            throw std::runtime_error("cannot complete bridge evidence file");
        }
    }

    [[nodiscard]] const std::string& text() const noexcept { return text_; }

private:
    std::string text_;
};

[[nodiscard]] std::string bits(double value) {
    return std::to_string(std::bit_cast<std::uint64_t>(value));
}

[[nodiscard]] std::string boolean(bool value) {
    return value ? "true" : "false";
}

[[nodiscard]] std::string rational(bridge::PositiveRational value) {
    return std::to_string(value.numerator) + "/" +
        std::to_string(value.denominator);
}

[[nodiscard]] std::vector<bridge::AuthoritativePacket> base_packets() {
    return {
        {1, {}, {}, Mass::from_raw(1)},
        {2, {Length::from_raw(1'001'000'000), {}, {}}, {}, Mass::from_raw(1)},
        {3, {{}, Length::from_raw(1'001'000'000), {}}, {}, Mass::from_raw(1)},
        {4, {{}, {}, Length::from_raw(1'001'000'000)}, {}, Mass::from_raw(1)},
    };
}

[[nodiscard]] std::vector<observation::MechanicalPacket> reference_packets() {
    return {
        {1, 1, {0.0, 0.0, 0.0}, {}},
        {2, 1, {1.0, 0.0, 0.0}, {}},
        {3, 1, {0.0, 1.0, 0.0}, {}},
        {4, 1, {0.0, 0.0, 1.0}, {}},
    };
}

[[nodiscard]] std::vector<observation::BondRelation> relations() {
    return {{1, 2}, {1, 3}, {1, 4}, {2, 3}, {2, 4}, {3, 4}};
}

[[nodiscard]] std::vector<constitutive::WeightedRelation> weighted_relations() {
    std::vector<constitutive::WeightedRelation> result;
    for (const auto relation : relations()) {
        result.push_back({relation, 1.0});
    }
    return result;
}

[[nodiscard]] std::vector<observation::MechanicalPacket> current_packets(
    std::span<const bridge::AuthoritativePacket> packets) {
    const auto units = bridge::mechanics_unit_contract(1);
    std::vector<observation::MechanicalPacket> result;
    for (const auto& packet : packets) {
        const auto mapped = bridge::map_packet_to_binary64_si(packet, units);
        result.push_back({packet.id, packet.mass.raw(), mapped.position_m, {}});
    }
    return result;
}

[[nodiscard]] const bridge::AuthoritativePacket& packet_by_id(
    std::span<const bridge::AuthoritativePacket> packets, std::uint64_t id) {
    const auto found = std::ranges::find(packets, id, &bridge::AuthoritativePacket::id);
    if (found == packets.end()) {
        throw std::runtime_error("bridge packet identity absent");
    }
    return *found;
}

[[nodiscard]] Vec3d relation_force_to_first(
    const geometry::ResolvedRelationForceCoordinate& coordinate) {
    return coordinate.conjugate_force_n *
        coordinate.geometry.direction_first_to_second;
}

struct EvaluationRow final {
    std::size_t relation_index{0};
    bridge::CentralImpulseEvaluation value{};
};

struct SummaryRow final {
    std::uint32_t refinement{1};
    double maximum_error_base_quanta{0.0};
    double subdivision_spread_base_quanta{0.0};
    double maximum_floor_residual_j{0.0};
    bool passes{false};
};

[[nodiscard]] std::vector<SummaryRow> summarize(
    const std::vector<EvaluationRow>& evaluations) {
    constexpr std::array refinements{1U, 2U, 4U, 8U, 16U};
    const auto base_units = bridge::mechanics_unit_contract(1);
    const auto base_pq =
        static_cast<double>(base_units.momentum_quantum_kg_m_per_s.numerator) /
        static_cast<double>(base_units.momentum_quantum_kg_m_per_s.denominator);
    std::vector<SummaryRow> result;
    for (const auto refinement : refinements) {
        SummaryRow summary{};
        summary.refinement = refinement;
        for (std::size_t relation = 0; relation < 6U; ++relation) {
            std::array<double, 3> minimum{
                std::numeric_limits<double>::infinity(),
                std::numeric_limits<double>::infinity(),
                std::numeric_limits<double>::infinity()};
            std::array<double, 3> maximum{
                -std::numeric_limits<double>::infinity(),
                -std::numeric_limits<double>::infinity(),
                -std::numeric_limits<double>::infinity()};
            for (const auto& row : evaluations) {
                if (row.relation_index != relation ||
                    row.value.refinement != refinement ||
                    row.value.path != bridge::QuantizationPath::fixed_point_refinement) {
                    continue;
                }
                const std::array target{
                    row.value.target_impulse_kg_m_per_s.x,
                    row.value.target_impulse_kg_m_per_s.y,
                    row.value.target_impulse_kg_m_per_s.z};
                const std::array applied{
                    row.value.applied_impulse_kg_m_per_s.x,
                    row.value.applied_impulse_kg_m_per_s.y,
                    row.value.applied_impulse_kg_m_per_s.z};
                for (std::size_t axis = 0; axis < 3U; ++axis) {
                    summary.maximum_error_base_quanta = std::max(
                        summary.maximum_error_base_quanta,
                        std::abs(target[axis] - applied[axis]) / base_pq);
                    minimum[axis] = std::min(minimum[axis], applied[axis]);
                    maximum[axis] = std::max(maximum[axis], applied[axis]);
                }
                summary.maximum_floor_residual_j = std::max(
                    summary.maximum_floor_residual_j,
                    row.value.kinetic_floor_residual_j);
            }
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                summary.subdivision_spread_base_quanta = std::max(
                    summary.subdivision_spread_base_quanta,
                    (maximum[axis] - minimum[axis]) / base_pq);
            }
        }
        summary.passes = refinement > 1U &&
            summary.maximum_error_base_quanta < 1.0 / 32.0 &&
            summary.subdivision_spread_base_quanta < 1.0 / 16.0;
        result.push_back(summary);
    }
    return result;
}

struct Tables final {
    Csv metadata{"key,value"};
    Csv units{
        "refinement,Lq,Mq,Tq,Pq,Eq,Fq,physical_time_numerator,"
        "physical_time_denominator,velocity_scale_numerator,"
        "velocity_scale_denominator,kinetic_scale_denominator"};
    Csv packets{
        "packet_id,base_x_raw,base_y_raw,base_z_raw,base_px_raw,base_py_raw,"
        "base_pz_raw,base_mass_raw,x_bits,y_bits,z_bits,px_bits,py_bits,pz_bits,"
        "mass_bits,nearest_roundtrip_exact"};
    Csv relation_values{
        "relation_index,first_id,second_id,reference_length_bits,current_length_bits,"
        "extension_bits,direction_x_bits,direction_y_bits,direction_z_bits,"
        "conjugate_force_bits,force_x_bits,force_y_bits,force_z_bits,"
        "geometry_path,geometry_status,rho_num,rho_den"};
    Csv h{
        "row_relation_index,column_relation_index,h_bits"};
    Csv evaluations{
        "relation_index,first_id,second_id,path,refinement,subdivisions,"
        "primitive_x,primitive_y,primitive_z,applied_multiple,impulse_x_raw,"
        "impulse_y_raw,impulse_z_raw,opposite_x_raw,opposite_y_raw,opposite_z_raw,"
        "target_multiple_bits,remainder_bits,target_x_bits,target_y_bits,target_z_bits,"
        "applied_x_bits,applied_y_bits,applied_z_bits,discarded_x_bits,"
        "discarded_y_bits,discarded_z_bits,kinetic_raw,exact_kinetic_bits,"
        "quantized_kinetic_bits,floor_residual_bits,work_bits,balance_error_bits,"
        "checkpoint_first_id,checkpoint_second_id,checkpoint_remainder_bits,"
        "checkpoint_hash,linear_conserved,angular_conserved,checkpoint_roundtrip"};
    Csv summary{
        "refinement,maximum_error_base_quanta_bits,subdivision_spread_base_quanta_bits,"
        "maximum_floor_residual_bits,passes,selected"};
};

void write_tables(const std::filesystem::path& output) {
    const auto packets = base_packets();
    const auto reference = reference_packets();
    const auto current = current_packets(packets);
    const auto parent = constitutive::build_local_collective_energy(
        reference, weighted_relations(),
        {.dilatational_coefficient_j_per_m2 = 3.0 * 2.0 / 20.0,
         .deviatoric_coefficient_j_per_m2 = 0.25});
    const auto frozen = force::freeze_symmetric_force_operator(parent);
    const auto evaluated_force = geometry::evaluate_resolved_spatial_force(
        frozen, reference, current,
        geometry::GeometryPath::cancellation_resistant_binary64);
    if (evaluated_force.status != geometry::ResolvedForceStatus::evaluated ||
        evaluated_force.relation_coordinates.size() != 6U) {
        throw std::runtime_error("accepted Path B bridge force did not evaluate");
    }

    Tables tables{};
    tables.metadata.row({"schema", "mls.authoritative-mechanics-state-bridge.raw.v1"});
    tables.metadata.row({"accepted_parent_sha", accepted_parent_sha});
    tables.metadata.row({"accepted_parent_tag", accepted_parent_tag});
    tables.metadata.row({"accepted_parent_tag_object", accepted_parent_tag_object});
    tables.metadata.row({"source_sha", MLS_CONFIGURED_SOURCE_SHA});
    tables.metadata.row({"source_branch", MLS_CONFIGURED_SOURCE_BRANCH});
    tables.metadata.row({"source_dirty", MLS_CONFIGURED_SOURCE_DIRTY});
    tables.metadata.row({"compiler_id", MLS_CONFIGURED_COMPILER_ID});
    tables.metadata.row({"compiler_version", MLS_CONFIGURED_COMPILER_VERSION});
    tables.metadata.row({"build_type", MLS_CONFIGURED_BUILD_TYPE});
    tables.metadata.row({"branch", branch});
    tables.metadata.row({"decision", decision});
    tables.metadata.row({"selected_refinement", "16"});
    tables.metadata.row({"selected_geometry_path", "cancellation_resistant_binary64"});
    tables.metadata.row({"safe_domain", "2^-24"});
    tables.metadata.row({"promotion", "NO_PROMOTION"});

    for (const auto refinement : std::array{1U, 2U, 4U, 8U, 16U}) {
        const auto unit = bridge::mechanics_unit_contract(refinement);
        tables.units.row(
            {std::to_string(refinement), rational(unit.length_quantum_m),
             rational(unit.mass_quantum_kg), rational(unit.time_quantum_s),
             rational(unit.momentum_quantum_kg_m_per_s),
             rational(unit.energy_quantum_j), rational(unit.force_quantum_n),
             std::to_string(unit.physical_time_scale.seconds_per_time_quantum_numerator),
             std::to_string(unit.physical_time_scale.seconds_per_time_quantum_denominator),
             std::to_string(unit.momentum_mass_to_velocity_scale.length_quanta_numerator),
             std::to_string(unit.momentum_mass_to_velocity_scale.length_quanta_denominator),
             std::to_string(unit.kinetic_energy_scale_denominator)});
    }

    const auto base_units = bridge::mechanics_unit_contract(1);
    for (const auto& packet : packets) {
        const auto mapped = bridge::map_packet_to_binary64_si(packet, base_units);
        tables.packets.row(
            {std::to_string(packet.id), std::to_string(packet.position.x.raw()),
             std::to_string(packet.position.y.raw()),
             std::to_string(packet.position.z.raw()),
             std::to_string(packet.momentum.x.raw()),
             std::to_string(packet.momentum.y.raw()),
             std::to_string(packet.momentum.z.raw()),
             std::to_string(packet.mass.raw()), bits(mapped.position_m.x),
             bits(mapped.position_m.y), bits(mapped.position_m.z),
             bits(mapped.momentum_kg_m_per_s.x),
             bits(mapped.momentum_kg_m_per_s.y),
             bits(mapped.momentum_kg_m_per_s.z), bits(mapped.mass_kg),
             boolean(mapped.nearest_roundtrip_exact)});
    }

    for (std::size_t row = 0;
         row < frozen.force_operator.h_j_per_m2.row_count(); ++row) {
        for (std::size_t column = 0;
             column < frozen.force_operator.h_j_per_m2.column_count(); ++column) {
            tables.h.row(
                {std::to_string(row), std::to_string(column),
                 bits(frozen.force_operator.h_j_per_m2(row, column))});
        }
    }

    std::vector<EvaluationRow> evaluation_rows;
    for (const auto& coordinate : evaluated_force.relation_coordinates) {
        const auto force_value = relation_force_to_first(coordinate);
        tables.relation_values.row(
            {std::to_string(coordinate.relation_index),
             std::to_string(coordinate.relation.first_id),
             std::to_string(coordinate.relation.second_id),
             bits(frozen.force_operator.reference_lengths_m.at(
                 coordinate.relation_index)),
             bits(coordinate.geometry.current_length_m),
             bits(coordinate.geometry.extension_m),
             bits(coordinate.geometry.direction_first_to_second.x),
             bits(coordinate.geometry.direction_first_to_second.y),
             bits(coordinate.geometry.direction_first_to_second.z),
             bits(coordinate.conjugate_force_n), bits(force_value.x),
             bits(force_value.y), bits(force_value.z),
             geometry::path_name(coordinate.geometry.path).data(),
             geometry::status_name(coordinate.geometry.status).data(),
             "1001", "1000"});
        const auto& first = packet_by_id(packets, coordinate.relation.first_id);
        const auto& second = packet_by_id(packets, coordinate.relation.second_id);
        for (const auto refinement : std::array{1U, 2U, 4U, 8U, 16U}) {
            const auto units = bridge::mechanics_unit_contract(refinement);
            for (const auto subdivisions : std::array{1U, 2U, 4U, 8U, 16U}) {
                for (const auto path :
                     std::array{bridge::QuantizationPath::direct_nearest,
                                bridge::QuantizationPath::fixed_point_refinement,
                                bridge::QuantizationPath::explicit_remainder}) {
                    const auto value = bridge::evaluate_central_impulse(
                        {first, second, force_value,
                         Time::from_raw(1'000'000'000), subdivisions, path},
                        units);
                    evaluation_rows.push_back({coordinate.relation_index, value});
                    tables.evaluations.row(
                        {std::to_string(coordinate.relation_index),
                         std::to_string(first.id), std::to_string(second.id),
                         bridge::path_name(path), std::to_string(refinement),
                         std::to_string(subdivisions),
                         std::to_string(value.primitive_direction.x.raw()),
                         std::to_string(value.primitive_direction.y.raw()),
                         std::to_string(value.primitive_direction.z.raw()),
                         std::to_string(value.applied_primitive_multiple),
                         std::to_string(value.impulse_to_first.x.raw()),
                         std::to_string(value.impulse_to_first.y.raw()),
                         std::to_string(value.impulse_to_first.z.raw()),
                         std::to_string(value.impulse_to_second.x.raw()),
                         std::to_string(value.impulse_to_second.y.raw()),
                         std::to_string(value.impulse_to_second.z.raw()),
                         bits(value.target_primitive_multiple),
                         bits(value.remainder_primitive_quanta),
                         bits(value.target_impulse_kg_m_per_s.x),
                         bits(value.target_impulse_kg_m_per_s.y),
                         bits(value.target_impulse_kg_m_per_s.z),
                         bits(value.applied_impulse_kg_m_per_s.x),
                         bits(value.applied_impulse_kg_m_per_s.y),
                         bits(value.applied_impulse_kg_m_per_s.z),
                         bits(value.discarded_impulse_kg_m_per_s.x),
                         bits(value.discarded_impulse_kg_m_per_s.y),
                         bits(value.discarded_impulse_kg_m_per_s.z),
                         std::to_string(value.quantized_kinetic_delta.raw()),
                         bits(value.exact_kinetic_delta_j),
                         bits(value.quantized_kinetic_delta_j),
                         bits(value.kinetic_floor_residual_j),
                         bits(value.exact_impulse_work_j),
                         bits(value.remainder_balance_error),
                         std::to_string(value.remainder_checkpoint.first_id),
                         std::to_string(value.remainder_checkpoint.second_id),
                         std::to_string(
                             value.remainder_checkpoint.scalar_remainder_bits),
                         std::to_string(value.remainder_checkpoint_hash),
                         boolean(value.exact_linear_momentum),
                         boolean(value.exact_orbital_angular_momentum),
                         boolean(value.remainder_checkpoint_roundtrip)});
                }
            }
        }
    }

    const auto summaries = summarize(evaluation_rows);
    bool prior_error = false;
    double last_error = std::numeric_limits<double>::infinity();
    std::uint32_t selected = 0U;
    for (const auto& summary : summaries) {
        if (summary.maximum_error_base_quanta >= last_error) {
            prior_error = true;
        }
        last_error = summary.maximum_error_base_quanta;
        if (selected == 0U && summary.passes) {
            selected = summary.refinement;
        }
        tables.summary.row(
            {std::to_string(summary.refinement),
             bits(summary.maximum_error_base_quanta),
             bits(summary.subdivision_spread_base_quanta),
             bits(summary.maximum_floor_residual_j), boolean(summary.passes),
             boolean(summary.refinement == 16U)});
    }
    if (prior_error || selected != 16U) {
        throw std::runtime_error(
            "preregistered stateless refinement selection did not resolve to R=16");
    }

    std::filesystem::create_directories(output);
    tables.metadata.write(output / "metadata.csv");
    tables.units.write(output / "units.csv");
    tables.packets.write(output / "packets_bits.csv");
    tables.relation_values.write(output / "relations_bits.csv");
    tables.h.write(output / "h_bits.csv");
    tables.evaluations.write(output / "evaluations.csv");
    tables.summary.write(output / "candidate_summary.csv");
}

void schema_audit() {
    Tables tables{};
    if (tables.metadata.text() != "key,value\n" ||
        tables.units.text().find("refinement,Lq,Mq,Tq,Pq,Eq,Fq") != 0U ||
        tables.evaluations.text().find("relation_index,first_id,second_id,path") != 0U) {
        throw std::runtime_error("bridge raw schema inventory differs");
    }
    std::cout << "Authoritative Mechanics State Bridge raw schema audit: PASS\n";
}

} // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--schema-audit") {
            schema_audit();
            return 0;
        }
        if (argc != 3 || std::string(argv[1]) != "--output") {
            throw std::invalid_argument(
                "usage: diagnostic --schema-audit | --output DIRECTORY");
        }
        write_tables(argv[2]);
        std::cout
            << "AUTHORITATIVE MECHANICS STATE BRIDGE RAW COMPLETE: "
            << decision << " R=16 NO_PROMOTION\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "AUTHORITATIVE MECHANICS STATE BRIDGE FAILED: "
                  << error.what() << '\n';
        return 1;
    }
}
