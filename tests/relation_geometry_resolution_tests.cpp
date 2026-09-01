#include "test_harness.hpp"

#include "mls/relation_geometry_resolution_lab.hpp"

#include <array>
#include <cmath>
#include <limits>

namespace {

namespace geometry = mls::experimental::relation_geometry_resolution;
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

