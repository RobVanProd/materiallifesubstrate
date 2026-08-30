#include "test_harness.hpp"

#include "mls/constitutive_expressivity_lab.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <map>
#include <numbers>
#include <vector>

namespace {

namespace constitutive = mls::experimental::constitutive_expressivity;
namespace observation = mls::experimental::mechanical_observability;
using mls::experimental::Matrix3d;
using mls::experimental::Vec3d;
using constitutive::PacketDisplacement;
using observation::BondRelation;
using observation::MechanicalPacket;

[[nodiscard]] std::vector<MechanicalPacket> tetrahedron() {
    return {
        {1, 1, {0.0, 0.0, 0.0}, {}},
        {2, 1, {1.0, 0.0, 0.0}, {}},
        {3, 1, {0.0, 1.0, 0.0}, {}},
        {4, 1, {0.0, 0.0, 1.0}, {}},
    };
}

[[nodiscard]] std::vector<BondRelation> k4() {
    return {{1, 2}, {1, 3}, {1, 4}, {2, 3}, {2, 4}, {3, 4}};
}

struct IsotropicStar final {
    std::vector<MechanicalPacket> packets{};
    std::vector<constitutive::WeightedRelation> weighted{};
};

// Seven unoriented directions. Axes have weight 8 and the four tetrahedral
// body-diagonal lines have weight 9. Their second/fourth moments are isotropic:
// m=60, sum(w*n*n)=20I, and the pair control has lambda=mu.
[[nodiscard]] IsotropicStar isotropic_star() {
    const auto d = 1.0 / std::sqrt(3.0);
    IsotropicStar result{};
    result.packets = {
        {1, 1, {0.0, 0.0, 0.0}, {}},
        {2, 1, {1.0, 0.0, 0.0}, {}},
        {3, 1, {0.0, 1.0, 0.0}, {}},
        {4, 1, {0.0, 0.0, 1.0}, {}},
        {5, 1, {d, d, d}, {}},
        {6, 1, {d, -d, -d}, {}},
        {7, 1, {-d, d, -d}, {}},
        {8, 1, {-d, -d, d}, {}},
    };
    result.weighted = {
        {{1, 2}, 8.0}, {{1, 3}, 8.0}, {{1, 4}, 8.0},
        {{1, 5}, 9.0}, {{1, 6}, 9.0}, {{1, 7}, 9.0},
        {{1, 8}, 9.0},
    };
    return result;
}

// Independent nine-line cubature: three axes at weight 1 and both unoriented
// face diagonals in each coordinate plane at weight 2. It has m=15,
// sum(w*n*n)=5I, and the same isotropic fourth moment ratio.
[[nodiscard]] IsotropicStar face_diagonal_star() {
    const auto d = 1.0 / std::sqrt(2.0);
    IsotropicStar result{};
    result.packets = {
        {1, 1, {0.0, 0.0, 0.0}, {}},
        {2, 1, {1.0, 0.0, 0.0}, {}},
        {3, 1, {0.0, 1.0, 0.0}, {}},
        {4, 1, {0.0, 0.0, 1.0}, {}},
        {5, 1, {d, d, 0.0}, {}},
        {6, 1, {d, -d, 0.0}, {}},
        {7, 1, {d, 0.0, d}, {}},
        {8, 1, {d, 0.0, -d}, {}},
        {9, 1, {0.0, d, d}, {}},
        {10, 1, {0.0, d, -d}, {}},
    };
    result.weighted = {
        {{1, 2}, 1.0}, {{1, 3}, 1.0}, {{1, 4}, 1.0},
        {{1, 5}, 2.0}, {{1, 6}, 2.0}, {{1, 7}, 2.0},
        {{1, 8}, 2.0}, {{1, 9}, 2.0}, {{1, 10}, 2.0},
    };
    return result;
}

[[nodiscard]] std::vector<PacketDisplacement> affine_displacements(
    std::span<const MechanicalPacket> packets, const Matrix3d& strain) {
    std::vector<PacketDisplacement> result;
    result.reserve(packets.size());
    for (const auto& packet : packets) {
        result.push_back({packet.id,
                          mls::experimental::multiply(
                              strain, packet.position_m)});
    }
    return result;
}

[[nodiscard]] Matrix3d diagonal(double x, double y, double z) {
    Matrix3d result{};
    result.value[0][0] = x;
    result.value[1][1] = y;
    result.value[2][2] = z;
    return result;
}

[[nodiscard]] Matrix3d add(Matrix3d lhs, const Matrix3d& rhs) {
    for (std::size_t row = 0; row < 3U; ++row) {
        for (std::size_t column = 0; column < 3U; ++column) {
            lhs.value[row][column] += rhs.value[row][column];
        }
    }
    return lhs;
}

[[nodiscard]] std::vector<Matrix3d> kelvin_basis() {
    const auto inverse_sqrt_two = 1.0 / std::sqrt(2.0);
    std::vector<Matrix3d> result(6);
    result[0].value[0][0] = 1.0;
    result[1].value[1][1] = 1.0;
    result[2].value[2][2] = 1.0;
    result[3].value[0][1] = inverse_sqrt_two;
    result[3].value[1][0] = inverse_sqrt_two;
    result[4].value[0][2] = inverse_sqrt_two;
    result[4].value[2][0] = inverse_sqrt_two;
    result[5].value[1][2] = inverse_sqrt_two;
    result[5].value[2][1] = inverse_sqrt_two;
    return result;
}

[[nodiscard]] double local_energy(
    const constitutive::RelationEnergyOperator& energy_operator,
    const constitutive::RelationExtensionState& extensions,
    std::uint64_t packet_id) {
    const auto evaluated = constitutive::evaluate_energy(
        energy_operator, extensions);
    MLS_REQUIRE(evaluated.finite);
    const auto found = std::ranges::find(
        evaluated.local, packet_id, &constitutive::LocalEnergyValue::packet_id);
    MLS_REQUIRE(found != evaluated.local.end());
    return found->total_j;
}

[[nodiscard]] double center_affine_energy(
    const IsotropicStar& star,
    const constitutive::RelationEnergyOperator& energy_operator,
    const Matrix3d& strain) {
    std::vector<BondRelation> relations;
    for (const auto& entry : star.weighted) {
        relations.push_back(entry.relation);
    }
    const auto extensions = constitutive::evaluate_linearized_relation_extensions(
        star.packets, affine_displacements(star.packets, strain), relations);
    return local_energy(energy_operator, extensions, 1U);
}

[[nodiscard]] double pair_affine_energy(
    const IsotropicStar& star,
    const constitutive::RelationEnergyOperator& energy_operator,
    const Matrix3d& strain) {
    std::vector<BondRelation> relations;
    for (const auto& entry : star.weighted) {
        relations.push_back(entry.relation);
    }
    const auto extensions = constitutive::evaluate_linearized_relation_extensions(
        star.packets, affine_displacements(star.packets, strain), relations);
    const auto evaluated = constitutive::evaluate_energy(
        energy_operator, extensions);
    MLS_REQUIRE(evaluated.finite);
    return evaluated.total_j;
}

[[nodiscard]] std::vector<MechanicalPacket> affine_configuration(
    std::span<const MechanicalPacket> packets, const Matrix3d& map,
    Vec3d translation) {
    std::vector<MechanicalPacket> result(packets.begin(), packets.end());
    for (auto& packet : result) {
        packet.position_m =
            mls::experimental::multiply(map, packet.position_m) + translation;
    }
    return result;
}

[[nodiscard]] Matrix3d rational_rotation() {
    Matrix3d result{};
    result.value = {{{1.0 / 9.0, 8.0 / 9.0, 4.0 / 9.0},
                     {8.0 / 9.0, 1.0 / 9.0, -4.0 / 9.0},
                     {-4.0 / 9.0, 4.0 / 9.0, -7.0 / 9.0}}};
    return result;
}

[[nodiscard]] bool close(double lhs, double rhs, double relative) {
    return std::abs(lhs - rhs) <=
        relative * std::max({1.0, std::abs(lhs), std::abs(rhs)});
}

[[nodiscard]] double factor_gram_residual(
    const constitutive::RelationEnergyOperator& energy_operator) {
    double result = 0.0;
    for (std::size_t row = 0; row < energy_operator.h_j_per_m2.row_count();
         ++row) {
        for (std::size_t column = 0;
             column < energy_operator.h_j_per_m2.column_count(); ++column) {
            long double gram = 0.0L;
            for (std::size_t factor_row = 0;
                 factor_row < energy_operator.factor_sqrt_j_per_m.row_count();
                 ++factor_row) {
                gram += static_cast<long double>(
                    energy_operator.factor_sqrt_j_per_m(factor_row, row)) *
                    energy_operator.factor_sqrt_j_per_m(factor_row, column);
            }
            result = std::max(
                result,
                std::abs(static_cast<double>(gram) -
                         energy_operator.h_j_per_m2(row, column)));
        }
    }
    return result;
}

} // namespace

MLS_TEST("constitutive pair control reproduces the registered Cauchy restriction") {
    const auto star = isotropic_star();
    std::vector<constitutive::PairRelationCoefficient> coefficients;
    for (const auto& entry : star.weighted) {
        coefficients.push_back({entry.relation, entry.weight});
    }
    const auto pair = constitutive::build_pair_separable_energy(
        star.packets, coefficients);
    const auto identity = Matrix3d::identity();
    const auto inverse_sqrt_two = 1.0 / std::sqrt(2.0);
    const auto unit_deviator =
        diagonal(inverse_sqrt_two, -inverse_sqrt_two, 0.0);
    const auto bulk = 2.0 * pair_affine_energy(star, pair, identity) / 9.0;
    const auto shear = pair_affine_energy(star, pair, unit_deviator);
    MLS_REQUIRE(close(pair_affine_energy(star, pair, identity), 30.0, 2.0e-15));
    MLS_REQUIRE(close(shear, 4.0, 2.0e-15));
    MLS_REQUIRE(close(bulk / shear, 5.0 / 3.0, 3.0e-15));
    MLS_REQUIRE(factor_gram_residual(pair) < 2.0e-15);
    for (std::size_t row = 0; row < pair.h_j_per_m2.row_count(); ++row) {
        for (std::size_t column = 0; column < pair.h_j_per_m2.column_count();
             ++column) {
            if (row != column) {
                MLS_REQUIRE_EQ(pair.h_j_per_m2(row, column), 0.0);
            }
        }
    }
}

MLS_TEST("constitutive collective star independently spans four bulk shear targets") {
    const auto star = isotropic_star();
    const auto basis = kelvin_basis();
    const std::array ratios{1.0 / 3.0, 1.0, 2.0, 10.0};
    for (const auto ratio : ratios) {
        constexpr auto shear_target = 4.0;
        const auto bulk_target = ratio * shear_target;
        const auto collective = constitutive::build_local_collective_energy(
            star.packets, star.weighted,
            {.dilatational_coefficient_j_per_m2 =
                 3.0 * bulk_target / 20.0,
             .deviatoric_coefficient_j_per_m2 = shear_target / 4.0});
        MLS_REQUIRE_EQ(collective.nonlocal_off_diagonal_count, std::size_t{0});
        const auto center = std::ranges::find(
            collective.local_contributions, std::uint64_t{1},
            &constitutive::LocalCollectiveContribution::packet_id);
        MLS_REQUIRE(center != collective.local_contributions.end());
        MLS_REQUIRE_EQ(center->incident_relation_count, std::size_t{7});
        MLS_REQUIRE(close(center->weighted_length_moment_m2, 60.0, 3.0e-15));

        const auto identity = Matrix3d::identity();
        const auto inverse_sqrt_two = 1.0 / std::sqrt(2.0);
        const auto unit_deviator =
            diagonal(inverse_sqrt_two, -inverse_sqrt_two, 0.0);
        const auto bulk =
            2.0 * center_affine_energy(star, collective, identity) / 9.0;
        const auto shear =
            center_affine_energy(star, collective, unit_deviator);
        MLS_REQUIRE(close(bulk, bulk_target, 2.0e-13));
        MLS_REQUIRE(close(shear, shear_target, 2.0e-13));
        MLS_REQUIRE(close(bulk / shear, ratio, 2.0e-13));

        // Six Kelvin directions and all mixed pairs recover the isotropic
        // tangent C=K*t*t^T+2G*P_dev by energy polarization.
        std::array<std::array<double, 6>, 6> tangent{};
        for (std::size_t i = 0; i < basis.size(); ++i) {
            tangent[i][i] =
                2.0 * center_affine_energy(star, collective, basis[i]);
        }
        for (std::size_t i = 0; i < basis.size(); ++i) {
            for (std::size_t j = i + 1U; j < basis.size(); ++j) {
                const auto mixed = center_affine_energy(
                    star, collective, add(basis[i], basis[j]));
                tangent[i][j] = mixed - 0.5 * tangent[i][i] -
                    0.5 * tangent[j][j];
                tangent[j][i] = tangent[i][j];
            }
        }
        for (std::size_t i = 0; i < 6U; ++i) {
            for (std::size_t j = 0; j < 6U; ++j) {
                const auto trace_i = i < 3U ? 1.0 : 0.0;
                const auto trace_j = j < 3U ? 1.0 : 0.0;
                const auto identity_kelvin = i == j ? 1.0 : 0.0;
                const auto expected = bulk_target * trace_i * trace_j +
                    2.0 * shear_target *
                        (identity_kelvin - trace_i * trace_j / 3.0);
                MLS_REQUIRE(close(tangent[i][j], expected, 4.0e-13));
            }
        }
        MLS_REQUIRE(constitutive::maximum_symmetry_residual(
                        collective.h_j_per_m2) < 2.0e-14);
        MLS_REQUIRE(factor_gram_residual(collective) < 2.0e-13);
    }
}

MLS_TEST("constitutive independent face diagonal star confirms two modulus span") {
    const auto star = face_diagonal_star();
    const auto identity = Matrix3d::identity();
    const auto inverse_sqrt_two = 1.0 / std::sqrt(2.0);
    const auto unit_deviator =
        diagonal(inverse_sqrt_two, -inverse_sqrt_two, 0.0);
    const std::array ratios{1.0 / 3.0, 1.0, 2.0, 10.0};
    for (const auto ratio : ratios) {
        constexpr auto shear_target = 3.0;
        const auto bulk_target = ratio * shear_target;
        const auto collective = constitutive::build_local_collective_energy(
            star.packets, star.weighted,
            {.dilatational_coefficient_j_per_m2 =
                 3.0 * bulk_target / 5.0,
             .deviatoric_coefficient_j_per_m2 = shear_target});
        const auto center = std::ranges::find(
            collective.local_contributions, std::uint64_t{1},
            &constitutive::LocalCollectiveContribution::packet_id);
        MLS_REQUIRE(center != collective.local_contributions.end());
        MLS_REQUIRE_EQ(center->incident_relation_count, std::size_t{9});
        MLS_REQUIRE(close(center->weighted_length_moment_m2, 15.0, 3.0e-15));
        const auto bulk =
            2.0 * center_affine_energy(star, collective, identity) / 9.0;
        const auto shear =
            center_affine_energy(star, collective, unit_deviator);
        MLS_REQUIRE(close(bulk, bulk_target, 2.0e-13));
        MLS_REQUIRE(close(shear, shear_target, 2.0e-13));
        MLS_REQUIRE(close(bulk / shear, ratio, 2.0e-13));
    }

    std::vector<constitutive::PairRelationCoefficient> coefficients;
    for (const auto& entry : star.weighted) {
        coefficients.push_back({entry.relation, entry.weight});
    }
    const auto pair = constitutive::build_pair_separable_energy(
        star.packets, coefficients);
    const auto pair_bulk =
        2.0 * pair_affine_energy(star, pair, identity) / 9.0;
    const auto pair_shear = pair_affine_energy(star, pair, unit_deviator);
    MLS_REQUIRE(close(pair_bulk / pair_shear, 5.0 / 3.0, 4.0e-15));
}

MLS_TEST("constitutive active-family moment does not hide a deleted relation") {
    const auto star = isotropic_star();
    const auto full = constitutive::build_local_collective_energy(
        star.packets, star.weighted,
        {.dilatational_coefficient_j_per_m2 = 2.0,
         .deviatoric_coefficient_j_per_m2 = 3.0});
    auto deleted_relations = star.weighted;
    deleted_relations.erase(deleted_relations.begin());
    const auto deleted = constitutive::build_local_collective_energy(
        star.packets, deleted_relations,
        {.dilatational_coefficient_j_per_m2 = 2.0,
         .deviatoric_coefficient_j_per_m2 = 3.0});
    const auto identity = Matrix3d::identity();
    const auto full_energy = center_affine_energy(star, full, identity);
    IsotropicStar deleted_star{star.packets, deleted_relations};
    const auto deleted_energy =
        center_affine_energy(deleted_star, deleted, identity);
    MLS_REQUIRE(close(deleted_energy / full_energy, 52.0 / 60.0, 4.0e-15));
    const auto center = std::ranges::find(
        deleted.local_contributions, std::uint64_t{1},
        &constitutive::LocalCollectiveContribution::packet_id);
    MLS_REQUIRE(center != deleted.local_contributions.end());
    MLS_REQUIRE(close(center->weighted_length_moment_m2, 52.0, 3.0e-15));
}

MLS_TEST("constitutive local H preserves rigid kernel and existing floppy modes") {
    const auto packets = tetrahedron();
    std::vector<constitutive::WeightedRelation> weighted;
    for (const auto relation : k4()) {
        weighted.push_back({relation, 1.0});
    }
    const auto model = constitutive::build_local_collective_energy(
        packets, weighted,
        {.dilatational_coefficient_j_per_m2 = 2.0,
         .deviatoric_coefficient_j_per_m2 = 3.0});
    const auto rigidity = observation::build_bond_rigidity_operator(
        packets, k4());
    const auto hessian = constitutive::assemble_packet_energy_hessian(
        rigidity, model);
    MLS_REQUIRE(constitutive::maximum_symmetry_residual(hessian) < 2.0e-14);
    const auto k_operator =
        constitutive::assemble_energy_factor_times_rigidity(rigidity, model);
    const auto diagnostics = observation::diagnose_mechanical_observability(
        k_operator, packets);
    MLS_REQUIRE_EQ(diagnostics.status, observation::RankStatus::analyzed);
    MLS_REQUIRE(diagnostics.kernel_equals_rigid_subspace);

    auto missing = k4();
    missing.pop_back();
    std::vector<constitutive::WeightedRelation> missing_weighted;
    for (const auto relation : missing) {
        missing_weighted.push_back({relation, 1.0});
    }
    const auto floppy_model = constitutive::build_local_collective_energy(
        packets, missing_weighted,
        {.dilatational_coefficient_j_per_m2 = 2.0,
         .deviatoric_coefficient_j_per_m2 = 3.0});
    const auto floppy_rigidity = observation::build_bond_rigidity_operator(
        packets, missing);
    const auto floppy_k = constitutive::assemble_energy_factor_times_rigidity(
        floppy_rigidity, floppy_model);
    const auto floppy = observation::diagnose_mechanical_observability(
        floppy_k, packets);
    MLS_REQUIRE_EQ(floppy.status, observation::RankStatus::analyzed);
    MLS_REQUIRE_EQ(floppy.nonrigid_nullity, std::size_t{1});
    MLS_REQUIRE(!floppy.kernel_equals_rigid_subspace);
}

MLS_TEST("constitutive finite energy is objective label free and dimensioned") {
    const auto reference = tetrahedron();
    std::vector<constitutive::WeightedRelation> weighted;
    for (const auto relation : k4()) {
        weighted.push_back({relation, 1.0});
    }
    Matrix3d deformation = Matrix3d::identity();
    deformation.value[0][0] = 1.1;
    deformation.value[1][1] = 0.9;
    deformation.value[2][2] = 1.05;
    deformation.value[0][1] = 0.15;
    const auto current = affine_configuration(reference, deformation, {});
    const auto model = constitutive::build_local_collective_energy(
        reference, weighted,
        {.dilatational_coefficient_j_per_m2 = 2.0,
         .deviatoric_coefficient_j_per_m2 = 3.0});
    const auto baseline = constitutive::evaluate_finite_energy(
        model, reference, current);
    MLS_REQUIRE(baseline.finite);
    MLS_REQUIRE(baseline.total_j > 0.0);

    const auto rotation = rational_rotation();
    auto rotated_reference = affine_configuration(
        reference, rotation, {3.0, -2.0, 5.0});
    auto rotated_current = affine_configuration(
        current, rotation, {3.0, -2.0, 5.0});
    std::ranges::reverse(rotated_reference);
    std::ranges::rotate(rotated_current, rotated_current.begin() + 1);
    auto permuted_relations = weighted;
    std::ranges::reverse(permuted_relations);
    for (std::size_t index = 0; index < permuted_relations.size(); index += 2U) {
        std::swap(permuted_relations[index].relation.first_id,
                  permuted_relations[index].relation.second_id);
    }
    const auto rotated_model = constitutive::build_local_collective_energy(
        rotated_reference, permuted_relations,
        {.dilatational_coefficient_j_per_m2 = 2.0,
         .deviatoric_coefficient_j_per_m2 = 3.0});
    const auto rotated = constitutive::evaluate_finite_energy(
        rotated_model, rotated_reference, rotated_current);
    MLS_REQUIRE(rotated.finite);
    MLS_REQUIRE(close(rotated.total_j, baseline.total_j, 2.0e-13));

    // With weights and J/m^2 coefficients held fixed, scaling every reference
    // and current length by s scales extension^2 and therefore energy by s^2.
    constexpr auto scale = 2.5;
    Matrix3d scaled_map = Matrix3d::identity();
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        scaled_map.value[axis][axis] = scale;
    }
    const auto scaled_reference =
        affine_configuration(reference, scaled_map, {});
    const auto scaled_current = affine_configuration(current, scaled_map, {});
    const auto scaled_model = constitutive::build_local_collective_energy(
        scaled_reference, weighted,
        {.dilatational_coefficient_j_per_m2 = 2.0,
         .deviatoric_coefficient_j_per_m2 = 3.0});
    const auto scaled = constitutive::evaluate_finite_energy(
        scaled_model, scaled_reference, scaled_current);
    MLS_REQUIRE(close(
        scaled.total_j, scale * scale * baseline.total_j, 3.0e-13));

    const std::map<std::uint64_t, std::uint64_t> renaming{
        {1, 40}, {2, 10}, {3, 30}, {4, 20}};
    auto renamed_reference = reference;
    auto renamed_current = current;
    for (auto& packet : renamed_reference) {
        packet.id = renaming.at(packet.id);
    }
    for (auto& packet : renamed_current) {
        packet.id = renaming.at(packet.id);
    }
    auto renamed_relations = weighted;
    for (auto& entry : renamed_relations) {
        entry.relation.first_id = renaming.at(entry.relation.first_id);
        entry.relation.second_id = renaming.at(entry.relation.second_id);
    }
    const auto renamed_model = constitutive::build_local_collective_energy(
        renamed_reference, renamed_relations,
        {.dilatational_coefficient_j_per_m2 = 2.0,
         .deviatoric_coefficient_j_per_m2 = 3.0});
    const auto renamed = constitutive::evaluate_finite_energy(
        renamed_model, renamed_reference, renamed_current);
    MLS_REQUIRE(renamed.finite);
    MLS_REQUIRE(close(renamed.total_j, baseline.total_j, 3.0e-14));
}

MLS_TEST("constitutive evaluator rejects hidden or malformed relation data") {
    const auto packets = tetrahedron();
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        constitutive::build_pair_separable_energy(
            packets,
            std::array{constitutive::PairRelationCoefficient{{1, 2}, 0.0}}));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        constitutive::build_local_collective_energy(
            packets,
            std::array{constitutive::WeightedRelation{{1, 2}, 1.0},
                       constitutive::WeightedRelation{{2, 1}, 2.0}},
            {}));
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        constitutive::build_local_collective_energy(
            packets,
            std::array{constitutive::WeightedRelation{{1, 99}, 1.0}},
            {}));
    const auto model = constitutive::build_local_collective_energy(
        packets,
        std::array{constitutive::WeightedRelation{{1, 2}, 1.0}}, {});
    auto wrong_reference = packets;
    wrong_reference[1].position_m.x = 2.0;
    const auto extensions = constitutive::evaluate_finite_relation_extensions(
        wrong_reference, wrong_reference,
        std::array{BondRelation{1, 2}});
    MLS_REQUIRE_THROWS(
        std::invalid_argument,
        constitutive::evaluate_energy(model, extensions));
}
