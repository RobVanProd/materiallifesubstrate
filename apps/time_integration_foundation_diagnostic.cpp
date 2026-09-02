#include "mls/time_integration_foundation_lab.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <initializer_list>
#include <iostream>
#include <limits>
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

namespace lab = mls::experimental::time_integration_foundation;
namespace drift = mls::experimental::authoritative_drift_state_bridge;
namespace mechanics = mls::experimental::authoritative_mechanics_state_bridge;
namespace observation = mls::experimental::mechanical_observability;
using mls::Length;
using mls::Mass;
using mls::Momentum;
using mls::Time;
using lab::DynamicModel;
using lab::DynamicPacket;
using lab::PhaseState;

constexpr auto accepted_parent_sha =
    "ffefb2ea9ee0f032946af4ed23acd12883f20cfe";
constexpr auto accepted_parent_tag =
    "authoritative-drift-state-bridge-lab-evidence-v1";
constexpr auto accepted_parent_tag_object =
    "5a6237a9dcbe676aa4c89c10d5f9f94e935507e6";
constexpr auto branch = "time-integration-foundation-lab";
constexpr mls::Scalar metre = 128'000'000'000LL;
constexpr mls::Scalar kilogram = 524'288;
constexpr std::array<mls::Scalar, 5> timesteps{
    62'500'000, 31'250'000, 15'625'000, 7'812'500, 3'906'250};
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
            throw std::runtime_error("cannot write time integration evidence");
        }
        stream << text_;
        if (!stream) {
            throw std::runtime_error("cannot complete time integration evidence");
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
    const DynamicPacket& first, const DynamicPacket& second) {
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
    std::vector<DynamicPacket> packets, mls::Position3 shift) {
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

struct NamedModel final {
    std::string id;
    DynamicModel model;
};

struct Scenario final {
    std::string id;
    std::string model_id;
    PhaseState initial;
    bool convergence{false};
};

[[nodiscard]] const NamedModel& find_model(
    std::span<const NamedModel> models, std::string_view id) {
    const auto found = std::ranges::find_if(
        models, [id](const NamedModel& model) { return model.id == id; });
    if (found == models.end()) {
        throw std::runtime_error("time-map model not found");
    }
    return *found;
}

[[nodiscard]] const Scenario& find_scenario(
    std::span<const Scenario> scenarios, std::string_view id) {
    const auto found = std::ranges::find_if(
        scenarios, [id](const Scenario& scenario) { return scenario.id == id; });
    if (found == scenarios.end()) {
        throw std::runtime_error("time-map scenario not found");
    }
    return *found;
}

struct Tables final {
    Csv metadata{"key,value"};
    Csv units{"refinement,Lq,Mq,Tq,Pq,Eq,Fq"};
    Csv parent_fingerprint{"case,passed"};
    Csv rounding_controls{"numerator,denominator,nearest_even"};
    Csv reference_packets{"model_id,packet_id,x_raw,y_raw,z_raw,mass_raw"};
    Csv relations{"model_id,relation_index,first_id,second_id,rest_length_bits"};
    Csv force_operator{"model_id,row,column,h_bits"};
    Csv initial_states{
        "scenario_id,model_id,convergence,packet_id,x_raw,y_raw,z_raw,px_raw,py_raw,pz_raw,mass_raw"};
    Csv endpoints{
        "scenario_id,path,level,dt_raw,steps,status,completed_steps,packet_id,time_raw,x_raw,y_raw,z_raw,px_raw,py_raw,pz_raw,momentum_preserved,angular_preserved"};
    Csv energies{
        "scenario_id,path,level,sample,dt_raw,mechanical_energy_bits"};
    Csv reversibility{
        "scenario_id,level,dt_raw,steps,forward_status,backward_status,initial_hash,recovered_hash,bit_identical"};
    Csv covariance{
        "kind,level,dt_raw,position_discrepancy_raw,momentum_discrepancy_raw,exact"};
    Csv checkpoint{
        "scenario_id,dt_raw,steps,checkpoint_step,checkpoint_hash,decoded_hash,whole_final_hash,resumed_final_hash,event_suffix_identical"};
    Csv domain{
        "scenario_id,status,failed_relation_index,first_id,second_id,time_unchanged,momentum_unchanged,state_unchanged,energy_before_bits,energy_after_evaluated"};
    Csv long_energy{
        "scenario_id,dt_raw,sample,mechanical_energy_bits"};
};

void export_packet(
    Csv& table,
    const std::string& scenario,
    const std::string& model_id,
    bool convergence,
    const DynamicPacket& value) {
    table.row({
        scenario, model_id, boolean(convergence), std::to_string(value.id),
        std::to_string(value.position.x.raw()),
        std::to_string(value.position.y.raw()),
        std::to_string(value.position.z.raw()),
        std::to_string(value.momentum.x.raw()),
        std::to_string(value.momentum.y.raw()),
        std::to_string(value.momentum.z.raw()),
        std::to_string(value.mass.raw()),
    });
}

[[nodiscard]] bool parent_fingerprint(Tables& tables) {
    const auto units = mechanics::mechanics_unit_contract(128);
    const mechanics::AuthoritativePacket first{1, {}, {}, Mass::from_raw(1)};
    const mechanics::AuthoritativePacket second{
        2, {Length::from_raw(1'001'000'000), {}, {}}, {}, Mass::from_raw(1)};
    const auto impulse = mechanics::evaluate_central_impulse(
        {first, second, {0.0006, 0.0, 0.0}, Time::from_raw(1'000'000'000),
         16, mechanics::QuantizationPath::fixed_point_refinement}, units);
    const auto impulse_pass = impulse.exact_linear_momentum &&
        impulse.exact_orbital_angular_momentum;
    tables.parent_fingerprint.row({"accepted_R128_impulse", boolean(impulse_pass)});

    const drift::DriftPacket value{
        3, {Length::from_raw(9), Length::from_raw(-6), Length::from_raw(3)},
        {Momentum::from_raw(-3), Momentum::from_raw(5), Momentum::from_raw(-7)},
        Mass::from_raw(41)};
    const auto directional = drift::evaluate_drift(
        {value, Time::from_raw(32), 32,
         drift::DriftPath::primitive_directional}, units);
    const auto drift_pass = directional.exact_momentum_unchanged &&
        directional.exact_orbital_angular_momentum;
    tables.parent_fingerprint.row({"accepted_R128_drift", boolean(drift_pass)});
    const auto cartesian = drift::evaluate_drift(
        {value, Time::from_raw(32), 32, drift::DriftPath::cartesian_nearest},
        mechanics::mechanics_unit_contract(16));
    const auto cartesian_pass = !cartesian.exact_orbital_angular_momentum;
    tables.parent_fingerprint.row(
        {"cartesian_torque_control", boolean(cartesian_pass)});
    const auto safe = drift::evaluate_relation_chord(
        {1, {Length::from_raw(1'000'000), {}, {}},
         {Length::from_raw(1'000'000), Length::from_raw(10), {}},
         Length::from_raw(1'000'000)}).admissible_force_domain;
    const auto crossing = !drift::evaluate_relation_chord(
        {2, {Length::from_raw(1'000'000), {}, {}},
         {Length::from_raw(-1'000'000), {}, {}},
         Length::from_raw(1'000'000)}).admissible_force_domain;
    tables.parent_fingerprint.row({"safe_chord", boolean(safe)});
    tables.parent_fingerprint.row({"crossing_chord", boolean(crossing)});
    return impulse_pass && drift_pass && cartesian_pass && safe && crossing;
}

[[nodiscard]] mls::Scalar maximum_relative_discrepancy(
    const PhaseState& first, const PhaseState& second, bool momentum) {
    if (first.packets.size() != second.packets.size()) {
        throw std::runtime_error("covariance packet count differs");
    }
    mls::Scalar maximum = 0;
    for (std::size_t index = 1; index < first.packets.size(); ++index) {
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            const auto component = [&](const DynamicPacket& packet) {
                if (momentum) {
                    return axis == 0U ? packet.momentum.x.raw() :
                        (axis == 1U ? packet.momentum.y.raw() :
                         packet.momentum.z.raw());
                }
                return axis == 0U ? packet.position.x.raw() :
                    (axis == 1U ? packet.position.y.raw() :
                     packet.position.z.raw());
            };
            const auto a = mls::detail::checked_subtract(
                component(first.packets[index]), component(first.packets[0]));
            const auto b = mls::detail::checked_subtract(
                component(second.packets[index]), component(second.packets[0]));
            const auto difference = mls::detail::checked_subtract(a, b);
            const auto magnitude = difference < 0 ? -difference : difference;
            maximum = std::max(maximum, magnitude);
        }
    }
    return maximum;
}

[[nodiscard]] PhaseState remove_boost_translation(
    const PhaseState& boosted_state,
    mls::Scalar elapsed_raw) {
    auto result = boosted_state;
    const auto displacement = elapsed_raw;
    for (auto& value : result.packets) {
        value.position -= {
            Length::from_raw(displacement), Length::from_raw(-displacement),
            Length::from_raw(displacement)};
        const auto boost = value.mass.raw();
        value.momentum -= {
            Momentum::from_raw(boost), Momentum::from_raw(-boost),
            Momentum::from_raw(boost)};
    }
    return result;
}

void write_tables(const std::filesystem::path& output) {
    Tables tables{};
    if (!parent_fingerprint(tables)) {
        throw std::runtime_error("stop_inconclusive_or_wrong_parent");
    }
    for (const auto control :
         std::array<std::array<mls::Scalar, 2>, 8>{
             {{{1, 2}}, {{3, 2}}, {{5, 2}}, {{-1, 2}},
              {{-3, 2}}, {{-5, 2}}, {{2, 3}}, {{-2, 3}}}}) {
        tables.rounding_controls.row({
            std::to_string(control[0]), std::to_string(control[1]),
            std::to_string(drift::nearest_even_rational(
                control[0], control[1]))});
    }
    const auto units = mechanics::mechanics_unit_contract(128);
    tables.units.row({
        "128", rational(units.length_quantum_m), rational(units.mass_quantum_kg),
        rational(units.time_quantum_s),
        rational(units.momentum_quantum_kg_m_per_s),
        rational(units.energy_quantum_j), rational(units.force_quantum_n)});

    const mls::Position3 translation{
        Length::from_raw(17 * metre), Length::from_raw(-11 * metre),
        Length::from_raw(7 * metre)};
    const auto k4_ref = k4_reference();
    const auto k4_edges = k4_relations();
    const auto translated_ref = translated_reference(k4_ref, translation);
    const auto rotated_ref = rotated_packets(k4_ref);
    const auto octa_ref = octahedron_reference();
    const auto octa_edges = octahedron_relations();
    const auto pair_ref = std::vector<DynamicPacket>{
        packet(1, -metre, 0, 0), packet(2, metre, 0, 0)};
    const std::array pair_edge{observation::BondRelation{1, 2}};
    const std::vector<NamedModel> models{
        {"k4", lab::build_registered_model(k4_ref, k4_edges)},
        {"k4_translated", lab::build_registered_model(translated_ref, k4_edges)},
        {"k4_rotated", lab::build_registered_model(rotated_ref, k4_edges)},
        {"octahedron", lab::build_registered_model(octa_ref, octa_edges)},
        {"pair", lab::build_registered_model(pair_ref, pair_edge)},
    };

    auto crossing = PhaseState{{}, pair_ref};
    crossing.packets[0].momentum.x = Momentum::from_raw(134'217'728);
    crossing.packets[1].momentum.x = Momentum::from_raw(-134'217'728);
    const std::vector<Scenario> scenarios{
        {"k4_breathing", "k4", k4_state(false), true},
        {"k4_internal", "k4", k4_state(true), true},
        {"octahedron_deformation", "octahedron", octahedron_state(), true},
        {"k4_translated", "k4_translated", translated(k4_state(true), translation), false},
        {"k4_boosted", "k4", boosted(k4_state(true)), false},
        {"k4_rotated", "k4_rotated", {{}, rotated_packets(k4_state(true).packets)}, false},
        {"domain_crossing", "pair", crossing, false},
    };

    for (const auto& named : models) {
        for (const auto& value : named.model.reference_packets) {
            tables.reference_packets.row({
                named.id, std::to_string(value.id),
                std::to_string(value.position.x.raw()),
                std::to_string(value.position.y.raw()),
                std::to_string(value.position.z.raw()),
                std::to_string(value.mass.raw())});
        }
        const auto& energy = named.model.frozen_force.force_operator;
        for (std::size_t index = 0; index < energy.relations.size(); ++index) {
            tables.relations.row({
                named.id, std::to_string(index),
                std::to_string(energy.relations[index].first_id),
                std::to_string(energy.relations[index].second_id),
                bits(energy.reference_lengths_m[index])});
        }
        for (std::size_t row = 0; row < energy.h_j_per_m2.row_count(); ++row) {
            for (std::size_t column = 0;
                 column < energy.h_j_per_m2.column_count(); ++column) {
                tables.force_operator.row({
                    named.id, std::to_string(row), std::to_string(column),
                    bits(energy.h_j_per_m2(row, column))});
            }
        }
    }
    for (const auto& scenario : scenarios) {
        for (const auto& value : scenario.initial.packets) {
            export_packet(
                tables.initial_states, scenario.id, scenario.model_id,
                scenario.convergence, value);
        }
    }

    const auto paths = std::array{
        lab::IntegratorPath::symplectic_euler_control,
        lab::IntegratorPath::quantized_kick_drift_kick};
    for (const auto& scenario : scenarios) {
        if (!scenario.convergence) {
            continue;
        }
        const auto& model = find_model(models, scenario.model_id).model;
        for (std::size_t level = 0; level < timesteps.size(); ++level) {
            for (const auto path : paths) {
                const auto trajectory = lab::evaluate_trajectory(
                    model, path, scenario.initial,
                    Time::from_raw(timesteps[level]), step_counts[level]);
                for (const auto& value : trajectory.final_state.packets) {
                    tables.endpoints.row({
                        scenario.id, std::string(lab::path_name(path)),
                        std::to_string(level), std::to_string(timesteps[level]),
                        std::to_string(step_counts[level]),
                        std::string(lab::status_name(trajectory.status)),
                        std::to_string(trajectory.completed_steps),
                        std::to_string(value.id),
                        std::to_string(trajectory.final_state.physical_time.raw()),
                        std::to_string(value.position.x.raw()),
                        std::to_string(value.position.y.raw()),
                        std::to_string(value.position.z.raw()),
                        std::to_string(value.momentum.x.raw()),
                        std::to_string(value.momentum.y.raw()),
                        std::to_string(value.momentum.z.raw()),
                        boolean(trajectory.exact_momentum_preserved),
                        boolean(trajectory.exact_orbital_angular_momentum_preserved)});
                }
                for (std::size_t sample = 0;
                     sample < trajectory.mechanical_energy_j.size(); ++sample) {
                    tables.energies.row({
                        scenario.id, std::string(lab::path_name(path)),
                        std::to_string(level), std::to_string(sample),
                        std::to_string(timesteps[level]),
                        bits(trajectory.mechanical_energy_j[sample])});
                }
            }
        }
    }

    for (const auto& scenario : scenarios) {
        if (scenario.id == "domain_crossing") {
            continue;
        }
        const auto& model = find_model(models, scenario.model_id).model;
        for (std::size_t level = 0; level < timesteps.size(); ++level) {
            const auto forward = lab::evaluate_trajectory(
                model, lab::IntegratorPath::quantized_kick_drift_kick,
                scenario.initial, Time::from_raw(timesteps[level]),
                step_counts[level]);
            const auto backward = lab::evaluate_trajectory(
                model, lab::IntegratorPath::quantized_kick_drift_kick,
                forward.final_state, Time::from_raw(-timesteps[level]),
                step_counts[level]);
            tables.reversibility.row({
                scenario.id, std::to_string(level),
                std::to_string(timesteps[level]),
                std::to_string(step_counts[level]),
                std::string(lab::status_name(forward.status)),
                std::string(lab::status_name(backward.status)),
                std::to_string(lab::hash_phase_state(scenario.initial)),
                std::to_string(lab::hash_phase_state(backward.final_state)),
                boolean(backward.final_state == scenario.initial)});
        }
    }

    const auto& baseline = find_scenario(scenarios, "k4_internal");
    const auto& translated_case = find_scenario(scenarios, "k4_translated");
    const auto& boosted_case = find_scenario(scenarios, "k4_boosted");
    const auto& rotated_case = find_scenario(scenarios, "k4_rotated");
    for (std::size_t level = 0; level < timesteps.size(); ++level) {
        const auto base = lab::evaluate_trajectory(
            find_model(models, baseline.model_id).model,
            lab::IntegratorPath::quantized_kick_drift_kick,
            baseline.initial, Time::from_raw(timesteps[level]),
            step_counts[level]);
        const auto shifted = lab::evaluate_trajectory(
            find_model(models, translated_case.model_id).model,
            lab::IntegratorPath::quantized_kick_drift_kick,
            translated_case.initial, Time::from_raw(timesteps[level]),
            step_counts[level]);
        const auto translation_x = maximum_relative_discrepancy(
            base.final_state, shifted.final_state, false);
        const auto translation_p = maximum_relative_discrepancy(
            base.final_state, shifted.final_state, true);
        tables.covariance.row({
            "translation", std::to_string(level),
            std::to_string(timesteps[level]), std::to_string(translation_x),
            std::to_string(translation_p),
            boolean(translation_x == 0 && translation_p == 0)});

        const auto boost_run = lab::evaluate_trajectory(
            find_model(models, boosted_case.model_id).model,
            lab::IntegratorPath::quantized_kick_drift_kick,
            boosted_case.initial, Time::from_raw(timesteps[level]),
            step_counts[level]);
        const auto unboosted = remove_boost_translation(
            boost_run.final_state, 1'000'000'000);
        const auto boost_x = maximum_relative_discrepancy(
            base.final_state, unboosted, false);
        const auto boost_p = maximum_relative_discrepancy(
            base.final_state, unboosted, true);
        tables.covariance.row({
            "galilean_boost", std::to_string(level),
            std::to_string(timesteps[level]), std::to_string(boost_x),
            std::to_string(boost_p), boolean(boost_x == 0 && boost_p == 0)});

        auto rotated_run = lab::evaluate_trajectory(
            find_model(models, rotated_case.model_id).model,
            lab::IntegratorPath::quantized_kick_drift_kick,
            rotated_case.initial, Time::from_raw(timesteps[level]),
            step_counts[level]);
        for (auto& value : rotated_run.final_state.packets) {
            value.position = inverse_rotate(value.position);
            value.momentum = inverse_rotate(value.momentum);
        }
        const auto rotation_x = maximum_relative_discrepancy(
            base.final_state, rotated_run.final_state, false);
        const auto rotation_p = maximum_relative_discrepancy(
            base.final_state, rotated_run.final_state, true);
        tables.covariance.row({
            "proper_lattice_rotation", std::to_string(level),
            std::to_string(timesteps[level]), std::to_string(rotation_x),
            std::to_string(rotation_p),
            boolean(rotation_x == 0 && rotation_p == 0)});
    }

    const auto whole = lab::evaluate_trajectory(
        find_model(models, "k4").model,
        lab::IntegratorPath::quantized_kick_drift_kick,
        baseline.initial, Time::from_raw(15'625'000), 64);
    const auto first_half = lab::evaluate_trajectory(
        find_model(models, "k4").model,
        lab::IntegratorPath::quantized_kick_drift_kick,
        baseline.initial, Time::from_raw(15'625'000), 32);
    const auto checkpoint_bytes = lab::encode_phase_checkpoint(first_half.final_state);
    const auto decoded = lab::decode_phase_checkpoint(checkpoint_bytes);
    const auto second_half = lab::evaluate_trajectory(
        find_model(models, "k4").model,
        lab::IntegratorPath::quantized_kick_drift_kick,
        decoded, Time::from_raw(15'625'000), 32);
    bool suffix_identical = second_half.event_hashes.size() == 32U;
    for (std::size_t index = 0; suffix_identical && index < 32U; ++index) {
        suffix_identical = second_half.event_hashes[index] ==
            whole.event_hashes[index + 32U];
    }
    tables.checkpoint.row({
        baseline.id, "15625000", "64", "32",
        std::to_string(lab::hash_phase_state(first_half.final_state)),
        std::to_string(lab::hash_phase_state(decoded)),
        std::to_string(lab::hash_phase_state(whole.final_state)),
        std::to_string(lab::hash_phase_state(second_half.final_state)),
        boolean(suffix_identical)});

    const auto& domain_case = find_scenario(scenarios, "domain_crossing");
    const auto domain_energy = lab::evaluate_energy(
        find_model(models, "pair").model, domain_case.initial);
    const auto crossing_step = lab::evaluate_step(
        find_model(models, "pair").model,
        {lab::IntegratorPath::quantized_kick_drift_kick,
         domain_case.initial, Time::from_raw(1'000'000'000)});
    tables.domain.row({
        domain_case.id, std::string(lab::status_name(crossing_step.status)),
        std::to_string(crossing_step.failed_relation_index),
        std::to_string(crossing_step.failed_relation.first_id),
        std::to_string(crossing_step.failed_relation.second_id),
        boolean(crossing_step.next_state.physical_time ==
            domain_case.initial.physical_time),
        boolean(lab::evaluate_exact_invariants(crossing_step.next_state.packets)
                    .total_momentum ==
                lab::evaluate_exact_invariants(domain_case.initial.packets)
                    .total_momentum),
        boolean(crossing_step.state_unchanged_on_rejection),
        bits(domain_energy.mechanical_energy_j),
        boolean(crossing_step.energy_after.evaluated)});

    const auto long_run = lab::evaluate_trajectory(
        find_model(models, "k4").model,
        lab::IntegratorPath::quantized_kick_drift_kick,
        baseline.initial, Time::from_raw(15'625'000), 1024);
    for (std::size_t sample = 0;
         sample < long_run.mechanical_energy_j.size(); ++sample) {
        tables.long_energy.row({
            baseline.id, "15625000", std::to_string(sample),
            bits(long_run.mechanical_energy_j[sample])});
    }

    tables.metadata.row({"schema", "mls.time-integration-foundation.raw.v1"});
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
    tables.metadata.row({"selected_refinement", "128"});
    tables.metadata.row({"candidate", "quantized_kick_drift_kick"});
    tables.metadata.row({"negative_control", "symplectic_euler_control"});
    tables.metadata.row({"safe_domain", "2^-24"});
    tables.metadata.row({"position_remainder_present", "false"});
    tables.metadata.row({"energy_discrepancy_stored", "false"});
    tables.metadata.row({"promotion", "NO_PROMOTION"});

    std::filesystem::create_directories(output);
    tables.metadata.write(output / "metadata.csv");
    tables.units.write(output / "units.csv");
    tables.parent_fingerprint.write(output / "parent_fingerprint.csv");
    tables.rounding_controls.write(output / "rounding_controls.csv");
    tables.reference_packets.write(output / "reference_packets.csv");
    tables.relations.write(output / "relations.csv");
    tables.force_operator.write(output / "force_operator.csv");
    tables.initial_states.write(output / "initial_states.csv");
    tables.endpoints.write(output / "endpoints.csv");
    tables.energies.write(output / "energies.csv");
    tables.reversibility.write(output / "reversibility.csv");
    tables.covariance.write(output / "covariance.csv");
    tables.checkpoint.write(output / "checkpoint.csv");
    tables.domain.write(output / "domain.csv");
    tables.long_energy.write(output / "long_energy.csv");
}

void schema_audit() {
    Tables tables{};
    if (tables.metadata.text() != "key,value\n" ||
        tables.endpoints.text().find("scenario_id,path,level,dt_raw") != 0U ||
        tables.domain.text().find("scenario_id,status,failed_relation_index") != 0U) {
        throw std::runtime_error("time integration raw schema inventory differs");
    }
    std::cout << "Time Integration Foundation raw schema audit: PASS\n";
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
        std::cout << "TIME INTEGRATION FOUNDATION RAW COMPLETE: R=128 "
                     "NO_PROMOTION\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "TIME INTEGRATION FOUNDATION FAILED: "
                  << error.what() << '\n';
        return 1;
    }
}
