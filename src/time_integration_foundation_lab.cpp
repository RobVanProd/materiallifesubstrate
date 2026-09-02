#include "mls/time_integration_foundation_lab.hpp"

#include "mls/constitutive_expressivity_lab.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <limits>
#include <map>
#include <numeric>
#include <stdexcept>
#include <type_traits>

namespace mls::experimental::time_integration_foundation {
namespace {

using observation::BondRelation;
using observation::MechanicalPacket;

[[nodiscard]] double rational_value(
    mechanics::PositiveRational value) noexcept {
    return static_cast<double>(value.numerator) /
        static_cast<double>(value.denominator);
}

[[nodiscard]] Scalar absolute_for_gcd(Scalar value) {
    if (value == std::numeric_limits<Scalar>::min()) {
        throw std::overflow_error("time-map primitive magnitude overflow");
    }
    return value < 0 ? static_cast<Scalar>(-value) : value;
}

[[nodiscard]] Scalar component(const Position3& value, std::size_t axis) {
    return axis == 0U ? value.x.raw() :
        (axis == 1U ? value.y.raw() : value.z.raw());
}

[[nodiscard]] Scalar component(const Momentum3& value, std::size_t axis) {
    return axis == 0U ? value.x.raw() :
        (axis == 1U ? value.y.raw() : value.z.raw());
}

[[nodiscard]] Position3 make_position(const std::array<Scalar, 3>& value) {
    return {Length::from_raw(value[0]), Length::from_raw(value[1]),
            Length::from_raw(value[2])};
}

[[nodiscard]] Momentum3 make_momentum(const std::array<Scalar, 3>& value) {
    return {Momentum::from_raw(value[0]), Momentum::from_raw(value[1]),
            Momentum::from_raw(value[2])};
}

[[nodiscard]] std::vector<DynamicPacket> canonical_packets(
    std::span<const DynamicPacket> packets) {
    std::vector<DynamicPacket> result(packets.begin(), packets.end());
    std::ranges::sort(result, {}, &DynamicPacket::id);
    for (std::size_t index = 0; index < result.size(); ++index) {
        if (result[index].id == 0U || result[index].mass.raw() <= 0 ||
            (index != 0U && result[index - 1U].id == result[index].id)) {
            throw std::invalid_argument(
                "time-map packets require unique positive IDs and mass");
        }
    }
    return result;
}

[[nodiscard]] std::map<std::uint64_t, std::size_t> lookup(
    std::span<const DynamicPacket> packets) {
    std::map<std::uint64_t, std::size_t> result;
    for (std::size_t index = 0; index < packets.size(); ++index) {
        result.emplace(packets[index].id, index);
    }
    return result;
}

[[nodiscard]] MechanicalPacket mapped_packet(
    const DynamicPacket& packet,
    const mechanics::MechanicsUnitContract& units) {
    const auto lq = rational_value(units.length_quantum_m);
    return {
        packet.id,
        packet.mass.raw(),
        {static_cast<double>(packet.position.x.raw()) * lq,
         static_cast<double>(packet.position.y.raw()) * lq,
         static_cast<double>(packet.position.z.raw()) * lq},
        {},
    };
}

[[nodiscard]] std::vector<MechanicalPacket> mapped_packets(
    std::span<const DynamicPacket> packets,
    const mechanics::MechanicsUnitContract& units) {
    std::vector<MechanicalPacket> result;
    result.reserve(packets.size());
    for (const auto& packet : packets) {
        result.push_back(mapped_packet(packet, units));
    }
    return result;
}

[[nodiscard]] std::array<Scalar, 3> primitive_direction(
    const Position3& first, const Position3& second) {
    const auto offset = second - first;
    auto divisor = std::gcd(
        absolute_for_gcd(offset.x.raw()),
        absolute_for_gcd(offset.y.raw()));
    divisor = std::gcd(divisor, absolute_for_gcd(offset.z.raw()));
    if (divisor == 0) {
        throw std::domain_error("time-map central kick requires separation");
    }
    return {offset.x.raw() / divisor, offset.y.raw() / divisor,
            offset.z.raw() / divisor};
}

[[nodiscard]] Scalar nearest_even_binary64(double value) {
    if (!std::isfinite(value) ||
        value < static_cast<double>(std::numeric_limits<Scalar>::min()) ||
        value > static_cast<double>(std::numeric_limits<Scalar>::max())) {
        throw std::overflow_error("time-map impulse multiple outside range");
    }
    const auto lower = std::floor(value);
    const auto fraction = value - lower;
    auto result = static_cast<Scalar>(lower);
    if (fraction > 0.5 ||
        (fraction == 0.5 && result % static_cast<Scalar>(2) != 0)) {
        result = detail::checked_add(result, 1);
    }
    return result;
}

[[nodiscard]] Momentum3 impulse_from_direction(
    const std::array<Scalar, 3>& direction, Scalar multiple) {
    return make_momentum({
        detail::checked_multiply(direction[0], multiple),
        detail::checked_multiply(direction[1], multiple),
        detail::checked_multiply(direction[2], multiple),
    });
}

struct KickResult final {
    StepStatus status{StepStatus::arithmetic_failure};
    std::vector<DynamicPacket> packets{};
    std::size_t failed_relation_index{
        std::numeric_limits<std::size_t>::max()};
    BondRelation failed_relation{};
};

[[nodiscard]] KickResult kick(
    const DynamicModel& model,
    std::span<const DynamicPacket> input_packets,
    Time interval,
    const mechanics::MechanicsUnitContract& units) {
    auto packets = canonical_packets(input_packets);
    const auto reference = mapped_packets(model.reference_packets, units);
    const auto current = mapped_packets(packets, units);
    const auto evaluated = geometry::evaluate_resolved_spatial_force(
        model.frozen_force, reference, current,
        geometry::GeometryPath::cancellation_resistant_binary64);
    if (evaluated.status != geometry::ResolvedForceStatus::evaluated) {
        return {
            StepStatus::force_domain_failure, {}, evaluated.failed_relation_index,
            evaluated.failed_relation};
    }
    const auto by_id = lookup(packets);
    const auto pq = rational_value(units.momentum_quantum_kg_m_per_s);
    const auto dt = static_cast<double>(interval.raw()) *
        rational_value(units.time_quantum_s);

    for (const auto& relation : evaluated.relation_coordinates) {
        const auto first_index = by_id.at(relation.relation.first_id);
        const auto second_index = by_id.at(relation.relation.second_id);
        const auto direction = primitive_direction(
            packets[first_index].position, packets[second_index].position);
        const Vec3d raw_direction{
            static_cast<double>(direction[0]),
            static_cast<double>(direction[1]),
            static_cast<double>(direction[2])};
        const auto direction_squared = dot(raw_direction, raw_direction);
        const auto relation_force =
            relation.conjugate_force_n *
            relation.geometry.direction_first_to_second;
        const auto target_multiple =
            dt * dot(relation_force, raw_direction) /
            (pq * direction_squared);
        const auto multiple = nearest_even_binary64(target_multiple);
        const auto impulse = impulse_from_direction(direction, multiple);
        packets[first_index].momentum += impulse;
        packets[second_index].momentum -= impulse;
    }
    return {StepStatus::accepted, std::move(packets), {}, {}};
}

[[nodiscard]] Position3 drift_displacement(
    const DynamicPacket& packet, Time timestep) {
    auto divisor = std::gcd(
        absolute_for_gcd(packet.momentum.x.raw()),
        absolute_for_gcd(packet.momentum.y.raw()));
    divisor = std::gcd(divisor, absolute_for_gcd(packet.momentum.z.raw()));
    if (divisor == 0) {
        return {};
    }
    const std::array<Scalar, 3> direction{
        packet.momentum.x.raw() / divisor,
        packet.momentum.y.raw() / divisor,
        packet.momentum.z.raw() / divisor};
    const auto multiple = drift::nearest_even_product_ratio(
        divisor, timestep.raw(), packet.mass.raw());
    return make_position({
        detail::checked_multiply(direction[0], multiple),
        detail::checked_multiply(direction[1], multiple),
        detail::checked_multiply(direction[2], multiple),
    });
}

[[nodiscard]] bool chord_is_admissible(
    const Position3& initial,
    const Position3& final,
    const Position3& reference) {
    std::array<long double, 3> a{};
    std::array<long double, 3> d{};
    std::array<long double, 3> r{};
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        a[axis] = static_cast<long double>(component(initial, axis));
        d[axis] = static_cast<long double>(detail::checked_subtract(
            component(final, axis), component(initial, axis)));
        r[axis] = static_cast<long double>(component(reference, axis));
    }
    long double delta_squared = 0.0L;
    long double initial_dot_delta = 0.0L;
    long double reference_squared = 0.0L;
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        delta_squared += d[axis] * d[axis];
        initial_dot_delta += a[axis] * d[axis];
        reference_squared += r[axis] * r[axis];
    }
    if (!(reference_squared > 0.0L)) {
        throw std::invalid_argument("time-map reference relation is coincident");
    }
    auto parameter = 0.0L;
    if (delta_squared > 0.0L) {
        parameter = std::clamp(
            -initial_dot_delta / delta_squared, 0.0L, 1.0L);
    }
    long double minimum_squared = 0.0L;
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        const auto value = a[axis] + parameter * d[axis];
        minimum_squared += value * value;
    }
    return minimum_squared / reference_squared >= std::ldexp(1.0L, -48);
}

struct DomainResult final {
    bool admissible{true};
    std::size_t failed_relation_index{
        std::numeric_limits<std::size_t>::max()};
    BondRelation failed_relation{};
};

[[nodiscard]] DomainResult check_chords(
    const DynamicModel& model,
    std::span<const DynamicPacket> initial,
    std::span<const DynamicPacket> final) {
    const auto initial_by_id = lookup(initial);
    const auto final_by_id = lookup(final);
    const auto reference_by_id = lookup(model.reference_packets);
    const auto& relations = model.frozen_force.force_operator.relations;
    for (std::size_t index = 0; index < relations.size(); ++index) {
        const auto relation = relations[index];
        const auto initial_relative =
            initial[initial_by_id.at(relation.second_id)].position -
            initial[initial_by_id.at(relation.first_id)].position;
        const auto final_relative =
            final[final_by_id.at(relation.second_id)].position -
            final[final_by_id.at(relation.first_id)].position;
        const auto reference_relative =
            model.reference_packets[reference_by_id.at(relation.second_id)].position -
            model.reference_packets[reference_by_id.at(relation.first_id)].position;
        if (!chord_is_admissible(
                initial_relative, final_relative, reference_relative)) {
            return {false, index, relation};
        }
    }
    return {};
}

[[nodiscard]] PhaseState with_packets(
    const PhaseState& state, std::vector<DynamicPacket> packets) {
    return {state.physical_time, std::move(packets)};
}

void append_stage(
    std::vector<StageRecord>& stages,
    StageKind kind,
    const PhaseState& state) {
    stages.push_back(
        {kind, evaluate_exact_invariants(state.packets), hash_phase_state(state)});
}

[[nodiscard]] std::uint64_t fnv_byte(
    std::uint64_t hash, std::uint8_t byte) noexcept {
    return (hash ^ byte) * UINT64_C(1099511628211);
}

void append_u32(std::vector<std::uint8_t>& bytes, std::uint32_t value) {
    for (unsigned int shift = 0; shift < 32U; shift += 8U) {
        bytes.push_back(static_cast<std::uint8_t>((value >> shift) & 0xffU));
    }
}

void append_u64(std::vector<std::uint8_t>& bytes, std::uint64_t value) {
    for (unsigned int shift = 0; shift < 64U; shift += 8U) {
        bytes.push_back(static_cast<std::uint8_t>((value >> shift) & 0xffU));
    }
}

void append_i64(std::vector<std::uint8_t>& bytes, Scalar value) {
    append_u64(bytes, std::bit_cast<std::uint64_t>(value));
}

[[nodiscard]] std::uint32_t read_u32(
    std::span<const std::uint8_t> bytes, std::size_t& cursor) {
    if (cursor + 4U > bytes.size()) {
        throw std::invalid_argument("truncated time-map checkpoint");
    }
    std::uint32_t result = 0U;
    for (unsigned int shift = 0; shift < 32U; shift += 8U) {
        result |= static_cast<std::uint32_t>(bytes[cursor++]) << shift;
    }
    return result;
}

[[nodiscard]] std::uint64_t read_u64(
    std::span<const std::uint8_t> bytes, std::size_t& cursor) {
    if (cursor + 8U > bytes.size()) {
        throw std::invalid_argument("truncated time-map checkpoint");
    }
    std::uint64_t result = 0U;
    for (unsigned int shift = 0; shift < 64U; shift += 8U) {
        result |= static_cast<std::uint64_t>(bytes[cursor++]) << shift;
    }
    return result;
}

[[nodiscard]] Scalar read_i64(
    std::span<const std::uint8_t> bytes, std::size_t& cursor) {
    return std::bit_cast<Scalar>(read_u64(bytes, cursor));
}

} // namespace

std::string_view path_name(IntegratorPath path) noexcept {
    switch (path) {
    case IntegratorPath::symplectic_euler_control:
        return "symplectic_euler_control";
    case IntegratorPath::quantized_kick_drift_kick:
        return "quantized_kick_drift_kick";
    }
    return "unknown";
}

std::string_view status_name(StepStatus status) noexcept {
    switch (status) {
    case StepStatus::accepted:
        return "accepted";
    case StepStatus::initial_domain_failure:
        return "initial_domain_failure";
    case StepStatus::force_domain_failure:
        return "force_domain_failure";
    case StepStatus::chord_domain_failure:
        return "chord_domain_failure";
    case StepStatus::invariant_failure:
        return "invariant_failure";
    case StepStatus::arithmetic_failure:
        return "arithmetic_failure";
    }
    return "unknown";
}

std::string_view stage_name(StageKind stage) noexcept {
    switch (stage) {
    case StageKind::initial:
        return "initial";
    case StageKind::first_kick:
        return "first_kick";
    case StageKind::drift:
        return "drift";
    case StageKind::second_kick:
        return "second_kick";
    case StageKind::committed:
        return "committed";
    case StageKind::rejected:
        return "rejected";
    }
    return "unknown";
}

DynamicModel build_registered_model(
    std::span<const DynamicPacket> reference_packets,
    std::span<const BondRelation> relations) {
    const auto units = mechanics::mechanics_unit_contract(selected_refinement);
    auto exact_reference = canonical_packets(reference_packets);
    const auto mapped_reference = mapped_packets(exact_reference, units);
    std::vector<constitutive_expressivity::WeightedRelation> weighted;
    weighted.reserve(relations.size());
    for (const auto relation : relations) {
        weighted.push_back({relation, 1.0});
    }
    auto energy = constitutive_expressivity::build_local_collective_energy(
        mapped_reference, weighted,
        {.dilatational_coefficient_j_per_m2 = 0.3,
         .deviatoric_coefficient_j_per_m2 = 0.25});
    return {
        std::move(exact_reference),
        force::freeze_symmetric_force_operator(energy),
    };
}

ExactInvariants evaluate_exact_invariants(
    std::span<const DynamicPacket> packets) {
    ExactInvariants result{};
    for (const auto& packet : packets) {
        result.total_momentum += packet.momentum;
        result.orbital_angular_momentum += cross(
            packet.position, packet.momentum);
    }
    return result;
}

EnergyDiagnostic evaluate_energy(
    const DynamicModel& model,
    const PhaseState& state) {
    const auto units = mechanics::mechanics_unit_contract(selected_refinement);
    const auto packets = canonical_packets(state.packets);
    const auto mapped_reference = mapped_packets(model.reference_packets, units);
    const auto mapped_current = mapped_packets(packets, units);
    const auto force_value = geometry::evaluate_resolved_spatial_force(
        model.frozen_force, mapped_reference, mapped_current,
        geometry::GeometryPath::cancellation_resistant_binary64);
    if (force_value.status != geometry::ResolvedForceStatus::evaluated) {
        return {};
    }
    const auto pq = static_cast<long double>(
        rational_value(units.momentum_quantum_kg_m_per_s));
    const auto mq = static_cast<long double>(
        rational_value(units.mass_quantum_kg));
    long double kinetic = 0.0L;
    Energy floored{};
    for (const auto& packet : packets) {
        long double squared_momentum = 0.0L;
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            const auto p = static_cast<long double>(
                component(packet.momentum, axis)) * pq;
            squared_momentum += p * p;
        }
        kinetic += squared_momentum /
            (2.0L * static_cast<long double>(packet.mass.raw()) * mq);
        floored += kinetic_energy_of(packet.mass, packet.momentum, 1);
    }
    const auto kinetic_double = static_cast<double>(kinetic);
    return {
        kinetic_double,
        floored,
        force_value.energy_j,
        kinetic_double + force_value.energy_j,
        true,
    };
}

StepResult evaluate_step(
    const DynamicModel& model,
    const StepInput& input) {
    if (input.timestep.raw() == 0 || input.timestep.raw() % 2 != 0 ||
        model.reference_packets.empty()) {
        throw std::invalid_argument(
            "time-map KDK requires a nonzero even raw timestep and model");
    }
    StepResult result{};
    result.path = input.path;
    result.prior_state = {
        input.state.physical_time, canonical_packets(input.state.packets)};
    result.next_state = result.prior_state;
    append_stage(result.stages, StageKind::initial, result.prior_state);
    const auto initial_invariants = result.stages.front().invariants;

    const auto reject = [&](StepStatus status,
                            std::size_t failed_index,
                            BondRelation failed_relation) {
        result.status = status;
        result.failed_relation_index = failed_index;
        result.failed_relation = failed_relation;
        result.next_state = result.prior_state;
        append_stage(result.stages, StageKind::rejected, result.next_state);
        result.state_unchanged_on_rejection =
            result.next_state == result.prior_state;
        result.exact_momentum_preserved = true;
        result.exact_orbital_angular_momentum_preserved = true;
        return result;
    };

    try {
        const auto initial_domain = check_chords(
            model, result.prior_state.packets, result.prior_state.packets);
        if (!initial_domain.admissible) {
            return reject(
                StepStatus::initial_domain_failure,
                initial_domain.failed_relation_index,
                initial_domain.failed_relation);
        }
        result.energy_before = evaluate_energy(model, result.prior_state);
        if (!result.energy_before.evaluated) {
            return reject(StepStatus::force_domain_failure, {}, {});
        }

        const auto kick_interval = input.path ==
                IntegratorPath::quantized_kick_drift_kick
            ? Time::from_raw(input.timestep.raw() / 2)
            : input.timestep;
        const auto units = mechanics::mechanics_unit_contract(selected_refinement);
        auto first = kick(
            model, result.prior_state.packets, kick_interval, units);
        if (first.status != StepStatus::accepted) {
            return reject(
                first.status, first.failed_relation_index, first.failed_relation);
        }
        auto working = with_packets(result.prior_state, std::move(first.packets));
        append_stage(result.stages, StageKind::first_kick, working);
        if (result.stages.back().invariants != initial_invariants) {
            return reject(StepStatus::invariant_failure, {}, {});
        }

        auto proposed_packets = working.packets;
        for (auto& packet : proposed_packets) {
            packet.position += drift_displacement(packet, input.timestep);
        }
        const auto chord = check_chords(
            model, working.packets, proposed_packets);
        if (!chord.admissible) {
            return reject(
                StepStatus::chord_domain_failure,
                chord.failed_relation_index,
                chord.failed_relation);
        }
        working.packets = std::move(proposed_packets);
        append_stage(result.stages, StageKind::drift, working);
        if (result.stages.back().invariants != initial_invariants) {
            return reject(StepStatus::invariant_failure, {}, {});
        }

        if (input.path == IntegratorPath::quantized_kick_drift_kick) {
            auto second = kick(model, working.packets, kick_interval, units);
            if (second.status != StepStatus::accepted) {
                return reject(
                    second.status,
                    second.failed_relation_index,
                    second.failed_relation);
            }
            working.packets = std::move(second.packets);
            append_stage(result.stages, StageKind::second_kick, working);
            if (result.stages.back().invariants != initial_invariants) {
                return reject(StepStatus::invariant_failure, {}, {});
            }
        }

        working.physical_time += input.timestep;
        result.energy_after = evaluate_energy(model, working);
        if (!result.energy_after.evaluated) {
            return reject(StepStatus::force_domain_failure, {}, {});
        }
        result.next_state = std::move(working);
        result.status = StepStatus::accepted;
        append_stage(result.stages, StageKind::committed, result.next_state);
        const auto final_invariants = result.stages.back().invariants;
        result.exact_momentum_preserved =
            final_invariants.total_momentum == initial_invariants.total_momentum;
        result.exact_orbital_angular_momentum_preserved =
            final_invariants.orbital_angular_momentum ==
            initial_invariants.orbital_angular_momentum;
        if (!result.exact_momentum_preserved ||
            !result.exact_orbital_angular_momentum_preserved) {
            return reject(StepStatus::invariant_failure, {}, {});
        }
        return result;
    } catch (const std::overflow_error&) {
        return reject(StepStatus::arithmetic_failure, {}, {});
    } catch (const std::domain_error&) {
        return reject(StepStatus::arithmetic_failure, {}, {});
    }
}

TrajectoryResult evaluate_trajectory(
    const DynamicModel& model,
    IntegratorPath path,
    const PhaseState& initial_state,
    Time timestep,
    std::uint64_t step_count) {
    if (step_count == 0U) {
        throw std::invalid_argument("time-map trajectory requires steps");
    }
    TrajectoryResult result{};
    result.path = path;
    result.initial_state = {
        initial_state.physical_time, canonical_packets(initial_state.packets)};
    result.final_state = result.initial_state;
    result.requested_steps = step_count;
    const auto initial_invariants = evaluate_exact_invariants(
        result.initial_state.packets);
    const auto initial_energy = evaluate_energy(model, result.initial_state);
    if (initial_energy.evaluated) {
        result.mechanical_energy_j.push_back(initial_energy.mechanical_energy_j);
    }
    for (std::uint64_t index = 0; index < step_count; ++index) {
        const auto step = evaluate_step(
            model, {path, result.final_state, timestep});
        auto event_hash = hash_phase_state(step.next_state);
        event_hash ^= static_cast<std::uint64_t>(step.status) +
            UINT64_C(0x9e3779b97f4a7c15) + (event_hash << 6U) +
            (event_hash >> 2U);
        result.event_hashes.push_back(event_hash);
        result.status = step.status;
        if (step.status != StepStatus::accepted) {
            break;
        }
        result.final_state = step.next_state;
        ++result.completed_steps;
        result.mechanical_energy_j.push_back(
            step.energy_after.mechanical_energy_j);
    }
    const auto final_invariants = evaluate_exact_invariants(
        result.final_state.packets);
    result.exact_momentum_preserved =
        final_invariants.total_momentum == initial_invariants.total_momentum;
    result.exact_orbital_angular_momentum_preserved =
        final_invariants.orbital_angular_momentum ==
        initial_invariants.orbital_angular_momentum;
    return result;
}

std::vector<std::uint8_t> encode_phase_checkpoint(const PhaseState& state) {
    const auto packets = canonical_packets(state.packets);
    std::vector<std::uint8_t> bytes;
    bytes.reserve(24U + packets.size() * 64U);
    append_u32(bytes, checkpoint_version);
    append_u32(bytes, static_cast<std::uint32_t>(packets.size()));
    append_i64(bytes, state.physical_time.raw());
    for (const auto& packet : packets) {
        append_u64(bytes, packet.id);
        append_i64(bytes, packet.position.x.raw());
        append_i64(bytes, packet.position.y.raw());
        append_i64(bytes, packet.position.z.raw());
        append_i64(bytes, packet.momentum.x.raw());
        append_i64(bytes, packet.momentum.y.raw());
        append_i64(bytes, packet.momentum.z.raw());
        append_i64(bytes, packet.mass.raw());
    }
    return bytes;
}

PhaseState decode_phase_checkpoint(std::span<const std::uint8_t> bytes) {
    std::size_t cursor = 0U;
    if (read_u32(bytes, cursor) != checkpoint_version) {
        throw std::invalid_argument("unsupported time-map checkpoint version");
    }
    const auto count = read_u32(bytes, cursor);
    PhaseState result{};
    result.physical_time = Time::from_raw(read_i64(bytes, cursor));
    result.packets.reserve(count);
    for (std::uint32_t index = 0; index < count; ++index) {
        DynamicPacket packet{};
        packet.id = read_u64(bytes, cursor);
        packet.position = {
            Length::from_raw(read_i64(bytes, cursor)),
            Length::from_raw(read_i64(bytes, cursor)),
            Length::from_raw(read_i64(bytes, cursor))};
        packet.momentum = {
            Momentum::from_raw(read_i64(bytes, cursor)),
            Momentum::from_raw(read_i64(bytes, cursor)),
            Momentum::from_raw(read_i64(bytes, cursor))};
        packet.mass = Mass::from_raw(read_i64(bytes, cursor));
        result.packets.push_back(packet);
    }
    if (cursor != bytes.size()) {
        throw std::invalid_argument("trailing time-map checkpoint bytes");
    }
    result.packets = canonical_packets(result.packets);
    return result;
}

std::uint64_t hash_phase_state(const PhaseState& state) {
    auto hash = UINT64_C(1469598103934665603);
    for (const auto byte : encode_phase_checkpoint(state)) {
        hash = fnv_byte(hash, byte);
    }
    return hash;
}

} // namespace mls::experimental::time_integration_foundation
