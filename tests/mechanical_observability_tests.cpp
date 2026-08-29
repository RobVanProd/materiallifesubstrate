#include "test_harness.hpp"

#include "mls/mechanical_observability_lab.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <tuple>
#include <vector>

namespace {

namespace observation = mls::experimental::mechanical_observability;
using mls::experimental::Matrix3d;
using mls::experimental::Vec3d;
using observation::BondRelation;
using observation::MechanicalPacket;
using observation::VolumeRelation;

[[nodiscard]] std::vector<MechanicalPacket> tetrahedron() {
    return {
        {1, 1, {0.0, 0.0, 0.0}, {}},
        {2, 1, {1.0, 0.0, 0.0}, {}},
        {3, 1, {0.0, 1.0, 0.0}, {}},
        {4, 1, {0.0, 0.0, 1.0}, {}},
    };
}

[[nodiscard]] std::vector<BondRelation> tetrahedron_bonds() {
    return {{1, 2}, {1, 3}, {1, 4}, {2, 3}, {2, 4}, {3, 4}};
}

[[nodiscard]] std::vector<MechanicalPacket> planar_square() {
    return {
        {1, 2, {0.0, 0.0, 0.0}, {}},
        {2, 2, {1.0, 0.0, 0.0}, {}},
        {3, 2, {1.0, 1.0, 0.0}, {}},
        {4, 2, {0.0, 1.0, 0.0}, {}},
    };
}

[[nodiscard]] std::vector<BondRelation> square_bonds_with_diagonal() {
    return {{1, 2}, {1, 3}, {1, 4}, {2, 3}, {3, 4}};
}

[[nodiscard]] Matrix3d general_affine() {
    Matrix3d result{};
    result.value = {{{1.0 / 5.0, -1.0 / 10.0, 3.0 / 20.0},
                     {1.0 / 4.0, -3.0 / 20.0, 1.0 / 10.0},
                     {-1.0 / 5.0, 1.0 / 8.0, 1.0 / 20.0}}};
    return result;
}

[[nodiscard]] Matrix3d rigid_rotation_gradient() {
    Matrix3d result{};
    const Vec3d omega{0.3, -0.2, 0.4};
    result.value = {{{0.0, -omega.z, omega.y},
                     {omega.z, 0.0, -omega.x},
                     {-omega.y, omega.x, 0.0}}};
    return result;
}

[[nodiscard]] Matrix3d rational_proper_rotation() {
    Matrix3d result{};
    result.value = {{{1.0 / 9.0, 8.0 / 9.0, 4.0 / 9.0},
                     {8.0 / 9.0, 1.0 / 9.0, -4.0 / 9.0},
                     {-4.0 / 9.0, 4.0 / 9.0, -7.0 / 9.0}}};
    return result;
}

[[nodiscard]] Matrix3d signed_axis_proper_rotation() {
    Matrix3d result{};
    result.value = {{{1.0, 0.0, 0.0},
                     {0.0, -1.0, 0.0},
                     {0.0, 0.0, -1.0}}};
    return result;
}

void require_matrix_close(
    const Matrix3d& actual, const Matrix3d& expected, double tolerance) {
    for (std::size_t row = 0; row < 3U; ++row) {
        for (std::size_t column = 0; column < 3U; ++column) {
            MLS_REQUIRE(
                std::abs(actual.value[row][column] -
                         expected.value[row][column]) <= tolerance);
        }
    }
}

} // namespace

MLS_TEST("mechanical observability corrected WLS reproduces affine fields") {
    const auto geometry = tetrahedron();
    const auto field = general_affine();
    const auto packets = observation::with_affine_velocity(
        geometry, field, {0.7, -0.4, 0.2});
    const auto corrected = observation::build_corrected_local_gradient(
        packets, {.support_radius_m = 2.0});

    MLS_REQUIRE_EQ(
        corrected.status, observation::OperatorBuildStatus::built);
    MLS_REQUIRE_EQ(corrected.local_moments.size(), packets.size());
    for (const auto& moment : corrected.local_moments) {
        MLS_REQUIRE(moment.inverse_accepted);
        MLS_REQUIRE(std::isfinite(moment.inverse_residual_normalized));
        MLS_REQUIRE(moment.inverse_residual_normalized <=
                    moment.inverse_residual_tolerance);
    }
    const auto gradients =
        observation::evaluate_full_local_gradients(corrected, packets);
    MLS_REQUIRE_EQ(gradients.size(), packets.size());
    for (const auto& gradient : gradients) {
        require_matrix_close(gradient, field, 2.0e-14);
    }

    const auto rotation_packets = observation::with_affine_velocity(
        geometry, rigid_rotation_gradient(), {0.3, -0.2, 0.1});
    const auto rotation_operator = observation::build_corrected_local_gradient(
        rotation_packets, {.support_radius_m = 2.0});
    const auto symmetric = observation::apply_operator(
        rotation_operator.symmetric_gradient, rotation_packets);
    for (const auto value : symmetric) {
        MLS_REQUIRE(std::abs(value) < 3.0e-15);
    }
}

MLS_TEST("mechanical observability WLS is deterministic and ignores mass") {
    auto first = observation::with_affine_velocity(
        tetrahedron(), general_affine(), {0.1, 0.2, -0.3});
    auto permuted = first;
    std::ranges::reverse(permuted);
    for (auto& packet : permuted) {
        packet.mass_quanta += 100;
    }
    const auto left = observation::build_corrected_local_gradient(
        first, {.support_radius_m = 2.0});
    const auto right = observation::build_corrected_local_gradient(
        permuted, {.support_radius_m = 2.0});
    MLS_REQUIRE_EQ(left.status, right.status);
    MLS_REQUIRE_EQ(left.symmetric_gradient.matrix, right.symmetric_gradient.matrix);
    MLS_REQUIRE_EQ(left.full_gradient, right.full_gradient);
    MLS_REQUIRE_EQ(
        left.symmetric_gradient.packet_ids,
        right.symmetric_gradient.packet_ids);
}

MLS_TEST("mechanical observability WLS exposes singular lower dimensional support") {
    const auto corrected = observation::build_corrected_local_gradient(
        planar_square(), {.support_radius_m = 2.0});
    MLS_REQUIRE_EQ(
        corrected.status,
        observation::OperatorBuildStatus::singular_local_moment);
    MLS_REQUIRE_EQ(corrected.symmetric_gradient.matrix.row_count(), std::size_t{0});
    MLS_REQUIRE_EQ(corrected.full_gradient.row_count(), std::size_t{0});
    MLS_REQUIRE(std::ranges::all_of(
        corrected.local_moments,
        [](const auto& moment) {
            return moment.status ==
                observation::OperatorBuildStatus::singular_local_moment;
        }));
}

MLS_TEST("mechanical observability tetrahedron bond kernel is exactly rigid numerically") {
    const auto packets = tetrahedron();
    const auto bonds = observation::build_bond_rigidity_operator(
        packets, tetrahedron_bonds());
    const auto result = observation::diagnose_mechanical_observability(
        bonds.linearized, packets);

    std::cout << "[EVIDENCE] tetra_status="
              << observation::status_name(result.status)
              << " rank=" << result.operator_rank.rank
              << " nullity=" << result.operator_rank.nullity
              << " rigid_residual=" << result.normalized_rigid_residual
              << " null_residual="
              << result.operator_rank.normalized_null_residual << '\n';

    MLS_REQUIRE_EQ(result.status, observation::RankStatus::analyzed);
    MLS_REQUIRE_EQ(result.operator_rank.rank, std::size_t{6});
    MLS_REQUIRE_EQ(result.operator_rank.nullity, std::size_t{6});
    MLS_REQUIRE_EQ(result.rigid.rank, std::size_t{6});
    MLS_REQUIRE(result.rigid_subspace_in_kernel);
    MLS_REQUIRE(result.kernel_equals_rigid_subspace);
    MLS_REQUIRE_EQ(result.nonrigid_nullity, std::size_t{0});
    MLS_REQUIRE_EQ(
        result.nonrigid_nullspace_basis.column_count(), std::size_t{0});
    MLS_REQUIRE(result.operator_rank.normalized_null_residual < 2.0e-15);
}

MLS_TEST("mechanical observability objective volume removes planar square floppy mode") {
    const auto packets = planar_square();
    const auto bond_operator = observation::build_bond_rigidity_operator(
        packets, square_bonds_with_diagonal());
    const auto bond_result = observation::diagnose_mechanical_observability(
        bond_operator.linearized, packets);
    MLS_REQUIRE_EQ(bond_result.operator_rank.rank, std::size_t{5});
    MLS_REQUIRE_EQ(bond_result.operator_rank.nullity, std::size_t{7});
    MLS_REQUIRE_EQ(bond_result.nonrigid_nullity, std::size_t{1});
    MLS_REQUIRE(!bond_result.kernel_equals_rigid_subspace);

    const std::array volume_relations{
        VolumeRelation{1, {2, 3, 4}}};
    const auto volume_operator = observation::build_oriented_volume_operator(
        packets, volume_relations);
    MLS_REQUIRE_EQ(volume_operator.oriented_volumes_m3[0], 0.0);
    const auto enriched = observation::combine_relational_operators(
        bond_operator, volume_operator);
    const auto enriched_result =
        observation::diagnose_mechanical_observability(enriched, packets);
    std::cout << "[EVIDENCE] square_enriched_status="
              << observation::status_name(enriched_result.status)
              << " rank=" << enriched_result.operator_rank.rank
              << " nullity=" << enriched_result.operator_rank.nullity
              << " rigid_residual="
              << enriched_result.normalized_rigid_residual
              << " nonrigid_columns="
              << enriched_result.nonrigid_nullspace_basis.column_count()
              << '\n';
    MLS_REQUIRE_EQ(enriched_result.operator_rank.rank, std::size_t{6});
    MLS_REQUIRE_EQ(enriched_result.operator_rank.nullity, std::size_t{6});
    MLS_REQUIRE(enriched_result.kernel_equals_rigid_subspace);
}

MLS_TEST("mechanical observability affine relational predictions match operators") {
    const auto geometry = tetrahedron();
    const auto field = general_affine();
    const auto packets = observation::with_affine_velocity(
        geometry, field, {0.8, -0.6, 0.4});
    const auto relations = tetrahedron_bonds();
    const auto bond_operator = observation::build_bond_rigidity_operator(
        packets, relations);
    const auto observed_bond =
        observation::apply_operator(bond_operator.linearized, packets);
    const auto expected_bond = observation::expected_affine_bond_rates_m_per_s(
        packets, relations, field);
    MLS_REQUIRE_EQ(observed_bond.size(), expected_bond.size());
    for (std::size_t index = 0; index < observed_bond.size(); ++index) {
        MLS_REQUIRE(std::abs(observed_bond[index] - expected_bond[index]) <
                    2.0e-15);
    }

    const std::array volumes{VolumeRelation{1, {2, 3, 4}}};
    const auto volume_operator = observation::build_oriented_volume_operator(
        packets, volumes);
    const auto observed_volume =
        observation::apply_operator(volume_operator.linearized, packets);
    const auto expected_volume =
        observation::expected_affine_volume_rates_m3_per_s(
            packets, volumes, field);
    MLS_REQUIRE_EQ(observed_volume.size(), std::size_t{1});
    MLS_REQUIRE(std::abs(observed_volume[0] - expected_volume[0]) < 2.0e-15);
    MLS_REQUIRE(std::abs(expected_volume[0] - 0.1) < 2.0e-15);
}

MLS_TEST("mechanical observability finite relations are rigid objective") {
    const auto packets = observation::with_affine_velocity(
        tetrahedron(), general_affine(), {0.1, 0.2, 0.3});
    const auto rotation = rational_proper_rotation();
    MLS_REQUIRE(observation::is_proper_rotation(rotation, 2.0e-15));
    const auto transformed = observation::similarity_transform_packets(
        packets, rotation, {13.0 / 100.0, -7.0 / 100.0, 21.0 / 100.0}, 1.0);
    const std::array volumes{VolumeRelation{1, {2, 3, 4}}};
    const auto comparison = observation::compare_finite_relations(
        packets, transformed, tetrahedron_bonds(), volumes);
    MLS_REQUIRE(comparison.finite);
    MLS_REQUIRE(comparison.maximum_bond_absolute_error_m < 5.0e-16);
    MLS_REQUIRE(comparison.maximum_volume_absolute_error_m3 < 5.0e-16);

    const auto signed_axis = signed_axis_proper_rotation();
    MLS_REQUIRE(observation::is_proper_rotation(signed_axis, 2.0e-15));
    const auto signed_axis_transformed =
        observation::similarity_transform_packets(
            packets, signed_axis,
            {13.0 / 100.0, -7.0 / 100.0, 21.0 / 100.0}, 1.0);
    const auto signed_axis_comparison = observation::compare_finite_relations(
        packets, signed_axis_transformed, tetrahedron_bonds(), volumes);
    MLS_REQUIRE(signed_axis_comparison.finite);
    MLS_REQUIRE(
        signed_axis_comparison.maximum_bond_absolute_error_m < 5.0e-16);
    MLS_REQUIRE(
        signed_axis_comparison.maximum_volume_absolute_error_m3 < 5.0e-16);

    auto reflection = Matrix3d::identity();
    reflection.value[0][0] = -1.0;
    MLS_REQUIRE(!observation::is_proper_rotation(reflection));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::similarity_transform_packets(
            packets, reflection, {}, 1.0));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::similarity_transform_packets(
            packets, rotation, {}, 0.0));
}

MLS_TEST("mechanical observability D selector is graph-derived and subset-safe") {
    const auto packets = tetrahedron();
    const auto bonds = tetrahedron_bonds();
    const auto selected = observation::select_oriented_volume_relations(
        packets, bonds);
    MLS_REQUIRE_EQ(selected.size(), std::size_t{4});
    for (std::size_t index = 0U; index < selected.size(); ++index) {
        MLS_REQUIRE_EQ(selected[index].center_id,
                       static_cast<std::uint64_t>(index + 1U));
    }
    observation::validate_selected_oriented_volume_relations(
        packets, bonds, selected);
    observation::validate_selected_oriented_volume_relations(
        packets, bonds, std::span<const VolumeRelation>{});
    const std::array registered_subset{VolumeRelation{1, {2, 3, 4}}};
    observation::validate_selected_oriented_volume_relations(
        packets, bonds, registered_subset);

    auto five_packets = packets;
    five_packets.push_back({5, 1, {-1.0, 0.2, 0.3}, {}});
    const std::vector<BondRelation> star_bonds{
        {1, 2}, {1, 3}, {1, 4}, {1, 5}};
    const auto star_selected = observation::select_oriented_volume_relations(
        five_packets, star_bonds);
    MLS_REQUIRE_EQ(star_selected.size(), std::size_t{1});
    std::vector<VolumeRelation> alternatives{
        {1, {2, 3, 4}}, {1, {2, 3, 5}},
        {1, {2, 4, 5}}, {1, {3, 4, 5}}};
    const auto different = std::ranges::find_if(
        alternatives,
        [&](const auto& value) { return value != star_selected.front(); });
    MLS_REQUIRE(different != alternatives.end());
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::validate_selected_oriented_volume_relations(
            five_packets, star_bonds, std::span{&*different, std::size_t{1}}));

    std::vector<VolumeRelation> duplicate_center{
        star_selected.front(), *different};
    std::ranges::sort(duplicate_center, {}, [](const auto& value) {
        return std::tuple{value.center_id, value.other_ids[0],
            value.other_ids[1], value.other_ids[2]};
    });
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::validate_selected_oriented_volume_relations(
            five_packets, star_bonds, duplicate_center));

    const auto square = planar_square();
    const auto square_bonds = square_bonds_with_diagonal();
    const std::array nonincident{VolumeRelation{2, {1, 3, 4}}};
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::validate_selected_oriented_volume_relations(
            square, square_bonds, nonincident));
}

MLS_TEST("mechanical observability preserves intentional and degenerate modes") {
    const auto square = planar_square();
    const std::array underconnected{BondRelation{1, 2}, BondRelation{3, 4}};
    const auto operator_result = observation::build_bond_rigidity_operator(
        square, underconnected);
    const auto diagnostic = observation::diagnose_mechanical_observability(
        operator_result.linearized, square);
    MLS_REQUIRE_EQ(diagnostic.operator_rank.rank, std::size_t{2});
    MLS_REQUIRE_EQ(diagnostic.operator_rank.nullity, std::size_t{10});
    MLS_REQUIRE_EQ(diagnostic.nonrigid_nullity, std::size_t{4});

    const std::vector<MechanicalPacket> filament{
        {1, 1, {-1.0, 0.0, 0.0}, {}},
        {2, 1, {0.0, 0.0, 0.0}, {}},
        {3, 1, {1.0, 0.0, 0.0}, {}},
    };
    const auto rigid = observation::build_rigid_motion_subspace(filament);
    MLS_REQUIRE_EQ(rigid.rank, std::size_t{5});
}

MLS_TEST("mechanical observability rejects malformed topology and state") {
    const auto packets = tetrahedron();
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::build_bond_rigidity_operator(
            packets, std::array{BondRelation{2, 1}}));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::build_bond_rigidity_operator(
            packets, std::array{BondRelation{1, 1}}));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::build_bond_rigidity_operator(
            packets, std::array{BondRelation{1, 2}, BondRelation{1, 2}}));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::build_oriented_volume_operator(
            packets, std::array{VolumeRelation{1, {3, 2, 4}}}));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::build_oriented_volume_operator(
            packets, std::array{VolumeRelation{2, {1, 2, 4}}}));

    auto duplicate = packets;
    duplicate[1].id = duplicate[0].id;
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::build_corrected_local_gradient(
            duplicate, {.support_radius_m = 2.0}));
    auto invalid_mass = packets;
    invalid_mass[0].mass_quanta = 0;
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::build_bond_rigidity_operator(
            invalid_mass, tetrahedron_bonds()));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::build_corrected_local_gradient(
            packets, {.support_radius_m = 0.0}));
}

MLS_TEST("mechanical observability row and rank diagnostics fail closed") {
    observation::DenseMatrix matrix(2, 3);
    matrix(0, 0) = 1.0;
    const auto normalization = observation::normalize_operator_rows(matrix);
    MLS_REQUIRE(!normalization.complete);
    MLS_REQUIRE_EQ(normalization.first_invalid_row, std::size_t{1});

    observation::DenseMatrix identity(3, 3);
    identity(0, 0) = 1.0;
    identity(1, 1) = 1.0;
    identity(2, 2) = 1.0;
    const auto rank = observation::diagnose_rank_and_nullspace(identity);
    MLS_REQUIRE_EQ(rank.status, observation::RankStatus::analyzed);
    MLS_REQUIRE_EQ(rank.rank, std::size_t{3});
    MLS_REQUIRE_EQ(rank.nullity, std::size_t{0});
    MLS_REQUIRE(rank.basis_complete);

    auto bounded_policy = observation::RankPolicy{};
    bounded_policy.maximum_columns = 2;
    const auto bounded = observation::diagnose_rank_and_nullspace(
        identity, bounded_policy);
    MLS_REQUIRE_EQ(bounded.status, observation::RankStatus::size_limit);

    observation::DenseMatrix structurally_rank_deficient(2, 3);
    structurally_rank_deficient(0, 0) = 1.0;
    const auto structural = observation::diagnose_rank_and_nullspace(
        structurally_rank_deficient);
    MLS_REQUIRE_EQ(structural.status, observation::RankStatus::analyzed);
    MLS_REQUIRE_EQ(structural.rank, std::size_t{1});
    MLS_REQUIRE_EQ(structural.diagonal_magnitudes.size(), std::size_t{2});
    MLS_REQUIRE_EQ(structural.diagonal_magnitudes[1], 0.0);

    observation::DenseMatrix structural_zero(2, 3);
    const auto zero_rank = observation::diagnose_rank_and_nullspace(
        structural_zero);
    MLS_REQUIRE_EQ(zero_rank.status, observation::RankStatus::analyzed);
    MLS_REQUIRE_EQ(zero_rank.rank, std::size_t{0});
    MLS_REQUIRE_EQ(zero_rank.diagonal_magnitudes.size(), std::size_t{2});
    MLS_REQUIRE(zero_rank.threshold > 0.0);

    auto strict_residual_policy = observation::RankPolicy{};
    strict_residual_policy.residual_safety_factor = 1.0e-6;
    const auto tetra_operator = observation::build_bond_rigidity_operator(
        tetrahedron(), tetrahedron_bonds());
    const auto residual_rejected =
        observation::diagnose_mechanical_observability(
            tetra_operator.linearized, tetrahedron(), strict_residual_policy);
    MLS_REQUIRE_EQ(
        residual_rejected.status, observation::RankStatus::numerical_failure);
    MLS_REQUIRE(!residual_rejected.kernel_equals_rigid_subspace);
}

MLS_TEST("mechanical observability WLS rejects nonfinite coordinate subtraction") {
    const double large = 0.75 * std::numeric_limits<double>::max();
    const std::vector<MechanicalPacket> packets{
        {1, 1, {large, 0.0, 0.0}, {}},
        {2, 1, {-large, 0.0, 0.0}, {}},
    };
    const auto result = observation::build_corrected_local_gradient(
        packets,
        {.support_radius_m = std::numeric_limits<double>::max()});
    MLS_REQUIRE_EQ(
        result.status, observation::OperatorBuildStatus::numerical_failure);
    MLS_REQUIRE(std::ranges::all_of(
        result.local_moments,
        [](const auto& moment) {
            return moment.status ==
                observation::OperatorBuildStatus::numerical_failure;
        }));
}

MLS_TEST("mechanical observability checkpoint is canonical and diagnostics read only") {
    observation::MechanicalObservabilityState state{};
    state.support_radius_m = 2.0;
    state.packets = tetrahedron();
    state.bonds = tetrahedron_bonds();
    state.volumes = {VolumeRelation{1, {2, 3, 4}}};
    const auto before = observation::serialize_mechanical_observability_state(state);
    const auto decoded =
        observation::deserialize_mechanical_observability_state(before);
    MLS_REQUIRE_EQ(decoded, state);
    MLS_REQUIRE_EQ(
        observation::serialize_mechanical_observability_state(decoded), before);

    const auto bond_operator = observation::build_bond_rigidity_operator(
        state.packets, state.bonds);
    static_cast<void>(observation::diagnose_mechanical_observability(
        bond_operator.linearized, state.packets));
    static_cast<void>(observation::build_corrected_local_gradient(
        state.packets, {.support_radius_m = state.support_radius_m}));
    const auto after = observation::serialize_mechanical_observability_state(state);
    MLS_REQUIRE_EQ(after, before);

    auto trailing = before;
    trailing.push_back(0U);
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::deserialize_mechanical_observability_state(trailing));
    auto corrupt = before;
    corrupt[0] ^= 1U;
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::deserialize_mechanical_observability_state(corrupt));

    auto permuted = state;
    std::ranges::reverse(permuted.packets);
    MLS_REQUIRE_EQ(
        observation::serialize_mechanical_observability_state(permuted), before);

    observation::MechanicalObservabilityState candidate_c{};
    candidate_c.support_radius_m = 2.0;
    candidate_c.packets = planar_square();
    candidate_c.bonds = square_bonds_with_diagonal();
    MLS_REQUIRE(!observation::serialize_mechanical_observability_state(
                     candidate_c).empty());
    candidate_c.volumes = {VolumeRelation{2, {1, 3, 4}}};
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        observation::serialize_mechanical_observability_state(candidate_c));
}
