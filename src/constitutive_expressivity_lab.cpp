#include "mls/constitutive_expressivity_lab.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>
#include <tuple>
#include <utility>

namespace mls::experimental::constitutive_expressivity {
namespace {

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
                "constitutive packets require positive IDs/mass and finite state");
        }
        if (index != 0U && result[index - 1U].id == packet.id) {
            throw std::invalid_argument("constitutive packet IDs must be unique");
        }
    }
    return result;
}

[[nodiscard]] BondRelation canonical_relation(BondRelation relation) {
    if (relation.first_id == 0U || relation.second_id == 0U ||
        relation.first_id == relation.second_id) {
        throw std::invalid_argument("relation endpoints must be distinct positive IDs");
    }
    if (relation.second_id < relation.first_id) {
        std::swap(relation.first_id, relation.second_id);
    }
    return relation;
}

template <typename Entry, typename ScalarAccessor>
[[nodiscard]] std::vector<Entry> canonical_entries(
    std::span<const MechanicalPacket> packets, std::span<const Entry> entries,
    ScalarAccessor scalar) {
    const auto canonical = canonical_packets(packets);
    std::set<std::uint64_t> ids;
    for (const auto& packet : canonical) {
        ids.insert(packet.id);
    }
    std::vector<Entry> result(entries.begin(), entries.end());
    for (auto& entry : result) {
        entry.relation = canonical_relation(entry.relation);
        if (!ids.contains(entry.relation.first_id) ||
            !ids.contains(entry.relation.second_id)) {
            throw std::invalid_argument("relation endpoint is not a reference packet");
        }
        const auto value = scalar(entry);
        if (!(value > 0.0) || !std::isfinite(value)) {
            throw std::invalid_argument("constitutive relation scalar must be positive");
        }
    }
    std::ranges::sort(result, [](const auto& lhs, const auto& rhs) {
        return std::pair{lhs.relation.first_id, lhs.relation.second_id} <
            std::pair{rhs.relation.first_id, rhs.relation.second_id};
    });
    for (std::size_t index = 1; index < result.size(); ++index) {
        if (result[index - 1U].relation == result[index].relation) {
            throw std::invalid_argument("duplicate constitutive relation");
        }
    }
    return result;
}

[[nodiscard]] std::vector<BondRelation> canonical_relations(
    std::span<const MechanicalPacket> packets,
    std::span<const BondRelation> relations) {
    std::vector<WeightedRelation> weighted;
    weighted.reserve(relations.size());
    for (const auto relation : relations) {
        weighted.push_back({relation, 1.0});
    }
    const auto canonical = canonical_entries(
        packets, std::span<const WeightedRelation>(weighted),
        [](const auto& entry) { return entry.weight; });
    std::vector<BondRelation> result;
    result.reserve(canonical.size());
    for (const auto& entry : canonical) {
        result.push_back(entry.relation);
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

[[nodiscard]] std::vector<double> reference_lengths(
    std::span<const MechanicalPacket> canonical,
    std::span<const BondRelation> relations) {
    const auto lookup = packet_lookup(canonical);
    std::vector<double> result;
    result.reserve(relations.size());
    for (const auto relation : relations) {
        const auto offset = canonical[lookup.at(relation.second_id)].position_m -
            canonical[lookup.at(relation.first_id)].position_m;
        if (!finite(offset)) {
            throw std::overflow_error("relation coordinate subtraction overflow");
        }
        const auto length = stable_norm(offset);
        if (!(length > 0.0) || !std::isfinite(length)) {
            throw std::invalid_argument("relation reference length must be positive");
        }
        result.push_back(length);
    }
    return result;
}

[[nodiscard]] long double quadratic_form(
    const DenseMatrix& matrix, std::span<const double> vector) {
    if (matrix.row_count() != matrix.column_count() ||
        matrix.column_count() != vector.size()) {
        throw std::invalid_argument("quadratic-form dimensions disagree");
    }
    long double result = 0.0L;
    for (std::size_t row = 0; row < vector.size(); ++row) {
        long double product = 0.0L;
        for (std::size_t column = 0; column < vector.size(); ++column) {
            product += static_cast<long double>(matrix(row, column)) *
                vector[column];
        }
        result += static_cast<long double>(vector[row]) * product;
    }
    return result;
}

[[nodiscard]] long double factor_energy_twice(
    const DenseMatrix& factor, std::span<const double> vector) {
    if (factor.column_count() != vector.size()) {
        throw std::invalid_argument("energy-factor dimensions disagree");
    }
    long double result = 0.0L;
    for (std::size_t row = 0; row < factor.row_count(); ++row) {
        long double value = 0.0L;
        for (std::size_t column = 0; column < factor.column_count(); ++column) {
            value += static_cast<long double>(factor(row, column)) *
                vector[column];
        }
        result += value * value;
    }
    return result;
}

void add_matrix(DenseMatrix& target, const DenseMatrix& source) {
    if (target.row_count() != source.row_count() ||
        target.column_count() != source.column_count()) {
        throw std::invalid_argument("matrix-sum dimensions disagree");
    }
    for (std::size_t row = 0; row < target.row_count(); ++row) {
        for (std::size_t column = 0; column < target.column_count(); ++column) {
            target(row, column) += source(row, column);
        }
    }
}

[[nodiscard]] bool relations_share_packet(
    BondRelation lhs, BondRelation rhs) noexcept {
    return lhs.first_id == rhs.first_id || lhs.first_id == rhs.second_id ||
        lhs.second_id == rhs.first_id || lhs.second_id == rhs.second_id;
}

void validate_extension_compatibility(
    const RelationEnergyOperator& energy_operator,
    const RelationExtensionState& extensions) {
    if (energy_operator.relations != extensions.relations ||
        energy_operator.reference_lengths_m.size() !=
            extensions.reference_lengths_m.size() ||
        extensions.extensions_m.size() != energy_operator.relations.size() ||
        energy_operator.h_j_per_m2.row_count() !=
            energy_operator.relations.size() ||
        energy_operator.h_j_per_m2.column_count() !=
            energy_operator.relations.size()) {
        throw std::invalid_argument("energy operator and extension state disagree");
    }
    constexpr auto factor = 256.0;
    for (std::size_t index = 0;
         index < energy_operator.reference_lengths_m.size(); ++index) {
        const auto expected = energy_operator.reference_lengths_m[index];
        const auto actual = extensions.reference_lengths_m[index];
        const auto scale = std::max({1.0, std::abs(expected), std::abs(actual)});
        if (!std::isfinite(actual) ||
            std::abs(actual - expected) >
                factor * std::numeric_limits<double>::epsilon() * scale) {
            throw std::invalid_argument("extension state uses a different reference");
        }
    }
}

} // namespace

RelationExtensionState evaluate_finite_relation_extensions(
    std::span<const MechanicalPacket> reference_packets,
    std::span<const MechanicalPacket> current_packets,
    std::span<const BondRelation> relations) {
    const auto reference = canonical_packets(reference_packets);
    const auto current = canonical_packets(current_packets);
    if (reference.size() != current.size()) {
        throw std::invalid_argument("reference/current packet sets disagree");
    }
    for (std::size_t index = 0; index < reference.size(); ++index) {
        if (reference[index].id != current[index].id) {
            throw std::invalid_argument("reference/current packet IDs disagree");
        }
    }
    RelationExtensionState result{};
    result.relations = canonical_relations(reference, relations);
    result.reference_lengths_m = reference_lengths(reference, result.relations);
    const auto current_lengths = reference_lengths(current, result.relations);
    result.extensions_m.reserve(result.relations.size());
    for (std::size_t index = 0; index < result.relations.size(); ++index) {
        const auto extension =
            current_lengths[index] - result.reference_lengths_m[index];
        if (!std::isfinite(extension)) {
            throw std::overflow_error("finite relation extension overflow");
        }
        result.extensions_m.push_back(extension);
    }
    return result;
}

RelationExtensionState evaluate_linearized_relation_extensions(
    std::span<const MechanicalPacket> reference_packets,
    std::span<const PacketDisplacement> displacements_by_id,
    std::span<const BondRelation> relations) {
    const auto reference = canonical_packets(reference_packets);
    auto canonical_bonds = canonical_relations(reference, relations);
    const auto rigidity = observation::build_bond_rigidity_operator(
        reference, canonical_bonds);
    std::map<std::uint64_t, Vec3d> displacement;
    for (const auto& entry : displacements_by_id) {
        if (entry.packet_id == 0U || !finite(entry.displacement_m) ||
            !displacement.emplace(entry.packet_id, entry.displacement_m).second) {
            throw std::invalid_argument("displacements require unique IDs and finite values");
        }
    }
    if (displacement.size() != reference.size()) {
        throw std::invalid_argument("every reference packet needs one displacement");
    }
    for (const auto& packet : reference) {
        if (!displacement.contains(packet.id)) {
            throw std::invalid_argument("displacement packet IDs disagree");
        }
    }
    RelationExtensionState result{};
    result.relations = rigidity.relations;
    result.reference_lengths_m = rigidity.lengths_m;
    result.extensions_m.assign(result.relations.size(), 0.0);
    for (std::size_t row = 0; row < rigidity.linearized.matrix.row_count(); ++row) {
        long double value = 0.0L;
        for (std::size_t packet = 0;
             packet < rigidity.linearized.packet_ids.size(); ++packet) {
            const auto entry = displacement.at(
                rigidity.linearized.packet_ids[packet]);
            const std::array components{entry.x, entry.y, entry.z};
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                value += static_cast<long double>(
                    rigidity.linearized.matrix(row, 3U * packet + axis)) *
                    components[axis];
            }
        }
        result.extensions_m[row] = static_cast<double>(value);
    }
    return result;
}

RelationEnergyOperator build_pair_separable_energy(
    std::span<const MechanicalPacket> reference_packets,
    std::span<const PairRelationCoefficient> coefficients) {
    const auto reference = canonical_packets(reference_packets);
    const auto canonical = canonical_entries(
        reference, coefficients,
        [](const auto& entry) { return entry.h_j_per_m2; });
    RelationEnergyOperator result{};
    result.family = EnergyFamily::pair_separable;
    for (const auto& entry : canonical) {
        result.relations.push_back(entry.relation);
    }
    result.reference_lengths_m = reference_lengths(reference, result.relations);
    result.h_j_per_m2 = DenseMatrix(canonical.size(), canonical.size());
    result.factor_sqrt_j_per_m = DenseMatrix(canonical.size(), canonical.size());
    for (std::size_t index = 0; index < canonical.size(); ++index) {
        result.h_j_per_m2(index, index) = canonical[index].h_j_per_m2;
        result.factor_sqrt_j_per_m(index, index) =
            std::sqrt(canonical[index].h_j_per_m2);
        result.locality_radius_m =
            std::max(result.locality_radius_m, result.reference_lengths_m[index]);
    }
    return result;
}

RelationEnergyOperator build_local_collective_energy(
    std::span<const MechanicalPacket> reference_packets,
    std::span<const WeightedRelation> relations,
    const LocalCollectivePolicy& policy) {
    if (!(policy.dilatational_coefficient_j_per_m2 > 0.0) ||
        !std::isfinite(policy.dilatational_coefficient_j_per_m2) ||
        !(policy.deviatoric_coefficient_j_per_m2 > 0.0) ||
        !std::isfinite(policy.deviatoric_coefficient_j_per_m2)) {
        throw std::invalid_argument("collective coefficients must be positive and finite");
    }
    const auto reference = canonical_packets(reference_packets);
    const auto canonical = canonical_entries(
        reference, relations, [](const auto& entry) { return entry.weight; });
    RelationEnergyOperator result{};
    result.family = EnergyFamily::local_incident_collective;
    std::vector<double> weights;
    weights.reserve(canonical.size());
    for (const auto& entry : canonical) {
        result.relations.push_back(entry.relation);
        weights.push_back(entry.weight);
    }
    result.reference_lengths_m = reference_lengths(reference, result.relations);
    const auto relation_count = result.relations.size();
    result.h_j_per_m2 = DenseMatrix(relation_count, relation_count);
    std::vector<std::vector<double>> factor_rows;
    for (const auto length : result.reference_lengths_m) {
        result.locality_radius_m = std::max(result.locality_radius_m, length);
    }

    for (const auto& packet : reference) {
        std::vector<std::size_t> incident;
        for (std::size_t relation_index = 0;
             relation_index < relation_count; ++relation_index) {
            const auto relation = result.relations[relation_index];
            if (relation.first_id == packet.id ||
                relation.second_id == packet.id) {
                incident.push_back(relation_index);
            }
        }
        LocalCollectiveContribution contribution{};
        contribution.packet_id = packet.id;
        contribution.incident_relation_count = incident.size();
        contribution.dilatational_h_j_per_m2 =
            DenseMatrix(relation_count, relation_count);
        contribution.deviatoric_h_j_per_m2 =
            DenseMatrix(relation_count, relation_count);
        contribution.dilatational_factor_sqrt_j_per_m =
            DenseMatrix(incident.empty() ? 0U : 1U, relation_count);
        contribution.deviatoric_factor_sqrt_j_per_m =
            DenseMatrix(incident.size(), relation_count);
        for (const auto index : incident) {
            const auto length = result.reference_lengths_m[index];
            contribution.weighted_length_moment_m2 +=
                weights[index] * length * length;
            contribution.maximum_incident_length_m =
                std::max(contribution.maximum_incident_length_m, length);
        }
        const auto moment = contribution.weighted_length_moment_m2;
        if (!incident.empty() && (!(moment > 0.0) || !std::isfinite(moment))) {
            throw std::overflow_error("local weighted length moment is invalid");
        }
        if (!incident.empty()) {
            std::vector<double> dilation_factor(relation_count, 0.0);
            const auto dilation_scale = std::sqrt(
                policy.dilatational_coefficient_j_per_m2 / moment);
            for (const auto index : incident) {
                dilation_factor[index] = dilation_scale * weights[index] *
                    result.reference_lengths_m[index];
                contribution.dilatational_factor_sqrt_j_per_m(0U, index) =
                    dilation_factor[index];
            }
            factor_rows.push_back(std::move(dilation_factor));
            for (const auto row : incident) {
                const auto a_row = weights[row] *
                    result.reference_lengths_m[row];
                for (const auto column : incident) {
                    const auto a_column = weights[column] *
                        result.reference_lengths_m[column];
                    contribution.dilatational_h_j_per_m2(row, column) +=
                        policy.dilatational_coefficient_j_per_m2 *
                        a_row * a_column / moment;
                }
            }
            // P maps e to e_dev=e-l*(a^T e)/m. Accumulate B*P^T*W*P.
            for (std::size_t residual_index = 0;
                 residual_index < incident.size(); ++residual_index) {
                const auto residual_row = incident[residual_index];
                std::vector<double> deviation_factor(relation_count, 0.0);
                for (const auto row : incident) {
                    const auto p_row = (row == residual_row ? 1.0 : 0.0) -
                        result.reference_lengths_m[residual_row] *
                            weights[row] * result.reference_lengths_m[row] /
                            moment;
                    deviation_factor[row] = std::sqrt(
                        policy.deviatoric_coefficient_j_per_m2 *
                        weights[residual_row]) * p_row;
                    contribution.deviatoric_factor_sqrt_j_per_m(
                        residual_index, row) = deviation_factor[row];
                    for (const auto column : incident) {
                        const auto p_column =
                            (column == residual_row ? 1.0 : 0.0) -
                            result.reference_lengths_m[residual_row] *
                                weights[column] *
                                result.reference_lengths_m[column] / moment;
                        contribution.deviatoric_h_j_per_m2(row, column) +=
                            policy.deviatoric_coefficient_j_per_m2 *
                            weights[residual_row] * p_row * p_column;
                    }
                }
                factor_rows.push_back(std::move(deviation_factor));
            }
        }
        add_matrix(result.h_j_per_m2,
                   contribution.dilatational_h_j_per_m2);
        add_matrix(result.h_j_per_m2,
                   contribution.deviatoric_h_j_per_m2);
        result.local_contributions.push_back(std::move(contribution));
    }
    result.factor_sqrt_j_per_m =
        DenseMatrix(factor_rows.size(), relation_count);
    for (std::size_t row = 0; row < factor_rows.size(); ++row) {
        for (std::size_t column = 0; column < relation_count; ++column) {
            result.factor_sqrt_j_per_m(row, column) =
                factor_rows[row][column];
        }
    }
    for (std::size_t row = 0; row < relation_count; ++row) {
        for (std::size_t column = row + 1U; column < relation_count; ++column) {
            if (result.h_j_per_m2(row, column) != 0.0 &&
                !relations_share_packet(
                    result.relations[row], result.relations[column])) {
                ++result.nonlocal_off_diagonal_count;
            }
        }
    }
    return result;
}

EnergyEvaluation evaluate_energy(
    const RelationEnergyOperator& energy_operator,
    const RelationExtensionState& extensions) {
    validate_extension_compatibility(energy_operator, extensions);
    EnergyEvaluation result{};
    if (energy_operator.family == EnergyFamily::local_incident_collective) {
        result.local.reserve(energy_operator.local_contributions.size());
        long double total_dilatational = 0.0L;
        long double total_deviatoric = 0.0L;
        for (const auto& contribution : energy_operator.local_contributions) {
            const auto dilation = 0.5L * factor_energy_twice(
                contribution.dilatational_factor_sqrt_j_per_m,
                extensions.extensions_m);
            const auto deviation = 0.5L * factor_energy_twice(
                contribution.deviatoric_factor_sqrt_j_per_m,
                extensions.extensions_m);
            LocalEnergyValue local{};
            local.packet_id = contribution.packet_id;
            local.dilatational_j = static_cast<double>(dilation);
            local.deviatoric_j = static_cast<double>(deviation);
            local.total_j = local.dilatational_j + local.deviatoric_j;
            result.local.push_back(local);
            total_dilatational += dilation;
            total_deviatoric += deviation;
        }
        result.dilatational_j = static_cast<double>(total_dilatational);
        result.deviatoric_j = static_cast<double>(total_deviatoric);
        result.total_j = result.dilatational_j + result.deviatoric_j;
    } else {
        if (energy_operator.factor_sqrt_j_per_m.column_count() ==
            extensions.extensions_m.size()) {
            result.total_j = static_cast<double>(
                0.5L * factor_energy_twice(
                    energy_operator.factor_sqrt_j_per_m,
                    extensions.extensions_m));
        } else {
            result.total_j = static_cast<double>(
                0.5L * quadratic_form(
                    energy_operator.h_j_per_m2, extensions.extensions_m));
        }
    }
    result.finite = std::isfinite(result.total_j) &&
        std::isfinite(result.dilatational_j) &&
        std::isfinite(result.deviatoric_j) && result.total_j >= 0.0 &&
        result.dilatational_j >= 0.0 && result.deviatoric_j >= 0.0;
    return result;
}

EnergyEvaluation evaluate_finite_energy(
    const RelationEnergyOperator& energy_operator,
    std::span<const MechanicalPacket> reference_packets,
    std::span<const MechanicalPacket> current_packets) {
    return evaluate_energy(
        energy_operator,
        evaluate_finite_relation_extensions(
            reference_packets, current_packets, energy_operator.relations));
}

DenseMatrix assemble_packet_energy_hessian(
    const observation::BondOperator& rigidity,
    const RelationEnergyOperator& energy_operator) {
    if (rigidity.relations != energy_operator.relations ||
        rigidity.linearized.matrix.row_count() !=
            energy_operator.h_j_per_m2.row_count() ||
        energy_operator.h_j_per_m2.row_count() !=
            energy_operator.h_j_per_m2.column_count()) {
        throw std::invalid_argument("rigidity and constitutive operator disagree");
    }
    const auto relation_count = rigidity.linearized.matrix.row_count();
    const auto coordinate_count = rigidity.linearized.matrix.column_count();
    DenseMatrix h_times_r(relation_count, coordinate_count);
    for (std::size_t row = 0; row < relation_count; ++row) {
        for (std::size_t column = 0; column < coordinate_count; ++column) {
            long double value = 0.0L;
            for (std::size_t inner = 0; inner < relation_count; ++inner) {
                value += static_cast<long double>(
                    energy_operator.h_j_per_m2(row, inner)) *
                    rigidity.linearized.matrix(inner, column);
            }
            h_times_r(row, column) = static_cast<double>(value);
        }
    }
    DenseMatrix result(coordinate_count, coordinate_count);
    for (std::size_t row = 0; row < coordinate_count; ++row) {
        for (std::size_t column = 0; column < coordinate_count; ++column) {
            long double value = 0.0L;
            for (std::size_t relation = 0; relation < relation_count;
                 ++relation) {
                value += static_cast<long double>(
                    rigidity.linearized.matrix(relation, row)) *
                    h_times_r(relation, column);
            }
            result(row, column) = static_cast<double>(value);
        }
    }
    return result;
}

observation::LinearizedOperator assemble_energy_factor_times_rigidity(
    const observation::BondOperator& rigidity,
    const RelationEnergyOperator& energy_operator) {
    if (rigidity.relations != energy_operator.relations ||
        energy_operator.factor_sqrt_j_per_m.column_count() !=
            rigidity.linearized.matrix.row_count()) {
        throw std::invalid_argument("rigidity and energy factor disagree");
    }
    observation::LinearizedOperator result{};
    result.kind = observation::ObservableKind::central_bond_length_rate;
    result.packet_ids = rigidity.linearized.packet_ids;
    result.matrix = DenseMatrix(
        energy_operator.factor_sqrt_j_per_m.row_count(),
        rigidity.linearized.matrix.column_count());
    for (std::size_t row = 0; row < result.matrix.row_count(); ++row) {
        for (std::size_t column = 0; column < result.matrix.column_count();
             ++column) {
            long double value = 0.0L;
            for (std::size_t relation = 0;
                 relation < rigidity.linearized.matrix.row_count(); ++relation) {
                value += static_cast<long double>(
                    energy_operator.factor_sqrt_j_per_m(row, relation)) *
                    rigidity.linearized.matrix(relation, column);
            }
            result.matrix(row, column) = static_cast<double>(value);
        }
    }
    return result;
}

double maximum_symmetry_residual(const DenseMatrix& matrix) noexcept {
    if (matrix.row_count() != matrix.column_count()) {
        return std::numeric_limits<double>::infinity();
    }
    double result = 0.0;
    for (std::size_t row = 0; row < matrix.row_count(); ++row) {
        for (std::size_t column = row + 1U; column < matrix.column_count();
             ++column) {
            result = std::max(
                result, std::abs(matrix(row, column) - matrix(column, row)));
        }
    }
    return result;
}

} // namespace mls::experimental::constitutive_expressivity
