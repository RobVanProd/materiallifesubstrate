#include "mls/conservative_force_consistency_lab.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>
#include <utility>

namespace mls::experimental::conservative_force_consistency {
namespace {

static_assert(sizeof(double) == 8U);
static_assert(std::numeric_limits<double>::digits == 53);
static_assert(std::numeric_limits<double>::is_iec559);

using constitutive::RelationEnergyOperator;
using observation::BondRelation;
using observation::DenseMatrix;
using observation::MechanicalPacket;

[[nodiscard]] bool finite(Vec3d value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) &&
        std::isfinite(value.z);
}

[[nodiscard]] double stable_norm(Vec3d value) noexcept {
    const auto scale =
        std::max({std::abs(value.x), std::abs(value.y), std::abs(value.z)});
    if (scale == 0.0) {
        return 0.0;
    }
    if (!std::isfinite(scale)) {
        return std::numeric_limits<double>::infinity();
    }
    const auto x = value.x / scale;
    const auto y = value.y / scale;
    const auto z = value.z / scale;
    return scale * std::sqrt(x * x + y * y + z * z);
}

[[nodiscard]] std::vector<MechanicalPacket> canonical_packets(
    std::span<const MechanicalPacket> packets) {
    std::vector<MechanicalPacket> result(packets.begin(), packets.end());
    std::ranges::sort(result, {}, &MechanicalPacket::id);
    for (std::size_t index = 0; index < result.size(); ++index) {
        const auto& packet = result[index];
        if (packet.id == 0U || packet.mass_quanta <= 0 ||
            !finite(packet.position_m) || !finite(packet.velocity_m_per_s)) {
            throw std::invalid_argument(
                "force packets require positive IDs/mass and finite state");
        }
        if (index != 0U && result[index - 1U].id == packet.id) {
            throw std::invalid_argument("force packet IDs must be unique");
        }
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

void validate_local_reference_metadata(
    const RelationEnergyOperator& energy_operator) {
    if (energy_operator.family !=
        constitutive::EnergyFamily::local_incident_collective) {
        return;
    }
    if (energy_operator.reference_lengths_m.size() !=
        energy_operator.relations.size() ||
        energy_operator.local_contributions.empty()) {
        throw std::invalid_argument(
            "local force reference metadata dimensions disagree");
    }
    double expected_radius = 0.0;
    for (const auto length : energy_operator.reference_lengths_m) {
        if (!(length > 0.0) || !std::isfinite(length)) {
            throw std::invalid_argument(
                "local force reference lengths must be positive and finite");
        }
        expected_radius = std::max(expected_radius, length);
    }
    if (energy_operator.locality_radius_m != expected_radius) {
        throw std::invalid_argument(
            "local force locality radius is stale relative to reference data");
    }
    std::set<std::uint64_t> contribution_ids;
    for (const auto& contribution : energy_operator.local_contributions) {
        if (contribution.packet_id == 0U ||
            !contribution_ids.insert(contribution.packet_id).second ||
            !(contribution.weighted_length_moment_m2 > 0.0) ||
            !std::isfinite(contribution.weighted_length_moment_m2)) {
            throw std::invalid_argument(
                "local force contribution metadata is invalid");
        }
        std::size_t incident_count = 0U;
        double maximum_incident_length = 0.0;
        for (std::size_t index = 0;
             index < energy_operator.relations.size(); ++index) {
            const auto relation = energy_operator.relations[index];
            if (relation.first_id == contribution.packet_id ||
                relation.second_id == contribution.packet_id) {
                ++incident_count;
                maximum_incident_length = std::max(
                    maximum_incident_length,
                    energy_operator.reference_lengths_m[index]);
            }
        }
        if (incident_count == 0U ||
            contribution.incident_relation_count != incident_count ||
            contribution.maximum_incident_length_m !=
                maximum_incident_length) {
            throw std::invalid_argument(
                "local force incident reference metadata is stale");
        }
    }
}

void validate_frozen_operator(
    const RelationEnergyOperator& energy_operator,
    std::span<const MechanicalPacket> current) {
    const auto relation_count = energy_operator.relations.size();
    if (energy_operator.reference_lengths_m.size() != relation_count ||
        energy_operator.h_j_per_m2.row_count() != relation_count ||
        energy_operator.h_j_per_m2.column_count() != relation_count) {
        throw std::invalid_argument(
            "frozen force operator dimensions disagree");
    }
    const auto lookup = packet_lookup(current);
    std::set<std::pair<std::uint64_t, std::uint64_t>> undirected_relations;
    for (std::size_t index = 0; index < relation_count; ++index) {
        const auto relation = energy_operator.relations[index];
        if (relation.first_id == 0U || relation.second_id == 0U ||
            relation.first_id == relation.second_id ||
            !lookup.contains(relation.first_id) ||
            !lookup.contains(relation.second_id)) {
            throw std::invalid_argument(
                "force relations must be valid and reference current packets");
        }
        const auto key = std::minmax(relation.first_id, relation.second_id);
        if (!undirected_relations.emplace(key.first, key.second).second) {
            throw std::invalid_argument("force relations must be unique");
        }
        const auto reference_length =
            energy_operator.reference_lengths_m[index];
        if (!(reference_length > 0.0) || !std::isfinite(reference_length)) {
            throw std::invalid_argument(
                "frozen force reference lengths must be positive and finite");
        }
    }
    for (std::size_t row = 0; row < relation_count; ++row) {
        for (std::size_t column = 0; column < relation_count; ++column) {
            const auto value = energy_operator.h_j_per_m2(row, column);
            if (!std::isfinite(value)) {
                throw std::invalid_argument("frozen force H must be finite");
            }
            if (value != energy_operator.h_j_per_m2(column, row)) {
                throw std::invalid_argument(
                    "force H must be exactly mirrored symmetric storage");
            }
        }
    }
}

[[nodiscard]] double checked_double(double value, const char* message) {
    if (!std::isfinite(value)) {
        throw std::overflow_error(message);
    }
    return value;
}

[[nodiscard]] Vec3d checked_vec(Vec3d value, const char* message) {
    return {checked_double(value.x, message), checked_double(value.y, message),
            checked_double(value.z, message)};
}

void add(Vec3d& target, Vec3d value) noexcept {
    target += value;
}

[[nodiscard]] DenseMatrix material_hessian(
    const observation::LinearizedOperator& rigidity,
    const RelationEnergyOperator& energy_operator) {
    const auto relation_count = rigidity.matrix.row_count();
    const auto coordinate_count = rigidity.matrix.column_count();
    DenseMatrix h_times_r(relation_count, coordinate_count);
    for (std::size_t row = 0; row < relation_count; ++row) {
        for (std::size_t column = 0; column < coordinate_count; ++column) {
            double value = 0.0;
            for (std::size_t inner = 0; inner < relation_count; ++inner) {
                value += energy_operator.h_j_per_m2(row, inner) *
                    rigidity.matrix(inner, column);
            }
            h_times_r(row, column) = checked_double(
                value, "material H*R overflow");
        }
    }
    DenseMatrix result(coordinate_count, coordinate_count);
    for (std::size_t row = 0; row < coordinate_count; ++row) {
        for (std::size_t column = 0; column < coordinate_count; ++column) {
            double value = 0.0;
            for (std::size_t relation = 0; relation < relation_count;
                 ++relation) {
                value += rigidity.matrix(relation, row) *
                    h_times_r(relation, column);
            }
            result(row, column) = checked_double(
                value, "material R^T*H*R overflow");
        }
    }
    return result;
}

[[nodiscard]] bool same_local_contribution(
    const constitutive::LocalCollectiveContribution& lhs,
    const constitutive::LocalCollectiveContribution& rhs) noexcept {
    return lhs.packet_id == rhs.packet_id &&
        lhs.incident_relation_count == rhs.incident_relation_count &&
        lhs.weighted_length_moment_m2 == rhs.weighted_length_moment_m2 &&
        lhs.maximum_incident_length_m == rhs.maximum_incident_length_m &&
        lhs.dilatational_h_j_per_m2 == rhs.dilatational_h_j_per_m2 &&
        lhs.deviatoric_h_j_per_m2 == rhs.deviatoric_h_j_per_m2 &&
        lhs.dilatational_factor_sqrt_j_per_m ==
            rhs.dilatational_factor_sqrt_j_per_m &&
        lhs.deviatoric_factor_sqrt_j_per_m ==
            rhs.deviatoric_factor_sqrt_j_per_m;
}

[[nodiscard]] bool same_non_h_operator_data(
    const RelationEnergyOperator& lhs,
    const RelationEnergyOperator& rhs) noexcept {
    if (lhs.family != rhs.family || lhs.relations != rhs.relations ||
        lhs.reference_lengths_m != rhs.reference_lengths_m ||
        lhs.factor_sqrt_j_per_m != rhs.factor_sqrt_j_per_m ||
        lhs.locality_radius_m != rhs.locality_radius_m ||
        lhs.nonlocal_off_diagonal_count != rhs.nonlocal_off_diagonal_count ||
        lhs.local_contributions.size() != rhs.local_contributions.size()) {
        return false;
    }
    for (std::size_t index = 0; index < lhs.local_contributions.size();
         ++index) {
        if (!same_local_contribution(
                lhs.local_contributions[index], rhs.local_contributions[index])) {
            return false;
        }
    }
    return true;
}

} // namespace

std::string_view status_name(ForceDomainStatus status) noexcept {
    switch (status) {
    case ForceDomainStatus::evaluated:
        return "evaluated";
    case ForceDomainStatus::coincident_relation:
        return "coincident_relation";
    }
    return "unknown";
}

FrozenForceOperator freeze_symmetric_force_operator(
    const RelationEnergyOperator& parent_operator) {
    validate_local_reference_metadata(parent_operator);
    const auto count = parent_operator.relations.size();
    if (parent_operator.reference_lengths_m.size() != count ||
        parent_operator.h_j_per_m2.row_count() != count ||
        parent_operator.h_j_per_m2.column_count() != count) {
        throw std::invalid_argument("parent force operator dimensions disagree");
    }
    FrozenForceOperator result{};
    result.parent_operator = parent_operator;
    result.force_operator = parent_operator;
    std::set<std::uint64_t> packet_ids;
    for (const auto relation : parent_operator.relations) {
        packet_ids.insert(relation.first_id);
        packet_ids.insert(relation.second_id);
    }
    for (const auto& contribution : parent_operator.local_contributions) {
        packet_ids.insert(contribution.packet_id);
    }
    const auto dimension = std::max(
        {std::size_t{6}, 3U * packet_ids.size(), count});
    for (std::size_t row = 0; row < count; ++row) {
        const auto diagonal = parent_operator.h_j_per_m2(row, row);
        if (!std::isfinite(diagonal)) {
            throw std::invalid_argument("parent force H must be finite");
        }
        result.force_operator.h_j_per_m2(row, row) = diagonal;
        result.maximum_parent_h_magnitude_j_per_m2 = std::max(
            result.maximum_parent_h_magnitude_j_per_m2,
            std::abs(diagonal));
        for (std::size_t column = row + 1U; column < count; ++column) {
            const auto upper = parent_operator.h_j_per_m2(row, column);
            const auto lower = parent_operator.h_j_per_m2(column, row);
            if (!std::isfinite(upper) || !std::isfinite(lower)) {
                throw std::invalid_argument("parent force H must be finite");
            }
            // The registered construction is deliberately one addition and
            // one exactly representable multiplication by one half.
            const auto sum = upper + lower;
            if (!std::isfinite(sum)) {
                throw std::overflow_error("symmetric force H average overflow");
            }
            const auto frozen = 0.5 * sum;
            result.force_operator.h_j_per_m2(row, column) = frozen;
            result.force_operator.h_j_per_m2(column, row) = frozen;
            result.maximum_parent_h_magnitude_j_per_m2 = std::max(
                {result.maximum_parent_h_magnitude_j_per_m2,
                 std::abs(upper), std::abs(lower)});
            result.maximum_correction_j_per_m2 = std::max(
                {result.maximum_correction_j_per_m2,
                 std::abs(frozen - upper), std::abs(frozen - lower)});
        }
    }
    result.correction_tolerance_j_per_m2 = 32768.0 *
        static_cast<double>(dimension) *
        std::numeric_limits<double>::epsilon() *
        std::max(result.maximum_parent_h_magnitude_j_per_m2,
                 std::numeric_limits<double>::min());
    if (result.maximum_correction_j_per_m2 >
        result.correction_tolerance_j_per_m2) {
        throw std::invalid_argument(
            "parent force H asymmetry exceeds frozen correction bound");
    }
    return result;
}

namespace {

void validate_frozen_integrity(const FrozenForceOperator& frozen) {
    const auto expected =
        freeze_symmetric_force_operator(frozen.parent_operator);
    if (!same_non_h_operator_data(
            frozen.parent_operator, frozen.force_operator) ||
        !same_non_h_operator_data(
            expected.force_operator, frozen.force_operator) ||
        expected.force_operator.h_j_per_m2 !=
            frozen.force_operator.h_j_per_m2 ||
        expected.maximum_parent_h_magnitude_j_per_m2 !=
            frozen.maximum_parent_h_magnitude_j_per_m2 ||
        expected.maximum_correction_j_per_m2 !=
            frozen.maximum_correction_j_per_m2 ||
        expected.correction_tolerance_j_per_m2 !=
            frozen.correction_tolerance_j_per_m2) {
        throw std::invalid_argument(
            "frozen force operator fails parent/canonical integrity check");
    }
}

} // namespace

namespace {

[[nodiscard]] RelationEnergyOperator permute_one_operator(
    const RelationEnergyOperator& energy_operator,
    std::span<const std::size_t> new_to_old) {
    const auto count = energy_operator.relations.size();
    if (new_to_old.size() != count ||
        energy_operator.reference_lengths_m.size() != count ||
        energy_operator.h_j_per_m2.row_count() != count ||
        energy_operator.h_j_per_m2.column_count() != count ||
        energy_operator.factor_sqrt_j_per_m.column_count() != count) {
        throw std::invalid_argument("relation permutation dimensions disagree");
    }
    std::vector<std::uint8_t> seen(count, 0U);
    for (const auto source : new_to_old) {
        if (source >= count || std::exchange(seen[source], std::uint8_t{1}) != 0U) {
            throw std::invalid_argument(
                "relation permutation must be a complete bijection");
        }
    }
    auto result = energy_operator;
    for (std::size_t row = 0; row < count; ++row) {
        result.relations[row] = energy_operator.relations[new_to_old[row]];
        result.reference_lengths_m[row] =
            energy_operator.reference_lengths_m[new_to_old[row]];
        for (std::size_t column = 0; column < count; ++column) {
            result.h_j_per_m2(row, column) = energy_operator.h_j_per_m2(
                new_to_old[row], new_to_old[column]);
        }
    }
    for (std::size_t factor_row = 0;
         factor_row < result.factor_sqrt_j_per_m.row_count(); ++factor_row) {
        for (std::size_t column = 0; column < count; ++column) {
            result.factor_sqrt_j_per_m(factor_row, column) =
                energy_operator.factor_sqrt_j_per_m(
                    factor_row, new_to_old[column]);
        }
    }
    for (std::size_t local_index = 0;
         local_index < result.local_contributions.size(); ++local_index) {
        auto& target = result.local_contributions[local_index];
        const auto& source = energy_operator.local_contributions[local_index];
        for (std::size_t row = 0; row < count; ++row) {
            for (std::size_t column = 0; column < count; ++column) {
                target.dilatational_h_j_per_m2(row, column) =
                    source.dilatational_h_j_per_m2(
                        new_to_old[row], new_to_old[column]);
                target.deviatoric_h_j_per_m2(row, column) =
                    source.deviatoric_h_j_per_m2(
                        new_to_old[row], new_to_old[column]);
            }
        }
        for (std::size_t factor_row = 0;
             factor_row < target.dilatational_factor_sqrt_j_per_m.row_count();
             ++factor_row) {
            for (std::size_t column = 0; column < count; ++column) {
                target.dilatational_factor_sqrt_j_per_m(factor_row, column) =
                    source.dilatational_factor_sqrt_j_per_m(
                        factor_row, new_to_old[column]);
            }
        }
        for (std::size_t factor_row = 0;
             factor_row < target.deviatoric_factor_sqrt_j_per_m.row_count();
             ++factor_row) {
            for (std::size_t column = 0; column < count; ++column) {
                target.deviatoric_factor_sqrt_j_per_m(factor_row, column) =
                    source.deviatoric_factor_sqrt_j_per_m(
                        factor_row, new_to_old[column]);
            }
        }
    }
    return result;
}

} // namespace

FrozenForceOperator permute_relation_coordinates(
    const FrozenForceOperator& energy_operator,
    std::span<const std::size_t> new_to_old) {
    FrozenForceOperator result = energy_operator;
    result.parent_operator =
        permute_one_operator(energy_operator.parent_operator, new_to_old);
    result.force_operator =
        permute_one_operator(energy_operator.force_operator, new_to_old);
    return result;
}

SpatialForceEvaluation evaluate_spatial_force(
    const FrozenForceOperator& frozen_operator,
    std::span<const MechanicalPacket> current_packets) {
    validate_frozen_integrity(frozen_operator);
    const auto& energy_operator = frozen_operator.force_operator;
    const auto current = canonical_packets(current_packets);
    validate_frozen_operator(energy_operator, current);
    const auto lookup = packet_lookup(current);
    const auto relation_count = energy_operator.relations.size();

    // Stage all relation geometry before allocating any actionable output. A
    // coincident edge therefore cannot leak a partial force evaluation.
    std::vector<double> current_lengths;
    std::vector<double> extensions;
    std::vector<Vec3d> directions;
    current_lengths.reserve(relation_count);
    extensions.reserve(relation_count);
    directions.reserve(relation_count);
    for (std::size_t index = 0; index < relation_count; ++index) {
        const auto relation = energy_operator.relations[index];
        const auto offset = current[lookup.at(relation.second_id)].position_m -
            current[lookup.at(relation.first_id)].position_m;
        if (!finite(offset)) {
            throw std::overflow_error("current relation offset overflow");
        }
        const auto length = stable_norm(offset);
        if (length == 0.0) {
            SpatialForceEvaluation failure{};
            failure.status = ForceDomainStatus::coincident_relation;
            failure.failed_relation_index = index;
            failure.failed_relation = relation;
            return failure;
        }
        if (!std::isfinite(length)) {
            throw std::overflow_error("current relation length overflow");
        }
        const auto extension =
            length - energy_operator.reference_lengths_m[index];
        // Spell out the three binary64 divisions. Vec3d's generic division
        // helper is implemented as reciprocal-then-multiply, which is a
        // different floating-point operation sequence and would make the
        // evidence producer disagree with the registered binary64 reference
        // path by one or more ulps.
        const Vec3d direction{
            offset.x / length, offset.y / length, offset.z / length};
        if (!std::isfinite(extension) || !finite(direction)) {
            throw std::overflow_error("current force coordinate overflow");
        }
        current_lengths.push_back(length);
        extensions.push_back(extension);
        directions.push_back(direction);
    }

    // The conjugate vector is evaluated once in the frozen canonical relation
    // coordinates. Relation assembly below never recomputes H*e.
    std::vector<double> conjugate(relation_count, 0.0);
    for (std::size_t row = 0; row < relation_count; ++row) {
        double value = 0.0;
        for (std::size_t column = 0; column < relation_count; ++column) {
            value += energy_operator.h_j_per_m2(row, column) *
                extensions[column];
        }
        conjugate[row] = checked_double(value, "relation conjugate overflow");
    }
    double energy_twice = 0.0;
    for (std::size_t index = 0; index < relation_count; ++index) {
        energy_twice += extensions[index] * conjugate[index];
    }

    SpatialForceEvaluation result{};
    result.status = ForceDomainStatus::evaluated;
    result.energy_j = checked_double(
        0.5 * energy_twice, "finite relation energy overflow");
    result.current_rigidity.kind =
        observation::ObservableKind::central_bond_length_rate;
    result.current_rigidity.packet_ids.reserve(current.size());
    for (const auto& packet : current) {
        result.current_rigidity.packet_ids.push_back(packet.id);
    }
    result.current_rigidity.matrix =
        DenseMatrix(relation_count, 3U * current.size());
    result.relation_coordinates.reserve(relation_count);
    std::vector<Vec3d> accumulated(current.size());
    for (std::size_t index = 0; index < relation_count; ++index) {
        const auto relation = energy_operator.relations[index];
        const auto first = lookup.at(relation.first_id);
        const auto second = lookup.at(relation.second_id);
        const auto direction = directions[index];
        const auto relation_force = conjugate[index] * direction;
        add(accumulated[first], relation_force);
        add(accumulated[second], -relation_force);
        result.relation_coordinates.push_back(
            {index, relation, energy_operator.reference_lengths_m[index],
             current_lengths[index], extensions[index], conjugate[index],
             direction});
        const std::array components{direction.x, direction.y, direction.z};
        for (std::size_t axis = 0; axis < 3U; ++axis) {
            result.current_rigidity.matrix(index, 3U * first + axis) =
                -components[axis];
            result.current_rigidity.matrix(index, 3U * second + axis) =
                components[axis];
        }
    }
    result.packet_forces.reserve(current.size());
    for (std::size_t index = 0; index < current.size(); ++index) {
        result.packet_forces.push_back(
            {current[index].id,
             checked_vec(accumulated[index], "packet force overflow")});
    }
    return result;
}

ContinuousForceIdentities evaluate_continuous_identities(
    const SpatialForceEvaluation& force,
    std::span<const MechanicalPacket> current_packets,
    Vec3d second_origin_m) {
    if (force.status != ForceDomainStatus::evaluated) {
        throw std::domain_error(
            "continuous identities require a noncoincident force evaluation");
    }
    if (!finite(second_origin_m)) {
        throw std::invalid_argument("torque origin must be finite");
    }
    const auto current = canonical_packets(current_packets);
    if (force.packet_forces.size() != current.size() ||
        force.current_rigidity.packet_ids.size() != current.size()) {
        throw std::invalid_argument("force/current packet sets disagree");
    }
    const auto lookup = packet_lookup(current);
    Vec3d total_force{};
    Vec3d torque_origin{};
    Vec3d torque_second{};
    double force_power = 0.0;
    for (std::size_t index = 0; index < current.size(); ++index) {
        if (force.packet_forces[index].packet_id != current[index].id ||
            force.current_rigidity.packet_ids[index] != current[index].id ||
            !finite(force.packet_forces[index].force_n)) {
            throw std::invalid_argument("force/current canonical order disagrees");
        }
        const auto packet_force = force.packet_forces[index].force_n;
        add(total_force, packet_force);
        const auto about_origin =
            cross(current[index].position_m, packet_force);
        add(torque_origin, about_origin);
        const auto shifted_position =
            current[index].position_m - second_origin_m;
        const auto about_second = cross(shifted_position, packet_force);
        add(torque_second, about_second);
        force_power += packet_force.x * current[index].velocity_m_per_s.x +
            packet_force.y * current[index].velocity_m_per_s.y +
            packet_force.z * current[index].velocity_m_per_s.z;
    }
    double energy_rate = 0.0;
    for (const auto& relation : force.relation_coordinates) {
        const auto& first = current[lookup.at(relation.relation.first_id)];
        const auto& second = current[lookup.at(relation.relation.second_id)];
        const auto relative_velocity =
            second.velocity_m_per_s - first.velocity_m_per_s;
        const auto extension_rate =
            relation.direction_first_to_second.x * relative_velocity.x +
            relation.direction_first_to_second.y * relative_velocity.y +
            relation.direction_first_to_second.z * relative_velocity.z;
        energy_rate += relation.conjugate_force_n * extension_rate;
    }
    ContinuousForceIdentities result{};
    result.total_internal_force_n =
        checked_vec(total_force, "total force diagnostic overflow");
    result.torque_about_origin_n_m =
        checked_vec(torque_origin, "torque diagnostic overflow");
    result.torque_about_second_origin_n_m =
        checked_vec(torque_second, "translated torque diagnostic overflow");
    result.relation_energy_rate_w =
        checked_double(energy_rate, "energy-rate diagnostic overflow");
    result.force_power_w =
        checked_double(force_power, "power diagnostic overflow");
    result.power_identity_residual_w = checked_double(
        energy_rate + force_power, "power residual overflow");
    return result;
}

SpatialTangentEvaluation evaluate_spatial_tangent(
    const FrozenForceOperator& frozen_operator,
    std::span<const MechanicalPacket> current_packets) {
    const auto force = evaluate_spatial_force(frozen_operator, current_packets);
    if (force.status != ForceDomainStatus::evaluated) {
        SpatialTangentEvaluation failure{};
        failure.status = force.status;
        failure.failed_relation_index = force.failed_relation_index;
        failure.failed_relation = force.failed_relation;
        return failure;
    }
    SpatialTangentEvaluation result{};
    result.status = ForceDomainStatus::evaluated;
    result.packet_ids = force.current_rigidity.packet_ids;
    const auto coordinate_count = force.current_rigidity.matrix.column_count();
    result.material_energy_hessian_n_per_m =
        material_hessian(
            force.current_rigidity, frozen_operator.force_operator);
    result.geometric_energy_hessian_n_per_m =
        DenseMatrix(coordinate_count, coordinate_count);
    const auto current = canonical_packets(current_packets);
    const auto lookup = packet_lookup(current);
    for (const auto& relation : force.relation_coordinates) {
        const auto first = lookup.at(relation.relation.first_id);
        const auto second = lookup.at(relation.relation.second_id);
        const std::array n{relation.direction_first_to_second.x,
                           relation.direction_first_to_second.y,
                           relation.direction_first_to_second.z};
        for (std::size_t row_axis = 0; row_axis < 3U; ++row_axis) {
            for (std::size_t column_axis = 0; column_axis < 3U;
                 ++column_axis) {
                const auto identity =
                    row_axis == column_axis ? 1.0 : 0.0;
                const auto projector =
                    (identity - n[row_axis] * n[column_axis]) /
                    relation.current_length_m;
                const auto contribution =
                    relation.conjugate_force_n * projector;
                const auto first_row = 3U * first + row_axis;
                const auto second_row = 3U * second + row_axis;
                const auto first_column = 3U * first + column_axis;
                const auto second_column = 3U * second + column_axis;
                result.geometric_energy_hessian_n_per_m(
                    first_row, first_column) += contribution;
                result.geometric_energy_hessian_n_per_m(
                    second_row, second_column) += contribution;
                result.geometric_energy_hessian_n_per_m(
                    first_row, second_column) -= contribution;
                result.geometric_energy_hessian_n_per_m(
                    second_row, first_column) -= contribution;
            }
        }
    }
    result.total_energy_hessian_n_per_m =
        DenseMatrix(coordinate_count, coordinate_count);
    result.force_jacobian_n_per_m =
        DenseMatrix(coordinate_count, coordinate_count);
    for (std::size_t row = 0; row < coordinate_count; ++row) {
        for (std::size_t column = 0; column < coordinate_count; ++column) {
            const auto total =
                result.material_energy_hessian_n_per_m(row, column) +
                result.geometric_energy_hessian_n_per_m(row, column);
            if (!std::isfinite(total)) {
                throw std::overflow_error("finite force tangent overflow");
            }
            result.total_energy_hessian_n_per_m(row, column) = total;
            result.force_jacobian_n_per_m(row, column) = -total;
        }
    }
    return result;
}

double maximum_asymmetry(const DenseMatrix& matrix) noexcept {
    if (matrix.row_count() != matrix.column_count()) {
        return std::numeric_limits<double>::infinity();
    }
    double result = 0.0;
    for (std::size_t row = 0; row < matrix.row_count(); ++row) {
        for (std::size_t column = row + 1U;
             column < matrix.column_count(); ++column) {
            result = std::max(
                result,
                std::abs(matrix(row, column) - matrix(column, row)));
        }
    }
    return result;
}

} // namespace mls::experimental::conservative_force_consistency
