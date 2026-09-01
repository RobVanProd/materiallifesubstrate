#include "test_harness.hpp"

#include "mls/relation_geometry_resolution_lab.hpp"

#include <array>
#include <cmath>
#include <limits>

namespace {

namespace geometry = mls::experimental::relation_geometry_resolution;
namespace constitutive = mls::experimental::constitutive_expressivity;
namespace force = mls::experimental::conservative_force_consistency;
namespace observation = mls::experimental::mechanical_observability;
using mls::experimental::Vec3d;

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
