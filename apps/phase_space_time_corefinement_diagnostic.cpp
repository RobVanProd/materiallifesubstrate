#include "mls/phase_space_time_corefinement_lab.hpp"

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
#include <span>
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

namespace corefine = mls::experimental::phase_space_time_corefinement;
namespace drift = mls::experimental::authoritative_drift_state_bridge;
namespace mechanics = mls::experimental::authoritative_mechanics_state_bridge;
namespace observation = mls::experimental::mechanical_observability;
namespace parent = mls::experimental::time_integration_foundation;

using corefine::DynamicModel;
using corefine::DynamicPacket;
using corefine::PhaseState;
using mls::Length;
using mls::Mass;
using mls::Momentum;
using mls::Time;

constexpr auto accepted_parent_sha =
    "243d52938ef22f7bf37e4e37decbe209bec504cf";
constexpr auto accepted_parent_tag =
    "time-integration-foundation-lab-evidence-v1";
constexpr auto accepted_parent_tag_object =
    "855e89d86fa0192f7cd24a9743e545f588335c44";
constexpr auto accepted_parent_archive_sha256 =
    "d2c8f6e468a5f81c60ba4300276b6b301e1f4ab966eb4198bc4e3a02bff55dbb";
constexpr auto branch = "phase-space-time-corefinement-lab";
constexpr mls::Scalar metre = 128'000'000'000LL;
constexpr mls::Scalar kilogram = 524'288;
constexpr std::array<mls::Scalar, 5> raw_timesteps{
    62'500'000, 250'000'000, 1'000'000'000, 4'000'000'000,
    16'000'000'000};
constexpr std::array<std::uint64_t, 5> step_counts{16, 32, 64, 128, 256};

class Csv final {
public:
    explicit Csv(std::string header) : text_(std::move(header) + "\n") {}

    void row(std::initializer_list<std::string> values) {
        for (auto iterator = values.begin(); iterator != values.end(); ++iterator) {
            if (iterator != values.begin()) {
                text_ += ',';
            }
            if (iterator->find_first_of(",\"\n") == std::string::npos) {
                text_ += *iterator;
            } else {
                text_ += '"';
                for (const auto character : *iterator) {
                    if (character == '"') {
                        text_ += '"';
                    }
                    text_ += character;
                }
                text_ += '"';
            }
        }
        text_ += '\n';
    }

    void write(const std::filesystem::path& path) const {
        std::ofstream stream(path, std::ios::binary);
        if (!stream) {
            throw std::runtime_error("cannot write corefinement evidence");
        }
        stream << text_;
        if (!stream) {
            throw std::runtime_error("cannot complete corefinement evidence");
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

[[nodiscard]] std::string precise(long double value) {
    std::ostringstream stream;
    stream << std::setprecision(std::numeric_limits<long double>::max_digits10)
           << value;
    return stream.str();
}

[[nodiscard]] DynamicPacket packet(
    std::uint64_t id,
    mls::Scalar x,
    mls::Scalar y,
    mls::Scalar z,
    mls::Scalar px = 0,
    mls::Scalar py = 0,
    mls::Scalar pz = 0) {
    return {
        id,
        {Length::from_raw(x), Length::from_raw(y), Length::from_raw(z)},
        {Momentum::from_raw(px), Momentum::from_raw(py), Momentum::from_raw(pz)},
        Mass::from_raw(kilogram),
    };
}

[[nodiscard]] std::vector<DynamicPacket> k4_reference() {
    return {packet(1, 0, 0, 0), packet(2, metre, 0, 0),
            packet(3, 0, metre, 0), packet(4, 0, 0, metre)};
}

[[nodiscard]] std::vector<observation::BondRelation> k4_relations() {
    return {{1, 2}, {1, 3}, {1, 4}, {2, 3}, {2, 4}, {3, 4}};
}

[[nodiscard]] PhaseState k4_state(bool moving) {
    constexpr mls::Scalar low = -32'000'000;
    constexpr mls::Scalar high = 128'096'000'000LL;
    auto result = PhaseState{
        {},
        {packet(1, low, low, low), packet(2, high, low, low),
         packet(3, low, high, low), packet(4, low, low, high)}};
    if (moving) {
        result.packets[0].momentum = {
            Momentum::from_raw(65'536), Momentum::from_raw(-32'768),
            Momentum::from_raw(16'384)};
        result.packets[1].momentum = {
            Momentum::from_raw(-49'152), Momentum::from_raw(24'576),
            Momentum::from_raw(-8'192)};
        result.packets[2].momentum = {
            Momentum::from_raw(-8'192), Momentum::from_raw(16'384),
            Momentum::from_raw(-24'576)};
        result.packets[3].momentum = {
            Momentum::from_raw(-8'192), Momentum::from_raw(-8'192),
            Momentum::from_raw(16'384)};
    }
    return result;
}

[[nodiscard]] std::vector<DynamicPacket> octahedron_reference() {
    return {
        packet(1, metre, 0, 0), packet(2, -metre, 0, 0),
        packet(3, 0, metre, 0), packet(4, 0, -metre, 0),
        packet(5, 0, 0, metre), packet(6, 0, 0, -metre),
    };
}

[[nodiscard]] bool antipodal(
    const DynamicPacket& first,
    const DynamicPacket& second) {
    return first.position.x.raw() == -second.position.x.raw() &&
        first.position.y.raw() == -second.position.y.raw() &&
        first.position.z.raw() == -second.position.z.raw();
}

[[nodiscard]] std::vector<observation::BondRelation> octahedron_relations() {
    const auto packets = octahedron_reference();
    std::vector<observation::BondRelation> result;
    for (std::size_t first = 0; first < packets.size(); ++first) {
        for (std::size_t second = first + 1U; second < packets.size(); ++second) {
            if (!antipodal(packets[first], packets[second])) {
                result.push_back({packets[first].id, packets[second].id});
            }
        }
    }
    return result;
}

[[nodiscard]] PhaseState octahedron_state() {
    constexpr mls::Scalar scaled = 128'128'000'000LL;
    return {
        {},
        {packet(1, scaled, 0, 0), packet(2, -scaled, 0, 0),
         packet(3, 0, scaled, 0), packet(4, 0, -scaled, 0),
         packet(5, 0, 0, scaled), packet(6, 0, 0, -scaled)},
    };
}

[[nodiscard]] PhaseState translated(PhaseState state, mls::Position3 shift) {
    for (auto& value : state.packets) {
        value.position += shift;
    }
    return state;
}

[[nodiscard]] std::vector<DynamicPacket> translated_reference(
    std::vector<DynamicPacket> packets,
    mls::Position3 shift) {
    for (auto& value : packets) {
        value.position += shift;
    }
    return packets;
}

[[nodiscard]] mls::Position3 rotate(const mls::Position3& value) {
    return {-value.y, value.x, value.z};
}

[[nodiscard]] mls::Momentum3 rotate(const mls::Momentum3& value) {
    return {-value.y, value.x, value.z};
}

[[nodiscard]] mls::Position3 inverse_rotate(const mls::Position3& value) {
    return {value.y, -value.x, value.z};
}

[[nodiscard]] mls::Momentum3 inverse_rotate(const mls::Momentum3& value) {
    return {value.y, -value.x, value.z};
}

[[nodiscard]] std::vector<DynamicPacket> rotated_packets(
    std::vector<DynamicPacket> packets) {
    for (auto& value : packets) {
        value.position = rotate(value.position);
        value.momentum = rotate(value.momentum);
    }
    return packets;
}

[[nodiscard]] PhaseState boosted(PhaseState state) {
    for (auto& value : state.packets) {
        const auto boost = value.mass.raw();
        value.momentum += {
            Momentum::from_raw(boost), Momentum::from_raw(-boost),
            Momentum::from_raw(boost)};
    }
    return state;
}

struct BaseScenario final {
    std::string id;
    std::string model_id;
    PhaseState state;
    bool convergence{false};
};

struct Tables final {
    Csv metadata{"key,value"};
    Csv units{"level,Lq,Mq,Tq,Pq,Eq,Fq,dt_raw,steps,unit_contract_valid"};
    Csv parent_fingerprint{"case,observed,expected,passed"};
    Csv mapping{"scenario_id,model_id,level,status,detail"};
    Csv reference_packets{"model_id,level,packet_id,x_raw,y_raw,z_raw,mass_raw"};
    Csv relations{"model_id,relation_index,first_id,second_id,rest_length_bits"};
    Csv force_operator{"model_id,row,column,h_bits"};
    Csv initial_states{
        "scenario_id,model_id,convergence,level,packet_id,x_raw,y_raw,z_raw,px_raw,py_raw,pz_raw,mass_raw"};
    Csv endpoints{
        "scenario_id,path,level,dt_raw,steps,status,completed_steps,packet_id,time_raw,x_raw,y_raw,z_raw,px_raw,py_raw,pz_raw,momentum_preserved,angular_preserved"};
    Csv energies{
        "scenario_id,path,level,sample,dt_raw,mechanical_energy_bits"};
    Csv primitive{
        "scenario_id,path,level,step,stage,packet_id,px_raw,py_raw,pz_raw,g,ux,uy,uz,primitive_norm_squared_ld,minimum_drift_m_bits"};
    Csv relation_primitive{
        "scenario_id,path,level,step,stage,relation_index,first_id,second_id,rx_raw,ry_raw,rz_raw,g,ux,uy,uz,target_multiple_bits,applied_multiple,minimum_impulse_bits"};
    Csv reversibility{
        "scenario_id,level,dt_raw,steps,forward_status,backward_status,initial_hash,recovered_hash,bit_identical"};
    Csv covariance{
        "kind,level,dt_raw,position_discrepancy_raw,momentum_discrepancy_raw,status"};
    Csv checkpoint{
        "scenario_id,level,dt_raw,steps,checkpoint_step,checkpoint_hash,decoded_hash,whole_final_hash,resumed_final_hash,event_suffix_identical"};
    Csv domain{
        "scenario_id,level,status,failed_relation_index,first_id,second_id,time_unchanged,momentum_unchanged,state_unchanged,energy_after_evaluated"};
    Csv bridge{
        "level,unit_contract,path_b_force,equal_velocity_drift,exact_momentum,exact_angular,reversible,overflow_fail_closed,kinetic_diagnostic"};
    Csv long_energy{
        "scenario_id,level,dt_raw,sample,mechanical_energy_bits"};
};

[[nodiscard]] mls::Scalar component(
    const DynamicPacket& packet,
    bool momentum,
    std::size_t axis) {
    if (momentum) {
        return axis == 0U ? packet.momentum.x.raw() :
            (axis == 1U ? packet.momentum.y.raw() : packet.momentum.z.raw());
    }
    return axis == 0U ? packet.position.x.raw() :
        (axis == 1U ? packet.position.y.raw() : packet.position.z.raw());
}

[[nodiscard]] mls::Scalar maximum_relative_discrepancy(
    const PhaseState& first,
    const PhaseState& second,
    bool momentum) {
    if (first.packets.size() != second.packets.size()) {
        throw std::runtime_error("corefinement covariance packet count differs");
    }
    mls::Scalar maximum = 0;
    for (std::size_t index = 1; index < first.packets.size(); ++index) {
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            const auto a = mls::detail::checked_subtract(
                component(first.packets[index], momentum, axis),
                component(first.packets[0], momentum, axis));
            const auto b = mls::detail::checked_subtract(
                component(second.packets[index], momentum, axis),
                component(second.packets[0], momentum, axis));
            const auto difference = mls::detail::checked_subtract(a, b);
            if (difference == std::numeric_limits<mls::Scalar>::min()) {
                throw std::overflow_error("corefinement discrepancy magnitude overflow");
            }
            const auto magnitude = difference < 0 ? -difference : difference;
            maximum = std::max(maximum, magnitude);
        }
    }
    return maximum;
}

[[nodiscard]] PhaseState remove_boost_translation(
    PhaseState state,
    std::uint32_t level) {
    const auto momentum_factor = mls::Scalar{1} << (3U * level);
    const auto position_factor = mls::Scalar{1} << (6U * level);
    const auto displacement = mls::detail::checked_multiply(
        mls::Scalar{1'000'000'000}, position_factor);
    for (auto& value : state.packets) {
        value.position -= {
            Length::from_raw(displacement), Length::from_raw(-displacement),
            Length::from_raw(displacement)};
        const auto boost = mls::detail::checked_multiply(
            value.mass.raw(), momentum_factor);
        value.momentum -= {
            Momentum::from_raw(boost), Momentum::from_raw(-boost),
            Momentum::from_raw(boost)};
    }
    return state;
}

void export_packet(
    Csv& table,
    const BaseScenario& scenario,
    std::uint32_t level,
    const DynamicPacket& value) {
    table.row({
        scenario.id, scenario.model_id, boolean(scenario.convergence),
        std::to_string(level), std::to_string(value.id),
        std::to_string(value.position.x.raw()),
        std::to_string(value.position.y.raw()),
        std::to_string(value.position.z.raw()),
        std::to_string(value.momentum.x.raw()),
        std::to_string(value.momentum.y.raw()),
        std::to_string(value.momentum.z.raw()),
        std::to_string(value.mass.raw()),
    });
}

void export_primitive(
    Tables& tables,
    const std::string& scenario,
    corefine::IntegratorPath path,
    std::uint32_t level,
    const corefine::TrajectoryResult& trajectory,
    const corefine::UnitProfile& units) {
    const auto lq = static_cast<double>(units.length_quantum_m.numerator) /
        static_cast<double>(units.length_quantum_m.denominator);
    for (const auto& record : trajectory.primitive_records) {
        const auto& value = record.diagnostic;
        long double squared = 0.0L;
        double binary64_squared = 0.0;
        for (const auto component_value : value.primitive_direction) {
            const auto converted = static_cast<long double>(component_value);
            squared += converted * converted;
            const auto binary64_component = static_cast<double>(component_value);
            binary64_squared += binary64_component * binary64_component;
        }
        const auto minimum = lq * std::sqrt(binary64_squared);
        tables.primitive.row({
            scenario, std::string(parent::path_name(path)),
            std::to_string(level), std::to_string(record.step_index),
            std::string(parent::stage_name(record.stage)),
            std::to_string(value.packet_id),
            std::to_string(value.momentum.x.raw()),
            std::to_string(value.momentum.y.raw()),
            std::to_string(value.momentum.z.raw()),
            std::to_string(value.direction_gcd),
            std::to_string(value.primitive_direction[0]),
            std::to_string(value.primitive_direction[1]),
            std::to_string(value.primitive_direction[2]),
            precise(squared), bits(minimum),
        });
    }
}

void export_relation_primitive(
    Tables& tables,
    const std::string& scenario,
    corefine::IntegratorPath path,
    std::uint32_t level,
    const corefine::TrajectoryResult& trajectory,
    const corefine::UnitProfile& units) {
    const auto pq =
        static_cast<double>(units.momentum_quantum_kg_m_per_s.numerator) /
        static_cast<double>(units.momentum_quantum_kg_m_per_s.denominator);
    for (const auto& record : trajectory.relation_records) {
        const auto& value = record.diagnostic;
        long double squared = 0.0L;
        double binary64_squared = 0.0;
        for (const auto component_value : value.primitive_direction) {
            const auto converted = static_cast<long double>(component_value);
            squared += converted * converted;
            const auto binary64_component = static_cast<double>(component_value);
            binary64_squared += binary64_component * binary64_component;
        }
        const auto minimum = pq * std::sqrt(binary64_squared);
        tables.relation_primitive.row({
            scenario, std::string(parent::path_name(path)),
            std::to_string(level), std::to_string(record.step_index),
            std::string(parent::stage_name(record.stage)),
            std::to_string(value.relation_index),
            std::to_string(value.relation.first_id),
            std::to_string(value.relation.second_id),
            std::to_string(value.relative_position.x.raw()),
            std::to_string(value.relative_position.y.raw()),
            std::to_string(value.relative_position.z.raw()),
            std::to_string(value.direction_gcd),
            std::to_string(value.primitive_direction[0]),
            std::to_string(value.primitive_direction[1]),
            std::to_string(value.primitive_direction[2]),
            std::to_string(value.target_multiple_bits),
            std::to_string(value.applied_multiple), bits(minimum),
        });
    }
}

void export_endpoint(
    Tables& tables,
    const std::string& scenario,
    corefine::IntegratorPath path,
    std::uint32_t level,
    const corefine::TrajectoryResult& trajectory) {
    for (const auto& value : trajectory.final_state.packets) {
        tables.endpoints.row({
            scenario, std::string(parent::path_name(path)),
            std::to_string(level), std::to_string(raw_timesteps[level]),
            std::to_string(step_counts[level]),
            std::string(parent::status_name(trajectory.status)),
            std::to_string(trajectory.completed_steps), std::to_string(value.id),
            std::to_string(trajectory.final_state.physical_time.raw()),
            std::to_string(value.position.x.raw()),
            std::to_string(value.position.y.raw()),
            std::to_string(value.position.z.raw()),
            std::to_string(value.momentum.x.raw()),
            std::to_string(value.momentum.y.raw()),
            std::to_string(value.momentum.z.raw()),
            boolean(trajectory.exact_momentum_preserved),
            boolean(trajectory.exact_orbital_angular_momentum_preserved),
        });
    }
    for (std::size_t sample = 0;
         sample < trajectory.mechanical_energy_j.size(); ++sample) {
        tables.energies.row({
            scenario, std::string(parent::path_name(path)),
            std::to_string(level), std::to_string(sample),
            std::to_string(raw_timesteps[level]),
            bits(trajectory.mechanical_energy_j[sample]),
        });
    }
}

[[nodiscard]] bool basic_parent_fingerprint(Tables& tables) {
    const auto units = mechanics::mechanics_unit_contract(128);
    const mechanics::AuthoritativePacket first{1, {}, {}, Mass::from_raw(1)};
    const mechanics::AuthoritativePacket second{
        2, {Length::from_raw(1'001'000'000), {}, {}}, {}, Mass::from_raw(1)};
    const auto impulse = mechanics::evaluate_central_impulse(
        {first, second, {0.0006, 0.0, 0.0}, Time::from_raw(1'000'000'000),
         16, mechanics::QuantizationPath::fixed_point_refinement},
        units);
    const auto impulse_pass = impulse.exact_linear_momentum &&
        impulse.exact_orbital_angular_momentum;
    tables.parent_fingerprint.row(
        {"accepted_R128_impulse", boolean(impulse_pass), "true",
         boolean(impulse_pass)});
    const drift::DriftPacket value{
        3, {Length::from_raw(9), Length::from_raw(-6), Length::from_raw(3)},
        {Momentum::from_raw(-3), Momentum::from_raw(5),
         Momentum::from_raw(-7)},
        Mass::from_raw(41)};
    const auto directional = drift::evaluate_drift(
        {value, Time::from_raw(32), 32, drift::DriftPath::primitive_directional},
        units);
    const auto drift_pass = directional.exact_momentum_unchanged &&
        directional.exact_orbital_angular_momentum;
    tables.parent_fingerprint.row(
        {"accepted_R128_drift", boolean(drift_pass), "true",
         boolean(drift_pass)});
    const auto cartesian = drift::evaluate_drift(
        {value, Time::from_raw(32), 32, drift::DriftPath::cartesian_nearest},
        mechanics::mechanics_unit_contract(16));
    const auto cartesian_pass = !cartesian.exact_orbital_angular_momentum;
    tables.parent_fingerprint.row(
        {"cartesian_torque_control", boolean(cartesian_pass), "true",
         boolean(cartesian_pass)});
    const auto safe = drift::evaluate_relation_chord(
        {1, {Length::from_raw(1'000'000), {}, {}},
         {Length::from_raw(1'000'000), Length::from_raw(10), {}},
         Length::from_raw(1'000'000)}).admissible_force_domain;
    const auto crossing = !drift::evaluate_relation_chord(
        {2, {Length::from_raw(1'000'000), {}, {}},
         {Length::from_raw(-1'000'000), {}, {}},
         Length::from_raw(1'000'000)}).admissible_force_domain;
    tables.parent_fingerprint.row(
        {"safe_chord", boolean(safe), "true", boolean(safe)});
    tables.parent_fingerprint.row(
        {"crossing_chord", boolean(crossing), "true", boolean(crossing)});
    tables.parent_fingerprint.row({
        "sealed_decision", "temporal_convergence_blocked_by_authoritative_quantization",
        "temporal_convergence_blocked_by_authoritative_quantization", "true"});
    return impulse_pass && drift_pass && cartesian_pass && safe && crossing;
}

[[nodiscard]] std::vector<BaseScenario> scenarios() {
    const mls::Position3 shift{
        Length::from_raw(17 * metre), Length::from_raw(-11 * metre),
        Length::from_raw(7 * metre)};
    const auto pair_reference = std::vector<DynamicPacket>{
        packet(1, -metre, 0, 0), packet(2, metre, 0, 0)};
    auto crossing = PhaseState{{}, pair_reference};
    crossing.packets[0].momentum.x = Momentum::from_raw(134'217'728);
    crossing.packets[1].momentum.x = Momentum::from_raw(-134'217'728);
    return {
        {"k4_breathing", "k4", k4_state(false), true},
        {"k4_internal", "k4", k4_state(true), true},
        {"octahedron_deformation", "octahedron", octahedron_state(), true},
        {"k4_translated", "k4_translated", translated(k4_state(true), shift), false},
        {"k4_boosted", "k4", boosted(k4_state(true)), false},
        {"k4_rotated", "k4_rotated", {{}, rotated_packets(k4_state(true).packets)}, false},
        {"domain_crossing", "pair", crossing, false},
    };
}

[[nodiscard]] DynamicModel model_for(
    std::string_view id,
    std::uint32_t level) {
    const mls::Position3 shift{
        Length::from_raw(17 * metre), Length::from_raw(-11 * metre),
        Length::from_raw(7 * metre)};
    if (id == "k4") {
        return corefine::build_registered_model(
            k4_reference(), k4_relations(), level);
    }
    if (id == "k4_translated") {
        return corefine::build_registered_model(
            translated_reference(k4_reference(), shift), k4_relations(), level);
    }
    if (id == "k4_rotated") {
        return corefine::build_registered_model(
            rotated_packets(k4_reference()), k4_relations(), level);
    }
    if (id == "octahedron") {
        return corefine::build_registered_model(
            octahedron_reference(), octahedron_relations(), level);
    }
    if (id == "pair") {
        return corefine::build_registered_model(
            std::array{packet(1, -metre, 0, 0), packet(2, metre, 0, 0)},
            std::array{observation::BondRelation{1, 2}},
            level);
    }
    throw std::invalid_argument("unknown corefinement model");
}

void export_static_model(Tables& tables, std::string_view id) {
    const auto model = model_for(id, 0);
    const auto& force = model.frozen_force.force_operator;
    for (std::size_t index = 0; index < force.relations.size(); ++index) {
        tables.relations.row({
            std::string(id), std::to_string(index),
            std::to_string(force.relations[index].first_id),
            std::to_string(force.relations[index].second_id),
            bits(force.reference_lengths_m[index]),
        });
    }
    for (std::size_t row = 0; row < force.h_j_per_m2.row_count(); ++row) {
        for (std::size_t column = 0;
             column < force.h_j_per_m2.column_count(); ++column) {
            tables.force_operator.row({
                std::string(id), std::to_string(row), std::to_string(column),
                bits(force.h_j_per_m2(row, column)),
            });
        }
    }
}

void write_tables(const std::filesystem::path& output) {
    Tables tables{};
    if (!basic_parent_fingerprint(tables)) {
        throw std::runtime_error("stop_inconclusive_or_wrong_parent");
    }
    for (std::uint32_t level = 0; level <= corefine::maximum_level; ++level) {
        const auto units = corefine::unit_profile(level);
        tables.units.row({
            std::to_string(level), rational(units.length_quantum_m),
            rational(units.mass_quantum_kg), rational(units.time_quantum_s),
            rational(units.momentum_quantum_kg_m_per_s),
            rational(units.energy_quantum_j), rational(units.force_quantum_n),
            std::to_string(raw_timesteps[level]),
            std::to_string(step_counts[level]), "true",
        });
    }
    for (const auto id :
         {"k4", "k4_translated", "k4_rotated", "octahedron", "pair"}) {
        export_static_model(tables, id);
    }

    const auto registered = scenarios();
    for (std::uint32_t level = 0; level <= corefine::maximum_level; ++level) {
        for (const auto& scenario : registered) {
            try {
                const auto state = corefine::map_level_zero_state(
                    scenario.state, level);
                static_cast<void>(model_for(scenario.model_id, level));
                tables.mapping.row({
                    scenario.id, scenario.model_id, std::to_string(level),
                    "mapped", "exact_same_SI_state"});
                for (const auto& value : state.packets) {
                    export_packet(tables.initial_states, scenario, level, value);
                }
            } catch (const std::overflow_error& error) {
                tables.mapping.row({
                    scenario.id, scenario.model_id, std::to_string(level),
                    "signed64_overflow", error.what()});
            }
        }
        for (const auto model_id :
             {"k4", "k4_translated", "k4_rotated", "octahedron", "pair"}) {
            try {
                const auto model = model_for(model_id, level);
                for (const auto& value : model.reference_packets) {
                    tables.reference_packets.row({
                        model_id, std::to_string(level),
                        std::to_string(value.id),
                        std::to_string(value.position.x.raw()),
                        std::to_string(value.position.y.raw()),
                        std::to_string(value.position.z.raw()),
                        std::to_string(value.mass.raw()),
                    });
                }
            } catch (const std::overflow_error&) {
                // The mapping table owns the registered signed-width result.
            }
        }
    }

    const std::array paths{
        corefine::IntegratorPath::symplectic_euler_control,
        corefine::IntegratorPath::quantized_kick_drift_kick};
    for (std::uint32_t level = 0; level <= corefine::maximum_level; ++level) {
        const auto units = corefine::unit_profile(level);
        for (const auto& scenario : registered) {
            if (!scenario.convergence) {
                continue;
            }
            const auto state = corefine::map_level_zero_state(
                scenario.state, level);
            const auto model = model_for(scenario.model_id, level);
            for (const auto path : paths) {
                const auto trajectory = corefine::evaluate_trajectory(
                    model, path, state, Time::from_raw(raw_timesteps[level]),
                    step_counts[level]);
                export_endpoint(tables, scenario.id, path, level, trajectory);
                export_primitive(
                    tables, scenario.id, path, level, trajectory, units);
                export_relation_primitive(
                    tables, scenario.id, path, level, trajectory, units);
            }
        }
    }

    const auto find_scenario = [&](std::string_view id) -> const BaseScenario& {
        const auto found = std::ranges::find_if(
            registered, [id](const BaseScenario& value) { return value.id == id; });
        if (found == registered.end()) {
            throw std::runtime_error("registered corefinement scenario missing");
        }
        return *found;
    };

    for (std::uint32_t level = 0; level <= corefine::maximum_level; ++level) {
        for (const auto& scenario : registered) {
            if (scenario.id == "domain_crossing") {
                continue;
            }
            try {
                const auto initial = corefine::map_level_zero_state(
                    scenario.state, level);
                const auto model = model_for(scenario.model_id, level);
                const auto forward = corefine::evaluate_trajectory(
                    model, corefine::IntegratorPath::quantized_kick_drift_kick,
                    initial, Time::from_raw(raw_timesteps[level]),
                    step_counts[level]);
                const auto backward = corefine::evaluate_trajectory(
                    model, corefine::IntegratorPath::quantized_kick_drift_kick,
                    forward.final_state, Time::from_raw(-raw_timesteps[level]),
                    step_counts[level]);
                tables.reversibility.row({
                    scenario.id, std::to_string(level),
                    std::to_string(raw_timesteps[level]),
                    std::to_string(step_counts[level]),
                    std::string(parent::status_name(forward.status)),
                    std::string(parent::status_name(backward.status)),
                    std::to_string(parent::hash_phase_state(initial)),
                    std::to_string(parent::hash_phase_state(backward.final_state)),
                    boolean(backward.final_state == initial),
                });
            } catch (const std::overflow_error&) {
                tables.reversibility.row({
                    scenario.id, std::to_string(level),
                    std::to_string(raw_timesteps[level]),
                    std::to_string(step_counts[level]), "mapping_overflow",
                    "mapping_overflow", "0", "0", "false"});
            }
        }

        const auto& baseline = find_scenario("k4_internal");
        const auto base_initial = corefine::map_level_zero_state(
            baseline.state, level);
        const auto base_model = model_for("k4", level);
        const auto base = corefine::evaluate_trajectory(
            base_model, corefine::IntegratorPath::quantized_kick_drift_kick,
            base_initial, Time::from_raw(raw_timesteps[level]),
            step_counts[level]);
        const auto& translated_case = find_scenario("k4_translated");
        try {
            const auto shifted = corefine::evaluate_trajectory(
                model_for("k4_translated", level),
                corefine::IntegratorPath::quantized_kick_drift_kick,
                corefine::map_level_zero_state(translated_case.state, level),
                Time::from_raw(raw_timesteps[level]), step_counts[level]);
            tables.covariance.row({
                "translation", std::to_string(level),
                std::to_string(raw_timesteps[level]),
                std::to_string(maximum_relative_discrepancy(
                    base.final_state, shifted.final_state, false)),
                std::to_string(maximum_relative_discrepancy(
                    base.final_state, shifted.final_state, true)),
                "evaluated"});
        } catch (const std::overflow_error&) {
            tables.covariance.row({
                "translation", std::to_string(level),
                std::to_string(raw_timesteps[level]), "0", "0",
                "mapping_overflow"});
        }

        const auto& boost_case = find_scenario("k4_boosted");
        const auto boost_run = corefine::evaluate_trajectory(
            base_model, corefine::IntegratorPath::quantized_kick_drift_kick,
            corefine::map_level_zero_state(boost_case.state, level),
            Time::from_raw(raw_timesteps[level]), step_counts[level]);
        const auto unboosted = remove_boost_translation(
            boost_run.final_state, level);
        tables.covariance.row({
            "galilean_boost", std::to_string(level),
            std::to_string(raw_timesteps[level]),
            std::to_string(maximum_relative_discrepancy(
                base.final_state, unboosted, false)),
            std::to_string(maximum_relative_discrepancy(
                base.final_state, unboosted, true)),
            "evaluated"});
        export_primitive(
            tables, boost_case.id,
            corefine::IntegratorPath::quantized_kick_drift_kick,
            level, boost_run, corefine::unit_profile(level));
        export_relation_primitive(
            tables, boost_case.id,
            corefine::IntegratorPath::quantized_kick_drift_kick,
            level, boost_run, corefine::unit_profile(level));

        const auto& rotated_case = find_scenario("k4_rotated");
        auto rotated_run = corefine::evaluate_trajectory(
            model_for("k4_rotated", level),
            corefine::IntegratorPath::quantized_kick_drift_kick,
            corefine::map_level_zero_state(rotated_case.state, level),
            Time::from_raw(raw_timesteps[level]), step_counts[level]);
        for (auto& value : rotated_run.final_state.packets) {
            value.position = inverse_rotate(value.position);
            value.momentum = inverse_rotate(value.momentum);
        }
        tables.covariance.row({
            "proper_lattice_rotation", std::to_string(level),
            std::to_string(raw_timesteps[level]),
            std::to_string(maximum_relative_discrepancy(
                base.final_state, rotated_run.final_state, false)),
            std::to_string(maximum_relative_discrepancy(
                base.final_state, rotated_run.final_state, true)),
            "evaluated"});

        const auto checkpoint_steps = step_counts[level] / 2U;
        const auto first = corefine::evaluate_trajectory(
            base_model, corefine::IntegratorPath::quantized_kick_drift_kick,
            base_initial, Time::from_raw(raw_timesteps[level]),
            checkpoint_steps);
        const auto encoded = parent::encode_phase_checkpoint(first.final_state);
        const auto decoded = parent::decode_phase_checkpoint(encoded);
        const auto second = corefine::evaluate_trajectory(
            base_model, corefine::IntegratorPath::quantized_kick_drift_kick,
            decoded, Time::from_raw(raw_timesteps[level]), checkpoint_steps);
        bool suffix = second.event_hashes.size() == checkpoint_steps;
        for (std::size_t index = 0;
             suffix && index < second.event_hashes.size(); ++index) {
            suffix = second.event_hashes[index] ==
                base.event_hashes[index + checkpoint_steps];
        }
        tables.checkpoint.row({
            baseline.id, std::to_string(level),
            std::to_string(raw_timesteps[level]),
            std::to_string(step_counts[level]),
            std::to_string(checkpoint_steps),
            std::to_string(parent::hash_phase_state(first.final_state)),
            std::to_string(parent::hash_phase_state(decoded)),
            std::to_string(parent::hash_phase_state(base.final_state)),
            std::to_string(parent::hash_phase_state(second.final_state)),
            boolean(suffix),
        });

        const auto& crossing = find_scenario("domain_crossing");
        const auto crossing_initial = corefine::map_level_zero_state(
            crossing.state, level);
        const auto crossing_result = corefine::evaluate_step(
            model_for("pair", level),
            {corefine::IntegratorPath::quantized_kick_drift_kick,
             crossing_initial,
             Time::from_raw(static_cast<mls::Scalar>(
                 corefine::unit_profile(level).time_quantum_s.denominator))});
        tables.domain.row({
            crossing.id, std::to_string(level),
            std::string(parent::status_name(crossing_result.status)),
            std::to_string(crossing_result.failed_relation_index),
            std::to_string(crossing_result.failed_relation.first_id),
            std::to_string(crossing_result.failed_relation.second_id),
            boolean(crossing_result.next_state.physical_time ==
                crossing_initial.physical_time),
            boolean(corefine::evaluate_exact_invariants(
                        crossing_result.next_state.packets).total_momentum ==
                    corefine::evaluate_exact_invariants(
                        crossing_initial.packets).total_momentum),
            boolean(crossing_result.state_unchanged_on_rejection),
            boolean(crossing_result.energy_after.evaluated),
        });

        auto first_velocity = base_initial.packets.front();
        auto second_velocity = first_velocity;
        first_velocity.momentum = {
            Momentum::from_raw(3 * (mls::Scalar{1} << (3U * level))),
            Momentum::from_raw(-5 * (mls::Scalar{1} << (3U * level))),
            Momentum::from_raw(7 * (mls::Scalar{1} << (3U * level)))};
        second_velocity.mass = Mass::from_raw(2 * first_velocity.mass.raw());
        second_velocity.momentum = {
            first_velocity.momentum.x * 2,
            first_velocity.momentum.y * 2,
            first_velocity.momentum.z * 2};
        const auto first_drift = corefine::evaluate_directional_drift(
            first_velocity, Time::from_raw(raw_timesteps[level]));
        const auto second_drift = corefine::evaluate_directional_drift(
            second_velocity, Time::from_raw(raw_timesteps[level]));
        bool overflow_closed = false;
        try {
            auto excessive = base_initial;
            excessive.packets.front().position.x =
                Length::from_raw(std::numeric_limits<mls::Scalar>::max());
            static_cast<void>(corefine::map_level_zero_state(excessive, 1));
        } catch (const std::overflow_error&) {
            overflow_closed = true;
        }
        const auto initial_energy = corefine::evaluate_energy(
            base_model, base_initial);
        const auto bridge_backward = corefine::evaluate_trajectory(
            base_model, corefine::IntegratorPath::quantized_kick_drift_kick,
            base.final_state, Time::from_raw(-raw_timesteps[level]),
            step_counts[level]);
        tables.bridge.row({
            std::to_string(level), "true",
            boolean(base.status == corefine::StepStatus::accepted),
            boolean(first_drift == second_drift),
            boolean(base.exact_momentum_preserved),
            boolean(base.exact_orbital_angular_momentum_preserved),
            boolean(
                bridge_backward.status == corefine::StepStatus::accepted &&
                bridge_backward.final_state == base_initial),
            boolean(overflow_closed), boolean(initial_energy.evaluated),
        });

        const auto long_steps = step_counts[level] * 16U;
        const auto long_run = corefine::evaluate_trajectory(
            base_model, corefine::IntegratorPath::quantized_kick_drift_kick,
            base_initial, Time::from_raw(raw_timesteps[level]), long_steps);
        for (std::size_t sample = 0;
             sample < long_run.mechanical_energy_j.size(); ++sample) {
            tables.long_energy.row({
                baseline.id, std::to_string(level),
                std::to_string(raw_timesteps[level]), std::to_string(sample),
                bits(long_run.mechanical_energy_j[sample]),
            });
        }
    }

    tables.metadata.row(
        {"schema", "mls.phase-space-time-corefinement.raw.v1"});
    tables.metadata.row({"accepted_parent_sha", accepted_parent_sha});
    tables.metadata.row({"accepted_parent_tag", accepted_parent_tag});
    tables.metadata.row(
        {"accepted_parent_tag_object", accepted_parent_tag_object});
    tables.metadata.row(
        {"accepted_parent_archive_sha256", accepted_parent_archive_sha256});
    tables.metadata.row({"accepted_parent_archive_size", "7742347"});
    tables.metadata.row({"source_sha", MLS_CONFIGURED_SOURCE_SHA});
    tables.metadata.row(
        {"configured_source_branch", MLS_CONFIGURED_SOURCE_BRANCH});
    tables.metadata.row({"source_dirty", MLS_CONFIGURED_SOURCE_DIRTY});
    tables.metadata.row({"compiler_id", MLS_CONFIGURED_COMPILER_ID});
    tables.metadata.row({"compiler_version", MLS_CONFIGURED_COMPILER_VERSION});
    tables.metadata.row({"build_type", MLS_CONFIGURED_BUILD_TYPE});
    tables.metadata.row({"branch", branch});
    tables.metadata.row({"base_representation", "R=128"});
    tables.metadata.row({"candidate", "order_matched_space_time_corefinement"});
    tables.metadata.row({"negative_control", "fixed_R128_parent"});
    tables.metadata.row({"safe_domain", "2^-24"});
    tables.metadata.row({"authoritative_integer_width", "signed64"});
    tables.metadata.row({"diagnostic_invariant_width", "signed_magnitude_192"});
    tables.metadata.row({"position_remainder_present", "false"});
    tables.metadata.row({"impulse_remainder_present", "false"});
    tables.metadata.row({"adaptive_profile_present", "false"});
    tables.metadata.row({"energy_discrepancy_stored", "false"});
    tables.metadata.row({"promotion", "NO_PROMOTION"});

    std::filesystem::create_directories(output);
    tables.metadata.write(output / "metadata.csv");
    tables.units.write(output / "units.csv");
    tables.parent_fingerprint.write(output / "parent_fingerprint.csv");
    tables.mapping.write(output / "mapping.csv");
    tables.reference_packets.write(output / "reference_packets.csv");
    tables.relations.write(output / "relations.csv");
    tables.force_operator.write(output / "force_operator.csv");
    tables.initial_states.write(output / "initial_states.csv");
    tables.endpoints.write(output / "endpoints.csv");
    tables.energies.write(output / "energies.csv");
    tables.primitive.write(output / "primitive_diagnostics.csv");
    tables.relation_primitive.write(
        output / "relation_primitive_diagnostics.csv");
    tables.reversibility.write(output / "reversibility.csv");
    tables.covariance.write(output / "covariance.csv");
    tables.checkpoint.write(output / "checkpoint.csv");
    tables.domain.write(output / "domain.csv");
    tables.bridge.write(output / "bridge_contracts.csv");
    tables.long_energy.write(output / "long_energy.csv");
}

void schema_audit() {
    Tables tables{};
    if (tables.metadata.text() != "key,value\n" ||
        tables.units.text().find("level,Lq,Mq,Tq,Pq,Eq,Fq") != 0U ||
        tables.primitive.text().find("scenario_id,path,level,step,stage") != 0U ||
        tables.relation_primitive.text().find(
            "scenario_id,path,level,step,stage,relation_index") != 0U ||
        tables.domain.text().find("scenario_id,level,status") != 0U) {
        throw std::runtime_error("corefinement raw schema inventory differs");
    }
    std::cout << "Phase-Space/Time Co-Refinement raw schema audit: PASS\n";
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
        std::cout << "PHASE SPACE TIME COREFINEMENT RAW COMPLETE: signed64 "
                     "NO_PROMOTION\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "PHASE SPACE TIME COREFINEMENT FAILED: "
                  << error.what() << '\n';
        return 1;
    }
}
