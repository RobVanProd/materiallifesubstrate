#include "mls/authoritative_drift_state_bridge_lab.hpp"
#include "mls/constitutive_expressivity_lab.hpp"
#include "mls/world.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <initializer_list>
#include <iostream>
#include <limits>
#include <map>
#include <ranges>
#include <span>
#include <stdexcept>
#include <string>
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

namespace drift = mls::experimental::authoritative_drift_state_bridge;
namespace mechanics = mls::experimental::authoritative_mechanics_state_bridge;
namespace constitutive = mls::experimental::constitutive_expressivity;
namespace force = mls::experimental::conservative_force_consistency;
namespace geometry = mls::experimental::relation_geometry_resolution;
namespace observation = mls::experimental::mechanical_observability;
using mls::Length;
using mls::Mass;
using mls::Momentum;
using mls::Time;
using mls::experimental::Vec3d;

constexpr auto accepted_parent_sha =
    "d8fca8b0bf59a92382048bfb1389126552ac92f3";
constexpr auto accepted_parent_tag =
    "authoritative-mechanics-state-bridge-lab-evidence-v1";
constexpr auto accepted_parent_tag_object =
    "0a920fbb080525123d29dbea0a81b3bee3b9eec6";
constexpr auto branch = "authoritative-drift-state-bridge-lab";
constexpr auto decision =
    "retain_refined_stateless_mechanics_representation_for_research";
constexpr double base_length_quantum_m = 1.0e-9;

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
            throw std::runtime_error("cannot write drift evidence file");
        }
        stream << text_;
        if (!stream) {
            throw std::runtime_error("cannot complete drift evidence file");
        }
    }

    [[nodiscard]] const std::string& text() const noexcept { return text_; }

private:
    std::string text_;
};

[[nodiscard]] std::string boolean(bool value) {
    return value ? "true" : "false";
}

[[nodiscard]] std::string bits(double value) {
    return std::to_string(std::bit_cast<std::uint64_t>(value));
}

[[nodiscard]] std::string rational(mechanics::PositiveRational value) {
    return std::to_string(value.numerator) + "/" +
        std::to_string(value.denominator);
}

[[nodiscard]] drift::DriftPacket drift_packet(
    std::uint64_t id,
    mls::Scalar px,
    mls::Scalar py,
    mls::Scalar pz,
    mls::Scalar mass) {
    return {
        id,
        {Length::from_raw(static_cast<mls::Scalar>(id * 3U)),
         Length::from_raw(-static_cast<mls::Scalar>(id * 2U)),
         Length::from_raw(static_cast<mls::Scalar>(id))},
        {Momentum::from_raw(px), Momentum::from_raw(py), Momentum::from_raw(pz)},
        Mass::from_raw(mass),
    };
}

[[nodiscard]] std::vector<drift::DriftPacket> inventory() {
    return {
        drift_packet(1, 0, 0, 0, 37),
        drift_packet(2, 5, 0, 0, 37),
        drift_packet(3, -3, 5, -7, 41),
        drift_packet(4, 14, -21, 28, 43),
        drift_packet(5, 33, 22, -11, 47),
        drift_packet(6, 2, -3, 1, 5),
        drift_packet(7, 6, -9, 3, 15),
    };
}

[[nodiscard]] const drift::DriftPacket& packet_by_id(
    std::span<const drift::DriftPacket> packets, std::uint64_t id) {
    const auto found = std::ranges::find(packets, id, &drift::DriftPacket::id);
    if (found == packets.end()) {
        throw std::runtime_error("drift packet identity absent");
    }
    return *found;
}

struct Fingerprint final {
    bool exact_pass{false};
    bool exact_displacement{false};
    bool fractional_rejected{false};
    bool fractional_transactional{false};
};

struct WorldFixture final {
    mls::CompoundId material{};
    mls::World world;
};

[[nodiscard]] WorldFixture fingerprint_world() {
    const mls::ElementId element{1};
    mls::ElementCatalog elements;
    elements.define(
        element,
        {Mass::from_raw(4), mls::HeatCapacity::from_raw(2),
         mls::Energy::from_raw(20)});
    mls::CompoundRegistry compounds;
    const auto material = compounds.intern(mls::CompoundGraph({element}, {}));
    return {material, mls::World(std::move(elements), std::move(compounds))};
}

[[nodiscard]] mls::MaterialSeed material_seed(
    mls::CompoundId material, mls::Momentum momentum) {
    return {
        {}, {momentum, {}, {}}, {{material, 1}},
        mls::Energy::from_raw(100), mls::Energy::from_raw(50)};
}

[[nodiscard]] Fingerprint reproduce_parent_fingerprint() {
    Fingerprint result{};
    auto exact = fingerprint_world();
    const auto exact_packet = exact.world.introduce_material_from_boundary(
        material_seed(exact.material, Momentum::from_raw(4)));
    exact.world.step();
    result.exact_pass = exact.world.tick() == 1U;
    result.exact_displacement =
        exact.world.packets().snapshot(exact_packet).position.x ==
        Length::from_raw(1);

    auto fractional = fingerprint_world();
    static_cast<void>(fractional.world.introduce_material_from_boundary(
        material_seed(fractional.material, Momentum::from_raw(1))));
    const auto hash_before = fractional.world.physical_state_hash();
    try {
        fractional.world.step();
    } catch (const std::domain_error&) {
        result.fractional_rejected = true;
    }
    result.fractional_transactional =
        fractional.world.physical_state_hash() == hash_before &&
        fractional.world.tick() == 0U && fractional.world.physical_time() == Time{};
    return result;
}

[[nodiscard]] std::array<mls::Scalar, 3> raw(const mls::Position3& value) noexcept {
    return {value.x.raw(), value.y.raw(), value.z.raw()};
}

[[nodiscard]] std::array<mls::Scalar, 3> raw(const mls::Momentum3& value) noexcept {
    return {value.x.raw(), value.y.raw(), value.z.raw()};
}

[[nodiscard]] std::array<mls::Scalar, 3> raw(
    const mls::AngularMomentum3& value) noexcept {
    return {value.x.raw(), value.y.raw(), value.z.raw()};
}

[[nodiscard]] std::array<double, 3> as_base_quanta(
    const mls::Position3& value, std::uint32_t refinement) noexcept {
    return {
        static_cast<double>(value.x.raw()) / refinement,
        static_cast<double>(value.y.raw()) / refinement,
        static_cast<double>(value.z.raw()) / refinement,
    };
}

[[nodiscard]] double distance(
    const std::array<double, 3>& first,
    const std::array<double, 3>& second) noexcept {
    const auto x = first[0] - second[0];
    const auto y = first[1] - second[1];
    const auto z = first[2] - second[2];
    return std::sqrt(x * x + y * y + z * z);
}

struct EvaluationRow final {
    std::uint64_t packet_id{0};
    mls::Scalar horizon{0};
    drift::DriftEvaluation value{};
};

struct ImpulseRegression final {
    std::uint32_t refinement{1};
    bool exact_conservation{true};
    bool kinetic_floor{true};
    double maximum_error_base_quanta{0.0};
    double maximum_spread_base_quanta{0.0};
    bool passes{false};
};

[[nodiscard]] std::vector<mechanics::AuthoritativePacket> impulse_packets() {
    return {
        {1, {}, {}, Mass::from_raw(1)},
        {2, {Length::from_raw(1'001'000'000), {}, {}}, {}, Mass::from_raw(1)},
        {3, {{}, Length::from_raw(1'001'000'000), {}}, {}, Mass::from_raw(1)},
        {4, {{}, {}, Length::from_raw(1'001'000'000)}, {}, Mass::from_raw(1)},
    };
}

[[nodiscard]] std::vector<observation::MechanicalPacket> impulse_reference() {
    return {
        {1, 1, {0.0, 0.0, 0.0}, {}}, {2, 1, {1.0, 0.0, 0.0}, {}},
        {3, 1, {0.0, 1.0, 0.0}, {}}, {4, 1, {0.0, 0.0, 1.0}, {}},
    };
}

[[nodiscard]] std::vector<observation::BondRelation> impulse_relations() {
    return {{1, 2}, {1, 3}, {1, 4}, {2, 3}, {2, 4}, {3, 4}};
}

[[nodiscard]] std::vector<constitutive::WeightedRelation> impulse_weights() {
    std::vector<constitutive::WeightedRelation> result;
    for (const auto relation : impulse_relations()) {
        result.push_back({relation, 1.0});
    }
    return result;
}

[[nodiscard]] std::vector<observation::MechanicalPacket> impulse_current(
    std::span<const mechanics::AuthoritativePacket> packets) {
    const auto units = mechanics::mechanics_unit_contract(1);
    std::vector<observation::MechanicalPacket> result;
    for (const auto& packet : packets) {
        const auto mapped = mechanics::map_packet_to_binary64_si(packet, units);
        result.push_back({packet.id, packet.mass.raw(), mapped.position_m, {}});
    }
    return result;
}

[[nodiscard]] const mechanics::AuthoritativePacket& impulse_packet_by_id(
    std::span<const mechanics::AuthoritativePacket> packets, std::uint64_t id) {
    const auto found = std::ranges::find(
        packets, id, &mechanics::AuthoritativePacket::id);
    if (found == packets.end()) {
        throw std::runtime_error("impulse packet identity absent");
    }
    return *found;
}

[[nodiscard]] std::map<std::uint32_t, ImpulseRegression>
run_impulse_regression(Csv& rows) {
    const auto packets = impulse_packets();
    const auto reference = impulse_reference();
    const auto parent = constitutive::build_local_collective_energy(
        reference, impulse_weights(),
        {.dilatational_coefficient_j_per_m2 = 3.0 * 2.0 / 20.0,
         .deviatoric_coefficient_j_per_m2 = 0.25});
    const auto frozen = force::freeze_symmetric_force_operator(parent);
    const auto evaluated = geometry::evaluate_resolved_spatial_force(
        frozen, reference, impulse_current(packets),
        geometry::GeometryPath::cancellation_resistant_binary64);
    if (evaluated.status != geometry::ResolvedForceStatus::evaluated ||
        evaluated.relation_coordinates.size() != 6U) {
        throw std::runtime_error("frozen impulse force regression unavailable");
    }

    const auto base_pq = 1.0 / 4'096.0;
    std::map<std::uint32_t, ImpulseRegression> result;
    for (const auto refinement : std::array{16U, 32U, 64U, 128U}) {
        ImpulseRegression summary{};
        summary.refinement = refinement;
        const auto units = mechanics::mechanics_unit_contract(refinement);
        for (const auto& coordinate : evaluated.relation_coordinates) {
            const auto direction = coordinate.geometry.direction_first_to_second;
            const auto relation_force = coordinate.conjugate_force_n * direction;
            const auto& first = impulse_packet_by_id(
                packets, coordinate.relation.first_id);
            const auto& second = impulse_packet_by_id(
                packets, coordinate.relation.second_id);
            std::array<double, 3> minimum{
                std::numeric_limits<double>::infinity(),
                std::numeric_limits<double>::infinity(),
                std::numeric_limits<double>::infinity()};
            std::array<double, 3> maximum{
                -std::numeric_limits<double>::infinity(),
                -std::numeric_limits<double>::infinity(),
                -std::numeric_limits<double>::infinity()};
            for (const auto subdivisions : std::array{1U, 2U, 4U, 8U, 16U}) {
                const auto value = mechanics::evaluate_central_impulse(
                    {first, second, relation_force, Time::from_raw(1'000'000'000),
                     subdivisions, mechanics::QuantizationPath::fixed_point_refinement},
                    units);
                const std::array target{
                    value.target_impulse_kg_m_per_s.x,
                    value.target_impulse_kg_m_per_s.y,
                    value.target_impulse_kg_m_per_s.z};
                const std::array applied{
                    value.applied_impulse_kg_m_per_s.x,
                    value.applied_impulse_kg_m_per_s.y,
                    value.applied_impulse_kg_m_per_s.z};
                for (std::size_t axis = 0; axis < target.size(); ++axis) {
                    summary.maximum_error_base_quanta = std::max(
                        summary.maximum_error_base_quanta,
                        std::abs(target[axis] - applied[axis]) / base_pq);
                    minimum[axis] = std::min(minimum[axis], applied[axis]);
                    maximum[axis] = std::max(maximum[axis], applied[axis]);
                }
                const auto eq = static_cast<double>(units.energy_quantum_j.numerator) /
                    static_cast<double>(units.energy_quantum_j.denominator);
                summary.exact_conservation = summary.exact_conservation &&
                    value.exact_linear_momentum &&
                    value.exact_orbital_angular_momentum;
                summary.kinetic_floor = summary.kinetic_floor &&
                    value.kinetic_floor_residual_j >= -1.0e-18 &&
                    value.kinetic_floor_residual_j < 2.0 * eq;
                rows.row(
                    {std::to_string(coordinate.relation_index),
                     std::to_string(refinement), std::to_string(subdivisions),
                     bits(value.target_primitive_multiple),
                     std::to_string(value.primitive_direction.x.raw()),
                     std::to_string(value.primitive_direction.y.raw()),
                     std::to_string(value.primitive_direction.z.raw()),
                     std::to_string(value.applied_primitive_multiple),
                     boolean(value.exact_linear_momentum),
                     boolean(value.exact_orbital_angular_momentum),
                     bits(value.kinetic_floor_residual_j)});
            }
            for (std::size_t axis = 0; axis < minimum.size(); ++axis) {
                summary.maximum_spread_base_quanta = std::max(
                    summary.maximum_spread_base_quanta,
                    (maximum[axis] - minimum[axis]) / base_pq);
            }
        }
        summary.passes = summary.exact_conservation && summary.kinetic_floor &&
            summary.maximum_error_base_quanta < 1.0 / 32.0 &&
            summary.maximum_spread_base_quanta < 1.0 / 16.0;
        result.emplace(refinement, summary);
    }
    return result;
}

struct DriftSummary final {
    std::uint32_t refinement{1};
    double maximum_component_error{0.0};
    double maximum_vector_error{0.0};
    double maximum_component_spread{0.0};
    double maximum_vector_spread{0.0};
    double maximum_com_component_error{0.0};
    double maximum_com_vector_error{0.0};
    bool exact_gates{true};
    bool equal_velocity{true};
    bool inherited_impulse{false};
    bool passes{false};
};

struct Tables final {
    Csv metadata{"key,value"};
    Csv units{
        "refinement,Lq,Mq,Tq,Pq,Eq,Fq,velocity_scale_numerator,"
        "velocity_scale_denominator,kinetic_scale_denominator"};
    Csv parent_fingerprint{
        "case,expected,result,transactional"};
    Csv inventory{
        "packet_id,base_x,base_y,base_z,base_px,base_py,base_pz,base_mass,role"};
    Csv evaluations{
        "packet_id,path,refinement,horizon,subdivisions,substep,refined_x,"
        "refined_y,refined_z,refined_px,refined_py,refined_pz,refined_mass,gcd,"
        "primitive_x,primitive_y,primitive_z,applied_dx,applied_dy,applied_dz,"
        "target_x_num,target_y_num,target_z_num,target_den,error_x_num,error_y_num,"
        "error_z_num,exact_x_bits,exact_y_bits,exact_z_bits,applied_x_bits,"
        "applied_y_bits,applied_z_bits,error_x_bits,error_y_bits,error_z_bits,"
        "vector_error_bits,delta_L_x,delta_L_y,delta_L_z,kinetic_before,kinetic_after,"
        "product_margin,momentum_unchanged,kinetic_unchanged,angular_unchanged"};
    Csv equal_velocity{
        "refinement,horizon,subdivisions,first_id,second_id,first_dx,first_dy,"
        "first_dz,second_dx,second_dy,second_dz,above_resolution,equal"};
    Csv center_of_mass{
        "refinement,horizon,subdivisions,total_mass,exact_x_bits,exact_y_bits,"
        "exact_z_bits,applied_x_bits,applied_y_bits,applied_z_bits,error_x_bits,"
        "error_y_bits,error_z_bits,vector_error_bits"};
    Csv impulse_regression{
        "relation_index,refinement,subdivisions,target_multiple_bits,primitive_x,"
        "primitive_y,primitive_z,applied_multiple,linear_conserved,"
        "angular_conserved,kinetic_floor_residual_bits"};
    Csv domain_chords{
        "id,initial_x,initial_y,initial_z,final_x,final_y,final_z,rest_length,"
        "interior_minimum,admissible"};
    Csv overflow_controls{
        "case,multiplicand,multiplier,denominator,accepted,result"};
    Csv rounding_controls{
        "numerator,denominator,nearest_even"};
    Csv candidate_summary{
        "refinement,maximum_component_error_bits,maximum_vector_error_bits,"
        "maximum_component_spread_bits,maximum_vector_spread_bits,"
        "maximum_com_component_error_bits,maximum_com_vector_error_bits,"
        "exact_gates,equal_velocity,inherited_impulse,passes,selected"};
};

void write_tables(const std::filesystem::path& output) {
    Tables tables{};
    const auto fingerprint = reproduce_parent_fingerprint();
    tables.parent_fingerprint.row(
        {"exact_integer", "pass", boolean(fingerprint.exact_pass && fingerprint.exact_displacement), "true"});
    tables.parent_fingerprint.row(
        {"fractional", "reject", boolean(fingerprint.fractional_rejected),
         boolean(fingerprint.fractional_transactional)});
    if (!fingerprint.exact_pass || !fingerprint.exact_displacement ||
        !fingerprint.fractional_rejected || !fingerprint.fractional_transactional) {
        throw std::runtime_error("stop_inconclusive_or_wrong_parent");
    }

    const auto packets = inventory();
    const std::array roles{
        "zero", "axis", "mixed_primitive", "non_coprime", "magnitude",
        "equal_velocity_a", "equal_velocity_b"};
    for (std::size_t index = 0; index < packets.size(); ++index) {
        const auto& value = packets[index];
        tables.inventory.row(
            {std::to_string(value.id), std::to_string(value.base_position.x.raw()),
             std::to_string(value.base_position.y.raw()),
             std::to_string(value.base_position.z.raw()),
             std::to_string(value.base_momentum.x.raw()),
             std::to_string(value.base_momentum.y.raw()),
             std::to_string(value.base_momentum.z.raw()),
             std::to_string(value.base_mass.raw()), roles[index]});
    }

    constexpr std::array refinements{1U, 2U, 4U, 8U, 16U, 32U, 64U, 128U};
    constexpr std::array horizons{32, 96, 160};
    constexpr std::array subdivisions{1U, 2U, 4U, 8U, 16U, 32U};
    for (const auto refinement : refinements) {
        const auto units = mechanics::mechanics_unit_contract(refinement);
        tables.units.row(
            {std::to_string(refinement), rational(units.length_quantum_m),
             rational(units.mass_quantum_kg), rational(units.time_quantum_s),
             rational(units.momentum_quantum_kg_m_per_s),
             rational(units.energy_quantum_j), rational(units.force_quantum_n),
             std::to_string(units.momentum_mass_to_velocity_scale.length_quanta_numerator),
             std::to_string(units.momentum_mass_to_velocity_scale.length_quanta_denominator),
             std::to_string(units.kinetic_energy_scale_denominator)});
    }

    std::vector<EvaluationRow> evaluation_rows;
    for (const auto refinement : refinements) {
        const auto units = mechanics::mechanics_unit_contract(refinement);
        for (const auto& packet : packets) {
            for (const auto horizon : horizons) {
                for (const auto count : subdivisions) {
                    for (const auto path :
                         std::array{drift::DriftPath::cartesian_nearest,
                                    drift::DriftPath::primitive_directional}) {
                        const auto value = drift::evaluate_drift(
                            {packet, Time::from_raw(horizon), count, path}, units);
                        evaluation_rows.push_back({packet.id, horizon, value});
                        const auto position = raw(value.refined_position);
                        const auto momentum = raw(value.refined_momentum);
                        const auto primitive = raw(value.primitive_direction);
                        const auto applied = raw(value.applied_displacement);
                        const auto delta = raw(value.orbital_angular_momentum_delta);
                        tables.evaluations.row(
                            {std::to_string(packet.id), drift::path_name(path),
                             std::to_string(refinement), std::to_string(horizon),
                             std::to_string(count), std::to_string(value.substep.raw()),
                             std::to_string(position[0]), std::to_string(position[1]),
                             std::to_string(position[2]), std::to_string(momentum[0]),
                             std::to_string(momentum[1]), std::to_string(momentum[2]),
                             std::to_string(value.refined_mass.raw()),
                             std::to_string(value.direction_gcd),
                             std::to_string(primitive[0]), std::to_string(primitive[1]),
                             std::to_string(primitive[2]), std::to_string(applied[0]),
                             std::to_string(applied[1]), std::to_string(applied[2]),
                             std::to_string(value.target_numerator[0]),
                             std::to_string(value.target_numerator[1]),
                             std::to_string(value.target_numerator[2]),
                             std::to_string(value.target_denominator),
                             std::to_string(value.error_numerator[0]),
                             std::to_string(value.error_numerator[1]),
                             std::to_string(value.error_numerator[2]),
                             bits(value.exact_displacement_m.x),
                             bits(value.exact_displacement_m.y),
                             bits(value.exact_displacement_m.z),
                             bits(value.applied_displacement_m.x),
                             bits(value.applied_displacement_m.y),
                             bits(value.applied_displacement_m.z),
                             bits(value.component_error_m.x),
                             bits(value.component_error_m.y),
                             bits(value.component_error_m.z), bits(value.vector_error_m),
                             std::to_string(delta[0]), std::to_string(delta[1]),
                             std::to_string(delta[2]),
                             std::to_string(value.kinetic_energy_before.raw()),
                             std::to_string(value.kinetic_energy_after.raw()),
                             std::to_string(value.checked_product_margin),
                             boolean(value.exact_momentum_unchanged),
                             boolean(value.exact_kinetic_energy_unchanged),
                             boolean(value.exact_orbital_angular_momentum)});
                    }
                }
            }
        }
    }

    const auto impulse = run_impulse_regression(tables.impulse_regression);
    std::vector<DriftSummary> summaries;
    for (const auto refinement : refinements) {
        DriftSummary summary{};
        summary.refinement = refinement;
        for (const auto& row : evaluation_rows) {
            if (row.value.refinement != refinement ||
                row.value.path != drift::DriftPath::primitive_directional) {
                continue;
            }
            summary.maximum_component_error = std::max(
                summary.maximum_component_error,
                std::max({std::abs(row.value.component_error_m.x),
                          std::abs(row.value.component_error_m.y),
                          std::abs(row.value.component_error_m.z)}) /
                    base_length_quantum_m);
            summary.maximum_vector_error = std::max(
                summary.maximum_vector_error,
                row.value.vector_error_m / base_length_quantum_m);
            summary.exact_gates = summary.exact_gates &&
                row.value.exact_momentum_unchanged &&
                row.value.exact_kinetic_energy_unchanged &&
                row.value.exact_orbital_angular_momentum;
        }

        for (const auto& packet : packets) {
            for (const auto horizon : horizons) {
                std::vector<std::array<double, 3>> applied;
                for (const auto& row : evaluation_rows) {
                    if (row.packet_id == packet.id && row.horizon == horizon &&
                        row.value.refinement == refinement &&
                        row.value.path == drift::DriftPath::primitive_directional) {
                        applied.push_back(as_base_quanta(
                            row.value.applied_displacement, refinement));
                    }
                }
                for (const auto& first : applied) {
                    for (const auto& second : applied) {
                        for (std::size_t axis = 0; axis < first.size(); ++axis) {
                            summary.maximum_component_spread = std::max(
                                summary.maximum_component_spread,
                                std::abs(first[axis] - second[axis]));
                        }
                        summary.maximum_vector_spread = std::max(
                            summary.maximum_vector_spread,
                            distance(first, second));
                    }
                }
            }
        }

        const auto& equal_a = packet_by_id(packets, 6);
        const auto& equal_b = packet_by_id(packets, 7);
        for (const auto horizon : horizons) {
            for (const auto count : subdivisions) {
                const auto units = mechanics::mechanics_unit_contract(refinement);
                const auto first = drift::evaluate_drift(
                    {equal_a, Time::from_raw(horizon), count,
                     drift::DriftPath::primitive_directional}, units);
                const auto second = drift::evaluate_drift(
                    {equal_b, Time::from_raw(horizon), count,
                     drift::DriftPath::primitive_directional}, units);
                const auto equal = first.applied_displacement == second.applied_displacement;
                summary.equal_velocity = summary.equal_velocity && equal;
                const auto exact_norm = std::sqrt(
                    first.exact_displacement_m.x * first.exact_displacement_m.x +
                    first.exact_displacement_m.y * first.exact_displacement_m.y +
                    first.exact_displacement_m.z * first.exact_displacement_m.z);
                tables.equal_velocity.row(
                    {std::to_string(refinement), std::to_string(horizon),
                     std::to_string(count), "6", "7",
                     std::to_string(first.applied_displacement.x.raw()),
                     std::to_string(first.applied_displacement.y.raw()),
                     std::to_string(first.applied_displacement.z.raw()),
                     std::to_string(second.applied_displacement.x.raw()),
                     std::to_string(second.applied_displacement.y.raw()),
                     std::to_string(second.applied_displacement.z.raw()),
                     boolean(exact_norm > base_length_quantum_m / refinement),
                     boolean(equal)});
            }
        }

        for (const auto horizon : horizons) {
            for (const auto count : subdivisions) {
                double total_mass = 0.0;
                std::array<double, 3> exact{};
                std::array<double, 3> applied{};
                for (const auto id : std::array{2U, 3U, 4U, 5U}) {
                    const auto& packet = packet_by_id(packets, id);
                    const auto value = drift::evaluate_drift(
                        {packet, Time::from_raw(horizon), count,
                         drift::DriftPath::primitive_directional},
                        mechanics::mechanics_unit_contract(refinement));
                    const auto mass = static_cast<double>(packet.base_mass.raw());
                    total_mass += mass;
                    const std::array exact_value{
                        value.exact_displacement_m.x / base_length_quantum_m,
                        value.exact_displacement_m.y / base_length_quantum_m,
                        value.exact_displacement_m.z / base_length_quantum_m};
                    const auto applied_value = as_base_quanta(
                        value.applied_displacement, refinement);
                    for (std::size_t axis = 0; axis < exact.size(); ++axis) {
                        exact[axis] += mass * exact_value[axis];
                        applied[axis] += mass * applied_value[axis];
                    }
                }
                std::array<double, 3> error{};
                for (std::size_t axis = 0; axis < exact.size(); ++axis) {
                    exact[axis] /= total_mass;
                    applied[axis] /= total_mass;
                    error[axis] = applied[axis] - exact[axis];
                    summary.maximum_com_component_error = std::max(
                        summary.maximum_com_component_error,
                        std::abs(error[axis]));
                }
                const auto vector_error = std::sqrt(
                    error[0] * error[0] + error[1] * error[1] +
                    error[2] * error[2]);
                summary.maximum_com_vector_error = std::max(
                    summary.maximum_com_vector_error, vector_error);
                tables.center_of_mass.row(
                    {std::to_string(refinement), std::to_string(horizon),
                     std::to_string(count), bits(total_mass), bits(exact[0]),
                     bits(exact[1]), bits(exact[2]), bits(applied[0]),
                     bits(applied[1]), bits(applied[2]), bits(error[0]),
                     bits(error[1]), bits(error[2]), bits(vector_error)});
            }
        }

        const auto impulse_found = impulse.find(refinement);
        summary.inherited_impulse =
            impulse_found != impulse.end() && impulse_found->second.passes;
        summary.passes = refinement >= 16U && summary.exact_gates &&
            summary.equal_velocity && summary.inherited_impulse &&
            summary.maximum_component_error <= 1.0 &&
            summary.maximum_vector_error <= 1.5 &&
            summary.maximum_component_spread <= 1.0 &&
            summary.maximum_vector_spread <= 1.5 &&
            summary.maximum_com_component_error <= 1.0 &&
            summary.maximum_com_vector_error <= 1.5;
        summaries.push_back(summary);
    }

    std::uint32_t selected = 0U;
    for (const auto& summary : summaries) {
        if (selected == 0U && summary.passes) {
            selected = summary.refinement;
        }
    }
    if (selected != 128U) {
        throw std::runtime_error("preregistered drift selection did not resolve to R=128");
    }

    for (const auto& summary : summaries) {
        tables.candidate_summary.row(
            {std::to_string(summary.refinement),
             bits(summary.maximum_component_error),
             bits(summary.maximum_vector_error),
             bits(summary.maximum_component_spread),
             bits(summary.maximum_vector_spread),
             bits(summary.maximum_com_component_error),
             bits(summary.maximum_com_vector_error),
             boolean(summary.exact_gates), boolean(summary.equal_velocity),
             boolean(summary.inherited_impulse), boolean(summary.passes),
             boolean(summary.refinement == selected)});
    }

    const std::array chords{
        drift::RelationChordInput{
            1, {Length::from_raw(1'000'000), {}, {}},
            {Length::from_raw(1'000'000), Length::from_raw(10), {}},
            Length::from_raw(1'000'000)},
        drift::RelationChordInput{
            2, {Length::from_raw(1'000'000), {}, {}},
            {Length::from_raw(-1'000'000), {}, {}},
            Length::from_raw(1'000'000)},
        drift::RelationChordInput{
            3, {Length::from_raw(1), {}, {}}, {Length::from_raw(1), {}, {}},
            Length::from_raw(static_cast<mls::Scalar>(1U << 25U))},
    };
    for (const auto& chord : chords) {
        const auto value = drift::evaluate_relation_chord(chord);
        tables.domain_chords.row(
            {std::to_string(chord.id),
             std::to_string(chord.initial_relative.x.raw()),
             std::to_string(chord.initial_relative.y.raw()),
             std::to_string(chord.initial_relative.z.raw()),
             std::to_string(chord.final_relative.x.raw()),
             std::to_string(chord.final_relative.y.raw()),
             std::to_string(chord.final_relative.z.raw()),
             std::to_string(chord.rest_length.raw()),
             boolean(value.interior_minimum),
             boolean(value.admissible_force_domain)});
    }

    constexpr auto maximum = std::numeric_limits<mls::Scalar>::max();
    constexpr mls::Scalar multiplier = 32;
    const auto safe = static_cast<mls::Scalar>(maximum / multiplier);
    const auto safe_result = drift::nearest_even_product_ratio(
        safe, multiplier, maximum);
    tables.overflow_controls.row(
        {"largest_safe_product", std::to_string(safe), "32",
         std::to_string(maximum), "true", std::to_string(safe_result)});
    bool overflow_rejected = false;
    try {
        static_cast<void>(drift::nearest_even_product_ratio(
            static_cast<mls::Scalar>(safe + 1), multiplier, maximum));
    } catch (const std::overflow_error&) {
        overflow_rejected = true;
    }
    tables.overflow_controls.row(
        {"adjacent_overflow", std::to_string(safe + 1), "32",
         std::to_string(maximum), boolean(!overflow_rejected), "rejected"});
    if (!overflow_rejected) {
        throw std::runtime_error("drift overflow control wrapped");
    }

    for (const auto control :
         std::array<std::array<mls::Scalar, 2>, 8>{
             {{{1, 2}}, {{3, 2}}, {{5, 2}}, {{-1, 2}},
              {{-3, 2}}, {{-5, 2}}, {{2, 3}}, {{-2, 3}}}}) {
        tables.rounding_controls.row(
            {std::to_string(control[0]), std::to_string(control[1]),
             std::to_string(drift::nearest_even_rational(control[0], control[1]))});
    }

    bool cartesian_torque = false;
    for (const auto& row : evaluation_rows) {
        if (row.value.path == drift::DriftPath::cartesian_nearest &&
            !row.value.exact_orbital_angular_momentum) {
            cartesian_torque = true;
        }
    }
    if (!cartesian_torque) {
        throw std::runtime_error("Cartesian drift negative control produced no torque");
    }

    tables.metadata.row({"schema", "mls.authoritative-drift-state-bridge.raw.v1"});
    tables.metadata.row({"accepted_parent_sha", accepted_parent_sha});
    tables.metadata.row({"accepted_parent_tag", accepted_parent_tag});
    tables.metadata.row({"accepted_parent_tag_object", accepted_parent_tag_object});
    tables.metadata.row({"source_sha", MLS_CONFIGURED_SOURCE_SHA});
    tables.metadata.row({"configured_source_branch", MLS_CONFIGURED_SOURCE_BRANCH});
    tables.metadata.row({"source_dirty", MLS_CONFIGURED_SOURCE_DIRTY});
    tables.metadata.row({"compiler_id", MLS_CONFIGURED_COMPILER_ID});
    tables.metadata.row({"compiler_version", MLS_CONFIGURED_COMPILER_VERSION});
    tables.metadata.row({"build_type", MLS_CONFIGURED_BUILD_TYPE});
    tables.metadata.row({"branch", branch});
    tables.metadata.row({"decision", decision});
    tables.metadata.row({"selected_refinement", std::to_string(selected)});
    tables.metadata.row({"selected_path", "primitive_directional"});
    tables.metadata.row({"explicit_remainder_evaluated", "false"});
    tables.metadata.row({"safe_domain", "2^-24"});
    tables.metadata.row({"cartesian_negative_control", "reject_cartesian_drift_quantization"});
    tables.metadata.row({"promotion", "NO_PROMOTION"});

    std::filesystem::create_directories(output);
    tables.metadata.write(output / "metadata.csv");
    tables.units.write(output / "units.csv");
    tables.parent_fingerprint.write(output / "parent_fingerprint.csv");
    tables.inventory.write(output / "inventory.csv");
    tables.evaluations.write(output / "evaluations.csv");
    tables.equal_velocity.write(output / "equal_velocity.csv");
    tables.center_of_mass.write(output / "center_of_mass.csv");
    tables.impulse_regression.write(output / "impulse_regression.csv");
    tables.domain_chords.write(output / "domain_chords.csv");
    tables.overflow_controls.write(output / "overflow_controls.csv");
    tables.rounding_controls.write(output / "rounding_controls.csv");
    tables.candidate_summary.write(output / "candidate_summary.csv");
}

void schema_audit() {
    Tables tables{};
    if (tables.metadata.text() != "key,value\n" ||
        tables.evaluations.text().find("packet_id,path,refinement,horizon") != 0U ||
        tables.domain_chords.text().find("id,initial_x,initial_y") != 0U) {
        throw std::runtime_error("drift raw schema inventory differs");
    }
    std::cout << "Authoritative Drift State Bridge raw schema audit: PASS\n";
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
            << "AUTHORITATIVE DRIFT STATE BRIDGE RAW COMPLETE: "
            << decision << " R=128 NO_PROMOTION\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "AUTHORITATIVE DRIFT STATE BRIDGE FAILED: "
                  << error.what() << '\n';
        return 1;
    }
}
