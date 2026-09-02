#include "mls/authoritative_mechanics_state_bridge_lab.hpp"

#include <bit>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <limits>
#include <numeric>
#include <sstream>
#include <stdexcept>

namespace mls::experimental::authoritative_mechanics_state_bridge {
namespace {

[[nodiscard]] bool valid_refinement(std::uint32_t value) noexcept {
    return value == 1U || value == 2U || value == 4U || value == 8U ||
        value == 16U || value == 32U || value == 64U || value == 128U;
}

[[nodiscard]] PositiveRational reduced(
    std::uint64_t numerator, std::uint64_t denominator) {
    if (numerator == 0U || denominator == 0U) {
        throw std::invalid_argument("mechanics rational must be positive");
    }
    const auto divisor = std::gcd(numerator, denominator);
    return {numerator / divisor, denominator / divisor};
}

[[nodiscard]] std::uint64_t checked_unsigned_multiply(
    std::uint64_t lhs, std::uint64_t rhs) {
    if (lhs != 0U && rhs > std::numeric_limits<std::uint64_t>::max() / lhs) {
        throw std::overflow_error("mechanics rational product overflow");
    }
    return lhs * rhs;
}

[[nodiscard]] PositiveRational multiply(
    PositiveRational lhs, PositiveRational rhs) {
    const auto left_cancel = std::gcd(lhs.numerator, rhs.denominator);
    lhs.numerator /= left_cancel;
    rhs.denominator /= left_cancel;
    const auto right_cancel = std::gcd(rhs.numerator, lhs.denominator);
    rhs.numerator /= right_cancel;
    lhs.denominator /= right_cancel;
    return reduced(
        checked_unsigned_multiply(lhs.numerator, rhs.numerator),
        checked_unsigned_multiply(lhs.denominator, rhs.denominator));
}

[[nodiscard]] PositiveRational divide(
    PositiveRational lhs, PositiveRational rhs) {
    return multiply(lhs, {rhs.denominator, rhs.numerator});
}

[[nodiscard]] double value(PositiveRational rational) noexcept {
    return static_cast<double>(rational.numerator) /
        static_cast<double>(rational.denominator);
}

[[nodiscard]] Scalar checked_scale(Scalar raw, std::uint64_t factor) {
    if (factor > static_cast<std::uint64_t>(
            std::numeric_limits<Scalar>::max())) {
        throw std::overflow_error("mechanics refinement factor overflow");
    }
    return detail::checked_multiply(raw, static_cast<Scalar>(factor));
}

[[nodiscard]] Scalar nearest_even(double value_to_round) {
    if (!std::isfinite(value_to_round) ||
        value_to_round < static_cast<double>(std::numeric_limits<Scalar>::min()) ||
        value_to_round > static_cast<double>(std::numeric_limits<Scalar>::max())) {
        throw std::overflow_error("central impulse is outside integer range");
    }
    const auto lower = std::floor(value_to_round);
    const auto fraction = value_to_round - lower;
    auto result = static_cast<Scalar>(lower);
    if (fraction > 0.5 ||
        (fraction == 0.5 && result % static_cast<Scalar>(2) != 0)) {
        result = detail::checked_add(result, 1);
    }
    return result;
}

[[nodiscard]] Scalar absolute_for_gcd(Scalar value_to_abs) {
    if (value_to_abs == std::numeric_limits<Scalar>::min()) {
        throw std::overflow_error("relation offset magnitude overflow");
    }
    return value_to_abs < 0 ? static_cast<Scalar>(-value_to_abs) : value_to_abs;
}

[[nodiscard]] Position3 primitive_direction(
    const Position3& first, const Position3& second) {
    const auto offset = second - first;
    auto divisor = std::gcd(
        absolute_for_gcd(offset.x.raw()),
        absolute_for_gcd(offset.y.raw()));
    divisor = std::gcd(divisor, absolute_for_gcd(offset.z.raw()));
    if (divisor == 0) {
        throw std::domain_error("central impulse requires noncoincident packets");
    }
    return {
        Length::from_raw(offset.x.raw() / divisor),
        Length::from_raw(offset.y.raw() / divisor),
        Length::from_raw(offset.z.raw() / divisor),
    };
}

[[nodiscard]] Momentum3 momentum_from_direction(
    const Position3& direction, Scalar multiple) {
    return {
        Momentum::from_raw(detail::checked_multiply(direction.x.raw(), multiple)),
        Momentum::from_raw(detail::checked_multiply(direction.y.raw(), multiple)),
        Momentum::from_raw(detail::checked_multiply(direction.z.raw(), multiple)),
    };
}

[[nodiscard]] Position3 scaled_position(
    const Position3& position, Scalar factor) {
    return {
        Length::from_raw(detail::checked_multiply(position.x.raw(), factor)),
        Length::from_raw(detail::checked_multiply(position.y.raw(), factor)),
        Length::from_raw(detail::checked_multiply(position.z.raw(), factor)),
    };
}

[[nodiscard]] Vec3d mapped(
    const Position3& raw, double quantum) noexcept {
    return {
        static_cast<double>(raw.x.raw()) * quantum,
        static_cast<double>(raw.y.raw()) * quantum,
        static_cast<double>(raw.z.raw()) * quantum,
    };
}

[[nodiscard]] Vec3d mapped(
    const Momentum3& raw, double quantum) noexcept {
    return {
        static_cast<double>(raw.x.raw()) * quantum,
        static_cast<double>(raw.y.raw()) * quantum,
        static_cast<double>(raw.z.raw()) * quantum,
    };
}

[[nodiscard]] bool roundtrip(Scalar raw, double quantum) {
    return nearest_even(static_cast<double>(raw) * quantum / quantum) == raw;
}

[[nodiscard]] double squared(Vec3d vector) noexcept {
    return vector.x * vector.x + vector.y * vector.y + vector.z * vector.z;
}

[[nodiscard]] std::uint64_t fnv_byte(
    std::uint64_t hash, std::uint8_t byte) noexcept {
    return (hash ^ byte) * 1099511628211ULL;
}

[[nodiscard]] std::uint64_t fnv_word(
    std::uint64_t hash, std::uint64_t word) noexcept {
    for (unsigned int index = 0; index < 8U; ++index) {
        hash = fnv_byte(
            hash, static_cast<std::uint8_t>((word >> (8U * index)) & 0xffU));
    }
    return hash;
}

} // namespace

MechanicsUnitContract mechanics_unit_contract(std::uint32_t refinement) {
    if (!valid_refinement(refinement)) {
        throw std::invalid_argument("unregistered mechanics refinement");
    }
    const auto r = static_cast<std::uint64_t>(refinement);
    const auto r2 = r * r;
    const auto r3 = r2 * r;
    MechanicsUnitContract result{};
    result.refinement = refinement;
    result.length_quantum_m = reduced(1U, 1'000'000'000ULL * r);
    result.mass_quantum_kg = reduced(1U, 4'096ULL * r);
    result.time_quantum_s = {1, 1'000'000'000};
    result.momentum_quantum_kg_m_per_s = reduced(1U, 4'096ULL * r2);
    result.energy_quantum_j = reduced(1U, 4'096ULL * r3);
    result.force_quantum_n = reduced(1'953'125U, 8U * r2);
    validate_mechanics_unit_contract(result);
    return result;
}

void validate_mechanics_unit_contract(const MechanicsUnitContract& contract) {
    const auto positive = [](PositiveRational rational) {
        return rational.numerator != 0U && rational.denominator != 0U;
    };
    if (!valid_refinement(contract.refinement) ||
        !positive(contract.length_quantum_m) ||
        !positive(contract.mass_quantum_kg) ||
        !positive(contract.time_quantum_s) ||
        !positive(contract.momentum_quantum_kg_m_per_s) ||
        !positive(contract.energy_quantum_j) ||
        !positive(contract.force_quantum_n)) {
        throw std::invalid_argument("mechanics unit quanta must be positive");
    }
    const auto velocity_quantum = divide(
        contract.length_quantum_m, contract.time_quantum_s);
    const auto derived_momentum = multiply(
        contract.mass_quantum_kg, velocity_quantum);
    const auto derived_energy = multiply(derived_momentum, velocity_quantum);
    const auto derived_force = divide(derived_energy, contract.length_quantum_m);
    if (derived_momentum != contract.momentum_quantum_kg_m_per_s ||
        derived_energy != contract.energy_quantum_j ||
        derived_force != contract.force_quantum_n ||
        contract.physical_time_scale.seconds_per_time_quantum_numerator !=
            contract.time_quantum_s.numerator ||
        contract.physical_time_scale.seconds_per_time_quantum_denominator !=
            contract.time_quantum_s.denominator ||
        contract.momentum_mass_to_velocity_scale !=
            MomentumMassToVelocityScale{1, 1} ||
        contract.kinetic_energy_scale_denominator != 1) {
        throw std::invalid_argument(
            "stop_authoritative_unit_contract_inconsistent");
    }
}

Binary64PacketMapping map_packet_to_binary64_si(
    const AuthoritativePacket& packet,
    const MechanicsUnitContract& contract) {
    validate_mechanics_unit_contract(contract);
    if (packet.id == 0U || packet.mass.raw() <= 0) {
        throw std::invalid_argument("authoritative packet identity/mass invalid");
    }
    const auto lq = value(contract.length_quantum_m);
    const auto pq = value(contract.momentum_quantum_kg_m_per_s);
    const auto mq = value(contract.mass_quantum_kg);
    Binary64PacketMapping result{};
    result.id = packet.id;
    result.position_m = mapped(packet.position, lq);
    result.momentum_kg_m_per_s = mapped(packet.momentum, pq);
    result.mass_kg = static_cast<double>(packet.mass.raw()) * mq;
    result.nearest_roundtrip_exact =
        roundtrip(packet.position.x.raw(), lq) &&
        roundtrip(packet.position.y.raw(), lq) &&
        roundtrip(packet.position.z.raw(), lq) &&
        roundtrip(packet.momentum.x.raw(), pq) &&
        roundtrip(packet.momentum.y.raw(), pq) &&
        roundtrip(packet.momentum.z.raw(), pq) &&
        roundtrip(packet.mass.raw(), mq);
    return result;
}

const char* path_name(QuantizationPath path) noexcept {
    switch (path) {
    case QuantizationPath::direct_nearest:
        return "direct_nearest";
    case QuantizationPath::fixed_point_refinement:
        return "fixed_point_refinement";
    case QuantizationPath::explicit_remainder:
        return "explicit_remainder";
    }
    return "unknown";
}

std::string encode_remainder_checkpoint(
    const ExplicitRemainderCheckpoint& checkpoint) {
    std::ostringstream stream;
    stream << checkpoint.first_id << ':' << checkpoint.second_id << ':'
           << std::hex << std::setw(16) << std::setfill('0')
           << checkpoint.scalar_remainder_bits;
    return stream.str();
}

ExplicitRemainderCheckpoint decode_remainder_checkpoint(
    const std::string& encoded) {
    ExplicitRemainderCheckpoint result{};
    char first_separator = 0;
    char second_separator = 0;
    std::istringstream stream(encoded);
    stream >> result.first_id >> first_separator >> result.second_id >>
        second_separator >> std::hex >> result.scalar_remainder_bits;
    if (!stream || first_separator != ':' || second_separator != ':' ||
        result.first_id == 0U || result.first_id >= result.second_id ||
        stream.peek() != std::char_traits<char>::eof()) {
        throw std::invalid_argument("invalid mechanics remainder checkpoint");
    }
    return result;
}

std::uint64_t hash_remainder_checkpoint(
    const ExplicitRemainderCheckpoint& checkpoint) noexcept {
    auto hash = 1469598103934665603ULL;
    hash = fnv_word(hash, checkpoint.first_id);
    hash = fnv_word(hash, checkpoint.second_id);
    return fnv_word(hash, checkpoint.scalar_remainder_bits);
}

CentralImpulseEvaluation evaluate_central_impulse(
    const CentralImpulseInput& input,
    const MechanicsUnitContract& contract) {
    validate_mechanics_unit_contract(contract);
    if (input.first.id == 0U || input.first.id >= input.second.id ||
        input.first.mass.raw() <= 0 || input.second.mass.raw() <= 0 ||
        input.interval.raw() <= 0 || input.subdivisions == 0U ||
        (input.subdivisions != 1U && input.subdivisions != 2U &&
         input.subdivisions != 4U && input.subdivisions != 8U &&
         input.subdivisions != 16U) ||
        !std::isfinite(input.force_to_first_n.x) ||
        !std::isfinite(input.force_to_first_n.y) ||
        !std::isfinite(input.force_to_first_n.z)) {
        throw std::invalid_argument("invalid prescribed central impulse input");
    }
    const auto direction = primitive_direction(
        input.first.position, input.second.position);
    const Vec3d direction_value{
        static_cast<double>(direction.x.raw()),
        static_cast<double>(direction.y.raw()),
        static_cast<double>(direction.z.raw())};
    const auto direction_squared = squared(direction_value);
    const auto dt = static_cast<double>(input.interval.raw()) *
        value(contract.time_quantum_s);
    const auto pq = value(contract.momentum_quantum_kg_m_per_s);
    const Vec3d target{
        input.force_to_first_n.x * dt,
        input.force_to_first_n.y * dt,
        input.force_to_first_n.z * dt};
    const auto target_multiple =
        (target.x * direction_value.x + target.y * direction_value.y +
         target.z * direction_value.z) /
        (pq * direction_squared);
    const auto per_substep = target_multiple /
        static_cast<double>(input.subdivisions);

    Scalar applied_multiple = 0;
    double remainder = 0.0;
    for (std::uint32_t step = 0; step < input.subdivisions; ++step) {
        const auto available = per_substep +
            (input.path == QuantizationPath::explicit_remainder ? remainder : 0.0);
        const auto increment = nearest_even(available);
        applied_multiple = detail::checked_add(applied_multiple, increment);
        if (input.path == QuantizationPath::explicit_remainder) {
            remainder = available - static_cast<double>(increment);
        }
    }

    CentralImpulseEvaluation result{};
    result.path = input.path;
    result.refinement = contract.refinement;
    result.subdivisions = input.subdivisions;
    result.primitive_direction = direction;
    result.applied_primitive_multiple = applied_multiple;
    result.impulse_to_first = momentum_from_direction(direction, applied_multiple);
    result.impulse_to_second = -result.impulse_to_first;
    result.total_momentum_delta = result.impulse_to_first + result.impulse_to_second;

    const auto refinement = static_cast<Scalar>(contract.refinement);
    const auto refined_first_position = scaled_position(
        input.first.position, refinement);
    const auto refined_second_position = scaled_position(
        input.second.position, refinement);
    result.orbital_angular_momentum_delta = pair_angular_momentum_delta(
        refined_first_position, refined_second_position,
        result.impulse_to_first);
    result.target_primitive_multiple = target_multiple;
    result.remainder_primitive_quanta = remainder;
    result.target_impulse_kg_m_per_s = target;
    result.applied_impulse_kg_m_per_s = mapped(result.impulse_to_first, pq);
    result.discarded_impulse_kg_m_per_s =
        target - result.applied_impulse_kg_m_per_s;

    const auto r2 = static_cast<std::uint64_t>(contract.refinement) *
        contract.refinement;
    const Momentum3 first_before{
        Momentum::from_raw(checked_scale(input.first.momentum.x.raw(), r2)),
        Momentum::from_raw(checked_scale(input.first.momentum.y.raw(), r2)),
        Momentum::from_raw(checked_scale(input.first.momentum.z.raw(), r2))};
    const Momentum3 second_before{
        Momentum::from_raw(checked_scale(input.second.momentum.x.raw(), r2)),
        Momentum::from_raw(checked_scale(input.second.momentum.y.raw(), r2)),
        Momentum::from_raw(checked_scale(input.second.momentum.z.raw(), r2))};
    const auto first_mass = Mass::from_raw(
        checked_scale(input.first.mass.raw(), contract.refinement));
    const auto second_mass = Mass::from_raw(
        checked_scale(input.second.mass.raw(), contract.refinement));
    const auto before = kinetic_energy_of(first_mass, first_before, 1) +
        kinetic_energy_of(second_mass, second_before, 1);
    const auto after = kinetic_energy_of(
        first_mass, first_before + result.impulse_to_first, 1) +
        kinetic_energy_of(
            second_mass, second_before + result.impulse_to_second, 1);
    result.quantized_kinetic_delta = after - before;
    result.quantized_kinetic_delta_j =
        static_cast<double>(result.quantized_kinetic_delta.raw()) *
        value(contract.energy_quantum_j);

    const auto first_mapping = map_packet_to_binary64_si(
        {input.first.id, refined_first_position, first_before, first_mass}, contract);
    const auto second_mapping = map_packet_to_binary64_si(
        {input.second.id, refined_second_position, second_before, second_mass}, contract);
    const auto applied = result.applied_impulse_kg_m_per_s;
    const auto first_linear =
        first_mapping.momentum_kg_m_per_s.x * applied.x +
        first_mapping.momentum_kg_m_per_s.y * applied.y +
        first_mapping.momentum_kg_m_per_s.z * applied.z;
    const auto second_linear =
        second_mapping.momentum_kg_m_per_s.x * applied.x +
        second_mapping.momentum_kg_m_per_s.y * applied.y +
        second_mapping.momentum_kg_m_per_s.z * applied.z;
    const auto applied_squared = squared(applied);
    result.exact_kinetic_delta_j =
        first_linear / first_mapping.mass_kg -
        second_linear / second_mapping.mass_kg +
        applied_squared / (2.0 * first_mapping.mass_kg) +
        applied_squared / (2.0 * second_mapping.mass_kg);
    result.exact_impulse_work_j = result.exact_kinetic_delta_j;
    result.kinetic_floor_residual_j =
        result.exact_kinetic_delta_j - result.quantized_kinetic_delta_j;
    result.remainder_balance_error = target_multiple -
        (static_cast<double>(applied_multiple) + remainder);

    result.remainder_checkpoint = {
        input.first.id, input.second.id, std::bit_cast<std::uint64_t>(remainder)};
    result.remainder_checkpoint_hash =
        hash_remainder_checkpoint(result.remainder_checkpoint);
    result.remainder_checkpoint_roundtrip =
        decode_remainder_checkpoint(
            encode_remainder_checkpoint(result.remainder_checkpoint)) ==
        result.remainder_checkpoint;
    result.exact_linear_momentum = result.total_momentum_delta == Momentum3{};
    result.exact_orbital_angular_momentum =
        result.orbital_angular_momentum_delta == AngularMomentum3{};
    return result;
}

} // namespace mls::experimental::authoritative_mechanics_state_bridge
