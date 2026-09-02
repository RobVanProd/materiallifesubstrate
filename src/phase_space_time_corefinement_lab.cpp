#include "mls/phase_space_time_corefinement_lab.hpp"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <iomanip>
#include <limits>
#include <map>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace mls::experimental::phase_space_time_corefinement {
namespace {

namespace geometry = relation_geometry_resolution;
using observation::BondRelation;
using observation::MechanicalPacket;

[[nodiscard]] std::uint64_t checked_u64_multiply(
    std::uint64_t lhs, std::uint64_t rhs) {
    if (lhs != 0U && rhs > std::numeric_limits<std::uint64_t>::max() / lhs) {
        throw std::overflow_error("corefinement rational overflow");
    }
    return lhs * rhs;
}

[[nodiscard]] std::uint64_t power_of_two(unsigned int exponent) {
    if (exponent >= 64U) {
        throw std::overflow_error("corefinement exponent overflow");
    }
    return std::uint64_t{1} << exponent;
}

[[nodiscard]] mechanics::PositiveRational reduced(
    std::uint64_t numerator, std::uint64_t denominator) {
    if (numerator == 0U || denominator == 0U) {
        throw std::invalid_argument("corefinement rational must be positive");
    }
    const auto divisor = std::gcd(numerator, denominator);
    return {numerator / divisor, denominator / divisor};
}

[[nodiscard]] mechanics::PositiveRational multiply(
    mechanics::PositiveRational lhs,
    mechanics::PositiveRational rhs) {
    const auto first = std::gcd(lhs.numerator, rhs.denominator);
    const auto second = std::gcd(rhs.numerator, lhs.denominator);
    return reduced(
        checked_u64_multiply(lhs.numerator / first, rhs.numerator / second),
        checked_u64_multiply(lhs.denominator / second, rhs.denominator / first));
}

[[nodiscard]] mechanics::PositiveRational divide(
    mechanics::PositiveRational lhs,
    mechanics::PositiveRational rhs) {
    if (rhs.numerator == 0U) {
        throw std::invalid_argument("corefinement rational division by zero");
    }
    return multiply(lhs, {rhs.denominator, rhs.numerator});
}

[[nodiscard]] double rational_value(
    mechanics::PositiveRational value) noexcept {
    return static_cast<double>(value.numerator) /
        static_cast<double>(value.denominator);
}

[[nodiscard]] Scalar absolute_for_gcd(Scalar value) {
    if (value == std::numeric_limits<Scalar>::min()) {
        throw std::overflow_error("corefinement primitive magnitude overflow");
    }
    return value < 0 ? static_cast<Scalar>(-value) : value;
}

[[nodiscard]] std::uint64_t unsigned_magnitude(Scalar value) noexcept {
    if (value >= 0) {
        return static_cast<std::uint64_t>(value);
    }
    return static_cast<std::uint64_t>(-(value + 1)) + 1U;
}

[[nodiscard]] SignedMagnitude192 add_magnitude(
    const SignedMagnitude192& lhs,
    const SignedMagnitude192& rhs);
[[nodiscard]] SignedMagnitude192 product(Scalar lhs, Scalar rhs) noexcept;

[[nodiscard]] Energy exact_kinetic_floor(
    Mass mass,
    const Momentum3& momentum) {
    if (mass.raw() <= 0) {
        throw std::invalid_argument("corefinement kinetic mass must be positive");
    }
    SignedMagnitude192 squared{};
    const std::array values{
        momentum.x.raw(), momentum.y.raw(), momentum.z.raw()};
    for (const auto value : values) {
        squared = add_magnitude(squared, product(value, value));
    }
    const auto denominator = checked_u64_multiply(
        static_cast<std::uint64_t>(mass.raw()), 2U);
    SignedMagnitude192 quotient{};
    std::uint64_t remainder = 0U;
    constexpr std::size_t bit_count = 192U;
    for (std::size_t bit = bit_count; bit-- > 0U;) {
        const auto source =
            (squared.magnitude[bit / 64U] >> (bit % 64U)) & UINT64_C(1);
        if (remainder > (std::numeric_limits<std::uint64_t>::max() - source) /
                2U) {
            throw std::overflow_error("corefinement kinetic division overflow");
        }
        remainder = remainder * 2U + source;
        if (remainder >= denominator) {
            remainder -= denominator;
            quotient.magnitude[bit / 64U] |= UINT64_C(1) << (bit % 64U);
        }
    }
    if (quotient.magnitude[1] != 0U || quotient.magnitude[2] != 0U ||
        quotient.magnitude[0] > static_cast<std::uint64_t>(
            std::numeric_limits<Scalar>::max())) {
        throw std::overflow_error("corefinement kinetic result overflow");
    }
    return Energy::from_raw(static_cast<Scalar>(quotient.magnitude[0]));
}

[[nodiscard]] int compare_magnitude(
    const SignedMagnitude192& lhs,
    const SignedMagnitude192& rhs) noexcept {
    for (std::size_t index = lhs.magnitude.size(); index-- > 0U;) {
        if (lhs.magnitude[index] < rhs.magnitude[index]) {
            return -1;
        }
        if (lhs.magnitude[index] > rhs.magnitude[index]) {
            return 1;
        }
    }
    return 0;
}

[[nodiscard]] bool is_zero(const SignedMagnitude192& value) noexcept {
    return std::ranges::all_of(
        value.magnitude, [](std::uint64_t limb) { return limb == 0U; });
}

[[nodiscard]] SignedMagnitude192 normalized(SignedMagnitude192 value) noexcept {
    if (is_zero(value)) {
        value.negative = false;
    }
    return value;
}

[[nodiscard]] SignedMagnitude192 add_magnitude(
    const SignedMagnitude192& lhs,
    const SignedMagnitude192& rhs) {
    SignedMagnitude192 result{};
    std::uint64_t carry = 0U;
    for (std::size_t index = 0; index < result.magnitude.size(); ++index) {
        const auto first = lhs.magnitude[index] + carry;
        const auto carry_first = first < lhs.magnitude[index];
        const auto sum = first + rhs.magnitude[index];
        const auto carry_second = sum < first;
        result.magnitude[index] = sum;
        carry = (carry_first || carry_second) ? 1U : 0U;
    }
    if (carry != 0U) {
        throw std::overflow_error("wide invariant accumulator overflow");
    }
    return result;
}

[[nodiscard]] SignedMagnitude192 subtract_magnitude(
    const SignedMagnitude192& larger,
    const SignedMagnitude192& smaller) noexcept {
    SignedMagnitude192 result{};
    std::uint64_t borrow = 0U;
    for (std::size_t index = 0; index < result.magnitude.size(); ++index) {
        const auto subtrahend = smaller.magnitude[index] + borrow;
        const auto overflow = subtrahend < smaller.magnitude[index];
        const auto next_borrow = overflow || larger.magnitude[index] < subtrahend;
        result.magnitude[index] = larger.magnitude[index] - subtrahend;
        borrow = next_borrow ? 1U : 0U;
    }
    return result;
}

[[nodiscard]] SignedMagnitude192 add_signed(
    SignedMagnitude192 lhs,
    SignedMagnitude192 rhs) {
    lhs = normalized(lhs);
    rhs = normalized(rhs);
    if (lhs.negative == rhs.negative) {
        auto result = add_magnitude(lhs, rhs);
        result.negative = lhs.negative;
        return normalized(result);
    }
    const auto ordering = compare_magnitude(lhs, rhs);
    if (ordering == 0) {
        return {};
    }
    if (ordering > 0) {
        auto result = subtract_magnitude(lhs, rhs);
        result.negative = lhs.negative;
        return normalized(result);
    }
    auto result = subtract_magnitude(rhs, lhs);
    result.negative = rhs.negative;
    return normalized(result);
}

[[nodiscard]] SignedMagnitude192 negated(SignedMagnitude192 value) noexcept {
    if (!is_zero(value)) {
        value.negative = !value.negative;
    }
    return value;
}

[[nodiscard]] SignedMagnitude192 product(Scalar lhs, Scalar rhs) noexcept {
    const auto a = unsigned_magnitude(lhs);
    const auto b = unsigned_magnitude(rhs);
    constexpr auto mask = UINT64_C(0xffffffff);
    const auto a0 = a & mask;
    const auto a1 = a >> 32U;
    const auto b0 = b & mask;
    const auto b1 = b >> 32U;
    const auto w0 = a0 * b0;
    const auto t = a1 * b0 + (w0 >> 32U);
    auto w1 = t & mask;
    const auto w2 = t >> 32U;
    w1 += a0 * b1;
    const auto high = a1 * b1 + w2 + (w1 >> 32U);
    const auto low = (w1 << 32U) + (w0 & mask);
    SignedMagnitude192 result{};
    result.negative = (lhs < 0) != (rhs < 0) && a != 0U && b != 0U;
    result.magnitude = {low, high, 0U};
    return result;
}

[[nodiscard]] SignedMagnitude192 product_difference(
    Scalar first_lhs,
    Scalar first_rhs,
    Scalar second_lhs,
    Scalar second_rhs) {
    return add_signed(
        product(first_lhs, first_rhs),
        negated(product(second_lhs, second_rhs)));
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
                "corefinement packets require unique positive IDs and mass");
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
    const UnitProfile& units) {
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
    const UnitProfile& units) {
    std::vector<MechanicalPacket> result;
    result.reserve(packets.size());
    for (const auto& packet : packets) {
        result.push_back(mapped_packet(packet, units));
    }
    return result;
}

[[nodiscard]] std::array<Scalar, 3> primitive_direction(
    const Position3& first,
    const Position3& second) {
    const auto offset = second - first;
    auto divisor = std::gcd(
        absolute_for_gcd(offset.x.raw()),
        absolute_for_gcd(offset.y.raw()));
    divisor = std::gcd(divisor, absolute_for_gcd(offset.z.raw()));
    if (divisor == 0) {
        throw std::domain_error("corefinement central kick requires separation");
    }
    return {offset.x.raw() / divisor, offset.y.raw() / divisor,
            offset.z.raw() / divisor};
}

[[nodiscard]] Scalar nearest_even_binary64(double value) {
    if (!std::isfinite(value) ||
        value < static_cast<double>(std::numeric_limits<Scalar>::min()) ||
        value > static_cast<double>(std::numeric_limits<Scalar>::max())) {
        throw std::overflow_error("corefinement impulse multiple outside range");
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
    const std::array<Scalar, 3>& direction,
    Scalar multiple) {
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
    std::vector<PrimitiveRelationDiagnostic> diagnostics{};
};

[[nodiscard]] KickResult kick(
    const DynamicModel& model,
    std::span<const DynamicPacket> input_packets,
    Time interval) {
    auto packets = canonical_packets(input_packets);
    const auto reference = mapped_packets(model.reference_packets, model.units);
    const auto current = mapped_packets(packets, model.units);
    const auto evaluated = geometry::evaluate_resolved_spatial_force(
        model.frozen_force,
        reference,
        current,
        geometry::GeometryPath::cancellation_resistant_binary64);
    if (evaluated.status != geometry::ResolvedForceStatus::evaluated) {
        return {
            StepStatus::force_domain_failure,
            {},
            evaluated.failed_relation_index,
            evaluated.failed_relation,
            {}};
    }
    const auto by_id = lookup(packets);
    const auto pq = rational_value(model.units.momentum_quantum_kg_m_per_s);
    const auto dt = static_cast<double>(interval.raw()) *
        rational_value(model.units.time_quantum_s);
    std::vector<PrimitiveRelationDiagnostic> diagnostics;
    diagnostics.reserve(evaluated.relation_coordinates.size());
    for (std::size_t relation_index = 0;
         relation_index < evaluated.relation_coordinates.size();
         ++relation_index) {
        const auto& relation = evaluated.relation_coordinates[relation_index];
        const auto first_index = by_id.at(relation.relation.first_id);
        const auto second_index = by_id.at(relation.relation.second_id);
        const auto direction = primitive_direction(
            packets[first_index].position,
            packets[second_index].position);
        const Vec3d raw_direction{
            static_cast<double>(direction[0]),
            static_cast<double>(direction[1]),
            static_cast<double>(direction[2])};
        const auto direction_squared = dot(raw_direction, raw_direction);
        const auto relation_force = relation.conjugate_force_n *
            relation.geometry.direction_first_to_second;
        const auto target_multiple =
            dt * dot(relation_force, raw_direction) /
            (pq * direction_squared);
        const auto multiple = nearest_even_binary64(target_multiple);
        const auto relative =
            packets[second_index].position - packets[first_index].position;
        auto direction_gcd = std::gcd(
            absolute_for_gcd(relative.x.raw()),
            absolute_for_gcd(relative.y.raw()));
        direction_gcd = std::gcd(
            direction_gcd, absolute_for_gcd(relative.z.raw()));
        diagnostics.push_back({
            relation_index,
            relation.relation,
            relative,
            direction_gcd,
            direction,
            std::bit_cast<std::uint64_t>(target_multiple),
            multiple});
        const auto impulse = impulse_from_direction(direction, multiple);
        packets[first_index].momentum += impulse;
        packets[second_index].momentum -= impulse;
    }
    return {
        StepStatus::accepted,
        std::move(packets),
        {},
        {},
        std::move(diagnostics)};
}

[[nodiscard]] Position3 drift_displacement(
    const DynamicPacket& packet,
    Time timestep) {
    const auto diagnostic = primitive_momentum_diagnostic(packet);
    if (diagnostic.direction_gcd == 0) {
        return {};
    }
    auto first = diagnostic.direction_gcd;
    auto second = timestep.raw();
    auto denominator = packet.mass.raw();
    const auto first_divisor = std::gcd(
        absolute_for_gcd(first), denominator);
    first /= first_divisor;
    denominator /= first_divisor;
    const auto second_divisor = std::gcd(
        absolute_for_gcd(second), denominator);
    second /= second_divisor;
    denominator /= second_divisor;
    const auto multiple =
        authoritative_drift_state_bridge::nearest_even_rational(
            detail::checked_multiply(first, second), denominator);
    return make_position({
        detail::checked_multiply(
            diagnostic.primitive_direction[0], multiple),
        detail::checked_multiply(
            diagnostic.primitive_direction[1], multiple),
        detail::checked_multiply(
            diagnostic.primitive_direction[2], multiple),
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
        throw std::invalid_argument("corefinement reference relation coincident");
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
    const PhaseState& state,
    std::vector<DynamicPacket> packets) {
    return {state.physical_time, std::move(packets)};
}

void append_stage(
    std::vector<StageRecord>& stages,
    StageKind kind,
    const PhaseState& state) {
    StageRecord record{};
    record.stage = kind;
    record.invariants =
        phase_space_time_corefinement::evaluate_exact_invariants(state.packets);
    record.state_hash = time_foundation::hash_phase_state(state);
    record.primitive_momenta.reserve(state.packets.size());
    for (const auto& packet : state.packets) {
        record.primitive_momenta.push_back(
            primitive_momentum_diagnostic(packet));
    }
    stages.push_back(std::move(record));
}

[[nodiscard]] DynamicPacket scale_packet(
    const DynamicPacket& packet,
    Scalar position_factor,
    Scalar momentum_factor) {
    auto result = packet;
    result.position = {
        Length::from_raw(detail::checked_multiply(
            packet.position.x.raw(), position_factor)),
        Length::from_raw(detail::checked_multiply(
            packet.position.y.raw(), position_factor)),
        Length::from_raw(detail::checked_multiply(
            packet.position.z.raw(), position_factor)),
    };
    result.momentum = {
        Momentum::from_raw(detail::checked_multiply(
            packet.momentum.x.raw(), momentum_factor)),
        Momentum::from_raw(detail::checked_multiply(
            packet.momentum.y.raw(), momentum_factor)),
        Momentum::from_raw(detail::checked_multiply(
            packet.momentum.z.raw(), momentum_factor)),
    };
    return result;
}

} // namespace

UnitProfile unit_profile(std::uint32_t level) {
    if (level > maximum_level) {
        throw std::invalid_argument("unregistered corefinement level");
    }
    const auto time_factor = power_of_two(3U * level);
    const auto length_factor = power_of_two(6U * level);
    UnitProfile result{};
    result.level = level;
    result.length_quantum_m = reduced(
        1U, checked_u64_multiply(UINT64_C(128000000000), length_factor));
    result.mass_quantum_kg = {1U, 524288U};
    result.time_quantum_s = reduced(
        1U, checked_u64_multiply(UINT64_C(1000000000), time_factor));
    result.momentum_quantum_kg_m_per_s = reduced(
        1U, checked_u64_multiply(UINT64_C(67108864), time_factor));
    result.energy_quantum_j = reduced(
        1U, checked_u64_multiply(UINT64_C(8589934592), length_factor));
    result.force_quantum_n = {1953125U, 131072U};
    validate_unit_profile(result);
    return result;
}

void validate_unit_profile(const UnitProfile& profile) {
    if (profile.level > maximum_level) {
        throw std::invalid_argument("unregistered corefinement level");
    }
    const auto positive = [](mechanics::PositiveRational value) {
        return value.numerator != 0U && value.denominator != 0U;
    };
    if (!positive(profile.length_quantum_m) ||
        !positive(profile.mass_quantum_kg) ||
        !positive(profile.time_quantum_s) ||
        !positive(profile.momentum_quantum_kg_m_per_s) ||
        !positive(profile.energy_quantum_j) ||
        !positive(profile.force_quantum_n)) {
        throw std::invalid_argument(
            "stop_corefinement_unit_contract_inconsistent");
    }
    bool consistent = false;
    try {
        const auto velocity = divide(
            profile.length_quantum_m, profile.time_quantum_s);
        const auto momentum = multiply(profile.mass_quantum_kg, velocity);
        const auto energy = multiply(momentum, velocity);
        const auto force = divide(energy, profile.length_quantum_m);
        consistent =
            momentum == profile.momentum_quantum_kg_m_per_s &&
            energy == profile.energy_quantum_j &&
            force == profile.force_quantum_n &&
            multiply(
                divide(
                    profile.momentum_quantum_kg_m_per_s,
                    profile.mass_quantum_kg),
                divide(
                    profile.time_quantum_s,
                    profile.length_quantum_m)) ==
                mechanics::PositiveRational{1U, 1U};
    } catch (const std::overflow_error&) {
        consistent = false;
    }
    if (!consistent) {
        throw std::invalid_argument(
            "stop_corefinement_unit_contract_inconsistent");
    }
}

std::string hexadecimal(const SignedMagnitude192& input) {
    const auto value = normalized(input);
    if (is_zero(value)) {
        return "0";
    }
    std::ostringstream stream;
    if (value.negative) {
        stream << '-';
    }
    stream << "0x" << std::hex;
    bool emitted = false;
    for (std::size_t index = value.magnitude.size(); index-- > 0U;) {
        if (!emitted) {
            if (value.magnitude[index] == 0U) {
                continue;
            }
            stream << value.magnitude[index];
            emitted = true;
        } else {
            stream << std::setw(16) << std::setfill('0')
                   << value.magnitude[index];
        }
    }
    return stream.str();
}

ExactInvariants evaluate_exact_invariants(
    std::span<const DynamicPacket> packets) {
    ExactInvariants result{};
    for (const auto& packet : packets) {
        result.total_momentum += packet.momentum;
        result.orbital_angular_momentum.x = add_signed(
            result.orbital_angular_momentum.x,
            product_difference(
                packet.position.y.raw(), packet.momentum.z.raw(),
                packet.position.z.raw(), packet.momentum.y.raw()));
        result.orbital_angular_momentum.y = add_signed(
            result.orbital_angular_momentum.y,
            product_difference(
                packet.position.z.raw(), packet.momentum.x.raw(),
                packet.position.x.raw(), packet.momentum.z.raw()));
        result.orbital_angular_momentum.z = add_signed(
            result.orbital_angular_momentum.z,
            product_difference(
                packet.position.x.raw(), packet.momentum.y.raw(),
                packet.position.y.raw(), packet.momentum.x.raw()));
    }
    return result;
}

PrimitiveMomentumDiagnostic primitive_momentum_diagnostic(
    const DynamicPacket& packet) {
    auto divisor = std::gcd(
        absolute_for_gcd(packet.momentum.x.raw()),
        absolute_for_gcd(packet.momentum.y.raw()));
    divisor = std::gcd(
        divisor, absolute_for_gcd(packet.momentum.z.raw()));
    PrimitiveMomentumDiagnostic result{};
    result.packet_id = packet.id;
    result.momentum = packet.momentum;
    result.direction_gcd = divisor;
    if (divisor != 0) {
        result.primitive_direction = {
            packet.momentum.x.raw() / divisor,
            packet.momentum.y.raw() / divisor,
            packet.momentum.z.raw() / divisor};
    }
    return result;
}

Position3 evaluate_directional_drift(
    const DynamicPacket& packet,
    Time timestep) {
    return drift_displacement(packet, timestep);
}

PhaseState map_level_zero_state(
    const PhaseState& level_zero_state,
    std::uint32_t level) {
    if (level > maximum_level) {
        throw std::invalid_argument("unregistered corefinement level");
    }
    const auto position_factor = static_cast<Scalar>(power_of_two(6U * level));
    const auto momentum_factor = static_cast<Scalar>(power_of_two(3U * level));
    const auto time_factor = momentum_factor;
    PhaseState result{};
    result.physical_time = Time::from_raw(detail::checked_multiply(
        level_zero_state.physical_time.raw(), time_factor));
    result.packets.reserve(level_zero_state.packets.size());
    for (const auto& packet : level_zero_state.packets) {
        result.packets.push_back(
            scale_packet(packet, position_factor, momentum_factor));
    }
    return {result.physical_time, canonical_packets(result.packets)};
}

DynamicModel build_registered_model(
    std::span<const DynamicPacket> level_zero_reference_packets,
    std::span<const BondRelation> relations,
    std::uint32_t level) {
    const auto base = time_foundation::build_registered_model(
        level_zero_reference_packets, relations);
    const auto mapped = map_level_zero_state(
        {{}, std::vector<DynamicPacket>(
                 level_zero_reference_packets.begin(),
                 level_zero_reference_packets.end())},
        level);
    return {
        level,
        unit_profile(level),
        mapped.packets,
        base.frozen_force,
    };
}

EnergyDiagnostic evaluate_energy(
    const DynamicModel& model,
    const PhaseState& state) {
    validate_unit_profile(model.units);
    const auto packets = canonical_packets(state.packets);
    const auto reference = mapped_packets(model.reference_packets, model.units);
    const auto current = mapped_packets(packets, model.units);
    const auto force_value = geometry::evaluate_resolved_spatial_force(
        model.frozen_force,
        reference,
        current,
        geometry::GeometryPath::cancellation_resistant_binary64);
    if (force_value.status != geometry::ResolvedForceStatus::evaluated) {
        return {};
    }
    const auto pq = static_cast<long double>(
        rational_value(model.units.momentum_quantum_kg_m_per_s));
    const auto mq = static_cast<long double>(
        rational_value(model.units.mass_quantum_kg));
    long double kinetic = 0.0L;
    Energy floored{};
    for (const auto& packet : packets) {
        long double squared_momentum = 0.0L;
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            const auto value = static_cast<long double>(
                component(packet.momentum, axis)) * pq;
            squared_momentum += value * value;
        }
        kinetic += squared_momentum /
            (2.0L * static_cast<long double>(packet.mass.raw()) * mq);
        floored += exact_kinetic_floor(packet.mass, packet.momentum);
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
            "corefinement KDK requires nonzero even timestep and model");
    }
    validate_unit_profile(model.units);
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
        auto first = kick(model, result.prior_state.packets, kick_interval);
        if (first.status != StepStatus::accepted) {
            return reject(
                first.status,
                first.failed_relation_index,
                first.failed_relation);
        }
        auto working = with_packets(result.prior_state, std::move(first.packets));
        append_stage(result.stages, StageKind::first_kick, working);
        result.stages.back().primitive_relations = std::move(first.diagnostics);
        if (result.stages.back().invariants != initial_invariants) {
            return reject(StepStatus::invariant_failure, {}, {});
        }

        auto proposed_packets = working.packets;
        for (auto& packet : proposed_packets) {
            packet.position += drift_displacement(packet, input.timestep);
        }
        const auto chord = check_chords(model, working.packets, proposed_packets);
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
            auto second = kick(model, working.packets, kick_interval);
            if (second.status != StepStatus::accepted) {
                return reject(
                    second.status,
                    second.failed_relation_index,
                    second.failed_relation);
            }
            working.packets = std::move(second.packets);
            append_stage(result.stages, StageKind::second_kick, working);
            result.stages.back().primitive_relations =
                std::move(second.diagnostics);
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
        throw std::invalid_argument("corefinement trajectory requires steps");
    }
    TrajectoryResult result{};
    result.path = path;
    result.initial_state = {
        initial_state.physical_time, canonical_packets(initial_state.packets)};
    result.final_state = result.initial_state;
    result.requested_steps = step_count;
    const auto initial_invariants =
        phase_space_time_corefinement::evaluate_exact_invariants(
            result.initial_state.packets);
    const auto initial_energy = evaluate_energy(model, result.initial_state);
    if (initial_energy.evaluated) {
        result.mechanical_energy_j.push_back(initial_energy.mechanical_energy_j);
    }
    for (std::uint64_t index = 0; index < step_count; ++index) {
        const auto step = evaluate_step(
            model, {path, result.final_state, timestep});
        for (const auto& stage : step.stages) {
            for (const auto& diagnostic : stage.primitive_momenta) {
                result.primitive_records.push_back(
                    {index, stage.stage, diagnostic});
            }
            for (const auto& diagnostic : stage.primitive_relations) {
                result.relation_records.push_back(
                    {index, stage.stage, diagnostic});
            }
        }
        auto event_hash = time_foundation::hash_phase_state(step.next_state);
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
    const auto final_invariants =
        phase_space_time_corefinement::evaluate_exact_invariants(
            result.final_state.packets);
    result.exact_momentum_preserved =
        final_invariants.total_momentum == initial_invariants.total_momentum;
    result.exact_orbital_angular_momentum_preserved =
        final_invariants.orbital_angular_momentum ==
        initial_invariants.orbital_angular_momentum;
    return result;
}

} // namespace mls::experimental::phase_space_time_corefinement
