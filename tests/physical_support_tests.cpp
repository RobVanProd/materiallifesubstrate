#include "mls/physical_support.hpp"
#include "mls/world.hpp"

#include "test_harness.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <utility>
#include <vector>

namespace {

[[nodiscard]] mls::Position3 point(
    mls::Scalar x, mls::Scalar y = 0, mls::Scalar z = 0) {
    return {
        mls::Length::from_raw(x),
        mls::Length::from_raw(y),
        mls::Length::from_raw(z)};
}

struct SupportFixture final {
    mls::CompoundId atom{};
    mls::World world;
};

[[nodiscard]] SupportFixture make_support_world(
    const mls::Scalar voxel_edge = 100, const mls::Scalar radius = 10) {
    const mls::ElementId element{0};
    mls::ElementCatalog elements;
    elements.define(
        element,
        mls::ElementProperties{
            mls::Mass::from_raw(10),
            mls::HeatCapacity::from_raw(1),
            mls::Energy::from_raw(10)});
    mls::CompoundRegistry compounds;
    const auto atom = compounds.intern(
        mls::CompoundGraph(std::vector<mls::ElementId>{element}, {}));
    auto config = mls::WorldConfig{};
    config.voxel_edge = mls::Length::from_raw(voxel_edge);
    config.interaction_radius = mls::Length::from_raw(radius);
    return {atom, mls::World(std::move(elements), std::move(compounds), config)};
}

[[nodiscard]] mls::MaterialSeed support_seed(
    const SupportFixture& fixture, const mls::Position3 position) {
    return {
        .position = position,
        .momentum = {},
        .composition = mls::CompoundMixture{{fixture.atom, 1}},
        .stored_energy = mls::Energy::from_raw(100),
        .thermal_energy = mls::Energy::from_raw(100),
    };
}

} // namespace

MLS_TEST("hardening/support/spherical_face_edge_corner_cases_are_exact") {
    const auto origin = point(0, 0, 0);
    const auto radius = mls::Length::from_raw(10);
    MLS_REQUIRE(mls::within_spherical_support(origin, point(10, 0, 0), radius));
    MLS_REQUIRE(mls::within_spherical_support(origin, point(6, 8, 0), radius));
    MLS_REQUIRE(mls::within_spherical_support(origin, point(6, 6, 5), radius));
    MLS_REQUIRE(!mls::within_spherical_support(origin, point(6, 8, 1), radius));
    MLS_REQUIRE(!mls::within_spherical_support(origin, point(10, 1, 0), radius));
}

MLS_TEST("hardening/support/voxel_membership_neither_authorizes_nor_rejects_interaction") {
    auto same_voxel = make_support_world();
    const auto same_first = same_voxel.world.introduce_material_from_boundary(
        support_seed(same_voxel, point(1, 1, 1)));
    const auto same_second = same_voxel.world.introduce_material_from_boundary(
        support_seed(same_voxel, point(10, 10, 10)));
    MLS_REQUIRE_EQ(
        same_voxel.world.grid().coordinate_for(point(1, 1, 1)),
        same_voxel.world.grid().coordinate_for(point(10, 10, 10)));
    MLS_REQUIRE_THROWS(
        std::domain_error,
        same_voxel.world.transfer_heat(
            same_first, same_second, mls::Energy::from_raw(1)));

    auto across_face = make_support_world();
    const auto face_first = across_face.world.introduce_material_from_boundary(
        support_seed(across_face, point(99, 20, 20)));
    const auto face_second = across_face.world.introduce_material_from_boundary(
        support_seed(across_face, point(101, 20, 20)));
    MLS_REQUIRE(
        across_face.world.grid().coordinate_for(point(99, 20, 20)) !=
        across_face.world.grid().coordinate_for(point(101, 20, 20)));
    across_face.world.transfer_heat(face_first, face_second, mls::Energy::from_raw(1));
    MLS_REQUIRE(across_face.world.audit().ok());

    auto across_edge = make_support_world();
    const auto edge_first_position = point(99, 99, 20);
    const auto edge_second_position = point(101, 101, 20);
    const auto edge_first = across_edge.world.introduce_material_from_boundary(
        support_seed(across_edge, edge_first_position));
    const auto edge_second = across_edge.world.introduce_material_from_boundary(
        support_seed(across_edge, edge_second_position));
    const auto edge_first_cell = across_edge.world.grid().coordinate_for(edge_first_position);
    const auto edge_second_cell = across_edge.world.grid().coordinate_for(edge_second_position);
    MLS_REQUIRE(edge_first_cell.x != edge_second_cell.x);
    MLS_REQUIRE(edge_first_cell.y != edge_second_cell.y);
    MLS_REQUIRE_EQ(edge_first_cell.z, edge_second_cell.z);
    across_edge.world.transfer_heat(edge_first, edge_second, mls::Energy::from_raw(1));
    MLS_REQUIRE(across_edge.world.audit().ok());

    auto across_corner = make_support_world();
    const auto corner_first_position = point(99, 99, 99);
    const auto corner_second_position = point(101, 101, 101);
    const auto corner_first = across_corner.world.introduce_material_from_boundary(
        support_seed(across_corner, corner_first_position));
    const auto corner_second = across_corner.world.introduce_material_from_boundary(
        support_seed(across_corner, corner_second_position));
    const auto corner_first_cell =
        across_corner.world.grid().coordinate_for(corner_first_position);
    const auto corner_second_cell =
        across_corner.world.grid().coordinate_for(corner_second_position);
    MLS_REQUIRE(corner_first_cell.x != corner_second_cell.x);
    MLS_REQUIRE(corner_first_cell.y != corner_second_cell.y);
    MLS_REQUIRE(corner_first_cell.z != corner_second_cell.z);
    across_corner.world.transfer_heat(
        corner_first, corner_second, mls::Energy::from_raw(1));
    MLS_REQUIRE(across_corner.world.audit().ok());

    auto distant_corner = make_support_world();
    const auto distant_first = distant_corner.world.introduce_material_from_boundary(
        support_seed(distant_corner, point(95, 95, 95)));
    const auto distant_second = distant_corner.world.introduce_material_from_boundary(
        support_seed(distant_corner, point(105, 105, 105)));
    MLS_REQUIRE_THROWS(
        std::domain_error,
        distant_corner.world.transfer_heat(
            distant_first, distant_second, mls::Energy::from_raw(1)));
}

MLS_TEST("hardening/support/eligibility_is_invariant_across_fractional_voxel_phases") {
    constexpr std::array<mls::Scalar, 3> separation{6, 6, 5};
    bool observed_same_cell = false;
    bool observed_different_cells = false;
    for (mls::Scalar phase = -199; phase <= 199; ++phase) {
        auto fixture = make_support_world(100, 10);
        const auto first_position = point(phase, phase * 3, -phase * 2);
        const auto second_position = point(
            phase + separation[0],
            phase * 3 + separation[1],
            -phase * 2 + separation[2]);
        MLS_REQUIRE(mls::within_spherical_support(
            first_position, second_position, fixture.world.config().interaction_radius));

        const auto first_cell = fixture.world.grid().coordinate_for(first_position);
        const auto second_cell = fixture.world.grid().coordinate_for(second_position);
        observed_same_cell = observed_same_cell || first_cell == second_cell;
        observed_different_cells = observed_different_cells || first_cell != second_cell;

        const auto first = fixture.world.introduce_material_from_boundary(
            support_seed(fixture, first_position));
        const auto second = fixture.world.introduce_material_from_boundary(
            support_seed(fixture, second_position));
        fixture.world.transfer_heat(first, second, mls::Energy::from_raw(1));
        MLS_REQUIRE(fixture.world.audit().ok());
    }
    MLS_REQUIRE(observed_same_cell);
    MLS_REQUIRE(observed_different_cells);
}

MLS_TEST("hardening/support/eligibility_is_invariant_under_exact_axis_rotations") {
    const auto radius = mls::Length::from_raw(10);
    std::array<mls::Scalar, 3> inside{5, 6, 6};
    do {
        for (const mls::Scalar sign_x : {-1, 1}) {
            for (const mls::Scalar sign_y : {-1, 1}) {
                for (const mls::Scalar sign_z : {-1, 1}) {
                    MLS_REQUIRE(mls::within_spherical_support(
                        point(37, -81, 109),
                        point(
                            37 + sign_x * inside[0],
                            -81 + sign_y * inside[1],
                            109 + sign_z * inside[2]),
                        radius));
                    auto fixture = make_support_world(100, 10);
                    const auto first_position = point(97, 97, 97);
                    const auto second_position = point(
                        97 + sign_x * inside[0],
                        97 + sign_y * inside[1],
                        97 + sign_z * inside[2]);
                    const auto first = fixture.world.introduce_material_from_boundary(
                        support_seed(fixture, first_position));
                    const auto second = fixture.world.introduce_material_from_boundary(
                        support_seed(fixture, second_position));
                    fixture.world.transfer_heat(first, second, mls::Energy::from_raw(1));
                    MLS_REQUIRE(fixture.world.audit().ok());
                }
            }
        }
    } while (std::next_permutation(inside.begin(), inside.end()));

    std::array<mls::Scalar, 3> outside{1, 6, 8};
    do {
        for (const mls::Scalar sign_x : {-1, 1}) {
            for (const mls::Scalar sign_y : {-1, 1}) {
                for (const mls::Scalar sign_z : {-1, 1}) {
                    MLS_REQUIRE(!mls::within_spherical_support(
                        point(-37, 81, -109),
                        point(
                            -37 + sign_x * outside[0],
                            81 + sign_y * outside[1],
                            -109 + sign_z * outside[2]),
                        radius));
                }
            }
        }
    } while (std::next_permutation(outside.begin(), outside.end()));
}

MLS_TEST("hardening/support/squared_distance_comparison_handles_extreme_coordinates") {
    constexpr auto minimum = std::numeric_limits<mls::Scalar>::min();
    constexpr auto maximum = std::numeric_limits<mls::Scalar>::max();
    const auto maximum_radius = mls::Length::from_raw(maximum);

    MLS_REQUIRE(!mls::within_spherical_support(
        point(minimum, 0, 0), point(maximum, 0, 0), maximum_radius));
    MLS_REQUIRE(mls::within_spherical_support(
        point(minimum, 0, 0), point(-1, 0, 0), maximum_radius));
    MLS_REQUIRE(!mls::within_spherical_support(
        point(0, 0, 0), point(maximum, maximum, maximum), maximum_radius));
    constexpr mls::Scalar limb_boundary = INT64_C(4294967296);
    MLS_REQUIRE(mls::within_spherical_support(
        point(0),
        point(limb_boundary - 1, 1, 0),
        mls::Length::from_raw(limb_boundary)));
    MLS_REQUIRE(!mls::within_spherical_support(
        point(0),
        point(limb_boundary, 1, 0),
        mls::Length::from_raw(limb_boundary)));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        mls::within_spherical_support(point(0), point(0), mls::Length{}));
}
