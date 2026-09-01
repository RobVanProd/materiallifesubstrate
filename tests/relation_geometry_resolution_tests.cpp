#include "test_harness.hpp"

#include "mls/relation_geometry_resolution_lab.hpp"

#include <array>
#include <algorithm>
#include <cmath>
#include <map>
#include <limits>
#include <span>
#include <vector>

namespace {

namespace geometry = mls::experimental::relation_geometry_resolution;
namespace constitutive = mls::experimental::constitutive_expressivity;
namespace force = mls::experimental::conservative_force_consistency;
namespace observation = mls::experimental::mechanical_observability;
using mls::experimental::Vec3d;
using mls::experimental::Matrix3d;
using observation::BondRelation;
using observation::MechanicalPacket;

[[nodiscard]] geometry::RelationGeometryInput octahedron_relation() {
    return {
        .reference_first_m = {1.0, 0.0, 0.0},
        .reference_second_m = {0.0, 1.0, 0.0},
        .current_first_m = {1.0, 0.0, 0.0},
        .current_second_m = {0.0, 1.0, 0.0},
        .frozen_reference_length_m = std::sqrt(2.0),
    };
}

[[nodiscard]] bool close(double lhs, double rhs, double tolerance) {
    return std::abs(lhs - rhs) <= tolerance;
}

[[nodiscard]] std::vector<observation::MechanicalPacket> pair_packets() {
    return {{1, 1, {1.0, 0.0, 0.0}, {}},
            {2, 1, {0.0, 1.0, 0.0}, {}}};
}

[[nodiscard]] force::FrozenForceOperator pair_operator(
    const std::vector<observation::MechanicalPacket>& reference) {
    const std::array coefficients{
        constitutive::PairRelationCoefficient{{1, 2}, 2.0}};
    return force::freeze_symmetric_force_operator(
        constitutive::build_pair_separable_energy(reference, coefficients));
}

[[nodiscard]] std::vector<MechanicalPacket> tetrahedron() {
    return {{1, 1, {0.0, 0.0, 0.0}, {}},
            {2, 1, {1.0, 0.0, 0.0}, {}},
            {3, 1, {0.0, 1.0, 0.0}, {}},
            {4, 1, {0.0, 0.0, 1.0}, {}}};
}

[[nodiscard]] std::vector<BondRelation> k4() {
    return {{1, 2}, {1, 3}, {1, 4}, {2, 3}, {2, 4}, {3, 4}};
}

[[nodiscard]] std::vector<constitutive::WeightedRelation> weighted(
    std::span<const BondRelation> relations) {
    std::vector<constitutive::WeightedRelation> result;
    for (const auto relation : relations) {
        result.push_back({relation, 1.0});
    }
    return result;
}

[[nodiscard]] force::FrozenForceOperator collective_model(
    std::span<const MechanicalPacket> reference,
    std::span<const BondRelation> relations, double ratio = 2.0) {
    return force::freeze_symmetric_force_operator(
        constitutive::build_local_collective_energy(
            reference, weighted(relations),
            {.dilatational_coefficient_j_per_m2 = 3.0 * ratio / 20.0,
             .deviatoric_coefficient_j_per_m2 = 0.25}));
}

[[nodiscard]] Matrix3d deformation() {
    Matrix3d result{};
    result.value = {{{21.0 / 20.0, 1.0 / 20.0, -1.0 / 40.0},
                     {0.0, 19.0 / 20.0, 1.0 / 25.0},
                     {1.0 / 50.0, 0.0, 11.0 / 10.0}}};
    return result;
}

[[nodiscard]] Matrix3d rotation() {
    Matrix3d result{};
    result.value = {{{1.0 / 9.0, 8.0 / 9.0, 4.0 / 9.0},
                     {8.0 / 9.0, 1.0 / 9.0, -4.0 / 9.0},
                     {-4.0 / 9.0, 4.0 / 9.0, -7.0 / 9.0}}};
    return result;
}

[[nodiscard]] std::vector<MechanicalPacket> transformed(
    std::span<const MechanicalPacket> packets, const Matrix3d& map,
    Vec3d translation = {}) {
    std::vector<MechanicalPacket> result(packets.begin(), packets.end());
    for (auto& packet : result) {
        packet.position_m =
            mls::experimental::multiply(map, packet.position_m) + translation;
        packet.velocity_m_per_s =
            mls::experimental::multiply(map, packet.velocity_m_per_s);
    }
    return result;
}

[[nodiscard]] double magnitude(Vec3d value) {
    return std::sqrt(mls::experimental::dot(value, value));
}

[[nodiscard]] bool close(Vec3d lhs, Vec3d rhs, double tolerance) {
    return magnitude(lhs - rhs) <= tolerance;
}

[[nodiscard]] std::vector<double> flattened(
    const geometry::ResolvedForceEvaluation& evaluated) {
    std::vector<double> result;
    for (const auto& packet : evaluated.packet_forces) {
        result.push_back(packet.force_n.x);
        result.push_back(packet.force_n.y);
        result.push_back(packet.force_n.z);
    }
    return result;
}

[[nodiscard]] std::vector<MechanicalPacket> displaced(
    std::span<const MechanicalPacket> packets, std::size_t coordinate,
    double amount) {
    auto result = std::vector<MechanicalPacket>(packets.begin(), packets.end());
    auto& position = result[coordinate / 3U].position_m;
    if (coordinate % 3U == 0U) {
        position.x += amount;
    } else if (coordinate % 3U == 1U) {
        position.y += amount;
    } else {
        position.z += amount;
    }
    return result;
}

} // namespace

MLS_TEST("relation geometry path A reproduces octahedron adjacency loss") {
    auto input = octahedron_relation();
    input.current_second_m.x = std::nextafter(
        0.0, -std::numeric_limits<double>::infinity());
    const auto evaluated = geometry::evaluate_relation_geometry(
        input, geometry::GeometryPath::frozen_binary64);
    MLS_REQUIRE_EQ(evaluated.status, geometry::GeometryStatus::evaluated);
    MLS_REQUIRE_EQ(evaluated.extension_m, 0.0);
    MLS_REQUIRE_EQ(
        evaluated.exact_length_order, geometry::LengthOrder::equal);
}

MLS_TEST("cancellation resistant path preserves subnormal extension sign") {
    const auto minimum = std::numeric_limits<double>::denorm_min();
    auto longer = octahedron_relation();
    longer.current_second_m.x = -minimum;
    const auto longer_evaluated = geometry::evaluate_relation_geometry(
        longer, geometry::GeometryPath::cancellation_resistant_binary64);
    MLS_REQUIRE_EQ(
        longer_evaluated.status, geometry::GeometryStatus::evaluated);
    MLS_REQUIRE(longer_evaluated.extension_m > 0.0);
    MLS_REQUIRE_EQ(
        longer_evaluated.exact_length_order, geometry::LengthOrder::longer);

    auto shorter = octahedron_relation();
    shorter.current_second_m.x = minimum;
    const auto shorter_evaluated = geometry::evaluate_relation_geometry(
        shorter, geometry::GeometryPath::cancellation_resistant_binary64);
    MLS_REQUIRE(shorter_evaluated.extension_m < 0.0);
    MLS_REQUIRE_EQ(
        shorter_evaluated.exact_length_order, geometry::LengthOrder::shorter);
}

MLS_TEST("transient geometry preserves endpoint subtraction low words") {
    const auto minimum = std::numeric_limits<double>::denorm_min();
    auto input = octahedron_relation();
    input.current_second_m.x = -minimum;
    const auto evaluated = geometry::evaluate_relation_geometry(
        input, geometry::GeometryPath::transient_double_double);
    MLS_REQUIRE_EQ(evaluated.status, geometry::GeometryStatus::evaluated);
    MLS_REQUIRE(evaluated.extension_m > 0.0 ||
                evaluated.extension_low_m > 0.0);
    MLS_REQUIRE_EQ(
        evaluated.exact_length_order, geometry::LengthOrder::longer);
    MLS_REQUIRE(evaluated.current_offset_low_m.x != 0.0);
}

MLS_TEST("relation geometry endpoint reversal is orientation covariant") {
    auto input = octahedron_relation();
    input.current_second_m.x = -4.0 *
        std::numeric_limits<double>::denorm_min();
    for (const auto path :
         std::array{geometry::GeometryPath::frozen_binary64,
                    geometry::GeometryPath::cancellation_resistant_binary64,
                    geometry::GeometryPath::transient_double_double}) {
        const auto forward = geometry::evaluate_relation_geometry(input, path);
        auto reversed = input;
        std::swap(reversed.reference_first_m, reversed.reference_second_m);
        std::swap(reversed.current_first_m, reversed.current_second_m);
        const auto backward =
            geometry::evaluate_relation_geometry(reversed, path);
        MLS_REQUIRE_EQ(forward.status, backward.status);
        MLS_REQUIRE_EQ(forward.exact_length_order, backward.exact_length_order);
        MLS_REQUIRE_EQ(forward.extension_m, backward.extension_m);
        MLS_REQUIRE(close(
            forward.direction_first_to_second.x,
            -backward.direction_first_to_second.x, 2.0e-15));
        MLS_REQUIRE(close(
            forward.direction_first_to_second.y,
            -backward.direction_first_to_second.y, 2.0e-15));
        MLS_REQUIRE(close(
            forward.direction_first_to_second.z,
            -backward.direction_first_to_second.z, 2.0e-15));
    }
}

MLS_TEST("relation geometry exact coincidence fails closed") {
    auto input = octahedron_relation();
    input.current_second_m = input.current_first_m;
    for (const auto path :
         std::array{geometry::GeometryPath::frozen_binary64,
                    geometry::GeometryPath::cancellation_resistant_binary64,
                    geometry::GeometryPath::transient_double_double}) {
        const auto evaluated = geometry::evaluate_relation_geometry(input, path);
        MLS_REQUIRE_EQ(
            evaluated.status, geometry::GeometryStatus::coincident_relation);
        MLS_REQUIRE(evaluated.coordinate_coincident);
        MLS_REQUIRE_EQ(evaluated.current_length_m, 0.0);
        MLS_REQUIRE_EQ(evaluated.extension_m, 0.0);
        MLS_REQUIRE_EQ(evaluated.direction_first_to_second, Vec3d{});
    }
}

MLS_TEST("resolved Path A force is the accepted force on ordinary geometry") {
    const auto reference = pair_packets();
    const auto model = pair_operator(reference);
    auto current = reference;
    current[1].position_m = {0.25, 1.125, -0.5};
    const auto accepted = force::evaluate_spatial_force(model, current);
    const auto resolved = geometry::evaluate_resolved_spatial_force(
        model, reference, current, geometry::GeometryPath::frozen_binary64);
    MLS_REQUIRE_EQ(resolved.status, geometry::ResolvedForceStatus::evaluated);
    MLS_REQUIRE_EQ(resolved.energy_j, accepted.energy_j);
    MLS_REQUIRE_EQ(resolved.packet_forces, accepted.packet_forces);
    MLS_REQUIRE_EQ(
        resolved.current_rigidity.matrix, accepted.current_rigidity.matrix);

    const auto accepted_tangent = force::evaluate_spatial_tangent(model, current);
    const auto resolved_tangent = geometry::evaluate_resolved_spatial_tangent(
        model, reference, current, geometry::GeometryPath::frozen_binary64);
    MLS_REQUIRE_EQ(
        resolved_tangent.status, geometry::ResolvedForceStatus::evaluated);
    MLS_REQUIRE_EQ(
        resolved_tangent.material_energy_hessian_n_per_m,
        accepted_tangent.material_energy_hessian_n_per_m);
    MLS_REQUIRE_EQ(
        resolved_tangent.geometric_energy_hessian_n_per_m,
        accepted_tangent.geometric_energy_hessian_n_per_m);
    MLS_REQUIRE_EQ(
        resolved_tangent.total_energy_hessian_n_per_m,
        accepted_tangent.total_energy_hessian_n_per_m);
}

MLS_TEST("resolved force paths fail closed without partial output") {
    const auto reference = pair_packets();
    const auto model = pair_operator(reference);
    auto current = reference;
    current[1].position_m = current[0].position_m;
    for (const auto path :
         std::array{geometry::GeometryPath::frozen_binary64,
                    geometry::GeometryPath::cancellation_resistant_binary64,
                    geometry::GeometryPath::transient_double_double}) {
        const auto evaluated = geometry::evaluate_resolved_spatial_force(
            model, reference, current, path);
        MLS_REQUIRE_EQ(
            evaluated.status, geometry::ResolvedForceStatus::coincident_relation);
        MLS_REQUIRE(std::isnan(evaluated.energy_j));
        MLS_REQUIRE(evaluated.packet_forces.empty());
        MLS_REQUIRE(evaluated.relation_coordinates.empty());
        const auto tangent = geometry::evaluate_resolved_spatial_tangent(
            model, reference, current, path);
        MLS_REQUIRE_EQ(
            tangent.status, geometry::ResolvedForceStatus::coincident_relation);
        MLS_REQUIRE_EQ(
            tangent.total_energy_hessian_n_per_m.row_count(), std::size_t{0});
    }
}

MLS_TEST("selectable geometry paths preserve conservative identities") {
    const auto reference = tetrahedron();
    const auto relations = k4();
    const auto model = collective_model(reference, relations);
    auto current = transformed(reference, deformation());
    for (std::size_t index = 0; index < current.size(); ++index) {
        const auto factor = static_cast<double>(index + 1U);
        current[index].velocity_m_per_s =
            {factor / 7.0, -factor / 11.0, factor / 13.0};
    }
    for (const auto path :
         std::array{geometry::GeometryPath::cancellation_resistant_binary64,
                    geometry::GeometryPath::transient_double_double}) {
        const auto evaluated = geometry::evaluate_resolved_spatial_force(
            model, reference, current, path);
        MLS_REQUIRE_EQ(
            evaluated.status, geometry::ResolvedForceStatus::evaluated);
        Vec3d total{};
        Vec3d torque_origin{};
        Vec3d torque_shifted{};
        const Vec3d origin{7.0 / 13.0, -5.0 / 11.0, 3.0 / 17.0};
        double power = 0.0;
        for (std::size_t index = 0; index < current.size(); ++index) {
            const auto force_value = evaluated.packet_forces[index].force_n;
            total += force_value;
            torque_origin += mls::experimental::cross(
                current[index].position_m, force_value);
            torque_shifted += mls::experimental::cross(
                current[index].position_m - origin, force_value);
            power += mls::experimental::dot(
                force_value, current[index].velocity_m_per_s);
        }
        double relation_rate = 0.0;
        std::map<std::uint64_t, std::size_t> lookup;
        for (std::size_t index = 0; index < current.size(); ++index) {
            lookup.emplace(current[index].id, index);
        }
        for (const auto& coordinate : evaluated.relation_coordinates) {
            const auto first = lookup.at(coordinate.relation.first_id);
            const auto second = lookup.at(coordinate.relation.second_id);
            relation_rate += coordinate.conjugate_force_n *
                mls::experimental::dot(
                    coordinate.geometry.direction_first_to_second,
                    current[second].velocity_m_per_s -
                        current[first].velocity_m_per_s);
        }
        MLS_REQUIRE(magnitude(total) < 3.0e-16);
        MLS_REQUIRE(magnitude(torque_origin) < 5.0e-16);
        MLS_REQUIRE(magnitude(torque_shifted) < 7.0e-16);
        MLS_REQUIRE(std::abs(power + relation_rate) < 4.0e-16);

        constexpr double step = 1.0e-6;
        const auto analytic = flattened(evaluated);
        for (std::size_t coordinate = 0; coordinate < analytic.size();
             ++coordinate) {
            const auto plus = geometry::evaluate_resolved_spatial_force(
                model, reference, displaced(current, coordinate, step), path);
            const auto minus = geometry::evaluate_resolved_spatial_force(
                model, reference, displaced(current, coordinate, -step), path);
            const auto derivative = (plus.energy_j - minus.energy_j) /
                (2.0 * step);
            MLS_REQUIRE(close(derivative, -analytic[coordinate], 3.0e-10));
        }
        const auto tangent = geometry::evaluate_resolved_spatial_tangent(
            model, reference, current, path);
        MLS_REQUIRE(
            force::maximum_asymmetry(
                tangent.total_energy_hessian_n_per_m) < 4.0e-16);
    }
}

MLS_TEST("selected geometry is covariant and label order independent") {
    const auto reference = tetrahedron();
    const auto relations = k4();
    const auto model = collective_model(reference, relations);
    const auto current = transformed(reference, deformation());
    constexpr auto path =
        geometry::GeometryPath::cancellation_resistant_binary64;
    const auto baseline = geometry::evaluate_resolved_spatial_force(
        model, reference, current, path);
    const auto proper_rotation = rotation();
    const auto rotated_reference = transformed(reference, proper_rotation);
    const auto rotated_current = transformed(
        current, proper_rotation,
        {7.0 / 13.0, -5.0 / 11.0, 3.0 / 17.0});
    const auto rotated = geometry::evaluate_resolved_spatial_force(
        model, rotated_reference, rotated_current, path);
    MLS_REQUIRE(close(rotated.energy_j, baseline.energy_j, 2.0e-15));
    for (std::size_t index = 0; index < baseline.packet_forces.size(); ++index) {
        MLS_REQUIRE(close(
            rotated.packet_forces[index].force_n,
            mls::experimental::multiply(
                proper_rotation, baseline.packet_forces[index].force_n),
            8.0e-15));
    }

    constexpr double scale = 2.0;
    const auto scaled_reference = transformed(
        reference, scale * Matrix3d::identity());
    const auto scaled_current = transformed(
        current, scale * Matrix3d::identity());
    const auto scaled_model = collective_model(scaled_reference, relations);
    const auto scaled = geometry::evaluate_resolved_spatial_force(
        scaled_model, scaled_reference, scaled_current, path);
    MLS_REQUIRE(close(
        scaled.energy_j, scale * scale * baseline.energy_j, 3.0e-15));
    for (std::size_t index = 0; index < baseline.packet_forces.size(); ++index) {
        MLS_REQUIRE(close(
            scaled.packet_forces[index].force_n,
            scale * baseline.packet_forces[index].force_n, 8.0e-15));
    }

    auto packet_permuted_reference = reference;
    auto packet_permuted_current = current;
    std::ranges::reverse(packet_permuted_reference);
    std::ranges::reverse(packet_permuted_current);
    const auto packet_permuted = geometry::evaluate_resolved_spatial_force(
        model, packet_permuted_reference, packet_permuted_current, path);
    MLS_REQUIRE_EQ(packet_permuted.packet_forces, baseline.packet_forces);

    std::vector<std::size_t> reverse_coordinates(relations.size());
    for (std::size_t index = 0; index < relations.size(); ++index) {
        reverse_coordinates[index] = relations.size() - 1U - index;
    }
    auto relation_permuted = force::permute_relation_coordinates(
        model, reverse_coordinates);
    for (auto& relation : relation_permuted.parent_operator.relations) {
        std::swap(relation.first_id, relation.second_id);
    }
    for (auto& relation : relation_permuted.force_operator.relations) {
        std::swap(relation.first_id, relation.second_id);
    }
    const auto relation_result = geometry::evaluate_resolved_spatial_force(
        relation_permuted, reference, current, path);
    for (std::size_t index = 0; index < baseline.packet_forces.size(); ++index) {
        MLS_REQUIRE(close(
            relation_result.packet_forces[index].force_n,
            baseline.packet_forces[index].force_n, 3.0e-15));
    }

    const std::map<std::uint64_t, std::uint64_t> rename{
        {1, 40}, {2, 10}, {3, 30}, {4, 20}};
    auto renamed_reference = reference;
    auto renamed_current = current;
    auto renamed_relations = relations;
    for (auto& packet : renamed_reference) {
        packet.id = rename.at(packet.id);
    }
    for (auto& packet : renamed_current) {
        packet.id = rename.at(packet.id);
    }
    for (auto& relation : renamed_relations) {
        relation.first_id = rename.at(relation.first_id);
        relation.second_id = rename.at(relation.second_id);
    }
    const auto renamed_model = collective_model(
        renamed_reference, renamed_relations);
    const auto renamed = geometry::evaluate_resolved_spatial_force(
        renamed_model, renamed_reference, renamed_current, path);
    std::map<std::uint64_t, Vec3d> semantic;
    for (const auto& packet : renamed.packet_forces) {
        const auto original = std::ranges::find_if(
            rename, [&](const auto& entry) {
                return entry.second == packet.packet_id;
            });
        semantic.emplace(original->first, packet.force_n);
    }
    for (const auto& packet : baseline.packet_forces) {
        MLS_REQUIRE(close(
            semantic.at(packet.packet_id), packet.force_n, 3.0e-15));
    }
}
